# Phase 3 — PR D Implementation Plan: Standing-Query Materialisation (no UI) + Phase 3 Close-Out

> **Status:** plan APPROVED at review (same bar as PR A / PR B / PR C / the executor plans). Grounded in fresh live-codebase + live-DB probes 2026-05-17, HEAD `d3914d8`. **All six decisions CLOSED (§6, LOCKED). Two required changes applied: (1) §5 ledger + §2.1 §E carry the orphaned-source-survives-materialisation property in the *unverified-on-production-path* column, unsoftened — the entitled corpus contains no orphan, so it is code-path-proven via a test-only injected workspace arg, NOT production-corpus-demonstrated (fourth occurrence of the earns-overclaim cure, applied in the close-out artifact because that is the document read most adversarially); (2) §2.4 distinguishes the executable presence-check (automatable, necessary, build-failing) from the human-verified checklist (the sufficiency condition, a human judgement at review).** Build order is load-bearing: the three close-out artifacts + the §2.4 gate green BEFORE the standing-query code is complete — the PR genuinely not mergeable with §3 green and §2.4 red, as the actual build order, not a slogan.
>
> **Premise corrections this probe surfaced (norm #1 — verify before asserting; same discipline as PR B's `action_name`≠`action_type` and PR C's provider/flag reality):**
> - **The umbrella's worker-topology assumption is PARTIALLY FALSE and materially underspecified.** Design choice #5 says "reuse the existing long-lived worker; one scheduler tick." A long-lived worker DOES exist (`app/services/document_watcher.py` `DocumentWatcher`, an asyncio `while self._running: … await asyncio.sleep(N)` loop started in `server.py`'s `@app.on_event("startup")`). **But it is a single-workspace singleton hard-bound to `DEMO_WORKSPACE_ID`, not a multi-tenant scheduler**, its loop is private to the `DocumentWatcher` class (not a generic tick host), and it is wired through deprecated `@app.on_event` not a lifespan. "Reuse it" is not a free verb — see §1 Finding W and §3.3/§6.3 for the adapted (not silently-invented) topology.
> - **The 62% / 15-of-24 orphaned-source figure is now 60% / 15-of-25.** The orphan *count* is still exactly 15; one new sourced-but-present diagnosis was added since PR B (24→25 sourced). The post-mortem records the **count (15) as the permanent finding** and notes the denominator drift honestly — it does NOT cargo-cult "62%".
> - **`backend/.env`, not `../.env`** — re-confirmed (carried PR B/PR C correction).
> - **Exactly two workspaces are `clinical_query`-entitled** (`demo-gp-workspace-001`, `demo-briefing-workspace-001`) — not the umbrella-era "demo-gp only"; `demo-briefing-workspace-001` was provisioned in PR B. The materialiser's trusted workspace source enumerates entitled workspaces, and that set is 2, not 1.

---

## 1. Empirical findings (live codebase / DB)

All DB probes via the `verify_query_phase0.py` idiom: `load_dotenv('backend/.env')`, `psycopg2.connect(os.environ['DATABASE_URL'])`. Chokepoint probes via `PYTHONPATH=. .venv/bin/python` importing `ontology.query`.

### Finding W (Probe 1 — THE umbrella premise under test) — worker exists but is NOT what the umbrella assumed

- **A long-lived worker exists:** `backend/app/services/document_watcher.py`. `DocumentWatcher.start()` (`:59`) runs `await asyncio.gather(self._storage_scan_loop(), self._auto_process_loop())`. Both are genuine tick loops: `_storage_scan_loop` (`:108-116`) `while self._running: … await asyncio.sleep(self._scan_interval)`; `_auto_process_loop` (`:262-271`) same. Intervals from env (`WATCHER_SCAN_INTERVAL` default 60s, `:48`).
- **How it starts:** `server.py:5361` `@app.on_event("startup")` → `start_document_watcher(supabase, DEMO_WORKSPACE_ID)` (`:5370-5371`) → `_watcher_task = asyncio.create_task(watcher.start())` (`document_watcher.py:427`). Shutdown: `@app.on_event("shutdown")` → `stop_document_watcher()` (`server.py:5376-5382`) sets `_running=False` + cancels (`:432-444`).
- **The falsified part:** a **module-level single-workspace singleton** (`_watcher_instance`, `_watcher_task`, `:410-411`) constructed with **one** `workspace_id` = `DEMO_WORKSPACE_ID` (`server.py:41`, default `'demo-gp-workspace-001'`). NOT a multi-tenant scheduler; loops private to `DocumentWatcher`'s ingestion concern. No generic "tick host". `grep APScheduler|BackgroundScheduler|celery|schedule.every|run_forever` across `app/`,`server.py`,`ontology/` → only `document_watcher.py`+`server.py`. No scheduler lib, no pg_cron, no second daemon.
- **Consequence (adapt, do not silently invent):** design choice #5's literal "reuse the existing long-lived worker; one scheduler tick" is **directionally honoured but cannot be a no-op bolt-on**. Options (§6.3): **(D-W1, recommended)** a new small *independent* asyncio tick task started from the *same* `@app.on_event("startup")` host as the watcher — same process, NOT a new OS daemon, NOT pg_cron — because the watcher is single-workspace and bolting a multi-tenant materialiser into its private loop entangles two concerns; **(D-W2)** ship PR D manual-refresh-only with the tick explicitly deferred/flagged. pg_cron is the rejected-by-default fallback. Recorded in post-mortem §D as a premise empirically tested and found underspecified.

