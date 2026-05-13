-- ============================================================================
-- Migration 015 — PL/pgSQL port of extraction_promoter (PR 2)
-- ============================================================================
--
-- WHAT THIS DELIVERS
--
--   Three load-bearing properties PR 1 deliberately did not deliver:
--
--   1. ACID. The entire promote-document mutation runs inside ONE
--      Postgres transaction. Either every row lands (success) or nothing
--      does (rollback). PR 1's 100+ HTTP round-trips via PostgREST could
--      half-apply on a network failure mid-stream; that gap is closed.
--
--   2. Mutual exclusion. The transaction begins with
--      SELECT id FROM digitised_documents WHERE id = p_document_id
--      FOR UPDATE NOWAIT. Two concurrent calls targeting the same
--      document: the second raises SQLSTATE 55P03 (lock_not_available)
--      which the Python wrapper maps to ErrorDetail(code='action_locked').
--      Phase 0 verification proved this property is unattainable at the
--      Python/PostgREST layer (session-scoped advisory locks invisible
--      across HTTP pooling); the only way to deliver it is to move the
--      work to where the lock can live — one transaction.
--
--   3. Latency. PR 1 measured ~35 seconds per promote (100+ HTTP
--      round-trips through PostgREST: one INSERT per diagnosis, one per
--      med, one per vital, etc.). PL/pgSQL collapses that to a single
--      transaction's worth of work — projected 1-2 seconds. The 25-second
--      SET LOCAL statement_timeout is the canary, not the target.
--
-- WHAT THIS DOES NOT DELIVER
--
--   Audit-write atomicity. The RPC mutates data and returns the result
--   payload (PromotionResult shape + affected_objects). The Python
--   ActionExecutor writes the audit row AFTER the RPC returns. There is
--   a small (~5ms) window between RPC commit and audit-INSERT during
--   which a Python crash leaves mutated data without a corresponding
--   audit row. This is the same window PR 1 carried.
--
--   The plan's §1 implied the RPC writes the audit row too. After
--   building it both ways, the cleaner design is: RPC owns data-mutation
--   atomicity (the load-bearing regulatory property); Python owns audit
--   write (single INSERT, low blast radius if it fails). Closing the
--   ~5ms audit-write gap costs more architectural debt than it saves:
--   the RPC would need every audit-row field as a parameter, the
--   executor would need a sentinel to detect "audit already written",
--   and the symmetry across actions (none yet, but coming in PR 3) would
--   fracture. PR description names this departure from the plan
--   explicitly.
--
-- WHO CALLS THIS
--
--   The PromoteExtractionsViaPromoter Effect's apply() method:
--       supabase.rpc('execute_action_promote_document', {p_document_id, ...})
--
--   The Python wrapper maps SQLSTATEs to ErrorDetail.code values
--   (55P03 → action_locked, 23503 → invariant_violated,
--   P0001 with hint 'not_found' → not_found, etc.).
--
-- HELPER FUNCTIONS
--
--   _promote_doc_resolve_icd10(p_description TEXT)
--       Two-tier ICD-10 inference matching the Python promoter exactly.
--       Tier 1: exact match in icd10_abbreviations (e.g. 'htn' → 'I10').
--       Tier 2: ILIKE fuzzy on icd10_codes.who_full_desc, but only when
--       description ≥ 10 chars OR multi-word (short single tokens are
--       false-positive magnets). Single-hit only — multi-hit returns NULL
--       to avoid wrong codes. Matches the Python at
--       extraction_promoter.py:188-253.
--
--   _promote_doc_resolve_nappi(p_drug_name TEXT)
--       Brand-first then generic fallback. No `%` wrapping — case-
--       insensitive exact match via ILIKE. Matches the Python at
--       extraction_promoter.py:256-287.
--
--   _promote_doc_resolve_patient_match(p_workspace_id, p_id_number,
--                                       p_surname, p_dob)
--       Tier 1 SA ID exact, Tier 2 surname (ILIKE) + dob (exact).
--       Returns one patient row or NULL. Matches the Python at
--       extraction_promoter.py:417-450.
--
-- LOCKING NOTE
--
--   The FOR UPDATE NOWAIT is held on the digitised_documents row for
--   the full ~1-2s of work. Contention surface is single-user-clicking-
--   approve, not a hot path. The doc's encounter_id gets nulled later in
--   the same transaction anyway. Advisory-lock helpers from migration 014
--   become dead code — dropped in migration 017.
--
-- TIMEOUT CHAIN
--
--   SET LOCAL statement_timeout = '25s' at the top of the orchestrator.
--   Sits under PostgREST's 30s default and typical proxy ceilings (60s+).
--   The Python supabase client should be configured with timeout=30 so
--   the SQL timeout fires first (clean SQLSTATE) rather than httpx
--   cutting off with a generic ReadTimeout. The Python wrapper logs a
--   warning when duration_ms > 5000 — well before the 25s ceiling.
--
-- IDEMPOTENT — safe to re-run.
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- icd10_abbreviations — SA-GP shorthand → ICD-10 code lookup
-- ----------------------------------------------------------------------------
--
-- Seeded by migration 016. Adding a new abbreviation is a one-line INSERT
-- in that file (or an ad-hoc INSERT against this table) — no code deploy.
-- The Python ICD10_ABBREVIATIONS dict
-- (extraction_promoter.py:64-165) is the authoritative source for the
-- initial 65 entries; subsequent additions can diverge.
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS icd10_abbreviations (
    abbrev       TEXT NOT NULL PRIMARY KEY,
    icd10_code   TEXT NOT NULL,
    notes        TEXT
);

COMMENT ON TABLE icd10_abbreviations IS
    'SA-GP clinical shorthand resolved to WHO ICD-10 codes. abbrev is the '
    'normalised lower-cased lookup key; icd10_code MUST exist in icd10_codes '
    'or the abbreviation tier falls through to Tier 2 fuzzy ILIKE search.';


-- ----------------------------------------------------------------------------
-- _promote_doc_resolve_icd10(description) → (code, who_full_desc)
-- ----------------------------------------------------------------------------
--
-- Two-tier resolution mirroring the Python promoter exactly.
--
-- Tier 1 (abbreviation map): exact lower-cased key match against
-- icd10_abbreviations. If the mapped code is missing from icd10_codes,
-- returns NULL rather than a code that won't validate downstream.
--
-- Tier 2 (fuzzy ILIKE): ONLY runs when the input is multi-word OR
-- ≥ 10 chars. Short single tokens ('URTI', 'Arthrog') are false-positive
-- magnets — substring search against ICD descriptions matches obscure
-- codes like Q74.3 ("Arthrogryposis multiplex congenita"). Multi-hit
-- returns NULL — avoid wrong codes.
--
-- STABLE because it reads but does not modify the database.
-- ----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION _promote_doc_resolve_icd10(p_description TEXT)
RETURNS TABLE(code TEXT, who_full_desc TEXT)
LANGUAGE plpgsql STABLE AS $$
DECLARE
    v_key   TEXT;
    v_code  TEXT;
    v_hit_count INT;
    v_hit_code TEXT;
    v_hit_desc TEXT;
