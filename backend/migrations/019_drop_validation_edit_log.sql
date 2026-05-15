-- ============================================================================
-- Migration 019 — Drop validation_edit_log (PR 3, LAST migration in the PR)
-- ============================================================================
--
-- This migration MUST run last in the PR 3 sequence, after:
--
--   1. Migration 020 (schema additions for patients + prescriptions)
--   2. Migration 021 (ReassignDocument RPCs)
--   3. Migration 022 (MergePatient RPCs)
--   4. Migration 023 (capabilities seed)
--   5. APPLICATION CODE DEPLOY — every _write_edit_log caller is gone;
--      reject/save/reprocess endpoints route through the ActionExecutor;
--      action_audit_log is the single source of truth for all
--      validation-queue mutations.
--
-- Confirm before applying:
--
--   grep -rn "_write_edit_log\|validation_edit_log\.insert\|validation_edit_log\.update" \
--       backend --include="*.py" | grep -v __pycache__
--
--   Must return zero matches. If anything still writes to the table,
--   that data is lost when this migration runs.
--
-- WHAT BREAKS (briefly, until PR 4)
--
--   The `/digitisation/validation/{document_id}/history` endpoint
--   (digitisation.py:670) currently reads from validation_edit_log.
--   Post-migration it returns `history: []` with a deprecation log
--   message. PR 4's audit-trail UI rewires it to query action_audit_log
--   filtered by `affected_objects @> [{type:"Document", id:doc_id}]`.
--
--   This is a temporary regression accepted with the user; the data is
--   not lost — it's all in action_audit_log; only the legacy read path
--   is empty for one PR cycle.
--
-- DESTRUCTIVE — drops the table. Idempotent in that DROP TABLE IF EXISTS
-- is a no-op if the table is already gone.
-- ============================================================================

BEGIN;

-- Indexes are dropped automatically with the table; named here for clarity.
DROP INDEX IF EXISTS idx_validation_edit_log_document;
DROP INDEX IF EXISTS idx_validation_edit_log_session;
DROP INDEX IF EXISTS idx_validation_edit_log_workspace;
DROP INDEX IF EXISTS idx_validation_edit_log_user;

DROP TABLE IF EXISTS validation_edit_log;

COMMIT;
