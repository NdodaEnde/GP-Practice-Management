"""
query — the HTTP surface for the Phase-3 query layer (PR A).

One endpoint that matters: `POST /api/query/run`. It is the reason PR #13
could not merge as-is. The runner and the provenance contract are sound,
but a query result a clinician can act on did not exist over HTTP — a
Python REPL is not the binding constraint; a demo doctor clicking a
source is. This endpoint makes the safe artifact reachable, and reachable
*only* in its safe form: every row comes back with its provenance
resolved to an openable scan or an explicitly, visibly unresolvable
marker — never a silent dead link — and the envelope carries a
cohort-level `unresolvable_count` so the dead-link signal is visible at
the altitude a clinician actually reads a 40-row answer.

Security shape, deliberately tight (it is the highest-blast-radius read
surface in the system — it runs cross-cutting clinical queries):

  * `workspace_id` is taken from the authenticated user ONLY, never from
    the request body. A forged body workspace is structurally inert: the
    request model has no such field and the runner is handed the auth
    workspace. Tenant scope is not a check here, it is the absence of any
    other path.
  * Gated on the `clinical_query` capability — explicit-grant, NOT in the
    foundation set (locked decision #4; same posture as PR 3's
    `patient_admin`).
  * Per-user rate limited (same in-process sliding-window pattern as
    digitisation `/search`).

Read-only by construction: this does NOT route through the
ActionExecutor (queries are not actions; no audit row). `run_template`
is the one chokepoint a future POPIA access-log decorator attaches to
(Phase 5 — deferred, chokepoint already exists).
"""

from __future__ import annotations

import os
import time as _time
from collections import deque as _deque
from threading import Lock as _Lock
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.auth import require_capability
from ontology.query import QueryError, resolve_provenance, run_template

router = APIRouter(prefix="/api/query", tags=["Query Layer"])


# Lazy supabase client — mirrors clinical_actions._sb(). Avoids
# hard-failing at import time during test collection when env is unset.
_supabase = None


def _sb():
    global _supabase
    if _supabase is None:
        from supabase import create_client

        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get(
            "SUPABASE_KEY"
        )
        if not url or not key:
            raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_KEY missing")
        _supabase = create_client(url, key)
    return _supabase


# ---------------------------------------------------------------------------
# Per-user rate limiter — verbatim shape of digitisation._enforce_search_rate_limit.
# Query execution is cheap but a runaway frontend or a scripted caller
# should not be able to enumerate a practice's cohorts unbounded.
# ---------------------------------------------------------------------------
_rate_lock = _Lock()
_rate_state: Dict[str, _deque] = {}
_RATE_WINDOW_S = 60
_RATE_MAX = 30


def _enforce_rate_limit(user_email: str) -> None:
    now = _time.monotonic()
    with _rate_lock:
        bucket = _rate_state.setdefault(user_email, _deque())
        while bucket and now - bucket[0] > _RATE_WINDOW_S:
            bucket.popleft()
        if len(bucket) >= _RATE_MAX:
            retry = int(_RATE_WINDOW_S - (now - bucket[0])) + 1
            raise HTTPException(
                status_code=429,
                detail=f"Query rate limit: {_RATE_MAX}/min. Retry in {retry}s.",
                headers={"Retry-After": str(retry)},
            )
        bucket.append(now)


# QueryError.code → HTTP status. Kept explicit (not a catch-all) so the
# vocabulary is auditable: a template bug is a 500, a caller mistake is a
# 4xx, a cold PostgREST cache is a retryable 503.
_CODE_TO_STATUS: Dict[str, int] = {
    "unknown_template": status.HTTP_404_NOT_FOUND,
    "missing_workspace": status.HTTP_400_BAD_REQUEST,
    "unknown_param": status.HTTP_422_UNPROCESSABLE_CONTENT,
    "invalid_param": status.HTTP_422_UNPROCESSABLE_CONTENT,
    "provenance_missing": status.HTTP_500_INTERNAL_SERVER_ERROR,
    "bad_rpc_shape": status.HTTP_500_INTERNAL_SERVER_ERROR,
    "template_unavailable": status.HTTP_503_SERVICE_UNAVAILABLE,
}
_DEFAULT_ERROR_STATUS = status.HTTP_400_BAD_REQUEST


