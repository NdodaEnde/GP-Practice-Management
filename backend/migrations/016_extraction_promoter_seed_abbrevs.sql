-- ============================================================================
-- Migration 016 — Seed icd10_abbreviations from the Python ICD10_ABBREVIATIONS
-- ============================================================================
--
-- Mirrors backend/app/services/extraction_promoter.py:64-165 verbatim.
-- The Python dict was the source of truth in PR 1; this seed promotes it
-- to a real table so future additions are one-line INSERTs (no code
-- deploy). The Python dict can be deleted once PR 3 removes
-- extraction_promoter.py entirely; until then it must stay in sync.
--
-- Idempotent: ON CONFLICT DO NOTHING. Re-running is a no-op. Re-syncing
-- a changed code requires UPDATE first, or DELETE + INSERT.
--
-- WHEN ADDING A NEW ABBREVIATION
--
--   Either:
--     (a) Edit this file, add the INSERT, re-run the migration; OR
--     (b) Run an ad-hoc INSERT against the table in production with
--         operator review.
--
--   In either case, the code MUST exist in icd10_codes or the
--   abbreviation tier falls through to Tier 2 fuzzy ILIKE. The Python
--   resolver detects "mapped code missing from table" and returns NULL
--   instead of a code that won't validate.
-- ============================================================================

BEGIN;

INSERT INTO icd10_abbreviations (abbrev, icd10_code, notes) VALUES
    -- respiratory
    ('urti',           'J06.9',  'Acute upper respiratory infection, unspecified'),
    ('urfi',           'J06.9',  'Variant spelling: upper respiratory feverish illness'),
    ('urt',            'J06.9',  'Abbrev: URT infection'),
    ('lrti',           'J22',    'Unspecified acute lower respiratory infection'),
    ('asthma',         'J45.9',  'Asthma, unspecified'),
    ('copd',           'J44.9',  'Chronic obstructive pulmonary disease, unspecified'),
    ('bronchitis',     'J40',    'Bronchitis, not specified as acute or chronic'),
    ('pneumonia',      'J18.9',  'Pneumonia, unspecified organism'),
    ('tonsillitis',    'J03.9',  'Acute tonsillitis, unspecified'),
    ('pharyngitis',    'J02.9',  'Acute pharyngitis, unspecified'),
    ('sinusitis',      'J32.9',  'Chronic sinusitis, unspecified'),
    ('otitis media',   'H66.9',  'Otitis media, unspecified'),
    ('om',             'H66.9',  'Abbrev: otitis media'),
    ('dyspnea',        'R06.0',  'Dyspnoea'),
    ('dyspnoea',       'R06.0',  'Variant spelling: dyspnoea'),
    ('cough',          'R05',    'Cough'),

    -- cardiovascular
    ('hpt',            'I10',    'Essential (primary) hypertension'),
    ('htn',            'I10',    'Essential (primary) hypertension'),
    ('hypertension',   'I10',    'Essential (primary) hypertension'),
    ('ihd',            'I25.9',  'Chronic ischaemic heart disease, unspecified'),
    ('cva',            'I63.9',  'Cerebral infarction, unspecified'),
    ('tia',            'G45.9',  'Transient cerebral ischaemic attack, unspecified'),
    ('afib',           'I48',    'Atrial fibrillation and flutter'),
    ('af',             'I48',    'Atrial fibrillation and flutter'),
    ('chf',            'I50.9',  'Heart failure, unspecified'),
    ('heart failure',  'I50.9',  'Heart failure, unspecified'),

    -- endocrine
    ('dm',             'E11.9',  'Type 2 diabetes mellitus without complications'),
    ('t2dm',           'E11.9',  'Type 2 diabetes mellitus without complications'),
    ('t1dm',           'E10.9',  'Type 1 diabetes mellitus without complications'),
    ('diabetes',       'E11.9',  'Type 2 diabetes mellitus without complications'),
    ('thyroid',        'E07.9',  'Disorder of thyroid, unspecified'),
    ('hypothyroid',    'E03.9',  'Hypothyroidism, unspecified'),
    ('hyperthyroid',   'E05.9',  'Thyrotoxicosis, unspecified'),

    -- gastrointestinal
    ('gerd',           'K21.9',  'Gastro-oesophageal reflux disease without oesophagitis'),
    ('gord',           'K21.9',  'Variant spelling: GORD'),
    ('ibs',            'K58.9',  'Irritable bowel syndrome without diarrhoea'),
    ('gastritis',      'K29.7',  'Gastritis, unspecified'),
    ('constipation',   'K59.0',  'Constipation'),
    ('diarrhea',       'A09',    'Diarrhoea and gastroenteritis of presumed infectious origin'),
    ('diarrhoea',      'A09',    'Variant spelling: diarrhoea'),

    -- musculoskeletal
    ('arthritis',      'M13.9',  'Arthritis, unspecified'),
    ('ra',             'M06.9',  'Rheumatoid arthritis, unspecified'),
    ('oa',             'M19.9',  'Arthrosis, unspecified'),
    ('back pain',      'M54.9',  'Dorsalgia, unspecified'),
    ('lbp',            'M54.5',  'Low back pain'),
    ('low back pain',  'M54.5',  'Low back pain'),
    ('myalgia',        'M79.1',  'Myalgia'),

    -- neuro
    ('headache',       'G44',    'Other headache syndromes'),
    ('migraine',       'G43',    'Migraine'),
    ('vertigo',        'R42',    'Dizziness and giddiness'),
    ('epilepsy',       'G40.9',  'Epilepsy, unspecified'),

    -- genitourinary
    ('uti',            'N39.0',  'Urinary tract infection, site not specified'),
    ('cystitis',       'N30.9',  'Cystitis, unspecified'),
    ('bph',            'N40',    'Hyperplasia of prostate'),

    -- infections
    ('hiv',            'B20',    'Human immunodeficiency virus disease'),
    ('tb',             'A15.9',  'Respiratory tuberculosis unspecified, bacteriologically confirmed'),
    ('tuberculosis',   'A15.9',  'Respiratory tuberculosis unspecified'),
    ('malaria',        'B54',    'Unspecified malaria'),

    -- mental
    ('depression',     'F32.9',  'Depressive episode, unspecified'),
    ('anxiety',        'F41.9',  'Anxiety disorder, unspecified'),
    ('gad',            'F41.1',  'Generalised anxiety disorder'),

    -- symptoms / signs
    ('pyrexia',        'R50.9',  'Fever, unspecified'),
    ('fever',          'R50.9',  'Fever, unspecified'),
    ('anaemia',        'D64.9',  'Anaemia, unspecified'),
    ('anemia',         'D64.9',  'Variant spelling: anemia'),
    ('fatigue',        'R53',    'Malaise and fatigue'),
    ('vomiting',       'R11',    'Nausea and vomiting'),
    ('nausea',         'R11',    'Nausea and vomiting'),
    ('rash',           'R21',    'Rash and other nonspecific skin eruption'),

    -- mother/child / OB
    ('pregnancy',      'Z34.9',  'Supervision of normal pregnancy, unspecified'),
    ('antenatal',      'Z34.9',  'Supervision of normal pregnancy, unspecified'),
    ('labour',         'O80',    'Single spontaneous delivery'),
    ('well child',     'Z00.1',  'Routine child health examination')
ON CONFLICT (abbrev) DO NOTHING;

COMMIT;
