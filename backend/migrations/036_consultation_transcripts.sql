-- ============================================================================
-- Migration 036 — consultation_transcripts (AI Scribe) onto Supabase
-- ============================================================================
--
-- AI Scribe's save-consultation stored the verbatim transcript in MongoDB
-- (db.consultation_transcripts) — the last AI-scribe Mongo write. Migrated onto
-- the foundation: one Supabase table, tenant-scoped by workspace_id from the
-- caller's token, RLS deny-all underneath (see 033 for the threat model).
--
-- The structured SOAP note already lives in clinical_notes; this table keeps the
-- raw verbatim transcript linked to the encounter as a medico-legal record.
--
-- (The handler's separate Mongo db.audit_events write is NOT migrated — it had
-- no reader, no Supabase home, and used DEMO ids; dropped, same call as the
-- reception-queue rebuild.)
--
-- Idempotent: safe to re-run.
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS consultation_transcripts (
    id             UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id   TEXT         NOT NULL,
    tenant_id      TEXT,
    encounter_id   TEXT         NOT NULL,
    patient_id     TEXT         NOT NULL,
    transcription  TEXT,
    soap_notes     TEXT,
    doctor_name    TEXT,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_consultation_transcripts_encounter
    ON consultation_transcripts (workspace_id, encounter_id);

-- RLS deny-all (service_role / postgres bypass) — identical posture to 033.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relname = 'consultation_transcripts' AND c.relrowsecurity = FALSE
    ) THEN
        EXECUTE 'ALTER TABLE public.consultation_transcripts ENABLE ROW LEVEL SECURITY';
    END IF;
END $$;

COMMIT;
