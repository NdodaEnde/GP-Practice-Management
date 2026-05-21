# Phase 4 — The Proactive Layer: PR-by-PR Implementation Plan

> **DRAFT FOR REVIEW — discharge-the-carried-constraint-first ordering.**
> This deliberately inverts the roadmap's week order (OpenLoop → taxonomy
> → briefing surface → pre-consult). The inversion is the same class of
> decision as Phase 3's provenance-verifiable-first re-draft: it is a
> *discipline* decision, not a preference. Phase 4 inherits exactly one
> hard close-condition from Phase 3, that condition is the screenshot-
> producing part everyone is motivated to do, and the roadmap order puts
> it at week 13 *behind* the interesting OpenLoop state-machine work —
> which is precisely the "named deferral done last or thin under the
> pressure of more interesting work" failure family this project's whole
> method exists to catch (the §8 overclaim, the §D.1 vacuous test, the
> pre-committed-wording category error). So the carried constraint is
> discharged FIRST, by the thinnest PR that can discharge it, while it is
> still visible. **This ordering is Decision #1 — OPEN, recommended, for
> the user to lock or override at review.**
>
> **Status tracker (update as PRs land):**
> - **PR E** — morning-briefing UI; discharges the inherited Phase-3
>   close-condition (openable-vs-unresolvable pixel-rendered against a
>   real login) — ⬜ (carries the Phase-3 carried constraint as its
>   single load-bearing property; its hardest part is the
>   workspace/login *contrast* reality, scoped FIRST and honest)
> - **PR F** — `OpenLoop` as a first-class ontology object + links +
>   state machine; refactor scattered existing follow-up logic into it
>   (roadmap wk11) — ⬜
> - **PR G** — the SA-primary-care loop taxonomy as standing-query
>   `kind`s materialising into `briefing_items` over the proven
>   chokepoint (roadmap wk12, harvested through PR E's surface) — ⬜
> - **PR H** — the pre-consultation brief (per-patient composition) +
>   Phase 4 close-out post-mortem (roadmap wk14) — ⬜
>
> **APPROVED AT REVIEW.** Four decisions LOCKED, a fifth added and locked
> (closeability-under-outcome-(c), forced by Decision 2's outcome (c)),
> and two required umbrella changes applied: the sixth-occurrence earns-
> split (Phase 4 proves extensibility *for the loop taxonomy*, explicitly
> NOT re-validating PR D's conversion-instrumentation "configuration not
> a project" promise), and the Decision-5 closeability lock wired into
> the inherits-section and Risks. See "Decisions locked at review". No
> code is written until PR E's own plan is brought complete and reviewed
> at the A/B/C/D bar (Phase-0 probe block FIRST; the survives-deleting-
> the-demo test written into outcome (b); the human-reads-the-actual-
> screen verification statement verbatim; the thin=surface-not-
> verification rider explicit).

---

## The one thing Phase 4 inherits and cannot close without

Recorded verbatim from `ONTOLOGY_QUERY_LAYER_POSTMORTEM.md` §B and the
project memory `project_phase3_tracked_deferrals`, so it cannot be
softened anywhere it recurs:

> *Phase 4 cannot close until the openable-vs-unresolvable rendering is
> verified against the real briefing UI — that is the moment the safety
> property becomes visible to the human it protects; "correct but never
> seen by a human" is weaker than the platform's trust thesis promises.*

This is not polish and not a PR-description sentence. It is the spine of
Phase 4's definition-of-done, equal weight to every OpenLoop deliverable,
and it is the reason PR E exists and is sequenced first.

**What "cannot close without" means if the honest corpus cannot show
the contrast (locked Decision 5 — the structural consequence of Decision
2's outcome (c), confronted here rather than at PR H under pressure).**
Decision 2 lists "carry-forward-UNMET with a named blocker" as an
acceptable *PR E* outcome. It is — but it is **not automatically an
acceptable Phase 4 *close*** outcome, because the same corpus limitation
that blocked PR E persists to PR H, and this very section says Phase 4
cannot close without the constraint. Carry-forward-UNMET is therefore an
acceptable **waypoint**, and an acceptable **terminus only** under
locked Decision 5: either (i) PR E's Phase-0 probe additionally scopes
the *minimal honest* corpus/placement work that would make the contrast
human-visible, that work becomes a **named Phase 4 deliverable** (a PR
E.1, or explicitly folded into PR H — never an unscoped "later"), and
Phase 4 does not close until the contrast is human-verified; **or** (ii)
the Phase 4 close-out records — *through the build-failing presence gate*
(locked Decision 4) — that **Phase 4 closed with its defining safety
constraint formally UNMET and re-inherited forward to Phase 5, in
exactly those words**, with the §C-residual's unsoftened honesty, so no
future reader can infer the constraint was met. There is no third path
where Phase 4 simply closes and the constraint quietly evaporates.

---

## Context

Phase 3 closed honestly (`main`@`51d1664`): a tenant-scoped, provenance-
verifiable query layer; the `morning_briefing` standing query *already
materialising* provenance-resolved rows into `briefing_items`; the
dead-link failure rendered visibly unresolvable, never a silent confident
wrong answer. Phase 4 turns the spine *proactive*: the platform stops
only answering questions and starts surfacing what the clinician didn't
know to ask — `OpenLoop` as a first-class object, the SA-primary-care
loop taxonomy, the real morning-briefing screen, the pre-consult brief.

The binding constraint of Phase 4 is *not* the OpenLoop state machine
(that is the interesting, well-motivated work that will get done well by
gravity). It is the carried Phase-3 constraint above: a human eye, on a
real authenticated screen, seeing an openable source open and a dead
source refuse to open *visibly*. Everything in Phase 3's trust thesis
routes through that one human-visible moment, and nothing in the
roadmap's week order forces it early.

**Empirical grounding (probed against `main`@`51d1664` before any
assertion — the load-bearing ones flagged; one is an unresolved fork
deliberately NOT closed here):**

1. **The roadmap's "refactor your EXISTING 'things to follow up' logic"
   premise is TRUE, not imagined.** Scattered, real, mostly-disconnected
   follow-up logic exists: `procedures.follow_up_required` /
   `follow_up_date` with a live `GET /procedures/follow-up/due`
   (`backend/api/procedures.py:46-47,292-311`, tested);
   `immunizations.next_dose_due` / `compliance_status='overdue'` with an
   overdue query (tested); `EncounterType.FOLLOW_UP`
   (`backend/ontology/enums/consultation_enums.py:34`, a classifier
   marker, not a deadline tracker); one-way `POST /referrals`
   (`backend/server.py:254-276,4908-4930` — a source fact, no loop
   lifecycle); and the Phase-3 `morning_briefing` recall cohort already
   materialising. Phase 4 *unifies* these into `OpenLoop`; it does not
   invent follow-up from scratch. **There is NO existing `OpenLoop`
   object** — it is genuinely the fourth ontology object after
   Patient/Document/Consultation.

2. **(Load-bearing) The briefing substrate is proven and extensible —
   new proactive content is configuration, not infrastructure.** The
   `morning_briefing` standing query, `materialise_standing_queries()`,
   the `briefing_items` table (migration 027), and the chokepoint
   (`run_template`+`resolve_provenance`) all exist and are proven. A new
   loop type is a new `StandingQuery` `kind` over the *same* chokepoint
   and *same* table, inheriting verifiable-provenance + tenant-scoping by
   construction. This is the exact payoff PR D's conversion-instrumentation
   note promised the substrate was shaped for: *"a configuration of this
   infrastructure, not a project."* Phase 4 is where that promise is
   first cashed.

3. **(Load-bearing) A real human dev login EXISTS — the §B "no login"
   note was about a *different* workspace, and that distinction is the
   fork.** Frontend: Create-React-App + craco, React 19,
   react-router-dom 7, axios, Radix UI, Tailwind, JavaScript (`.jsx`,
   NOT TypeScript). Dev server `yarn start` → **`:3000`** (confirmed,
   NOT `:3001` — the old Phase-3 plan's `:3001→:8002→:5001` chain wording
   was wrong; per project memory the chain is **`:3000` → `:8002`**,
   there is no `:5001`). A working human login exists at `/login` with
   seeded demo accounts (`admin@surgiscan.com` / `password123` →
   workspace `demo-gp-workspace-001`). **But** §B recorded that the
   workspace whose briefing rows are *openable*
   (`demo-briefing-workspace-001`) "has no login", and that `demo-gp` is
   *NULL-sourced* (→ `no_source`, **not** `unresolvable`). To pixel-
   verify the openable-**vs**-unresolvable *contrast* the human-loginable
   workspace must contain **both** an openable row **and** an
   unresolvable row on one screen. Whether `demo-gp-workspace-001`
   currently does is the **#1 unresolved fork — see Risks and Decision
   #2; it is NAMED here, not faked, and explicitly not closed by
   seeding-a-contrast-pair-to-order** (the construct-validity anti-
   pattern this project rejected in Phase 3 PR A Option 2 and PR B
   rider 3 — re-importing it through Phase 4's back door is the same
   violation).

4. **(Load-bearing — verify the premise, not the wording: §D.1's exact
   lesson) The `GET /api/query/briefing` response shape, read from the
   code directly, NOT from a summary.** `query.py:347-357` returns raw
   `briefing_items` rows via `.select("*")`. Each item therefore carries
   *both*: top-level denormalised columns
   `source_status` / `openable` / `unresolvable_reason` / `citation`
   (the cheap badge signal), **and** the full `row_payload` JSONB whose
   nested `source{status,openable,document_id,signed_url,citation,
   unresolvable_reason,quality}` is where the **`signed_url` actually
   lives**. The denormalised top-level columns do NOT contain the signed
   URL. The UI must read `row_payload.source.signed_url` to render an
   openable link and may read the top-level `source_status`/`openable`
   for the cheap status badge. Any plan that assumes a flat per-item
   `source.signed_url` (a plausible-looking simplification) renders the
   openable case as a dead button — exactly the failure the close-
   condition exists to catch. This shape is pinned from the code, not
   paraphrased.

5. The next free migration number is **028** (highest on `main` is
   `027_briefing_items.sql`). The async worker host pattern is set:
   `@app.on_event("startup")` in `server.py` wires the document watcher
   and the (default-off) standing-query scheduler as asyncio-task
   singletons; any Phase-4 detector tick rides that identical pattern.

## Design choices

**1. (Load-bearing) The carried Phase-3 constraint is discharged FIRST,
by the PR with the smallest *surface area* that can discharge it, before
any OpenLoop work.** PR E renders the *already-materialising*
`morning_briefing` rows; it needs zero OpenLoop, zero new backend data
path, zero new migration. **"Small surface" is not "low-stakes" (locked
Decision 1 rider):** PR E is small in code — one route, one screen, one
service method — and *maximal in fork-honesty*; its contrast-corpus fork
is the single hardest honesty problem in Phase 4. Wherever this plan
says PR E is "thin", it means thin-in-surface, never thin-in-
verification. It exists solely to make the Phase-3 safety property
*visible to a human*. *Rejected:*
the roadmap week order (OpenLoop wk11 → … → briefing surface wk13). It is
not wrong as a learning sequence but it parks the one carried constraint
behind three weeks of more interesting work, which is the precise failure
family (named-deferral-done-thin-last) the project's method catches.
*Also rejected:* folding the briefing UI into the OpenLoop PRs — same
parking, with the additional hazard that the close-condition rides on
data shaped by the loop work rather than on the honest Phase-3 corpus.

**2. (Load-bearing, honesty about the contrast corpus) The close-
condition is verified against whatever openable/unresolvable distribution
the honest existing corpus *naturally* produces — never a contrast pair
seeded to order.** This is PR B rider 3 carried into Phase 4 verbatim in
spirit: if the human-loginable workspace does not naturally contain both
an openable and an unresolvable briefing row, the correct response is to
*resolve the entitlement/login placement so a legitimately data-bearing
workspace is reachable by a human* (the Phase-3 precedent: move the
workspace to the right product, never bend data to the test), or to
record honestly that the contrast remains probe-verified-only and say so
in PR E's verification statement. *Rejected outright:* `INSERT`-ing a
hand-built openable+unresolvable pair into `briefing_items` so the demo
clicks cleanly — that is the construct-validity anti-pattern
(manufacturing data to satisfy the property it is supposed to test), the
exact thing Phase 3 refused twice.

**3. `OpenLoop` is a real first-class ontology object (roadmap-explicit),
but the taxonomy distinguishes *stateful* loops from *derived* cohorts.**
A specialist-referral-pending loop has a genuine lifecycle (opened →
awaiting → closed/breached) and needs an `OpenLoop` row with a state
machine and an audit trail. A patients-not-seen-since cohort is
*stateless* — it is recomputed every materialisation, it has no per-row
lifecycle, and forcing it into a state machine would be modelling
ceremony with no audit value. PR F builds `OpenLoop` for the stateful
loops; PR G registers the derived cohorts as plain `StandingQuery`
`kind`s. *Rejected:* "every taxonomy item is an `OpenLoop` row" — inflates
the object, manufactures lifecycle where there is none, and couples the
proven stateless substrate to a state machine it does not need.

**4. (Retained from Phase 3) Every new proactive read rides the single
`run_template`+`resolve_provenance` chokepoint and the existing
`briefing_items` table; no new data path; reuse `clinical_query`, never
mint a capability.** The coherent-choice-pays-twice invariant: a new
read surface that reaches clinical data reuses `clinical_query`, so PR
A's `module_digitisation`-does-NOT-entail-`clinical_query` Type-C ratchet
propagates the written customer promise to every Phase-4 surface for
free. *Rejected:* a bespoke loops query path or a new `loops` read
capability — re-opens the tenant-guard and entitlement surface Phase 3
closed structurally.

**5. (Retained) `OpenLoop` mutations are first-class audited Actions
through the existing `ActionExecutor`; loop materialisation is read-only-
derived and does NOT route through it (no audit row), exactly as the
standing-query materialiser does not.** Opening/closing/breaching a
stateful loop is a mutation with a reversal and an audit trail
(Phase-2 machinery, already built). Recomputing a derived cohort is not
a mutation. *Rejected:* auditing materialisation (audit-log spam with no
forensic value — the same call PR D made for the standing-query writer).

**6. (Honesty about non-corpus-exercisable loop types) Where a loop type
has no live data on the dev corpus, ship the structural detector +
standing `kind` and label it `schema_only` / `thin` via the existing
`data_maturity` mechanism — never a fabricated fixture presented as a
populated loop.** Phase 3 design choice #7, carried. Several SA-primary-
care loop types (retinal-screening-due, diabetic-foot-exam-due) will
have zero corpus rows until lab/screening ingestion exists; they ship
honest-and-empty, labelled, not faked.

---

## PR breakdown

Four PRs (E–H), continuing the A–D lettering, close-out folded into PR H
(the Phase-3 precedent: the carried-constraint *verification record* and
the next-phase inherited constraints belong in the phase close-out, not
a separate ratification PR). Every boundary preserves the invariant: **no
PR ships a proactive surface a clinician could act on whose provenance
is not the same verifiable contract Phase 3 proved, and Phase 4 does not
close until that contract is human-visible.**

### PR E — Morning-briefing UI (discharges the inherited Phase-3 close-condition)

**Single load-bearing property:** a human, logged into the real frontend
through the real `:3000` → `:8002` chain against a real entitled
workspace, sees the materialised `morning_briefing` rows rendered such
that an **openable** source actually opens the real scan (clicked, in a
browser) and an **unresolvable** source is shown as a visible, explicit
known-unknown that *cannot* be silently mistaken for a live link — the
Phase-3 safety property made visible to the human it protects.

**This PR is deliberately thin in *surface area*, and explicitly NOT
thin in verification (locked Decision 1 rider).** It adds no migration,
no OpenLoop, no new backend data path — a frontend route + a service
method + one screen. But its load-bearing part is the honest resolution
of the contrast-corpus fork, which is the single hardest honesty problem
in Phase 4. "Thin" here means small-in-code-maximal-in-fork-honesty; it
must never be read as low-stakes. The screen this PR renders is the
first time in the entire project the Phase-3 safety property becomes
visible to the human it exists to protect — that is the whole point and
it does not get done thin.

**Deliverables (paths; sized at implementation, Phase-3 discipline —
PR E is small but its hard part is the fork, not the LoC):**
- `frontend/src/services/briefing.js` (or a method on the existing
  `api.js`) — `getBriefing(kind?, as_of_date?)` / `refreshBriefing()`
  hitting `GET|POST /api/query/briefing[/refresh]`; token attached by
  the existing axios interceptor.
- `frontend/src/pages/MorningBriefing.jsx` + a `/briefing` route in
  `App.js` behind `ProtectedRoute`, nav-gated on the same capability the
  backend gates (`clinical_query`) — capability-gated nav already exists
  in `Layout.jsx`.
- The rendering contract, pinned to grounding finding #4: read
  `row_payload.source.signed_url` for the openable link target; read
  top-level `source_status` for the badge; the **unresolvable** state is
  rendered first-class (explicit citation incl. the truncated-id wording
  Phase 3 locked, `openable=false`, never a clickable element), and the
  envelope's `unresolvable_count` is surfaced at cohort altitude (the
  Phase-3 reason the per-row marker alone is insufficient).
- **Phase-0 probe block (REQUIRED in PR E's own plan, mirroring PR A's
  live-DB probe — this is the fork, scoped FIRST):** before any UI code,
  probe the live DB for *which workspace a human can log into AND which
  workspace's `briefing_items` carry an openable row AND an unresolvable
  row*. The probe answer determines PR E's shape and is reported as
  fact, not assumed. Three honest outcomes, all acceptable, none faked:
  (a) one entitled human-loginable workspace naturally carries both →
  the contrast is pixel-verifiable as-is; (b) the openable data and the
  login are in different workspaces → resolve by *workspace/entitlement
  placement* (Phase-3 precedent: move the workspace to the right
  product), never by injecting data; (c) the honest corpus cannot show
  the contrast on one screen → PR E's verification statement records the
  contrast as probe-verified-only and Phase 4's close-condition is
  explicitly carried forward UNMET into PR H with the named blocker,
  rather than declared met on manufactured data.

**Verification statement (REQUIRED WORDING — quote verbatim in the PR
description; the named human verifier reads the actual screen, not a
screenshot description — the §2.4 discipline):** *The inherited Phase-3
close-condition is discharged iff a human verifier has, in a browser
through the real `:3000`→`:8002` chain on a real entitled login, clicked
an openable briefing source and watched the real scan open, and seen an
unresolvable briefing source rendered as an explicit visible known-
unknown that is not clickable as a live link. If the honest corpus
cannot present both on one screen, this statement records that the
contrast is probe-verified-only and the close-condition is carried
forward UNMET — it is never declared met against seeded-to-order data.*

**Defers:** OpenLoop (PR F); the loop taxonomy (PR G); pre-consult
(PR H). PR E renders exactly what Phase 3 already materialises.

### PR F — `OpenLoop` as a first-class ontology object (roadmap wk11)

**Load-bearing property:** `OpenLoop` exists as the fourth ontology
object, following the `objects/patient.py` declarative template
(property metadata, PII tags, links registry, the inherited
`id`/`practice_id`/timestamps/`deleted_at`), with a typed state machine
(opening event → expected closing event → deadline → urgency → state);
the scattered existing follow-up logic (procedures, immunizations) is
refactored so `OpenLoop` is the audited source of loop *state*, the
source tables remain the source *facts*, and every loop mutation is a
first-class audited `Action` with a reversal (Phase-2 machinery).

**Deliverables (paths; sized at implementation):**
- `backend/ontology/objects/open_loop.py` — the object, mirroring the
  `patient.py` template exactly (the project's consistency discipline).
- Link registry entries (`backend/ontology/links/registry.py`):
  `Patient --has_open_loop--> OpenLoop`, `Consultation --opened_loop-->
  OpenLoop`, `Document --evidences_loop_closure--> OpenLoop`, with
  cardinality + metadata.
- `backend/migrations/028_open_loops.sql` — the `open_loops` table;
  RLS-deny-all per the migration-018 idiom *verbatim* (the Phase-3
  pattern: ENABLE RLS, no permissive policy, NOT FORCE, NOT auth.*-keyed);
  added to the PR-5 static tenant-guard `TENANT_TABLES` (the ratchet only
  goes down; a born-scoped table adds zero new BASELINE keys); explicit
  `NOTIFY pgrst` *decision* (Phase-3 discipline: the decision is stated,
  not cargo-culted in either direction).
- `backend/ontology/actions/open_close_loop.py` (or similarly named) —
  the open/close/breach mutations as audited Actions through the existing
  `ActionExecutor`, with reversal.
- Refactor of the existing follow-up logic so it produces/consumes
  `OpenLoop` state rather than ad-hoc table columns — the source tables
  stay; the loop *lifecycle* moves to `OpenLoop`.

**Defers:** the full taxonomy + detectors (PR G); the briefing surface
(already shipped in PR E).

### PR G — The SA-primary-care loop taxonomy (roadmap wk12, harvested through PR E)

**Load-bearing property:** the loop taxonomy (specialist-referral-
pending, abnormal-result-unacknowledged, chronic-script-expiring,
immunisation-overdue, diabetic-foot-exam-due, retinal-screening-due,
medication-reconciliation-needed, …) is registered as standing-query
`kind`s materialising into `briefing_items` over the *same* proven
chokepoint, inheriting verifiable-provenance + tenant-scoping by
construction; stateful loop types write/advance `OpenLoop` rows (PR F),
derived cohorts are stateless `StandingQuery` kinds (design choice #3);
non-corpus-exercisable types ship honest-and-empty, `data_maturity`-
labelled (design choice #6); each new `kind` surfaces through the PR E
screen with zero new UI.

**Deliverables (paths; sized at implementation):** per-loop-type query
templates + standing `kind` registrations; opening/closing detectors
riding the existing async worker host pattern where a detector is needed;
honest `data_maturity` labels for the empty ones; tests proving each new
`kind` materialises through the chokepoint and inherits the
openable/unresolvable contract (the Phase-3 regression guard, extended).

**Defers:** pre-consult (PR H).

### PR H — The pre-consultation brief + Phase 4 close-out post-mortem (roadmap wk14)

**Load-bearing property:** the per-patient pre-consult brief is a
*composition* of primitives already built (audit-log diff against last
visit, that patient's open loops from PR F/G, medications/allergies,
reason-for-visit) — not new infrastructure; AND the Phase 4 close-out
post-mortem records, in the project's now-standard close-out shape: the
**discharge record of the carried Phase-3 close-condition** (met against
the honest corpus, or carried-forward-UNMET with the named blocker —
whichever PR E's verification statement honestly produced); Phase 4's own
residuals and construct-validity limits; and the next-phase inherited
constraints, in the umbrella's exact words where it matters, so a future-
self or regulator quoting the close-out cannot infer a stronger property
than was built (the §C/§E discipline).

**Deliverables:** the pre-consult composition + `ONTOLOGY_PROACTIVE_
LAYER_POSTMORTEM.md` (or the agreed close-out filename), built to the
PR D close-out bar, with a build-failing presence gate that is proven
non-vacuous before any composition code (the §2.4 necessary-not-
sufficient + §D.1 lesson, carried).

**Defers:** Phase 5 (compound returns) — named only.

---

## Risks

- **#1, the sharpest: the contrast-corpus / login fork (grounding #3).**
  The close-condition needs an openable row AND an unresolvable row on
  one screen, in a workspace a human can log into. §B says the openable
  workspace has no login and the loginable one is NULL-sourced. If this
  is unresolved silently, PR E either fakes the contrast (the rejected
  anti-pattern) or quietly declares the close-condition met when it
  isn't (the §8-overclaim family). Mitigation: it is NAMED here as
  Decision #2, scoped as PR E's FIRST work (the Phase-0 probe block),
  with three honest outcomes pre-authorised — including "carry forward
  UNMET with the named blocker", which is an acceptable outcome and a
  faked green is not.
- **#1's under-weighted second-order risk: outcome (c) is a Phase-4
  *closeability* problem, not only a PR E problem.** If the honest corpus
  cannot present the contrast, the same limitation persists to PR H, yet
  this plan's own opening section says Phase 4 cannot close without the
  constraint. Treating carry-forward-UNMET as merely an acceptable PR E
  outcome, without confronting what it does to Phase-4 closeability, is
  exactly the gap that gets decided under pressure at PR H. Mitigation:
  **locked Decision 5** confronts it now — carry-forward-UNMET is an
  acceptable waypoint, a terminus only via the named-corpus-work path or
  the build-failing close-out record of a formally-unmet defining
  constraint. Not left to PR H.
- **Outcome (b) is the launderable one.** "Resolve by workspace/
  entitlement placement" reads like the legitimate migration-025
  precedent but becomes the seeded-to-order anti-pattern in the
  precedent's clothes if the *only* reason for the placement/login
  change is "so PR E's contrast demo works". Mitigation: **locked
  Decision 2's survives-deleting-the-demo test** — outcome (b) is
  permitted only if the placement change is justified by a reason that
  survives deleting the close-condition from the argument; otherwise it
  is outcome (c), not (b).
- **Roadmap-order inversion is a real call, not a free one.** Building
  the briefing UI (PR E) before `OpenLoop` (PR F) means PR E renders
  only the Phase-3 `morning_briefing` kind — a smaller-surface first
  screen than the roadmap's wk13 "the screen the doctor checks every
  morning". This is accepted deliberately: a small-surface screen that
  *discharges* the carried safety constraint beats a rich screen that
  *parks* it — and "small surface" carries the locked Decision 1 rider
  (small in code, maximal in fork-honesty, never low-stakes). Decision 1.
- **`OpenLoop` state-machine scope balloon.** A loop state machine
  invites modelling every clinical-workflow nuance. Mitigated by design
  choice #3 (stateful vs derived split — only genuinely-lifecycled loops
  get the machine) and by the Phase-3 "ship the thin proven thing,
  label the rest" discipline.
- **Frontend is JavaScript/CRA, not TS** — no codegen'd types from the
  ontology; the briefing row shape is hand-mirrored in JS. Risk: shape
  drift between the Python `briefing_items`/`row_payload.source` contract
  and the JS renderer. Mitigation: PR E pins the shape from the code
  (grounding #4) and the close-condition itself is the human check that
  the rendered openable link actually opens.
- **Backend-port discrepancy** — `backend/.env` says `:8001`,
  `frontend/.env`'s `REACT_APP_BACKEND_URL` says `:8002`, App.js
  autologin hardcodes `:8002`, project memory says `:8002`. The UI uses
  the frontend's configured `:8002`; the discrepancy is verified at
  dev-server-start in PR E, not asserted away in this plan.

## Decisions locked at review

All four reserved decisions are LOCKED, a fifth is added and locked
(forced by Decision 2's outcome (c)), and two umbrella changes are
applied above (the sixth-occurrence earns-split; the Decision-5 wiring).
Coding implements exactly these; a deviation requires a new explicit
user call, not an implementer's judgement. The reasoning and the riders
are recorded so the calls can be overridden deliberately rather than
re-derived — and so the riders do not have to be rediscovered when the
pressure to violate them is live and this reasoning is weeks cold.

**1. PR ordering — inversion LOCKED (discharge-the-carried-constraint-
first; PR E before the OpenLoop work).** Same reasoning that has been
correct five times: the carried Phase-3 close-condition is the one thing
Phase 4 inherits and cannot close without; the roadmap parks it at wk13
behind the interesting OpenLoop state-machine work; that is the precise
named-deferral-done-thin-last failure family that produced the §8
overclaim, the §D.1 vacuous test, and the pre-committed-wording category
error. **Rider (locked, not an override) — "thin" applies to PR E's
*surface area*, never its load-bearing verification.** The word "thin"
has been dangerous every time it appeared in this project (PR C's NL
layer, PR B's adversarial set) and will be read later as "low-stakes".
It is not. PR E is **small in code and maximal in fork-honesty**: one
route, one screen, one service method (thin surface), and the contrast-
corpus fork is its hard part — the single hardest honesty problem in
Phase 4, explicitly NOT thin. This rider is written explicitly into PR
E's own plan and the surface/verification distinction is carried inline
wherever "thin" appears so it cannot be misread as low-stakes.

**2. Contrast-corpus / login policy — LOCKED: honest corpus only;
resolve by workspace/entitlement *placement*, never seeded-to-order
data; carry-forward-UNMET-with-named-blocker is an acceptable honest
outcome and a faked green is not.** This is PR A Option 2's rejection
and PR B rider 3 carried verbatim in spirit; re-importing the construct-
validity anti-pattern through Phase 4's back door is the same violation
Phase 3 refused twice. **Rider (locked) — the survives-deleting-the-demo
test is the gate on outcome (b).** Outcome (b) ("resolve by placement")
is legitimate *only if* the placement/login change is justified by a
reason that **survives deleting the close-condition from the argument**
(the exact migration-025 test: legitimate iff correct on the merits
independent of the demo — e.g. a briefing-demo workspace being human-
loginable is coherent on its own terms). If the *only* reason
`demo-briefing-workspace-001` (or any workspace) gets a login is "so PR
E can pixel-verify the contrast", that is **outcome (c), not outcome
(b)** — the seeded-to-order anti-pattern wearing the entitlement-
placement precedent's clothes (the same shape migration-025 Option C
wore "completeness"). This test is written into PR E's plan as the
explicit gate on which outcome (b) is permitted.

**3. `OpenLoop` modelling — stateful-vs-derived split LOCKED (design
choice #3).** Same discipline as "three deep objects not fourteen
shallow" and PR D's "one registered kind not the whole taxonomy": a
genuinely-lifecycled loop earns an `OpenLoop` row + state machine +
audit trail; a recomputed cohort stays a stateless `StandingQuery` kind;
"every taxonomy item is an OpenLoop row" is rejected for object
inflation. **Forward requirement (locked into PR F's plan, not a change
to this lock) — the inverse hazard.** The split's correctness depends
entirely on each loop type being classified stateful-or-derived
*honestly per-type against what that loop actually is*, not chosen to
minimise work. The PR F hazard is the inverse of object-inflation:
classifying a genuinely-stateful loop as derived because the state
machine is more work. PR F's plan MUST show the stateful/derived
classification **per loop type with the reasoning** (the same way the
entitlement decisions showed their coherence reasoning), so a future
reader sees why each loop is on the side of the split it is on.

**4. Phase 4 close-out build-failing presence gate proven non-vacuous —
LOCKED (same gate, same bar as PR D's §2.4).** The carried-constraint
discharge record is the highest-stakes sentence in the Phase 4 close-out
and the project's method is that the highest-stakes sentence gets the
build-failing-proven-non-vacuous gate, not prose nobody re-reads.
**Rider (locked) — the §D.1 lesson carried explicitly.** The gate is the
*automatable necessary* condition (presence parsed; build fails on
absence); the *human sufficient* condition is the named verifier reading
the **actual rendered screen through the real chain** — not a screenshot
description — and confirming the discharge record's wording matches what
the human actually saw. PR D proved a signed sentence can be honestly
worded and not backed; the close-out must state, in its own voice, that
the parser passing is necessary-not-sufficient and the human screen-read
is the sufficiency, exactly as the Phase 3 post-mortem now does.

**5. Closeability-under-outcome-(c) — LOCKED (added at review; forced by
Decision 2's outcome (c) being real — confronted now, not at PR H under
pressure).** Carry-forward-UNMET is an acceptable **waypoint** for PR E;
it is an acceptable **terminus** for Phase 4 only under one of two
paths, decided now: **(i)** PR E's Phase-0 probe additionally scopes the
*minimal honest* corpus/placement work that *would* make the contrast
human-visible, that work becomes a **named Phase 4 deliverable** (a PR
E.1, or explicitly folded into PR H — never an unscoped "later"), and
Phase 4 does not close until the contrast is human-verified; **or (ii)**
the Phase 4 close-out records — *through the build-failing gate (locked
Decision 4)* — that **Phase 4 closed with its defining safety constraint
formally UNMET and re-inherited forward to Phase 5, in exactly those
words**, with the §C-residual's unsoftened honesty, so no future reader
can infer the constraint was met. There is no third path where Phase 4
closes and the constraint quietly evaporates. The close-out filename is
the agreed `ONTOLOGY_PROACTIVE_LAYER_POSTMORTEM.md` (or a rename the
user calls); it is not a load-bearing decision and is settled here.

## What Phase 4 earns when it lands

When PR H merges, SurgiScan stops only answering questions and starts
surfacing what the clinician didn't know to ask — open loops tracked as
audited first-class objects, the SA-primary-care loop taxonomy
materialising through the *same* verifiable-provenance chokepoint Phase 3
proved, the morning briefing a real screen a doctor checks, the pre-
consult brief a composition of primitives rather than new infrastructure.
The word that matters is still *trustworthy*: the carried Phase-3
constraint is discharged honestly — the openable-vs-unresolvable safety
property is *seen by the human it protects*, on a real login, against the
honest corpus, or it is recorded carried-forward-UNMET with a named
blocker and never declared met on manufactured data.

**The earns-claim split (sixth named occurrence of the earns-overclaim
cure — applied here, in the umbrella, before it propagates into four PR
plans).** What Phase 4 genuinely earns: the PR D substrate (the
`run_template`+`resolve_provenance` chokepoint, `briefing_items`,
`materialise_standing_queries`, the verifiable-provenance contract) is
**proven extensible *for the loop taxonomy*** — PR G adding loop types as
standing `kind`s over the same chokepoint *is* that demonstration, and it
is real. What Phase 4 does **NOT** earn, and what this section must not
fuse into the sentence above: Phase 4 does **not** re-validate PR D's
conversion-instrumentation *"configuration, not a project"* promise. That
promise was about a *different* consumer with a different shape
(conversion instrumentation needs real customer interaction events, which
the loop taxonomy does not generate); proving the substrate configurable
*for loop types* says nothing about whether it will be configurable for
conversion instrumentation when customers arrive. That remains correctly
deferred and **unproven and unprovable until customers generate
interaction events**, exactly as PR D's note states — Phase 4 neither
validates nor weakens it, and a future reader must not infer from "the
substrate proved extensible for loops" that the conversion promise is
discharged. It is not; it is untouched.

The things Phase 4 cannot do — close loop types with no corpus data,
codegen JS types from the ontology, model lifecycle where there is none,
re-validate the conversion-instrumentation promise — are labelled
construct-validity limits and named deferrals in the close-out, not
silent gaps.
