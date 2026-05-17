"""
OpenLoop executor round-trip — RUN_INTEGRATION (Phase 4 PR F).

Skipped unless RUN_INTEGRATION is set (writes to the live DB:
opens/advances/closes/reverses ONE fabricated loop in a real workspace,
then removes it and asserts the workspace is back to baseline). This is
the verification the DB-free suite structurally proved + proved-to-bite
but could not exercise: the real round-trip against the real executor
and the real action_audit_log.

Reports ACTUALS via psycopg2 read-back (the PR-D idiom), and the
teardown ASSERTS cleanup (the PR-D teardown-non-vacuity discipline —
the fabricated loop actually gone, the workspace's open_loops back to
the captured baseline), it does not assume it.
"""

from __future__ import annotations

import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_INTEGRATION"),
    reason="RUN_INTEGRATION not set (writes to the live DB)",
)


def _supabase():
    from supabase import create_client

    url = os.environ["SUPABASE_URL"]
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ["SUPABASE_KEY"]
    return create_client(url, key)


def _pg():
    import psycopg2

    return psycopg2.connect(os.environ["DATABASE_URL"])


def test_open_loop_executor_roundtrip_and_reversal():
    import app.actions.registered  # noqa: F401  (fires @register_action)
    from app.actions.base import ActorContext
    from app.actions.executor import execute, reverse
    from ontology.actions.open_loop_advance import OpenLoopAdvance
    from ontology.actions.open_loop_close import OpenLoopClose
    from ontology.actions.open_loop_open import OpenLoopOpen

    sb = _supabase()
    actor = ActorContext(user_id="integration-test", email="it@x.com", permissions=[])

    # --- pick a real patient in a real workspace (the Open precondition) ---
    conn = _pg()
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(
        "SELECT id, workspace_id FROM patients "
        "WHERE workspace_id IN ('demo-gp-workspace-001','demo-briefing-workspace-001') "
        "AND deleted_at IS NULL LIMIT 1"
    )
    prow = cur.fetchone()
    assert prow is not None, "no usable patient found in demo workspaces"
    patient_id, ws = str(prow[0]), prow[1]

    cur.execute("SELECT count(*) FROM open_loops WHERE workspace_id=%s", (ws,))
    baseline = cur.fetchone()[0]
    print(f"\nACTUALS — workspace={ws} patient={patient_id} "
          f"open_loops baseline={baseline}")

    loop_id = str(uuid.uuid4())
    audit_ids = []
    try:
        # 1. OPEN -------------------------------------------------------
        r_open = execute(
            OpenLoopOpen(
                loop_id=loop_id, patient_id=patient_id,
                expected_closing_event_kind="specialist letter received",
                actor_user_id=actor.user_id, practice_id=ws, workspace_id=ws,
            ),
            actor=actor, supabase=sb, practice_id=ws, workspace_id=ws,
        )
        audit_ids.append(r_open.audit_id)
        cur.execute("SELECT state FROM open_loops WHERE id=%s", (loop_id,))
        st_open = cur.fetchone()
        cur.execute("SELECT count(*) FROM action_audit_log WHERE id=%s",
                    (r_open.audit_id,))
        open_audit_n = cur.fetchone()[0]
        print(f"OPEN    -> outcome={r_open.outcome!r} "
              f"open_loops.state={st_open and st_open[0]!r} "
              f"audit_row_present={open_audit_n}")
        assert r_open.outcome == "success"
        assert st_open and st_open[0] == "open"
        assert open_audit_n == 1

        # 2. ADVANCE ----------------------------------------------------
        r_adv = execute(
            OpenLoopAdvance(loop_id=loop_id, actor_user_id=actor.user_id,
                            practice_id=ws, workspace_id=ws),
            actor=actor, supabase=sb, practice_id=ws, workspace_id=ws,
        )
        audit_ids.append(r_adv.audit_id)
        cur.execute("SELECT state FROM open_loops WHERE id=%s", (loop_id,))
        st_adv = cur.fetchone()[0]
        print(f"ADVANCE -> outcome={r_adv.outcome!r} open_loops.state={st_adv!r}")
        assert r_adv.outcome == "success"
        assert st_adv == "awaiting"

        # 3. CLOSE ------------------------------------------------------
        r_close = execute(
            OpenLoopClose(loop_id=loop_id, closed_reason="integration round-trip",
                          actor_user_id=actor.user_id, practice_id=ws,
                          workspace_id=ws),
            actor=actor, supabase=sb, practice_id=ws, workspace_id=ws,
        )
        audit_ids.append(r_close.audit_id)
        cur.execute(
            "SELECT state, closed_at, closed_reason FROM open_loops WHERE id=%s",
            (loop_id,),
        )
        st_c, c_at, c_reason = cur.fetchone()
        print(f"CLOSE   -> outcome={r_close.outcome!r} state={st_c!r} "
              f"closed_at_set={c_at is not None} closed_reason={c_reason!r}")
        assert r_close.outcome == "success"
        assert st_c == "closed" and c_at is not None
        assert c_reason == "integration round-trip"

        # 4. REVERSE the close -----------------------------------------
        r_rev = reverse(r_close.audit_id, actor=actor, supabase=sb)
        audit_ids.append(r_rev.audit_id)
        cur.execute(
            "SELECT reversed_by_audit_id FROM action_audit_log WHERE id=%s",
            (r_close.audit_id,),
        )
        reversed_by = cur.fetchone()[0]
        cur.execute(
            "SELECT reverses_audit_id, outcome FROM action_audit_log WHERE id=%s",
            (r_rev.audit_id,),
        )
        reverses, rev_outcome = cur.fetchone()
        cur.execute(
            "SELECT state, closed_at, closed_reason FROM open_loops WHERE id=%s",
            (loop_id,),
        )
        st_r, c_at_r, c_reason_r = cur.fetchone()
        print(f"REVERSE -> outcome={r_rev.outcome!r} "
              f"orig.reversed_by={str(reversed_by)!r} "
              f"rev.reverses={str(reverses)!r} rev.row_outcome={rev_outcome!r}")
        print(f"        -> before-image restored: state={st_r!r} "
              f"closed_at={c_at_r} closed_reason={c_reason_r!r}")
        assert r_rev.outcome == "reversed"
        assert str(reversed_by) == str(r_rev.audit_id)       # wiring, real rows
        assert str(reverses) == str(r_close.audit_id)        # wiring, real rows
        assert st_r == "awaiting"                            # before-image
        assert c_at_r is None and c_reason_r is None         # before-image
    finally:
        # --- teardown: REMOVE the fabricated rows, ASSERT it worked ---
        # The close row and its reversal row form an FK cycle
        # (reverses_audit_id <-> reversed_by_audit_id). Break BOTH FK
        # columns on every collected row first, THEN delete — order- and
        # cycle-independent.
        with conn.cursor() as tc:
            tc.execute("DELETE FROM open_loops WHERE id=%s", (loop_id,))
            for aid in audit_ids:
                tc.execute(
                    "UPDATE action_audit_log "
                    "SET reverses_audit_id=NULL, reversed_by_audit_id=NULL "
                    "WHERE id=%s",
                    (aid,),
                )
            for aid in audit_ids:
                tc.execute("DELETE FROM action_audit_log WHERE id=%s", (aid,))
        cur.execute("SELECT count(*) FROM open_loops WHERE id=%s", (loop_id,))
        loop_gone = cur.fetchone()[0] == 0
        cur.execute("SELECT count(*) FROM open_loops WHERE workspace_id=%s", (ws,))
        post = cur.fetchone()[0]
        print(f"CLEANUP -> fabricated loop gone={loop_gone} "
              f"open_loops[{ws}] back to baseline={post == baseline} "
              f"({post} vs {baseline})")
        conn.close()
        assert loop_gone, "teardown did NOT remove the fabricated loop"
        assert post == baseline, "workspace open_loops not restored to baseline"
