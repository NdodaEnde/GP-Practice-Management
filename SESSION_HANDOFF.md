# Session handoff — 2026-05-10 (production-ready)

> **Use this file when starting a fresh Claude Code session to pick up where the
> previous one left off.** Delete it after the next session is up to speed.

---

## Where the platform is right now

**Type C Digitisation is production-ready code-side.** A friendly design-partner
practice can be onboarded today; the per-customer setup is ~30 minutes.

### What a user actually experiences

| Step | URL | What happens |
|---|---|---|
| Upload | `/digitisation/documents` | PDFs land in Supabase Storage `medical-records` |
| AI extraction | (background) | LandingAI ADE → `gp_validation_sessions.extractions` JSONB with per-field grounding metadata |
| Review | `/digitisation/validation/:id` | PDF + extracted EHR side-by-side; NAPPI+ATC chips, ICD-10 chips, click-to-source PDF highlighting; every edit audit-logged |
| Approve | (modal) | Patient match-confirmation modal forces explicit pick (existing patient OR create new) before any structured data lands |
| Promote | (server-side, sync) | patients, encounters, diagnoses, vitals, allergies, prescriptions + items written to relational tables. ICD-10 + NAPPI/ATC inferred at promotion time. Idempotent on re-approval. |
| Index | (background) | OpenAI text-embedding-3-large (1536 dims) → pgvector via `document_embeddings`. Failures persisted on `digitised_documents.search_index_*`. |
| Search | `/digitisation/search` | Plain-English query → cosine-ANN ranked snippets; click-through to source doc. Rate-limited 30/min/user. |
| Configure FHIR | `/digitisation/export/connect` | 4-step wizard with live `GET /metadata` test; bearer tokens redacted from API responses |
| Export | `/digitisation/export` | Worker generates FHIR R4 Bundle → Supabase Storage `digitisation-exports` → auto-POSTs to configured endpoint. Push status tracked separately from bundle generation. |

### Today's commit arc (10 commits)

```
0f37fa8  docs: §10 FHIR push bundle profile per downstream EHR
0133648  docs: key already rotated 2025; migration 012 applied
757e32e  feat: patient match-confirmation modal
61ee44d  feat: production-readiness pass (security/observability/Phase C/schema)
25b0e06  feat: semantic search v1 (TRACEABILITY §9)
fb5267e  docs: §9 untransferred (now obsolete)
3b57811  docs: §1 lexicon + §6f promotion
00ee562  feat: Phase B FHIR + structured-data promotion
d4168a5  feat: Type C cleanup + FHIR Wizard skeleton
52d8227  feat: ATC code backfill (TRACEABILITY 6b/6c)
```

## Production-readiness gates — all closed

| Gate | Status |
|---|---|
| Hardcoded JWTs removed from 12 backend scripts | ✅ Shipped (`61ee44d`) |
| Supabase service-role key | ✅ Already rotated by owner (2025) |
| FHIR bearer tokens redacted from API responses | ✅ Shipped |
| Patient match-confirmation modal (no silent wrong-patient promotion) | ✅ Shipped (`757e32e`) |
| Indexer / promoter failure visibility | ✅ Persisted on `digitised_documents.search_index_*` + `validation_edit_log.metadata` |
| /search rate limiting (30/min/user) | ✅ Shipped |
| FHIR bundle storage on Supabase Storage | ✅ `digitisation-exports` bucket created + verified |
| Schema completion (encounters.doctor_id, gp_invoices.workspace_id) | ✅ Migration 012 applied |
| Auto-POST FHIR bundle to configured endpoint | ✅ Shipped (per-EHR bundle shaping is §10 deferred) |
| Backfill script for pre-existing approved docs | ✅ `backend/scripts/backfill_semantic_index.py` |
| Production checklist | ✅ `PRODUCTION_CHECKLIST.md` |

## What's still deferred (TRACEABILITY-tracked)

| # | Item | Trigger |
|---|---|---|
| **§1 Tier 2** | LLM-based ICD-10 fallback | Reviewer-edit rate >20% in `validation_edit_log` |
| **§6a** | BHF NAPPI MPP licence | Procurement; lifts NAPPI match ~10% → ~70-90% |
| **§6d** | Drug-drug interactions (now feasible thanks to ATC infra) | Clinical lead available to review |
| **§7** | Mongo consolidation (~5-10 endpoints still on Mongo) | Anytime — tech debt |
| **§8** | ML risk scores / X-ray AI panels | First Beta-tier customer |
| **§10** | FHIR push bundle profile per downstream EHR | First real customer endpoint |
| Patient EHR view of promoted data (`/patients/:id`) | Small UI ~45 min | Anytime |

## What's data-bottlenecked vs algorithm-bottlenecked

| Today's leftover | Real cause | Fix |
|---|---|---|
| Many extracted meds have no NAPPI/ATC | nappi_codes table is small (173 rows: 119 Rx + 54 OTC) | BHF MPP licence (~30k rows) — no code change needed |
| Some diagnoses unmapped (Arthrog, Chat Nais) | Cryptic OCR / handwritten abbreviations | Either expand the lexicon or LLM fallback (§1 Tier 2) |
| ATC source data is CC BY-NC-SA | NonCommercial mirror (atcd) | Replace 119 `atcd-2026-04-25`-tagged rows when commercial licence lands |

## Onboarding a new customer (~30 min)

1. **Provision workspace** in Supabase (tenants + workspaces + practice_capabilities row + first user)
2. **Apply migrations 001–012** if it's a new project (paste each into SQL editor)
3. **Create Storage buckets** (private): `medical-records` + `digitisation-exports`
4. **Decide ATC source** if commercial GA — replace dev-tagged rows per `backend/data/atc/NOTICE.md`
5. **Optional:** configure their downstream FHIR endpoint via `/digitisation/export/connect`

## Demo workspaces (unchanged)

| Workspace | Login |
|---|---|
| `typec-workspace-001` | `typec@surgiscan.com` / `password123` |
| `demo-gp-workspace-001` | `admin@surgiscan.com` / `password123` |

## Servers

```
backend  — http://localhost:8002 (FastAPI, --reload)
frontend — http://localhost:3001 (CRA)
```

## Suggested next focus (when you come back)

In order of leverage:

1. **TRACEABILITY §6d (drug-drug interactions)** — strategic capstone. Patients now have ATC-coded medication histories; class-level DDI rules + reviewer alerts in the Medications tab. ~3-4 hr. Adds *actual safety value* to the platform — not just "we digitise records" but "we catch dangerous combos."
2. **Patient EHR view of promoted data** — `/patients/:id` doesn't yet read from the structured tables for digitisation-sourced patients. ~45 min UI work.
3. **§1 Tier 2 LLM ICD-10 fallback** — only if reviewers start editing codes a lot. Triggered by data, not speculation.
4. **§7 Mongo consolidation** — tech debt; pure cleanup. ~4-6 hr.

User signal at end of this session: **production-ready stop**.
