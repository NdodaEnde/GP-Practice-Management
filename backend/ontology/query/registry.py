"""
The query template registry.

Mirrors the action registry pattern (app/actions/registry.py): modules
under ontology/query/templates/ call register_template() at import
time; ontology/query/registered.py imports them all so the registry is
populated at package import.

A template can only enter the registry if it declares a provenance
output column (enforced by TemplateSpec.__post_init__) — so "every
answer has a source" is impossible to violate by construction, not by
review vigilance.
"""

from __future__ import annotations

from typing import Dict, List

from ontology.query.spec import TemplateSpec

_REGISTRY: Dict[str, TemplateSpec] = {}


def register_template(spec: TemplateSpec) -> TemplateSpec:
    if spec.id in _REGISTRY:
        existing = _REGISTRY[spec.id]
        if existing.version == spec.version:
            raise RuntimeError(
                f"query template {spec.id!r} v{spec.version} already "
                f"registered — duplicate registration"
            )
        # Higher version supersedes; keep the newest.
        if spec.version < existing.version:
            return existing
    _REGISTRY[spec.id] = spec
    return spec


def get_template(template_id: str) -> TemplateSpec:
    if template_id not in _REGISTRY:
        raise KeyError(
            f"unknown query template {template_id!r}. "
            f"Known: {sorted(_REGISTRY)}"
        )
    return _REGISTRY[template_id]


def all_templates() -> List[TemplateSpec]:
    return sorted(_REGISTRY.values(), key=lambda s: s.id)
