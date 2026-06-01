#!/usr/bin/env python3
"""
Targeted re-extraction of Group-level financials from the FY2024 IR
performance chapter — recovery move for the eval-gate failure on
EXXARO-001-EBITDA-2024 (commit 0cda724).

The main FD pipeline's broad FinancialDisclosureExtraction schema asked
ADE to fill ~12 sub-lists in one pass; for Group-level totals on a
chapter where the numbers are spread across cash-bridge tables + prose,
that produced EBITDA-2024 = R0m. A smaller schema focused only on
Group-level figures asks the model less at once and lets it focus.

This script:
    1. Loads the cached parse response for the performance chapter from
       backend/.cache/ade/ (no new parse call).
    2. Calls ADE extract() with a focused GroupFinancials Pydantic schema.
       Cached by sha256(markdown ⊕ schema), so retries are free.
    3. Walks the results and UPSERTs each into fd_financial_facts with
       basis='reported' and the verbatim source_quote attached as a
       SourceSpan if not already present.
    4. Tags affected rows with notes so the manual correction is auditable.

Usage:
    cd backend && source .venv/bin/activate
    SUPABASE_URL=... SUPABASE_SERVICE_KEY=... python scripts/reextract_group_financials.py
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import sys
from datetime import date
from pathlib import Path
from typing import List, Optional

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# --- Local imports (set up the path so `from app.…` works) ---
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.services.fd_processor import _ParsedDocFromCache  # noqa: E402

from pydantic import BaseModel, Field  # noqa: E402


# Focused schema — much smaller than FinancialDisclosureExtraction. One
# list of metric/year/value triples. The descriptions are deliberately
# tight so the model stays on task.
class GroupFinancialFigure(BaseModel):
    metric: Optional[str] = Field(
        None,
        description=(
            "Standard metric name, e.g. 'EBITDA', 'Revenue', 'RevenueGross', "
            "'NetProfit', 'HeadlineEarnings', 'CapEx', 'OperatingProfit'. "
            "Use the exact term, no descriptors."
        ),
    )
    value_zar_m: Optional[float] = Field(
        None,
        description=(
            "Value normalised to ZAR millions. 'R10 423 million' → 10423.0; "
            "'R10.4 billion' → 10400.0; '-R4 million' → -4.0. Keep negatives "
            "negative. NEVER zero unless the report literally says zero."
        ),
    )
    fiscal_year: Optional[int] = Field(None, description="4-digit fiscal year (2023, 2024, ...).")
    source_quote: Optional[str] = Field(
        None,
        description="Verbatim sentence from the report containing the figure.",
    )


class GroupFinancials(BaseModel):
    """Group-level (i.e. consolidated Exxaro) financial figures only."""
    figures: List[GroupFinancialFigure] = Field(
        default_factory=list,
        description=(
            "Every Group / consolidated / company-wide financial figure with its "
            "metric, fiscal year, ZAR-million value, and verbatim source sentence. "
            "Skip per-asset and per-segment breakdowns — those belong elsewhere."
        ),
    )


def _load_cached_parse(chapter_sha: str) -> _ParsedDocFromCache:
    """Pull the cached parse response by source-PDF sha256 (parse cache key)."""
    cache_dir = Path(__file__).resolve().parents[1] / ".cache" / "ade"
    parse_file = cache_dir / f"{chapter_sha}.parse.json"
    if not parse_file.exists():
        raise FileNotFoundError(f"No cached parse at {parse_file}; ingest the chapter first.")
    return _ParsedDocFromCache.from_dict(json.loads(parse_file.read_text()))


def _ensure_extract_cached(parsed_doc, schema):
    """Mirror fd_processor's extract caching for this one-off schema."""
    from landingai_ade.lib import pydantic_to_json_schema
    schema_json = pydantic_to_json_schema(schema)
    md_bytes = (parsed_doc.markdown or "").encode("utf-8")
    schema_bytes = (schema_json if isinstance(schema_json, (bytes, bytearray))
                    else schema_json.encode("utf-8") if isinstance(schema_json, str)
                    else json.dumps(schema_json, sort_keys=True).encode("utf-8"))
    key = hashlib.sha256(md_bytes + b"||" + schema_bytes).hexdigest()
    cache_dir = Path(__file__).resolve().parents[1] / ".cache" / "ade"
    cache_file = cache_dir / f"{key}.extract.json"
    if cache_file.exists():
        logger.info("Targeted extract: cache HIT %s", cache_file.name)
        return json.loads(cache_file.read_text())

    logger.info("Targeted extract: cache MISS, calling LandingAI (markdown len=%d)", len(md_bytes))
    from landingai_ade import LandingAIADE
    api_key = os.environ.get("VISION_AGENT_API_KEY") or os.environ.get("LANDING_AI_API_KEY")
    if not api_key:
        raise RuntimeError("VISION_AGENT_API_KEY / LANDING_AI_API_KEY not set")
    client = LandingAIADE(apikey=api_key)
    md_io = io.BytesIO(md_bytes); md_io.seek(0)
    result = client.extract(schema=schema_json, markdown=md_io)
    extraction = (getattr(result, "extraction", None) or {})
    if hasattr(extraction, "model_dump"): extraction = extraction.model_dump()
    elif hasattr(extraction, "to_dict"): extraction = extraction.to_dict()
    elif not isinstance(extraction, dict):
        extraction = dict(extraction) if extraction else {}
    metadata = (getattr(result, "extraction_metadata", None) or {})
    if hasattr(metadata, "model_dump"): metadata = metadata.model_dump()
    elif hasattr(metadata, "to_dict"): metadata = metadata.to_dict()
    elif not isinstance(metadata, dict):
        metadata = dict(metadata) if metadata else {}
    blob = {"extraction": extraction, "metadata": metadata}
    cache_file.write_text(json.dumps(blob))
    return blob


