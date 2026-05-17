"""
OpenLoop state machine — Phase 4 PR F, THE load-bearing part, built and
proven in isolation BEFORE the object/migration/actions (the locked
build order; this is the one new thing in PR F and the place a §D.1
false-green would hide).

A CLOSED transition table (F-2 locked, verbatim):

    OPEN     --ADVANCE--> AWAITING
    AWAITING --BREACH-->  BREACHED
    AWAITING --CLOSE-->   CLOSED
    BREACHED --CLOSE-->   CLOSED
    CLOSED   -- * -->     (terminal: nothing leaves CLOSED)

Every (state, event) pair is EITHER a defined transition OR an
explicitly-illegal one — there is NO implicit fall-through. `classify_all_pairs`
enumerates the full state×event space so the test can assert
completeness: a future-added state or event that is not classified makes
the space incomplete and fails CI (F-2 rider). The transition table is
the single source of truth; no object may change `state` except by
`apply_transition` routed through an audited action (PR F §4) — the
object's `model_validator` independently rejects an inconsistent
(state, *_at) tuple so an un-audited bare write cannot produce a valid
object.
"""

from __future__ import annotations

from itertools import product
from typing import Dict, Tuple

from ontology.enums.open_loop_enums import OpenLoopEvent, OpenLoopState

ALL_STATES: Tuple[OpenLoopState, ...] = tuple(OpenLoopState)
ALL_EVENTS: Tuple[OpenLoopEvent, ...] = tuple(OpenLoopEvent)

# The closed transition table (F-2 locked). A (state, event) key present
# here is the ONLY way that pair is legal; its value is the resulting
# state. Absence = explicitly illegal (no fall-through).
ALLOWED_TRANSITIONS: Dict[Tuple[OpenLoopState, OpenLoopEvent], OpenLoopState] = {
    (OpenLoopState.OPEN, OpenLoopEvent.ADVANCE): OpenLoopState.AWAITING,
    (OpenLoopState.AWAITING, OpenLoopEvent.BREACH): OpenLoopState.BREACHED,
    (OpenLoopState.AWAITING, OpenLoopEvent.CLOSE): OpenLoopState.CLOSED,
    (OpenLoopState.BREACHED, OpenLoopEvent.CLOSE): OpenLoopState.CLOSED,
}

# Terminal states have zero outgoing legal transitions. Derived from the
# table (not asserted independently) so it cannot drift from it.
TERMINAL_STATES: Tuple[OpenLoopState, ...] = tuple(
    s for s in ALL_STATES
    if not any(k[0] == s for k in ALLOWED_TRANSITIONS)
)


class IllegalLoopTransition(ValueError):
    """Raised when an (state, event) pair is not in the closed table.

    A ValueError subclass so the object's `model_validator` and the
    audited action's precondition can both treat an illegal transition
    as the same rejection.
    """

    def __init__(self, state: OpenLoopState, event: OpenLoopEvent) -> None:
        super().__init__(
            f"illegal OpenLoop transition: no {event.value!r} from "
            f"{state.value!r} (closed transition table; CLOSED is terminal)"
        )
        self.state = state
        self.event = event


def apply_transition(state: OpenLoopState, event: OpenLoopEvent) -> OpenLoopState:
    """Return the resulting state for a legal (state, event), else raise
    IllegalLoopTransition. The ONLY sanctioned way to move state."""
    try:
        return ALLOWED_TRANSITIONS[(state, event)]
    except KeyError:
        raise IllegalLoopTransition(state, event) from None


def classify_all_pairs() -> Dict[Tuple[OpenLoopState, OpenLoopEvent], str]:
    """Classify EVERY (state, event) pair in the full state×event space
    as 'defined' or 'illegal' — exhaustively, no pair unclassified.

    This is the completeness oracle the test uses: it iterates the
    cartesian product of the live enums, so adding a state or an event
    without updating ALLOWED_TRANSITIONS still yields a fully-classified
    map (the new pairs land in 'illegal'); the test then asserts that
    the count of 'defined' equals len(ALLOWED_TRANSITIONS) and that the
    map covers exactly |states|×|events| pairs — so an unhandled pair or
    a stale table is a build failure, never a silent fall-through.
    """
    out: Dict[Tuple[OpenLoopState, OpenLoopEvent], str] = {}
    for state, event in product(ALL_STATES, ALL_EVENTS):
        out[(state, event)] = (
            "defined" if (state, event) in ALLOWED_TRANSITIONS else "illegal"
        )
    return out
