-- ############################################################################
-- ##  DISCARDED — DO NOT RUN.  ###############################################
-- ##  This concatenation of migrations/ is NOT a from-zero schema: the
-- ##  numbered migrations are incremental and assume a base schema
-- ##  (workspaces, patients, products, ...) that no migration creates.
-- ##  Running this on an empty project FAILS (proven 2026-05-19).
-- ##  Correct bootstrap: backend/scripts/migrate_dev_to_prod.sh
-- ##  (dumps the real schema + reference data from the DEV database).
-- ############################################################################
-- ============================================================================
-- production_bootstrap.sql  —  ONE-SHOT schema + catalog bootstrap
-- ============================================================================
-- WHAT THIS IS
--   The full SurgiScan schema for a BRAND-NEW, EMPTY production Supabase
--   project: all 32 migrations (001 -> 030, incl. 010b & 013b) in dependency
--   order, followed by the products/capabilities catalog seed. Generated from
--   the verified migration set (drift-checked: list == actual files).
--
-- HOW TO RUN
--   1. Create the new (PAID/Pro) Supabase project. It is empty.
--   2. Supabase Dashboard -> SQL Editor -> paste this whole file -> Run.
--      (Or: psql "<prod connection string>" -f scripts/production_bootstrap.sql)
--   3. Run it ONCE. It is NOT idempotent as a whole (contains ALTER/DROP/
--      INSERT). Do not re-run on a project that already has it.
--   4. If a statement errors: stop, fix it, then resume from that file's
--      "BEGIN <filename>" marker — each file is delimited below.
--
-- ORDER IS FIXED. Do not reorder. 010b must follow 010; 013b must follow 013;
-- the seed runs last (it depends on the entitlement tables from 001).
--
-- SCOPE — this script does the SCHEMA + CATALOG only. It does NOT:
--   * create the `medical-records` Storage bucket  (Dashboard step — see
--     PRODUCTION_ONBOARDING_GUIDE.md Part 1 / "how the new project works")
--   * set the Digitisation customer price — `digitisation_plan_allowances`
--     is created EMPTY; the real price (R3,500 founder / R4,000 list, flat
--     per practice) is the Paystack plan you create (guide Part 2). Running
--     this does NOT bake a wrong price into prod.
--   * create any tenant / workspace / user / entitlement — production starts
--     EMPTY; the first rows are your first real customer via
--     scripts/provision_practice.py (guide Part 4).
--
-- Generated 2026-05-19 from backend/migrations/* + backend/seeds/.
-- ============================================================================



-- ============================================================================
-- ==============  BEGIN  migrations/001_entitlements_core.sql
-- ============================================================================

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


-- ==============  END    migrations/001_entitlements_core.sql  ==============


-- ============================================================================
-- ==============  BEGIN  migrations/002_practice_capabilities_list.sql
-- ============================================================================

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


-- ==============  END    migrations/002_practice_capabilities_list.sql  ==============


-- ============================================================================
-- ==============  BEGIN  migrations/003_digitisation_operational_analytics.sql
-- ============================================================================

-- ============================================================================
-- Migration 003 — Digitisation Operational Analytics capability
-- ============================================================================
-- Adds the operational digitisation analytics capability that ships with
-- module_digitisation (throughput, latency, validation accuracy, page-credit
-- consumption, engine health, peer benchmarking — the Type C "Operational
-- Insights" screen).
--
-- This is DISTINCT from module_analytics (clinical analytics: chronic cohorts,
-- claims aging, drug spend, semantic search). The two surfaces share the word
-- "analytics" but ship under different SKUs and answer different questions.
--
-- Idempotent: safe to re-run.
-- ============================================================================

BEGIN;

-- 1. New capability: operational digitisation analytics
INSERT INTO capabilities (id, display_name, description) VALUES
    ('digitisation_operational_analytics',
     'Digitisation operational analytics',
     'Throughput, latency, validation accuracy, page-credit consumption, engine health, and peer benchmarking for the digitisation pipeline. Ships with Module 01.')
ON CONFLICT (id) DO UPDATE
    SET display_name = EXCLUDED.display_name,
        description  = EXCLUDED.description;

-- 2. Map to module_digitisation
INSERT INTO product_capabilities (product_id, capability_id) VALUES
    ('module_digitisation', 'digitisation_operational_analytics')
ON CONFLICT (product_id, capability_id) DO NOTHING;

-- 3. Map to foundation_bundle (internal SKU includes Digitisation Starter)
INSERT INTO product_capabilities (product_id, capability_id) VALUES
    ('foundation_bundle', 'digitisation_operational_analytics')
ON CONFLICT (product_id, capability_id) DO NOTHING;

-- 4. Map to legacy_full_access_grant (grandfathered customers see everything)
INSERT INTO product_capabilities (product_id, capability_id)
SELECT 'legacy_full_access_grant', 'digitisation_operational_analytics'
WHERE EXISTS (SELECT 1 FROM products WHERE id = 'legacy_full_access_grant')
ON CONFLICT (product_id, capability_id) DO NOTHING;

-- 5. Tighten module_analytics description so "operational" doesn't collide
--    with the digitisation operational analytics surface.
UPDATE products
SET description = 'Population-level clinical analytics. Chronic disease cohorts, claims aging, no-show patterns, doctor productivity, drug spend, semantic search.'
WHERE id = 'module_analytics';

COMMIT;


-- ==============  END    migrations/003_digitisation_operational_analytics.sql  ==============


-- ============================================================================
-- ==============  BEGIN  migrations/004_extraction_metadata.sql
-- ============================================================================

-- ============================================================================
-- Migration 004 — extraction_metadata column on gp_validation_sessions
-- ============================================================================
-- Persist LandingAI ADE's native per-field grounding metadata
-- ({value, references: [chunk_id, ...]}). Without this column, the processor
-- falls back to nesting metadata inside confidence_scores._extraction_metadata
-- (works but conflates two concerns). This migration cleans that up.
--
-- Idempotent: safe to re-run.
-- ============================================================================

BEGIN;

ALTER TABLE gp_validation_sessions
    ADD COLUMN IF NOT EXISTS extraction_metadata JSONB;

COMMENT ON COLUMN gp_validation_sessions.extraction_metadata IS
    'LandingAI ADE per-field grounding metadata. Each leaf has shape '
    '{value, references: [chunk_id, ...]}. Empty references = LLM-inferred; '
    'non-empty = grounded in source text chunks (for traceability + per-field '
    'confidence + click-to-source on the validation panel).';

COMMIT;


-- ==============  END    migrations/004_extraction_metadata.sql  ==============


-- ============================================================================
-- ==============  BEGIN  migrations/005_validation_edit_log.sql
-- ============================================================================

-- ============================================================================
-- Migration 005 — Append-only edit log + frozen AI baseline
-- ============================================================================
-- Implements TRACEABILITY.md item 4 (edit log) + item 5 (original-vs-approved
-- preservation). Required before first paying GP — provides the audit trail
-- regulators (SAHPRA / HPCSA) and malpractice defence both need.
--
-- Two changes:
--   1. extractions_original JSONB on gp_validation_sessions — snapshots the
--      AI's first output at extract time, NEVER modified afterwards. The
--      existing `extractions` column remains the live / approved version.
--      Together they let us answer "what did the AI say vs what did the
--      reviewer approve" forever.
--
--   2. validation_edit_log table — one row per reviewer action (edit, accept,
--      approve, reject). Append-only by convention; no UPDATE or DELETE
--      triggers from the application code path.
--
-- Idempotent: safe to re-run.
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- 1. Frozen AI baseline
-- ----------------------------------------------------------------------------

ALTER TABLE gp_validation_sessions
    ADD COLUMN IF NOT EXISTS extractions_original JSONB;

COMMENT ON COLUMN gp_validation_sessions.extractions_original IS
    'AI extraction output at session creation, NEVER modified after. '
    'Used to answer "what did the AI say vs what did the reviewer approve".';

-- ----------------------------------------------------------------------------
-- 2. Append-only edit log
-- ----------------------------------------------------------------------------

-- Note on column types: digitised_documents.id and gp_validation_sessions.id
-- are TEXT (storing UUID-formatted strings) in the existing schema — see
-- STRATEGY_HEALTHCARE_TIERING_v1.2 §10c "Tech debt: schema UUID/TEXT
-- mismatch". Match those types here so the foreign key works.
CREATE TABLE IF NOT EXISTS validation_edit_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     TEXT        NOT NULL REFERENCES digitised_documents(id) ON DELETE CASCADE,
    session_id      TEXT,                    -- gp_validation_sessions.id at the time of the action
    workspace_id    TEXT        NOT NULL,
    user_email      TEXT,                    -- reviewer who took the action (NULL = system / watcher)
    action          TEXT        NOT NULL CHECK (action IN ('edit', 'accept', 'approve', 'reject', 'reprocess')),
    field_path      TEXT,                    -- e.g. 'patient_demographics.full_names' (NULL for whole-doc actions)
    from_value      JSONB,
    to_value        JSONB,
    notes           TEXT,
    metadata        JSONB,                   -- room for future extensions (e.g. provenance tag, confidence at edit time)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE validation_edit_log IS
    'Append-only audit log of every reviewer action on a validation session. '
    'No UPDATE / DELETE from application code. Required for HPCSA / SAHPRA '
    'audit trail and for active-learning feedback (which fields get corrected most).';

CREATE INDEX IF NOT EXISTS validation_edit_log_document_idx
    ON validation_edit_log (document_id, created_at DESC);

CREATE INDEX IF NOT EXISTS validation_edit_log_workspace_idx
    ON validation_edit_log (workspace_id, created_at DESC);

CREATE INDEX IF NOT EXISTS validation_edit_log_field_idx
    ON validation_edit_log (field_path)
    WHERE field_path IS NOT NULL;

COMMIT;


-- ==============  END    migrations/005_validation_edit_log.sql  ==============


-- ============================================================================
-- ==============  BEGIN  migrations/006_atc_backfill.sql
-- ============================================================================

-- ============================================================================
-- Migration 006 — ATC code backfill scaffolding on nappi_codes
-- ============================================================================
-- Implements TRACEABILITY.md item 6b. The WHO Anatomical Therapeutic Chemical
-- (ATC) classification is public + free; ~95% of nappi_codes rows currently
-- have NULL atc_code. This migration adds the columns we need to (a) store
-- the human-readable class description alongside the code, and (b) keep an
-- audit trail of HOW each row was matched (exact / fuzzy / manual / null) so
-- we can later tighten or re-run the backfill without losing provenance.
--
-- The atc_code column itself already exists from nappi_codes_migration.sql;
-- we only add the descriptive + audit columns here.
--
-- Idempotent: safe to re-run.
-- ============================================================================

BEGIN;

ALTER TABLE nappi_codes
    ADD COLUMN IF NOT EXISTS atc_class_desc   TEXT,
    ADD COLUMN IF NOT EXISTS atc_match_method TEXT,
    ADD COLUMN IF NOT EXISTS atc_source       TEXT,
    ADD COLUMN IF NOT EXISTS atc_matched_at   TIMESTAMPTZ;

-- Constrain match_method to a known vocabulary. Existing NULLs stay NULL.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'nappi_codes_atc_match_method_chk'
    ) THEN
        ALTER TABLE nappi_codes
            ADD CONSTRAINT nappi_codes_atc_match_method_chk
            CHECK (atc_match_method IN ('exact', 'fuzzy', 'manual', 'combo') OR atc_match_method IS NULL);
    END IF;
END$$;

COMMENT ON COLUMN nappi_codes.atc_class_desc   IS
    'WHO ATC class description (level-5 substance name; e.g. "enalapril"). '
    'Populated by backend/scripts/atc_backfill.py.';
COMMENT ON COLUMN nappi_codes.atc_match_method IS
    'How atc_code was assigned: exact (normalized name match), fuzzy '
    '(token/edit-distance match above threshold), combo (combination drug '
    'matched against ATC combination entry), manual (reviewer-applied).';
COMMENT ON COLUMN nappi_codes.atc_source IS
    'Provenance tag for the ATC data used (e.g. "atcd-2026-04-25", '
    '"bioportal-CCBY", "rxnorm-YYYY", "manual"). Used to find rows whose '
    'source needs replacement (e.g. dev-only NC-licensed data swapped for '
    'a commercial-licensed source before GA).';
COMMENT ON COLUMN nappi_codes.atc_matched_at   IS
    'Timestamp the current atc_code/atc_class_desc was applied. Re-runs '
    'overwrite this; rows without an ATC match keep it NULL.';

-- Lookup index for "give me everything in ATC class C09AA*" style queries
-- once the backfill has populated codes. Partial index keeps it small.
CREATE INDEX IF NOT EXISTS idx_nappi_atc_code
    ON nappi_codes (atc_code)
    WHERE atc_code IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_nappi_atc_match_method
    ON nappi_codes (atc_match_method)
    WHERE atc_match_method IS NOT NULL;

COMMIT;


-- ==============  END    migrations/006_atc_backfill.sql  ==============


-- ============================================================================
-- ==============  BEGIN  migrations/007_curated_otc_supplement.sql
-- ============================================================================

-- ============================================================================
-- Migration 007 — Curated OTC supplement support
-- ============================================================================
-- Implements TRACEABILITY.md item 6c. The existing nappi_codes table is
-- almost entirely scheduled prescription medicines (data sourced from a
-- BHF/MIMS-style database). High-frequency SA OTC products (Demazin,
-- Disprin, Med-Lemon, Calpol, Bioplus, Strepsils, Reuterina, Buscopan,
-- etc) aren't in there, so during digitisation those rows get a red
-- "No NAPPI" badge and reviewers have to explain it every time.
--
-- This migration adds the column we need to distinguish CURATED rows
-- (hand-added by us, no real NAPPI code yet) from real_nappi rows
-- (sourced from the official NAPPI/MPP feed). Curated rows use a
-- synthetic id like CURATED-DEMAZIN-001 in nappi_code; the data_source
-- flag is what frontend / backend code branches on.
--
-- Idempotent: safe to re-run.
-- ============================================================================

BEGIN;

ALTER TABLE nappi_codes
    ADD COLUMN IF NOT EXISTS data_source TEXT NOT NULL DEFAULT 'real_nappi';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'nappi_codes_data_source_chk'
    ) THEN
        ALTER TABLE nappi_codes
            ADD CONSTRAINT nappi_codes_data_source_chk
            CHECK (data_source IN ('real_nappi', 'curated'));
    END IF;
END$$;

COMMENT ON COLUMN nappi_codes.data_source IS
    'Origin of this row: real_nappi (sourced from the official NAPPI/MPP '
    'feed; nappi_code is the real code) or curated (hand-added high-'
    'frequency OTC; nappi_code is a synthetic CURATED-<slug>-NNN '
    'placeholder that gets replaced when the real NAPPI lands).';

-- Partial index — most queries that care about data_source are filtering
-- "show me only the real ones" or "show me only the curated ones".
CREATE INDEX IF NOT EXISTS idx_nappi_data_source
    ON nappi_codes (data_source);

COMMIT;


-- ==============  END    migrations/007_curated_otc_supplement.sql  ==============


-- ============================================================================
-- ==============  BEGIN  migrations/008_digitisation_export_jobs.sql
-- ============================================================================

-- ============================================================================
-- Migration 008 — Digitisation export-job tracking
-- ============================================================================
-- Implements the data-side of the Export Centre's "Recent Export History"
-- view. Today the UI shows hardcoded sample rows because there's no place
-- for export attempts to be recorded.
--
-- This migration adds the tracking table only — the actual FHIR / CSV
-- export action (generate bundle, push to remote, etc) remains in
-- backend/app/services/fhir_export.py and is wired by Phase B.
--
-- Idempotent: safe to re-run.
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS digitisation_export_jobs (
    id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    TEXT         NOT NULL,
    batch_id        TEXT         NOT NULL,                    -- human-readable, e.g. EXP-2026-0431
    format          TEXT         NOT NULL,                    -- fhir_r4 | csv | json
    target_system   TEXT,                                     -- e.g. "Discovery Health (FHIR R4)"
    record_count    INT          NOT NULL DEFAULT 0,
    document_ids    TEXT[]       NOT NULL DEFAULT '{}',       -- which docs were in this export
    status          TEXT         NOT NULL DEFAULT 'queued',   -- queued|running|success|partial|failed
    error_message   TEXT,
    bundle_url      TEXT,                                     -- where the generated bundle landed (Storage / external FHIR)
    requested_by    TEXT,                                     -- user_email at request time
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    metadata        JSONB                                     -- room for format-specific extras (e.g. FHIR endpoint config snapshot)
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'digitisation_export_jobs_format_chk'
    ) THEN
        ALTER TABLE digitisation_export_jobs
            ADD CONSTRAINT digitisation_export_jobs_format_chk
            CHECK (format IN ('fhir_r4', 'csv', 'json'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'digitisation_export_jobs_status_chk'
    ) THEN
        ALTER TABLE digitisation_export_jobs
            ADD CONSTRAINT digitisation_export_jobs_status_chk
            CHECK (status IN ('queued', 'running', 'success', 'partial', 'failed'));
    END IF;
END$$;

COMMENT ON TABLE digitisation_export_jobs IS
    'One row per export request from the Type C Export Centre. Records the '
    'request (what / which docs / where to) plus the run outcome. Real FHIR '
    'bundle bytes live in Storage (bundle_url); this table is the index.';

-- Lookups:
--   1. Workspace history view: ORDER BY created_at DESC, filter by workspace
CREATE INDEX IF NOT EXISTS idx_export_jobs_workspace_created
    ON digitisation_export_jobs (workspace_id, created_at DESC);

--   2. "What's still running" worker poll
CREATE INDEX IF NOT EXISTS idx_export_jobs_status_pending
    ON digitisation_export_jobs (status)
    WHERE status IN ('queued', 'running');

COMMIT;


-- ==============  END    migrations/008_digitisation_export_jobs.sql  ==============


-- ============================================================================
-- ==============  BEGIN  migrations/009_fhir_connections.sql
-- ============================================================================

-- ============================================================================
-- Migration 009 — FHIR connections (Type C downstream EHR push)
-- ============================================================================
-- Type C customers buy SurgiScan to digitise paper records and push the
-- structured data into their existing EHR (TrakCare, Practice Perfect,
-- Healthbridge, GoodX, Discovery's FHIR endpoint, etc). They need to
-- configure WHERE the data goes and HOW we authenticate to it.
--
-- This migration creates the connection table. Phase A populates name,
-- URL, environment, and auth_method (no credentials yet). Phase B will
-- add credential storage (Supabase Vault or equivalent) and actually
-- exercise the connection via the export worker.
--
-- One workspace can have multiple connections (e.g. sandbox + production)
-- but only one can be marked is_default — that's the one Export Centre
-- targets when no specific connection is chosen.
--
-- Idempotent: safe to re-run.
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS digitisation_fhir_connections (
    id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    TEXT         NOT NULL,
    name            TEXT         NOT NULL,                  -- e.g. "TrakCare Cape Town Clinic"
    fhir_url        TEXT         NOT NULL,                  -- e.g. "https://endpoint.health/fhir"
    environment     TEXT         NOT NULL DEFAULT 'sandbox',-- sandbox|staging|production
    auth_method     TEXT         NOT NULL DEFAULT 'none',   -- none|basic|bearer|oauth2_client_credentials|smart_on_fhir
    is_default      BOOLEAN      NOT NULL DEFAULT FALSE,    -- one default per workspace; export uses this when not specified
    last_test_at    TIMESTAMPTZ,                            -- when did we last verify connectivity
    last_test_ok    BOOLEAN,                                -- result of last test
    last_test_error TEXT,                                    -- error message from failed test
    created_by      TEXT,                                    -- user_email at create time
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    metadata        JSONB                                    -- room for resource-mapping config (Phase B)
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fhir_connections_environment_chk'
    ) THEN
        ALTER TABLE digitisation_fhir_connections
            ADD CONSTRAINT fhir_connections_environment_chk
            CHECK (environment IN ('sandbox', 'staging', 'production'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fhir_connections_auth_method_chk'
    ) THEN
        ALTER TABLE digitisation_fhir_connections
            ADD CONSTRAINT fhir_connections_auth_method_chk
            CHECK (auth_method IN ('none', 'basic', 'bearer',
                                    'oauth2_client_credentials', 'smart_on_fhir'));
    END IF;
END$$;

COMMENT ON TABLE digitisation_fhir_connections IS
    'Saved FHIR endpoint configurations per workspace. Phase A stores the '
    'connection metadata (name/URL/env/auth_method). Phase B will add '
    'credential storage (Supabase Vault) and actually exercise these in '
    'the export worker.';

CREATE INDEX IF NOT EXISTS idx_fhir_connections_workspace
    ON digitisation_fhir_connections (workspace_id, created_at DESC);

-- Enforce single default per workspace via partial unique index.
CREATE UNIQUE INDEX IF NOT EXISTS idx_fhir_connections_one_default
    ON digitisation_fhir_connections (workspace_id)
    WHERE is_default = TRUE;

COMMIT;


-- ==============  END    migrations/009_fhir_connections.sql  ==============


-- ============================================================================
-- ==============  BEGIN  migrations/010_extraction_promotion_schema.sql
-- ============================================================================

-- ============================================================================
-- Migration 010 — Schema fixes that unblock structured-data promotion
-- ============================================================================
-- The strategy doc §10c calls this out: `diagnoses`, `vitals`, and
-- `allergies` were originally created with `workspace_id`, `tenant_id`,
-- `patient_id`, `encounter_id` as UUID NOT NULL — but the live
-- `patients`, `workspaces`, and `tenants` tables all use TEXT IDs (e.g.
-- 'demo-gp-workspace-001'). Effect: every INSERT into these tables
-- against the demo workspace fails with `22P02 invalid input syntax
-- for type uuid`.
--
-- We've been unable to promote validated digitisation extractions into
-- these tables for that reason — the data sits trapped in
-- `gp_validation_sessions.extractions` JSONB and analytics / patient
-- EHR views see an empty world.
--
-- This migration converts all those columns from UUID → TEXT. Existing
-- UUID values become their canonical string representation
-- ('e8f3...c2'), so no data is lost.
--
-- Idempotent: safe to re-run (each ALTER is guarded with a type check).
--
-- Affected: diagnoses (0 rows), vitals (0 rows), allergies (4 rows).
-- ============================================================================

BEGIN;

-- Helper that flips a column from UUID → TEXT only if it's currently UUID.
-- Wraps the migration so re-runs are no-ops.
CREATE OR REPLACE FUNCTION _alter_uuid_to_text(p_table TEXT, p_column TEXT)
RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE
    cur_type TEXT;
BEGIN
    SELECT data_type INTO cur_type
      FROM information_schema.columns
     WHERE table_schema = 'public'
       AND table_name = p_table
       AND column_name = p_column;
    IF cur_type IS NULL THEN
        RAISE NOTICE 'Column %.% does not exist, skipping', p_table, p_column;
        RETURN;
    END IF;
    IF cur_type = 'uuid' THEN
        EXECUTE format(
            'ALTER TABLE %I ALTER COLUMN %I TYPE TEXT USING %I::text',
            p_table, p_column, p_column);
        RAISE NOTICE 'Converted %.% from uuid to text', p_table, p_column;
    ELSE
        RAISE NOTICE 'Column %.% already %, skipping', p_table, p_column, cur_type;
    END IF;
END$$;

-- ---------------------------------------------------------------------------
-- diagnoses
-- ---------------------------------------------------------------------------
SELECT _alter_uuid_to_text('diagnoses', 'tenant_id');
SELECT _alter_uuid_to_text('diagnoses', 'workspace_id');
SELECT _alter_uuid_to_text('diagnoses', 'patient_id');
SELECT _alter_uuid_to_text('diagnoses', 'encounter_id');
SELECT _alter_uuid_to_text('diagnoses', 'source_document_id');

-- ---------------------------------------------------------------------------
-- vitals
-- ---------------------------------------------------------------------------
-- vitals.bmi is a GENERATED ALWAYS column; the columns it depends on
-- (weight_kg, height_cm) are NUMERIC so unaffected by the type changes
-- below. No drop+recreate needed.
SELECT _alter_uuid_to_text('vitals', 'tenant_id');
SELECT _alter_uuid_to_text('vitals', 'workspace_id');
SELECT _alter_uuid_to_text('vitals', 'patient_id');
SELECT _alter_uuid_to_text('vitals', 'encounter_id');

-- ---------------------------------------------------------------------------
-- allergies (4 existing rows — UUID values become their canonical TEXT form)
-- ---------------------------------------------------------------------------
SELECT _alter_uuid_to_text('allergies', 'tenant_id');
SELECT _alter_uuid_to_text('allergies', 'workspace_id');
SELECT _alter_uuid_to_text('allergies', 'patient_id');
SELECT _alter_uuid_to_text('allergies', 'source_document_id');

-- ---------------------------------------------------------------------------
-- Add columns the promoter writes that may be missing from older schemas.
-- All idempotent.
-- ---------------------------------------------------------------------------

-- diagnoses needs source_document_id for traceability back to the source PDF
ALTER TABLE diagnoses
    ADD COLUMN IF NOT EXISTS source_document_id TEXT;

-- vitals: source flag + source_document_id + a free-text consultation date
-- (the JSONB has consultation_date strings that may not parse cleanly to
-- TIMESTAMPTZ for measured_datetime — keep both)
ALTER TABLE vitals
    ADD COLUMN IF NOT EXISTS source_document_id TEXT,
    ADD COLUMN IF NOT EXISTS consultation_date_text TEXT,
    ADD COLUMN IF NOT EXISTS hba1c             NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS blood_glucose_fasting NUMERIC(5,2);

-- prescriptions: ensure source columns exist (used by promoter)
ALTER TABLE prescriptions
    ADD COLUMN IF NOT EXISTS source              TEXT,
    ADD COLUMN IF NOT EXISTS source_document_id  TEXT;

-- prescription_items: source columns + ATC ride-along (helps analytics
-- without re-joining nappi_codes for digitised rows that may not have
-- a real NAPPI yet)
ALTER TABLE prescription_items
    ADD COLUMN IF NOT EXISTS source              TEXT,
    ADD COLUMN IF NOT EXISTS source_document_id  TEXT,
    ADD COLUMN IF NOT EXISTS atc_code            TEXT;

-- allergies already has source / source_document_id from
-- phase1_patient_safety_migration.sql — no-op here.

-- ---------------------------------------------------------------------------
-- Indexes for promoter idempotency: looking up by source_document_id is the
-- standard "have we already promoted this doc?" check.
-- ---------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_diagnoses_source_doc
    ON diagnoses (source_document_id)
    WHERE source_document_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_vitals_source_doc
    ON vitals (source_document_id)
    WHERE source_document_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_allergies_source_doc
    ON allergies (source_document_id)
    WHERE source_document_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_prescriptions_source_doc
    ON prescriptions (source_document_id)
    WHERE source_document_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- digitised_documents: ensure patient_id linkage column exists (the
-- /gp/validation/confirm-match flow already populates this for healthcare-
-- app users; promoter wants it set by Type C path too).
-- ---------------------------------------------------------------------------

ALTER TABLE digitised_documents
    ADD COLUMN IF NOT EXISTS patient_id   TEXT,
    ADD COLUMN IF NOT EXISTS encounter_id TEXT;

CREATE INDEX IF NOT EXISTS idx_digitised_documents_patient
    ON digitised_documents (patient_id)
    WHERE patient_id IS NOT NULL;

DROP FUNCTION _alter_uuid_to_text(TEXT, TEXT);

COMMIT;


-- ==============  END    migrations/010_extraction_promotion_schema.sql  ==============


-- ============================================================================
-- ==============  BEGIN  migrations/010b_encounters_source_doc.sql
-- ============================================================================

-- ============================================================================
-- Migration 010b — encounters.source_document_id (promoter idempotency)
-- ============================================================================
-- The promoter creates one encounter per consultation_date in the JSONB.
-- Without source_document_id, re-running the approval (idempotency) would
-- accumulate encounter rows on every retry. This adds the column + index
-- and back-fills nothing — encounters created before this migration stay
-- as-is (orphaned legacy rows the user can clean up manually).
--
-- Idempotent: safe to re-run.
-- ============================================================================

BEGIN;

ALTER TABLE encounters
    ADD COLUMN IF NOT EXISTS source_document_id TEXT;

CREATE INDEX IF NOT EXISTS idx_encounters_source_doc
    ON encounters (source_document_id)
    WHERE source_document_id IS NOT NULL;

COMMIT;


-- ==============  END    migrations/010b_encounters_source_doc.sql  ==============


-- ============================================================================
-- ==============  BEGIN  migrations/011_semantic_search.sql
-- ============================================================================

-- ============================================================================
-- Migration 011 — Semantic search infrastructure (pgvector)
-- ============================================================================
-- Implements TRACEABILITY §9. Embedding-based search across digitised
-- documents — the capability the Pricing page already sells via the
-- analytics_semantic_search flag but that has no backend until now.
--
-- Stores per-chunk embeddings keyed by source_document_id, so the indexer
-- can wipe-and-reinsert on doc re-approval (mirrors the promoter's idempotency
-- model). Vector dimension = 1536 (OpenAI text-embedding-3-large with
-- dimensions=1536 truncation — Matryoshka representation; pgvector's
-- ivfflat index caps at 2000 dims, full 3072 would force exact search).
--
-- Idempotent: safe to re-run.
-- ============================================================================

BEGIN;

-- pgvector extension. Supabase enables this with a GUI button OR the SQL below.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS document_embeddings (
    id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    TEXT         NOT NULL,
    document_id     TEXT         NOT NULL,           -- source digitised_documents.id
    patient_id      TEXT,                            -- denormalised for fast workspace+patient filtering
    chunk_index     INT          NOT NULL,           -- position within the doc
    chunk_text      TEXT         NOT NULL,           -- the content embedded — used as snippet on result
    chunk_section   TEXT,                            -- which section it came from (e.g. 'progress_notes', 'medications', 'patient_demographics')
    embedding       vector(1536),                    -- text-embedding-3-large w/ dimensions=1536
    metadata        JSONB,                           -- room for chunk-level extras
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

COMMENT ON TABLE document_embeddings IS
    'Per-chunk embeddings for semantic search. One row per chunk per source '
    'document. Chunks are derived at approval time from the validated '
    'gp_validation_sessions.extractions JSONB plus the structured-table '
    'rows the promoter wrote. Wipe-and-reinsert on re-approval keyed on '
    'document_id.';

-- Idempotency lookup
CREATE INDEX IF NOT EXISTS idx_doc_embeddings_doc
    ON document_embeddings (document_id);

-- Workspace + patient filters before vector search
CREATE INDEX IF NOT EXISTS idx_doc_embeddings_workspace
    ON document_embeddings (workspace_id, patient_id);

-- Approximate nearest-neighbour index for fast cosine-similarity search.
-- ivfflat needs `lists` parameter; for <100k rows, lists=100 is a fine default.
-- Cosine distance is `<=>` operator. Only build the index if it doesn't exist
-- (DROP INDEX + CREATE INDEX is safer than CREATE INDEX IF NOT EXISTS for
-- ivfflat — IF NOT EXISTS works in Postgres 12+ which Supabase runs).
CREATE INDEX IF NOT EXISTS idx_doc_embeddings_cosine
    ON document_embeddings
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- ----------------------------------------------------------------------------
-- Search RPC — wraps pgvector's <=> operator so the Supabase Python SDK can
-- call it via .rpc('digitisation_search', {...}). Returns top N chunks ranked
-- by cosine similarity within a workspace, optionally filtered by patient.
-- ----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION digitisation_search(
    p_workspace_id TEXT,
    p_embedding    vector(1536),
    p_limit        INT  DEFAULT 20,
    p_patient_id   TEXT DEFAULT NULL
)
RETURNS TABLE (
    document_id   TEXT,
    patient_id    TEXT,
    chunk_section TEXT,
    chunk_text    TEXT,
    similarity    REAL
) LANGUAGE sql STABLE AS $$
    SELECT
        document_id,
        patient_id,
        chunk_section,
        chunk_text,
        (1 - (embedding <=> p_embedding))::real AS similarity
      FROM document_embeddings
     WHERE workspace_id = p_workspace_id
       AND (p_patient_id IS NULL OR patient_id = p_patient_id)
     ORDER BY embedding <=> p_embedding
     LIMIT p_limit;
$$;

COMMIT;


-- ==============  END    migrations/011_semantic_search.sql  ==============


-- ============================================================================
-- ==============  BEGIN  migrations/012_production_readiness.sql
-- ============================================================================

-- ============================================================================
-- Migration 012 — Production-readiness schema completion
-- ============================================================================
-- Several gaps surfaced during the production-readiness pass:
--
-- 1. Search-indexer status visibility on digitised_documents
--    The semantic-search indexer runs as a BackgroundTask and silently
--    succeeds or fails. Surfacing the result on the document row lets
--    the validation panel show "indexed", "indexing failed", "stale".
--
-- 2. encounters.doctor_id (§10c tech debt #3)
--    Cross-doctor analytics needs this. Backfill from AI Scribe metadata
--    when available; nullable for legacy rows.
--
-- 3. gp_invoices.workspace_id (§10c tech debt #2)
--    Cross-tenant data leak risk if a shared report query were built.
--    Backfilled from joined patients/encounters where possible.
--
-- 4. patients.created_at index — patient registry list endpoint orders
--    by created_at DESC; index materially speeds up workspaces with
--    >1k patients.
--
-- Idempotent: safe to re-run.
-- ============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Search-indexer state on digitised_documents
-- ---------------------------------------------------------------------------
ALTER TABLE digitised_documents
    ADD COLUMN IF NOT EXISTS search_indexed_at      TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS search_index_chunks    INT,
    ADD COLUMN IF NOT EXISTS search_index_error     TEXT;

COMMENT ON COLUMN digitised_documents.search_indexed_at IS
    'When the semantic-search indexer last completed. NULL if never. '
    'Re-set on every approval (idempotent indexing).';
COMMENT ON COLUMN digitised_documents.search_index_chunks IS
    'How many chunks landed in document_embeddings on the last index run.';
COMMENT ON COLUMN digitised_documents.search_index_error IS
    'Error message from the most recent failed index run, NULL on success. '
    'Lets the validation history drawer surface silent BackgroundTasks failures.';

-- ---------------------------------------------------------------------------
-- 2. encounters.doctor_id (§10c.3)
-- ---------------------------------------------------------------------------
ALTER TABLE encounters
    ADD COLUMN IF NOT EXISTS doctor_id   TEXT,
    ADD COLUMN IF NOT EXISTS doctor_name TEXT;

COMMENT ON COLUMN encounters.doctor_id IS
    'FK to users.id (logical, not enforced because users.id may be a TEXT '
    'auth0/supabase user id). Populated from AI Scribe metadata or by the '
    'reception check-in flow. Nullable on legacy + digitisation-sourced rows.';

CREATE INDEX IF NOT EXISTS idx_encounters_doctor
    ON encounters (doctor_id, encounter_date DESC)
    WHERE doctor_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 3. gp_invoices.workspace_id (§10c.2)
-- ---------------------------------------------------------------------------
ALTER TABLE gp_invoices
    ADD COLUMN IF NOT EXISTS workspace_id TEXT;

-- Backfill from encounters where possible. Encounters always have
-- workspace_id; gp_invoices joins via encounter_id.
UPDATE gp_invoices i
   SET workspace_id = e.workspace_id
  FROM encounters e
 WHERE i.encounter_id = e.id
   AND i.workspace_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_gp_invoices_workspace
    ON gp_invoices (workspace_id, created_at DESC)
    WHERE workspace_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 4. patient registry list speed-up
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_patients_workspace_created
    ON patients (workspace_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- 5. Export-job push tracking (Phase C — auto-POST to configured FHIR endpoint)
-- ---------------------------------------------------------------------------
-- After the bundle is generated, the worker optionally pushes it to the
-- workspace's default FHIR connection. Push success/failure tracked
-- separately from bundle generation so a failed push doesn't roll back
-- the (still-downloadable) bundle.

ALTER TABLE digitisation_export_jobs
    ADD COLUMN IF NOT EXISTS push_status         TEXT,         -- not_attempted|queued|success|failed
    ADD COLUMN IF NOT EXISTS push_status_code    INT,          -- HTTP status from the FHIR server
    ADD COLUMN IF NOT EXISTS push_error          TEXT,
    ADD COLUMN IF NOT EXISTS pushed_at           TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS push_connection_id  TEXT;         -- which fhir_connection received the push

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'digitisation_export_jobs_push_status_chk'
    ) THEN
        ALTER TABLE digitisation_export_jobs
            ADD CONSTRAINT digitisation_export_jobs_push_status_chk
            CHECK (push_status IS NULL
                OR push_status IN ('not_attempted', 'queued', 'success', 'failed'));
    END IF;
END$$;

COMMIT;


-- ==============  END    migrations/012_production_readiness.sql  ==============


-- ============================================================================
-- ==============  BEGIN  migrations/013_user_workspaces.sql
-- ============================================================================

-- ============================================================================
-- Migration 013 — Multi-practice support: user_workspaces join (Tranche A)
-- ============================================================================
-- Implements TRACEABILITY §11 Tranche A.
--
-- Today every user belongs to exactly one workspace via users.workspace_id.
-- That blocks a doctor running multiple clinics from having a single login
-- that flips between practices. We add a many-to-many join table; the
-- existing users.workspace_id column is preserved as the "primary"
-- workspace (backwards compat — every existing endpoint keeps working).
--
-- Roles:
--   - owner    : tenant-level decisions (can delete the workspace)
--   - admin    : workspace admin (manage users, capabilities)
--   - clinical : doctor / clinical staff (digitisation, validation)
--   - reception: front-desk
--   - billing  : finance / claims only
--   - readonly : view-only
--
-- Idempotent: safe to re-run.
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS user_workspaces (
    user_id        TEXT        NOT NULL,
    workspace_id   TEXT        NOT NULL,
    role           TEXT        NOT NULL DEFAULT 'clinical',
    is_primary     BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    granted_by     TEXT,                 -- who added them (audit)
    PRIMARY KEY (user_id, workspace_id)
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'user_workspaces_role_chk'
    ) THEN
        ALTER TABLE user_workspaces
            ADD CONSTRAINT user_workspaces_role_chk
            CHECK (role IN ('owner', 'admin', 'clinical', 'reception',
                            'billing', 'readonly'));
    END IF;
END$$;

-- Enforce: at most ONE primary workspace per user (the one their default
-- session lands on). Other workspaces are explicit-switch.
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_workspaces_one_primary
    ON user_workspaces (user_id)
    WHERE is_primary = TRUE;

CREATE INDEX IF NOT EXISTS idx_user_workspaces_workspace
    ON user_workspaces (workspace_id);

COMMENT ON TABLE user_workspaces IS
    'Multi-practice support: a user may belong to N workspaces (TRACEABILITY '
    '§11). Backfilled from users.workspace_id on this migration; new users '
    'get one row at provisioning time. users.workspace_id is preserved as '
    'the primary-workspace pointer for backwards compat — every existing '
    'endpoint still works because the JWT keeps an active workspace_id.';

-- ----------------------------------------------------------------------------
-- Backfill from existing users.workspace_id
-- ----------------------------------------------------------------------------
-- Each existing user gets a single user_workspaces row mirroring their
-- current workspace, marked is_primary=true. ON CONFLICT DO NOTHING so
-- re-running is safe.

INSERT INTO user_workspaces (user_id, workspace_id, role, is_primary, granted_by)
SELECT u.id, u.workspace_id,
       CASE WHEN u.role = 'admin' THEN 'admin' ELSE 'clinical' END,
       TRUE,
       'migration-013'
  FROM users u
 WHERE u.workspace_id IS NOT NULL
ON CONFLICT (user_id, workspace_id) DO NOTHING;

COMMIT;


-- ==============  END    migrations/013_user_workspaces.sql  ==============


-- ============================================================================
-- ==============  BEGIN  migrations/013b_user_workspaces_uuid.sql
-- ============================================================================

-- ============================================================================
-- Migration 013b — Align user_workspaces.user_id type with users.id (UUID)
-- ============================================================================
-- Migration 013 created user_workspaces.user_id as TEXT, but users.id is UUID.
-- The backfill INSERT worked (implicit UUID → TEXT cast on assignment) but
-- JOINs fail with `operator does not exist: uuid = text`. Casting on every
-- query is ugly; fixing the column type once is cleaner.
--
-- The existing values are valid UUID strings (canonical format), so
-- ALTER COLUMN ... TYPE UUID USING user_id::uuid converts in place with
-- no data loss.
--
-- Idempotent: safe to re-run.
-- ============================================================================

BEGIN;

DO $$
DECLARE
    cur_type TEXT;
BEGIN
    SELECT data_type INTO cur_type
      FROM information_schema.columns
     WHERE table_schema = 'public'
       AND table_name = 'user_workspaces'
       AND column_name = 'user_id';
    IF cur_type = 'text' THEN
        ALTER TABLE user_workspaces
            ALTER COLUMN user_id TYPE UUID USING user_id::uuid;
        RAISE NOTICE 'Converted user_workspaces.user_id text → uuid';
    ELSE
        RAISE NOTICE 'user_workspaces.user_id already %, skipping', cur_type;
    END IF;
END$$;

COMMIT;


-- ==============  END    migrations/013b_user_workspaces_uuid.sql  ==============


-- ============================================================================
-- ==============  BEGIN  migrations/014_action_audit_log.sql
-- ============================================================================

-- ============================================================================
-- Migration 014 — Action audit log
-- ============================================================================
--
-- The ActionExecutor writes one row here per mutation it processes (real,
-- dry-run, or reversed). This table is the regulatory-grade audit surface
-- the platform's "audit-ready by default" claim leans on.
--
-- Why a new table and not an extension of validation_edit_log?
--
--   validation_edit_log (migration 005) is document-scoped: its action CHECK
--   constraint enumerates ('edit', 'accept', 'approve', 'reject',
--   'reprocess'), its field_path semantics are field-level, and it has no
--   concept of affected_objects across the graph. The audit-trail UI in
--   Phase 4 will want "show me every action that touched patient X" — a
--   query that table's schema cannot answer without joins it isn't indexed
--   for. The two tables overlap for one PR cycle (PR 1 double-writes,
--   PR 2 removes the legacy write).
--
-- affected_objects is structured JSONB, not TEXT[]
--
--   Each entry is {type, id, op} where op is created|updated|soft_deleted|
--   linked. The Phase 4 UI renders WHAT happened to each object — type-
--   prefixed strings ('patient_<uuid>') can't carry the op dimension; bare
--   UUIDs need joins to recover the type. The slightly more complex GIN
--   (jsonb_path_ops) index pays for the audit log becoming a *story*, not
--   a *list*.
--
--   Containment query example:
--     SELECT * FROM action_audit_log
--      WHERE affected_objects @> '[{"type": "Patient", "id": "<uuid>"}]'
--      ORDER BY started_at DESC;
--
-- Append-only by convention
--
--   The reverses_audit_id / reversed_by_audit_id pointers let us link
--   forward and backward without UPDATEing the original row in normal
--   flow. Reversal of action X writes a new row Y with Y.reverses_audit_id
--   = X.id, AND updates X.reversed_by_audit_id = Y.id (one targeted
--   UPDATE via the executor; not a free-form mutation).
--
-- Idempotent: safe to re-run.
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS action_audit_log (
    id                     UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    action_name            TEXT         NOT NULL,
    action_version         INT          NOT NULL DEFAULT 1,
    actor_user_id          TEXT         NOT NULL,
    actor_email            TEXT,
    practice_id            TEXT         NOT NULL,
    workspace_id           TEXT         NOT NULL,
    idempotency_key        TEXT,
    dry_run                BOOLEAN      NOT NULL DEFAULT FALSE,
    parameters             JSONB        NOT NULL,
    preconditions_checked  JSONB        NOT NULL,   -- [{name, passed, detail}]
    effects_applied        JSONB        NOT NULL,   -- [{name, descriptor, result}]
    affected_objects       JSONB        NOT NULL DEFAULT '[]',
                                                    -- [{type, id, op}]
    outcome                TEXT         NOT NULL CHECK (outcome IN (
                                            'success',
                                            'precondition_failed',
                                            'effect_failed',
                                            'reversed',
                                            'dry_run'
                                        )),
    error_detail           JSONB,                   -- ErrorDetail(code, message, context)
    reverses_audit_id      UUID         REFERENCES action_audit_log(id),
    reversed_by_audit_id   UUID         REFERENCES action_audit_log(id),
    started_at             TIMESTAMPTZ  NOT NULL DEFAULT now(),
    finished_at            TIMESTAMPTZ,
    duration_ms            INT
);

-- "every action of type X across all practices, most recent first"
CREATE INDEX IF NOT EXISTS idx_action_audit_log_action_started
    ON action_audit_log (action_name, started_at DESC);

-- "every action in this practice, most recent first" — practice timeline view
CREATE INDEX IF NOT EXISTS idx_action_audit_log_practice_started
    ON action_audit_log (practice_id, started_at DESC);

-- "every action this user ever did" — for individual-actor audit trails
CREATE INDEX IF NOT EXISTS idx_action_audit_log_actor_started
    ON action_audit_log (actor_user_id, started_at DESC);

-- "every action that touched patient/document/consultation X" — Phase 4 UI
CREATE INDEX IF NOT EXISTS idx_action_audit_log_affected_objects
    ON action_audit_log USING gin (affected_objects jsonb_path_ops);

-- Idempotency: same key + same action = same audit row (real writes only).
-- Dry-runs are intentionally outside this constraint so previews are repeatable.
CREATE UNIQUE INDEX IF NOT EXISTS idx_action_audit_log_idempotency
    ON action_audit_log (action_name, idempotency_key)
    WHERE idempotency_key IS NOT NULL AND dry_run = FALSE;

-- Find all reversals of a given action
CREATE INDEX IF NOT EXISTS idx_action_audit_log_reverses
    ON action_audit_log (reverses_audit_id)
    WHERE reverses_audit_id IS NOT NULL;

COMMENT ON TABLE action_audit_log IS
    'One row per ActionExecutor invocation (real or dry-run). Append-only; '
    'reversals add a new row pointing at reverses_audit_id and the executor '
    'updates the original row''s reversed_by_audit_id (one targeted UPDATE).';

-- ----------------------------------------------------------------------------
-- Advisory lock RPC
-- ----------------------------------------------------------------------------
-- Callable from Python via supabase.rpc('action_try_advisory_lock', ...).
-- Uses pg_try_advisory_xact_lock — transaction-scoped. The lock is held only
-- for the duration of the RPC call, then released automatically.
--
-- The plan calls for verifying empirically (Phase 0) whether session-scoped
-- advisory locks (pg_try_advisory_lock + pg_advisory_unlock) are visible
-- across Supabase's HTTP-pooled requests. This RPC supports the verification
-- by acquiring a session-scoped lock and returning whether it succeeded; the
-- companion unlock RPC releases it.
--
-- See backend/tests/test_advisory_lock_semantics.py for the verification.
-- ----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION action_try_advisory_lock(
    p_action_name  TEXT,
    p_resource_key TEXT
) RETURNS BOOLEAN LANGUAGE sql AS $$
    -- Session-scoped lock. Must be released via action_advisory_unlock.
    SELECT pg_try_advisory_lock(
        hashtextextended(p_action_name || '|' || p_resource_key, 0)
    );
$$;

CREATE OR REPLACE FUNCTION action_advisory_unlock(
    p_action_name  TEXT,
    p_resource_key TEXT
) RETURNS BOOLEAN LANGUAGE sql AS $$
    SELECT pg_advisory_unlock(
        hashtextextended(p_action_name || '|' || p_resource_key, 0)
    );
$$;

COMMIT;


-- ==============  END    migrations/014_action_audit_log.sql  ==============


-- ============================================================================
-- ==============  BEGIN  migrations/015_extraction_promoter_plpgsql.sql
-- ============================================================================

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


-- ==============  END    migrations/015_extraction_promoter_plpgsql.sql  ==============


-- ============================================================================
-- ==============  BEGIN  migrations/016_extraction_promoter_seed_abbrevs.sql
-- ============================================================================

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


-- ==============  END    migrations/016_extraction_promoter_seed_abbrevs.sql  ==============


-- ============================================================================
-- ==============  BEGIN  migrations/017_drop_legacy_lock_helpers.sql
-- ============================================================================

-- ============================================================================
-- Migration 017 — Drop legacy advisory-lock helpers from migration 014
-- ============================================================================
--
-- ORDERING — RUN STRICTLY AFTER:
--
--   1. Migration 015 (introduces execute_action_promote_document with
--      SELECT...FOR UPDATE NOWAIT — the replacement for advisory locks)
--   2. Migration 016 (idempotent data seed, no dependency either way)
--   3. PR 2 application code deploy (executor.py without _acquire_lock,
--      primitives.py with the RPC-dispatch apply())
--
-- Reason for the ordering: dropping the advisory-lock helpers before
-- the application code stops calling them would crash any in-flight
-- promote. The helpers are NO-OPed at the Python layer in PR 1 (no real
-- mutual exclusion is delivered — see Phase 0 outcome in executor.py),
-- but Migration 014 still defines them in the database. After PR 2's
-- code lands, no caller invokes them anymore. This migration removes
-- the dead RPCs.
--
-- Confirm before applying:
--   - `git log --oneline backend/app/actions/executor.py` shows the
--     PR 2 commit that deletes _acquire_lock().
--   - `grep -rn "action_try_advisory_lock\|action_advisory_unlock"
--      backend/app backend/scripts` returns no matches (test file
--      reference in test_advisory_lock_semantics.py is allowed — that
--      test is the Phase 0 verification, marked slow_integration, runs
--      only against the OLD schema before 017 applies).
--
-- This migration is destructive. The advisory-lock RPCs are not in use
-- elsewhere in the codebase (verified via grep), and Phase 0 confirmed
-- they don't deliver the mutual-exclusion property anyway, so the drop
-- is risk-free in practice.
--
-- Idempotent: DROP FUNCTION IF EXISTS.
-- ============================================================================

BEGIN;

DROP FUNCTION IF EXISTS action_try_advisory_lock(TEXT, TEXT);
DROP FUNCTION IF EXISTS action_advisory_unlock(TEXT, TEXT);

COMMIT;


-- ==============  END    migrations/017_drop_legacy_lock_helpers.sql  ==============


-- ============================================================================
-- ==============  BEGIN  migrations/018_enable_rls_tenant_tables.sql
-- ============================================================================

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


-- ==============  END    migrations/018_enable_rls_tenant_tables.sql  ==============


-- ============================================================================
-- ==============  BEGIN  migrations/019_drop_validation_edit_log.sql
-- ============================================================================

-- ============================================================================
-- Migration 019 — Drop validation_edit_log (PR 3, LAST migration in the PR)
-- ============================================================================
--
-- This migration MUST run last in the PR 3 sequence, after:
--
--   1. Migration 020 (schema additions for patients + prescriptions)
--   2. Migration 021 (ReassignDocument RPCs)
--   3. Migration 022 (MergePatient RPCs)
--   4. Migration 023 (capabilities seed)
--   5. APPLICATION CODE DEPLOY — every _write_edit_log caller is gone;
--      reject/save/reprocess endpoints route through the ActionExecutor;
--      action_audit_log is the single source of truth for all
--      validation-queue mutations.
--
-- Confirm before applying:
--
--   grep -rn "_write_edit_log\|validation_edit_log\.insert\|validation_edit_log\.update" \
--       backend --include="*.py" | grep -v __pycache__
--
--   Must return zero matches. If anything still writes to the table,
--   that data is lost when this migration runs.
--
-- WHAT BREAKS (briefly, until PR 4)
--
--   The `/digitisation/validation/{document_id}/history` endpoint
--   (digitisation.py:670) currently reads from validation_edit_log.
--   Post-migration it returns `history: []` with a deprecation log
--   message. PR 4's audit-trail UI rewires it to query action_audit_log
--   filtered by `affected_objects @> [{type:"Document", id:doc_id}]`.
--
--   This is a temporary regression accepted with the user; the data is
--   not lost — it's all in action_audit_log; only the legacy read path
--   is empty for one PR cycle.
--
-- DESTRUCTIVE — drops the table. Idempotent in that DROP TABLE IF EXISTS
-- is a no-op if the table is already gone.
-- ============================================================================

BEGIN;

-- Indexes are dropped automatically with the table; named here for clarity.
DROP INDEX IF EXISTS idx_validation_edit_log_document;
DROP INDEX IF EXISTS idx_validation_edit_log_session;
DROP INDEX IF EXISTS idx_validation_edit_log_workspace;
DROP INDEX IF EXISTS idx_validation_edit_log_user;

DROP TABLE IF EXISTS validation_edit_log;

COMMIT;


-- ==============  END    migrations/019_drop_validation_edit_log.sql  ==============


-- ============================================================================
-- ==============  BEGIN  migrations/020_patient_soft_delete_columns.sql
-- ============================================================================

-- ============================================================================
-- Migration 020 — Schema additions for PR 3 actions (patients + prescriptions)
-- ============================================================================
--
-- Three new Actions in PR 3 need columns this migration adds:
--
--   SoftDeletePatient (POPIA right-to-erasure, reversible):
--     - patients.deleted_at  TIMESTAMPTZ
--     - patients.deletion_reason TEXT
--
--   MergePatient (consolidate duplicate records into one):
--     - patients.merged_into_patient_id  TEXT REFERENCES patients(id)
--
--   VoidPrescription (soft-cancel an active prescription, reversible):
--     - prescriptions.void_reason TEXT
--
-- Soft-delete is reversible by design — POPIA permits erasure, but a
-- mistakenly-deleted patient must be restorable within a retention
-- window. The `deleted_at` column is the soft-flag; reversal sets it
-- back to NULL.
--
-- Merge re-points every child row (encounters, prescriptions, etc.)
-- from a source patient to a target patient, then soft-deletes the
-- source with `merged_into_patient_id` pointing at the survivor. A
-- regulator asking "where did this patient go?" gets a clean trail.
--
-- IDEMPOTENT — safe to re-run. All ADD COLUMN clauses use IF NOT EXISTS.
--
-- Indexes:
--   idx_patients_active — the canonical hot-path filter; every patient-
--     facing query gets a `WHERE deleted_at IS NULL` clause AFTER PR 3
--     code lands. The partial index keeps the scan cheap.
--   idx_patients_merged_into — for "show me every patient consolidated
--     into this survivor" admin queries.
--
-- ORDERING NOTE: ships FIRST in the PR 3 migration sequence (before 021
-- and 022) because both ReassignDocument and MergePatient rely on these
-- columns. Application code that queries patients without filtering on
-- deleted_at IS NULL keeps working until the per-query sweep lands in
-- the SAME PR — the column defaults to NULL, so existing rows are still
-- visible to queries that don't filter.
-- ============================================================================

BEGIN;

ALTER TABLE patients
    ADD COLUMN IF NOT EXISTS deleted_at              TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS deletion_reason         TEXT,
    ADD COLUMN IF NOT EXISTS merged_into_patient_id  TEXT REFERENCES patients(id);

-- Partial index for the canonical "active patients" filter — every
-- per-workspace patient-list query will use this once code-side filters
-- are added.
CREATE INDEX IF NOT EXISTS idx_patients_active
    ON patients (workspace_id)
    WHERE deleted_at IS NULL;

-- For admin queries: "show all patients that were consolidated into X"
CREATE INDEX IF NOT EXISTS idx_patients_merged_into
    ON patients (merged_into_patient_id)
    WHERE merged_into_patient_id IS NOT NULL;

COMMENT ON COLUMN patients.deleted_at IS
    'Soft-delete flag for POPIA right-to-erasure. NULL = active. '
    'Set by the SoftDeletePatient or MergePatient action. Reversible '
    'via executor.reverse() within the retention window (no retention '
    'job exists yet — see PR 4 roadmap).';

COMMENT ON COLUMN patients.merged_into_patient_id IS
    'When a patient is merged into another, this points at the survivor. '
    'Set by MergePatient on the source-patient row; the target row is '
    'untouched. Reversed by reverse_action_merge_patient.';


-- ----------------------------------------------------------------------------
-- prescriptions.void_reason — for VoidPrescription action
-- ----------------------------------------------------------------------------
--
-- A reason string captured at void time. Queryable column (rather than
-- stuffing it into notes) so admin dashboards can answer "why did we
-- void this prescription class?" without parsing free text.
--
-- Reversal does NOT clear the column on its own — the audit row's
-- parameters carry previous_status; void_reason is informational, not
-- a load-bearing state-restoration field.
-- ----------------------------------------------------------------------------

ALTER TABLE prescriptions
    ADD COLUMN IF NOT EXISTS void_reason TEXT;

COMMENT ON COLUMN prescriptions.void_reason IS
    'Reason captured when the VoidPrescription action soft-cancels a '
    'prescription. NULL for prescriptions that have never been voided. '
    'Survives reversal (the audit row carries the load-bearing state).';

COMMIT;


-- ==============  END    migrations/020_patient_soft_delete_columns.sql  ==============


-- ============================================================================
-- ==============  BEGIN  migrations/021_reassign_document_plpgsql.sql
-- ============================================================================

-- ============================================================================
-- Migration 021 — Reassign-document RPCs (PR 3)
-- ============================================================================
--
-- ReassignDocument re-points a single document's structured data from
-- one patient to another. Used when a document was incorrectly linked
-- (e.g. a reviewer approved into the wrong patient and only noticed
-- after promote). The whole sweep runs in one transaction with
-- SELECT...FOR UPDATE NOWAIT on the digitised_documents row, matching
-- the mutual-exclusion semantics PR 2 established.
--
-- TABLES TOUCHED
--
--   digitised_documents:  UPDATE patient_id = new WHERE id = doc_id
--   encounters:           UPDATE patient_id = new WHERE source_document_id = doc_id
--   diagnoses:            same
--   vitals:               same
--   allergies:            same
--   prescriptions:        same
--   prescription_items:   NOT TOUCHED (no patient_id column; reaches the
--                         patient transitively via prescription)
--
-- AFFECTED OBJECTS
--
--   Every re-pointed row appends to affected_objects with op='updated'
--   and a `previous_patient_id` field so reversal can restore.
--   The Document entry carries the document's own previous_patient_id.
--
-- REVERSAL
--
--   reverse_action_reassign_document iterates affected_objects, restores
--   each row's patient_id to its `previous_patient_id`, writes the new
--   reversal audit row, updates the original audit row's
--   reversed_by_audit_id. Same atomicity envelope as migration 015's
--   reverse RPC.
--
-- IDEMPOTENT — safe to re-run.
-- ============================================================================

BEGIN;

CREATE OR REPLACE FUNCTION execute_action_reassign_document(
    p_document_id        TEXT,
    p_workspace_id       TEXT,
    p_new_patient_id     TEXT,
    p_reason             TEXT,
    p_created_by         TEXT
) RETURNS JSONB
LANGUAGE plpgsql AS $$
DECLARE
    v_locked_id          TEXT;
    v_prev_patient_id    TEXT;
    v_affected           JSONB := '[]'::JSONB;
    v_count_enc          INT := 0;
    v_count_diag         INT := 0;
    v_count_vital        INT := 0;
    v_count_allergy      INT := 0;
    v_count_rx           INT := 0;
    v_row                RECORD;
BEGIN
    SET LOCAL statement_timeout = '15s';

    -- ------------------------------------------------------------------------
    -- 1. Lock the document row. FOR UPDATE NOWAIT raises 55P03 if another
    -- transaction holds it; Python maps to ErrorDetail(code='action_locked').
    -- ------------------------------------------------------------------------
    SELECT id, patient_id
      INTO v_locked_id, v_prev_patient_id
      FROM digitised_documents
     WHERE id = p_document_id
       AND workspace_id = p_workspace_id
     FOR UPDATE NOWAIT;

    IF v_locked_id IS NULL THEN
        RAISE EXCEPTION 'digitised_documents row not found: %', p_document_id
            USING ERRCODE = 'P0001', HINT = 'not_found';
    END IF;

    -- ------------------------------------------------------------------------
    -- 2. Verify the new patient exists in the same workspace + not soft-deleted.
    --    (Python preconditions also check these; this is the
    --    inside-transaction safety net.)
    -- ------------------------------------------------------------------------
    PERFORM 1 FROM patients
     WHERE id = p_new_patient_id
       AND workspace_id = p_workspace_id
       AND deleted_at IS NULL;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'target patient % not found / soft-deleted / wrong workspace',
                        p_new_patient_id
            USING ERRCODE = 'P0001', HINT = 'invariant_violated';
    END IF;

    -- ------------------------------------------------------------------------
    -- 3. Iterate each child table; for each row attached to this document
    --    via source_document_id, capture {id, previous_patient_id} in
    --    affected_objects then re-point patient_id.
    -- ------------------------------------------------------------------------

    -- Encounters
    FOR v_row IN
        SELECT id, patient_id
          FROM encounters
         WHERE source_document_id = p_document_id
    LOOP
        v_affected := v_affected || jsonb_build_array(jsonb_build_object(
            'type', 'Consultation',
            'id', v_row.id::TEXT,
            'op', 'updated',
            'previous_patient_id', v_row.patient_id
        ));
        v_count_enc := v_count_enc + 1;
    END LOOP;
    UPDATE encounters
       SET patient_id = p_new_patient_id
     WHERE source_document_id = p_document_id;

    -- Diagnoses
    FOR v_row IN
        SELECT id, patient_id
          FROM diagnoses
         WHERE source_document_id = p_document_id
    LOOP
        v_affected := v_affected || jsonb_build_array(jsonb_build_object(
            'type', 'Diagnosis',
            'id', v_row.id::TEXT,
            'op', 'updated',
            'previous_patient_id', v_row.patient_id
        ));
        v_count_diag := v_count_diag + 1;
    END LOOP;
    UPDATE diagnoses
       SET patient_id = p_new_patient_id
     WHERE source_document_id = p_document_id;

    -- Vitals
    FOR v_row IN
        SELECT id, patient_id
          FROM vitals
         WHERE source_document_id = p_document_id
    LOOP
        v_affected := v_affected || jsonb_build_array(jsonb_build_object(
            'type', 'Vital',
            'id', v_row.id::TEXT,
            'op', 'updated',
            'previous_patient_id', v_row.patient_id
        ));
        v_count_vital := v_count_vital + 1;
    END LOOP;
    UPDATE vitals
       SET patient_id = p_new_patient_id
     WHERE source_document_id = p_document_id;

    -- Allergies
    FOR v_row IN
        SELECT id, patient_id
          FROM allergies
         WHERE source_document_id = p_document_id
    LOOP
        v_affected := v_affected || jsonb_build_array(jsonb_build_object(
            'type', 'Allergy',
            'id', v_row.id::TEXT,
            'op', 'updated',
            'previous_patient_id', v_row.patient_id
        ));
        v_count_allergy := v_count_allergy + 1;
    END LOOP;
    UPDATE allergies
       SET patient_id = p_new_patient_id
     WHERE source_document_id = p_document_id;

    -- Prescriptions
    FOR v_row IN
        SELECT id, patient_id
          FROM prescriptions
         WHERE source_document_id = p_document_id
    LOOP
        v_affected := v_affected || jsonb_build_array(jsonb_build_object(
            'type', 'Prescription',
            'id', v_row.id,
            'op', 'updated',
            'previous_patient_id', v_row.patient_id
        ));
        v_count_rx := v_count_rx + 1;
    END LOOP;
    UPDATE prescriptions
       SET patient_id = p_new_patient_id
     WHERE source_document_id = p_document_id;

    -- The document itself
    UPDATE digitised_documents
       SET patient_id = p_new_patient_id,
           updated_at = now()
     WHERE id = p_document_id;

    v_affected := v_affected || jsonb_build_array(jsonb_build_object(
        'type', 'Document',
        'id', p_document_id,
        'op', 'updated',
        'previous_patient_id', v_prev_patient_id
    ));

    RETURN jsonb_build_object(
        'document_id',         p_document_id,
        'new_patient_id',      p_new_patient_id,
        'previous_patient_id', v_prev_patient_id,
        'counts', jsonb_build_object(
            'encounters',    v_count_enc,
            'diagnoses',     v_count_diag,
            'vitals',        v_count_vital,
            'allergies',     v_count_allergy,
            'prescriptions', v_count_rx
        ),
        'affected_objects', v_affected
    );
END;
$$;

COMMENT ON FUNCTION execute_action_reassign_document(TEXT, TEXT, TEXT, TEXT, TEXT) IS
    'PR 3: re-point all rows linked to a document from one patient to '
    'another, in one transaction with FOR UPDATE NOWAIT on the document. '
    'Returns affected_objects with previous_patient_id for reversal.';


-- ============================================================================
-- reverse_action_reassign_document
-- ============================================================================

CREATE OR REPLACE FUNCTION reverse_action_reassign_document(
    p_audit_id        UUID,
    p_actor_user_id   TEXT,
    p_reason          TEXT DEFAULT NULL
) RETURNS JSONB
LANGUAGE plpgsql AS $$
DECLARE
    v_audit              action_audit_log%ROWTYPE;
    v_affected           JSONB;
    v_entry              JSONB;
    v_new_audit_id       UUID;
    v_reverse_affected   JSONB := '[]'::JSONB;
    v_started_at         TIMESTAMPTZ;
    v_finished_at        TIMESTAMPTZ;
    v_restored           INT := 0;
BEGIN
    SET LOCAL statement_timeout = '15s';
    v_started_at := now();

    -- Load + lock the original audit row.
    SELECT * INTO v_audit
      FROM action_audit_log
     WHERE id = p_audit_id
     FOR UPDATE NOWAIT;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'action_audit_log row not found: %', p_audit_id
            USING ERRCODE = 'P0001', HINT = 'not_found';
    END IF;
    IF v_audit.dry_run THEN
        RAISE EXCEPTION 'cannot reverse dry-run row %', p_audit_id
            USING ERRCODE = 'P0001', HINT = 'cannot_reverse_dry_run';
    END IF;
    IF v_audit.reversed_by_audit_id IS NOT NULL THEN
        RAISE EXCEPTION 'audit row % already reversed', p_audit_id
            USING ERRCODE = 'P0001', HINT = 'precondition_failed';
    END IF;
    IF v_audit.action_name <> 'ReassignDocument' THEN
        RAISE EXCEPTION 'reverse_action_reassign_document called on action %',
                        v_audit.action_name
            USING ERRCODE = 'P0001', HINT = 'invariant_violated';
    END IF;

    v_affected := COALESCE(v_audit.affected_objects, '[]'::JSONB);

    -- Restore patient_id on every affected row.
    FOR v_entry IN SELECT * FROM jsonb_array_elements(v_affected) LOOP
        DECLARE
            v_type TEXT := v_entry ->> 'type';
            v_id   TEXT := v_entry ->> 'id';
            v_prev TEXT := v_entry ->> 'previous_patient_id';
        BEGIN
            IF v_type = 'Consultation' THEN
                UPDATE encounters SET patient_id = v_prev WHERE id = v_id;
            ELSIF v_type = 'Diagnosis' THEN
                UPDATE diagnoses SET patient_id = v_prev WHERE id = v_id::UUID;
            ELSIF v_type = 'Vital' THEN
                UPDATE vitals SET patient_id = v_prev WHERE id = v_id::UUID;
            ELSIF v_type = 'Allergy' THEN
                UPDATE allergies SET patient_id = v_prev WHERE id = v_id::UUID;
            ELSIF v_type = 'Prescription' THEN
                UPDATE prescriptions SET patient_id = v_prev WHERE id = v_id;
            ELSIF v_type = 'Document' THEN
                UPDATE digitised_documents
                   SET patient_id = v_prev, updated_at = now()
                 WHERE id = v_id;
            END IF;
            v_restored := v_restored + 1;
            v_reverse_affected := v_reverse_affected || jsonb_build_array(jsonb_build_object(
                'type', v_type,
                'id', v_id,
                'op', 'reversed_update',
                'restored_patient_id', v_prev
            ));
        END;
    END LOOP;

    v_new_audit_id := gen_random_uuid();
    v_finished_at := now();

    INSERT INTO action_audit_log (
        id, action_name, action_version, actor_user_id, actor_email,
        practice_id, workspace_id, idempotency_key, dry_run,
        parameters, preconditions_checked, effects_applied,
        affected_objects, outcome, error_detail,
        reverses_audit_id, reversed_by_audit_id,
        started_at, finished_at, duration_ms
    ) VALUES (
        v_new_audit_id, 'ReverseActionReassignDocument', 1,
        p_actor_user_id, NULL,
        v_audit.practice_id, v_audit.workspace_id, NULL, FALSE,
        jsonb_build_object('reverses_audit_id', p_audit_id::TEXT, 'reason', p_reason),
        '[]'::JSONB, '[]'::JSONB,
        v_reverse_affected, 'reversed', NULL,
        p_audit_id, NULL,
        v_started_at, v_finished_at,
        EXTRACT(MILLISECONDS FROM (v_finished_at - v_started_at))::INT
    );

    UPDATE action_audit_log SET reversed_by_audit_id = v_new_audit_id
     WHERE id = p_audit_id;

    RETURN jsonb_build_object(
        'audit_id',         v_new_audit_id,
        'reverses_audit_id', p_audit_id,
        'outcome',          'reversed',
        'restored_count',   v_restored,
        'affected_objects', v_reverse_affected
    );
END;
$$;

COMMENT ON FUNCTION reverse_action_reassign_document(UUID, TEXT, TEXT) IS
    'PR 3: undo a ReassignDocument by restoring each affected row''s '
    'patient_id from the audit row''s previous_patient_id field.';

COMMIT;


-- ==============  END    migrations/021_reassign_document_plpgsql.sql  ==============


-- ============================================================================
-- ==============  BEGIN  migrations/022_merge_patient_plpgsql.sql
-- ============================================================================

-- ============================================================================
-- Migration 022 — Merge-patient RPCs (PR 3)
-- ============================================================================
--
-- MergePatient consolidates two patient records into one. Every child
-- row carrying patient_id = source is re-pointed to target. The source
-- patient is then soft-deleted with `merged_into_patient_id = target`
-- so the audit trail makes the consolidation explicit and a future
-- "show me every patient consolidated into X" query is cheap.
--
-- HIGHEST-BLAST-RADIUS ACTION IN THE SYSTEM. Re-points across 10 child
-- tables in one transaction. Mutual exclusion via FOR UPDATE NOWAIT on
-- BOTH patient rows; locking ordered by id to avoid deadlock with a
-- concurrent reverse-direction merge.
--
-- TABLES TOUCHED (10 + patients itself)
--
--   encounters, diagnoses, vitals, allergies, prescriptions,
--   document_refs, digitised_documents, sick_notes, referrals,
--   clinical_notes
--
-- CRITICAL: this list MUST be kept in sync with the schema. If a future
-- migration adds a new table with patient_id, MergePatient leaves rows
-- in that table pointing at the soft-deleted source patient. A CI test
-- (TODO post-PR 3) will introspect pg_constraint for every FK to
-- patients(id) and assert every referenced table appears here.
--
-- REVERSAL
--
--   reverse_action_merge_patient reads affected_objects (each entry
--   carries previous_patient_id), restores each row's patient_id,
--   clears the source patient's deleted_at + merged_into_patient_id,
--   writes the new reversal audit row, updates the original's
--   reversed_by_audit_id. All atomic.
--
-- IDEMPOTENT — safe to re-run.
-- ============================================================================

BEGIN;

CREATE OR REPLACE FUNCTION execute_action_merge_patient(
    p_source_patient_id  TEXT,
    p_target_patient_id  TEXT,
    p_workspace_id       TEXT,
    p_merge_reason       TEXT,
    p_created_by         TEXT
) RETURNS JSONB
LANGUAGE plpgsql AS $$
DECLARE
    v_first_lock  TEXT;
    v_second_lock TEXT;
    v_source_row  RECORD;
    v_target_row  RECORD;
    v_affected    JSONB := '[]'::JSONB;
    v_counts      JSONB := '{}'::JSONB;
    v_count_enc          INT := 0;
    v_count_diag         INT := 0;
    v_count_vital        INT := 0;
    v_count_allergy      INT := 0;
    v_count_rx           INT := 0;
    v_count_docref       INT := 0;
    v_count_digidoc      INT := 0;
    v_count_sicknote     INT := 0;
    v_count_referral     INT := 0;
    v_count_clinnote     INT := 0;
    v_row                RECORD;
BEGIN
    SET LOCAL statement_timeout = '30s';

    -- Reject same-row merge.
    IF p_source_patient_id = p_target_patient_id THEN
        RAISE EXCEPTION 'cannot merge patient % into itself', p_source_patient_id
            USING ERRCODE = 'P0001', HINT = 'invariant_violated';
    END IF;

    -- ------------------------------------------------------------------------
    -- Acquire locks in deterministic order (lower id first). Avoids
    -- deadlock with a reverse-direction concurrent merge (B → A while
    -- this one does A → B).
    -- ------------------------------------------------------------------------
    IF p_source_patient_id < p_target_patient_id THEN
        v_first_lock := p_source_patient_id;
        v_second_lock := p_target_patient_id;
    ELSE
        v_first_lock := p_target_patient_id;
        v_second_lock := p_source_patient_id;
    END IF;

    PERFORM 1 FROM patients
     WHERE id = v_first_lock AND workspace_id = p_workspace_id
     FOR UPDATE NOWAIT;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'patient % not found in workspace %', v_first_lock, p_workspace_id
            USING ERRCODE = 'P0001', HINT = 'not_found';
    END IF;
    PERFORM 1 FROM patients
     WHERE id = v_second_lock AND workspace_id = p_workspace_id
     FOR UPDATE NOWAIT;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'patient % not found in workspace %', v_second_lock, p_workspace_id
            USING ERRCODE = 'P0001', HINT = 'not_found';
    END IF;

    -- ------------------------------------------------------------------------
    -- Sanity: source must not already be soft-deleted; target must not
    -- be soft-deleted; neither must already be merged.
    -- ------------------------------------------------------------------------
    SELECT * INTO v_source_row FROM patients
     WHERE id = p_source_patient_id AND workspace_id = p_workspace_id;
    SELECT * INTO v_target_row FROM patients
     WHERE id = p_target_patient_id AND workspace_id = p_workspace_id;

    IF v_source_row.deleted_at IS NOT NULL THEN
        RAISE EXCEPTION 'source patient % is already soft-deleted', p_source_patient_id
            USING ERRCODE = 'P0001', HINT = 'precondition_failed';
    END IF;
    IF v_target_row.deleted_at IS NOT NULL THEN
        RAISE EXCEPTION 'target patient % is soft-deleted', p_target_patient_id
            USING ERRCODE = 'P0001', HINT = 'precondition_failed';
    END IF;

    -- ------------------------------------------------------------------------
    -- Per-table re-point. Each block: SELECT to capture affected_objects,
    -- then UPDATE. Same pattern for all 10 tables.
    -- ------------------------------------------------------------------------

    -- encounters
    FOR v_row IN SELECT id FROM encounters WHERE patient_id = p_source_patient_id LOOP
        v_affected := v_affected || jsonb_build_array(jsonb_build_object(
            'type', 'Consultation', 'id', v_row.id::TEXT, 'op', 'updated',
            'previous_patient_id', p_source_patient_id));
        v_count_enc := v_count_enc + 1;
    END LOOP;
    UPDATE encounters SET patient_id = p_target_patient_id
     WHERE patient_id = p_source_patient_id;

    -- diagnoses
    FOR v_row IN SELECT id FROM diagnoses WHERE patient_id = p_source_patient_id LOOP
        v_affected := v_affected || jsonb_build_array(jsonb_build_object(
            'type', 'Diagnosis', 'id', v_row.id::TEXT, 'op', 'updated',
            'previous_patient_id', p_source_patient_id));
        v_count_diag := v_count_diag + 1;
    END LOOP;
    UPDATE diagnoses SET patient_id = p_target_patient_id
     WHERE patient_id = p_source_patient_id;

    -- vitals
    FOR v_row IN SELECT id FROM vitals WHERE patient_id = p_source_patient_id LOOP
        v_affected := v_affected || jsonb_build_array(jsonb_build_object(
            'type', 'Vital', 'id', v_row.id::TEXT, 'op', 'updated',
            'previous_patient_id', p_source_patient_id));
        v_count_vital := v_count_vital + 1;
    END LOOP;
    UPDATE vitals SET patient_id = p_target_patient_id
     WHERE patient_id = p_source_patient_id;

    -- allergies
    FOR v_row IN SELECT id FROM allergies WHERE patient_id = p_source_patient_id LOOP
        v_affected := v_affected || jsonb_build_array(jsonb_build_object(
            'type', 'Allergy', 'id', v_row.id::TEXT, 'op', 'updated',
            'previous_patient_id', p_source_patient_id));
        v_count_allergy := v_count_allergy + 1;
    END LOOP;
    UPDATE allergies SET patient_id = p_target_patient_id
     WHERE patient_id = p_source_patient_id;

    -- prescriptions
    FOR v_row IN SELECT id FROM prescriptions WHERE patient_id = p_source_patient_id LOOP
        v_affected := v_affected || jsonb_build_array(jsonb_build_object(
            'type', 'Prescription', 'id', v_row.id, 'op', 'updated',
            'previous_patient_id', p_source_patient_id));
        v_count_rx := v_count_rx + 1;
    END LOOP;
    UPDATE prescriptions SET patient_id = p_target_patient_id
     WHERE patient_id = p_source_patient_id;

    -- document_refs
    FOR v_row IN SELECT id FROM document_refs WHERE patient_id = p_source_patient_id LOOP
        v_affected := v_affected || jsonb_build_array(jsonb_build_object(
            'type', 'DocumentRef', 'id', v_row.id, 'op', 'updated',
            'previous_patient_id', p_source_patient_id));
        v_count_docref := v_count_docref + 1;
    END LOOP;
    UPDATE document_refs SET patient_id = p_target_patient_id
     WHERE patient_id = p_source_patient_id;

    -- digitised_documents
    FOR v_row IN SELECT id FROM digitised_documents WHERE patient_id = p_source_patient_id LOOP
        v_affected := v_affected || jsonb_build_array(jsonb_build_object(
            'type', 'Document', 'id', v_row.id, 'op', 'updated',
            'previous_patient_id', p_source_patient_id));
        v_count_digidoc := v_count_digidoc + 1;
    END LOOP;
    UPDATE digitised_documents SET patient_id = p_target_patient_id
     WHERE patient_id = p_source_patient_id;

    -- sick_notes
    FOR v_row IN SELECT id FROM sick_notes WHERE patient_id = p_source_patient_id LOOP
        v_affected := v_affected || jsonb_build_array(jsonb_build_object(
            'type', 'SickNote', 'id', v_row.id::TEXT, 'op', 'updated',
            'previous_patient_id', p_source_patient_id));
        v_count_sicknote := v_count_sicknote + 1;
    END LOOP;
    UPDATE sick_notes SET patient_id = p_target_patient_id
     WHERE patient_id = p_source_patient_id;

    -- referrals
    FOR v_row IN SELECT id FROM referrals WHERE patient_id = p_source_patient_id LOOP
        v_affected := v_affected || jsonb_build_array(jsonb_build_object(
            'type', 'Referral', 'id', v_row.id::TEXT, 'op', 'updated',
            'previous_patient_id', p_source_patient_id));
        v_count_referral := v_count_referral + 1;
    END LOOP;
    UPDATE referrals SET patient_id = p_target_patient_id
     WHERE patient_id = p_source_patient_id;

    -- clinical_notes
    FOR v_row IN SELECT id FROM clinical_notes WHERE patient_id = p_source_patient_id LOOP
        v_affected := v_affected || jsonb_build_array(jsonb_build_object(
            'type', 'ClinicalNote', 'id', v_row.id::TEXT, 'op', 'updated',
            'previous_patient_id', p_source_patient_id));
        v_count_clinnote := v_count_clinnote + 1;
    END LOOP;
    UPDATE clinical_notes SET patient_id = p_target_patient_id
     WHERE patient_id = p_source_patient_id;

    -- ------------------------------------------------------------------------
    -- Soft-delete the source patient with merge metadata.
    -- ------------------------------------------------------------------------
    UPDATE patients
       SET deleted_at = now(),
           deletion_reason = 'merged',
           merged_into_patient_id = p_target_patient_id
     WHERE id = p_source_patient_id;

    v_affected := v_affected || jsonb_build_array(jsonb_build_object(
        'type', 'Patient',
        'id', p_source_patient_id,
        'op', 'soft_deleted',
        'merged_into_patient_id', p_target_patient_id
    ));

    v_counts := jsonb_build_object(
        'encounters', v_count_enc,
        'diagnoses', v_count_diag,
        'vitals', v_count_vital,
        'allergies', v_count_allergy,
        'prescriptions', v_count_rx,
        'document_refs', v_count_docref,
        'digitised_documents', v_count_digidoc,
        'sick_notes', v_count_sicknote,
        'referrals', v_count_referral,
        'clinical_notes', v_count_clinnote
    );

    RETURN jsonb_build_object(
        'source_patient_id', p_source_patient_id,
        'target_patient_id', p_target_patient_id,
        'merge_reason', p_merge_reason,
        'counts', v_counts,
        'affected_objects', v_affected
    );
END;
$$;

COMMENT ON FUNCTION execute_action_merge_patient(TEXT, TEXT, TEXT, TEXT, TEXT) IS
    'PR 3: consolidate two patients into one. Re-points 10 child tables, '
    'soft-deletes source with merged_into pointer. FOR UPDATE NOWAIT on '
    'both patient rows; deterministic lock order to avoid deadlocks.';


-- ============================================================================
-- reverse_action_merge_patient
-- ============================================================================

CREATE OR REPLACE FUNCTION reverse_action_merge_patient(
    p_audit_id        UUID,
    p_actor_user_id   TEXT,
    p_reason          TEXT DEFAULT NULL
) RETURNS JSONB
LANGUAGE plpgsql AS $$
DECLARE
    v_audit              action_audit_log%ROWTYPE;
    v_affected           JSONB;
    v_entry              JSONB;
    v_new_audit_id       UUID;
    v_reverse_affected   JSONB := '[]'::JSONB;
    v_started_at         TIMESTAMPTZ;
    v_finished_at        TIMESTAMPTZ;
    v_source_patient_id  TEXT;
    v_restored           INT := 0;
BEGIN
    SET LOCAL statement_timeout = '30s';
    v_started_at := now();

    SELECT * INTO v_audit FROM action_audit_log
     WHERE id = p_audit_id FOR UPDATE NOWAIT;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'action_audit_log row not found: %', p_audit_id
            USING ERRCODE = 'P0001', HINT = 'not_found';
    END IF;
    IF v_audit.dry_run THEN
        RAISE EXCEPTION 'cannot reverse dry-run row %', p_audit_id
            USING ERRCODE = 'P0001', HINT = 'cannot_reverse_dry_run';
    END IF;
    IF v_audit.reversed_by_audit_id IS NOT NULL THEN
        RAISE EXCEPTION 'audit row % already reversed', p_audit_id
            USING ERRCODE = 'P0001', HINT = 'precondition_failed';
    END IF;
    IF v_audit.action_name <> 'MergePatient' THEN
        RAISE EXCEPTION 'reverse_action_merge_patient called on action %', v_audit.action_name
            USING ERRCODE = 'P0001', HINT = 'invariant_violated';
    END IF;

    v_affected := COALESCE(v_audit.affected_objects, '[]'::JSONB);
    v_source_patient_id := v_audit.parameters ->> 'source_patient_id';

    -- Restore patient_id on every affected row + un-soft-delete the source.
    FOR v_entry IN SELECT * FROM jsonb_array_elements(v_affected) LOOP
        DECLARE
            v_type TEXT := v_entry ->> 'type';
            v_id   TEXT := v_entry ->> 'id';
            v_prev TEXT := v_entry ->> 'previous_patient_id';
        BEGIN
            IF v_type = 'Consultation' THEN
                UPDATE encounters SET patient_id = v_prev WHERE id = v_id;
            ELSIF v_type = 'Diagnosis' THEN
                UPDATE diagnoses SET patient_id = v_prev WHERE id = v_id::UUID;
            ELSIF v_type = 'Vital' THEN
                UPDATE vitals SET patient_id = v_prev WHERE id = v_id::UUID;
            ELSIF v_type = 'Allergy' THEN
                UPDATE allergies SET patient_id = v_prev WHERE id = v_id::UUID;
            ELSIF v_type = 'Prescription' THEN
                UPDATE prescriptions SET patient_id = v_prev WHERE id = v_id;
            ELSIF v_type = 'DocumentRef' THEN
                UPDATE document_refs SET patient_id = v_prev WHERE id = v_id;
            ELSIF v_type = 'Document' THEN
                UPDATE digitised_documents SET patient_id = v_prev WHERE id = v_id;
            ELSIF v_type = 'SickNote' THEN
                UPDATE sick_notes SET patient_id = v_prev WHERE id = v_id;
            ELSIF v_type = 'Referral' THEN
                UPDATE referrals SET patient_id = v_prev WHERE id = v_id;
            ELSIF v_type = 'ClinicalNote' THEN
                UPDATE clinical_notes SET patient_id = v_prev WHERE id = v_id;
            ELSIF v_type = 'Patient' AND (v_entry ->> 'op') = 'soft_deleted' THEN
                -- Un-soft-delete the source patient.
                UPDATE patients
                   SET deleted_at = NULL,
                       deletion_reason = NULL,
                       merged_into_patient_id = NULL
                 WHERE id = v_id;
            END IF;
            v_restored := v_restored + 1;
            v_reverse_affected := v_reverse_affected || jsonb_build_array(jsonb_build_object(
                'type', v_type, 'id', v_id, 'op', 'reversed_update'
            ));
        END;
    END LOOP;

    v_new_audit_id := gen_random_uuid();
    v_finished_at := now();

    INSERT INTO action_audit_log (
        id, action_name, action_version, actor_user_id, actor_email,
        practice_id, workspace_id, idempotency_key, dry_run,
        parameters, preconditions_checked, effects_applied,
        affected_objects, outcome, error_detail,
        reverses_audit_id, reversed_by_audit_id,
        started_at, finished_at, duration_ms
    ) VALUES (
        v_new_audit_id, 'ReverseActionMergePatient', 1,
        p_actor_user_id, NULL,
        v_audit.practice_id, v_audit.workspace_id, NULL, FALSE,
        jsonb_build_object('reverses_audit_id', p_audit_id::TEXT, 'reason', p_reason),
        '[]'::JSONB, '[]'::JSONB,
        v_reverse_affected, 'reversed', NULL,
        p_audit_id, NULL,
        v_started_at, v_finished_at,
        EXTRACT(MILLISECONDS FROM (v_finished_at - v_started_at))::INT
    );

    UPDATE action_audit_log SET reversed_by_audit_id = v_new_audit_id
     WHERE id = p_audit_id;

    RETURN jsonb_build_object(
        'audit_id', v_new_audit_id,
        'reverses_audit_id', p_audit_id,
        'outcome', 'reversed',
        'restored_count', v_restored,
        'affected_objects', v_reverse_affected
    );
END;
$$;

COMMENT ON FUNCTION reverse_action_merge_patient(UUID, TEXT, TEXT) IS
    'PR 3: undo a MergePatient. Restores every affected row''s '
    'patient_id and clears the source patient''s soft-delete + merge '
    'metadata.';

COMMIT;


-- ==============  END    migrations/022_merge_patient_plpgsql.sql  ==============


-- ============================================================================
-- ==============  BEGIN  migrations/023_pr3_capabilities_seed.sql
-- ============================================================================

-- ============================================================================
-- Migration 023 — Seed new capabilities for PR 3 actions
-- ============================================================================
--
-- Two new capabilities for the new patient/prescription actions:
--
--   prescription_management — VoidPrescription. Granted to anyone who
--     can prescribe. Mapped to platform_essential, platform_professional,
--     and foundation_bundle products.
--
--   patient_admin — SoftDeletePatient, ReassignDocument, MergePatient.
--     POPIA-erasure-grade authority. Mapped to platform_essential and
--     platform_professional (the products with patient-management UI).
--     NOT mapped to module_digitisation alone — Intelligence-Layer-only
--     customers run on their own EHR; patient admin happens there.
--
-- Schema (already in place from seeds/products_and_capabilities.sql):
--
--   capabilities(id TEXT PK, display_name TEXT, description TEXT, created_at)
--   product_capabilities(product_id TEXT, capability_id TEXT, PK pair)
--
-- Idempotent: ON CONFLICT DO NOTHING on both inserts.
-- ============================================================================

BEGIN;

INSERT INTO capabilities (id, display_name, description) VALUES
    ('prescription_management',
     'Prescription Management',
     'Void / cancel prescriptions. Required by clinicians who prescribe.'),
    ('patient_admin',
     'Patient Administration',
     'Soft-delete patients (POPIA right-to-erasure), reassign documents '
     'between patients, merge duplicate patient records. Privileged.')
ON CONFLICT (id) DO NOTHING;

-- prescription_management — anyone with a prescribing UI gets this.
INSERT INTO product_capabilities (product_id, capability_id) VALUES
    ('platform_essential',    'prescription_management'),
    ('platform_professional', 'prescription_management'),
    ('foundation_bundle',     'prescription_management')
ON CONFLICT (product_id, capability_id) DO NOTHING;

-- patient_admin — only the practice-platform products surface the
-- patient management UI. Intelligence-Layer-only customers run on
-- their own EHR; patient lifecycle admin happens there, not here.
INSERT INTO product_capabilities (product_id, capability_id) VALUES
    ('platform_essential',    'patient_admin'),
    ('platform_professional', 'patient_admin')
ON CONFLICT (product_id, capability_id) DO NOTHING;

COMMIT;


-- ==============  END    migrations/023_pr3_capabilities_seed.sql  ==============


-- ============================================================================
-- ==============  BEGIN  migrations/024_query_layer_diagnosis_template.sql
-- ============================================================================

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


-- ==============  END    migrations/024_query_layer_diagnosis_template.sql  ==============


-- ============================================================================
-- ==============  BEGIN  migrations/025_query_capability_seed.sql
-- ============================================================================

-- ============================================================================
-- Migration 025 — Seed the `clinical_query` capability (Phase 3, PR A)
-- ============================================================================
--
-- The Phase-3 query layer's HTTP surface (POST /api/query/run) is the
-- highest-blast-radius READ capability in the system: it runs
-- cross-cutting clinical cohort queries over a whole practice. Locked
-- decision #4 of the Phase-3 plan: it is an EXPLICIT-GRANT capability,
-- NOT in the foundation set — exactly the posture migration 023 took for
-- `patient_admin`. A capability that can enumerate a practice's clinical
-- cohorts must not be default-granted the moment it becomes
-- HTTP-reachable.
--
-- Schema (unchanged, from seeds/products_and_capabilities.sql; confirmed
-- live by migration 023):
--
--   capabilities(id TEXT PK, display_name TEXT, description TEXT, created_at)
--   product_capabilities(product_id TEXT, capability_id TEXT, PK pair)
--
-- PRODUCT MAPPING — chosen on a COHERENCE argument, NOT a demo-
-- enablement one. This distinction is load-bearing; read it before
-- editing the VALUES list.
--
--   platform_essential, platform_professional — the practice-platform
--   tiers, per the migration-023 `patient_admin` precedent.
--
--   legacy_full_access_grant — added on COHERENCE grounds. That product
--   already entails `analytics_cohorts`, `audit_log`, and the
--   `clinical_ai_*` capabilities (verified live: it is the bundle
--   `demo-gp-workspace-001` holds). Those are strictly more sensitive
--   read surfaces than `clinical_query`. A "full access" grant that
--   includes clinical-AI and analytics cohorts but EXCLUDES the query
--   layer is not a tighter blast radius — it is an INCOHERENT
--   entitlement that lies about what "full access" means. `clinical_query`
--   is added to it to remove that incoherence. That this also lets the
--   flagship demo practice exercise the query layer is a CONSEQUENCE of
--   the demo workspace being correctly provisioned on full-access — it
--   is NOT the reason for the mapping. If the demo workspace were on the
--   wrong product, the correct fix would be to move the workspace, never
--   to widen this capability to reach it. Entitlement mappings are
--   chosen for semantic correctness; workspaces are placed on the
--   product that matches their role. Do not bend this list toward a
--   demo.
--
--   NOT `foundation_bundle` — explicit grant, never foundation/default
--   (locked decision #4).
--
--   NOT `module_digitisation` — and this exclusion is a WRITTEN CUSTOMER
--   PROMISE, not merely a precedent. The Type C leave-behind commits in
--   writing that a digitisation-only practice gets digitisation and
--   nothing else and is deliberately NOT pushed onto the platform path.
--   Granting the highest-blast-radius cross-cutting clinical-query
--   surface to `module_digitisation` would make that written commitment
--   a lie. This exclusion is regression-guarded by a build-failing CI
--   ratchet (tests/test_query_layer_invariants.py::
--   test_module_digitisation_never_entails_clinical_query) — the same
--   shape as the PR 5 tenant-guard ratchet, but guarding a customer
--   promise, which makes it more important than a technical invariant,
--   not less. If a future debugging session is tempted to add a
--   one-line grant here to reproduce a bug on a digitisation workspace:
--   move the debugging workspace to a platform product instead.
--
-- HONESTY NOTE (construct validity) — CORRECTED against the live DB,
-- because the first draft of this note asserted something false:
-- `demo-gp-workspace-001` (the workspace `legacy_full_access_grant`
-- entitles, i.e. the one this mapping makes able to run queries) has 31
-- patients but ZERO diagnoses. The one shipped template
-- (`patients_with_diagnosis_prefix`) therefore returns an EMPTY result
-- for demo-gp — it exercises neither the openable nor the unresolvable
-- path over HTTP. The orphaned-source data-quality finding (the
-- dominant ~62% failure) lives in the `test-workspace-*` tenants; the
-- resolvable case lives in `typec-workspace-001`. Neither of those is
-- entitled to `clinical_query` (correctly: typec is module_digitisation,
-- ratchet-guarded). So: the resolver's safety property
-- (orphaned ⇒ visibly unresolvable; present ⇒ openable) IS verified
-- end-to-end against live data by scripts/verify_query_phase0.py probe
-- (iv) — real RPC, real resolver, real signed-URL minting — and through
-- the HTTP/auth stack by tests/test_query_api.py. What is NOT achievable
-- on the current corpus is a single browser click-through that shows a
-- real openable row AND a real unresolvable row on one screen, because
-- no single workspace both (a) is entitled to clinical_query and (b)
-- holds both a resolvable and an orphaned sourced diagnosis. Closing
-- that gap requires a properly provisioned platform-tier demo workspace
-- seeded with both shapes — NAMED here, not faked, and not papered over
-- by bending this entitlement list to a data-bearing workspace.
--
-- Idempotent: ON CONFLICT DO NOTHING on both inserts (re-runnable).
--
-- POSTGREST SCHEMA-CACHE NOTE — deliberately NO `NOTIFY pgrst` here, and
-- that omission is a conscious decision, not an oversight. The
-- `NOTIFY pgrst, 'reload schema'` discipline (Phase-0 finding) exists
-- because a newly-created FUNCTION is invisible to PostgREST's RPC
-- surface until its schema cache reloads. Migration 025 creates no
-- function — it is pure data seeded into existing tables read through
-- the normal app path (require_capability → practice_capabilities),
-- never through PostgREST's function cache. Adding NOTIFY here would be
-- cargo-culting the discipline rather than applying it. Every migration
-- that DOES add a query RPC (024, and 026 in PR B) must still end with
-- NOTIFY; this one correctly does not.
-- ============================================================================

BEGIN;

INSERT INTO capabilities (id, display_name, description) VALUES
    ('clinical_query',
     'Clinical Query Layer',
     'Run registered, tenant-scoped clinical cohort queries '
     '(POST /api/query/run). Every result row carries verifiable '
     'provenance. High-blast-radius read surface — explicit grant.')
ON CONFLICT (id) DO NOTHING;

-- clinical_query — platform tiers (per 023 precedent) + legacy_full_access_grant
-- (on the coherence argument in the header — that product already entails
-- strictly more sensitive read surfaces, so excluding query from it is
-- incoherent, not conservative). Explicit grant; NOT foundation_bundle;
-- NOT module_digitisation (written Type C promise, CI-ratchet-guarded).
INSERT INTO product_capabilities (product_id, capability_id) VALUES
    ('platform_essential',      'clinical_query'),
    ('platform_professional',   'clinical_query'),
    ('legacy_full_access_grant', 'clinical_query')
ON CONFLICT (product_id, capability_id) DO NOTHING;

COMMIT;


-- ==============  END    migrations/025_query_capability_seed.sql  ==============


-- ============================================================================
-- ==============  BEGIN  migrations/026_query_layer_briefing_templates.sql
-- ============================================================================

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


-- ==============  END    migrations/026_query_layer_briefing_templates.sql  ==============


-- ============================================================================
-- ==============  BEGIN  migrations/027_briefing_items.sql
-- ============================================================================

-- ============================================================================
-- Migration 027 — briefing_items (Phase 3 PR D: standing-query materialisation)
-- ============================================================================
--
-- The persistence target for materialised standing queries (morning
-- briefing / pre-consult). Each row is ONE resolved answer row produced
-- by the SAME run_template + resolve_provenance chokepoint /run and /ask
-- use — so every briefing_items row structurally inherits PR A/B's
-- verifiable-provenance + openable/no_source/unresolvable contract.
-- standing.py NEVER reads facts directly; it only writes what the
-- chokepoint resolved. No new data path.
--
-- COLUMNS — grounded in the REAL ResolvedQueryResult.to_dict() /
-- ResolvedRow.to_dict() shape (probed live at PR D, not guessed):
-- row_payload jsonb holds the full per-row {**data, provenance{…},
-- source{status,openable,document_id,signed_url,citation,
-- unresolvable_reason,quality}, additional_sources}; the denormalised
-- top-signal columns (source_status/openable/unresolvable_reason/
-- citation) exist so a UI / probe can read the safety signal cheaply
-- without unpacking jsonb.
--
-- IDEMPOTENCY (PR D §3.3, locked decision #6): the partition key is the
-- triple (workspace_id, kind, as_of_date). materialise_standing_queries
-- DELETEs that exact partition then INSERTs the freshly-resolved rows,
-- one transaction per (workspace_id, kind) — a double-run is row-stable
-- by construction; a mid-run failure's blast radius is exactly the
-- partition being rewritten. The index below backs that DELETE.
--
-- TENANT SCOPE: workspace_id is TEXT and joins workspaces.id (TEXT) with
-- NO ::uuid cast (the heterogeneous-identifier postmortem scar; the
-- materialiser only ever materialises clinical_query-ENTITLED workspaces
-- enumerated from a trusted DB source, never caller input). Added to the
-- PR 5 static tenant-guard TENANT_TABLES (the ratchet only goes down).
--
-- RLS — DENY-ALL, the migration-018 idiom VERBATIM:
--   ENABLE ROW LEVEL SECURITY with NO permissive policy => deny-all to
--   non-bypass roles. The service_role backend (rolbypassrls=TRUE) is
--   unaffected; anon/authenticated get ZERO rows. We deliberately do
--   NOT use FORCE ROW LEVEL SECURITY (018:36 rationale: FORCE would also
--   constrain the bypass-role backend, breaking the app's own writes)
--   and NOT auth.*-keyed policies (the app does not use Supabase Auth;
--   018:43-48). This reproduces exactly the posture migration 018 gave
--   the existing tenant tables.
--
-- POSTGREST SCHEMA-CACHE — `NOTIFY pgrst` is INCLUDED, and that is a
-- consciously-decided call, documented here (locked decision #5; the
-- discipline of 025 omitting it because it added no function and 026
-- including it because it added functions). 027 adds a TABLE and no
-- function. Reasoning for INCLUDING: briefing_items is addressed by the
-- supabase-py REST/table builder (.table("briefing_items")); a stale
-- PostgREST table-schema cache could 404 early .table("briefing_items")
-- calls until the cache happens to reload. NOTIFY is the cheap correct
-- hygiene here even though no function is added — this is a decided
-- inclusion, NOT a cargo-cult of 026's function-driven NOTIFY and NOT a
-- cargo-cult of 025's omission. The test
-- test_standing_queries.py::test_027_migration_ends_with_notify_pgrst_decision_is_explicit
-- enforces only that the decision is EXPLICIT, not its direction.
--
-- ORDERING: strictly after 026. Adds no function, so no
-- template-availability race; standard deploy sequence.
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS public.briefing_items (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    -- idempotency partition key (PR D §3.3)
    workspace_id        TEXT        NOT NULL,
    kind                TEXT        NOT NULL,
    as_of_date          DATE        NOT NULL,
    -- which template produced this row
    template_id         TEXT        NOT NULL,
    template_version    INT,
    -- the full resolved row (ResolvedRow.to_dict())
    row_payload         JSONB       NOT NULL,
    -- denormalised top safety-signal (cheap reads without unpacking jsonb)
    source_status       TEXT,       -- openable | unresolvable | no_source
    openable            BOOLEAN,
    unresolvable_reason TEXT,
    citation            TEXT,
    materialised_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Backs the idempotency DELETE (workspace_id, kind, as_of_date) AND the
-- GET /api/query/briefing reads (workspace_id [+ kind] [+ as_of_date]).
CREATE INDEX IF NOT EXISTS idx_briefing_items_partition
    ON public.briefing_items (workspace_id, kind, as_of_date);

-- Workspace-scoped reads are index-backed (tenant-guard chains carry
-- .eq("workspace_id", …); this keeps them cheap).
CREATE INDEX IF NOT EXISTS idx_briefing_items_workspace
    ON public.briefing_items (workspace_id);

-- RLS deny-all — migration-018 idiom verbatim. Enable RLS, add NO
-- permissive policy. NOT FORCE. NOT auth.*-keyed.
ALTER TABLE public.briefing_items ENABLE ROW LEVEL SECURITY;

-- Phase-0 finding discipline — consciously INCLUDED for 027 (see header:
-- briefing_items is REST-builder-addressed; a stale table-schema cache
-- could 404 early .table() calls). Decided inclusion, not cargo-cult.
NOTIFY pgrst, 'reload schema';

COMMIT;


-- ==============  END    migrations/027_briefing_items.sql  ==============


-- ============================================================================
-- ==============  BEGIN  migrations/028_open_loops.sql
-- ============================================================================

-- ============================================================================
-- Migration 028 — open_loops (Phase 4 PR F: the OpenLoop substrate)
-- ============================================================================
--
-- The persistence target for the fourth ontology object, `OpenLoop`
-- (ontology/objects/open_loop.py). A row is one tracked clinical loop:
-- an opening event, an expected closing event, a deadline, an urgency,
-- and a lifecycle state (the closed transition table in
-- ontology/objects/open_loop_state.py: OPEN → AWAITING → (CLOSED |
-- BREACHED), BREACHED → CLOSED, CLOSED terminal).
--
-- SCOPE — F-1 = option B (LOCKED): this is the SUBSTRATE ONLY. PR F adds
-- the table, the object, the state machine, and the audited mutation
-- actions. It does NOT add a detector (F-4: detectors are PR G) and does
-- NOT instantiate any real loop. The substrate ships built and proven
-- non-vacuous on fabricated input, the first real stateful loop deferred
-- to PR G. This migration creates storage; it asserts nothing about a
-- loop existing.
--
-- COLUMNS — grounded in the REAL OpenLoop field set (open_loop.py), not
-- guessed. loop_kind / state / urgency are TEXT, deliberately NOT a DB
-- ENUM type: F-3 (locked) — the taxonomy is PR G's and extensibility
-- must be structural (PR G adds an enum member, NO migration churn). The
-- (state, *_at) consistency invariant is enforced at the ontology layer
-- (OpenLoop.model_validator, the independent second guard) and the
-- audited-action path is the only writer; the table is storage, the
-- ontology is the guard — the base.py "ontology sits above persistence"
-- principle. A DB CHECK is deliberately NOT added (it is not in PR F's
-- locked scope; the guard is the model_validator + the executor path).
--
-- IDEMPOTENCY: CREATE TABLE IF NOT EXISTS + CREATE INDEX IF NOT EXISTS;
-- a double-run is a clean no-op. No data is seeded (substrate only).
--
-- TENANT SCOPE: workspace_id is TEXT and joins workspaces.id (TEXT) with
-- NO ::uuid cast (the heterogeneous-identifier postmortem scar; the
-- ontology object's `practice_id` is the slug-shaped tenancy ref and
-- maps to this column — the established Patient split). Added to the
-- PR 5 static tenant-guard TENANT_TABLES; under F-1=B the audited Effect
-- primitives use `.table(self.table)` (a variable, not a string
-- literal) so the static scanner finds ZERO `.table("open_loops")`
-- literal chains — adding it to TENANT_TABLES adds ZERO new BASELINE
-- keys (born tenant-scoped; the ratchet only goes down). Proven by
-- running test_no_new_unscoped_tenant_queries, not asserted.
--
-- RLS — DENY-ALL, the migration-018 idiom VERBATIM:
--   ENABLE ROW LEVEL SECURITY with NO permissive policy => deny-all to
--   non-bypass roles. service_role backend (rolbypassrls=TRUE) and the
--   postgres migration role are unaffected; anon/authenticated get ZERO
--   rows. We deliberately do NOT use FORCE ROW LEVEL SECURITY (018:36
--   rationale) and do NOT add auth.*-keyed policies (018:43-48 — the app
--   does not use Supabase Auth). This reproduces exactly the posture
--   migration 018 gave the existing tenant tables and 027 gave
--   briefing_items.
--
-- POSTGREST SCHEMA-CACHE — `NOTIFY pgrst` is INCLUDED, a consciously-
-- decided call (the discipline of 025 omitting it because it added no
-- function, 026 including it because it added functions, 027 including
-- it for a REST-builder-addressed table). 028 adds a TABLE and no
-- function. Reasoning for INCLUDING (same as 027): open_loops is
-- addressed by the supabase-py REST/table builder
-- (.table("open_loops")) via the audited Effect primitives; a stale
-- PostgREST table-schema cache could 404 early .table("open_loops")
-- calls until the cache happens to reload. NOTIFY is the cheap correct
-- hygiene here even though no function is added — a decided inclusion,
-- NOT a cargo-cult of 026's function-driven NOTIFY and NOT a cargo-cult
-- of 025's omission.
--
-- ORDERING: strictly after 027. Adds no function, so no
-- template-availability race; standard deploy sequence.
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS public.open_loops (
    id                          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    -- tenancy (DB-level; the object's practice_id maps here)
    workspace_id                TEXT        NOT NULL,
    -- the patient this loop concerns
    patient_id                  UUID        NOT NULL,
    -- taxonomy discriminator (TEXT, not enum — F-3 structural extensibility)
    loop_kind                   TEXT        NOT NULL,
    -- lifecycle state (the closed transition table is the source of truth)
    state                       TEXT        NOT NULL,
    -- what opened it (PR F substrate: 'manual'; PR G detectors set more)
    opening_event_kind          TEXT        NOT NULL,
    opening_event_ref           TEXT,
    -- human-readable description of the event that would close it
    expected_closing_event_kind TEXT        NOT NULL,
    -- urgency (TEXT, not enum — same F-3 rationale as loop_kind)
    urgency                     TEXT        NOT NULL DEFAULT 'routine',
    -- when it breaches if not closed (nullable: a loop may have none)
    deadline_at                 TIMESTAMPTZ,
    -- lifecycle timestamps (consistency enforced by the ontology guard)
    opened_at                   TIMESTAMPTZ NOT NULL,
    closed_at                   TIMESTAMPTZ,
    closed_reason               TEXT,
    breached_at                 TIMESTAMPTZ,
    -- ontology system fields
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at                  TIMESTAMPTZ
);

-- Workspace-scoped reads by state (the briefing/PR-G read shape) and by
-- patient (the Patient--has_open_loop-->OpenLoop traversal).
CREATE INDEX IF NOT EXISTS idx_open_loops_workspace_state
    ON public.open_loops (workspace_id, state);
CREATE INDEX IF NOT EXISTS idx_open_loops_workspace_patient
    ON public.open_loops (workspace_id, patient_id);

-- RLS deny-all — migration-018 idiom verbatim. Enable RLS, add NO
-- permissive policy. NOT FORCE. NOT auth.*-keyed.
ALTER TABLE public.open_loops ENABLE ROW LEVEL SECURITY;

-- Phase-0 finding discipline — consciously INCLUDED for 028 (see header:
-- open_loops is REST-builder-addressed via the audited Effect
-- primitives; a stale table-schema cache could 404 early .table()
-- calls). Decided inclusion, not cargo-cult.
NOTIFY pgrst, 'reload schema';

COMMIT;


-- ==============  END    migrations/028_open_loops.sql  ==============


-- ============================================================================
-- ==============  BEGIN  migrations/029_query_layer_immunisations_overdue.sql
-- ============================================================================

-- ============================================================================
-- Migration 029 — query_immunisations_overdue (Phase 4 PR G, option B)
-- ============================================================================
--
-- PR G ships ONE real derived cohort (G-1=B locked): patients with an
-- overdue next immunisation dose. STATELESS recomputed cohort (locked
-- Decision 3 / §2.0) — NOT an OpenLoop; no per-row lifecycle. It is a
-- new StandingQuery kind materialising into briefing_items through the
-- SAME run_template+resolve_provenance chokepoint morning_briefing uses
-- — zero new data path, the PR-D "configuration, not a project" payoff.
--
-- THE FUNCTION (mirrors query_patients_not_seen_since, migration 026
-- verbatim idiom):
--   * LANGUAGE sql STABLE. Pure read — never mutates, never audited.
--   * p_workspace_id is the MANDATORY first parameter; the WHERE clause
--     is the structural tenant scope (i.workspace_id = p_workspace_id).
--   * Returns TABLE(... provenance jsonb). PROVENANCE IS HONEST
--     live_entry: the immunizations table has NO source_document_id
--     column (probed 2026-05-17) — immunisations are entered directly in
--     the EHR, there is no source scan. So provenance resolves NO_SOURCE
--     ("entered directly in the EHR"), exactly the honest NULL-sourced
--     case the resolver already handles for demo-gp. This is NOT faked
--     and NOT an error — it is the true provenance of EHR-direct data.
--
-- DATA MATURITY: "thin" (G-3 locked) — 1 overdue of 31 immunisations on
-- the live corpus (probed). Real, but ONE instance. The template
-- declares data_maturity="thin"; a reader must not infer volume.
--
-- NOTIFY pgrst: INCLUDED and REQUIRED — 029 adds a function; without the
-- NOTIFY the new RPC is invisible to PostgREST until the schema cache
-- happens to reload (the Phase-0 finding; the 026 discipline verbatim).
--
-- APPLICATION: this migration is SURFACED for the user's per-migration
-- call. It is NOT auto-applied by the assistant — the
-- assistant-auto-applies-migrations standing rule is REJECTED-tombstoned;
-- migration 028 was the one-time exception, explicitly NOT precedent.
-- The RUN_INTEGRATION materialisation test (read-back of the real
-- overdue row) cannot pass until the user applies this migration.
--
-- ORDERING: strictly after 028. Adds a function; standard deploy.
-- ============================================================================

BEGIN;

CREATE OR REPLACE FUNCTION query_immunisations_overdue(
    p_workspace_id  TEXT
)
RETURNS TABLE(
    patient_id      TEXT,
    first_name      TEXT,
    last_name       TEXT,
    dob             TEXT,
    vaccine_name    TEXT,
    next_dose_due   TEXT,
    provenance      JSONB
)
LANGUAGE sql STABLE AS $$
    SELECT
        p.id, p.first_name, p.last_name, p.dob,
        i.vaccine_name,
        to_char(i.next_dose_due, 'YYYY-MM-DD'),
        jsonb_build_object(
            -- immunizations has NO source_document_id: EHR-direct ⇒
            -- live_entry ⇒ resolver renders NO_SOURCE (honest, not error)
            'source_kind',        'live_entry',
            'source_document_id', NULL,
            'occurred_on',        to_char(i.next_dose_due, 'YYYY-MM-DD'),
            'snippet',
            COALESCE(i.vaccine_name, 'immunisation')
              || ' next dose overdue since '
              || to_char(i.next_dose_due, 'YYYY-MM-DD'),
            'page', NULL
        )
    FROM immunizations i
    JOIN patients p
      ON p.id = i.patient_id
     AND p.workspace_id = i.workspace_id
     AND p.deleted_at IS NULL
    WHERE i.workspace_id = p_workspace_id            -- structural tenant scope
      AND COALESCE(i.series_complete, FALSE) = FALSE
      AND i.next_dose_due IS NOT NULL
      AND i.next_dose_due < current_date
    ORDER BY i.next_dose_due ASC, p.last_name, p.first_name
    LIMIT 500
$$;

COMMENT ON FUNCTION query_immunisations_overdue(TEXT)
IS 'PR G (option B). Patients with an overdue next immunisation dose '
   '(series not complete, next_dose_due < today). STATELESS derived '
   'cohort, NOT an OpenLoop. Provenance = live_entry (immunisations are '
   'EHR-direct; no source_document_id) ⇒ resolves NO_SOURCE honestly.';

NOTIFY pgrst, 'reload schema';

COMMIT;


-- ==============  END    migrations/029_query_layer_immunisations_overdue.sql  ==============


-- ============================================================================
-- ==============  BEGIN  migrations/030_fix_prescriber_provenance.sql
-- ============================================================================

-- 030_fix_prescriber_provenance.sql
--
-- Class-3 honesty fix (founder-decision "Two"; lone unconditional
-- pre-phone defect). The live real-auth Type-C run proved
-- execute_action_promote_document persisted
--   prescriptions.doctor_name = '(Digitised record — prescriber not
--   extracted)'
-- as a hardcoded literal (was migration 015:973) even though the
-- extraction carried medications[].prescribed_by = "Dr A. Tester"
-- (schema gp_patient.py:397; available in v_dgroup_rows at the write
-- scope — assigned 015:949, unmodified to the INSERT). The system held
-- the true value and wrote a durable false provenance claim into a
-- clinical record. Premise verified at file:line; not (b) mismatch but
-- (c)-realised-as-(a): an intentional blanket sentinel.
--
-- Fix shape (bar-ratified, three-case, true-by-construction; btrim-only
-- match strictness fails safe toward honesty — can only over-report
-- ambiguity, never fabricate agreement):
--   * exactly one distinct non-empty prescriber across the date-group's
--     medications  -> that prescriber
--   * none on any med row                  -> the sentinel (TRUE only here)
--   * two or more distinct                 -> an honest ambiguity marker
--     that points the validating doctor at the per-medication detail
--     ("see medications" is actionable: validation_detail returns
--     extractions.medications[].prescribed_by verbatim — proven in the
--     live run's HISTORY/VALIDATION actuals).
--
-- Mechanism: a NEW CREATE OR REPLACE of execute_action_promote_document
-- only (helpers + reverse_* untouched). 015 is applied; editing it
-- in-place would diverge file-from-DB. The function body below is a
-- BYTE-IDENTICAL extraction of migration 015 lines 497-1090 with
-- EXACTLY three surgical changes (proven by diff in the cover note):
--   1. DECLARE: + v_rx_prescriber TEXT;  + v_rx_presc_set TEXT[];
--   2. a pre-INSERT resolution block (uses jsonb_array_elements(
--      v_dgroup_rows) — proven valid at this scope at 015:984)
--   3. the literal at 015:973 -> v_rx_prescriber
-- Idempotency unchanged (same wipe-and-rewrite; only doctor_name's
-- value-source differs). Surgical to doctor_name; prescription_items
-- (classes 1/2) deliberately untouched and held post-first-doctor.
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
    'PromotionResult-shaped JSONB plus affected_objects for the audit row.';

COMMIT;


-- ==============  END    migrations/030_fix_prescriber_provenance.sql  ==============


-- ============================================================================
-- ==============  BEGIN  seeds/products_and_capabilities.sql
-- ============================================================================

-- ============================================================================
-- Seed: products, capabilities, product_capabilities, pricing_bands
-- ============================================================================
--
-- Hand-curated catalog data per the v1.2 strategy doc:
--   /Users/luzuko/Complete Doctor Suite/STRATEGY_HEALTHCARE_TIERING_v1.2.md
--
-- Run AFTER 001_entitlements_core.sql.
--
-- Idempotent: uses ON CONFLICT DO NOTHING so re-running is safe. To update
-- an existing row (e.g. price change), edit the row in-place via a UPDATE
-- statement at the bottom of this file or write a new migration.
--
-- v1.2 price stack locked (§15 of strategy doc):
--   • Practice Essential Solo:    R2,500 founder  / R3,000 list
--   • Practice Essential Small:   R4,000 founder  / R5,000 list
--   • Practice Essential Medium:  R6,500 founder  / R8,500 list
--   • Practice Professional Solo: R4,500 founder  / R5,500 list
--   • Practice Professional Small:R7,500 founder  / R9,500 list
--   • Practice Professional Med:  R12,000 founder / R15,000 list
--   • Module Analytics:           R2,500 founder  / R3,000 list  (flat per practice — Paystack plan only)
--   • Module Digitisation tiers:  Starter R3,500/R4,500 (1,500 pages)
--                                 Growth  R6,000/R7,500 (3,000 pages)
--                                 Scale   R9,500/R12,000 (5,000 pages)
--   • Foundation Bundle:          R5,500 founder  / R6,500 list  (internal SKU)
--   • Module Clinical AI:         Bespoke / often subsidised (Beta)
--   • Group (7+):                 Out of v1 scope (no bands seeded)
--
-- Module Digitisation tier prices live in digitisation_plan_allowances which
-- is created in Phase 4 (002_page_credits.sql). Module Analytics and the
-- Foundation Bundle are flat-priced and configured directly in the Paystack
-- dashboard; the plan codes can be recorded in product_paystack_plans (also
-- Phase 4) once they're created.
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- Products (6 total: 5 customer-facing + 1 internal Foundation Bundle)
-- ----------------------------------------------------------------------------

INSERT INTO products (id, product_line, display_name, description, is_internal_only) VALUES
    ('platform_essential',
        'practice_platform',
        'Practice Platform — Essential',
        'EHR + reception + billing + prescriptions + audit log. For Type A doctors with no digital system today.',
        FALSE),

    ('platform_professional',
        'practice_platform',
        'Practice Platform — Professional',
        'Everything in Essential plus AI Scribe, telehealth, queue/vitals stations, workflow dashboards. For Type B doctors who have an EHR but a broken workflow.',
        FALSE),

    ('module_digitisation',
        'intelligence_layer',
        'Intelligence Layer — Digitisation',
        'Page-credit subscription that turns paper archives into structured data. Universal entry product. Output to SurgiScan or any EHR via FHIR / CSV / JSON.',
        FALSE),

    ('module_analytics',
        'intelligence_layer',
        'Intelligence Layer — Advanced Clinical Analytics',
        'Population-level clinical analytics. Chronic disease cohorts, claims aging, no-show patterns, doctor productivity, drug spend, semantic search.',
        FALSE),

    ('module_clinical_ai',
        'intelligence_layer',
        'Intelligence Layer — Clinical AI (Beta)',
        'Invite-only Beta. Diagnostic Coordinator, Safety Monitor, risk scoring, imaging AI, predictive population health, cryptographically-signed audit trail. Available only to SurgiScan-resident practices.',
        FALSE),

    ('foundation_bundle',
        'internal_bundle',
        'Foundation Bundle (internal SKU)',
        'Digitisation Starter + Analytics. R5,500 founder / R6,500 list. NOT on the customer brochure. Available to Sales when a prospect explicitly wants both upfront.',
        TRUE)
ON CONFLICT (id) DO NOTHING;

-- ----------------------------------------------------------------------------
-- Capabilities (~25 atoms across all products + 1 legacy escape valve)
-- ----------------------------------------------------------------------------

INSERT INTO capabilities (id, display_name, description) VALUES
    -- Practice Platform Essential capabilities
    ('patient_ehr_basic',         'Patient EHR (basic)',           'Patient registry, demographics, encounter records, vitals with auto-BMI, allergies, diagnoses, medications.'),
    ('icd10_coding',              'AI ICD-10 coding',              'GPT-4o-assisted ICD-10 code suggestion across the SA-edition code set.'),
    ('nappi_medications',         'NAPPI medication database',     'NAPPI-coded medication search and prescribing.'),
    ('allergy_alerts',            'Allergy interaction alerts',    'Red-banner alerts in patient EHR; blocking interaction check on prescription.'),
    ('reception_checkin',         'Reception check-in',            'Patient registration and check-in workflow.'),
    ('billing_invoicing',         'Billing & invoicing',           'Invoice generation, line items, PayFast payment-method line on invoices.'),
    ('audit_log',                 'Audit log',                     'Standard application audit log (every edit, who, when).'),
    ('prescription_writing',      'Prescription writing',          'Prescription creation with NAPPI search + allergy interaction check + HPCSA-bearing prescription PDF.'),

    -- Practice Platform Professional capabilities (everything in Essential plus these)
    ('ai_scribe',                 'AI Scribe',                     'GPT-4o-drafted SOAP notes from voice during consult. Doctor reviews and signs.'),
    ('telehealth',                'Telehealth',                    'Video calls, patient chat, e-prescriptions, sick notes, referral letters — all integrated.'),
    ('queue_display',             'Queue display',                 'Real-time waiting-room queue visible to reception and clinical staff.'),
    ('vitals_station',            'Vitals station',                'Nurse vitals capture; auto-populates encounter screen.'),
    ('workflow_dashboards',       'Workflow dashboards',           'Operational dashboards (patient flow, no-show rates, doctor productivity within the practice). Real-time / weekly cadence.'),

    -- Module 01 Digitisation capabilities
    ('digitisation_upload',       'Digitisation upload',           'Document upload pipeline. Subject to monthly page-credit balance check.'),
    ('digitisation_validation',   'Digitisation validation queue', 'Human-in-the-loop validation queue with confidence scores.'),
    ('digitisation_auto_populate','Digitisation auto-population',  'Validated records auto-populate the EHR (allergies, diagnoses, vitals, medications) where applicable.'),
    ('digitisation_export_basic', 'Digitisation export (CSV/JSON)','Export validated records as CSV / JSON. Available v1.'),
    ('digitisation_export_fhir',  'Digitisation export (FHIR R4)', 'Export validated records as FHIR R4 with US Core profile validation. Pulled into v1 per v1.2 strategy doc §11.'),
    ('digitisation_operational_analytics', 'Digitisation operational analytics', 'Throughput, latency, validation accuracy, page-credit consumption, engine health, peer benchmarking for the digitisation pipeline. Ships with Module 01. Distinct from clinical analytics (Module 02).'),

    -- Module 02 Analytics capabilities
    ('analytics_cohorts',         'Cohort analytics',              'Chronic disease cohorts (diabetes, hypertension, asthma) sliced by control status, age, geography.'),
    ('analytics_claims_aging',    'Claims aging analytics',        'Claims aging by medical aid, no-show patterns, revenue leakage analysis.'),
    ('analytics_productivity',    'Doctor productivity analytics', 'Cross-doctor productivity, consults per session, time per encounter, billing variance (group practices).'),
    ('analytics_drug_spend',      'Drug spend analytics',          'Practice-level NAPPI drug spend trends; outlier detection.'),
    ('analytics_semantic_search', 'Unified semantic search',       'Natural-language queries across the practice''s full archive.'),
    ('analytics_dashboards',      'Custom analytics dashboards',   'Custom dashboards + scheduled email reports.'),

    -- Module 03 Clinical AI Beta capabilities
    ('clinical_ai_diagnostic',    'Diagnostic Coordinator',        'Bayesian belief updating across candidate diagnoses; calibrated confidence (Platt scaling). Beta.'),
    ('clinical_ai_safety_monitor','Safety Monitor',                'Silent watch for MI / PE / sepsis / stroke; SAFETY ALERT on threshold exceedance. Beta.'),
    ('clinical_ai_risk_scoring',  'Clinical risk scoring',         'Survival curves and 1/5/10-year risk projections for chronic patients. Beta.'),
    ('clinical_ai_imaging',       'Imaging AI',                    'Chest X-ray flagging with bounding boxes. Beta.'),
    ('clinical_ai_population',    'Predictive population health',  'Forward-looking patient deterioration risk over 90 days. Beta.'),
    ('clinical_ai_audit_signed',  'Cryptographic audit trail',     'Append-only cryptographically-signed log of every AI inference. Beta.'),

    -- Grandfathering: legacy_full_access for existing customers migrated from v1 subscription_tier model.
    -- Mapped to ALL capabilities in product_capabilities below. Sunset in Phase 5 once all customers
    -- have been migrated to specific entitlements per the new model.
    ('legacy_full_access',        'Legacy full access (sunset)',   'Grandfathering capability for customers migrated from the v1 subscription_tier model. Grants every capability. To be sunset in Phase 5.')
ON CONFLICT (id) DO NOTHING;

-- ----------------------------------------------------------------------------
-- Product → Capability mappings
-- ----------------------------------------------------------------------------

-- Practice Essential
INSERT INTO product_capabilities (product_id, capability_id) VALUES
    ('platform_essential', 'patient_ehr_basic'),
    ('platform_essential', 'icd10_coding'),
    ('platform_essential', 'nappi_medications'),
    ('platform_essential', 'allergy_alerts'),
    ('platform_essential', 'reception_checkin'),
    ('platform_essential', 'billing_invoicing'),
    ('platform_essential', 'audit_log'),
    ('platform_essential', 'prescription_writing')
ON CONFLICT DO NOTHING;

-- Practice Professional (everything in Essential plus the workflow upgrades)
INSERT INTO product_capabilities (product_id, capability_id) VALUES
    ('platform_professional', 'patient_ehr_basic'),
    ('platform_professional', 'icd10_coding'),
    ('platform_professional', 'nappi_medications'),
    ('platform_professional', 'allergy_alerts'),
    ('platform_professional', 'reception_checkin'),
    ('platform_professional', 'billing_invoicing'),
    ('platform_professional', 'audit_log'),
    ('platform_professional', 'prescription_writing'),
    ('platform_professional', 'ai_scribe'),
    ('platform_professional', 'telehealth'),
    ('platform_professional', 'queue_display'),
    ('platform_professional', 'vitals_station'),
    ('platform_professional', 'workflow_dashboards')
ON CONFLICT DO NOTHING;

-- Module 01 Digitisation
INSERT INTO product_capabilities (product_id, capability_id) VALUES
    ('module_digitisation', 'digitisation_upload'),
    ('module_digitisation', 'digitisation_validation'),
    ('module_digitisation', 'digitisation_auto_populate'),
    ('module_digitisation', 'digitisation_export_basic'),
    ('module_digitisation', 'digitisation_export_fhir'),
    ('module_digitisation', 'digitisation_operational_analytics')
ON CONFLICT DO NOTHING;

-- Module 02 Analytics
INSERT INTO product_capabilities (product_id, capability_id) VALUES
    ('module_analytics', 'analytics_cohorts'),
    ('module_analytics', 'analytics_claims_aging'),
    ('module_analytics', 'analytics_productivity'),
    ('module_analytics', 'analytics_drug_spend'),
    ('module_analytics', 'analytics_semantic_search'),
    ('module_analytics', 'analytics_dashboards')
ON CONFLICT DO NOTHING;

-- Module 03 Clinical AI
INSERT INTO product_capabilities (product_id, capability_id) VALUES
    ('module_clinical_ai', 'clinical_ai_diagnostic'),
    ('module_clinical_ai', 'clinical_ai_safety_monitor'),
    ('module_clinical_ai', 'clinical_ai_risk_scoring'),
    ('module_clinical_ai', 'clinical_ai_imaging'),
    ('module_clinical_ai', 'clinical_ai_population'),
    ('module_clinical_ai', 'clinical_ai_audit_signed')
ON CONFLICT DO NOTHING;

-- Foundation Bundle (Digitisation + Analytics — internal SKU)
INSERT INTO product_capabilities (product_id, capability_id) VALUES
    ('foundation_bundle', 'digitisation_upload'),
    ('foundation_bundle', 'digitisation_validation'),
    ('foundation_bundle', 'digitisation_auto_populate'),
    ('foundation_bundle', 'digitisation_export_basic'),
    ('foundation_bundle', 'digitisation_export_fhir'),
    ('foundation_bundle', 'digitisation_operational_analytics'),
    ('foundation_bundle', 'analytics_cohorts'),
    ('foundation_bundle', 'analytics_claims_aging'),
    ('foundation_bundle', 'analytics_productivity'),
    ('foundation_bundle', 'analytics_drug_spend'),
    ('foundation_bundle', 'analytics_semantic_search'),
    ('foundation_bundle', 'analytics_dashboards')
ON CONFLICT DO NOTHING;

-- Legacy grandfathering: legacy_full_access grants ALL capabilities.
-- We model this by mapping it to every capability rather than special-casing
-- the function. This way, sunset is a simple DELETE FROM product_capabilities
-- WHERE product_id IN (SELECT id FROM products WHERE id IN ('legacy_full_access_grant'))
-- when the time comes.
--
-- We treat 'legacy_full_access' as both a capability AND a stand-in product
-- so existing customers can be granted it via a regular practice_entitlements
-- row pointing to a synthetic product. Insert that synthetic product:
INSERT INTO products (id, product_line, display_name, description, is_internal_only) VALUES
    ('legacy_full_access_grant',
        'internal_bundle',
        'Legacy full access (sunset)',
        'Synthetic product used to grandfather existing customers from the v1 subscription_tier model. Maps to every capability. To be sunset in Phase 5.',
        TRUE)
ON CONFLICT (id) DO NOTHING;

-- Map the legacy grant product to every capability (including itself for completeness).
INSERT INTO product_capabilities (product_id, capability_id)
SELECT 'legacy_full_access_grant', id FROM capabilities
ON CONFLICT DO NOTHING;

-- ----------------------------------------------------------------------------
-- Pricing bands — Practice Platform tiers, Solo / Small / Medium
-- (Group 7+ deliberately omitted — out of v1 scope per v1.2 §10)
--
-- Prices are in cents (multiply ZAR by 100). E.g. R2,500 = 250000.
-- Paystack plan codes (paystack_plan_code_founder, paystack_plan_code_list)
-- are intentionally NULL — they're populated AFTER the plans are created in
-- the Paystack dashboard during Phase 1 manual setup.
-- ----------------------------------------------------------------------------

INSERT INTO pricing_bands (
    id, product_id, band_name, min_doctors, max_doctors,
    monthly_price_cents_founder, monthly_price_cents_list,
    paystack_plan_code_founder, paystack_plan_code_list
) VALUES
    -- Practice Essential
    ('platform_essential_solo',    'platform_essential',    'Solo',    1, 1,    250000,  300000,  NULL, NULL),
    ('platform_essential_small',   'platform_essential',    'Small',   2, 3,    400000,  500000,  NULL, NULL),
    ('platform_essential_medium',  'platform_essential',    'Medium',  4, 6,    650000,  850000,  NULL, NULL),

    -- Practice Professional
    ('platform_professional_solo',   'platform_professional', 'Solo',    1, 1,    450000,  550000,  NULL, NULL),
    ('platform_professional_small',  'platform_professional', 'Small',   2, 3,    750000,  950000,  NULL, NULL),
    ('platform_professional_medium', 'platform_professional', 'Medium',  4, 6,   1200000, 1500000,  NULL, NULL)
ON CONFLICT (id) DO NOTHING;

COMMIT;

-- ============================================================================
-- Sanity-check queries
-- ============================================================================
--
-- -- 6 products (5 customer-facing + 1 internal + 1 legacy = 7 total)
-- SELECT id, product_line, is_internal_only FROM products ORDER BY product_line, id;
--
-- -- ~26 capabilities (24 real + legacy_full_access = 25)
-- SELECT count(*) FROM capabilities;
--
-- -- Practice Professional should grant 13 capabilities
-- SELECT capability_id FROM product_capabilities WHERE product_id = 'platform_professional' ORDER BY capability_id;
--
-- -- 6 pricing bands (Essential + Professional × Solo/Small/Medium)
-- SELECT id, monthly_price_cents_founder / 100 AS r_founder, monthly_price_cents_list / 100 AS r_list
-- FROM pricing_bands ORDER BY id;
--
-- -- Smoke test: a hypothetical practice with platform_professional active
-- -- has ai_scribe but not clinical_ai_diagnostic.
-- -- (Run after provisioning a test entitlement.)
--
-- ============================================================================


-- ==============  END    seeds/products_and_capabilities.sql  ==============
