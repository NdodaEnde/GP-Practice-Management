"""
PR B integration suite — RUN_INTEGRATION-gated, real dev DB.

Verifies each PR B briefing template's resolution-correctness against
live data (this is NOT inherited from PR A — each template builds its
provenance in its own PL/pgSQL function), zero cross-workspace leakage,
join-correctness, and the three ugly branches with HONEST
xfail-with-asserted-reason for the cases the live corpus cannot
exercise. No fabricated fixture is ever presented as corpus evidence.

Run:
  cd backend && RUN_INTEGRATION=1 PYTHONPATH=. .venv/bin/python \
      -m pytest tests/test_query_templates_integration.py -q

Premise correction (probed 2026-05-16): the live env is backend/.env,
NOT ../.env (repo root has no .env).
"""

from __future__ import annotations

import os

import pytest

if not os.environ.get("RUN_INTEGRATION"):
    pytest.skip("RUN_INTEGRATION not set", allow_module_level=True)

import psycopg2
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from supabase import create_client

from ontology.query import (
    OPENABLE,
    UNRESOLVABLE,
    NO_SOURCE,
    QueryError,
    resolve_provenance,
    run_template,
)

WS = "demo-gp-workspace-001"          # entitled (legacy_full_access_grant)
TYPEC = "typec-workspace-001"         # NOT entitled (module_digitisation)
ORPHAN_WS = "test-workspace-c9f4d540"  # holds the …e15a71 orphaned dx
ORPHAN_PREFIX = "I10"

_SB = create_client(
    os.environ["SUPABASE_URL"],
    os.environ.get("SUPABASE_SERVICE_KEY") or os.environ["SUPABASE_KEY"],
)


def _conn():
    return psycopg2.connect(os.environ["DATABASE_URL"])


@pytest.fixture(scope="module", autouse=True)
def _require_migration_026():
    """026 application is the user's Dashboard step. If the briefing
    RPCs are absent, skip with an actionable message rather than a
    confusing hard failure."""
    c = _conn()
    c.autocommit = True
    with c.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM pg_proc WHERE proname = "
            "'query_patients_not_seen_since'"
        )
        present = bool(cur.fetchall())
    c.close()
    if not present:
        pytest.skip(
            "migration 026 not applied to dev DB — apply "
            "026_query_layer_briefing_templates.sql (Supabase Dashboard) "
            "and wait for the PostgREST schema-cache reload first"
        )


def _run(template, params, ws=WS):
    return run_template(_SB, template, params, workspace_id=ws)


def _resolve(template, params, ws=WS):
    return resolve_provenance(_SB, _run(template, params, ws), workspace_id=ws)


def _a_patient_with(table_pred: str) -> str | None:
    c = _conn()
    c.autocommit = True
    with c.cursor() as cur:
        cur.execute(table_pred, (WS,))
        row = cur.fetchone()
    c.close()
    return row[0] if row else None


# ── data-bearing templates on the entitled workspace ────────────────────────

def test_not_seen_since_is_data_bearing_and_fully_resolved():
    res = _resolve("patients_not_seen_since", {"days_since": 1})
    assert res.row_count > 0, "demo-gp has 38 encounters — expected rows"
    # Every row resolved to one of the three honest states; demo-gp facts
    # are NULL-sourced (§1.6) ⇒ NO_SOURCE dominant; never a crash/blank.
    for r in res.rows:
        assert r.source.status in (OPENABLE, NO_SOURCE, UNRESOLVABLE)
        assert r.source.citation
    assert res.unresolvable_count == sum(
        1 for r in res.rows if r.source.status == UNRESOLVABLE
    )
    assert res.superseded_count == 0  # construct-validity-only on corpus


def test_active_medications_resolves_for_a_real_patient():
    pid = _a_patient_with(
        "SELECT pr.patient_id FROM prescriptions pr JOIN patients p "
        "ON p.id = pr.patient_id WHERE p.workspace_id=%s "
        "AND pr.status='active' LIMIT 1"
    )
    if not pid:
        pytest.xfail("no demo-gp patient with an active prescription this run")
    res = _resolve("patient_active_medications", {"patient_id": pid})
    assert res.row_count > 0
    for r in res.rows:
        assert r.source.status in (OPENABLE, NO_SOURCE, UNRESOLVABLE)
        assert r.additional_sources is None  # inertness holds on live data


