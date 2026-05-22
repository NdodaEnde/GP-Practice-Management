-- ============================================================================
-- Migration 037 — align the tier products with the actual go-to-market
-- ============================================================================
--
-- The product catalog was built EHR-first: platform_essential / platform_professional
-- were EHR tiers and digitisation was a bolt-on (module_digitisation). The business
-- is digitisation-first: Essential = digitisation; Professional = digitisation + full EHR.
-- The catalog never caught up, leaving two traps (see the sweep notes):
--   * platform_essential was MISNAMED — it granted the EHR stack, not digitisation.
--   * NO single product granted "digitisation + EHR" (platform_professional had EHR
--     but not digitisation), so the only thing that did was the sunset legacy grant.
--
-- This migration makes the two tier products honest and properly nested:
--   * platform_essential      = the digitisation capability set (Essential tier).
--   * platform_professional   = digitisation + the full EHR/clinical/billing stack
--                               (Professional tier = Essential ∪ EHR).
-- => platform_essential ⊂ platform_professional, and "Professional = Essential + EHR"
--    is now a single clean product.
--
-- Capability resolution (practice_capabilities RPC) joins active entitlements to
-- product_capabilities and does NOT check products.active, so this row rewrite is
-- the authoritative change. Live impact: platform_essential has ZERO entitlements;
-- platform_professional's one holder (demo-briefing-workspace-001) correctly GAINS
-- digitisation. module_digitisation is unchanged (existing Essential workspaces and
-- onboard_practice.py keep using it — it is capability-equivalent to platform_essential).
--
-- Idempotent: rewrites the two products' capability rows from scratch.
-- ============================================================================

BEGIN;

-- The 6 digitisation capabilities (mirrors module_digitisation).
-- The full EHR/clinical/billing stack platform_professional already carried.
DELETE FROM product_capabilities WHERE product_id IN ('platform_essential', 'platform_professional');

-- Essential tier = digitisation only.
INSERT INTO product_capabilities (product_id, capability_id) VALUES
    ('platform_essential', 'digitisation_upload'),
    ('platform_essential', 'digitisation_validation'),
    ('platform_essential', 'digitisation_auto_populate'),
    ('platform_essential', 'digitisation_export_basic'),
    ('platform_essential', 'digitisation_export_fhir'),
    ('platform_essential', 'digitisation_operational_analytics');

-- Professional tier = Essential (digitisation) + the full EHR / clinical / billing stack.
INSERT INTO product_capabilities (product_id, capability_id) VALUES
    -- digitisation (same as Essential)
    ('platform_professional', 'digitisation_upload'),
    ('platform_professional', 'digitisation_validation'),
    ('platform_professional', 'digitisation_auto_populate'),
    ('platform_professional', 'digitisation_export_basic'),
    ('platform_professional', 'digitisation_export_fhir'),
    ('platform_professional', 'digitisation_operational_analytics'),
    -- EHR / clinical / billing / workflow
    ('platform_professional', 'patient_ehr_basic'),
    ('platform_professional', 'patient_admin'),
    ('platform_professional', 'prescription_management'),
    ('platform_professional', 'prescription_writing'),
    ('platform_professional', 'allergy_alerts'),
    ('platform_professional', 'icd10_coding'),
    ('platform_professional', 'nappi_medications'),
    ('platform_professional', 'billing_invoicing'),
    ('platform_professional', 'reception_checkin'),
    ('platform_professional', 'queue_display'),
    ('platform_professional', 'vitals_station'),
    ('platform_professional', 'clinical_query'),
    ('platform_professional', 'audit_log'),
    ('platform_professional', 'ai_scribe'),
    ('platform_professional', 'telehealth'),
    ('platform_professional', 'workflow_dashboards');

COMMIT;
