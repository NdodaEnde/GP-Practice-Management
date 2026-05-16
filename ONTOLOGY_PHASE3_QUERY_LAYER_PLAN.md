# Phase 3 — The Query Layer: PR-by-PR Implementation Plan

> Status tracker (update as PRs land):
> - **PR 6** — query foundation + first compiled template — ✅ merged-pending (#13)
> - **PR 7** — briefing/pre-consult query set — ⬜ not started
> - **PR 8** — HTTP query API — ⬜ not started
> - **PR 9** — narrow NL layer (ships disabled) — ⬜ not started
> - **PR 10** — briefing_items + materialiser — ⬜ not started
> - **PR 11** — invariant hardening + postmortem — ⬜ not started
>
> User decisions locked at planning time:
> - Query shapes: use the plan's evidence-based set (confirmed)
> - NL layer: build disabled, decide provider later (confirmed)
> - Briefing UI: deferred to Phase 4 (confirmed)
> - Scheduler / access-logging / clinical_query capability: ride the plan's
>   recommendation, verified in their respective PRs

---

## Context

Phases 0–2 built the ontology spine (typed `Patient`/`Document`/`Consultation`
objects, a link registry) and made every mutation a first-class audited
`Action` flowing through `app/actions/executor.py` with a hard-won "thin
Python orchestrator + PL/pgSQL RPC for the ACID/locking part" pattern.
Phase 3 turns the spine load-bearing for *reads*: clinicians ask questions,
get ranked answers, every answer carries its source document. The roadmap's
four sub-goals (structured query primitives → narrow NL layer →
provenance-in-every-answer → standing-query materialisation) are correctly
sequenced but each is a different risk class. The empirical probe of the
live DB changes the plan materially: clinical *write* tables are
well-populated (67 patients, 79 encounters, 45 prescriptions, 24 diagnoses,
`document_embeddings` already at 76 rows with an ivfflat index) but the lab
corpus is effectively empty (1 `lab_results` row, `test_code` NULL, no
LOINC), and `lab_results` has no `patient_id`/`workspace_id` (joins through
`lab_orders`). The roadmap's flagship example query
(`has_lab_result(loinc="4548-4", ...)`) is therefore aspirational against
current data and must be planned as schema-correct-but-data-thin, not as
the demo. supabase-py REST as `service_role` (RLS-bypassing) remains the
only mutation/read path from Python; complex joins/aggregations/pgvector
force PL/pgSQL RPCs or the psycopg2 `DATABASE_URL` path, exactly as in
Phase 2.

## Design choices

**1. The query layer is a compiler to PL/pgSQL RPCs, not an ORM over
PostgREST.** The roadmap's example query spans Patient → Diagnosis (FK
join) → LabResult (two-hop join through `lab_orders`) → ordering on a
denormalised summary. supabase-py's PostgREST builder cannot express
multi-table joins with per-branch filters, `EXISTS` sub-selects, or
`embedding <=> $1` ordering. The established and *only proven* pattern
(migrations 011, 015, 021, 022) is: a Python builder produces a structured
query IR, a small set of parameterised PL/pgSQL `STABLE` functions execute
it, the supabase client calls them via `.rpc()`. *Rejected alternative:*
the direct psycopg2 `DATABASE_URL` path for ad-hoc SQL. It works (used for
migrations) and bypasses RLS, but it (a) duplicates the connection/secrets
surface inside request handlers, (b) makes the PR 5 AST tenant-guard blind
(the guard only understands `supabase.table(...)` chains — raw psycopg2 SQL
is invisible to it, so a missing `workspace_id` would not trip CI), and (c)
breaks the symmetry with the action layer. RPCs keep tenant scoping a
*mandatory function parameter* (`p_workspace_id`), reviewable in one file.
psycopg2-direct is reserved for migrations and Phase-0-style verification
scripts only.

**2. Query shapes are a closed, hand-written registry — not a generic
query algebra.** The roadmap explicitly says "start with the 5–10 query
shapes that matter." We ship a `QueryTemplate` registry where each template
is (a) a named, versioned, parameterised query with a typed parameter
schema, (b) backed by exactly one reviewed PL/pgSQL function, (c)
tenant-scoped by construction. New shapes are new registry entries + one
function, mirroring how the action registry grew. *Rejected alternative:* a
fluent `Patient.where(...).has_diagnosis(...)` builder that compiles
arbitrary chains to SQL. That is the roadmap's *illustrative texture*, not
a delivery contract — building a safe general compiler (join planning,
index selection, injection-proof predicate composition, EXPLAIN regression
guards) is a multi-month research project and an unbounded attack surface.
We deliver the *ergonomics* of that example for the fixed template set; the
fluent API, if ever wanted, becomes sugar over the registry later.

