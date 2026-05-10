# Traceability & Deferred Work

> *"hallucination is the real thing"* — guiding principle.

Doctors will trust SurgiScan only if every AI-derived value is traceable: was it
extracted verbatim from the source, was it inferred by an LLM, what confidence,
which chunk of the PDF supports it, who reviewed it. This document captures
both the **principles** we commit to and the **deferred work** required to make
those principles fully real.

---

## Why this matters strategically — validation is the substrate

The validation work we've done so far isn't just about getting today's documents
right; it's the foundation every downstream module reads from. If a code is
wrong here, it's wrong everywhere it gets aggregated.

| Validation today produces | Module 02 Analytics consumes | Module 03 Clinical AI consumes |
|---|---|---|
| Validated ICD-10 codes per visit | Chronic-disease cohorts, comorbidity networks, prevalence by region | Differential-diagnosis priors, "patients like this one" matching |
| Validated NAPPI codes per script | Drug spend, generic/brand mix, formulary compliance, prescribing patterns | Drug-drug interaction flags, alternative-therapy suggestions |
| Combined over time | Adherence by condition, cost-per-condition, treatment effectiveness | Predictive: "this combination of meds + HbA1c trajectory → likely outcome" |
| Reviewer edits + audit log | Quality signal — which AI extractions get corrected most often | Active-learning signal to retrain the extractors themselves |

The "Demazin gap" (item 6a below) is exactly the kind of issue that compounds:
a missing OTC today becomes a wrong drug-interaction alert tomorrow becomes a
missed safety signal six months later. That's the whole reason this document
exists — every gap gets its trigger written down so it surfaces at the right
moment, not after a doctor has already lost trust.

---

## Principles (non-negotiable)

1. **Provenance per field.** Every extracted value records *how* it came to be:
   `verbatim` (lifted directly from the source text), `inferred` (LLM mapped
   from related text — e.g., ICD-10 code derived from a written diagnosis),
   `manual` (reviewer typed/edited it).

2. **Validate inferred values against authoritative datasets.** Every code that
   the LLM produces (ICD-10, NAPPI, ICPC, FHIR codes, etc.) is cross-checked
   against a reference table before it reaches the reviewer. Failed validations
   are flagged, never silently accepted.

3. **Fail closed, not open.** When a lookup endpoint is unreachable, mark the
   value as unverified — never assume it's correct. Reviewer should see the
   gap, not get a false-green.

4. **Source-chunk tracing.** Every extracted field links back to the chunk(s)
   in the parsed PDF that supports it. Click a field → highlight its source
   on the PDF.

5. **Append-only edit log.** Every reviewer edit is recorded with `who`,
   `when`, `from`, `to`, `field_path`. Approved records carry both the
   original AI value AND the final approved value. Forever.

6. **No silent re-runs of the AI pipeline.** LandingAI parse + extract are
   called exactly ONCE per document at upload time. Re-extraction requires an
   explicit, audited admin action (`POST /api/digitisation/documents/{id}/reprocess`).

---

## Deferred work

Each item lists **what**, **why deferred**, **trigger to revisit**, and
**implementation hint**. Prioritise by trigger, not by appearance order.

### 1. ICD-10 inference — *partially shipped 2026-05-10*

Two-tier inference. Tier 1 (lexicon) is live; Tier 2 (LLM) is still ahead.

#### Tier 1 — SA-GP abbreviation lexicon — *shipped 2026-05-10*

- **What.** Curated map of common SA primary-care shorthand
  (URTI → J06.9, HPT → I10, DM → E11.9, OA → M19.9, …) used by the
  promoter at approval time to assign ICD-10 codes when LandingAI
  extracted a description but no code. Lives in
  `backend/app/services/extraction_promoter.py::ICD10_ABBREVIATIONS`.
