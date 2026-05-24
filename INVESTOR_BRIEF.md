# SurgiScan — Build Status Brief (for investors)

**MedicData (Pty) Ltd · SurgiScan platform · prepared 2026-05-22**

This document is written with the same discipline the platform itself is built on:
specific, verifiable, and honest about what is *not* yet built.

---

## In one paragraph

SurgiScan is a multi-tenant healthcare platform for South African GP practices,
designed around a Palantir-Foundry-style ontology engine with POPIA-aligned multi-tenant
isolation. The commercial wedge is **document digitisation** (the Essential tier) —
turning a practice's paper/PDF records into structured, queryable patient data with
audited provenance. The Professional tier extends that with a full EHR. An "intelligence
overlay" (morning briefing, analytics) layers on top. The platform is built; the
Essential tier is at the door of its first concierge customer launch.

---

## 1. PRODUCTION-READY — at the door of launch

The following ships today; the only remaining steps are operational (Render deploy +
the first customer):

### Essential tier (the commercial wedge)
- **Document digitisation pipeline**: upload → AI extraction (LandingAI OCR) →
  validation queue → review screen → approve → audited promotion into structured
  patient/encounter/diagnosis/vitals/prescription records.
- **Verified end-to-end** including the live LandingAI extraction path; cross-tenant
  isolation probed; no mock-data-as-real on any screen.
- **Document-centric search + lookup** (find a scan by patient name, ID number,
  file number, or filename), CSV / FHIR R4 export, operational insights.
- **Concierge onboarding script** (`scripts/onboard_practice.py --plan essential`)
  — one command provisions a new practice with the right tier entitlement, admin
  login (strong random password, bcrypt-hashed), manual-billing flag, and a
  post-write capability-boundary check that proves no tier leak. Runbook:
  `scripts/ONBOARDING_RUNBOOK.md`.
- **In-app password rotation** (sidebar → *Change Password*). Verifies the current
  password against the stored hash before setting a new one (8-char minimum).
  Customers are told to rotate their issued password on first login.
- **Concierge password-reset fallback** (`scripts/reset_user_password.py --email
  <user>`) — for the locked-out case until the self-service forgot-password
  email flow is built (deferred — see §5).

### Platform foundation that the Essential tier rides on
- **Multi-tenant by design**: every read/write is workspace-scoped from the
  authenticated token; cross-tenant probes pass on every rebuilt module
  (digitisation, billing, queue, vitals, analytics, AI-scribe).
- **POPIA-aligned data layer**: Supabase Postgres with Row-Level Security
  enabled on all tenant / PHI tables (migration 033), service-role bypass for
  the backend, deny-all to anon/authenticated otherwise.
- **Audit substrate**: `action_audit_log` (migration 014) captures every
  ontology action — action name, parameters, preconditions checked, effects
  applied, affected objects, idempotency key, reversal pointers. Append-only by
  convention.
- **Production deployment runbook**: `DEPLOYMENT.md` — Render blueprint (one
  backend service + one static frontend), secrets list, CORS wiring,
  cross-tenant probe at deploy, pre-launch checklist. Production Supabase
  project verified (RLS complete, no patient data, buckets private).
- **Migration-history reproducibility**: `migrate_dev_to_prod.sh` replays the
  full schema; no ad-hoc "production bootstrap" scripts (a known anti-pattern,
  explicitly avoided).

### What it takes to launch the first paying customer
1. Click-deploy on Render (blueprint configured).
2. Set production secrets + CORS.
3. Run the cross-tenant probe against the live prod backend (~2 min).
4. One live LandingAI OCR smoke (single real PDF, end-to-end).
5. `onboard_practice.py` pointed at prod with the customer's details.

These are operational steps, not engineering work.

---

## 2. BUILT, AWAITING THE FIRST CUSTOMER — Professional tier

The Professional tier (Essential + full EHR) was **rebuilt onto the foundation,
swept, and live-browser-verified this period**, but no Professional customer has
been onboarded yet — it's built before sold, not sold before built.

### What's in the Professional tier (verified live)
- **Clinical**: patient management, encounters, vitals (rebuilt + drift-fixed),
  prescriptions, allergies, diagnoses, lab orders/results, conditions, AI scribe
  (Whisper transcription + GPT-4o SOAP generation; verbatim transcript stored
  in Supabase with workspace scoping).
- **Billing**: invoices, payments, medical-aid claims, revenue reports, outstanding
  reports — workspace-scoped, cross-tenant probe 13/13 pass.
- **Operations**: reception check-in, patient queue, queue display, workstation
  dashboard, financial dashboard, claims management.
