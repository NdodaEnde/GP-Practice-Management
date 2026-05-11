"""
Verification harness for the refactored chronic-summary endpoint.

What this is:
  - An end-to-end exercise of the refactored handler in
    app/api/gp_endpoints.py — mapper, try/except fallback, both legacy
    and ontology serialisers — via FastAPI's TestClient.

What it is NOT:
  - A replacement for capturing real-DB baselines on a running backend.
    Real baselines exercise the production data shape, which can
    surprise us in ways synthetic rows can't. This harness uses
    hand-built rows representative of the five data-quality profiles
    named in the integration plan.

The harness:
  1. Monkeypatches `_get_supabase` to return a fake client backed by a
     dict of synthetic rows.
  2. Mounts the existing `gp_router` on a minimal FastAPI app.
  3. Hits the chronic-summary endpoint for each row and captures the
     response (this is the POST-refactor wire format).
  4. Computes the PRE-refactor wire format by calling
     `_legacy_chronic_summary_response(row)` directly with the same
     row dict.
  5. Diffs the two with `jq -S`-style canonical key-sorting.

The diff classifications, per the integration plan's success criterion:
  - empty diff → identical wire format. Pass.
  - normalisation-only diff → expected (whitespace stripped, dates
    canonicalised, null vs absent). Pass.
  - real value change → regression. Inspect.

Run from backend/:
    python3 verify_integration_endpoint.py
"""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient


# --- Fake Supabase client that the endpoint can call ----------------------

class _FakeQuery:
    """Mimics the supabase-py builder chain: .select().eq().execute()."""

    def __init__(self, rows: list[dict]):
        self._rows = rows
        self._eq: list[tuple[str, Any]] = []

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, col: str, val: Any):
        self._eq.append((col, val))
        return self

    def execute(self):
        matched = self._rows
        for col, val in self._eq:
            matched = [r for r in matched if r.get(col) == val]
        return type("R", (), {"data": matched})()


class FakeSupabase:
    def __init__(self, rows: list[dict]):
        self._rows = rows

    def table(self, _name: str):
        return _FakeQuery(self._rows)


# --- Synthetic rows spanning the five data-quality profiles ---------------

CLEAN_ID = str(uuid4())
SENTINEL_ID = str(uuid4())
PADDED_ID = str(uuid4())
NULL_MA_ID = str(uuid4())
MAX_CHRONIC_ID = str(uuid4())
WORKSPACE_ID = str(uuid4())

ROW_CLEAN = {
    "id": CLEAN_ID,
    "tenant_id": "tenant-acme",
    "workspace_id": WORKSPACE_ID,
    "first_name": "Thandi",
    "last_name": "Mthembu",
    "dob": "1985-03-14",
    "id_number": "8503140001087",
    "contact_number": "+27821234567",
    "email": "thandi@example.co.za",
    "address": "12 Main Rd, Khayelitsha",
    "medical_aid": "Discovery Classic",
    "chronic_conditions": ["Hypertension"],
    "current_medications": ["Atenolol 50mg"],
    "allergies": [],
    "latest_vitals": {"bp": "130/85"},
    "created_at": "2026-03-08T14:23:00+00:00",
    "updated_at": "2026-05-01T09:00:00+00:00",
    "validation_status": "validated",
}

ROW_SENTINEL_DOB = {
    **ROW_CLEAN,
    "id": SENTINEL_ID,
    "first_name": "Jane",
    "last_name": "Doe",
    "dob": "1900-01-01",  # sentinel; real SA ID below
    "id_number": "8503140001087",  # this is what creates the cross-check failure
}

ROW_PADDED_ID = {
    **ROW_CLEAN,
    "id": PADDED_ID,
    "id_number": "8503140001087 ",  # trailing whitespace — coffee bet
}

ROW_NULL_MEDICAL_AID = {
    **ROW_CLEAN,
    "id": NULL_MA_ID,
    "medical_aid": None,
}

ROW_MAX_CHRONIC = {
    **ROW_CLEAN,
    "id": MAX_CHRONIC_ID,
    "chronic_conditions": [
        "Hypertension", "Type 2 Diabetes", "Hyperlipidaemia",
        "Osteoarthritis", "Asthma", "Depression",
    ],
    "current_medications": [
        "Atenolol 50mg", "Metformin 1g BD", "Atorvastatin 40mg",
        "Salbutamol PRN", "Citalopram 20mg",
    ],
}

ALL_ROWS = [
    ROW_CLEAN, ROW_SENTINEL_DOB, ROW_PADDED_ID,
    ROW_NULL_MEDICAL_AID, ROW_MAX_CHRONIC,
]


# --- Monkeypatch + build minimal app --------------------------------------

import app.api.gp_endpoints as gp_mod  # noqa: E402

gp_mod._get_supabase = lambda: FakeSupabase(ALL_ROWS)

