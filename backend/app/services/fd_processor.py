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
import tempfile
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


# LandingAI ADE's parse() rejects PDFs over 100 pages. We split larger PDFs
# into independent passes; each pass parses + extracts + maps separately,
# with page offsets applied to grounding so source spans point at the
# ORIGINAL PDF's page numbers (the user-facing citation must be the real
# page, not a within-chunk index). Per-chunk node/edge writes deduplicate
# via the idempotent ON CONFLICT keys in the mapper.
ADE_MAX_PAGES_PER_PARSE = 100


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
            # 2. Split if necessary, then parse+extract+map each chunk.
            await self._set_status(workspace_id, doc_id, "extracting")
            chunk_paths = await asyncio.to_thread(self._split_if_needed, file_path)
            logger.info("FD ingest: %d chunk(s) to process", len(chunk_paths))

            accumulated = MapResult()
            global_chunk_offset = 0  # for synthetic char_start uniqueness across chunks

            for chunk_idx, (chunk_path, page_offset) in enumerate(chunk_paths):
                logger.info("FD chunk %d/%d: parsing %s (page_offset=%d)",
                            chunk_idx + 1, len(chunk_paths), chunk_path, page_offset)
                parsed_doc = await asyncio.to_thread(self._parse_document, chunk_path)
                chunks_by_id = self._index_chunks(parsed_doc, page_offset=page_offset,
                                                 char_start_offset=global_chunk_offset)
                global_chunk_offset += len(chunks_by_id) * 1_000_000

                # Extract per-chunk — smaller context tends to yield better extractions.
                extraction_dict, extraction_metadata = await asyncio.to_thread(
                    self._extract_financial_disclosure, parsed_doc
                )
                logger.info("FD chunk %d/%d: extract produced %d populated top-level fields",
                            chunk_idx + 1, len(chunk_paths),
                            sum(1 for k, v in extraction_dict.items() if v))

                await self._set_status(workspace_id, doc_id, "mapping")
                provenance_ctx = self._build_provenance_ctx(extraction_metadata, chunks_by_id, doc_id)

                await self._set_status(workspace_id, doc_id, "resolving")
                chunk_result: MapResult = await asyncio.to_thread(
                    map_and_persist,
                    self.supabase,
                    workspace_id=workspace_id,
                    doc_id=doc_id,
                    extraction_dict=extraction_dict,
                    provenance_ctx=provenance_ctx,
                )
                self._merge_map_results(accumulated, chunk_result)

            map_result = accumulated
            elapsed = (datetime.now(timezone.utc) - start).total_seconds()
            confidence = self._aggregate_resolution_confidence(map_result, {})  # confidence over the aggregate

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
    #
    # Each call is wrapped in a sha256-keyed disk cache under
    # backend/.cache/ade/. A cache hit costs zero ADE credits and short-
    # circuits retries during development. The cache is per-input-bytes:
    # editing the PDF (or the extraction schema) bypasses the cache cleanly.
    # =========================================================================

    _CACHE_ROOT_ENV = "FD_ADE_CACHE_DIR"

    @classmethod
    def _cache_root(cls) -> Path:
        root = Path(os.environ.get(cls._CACHE_ROOT_ENV) or
                    Path(__file__).resolve().parents[2] / ".cache" / "ade")
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _parse_document(self, file_path: str) -> Any:
        """
        Parse the PDF via LandingAI ADE, with a sha256-keyed disk cache.
        Hits cost zero credits; misses make one real API call and write the
        result.
        """
        import hashlib, json
        pdf_bytes = Path(file_path).read_bytes()
        sha = hashlib.sha256(pdf_bytes).hexdigest()
        cache_file = self._cache_root() / f"{sha}.parse.json"
        if cache_file.exists():
            logger.info("ADE parse: cache HIT %s", cache_file.name)
            return _ParsedDocFromCache.from_dict(json.loads(cache_file.read_text()))

        logger.info("ADE parse: cache MISS, calling LandingAI on %s", Path(file_path).name)
        parsed = self.client.parse(document=Path(file_path), model="dpt-2-latest")
        # Serialize. We keep only the fields the downstream code uses:
        # parsed_doc.markdown + parsed_doc.chunks (each with id, text, grounding).
        serialised = {
            "markdown": getattr(parsed, "markdown", "") or "",
            "chunks": [
                (c.to_dict() if hasattr(c, "to_dict") else dict(c))
                for c in (getattr(parsed, "chunks", None) or [])
            ],
        }
        cache_file.write_text(json.dumps(serialised))
        return parsed

    def _extract_financial_disclosure(self, parsed_doc: Any) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        One ADE extract call against FinancialDisclosureExtraction. Returns
        (extraction_dict, extraction_metadata). Both are plain dicts.

        Cached by sha256(markdown_bytes ⊕ schema_fingerprint). Schema
        changes invalidate the cache automatically.
        """
        import hashlib, json
        from landingai_ade.lib import pydantic_to_json_schema  # lazy for testability

        schema = pydantic_to_json_schema(FinancialDisclosureExtraction)
        md = (parsed_doc.markdown or "").encode("utf-8")
        schema_bytes = (schema if isinstance(schema, (bytes, bytearray))
                        else (schema if isinstance(schema, str) else json.dumps(schema, sort_keys=True))).encode("utf-8") \
            if not isinstance(schema, (bytes, bytearray)) else schema
        key = hashlib.sha256(md + b"||" + schema_bytes).hexdigest()
        cache_file = self._cache_root() / f"{key}.extract.json"
        if cache_file.exists():
            logger.info("ADE extract: cache HIT %s", cache_file.name)
            blob = json.loads(cache_file.read_text())
            return blob.get("extraction") or {}, blob.get("metadata") or {}

        logger.info("ADE extract: cache MISS, calling LandingAI (md len=%d)", len(md))
        markdown_bytes = io.BytesIO(md)
        markdown_bytes.seek(0)
        result = self.client.extract(schema=schema, markdown=markdown_bytes)
        extraction = _safe_to_dict(getattr(result, "extraction", None)) or {}
        metadata = _safe_to_dict(getattr(result, "extraction_metadata", None)) or {}
        cache_file.write_text(json.dumps({"extraction": extraction, "metadata": metadata}))
        return extraction, metadata

    # =========================================================================
    # Chunk indexing + metadata → ProvenanceCtx
    # =========================================================================

    @staticmethod
    def _index_chunks(
        parsed_doc: Any,
        *,
        page_offset: int = 0,
        char_start_offset: int = 0,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Build chunk_id → {page, content, char_start, char_end} from a LandingAI
        parse response.

        Mirrors GPDocumentProcessor._process_chunks's chunk-shape handling but
        keeps only the bits we need for SourceSpan (page + text + synthetic
        char range). The grounding bounding-box is not stored on
        fd_source_spans for the MVP.

        ``page_offset`` is added to each chunk's grounding page — used when
        the parsed_doc is one PDF chunk of a multi-chunk split, so the
        final SourceSpan.page reflects the ORIGINAL PDF page number, not
        the within-chunk index.

        ``char_start_offset`` shifts the synthetic char_start so it stays
        unique across chunks of a split. Within one parse, char_start =
        (idx * 1_000_000) + char_start_offset.
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
            char_start = (idx * 1_000_000) + char_start_offset
            char_end = char_start + len(text)
            chunks[chunk_id] = {
                "page": page + page_offset,
                "content": text,
                "char_start": char_start,
                "char_end": char_end,
            }
        return chunks

    # =========================================================================
    # PDF chunking (LandingAI ADE 100-page limit)
    # =========================================================================

    @staticmethod
    def _split_if_needed(file_path: str) -> List[Tuple[str, int]]:
        """
        Return ``[(chunk_path, page_offset), …]``. For PDFs ≤ ADE_MAX_PAGES_PER_PARSE
        the list contains exactly one entry pointing at the original file with
        page_offset=0. Otherwise the PDF is split into temp files of at most
        ADE_MAX_PAGES_PER_PARSE pages each, with each entry's page_offset
        recording the 0-based page index where the chunk starts (chunk 2's
        page_offset is the count of pages in chunk 1 — usually 100).

        Tempfiles persist for the life of the process — we clean them in
        ``_cleanup_temp_chunks`` (best-effort, no-op if missing).
        """
        try:
            import pypdf  # local import: only needed when PDFs exceed the limit
        except ImportError:
            # pypdf not installed → assume the PDF is small enough. If it's not
            # the LandingAI 422 will surface immediately and the user can install.
            return [(file_path, 0)]

        reader = pypdf.PdfReader(file_path)
        total_pages = len(reader.pages)
        if total_pages <= ADE_MAX_PAGES_PER_PARSE:
            return [(file_path, 0)]

        # Build a stable temp directory keyed off the source path so re-runs
        # in the same process don't re-split unnecessarily.
        src = Path(file_path).resolve()
        tmp_root = Path(tempfile.gettempdir()) / "fd_pdf_chunks" / src.stem
        tmp_root.mkdir(parents=True, exist_ok=True)

        chunks: List[Tuple[str, int]] = []
        for start in range(0, total_pages, ADE_MAX_PAGES_PER_PARSE):
            end = min(start + ADE_MAX_PAGES_PER_PARSE, total_pages)
            chunk_path = tmp_root / f"{src.stem}_pages_{start + 1:04d}-{end:04d}.pdf"
            if not chunk_path.exists():
                writer = pypdf.PdfWriter()
                for p in range(start, end):
                    writer.add_page(reader.pages[p])
                with open(chunk_path, "wb") as fh:
                    writer.write(fh)
            chunks.append((str(chunk_path), start))
        logger.info("Split %s (%d pages) into %d ≤%dp chunks",
                    src.name, total_pages, len(chunks), ADE_MAX_PAGES_PER_PARSE)
        return chunks

    @staticmethod
    def _merge_map_results(into: MapResult, addition: MapResult) -> None:
        """Accumulate counters from `addition` into `into`. Used by chunked ingest."""
        for k, v in addition.nodes_written.items():
            into.nodes_written[k] = into.nodes_written.get(k, 0) + v
        for k, v in addition.edges_written.items():
            into.edges_written[k] = into.edges_written.get(k, 0) + v
        into.quarantined += addition.quarantined
        into.rejected.extend(addition.rejected)

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
        trip-wire. Heuristic: fraction of attempted rows that landed in a
        node table (resolved confidently) vs. were quarantined or rejected.

        Works across single-pass and chunked ingest by computing the score
        purely from MapResult counters (rather than the source
        extraction_dict, which is per-chunk in the chunked path).
        ``extraction_dict`` is accepted for backwards compatibility but
        ignored when MapResult carries enough signal.
        """
        rejected = len(map_result.rejected)
        quarantined = map_result.quarantined
        # Sum of all entity nodes written (excludes source_spans which are
        # provenance scaffolding, not domain entities).
        good = sum(
            v for k, v in map_result.nodes_written.items()
            if k != "fd_source_spans"
        )
        total = good + rejected + quarantined
        if total == 0:
            return None
        return round(good / total, 3)


# =============================================================================
# Module-level helpers
# =============================================================================


class _ParsedDocFromCache:
    """
    Mimics LandingAI's parse-response object after a cache hit. Exposes the
    two attributes downstream code reads: ``.markdown`` (str) and ``.chunks``
    (list of dicts; each dict has at least ``id``, ``text``/``content``, and
    ``grounding``).
    """

    def __init__(self, markdown: str, chunks: List[Dict[str, Any]]):
        self.markdown = markdown
        self.chunks = chunks

    @classmethod
    def from_dict(cls, blob: Dict[str, Any]) -> "_ParsedDocFromCache":
        return cls(markdown=blob.get("markdown") or "", chunks=blob.get("chunks") or [])


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
