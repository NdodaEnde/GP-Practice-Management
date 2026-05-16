"""
ontology.query — the Phase 3 query layer.

A closed registry of named, versioned, parameterised query templates.
Each template is backed by exactly one reviewed PL/pgSQL function,
tenant-scoped by construction (workspace_id is a mandatory RPC
parameter), and provenance-bearing by construction (every result row
carries the source it came from — enforced as a CI invariant, not a
convention).

This is deliberately NOT a generic query algebra / fluent ORM. The
roadmap's `Patient.where(...).has_diagnosis(...)` example is the
illustrative *texture*; a safe general SQL compiler is a multi-month
research project with an unbounded attack surface. We deliver the
ergonomics of that example for a fixed, hand-reviewed template set —
the same way the action registry grew one reviewed action at a time.

Public surface:
  - register_template / get_template / all_templates  (registry)
  - run_template                                      (the one chokepoint)
  - QueryResult / QueryRow / Provenance               (result contract)
  - ParamSpec / TemplateSpec                           (declaration types)
"""

from ontology.query.spec import ParamSpec, TemplateSpec
from ontology.query.registry import register_template, get_template, all_templates
from ontology.query.result import Provenance, QueryRow, QueryResult
from ontology.query.runner import run_template, QueryError
from ontology.query.provenance import (
    resolve_provenance,
    ResolvedSource,
    ResolvedRow,
    ResolvedQueryResult,
    SourceQuality,
    OPENABLE,
    UNRESOLVABLE,
    NO_SOURCE,
)

# Side-effect import: populates the registry at package import time
# (mirrors app.actions importing .registered).
from ontology.query import registered  # noqa: F401,E402

__all__ = [
    "ParamSpec",
    "TemplateSpec",
    "register_template",
    "get_template",
    "all_templates",
    "Provenance",
    "QueryRow",
    "QueryResult",
    "run_template",
    "QueryError",
    "resolve_provenance",
    "ResolvedSource",
    "ResolvedRow",
    "ResolvedQueryResult",
    "SourceQuality",
    "OPENABLE",
    "UNRESOLVABLE",
    "NO_SOURCE",
]
