-- ============================================================================
-- Migration 008 — Digitisation export-job tracking
-- ============================================================================
-- Implements the data-side of the Export Centre's "Recent Export History"
-- view. Today the UI shows hardcoded sample rows because there's no place
-- for export attempts to be recorded.
--
-- This migration adds the tracking table only — the actual FHIR / CSV
-- export action (generate bundle, push to remote, etc) remains in
-- backend/app/services/fhir_export.py and is wired by Phase B.
--
-- Idempotent: safe to re-run.
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS digitisation_export_jobs (
    id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    TEXT         NOT NULL,
    batch_id        TEXT         NOT NULL,                    -- human-readable, e.g. EXP-2026-0431
    format          TEXT         NOT NULL,                    -- fhir_r4 | csv | json
    target_system   TEXT,                                     -- e.g. "Discovery Health (FHIR R4)"
    record_count    INT          NOT NULL DEFAULT 0,
    document_ids    TEXT[]       NOT NULL DEFAULT '{}',       -- which docs were in this export
    status          TEXT         NOT NULL DEFAULT 'queued',   -- queued|running|success|partial|failed
    error_message   TEXT,
    bundle_url      TEXT,                                     -- where the generated bundle landed (Storage / external FHIR)
    requested_by    TEXT,                                     -- user_email at request time
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    metadata        JSONB                                     -- room for format-specific extras (e.g. FHIR endpoint config snapshot)
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'digitisation_export_jobs_format_chk'
    ) THEN
        ALTER TABLE digitisation_export_jobs
            ADD CONSTRAINT digitisation_export_jobs_format_chk
            CHECK (format IN ('fhir_r4', 'csv', 'json'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'digitisation_export_jobs_status_chk'
    ) THEN
        ALTER TABLE digitisation_export_jobs
            ADD CONSTRAINT digitisation_export_jobs_status_chk
            CHECK (status IN ('queued', 'running', 'success', 'partial', 'failed'));
    END IF;
END$$;

COMMENT ON TABLE digitisation_export_jobs IS
    'One row per export request from the Type C Export Centre. Records the '
    'request (what / which docs / where to) plus the run outcome. Real FHIR '
    'bundle bytes live in Storage (bundle_url); this table is the index.';

-- Lookups:
--   1. Workspace history view: ORDER BY created_at DESC, filter by workspace
CREATE INDEX IF NOT EXISTS idx_export_jobs_workspace_created
    ON digitisation_export_jobs (workspace_id, created_at DESC);

--   2. "What's still running" worker poll
CREATE INDEX IF NOT EXISTS idx_export_jobs_status_pending
    ON digitisation_export_jobs (status)
    WHERE status IN ('queued', 'running');

COMMIT;