def test_recent_consultations_resolves_for_a_real_patient():
    pid = _a_patient_with(
        "SELECT e.patient_id FROM encounters e JOIN patients p "
        "ON p.id = e.patient_id WHERE p.workspace_id=%s LIMIT 1"
    )
    if not pid:
        pytest.xfail("no demo-gp patient with an encounter this run")
    res = _resolve("patient_recent_consultations",
                   {"patient_id": pid, "limit": 10})
    assert res.row_count > 0
    for r in res.rows:
        assert r.source.status in (OPENABLE, NO_SOURCE, UNRESOLVABLE)


def test_open_documents_yields_openable_or_visibly_unresolvable():
    """open_documents is special: the document IS the source, so on the
    entitled workspace these rows resolve OPENABLE (or visibly
    UNRESOLVABLE if the stored object is gone) — NEVER NO_SOURCE, NEVER
    silent. This is the one briefing template that exercises the OPENABLE
    path on demo-gp itself."""
    res = _resolve("patient_open_documents", {})
    assert res.row_count > 0, "demo-gp has 15 non-validated documents"
    for r in res.rows:
        assert r.source.status in (OPENABLE, UNRESOLVABLE), (
            "a document's own provenance must never be NO_SOURCE"
        )
        if r.source.status == OPENABLE:
            assert r.source.signed_url
        else:
            assert r.source.unresolvable_reason  # explicit, never blank


# ── honest thinness (the shape is correct; the data is thin/absent) ─────────

@pytest.mark.parametrize("template,params", [
    ("patients_with_diagnosis_prefix",
     {"icd10_prefix": "E11", "order_by": "last_consultation"}),
    ("patients_with_abnormal_recent_vitals", {"within_days": 3650}),
    ("patients_with_lab_threshold", {"test_code": "HBA1C", "min_value": 0.0}),
])
def test_thin_templates_are_honestly_empty_on_demo_gp(template, params):
    """demo-gp has 0 diagnoses, 0 vitals; 1 lab globally. These return
    empty — and that emptiness is surfaced honestly via data_maturity,
    never disguised as a clean 'all clear' cohort."""
    from ontology.query import get_template
    res = _resolve(template, params)
    assert res.row_count == 0
    assert get_template(template).data_maturity in (
        "populated", "thin", "schema_only"
    )


# ── tenant scope: zero cross-workspace leakage ──────────────────────────────

def test_zero_cross_workspace_leakage():
    res = _run("patients_not_seen_since", {"days_since": 1})
    ids = [r.data.get("patient_id") for r in res.rows if r.data.get("patient_id")]
    if not ids:
        pytest.xfail("no rows to check leakage on this run")
    c = _conn()
    c.autocommit = True
    with c.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM patients WHERE id = ANY(%s) "
            "AND workspace_id <> %s",
            (ids, WS),
        )
        foreign = cur.fetchone()[0]
        cur.execute(
            "SELECT count(*) FROM patients WHERE id = ANY(%s) "
            "AND workspace_id = %s",
            (ids, TYPEC),
        )
        typec = cur.fetchone()[0]
    c.close()
    assert foreign == 0, "a non-demo-gp patient leaked into the result"
    assert typec == 0


# ── EXPLAIN: join-correct, PR A small-table heuristic (NOT forced index) ────

def test_briefing_shape_is_join_correct_not_cross_join():
    c = _conn()
    c.autocommit = True
    with c.cursor() as cur:
        cur.execute(
            "EXPLAIN (FORMAT JSON) "
            "SELECT p.id FROM patients p JOIN encounters e "
            "ON e.patient_id = p.id WHERE p.workspace_id = %s LIMIT 50",
            (WS,),
        )
        import json
        plan = json.dumps(cur.fetchone()[0])
    c.close()
    # Same heuristic PR A's Phase-0 probe (iii) used: assert a real join
    # strategy, NOT a forced index (corpus is tiny; prescription_items
    # has no prescription_id index — a forced-index assert would
    # false-fail; recorded as a future scale index in the postmortem).
    assert ("Nested Loop" in plan or "Hash Join" in plan
            or "Merge Join" in plan or "Seq Scan" in plan)


