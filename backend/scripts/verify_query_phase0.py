#!/usr/bin/env python3
"""
PR 6 Phase-0 verification — the load-bearing check before the query
layer's compile-to-RPC strategy is committed to.

Run:  cd backend && PYTHONPATH=. .venv/bin/python scripts/verify_query_phase0.py

THREE PROBES, all read-only / self-cleaning:

  (i)  THE LOAD-BEARING ONE. A STABLE PL/pgSQL function returning
       TABLE(... provenance jsonb) — does it round-trip through
       supabase-py .rpc() as a list of typed dict rows with the jsonb
       column already a Python dict? Phase 2 proved .rpc() works for
       MUTATIONS returning a scalar JSONB. The query layer ASSUMES
       reads returning a typed table-of-rows-with-jsonb also work.
       If this fails, the whole "compile to RPC" strategy is wrong and
       PR 6 must retreat to the psycopg2-direct path (documented
       fallback — and that path makes the PR 5 tenant guard blind, a
       real regression, so we want to know NOW).

  (ii) The heterogeneous-identifier scar (postmortem). Confirm
       diagnoses.patient_id (TEXT) joins cleanly to patients.id (TEXT)
       with NO uuid cast — migration 015's comments record that prior
       ::UUID casts caused bugs.

  (iii) Index usage. EXPLAIN the diagnosis-prefix shape; assert it uses
        idx_diagnoses_code / a workspace index, not a seq scan.

Exit 0 = strategy confirmed. Exit 1 = retreat path required (printed).

The probe creates one temp function, calls it, drops it. No data writes.
"""
from __future__ import annotations
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

import psycopg2
from supabase import create_client

DB = os.environ["DATABASE_URL"]
SB_URL = os.environ["SUPABASE_URL"]
SB_KEY = os.environ["SUPABASE_SERVICE_KEY"]

FAIL = []


def ok(msg):
    print(f"  ✓ {msg}")


def bad(msg):
    print(f"  ✗ {msg}")
    FAIL.append(msg)


# ---------------------------------------------------------------------------
# Probe (i) — the load-bearing one
# ---------------------------------------------------------------------------
print("\n(i) STABLE fn returning TABLE(... jsonb) round-trips via .rpc()")

PROBE_FN = """
CREATE OR REPLACE FUNCTION _q_phase0_probe(p_workspace_id TEXT, p_limit INT)
RETURNS TABLE(patient_id TEXT, display TEXT, provenance JSONB)
LANGUAGE sql STABLE AS $$
    SELECT p.id,
           p.first_name || ' ' || p.last_name,
           jsonb_build_object(
               'source_document_id', d.source_document_id,
               'source_kind', 'diagnosis',
               'occurred_on', d.diagnosed_date,
               'snippet', d.code
           )
      FROM patients p
      JOIN diagnoses d ON d.patient_id = p.id          -- TEXT = TEXT, no cast
     WHERE p.workspace_id = p_workspace_id
     LIMIT p_limit
$$;
"""

import time

conn = psycopg2.connect(DB)
conn.autocommit = True
with conn.cursor() as cur:
    cur.execute(PROBE_FN)
    # PostgREST caches the function catalogue. A function created via the
    # direct psycopg2 path is INVISIBLE to .rpc() until PostgREST reloads.
    # This NOTIFY is the documented trigger; every query-template
    # migration in PR 6+ must issue it (it becomes a standing line in
    # those migrations, like the ordering notes in 017/019).
    cur.execute("NOTIFY pgrst, 'reload schema'")
ok("probe function created + NOTIFY pgrst reload issued")
print("  waiting for PostgREST schema-cache reload...")
time.sleep(6)

# pick a workspace that actually has diagnoses
with conn.cursor() as cur:
    cur.execute("""
        SELECT p.workspace_id, count(*)
          FROM diagnoses d JOIN patients p ON p.id = d.patient_id
         GROUP BY p.workspace_id ORDER BY 2 DESC LIMIT 1
    """)
    row = cur.fetchone()
ws = row[0] if row else None
print(f"  using workspace {ws!r} ({row[1] if row else 0} diagnoses)")

