#!/usr/bin/env python3
"""
Download Exxaro's public reports for FY2022–FY2025 into the FD source set.

Resolves the plan's open question #1 (which PDFs feed the ingest pipeline +
the gold set). Each report is fetched from
investor.exxaro.com/integrated-reports{year}/pdf/..., verified to start with
the %PDF magic, sha256-hashed, and written to:

    backend/data/exxaro_source_set/{doc_type}/fy{year}/exxaro-{type}-{year}.pdf

Re-runnable: existing files are skipped unless --force is passed.

Usage:
    cd backend && source .venv/bin/activate
    python scripts/download_exxaro_reports.py [--year 2024] [--type integrated] [--force]
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import urllib.request
from pathlib import Path
from typing import Dict, Iterable, List, NamedTuple


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = REPO_ROOT / "data" / "exxaro_source_set"
BASE = "https://investor.exxaro.com/integrated-reports{year}/pdf"


class Report(NamedTuple):
    """One PDF to fetch."""
    year: int
    doc_type: str         # 'integrated' | 'sustainability' | 'investor'
    remote_name: str      # filename at the IR portal
    local_name: str       # canonical filename in our tree
    doc_id: str           # used by the ingest pipeline

    @property
    def url(self) -> str:
        return f"{BASE.format(year=self.year)}/{self.remote_name}"

    @property
    def local_path(self) -> Path:
        return DATA_ROOT / self.doc_type / f"fy{self.year}" / self.local_name


# Confirmed URL patterns via WebFetch against investor.exxaro.com on 2026-06-01.
# AFS file names are inconsistent across years (full-afs.pdf for 2022–2024,
# exxaro-2025-afs.pdf for 2025); same for the 2025 ESG file.
REPORTS: List[Report] = [
    # FY2022
    Report(2022, "integrated",     "exxaro-ir-2022.pdf",       "exxaro-ir-2022.pdf",  "EXXARO-IR-2022"),
    Report(2022, "sustainability", "exxaro-esg-2022.pdf",      "exxaro-esg-2022.pdf", "EXXARO-ESG-2022"),
    Report(2022, "investor",       "full-afs.pdf",             "exxaro-afs-2022.pdf", "EXXARO-AFS-2022"),
    # FY2023
    Report(2023, "integrated",     "exxaro-ir-2023.pdf",       "exxaro-ir-2023.pdf",  "EXXARO-IR-2023"),
    Report(2023, "sustainability", "exxaro-esg-2023.pdf",      "exxaro-esg-2023.pdf", "EXXARO-ESG-2023"),
    Report(2023, "investor",       "full-afs.pdf",             "exxaro-afs-2023.pdf", "EXXARO-AFS-2023"),
    # FY2024
    Report(2024, "integrated",     "exxaro-ir-2024.pdf",       "exxaro-ir-2024.pdf",  "EXXARO-IR-2024"),
    Report(2024, "sustainability", "exxaro-esg-2024.pdf",      "exxaro-esg-2024.pdf", "EXXARO-ESG-2024"),
    Report(2024, "investor",       "full-afs.pdf",             "exxaro-afs-2024.pdf", "EXXARO-AFS-2024"),
    # FY2025
    Report(2025, "integrated",     "exxaro-ir-2025.pdf",       "exxaro-ir-2025.pdf",  "EXXARO-IR-2025"),
    Report(2025, "sustainability", "exx-2025-esg-report.pdf",  "exxaro-esg-2025.pdf", "EXXARO-ESG-2025"),
    Report(2025, "investor",       "exxaro-2025-afs.pdf",      "exxaro-afs-2025.pdf", "EXXARO-AFS-2025"),
]

# Per-chapter splits of the Integrated Report — much smaller, focused, and
# come in well under the ADE 100-page limit. Use these for cost-controlled
# ingest when the full IR is too expensive to extract.
#
# We file them under doc_type='integrated' so the mapper handles them the
# same way; the doc_id encodes which chapter. The two we use most:
#   * strategically-positioning-the-business-for-growth.pdf — capital
#     allocation + transition strategy (powers Q3 strategic_narratives).
#   * creating-value.pdf — per-segment financial / operational results
#     (powers Q1 + Q4 financial_facts).
CHAPTERS: List[Report] = [
    # FY2024 — the spec's reference year.
    Report(2024, "integrated", "strategically-positioning-the-business-for-growth.pdf",
           "exxaro-ir-2024-chapter-strategy.pdf",     "EXXARO-IR-2024-CH-STRATEGY"),
    Report(2024, "integrated", "creating-value.pdf",
           "exxaro-ir-2024-chapter-performance.pdf",  "EXXARO-IR-2024-CH-PERFORMANCE"),
]


def fetch(report: Report, force: bool = False) -> Dict[str, object]:
    """
    Download one report. Returns a manifest entry.

    Raises if the remote responds 2xx but the bytes don't start with %PDF —
    that's the most common failure mode (CDN redirects to a wrapper page on
    404). Hashes the body so we can pin specific versions later (gold set
    capture date is supposed to identify *which* PDF the row came from).
    """
    target = report.local_path
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists() and not force:
        body = target.read_bytes()
        return {
            "year": report.year, "doc_type": report.doc_type, "doc_id": report.doc_id,
            "url": report.url, "path": str(target.relative_to(REPO_ROOT)),
            "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(),
            "skipped": True,
        }

    req = urllib.request.Request(
        report.url,
        headers={"User-Agent": "Mozilla/5.0 (SurgiScan FD ingest; contact: fd@progno-labs.dev)"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = resp.read()
        status = resp.status
    if status != 200:
        raise RuntimeError(f"{report.url} → HTTP {status}")
    if not body.startswith(b"%PDF"):
        head = body[:80].decode("ascii", errors="replace")
        raise RuntimeError(f"{report.url} did not return a PDF (head: {head!r})")

    target.write_bytes(body)
    return {
        "year": report.year, "doc_type": report.doc_type, "doc_id": report.doc_id,
        "url": report.url, "path": str(target.relative_to(REPO_ROOT)),
        "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(),
        "skipped": False,
    }


def filter_reports(reports: Iterable[Report], year: int | None, doc_type: str | None) -> List[Report]:
    return [r for r in reports if (year is None or r.year == year) and (doc_type is None or r.doc_type == doc_type)]


def main() -> int:
    p = argparse.ArgumentParser(description="Download Exxaro public reports for the FD ingest pipeline.")
    p.add_argument("--year", type=int, choices=[2022, 2023, 2024, 2025], default=None)
    p.add_argument("--type", choices=["integrated", "sustainability", "investor"], default=None)
    p.add_argument("--force", action="store_true", help="Re-download even if the file is already present.")
    p.add_argument(
        "--chapters", action="store_true",
        help="Download per-chapter splits of the Integrated Report instead of the full reports. "
             "Each chapter is ~20-40 pages — fits under the ADE 100-page limit without splitting.",
    )
    args = p.parse_args()

    source = CHAPTERS if args.chapters else REPORTS
    selected = filter_reports(source, args.year, args.type)
    if not selected:
        print("No reports matched the filter.", file=sys.stderr)
        return 2

    print(f"Fetching {len(selected)} report(s) into {DATA_ROOT.relative_to(REPO_ROOT)}/")
    manifest: List[Dict[str, object]] = []
    failed: List[str] = []
    for r in selected:
        try:
            entry = fetch(r, force=args.force)
            mb = entry["bytes"] / (1024 * 1024)
            tag = "SKIP" if entry["skipped"] else " GET"
            print(f"  {tag}  {r.year}/{r.doc_type:14s}  {mb:6.1f} MB  sha256={entry['sha256'][:12]}…  {r.url}")
            manifest.append(entry)
        except Exception as exc:
            print(f"  FAIL {r.year}/{r.doc_type:14s}  {r.url}\n         → {exc}", file=sys.stderr)
            failed.append(f"{r.year}/{r.doc_type}")

    # Write a manifest for later reproducibility / gold-set provenance.
    manifest_path = DATA_ROOT / "manifest.json"
    import json
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True))
    print(f"\nManifest: {manifest_path.relative_to(REPO_ROOT)}  ({len(manifest)} entries)")
    if failed:
        print(f"\nFailures: {len(failed)}: {', '.join(failed)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