**3. Provenance is a column in the result row contract, enforced by a
result-shape test — not threaded by convention.** Every template's
PL/pgSQL function MUST return a `provenance` JSONB column per row:
`{source_document_id, source_kind, occurred_on, page, snippet}`. A unit
test introspects every registered template's declared output columns and
fails CI if `provenance` is absent. This makes "every answer has a source"
a structural property (the Phase 2 discipline: no fake properties), not a
UI afterthought that silently rots. *Rejected alternative:* a post-query
Python enrichment pass that re-queries `digitised_documents` to attach
sources. It works but is N+1, drifts from the query's actual join, and can
attribute the wrong document when a fact has multiple sources — the
provenance must come from the same join that produced the fact.

**4. The NL layer is a constrained intent classifier over the closed
template set, and PII never leaves the box without an explicit user
decision.** The clinician's free-text question goes to an LLM whose *only*
job is to output `{template_id, params}` constrained to the registered
template IDs and their typed param schemas (function/tool-calling with an
enum of template IDs, not free-form SQL). The question text may contain PII
(patient names). Whether that text — and which provider — is allowed is a
**user decision** (locked: build disabled, decide later). The classifier
returns "I can't answer that yet" with the answerable list for
unmatched/low-confidence questions, never a guessed query. *Rejected
outright:* NL2SQL (LLM emits SQL) — unbounded injection/exfiltration
surface, ungovernable tenant scoping, the "research project" the roadmap
warns against.

**5. Standing queries reuse the existing scheduler the platform already
runs.** The platform already runs background workers
(`document_watcher.py`, `digitisation_export_worker.py`) as long-lived
processes. A standing query is a registered
`(template_id, params, schedule, workspace_id)` row whose execution writes
rows into a new `briefing_items` table via the *same* RPC path. Phase 3
ships the table, the materialiser, a manual trigger endpoint, and a single
scheduler tick inside the existing worker — **not** pg_cron (not enabled;
project-level change; would run as superuser outside tenant discipline),
**not** Supabase Edge, **not** a new daemon. The thin briefing UI is
**deferred to Phase 4** per the roadmap's own framing.

**6. The query layer is read-only and does NOT route through the
ActionExecutor.** Queries are not mutations; they get no `action_audit_log`
row. POPIA query-access-logging is a real future requirement but
conflating it with the mutation audit log would pollute
`affected_objects` semantics. Deferred to Phase 5; the single
`run_template()` chokepoint is built so a logging decorator slots in later
without a refactor.

---

## PR breakdown

Total: **6 PRs (PR 6–11)**. Each independently mergeable. LoC estimates
inflated ~40–50% over first instinct because the PR 3 estimate was 40%
low — the dominant cost is PL/pgSQL + verification, not Python.

### PR 6 — Query IR + registry + ONE compiled template, end-to-end ✅

**Load-bearing property:** a structured query expressed in ontology terms
compiles to a tenant-scoped PL/pgSQL function, executes against real dev
data, every result row carries provenance — proven on one shape before the
pattern is replicated.

**Deliverables:** `ontology/query/{spec,registry,runner,result}.py`;
`ontology/query/templates/patients_with_diagnosis_prefix.py`; migration
`024_query_layer_diagnosis_template.sql`; `tests/test_query_layer_unit.py`;
`scripts/verify_query_phase0.py`.

**Verification (the Phase-0 gate):** confirm a `STABLE` function returning
`TABLE(... jsonb)` round-trips via `.rpc()` as typed dict rows; confirm
`diagnoses.patient_id` ⋈ `patients.id` TEXT=TEXT no cast; `EXPLAIN` index
usage. If (i) fails, retreat to psycopg2-direct + extend the PR 5 tenant
guard.

