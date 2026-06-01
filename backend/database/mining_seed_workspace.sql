-- ============================================================
-- Mining Gateway / Financial-Disclosure — seed the Exxaro workspace
-- ============================================================
-- Idempotent: re-runs are no-ops via INSERT … ON CONFLICT (slug) DO NOTHING.
-- The Supabase REST check before this migration returned zero rows, so the
-- first run creates the workspace.
--
-- After this file runs:
--   * fd_entity_registry, fd_assets, etc. can be seeded with this workspace_id.
--   * The backend's `current_user["workspace_id"]` must equal this row's id
--     for any Mining/FD API call. Wire-up of user → workspace_users happens
--     separately (see the TODO at the end of this file).
-- ============================================================

INSERT INTO workspaces (
    name,
    slug,
    organization_name,
    organization_type,
    contact_email,
    tenant_id,
    country,
    subscription_tier,
    subscription_status,
    is_active,
    metadata
)
VALUES (
    'Exxaro Transition Intelligence',
    'exxaro-fd',
    'Exxaro Resources Limited',
    'mining_corporate_disclosure',
    'fd@progno-labs.dev',
    'mining-exxaro-fd-001',
    'South Africa',
    'professional',
    'active',
    TRUE,
    jsonb_build_object(
        'gateway', 'mining',
        'module',  'financial_disclosure',
        'first_account', 'exxaro',
        'spec_version', '0.5',
        'source_year_range', jsonb_build_array(2022, 2023, 2024, 2025)
    )
)
ON CONFLICT (slug) DO NOTHING;

-- ------------------------------------------------------------
-- Sanity check the seed exists. Returns one row with the workspace UUID.
-- Useful when copy-pasting the UUID into the next seed file.
-- ------------------------------------------------------------
-- SELECT id, name, slug, tenant_id FROM workspaces WHERE slug = 'exxaro-fd';

-- ------------------------------------------------------------
-- TODO (step 2 setup, not blocking the migration itself):
--   * Decide which dev/test user should be bound to this workspace via
--     workspace_users (role: 'owner' for the engineer, 'member' for QA).
--   * Confirm the production-vs-dev tenant_id convention with the rest of the
--     platform's onboarding flow (backend/scripts/onboard_practice.py) — if
--     prod uses a different tenant_id format, override before going live.
-- ------------------------------------------------------------
