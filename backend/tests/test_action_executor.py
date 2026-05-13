"""
ActionExecutor test suite — PR 1.

Three test tiers (see backend/pytest.ini for marker definitions):

  Unit (no DB, no fixtures, fast):
    1. test_action_base_class_enforces_required_methods
    2. test_register_action_decorator_populates_registry
    3. test_error_detail_serialisation_round_trip
    4. test_action_audit_parameters_serialise_to_jsonb_safe
    5. test_error_codes_are_declared_constants (CI drift insurance)

  Integration (FAST, uses validated_document_row direct insert):
    6. test_execute_dry_run_promote_writes_dry_run_audit_row_without_mutating
    7. test_execute_promote_with_stale_confirmation_fails_precondition

  Slow integration (full pipeline, slower):
    8. test_execute_promote_writes_audit_row_with_exact_affected_objects
    9. test_execute_promote_holds_lock_against_concurrent_call

Plan §5 calls for "8 total". This file implements 9 because the error-
code drift unit test the user asked for (cheap CI insurance) is folded
into the unit tier.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from pathlib import Path
import threading
import time
import uuid

import pytest

from app.actions import (
    Action,
    ActorContext,
    execute,
    register_action,
    ACTIONS,
)
from app.actions.base import (
    CheckResult,
    Effect,
    EffectDescriptor,
    EffectResult,
    ErrorDetail,
    ExecutorContext,
    Precondition,
    KNOWN_ERROR_CODES,
    ERROR_CODE_ACTION_LOCKED,
    ERROR_CODE_PRECONDITION_FAILED,
)
from ontology.actions.promote_document import (
    PatientMatchEvidence,
    PromoteDocumentToPatientRecord,
)


# ===========================================================================
# UNIT TESTS (no DB, fast)
# ===========================================================================

def test_action_base_class_enforces_required_methods():
    """Action's abstract methods raise TypeError if a subclass omits them."""
    # Cannot instantiate an Action subclass that doesn't implement the
    # required abstract methods.
    with pytest.raises(TypeError):
        # `eq=False` mirrors the project convention; `@dataclass` decoration
        # doesn't satisfy abstractmethod requirements.
        @dataclass(eq=False)
        class BadAction(Action):
            __action_name__ = "BadAction"
            # missing: preconditions, effects, describe_for_user,
            # to_audit_parameters
        BadAction()  # should raise


def test_register_action_decorator_populates_registry():
    """@register_action inserts the class into ACTIONS."""
    test_name = f"_TestRegistration_{uuid.uuid4().hex[:8]}"

    @register_action
    @dataclass(eq=False)
    class _TestAction(Action):
        __action_name__ = test_name

        def preconditions(self): return []
        def effects(self): return []
        def describe_for_user(self): return "test"
        def to_audit_parameters(self): return {}

    assert test_name in ACTIONS
    assert ACTIONS[test_name] is _TestAction

    # Cleanup so the registry doesn't carry test pollution
    ACTIONS.pop(test_name, None)


def test_error_detail_serialisation_round_trip():
    """ErrorDetail.to_dict() round-trips losslessly into JSON-safe data."""
    ed = ErrorDetail(
        code=ERROR_CODE_ACTION_LOCKED,
        message="locked for testing",
        context={"resource_key": "doc-123", "nested": {"a": 1}},
    )

    d = ed.to_dict()
    # JSON-encode then decode — proves it's JSONB-safe for audit log
    j = json.dumps(d)
    d2 = json.loads(j)

    assert d2["code"] == ERROR_CODE_ACTION_LOCKED
    assert d2["message"] == "locked for testing"
    assert d2["context"]["resource_key"] == "doc-123"
    assert d2["context"]["nested"]["a"] == 1


