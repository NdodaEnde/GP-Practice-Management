#!/usr/bin/env python3
"""
provision_briefing_demo_login.py — Phase 4 PR E.1, the openable-half
login grant. Sibling of scripts/provision_briefing_demo.py; deliberately
SEPARATE from it (see "Independence" below).

PURPOSE (primary, stated, and the ONLY reason this script exists):
grant a human a login into `demo-briefing-workspace-001` so the named
verifier can read the Morning Briefing screen through the real
:3000 -> :8002 chain and watch a real openable source open. That screen
is the first time in the project the Phase-3 safety property becomes
visible to the human it protects; this script provisions the credential
that lets a human reach it, nothing more.

═══════════════════════════════════════════════════════════════════════
LEGITIMACY CONTRACT — read before editing. Enforced at review and, where
it can be, asserted at runtime (not left to convention). Same register as
provision_briefing_demo.py:19-42.

  (1) ONE ROW, ONE TABLE. This script writes EXACTLY ONE row to EXACTLY
      ONE table: a `users` row for workspace `demo-briefing-workspace-001`.
      It performs ZERO clinical-fact writes, ZERO entitlement changes,
      ZERO workspace/tenant changes. The workspace and its
      practice-entitlement rows ALREADY EXIST from the PR B provisioning
      (provision_briefing_demo.py) and this script MUST NOT create,
      modify, or even depend on the specific shape of them. The only
      `.table(...).insert(...)` in this file is the single users insert;
      any `.update(...)`, `.delete(...)`, or any insert into ANY other
      table (entitlements, workspaces, tenants, or ANY clinical-fact
      table) added to THIS script is the scope-creep anti-pattern and
      FAILS REVIEW. If this script appears to NEED such a write to do
      its job, that is the signal the premise is wrong — it must fail
      its own contract and stop, not code around it.

  (2) SINGLE-ROW SCOPE ASSERTED, NOT ASSUMED. After the insert the
      script reads back and asserts that exactly one `users` row exists
      for this email and that it carries the intended workspace/role —
      the same non-vacuity discipline as PR D's teardown asserting the
      registry back to exactly one kind. A write that cannot be verified
      to be exactly the single intended row is a failure, reported as
      such.

  (3) DEMO CREDENTIAL, NOT A SECRET, NOT A PRODUCTION ACCOUNT. This is a
      login into a DEMONSTRATION workspace shown to prospecting doctors.
      The password is the established clearly-marked demo credential
      (`password123`, the exact pattern of the seeded
      admin@/validator@/uploader@surgiscan.com accounts —
      init_users_table.py:64-100). It is intentionally NOT a strong
      secret: a production-grade secret here would falsely imply
      production access. This account carries NO production meaning; a
      future reader must not mistake it for a real user's credential or
      for a security defect. It is a demo door into a demo room.

  (4) MINIMUM ROLE. The role is `validator` — a NON-admin role. Capability
      scope (incl. `clinical_query`, which the briefing screen gates on)
      is hydrated AT LOGIN from the WORKSPACE's entitlements, NOT from the
      role (app/api/auth.py:346 — `practice_capabilities(workspace_id)`).
      So this account's authority is bounded ENTIRELY by
      `demo-briefing-workspace-001`'s pre-existing PR-B
      `platform_professional` entitlement, which this script neither
      branches on nor modifies. The role is chosen non-admin purely to
      withhold the admin-only surfaces (app/api/auth.py:247;
      Layout.jsx adminNav role gate). The grant is exactly: "a human may
      authenticate as a member of an already-entitled demonstration
      workspace, and is then bounded by that workspace's existing
      entitlements" — nothing broader.

  (5) RE-RUNNABLE SAFE NO-OP. Deterministic identity; if the users row
      already exists (looked up by email) the script REPORTS and EXITS 0
      WITHOUT rewriting — idempotent, never a silent overwrite. Same
      property as provision_briefing_demo.py:81-84.

  (6) INDEPENDENCE. This script does NOT import, call, or trigger
      provision_briefing_demo.py, and that script does not trigger this
      one. The login grant and the openable-corpus re-assertion are TWO
      separate shared-state writes, each idempotent, each reporting its
      own result, intentionally NOT coupled in code — the same isolation
      reasoning as PR D's per-(workspace_id, kind) transaction
      granularity: a failure in one must not half-complete the other.
      Run order does not matter (both idempotent); run them as two
      executions.
═══════════════════════════════════════════════════════════════════════

Usage (the shared-state write is the operator's hand, like every
migration and like provision_briefing_demo.py):
  cd backend && PYTHONPATH=. .venv/bin/python scripts/provision_briefing_demo_login.py
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from passlib.context import CryptContext  # noqa: E402
from supabase import create_client  # noqa: E402

# ── Deterministic identity (re-runnable; idempotency is by email) ──────────
WORKSPACE = "demo-briefing-workspace-001"
TENANT = "demo-briefing-tenant-001"  # the tenant PR B used for this WS
EMAIL = "briefing-demo@surgiscan.com"
PASSWORD = "password123"  # contract (3): the established demo credential
ROLE = "validator"  # contract (4): non-admin; capabilities are WS-derived
USER_ID = "b1efed00-0000-4000-8000-000000000001"  # fixed, deterministic

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
    if not url or not key:
        print("❌ Missing SUPABASE_URL / SUPABASE_SERVICE_KEY in backend/.env")
        sys.exit(1)
    return create_client(url, key)


def main() -> None:
    sb = _client()

    # ── Contract (5): re-runnable safe no-op. Look up by email FIRST. ──────
    existing = (
        sb.table("users").select("id, email, workspace_id, role")
        .eq("email", EMAIL).execute()
    )
    rows = getattr(existing, "data", None) or []
    if rows:
        r = rows[0]
        print(
            f"ℹ️  Login already provisioned — no-op. "
            f"email={r.get('email')} workspace={r.get('workspace_id')} "
            f"role={r.get('role')} (rows={len(rows)})"
        )
        # Even on the no-op path, assert the single-row scope (contract 2).
        if len(rows) != 1:
            print(f"❌ Expected exactly 1 users row for {EMAIL}, found {len(rows)}.")
            sys.exit(1)
        print("✅ Safe no-op. Nothing written.")
        return

    # ── Contract (1): the ONLY write in this script — one users row. ──────
    record = {
        "id": USER_ID,
        "email": EMAIL,
        "password_hash": pwd_context.hash(PASSWORD),
        "first_name": "Briefing",
        "last_name": "Demo",
        "role": ROLE,
        "workspace_id": WORKSPACE,
        "tenant_id": TENANT,
        "is_active": True,
        "is_verified": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    result = sb.table("users").insert(record).execute()
    if not (getattr(result, "data", None) or []):
        print(f"❌ Insert returned no row for {EMAIL}; aborting.")
        sys.exit(1)

    # ── Contract (2): single-row scope ASSERTED, not assumed. ─────────────
    back = (
        sb.table("users").select("id, email, workspace_id, role, is_active")
        .eq("email", EMAIL).execute()
    )
    back_rows = getattr(back, "data", None) or []
    if len(back_rows) != 1:
        print(
            f"❌ Post-write assertion failed: expected exactly 1 users row "
            f"for {EMAIL}, found {len(back_rows)}. NOT a clean single-row write."
        )
        sys.exit(1)
    w = back_rows[0]
    if w.get("workspace_id") != WORKSPACE or w.get("role") != ROLE:
        print(
            f"❌ Post-write assertion failed: row is "
            f"workspace={w.get('workspace_id')} role={w.get('role')}, "
            f"expected {WORKSPACE}/{ROLE}."
        )
        sys.exit(1)

    print("=" * 64)
    print("✅ PR E.1 login granted — ONE users row, verified.")
    print("=" * 64)
    print(f"   email      : {EMAIL}")
    print(f"   password   : {PASSWORD}   (demo credential — no production meaning)")
    print(f"   workspace  : {WORKSPACE}")
    print(f"   role       : {ROLE}   (non-admin; capabilities are workspace-derived)")
    print("   wrote      : exactly 1 row to exactly 1 table (users)")
    print("   touched    : no entitlements, no workspace/tenant, no clinical facts")
    print("=" * 64)


if __name__ == "__main__":
    main()