- **Analytics**: clinical (top diagnoses / medications / allergies / age
  distribution / encounter stats), prescription analytics (volume / schedule /
  monthly trend).

### Verification done this period
- **Browser-verified live (Playwright over running stack)**: 10/10 Professional
  pages load real workspace-scoped data with zero `>=4xx` on `/api/*` and no
  console errors. PatientEHR tabs (medications from real prescriptions,
  investigations from real lab orders, documents from digitised store, vitals
  with honest empty states) screenshot-confirmed.
- **Tier catalog cleaned (migration 037)**: `platform_professional` is now a
  single clean product = digitisation + full EHR (was previously EHR-only,
  forcing a dev "everything" workaround). `platform_essential` is now honestly
  digitisation-only and a clean subset of Professional.
- **All Mongo-on-live-paths removed**: queue (was last Mongo feature),
  AI-scribe transcript, medications read — all moved to Supabase with proper
  scoping and migration history (034 / 035 / 036).

---

## 3. PLATFORM FOUNDATION — the architectural moat

This is the differentiator investors should understand most:

- **Palantir / Foundry-fashioned ontology layer**: typed Objects (Patient,
  Document, Consultation, OpenLoop), declared Links between them, 13 Actions
  through an executor with preconditions / effects / idempotency / reversal
  contract / signed audit, 9 Query templates, standing queries that
  materialise into the morning briefing, end-to-end provenance resolution at
  every chokepoint. The intent is for this to become the platform's engine —
  see roadmap below.
- **Capability + entitlement model**: every protected route is gated against a
  capability; capabilities resolve from active practice entitlements joined
  to product capabilities (a Postgres RPC). Tiers (`platform_essential`,
  `platform_professional`) and modules (`module_digitisation`,
  `module_analytics`, `module_clinical_ai`) compose freely. Tier-boundary
  checks at onboarding prove a tier never leaks unpurchased modules.
- **Built-in honesty discipline**: query templates explicitly forbid registering
  derived "kinds" without honest data backing (the "fake-property anti-pattern"
  guardrail is in the code, with tests). Provenance is resolved at every
  query chokepoint; reversal claims are audited (a forbidden reversal claim
  fails its honesty test).

This foundation is also why the deferred Clinical-AI build (see §5) is
relatively cheap when it's time — every rebuilt module ports cleanly onto
the ontology when convergence work happens.

---

## 4. INTELLIGENCE OVERLAY — works today, partial in scope

The smallest credible "intelligence overlay" SKU ships today on top of either
tier (most naturally: Essential + intelligence):

- **Morning briefing** — currently materialises **2 standing queries**: "patients
  not seen in 180 days" (recall cohort) and "overdue immunisations". Workspace-
  scoped; reads `briefing_items`. *Operational gap: the autonomous scheduler
  exists but ships disabled; today it requires a manual or cron refresh.*
- **Clinical analytics** — top diagnoses / medications / allergies, age
  distribution, encounter stats, all workspace-scoped (capability
  `analytics_cohorts`).
- **Prescription analytics** — volume / schedule distribution / monthly trend
  over a 90-day window (capability `analytics_drug_spend`). *Honest documented
  limit: true ZAR drug-spend requires NAPPI pricing data not yet loaded;
  endpoint currently returns volume-based metrics.*

The other 4 advanced-analytics capabilities (`analytics_claims_aging`,
`analytics_dashboards`, `analytics_productivity`, `analytics_semantic_search`)
are catalog-only — they have no backend yet.

---

## 5. NOT READY FOR PRODUCTION — explicitly deferred (with rationale)

The discipline of this section is the most important part of the document.

### Clinical AI suite — DEFERRED (`module_clinical_ai` inactivated as guardrail)
- 6 capabilities (diagnostic, imaging, risk-scoring, safety-monitor, population,
  signed-audit) — all catalog-only, **no backend, no frontend, no data layer**.
- Maps 1:1 to the reference architecture in "30 Agents Every AI Engineer Must
  Build" Chapter 13 (Healthcare and Scientific Agents) — POMDP + Bayesian
  belief, Brier-Platt calibration, FHIR R4 adapters across HL7v2 / Epic /
  Cerner, dual-memory clinical knowledge base, cryptographically signed 7-year
  HIPAA audit, cost-derived safety thresholds, FDA-SaMD positioning.
- Deferred because each layer is real depth, not a sprint, and shouldn't be
  built before there's a defined clinical problem, regulatory pathway, and
  revenue from the realisable wedge.
- **Guardrail in place** (migration 038): `module_clinical_ai.active = false`
  so the product cannot be accidentally entitled at onboarding. The 6
  capability rows are preserved as the documented build-target.

