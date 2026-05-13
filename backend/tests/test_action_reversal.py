"""
ActionExecutor reversal test suite — PR 2.

Four tests covering the reverse() pathway. Mostly slow_integration
because reversal requires a real RPC + audit row in the database.

  4 NEW tests:
    1. test_reverse_undoes_promotion — forward + reverse cycle works
    2. test_reverse_of_already_reversed_fails_precondition — idempotency
    3. test_reverse_of_dry_run_audit_row_fails_precondition — pins
       cannot_reverse_dry_run as the answer
    4. test_reverse_of_effect_failed_audit_row_succeeds_idempotently —
       reversal undoes what affected_objects claims, regardless of
       forward outcome

The reverse pathway is:
  Python validates (audit row exists, not dry-run, not already reversed,
  action_name is in _REVERSE_RPC_FOR_ACTION) → calls
  reverse_action_promote_document RPC → RPC deletes by id all created
  rows + restores document's previous_encounter_id + writes new
  reversal audit row + updates original row's reversed_by_audit_id.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.actions import ActorContext, execute
from app.actions.executor import reverse
from app.actions.base import (
    ERROR_CODE_CANNOT_REVERSE_DRY_RUN,
    ERROR_CODE_PRECONDITION_FAILED,
)
from ontology.actions.promote_document import (
    PatientMatchEvidence,
    PromoteDocumentToPatientRecord,
)


def _build_action(doc_id: str, workspace_id: str, patient_id: str,
                  actor_user_id: str, extractions: dict) -> PromoteDocumentToPatientRecord:
    return PromoteDocumentToPatientRecord(
        document_id=doc_id,
        target_patient_id=patient_id,
        confirmation=PatientMatchEvidence(
            confirmed_by_user_id=actor_user_id,
            confirmed_at=datetime.now(timezone.utc),
            match_signals=["test"],
            confidence_score=1.0,
        ),
        actor_user_id=actor_user_id,
        practice_id=workspace_id,
        workspace_id=workspace_id,
        extractions=extractions,
    )


# ===========================================================================
# Slow integration — require Supabase + migrations 015/016 applied
# ===========================================================================

@pytest.mark.slow_integration
def test_reverse_undoes_promotion(supabase_client, validated_document_row):
    """Promote, capture the audit_id, reverse, verify the database is
    back to its pre-promotion state.

    Asserts:
      - all op='created' affected_objects rows are gone (DELETE by id)
      - digitised_documents.encounter_id restored to NULL (the
        previous_encounter_id captured on the Document entry)
      - original audit row has reversed_by_audit_id pointing at the
        new audit row
      - new audit row has outcome='reversed' and reverses_audit_id
        pointing at the original
    """
    sb = supabase_client
    doc_id = validated_document_row["document_id"]
    workspace_id = validated_document_row["workspace_id"]

    patient_id = str(uuid.uuid4())
    sb.table("patients").insert({
        "id": patient_id,
        "tenant_id": validated_document_row["tenant_id"],
        "workspace_id": workspace_id,
        "first_name": "Reverse", "last_name": "Test",
        "dob": "1985-03-14", "id_number": "8503140003089",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }).execute()

    actor = ActorContext(
        user_id="test-user-reverse",
        email="reverse@example.co.za",
        permissions=["digitisation_validation"],
    )

    try:
        # 1. Promote.
        action = _build_action(
            doc_id, workspace_id, patient_id,
            "test-user-reverse", validated_document_row["extraction"],
        )
        fwd = execute(action, actor=actor, supabase=sb)
        assert fwd.outcome == "success", (
            f"forward must succeed for the reversal test to be meaningful; "
            f"outcome={fwd.outcome} error={fwd.error}"
        )

        # Snapshot the created Encounter / Diagnosis IDs before reversal
        # so we can verify the post-reverse DB state.
        created_encounters = [
            e["id"] for e in fwd.affected_objects
            if e["type"] == "Consultation" and e["op"] == "created"
        ]
        created_diagnoses = [
            e["id"] for e in fwd.affected_objects
            if e["type"] == "Diagnosis" and e["op"] == "created"
        ]
        assert created_encounters, "forward should have created at least one encounter"

        # 2. Reverse.
        rev = reverse(fwd.audit_id, actor=actor, supabase=sb,
                      reason="test_reverse_undoes_promotion")
        assert rev.outcome == "reversed", (
            f"reverse should return outcome=reversed; got {rev.outcome} "
            f"error={rev.error.code if rev.error else None}"
        )

        # 3. Created encounters are gone
        for enc_id in created_encounters:
            r = sb.table("encounters").select("id").eq("id", enc_id).execute()
            assert not r.data, f"encounter {enc_id} should be deleted by reverse"

        # 4. Created diagnoses are gone
        for diag_id in created_diagnoses:
            r = sb.table("diagnoses").select("id").eq("id", diag_id).execute()
            assert not r.data, f"diagnosis {diag_id} should be deleted by reverse"

        # 5. Document's encounter_id is restored
        doc = (
            sb.table("digitised_documents").select("encounter_id, patient_id")
            .eq("id", doc_id).execute()
        )
        # The fixture's pre-promotion encounter_id was NULL.
        assert doc.data[0]["encounter_id"] is None, (
            f"document encounter_id should be restored to NULL after reverse; "
            f"got {doc.data[0]['encounter_id']}"
        )
        assert doc.data[0]["patient_id"] is None, (
            f"document patient_id should also be cleared on reverse; "
            f"got {doc.data[0]['patient_id']}"
        )

        # 6. Original audit row's reversed_by_audit_id is set
        orig = (
            sb.table("action_audit_log").select("reversed_by_audit_id")
            .eq("id", fwd.audit_id).execute()
        )
        assert orig.data[0]["reversed_by_audit_id"] == rev.audit_id, (
            f"original's reversed_by_audit_id should point at new audit row; "
            f"got {orig.data[0]['reversed_by_audit_id']}"
        )

        # 7. New audit row's reverses_audit_id is set
        new = (
            sb.table("action_audit_log").select("reverses_audit_id, outcome")
            .eq("id", rev.audit_id).execute()
        )
        assert new.data[0]["reverses_audit_id"] == fwd.audit_id
        assert new.data[0]["outcome"] == "reversed"

    finally:
        sb.table("patients").delete().eq("id", patient_id).execute()


@pytest.mark.slow_integration
def test_reverse_of_already_reversed_fails_precondition(
    supabase_client, validated_document_row
):
    """A second reversal returns precondition_failed with 'already reversed'."""
    sb = supabase_client
    doc_id = validated_document_row["document_id"]
    workspace_id = validated_document_row["workspace_id"]

    patient_id = str(uuid.uuid4())
    sb.table("patients").insert({
        "id": patient_id,
        "tenant_id": validated_document_row["tenant_id"],
        "workspace_id": workspace_id,
        "first_name": "DoubleReverse", "last_name": "Test",
        "dob": "1985-03-14", "id_number": "8503140004080",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }).execute()

    actor = ActorContext(
        user_id="test-user-double-reverse",
        email="double@example.co.za",
        permissions=["digitisation_validation"],
    )

    try:
        action = _build_action(
            doc_id, workspace_id, patient_id,
            "test-user-double-reverse", validated_document_row["extraction"],
        )
        fwd = execute(action, actor=actor, supabase=sb)
        assert fwd.outcome == "success"

        # First reverse succeeds
        first = reverse(fwd.audit_id, actor=actor, supabase=sb)
        assert first.outcome == "reversed"

        # Second reverse: precondition_failed with 'already reversed'
        second = reverse(fwd.audit_id, actor=actor, supabase=sb)
        assert second.outcome == "precondition_failed", (
            f"second reverse must fail; got outcome={second.outcome} "
            f"error={second.error.code if second.error else None}"
        )
        assert second.error is not None
        assert second.error.code == ERROR_CODE_PRECONDITION_FAILED
        assert "already reversed" in (second.error.message or "").lower()

    finally:
        sb.table("patients").delete().eq("id", patient_id).execute()


@pytest.mark.slow_integration
def test_reverse_of_dry_run_audit_row_fails_precondition(
    supabase_client, validated_document_row
):
    """Reversing a dry-run audit row returns cannot_reverse_dry_run.

    A dry-run is by definition a "what would happen" preview; there is
    nothing to undo. This test pins the answer — and pins that "fixing"
    reversal to succeed on dry-runs would be silently nonsense.
    """
    sb = supabase_client
    doc_id = validated_document_row["document_id"]
    workspace_id = validated_document_row["workspace_id"]

    patient_id = str(uuid.uuid4())
    sb.table("patients").insert({
        "id": patient_id,
        "tenant_id": validated_document_row["tenant_id"],
        "workspace_id": workspace_id,
        "first_name": "DryRun", "last_name": "Reverse",
        "dob": "1985-03-14", "id_number": "8503140005081",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }).execute()

    actor = ActorContext(
        user_id="test-user-dry-reverse",
        email="dry@example.co.za",
        permissions=["digitisation_validation"],
    )

    try:
        action = _build_action(
            doc_id, workspace_id, patient_id,
            "test-user-dry-reverse", validated_document_row["extraction"],
        )
        dry = execute(action, actor=actor, supabase=sb, dry_run=True)
        assert dry.outcome == "dry_run"

        rev = reverse(dry.audit_id, actor=actor, supabase=sb)
        assert rev.outcome == "precondition_failed"
        assert rev.error is not None
        assert rev.error.code == ERROR_CODE_CANNOT_REVERSE_DRY_RUN, (
            f"expected cannot_reverse_dry_run; got {rev.error.code}: "
            f"{rev.error.message}"
        )

    finally:
        sb.table("patients").delete().eq("id", patient_id).execute()


@pytest.mark.slow_integration
def test_reverse_of_effect_failed_audit_row_succeeds_idempotently(
    supabase_client, validated_document_row
):
    """Reversal of an effect_failed audit row succeeds with outcome=reversed.

    The forward action may have partially applied — affected_objects
    records what the RPC saw before any rollback. Reversing iterates
    that list and emits DELETE-by-ID statements; missing rows are
    no-ops. The contract: reversal undoes what affected_objects claims
    happened, regardless of the forward outcome.

    We simulate an effect_failed audit row by inserting one synthetically
    with affected_objects pointing at IDs that won't exist (or partially
    exist). The reversal should still return outcome='reversed'.
    """
    sb = supabase_client
    workspace_id = validated_document_row["workspace_id"]

    # Synthetic effect_failed audit row that references non-existent
    # encounter / diagnosis IDs. DELETE by id is idempotent for missing
    # rows so this exercises the "tolerates effect_failed" pathway.
    fake_enc_id = str(uuid.uuid4())
    fake_diag_id = str(uuid.uuid4())
    fake_doc_id = validated_document_row["document_id"]
    fake_audit_id = str(uuid.uuid4())

    affected = [
        {"type": "Consultation", "id": fake_enc_id, "op": "created"},
        {"type": "Diagnosis", "id": fake_diag_id, "op": "created"},
        {"type": "Document", "id": fake_doc_id, "op": "updated",
         "previous_encounter_id": None},
    ]
    sb.table("action_audit_log").insert({
        "id": fake_audit_id,
        "action_name": "PromoteDocumentToPatientRecord",
        "action_version": 1,
        "actor_user_id": "test-user-effect-failed",
        "actor_email": "ef@example.co.za",
        "practice_id": workspace_id,
        "workspace_id": workspace_id,
        "dry_run": False,
        "parameters": {"document_id": fake_doc_id},
        "preconditions_checked": [],
        "effects_applied": [],
        "affected_objects": affected,
        "outcome": "effect_failed",
        "error_detail": {"code": "effect_failed", "message": "synthetic", "context": {}},
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": 1,
    }).execute()

    actor = ActorContext(
        user_id="test-user-effect-failed",
        email="ef@example.co.za",
        permissions=["digitisation_validation"],
    )

    try:
        rev = reverse(fake_audit_id, actor=actor, supabase=sb)
        assert rev.outcome == "reversed", (
            f"reversal of effect_failed row must succeed (DELETE-by-id is "
            f"idempotent for missing rows); got outcome={rev.outcome} "
            f"error={rev.error.code if rev.error else None}"
        )

        # Original row should still get its reversed_by_audit_id set
        orig = (
            sb.table("action_audit_log").select("reversed_by_audit_id")
            .eq("id", fake_audit_id).execute()
        )
        assert orig.data[0]["reversed_by_audit_id"] == rev.audit_id

    finally:
        # Best-effort cleanup
        try:
            sb.table("action_audit_log").delete().eq("id", fake_audit_id).execute()
            sb.table("action_audit_log").delete().eq("reverses_audit_id",
                                                       fake_audit_id).execute()
        except Exception:  # noqa: BLE001
            pass
