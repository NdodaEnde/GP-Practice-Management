#!/usr/bin/env python
"""
onboard_practice.py — concierge provisioning for a new practice (Essential or Professional).

Creates, in one shot, everything a new customer needs to log in:
  1. tenant
  2. workspace (the practice)
  3. practice_entitlements row for the chosen TIER product, billed 'manual'
     (you invoice out-of-band):
       --plan essential     -> platform_essential / module_digitisation (digitisation only)
       --plan professional  -> platform_professional (digitisation + full EHR)
     NB: never the sunset internal `legacy_full_access_grant` (the dev "everything"
     bundle the demo workspace rides on) — that gives away unpaid modules.
  4. first admin user (bcrypt password — same hashing the login uses)

Run:
  PYTHONPATH=. ./.venv/bin/python scripts/onboard_practice.py \
      --practice "Wellness Medical Centre" \
      --email dr@wellness.co.za \
      --name "Thandi Khumalo" \
      [--plan essential|professional]     # default: essential
      [--password 'StrongPass123']        # omit to auto-generate
      [--workspace-id wellness-medical]   # omit to derive from name
      [--dry-run]

Idempotency: refuses if the email already exists or the derived workspace id
is taken. On any mid-way failure it prints exactly what was created so you can
clean up. Targets whatever DATABASE_URL / SUPABASE_* the loaded .env points at
— double-check you're pointed at the intended project before running on prod.
"""
import argparse
import re
import secrets
import sys
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv

# Load env from the backend dir regardless of CWD.
import os
_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_BACKEND, ".env"))

from app.api.auth import supabase as sb, get_password_hash  # noqa: E402

# Tier -> the product to entitle + the capability invariants to verify post-write.
# 'require' must all be granted; 'forbid' must NOT be (proves the tier boundary,
# e.g. Essential genuinely has no EHR). See migration 037 for the catalog shape.
PLANS = {
    "essential": {
        "product_id": "module_digitisation",   # == platform_essential caps (digitisation only)
        "tier_label": "essential",
        "require": {"digitisation_upload", "digitisation_validation"},
        "forbid": {"patient_ehr_basic"},        # Essential = digitisation only, NO EHR
    },
    "professional": {
        "product_id": "platform_professional",  # digitisation + full EHR (single clean product)
        "tier_label": "professional",
        "require": {"digitisation_upload", "patient_ehr_basic"},  # the superset
        "forbid": set(),
    },
}


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s[:40] or "practice"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def fail(msg: str, created: list):
    print(f"\n✗ {msg}")
    if created:
        print("  Already created (clean these up if you re-run):")
        for c in created:
            print(f"    - {c}")
    sys.exit(1)


