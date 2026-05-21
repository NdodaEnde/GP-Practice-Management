# Phase 4 — PR E Implementation Plan: Morning-Briefing UI (discharges the inherited Phase-3 close-condition)

> **Status:** plan APPROVED at review at the A/B/C/D bar. **E-1, E-2,
> E-3 are FINAL (locked, §6).** Grounded in fresh live-DB read-only
> probes **2026-05-17, `main`@`51d1664`** (the `verify_query_phase0.py`
> idiom: `load_dotenv('backend/.env')`; `psycopg2.connect(DATABASE_URL)`;
> `set_session(readonly=True)`). Implements the LOCKED umbrella decisions
> verbatim; no decision is re-opened here. **E-1 FINAL = Option 2: BOTH
> halves carry forward via path (ii)** (§2.2 — superseded the earlier
> hybrid on an empirical finding made at PR-E execution time: the
> registered `morning_briefing` kind returns 0 rows for the only
> entitled+loginable workspace, so the legitimate login does not
> discharge the openable half either, and option-1's
> product-motivated-kind is rejected by the survives-deleting-the-demo
> test). **Executed this turn (all done, raw):** `provision_briefing_
> demo_login.py` → one verified `users` row; `provision_briefing_demo.py`
> → safe no-op; the **real authenticated materialiser round-trip**
> (login → `POST /briefing/refresh` → GET) exercised end-to-end →
> `{rows:0, unresolvable_count:0, superseded_count:0}` / `{count:0}` —
> the honest-zero is the materialiser's own output, the full real path
> run. PR E's plumbing (auth, `clinical_query` gate, route, screen,
> refresh→materialise→render) is **verified through the real
> `:3000`→`:8002` chain**; PR E is **not mergeable as the safety
> discharge** (E-2) — the close-out records BOTH halves UNMET on the
> honest corpus through the build-failing gate in the **verbatim
> pre-committed words** + the Decision-5 sentence (§2.0, §2.2, §5, §6).
>
> **Premise the probe corrected (norm #1 — verify before asserting; same
> discipline as PR D's Finding W worker-topology correction):** the
> umbrella's grounding #3 said the contrast-corpus fork has "three honest
> outcomes, (a)/(b)/(c)". **The live probe proves outcome (c) obtains
> HARD, and no honest placement move produces the contrast** — the
> openable corpus and the unresolvable corpus are in *different*
> workspaces, the unresolvable corpus is *only* in non-entitled no-login
> `test-workspace-*`, and `briefing_items` is *empty*. The umbrella was
> directionally right that this is risk #1 but under-stated its severity:
> this is not "probe to discover which of three outcomes" — the probe has
> run and the answer is (c). **Locked Decision 5 is therefore not a
> contingency for PR E — it is PR E's governing decision**, and PR E's
> load-bearing work (§2) is resolving *which Decision-5 path* the user
> locks, BEFORE any UI code. PR E is genuinely not mergeable with §3
> (the UI) green and §2 (the path) unresolved — that is the actual build
> order, the same shape as PR D's "close-out green before standing-query
> code", not a slogan.
>
> **The locked-Decision-1 rider, restated because this is exactly where
> it bites:** PR E is thin in *surface area* (one route, one service
> method, one screen) and **maximal in fork-honesty**. §2 is the hard
> part and it is not thin. "Thin" anywhere in this plan means
> small-in-code, never low-stakes. The screen §3 renders is the first
> time in the entire project the Phase-3 safety property becomes visible
> to the human it exists to protect; that does not get done thin.

---

## 1. Empirical findings (live DB, read-only, 2026-05-17 `main`@`51d1664`)

Probe scripts ran read-only (`SET SESSION CHARACTERISTICS … READ ONLY`,
autocommit, no writes). The load-bearing facts were pinned by *explicit*
queries, not inferred (e.g. `briefing_items` emptiness confirmed by
`SELECT count(*)`, not by an empty `GROUP BY`).

### Finding L1 — exactly two `clinical_query`-entitled workspaces (confirms PR D Finding E)

`SELECT w.id FROM workspaces w WHERE 'clinical_query' = ANY(practice_capabilities(w.id))`
→ exactly **`demo-gp-workspace-001`** and **`demo-briefing-workspace-001`**.
All `test-workspace-*` and `typec-workspace-001` → not entitled
(unchanged from PR D; the trusted materialiser source is these two).

### Finding L2 — the "no login" fact, pinned by direct user count

`users` table: `email, workspace_id, role` (+ password_hash etc.).
Per-workspace human-login reality:

| Workspace | entitled (L1) | users (human login) |
|---|---|---|
| `demo-gp-workspace-001` | ✅ | **4** (`admin@surgiscan.com`, `validator@…`, `uploader@…`, `qwathi@gmail.ocm`) |
| `demo-briefing-workspace-001` | ✅ | **0** |
| `typec-workspace-001` | ❌ | 1 (`typec@surgiscan.com`) |
| `test-workspace-*` | ❌ | 0 |

§B's "`demo-briefing-workspace-001` has no login" is now a *counted*
fact, not a recollection: 0 user rows.

### Finding L3 — `briefing_items` is EMPTY (explicit count)

`SELECT count(*) FROM briefing_items` → **0**. No briefing data exists in
any workspace right now. The PR D materialiser proved the path; its test
partitions were torn down and the autonomous tick ships disabled, so the
table is presently empty. PR E's UI therefore has *nothing to render*
until a materialisation is run for a workspace — and which workspace
decides what `source_status` the rows carry.

### Finding L4 — the three honest source states live in THREE DIFFERENT workspaces, and the disqualifying split

Cross-referencing the live corpus with L1/L2 (and PR D Findings C/S,
re-asserted live: demo-gp `patients_not_seen_since` → `no_source`;
demo-briefing → `openable`; the orphaned diagnosis → `unresolvable`):

| Workspace | entitled | login | briefing `source_status` if `morning_briefing` materialised |
|---|---|---|---|
| `demo-gp-workspace-001` | ✅ | ✅ | **`no_source` only** — NULL-sourced corpus; 0 sourced-diagnoses-with-live-doc (Finding E in probe); no openable, no unresolvable |
| `demo-briefing-workspace-001` | ✅ | ❌ | **`openable`** (1 sourced diagnosis with a live doc) — but **no unresolvable row** |
| `test-workspace-*` (incl. `c9f4d540`) | ❌ | ❌ | **`unresolvable`** (1 genuine orphaned-source diagnosis each, real reverse/delete history) — but **not entitled, no login** |

**The disqualifying facts, stated unsoftened:**
1. The only workspace that is *entitled ∧ human-loginable* is
   `demo-gp-workspace-001`, and it is **`no_source`-only** — it
   structurally cannot show either an openable *or* an unresolvable row,
   let alone the contrast.
2. The openable corpus and the unresolvable corpus are in **different
   workspaces**, and the unresolvable corpus exists **only** in
   non-entitled, no-login `test-workspace-*`.
3. Therefore **no single workspace is (entitled ∧ loginable ∧ contains
   both an openable and an unresolvable row)**, and **no entitlement/
   login placement move of any *single* workspace produces the
   contrast** — because even the most generous candidate (give
   `demo-briefing-workspace-001` a login) yields *openable only*, never
   the openable-vs-unresolvable contrast, since demo-briefing has no
   unresolvable row.

**Conclusion (Finding L4): umbrella outcome (c) obtains, hard. Locked
Decision 5 governs PR E.** This was caught by the Phase-0 probe run
before any UI code — at plan time, not at PR H under pressure. The
method worked.

---

## 2.0 The inherited pre-commitment (§D.1-class note — recorded so it is NOT re-derived as a fresh Phase-4 judgement)

> Same register as the post-mortem's §D / §D.1: not failure narration —
> a premise tested at PR E plan time and found to have been **already
> confronted and answered, correctly, in merged review-enforced code at
> PR B, before Phase 4 existed.** A future maintainer must inherit the
> *knowledge* that the load-bearing half of the E-1 decision is an
> inherited pre-commitment, not a Phase-4 call, so it is not re-litigated
> nor re-derived under later pressure.

The contrast-corpus fork (Finding L4: the honest corpus cannot present
the openable-vs-unresolvable contrast on one entitled+loginable screen
without manufacturing an orphan) is **not new to Phase 4.** Phase 3 PR B
confronted exactly this fork when it built
`backend/scripts/provision_briefing_demo.py` (the script that created
`demo-briefing-workspace-001`), and pre-committed the honest resolution
**in the script itself**, review-enforced, travelling with the code:

- **Legitimacy contract — `provision_briefing_demo.py:19-42` (read in
  the artifact, not summarised):** clinical facts are produced ONLY by
  the real production path — the patient via the production
  `match_or_create_patient` helper, every fact EXCLUSIVELY via
  `execute(PromoteDocumentToPatientRecord(...))`, the identical executor
  the digitisation "approve" endpoint calls; the script contains ZERO
  direct `.table("<fact>").insert(...)` calls; **"Any direct fact-table
  INSERT added to THIS script is the seeded-to-order anti-pattern and
  FAILS REVIEW."**
- **Orphan foreclosed — `:64-66`:** *"This script MUST NOT delete the
  document to manufacture an orphan, and MUST NOT inject an
  orphaned-source fact by any means."* This is precisely the move
  rejected as current-state laundering for E-1 path (i)-A — the project
  wrote that rejection into merged code at PR B, before the question was
  re-asked.
- **Pre-committed accepted outcome — `:56-78`, the verbatim wording the
  Phase-4 close-out REUSES (it is a quotation of a pre-merge commitment,
  NOT prose authored this turn — that is the decisive refinement):**

  > *"orphan-rendering remains probe-verified-only
  > (verify_query_phase0.py probe iv/v + the unit form in
  > test_query_layer_invariants.py); the browser contrast confirmed
  > OPENABLE and NO_SOURCE rendering only; no orphan was injected to
  > complete the demo."*

  followed by `:76-78`: *"That is the EXPECTED path, not a failure. The
  orphaned-source case is the dominant corpus finding (15/24 on
  test-workspace-* tenants) and is verified there by the probe, never
  manufactured here."*

**Why this is the strongest provenance any decision in this project has
had.** Every prior gate applied the discipline *at the gate* (caught at
review, at premise-check, by reading the artifact). Here the discipline
was applied *before the question was asked* — by a past instance of the
same method — and PR E's plan work was to discover the answer was
already merged and still binding. The unresolvable half being
carry-forward is therefore not a Phase-4 judgement call dressed as
inheritance; it is a PR-B decision, in code, under the same legitimacy
contract, with the accepted wording pre-written **so it could not be
softened under later pressure** — exactly the failure mode (a sentence
honestly worded but written under pressure to soften) the §D.1 lesson
and the twice-withdrawn signature exist to defend against. PR B defended
against it prospectively; Phase 4 inherits the defence. **Do not
re-derive this; quote it.**

---

## 2. The load-bearing part of PR E — the contrast-corpus fork resolution (scoped FIRST, carried-constraint weight)

> **This section is PR E.** §3's UI is the small-surface part that sits
> on top of a *resolved* fork. The fork is resolved by the user locking
> one Decision-5 path on the honest evidence below — not by PR E choosing
> under pressure, and not by any move that fails locked Decision 2's
> survives-deleting-the-demo test.

### 2.1 Locked Decision 2's survives-deleting-the-demo test, applied to every candidate

The test (locked, verbatim): a placement/login change is outcome (b)
(legitimate) **only if it is justified by a reason that survives
deleting the close-condition from the argument**; if the *only* reason is
"so PR E can pixel-verify the contrast", it is outcome (c) wearing (b)'s
clothes — the migration-025 Option-C anti-pattern.

| Candidate move | Does it survive deleting the close-condition? | Verdict |
|---|---|---|
| **Seed an openable+unresolvable pair into `demo-gp`'s `briefing_items`** | No — the only reason to hand-write those rows is to pass the click. | **Rejected** — the construct-validity anti-pattern Phase 3 refused twice. Not on the table. |
| **Give `test-workspace-c9f4d540` (real orphan) `clinical_query` + a user** | No — a throwaway test workspace becoming entitled+loginable has no coherent reason except "its orphan is the unresolvable demo data". | **Outcome (c), not (b)** — laundered anti-pattern; rejected. |
| **Relocate the real orphaned diagnosis from a `test-workspace` into `demo-gp`/`demo-briefing`** | No — moving real data across tenants purely so it co-locates with openable data for the demo is seeding-to-order with real bricks. | **Outcome (c), not (b)** — rejected. |
| **Give `demo-briefing-workspace-001` a human login** | *Legitimate (and done).* The workspace is the GTM-load-bearing demo corpus (verified, §2.2) — its reason to exist survives deleting the close-condition; a briefing-demo workspace no human can log into is incoherent on its own terms. **But** the registered `morning_briefing` kind returns 0 rows there (patient seen inside the 180-day window — proven by the live materialiser round-trip), so the login does **not** surface an openable row. | **Login: legitimate outcome (b), executed.** Openable-half discharge: **NOT achieved** — the registered kind and the openable corpus do not intersect in the loginable workspace. Both halves carry forward (E-1 Option 2, §2.2). |
| **Register a different (product-motivated) standing kind that surfaces a sourced row** | No — *as the fix for PR E's contrast*. PR G will register loop kinds for real product reasons; pulling one forward *because it makes PR E show openable* is PR-G-shaped work done for PR E's contrast: legitimate-in-general, not-legitimate-for-this-reason-now. A genuine, independently-decided PR-G pull-forward on PR-G's own merits remains open as a *separate explicit decision*, never inferred, never the fix-for-the-contrast. | **REJECTED as PR E's openable-half fix (E-1 final, Option 1 declined)** — the migration-025 Option-C / §D.1 anti-pattern wearing "it's a real PR-G kind anyway". |
| **In `demo-briefing`, perform a reversal to produce a dead-link unresolvable row, then give demo-briefing a login** | No — as the situation actually stands there is no independent reason to reverse a real promotion in demo-briefing now; the only thing that wants it is PR E's need for the contrast. **§2.0: PR B already foreclosed exactly this in merged code** (`provision_briefing_demo.py:64-66`: MUST NOT delete the document to manufacture an orphan; MUST NOT inject an orphaned-source fact by any means). | **REJECTED (E-1 final)** — current-state laundered-reversal; the project wrote this rejection into merged review-enforced code at PR B before the question was re-asked. |

### 2.2 E-1 FINAL — Option 2: BOTH halves carry forward (LOCKED; superseded the hybrid on an empirical finding at PR-E execution time)

> **Supersedes the earlier hybrid.** The hybrid (openable half via
> (i)-B-minus-reversal) assumed the registered `morning_briefing` kind
> would surface a sourced/openable row in the loginable workspace once
> the login was granted. **It does not.** That assumption was tested at
> PR-E execution time and falsified — the §D.1 discipline, one more
> time: the premise was verified, not asserted, and it failed.

Finding L4 = outcome (c). What PR-E execution additionally established
(all done; raw, before interpretation):

- `provision_briefing_demo_login.py` ran → exactly **one verified
  `users` row** (`briefing-demo@surgiscan.com`, `demo-briefing-
  workspace-001`, role `validator`); the login is legitimate outcome (b)
  (the workspace is the GTM-load-bearing demo corpus the sales motion
  runs on — `provision_briefing_demo.py:5-13`,
  `marketing/brochure_doctors_v1.md:75`, `TRACEABILITY.md:513`,
  `ONTOLOGY_PHASE3_PRD_PLAN.md:75` — all predating Phase 4; a
  briefing-demo workspace no human can log into is incoherent on its own
  terms).
- `provision_briefing_demo.py` re-asserted → safe no-op (document
  already promoted from the original PR-B run).
- **The real authenticated materialiser round-trip was exercised
  end-to-end** (login → `POST /api/query/briefing/refresh` → GET):
  `results: {"demo-briefing-workspace-001:morning_briefing":
  {rows:0, unresolvable_count:0, superseded_count:0}}`,
  `GET → {count:0, items:[]}`. The registered `morning_briefing`
  (`patients_not_seen_since`, 180d) returns **zero rows** for the only
  entitled+loginable workspace, because its sole patient was seen
  2026-01-08 — *inside* the 180-day recall window, correctly excluded.
  The honest-zero is the **materialiser's own output**, the full real
  path run, not an unpopulated screen.

So the legitimate login (outcome (b), done) does **not** discharge the
openable half: the registered kind and the openable corpus do not
intersect in the loginable workspace. The only way to make an openable
row appear there is to register a *different* standing kind chosen
because it surfaces a sourced row — and **option 1 (a product-motivated
additional kind) is REJECTED by the locked survives-deleting-the-demo
test**: PR G's loop taxonomy will register kinds for real product
reasons, but pulling one forward *here, now, because it makes PR E's
screen show openable* is PR-G-shaped work done for PR E's contrast —
"legitimate in general, not legitimate for this reason now", the
migration-025 Option-C / §D.1 anti-pattern wearing "it's a real PR-G
kind anyway" as its disguise. (A genuine, independently-decided PR-G
pull-forward on PR-G's own merits remains open as a *separate explicit
decision*, never inferred and never the fix-for-the-contrast.)

