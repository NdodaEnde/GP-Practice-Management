# Session handoff — 2026-05-10 (continued)

> **Use this file when starting a fresh Claude Code session to pick up where the
> previous one left off.** Delete it after the next session is up to speed.

---

## Where we are right now

Two waves of work landed today on a shared theme: **the Type C Digitisation
workspace surfaces are now honest** — no fake stats, no sample data, no
hardcoded confidences, dead links wired up.

### Wave A — TRACEABILITY 6b/6c + UI surfaces 1 & 2 (committed earlier)

1. **TRACEABILITY 6b — ATC code backfill** *(partially shipped — 119 of 1,637)*
2. **TRACEABILITY 6c — Curated OTC supplement** *(shipped — 54 entries)*
3. **Analytics drug-class panel** (Charts Row 3 on `/analytics`)
4. **Validation panel NAPPI+ATC chip strip** (Medications tab)

### Wave B — Digitisation outstanding-work cleanup (this commit)

5. **Dashboard wired to real `/api/digitisation/dashboard`** — no more hardcoded
   page-credit / awaiting / accuracy numbers. Empty states are honest.
6. **Backend status fix**: `extracted` now counts toward awaiting validation
   (was being undercounted).
7. **44 hardcoded confidence values** stripped from EHRValidationPanel — fields
   without real LandingAI grounding now show `–` (missing) instead of fake `91%`.
8. **Export job tracking (Phase A)** — migration 008 + 3 endpoints + Export
   Centre UI swap (sample data → real history with empty state). Queueing
   button is wired; bundle generation deferred to Phase B.
9. **FHIR Connection Wizard skeleton (Phase A)** — migration 009 + 5 endpoints
   + new wizard page at `/digitisation/export/connect` (4-step rail, Step 01
   functional). Saved Connections table + default toggle. Export Centre's
   System Configuration card now reads from saved connections.
10. **Backend `/api/digitisation/nappi/lookup`** now returns `atc_class_desc`
    (used by the chip strip).

## Two things you must know about the data

1. **The ATC source data is CC BY-NC-SA NonCommercial.** Used for development
   only. Every backfilled row stamped `atc_source='atcd-2026-04-25'` for
   findability. Replace before commercial GA — see
   `backend/data/atc/NOTICE.md`.

2. **Curated OTC rows have synthetic IDs** like `CURATED-DEMAZIN-001`,
   `data_source='curated'`. When the BHF MPP licence lands, real NAPPI rows
   for these brands replace the curated placeholders.

## What's open / parked

| Item | Why parked | When to revisit |
|---|---|---|
| 226 review-pile rows (multi-candidate ATC) | User chose to skip; not blocking | Free recovery anytime |
| 1,292 unmatched NAPPI rows | Pure brand names; needs MIMS/SAEPI/BHF brand→INN data | When licence lands |
| **Phase B: FHIR bundle worker** | Half a day — generates real FHIR bundles, marks queued jobs success/failed, stores bundle_url | Next session |
| **Phase B: FHIR connection test + auth** | HEAD against `/metadata`, real OAuth/Basic credential storage in Supabase Vault | Next session |
| **Phase B: Wizard steps 2-4** (Auth, Resource Mapping, Test & Save) | Construction-card placeholders today | After Phase B server work |
| TRACEABILITY 6d (drug-drug interactions) | Now feasible thanks to 6b/6c + ATC infra | When user prioritises |
| Patient EHR medication tab class display | Skipped today | Anytime — small (~45 min) |
| Mongo consolidation | Big infra task | When time allows |

## Files added today

