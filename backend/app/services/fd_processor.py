"""
Financial-Disclosure document processor.

This is the FD analogue of GPDocumentProcessor (backend/app/services/gp_processor.py).
Per the §1.2 reuse-principle decision (see the plan's step 2c): we share the
LandingAI ADE *substrate* — same SDK, same env-var convention, same parse-then-
extract pattern — but build a separate processor with FD schemas and write to
the fd_* tables. No refactor of gp_processor.py until duplication actually
hurts.

The processor:

  1. Records the upload in fd_documents (status='pending').
  2. Calls LandingAI parse → chunks + markdown.
  3. Calls LandingAI extract(schema=FinancialDisclosureExtraction) → extraction
     dict + extraction_metadata (per-field grounding refs to chunk ids).
  4. Translates LandingAI's extraction_metadata into the
     fd_ontology_mapper.ProvenanceCtx shape (field_path → list[Provenance]).
  5. Hands off to fd_ontology_mapper.map_and_persist — which does entity
     resolution, assertion-type stamping, the OWNS-edge provenance gate, and
     idempotent writes.
  6. Updates fd_documents with the run's latency and entity-resolution
     confidence (the §7.5 demo health-check trip-wires read these).

The extraction call is offloaded to a thread (LandingAI SDK is sync, the
FastAPI event loop must stay live for concurrent requests). This mirrors
GPDocumentProcessor's pattern at gp_processor.py:83.
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from app.schemas.fd_ontology import FinancialDisclosureExtraction
from app.services.fd_ontology_mapper import (
    MapResult,
    Provenance,
    ProvenanceCtx,
    map_and_persist,
)

logger = logging.getLogger(__name__)


# The top-level list fields on FinancialDisclosureExtraction that the
# mapper expects ProvenanceCtx entries for. Mirrors the schema in fd_ontology.py.
_TOP_LEVEL_LIST_FIELDS: Tuple[str, ...] = (
    "orgs",
    "assets",
    "capital_funds",
    "strategic_pillars",
    "financial_facts",
    "esg_facts",
    "acquisitions",
    "ownership_facts",
    "strategic_narratives",
    "restatements",
)


class FDDocumentProcessor:
    """End-to-end ingest of one Exxaro report into the fd_* tables."""

    def __init__(self, supabase_client: Any, ade_client: Any = None) -> None:
        self.supabase = supabase_client
        if ade_client is not None:
            # Caller-injected (typically a fake / mock for tests). Honour it.
            self.client = ade_client
        else:
            api_key = os.environ.get("VISION_AGENT_API_KEY") or os.environ.get("LANDING_AI_API_KEY")
            if not api_key:
                raise ValueError("VISION_AGENT_API_KEY or LANDING_AI_API_KEY not set")
            # Import locally so unit tests don't need the SDK installed at import time.
            from landingai_ade import LandingAIADE
            self.client = LandingAIADE(apikey=api_key)
        logger.info("FDDocumentProcessor initialised (supabase=%s, ade=%s)", bool(self.supabase), type(self.client).__name__)

    # =========================================================================
    # Public entry point
    # =========================================================================

    async def process_document(
        self,
        *,
        workspace_id: str,
        file_path: str,
        doc_id: str,
        doc_type: str,                  # 'integrated' | 'sustainability' | 'investor'
        fiscal_year: int,
        title: str,
        storage_path: str,
        sha256: str,
    ) -> Dict[str, Any]:
        """
        Process one PDF end-to-end. Idempotent on (workspace_id, doc_id).

        Returns a dict carrying the ingest summary suitable for an API response.
        """
        start = datetime.now(timezone.utc)

        # 1. Upsert fd_documents (status='pending')
        await self._upsert_fd_document(
            workspace_id=workspace_id,
            doc_id=doc_id,
            doc_type=doc_type,
            fiscal_year=fiscal_year,
            title=title,
            storage_path=storage_path,
            sha256=sha256,
            ingest_status="pending",
        )

        try:
            # 2. Parse
            await self._set_status(workspace_id, doc_id, "extracting")
            parsed_doc = await asyncio.to_thread(self._parse_document, file_path)
            chunks_by_id = self._index_chunks(parsed_doc)
            logger.info("FD parse complete: %d chunks", len(chunks_by_id))

            # 3. Extract with FD schema
            extraction_dict, extraction_metadata = await asyncio.to_thread(
                self._extract_financial_disclosure, parsed_doc
            )
            logger.info(
                "FD extract complete: %d top-level fields populated",
                sum(1 for k, v in extraction_dict.items() if v),
            )

            # 4. Translate extraction_metadata → ProvenanceCtx
            await self._set_status(workspace_id, doc_id, "mapping")
            provenance_ctx = self._build_provenance_ctx(extraction_metadata, chunks_by_id, doc_id)

            # 5. Map + persist
            await self._set_status(workspace_id, doc_id, "resolving")
            map_result: MapResult = await asyncio.to_thread(
                map_and_persist,
                self.supabase,
                workspace_id=workspace_id,
                doc_id=doc_id,
                extraction_dict=extraction_dict,
                provenance_ctx=provenance_ctx,
            )

            elapsed = (datetime.now(timezone.utc) - start).total_seconds()
            confidence = self._aggregate_resolution_confidence(map_result, extraction_dict)

            await self._upsert_fd_document(
                workspace_id=workspace_id,
                doc_id=doc_id,
                doc_type=doc_type,
                fiscal_year=fiscal_year,
                title=title,
                storage_path=storage_path,
                sha256=sha256,
                ingest_status="completed",
                extraction_latency_seconds=elapsed,
                entity_resolution_confidence=confidence,
            )

            return {
                "success": True,
                "doc_id": doc_id,
                "elapsed_seconds": elapsed,
                "entity_resolution_confidence": confidence,
                "nodes_written": dict(map_result.nodes_written),
                "edges_written": dict(map_result.edges_written),
                "quarantined": map_result.quarantined,
                "rejected": map_result.rejected,
            }

        except Exception as exc:
            logger.exception("FD ingest failed for doc_id=%s", doc_id)
            elapsed = (datetime.now(timezone.utc) - start).total_seconds()
            await self._upsert_fd_document(
                workspace_id=workspace_id,
                doc_id=doc_id,
                doc_type=doc_type,
                fiscal_year=fiscal_year,
                title=title,
                storage_path=storage_path,
                sha256=sha256,
                ingest_status="failed",
                extraction_latency_seconds=elapsed,
                entity_resolution_confidence=None,
                error_message=str(exc)[:1000],
            )
            raise

    # =========================================================================
    # LandingAI calls (sync; called via asyncio.to_thread above)
    # =========================================================================

    def _parse_document(self, file_path: str) -> Any:
        """Mirror GPDocumentProcessor._parse_document — same SDK call signature."""
        return self.client.parse(document=Path(file_path), model="dpt-2-latest")

    def _extract_financial_disclosure(self, parsed_doc: Any) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        One ADE extract call against FinancialDisclosureExtraction. Returns
        (extraction_dict, extraction_metadata). Both are plain dicts.
        """
        from landingai_ade.lib import pydantic_to_json_schema  # imported lazily for testability

        schema = pydantic_to_json_schema(FinancialDisclosureExtraction)
        markdown_bytes = io.BytesIO(parsed_doc.markdown.encode("utf-8"))
        markdown_bytes.seek(0)

        result = self.client.extract(schema=schema, markdown=markdown_bytes)

        extraction = _safe_to_dict(getattr(result, "extraction", None)) or {}
        metadata = _safe_to_dict(getattr(result, "extraction_metadata", None)) or {}
        return extraction, metadata

    # =========================================================================
    # Chunk indexing + metadata → ProvenanceCtx
    # =========================================================================

    @staticmethod
    def _index_chunks(parsed_doc: Any) -> Dict[str, Dict[str, Any]]:
        """
        Build chunk_id → {page, content, char_start, char_end} from a LandingAI
        parse response.

        Mirrors GPDocumentProcessor._process_chunks's chunk-shape handling but
        keeps only the bits we need for SourceSpan (page + text + synthetic
        char range). The grounding bounding-box is not stored on
        fd_source_spans for the MVP.

        ``char_start`` is synthesised from the chunk's position in the parsed
        doc (idx * 1,000,000 — assumes no single chunk exceeds 1 MB of text,
        which is far more than ADE emits). This gives every chunk a unique
        ``(doc_id, page, char_start)`` tuple even when several chunks land on
        the same page, so the fd_source_spans natural key deduplicates by
        chunk identity rather than collapsing distinct chunks together.
        """
        chunks: Dict[str, Dict[str, Any]] = {}
        for idx, chunk in enumerate(getattr(parsed_doc, "chunks", []) or []):
            chunk_dict = chunk.to_dict() if hasattr(chunk, "to_dict") else chunk
            chunk_id = chunk_dict.get("id") or f"chunk-{idx}"
            text = chunk_dict.get("text") or chunk_dict.get("content") or chunk_dict.get("markdown", "")
            grounding = chunk_dict.get("grounding")
            page = 0
            if isinstance(grounding, dict):
                page = grounding.get("page", 0) or 0
            elif isinstance(grounding, list) and grounding:
                first = grounding[0]
                if isinstance(first, dict):
                    page = first.get("page", 0) or 0
            char_start = idx * 1_000_000
            char_end = char_start + len(text)
            chunks[chunk_id] = {
                "page": page,
                "content": text,
                "char_start": char_start,
                "char_end": char_end,
            }
        return chunks

    @staticmethod
    def _build_provenance_ctx(
        extraction_metadata: Dict[str, Any],
        chunks_by_id: Dict[str, Dict[str, Any]],
        doc_id: str,
    ) -> ProvenanceCtx:
        """
        Walk extraction_metadata and turn it into the per-row Provenance map
        the ontology mapper consumes.

        For each top-level list field (e.g. ``assets``), collect every chunk_id
        referenced by ANY descendant of each list element. That's the
        provenance set for that row.
        """
        ctx: ProvenanceCtx = {}
        if not isinstance(extraction_metadata, dict):
            return ctx

        for top_key in _TOP_LEVEL_LIST_FIELDS:
            items = extraction_metadata.get(top_key)
            if not isinstance(items, list):
                continue
            for i, item_meta in enumerate(items):
                field_path = f"{top_key}[{i}]"
                chunk_ids = _collect_chunk_refs(item_meta)
                # Deduplicate while preserving order — first-seen wins so the
                # span list reads left-to-right by chunk discovery.
                seen: Set[str] = set()
                provs: List[Provenance] = []
                for cid in chunk_ids:
                    if not isinstance(cid, str) or cid in seen:
                        continue
                    seen.add(cid)
                    chunk = chunks_by_id.get(cid)
                    if not chunk:
                        continue
                    quote = chunk.get("content") or ""
                    page = int(chunk.get("page") or 0)
                    provs.append(
                        Provenance(
                            doc_id=doc_id,
                            page=page,
                            char_start=int(chunk.get("char_start") or 0),
                            char_end=int(chunk.get("char_end") or len(quote)),
                            quote=quote,
                        )
                    )
                ctx[field_path] = provs
        return ctx

    # =========================================================================
    # Database helpers
    # =========================================================================

    async def _upsert_fd_document(
        self,
        *,
        workspace_id: str,
        doc_id: str,
        doc_type: str,
        fiscal_year: int,
        title: str,
        storage_path: str,
        sha256: str,
        ingest_status: str,
        extraction_latency_seconds: Optional[float] = None,
        entity_resolution_confidence: Optional[float] = None,
        error_message: Optional[str] = None,
    ) -> None:
        row = {
            "workspace_id": workspace_id,
            "doc_id": doc_id,
            "doc_type": doc_type,
            "fiscal_year": fiscal_year,
            "title": title,
            "storage_path": storage_path,
            "sha256": sha256,
            "ingest_status": ingest_status,
        }
        if extraction_latency_seconds is not None:
            row["extraction_latency_seconds"] = extraction_latency_seconds
        if entity_resolution_confidence is not None:
            row["entity_resolution_confidence"] = entity_resolution_confidence
        if error_message is not None:
            row["error_message"] = error_message

        # supabase-py is sync; wrap so we don't block the event loop.
        await asyncio.to_thread(
            lambda: self.supabase.table("fd_documents").upsert(
                row, on_conflict="workspace_id,doc_id"
            ).execute()
        )

    async def _set_status(self, workspace_id: str, doc_id: str, ingest_status: str) -> None:
        await asyncio.to_thread(
            lambda: self.supabase.table("fd_documents")
            .update({"ingest_status": ingest_status})
            .eq("workspace_id", workspace_id)
            .eq("doc_id", doc_id)
            .execute()
        )

    # =========================================================================
    # Aggregates
    # =========================================================================

    @staticmethod
    def _aggregate_resolution_confidence(
        map_result: MapResult,
        extraction_dict: Dict[str, Any],
    ) -> Optional[float]:
        """
        Aggregate "entity-resolution confidence" for the §7.5 health-check
        trip-wire. Heuristic: fraction of extracted entity rows that landed in
        a node table (i.e. resolved confidently) vs. were quarantined or
        rejected. Returns None if no extractable rows were present.
        """
        rejected = len(map_result.rejected)
        quarantined = map_result.quarantined
        # Count entity-shape rows from the extraction (those that could in principle resolve)
        total = sum(
            len(extraction_dict.get(k) or [])
            for k in _TOP_LEVEL_LIST_FIELDS
        )
        if total == 0:
            return None
        good = max(0, total - rejected - quarantined)
        return round(good / total, 3)