**Therefore BOTH halves carry forward via path (ii) (LOCKED).** The
openable half and the unresolvable/contrast half are both recorded —
through the build-failing presence gate proven non-vacuous (umbrella
Decision 4, the §2.4/§D.1 mechanism) — as **UNMET on the honest corpus
and re-inherited to Phase 5**. The close-out's most load-bearing
sentence is a **quotation of the already-merged, review-enforced PR-B
commitment** (`provision_briefing_demo.py:70-78`), reproduced verbatim,
NOT prose authored this turn:

> *"orphan-rendering remains probe-verified-only (verify_query_phase0.py
> probe iv/v + the unit form in test_query_layer_invariants.py); the
> browser contrast confirmed OPENABLE and NO_SOURCE rendering only; no
> orphan was injected to complete the demo." … "That is the EXPECTED
> path, not a failure. The orphaned-source case is the dominant corpus
> finding (15/24 on test-workspace-* tenants) and is verified there by
> the probe, never manufactured here."*

plus the umbrella Decision-5 path-(ii) sentence in its locked words:
**Phase 4 closed with its defining safety constraint — the
openable-vs-unresolvable contrast seen by a human — formally UNMET and
re-inherited to Phase 5.** The §C/§E discipline at its strongest: the
unsoftened residual is trusted not because it was written carefully this
turn but because it was written and merged **before any pressure to
soften it existed** — the pre-commitment removing this decision from the
pressure of the moment by having been decided, in code, before the
moment arrived.

