"""
OpenLoopBreach — AWAITING → BREACHED. Phase 4 PR F.

Mirrors SoftDeletePatient. HasStatus pins the legal source (AWAITING);
the effect calls the closed table (second guard) and sets breached_at.
Reversal restores the before-image (BREACHED → AWAITING, breached_at
cleared to its recorded prior). Authorization deferred to PR G (F-4).
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
class OpenLoopBreach(Action):
    """Breach a loop AWAITING → BREACHED (the deadline passed without the
    closing event). NOT terminal — a breached loop can still be closed
    late. Reversible."""

    __action_name__: str = "OpenLoopBreach"
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
                expected_status=OpenLoopState.AWAITING.value,
                column="state",
            ),
        ]

    def effects(self) -> List[Effect]:
        return [LoopTransitionEffect(self.loop_id, OpenLoopEvent.BREACH)]

    def describe_for_user(self) -> str:
        return f"Breach loop {self.loop_id} (AWAITING → BREACHED). Reversible."

    def to_audit_parameters(self) -> Dict[str, Any]:
        return {
            "loop_id": self.loop_id,
            "actor_user_id": self.actor_user_id,
            "practice_id": self.practice_id,
            "workspace_id": self.workspace_id,
        }

    @classmethod
    def from_audit_parameters(cls, params: Dict[str, Any]) -> "OpenLoopBreach":
        return cls(
            loop_id=params["loop_id"],
            actor_user_id=params.get("actor_user_id", ""),
            practice_id=params.get("practice_id", ""),
            workspace_id=params.get("workspace_id", ""),
        )


register_python_reversal("OpenLoopBreach", loop_transition_reversal)
