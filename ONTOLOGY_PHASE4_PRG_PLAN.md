# Phase 4 — PR G Implementation Plan: the SA-primary-care loop taxonomy + its detectors (the F-4 policy layer)

> **Status:** plan APPROVED at review at the A/B/C/D bar. **G-1..G-5
> FINAL (§5).** Grounded in fresh recon + my own read-only live-DB
> data-maturity probe **2026-05-17, `main`@`f34cbf5`** (PR F merged).
> **G-1 = option B**: the user DECLINED the legitimate-A call (reasoned
> decline — §5); PR G ships **immunisation-overdue** as ONE real derived
> `StandingQuery` kind (stateless, thin 1/31); specialist-referral-
> pending + 5 others named-not-built; the legitimate-A door stays a
> deliberate FUTURE user call, NOT made here. The four required
> recordings are applied: §2.0 (the "8–12 taxonomy" falsification note),
> the G-2-under-B "no new tick / no loop detector — the existing
> materialiser serves the new kind" clarification, the G-4 verbatim
> earns-split, and G-1=B with the legitimate-A-door-not-made-here. No
> umbrella/PR-F decision re-opened. PR G under B is the **derived-cohort
> registration** (the PR-D "configuration, not a project" payoff) — NOT
> a loop-opening detector, NOT a stateful loop, NOT a new tick. Migration
> 029 (the immunisation-overdue RPC) is **surfaced for the user's
> per-migration call** — the rejected auto-apply gate stays tombstoned,
> 028 the one-time exception, not precedent. No code until these
> recordings are in the plan (done below); then the build at the bar.
>
> **PR F inheritance carried explicitly (verified against current code,
> not assumed):**
> - **§2.0 holds, re-verified on `main`@`f34cbf5`:** every existing
>   follow-up mechanism is STATELESS recomputed-cohort or
>   WRITE-ONCE-INERT (procedures.follow_up, immunisations.overdue,
>   referrals.status, EncounterType.FOLLOW_UP, patients_not_seen_since).
>   By locked Decision 3 the stateless ones **stay StandingQuery kinds —
>   they are NOT OpenLoop rows**; PR G must NOT invent an
>   `acknowledged_on`/`closed_by` lifecycle on them (the symmetric
>   misclassification). PR G is still an *introduction*, not a refactor.
> - **F-1=B / F-3:** `LoopKind` currently = `SPECIALIST_REFERRAL_PENDING`
>   (named, not instantiated) + `OTHER` (structural minimum). The
>   taxonomy is PR G's to add — but ONLY kinds PR G can honestly back
>   (enum value with no detector + no honest instance = fake-property,
>   forbidden). Extensibility is structural (TEXT column; add a member,
>   no migration churn).
> - **F-4:** detectors are PR G's; they ride the existing
>   `@app.on_event("startup")` host, **env-gated default-off**, same
>   discipline as `standing_query_scheduler` — proven inert at merge.
> - **Legitimate-A carve-out (locked):** `specialist_referral_pending`
>   may become PR G's first stateful loop ONLY as a **deliberate
>   PR-G-merits decision, stated as such by the user — never inferred**.
>   Surfaced in §6 G-1, not chosen here.
> - **§5.1 FK-cycle idiom (inherited):** any PR-G detector cleanup /
>   maintenance touching `action_audit_log` reversal pairs MUST use the
>   cycle-safe idiom (null both `reverses_audit_id`/`reversed_by_audit_id`
>   on all collected ids, then delete). It bit once already; PR G
>   inherits it, does not re-derive it.
>
> **Premise the probe corrected/sharpened (norm #1):** the umbrella
> framed PR G as "the 8–12 loop taxonomy + detectors, harvested through
> PR E's surface." The live probe sharpens this hard: (a) of the 7
> SA-primary-care kinds, only **2** have any backing
> (immunisation-overdue, specialist-referral-pending) and **5 are
> unbacked** (no data path today); (b) `referrals` is **empty (0 rows
> everywhere)** so even the one stateful candidate is
> construct-validity-only on this corpus; (c) **PR E is held — its
> briefing UI is untracked/unmerged** on `main`, so PR G's materialised
> rows have **no merged surface a doctor sees**. PR G is therefore NOT
> "ship the taxonomy"; it is "ship the one honestly-backed derived
> cohort + at most one stateful-loop vertical slice (labelled
> construct-validity-only), name the rest, and state the no-UI reality" —
> the §2 load-bearing classification, scoped FIRST.

---

## 1. Empirical findings (live, read-only, 2026-05-17 `main`@`f34cbf5`)

### Finding G1 — §2.0 classification re-verified on current main (unchanged)

procedures.follow_up (`backend/api/procedures.py:46-47,291-312`),
immunisations.overdue (`backend/api/immunizations.py:43,295-316`),
referrals.status (`backend/server.py:4909-4962`, write-once `'pending'`,
no update endpoint), `EncounterType.FOLLOW_UP`
(`consultation_enums.py:34`, a classifier), `patients_not_seen_since`
(`standing.py:123-128`) — **all STATELESS or WRITE-ONCE-INERT, no
change** vs PR F's §2.0. Locked Decision 3 holds; the stateless ones are
StandingQuery-kind candidates, not OpenLoop rows.

### Finding G2 — the OpenLoop substrate as merged (the API PR G's detectors call)

`open_loop_enums.py`: `LoopKind = {SPECIALIST_REFERRAL_PENDING, OTHER}`.
4 audited actions, exact signatures (recon-verified):
`OpenLoopOpen(loop_id?, patient_id, loop_kind, opening_event_kind,
expected_closing_event_kind, urgency, deadline_at, actor_user_id,
practice_id, workspace_id)`; `OpenLoopAdvance/Breach(loop_id,
actor_user_id, practice_id, workspace_id)`; `OpenLoopClose(loop_id,
closed_reason, actor_user_id, practice_id, workspace_id)`. All route
through `app/actions/executor.py::execute(action, *, actor, supabase,
practice_id, workspace_id)`. **Authorization deferred to PR G (F-4):**
no `HasPermission` precondition on any of the four — see §6 G-5.

### Finding G3 — the standing-query substrate PR G extends (the derived-kind path)

`standing.py`: `StandingQuery{kind,template_id,params,description}`,
`register_standing`, `materialise_standing_queries(supabase, *,
as_of_date, only_workspace=None)`, idempotent per-(ws,kind) partition
rewrite into `briefing_items` (migration 027). A NEW derived kind =
(1) a query template `ontology/query/templates/<name>.py` +
`register_template`, (2) its PL/pgSQL in the next migration ending
`NOTIFY pgrst`, (3) an import line in `ontology/query/registered.py`,
(4) a `register_standing(StandingQuery(...))` call. 8 templates exist;
`morning_briefing` is the only registered standing kind.

### Finding G4 — the detector host (F-4)

`server.py:5361-5383` `@app.on_event("startup")`;
`standing_query_scheduler.py:41-94` is the singleton + flag-gated tick
template (`STANDING_QUERY_TICK_ENABLED` default false → no task created;
`_tick_loop` per-iteration try/except; interval env var). A PR-G
detector tick follows this exact pattern under its OWN env flag,
default-off, proven inert at merge.

### Finding G5 — data-maturity actuals (my read-only probe; the design-choice-#7 input)

| Taxonomy item | Backing | Live corpus (probed) | Honest label |
|---|---|---|---|
| **immunisation-overdue** | `immunizations` table (`api/immunizations.py`) | 31 total in demo-gp; **1 overdue** | **DERIVED, thin-but-real** |
| **specialist-referral-pending** | `referrals` table | **0 rows everywhere** | STATEFUL-when-built, but **construct-validity-only** (empty corpus) |
| abnormal-vitals | `patients_with_abnormal_recent_vitals` template | 6 vitals / 3 abnormal | DERIVED, thin |
| lab-threshold | `patients_with_lab_threshold` template | 1 lab_result | DERIVED, schema_only |
| chronic-script-expiring | none | no prescription-expiry path | **unbacked** |
| diabetic-foot-exam-due | none | no foot-exam path | **unbacked** |
| retinal-screening-due | none | no screening-due path | **unbacked** |
| medication-reconciliation-needed | none | no reconciliation-state path | **unbacked** |

### Finding G6 — PR E held: no merged surface

`MorningBriefing.jsx` / `briefing.js` are **untracked on `main`@`f34cbf5`**
(PR E held). The briefing *substrate* (`materialise_standing_queries`,
`briefing_items`) IS merged; the *UI* is not. PR G's materialised rows
have **no merged surface a doctor sees**. PR G's honest earns claim is
backend materialisation, NOT "the doctor sees these".

---

## 2.0 §D.1-class note — "ship the 8–12 loop taxonomy" was FALSIFIED at plan time against the live corpus (recorded so it is NOT re-derived from the stale umbrella number)

> Same register as PR F's §2.0 / the post-mortem's §D·§D.1: a premise
> that read sound in the umbrella, tested against the live corpus at
> PR-G plan time, and found false. PR H and any re-reader of the
> umbrella must inherit the *finding*, not re-derive "8–12" from the
> umbrella's stale estimate.

The umbrella framed PR G as "the 8–12 SA-primary-care loop taxonomy +
detectors." At PR-G plan time that was probed against `main`@`f34cbf5`
and the live corpus (Finding G5) and **falsified**: of the 7 named
kinds, exactly **one** has real (thin) backing
(immunisation-overdue, 1 overdue / 31), **one** is a genuinely-stateful
candidate with an **empty corpus** (specialist-referral-pending,
`referrals`=0 rows everywhere), and **five** have no data path at all
(chronic-script-expiring, diabetic-foot-exam-due, retinal-screening-due,
medication-reconciliation-needed, + abnormal/lab thin/schema-only). The
umbrella's "8–12" was a **stale estimate, not a corpus fact**.

**Therefore PR G ships ONE real derived kind, not a taxonomy.** Under
the locked G-1=B it ships immunisation-overdue (derived, thin, real);
specialist-referral-pending and the rest are named-not-built. A future
maintainer / PR H / any umbrella re-reader must inherit "the taxonomy
was corpus-falsified to one kind at PR G" and must NOT re-derive "8–12
loop kinds" from the umbrella's stale number — the same inheritance
mechanism as PR F's §2.0 falsified-refactor note. See
[[project-phase4-pr-f-lock-and-pr-g-inheritance]].

---

## 2. The load-bearing part of PR G — the per-kind classification + the grounded scoping fork (scoped FIRST, locked-Decision-3 forward requirement)

> **PR G's brakes.** Locked Decision 3 *requires* the per-loop-type
> stateful-vs-derived classification with reasoning. Applied to the
> ACTUAL taxonomy with Finding G5's grounded data, it produces the
> scope: there is exactly **one** honestly-backed derived cohort and
> **one** stateful-loop candidate (corpus-empty), and **five**
> name-only. Resolved by the locked G-1 decision BEFORE any code.

### 2.1 The classification, per taxonomy item, with reasoning (on the code + the probed data)

| Item | Class | Reasoning (grounded) |
|---|---|---|
| **immunisation-overdue** | **DERIVED → new StandingQuery kind** | Stateless recomputed cohort (`next_dose_due<today AND not series_complete`), no per-row lifecycle/closing trigger (G1). Real thin corpus (1/31, G5). A query template + `register_standing`, materialises into `briefing_items` like `morning_briefing`. NOT an OpenLoop (locked Decision 3; do not invent a lifecycle). data_maturity="thin". |
| **specialist-referral-pending** | **STATEFUL → OpenLoop + detector, IF the user makes the legitimate-A call** | The one genuinely-lifecycled candidate (a referral opens it; the specialist letter / decision closes it; a deadline breaches it). But `referrals`=0 corpus (G5): building it = the detector + OpenLoop wiring + transitions, **proven non-vacuous on fabricated input, labelled construct-validity-only / not-corpus-exercised** — the PR-F F-1=B "substrate proven, first real instance later" honesty, now applied to a loop. Requires the locked legitimate-A **PR-G-merits decision by the user** (§6 G-1). |
| abnormal-vitals, lab-threshold | DERIVED (already templates) | Stateless; templates exist (`patients_with_abnormal_recent_vitals` thin, `patients_with_lab_threshold` schema_only). Could be registered as standing kinds, labelled by maturity — candidate scope, not load-bearing. |
| chronic-script-expiring, diabetic-foot-exam-due, retinal-screening-due, medication-reconciliation-needed | **NAMED-NOT-BUILT (F-3)** | No data path today (G5). Enumerating/building them = the fake-property anti-pattern. Recorded as the taxonomy's deferred members with their trigger (the data-ingestion that does not exist), NOT built. |

**The premise-correction, stated unsoftened:** "ship the 8–12 loop
taxonomy" is, against the live corpus, **one honestly-backed derived
cohort + one corpus-empty stateful candidate + five name-only**. PR G's
honest scope is exactly that; anything more is a fake-property.

### 2.2 The reserved scoping fork this forces (§6 G-1) — surfaced, not chosen

- **G-1 option A** — the two-honest-slices vertical: (1) ship
  **immunisation-overdue** as a real derived StandingQuery kind (thin,
  labelled) — the cheap honest real win on actual data; AND (2) ship
  **specialist-referral-pending** as the first stateful loop — detector
  + OpenLoop wiring + the four audited transitions, proven non-vacuous
  on fabricated input, **labelled construct-validity-only because
  referrals=0** (the F-1=B honesty applied to a loop). The other five
  named-not-built. *Requires the user's deliberate legitimate-A PR-G
  call for the stateful half.*
- **G-1 option B** — derived-only: ship **immunisation-overdue**
  (real, stateless) ONLY; defer ALL stateful-loop+detector work because
  its corpus is empty (referrals=0). The most conservative honest read:
  don't build a state machine + detector for a kind with zero instances
  to detect. The named-not-built set grows by one (specialist-referral
  joins it until referral data exists).
- **G-1 option C** — stateful-only substrate-extension: ship the
  specialist-referral detector + OpenLoop wiring (construct-validity-only)
  ONLY; defer the derived cohort. *Rejected-by-default and named:* it
  skips the one kind with real data for the one with none — inverts the
  honesty.

**Recommendation (the user locks G-1):** option **A** if the user makes
the deliberate legitimate-A call that specialist-referral-pending is
PR G's first stateful loop on PR-G's merits (it is the only genuinely-
lifecycled kind and the substrate exists to prove it, exactly the
vertical-slice "one proven, not many shallow" discipline — built and
honestly labelled construct-validity-only). Otherwise **B** (the more
conservative honesty: a state machine + detector for a zero-instance
kind is arguably the substrate-without-a-consumer shape, and B refuses
it until referral data exists). Both are honest; the choice is a real
trade-off and is **the user's, not the implementer's** — and the
legitimate-A carve-out explicitly forbids me inferring it.

---

## 3. Design — under the G-1 lock (sketched; detailed at implementation, the bar)

**Derived kind (both options):** `immunisations_overdue` query template
(PL/pgSQL, provenance column, `p_workspace_id`-first, trailing `NOTIFY
pgrst` — migration 029) + `register_template` + `registered.py` import +
`register_standing(StandingQuery(kind="immunisation_overdue",
template_id="immunisations_overdue", params={...}))`. Materialises into
`briefing_items` via the existing chokepoint — zero new data path,
inherits provenance + tenant-scoping by construction (the PR-D payoff).
data_maturity="thin".

**Stateful loop (option A only):** a `specialist_referral_pending`
detector — an env-gated default-off async tick (`LOOP_DETECTOR_TICK_ENABLED`,
the `STANDING_QUERY_TICK_ENABLED` idiom, F-4), riding the same
`@app.on_event("startup")` host, that for each entitled workspace
(trusted enumeration, never caller input — the materialiser's pattern):
opens `OpenLoopOpen(loop_kind=SPECIALIST_REFERRAL_PENDING, …)` for a
referral with no existing open loop; advances/breaches/closes via the
PR-F actions on referral-status / deadline; idempotent (a loop already
open for a referral is not re-opened). All mutations through `execute()`
— audited, reversible, the §5.1 FK-cycle-safe cleanup idiom used for any
teardown. **Labelled construct-validity-only** (referrals=0): proven
non-vacuous on fabricated input, first real instance when referral data
exists — the F-1=B honesty, recorded not hidden.

**No migration applied by the assistant as a standing rule** — migration
029 (if any) is surfaced for the user's per-migration call (the
REJECTED-tombstoned gate; 028 was the one-time exception, not precedent).

---

## 4. Tests / verification (the bar; non-vacuity carried)

- Derived kind: double-run row-stable (idempotent), tenant-scoped,
  provenance resolved through the chokepoint; data_maturity="thin"
  asserted against the real 1-overdue corpus (not fabricated).
- Stateful loop (option A): the detector's open/advance/breach/close
  decisions unit-tested on **fabricated** referral input, **proven
  non-vacuous by asserted rejection** of illegal detector decisions (the
  §D.1 mechanism, the PR-F state-machine discipline carried); the
  RUN_INTEGRATION executor round-trip extended to the detector path,
  teardown using the §5.1 cycle-safe idiom; labelled
  construct-validity-only, no fabricated referral presented as corpus.
- Tenant ratchet stays green (any new table/chain born workspace-scoped,
  zero new BASELINE keys — verified by running it).
- The detector tick proven inert at merge (env flag default-off; no task
  created), the `standing_query_scheduler` discipline.

### §4.1 §D.1-class inherited-knowledge note — raise test-scaffolding to the code bar (recorded for PR H to inherit, the FK-cycle-idiom mechanism)

> Same register as §2.0 / PR F's §5.1 / the post-mortem's §D·§D.1: a
> pattern surfaced by two consecutive failures, written into the record
> so the next PR inherits the cure, not the failure.

**Two consecutive first-run scaffolding failures, now a named pattern:**
PR F's first integration run failed in test teardown (the
`action_audit_log` close↔reversal FK-cycle delete order); PR G's first
materialisation run failed on a stale `assert post` left by an
incomplete test edit (`NameError`). **Both times the code under test was
correct and the test harness was buggy.** Both were harmless *only
because a different safeguard caught it* — the residue discipline (PR F:
caught after, residue cleaned; PR G: the PR-F lesson applied
prospectively, zero residue, verified). "Harmless because a different
safeguard caught it" is exactly the reasoning the project refuses
everywhere else.

