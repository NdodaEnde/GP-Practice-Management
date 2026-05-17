# Phase 4 — PR H Implementation Plan: the Phase-4 close-out (scoped FIRST) + the pre-consultation brief

> **Status:** plan APPROVED at review at the A/B/C/D bar. **H-1..H-4
> FINAL (§5)** + **five required strengthenings recorded** (1: gate
> asserts the `provision_briefing_demo.py:70-78` quotation byte-faithful
> to live source, proven to bite by mutating it; 2: human sufficiency =
> the not-invertible-to-met standard, §2.4 framing; 3: allergies/RFV/
> open-loops named-not-built WITH reasons, override declined; 4: §D
> locked load-bearing-equal of §A — the credential, gate-enforced; 5:
> this gate's scaffolding written to the code bar + reviewed before run,
> no residue net). Grounded in fresh recon + the actual PR-D gate-test
> code (not its description — §D.1), **2026-05-17, `main`@`298ab72`**.
> PR H is **the LAST PR of Phase 4** and carries the heaviest inherited
> load in the project. **The close-out is PR H's load-bearing part —
> scoped FIRST, the gate proven to bite BEFORE any pre-consult code —
> exactly as PR D scoped its close-out first.** The pre-consult brief is
> the harvest, secondary. No code until the five strengthenings are in
> the plan (done); then the build in the PR-D order.
>
> **The build order is load-bearing, not a slogan (the PR-D shape):**
> the Phase-4 close-out artifact + its build-failing non-vacuous gate are
> built and the gate proven to bite **before** the pre-consult
> composition code exists. PR H is genuinely **not mergeable with the
> pre-consult composition green and the close-out gate red**. Phase 4
> closes honestly on a formally-UNMET defining safety constraint; the
> close-out is where that lands.
>
> **The heaviest inherited load, carried explicitly (verified against
> the live artifacts + the gate-test code, not memory):**
> - **The Option-2 / Decision-5 path-(ii) carry-forward.** Both halves
>   of the openable-vs-unresolvable contrast carry forward UNMET
>   ([[project-phase4-pr-e-option2-gate]]; PR E held, no clinician-visible
>   surface — re-confirmed: `MorningBriefing.jsx`/`briefing.js` untracked
>   on `main`@`298ab72`). The Phase-4 close-out records this through the
>   **build-failing presence gate proven non-vacuous** (umbrella
>   Decision 4 = the §2.4 mechanism), and its most load-bearing sentence
>   is a **VERBATIM QUOTATION**, NOT newly-authored prose:
>   `backend/scripts/provision_briefing_demo.py:70-78` —
>   *"orphan-rendering remains probe-verified-only … no orphan was
>   injected to complete the demo. That is the EXPECTED path, not a
>   failure."* — PLUS the umbrella/Decision-5 locked sentence verbatim:
>   *"Phase 4 closed with its defining safety constraint — the
>   openable-vs-unresolvable contrast seen by a human — formally UNMET
>   and re-inherited to Phase 5."*
> - **The conversion-instrumentation named-not-built note** + **the
>   shared-trigger sentence** — carried into the Phase-4 close-out (the
>   Phase-4 close inherits these Phase-3 obligations because Phase 4 is
>   the phase that closes); the gate asserts them present + non-vacuous.
> - **§5.1 FK-cycle idiom** and **§4.1 raise-test-scaffolding-to-the-
>   code-bar** (PR F/PR G) — PR H's own test scaffolding is written and
>   reviewed to the code bar before any run (the stale-edit / wrong-
>   teardown-order / NameError class is NOT acceptable-because-harmless);
>   any audit-row teardown uses the cycle-safe idiom.
> - **§2.0 falsified-premise discipline** — the pre-consult "composition
>   of everything you need" is premise-checked against the live corpus,
>   not re-derived from the roadmap's wk14 framing.

---

## 1. Empirical findings (live, read-only, 2026-05-17 `main`@`298ab72`)

### Finding H1 — the PR-D close-out gate mechanism (read in the actual code; PR H mirrors it EXACTLY)