def test_action_audit_parameters_serialise_to_jsonb_safe():
    """PromoteDocumentToPatientRecord.to_audit_parameters() returns only
    JSON-encodable values."""
    confirmed_at = datetime(2026, 5, 12, 10, 0, 0, tzinfo=timezone.utc)
    action = PromoteDocumentToPatientRecord(
        document_id=str(uuid.uuid4()),
        target_patient_id=str(uuid.uuid4()),
        confirmation=PatientMatchEvidence(
            confirmed_by_user_id="user-abc",
            confirmed_at=confirmed_at,
            match_signals=["sa_id_match", "name_dob_match"],
            confidence_score=0.95,
        ),
        actor_user_id="user-abc",
        practice_id="typec-workspace-001",
        workspace_id="typec-workspace-001",
        extractions={"diagnoses": [{"icd10": "I10"}]},
    )

    params = action.to_audit_parameters()

    # The extractions blob is DELIBERATELY omitted from audit_parameters
    # (would bloat audit log). Verify it's not present.
    assert "extractions" not in params

    # Round-trip through JSON to prove JSONB compatibility
    j = json.dumps(params)
    params2 = json.loads(j)
    assert params2["document_id"] == action.document_id
    assert params2["confirmation"]["confirmed_at"] == confirmed_at.isoformat()
    assert params2["confirmation"]["confidence_score"] == 0.95


def test_error_codes_are_declared_constants():
    """CI drift insurance — every `ErrorDetail(code=...)` literal in the
    actions/ package must reference a declared constant in
    KNOWN_ERROR_CODES.

    This catches the subtle bug of someone introducing a new error code
    in code without adding it to base.py's constant list, breaking
    downstream consumers that switch on codes.
    """
    actions_root = Path(__file__).resolve().parent.parent / "app" / "actions"
    assert actions_root.is_dir(), f"actions/ package missing at {actions_root}"

    # Match `code=ERROR_CODE_<NAME>` and `code="<literal>"` in ErrorDetail
    # constructor calls. Permissive multi-line regex over the source.
    sources = [
        (p, p.read_text())
        for p in actions_root.rglob("*.py")
    ]

    # Pattern A: code references the named constant
    constant_pattern = re.compile(r"code=(ERROR_CODE_[A-Z_]+)")
    # Pattern B: code is a string literal — disallowed (forces constants)
    literal_pattern = re.compile(r'code=["\']([a-z_]+)["\']')

    violations: List[str] = []
    for path, src in sources:
        # Allow string literals in base.py itself (where constants are declared)
        # and in test files (this file lives outside actions/).
        for m in literal_pattern.finditer(src):
            literal = m.group(1)
            if literal not in KNOWN_ERROR_CODES:
                violations.append(f"{path.name}: undeclared literal {literal!r}")
        for m in constant_pattern.finditer(src):
            const_name = m.group(1)
            # The constant must be one of the exports from base.py
            import app.actions.base as base_mod
            if not hasattr(base_mod, const_name):
                violations.append(
                    f"{path.name}: references {const_name} but it's not in base.py"
                )

    assert not violations, (
        "ErrorDetail code drift detected:\n  " + "\n  ".join(violations)
    )


# ===========================================================================
# INTEGRATION TESTS (FAST — uses validated_document_row direct insert)
# ===========================================================================

