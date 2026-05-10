# Production-readiness checklist — Type C Digitisation

> Use this before inviting **any external user** to the workspace, paying or not.
> Items are grouped by what code can fix vs what needs human action.

Last updated: **2026-05-10**.

---

## 🔒 Code-side hardening — *shipped 2026-05-10*

| # | Item | Where |
|---|---|---|
| 1 | Hardcoded Supabase service-role JWT removed from 12 backend scripts (env-only) | `backend/{init_,load_,test_}*.py` |
| 2 | `.env` files confirmed never committed; `.gitignore` covers them | repo-wide audit |
| 3 | FHIR bearer tokens redacted from POST/PATCH `/fhir/connections` responses | `backend/app/api/digitisation.py::_redact_fhir_connection` |
| 4 | Patient match details + confidence (`id_number` / `name_dob` / created) returned in promotion summary; ambiguous matches flagged | `backend/app/services/extraction_promoter.py::_match_or_create_patient` |
| 5 | Validation history drawer surfaces the matched patient's name/dob/id + a coloured confidence pill | `frontend/src/components/groundtruth/ValidationHistoryDrawer.jsx` |
| 6 | Semantic-search indexer status (`search_indexed_at`, `search_index_chunks`, `search_index_error`) now persisted on `digitised_documents` so silent BackgroundTasks failures are visible | migration 012 + `semantic_search.py::_record_index_result` |
| 7 | `/api/digitisation/search` rate-limited to 30 queries/minute/user (in-process, swap to Redis for multi-instance) | `backend/app/api/digitisation.py::_enforce_search_rate_limit` |
| 8 | FHIR bundle storage moved from local disk to Supabase Storage (`digitisation-exports` bucket) with disk fallback for dev | `digitisation_export_worker.py::_store_bundle / fetch_bundle` |
| 9 | Phase C: auto-POST FHIR bundle to default connection after generation; status tracked separately from bundle generation | `digitisation_export_worker.py::_attempt_push` |
| 10 | Schema completion: `encounters.doctor_id` (§10c.3), `gp_invoices.workspace_id` (§10c.2), patient registry list index | migration 012 |
| 11 | One-time backfill script for semantic index of pre-existing approved docs | `backend/scripts/backfill_semantic_index.py` |

---

## 🚨 Required human action before first external user

These can't be done in code — they need a Supabase Studio click, a procurement step, or a legal/compliance review.

### 1. Rotate the leaked Supabase service-role key

The key `eyJhbGciOiJIUzI1NiI…IsImlhdCI6MTc2MDMyMTc0Ng…` was committed to git history (October 2025). Even though it's removed from the working tree, anyone with read access to the repo can pull it from history. Rotate **before any external login is granted**.

> Supabase Studio → Project Settings → API → "Reset service_role key"

Update local `.env` files + any deployed environment variable stores after rotation. The old key remains valid until the new one is generated (no overlap window) so prepare deploy + dev-machine rollouts in advance.

### 2. Apply the production-readiness migrations

Two new migrations to run via Supabase SQL Editor:

| Migration | What |
|---|---|
| `backend/migrations/012_production_readiness.sql` | search_index_* columns, encounters.doctor_id, gp_invoices.workspace_id, patient registry index, push tracking columns on export_jobs |

Migrations 001–011 must be applied first.

### 3. Create the Supabase Storage bucket

> Supabase Studio → Storage → "Create bucket" → name `digitisation-exports`, **private** (no public access — the API proxies via the download endpoint after auth)

Without this bucket, generated FHIR bundles fall back to local disk and won't survive multi-instance deploys.

### 4. ATC source data licensing decision

The 119 ATC-coded NAPPI rows are stamped `atc_source='atcd-2026-04-25'` — a CC BY-NC-SA NonCommercial mirror. Pick a commercial path before invoicing:

- **BioPortal ATC** (CC-BY) — needs free API key
- **NLM RxNorm** (US public domain) — bigger one-time pull
- **WHOcc direct licence** — annual fee ~R10–30k

