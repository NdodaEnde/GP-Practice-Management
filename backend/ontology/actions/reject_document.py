"""
RejectDocument — the reject path through the ActionExecutor.

Replaces the direct `digitised_documents.update` + `_write_edit_log(action='reject')`
combo previously in `digitisation.py:reject_validation`. After PR 3 lands,
ALL rejects flow through `execute(RejectDocument(...))` and audit-log to
`action_audit_log`. The legacy `validation_edit_log` table is then dropped
by migration 019.

Reversal restores the document's pre-reject status. The audit row's
`parameters` snapshots `previous_status` so the reverse builder doesn't
need to re-read the document.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.actions.base import Action, Effect, Precondition
from app.actions.executor import register_python_reversal
from app.actions.primitives import (
    BelongsToPractice,
    HasPermission,
    ObjectExists,
    SetField,
    SetMultipleFields,
    StatusOneOf,
)
from app.actions.registry import register_action


# Statuses a document can be in immediately before rejection. Excludes
# 'rejected' (idempotency catches replays), 'queued_for_processing' and
# 'processing' (in-flight; reject after they settle), and any
# 'approved'/'promoted' terminal state.
_REJECTABLE_FROM = ["parsed", "pending_validation", "validated", "error"]


@register_action
@dataclass(eq=False)
class RejectDocument(Action):
    """Reject a digitised document. Audited + reversible.

    The act of rejecting flips the doc's status to 'rejected' and stamps
    metadata (validator id, timestamp, reason). Reversal restores the
    pre-reject status so a reviewer who clicked reject in error can
    undo it within the audit-trail UI.
    """

    __action_name__: str = "RejectDocument"
    __action_version__: int = 1
    __reversible__: bool = True
    __pii_level__: str = "medium"

    document_id: str = ""
    reason: str = "Rejected by reviewer"
    actor_user_id: str = ""
    actor_email: Optional[str] = None
    practice_id: str = ""
    workspace_id: str = ""

    # Snapshotted at construction time by the API endpoint so reversal
    # can restore. NOT user-provided — the endpoint reads the row before
    # invoking the action.
    previous_status: str = ""
    previous_validated_at: Optional[str] = None
    previous_validated_by: Optional[str] = None
    previous_error_message: Optional[str] = None

    def preconditions(self) -> List[Precondition]:
        return [
            ObjectExists("digitised_documents", self.document_id),
            BelongsToPractice(
                "digitised_documents", self.document_id, self.workspace_id
            ),
            StatusOneOf(
                "digitised_documents", self.document_id, _REJECTABLE_FROM
            ),
            HasPermission("digitisation_validation"),
        ]

    def effects(self) -> List[Effect]:
        now_iso = datetime.now(timezone.utc).isoformat()
        return [
            SetMultipleFields(
                table="digitised_documents",
                object_id=self.document_id,
                columns={
                    "status": "rejected",
                    "validated_at": now_iso,
                    "validated_by": self.actor_email or "system",
                    "error_message": self.reason,
                    "updated_at": now_iso,
                },
                object_type="Document",
            ),
        ]

    def describe_for_user(self) -> str:
        return (
            f"Reject document {self.document_id} (reason: {self.reason!r}). "
            f"Reversible — previous status was {self.previous_status!r}."
        )

    def to_audit_parameters(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "reason": self.reason,
            "actor_user_id": self.actor_user_id,
            "practice_id": self.practice_id,
            "workspace_id": self.workspace_id,
            "previous_status": self.previous_status,
            "previous_validated_at": self.previous_validated_at,
            "previous_validated_by": self.previous_validated_by,
            "previous_error_message": self.previous_error_message,
        }

    @classmethod
    def from_audit_parameters(cls, params: Dict[str, Any]) -> "RejectDocument":
        return cls(
            document_id=params["document_id"],
            reason=params.get("reason", ""),
            actor_user_id=params["actor_user_id"],
            practice_id=params["practice_id"],
            workspace_id=params["workspace_id"],
            previous_status=params.get("previous_status", ""),
            previous_validated_at=params.get("previous_validated_at"),
            previous_validated_by=params.get("previous_validated_by"),
            previous_error_message=params.get("previous_error_message"),
        )


# ----------------------------------------------------------------------------
# Reversal builder — restore the pre-reject state from snapshotted params.
# ----------------------------------------------------------------------------
def _build_reject_document_reversal(original: Dict[str, Any], actor) -> List[Effect]:
    """Reversal returns a single SetMultipleFields Effect that restores
    all four columns the forward action overwrote."""
    params = original.get("parameters", {}) or {}
    return [
        SetMultipleFields(
            table="digitised_documents",
            object_id=params["document_id"],
            columns={
                "status": params.get("previous_status") or "pending_validation",
                "validated_at": params.get("previous_validated_at"),
                "validated_by": params.get("previous_validated_by"),
                "error_message": params.get("previous_error_message"),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            object_type="Document",
        ),
    ]


register_python_reversal("RejectDocument", _build_reject_document_reversal)
