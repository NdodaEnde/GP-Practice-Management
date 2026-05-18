# ZERO — the ~80-row per-route capability table (artifact for locking)

**STATUS: A–D LOCKED *and APPLIED* via the central `ROUTE_CAPABILITIES`
map (Item 1; code local + tests green; NOT committed — awaiting the
word). §E intentionally undecided (product-gated). Floor + sick-note cut
already on `main` @ `8f2486b` (true-ff).**

### Item 1 applied — 2026-05-18 (Forks 1 & 2 locked, executed to spec)

- **Fork 1 (mechanism): central `ROUTE_CAPABILITIES` map** in
  `app/core/auth_backstop.py`, enforced once in the middleware after
  authentication — NOT ~68 per-route decorators (that re-installs the
  silent-omission failure the floor exists to kill). The map is the lock
  made executable in one diff-visible block. Bite-proving test
  (`tests/test_capability_application.py`) parametrised over the map
  itself, proven RED pre-enforcement (read-only probe) → GREEN
  post-enforcement; non-vacuous both ways (wrong-cap → 403 *naming the
  cap*; removing any entry flips its decision); every map key verified to
  bind to a real live route (no orphan keys); §E immovability asserted
  *and* the immovability check itself proven non-vacuous.
- **Fork 2 (scope): capability-only. RECORDED INTENDED SHAPE —** post
  Item 1 the A–D surface is **authentication-and-authorization correct
  but NOT yet uniformly tenant-correct.** The sick-note cut fixed the
  worst single instance (its `DEMO_*` hardcode); the rest of the write
  surface may carry the same hardcode and is **its own deliberate
  tracked crossing**, NOT bundled (bundling = the sprawl) and NOT
  ignored (ignoring = the looks-fixed trap). "Gated" here does **not**
  mean "tenant-correct" — that distinction is chosen and recorded so the
  post-Item-1 state is honestly described, not more finished than it is.
- **Not in the map, by design:** sick-note family (own `Depends`, not
  double-gated — coexistence test-verified); the 3 pre-existing CAP'd
  routes (unchanged); §E (floor-only, undecided); explicitly-public
  `leads` + `medications/*` (in `PUBLIC_PATHS`).
- **Observed, surfaced not buried (not ZERO scope):** several legacy GET
  endpoints 500 on a refused `localhost:27017` (MongoDB) — a pre-existing
  legacy infra coupling, not introduced here; named, not actioned.
The deny-by-default floor (commit `8f2486b`) already closed the security
hole structurally — every route is authenticated-or-401 now. This table
is the *granularity* layer (which authenticated principal), a
correctness/product refinement on an already-safe surface. No time
pressure; done well. Application of locked rows is its own
surgically-staged commit under the same gates — "locked" ≠ "applied".

### Locks recorded — 2026-05-18

- **Referrals → `gate:patient_ehr_basic`** — LOCKED. Same object class
  and reasoning as the committed sick-note cut (clinical-legal doc,
  consultation context, `ReferralBuilder.jsx` sibling of
  `SickNoteBuilder.jsx`, no `referral_*` capability exists; gate to the
  capability the legitimate caller already holds). Overruleable ONLY by
  a product role-distinction not in the code (e.g. a referral may be
  raised by a nurse/admin where a sick note may not). No such
  distinction supplied ⇒ locked `patient_ehr_basic`.
- **`/api/medications/*` → `explicitly-public` (reference data)** —
  LOCKED; principal **overruled** the proposed `gate:prescription_writing`.
  Reasoning (recorded because the reasoning is the lock): NAPPI is a
  public SA drug-code registry — reference data, no patient/tenant/
  workspace scope, same class as ICD-10 lookup. "Only the prescriber
  calls it today" is not evidence only the prescriber *should* (the
  preamble's absence-isn't-signal principle, inverted form). A
  digitisation-tier reviewer resolving a NAPPI code while validating an
  extraction is a legitimate future caller the wedge depends on;
  `gate:prescription_writing` would break the Type-C review path for the
  exact tier the wedge is sold to. Public-registry risk ≈ nil (floor
  still requires the request reach the allowlist; no sensitive data).