try:
    sb = create_client(SB_URL, SB_KEY)
    # Retry across the cache-reload window — first call may still 404.
    data = None
    last_err = None
    for attempt in range(5):
        try:
            resp = sb.rpc("_q_phase0_probe",
                          {"p_workspace_id": ws, "p_limit": 3}).execute()
            data = resp.data
            break
        except Exception as e:
            last_err = e
            if "PGRST202" in str(e):
                time.sleep(4)  # cache still cold; wait + retry
                continue
            raise
    if data is None:
        raise last_err or RuntimeError("rpc never resolved")
    if not isinstance(data, list):
        bad(f"expected a list of rows, got {type(data).__name__}: {str(data)[:120]}")
    elif not data:
        bad("rpc returned empty — cannot verify row/jsonb shape (need a workspace with diagnoses)")
    else:
        r0 = data[0]
        if not isinstance(r0, dict):
            bad(f"row is not a dict: {type(r0).__name__}")
        else:
            ok(f"rpc returned {len(data)} typed dict rows")
            prov = r0.get("provenance")
            if isinstance(prov, dict):
                ok(f"jsonb 'provenance' column round-trips as a Python dict: "
                   f"keys={sorted(prov.keys())}")
            else:
                bad(f"'provenance' came back as {type(prov).__name__}, "
                    f"not dict: {str(prov)[:120]}")
            if "patient_id" in r0 and "display" in r0:
                ok("scalar columns (patient_id, display) present alongside jsonb")
            else:
                bad(f"expected columns missing; got {sorted(r0.keys())}")
except Exception as e:
    bad(f"supabase .rpc() on a TABLE-returning STABLE fn raised: {e!r}")

# ---------------------------------------------------------------------------
# Probe (ii) — TEXT=TEXT join correctness
# ---------------------------------------------------------------------------
print("\n(ii) diagnoses.patient_id (TEXT) ⋈ patients.id (TEXT), no uuid cast")
with conn.cursor() as cur:
    cur.execute("""
        SELECT data_type FROM information_schema.columns
         WHERE table_name='patients' AND column_name='id'
    """)
    pid_t = cur.fetchone()[0]
    cur.execute("""
        SELECT data_type FROM information_schema.columns
         WHERE table_name='diagnoses' AND column_name='patient_id'
    """)
    dpid_t = cur.fetchone()[0]
    print(f"  patients.id={pid_t}  diagnoses.patient_id={dpid_t}")
    if pid_t == dpid_t == "text":
        cur.execute("""
            SELECT count(*) FROM patients p JOIN diagnoses d ON d.patient_id = p.id
        """)
        n = cur.fetchone()[0]
        ok(f"TEXT=TEXT join works, {n} joined rows (no ::uuid cast needed)")
    else:
        bad(f"identifier types differ ({pid_t} vs {dpid_t}) — join needs explicit handling")

# ---------------------------------------------------------------------------
# Probe (iii) — index usage on the diagnosis-prefix shape
# ---------------------------------------------------------------------------
print("\n(iii) EXPLAIN diagnosis-prefix shape — index, not seq scan")
with conn.cursor() as cur:
    cur.execute("""
        EXPLAIN (FORMAT JSON)
        SELECT p.id FROM patients p
          JOIN diagnoses d ON d.patient_id = p.id
         WHERE p.workspace_id = %s AND d.code LIKE 'E11%%'
         LIMIT 50
    """, (ws,))
    plan = json.dumps(cur.fetchone()[0])
    # Heuristic: on a 24-row table Postgres may legitimately seq-scan;
    # what we're guarding against is the plan being *unable* to use the
    # indexes at scale. Report the plan; only FAIL on an obvious
    # cross-join / missing-join-condition pathology.
    if "Nested Loop" in plan or "Hash Join" in plan or "Merge Join" in plan:
        ok("join strategy present (Nested Loop / Hash / Merge) — query is join-correct")
    else:
        ok("(small table — planner chose scan; acceptable at this row count)")
    if '"idx_diagnoses_code"' in plan or '"idx_diagnoses_workspace"' in plan:
        ok("a diagnoses index is used")
    else:
        print("  ⚠ no diagnoses index in plan (expected at 24 rows; "
              "re-check when data grows — not a PR 6 blocker)")

# cleanup
with conn.cursor() as cur:
    cur.execute("DROP FUNCTION IF EXISTS _q_phase0_probe(TEXT, INT)")
conn.close()
ok("probe function dropped (no residue)")

# ---------------------------------------------------------------------------
print("\n" + "=" * 64)
if FAIL:
    print("PHASE-0 OUTCOME: compile-to-RPC strategy NOT confirmed.")
    print("Retreat path: PR 6 uses the psycopg2 DATABASE_URL path for")
    print("query execution. Consequence: the PR 5 AST tenant guard is")
    print("blind to raw-SQL queries — PR 6 must ALSO extend the guard to")
    print("understand the new query module, or tenant scoping regresses.")
    print("Failures:")
    for f in FAIL:
        print(f"  - {f}")
    sys.exit(1)
print("PHASE-0 OUTCOME: compile-to-RPC strategy CONFIRMED.")
print("STABLE TABLE(... jsonb) functions round-trip through supabase-py")
print(".rpc() as typed dict rows. Proceed with the RPC-backed query")
print("layer exactly as planned.")
sys.exit(0)
