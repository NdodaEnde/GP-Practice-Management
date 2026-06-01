"""
Financial-Disclosure entity resolver.

Spec §4.2: maps a verbatim surface form (e.g. "Matla Mine") to its canonical_id
in fd_entity_registry, with a `surface_form_confidence` score.

Resolution policy (the load-bearing rule):
    * confidence ≥ 0.80  → return the canonical_id; safe to write nodes/edges.
    * confidence <  0.80 → return (None, score); caller MUST route the input to
      fd_facts_needs_review via quarantine_for_review(). A wrong silent merge
      is worse than a missing node — it corrupts every rollup that touches
      the merged entity.

The actual fuzzy match runs in Postgres (fd_resolve_surface_form, defined in
backend/database/mining_fd_functions.sql) so trigram + array ops stay in the
DB. This wrapper is thin by design.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


# The single 0.80 confidence gate, per spec §4.2.
CONFIDENCE_GATE = 0.80


@dataclass(frozen=True)
class ResolveResult:
    """Outcome of resolving a surface form against the registry."""

    canonical_id: Optional[str]
    confidence: float
    is_confident: bool  # True iff confidence >= CONFIDENCE_GATE and canonical_id is not None

    @property
    def needs_review(self) -> bool:
        """Convenience inverse: True when caller must quarantine."""
        return not self.is_confident


def _ensure_supabase(supabase: Any) -> None:
    if supabase is None:
        raise ValueError("fd_entity_resolver requires a Supabase client (got None)")


def resolve_surface_form(
    supabase: Any,
    workspace_id: str,
    surface_form: str,
    entity_type: str,
) -> ResolveResult:
    """
    Resolve a verbatim surface form to a canonical_id within a workspace.

    Args:
        supabase: a supabase-py Client instance.
        workspace_id: UUID of the workspace (from current_user["workspace_id"]).
        surface_form: the verbatim text as extracted by ADE, e.g. "Matla Mine".
        entity_type: one of "Asset" | "CapitalFund" | "StrategicPillar" |
            "Acquisition" | "Org". Restricts the lookup to that subset of the
            registry (so an Asset-shaped extraction can't accidentally resolve
            to an Org with the same name).

    Returns:
        ResolveResult. If confidence < CONFIDENCE_GATE the canonical_id is
        wiped to None by this wrapper — the SQL function still returns the
        best partial match for diagnostic logging, but the caller MUST NOT
        treat it as resolved. Use quarantine_for_review() with the result's
        confidence to record what was seen and why it was rejected.
    """
    _ensure_supabase(supabase)
    if not isinstance(surface_form, str):
        return ResolveResult(canonical_id=None, confidence=0.0, is_confident=False)

    response = supabase.rpc(
        "fd_resolve_surface_form",
        {
            "p_workspace_id": workspace_id,
            "p_surface_form": surface_form,
            "p_entity_type": entity_type,
        },
    ).execute()

    rows = getattr(response, "data", None) or []
    if not rows:
        return ResolveResult(canonical_id=None, confidence=0.0, is_confident=False)

    row = rows[0]
    raw_confidence = row.get("confidence")
    confidence = float(raw_confidence) if raw_confidence is not None else 0.0
    raw_canonical_id: Optional[str] = row.get("canonical_id")

    is_confident = (
        confidence >= CONFIDENCE_GATE
        and raw_canonical_id is not None
        and raw_canonical_id != ""
    )

    return ResolveResult(
        canonical_id=raw_canonical_id if is_confident else None,
        confidence=confidence,
        is_confident=is_confident,
    )


def quarantine_for_review(
    supabase: Any,
    workspace_id: str,
    raw_surface_form: str,
    best_match_canonical_id: Optional[str],
    surface_form_confidence: float,
    ade_output: dict,
    doc_id: Optional[str] = None,
    page: Optional[int] = None,
) -> Optional[str]:
    """
    Write a low-confidence surface form to fd_facts_needs_review.

    Called for any ResolveResult with needs_review = True. The returned UUID
    is the new fd_facts_needs_review.id; the caller may want to surface it in
    ingest logs or the /api/fd/needs_review endpoint.

    A wrong silent merge is worse than a missing node, so the quarantine is
    the safety valve — but the registry pre-seeding is the *real* defence.
    If you find this function getting called for forms that obviously belong
    in the registry, expand mining_seed_entity_registry.sql with the new
    aliases rather than tuning the threshold down.
    """
    _ensure_supabase(supabase)
    payload = {
        "workspace_id": workspace_id,
        "raw_surface_form": raw_surface_form,
        "best_match_canonical_id": best_match_canonical_id,
        "surface_form_confidence": surface_form_confidence,
        "ade_output": ade_output,
        "doc_id": doc_id,
        "page": page,
    }
    response = supabase.table("fd_facts_needs_review").insert(payload).execute()
    rows = getattr(response, "data", None) or []
    if not rows:
        return None
    return rows[0].get("id")