**Why Option 2 is the materially stronger outcome, not a fallback.**
Every path to the openable screen requires manufacturing something — a
seeded row, a relocated orphan, a reversal-for-contrast, or a kind
minted because it makes the demo green. The platform's entire trust
thesis is that it does not. A real screen rendering the true empty/zero
state, plus a close-out that quotes a pre-merge commitment naming
exactly what the honest corpus cannot show and why, is a *more*
trustworthy artifact than a green screen produced to be green. The
materialiser was *run* end-to-end and correctly produced nothing,
because the honest corpus contains nothing to show — a more complete
true statement than "the screen rendered empty".

**Explicitly not on the table** (rejected, §2.1 + §2.0): any
`briefing_items` seed; any test-workspace entitlement/relocation; any
document-deletion or reversal performed to manufacture the orphan; any
standing kind registered *because* it would make PR E show openable.

### 2.3 Build order (load-bearing, not a slogan) — E-2 FINAL

§2 fork is **resolved** (E-1 locked, §2.2; resolved by inherited
pre-commitment, §2.0). Build order is the **PR D shape**:

1. **PR E.1 (the named openable-half deliverable):** grant
   `demo-briefing-workspace-001` a login and re-assert the existing
   legitimacy-contract-bound provisioning (`provision_briefing_demo.py`,
   re-runnable safe no-op). **No orphan, no reversal-for-contrast** — the
   §2.0 / `:64-66` foreclosure is binding. This is scoped *as the openable
   half*, nothing more.
