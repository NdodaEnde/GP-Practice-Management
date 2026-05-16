# Phase 3 — PR B Implementation Plan: Harden + Broaden + the Ugly Cases

> **Status:** plan APPROVED at review (same bar as PR A / the executor
> plans). Grounded in fresh live-DB probes run 2026-05-16. **Both
> reserved decisions RESOLVED with required riders (see §7); two required
> plan changes applied (§8 overclaim tightened; §3.5 inertness invariant
> named as a gate); one suggested change applied (§6 shared-trigger
> note).** Cleared for implementation, carried constraints first.
>
> Supersedes nothing in `ONTOLOGY_PHASE3_QUERY_LAYER_PLAN.md`; that
> remains the umbrella source of truth. This is the detailed PR B
> implementation plan its "PR B" section deferred to
> "sized-by-the-locked-semantics, brought back complete."
>
> **Premise corrections this probe surfaced (norm: verify before
> asserting):**
> - The live env is `backend/.env`, NOT `../.env` (repo root has no
>   `.env`). All PR B test/probe `load_dotenv` must target `backend/.env`.
> - Migration 026 is **7** `CREATE OR REPLACE FUNCTION` statements (6 new
>   + the diagnosis-template re-creation for `order_by`), not "six" as
>   the umbrella plan's prose said. Corrected count, not a scope change.
> - The reversed-source audit column is `action_audit_log.action_name`
>   (the umbrella prose said `action_type`). Coding the literal wrong
>   string would make the lookup silently match nothing and report
>   `superseded_count=0` for the wrong reason — indistinguishable from
>   the true 0. Load-bearing correction.
> - **Material:** the umbrella plan / migration 025's honesty note say
>   demo-gp returns empty for the diagnosis template (true) — but demo-gp
>   is **richly data-bearing for the NEW templates** (38 encounters, 20
>   prescriptions, 15 docs) with **every fact `source_document_id =
>   NULL`**. This changes the carried-browser-contrast story (see §1.6,
>   §2(i), §6). It is not a scope change; it is the corpus being
>   different from what the umbrella plan assumed, caught before coding.

---

## 1. Empirical findings (live DB) — actual numbers, falsified assumptions flagged

All probes via the `verify_query_phase0.py` connection idiom
(`psycopg2.connect(os.environ['DATABASE_URL'])`, `load_dotenv('backend/.env')`).

### 1.1 Entitlement still resolves (Decision #4)
`SELECT 'clinical_query' = ANY(practice_capabilities('demo-gp-workspace-001'))`
→ **True**. demo-gp's set includes `clinical_query`, `legacy_full_access`,
`analytics_cohorts`, `audit_log`, `clinical_ai_*` — the coherence
argument in migration 025's header holds verbatim. No adaptation.

### 1.2 Per-template data maturity (the load-bearing maturity table)

| Template | Join (verified cols) | demo-gp-001 (entitled) | typec-001 | Verdict |
|---|---|---|---|---|
| `patients_with_diagnosis_prefix` (+`order_by last_consultation`) | `patients.id`(text)⋈`diagnoses.patient_id`(text); LEFT JOIN `encounters.encounter_date` for order_by | **0 diagnoses** (PR A finding re-confirmed) | 9 | `populated` registry-wide; empty on entitled ws |
| `patients_not_seen_since` | `patients` LEFT JOIN `encounters`(patient_id text=text); `encounters.encounter_date timestamptz` | **38 encounters** 2025-10-13→2026-01-15 (all >120d before today → all 31 patients qualify) | 16 | `populated`, **data-bearing on demo-gp** |
| `patient_active_medications` | `prescriptions`(patient_id text,status,source_document_id)⋈`prescription_items`(prescription_id,medication_name) | **20 presc / 20 items**, all `status='active'`, **all `source_document_id NULL`** | 10 | `populated`; **provenance = all live_entry** |
| `patient_recent_consultations` | `encounters`(patient_id text,encounter_date,chief_complaint,status,source_document_id) | **38**, status completed(16)/in_progress(22), **all source NULL** | 16 | `populated`; **provenance = all live_entry** |
| `patients_with_abnormal_recent_vitals` | `vitals`(patient_id text,bp_systolic int,measured_datetime,source_document_id) | **0 vitals** | 5 (2 bp_sys>140) | **`thin` confirmed**; empty on demo-gp |
| `patient_open_documents` | `digitised_documents`(workspace_id,status,filename,upload_date,file_path) | **15 docs**: extracted(9),error(3),extraction_failed(2),parsing(1); none validated/approved | 3 | `populated`, data-bearing |
| `patients_with_lab_threshold` | `lab_results`(result_numeric,reference_high,test_code) via `lab_orders`(patient_id,workspace_id) | lab_orders 2; **lab_results 1 globally**, no LOINC | 0 | **`schema_only` confirmed** |

