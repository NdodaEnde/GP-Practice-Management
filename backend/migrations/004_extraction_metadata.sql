-- ============================================================================
-- Migration 004 — extraction_metadata column on gp_validation_sessions
-- ============================================================================
-- Persist LandingAI ADE's native per-field grounding metadata
-- ({value, references: [chunk_id, ...]}). Without this column, the processor
-- falls back to nesting metadata inside confidence_scores._extraction_metadata
-- (works but conflates two concerns). This migration cleans that up.
--
-- Idempotent: safe to re-run.
-- ============================================================================

BEGIN;

ALTER TABLE gp_validation_sessions
    ADD COLUMN IF NOT EXISTS extraction_metadata JSONB;

COMMENT ON COLUMN gp_validation_sessions.extraction_metadata IS
    'LandingAI ADE per-field grounding metadata. Each leaf has shape '
    '{value, references: [chunk_id, ...]}. Empty references = LLM-inferred; '
    'non-empty = grounded in source text chunks (for traceability + per-field '
    'confidence + click-to-source on the validation panel).';

COMMIT;