`backend/tests/test_standing_queries.py:30-120`: `_section(text,start,end)`
slices between markers; `_assert_closeout_artifacts(text)` runs the
load-bearing assertions, each raising `AssertionError` naming the
missing element, **factored out so the non-vacuity test can prove each
BITES**; `test_postmortem_closeout_artifacts_present()` is the
build-failing **necessary** gate on the real artifact;
`test_closeout_gate_is_non_vacuous` is **parametrized over each
load-bearing phrase**, removes it (all case variants) from a copy and
`pytest.raises(AssertionError)` — proving the gate bites; **permanent
CI, not a one-time check**. Docstring discipline (`:11-16`): the gate is
the *automatable necessary* condition; the *human §2.4 read by the named
verifier* is the sufficiency; **"discharged" ≠ "parser passed"**. PR H's
Phase-4 close-out gate is this mechanism, pointed at a NEW Phase-4
artifact with Phase-4-specific load-bearing sentences (NOT copied from
Phase 3).

### Finding H2 — the pre-consult brief, honestly classified against the live corpus (the §2.0/PR-G premise check)

Roadmap wk14 frames pre-consult as a *composition* of: diff-against-
last-visit (audit log), open loops, reason-for-visit, meds + allergies.
Against `main`@`298ab72`:

| Pre-consult input | Live state (file:line) | Honest class |
|---|---|---|
| Diff-against-last-visit | `migrations/014_action_audit_log.sql:47-91` — table + `affected_objects` JSONB + GIN index `@>` containment exist; **NO query template / builder** in `ontology/query/templates/` | **DATA+MECHANISM EXIST, builder NOT built** — composable but needs a (small) builder, not new infra |
| Open loops | `open_loops` (PR F, migration 028) — substrate only, **ZERO real instances** (F-1=B, no detector on main); PR G added one *stateless derived* kind (`immunisation_overdue`), NOT a stateful loop | **CANNOT source open loops** — no real loop exists; named-not-built |
| Active medications | `ontology/query/templates/patient_active_medications.py` — template + RPC, `data_maturity="populated"` | **BACKED** (real) |
| Allergies | `allergies` table exists; **NO ontology query template** (grep: none) | **table-only, no template** — composable only if a template is built |
| Reason-for-visit | no appointment table/object/ingestion anywhere; `consultation.reasoning` is post-fact clinical reasoning, not RFV ingestion | **ZERO backed** — named-not-built |
| Clinician-visible surface | PR E held: `MorningBriefing.jsx`/`briefing.js` untracked on `main` | **NO merged surface** — pre-consult is backend composition, not clinician-visible |

**The premise-correction (the §2.0 register, recorded so it is not
re-derived):** "the pre-consult brief is a composition of everything you
need" is, against the live corpus + PR E held, **false**. Honestly it
composes: active-medications (backed) + a per-patient audit-log diff
(data+index exist; a small builder, not new infra) + the
`immunisation_overdue` thin derived kind (PR G). It **cannot** honestly
source open loops (zero real instances), allergies via the query layer
(no template), or reason-for-visit (no ingestion); and there is **no
merged clinician-visible surface** (PR E held). PR H ships the honest
composition + names the rest — it does NOT ship "the full pre-consult
brief a doctor sees."

### Finding H3 — PR E held, re-confirmed (the surface reality the close-out states)

`git log origin/main -4` = `298ab72 (PR G) → f34cbf5 (PR F) → 51d1664
(PR D) → 57a08b2`. `MorningBriefing.jsx`, `briefing.js`,
`ONTOLOGY_PHASE4_PRE_PLAN.md`, `ONTOLOGY_PHASE4_PROACTIVE_LAYER_PLAN.md`
all **untracked** on `main`. The openable-vs-unresolvable contrast was
never made clinician-visible; that is the constraint Phase 4 closes
**UNMET** on, recorded in the verbatim pre-committed words.

---

## 2. The load-bearing part of PR H — the Phase-4 close-out (scoped FIRST, PR-D weight, gate proven to bite before any pre-consult code)

> **This section is PR H.** §3's pre-consult composition sits on top of a
> genuinely-discharged close-out, not alongside an assumed one — exactly
> as PR D's standing-query code sat on a genuinely-discharged Phase-3
> close-out. The gate is built and proven non-vacuous BEFORE §3.

