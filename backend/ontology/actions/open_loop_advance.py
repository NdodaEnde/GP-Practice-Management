"""
OpenLoopAdvance — OPEN → AWAITING. Phase 4 PR F.

Mirrors SoftDeletePatient (single-table mutation, @register_action,
Python reversal). The HasStatus precondition pins the legal source
state; the effect calls the closed transition table (the SECOND
structural guard). Reversal restores the recorded before-image.
Authorization deferred to PR G (F-4) — see open_loop_open.py docstring.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.actions.base import Action, Effect, Precondition
from app.actions.executor import register_python_reversal
from app.actions.primitives import BelongsToPractice, HasStatus, NotSoftDeleted, ObjectExists
from app.actions.registry import register_action
from ontology.actions._open_loop_transition import (
    LoopTransitionEffect,
    loop_transition_reversal,
)
from ontology.enums.open_loop_enums import OpenLoopEvent, OpenLoopState


@register_action
@dataclass(eq=False)
class OpenLoopAdvance(Action):
    """Advance a loop OPEN → AWAITING (its expected closing event is now
    pending; the deadline is live). Reversible."""

    __action_name__: str = "OpenLoopAdvance"
    __action_version__: int = 1
    __reversible__: bool = True
    __pii_level__: str = "low"

    loop_id: str = ""
    actor_user_id: str = ""
    actor_email: Optional[str] = None
    practice_id: str = ""
    workspace_id: str = ""

    def preconditions(self) -> List[Precondition]:
        return [
            ObjectExists("open_loops", self.loop_id),
            BelongsToPractice("open_loops", self.loop_id, self.workspace_id),
            NotSoftDeleted("open_loops", self.loop_id),
            HasStatus(
                table="open_loops",
                object_id=self.loop_id,
                expected_status=OpenLoopState.OPEN.value,
                column="state",
            ),
        ]

    def effects(self) -> List[Effect]:
        return [LoopTransitionEffect(self.loop_id, OpenLoopEvent.ADVANCE)]

    def describe_for_user(self) -> str:
        return f"Advance loop {self.loop_id} (OPEN → AWAITING). Reversible."

    def to_audit_parameters(self) -> Dict[str, Any]:
        return {
            "loop_id": self.loop_id,
            "actor_user_id": self.actor_user_id,
            "practice_id": self.practice_id,
            "workspace_id": self.workspace_id,
        }

    @classmethod
    def from_audit_parameters(cls, params: Dict[str, Any]) -> "OpenLoopAdvance":
        return cls(
            loop_id=params["loop_id"],
            actor_user_id=params.get("actor_user_id", ""),
            practice_id=params.get("practice_id", ""),
            workspace_id=params.get("workspace_id", ""),
        )


register_python_reversal("OpenLoopAdvance", loop_transition_reversal)