- **`/api/leads` → `explicitly-public`** — LOCKED, with rider. A public
  marketing form has no authenticated principal by definition; the floor
  401ing it was deny-by-default correctly catching a true allowlist
  member. **Rider (named-not-now, see §F):** a public *write* endpoint
  is an abuse target in a way a public read is not; allowlisting fixes
  *authorization*, not *abuse* — conflating them would repeat the
  auth-vs-tenant error from the sick-note cut.
- **A–D, all other rows → LOCKED as proposed**, by acceptance of their
  verified-caller reason (the lock is the reason, not the disposition).
  Any row whose verified-caller reason does not hold is brought back and
  re-reasoned the way the three above were.

## Preamble — why this is decided, not recovered (load-bearing; read first)

The legacy `server.py @api_router` surface is the old GP-Practice module,
merged in wholesale, built **before** the capability-gating discipline
existed and never reconciled. Therefore: **the absence of a gate on a
legacy route carries NO signal.** The module never expressed the
decision either way — it predates the discipline that would have. Every
row below is a **first-time decision being made**, not a prior decision
being recovered.

Consequences that constrain this artifact:
- It must NOT infer intent from current state — there is no intent
  encoded in the absence.
- It must NOT mechanically pattern-match route names to capabilities —
  that invents intent.
- Each disposition is backed by a **verified legitimate caller** (which
  frontend surface calls it ⇒ which tier holds the capability), the same
  method that made the sick-note cut correct: *verify what legitimately
  calls it before choosing the capability.*
- Rows where the legitimate caller could **not** be determined from the
  code are surfaced as their own honest category (§E) — not given a
  confident disposition. That is the §D.1 discipline applied to the
  table: do not manufacture an answer where the premise (who calls this)
  is unverified.

You lock by reviewing reasons. A disposition without a verified reason is
exactly the inference-without-verification the preamble forbids.

## Capability vocabulary (real strings — do not invent; from `seeds/products_and_capabilities.sql`)

| Capability | Tier that grants it |
|---|---|
| `patient_ehr_basic` | platform_essential / professional (Full-EHR clinical) |
| `prescription_writing` | platform_essential / professional |
| `billing_invoicing` | platform_essential / professional |
| `ai_scribe` | platform_professional |
| `queue_display` | platform_professional |
| `digitisation_upload` / `_validation` / `_auto_populate` / `_export_basic` / `_export_fhir` / `_operational_analytics` | module_digitisation / foundation_bundle |
| `analytics_cohorts` / `_claims_aging` / `_productivity` / `_drug_spend` / `_semantic_search` / `_dashboards` | module_analytics |

Disposition values: `gate:<cap>` · `explicitly-public` (→ minimal allowlist, diff-visible) · `off-reachable-path` (route should not be reachable at all; retire — a Piece-1 decision, see note).

---

## A. CLINICAL / LEGAL WRITE — highest severity