### 2.1 The artifact — `ONTOLOGY_PROACTIVE_LAYER_POSTMORTEM.md` (the Phase-4 close-out, the Phase-3-postmortem register)

Sibling of `ONTOLOGY_QUERY_LAYER_POSTMORTEM.md`. Required sections + the
**Phase-4-specific load-bearing sentences** (each gate-enforced + proven
non-vacuous):

- **§A — the defining constraint, formally UNMET, in the locked words.**
  Verbatim, NOT authored this turn: *"Phase 4 closed with its defining
  safety constraint — the openable-vs-unresolvable contrast seen by a
  human — formally UNMET and re-inherited to Phase 5."* Plus the
  **verbatim quotation** of `provision_briefing_demo.py:70-78`:
  *"orphan-rendering remains probe-verified-only (verify_query_phase0.py
  probe iv/v + the unit form in test_query_layer_invariants.py); the
  browser contrast confirmed OPENABLE and NO_SOURCE rendering only; no
  orphan was injected to complete the demo." … "That is the EXPECTED
  path, not a failure. The orphaned-source case is the dominant corpus
  finding (15/24 on test-workspace-* tenants) and is verified there by
  the probe, never manufactured here."* The close-out's most
  load-bearing sentence is this quotation of a pre-merge commitment —
  the §C/§E discipline at its strongest (trusted because merged before
  any pressure to soften it, by a past instance that could not have been
  serving this moment because this moment did not exist yet).
  **Strengthening 1 (locked):** the quotation is re-read from
  `backend/scripts/provision_briefing_demo.py:70-78` at the moment the
  close-out is authored (NOT from memory — §D.1), and the gate asserts
  it **byte-faithful to the live source file**, proven to bite by
  mutating the quotation and asserting red — not merely present. Trust
  on author-care alone is the one gap the §D.1 false-green lived in;
  closed here mechanically.
- **§B — what Phase 4 actually delivered, honestly.** OpenLoop substrate
  (PR F; proven-to-bite state machine; ZERO real instances, F-1=B); one
  thin derived kind (PR G; `immunisation_overdue`, 1/31, labelled thin,
  NOT corpus-proven at volume); the pre-consult honest composition
  (§3). What it did NOT deliver, unsoftened: no stateful loop, no
  detector, no clinician-visible surface (PR E held), the contrast not
  human-visible. No overclaim.
- **§C — the carried Phase-3 obligations re-inherited, verbatim.** The
  conversion-instrumentation named-not-built note (anchors:
  "conversion instrumentation", "StandingQuery", "briefing_items") and
  the shared-trigger sentence ("one review",
  "project_phase3_tracked_deferrals") — carried into the Phase-4
  close-out because Phase 4 is the phase that closes; gate-enforced +
  non-vacuous, the PR-D pattern.
- **§D — the legible scars: THE CREDENTIAL (strengthening 4 — locked
  load-bearing-equal of §A, gate-enforced + non-vacuous, NOT a
  supporting section).** The §D.1-class notes made legible: PR D's
  false-green caught after signature, PR F's FK-cycle teardown, PR G's
  stale-assertion scaffolding failure, AND the method *compounding*
  (PR F's scar → PR G's prophylaxis: residue-safe teardown applied
  before the run → zero residue where PR F had residue), the
  raise-test-scaffolding-to-the-code-bar cure. **Why §D is
  load-bearing-equal of §A, not below it:** §A states the constraint was
  unmet; §D is the evidence the system that failed to meet it is
  nonetheless trustworthy — it caught its own failures, recorded them
  unsoftened, improved from them. A close-out recording only the unmet
  constraint is honest but bleak; one recording the unmet constraint AND
  the legible caught-failure history AND the compounding is the actual
  credential — it says the constraint was not met and *here is why you
  can trust the system that says so*. The gate asserts §D's load-bearing
  sentences present + proven non-vacuous, the same weight as §A.
