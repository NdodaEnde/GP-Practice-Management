-- ============================================================================
-- Migration 024 — Query layer: query_patients_with_diagnosis_prefix (PR 6)
-- ============================================================================
--
-- The first compiled query template. Backs the
-- `patients_with_diagnosis_prefix` registry entry. Establishes the
-- pattern every later query RPC repeats:
--
--   * STABLE, LANGUAGE sql/plpgsql. Pure read — never mutates, never
--     audited (queries are not actions; no action_audit_log row).
--   * p_workspace_id is the MANDATORY first parameter. The Python
--     runner supplies it from the trusted auth context, never from
--     caller params. Tenant scoping is structural: the WHERE clause
--     filters patients.workspace_id = p_workspace_id, so a query
--     physically cannot return another practice's patients.
--   * Returns a TABLE(... provenance jsonb). The provenance object is
--     built IN THE SAME JOIN that produced the fact (diagnoses row →
--     its source_document_id) — never re-derived afterwards, which
--     would risk attributing the wrong document. Verified to
--     round-trip through supabase-py .rpc() as a Python dict
--     (scripts/verify_query_phase0.py, PR 6 Phase 0).
--
-- IDENTIFIER NOTE (migration-015 scar): patients.id and
-- diagnoses.patient_id are both TEXT in the live schema. The join is
-- TEXT = TEXT with NO ::uuid cast. Verified by the Phase-0 probe.
--
-- ============================================================================
-- POSTGREST SCHEMA-CACHE — DO NOT REMOVE THE NOTIFY AT THE BOTTOM.
--
-- Phase-0 finding: a function created via the psycopg2 DATABASE_URL
-- path is INVISIBLE to PostgREST's .rpc() until PostgREST reloads its
-- schema cache. Without the trailing `NOTIFY pgrst, 'reload schema'`
-- the first call to this template 404s with PGRST202 until the cache
-- happens to refresh. Every query-template migration MUST end with it.
-- After applying, allow a few seconds before the RPC is callable.
-- ============================================================================

BEGIN;

CREATE OR REPLACE FUNCTION query_patients_with_diagnosis_prefix(
    p_workspace_id  TEXT,
    p_icd10_prefix  TEXT,
    p_limit         INT DEFAULT 100
)
RETURNS TABLE(
    patient_id        TEXT,
    first_name        TEXT,
    last_name         TEXT,
    dob               TEXT,
    diagnosis_code    TEXT,
    diagnosis_display TEXT,
    provenance        JSONB
)
LANGUAGE sql STABLE AS $$
    SELECT
        p.id,
        p.first_name,
        p.last_name,
        p.dob,
        d.code,
        d.display,
        jsonb_build_object(
            'source_kind',        'diagnosis',
            -- NULL source_document_id is allowed iff the fact was
            -- entered live (no scan). The result contract enforces
            -- that pairing; here we surface whatever the row has.
            'source_document_id', d.source_document_id,
            'occurred_on',        d.diagnosed_date,
            'snippet',            d.code || COALESCE(' — ' || d.display, ''),
            'page',               NULL
        ) AS provenance
    FROM patients p
    JOIN diagnoses d
      ON d.patient_id = p.id                         -- TEXT = TEXT, no cast
    WHERE p.workspace_id = p_workspace_id             -- structural tenant scope
      AND p.deleted_at IS NULL                        -- migration 020 soft-delete
      AND d.code IS NOT NULL
      AND d.code LIKE p_icd10_prefix || '%'           -- p_icd10_prefix validated
                                                      -- caller-side (no LIKE
                                                      -- metacharacters reach here)
    ORDER BY p.last_name, p.first_name
    LIMIT GREATEST(1, LEAST(p_limit, 500))
$$;

COMMENT ON FUNCTION query_patients_with_diagnosis_prefix(TEXT, TEXT, INT) IS
    'PR 6 query layer. Patients whose diagnosis ICD-10 code starts with '
    'p_icd10_prefix, scoped to p_workspace_id. STABLE read-only; every '
    'row carries provenance built from the diagnoses source document. '
    'Backed by the patients_with_diagnosis_prefix registry template.';

-- Phase-0 finding — MANDATORY. See header. Without this the template's
-- first .rpc() call 404s (PGRST202) until PostgREST refreshes.
NOTIFY pgrst, 'reload schema';

COMMIT;