BEGIN
    IF p_description IS NULL OR btrim(p_description) = '' THEN
        RETURN;
    END IF;

    v_key := lower(btrim(regexp_replace(p_description, '\s+', ' ', 'g')));

    -- Tier 1: abbreviation map exact match
    SELECT a.icd10_code INTO v_code
      FROM icd10_abbreviations a
     WHERE a.abbrev = v_key
     LIMIT 1;

    IF v_code IS NOT NULL THEN
        SELECT c.code, c.who_full_desc
          INTO v_hit_code, v_hit_desc
          FROM icd10_codes c
         WHERE c.code = v_code
         LIMIT 1;
        IF v_hit_code IS NOT NULL THEN
            code := v_hit_code;
            who_full_desc := v_hit_desc;
            RETURN NEXT;
        END IF;
        -- Mapped code missing from icd10_codes; fall through without returning.
        RETURN;
    END IF;

    -- Tier 2: fuzzy ILIKE. Skip for short single-token inputs.
    IF char_length(btrim(p_description)) < 10
       AND position(' ' IN btrim(p_description)) = 0 THEN
        RETURN;
    END IF;

    -- Single-hit acceptance only. LIMIT 2 lets us detect ambiguity cheaply.
    SELECT COUNT(*) INTO v_hit_count
      FROM (
          SELECT c.code
            FROM icd10_codes c
           WHERE c.who_full_desc ILIKE '%' || btrim(p_description) || '%'
             AND c.valid_clinical_use = TRUE
           LIMIT 2
      ) AS hits;

    IF v_hit_count = 1 THEN
        SELECT c.code, c.who_full_desc
          INTO v_hit_code, v_hit_desc
          FROM icd10_codes c
         WHERE c.who_full_desc ILIKE '%' || btrim(p_description) || '%'
           AND c.valid_clinical_use = TRUE
         LIMIT 1;
        code := v_hit_code;
        who_full_desc := v_hit_desc;
        RETURN NEXT;
    END IF;
    -- Otherwise: 0 or 2+ hits → return nothing (NULL semantics).
END;
$$;

COMMENT ON FUNCTION _promote_doc_resolve_icd10(TEXT) IS
    'ICD-10 inference for digitised diagnoses. Tier 1: icd10_abbreviations '
    'exact; Tier 2: fuzzy ILIKE on icd10_codes.who_full_desc (single-hit only, '
    'short single-token inputs skipped). NULL when ambiguous or unresolvable.';


-- ----------------------------------------------------------------------------
-- _promote_doc_resolve_nappi(drug_name) → (nappi_code, brand_name,
--                                          generic_name, atc_code, atc_class_desc)
-- ----------------------------------------------------------------------------
--
-- Brand-first match, then generic fallback. No `%` wrapping — case-
-- insensitive exact match via ILIKE. Mirrors the Python at
-- extraction_promoter.py:256-287. The nappi_codes table contains both
-- real-NAPPI rows and curated OTCs (CURATED-* synthetic IDs).
-- ----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION _promote_doc_resolve_nappi(p_drug_name TEXT)
RETURNS TABLE(
    nappi_code     TEXT,
    brand_name     TEXT,
    generic_name   TEXT,
    atc_code       TEXT,
    atc_class_desc TEXT
)
LANGUAGE plpgsql STABLE AS $$
DECLARE
    v_cleaned TEXT;
BEGIN
    IF p_drug_name IS NULL OR btrim(p_drug_name) = '' THEN
        RETURN;
    END IF;

    v_cleaned := btrim(p_drug_name);

    -- Brand-first
    RETURN QUERY
        SELECT n.nappi_code, n.brand_name, n.generic_name, n.atc_code, n.atc_class_desc
          FROM nappi_codes n
         WHERE n.brand_name ILIKE v_cleaned
         LIMIT 1;
    IF FOUND THEN
        RETURN;
    END IF;

    -- Generic fallback
    RETURN QUERY
        SELECT n.nappi_code, n.brand_name, n.generic_name, n.atc_code, n.atc_class_desc
          FROM nappi_codes n
         WHERE n.generic_name ILIKE v_cleaned
         LIMIT 1;
END;
$$;

COMMENT ON FUNCTION _promote_doc_resolve_nappi(TEXT) IS
    'NAPPI lookup: brand_name first, generic_name fallback. ILIKE without `%` '
    'wrapping = case-insensitive exact match. Returns one row or none.';


-- ----------------------------------------------------------------------------
-- _promote_doc_resolve_patient_match(workspace_id, id_number, surname, dob)
-- ----------------------------------------------------------------------------
--
-- Tier 1: SA ID exact match within workspace.
-- Tier 2: surname (ILIKE) + dob (exact) within workspace.
-- Returns matching patient row or no rows.
-- Mirrors extraction_promoter.py:417-450.
-- ----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION _promote_doc_resolve_patient_match(
    p_workspace_id TEXT,
    p_id_number    TEXT,
    p_surname      TEXT,
    p_dob          TEXT
)
RETURNS TABLE(
    id         TEXT,
    first_name TEXT,
    last_name  TEXT,
    id_number  TEXT,
    dob        TEXT
)
LANGUAGE plpgsql STABLE AS $$
BEGIN
    IF p_id_number IS NOT NULL AND btrim(p_id_number) <> '' THEN
        RETURN QUERY
            SELECT p.id, p.first_name, p.last_name, p.id_number, p.dob
              FROM patients p
             WHERE p.workspace_id = p_workspace_id
               AND p.id_number = btrim(p_id_number)
             LIMIT 1;
        IF FOUND THEN
            RETURN;
        END IF;
    END IF;

    IF p_surname IS NOT NULL AND btrim(p_surname) <> ''
       AND p_dob IS NOT NULL AND btrim(p_dob) <> '' THEN
        RETURN QUERY
            SELECT p.id, p.first_name, p.last_name, p.id_number, p.dob
              FROM patients p
             WHERE p.workspace_id = p_workspace_id
               AND p.last_name ILIKE btrim(p_surname)
               AND p.dob = p_dob
             LIMIT 1;
    END IF;
END;
$$;

COMMENT ON FUNCTION _promote_doc_resolve_patient_match(TEXT, TEXT, TEXT, TEXT) IS
    'Patient match-or-find. Tier 1: id_number exact within workspace. '
    'Tier 2: surname ILIKE + dob exact. Returns first hit or no rows.';


-- ----------------------------------------------------------------------------
-- _promote_doc_normalise_date(raw TEXT) → TEXT (YYYY-MM-DD or NULL)
-- ----------------------------------------------------------------------------
-- Best-effort: ISO first (YYYY-MM-DD prefix), then DD/MM/YYYY / DD-MM-YYYY.
-- Returns NULL when unparseable. Mirrors Python _normalise_date.
-- ----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION _promote_doc_normalise_date(p_raw TEXT)
RETURNS TEXT
LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE
    v_s     TEXT;
    v_d     INT;
    v_m     INT;
    v_y     INT;
    v_sep   TEXT;
    v_parts TEXT[];
