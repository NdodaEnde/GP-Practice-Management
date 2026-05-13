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
    ERROR_CODE_ACTION_LOCKED,
    ERROR_CODE_EFFECT_FAILED,
    ERROR_CODE_INVARIANT_VIOLATED,
    ERROR_CODE_NOT_FOUND,
    ERROR_CODE_PRECONDITION_FAILED,
)


# ----------------------------------------------------------------------------
# SQLSTATE → ErrorDetail.code mapping
# ----------------------------------------------------------------------------
#
# When the PL/pgSQL RPC fails it surfaces as an APIError from supabase-py
# carrying a PostgREST response that includes the SQLSTATE. We translate
# to the typed ErrorDetail.code vocabulary so downstream consumers (UI,
# alerting, audit-trail filters) can switch on code with confidence.
#
# Beyond raw SQLSTATE: the RPC uses PostgreSQL's `HINT` clause on RAISE
# to attach a semantic discriminator to P0001 (user-defined exception)
# codes. We read the hint when present.

_SQLSTATE_TO_ERROR_CODE: Dict[str, str] = {
    # FOR UPDATE NOWAIT could not acquire the row lock — another
    # transaction is currently holding it. This is the mutual-exclusion
    # signal PR 2 set out to deliver.
    "55P03": ERROR_CODE_ACTION_LOCKED,
    # Foreign-key violation — usually means a precondition wasn't met
    # (referenced row missing) but treat as invariant since the RPC
    # checks references explicitly.
    "23503": ERROR_CODE_INVARIANT_VIOLATED,
    # NOT NULL violation
    "23502": ERROR_CODE_INVARIANT_VIOLATED,
    # Unique violation
    "23505": ERROR_CODE_INVARIANT_VIOLATED,
}

# Hint values used in RAISE EXCEPTION USING HINT = '...' inside the
# RPC. Map to typed error codes.
_HINT_TO_ERROR_CODE: Dict[str, str] = {
    "not_found":             ERROR_CODE_NOT_FOUND,
    "precondition_failed":   ERROR_CODE_PRECONDITION_FAILED,
    "invariant_violated":    ERROR_CODE_INVARIANT_VIOLATED,
    "cannot_reverse_dry_run": "cannot_reverse_dry_run",
}


