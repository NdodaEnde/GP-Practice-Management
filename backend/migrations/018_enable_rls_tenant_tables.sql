-- ============================================================================
-- Migration 018 — Enable Row Level Security on tenant-scoped tables
-- ============================================================================
--
-- THREAT MODEL — read this before assuming what RLS buys here.
--
-- This backend talks to Supabase exclusively via the SERVICE key, which
-- PostgREST runs as the `service_role` Postgres role. `service_role` has
-- rolbypassrls = TRUE (Supabase default, verified). RLS policies DO NOT
-- apply to it. Therefore:
--
--   * Enabling RLS does NOT protect the application's own queries. A
--     backend query that forgets `WHERE workspace_id = ...` still leaks
--     cross-workspace data, because service_role ignores RLS. That gap
--     is closed at the APPLICATION layer by the static query-isolation
--     guard shipped alongside this migration (PR 5,
--     tests/test_tenant_query_isolation.py), NOT by RLS.
--
--   * What RLS DOES close: the client-direct surface. Anyone holding the
--     anon key (or a leaked authenticated token) hitting PostgREST
--     directly. Before this migration, most tenant tables were readable
--     by `anon` if the anon key was ever used directly. After it, anon /
--     authenticated get ZERO rows from these tables — exactly the
--     posture action_audit_log and gp_validation_sessions already had
--     (RLS on, no permissive policy = deny-all to non-bypass roles),
--     which the running app proves is compatible with the service-role
--     backend.
--
-- DESIGN: enable RLS, add NO permissive policy.
--
--   With RLS enabled and no policy, every role WITHOUT rolbypassrls gets
--   zero rows / zero writes. Roles WITH rolbypassrls (service_role — the
--   backend; postgres — migrations + admin scripts) are unaffected. This
--   is the minimal correct deny-all for the client-direct threat.
--
--   We deliberately do NOT use FORCE ROW LEVEL SECURITY. FORCE makes the
--   table owner respect RLS too, but rolbypassrls is role-level and FORCE
--   does not override it — so FORCE would only affect a non-bypass owner.
--   It would, however, break the `postgres` direct-DB role used by
--   migration/admin tooling if that role were ever non-bypass. Plain
--   ENABLE is the correct, reversible choice.
--
--   We deliberately do NOT add auth.jwt()-keyed policies. This app does
--   not use Supabase Auth — end users authenticate through the FastAPI
--   backend, not Supabase, so there is no populated auth.uid()/auth.jwt()
--   to key a policy on. A policy referencing auth.* would be dead code.
--   If a future direct-from-frontend Supabase path is introduced, add
--   per-table SELECT policies keyed on the JWT workspace claim THEN.
--
-- REVERSIBLE: each table can be reverted with
--   ALTER TABLE <t> DISABLE ROW LEVEL SECURITY;
-- The DO block is idempotent — only enables where not already enabled.
--
-- SCOPE: 28 tenant-scoped base tables that hold workspace / tenant /
-- patient-identifiable data and did not already have RLS enabled.
-- (7 others — action_audit_log, gp_validation_sessions, etc. — already
-- had it; this migration leaves them untouched.)
-- ============================================================================

BEGIN;

DO $$
DECLARE
    t TEXT;
    tenant_tables TEXT[] := ARRAY[
        'allergies',
        'clinical_notes',
        'diagnoses',
        'digitised_documents',
        'encounters',
        'epic_patient_hierarchy',
        'extraction_field_mappings',
        'extraction_history',
        'extraction_templates',
        'gp_invoices',
        'immunizations',
        'invoices',
        'lab_orders',
        'medical_aid_claims',
        'patient_conditions',
        'patients',
        'payments',
        'prescription_templates',
        'prescriptions',
        'procedures',
        'referrals',
        'scheduling_appointments',
        'scheduling_waitlist',
        'sick_notes',
        'users',
        'vitals',
        'workspace_users',
        'workspaces'
    ];
BEGIN
    FOREACH t IN ARRAY tenant_tables LOOP
        -- Only act on tables that exist and don't already have RLS on,
        -- so re-running is a clean no-op.
        IF EXISTS (
            SELECT 1 FROM pg_class c
              JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = 'public'
               AND c.relname = t
               AND c.relkind = 'r'
               AND c.relrowsecurity = FALSE
        ) THEN
            EXECUTE format(
                'ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t
            );
            RAISE NOTICE 'RLS enabled on %', t;
        ELSE
            RAISE NOTICE 'RLS already on (or table missing): % — skipped', t;
        END IF;
    END LOOP;
END $$;

COMMIT;
