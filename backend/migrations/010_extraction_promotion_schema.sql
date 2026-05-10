-- ============================================================================
-- Migration 010 — Schema fixes that unblock structured-data promotion
-- ============================================================================
-- The strategy doc §10c calls this out: `diagnoses`, `vitals`, and
-- `allergies` were originally created with `workspace_id`, `tenant_id`,
-- `patient_id`, `encounter_id` as UUID NOT NULL — but the live
-- `patients`, `workspaces`, and `tenants` tables all use TEXT IDs (e.g.
-- 'demo-gp-workspace-001'). Effect: every INSERT into these tables
-- against the demo workspace fails with `22P02 invalid input syntax
-- for type uuid`.
--
-- We've been unable to promote validated digitisation extractions into
-- these tables for that reason — the data sits trapped in
-- `gp_validation_sessions.extractions` JSONB and analytics / patient
-- EHR views see an empty world.
--
-- This migration converts all those columns from UUID → TEXT. Existing
-- UUID values become their canonical string representation
-- ('e8f3...c2'), so no data is lost.
--
-- Idempotent: safe to re-run (each ALTER is guarded with a type check).
--
-- Affected: diagnoses (0 rows), vitals (0 rows), allergies (4 rows).
-- ============================================================================

BEGIN;

-- Helper that flips a column from UUID → TEXT only if it's currently UUID.
-- Wraps the migration so re-runs are no-ops.
CREATE OR REPLACE FUNCTION _alter_uuid_to_text(p_table TEXT, p_column TEXT)
RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE
    cur_type TEXT;
BEGIN
    SELECT data_type INTO cur_type
      FROM information_schema.columns
     WHERE table_schema = 'public'
       AND table_name = p_table
       AND column_name = p_column;
    IF cur_type IS NULL THEN
        RAISE NOTICE 'Column %.% does not exist, skipping', p_table, p_column;
        RETURN;
    END IF;
    IF cur_type = 'uuid' THEN
        EXECUTE format(
            'ALTER TABLE %I ALTER COLUMN %I TYPE TEXT USING %I::text',
            p_table, p_column, p_column);
        RAISE NOTICE 'Converted %.% from uuid to text', p_table, p_column;
    ELSE
        RAISE NOTICE 'Column %.% already %, skipping', p_table, p_column, cur_type;
    END IF;
END$$;

-- ---------------------------------------------------------------------------
-- diagnoses
-- ---------------------------------------------------------------------------
SELECT _alter_uuid_to_text('diagnoses', 'tenant_id');
SELECT _alter_uuid_to_text('diagnoses', 'workspace_id');
SELECT _alter_uuid_to_text('diagnoses', 'patient_id');
SELECT _alter_uuid_to_text('diagnoses', 'encounter_id');
SELECT _alter_uuid_to_text('diagnoses', 'source_document_id');

-- ---------------------------------------------------------------------------
-- vitals
-- ---------------------------------------------------------------------------
-- vitals.bmi is a GENERATED ALWAYS column; the columns it depends on
-- (weight_kg, height_cm) are NUMERIC so unaffected by the type changes
-- below. No drop+recreate needed.
SELECT _alter_uuid_to_text('vitals', 'tenant_id');
SELECT _alter_uuid_to_text('vitals', 'workspace_id');
SELECT _alter_uuid_to_text('vitals', 'patient_id');
SELECT _alter_uuid_to_text('vitals', 'encounter_id');

-- ---------------------------------------------------------------------------
-- allergies (4 existing rows — UUID values become their canonical TEXT form)
-- ---------------------------------------------------------------------------
SELECT _alter_uuid_to_text('allergies', 'tenant_id');
SELECT _alter_uuid_to_text('allergies', 'workspace_id');
SELECT _alter_uuid_to_text('allergies', 'patient_id');
SELECT _alter_uuid_to_text('allergies', 'source_document_id');

-- ---------------------------------------------------------------------------
-- Add columns the promoter writes that may be missing from older schemas.
-- All idempotent.
-- ---------------------------------------------------------------------------

-- diagnoses needs source_document_id for traceability back to the source PDF
ALTER TABLE diagnoses
    ADD COLUMN IF NOT EXISTS source_document_id TEXT;

-- vitals: source flag + source_document_id + a free-text consultation date
-- (the JSONB has consultation_date strings that may not parse cleanly to
-- TIMESTAMPTZ for measured_datetime — keep both)
ALTER TABLE vitals
    ADD COLUMN IF NOT EXISTS source_document_id TEXT,
    ADD COLUMN IF NOT EXISTS consultation_date_text TEXT,
    ADD COLUMN IF NOT EXISTS hba1c             NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS blood_glucose_fasting NUMERIC(5,2);

-- prescriptions: ensure source columns exist (used by promoter)
ALTER TABLE prescriptions
    ADD COLUMN IF NOT EXISTS source              TEXT,
    ADD COLUMN IF NOT EXISTS source_document_id  TEXT;

-- prescription_items: source columns + ATC ride-along (helps analytics
-- without re-joining nappi_codes for digitised rows that may not have
-- a real NAPPI yet)
ALTER TABLE prescription_items
    ADD COLUMN IF NOT EXISTS source              TEXT,
    ADD COLUMN IF NOT EXISTS source_document_id  TEXT,
    ADD COLUMN IF NOT EXISTS atc_code            TEXT;

-- allergies already has source / source_document_id from
-- phase1_patient_safety_migration.sql — no-op here.

-- ---------------------------------------------------------------------------
-- Indexes for promoter idempotency: looking up by source_document_id is the
-- standard "have we already promoted this doc?" check.
-- ---------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_diagnoses_source_doc
    ON diagnoses (source_document_id)
    WHERE source_document_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_vitals_source_doc
    ON vitals (source_document_id)
    WHERE source_document_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_allergies_source_doc
    ON allergies (source_document_id)
    WHERE source_document_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_prescriptions_source_doc
    ON prescriptions (source_document_id)
    WHERE source_document_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- digitised_documents: ensure patient_id linkage column exists (the
-- /gp/validation/confirm-match flow already populates this for healthcare-
-- app users; promoter wants it set by Type C path too).
-- ---------------------------------------------------------------------------

ALTER TABLE digitised_documents
    ADD COLUMN IF NOT EXISTS patient_id   TEXT,
    ADD COLUMN IF NOT EXISTS encounter_id TEXT;

CREATE INDEX IF NOT EXISTS idx_digitised_documents_patient
    ON digitised_documents (patient_id)
    WHERE patient_id IS NOT NULL;

DROP FUNCTION _alter_uuid_to_text(TEXT, TEXT);

COMMIT;