2. **§3 the small-surface UI**, then
3. **the build-failing close-out gate** recording the unresolvable-half
   carry-forward in the **verbatim pre-committed words** (§2.2 quote).

PR E is **not mergeable** until the openable half is human-verified —
the named verifier logs in through the real `:3000`→`:8002` chain,
clicks the real openable source, watches the real scan open (the actual
screen, not a screenshot of it — the §2.4/§D.1 discipline) — **AND** the
unresolvable half's carry-forward is recorded through the build-failing
gate in the pre-committed verbatim wording. Same shape as PR D gating
the standing-query code on the close-out being genuinely discharged.

---

## 3. The small-surface UI (sits on top of a resolved §2)

**Single load-bearing property (umbrella, verbatim):** a human, logged
into the real frontend through the real `:3000` → `:8002` chain against a
real entitled workspace, sees the materialised briefing rows rendered
such that an **openable** source actually opens the real scan (clicked,
in a browser) and an **unresolvable** source is shown as a visible,
explicit known-unknown that *cannot* be silently mistaken for a live
link.

**Deliverables (paths; sized at implementation — small surface):**

- **PR E.1 — the openable-half deliverable (E-2 step 1; runs before the
  UI is mergeable).** Grant `demo-briefing-workspace-001` a real user
  (the legitimate outcome-(b) login; mirror the existing `users`-row
  seed shape — `init_users_table.py` idiom — a real loginable account in
  that workspace, e.g. a `briefing-demo` admin). Re-assert the existing
  legitimacy-contract-bound provisioning by running
  `provision_briefing_demo.py` (re-runnable; safe no-op if already
  promoted, per its lines 81-84). **Hard constraints, inherited from
  §2.0 and binding at review:** zero direct `briefing_items` or
  fact-table INSERTs; no document deletion; no reversal performed to
  manufacture an orphan. PR E.1 produces *only* the openable + no_source
  honest states; the unresolvable half is NOT its job (it is the
  carry-forward of §2.2). This is the entire "minimal honest
  corpus/placement work" Decision 5 path (i) scopes — and it is minimal
  precisely because the script already exists.
