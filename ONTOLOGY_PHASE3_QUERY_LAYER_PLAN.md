# Phase 3 — The Query Layer: PR-by-PR Implementation Plan

> **RE-DRAFT — provenance-verifiable-first ordering.** This supersedes the
> earlier primitives→NL→provenance→standing sequence. The inversion is a
> safety decision, not a preference: Phase 3's failure mode is a silent,
> plausible-looking wrong answer with a provenance link beside it, and the
> binding constraint (a clinician — or a prospecting doctor in a demo —
> trusting it) is present from the first runnable query, not at customer
> arrival.
>
> **Status tracker (update as PRs land):**
> - **PR A** — primitives + *verifiable* provenance (extends open PR #13) — ✅ code-complete, safety property verified on live data (Phase-0 probe iv + 46/46 tests), cleared to merge; browser-contrast carried to PR B
> - **PR B** — hardening + briefing/pre-consult set + the ugly cases — ⬜ (carries the PR A browser openable-vs-unresolvable contrast as an un-skippable DoD item — see PR B scope)
> - **PR C** — thinnest NL mapping (ships disabled) — ⬜
> - **PR D** — standing-query materialisation + Phase 3 close-out — ⬜
>
> **Plan approved at review with two required changes (safety-property
> reframe in three places; PR B sized-not-projected) and all four
> reserved decisions LOCKED.** Both required changes are applied below;
> the locked decisions are in "Decisions locked at review."
>
> **Disposition of open PR #13: DO NOT MERGE AS-IS — extend the branch to
> meet PR A's bar before merge.** See the dedicated section below.
>
> **All decisions locked** (planning time: query-shape set, NL ships
> disabled, briefing UI → Phase 4; at review: low-confidence phrasing,
> reversed-source aggregate, unresolvable citation wording,
> `clinical_query` out of foundation). See "Decisions locked at review."

---

## Context

Phases 0–2 built the typed ontology spine and made every mutation a
first-class audited `Action` through `app/actions/executor.py`. Phase 3
turns the spine load-bearing for *reads*. The prior plan correctly
identified that supabase-py's PostgREST builder cannot express the
required joins, so the query layer is a compiler to tenant-scoped
PL/pgSQL RPCs (proven in PR #13 / migration 024).

The binding constraint is not customer count — it is the first runnable
query. Phase 2's failure mode was loud (rollback, action error). Phase
3's is silent and clinically consequential: the layer answers 20 queries
correctly and returns a subtly wrong cohort on the 21st, with a plausible
provenance link beside it, and nobody notices until a doctor acts on it.
In the current pre-customer reality the *demo itself* is the binding
constraint. Therefore provenance is not a UI feature — it is the
correctness mechanism, and it must be **verifiable** (a resolvable
`source_document_id` → an openable scan + a human-readable citation),
not merely **present** (an opaque UUID in a JSONB blob), from the first
query the system can run.

**Precise statement of what verifiable provenance does and does not
defend (review-required framing — do not soften this anywhere it
recurs).** Verifiable provenance defends *one* failure exactly: the
**dead-link** failure — a row presented authoritatively whose source
silently resolves to nothing. That failure is measured, dominant (62%,
finding #1), and this is the failure the whole ordering exists to close.
What verifiable provenance does **not** defend is the **wrong-extraction**
failure: a row whose `source_document_id` opens a real scan, but the
ICD-10/medication/vital extracted *from* that scan is itself wrong.
Verifiable provenance makes that failure *checkable by a motivated reader*
— someone who opens the scan and confirms the extracted fact against the
document. **A clinician in a hurry, and emphatically a prospecting doctor
in a demo, is not a motivated reader.** The provenance link is the
correctness mechanism *only when it is used*; an openable link beside a
wrong extraction that nobody opens is still a confident wrong answer with
a working "open" button. Phase 3 does not, and within its scope cannot,
solve extraction correctness (that is upstream of the query layer and
out of Phase 3 — attempting it here is scope-balloon). The honest
boundary, stated here and re-stated identically in "What Phase 3 earns"
and the close-out post-mortem: **the failure mode becomes a known unknown
the clinician sees for dead links; for live links it becomes
checkable-but-not-checked, which is a real residual risk, not a closed
one.**

**Empirical probe of the live dev DB (role=postgres) — five findings,
three safety-load-bearing:**

1. **The verifiability gap is present and dominant.** `digitised_documents`
   has 20 rows. **15 of 24 diagnoses carrying a `source_document_id` point
   at a document row that no longer exists** (the join returns NULL; IDs
   survive in `action_audit_log.affected_objects`). PR #13's contract is
   satisfied (UUID present) but a resolver produces a dead link / blank
   citation for 62% of real rows while the answer still renders
   authoritative. This is the unsafe artifact, and it is the *dominant*
   case on the corpus, not a hypothetical.
2. **No clinical fact table carries a per-row confidence column.** The
   only confidence signal is `gp_validation_sessions.confidence_scores`,
   **section-level not per-fact**, keyed by `document_id`, recoverable for
   only **1 of 16** distinct diagnosis source documents.
3. **"Source document reversed" does not currently manifest as a live
   stale fact** — `reverse_action_promote_document` *DELETEs* the fact
   rows. 17/100 promotions reversed, 0 live diagnoses point at a reversed
   promotion. The risk is structural-future, not present-corpus.
4. **"Two source documents" is absent** — 0 patients have diagnoses from
   >1 source document.
5. **Lab/vitals thinness confirmed** — 1 `lab_results` row (no LOINC), 5
   `vitals` rows (2 with `bp_systolic>140`). `doc_type` is 0% populated,
   so a citation cannot say "referral letter" — only `filename` +
   `upload_date` + page.

## Design choices

**1. (NEW — load-bearing) Provenance is the correctness mechanism;
"verifiable" is the definition of done for the FIRST runnable query, not
a later PR.** PR #13 made provenance a structural contract (TemplateSpec
refuses templates without a `provenance` column; runner fails loud) —
retained. But it deferred *resolution* and the *CI invariant test* to
later PRs, creating a window in which a query returns rows whose
provenance resolves to nothing 62% of the time. Present + CI-enforced +
resolvable collapse into one DoD in PR A. *Rejected:* the prior plan's
"ship #13, harden over PRs 8/11" — creates exactly the multi-PR unsafe
window. *Also rejected:* resolve provenance lazily in the frontend —
moves the correctness mechanism out of the tested backend contract into
an untested rendering path.

**2. (Retained) The query layer is a compiler to PL/pgSQL RPCs, not an
ORM over PostgREST.** Joins/EXISTS/pgvector/tenant-scope-as-mandatory-
parameter are unattainable through the builder and invisible to the PR 5
tenant guard if done via raw psycopg2 in handlers. *Rejected:*
psycopg2-direct in handlers. Confirmed in #13's Phase-0.

**3. (Retained) Query shapes are a closed, versioned registry — not a
generic algebra.** *Rejected:* a fluent arbitrary-chain compiler
(multi-month research project, unbounded injection surface).

**4. (Retained) The NL layer is the thinnest possible constrained intent
classifier over the closed template enum, ships disabled, PII-gated.**
*Rejected outright:* NL2SQL.

**5. (Retained) Standing queries reuse the existing long-lived worker;
one scheduler tick, not pg_cron, not a new daemon.**

**6. (Retained) The query layer is read-only; does NOT route through
ActionExecutor.** The `run_template()` chokepoint is where a future POPIA
access-log decorator slots in (Phase-5 deferral, chokepoint exists).

**7. (NEW — honesty about non-defendable cases) Where a safety case is
not present on the corpus, ship the structural defence and label it
"schema-correct, not corpus-exercised" — do not claim a tested defence
that cannot be demonstrated.** Applies to reversed-source and two-source
(findings #3, #4). *Rejected:* synthesising adversarial fixtures and
presenting them as evidence the case is handled — that is itself a fake
property, the exact Phase-2 anti-pattern.

---

## Disposition of the open PR #13

**Recommendation: extend the #13 branch to meet the PR A bar before
merge. Do NOT merge #13 as-is.**

*Already satisfies PR A:* the structural provenance contract
(`spec.py`/`runner.py`/`result.py`), the single tenant-scoped chokepoint,
migration 024's provenance-in-join + mandatory `NOTIFY pgrst` pattern.

*Missing for PR A (the unsafe gap):* (i) no **resolution** — a
`source_document_id` is an opaque UUID; 62% resolve to nothing on real
data; (ii) no **CI invariant test** that fails the build if a future
template's SQL forgets provenance or returns an unresolvable id; (iii) no
**HTTP surface** — a demo doctor cannot click a source; a Python REPL is
insufficient for the present binding constraint.

*Why extend, not merge-then-fix:* "merge as labelled-not-demo-safe" is a
social control over a technical hazard — the runner works, someone wires
an endpoint, the unsafe demo happens. The only guarantee the unsafe
window never exists is to never land a mergeable artifact that answers a
query without resolution. #13 is sound and ~1,330 LoC; extending
on-branch is bounded. #13 becomes PR A.

---

## PR breakdown

Four PRs (A–D), close-out folded into PR D (the CI invariant moves *into*
PR A as the gate, so a separate PR-11 ratifying invariants that have been
load-bearing for three PRs is redundant). Deviation from the prior 6-PR
shape is deliberate and justified per-boundary. Every boundary preserves
the invariant: **no PR ships a query result a clinician could act on
without verification present, CI-enforced, and resolvable.** LoC
estimates corrected upward (PR 3's estimate ran 40% low; cost is
PL/pgSQL + resolution + ugly-case verification, not Python).

### PR A — Structured query primitives WITH verifiable provenance (extends #13)

**Load-bearing property:** the first runnable query returns rows whose
provenance is present (contract), CI-enforced (build fails otherwise),
and resolvable (every `source_document_id` either opens a real scan with
a human citation, or is *explicitly and visibly* marked unresolvable —
never a silent dead link), reachable over HTTP so a demo verifies by
clicking.

**Deliverables (paths + honest LoC):**
- *Retained from #13, unchanged:* `backend/ontology/query/{spec,registry,
  runner,result,__init__,registered}.py`, `templates/
  patients_with_diagnosis_prefix.py`, `migrations/024_…sql` (~0 new).
- **`backend/ontology/query/provenance.py`** (~340) —
  `resolve_provenance(supabase, rows, *, workspace_id)`: one
  workspace-scoped batch query → `ResolvedSource{document_id, openable,
  signed_url_or_none, citation, unresolvable_reason}`. Reuses the
  signed-URL pattern at `digitisation.py:268` and the metadata shape of
  `_audit_row_to_drawer_row`. Honest citation (`filename` +
  `upload_date` + page; **no fabricated "referral letter"** — `doc_type`
  0% populated). **The unresolvable path is first-class:** missing doc →
  `openable=False`, explicit reason, explicit citation. This is the
  safe/unsafe difference.
- **`backend/app/api/query.py`** (~190) — `POST /api/query/run`;
  `workspace_id` from `get_current_user` only (never body); new
  `clinical_query` capability gate; rate limiter reusing the digitisation
  pattern; response calls `resolve_provenance` so every row ships
  resolved-or-explicitly-not. **The response envelope carries a
  cohort-level `unresolvable_count`** (born here in PR A — the
  cohort-altitude argument that mandated the reversed-source aggregate in
  locked decision #2 applies *identically and more urgently* to the
  dominant 62% dead-link case: a 40-row cohort where 25 sources are dead
  is exactly the demo failure, and a per-row marker nobody scans does not
  surface it). PR B adds `superseded_count` to the same envelope; the
  shape is designed for that extension from PR A.
- **`backend/migrations/025_query_capability_seed.sql`** (~40) — seed
  `clinical_query`; `NOTIFY pgrst` discipline note.
- **`backend/tests/test_query_layer_invariants.py`** (~280) — **the CI
  gate, pulled forward from the prior PR 11.** Every template declares
  `provenance`; every RPC takes `p_workspace_id` first; no template
  bypasses `run_template`; `resolve_provenance` never returns
  `openable=True` with no signed URL (silent-dead-link guard as an
  executable invariant). **PLUS the row/aggregate-consistency invariant
  (review-suggested, adopted as required-in-A): no result envelope can be
  returned where `unresolvable_count` disagrees with the number of rows
  whose resolved source is `openable=False` — the cohort-level and
  row-level safety signals can never drift apart, because the aggregate
  is precisely the signal that gets read.** The invariant is written
  extensibly in PR A so PR B's `superseded_count` slots into the same
  consistency check without a rewrite.
- **`backend/tests/test_query_api.py`** (~180) — forged-body workspace
  cannot cross tenants; every row resolved; unresolvable rows carry the
  explicit marker, not null.
- **`backend/scripts/verify_query_phase0.py`** (+~90) — extend with the
  resolution probe: assert the known-15 orphaned-source rows return
  `openable=False` + explicit reason (proves the unsafe case is *visibly*
  handled, not blank/crashed).

**Empirical verification (Phase-0) — DONE, with one corrected premise.**
The 15/24 orphaned-source finding is re-asserted live by
`verify_query_phase0.py` probe (iv): against the real DB, through the
real RPC + real resolver + real signed-URL minting, the orphaned source
resolves VISIBLY UNRESOLVABLE (citation `source document no longer
available (id …e15a71)`) and a present source resolves OPENABLE with a
signed URL (`Patient file.pdf, 7 May 2026`). The HTTP/auth stack
(capability gate, forged-body inertness, error mapping) is verified by
`test_query_api.py`. **Corrected premise:** the single browser
click-through "one link opens, one visibly doesn't on one screen against
a real entitled workspace" is NOT achievable on the current corpus.
`demo-gp-workspace-001` (the only workspace `clinical_query` legitimately
reaches, via `legacy_full_access_grant`) has 31 patients but **0
diagnoses** — the shipped template returns empty there. The orphaned data
lives in `test-workspace-*` (not entitled) and the resolvable case in
`typec-workspace-001` (module_digitisation — correctly NOT entitled,
ratchet-guarded). No single workspace is both entitled and data-bearing.
Closing this needs a properly provisioned platform-tier demo workspace
seeded with both a resolvable and an orphaned sourced diagnosis — NAMED
here, not faked, and explicitly NOT closed by bending the entitlement
mapping to a data-bearing workspace (that is the anti-pattern the
entitlement decision rejected).

**Smoke-vehicle decision: RESOLVED — Option 1 (carry the browser
contrast to PR B).** Rationale (from review): the browser click verifies
*rendering*, a strictly weaker and different thing than the resolver
*correctness contract* the probe already proves on live data; making it
PR A's gate would contradict design choice #1 (correctness mechanism
stays in the tested backend, not the rendering path). Provisioning a
seeded workspace *now* (the rejected Option 2) is design choice #7's
anti-pattern in a provisioning-script costume — proving a safety property
against data manufactured to satisfy it. Option 1 is the only path that
keeps the discipline: PR B independently *requires* a seeded, entitled,
data-bearing demo workspace to verify its own briefing-set property, so
the browser contrast rides on data that exists for PR B's own legitimate
reasons, not a fixture built to pass a PR A click.

**PR A verification statement (REQUIRED WORDING — quote verbatim in the
PR description; do not soften to "safety property verified"):** *The PR A
safety property — every query row's provenance resolves to an openable
scan with an honest citation, or is visibly marked unresolvable, never a
silent dead link — is verified by an automated Phase-0 resolution probe
on live data plus 46/46 invariant/API tests, including the known-orphaned
rows returning `openable=False` with an explicit reason. The visual
rendering of that distinction in a browser is deferred to PR B because no
current workspace is both entitled to `clinical_query` and data-bearing,
and manufacturing one solely to demonstrate it would be the
construct-validity anti-pattern this plan rejects. What is proven:
resolver correctness on real data. The edge not covered by PR A: the
human-visible rendering of it.*

**Defers:** the briefing set, the ugly cases, NL, standing. Ships exactly
one template — but fully safe.

**~1,120 new on top of #13's ~1,330.**

### PR B — Harden + broaden + the ugly cases

**Load-bearing property:** the briefing/pre-consult set exists,
tenant-scoped, index-backed, provenance-verifiable; the three ugly cases
are either defended-and-tested OR explicitly labelled
schema-correct-not-corpus-exercised — never silently authoritative.

**CARRIED FROM PR A — un-skippable definition-of-done item (equal weight
to the briefing-set verification, not prose in a description nobody
re-reads):** the live browser openable-vs-unresolvable contrast deferred
from PR A. PR B does not merge until a human eye has seen, in a browser
through the real `:3001→:8002→:5001` chain, a query result rendering
both an openable source (opens the real scan) and a visibly unresolvable
one (explicit citation, no silent dead link). This is the FIRST time the
resolved/unresolved distinction is visually confirmed; the plan's whole
thesis is that the distinction must be *visible*, not merely *correct*,
so this is load-bearing, not polish. **Constraint (rider 3, written now
while it can be seen — in PR B the pressure to violate it will be live
and this reasoning three weeks cold):** PR B's seeded demo workspace is
provisioned for the *briefing templates' own verification needs first*;
the browser-contrast check rides on whatever orphan/resolvable
distribution that legitimate seed *naturally* produces. It must NOT be
seeded-to-order to manufacture a resolvable+orphaned pair for the
click-through (that re-imports Option 2's construct-validity
anti-pattern through PR B's back door). If the honest briefing seed
contains no orphan, the correct response is to record that the
orphan-rendering case remains probe-verified-only and say so — never to
inject an orphan to complete the demo.

**Deliverables:**
- Template modules (~110 each): `patients_with_diagnosis_prefix`
  (+`order_by last_consultation`), `patients_not_seen_since`,
  `patient_active_medications`, `patient_recent_consultations`,
  `patients_with_abnormal_recent_vitals` (`data_maturity="thin"`),
  `patient_open_documents`, `patients_with_lab_threshold`
  (`data_maturity="schema_only"`).
- **`backend/migrations/026_query_layer_briefing_templates.sql`** (~620
  PL/pgSQL — six functions, provenance-in-join, `p_workspace_id`-first,
  trailing `NOTIFY pgrst`).
- **Ugly-case handling (the part the prior plan underweighted):**
  - **(i) Low-confidence:** provenance gains an optional `quality`
    sub-object resolved from `gp_validation_sessions` (batch, same
    workspace-scoped query, joined on `document_id`):
    `{section_confidence_recoverable: bool}` — **no numeric score is
    surfaced and no threshold exists** (locked decision #1). Recoverable
    → citation suffix `extraction quality not individually verified
    (document-level check available)`; not recoverable (the dominant
    15/16 case) → `extraction quality not verified`. Never
    "low-confidence," never a percentage, never a binary implying "known"
    vouched for the fact. Implements locked decision #1 exactly.
  - **(ii) Reversed/superseded source:** resolver checks
    `action_audit_log` for `PromoteDocumentToPatientRecord` with
    `reversed_by_audit_id IS NOT NULL` and no later non-reversed
    promotion → per-row `quality.superseded=true` + citation suffix
    `(source promotion was reversed — fact may be stale)`, **AND a
    mandatory `superseded_count` in the result envelope** (locked
    decision #2 — the cohort-altitude count is not optional). **Labelled
    construct-validity-only** for the live-data demonstration (corpus
    produces 0 — design choice #7); the per-row + aggregate plumbing is
    still built and unit-tested.
  - **(iii) Two-document fact:** resolver returns `sources: []` array,
    citation lists both. Schema-correct, labelled not-corpus-exercised.
- **`backend/tests/test_query_templates_integration.py`** (~360,
  RUN_INTEGRATION-gated) — each template vs live dev DB; zero
  cross-workspace leakage (run as `demo-gp-workspace-001`, assert no
  `typec-workspace-001` rows); `EXPLAIN` index usage; lab/vitals asserted
  thin; the three ugly branches (low-conf suffix; synthetic reversed
  fixture → superseded marker; multi-source fixture → array form).

**Empirical verification (all safety-load-bearing, all confirmed by the
planning probe and to be re-asserted as tests):** confidence is
section-level, recoverable 1/16; 0 live reversed-source facts; 0
two-source patients; the 15/24 orphaned rows still render
explicitly-unresolvable through the new templates (regression guard on
PR A's core property).

**Defers:** NL (PR C); standing (PR D); lab non-thinness (needs lab
ingestion, out of Phase 3).

**Size (review-required, deliberately not a single number):** the
ugly-case semantics that determine PR B's size are now locked (see
"Decisions locked at review"), so PR B is no longer *unbounded* — but the
LoC-projection method that produced the other estimates missed PR 3 by
40% on strictly easier work, and PR B is the hardest PR (it carries all
three ugly cases plus the briefing set). A single "~1,580" here would be
false precision of exactly the kind this plan otherwise refuses. **PR B
is sized by the locked semantics below, measured at implementation, not
projected** — its boundary is the decided behaviour, not a number, and it
is brought back complete (same bar as PR A), not estimated forward.

### PR C — Thinnest NL mapping (ships DISABLED)

**Load-bearing property:** a small fixed phrasing set maps to a
registered template + typed params via a constrained classifier over the
closed enum; hard refusal outside the set; no PII-bearing text reaches an
LLM unless the user explicitly authorises a provider (default off — merge
cannot leak PII); rides on primitives already provenance-verifiable from
A/B (brakes built and proven before the steering wheel).

**Deliverables:**
- **`backend/app/services/nl_query.py`** (~360) — constrained tool-call;
  tool schema generated from the registry (`all_templates()`) so it
  cannot drift; `NL_QUERY_LLM_ENABLED` default off; unmatched/low-conf →
  refusal + answerable list, never a guess.
- **`backend/app/api/query.py`** — `POST /api/query/ask` (~70).
- **`backend/tests/test_nl_query.py`** (~260) — fixed phrasing golden set
  vs **mocked** LLM (wiring, not intelligence); refusal path;
  disabled-default proven (no LLM client constructed with flag unset).
- **`backend/scripts/nl_query_eval.py`** (~120) — opt-in real-LLM eval,
  never CI; accuracy reported in PR prose, never a gate.

**Defers:** enabling the LLM (governance decision, user-deferred);
provider choice; standing (PR D).

**~810** (lower than the prior PR 9's ~1,180 — re-scoped to *thinnest
viable*, mitigating the balloon by smaller scope not hope).

### PR D — Standing-query materialisation (no UI) + Phase 3 close-out

**Load-bearing property:** a registered standing query runs on a schedule
in the existing worker and writes provenance-verifiable rows (A/B
resolution applies — briefing rows carry openable citations or explicit
unresolvable markers) into `briefing_items`, idempotently, tenant-scoped,
RLS-deny-all.

**Deliverables:**
- **`backend/migrations/027_briefing_items.sql`** (~110) — table;
  RLS-deny-all per migration 018; **add `briefing_items` to the PR 5
  tenant-guard table set (ratchet only goes down)**; `NOTIFY pgrst` note.
- **`backend/ontology/query/standing.py`** (~330) — `StandingQuery`
  registry + `materialise_standing_queries()` (wipe-and-reinsert per
  `(workspace_id, kind, as_of_date)` → idempotent); each row through
  `run_template` + `resolve_provenance` so briefing inherits the safety
  property.
- Worker scheduler tick (~90; runtime-topology assumption verified
  empirically here; pg_cron the rejected-by-default fallback).
- **`backend/app/api/query.py`** — `POST /api/query/briefing/refresh`
  (manual) + `GET /api/query/briefing` (~80).
- **`backend/tests/test_standing_queries.py`** (~240) — double-run row
  stability (idempotent); tenant scoping; provenance preserved AND
  resolved (orphaned-source rows still carry the explicit marker through
  the briefing path — safety invariant survives materialisation).
- **`ONTOLOGY_QUERY_LAYER_POSTMORTEM.md`** — Phase 3 close-out; the 15/24
  orphaned-source finding recorded as a permanent data-quality finding
  for a future backfill; what's documented-thin; what's
  construct-validity-only; **and, recorded as a permanent residual (not a
  deferral that gets closed later within Phase 3): verifiable provenance
  defends the dead-link failure but renders the wrong-extraction failure
  only checkable-but-not-checked — extraction correctness is upstream of
  the query layer; the post-mortem states this in the same words as the
  Context section so a future-self quoting the close-out to a regulator
  cannot infer a stronger property than was built.**
- **MANDATORY one-sentence scope note (named, not built):** "Conversion
  instrumentation — measuring which briefing/pre-consult items a
  prospecting or live practice acts on — is a known future consumer of
  exactly this standing-query materialisation substrate; when customers
  arrive it must be a small configuration of this infrastructure (a new
  `StandingQuery` kind writing to `briefing_items`), not a forgotten
  requirement rediscovered late."

**Defers:** briefing UI (Phase 4, confirmed); conversion instrumentation
(named only); POPIA query-access-logging (Phase 5, chokepoint exists).

**~950.**

**Total: ~1,330 (retained #13) + 1,120 (PR A) + PR B *not projected,
sized by locked semantics* + 810 (PR C) + 950 (PR D), 4 PRs.** A single
grand total is deliberately withheld: it would be dominated by the one
PR whose number this plan declines to assert. Cost is moved forward into
PR A/B where the safety work lives; PR B is delivered complete, not
estimated.

## Risks

- **The verifiability gap is the present dominant failure mode (finding
  #1), not hypothetical.** 62% of dev sourced-diagnoses resolve to a
  missing doc row. If PR A's resolver renders these as anything other
  than visibly-unresolvable, the demo shows a confident answer with a
  dead link. The orphaned-source explicit-marker test is the single
  highest-priority test in Phase 3 — CI invariant in A, regression guard
  in B and D.
- **Confidence is coarse and mostly unrecoverable (finding #2).**
  Section-level, recoverable 1/16. The honest design is correct but weak;
  a high section score does not vouch for a specific fact. The original
  risk — a "low-confidence" suffix creating false reassurance on the
  silent ones — is structurally eliminated by **locked decision #1**: no
  numeric score, no threshold, no word implying the fact was scored, and
  the dominant case renders the explicit `extraction quality not
  verified`. Residual: even this conservative phrasing is a
  section-level proxy; mitigation is design choice #7 plus the
  postmortem recording it as a permanent limitation.
- **Reversed-source / two-source defences are not corpus-exercisable
  (#3, #4).** Risk: a reviewer believes they're tested against real data.
  Mitigation: explicit construct-validity-only labelling in PR prose,
  postmortem, test names.
- **`doc_type` 0% populated.** Citation cannot say "Lancet referral
  letter." Honest builder; documented; not faked.
- **NL balloon.** Mitigated structurally by re-scoping PR C smaller.
- **Worker-topology assumption (PR D)** — verified empirically; pg_cron
  rejected-by-default fallback.
- **Heterogeneous TEXT identifiers (postmortem scar)** — all
  `patient_id`/`id` joins TEXT=TEXT, no `::uuid` cast; confirmed in #13
  Phase-0 and re-probed (0 cross-workspace mismatches).

## Decisions locked at review

All four decisions the plan reserved are now resolved at plan review.
They are LOCKED — coding implements exactly these; a deviation requires a
new explicit user call, not an implementer's judgement. The reasoning is
recorded so the calls can be overridden deliberately rather than
re-derived.

(Also locked at planning time, not re-asked: query-shape set,
NL-disabled, briefing-UI → Phase 4.)

**1. "Low-confidence" per-fact → binary, conservative phrasing, NO
implied per-fact score, NO threshold.** (safety-load-bearing) The
stronger form of option (b). Reasoning: a section-level signal rendered
as a per-fact suffix manufactures a confidence claim the data does not
support — structurally the exact failure this plan exists to prevent. A
clinician seeing "(low-confidence)" on fact X but not Y will infer Y is
*more* confident; but the signal is recoverable for 1/16 documents, so
for almost all facts the *absence* of the suffix means "we have no idea,"
not "this is fine" — turning absence-of-signal into implied reassurance.
There is therefore **no threshold** (the option-(a) "which threshold"
question is void — there is no number to threshold against at the fact
level) and **no word that implies the fact itself was scored.** Locked
citation wording:
   - section confidence *recoverable* for the source document →
     `extraction quality not individually verified (document-level check
     available)`
   - section confidence *not recoverable* (the dominant 15/16 case) →
     `extraction quality not verified`
   Never "low-confidence," never a percentage, never a known/unknown
   binary that implies "known" vouched for the fact.

**2. Reversed/superseded source → per-row suffix PLUS a mandatory
aggregate count in the result envelope.** (safety-load-bearing) Option
(b) for the single-fact case AND a non-optional cohort-level count.
Reasoning: the per-row suffix `(source promotion was reversed — fact may
be stale)` is correct for one fact a clinician reads, but the failure
that hurts is a *cohort* query where 3 of 40 rows rest on reversed
sources and the clinician scans the list and acts on the cohort whole —
the per-row marker is invisible at the altitude the query is actually
used. The result envelope therefore carries `superseded_count` (e.g. "3
of 40 results have a superseded source") surfaced at cohort level.
Hiding (a) is rejected — silent cohort shrinkage is its own trust
violation. Flag-only (c) is rejected — same per-row-attention failure as
the suffix alone. **The aggregate count is not optional polish; it is the
part that makes the defence work at the altitude the failure occurs.**
(Corpus produces 0 — construct-validity-only per design choice #7; the
*aggregate plumbing* is still built and unit-tested, only the live-data
demonstration is labelled not-corpus-exercised.)

**3. Unresolvable-case citation → truncated id, not opaque.** Locked:
`source document no longer available (id …e15a71)` (last 6 hex of the
id). Reasoning: a partial id reads as "the system knows precisely which
record and is telling me it's gone" — the honest state, a precise
known-unknown — whereas bare "source unavailable" reads as a vague system
fault. The truncated id converts a scary blank into the safe-failure
posture the whole plan is built around.

**4. `clinical_query` stays explicit-grant, OUT of foundation; product
set resolved at review on a COHERENCE argument.** Locked: explicit-grant,
never `foundation_bundle`, never default — highest-blast-radius read
surface. The product set within that lock, forced into the open by the
entitlement reality, is resolved as: `platform_essential` +
`platform_professional` (per the 023 `patient_admin` precedent) **+
`legacy_full_access_grant`**. The justification is coherence, NOT
demo-enablement: `legacy_full_access_grant` already entails
`analytics_cohorts`, `audit_log`, and `clinical_ai_*` (strictly more
sensitive read surfaces); a "full access" grant that excludes the query
layer is an *incoherent* entitlement, not a tighter blast radius. That
this also lets the flagship demo practice exercise the query layer is a
*consequence* of the demo workspace being correctly on full-access — not
the reason for the mapping. Precedent rule established: entitlement
mappings are chosen for semantic correctness; workspaces are placed on
the product that matches their role; a demo that needs a capability
moves the workspace to the right product, never widens the capability to
reach the workspace. **`module_digitisation` is excluded as a written
customer promise** (the Type C leave-behind), regression-guarded by a
build-failing CI ratchet
(`test_query_layer_invariants.py::test_module_digitisation_never_entails_clinical_query`,
proven non-vacuous against one-line / multi-line / reversed-order
injection). Migration 025 seeds this; its header encodes the coherence
justification and the corrected corpus-honesty finding (below) so a
future maintainer cannot re-derive it wrongly.

*Corpus-honesty finding attached to this decision:* the workspace this
mapping legitimately reaches (`demo-gp-workspace-001`,
`legacy_full_access_grant`) has 0 diagnoses, so the shipped template is
empty there; the orphaned/resolvable data lives in non-entitled
workspaces. The resolver safety property is verified by Phase-0 probe
(iv) + the API tests; a one-screen browser click-through needs a
provisioned platform-tier demo workspace (named, not faked). See the PR
A "Empirical verification" block and the open smoke-vehicle decision.

## What Phase 3 earns when it lands

When PR D merges, SurgiScan stops being a digitiser and becomes
*trustworthy* queryable clinical infrastructure — the word that matters
is *trustworthy*, not *queryable*. From the first runnable query in PR A,
a clinician (or a prospecting doctor in a demo) gets a tenant-scoped
ranked answer where every row's source is not just present but
*verifiable*: it opens the actual scan with a human citation, or it tells
the clinician *visibly* that the source cannot be opened. **The dead-link
failure mode — the measured, dominant one — becomes a known unknown the
clinician sees, never a confident wrong answer with a dead link they
trust.** The residual that remains, stated without softening: a row whose
link *does* open can still rest on a wrong extraction of the underlying
scan; verifiable provenance makes that checkable by whoever opens the
scan, but a demo viewer and a hurried clinician do not, so
wrong-extraction-behind-a-live-link is checkable-but-not-checked — a real
residual risk Phase 3 surfaces and does not close (extraction correctness
is upstream of the query layer). The morning briefing and pre-consult
brief are registered standing queries already materialising into
`briefing_items`, inheriting that verifiability, waiting only for the
Phase 4 UI. The platform earns this honestly: provenance is the
correctness mechanism (a CI invariant from line one, not bolted on three
PRs late), tenant-scoping is structural, and the things it cannot do —
guarantee a live-link extraction is itself correct (only make it
checkable), precise per-fact confidence, defend a reversed-source live
fact, answer lab-threshold questions, see PII without a governance
decision — are documented deferrals and labelled construct-validity
limits, not silent gaps.
