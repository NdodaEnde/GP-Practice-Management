#!/usr/bin/env python3
"""
apply_migration_014.py

Applies migration 014 (action_audit_log + advisory-lock RPCs) to the
remote Supabase Postgres.

USAGE — two paths

  Path A (RECOMMENDED): paste the migration SQL into the Supabase
  Dashboard SQL Editor. This is how migrations 005/010/011/012 were
  applied historically in this repo. Open:

      https://supabase.com/dashboard/project/<your-project>/sql/new

  Paste the contents of backend/migrations/014_action_audit_log.sql and
  click Run. The whole file runs in a single BEGIN/COMMIT transaction.

  Path B (this script): connect via psycopg directly. Requires:

      pip install "psycopg[binary]"
      export DATABASE_URL="postgresql://postgres:<pw>@db.<ref>.supabase.co:5432/postgres"
      python apply_migration_014.py

  The DATABASE_URL password is at:
      Supabase Dashboard → Project Settings → Database → Connection string

If neither path is available, the migration must wait until the developer
applies it manually. The ActionExecutor's unit tests pass without it; the
integration + slow_integration tests skip until the migration is live.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


MIGRATION_FILE = (
    Path(__file__).parent / "migrations" / "014_action_audit_log.sql"
)


def main() -> int:
    if not MIGRATION_FILE.exists():
        print(f"ERROR: {MIGRATION_FILE} not found", file=sys.stderr)
        return 1

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print(__doc__)
        print()
        print("DATABASE_URL not set; cannot apply automatically.")
        print(f"Paste the contents of {MIGRATION_FILE} into the Supabase ")
        print("Dashboard SQL Editor manually.")
        return 1

    try:
        import psycopg  # type: ignore
    except ImportError:
        print(
            "psycopg not installed in this environment. Install with:\n"
            "    pip install 'psycopg[binary]'\n"
            "or apply the migration manually via the Supabase Dashboard."
        )
        return 1

    sql = MIGRATION_FILE.read_text()
    print(f"Applying {MIGRATION_FILE.name} ({len(sql)} bytes) via {database_url[:30]}…")

    with psycopg.connect(database_url, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()

    print("✓ migration applied successfully.")
    print()
    print("Verification queries:")
    print("    SELECT tablename FROM pg_tables WHERE tablename = 'action_audit_log';")
    print("    SELECT proname FROM pg_proc WHERE proname LIKE 'action_%advisory%';")
    print()
    print("Now you can:")
    print("    cd backend && RUN_INTEGRATION=1 pytest tests/ -m integration -v")
    print("    cd backend && RUN_INTEGRATION=1 pytest tests/test_advisory_lock_semantics.py -m slow_integration -v -s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
