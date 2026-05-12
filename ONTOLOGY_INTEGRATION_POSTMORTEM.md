# Ontology Integration Pass — Post-Mortem

**Status — the framing in one sentence:** The ontology's structural integration is complete, and the integration pass surfaced a heterogeneous-identifier issue at the DB layer that needs to be resolved before the ontology's validators start running against production data.

---

## What shipped

- `backend/ontology/` — the full ontology package (Patient, Document, Consultation + base, enums, links, validators, actions), copied verbatim from `Ontology_starter/`.
- `backend/ontology/mappers/patient.py` — `hydrate_patient_from_row()`, a single function from Supabase `patients` row → validated `Patient` ontology object.
- `backend/app/api/ontology.py` — `ontology_router` with `GET /api/ontology/ping` and `GET /api/ontology/schema`. Mounted in `main.py` alongside the existing `gp_router`.
- `backend/app/api/gp_endpoints.py` — `get_patient_chronic_summary` refactored to hydrate the row through the ontology with a try/except fallback to the original inline-dict response. (Committed separately by the maintainer; see "What's deferred to the maintainer" below.)
- Verification harnesses: `verify_patient_mapper.py` (dict-in, Patient-out, 5 cases) and `verify_integration_endpoint.py` (FastAPI TestClient with a monkeypatched Supabase, 5 data-quality profiles, all PASS).
- `scripts/ontology_integration_verify.sh` — `capture` / `diff` against a running backend with `jq -S` canonical-key-sorted JSON.

The success criteria — JSON-equal-after-canonical-normalisation wire format, frontend unaffected, `/api/ontology/schema` serving `Patient.ontology_schema()` — were met. Confirmed under real load against three live patients through the production proxy chain (`:3001 frontend → :8002 server.py → :5001 main.py microservice`); responses were byte-identical between microservice-direct and proxy-mediated paths.

---

## Identifier strategy finding (the prize the pass produced)

### What we discovered

- `workspaces.id` and `tenants.id` are slug-style `TEXT` primary keys in the dev DB. Real values look like `typec-workspace-001`, `typec-tenant-001`. The `patients.workspace_id` and `patients.tenant_id` FK columns inherit this format.
- `patients.id` IS a UUID (verified: `25b83351-3450-471e-ae8b-9f5a5b90da18` and others parse cleanly). The identifier heterogeneity is per-entity, not global — Patient identity is a UUID, but Workspace/Tenant identity is a slug.
- The exact failure location in the mapper is `UUID(row["workspace_id"])` at [backend/ontology/mappers/patient.py](backend/ontology/mappers/patient.py). The mapper raises `ValueError: badly formed hexadecimal UUID string` before reaching any Patient validator, because `OntologyObject.practice_id: UUID` is declared on the base class.
- Consequence on dev data: **10/10 sampled patients fall through to the legacy fallback path.** All 10 emit the structured warning `Patient ontology hydration failed; serving legacy response` with `{patient_id, validation_errors, endpoint}` extras. None of the Patient validators (SA-ID DOB cross-check, deceased consistency, etc.) executes against any production row yet.
- The fallback machinery is working as designed: no 5xx responses, wire format preserved, frontend unaffected, every failure logged. The integration is sound; the ontology's validators just don't get to run.

### What we don't yet know

- **Whether the slug choice was deliberate or accidental.** Modern multi-tenant Postgres schemas usually use UUIDs for FKs precisely because slugs leak human-readable structure (e.g., `typec-workspace-001` is an obvious internal naming pattern). The slug convention here might be a considered choice (admin-friendly URLs, easier ops debugging) or might have happened because someone seeded the workspaces table with TEXT primary keys early and the rest of the schema accreted around that.
- **Whether the slug pattern extends to other tables we haven't touched.** A grep across migrations would show this quickly. `User.id` (referenced by Document.validated_by_user_id, promoted_by_user_id, etc., and by Consultation.practitioner_id) is the next one that matters — if Users are also slugs, every Document mapper and the eventual Consultation mapper face the same UUID/str conflict.
- **The migration cost if we moved to UUIDs everywhere.** Non-trivial: every FK across the schema, every URL path containing a workspace slug, every external-system integration that quotes a workspace ID would need a coordinated change. Possibly weeks of work spread across migrations + UI + observability.

### What it implies for the next plan