def _classify_rpc_error(exc: Exception) -> ErrorDetail:
    """Translate a supabase RPC exception into a typed ErrorDetail.

    supabase-py raises a number of shapes depending on version + error
    type: APIError, PostgrestAPIError, generic Exception. We extract
    code/message/hint best-effort.
    """
    sqlstate: Optional[str] = None
    hint: Optional[str] = None
    pg_message: Optional[str] = None

    # supabase-py's APIError exposes code/message/details/hint on the
    # instance. Older versions stash them in args[0] as a dict.
    for attr in ("code", "sqlstate", "pg_code"):
        val = getattr(exc, attr, None)
        if val:
            sqlstate = str(val)
            break
    for attr in ("hint",):
        val = getattr(exc, attr, None)
        if val:
            hint = str(val)
            break
    for attr in ("message", "details"):
        val = getattr(exc, attr, None)
        if val and not pg_message:
            pg_message = str(val)

    # Fallback: parse the exception's str() — common for older client
    # versions where structured fields aren't set.
    if not sqlstate or not hint:
        text = str(exc)
        # PostgREST errors typically contain 'code: 55P03' or 'sqlstate'.
        import re
        m = re.search(r"(?:code|sqlstate)[\":\s]+\(?([0-9A-Z]{5})\)?", text)
        if m and not sqlstate:
            sqlstate = m.group(1)
        m = re.search(r"hint[\":\s]+([a-z_]+)", text)
        if m and not hint:
            hint = m.group(1)
        if not pg_message:
            pg_message = text

    code = "effect_failed"
    if hint and hint in _HINT_TO_ERROR_CODE:
        code = _HINT_TO_ERROR_CODE[hint]
    elif sqlstate and sqlstate in _SQLSTATE_TO_ERROR_CODE:
        code = _SQLSTATE_TO_ERROR_CODE[sqlstate]

    return ErrorDetail(
        code=code,
        message=pg_message or f"RPC failed: {exc!r}",
        context={
            "sqlstate": sqlstate,
            "hint": hint,
        },
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
    """The single Effect that wraps the document → patient-record promotion.

    PR 1: this called `promote_extractions()` from
    `app.services.extraction_promoter` — 100+ HTTP round-trips through
    PostgREST, no real ACID, ~35s latency.

    PR 2: calls `supabase.rpc('execute_action_promote_document', {...})`.
    The RPC runs the entire mutation inside one Postgres transaction
    with SELECT...FOR UPDATE NOWAIT mutual exclusion on the source
    document row. ~1-2s typical latency. SQLSTATE 55P03 (lock_not_available)
    surfaces as ErrorDetail(code='action_locked'); P0001 with HINT=
    'not_found' as ErrorDetail(code='not_found'); etc.

    The Effect descriptor + result shapes are identical to PR 1, so the
    executor's pipeline doesn't need to change. Each row created by the
    RPC lands in affected_objects with op='created'; the Document entry
    carries previous_encounter_id so reversal can restore it.
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
        import time
        import logging
        _log = logging.getLogger(__name__)

        rpc_started = time.monotonic()
        try:
            response = ctx.supabase.rpc(
                "execute_action_promote_document",
                {
                    "p_document_id":          self.document_id,
                    "p_workspace_id":         self.workspace_id,
                    "p_extractions":          self.extractions,
                    "p_created_by":           self.actor_email or "promoter",
                    "p_forced_patient_id":    self.forced_patient_id,
                    "p_force_create_patient": self.force_create_patient,
                },
            ).execute()
        except Exception as exc:  # noqa: BLE001
            return EffectResult(
                name=self.name,
                succeeded=False,
                error=_classify_rpc_error(exc),
            )

        elapsed_ms = int((time.monotonic() - rpc_started) * 1000)
        if elapsed_ms > 5000:
            # The 5s log canary — well before the 25s statement_timeout
            # ceiling fires. If we start seeing these regularly, the
            # contention surface or query plan has degraded.
            _log.warning(
                "execute_action_promote_document took %dms for document=%s — "
                "investigate contention or query plan",
                elapsed_ms, self.document_id,
            )

        # The RPC returns JSONB; supabase-py exposes it as `.data`.
        payload = response.data if hasattr(response, "data") else response
        if not isinstance(payload, dict):
            return EffectResult(
                name=self.name,
                succeeded=False,
                error=ErrorDetail(
                    code=ERROR_CODE_EFFECT_FAILED,
                    message=f"unexpected RPC payload type: {type(payload).__name__}",
                    context={"payload": str(payload)[:500]},
                ),
            )

        # Forward affected_objects from the RPC into the executor's
        # audit-row-in-progress so the audit row gets every created row,
        # not just the three-entry summary.
        rpc_affected: List[Dict[str, Any]] = payload.get("affected_objects") or []
        for entry in rpc_affected:
            # The RPC may include extra keys (e.g. previous_encounter_id);
            # only the three core keys are required for the executor's
            # append. Pass through the full entry to preserve metadata.
            ctx.audit_row_in_progress.setdefault("affected_objects", []).append(entry)

        return EffectResult(
            name=self.name,
            succeeded=True,
            affected=rpc_affected,
            detail=(
                f"promoted via RPC in {elapsed_ms}ms: "
                f"patient={payload.get('patient_id')}, "
                f"encounters={len(payload.get('encounter_ids') or [])}, "
                f"counts={payload.get('counts')}"
            ),
        )


@dataclass
class ReverseDocumentPromotionViaRpc:
    """Effect that calls reverse_action_promote_document(...) RPC.

    Used by `executor.reverse(audit_id)` when reversing a
    PromoteDocumentToPatientRecord audit row. The reverse RPC reads the
    original audit row's affected_objects (which lists every created
    row + previous_encounter_id on the Document entry), DELETEs in
    reverse FK order, restores the document's encounter_id, and writes
    a new reversal audit row + back-pointer atomically.

    Returns affected_objects describing the reversal (op='reversed_delete'
    / op='reversed_update') so the audit row records the undo work.
    """
    audit_id: str
    actor_user_id: str
    reason: Optional[str] = None
    name: str = "ReverseDocumentPromotionViaRpc"

    def plan(self, ctx: ExecutorContext) -> EffectDescriptor:
        return EffectDescriptor(
            name=self.name,
            summary=f"would reverse promote-document audit row {self.audit_id}",
            will_affect=[
                {"type": "ActionAuditLog", "id": self.audit_id, "op": "updated"},
            ],
        )

    def apply(self, ctx: ExecutorContext) -> EffectResult:
        try:
            response = ctx.supabase.rpc(
                "reverse_action_promote_document",
                {
                    "p_audit_id":      self.audit_id,
                    "p_actor_user_id": self.actor_user_id,
                    "p_reason":        self.reason,
                },
            ).execute()
        except Exception as exc:  # noqa: BLE001
            return EffectResult(
                name=self.name,
                succeeded=False,
                error=_classify_rpc_error(exc),
            )

        payload = response.data if hasattr(response, "data") else response
        if not isinstance(payload, dict):
            return EffectResult(
                name=self.name,
                succeeded=False,
                error=ErrorDetail(
                    code=ERROR_CODE_EFFECT_FAILED,
                    message=f"unexpected reverse RPC payload: {type(payload).__name__}",
                    context={"payload": str(payload)[:500]},
                ),
            )

        rpc_affected: List[Dict[str, Any]] = payload.get("affected_objects") or []
        for entry in rpc_affected:
            ctx.audit_row_in_progress.setdefault("affected_objects", []).append(entry)

        return EffectResult(
            name=self.name,
            succeeded=True,
            affected=rpc_affected,
            detail=(
                f"reversed via RPC: new_audit_id={payload.get('audit_id')}, "
                f"deleted_counts={payload.get('deleted_counts')}"
            ),
        )
