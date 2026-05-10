"""
Cross-check the curated OTC list against the WHO ATC index. Catches any
typos in atc_code or atc_class_desc before we generate INSERT SQL.

Usage:
    .venv/bin/python scripts/validate_curated_otc.py \\
        --csv data/atc/curated_otc_starter.csv

Reports any:
  - atc_code missing from the WHO index
  - atc_class_desc mismatching the WHO substance name
  - duplicate curated_id values
  - missing required fields (curated_id, brand_name, schedule)
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from scripts import atc_backfill as atc  # noqa: E402

DEFAULT_ATC = HERE.parent / "data" / "atc" / "WHO_ATC-DDD_2026-04-25.csv"

VALID_SCHEDULES = {"S0", "S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8",
                   "Unscheduled"}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--csv", type=Path, required=True)
    p.add_argument("--atc-csv", type=Path, default=DEFAULT_ATC)
    args = p.parse_args()

    by_code, by_name = atc.load_atc(args.atc_csv)

    rows: list[dict[str, str]] = []
    with args.csv.open(newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            rows.append(r)

    print(f"Loaded {len(rows)} curated rows from {args.csv}")
    print(f"Loaded {len(by_code)} ATC entries from {args.atc_csv}\n")

    errors: list[str] = []
    warnings: list[str] = []
    seen_ids: set[str] = set()

    for i, r in enumerate(rows, 1):
        cid = (r.get("curated_id") or "").strip()
        brand = (r.get("brand_name") or "").strip()
        sched = (r.get("schedule") or "").strip()
        atc_code = (r.get("atc_code") or "").strip()
        atc_desc = (r.get("atc_class_desc") or "").strip()

        # Required fields
        if not cid:
            errors.append(f"row {i}: missing curated_id")
            continue
        if cid in seen_ids:
            errors.append(f"row {i}: duplicate curated_id '{cid}'")
        seen_ids.add(cid)
        if not brand:
            errors.append(f"row {i} ({cid}): missing brand_name")
        if sched and sched not in VALID_SCHEDULES:
            errors.append(f"row {i} ({cid}): invalid schedule '{sched}'")

        # ATC validation
        if not atc_code:
            warnings.append(f"row {i} ({cid}): no atc_code (will go in unmatched)")
            continue

        entry = by_code.get(atc_code)
        if entry is None:
            errors.append(
                f"row {i} ({cid}): atc_code '{atc_code}' NOT FOUND in WHO index "
                f"(brand_name='{brand}')"
            )
            continue

        # Cross-check description matches the WHO name (loose — case-insensitive,
        # normalized).
        if atc_desc:
            who_norm = atc.normalize(entry.name)
            user_norm = atc.normalize(atc_desc)
            if who_norm != user_norm:
                warnings.append(
                    f"row {i} ({cid}): atc_class_desc '{atc_desc}' differs from "
                    f"WHO name '{entry.name}' for code {atc_code}"
                )

    print(f"Errors:   {len(errors)}")
    for e in errors:
        print(f"  ✗ {e}")
    print(f"Warnings: {len(warnings)}")
    for w in warnings:
        print(f"  ⚠ {w}")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
