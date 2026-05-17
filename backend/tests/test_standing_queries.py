"""
PR D — standing-query materialisation + Phase 3 close-out tests.

BUILD-ORDER NOTE: the close-out gate (`test_postmortem_closeout_artifacts_
present`) and its non-vacuity proof are FIRST in this file deliberately.
PR D's load-bearing part is the close-out, not the standing-query code;
the gate is built and proven to bite before the materialiser exists,
the same way PR C's default-off gate was proven un-mockable before the
classifier existed.

The gate is the AUTOMATABLE NECESSARY condition (it fails the build if a
load-bearing close-out sentence is physically absent). It is NOT
sufficient: discharge proper additionally requires the human-verified
§2.4 checklist read by the named verifier at review (semantic
correctness is a bounded human judgement, deliberately not automated).
"Discharged" must never be read as "the parser passed".
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_POSTMORTEM = _REPO_ROOT / "ONTOLOGY_QUERY_LAYER_POSTMORTEM.md"


def _section(text: str, start_marker: str, end_marker: str) -> str:
    i = text.find(start_marker)
    if i == -1:
        raise AssertionError(f"close-out section missing: {start_marker!r}")
    j = text.find(end_marker, i + len(start_marker))
    return text[i: j if j != -1 else len(text)]


def _assert_closeout_artifacts(text: str) -> None:
    """The four load-bearing assertions (plan §2.4). Prose anchors are
    case-insensitive (this is a human document, not code); the stable
    COUNT and the verbatim hyphenated residual phrase are exact.
    Factored out so the non-vacuity test can prove each BITES when its
    phrase is removed. Raises AssertionError naming the missing element.
    """
    low = text.lower()

    # (i) §A: the stable count 15 anchored to the orphaned-source finding.
    sec_a = _section(text, "## §A.", "## §B.")
    if "15" not in sec_a:
        raise AssertionError("§A: the stable orphan count '15' is absent")
    sec_a_low = sec_a.lower()
    if "orphaned" not in sec_a_low or "sourced diagnoses" not in sec_a_low:
        raise AssertionError(
            "§A: '15' is not anchored to the orphaned-sourced-diagnoses "
            "finding (missing 'orphaned' / 'sourced diagnoses')"
        )

    # (ii) §C: the residual phrase, verbatim (hyphenated, exact).
    if "checkable-but-not-checked" not in low:
        raise AssertionError(
            "§C residual phrase 'checkable-but-not-checked' is absent — "
            "the permanent wrong-extraction residual is not recorded in "
            "the umbrella's exact words"
        )

    # (iii) the conversion-instrumentation note: three anchors co-occur
    #       in the named-not-built section (case-insensitive prose).
    note = _section(text, "Named-not-built", "## The shared-trigger").lower()
    for anchor in ("conversion instrumentation", "standingquery",
                   "briefing_items"):
        if anchor not in note:
            raise AssertionError(
                f"conversion-instrumentation note missing anchor "
                f"{anchor!r} — the hardest-guarded artifact is not "
                f"structurally anchored"
            )

    # (iv) the shared-trigger sentence.
    trig = _section(text, "## The shared-trigger", "## What closes").lower()
    if "one review" not in trig:
        raise AssertionError(
            "shared-trigger sentence missing 'one review' — the three "
            "deferrals are not bound to a single trigger"
        )
    if "project_phase3_tracked_deferrals" not in trig:
        raise AssertionError(
            "shared-trigger sentence does not name the memory key "
            "'project_phase3_tracked_deferrals'"
        )


def test_postmortem_closeout_artifacts_present():
    """THE §2.4 gate (necessary, automatable, build-failing). Parses the
    real Phase 3 post-mortem and asserts the load-bearing sentences are
    physically present. NOT sufficient — the human §2.4 checklist is the
    sufficiency condition."""
    assert _POSTMORTEM.is_file(), f"post-mortem missing: {_POSTMORTEM}"
    _assert_closeout_artifacts(_POSTMORTEM.read_text())


@pytest.mark.parametrize("removed", [
    "15",
    "checkable-but-not-checked",
    "conversion instrumentation",
    "one review",
])
def test_closeout_gate_is_non_vacuous(removed):
    """The discriminating check (PR C's trap-non-vacuity discipline
    applied to a presence-gate): a presence check that never fails when
    a sentence is absent is worthless. Remove each load-bearing phrase
    from a COPY of the real post-mortem and assert the gate BITES. If
    any removal does not raise, the gate is vacuous and the close-out is
    not actually guarded. Shipped (permanent CI), not a one-time check."""
    text = _POSTMORTEM.read_text()
    assert re.search(re.escape(removed), text, re.I), \
        f"precondition: {removed!r} present (case-insensitively) in the real doc"
    # Remove ALL case variants — proves the gate bites regardless of casing.
    tampered = re.sub(re.escape(removed), "", text, flags=re.I)
    with pytest.raises(AssertionError):
        _assert_closeout_artifacts(tampered)


# ===========================================================================
# The standing-query property (scoped AFTER the close-out, §3). DB-free
# recorder tests + RUN_INTEGRATION live ones.
# ===========================================================================

import os                                                       # noqa: E402
import types                                                    # noqa: E402
from datetime import date                                       # noqa: E402

import ontology.query.standing as standing                      # noqa: E402
from ontology.query.provenance import (                          # noqa: E402
    NO_SOURCE, OPENABLE, UNRESOLVABLE, ResolvedRow,
    ResolvedQueryResult, ResolvedSource,
)
from ontology.query.result import Provenance                     # noqa: E402


def _resolved(*sources) -> ResolvedQueryResult:
    rows = [
        ResolvedRow(
            data={"patient_id": f"p{i}"},
            provenance=Provenance(
                source_kind="diagnosis",
                source_document_id=(None if s.status == NO_SOURCE else "d"),
            ) if s.status != NO_SOURCE
            else Provenance(source_kind="live_entry"),
            source=s,
        )
        for i, s in enumerate(sources)
    ]
    return ResolvedQueryResult(
        template_id="patients_not_seen_since", template_version=1,
        workspace_id="ws-1", rows=rows, row_count=len(rows),
        data_maturity="populated",
        unresolvable_count=sum(1 for s in sources
                               if s.status == UNRESOLVABLE),
        superseded_count=0,
    )


def test_materialise_reaches_data_only_through_run_template_and_resolve(
        monkeypatch):
    """No new data path: the materialiser reaches facts ONLY through
    run_template→resolve_provenance (recorder), and writes ONLY via
    _rewrite_partition. Same shape as PR C's no-new-path proof."""
    seen = {"run_template": 0, "resolve": 0, "rewrite": []}

    monkeypatch.setattr(standing, "_entitled_workspaces", lambda sb: ["ws-1"])

    def fake_run(sb, tid, params, *, workspace_id):
        seen["run_template"] += 1
        return types.SimpleNamespace(template_id=tid)

    def fake_resolve(sb, result, *, workspace_id):
        seen["resolve"] += 1
        return _resolved(
            ResolvedSource(status=OPENABLE, document_id="d",
                           signed_url="u", citation="c"),
        )

    def fake_rewrite(ws, kind, as_of, tid, tv, rows):
        seen["rewrite"].append((ws, kind, str(as_of), len(rows)))

    monkeypatch.setattr(standing, "run_template", fake_run)
    monkeypatch.setattr(standing, "resolve_provenance", fake_resolve)
    monkeypatch.setattr(standing, "_rewrite_partition", fake_rewrite)

    out = standing.materialise_standing_queries(
        object(), as_of_date=date(2026, 5, 17))

    assert seen["run_template"] == 1 and seen["resolve"] == 1
    assert seen["rewrite"] == [("ws-1", "morning_briefing",
                                "2026-05-17", 1)]
    assert out["results"]["ws-1:morning_briefing"]["rows"] == 1


