"""
THE Phase-3 CI gate. No DB, fast, runs on every commit.

This file is the executable expression of the Phase-3 safety property:
**no query result a clinician can act on may ship without provenance that
is present, CI-enforced, and resolvable — or, when it cannot resolve,
visibly and explicitly unresolvable, never a silent dead link.**

It consolidates the structural invariants the prior plan deferred to a
late "ratify invariants" PR. They are pulled forward to PR A because the
window in which they are not enforced is exactly the unsafe window. Three
layers, each a defence behind the next:

  1. Registry invariants — a template that forgets provenance, forgets
     tenant scope, or lets the caller forge the workspace cannot register.
  2. Type invariants — ResolvedSource cannot represent a silent dead
     link; ResolvedQueryResult cannot represent a drifted aggregate.
     These are structural (__post_init__), so the assertions below are
     verifying a property the type already guarantees — that redundancy
     is the point.
  3. End-to-end resolver invariants — resolve_provenance over a fake
     Supabase (no DB) produces exactly the honest three states, counts
     only true failures, and the silent-dead-link guard holds through
     the real function, not just the constructor.

The orphaned-source case (62% of the live corpus) is the dominant real
failure; its unit form is `test_missing_document_is_visibly_unresolvable`
and its live form is the verify_query_phase0.py resolution probe.
"""

from __future__ import annotations

import re
import types
from pathlib import Path

import pytest

from ontology.query import (
    all_templates,
    resolve_provenance,
    ResolvedSource,
    ResolvedQueryResult,
    OPENABLE,
    UNRESOLVABLE,
    NO_SOURCE,
)
from ontology.query.result import LIVE_ENTRY, Provenance, QueryResult, QueryRow
from ontology.query.spec import PROVENANCE_COLUMN, WORKSPACE_PARAM


# ===========================================================================
# Layer 1 — registry invariants (a bad template cannot register)
# ===========================================================================

def test_every_template_declares_provenance():
    """THE structural invariant. Every registered template declares a
    provenance output column. A template that omits it fails this — and
    cannot even construct (TemplateSpec.__post_init__) — so provenance is
    structural, not a review checklist item."""
    for t in all_templates():
        assert PROVENANCE_COLUMN in t.output_columns, (
            f"template {t.id!r} does not declare a {PROVENANCE_COLUMN!r} "
            f"output column"
        )


def test_every_template_rpc_is_query_namespaced():
    for t in all_templates():
        assert t.rpc_name.startswith("query_"), (
            f"{t.id!r} rpc {t.rpc_name!r} must be query_-namespaced "
            f"(visually distinct from execute_action_*)"
        )


def test_no_template_lets_the_caller_supply_the_workspace():
    """Tenant scope is injected by the runner from the trusted auth
    context. A template that declared a caller-side parameter mapping to
    p_workspace_id would let a caller forge another practice's scope.
    No template may. This is the registry-level expression of the PR 5
    tenant-isolation guarantee."""
    for t in all_templates():
        for p in t.params:
            assert p.rpc_arg != WORKSPACE_PARAM, (
                f"template {t.id!r} param {p.name!r} maps to "
                f"{WORKSPACE_PARAM!r} — the workspace must come from the "
                f"runner, never a caller param"
            )
            assert "workspace" not in p.name.lower(), (
                f"template {t.id!r} param {p.name!r} smells like a "
                f"caller-supplied workspace; tenant scope is runner-only"
            )


# --- the entitlement ratchet (guards a WRITTEN customer promise) ----------

def _migrations_dir() -> Path:
    # tests/ -> backend/ -> backend/migrations
    return Path(__file__).resolve().parent.parent / "migrations"


def _strip_sql_comments(sql: str) -> str:
    """Remove -- line comments and /* */ block comments so the
    explanatory prose in 025's header (which legitimately mentions both
    tokens) cannot false-positive — only executable SQL is scanned."""
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    sql = re.sub(r"--[^\n]*", " ", sql)
    return sql


# A product_capabilities row pairing module_digitisation with
# clinical_query, in either column order, possibly across newlines.
_FORBIDDEN_GRANT = re.compile(
    r"\(\s*'(?:module_digitisation'\s*,\s*'clinical_query"
    r"|clinical_query'\s*,\s*'module_digitisation)'\s*\)",
    re.DOTALL,
)