```
backend/migrations/006_atc_backfill.sql                     — schema (applied; in earlier commit)
backend/migrations/007_curated_otc_supplement.sql           — schema (applied; in earlier commit)
backend/migrations/008_digitisation_export_jobs.sql         — schema (applied)
backend/migrations/009_fhir_connections.sql                 — schema (applied)
backend/scripts/atc_backfill.py                             — matcher (in earlier commit)
backend/scripts/test_atc_backfill.py                        — 28 unit tests (in earlier commit)
backend/scripts/validate_curated_otc.py                     — curated CSV validator (in earlier commit)
backend/scripts/generate_curated_otc_sql.py                 — INSERT SQL emitter (in earlier commit)
backend/scripts/ATC_BACKFILL_README.md                      — runbook (in earlier commit)
backend/scripts/_atc_test_sample.csv                        — 15-row test fixture (in earlier commit)
backend/data/atc/WHO_ATC-DDD_2026-04-25.csv                 — WHO ATC index (in earlier commit)
backend/data/atc/WHO_ATC-DDD-combinations_2026-04-25.csv    — WHO combinations (in earlier commit)
backend/data/atc/NOTICE.md                                  — license + cleanup (in earlier commit)
backend/data/atc/curated_otc_starter.csv                    — 54 curated OTCs (in earlier commit)
backend/data/atc/run_2026-05-10/006_atc_backfill_data.sql   — Rx UPDATEs (in earlier commit)
backend/data/atc/run_2026-05-10/007_curated_otc_data.sql    — OTC INSERTs (in earlier commit)
backend/data/atc/run_2026-05-10/matched_*.csv               — review CSVs (in earlier commit)
backend/data/atc/run_2026-05-10/verify_atc.sql              — 8-test SQL suite (in earlier commit)
frontend/src/pages/DigitisationFHIRConnectionWizard.jsx     — new wizard page
```

## Files modified today

```
backend/server.py                                           — +ATC class agg in /analytics/medications (Wave A)
backend/app/api/digitisation.py                             — +atc_class_desc in /nappi/lookup, +exports endpoints, +fhir/connections endpoints, dashboard `extracted` count fix
frontend/src/pages/Analytics.jsx                            — +ATC Charts Row 3 (Wave A)
frontend/src/pages/DigitisationDashboard.jsx                — full rewrite to consume /api/digitisation/dashboard
frontend/src/pages/DigitisationExportCentre.jsx             — replaced sample history with real /exports + Saved Connection display + Queue button
frontend/src/components/groundtruth/EHRValidationPanel.jsx  — NAPPIBadge → chip strip (Wave A) + stripped 44 hardcoded confidences (Wave B)
frontend/src/components/groundtruth/EHRValidationPanel.css  — +nappi-curated/schedule/atc styles (Wave A)
frontend/src/services/api.js                                — +analyticsAPI.getMedications() (Wave A)
frontend/src/App.js                                         — +/digitisation/export/connect route
TRACEABILITY.md                                             — §6b/§6c marked partial/shipped (in earlier commit)
SESSION_HANDOFF.md                                          — replaced (this file)
```

## Tests

- **Python:** `cd backend && .venv/bin/python -m unittest scripts.test_atc_backfill -v` — 28/28 passing
- **SQL verification:** `backend/data/atc/run_2026-05-10/verify_atc.sql` — all 8 blocks pass
- **Endpoint smoke tests** (this session): Dashboard, Exports, FHIR Connections all return correct shapes
- **End-to-end:**
  - `/digitisation` → real dashboard data
  - `/digitisation/export` → empty history, Configure Connection link works
  - `/digitisation/export/connect` → wizard saves connections; Default toggling works
  - `/analytics` → ATC Charts Row 3 renders
  - `/digitisation/validation/<doc_id>` → NAPPI+schedule+ATC chip strip on Medications tab; missing-grounding fields show `–`

## Servers

```
backend  — http://localhost:8002 (FastAPI, restarted with --reload during this session)
frontend — http://localhost:3001 (CRA)
```

If both aren't running:

```bash
cd /Users/luzuko/GP-Practice-Management/backend && .venv/bin/uvicorn server:app --host 127.0.0.1 --port 8002 --reload
cd /Users/luzuko/GP-Practice-Management/frontend && PORT=3001 BROWSER=none npm run start
```

## Demo workspaces (unchanged)

| Workspace | Login |
|---|---|
| `typec-workspace-001` | `typec@surgiscan.com` / `password123` |
| `demo-gp-workspace-001` | `admin@surgiscan.com` / `password123` |

## Suggested next focus

**TRACEABILITY 6d (drug-drug interactions)** OR **Phase B FHIR work**.

- 6d: class-level DDI rules using ATC codes; reviewer-facing alerts in
  Medications tab. ~3-4 hr. Strategic — the natural completion of today's
  ATC work.
- Phase B FHIR: real bundle generation (queued → success + bundle_url),
  connection test (HEAD `/metadata`), credential storage. ~half a day+.
  Required for Type C to actually push data to a downstream EHR.

User signal at end of this session: ship the wizard skeleton, commit, stop.
