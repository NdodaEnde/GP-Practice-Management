-- ============================================================================
-- Audit double-write detection — run nightly during the PR 1 → PR 2 window
-- ============================================================================
--
-- During PR 1, every PromoteDocumentToPatientRecord call double-writes:
--   - one row to validation_edit_log (action='approve') via _write_edit_log()
--   - one row to action_audit_log (action_name='PromoteDocumentToPatientRecord')
--     via the ActionExecutor
--
-- The two writers must stay in sync until PR 2 removes the legacy
-- _write_edit_log call. This query catches either side silently breaking:
--
--   - "validation_edit_log only" rows — the legacy writer fired but the
--     ActionExecutor didn't write an audit row. Indicates the executor
--     path was bypassed (someone called promote_extractions directly?)
--     or the audit_log insert silently failed.
--
--   - "action_audit_log only" rows — the executor fired but the legacy
--     _write_edit_log call didn't. Indicates the legacy path was bypassed,
--     which is fine if it was intentional but a sign of drift if it wasn't.
--
-- Expected during the double-write window: ZERO rows.
-- Any rows: investigate immediately.
--
-- This query is retired when PR 2 removes the legacy _write_edit_log
-- write from approve_validation.
-- ============================================================================

WITH window AS (
    -- Look back 24 hours. Increase if running less frequently than nightly.
    SELECT now() - INTERVAL '24 hours' AS since
)
SELECT
    'validation_edit_log only' AS missing_side,
    vel.document_id            AS document_id,
    vel.created_at             AS event_at,
    NULL::uuid                 AS audit_id
  FROM validation_edit_log vel, window
 WHERE vel.action = 'approve'
   AND vel.created_at > window.since
   AND NOT EXISTS (
       SELECT 1
         FROM action_audit_log aal
        WHERE aal.action_name = 'PromoteDocumentToPatientRecord'
          AND aal.parameters->>'document_id' = vel.document_id
          AND aal.started_at BETWEEN vel.created_at - INTERVAL '60 seconds'
                                  AND vel.created_at + INTERVAL '60 seconds'
   )

UNION ALL

SELECT
    'action_audit_log only',
    aal.parameters->>'document_id',
    aal.started_at,
    aal.id
  FROM action_audit_log aal, window
 WHERE aal.action_name = 'PromoteDocumentToPatientRecord'
   AND aal.dry_run = FALSE
   AND aal.outcome = 'success'  -- only successful promotions should double-write
   AND aal.started_at > window.since
   AND NOT EXISTS (
       SELECT 1
         FROM validation_edit_log vel
        WHERE vel.action = 'approve'
          AND vel.document_id = aal.parameters->>'document_id'
          AND vel.created_at BETWEEN aal.started_at - INTERVAL '60 seconds'
                                  AND aal.started_at + INTERVAL '60 seconds'
   )

ORDER BY event_at DESC;
