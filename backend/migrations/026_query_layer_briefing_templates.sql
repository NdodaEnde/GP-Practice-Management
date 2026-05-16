-- ============================================================================
-- Migration 026 — Query layer: briefing / pre-consult template set (PR B)
-- ============================================================================
--
-- Adds the PR B briefing shapes, each repeating migration 024's pattern:
--
--   * LANGUAGE sql STABLE. Pure read — never mutates, never audited.
--   * p_workspace_id is the MANDATORY first parameter, supplied by the
--     Python runner from the trusted auth context, never from caller
--     params. Tenant scoping is structural (WHERE <fact>.workspace_id =
--     p_workspace_id, or via the patients join's workspace filter).
--   * Returns TABLE(... provenance jsonb). Provenance is built IN THE
--     SAME JOIN that produced the fact — never re-derived.
--
-- LOAD-BEARING (PR B finding §1.6): the only naturally-entitled
-- workspace (demo-gp-workspace-001, via legacy_full_access_grant) has
-- EVERY clinical fact NULL-sourced. The result contract
-- (Provenance.__post_init__) refuses a sourced fact with no source
-- unless source_kind == 'live_entry'. Therefore every function below
-- emits:
--     'source_kind',
--     CASE WHEN <fact>.source_document_id IS NULL
--          THEN 'live_entry' ELSE '<factkind>' END
-- Without this, the very first briefing query on the only workspace it
-- can run on would raise provenance_missing on every row.
--
-- IDENTIFIER NOTE (migration-015 scar, re-verified 2026-05-16): all
-- patient joins are TEXT = TEXT with NO ::uuid cast (patients.id,
-- *.patient_id, prescription_items.prescription_id are all TEXT;
-- diagnoses.id / vitals.id are uuid but are never join keys here).
--
-- RETURN-TYPE NOTE (premise corrected — do not "fix" to CREATE OR
-- REPLACE): query_patients_with_diagnosis_prefix changes its RETURNS
-- TABLE (adds last_consultation) and its signature (adds p_order_by).
-- PostgreSQL CREATE OR REPLACE FUNCTION CANNOT change a function's
-- return type, so the diagnosis template is DROP + CREATE, not CREATE OR
-- REPLACE. The six new functions are plain CREATE OR REPLACE.
--
-- ORDERING: 026 strictly after 025. The diagnosis re-creation
-- supersedes migration 024's definition (registry version 2 > 1). The
-- deploy must wait for the PostgREST schema-cache reload before the new
-- templates are callable (runner returns template_unavailable/503 until
-- then — operational, not retried).
--
-- POSTGREST SCHEMA-CACHE — MANDATORY trailing NOTIFY (Phase-0 finding).
-- 026 ADDS functions, so — unlike 025, which correctly omits it because
-- it adds no function — 026 MUST end with NOTIFY pgrst or every new
-- template 404s (PGRST202) until the cache happens to reload. Enforced
-- by tests/test_query_layer_invariants.py::
-- test_026_migration_ends_with_notify_pgrst.
-- ============================================================================

BEGIN;

-- ── 1/7 — diagnosis template v2: +order_by, +last_consultation ──────────────
-- DROP + CREATE (return type changes; CREATE OR REPLACE cannot).
DROP FUNCTION IF EXISTS query_patients_with_diagnosis_prefix(TEXT, TEXT, INT);

CREATE FUNCTION query_patients_with_diagnosis_prefix(
    p_workspace_id  TEXT,
    p_icd10_prefix  TEXT,
    p_limit         INT  DEFAULT 100,
    p_order_by      TEXT DEFAULT 'name'      -- 'name' | 'last_consultation'
)
RETURNS TABLE(
    patient_id         TEXT,
    first_name         TEXT,
    last_name          TEXT,
    dob                TEXT,
    diagnosis_code     TEXT,
    diagnosis_display  TEXT,
    last_consultation  TEXT,
    provenance         JSONB
)
LANGUAGE sql STABLE AS $$
    SELECT
        p.id, p.first_name, p.last_name, p.dob,
        d.code, d.display,
        (SELECT to_char(max(e.encounter_date), 'YYYY-MM-DD')
           FROM encounters e WHERE e.patient_id = p.id),
        jsonb_build_object(
            'source_kind',
            CASE WHEN d.source_document_id IS NULL
                 THEN 'live_entry' ELSE 'diagnosis' END,
            'source_document_id', d.source_document_id,
            'occurred_on',        d.diagnosed_date,
            'snippet',            d.code || COALESCE(' — ' || d.display, ''),
            'page',               NULL
        )
    FROM patients p
    JOIN diagnoses d ON d.patient_id = p.id            -- TEXT = TEXT
    WHERE p.workspace_id = p_workspace_id              -- structural tenant scope
      AND p.deleted_at IS NULL                         -- migration 020 soft-delete
      AND d.code IS NOT NULL
      AND d.code LIKE p_icd10_prefix || '%'            -- prefix validated caller-side
    ORDER BY
        CASE WHEN p_order_by = 'last_consultation'
             THEN (SELECT max(e.encounter_date)
                     FROM encounters e WHERE e.patient_id = p.id)
        END DESC NULLS LAST,
        p.last_name, p.first_name
    LIMIT GREATEST(1, LEAST(p_limit, 500))
$$;

COMMENT ON FUNCTION query_patients_with_diagnosis_prefix(TEXT, TEXT, INT, TEXT)
IS 'PR B v2. Diagnosis-prefix cohort; +p_order_by (name|last_consultation), '
   '+last_consultation column. Supersedes migration 024. Provenance in-join.';

-- ── 2/7 — patients not seen since N days (or never) ─────────────────────────
CREATE OR REPLACE FUNCTION query_patients_not_seen_since(
    p_workspace_id  TEXT,
    p_days_since    INT DEFAULT 180
)
RETURNS TABLE(
    patient_id         TEXT,
    first_name         TEXT,
    last_name          TEXT,
    dob                TEXT,
    last_consultation  TEXT,
    provenance         JSONB
)
LANGUAGE sql STABLE AS $$
    SELECT
        p.id, p.first_name, p.last_name, p.dob,
        to_char(le.encounter_date, 'YYYY-MM-DD'),
        jsonb_build_object(
            'source_kind',
            CASE WHEN le.source_document_id IS NULL
                 THEN 'live_entry' ELSE 'encounter' END,
            'source_document_id', le.source_document_id,
            'occurred_on',        to_char(le.encounter_date, 'YYYY-MM-DD'),
            'snippet',
            CASE WHEN le.encounter_date IS NULL THEN 'never seen'
                 ELSE 'last seen ' || to_char(le.encounter_date,
                                              'YYYY-MM-DD') END,
            'page', NULL
        )
    FROM patients p
    LEFT JOIN LATERAL (
        SELECT e.encounter_date, e.source_document_id
          FROM encounters e
         WHERE e.patient_id = p.id
         ORDER BY e.encounter_date DESC NULLS LAST
         LIMIT 1
    ) le ON TRUE
    WHERE p.workspace_id = p_workspace_id
      AND p.deleted_at IS NULL
      AND (le.encounter_date IS NULL
           OR le.encounter_date
              < (now() - make_interval(days => GREATEST(0, p_days_since))))
    ORDER BY le.encounter_date ASC NULLS FIRST, p.last_name, p.first_name
    LIMIT 500
$$;

COMMENT ON FUNCTION query_patients_not_seen_since(TEXT, INT)
IS 'PR B. Patients with no encounter in the last p_days_since days (or '
   'never). Provenance = the last encounter (NULL-source ⇒ live_entry).';

-- ── 3/7 — a patient''s active medications ───────────────────────────────────
CREATE OR REPLACE FUNCTION query_patient_active_medications(
    p_workspace_id  TEXT,
    p_patient_id    TEXT
)
RETURNS TABLE(
    medication_name    TEXT,
    dosage             TEXT,
    frequency          TEXT,
    prescription_date  TEXT,
    provenance         JSONB
)
LANGUAGE sql STABLE AS $$
    SELECT
        pi.medication_name, pi.dosage, pi.frequency,
        to_char(pr.prescription_date, 'YYYY-MM-DD'),
        jsonb_build_object(
            'source_kind',
            CASE WHEN COALESCE(pi.source_document_id,
                               pr.source_document_id) IS NULL
                 THEN 'live_entry' ELSE 'prescription' END,
            'source_document_id',
            COALESCE(pi.source_document_id, pr.source_document_id),
            'occurred_on', to_char(pr.prescription_date, 'YYYY-MM-DD'),
            'snippet',     pi.medication_name
                           || COALESCE(' ' || pi.dosage, ''),
            'page', NULL
        )
    FROM patients p
    JOIN prescriptions pr      ON pr.patient_id = p.id
    JOIN prescription_items pi ON pi.prescription_id = pr.id
    WHERE p.workspace_id = p_workspace_id
      AND p.deleted_at IS NULL
      AND pr.patient_id = p_patient_id
      AND pr.status = 'active'
      AND pr.void_reason IS NULL                       -- migration 020 void
    ORDER BY pr.prescription_date DESC NULLS LAST, pi.medication_name
    LIMIT 500
$$;

COMMENT ON FUNCTION query_patient_active_medications(TEXT, TEXT)
IS 'PR B. Active, non-voided prescription items for one patient. '
   'Provenance from the item (NULL-source ⇒ live_entry).';

-- ── 4/7 — a patient''s recent consultations ─────────────────────────────────
CREATE OR REPLACE FUNCTION query_patient_recent_consultations(
    p_workspace_id  TEXT,
    p_patient_id    TEXT,
    p_limit         INT DEFAULT 50
)
RETURNS TABLE(
    encounter_id     TEXT,
    encounter_date   TEXT,
    chief_complaint  TEXT,
    status           TEXT,
    provenance       JSONB
)
LANGUAGE sql STABLE AS $$
    SELECT
        e.id, to_char(e.encounter_date, 'YYYY-MM-DD'),
        e.chief_complaint, e.status,
        jsonb_build_object(
            'source_kind',
            CASE WHEN e.source_document_id IS NULL
                 THEN 'live_entry' ELSE 'encounter' END,
            'source_document_id', e.source_document_id,
            'occurred_on', to_char(e.encounter_date, 'YYYY-MM-DD'),
            'snippet',
            COALESCE(NULLIF(e.chief_complaint, ''), 'consultation'),
            'page', NULL
        )
    FROM patients p
    JOIN encounters e ON e.patient_id = p.id
    WHERE p.workspace_id = p_workspace_id
      AND p.deleted_at IS NULL
      AND e.patient_id = p_patient_id
    ORDER BY e.encounter_date DESC NULLS LAST
    LIMIT GREATEST(1, LEAST(p_limit, 500))
$$;

COMMENT ON FUNCTION query_patient_recent_consultations(TEXT, TEXT, INT)
IS 'PR B. A patient''s most recent encounters. Provenance from the '
   'encounter (NULL-source ⇒ live_entry).';

-- ── 5/7 — patients with abnormal recent vitals (DATA-THIN) ──────────────────
CREATE OR REPLACE FUNCTION query_patients_with_abnormal_recent_vitals(
    p_workspace_id  TEXT,
    p_within_days   INT DEFAULT 90
)
RETURNS TABLE(
    patient_id        TEXT,
    first_name        TEXT,
    last_name         TEXT,
    bp_systolic       INT,
    bp_diastolic      INT,
    measured_datetime TEXT,
    provenance        JSONB
)
LANGUAGE sql STABLE AS $$
    SELECT
        p.id, p.first_name, p.last_name,
        v.bp_systolic, v.bp_diastolic,
        to_char(v.measured_datetime, 'YYYY-MM-DD'),
        jsonb_build_object(
            'source_kind',
            CASE WHEN v.source_document_id IS NULL
                 THEN 'live_entry' ELSE 'vital' END,
            'source_document_id', v.source_document_id,
            'occurred_on', to_char(v.measured_datetime, 'YYYY-MM-DD'),
            'snippet', 'BP ' || COALESCE(v.bp_systolic::text, '?')
                       || '/' || COALESCE(v.bp_diastolic::text, '?'),
            'page', NULL
        )
    FROM patients p
    JOIN vitals v ON v.patient_id = p.id
    WHERE p.workspace_id = p_workspace_id
      AND p.deleted_at IS NULL
      AND v.measured_datetime
          >= (now() - make_interval(days => GREATEST(0, p_within_days)))
      AND (v.bp_systolic > 140 OR v.bp_diastolic > 90)
    ORDER BY v.measured_datetime DESC NULLS LAST
    LIMIT 500
$$;

COMMENT ON FUNCTION query_patients_with_abnormal_recent_vitals(TEXT, INT)
IS 'PR B. data_maturity=thin (corpus: 0 vitals in demo-gp, 5 globally). '
   'Abnormal = systolic>140 or diastolic>90. Provenance from the vital.';

-- ── 6/7 — open documents (the document IS the source) ───────────────────────
CREATE OR REPLACE FUNCTION query_patient_open_documents(
    p_workspace_id  TEXT,
    p_patient_id    TEXT DEFAULT NULL,
    p_limit         INT  DEFAULT 100
)
RETURNS TABLE(
    document_id   TEXT,
    filename      TEXT,
    status        TEXT,
    upload_date   TEXT,
    provenance    JSONB
)
LANGUAGE sql STABLE AS $$
    SELECT
        dd.id, dd.filename, dd.status,
        to_char(dd.upload_date, 'YYYY-MM-DD'),
        jsonb_build_object(
            -- The document itself is the source; dd.id is never NULL, so
            -- this is always 'document' (the CASE keeps the pattern
            -- uniform and future-proof).
            'source_kind',
            CASE WHEN dd.id IS NULL THEN 'live_entry' ELSE 'document' END,
            'source_document_id', dd.id,
            'occurred_on', to_char(dd.upload_date, 'YYYY-MM-DD'),
            'snippet', dd.filename,
            'page', NULL
        )
    FROM digitised_documents dd
    WHERE dd.workspace_id = p_workspace_id
      AND dd.status <> 'validated'                     -- 'open' = not finalised
      AND (p_patient_id IS NULL OR dd.patient_id = p_patient_id)
    ORDER BY dd.upload_date DESC NULLS LAST
    LIMIT GREATEST(1, LEAST(p_limit, 500))
$$;

COMMENT ON FUNCTION query_patient_open_documents(TEXT, TEXT, INT)
IS 'PR B. Documents not yet finalised (status <> validated), optionally '
   'for one patient. Provenance is self-referential (the doc).';

-- ── 7/7 — patients with a lab result over a threshold (SCHEMA-ONLY) ─────────
CREATE OR REPLACE FUNCTION query_patients_with_lab_threshold(
    p_workspace_id  TEXT,
    p_test_code     TEXT,
    p_min_value     DOUBLE PRECISION DEFAULT 0
)
RETURNS TABLE(
    patient_id      TEXT,
    first_name      TEXT,
    last_name       TEXT,
    test_name       TEXT,
    result_numeric  NUMERIC,
    reference_high  NUMERIC,
    provenance      JSONB
)
LANGUAGE sql STABLE AS $$
    SELECT
        p.id, p.first_name, p.last_name,
        lr.test_name, lr.result_numeric, lr.reference_high,
        jsonb_build_object(
            'source_kind',
            CASE WHEN COALESCE(lr.source_document_id,
                               lo.source_document_id) IS NULL
                 THEN 'live_entry' ELSE 'lab_result' END,
            'source_document_id',
            COALESCE(lr.source_document_id, lo.source_document_id),
            'occurred_on', to_char(lr.result_datetime, 'YYYY-MM-DD'),
            'snippet', lr.test_name
                       || ' = ' || COALESCE(lr.result_numeric::text, '?'),
            'page', NULL
        )
    FROM patients p
    JOIN lab_orders  lo ON lo.patient_id = p.id
    JOIN lab_results lr ON lr.lab_order_id = lo.id
    WHERE p.workspace_id = p_workspace_id
      AND p.deleted_at IS NULL
      AND lr.test_code = p_test_code
      AND lr.result_numeric IS NOT NULL
      AND lr.result_numeric >= p_min_value
    ORDER BY lr.result_numeric DESC NULLS LAST
    LIMIT 500
$$;

COMMENT ON FUNCTION query_patients_with_lab_threshold(TEXT, TEXT, DOUBLE PRECISION)
IS 'PR B. data_maturity=schema_only (corpus: 1 lab_result globally, no '
   'LOINC). Provenance from the lab_result (NULL-source ⇒ live_entry).';

-- Phase-0 finding — MANDATORY. 026 adds functions; without this every
-- new template 404s (PGRST202) until PostgREST refreshes its cache.
NOTIFY pgrst, 'reload schema';

COMMIT;