- **Status.** ~70 entries. On the typec demo doc this lifts diagnoses-
  with-codes from 0/9 → 6/9. Tier 2 fuzzy fallback (ilike against
  `icd10_codes.who_full_desc`) is constrained to ≥10-char or multi-
  word descriptions to avoid short-abbreviation false positives like
  `Arthrog → Q74.3 (arthrogryposis multiplex congenita)`.
- **Codes are validated against the live `icd10_codes` table** at
  lookup time — entries that point at codes the table doesn't carry
  silently fall through (no broken FK).
- **Maintenance task.** The lexicon is intended to grow as production
  documents surface new abbreviations. Reviewers should append entries
  to `ICD10_ABBREVIATIONS` when they edit a NULL `code` field on the
  patient EHR. A future enhancement could promote frequent reviewer-
  applied codes into the lexicon automatically (mining
  `validation_edit_log`).
- **Known unmapped on demo doc:** "Arthrog", "Chest + Exigestion",
  "Chat Nais" — cryptic OCR / handwriting artefacts. The reviewer step
  on the patient EHR will catch these.

#### Tier 2 — LLM-based fallback — *deferred*

- **What.** When neither the lexicon nor the constrained fuzzy match
  produce a code, fall back to an LLM call (Claude / GPT-4o) that
  picks the best ICD-10 code from `icd10_codes` given the description.
- **Why deferred.** Tier 1 covers the high-frequency cases for free;
  Tier 2 burns API credits per row. Worth it once Tier 1 stabilises
  and the residue is genuinely cryptic.
- **Trigger to revisit.** When `validation_edit_log` rows show >20%
  of approved diagnoses had their code edited by reviewers — the
  lexicon isn't keeping up and an LLM fallback would lift recovery.
- **Implementation hint.** `POST /api/digitisation/icd10/suggest
  {description: str}` → Claude prompt constrained to the SA
  `icd10_codes` table; validate each suggestion via `/icd10/validate`;
  return top 3 with confidence. Wire into the promoter as Tier 3
  (after lexicon and fuzzy).

### 2. Per-field confidence scores

- **What.** The EHR validation panel currently shows hardcoded confidence
  values (95%, 93%, 91%...) per field. They look real but they're cosmetic.
  Real confidence has to come from the extraction pipeline.
- **Why deferred.** LandingAI ADE doesn't expose per-field confidence by
  default. Either (a) ask LandingAI for it via their newer API surface, or
  (b) compute it heuristically (presence of supporting chunk text, value
  validates against reference tables, etc.).
- **Trigger to revisit.** When a doctor asks "what does that 91% mean?" — the
  honest answer today is "nothing, it's a placeholder." That's a trust killer.
- **Implementation hint.** Store confidence in `gp_validation_sessions.confidence_scores`
  (column already exists). Surface via the `/api/digitisation/validation/{id}`
  response. Frontend already wired to read per-field confidence — just needs
  real numbers behind it.

### 3. Source-chunk tracing per field

- **What.** Click a field in the right panel → highlight the chunk(s) on the
  PDF that supplied that value. Today the panel does the reverse (PDF chunk
  click → switch to Parsed View) but field-to-chunk is heuristic
  (token-match search), not deterministic.
- **Why deferred.** Requires the extract step to track which input chunks
  contributed to each output field. LandingAI ADE may or may not expose this
  in extract output — needs investigation.
- **Trigger to revisit.** First reviewer who asks "where on the page did you
  get that ID number from?" — they need to verify against the source.
- **Implementation hint.** Either (a) modify extract prompt to require chunk
  IDs in output JSON; (b) post-hoc fuzzy match field values against chunk
  texts and persist the mapping. Field-path → chunk-id list goes into the
  validation session payload.

### 4. Append-only edit log — *shipped 2026-05-07 (backend), pending migration 005*

- **What.** Every reviewer save / approve / reject writes append-only rows to
  `validation_edit_log`. /save computes a per-field diff against the prior
  extractions and logs one row per changed leaf. /approve and /reject log
  whole-doc actions with optional notes.
- **Status.** Backend wiring complete. Migration 005 written. Once the
  migration runs, every action is captured forever.
