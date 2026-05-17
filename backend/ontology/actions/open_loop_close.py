"""
OpenLoopClose — (AWAITING | BREACHED) → CLOSED. Phase 4 PR F.

Mirrors SoftDeletePatient. CLOSE is legal from TWO source states, so the
precondition is StatusOneOf (the verified multi-state primitive), not
HasStatus. The effect calls the closed table (second guard) and sets
closed_at + closed_reason. Reversal restores the before-image — correct
regardless of which path (AWAITING→CLOSED vs BREACHED→CLOSED) because it
restores the literal recorded prior values. Authorization deferred to
PR G (F-4).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.actions.base import Action, Effect, Precondition
from app.actions.executor import register_python_reversal
from app.actions.primitives import (
    BelongsToPractice,
    NotSoftDeleted,
    ObjectExists,
    StatusOneOf,
)
from app.actions.registry import register_action
from ontology.actions._open_loop_transition import (
    LoopTransitionEffect,
    loop_transition_reversal,
)
from ontology.enums.open_loop_enums import OpenLoopEvent, OpenLoopState


@register_action
@dataclass(eq=False)
class OpenLoopClose(Action):
    """Close a loop (AWAITING | BREACHED) → CLOSED (terminal). A breached
    loop closed here is a legitimate late resolution. Reversible (to its
    recorded prior state — AWAITING or BREACHED — exactly)."""

    __action_name__: str = "OpenLoopClose"
    __action_version__: int = 1
    __reversible__: bool = True
    __pii_level__: str = "low"

    loop_id: str = ""
    closed_reason: str = ""
    actor_user_id: str = ""
    actor_email: Optional[str] = None
    practice_id: str = ""
    workspace_id: str = ""

    def preconditions(self) -> List[Precondition]:
        return [
            ObjectExists("open_loops", self.loop_id),
            BelongsToPractice("open_loops", self.loop_id, self.workspace_id),
            NotSoftDeleted("open_loops", self.loop_id),
            StatusOneOf(
                table="open_loops",
                object_id=self.loop_id,
                allowed=[
                    OpenLoopState.AWAITING.value,
                    OpenLoopState.BREACHED.value,
                ],
                column="state",
            ),
        ]

    def effects(self) -> List[Effect]:
        return [
            LoopTransitionEffect(
                self.loop_id, OpenLoopEvent.CLOSE, closed_reason=self.closed_reason
            )
        ]

    def describe_for_user(self) -> str:
        return (
            f"Close loop {self.loop_id} (→ CLOSED, reason: "
            f"{self.closed_reason!r}). Reversible."
        )

    def to_audit_parameters(self) -> Dict[str, Any]:
        return {
            "loop_id": self.loop_id,
            "closed_reason": self.closed_reason,
            "actor_user_id": self.actor_user_id,
            "practice_id": self.practice_id,
            "workspace_id": self.workspace_id,
        }

    @classmethod
    def from_audit_parameters(cls, params: Dict[str, Any]) -> "OpenLoopClose":
        return cls(
            loop_id=params["loop_id"],
            closed_reason=params.get("closed_reason", ""),
            actor_user_id=params.get("actor_user_id", ""),
            practice_id=params.get("practice_id", ""),
            workspace_id=params.get("workspace_id", ""),
        )


register_python_reversal("OpenLoopClose", loop_transition_reversal)
