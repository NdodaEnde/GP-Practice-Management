# Phase 4 — The Proactive Layer: Close-Out Post-Mortem

**Status — the framing in one sentence:** Phase 4 delivered the
`OpenLoop` substrate (PR F: the fourth ontology object + a closed,
proven-to-bite state machine + audited reversible actions, zero real
instances), one thin real derived cohort (PR G: `immunisation_overdue`,
1/31, labelled thin), and an honest backend pre-consult composition
(PR H) — and it **closes with its defining safety constraint formally
UNMET**, recorded here unsoftened, gate-enforced, and in pre-merge-quoted
words, because the platform's trust thesis is upheld not by claiming the
property is visible but by stating, in language merged before any
pressure to soften it, exactly that it is not.

This is the Phase 4 close-out artifact. It is load-bearing, not
paperwork: its presence and its load-bearing sentences are asserted by a
build-failing test
(`backend/tests/test_phase4_closeout.py::test_phase4_closeout_artifacts_present`),
proven non-vacuous (each load-bearing phrase removed individually
asserts the gate bites; the §A quotation additionally verified
byte-faithful to its live source file and proven to bite by mutation).
That gate is the **automatable necessary** condition; it is **not
sufficient** — discharge proper additionally requires the human-verified
read by the named verifier at review, against the **not-invertible-to-met
standard**: no sentence — especially the §A quotation, which pulls out
of context more easily than authored prose — may be invertible by an
adversarial reader quoting in isolation into "Phase 4 met its safety
constraint." **"Discharged" must never be read as "the parser passed".**

---

## §A. The defining constraint — formally UNMET, in the locked words, the quotation byte-faithful to its pre-merge source

Phase 4's defining safety constraint, carried from the Phase-3 close-out
(§B "Phase-4 cannot close until the openable-vs-unresolvable rendering is
verified against the real briefing UI"), is the moment the resolver's
openable-vs-unresolvable safety property becomes **visible to the human
it protects**. It was **NOT met.** PR E (the briefing UI that would
render the contrast) is held — `MorningBriefing.jsx`/`briefing.js`
untracked, never merged; there is no clinician-visible surface; the
contrast was never pixel-rendered against a real login on the honest
corpus.

In the umbrella/Decision-5 locked words, recorded here exactly and not
softened:

> **Phase 4 closed with its defining safety constraint — the
> openable-vs-unresolvable contrast seen by a human — formally UNMET and
> re-inherited to Phase 5.**

The most load-bearing sentence of this close-out is **not authored this
turn**. It is a verbatim quotation of a commitment merged into
`backend/scripts/provision_briefing_demo.py` (lines 70-78) at PR B —
*before Phase 4's outcome was known, before any pressure to soften it
existed, by a past instance that could not have been serving this
moment because this moment did not yet exist*. Quoted here, the words
exactly as the source commits them (re-read from the source file at the
moment this close-out was authored; the gate verifies this block
byte-faithful to those source lines and is proven to bite if the
quotation is mutated):

> "orphan-rendering remains probe-verified-only (verify_query_phase0.py
> probe iv/v + the unit form in test_query_layer_invariants.py); the
> browser contrast confirmed OPENABLE and NO_SOURCE rendering only; no
> orphan was injected to complete the demo."
>
> That is the EXPECTED path, not a failure. The orphaned-source case is
> the dominant *corpus* finding (15/24 on test-workspace-* tenants) and
> is verified there by the probe, never manufactured here.

That commitment, made before the outcome was known, is why this
close-out can state the constraint UNMET without that being a softening
or a manufactured cleanliness: the honest path was pre-declared the
expected, accepted, non-failure path. The constraint is not met. It is
re-inherited to Phase 5.

---

## §B. What Phase 4 actually delivered — honestly, no overclaim

- **PR F — the OpenLoop substrate.** The fourth ontology object, a
  **closed transition table proven non-vacuous by fault injection**
  (illegal transitions asserted rejected; a legal-only suite cannot
  pass), an independent second-guard `model_validator`, four audited
  reversible actions through the existing executor. **Zero real
  instances** (F-1=B: substrate only; no detector); the first real
  stateful loop is deferred — the legitimate-A door (specialist-referral-
  pending) is a deliberate future call, never inferred.
- **PR G — one thin derived cohort.** `immunisation_overdue`, a
  **stateless** `StandingQuery` kind (NOT an OpenLoop — locked
  Decision 3), materialising through the proven chokepoint into
  `briefing_items`, **thin: 1 overdue of 31, labelled thin, NOT
  corpus-proven at volume**. The PR-D "configuration, not a project"
  substrate paying off: a new kind is a template + a registration.
- **PR H — the honest backend pre-consult composition.** Composes ONLY
  what the corpus backs: active-medications + a per-patient audit-log
  diff-since-last-visit (over the existing `action_audit_log`
  GIN-indexed containment) + the `immunisation_overdue` kind.
