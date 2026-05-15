"""
SoftDeletePatient — POPIA right-to-erasure, with safety guards.

Sets `patients.deleted_at = now()` and `deletion_reason`. Reversible
within the retention window (by clearing deleted_at).

PR 3 scope decision: BLOCK soft-delete when the patient has active
prescriptions OR pending-validation documents. Clinical safety reading:
a doctor seeing a phantom open prescription with no patient record is
the kind of bug that triggers a malpractice complaint. The reviewer
must resolve those (void the prescriptions, reject the documents) before
deletion. A future PR may add a cascade-delete option for explicit
right-to-erasure flows.

The deleted patient is NOT removed from the validation queue's match
candidates by this action alone — that requires updating
find_match_candidates() to filter deleted_at IS NULL, which lands in
patient_matching.py (PR 3 extraction).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.actions.base import (
    Action,
    CheckResult,
    Effect,
    ExecutorContext,
    Precondition,
)
from app.actions.executor import register_python_reversal
from app.actions.primitives import (
    BelongsToPractice,
    HasPermission,
    NotSoftDeleted,
    ObjectExists,
    RestoreSoftDeleted,
    SoftDelete,
)
from app.actions.registry import register_action


@dataclass
class NoActivePrescriptions:
    """Refuse soft-delete while the patient has any prescription in
    'active' status. The reviewer should void them first."""
    patient_id: str
    name: str = "NoActivePrescriptions"

    def check(self, ctx: ExecutorContext) -> CheckResult:
        res = (
            ctx.supabase.table("prescriptions")
            .select("id", count="exact")
            .eq("patient_id", self.patient_id)
            .eq("status", "active")
            .limit(1)
            .execute()
        )
        count = getattr(res, "count", None)
        if count is None:
            count = len(res.data or [])
        passed = count == 0
        return CheckResult(
            name=self.name,
            passed=passed,
            detail=None if passed else (
                f"patient has {count} active prescription(s); void them before "
                f"soft-deleting"
            ),
        )


@dataclass
class NoPendingValidationDocuments:
    """Refuse soft-delete while the patient is the bound patient on a
    document still in pending_validation."""
    patient_id: str
    name: str = "NoPendingValidationDocuments"

    def check(self, ctx: ExecutorContext) -> CheckResult:
        res = (
            ctx.supabase.table("digitised_documents")
            .select("id", count="exact")
            .eq("patient_id", self.patient_id)
            .eq("status", "pending_validation")
            .limit(1)
            .execute()
        )
        count = getattr(res, "count", None)
        if count is None:
            count = len(res.data or [])
        passed = count == 0
        return CheckResult(
            name=self.name,
            passed=passed,
            detail=None if passed else (
                f"patient has {count} document(s) in pending_validation; "
                f"reject or re-route them before soft-deleting"
            ),
        )


@register_action
@dataclass(eq=False)
class SoftDeletePatient(Action):
    """Soft-delete a patient (POPIA right-to-erasure). Reversible.

    Blocks on:
      - Active prescriptions (void them first).
      - Pending-validation documents (resolve them first).
    """

    __action_name__: str = "SoftDeletePatient"
    __action_version__: int = 1
    __reversible__: bool = True
    __pii_level__: str = "high"

    patient_id: str = ""
    erasure_reason: str = ""
    actor_user_id: str = ""
    actor_email: Optional[str] = None
    practice_id: str = ""
    workspace_id: str = ""

    def preconditions(self) -> List[Precondition]:
        return [
            ObjectExists("patients", self.patient_id),
            BelongsToPractice("patients", self.patient_id, self.workspace_id),
            NotSoftDeleted("patients", self.patient_id),
            NoActivePrescriptions(self.patient_id),
            NoPendingValidationDocuments(self.patient_id),
            HasPermission("patient_admin"),
        ]

    def effects(self) -> List[Effect]:
        return [
            SoftDelete("patients", self.patient_id, object_type="Patient"),
        ]

    def describe_for_user(self) -> str:
        return (
            f"Soft-delete patient {self.patient_id} "
            f"(POPIA erasure, reason: {self.erasure_reason!r}). Reversible."
        )

    def to_audit_parameters(self) -> Dict[str, Any]:
        return {
            "patient_id": self.patient_id,
            "erasure_reason": self.erasure_reason,
            "actor_user_id": self.actor_user_id,
            "practice_id": self.practice_id,
            "workspace_id": self.workspace_id,
        }

    @classmethod
    def from_audit_parameters(cls, params: Dict[str, Any]) -> "SoftDeletePatient":
        return cls(
            patient_id=params["patient_id"],
            erasure_reason=params.get("erasure_reason", ""),
            actor_user_id=params["actor_user_id"],
            practice_id=params["practice_id"],
            workspace_id=params["workspace_id"],
        )


def _build_soft_delete_patient_reversal(original: Dict[str, Any], actor) -> List[Effect]:
    params = original.get("parameters", {}) or {}
    return [
        RestoreSoftDeleted("patients", params["patient_id"], object_type="Patient"),
    ]


register_python_reversal("SoftDeletePatient", _build_soft_delete_patient_reversal)