- **Endpoint:** `GET /api/digitisation/validation/{id}/history` — returns
  the original (frozen AI baseline), the approved/working extractions, and
  the full audit log.
- **Frontend follow-up:** render a "history" sidebar on the validation
  panel showing the timeline of edits.

### 5. Original vs approved values preserved — *shipped with #4*

- **What.** New `extractions_original JSONB` column on
  `gp_validation_sessions`. Snapshot of the AI's first output at extract
  time, NEVER modified afterward. The existing `extractions` column remains
  the live / approved version. Together they answer "what did the AI say
  vs what did the reviewer approve."
- **Status.** Backend wiring complete (gp_processor populates it on session
  creation; graceful fallback if column is missing). Surfaced via `/history`
  endpoint as `original`.

### 6. NAPPI lookup endpoint — *shipped 2026-05-07; coverage gap below*

- **What.** Validate extracted drug names against the SA NAPPI reference,
  surface NAPPI code + brand + generic + strength + schedule in the
  Medications tab badge.
- **Status.** Shipped. `GET /api/digitisation/nappi/lookup?drug_name=X` and
  `GET /api/digitisation/nappi/search?q=X` are live. Wired through the
  groundtruth adapter.

### 6a. NAPPI dataset coverage gap (CRITICAL for Analytics module)

- **What.** The current `nappi_codes` table has only **1,637 rows** vs the
  full SA NAPPI master (BHF MPP) of ~30,000-50,000 items. The subset is
  heavily skewed toward Schedule 3 (980 rows / 60%). OTC schedules total
  just 14 rows: S0=3, S1=7, S2=4. Common OTC products (Demazin syrup,
  Pseudoephedrine-based cold/flu meds, common antacids, vitamins, etc) are
  absent. Even the **active ingredients** of common OTCs (Pseudoephedrine,
  Brompheniramine, Chlorpheniramine) return 0 rows.
- **Why deferred.** Existing dataset works for the prescription path which
  is the v1 demo. Reviewer simply sees "No NAPPI" red badge for OTC drugs
  and can manually flag — no crash, no false positive.
- **Trigger to revisit.** Before Module 02 (Advanced Clinical Analytics)
  goes live. Without OTC coverage:
    - drug-spend analytics under-counts by however much patients spend OTC
    - drug-drug interaction alerts miss OTC↔Rx interactions (e.g.
      Pseudoephedrine raises BP in patients on antihypertensives)
    - generic-vs-brand substitution analysis impossible for OTC
    - "what are GPs really prescribing for cough?" is unanswerable
