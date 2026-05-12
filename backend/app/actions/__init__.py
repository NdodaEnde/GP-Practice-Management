"""
ActionExecutor package — the audited pathway for clinical mutations.

Public surface:

    from app.actions import execute, reverse, Action, ActorContext, ErrorDetail
"""

from app.actions.base import (
    Action,
    ActionResult,
    ActorContext,
    CheckResult,
    EffectDescriptor,
    EffectResult,
    ErrorDetail,
    ExecutorContext,
    KNOWN_ERROR_CODES,
)
from app.actions.executor import execute, reverse
from app.actions.registry import ACTIONS, get_action_class, register_action

# Importing `registered` registers all known actions via the @register_action
# decorator side-effect. Keep this import last so circular references between
# action modules and the registry resolve cleanly.
from app.actions import registered  # noqa: F401

__all__ = [
    "Action",
    "ActionResult",
    "ActorContext",
    "ACTIONS",
    "CheckResult",
    "EffectDescriptor",
    "EffectResult",
    "ErrorDetail",
    "ExecutorContext",
    "KNOWN_ERROR_CODES",
    "execute",
    "get_action_class",
    "register_action",
    "reverse",
]