| Family (routes; register file:line) | Proposed disposition | Verified-caller reason |
|---|---|---|
| **Patients write** — `POST /api/patients` 1053, `PUT /api/patients/{id}` 1126 | `gate:patient_ehr_basic` | `pages/ReceptionCheckIn.jsx`, `pages/PatientEHR.jsx`, `services/gp.js` — Full-EHR registry/demographics; `patient_ehr_basic` is its exact named scope. |
| **Encounters write** — `POST /api/encounters` 1142, `PUT /api/encounters/{id}` 1203 | `gate:patient_ehr_basic` | `VitalsStation.jsx`, `AIScribe.jsx`, `PatientEHR.jsx` — encounter records + vitals are inside `patient_ehr_basic`'s described scope. |
| **Documents write (Full-EHR side)** — `POST /api/documents/upload` 1334, `/upload-standalone` 1259, `/match-patient` 1415, `/link-to-patient` 1476, `/create-patient-from-document` 1585, `/{id}/log-access` 3928 | `gate:digitisation_upload` (match/link/create-patient: `digitisation_validation`) | `DocumentUpload.jsx`, `DigitisedDocuments.jsx` — the digitisation ingestion path; upload→`digitisation_upload`, the match/link/create-patient promotion→`digitisation_validation`. |
| **GP validation/promote** — `POST /api/gp/validation/save` 2467, `/match-patient` 2541, `/confirm-match` 2563, `/create-new-patient` 2652, `/api/gp/validate-extraction` 2340 | `gate:digitisation_validation` | `GPValidationInterface.jsx`, `DocumentValidation.jsx`, `ValidationReview.jsx` — the human-in-the-loop validation queue; `digitisation_validation` is its exact scope. |
| **GP document processing** — `POST /api/gp/upload-patient-file` 2213, `/upload-with-template` 3358, `/documents/bulk-extract` 3321, `/documents/{id}/extract` 3500, `/documents/{id}/reprocess` 2878, `/documents/{id}/queue-processing` 2917, `/documents/queue-all-uploaded` 2963, `/api/gp/batch-upload` 3649, `PUT /api/gp/documents/{id}/status` 3253, `DELETE /api/gp/documents/{id}` 3286 | `gate:digitisation_upload` (DELETE: `digitisation_validation`) | `DigitisedDocuments.jsx`, `DocumentUpload.jsx`, `services/gp.js` — the ingestion/reprocess pipeline = `digitisation_upload`; destructive DELETE raised to `digitisation_validation`. |
| **Validation approve/reject (the wedge)** — `POST /api/validation/{id}/approve` 1847, `/validation/approve/{id}` 1775 (dup), `/validation/reject/{id}` 1811 | `gate:digitisation_auto_populate` | `ValidationQueue.jsx`, `DocumentValidation.jsx` — approve promotes extractions into the EHR; `digitisation_auto_populate` is exactly "validated records auto-populate the EHR". **The duplicate `1775` is also a Piece-1 retire candidate (see note).** |
| **AI scribe** — `POST /api/ai-scribe/transcribe` 4268, `/generate-soap` 4321, `/extract-clinical-actions` 4403, `/save-consultation` 4533 | `gate:ai_scribe` | `pages/AIScribe.jsx` — 1:1 with the `ai_scribe` capability ("GPT-4o SOAP from voice"). `save-consultation` writes the encounter → also within `patient_ehr_basic`; gate on `ai_scribe` (the surface that calls it; that tier also holds `patient_ehr_basic`). |
| **Prescriptions** — `POST /api/prescriptions` 4681 | `gate:prescription_writing` | `PrescriptionBuilder.jsx`, `PatientPrescriptions.jsx` — 1:1 with `prescription_writing`. |
| **Referrals** — `POST /api/referrals` 4908 | `gate:patient_ehr_basic` | `ReferralBuilder.jsx` — same consultation surface and reasoning as the locked sick-note cut; **no `referral_*` capability exists** → the clinical-consultation tier (`patient_ehr_basic`) the issuing clinician already holds. Flagged: confirm this is the intended tier for a referral letter (legal-ish doc), same question you locked for sick-notes. |
| **Sick-notes** — `POST /api/sick-notes` 4854 | **LOCKED — `gate:patient_ehr_basic`** (committed `8f2486b`) | First concrete cut, already done to definition + tenant fix. Listed for completeness. |

## B. PII / CLINICAL READ