**OUTCOME (actual):** Phase-0 CONFIRMED. Also surfaced the operational
finding that every query migration must end with
`NOTIFY pgrst, 'reload schema'` or the RPC 404s (PGRST202) until cache
reload. Baked into migration 024; standing requirement for PR 7+.

**~1,330 LoC.**

### PR 7 — The morning-briefing / pre-consult query template set

**Load-bearing property:** the 5–8 query shapes the briefing and
pre-consult brief are composed from all exist, tenant-scoped,
provenance-bearing, index-backed against real data.

**Proposed set (locked — evidence-based):**
1. `patients_with_diagnosis_prefix` (PR 6, extend with `order_by last_consultation`)
2. `patients_not_seen_since(months)` — recall, uses `encounters.encounter_date` + `idx_encounters_date`
3. `patient_active_medications(patient_id)` — pre-consult med list from `prescriptions`+`prescription_items`
4. `patient_recent_consultations(patient_id, within_days)` — pre-consult timeline
5. `patients_with_abnormal_recent_vitals(...)` — e.g. `bp_systolic > threshold` (vitals thin: 5 rows — ship schema-correct, document thinness)
6. `patient_open_documents(patient_id)` — un-promoted/awaiting-validation docs
7. lab-threshold shape — **built schema-correct, marked data-thin** (1 row, no LOINC; ready when lab ingestion exists, not faked)

**Deliverables:** 6 template modules; migration
`025_query_layer_briefing_templates.sql`; extend unit tests +
`test_query_templates_integration.py` (RUN_INTEGRATION gated).

**Verification:** each template against live dev DB; assert zero
cross-workspace leakage (run as A, assert no B rows); every row has
provenance OR explicit `source_kind="live_entry"`; `EXPLAIN` index usage on
the two cohort queries; lab template asserted "0 rows, plan valid" with
documented thinness.

**~1,430 LoC.**

### PR 8 — Provenance hardening + the query API endpoint

**Load-bearing property:** the query layer is reachable over HTTP,
tenant-scoped from the auth context (never a client-supplied workspace),
provenance deep-links to the actual source scan.

**Deliverables:** `app/api/query.py` (`POST /api/query/run` —
`workspace_id` from `get_current_user` only, never body; new
`clinical_query` capability gate; rate limiter reusing the digitisation
pattern); migration `026_query_capability_seed.sql`;
`ontology/query/provenance.py` (batch-resolve `source_document_id` →
citation string + deep-link, one workspace-scoped query);
`tests/test_query_api.py`.

**Verification:** TestClient proves a forged body `workspace_id` cannot
read another workspace; live smoke through the proxy chain
(`:3001 → :8002 → :5001`) confirms one provenance deep-link opens the
right scan.

**~1,100 LoC.**

### PR 9 — The narrow NL layer (ships DISABLED)

**Load-bearing property:** ~20 hand-mapped clinician question patterns
classify to a registered template + typed params with a hard refusal for
anything outside the set, and no PII-bearing query text reaches an LLM
unless the user has explicitly authorised the provider.

**Deliverables:** `app/services/nl_query.py` (constrained tool-call mode;
the tool schema is *generated from the PR 6 registry* so it can't drift;
`NL_QUERY_LLM_ENABLED` defaults **off** so merging cannot leak PII);
`POST /api/query/ask`; `tests/test_nl_query.py` (20-question golden set vs
a **mocked** LLM — deterministic, no network in CI; refusal path; PII-gate
default-off); `scripts/nl_query_eval.py` (opt-in real-LLM eval, never CI).

**Verification:** golden set ≥18/20 against the mocked classifier
(verifies wiring not LLM intelligence); real accuracy reported in the PR
description as an honest measured number, NOT a CI gate.

**~1,180 LoC.**

### PR 10 — `briefing_items` + materialiser (standing queries), no UI

**Load-bearing property:** a registered standing query runs on a schedule
inside the existing worker process and writes provenance-bearing rows into
`briefing_items`, idempotently, tenant-scoped.

