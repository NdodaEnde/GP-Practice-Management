"""
PR G (option B) — immunisation_overdue materialisation, RUN_INTEGRATION.

Skipped unless RUN_INTEGRATION. Proves (the user's explicit requirement)
that the derived kind materialises the REAL overdue row(s) by read-back
on the live corpus (probed: 1 overdue / 31 in demo-gp-workspace-001),
is double-run row-stable (idempotent), tenant-scoped, and that the
teardown is asserted non-vacuous (not assumed).

CANNOT pass until the user applies migration 029 — its own per-migration
call (the assistant-auto-applies-migrations rule is REJECTED-tombstoned;
028 was the one-time exception, not precedent). If the RPC is absent the
test SKIPS with a clear "migration 029 not applied" message rather than
a cryptic failure — the honest state, surfaced.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_INTEGRATION"),
    reason="RUN_INTEGRATION not set (reads/writes the live DB)",
)

WS = "demo-gp-workspace-001"
KIND = "immunisation_overdue"


def _supabase():
    from supabase import create_client

    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ.get("SUPABASE_SERVICE_KEY") or os.environ["SUPABASE_KEY"],
    )


def _pg():
    import psycopg2

    c = psycopg2.connect(os.environ["DATABASE_URL"])
    c.autocommit = True
    return c


def _count(cur, as_of):
    cur.execute(
        "SELECT count(*) FROM briefing_items "
        "WHERE workspace_id=%s AND kind=%s AND as_of_date=%s",
        (WS, KIND, as_of),
    )
    return cur.fetchone()[0]


def _count_all(cur, as_of):
    """ALL kinds for (WS, as_of). materialise_standing_queries runs EVERY
    registered kind (morning_briefing AND immunisation_overdue), so the
    test must clean — and assert back to — the FULL partition it wrote,
    not just its own slice (the inherited PR-F teardown-residue lesson:
    a test writing to a shared live table cleans everything it created)."""
    cur.execute(
        "SELECT count(*) FROM briefing_items "
        "WHERE workspace_id=%s AND as_of_date=%s",
        (WS, as_of),
    )
    return cur.fetchone()[0]


def test_immunisation_overdue_materialises_the_real_overdue_row():
    import ontology.query.registered  # noqa: F401
    from ontology.query.standing import materialise_standing_queries

    sb = _supabase()
    as_of = datetime.now(timezone.utc).date()
    conn = _pg()
    cur = conn.cursor()
    baseline = _count(cur, as_of)               # the immunisation_overdue slice
    baseline_all = _count_all(cur, as_of)       # FULL partition (all kinds)

    try:
        stats = materialise_standing_queries(
            sb, as_of_date=as_of, only_workspace=WS
        )
        key = f"{WS}:{KIND}"
        res = (stats.get("results") or {}).get(key)
        print(f"\nACTUALS — materialise {key}: {res}")

        # migration 029 not applied → the chokepoint RPC is absent → the
        # materialiser's per-(ws,kind) error isolation reports an error.
        if isinstance(res, dict) and res.get("error"):
            err = res["error"].lower()
            if "query_immunisations_overdue" in err or "function" in err \
               or "does not exist" in err or "schema cache" in err:
                pytest.skip(
                    "migration 029 not applied (RPC query_immunisations_"
                    "overdue absent) — the user's per-migration call. "
                    f"materialiser error: {res['error'][:160]}"
                )
            pytest.fail(f"unexpected materialiser error: {res['error']}")

        # read-back the REAL row(s). Live corpus probed = exactly 1
        # overdue immunisation in demo-gp (next_dose_due < today,
        # series_complete false).
        cur.execute(
            "SELECT row_payload->>'vaccine_name', source_status "
            "FROM briefing_items "
            "WHERE workspace_id=%s AND kind=%s AND as_of_date=%s",
            (WS, KIND, as_of),
        )
        rows = cur.fetchall()
        print(f"ACTUALS — briefing_items[{WS}:{KIND}] rows: {rows}")
        assert res["rows"] == 1, f"expected the 1 real overdue row, got {res}"
        assert len(rows) == 1
        # immunisations are EHR-direct (no source_document_id) ⇒ honest
        # NO_SOURCE, never an error.
        assert rows[0][1] == "no_source", (
            f"expected honest no_source provenance, got {rows[0][1]!r}"
        )

        # double-run row-stable (idempotent wipe-and-reinsert).
        materialise_standing_queries(sb, as_of_date=as_of, only_workspace=WS)
        assert _count(cur, as_of) == 1, "double-run not row-stable"
    finally:
        # teardown: materialise_standing_queries wrote EVERY registered
        # kind for (WS, as_of) — morning_briefing AND immunisation_overdue.
        # Clean the FULL partition the run created and ASSERT back to the
        # full baseline, not just this test's slice (the inherited PR-F
        # lesson: a test writing to a shared live table cleans everything
        # it created; teardown asserted non-vacuous, not assumed).
        with conn.cursor() as tc:
            tc.execute(
                "DELETE FROM briefing_items "
                "WHERE workspace_id=%s AND as_of_date=%s",
                (WS, as_of),
            )
        post_kind = _count(cur, as_of)
        post_all = _count_all(cur, as_of)
        print(f"CLEANUP — briefing_items[{WS}, {as_of}]: kind={post_kind} "
              f"all={post_all} (baselines: kind={baseline} all={baseline_all})")
        conn.close()
        assert post_kind == baseline, "immunisation_overdue slice not restored"
        assert post_all == baseline_all, (
            "FULL partition not restored to baseline — test left residue "
            "(the PR-F teardown-residue failure)"
        )