**Assumption corrected (material):** demo-gp is empty *for the diagnosis
template* (true) but **richly data-bearing for the new
encounter/medication/open-docs templates**. PR B's briefing set CAN be
verified on the real entitled workspace — directly answering carried
constraint (ii)'s open question.

### 1.3 Confidence recoverability (Decision #1) — re-verified, HOLDS
`gp_validation_sessions`: 16 rows, all with non-empty `confidence_scores`
jsonb keyed by `document_id`; sample keys `['vitals','demographics','chronic_summary']`
→ **section-level, not per-fact** confirmed. Distinct diagnosis source
docs = 16; recoverable = **1/16**, exactly as the umbrella plan stated.
Decision #1's "dominant 15/16 not-recoverable" is corpus-true.

### 1.4 Reversed-source (Decision #2) — re-verified, HOLDS
`PromoteDocumentToPatientRecord` rows: 100; with `reversed_by_audit_id IS
NOT NULL`: 17. **LIVE diagnoses pointing at a reversed-promotion source:
0. LIVE prescription_items: 0.** Reverse RPC DELETEs the facts.
**Reversed-source is construct-validity-only — re-confirmed.** Detection
column: `action_audit_log.reversed_by_audit_id` (uuid); identifier
`action_name` (NOT `action_type`).

### 1.5 Two-source — re-verified, HOLDS
Patients with diagnoses from >1 distinct `source_document_id`: **0**.
prescription_items >1 source: **0**. **Construct-validity-only.**

### 1.6 Orphaned source + carried browser-contrast — DECISIVE FINDING
Diagnoses with `source_document_id`: 24; orphaned (doc missing
globally): **15** → 62% dominant-failure finding **re-verified exactly**.
demo-gp digitised_documents: 15, all `file_path` non-null. **But: ZERO
demo-gp clinical facts reference ANY demo-gp document.** Across
diagnoses/encounters/clinical_notes/prescriptions/prescription_items/
vitals/lab_orders/allergies in demo-gp, every `source_document_id` is
NULL → every demo-gp briefing row resolves **NO_SOURCE (live_entry)**,
never OPENABLE, never UNRESOLVABLE.

**Load-bearing consequence:** the honest openable-vs-unresolvable browser
contrast is **NOT naturally producible on demo-gp** even with the new
templates. Per riders (ii)/(iii): the browser contrast is delivered via
a legitimately-provisioned platform-tier demo workspace whose primary
purpose is briefing-template verification; orphan-rendering is recorded
**probe-verified-only** if that legitimate seed contains no orphan
(expected — orphans are a deletion-history artifact, not normal
ingestion). **No orphan is ever injected to complete the click-through.**

### 1.7 Schema reality per new template (TEXT-vs-UUID scar, verified)
All join keys TEXT=TEXT, no `::uuid` casts: `patients.id`⋈
`encounters/prescriptions/vitals.patient_id` (all text);
`prescription_items.prescription_id`⋈`prescriptions.id` (text).
`diagnoses.id`/`vitals.id` are uuid but their `patient_id` is text
(joins unaffected). `lab_results` has **no patient_id** — reaches
patient via `lab_orders.id`⋈`lab_results.lab_order_id`→
`lab_orders.patient_id` text. Date cols (verified, not assumed):
`encounters.encounter_date timestamptz`, `prescriptions.prescription_date
date`, `vitals.measured_datetime timestamptz`,
`digitised_documents.upload_date timestamp`, `diagnoses.diagnosed_date
date`. `prescriptions.status` distinct = only `'active'`; "active" filter
= `status='active' AND void_reason IS NULL`. Medication name =
`prescription_items.medication_name`. `digitised_documents.status` ∈
{extracted,error,validated,extraction_failed,parsing}; "open" = NOT IN
terminal. `doc_type` 0/20 populated — citations never name a doc class.