def test_materialiser_does_not_route_through_action_executor(monkeypatch):
    """Read-only: queries are not actions. If the materialiser ever
    touched the ActionExecutor this sentinel would fire."""
    import app.actions as actions

    monkeypatch.setattr(standing, "_entitled_workspaces", lambda sb: ["ws-1"])
    monkeypatch.setattr(standing, "run_template",
                        lambda *a, **k: types.SimpleNamespace(template_id="t"))
    monkeypatch.setattr(standing, "resolve_provenance",
                        lambda *a, **k: _resolved(
                            ResolvedSource(status=NO_SOURCE, document_id=None,
                                           signed_url=None, citation="c")))
    monkeypatch.setattr(standing, "_rewrite_partition",
                        lambda *a, **k: None)
    monkeypatch.setattr(
        actions, "execute",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("materialiser routed through ActionExecutor")))
    standing.materialise_standing_queries(object(), as_of_date=date.today())


def test_materialiser_only_iterates_entitled_workspaces(monkeypatch):
    """The trusted source: only clinical_query-entitled workspaces are
    ever passed to the chokepoint; non-entitled are excluded by
    practice_has_capability, never by caller input."""
    from app.services import entitlements

    fake_sb = types.SimpleNamespace(
        table=lambda n: types.SimpleNamespace(
            select=lambda *a: types.SimpleNamespace(
                execute=lambda: types.SimpleNamespace(
                    data=[{"id": "ws-entitled"}, {"id": "ws-NOT"}]))))
    monkeypatch.setattr(
        entitlements, "practice_has_capability",
        lambda c, ws, cap: ws == "ws-entitled" and cap == "clinical_query")

    got = standing._entitled_workspaces(fake_sb)
    assert got == ["ws-entitled"]  # ws-NOT excluded by the trusted check


