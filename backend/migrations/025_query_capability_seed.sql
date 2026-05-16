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