def main():
    ap = argparse.ArgumentParser(description="Provision a new practice (Essential or Professional).")
    ap.add_argument("--practice", required=True, help="Practice / workspace display name")
    ap.add_argument("--email", required=True, help="First admin user's email (login identity)")
    ap.add_argument("--name", required=True, help="Admin full name, e.g. 'Thandi Khumalo'")
    ap.add_argument("--plan", default="essential", choices=sorted(PLANS),
                    help="Tier to provision (essential = digitisation only; professional = + full EHR)")
    ap.add_argument("--password", help="Admin password (auto-generated if omitted)")
    ap.add_argument("--workspace-id", help="Explicit workspace id (derived from name otherwise)")
    ap.add_argument("--tier", help="Override the cosmetic subscription_tier label (defaults to --plan)")
    ap.add_argument("--dry-run", action="store_true", help="Show what would be created; write nothing")
    args = ap.parse_args()

    plan = PLANS[args.plan]
    product_id = plan["product_id"]
    tier_label = args.tier or plan["tier_label"]

    email = args.email.strip().lower()
    if "@" not in email:
        fail(f"'{email}' doesn't look like an email", [])

    ws_id = (args.workspace_id or f"{slugify(args.practice)}-{uuid.uuid4().hex[:4]}").strip()
    tenant_id = f"{ws_id}-tenant"
    parts = args.name.strip().split()
    first = parts[0]
    last = " ".join(parts[1:]) or parts[0]
    password = args.password or secrets.token_urlsafe(12)
    user_id = str(uuid.uuid4())
    ts = now_iso()

    print("=== Provisioning plan ===")
    print(f"  Practice (workspace): {args.practice}  (id: {ws_id})")
    print(f"  Tenant id:            {tenant_id}")
    print(f"  Plan / tier:          {args.plan}")
    print(f"  Entitlement:          {product_id}  status=active  payment=manual")
    print(f"  Admin user:           {first} {last} <{email}>  role=admin")
    print(f"  Password:             {'(provided)' if args.password else password}")

    if args.dry_run:
        print("\n(dry-run — nothing written)")
        return

    # --- Pre-flight uniqueness checks ---
    if sb.table("users").select("id").eq("email", email).execute().data:
        fail(f"a user with email {email} already exists", [])
    if sb.table("workspaces").select("id").eq("id", ws_id).execute().data:
        fail(f"workspace id '{ws_id}' is already taken (pass --workspace-id)", [])

    created = []
    try:
        # 1. tenant
        sb.table("tenants").insert({"id": tenant_id, "name": args.practice, "created_at": ts}).execute()
        created.append(f"tenants.id = {tenant_id}")

        # 2. workspace
        sb.table("workspaces").insert({
            "id": ws_id, "tenant_id": tenant_id, "name": args.practice, "slug": ws_id,
            "type": "gp", "organization_name": args.practice, "organization_type": "gp_practice",
            "is_active": True, "subscription_status": "active", "subscription_tier": tier_label,
            "created_at": ts, "updated_at": ts,
        }).execute()
        created.append(f"workspaces.id = {ws_id}")

        # 3. entitlement (chosen tier, manual billing)
        sb.table("practice_entitlements").insert({
            "practice_id": ws_id, "product_id": product_id,
            "status": "active", "payment_status": "manual", "starts_at": ts,
        }).execute()
        created.append(f"practice_entitlements: {ws_id} -> {product_id}")

        # 4. admin user
        sb.table("users").insert({
            "id": user_id, "email": email, "password_hash": get_password_hash(password),
            "first_name": first, "last_name": last, "role": "admin",
            "workspace_id": ws_id, "tenant_id": tenant_id,
            "is_active": True, "is_verified": True, "created_at": ts, "updated_at": ts,
        }).execute()
        created.append(f"users.id = {user_id} ({email})")
    except Exception as e:
        fail(f"provisioning failed: {e}", created)

    # --- Verify the entitlement grants the right capabilities for this tier ---
    # require: all must be present; forbid: none may be present (proves the boundary,
    # e.g. an Essential practice must NOT come out with patient_ehr_basic).
    try:
        caps = set(sb.rpc("practice_capabilities", {"p_practice_id": ws_id}).execute().data or [])
    except Exception:
        caps = set()
    missing = plan["require"] - caps
    leaked = plan["forbid"] & caps
    caps_ok = not missing and not leaked

    print("\n✓ Practice provisioned." if caps_ok else "\n⚠ Practice provisioned, but capability check FAILED.")
    print(f"  Workspace id : {ws_id}")
    print(f"  Plan         : {args.plan}  (entitlement: {product_id})")
    print(f"  Login email  : {email}")
    print(f"  Password     : {password}")
    if caps_ok:
        print(f"  Capabilities : OK — {len(caps)} granted: {', '.join(sorted(caps))}")
    else:
        if missing:
            print(f"  Capabilities : MISSING required {sorted(missing)} — check products/capabilities seed (migration 037).")
        if leaked:
            print(f"  Capabilities : TIER LEAK — {sorted(leaked)} granted but forbidden for '{args.plan}'.")
    print("\n  Share the email + password with the practice. They log in at the app URL,")
    print("  then add their own staff via the in-app user management (admin role).")
    if not caps_ok:
        sys.exit(2)


if __name__ == "__main__":
    main()