def _fake_pg(captured):
    """A fake psycopg2 connection/cursor capturing executed SQL+params,
    so the per-(ws,kind) transaction + idempotency DELETE is testable
    DB-free."""
    class _Cur:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, sql, params=None):
            captured.append((" ".join(sql.split()), params))
    class _Conn:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def cursor(self): return _Cur()
        def close(self): pass
    return _Conn()


def test_double_run_is_row_stable_and_idempotency_delete_is_keyed(
        monkeypatch):
    """Structural idempotency (locked decision #6): each partition
    rewrite issues a DELETE keyed EXACTLY to (workspace_id, kind,
    as_of_date) before the INSERTs, inside one transaction; two runs
    over the same resolved rows produce byte-identical INSERT payloads
    (row-stable by construction, not hoped)."""
    monkeypatch.setattr(standing, "_entitled_workspaces", lambda sb: ["ws-1"])
    monkeypatch.setattr(standing, "run_template",
                        lambda *a, **k: types.SimpleNamespace(template_id="t"))
    monkeypatch.setattr(standing, "resolve_provenance",
                        lambda *a, **k: _resolved(
                            ResolvedSource(status=UNRESOLVABLE, document_id="d",
                                           signed_url=None, citation="gone",
                                           unresolvable_reason="r")))
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused")

    runs = []
    for _ in range(2):
        cap: list = []
        import psycopg2
        monkeypatch.setattr(psycopg2, "connect", lambda *a, **k: _fake_pg(cap))
        standing.materialise_standing_queries(
            object(), as_of_date=date(2026, 5, 17))
        runs.append(cap)

    # First statement of the partition rewrite is the keyed DELETE.
    del_sql, del_params = runs[0][0]
    assert del_sql.startswith("DELETE FROM briefing_items")
    assert del_params == ("ws-1", "morning_briefing", date(2026, 5, 17))
    # Two runs → identical captured SQL+params (row-stable).
    assert runs[0] == runs[1]


def test_027_migration_notify_decision_is_explicit():
    """027 adds a TABLE and no function; the decision to include
    NOTIFY pgrst must be EXPLICIT (present in executable SQL) and the
    header must document the reasoning. Reuses PR B's _strip_sql_comments."""
    def _strip_sql(s: str) -> str:
        s = re.sub(r"/\*.*?\*/", " ", s, flags=re.DOTALL)
        s = re.sub(r"--[^\n]*", " ", s)
        return s

    f = (_REPO_ROOT / "backend" / "migrations" /
         "027_briefing_items.sql")
    assert f.is_file(), f"migration 027 missing: {f}"
    raw = f.read_text()
    body = _strip_sql(raw).lower()
    assert "notify pgrst" in body, "027 NOTIFY decision not explicit in SQL"
    assert body.rfind("notify pgrst") < body.rfind("commit")
    # The reasoning must be documented (header, comment-stripped out of
    # `body` but present in `raw`).
    assert "consciously-decided" in raw or "consciously decided" in raw
    assert "rest" in raw.lower() and "cache" in raw.lower()


# ── RUN_INTEGRATION live ones ──────────────────────────────────────────────

_INTEG = pytest.mark.skipif(
    not os.environ.get("RUN_INTEGRATION"), reason="RUN_INTEGRATION not set")