- **§E — what re-inherits to Phase 5.** The formally-UNMET contrast
  constraint (the §A sentence); the conversion-instrumentation /
  shared-trigger first-customer trigger; the legitimate-A door
  (specialist-referral-pending as a future stateful loop, a deliberate
  user call never inferred). Stated as Phase 5's inherited load, the
  §2.4 necessary-not-sufficient framing carried.

### 2.2 The build-failing non-vacuous gate (mirrors `test_standing_queries.py` EXACTLY)

A new test (e.g. `backend/tests/test_phase4_closeout.py`) reproducing the
H1 mechanism verbatim in shape: `_section` helper; an
`_assert_phase4_closeout_artifacts(text)` with the Phase-4-specific
load-bearing assertions — (i) the §A formally-UNMET locked sentence
present; (ii) the verbatim `provision_briefing_demo.py:70-78` quotation
present AND **byte-faithful to the live source file** (strengthening 1:
the test reads `backend/scripts/provision_briefing_demo.py`, extracts
lines 70-78, and asserts the close-out contains that exact byte
sequence — not a paraphrase, not "the phrase is present"); (iii) the
conversion-instrumentation three anchors; (iv) the shared-trigger
"one review" + memory key; (v) §D's load-bearing scar sentences
(strengthening 4 — §D gate-enforced equal to §A) — each raising a named
`AssertionError`; `test_phase4_closeout_artifacts_present()` the
build-failing necessary gate; `test_phase4_closeout_gate_is_non_vacuous`
**parametrized over each load-bearing phrase**, removing it from a copy
and asserting the gate raises — **AND the byte-faithfulness assertion
proven to bite by mutating the quotation and asserting red** (the
non-vacuity itself non-vacuous, the PR-G discipline) — **permanent CI**.
The docstring carries the necessary-not-sufficient discipline verbatim,
and **strengthening 2**: the human sufficiency is the
**not-invertible-to-met standard** — the named verifier (you) confirms
no sentence, *especially the quotation* (pulls out of context more
easily than authored prose), can be inverted by an adversarial reader
quoting in isolation into "Phase 4 met its safety constraint".
"Discharged" ≠ "parser passed". **Strengthening 5: this gate's test
scaffolding is written to the code bar and reviewed BEFORE the run** —
the §4.1 two-consecutive-scaffolding-failures note applies *here
specifically* because **a presence-gate has NO residue net**: the
assertion is the only safeguard; a first-run scaffolding failure in this
test is the one place "harmless because residue caught it" is not
harmless. **Proven to bite BEFORE any pre-consult code (H-3 build
order).**

---

## 3. The pre-consult brief — the honest composition (the harvest, on a discharged close-out)

Under the H2 honest classification: a backend pre-consult composition
that assembles, per patient, ONLY what the corpus backs — active
medications (the `patient_active_medications` template, real) + a
per-patient audit-log diff-since-last-visit (a small builder over the
existing `action_audit_log` `affected_objects` GIN-indexed `@>`
containment — data+mechanism exist, not new infra) + the
`immunisation_overdue` thin derived kind (PR G). **Strengthening 3
(locked) — named-not-built WITH reasons, so a future reader inherits
*why* not built, not "the brief is incomplete" as a defect:**
- **allergies-via-query-layer** — the `allergies` table exists but there
  is NO ontology query template; building one *for pre-consult
  completeness* is net-new query-layer work whose only driver is PR-H
  completeness (legitimate-in-general, not-for-this-reason-now — the
  purest form of the anti-pattern; the override was DECLINED, H-2).
- **reason-for-visit** — no appointment ingestion path anywhere (no
  table/object/endpoint); `consultation.reasoning` is post-fact, not RFV.
- **open loops** — zero real instances (F-1=B substrate only; PR G added
  one *stateless derived* kind, not a stateful loop; no detector on
  main).