- **The slug fix is the first item on the ActionExecutor plan's prerequisites section.** The executor's first action is `PromoteDocumentToPatientRecord`. Its preconditions include "the document and target patient belong to the actor's practice." That check needs `practice_id` to round-trip cleanly DB row → ontology object → action precondition. Today it doesn't; the mapper raises before the precondition can even be evaluated.
- **The fix is a real design decision, not a one-line follow-up.** Loosening `OntologyObject.practice_id` from `UUID` to `str` touches: the JSON schema emitted by `ontology_schema()` (frontend codegen consequences), the FHIR exporter's reference-resolution logic, the link registry's "every link target is a UUID" invariant, the eventual audit log's `affected_object_id` GIN index (UUID arrays index differently to text arrays in Postgres), and the eventual ER work's round-trip semantics. It deserves its own thinking time and a deliberate call, not a reflex during executor work.
- **The decision tree before the executor plan can start writing audit log SQL:**
    1. Is the slug-style workspace_id deliberate or accidental?
    2. If deliberate → loosen `OntologyObject.practice_id` (and any other "Practice-typed" reference) to `str`, document why slugs are right for Workspace and UUIDs are right for Patient, accept the codegen/FHIR/index consequences.
    3. If accidental → schedule a DB migration to UUIDs for workspaces/tenants/users; the ontology stays as-is; the migration becomes a real-data correctness exercise.
    4. Either way, the ActionExecutor's `practice_id` round-trip story has to be settled BEFORE the audit log table is designed.

---

## Other findings worth recording

### gp_endpoints.py / the two-tier architecture surprise

The original plan assumed a single FastAPI backend. The reality is two-tier: `server.py` (front-facing on :8002, called "SurgiScan API") proxies `/api/gp/patient/{id}/chronic-summary` to `MICROSERVICE_URL/api/v1/gp/patient/{id}/chronic-summary` (default `localhost:5001`, where `main.py` runs). The refactor sits in the microservice; the frontend reaches it via the proxy.

The plan was right that `app/api/gp_endpoints.py:182-230` was the right file to refactor — it just didn't anticipate the proxy in between. Practical consequence for verification: real baselines have to be captured either through the proxy (which requires both servers running) or directly against the microservice. The synthetic verifier (TestClient + monkeypatched Supabase) sidesteps the runtime topology entirely.

### Patient field mapping gaps

Of Patient's 29 declared properties:
- **11 map directly** to existing patients columns (first_name, surname, dob → date_of_birth, id_number, contact_number → primary_phone, email, address → physical_address, plus id, workspace_id, created_at, updated_at).
- **3 are mapper-defaulted** with documented rationale: `biological_sex = UNKNOWN`, `identifier_type = SA_ID`, `status = ACTIVE`.
- **15 are None** because no corresponding DB column exists (title, middle_names, preferred_name, population_group, home_language, the 4 medical_aid_* structured fields, deceased_date, merged_into_patient_id, the 3 denormalised summary fields, deleted_at).

None of these caused validation failures — all 15 are Optional. The mapping is clean; the structural fit between the existing schema and Patient is high. The slug issue is the only hard failure.

### Validation failures dominated by one pattern

All 10 sampled rows failed at the same step: `UUID(row["workspace_id"])`. None reached the SA-ID or deceased-consistency validators. **This is good news for cleanup**: the slug fix unblocks all 10. We won't need separate cleanup migrations for SA-ID quality, DOB sentinels, or other data issues *until after* the slug fix lands and the next layer of validators starts firing. Then we'll see the next wave.

### Normalisations observed in the synthetic verifier