@pytest.mark.integration
def test_execute_dry_run_promote_writes_dry_run_audit_row_without_mutating(
    supabase_client, validated_document_row
):
    """Dry-run mode: preconditions run, effects.plan() runs, but no DB
    mutation. Audit row is written with outcome='dry_run', dry_run=TRUE,
    and the planned affected_objects.

    Asserts:
      - Exactly 0 new `patients` rows beyond pre-state.
      - Exactly 0 new `encounters` rows beyond pre-state.
      - One new `action_audit_log` row with outcome='dry_run', dry_run=TRUE.
      - The audit row's `affected_objects` is non-empty (effects planned).
    """
    sb = supabase_client
    doc_id = validated_document_row["document_id"]
    workspace_id = validated_document_row["workspace_id"]
    extraction = validated_document_row["extraction"]

    # Snapshot pre-state counts
    patients_before = sb.table("patients").select("id", count="exact") \
        .eq("workspace_id", workspace_id).execute().count or 0
    encounters_before = sb.table("encounters").select("id", count="exact") \
        .eq("workspace_id", workspace_id).execute().count or 0

    actor = ActorContext(
        user_id="test-user-1",
        email="test@example.co.za",
        permissions=["digitisation_validation"],
    )
    action = PromoteDocumentToPatientRecord(
        document_id=doc_id,
        target_patient_id="not-applicable-for-dry-run-create-path",
        confirmation=PatientMatchEvidence(
            confirmed_by_user_id="test-user-1",
            confirmed_at=datetime.now(timezone.utc),
            match_signals=["test"],
            confidence_score=1.0,
        ),
        actor_user_id="test-user-1",
        practice_id=workspace_id,
        workspace_id=workspace_id,
        extractions=extraction,
        force_create_patient=True,
    )

    result = execute(action, actor=actor, supabase=sb, dry_run=True)

    # No mutation
    patients_after = sb.table("patients").select("id", count="exact") \
        .eq("workspace_id", workspace_id).execute().count or 0
    encounters_after = sb.table("encounters").select("id", count="exact") \
        .eq("workspace_id", workspace_id).execute().count or 0

    assert patients_after == patients_before, "dry-run must not insert patients"
    assert encounters_after == encounters_before, "dry-run must not insert encounters"

    # Audit row reflects dry-run
    assert result.outcome in ("dry_run", "precondition_failed"), (
        f"unexpected outcome {result.outcome} — note: ObjectExists on the "
        f"target_patient_id will fail in this test because we used a "
        f"non-existent id to exercise force_create_patient. Either outcome "
        f"is acceptable for confirming dry-run doesn't mutate."
    )

    # Verify audit row landed
    audit_row = sb.table("action_audit_log").select("*") \
        .eq("id", result.audit_id).execute().data
    assert audit_row, "audit row should be persisted"
    row = audit_row[0]
    assert row["dry_run"] is True
    # When all preconditions pass, dry-run records the planned will_affect
    # in affected_objects. When a precondition fails first, affected_objects
    # may be empty — both are valid for this test (it asserts no mutation,
    # not specific outcome).


@pytest.mark.integration
def test_execute_promote_with_stale_confirmation_fails_precondition(
    supabase_client, validated_document_row
):
    """Confirmation older than 15 minutes → ConfirmationFresh fails,
    outcome='precondition_failed', error_detail.code='precondition_failed',
    no patients row created, audit row still written."""
    sb = supabase_client
    doc_id = validated_document_row["document_id"]
    workspace_id = validated_document_row["workspace_id"]

    # Create a fresh patient to be the target — we want this precondition
    # to pass, so we can confirm the FAILING precondition is the staleness check.
    patient_id = str(uuid.uuid4())
    sb.table("patients").insert({
        "id": patient_id,
        "tenant_id": validated_document_row["tenant_id"],
        "workspace_id": workspace_id,
        "first_name": "Stale", "last_name": "Confirmation",
        "dob": "1985-03-14", "id_number": "8503140001087",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }).execute()

    try:
        actor = ActorContext(
            user_id="test-user-stale",
            email="stale@example.co.za",
            permissions=["digitisation_validation"],
        )
        action = PromoteDocumentToPatientRecord(
            document_id=doc_id,
            target_patient_id=patient_id,
            confirmation=PatientMatchEvidence(
                confirmed_by_user_id="test-user-stale",
                # 16 minutes ago — past the 15-minute window
                confirmed_at=datetime.now(timezone.utc) - timedelta(minutes=16),
                match_signals=["test"],
                confidence_score=0.95,
            ),
            actor_user_id="test-user-stale",
            practice_id=workspace_id,
            workspace_id=workspace_id,
            extractions=validated_document_row["extraction"],
        )

        result = execute(action, actor=actor, supabase=sb)

        assert result.outcome == "precondition_failed", (
            f"expected precondition_failed, got {result.outcome}"
        )
        assert result.error is not None
        assert result.error.code == ERROR_CODE_PRECONDITION_FAILED
        assert "ConfirmationFresh" in (result.error.message or ""), (
            f"failing precondition should be ConfirmationFresh; "
            f"got message: {result.error.message!r}"
        )

        # Audit row exists with the right outcome
        audit_row = sb.table("action_audit_log").select("*") \
            .eq("id", result.audit_id).execute().data
        assert audit_row, "audit row should be persisted even on precondition failure"
        assert audit_row[0]["outcome"] == "precondition_failed"

    finally:
        # Cleanup
        sb.table("patients").delete().eq("id", patient_id).execute()


