-- ============================================================================
-- Migration 010b — encounters.source_document_id (promoter idempotency)
-- ============================================================================
-- The promoter creates one encounter per consultation_date in the JSONB.
-- Without source_document_id, re-running the approval (idempotency) would
-- accumulate encounter rows on every retry. This adds the column + index
-- and back-fills nothing — encounters created before this migration stay
-- as-is (orphaned legacy rows the user can clean up manually).
--
-- Idempotent: safe to re-run.
-- ============================================================================

BEGIN;

ALTER TABLE encounters
    ADD COLUMN IF NOT EXISTS source_document_id TEXT;

CREATE INDEX IF NOT EXISTS idx_encounters_source_doc
    ON encounters (source_document_id)
    WHERE source_document_id IS NOT NULL;

COMMIT;