def test_module_digitisation_never_entails_clinical_query():
    """REGRESSION RATCHET — same shape as the PR 5 tenant-guard ratchet,
    but it guards a *written customer promise*, which makes it more
    important than a technical invariant, not less.

    The Type C leave-behind commits in writing that a digitisation-only
    practice gets digitisation and nothing else and is deliberately not
    pushed onto the platform path. Granting the highest-blast-radius
    cross-cutting clinical-query surface to `module_digitisation` would
    make that commitment a lie. The pressure to add a one-line grant
    *will* recur (a future debugging session wanting a digitisation
    workspace to reproduce a provenance bug). When it does, the right fix
    is to move the debugging workspace to a platform product — never to
    cross this line. This test fails the build if the line is ever
    crossed in any migration's executable SQL."""
    migrations = _migrations_dir()
    assert migrations.is_dir(), f"migrations dir not found: {migrations}"
    offenders = []
    for sql_file in sorted(migrations.glob("*.sql")):
        body = _strip_sql_comments(sql_file.read_text())
        if _FORBIDDEN_GRANT.search(body):
            offenders.append(sql_file.name)
    assert not offenders, (
        "module_digitisation is being granted clinical_query in "
        f"{offenders} — this contradicts the written Type C customer "
        "promise. Do NOT add this grant. If you need a digitisation "
        "workspace to run a query for debugging, move that workspace to "
        "a platform product instead."
    )


# ===========================================================================
# Layer 2 — type invariants (the unsafe shape cannot be constructed)
# ===========================================================================

def test_resolvedsource_openable_requires_signed_url():
    """The silent-dead-link guard, as an executable invariant. You
    physically cannot construct an OPENABLE source with no URL."""
    with pytest.raises(ValueError, match="silent dead link"):
        ResolvedSource(
            status=OPENABLE,
            document_id="d1",
            signed_url=None,
            citation="x",
        )


def test_resolvedsource_non_openable_cannot_carry_url():
    with pytest.raises(ValueError, match="only OPENABLE"):
        ResolvedSource(
            status=UNRESOLVABLE,
            document_id="d1",
            signed_url="https://leak",
            citation="x",
            unresolvable_reason="r",
        )


def test_resolvedsource_unresolvable_must_explain_itself():
    with pytest.raises(ValueError, match="explicit unresolvable_reason"):
        ResolvedSource(
            status=UNRESOLVABLE,
            document_id="d1",
            signed_url=None,
            citation="x",
            unresolvable_reason=None,
        )


def test_resolvedsource_always_has_a_citation():
    with pytest.raises(ValueError, match="always carry a citation"):
        ResolvedSource(
            status=NO_SOURCE, document_id=None, signed_url=None, citation=""
        )


def _src(status, **kw):
    base = dict(document_id=None, signed_url=None, citation="c")
    if status == OPENABLE:
        base.update(document_id="d", signed_url="u")
    if status == UNRESOLVABLE:
        base.update(document_id="d", unresolvable_reason="r")
    base.update(kw)
    return ResolvedSource(status=status, **base)


def _row(status):
    prov = Provenance(source_kind="diagnosis", source_document_id="d") \
        if status != NO_SOURCE else Provenance(source_kind=LIVE_ENTRY)
    from ontology.query.provenance import ResolvedRow
    return ResolvedRow(data={"x": 1}, provenance=prov, source=_src(status))


def test_resolvedqueryresult_aggregate_cannot_drift_from_rows():
    """The row/aggregate-consistency invariant (review-suggested,
    adopted as required-in-A). The envelope refuses to exist if the
    cohort-level count disagrees with the rows it summarises — because
    the aggregate is precisely the signal that gets read."""
    rows = [_row(UNRESOLVABLE), _row(UNRESOLVABLE), _row(OPENABLE),
            _row(NO_SOURCE)]
    # Honest count (2 unresolvable) constructs fine.
    ok = ResolvedQueryResult(
        template_id="t", template_version=1, workspace_id="ws",
        rows=rows, row_count=4, data_maturity="populated",
        unresolvable_count=2,
    )
    assert ok.unresolvable_count == 2
    # A drifted aggregate is structurally impossible.
    with pytest.raises(ValueError, match="must never drift apart"):
        ResolvedQueryResult(
            template_id="t", template_version=1, workspace_id="ws",
            rows=rows, row_count=4, data_maturity="populated",
            unresolvable_count=1,
        )