### Finding T (Probe 2) — `briefing_items` does not exist; RLS idiom confirmed

- No `briefing_items`/`%standing%` table exists. Migration 027 creates it greenfield.
- **Migration-018 RLS-deny-all idiom (027 mirrors verbatim):** `ALTER TABLE public.<t> ENABLE ROW LEVEL SECURITY;` with **no permissive policy** (`018:107-109`,`:29`). NOT `FORCE` (`018:36-41`), NOT `auth.*` policies (`018:43-48`). Verified live: core tenant tables `relrowsecurity=True`, 0 permissive policies → deny-all to non-bypass roles, the exact posture 027 reproduces.
- **PR 5 ratchet BASELINE:** `tests/test_tenant_query_isolation.py` — `TENANT_TABLES: Set[str]` (`:65-86`); `BASELINE: Set[str]` frozen `"relpath::lineno::table"` (`:206-335`); `test_no_new_unscoped_tenant_queries` (`:338`) fails on `current-BASELINE` AND `BASELINE-current`. Plan: add `"briefing_items"` to `TENANT_TABLES`; all `briefing_items` chains carry `.eq("workspace_id",…)` → zero new BASELINE keys (ratchet only goes down).

### Finding C (Probe 3) — chokepoint reuse confirmed from a non-HTTP context

- `run_template(sb, template_id, params, *, workspace_id)` then `resolve_provenance(sb, result, *, workspace_id)` **work verbatim from plain Python (non-FastAPI)** — verified driving `patients_not_seen_since`/`patients_with_diagnosis_prefix` with a service-role client. Neither touches fastapi/current_user/request (`runner.py:48-152`, `provenance.py:428-585`). Materialiser reuses them with **zero new data path** — §3 property structurally true, not hoped.
- `ResolvedQueryResult.to_dict()` (grounds `briefing_items` columns, not guessed): `{template_id,template_version,workspace_id,row_count,data_maturity,unresolvable_count,superseded_count,rows:[…]}`; each row `{**data, provenance:{…}, source:{status,openable,document_id,signed_url,citation,unresolvable_reason,quality}, additional_sources}`.
- **Highest-priority Phase-3 regression re-asserted live through the materialisation-shaped path:** `patients_with_diagnosis_prefix`(`I`) as `test-workspace-c9f4d540` (holds orphaned `I10`) → `statuses={'unresolvable':1}`, `unresolvable_count=1`, citation `source document no longer available (id …e15a71)`, `openable=False`. The dominant property survives the exact chokepoint the materialiser uses. §3.2 turns this into a named test.

### Finding S — OPENABLE/NO_SOURCE survive too

`demo-briefing-workspace-001` `patients_not_seen_since` → `{'openable':1}` (real signed URL). `demo-gp-workspace-001` → `{'no_source':31}` (NULL-sourced; correctly not counted unresolvable). All three honest states reproducible through the chokepoint.

### Finding E (Probe 4) — workspace enumeration: the trusted source

- `workspaces` table: `id text` PK; 37 ids. Trusted entitlement query: `practice_capabilities(p_practice_id text)->text[]` RPC (`app/services/entitlements.py:46-65`, migration 002). Membership: `'clinical_query' = ANY(practice_capabilities(<ws>))`.
- **Live: exactly 2 entitled** (`demo-briefing-workspace-001`, `demo-gp-workspace-001`); all 34 `test-workspace-*` + `typec-workspace-001` → False (typec=`module_digitisation`, ratchet-guarded; 025 honesty note holds). Materialiser iterates entitled `workspaces.id` — TRUSTED DB source, never caller input (§3.4).

### Finding P — `prescription_items` scale index still outstanding

Only `prescription_items_pkey`; **no `idx_prescription_items_prescription_id`**. 73 rows (was 51 at PR B); still seq-scan-acceptable. The PR-B-deferred index is genuinely still outstanding — the live fact the §2.3 shared-trigger sentence binds.

### Finding D — 15 of 25, not 15 of 24

Sourced diagnoses = **25** (was 24). Orphaned (doc missing globally) = **15** (unchanged). 15/25=60% (was 15/24=62%). Post-mortem records the permanent finding as the **stable count 15**, notes denominator is corpus-drift-sensitive, freezes no percentage. Construct-validity honesty applied to the close-out itself.

### Finding U — umbrella under-/over-specification

