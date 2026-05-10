-- ============================================================================
-- Migration 012 — Production-readiness schema completion
-- ============================================================================
-- Several gaps surfaced during the production-readiness pass:
--
-- 1. Search-indexer status visibility on digitised_documents
--    The semantic-search indexer runs as a BackgroundTask and silently
--    succeeds or fails. Surfacing the result on the document row lets
--    the validation panel show "indexed", "indexing failed", "stale".
--
-- 2. encounters.doctor_id (§10c tech debt #3)
--    Cross-doctor analytics needs this. Backfill from AI Scribe metadata
--    when available; nullable for legacy rows.
--
-- 3. gp_invoices.workspace_id (§10c tech debt #2)
--    Cross-tenant data leak risk if a shared report query were built.
--    Backfilled from joined patients/encounters where possible.
--
-- 4. patients.created_at index — patient registry list endpoint orders
--    by created_at DESC; index materially speeds up workspaces with
--    >1k patients.
--
-- Idempotent: safe to re-run.
-- ============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Search-indexer state on digitised_documents
-- ---------------------------------------------------------------------------
ALTER TABLE digitised_documents
    ADD COLUMN IF NOT EXISTS search_indexed_at      TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS search_index_chunks    INT,
    ADD COLUMN IF NOT EXISTS search_index_error     TEXT;

COMMENT ON COLUMN digitised_documents.search_indexed_at IS
    'When the semantic-search indexer last completed. NULL if never. '
    'Re-set on every approval (idempotent indexing).';
COMMENT ON COLUMN digitised_documents.search_index_chunks IS
    'How many chunks landed in document_embeddings on the last index run.';
COMMENT ON COLUMN digitised_documents.search_index_error IS
    'Error message from the most recent failed index run, NULL on success. '
    'Lets the validation history drawer surface silent BackgroundTasks failures.';

-- ---------------------------------------------------------------------------
-- 2. encounters.doctor_id (§10c.3)
-- ---------------------------------------------------------------------------
ALTER TABLE encounters
    ADD COLUMN IF NOT EXISTS doctor_id   TEXT,
    ADD COLUMN IF NOT EXISTS doctor_name TEXT;

COMMENT ON COLUMN encounters.doctor_id IS
    'FK to users.id (logical, not enforced because users.id may be a TEXT '
    'auth0/supabase user id). Populated from AI Scribe metadata or by the '
    'reception check-in flow. Nullable on legacy + digitisation-sourced rows.';

CREATE INDEX IF NOT EXISTS idx_encounters_doctor
    ON encounters (doctor_id, encounter_date DESC)
    WHERE doctor_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 3. gp_invoices.workspace_id (§10c.2)
-- ---------------------------------------------------------------------------
ALTER TABLE gp_invoices
    ADD COLUMN IF NOT EXISTS workspace_id TEXT;

-- Backfill from encounters where possible. Encounters always have
-- workspace_id; gp_invoices joins via encounter_id.
UPDATE gp_invoices i
   SET workspace_id = e.workspace_id
  FROM encounters e
 WHERE i.encounter_id = e.id
   AND i.workspace_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_gp_invoices_workspace
    ON gp_invoices (workspace_id, created_at DESC)
    WHERE workspace_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 4. patient registry list speed-up
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_patients_workspace_created
    ON patients (workspace_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- 5. Export-job push tracking (Phase C — auto-POST to configured FHIR endpoint)
-- ---------------------------------------------------------------------------
-- After the bundle is generated, the worker optionally pushes it to the
-- workspace's default FHIR connection. Push success/failure tracked
-- separately from bundle generation so a failed push doesn't roll back
-- the (still-downloadable) bundle.

ALTER TABLE digitisation_export_jobs
    ADD COLUMN IF NOT EXISTS push_status         TEXT,         -- not_attempted|queued|success|failed
    ADD COLUMN IF NOT EXISTS push_status_code    INT,          -- HTTP status from the FHIR server
    ADD COLUMN IF NOT EXISTS push_error          TEXT,
    ADD COLUMN IF NOT EXISTS pushed_at           TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS push_connection_id  TEXT;         -- which fhir_connection received the push

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'digitisation_export_jobs_push_status_chk'
    ) THEN
        ALTER TABLE digitisation_export_jobs
            ADD CONSTRAINT digitisation_export_jobs_push_status_chk
            CHECK (push_status IS NULL
                OR push_status IN ('not_attempted', 'queued', 'success', 'failed'));
    END IF;
END$$;

COMMIT;
