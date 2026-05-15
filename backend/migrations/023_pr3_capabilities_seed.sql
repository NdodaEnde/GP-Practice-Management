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