BEGIN
    IF p_raw IS NULL OR btrim(p_raw) = '' THEN
        RETURN NULL;
    END IF;

    v_s := btrim(p_raw);

    -- ISO prefix
    IF char_length(v_s) >= 10
       AND substring(v_s FROM 5 FOR 1) = '-'
       AND substring(v_s FROM 8 FOR 1) = '-' THEN
        RETURN substring(v_s FROM 1 FOR 10);
    END IF;

    -- DD/MM/YYYY or DD-MM-YYYY
    FOREACH v_sep IN ARRAY ARRAY['/', '-'] LOOP
        IF array_length(string_to_array(v_s, v_sep), 1) = 3 THEN
            v_parts := string_to_array(v_s, v_sep);
            IF char_length(v_parts[3]) = 4 THEN
                BEGIN
                    v_d := v_parts[1]::INT;
                    v_m := v_parts[2]::INT;
                    v_y := v_parts[3]::INT;
                    RETURN to_char(make_date(v_y, v_m, v_d), 'YYYY-MM-DD');
                EXCEPTION WHEN OTHERS THEN
                    -- fall through
                END;
            END IF;
        END IF;
    END LOOP;

    RETURN NULL;
END;
$$;


-- ----------------------------------------------------------------------------
-- _promote_doc_allergy_substances(extractions JSONB) → TEXT[]
-- ----------------------------------------------------------------------------
-- Parse extractions.clinical_history.known_allergies. Skip NKDA/none.
-- Mirrors Python _allergy_substances.
-- ----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION _promote_doc_allergy_substances(p_extractions JSONB)
RETURNS TEXT[]
LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE
    v_raw     JSONB;
    v_raw_txt TEXT;
    v_out     TEXT[] := ARRAY[]::TEXT[];
    v_token   TEXT;
