"""
Backfill the semantic-search index for every already-approved digitised
document. The indexer normally runs on every approval, so this is a
one-time catch-up after deploying TRACEABILITY §9 — and a recovery tool
if the embeddings table ever gets wiped.

Usage:
    cd backend && .venv/bin/python scripts/backfill_semantic_index.py [--workspace WS] [--dry-run]

Behaviour:
    --workspace WS   only re-index docs in that workspace (default: all)
    --dry-run        list what would be indexed without calling OpenAI
    --skip-indexed   skip docs that already have a search_indexed_at
                     timestamp (default: re-index everything)

Cost guard:
    Prints the projected OpenAI cost (≈$0.0008 per doc) before running
    and asks for confirmation when the bill exceeds $1.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Allow `from app...` imports
HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent
sys.path.insert(0, str(BACKEND))

from supabase import create_client


COST_PER_DOC = 0.0008  # text-embedding-3-large at 1536 dims, ~6k tokens/doc


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--workspace", help="restrict to one workspace_id")
    p.add_argument("--dry-run", action="store_true",
                   help="list what would be indexed; don't call OpenAI")
    p.add_argument("--skip-indexed", action="store_true",
                   help="skip docs that already have search_indexed_at set")
    p.add_argument("--limit", type=int, default=10000,
                   help="safety cap on docs to process")
    args = p.parse_args()

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        print("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set", file=sys.stderr)
        return 2
    sb = create_client(url, key)

    # Find candidate docs — validated/approved status, optionally filtered.
    query = (
        sb.table("digitised_documents")
        .select("id, workspace_id, filename, status, search_indexed_at")
        .in_("status", ["validated", "approved"])
        .order("created_at", desc=True)
        .limit(args.limit)
    )
    if args.workspace:
        query = query.eq("workspace_id", args.workspace)
    docs = query.execute().data or []

    if args.skip_indexed:
        before = len(docs)
        docs = [d for d in docs if not d.get("search_indexed_at")]
        skipped = before - len(docs)
        if skipped:
            print(f"Skipping {skipped} doc(s) already indexed")

    if not docs:
        print("No candidate docs found.")
        return 0

    cost = len(docs) * COST_PER_DOC
    print(f"Found {len(docs)} doc(s) to index. Estimated cost: ~${cost:.2f}")
    if args.dry_run:
        for d in docs[:20]:
            print(f"  [{d['status']:10s}] {d['id'][:8]}… {d['workspace_id']:25s} {d.get('filename') or ''}")
        if len(docs) > 20:
            print(f"  … and {len(docs) - 20} more")
        return 0

    if cost > 1.0:
        try:
            confirm = input(f"This will spend ~${cost:.2f} on OpenAI embeddings. Proceed? [y/N] ")
        except EOFError:
            confirm = "n"
        if confirm.strip().lower() != "y":
            print("Aborted.")
            return 1

    # Run the indexer per-doc. We import here so dry-run doesn't pay the
    # OpenAI client init cost (and so the script can run without an
    # OPENAI_API_KEY for --dry-run).
    from app.services.semantic_search import index_document

    ok = 0
    failed = 0
    for i, d in enumerate(docs, 1):
        try:
            res = index_document(sb, d["id"])
            if res.get("error"):
                print(f"  [{i:4d}/{len(docs)}] ✗ {d['id'][:8]}…  {res['error']}")
                failed += 1
            else:
                print(f"  [{i:4d}/{len(docs)}] ✓ {d['id'][:8]}…  {res.get('chunks_indexed', 0)} chunks")
                ok += 1
        except Exception as e:
            print(f"  [{i:4d}/{len(docs)}] ✗ {d['id'][:8]}…  {type(e).__name__}: {e}")
            failed += 1

    print()
    print(f"Done. {ok} indexed, {failed} failed.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
