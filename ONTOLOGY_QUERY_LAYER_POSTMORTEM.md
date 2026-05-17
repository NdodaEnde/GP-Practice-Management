# Phase 3 — Query Layer Post-Mortem (Close-Out)

**Status — the framing in one sentence:** Phase 3 shipped a tenant-scoped, provenance-verifiable query layer (PR A primitives + resolver, PR B briefing/pre-consult set + ugly-case defences, PR C thinnest NL surface ships-disabled, PR D standing-query materialisation + this close-out); the dominant failure mode was *measured before the resolver was built*, every limit the corpus cannot exercise is *labelled rather than hidden*, and this document records — in the umbrella's own words where it matters — exactly what was proven, what is corpus-thin, what is construct-validity-only, and the one permanent residual, so a future-self or a regulator quoting the close-out cannot infer a stronger property than was built.

This is the Phase 3 close-out artifact. It is load-bearing, not paperwork: its presence and its load-bearing sentences are asserted by a build-failing test (`backend/tests/test_standing_queries.py::test_postmortem_closeout_artifacts_present`). That test is the **automatable necessary** condition (it proves the sentences are physically present and fails the build if any is absent); it is **not sufficient** — discharge proper additionally requires the human-verified §2.4 checklist read by the named verifier at review, because semantic correctness of this document is a bounded human judgement deliberately not automated. "The close-out is a build-failing gate" means the parser passing is necessary-not-sufficient and the human read is the sufficiency. "Discharged" must never be read as "the parser passed".

---

## §A. The permanent data-quality finding (recorded for a future backfill — NOT a deferral closed within Phase 3)

**15 sourced diagnoses** on the dev corpus carry a `source_document_id` that resolves to no `digitised_documents` row (orphaned by the reverse/delete history; the ids survive in `action_audit_log.affected_objects`). At PR A this was **15 of 24 sourced diagnoses (62%)**; at PR D close-out it is **15 of 25 (60%)** — the orphan **count is stable at 15**; the denominator drifts with corpus growth (one new sourced-but-present diagnosis was added between PR B and PR D), so **the permanent finding is the count (15) and the mechanism, not the percentage** (a frozen percentage has already moved twice and would be a false "permanent" figure).

This is the dominant, *measured* failure the entire provenance-verifiable ordering of Phase 3 exists to close. The query layer makes it **visibly unresolvable** — citation `source document no longer available (id …e15a71)`, `openable=False`, counted in the row's `unresolvable_count` — it does **not** repair it. A future data-quality **backfill** (recover the documents from `action_audit_log.affected_objects`, or tombstone the dangling ids) is named here and is explicitly **OUT of Phase 3 scope**. It is recorded so it cannot be silently forgotten: the orphaned-source population is a known, quantified, mechanism-understood data-quality debt, not an unknown.

---

## §B. Documented-thin / construct-validity ledger (carried from PR B §4, re-verified at close-out)

