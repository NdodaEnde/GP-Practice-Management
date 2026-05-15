"""
ActionExecutor — the single audited pathway for every clinical mutation.

The execute() function:
    1. Constructs an in-flight audit row (the "audit_row_in_progress").
    2. Checks idempotency_key against the action_audit_log unique index.
    3. Runs every precondition in order. If any fails, returns
       ActionResult(outcome='precondition_failed').
    4. In dry-run mode: calls effect.plan() for each effect, records
       descriptors, returns ActionResult(outcome='dry_run'). The audit
       row is written with dry_run=TRUE.
    5. In real mode: calls effect.plan() to record the descriptor,
       then effect.apply() to perform the mutation. Records results
       into the audit row. Returns ActionResult(outcome='success' or
       'effect_failed').
    6. Writes the audit row in finally (fail-safe — log errors never
       propagate to the caller).

Locking — PR 2 outcome
----------------------

PR 1 acknowledged the Phase 0 outcome: session-scoped Postgres advisory
locks are NOT visible across Supabase's HTTP-pooled requests, so locking
cannot be retrofitted at the Python layer. PR 1 shipped without mutual
exclusion.

PR 2 closes the gap structurally. The PromoteExtractionsViaPromoter
Effect's apply() now calls the PL/pgSQL RPC `execute_action_promote_document`
which begins with SELECT...FOR UPDATE NOWAIT on the source document row.
The lock holds for the full transaction (the entire work IS the
transaction). Concurrent calls targeting the same document raise
SQLSTATE 55P03 which the Effect's error classifier maps to
ErrorDetail(code='action_locked').

The advisory-lock helpers from migration 014 became dead code; migration
017 drops them. The executor's _acquire_lock no-op is deleted from this
file. Mutual exclusion now lives at the database, where it has always
needed to live.

Lock granularity (per-document, not per-patient):
    PR 2 locks per-document because that extracts cleanly from the
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

Reversal — PR 2
---------------

reverse(audit_id, actor) loads the original audit row, validates it
(not dry-run, not already reversed, action is reversible), and calls
the reverse RPC for the action's type. For PromoteDocumentToPatientRecord
this is reverse_action_promote_document. The reverse RPC handles BOTH
the data undo AND the audit-row writes (new reversal row + back-pointer
update on the original) inside one transaction — required because the
back-pointer UPDATE depends on the new row's id and atomicity matters
for audit-trail integrity.

The executor.reverse() wrapper validates in Python first (cheap, no DB
round-trip for dry-run/already-reversed cases), then calls the RPC and
parses the response into an ActionResult.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

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
    ERROR_CODE_CANNOT_REVERSE_DRY_RUN,
    ERROR_CODE_EFFECT_FAILED,
    ERROR_CODE_IDEMPOTENCY_REPLAY,
    ERROR_CODE_INTERNAL,
    ERROR_CODE_NOT_FOUND,
    ERROR_CODE_PRECONDITION_FAILED,
    utcnow,
)
logger = logging.getLogger(__name__)


_AUDIT_LOG_TABLE = "action_audit_log"


# ---------------------------------------------------------------------------
# Mutual exclusion — lives at the database now
# ---------------------------------------------------------------------------
#
# PR 1's _acquire_lock / _release_lock no-ops are deleted. Phase 0
# verification confirmed session-scoped advisory locks aren't visible
# across Supabase's HTTP-pooled requests; the only working primitive is
# the FOR UPDATE NOWAIT taken inside the PL/pgSQL RPC (migration 015).
# The Effect's apply() handles SQLSTATE 55P03 (lock_not_available) and
# surfaces it as ErrorDetail(code='action_locked') through the normal
# error path, so the executor pipeline doesn't need a separate lock
# step. Actions that aren't database-backed (none yet) can layer their
# own mutual exclusion in their effects.


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

    try:
        # 1) Run preconditions
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

        # 2) Plan effects (always — even in real mode, so descriptors land
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

        # 3) Apply effects (real mode)
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
# reverse() — PR 2 implementation
# ---------------------------------------------------------------------------

# Per-action reverse dispatch — two maps, one per implementation tier.
#
# _REVERSE_RPC_FOR_ACTION: action_name → PL/pgSQL RPC name. For actions
#   whose forward mutates >1 table or needs FOR UPDATE NOWAIT on
#   anything, reversal must be a PL/pgSQL RPC so the data undo + new
#   audit row + back-pointer update are all atomic in one transaction.
#
# _REVERSE_PYTHON_FOR_ACTION: action_name → callable returning List[Effect].
#   For actions whose forward is a single-row UPDATE (RejectDocument,
#   VoidPrescription, etc.), reversal can be a Python-side Effect re-run.
#   The two writes (new audit row INSERT + back-pointer UPDATE on
#   original) are NOT atomic — same ~5ms audit-write gap PR 2 documented
#   for forward Python paths. The data state is still consistent; only
#   the audit pointer-pair might be missing on a Python crash mid-flight.
#
# An action_name in NEITHER map is non-reversible (returns
# precondition_failed). An action_name in BOTH is a bug — caught by
# test_pr3_reverse_dispatch_has_no_overlap in the unit tier.
_REVERSE_RPC_FOR_ACTION: Dict[str, str] = {
    "PromoteDocumentToPatientRecord": "reverse_action_promote_document",
}

# Each callable receives the ORIGINAL audit row (dict, with parameters
# JSONB hydrated) and the reversing ActorContext, returns the list of
# Effects to apply for reversal. Populated by ontology/actions/<name>.py
# modules at import time via register_python_reversal().
_REVERSE_PYTHON_FOR_ACTION: Dict[str, Callable[[Dict[str, Any], "ActorContext"], List[Any]]] = {}


def register_python_reversal(action_name: str, builder: Callable[[Dict[str, Any], "ActorContext"], List[Any]]) -> None:
    """Action modules call this at import time to register their reversal
    builder. Splits the concern: each Action class declares its own
    reverse behavior in its module, while the executor stays generic."""
    if action_name in _REVERSE_RPC_FOR_ACTION:
        raise RuntimeError(
            f"action {action_name!r} already has an RPC reverse handler; "
            "an action cannot be reversed via both Python and RPC paths"
        )
    _REVERSE_PYTHON_FOR_ACTION[action_name] = builder


def reverse(
    audit_id: str,
    *,
    actor: ActorContext,
    supabase,
    reason: Optional[str] = None,
) -> ActionResult:
    """Reverse a previously-applied audit row.

    Loads the original row, validates it (not dry-run, not already
    reversed, action is reversible), and calls the action-specific
    reverse RPC. The RPC handles BOTH the data undo AND the audit-row
    writes (new reversal row + back-pointer update on the original)
    inside one transaction — required because the back-pointer UPDATE
    depends on the new row's id and atomicity matters for audit-trail
    integrity.

    Returns an ActionResult with outcome='reversed' on success. The
    audit_id field on the returned ActionResult is the NEW (reversal)
    audit row's id, not the original's.
    """
    started_at = utcnow()
    started_ts = time.monotonic()

    # ----------------------------------------------------------------------
    # 1) Load the original audit row.
    # ----------------------------------------------------------------------
    try:
        original = (
            supabase.table(_AUDIT_LOG_TABLE)
            .select("*")
            .eq("id", audit_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("audit row lookup failed for reverse(%s)", audit_id)
        return _build_reverse_error_result(
            audit_id=audit_id,
            action_name="<unknown>",
            error=ErrorDetail(
                code=ERROR_CODE_INTERNAL,
                message=f"audit row lookup raised: {exc!r}",
                context={"audit_id": audit_id},
            ),
            started_at=started_at,
            started_ts=started_ts,
        )

    if not original.data:
        return _build_reverse_error_result(
            audit_id=audit_id,
            action_name="<unknown>",
            error=ErrorDetail(
                code=ERROR_CODE_NOT_FOUND,
                message=f"audit row not found: {audit_id}",
                context={"audit_id": audit_id},
            ),
            started_at=started_at,
            started_ts=started_ts,
        )

    row = original.data[0]
    action_name = row.get("action_name", "<unknown>")

    # ----------------------------------------------------------------------
    # 2) Validate. These checks are also done inside the RPC for
    # atomicity, but we run them in Python first so the cheap rejection
    # cases (dry-run, already-reversed) don't burn a transaction.
    # ----------------------------------------------------------------------
    if row.get("dry_run"):
        return _build_reverse_error_result(
            audit_id=audit_id,
            action_name=action_name,
            error=ErrorDetail(
                code=ERROR_CODE_CANNOT_REVERSE_DRY_RUN,
                message=(
                    f"audit row {audit_id} is a dry-run; there is nothing to undo. "
                    "Dry-runs are previews, not mutations."
                ),
                context={"audit_id": audit_id, "action_name": action_name},
            ),
            started_at=started_at,
            started_ts=started_ts,
        )

    if row.get("reversed_by_audit_id"):
        return _build_reverse_error_result(
            audit_id=audit_id,
            action_name=action_name,
            error=ErrorDetail(
                code=ERROR_CODE_PRECONDITION_FAILED,
                message=(
                    f"audit row {audit_id} already reversed by "
                    f"{row['reversed_by_audit_id']}"
                ),
                context={
                    "audit_id": audit_id,
                    "reversed_by": row.get("reversed_by_audit_id"),
                },
            ),
            started_at=started_at,
            started_ts=started_ts,
        )

    rpc_name = _REVERSE_RPC_FOR_ACTION.get(action_name)
    python_builder = _REVERSE_PYTHON_FOR_ACTION.get(action_name)

    if rpc_name is None and python_builder is None:
        return _build_reverse_error_result(
            audit_id=audit_id,
            action_name=action_name,
            error=ErrorDetail(
                code=ERROR_CODE_PRECONDITION_FAILED,
                message=f"action {action_name!r} is not reversible",
                context={"audit_id": audit_id, "action_name": action_name},
            ),
            started_at=started_at,
            started_ts=started_ts,
        )

    if python_builder is not None:
        # ------------------------------------------------------------------
        # 3a) Python-side reversal. The action's registered builder turns
        # the original audit row into a list of reversal Effects; we run
        # them, then INSERT a new audit row pointing at the original and
        # UPDATE the original's reversed_by_audit_id. Two statements,
        # NOT atomic — same audit-write gap as forward Python actions.
        # ------------------------------------------------------------------
        return _reverse_via_python(
            original=row,
            audit_id=audit_id,
            action_name=action_name,
            builder=python_builder,
            actor=actor,
            supabase=supabase,
            reason=reason,
            started_at=started_at,
            started_ts=started_ts,
        )

    # ----------------------------------------------------------------------
    # 3b) Call the reverse RPC. The RPC writes both the new reversal
    # audit row AND the back-pointer update on the original. Symmetric
    # data + audit atomicity inside one transaction.
    # ----------------------------------------------------------------------
    try:
        response = supabase.rpc(
            rpc_name,
            {
                "p_audit_id": audit_id,
                "p_actor_user_id": actor.user_id,
                "p_reason": reason,
            },
        ).execute()
    except Exception as exc:  # noqa: BLE001
        from app.actions.primitives import _classify_rpc_error
        err = _classify_rpc_error(exc)
        return _build_reverse_error_result(
            audit_id=audit_id,
            action_name=action_name,
            error=err,
            started_at=started_at,
            started_ts=started_ts,
        )

    payload = response.data if hasattr(response, "data") else response
    if not isinstance(payload, dict) or "audit_id" not in payload:
        return _build_reverse_error_result(
            audit_id=audit_id,
            action_name=action_name,
            error=ErrorDetail(
                code=ERROR_CODE_EFFECT_FAILED,
                message=f"unexpected reverse RPC payload: {type(payload).__name__}",
                context={"payload": str(payload)[:500]},
            ),
            started_at=started_at,
            started_ts=started_ts,
        )

    new_audit_id = payload["audit_id"]
    finished_at = utcnow()
    return ActionResult(
        audit_id=new_audit_id,
        action_name="ReverseActionPromoteDocument" if action_name == "PromoteDocumentToPatientRecord" else f"Reverse{action_name}",
        outcome="reversed",
        affected_objects=payload.get("affected_objects") or [],
        preconditions_checked=[
            {"name": "AuditRowExists", "passed": True, "detail": None},
            {"name": "NotDryRun", "passed": True, "detail": None},
            {"name": "NotAlreadyReversed", "passed": True, "detail": None},
        ],
        effects_applied=[{
            "name": "ReverseDocumentPromotionViaRpc",
            "descriptor": {"summary": f"reverse {action_name} via {rpc_name}"},
            "result": {
                "succeeded": True,
                "deleted_counts": payload.get("deleted_counts"),
            },
        }],
        error=None,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=int((time.monotonic() - started_ts) * 1000),
    )


def _build_reverse_error_result(
    *,
    audit_id: str,
    action_name: str,
    error: ErrorDetail,
    started_at: datetime,
    started_ts: float,
) -> ActionResult:
    """Construct an ActionResult for a reversal that failed validation
    or surfaced an error. Does NOT write an audit row for failed reversal
    attempts — failed reversals are not themselves auditable events in PR 2.
    PR 3 may revisit (audit-the-attempt is useful for security reviews)."""
    finished_at = utcnow()
    # outcome must be one of ACTION_OUTCOMES. For reversal errors we use
    # 'precondition_failed' (the cheap-rejection cases) or 'effect_failed'
    # (RPC errors). action_locked could surface from the FOR UPDATE NOWAIT
    # inside the reverse RPC if another reversal is racing.
    outcome = "precondition_failed"
    if error.code in (ERROR_CODE_EFFECT_FAILED, ERROR_CODE_INTERNAL, ERROR_CODE_ACTION_LOCKED):
        outcome = "effect_failed"
    return ActionResult(
        audit_id=f"reverse-failed-{audit_id}",
        action_name=f"Reverse{action_name}" if action_name != "<unknown>" else "ReverseAction",
        outcome=outcome,
        affected_objects=[],
        preconditions_checked=[],
        effects_applied=[],
        error=error,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=int((time.monotonic() - started_ts) * 1000),
    )


def _reverse_via_python(
    *,
    original: Dict[str, Any],
    audit_id: str,
    action_name: str,
    builder: Callable[[Dict[str, Any], ActorContext], List[Any]],
    actor: ActorContext,
    supabase,
    reason: Optional[str],
    started_at: datetime,
    started_ts: float,
) -> ActionResult:
    """Run a Python-side reversal: build effects, apply them, write the
    new reversal audit row, update the original's back-pointer.

    Atomicity caveat: the two audit-log writes (INSERT new + UPDATE
    original) are not in a transaction together. If Python crashes
    between them, the reversal data state is correct but the back-
    pointer pair is asymmetric (new row points at original; original
    doesn't point at new). Same audit-write gap PR 2 named for forward
    actions; acceptable for the same reasons.
    """
    finished_at = utcnow()
    new_audit_id = str(uuid.uuid4())

    # 1) Build the reversal effects from the original audit row.
    try:
        effects = builder(original, actor)
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "python reversal builder for %s crashed: %s", action_name, exc
        )
        return _build_reverse_error_result(
            audit_id=audit_id,
            action_name=action_name,
            error=ErrorDetail(
                code=ERROR_CODE_INTERNAL,
                message=f"reversal builder for {action_name} raised: {exc!r}",
                context={"audit_id": audit_id},
            ),
            started_at=started_at,
            started_ts=started_ts,
        )

    # 2) Apply each effect via a shared ExecutorContext so they can
    # contribute to a single affected_objects list. The reversal
    # equivalent of forward's effect-application loop.
    reverse_audit_row: Dict[str, Any] = {
        "affected_objects": [],
    }
    ctx = ExecutorContext(
        supabase=supabase,
        actor=actor,
        practice_id=original.get("practice_id", "unknown"),
        workspace_id=original.get("workspace_id", "unknown"),
        audit_row_in_progress=reverse_audit_row,
    )

    effects_applied: List[Dict[str, Any]] = []
    for eff in effects:
        try:
            desc = eff.plan(ctx)
        except Exception as exc:  # noqa: BLE001
            desc = EffectDescriptor(
                name=getattr(eff, "name", eff.__class__.__name__),
                summary=f"plan raised: {exc!r}",
            )
        try:
            er = eff.apply(ctx)
        except Exception as exc:  # noqa: BLE001
            er = EffectResult(
                name=getattr(eff, "name", eff.__class__.__name__),
                succeeded=False,
                error=ErrorDetail(
                    code=ERROR_CODE_EFFECT_FAILED,
                    message=f"reversal effect.apply raised: {exc!r}",
                    context={"action_name": action_name},
                ),
            )
        effects_applied.append({
            "name": desc.name,
            "descriptor": desc.to_dict(),
            "result": er.to_dict(),
        })
        if not er.succeeded:
            # Bail out — partial reversal is worse than no reversal because
            # the original audit row's reversed_by_audit_id stays NULL.
            return _build_reverse_error_result(
                audit_id=audit_id,
                action_name=action_name,
                error=er.error or ErrorDetail(
                    code=ERROR_CODE_EFFECT_FAILED,
                    message=f"reversal effect for {action_name} failed",
                    context={"action_name": action_name},
                ),
                started_at=started_at,
                started_ts=started_ts,
            )

    # 3) Write the new reversal audit row.
    finished_at = utcnow()
    duration_ms = int((time.monotonic() - started_ts) * 1000)
    reverse_action_name = f"Reverse{action_name}"
    new_row = {
        "id": new_audit_id,
        "action_name": reverse_action_name,
        "action_version": 1,
        "actor_user_id": actor.user_id,
        "actor_email": actor.email,
        "practice_id": original.get("practice_id"),
        "workspace_id": original.get("workspace_id"),
        "idempotency_key": None,
        "dry_run": False,
        "parameters": {
            "reverses_audit_id": audit_id,
            "reason": reason,
        },
        "preconditions_checked": [
            {"name": "AuditRowExists", "passed": True, "detail": None},
            {"name": "NotDryRun", "passed": True, "detail": None},
            {"name": "NotAlreadyReversed", "passed": True, "detail": None},
        ],
        "effects_applied": effects_applied,
        "affected_objects": reverse_audit_row.get("affected_objects", []),
        "outcome": "reversed",
        "error_detail": None,
        "reverses_audit_id": audit_id,
        "reversed_by_audit_id": None,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_ms": duration_ms,
    }
    inserted_id = _write_audit_row(supabase, new_row)
    if inserted_id is None:
        # Audit write failed; data has been undone but the trail is
        # incomplete. Return effect_failed so the caller knows; the
        # underlying log captures the write failure.
        logger.error(
            "python reversal of %s succeeded data-side but new audit row insert failed",
            action_name,
        )
        return _build_reverse_error_result(
            audit_id=audit_id,
            action_name=action_name,
            error=ErrorDetail(
                code=ERROR_CODE_EFFECT_FAILED,
                message="reversal applied but audit-row INSERT failed",
                context={"audit_id": audit_id, "new_audit_id": new_audit_id},
            ),
            started_at=started_at,
            started_ts=started_ts,
        )

    # 4) Update the original's back-pointer. If this fails the data is
    # consistent but the pointer-pair is asymmetric; logged and tolerated.
    try:
        (
            supabase.table(_AUDIT_LOG_TABLE)
            .update({"reversed_by_audit_id": inserted_id})
            .eq("id", audit_id)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "back-pointer UPDATE on original audit row %s failed: %s — "
            "reversal succeeded, new row %s is intact, audit trail is "
            "one-way until reconciliation",
            audit_id, exc, inserted_id,
        )

    return ActionResult(
        audit_id=inserted_id,
        action_name=reverse_action_name,
        outcome="reversed",
        affected_objects=reverse_audit_row.get("affected_objects", []),
        preconditions_checked=new_row["preconditions_checked"],
        effects_applied=effects_applied,
        error=None,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
    )
