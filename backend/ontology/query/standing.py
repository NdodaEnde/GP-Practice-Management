"""
standing — Phase 3 PR D. Standing-query materialisation substrate.

WHAT THIS IS (and is not):
  - A small CLOSED registry of `StandingQuery` declarations + a
    `materialise_standing_queries()` that, for each clinical_query-
    ENTITLED workspace (enumerated from a TRUSTED DB source, never
    caller input) × each registered standing query, runs the query
    through the SAME `run_template` + `resolve_provenance` chokepoint
    `/run` and `/ask` use and writes the resolved rows into
    `briefing_items`.
  - It adds NO new data path. The materialiser reaches facts ONLY
    through that two-call chokepoint, so every `briefing_items` row
    structurally inherits PR A/B's verifiable-provenance +
    openable/no_source/unresolvable + unresolvable_count/superseded_count
    contract. It NEVER reads fact tables directly and NEVER
    re-implements provenance.
  - Read-only with respect to clinical data; it does NOT route through
    the ActionExecutor (queries are not actions; no audit row). The
    only writes are the materialised `briefing_items` rows.
  - The `run_template` chokepoint is where a future POPIA
    query-access-log decorator attaches (Phase 5, deferred — the
    chokepoint exists, so it is a decorator not a refactor; design
    choice #6). The materialiser rides it, so it inherits that slot for
    free — a positive consequence of "no new data path".

IDEMPOTENCY (locked decision #6): per (workspace_id, kind, as_of_date)
the materialiser DELETEs that exact partition then INSERTs the freshly-
resolved rows, ONE TRANSACTION per (workspace_id, kind) via a psycopg2
connection (the chokepoint reads use the supabase client; the
briefing_items write is transactional so a mid-run failure's blast
radius is exactly the partition being rewritten and a double-run is
row-stable by construction). 027 deliberately added no PL/pgSQL
function; the transaction lives in this writer.

═══════════════════════════════════════════════════════════════════════
NAMED-NOT-BUILT — the conversion-instrumentation scope note (guarded
hardest). This note travels with the code (it is also in
ONTOLOGY_QUERY_LAYER_POSTMORTEM.md); no code stub exists because a stub
would be the fake-property anti-pattern (pretending the consumer
exists):

  Conversion instrumentation — measuring which briefing / pre-consult
  items a prospecting or live practice actually acts on (opened the
  scan, dismissed the row, booked the recall) — is a known, named
  future consumer of exactly this standing-query materialisation
  substrate. It is deliberately NOT built and NOT demoed because it
  structurally cannot be until real customers generate real interaction
  events; building it now would be measuring nothing. When the first
  customer arrives it MUST be a small configuration of this
  infrastructure — a new StandingQuery kind (e.g.
  kind='conversion_probe') writing rows into briefing_items (or a
  sibling briefing_item_events table) through the SAME run_template +
  resolve_provenance chokepoint, inheriting the same verifiable-
  provenance and tenant-scoping contract — NOT a forgotten requirement
  rediscovered late as a from-scratch analytics build. The substrate
  was shaped in PR D specifically so this is a configuration, not a
  project. This note is the named anchor; the work is correctly
  deferred, not lost. See ONTOLOGY_QUERY_LAYER_POSTMORTEM.md.
═══════════════════════════════════════════════════════════════════════

WHAT IS NOT VERIFIED AT MERGE (unsoftened, post-mortem §E): the
orphaned-source-survives-materialisation guarantee is CODE-PATH-PROVEN
via a test-only injected non-entitled workspace arg, NOT production-
corpus-demonstrated — the production path only iterates entitled
workspaces and the entitled corpus contains no orphan. The autonomous
tick ships env-gated default-off; only the substrate + manual refresh
are proven.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional

from ontology.query import resolve_provenance, run_template

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StandingQuery:
    """One registered standing query. `params` are FIXED at registration
    (never caller input); `kind` is the `briefing_items.kind`
    discriminator and the idempotency-partition discriminator."""

    kind: str
    template_id: str
    params: Dict[str, Any] = field(default_factory=dict)
    description: str = ""


_STANDING: Dict[str, StandingQuery] = {}


def register_standing(sq: StandingQuery) -> None:
    if sq.kind in _STANDING:
        raise ValueError(f"standing query kind {sq.kind!r} already registered")
    _STANDING[sq.kind] = sq


def all_standing() -> List[StandingQuery]:
    return list(_STANDING.values())


def get_standing(kind: str) -> StandingQuery:
    return _STANDING[kind]


# ── The registered set — EXACTLY ONE at merge (locked decision #2) ─────────
# `morning_briefing` → `patients_not_seen_since` is the only template
# proven BOTH data-bearing AND provenance-resolving on an entitled
# workspace (PR D Findings S/E). Vertical-slice discipline: one thing
# proven, not many shallow. `pre_consult` is named-registered-LATER (it
# needs the per-patient UI absent until Phase 4 — registering it now
# would be a registered kind that cannot be exercised, the fake-property
# shape). `conversion_probe` is NAMED-BUT-NOT-REGISTERED (the docstring
# note above; registering it would be the fake-property anti-pattern).
register_standing(StandingQuery(
    kind="morning_briefing",
    template_id="patients_not_seen_since",
    params={"days_since": 180},
    description="Patients not seen in the last 180 days (recall cohort).",
))


def _entitled_workspaces(supabase) -> List[str]:
    """The ONLY workspace source — TRUSTED, never caller input. Every
    workspace whose `practice_capabilities` includes `clinical_query`
    (the same entitlement test the HTTP gate uses). The materialiser
    only ever materialises entitled workspaces — same coherence as
    PR C: a surface narrower-or-equal to the data it exposes."""
    from app.services.entitlements import practice_has_capability

    resp = supabase.table("workspaces").select("id").execute()
    ids = [r["id"] for r in (getattr(resp, "data", None) or []) if r.get("id")]
    out: List[str] = []
    for ws in ids:
        try:
            if practice_has_capability(supabase, ws, "clinical_query"):
                out.append(ws)
        except Exception as e:  # noqa: BLE001 — one bad ws must not starve the rest
            logger.warning("entitlement check failed for %s: %s", ws, e)
    return out


def _rewrite_partition(ws: str, kind: str, as_of: date,
                       template_id: str, template_version: int,
                       rows: List[Any]) -> None:
    """Atomic per-(workspace_id, kind) partition rewrite (locked
    decision #6): DELETE the (ws, kind, as_of) partition then INSERT the
    freshly-resolved rows, in ONE psycopg2 transaction. `with conn:`
    commits on success, rolls back on any exception — a mid-run failure
    leaves the partition exactly as it was, never half-written."""
    import psycopg2

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn:  # transaction boundary
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM briefing_items "
                    "WHERE workspace_id=%s AND kind=%s AND as_of_date=%s",
                    (ws, kind, as_of),
                )
                for r in rows:
                    payload = r.to_dict()
                    src = payload.get("source") or {}
                    cur.execute(
                        "INSERT INTO briefing_items "
                        "(workspace_id, kind, as_of_date, template_id, "
                        " template_version, row_payload, source_status, "
                        " openable, unresolvable_reason, citation) "
                        "VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s)",
                        (ws, kind, as_of, template_id, template_version,
                         json.dumps(payload), src.get("status"),
                         src.get("openable"), src.get("unresolvable_reason"),
                         src.get("citation")),
                    )
    finally:
        conn.close()


def materialise_standing_queries(
    supabase,
    *,
    as_of_date: date,
    only_workspace: Optional[str] = None,
) -> Dict[str, Any]:
    """Materialise every registered standing query for every entitled
    workspace (or just `only_workspace` — used by the manual refresh
    endpoint and by tests). Per (workspace, kind): run the chokepoint,
    resolve, atomically rewrite the partition. Per-(ws,kind) error
    isolation (log + continue, mirrors the document-watcher's per-loop
    discipline) so one bad workspace never starves the rest. Returns a
    stats dict for observability — NEVER raises a per-workspace failure
    into a global abort."""
    workspaces = (
        [only_workspace] if only_workspace
        else _entitled_workspaces(supabase)
    )
    results: Dict[str, Any] = {}
    for ws in workspaces:
        for sq in all_standing():
            key = f"{ws}:{sq.kind}"
            try:
                result = run_template(
                    supabase, sq.template_id, sq.params, workspace_id=ws,
                )
                resolved = resolve_provenance(
                    supabase, result, workspace_id=ws,
                )
                _rewrite_partition(
                    ws, sq.kind, as_of_date,
                    resolved.template_id, resolved.template_version,
                    resolved.rows,
                )
                results[key] = {
                    "rows": resolved.row_count,
                    "unresolvable_count": resolved.unresolvable_count,
                    "superseded_count": resolved.superseded_count,
                }
            except Exception as e:  # noqa: BLE001 — per-(ws,kind) isolation
                logger.warning(
                    "standing materialise failed ws=%s kind=%s: %s",
                    ws, sq.kind, e,
                )
                results[key] = {"error": str(e)}
    return {"as_of_date": str(as_of_date),
            "workspaces": len(workspaces),
            "results": results}
