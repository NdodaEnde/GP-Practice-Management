# Session handoff — 2026-05-10 (final)

> **Use this file when starting a fresh Claude Code session to pick up where the
> previous one left off.** Delete it after the next session is up to speed.

---

## What this session accomplished

Type C Digitisation now has a **complete data flow**: PDF → AI extraction →
reviewer validation → **structured EHR tables** → analytics + downstream
FHIR push. Three commits over two days landed it.

### Wave 1 (committed earlier — `52d8227`)
TRACEABILITY 6b/6c: ATC code backfill (119 Rx + 54 OTC) + matcher infra +
WHO ATC index + tests + verification SQL.

### Wave 2 (committed earlier — `d4168a5`)
Surface honesty pass: Dashboard wired to API, EHR confidence cleanup,
Export job tracking (Phase A), FHIR Connection Wizard skeleton.

### Wave 3 (this commit)
**Phase B FHIR work** + **structured-data promotion** — the substantive
plumbing that makes everything downstream possible.

1. **FHIR bundle worker** — POST /exports queues a job; BackgroundTasks
   fires the worker; worker pulls validated extractions, runs them through
   `fhir_export.py` mappers per-document, writes a real FHIR R4 batch
   Bundle to `backend/storage/exports/`, marks the job `success` with a
   `bundle_url`. Download endpoint streams `application/fhir+json`.
   Smoke-tested: 1 doc → 35KB FHIR bundle with 1 Patient + 9 Conditions +
   36 MedicationStatements + 13 Encounters.
2. **Real connection test** — replaces the Phase A stub with a proper
   `GET {fhir_url}/metadata` probe. Records `last_test_ok` /
   `last_test_error` on the connection row. Verified against the HAPI
   public sandbox.
3. **Wizard Steps 02-04** — Authentication form (none / bearer; basic /
   OAuth / SMART tagged Phase C), Resource Mapping (toggleable categories
   stored on the connection's metadata), Test & Save (summary + run-test
   + commit).
4. **Migration 010** — fixes the §10c blocker by converting `diagnoses`,
   `vitals`, `allergies` `workspace_id` / `tenant_id` / `patient_id` /
   `encounter_id` from UUID → TEXT to match the rest of the schema.
   Adds source / source_document_id / hba1c / blood_glucose_fasting
   columns. Existing UUID values become TEXT, no data loss.
5. **Migration 010b** — adds `encounters.source_document_id` for promoter
   idempotency.
6. **`extraction_promoter.py`** — idempotent JSONB → structured tables
   service. Match-or-create patient (by SA ID number, fallback to
   surname+dob), one encounter per consultation date, per-category
   writers for allergies / diagnoses / vitals / prescriptions +
   prescription_items. Wipe-and-reinsert keyed on `source_document_id`
   so re-approving a doc never duplicates. Handles digitised_documents
   FK back-link cleanly.
7. **/approve wired to promoter** — every document approval now
   promotes the validated extractions into the structured tables. The
   document's `patient_id` + `encounter_id` get linked. Promotion
   summary is returned in the response and persisted to the audit log.
8. **Validation History Drawer** renders a green "Promoted to EHR"
   card on `approve` events showing per-category counts, plus an
   `inferred` count for icd10/nappi.
9. **Inference layer in the promoter:**
   - **ICD-10:** curated SA-GP abbreviation lexicon (URTI, HPT, DM, OA,
     etc) → ICD code, with a fuzzy fallback that's tightened to avoid
     false positives on short ambiguous abbreviations.
   - **NAPPI/ATC:** at promotion time, looks up `medication_name`
     against `nappi_codes` (brand or generic). When matched, copies
     `nappi_code`, `atc_code`, `generic_name` onto the prescription
     item. Cached per-promotion run.

## Smoke-test snapshot (typec workspace, demo doc)

```
Patient: MAMELLO MOTSOENENG (id 9102030347687) — created
Encounters:                  16  (one per consultation date 2023-2025)
Diagnoses:                    9  (6 with ICD-10 codes from inference)
Vitals:                       5  (HR + BP across visits)
Allergies:                    0  (chart had none)
Prescriptions:               10  (one per visit)
Prescription items:          36  (4 NAPPI/ATC matched, mostly Paracetamol)

ICD-10 inferred:  6 / 9
NAPPI inferred:   4 / 36 (data-bottlenecked; lifts to 70%+ with BHF MPP licence)
```

