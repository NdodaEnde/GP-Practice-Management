"""
PR 3 unit tests — no DB, fast.

Covers the new action class constructions, audit-parameter round-trips,
reverse-dispatch consistency, and the new primitives' shape.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

import pytest

from app.actions import ACTIONS
from app.actions.executor import (
    _REVERSE_PYTHON_FOR_ACTION,
    _REVERSE_RPC_FOR_ACTION,
)
from app.actions.primitives import (
    ConfirmationActorMatches,
    RestoreSoftDeleted,
    SetJsonPath,
    SetMultipleFields,
    StatusOneOf,
)


# ===========================================================================
# Registry — every PR 3 action is registered
# ===========================================================================

def test_pr3_all_seven_actions_registered():
    """The seven PR 3 actions should be in ACTIONS after importing
    app.actions (which triggers registered.py's side effects)."""
    expected = {
        "RejectDocument",
        "EditExtractionField",
        "ReprocessDocument",
        "VoidPrescription",
        "SoftDeletePatient",
        "ReassignDocument",
        "MergePatient",
    }
    assert expected.issubset(set(ACTIONS.keys())), (
        f"missing PR 3 actions: {expected - set(ACTIONS.keys())}"
    )


def test_pr3_reverse_dispatch_no_overlap():
    """An action_name cannot be in both reverse maps — bug if it is."""
    rpc_keys = set(_REVERSE_RPC_FOR_ACTION.keys())
    python_keys = set(_REVERSE_PYTHON_FOR_ACTION.keys())
    overlap = rpc_keys & python_keys
    assert not overlap, (
        f"action(s) in both reverse maps: {overlap}. Pick one path per action."
    )


def test_pr3_every_reversible_action_has_a_reverse_path():
    """Every action with __reversible__=True should have an entry in
    one of the two reverse-dispatch maps."""
    for name, cls in ACTIONS.items():
        if cls.__reversible__:
            in_rpc = name in _REVERSE_RPC_FOR_ACTION
            in_python = name in _REVERSE_PYTHON_FOR_ACTION
            assert in_rpc or in_python, (
                f"{name} is __reversible__=True but has no reverse handler. "
                f"Add it to _REVERSE_RPC_FOR_ACTION or call "
                f"register_python_reversal() in its module."
            )


def test_pr3_reprocess_document_is_not_reversible():
    """ReprocessDocument deliberately not-reversible — reprocess is
    idempotent at the watcher; 'undoing a reprocess' has no semantics."""
    assert ACTIONS["ReprocessDocument"].__reversible__ is False
    assert "ReprocessDocument" not in _REVERSE_RPC_FOR_ACTION
    assert "ReprocessDocument" not in _REVERSE_PYTHON_FOR_ACTION


# ===========================================================================
# Audit parameter round-trips
# ===========================================================================

def _round_trip(action_cls, init_kwargs):
    """Construct, serialise to_audit_parameters, reconstruct via
    from_audit_parameters, verify the reconstruction matches."""
    a = action_cls(**init_kwargs)
    params = a.to_audit_parameters()
    b = action_cls.from_audit_parameters(params)
    return a, b, params


def test_reject_document_audit_round_trip():
    from ontology.actions.reject_document import RejectDocument
    a, b, params = _round_trip(RejectDocument, dict(
        document_id="doc-1",
        reason="Looks wrong",
        actor_user_id="u-1",
        practice_id="ws-1",
        workspace_id="ws-1",
        previous_status="pending_validation",
        previous_validated_at="2026-01-01T00:00:00+00:00",
        previous_validated_by="someone@example.com",
        previous_error_message=None,
    ))
    assert b.document_id == "doc-1"
    assert b.previous_status == "pending_validation"
    assert "previous_status" in params


def test_void_prescription_audit_round_trip():
    from ontology.actions.void_prescription import VoidPrescription
    a, b, _ = _round_trip(VoidPrescription, dict(
        prescription_id="rx-1",
        void_reason="dispensing error",
        actor_user_id="u-1",
        practice_id="ws-1",
        workspace_id="ws-1",
        previous_status="active",
    ))
    assert b.prescription_id == "rx-1"
    assert b.previous_status == "active"


def test_edit_extraction_field_audit_round_trip():
    from ontology.actions.edit_extraction_field import EditExtractionField
    a, b, _ = _round_trip(EditExtractionField, dict(
        document_id="doc-1",
        session_id="sess-1",
        field_path="patient_demographics.surname",
        from_value="Smith",
        to_value="Smyth",
        actor_user_id="u-1",
        practice_id="ws-1",
        workspace_id="ws-1",
    ))
    assert b.field_path == "patient_demographics.surname"
    assert b.from_value == "Smith"
    assert b.to_value == "Smyth"


def test_soft_delete_patient_audit_round_trip():
    from ontology.actions.soft_delete_patient import SoftDeletePatient
    a, b, _ = _round_trip(SoftDeletePatient, dict(
        patient_id="p-1",
        erasure_reason="POPIA request",
        actor_user_id="u-1",
        practice_id="ws-1",
        workspace_id="ws-1",
    ))
    assert b.patient_id == "p-1"
    assert b.erasure_reason == "POPIA request"


def test_reassign_document_audit_round_trip():
    from ontology.actions.reassign_document import ReassignDocument
    a, b, _ = _round_trip(ReassignDocument, dict(
        document_id="doc-1",
        new_patient_id="p-2",
        reason="wrong patient at upload",
        actor_user_id="u-1",
        practice_id="ws-1",
        workspace_id="ws-1",
    ))
    assert b.new_patient_id == "p-2"


def test_merge_patient_audit_round_trip():
    from ontology.actions.merge_patient import MergePatient, MergeConfirmation
    confirmation = MergeConfirmation(
        confirmed_by_user_id="u-1",
        confirmed_at=datetime.now(timezone.utc),
        survivor_choice_evidence="more recent visit history",
    )
    a, b, _ = _round_trip(MergePatient, dict(
        source_patient_id="p-source",
        target_patient_id="p-target",
        merge_reason="dup detected",
        confirmation=confirmation,
        actor_user_id="u-1",
        practice_id="ws-1",
        workspace_id="ws-1",
    ))
    assert b.source_patient_id == "p-source"
    assert b.confirmation is not None
    assert b.confirmation.confirmed_by_user_id == "u-1"


# ===========================================================================
# New primitives — shape sanity
# ===========================================================================

def test_set_multiple_fields_plan_describes_all_columns():
    eff = SetMultipleFields(
        table="prescriptions",
        object_id="rx-1",
        columns={"status": "cancelled", "void_reason": "x", "updated_at": "now"},
        object_type="Prescription",
    )

    class _FakeCtx:
        pass

    desc = eff.plan(_FakeCtx())
    assert "3 columns" in desc.summary
    assert desc.will_affect == [{"type": "Prescription", "id": "rx-1", "op": "updated"}]


def test_status_one_of_constructs_with_default_column():
    p = StatusOneOf(
        table="digitised_documents",
        object_id="doc-1",
        allowed=["parsed", "validated"],
    )
    assert p.column == "status"
    assert "in ['parsed', 'validated']" in p.name


def test_confirmation_actor_matches_fail_path_message():
    p = ConfirmationActorMatches(
        confirmation_user_id="user-a",
        actor_user_id="user-b",
    )

    class _FakeCtx:
        pass

    r = p.check(_FakeCtx())
    assert r.passed is False
    assert "user-a" in (r.detail or "")
    assert "user-b" in (r.detail or "")


def test_restore_soft_deleted_plan_op_is_updated_not_created():
    """RestoreSoftDeleted's affected_objects op is 'updated' (clearing
    a flag), not 'created' — affected_objects ops are a closed set."""
    eff = RestoreSoftDeleted(
        table="patients",
        object_id="p-1",
        object_type="Patient",
    )

    class _FakeCtx:
        pass

    desc = eff.plan(_FakeCtx())
    assert desc.will_affect[0]["op"] == "updated"


def test_set_json_path_plan_includes_path_in_summary():
    eff = SetJsonPath(
        table="gp_validation_sessions",
        object_id="sess-1",
        json_column="extractions",
        json_path="patient_demographics.surname",
        value="Smyth",
        object_type="ValidationSession",
    )

    class _FakeCtx:
        pass

    desc = eff.plan(_FakeCtx())
    assert "patient_demographics.surname" in desc.summary
    assert "'Smyth'" in desc.summary


# ===========================================================================
# describe_for_user — non-empty + mentions affected objects
# ===========================================================================

def test_describe_for_user_returns_non_empty_strings():
    """Each PR 3 action's describe_for_user produces a non-empty user-
    facing string when constructed with its minimal valid kwargs."""
    from ontology.actions.reject_document import RejectDocument
    from ontology.actions.edit_extraction_field import EditExtractionField
    from ontology.actions.reprocess_document import ReprocessDocument
    from ontology.actions.void_prescription import VoidPrescription
    from ontology.actions.soft_delete_patient import SoftDeletePatient
    from ontology.actions.reassign_document import ReassignDocument
    from ontology.actions.merge_patient import MergePatient, MergeConfirmation

    constructions = [
        RejectDocument(document_id="d", reason="r", actor_user_id="u",
                       practice_id="ws", workspace_id="ws"),
        EditExtractionField(document_id="d", session_id="s",
                            field_path="x", from_value="a", to_value="b",
                            actor_user_id="u", practice_id="ws", workspace_id="ws"),
        ReprocessDocument(document_id="d", actor_user_id="u",
                          practice_id="ws", workspace_id="ws"),
        VoidPrescription(prescription_id="rx", void_reason="r",
                         actor_user_id="u", practice_id="ws", workspace_id="ws"),
        SoftDeletePatient(patient_id="p", erasure_reason="r",
                          actor_user_id="u", practice_id="ws", workspace_id="ws"),
        ReassignDocument(document_id="d", new_patient_id="p2", reason="r",
                         actor_user_id="u", practice_id="ws", workspace_id="ws"),
        MergePatient(
            source_patient_id="ps", target_patient_id="pt",
            merge_reason="dup",
            confirmation=MergeConfirmation(
                confirmed_by_user_id="u",
                confirmed_at=datetime.now(timezone.utc),
            ),
            actor_user_id="u", practice_id="ws", workspace_id="ws"),
    ]
    for a in constructions:
        desc = a.describe_for_user()
        assert isinstance(desc, str) and len(desc) > 0, (
            f"{a.__class__.__name__}.describe_for_user() returned {desc!r}"
        )