| Family (routes; file:line) | Proposed disposition | Verified-caller reason |
|---|---|---|
| **Patient reads** — `GET /api/patients` 1084, `/{id}` 1112, `/{id}/conditions` 1229, `/{id}/medications` 1243, `GET /api/encounters/patient/{id}` 1179, `/encounters/{id}` 1189 | `gate:patient_ehr_basic` | `PatientEHR.jsx`, `services/gp.js` — Full-EHR record reads; `patient_ehr_basic` scope. |
| **Digitisation reads** — `GET /api/gp/documents` 3004, `/{id}` 3072, `/api/gp/parsed-document/{id}` 3106, `/api/gp/validation-session/{id}` 3148, `/api/gp/document/{id}/view` 2409 & 3213, `/api/gp/patients` 2355, `/api/gp/patient/{id}/chronic-summary` 2367, `GET /api/validation/{id}` 1702, `/validation/queue/list` 1721, `GET /api/documents/pending-match` 1628, `/documents/encounter/{id}` 1646, `/documents/{id}/original` 1672, `/documents/patient/{id}` 3829, `/documents/{id}/details` 3853, `/documents/{id}/audit-trail` 3891, `/documents/search` 3959 | `gate:digitisation_validation` | `DigitisedDocuments.jsx`, `ValidationQueue.jsx`, `DocumentValidation.jsx`, `services/gp.js` — the validation-queue surface (reads of parsed/validation state). `digitisation_validation` is its scope. **`2409`/`3213` are duplicate `/gp/document/{id}/view` → Piece-1 retire candidate.** |
| **Prescription reads** — `GET /api/prescriptions/patient/{id}` 4799, `/prescriptions/{id}` 4829 | `gate:prescription_writing` | `PatientPrescriptions.jsx`, `PrescriptionBuilder.jsx`. |
| **Sick-note read** — `GET /api/sick-notes/patient/{id}` 4890 | **LOCKED — `gate:patient_ehr_basic`** + workspace-scoped (committed `8f2486b`) | Mirror read-isolation, already done. |
| **Referral read** — `GET /api/referrals/patient/{id}` 4947 | `gate:patient_ehr_basic` | `ReferralBuilder.jsx` / consultation surface — symmetric with the referral write row; same flag. |

## C. CLINICAL-OPS / SENSITIVE METADATA

| Family (routes; file:line) | Proposed disposition | Verified-caller reason |
|---|---|---|
| **Queue** — `POST /api/queue/check-in` 4003, `/queue/{id}/call-next` 4109, `PUT /api/queue/{id}/update-status` 4168, `GET /api/queue/current` 4070, `/queue/stats` 4223 | `gate:queue_display` | `QueueDisplay.jsx`, `ReceptionCheckIn.jsx` — 1:1 with the `queue_display` capability (reception + clinical waiting-room board). |
| **Digitisation ops metadata** — `GET /api/gp/statistics` 2397, `/api/gp/watcher/status` 2845, `/api/gp/batch-status/{id}` 3770, `/api/gp/batch-history` 3805 | `gate:digitisation_operational_analytics` | `DigitisedDocuments.jsx`, `services/gp.js` — throughput/engine-health/batch state = exactly `digitisation_operational_analytics`'s description. |

## D. REFERENCE DATA / PUBLIC CANDIDATES

| Routes (file:line) | Proposed disposition | Reason + the lock question |
|---|---|---|
| `GET /api/medications/search` 4965, `GET /api/medications/{id}` 4984 | **LOCKED → `explicitly-public`** (reference data) | NAPPI public SA drug-code registry; no PII/tenant scope. Proposed gate **overruled**: gating to the current sole caller breaks the Type-C digitisation reviewer resolving NAPPI codes — a legitimate future caller the wedge depends on. Becomes a diff-visible allowlist line at application. |
| `POST /api/leads` 1018 | **LOCKED → `explicitly-public`** (+ §F rider) | Public marketing lead-capture; no authenticated principal by definition. Diff-visible allowlist line at application. Abuse-hardening for this public *write* is named-not-now (§F) — authorization is decided; abuse is a separate adjacent piece, surfaced not buried. |
| `GET /api/` 987, `GET /api/health` 991 | `explicitly-public` | Root/liveness — already on the allowlist (committed). No data. Listed for completeness. |

## E. UNKNOWN / AMBIGUOUS LEGITIMATE CALLER — honest category, needs your product knowledge

