"""
Action / Precondition / Effect base types for the ActionExecutor.

The contract in one paragraph
-----------------------------

Every clinical mutation in the platform is an `Action` (subclass of
`Action`). The executor calls `action.preconditions()` to get a list of
`Precondition`s, each of which has `check(ctx) -> CheckResult`. If any
precondition fails, the executor stops, writes an audit row with
`outcome='precondition_failed'`, and returns an `ActionResult`. If all
preconditions pass, the executor calls `action.effects()` to get a list
of `Effect`s, each of which has `plan(ctx) -> EffectDescriptor` and
`apply(ctx) -> EffectResult`. In dry-run mode the executor only calls
`plan()`; in real mode it calls `plan()` then `apply()`. The executor
writes one audit row per invocation with the planned-or-applied effects,
the affected objects, the outcome, and any error.

Why typed and not free-form
---------------------------

Preconditions and Effects are Protocols, not callables. The contract is
explicit, the consumer of the audit log can rely on the shape of
`preconditions_checked` and `effects_applied`, and the executor can
generate uniform descriptors regardless of which Action is running.

ErrorDetail is a typed dataclass, not free-form JSONB. The `code` is
enum-style (a Final[str] constant from a known set). Every consumer of
the audit log — the audit-trail UI in Phase 4, alerting rules,
error-classification dashboards — can switch on the code with confidence.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, ClassVar, Dict, Final, List, Optional, Protocol


# ----------------------------------------------------------------------------
# ErrorDetail — the typed error shape every consumer can rely on
# ----------------------------------------------------------------------------

# Known error codes. New codes must be added here; the unit test
# `test_error_codes_are_declared_constants` enforces this discipline
# (and CI fails if a code is used in ErrorDetail(code=...) that isn't
# in this list).

ERROR_CODE_ACTION_LOCKED:        Final[str] = "action_locked"
ERROR_CODE_PRECONDITION_FAILED:  Final[str] = "precondition_failed"
ERROR_CODE_EFFECT_FAILED:        Final[str] = "effect_failed"
ERROR_CODE_NOT_FOUND:            Final[str] = "not_found"
ERROR_CODE_PERMISSION_DENIED:    Final[str] = "permission_denied"
ERROR_CODE_IDEMPOTENCY_REPLAY:   Final[str] = "idempotency_replay"
ERROR_CODE_VALIDATION_FAILED:    Final[str] = "validation_failed"
ERROR_CODE_INVARIANT_VIOLATED:   Final[str] = "invariant_violated"
ERROR_CODE_INTERNAL:             Final[str] = "internal"

KNOWN_ERROR_CODES: Final[frozenset[str]] = frozenset({
    ERROR_CODE_ACTION_LOCKED,
    ERROR_CODE_PRECONDITION_FAILED,
    ERROR_CODE_EFFECT_FAILED,
    ERROR_CODE_NOT_FOUND,
    ERROR_CODE_PERMISSION_DENIED,
    ERROR_CODE_IDEMPOTENCY_REPLAY,
    ERROR_CODE_VALIDATION_FAILED,
    ERROR_CODE_INVARIANT_VIOLATED,
    ERROR_CODE_INTERNAL,
})


@dataclass
class ErrorDetail:
    """Structured error description carried in audit rows and surfaced to UI.

    Why typed: every downstream consumer (error-handling UI, alerting,
    audit-trail filters) can switch on `code` with confidence. A free-form
    JSONB blob forces every consumer to reverse-engineer what fields exist.
    """
    code: str
    message: str
    context: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.code not in KNOWN_ERROR_CODES:
            # We deliberately don't crash on unknown codes at runtime — the
            # CI unit test catches drift at code-review time. At runtime we
            # accept unknown codes so a misconfigured deploy still produces
            # a logged audit row rather than crashing the executor itself.
            pass

    def to_dict(self) -> Dict[str, Any]:
        return {"code": self.code, "message": self.message, "context": dict(self.context)}


# ----------------------------------------------------------------------------
# ActorContext — who is invoking the action
# ----------------------------------------------------------------------------

@dataclass
class ActorContext:
    """The user invoking an action. Populated from the FastAPI auth dependency.

    Both user_id and email are stored on the audit row because user_id is
    stable for query joins but email is what humans recognise on a timeline.
    """
    user_id: str
    email: Optional[str] = None
    permissions: List[str] = field(default_factory=list)

    @classmethod
    def from_user(cls, current_user: Dict[str, Any]) -> "ActorContext":
        """Build an ActorContext from the dict the auth dependency returns."""
        return cls(
            user_id=current_user.get("id") or current_user.get("email", "unknown"),
            email=current_user.get("email"),
            permissions=current_user.get("permissions", []) or [],
        )

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions


# ----------------------------------------------------------------------------
# ExecutorContext — what preconditions and effects can see during a run
# ----------------------------------------------------------------------------

@dataclass
class ExecutorContext:
    """Threaded through every precondition.check() and effect.plan()/apply().

    Carries the Supabase client (for queries) and the actor (for permission
    checks). The executor populates `audit_row_in_progress` so effects can
    record their affected_objects entries as they go.
    """
    supabase: Any  # supabase.Client; untyped to avoid hard dep at import time
    actor: ActorContext
    practice_id: str
    workspace_id: str
    audit_row_in_progress: Dict[str, Any] = field(default_factory=dict)

    def append_affected_object(self, *, object_type: str, object_id: str, op: str) -> None:
        """Record an object touched by this action.

        `op` must be one of: created, updated, soft_deleted, linked.
        """
        if op not in ("created", "updated", "soft_deleted", "linked"):
            raise ValueError(f"unknown affected-object op: {op!r}")
        self.audit_row_in_progress.setdefault("affected_objects", []).append({
            "type": object_type,
            "id": object_id,
            "op": op,
        })


# ----------------------------------------------------------------------------
# Precondition Protocol
# ----------------------------------------------------------------------------

@dataclass
class CheckResult:
    """The outcome of a Precondition.check() call."""
    name: str
    passed: bool
    detail: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "passed": self.passed, "detail": self.detail}


class Precondition(Protocol):
    """A check that runs before any effect.apply().

    Implementations should be pure — read DB state, return CheckResult,
    never mutate. Side effects belong on Effect.
    """
    name: str

    def check(self, ctx: ExecutorContext) -> CheckResult: ...


# ----------------------------------------------------------------------------
# Effect Protocol
# ----------------------------------------------------------------------------

@dataclass
class EffectDescriptor:
    """What an effect WOULD do, returned by Effect.plan().

    Used in dry-run mode (executor records descriptors and stops) and in
    real-run mode (executor records descriptors then calls apply()). The
    descriptor is structured so a Phase 4 UI can render a "preview before
    commit" view without executing.
    """
    name: str
    summary: str
    will_affect: List[Dict[str, Any]] = field(default_factory=list)
        # list of {"type", "id", "op"} entries planned

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "summary": self.summary,
            "will_affect": list(self.will_affect),
        }


@dataclass
class EffectResult:
    """What an effect ACTUALLY did, returned by Effect.apply().

    Carries the IDs of created/modified objects so the audit row can
    record affected_objects without re-querying the DB.
    """
    name: str
    succeeded: bool
    affected: List[Dict[str, Any]] = field(default_factory=list)
        # list of {"type", "id", "op"} entries that actually happened
    detail: Optional[str] = None
    error: Optional[ErrorDetail] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "succeeded": self.succeeded,
            "affected": list(self.affected),
            "detail": self.detail,
            "error": self.error.to_dict() if self.error else None,
        }


class Effect(Protocol):
    """A side-effect performed by an action.

    `plan(ctx)` returns what would happen — used by dry-run mode and as
    the input to `apply()` in real-run mode (the executor records the
    descriptor in the audit row BEFORE calling apply()).

    `apply(ctx)` performs the mutation and returns what happened.
    """
    name: str

    def plan(self, ctx: ExecutorContext) -> EffectDescriptor: ...
    def apply(self, ctx: ExecutorContext) -> EffectResult: ...


# ----------------------------------------------------------------------------
# Action base
# ----------------------------------------------------------------------------

class Action(ABC):
    """Base class for every declarative action.

    Subclasses are typically `@dataclass(eq=False)` decorated. Use
    `eq=False` so two action instances with identical parameters don't
    compare equal — equality semantics aren't what tests want, and the
    audit log's idempotency key handles "same logical action" identity.

    The dunder class attributes describe the action's identity for the
    registry, the audit row, and the reversal pathway.
    """

    __action_name__:    ClassVar[str]
    __action_version__: ClassVar[int] = 1
    __reversible__:     ClassVar[bool] = False
    __pii_level__:      ClassVar[str] = "none"

    # ---- Required overrides -------------------------------------------

    @abstractmethod
    def preconditions(self) -> List[Precondition]:
        """Checks to run before any effect.apply()."""
        ...

    @abstractmethod
    def effects(self) -> List[Effect]:
        """Side effects to apply, in order."""
        ...

    @abstractmethod
    def describe_for_user(self) -> str:
        """Human-readable summary surfaced in UI confirmations."""
        ...

    @abstractmethod
    def to_audit_parameters(self) -> Dict[str, Any]:
        """JSON-encodable snapshot of action parameters for the audit row.

        Must include enough information for `Action.from_audit_parameters()`
        to reconstruct the action when a reversal is requested. Sensitive
        values that shouldn't appear in audit logs should be redacted here.
        """
        ...

    # ---- Optional overrides -------------------------------------------

    def reversal(self) -> List[Effect]:
        """Effects to apply when reversing this action.

        Default: raises NotImplementedError. Reversible actions override.
        """
        raise NotImplementedError(f"{self.__action_name__} is not reversible")

    def rpc_function_name(self) -> Optional[str]:
        """If this action is implemented via a PL/pgSQL RPC, return its name.

        Returns None for PR 1 (Python-side execution). PR 2's PL/pgSQL port
        sets this to 'execute_action_promote_document' etc.
        """
        return None

    def affected_object_ids_preview(self) -> List[Dict[str, Any]]:
        """Best-effort guess at the objects this action will affect.

        Optional — used to populate the audit row's affected_objects column
        when dry-run mode runs without calling effect.plan() at full fidelity.
        Default: empty list (effect.plan() will produce the real preview).
        """
        return []

    # ---- Hydration from audit parameters (for reversal) ----------------

    @classmethod
    def from_audit_parameters(cls, params: Dict[str, Any]) -> "Action":
        """Reconstruct an action instance from its audit-row `parameters`.

        Default implementation assumes parameters match the dataclass
        constructor signature. Override for actions with derived fields
        or non-trivial reconstruction.
        """
        return cls(**params)  # type: ignore[call-arg]


# ----------------------------------------------------------------------------
# ActionResult — what execute() returns
# ----------------------------------------------------------------------------

ACTION_OUTCOMES: Final[frozenset[str]] = frozenset({
    "success",
    "precondition_failed",
    "effect_failed",
    "reversed",
    "dry_run",
})


@dataclass
class ActionResult:
    """The result of an `execute()` or `reverse()` call.

    Mirrors the audit row's important fields so callers don't need to
    re-query the audit log to learn what happened.
    """
    audit_id: str
    action_name: str
    outcome: str
    affected_objects: List[Dict[str, Any]] = field(default_factory=list)
    preconditions_checked: List[Dict[str, Any]] = field(default_factory=list)
    effects_applied: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[ErrorDetail] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = None

    def __post_init__(self) -> None:
        if self.outcome not in ACTION_OUTCOMES:
            raise ValueError(
                f"unknown outcome {self.outcome!r}; must be one of {sorted(ACTION_OUTCOMES)}"
            )

    @property
    def is_success(self) -> bool:
        return self.outcome == "success"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "audit_id": self.audit_id,
            "action_name": self.action_name,
            "outcome": self.outcome,
            "affected_objects": list(self.affected_objects),
            "preconditions_checked": list(self.preconditions_checked),
            "effects_applied": list(self.effects_applied),
            "error": self.error.to_dict() if self.error else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_ms": self.duration_ms,
        }


def utcnow() -> datetime:
    """Module-level timestamp helper. Centralised so tests can monkeypatch."""
    return datetime.now(timezone.utc)
