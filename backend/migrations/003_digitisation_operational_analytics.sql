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