**The cure (inherited knowledge, the §D.1 lesson pointed at the tests
themselves):** the test is the instrument that certifies the code; an
instrument that itself fails on first run twice in a row makes its own
reliability a standing question, and the project's epistemic structure
rests on a green being real. **Test scaffolding gets written to the SAME
bar as the code it verifies** — reviewed before the run, non-vacuity and
premise-checks applied to the harness (teardown order, edit completeness,
no stale-assertion / NameError class) exactly as to the code. Do NOT
rely on the residue net: the next scaffolding bug may land in the gap
between "test buggy" and "result wrong" where the residue safeguard does
not catch it. A green from an instrument that needed two tries to run
cleanly is weaker than one that ran clean; the cure is the standard, not
the net.

**PR H MUST carry this:** PR H's test scaffolding is written to the code
bar and reviewed before the run; the stale-edit / NameError /
wrong-teardown-order class of first-run failure is NOT treated as
acceptable-because-harmless. Recorded so PR H inherits the cure. The
positive half is also legible: PR F's scar became PR G's prophylaxis
(the residue-safe teardown applied *before* the run → zero live-DB harm
where PR F had residue) — the method compounding, which is the credential
this note also records. See
[[project-phase4-pr-f-lock-and-pr-g-inheritance]],
[[feedback-test-scaffolding-to-code-bar]].