It is **backend composition, NOT clinician-visible** (PR E held) — the
close-out's §B states this unsoftened; the pre-consult earns "composes
what's backed, verified by read-back", NOT "the doctor sees a
pre-consult brief". Conforms to the verified template/registration
idioms; no fabricated input presented as corpus (design-choice-#7);
reuses the chokepoint (no new data path).

---

## 4. Tests / verification (the bar; the close-out gate FIRST and proven to bite)

- **FIRST: the Phase-4 close-out gate** (§2.2) — built, the artifact
  written, `test_phase4_closeout_artifacts_present` green and
  `test_phase4_closeout_gate_is_non_vacuous` proving each load-bearing
  phrase BITES on removal — BEFORE any pre-consult code. PR H not
  mergeable with §3 green and this red.
- **Test scaffolding to the code bar (§4.1 inherited):** every teardown
  / fixture / in-place test edit reviewed before the run; no
  stale-assertion / wrong-teardown-order / NameError class accepted as
  harmless; the residue net is not the reason a scaffolding bug is okay.
  Any audit-row teardown uses the §5.1 FK-cycle-safe idiom.
- Pre-consult composition: the audit-log-diff builder + meds + the
  derived kind unit-tested; RUN_INTEGRATION read-back of a real
  per-patient composition on the live corpus (the PR-G read-back
  discipline), residue-safe teardown asserted to baseline.
- Tenant ratchet stays green (any new chain born workspace-scoped, zero
  new BASELINE keys — verified by running it).

---

## 5. Decisions locked at review — H-1..H-4 FINAL + five required strengthenings

Recorded as the user locked them; the reasoning is the lock. No
umbrella/prior decision re-opened. **No code until all five
strengthenings are in this plan (done below).**

**H-1 — FINAL: the close-out + gate, with TWO required strengthenings.**
`ONTOLOGY_PROACTIVE_LAYER_POSTMORTEM.md`, §A–§E (§D load-bearing-equal of
§A — strengthening 4). The gate mirrors `test_standing_queries.py`
EXACTLY (factored `_assert`, build-failing `_present` necessary test,
`_non_vacuous` parametrized-over-each-load-bearing-phrase removed-and-
asserted-to-bite, permanent CI, necessary-not-sufficient). The §A
sentence is the verbatim locked Decision-5 wording + the verbatim
`provision_briefing_demo.py:70-78` quotation.
- **Strengthening 1 — byte-faithfulness, gate-enforced.** "Quoted from
  source at authoring time, never from memory" is necessary, NOT
  sufficient (the §D.1 lesson: a quotation believed faithful is not
  verified until mechanically checked). The non-vacuous gate MUST assert
  the close-out's quotation is **byte-faithful to the live
  `backend/scripts/provision_briefing_demo.py` lines 70-78** (read the
  source file in the test, compare bytes), and that assertion MUST be
  proven to bite by **mutating the quotation and asserting red** — not
  merely that the phrase is present. The most load-bearing sentence in
  the project's terminal artifact is verified against live source
  mechanically, not on author care (the one gap the §D.1 false-green
  lived in, closed).
- **Strengthening 2 — the human sufficiency is the not-invertible-to-met
  standard.** PR H's close-out records a phase closing with its defining
  constraint UNMET; the human read (the named verifier, you) is NOT
  "confirm the prose is honest" but "confirm no sentence — *especially
  the quotation*, which pulls out of context more easily than authored
  prose — can be inverted by an adversarial reader quoting in isolation
  into 'Phase 4 met its safety constraint'." Stated in the §2.4
  necessary-not-sufficient framing carried into the Phase-4 close-out:
  parser-green is necessary; the not-invertible-to-met human read is the
  sufficiency. "Discharged" ≠ "parser passed".

**H-2 — FINAL: compose-what's-backed; the override (build the allergies
template) is DECLINED.** Active-medications (backed) + the
audit-log-diff builder (data + GIN `@>` index exist; a small builder on
existing infra, NOT new query-layer infra) + `immunisation_overdue` (PR
G thin kind). The survives-deleting-the-feature test, ninth application:
building the allergies query-template has no reason that survives
deleting "the pre-consult brief would be more complete with allergies" —
it is net-new query-layer work whose only driver is PR-H completeness
(legitimate-in-general, not-for-this-reason-now, the purest form).
**Strengthening 3:** allergies-via-query-layer AND reason-for-visit AND
open-loops are recorded **named-not-built with their reasons** (allergies:
table exists, no template, building-for-completeness is the anti-pattern;
RFV: no ingestion; open-loops: zero real instances, F-1=B/G-1=B) — so a
future reader inherits *why* not built, not "the brief is incomplete" as
a defect. Backend composition, NOT clinician-visible (PR E held), stated
verbatim in §B.