def test_resolvedqueryresult_no_source_is_not_counted_unresolvable():
    """A live_entry is openable==False but is NOT a failure. Counting it
    as unresolvable would inflate the dead-link number into its own
    confident-wrong-answer about how broken the sources are."""
    rows = [_row(NO_SOURCE), _row(NO_SOURCE), _row(OPENABLE)]
    res = ResolvedQueryResult(
        template_id="t", template_version=1, workspace_id="ws",
        rows=rows, row_count=3, data_maturity="populated",
        unresolvable_count=0,  # zero, despite two openable==False rows
    )
    assert res.unresolvable_count == 0
    assert sum(1 for r in res.rows if not r.source.openable) == 2


# ===========================================================================
# Layer 3 — end-to-end resolver invariants (fake Supabase, no DB)
# ===========================================================================

class _FakeTable:
    def __init__(self, rows):
        self._rows = rows
        self._ids = None
        self._ws = None

    def select(self, *_a, **_k):
        return self

    def in_(self, _col, vals):
        self._ids = set(vals)
        return self

    def eq(self, col, val):
        if col == "workspace_id":
            self._ws = val
        return self

    def execute(self):
        out = [
            r for r in self._rows
            if (self._ids is None or r["id"] in self._ids)
            and (self._ws is None or r.get("workspace_id") == self._ws)
        ]
        return types.SimpleNamespace(data=out)


class _FakeBucket:
    def __init__(self, mode):
        self.mode = mode

    def create_signed_url(self, path, expires_in):
        if self.mode == "raise":
            raise RuntimeError("storage unreachable")
        if self.mode == "empty":
            return {}
        return {"signedURL": f"https://signed.example/{path}?t=abc"}


class _FakeStorage:
    def __init__(self, mode):
        self.mode = mode

    def from_(self, _bucket):
        return _FakeBucket(self.mode)


class FakeSupabase:
    def __init__(self, docs, storage_mode="ok"):
        self._docs = docs
        self.storage = _FakeStorage(storage_mode)

    def table(self, _name):
        return _FakeTable(self._docs)


_PRESENT = {
    "id": "doc-present-abc123",
    "workspace_id": "ws-1",
    "filename": "Patient file.pdf",
    "file_path": "ws-1/doc-present-abc123/Patient file.pdf",
    "upload_date": "2026-05-07T17:03:10",
    "created_at": "2026-05-07T17:03:10",
}
_OTHER_TENANT = {
    "id": "doc-other-tenant-xyze15a71",
    "workspace_id": "ws-OTHER",
    "filename": "SomeoneElse.pdf",
    "file_path": "ws-OTHER/x.pdf",
    "upload_date": "2026-01-01T00:00:00",
    "created_at": None,
}


def _result(*provs):
    rows = [QueryRow(data={"patient_id": f"p{i}"}, provenance=p)
            for i, p in enumerate(provs)]
    return QueryResult(
        template_id="patients_with_diagnosis_prefix",
        template_version=1,
        workspace_id="ws-1",
        rows=rows,
        row_count=len(rows),
        data_maturity="populated",
    )


def test_present_document_is_openable_with_honest_citation():
    res = _result(
        Provenance(source_kind="diagnosis",
                   source_document_id="doc-present-abc123", page=2)
    )
    out = resolve_provenance(FakeSupabase([_PRESENT]), res,
                             workspace_id="ws-1")
    s = out.rows[0].source
    assert s.status == OPENABLE and s.openable is True
    assert s.signed_url and s.signed_url.startswith("https://signed.example/")
    # PR B locked-contract change (Decision #1): an OPENABLE citation now
    # carries the binary quality suffix. This FakeSupabase serves no
    # gp_validation_sessions row, so confidence is NOT recoverable — and
    # absence is rendered EXPLICITLY as not-verified, never as silent
    # reassurance. Still a strict exact assertion, just the new contract.
    assert s.citation == (
        "Patient file.pdf, 7 May 2026, page 2 "
        "— extraction quality not verified"
    )
    assert s.quality is not None
    assert s.quality.section_confidence_recoverable is False
    assert s.quality.superseded is False
    assert out.unresolvable_count == 0
    assert out.superseded_count == 0


def test_missing_document_is_visibly_unresolvable():
    """The dominant 62% corpus failure, in unit form. The id ends e15a71
    — the exact truncated form locked decision #3 specified — so the
    citation is the demo-visible known-unknown, never a blank."""
    res = _result(
        Provenance(source_kind="diagnosis",
                   source_document_id="6d435053-e2cf-49fd-ae3c-0cd6bfe15a71")
    )
    out = resolve_provenance(FakeSupabase([_PRESENT]), res,
                             workspace_id="ws-1")
    s = out.rows[0].source
    assert s.status == UNRESOLVABLE and s.openable is False
    assert s.signed_url is None
    assert s.unresolvable_reason == "source_document_not_found_in_workspace"
    assert "…e15a71" in s.citation
    assert "no longer available" in s.citation
    assert out.unresolvable_count == 1