### 1.8 Index/EXPLAIN reality
Briefing tables well-indexed (workspace/patient/date indexes present).
**Gap:** `prescription_items` has only its pkey — no `prescription_id`
index. At 51 rows the planner seq-scans (acceptable). The integration
EXPLAIN assertion uses PR A's Phase-0 (iii) heuristic (assert
join-correctness / no cross-join pathology, NOT forced index use).
Postmortem records `idx_prescription_items_prescription_id` as a future
scale index.

---

## 2. The three carried constraints — scoped FIRST, equal weight, un-skippable

### (i) Live openable-vs-unresolvable contrast (real chain `:3000→:8002`; in-app render Phase-4-gated — see DISCHARGED note)
Discharged by a checklist item in the PR B description with a literal
screenshot/recording reference and a named human verifier (the user, at
review), a row in the §4 ledger, and a postmortem line — mirroring PR A's
verification-statement discipline. **Honest scope, forced by §1.6:** run
against the provisioned briefing workspace (NOT demo-gp — demo-gp
produces all-NO_SOURCE rows for the new templates). Verifier opens a real
browser, sees ≥1 OPENABLE row (clicks → real scan) and, *if the
legitimate seed contains one*, ≥1 visibly-UNRESOLVABLE row.
**Failure-to-produce branch (mandatory):** if the legitimate seed has no
orphan, the recorded outcome is verbatim: *"orphan-rendering remains
probe-verified-only (verify_query_phase0 probe iv/v + unit form); browser
confirmed OPENABLE and NO_SOURCE only; no orphan injected to complete the
demo."* This is the **expected** path (§1.6).

> **DISCHARGED 2026-05-16 — corrected outcome (a category error was
> caught; original preserved above for audit, same discipline as every
> tightened overclaim in this phase).** ~~Pre-committed: "browser
> confirmed OPENABLE and NO_SOURCE on the provisioned workspace".~~ This
> was a **category error**: the promote path stamps `source_document_id`
> on every fact, so a promote-only workspace (demo-briefing) structurally
> **cannot** produce a NO_SOURCE row — the single-workspace wording was
> incoherent at planning time. Live distribution exposed it: provisioned
> ws = `openable:4, no_source:0, unresolvable:0`. **Corrected, verified
> via the real `:8002` HTTP chain (real JWT, real `clinical_query` gate,
> real resolver, real signed URL):** OPENABLE confirmed on
> `demo-briefing-workspace-001` (`GET signed_url` → HTTP 200, `%PDF-1.4`
> — the scan opens); NO_SOURCE confirmed on `demo-gp-workspace-001` (the
> NULL-sourced corpus where the category naturally occurs, `{'no_source':
> 2}`); orphan probe-verified-only, **no orphan injected on any
> workspace** (pre-committed branch held). The honest demo is
> intrinsically **two-workspace** — the only single-workspace way to show
> all categories is to manufacture one, which the discipline forbids;
> the corrected framing is the bar stated correctly, not relaxed.
> Residual — corrected against the running system (original preserved):
> ~~"the literal human pixel-click in `:3001` is the reviewer's DoD
> checkbox."~~ Wrong on two counts: the frontend is on `:3000` not
> `:3001` (the `:3001→:8002→:5001` label is stale; there is no `:5001`),
> and **PR B has no query UI** (briefing UI is Phase 4) and
> `demo-briefing-workspace-001` has no login — so the in-app pixel-click
> is **Phase-4-gated, not a PR B step** (PR A-shape deferral). PR B
> stands on the backend real-stack verification (above) + an optional
> Swagger eyeball (`:8002/docs`, `POST /api/query/run`) of the actual
> output. All backend the eventual Phase-4 click will exercise (incl.
> the PDF fetched through the signed URL) is already mechanically
> confirmed.

