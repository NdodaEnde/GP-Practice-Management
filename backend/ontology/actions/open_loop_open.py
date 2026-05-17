"""
OpenLoopOpen — open a tracked clinical loop (born OPEN). Phase 4 PR F.

Mirrors the SoftDeletePatient analog (single-table mutation,
@register_action, Python-side reversal). Reversal soft-deletes the
created loop (the SoftDeletePatient inverse pattern, applied to a
create).

AUTHORIZATION DEFERRED TO PR G (F-4, mechanism-vs-policy cut — recorded,
not skipped): this action is the *mechanism* by which a loop is opened.
*Who* may open one — the capability gate — belongs with the *policy*
layer (the PR-G detector/endpoint that invokes it). PR F deliberately
does NOT attach a guessed `HasPermission(...)`: minting/guessing a
capability string here would be a fake-property (a gate that doesn't
match any real entitlement). The structural preconditions (the patient
exists and belongs to the workspace) ARE enforced; the authorization
precondition is a named PR-G addition, not a silent omission. F-1=B:
substrate only, no detector, no real instance — proven non-vacuous on
fabricated input, first real loop is PR G's.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.actions.base import Action, Effect, Precondition
from app.actions.executor import register_python_reversal
from app.actions.primitives import BelongsToPractice, ObjectExists
from app.actions.registry import register_action
from ontology.actions._open_loop_transition import CreateLoopEffect, loop_open_reversal
from ontology.enums.open_loop_enums import LoopKind, LoopUrgency, OpenLoopState


@register_action
@dataclass(eq=False)
class OpenLoopOpen(Action):
    """Open a new OpenLoop for a patient. The loop is born OPEN; it is
    advanced/closed/breached by the sibling audited actions. Reversible
    (soft-deletes the created loop)."""

    __action_name__: str = "OpenLoopOpen"
    __action_version__: int = 1
    __reversible__: bool = True
    __pii_level__: str = "low"

    loop_id: str = ""
    patient_id: str = ""
    loop_kind: str = LoopKind.OTHER.value
    opening_event_kind: str = "manual"
    expected_closing_event_kind: str = ""
    urgency: str = LoopUrgency.ROUTINE.value
    deadline_at: Optional[str] = None
    actor_user_id: str = ""
    actor_email: Optional[str] = None
    practice_id: str = ""
    workspace_id: str = ""

    def __post_init__(self) -> None:
        if not self.loop_id:
            self.loop_id = str(uuid4())

    def preconditions(self) -> List[Precondition]:
        # Structural guards only. Authorization is a named PR-G addition
        # (F-4 mechanism-vs-policy — see module docstring).
        return [
            ObjectExists("patients", self.patient_id),
            BelongsToPractice("patients", self.patient_id, self.workspace_id),
        ]

    def _row(self) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        return {
            "id": self.loop_id,
            "workspace_id": self.workspace_id,
            "patient_id": self.patient_id,
            "loop_kind": self.loop_kind,
            "state": OpenLoopState.OPEN.value,
            "opening_event_kind": self.opening_event_kind,
            "opening_event_ref": None,
            "expected_closing_event_kind": self.expected_closing_event_kind,
            "urgency": self.urgency,
            "deadline_at": self.deadline_at,
            "opened_at": now,
            "closed_at": None,
            "closed_reason": None,
            "breached_at": None,
        }

    def effects(self) -> List[Effect]:
        return [CreateLoopEffect(self.loop_id, self._row())]

    def describe_for_user(self) -> str:
        return (
            f"Open a {self.loop_kind!r} loop for patient {self.patient_id} "
            f"(closes when: {self.expected_closing_event_kind!r}). Reversible."
        )

    def to_audit_parameters(self) -> Dict[str, Any]:
        return {
            "loop_id": self.loop_id,
            "patient_id": self.patient_id,
            "loop_kind": self.loop_kind,
            "opening_event_kind": self.opening_event_kind,
            "expected_closing_event_kind": self.expected_closing_event_kind,
            "urgency": self.urgency,
            "deadline_at": self.deadline_at,
            "actor_user_id": self.actor_user_id,
            "practice_id": self.practice_id,
            "workspace_id": self.workspace_id,
        }

    @classmethod
    def from_audit_parameters(cls, params: Dict[str, Any]) -> "OpenLoopOpen":
        return cls(
            loop_id=params["loop_id"],
            patient_id=params["patient_id"],
            loop_kind=params.get("loop_kind", LoopKind.OTHER.value),
            opening_event_kind=params.get("opening_event_kind", "manual"),
            expected_closing_event_kind=params.get("expected_closing_event_kind", ""),
            urgency=params.get("urgency", LoopUrgency.ROUTINE.value),
            deadline_at=params.get("deadline_at"),
            actor_user_id=params.get("actor_user_id", ""),
            practice_id=params.get("practice_id", ""),
            workspace_id=params.get("workspace_id", ""),
        )


register_python_reversal("OpenLoopOpen", loop_open_reversal)
