"""
OpenLoop ontology enums — Phase 4 PR F.

The OpenLoop state machine is a CLOSED, exhaustively-tested transition
table (F-2 locked): `OPEN → AWAITING → (CLOSED | BREACHED)`,
`BREACHED → CLOSED`, `CLOSED` terminal. The states and the events that
drive transitions are declared here as closed enums; the allowed-
transition table and the transition function live in
`ontology.objects.open_loop_state` so they can be proven non-vacuous in
isolation BEFORE the object, migration, or actions exist (the locked
build order).

`LoopKind` is the taxonomy discriminator. F-3 (locked): PR F seeds ONLY
kinds it can honestly back — under the F-1=B lock (substrate + state
machine only, zero loop instance), PR F has NO detector and NO real
instance, so the enum carries the structural-minimum value `OTHER` plus
`SPECIALIST_REFERRAL_PENDING` as the NAMED-BUT-NOT-INSTANTIATED first
member (its detector and lifecycle are PR-G work, F-4 locked). No other
taxonomy kind is enumerated: an enum value with no detector and no
honest instance is a fake-property (it asserts a capability the code
does not have). PR G adds the remaining kinds when it builds their
detectors — extensibility is structural (a new enum member, no migration
churn: `open_loops.loop_kind` is TEXT, not a DB enum type).
"""

from enum import Enum


class OpenLoopState(str, Enum):
    """The lifecycle state of an OpenLoop. CLOSED is terminal.

    OPEN      → a loop has been opened (an opening event recorded), not
                yet acted on.
    AWAITING  → the loop is awaiting its expected closing event (e.g. a
                specialist letter, a result) — the deadline is live.
    BREACHED  → the deadline passed without the closing event; the loop
                is overdue. It is NOT terminal — it can still be closed
                late (BREACHED → CLOSED).
    CLOSED    → the loop is resolved (closing event arrived, or closed
                with a reason). Terminal: no transition leaves CLOSED.
    """

    OPEN = "open"
    AWAITING = "awaiting"
    BREACHED = "breached"
    CLOSED = "closed"


class OpenLoopEvent(str, Enum):
    """The events that drive state transitions. Each corresponds to one
    audited action (PR F §4): ADVANCE↔OpenLoopAdvance, BREACH↔OpenLoopBreach,
    CLOSE↔OpenLoopClose. (Opening a loop is creation, not a transition
    from a prior state — a loop is born OPEN; there is no event into OPEN.)
    """

    ADVANCE = "advance"   # OPEN → AWAITING
    BREACH = "breach"     # AWAITING → BREACHED
    CLOSE = "close"       # AWAITING → CLOSED ; BREACHED → CLOSED


class LoopUrgency(str, Enum):
    """How time-critical this loop is. Categorical (the project's
    enum-for-categorical discipline; a free string here would be
    inconsistent). Two honest values for the substrate — PR G may widen
    this WITH the detectors that would set finer urgencies; PR F does not
    enumerate urgencies no detector assigns (the F-3 named-not-built
    discipline applied to urgency)."""

    ROUTINE = "routine"   # default; deadline matters but not time-critical
    URGENT = "urgent"     # clinically time-critical if it breaches


class LoopKind(str, Enum):
    """The taxonomy discriminator. F-3 LOCKED — only honestly-backed
    kinds are seeded here.

    SPECIALIST_REFERRAL_PENDING is NAMED but NOT INSTANTIATED in PR F:
    its detector and lifecycle are PR-G taxonomy work (F-4 locked;
    legitimate-A carve-out only as a deliberate PR-G-merits decision).
    OTHER is the structural-minimum value that lets the substrate be
    coherent without enumerating kinds PR F cannot back. The remaining
    SA-primary-care loop taxonomy (abnormal-result-unacknowledged,
    chronic-script-expiring, immunisation-overdue, diabetic-foot-exam-due,
    retinal-screening-due, medication-reconciliation-needed, …) is
    PR G's to add WITH its detectors — deliberately absent here, not
    forgotten (the PR-D Decision-2 named-not-built discipline).
    """

    SPECIALIST_REFERRAL_PENDING = "specialist_referral_pending"  # named; PR-G builds the detector
    OTHER = "other"                                              # structural minimum
