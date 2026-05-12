"""
Generic Precondition + Effect primitives.

Actions compose preconditions and effects from this library. Per-action
bespoke logic (the heavy lifting in promotion specifically) stays inside
the wrapped service function (`promote_extractions`) and is invoked by a
single Effect — see `PromoteExtractionsViaPromoter` below.

The discipline:
    - A Precondition reads DB state, returns a CheckResult, never mutates.
    - An Effect's `plan(ctx)` returns an EffectDescriptor without mutating.
    - An Effect's `apply(ctx)` mutates and returns an EffectResult.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.actions.base import (
    CheckResult,
    Effect,
    EffectDescriptor,
    EffectResult,
    ErrorDetail,
    ExecutorContext,
    ERROR_CODE_EFFECT_FAILED,
    ERROR_CODE_NOT_FOUND,
)


# ----------------------------------------------------------------------------
# Precondition primitives
# ----------------------------------------------------------------------------

@dataclass
class ObjectExists:
    """Verify a row with `id == object_id` exists in `table`."""
    table: str
    object_id: str
    name: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            self.name = f"ObjectExists({self.table}, {self.object_id[:8]}...)"

    def check(self, ctx: ExecutorContext) -> CheckResult:
        result = ctx.supabase.table(self.table).select("id").eq("id", self.object_id).execute()
        passed = bool(result.data)
        return CheckResult(
            name=self.name,
            passed=passed,
            detail=None if passed else f"no {self.table} row with id={self.object_id}",
        )


@dataclass
class HasStatus:
    """Verify `<table>.<column>` equals `expected_status` for the given object_id."""
    table: str
    object_id: str
    expected_status: str
    column: str = "status"
    name: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            self.name = f"HasStatus({self.table}.{self.column}=={self.expected_status})"

    def check(self, ctx: ExecutorContext) -> CheckResult:
        result = (
            ctx.supabase.table(self.table)
            .select(self.column)
            .eq("id", self.object_id)
            .execute()
        )
        if not result.data:
            return CheckResult(self.name, False, f"no {self.table} row with id={self.object_id}")
        actual = result.data[0].get(self.column)
        passed = actual == self.expected_status
        return CheckResult(
            name=self.name,
            passed=passed,
            detail=None if passed else (
                f"{self.table}.{self.column} is {actual!r}, expected {self.expected_status!r}"
            ),
        )


@dataclass
class BelongsToPractice:
    """Verify `<table>.workspace_id == practice_id` for the given object_id.

    The "practice_id" terminology in the ontology corresponds to the
    "workspace_id" column in the DB (per setup_supabase.sql). This
    precondition bridges that vocabulary gap.
    """
    table: str
    object_id: str
    practice_id: str
    column: str = "workspace_id"
    name: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            self.name = f"BelongsToPractice({self.table}, {self.practice_id})"

    def check(self, ctx: ExecutorContext) -> CheckResult:
        result = (
            ctx.supabase.table(self.table)
            .select(self.column)
            .eq("id", self.object_id)
            .execute()
        )
        if not result.data:
            return CheckResult(self.name, False, f"no {self.table} row with id={self.object_id}")
        actual = result.data[0].get(self.column)
        passed = actual == self.practice_id
        return CheckResult(
            name=self.name,
            passed=passed,
            detail=None if passed else (
                f"{self.table}.{self.column} is {actual!r}, expected {self.practice_id!r}"
            ),
        )


@dataclass
class NotSoftDeleted:
    """Verify the row hasn't been soft-deleted (deleted_at IS NULL)."""
    table: str
    object_id: str
    column: str = "deleted_at"
    name: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            self.name = f"NotSoftDeleted({self.table})"

    def check(self, ctx: ExecutorContext) -> CheckResult:
        result = (
            ctx.supabase.table(self.table)
            .select(self.column)
            .eq("id", self.object_id)
            .execute()
        )
        if not result.data:
            # Treat missing as not-soft-deleted but a separate ObjectExists
            # should catch the absence. Pass to avoid double-failure.
            return CheckResult(self.name, True, None)
        deleted_at = result.data[0].get(self.column)
        passed = deleted_at is None
        return CheckResult(
            name=self.name,
            passed=passed,
            detail=None if passed else f"row was soft-deleted at {deleted_at}",
        )


