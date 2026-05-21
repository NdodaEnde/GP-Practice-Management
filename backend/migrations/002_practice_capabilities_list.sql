-- ============================================================================
-- Migration 002: practice_capabilities() list function (Phase 2)
-- ============================================================================
--
-- Adds a companion to practice_has_capability() that returns the FULL list of
-- capability IDs a practice currently has via active entitlements.
--
-- Why: the /api/auth/me endpoint hydrates the frontend with the full set of
-- capabilities so the UI can render gating (locked/unlocked states, upsell
-- cards) WITHOUT making a roundtrip per-component. The frontend's
-- AuthContext.hasCapability(id) helper is a pure JS membership check on this
-- preloaded list. New entitlement → user re-logs (or refreshes) → updated
-- list. Acceptable trade-off for v1 (<100 customers); revisit caching later.
--
-- Run AFTER 001_entitlements_core.sql + the seed.
-- Idempotent (CREATE OR REPLACE).
-- ============================================================================

CREATE OR REPLACE FUNCTION practice_capabilities(p_practice_id TEXT)
RETURNS TEXT[]
LANGUAGE SQL
STABLE
PARALLEL SAFE
AS $$
    SELECT COALESCE(
        ARRAY(
            SELECT DISTINCT pc.capability_id
            FROM practice_entitlements pe
            JOIN product_capabilities pc ON pc.product_id = pe.product_id
            WHERE pe.practice_id = p_practice_id
              AND pe.status = 'active'
              AND (pe.ends_at IS NULL OR pe.ends_at > now())
            ORDER BY pc.capability_id
        ),
        ARRAY[]::TEXT[]
    );
$$;

COMMENT ON FUNCTION practice_capabilities IS
    'Returns the deduplicated list of capability IDs granted to a practice via active, non-expired entitlements. Empty array if none. Used by /api/auth/me to hydrate frontend AuthContext.';

-- ============================================================================
-- Verification (run after migration applied):
--
-- -- Practice with no entitlements
-- SELECT practice_capabilities('fake-practice');
--   -- expects: {}
--
-- -- demo-gp-workspace-001 (grandfathered with legacy_full_access_grant)
-- SELECT practice_capabilities('demo-gp-workspace-001');
--   -- expects: array of all 31 capability IDs
--
-- -- Cardinality check
-- SELECT cardinality(practice_capabilities('demo-gp-workspace-001'));
--   -- expects: 31
-- ============================================================================