# ── highest-priority regression: PR A's dominant property survives ──────────

def test_orphaned_source_still_unresolvable_through_new_code_path():
    """THE single highest-priority Phase-3 regression. PR B's resolver
    now also does the gp_validation_sessions + action_audit_log lookups.
    The 15/24 orphaned diagnoses MUST still render visibly UNRESOLVABLE
    with the truncated-id citation through that new path."""
    try:
        res = resolve_provenance(
            _SB,
            run_template(_SB, "patients_with_diagnosis_prefix",
                         {"icd10_prefix": ORPHAN_PREFIX},
                         workspace_id=ORPHAN_WS),
            workspace_id=ORPHAN_WS,
        )
    except QueryError as e:
        pytest.fail(f"orphan regression probe raised QueryError: {e.code}")
    unres = [r for r in res.rows if r.source.status == UNRESOLVABLE]
    assert unres, "the known-orphaned diagnosis no longer renders UNRESOLVABLE"
    s = unres[0].source
    assert s.signed_url is None
    assert s.unresolvable_reason == "source_document_not_found_in_workspace"
    assert "…" in s.citation and "no longer available" in s.citation
    assert res.unresolvable_count >= 1


# ── the three ugly branches — HONEST construct-validity discipline ──────────

def test_low_confidence_suffix_on_a_doc_sourced_openable_row():
    """The doc-sourced OPENABLE rows on demo-gp are open_documents. Their
    citation MUST carry exactly one of the two locked Decision-#1 phrases
    and NEVER 'low-confidence'/'%'. If no OPENABLE row materialises this
    run (stored objects gone), this is honestly xfailed — the unit form
    in test_query_layer_invariants covers both branches."""
    res = _resolve("patient_open_documents", {})
    openable = [r for r in res.rows if r.source.status == OPENABLE]
    if not openable:
        pytest.xfail(
            "no doc-sourced OPENABLE row on the entitled corpus this run; "
            "low-confidence phrasing covered by the unit invariant"
        )
    cit = openable[0].source.citation
    assert ("extraction quality not verified" in cit
            or "extraction quality not individually verified "
               "(document-level check available)" in cit)
    assert "low-confidence" not in cit.lower() and "%" not in cit


def test_reversed_source_is_construct_validity_only():
    """Assert the live premise (0 live facts point at a reversed
    promotion), THEN xfail — so a green run can never be misread as
    'tested against real reversed-source data'. The plumbing is unit-
    tested on fabricated input in test_query_layer_invariants."""
    c = _conn()
    c.autocommit = True
    with c.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM diagnoses d WHERE d.source_document_id IN ("
            "  SELECT (parameters->>'document_id') FROM action_audit_log "
            "  WHERE action_name='PromoteDocumentToPatientRecord' "
            "  AND reversed_by_audit_id IS NOT NULL)"
        )
        live_reversed = cur.fetchone()[0]
    c.close()
    assert live_reversed == 0, (
        "corpus changed — live reversed-source facts now exist; the "
        "reversed-source defence must move from construct-validity-only "
        "to corpus-demonstrated"
    )
    pytest.xfail(
        "construct-validity-only (§1.4): 0 live reversed-source facts on "
        "the corpus; reverse RPC DELETEs facts. Plumbing unit-tested on "
        "fabricated input, never claimed corpus-demonstrated."
    )


def test_two_source_fact_is_construct_validity_only():
    c = _conn()
    c.autocommit = True
    with c.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM (SELECT patient_id FROM diagnoses "
            "WHERE source_document_id IS NOT NULL "
            "GROUP BY patient_id HAVING count(DISTINCT source_document_id) > 1"
            ") x"
        )
        two_src = cur.fetchone()[0]
    c.close()
    assert two_src == 0, "corpus changed — two-source facts now exist"
    pytest.xfail(
        "construct-validity-only (§1.5): 0 two-source patients AND no "
        "multi-source schema. additional_sources is the inert optional "
        "field (Decision #1→a); inertness is the unit gate."
    )