### Inbound EHR integration — NOT built
- The platform exports FHIR but does not import from external EHRs.
- For clients on a competitor EHR, the ingestion path today is **digitisation**
  (their exports / printed records → SurgiScan's structured schema → analytics
  / briefing). A structured-import path (FHIR bundle straight into the
  schema, skipping OCR) would be a meaningful enabler and is on the roadmap.

### Self-service forgot-password (email flow) — NOT built; concierge fallback in place
- Backend endpoint exists but is a placeholder; the integrated build (token
  generation + email send + reset-page UI) is deferred.
- For v1 concierge customers, the operator runs `scripts/reset_user_password.py
  --email <user>`, which writes a new bcrypt hash and prints the new password
  for secure-channel handover. Documented in `ONBOARDING_RUNBOOK.md`.
- Self-service is a post-launch build (requires email-service integration —
  SendGrid / SES / Postmark or Supabase Auth).

### Briefing scheduler — exists but ships disabled
- `app/services/standing_query_scheduler.py` is built but intentionally off.
  Production briefing requires manual `POST /briefing/refresh` or an external
  cron until enabled — an operational decision, not a build.

### Other items honestly named, not active
- Public self-serve signup — by design v1 is concierge only.
- 850-LoC functional reversal for promote_document — named-not-built (a
  property the code claims has been honestly fixed at the metadata level).
- Several `*TestPage` developer routes have been removed from the production
  build this period (cleanup).

---

## 6. RISK REGISTER — what investors will rightly ask

| Risk | Honest status |
|---|---|
| **Single point of failure on LandingAI** (OCR) | True. Fallback OCR not built; budget cap on extractions per page is configured. Diversification is a future build. |
| **AI-scribe depends on OpenAI** (Whisper + GPT-4o) | True. Third-party dependency; no on-prem fallback. South-African data residency for OpenAI is provider-dependent. |
| **No live integration with competitor EHRs** | True; ingestion is via digitisation today (see §5). |
| **Concierge onboarding doesn't scale to thousands of customers** | True, and intentional for v1. Self-serve is a build, not a config. |
| **The ontology engine is intended to underpin the platform but currently coexists with direct-to-Supabase REST handlers** | True. Two access patterns (ontology for digitisation/actions/queries; REST for CRUD). The convergence direction is being researched (three options on the table); the existing REST work is correct in isolation but not yet ontology-mediated. |
| **POPIA compliance is engineered-in but not externally audited** | True. RLS, multi-tenant isolation, capability gating, audit substrate, no PHI in browser console, signed-audit roadmap are all in place. Formal POPIA audit / SOC2-equivalent has not been commissioned. |
| **Default-credential dev accounts must never reach prod** | True. The dev autologin routes are gated behind a build flag (off in production builds). The standing launch-blocker (DEPLOYMENT.md item 3b) is "verify no `admin@surgiscan.com / password123` style account exists in prod." |
| **Tests + browser verification are extensive but not formal UAT** | True. 178-test gating suite passes; live Playwright pass over Professional pages; live cross-tenant probes per module. Formal user-acceptance testing happens with customer #1. |

---

## 7. WHAT THE NEXT R OF FUNDING WOULD FUND

Honest framing of where capital moves the needle:
- **First N concierge customers + dedicated customer-success motion** — the
  proof that the wedge converts and the briefing/analytics drive retention.
- **Structured-import (FHIR bundle → schema)** — opens the door to clients on
  competitor EHRs without forcing a migration.
- **Briefing expansion + scheduler enablement** — turns the morning brief from
  "2 kinds of items, manual refresh" into a real daily-driver feature with
  lab anomalies, follow-up alerts, today's panel, etc.
- **Self-serve signup + automated billing** — concierge → SaaS scale path.
- **Clinical AI: build the first single capability** (likely `risk_scoring`
  or `safety_monitor`) as the credible foothold of the deferred suite. Ch 13
  is the reference architecture; nothing needs to be re-derived.

---

## How to verify any of this

Every claim in this brief can be checked against the codebase and migration
history in the SurgiScan repo:

- Production-readiness: `DEPLOYMENT.md`, `scripts/ONBOARDING_RUNBOOK.md`,
  `migrations/033_enable_rls_all_tenant_tables.sql`.
- Tier model: `migrations/037_align_tier_products.sql`,
  `scripts/onboard_practice.py`.
- Foundation: `backend/ontology/` (objects, links, actions, query, mappers,
  provenance), `migrations/014_action_audit_log.sql`.
- Sweep + browser verification: `backend/tests/manual/` (cross-tenant probes
  for billing / queue / vitals; `professional_browser_verify.py`).
- Deferral guardrails: `migrations/038_inactivate_module_clinical_ai.sql`.

— end —
