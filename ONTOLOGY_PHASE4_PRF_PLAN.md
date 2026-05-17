# Phase 4 — PR F Implementation Plan: `OpenLoop` as the Fourth Ontology Object (+ state machine, audited actions, migration 028)

> **Status:** plan APPROVED at review at the A/B/C/D bar. **F-1, F-2,
> F-3, F-4 FINAL (locked, §6).** Grounded in fresh read-only probes of
> the live codebase **2026-05-17, `main`@`51d1664`** (own probes + two
> recon sweeps, every load-bearing claim file:line-verified, not taken
> from the umbrella's subagent summary — the §D.1 lesson). Implements
> umbrella **locked Decision 3** (stateful-vs-derived split) and its
> forward requirement (per-loop-type classification *with reasoning*);
> no umbrella decision re-opened. **F-1 = option B** (substrate + state
> machine + audited actions ONLY; first real stateful loop deferred to
> PR G) **with the non-vacuity rider**: the construct-validity tests
> must be **proven non-vacuous by asserted rejection of illegal
> transitions — the §D.1 mechanism** (a state machine "proven" only by
> feeding it valid transitions is the §D.1 false-green in a new place;
> the honest claim option B may make is "shown to reject what it must
> reject", not merely "works on well-formed fabricated input"). F-2/F-3/
> F-4 locked with riders (§6). The §2.1 falsification is recorded as the
> §2.0 §D.1-class premise-test note so a future maintainer inherits the
> finding and does NOT re-derive "refactor" from the umbrella's stale
> word. No code until §3.1/§4/§5 carry the non-vacuity rider in their
> explicit test scope (done below).
>
> **Premise the probe corrected (norm #1 — verify before asserting; same
> register as PR D Finding W and PR E Finding L4):** the umbrella's PR F
> scope says *"refactor scattered existing follow-up logic into it so
> OpenLoop is the audited source of loop state."* **The live code
> falsifies the premise that genuinely-stateful follow-up logic exists
> to refactor.** Probed against the actual code, *every* existing
> follow-up mechanism is either a **stateless recomputed cohort** (no
> stored per-row state, no closing trigger) or a **write-once record
> with an inert status field**. By locked Decision 3 the stateless ones
> **stay standing queries — they are NOT refactor targets**; nothing
> currently keeps loop *state* anywhere to move into `OpenLoop`. PR F is
> therefore **not a refactor of existing state** — it is the
> introduction of the `OpenLoop` substrate + state machine, proven on a
> **deliberately-built first stateful loop**, and *which* loop (or
> none-in-PR-F) is a **reserved scoping decision (§6 F-1)**, surfaced
> here, not chosen under pressure. This is PR F's load-bearing finding
> and it is scoped FIRST (§2), brakes-before-wheel, exactly as PR D
> scoped its close-out and PR E its contrast-fork before any code.
>
> **The locked-Decision-3 inverse hazard, restated because this is
> exactly where it bites:** Decision 3 warned against classifying a
> genuinely-stateful loop as *derived* to dodge state-machine work. The
> live finding shows the *symmetric* hazard is the live one: the
> temptation to classify the stateless cohorts as *stateful* "because
> they're called follow-up", and to **invent** an `acknowledged_on` /
> `closed_by` lifecycle the current code does not have. Both directions
> are misclassification; §2 classifies each on *what the code actually
> does*, file:line, not on the word "follow-up".

---

## 1. Empirical findings (live codebase, read-only, 2026-05-17 `main`@`51d1664`)

### Finding F1 — every existing follow-up mechanism is DERIVED or write-once-inert (the load-bearing fact)

Code-level characterisation, file:line, strictly on what the code *does*:

| Mechanism | File:line | What the code does | Lifecycle? |
|---|---|---|---|
| Procedures follow-up | `backend/api/procedures.py:46-47,291-311` | `follow_up_required`/`follow_up_date` set at create; `GET /procedures/follow-up/due` recomputes `follow_up_date <= today` at query time; `PUT` allows arbitrary field mutation; **no endpoint/trigger ever closes a follow-up** | **STATELESS** — recomputed cohort, no stored per-row state, no closing trigger |
| Immunizations overdue | `backend/api/immunizations.py:42-43,295-316` | `next_dose_due`/`series_complete`; `GET /immunizations/overdue` recomputes `series_complete=false AND next_dose_due < today`; "overdue" is **never stored**; `series_complete` marks series end, not per-dose compliance | **STATELESS** — "overdue" is a query-time comparison, no stored compliance state, no closing trigger |
| Referrals | `backend/server.py:251-283,4908-4963`; `database/phase_4_2_schema.sql:52-71` | `POST /referrals` inserts with hard-coded `status='pending'`; schema *defines* `pending/sent/completed/cancelled`; **no API endpoint mutates status**; no `PUT`; no deadline | **WRITE-ONCE / INERT** — status field present but never transitioned in code; a lifecycle only *exists if PR F builds it* |
| `EncounterType.FOLLOW_UP` | `backend/ontology/enums/consultation_enums.py:34` | A classifier label on an immutable encounter; may *trigger* future detection, holds no state itself | **CLASSIFIER** — not a state machine |
| `morning_briefing` / `patients_not_seen_since` | `backend/ontology/query/standing.py:123-128,188-235` | Recomputed cohort materialised per `as_of_date`; a patient leaves implicitly via a new encounter; no per-row state, no audit, no closing trigger | **STATELESS** — the canonical DERIVED example (Decision 3's reference) |
| `OpenLoop` | — | Grep across `backend/`: only in design docstrings (`executor.py`, `patient.py`, `consultation_enums.py`, `consultation.py`); **no object, table, or endpoint** | **CONFIRMED ABSENT** |

**Consequence:** applying locked Decision 3 honestly, *nothing existing
is a stateful loop*. The stateless cohorts stay standing queries (not
refactored). Referrals are the only thing with a *latent* lifecycle, and
only because a schema column names states the code never transitions —
making them stateful is **building new state-machine logic, not
refactoring existing state**.

### Finding F2 — the ontology-object template `OpenLoop` must conform to (verified)

`backend/ontology/base.py`: `OntologyObject` base (model_config
`extra="forbid", validate_assignment=True, str_strip_whitespace=True`,
inherited — do not override); `Prop(default, *, pii, fhir, search,
display_label, description, link_to, link_cardinality,
immutable_after_create, deprecated, **field_kwargs)`; ClassVars
`__object_type_name__`, `__display_template__`, `__fhir_resource__`,
`__pii_level__` (`PIILevel.NONE|LOW|MEDIUM|HIGH|SPECIAL`), `__audited__`;
inherited system fields `id`, `practice_id` (link_to="Practice"),
`created_at`, `updated_at`, `deleted_at` (all `Prop(...)`,
`immutable_after_create` where appropriate). Validators:
`@field_validator` + `@model_validator(mode="after")` (Pydantic v2).
Template object: `backend/ontology/objects/patient.py`. Export wiring:
add to `backend/ontology/__init__.py` import + `__all__` (objects/
`__init__.py` is empty by design).

### Finding F3 — the links registry pattern (verified)

`backend/ontology/links/registry.py`: `@dataclass(frozen=True) LinkType{
name, source_type, target_type, cardinality: Cardinality
(ONE_TO_ONE|ONE_TO_MANY|MANY_TO_MANY), inverse_name, description,
link_properties: tuple=(), explicit_table: Optional[str]=None}`; links
declared by appending `LinkType(...)` to the `LINKS` tuple; an object's
`Prop(link_to="X", link_cardinality="one|many")` is mirrored by a
matching `LinkType`; helpers `get_links_from/to`, `find_link`.

### Finding F4 — the audited-action + reversal template (verified)

`backend/app/actions/base.py`: `Action` ABC — ClassVars
`__action_name__`, `__action_version__`, `__reversible__`,
`__pii_level__`; abstract `preconditions()→List[Precondition]`,
`effects()→List[Effect]`, `describe_for_user()`,
`to_audit_parameters()`, classmethod `from_audit_parameters()`.
`Precondition.check(ctx)→CheckResult`; `Effect.plan(ctx)→EffectDescriptor`
+ `apply(ctx)→EffectResult`; `ExecutorContext.append_affected_object(
object_type,object_id,op∈{created,updated,soft_deleted,linked})`.
Entrypoint `backend/app/actions/executor.py: execute(action, *, actor,
supabase, practice_id, workspace_id, dry_run, idempotency_key)`. Audit
row `migrations/014_action_audit_log.sql` (parameters,
preconditions_checked, effects_applied, affected_objects, outcome∈
{success,precondition_failed,effect_failed,reversed,dry_run},
reverses_audit_id, reversed_by_audit_id). Reversal: RPC-backed
(`_REVERSE_RPC_FOR_ACTION`) OR Python-side
(`register_python_reversal(name, builder)` at module import — the
`SoftDeletePatient` template, `ontology/actions/soft_delete_patient.py`,
is the closest analog: single-table state change, Python-side reversal).
Primitives `backend/app/actions/primitives.py`: `ObjectExists`,
`HasStatus`, `NotSoftDeleted`, `BelongsToPractice`, `HasPermission`;
`SetField`, `SetMultipleFields`, `SoftDelete`, `RestoreSoftDeleted`.
Register action modules in `backend/app/actions/registered.py`
(one import line each, `@register_action @dataclass(eq=False)`).

### Finding F5 — migration / RLS / ratchet / worker facts (verified)

- **Next free migration = 028** (highest on `main` is `027_briefing_
  items.sql`; PR E added none).
- **migration-018 RLS-deny-all idiom (028 reproduces verbatim):**
  `ALTER TABLE … ENABLE ROW LEVEL SECURITY`, **no permissive policy**,
  **NOT FORCE** (`018:36` rationale — FORCE would also constrain the
  service_role backend), **NOT auth.*-keyed** (`018:43-46` — app is not
  Supabase-Auth; an auth.* policy is dead code). Deny-all to
  anon/authenticated; service_role bypasses. Exactly what `027`
  reproduced.
- **PR-5 tenant guard ratchet** (`tests/test_tenant_query_isolation.py`):
  `TENANT_TABLES: Set[str]` (`:65`) + frozen `BASELINE` of
  `"relpath::lineno::table"` (`:212`); `test_no_new_unscoped_tenant_
  queries` (`:344`) fails on `current-BASELINE` AND `BASELINE-current`
  (ratchet only goes down). A **born-workspace-scoped** `open_loops`
  (every chain carries `.eq("workspace_id",…)`) added to `TENANT_TABLES`
  adds **zero new BASELINE keys** — the exact posture `briefing_items`
  took.
- **NOTIFY pgrst:** `028` adds a TABLE and no function — the **`027`
  decided-inclusion reasoning applies verbatim** (REST-builder-addressed
  table; stale schema-cache 404s; NOTIFY is the cheap correct hygiene),
  stated explicitly in the `028` header as a *decided* inclusion, not
  cargo-culted in either direction.
- **Worker host** (`server.py:5361` `@app.on_event("startup")`,
  singleton `create_task` pattern): relevant only to loop *detectors*.
  Per the umbrella PR breakdown detectors are **PR G**; PR F adds the
  object/state-machine/actions and **no worker** (a scoping note, §6).

---

## 2.0 §D.1-class premise-test note — "refactor existing follow-up logic" is FALSIFIED; PR F is an introduction, not a refactor (recorded so it is NOT re-derived)

> Same register as the post-mortem's §D/§D.1 and PR E's §2.0: not
> failure narration — a premise that read sound in the umbrella and was
> tested at PR-F plan time against the live code and found false. A
> future maintainer (PR G, or anyone re-reading the umbrella) must
> inherit the *finding*, not re-derive "refactor" from the umbrella's
> stale word.

The umbrella's PR F scope line — *"refactor scattered existing
follow-up logic into it so OpenLoop is the audited source of loop
state"* — was reviewed and approved at umbrella time. At PR-F plan time
its premise was probed against the actual code (§1 Finding F1,
file:line) and **falsified**: there is **no genuinely-stateful
follow-up logic anywhere to refactor.** Every candidate is a stateless
recomputed cohort (procedures-follow-up, immunisations-overdue,
patients-not-seen-since — all `< today` query-time comparisons, no
stored per-row state, no closing trigger) or a write-once record with
an **inert** status field never transitioned by any code (referrals).
By locked Decision 3 the stateless ones **stay standing queries — they
are not refactor targets**; nothing currently keeps loop *state*
anywhere to move into `OpenLoop`.

**Therefore PR F is the *introduction* of `OpenLoop` (substrate + state
machine + audited mutation actions), not a refactor of pre-existing
state.** The umbrella word "refactor" is stale; PR F (and PR G, and any
future reader) must treat the existing follow-up mechanisms as
classified in §2.1 — DERIVED → standing queries, referral →
write-once-inert (a real loop only if *built*, which is PR-G taxonomy
work, F-4-locked) — and must NOT invent an `acknowledged_on`/`closed_by`
lifecycle on the stateless cohorts to make PR F look like a refactor
(the symmetric misclassification, the live hazard). This note is the
named anchor; the finding is inherited, not re-derived. See
[[project-phase4-pr-e-option2-gate]] (the sibling Phase-4
premise-correction) and [[feedback-verify-premise-boring-first]].

---

## 2. The load-bearing part of PR F — the per-loop-type classification + the premise it forces (scoped FIRST, locked-Decision-3 forward requirement)

> **This section is PR F's brakes.** Locked Decision 3 *requires* the
> per-loop-type stateful/derived classification with reasoning in this
> plan. Done honestly against Finding F1 it produces a premise-correction
> that reshapes PR F's scope — resolved by the locked F-1 decision
> (option B, §2.2 + §6) BEFORE the object/migration/action code.

### 2.1 The classification, per type, with reasoning (on what the code does — not the word "follow-up")

| Loop type | Classification | Reasoning (code-grounded) |
|---|---|---|
| Patients-not-seen-since (recall) | **DERIVED** | Recomputed cohort; leaves implicitly via a new encounter; no per-row state/audit/closing trigger (`standing.py:188-235`). Stays a standing query. Adding `acknowledged_on` would *invent* a lifecycle — the inverse misclassification. |
| Procedures-follow-up-due | **DERIVED** | `follow_up_date < today` recomputed at query time; nothing closes it (`procedures.py:291-311`). Stateless. Stays a (future PR-G) standing query; not an `OpenLoop`. |
| Immunisation-overdue | **DERIVED** | `next_dose_due < today` recomputed; "overdue" never stored (`immunizations.py:295-316`). Stateless. Standing query, not `OpenLoop`. |
| Specialist-referral-pending | **STATEFUL — but NOT existing; would be NEWLY BUILT** | Referrals are write-once with an inert `status` (`server.py:4908-4945`); the schema *names* `pending/sent/completed/cancelled` but no code transitions it. A real loop here = PR F **building** open→awaiting→closed/breached + deadline + audited transitions. Genuinely stateful (an opening event, an expected closing event — the specialist letter — a deadline, a breach) — *if built*. Not a refactor. |
| Abnormal-result-unacknowledged, chronic-script-expiring, diabetic-foot-exam-due, retinal-screening-due, medication-reconciliation-needed, … | **DEFERRED to PR G classification** | No corpus data and/or no code today; classifying them now would be classifying imagined code (the §D.1 anti-pattern). PR G classifies each against its then-real implementation. |

**The premise-correction, stated unsoftened:** there is **no existing
stateful follow-up logic to refactor into `OpenLoop`.** The umbrella's
"refactor scattered existing follow-up logic" is, against the live code,
*false* — the scattered logic is stateless cohorts (stay standing
queries) and a write-once referral record (no transitions). `OpenLoop`'s
value is the substrate for loops PR G will populate; its first *stateful*
instance must be **deliberately built**, not inherited.

### 2.2 F-1 FINAL — option B, LOCKED (substrate + state machine + audited actions only; first real stateful loop deferred to PR G), with the non-vacuity rider

> **LOCKED at review.** The fork below was a genuine scoping decision;
> the user locked **option B**, with the non-vacuity rider, for the same
> reason it has been the answer six times (PR C disabled-but-built, PR D
> one-kind-the-rest-named, PR E option 2, …): every prettier outcome is
> reachable only by pulling another PR's work forward for *this* PR's
> satisfaction, and the project refuses that. This is not a coincidence
> of recommendation — it is the same anti-pattern in a new place and the
> same cure.

**Why option A is rejected (the survives-deleting-the-demo test, applied
to PR F's would-be vertical slice).** Option A builds the
specialist-referral-pending lifecycle "to prove the substrate end-to-end
on a real stateful loop." Does the referral lifecycle have an
independent reason to be built **in PR F** that survives deleting "PR F
wants a populated/exercised state machine" from the argument? **It does
not.** By §2.1 and umbrella locked Decision 3 the referral lifecycle is
PR-G taxonomy work — a loop *kind* with a detector, and detectors are
**F-4-locked as PR G**. The only thing wanting it built in PR F is PR F's
desire to look proven on real data instead of fabricated input — exactly
the PR-E Option-1 anti-pattern: legitimate-in-general (the referral loop
is real PR-G work), not-for-this-reason-now (built in PR F because PR F
wants it populated). The seventh instance, refused.

**Why option B is the materially stronger outcome, not a fallback.**
The substrate built, structurally proven on fabricated construct-validity
input, **labelled exactly "not corpus-exercised; first real loop is PR
G"**, with the real instance arriving in the PR that legitimately owns
it, is brakes-before-wheel applied to the object: PR C
disabled-but-built, PR D one-kind-the-rest-named, PR E honest-empty — a
seventh time, and the consistency is the point. An honestly-labelled
"built, structurally proven, not yet exercised" substrate is *more*
trustworthy than one that looks proven because PR F reached into PR G to
populate it.

**The non-vacuity rider (LOCKED, the §D.1 cure applied to the state
machine — load-bearing, written into §3.1/§4/§5 test scope explicitly).**
Option B proves the state machine on fabricated input; a fabricated-input
test passes vacuously if it only ever feeds *valid* transitions. So the
construct-validity tests must be **proven non-vacuous by asserted
rejection of illegal transitions** — every illegal (state, event) pair
fed in and asserted *rejected*, not merely every legal one fed in and
asserted accepted. The honest claim option B is permitted to make is
**"the state machine was shown to reject what it must reject"**, never
merely "works on well-formed fabricated input". A state machine
"proven" only by valid fabricated transitions is the §D.1 false-green in
a new location, and is explicitly disallowed.

**The legitimate-A carve-out (recorded so the door is not falsely
shut).** If, on **PR G's own merits**, the user later deliberately
decides specialist-referral-pending is PR G's first loop and pulls that
*PR-G-scope* decision forward **stated as such** — not as PR F's fix for
wanting a populated machine — that is legitimate and routes as a
deliberate PR-G pull-forward with its own justification (the same
carve-out left open for PR E Option 1 / the demo workspace). **At this
review the user did NOT make that PR-G-first-loop decision**, so F-1
stands at B; the carve-out is a future *deliberate* PR-G decision, never
an inference from PR F's desire to be exercised.

The original fork, retained for the audit trail:

- **F-1 option A — substrate + ONE honest stateful loop
  (specialist-referral-pending), built.** PR F ships the `OpenLoop`
  object + links + state machine + audited Open/Advance/Close/Breach
  actions, AND builds the referral lifecycle as the *vertical slice*
  proving the substrate end-to-end on a genuinely-stateful loop
  (PR D's "one kind proven, not many shallow"). Heavier; produces a
  real, exercised state machine. Risk: referral-lifecycle scope creep
  into PR G's taxonomy.
- **F-1 option B — substrate + state machine ONLY, zero loop
  instance.** PR F ships `OpenLoop` + the state machine + audited
  actions, proven by construct-validity tests on fabricated input (the
  Phase-3 design-choice-#7 idiom: structural defence built + unit-tested,
  labelled not-corpus-exercised), with the **first real stateful loop
  explicitly deferred to PR G**. Lighter; the substrate is honest-but-
  unexercised-on-real-data and *labelled exactly that* (no fake
  populated loop). Mirrors PR C shipping the NL classifier
  disabled-but-built.
- **F-1 option C — defer `OpenLoop` entirely; fold it into PR G.**
  Rejected-by-default and named: it collapses the umbrella's E→F→G→H
  boundary and re-creates the "object declared with the taxonomy in one
  big PR" shape the roadmap's completeness-trap warning forbids. Named
  so the rejection is deliberate, not silent.

**Recommendation (the user locks):** option B. Reasoning: option A's
referral lifecycle is genuinely PR-G-taxonomy work; pulling it into PR F
*because PR F wants a populated state machine* is the PR-E Option-1
anti-pattern (legitimate-in-general, not-for-this-reason-now). Option B
ships the substrate honestly, labelled construct-validity-only, with the
first real loop deferred to PR G where it belongs — the
brakes-before-wheel, vertical-slice, ship-the-proven-substrate-and-label
-the-rest discipline applied consistently. But this is a scope call with
real trade-offs and it is **the user's to lock**, not mine.

---

## 3. The `OpenLoop` object + links + state machine (conforming to F2/F3; built under the F-1 lock)

**Object** `backend/ontology/objects/open_loop.py` — mirrors
`patient.py` exactly (F2): `class OpenLoop(OntologyObject)` with
`__object_type_name__="OpenLoop"`, `__display_template__`,
`__fhir_resource__=None` (no clean FHIR analog — stated, not faked),
`__pii_level__` (LOW — a loop references a patient but holds little PII
itself; pinned at implementation against the actual fields),
`__audited__=True`. Inherited system fields untouched. Domain props via
`Prop(...)` with full metadata: `patient_id`
(link_to="Patient", link_cardinality="one"),
`opening_event_*` (what opened it — type + reference),
`expected_closing_event_*` (what would close it),
`loop_kind` (the taxonomy discriminator — a closed enum,
`backend/ontology/enums/`, mirroring the consultation/document enum
pattern), `state` (the state-machine enum, §3.1), `deadline_at`,
`urgency`, `opened_at`, `closed_at`, `closed_reason`,
`breached_at`. Validators (`@model_validator(mode="after")`) enforce the
state-machine invariants declaratively (e.g. `closed_at` set iff
`state` terminal; `breached_at` set iff `state==BREACHED`).

**Links** (F3 — append `LinkType` to `LINKS`):
`Patient --has_open_loop--> OpenLoop` (ONE_TO_MANY),
`Consultation --opened_loop--> OpenLoop` (ONE_TO_MANY, the opening
event), `Document --evidences_loop_closure--> OpenLoop` (MANY_TO_MANY,
the closing evidence) — plus the matching `Prop(link_to=…)` on the
object.

### 3.1 The state machine (explicit, closed, declarative)

A **closed, exhaustively-tested** transition table (F-2 LOCKED — not
implicit string moves, no fall-through): `OPEN → AWAITING → (CLOSED |
BREACHED)`; `BREACHED → CLOSED` (a breached loop can still be resolved
late — an explicit tested fact, not the absence of code); `CLOSED` is
terminal (`CLOSED → anything` is an explicit *asserted-rejected* fact,
not merely "no code for it"). Every transition is an audited action
(§4); no transition by a bare field write — the `model_validator`
rejects an inconsistent (`state`, `*_at`) tuple so an un-audited
mutation cannot produce a valid object.

**F-2 + non-vacuity rider, LOCKED into the test scope (the §D.1
mechanism, exact wording — not "construct-validity tests" but
"construct-validity tests proven non-vacuous by asserted rejection of
illegal transitions"):** the transition table is the single source of
truth and its test is **exhaustive over the full state × event space**.
For every (state, event) pair: either it is a defined transition (fed
through the action+executor path and asserted to *execute and produce
the expected* (state, `*_at`)) **or** it is an illegal pair (fed in and
asserted to be **rejected** — by the transition table AND independently
by the `model_validator`). The test must **bite**: feeding an illegal
transition and asserting rejection is the load-bearing half; a test that
only feeds legal transitions and asserts acceptance is the §D.1
false-green relocated and is explicitly disallowed. Any future addition
of a state or an event that does not update the table **fails CI**
(the table is enumerated and the test cross-checks completeness, so an
unhandled pair is a build failure, never a silent fall-through).

---

## 4. Audited actions + migration 028 (conforming to F4/F5; under the F-1 lock)

**Actions** (`backend/ontology/actions/open_loop_*.py`, F4 template,
`@register_action @dataclass(eq=False)`, registered in
`app/actions/registered.py`): `OpenLoopOpen`, `OpenLoopAdvance`
(OPEN→AWAITING), `OpenLoopClose`, `OpenLoopBreach`. Each:
`preconditions()` from primitives (`ObjectExists`, `BelongsToPractice`,
`HasStatus` on `state`, `HasPermission`), `effects()` via
`SetMultipleFields` (state + the paired `*_at`), `to_audit_parameters()`
/ `from_audit_parameters()`, `__reversible__=True` with **Python-side
reversal** (`register_python_reversal`) — the `SoftDeletePatient`
analog (single-table state change; the executor's Python reversal path,
not an RPC, is the right weight; no multi-table atomicity needed). Loop
mutations route **only** through `execute()` — the
`model_validator` + the no-bare-write discipline make the audit trail
structural, not optional.

**Migration `028_open_loops.sql`** (F5): `CREATE TABLE open_loops` —
`id uuid pk`, `workspace_id text NOT NULL` (born-scoped; TEXT, no
::uuid — the heterogeneous-id postmortem scar), `patient_id`,
`loop_kind`, `state`, `opening_*`, `expected_closing_*`, `deadline_at`,
`urgency`, `opened_at`, `closed_at`, `closed_reason`, `breached_at`,
`created_at/updated_at/deleted_at`; indexes on `(workspace_id, state)`
and `(workspace_id, patient_id)`; **RLS-deny-all, migration-018 idiom
verbatim** (ENABLE RLS, no policy, NOT FORCE, NOT auth.*); **added to
`test_tenant_query_isolation.py` `TENANT_TABLES`** (born-scoped → zero
new BASELINE keys); **explicit NOTIFY-pgrst decided-inclusion** header
per the `027` reasoning (table, no function). Header carries the
single-table scope + the 018-idiom rationale so a future maintainer
inherits it.

---

## 5. Tests / verification

- **State-machine non-vacuity — LOCKED test scope (F-1 rider, the §D.1
  mechanism, exact wording):** these are not merely "construct-validity
  tests" — they are **construct-validity tests proven non-vacuous by
  asserted rejection of illegal transitions**. The test is **exhaustive
  over the full state × event space**: every legal pair fed through the
  action+executor path and asserted to execute + produce the expected
  (state, `*_at`); every **illegal** pair fed in and asserted
  **rejected** — by the transition table AND independently by the
  `model_validator`. The illegal-rejection half is load-bearing; a suite
  that only feeds legal fabricated transitions is the §D.1 false-green
  relocated and **fails review**. CI completeness check: an unhandled
  (state, event) pair (e.g. a future-added state/event not in the table)
  is a **build failure**, never a silent fall-through. `CLOSED → *` and
  the `BREACHED → CLOSED` allowance are explicit asserted facts in the
  table test, not the absence of code.
- **Audited-action round-trip**: open → advance → close through
  `execute()`; assert one `action_audit_log` row per transition with
  correct `affected_objects`/`outcome`; reverse the close; assert
  `reversed_by_audit_id`/`reverses_audit_id` wiring and state restored
  (the `test_action_reversal` idiom).
- **Tenant ratchet**: `test_no_new_unscoped_tenant_queries` stays green
  with `open_loops` added to `TENANT_TABLES` (zero new BASELINE keys).
- **RLS**: `open_loops` `relrowsecurity=true`, 0 permissive policies
  (the 027 RUN_INTEGRATION idiom).
- **Under F-1 option B**: the substrate is exercised on **fabricated**
  loop input only, and every such test is **named and labelled
  construct-validity-only** (design-choice-#7 idiom) — no fabricated
  loop is presented as corpus evidence; the "first real stateful loop is
  PR G" deferral is recorded, not hidden.

### §5.1 §D.1-class inherited-knowledge note — the `action_audit_log` close↔reversal FK cycle (recorded so it is NOT re-derived the hard way in a live DB)

> Same register as §2.0 / the post-mortem's §D·§D.1: a piece of
> schema knowledge surfaced by an actual failure, written into the
> record so the next person inherits it instead of rediscovering it.

The RUN_INTEGRATION round-trip
(`tests/test_open_loop_executor_roundtrip.py`) on its **first** run
**failed in the test's teardown, not in the round-trip.** The round-trip
itself was correct and independently corroborated by the live
`action_audit_log` (the `OpenLoopClose success` ↔ `ReverseOpenLoopClose
reversed` pair, wired both ways, persisted as fact regardless of the
test's pass/fail). The teardown's naive parent-before-child
`DELETE FROM action_audit_log` hit
`ForeignKeyViolation: action_audit_log_reverses_audit_id_fkey` and left
**2 orphaned audit rows in the live demo workspace** — treated as a real
harm (audit-log pollution in a clinical system's source-of-truth table
is exactly the failure that table exists to prevent), reported before
interpretation, cleaned FK-correct scoped to the two known ids, verified
zero residue by read-back, the teardown then permanently fixed and the
run re-done clean.

**The inherited knowledge (the load-bearing part):** a reversal and its
target in `action_audit_log` form a **deliberate bidirectional FK
cycle** — the reversal row's `reverses_audit_id` → the original, and the
original's `reversed_by_audit_id` → the reversal. **This cycle is
correct production design** (it is what makes a reversal and its target
mutually discoverable; do not "fix" it). The consequence for **any**
future teardown, cleanup, maintenance, or migration that deletes across
a reversal pair: a naive ordered delete **cannot** break the cycle and
**will** `ForeignKeyViolation`. **The cycle-safe idiom (established
here, reuse it):** first `UPDATE action_audit_log SET
reverses_audit_id=NULL, reversed_by_audit_id=NULL WHERE id = <each
collected id>` for *every* row in the set, **then** `DELETE` them —
order- and cycle-independent. Any code touching audit reversal rows
without this will hit the exact wall this run hit; this note is so it is
inherited, not re-derived in a live DB. (PR G builds detectors that
write/clean audit rows — this is directly its inheritance; see
[[project-phase4-pr-f-lock-and-pr-g-inheritance]].)

---

## 6. Decisions locked at review — F-1, F-2, F-3, F-4 FINAL

Recorded as the user locked them; the reasoning is the lock and is
recorded so it can be overridden deliberately, not re-derived. No
umbrella decision re-opened.

**F-1 — FINAL: option B + the non-vacuity rider (§2.0, §2.2, §3.1, §5).**
Substrate + state machine + audited actions only; first real stateful
loop deferred to PR G. Option A REJECTED (the survives-deleting-the-demo
test: the referral lifecycle has no independent reason to be built *in
PR F* — it is PR-G taxonomy work pulled forward for PR F's
populated-machine satisfaction, the PR-E Option-1 anti-pattern, seventh
instance, refused). Option C REJECTED (collapses the E→F→G→H boundary,
the completeness-trap). **Non-vacuity rider LOCKED**: the
construct-validity tests are *"proven non-vacuous by asserted rejection
of illegal transitions, the §D.1 mechanism"* — written verbatim into the
§3.1/§5 test scope; a suite that only feeds legal fabricated transitions
fails review. **Legitimate-A carve-out**: only a future *deliberate
PR-G-scope* decision (specialist-referral-pending chosen as PR G's first
loop on PR G's merits, stated as such) — never an inference from PR F's
desire to be exercised; the user did NOT make that decision at this
review, so F-1 stands at B.

**F-2 — FINAL: `OPEN → AWAITING → (CLOSED | BREACHED)`, `BREACHED →
CLOSED`, `CLOSED` terminal — closed, exhaustively-tested transition
table.** Rider LOCKED: every (state, event) pair is a defined transition
**or** an asserted-rejected illegal one; **no implicit fall-through**;
the table is enumerated and the test cross-checks completeness so a
future-added state/event not in the table **fails CI**; `BREACHED →
CLOSED` and `CLOSED → *`-rejected are explicit tested facts, not the
absence of code. Every transition an audited action; no bare field
write valid (`model_validator` enforced).

**F-3 — FINAL: PR F defines the `loop_kind` enum *type* but seeds only
honestly-backed kinds; the rest are named-not-built (PR-D Decision-2
discipline applied to the enum).** An enum value with no detector and no
honest instance is a fake-property (asserts a capability the code lacks)
— forbidden. Under option B the enum carries the structural minimum for
substrate coherence; `specialist_referral_pending` is the **named**
first member, **not instantiated** until PR G builds its detector;
extensibility is **structural** (PR G adds kinds without migration
churn). The plan states which kinds are *defined* vs *deferred-and-named*
so a future reader sees the boundary, not a half-populated enum of
uncertain status.

**F-4 — FINAL: detectors are PR G, not PR F (mechanism-vs-policy cut).**
PR F ships the *mechanism* — the object, state machine, and audited
Open/Advance/Close/Breach actions by which a loop is mutated. PR G ships
the *policy* — what *decides* to open a loop from a clinical event (the
detectors), riding the §F5 `@app.on_event` worker host alongside the
taxonomy. A detector in PR F would be the referral-lifecycle
anti-pattern again (PR-G work pulled forward for PR F's satisfaction).

---

## What PR F earns when it lands

`OpenLoop` exists as the fourth ontology object — same declarative
template as Patient/Document/Consultation — with a closed, explicitly-
tested state machine and audited, reversible transitions through the
existing executor; `open_loops` is RLS-deny-all and born tenant-scoped
(zero ratchet cost). What PR F **does not** claim, stated unsoftened
(the §D.1/§E discipline): it does **not** "refactor existing follow-up
logic" — the live code has none that is stateful; the stateless cohorts
remain standing queries by locked Decision 3, and PR F says so rather
than inventing a lifecycle to look like a refactor. Under **locked F-1
option B** the substrate is **built and proven non-vacuous by asserted
rejection of illegal transitions (the §D.1 mechanism), but not
corpus-exercised** — labelled exactly that, with the first real stateful
loop deferred to PR G where the taxonomy and its detectors live. The
honest claim PR F makes is "the state machine was shown to reject what
it must reject", never "exercised on a real loop". The
premise-correction (no existing stateful logic) was caught at plan time
by verifying the umbrella's wording against the code, not discovered
mid-implementation — the method working at the boundary it was built
for, a seventh time.