## 5. Decisions locked at review — G-1..G-5 FINAL

Recorded as the user locked them; reasoning is the lock, recorded so it
is overridable deliberately, not re-derived. No umbrella/PR-F decision
re-opened.

**G-1 — FINAL: option B. The user DECLINED the legitimate-A call (a
reasoned decline, not a failure to make it).** PR G ships
**immunisation-overdue** as a real derived `StandingQuery` kind
(stateless, thin-but-real 1/31, labelled "thin"). **specialist-referral-
pending and the five unbacked items are NAMED-NOT-BUILT**, with
specialist-referral-pending's deferral reason recorded: `referrals`=0
corpus — deferred **until referral data exists**. The reasoning: the
survives-deleting-the-demo test, applied an eighth time — the only
driver to build the referral detector+OpenLoop *now* is PR G's wish to
exercise PR F's substrate on a stateful instance; the corpus is empty
(referrals=0); that is legitimate-in-general,
not-for-this-reason-now — the PR-E-opt-1 / PR-F-opt-A anti-pattern. The
F-1=B precedent cuts FOR B here: PR F's OpenLoop substrate is already
proven (on `main`, transition table proven-to-bite); building a
detector against zero referrals is not "proving the substrate", it is a
consumer for data that does not exist. **The legitimate-A door stays
open as a deliberate FUTURE call on referral-lifecycle's own product
merits, made by the user in those terms — NOT inferred from "finish
Phase 4", NOT recommended into existence, and explicitly NOT MADE
HERE.** The carve-out is honored by my declining to infer it.