**Deliverables:** migration `027_briefing_items.sql` (RLS-enabled deny-all
to anon, matching migration 018 discipline; add `briefing_items` to the PR
5 tenant guard's table set — the ratchet only goes down);
`ontology/query/standing.py` (StandingQuery registry +
`materialise_standing_queries()` — wipe-and-reinsert per
`(workspace_id, kind, as_of_date)`); worker scheduler tick;
`POST /api/query/briefing/refresh` (manual) + `GET /api/query/briefing`;
`tests/test_standing_queries.py`.

**Verification:** run materialiser twice → stable row count (idempotent);
tenant scoping; provenance preserved; confirm the scheduler tick actually
fires inside the worker process (verify the runtime-topology assumption,
pg_cron the documented-but-rejected fallback).

**~1,090 LoC.**

### PR 11 — Hardening, docs, Phase 3 close-out

**Load-bearing property:** the query layer's safety invariants are tested
as invariants; deferrals are documented as deliberate.

**Deliverables:** `tests/test_query_layer_invariants.py` (every template's
RPC takes `p_workspace_id`; every template declares `provenance`; no
template module bypasses `run_template()`);
`scripts/query_explain_regression.py`;
`ONTOLOGY_QUERY_LAYER_POSTMORTEM.md`.

**~600 LoC.**

**Total Phase 3: ~6,730 LoC across 6 PRs.** Largest under-estimate risk is
PR 9 (NL layer) if scope creeps.

## Risks

- **supabase-py REST can't do the joins — PL/pgSQL forced.** The one
  unproven assumption was PR 6's Phase-0 (i) — *now confirmed*. Retreat
  (psycopg2-direct → blind tenant guard) not needed.
- **The NL layer balloons into a research project (highest risk).**
  Mitigations: closed template enum (no NL2SQL), constrained tool-calling,
  schema generated from the registry, golden-set CI on a mocked LLM, real
  accuracy reported not gated. PR 9 is a *hand-mapped-template classifier
  MVP*, not arbitrary-question answering.
- **PII exposure to the LLM.** PR 9 defaults LLM disabled; enabling is a
  separate governance decision.
- **Provenance threading touches every query path.** A template that
  forgets it is a fake-property regression. Mitigated by PR 11's invariant
  test + PR 6's result-shape contract; until PR 11, a sloppy PR 7/8
  template could ship without it (option: pull PR 11's invariant test
  earlier).
- **Lab data effectively absent (1 row, no LOINC, no patient_id).** The
  roadmap's flagship query is undeliverable on real data in Phase 3.
  Shipped schema-correct + documented-thin, never faked. The risk is
  *expectation*, not engineering.
- **Vitals thin (5 rows).** Abnormal-vitals cohort query real but near-
  empty on dev. Same honesty discipline.
- **Standing-query scheduler** assumes the existing worker is a persistent
  process that can host a tick. Verified empirically in PR 10; pg_cron the
  rejected-by-default fallback.
- **Heterogeneous TEXT identifiers** (postmortem scar). All
  `patient_id`/`id` joins are TEXT=TEXT, no `::uuid` cast (migration-015
  bug). Verified in PR 6.

## Underspecified decisions (status)

1. **Exact briefing query shapes** — RESOLVED: plan's evidence-based set.
2. **NL LLM provider / PII** — RESOLVED: build disabled, decide later.
3. **Scheduler mechanism** — ride the plan (tick in existing worker);
   verified in PR 10.
4. **Briefing UI in Phase 3?** — RESOLVED: no, deferred to Phase 4.
5. **Query access-logging (POPIA)** — Phase 5 deferral; chokepoint built
   in PR 6.
6. **`clinical_query` capability** — seeded NOT-in-foundation per the PR 3
   `patient_admin` precedent; confirm at PR 8.

## What Phase 3 earns when it lands

When PR 11 merges, SurgiScan stops being a digitiser and becomes queryable
clinical infrastructure: a clinician asks one of ~20 known questions in
plain language and gets a ranked, tenant-scoped answer where *every single
row carries the scanned document it came from* — "Mrs Khumalo, Type 2
diabetes (recorded 8 Mar 2026, from Lancet referral letter, page 1)" with a
one-click link to the actual scan. The morning briefing and pre-consult
brief are no longer features to build — they are registered standing
queries that already materialise on a schedule into `briefing_items`,
waiting for the Phase 4 UI. The platform earns this *honestly*: the query
layer is provenance-bearing by construction (a CI invariant), tenant-scoped
by construction (the same discipline PR 5's guard enforces for writes), and
the things it cannot yet do — lab-threshold questions on absent data,
questions outside the 20 patterns, see PII without a governance decision —
are documented deferrals, not silent gaps.
