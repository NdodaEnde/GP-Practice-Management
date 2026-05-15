-- ============================================================================
-- Migration 023 — Seed new capabilities for PR 3 actions
-- ============================================================================
--
-- Two new capabilities for the new patient/prescription actions:
--
--   prescription_management — VoidPrescription. By default grant to
--     anyone who can prescribe. The seed adds it to foundation_bundle.
--
--   patient_admin — SoftDeletePatient, ReassignDocument, MergePatient.
--     POPIA-erasure-grade authority; deliberately NOT in foundation_bundle.
--     Practice owners and dedicated practice admins should opt-in.
--
-- The `capabilities` table seed schema:
--   id (TEXT, capability name)
--   description (TEXT)
--   tier (TEXT) — historical; informational.
--
-- The bundle/mapping seed schema (from seeds/products_and_capabilities.sql):
--   bundle_capabilities (bundle_id TEXT, capability_id TEXT).
--
-- Idempotent: ON CONFLICT DO NOTHING.
-- ============================================================================

BEGIN;

INSERT INTO capabilities (id, description, tier) VALUES
    ('prescription_management',
     'Void / cancel prescriptions. Required by clinicians who prescribe.',
     'foundation'),
    ('patient_admin',
     'Soft-delete patients (POPIA right-to-erasure), reassign documents '
     'between patients, merge duplicate patient records. Privileged — '
     'grant only to practice admins.',
     'advanced')
ON CONFLICT (id) DO NOTHING;

-- prescription_management → foundation_bundle (granted by default).
INSERT INTO bundle_capabilities (bundle_id, capability_id) VALUES
    ('foundation_bundle', 'prescription_management')
ON CONFLICT (bundle_id, capability_id) DO NOTHING;

-- patient_admin is NOT in foundation_bundle. Practices grant per-user.

COMMIT;