### (ii) Seeded briefing workspace provisioned for briefing verification FIRST
Empirical answer to the briefing's question: a workspace both entitled
AND data-bearing **exists** — demo-gp, for not_seen_since /
active_medications / recent_consultations / open_documents (NOT
diagnosis/vitals/lab). So the briefing-set **functional** verification
runs on real demo-gp (not a fixture). But demo-gp's facts are all
NULL-sourced (§1.6), so the **provenance-resolution** property needs a
provisioned platform-tier workspace whose **primary stated purpose is
verifying the briefing templates' provenance-resolution end-to-end on an
entitled workspace** — seeded via the real promote-from-document path,
NOT seeded-to-order with a manufactured resolvable+orphan pair (Option
2's rejected anti-pattern through the back door). Whatever natural
distribution that legitimate seed yields is what (i) rides on.

### (iii) Construct-validity honesty
§4's ledger is a literal table in the PR B description + postmortem.
Every 0-corpus case labelled schema-correct-not-corpus-exercised; test
names carry the label; docstrings reuse PR A's exact wording. Integration
reversed/two-source branches are `xfail(reason=...)` with the reason
string asserted, so green CI cannot be misread as corpus-tested.

---

## 3. Deliverables, file-by-file

### 3.1 Template modules (`backend/ontology/query/templates/`)
Each mirrors `patients_with_diagnosis_prefix.py` (typed ParamSpec +
edge validators, `output_columns` includes `"provenance"`, `query_`
rpc_name, `data_maturity` from §1.2):
1. `patients_with_diagnosis_prefix.py` — **modified, version→2**, add
   `order_by` enum (`"name"`|`"last_consultation"`). Same module ⇒
   `registered.py` import unchanged.
2. `patients_not_seen_since.py` — `days_since` int (1–3650, default 180).
3. `patient_active_medications.py` — `patient_id` str.
4. `patient_recent_consultations.py` — `patient_id` str, `limit` int.
5. `patients_with_abnormal_recent_vitals.py` — `within_days` int.
   `data_maturity="thin"`.
6. `patient_open_documents.py` — `patient_id` str optional, `limit` int.
   Provenance self-referential (the doc IS the source).
7. `patients_with_lab_threshold.py` — `test_code` str, `min_value`
   float. `data_maturity="schema_only"`.
`registered.py` — add 6 import lines.

### 3.2 Migration `026_query_layer_briefing_templates.sql`
024's discipline header reproduced; `BEGIN;`; **7 `CREATE OR REPLACE
FUNCTION query_*`** (6 new + diagnosis re-creation for `order_by`); each
`LANGUAGE sql STABLE`, `p_workspace_id TEXT` first, `WHERE
<fact>.workspace_id = p_workspace_id AND <patients>.deleted_at IS NULL`,
`LIMIT GREATEST(1, LEAST(p_limit,500))` where applicable, provenance
`jsonb_build_object(...)` built in the producing join. **Load-bearing:
emit `'source_kind', CASE WHEN <fact>.source_document_id IS NULL THEN
'live_entry' ELSE '<factkind>' END`** in every function — demo-gp's
entire briefing corpus is NULL-sourced (§1.6) and would otherwise raise
`provenance_missing` at the runner. `COMMENT ON FUNCTION` each. **Trailing
`NOTIFY pgrst, 'reload schema';` then `COMMIT;`** (mandatory; 026 adds
functions, unlike 025).

### 3.3 Ugly-case handling in `provenance.py` (extend, structural style preserved)
**(i) Low-confidence — Decision #1, binary only.** New workspace-scoped
batch lookup `gp_validation_sessions.select("document_id,
confidence_scores").in_("document_id", needed).eq("workspace_id", ws)`.
`ResolvedSource` gains `quality: Optional[SourceQuality]`;
`SourceQuality = {section_confidence_recoverable: bool, superseded:
bool}` — booleans only. Citation suffix: recoverable → ` — extraction
quality not individually verified (document-level check available)`; not
→ ` — extraction quality not verified`. Never "low-confidence", never a
%, never a binary implying the fact was scored. CI string-scan enforces.
**(ii) Reversed/superseded — Decision #2.** Batch lookup
`action_audit_log.select("parameters, reversed_by_audit_id").eq("action_name",
"PromoteDocumentToPatientRecord").eq("workspace_id", ws)`; superseded if
`source_document_id` ∈ reversed set AND no later non-reversed promotion.
Per-row `quality.superseded=True` + citation ` (source promotion was
reversed — fact may be stale)`. **`ResolvedQueryResult` gains mandatory
`superseded_count`**; extend the existing `__post_init__` drift invariant
with the sibling assertion (same drift-impossible pattern as
`unresolvable_count`). Construct-validity-only (§1.4): unit-tested on
fabricated audit rows; integration branch xfail-with-asserted-reason.
**(iii) Two-document — see §7 decision 1** (recommended: optional
additive `additional_sources` on `ResolvedRow`, single-source path
untouched, fabricated-unit-test only, labelled construct-validity-only).

### 3.4 `tests/test_query_templates_integration.py` (new, RUN_INTEGRATION-gated)
`load_dotenv("backend/.env")` (corrected). Per template as
`demo-gp-workspace-001`: 4 data-bearing templates assert non-empty
correct rows; diagnosis/vitals/lab assert empty/thin matching
`data_maturity`. Zero cross-workspace leakage (assert no typec ids).
EXPLAIN with PR A's small-table heuristic. Three ugly branches:
low-conf suffix (xfail if no doc-sourced openable row on entitled
corpus), reversed (xfail construct-validity-only §1.4), two-source
(xfail §1.5). **Highest-priority regression:** the 15 orphaned diagnoses
still resolve UNRESOLVABLE with truncated-id through the new code path.

### 3.5 CI invariant extensions in `test_query_layer_invariants.py`
`test_resolvedqueryresult_superseded_aggregate_cannot_drift_from_rows`;
`test_superseded_not_counted_as_unresolvable` (+ vice-versa);
`test_citation_never_says_low_confidence_or_percentage`;
`test_superseded_suffix_is_locked_wording`;
`test_026_migration_ends_with_notify_pgrst` (reuse `_strip_sql_comments`);
**`test_additional_sources_is_inert_on_current_corpus` — the Decision-1
required-rider named gate: asserts `additional_sources is None` for 100%
of rows the resolver produces over the current corpus (driven through
the real resolver, not just the dataclass), so the two-source field's
inertness is a tested invariant, not an assumption. A future change that
silently begins populating it fails CI here. Same drift-impossible
status as `superseded_count`/`unresolvable_count`.**
The 6 new templates are **automatically** covered by the existing
`test_every_template_declares_provenance` /
`_rpc_is_query_namespaced` / `_no_template_lets_the_caller_supply_the_workspace`
(they iterate `all_templates()`) — the PR A gate guards them by
construction; state this in the PR description.

### 3.6 `verify_query_phase0.py` — added probe (v)
Read-only, retry-on-cold-cache: (a) the 15 orphaned diagnoses still
UNRESOLVABLE after the new gvs/audit lookups (no PR A regression); (b) an
OPENABLE doc-sourced row still OPENABLE and now carries `quality` with
`section_confidence_recoverable` matching the 1/16 reality; (c)
`superseded_count==0` on live corpus, printing "construct-validity-only
confirmed". Exit non-zero only on a genuine regression.

---

## 4. Construct-validity ledger

| Case | Corpus-exercisable? | Live numbers (2026-05-16) | Verified by | Label |
|---|---|---|---|---|
| Orphaned → visibly UNRESOLVABLE | **Yes (dominant)** | 15/24 | probe iv+v, integration, unit | corpus-demonstrated |
| Present → OPENABLE + honest citation | **Yes** | typec 1ea97a59; demo-gp 15 docs file_path-present | probe iv, integration | corpus-demonstrated |
| Briefing templates correct + tenant-scoped | **Yes on demo-gp** | 38 enc/20 presc/15 docs | integration as demo-gp + zero-typec-leak | corpus-demonstrated |
| NO_SOURCE (live_entry) rendering | **Yes, dominant on demo-gp** | 100% demo-gp briefing facts NULL-sourced | integration + browser (i) | corpus-demonstrated |
| Low-confidence binary suffix | Partially | 1/16 recoverable | unit both branches + probe v + integration xfail-if-none | recoverability corpus-demonstrated; rendering probe-verified |
| Reversed/superseded (row+aggregate) | **No** | 17 reversed, **0 live facts** | fabricated unit `_CONSTRUCT_VALIDITY_ONLY`; integration xfail asserted; probe v prints 0 | **schema-correct-not-corpus-exercised** |
| Two-document fact | **No** | **0** (dx & presc); no multi-source schema | fabricated unit; no schema repr | **schema-correct-not-corpus-exercised** |
| Cross-tenant id leak refusal | **No** | 0 (all missing ids missing globally) | PR A's existing labelled test | **schema-correct-not-corpus-exercised** (inherited) |
| Real-chain OPENABLE rendering | **Yes** | demo-briefing: 4 openable; signed_url→`%PDF` HTTP 200 | #1c real `:8002` HTTP chain | corpus-demonstrated (one real workspace) |
| Real-chain NO_SOURCE rendering | **Yes** | demo-gp: `{'no_source':2}` via real HTTP | #1c real `:8002` HTTP chain | corpus-demonstrated (on the NULL-sourced corpus where it naturally occurs) |
| ~~Single-workspace OPENABLE+NO_SOURCE~~ (pre-committed) | **No — category error** | provisioned ws `openable:4,no_source:0` | corrected in #1c | promote stamps source on every fact ⇒ promote-only ws cannot produce NO_SOURCE; honest demo is two-workspace, no category manufactured |
| Browser orphan rendering | **No on any entitled ws** | entitled ws have no orphan by construction | probe iv/v + unit; no injection | orphan **probe-verified-only** (pre-committed branch held) |

No fabricated fixture appears anywhere as corpus evidence.

---

## 5. Migration / PostgREST discipline
026 ends with `NOTIFY pgrst, 'reload schema';` then `COMMIT;` (CI
enforced). 026 strictly after 025. The diagnosis re-creation supersedes
024's definition (registry v2>v1). **No new tables in PR B — confirmed**
(`briefing_items` is PR D). Reads existing tables only ⇒ no RLS-deny-all
migration, no PR 5 tenant-guard table addition, no ActionExecutor
routing (read-only; `run_template` chokepoint; no audit row). All three
batch lookups (digitised_documents, gp_validation_sessions,
action_audit_log) carry `.eq("workspace_id", ws)` — correctness + tenant
scope, same as PR A.

---

## 6. Risks (Phase-3 honesty standard)
- **demo-gp NULL-source reality (new, material).** (a) PL/pgSQL must emit
  `live_entry` on NULL source or every demo-gp briefing row raises
  `provenance_missing`. (b) Browser contrast (i) cannot be shown on
  demo-gp; depends on the provisioned ws whose clean seed will likely
  have no orphan → pre-committed honest outcome: OPENABLE+NO_SOURCE
  browser-confirmed, orphan probe-verified-only. **Risk: review pressure
  recurs to inject an orphan to "complete" the click-through — riders
  (ii)/(iii) forbid it; named here while it can be seen.**
- `prescription_items` no `prescription_id` index — EXPLAIN uses PR A
  small-table heuristic; future scale index in postmortem. **Postmortem
  sentence (suggested-at-review, adopted): the `idx_prescription_items_prescription_id`
  deferral and PR D's named-not-built conversion-instrumentation carry
  share a single trigger condition — the first real customer with real
  data volume. Record them as one trigger so that when that customer
  lands the "what gets slow / what needs measuring" review is one
  review, not two separately rediscovered.**
- `action_name` vs `action_type` — wrong literal silently reports
  `superseded_count=0` for the wrong reason. Implementer + fabricated
  fixture must use `action_name`.
- Confidence coarse/1-in-16 (Decision #1 unchanged); reversed/two-source
  0/0; `doc_type` 0/20 — all carried from PR A's register, re-verified.
- Two-source contract surface expansion for a 0-corpus case — §7 dec 1.

---

## 7. Decisions resolved at review (LOCKED, with required riders)

**Decision 1 — Two-source contract shape → (a), with a required
inertness invariant.** Locked: additive optional `additional_sources:
Optional[List[ResolvedSource]]` on `ResolvedRow`. Reasoning (why not the
purist (c)): the two-source case is not "cannot occur" — it is "cannot
occur *yet* on *this* corpus because the promote path currently produces
single-source facts"; it is structurally inevitable the first time a
fact is assembled from two documents (a diagnosis confirmed by both a
referral letter and a lab report — clinically normal). (c) creates a
circular deferral (contract waits for schema, schema waits for need,
need *is* the contract); (a) breaks it cheaply. (b) rejected
(scope-balloon — touches API/frontend/PR A envelope for a 0-corpus
case). **REQUIRED RIDER:** the CI invariant set must assert
`additional_sources is None` for **100% of current-corpus rows** — the
field's *inertness* is itself a tested, drift-impossible invariant (same
logic as `superseded_count`), so a future change that silently starts
populating it cannot pass CI. Construct-validity-only AND
currently-always-empty are *both* enforced, not assumed. (Named
explicitly in §3.5.)

**Decision 2 — Provisioning ownership → (a) authored in PR B, with a
required real-promote-path rider.** Locked: the provisioning script is a
PR B deliverable under `backend/scripts/` (precedent
`provision_typec_demo.py`). **REQUIRED RIDER (the legitimacy test, made
mechanical):** the script seeds **exclusively through the real
`PromoteDocumentToPatientRecord` action path** — the same executor code
path production runs. **Any direct fact-table INSERT in that script is
the seeded-to-order anti-pattern and fails review.** The mechanical
test of legitimacy: *does the script call the same action code path
production uses?* If it would need to bypass the promote path to produce
a desired demo distribution, that bypass *is* the proof it is
seeded-to-order. **Whatever orphan/resolvable distribution the real path
naturally yields is what carried-constraint (i) rides on; if it yields
no orphan the recorded outcome is verbatim "orphan-rendering
probe-verified-only, no orphan injected" — and this pre-committed
failure-to-produce wording lives in the provisioning script's own header
comment, not only in this plan, so the constraint travels with the
artifact.**

(No other premise probe surfaced anything the locked decisions don't
cover. #1–#4 all corpus-re-verified, unchanged.)

---

## 8. What PR B earns when it lands (honest, residual limits named)
- 6 new + 1 extended registered, tenant-scoped, index-eligible,
  provenance-verifiable templates on the same safe HTTP surface. **Precise
  inheritance claim (tightened at review — the "earns" section must not
  absorb a verification it didn't do):** the *declaration* and
  *tenant-scope* invariants ARE structurally inherited — the iterating CI
  invariants (`test_every_template_declares_provenance`,
  `_rpc_is_query_namespaced`, `_no_template_lets_the_caller_supply_the_workspace`)
  cover the six new templates by construction, zero new code. But
  **resolution-correctness is NOT inherited**: each new template builds
  its provenance JSONB in its *own* hand-written PL/pgSQL function over a
  *different* fact table and join (migration 026, seven functions). A
  function that builds provenance with a wrong column or join yields a
  blob the shared resolver faithfully resolves to the wrong thing or to
  nothing. Resolution-correctness for each new template is therefore
  **re-verified per-template against live data** by probe (v) and the
  integration suite — it is *not* inherited. The resolver is extended,
  its `__post_init__` invariants preserved.
- The dead-link failure (62%, re-verified 15/24) stays the defended,
  dominant, corpus-demonstrated case; PR B adds a live regression guard
  so the new lookups can't silently regress it. The reframed
  safety-language stands exactly: verifiable provenance defends the
  dead-link failure; wrong-extraction behind a live link stays
  checkable-but-not-checked, not closed.
- Reversed-source / two-source ship with built, unit-tested,
  structurally-enforced plumbing (`superseded_count` with the same
  drift-impossible invariant as `unresolvable_count`) labelled
  schema-correct-not-corpus-exercised everywhere — never claimed tested
  on real data.
- Decision #1 ships locked: binary, no score, no threshold, two exact
  phrases, "low-confidence"/% made impossible by a CI string-scan.

**Residual limits, unsoftened:** on the only naturally-entitled
workspace every briefing fact is NULL-sourced, so the human-visible
openable-vs-unresolvable browser contrast is delivered against a
separately-provisioned workspace, and the orphan-rendering case will
most likely be browser-unconfirmed and recorded probe-verified-only — no
orphan injected to manufacture it. Lab-threshold stays `schema_only`,
abnormal-vitals `thin` (honest `data_maturity`, not hidden empties).
Extraction correctness / PII-NL / standing remain out of scope (PR C/D
and upstream).
