#!/usr/bin/env python3
"""
Local-dev: seed an admin user bound to the exxaro-fd workspace.

Use this to drive the Financial-Disclosure Copilot in the browser against a
local Supabase. NOT for production — the email/password are dev defaults and
no entitlement is provisioned.

Usage:
    cd backend && source .venv/bin/activate
    SUPABASE_URL=http://127.0.0.1:54321 \\
    SUPABASE_SERVICE_KEY=sb_secret_xxx \\
    python scripts/seed_exxaro_user.py

Default credentials (override via flags or env):
    --email     fd@progno-labs.dev
    --password  exxaro-local-2026

After running, log in at http://localhost:3002/login with the printed creds,
then navigate to /mining/financial-disclosure.
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from datetime import datetime, timezone

# Re-use the platform's password hasher.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.api.auth import supabase as sb, get_password_hash  # noqa: E402


WORKSPACE_SLUG = "exxaro-fd"


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed a local-dev admin user for the exxaro-fd workspace.")
    parser.add_argument("--email", default="fd@progno-labs.dev")
    parser.add_argument("--password", default="exxaro-local-2026")
    parser.add_argument("--first-name", default="FD")
    parser.add_argument("--last-name", default="Demo")
    parser.add_argument("--quiet", action="store_true", help="Suppress the credentials banner (useful for CI).")
    args = parser.parse_args()

    # 1. Resolve the exxaro-fd workspace.
    ws_resp = sb.table("workspaces").select("id, tenant_id, name, slug").eq("slug", WORKSPACE_SLUG).limit(1).execute()
    ws_rows = ws_resp.data or []
    if not ws_rows:
        print(
            f"ERROR: workspace slug={WORKSPACE_SLUG!r} not found. Run "
            f"backend/database/mining_seed_workspace.sql against $DATABASE_URL first.",
            file=sys.stderr,
        )
        return 2
    ws = ws_rows[0]
    workspace_id = ws["id"]
    tenant_id = ws["tenant_id"]

    # 2. Find an existing user with this email — re-use if present, else create.
    existing = sb.table("users").select("id, email, workspace_id").eq("email", args.email).limit(1).execute().data or []
    ts = datetime.now(timezone.utc).isoformat()

    if existing:
        user = existing[0]
        user_id = user["id"]
        # If they're already bound somewhere else, repoint them to this workspace + reset the password.
        update = {
            "password_hash": get_password_hash(args.password),
            "workspace_id":  workspace_id,
            "tenant_id":     tenant_id,
            "role":          "admin",
            "is_active":     True,
            "is_verified":   True,
            "updated_at":    ts,
        }
        sb.table("users").update(update).eq("id", user_id).execute()
        action = "updated"
    else:
        user_id = str(uuid.uuid4())
        try:
            sb.table("users").insert({
                "id":            user_id,
                "email":         args.email,
                "password_hash": get_password_hash(args.password),
                "first_name":    args.first_name,
                "last_name":     args.last_name,
                "role":          "admin",
                "workspace_id":  workspace_id,
                "tenant_id":     tenant_id,
                "is_active":     True,
                "is_verified":   True,
                "created_at":    ts,
                "updated_at":    ts,
            }).execute()
            action = "created"
        except Exception as exc:
            print(f"ERROR: failed to insert user: {exc}", file=sys.stderr)
            return 3

    # 3. Best-effort bind via workspace_users (newer multi-workspace table —
    #    auth.list_user_workspaces() queries this first). The local DB only
    #    has workspace_users (not the user_workspaces variant the prod code
    #    queries) — adding a row here is harmless either way.
    try:
        sb.table("workspace_users").upsert({
            "id":           str(uuid.uuid4()),
            "workspace_id": workspace_id,
            "user_id":      user_id,
            "role":         "owner",
            "joined_at":    ts,
        }, on_conflict="workspace_id,user_id").execute()
    except Exception as exc:
        # Not fatal — auth falls back to users.workspace_id (set above).
        print(f"WARN: workspace_users upsert skipped ({exc})", file=sys.stderr)

    if not args.quiet:
        print()
        print(f"✓ User {action} and bound to workspace {ws['name']!r}.")
        print()
        print(f"   Login URL  : http://localhost:3002/login")
        print(f"   Email      : {args.email}")
        print(f"   Password   : {args.password}")
        print(f"   Workspace  : {ws['slug']}  (id: {workspace_id})")
        print(f"   Tenant     : {tenant_id}")
        print()
        print(f"   After login, navigate to: http://localhost:3002/mining/financial-disclosure")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