def test_cross_tenant_document_id_does_not_leak():
    """CONSTRUCT-VALIDITY-ONLY (design choice #7): the live corpus
    produces 0 of this case — every one of the 15 missing ids is missing
    globally, not cross-tenant. This is a fabricated fixture, labelled as
    such, asserting the structural defence: the workspace-scoped lookup
    refuses a doc that exists only in another practice, so it resolves
    UNRESOLVABLE rather than leaking another tenant's scan."""
    res = _result(
        Provenance(source_kind="diagnosis",
                   source_document_id="doc-other-tenant-xyze15a71")
    )
    out = resolve_provenance(
        FakeSupabase([_PRESENT, _OTHER_TENANT]), res, workspace_id="ws-1"
    )
    s = out.rows[0].source
    assert s.status == UNRESOLVABLE
    assert s.signed_url is None
    assert "SomeoneElse.pdf" not in s.citation  # no other-tenant metadata
    assert out.unresolvable_count == 1


@pytest.mark.parametrize("mode", ["empty", "raise"])
def test_signing_failure_is_visible_never_a_silent_dead_link(mode):
    """The document row exists but the object cannot be retrieved. This
    must STILL be a visible UNRESOLVABLE, never an OPENABLE with a dead
    URL and never a crash."""
    res = _result(
        Provenance(source_kind="diagnosis",
                   source_document_id="doc-present-abc123")
    )
    out = resolve_provenance(
        FakeSupabase([_PRESENT], storage_mode=mode), res,
        workspace_id="ws-1",
    )
    s = out.rows[0].source
    assert s.status == UNRESOLVABLE and s.openable is False
    assert s.unresolvable_reason == "signed_url_unavailable"
    assert "not retrievable right now" in s.citation
    assert out.unresolvable_count == 1


def test_live_entry_is_no_source_not_a_failure():
    res = _result(Provenance(source_kind=LIVE_ENTRY))
    out = resolve_provenance(FakeSupabase([]), res, workspace_id="ws-1")
    s = out.rows[0].source
    assert s.status == NO_SOURCE and s.openable is False
    assert s.signed_url is None
    assert out.unresolvable_count == 0  # NOT counted


def test_mixed_cohort_aggregate_equals_unresolvable_rows_exactly():
    """The end-to-end consistency proof: through the real resolver (not
    just the constructor), unresolvable_count equals the number of
    UNRESOLVABLE rows and nothing else — and no openable row ever lacks a
    URL."""
    res = _result(
        Provenance(source_kind="diagnosis",
                   source_document_id="doc-present-abc123"),       # openable
        Provenance(source_kind="diagnosis",
                   source_document_id="missing-aaaaaa"),            # unresolvable
        Provenance(source_kind="diagnosis",
                   source_document_id="doc-other-tenant-xyze15a71"),  # unresolvable (x-tenant)
        Provenance(source_kind=LIVE_ENTRY),                          # no_source
    )
    out = resolve_provenance(
        FakeSupabase([_PRESENT, _OTHER_TENANT]), res, workspace_id="ws-1"
    )
    statuses = [r.source.status for r in out.rows]
    assert statuses == [OPENABLE, UNRESOLVABLE, UNRESOLVABLE, NO_SOURCE]
    assert out.unresolvable_count == 2
    # The silent-dead-link guarantee, asserted through the real function.
    for r in out.rows:
        if r.source.openable:
            assert r.source.signed_url, "openable row with no URL escaped"
    # The envelope serialises with the cohort signal a clinician reads.
    assert out.to_dict()["unresolvable_count"] == 2


# ===========================================================================
# PR B — ugly-case invariants (low-confidence binary, superseded
# row+aggregate, two-source inertness), DB-free. A table-aware fake is
# required here because PR B's resolver reads gp_validation_sessions and
# action_audit_log in addition to digitised_documents.
# ===========================================================================

from ontology.query import SourceQuality  # noqa: E402


