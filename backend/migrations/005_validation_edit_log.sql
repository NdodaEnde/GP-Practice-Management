-- ============================================================================
-- Migration 005 — Append-only edit log + frozen AI baseline
-- ============================================================================
-- Implements TRACEABILITY.md item 4 (edit log) + item 5 (original-vs-approved
-- preservation). Required before first paying GP — provides the audit trail
-- regulators (SAHPRA / HPCSA) and malpractice defence both need.
--
-- Two changes:
--   1. extractions_original JSONB on gp_validation_sessions — snapshots the
--      AI's first output at extract time, NEVER modified afterwards. The
--      existing `extractions` column remains the live / approved version.
--      Together they let us answer "what did the AI say vs what did the
--      reviewer approve" forever.
--
--   2. validation_edit_log table — one row per reviewer action (edit, accept,
--      approve, reject). Append-only by convention; no UPDATE or DELETE
--      triggers from the application code path.
--
-- Idempotent: safe to re-run.
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- 1. Frozen AI baseline
-- ----------------------------------------------------------------------------

ALTER TABLE gp_validation_sessions
    ADD COLUMN IF NOT EXISTS extractions_original JSONB;

COMMENT ON COLUMN gp_validation_sessions.extractions_original IS
    'AI extraction output at session creation, NEVER modified after. '
    'Used to answer "what did the AI say vs what did the reviewer approve".';

-- ----------------------------------------------------------------------------
-- 2. Append-only edit log
-- ----------------------------------------------------------------------------

-- Note on column types: digitised_documents.id and gp_validation_sessions.id
-- are TEXT (storing UUID-formatted strings) in the existing schema — see
-- STRATEGY_HEALTHCARE_TIERING_v1.2 §10c "Tech debt: schema UUID/TEXT
-- mismatch". Match those types here so the foreign key works.
CREATE TABLE IF NOT EXISTS validation_edit_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     TEXT        NOT NULL REFERENCES digitised_documents(id) ON DELETE CASCADE,
    session_id      TEXT,                    -- gp_validation_sessions.id at the time of the action
    workspace_id    TEXT        NOT NULL,
    user_email      TEXT,                    -- reviewer who took the action (NULL = system / watcher)
    action          TEXT        NOT NULL CHECK (action IN ('edit', 'accept', 'approve', 'reject', 'reprocess')),
    field_path      TEXT,                    -- e.g. 'patient_demographics.full_names' (NULL for whole-doc actions)
    from_value      JSONB,
    to_value        JSONB,
    notes           TEXT,
    metadata        JSONB,                   -- room for future extensions (e.g. provenance tag, confidence at edit time)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE validation_edit_log IS
    'Append-only audit log of every reviewer action on a validation session. '
    'No UPDATE / DELETE from application code. Required for HPCSA / SAHPRA '
    'audit trail and for active-learning feedback (which fields get corrected most).';

CREATE INDEX IF NOT EXISTS validation_edit_log_document_idx
    ON validation_edit_log (document_id, created_at DESC);

CREATE INDEX IF NOT EXISTS validation_edit_log_workspace_idx
    ON validation_edit_log (workspace_id, created_at DESC);

CREATE INDEX IF NOT EXISTS validation_edit_log_field_idx
    ON validation_edit_log (field_path)
    WHERE field_path IS NOT NULL;

COMMIT;
