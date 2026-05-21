-- Migration 031: comma-tolerant numeric vitals in execute_action_promote_document
--
-- South-African clinical documents write decimals with a comma (36,7 °C;
-- 96,1 kg). The vitals_history numeric/int casts in
-- execute_action_promote_document rejected '36,7' (SQLSTATE 22P02),
-- which failed the whole promote — the document validated but no patient
-- record was filed. Clients use '.' and ',' interchangeably, so this
-- recurs on real data.
--
-- This redefines the function verbatim from migration 030, wrapping ONLY
-- the 8 numeric/int vitals cast expressions in translate(x, ',', '.').
-- Scoped to vitals_history numeric/int fields; string fields, dates, and
-- ID numbers are untouched. Vitals carry no thousands separators, so a
-- lone comma is unambiguously a decimal point. Defense-in-depth: the
-- Python promote boundary (PromoteExtractionsViaPromoter) also normalises,
-- so this hardens the RPC against any other / future caller.
--
-- Applied by the principal's explicit per-migration hand. Not auto-run.

BEGIN;

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
    v_rx_prescriber      TEXT;
    v_rx_presc_set       TEXT[];
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
        v_bp_systolic   := NULLIF(btrim(translate(COALESCE(v_row ->> 'bp_systolic', ''), ',', '.')), '')::INT;
        v_bp_diastolic  := NULLIF(btrim(translate(COALESCE(v_row ->> 'bp_diastolic', ''), ',', '.')), '')::INT;
        v_heart_rate    := NULLIF(btrim(translate(COALESCE(v_row ->> 'heart_rate', ''), ',', '.')), '')::INT;
        v_temperature   := NULLIF(btrim(translate(COALESCE(v_row ->> 'temperature_c', ''), ',', '.')), '')::NUMERIC;
        v_spo2          := NULLIF(btrim(translate(COALESCE(v_row ->> 'oxygen_saturation', ''), ',', '.')), '')::INT;
        v_weight_kg     := NULLIF(btrim(translate(COALESCE(v_row ->> 'weight_kg', ''), ',', '.')), '')::NUMERIC;
        v_hba1c         := NULLIF(btrim(translate(COALESCE(v_row ->> 'hba1c', ''), ',', '.')), '')::NUMERIC;
        v_blood_glu     := NULLIF(btrim(translate(COALESCE(v_row ->> 'blood_glucose_fasting', ''), ',', '.')), '')::NUMERIC;

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

        -- Class-3 honest prescriber resolution (030): doctor_name is one
        -- value per prescription but prescribed_by is per-medication.
        -- Every branch is TRUE by construction; btrim-only match can only
        -- over-report ambiguity, never fabricate agreement (fails safe
        -- toward honesty). v_dgroup_rows is the date-group's med rows
        -- (assigned 015:949, unmodified here); jsonb_array_elements over
        -- it is proven valid at this scope (used again at 015:984).
        SELECT array_agg(DISTINCT s.p)
          INTO v_rx_presc_set
          FROM (SELECT NULLIF(btrim(e ->> 'prescribed_by'), '') AS p
                  FROM jsonb_array_elements(v_dgroup_rows) AS e) s
         WHERE s.p IS NOT NULL;

        v_rx_prescriber := CASE
            WHEN v_rx_presc_set IS NULL
              OR array_length(v_rx_presc_set, 1) IS NULL
                THEN '(Digitised record — prescriber not extracted)'
            WHEN array_length(v_rx_presc_set, 1) = 1
                THEN v_rx_presc_set[1]
            ELSE '(Multiple prescribers in source — see medications)'
        END;

        -- prescriptions.id is TEXT in the live schema (probed); no cast needed.
        -- encounter_id/patient_id are also TEXT (migration 010).
        INSERT INTO prescriptions (
            id, tenant_id, workspace_id, patient_id, encounter_id,
            doctor_name, prescription_date, status,
            source, source_document_id
        ) VALUES (
            v_rx_id, v_tenant_id, p_workspace_id, v_patient_id, v_encounter_id,
            v_rx_prescriber,
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
    'PromotionResult-shaped JSONB plus affected_objects for the audit row. '
    'Migration 031: vitals numeric/int casts are comma-tolerant (SA decimals).';

COMMIT;