- **`frontend/src/services/briefing.js`** — `getBriefing(kind?,
  asOfDate?)` → `GET /api/query/briefing`; `refreshBriefing()` →
  `POST /api/query/briefing/refresh`. Uses the existing axios instance
  so the `AuthContext` interceptor attaches the JWT (no new auth code).
  Backend base URL is the frontend's configured `REACT_APP_BACKEND_URL`
  (`:8002`); the `:8001` in `backend/.env` is the known discrepancy —
  verified at dev-server-start, not asserted away.
- **`frontend/src/pages/MorningBriefing.jsx`** + a `/briefing` route in
  `App.js` behind `ProtectedRoute`, nav-gated in `Layout.jsx` on the
  same capability the backend gates (`clinical_query`) — the
  capability-gated nav filter already exists.
- **The rendering contract, pinned from the code (`query.py:347-357`),
  not from a summary (grounding #4 / §D.1 discipline):**
  `GET /api/query/briefing` returns `{workspace_id, count, items:[…]}`
  where each item is a raw `briefing_items` row from `.select("*")`. Each
  item therefore carries **both** the denormalised top-level columns
  `source_status` / `openable` / `unresolvable_reason` / `citation`
  (cheap badge signal) **and** `row_payload` (JSONB). **The signed URL
  is at `row_payload.source.signed_url`, NOT in any top-level column.**
  The UI MUST:
  - render the **openable** state as a link/button whose target is
    `row_payload.source.signed_url`; if that is absent the row is NOT
    rendered openable (the silent-dead-link guard, mirrored client-side);
  - render the **unresolvable** state first-class: the explicit
    `citation` (carrying Phase 3's locked truncated-id wording, e.g.
    `source document no longer available (id …e15a71)`),
    `openable=false`, **never a clickable live-link element**;
  - render **no_source** as the honest "entered directly in the EHR (no
    source document)" non-failure, distinct from unresolvable;
  - surface the envelope's cohort-level unresolvable signal at the top
    of the screen (the Phase-3 reason a per-row marker alone is
    insufficient at the altitude a clinician reads a 40-row list).