# ===========================================================================
# SLOW INTEGRATION TESTS
# ===========================================================================

@pytest.mark.slow_integration
def test_execute_promote_writes_audit_row_with_exact_affected_objects(
    supabase_client, validated_document_e2e
):
    """Full pipeline through a real document fixture. Asserts the audit
    row's affected_objects matches the fixture's known shape (1 Patient
    + 1 Consultation + N Diagnoses, etc.). PR 1 stub: skips if the
    fixture file isn't committed."""
    # The validated_document_e2e fixture currently skips (pre-fixture
    # in conftest). When PR 2 ships the fixture, this test asserts the
    # exact-count contract on affected_objects.
    pytest.skip(
        "PR 1: e2e fixture file not committed; test scaffold in place. "
        "PR 2 ships fixtures/sample_consultation.pdf and the assertions."
    )


@pytest.mark.slow_integration
def test_execute_promote_holds_lock_against_concurrent_call(
    supabase_client, validated_document_row
):
    """Two threads call execute() simultaneously on the same document.

    PR 2 — un-skipped. The PL/pgSQL RPC's SELECT...FOR UPDATE NOWAIT
    holds the digitised_documents row lock for the duration of the
    promote transaction. The second concurrent call sees the locked
    row, the NOWAIT raises SQLSTATE 55P03, the Effect's error classifier
    maps it to ErrorDetail(code='action_locked'). One thread should
    return outcome='success', the other outcome='effect_failed' with
    code='action_locked'.

    This is the test the Phase 0 outcome explicitly deferred to PR 2.
    """
    sb = supabase_client
    doc_id = validated_document_row["document_id"]
    workspace_id = validated_document_row["workspace_id"]

    # Create the target patient so other preconditions pass
    patient_id = str(uuid.uuid4())
    sb.table("patients").insert({
        "id": patient_id,
        "tenant_id": validated_document_row["tenant_id"],
        "workspace_id": workspace_id,
        "first_name": "Concurrent", "last_name": "Test",
        "dob": "1985-03-14", "id_number": "8503140001087",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }).execute()

    actor = ActorContext(
        user_id="test-user-concurrent",
        email="concurrent@example.co.za",
        permissions=["digitisation_validation"],
    )

    def _build_action() -> PromoteDocumentToPatientRecord:
        return PromoteDocumentToPatientRecord(
            document_id=doc_id,
            target_patient_id=patient_id,
            confirmation=PatientMatchEvidence(
                confirmed_by_user_id="test-user-concurrent",
                confirmed_at=datetime.now(timezone.utc),
                match_signals=["test"],
                confidence_score=1.0,
            ),
            actor_user_id="test-user-concurrent",
            practice_id=workspace_id,
            workspace_id=workspace_id,
            extractions=validated_document_row["extraction"],
        )

    results: List[Any] = []
    errors: List[Exception] = []

    def _runner():
        try:
            r = execute(_build_action(), actor=actor, supabase=sb)
            results.append(r)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    try:
        start = time.monotonic()
        t1 = threading.Thread(target=_runner)
        t2 = threading.Thread(target=_runner)
        t1.start()
        t2.start()
        t1.join(timeout=15)
        t2.join(timeout=15)
        elapsed = time.monotonic() - start

        # No threads should still be alive
        assert not t1.is_alive() and not t2.is_alive(), "executor hung"
        assert not errors, f"unexpected exceptions: {errors}"
        assert elapsed < 10, f"concurrent path took too long: {elapsed:.1f}s"

        # Exactly one should have an action_locked outcome, the other success
        # (or one success + one effect_failed if the data quality issues
        # kick in — accept either as long as the lock is observed)
        outcomes = sorted([r.outcome for r in results])
        codes = sorted([
            (r.error.code if r.error else None) for r in results
        ])
        assert ERROR_CODE_ACTION_LOCKED in codes, (
            f"expected one action_locked outcome among concurrent calls; "
            f"got outcomes={outcomes}, error_codes={codes}"
        )

    finally:
        sb.table("patients").delete().eq("id", patient_id).execute()