- **Implementation hint.** The long-term answer is the full BHF Master
  Procurement Plan (NAPPI MPP). It is **commercially licensed** — a founder /
  ops procurement step:
    1. Contact Board of Healthcare Funders SA (https://www.bhfglobal.com)
    2. Sign a data licensing agreement
    3. Pay annual fee (typically R10–30k/year, varies by seat / practice count)
    4. Quarterly updates via their portal
  Engineering cannot acquire this independently. Do **not** scrape any
  third-party source as a workaround — breaches the BHF terms and exposes
  the company to copyright + contract liability later.

  In parallel with the BHF conversation, three things we CAN do without that
  licence to meaningfully close the gap. Each is a separate deferred item
  below (6b / 6c / 6d).

### 6b. ATC code backfill for existing NAPPI rows — *partially shipped 2026-05-10*

- **What.** ~95% of rows in `nappi_codes` had NULL `atc_code`. The WHO
  Anatomical Therapeutic Chemical classification is public + free
  (compilation rights restrict bulk distribution; see cleanup note below).
  Backfill onto every row matchable from `generic_name` / `ingredients`.
- **Why this matters.** Lets analytics group drugs by class ("all
  beta-blockers", "all SSRIs", "all ACE inhibitors") instead of only by
  brand. Required for international comparability and any drug-class
  analytics.
- **Status.** **Shipped 119 high-confidence Rx matches** out of 1,637 NULL
  rows. 226 routed to a review pile (multi-candidate substances like
  diclofenac/ibuprofen across anatomical groups, partial combos like
  Augmentin), 1,292 unmatched (pure brand names with no embedded INN —
  same blocker as 6a, needs MIMS/BHF brand→INN data). Migration 006 added
  `atc_class_desc`, `atc_match_method`, `atc_source`, `atc_matched_at`
  columns + indexes. 28-test unittest suite covers the matcher; SQL
  verification suite confirms data integrity.
- **What's NOT shipped.** The 226 review rows are sitting in
  `backend/data/atc/run_2026-05-10/matched_review.csv` waiting for a
  human to pick the right anatomical-group code from the alternatives
  column. Free recovery if/when prioritised.
- **Promotion-time inference (shipped 2026-05-10):** the
  `extraction_promoter` looks up every digitised medication's
  `medication_name` against `nappi_codes` (brand or generic, exact
  case-insensitive) and copies `nappi_code` + `atc_code` +
  `generic_name` onto the `prescription_items` row. Coverage today is
  data-bottlenecked (~10% on handwritten chart with 36 meds) — lifts
  to ~70-90% on typed/clean docs once the BHF MPP licence brings the
  full ~30k row dataset. No code change needed when that lands; the
  matcher and the promoter both work as-is on whatever's in
  `nappi_codes`.
- **License caveat.** Source data is the atcd GitHub mirror
  (CC BY-NC-SA 4.0, **NonCommercial**) — every row stamped
  `atc_source='atcd-2026-04-25'` for findability. Replace with a
  commercially-licensed source (BioPortal CC-BY, RxNorm public-domain,
  or WHOcc direct licence) before commercial GA. Cleanup is two SQL
  queries documented in `backend/data/atc/NOTICE.md`.
- **Files.**
  - `backend/migrations/006_atc_backfill.sql` — schema (run, applied)
  - `backend/scripts/atc_backfill.py` — matcher (re-runnable)
  - `backend/scripts/test_atc_backfill.py` — 28 unit tests
  - `backend/scripts/ATC_BACKFILL_README.md` — runbook
  - `backend/data/atc/WHO_ATC-DDD_2026-04-25.csv` (+ combinations) — index
  - `backend/data/atc/run_2026-05-10/` — matched/review/unmatched CSVs +
    applied UPDATE SQL + verification SQL suite
- **Source.** WHO Collaborating Centre for Drug Statistics Methodology —
  https://www.whocc.no/atc_ddd_index/

### 6c. Curated common-OTC supplement — *shipped 2026-05-10*

- **What.** Hand-add high-frequency SA OTC products into `nappi_codes`
  with brand + generic + ingredients + schedule + ATC. Synthetic
  `CURATED-<slug>-NNN` placeholder in `nappi_code`. `data_source='curated'`
  flag distinguishes from real_nappi rows.
- **Status.** **Shipped 54 curated OTC rows** covering analgesics
  (Disprin, Panado, Calpol, Compral, Grandpa, Nurofen, Voltaren Emulgel),
  cough/cold/flu (Demazin, Med-Lemon, Sinutab, ACC 200, Bisolvon, Strepsils),
  antihistamines (Zyrtec, Texa, Telfast), GI/antacids (Buscopan, Eno,
  Rennie, Maalox, Gaviscon, Imodium, Adco-Bilosec OTC), supplements
  (Reuterina, Bioplus, Berocca, Centrum, Vitamin C/B12, Slow-Mag),
  topicals (Deep Heat, Arnica), and antiseptics/antifungals (Antabax,
  Dettol, Savlon, Sudocrem, Bactroban, Candid, Canesten, Daktarin).
  Every row has its ATC pre-populated and validated against the WHO
  index (0 errors / 0 warnings).
- **NAPPI badge updated** in the validation panel ([UI surface 2]) to
  show "CURATED (NAPPI pending)" amber chip + schedule + ATC chip strip
  for curated rows. Reviewers see ingredient-validated drugs instead of
  red "No NAPPI".
- **Cleanup obligation.** When BHF MPP licence lands, real NAPPI rows
  for these brands will be ingested. For each curated/real overlap,
  copy `prescription_items.nappi_code` references from `CURATED-*` →
  real code, then drop the curated row. Stamped
  `atc_source='curated-otc-2026-05'` for findability.
- **Files.**
  - `backend/migrations/007_curated_otc_supplement.sql` — schema (applied)
  - `backend/data/atc/curated_otc_starter.csv` — the 54 entries
  - `backend/scripts/validate_curated_otc.py` — cross-checks ATC codes
  - `backend/scripts/generate_curated_otc_sql.py` — emits INSERT SQL
  - `backend/data/atc/run_2026-05-10/007_curated_otc_data.sql` (applied)

### 6d. Drug-drug interaction starter table

- **What.** New `drug_interactions` table with ~50-100 critical interactions
  curated from public clinical references (NICE BNF, FDA labels, Beers
  Criteria 2023, AGS guidelines). Each row: drug A, drug B, severity, clinical
  consequence, source. The validation panel flags dangerous combos at
  extraction time.
- **Why this matters.** This is the first thing that makes SurgiScan
  *actively* help a doctor (alert) instead of only digitise (record). Real
  safety value. Strategic differentiator.
- **Trigger to revisit.** When clinical lead is available to review the
  interaction list before ship — must not go live without sign-off.
- **Implementation hint.** Schema: `drug_interactions(id, drug_a_atc,
  drug_b_atc, severity ENUM('contraindicated','major','moderate','minor'),
  consequence TEXT, source TEXT, source_url TEXT, last_reviewed DATE)`.
  Match by ATC code (not brand) so it works across brands of the same drug.
  Requires items 6b (ATC backfill) and ideally 6c (OTC supplement) to be
  worth the effort. Initial seed list ~3 hr; clinical review pass separate.
- **Compliance note.** Any production drug-interaction service in SA
  arguably needs HPCSA + SAHPRA review. Do NOT ship without legal/clinical
  sign-off.

### 6e. Pricing + pack-size data on NAPPI rows

- **What.** Today `pack_size`, `manufacturer`, `route_of_administration` are
  all NULL on most NAPPI rows. Without them, drug-spend analytics can only
  count prescriptions, not rand value.
- **Why deferred.** Pricing data lives inside the BHF MPP licence — there's
  no clean public substitute.
- **Trigger to revisit.** When BHF MPP licence is in place (item 6a) — comes
  for free with the licensed dataset.

### 6f. Structured-data promotion (extractions → relational tables) — *shipped 2026-05-10*

- **What.** Validated digitisation extractions used to live forever as
  JSONB on `gp_validation_sessions.extractions`. The relational tables
  (`patients`, `encounters`, `diagnoses`, `vitals`, `allergies`,
  `prescriptions`, `prescription_items`) stayed empty for digitised
  patients, so analytics, the patient EHR view, and TRACEABILITY 6d
  (drug-drug interactions) all saw an empty world.
- **Status.** **`extraction_promoter` now runs on every approval** —
  match-or-create patient (by SA ID number, fallback to surname+dob),
  one encounter per consultation date, per-category writers tagging
  every row with `source_document_id`. Idempotent: re-approving the
  same doc wipes prior promotion artifacts and re-inserts. Migrations
  010 (UUID→TEXT schema fix per §10c of strategy doc) and 010b
  (encounters.source_document_id) are applied. Smoke-tested: doc with
  16 consultation dates → 1 patient + 16 encounters + 9 diagnoses +
  5 vitals + 36 prescription items.
- **Inference layer at promotion time:**
    - ICD-10 via the §1 lexicon (Tier 1) + tightened fuzzy (Tier 2).
    - NAPPI/ATC via lookup against `nappi_codes` (brand or generic).
- **What's NOT done:**
    - **Patient EHR view of promoted data** — `/patients/:id` doesn't
      yet read from these tables for digitisation-sourced patients.
      ~45 min UI work.
    - **Cross-document patient timelines** — multiple PDFs for the
      same patient match by ID number and layer onto one record, but
      there's no UI yet that surfaces "this Rx came from doc A,
      this one from doc B".
- **Files.**
    - `backend/migrations/010_extraction_promotion_schema.sql`
    - `backend/migrations/010b_encounters_source_doc.sql`
    - `backend/app/services/extraction_promoter.py`
    - approve handler in `backend/app/api/digitisation.py`
    - `frontend/src/components/groundtruth/ValidationHistoryDrawer.jsx`
      (renders the green "Promoted to EHR" card)

### 7. Mongo consolidation

- **What.** ~5-10 endpoints still write to MongoDB. Migrate to Supabase
  Postgres tables / `jsonb` columns / Storage buckets. Drop Mongo from the
  stack entirely.
- **Why deferred.** Not blocking; cleaner as a single focused pass after
  Type C pipeline stabilises.
- **Trigger to revisit.** Anytime — pure tech debt.
- **Implementation hint.** Inventory in earlier conversation: `validation_sessions`,
  `scanned_documents`, `audit_events`, AI Scribe transcripts. Migrate field by
  field, drop Mongo from `requirements.txt` + `.env` + docker-compose last.

### 8. ML risk scores + X-ray AI

- **What.** Risk scoring (cardiovascular, diabetes, lab anomaly) and X-ray
  analysis panels exist in the lifted EHRValidationPanel UI but the backing
  microservices don't.
- **Why deferred.** Phase 2 (Intelligence Layer) per the strategy doc — invite-
  only Beta. Not part of v1 scope.
- **Trigger to revisit.** First Beta-tier customer signs.
- **Implementation hint.** Adapter stubs in `groundtruth/api.js` (`mlRiskBatch`,
  `xrayStatus`, `xrayAnalyze`) — flip to real endpoints when the
  Intelligence Layer ships.

### 9. Unified semantic search — *shipped 2026-05-10*

- **What.** Embedding-based search across the whole digitisation corpus.
  User asks in natural language ("patients with arthritis", "elevated
  heart rate", "doctor prescribed antibiotics") and the system returns
  ranked chunks with the source document. Replaces the strategy-doc
  promise of "Q4 2026" — shipped today.
- **Status.** Working end-to-end. Indexer runs on every approval as a
  BackgroundTask (the validated extractions get chunked → embedded →
  stored). Search RPC ranks by cosine similarity within the workspace.
  UI page at `/digitisation/search` with example queries, ranked doc
  cards, and click-through to the validation panel. Demo doc indexed
  to 76 chunks across 11 sections; sample queries return clinically
  relevant hits at 45-60% similarity.
- **Architecture.**
    - **Embedding provider:** OpenAI `text-embedding-3-large` with
      `dimensions=1536` Matryoshka truncation (full 3072 exceeds
      pgvector ivfflat's 2000-dim limit). Cost: ~$0.0008 per doc
      indexed, ~$0.0000013 per search.
    - **Vector DB:** pgvector inside Supabase. ivfflat ANN index
      with `lists=100`; fine up to ~100k chunks. Switch to hnsw or
      Qdrant when scale demands.
    - **Chunking:** one chunk per JSONB section (top-level scalars
      and dict subsections) plus one chunk per array item under
      `medications`, `diagnoses`, `vitals_history`, `progress_notes`,
      `investigations`, `referrals`. Hard cap 1200 chars per chunk.
    - **Idempotency:** wipe-and-reinsert keyed on `document_id` —
      mirrors the promoter's pattern.
    - **Search RPC** (`digitisation_search` Postgres function) wraps
      the `<=>` cosine operator so the Supabase Python SDK can call
      it cleanly.
- **Files.**
    - `backend/migrations/011_semantic_search.sql` — pgvector ext +
      `document_embeddings` table + ivfflat index + RPC function
    - `backend/app/services/semantic_search.py` — chunking, embedding,
      indexer, search wrapper
    - `backend/app/api/digitisation.py` — `/search` (GET) +
      `/search/reindex/{document_id}` (POST) + indexer hooked into
      `/approve` via `BackgroundTasks`
    - `frontend/src/pages/DigitisationSearch.jsx` — search UI
    - `frontend/src/App.js` + `Layout.jsx` — route + nav entry
- **What's NOT shipped (Phase 2 enhancements).**
    - **LLM query rewriter** for compound queries like "patients on
      metformin AND HbA1c > 8 in last 6 months" — today the embedding
      handles the semantic part but doesn't translate to structured
      filters. Phase 2: have an LLM emit a `WHERE` clause from the
      query, then ANN-search within the filter set.
    - **Patient-level "similar patients"** — needs whole-record
      embedding (concat all sections) instead of per-chunk. Layered
      addition; same table, new vector kind.
    - **Backfill of pre-existing approved docs** — the indexer runs
      on new approvals and the on-demand reindex endpoint exists, but
      a one-time backfill script that walks every validated doc and
      indexes it would be useful (~30 min to write).
    - **Cross-workspace federation** — search is workspace-scoped
      (correctly — tenancy). For multi-practice groups (Group tier
      Q1 2027), a workspace-list filter would be the addition.

### 10. FHIR push bundle profile per downstream EHR — *deferred to first real customer*

- **What.** Phase C ships an auto-POST of the generated bundle to the
  workspace's default FHIR connection. The bundle today is structured
  as an **outer batch Bundle wrapping per-document searchset Bundles**
  — valid FHIR R4 but conformant servers vary in what they accept.

      Bundle { type: 'batch',
               entry: [ Bundle { type: 'searchset',
                                 entry: [ Patient, Condition, ... ] },
                        ... per source document ... ] }

- **Status.** Works against **lenient** endpoints (custom EHR FHIR
  facades that just store-and-forward). Returns **HTTP 400** against
  strict servers (verified against HAPI public sandbox 2026-05-10).
  HAPI wants either:
    - `Bundle{type:'transaction', entry:[Resource{}, ...]}` with
      `entry.request.{method, url}` per resource, OR
    - One Resource per POST (no Bundle), one HTTP call each.
- **Why deferred.** Different downstream EHRs profile FHIR differently.
  Discovery Health's API differs from Practice Perfect, which differs
  from TrakCare, which differs from a HAPI-on-prem deployment. Picking
  the "right" shape speculatively burns time on profiles no real
  customer is using yet. Connection-test (`GET /metadata`) works
  universally because every conformant FHIR server exposes
  CapabilityStatement; the push side wants tuning per customer.
- **Trigger to revisit.** First real customer connects a real FHIR
  endpoint and surfaces their server's expected bundle shape. Until
  then, the manual download path still works (Export Centre →
  Download FHIR bundle → upload to their EHR).
- **Implementation hint.** Add a `bundle_profile` enum on
  `digitisation_fhir_connections.metadata` with values like
  `nested_batch` (current default), `flat_transaction`, or
  `single_resource_post`. The push step in
  `digitisation_export_worker._attempt_push` reshapes the outgoing
  payload accordingly:
    - `flat_transaction`: walk the per-doc bundles, hoist all leaf
      resources into one outer Bundle with `type='transaction'` and
      synthesise `entry.request = {method: 'POST', url: '<ResourceType>'}`
      per entry.
    - `single_resource_post`: skip the outer Bundle entirely; loop and
      POST each Resource individually with the resource type appended
      to `fhir_url`. Aggregate the per-resource statuses.
  Estimated effort: ~2-3 hr including testing against HAPI for
  `flat_transaction` and a curl-based mock for `single_resource_post`.
- **Customer onboarding cost.** Each new downstream EHR adds at most
  one new bundle_profile value. Once added, every other workspace on
  the same EHR reuses it without re-work.

### 11. Multi-practice support — *partially supported (schema only); UX deferred*

- **What.** A single doctor (or admin) operating multiple practices —
  e.g. clinics in Sandton + Pretoria, or a Group practice (Quadcare,
  Intercare-style) with 7+ doctors across multiple locations sharing a
  central admin.
- **Status.**
    - ✅ **Schema supports it.** Three-level model: `tenants` →
      `workspaces` → `users`. Every endpoint filters by
      `current_user.workspace_id`; cross-workspace data leak is
      structurally impossible.
    - ✅ **Solo doctors with one practice** — fully supported today.
    - 🟡 **Multi-practice doctor (2-3 clinics)** — works at the data
      layer but UI assumes one workspace per session. Doctor needs
      separate logins per practice. No workspace-switcher in the nav.
    - ❌ **Group practices (Quadcare-style, 7+)** — not yet built;
      strategy doc explicitly deferred to **Q1 2027**.
- **Why deferred.** v1 sales motion targets solo / Type C / Type A
  practices. Group sales is a different cycle (corporate procurement,
  multi-month, different decision-makers). Per the sales playbook:
  *"don't quote Group bands; defer with 'we're focused on private
  practice for v1'."*
- **Trigger to revisit.**
    - **For multi-practice solo doctors:** First prospect with 2+ owned
      practices balks at the multi-login UX → ship the workspace switcher
      (the smaller fix below). Roughly **half a day** of work.
    - **For Group tier:** When commercial sales motion opens for Group
      (Q1 2027 per strategy). Multi-day effort.
- **Implementation hint.** Two distinct work tranches:

    **Tranche A — multi-practice solo (~3-5 days total)**
    1. Migration: `user_workspaces` join table (`user_id`,
       `workspace_id`, `role`) — replaces the implicit single
       `users.workspace_id` with N:N. Backfill from existing data.
    2. Auth update: token claims include the user's accessible
       workspace list; current request's `workspace_id` selected via
       header / context.
    3. **Workspace switcher** in `Layout.jsx` sidebar — dropdown of
       accessible workspaces, click to flip context. Persists via a
       simple cookie or query param.
    4. Cross-workspace federated search — `/api/digitisation/search`
       already designed for workspace-list filter; surface a "search
       all my practices" toggle in the UI (~1-2 hr).

    **Tranche B — Group tier (~2-3 days on top of A)**
    5. Group admin role with cross-workspace permissions within a
       tenant — separate from individual workspace roles.
    6. Capability inheritance: `practice_capabilities` rolls up at the
       tenant level so Group buys Module 02 once and all workspaces
       under it inherit the entitlement.
    7. Group-level analytics rollup — depends on §10c.5 (cross-doctor
       analytics) being addressed first. Aggregation views over
       `prescriptions` / `diagnoses` / `encounters` filtered by
       `tenant_id`.
    8. Centralised billing — single invoice covering all workspaces
       under one tenant. Today `gp_invoices` has `workspace_id`
       (post-migration 012); add `tenant_id` rollup queries.

- **What stays valid throughout.** No throwaway work. The current
  workspace-scoped tenancy model is the foundation; multi-practice
  layers on top via `user_workspaces` and a tenant-level rollup
  pattern. The current code keeps working unchanged for solo
  customers while the multi-practice path opens up alongside.
- **Sales positioning today.** "We support practices end-to-end. If
  you operate multiple clinics, we onboard each as a separate workspace
  with your same login — group rollups and central admin land Q1 2027."

---

## How to use this document

- When a deferred item bites in production, find it here, build it.
- When a sales conversation surfaces a need, find it here, prioritise it.
- When you're tempted to ship a "quick fix" that breaks one of the principles
  above (e.g., silent fail-open on a lookup), pull this up and don't.
- Add new items inline, in the same shape (what / why / trigger / hint).
- Move completed items to `## Done` at the bottom with the date.

---

## Done

*(none yet — this doc just born 2026-05-07)*