class _PRBTable:
    """Faithful fake: filters by the ACTUAL in_ column and all eq pairs
    (the PR A _FakeTable hardcodes id-filtering, which is wrong for the
    document_id-keyed gp_validation_sessions table)."""

    def __init__(self, rows):
        self._rows, self._inkey, self._invals, self._eq = rows, None, None, {}

    def select(self, *_a, **_k):
        return self

    def in_(self, col, vals):
        self._inkey, self._invals = col, set(vals)
        return self

    def eq(self, col, val):
        self._eq[col] = val
        return self

    def execute(self):
        out = []
        for r in self._rows:
            if self._inkey is not None and r.get(self._inkey) not in self._invals:
                continue
            if any(r.get(k) != v for k, v in self._eq.items()):
                continue
            out.append(r)
        return types.SimpleNamespace(data=out)


class _PRBSupabase:
    def __init__(self, *, docs=None, sessions=None, audit=None,
                 storage_mode="ok"):
        self._t = {
            "digitised_documents": docs or [],
            "gp_validation_sessions": sessions or [],
            "action_audit_log": audit or [],
        }
        self.storage = _FakeStorage(storage_mode)

    def table(self, name):
        return _PRBTable(self._t.get(name, []))


_WS = "ws-prb"
_DOC = {
    "id": "doc-prb-1", "workspace_id": _WS,
    "filename": "Briefing.pdf", "file_path": f"{_WS}/doc-prb-1/Briefing.pdf",
    "upload_date": "2026-02-01T10:00:00", "created_at": "2026-02-01T10:00:00",
}


def _prb_result(*provs):
    rows = [QueryRow(data={"patient_id": f"p{i}"}, provenance=p)
            for i, p in enumerate(provs)]
    return QueryResult(
        template_id="patient_active_medications", template_version=1,
        workspace_id=_WS, rows=rows, row_count=len(rows),
        data_maturity="populated",
    )


def test_superseded_aggregate_cannot_drift_from_rows():
    """Decision #2 sibling of the unresolvable drift invariant. The
    envelope cannot exist if superseded_count disagrees with the rows."""
    from ontology.query.provenance import ResolvedRow
    q_sup = SourceQuality(section_confidence_recoverable=False,
                          superseded=True)
    q_clean = SourceQuality(section_confidence_recoverable=True,
                            superseded=False)
    rows = [
        ResolvedRow(data={}, provenance=Provenance(source_kind="diagnosis",
                    source_document_id="d"),
                    source=ResolvedSource(status=OPENABLE, document_id="d",
                    signed_url="u", citation="c", quality=q_sup)),
        ResolvedRow(data={}, provenance=Provenance(source_kind="diagnosis",
                    source_document_id="e"),
                    source=ResolvedSource(status=OPENABLE, document_id="e",
                    signed_url="u", citation="c", quality=q_clean)),
    ]
    ok = ResolvedQueryResult(
        template_id="t", template_version=1, workspace_id=_WS, rows=rows,
        row_count=2, data_maturity="populated", unresolvable_count=0,
        superseded_count=1,
    )
    assert ok.superseded_count == 1
    with pytest.raises(ValueError, match="must never drift apart"):
        ResolvedQueryResult(
            template_id="t", template_version=1, workspace_id=_WS, rows=rows,
            row_count=2, data_maturity="populated", unresolvable_count=0,
            superseded_count=0,  # drifted
        )


def test_superseded_and_unresolvable_are_independent_signals():
    """Neither aggregate inflates the other: a superseded OPENABLE row is
    NOT unresolvable; an UNRESOLVABLE row is not auto-superseded."""
    out = resolve_provenance(
        _PRBSupabase(
            docs=[_DOC],
            # Fixture MUST carry action_name (not action_type) — the
            # resolver filters on it; a fixture without it tests nothing
            # (the plan's load-bearing risk note).
            audit=[{"action_name": "PromoteDocumentToPatientRecord",
                    "workspace_id": _WS, "reversed_by_audit_id": "rev-1",
                    "parameters": {"document_id": "doc-prb-1"}}],
        ),
        _prb_result(
            Provenance(source_kind="diagnosis", source_document_id="doc-prb-1"),
            Provenance(source_kind="diagnosis", source_document_id="gone-xyz"),
        ),
        workspace_id=_WS,
    )
    openable, missing = out.rows[0].source, out.rows[1].source
    assert openable.status == OPENABLE and openable.quality.superseded is True
    assert missing.status == UNRESOLVABLE
    assert out.superseded_count == 1      # only the openable-superseded one
    assert out.unresolvable_count == 1    # only the missing one
    # Independence: the superseded row is not counted unresolvable and
    # vice versa.
    assert out.superseded_count + out.unresolvable_count == 2


