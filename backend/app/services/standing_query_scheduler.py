"""
standing_query_scheduler — Phase 3 PR D, decision #3 (D-W1).

A new small INDEPENDENT async tick that materialises the registered
standing queries on an interval. It is started from the SAME
`@app.on_event("startup")` host as the document watcher (same process,
same lifecycle pattern: module singleton + asyncio.create_task +
shutdown-cancel) — NOT a new OS daemon, NOT pg_cron (rejected-by-default).

It is NOT bolted into `DocumentWatcher`'s private loop because that
watcher is a single-workspace document-ingestion singleton hard-bound to
DEMO_WORKSPACE_ID (PR D Finding W); entangling a multi-tenant
materialiser into it would inherit that single-workspace binding and
mix two unrelated concerns.

SHIPS DISABLED — structurally. `start_standing_query_scheduler` checks
`settings.STANDING_QUERY_TICK_ENABLED` FIRST; with it False (the merge
default) it logs and returns WITHOUT creating a task — so no loop runs,
no materialisation happens autonomously, the merge proves only the
substrate + the manual `POST /api/query/briefing/refresh` path.
Enabling autonomous operation is a deliberate operator/governance act
(one env flag) against already-proven code — decision #3's reasoning:
build the inert substrate now so it is a configuration, not a future
from-scratch build against cold context (the same logic as PR C
shipping the NL classifier disabled-but-built).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_scheduler_task: Optional[asyncio.Task] = None
_running: bool = False


async def _tick_loop(supabase) -> None:
    """`while _running: materialise; sleep`. Per-iteration try/except so
    one bad cycle never kills the loop (mirrors the document-watcher's
    per-loop discipline). as_of_date is the UTC wall-clock date
    (decision #1)."""
    from app.core.config import settings
    from ontology.query.standing import materialise_standing_queries

    interval = max(60, int(settings.STANDING_QUERY_TICK_INTERVAL))
    logger.info("standing-query tick loop started (interval=%ss)", interval)
    while _running:
        try:
            as_of = datetime.now(timezone.utc).date()
            stats = materialise_standing_queries(supabase, as_of_date=as_of)
            logger.info("standing-query materialise: %s", stats)
        except Exception as e:  # noqa: BLE001 — one bad cycle must not kill the loop
            logger.warning("standing-query tick failed: %s", e)
        await asyncio.sleep(interval)


async def start_standing_query_scheduler(supabase) -> None:
    """THE GATE. Flag off (merge default) ⇒ no task created, no loop,
    no autonomous materialisation. Flag on ⇒ one tick task on the
    existing event-loop host. Mirrors start_document_watcher's
    singleton+create_task pattern."""
    global _scheduler_task, _running
    from app.core.config import settings

    if not settings.STANDING_QUERY_TICK_ENABLED:
        logger.info(
            "standing-query tick DISABLED (STANDING_QUERY_TICK_ENABLED "
            "off — merge default). Substrate + manual "
            "/api/query/briefing/refresh only; no autonomous loop."
        )
        return
    if _scheduler_task is not None:
        return
    _running = True
    _scheduler_task = asyncio.create_task(_tick_loop(supabase))
    logger.info("standing-query tick scheduler started")


async def stop_standing_query_scheduler() -> None:
    """Mirrors stop_document_watcher: stop the loop, cancel the task."""
    global _scheduler_task, _running
    _running = False
    if _scheduler_task is not None:
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
        _scheduler_task = None
