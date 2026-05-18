"""
Piece 2 — the bounded reversal-claim honesty fix, bite-proven.

`PromoteDocumentToPatientRecord` declared `__reversible__ = True` while
functional promote-reversal was never built (the abandoned "PR 2"). That
flag is what `executor.reverse()` consults: True lets a reverse attempt
past the precondition into a pathway that does not exist; False makes it
return precondition_failed — the honest-refusal contract
`reprocess_document.py` documents and uses.

This test is non-vacuous BY CONTRAST: it does not merely assert
`promote.__reversible__ is False` (a constant against itself). It asserts
the attribute genuinely varies across actions (a legitimately-reversible
action still reads True; the established honest-False exemplar reads
False) and that promote — read through the REGISTRY the executor
consults, not just the class literal — is on the honest side. Revert the
fix to True and this flips.

DB-free: imports action classes + the registry only.
"""
import pytest

try:
    from app.actions.registry import get_action_class
    from ontology.actions.promote_document import PromoteDocumentToPatientRecord
    from ontology.actions.reprocess_document import ReprocessDocument
    from ontology.actions.void_prescription import VoidPrescription
except Exception as e:  # pragma: no cover - env-dependent
    pytest.skip(f"cannot import actions under test ({e})", allow_module_level=True)


def test_promote_is_not_declared_reversible():
    """The fix: promote no longer asserts a reversibility it lacks."""
    assert PromoteDocumentToPatientRecord.__reversible__ is False


def test_registry_consumed_value_is_honest():
    """Tie the flag to the consumption path: executor.reverse() resolves
    the action via the registry, not the class literal. The registered
    class must carry the honest value."""
    cls = get_action_class("PromoteDocumentToPatientRecord")
    assert cls.__reversible__ is False


def test_non_vacuous_contrast():
    """The attribute genuinely varies — so the assertions above are not a
    constant asserting itself. A legitimately-reversible action still
    reads True; the established honest-False exemplar reads False; promote
    now matches the honest exemplar, not the reversible one."""
    assert VoidPrescription.__reversible__ is True, (
        "contrast broken: expected a legitimately-reversible action to "
        "still read True — without this the promote check is vacuous"
    )
    assert ReprocessDocument.__reversible__ is False
    assert (
        PromoteDocumentToPatientRecord.__reversible__
        == ReprocessDocument.__reversible__
        != VoidPrescription.__reversible__
    )