@dataclass
class ConfirmationFresh:
    """Verify a user confirmation timestamp is within `window` of now.

    Used by actions where the user clicked "confirm" in a UI and the
    server needs to verify the click is recent (not a replayed request
    from yesterday).
    """
    confirmed_at: datetime
    window: timedelta = field(default_factory=lambda: timedelta(minutes=15))
    name: str = "ConfirmationFresh"

    def check(self, ctx: ExecutorContext) -> CheckResult:
        now = datetime.now(timezone.utc)
        # Normalise naive datetimes to UTC for comparison
        confirmed = self.confirmed_at
        if confirmed.tzinfo is None:
            confirmed = confirmed.replace(tzinfo=timezone.utc)
        age = now - confirmed
        passed = age <= self.window
        return CheckResult(
            name=self.name,
            passed=passed,
            detail=None if passed else (
                f"confirmation is {age.total_seconds():.0f}s old, "
                f"max allowed {self.window.total_seconds():.0f}s"
            ),
        )


@dataclass
class HasPermission:
    """Verify the actor holds a named permission."""
    permission: str
    name: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            self.name = f"HasPermission({self.permission})"

    def check(self, ctx: ExecutorContext) -> CheckResult:
        passed = ctx.actor.has_permission(self.permission)
        return CheckResult(
            name=self.name,
            passed=passed,
            detail=None if passed else f"actor lacks {self.permission!r}",
        )


# ----------------------------------------------------------------------------
# Effect primitives
# ----------------------------------------------------------------------------

@dataclass
class SetField:
    """Update a single column on a single row."""
    table: str
    object_id: str
    column: str
    value: Any
    op: str = "updated"  # affected_objects op
    object_type: str = ""
    name: str = ""

    def __post_init__(self) -> None:
        if not self.object_type:
            self.object_type = self.table.rstrip("s").capitalize()
        if not self.name:
            self.name = f"SetField({self.table}.{self.column})"

    def plan(self, ctx: ExecutorContext) -> EffectDescriptor:
        return EffectDescriptor(
            name=self.name,
            summary=f"would set {self.table}.{self.column} = {self.value!r} for id={self.object_id}",
            will_affect=[{"type": self.object_type, "id": self.object_id, "op": self.op}],
        )

    def apply(self, ctx: ExecutorContext) -> EffectResult:
        try:
            (
                ctx.supabase.table(self.table)
                .update({self.column: self.value})
                .eq("id", self.object_id)
                .execute()
            )
            ctx.append_affected_object(
                object_type=self.object_type, object_id=self.object_id, op=self.op
            )
            return EffectResult(
                name=self.name,
                succeeded=True,
                affected=[{"type": self.object_type, "id": self.object_id, "op": self.op}],
            )
        except Exception as exc:  # noqa: BLE001
            return EffectResult(
                name=self.name,
                succeeded=False,
                error=ErrorDetail(
                    code=ERROR_CODE_EFFECT_FAILED,
                    message=f"failed to update {self.table}.{self.column}: {exc}",
                    context={"table": self.table, "object_id": self.object_id},
                ),
            )


@dataclass
class SoftDelete:
    """Set the table's `deleted_at` column to now() — the conventional
    soft-delete pattern used across this codebase."""
    table: str
    object_id: str
    object_type: str = ""
    name: str = ""

    def __post_init__(self) -> None:
        if not self.object_type:
            self.object_type = self.table.rstrip("s").capitalize()
        if not self.name:
            self.name = f"SoftDelete({self.table}, {self.object_id[:8]}...)"

    def plan(self, ctx: ExecutorContext) -> EffectDescriptor:
        return EffectDescriptor(
            name=self.name,
            summary=f"would soft-delete {self.table} row id={self.object_id}",
            will_affect=[{"type": self.object_type, "id": self.object_id, "op": "soft_deleted"}],
        )

    def apply(self, ctx: ExecutorContext) -> EffectResult:
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            (
                ctx.supabase.table(self.table)
                .update({"deleted_at": now_iso})
                .eq("id", self.object_id)
                .execute()
            )
            ctx.append_affected_object(
                object_type=self.object_type, object_id=self.object_id, op="soft_deleted"
            )
            return EffectResult(
                name=self.name,
                succeeded=True,
                affected=[{
                    "type": self.object_type,
                    "id": self.object_id,
                    "op": "soft_deleted",
                }],
            )
        except Exception as exc:  # noqa: BLE001
            return EffectResult(
                name=self.name,
                succeeded=False,
                error=ErrorDetail(
                    code=ERROR_CODE_EFFECT_FAILED,
                    message=f"failed to soft-delete {self.table}: {exc}",
                    context={"table": self.table, "object_id": self.object_id},
                ),
            )


