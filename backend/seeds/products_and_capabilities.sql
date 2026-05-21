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
    ('digitisation_upload',       'Digitisation upload',           'Document upload pipeline. Flat per-practice plan with a monthly fair-use page allowance (usage shown + warned near the cap; uploads are not blocked).'),
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