~950 LoC = order not contract (PR B's refusal of false precision). Worker tick "verified empirically here" — verified, underspecified, adapted §3.3. `briefing_items` columns grounded in Finding C's real shape. `as_of_date`/cadence/initial-kind-set unspecified → §6 open decisions, surfaced not resolved.

---

## 2. The three close-out artifacts — scoped FIRST, carried-constraint weight, the gate the standing-query code sits on top of

> **This section is the load-bearing part of PR D.** The standing-query materialisation is built *on top of a genuinely discharged close-out*, not alongside an assumed one. Tracked in memory `project_phase3_tracked_deferrals`; scoped here with PR B carried-constraint weight, BEFORE §3–§4, with "close-out discharged" made a checkable build-failing gate (§2.4).

### 2.1 Artifact (1) — the Phase 3 post-mortem (`ONTOLOGY_QUERY_LAYER_POSTMORTEM.md`)

New top-level doc, following `ONTOLOGY_INTEGRATION_POSTMORTEM.md`'s register. Required sections + exact load-bearing content:

- **§A. The permanent data-quality finding** (for a future backfill, NOT a deferral closed within Phase 3): *"15 sourced diagnoses on the dev corpus carry a `source_document_id` resolving to no `digitised_documents` row (orphaned by reverse/delete history; ids survive in `action_audit_log.affected_objects`). At PR A 15/24 (62%); at PR D close-out 15/25 (60%) — the orphan **count is stable at 15**; the denominator drifts with corpus growth, so the permanent finding is the count + mechanism, not the percentage. This is the dominant, measured failure the entire provenance-verifiable ordering exists to close. The query layer makes it **visibly unresolvable** (citation `source document no longer available (id …e15a71)`, `openable=False`, in `unresolvable_count`); it does NOT repair it. A future backfill (recover from `action_audit_log.affected_objects`, or tombstone the dangling ids) is named here and is OUT of Phase 3 scope."*
- **§B. Documented-thin / construct-validity ledger** (carried from PR B §4, re-verified): lab `schema_only`; vitals `thin`; reversed-source construct-validity-only (17 reversed, 0 live); two-source construct-validity-only (0, no schema); PR C NL mapping-correctness unverified-at-merge. Labelled exactly as PR B/C labelled — never re-fused. Includes the Phase-4 pixel-render close-condition (carried from PR B's DISCHARGED note).
- **§C. The permanent residual, in the umbrella Context §'s EXACT words:** *"Verifiable provenance defends exactly one failure: the dead-link failure … It does NOT defend the wrong-extraction failure … checkable by a motivated reader …; a clinician in a hurry and a prospecting doctor in a demo are not motivated readers. So wrong-extraction-behind-a-live-link is checkable-but-not-checked — a real residual risk Phase 3 surfaces and does NOT close. Extraction correctness is upstream of the query layer and out of Phase 3 scope."*
- **§D. The worker-topology premise test** (Finding W): records design choice #5 was empirically tested at PR D and found underspecified; the resolution (D-W1/D-W2 per §6.3) recorded so a future maintainer does not re-derive wrongly. Same discipline as PR B recording `action_name`≠`action_type`.
- **§E. What Phase 3 earned (proven) vs did not (unverified/residual)** — points to §5; must NOT fuse them.

### 2.2 Artifact (2) — the MANDATORY named-not-built conversion-instrumentation scope note (GUARDED HARDEST)

Most likely to evaporate ("nothing to build here yet") — no code, no demo, *precisely because it cannot until customers exist*, which is exactly why it must be named, specific, structural. It is the entire reason the digitisation-wedge thesis stays testable the day cold-calling lands a practice.

**Lives in TWO places (travels with the artifact — PR B discipline):** (a) a post-mortem section; (b) a module docstring block in `ontology/query/standing.py` itself.

**Exact proposed wording (written here so review can adjust now, not discover absent later):**

> *"Conversion instrumentation — measuring which briefing / pre-consult items a prospecting or live practice actually acts on (opened the scan, dismissed the row, booked the recall) — is a known, named future consumer of exactly this standing-query materialisation substrate. It is deliberately NOT built and NOT demoed because it structurally cannot be until real customers generate real interaction events; building it now would be measuring nothing. When the first customer arrives it MUST be a small configuration of this infrastructure — a new `StandingQuery` kind (e.g. `kind='conversion_probe'`) writing rows into `briefing_items` (or a sibling `briefing_item_events` table) through the SAME `run_template` + `resolve_provenance` chokepoint, inheriting the same verifiable-provenance and tenant-scoping contract — NOT a forgotten requirement rediscovered late as a from-scratch analytics build. The substrate was shaped in PR D specifically so this is a configuration, not a project. This note is the named anchor; the work is correctly deferred, not lost."*

Registered code-adjacent: `standing.py`'s registry docstring states `conversion_probe` is the named-not-registered future kind + a pointer to the post-mortem. **No code stub** (a stub = fake-property anti-pattern, pretending the consumer exists). §2.4 gate checks the note is present in both places.

### 2.3 Artifact (3) — the shared-trigger post-mortem sentence

> *"Three deferred consequences share ONE trigger — the first real customer with real data volume: (1) `idx_prescription_items_prescription_id` (PR B-deferred; verified at PR D still absent, `prescription_items` still seq-scan-able at 73 rows); (2) the conversion-instrumentation `StandingQuery` kind (§2.2, deferred until interaction events exist); (3) the `/ask`↔`/run`↔`/briefing` shared rate-limit bucket (PR C §7, widened by PR D, inert while traffic is low). When that customer lands, 'what gets slow / what needs measuring / what needs its own budget' is **one review against this single trigger**, not three separately rediscovered late. All tracked in `project_phase3_tracked_deferrals`."*

### 2.4 "Close-out genuinely discharged" as a checkable build-failing gate (carried-constraint weight, not paperwork)

PR D description carries a literal checklist, each item a concrete artifact reference; the PR **does not merge** until every box is checked by the named verifier (the user, at review):

- [ ] `ONTOLOGY_QUERY_LAYER_POSTMORTEM.md` exists with §A (stable-count-15, denominator-drift noted), §B (carried ledger + Phase-4 pixel-render close-condition), §C (residual in umbrella's exact words), §D (worker-topology premise-test), §E (proven-vs-unverified, un-fused).
- [ ] The conversion-instrumentation note (§2.2 wording, or review-adjusted) present in BOTH the post-mortem AND `standing.py`'s docstring.
- [ ] The shared-trigger sentence (§2.3) present, naming all three + the memory key.
- [ ] **Executable gate `tests/test_standing_queries.py::test_postmortem_closeout_artifacts_present`** parses the post-mortem and asserts (i) `15` adjacent to "orphaned"/"sourced diagnoses" in §A, (ii) the residual phrase `checkable-but-not-checked`, (iii) `conversion instrumentation` AND `StandingQuery` AND `briefing_items` co-occurring, (iv) the shared-trigger phrase `one review`. Same shape as PR A's silent-dead-link guard / PR B's inertness gate / PR C's three-trap gate.

**Necessary vs sufficient — stated so "build-failing gate" is not misread (required tightening):** the prior gates (PR A/B/C) asserted *behaviour* (no client constructed, resolver returns unresolvable); this gate asserts *text exists*, and a presence-check has a weakness behaviour-checks do not — text can be present but contradicted by edited prose around it, and the co-occurrence check still passes (the same shape as the `action_name`/`action_type` "passes for the wrong reason" concern). Therefore: **the executable test is the AUTOMATABLE NECESSARY condition — it proves the load-bearing sentences are physically present and fails the build if any is absent. It is NOT the sufficiency condition. Discharge proper additionally requires the human-verified checklist above, read by the named verifier (the user) at review — semantic correctness of the post-mortem is a bounded human judgement, deliberately not automated (semantic validation is unbounded scope the plan rightly avoids).** "The close-out is a build-failing gate" means: the parser passing is necessary-not-sufficient; the human read is the sufficiency. The PR is not mergeable with the parser red (automatable), and not discharged until the human checklist is signed (judgement). Stating this split is itself the cure: "discharged" must never be read as "the parser passed".

**The §3–§4 code is explicitly built on top of this gate passing AND the human checklist signed.** PR body states verbatim: "the standing-query materialisation is the *interesting* part; §2's three artifacts are the *load-bearing* part — this PR is not mergeable with the §3 code green and the §2.4 gate red, and not discharged until the human checklist is signed."

---

## 3. The load-bearing standing-query property, scoped AFTER the close-out

**Property:** a registered standing query runs (scheduled or manual) and writes provenance-verifiable rows into `briefing_items`, idempotently, tenant-scoped, RLS-deny-all — every materialised row **structurally inheriting PR A/B's openable/no_source/unresolvable contract because it rides the exact same `run_template`+`resolve_provenance` chokepoint, no new data path.**

### 3.1 No new data path (rides the chokepoint, proven by test)
`materialise_standing_queries()` reaches data ONLY through `run_template`→`resolve_provenance` — the identical two-call chokepoint `/run`/`/ask` use. No own fact-table reads, no re-implemented provenance, no `ActionExecutor` (read-only, no audit row). Only `briefing_items` writes are the materialised resolved rows. Proven by `test_materialise_reaches_data_only_through_run_template_and_resolve_provenance` (recorder; same shape as PR C's no-new-path proof).

### 3.2 The dominant orphaned-source property survives materialisation (THE highest-priority Phase-3 regression, re-asserted)
`test_orphaned_source_still_unresolvable_through_briefing_path` drives the materialiser over a workspace holding an orphaned-source diagnosis; asserts the persisted `briefing_items` row carries `openable=False`, the truncated-id citation, counted unresolvable. PR A dominant property at the third boundary (CI invariant in A, regression guard in B, **materialisation-survival guard in D**). Live-verified (Finding C).
> **Honest scope note (construct-validity discipline):** orphaned data lives in `test-workspace-*` which is **NOT entitled** (Finding E); the materialiser by design only iterates entitled workspaces, so it would *never* materialise that workspace in production. The test drives the materialiser's **inner per-workspace function directly with an explicit workspace arg** (bypassing the entitlement filter for the test only) — exactly how PR B drove non-entitled corpus to prove the resolver property. Test docstring verbatim: *"asserts the resolver contract survives the materialisation code path; does NOT assert this workspace is ever materialised in production (it is not entitled). Entitled production path is NULL-sourced/openable per Findings S/E."* No orphan injected anywhere.

### 3.3 Idempotency is structural, not hoped
Per umbrella: **wipe-and-reinsert per `(workspace_id, kind, as_of_date)`**. Per entitled workspace × registered kind: delete all `briefing_items` for that exact triple, insert the freshly-resolved rows for the same triple. Double-run row-stable by construction (delete keyed identically to insert). Proven by `test_double_run_is_row_stable`. Recommended one transaction per `(workspace_id, kind)` so a mid-run failure never half-materialises (§6.6).

### 3.4 Tenant-scoped, trusted source, never caller input
Enumerates workspaces from the trusted DB source (Finding E): `workspaces.id` filtered to `'clinical_query' = ANY(practice_capabilities(id))`. No caller-supplied workspace anywhere (the tick takes no request; manual `POST /briefing/refresh` takes `workspace_id` from `current_user` only, never body — verbatim `/run` shape). `run_template` injects `p_workspace_id` structurally; `resolve_provenance` doc lookup `.eq("workspace_id",ws)`. Only entitled workspaces materialised (PR C coherence). Proven by `test_materialiser_only_iterates_entitled_workspaces_from_trusted_source`.

### 3.5 RLS-deny-all
`briefing_items` created `ENABLE ROW LEVEL SECURITY` + no permissive policy (027, migration-018 idiom). Backend writes/reads as service_role (bypass); anon/authenticated get zero rows. Added to PR 5 ratchet `TENANT_TABLES` (§4.D). `test_briefing_items_is_rls_deny_all` (RUN_INTEGRATION-gated) asserts `relrowsecurity=True` + zero permissive policies.

### 3.6 The named tests (one place)
`backend/tests/test_standing_queries.py`: `test_materialise_reaches_data_only_through_run_template_and_resolve_provenance`; `test_orphaned_source_still_unresolvable_through_briefing_path`; `test_double_run_is_row_stable`; `test_materialiser_only_iterates_entitled_workspaces_from_trusted_source`; `test_briefing_items_is_rls_deny_all` (RUN_INTEGRATION); `test_materialiser_does_not_route_through_action_executor`; `test_postmortem_closeout_artifacts_present` (the §2.4 gate); `test_027_migration_ends_with_notify_pgrst_decision_is_explicit` (reuse PR B's `_strip_sql_comments`).

---

## 4. Deliverables, file-by-file (honest size — order, not contract)

### 4.A `backend/migrations/027_briefing_items.sql` (NEW)
`BEGIN;…COMMIT;`, migration-018 discipline header. `CREATE TABLE IF NOT EXISTS briefing_items` — columns grounded in the real `to_dict()` shape (Finding C): `id uuid default gen_random_uuid() PK`; idempotency triple `workspace_id text NOT NULL`, `kind text NOT NULL`, `as_of_date date NOT NULL`; payload `template_id text`, `template_version int`, `row_payload jsonb NOT NULL`; denormalised top signals `source_status text`, `openable boolean`, `unresolvable_reason text`, `citation text`; `materialised_at timestamptz default now()`. Index on `(workspace_id,kind,as_of_date)` (the wipe predicate) + `(workspace_id)`. **RLS-deny-all** verbatim migration-018 idiom (no `FORCE`, no `auth.*`), header cites `018:29,36-48`. **The `NOTIFY pgrst` question consciously decided + documented (§6.5 open call):** 025 omitted (no function, app-path only); 026 included (adds functions). 027 adds a TABLE the supabase-py REST builder will address → **recommended: include trailing `NOTIFY pgrst,'reload schema';`** (a stale PostgREST table-schema cache could 404 early `.table("briefing_items")` calls until reload) — rationale in header; the gate enforces the decision is *explicit*, not its direction. Ordering: strictly after 026; adds no function so no template-availability race. ~110–150 lines (header-dominated). Umbrella ~110 = right order.

### 4.B `backend/ontology/query/standing.py` (NEW)
Module docstring in the umbrella register: rides the chokepoint, no new data path, read-only, no `ActionExecutor`, the chokepoint is the future POPIA decorator slot (Phase 5, deferred — design choice #6); **includes the §2.2 conversion-instrumentation note verbatim** (travels with the code). `@dataclass(frozen=True) StandingQuery{kind,template_id,params,description}`. Closed registry `_STANDING` + `register_standing()`/`all_standing()` (mirrors `registry.py`). **Initial kinds bounded by §6.2** — recommended **exactly ONE at merge:** `morning_briefing`→`patients_not_seen_since` (the only template proven both data-bearing AND provenance-resolving on an entitled workspace, Findings S/E); `pre_consult` named-registered-later (per-patient needs a UI absent until Phase 4); `conversion_probe` named-but-NOT-registered (§2.2). `materialise_standing_queries(supabase,*,as_of_date,only_workspace=None)->dict`: per entitled workspace (trusted §3.4) — or just `only_workspace` — per registered kind: `run_template`→`resolve_provenance`→wipe-and-reinsert the `(ws,kind,as_of_date)` partition; per-workspace error isolation (log+continue, mirrors watcher `:111-114`); returns per-(ws,kind) counts for observability. `_entitled_workspaces(supabase)`: the ONLY workspace source (trusted entitlement query). ~250–330; umbrella ~330 = right order.

### 4.C The worker tick — grounded in Finding W (adapted, not invented)
Per Finding W, design choice #5 honoured directionally but adapted. **Recommended (D-W1):** a new small async `standing_query_tick(supabase)` — `while _running: try: materialise_standing_queries(sb,as_of_date=<today>) except: log; await asyncio.sleep(STANDING_QUERY_TICK_INTERVAL)` — **started from the SAME `@app.on_event("startup")` host** as the watcher (same process, NOT new daemon, NOT pg_cron), matching `start/stop_document_watcher`'s singleton+`create_task`+cancel pattern (`:410-444`). A `STANDING_QUERY_TICK_ENABLED` env flag **default off** (PR C's `NL_QUERY_LLM_ENABLED` house pattern) — the tick is structurally inert at merge; enabling is a deliberate operator act; the merge ships substrate + manual refresh, autonomous tick ships gated. ~60–110; umbrella ~90 = right order. If review prefers **D-W2** (manual-refresh-only, tick deferred), this file is dropped and the deferral recorded in post-mortem §D — the daemon is not silently invented either way.

### 4.D `backend/app/api/query.py` — `POST /api/query/briefing/refresh` + `GET /api/query/briefing` (additive only)
Both `Depends(require_capability("clinical_query"))` — **§6.4: confirm reuse**; recommended **yes** (coherence + inherits PR A's `module_digitisation` Type-C ratchet **for free by construction** — coherent-choice-pays-twice, PR C decision #3 precedent; a distinct capability needs a 025-style seed + new ratchet). `_enforce_rate_limit` reused — **the same shared bucket PR C §7 flagged, now widened to `/run`+`/ask`+`/briefing`** (inert at merge; §2.3 shared-trigger cluster, not a blocker). `POST /briefing/refresh`: request model **NO `workspace_id`** (load-bearing comment); workspace from `current_user`; `materialise_standing_queries(_sb(),as_of_date=<today>,only_workspace=workspace_id)`; returns stats; no `ActionExecutor`. `GET /briefing`: persisted `briefing_items` for the auth workspace (optional `?kind=`/`?as_of_date=`), `row_payload` already resolved (written by the chokepoint). `.table("briefing_items")` chain carries `.eq("workspace_id",…)`. **PR 5 ratchet (mandatory):** add `"briefing_items"` to `TENANT_TABLES`; zero new BASELINE keys (a new tenant table joins the scanned set born-scoped — the ratchet doing its job). ~70–100; umbrella ~80 = right order.

### 4.E `backend/tests/test_standing_queries.py` (NEW)
The eight §3.6 named tests. RUN_INTEGRATION-gated live-DB ones; DB-free recorder ones use the `test_query_api.py` FakeSupabase/recorder harness. Largest file + honest size driver (close-out gate + highest-priority regression + idempotency/no-new-path invariants), same as PR C's `test_nl_query.py`. Umbrella ~240 = right order, measured at implementation.

### 4.F `ONTOLOGY_QUERY_LAYER_POSTMORTEM.md` (NEW) — §2.1 content, top-level repo doc.

### 4.G `backend/scripts/verify_query_phase0.py` (+~40, optional)
Probe (vi): drive `materialise_standing_queries` over an entitled workspace, assert persisted `briefing_items` statuses match the chokepoint's direct output (faithful pass-through, no drift). Read-only except the idempotent wipe-reinsert. Flagged optional — the named tests are the gate; the probe is the live-data confirmation in PR A/B's tradition.

### Honest size discussion
Umbrella ~950 = order, not contract; no grand total asserted (PR B refusal). Migration + handlers are mechanical mirrors (cheap); `standing.py` thin; tick ≈ watcher start/stop (cheap, gated). Honest cost is `test_standing_queries.py` + the post-mortem prose discipline. Size set by locked semantics + §6 once resolved, measured at implementation.

---

## 5. Construct-validity / honesty ledger

| Claim | Verified by | Label |
|---|---|---|
| Materialiser adds no new data path | `test_materialise_reaches_data_only_through_run_template_and_resolve_provenance` | **structural invariant — proven, load-bearing** |
| Orphaned-source survives the materialisation **code path** (resolver contract holds when the materialiser is pointed at orphaned data) | `test_orphaned_source_still_unresolvable_through_briefing_path` driving the inner per-workspace fn with a **test-only injected non-entitled workspace arg** | **CODE-PATH-PROVEN, NOT production-corpus-demonstrated** — see the row below |
| Orphaned-source rendering on the **production materialisation path** | — (the production path only iterates *entitled* workspaces; the entitled corpus contains **no orphan** — demo-gp is NULL-sourced, demo-briefing openable; the production path *structurally cannot reach an orphan* on this corpus) | **UNVERIFIED-ON-PRODUCTION-PATH, unsoftened (fourth occurrence of the earns-overclaim cure): the dominant-property guarantee at the PR-D boundary is "the resolver contract survives the materialisation code path when a test points it at orphaned data", which is genuinely weaker than "the dominant property survives materialisation" reads. Production never materialises an orphan here because no entitled workspace has one. A real epistemic limit, not a footnote — recorded in post-mortem §E in this column.** |
| Double-run row stability (idempotent) | `test_double_run_is_row_stable` | **structural invariant — proven** |
| Only entitled workspaces, trusted source, never caller input | `test_materialiser_only_iterates_entitled_workspaces_from_trusted_source` + Finding E | **proven by construction** |
| `briefing_items` RLS-deny-all | 027 + `test_briefing_items_is_rls_deny_all` (live) | **structurally enforced, proven** |
| Read-only; no `ActionExecutor` | `test_materialiser_does_not_route_through_action_executor` | **proven by construction** |
| Close-out artifacts physically present | `test_postmortem_closeout_artifacts_present` | **structurally enforced — a gate, not paperwork** |
| Briefing materialises end-to-end on entitled, data-bearing ws | Findings S/E | **corpus-demonstrated on the 2 entitled workspaces** |
| Conversion instrumentation works | — (NOT BUILT; cannot until customers exist) | **named-not-built — guarded hardest; substrate shaped, consumer deferred, note travels with code** |
| Autonomous scheduler tick in production | env-gated default-off | **substrate proven; autonomous op ships gated, deliberate operator act (cadence §6.1)** |
| 15-orphan permanent finding | live 15/25 (was 15/24); count stable | **corpus-demonstrated; recorded as the stable COUNT, no frozen percentage** |

No fabricated fixture appears as corpus evidence.

### The "earns" split — proven vs unverified, deliberately UN-fused (FOURTH-occurrence cure, now a known pattern; do not re-fuse — and applied here in the close-out artifact itself, the document read most adversarially)
- **PROVEN at merge:** standing-query rows **structurally inherit** PR A/B's verifiable-provenance + openable/no_source/unresolvable + `unresolvable_count`/`superseded_count` contract (materialiser rides *exactly* the `/run`+`/ask` chokepoint — proven by recorder, not asserted). The resolver contract **survives the materialisation code path** (proven by the inner-fn test). Idempotent by structural wipe-reinsert (proven). Tenant scope structural (trusted entitled enumeration, never caller input). `briefing_items` RLS-deny-all. Close-out discharged as a build-failing gate (necessary) + human checklist (sufficient). **Load-bearing and earned.**
- **NOT verified at merge / NOT closed:** **The orphaned-source-survives-materialisation guarantee is NOT production-corpus-demonstrated** — it is code-path-proven via a test-only injected non-entitled workspace arg; the production path only iterates *entitled* workspaces and the entitled corpus contains no orphan, so production *structurally cannot reach an orphan on this corpus*. "Survives materialisation" must be read as "the resolver contract holds when the code path is pointed at orphaned data by a test", which is genuinely weaker than its headline — fourth occurrence of the same earns-overclaim, named here unsoftened and carried into post-mortem §E's unverified column, not buried in risks. The **autonomous tick's production behaviour is unverified** (env-gated default-off; only substrate + manual refresh proven; worker-topology found underspecified, adapted to D-W1, post-mortem §D). **Conversion instrumentation is entirely unbuilt** — substrate shaped, but whether it measures the right thing is unknowable until customers generate events; "substrate ready" ≠ "conversion measurable." **The wrong-extraction residual is NOT closed** (post-mortem §C, umbrella's exact words). Named here, unsoftened; post-mortem §E must not re-fuse.

---

## 6. Decisions closed at review (LOCKED)

1. **Scheduler cadence + `as_of_date` — LOCKED:** `STANDING_QUERY_TICK_INTERVAL` default 24h (a morning-briefing is a daily artifact); `as_of_date` = materialiser wall-clock **UTC** date; tick env-gated default-off. Per-workspace timezone is a Phase-4-with-UI concern (the place's tz matters when a human *reads* the briefing, not when the row is materialised; the corpus can't even exercise it). **Rider:** the post-mortem names **per-workspace-timezone as the specific deferred refinement** (not vaguely "coarseness flagged").
2. **Initial kinds — LOCKED: exactly ONE at merge** — `morning_briefing` → `patients_not_seen_since` (the only template proven both data-bearing AND provenance-resolving on an entitled workspace, Findings S/E — vertical-slice discipline, one thing proven not many shallow). `pre_consult` named-later (needs the per-patient UI absent until Phase 4 — registering it now = a registered kind that cannot be exercised, the fake-property shape). `conversion_probe` named-but-NOT-registered, no stub.
3. **Worker-topology — LOCKED: D-W1** (a new small independent async tick from the *same* `@app.on_event("startup")` host, env-gated default-off, matching the watcher's singleton+create_task+cancel pattern; explicitly NOT a new daemon, NOT pg_cron). **Reasoning (recorded because this was the reserved call):** D-W2 looks safer but is wrong here — the env-gated flag makes the tick *structurally inert at merge under EITHER option*, so the merge-time risk profiles are identical; the *deferred-work* profiles differ — D-W2 defers building the tick into an unscoped future (the exact "rediscovered late as a from-scratch build" failure the conversion-instrumentation note exists to prevent), while D-W1 builds the inert substrate now so enabling autonomous operation is a one-flag operator/governance act against proven code, not a future engineering project against cold context. Same logic as PR C shipping the NL classifier disabled-but-built. pg_cron rejected-by-default. Post-mortem §D records design choice #5 was tested, found underspecified, resolved to D-W1, with this reasoning, so the next maintainer inherits the decision not the re-derivation.
4. **`/briefing` reuses `clinical_query` — LOCKED.** Coherence (same data, same chokepoint; a narrower capability is incoherent). **Required PR-body statement, now a RECOGNISED DESIGN INVARIANT, not just an instance:** *new read surfaces that reach clinical data reuse `clinical_query` specifically so PR A's `module_digitisation`-does-NOT-entail-`clinical_query` Type-C ratchet propagates the written Type-C customer promise to them for free, by construction, with zero per-surface ratchet code.* This is the fourth occurrence (migration 025, PR C `/ask`, now `/briefing`); state it as a principle of the design, not a one-off. (A distinct capability = 025-style seed + a new ratchet — the reuse inherits both for free.)
5. **027 `NOTIFY pgrst` — LOCKED: include**, header states the supabase-py-REST-builder reasoning so the decision is auditable. The `test_027…_decision_is_explicit` gate enforces *explicitness* (NOTIFY present OR a conscious-omission header), NOT a direction — reusing PR B's `_strip_sql_comments` idiom.
6. **Idempotency granularity — LOCKED: one transaction per `(workspace_id, kind)`** — `as_of_date` is constant within a run so finer adds no isolation; per-workspace-across-all-kinds would let one kind's failure roll back another's good materialisation. Per-`(workspace_id, kind)` makes a failure's blast radius exactly the partition being rewritten — the correct property.

---

## 7. Risks (Phase-3 honesty standard)
- **Worker-topology was the flagged "verify empirically here" — underspecified, not merely confirmed (Finding W).** Mitigation: §3.3/§4.C/§6.3 adapt explicitly; post-mortem §D records; tick env-gated so a wrong choice is inert at merge; pg_cron stays rejected-by-default, named.
- **The close-out is the load-bearing part most likely to be skimped under "the code is the interesting bit"** (the exact failure the overriding instruction guards). Mitigation: §2 scoped first, carried-constraint weight, the §2.4 build-failing gate makes "discharged" checkable; PR not mergeable with §3 green and §2.4 red.
- **The conversion-instrumentation note most likely to evaporate (no code/demo by necessity).** Mitigation: §2.2 exact wording, two locations, the §2.4 gate asserts its anchor phrases co-occur.
- **Orphaned-through-materialisation corpus-demonstrated only on the inner non-entitled path.** Mitigation: §3.2 verbatim honest-scope docstring; §5 labels precisely; no orphan injected.
- **15/25 vs the umbrella's 62%/15-of-24.** Mitigation: post-mortem records the stable count + mechanism, denominator-drift noted, no frozen percentage.
- **Shared rate-limit bucket now spans `/run`+`/ask`+`/briefing`.** Not a blocker (inert at low traffic); §2.3 shared-trigger cluster, resolved at the flag-enablement boundary.
- **Heterogeneous TEXT identifiers (carried scar).** `briefing_items.workspace_id text` = `workspaces.id text`, no `::uuid`; re-confirmed.

## 8. What PR D earns; what closes Phase 3; what remains explicitly deferred
**Earns (proven, §5):** the morning-briefing/pre-consult substrate is a registered standing query already materialising into `briefing_items`, every row structurally inheriting PR A/B's verifiable-provenance contract (same chokepoint), idempotent, tenant-scoped from a trusted source, RLS-deny-all, read-only. The Phase 3 close-out is **genuinely discharged as a build-failing gate**, not paperwork.

**What closes Phase 3:** SurgiScan stops being a digitiser and becomes *trustworthy* queryable clinical infrastructure — the dead-link failure is a known-unknown the clinician sees, never a confident wrong answer; the briefing/pre-consult set materialises into `briefing_items` inheriting that verifiability, waiting only for the Phase 4 UI; the post-mortem records honestly what was proven / corpus-thin / construct-validity-only / the permanent residual, in the umbrella's own words.

**Explicitly deferred (named, not silent):** briefing UI → Phase 4; the Phase-4 pixel-render close-condition (carried from PR B's DISCHARGED note, post-mortem §B); conversion instrumentation → named-only (§2.2, hardest-guarded); POPIA query-access logging → Phase 5 (the chokepoint is the decorator slot; materialiser rides it so inherits it for free); the shared trigger (§2.3) — one review at the first real customer, tracked in memory.
