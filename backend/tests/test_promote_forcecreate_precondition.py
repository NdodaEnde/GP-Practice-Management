"""
Promote force-create precondition fix — bite-proven, both directions,
DB-free.

The defect (caught by the golden-run harness, run #2/#3): the real
Type-C approve passes target_patient_id="" + force_create_patient=True
for every NEW patient (digitisation.py:1203-1299, ambiguity gate forces
it), and `preconditions()` UNCONDITIONALLY emitted
ObjectExists("patients","") -> precondition_failed before any effect ->
every new-patient approval (the wedge's MAIN case) dead.

Premise verified at file:line before the fix: migration 015's
execute_action_promote_document force-create path provably INSERTs the
patients row (`IF v_patient_id IS NULL` branch, reached because the
match block is skipped under p_force_create_patient=TRUE) — so guarding
the precondition is a real fix, not a deferral into a silent
broken-data success.

Non-vacuous BOTH directions:
  * force_create_patient=True  -> NO patients-side ObjectExists/
    BelongsToPractice (the fix: the new-patient path now passes
    preconditions and reaches the effect, which creates the patient).
  * force_create_patient=False -> the patients-side checks ARE present
    (the guard did NOT globally disable a safety precondition; the
    confirmed-match path still rejects a missing patient).
  * document-side ObjectExists intact in BOTH (the guard is surgical —
    it gated only the patients-side block, perturbed nothing else).
  * the count FLIPS with the flag (2 <-> 0), so the test cannot pass
    vacuously against a no-op guard.

DB-free: preconditions() only constructs the Precondition list; no
.check(), no ctx, no Supabase.
"""
import pytest

try:
    from ontology.actions.promote_document import PromoteDocumentToPatientRecord
except Exception as e:  # pragma: no cover - env-dependent
    pytest.skip(f"cannot import action under test ({e})", allow_module_level=True)

_PATIENTS_GATED = {"ObjectExists", "BelongsToPractice"}


def _mk(force_create: bool, target: str):
    return PromoteDocumentToPatientRecord(
        document_id="doc-1", workspace_id="ws-1",
        target_patient_id=target, force_create_patient=force_create,
    )


def _patients_side(action):
    return [p for p in action.preconditions()
            if p.__class__.__name__ in _PATIENTS_GATED
            and getattr(p, "table", None) == "patients"]


def _doc_side(action):
    return [p for p in action.preconditions()
            if p.__class__.__name__ == "ObjectExists"
            and getattr(p, "table", None) == "digitised_documents"]


def test_force_create_skips_patients_side():
    """The fix: force-create no longer asserts an existing patient."""
    a = _mk(force_create=True, target="")
    assert _patients_side(a) == [], (
        "force-create still emits a patients-side existence/tenancy "
        "precondition — the new-patient wedge path is still dead"
    )
    # surgical: the guard perturbed nothing else
    assert len(_doc_side(a)) == 1, "document-side precondition disturbed"


def test_non_force_keeps_patients_side():
    """Non-vacuity: the guard did NOT globally disable the safety
    precondition — the confirmed-match path still enforces it."""
    a = _mk(force_create=False, target="P-123")
    ps = _patients_side(a)
    assert {p.__class__.__name__ for p in ps} == _PATIENTS_GATED, (
        f"confirmed-match path lost its patients-side checks: {ps}"
    )
    assert len(ps) == 2
    assert len(_doc_side(a)) == 1, "document-side precondition disturbed"


def test_guard_flips_with_the_flag_non_vacuous():
    """The count must FLIP with force_create_patient (2 <-> 0). If it
    didn't, both assertions above could pass against a broken/no-op
    guard — this proves the guard genuinely keys off the flag."""
    forced = len(_patients_side(_mk(force_create=True, target="")))
    notf = len(_patients_side(_mk(force_create=False, target="P-123")))
    assert forced == 0 and notf == 2, (forced, notf)
