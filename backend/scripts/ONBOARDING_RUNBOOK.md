# Onboarding a new practice (Essential or Professional)

Concierge model: we provision each practice; there is no public self-serve
signup yet. Takes ~1 minute per practice.

## Provision

From `backend/`, with the env pointed at the **intended** project (check
`.env` → `SUPABASE_URL` / `DATABASE_URL` before running on production):

```bash
PYTHONPATH=. ./.venv/bin/python scripts/onboard_practice.py \
  --practice "Wellness Medical Centre" \
  --email dr@wellness.co.za \
  --name "Thandi Khumalo" \
  --plan essential            # or: professional
# --plan defaults to essential.
# password auto-generates and prints; pass --password to set your own.
# add --dry-run first to preview.
```

This creates: tenant → workspace → the tier entitlement (`status=active`,
`payment_status=manual`) → first **admin** user (bcrypt password):

| `--plan`        | entitlement              | grants                        |
|-----------------|--------------------------|-------------------------------|
| `essential`     | `module_digitisation`    | digitisation only (no EHR)    |
| `professional`  | `platform_professional`  | digitisation + full EHR       |

It then verifies the entitlement grants the right capabilities **and** that it
does not leak forbidden ones (an Essential practice must not come out with
`patient_ehr_basic`), then prints the login email + password.

## Hand-off to the customer

1. Send them the **login email + password** (over a secure channel — not plain email).
2. They log in at the app URL and should land on the digitisation Dashboard.
3. **Tell them to rotate the password on first login** via the sidebar →
   *Change Password*. The endpoint (`POST /api/auth/change-password`) verifies
   the current password and writes a new bcrypt hash; 8-character minimum.
4. They add their own staff in-app (admin → user management); new staff
   inherit the workspace + its entitlement.

## If a customer is locked out / forgot their password (v1 concierge fallback)

There is no self-service forgot-password email flow in v1 (intentionally
deferred — see DEPLOYMENT.md). The concierge fallback is:

```bash
PYTHONPATH=. ./.venv/bin/python scripts/reset_user_password.py \
  --email dr@wellness.co.za
# add --dry-run first to preview; --password 'StrongPass123' to set explicitly
```

This generates a strong random password, writes the new bcrypt hash to the
user's row, and prints the new password **once**. Send it over a secure
channel; ask the customer to rotate it on next login.

## Billing (manual)

`payment_status='manual'` means SurgiScan is the source of truth and you
invoice out-of-band (EFT / a manual PayFast link). Nothing is auto-charged.
To suspend access for non-payment, set the entitlement `status` to `paused`
(capabilities then evaluate to none and the tier locks).

## Notes / guardrails

- **Email is the global login identity** and must be unique; the script
  refuses a duplicate email or a taken workspace id.
- **Never** entitle a real practice to `legacy_full_access_grant` — that's the
  internal/sunset "everything" bundle the demo workspace rides on; it gives away
  unpaid Clinical-AI/analytics modules. Use the tier products above.
- If the capability check **FAILS** (missing required, or a tier leak), the
  products/capabilities catalog seed is wrong on that project — apply the
  entitlement seed migrations (incl. **037**, which aligns the tier products)
  before onboarding.
- Default landing differs by plan: Essential → digitisation Dashboard;
  Professional → also has the EHR/clinical nav.
