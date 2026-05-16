"""
run_template() — the single chokepoint every query flows through.

Responsibilities, in order:
  1. Resolve the template from the registry.
  2. Validate caller params against the typed schema (reject unknown
     params; coerce/validate declared ones).
  3. Inject workspace_id as the mandatory first RPC arg — taken from
     the trusted caller context, NEVER from caller-supplied params.
     This is the tenant-scoping invariant: a query physically cannot
     run unscoped because the runner always supplies p_workspace_id.
  4. Call the backing PL/pgSQL function via supabase.rpc().
  5. Map RPC SQLSTATEs to typed QueryError (reusing the action layer's
     classifier so the vocabulary is consistent platform-wide).
  6. Wrap every row in QueryRow with its mandatory Provenance — a row
     that comes back without provenance is a template bug and raises
     here (defence in depth behind the CI invariant test).

This is also the one place a future POPIA access-log decorator would
attach (deliberately deferred — Phase 5 — but the chokepoint exists so
it's a decorator, not a refactor).

Note: per the Phase-0 finding, a freshly-migrated template RPC is
invisible to PostgREST until its schema cache reloads. Callers hitting
a brand-new template may see QueryError(code='template_unavailable');
the migration that ships a template issues NOTIFY pgrst + the deploy
waits. Not retried here — a cold cache in normal operation is an
operational fault, not a per-request condition to paper over.
"""

from __future__ import annotations

from typing import Any, Dict

from ontology.query.registry import get_template
from ontology.query.result import Provenance, QueryResult, QueryRow
from ontology.query.spec import PROVENANCE_COLUMN


class QueryError(Exception):
    def __init__(self, code: str, message: str, context: Dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.context = context or {}


def run_template(
    supabase,
    template_id: str,
    params: Dict[str, Any],
    *,
    workspace_id: str,
) -> QueryResult:
    if not workspace_id:
        # The runner is the tenant-scoping invariant. No workspace =
        # no query, full stop. (Mirrors the PR 5 guard's intent at
        # runtime.)
        raise QueryError(
            "missing_workspace",
            "run_template requires a workspace_id from the trusted "
            "caller context; refusing to run an unscoped query",
        )

    try:
        spec = get_template(template_id)
    except KeyError as e:
        raise QueryError("unknown_template", str(e), {"template_id": template_id})

    # Reject unknown params (typo / injection-shaped input fails closed).
    declared = {p.name for p in spec.params}
    unknown = set(params) - declared
    if unknown:
        raise QueryError(
            "unknown_param",
            f"unknown parameter(s) {sorted(unknown)} for template "
            f"{template_id!r}; accepts {sorted(declared)}",
            {"template_id": template_id},
        )

    # Build the RPC kwargs: workspace first (trusted), then validated params.
    rpc_kwargs: Dict[str, Any] = {"p_workspace_id": workspace_id}
    for p in spec.params:
        try:
            value = p.coerce_and_validate(params.get(p.name))
        except ValueError as ve:
            raise QueryError("invalid_param", str(ve), {"param": p.name})
        rpc_kwargs[p.rpc_arg] = value

    # Execute.
    try:
        resp = supabase.rpc(spec.rpc_name, rpc_kwargs).execute()
    except Exception as exc:  # noqa: BLE001
        # Reuse the action layer's SQLSTATE/HINT → code classifier so the
        # error vocabulary is identical across mutations and queries.
        from app.actions.primitives import _classify_rpc_error
        ed = _classify_rpc_error(exc)
        text = str(exc)
        if "PGRST202" in text:
            raise QueryError(
                "template_unavailable",
                f"template {template_id!r} RPC {spec.rpc_name!r} not in "
                f"PostgREST schema cache — migration must NOTIFY pgrst "
                f"and the deploy must wait for reload",
                {"template_id": template_id, "rpc": spec.rpc_name},
            )
        raise QueryError(ed.code, ed.message, ed.context)

    raw = resp.data if hasattr(resp, "data") else resp
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        raise QueryError(
            "bad_rpc_shape",
            f"template {template_id!r} RPC returned "
            f"{type(raw).__name__}, expected a list of rows",
            {"template_id": template_id},
        )

    rows = []
    for r in raw:
        if not isinstance(r, dict):
            raise QueryError(
                "bad_rpc_shape",
                f"template {template_id!r} returned a non-dict row "
                f"({type(r).__name__})",
                {"template_id": template_id},
            )
        prov_blob = r.get(PROVENANCE_COLUMN)
        try:
            prov = Provenance.from_jsonb(prov_blob)
        except ValueError as ve:
            # Defence in depth behind the CI invariant test: a template
            # whose SQL forgot to build provenance fails loud at runtime
            # rather than silently returning sourceless answers.
            raise QueryError(
                "provenance_missing",
                f"template {template_id!r} row missing/invalid "
                f"provenance: {ve}",
                {"template_id": template_id},
            )
        data = {k: v for k, v in r.items() if k != PROVENANCE_COLUMN}
        rows.append(QueryRow(data=data, provenance=prov))

    return QueryResult(
        template_id=spec.id,
        template_version=spec.version,
        workspace_id=workspace_id,
        rows=rows,
        row_count=len(rows),
        data_maturity=spec.data_maturity,
    )
