#!/usr/bin/env python3
"""
provision_practice.py — manual entitlement provisioning CLI (Phase 1).

This is intentionally a script, not an admin panel. The user is the
provisioning UI for the first 10–20 customers. When manual provisioning
takes more than ~1 hour/week of ops time, build the admin panel (Phase 5).

Reads SUPABASE_URL + SUPABASE_SERVICE_KEY from backend/.env so it can run
from a laptop. The service key bypasses RLS — keep this script founder-only.

Usage examples:

    # Provision Practice Essential (Small band, founder pricing) for a practice
    python scripts/provision_practice.py \\
        --practice-id 11111111-2222-3333-4444-555555555555 \\
        --product-id platform_essential \\
        --pricing-band-id platform_essential_small \\
        --paystack-sub-code SUB_xxxxx \\
        --paystack-plan-code PLN_pe_small_founder \\
        --founder-pricing \\
        --duration-months 12

    # Provision Module Digitisation (no banding — pricing_band_id omitted)
    python scripts/provision_practice.py \\
        --practice-id 11111111-2222-3333-4444-555555555555 \\
        --product-id module_digitisation \\
        --paystack-sub-code SUB_yyyyy \\
        --paystack-plan-code PLN_dig_starter_founder

    # Grant a grandfathered customer full legacy access (no Paystack)
    python scripts/provision_practice.py \\
        --practice-id 11111111-2222-3333-4444-555555555555 \\
        --product-id legacy_full_access_grant \\
        --payment-status manual

    # List active entitlements for a practice
    python scripts/provision_practice.py \\
        --practice-id 11111111-2222-3333-4444-555555555555 \\
        --list

The script always prints the entitlement row(s) it just created (or the
existing list, in --list mode) so the operator has an audit trail.
"""

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional  # Python 3.9-compatible (no PEP 604 unions)

from dateutil.relativedelta import relativedelta  # python-dateutil; standard with most Python envs
from dotenv import load_dotenv
from supabase import create_client, Client

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


def supabase_client() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        sys.exit("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY in backend/.env.")
    return create_client(url, key)


def list_entitlements(client: Client, practice_id: str) -> None:
    res = (
        client.table("practice_entitlements")
        .select("id, product_id, status, payment_status, paystack_plan_code, "
                "is_founder_pricing, founder_protection_until, starts_at, ends_at")
        .eq("practice_id", practice_id)
        .order("created_at", desc=True)
        .execute()
    )
    if not res.data:
        print(f"No entitlements found for practice {practice_id}.")
        return
    print(f"Found {len(res.data)} entitlement(s) for practice {practice_id}:\n")
    for row in res.data:
        founder_marker = " (founder)" if row.get("is_founder_pricing") else ""
        print(f"  • {row['product_id']:32s} status={row['status']:10s} "
              f"payment={row['payment_status']:10s}{founder_marker}")
        print(f"    starts={row['starts_at']}  ends={row.get('ends_at') or 'open-ended'}")
        if row.get("founder_protection_until"):
            print(f"    founder_protection_until={row['founder_protection_until']}")
        if row.get("paystack_plan_code"):
            print(f"    paystack_plan={row['paystack_plan_code']}")
        print()


def provision(
    client: Client,
    practice_id: str,
    product_id: str,
    pricing_band_id: Optional[str],
    paystack_sub_code: Optional[str],
    paystack_plan_code: Optional[str],
    founder_pricing: bool,
    payment_status: str,
    duration_months: int,
) -> None:
    now = datetime.now(timezone.utc)
    ends_at = now + relativedelta(months=duration_months) if duration_months > 0 else None
    founder_protection_until = (
        now + relativedelta(months=12) if founder_pricing else None
    )

    record = {
        "practice_id": practice_id,
        "product_id": product_id,
        "status": "active",
        "payment_status": payment_status,
        "paystack_subscription_code": paystack_sub_code,
        "paystack_plan_code": paystack_plan_code,
        "pricing_band_id": pricing_band_id,
        "is_founder_pricing": founder_pricing,
        "founder_protection_until": founder_protection_until.isoformat() if founder_protection_until else None,
        "starts_at": now.isoformat(),
        "ends_at": ends_at.isoformat() if ends_at else None,
        "metadata": {"provisioned_via": "scripts/provision_practice.py"},
    }
    res = client.table("practice_entitlements").insert(record).execute()
    if not res.data:
        sys.exit(f"Insert returned no rows. Response: {res}")
    row = res.data[0]
    print("✓ Entitlement created:")
    print(f"  id={row['id']}")
    print(f"  practice={row['practice_id']}  product={row['product_id']}")
    print(f"  status={row['status']}  payment_status={row['payment_status']}")
    print(f"  starts={row['starts_at']}  ends={row.get('ends_at') or 'open-ended'}")
    if founder_pricing:
        print(f"  founder_protection_until={row['founder_protection_until']}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--practice-id", required=True, help="ID of the workspaces row (the practice). e.g. demo-gp-workspace-001.")
    parser.add_argument("--list", action="store_true", help="List active entitlements for the practice; ignore other args.")
    parser.add_argument("--product-id", help="e.g. platform_essential, module_digitisation, foundation_bundle, legacy_full_access_grant.")
    parser.add_argument("--pricing-band-id", default=None, help="Required for Practice Platform tiers; omit for modules.")
    parser.add_argument("--paystack-sub-code", default=None, help="Paystack subscription code (SUB_xxx). Optional when payment-status is manual.")
    parser.add_argument("--paystack-plan-code", default=None, help="Paystack plan code (PLN_xxx). Resolves to founder vs list.")
    parser.add_argument("--founder-pricing", action="store_true", help="Tag entitlement as founder-priced; sets founder_protection_until = +12mo.")
    parser.add_argument("--payment-status", default="paid", choices=["paid", "pending", "attention", "failed", "manual"],
                        help="Initial payment status. Use 'manual' for invoiced-outside-Paystack customers.")
    parser.add_argument("--duration-months", type=int, default=1,
                        help="Sets ends_at = now + N months. 0 = open-ended (NULL); webhook charge.success extends in production.")
    args = parser.parse_args()

    client = supabase_client()
    if args.list:
        list_entitlements(client, args.practice_id)
        return

    if not args.product_id:
        sys.exit("--product-id is required (omit only when using --list).")

    provision(
        client=client,
        practice_id=args.practice_id,
        product_id=args.product_id,
        pricing_band_id=args.pricing_band_id,
        paystack_sub_code=args.paystack_sub_code,
        paystack_plan_code=args.paystack_plan_code,
        founder_pricing=args.founder_pricing,
        payment_status=args.payment_status,
        duration_months=args.duration_months,
    )


if __name__ == "__main__":
    main()
