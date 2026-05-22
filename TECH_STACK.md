# SurgiScan — Production tech stack (Essential / digitisation tier)

What to subscribe to actually run the platform in production. Grounded in
what the code uses — not a generic list. Pricing is a **model + ballpark**;
confirm current numbers on each vendor's page.

## REQUIRED — you need accounts for all of these

| # | Service | What it does here | Plan | Pricing model | Env vars |
|---|---------|-------------------|------|---------------|----------|
| 1 | **Supabase** (Pro) | Postgres DB + `pgvector` (semantic search) + Storage (scans & export bundles). Your PROD project `veuwldlkunetbeqgxptc` already exists. | **Pro** (~US$25/mo + usage) — Pro needed for backups, no auto-pause, scale | Flat base + usage | `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `DATABASE_URL` |
| 2 | **Render** | Hosts the backend (Docker web service) + frontend (static site). One blueprint, both services. | Backend: **Starter** (~US$7/mo) → Standard as load grows. Frontend static: **free**. | Flat per service | — (set the secrets here) |
| 3 | **LandingAI** | The document parse/extract engine (OCR + structured extraction). Core to digitisation. | Per their plan / API quota | **Usage-based** (per page/doc) | `LANDING_AI_API_KEY`, `VISION_AGENT_API_KEY` |
| 4 | **OpenAI** | `text-embedding-3-large` embeddings powering semantic search. | Pay-as-you-go API | **Usage-based** (per token; embeddings are cheap) | `OPENAI_API_KEY` |
| 5 | **Domain + DNS** | Customer-facing URL (e.g. `medicdata.co.za` / `app.surgiscan.co.za`). You likely already own this. | Registrar of choice | Annual | — (point DNS at Render) |

That's the whole runtime stack. Notably **not** needed:
- ~~MongoDB~~ — legacy; the digitisation tier is Supabase-only. (See "Pre-deploy fix" below — the app still *references* `MONGO_URL` at boot.)
- ~~Separate parsing microservice~~ — legacy; digitisation calls LandingAI directly.
- ~~PayFast/Paystack~~ — v1 billing is **manual/invoiced**; no gateway needed yet.

## RECOMMENDED (soon, not blocking launch)

| Service | Why | Pricing |
|---------|-----|---------|
| **Transactional email** (Resend / Postmark / AWS SES) | Password-reset emails + delivering login details to new practices. Concierge hand-off is manual today, so this is a quality-of-life upgrade. | Free tier → usage |
| **Sentry** (or Render's log drains) | Backend error monitoring / alerting in prod. | Free tier → paid |

## FUTURE (only when you move past concierge onboarding)

| Service | Why |
|---------|-----|
| **PayFast** (reconcile vs the Paystack references in the entitlement model) | Self-serve billing / auto-charging. Manual invoicing covers first customers. |

## ✅ MongoDB dependency removed (done 2026-05-22)
Mongo is now **optional** — `server.py` boots with no `MONGO_URL` (a null-safe
stub no-ops the legacy Mongo-backed endpoints). So production needs **no Mongo**
and the deploy boots clean with the env above. Also removed: the dead
`call_microservice_parser` + `MICROSERVICE_URL`, and the unused
`app/services/database.py` module. The legacy Professional features that used
Mongo (reception queue, AI-scribe transcript storage, marketing leads, legacy
audit) were NOT deleted — they have live frontend pages — and simply go dormant
without Mongo; set `MONGO_URL` later if you revive them.

## One-time / dev-only (no subscription)
- **Java 17+** + the HL7 FHIR `validator_cli.jar` — used only to validate FHIR
  exports during development/CI, not at runtime.
