#!/usr/bin/env python
"""
reset_user_password.py — concierge fallback for a locked-out user.

This is the v1 stand-in for a self-service forgot-password email flow (which is
intentionally deferred — see DEPLOYMENT.md / ONBOARDING_RUNBOOK.md). Use when a
customer locks themselves out: regenerate a strong random password, write the
new bcrypt hash to their row, and print the new password ONCE so you can send
it to them over a secure channel.

Run:
  PYTHONPATH=. ./.venv/bin/python scripts/reset_user_password.py \
      --email dr@wellness.co.za \
      [--password 'StrongPass123']     # omit to auto-generate
      [--dry-run]
"""
import argparse
import secrets
import sys
from datetime import datetime, timezone

import os
from dotenv import load_dotenv
_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_BACKEND, ".env"))

from app.api.auth import supabase as sb, get_password_hash  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="Concierge password reset for a single user.")
    ap.add_argument("--email", required=True, help="The user's login email")
    ap.add_argument("--password", help="Explicit new password (auto-generated if omitted)")
    ap.add_argument("--dry-run", action="store_true", help="Show what would change; write nothing")
    args = ap.parse_args()

    email = args.email.strip().lower()
    res = sb.table("users").select("id, email, workspace_id, is_active").eq("email", email).execute()
    if not res.data:
        print(f"\n✗ No user with email {email}")
        sys.exit(1)
    user = res.data[0]
    new_password = args.password or secrets.token_urlsafe(12)

    print("=== Reset plan ===")
    print(f"  User:        {email}  (id: {user['id']})")
    print(f"  Workspace:   {user.get('workspace_id')}")
    print(f"  Active:      {user.get('is_active')}")
    print(f"  New password: {'(provided)' if args.password else new_password}")

    if args.dry_run:
        print("\n(dry-run — nothing written)")
        return

    sb.table("users").update({
        "password_hash": get_password_hash(new_password),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", user["id"]).execute()

    print("\n✓ Password reset.")
    print(f"  Email:       {email}")
    print(f"  Password:    {new_password}")
    print("\n  Send the password to the user over a SECURE channel (not email-in-clear).")
    print("  Ask them to log in and immediately rotate it via Settings -> Change Password.")


if __name__ == "__main__":
    main()