class QueryRunRequest(BaseModel):
    """Note the absence of `workspace_id`. It is intentional and
    load-bearing: the only place a workspace can come from is the
    authenticated user. A client that adds workspace_id to the body
    achieves nothing — the field does not exist on this model and the
    runner is never handed body data for scoping."""

    template_id: str = Field(..., min_length=1)
    params: Dict[str, Any] = Field(default_factory=dict)


@router.get("/templates")
async def list_templates(
    current_user: dict = Depends(require_capability("clinical_query")),
):
    """The closed set of query shapes this practice may run. Read-only;
    no data, just the registry — lets a UI (and PR C's NL layer) discover
    what is answerable instead of guessing."""
    from ontology.query import all_templates

    return {
        "templates": [
            {
                "id": t.id,
                "version": t.version,
                "description": t.description,
                "data_maturity": t.data_maturity,
                "params": [
                    {
                        "name": p.name,
                        "type": p.py_type.__name__,
                        "required": p.required,
                        "default": p.default,
                    }
                    for p in t.params
                ],
            }
            for t in all_templates()
        ]
    }


@router.post("/run")
async def run_query(
    body: QueryRunRequest,
    current_user: dict = Depends(require_capability("clinical_query")),
):
    """Run a registered query template, scoped to the caller's workspace,
    and return every row with its provenance resolved (openable scan or
    visible unresolvable marker) plus the cohort-level unresolvable_count.
    """
    _enforce_rate_limit(current_user.get("email") or "anonymous")

    workspace_id = current_user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No workspace context",
        )

    supabase = _sb()

    try:
        result = run_template(
            supabase,
            body.template_id,
            body.params or {},
            workspace_id=workspace_id,
        )
    except QueryError as qe:
        raise HTTPException(
            status_code=_CODE_TO_STATUS.get(qe.code, _DEFAULT_ERROR_STATUS),
            detail={
                "error": qe.code,
                "message": qe.message,
                "context": qe.context,
            },
        )

    # The safe/unsafe difference: a result NEVER leaves this process
    # without provenance resolved. resolve_provenance does not raise on a
    # missing/odd document — it renders it visibly unresolvable.
    resolved = resolve_provenance(
        supabase, result, workspace_id=workspace_id
    )
    return resolved.to_dict()


class QueryAskRequest(BaseModel):
    """PR C. Note the absence of `workspace_id` — same load-bearing
    reason as QueryRunRequest: the only place a workspace can come from
    is the authenticated user; neither the body nor the LLM can supply
    it. `question` may itself be PII (a patient name); with the NL flag
    off it goes nowhere (the disabled-default IS the boundary)."""

    question: str = Field(..., min_length=1, max_length=512)


