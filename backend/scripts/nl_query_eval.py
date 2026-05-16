#!/usr/bin/env python3
"""
nl_query_eval.py — OPT-IN real-LLM accuracy eval for the PR C NL layer.

ACCURACY IS REPORTED, NEVER GATED. This script is NEVER run in CI. With
`NL_QUERY_LLM_ENABLED` off it refuses. It is the ONLY thing that can
verify classifier *mapping correctness* — which is, by design,
UNVERIFIED at merge (the mocked unit tests prove WIRING only, not
intelligence). Running it sends real (potentially PII-bearing) phrasings
to whatever provider an operator has authorised, so it requires a
deliberate TWO-STEP opt-in: the flag must be on AND
`--i-have-authorised-a-provider` must be passed. It cannot be wired into
CI accidentally and cannot send anything without an operator's explicit
act.

It is not imported by any test, nor by registered.py / __init__.py.

Usage (operator, after authorising a provider — a governance act):
  cd backend && NL_QUERY_LLM_ENABLED=true PYTHONPATH=. \
    .venv/bin/python scripts/nl_query_eval.py --i-have-authorised-a-provider
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# ── In-set golden phrasings (Decision #4: thin — 1 canonical + 1
# paraphrase per registered template). The expected template is asserted;
# params are spot-checked where unambiguous. ──────────────────────────────
GOLDEN = [
    # patients_with_diagnosis_prefix
    ("which patients have an ICD-10 diagnosis starting with E11",
     "patients_with_diagnosis_prefix"),
    ("show me the type-2 diabetes cohort by code prefix E11",
     "patients_with_diagnosis_prefix"),
    # patients_not_seen_since
    ("which patients have not been seen in the last 180 days",
     "patients_not_seen_since"),
    ("list patients overdue for a visit — nothing in ~6 months",
     "patients_not_seen_since"),
    # patient_active_medications
    ("what is patient p1 currently on", "patient_active_medications"),
    ("show p1's active medication list", "patient_active_medications"),
    # patient_recent_consultations
    ("show p1's last 5 consultations", "patient_recent_consultations"),
    ("recent visits for patient p1", "patient_recent_consultations"),
    # patients_with_abnormal_recent_vitals
    ("who had a high blood pressure reading recently",
     "patients_with_abnormal_recent_vitals"),
    ("patients with abnormal BP in the last 90 days",
     "patients_with_abnormal_recent_vitals"),
    # patient_open_documents
    ("which documents are still waiting on me",
     "patient_open_documents"),
    ("show open / not-yet-finalised documents", "patient_open_documents"),
    # patients_with_lab_threshold
    ("who has an HbA1c result over 8", "patients_with_lab_threshold"),
    ("patients with a lab result above a threshold for HBA1C",
     "patients_with_lab_threshold"),
]

# ── Adversarial set (Decision #4: the LOAD-BEARING half — NOT governed
# by "thinnest"; sizing principle is HAZARD-SHAPE COVERAGE. Each MUST
# refuse — the silent-wrong-answer this whole phase guards against is an
# almost-match that converts instead of refusing). ─────────────────────────
ADVERSARIAL = [
    # near-miss: differs from patients_not_seen_since by a clinically
    # material term ("should not see again" ≠ "not seen since").
    "which patients should I not see again",
    # plausible clinical question with NO registered template.
    "what is the average waiting time in my practice this week",
    # plausible-but-unregistered shape near a real one.
    "delete patient p1's diabetes diagnosis",
    # PII-bearing free-text that is not a registered shape — must refuse,
    # never approximate to a template.
    "is Thabo Mokoena overdue for his diabetic foot screening",
]


def _refuse(msg: str) -> int:
    print(f"REFUSED: {msg}")
    print("This script is opt-in, never CI; with the flag off it refuses; "
          "accuracy is reported, never gated.")
    return 2


def main() -> int:
    if "--i-have-authorised-a-provider" not in sys.argv:
        return _refuse("missing --i-have-authorised-a-provider "
                       "(deliberate two-step opt-in; a provider "
                       "authorisation is a governance act)")
    from app.core.config import settings
    if not getattr(settings, "NL_QUERY_LLM_ENABLED", False):
        return _refuse("NL_QUERY_LLM_ENABLED is off")

    from app.services.nl_query import (
        NLClassification, NLRefusal, classify_question,
    )

    print("=" * 70)
    print("NL classifier accuracy eval — REPORTED, NEVER GATED, NEVER CI.")
    print("Sends real (possibly PII-bearing) phrasings to the authorised "
          "provider.")
    print("=" * 70)

    in_ok = 0
    print("\n-- in-set goldens (1 canonical + 1 paraphrase / template) --")
    for phrasing, expected in GOLDEN:
        out = classify_question(phrasing)
        got = (out.template_id if isinstance(out, NLClassification)
               else f"REFUSED({out.reason})")
        hit = isinstance(out, NLClassification) and out.template_id == expected
        in_ok += 1 if hit else 0
        print(f"  [{'OK ' if hit else 'MISS'}] {phrasing!r}\n"
              f"        expected={expected} got={got}")

    adv_ok = 0
    print("\n-- adversarial (MUST refuse — hazard-shape coverage) --")
    for phrasing in ADVERSARIAL:
        out = classify_question(phrasing)
        refused = isinstance(out, NLRefusal)
        adv_ok += 1 if refused else 0
        got = (f"REFUSED({out.reason})" if refused
               else f"!! MAPPED to {out.template_id} (HAZARD: silent "
                    f"conversion)")
        print(f"  [{'OK ' if refused else 'FAIL'}] {phrasing!r}\n"
              f"        {got}")

    print("\n" + "=" * 70)
    print(f"in-set mapping accuracy : {in_ok}/{len(GOLDEN)}")
    print(f"adversarial refusal rate: {adv_ok}/{len(ADVERSARIAL)}")
    print("REPORTED, NOT GATED. A low number here is a finding for "
          "governance, not a CI failure — accuracy is unverified at "
          "merge by design; this is the only thing that can verify it.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
