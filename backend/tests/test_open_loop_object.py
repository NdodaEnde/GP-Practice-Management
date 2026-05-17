"""
OpenLoop object — the SECOND, independent guard test (Phase 4 PR F).

The closed transition table (test_open_loop_state_machine.py) is the
first guard. This proves the object's `model_validator` is the second,
independent one: it rejects any (state, *_at) tuple the lifecycle could
never legitimately produce, so a bare un-audited field write cannot
construct a valid OpenLoop in an inconsistent state.

Same non-vacuity discipline as the state-machine suite (F-1 rider): the
invalid-rejection half is load-bearing; this file counts its rejection
assertions and asserts the count is non-zero — a suite that only builds
valid objects is the §D.1 false-green relocated and cannot pass.

DB-free: pure Pydantic construction, no Supabase/network.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from ontology.enums.open_loop_enums import LoopKind, LoopUrgency, OpenLoopState
from ontology.objects.open_loop import OpenLoop

NOW = datetime(2026, 5, 17, 9, 0, tzinfo=timezone.utc)
LATER = datetime(2026, 5, 24, 9, 0, tzinfo=timezone.utc)


def _base(**overrides):
    """Minimum valid kwargs for an OPEN loop; overrides tune state/*_at."""
    kw = dict(
        id=uuid4(),
        practice_id="demo-briefing-workspace-001",
        created_at=NOW,
        updated_at=NOW,
        patient_id=uuid4(),
        loop_kind=LoopKind.OTHER,
        state=OpenLoopState.OPEN,
        opening_event_kind="manual",
        expected_closing_event_kind="specialist letter received",
        urgency=LoopUrgency.ROUTINE,
        opened_at=NOW,
    )
    kw.update(overrides)
    return kw


# ---- valid (state, *_at) tuples — every legitimate lifecycle shape ----

def test_valid_states_construct():
    OpenLoop(**_base(state=OpenLoopState.OPEN))
    OpenLoop(**_base(state=OpenLoopState.AWAITING))
    OpenLoop(**_base(state=OpenLoopState.BREACHED, breached_at=LATER))
    OpenLoop(**_base(
        state=OpenLoopState.CLOSED, closed_at=LATER, closed_reason="resolved"
    ))


def test_closed_after_breach_retains_breached_at__explicit_valid_fact():
    """A loop closed late after a breach legitimately carries BOTH
    breached_at and closed_at with state CLOSED — an explicit allowed
    shape, not the absence of a check."""
    OpenLoop(**_base(
        state=OpenLoopState.CLOSED,
        breached_at=LATER,
        closed_at=LATER,
        closed_reason="closed late after breach",
    ))


# ---- THE load-bearing half: inconsistent tuples are REJECTED ----------

INVALID_CASES = [
    ("OPEN + closed_at", dict(state=OpenLoopState.OPEN, closed_at=LATER)),
    ("OPEN + closed_reason", dict(state=OpenLoopState.OPEN, closed_reason="x")),
    ("OPEN + breached_at", dict(state=OpenLoopState.OPEN, breached_at=LATER)),
    ("AWAITING + closed_at", dict(state=OpenLoopState.AWAITING, closed_at=LATER)),
    ("AWAITING + breached_at", dict(state=OpenLoopState.AWAITING, breached_at=LATER)),
    ("BREACHED w/o breached_at", dict(state=OpenLoopState.BREACHED)),
    ("BREACHED + closed_at", dict(
        state=OpenLoopState.BREACHED, breached_at=LATER, closed_at=LATER,
        closed_reason="x")),
    ("CLOSED w/o closed_at", dict(
        state=OpenLoopState.CLOSED, closed_reason="x")),
    ("CLOSED w/o closed_reason", dict(
        state=OpenLoopState.CLOSED, closed_at=LATER)),
]


@pytest.mark.parametrize("label,override", INVALID_CASES, ids=[c[0] for c in INVALID_CASES])
def test_inconsistent_state_at_tuple_is_rejected(label, override):
    """Each lifecycle-impossible (state, *_at) tuple must raise — this is
    the validator being the independent second guard against an
    un-audited bare write."""
    with pytest.raises(ValidationError):
        OpenLoop(**_base(**override))


def test_rejection_suite_is_non_vacuous():
    """F-1 non-vacuity rider, object layer: prove the invalid-rejection
    half actually ran over every invalid case (a valid-only suite would
    leave this at zero and fail)."""
    rejections = 0
    for _label, override in INVALID_CASES:
        with pytest.raises(ValidationError):
            OpenLoop(**_base(**override))
        rejections += 1
    assert rejections > 0
    assert rejections == len(INVALID_CASES)


def test_bare_write_to_closed_without_closed_at_cannot_construct():
    """The explicit 'no un-audited bare write' fact: setting state=CLOSED
    without the closing fields (what a raw UPDATE bypassing the audited
    action would do) cannot produce a valid object."""
    with pytest.raises(ValidationError):
        OpenLoop(**_base(state=OpenLoopState.CLOSED))


def test_object_is_registered_and_conforms_to_template():
    """OpenLoop is wired the same way as Patient/Document/Consultation."""
    from ontology import OpenLoop as ExportedOpenLoop
    assert ExportedOpenLoop is OpenLoop
    assert OpenLoop.__object_type_name__ == "OpenLoop"
    assert OpenLoop.__fhir_resource__ is None  # stated, not faked
    assert OpenLoop.__audited__ is True
    # inherits the five system fields from OntologyObject
    for f in ("id", "practice_id", "created_at", "updated_at", "deleted_at"):
        assert f in OpenLoop.model_fields
    # the Patient->OpenLoop link is registered
    from ontology.links.registry import find_link
    link = find_link("Patient", "OpenLoop", "has_open_loop")
    assert link is not None and link.inverse_name == "open_loop_for_patient"