When the source lands, the 119 rows can be cleared via the queries documented in `backend/data/atc/NOTICE.md`, then `atc_backfill.py` re-run with `--atc-source <new-tag>`.

### 5. Decide on monitoring stack

No error tracking or perf metrics are wired today. Recommend Sentry (free tier covers small workloads) — backend SDK + frontend SDK, init via env var, ~30 min to wire.

### 6. Consent + data retention policy

The Type C workspace doesn't yet:
- Show a POPIA consent banner before pushing data via FHIR
- Implement a documented retention policy (how long do we keep validated extractions / bundles / embeddings?)
- Have a breach-notification process documented

These are legal/compliance work — recommend running them past a SA healthtech-experienced lawyer before the first paying customer onboards.

---

## ⚠️ Strongly recommended before broader commercial release

| # | Item | Why | Effort |
|---|---|---|---|
| 1 | Move FHIR bearer tokens / OAuth secrets to Supabase Vault | Today they're plaintext JSONB; redacted from API but still on disk | ~2-3 hr (needs Supabase Pro) |
| 2 | Mongo consolidation (TRACEABILITY 7) | Removes one DB from the stack | ~4-6 hr |
| 3 | BHF NAPPI MPP licence | Lifts NAPPI match rate from ~10% to ~70-90% on real prescribing data | Procurement |
| 4 | Patient EHR view of promoted data | `/patients/:id` should show diagnoses/vitals/meds from digitisation | ~45 min |
| 5 | LLM-based ICD-10 fallback (TRACEABILITY 1 Tier 2) | Recovers descriptions like "Arthrog", "Chest + Exigestion" | ~2-3 hr |
| 6 | Multi-doctor productivity analytics | Now feasible thanks to migration 012 (`encounters.doctor_id`) | ~1 hr |
| 7 | Sentry / OTel / structured logging | Currently no error tracking | ~2-3 hr |

---

## 📊 Production-readiness verdict (post-Sprint)

| Audience | Verdict | Outstanding gates |
|---|---|---|
| **Friendly design-partner practice** | ✅ **Ready** after rotating the leaked Supabase key + applying migration 012 + creating the Storage bucket | Steps 1-3 above (~30 min) |
| **First paying customer** | 🟡 Add Vault for credentials + LLM ICD-10 fallback + Patient EHR view | Plus most "strongly recommended" items |
| **Multi-customer commercial release** | 🔴 Add: BHF MPP licence + Mongo consolidation + monitoring + retention policy + multi-instance load testing | ~1-2 weeks beyond the friendly-customer state |

---

## 📋 Final pre-launch checklist (copy this into a deploy ticket)

- [ ] Rotated Supabase `service_role` key in Studio + updated all `.env` files / secret managers
- [ ] Ran `migrations/012_production_readiness.sql` in target Supabase project
- [ ] Created `digitisation-exports` Storage bucket (private)
- [ ] Verified `OPENAI_API_KEY` is set in deploy environment (semantic search depends on it)
- [ ] Verified `LANDING_AI_API_KEY` / `VISION_AGENT_API_KEY` is set (extraction depends on it)
- [ ] Decided on ATC source replacement path; either licensed or accepted "NC-licensed dev data" disclaimer with the customer
- [ ] Wired Sentry (or equivalent) — `SENTRY_DSN` env var → backend + frontend
- [ ] Confirmed POPIA consent flow exists for any data leaving the workspace
- [ ] Run `python scripts/backfill_semantic_index.py --workspace <ws>` if the workspace has pre-existing approved docs
- [ ] End-to-end smoke test in target workspace:
  - [ ] Upload a doc, validate, approve
  - [ ] Promotion summary shows real patient details + confidence pill
  - [ ] Search returns real results
  - [ ] Export → bundle generated → push to test FHIR endpoint succeeds
  - [ ] Re-approval is idempotent