**Defers:** OpenLoop (PR F); the loop taxonomy (PR G); pre-consult +
close-out (PR H). PR E renders exactly what is materialised; it adds no
migration, no OpenLoop, no new backend data path.

---

## 4. Tests

- **`frontend`** — the renderer's three-state logic is unit-tested
  against pinned fixtures mirroring the real `briefing_items` row shape
  (openable with `row_payload.source.signed_url`; unresolvable with
  truncated-id citation + `openable=false`; no_source). The client-side
  silent-dead-link guard (no `signed_url` ⇒ never rendered openable) is
  an explicit test, mirroring the backend CI invariant.
- **`backend`** — a thin API test that `GET /api/query/briefing` for a
  workspace with no materialised rows returns `count:0` cleanly (the
  honest-empty state PR E will actually hit on `demo-gp` today), and that
  the row shape the renderer pins is the shape the endpoint emits (a
  shape-contract test, the §D.1 "verify the premise not the wording"
  discipline applied client/server).
- **The contrast itself is NOT a unit test.** It is the human screen-read
  of §5 — by construction, because the whole point is that the property
  must be *seen*, not asserted.

---

## 5. PR E verification statement (REQUIRED WORDING — quote verbatim in the PR description; do not soften) — FINAL, Option 2

> *PR E discharges, by E-1 (Option 2), NEITHER half as a human-visible
> safety property and claims exactly that. **What PR E verified** (real
> `:3000`→`:8002` chain, all executed): authentication
> (`briefing-demo@surgiscan.com` → token), the `clinical_query`
> capability gate (nav entry shown AND endpoint 200, not 403), the
> `/briefing` route, the screen rendering the honest empty state, and —
> closing the last loop — the **real authenticated materialiser
> round-trip**: login → `POST /api/query/briefing/refresh` →
> `materialise_standing_queries` over the one entitled workspace →
> `{rows:0, unresolvable_count:0, superseded_count:0}` → `GET
> /api/query/briefing → {count:0, items:[]}`. The full real path was
> RUN and correctly produced nothing, because the honest corpus contains
> nothing to show for the registered kind (its sole patient was seen
> inside the 180-day recall window) — the honest-zero is the
> materialiser's own output, a complete true statement, not an
> unpopulated screen. **What PR E did NOT discharge:** the
> openable-vs-unresolvable contrast — NEITHER half. The openable half is
> not human-visible because the registered `morning_briefing` kind and
> the openable corpus do not intersect in the only entitled+loginable
> workspace, and the only fixes are manufacture (forbidden) or a
> kind-minted-for-the-contrast (rejected, §2.2). The unresolvable half is
> not human-visible because an orphan in an entitled+loginable workspace
> would require manufacturing what PR B foreclosed in merged
> review-enforced code (§2.0). **Both halves carry forward via path
> (ii).** The Phase 4 close-out records this through the build-failing
> presence gate proven non-vacuous (umbrella Decision 4, §2.4/§D.1), and
> its most load-bearing sentence is a **verbatim quotation of the
> already-merged PR-B pre-commitment** (`provision_briefing_demo.py`
> 70-78): "orphan-rendering remains probe-verified-only … no orphan was
> injected to complete the demo. That is the EXPECTED path, not a
> failure," plus the umbrella Decision-5 path-(ii) sentence in its locked
> words: Phase 4 closed with its defining safety constraint — the
> openable-vs-unresolvable contrast seen by a human — formally UNMET and
> re-inherited to Phase 5. This is NEVER worded as either half being met;
> the plumbing (incl. the materialiser round-trip) is reported as
> verified, the contrast as carried-forward, and the residual sentence is
> trusted because it was merged before any pressure to soften it existed,
> not because it was written carefully this turn.*

