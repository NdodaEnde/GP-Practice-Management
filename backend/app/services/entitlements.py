"""
entitlements.py — Python helpers wrapping the SurgiScan entitlement SQL functions.

The authoritative source of truth is the SQL functions:
  - practice_has_capability(p_practice_id TEXT, p_capability_id TEXT) -> BOOLEAN
  - practice_capabilities(p_practice_id TEXT)                         -> TEXT[]

These thin Python wrappers exist so the FastAPI codebase doesn't have to know
the JSON shape of supabase-py RPC responses. Use them anywhere the application
needs to gate on entitlements.

See:
  - backend/migrations/001_entitlements_core.sql      (function definitions)
  - backend/migrations/002_practice_capabilities_list.sql
  - /Users/luzuko/.claude/plans/we-are-a-healthtech-sparkling-shamir.md
    (Phase 2 — Capability gating section)
"""

from typing import List, Optional

from supabase import Client


def practice_has_capability(
    client: Client,
    practice_id: str,
    capability_id: str,
) -> bool:
    """Return True iff the practice has an active, non-expired entitlement
    granting the named capability.

    Single-cap check. Use this in FastAPI dependencies (require_capability)
    where you only care about one capability.
    """
    res = client.rpc(
        "practice_has_capability",
        {
            "p_practice_id": practice_id,
            "p_capability_id": capability_id,
        },
    ).execute()
    # supabase-py returns the function's scalar result in res.data
    return bool(res.data)


def practice_capabilities(
    client: Client,
    practice_id: str,
) -> List[str]:
    """Return the deduplicated, sorted list of capability IDs granted to the
    practice via active entitlements. Empty list if the practice has no
    active entitlements.

    Use this to hydrate the user context (e.g. /api/auth/me response) so the
    frontend can render capability-aware UX without per-component roundtrips.
    """
    res = client.rpc(
        "practice_capabilities",
        {"p_practice_id": practice_id},
    ).execute()
    # Postgres TEXT[] comes back as a Python list
    return list(res.data) if res.data else []


__all__ = ["practice_has_capability", "practice_capabilities"]