**G-2 — FINAL: locked, with the under-B clarification (recorded so the
word does not mislead).** The detector-host pattern is the F-4 /
`standing_query_scheduler` idiom (startup host, env-gated, default-off,
not a daemon, not pg_cron, inert at merge). **Under B there is NO
loop-opening detector and NO new tick:** registering a new
`StandingQuery` kind is picked up by the EXISTING (default-off)
`standing_query_scheduler` materialiser — the PR-D "configuration, not a
project" payoff. "Detector" under B therefore means **the existing
derived-cohort materialisation tick handling the new kind**; the
**loop-opening detector is DEFERRED with specialist-referral-pending**.
A future reader must NOT inherit "PR G shipped a loop detector" — PR G
under B shipped a registered derived cohort the existing materialiser
serves; no new tick was added.

**G-3 — FINAL: data-maturity honesty locked.** immunisation-overdue
labelled **"thin"** — load-bearing exactly as PR B's construct-validity
ledger: 1-of-31 is real but it is ONE instance; a future reader must NOT
read "immunisation-overdue shipped" as "corpus-proven at volume". Thin
means thin, stated. specialist-referral-pending + the four unbacked
items: **named-not-built in the taxonomy record with their reasons**
(referrals=0 / no data path), NOT enumerated as if real (F-3
fake-property prohibition).

