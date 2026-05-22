-- ============================================================================
-- Migration 033 — Complete RLS coverage across ALL tenant / PHI tables
-- ============================================================================
--
-- WHY THIS EXISTS (read 018 first — same threat model).
--
-- Migration 018 enabled RLS on a broad set of tenant tables, and 027/028
-- enabled it on briefing_items / open_loops. But several tenant/PHI tables
-- ended up RLS-enabled only on the DEV project (ad-hoc / created via the
-- Supabase dashboard, which defaults RLS on) and NOT via any migration —
-- so a freshly-migrated PROJECT (production) would NOT inherit RLS on them.
-- Two tables (lab_results, prescription_items) had no RLS anywhere.
--
-- This migration makes RLS coverage MIGRATION-CAPTURED and complete, so
-- applying the migration history to a fresh database yields the full
-- deny-all-to-non-service posture with no reliance on dashboard state.
--
-- DESIGN (identical to 018):
--   * ENABLE ROW LEVEL SECURITY, add NO permissive policy => every role
--     WITHOUT rolbypassrls (anon, authenticated) gets zero rows / zero
--     writes. service_role (the backend) and postgres (migrations/admin)
--     have rolbypassrls = TRUE and are unaffected — the running app is
--     unchanged. This is defence-in-depth for the client-direct surface
--     (a leaked anon key / token hitting PostgREST), NOT a substitute for
--     the application-layer workspace scoping (test_tenant_query_isolation).
--   * Idempotent: only acts on tables that exist and have RLS currently
--     OFF, so re-running — and running over 018/027/028's work — is a
--     clean no-op.
--   * No FORCE, no auth.* policies (this app does not use Supabase Auth) —
--     same rationale as 018.
--
-- REVERSIBLE: ALTER TABLE public.<t> DISABLE ROW LEVEL SECURITY;
-- ============================================================================

BEGIN;

DO $$
DECLARE
    t TEXT;
    -- Every tenant / PHI / account table. Superset of 018 + tables added
    -- in 008/009/011/014/019-032 + the two that were never covered.
    tenant_tables TEXT[] := ARRAY[
        -- clinical / patient PHI
        'patients',
        'patient_conditions',
        'encounters',
        'diagnoses',
        'vitals',
        'allergies',
        'prescriptions',
        'prescription_items',
        'prescription_templates',
        'clinical_notes',
        'sick_notes',
        'referrals',
        'lab_orders',
        'lab_results',
        'immunizations',
        'procedures',
        'epic_patient_hierarchy',
        -- digitisation pipeline (Essential tier PHI)
        'digitised_documents',
        'gp_parsed_documents',
        'gp_validation_sessions',
        'document_embeddings',
        'digitisation_export_jobs',
        'digitisation_fhir_connections',
        'extraction_history',
        'extraction_templates',
        'extraction_field_mappings',
        -- intelligence / workflow
        'action_audit_log',
        'briefing_items',
        'open_loops',
        -- billing
        'invoices',
        'gp_invoices',
        'payments',
        'medical_aid_claims',
        -- scheduling
        'scheduling_appointments',
        'scheduling_waitlist',
        -- account / tenancy
        'workspaces',
        'workspace_users',
        'users',
        'practice_entitlements'
    ];
BEGIN
    FOREACH t IN ARRAY tenant_tables LOOP
        IF EXISTS (
            SELECT 1 FROM pg_class c
              JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = 'public'
               AND c.relname = t
               AND c.relkind = 'r'
               AND c.relrowsecurity = FALSE
        ) THEN
            EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
            RAISE NOTICE 'RLS enabled on %', t;
        ELSE
            RAISE NOTICE 'RLS already on (or table missing): % — skipped', t;
        END IF;
    END LOOP;
END $$;

COMMIT;

-- ============================================================================
-- Verification (run after applying):
--   SELECT c.relname, c.relrowsecurity
--   FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
--   WHERE n.nspname='public' AND c.relkind='r'
--     AND c.relname = ANY (ARRAY['lab_results','prescription_items',
--                                'gp_validation_sessions','digitised_documents'])
--   ORDER BY c.relname;   -- expect relrowsecurity = t for all
-- ============================================================================
