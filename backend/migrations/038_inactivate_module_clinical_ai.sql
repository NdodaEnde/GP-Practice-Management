-- ============================================================================
-- Migration 038 — inactivate module_clinical_ai (catalog guardrail)
-- ============================================================================
--
-- module_clinical_ai is the catalog placeholder for the clinical-AI suite —
-- 6 capabilities (clinical_ai_diagnostic / _imaging / _risk_scoring /
-- _safety_monitor / _population / _audit_signed) that map 1:1 to the Healthcare
-- Intelligence Agent components in the book "30 Agents Every AI Engineer Must
-- Build", Chapter 13 (Healthcare and Scientific Agents). NONE of the six have a
-- backend, frontend, or data layer today — they are the documented roadmap.
--
-- The decision (re-affirmed 2026-05-22 after reading Ch 13): defer this build.
-- Reasons: each layer is real depth (POMDP belief / Bayesian update / Brier
-- calibration / FHIR adapters / dual-memory knowledge base / signed 7-year
-- audit / cost-derived safety thresholds / FDA-SaMD positioning), and the
-- realisable wedge is the digitisation-fed Intelligence Overlay (morning
-- briefing + clinical analytics + drug analytics) shipped via clinical_query
-- and the 2 wired analytics capabilities.
--
-- This sets module_clinical_ai.active = false as a CATALOG GUARDRAIL so the
-- product cannot be accidentally entitled at onboarding. Capability resolution
-- (practice_capabilities RPC) joins entitlements x product_capabilities and
-- IGNORES products.active, so this:
--   * does NOT revoke caps from anyone (no entitlements reference it today),
--   * does NOT affect the 6 capability rows or the product_capabilities mapping —
--     they remain in place as the documented build-target.
-- It's a SALES/ONBOARDING discipline flag, not a feature flip.
--
-- Reversible: UPDATE products SET active = true WHERE id = 'module_clinical_ai';
-- Idempotent: safe to re-run (UPDATE to the same value is a no-op).
-- ============================================================================

BEGIN;

UPDATE products
SET active = false
WHERE id = 'module_clinical_ai';

COMMIT;
