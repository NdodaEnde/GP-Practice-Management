"""
MergePatient — consolidate two patient records into one.

The highest blast-radius mutation in the system. Re-points every child
row from source_patient_id to target_patient_id across 10 tables, then
soft-deletes the source with `merged_into_patient_id = target` so the
audit trail makes the consolidation explicit.

RPC-backed for atomicity + mutual exclusion (FOR UPDATE NOWAIT on both
patient rows). Reversible via the reverse RPC, which restores every
re-pointed row and un-soft-deletes the source.

Requires fresh user confirmation (ConfirmationFresh, 5-minute window —
TIGHTER than promote-document's 15 because the blast radius is bigger).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.actions.base import (
    Action,
    Effect,
    EffectDescriptor,
    EffectResult,
    ErrorDetail,
    ExecutorContext,
    Precondition,
)
from app.actions.primitives import (
    BelongsToPractice,
    ConfirmationActorMatches,
    ConfirmationFresh,
    HasPermission,
    NotSoftDeleted,
    ObjectExists,
    _classify_rpc_error,
)
from app.actions.registry import register_action
from datetime import timedelta


@dataclass(frozen=True)
class MergeConfirmation:
    """Structured user confirmation for a patient merge.

    Captured at the moment a reviewer clicks 'yes, merge these two'.
    The action's ConfirmationFresh precondition rejects evidence older
    than 5 minutes — clicks can't be replayed across coffee breaks.
    """
    confirmed_by_user_id: str
    confirmed_at: datetime
    survivor_choice_evidence: str = ""  # free-text: why this is the survivor

    def to_dict(self) -> Dict[str, Any]:
        return {
            "confirmed_by_user_id": self.confirmed_by_user_id,
            "confirmed_at": self.confirmed_at.isoformat() if self.confirmed_at else None,
            "survivor_choice_evidence": self.survivor_choice_evidence,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MergeConfirmation":
        ts = d.get("confirmed_at")
        when = datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else datetime.now(timezone.utc)
        return cls(
            confirmed_by_user_id=d["confirmed_by_user_id"],
            confirmed_at=when,
            survivor_choice_evidence=d.get("survivor_choice_evidence", ""),
        )


@dataclass
class MergePatientViaRpc:
    """Effect: call execute_action_merge_patient RPC."""
    source_patient_id: str
    target_patient_id: str
    workspace_id: str
    merge_reason: str
    actor_email: Optional[str] = None
    name: str = "MergePatientViaRpc"

    def plan(self, ctx: ExecutorContext) -> EffectDescriptor:
        return EffectDescriptor(
            name=self.name,
            summary=(
                f"would consolidate patient {self.source_patient_id} into "
                f"{self.target_patient_id} (re-point all child rows; soft-delete source)"
            ),
            will_affect=[
                {"type": "Patient", "id": self.source_patient_id, "op": "soft_deleted"},
                {"type": "Patient", "id": self.target_patient_id, "op": "linked"},
            ],
        )

    def apply(self, ctx: ExecutorContext) -> EffectResult:
        try:
            response = ctx.supabase.rpc(
                "execute_action_merge_patient",
                {
                    "p_source_patient_id": self.source_patient_id,
                    "p_target_patient_id": self.target_patient_id,
                    "p_workspace_id":      self.workspace_id,
                    "p_merge_reason":      self.merge_reason,
                    "p_created_by":        self.actor_email or "merger",
                },
            ).execute()
        except Exception as exc:  # noqa: BLE001
            return EffectResult(
                name=self.name, succeeded=False,
                error=_classify_rpc_error(exc),
            )

        payload = response.data if hasattr(response, "data") else response
        if not isinstance(payload, dict):
            return EffectResult(
                name=self.name, succeeded=False,
                error=ErrorDetail(
                    code="effect_failed",
                    message=f"unexpected merge RPC payload: {type(payload).__name__}",
                    context={"payload": str(payload)[:500]},
                ),
            )

        affected: List[Dict[str, Any]] = payload.get("affected_objects") or []
        for entry in affected:
            ctx.audit_row_in_progress.setdefault("affected_objects", []).append(entry)

        return EffectResult(
            name=self.name, succeeded=True, affected=affected,
            detail=(
                f"merged via RPC: source={self.source_patient_id} → "
                f"target={self.target_patient_id}, counts={payload.get('counts')}"
            ),
        )


@register_action
@dataclass(eq=False)
class MergePatient(Action):
    """Consolidate two patient records into one. Highest blast radius.

    Requires fresh user confirmation (5-minute window). Audited + reversible.
    """

    __action_name__: str = "MergePatient"
    __action_version__: int = 1
    __reversible__: bool = True
    __pii_level__: str = "high"

    source_patient_id: str = ""
    target_patient_id: str = ""
    merge_reason: str = ""
    confirmation: Optional[MergeConfirmation] = None
    actor_user_id: str = ""
    actor_email: Optional[str] = None
    practice_id: str = ""
    workspace_id: str = ""

    def preconditions(self) -> List[Precondition]:
        return [
            ObjectExists("patients", self.source_patient_id),
            BelongsToPractice("patients", self.source_patient_id, self.workspace_id),
            NotSoftDeleted("patients", self.source_patient_id),
            ObjectExists("patients", self.target_patient_id),
            BelongsToPractice("patients", self.target_patient_id, self.workspace_id),
            NotSoftDeleted("patients", self.target_patient_id),
            ConfirmationActorMatches(
                confirmation_user_id=(
                    self.confirmation.confirmed_by_user_id if self.confirmation else ""
                ),
                actor_user_id=self.actor_user_id,
            ),
            ConfirmationFresh(
                confirmed_at=(
                    self.confirmation.confirmed_at if self.confirmation
                    else datetime.now(timezone.utc)
                ),
                window=timedelta(minutes=5),  # tighter than promote-document
            ),
            HasPermission("patient_admin"),
        ]

    def effects(self) -> List[Effect]:
        return [
            MergePatientViaRpc(
                source_patient_id=self.source_patient_id,
                target_patient_id=self.target_patient_id,
                workspace_id=self.workspace_id,
                merge_reason=self.merge_reason,
                actor_email=self.actor_email,
            ),
        ]

    def describe_for_user(self) -> str:
        return (
            f"Consolidate patient {self.source_patient_id} into "
            f"{self.target_patient_id} (reason: {self.merge_reason!r}). "
            f"Re-points all child rows; soft-deletes source. Reversible."
        )

    def to_audit_parameters(self) -> Dict[str, Any]:
        return {
            "source_patient_id": self.source_patient_id,
            "target_patient_id": self.target_patient_id,
            "merge_reason": self.merge_reason,
            "confirmation": self.confirmation.to_dict() if self.confirmation else None,
            "actor_user_id": self.actor_user_id,
            "practice_id": self.practice_id,
            "workspace_id": self.workspace_id,
        }

    @classmethod
    def from_audit_parameters(cls, params: Dict[str, Any]) -> "MergePatient":
        confirmation = (
            MergeConfirmation.from_dict(params["confirmation"])
            if params.get("confirmation") else None
        )
        return cls(
            source_patient_id=params["source_patient_id"],
            target_patient_id=params["target_patient_id"],
            merge_reason=params.get("merge_reason", ""),
            confirmation=confirmation,
            actor_user_id=params["actor_user_id"],
            practice_id=params["practice_id"],
            workspace_id=params["workspace_id"],
        )