- **What Phase 4 did NOT deliver, stated unsoftened:** no stateful loop,
  no loop detector, no clinician-visible surface (PR E held), the
  openable-vs-unresolvable contrast not human-visible. Allergies-via-the-
  query-layer and reason-for-visit are **named-not-built** (allergies:
  a table exists but no template — building one for pre-consult
  completeness is the legitimate-in-general / not-for-this-reason-now
  anti-pattern, refused; RFV: no ingestion path exists).

---

## §C. The carried Phase-3 obligations, re-inherited verbatim (because Phase 4 is the phase that closes)

**Conversion instrumentation (named-not-built, the hardest-guarded
anchor):** measuring which briefing / pre-consult items a prospecting or
live practice actually acts on is a known, named future consumer of
exactly this standing-query materialisation substrate. It is
deliberately NOT built — it structurally cannot be until real customers
generate real interaction events. When the first customer arrives it
MUST be a small configuration of this infrastructure — a new
`StandingQuery` kind writing rows into `briefing_items` through the SAME
`run_template` + `resolve_provenance` chokepoint, inheriting the same
verifiable-provenance and tenant-scoping contract — NOT a from-scratch
analytics build rediscovered late. The substrate was shaped for this;
the work is correctly deferred, not lost.

**The shared-trigger sentence:** three deferred consequences share ONE
trigger — the first real customer with real data volume:
(1) `idx_prescription_items_prescription_id` (the scale index);
(2) the conversion-instrumentation `StandingQuery` kind (above);
(3) the `/ask` ↔ `/run` ↔ `/briefing` shared rate-limit bucket. When
that customer lands the "what gets slow / what needs measuring / what
needs its own budget" review is **one review** against this single
trigger, not three rediscovered late. All three are tracked in the
project memory `project_phase3_tracked_deferrals`.

---

## §D. The legible scars — THE CREDENTIAL (load-bearing-equal of §A)

This section is not supporting material. **§A states the constraint was
unmet; §D is the evidence the system that failed to meet it is
nonetheless trustworthy.** A close-out recording only the unmet
constraint is honest but bleak; one recording the unmet constraint AND
the legible history of every caught failure AND the discipline
*compounding* is the actual credential — it says the constraint was not
met *and here is why you can trust the system that says so.*

- **PR D — the false-green caught after signature.** A §2.4-signed
  close-out cited a test as backing its highest-priority guard; the test
  was vacuous. Caught by verifying the premise before running to report,
  not by test execution. Fixed by raising the test to the prose, never
  lowering the prose; the signature was withdrawn and re-given on the
  artifact read. The scar is unsquashed in `main` history deliberately.
- **PR F — the FK-cycle teardown.** The first integration run failed in
  test teardown (the `action_audit_log` close↔reversal FK cycle), which
  left real residue in a live audit log. Reported before interpretation,
  cleaned FK-correct, the cycle-safe idiom recorded (§5.1) for any
  future audit-row cleanup to inherit.
- **PR G — the stale-assertion scaffolding failure, and the method
  COMPOUNDING.** The first materialisation run failed on a stale
  `assert post` left by an incomplete test edit (NameError) — **but with
  zero live-DB harm**, because PR F's residue lesson had been applied
  *prospectively* (residue-safe teardown written before the run). PR F's
  scar became PR G's prophylaxis. Two consecutive first-run scaffolding
  failures named the pattern; the cure — **test scaffolding written to
  the same bar as the code it certifies, reviewed before the run, never
  acceptable-because-a-different-safeguard-caught-it** — is inherited
  knowledge, applied to this close-out's own gate (which has no residue
  net: the assertion is the only safeguard).

The discipline is not merely held; it transfers and improves. That is
what makes the close of a phase on its own unmet defining constraint a
trustworthy artifact rather than a bleak one.

---

## §E. What re-inherits to Phase 5

- **The formally-UNMET defining constraint** (the §A sentence): the
  openable-vs-unresolvable contrast seen by a human. Phase 5 inherits it
  in the §A locked words; it is not lost, not softened, not re-derivable
  as "met".
- **The conversion-instrumentation / shared-trigger first-customer
  trigger** (§C): one review when the first real customer with real data
  volume lands.
- **The legitimate-A door:** specialist-referral-pending as a future
  stateful loop is a deliberate Phase-5 (or later) call made on its own
  product merits and stated as such — never inferred from any prior PR's
  wish to populate the substrate.
- **The §D discipline:** verify the premise; build the load-bearing part
  first and prove it bites; test scaffolding to the code bar; the scar
  is the credential. Phase 5 inherits the method, not just the
  artifacts.

"Closes" here means **the obligation to record Phase 4's outcome
truthfully is discharged — NOT that the defining constraint was
satisfied.** It was not. This document is the discharge of that
obligation, and the gate + the named verifier's not-invertible-to-met
read are its necessary and sufficient conditions respectively.