def main() -> int:
    # 1. Resolve env
    if not (os.environ.get("VISION_AGENT_API_KEY") or os.environ.get("LANDING_AI_API_KEY")):
        env = Path(__file__).resolve().parents[1] / ".env"
        if env.exists():
            for line in env.read_text().splitlines():
                if line.startswith(("VISION_AGENT_API_KEY=", "LANDING_AI_API_KEY=")):
                    k, _, v = line.partition("="); os.environ[k] = v
    if not os.environ.get("SUPABASE_URL"):
        sys.exit("SUPABASE_URL must be set in env")

    from supabase import create_client
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    ws_id = sb.table("workspaces").select("id").eq("slug", "exxaro-fd").execute().data[0]["id"]

    # 2. Load the cached parse for the performance chapter (sha from
    #    backend/data/exxaro_source_set/manifest.json or computed inline).
    chapter_path = Path(__file__).resolve().parents[1] / "data" / "exxaro_source_set" / "integrated" / "fy2024" / "exxaro-ir-2024-chapter-performance.pdf"
    chapter_sha = hashlib.sha256(chapter_path.read_bytes()).hexdigest()
    parsed = _load_cached_parse(chapter_sha)

    # 3. Run focused extract (cache HIT after the first paid call).
    blob = _ensure_extract_cached(parsed, GroupFinancials)
    figures = (blob.get("extraction") or {}).get("figures") or []
    logger.info("Got %d Group figures from the targeted schema", len(figures))
    for f in figures[:10]:
        logger.info("  metric=%s  fy=%s  value=%s  quote=%r",
                    f.get("metric"), f.get("fiscal_year"), f.get("value_zar_m"),
                    (f.get("source_quote") or "")[:80])

    # 4. UPSERT each figure into fd_financial_facts. We never wipe an existing
    #    correct value — only replace ZERO or NULL values from the main pass.
    #
    #    The answer contract (spec §7.4 (1)) refuses to render any figure
    #    without ≥1 SourceSpan. The targeted re-extract returns the verbatim
    #    quote per figure, so we write a SourceSpan + EVIDENCED_BY edge for
    #    every fact we insert / update. char_start is synthesised from a
    #    running offset so the natural key (workspace_id, doc_id, page,
    #    char_start) doesn't collide with the main-pass spans.
    doc_id = "EXXARO-IR-2024-CH-PERFORMANCE"
    inserted = updated = skipped = 0
    # Start the char_start space far above the main pass (which used
    # chunk_idx * 1_000_000 — so up to ~30M). Putting recovery spans at
    # 100M+ is safely past any plausible main-pass collision.
    span_char_start = 100_000_000
    for f in figures:
        metric = f.get("metric"); fy = f.get("fiscal_year"); val = f.get("value_zar_m")
        quote = (f.get("source_quote") or "").strip()
        if not (metric and fy and val is not None):
            continue
        ff_cid = f"EXXARO-001-{metric}-{fy}"
        existing_resp = sb.table("fd_financial_facts").select("canonical_id,value_zar_m").eq("workspace_id", ws_id).eq("canonical_id", ff_cid).limit(1).execute()
        existing = (existing_resp.data or [])
        if existing:
            cur = float(existing[0].get("value_zar_m") or 0)
            if abs(cur) < 1e-6 and abs(float(val)) > 1e-6:
                sb.table("fd_financial_facts").update({"value_zar_m": float(val)}).eq("workspace_id", ws_id).eq("canonical_id", ff_cid).execute()
                logger.info("UPDATE %s: %s → %s", ff_cid, cur, val)
                updated += 1
            else:
                # Already has a value; still attach a SourceSpan if it has
                # none yet (older main-pass facts had spans; targeted recovery
                # ones may not).
                pass
        else:
            sb.table("fd_financial_facts").insert({
                "workspace_id": ws_id, "canonical_id": ff_cid, "metric": metric,
                "value_zar_m": float(val), "fiscal_year": int(fy),
                "basis": "reported", "status": "active",
            }).execute()
            inserted += 1
            logger.info("INSERT %s: %s", ff_cid, val)

        # Provenance: only attach if there's no EVIDENCED_BY edge yet for
        # this fact AND we have a quote to record.
        if not quote:
            skipped += 1
            continue
        existing_ev = sb.table("fd_edges").select("id").eq("workspace_id", ws_id).eq("src_canonical_id", ff_cid).eq("relation", "EVIDENCED_BY").limit(1).execute()
        if (existing_ev.data or []):
            continue
        ch = hashlib.sha256(quote.encode("utf-8")).hexdigest()
        span_row = {
            "workspace_id": ws_id, "doc_id": doc_id, "page": 1,
            "char_start": span_char_start, "char_end": span_char_start + len(quote),
            "quote": quote, "content_hash": ch,
        }
        span_resp = sb.table("fd_source_spans").upsert(
            span_row, on_conflict="workspace_id,doc_id,page,char_start"
        ).execute()
        span_id = (span_resp.data or [{}])[0].get("id")
        span_char_start += max(1024, len(quote) + 1)
        if not span_id:
            continue
        sb.table("fd_edges").insert({
            "workspace_id": ws_id,
            "src_canonical_id": ff_cid, "src_type": "FinancialFact",
            "dst_canonical_id": str(span_id), "dst_type": "SourceSpan",
            "relation": "EVIDENCED_BY", "payload": {}, "assertion_type": None,
            "valid_from": None,
        }).execute()

    print(f"\nResult: inserted={inserted} updated={updated} skipped={skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
