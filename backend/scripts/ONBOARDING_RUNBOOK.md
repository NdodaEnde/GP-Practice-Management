# Onboarding a new practice (Essential / digitisation tier)

Concierge model: we provision each practice; there is no public self-serve
signup yet. Takes ~1 minute per practice.

## Provision

From `backend/`, with the env pointed at the **intended** project (check
`.env` → `SUPABASE_URL` / `DATABASE_URL` before running on production):

```bash
PYTHONPATH=. ./.venv/bin/python scripts/onboard_practice.py \
  --practice "Wellness Medical Centre" \
  --email dr@wellness.co.za \
  --name "Thandi Khumalo"
# password auto-generates and prints; pass --password to set your own.
# add --dry-run first to preview.
```

This creates: tenant → workspace → `module_digitisation` entitlement
(`status=active`, `payment_status=manual`) → first **admin** user (bcrypt
password). It then verifies the entitlement actually grants the
`digitisation_*` capabilities and prints the login email + password.

## Hand-off to the customer

1. Send them the **login email + password** (over a secure channel).
2. They log in at the app URL and should land on the digitisation Dashboard.
3. They add their own staff in-app (admin → user management); new staff
   inherit the workspace + its entitlement.

## Billing (manual)

`payment_status='manual'` means SurgiScan is the source of truth and you
invoice out-of-band (EFT / a manual PayFast link). Nothing is auto-charged.
To suspend access for non-payment, set the entitlement `status` to `paused`
(capabilities then evaluate to none and the tier locks).

## Notes / guardrails

- **Email is the global login identity** and must be unique; the script
  refuses a duplicate email or a taken workspace id.
- Provisions **Essential only** — `module_digitisation`. Do not grant
  `patient_ehr_basic` (Professional EHR) here; that tier hasn't been swept.
- If "Capabilities: WARNING" prints, the products/capabilities catalog seed
  is missing on that project — apply the entitlement seed migrations first.
