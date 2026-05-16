# Phase 3 — PR C Implementation Plan: Thinnest NL Mapping (ships DISABLED)

> **Status:** plan APPROVED at review (same bar as PR A / PR B / the
> executor plans). Grounded in fresh live-codebase probes run
> 2026-05-16. PR A + PR B MERGED to main. **All four decisions CLOSED
> (§5, LOCKED). Two required changes applied: (1) §7 earns split into
> the proven output-domain constraint vs the unverified-at-merge
> mapping-correctness — unsoftened, the §4 ledger not re-fused; (2) §7
> deferred gains the shared rate-limit-bucket coupling as a named
> flag-enablement-review consequence.** Cleared for implementation —
> gate first, classifier around it.
>
> Supersedes nothing in `ONTOLOGY_PHASE3_QUERY_LAYER_PLAN.md` (umbrella
> source of truth); this is the detailed PR C plan its "PR C" section
> deferred.
>
> **Premise corrections this probe surfaced (verify before asserting):**
> - Provider/library unnamed in the umbrella. Live codebase has exactly
>   one completion-capable client pattern (OpenAI, lazy, inside function
>   bodies). PR C reuses the *construction pattern*; provider
>   *enablement* stays a deferred governance decision (§5 #1). The plan
>   picks the gate *shape*, not the provider.
> - The umbrella implies a generic enable flag. `config.py`'s actual
>   convention is `os.getenv(NAME,"false").lower()=="true"` on a
>   `Settings(BaseSettings)` field (`DEBUG`, `ENABLE_METRICS`); default-
>   off is the merge default by construction (§1 probe 2).
> - "No client constructed with flag unset" was stated as a goal, not a
>   mechanism. Corrected: §2 specifies the construction-ordering + three
>   complementary executable traps that make it a real CI gate.
> - `backend/.env`, not `../.env` (carried PR B correction, re-confirmed).

---

## 1. Empirical findings (live codebase) — file:line per probe

**Probe 1 — existing LLM client (REUSE, do not invent).** Three
OpenAI-using sites, all constructing the client **lazily inside a
function body, never at module top-level**:
- `backend/app/services/semantic_search.py:48-59` — canonical pattern:
  module-global `_openai_client=None`; `_client()` does `from openai
  import OpenAI` + `api_key=os.getenv("OPENAI_API_KEY")` + `if not
  api_key: raise RuntimeError(...)` + construct. **PR C copies this
  shape**, adding the flag check *before* the import line.
- `backend/api/icd10.py:108-118` — `from openai import OpenAI` in the
  handler; `client.chat.completions.create(model="gpt-4o", ...,
  temperature=0.3, max_tokens=200)` — the completion-call shape PR C's
  classifier uses (plus `tools=`/`tool_choice=`).
- `backend/server.py:4272,4290,…` — `import openai` inside handlers;
  confirms the no-import-time-construction convention is universal.
Env key: `OPENAI_API_KEY`, `config.py:42`. `import openai` is
network-free at import (socket-trap verified). No `anthropic` outside
`.venv`.

**Probe 2 — flag/settings convention.** `config.py:13-92`. Booleans:
`NAME: bool = os.getenv("NAME","false").lower()=="true"` (`DEBUG`
`:24`, `ENABLE_METRICS` `:71`). Global `settings=Settings()` `:92`.
Recommended: `NL_QUERY_LLM_ENABLED: bool =
os.getenv("NL_QUERY_LLM_ENABLED","false").lower()=="true"`. The env var
is absent from `backend/.env` and the whole tree — default-off is
**structural**, no commit flips it; enabling requires a deliberate env
edit.

**Probe 3 — registry → tool schema (the constrained-enum proof).**
`callable(p.validator) is True` for **all 12 params across all 7
templates**. `ParamSpec.validator` (`spec.py:49`) is a `Callable` and
**cannot** be serialised to a JSON tool schema — exactly the umbrella's
design-choice-#4 premise, confirmed. The classifier exposes only
`{id, description, params:[{name,type,required,default}]}` — the *exact
projection `GET /api/query/templates` already builds* (`query.py:134-153`).
Validators stay runner-side (`spec.py:51-66`, `runner.py:71-88`); the
classifier structurally cannot re-implement validation. Subtlety:
`validate_order_by`'s `("name","last_consultation")` enum lives in the
validator body — NOT on the serialisable surface; the schema cannot
express it; an out-of-enum value is caught by the runner
(`invalid_param`→422). The plan does not reflect validator internals
into the schema (that is the drift the umbrella forbids) — §6.

**Probe 4 — auth/gate/endpoint shape (mirror `/run`).**
`require_capability("clinical_query")` gates `/run` (`query.py:159`) &
`/templates` (`:127`) via `auth.py:255-287` reading hydrated
`current_user["capabilities"]`. `workspace_id` from
`current_user.get("workspace_id")` ONLY (`query.py:167`); request model
has no `workspace_id` (load-bearing). Rate limiter
`_enforce_rate_limit` (`query.py:83-96`, 30/60s). Error map
`_CODE_TO_STATUS` (`:102-111`). Lazy `_sb()` (`:57-69`). `/ask` is a
near-mechanical mirror; the classifier output feeds `run_template`
exactly as `/run` feeds the body — **no new data path**.

**Probe 5 — mockability of the default-off gate (most important).**
The structural arrangement that makes the safety property a real gate
(not hope) is in §2; the three complementary executable traps
(client-sentinel, socket.connect trap, `__import__` trap) are specified
there.

**Probe 6 — umbrella premises adapted.** Provider/flag unnamed →
fixed empirically (gate shape, not provider). "No client with flag
unset" goal → mechanism (§2). Validators-not-serialisable → confirmed,
leaned on. `/run` reusable verbatim → confirmed. Phrasing-set size
unspecified → surfaced as §5 #4, not silently picked.

---

## 2. The load-bearing safety property, scoped FIRST

**Property:** with `NL_QUERY_LLM_ENABLED` unset (merge default), there is
NO path that constructs an LLM client or attempts any outbound network
call, and `POST /api/query/ask` hard-refuses (feature-gated) without
sending the question text — *which itself may be PII (a patient name)* —
anywhere. Enforced structurally (lazy+gated construction; refusal
precedes construction) and proven by a NAMED executable CI invariant.

**Why this is THE thing the merge stands on (unsoftened):** the NL
question *is itself PII-bearing*. There is no scrubber and the plan does
not pretend one (a reliable name-stripper is itself unsolved; claiming
it is the Phase-2 fake-property anti-pattern). **The disabled-default IS
the safety boundary** — flag off ⇒ text never leaves the process ⇒
nothing to scrub. The merge is safe not because PII is cleaned but
because no PII-bearing text reaches any LLM until an explicit operator
governance act (§5 #1).

**Structural arrangement (implementable):**
1. `nl_query.py` module-global `_llm_client=None`; the provider import
   lives *inside* `_client()` (house pattern, probe 1) — never module
   scope.
2. `classify_question(question, …)` line 1 is the flag gate; flag off ⇒
   return `NLRefusal(reason="nl_disabled", answerable=<registry list>)`
   **before** `_client()`, before any import, before any network.
3. `_client()` re-checks flag + key, raises typed error if either
   missing (mirrors `semantic_search._client():56-58`) — defence in
   depth.
4. `/ask` maps a `nl_disabled` refusal to a stable status + the
   answerable list; never 500, never silent.

**NAMED CI invariant (the gate), in `backend/tests/test_nl_query.py`:**
- `test_nl_disabled_constructs_no_client_and_makes_no_network_call` —
  flag off; install (a) `_client` sentinel that raises if called, (b)
  `socket.socket.connect` trap raising on any connect, (c) `__import__`
  trap raising if the provider module imports; call
  `classify_question("show me Jane Doe's medications")` (deliberately
  PII-bearing); assert the `nl_disabled` refusal with answerable list is
  returned AND **all three traps never fired**. Same shape as PR A's
  silent-dead-link guard / PR B's `additional_sources` inertness gate.
- `test_ask_endpoint_hard_refuses_when_disabled` — through the real
  router + real `require_capability` (only `get_current_user`
  overridden, PR A's `test_query_api.py` harness), flag off: `/ask`
  returns the feature-gated refusal + answerable list; `run_template`
  never called (recorder); no `_sb()`/network.
Both quoted verbatim in the PR description's verification statement, at
equal weight to PR A's "46/46".

---

## 3. Deliverables, file-by-file

### 3.1 `backend/app/services/nl_query.py` (new)
Structural style of `semantic_search.py`. Module docstring states (in
the umbrella's register): thinnest constrained classifier over the
CLOSED enum; NL2SQL rejected; ships DISABLED; the question can itself be
PII so disabled-default is the boundary not a scrubber; classifier never
validates (runner does); no new data path.
- `NLRefusal{reason,message,answerable:List[dict]}`,
  `NLClassification{template_id,params,confidence_note}`. `answerable`
  built from `all_templates()` so refusal *always* states what IS
  answerable — "hard refusal + answerable list, never a guess" is
  structural.
- `build_tool_schema()` — pure, no LLM/network. One constrained tool per
  template from `all_templates()`: `{name:t.id, description, parameters:
  {properties:{p.name:{type:_json_type(p.py_type),description:…}},
  required:[…]}}`. **Surfaces only the serialisable projection — never
  `validator`.** Plus a synthetic `refuse` tool so the model can decline
  in-band. The tool set IS the registry, regenerated each call —
  structurally cannot drift.
- `_client()` — lazy singleton, flag+key guarded, provider import
  inside; provider call isolated to `_invoke(client,messages,tools)` so
  the §5-deferred provider swap touches one function.
- `classify_question(question,*,model=None)` — (1) flag gate → immediate
  `NLRefusal(nl_disabled)`; (2) build schema; (3) `_client()` + one
  constrained tool-call (`tool_choice` forcing selection from the closed
  set, low temp, small max-tokens); (4) `refuse`/unknown-tool/no-tool/
  low-confidence → `NLRefusal(out_of_set|low_confidence, answerable)`,
  **never a guess**; (5) valid selection → `NLClassification` with
  params passed **uninterpreted** (runner validates). Output domain =
  `{registered id}×{params}` ∪ refusal. Never SQL, never free-form.

### 3.2 `backend/app/api/query.py` — add `POST /api/query/ask`
Additive only; PR A/B code untouched. `QueryAskRequest` has **only**
`question: str (1..512)` — NO `workspace_id` (load-bearing, same comment
as `QueryRunRequest`). Handler: (1) `require_capability("clinical_query")`
(§5 #3); (2) `_enforce_rate_limit` (reuse existing bucket — an NL call
costs LLM+query; 30/min appropriately conservative; noted, unchanged);
(3) `workspace_id` from auth, 400 if absent (verbatim `/run`); (4)
`cls=classify_question(body.question)`; `NLRefusal` → structured
`{status:"refused",reason,message,answerable}` with stable code
(`nl_disabled` recommended 403 `{"error":"nl_disabled"}` for
consistency with `require_capability`'s 403 — §5 may adjust); (5)
`NLClassification` → `run_template(_sb(),cls.template_id,cls.params,
workspace_id=…)` then `resolve_provenance(_sb(),result,workspace_id=…)`
— **the identical chokepoint `/run` uses**, same `try/except QueryError
→ _CODE_TO_STATUS`. Response = `resolved.to_dict()` + an
`interpreted_as:{template_id,params}` echo (honest: the answer carries
how it was reached). No other path to data.

### 3.3 `backend/tests/test_nl_query.py` (new) — DB-free, network-free
- The default-off named gate (§2): the two named tests.
- `test_tool_schema_is_exactly_the_registry` — tool names ==
  `{t.id}`∪`{refuse}`; params == serialisable projection; **no
  validator in the serialised schema**. Drift fails CI (PR B
  registry-iterating-invariant discipline).
- Mocked-LLM **wiring (NOT intelligence — labelled)**: fake client,
  fixture-driven tool-call; golden set (§5 #4) → assert the
  fixture-chosen selection is passed *unmodified* to a recorded
  `run_template`, and the real `resolve_provenance` over the
  `test_query_api.py` `FakeSupabase` produces the envelope. Docstring
  states verbatim: proves wiring, NOT that the LLM picks correctly.
- Refusal matrix: `refuse` / unknown tool / no tool / low confidence →
  refusal with answerable list; `run_template` never called (recorder).
- `test_ask_only_reaches_data_through_run_template` — recorders prove
  `/ask` reaches data via exactly `run_template`+`resolve_provenance`;
  forged-body workspace inert (mirrors
  `test_forged_body_workspace_is_inert`).
- Capability + tenant mirror: `/ask` without `clinical_query` → 403.

### 3.4 `backend/scripts/nl_query_eval.py` (new) — opt-in, NEVER CI
`load_dotenv("backend/.env")`. Refuses unless
`NL_QUERY_LLM_ENABLED` true AND explicit
`--i-have-authorised-a-provider` flag (two-step operator opt-in; cannot
be CI-wired; cannot send PII without deliberate authorisation). Runs the
golden + held-out paraphrase + adversarial sets through the *real*
`classify_question`; prints an accuracy table. Header + final line state
verbatim: accuracy is reported never gated; never run in CI; refuses
with the flag off. Not imported by any test/registered.

### 3.5 Honest size discussion
Umbrella's ~810 is the right *order*; no single LoC total asserted
(PR B's deliberate refusal of false precision). Drivers: `nl_query.py`
genuinely thin (gate + schema-over-`all_templates()` + one tool-call +
refusal map); bulk is docstring discipline + the provider-isolation
seam. `/ask` ~one handler + model (mechanical mirror). `test_nl_query.py`
is the **largest** file and the honest driver — the named default-off
gate (3 traps) + registry anti-drift gate + no-new-path proof + refusal
matrix + the (user-bounded, §5 #4) golden set. Size is set by the
locked phrasing-set scope, measured at implementation, not projected.

---

## 4. Construct-validity / honesty ledger

| Claim | Verified by | Label |
|---|---|---|
| Flag off ⇒ no client, no outbound call, `/ask` hard-refuses w/o sending text | the two named gate tests (DB/network-free, real fn/router) | **structural invariant — proven, load-bearing** |
| Tool schema cannot drift from registry | `test_tool_schema_is_exactly_the_registry` | **structurally enforced, proven** |
| Classifier constrained to closed enum (no SQL/free-form) | refusal matrix + schema gate | **proven by construction** |
| NL adds no new data path | `test_ask_only_reaches_data_through_run_template` + forged-body-inert | **proven** |
| Mocked tests prove *wiring* (tool-call→chokepoint→envelope) | mocked client | **WIRING ONLY — explicitly NOT accuracy** |
| Classifier picks the right template for real phrasings | `nl_query_eval.py`, opt-in, never CI | **only verifiable with LLM enabled — prose, NEVER a gate; unverified at merge** |
| PII never reaches an LLM at merge | the disabled-default boundary (no scrubber) | **boundary is the flag, NOT a scrubber — stated unsoftened** |

Nothing verifiable only with the LLM enabled is presented as proven. No
mock/fixture appears as accuracy evidence.

---

## 5. Decisions closed at review (LOCKED)

All four resolved at plan review. Coding implements exactly these.

1. **Provider — DEFERRED (governance), LOCKED.** Plan picks only the
   gate *shape* (default-off structural for any provider). Does NOT pick
   OpenAI/Anthropic/other and does NOT authorise enablement. **A
   deliberate operator governance act is required before the LLM is ever
   turned on; not required to merge (PR C merges disabled).**
2. **Flag — LOCKED: `NL_QUERY_LLM_ENABLED` on `config.py` `Settings`**,
   `os.getenv("NL_QUERY_LLM_ENABLED","false").lower()=="true"`, the
   `DEBUG`/`ENABLE_METRICS` house pattern (discoverable; the test
   monkeypatches `settings.NL_QUERY_LLM_ENABLED`).
3. **`/ask` capability — LOCKED: reuse `clinical_query`.** Coherence:
   `/ask` reaches *exactly* the same data through the same chokepoint;
   a capability narrower than the data it exposes is incoherent (the
   locked-decision-#4 logic). **Two required PR-body statements:** (a)
   the coherence justification stated explicitly; (b) **the explicit,
   load-bearing point that reusing `clinical_query` (rather than minting
   a new capability) means PR A's `module_digitisation`-does-NOT-entail-
   `clinical_query` Type-C ratchet
   (`test_module_digitisation_never_entails_clinical_query`)
   automatically covers `/ask` by construction — the written Type-C
   customer promise is enforced on the NL surface for free, zero new
   ratchet code, *because* of the coherent choice.** Coherent-choice-
   pays-twice; show it in the record. (A distinct `clinical_query_nl`
   was rejected: it would need a migration-025-style seed = scope
   expansion AND a new ratchet to keep the Type-C promise — the reuse
   inherits both for free.)
4. **Phrasing-set scope — LOCKED with the adversarial modification.**
   In-set: thin as recommended — **1 canonical + 1 paraphrase per
   template** (14 in-set goldens). Adversarial set: **the load-bearing
   half; explicitly NOT governed by "thinnest"** — its sizing principle
   is *hazard-shape coverage*, not minimality. The in-set goldens verify
   the safe direction (a known-phrasing miss still produces a
   constrained, runner-validated, provenance-resolved answer); the
   dangerous direction is out-of-set phrasings that *almost* match a
   template with a clinically material difference and must hard-refuse —
   misclassification there is the silent-wrong-answer this whole phase
   guards against, and it is *invisible to every structural gate* (it
   stays inside the output-domain envelope). The adversarial set MUST
   therefore include, at minimum:
   - a **near-miss pair**: two phrasings differing by a clinically
     material term, one mapping to a template, one that must refuse;
   - a **PII-bearing question naming a real patient** — asserting
     flag-off constructs **no client at all** (not "politely refuses");
   - a **plausible clinical question with no registered template** —
     must refuse with the answerable list, **never approximate to the
     nearest template**.
   Generic gibberish is the easy case and proves little; the near-miss
   is the case that silently converts and is where the adversarial set
   earns its place.

---

## 6. Risks (Phase-3 honesty standard)

- **NL balloon** — mitigated *structurally by scope, not hope*: the
  model's entire callable surface is the registry-derived tool set;
  refusal is default outside the closed enum. Residual vector: the
  phrasing set growing — bounded by §5 #4 being a deliberate user call.
- **The question carries PII; disabled-default is the boundary, NOT a
  scrubber** — stated unsoftened in the plan, `nl_query.py` docstring,
  test docstrings, PR prose (same words). Risk: a reviewer infers a
  scrubber exists; mitigation is the repeated explicit statement (PR
  A/B "checkable-but-not-checked" / "construct-validity-only"
  discipline).
- **Mocked tests prove wiring, not accuracy** — risk green CI misread
  as "NL works"; mitigation: test docstrings + PR verification
  statement state verbatim accuracy is unverified until enabled, never
  gated (PR B xfail-with-asserted-reason shape).
- **Tool-schema/registry drift** — structurally prevented (regenerated
  from `all_templates()` each call; named equality gate; no validator
  surfaced). Hand-edit fails CI.
- **Validator internals invisible to schema (accepted-by-design)** —
  `validate_order_by`'s enum is validator-body, not serialisable; the
  runner catches out-of-enum (`invalid_param`→422); the classifier
  deliberately does NOT re-implement validation (design choice #4: the
  runner is the single validation authority). Accepted: surfacing
  validator internals IS the forbidden drift.
- **Refactor-defeats-the-gate** — a future move of the provider import
  to module top-level, or `_client()` before the flag check, would
  silently defeat default-off. Mitigation: the `__import__`-trap +
  `_client`-sentinel in the named gate fail the build if
  construction/import becomes reachable with the flag off — the gate
  guards its own preconditions.

---

## 7. What PR C earns; explicitly deferred to PR D

**Earns — TWO claims, deliberately UN-fused (required tightening; the
PR-A/PR-B earns-section overclaim, third occurrence, same cure — the
earns section must not re-fuse what the §4 ledger correctly separated):**

  - **PROVEN at merge — the output-domain constraint.** The classifier's
    output domain is *exactly* `{registered template id} × {params}` ∪
    refusal. It structurally *cannot* emit SQL, free-form, or an
    unregistered template — the model's only callable surface is the
    registry-derived tool set, regenerated each call and asserted equal
    to the registry by the drift gate; the refusal matrix proves
    out-of-set/unknown-tool/low-confidence → refusal. This is load-
    bearing and earned. It rides the **same
    `run_template`+`resolve_provenance` chokepoint** as `/run` (proven
    by the no-new-data-path recorder, not asserted), so NL answers
    inherit PR A/B's verifiable-provenance contract because it is the
    *same code path*. And — coherent-choice-pays-twice — because `/ask`
    reuses `clinical_query`, PR A's Type-C ratchet covers the NL surface
    *for free, by construction* (decision #3).
  - **NOT verified at merge — mapping correctness.** Whether the
    classifier picks the *right* enum member for a given real phrasing
    is **entirely unverified at merge** and is exactly the accuracy the
    §4 ledger brackets. "Constrained to the closed enum" must NOT be
    read as "safe": the classifier can pick the *wrong registered
    template*, confidently, and that wrong answer still passes the
    runner, still gets provenance-resolved, and still looks
    authoritative — **the misclassification failure is *inside* the
    safety envelope of every structural gate this PR ships and is
    therefore invisible to all of them.** It is knowable only via the
    opt-in eval once a provider is authorised. In a regulator's or a
    future-self's hands, "constrained to the closed enum" must mean
    *output-domain-constrained*, never *mapping-correct* — the half that
    is false (it may do the *wrong* registered thing) is precisely the
    silent-wrong-answer this entire phase exists to prevent, and it is
    named here, unsoftened, exactly as the ledger names it.

**Ships disabled**, and that disabled-default is a *structural CI
invariant* (named, executable, three traps), not a comment: flag unset
⇒ no client, no outbound call, the (PII-bearing) question goes nowhere,
`/ask` hard-refuses with the answerable list. The umbrella's reframed
standard applied to NL: **the provenance-verifiable primitives are the
brakes (shipped & proven in A/B); NL is the steering wheel — brakes
first, steering wheel ships locked until an operator deliberately
enables it.**

**Residual, unsoftened:** with the flag off (the merge state) classifier
*accuracy is entirely unverified* — mocked tests prove wiring only;
correctness is knowable only via the opt-in eval once a provider is
authorised (governance, deferred outside Phase 3 engineering). No PII
scrubber; the day the flag is on, PII-in-the-question reaches the chosen
provider — a deliberate operator act the code makes hard, not
impossible. NL does not widen what is answerable (only the 7 registered
templates, exactly as `/run`).

**Deferred to PR D (NOT absorbed here):** standing-query materialisation
(`StandingQuery`, `materialise_standing_queries()`, `briefing_items`,
migration 027, worker tick); `POST /api/query/briefing/refresh` + `GET
/api/query/briefing`; the Phase 3 close-out post-mortem; the MANDATORY
named-not-built conversion-instrumentation scope note (PR D deliverable,
recorded here only as *not in PR C* — and tracked in memory
[[phase3-tracked-deferrals]]); enabling the LLM / provider authorisation
(governance, §5 #1); POPIA query-access logging (Phase 5 — NL rides the
existing `run_template` chokepoint so it inherits that future decorator
slot for free, a positive consequence of "no new data path").

**Named deferred consequence — the shared rate-limit bucket (required
addition; name it at the cheap boundary, not in production).** `/ask`
reuses `/run`'s existing in-process 30/60s bucket (§3.2). With the flag
off this is inert (no `/ask` traffic). The day the flag is enabled this
becomes a real coupling: `/ask` and `/run` *share* a budget, so a burst
of one consumes the other's. This is NOT a merge blocker (flag-off makes
it inert, same logic as everything else deferred here) but it is a named
consequence the **flag-enablement governance review (§5 #1) must
include**: "decide whether `/ask` needs its own bucket" — resolved at
that boundary, not discovered in production. Same discipline as the
`prescription_items` index and the conversion-instrumentation note:
name the deferred consequence where it is still cheap to see. Recorded
in memory [[phase3-tracked-deferrals]] alongside the others.