Re-approval is idempotent — second run produces identical counts, no
duplicates.

## What's data-bottlenecked vs. algorithm-bottlenecked

| Today's leftover | Real cause | Fix |
|---|---|---|
| Many extracted meds have no NAPPI/ATC | nappi_codes table is small (173 rows) | Wait for BHF MPP licence (~30k rows) — no code change needed |
| Some diagnoses unmapped (Arthrog, Chat Nais) | Cryptic abbreviations / typos in source PDF | Either expand the lexicon or LLM-based ICD-10 fallback (TRACEABILITY 5) |
| ATC source data is CC BY-NC-SA | NonCommercial mirror | Replace 119 `atcd-2026-04-25`-stamped rows when commercial licence lands |

## What's open / parked for next session

| Item | Notes |
|---|---|
| **TRACEABILITY 6d (drug-drug interactions)** | Now feasible — patients have ATC-coded medication histories. Class-level DDI rules + reviewer alerts. ~3-4 hr. |
| **Phase C FHIR push** | Today the bundle is downloadable; auto-POST to the configured endpoint is the polish. Needs Vault for credential storage. ~half day. |
| **226 review-pile rows from Wave 1** | Manual disambiguation per row → lifts ATC coverage on existing nappi_codes. ~30-60 min. |
| **Patient EHR view of promoted data** | The data is now structured but `/patients/:id` page doesn't read from `gp_validation_sessions` to show the doc-of-truth lineage. UI surface 3 from earlier. ~45 min. |
| **Mongo consolidation** | TRACEABILITY 7. Unrelated tech debt. ~4-6 hr. |

## Files in this commit

**New:**
```
backend/app/services/digitisation_export_worker.py     — Phase B FHIR bundle worker
backend/app/services/extraction_promoter.py            — Promotion service
backend/migrations/010_extraction_promotion_schema.sql — UUID/TEXT schema fix
backend/migrations/010b_encounters_source_doc.sql      — Encounter idempotency
frontend/src/components/groundtruth/ValidationHistoryDrawer.jsx — promotion summary card (was untracked; included)
```

**Modified:**
```
backend/app/api/digitisation.py                          — exports endpoints + FHIR connections + real /metadata test + BackgroundTasks worker trigger + download endpoint + approve_validation promoter wiring
frontend/src/pages/DigitisationExportCentre.jsx          — Phase B download button, default conn display
frontend/src/pages/DigitisationFHIRConnectionWizard.jsx  — Steps 02-04 functional (auth + resource mapping + test+save)
SESSION_HANDOFF.md                                       — replaced
```

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

If both aren't running:
```bash
cd /Users/luzuko/GP-Practice-Management/backend && .venv/bin/uvicorn server:app --host 127.0.0.1 --port 8002 --reload
cd /Users/luzuko/GP-Practice-Management/frontend && PORT=3001 BROWSER=none npm run start
```

## End-to-end demo path (works today)

1. Login as typec → `/digitisation` shows real KPIs.
2. Upload a PDF; wait for status → `extracted`.
3. Open in Validation Queue → review → **Approve**.
4. History drawer shows: edits, AI baseline, **Promoted to EHR** card with
   per-category counts.
5. Patient + encounters + diagnoses + vitals + medications now in the
   structured tables. Querying any class (J chapter, ATC C09AA*, etc)
   returns the promoted rows.
6. Configure a FHIR Connection (HAPI sandbox) → run real `/metadata` test.
7. Export Centre → Queue → wait ~1s → **Download** the FHIR bundle.

## Suggested next focus

**TRACEABILITY 6d (drug-drug interactions)** — biggest strategic capstone.
The promoter has built the substrate (every patient has an ATC-coded
medication history); the DDI checker is now practical. Reviewer-facing
alerts in the Medications tab.

Failing that, **Phase C FHIR push** to actually send bundles to the
customer's EHR endpoint instead of letting them download.