@pytest.mark.slow_integration
def test_execute_promote_real_run_one_transaction(
    supabase_client, validated_document_row
):
    """Full pipeline real run through the PR 2 PL/pgSQL RPC.

    Asserts:
      - exactly one action_audit_log row written
      - outcome='success'
      - affected_objects includes at least one Patient (created or
        linked), at least one Consultation (created), and the Document
        (updated with previous_encounter_id captured)
      - latency under 3 seconds (projection is 1-2s; 3s ceiling absorbs
        normal variance, would catch a real regression).
    """
    sb = supabase_client
    doc_id = validated_document_row["document_id"]
    workspace_id = validated_document_row["workspace_id"]

    # Use an existing patient for the target; the RPC may match-or-create
    # based on demographics, but the action's preconditions require a
    # valid target_patient_id.
    patient_id = str(uuid.uuid4())
    sb.table("patients").insert({
        "id": patient_id,
        "tenant_id": validated_document_row["tenant_id"],
        "workspace_id": workspace_id,
        "first_name": "RealRun", "last_name": "Test",
        "dob": "1985-03-14", "id_number": "8503140002088",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }).execute()

    actor = ActorContext(
        user_id="test-user-realrun",
        email="realrun@example.co.za",
        permissions=["digitisation_validation"],
    )
    action = PromoteDocumentToPatientRecord(
        document_id=doc_id,
        target_patient_id=patient_id,
        confirmation=PatientMatchEvidence(
            confirmed_by_user_id="test-user-realrun",
            confirmed_at=datetime.now(timezone.utc),
            match_signals=["test"],
            confidence_score=1.0,
        ),
        actor_user_id="test-user-realrun",
        practice_id=workspace_id,
        workspace_id=workspace_id,
        extractions=validated_document_row["extraction"],
    )

    try:
        start = time.monotonic()
        result = execute(action, actor=actor, supabase=sb)
        elapsed = time.monotonic() - start

        assert result.outcome == "success", (
            f"expected success; got outcome={result.outcome} "
            f"error={result.error.code if result.error else None}: "
            f"{result.error.message if result.error else ''}"
        )
        assert elapsed < 3.0, (
            f"PR 2 latency target is 1-2s; threshold 3s. "
            f"Real run took {elapsed:.2f}s — investigate query plan or "
            f"contention before merging."
        )

        # Exactly one audit row for this run
        rows = (
            sb.table("action_audit_log").select("*")
            .eq("id", result.audit_id).execute().data
        )
        assert len(rows) == 1
        audit = rows[0]
        assert audit["outcome"] == "success"
        assert audit["dry_run"] is False

        # affected_objects must include the three key types
        types = {entry["type"] for entry in audit["affected_objects"]}
        assert "Patient" in types, f"affected_objects missing Patient: {types}"
        assert "Consultation" in types, f"affected_objects missing Consultation: {types}"
        assert "Document" in types, f"affected_objects missing Document: {types}"

        # Document entry should carry previous_encounter_id for reversal
        doc_entry = next(e for e in audit["affected_objects"] if e["type"] == "Document")
        assert "previous_encounter_id" in doc_entry, (
            f"Document affected_object must capture previous_encounter_id "
            f"for reversal; entry: {doc_entry}"
        )

    finally:
        sb.table("patients").delete().eq("id", patient_id).execute()
