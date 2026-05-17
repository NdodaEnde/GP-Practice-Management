"""
preconsult — Phase 4 PR H. The pre-consultation brief: an HONEST backend
composition (NOT a new data path, NOT clinician-visible).

H-2 (locked): compose ONLY what the live corpus backs —
  * active medications      → the existing `patient_active_medications`
                              query template, via the SAME run_template
                              chokepoint (zero new data path);
  * changes since last visit → the existing `action_audit_log`
                              affected_objects `@>` containment idiom,
                              workspace-scoped (the established audit read;
                              not a new path, not a new template);
  * overdue immunisations    → the PR-G `immunisation_overdue` derived
                              StandingQuery kind, via run_template.

What it deliberately does NOT compose, carried STRUCTURALLY in the brief
(`named_not_built`) so a consumer cannot mistake absence for "nothing to
follow up" — the §C/§E earns-split applied in the data structure itself:
  * open_loops        — zero real instances (F-1=B substrate only; PR G's
                        kind is stateless-derived, NOT an OpenLoop; no
                        detector on main);
  * allergies         — a table exists but NO ontology query template;
                        building one *for pre-consult completeness* is
                        the legitimate-in-general / not-for-this-reason-
                        now anti-pattern, DECLINED at H-2;
  * reason_for_visit  — no appointment ingestion path exists anywhere.

SURFACE: backend composition only. PR E (the briefing UI) is held /
unmerged; this is NOT clinician-visible. The brief says so itself
(`surface`), and the Phase-4 close-out §B states it unsoftened. The
earns claim is "composes what's backed, verified by read-back", NEVER
"the doctor sees a pre-consult brief".
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from ontology.query import resolve_provenance, run_template

_NAMED_NOT_BUILT: Dict[str, str] = {
    "open_loops": (
        "zero real instances — F-1=B substrate only, no detector on "
        "main; PR G's immunisation_overdue is a STATELESS derived kind, "
        "not an OpenLoop. Deferred until a stateful loop + detector "
        "exists (the legitimate-A door, a deliberate future call)."
    ),
    "allergies": (
        "the allergies table exists but has NO ontology query template; "
        "building one for pre-consult completeness is the "
        "legitimate-in-general / not-for-this-reason-now anti-pattern, "
        "DECLINED at H-2. Named, not built."
    ),
    "reason_for_visit": (
        "no appointment / reason-for-visit ingestion path exists "
        "anywhere in the codebase. Named, not built."
    ),
}

_SURFACE = (
    "backend composition only — NOT clinician-visible (PR E briefing UI "
    "held/unmerged on main). 'composes what's backed', never 'the doctor "
    "sees a pre-consult brief'."
)


def _resolved_rows(supabase, template_id: str, params: Dict[str, Any],
                    workspace_id: str) -> List[Dict[str, Any]]:
    """Run a registered template through the SAME chokepoint /run uses,
    resolved. No new data path; provenance + tenant scope inherited by
    construction."""
    result = run_template(supabase, template_id, params,
                           workspace_id=workspace_id)
    resolved = resolve_provenance(supabase, result, workspace_id=workspace_id)
    return resolved.to_dict().get("rows", [])


def _changes_since_last_visit(supabase, *, workspace_id: str,
                              patient_id: str,
                              since: Optional[str]) -> List[Dict[str, Any]]:
    """The established audit read: workspace-scoped (satisfies the PR-5
    tenant guard — zero new BASELINE keys) AND affected_objects `@>`
    [{type:Patient,id}] (the row IS the patient scoping). Optionally
    bounded by `since` (the last consultation date). Not a new path."""
    q = (
        supabase.table("action_audit_log")
        .select("action_name,outcome,affected_objects,started_at")
        .eq("workspace_id", workspace_id)
        .contains("affected_objects", [{"type": "Patient", "id": patient_id}])
    )
    if since:
        q = q.gte("started_at", since)
    resp = q.order("started_at", desc=True).execute()
    rows = getattr(resp, "data", None) or []
    return [
        {"action": r.get("action_name"), "outcome": r.get("outcome"),
         "at": r.get("started_at"),
         "affected": r.get("affected_objects") or []}
        for r in rows
    ]


def build_preconsult_brief(
    supabase,
    *,
    workspace_id: str,
    patient_id: str,
    since: Optional[str] = None,
    as_of: Optional[date] = None,
) -> Dict[str, Any]:
    """Compose the honest pre-consult brief for one patient. Composes
    only the three backed sources; carries `named_not_built` + `surface`
    structurally so absence is never mistaken for "nothing to follow
    up". Reuses the chokepoint; no fabrication; no new data path."""
    as_of = as_of or date.today()
    return {
        "patient_id": patient_id,
        "workspace_id": workspace_id,
        "as_of": str(as_of),
        # backed:
        "active_medications": _resolved_rows(
            supabase, "patient_active_medications",
            {"patient_id": patient_id}, workspace_id),
        "changes_since_last_visit": _changes_since_last_visit(
            supabase, workspace_id=workspace_id,
            patient_id=patient_id, since=since),
        "immunisations_overdue": _resolved_rows(
            supabase, "immunisations_overdue", {}, workspace_id),
        # honest structure — what is NOT composed, and why:
        "named_not_built": dict(_NAMED_NOT_BUILT),
        "surface": _SURFACE,
    }
