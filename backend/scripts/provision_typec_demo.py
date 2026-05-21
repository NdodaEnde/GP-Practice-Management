#!/usr/bin/env python3
"""
provision_typec_demo.py — one-shot Type C demo workspace provisioner.

Creates a tenant, workspace, admin user, and a single module_digitisation
entitlement so we can sign in as a Type C doctor and verify the
capability-filtered nav + login redirect end-to-end.

Idempotent: safe to re-run (uses upserts / "if not exists" semantics).

Run from backend/ directory:
    .venv/bin/python scripts/provision_typec_demo.py
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv
from passlib.context import CryptContext
from supabase import create_client

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

TENANT_ID = "typec-tenant-001"
WORKSPACE_ID = "typec-workspace-001"
WORKSPACE_NAME = "Acme Family Practice"
USER_EMAIL = "typec@surgiscan.com"
USER_PASSWORD = "password123"
USER_FIRST = "Patel"
USER_LAST = "Nair"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def main() -> None:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        sys.exit("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY in backend/.env.")
    client = create_client(url, key)

    now = datetime.now(timezone.utc)

    # 1. Tenant
    existing = client.table("tenants").select("id").eq("id", TENANT_ID).execute()
    if not existing.data:
        client.table("tenants").insert({
            "id": TENANT_ID,
            "name": "Type C Demo Tenant",
            "created_at": now.isoformat(),
        }).execute()
        print(f"✓ Created tenant {TENANT_ID}")
    else:
        print(f"• Tenant {TENANT_ID} already exists")

    # 2. Workspace
    existing = client.table("workspaces").select("id").eq("id", WORKSPACE_ID).execute()
    if not existing.data:
        client.table("workspaces").insert({
            "id": WORKSPACE_ID,
            "tenant_id": TENANT_ID,
            "name": WORKSPACE_NAME,
            "type": "gp",
            "created_at": now.isoformat(),
        }).execute()
        print(f"✓ Created workspace {WORKSPACE_ID}")
    else:
        print(f"• Workspace {WORKSPACE_ID} already exists")

    # 3. User (admin role inside the Type C workspace)
    existing = client.table("users").select("id, email").eq("email", USER_EMAIL).execute()
    if not existing.data:
        client.table("users").insert({
            "email": USER_EMAIL,
            "password_hash": pwd_context.hash(USER_PASSWORD),
            "first_name": USER_FIRST,
            "last_name": USER_LAST,
            "role": "admin",
            "workspace_id": WORKSPACE_ID,
            "tenant_id": TENANT_ID,
            "is_active": True,
            "is_verified": True,
            "created_at": now.isoformat(),
        }).execute()
        print(f"✓ Created user {USER_EMAIL} (password: {USER_PASSWORD})")
    else:
        print(f"• User {USER_EMAIL} already exists")

    # 4. Entitlement: module_digitisation only (Type C — no Practice Platform)
    existing = (
        client.table("practice_entitlements")
        .select("id")
        .eq("practice_id", WORKSPACE_ID)
        .eq("product_id", "module_digitisation")
        .eq("status", "active")
        .execute()
    )
    if not existing.data:
        client.table("practice_entitlements").insert({
            "practice_id": WORKSPACE_ID,
            "product_id": "module_digitisation",
            "status": "active",
            "payment_status": "manual",
            "is_founder_pricing": True,
            "founder_protection_until": (now + relativedelta(months=12)).isoformat(),
            "starts_at": now.isoformat(),
            "ends_at": None,  # open-ended for demo
            "metadata": {"provisioned_via": "scripts/provision_typec_demo.py"},
        }).execute()
        print("✓ Provisioned module_digitisation entitlement")
    else:
        print("• module_digitisation entitlement already active")

    print()
    print("=" * 60)
    print("Type C demo workspace ready.")
    print(f"  Login:    {USER_EMAIL}")
    print(f"  Password: {USER_PASSWORD}")
    print(f"  Workspace: {WORKSPACE_NAME} ({WORKSPACE_ID})")
    print("=" * 60)


if __name__ == "__main__":
    main()
