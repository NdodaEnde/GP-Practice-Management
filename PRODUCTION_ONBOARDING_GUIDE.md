# Production Readiness & Client Onboarding Guide

> Status: written from a verified read of the live codebase + Supabase
> project as of 2026-05-18. "Verified" = I checked the file/DB; "Gap" =
> confirmed missing; "Decision" = needs your call before it ships.

---

## Part 0 — Honest current state (what exists vs what doesn't)

| Thing | State |
|---|---|
| Backend `server:app` (:8002) + in-process document watcher | Exists, runs |
| Frontend (CRA) | Exists, runs (`npm start`) |
| Entitlement model (tenant→workspace→user→`practice_entitlements`→product→capabilities) | Exists, verified working end-to-end |
| Onboarding tool `scripts/provision_practice.py` (founder-only ops CLI, Paystack-driven) | Exists |
| Deny-by-default auth floor (ZERO) + capability gating | Exists (committed) |
| Pricing page (`frontend/src/pages/Pricing.jsx`) | **Updated & live** — Essential = Digitisation tier, R3,500 founder /practice/month → R4,000 from 1 Sep 2026; Professional/Intelligence "Coming soon"; comparison matrix removed; vendor/architecture words scrubbed from the frontend UI |
| Self-serve signup → pick tier → workspace + entitlement created | **Does NOT exist** (Gap) — `register_user` does not grant entitlements |
| Separate production environment | **Does NOT exist** (Gap) — one Supabase project holds demo + test + would hold real |
| Backups / point-in-time recovery | **None** on the free plan (Gap) |
| Demo/test data isolation | **None** — demo & real would co-mingle (this caused the earlier data-loss incident) |

**The single most important fact:** there is no staging/production
separation. The workspaces you have (`typec-workspace-001`,
`demo-gp-workspace-001`, `demo-briefing-workspace-001`, ~33
`test-workspace-*`) are demo/seed/test tenants **in the same database a
real client would land in.** Fix this before any real client.

---

## Environments — how Local / Staging / Production fit together

**An "environment" = one self-contained copy of the whole stack:** its own
Supabase project (Postgres + `medical-records` storage + keys) + a running
backend (`server:app` + the in-process document watcher) with its own
`.env` + a frontend build pointed at that backend
(`REACT_APP_BACKEND_URL`) + its own external keys (Paystack, extraction,
OpenAI, `JWT_SECRET_KEY`).

**Iron rule: each environment has its OWN Supabase project. Nothing
shared.** A bad delete or bug in one can never reach another's data. The
earlier data-loss incident happened precisely because there was only one
project.

| | Local / Dev | Staging | Production |
|---|---|---|---|
| Purpose | build & experiment | rehearse changes before customers | real paying customers |
| Supabase project | existing one, demo + test data | its own clean project | its own clean project, **Pro: backups + PITR** |
| Data | synthetic / throwaway | synthetic only | **real PHI only** |
| Runs | laptop (`localhost`) | deployed host (e.g. `staging.surgiscan.co.za`) | deployed host (e.g. `app.surgiscan.co.za`) |
| Paystack | test mode | test mode | **live mode** |
| `.env` / keys | dev | staging | prod, most guarded |
| Access | you, freely | you, to verify | locked; changes only via promotion |

**Today only Local exists** — everything is `localhost` against the one
shared free Supabase project. Staging and Production do not exist yet.

**Promotion flow (how a change reaches customers):**

```
edit locally → test on Local
  → deploy build to Staging → apply migrations on staging → verify (synthetic)
  → deploy SAME build to Production → apply SAME migrations → real users
```

A migration is **always proven on staging before prod**. You never run a
migration for the first time against the database holding patient data.

**Staging vs Production differ on purpose in only three ways:** data
(synthetic vs real), keys/mode (Paystack test vs live; separate Supabase
projects; separate JWT secret), and access (open vs locked). Code,
migrations, seeds, and the storage bucket are identical.

**Pragmatic sequence for your stage (do not over-build):**
1. **Now, non-negotiable:** one isolated **Production** Supabase project
   (Pro plan, backups + PITR). This alone removes the real risk.
2. **Interim staging:** the existing dev project doubles as staging for
   the first client or two — rehearse the migration apply + the
   onboarding runbook there before touching prod.
3. **Dedicated Staging project:** add later (~$25/mo) once you have
   paying customers and changes worth de-risking, so you stop rehearsing
   on the demo project.

