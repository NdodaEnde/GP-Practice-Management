#!/usr/bin/env python3
"""
Embed every fd_source_spans.quote with OpenAI text-embedding-3-large
(dimensions=1536, matching the pgvector column).

Mirrors backend/app/services/semantic_search.py's provider + dims so the
existing platform conventions hold. Idempotent: only rows where embedding
IS NULL get re-embedded.

Usage:
    cd backend && source .venv/bin/activate
    SUPABASE_URL=... SUPABASE_SERVICE_KEY=... OPENAI_API_KEY=... \\
    python scripts/embed_fd_source_spans.py [--workspace-slug exxaro-fd] [--reembed-all]
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import List

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


EMBED_MODEL = "text-embedding-3-large"
EMBED_DIMS  = 1536
BATCH_SIZE  = 96   # OpenAI accepts up to 2048 inputs, but keeping batches small
                    # reduces partial-failure impact if a call retries.


def _load_env():
    if not os.environ.get("OPENAI_API_KEY"):
        env = Path(__file__).resolve().parents[1] / ".env"
        if env.exists():
            for line in env.read_text().splitlines():
                if line.startswith("OPENAI_API_KEY="):
                    _, _, v = line.partition("=")
                    os.environ["OPENAI_API_KEY"] = v


def _embed_batch(client, texts: List[str]) -> List[List[float]]:
    if not texts:
        return []
    res = client.embeddings.create(model=EMBED_MODEL, input=texts, dimensions=EMBED_DIMS)
    return [d.embedding for d in res.data]


def main() -> int:
    p = argparse.ArgumentParser(description="Embed fd_source_spans for grounded retrieval.")
    p.add_argument("--workspace-slug", default="exxaro-fd")
    p.add_argument("--reembed-all", action="store_true",
                   help="Re-embed spans even if they already have an embedding (default: skip).")
    args = p.parse_args()

    _load_env()
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
    if not (supabase_url and supabase_key):
        sys.exit("SUPABASE_URL + SUPABASE_SERVICE_KEY required.")
    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY required.")

    from supabase import create_client
    from openai import OpenAI

    sb = create_client(supabase_url, supabase_key)
    ws_resp = sb.table("workspaces").select("id").eq("slug", args.workspace_slug).limit(1).execute()
    if not (ws_resp.data or []):
        sys.exit(f"workspace slug={args.workspace_slug!r} not found")
    ws_id = ws_resp.data[0]["id"]

    # Pull spans needing embeddings. Page through to handle large sets.
    page_size = 500
    offset = 0
    queued: List[dict] = []
    while True:
        q = sb.table("fd_source_spans").select("id, quote, embedding").eq("workspace_id", ws_id)
        if not args.reembed_all:
            q = q.is_("embedding", "null")
        resp = q.range(offset, offset + page_size - 1).execute()
        rows = resp.data or []
        queued.extend(rows)
        if len(rows) < page_size:
            break
        offset += page_size

    if not queued:
        print("Nothing to embed — every fd_source_spans row already has an embedding.")
        return 0
    print(f"Embedding {len(queued)} fd_source_spans rows with {EMBED_MODEL}@{EMBED_DIMS}.")

    oai = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    total_written = 0
    for i in range(0, len(queued), BATCH_SIZE):
        batch = queued[i:i + BATCH_SIZE]
        texts = [(r.get("quote") or "")[:8000] for r in batch]  # cap per-call tokens
        vectors = _embed_batch(oai, texts)
        for r, v in zip(batch, vectors):
            sb.table("fd_source_spans").update({"embedding": v}).eq("id", r["id"]).execute()
            total_written += 1
        logger.info("Batch %d-%d: wrote %d embeddings", i, i + len(batch), len(batch))

    print(f"Done. Wrote {total_written} embeddings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