BEGIN
    v_raw := COALESCE(p_extractions, '{}'::JSONB) -> 'clinical_history' -> 'known_allergies';
    IF v_raw IS NULL OR v_raw = 'null'::JSONB THEN
        RETURN v_out;
    END IF;

    IF jsonb_typeof(v_raw) = 'array' THEN
        SELECT array_agg(btrim(elem::TEXT, '"'))
          INTO v_out
          FROM jsonb_array_elements_text(v_raw) AS elem
         WHERE btrim(elem) <> '';
        RETURN COALESCE(v_out, ARRAY[]::TEXT[]);
    END IF;

    IF jsonb_typeof(v_raw) = 'string' THEN
        v_raw_txt := btrim(v_raw #>> '{}');
        IF v_raw_txt = '' OR lower(v_raw_txt) IN ('nkda', 'none', 'n/a', 'no known allergies') THEN
            RETURN v_out;
        END IF;
        v_out := ARRAY[]::TEXT[];
        FOR v_token IN
            SELECT btrim(unnest(string_to_array(
                replace(replace(v_raw_txt, ';', ','), E'\n', ','), ',')))
        LOOP
            IF v_token <> '' THEN
                v_out := array_append(v_out, v_token);
            END IF;
        END LOOP;
        RETURN v_out;
    END IF;

    RETURN v_out;
END;
$$;


-- ----------------------------------------------------------------------------
-- _promote_doc_consultation_dates(extractions JSONB) → TEXT[]
-- ----------------------------------------------------------------------------
-- Collect distinct consultation_date / date strings across the extraction
-- sections, normalised + sorted. Empty / unparseable excluded.
-- Mirrors Python _collect_consultation_dates.
-- ----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION _promote_doc_consultation_dates(p_extractions JSONB)
RETURNS TEXT[]
LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE
    v_section TEXT;
    v_rows    JSONB;
    v_row     JSONB;
    v_norm    TEXT;
    v_set     TEXT[] := ARRAY[]::TEXT[];
BEGIN
    IF p_extractions IS NULL THEN
        RETURN v_set;
    END IF;

    FOREACH v_section IN ARRAY ARRAY[
        'vitals_history', 'diagnoses', 'medications',
        'investigations', 'referrals', 'progress_notes'
    ] LOOP
        v_rows := p_extractions -> v_section;
        IF v_rows IS NULL OR jsonb_typeof(v_rows) <> 'array' THEN
            CONTINUE;
        END IF;

        FOR v_row IN SELECT * FROM jsonb_array_elements(v_rows) LOOP
            v_norm := _promote_doc_normalise_date(COALESCE(
                v_row ->> 'consultation_date',
                v_row ->> 'date'
            ));
            IF v_norm IS NOT NULL AND NOT (v_norm = ANY(v_set)) THEN
                v_set := array_append(v_set, v_norm);
            END IF;
        END LOOP;
    END LOOP;

    RETURN COALESCE((SELECT array_agg(d ORDER BY d) FROM unnest(v_set) AS d), ARRAY[]::TEXT[]);
END;
$$;


-- ============================================================================
-- execute_action_promote_document — the orchestrator
-- ============================================================================
--
-- Performs a full document → patient-record promotion inside ONE
-- transaction. SELECT...FOR UPDATE NOWAIT on the source document is the
-- first statement; failure to acquire raises SQLSTATE 55P03 which the
-- Python wrapper maps to action_locked.
--
-- Returns JSONB with shape:
--   {
--     patient_id, patient_kind, match_confidence, patient_summary,
--     encounter_ids, counts, warnings, affected_objects
--   }
--
-- The Python ActionExecutor consumes affected_objects to build the
-- audit row.
-- ============================================================================

CREATE OR REPLACE FUNCTION execute_action_promote_document(
    p_document_id          TEXT,
    p_workspace_id         TEXT,
    p_extractions          JSONB,
    p_created_by           TEXT,
    p_forced_patient_id    TEXT DEFAULT NULL,
    p_force_create_patient BOOLEAN DEFAULT FALSE
) RETURNS JSONB
LANGUAGE plpgsql AS $$
DECLARE
    -- The 25s ceiling sits under PostgREST's 30s default. Python client
    -- should be configured with timeout=30 so this fires first.
    v_locked_id          TEXT;
    v_tenant_id          TEXT;
    v_demo               JSONB;
    v_patient_id         TEXT;
    v_patient_kind       TEXT;
    v_match_confidence   TEXT;
    v_patient_summary    JSONB;
    v_prior_encounter_id TEXT;
    v_dates              TEXT[];
    v_date               TEXT;
    v_encounter_id       TEXT;
    v_encounter_map      JSONB := '{}'::JSONB;
    v_encounter_ids      TEXT[] := ARRAY[]::TEXT[];
    v_first_encounter    TEXT;
    v_affected           JSONB := '[]'::JSONB;
    v_warnings           JSONB := '[]'::JSONB;
    v_diagnoses_count    INT := 0;
    v_icd10_inferred     INT := 0;
    v_vitals_count       INT := 0;
    v_allergies_count    INT := 0;
    v_rx_items_count     INT := 0;
    v_nappi_inferred     INT := 0;
    v_match_row          RECORD;
    v_new_patient_id     TEXT;
    v_first_name         TEXT;
    v_last_name          TEXT;
    v_dob                TEXT;
    v_id_number          TEXT;
    v_now_iso            TEXT;
    v_row                JSONB;
    v_substances         TEXT[];
    v_substance          TEXT;
    v_diag_code          TEXT;
    v_diag_desc          TEXT;
    v_icd_hit            RECORD;
    v_nappi_hit          RECORD;
    v_diag_inserted_id   TEXT;
    v_vital_id           TEXT;
    v_allergy_id         TEXT;
    v_rx_id              TEXT;
    v_rx_item_id         TEXT;
    v_doc_dates_meds     JSONB := '{}'::JSONB;
    v_dgroup_date        TEXT;
    v_dgroup_rows        JSONB;
    v_med_name           TEXT;
    v_resolved_nappi     TEXT;
    v_resolved_atc       TEXT;
    v_resolved_atc_desc  TEXT;
    v_resolved_generic   TEXT;
    v_resolved_brand     TEXT;
    v_existing_nappi     TEXT;
    v_existing_atc       TEXT;
    v_extr_generic       TEXT;
    v_rx_date            TEXT;
    v_consult_date_text  TEXT;
    v_measurements_any   BOOLEAN;
    v_bp_systolic        INT;
    v_bp_diastolic       INT;
    v_heart_rate         INT;
    v_temperature        NUMERIC;
    v_spo2               INT;
    v_weight_kg          NUMERIC;
    v_hba1c              NUMERIC;
    v_blood_glu          NUMERIC;
    v_measured_dt        TEXT;
    v_row_date           TEXT;
BEGIN
    SET LOCAL statement_timeout = '25s';

    v_now_iso := to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"');

    -- ------------------------------------------------------------------------
    -- Acquire lock + capture prior encounter_id (for reversal).
    -- FOR UPDATE NOWAIT raises SQLSTATE 55P03 if the row is locked by
    -- another transaction. The Python wrapper maps 55P03 → action_locked.
    -- ------------------------------------------------------------------------
    SELECT id, encounter_id
      INTO v_locked_id, v_prior_encounter_id
      FROM digitised_documents
     WHERE id = p_document_id
     FOR UPDATE NOWAIT;

    IF v_locked_id IS NULL THEN
        -- No row found. Raise P0001 with hint='not_found' for the Python
        -- wrapper to map to ErrorDetail(code='not_found').
        RAISE EXCEPTION 'digitised_documents row not found: %', p_document_id
            USING ERRCODE = 'P0001', HINT = 'not_found';
    END IF;

    -- ------------------------------------------------------------------------
    -- Tenant lookup. Workspace must exist.
    -- ------------------------------------------------------------------------
    SELECT tenant_id INTO v_tenant_id
      FROM workspaces
     WHERE id = p_workspace_id
     LIMIT 1;

    IF v_tenant_id IS NULL THEN
        RAISE EXCEPTION 'workspace not found: %', p_workspace_id
            USING ERRCODE = 'P0001', HINT = 'not_found';
    END IF;

    -- ------------------------------------------------------------------------
    -- Wipe prior promotion in reverse-FK order. patient is NOT wiped
    -- (shared across documents; cleaned up by a separate concern).
    -- ------------------------------------------------------------------------

    -- Break the digitised_documents → encounters FK first.
    UPDATE digitised_documents
       SET encounter_id = NULL
     WHERE id = p_document_id;

    -- prescription_items lacks source_document_id; wipe via parent FK.
    DELETE FROM prescription_items
     WHERE prescription_id IN (
        SELECT id FROM prescriptions WHERE source_document_id = p_document_id
     );

    DELETE FROM prescriptions WHERE source_document_id = p_document_id;
    DELETE FROM diagnoses     WHERE source_document_id = p_document_id;
    DELETE FROM vitals        WHERE source_document_id = p_document_id;
    DELETE FROM allergies     WHERE source_document_id = p_document_id;
    DELETE FROM encounters    WHERE source_document_id = p_document_id;

    -- ------------------------------------------------------------------------
    -- Patient match-or-create.
    -- ------------------------------------------------------------------------
    v_demo := COALESCE(p_extractions -> 'patient_demographics', '{}'::JSONB);

    IF p_forced_patient_id IS NOT NULL AND btrim(p_forced_patient_id) <> '' THEN
        SELECT id, first_name, last_name, id_number, dob INTO v_match_row
          FROM patients
         WHERE workspace_id = p_workspace_id
           AND id = p_forced_patient_id
         LIMIT 1;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'forced_patient_id % not found in workspace %',
                            p_forced_patient_id, p_workspace_id
                USING ERRCODE = 'P0001', HINT = 'not_found';
        END IF;
        v_patient_id := v_match_row.id;
        v_patient_kind := 'matched_explicit';
        v_match_confidence := 'explicit';
        v_patient_summary := jsonb_build_object(
            'first_name', v_match_row.first_name,
            'last_name',  v_match_row.last_name,
            'dob',        v_match_row.dob,
            'id_number',  v_match_row.id_number
        );
    ELSE
        IF NOT p_force_create_patient THEN
            SELECT * INTO v_match_row
              FROM _promote_doc_resolve_patient_match(
                  p_workspace_id,
                  v_demo ->> 'id_number',
                  v_demo ->> 'surname',
                  _promote_doc_normalise_date(v_demo ->> 'date_of_birth')
              );
            IF FOUND THEN
                v_patient_id := v_match_row.id;
                v_patient_kind := 'matched';
                -- Confidence: id_number if id matched, else name_dob.
                IF v_demo ->> 'id_number' IS NOT NULL
                   AND btrim(v_demo ->> 'id_number') <> ''
                   AND v_match_row.id_number = btrim(v_demo ->> 'id_number') THEN
                    v_match_confidence := 'id_number';
                ELSE
                    v_match_confidence := 'name_dob';
                END IF;
                v_patient_summary := jsonb_build_object(
                    'first_name', v_match_row.first_name,
                    'last_name',  v_match_row.last_name,
                    'dob',        v_match_row.dob,
                    'id_number',  v_match_row.id_number
                );
            END IF;
        END IF;

        IF v_patient_id IS NULL THEN
            -- Create new patient.
            v_new_patient_id := gen_random_uuid()::TEXT;
            v_first_name := split_part(COALESCE(v_demo ->> 'full_names', ''), ' ', 1);
            IF v_first_name IS NULL OR btrim(v_first_name) = '' THEN
                v_first_name := 'Unknown';
            END IF;
            v_last_name  := COALESCE(NULLIF(btrim(v_demo ->> 'surname'), ''), 'Unknown');
            v_dob        := COALESCE(_promote_doc_normalise_date(v_demo ->> 'date_of_birth'),
                                     '1900-01-01');
            v_id_number  := COALESCE(NULLIF(btrim(v_demo ->> 'id_number'), ''),
                                     'unknown-' || substring(v_new_patient_id FROM 1 FOR 8));

            INSERT INTO patients (
                id, tenant_id, workspace_id,
                first_name, last_name, dob, id_number,
                contact_number, email, address, medical_aid
            ) VALUES (
                v_new_patient_id, v_tenant_id, p_workspace_id,
                v_first_name, v_last_name, v_dob, v_id_number,
                COALESCE(v_demo ->> 'telephone_cell', v_demo ->> 'phone'),
                v_demo ->> 'email',
                v_demo ->> 'address',
                COALESCE(v_demo ->> 'medical_aid', v_demo ->> 'scheme_name')
            );

            v_patient_id := v_new_patient_id;
            v_patient_kind := 'created';
            v_match_confidence := 'n/a';
            v_patient_summary := jsonb_build_object(
                'first_name', v_first_name,
                'last_name',  v_last_name,
                'dob',        v_dob,
                'id_number',  v_id_number
            );
        END IF;
    END IF;

    -- Affected: Patient (op='created' for new, 'linked' for matched)
    v_affected := v_affected || jsonb_build_array(jsonb_build_object(
        'type', 'Patient',
        'id',   v_patient_id,
        'op',   CASE WHEN v_patient_kind = 'created' THEN 'created' ELSE 'linked' END
    ));

    -- ------------------------------------------------------------------------
    -- Encounters. One per distinct consultation_date; fallback = today.
    -- ------------------------------------------------------------------------
    v_dates := _promote_doc_consultation_dates(p_extractions);
    IF array_length(v_dates, 1) IS NULL THEN
        v_dates := ARRAY[to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD')];
    END IF;

    FOREACH v_date IN ARRAY v_dates LOOP
        v_encounter_id := gen_random_uuid()::TEXT;
        INSERT INTO encounters (
            id, patient_id, workspace_id,
            encounter_date, status, chief_complaint, vitals_json, gp_notes,
            source_document_id
        ) VALUES (
            v_encounter_id, v_patient_id, p_workspace_id,
            (v_date || 'T00:00:00+00:00')::TIMESTAMPTZ,
            'completed', NULL, NULL,
            'Created from digitised document ' || p_document_id,
            p_document_id
        );
        v_encounter_map := v_encounter_map || jsonb_build_object(v_date, v_encounter_id);
        v_encounter_ids := array_append(v_encounter_ids, v_encounter_id);
        IF v_first_encounter IS NULL THEN
            v_first_encounter := v_encounter_id;
        END IF;

        v_affected := v_affected || jsonb_build_array(jsonb_build_object(
            'type', 'Consultation',
            'id',   v_encounter_id,
            'op',   'created'
        ));
    END LOOP;

    -- ------------------------------------------------------------------------
    -- Diagnoses
    -- ------------------------------------------------------------------------
    FOR v_row IN
        SELECT * FROM jsonb_array_elements(
            COALESCE(p_extractions -> 'diagnoses', '[]'::JSONB)
        )
    LOOP
        IF (v_row ->> 'description' IS NULL OR btrim(v_row ->> 'description') = '')
           AND (v_row ->> 'icd10_code' IS NULL OR btrim(v_row ->> 'icd10_code') = '')
        THEN
            CONTINUE;
        END IF;

        v_diag_code := NULLIF(btrim(COALESCE(v_row ->> 'icd10_code', '')), '');
        v_diag_desc := v_row ->> 'description';

        IF v_diag_code IS NULL AND v_diag_desc IS NOT NULL THEN
            SELECT * INTO v_icd_hit
              FROM _promote_doc_resolve_icd10(v_diag_desc);
            IF FOUND THEN
                v_diag_code := v_icd_hit.code;
                v_diag_desc := v_icd_hit.who_full_desc;
                v_icd10_inferred := v_icd10_inferred + 1;
            END IF;
        END IF;

        v_row_date := _promote_doc_normalise_date(COALESCE(
            v_row ->> 'consultation_date', v_row ->> 'date'
        ));
        v_encounter_id := COALESCE(
            v_encounter_map ->> v_row_date,
            v_first_encounter
        );

        v_diag_inserted_id := gen_random_uuid()::TEXT;
        -- diagnoses.id is UUID (phase1_patient_safety_migration.sql);
        -- PL/pgSQL needs an explicit cast unlike PostgREST's implicit one.
        INSERT INTO diagnoses (
            id, tenant_id, workspace_id, encounter_id, patient_id,
            code, coding_system, display, diagnosis_type, status,
            onset_date, source, source_document_id, created_by, diagnosed_date
        ) VALUES (
            v_diag_inserted_id::UUID, v_tenant_id, p_workspace_id, v_encounter_id, v_patient_id,
            v_diag_code,
            CASE WHEN v_diag_code IS NOT NULL THEN 'ICD-10' ELSE 'local' END,
            COALESCE(NULLIF(btrim(v_row ->> 'description'), ''), v_diag_desc, 'Unspecified'),
            COALESCE(NULLIF(btrim(v_row ->> 'type'), ''), 'primary'),
            COALESCE(NULLIF(btrim(v_row ->> 'status'), ''), 'active'),
            -- diagnoses.onset_date / diagnosed_date are DATE-typed; helper
            -- returns TEXT (YYYY-MM-DD or NULL). Explicit cast required.
            _promote_doc_normalise_date(v_row ->> 'onset_date')::DATE,
            'document_extraction',
            p_document_id,
            p_created_by,
            _promote_doc_normalise_date(v_row ->> 'consultation_date')::DATE
        );

        v_diagnoses_count := v_diagnoses_count + 1;
        v_affected := v_affected || jsonb_build_array(jsonb_build_object(
            'type', 'Diagnosis',
            'id',   v_diag_inserted_id,
            'op',   'created'
        ));
    END LOOP;

    -- ------------------------------------------------------------------------
    -- Vitals
    -- ------------------------------------------------------------------------
    FOR v_row IN
        SELECT * FROM jsonb_array_elements(
            COALESCE(p_extractions -> 'vitals_history', '[]'::JSONB)
        )
    LOOP
        v_bp_systolic   := NULLIF(btrim(COALESCE(v_row ->> 'bp_systolic', '')), '')::INT;
        v_bp_diastolic  := NULLIF(btrim(COALESCE(v_row ->> 'bp_diastolic', '')), '')::INT;
        v_heart_rate    := NULLIF(btrim(COALESCE(v_row ->> 'heart_rate', '')), '')::INT;
        v_temperature   := NULLIF(btrim(COALESCE(v_row ->> 'temperature_c', '')), '')::NUMERIC;
        v_spo2          := NULLIF(btrim(COALESCE(v_row ->> 'oxygen_saturation', '')), '')::INT;
        v_weight_kg     := NULLIF(btrim(COALESCE(v_row ->> 'weight_kg', '')), '')::NUMERIC;
        v_hba1c         := NULLIF(btrim(COALESCE(v_row ->> 'hba1c', '')), '')::NUMERIC;
        v_blood_glu     := NULLIF(btrim(COALESCE(v_row ->> 'blood_glucose_fasting', '')), '')::NUMERIC;

        v_measurements_any := (
            v_bp_systolic IS NOT NULL OR v_bp_diastolic IS NOT NULL
            OR v_heart_rate IS NOT NULL OR v_temperature IS NOT NULL
            OR v_spo2 IS NOT NULL OR v_weight_kg IS NOT NULL
            OR v_hba1c IS NOT NULL OR v_blood_glu IS NOT NULL
            OR (v_row ->> 'bmi' IS NOT NULL AND btrim(v_row ->> 'bmi') <> '')
        );
        IF NOT v_measurements_any THEN
            CONTINUE;
        END IF;

        v_row_date := _promote_doc_normalise_date(COALESCE(
            v_row ->> 'consultation_date', v_row ->> 'date'
        ));
        v_encounter_id := COALESCE(
            v_encounter_map ->> v_row_date,
            v_first_encounter
        );

        IF v_row_date IS NOT NULL THEN
            v_measured_dt := v_row_date || 'T00:00:00+00:00';
        ELSE
            v_measured_dt := v_now_iso;
        END IF;
        v_consult_date_text := NULLIF(btrim(COALESCE(v_row ->> 'consultation_date', '')), '');

        v_vital_id := gen_random_uuid()::TEXT;
        -- vitals.id is UUID.
        INSERT INTO vitals (
            id, tenant_id, workspace_id, encounter_id, patient_id,
            bp_systolic, bp_diastolic, heart_rate, temperature, spo2,
            weight_kg, hba1c, blood_glucose_fasting,
            measured_datetime, consultation_date_text,
            source, source_document_id, created_by
        ) VALUES (
            v_vital_id::UUID, v_tenant_id, p_workspace_id, v_encounter_id, v_patient_id,
            v_bp_systolic, v_bp_diastolic, v_heart_rate, v_temperature, v_spo2,
            v_weight_kg, v_hba1c, v_blood_glu,
            v_measured_dt::TIMESTAMPTZ, v_consult_date_text,
            'document_extraction', p_document_id, p_created_by
        );

        v_vitals_count := v_vitals_count + 1;
        v_affected := v_affected || jsonb_build_array(jsonb_build_object(
            'type', 'Vital',
            'id',   v_vital_id,
            'op',   'created'
        ));
    END LOOP;

    -- ------------------------------------------------------------------------
    -- Allergies
    -- ------------------------------------------------------------------------
    v_substances := _promote_doc_allergy_substances(p_extractions);
    IF v_substances IS NOT NULL AND array_length(v_substances, 1) IS NOT NULL THEN
        FOREACH v_substance IN ARRAY v_substances LOOP
            v_allergy_id := gen_random_uuid()::TEXT;
            -- allergies.id is UUID.
            INSERT INTO allergies (
                id, tenant_id, workspace_id, patient_id,
                substance, status, source, source_document_id, created_by
            ) VALUES (
                v_allergy_id::UUID, v_tenant_id, p_workspace_id, v_patient_id,
                v_substance, 'active', 'document_extraction', p_document_id, p_created_by
            );
            v_allergies_count := v_allergies_count + 1;
            v_affected := v_affected || jsonb_build_array(jsonb_build_object(
                'type', 'Allergy',
                'id',   v_allergy_id,
                'op',   'created'
            ));
        END LOOP;
    END IF;

    -- ------------------------------------------------------------------------
    -- Medications → group by consultation_date → one Prescription per date,
    -- prescription_items as children. Mirrors Python _promote_medications.
    -- ------------------------------------------------------------------------
    -- Build a JSONB grouping: { date_or_unknown: [med_row, ...] }
    v_doc_dates_meds := '{}'::JSONB;
    FOR v_row IN
        SELECT * FROM jsonb_array_elements(
            COALESCE(p_extractions -> 'medications', '[]'::JSONB)
        )
    LOOP
        v_row_date := _promote_doc_normalise_date(v_row ->> 'consultation_date');
        IF v_row_date IS NULL THEN
            v_row_date := '_unknown';
        END IF;
        v_doc_dates_meds := jsonb_set(
            v_doc_dates_meds,
            ARRAY[v_row_date],
            COALESCE(v_doc_dates_meds -> v_row_date, '[]'::JSONB) || jsonb_build_array(v_row),
            TRUE
        );
    END LOOP;

    FOR v_dgroup_date IN
        SELECT jsonb_object_keys(v_doc_dates_meds)
    LOOP
        v_dgroup_rows := v_doc_dates_meds -> v_dgroup_date;

        v_rx_id := gen_random_uuid()::TEXT;
        -- prescriptions.prescription_date is NOT NULL in the live schema.
        -- When meds have no consultation_date the Python promoter passed NULL
        -- (latent bug that didn't surface on PR 1 smoke because all meds had
        -- dates). Fall back to today — matches the encounter-creation behavior
        -- ("no consultation_date → today's encounter").
        v_rx_date := CASE WHEN v_dgroup_date = '_unknown'
                          THEN to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD')
                          ELSE v_dgroup_date END;
        v_encounter_id := COALESCE(
            v_encounter_map ->> v_dgroup_date,
            v_first_encounter
        );

        -- prescriptions.id is TEXT in the live schema (probed); no cast needed.
        -- encounter_id/patient_id are also TEXT (migration 010).
        INSERT INTO prescriptions (
            id, tenant_id, workspace_id, patient_id, encounter_id,
            doctor_name, prescription_date, status,
            source, source_document_id
        ) VALUES (
            v_rx_id, v_tenant_id, p_workspace_id, v_patient_id, v_encounter_id,
            '(Digitised record — prescriber not extracted)',
            v_rx_date::DATE, 'active',
            'document_extraction', p_document_id
        );

        v_affected := v_affected || jsonb_build_array(jsonb_build_object(
            'type', 'Prescription',
            'id',   v_rx_id,
            'op',   'created'
        ));

        FOR v_row IN
            SELECT * FROM jsonb_array_elements(v_dgroup_rows)
        LOOP
            v_med_name := btrim(COALESCE(v_row ->> 'drug_name', v_row ->> 'medication_name', ''));
            IF v_med_name = '' THEN
                CONTINUE;
            END IF;

            v_existing_nappi := NULLIF(btrim(COALESCE(v_row ->> 'nappi_code', '')), '');
            v_existing_atc   := NULLIF(btrim(COALESCE(v_row ->> 'atc_code', '')), '');
            v_extr_generic   := NULLIF(btrim(COALESCE(v_row ->> 'generic_name', '')), '');

            v_resolved_nappi   := v_existing_nappi;
            v_resolved_atc     := v_existing_atc;
            v_resolved_generic := v_extr_generic;
            v_resolved_brand   := NULL;
            v_resolved_atc_desc := NULL;

            IF v_existing_nappi IS NULL THEN
                SELECT * INTO v_nappi_hit
                  FROM _promote_doc_resolve_nappi(v_med_name);
                IF FOUND THEN
                    v_resolved_nappi := v_nappi_hit.nappi_code;
                    IF v_resolved_atc IS NULL THEN
                        v_resolved_atc := v_nappi_hit.atc_code;
                    END IF;
                    IF v_resolved_generic IS NULL THEN
                        v_resolved_generic := v_nappi_hit.generic_name;
                    END IF;
                    v_nappi_inferred := v_nappi_inferred + 1;
                END IF;
            END IF;

            v_rx_item_id := gen_random_uuid()::TEXT;
            -- prescription_items.id is TEXT (probed). prescription_id is TEXT.
            INSERT INTO prescription_items (
                id, prescription_id,
                medication_name, generic_name, nappi_code, atc_code,
                dosage, frequency, duration, quantity, instructions,
                source, source_document_id
            ) VALUES (
                v_rx_item_id, v_rx_id,
                v_med_name, v_resolved_generic, v_resolved_nappi, v_resolved_atc,
                COALESCE(NULLIF(btrim(v_row ->> 'dosage'), ''), '—'),
                COALESCE(NULLIF(btrim(v_row ->> 'frequency'), ''), '—'),
                COALESCE(NULLIF(btrim(v_row ->> 'duration'), ''), '—'),
                -- quantity is TEXT in the live schema (values like '15 tablets'),
                -- not INT — pass through as text, no cast.
                NULLIF(btrim(COALESCE(v_row ->> 'quantity', '')), ''),
                NULLIF(btrim(COALESCE(v_row ->> 'instructions', '')), ''),
                'document_extraction', p_document_id
            );
            v_rx_items_count := v_rx_items_count + 1;
            v_affected := v_affected || jsonb_build_array(jsonb_build_object(
                'type', 'PrescriptionItem',
                'id',   v_rx_item_id,
                'op',   'created'
            ));
        END LOOP;
    END LOOP;

    -- ------------------------------------------------------------------------
    -- Stitch the document to the first encounter + patient.
    -- previous_encounter_id is the captured value from BEFORE wipe so the
    -- reversal can restore it.
    -- ------------------------------------------------------------------------
    UPDATE digitised_documents
       SET patient_id   = v_patient_id,
           encounter_id = v_first_encounter
     WHERE id = p_document_id;

    v_affected := v_affected || jsonb_build_array(jsonb_build_object(
        'type', 'Document',
        'id',   p_document_id,
        'op',   'updated',
        'previous_encounter_id', v_prior_encounter_id
    ));

    -- ------------------------------------------------------------------------
    -- Assemble return payload — mirrors PromotionResult.to_dict() plus
    -- affected_objects.
    -- ------------------------------------------------------------------------
    RETURN jsonb_build_object(
        'patient_id',       v_patient_id,
        'patient_kind',     v_patient_kind,
        'match_confidence', v_match_confidence,
        'patient_summary',  v_patient_summary,
        'encounter_ids',    to_jsonb(v_encounter_ids),
        'counts',           jsonb_build_object(
            'encounters',           coalesce(array_length(v_encounter_ids, 1), 0),
            'allergies',            v_allergies_count,
            'diagnoses',            v_diagnoses_count,
            'vitals',               v_vitals_count,
            'prescription_items',   v_rx_items_count,
            'icd10_codes_inferred', v_icd10_inferred,
            'nappi_codes_inferred', v_nappi_inferred
        ),
        'warnings',         v_warnings,
        'affected_objects', v_affected
    );
END;
$$;

COMMENT ON FUNCTION execute_action_promote_document(TEXT, TEXT, JSONB, TEXT, TEXT, BOOLEAN) IS
    'PR 2 PL/pgSQL port of promote_extractions. Single-transaction ACID; '
    'FOR UPDATE NOWAIT mutual exclusion; ~1-2s typical latency. Returns '
    'PromotionResult-shaped JSONB plus affected_objects for the audit row.';


-- ============================================================================
-- reverse_action_promote_document — functional reversal
-- ============================================================================
--
-- Inputs:
--   p_audit_id      UUID of the original action_audit_log row to reverse.
--   p_actor_user_id TEXT of the user requesting the reversal.
--   p_reason        Optional human reason recorded on the reverse audit row.
--
-- Behavior:
--   1. SELECT FOR UPDATE the original audit row. NOWAIT to fail fast on
--      concurrent reversal attempts.
--   2. Validate: not dry_run, not already reversed. Either failure
--      raises P0001 with a hint the Python wrapper maps to an error code.
--   3. For each affected_objects entry with op='created', DELETE by id
--      from the matching table. Order: PrescriptionItem → Prescription →
--      Diagnosis → Vital → Allergy → Consultation (= encounter).
--      Patient is NOT deleted (preserved across documents).
--   4. Restore digitised_documents.encounter_id from the Document entry's
--      previous_encounter_id.
--   5. INSERT a new action_audit_log row with action_name=
--      'ReverseActionPromoteDocument', reverses_audit_id pointing at the
--      original. Returns the new audit row's id.
--   6. UPDATE the original row's reversed_by_audit_id = new id.
--
-- All in one transaction. If anything fails, the whole reversal rolls
-- back and the original row's pointers stay clean.
--
-- The reversal tolerates outcome='effect_failed' originals — the
-- affected_objects entries describe only what the executor SAW before
-- the crash; DELETE-by-id is idempotent for the rows the failed forward
-- never created.
-- ============================================================================

CREATE OR REPLACE FUNCTION reverse_action_promote_document(
    p_audit_id        UUID,
    p_actor_user_id   TEXT,
    p_reason          TEXT DEFAULT NULL
) RETURNS JSONB
LANGUAGE plpgsql AS $$
DECLARE
    v_audit              action_audit_log%ROWTYPE;
    v_affected           JSONB;
    v_entry              JSONB;
    v_type               TEXT;
    v_id                 TEXT;
    v_op                 TEXT;
    v_doc_id             TEXT;
    v_prior_encounter    TEXT;
    v_new_audit_id       UUID;
    v_reverse_affected   JSONB := '[]'::JSONB;
    v_deleted_counts     JSONB := '{}'::JSONB;
    v_started_at         TIMESTAMPTZ;
    v_finished_at        TIMESTAMPTZ;
    v_deleted_rxi        INT := 0;
    v_deleted_rx         INT := 0;
    v_deleted_diag       INT := 0;
    v_deleted_vital      INT := 0;
    v_deleted_allergy    INT := 0;
    v_deleted_enc        INT := 0;
BEGIN
    SET LOCAL statement_timeout = '25s';
    v_started_at := now();

    -- ------------------------------------------------------------------------
    -- 1. Load + lock the original audit row.
    -- ------------------------------------------------------------------------
    SELECT * INTO v_audit
      FROM action_audit_log
     WHERE id = p_audit_id
     FOR UPDATE NOWAIT;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'action_audit_log row not found: %', p_audit_id
            USING ERRCODE = 'P0001', HINT = 'not_found';
    END IF;

    -- ------------------------------------------------------------------------
    -- 2. Validate.
    -- ------------------------------------------------------------------------
    IF v_audit.dry_run THEN
        RAISE EXCEPTION 'cannot reverse a dry-run audit row: %', p_audit_id
            USING ERRCODE = 'P0001', HINT = 'cannot_reverse_dry_run';
    END IF;

    IF v_audit.reversed_by_audit_id IS NOT NULL THEN
        RAISE EXCEPTION 'audit row % already reversed by %',
                        p_audit_id, v_audit.reversed_by_audit_id
            USING ERRCODE = 'P0001', HINT = 'precondition_failed';
    END IF;

    IF v_audit.action_name <> 'PromoteDocumentToPatientRecord' THEN
        RAISE EXCEPTION 'reverse_action_promote_document called on action %',
                        v_audit.action_name
            USING ERRCODE = 'P0001', HINT = 'invariant_violated';
    END IF;

    v_affected := COALESCE(v_audit.affected_objects, '[]'::JSONB);
    v_doc_id := v_audit.parameters ->> 'document_id';

    -- ------------------------------------------------------------------------
    -- 3. Delete in reverse FK order. Iterate affected_objects 6 times,
    --    once per type, instead of one pass with conditional dispatch —
    --    keeps DELETE order deterministic and explicit.
    -- ------------------------------------------------------------------------

    -- PrescriptionItem
    FOR v_entry IN SELECT * FROM jsonb_array_elements(v_affected) LOOP
        v_type := v_entry ->> 'type';
        v_id   := v_entry ->> 'id';
        v_op   := v_entry ->> 'op';
        IF v_type = 'PrescriptionItem' AND v_op = 'created' THEN
            -- prescription_items.id is TEXT in the live schema (despite
            -- containing UUID-formatted values). TEXT = TEXT, no cast.
            DELETE FROM prescription_items WHERE id = v_id;
            IF FOUND THEN
                v_deleted_rxi := v_deleted_rxi + 1;
            END IF;
            v_reverse_affected := v_reverse_affected || jsonb_build_array(jsonb_build_object(
                'type', v_type, 'id', v_id, 'op', 'reversed_delete'
            ));
        END IF;
    END LOOP;

    -- Prescription
    FOR v_entry IN SELECT * FROM jsonb_array_elements(v_affected) LOOP
        v_type := v_entry ->> 'type';
        v_id   := v_entry ->> 'id';
        v_op   := v_entry ->> 'op';
        IF v_type = 'Prescription' AND v_op = 'created' THEN
            -- prescriptions.id is TEXT in the live schema. TEXT = TEXT.
            DELETE FROM prescriptions WHERE id = v_id;
            IF FOUND THEN
                v_deleted_rx := v_deleted_rx + 1;
            END IF;
            v_reverse_affected := v_reverse_affected || jsonb_build_array(jsonb_build_object(
                'type', v_type, 'id', v_id, 'op', 'reversed_delete'
            ));
        END IF;
    END LOOP;

    -- Diagnosis
    FOR v_entry IN SELECT * FROM jsonb_array_elements(v_affected) LOOP
        v_type := v_entry ->> 'type';
        v_id   := v_entry ->> 'id';
        v_op   := v_entry ->> 'op';
        IF v_type = 'Diagnosis' AND v_op = 'created' THEN
            DELETE FROM diagnoses WHERE id = v_id::UUID;
            IF FOUND THEN
                v_deleted_diag := v_deleted_diag + 1;
            END IF;
            v_reverse_affected := v_reverse_affected || jsonb_build_array(jsonb_build_object(
                'type', v_type, 'id', v_id, 'op', 'reversed_delete'
            ));
        END IF;
    END LOOP;

    -- Vital
    FOR v_entry IN SELECT * FROM jsonb_array_elements(v_affected) LOOP
        v_type := v_entry ->> 'type';
        v_id   := v_entry ->> 'id';
        v_op   := v_entry ->> 'op';
        IF v_type = 'Vital' AND v_op = 'created' THEN
            DELETE FROM vitals WHERE id = v_id::UUID;
            IF FOUND THEN
                v_deleted_vital := v_deleted_vital + 1;
            END IF;
            v_reverse_affected := v_reverse_affected || jsonb_build_array(jsonb_build_object(
                'type', v_type, 'id', v_id, 'op', 'reversed_delete'
            ));
        END IF;
    END LOOP;

    -- Allergy
    FOR v_entry IN SELECT * FROM jsonb_array_elements(v_affected) LOOP
        v_type := v_entry ->> 'type';
        v_id   := v_entry ->> 'id';
        v_op   := v_entry ->> 'op';
        IF v_type = 'Allergy' AND v_op = 'created' THEN
            DELETE FROM allergies WHERE id = v_id::UUID;
            IF FOUND THEN
                v_deleted_allergy := v_deleted_allergy + 1;
            END IF;
            v_reverse_affected := v_reverse_affected || jsonb_build_array(jsonb_build_object(
                'type', v_type, 'id', v_id, 'op', 'reversed_delete'
            ));
        END IF;
    END LOOP;

    -- Document — restore previous_encounter_id BEFORE encounters delete
    -- (otherwise the FK would prevent the encounter delete).
    IF v_doc_id IS NOT NULL THEN
        FOR v_entry IN SELECT * FROM jsonb_array_elements(v_affected) LOOP
            v_type := v_entry ->> 'type';
            v_id   := v_entry ->> 'id';
            v_op   := v_entry ->> 'op';
            IF v_type = 'Document' AND v_op = 'updated' AND v_id = v_doc_id THEN
                v_prior_encounter := v_entry ->> 'previous_encounter_id';
                UPDATE digitised_documents
                   SET encounter_id = v_prior_encounter,
                       patient_id   = NULL
                 WHERE id::TEXT = v_doc_id;
                v_reverse_affected := v_reverse_affected || jsonb_build_array(jsonb_build_object(
                    'type', 'Document', 'id', v_doc_id, 'op', 'reversed_update',
                    'restored_encounter_id', v_prior_encounter
                ));
                EXIT;
            END IF;
        END LOOP;
    END IF;

    -- Consultation (encounter)
    FOR v_entry IN SELECT * FROM jsonb_array_elements(v_affected) LOOP
        v_type := v_entry ->> 'type';
        v_id   := v_entry ->> 'id';
        v_op   := v_entry ->> 'op';
        IF v_type = 'Consultation' AND v_op = 'created' THEN
            -- encounters.id observed as TEXT in dev DB, but cast both sides
            -- defensively in case of schema drift.
            DELETE FROM encounters WHERE id::TEXT = v_id;
            IF FOUND THEN
                v_deleted_enc := v_deleted_enc + 1;
            END IF;
            v_reverse_affected := v_reverse_affected || jsonb_build_array(jsonb_build_object(
                'type', v_type, 'id', v_id, 'op', 'reversed_delete'
            ));
        END IF;
    END LOOP;

    -- Note: Patient rows are NOT deleted by reversal. They may be shared
    -- across documents and may have been created BEFORE this promote;
    -- the wipe deliberately preserved them.

    -- ------------------------------------------------------------------------
    -- 4. Write the new (reversal) audit row and update the original's
    --    back-pointer. Both inside this transaction — no separate Python
    --    INSERT/UPDATE.
    -- ------------------------------------------------------------------------
    v_new_audit_id := gen_random_uuid();
    v_finished_at := now();
    v_deleted_counts := jsonb_build_object(
        'prescription_items', v_deleted_rxi,
        'prescriptions',      v_deleted_rx,
        'diagnoses',          v_deleted_diag,
        'vitals',             v_deleted_vital,
        'allergies',          v_deleted_allergy,
        'encounters',         v_deleted_enc
    );

    INSERT INTO action_audit_log (
        id, action_name, action_version, actor_user_id, actor_email,
        practice_id, workspace_id, idempotency_key, dry_run,
        parameters, preconditions_checked, effects_applied,
        affected_objects, outcome, error_detail,
        reverses_audit_id, reversed_by_audit_id,
        started_at, finished_at, duration_ms
    ) VALUES (
        v_new_audit_id, 'ReverseActionPromoteDocument', 1,
        p_actor_user_id, NULL,
        v_audit.practice_id, v_audit.workspace_id, NULL, FALSE,
        jsonb_build_object(
            'reverses_audit_id', p_audit_id::TEXT,
            'reason',            p_reason
        ),
        '[]'::JSONB, '[]'::JSONB,
        v_reverse_affected, 'reversed', NULL,
        p_audit_id, NULL,
        v_started_at, v_finished_at,
        EXTRACT(MILLISECONDS FROM (v_finished_at - v_started_at))::INT
    );

    UPDATE action_audit_log
       SET reversed_by_audit_id = v_new_audit_id
     WHERE id = p_audit_id;

    RETURN jsonb_build_object(
        'audit_id',         v_new_audit_id,
        'reverses_audit_id', p_audit_id,
        'outcome',          'reversed',
        'deleted_counts',   v_deleted_counts,
        'affected_objects', v_reverse_affected,
        'duration_ms',      EXTRACT(MILLISECONDS FROM (v_finished_at - v_started_at))::INT
    );
END;
$$;

COMMENT ON FUNCTION reverse_action_promote_document(UUID, TEXT, TEXT) IS
    'Reverse a PromoteDocumentToPatientRecord audit row. Deletes by id every '
    'affected_objects entry with op=created (in reverse FK order), restores '
    'the document''s previous_encounter_id, inserts a new audit row with '
    'reverses_audit_id pointing at the original, updates the original''s '
    'reversed_by_audit_id. All atomic. Tolerates effect_failed originals.';


COMMIT;