**Honest caveat (specific to this stack):** LandingAI / extraction has
**no free sandbox** — it spends real credits in *any* environment. Keep
staging cheap by using the synthetic fixtures
(`backend/tests/fixtures/demo_*`) sparingly, not by expecting a free test
mode. Paystack *does* have a real free test mode — use it everywhere
except prod.

---

## Part 1 — Production-readiness checklist (do these BEFORE the first real client)

1. **Stand up a separate production Supabase project.**
   - New Supabase project, **paid plan** (the free plan has no
     backups/PITR — unacceptable for POPIA-governed clinical data).
   - Enable daily backups + point-in-time recovery.
   - Apply the full migration set (`backend/migrations/*` in order) +
     the seeds (`backend/seeds/products_and_capabilities.sql`,
     `migrations/023`, `025`, `030`, etc.) to the new project.
   - **Do NOT copy demo/test data into it.** It starts empty.

2. **Production env config.**
   - Separate `.env` for prod: prod `SUPABASE_URL`/`SUPABASE_SERVICE_KEY`,
     a strong unique `JWT_SECRET_KEY` (the dev default
     `"your-secret-key-change-in-production"` MUST be changed),
     `LANDING_AI_API_KEY`/`VISION_AGENT_API_KEY`, OpenAI key (semantic
     search), prod Paystack keys.
   - The Supabase **service key bypasses RLS** — it must never reach the
     browser or a client; backend-only, founder-held for ops scripts.

