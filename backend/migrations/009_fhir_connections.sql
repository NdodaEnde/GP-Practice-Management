-- ============================================================================
-- Migration 009 — FHIR connections (Type C downstream EHR push)
-- ============================================================================
-- Type C customers buy SurgiScan to digitise paper records and push the
-- structured data into their existing EHR (TrakCare, Practice Perfect,
-- Healthbridge, GoodX, Discovery's FHIR endpoint, etc). They need to
-- configure WHERE the data goes and HOW we authenticate to it.
--
-- This migration creates the connection table. Phase A populates name,
-- URL, environment, and auth_method (no credentials yet). Phase B will
-- add credential storage (Supabase Vault or equivalent) and actually
-- exercise the connection via the export worker.
--
-- One workspace can have multiple connections (e.g. sandbox + production)
-- but only one can be marked is_default — that's the one Export Centre
-- targets when no specific connection is chosen.
--
-- Idempotent: safe to re-run.
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS digitisation_fhir_connections (
    id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    TEXT         NOT NULL,
    name            TEXT         NOT NULL,                  -- e.g. "TrakCare Cape Town Clinic"
    fhir_url        TEXT         NOT NULL,                  -- e.g. "https://endpoint.health/fhir"
    environment     TEXT         NOT NULL DEFAULT 'sandbox',-- sandbox|staging|production
    auth_method     TEXT         NOT NULL DEFAULT 'none',   -- none|basic|bearer|oauth2_client_credentials|smart_on_fhir
    is_default      BOOLEAN      NOT NULL DEFAULT FALSE,    -- one default per workspace; export uses this when not specified
    last_test_at    TIMESTAMPTZ,                            -- when did we last verify connectivity
    last_test_ok    BOOLEAN,                                -- result of last test
    last_test_error TEXT,                                    -- error message from failed test
    created_by      TEXT,                                    -- user_email at create time
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    metadata        JSONB                                    -- room for resource-mapping config (Phase B)
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fhir_connections_environment_chk'
    ) THEN
        ALTER TABLE digitisation_fhir_connections
            ADD CONSTRAINT fhir_connections_environment_chk
            CHECK (environment IN ('sandbox', 'staging', 'production'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fhir_connections_auth_method_chk'
    ) THEN
        ALTER TABLE digitisation_fhir_connections
            ADD CONSTRAINT fhir_connections_auth_method_chk
            CHECK (auth_method IN ('none', 'basic', 'bearer',
                                    'oauth2_client_credentials', 'smart_on_fhir'));
    END IF;
END$$;

COMMENT ON TABLE digitisation_fhir_connections IS
    'Saved FHIR endpoint configurations per workspace. Phase A stores the '
    'connection metadata (name/URL/env/auth_method). Phase B will add '
    'credential storage (Supabase Vault) and actually exercise these in '
    'the export worker.';

CREATE INDEX IF NOT EXISTS idx_fhir_connections_workspace
    ON digitisation_fhir_connections (workspace_id, created_at DESC);

-- Enforce single default per workspace via partial unique index.
CREATE UNIQUE INDEX IF NOT EXISTS idx_fhir_connections_one_default
    ON digitisation_fhir_connections (workspace_id)
    WHERE is_default = TRUE;

COMMIT;
