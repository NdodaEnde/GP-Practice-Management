"""
Query template declaration types.

A TemplateSpec is the typed contract of one query shape:
  - a stable id + version
  - the PL/pgSQL function that executes it (tenant-scoped)
  - its typed parameter schema (ParamSpec list)
  - its declared output columns — which MUST include 'provenance'
    (enforced by register_template and the CI invariant test)

This is intentionally lightweight metadata, not a SQL IR. Per the
Phase 3 design (closed registry, not a generic algebra) the actual
query lives in a hand-reviewed PL/pgSQL function; this just describes
its shape so params can be validated and the provenance contract
enforced before the RPC is ever called.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional


# The column every template's RPC MUST return per row. Enforced at
# registration time and by test_query_layer_unit.py — "every answer
# carries its source" is a structural property, not a convention.
PROVENANCE_COLUMN = "provenance"

# workspace_id is always the first RPC arg, supplied by the runner from
# the auth context — never by the caller. Templates declare it
# implicitly; param specs are the *caller-supplied* params only.
WORKSPACE_PARAM = "p_workspace_id"


@dataclass(frozen=True)
class ParamSpec:
    """One caller-supplied parameter of a query template.

    `py_type` is the Python type the runner validates against.
    `rpc_arg` is the PL/pgSQL function's parameter name (e.g.
    'p_icd10_prefix'). `validator` is an optional extra check that
    raises ValueError with a human message on bad input.
    """
    name: str
    py_type: type
    rpc_arg: str
    required: bool = True
    default: Any = None
    validator: Optional[Callable[[Any], None]] = None

    def coerce_and_validate(self, raw: Any) -> Any:
        if raw is None:
            if self.required:
                raise ValueError(f"missing required parameter {self.name!r}")
            return self.default
        # Light coercion: ints arriving as numeric strings, etc.
        if self.py_type is int and isinstance(raw, str) and raw.lstrip("-").isdigit():
            raw = int(raw)
        if not isinstance(raw, self.py_type):
            raise ValueError(
                f"parameter {self.name!r} must be {self.py_type.__name__}, "
                f"got {type(raw).__name__}"
            )
        if self.validator is not None:
            self.validator(raw)  # raises ValueError on failure
        return raw


@dataclass(frozen=True)
class TemplateSpec:
    """The full declaration of one query shape."""
    id: str
    version: int
    rpc_name: str
    params: List[ParamSpec]
    output_columns: List[str]
    description: str = ""
    # Honest documentation surface: if the shape is correct but the
    # underlying data is thin/absent on the current corpus (e.g. the
    # lab-threshold shape — schema-correct, ~0 rows until lab ingestion
    # exists), say so here. Surfaced in the registry, never hidden.
    data_maturity: str = "populated"  # 'populated' | 'thin' | 'schema_only'

    def __post_init__(self) -> None:
        if PROVENANCE_COLUMN not in self.output_columns:
            raise ValueError(
                f"template {self.id!r} must declare a {PROVENANCE_COLUMN!r} "
                f"output column — every answer must carry its source. "
                f"Declared columns: {self.output_columns}"
            )
        if not self.rpc_name.startswith("query_"):
            raise ValueError(
                f"template {self.id!r} rpc_name {self.rpc_name!r} must start "
                f"with 'query_' (namespacing convention; keeps query RPCs "
                f"visually distinct from action RPCs like "
                f"execute_action_*)"
            )
        seen = set()
        for p in self.params:
            if p.name in seen:
                raise ValueError(f"duplicate param {p.name!r} in template {self.id!r}")
            seen.add(p.name)
