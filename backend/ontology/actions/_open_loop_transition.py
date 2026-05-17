"""
Shared effects + reversal for the OpenLoop audited actions (Phase 4
PR F). Mirrors the SoftDeletePatient analog (single-table mutation,
Python-side reversal) and uses ONLY the verified Effect/EffectResult
shape (app/actions/base.py) and the verified primitive structure
(app/actions/primitives.py SetField.apply).

THE STATE MACHINE IS THE SOURCE OF TRUTH. `LoopTransitionEffect` does
not hardcode target states: it reads the loop's current state and calls
`apply_transition` (the closed table proven non-vacuous before this
code existed). The action's precondition already gates the legal source
state; this effect calling `apply_transition` is the SECOND structural
guard at the mutation layer — an illegal transition that somehow reached
here fails the effect, it does not silently write.

REVERSAL is a before-image undo: the effect records the exact prior
values of every field it changes into EffectResult.detail (JSON); the
reversal builder reads it back from `original["effects_applied"]` (the
verified audit-row shape — executor loads the row via select("*"), and
effects_applied[i]["result"] is EffectResult.to_dict()) and restores
those literal prior values. This is correct regardless of which legal
path produced the state (e.g. AWAITING→CLOSED vs BREACHED→CLOSED both
reverse to their literal recorded prior), the SoftDeletePatient
inverse-effect pattern generalised.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.actions.base import (
    ERROR_CODE_EFFECT_FAILED,
    EffectDescriptor,
    EffectResult,
    ErrorDetail,
    ExecutorContext,
)
from ontology.enums.open_loop_enums import OpenLoopEvent, OpenLoopState
from ontology.objects.open_loop_state import IllegalLoopTransition, apply_transition

_TABLE = "open_loops"
_OBJ = "OpenLoop"

# Which timestamp field each event sets, alongside `state` + `updated_at`.
# CLOSE additionally sets closed_reason (from the action parameter).
_EVENT_TS_FIELD = {
    OpenLoopEvent.ADVANCE: None,
    OpenLoopEvent.BREACH: "breached_at",
    OpenLoopEvent.CLOSE: "closed_at",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class LoopTransitionEffect:
    """Apply one OpenLoop transition via the closed table. Records the
    before-image for reversal. Mirrors SetField.apply structure."""

    loop_id: str
    event: OpenLoopEvent
    closed_reason: Optional[str] = None  # only meaningful for CLOSE
    name: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            self.name = f"LoopTransition({self.event.value})"

    def _read_row(self, ctx: ExecutorContext) -> Optional[Dict[str, Any]]:
        res = (
            ctx.supabase.table(_TABLE)
            .select("state,closed_at,closed_reason,breached_at,updated_at")
            .eq("id", self.loop_id)
            .execute()
        )
        data = getattr(res, "data", None) or []
        return data[0] if data else None

    def plan(self, ctx: ExecutorContext) -> EffectDescriptor:
        return EffectDescriptor(
            name=self.name,
            summary=f"would apply {self.event.value} to open_loop {self.loop_id}",
            will_affect=[{"type": _OBJ, "id": self.loop_id, "op": "updated"}],
        )

    def apply(self, ctx: ExecutorContext) -> EffectResult:
        try:
            row = self._read_row(ctx)
            if row is None:
                raise ValueError(f"no open_loops row with id={self.loop_id}")

            current = OpenLoopState(row["state"])
            # SECOND structural guard: the closed table, again, at the
            # mutation layer. Raises IllegalLoopTransition if somehow
            # illegal (the precondition should have caught it first).
            new_state = apply_transition(current, self.event)

            ts_field = _EVENT_TS_FIELD[self.event]
            now = _now_iso()
            updates: Dict[str, Any] = {"state": new_state.value, "updated_at": now}
            if ts_field is not None:
                updates[ts_field] = now
            if self.event is OpenLoopEvent.CLOSE:
                updates["closed_reason"] = self.closed_reason

            # before-image of EXACTLY the fields we are about to change
            before = {k: row.get(k) for k in updates}

            (
                ctx.supabase.table(_TABLE)
                .update(updates)
                .eq("id", self.loop_id)
                .execute()
            )
            ctx.append_affected_object(
                object_type=_OBJ, object_id=self.loop_id, op="updated"
            )
            return EffectResult(
                name=self.name,
                succeeded=True,
                affected=[{"type": _OBJ, "id": self.loop_id, "op": "updated"}],
                detail=json.dumps({"loop_id": self.loop_id, "before": before}),
            )
        except IllegalLoopTransition as exc:
            return EffectResult(
                name=self.name,
                succeeded=False,
                error=ErrorDetail(
                    code=ERROR_CODE_EFFECT_FAILED,
                    message=str(exc),
                    context={"table": _TABLE, "object_id": self.loop_id},
                ),
            )
        except Exception as exc:  # noqa: BLE001
            return EffectResult(
                name=self.name,
                succeeded=False,
                error=ErrorDetail(
                    code=ERROR_CODE_EFFECT_FAILED,
                    message=f"failed to apply {self.event.value}: {exc}",
                    context={"table": _TABLE, "object_id": self.loop_id},
                ),
            )


@dataclass
class RestoreLoopFields:
    """Inverse effect: write a literal before-image back. Mirrors
    SetField.apply structure (multi-column update by id)."""

    loop_id: str
    before: Dict[str, Any]
    name: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            self.name = f"RestoreLoopFields({self.loop_id[:8]}...)"

    def plan(self, ctx: ExecutorContext) -> EffectDescriptor:
        return EffectDescriptor(
            name=self.name,
            summary=f"would restore {sorted(self.before)} on open_loop {self.loop_id}",
            will_affect=[{"type": _OBJ, "id": self.loop_id, "op": "updated"}],
        )

    def apply(self, ctx: ExecutorContext) -> EffectResult:
        try:
            (
                ctx.supabase.table(_TABLE)
                .update(self.before)
                .eq("id", self.loop_id)
                .execute()
            )
            ctx.append_affected_object(
                object_type=_OBJ, object_id=self.loop_id, op="updated"
            )
            return EffectResult(
                name=self.name,
                succeeded=True,
                affected=[{"type": _OBJ, "id": self.loop_id, "op": "updated"}],
            )
        except Exception as exc:  # noqa: BLE001
            return EffectResult(
                name=self.name,
                succeeded=False,
                error=ErrorDetail(
                    code=ERROR_CODE_EFFECT_FAILED,
                    message=f"failed to restore open_loop {self.loop_id}: {exc}",
                    context={"table": _TABLE, "object_id": self.loop_id},
                ),
            )


@dataclass
class CreateLoopEffect:
    """Insert a new OpenLoop row, born OPEN. Mirrors SetField.apply
    structure (single-table write by the executor's supabase client).
    Records the created id for the Open reversal (soft-delete)."""

    loop_id: str
    row: Dict[str, Any]
    name: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            self.name = f"CreateLoop({self.loop_id[:8]}...)"

    def plan(self, ctx: ExecutorContext) -> EffectDescriptor:
        return EffectDescriptor(
            name=self.name,
            summary=f"would create open_loop {self.loop_id} (state=open)",
            will_affect=[{"type": _OBJ, "id": self.loop_id, "op": "created"}],
        )

    def apply(self, ctx: ExecutorContext) -> EffectResult:
        try:
            ctx.supabase.table(_TABLE).insert(self.row).execute()
            ctx.append_affected_object(
                object_type=_OBJ, object_id=self.loop_id, op="created"
            )
            return EffectResult(
                name=self.name,
                succeeded=True,
                affected=[{"type": _OBJ, "id": self.loop_id, "op": "created"}],
                detail=json.dumps({"loop_id": self.loop_id, "created": True}),
            )
        except Exception as exc:  # noqa: BLE001
            return EffectResult(
                name=self.name,
                succeeded=False,
                error=ErrorDetail(
                    code=ERROR_CODE_EFFECT_FAILED,
                    message=f"failed to create open_loop {self.loop_id}: {exc}",
                    context={"table": _TABLE, "object_id": self.loop_id},
                ),
            )


def loop_open_reversal(original: Dict[str, Any], actor) -> List[Any]:
    """Reverse of OpenLoopOpen: soft-delete the created loop. Reads the
    created id from the recorded EffectResult.detail; uses the verified
    SoftDelete primitive (the SoftDeletePatient inverse pattern)."""
    from app.actions.primitives import SoftDelete

    for entry in original.get("effects_applied", []) or []:
        result = (entry or {}).get("result") or {}
        detail = result.get("detail")
        if not detail:
            continue
        try:
            payload = json.loads(detail)
        except (TypeError, ValueError):
            continue
        if payload.get("created") and "loop_id" in payload:
            return [SoftDelete(_TABLE, payload["loop_id"], object_type=_OBJ)]
    return []


def loop_transition_reversal(original: Dict[str, Any], actor) -> List[Any]:
    """Build the inverse from the recorded before-image. Reads the
    verified audit-row shape: original['effects_applied'][i]['result']
    is EffectResult.to_dict(); detail carries {'loop_id','before'}."""
    for entry in original.get("effects_applied", []) or []:
        result = (entry or {}).get("result") or {}
        detail = result.get("detail")
        if not detail:
            continue
        try:
            payload = json.loads(detail)
        except (TypeError, ValueError):
            continue
        if "loop_id" in payload and "before" in payload:
            return [RestoreLoopFields(payload["loop_id"], payload["before"])]
    # No recorded before-image → nothing to reverse (idempotent no-op),
    # the same posture as a missing-row reversal.
    return []