---

## 6. Decisions locked at review — E-1, E-2, E-3 FINAL

Recorded as the user locked them; the reasoning is the lock and is
recorded so it can be overridden deliberately, not re-derived. No
umbrella decision is re-opened.

**E-1 — FINAL: Option 2 — BOTH halves carry forward via path (ii)
(§2.2; superseded the hybrid).** Path (i)-A **REJECTED** (laundered
reversal; §2.0 — PR B foreclosed it in merged code at
`provision_briefing_demo.py:64-66`). The hybrid's openable-via-(i)-B
assumption was **falsified at PR-E execution time**: the legitimate
`demo-briefing-workspace-001` login was granted (one verified `users`
row) and the existing provisioning re-asserted, but the real
authenticated materialiser round-trip proved the registered
`morning_briefing` kind returns **0 rows** there (sole patient seen
inside the 180-day window) — so the login does not surface an openable
row. **Option 1 (a product-motivated additional kind) declined** by the
locked survives-deleting-the-demo test: PR-G-shaped work pulled forward
*because it makes PR E show openable* is the §D.1 anti-pattern in
disguise; a genuine independently-decided PR-G pull-forward remains a
separate explicit decision, never inferred. **Both halves therefore
carry forward**, recorded through the build-failing gate **reusing the
verbatim `provision_briefing_demo.py:70-78` wording + the Decision-5
formal-UNMET-re-inherited-to-Phase-5 sentence, NOT newly authored
prose**. Option 2 is the materially stronger outcome: every path to the
openable screen manufactures something; the platform's value is that it
does not. The decision's authority is the merged PR-B pre-commitment,
decided in code before the moment that would pressure it.