3. **Deploy the apps to a hosted environment.**
   - Backend `server:app` behind HTTPS (not localhost), with the
     document watcher running (it's in-process on startup — fine, but
     ensure the host doesn't sleep the process).
   - Frontend built (`npm run build`) and served as static assets;
     `REACT_APP_BACKEND_URL` pointed at the prod backend HTTPS URL.
   - Confirm the deny-by-default auth floor is active in prod.

4. **Data protection / POPIA.**
   - Verify Supabase RLS is on for tenant tables (migration 018 enabled
     RLS — confirm it holds in the prod project).
   - Patient consent capture (the intake form has a consent block — make
     sure it's recorded, not just rendered).
   - A documented data-handling policy: real PHI only in prod, never in
     dev/demo; demo always synthetic (the `tests/fixtures/demo_*`
     generators exist for this).
   - Audit log (`action_audit_log`) is populated by the action executor
     — keep it; it's your POPIA/processing trail.

5. **Billing wiring (Paystack).**
   - `provision_practice.py` already expects Paystack subscription +
     plan codes. Create the real Paystack **plans** for the Digitisation
     tier (founder and list price — see Part 2) and wire the webhook so
     a successful subscription triggers provisioning (or, interim, ops
     runs the script manually on payment confirmation).

6. **Backups & recovery runbook.**
   - With PITR on the paid plan, document: how to restore, who can, and
     test it once. (The earlier incident — deleted records, no recovery
     — must not be possible in prod.)

7. **Monitoring.**
   - Error logging/alerting on the backend; watch the watcher
     (parse/extract failures), LandingAI credit usage, and auth
     rejections.

8. **A staging environment (recommended).**
   - A third Supabase project + deploy for testing changes before prod,
     so demo/QA never touches prod and prod never touches demo.

---

## Part 2 — Pricing (Digitisation tier, Founder Plan) — LOCKED

**Decided this session — no longer open:**
- The **Essential** tier *is* the Digitisation product
  (`module_digitisation`). Professional & Intelligence are
  "Coming soon", not yet sellable.
- Price: **R3,500 / practice / month**, **flat per practice (not per
  doctor)**, founder pricing locked if the practice signs up before
  **31 August 2026**; **R4,000 / practice / month from 1 September
  2026**.
- `frontend/src/pages/Pricing.jsx` is **done**: prominent Founder-Plan
  box, R4,000 visible, outcome-only copy, vendor/architecture words
  removed, comparison matrix removed. (Verified compiled; uncommitted.)

**Still an action before billing goes live:**
1. **Reconcile the price source.** `seeds/products_and_capabilities.sql`
   still documents Digitisation list price as **R4,500**. The decision
   is **R4,000**. Update that seed/strategy reference to R4,000 so the
   database, the Paystack plan, and the page all agree. The page is
   already R4,000; the seed is not yet.
2. **Create the Paystack plans:** founder **R3,500/practice/month** and
   list **R4,000/practice/month**, flat per practice. The subscription
   code feeds `provision_practice.py`.

**Founder-price protection** is enforced server-side by
`practice_entitlements.is_founder_pricing` + `founder_protection_until`
(set by `provision_practice.py`), not by the page. The page only
advertises the deadline.

---

## Part 3 — Signup → tier → workspace: how it should work

**Your question:** "will the users on signup click on the tier and then
that will be the workspace they're assigned to?"

**Today:** there is **no self-serve signup that does this.** A user can
register an account, but registration does **not** create a workspace
or attach an entitlement. Onboarding is a manual ops action (Part 4).

**Recommended target design (this is the build to do):**

```
Prospect → Pricing/Signup page → picks "Digitisation" tier
   → enters practice details + creates admin user
   → pays via Paystack (subscription on the Digitisation plan)
   → Paystack webhook (or ops on payment confirmation) provisions:
        • a tenant
        • a workspace  (this becomes "their" workspace)
        • the admin user, linked to that workspace
        • a practice_entitlements row: product_id='module_digitisation',
          is_founder_pricing per sign-up date, founder_protection_until,
          Paystack sub/plan codes
   → on next login the JWT carries their workspace_id; capabilities
     resolve to the Digitisation set; they see the Digitisation nav only
```

So: **the tier they pick determines the product entitlement attached to
the new workspace that is created for them.** One practice = one
workspace = one entitlement (the product they bought). The
capability-gating you already have does the rest (Type-C sees
digitisation only; a full-bundle buyer sees more).

This is the automation of exactly what `provision_practice.py` does
manually. Until it's built, use the manual runbook (Part 4).

---

## Part 4 — Onboarding runbook (works TODAY, manual)

For each new client, ops (founder-held, prod service key) does:

1. **Confirm payment.** Client pays the Digitisation Founder
   subscription in Paystack → note the `SUB_xxx` (subscription code) and
   the `PLN_xxx` (plan code).

2. **Create the practice's workspace + tenant + admin user** in the
   **production** project (a small provisioning step — pattern is in
   `scripts/provision_typec_demo.py`: insert `tenants`, `workspaces`,
   `users` rows with the client's real details and a strong password).

3. **Attach the entitlement** with the ops CLI:
   ```
   python backend/scripts/provision_practice.py \
     --practice-id <the new workspace id> \
     --product-id module_digitisation \
     --paystack-sub-code SUB_xxx \
     --paystack-plan-code PLN_dig_founder \
     --founder-pricing \
     --duration-months 12
   ```
   (Run with the **production** `.env`. `--list` shows current
   entitlements for audit.)

4. **Verify**: log in as the client admin → confirm the Digitisation
   nav appears (upload / validation / export) and a synthetic test
   upload promotes end-to-end. Then hand over credentials.

5. **Founder price protection** is recorded on the entitlement
   (`is_founder_pricing`, `founder_protection_until`). When it elapses,
   ops moves them to the list-price plan (per the schema comment in
   migration 001).

---

## Part 5 — Open items before the first real client

Pricing (per-doctor-vs-flat, R4,000-vs-R4,500) is **resolved**: flat
per practice, R4,000, and the page is done. What's still open:

1. **Reconcile the price source + create Paystack plans** — set the
   seed/strategy from R4,500 → R4,000; create founder R3,500 / list
   R4,000 plans, flat per practice (Part 2).
2. **Stand up a separate, paid production Supabase project** with
   backups/PITR — the single biggest blocker. Apply migrations + seeds,
   start empty (no demo/test data).
3. **Deploy** backend (HTTPS) + frontend (built) pointed at the prod
   project; confirm the deny-by-default auth floor is active.
4. **Onboard the first clients manually** via Part 4
   (`provision_practice.py`). Self-serve signup is a later build, not a
   blocker.
5. (Flagged, optional) Scrub vendor names from **backend code/logs +
   root `.md` docs** — not demo-facing; the frontend UI is already done.

---

### Summary — the path

Pricing is locked and live on the page (Essential = Digitisation,
R3,500 flat/practice founder → R4,000 from 1 Sep 2026). You are still
**not** production-ready — same DB for demo/test/real, no backups, no
separate prod environment, no self-serve signup. None of that blocks a
**manual** first onboarding once a clean prod project exists. Ordered
path to the first paying client:

1. Reconcile the seed/Paystack price to R3,500 / R4,000 (Part 2).
2. Stand up a paid production Supabase project + backups; apply
   migrations/seeds; keep it empty (Part 1).
3. Deploy backend + frontend against that project (Part 1).
4. Onboard the first client **manually** via `provision_practice.py`
   (Part 4).
5. Automate self-serve signup later (Part 3) — not a blocker.

The separate prod environment is the real gate, not the tooling —
manual onboarding works the day a clean prod project exists.
