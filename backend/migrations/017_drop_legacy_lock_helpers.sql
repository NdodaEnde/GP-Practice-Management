-- ============================================================================
-- Migration 017 — Drop legacy advisory-lock helpers from migration 014
-- ============================================================================
--
-- ORDERING — RUN STRICTLY AFTER:
--
--   1. Migration 015 (introduces execute_action_promote_document with
--      SELECT...FOR UPDATE NOWAIT — the replacement for advisory locks)
--   2. Migration 016 (idempotent data seed, no dependency either way)
--   3. PR 2 application code deploy (executor.py without _acquire_lock,
--      primitives.py with the RPC-dispatch apply())
--
-- Reason for the ordering: dropping the advisory-lock helpers before
-- the application code stops calling them would crash any in-flight
-- promote. The helpers are NO-OPed at the Python layer in PR 1 (no real
-- mutual exclusion is delivered — see Phase 0 outcome in executor.py),
-- but Migration 014 still defines them in the database. After PR 2's
-- code lands, no caller invokes them anymore. This migration removes
-- the dead RPCs.
--
-- Confirm before applying:
--   - `git log --oneline backend/app/actions/executor.py` shows the
--     PR 2 commit that deletes _acquire_lock().
--   - `grep -rn "action_try_advisory_lock\|action_advisory_unlock"
--      backend/app backend/scripts` returns no matches (test file
--      reference in test_advisory_lock_semantics.py is allowed — that
--      test is the Phase 0 verification, marked slow_integration, runs
--      only against the OLD schema before 017 applies).
--
-- This migration is destructive. The advisory-lock RPCs are not in use
-- elsewhere in the codebase (verified via grep), and Phase 0 confirmed
-- they don't deliver the mutual-exclusion property anyway, so the drop
-- is risk-free in practice.
--
-- Idempotent: DROP FUNCTION IF EXISTS.
-- ============================================================================

BEGIN;

DROP FUNCTION IF EXISTS action_try_advisory_lock(TEXT, TEXT);
DROP FUNCTION IF EXISTS action_advisory_unlock(TEXT, TEXT);

COMMIT;