**E-2 — FINAL: build order is the PR D shape (§2.3); PR E is not the
safety discharge.** **PR E.1** (grant demo-briefing a login + re-assert
the legitimacy-contract provisioning; no orphan, no
reversal-for-contrast) was **executed** — one verified `users` row;
provisioning a safe no-op. The PR E plumbing is **verified through the
real `:3000`→`:8002` chain**, including the authenticated materialiser
round-trip (login → refresh → materialise → GET) which correctly
produced `{rows:0}`. PR E is **not mergeable as the safety discharge**:
no half is human-visible; the close-out records BOTH halves UNMET
through the build-failing gate in the pre-committed verbatim words.
Phase 4's terminus is Decision-5 path (ii).

**E-3 — FINAL: yes, PR E ships the small-surface UI under Option 2.** It
renders the honest state — empty/`no_source` on the registered kind —
and the full real materialiser path was exercised and correctly
produced nothing. The close-out names BOTH unmet halves in the
merged-code wording. A shipped honest screen rendering the true zero
state, the materialiser round-trip run end-to-end, plus a close-out
quoting a pre-merge commitment for what could not be shown, is the most
trustworthy artifact available; §5's wording prevents any conflation of
the verified plumbing with a discharged contrast.

---

## What PR E earns when it lands

The small-surface morning-briefing screen exists and renders the
materialised rows with the openable / unresolvable / no_source states
visually distinct and the cohort-level unresolvable signal at reading
altitude. What PR E **genuinely earns**: the full plumbing verified
through the real `:3000`→`:8002` chain — authentication, the
`clinical_query` capability gate, the `/briefing` route, the screen, and
the **real authenticated materialiser round-trip** (login → refresh →
`materialise_standing_queries` over the one entitled workspace → GET)
run end-to-end and correctly producing `{rows:0, count:0}`. The
honest-zero is the materialiser's own output: the real path was *run*
and correctly produced nothing because the honest corpus contains
nothing to show for the registered kind. What PR E **does not** earn,
and states without softening: NEITHER half of the
openable-vs-unresolvable contrast is human-visible — the openable half
because the registered kind and the openable corpus do not intersect in
the only loginable workspace (every fix manufactures or mints), the
unresolvable half because an orphan there would require manufacturing
what PR B foreclosed in merged code. Both carry forward as
UNMET/probe-verified-only, re-inherited to Phase 5, in the **verbatim
wording PR B pre-committed before any pressure to soften it existed**.
This terminus was not chosen under Phase-4 pressure — it was inherited
from a merged, review-enforced PR-B commitment, the strongest provenance
any decision in this project has had. The screen is real, the empty
state is true, the materialiser was run, and the close-out tells the
truth in words written before the truth was inconvenient.