| Case | Live state at close-out | Label |
|---|---|---|
| Lab-threshold template | 1 `lab_result` globally, no LOINC | **`schema_only`** — shape correct, data absent until lab ingestion exists (out of Phase 3) |
| Abnormal-vitals template | 0 vitals in demo-gp, 5 globally | **`thin`** — surfaced via `data_maturity`, never disguised as a clean cohort |
| Reversed/superseded source | 17 reversed promotions, **0 live facts** point at one (reverse RPC DELETEs facts) | **construct-validity-only** — per-row + `superseded_count` plumbing built + unit-tested on fabricated input, never claimed corpus-demonstrated |
| Two-document fact | 0 multi-source facts; no multi-source schema | **construct-validity-only** — `additional_sources` is the inert optional field, inertness is a tested CI gate |
| PR C NL mapping-correctness | classifier ships disabled (default-off structural; gate proven to bite) | **unverified-at-merge** — output-domain constraint proven; mapping correctness only knowable via the opt-in eval once a provider is authorised (governance act) |
| **Phase-4 pixel-render close-condition** (carried from PR B's DISCHARGED note) | `demo-briefing-workspace-001` has no login; PR B/D ship no query UI | **Phase-4-gated** — the in-app human pixel-click of the openable-vs-unresolvable contrast is NOT dischargeable in Phase 3; backend real-stack verification + named tests stand; **Phase 4 cannot close until the openable-vs-unresolvable rendering is verified against the real briefing UI** — that is the moment the safety property becomes visible to the human it protects; "correct but never seen by a human" is weaker than the platform's trust thesis promises |

No fabricated fixture appears anywhere as corpus evidence.

---

## §C. The permanent residual (stated in the umbrella Context §'s EXACT words, so a future-self quoting the close-out to a regulator cannot infer a stronger property than was built)

> *Verifiable provenance defends exactly one failure: the **dead-link** failure — a row presented authoritatively whose source silently resolves to nothing. It does NOT defend the **wrong-extraction** failure: a row whose `source_document_id` opens a real scan, but the ICD-10/medication/vital extracted from that scan is itself wrong. Verifiable provenance makes that failure checkable by a motivated reader — someone who opens the scan and confirms the extracted fact against the document. A clinician in a hurry, and emphatically a prospecting doctor in a demo, is not a motivated reader. So wrong-extraction-behind-a-live-link is **checkable-but-not-checked** — a real residual risk Phase 3 surfaces and does not close. Extraction correctness is upstream of the query layer and out of Phase 3 scope.*

This residual is permanent within Phase 3. It is not a deferral that gets closed later in the phase; it is the honest boundary of what verifiable provenance is and is not.

---

## §D. The worker-topology premise test (Finding W — design choice #5 was empirically tested at PR D and found underspecified)

The umbrella's design choice #5 said "reuse the existing long-lived worker; one scheduler tick." PR D's probe tested that premise against the live codebase and found it **underspecified, not merely confirmable**:

- A long-lived worker DOES exist — `backend/app/services/document_watcher.py` `DocumentWatcher`, an asyncio `while self._running: … await asyncio.sleep(N)` loop started in `server.py`'s `@app.on_event("startup")`.
- **But it is a single-workspace singleton hard-bound to `DEMO_WORKSPACE_ID`**, its loops are private to the document-ingestion concern, and there is no generic "tick host" to hang a materialiser on. "Reuse it" was a free verb covering a non-trivial topology decision.

**Resolution: D-W1.** A new small *independent* async tick task (`standing_query_tick`) started from the *same* `@app.on_event("startup")` host as the watcher — same process, same lifecycle pattern (singleton + `asyncio.create_task` + shutdown-cancel), gated behind `STANDING_QUERY_TICK_ENABLED` (default off, the PR C house pattern). NOT a new OS daemon; NOT pg_cron (rejected-by-default, named).

**Why D-W1 over the apparently-safer D-W2 (manual-refresh-only, tick deferred):** the env-gated flag makes the tick *structurally inert at merge under either option*, so the merge-time risk profiles are identical. The *deferred-work* profiles differ: D-W2 defers building the tick into an unscoped future — the exact "rediscovered late as a from-scratch build" failure the §2 conversion-instrumentation note exists to prevent — whereas D-W1 builds the inert substrate now so enabling autonomous operation is a one-flag operator/governance act against proven code, not a future engineering project against cold context. Same logic as PR C shipping the NL classifier disabled-but-built rather than deferred-and-unbuilt. The next maintainer inherits this decision, not the re-derivation.

---

## §E. What Phase 3 earned (proven) vs what it did not (unverified / residual) — deliberately UN-fused

This is the fourth named PR-level occurrence of the same earns-overclaim cure (PR A "verifiable provenance is the safety property", PR B "structurally inherited", PR C "constrained to the closed enum", and here). The pattern is now known; it is applied here, in the close-out artifact, because this is the document read most adversarially — and it is applied **twice within this close-out**: in this section's proven/unverified split, and again in the PROVEN column's three-boundary sentence below, where the PR-D materialisation leg's code-path-only scope is carried inside the sentence that claims it (a re-fusion an adversarial reader would otherwise reconstruct from the unverified column). The count is stated explicitly so it cannot drift: four named PR-level occurrences, two applications inside this document.

**PROVEN:**
- The dead-link failure (the measured, dominant one — §A) renders **visibly unresolvable**, a known-unknown the clinician sees, never a confident wrong answer with a silent dead link. Guarded at three boundaries of **unequal epistemic strength — not a strengthening progression**: a CI invariant in PR A and a regression guard in PR B, **both corpus-demonstrated**; and in PR D a materialisation-**code-path** guard that is **code-path-proven only, NOT production-corpus-demonstrated** — its production limit (the entitled corpus contains no orphan) is stated unsoftened in the NOT-verified column below and is load-bearing here too: this PR-D leg must not be read, or quoted in isolation, as the dominant property proven in production at the PR-D boundary. The PR A/B legs carry production weight; the PR D leg carries code-path weight.
- Provenance resolution is reached only through the single `run_template`+`resolve_provenance` chokepoint; no surface (`/run`, `/ask`, `/briefing`, the materialiser) reaches data any other way — proven by recorder tests, not asserted.
- Tenant scope is structural (the runner injects `p_workspace_id`; the resolver's document lookup is workspace-scoped; the materialiser enumerates only entitled workspaces from a trusted DB source, never caller input). The PR 5 ratchet covers every tenant table including `briefing_items`.
- The NL surface ships disabled with a default-off gate **proven to bite** (flag-off-silent AND flag-on-each-trap-fires, both permanent CI) — the disabled-default is the PII boundary; there is no scrubber and the code does not pretend one.
- Standing-query materialisation is idempotent by structural wipe-and-reinsert (double-run row-stable, proven), RLS-deny-all, read-only (no ActionExecutor / no audit row).

**NOT verified / NOT closed (unsoftened):**
- **The orphaned-source-survives-materialisation guarantee is NOT production-corpus-demonstrated.** It is **code-path-proven** via a test that drives the materialiser's inner per-workspace function with a *test-only injected non-entitled workspace argument*. The production materialisation path only iterates *entitled* workspaces, and the entitled corpus contains **no orphan** (demo-gp is NULL-sourced; demo-briefing is openable), so production *structurally cannot reach an orphan on this corpus*. "The dominant property survives materialisation" must be read as "the resolver contract holds when the materialisation code path is pointed at orphaned data by a test" — genuinely weaker than the headline. This is a real epistemic limit, recorded here in the unverified column, not buried in a risks list.
- **The wrong-extraction residual is NOT closed** (§C, verbatim umbrella words): checkable-but-not-checked.
- **The autonomous scheduler tick's production behaviour is unverified at merge** — it ships env-gated default-off; only the substrate and the manual refresh path are proven; the worker-topology premise was found underspecified and adapted to D-W1 (§D). Whether D-W1 behaves correctly under real multi-workspace load over days is not a merge-time-provable property.
- **Conversion instrumentation is entirely unbuilt** — the substrate is shaped for it; whether it measures the right thing is unknowable until customers generate interaction events. "Substrate ready" must NOT be read as "conversion measurable." See the named note below.

These are named here, unsoftened, and this section does not re-fuse the proven and the unverified.

---

## Named-not-built: the conversion-instrumentation scope note (guarded hardest)

This note is the named anchor for the single most important deferred consumer of the standing-query substrate. It has no code and no demo *precisely because it cannot until customers exist*, which is exactly why it is written verbatim here and in `backend/ontology/query/standing.py`'s module docstring (it travels with the code), with no code stub (a stub would be the fake-property anti-pattern — pretending the consumer exists):

> *Conversion instrumentation — measuring which briefing / pre-consult items a prospecting or live practice actually acts on (opened the scan, dismissed the row, booked the recall) — is a known, named future consumer of exactly this standing-query materialisation substrate. It is deliberately NOT built and NOT demoed because it structurally cannot be until real customers generate real interaction events; building it now would be measuring nothing. When the first customer arrives it MUST be a small configuration of this infrastructure — a new `StandingQuery` kind (e.g. `kind='conversion_probe'`) writing rows into `briefing_items` (or a sibling `briefing_item_events` table) through the SAME `run_template` + `resolve_provenance` chokepoint, inheriting the same verifiable-provenance and tenant-scoping contract — NOT a forgotten requirement rediscovered late as a from-scratch analytics build. The substrate was shaped in PR D specifically so this is a configuration, not a project. This note is the named anchor; the work is correctly deferred, not lost.*

---

## The shared-trigger sentence

> *Three deferred consequences share ONE trigger — the first real customer with real data volume: (1) `idx_prescription_items_prescription_id` (the scale index PR B deferred; verified at PR D still absent, `prescription_items` still seq-scan-able at 73 rows); (2) the conversion-instrumentation `StandingQuery` kind (named above, deferred until interaction events exist); (3) the `/ask` ↔ `/run` ↔ `/briefing` shared rate-limit bucket (PR C §7, widened by PR D, inert while traffic is low). When that customer lands, the "what gets slow / what needs measuring / what needs its own budget" review is **one review** against this single trigger, not three separately rediscovered late. All three are tracked in the project memory `project_phase3_tracked_deferrals`.*

---

## What closes when Phase 3 closes

SurgiScan stops being a digitiser and becomes *trustworthy* queryable clinical infrastructure: the dead-link failure (the measured, dominant one) is a known-unknown the clinician sees, never a confident wrong answer with a dead link; the morning-briefing / pre-consult set is a registered standing query already materialising into `briefing_items`, inheriting that verifiability, waiting only for the Phase 4 UI. The platform earns this honestly — provenance is the correctness mechanism (a CI invariant from line one, not bolted on late), tenant-scoping is structural, the NL steering wheel ships locked behind a gate proven to bite, and the things it cannot do (precise per-fact confidence, defend a reversed-source live fact, guarantee a live-link extraction is itself correct, see PII without a governance decision, prove orphan-rendering on the production materialisation path on this corpus) are documented deferrals and labelled construct-validity limits in this document, not silent gaps.
