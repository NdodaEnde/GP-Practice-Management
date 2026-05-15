"""
VoidPrescription — soft-cancel an active prescription.

The prescription row's status flips from 'active' to 'cancelled' and a
reason string is written to the new `void_reason` column (added by
migration 020). Reversible — clears the void_reason and restores the
prior status from the audit row's snapshot.

CANNOT void a prescription that has already been dispensed — HPCSA:
the pharmacist's dispense event closes the prescription's mutable
state; cancellation after dispense is a separate clinical workflow.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.actions.base import Action, Effect, Precondition
from app.actions.executor import register_python_reversal
from app.actions.primitives import (
    BelongsToPractice,
    HasPermission,
    HasStatus,
    ObjectExists,
    SetMultipleFields,
)
from app.actions.registry import register_action


@register_action
@dataclass(eq=False)
class VoidPrescription(Action):
    """Void an active prescription. Audited + reversible.

    The reason field is stored on the prescription row (queryable) AND
    on the audit row's parameters (regulatory trail). On reversal the
    audit row remains; only the data state restores.
    """

    __action_name__: str = "VoidPrescription"
    __action_version__: int = 1
    __reversible__: bool = True
    __pii_level__: str = "high"

    prescription_id: str = ""
    void_reason: str = ""
    actor_user_id: str = ""
    actor_email: Optional[str] = None
    practice_id: str = ""
    workspace_id: str = ""
    # Captured at construction-time so reversal can restore.
    previous_status: str = "active"

    def preconditions(self) -> List[Precondition]:
        return [
            ObjectExists("prescriptions", self.prescription_id),
            BelongsToPractice(
                "prescriptions", self.prescription_id, self.workspace_id
            ),
            # Status MUST be 'active' — cannot void dispensed or already-cancelled.
            HasStatus(
                "prescriptions",
                self.prescription_id,
                expected_status="active",
            ),
            HasPermission("prescription_management"),
        ]

    def effects(self) -> List[Effect]:
        now_iso = datetime.now(timezone.utc).isoformat()
        return [
            SetMultipleFields(
                table="prescriptions",
                object_id=self.prescription_id,
                columns={
                    "status": "cancelled",
                    "void_reason": self.void_reason,
                    "updated_at": now_iso,
                },
                object_type="Prescription",
            ),
        ]

    def describe_for_user(self) -> str:
        return (
            f"Void prescription {self.prescription_id} "
            f"(reason: {self.void_reason!r}). Reversible."
        )

    def to_audit_parameters(self) -> Dict[str, Any]:
        return {
            "prescription_id": self.prescription_id,
            "void_reason": self.void_reason,
            "actor_user_id": self.actor_user_id,
            "practice_id": self.practice_id,
            "workspace_id": self.workspace_id,
            "previous_status": self.previous_status,
        }

    @classmethod
    def from_audit_parameters(cls, params: Dict[str, Any]) -> "VoidPrescription":
        return cls(
            prescription_id=params["prescription_id"],
            void_reason=params.get("void_reason", ""),
            actor_user_id=params["actor_user_id"],
            practice_id=params["practice_id"],
            workspace_id=params["workspace_id"],
            previous_status=params.get("previous_status", "active"),
        )


# ----------------------------------------------------------------------------
# Reversal builder
# ----------------------------------------------------------------------------
def _build_void_prescription_reversal(original: Dict[str, Any], actor) -> List[Effect]:
    params = original.get("parameters", {}) or {}
    return [
        SetMultipleFields(
            table="prescriptions",
            object_id=params["prescription_id"],
            columns={
                "status": params.get("previous_status") or "active",
                "void_reason": None,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            object_type="Prescription",
        ),
    ]


register_python_reversal("VoidPrescription", _build_void_prescription_reversal)
