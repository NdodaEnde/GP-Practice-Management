-- ============================================================================
-- ATC backfill verification suite
-- ============================================================================
-- Paste this whole file into Supabase SQL editor and run. Each block prints
-- a labelled result. Read top-to-bottom; everything should match the
-- "expected" comment.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- TEST 1 — Schema check: all 5 ATC columns exist with right types
-- ----------------------------------------------------------------------------
-- Expected: 5 rows, types as listed.

SELECT 'TEST 1 — schema check' AS test;
SELECT column_name, data_type
  FROM information_schema.columns
 WHERE table_name = 'nappi_codes'
   AND column_name IN ('atc_code', 'atc_class_desc', 'atc_match_method',
                       'atc_source', 'atc_matched_at')
 ORDER BY column_name;

-- ----------------------------------------------------------------------------
-- TEST 2 — Constraint check: match_method CHECK constraint installed
-- ----------------------------------------------------------------------------
-- Expected: 1 row showing the CHECK constraint.

SELECT 'TEST 2 — match_method CHECK constraint' AS test;
SELECT conname, pg_get_constraintdef(oid) AS definition
  FROM pg_constraint
 WHERE conname = 'nappi_codes_atc_match_method_chk';

-- ----------------------------------------------------------------------------
-- TEST 3 — Indexes installed
-- ----------------------------------------------------------------------------
-- Expected: 2 rows (idx_nappi_atc_code, idx_nappi_atc_match_method).

SELECT 'TEST 3 — indexes installed' AS test;
SELECT indexname FROM pg_indexes
 WHERE tablename = 'nappi_codes'
   AND indexname LIKE 'idx_nappi_atc%'
 ORDER BY indexname;

-- ----------------------------------------------------------------------------
-- TEST 4 — Headline counts
-- ----------------------------------------------------------------------------
-- Expected:
--   total                : (your full nappi_codes count)
--   with_atc_code        : 119
--   atcd_source          : 119
--   exact_method         : 119
--   matched_at_populated : 119
--   class_desc_populated : 119

SELECT 'TEST 4 — headline counts' AS test;
SELECT
    count(*)                                                  AS total,
    count(*) FILTER (WHERE atc_code IS NOT NULL)              AS with_atc_code,
    count(*) FILTER (WHERE atc_source = 'atcd-2026-04-25')    AS atcd_source,
    count(*) FILTER (WHERE atc_match_method = 'exact')        AS exact_method,
    count(*) FILTER (WHERE atc_matched_at IS NOT NULL)        AS matched_at_populated,
    count(*) FILTER (WHERE atc_class_desc IS NOT NULL)        AS class_desc_populated
  FROM nappi_codes;

-- ----------------------------------------------------------------------------
-- TEST 5 — Audit consistency: every row with atc_code has the supporting
-- audit columns populated. ZERO inconsistent rows expected.
-- ----------------------------------------------------------------------------

SELECT 'TEST 5 — audit consistency' AS test;
SELECT count(*) AS inconsistent_rows
  FROM nappi_codes
 WHERE atc_code IS NOT NULL
   AND (atc_class_desc IS NULL
     OR atc_match_method IS NULL
     OR atc_source       IS NULL
     OR atc_matched_at   IS NULL);

-- ----------------------------------------------------------------------------
-- TEST 6 — Spot checks against known WHO ATC mappings
-- ----------------------------------------------------------------------------
-- Each generic name below has a single canonical WHO level-5 ATC code.
-- Every row must show the right code or the matcher is broken.