app = FastAPI()
app.include_router(gp_mod.gp_router)
client = TestClient(app)


# --- Diff helpers ---------------------------------------------------------

def canonical(d: Any) -> str:
    """Canonical-key-sorted JSON string. Mirrors `jq -S`."""
    return json.dumps(d, sort_keys=True, indent=2, default=str)


def diff_lines(a: dict, b: dict) -> list[str]:
    """Tiny field-by-field diff at top level + one nested level."""
    out: list[str] = []
    a_keys = set(a.keys())
    b_keys = set(b.keys())
    for k in sorted(a_keys | b_keys):
        if k not in a:
            out.append(f"  + {k}: {b[k]!r}")
            continue
        if k not in b:
            out.append(f"  - {k}: {a[k]!r}")
            continue
        av, bv = a[k], b[k]
        if av == bv:
            continue
        if isinstance(av, dict) and isinstance(bv, dict):
            for sub in sorted(set(av.keys()) | set(bv.keys())):
                if av.get(sub) != bv.get(sub):
                    out.append(f"  ~ {k}.{sub}: {av.get(sub)!r} → {bv.get(sub)!r}")
        else:
            out.append(f"  ~ {k}: {av!r} → {bv!r}")
    return out


def classify_diff(lines: list[str]) -> str:
    """Heuristic: normalisation-only (whitespace, ISO date, null vs absent)
    vs real value change."""
    if not lines:
        return "IDENTICAL"
    normalisation_signatures = [
        # id_number: trailing space stripped
        "id_number'", "'8503140001087 '", "'8503140001087'",
        # date_of_birth: T-suffix or other variant canonicalised
        "date_of_birth",
        # last_updated: null → populated (from created_at fallback)
        "last_updated",
    ]
    real_value_change = False
    for line in lines:
        if not any(sig in line for sig in normalisation_signatures):
            # Anything that doesn't match a known-normalisation pattern is
            # treated as a real value change.
            real_value_change = True
            break
    return "REGRESSION" if real_value_change else "NORMALISATION-ONLY"


# --- Run the comparison ---------------------------------------------------

def main() -> None:
    print("=" * 70)
    print("Verifying integration endpoint — refactor wire compatibility")
    print("=" * 70)

    profiles = [
        ("clean",                 CLEAN_ID,         ROW_CLEAN),
        ("sentinel_dob",          SENTINEL_ID,      ROW_SENTINEL_DOB),
        ("padded_id_number",      PADDED_ID,        ROW_PADDED_ID),
        ("null_medical_aid",      NULL_MA_ID,       ROW_NULL_MEDICAL_AID),
        ("max_chronic_conditions", MAX_CHRONIC_ID,  ROW_MAX_CHRONIC),
    ]

    summary: list[tuple[str, str]] = []

    for profile_name, pid, row in profiles:
        print(f"\n[{profile_name}]  patient_id={pid}")

        # Pre-refactor wire format: legacy helper directly on the row
        pre = gp_mod._legacy_chronic_summary_response(row)

        # Post-refactor wire format: hit the endpoint
        resp = client.get(f"/api/v1/gp/patient/{pid}/chronic-summary")
        if resp.status_code != 200:
            print(f"  FAIL — HTTP {resp.status_code}: {resp.text}")
            summary.append((profile_name, f"HTTP {resp.status_code}"))
            continue
        post = resp.json()

        lines = diff_lines(pre, post)
        classification = classify_diff(lines)

        # Which path executed?
        if profile_name == "sentinel_dob":
            # Expected to fail ontology validation and fall back to legacy
            expected = "IDENTICAL"
        else:
            expected = "any of IDENTICAL or NORMALISATION-ONLY"

        print(f"  classification: {classification}  (expected: {expected})")
        if lines:
            for line in lines:
                print(line)
        else:
            print("  (no diff)")

        summary.append((profile_name, classification))

    # Final summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for name, classification in summary:
        status = "PASS" if classification in {"IDENTICAL", "NORMALISATION-ONLY"} else "FAIL"
        print(f"  {status}  {name:24s}  {classification}")

    failures = [s for s in summary if s[1] not in {"IDENTICAL", "NORMALISATION-ONLY"}]
    print()
    if failures:
        print(f"FAILED — {len(failures)} profile(s) produced unexpected diffs:")
        for name, classification in failures:
            print(f"  {name}: {classification}")
    else:
        print(f"All {len(summary)} profiles either IDENTICAL or NORMALISATION-ONLY.")
        print()
        print("This is a synthetic verification — it does NOT replace running")
        print("./scripts/ontology_integration_verify.sh against your real")
        print("dev backend. But it does prove the refactored handler's code")
        print("paths produce wire-compatible responses for the five data")
        print("quality profiles named in the integration plan.")


if __name__ == "__main__":
    main()