**LOCK DECISION (2026-05-18): §E stays §E — floor-safe, capability-UNDECIDED.**
The floor holds these closed to unauthenticated callers *now* (safe);
they are NOT assigned a capability until the product decision is made.
"Safe" and "correctly tiered" are different states — the floor delivers
the first, only your product knowledge delivers the second. An §E row
with an invented capability is *more* dangerous than one honestly marked
undecided (it looks finished and isn't). Do not let "finish the table"
pressure dispose these.

These have **no determinable legitimate caller in the codebase**. No confident disposition is offered — that would be the manufactured-answer anti-pattern. Your decision, on product knowledge the code does not contain:

| Routes (file:line) | Why unknown | What I'd need from you |
|---|---|---|
| `POST /api/dispense` 1900, `GET /api/dispense/encounter/{id}` 1922 | **No frontend caller found** in any `frontend/src` file. Dispense is pharmacy-facing; the recon found a pharmacy/dispensary view is *missing* (Full-EHR audit). Caller genuinely undetermined. | Is there a pharmacy surface (built or planned)? Which tier is the dispenser? No `dispense`/`pharmacy` capability exists in the vocabulary — this may need a *new* capability, which is a product decision, not an inference. |
| `GET /api/analytics/summary` 2002, `/api/analytics/operational` 2027 | Caller plausibly `WorkstationDashboard.jsx` but not confirmed unambiguous; spans practice-ops. Family is "analytics" but the *sub-capability* (`analytics_dashboards`? operational vs cohort) is not determinable from code. | Which analytics sub-capability owns the practice summary/operational dashboard? (The 3 already-gated analytics routes use `analytics_cohorts`/`_drug_spend` — pattern suggests `analytics_*`, but the exact sub-cap is yours.) |
| `GET /api/analytics/financial` 2159 | Financial analytics straddles `analytics_claims_aging` and `billing_invoicing`; no single verified caller. | Is practice financial analytics part of the analytics module or the billing tier? |

## F. Named-not-now — surfaced, not buried, not blocking

- **Public-write abuse-hardening for `POST /api/leads`.** `explicitly-public`
  is the correct *authorization* disposition (LOCKED). It does NOT
  address *abuse*: a public unauthenticated write endpoint is a spam /
  injection / resource-exhaustion target in a way a public read
  (`/api/health`) is not. Rate-limiting + captcha + input-hardening for
  this route is its own deliberate piece — **not built now, not blocking
  the allowlist**, named so "public" is never silently assumed to mean
  "safe". Same shape of honesty as surfacing `/api/leads` itself when
  the floor first caught it.

## Already-gated (3) — confirm only, no change

`analytics-cohorts` 2085 `CAP:analytics_cohorts` · FHIR-export 5053 `CAP:digitisation_export_fhir` · drug-spend 5140 `CAP:analytics_drug_spend`. Verified correct against the vocabulary; no action.

## Note — the Zero ∩ Piece-1 intersection (do NOT merge)

Three duplicate/legacy routes appear above as `off-reachable-path` *candidates*: `POST /api/validation/approve/{id}` 1775 (dup of 1847), `GET /api/gp/document/{id}/view` 2409 & 3213 (dup). Zero's job is to **gate** them (deny-by-default already does; this table assigns the capability so they are safe *now*). Whether they are **retired** is a Piece-1 decision (the safest version of an ungated redundant path is a deleted one — but that is its own deliberate crossing, not Zero's, and not merged into this lock).

## State now / what's next

- **A–D: LOCKED** (3 rows re-reasoned at lock; the rest by acceptance of
  their verified-caller reason). **§E: undecided by design**, floor-safe.
- **Not applied.** `server.py` is untouched; the floor is the only thing
  live. Applying the locked A–D rows (add `require_capability(...)` deps;
  add the `explicitly-public` allowlist lines for `medications`/`leads`;
  `/api/` `/api/health` already allowlisted) is the **next deliberate
  act — its own surgically-staged commit, its own explicit word**, same
  gates as the first cut. "Locked" ≠ "applied".
- **§E exits §E only by a per-row product decision** from the principal
  (dispense pharmacy tier / a possible new capability; the analytics
  sub-capability / billing-vs-analytics boundary). Until then they stay
  floor-safe and capability-undecided.
- **Merge of `8f2486b` to `main` — DONE 2026-05-18, true fast-forward.**
  **Chosen shape, recorded as intended (not drifted into):** the
  deny-by-default floor + the first capability cut close the
  authorization *class* on `main` structurally; the per-route A–D
  *application*, the §E product decisions, and any tiering refinements
  are the **deliberate, explicitly-tracked follow-on** — not an
  accidental mid-table state. `main` is structurally safe (every route
  authenticated-or-401); it is not yet per-route-tiered, and that
  distinction is the intended shape, on the bias that a security closure
  belongs on `main` sooner.