SELECT 'TEST 6 — spot-check known mappings' AS test;
WITH expected(generic_norm, expected_atc) AS (VALUES
    ('paracetamol',  'N02BE01'),
    ('amoxicillin',  'J01CA04'),
    ('atorvastatin', 'C10AA05'),
    ('metformin',    'A10BA02'),
    ('amlodipine',   'C08CA01'),
    ('losartan',     'C09CA01'),
    ('simvastatin',  'C10AA01'),
    ('warfarin',     'B01AA03'),
    ('clopidogrel',  'B01AC04'),
    ('gabapentin',   'N02BF01'),
    ('lamotrigine',  'N03AX09'),
    ('clarithromycin','J01FA09')
)
SELECT
    e.generic_norm,
    e.expected_atc,
    count(*) FILTER (WHERE n.atc_code = e.expected_atc)               AS rows_with_expected_atc,
    count(*) FILTER (WHERE n.atc_code IS NOT NULL
                       AND n.atc_code <> e.expected_atc)              AS rows_with_wrong_atc
  FROM expected e
  LEFT JOIN nappi_codes n
    ON lower(n.generic_name) = e.generic_norm
   AND n.atc_source = 'atcd-2026-04-25'
 GROUP BY e.generic_norm, e.expected_atc
 ORDER BY e.generic_norm;
-- Expected: rows_with_wrong_atc = 0 for every generic.

-- ----------------------------------------------------------------------------
-- TEST 7 — The actual unlock: drug-class grouping queries WORK
-- ----------------------------------------------------------------------------
-- This is what TRACEABILITY 6b was about. Each query should return >=1 row.

SELECT 'TEST 7a — statins (HMG-CoA inhibitors, ATC C10AA)' AS test;
SELECT atc_code, atc_class_desc, count(*) AS rows
  FROM nappi_codes
 WHERE atc_code LIKE 'C10AA%'
 GROUP BY atc_code, atc_class_desc
 ORDER BY atc_code;

SELECT 'TEST 7b — penicillin antibiotics (ATC J01C)' AS test;
SELECT atc_code, atc_class_desc, count(*) AS rows
  FROM nappi_codes
 WHERE atc_code LIKE 'J01C%'
 GROUP BY atc_code, atc_class_desc
 ORDER BY atc_code;

SELECT 'TEST 7c — angiotensin II receptor blockers (ATC C09C)' AS test;
SELECT atc_code, atc_class_desc, count(*) AS rows
  FROM nappi_codes
 WHERE atc_code LIKE 'C09C%'
 GROUP BY atc_code, atc_class_desc
 ORDER BY atc_code;

SELECT 'TEST 7d — antidepressants (ATC N06A)' AS test;
SELECT atc_code, atc_class_desc, count(*) AS rows
  FROM nappi_codes
 WHERE atc_code LIKE 'N06A%'
 GROUP BY atc_code, atc_class_desc
 ORDER BY atc_code;

SELECT 'TEST 7e — antiretrovirals (ATC J05A)' AS test;
SELECT atc_code, atc_class_desc, count(*) AS rows
  FROM nappi_codes
 WHERE atc_code LIKE 'J05A%'
 GROUP BY atc_code, atc_class_desc
 ORDER BY atc_code;

-- ----------------------------------------------------------------------------
-- TEST 8 — Anatomical-level rollup (level-1 ATC = single letter)
-- ----------------------------------------------------------------------------
-- This is the "what does our prescribing landscape look like" view.

SELECT 'TEST 8 — anatomical-group distribution' AS test;
SELECT
    substring(atc_code FROM 1 FOR 1) AS atc_anatomical_group,
    CASE substring(atc_code FROM 1 FOR 1)
        WHEN 'A' THEN 'Alimentary tract & metabolism'
        WHEN 'B' THEN 'Blood & blood-forming organs'
        WHEN 'C' THEN 'Cardiovascular system'
        WHEN 'D' THEN 'Dermatologicals'
        WHEN 'G' THEN 'Genito-urinary & sex hormones'
        WHEN 'H' THEN 'Systemic hormonal preparations'
        WHEN 'J' THEN 'Anti-infectives for systemic use'
        WHEN 'L' THEN 'Antineoplastic & immunomodulating'
        WHEN 'M' THEN 'Musculo-skeletal system'
        WHEN 'N' THEN 'Nervous system'
        WHEN 'P' THEN 'Antiparasitic products'
        WHEN 'R' THEN 'Respiratory system'
        WHEN 'S' THEN 'Sensory organs'
        WHEN 'V' THEN 'Various'
    END AS group_name,
    count(*) AS distinct_substances
  FROM nappi_codes
 WHERE atc_code IS NOT NULL
 GROUP BY 1, 2
 ORDER BY distinct_substances DESC;
