"""
PR 6 query-layer unit tests — no DB, fast.

The load-bearing one is test_every_template_declares_provenance: it is
the CI expression of "every answer carries its source." A template
that forgets provenance cannot pass this, the same way
test_tenant_query_isolation.py is the CI expression of "no unscoped
tenant query."
"""

from __future__ import annotations

import pytest

from ontology.query import (
    all_templates,
    get_template,
    run_template,
    QueryError,
    Provenance,
)
from ontology.query.spec import ParamSpec, TemplateSpec, PROVENANCE_COLUMN
from ontology.query.result import LIVE_ENTRY


# ===========================================================================
# Registry + the provenance CI invariant
# ===========================================================================

def test_registry_populated_on_import():
    ids = [t.id for t in all_templates()]
    assert "patients_with_diagnosis_prefix" in ids


def test_every_template_declares_provenance():
    """THE invariant. Every registered template must declare a
    provenance output column. Adding a template that omits it makes
    this fail — provenance is structural, not a review checklist item."""
    for t in all_templates():
        assert PROVENANCE_COLUMN in t.output_columns, (
            f"template {t.id!r} does not declare a {PROVENANCE_COLUMN!r} "
            f"output column"
        )


def test_every_template_rpc_is_query_namespaced():
    for t in all_templates():
        assert t.rpc_name.startswith("query_"), (
            f"{t.id!r} rpc {t.rpc_name!r} must be query_-namespaced"
        )


def test_templatespec_rejects_missing_provenance():
    with pytest.raises(ValueError, match="must declare a 'provenance'"):
        TemplateSpec(
            id="bad", version=1, rpc_name="query_bad",
            params=[], output_columns=["patient_id"],  # no provenance
        )


def test_templatespec_rejects_non_query_rpc_name():
    with pytest.raises(ValueError, match="must start with 'query_'"):
        TemplateSpec(
            id="bad", version=1, rpc_name="execute_action_bad",
            params=[], output_columns=["provenance"],
        )


# ===========================================================================
# Param validation
# ===========================================================================

def test_param_required_missing_raises():
    p = ParamSpec(name="x", py_type=str, rpc_arg="p_x", required=True)
    with pytest.raises(ValueError, match="missing required parameter 'x'"):
        p.coerce_and_validate(None)


def test_param_optional_uses_default():
    p = ParamSpec(name="lim", py_type=int, rpc_arg="p_lim",
                  required=False, default=100)
    assert p.coerce_and_validate(None) == 100


def test_param_type_mismatch_raises():
    p = ParamSpec(name="lim", py_type=int, rpc_arg="p_lim")
    with pytest.raises(ValueError, match="must be int"):
        p.coerce_and_validate("not-a-number")


def test_param_numeric_string_coerced_to_int():
    p = ParamSpec(name="lim", py_type=int, rpc_arg="p_lim")
    assert p.coerce_and_validate("42") == 42


def test_diagnosis_prefix_validator_rejects_like_metachars():
    t = get_template("patients_with_diagnosis_prefix")
    prefix = next(p for p in t.params if p.name == "icd10_prefix")
    for bad in ["E11%", "I10_", "x'; DROP", 'a"b', "c\\d"]:
        with pytest.raises(ValueError):
            prefix.coerce_and_validate(bad)
    # valid ICD-10-ish prefixes pass
    for good in ["E11", "I10", "E11.9", "Z00"]:
        assert prefix.coerce_and_validate(good) == good


# ===========================================================================
# Provenance contract
# ===========================================================================

def test_provenance_requires_source_unless_live_entry():
    # sourced fact with no document id → refused
    with pytest.raises(ValueError, match="refusing to present a sourced fact"):
        Provenance(source_kind="diagnosis", source_document_id=None)
    # live entry with no document id → allowed
    p = Provenance(source_kind=LIVE_ENTRY, source_document_id=None)
    assert p.source_document_id is None


def test_provenance_from_jsonb_rejects_non_dict():
    with pytest.raises(ValueError, match="without a provenance object"):
        Provenance.from_jsonb(None)
    with pytest.raises(ValueError, match="without a provenance object"):
        Provenance.from_jsonb("oops")


def test_provenance_from_jsonb_roundtrips():
    blob = {
        "source_kind": "diagnosis",
        "source_document_id": "doc-1",
        "occurred_on": "2026-03-08",
        "snippet": "E11.9 — Type 2 diabetes",
        "page": 1,
    }
    p = Provenance.from_jsonb(blob)
    assert p.source_document_id == "doc-1"
    assert p.to_dict() == blob


# ===========================================================================
# run_template — argument plumbing (mocked supabase, no DB)
# ===========================================================================

class _FakeRPC:
    def __init__(self, rows): self._rows = rows
    def execute(self): return type("R", (), {"data": self._rows})()


class _FakeSupabase:
    def __init__(self, rows): self._rows = rows; self.calls = []
    def rpc(self, name, kwargs):
        self.calls.append((name, kwargs))
        return _FakeRPC(self._rows)


def test_run_template_injects_workspace_and_validates():
    fake = _FakeSupabase(rows=[{
        "patient_id": "p1", "first_name": "A", "last_name": "B",
        "dob": "1990-01-01", "diagnosis_code": "E11.9",
        "diagnosis_display": "T2DM",
        "provenance": {"source_kind": "diagnosis",
                       "source_document_id": "doc-9",
                       "occurred_on": "2026-03-08",
                       "snippet": "E11.9", "page": None},
    }])
    res = run_template(
        fake, "patients_with_diagnosis_prefix",
        {"icd10_prefix": "E11"}, workspace_id="ws-1",
    )
    name, kwargs = fake.calls[0]
    assert name == "query_patients_with_diagnosis_prefix"
    assert kwargs["p_workspace_id"] == "ws-1"          # injected by runner
    assert kwargs["p_icd10_prefix"] == "E11"
    assert kwargs["p_limit"] == 100                    # default applied
    assert res.row_count == 1
    assert res.rows[0].provenance.source_document_id == "doc-9"
    assert "provenance" not in res.rows[0].data        # split out


def test_run_template_refuses_without_workspace():
    with pytest.raises(QueryError) as e:
        run_template(_FakeSupabase([]), "patients_with_diagnosis_prefix",
                     {"icd10_prefix": "E11"}, workspace_id="")
    assert e.value.code == "missing_workspace"


def test_run_template_rejects_unknown_param():
    with pytest.raises(QueryError) as e:
        run_template(_FakeSupabase([]), "patients_with_diagnosis_prefix",
                     {"icd10_prefix": "E11", "evil": 1}, workspace_id="ws-1")
    assert e.value.code == "unknown_param"


def test_run_template_unknown_template():
    with pytest.raises(QueryError) as e:
        run_template(_FakeSupabase([]), "no_such_template",
                     {}, workspace_id="ws-1")
    assert e.value.code == "unknown_template"


def test_run_template_row_missing_provenance_fails_loud():
    fake = _FakeSupabase(rows=[{"patient_id": "p1"}])  # no provenance key
    with pytest.raises(QueryError) as e:
        run_template(fake, "patients_with_diagnosis_prefix",
                     {"icd10_prefix": "E11"}, workspace_id="ws-1")
    assert e.value.code == "provenance_missing"
