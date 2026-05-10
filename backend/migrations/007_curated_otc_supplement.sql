-- ============================================================================
-- Migration 007 — Curated OTC supplement support
-- ============================================================================
-- Implements TRACEABILITY.md item 6c. The existing nappi_codes table is
-- almost entirely scheduled prescription medicines (data sourced from a
-- BHF/MIMS-style database). High-frequency SA OTC products (Demazin,
-- Disprin, Med-Lemon, Calpol, Bioplus, Strepsils, Reuterina, Buscopan,
-- etc) aren't in there, so during digitisation those rows get a red
-- "No NAPPI" badge and reviewers have to explain it every time.
--
-- This migration adds the column we need to distinguish CURATED rows
-- (hand-added by us, no real NAPPI code yet) from real_nappi rows
-- (sourced from the official NAPPI/MPP feed). Curated rows use a
-- synthetic id like CURATED-DEMAZIN-001 in nappi_code; the data_source
-- flag is what frontend / backend code branches on.
--
-- Idempotent: safe to re-run.
-- ============================================================================

BEGIN;

ALTER TABLE nappi_codes
    ADD COLUMN IF NOT EXISTS data_source TEXT NOT NULL DEFAULT 'real_nappi';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'nappi_codes_data_source_chk'
    ) THEN
        ALTER TABLE nappi_codes
            ADD CONSTRAINT nappi_codes_data_source_chk
            CHECK (data_source IN ('real_nappi', 'curated'));
    END IF;
END$$;

COMMENT ON COLUMN nappi_codes.data_source IS
    'Origin of this row: real_nappi (sourced from the official NAPPI/MPP '
    'feed; nappi_code is the real code) or curated (hand-added high-'
    'frequency OTC; nappi_code is a synthetic CURATED-<slug>-NNN '
    'placeholder that gets replaced when the real NAPPI lands).';

-- Partial index — most queries that care about data_source are filtering
-- "show me only the real ones" or "show me only the curated ones".
CREATE INDEX IF NOT EXISTS idx_nappi_data_source
    ON nappi_codes (data_source);

COMMIT;