# =============================================================================
# Module-level helpers
# =============================================================================


def _safe_to_dict(obj: Any) -> Optional[Dict[str, Any]]:
    """Best-effort coercion of a Pydantic / SDK object → dict. Mirrors gp_processor's safe_model_dump."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj
    for attr in ("to_dict", "model_dump", "dict"):
        fn = getattr(obj, attr, None)
        if callable(fn):
            try:
                return fn()
            except Exception:
                pass
    try:
        return dict(obj)
    except Exception:
        return None


def _collect_chunk_refs(node: Any) -> List[str]:
    """
    Walk a LandingAI extraction_metadata sub-tree and gather every chunk-id
    referenced by any leaf. A leaf has the shape ``{"value": ..., "references": [...]}``.
    """
    refs: List[str] = []
    if isinstance(node, dict):
        if "references" in node and isinstance(node["references"], list):
            for r in node["references"]:
                if isinstance(r, str):
                    refs.append(r)
                elif isinstance(r, dict):
                    # Tolerate {"chunk_id": "..."} or {"id": "..."} shapes too.
                    cid = r.get("chunk_id") or r.get("id")
                    if isinstance(cid, str):
                        refs.append(cid)
        # Recurse into the rest of the dict.
        for k, v in node.items():
            if k == "references":
                continue
            refs.extend(_collect_chunk_refs(v))
    elif isinstance(node, list):
        for v in node:
            refs.extend(_collect_chunk_refs(v))
    return refs