@router.post("/ask")
async def ask_query(
    body: QueryAskRequest,
    current_user: dict = Depends(require_capability("clinical_query")),
):
    """PR C — thinnest NL surface. SHIPS DISABLED. Maps the question to
    ONE registered template via a classifier constrained to the closed
    registry enum (never SQL/free-form), then runs it through the
    IDENTICAL `run_template` + `resolve_provenance` chokepoint `/run`
    uses — there is NO other path to data, so NL answers structurally
    inherit the verifiable-provenance contract.

    Capability: `clinical_query` (reused, NOT a new capability). This is
    the coherent choice and it pays twice: PR A's
    `module_digitisation`-does-NOT-entail-`clinical_query` Type-C ratchet
    automatically covers this NL surface by construction — the written
    Type-C customer promise is enforced here for free, zero new ratchet
    code, *because* the capability was reused rather than minted.

    With `NL_QUERY_LLM_ENABLED` off (merge default) `classify_question`
    hard-refuses on line 1 — no client, no network, the question text
    goes nowhere.
    """
    from app.services.nl_query import (
        NLClassification,
        NLRefusal,
        classify_question,
    )

    _enforce_rate_limit(current_user.get("email") or "anonymous")

    workspace_id = current_user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No workspace context",
        )

    outcome = classify_question(body.question)

    if isinstance(outcome, NLRefusal):
        # Refusal (disabled / out-of-set / low-confidence) always carries
        # the answerable list; never a 500, never a silent guess.
        code = (status.HTTP_403_FORBIDDEN
                if outcome.reason == "nl_disabled"
                else status.HTTP_422_UNPROCESSABLE_CONTENT)
        raise HTTPException(status_code=code, detail=outcome.to_dict())

    # Successful classification: feed the SAME chokepoint /run uses.
    # The classifier passed params uninterpreted; the runner validates.
    assert isinstance(outcome, NLClassification)
    supabase = _sb()
    try:
        result = run_template(
            supabase,
            outcome.template_id,
            outcome.params or {},
            workspace_id=workspace_id,
        )
    except QueryError as qe:
        raise HTTPException(
            status_code=_CODE_TO_STATUS.get(qe.code, _DEFAULT_ERROR_STATUS),
            detail={
                "error": qe.code,
                "message": qe.message,
                "context": qe.context,
            },
        )

    resolved = resolve_provenance(
        supabase, result, workspace_id=workspace_id
    )
    out = resolved.to_dict()
    # Honest: the answer carries HOW the NL was mapped, so the caller
    # can see the interpretation (and catch a misclassification — the
    # failure mode no structural gate can see).
    out["interpreted_as"] = {
        "template_id": outcome.template_id,
        "params": outcome.params,
    }
    return out


@router.post("/briefing/refresh")
async def refresh_briefing(
    current_user: dict = Depends(require_capability("clinical_query")),
):
    """PR D — manually materialise the registered standing queries for
    the caller's workspace (the autonomous tick ships DISABLED; this is
    the proven path at merge). Mirrors /run's auth/gate/tenant exactly:
    `workspace_id` from `current_user` ONLY (no body — load-bearing,
    same reason as QueryRunRequest); reuses `clinical_query` (decision
    #4 — the recognised design invariant: a new read surface that
    reaches clinical data reuses `clinical_query` so PR A's
    `module_digitisation`-does-NOT-entail-`clinical_query` Type-C
    ratchet propagates the written Type-C customer promise to it for
    free, by construction, zero per-surface ratchet code). The
    materialiser rides the SAME run_template+resolve_provenance
    chokepoint — no new data path. Read-only-derived; no ActionExecutor.
    """
    from datetime import datetime, timezone

    from ontology.query.standing import materialise_standing_queries

    _enforce_rate_limit(current_user.get("email") or "anonymous")
    workspace_id = current_user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No workspace context",
        )
    as_of = datetime.now(timezone.utc).date()
    return materialise_standing_queries(
        _sb(), as_of_date=as_of, only_workspace=workspace_id,
    )


@router.get("/briefing")
async def get_briefing(
    kind: Optional[str] = None,
    as_of_date: Optional[str] = None,
    current_user: dict = Depends(require_capability("clinical_query")),
):
    """PR D — read the materialised briefing rows for the caller's
    workspace. Each `row_payload` was provenance-resolved at
    materialisation time (it was written by the chokepoint), so the
    rows inherit the verifiable-provenance contract — there is no other
    path to data. `.eq("workspace_id", …)` is the tenant scope (the
    chain carries it, so it adds zero new PR-5-ratchet BASELINE keys)."""
    workspace_id = current_user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No workspace context",
        )
    q = (
        _sb().table("briefing_items").select("*")
        .eq("workspace_id", workspace_id)
    )
    if kind:
        q = q.eq("kind", kind)
    if as_of_date:
        q = q.eq("as_of_date", as_of_date)
    resp = q.order("materialised_at", desc=True).execute()
    rows = getattr(resp, "data", None) or []
    return {"workspace_id": workspace_id, "count": len(rows), "items": rows}
