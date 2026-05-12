"""
Phase 0 — Advisory lock semantics verification.

THIS TEST IS THE GATE for the entire ActionExecutor PR. Before any
executor code commits to using session-scoped advisory locks, this
test runs against the real Supabase instance to verify whether the
chosen locking model is observable across HTTP-pooled requests.

Why this matters
----------------

Supabase's Python client uses HTTP-backed PostgREST. Each
`supabase.rpc(...)` call is an independent HTTP request that PostgREST
routes through a connection pool. Session-scoped advisory locks acquired
in one request may or may not be visible in a second request — depends
on whether PostgREST's pooling returns connections to the pool between
requests, returns them to the SAME client, holds them per-session, or
something else.

Run mode
--------

    RUN_INTEGRATION=1 pytest backend/tests/test_advisory_lock_semantics.py -m slow_integration -s

Required:
    - SUPABASE_URL, SUPABASE_SERVICE_KEY env vars
    - Migration 014 applied to dev DB (the action_try_advisory_lock and
      action_advisory_unlock functions must exist)

Outcomes
--------

LOAD-BEARING test: `test_lock_visible_across_pooled_requests`. This is
the one whose result pins the executor's locking approach.

  - If it PASSES (lock acquired by Client A IS visible to Client B
    through PostgREST's HTTP pool): executor.py's current advisory-lock
    approach works. Document outcome in PR description and proceed.

  - If it FAILS (Client B can also acquire the "same" lock because the
    sessions are not shared): executor.py must pivot to
    `SELECT ... FOR UPDATE NOWAIT` on the source document row. Pre-designed
    path in plan §2.6. Document outcome in PR description before
    refactoring.

The supplementary `test_lock_visible_to_raw_postgres` check confirms
"the lock exists in the DB at all" — useful for diagnosing failures
of the load-bearing test but not the load-bearing assertion.
"""

from __future__ import annotations

import os
import time
import uuid

import pytest


pytestmark = pytest.mark.slow_integration


def _try_acquire(client, action_name: str, resource_key: str) -> bool:
    """Call the action_try_advisory_lock RPC, normalising the various
    shapes supabase-py can return."""
    result = client.rpc(
        "action_try_advisory_lock",
        {"p_action_name": action_name, "p_resource_key": resource_key},
    ).execute()
    data = result.data
    if isinstance(data, bool):
        return data
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict):
            return bool(next(iter(first.values()), False))
        return bool(first)
    return bool(data)


def _release(client, action_name: str, resource_key: str) -> None:
    client.rpc(
        "action_advisory_unlock",
        {"p_action_name": action_name, "p_resource_key": resource_key},
    ).execute()


def test_lock_can_be_acquired_and_released(supabase_client):
    """Sanity: the advisory-lock RPCs exist and round-trip."""
    action_name = "TestProbe"
    resource_key = f"probe-{uuid.uuid4().hex[:8]}"

    acquired = _try_acquire(supabase_client, action_name, resource_key)
    assert acquired is True, "first acquisition should always succeed"

    _release(supabase_client, action_name, resource_key)

    # After release, re-acquisition should succeed
    re_acquired = _try_acquire(supabase_client, action_name, resource_key)
    assert re_acquired is True, "after release, re-acquisition should succeed"
    _release(supabase_client, action_name, resource_key)


def test_lock_visible_across_pooled_requests(supabase_client, supabase_client_b):
    """LOAD-BEARING — does Supabase HTTP pooling let session-scoped
    advisory locks be observed across two independent client instances?

    Setup:
      - Client A acquires advisory lock on key K.
      - Client B (independent supabase.Client instance, same URL +
        service key, separate HTTP request) attempts to acquire the
        same lock K.

    If the lock is visible to B (B's acquisition returns False),
    session-scoped advisory locks survive HTTP pooling and the
    executor's plan-as-written stands.

    If the lock is NOT visible to B (B's acquisition returns True),
    the pool is sharing sessions in a way that defeats session-scoped
    locks. The executor must pivot to SELECT ... FOR UPDATE NOWAIT
    (pre-designed in plan §2.6).
    """
    action_name = "TestProbe"
    resource_key = f"probe-cross-{uuid.uuid4().hex[:8]}"

    # Client A acquires
    a_acquired = _try_acquire(supabase_client, action_name, resource_key)
    assert a_acquired is True, "client A should acquire the lock first"

    try:
        # Client B attempts the same lock — this is the load-bearing assertion
        b_acquired = _try_acquire(supabase_client_b, action_name, resource_key)

        # Record the outcome explicitly in the test output (visible with -s)
        if b_acquired:
            print()
            print("─" * 70)
            print("PHASE 0 OUTCOME: lock NOT visible across pooled requests.")
            print("Executor must use SELECT ... FOR UPDATE NOWAIT on source")
            print("document row (plan §2.6 pivot path).")
            print("─" * 70)
            # Release Client B's lock so we leave the system clean
            _release(supabase_client_b, action_name, resource_key)
        else:
            print()
            print("─" * 70)
            print("PHASE 0 OUTCOME: lock IS visible across pooled requests.")
            print("Executor's session-scoped advisory lock approach stands.")
            print("─" * 70)

        # The assertion: lock SHOULD be visible to B (lock acquisition returns False)
        # If this fails, the executor's locking approach needs to pivot per plan §2.6.
        # We do NOT skip the test on failure — failure is the signal to pivot.
        assert b_acquired is False, (
            "Lock acquired by Client A was not visible to Client B. "
            "Supabase HTTP pooling does not preserve session-scoped advisory locks. "
            "The executor must pivot to SELECT ... FOR UPDATE NOWAIT per plan §2.6."
        )
    finally:
        # Always release Client A's lock
        _release(supabase_client, action_name, resource_key)


def test_locks_with_different_keys_dont_conflict(supabase_client, supabase_client_b):
    """Different resource_keys yield independent locks. Sanity check
    that the hash key isn't accidentally collapsing distinct keys."""
    action_name = "TestProbe"
    key_a = f"probe-a-{uuid.uuid4().hex[:8]}"
    key_b = f"probe-b-{uuid.uuid4().hex[:8]}"

    a_acquired = _try_acquire(supabase_client, action_name, key_a)
    b_acquired = _try_acquire(supabase_client_b, action_name, key_b)

    try:
        assert a_acquired is True
        assert b_acquired is True
    finally:
        _release(supabase_client, action_name, key_a)
        _release(supabase_client_b, action_name, key_b)