@dataclass
class PromoteExtractionsViaPromoter:
    """The single Effect that wraps the existing extraction_promoter.

    In PR 1, this Effect is the heavy hitter — it calls
    `promote_extractions()` from `app.services.extraction_promoter` and
    captures the resulting PromotionResult. The result's IDs are
    converted into `affected_objects` entries with `op='created'`.

    In PR 2, this Effect's `apply()` swaps from a Python call to a
    `supabase.rpc('execute_action_promote_document', ...)` call. The
    descriptor and result shapes don't change; the executor doesn't
    need to know.
    """
    document_id: str
    workspace_id: str
    extractions: Dict[str, Any]
    actor_email: Optional[str] = None
    forced_patient_id: Optional[str] = None
    force_create_patient: bool = False
    name: str = "PromoteExtractionsViaPromoter"

    def plan(self, ctx: ExecutorContext) -> EffectDescriptor:
        # Best-effort preview: count the structures inside the extraction
        # blob to give the dry-run audit row a meaningful summary.
        n_diag = len(self.extractions.get("diagnoses") or [])
        n_med = len(self.extractions.get("medications") or [])
        n_vit = len(self.extractions.get("vitals") or [])
        n_pn = len(self.extractions.get("progress_notes") or [])
        return EffectDescriptor(
            name=self.name,
            summary=(
                f"would promote document {self.document_id} to patient record: "
                f"{n_diag} diagnoses, {n_med} medications, {n_vit} vitals, "
                f"{n_pn} progress note(s)"
            ),
            will_affect=[
                {"type": "Patient",      "id": "<assigned-at-apply>", "op": "created"},
                {"type": "Consultation", "id": "<assigned-at-apply>", "op": "created"},
                {"type": "Document",     "id": self.document_id,      "op": "updated"},
            ],
        )

    def apply(self, ctx: ExecutorContext) -> EffectResult:
        # Imported here, not at module top, because extraction_promoter
        # pulls in heavy deps (the GP processor, etc.) that we don't want
        # to load when only running unit tests.
        from app.services.extraction_promoter import promote_extractions

        try:
            result = promote_extractions(
                ctx.supabase,
                workspace_id=self.workspace_id,
                document_id=self.document_id,
                extractions=self.extractions,
                created_by=self.actor_email,
                forced_patient_id=self.forced_patient_id,
                force_create_patient=self.force_create_patient,
            )
        except Exception as exc:  # noqa: BLE001
            return EffectResult(
                name=self.name,
                succeeded=False,
                error=ErrorDetail(
                    code=ERROR_CODE_EFFECT_FAILED,
                    message=f"promote_extractions raised: {exc}",
                    context={
                        "document_id": self.document_id,
                        "workspace_id": self.workspace_id,
                    },
                ),
            )

        affected: List[Dict[str, Any]] = []

        # Patient — op depends on whether we created or matched
        if getattr(result, "patient_id", None):
            # PromotionResult exposes `patient_kind` ('matched' | 'created' |
            # 'matched_explicit'). 'created' → we made the patient row;
            # everything else → we linked to an existing one.
            patient_kind = getattr(result, "patient_kind", "matched") or "matched"
            patient_op = "created" if patient_kind == "created" else "linked"
            affected.append({"type": "Patient", "id": result.patient_id, "op": patient_op})
            ctx.append_affected_object(
                object_type="Patient", object_id=result.patient_id, op=patient_op
            )

        # Consultations (encounters) — each is a created object
        for enc_id in getattr(result, "encounter_ids", None) or []:
            affected.append({"type": "Consultation", "id": enc_id, "op": "created"})
            ctx.append_affected_object(
                object_type="Consultation", object_id=enc_id, op="created"
            )

        # Document — we updated its promoted_to_patient_id etc.
        affected.append({"type": "Document", "id": self.document_id, "op": "updated"})
        ctx.append_affected_object(
            object_type="Document", object_id=self.document_id, op="updated"
        )

        return EffectResult(
            name=self.name,
            succeeded=True,
            affected=affected,
            detail=(
                f"promoted via extraction_promoter: patient={result.patient_id}, "
                f"encounters={len(result.encounter_ids or [])}"
            ),
        )
