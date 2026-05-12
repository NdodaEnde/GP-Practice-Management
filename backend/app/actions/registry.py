"""
Action registry.

`ACTIONS` is a dict keyed by `__action_name__` → Action subclass. Populated
by the `@register_action` decorator as a side-effect of importing each
action module. The executor uses this map to hydrate the original Action
from an audit row's `parameters` JSONB when a reversal is requested.

Why a decorator and not lazy importlib:

    Decorator registration is explicit, debuggable, and avoids the
    classic import-cycle trap. Adding a new action: write the class with
    `@register_action`, add one line to `registered.py`. The registry
    populates as a side-effect of import. No circular dependency between
    executor.py and the action modules.
"""

from __future__ import annotations

from typing import Dict, Type

from app.actions.base import Action


ACTIONS: Dict[str, Type[Action]] = {}


def register_action(cls: Type[Action]) -> Type[Action]:
    """Class decorator that inserts the action into the global registry.

    Usage:
        @register_action
        @dataclass(eq=False)
        class PromoteDocumentToPatientRecord(Action):
            ...
    """
    if not hasattr(cls, "__action_name__") or not cls.__action_name__:
        raise ValueError(
            f"{cls.__name__} must define a non-empty __action_name__ "
            "class attribute before @register_action can register it"
        )
    name = cls.__action_name__
    if name in ACTIONS and ACTIONS[name] is not cls:
        raise ValueError(
            f"action name {name!r} already registered to {ACTIONS[name].__name__}; "
            f"refusing to overwrite with {cls.__name__}"
        )
    ACTIONS[name] = cls
    return cls


def get_action_class(action_name: str) -> Type[Action]:
    """Look up an Action class by its name. Raises KeyError if unknown."""
    if action_name not in ACTIONS:
        raise KeyError(
            f"unknown action name {action_name!r}; "
            f"known: {sorted(ACTIONS.keys())}"
        )
    return ACTIONS[action_name]