**G-4 — FINAL: the no-UI boundary, verbatim earns-split (ninth
occurrence of the cure).** The earns section states **verbatim** what
PR G MAY claim — *"the immunisation-overdue derived cohort materialises
into `briefing_items`, verified by read-back"* — and what it MAY NOT —
*"a clinician sees the overdue immunisations"* (FALSE until PR E's
held/untracked briefing UI is merged, which is PR E's own decision). The
no-UI reality is a true boundary of PR G, not a defect, and is stated as
one — never papered over by implying the materialisation is visible.

**G-5 — FINAL: no capability minted; user-facing gate stays the named
F-4 deferral.** The materialisation tick is a trusted backend process
(trusted entitled-workspace enumeration, never caller input — the
materialiser pattern); not user-invoked, so no `HasPermission` is
minted/guessed (the don't-fake-a-capability discipline, as
`clinical_query` was not minted before its query surface existed). A
clinician-facing surface would need a capability; there is none in PR G;
the capability is correctly **deferred, not answered prematurely**.

## What PR G earns when it lands — the verbatim split (G-4 locked)

PR G **MAY claim, verbatim:** *the immunisation-overdue derived cohort
is registered as a `StandingQuery` kind and materialises into
`briefing_items` through the proven `run_template`+`resolve_provenance`
chokepoint, inheriting provenance + tenant-scoping by construction (the
PR-D substrate paying off as "configuration, not a project"), verified
by read-back of the real overdue row(s) on the live corpus.* It is
**thin** (1 overdue of 31 — real, one instance, labelled thin, NOT
corpus-proven at volume).

PR G **MAY NOT claim, and states so unsoftened:** *a clinician sees the
overdue immunisations* — FALSE until PR E's briefing UI is merged
(PR E held, `MorningBriefing.jsx`/`briefing.js` untracked on `main`); PR
G's surface is backend materialisation, not clinician-visible. It does
**not** ship "the 8–12 taxonomy" — it ships **one** real derived kind;
specialist-referral-pending and four others are named-not-built (the
§2.0 taxonomy-falsification note). It builds **no** stateful loop, **no**
loop-opening detector, **no** new tick. The classification was caught at
plan time against grounded live-corpus data, not asserted — the method
at the boundary it was built for, an eighth time; the earns-split, a
ninth.
