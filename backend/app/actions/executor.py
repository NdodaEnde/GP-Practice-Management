"""
ActionExecutor — the single audited pathway for every clinical mutation.

The execute() function:
    1. Constructs an in-flight audit row (the "audit_row_in_progress").
    2. Acquires a Postgres advisory lock keyed on (action_name, document_id)
       via the action_try_advisory_lock RPC. If the lock is taken,
       returns ActionResult(outcome='precondition_failed',
       error=ErrorDetail(code='action_locked', ...)).
    3. Checks idempotency_key against the action_audit_log unique index.
    4. Runs every precondition in order. If any fails, returns
       ActionResult(outcome='precondition_failed').
    5. In dry-run mode: calls effect.plan() for each effect, records
       descriptors, returns ActionResult(outcome='dry_run'). The audit
       row is written with dry_run=TRUE.
    6. In real mode: calls effect.plan() to record the descriptor,
       then effect.apply() to perform the mutation. Records results
       into the audit row. Returns ActionResult(outcome='success' or
       'effect_failed').
    7. Releases the advisory lock in finally.
    8. Writes the audit row in finally (fail-safe — log errors never
       propagate to the caller).

Locking approach (PR 1 outcome — see PR description and PHASE 0 below):
    PR 1 ships WITHOUT real mutual exclusion at the Python layer. The
    `_acquire_lock` function is a no-op that always returns True. This
    is the honest outcome of the Phase 0 verification:

      - Session-scoped pg_try_advisory_lock is NOT visible across
        Supabase's HTTP-pooled requests (verified empirically by
        test_advisory_lock_semantics.py::test_lock_visible_across_pooled_requests
        — the second client successfully re-acquires a lock the first
        client supposedly holds).

      - The pre-designed pivot to SELECT ... FOR UPDATE NOWAIT inside a
        one-shot RPC ALSO doesn't deliver work-level mutual exclusion at
        this layer — the FOR UPDATE lock is held only for the duration of
        the RPC's transaction (microseconds), not for the Python-side
        promote work that follows.

    Real mutual exclusion requires the entire mutation to run inside ONE
    Postgres transaction. That's PR 2's PL/pgSQL port: `promote_extractions`
    becomes `execute_action_promote_document(...)`, the RPC acquires
    FOR UPDATE NOWAIT at the start, and the lock holds for the duration
    of the whole transaction (which IS the work). Same end-state lock
    semantics, but the locking mechanism cannot be retrofitted at the
    Python layer.

    PR 1 still ships: audit log, structured preconditions, structured
    effects, dry-run mode, idempotency-key replay, ErrorDetail typing,
    reverse() column reservations. Those don't depend on locking. The
    concurrent-call test is skipped with this documented outcome.

Lock granularity (per-document, not per-patient):
    PR 1 locks per-document because that extracts cleanly from the
    current promoter. When the morning-briefing / open-loops machinery
    lands, the right semantics may be per-patient (two simultaneous
    promotions to the same patient compute their "since last visit"
    diffs against incomplete intermediate state). Revisit if same-
    patient concurrent promotions appear in production audit log —
    query for any two PromoteDocumentToPatientRecord audit rows
    targeting the same affected_objects[type=Patient].id within 5
    seconds of each other. Zero rows over three months = per-document
    is correct in practice. Handful of rows = per-patient is the right
    next move.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.actions.base import (
    Action,
    ActorContext,
    ActionResult,
    CheckResult,
    EffectDescriptor,
    EffectResult,
    ErrorDetail,
    ExecutorContext,
    ERROR_CODE_ACTION_LOCKED,
    ERROR_CODE_EFFECT_FAILED,
    ERROR_CODE_IDEMPOTENCY_REPLAY,
    ERROR_CODE_INTERNAL,
    ERROR_CODE_PRECONDITION_FAILED,
    utcnow,
)
from app.actions.registry import get_action_class

logger = logging.getLogger(__name__)


_AUDIT_LOG_TABLE = "action_audit_log"


# ---------------------------------------------------------------------------
# Lock acquisition + release
# ---------------------------------------------------------------------------

def _acquire_lock(supabase, action_name: str, resource_key: str) -> bool:
    """No-op in PR 1. Always returns True.

    Phase 0 verification (test_advisory_lock_semantics.py) revealed that
    session-scoped Postgres advisory locks are NOT visible across
    Supabase's HTTP-pooled requests — Client A acquires the lock,
    Client B (separate HTTP request through PostgREST's pool) successfully
    acquires the same lock. The lock primitive doesn't deliver
    mutual exclusion at the Python layer.

    The pre-designed pivot to SELECT ... FOR UPDATE NOWAIT inside a
    one-shot RPC ALSO doesn't help: the FOR UPDATE lock releases when
    the RPC's transaction commits (microseconds later), not when the
    Python-side promotion finishes.

    Real mutual exclusion requires the entire promotion to run inside
    one Postgres transaction. That's PR 2's PL/pgSQL port —
    `execute_action_promote_document(...)` will acquire FOR UPDATE NOWAIT
    at the start, and the lock will hold for the duration of the whole
    transaction (which IS the work). When PR 2 lands, this function's
    body changes to acquire the lock via the new RPC; the executor's
    public surface stays the same.

    For PR 1: the audit log makes concurrent-call collisions DETECTABLE
    after the fact (two audit rows for the same document within seconds
    of each other = race). The double-write detection query +
    `affected_objects @> '[{"type": "Document", "id": "<id>"}]'` lookup
    is sufficient to spot the gap in operations until PR 2 closes it.

    See scripts/audit_double_write_check.sql for the detection query
    and the PR description's "Phase 0 outcome" section.
    """
    # PR 2: replace with a call to the new PL/pgSQL RPC that acquires
    # FOR UPDATE NOWAIT inside the same transaction that does the work.
    return True


def _release_lock(supabase, action_name: str, resource_key: str) -> None:
    """No-op companion to _acquire_lock. See _acquire_lock docstring."""
    return None


def _resource_key_for(action: Action) -> str:
    """Derive the lock's resource_key from the action's parameters.

    PR 1 uses the document_id when present (per-document locking). The
    method walks action.to_audit_parameters() looking for a `document_id`
    key. Actions without a natural resource_key use the action_name +
    a UUID, effectively disabling cross-call mutual exclusion — fine
    for actions that aren't subject to the two-simultaneous-approvals
    race (e.g., MergePatient where the two patient IDs are the contention
    surface).
    """
    params = action.to_audit_parameters()
    if "document_id" in params:
        return str(params["document_id"])
    if "target_patient_id" in params:
        return str(params["target_patient_id"])
    return f"no-resource-key-{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# Audit row construction + write
# ---------------------------------------------------------------------------

def _init_audit_row(
    action: Action,
    actor: ActorContext,
    *,
    practice_id: str,
    workspace_id: str,
    dry_run: bool,
    idempotency_key: Optional[str],
) -> Dict[str, Any]:
    """Build the in-flight audit row dict. The executor mutates this as
    it runs (adding preconditions_checked, effects_applied, etc.) and
    writes it at the end."""
    return {
        "action_name":           action.__action_name__,
        "action_version":        action.__action_version__,
        "actor_user_id":         actor.user_id,
        "actor_email":           actor.email,
        "practice_id":           practice_id,
        "workspace_id":          workspace_id,
        "idempotency_key":       idempotency_key,
        "dry_run":               dry_run,
        "parameters":            action.to_audit_parameters(),
        "preconditions_checked": [],
        "effects_applied":       [],
        "affected_objects":      [],
        "outcome":               "internal_error_unfinished",  # overwritten before write
        "error_detail":          None,
        "started_at":            utcnow().isoformat(),
    }


def _write_audit_row(supabase, audit_row: Dict[str, Any]) -> Optional[str]:
    """Persist the audit row. Returns the audit row's UUID, or None on
    failure (logged, never raised — audit log must not break the caller)."""
    try:
        result = supabase.table(_AUDIT_LOG_TABLE).insert(audit_row).execute()
        if result.data:
            return result.data[0].get("id")
        return None
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "action_audit_log insert failed: %s — audit row: %s",
            exc, audit_row.get("action_name"),
            exc_info=True,
        )
        return None


def _check_idempotency_replay(
    supabase, action_name: str, idempotency_key: str
) -> Optional[Dict[str, Any]]:
    """Look up an existing audit row with this (action_name, idempotency_key).
    Returns the row dict if found (caller should treat this as a replay
    and return the original ActionResult), None otherwise."""
    try:
        result = (
            supabase.table(_AUDIT_LOG_TABLE)
            .select("*")
            .eq("action_name", action_name)
            .eq("idempotency_key", idempotency_key)
            .eq("dry_run", False)
            .limit(1)
            .execute()
        )
        if result.data:
            return result.data[0]
    except Exception as exc:  # noqa: BLE001
        logger.warning("idempotency check failed: %s", exc)
    return None


def _audit_row_to_result(row: Dict[str, Any]) -> ActionResult:
    """Convert an audit row dict to an ActionResult (e.g. for idempotency replay)."""
    err = None
    if row.get("error_detail"):
        ed = row["error_detail"]
        if isinstance(ed, dict) and "code" in ed:
            err = ErrorDetail(
                code=ed["code"],
                message=ed.get("message", ""),
                context=ed.get("context", {}) or {},
            )
    return ActionResult(
        audit_id=row["id"],
        action_name=row["action_name"],
        outcome=row["outcome"],
        affected_objects=row.get("affected_objects") or [],
        preconditions_checked=row.get("preconditions_checked") or [],
        effects_applied=row.get("effects_applied") or [],
        error=err,
        started_at=_parse_iso(row.get("started_at")),
        finished_at=_parse_iso(row.get("finished_at")),
        duration_ms=row.get("duration_ms"),
    )


def _parse_iso(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# execute()
# ---------------------------------------------------------------------------

def execute(
    action: Action,
    *,
    actor: ActorContext,
    supabase,
    practice_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    dry_run: bool = False,
    idempotency_key: Optional[str] = None,
) -> ActionResult:
    """Execute (or dry-run) an action through the audited pathway.

    practice_id / workspace_id default to the action's parameters (if it
    carries them). Override only when an action needs a different scope.
    """
    started_at = utcnow()
    started_ts = time.monotonic()

    # Resolve practice_id / workspace_id from action parameters if not passed
    params = action.to_audit_parameters()
    if practice_id is None:
        practice_id = params.get("practice_id") or params.get("workspace_id") or "unknown"
    if workspace_id is None:
        workspace_id = params.get("workspace_id") or practice_id

    # Idempotency replay short-circuit
    if idempotency_key and not dry_run:
        replay = _check_idempotency_replay(
            supabase, action.__action_name__, idempotency_key
        )
        if replay is not None:
            logger.info(
                "idempotency replay for %s key=%s; returning existing audit row %s",
                action.__action_name__, idempotency_key, replay.get("id"),
            )
            return _audit_row_to_result(replay)

    # Build the in-flight audit row
    audit_row = _init_audit_row(
        action,
        actor,
        practice_id=practice_id,
        workspace_id=workspace_id,
        dry_run=dry_run,
        idempotency_key=idempotency_key,
    )

    # Executor context — threaded through preconditions and effects
    ctx = ExecutorContext(
        supabase=supabase,
        actor=actor,
        practice_id=practice_id,
        workspace_id=workspace_id,
        audit_row_in_progress=audit_row,
    )

    resource_key = _resource_key_for(action)
    lock_acquired = False

    try:
        # 1) Acquire the advisory lock
        lock_acquired = _acquire_lock(supabase, action.__action_name__, resource_key)
        if not lock_acquired:
            audit_row["outcome"] = "precondition_failed"
            audit_row["error_detail"] = ErrorDetail(
                code=ERROR_CODE_ACTION_LOCKED,
                message=(
                    f"action {action.__action_name__} is already in progress for "
                    f"resource_key={resource_key}; please retry shortly"
                ),
                context={"resource_key": resource_key},
            ).to_dict()
            return _finalise(audit_row, started_at, started_ts, supabase)

        # 2) Run preconditions
        for pre in action.preconditions():
            try:
                cr = pre.check(ctx)
            except Exception as exc:  # noqa: BLE001
                cr = CheckResult(
                    name=getattr(pre, "name", pre.__class__.__name__),
                    passed=False,
                    detail=f"precondition raised: {exc!r}",
                )
            audit_row["preconditions_checked"].append(cr.to_dict())
            if not cr.passed:
                audit_row["outcome"] = "precondition_failed"
                audit_row["error_detail"] = ErrorDetail(
                    code=ERROR_CODE_PRECONDITION_FAILED,
                    message=f"precondition {cr.name} failed: {cr.detail}",
                    context={"failing_precondition": cr.name},
                ).to_dict()
                return _finalise(audit_row, started_at, started_ts, supabase)

        # 3) Plan effects (always — even in real mode, so descriptors land
        # in the audit row before any mutation happens).
        effects = list(action.effects())
        descriptors: List[EffectDescriptor] = []
        for eff in effects:
            try:
                desc = eff.plan(ctx)
            except Exception as exc:  # noqa: BLE001
                desc = EffectDescriptor(
                    name=getattr(eff, "name", eff.__class__.__name__),
                    summary=f"plan raised: {exc!r}",
                )
            descriptors.append(desc)
            audit_row["effects_applied"].append({
                "name": desc.name,
                "descriptor": desc.to_dict(),
                "result": None,  # filled by apply() below in real mode
            })

        if dry_run:
            audit_row["outcome"] = "dry_run"
            # In dry-run mode, the plan's `will_affect` becomes the audit
            # row's affected_objects (best-effort preview).
            for desc in descriptors:
                for entry in desc.will_affect:
                    audit_row["affected_objects"].append(entry)
            return _finalise(audit_row, started_at, started_ts, supabase)

        # 4) Apply effects (real mode)
        for idx, eff in enumerate(effects):
            try:
                er = eff.apply(ctx)
            except Exception as exc:  # noqa: BLE001
                er = EffectResult(
                    name=getattr(eff, "name", eff.__class__.__name__),
                    succeeded=False,
                    error=ErrorDetail(
                        code=ERROR_CODE_EFFECT_FAILED,
                        message=f"effect.apply raised: {exc!r}",
                        context={"effect_index": idx},
                    ),
                )
            # Update the corresponding entry's `result`
            audit_row["effects_applied"][idx]["result"] = er.to_dict()
            if not er.succeeded:
                audit_row["outcome"] = "effect_failed"
                audit_row["error_detail"] = er.error.to_dict() if er.error else ErrorDetail(
                    code=ERROR_CODE_EFFECT_FAILED,
                    message="effect failed without ErrorDetail",
                    context={"effect_index": idx},
                ).to_dict()
                # Note: PR 1 does NOT roll back already-applied effects.
                # That's the multi-statement ACID gap closed by PR 2's
                # PL/pgSQL port. The audit row's affected_objects records
                # what was actually applied, so reconciliation is possible.
                return _finalise(audit_row, started_at, started_ts, supabase)

        # All effects succeeded
        audit_row["outcome"] = "success"
        return _finalise(audit_row, started_at, started_ts, supabase)

    except Exception as exc:  # noqa: BLE001
        # Unexpected — log and return an internal-error audit row
        logger.exception("executor crashed during action %s", action.__action_name__)
        audit_row["outcome"] = "effect_failed"
        audit_row["error_detail"] = ErrorDetail(
            code=ERROR_CODE_INTERNAL,
            message=f"executor crashed: {exc!r}",
            context={"action_name": action.__action_name__},
        ).to_dict()
        return _finalise(audit_row, started_at, started_ts, supabase)

    finally:
        # Always release the lock if we acquired it
        if lock_acquired:
            _release_lock(supabase, action.__action_name__, resource_key)


def _finalise(
    audit_row: Dict[str, Any],
    started_at: datetime,
    started_ts: float,
    supabase,
) -> ActionResult:
    """Stamp the finish timestamps, write the audit row, return ActionResult."""
    finished_at = utcnow()
    audit_row["finished_at"] = finished_at.isoformat()
    audit_row["duration_ms"] = int((time.monotonic() - started_ts) * 1000)

    audit_id = _write_audit_row(supabase, audit_row)
    if audit_id is None:
        # Audit write failed — generate a synthetic ID so callers can
        # still return something coherent. The DB will eventually surface
        # the missing row through monitoring.
        audit_id = f"audit-write-failed-{uuid.uuid4().hex}"

    err = None
    if audit_row.get("error_detail"):
        ed = audit_row["error_detail"]
        err = ErrorDetail(
            code=ed["code"],
            message=ed["message"],
            context=ed.get("context", {}) or {},
        )

    return ActionResult(
        audit_id=audit_id,
        action_name=audit_row["action_name"],
        outcome=audit_row["outcome"],
        affected_objects=audit_row.get("affected_objects") or [],
        preconditions_checked=audit_row.get("preconditions_checked") or [],
        effects_applied=audit_row.get("effects_applied") or [],
        error=err,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=audit_row["duration_ms"],
    )


# ---------------------------------------------------------------------------
# reverse() — STUB for PR 1
# ---------------------------------------------------------------------------

def reverse(
    audit_id: str,
    *,
    actor: ActorContext,
    supabase,
    reason: Optional[str] = None,
) -> ActionResult:
    """STUB — reversal lands in PR 2.

    Column reservations (reverses_audit_id, reversed_by_audit_id) exist
    on the audit_log table; this function is the entry point that PR 2
    fleshes out. For now, calling it raises NotImplementedError to make
    the deferred work visible.
    """
    raise NotImplementedError(
        "ActionExecutor.reverse() is a PR 2 deliverable. "
        "PR 1 ships the audit_log columns and the function signature; "
        "PR 2 ships the implementation."
    )
