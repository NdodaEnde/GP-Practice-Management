"""
semantic_search — pgvector-backed search across digitised documents.

Lifted in spirit from groundtruth-clean-gp's vector_store.py + embeddings.py
but adapted for Supabase / pgvector (one fewer service to run; the embeddings
table lives next to the rest of the relational data).

Two responsibilities:
  1. INDEX a document's validated extractions: chunk → embed → store.
     Triggered from /digitisation/validation/{id}/approve via BackgroundTasks.
  2. SEARCH: embed the query → cosine-similarity ORDER BY → return ranked
     chunks plus their source document context.

Embedding provider: OpenAI text-embedding-3-large with dimensions=1536
(Matryoshka truncation — fits pgvector ivfflat's 2000-dim limit).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

EMBED_MODEL  = "text-embedding-3-large"
EMBED_DIMS   = 1536            # MUST match document_embeddings.embedding column
MAX_CHUNK_CHARS = 1200         # rough sweet spot for medical text
SECTION_LABELS = {
    "patient_demographics":   "demographics",
    "medical_aid":            "medical aid",
    "next_of_kin":            "next of kin",
    "clinical_history":       "clinical history",
    "vitals_history":         "vitals",
    "diagnoses":              "diagnoses",
    "medications":            "medications",
    "progress_notes":         "progress notes",
    "investigations":         "investigations",
    "referrals":              "referrals",
}


# ---------------------------------------------------------------------------
# OpenAI client (lazy)
# ---------------------------------------------------------------------------

_openai_client = None


def _client():
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY missing — cannot embed")
        _openai_client = OpenAI(api_key=api_key)
    return _openai_client


def _embed_batch(texts: List[str]) -> List[List[float]]:
    """One batched OpenAI call. Returns a list of vectors (one per input)."""
    if not texts:
        return []
    res = _client().embeddings.create(
        model=EMBED_MODEL,
        input=texts,
        dimensions=EMBED_DIMS,
    )
    return [d.embedding for d in res.data]


def _embed_one(text: str) -> List[float]:
    return _embed_batch([text])[0]


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

@dataclass
class Chunk:
    section: str    # which extraction section this came from
    text:    str    # the embeddable string
    index:   int    # position within the doc


def _flatten_section(section_name: str, section_value: Any) -> List[str]:
    """Render a JSONB section as one or more readable text snippets. The
    point isn't pretty formatting — it's giving the embedder enough context
    that semantic queries find the right chunks."""
    if section_value is None or section_value == "":
        return []
    label = SECTION_LABELS.get(section_name, section_name)

    if isinstance(section_value, dict):
        parts = []
        for k, v in section_value.items():
            if v in (None, "", [], {}):
                continue
            parts.append(f"{k.replace('_', ' ')}: {v}")
        if not parts:
            return []
        return [f"[{label}] " + " | ".join(parts)]

    if isinstance(section_value, list):
        out: List[str] = []
        for i, item in enumerate(section_value):
            if isinstance(item, dict):
                kvs = [f"{k.replace('_', ' ')}: {v}" for k, v in item.items()
                       if v not in (None, "", [], {})]
                if kvs:
                    out.append(f"[{label} #{i+1}] " + " | ".join(kvs))
            elif item:
                out.append(f"[{label} #{i+1}] {item}")
        return out

    # Scalar
    return [f"[{label}] {section_value}"]


def _chunks_from_extractions(extractions: Dict[str, Any]) -> List[Chunk]:
    chunks: List[Chunk] = []
    idx = 0
    for section_name, section_value in (extractions or {}).items():
        for text in _flatten_section(section_name, section_value):
            # Hard cap so we don't blow OpenAI per-input limits on giant
            # progress notes; rough char-based slice is fine for our scale.
            if len(text) <= MAX_CHUNK_CHARS:
                chunks.append(Chunk(section=section_name, text=text, index=idx))
                idx += 1
                continue
            for offset in range(0, len(text), MAX_CHUNK_CHARS):
                slice_ = text[offset:offset + MAX_CHUNK_CHARS]
                chunks.append(Chunk(section=section_name, text=slice_, index=idx))
                idx += 1
    return chunks


# ---------------------------------------------------------------------------
# Indexer (called from /approve background task)
# ---------------------------------------------------------------------------

def index_document(supabase, document_id: str) -> Dict[str, Any]:
    """Re-index a document. Idempotent: wipes prior embeddings keyed by
    document_id, fetches the latest validated extractions, chunks + embeds +
    inserts. Returns a small summary dict."""
    logger.info(f"[semantic-search] indexing doc {document_id[:8]}…")

    # 1. Resolve workspace + patient_id from the doc row
    doc_res = (
        supabase.table("digitised_documents")
        .select("id, workspace_id, patient_id, status")
        .eq("id", document_id)
        .limit(1)
        .execute()
    )
    if not doc_res.data:
        logger.error(f"[semantic-search] doc {document_id} not found")
        return {"error": "document not found"}
    doc = doc_res.data[0]

    # 2. Pull latest validated extractions
    sess = (
        supabase.table("gp_validation_sessions")
        .select("extractions")
        .eq("document_id", document_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    extractions = (sess.data[0].get("extractions") if sess.data else None) or {}

    chunks = _chunks_from_extractions(extractions)
    if not chunks:
        # Wipe whatever was there so the doc isn't searchable with stale data
        supabase.table("document_embeddings") \
            .delete().eq("document_id", document_id).execute()
        return {"document_id": document_id, "chunks_indexed": 0, "skipped": "no extractable text"}

    # 3. Idempotency wipe
    supabase.table("document_embeddings") \
        .delete().eq("document_id", document_id).execute()

    # 4. Embed in one batched call (OpenAI accepts up to 2048 inputs / call)
    try:
        vectors = _embed_batch([c.text for c in chunks])
    except Exception as e:
        logger.error(f"[semantic-search] embedding failed for {document_id}: {e}")
        return {"document_id": document_id, "error": f"embedding failed: {e}"}

    # 5. Insert. Supabase Python SDK handles vector lists as arrays — pgvector
    # accepts them directly when the column type is vector(N).
    rows = []
    for chunk, vec in zip(chunks, vectors):
        rows.append({
            "workspace_id": doc["workspace_id"],
            "document_id":  document_id,
            "patient_id":   doc.get("patient_id"),
            "chunk_index":  chunk.index,
            "chunk_text":   chunk.text,
            "chunk_section":chunk.section,
            "embedding":    vec,
        })
    # Insert in slices of 200 to keep individual requests small
    for i in range(0, len(rows), 200):
        supabase.table("document_embeddings").insert(rows[i:i + 200]).execute()

    logger.info(
        f"[semantic-search] indexed doc {document_id[:8]}…: {len(rows)} chunks"
    )
    return {
        "document_id": document_id,
        "chunks_indexed": len(rows),
    }


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

@dataclass
class SearchHit:
    document_id:   str
    patient_id:    Optional[str]
    chunk_section: str
    chunk_text:    str
    similarity:    float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id":   self.document_id,
            "patient_id":    self.patient_id,
            "chunk_section": self.chunk_section,
            "chunk_text":    self.chunk_text,
            "similarity":    self.similarity,
        }


def search(
    supabase,
    *,
    workspace_id: str,
    query: str,
    limit: int = 20,
    patient_id: Optional[str] = None,
) -> List[SearchHit]:
    """Embed query → cosine-similarity ORDER BY → return top N.

    Implementation note: the Supabase Python SDK doesn't expose pgvector's
    `<=>` operator directly. We call a Postgres function via .rpc() that
    encapsulates the query. The function is created by migration 011b
    (created on first call here lazily for now — see _ensure_search_fn).
    """
    if not query.strip():
        return []
    qvec = _embed_one(query)
    payload = {
        "p_workspace_id": workspace_id,
        "p_embedding":    qvec,
        "p_limit":        limit,
        "p_patient_id":   patient_id,
    }
    try:
        res = supabase.rpc("digitisation_search", payload).execute()
    except Exception as e:
        logger.error(f"[semantic-search] rpc failed: {e}")
        return []

    out: List[SearchHit] = []
    for r in res.data or []:
        out.append(SearchHit(
            document_id=r["document_id"],
            patient_id=r.get("patient_id"),
            chunk_section=r.get("chunk_section") or "",
            chunk_text=r["chunk_text"],
            similarity=float(r.get("similarity", 0.0)),
        ))
    return out
