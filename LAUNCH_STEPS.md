# SurgiScan Essential — Launch Steps

**Status: build complete (incl. real change-password as of 2026-05-24).**
**All remaining steps are operational.**

This is the ordered, scannable "what's left" guide. Each step links to the
operational detail in `DEPLOYMENT.md` or to the script that does the work.
Estimated total time end-to-end (assuming nothing surprises): **half a day**.

---

## Pre-flight (~10 min)

- [ ] **P1.** Confirm `.env.production` points at the right Supabase project
  (`veuwldlkunetbeqgxptc` is the live prod project). Double-check
  `SUPABASE_URL` / `DATABASE_URL` before running anything against prod.
- [ ] **P2.** `migrations/` contains 014, 033, **034 + 035 + 036 + 037 + 038**.
  All five must reach PROD with the migration history (the queue, vitals-nullable,
  AI-scribe transcript table, tier-product alignment, clinical-AI guardrail).
  Verify by re-running the prod migration replay if any are missing — the
  history is the source of truth, never an ad-hoc script.
- [ ] **P3.** Confirm there is **no `admin@surgiscan.com` / `typec@surgiscan.com`
  account** in PROD (or that their passwords have been rotated to strong unique
  ones). DEV has these accounts with `password123`; if seeded into prod, they're
  an unconditional auth backdoor. Run: `SELECT email FROM users WHERE email IN
  ('admin@surgiscan.com', 'typec@surgiscan.com')` against PROD — expect zero rows.

---

## 1. Deploy on Render (~30–45 min the first time)

- [ ] **1.1.** Push the Render blueprint (`render.yaml`). Both services come up
  (backend `web:docker`, frontend `web:static`). Detail: `DEPLOYMENT.md` §3.
- [ ] **1.2.** Set **backend secrets** in the Render dashboard:
  `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `DATABASE_URL`, `OPENAI_API_KEY`,
  `LANDING_AI_API_KEY`, `VISION_AGENT_API_KEY`. `JWT_SECRET_KEY` auto-gens.
  `DEBUG=false` is already set in the blueprint.
- [ ] **1.3.** Set frontend env: `REACT_APP_BACKEND_URL` → the backend's
  Render URL. **DO NOT set `REACT_APP_ENABLE_DEV_LOGIN`** — leaving it unset
  keeps the dev auto-login routes inert in the production bundle.
- [ ] **1.4.** Wire **CORS**: set the backend's `CORS_ORIGINS` to the exact
  frontend origin from step 1.3, redeploy backend.

---

## 2. Smoke + safety verification (~15 min)

- [ ] **2.1. Health.** `curl https://<backend>/api/health` → green; the body
  reports the prod tenant / workspace.
- [ ] **2.2. API surface hardened.** `/docs` and `/openapi.json` return 404
  (proves `DEBUG=false`).
- [ ] **2.3. Login works.** Provision a throwaway test user with
  `onboard_practice.py --plan essential --dry-run` first to confirm the script
  resolves correctly against prod; then for real on a test practice; log in;
  rotate the password via **Settings → Change Password**; log out; log back in
  with the new password.
- [ ] **2.4. ⚠ Live cross-tenant probe** against the deployed prod backend.
  Verified against DEV + the prod DB this session, but NOT yet against the
  deployed API. Ask me to run it (~2 min) once prod is reachable.
- [ ] **2.5. ⚠ One live LandingAI OCR smoke.** Upload a single real GP PDF
  through the live prod backend; drive it through *validate → approve → promote*.
  The OCR stage is the one path that was synthetic-only during the rebuild (to
  save credits) — this proves the full chain works end-to-end in prod.
- [ ] **2.6.** Confirm **Supabase Pro backups** are on for the prod project.

---

## 3. Onboard customer #1 (~5 min)

- [ ] **3.1.** Run, pointed at the prod env file:
  ```bash
  PYTHONPATH=. ./.venv/bin/python scripts/onboard_practice.py \
    --practice "Customer Practice Name" \
    --email dr@customer.co.za \
    --name "Doctor Name" \
    --plan essential
  ```
  The script creates tenant + workspace + `module_digitisation` entitlement +
  admin user with a strong random password; runs the post-write capability check
  (must show **OK — digitisation_upload, … granted** and no tier leak); prints
  the login email and the auto-generated password.
- [ ] **3.2.** Hand the **email + password** to the customer over a secure
  channel (encrypted message / WhatsApp voice note / in person — not plain email).
- [ ] **3.3.** Tell them to log in and **immediately rotate the password** via
  *Change Password* in the sidebar.
- [ ] **3.4.** Brief them on the lock-out fallback: "if you're ever locked out,
  message us — we'll regenerate within 5 minutes." (Powered by
  `scripts/reset_user_password.py`; the email-flow forgot-password is a
  post-launch build.)

---

## 4. Operational standing items (post-launch, week 1)

- [ ] **4.1.** Watch logs for the first 48 hours — login, digitisation upload,
  promote. Anything unexpected on `/api/auth/*` or `/api/digitisation/*` is the
  first signal to investigate.
- [ ] **4.2.** Decide on the briefing scheduler. The autonomous tick exists
  but ships disabled. Two options: enable it
  (`app/services/standing_query_scheduler.py`, default-off via config), or run
  an external cron hitting `POST /api/query/briefing/refresh` at 06:00 daily.
  Without one, the briefing requires a manual refresh.
- [ ] **4.3.** Track LandingAI credit consumption against budget (per-page cap
  is configured; review the burn rate against customer #1's usage).

---

## What this guide deliberately does NOT include
- **Self-service forgot-password (email flow).** Concierge fallback only for
  v1 — see `scripts/reset_user_password.py` and `ONBOARDING_RUNBOOK.md`.
  Self-service is a deliberate post-launch build (requires email-service
  integration).
- **MFA.** Not in v1.
- **Public self-serve signup.** Concierge model is the v1 go-to-market.
- **Professional-tier onboarding flow polish.** The Professional tier is
  built + browser-verified but has no first customer yet; the onboarding
  command exists (`--plan professional` → `platform_professional`) and is
  capability-boundary checked, but real Professional onboarding is its own
  exercise when the first Professional customer signs.

---

## Where to look if something goes wrong

| Symptom | First check |
|---|---|
| Backend won't start | Render logs; `DATABASE_URL` / `SUPABASE_URL` typos; secrets missing |
| Login 401 with the issued password | User row exists? `password_hash` populated? Run `reset_user_password.py` to regenerate |
| Login 401 after a successful change-password | Backend hot-restarted mid-request — try again; check `/api/auth/me` returns the right user |
| CORS errors in browser console | `CORS_ORIGINS` exact-match with the frontend origin (no trailing slash); redeploy backend |
| `/api/digitisation/upload` 403 | Entitlement check failed — confirm the practice has `module_digitisation` and not just `platform_essential` (both grant digitisation but onboarding uses `module_digitisation`) |
| Digitised document never reaches the validation queue | LandingAI key / quota; check the worker logs for the document id |

---

## When you're ready, say so
The build side is done. Step P1–P3 you can do now; step 1–3 needs your hands on
the Render dashboard + customer #1. Tell me when you're past step 1 and I'll run
2.4 (the live cross-tenant probe) and stand by for 2.5 if you want me to drive it.
