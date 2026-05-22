-- ============================================================================
-- Migration 035 — vitals.encounter_id nullable
-- ============================================================================
--
-- The vitals table required encounter_id NOT NULL, on the assumption every
-- vital is captured inside a formal encounter (true for digitisation-promoted
-- vitals). The rebuilt /api/vitals router (Professional EHR vitals tab) also
-- supports MANUAL vitals entry, which is not necessarily tied to an encounter.
-- Fabricating a throwaway encounter per manual reading would pollute the
-- clinical timeline; the honest model is a nullable link. Digitisation-promoted
-- vitals continue to carry their encounter_id unchanged.
--
-- Idempotent: DROP NOT NULL is a no-op if already nullable.
-- ============================================================================

BEGIN;

ALTER TABLE public.vitals ALTER COLUMN encounter_id DROP NOT NULL;

COMMIT;
