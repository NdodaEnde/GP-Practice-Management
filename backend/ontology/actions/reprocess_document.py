"""
ReprocessDocument — re-queue a document for the parse/extract pipeline.

Used when LandingAI extraction failed or when extraction-engine changes
mean an earlier-processed doc would benefit from re-parsing. Sets the
doc's status to 'queued_for_processing' and clears any error_message;
the document_watcher service picks it up from there.

NOT reversible. A reprocess re-runs the parse, which writes new
gp_validation_sessions and extractions; "undoing" a reprocess has no
clean semantics — the next watcher cycle would just re-run anyway.
__reversible__ is False; executor.reverse() returns precondition_failed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.actions.base import Action, Effect, Precondition
from app.actions.primitives import (
    BelongsToPractice,
    HasPermission,
    ObjectExists,
    SetMultipleFields,
    StatusOneOf,
)
from app.actions.registry import register_action


# Statuses the document can be in for reprocess to make sense. Excludes
# 'queued_for_processing' (already in flight; double-queue is a noop but
# clutters the audit trail) and 'processing' (worker is mid-parse).
_REPROCESSABLE_FROM = ["error", "parsed", "pending_validation", "validated", "rejected"]


@register_action
@dataclass(eq=False)
class ReprocessDocument(Action):
    """Re-queue a digitised document for parse/extract. NOT reversible."""

    __action_name__: str = "ReprocessDocument"
    __action_version__: int = 1
    __reversible__: bool = False
    __pii_level__: str = "low"

    document_id: str = ""
    reason: Optional[str] = None
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
                "digitised_documents", self.document_id, _REPROCESSABLE_FROM
            ),
            HasPermission("digitisation_upload"),
        ]

    def effects(self) -> List[Effect]:
        now_iso = datetime.now(timezone.utc).isoformat()
        return [
            SetMultipleFields(
                table="digitised_documents",
                object_id=self.document_id,
                columns={
                    "status": "queued_for_processing",
                    "error_message": None,
                    "updated_at": now_iso,
                },
                object_type="Document",
            ),
        ]

    def describe_for_user(self) -> str:
        suffix = f" (reason: {self.reason!r})" if self.reason else ""
        return f"Re-queue document {self.document_id} for parse/extract{suffix}."

    def to_audit_parameters(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "reason": self.reason,
            "actor_user_id": self.actor_user_id,
            "practice_id": self.practice_id,
            "workspace_id": self.workspace_id,
        }
