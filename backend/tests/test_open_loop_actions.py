"""
OpenLoop audited actions — DB-free suite (Phase 4 PR F).

The full executor round-trip (execute() → action_audit_log → reverse())
is RUN_INTEGRATION (needs the migrated DB; the user's Dashboard step).
This suite proves, WITHOUT a DB, the parts that can be proven without
one and where a bug would hide:

  * registration + the SoftDeletePatient-analog structure,
  * the transition EFFECT computes the correct next state + before-image,
  * the reversal builder produces an inverse that restores the LITERAL
    prior values — round-trip, and **path-independent** for CLOSE
    (AWAITING→CLOSED vs BREACHED→CLOSED both reverse exactly),
  * the effect-layer SECOND structural guard (apply_transition) rejects
    an illegal source even if a precondition were bypassed.

Non-vacuity (F-1 rider, action layer): the reversal assertions prove the
inverse actually ran and restored the exact prior — a no-op reversal
would leave the mutated state and fail. A fake in-memory supabase backs
the effects; no network, no Supabase.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import pytest

from app.actions.base import ActorContext, ExecutorContext
from app.actions.executor import _REVERSE_PYTHON_FOR_ACTION
from ontology.actions._open_loop_transition import (
    CreateLoopEffect,
    LoopTransitionEffect,
    loop_open_reversal,
    loop_transition_reversal,
)
from ontology.actions.open_loop_advance import OpenLoopAdvance
from ontology.actions.open_loop_breach import OpenLoopBreach
from ontology.actions.open_loop_close import OpenLoopClose
from ontology.actions.open_loop_open import OpenLoopOpen
from ontology.enums.open_loop_enums import OpenLoopEvent


# ---- minimal in-memory fake supabase (only what the effects use) ------

class _Resp:
    def __init__(self, data): self.data = data


class _Q:
    def __init__(self, store, table):
        self._store, self._table = store, table
        self._where: Dict[str, Any] = {}
        self._pending_update: Optional[Dict[str, Any]] = None

    def select(self, *_a, **_k): return self
    def insert(self, row): self._store.setdefault(self._table, {})[row["id"]] = dict(row); return self
    def update(self, d): self._pending_update = dict(d); return self

    def eq(self, col, val):
        self._where[col] = val
        return self

    def execute(self):
        rows = list(self._store.get(self._table, {}).values())
        for c, v in self._where.items():
            rows = [r for r in rows if r.get(c) == v]
        if self._pending_update is not None:
            for r in rows:
                r.update(self._pending_update)
            return _Resp(rows)
        return _Resp([dict(r) for r in rows])


class _FakeSupabase:
    def __init__(self): self.store: Dict[str, Dict[str, dict]] = {}
    def table(self, name): return _Q(self.store, name)


def _ctx(fake):
    return ExecutorContext(
        supabase=fake,
        actor=ActorContext(user_id="u1", email="u1@x.com", permissions=[]),
        practice_id="demo-briefing-workspace-001",
        workspace_id="demo-briefing-workspace-001",
    )


def _seed_loop(fake, **fields):
    base = dict(
        id="loop-1", workspace_id="demo-briefing-workspace-001",
        patient_id="pat-1", loop_kind="other", state="open",
        opening_event_kind="manual", opening_event_ref=None,
        expected_closing_event_kind="specialist letter", urgency="routine",
        deadline_at=None, opened_at="2026-05-17T09:00:00+00:00",
        closed_at=None, closed_reason=None, breached_at=None,
        created_at="2026-05-17T09:00:00+00:00",
        updated_at="2026-05-17T09:00:00+00:00", deleted_at=None,
    )
    base.update(fields)
    fake.store.setdefault("open_loops", {})[base["id"]] = base


def _audit_from(er) -> Dict[str, Any]:
    """Shape the executor would persist: effects_applied[i].result =
    EffectResult.to_dict() (the verified audit-row shape)."""
    return {"effects_applied": [{"name": er.name, "result": er.to_dict()}]}


# ---- registration + structure (the SoftDeletePatient analog) ----------

@pytest.mark.parametrize("name", [
    "OpenLoopOpen", "OpenLoopAdvance", "OpenLoopBreach", "OpenLoopClose",
])
def test_actions_register_python_reversal(name):
    assert name in _REVERSE_PYTHON_FOR_ACTION


def test_action_dunders_and_audit_param_roundtrip():
    for cls, name in [
        (OpenLoopOpen, "OpenLoopOpen"), (OpenLoopAdvance, "OpenLoopAdvance"),
        (OpenLoopBreach, "OpenLoopBreach"), (OpenLoopClose, "OpenLoopClose"),
    ]:
        a = cls(loop_id="loop-1", workspace_id="ws", actor_user_id="u1")
        assert a.__action_name__ == name
        assert a.__reversible__ is True
        rt = cls.from_audit_parameters(a.to_audit_parameters())
        assert rt.loop_id == "loop-1"
        assert isinstance(a.preconditions(), list) and a.preconditions()
        assert isinstance(a.effects(), list) and a.effects()


def test_close_precondition_accepts_both_legal_sources():
    pcs = OpenLoopClose(loop_id="loop-1", workspace_id="ws").preconditions()
    son = [p for p in pcs if p.__class__.__name__ == "StatusOneOf"]
    assert son and sorted(son[0].allowed) == ["awaiting", "breached"]


# ---- effect transition + before-image + reversal round-trip -----------

def test_advance_effect_transitions_and_reversal_restores_exactly():
    fake = _FakeSupabase(); _seed_loop(fake, state="open")
    er = LoopTransitionEffect("loop-1", OpenLoopEvent.ADVANCE).apply(_ctx(fake))
    assert er.succeeded
    assert fake.store["open_loops"]["loop-1"]["state"] == "awaiting"

    before = json.loads(er.detail)["before"]
    assert before["state"] == "open"  # the literal prior recorded

    rev_effects = loop_transition_reversal(_audit_from(er), None)
    assert len(rev_effects) == 1  # non-vacuous: a real inverse was built
    rev_effects[0].apply(_ctx(fake))
    assert fake.store["open_loops"]["loop-1"]["state"] == "open"  # restored exactly


def test_close_is_path_independent__awaiting_vs_breached_both_reverse_exactly():
    # AWAITING → CLOSED → reverse → AWAITING (closed_* back to None)
    fa = _FakeSupabase(); _seed_loop(fa, state="awaiting")
    er_a = LoopTransitionEffect("loop-1", OpenLoopEvent.CLOSE,
                                closed_reason="resolved").apply(_ctx(fa))
    assert fa.store["open_loops"]["loop-1"]["state"] == "closed"
    loop_transition_reversal(_audit_from(er_a), None)[0].apply(_ctx(fa))
    row_a = fa.store["open_loops"]["loop-1"]
    assert row_a["state"] == "awaiting"
    assert row_a["closed_at"] is None and row_a["closed_reason"] is None

    # BREACHED → CLOSED → reverse → BREACHED (breached_at intact)
    fb = _FakeSupabase()
    _seed_loop(fb, state="breached", breached_at="2026-05-20T09:00:00+00:00")
    er_b = LoopTransitionEffect("loop-1", OpenLoopEvent.CLOSE,
                                closed_reason="late close").apply(_ctx(fb))
    assert fb.store["open_loops"]["loop-1"]["state"] == "closed"
    loop_transition_reversal(_audit_from(er_b), None)[0].apply(_ctx(fb))
    row_b = fb.store["open_loops"]["loop-1"]
    assert row_b["state"] == "breached"
    assert row_b["breached_at"] == "2026-05-20T09:00:00+00:00"
    assert row_b["closed_at"] is None and row_b["closed_reason"] is None


def test_effect_layer_second_guard_rejects_illegal_source():
    """Defense in depth: even if a precondition were bypassed, the
    effect calling apply_transition rejects an illegal (state,event)."""
    fake = _FakeSupabase(); _seed_loop(fake, state="closed")
    er = LoopTransitionEffect("loop-1", OpenLoopEvent.ADVANCE).apply(_ctx(fake))
    assert er.succeeded is False
    assert er.error is not None
    assert "illegal OpenLoop transition" in er.error.message
    # the row was NOT mutated by a rejected effect
    assert fake.store["open_loops"]["loop-1"]["state"] == "closed"


def test_reversal_with_no_before_image_is_explicit_noop():
    assert loop_transition_reversal({"effects_applied": []}, None) == []
    assert loop_transition_reversal({}, None) == []


def test_create_effect_and_open_reversal_soft_deletes_created():
    fake = _FakeSupabase()
    row = OpenLoopOpen(
        loop_id="loop-9", patient_id="pat-1",
        workspace_id="demo-briefing-workspace-001",
        expected_closing_event_kind="x",
    )._row()
    er = CreateLoopEffect("loop-9", row).apply(_ctx(fake))
    assert er.succeeded
    assert fake.store["open_loops"]["loop-9"]["state"] == "open"

    rev = loop_open_reversal(_audit_from(er), None)
    assert len(rev) == 1
    assert rev[0].__class__.__name__ == "SoftDelete"
    assert rev[0].object_id == "loop-9" and rev[0].table == "open_loops"
