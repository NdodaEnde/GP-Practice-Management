"""
ReassignDocument — re-point a single document's structured data from
one patient to another. PL/pgSQL RPC-backed for atomicity and mutual
exclusion (FOR UPDATE NOWAIT on the document row).

Used when a reviewer realises a document was approved into the wrong
patient. Without ReassignDocument the only recovery would be: reverse
the original promotion (deleting all the structured data), then
re-promote against the correct patient. That works but loses any
post-promotion edits to the structured data. Reassigning preserves
edits and re-points by reference instead.

Reversible — every re-pointed row's `previous_patient_id` is captured
on the forward RPC's affected_objects, so reversal sets each one back.
"""

from __future__ import annotations

from dataclasses import dataclass
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
    HasPermission,
    NotSoftDeleted,
    ObjectExists,
    StatusOneOf,
    _classify_rpc_error,
)
from app.actions.registry import register_action


# Reassignment is unsafe while the doc is mid-processing or already
# rejected. Same shape as ReprocessDocument's allow-list, with rejected
# included (you might reassign a rejected doc to mark it as belonging
# to a different patient before re-processing).
_REASSIGNABLE_FROM = ["parsed", "pending_validation", "validated", "error", "rejected"]


@dataclass
class ReassignDocumentViaRpc:
    """Effect: call execute_action_reassign_document RPC."""
    document_id: str
    new_patient_id: str
    workspace_id: str
    reason: Optional[str] = None
    actor_email: Optional[str] = None
    name: str = "ReassignDocumentViaRpc"

    def plan(self, ctx: ExecutorContext) -> EffectDescriptor:
        return EffectDescriptor(
            name=self.name,
            summary=(
                f"would re-point document {self.document_id} and all "
                f"its child rows to patient {self.new_patient_id}"
            ),
            will_affect=[
                {"type": "Document", "id": self.document_id, "op": "updated"},
                {"type": "Patient",  "id": self.new_patient_id,  "op": "linked"},
            ],
        )

    def apply(self, ctx: ExecutorContext) -> EffectResult:
        try:
            response = ctx.supabase.rpc(
                "execute_action_reassign_document",
                {
                    "p_document_id":   self.document_id,
                    "p_workspace_id":  self.workspace_id,
                    "p_new_patient_id": self.new_patient_id,
                    "p_reason":        self.reason,
                    "p_created_by":    self.actor_email or "reassigner",
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
                    message=f"unexpected reassign RPC payload: {type(payload).__name__}",
                    context={"payload": str(payload)[:500]},
                ),
            )

        affected: List[Dict[str, Any]] = payload.get("affected_objects") or []
        for entry in affected:
            ctx.audit_row_in_progress.setdefault("affected_objects", []).append(entry)

        return EffectResult(
            name=self.name, succeeded=True, affected=affected,
            detail=(
                f"reassigned via RPC: counts={payload.get('counts')}, "
                f"previous_patient_id={payload.get('previous_patient_id')}"
            ),
        )


@register_action
@dataclass(eq=False)
class ReassignDocument(Action):
    """Reassign a document and its structured data to a different patient.
    Audited + reversible via PL/pgSQL reverse RPC."""

    __action_name__: str = "ReassignDocument"
    __action_version__: int = 1
    __reversible__: bool = True
    __pii_level__: str = "high"

    document_id: str = ""
    new_patient_id: str = ""
    reason: str = ""
    actor_user_id: str = ""
    actor_email: Optional[str] = None
    practice_id: str = ""
    workspace_id: str = ""

    def preconditions(self) -> List[Precondition]:
        return [
            ObjectExists("digitised_documents", self.document_id),
            BelongsToPractice(
                "digitised_documents", self.document_id, self.workspace_id
            ),
            StatusOneOf(
                "digitised_documents", self.document_id, _REASSIGNABLE_FROM
            ),
            ObjectExists("patients", self.new_patient_id),
            BelongsToPractice("patients", self.new_patient_id, self.workspace_id),
            NotSoftDeleted("patients", self.new_patient_id),
            HasPermission("patient_admin"),
        ]

    def effects(self) -> List[Effect]:
        return [
            ReassignDocumentViaRpc(
                document_id=self.document_id,
                new_patient_id=self.new_patient_id,
                workspace_id=self.workspace_id,
                reason=self.reason,
                actor_email=self.actor_email,
            ),
        ]

    def describe_for_user(self) -> str:
        return (
            f"Reassign document {self.document_id} to patient {self.new_patient_id} "
            f"(reason: {self.reason!r}). Reversible."
        )

    def to_audit_parameters(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "new_patient_id": self.new_patient_id,
            "reason": self.reason,
            "actor_user_id": self.actor_user_id,
            "practice_id": self.practice_id,
            "workspace_id": self.workspace_id,
        }

    @classmethod
    def from_audit_parameters(cls, params: Dict[str, Any]) -> "ReassignDocument":
        return cls(
            document_id=params["document_id"],
            new_patient_id=params["new_patient_id"],
            reason=params.get("reason", ""),
            actor_user_id=params["actor_user_id"],
            practice_id=params["practice_id"],
            workspace_id=params["workspace_id"],
        )
