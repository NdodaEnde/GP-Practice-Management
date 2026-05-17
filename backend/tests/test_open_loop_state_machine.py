"""
The OpenLoop state-machine non-vacuity suite — Phase 4 PR F, THE
load-bearing test, built and proven to BITE before the object,
migration, or actions exist (the locked build order).

F-1 non-vacuity rider (LOCKED, the §D.1 mechanism, verbatim): these are
"construct-validity tests proven non-vacuous by asserted rejection of
illegal transitions." The illegal-rejection half is load-bearing. A
suite that only feeds legal fabricated transitions is the §D.1
false-green relocated and is explicitly disallowed — so this file
*counts* its illegal-rejection assertions and asserts that the count is
non-zero AND equals the full count of illegal pairs in the state×event
space. A legal-only version of this suite cannot pass.

F-2 rider (LOCKED): the table is closed and exhaustively tested over the
full state×event space; no implicit fall-through; an unhandled pair (a
future-added state/event not in the table) fails CI; `BREACHED→CLOSED`
and `CLOSED→*`-rejected are explicit asserted facts, not the absence of
code.

DB-free: pure transition logic, no Supabase/Pydantic/network.
"""

from itertools import product

import pytest

from ontology.enums.open_loop_enums import OpenLoopEvent, OpenLoopState
from ontology.objects.open_loop_state import (
    ALL_EVENTS,
    ALL_STATES,
    ALLOWED_TRANSITIONS,
    TERMINAL_STATES,
    IllegalLoopTransition,
    apply_transition,
    classify_all_pairs,
)

S = OpenLoopState
E = OpenLoopEvent

# The EXACT locked F-2 table, written out independently of the module so
# a drift in ALLOWED_TRANSITIONS (added/removed/changed transition) is
# caught here, not silently inherited.
LOCKED_LEGAL = {
    (S.OPEN, E.ADVANCE): S.AWAITING,
    (S.AWAITING, E.BREACH): S.BREACHED,
    (S.AWAITING, E.CLOSE): S.CLOSED,
    (S.BREACHED, E.CLOSE): S.CLOSED,
}


def test_table_is_exactly_the_locked_F2_set():
    """Drift guard: the module's table must be EXACTLY the 4 locked
    transitions — no more (scope creep), no fewer (regression)."""
    assert ALLOWED_TRANSITIONS == LOCKED_LEGAL


def test_state_event_space_fully_classified_no_fall_through():
    """F-2 completeness/CI bite: every (state,event) pair in the live
    enum product is classified 'defined' or 'illegal' — exhaustively,
    once each, nothing unhandled. A future-added state/event not in the
    table still classifies (as 'illegal'); this test additionally pins
    the defined-count to the locked table so a stale table fails."""
    classified = classify_all_pairs()
    full_space = set(product(ALL_STATES, ALL_EVENTS))
    assert set(classified.keys()) == full_space
    assert len(classified) == len(ALL_STATES) * len(ALL_EVENTS)
    defined = [p for p, c in classified.items() if c == "defined"]
    illegal = [p for p, c in classified.items() if c == "illegal"]
    assert set(classified.values()) <= {"defined", "illegal"}  # no third class / no unhandled
    assert len(defined) == len(LOCKED_LEGAL)
    assert len(defined) + len(illegal) == len(full_space)


def test_legal_transitions_execute_to_expected_state():
    """Every locked-legal pair: apply_transition produces the expected
    next state."""
    for (state, event), expected in LOCKED_LEGAL.items():
        assert apply_transition(state, event) is expected


def test_illegal_transitions_are_rejected__and_the_rejection_count_proves_non_vacuity():
    """THE load-bearing assertion (F-1 non-vacuity rider). Every pair in
    the FULL state×event space that is NOT a locked-legal transition is
    fed in and asserted to RAISE. The number of rejections actually
    executed is counted and asserted to (a) be > 0 and (b) equal the
    exact count of illegal pairs — so a legal-only suite (0 rejections)
    structurally cannot pass this test."""
    full_space = list(product(ALL_STATES, ALL_EVENTS))
    illegal_pairs = [p for p in full_space if p not in LOCKED_LEGAL]

    rejections_executed = 0
    for state, event in illegal_pairs:
        with pytest.raises(IllegalLoopTransition) as ei:
            apply_transition(state, event)
        # the raised error carries the offending pair (used by the
        # object validator + action precondition the same way)
        assert ei.value.state is state
        assert ei.value.event is event
        rejections_executed += 1

    assert rejections_executed > 0, "vacuous: no illegal transition was exercised"
    assert rejections_executed == len(full_space) - len(LOCKED_LEGAL)
    assert rejections_executed == len(illegal_pairs)


def test_breached_can_still_close__explicit_fact():
    """`BREACHED → CLOSE → CLOSED` is an explicit allowed fact (a
    breached loop can still be resolved late), not the absence of code."""
    assert apply_transition(S.BREACHED, E.CLOSE) is S.CLOSED


def test_closed_is_terminal__every_event_rejected_explicitly():
    """CLOSED is terminal: every event from CLOSED is an explicit
    asserted rejection, not merely 'no code for it'."""
    for event in ALL_EVENTS:
        with pytest.raises(IllegalLoopTransition):
            apply_transition(S.CLOSED, event)
    assert S.CLOSED in TERMINAL_STATES
    assert TERMINAL_STATES == (S.CLOSED,)  # CLOSED is the ONLY terminal state


def test_open_cannot_close_directly__locked_table_has_no_OPEN_to_CLOSED():
    """The locked F-2 table is `OPEN → AWAITING → (CLOSED|BREACHED)`;
    there is deliberately NO direct OPEN→CLOSED. Asserted as an explicit
    fact so a future 'shortcut' is a deliberate F-2 override, not a
    silent addition."""
    with pytest.raises(IllegalLoopTransition):
        apply_transition(S.OPEN, E.CLOSE)
    with pytest.raises(IllegalLoopTransition):
        apply_transition(S.OPEN, E.BREACH)