**H-3 — FINAL: build order is the PR-D shape, non-negotiable.** Close-out
artifact written (quotation re-read from source at authoring time) +
the non-vacuous gate built and **proven to bite — including the
byte-faithfulness assertion proven to bite by mutating the quotation**
(the non-vacuity itself non-vacuous, the PR-G discipline) — BEFORE any
pre-consult composition code. PR H not mergeable with §3 green and the
gate red. **Strengthening 5:** PR H's gate test scaffolding is written
to the code bar and reviewed BEFORE the run — the inherited
two-consecutive-scaffolding-failures note (§4.1) applies *here
specifically* because **this gate has no residue net**: a presence-gate
has only the assertion itself; a first-run scaffolding failure in *this*
test is the one place "harmless because residue caught it" would not be
harmless.

**H-4 — FINAL: yes, PR H closes Phase 4 — on the precise condition,
stated unsoftened.** When the gate is green (incl. byte-faithfulness)
AND you have read the actual prose and confirmed the not-invertible-to-
met standard, Phase 4 closes. **What it closes AS, locked exactly:**
Phase 4 closes having delivered the OpenLoop substrate (proven, zero
real instances), one thin derived kind, an honest backend pre-consult
composition — and having **formally recorded, gate-enforced, in
pre-merge-quoted words, that its defining safety constraint (the
openable-vs-unresolvable contrast seen by a human) was NOT met and is
re-inherited to Phase 5**. "Closes" means **the obligation to record it
truthfully is discharged — NOT that the constraint was satisfied**. It
is not a successful phase in the sense of meeting its defining
constraint; the close-out must not let any reader read it as one. The
carried obligation does not thin in transit — it arrives as the
verbatim quotation it was pre-committed as; PR H's only job for it is to
record it faithfully and prove the recording bites. The legitimate-A
door and the contrast both go forward to Phase 5 as named, not lost.

**§D is the credential (strengthening 4, locked load-bearing-equal of
§A).** Every prior PR's close was "work sound, load-bearing part proven,
merge." PR H's terminal artifact's credibility does NOT come from being
green — it comes from §D: the legible scars (PR D's false-green caught
after signature, PR F's FK-cycle teardown, PR G's stale-assertion
scaffolding failure) AND the method *compounding* (PR F's scar →
PR G's prophylaxis, zero-residue where PR F had residue). §A states the
constraint was unmet; §D is the evidence the system that failed to meet
it is nonetheless trustworthy — it caught its own failures, recorded
them unsoftened, improved from them. §D is locked **load-bearing-equal
of §A**, gate-enforced + non-vacuous, NOT a supporting section: a
close-out recording only the unmet constraint is honest but bleak; one
recording the unmet constraint AND the legible caught-failure history
AND the compounding is the actual credential — it says the constraint
was not met and here is why you can trust the system that says so.

## What Phase 4 closes (honestly) when PR H lands

Phase 4 delivered the proactive substrate: the `OpenLoop` object + a
closed proven-to-bite state machine + audited reversible actions (PR F),
one thin real derived cohort (PR G, `immunisation_overdue`, labelled
thin), and a backend pre-consult composition of what the corpus backs
(PR H). It did **not** make the openable-vs-unresolvable safety contrast
visible to the human it protects — PR E is held, there is no merged
clinician surface, and that defining constraint is recorded **formally
UNMET and re-inherited to Phase 5 in the verbatim pre-committed words**,
through a build-failing gate proven non-vacuous and a human read of the
actual prose. The platform's trust thesis is upheld not by claiming the
property is visible but by stating, in words merged before any pressure
to soften them, exactly that it is not — the §C/§E discipline at the
hardest point in the project, the close of a phase on its own unmet
defining constraint. The scars are legible, the method compounded, and
nothing was manufactured to make the close look cleaner than it is.
