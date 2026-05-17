"""
OpenLoop — the fourth ontology object (Phase 4 PR F).

Conforms to the verified `OntologyObject` / `Prop` template
(`ontology/base.py`): inherits the five system fields (id, practice_id,
created_at, updated_at, deleted_at — practice_id is the ontology-level
tenancy ref; the DB `open_loops.workspace_id` is the persistence-level
tenancy column the RLS/PR-5-ratchet operate on, the established Patient
split), declares ClassVar metadata, and declares domain properties via
`Prop(...)`.

F-1 = option B (LOCKED): this is the SUBSTRATE + state machine only.
There is NO loop instance, NO detector (F-4: detectors are PR G), NO
real corpus exercise. The object is built and its (state, *_at)
invariant proven non-vacuous on fabricated input; the first real
stateful loop is PR G's. The honest claim is "the state machine was
shown to reject what it must reject", never "exercised on a real loop".

The state machine itself is the closed transition table in
`ontology.objects.open_loop_state` (built and proven to bite BEFORE this
object — the locked build order). This object's `model_validator` is the
SECOND, independent guard: it rejects any (state, *_at) tuple that the
lifecycle could never legitimately produce, so an un-audited bare field
write cannot construct a valid OpenLoop in an inconsistent state. State
is only ever moved by an audited action (PR F §4) calling
`apply_transition`; this validator makes the audit trail structural, not
optional.
"""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar, Optional
from uuid import UUID

from pydantic import model_validator

from ontology.base import OntologyObject, PIILevel, Prop, SearchBehaviour
from ontology.enums.open_loop_enums import LoopKind, LoopUrgency, OpenLoopState


class OpenLoop(OntologyObject):
    """A tracked clinical loop: an opening event, an expected closing
    event, a deadline, an urgency, and a lifecycle state. CLOSED is
    terminal; BREACHED can still be closed late."""

    __object_type_name__: ClassVar[str] = "OpenLoop"
    __display_template__: ClassVar[str] = (
        "OpenLoop {loop_kind} for {patient_id} ({state})"
    )
    # No clean FHIR analog for an internal proactive-loop tracker. Stated
    # honestly as None — NOT mapped to an ill-fitting resource to look
    # complete (the §C/§E "don't fake what isn't there" discipline).
    __fhir_resource__: ClassVar[Optional[str]] = None
    # LOW: the object holds a patient *reference* + categorical/lifecycle
    # fields + a free-text close reason; no direct identifiers (name,
    # dob, ID number) live here. patient_id itself is MEDIUM (it
    # identifies which patient a loop concerns).
    __pii_level__: ClassVar[PIILevel] = PIILevel.LOW
    __audited__: ClassVar[bool] = True

    patient_id: UUID = Prop(
        pii=PIILevel.MEDIUM,
        search=SearchBehaviour.FACETED,
        display_label="Patient",
        description="The patient this loop concerns.",
        link_to="Patient",
        link_cardinality="one",
        immutable_after_create=True,
    )
    loop_kind: LoopKind = Prop(
        pii=PIILevel.LOW,
        search=SearchBehaviour.FACETED,
        display_label="Loop kind",
        description="Taxonomy discriminator. F-3: PR F seeds only "
                    "honestly-backed kinds; the taxonomy is PR G's.",
        immutable_after_create=True,
    )
    state: OpenLoopState = Prop(
        pii=PIILevel.LOW,
        search=SearchBehaviour.FACETED,
        display_label="State",
        description="Lifecycle state. Only ever moved by an audited "
                    "action via the closed transition table; this "
                    "object's model_validator rejects an inconsistent "
                    "(state, *_at) tuple.",
    )
    opening_event_kind: str = Prop(
        pii=PIILevel.LOW,
        search=SearchBehaviour.NONE,
        display_label="Opened by",
        description="What opened this loop. PR F substrate has no "
                    "detector (F-4: PR G); the only honest value here is "
                    "'manual'. PR G's detectors set richer kinds.",
        immutable_after_create=True,
    )
    opening_event_ref: Optional[str] = Prop(
        default=None,
        pii=PIILevel.LOW,
        description="Optional reference to the opening event (e.g. a "
                    "consultation id once PR G's detectors exist). "
                    "Nullable in PR F — no detector populates it yet.",
    )
    expected_closing_event_kind: str = Prop(
        pii=PIILevel.LOW,
        search=SearchBehaviour.NONE,
        display_label="Closes when",
        description="A human-readable description of the event that "
                    "would close this loop (e.g. 'specialist letter "
                    "received'). Descriptive in PR F.",
    )
    urgency: LoopUrgency = Prop(
        default=LoopUrgency.ROUTINE,
        pii=PIILevel.LOW,
        search=SearchBehaviour.FACETED,
        display_label="Urgency",
        description="How time-critical a breach is.",
    )
    deadline_at: Optional[datetime] = Prop(
        default=None,
        pii=PIILevel.LOW,
        description="When the loop breaches if not closed. Nullable: a "
                    "loop may have no hard deadline.",
    )
    opened_at: datetime = Prop(
        pii=PIILevel.LOW,
        description="When the loop was opened (born OPEN). Always set.",
        immutable_after_create=True,
    )
    closed_at: Optional[datetime] = Prop(
        default=None,
        pii=PIILevel.LOW,
        description="Set iff state == CLOSED.",
    )
    closed_reason: Optional[str] = Prop(
        default=None,
        pii=PIILevel.LOW,
        description="Why the loop was closed. Set iff state == CLOSED.",
    )
    breached_at: Optional[datetime] = Prop(
        default=None,
        pii=PIILevel.LOW,
        description="When the deadline was breached. Set while BREACHED "
                    "and retained through a late BREACHED→CLOSED.",
    )

    @model_validator(mode="after")
    def _state_at_consistency(self) -> "OpenLoop":
        """The independent second guard (the first is the closed
        transition table). Rejects any (state, *_at) tuple the lifecycle
        could never legitimately produce, so a bare un-audited write
        cannot construct a valid OpenLoop in an inconsistent state.

        Decidable and exhaustive over the four states:
          OPEN/AWAITING : not closed, not breached
          BREACHED      : breached_at set, not closed
          CLOSED        : closed_at + closed_reason set
                          (breached_at MAY be set — a late BREACHED→CLOSED)
        """
        s = self.state
        if s in (OpenLoopState.OPEN, OpenLoopState.AWAITING):
            if self.closed_at is not None or self.closed_reason is not None:
                raise ValueError(f"{s.value!r} loop must not carry closed_at/closed_reason")
            if self.breached_at is not None:
                raise ValueError(f"{s.value!r} loop must not carry breached_at")
        elif s is OpenLoopState.BREACHED:
            if self.breached_at is None:
                raise ValueError("BREACHED loop must carry breached_at")
            if self.closed_at is not None or self.closed_reason is not None:
                raise ValueError("BREACHED loop must not carry closed_at/closed_reason")
        elif s is OpenLoopState.CLOSED:
            if self.closed_at is None or self.closed_reason is None:
                raise ValueError("CLOSED loop must carry closed_at and closed_reason")
            # breached_at intentionally unconstrained here: a loop closed
            # late after a breach legitimately retains breached_at.
        else:  # pragma: no cover - OpenLoopState is a closed enum
            raise ValueError(f"unknown OpenLoop state {s!r}")
        return self