`verify_integration_endpoint.py` tested 5 data-quality profiles. Four produced byte-identical responses between the legacy and ontology serialisation paths; one produced a normalisation-only diff: `identifier_number` trailing whitespace stripped by the SA-ID `field_validator` (`'8503140001087 '` → `'8503140001087'`). No date-format shifts, no number-vs-string type changes, no key omissions appeared. Caveat: the synthetic rows used canonical formats by construction — once the slug fix unblocks ontology hydration of real production data, expect further normalisation classes (likely `date_of_birth` if Supabase ever returns `T00:00:00`-suffixed strings, and `last_updated` going from `null` to a populated ISO timestamp via the mapper's created_at fallback). Document each new class as it surfaces.

### Time spent (vs. half-day estimate)

The half-day estimate covered the code changes themselves. Actuals:
- Code (commits 1-5 + verification helpers): ~3.5 hours.
- Live verification against real DB (starting the microservice, running probes, classifying failures): ~30 min.
- Identifier strategy finding investigation + this post-mortem: ~45 min.

Total: ~4.5 hours. The half-day estimate was right for code; the live verification + finding analysis added the extra hour. Worth it — the slug discovery would have surfaced during ActionExecutor work otherwise, and would have cost more there.

### Estimate refinement for Document + Consultation passes

- **Document mapper** will hit the slug issue on Document.practice_id (inherited from base) — same fix applies. It will also touch `User.id` for the four user-reference fields (uploaded_by_user_id, validated_by_user_id, promoted_by_user_id, rejected_by_user_id) — pending the slug check on Users.
- **Consultation mapper** is structurally similar to Patient — clean field mapping, single slug-issue blocker. The semantic narrative fields (chief_complaint, history, examination, assessment, plan) have no DB column yet (the existing schema lumps them into `gp_notes` or similar JSONB); they'll default to None.
- Estimate: each is ~half a day of code once the slug issue is resolved. Without the slug fix first, neither will hydrate any real row.

---

## What's deferred to the maintainer

- **`backend/app/api/gp_endpoints.py` refactor.** The integration's chronic-summary endpoint edits sit in the working tree, not yet committed, because the file already had ~580 lines of unrelated pre-existing uncommitted state from prior sessions. The maintainer reviews the surrounding edits and commits the chronic-summary refactor at a moment of their choosing. The new ontology code on `main` is structurally complete but functionally dormant until that commit lands.
- **`baselines/` in `.gitignore`.** Not added in this pass — `.gitignore` was also in the pre-existing uncommitted state.

---

## Update — 2026-05-12 — slug fix landed; next data-quality layer surfaced

The slug-identifier finding was resolved by loosening `OntologyObject.practice_id` from `UUID` to `str` (commit `0399842`). Rationale: the application has always used strings (per `app/api/workspaces.py` and 20+ hardcoded references); FHIR `Resource.id` is a constrained string, not specifically UUID; a future DB migration to UUID PKs would store UUID-shaped strings, which the declaration accepts unchanged. Investigation confirmed the original schema (`setup_supabase.sql`) uses `TEXT PRIMARY KEY` across all 9 tables — the slug pattern is deeply intentional in the codebase. The ontology layer was over-specifying.

**Hydration rate against real dev DB jumped from 0/32 to 4/32 patients.** The 4 that hydrate have valid SA IDs with matching DOBs. The remaining 28 fall back to legacy for these reasons:

- **24× Luhn checksum failures** — likely data-entry typos in the `id_number` column. Each row was captured at intake without intake-side validation.
- **3× invalid citizenship digit** — position 11 of the SA ID is not 0 or 1. Either corrupt data or unusual real IDs (worth a manual check on a couple before treating as cleanup-only).
- **1× DOB / SA-ID mismatch** — the stored `dob` disagrees with the date encoded in the `id_number`.

**Decision: validator stays strict; this is correct behaviour.** The fallback machinery handles the bad-data cases (no 5xx, wire format preserved, structured warnings logged with `patient_id`). The 28 fallback patients are now visible as data-quality findings to clean up over time, rather than being silently served as if valid.

**Implication for the next plan (ActionExecutor):** the slug resolution is done; the executor's `practice_id` round-trip story works. The data-quality layer surfaced here is its own work — a backfill task to repair Luhn-failing SA IDs, flag citizenship-digit anomalies for review, and resolve DOB mismatches. NOT blocking the executor, but worth a follow-up task once executor work begins (the executor's `audit_log` will start capturing per-action warning frequency, which makes "find me all patients whose data triggers the SA-ID validator on every read" trivially queryable).

## What to read first when picking up the ActionExecutor plan

1. This document — the slug finding (now resolved) is captured; the data-quality finding is next.
2. [ONTOLOGY_ROADMAP.md](ONTOLOGY_ROADMAP.md) — Phase 2 framing.
3. [backend/ontology/actions/promote_document.py](backend/ontology/actions/promote_document.py) — the existing illustrative action declaration, the template the executor instantiates.
4. [backend/ontology/mappers/patient.py](backend/ontology/mappers/patient.py) — the mapper's docstring captures the full list of deferred columns and the rationale for each.
