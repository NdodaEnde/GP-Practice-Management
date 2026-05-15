"""
EditExtractionField — single-field edit to a validation-session's
extractions JSONB.

A save endpoint that previously wrote one validation_edit_log row per
changed leaf now constructs one EditExtractionField action per changed
leaf and calls execute() on each. The result: one audit row per field
mutation, optimistic-concurrency-checked, reversible.

Per the user's PR 3 decision: granularity beats latency here. A 12-field
save produces 12 audit rows but each one is individually reversible —
the reviewer can undo a single field correction without rolling back the
whole save.

The optimistic-concurrency precondition (ExtractionFieldStillMatches)
defends against cross-reviewer races on the same session: if reviewer A
edited field X to value Y while reviewer B held a stale view showing X=W,
reviewer B's save fires an action with from_value=W which fails because
the live value is Y. Reviewer B must refresh.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
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
    ObjectExists,
    SetJsonPath,
)
from app.actions.registry import register_action


def _resolve_json_path(blob: Any, path: str) -> Any:
    """Read a dotted path from a JSONB blob. Returns None if any
    segment is missing. Numeric segments index into lists.
    """
    cursor = blob
    for seg in path.split("."):
        if cursor is None:
            return None
        idx: Any = int(seg) if seg.isdigit() else seg
        if isinstance(cursor, list):
            if not isinstance(idx, int) or idx >= len(cursor):
                return None
            cursor = cursor[idx]
        elif isinstance(cursor, dict):
            cursor = cursor.get(idx)
        else:
            return None
    return cursor


@dataclass
class ExtractionFieldStillMatches:
    """Optimistic-concurrency precondition: read the live value at
    field_path inside the session's extractions and assert it equals
    `expected_from_value`. If it doesn't, another reviewer has edited
    the same field — fail with precondition_failed so the caller can
    refresh.
    """
    session_id: str
    field_path: str
    expected_from_value: Any
    name: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            self.name = f"ExtractionFieldStillMatches({self.field_path})"

    def check(self, ctx: ExecutorContext) -> CheckResult:
        res = (
            ctx.supabase.table("gp_validation_sessions")
            .select("extractions")
            .eq("id", self.session_id)
            .limit(1)
            .execute()
        )
        if not res.data:
            return CheckResult(
                self.name, False,
                f"session {self.session_id} not found",
            )
        blob = res.data[0].get("extractions") or {}
        live_value = _resolve_json_path(blob, self.field_path)
        passed = live_value == self.expected_from_value
        return CheckResult(
            name=self.name,
            passed=passed,
            detail=None if passed else (
                f"field {self.field_path!r} expected {self.expected_from_value!r} "
                f"but live value is {live_value!r} — another reviewer may have "
                f"edited it"
            ),
        )


@register_action
@dataclass(eq=False)
class EditExtractionField(Action):
    """Edit a single field inside a validation session's extractions JSONB.

    Per-field granularity: one save endpoint call with N changed fields
    produces N EditExtractionField actions. Audit trail records each
    individually; each is independently reversible.

    The optimistic-concurrency precondition rejects stale writes when
    another reviewer beat us to it.
    """

    __action_name__: str = "EditExtractionField"
    __action_version__: int = 1
    __reversible__: bool = True
    __pii_level__: str = "high"

    document_id: str = ""
    session_id: str = ""
    field_path: str = ""
    from_value: Any = None
    to_value: Any = None
    actor_user_id: str = ""
    actor_email: Optional[str] = None
    practice_id: str = ""
    workspace_id: str = ""

    def preconditions(self) -> List[Precondition]:
        return [
            ObjectExists("gp_validation_sessions", self.session_id),
            BelongsToPractice(
                "gp_validation_sessions", self.session_id, self.workspace_id
            ),
            ExtractionFieldStillMatches(
                session_id=self.session_id,
                field_path=self.field_path,
                expected_from_value=self.from_value,
            ),
            HasPermission("digitisation_validation"),
        ]

    def effects(self) -> List[Effect]:
        return [
            SetJsonPath(
                table="gp_validation_sessions",
                object_id=self.session_id,
                json_column="extractions",
                json_path=self.field_path,
                value=self.to_value,
                object_type="ValidationSession",
            ),
        ]

    def describe_for_user(self) -> str:
        return (
            f"Edit extraction field {self.field_path!r} on "
            f"document {self.document_id}: "
            f"{self.from_value!r} → {self.to_value!r}"
        )

    def to_audit_parameters(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "session_id": self.session_id,
            "field_path": self.field_path,
            "from_value": self.from_value,
            "to_value": self.to_value,
            "actor_user_id": self.actor_user_id,
            "practice_id": self.practice_id,
            "workspace_id": self.workspace_id,
        }

    @classmethod
    def from_audit_parameters(cls, params: Dict[str, Any]) -> "EditExtractionField":
        return cls(
            document_id=params["document_id"],
            session_id=params["session_id"],
            field_path=params["field_path"],
            from_value=params.get("from_value"),
            to_value=params.get("to_value"),
            actor_user_id=params["actor_user_id"],
            practice_id=params["practice_id"],
            workspace_id=params["workspace_id"],
        )


# ----------------------------------------------------------------------------
# Reversal builder — swap from_value/to_value and re-apply.
# ----------------------------------------------------------------------------
def _build_edit_extraction_field_reversal(original: Dict[str, Any], actor) -> List[Effect]:
    """Reversal is symmetric: set the field back from to_value to from_value.
    Note: we don't go through another EditExtractionField action here —
    we just emit a SetJsonPath. The audit trail records the reversal as
    a 'ReverseEditExtractionField' row; the underlying SetJsonPath is
    the effect."""
    params = original.get("parameters", {}) or {}
    return [
        SetJsonPath(
            table="gp_validation_sessions",
            object_id=params["session_id"],
            json_column="extractions",
            json_path=params["field_path"],
            value=params.get("from_value"),
            object_type="ValidationSession",
        ),
    ]


register_python_reversal("EditExtractionField", _build_edit_extraction_field_reversal)