@_INTEG
def test_orphaned_source_still_unresolvable_through_briefing_path():
    """THE highest-priority Phase-3 regression at the PR-D boundary.

    NOTE — this test was REWRITTEN after a found defect (post-mortem
    §D.1): the prior form drove only the one production kind
    (`morning_briefing` → `patients_not_seen_since`, ENCOUNTER-sourced)
    over `test-workspace-c9f4d540`, whose orphan is on a DIAGNOSIS;
    `patients_not_seen_since` returns 0 rows there, so the materialiser
    wrote nothing and the sole assertion passed green having
    demonstrated nothing — a false green in the highest-priority guard,
    caught by integration-premise-verification. The test now genuinely
    routes a diagnosis-orphaned-source row through the FULL materialiser
    path and asserts it persisted visibly-unresolvable.

    HONEST SCOPE (verbatim — read this): this asserts the resolver
    contract survives the materialisation CODE PATH; it does NOT assert
    this workspace is ever materialised in production. Orphaned data
    lives in `test-workspace-c9f4d540`, which is NOT clinical_query-
    entitled, so the production materialiser (entitled-only) NEVER
    reaches it; and the ONE production kind is encounter-sourced and
    cannot surface a diagnosis orphan even on the inner path. We
    register a TEST-LOCAL diagnosis-sourced StandingQuery, drive the
    real `materialise_standing_queries` with an explicit non-entitled
    `only_workspace` arg (bypassing the entitlement filter for the test
    only), and read the persisted `briefing_items` row back. The
    production registry stays exactly one kind (decision #2 untouched) —
    asserted, not assumed (teardown non-vacuity). No orphan injected
    anywhere; the orphan is pre-existing live corpus data.
    """
    import psycopg2
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
    from supabase import create_client

    KIND = "__test_orphan_diag__"
    WS = "test-workspace-c9f4d540"
    sb = create_client(
        os.environ["SUPABASE_URL"],
        os.environ.get("SUPABASE_SERVICE_KEY") or os.environ["SUPABASE_KEY"])

    # Register a TEST-LOCAL diagnosis-sourced standing query. This is the
    # ONLY way to route the diagnosis orphan through the materialiser:
    # the one production kind is encounter-sourced (the found defect).
    standing.register_standing(standing.StandingQuery(
        kind=KIND, template_id="patients_with_diagnosis_prefix",
        params={"icd10_prefix": "I"},
        description="TEST-LOCAL — orphan-through-materialiser regression.",
    ))

    body_exc = None
    try:
        standing.materialise_standing_queries(
            sb, as_of_date=date(2026, 5, 17), only_workspace=WS)
        # Read the PERSISTED row back — proves it transited the full
        # path run_template→resolve_provenance→_rewrite_partition→
        # briefing_items, not just that resolve_provenance worked.
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        conn.autocommit = True
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT source_status, openable, citation, "
                    "unresolvable_reason FROM briefing_items "
                    "WHERE workspace_id=%s AND kind=%s", (WS, KIND))
                rows = cur.fetchall()
        finally:
            conn.close()
        assert rows, ("the orphaned diagnosis produced NO briefing_items "
                      "row — the materialiser did not route it")
        unres = [r for r in rows if r[0] == "unresolvable"]
        assert unres, (f"orphaned-source row NOT persisted unresolvable: "
                       f"{rows!r}")
        st, openable, citation, reason = unres[0]
        assert openable is False, f"openable should be False, got {openable!r}"
        assert "e15a71" in (citation or ""), (
            f"citation missing the truncated-id anchor: {citation!r}")
        assert reason == "source_document_not_found_in_workspace", reason
    except Exception as e:  # noqa: BLE001 — capture so teardown always runs
        body_exc = e

    # ── Teardown — ALWAYS runs, and is itself verified non-vacuous ──────
    standing._STANDING.pop(KIND, None)
    try:
        c2 = psycopg2.connect(os.environ["DATABASE_URL"])
        c2.autocommit = True
        with c2.cursor() as cur:
            cur.execute("DELETE FROM briefing_items WHERE workspace_id=%s "
                        "AND kind=%s", (WS, KIND))
        c2.close()
    except Exception:  # noqa: BLE001 — best-effort row cleanup
        pass

    # Teardown NON-VACUITY (the tightening): prove the registry is
    # restored to EXACTLY the one production kind — assert it, do not
    # assume the pop worked. A future registry-mechanism refactor that
    # silently leaves the test kind registered would contaminate
    # decision #2's "exactly one kind at merge" and MUST fail here.
    assert {s.kind for s in standing.all_standing()} == {"morning_briefing"}, (
        "teardown vacuous: production registry NOT restored to exactly "
        "{'morning_briefing'} — decision #2 contaminated by the test kind")

    if body_exc is not None:
        raise body_exc


@_INTEG
def test_briefing_items_is_rls_deny_all():
    import psycopg2
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
    c = psycopg2.connect(os.environ["DATABASE_URL"])
    c.autocommit = True
    with c.cursor() as cur:
        cur.execute("SELECT relrowsecurity FROM pg_class "
                    "WHERE relname='briefing_items'")
        row = cur.fetchone()
        assert row and row[0] is True, "briefing_items RLS not enabled"
        cur.execute("SELECT count(*) FROM pg_policies "
                    "WHERE tablename='briefing_items'")
        assert cur.fetchone()[0] == 0, (
            "briefing_items has a permissive policy — not deny-all "
            "(migration-018 idiom is: enable RLS, NO policy)")
    c.close()
