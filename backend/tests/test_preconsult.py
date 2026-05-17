"""
PR H — the pre-consult honest composition, DB-free.

Scaffolding written to the code bar (the inherited PR-F/PR-G note):
reviewed before the run, no stale-edit class; DB-free fake (no shared
state → no teardown, no residue concern). Proves the LOAD-BEARING half
is the honest structure: a test that only checked the happy-path
composition would be vacuous — the discipline is that what is NOT
composed is carried STRUCTURALLY (`named_not_built` + `surface`) so
absence is never mistaken for "checked, nothing to follow up". That is
asserted explicitly and proven to bite.
"""

from __future__ import annotations

import ontology.preconsult as pc


class _AuditQ:
    def __init__(self, rows): self._rows = rows
    def select(self, *_a, **_k): return self
    def eq(self, *_a, **_k): return self
    def contains(self, *_a, **_k): return self
    def gte(self, *_a, **_k): return self
    def order(self, *_a, **_k): return self
    def execute(self):
        class _R:  # noqa: D401
            pass
        r = _R(); r.data = self._rows
        return r


class _FakeSupabase:
    def __init__(self, audit_rows): self._audit_rows = audit_rows
    def table(self, name):
        assert name == "action_audit_log"  # the only direct read pre-consult does
        return _AuditQ(self._audit_rows)


def _stub_chokepoint(monkeypatch, rows_by_template):
    """Stub run_template+resolve_provenance so the test is DB-free and
    deterministic. rows_by_template: {template_id: [row,...]}."""
    class _Resolved:
        def __init__(self, rows): self._rows = rows
        def to_dict(self): return {"rows": self._rows}

    def fake_run_template(_sb, template_id, _params, *, workspace_id):  # noqa: ANN001
        fake_run_template.calls.append((template_id, workspace_id))
        return template_id
    fake_run_template.calls = []

    def fake_resolve(_sb, template_id, *, workspace_id):  # noqa: ANN001
        return _Resolved(rows_by_template.get(template_id, []))

    monkeypatch.setattr(pc, "run_template", fake_run_template)
    monkeypatch.setattr(pc, "resolve_provenance", fake_resolve)
    return fake_run_template


def test_composes_only_the_three_backed_sources(monkeypatch):
    calls = _stub_chokepoint(monkeypatch, {
        "patient_active_medications": [{"medication_name": "Atenolol"}],
        "immunisations_overdue": [{"vaccine_name": "Hepatitis B"}],
    })
    sb = _FakeSupabase([
        {"action_name": "PromoteDocumentToPatientRecord", "outcome": "success",
         "started_at": "2026-05-01T09:00:00Z",
         "affected_objects": [{"type": "Patient", "id": "pat-1"}]},
    ])
    brief = pc.build_preconsult_brief(
        sb, workspace_id="demo-gp-workspace-001",
        patient_id="pat-1", since="2026-04-01")

    assert brief["active_medications"] == [{"medication_name": "Atenolol"}]
    assert brief["immunisations_overdue"] == [{"vaccine_name": "Hepatitis B"}]
    assert len(brief["changes_since_last_visit"]) == 1
    assert brief["changes_since_last_visit"][0]["action"] == \
        "PromoteDocumentToPatientRecord"
    # both backed query-sources went through the chokepoint (no new path)
    assert {c[0] for c in calls.calls} == {
        "patient_active_medications", "immunisations_overdue"}


def test_named_not_built_is_carried_STRUCTURALLY_with_reasons(monkeypatch):
    """THE load-bearing assertion: what is NOT composed is in the brief
    explicitly, with reasons — never silently absent, never a fake empty
    data field. A consumer cannot mistake absence for 'nothing to follow
    up'."""
    _stub_chokepoint(monkeypatch, {})
    brief = pc.build_preconsult_brief(
        _FakeSupabase([]), workspace_id="ws", patient_id="p")

    nnb = brief["named_not_built"]
    assert set(nnb) == {"open_loops", "allergies", "reason_for_visit"}
    for k, reason in nnb.items():
        assert reason and len(reason) > 30, f"{k} reason is not substantive"
    assert "anti-pattern" in nnb["allergies"].lower()       # the declined override, recorded
    assert "f-1=b" in nnb["open_loops"].lower()
    assert "ingestion" in nnb["reason_for_visit"].lower()
    # surface honesty: NOT clinician-visible, stated in the brief itself
    assert "not clinician-visible" in brief["surface"].lower()
    assert "pr e" in brief["surface"].lower()
    # the named-not-built things are NOT also present as fake empty data
    # fields (absence is structural, not a silent [] that reads as
    # "checked, found nothing").
    for k in ("open_loops", "allergies", "reason_for_visit"):
        assert k not in brief, (
            f"{k!r} must NOT be a top-level data field — it is "
            f"named-not-built, not 'checked and empty'"
        )


def test_empty_backed_sources_are_present_not_omitted(monkeypatch):
    """Honest absence on the BACKED sources too: an empty audit/result is
    [] (present), not a missing key — distinguishable from named-not-
    built. Non-vacuity: the structure is asserted on the empty path."""
    _stub_chokepoint(monkeypatch, {})  # all templates → []
    brief = pc.build_preconsult_brief(
        _FakeSupabase([]), workspace_id="ws", patient_id="p")
    for f in ("active_medications", "changes_since_last_visit",
              "immunisations_overdue"):
        assert f in brief and brief[f] == [], f"{f} must be [] not omitted"
    assert brief["named_not_built"] and brief["surface"]
