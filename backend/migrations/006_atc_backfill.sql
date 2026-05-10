-- ============================================================================
-- Migration 006 — ATC code backfill scaffolding on nappi_codes
-- ============================================================================
-- Implements TRACEABILITY.md item 6b. The WHO Anatomical Therapeutic Chemical
-- (ATC) classification is public + free; ~95% of nappi_codes rows currently
-- have NULL atc_code. This migration adds the columns we need to (a) store
-- the human-readable class description alongside the code, and (b) keep an
-- audit trail of HOW each row was matched (exact / fuzzy / manual / null) so
-- we can later tighten or re-run the backfill without losing provenance.
--
-- The atc_code column itself already exists from nappi_codes_migration.sql;
-- we only add the descriptive + audit columns here.
--
-- Idempotent: safe to re-run.
-- ============================================================================

BEGIN;

ALTER TABLE nappi_codes
    ADD COLUMN IF NOT EXISTS atc_class_desc   TEXT,
    ADD COLUMN IF NOT EXISTS atc_match_method TEXT,
    ADD COLUMN IF NOT EXISTS atc_source       TEXT,
    ADD COLUMN IF NOT EXISTS atc_matched_at   TIMESTAMPTZ;

-- Constrain match_method to a known vocabulary. Existing NULLs stay NULL.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'nappi_codes_atc_match_method_chk'
    ) THEN
        ALTER TABLE nappi_codes
            ADD CONSTRAINT nappi_codes_atc_match_method_chk
            CHECK (atc_match_method IN ('exact', 'fuzzy', 'manual', 'combo') OR atc_match_method IS NULL);
    END IF;
END$$;

COMMENT ON COLUMN nappi_codes.atc_class_desc   IS
    'WHO ATC class description (level-5 substance name; e.g. "enalapril"). '
    'Populated by backend/scripts/atc_backfill.py.';
COMMENT ON COLUMN nappi_codes.atc_match_method IS
    'How atc_code was assigned: exact (normalized name match), fuzzy '
    '(token/edit-distance match above threshold), combo (combination drug '
    'matched against ATC combination entry), manual (reviewer-applied).';
COMMENT ON COLUMN nappi_codes.atc_source IS
    'Provenance tag for the ATC data used (e.g. "atcd-2026-04-25", '
    '"bioportal-CCBY", "rxnorm-YYYY", "manual"). Used to find rows whose '
    'source needs replacement (e.g. dev-only NC-licensed data swapped for '
    'a commercial-licensed source before GA).';
COMMENT ON COLUMN nappi_codes.atc_matched_at   IS
    'Timestamp the current atc_code/atc_class_desc was applied. Re-runs '
    'overwrite this; rows without an ATC match keep it NULL.';

-- Lookup index for "give me everything in ATC class C09AA*" style queries
-- once the backfill has populated codes. Partial index keeps it small.
CREATE INDEX IF NOT EXISTS idx_nappi_atc_code
    ON nappi_codes (atc_code)
    WHERE atc_code IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_nappi_atc_match_method
    ON nappi_codes (atc_match_method)
    WHERE atc_match_method IS NOT NULL;

COMMIT;
