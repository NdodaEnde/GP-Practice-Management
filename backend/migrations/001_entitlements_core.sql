-- ============================================================================
-- Migration 001: Entitlements core (Phase 1 — "Take Money")
-- ============================================================================
--
-- Adds the v2 entitlement model from the SurgiScan plan-of-record.
--
-- Background: in v1 the codebase used a single `workspaces.subscription_tier`
-- enum (free / basic / professional / enterprise). v2 sells two product lines
-- à la carte (Practice Platform tiers + Intelligence Layer modules), so a
-- single enum can no longer represent what a practice has bought.
--
-- This migration creates 5 catalog/entitlement tables and 1 SQL function:
--   1. products              — SKUs available for sale
--   2. capabilities          — atomic feature flags the application checks
--   3. product_capabilities  — which capabilities each product unlocks
--   4. pricing_bands         — per-product price brackets (currently used for
--                              Practice Platform Solo/Small/Medium bands;
--                              Digitisation tier prices live in
--                              digitisation_plan_allowances added in Phase 4)
--   5. practice_entitlements — the source of truth for what a practice has
--                              bought; Paystack subscription is a foreign
--                              reference, NOT primary
--   6. practice_has_capability(practice_id, capability_id) — authorization
--      helper used everywhere in the application
--
-- Naming note: the existing customer table is `workspaces`. In strategy docs
-- this is referred to as a "practice." practices and workspaces are synonyms
-- in this codebase.
--
-- v1.2 strategy doc: /Users/luzuko/Complete Doctor Suite/STRATEGY_HEALTHCARE_TIERING_v1.2.md
-- Plan of record:   /Users/luzuko/.claude/plans/we-are-a-healthtech-sparkling-shamir.md
--
-- This migration is idempotent (uses IF NOT EXISTS / OR REPLACE). Running it
-- twice is safe.
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- 1. products: catalog of SKUs available for sale
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS products (
    id                  TEXT PRIMARY KEY,
    product_line        TEXT NOT NULL CHECK (product_line IN ('practice_platform', 'intelligence_layer', 'internal_bundle')),
    display_name        TEXT NOT NULL,
    description         TEXT,
    is_internal_only    BOOLEAN NOT NULL DEFAULT FALSE,  -- TRUE = not on customer-facing brochure (e.g. Foundation Bundle)
    active              BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE products IS
    'Hand-curated catalog of SKUs. v2 has 5 customer-facing products (Practice Essential, Practice Professional, Module Digitisation, Module Analytics, Module Clinical AI Beta) + 1 internal Foundation Bundle.';

-- ----------------------------------------------------------------------------
-- 2. capabilities: atomic feature flags
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS capabilities (
    id                  TEXT PRIMARY KEY,
    display_name        TEXT NOT NULL,
    description         TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE capabilities IS
    'Atomic feature flags. Application code calls practice_has_capability() against these IDs, NOT against tier names. New capabilities are added when new features ship; deprecated ones are removed only when fully sunset.';

-- ----------------------------------------------------------------------------
-- 3. product_capabilities: which capabilities each product unlocks
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS product_capabilities (
    product_id          TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    capability_id       TEXT NOT NULL REFERENCES capabilities(id) ON DELETE CASCADE,
    PRIMARY KEY (product_id, capability_id)
);

CREATE INDEX IF NOT EXISTS idx_product_capabilities_capability
    ON product_capabilities(capability_id);

COMMENT ON TABLE product_capabilities IS
    'M:N mapping. A product unlocks one or more capabilities; a capability can be granted by multiple products (e.g. Foundation Bundle grants Digitisation + Analytics caps).';

-- ----------------------------------------------------------------------------
-- 4. pricing_bands: per-product price tiers
--
-- Currently used for Practice Platform tiers banded by permanent doctor count
-- (Solo / Small / Medium / Group). Digitisation tier prices (Starter / Growth /
-- Scale) are NOT stored here — they live in digitisation_plan_allowances which
-- is added in Phase 4. Module Analytics is flat per practice and doesn't need
-- a band; we skip seeding it here and just record its price on the Paystack
-- plan directly.
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS pricing_bands (
    id                              TEXT PRIMARY KEY,
    product_id                      TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    band_name                       TEXT NOT NULL,                          -- 'Solo' | 'Small' | 'Medium' | 'Group'
    min_doctors                     INTEGER NOT NULL CHECK (min_doctors > 0),
    max_doctors                     INTEGER CHECK (max_doctors IS NULL OR max_doctors >= min_doctors),  -- NULL = unbounded (e.g. Group 7+)
    monthly_price_cents_founder     INTEGER NOT NULL CHECK (monthly_price_cents_founder >= 0),
    monthly_price_cents_list        INTEGER NOT NULL CHECK (monthly_price_cents_list >= monthly_price_cents_founder),
    paystack_plan_code_founder      TEXT,                                   -- populated after Paystack plan creation
    paystack_plan_code_list         TEXT,
    active                          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pricing_bands_product
    ON pricing_bands(product_id);

COMMENT ON TABLE pricing_bands IS
    'Doctor-count-banded pricing for Practice Platform tiers. Each row has BOTH founder and list price + plan codes; the founder/list distinction lives at the Paystack subscription level (which plan code the practice''s subscription is tied to). v1.2 lock: founder pricing for customers signing before 31 Aug 2026, locked 12 months from signup with 60-day transition notice.';

-- ----------------------------------------------------------------------------
-- 5. practice_entitlements: source of truth for what a practice has bought
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS practice_entitlements (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Note: workspaces.id is TEXT in this codebase (e.g. 'demo-gp-workspace-001'),
    -- not UUID. Match the parent column type for the FK to work.
    practice_id                 TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    product_id                  TEXT NOT NULL REFERENCES products(id),
    status                      TEXT NOT NULL CHECK (status IN ('active', 'paused', 'cancelled')),
    payment_status              TEXT NOT NULL CHECK (payment_status IN ('paid', 'pending', 'attention', 'failed', 'manual')),
    paystack_subscription_code  TEXT,                                       -- foreign reference; nullable for manually-billed customers
    paystack_plan_code          TEXT,                                       -- which specific plan; resolves to founder vs list and band
    pricing_band_id             TEXT REFERENCES pricing_bands(id),          -- nullable for non-banded products (Analytics, Digitisation tiers)
    is_founder_pricing          BOOLEAN NOT NULL DEFAULT FALSE,
    founder_protection_until    TIMESTAMPTZ,                                -- nullable; 12 months from signup for founder customers
    starts_at                   TIMESTAMPTZ NOT NULL DEFAULT now(),
    ends_at                     TIMESTAMPTZ,                                -- NULL = open-ended; webhook charge.success extends this
    metadata                    JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_practice_entitlements_practice
    ON practice_entitlements(practice_id);

CREATE INDEX IF NOT EXISTS idx_practice_entitlements_active
    ON practice_entitlements(practice_id, status, ends_at)
    WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_practice_entitlements_paystack_sub
    ON practice_entitlements(paystack_subscription_code)
    WHERE paystack_subscription_code IS NOT NULL;

COMMENT ON TABLE practice_entitlements IS
    'SurgiScan is source of truth; Paystack is foreign reference. One row per active product subscription. payment_status separate from status so a card-decline doesn''t yank access on first failure (grace period).';

COMMENT ON COLUMN practice_entitlements.is_founder_pricing IS
    'TRUE if this entitlement is on founder pricing (signed before 31 Aug 2026). When founder_protection_until elapses, ops cancels the founder subscription and creates a new entitlement on the list plan.';

-- ----------------------------------------------------------------------------
-- 6. practice_has_capability: authoritative capability check
-- ----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION practice_has_capability(
    p_practice_id   TEXT,
    p_capability_id TEXT
)
RETURNS BOOLEAN
LANGUAGE SQL
STABLE
PARALLEL SAFE
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM practice_entitlements pe
        JOIN product_capabilities pc ON pc.product_id = pe.product_id
        WHERE pe.practice_id = p_practice_id
          AND pc.capability_id = p_capability_id
          AND pe.status = 'active'
          AND (pe.ends_at IS NULL OR pe.ends_at > now())
    );
$$;

COMMENT ON FUNCTION practice_has_capability IS
    'Authoritative capability check used by application code. STABLE so PostgreSQL can optimise within a single query. Returns TRUE iff the practice has an active, non-expired entitlement for any product that grants the named capability. Used by FastAPI''s require_capability() decorator (Phase 2).';

COMMIT;

-- ============================================================================
-- Verification queries (run manually after migration to sanity-check)
-- ============================================================================
--
-- -- Confirm tables exist
-- SELECT table_name FROM information_schema.tables
-- WHERE table_name IN ('products', 'capabilities', 'product_capabilities',
--                      'pricing_bands', 'practice_entitlements');
--
-- -- Confirm function exists
-- SELECT proname, pronargs FROM pg_proc WHERE proname = 'practice_has_capability';
--
-- -- After seeding (002): a practice with no entitlements has no capabilities
-- SELECT practice_has_capability('demo-gp-workspace-001', 'ai_scribe');  -- expects FALSE
--
-- ============================================================================