def test_citation_never_says_low_confidence_or_percentage():
    """Decision #1 as an executable invariant. Drive BOTH branches
    (recoverable / not) and assert the banned strings never appear and
    the two locked phrases appear exactly."""
    out = resolve_provenance(
        _PRBSupabase(
            docs=[_DOC],
            sessions=[{"document_id": "doc-prb-1", "workspace_id": _WS,
                       "confidence_scores": {"vitals": 0.9}}],
        ),
        _prb_result(Provenance(source_kind="diagnosis",
                               source_document_id="doc-prb-1")),
        workspace_id=_WS,
    )
    rec = out.rows[0].source.citation
    assert "extraction quality not individually verified " \
           "(document-level check available)" in rec
    out2 = resolve_provenance(
        _PRBSupabase(docs=[_DOC], sessions=[]),  # no session ⇒ not recoverable
        _prb_result(Provenance(source_kind="diagnosis",
                               source_document_id="doc-prb-1")),
        workspace_id=_WS,
    )
    notrec = out2.rows[0].source.citation
    assert notrec.endswith("extraction quality not verified")
    for c in (rec, notrec):
        assert "low-confidence" not in c.lower()
        assert "%" not in c
        assert not any(ch.isdigit() for ch in c.split("quality")[-1])


def test_superseded_suffix_is_locked_wording():
    out = resolve_provenance(
        _PRBSupabase(
            docs=[_DOC],
            audit=[{"action_name": "PromoteDocumentToPatientRecord",
                    "workspace_id": _WS, "reversed_by_audit_id": "rev-1",
                    "parameters": {"document_id": "doc-prb-1"}}],
        ),
        _prb_result(Provenance(source_kind="diagnosis",
                               source_document_id="doc-prb-1")),
        workspace_id=_WS,
    )
    assert out.rows[0].source.citation.endswith(
        " (source promotion was reversed — fact may be stale)"
    )


def test_additional_sources_is_inert_on_current_corpus():
    """THE Decision-1 required-rider named gate. The two-source field
    exists (option a) but the resolver NEVER populates it on the current
    corpus (no multi-source schema). Inertness is a TESTED invariant, not
    an assumption — a change that silently starts populating it fails
    here, same drift-impossible status as superseded_count."""
    out = resolve_provenance(
        _PRBSupabase(
            docs=[_DOC],
            sessions=[{"document_id": "doc-prb-1", "workspace_id": _WS,
                       "confidence_scores": {"x": 1}}],
            audit=[{"action_name": "PromoteDocumentToPatientRecord",
                    "workspace_id": _WS, "reversed_by_audit_id": "r",
                    "parameters": {"document_id": "doc-prb-1"}}],
        ),
        _prb_result(
            Provenance(source_kind="diagnosis", source_document_id="doc-prb-1"),
            Provenance(source_kind="diagnosis", source_document_id="gone"),
            Provenance(source_kind=LIVE_ENTRY),
        ),
        workspace_id=_WS,
    )
    # `additional_sources` lives on ResolvedRow (the two-source
    # representation is per-row, not per-source). The resolver NEVER
    # populates it on the current corpus — inertness is the tested gate.
    for r in out.rows:
        assert r.additional_sources is None
        assert r.to_dict()["additional_sources"] is None


def test_026_migration_ends_with_notify_pgrst():
    """Migration 026 adds query RPC functions, so — unlike 025 — it MUST
    end with NOTIFY pgrst or every new template 404s (PGRST202) until the
    schema cache happens to reload. Comment-stripped scan (reuse PR A's
    _strip_sql_comments)."""
    f = _migrations_dir() / "026_query_layer_briefing_templates.sql"
    assert f.is_file(), f"migration 026 not found: {f}"
    body = _strip_sql_comments(f.read_text())
    assert "notify pgrst" in body.lower(), (
        "026 adds functions but does not NOTIFY pgrst — the new templates "
        "will be invisible to PostgREST until the cache reloads"
    )
    # NOTIFY must come before the final COMMIT (inside the txn body).
    low = body.lower()
    assert low.rfind("notify pgrst") < low.rfind("commit"), (
        "NOTIFY pgrst must precede COMMIT"
    )


def test_resolver_refuses_unscoped():
    with pytest.raises(ValueError, match="refusing an unscoped"):
        resolve_provenance(FakeSupabase([]), _result(), workspace_id="")
