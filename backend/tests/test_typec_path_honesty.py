"""
Piece 2 — load-bearing artifact (the §2.4 NECESSARY half): the Type-C
demo path renders no hardcoded/sample data presented as real.

This is the automatable, re-runnable guard. It is non-vacuous BY
CONSTRUCTION via a positive control: the SAME detector must flag the
known off-path mock (`PatientEHR.jsx`'s `mockVitalsData`). A detector
that cannot catch the thing it checks for would make "Type-C path clean"
a vacuous green — exactly the §D.1 false-green, here at the worst
location. So: clean on the Type-C set AND proven to bite on the known
mock, or the suite fails.

NOT sufficient. "Demonstrable" is earned only by the live fresh-PDF
Type-C run (surfaced as the principal's credit/shared-state word in the
plan). Static-clean ≠ demo-honest; this is the necessary precheck.
"""
import re
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[2] / "frontend" / "src"

# The Type-C demo path, enumerated to match the separability probe: the
# isTypeC nav-reachable pages + the export sub-route + the shared
# uploader. If a path here does not exist, the enumeration is broken and
# the guard would pass vacuously — asserted in test_typec_files_exist.
_TYPEC_PATH = [
    "pages/DigitisationDashboard.jsx",
    "pages/DocumentsPipeline.jsx",
    "pages/DigitisationValidationQueue.jsx",
    "pages/DigitisationValidationDetail.jsx",
    "pages/DigitisationArchive.jsx",
    "pages/DigitisationSearch.jsx",
    "pages/DigitisationExportCentre.jsx",
    "pages/DigitisationFHIRConnectionWizard.jsx",
    "pages/DigitisationOperationalInsights.jsx",
    "components/DigitisationUploader.jsx",
]

# Known off-path mock — the positive control proving the detector bites.
_KNOWN_MOCK = "pages/PatientEHR.jsx"

_NAME = re.compile(
    r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*\[",
)
_MOCKISH = re.compile(r"mock|sample|fake|dummy|demo|placeholder|seed|example", re.I)
# A hardcoded array of record-shaped objects: an array literal whose
# first object carries >=2 clinical/record keys with literal values.
_RECORD_LITERAL = re.compile(
    r"=\s*\[\s*\{[^}]*?"
    r"(?:systolic|diastolic|icd10|nappi|date'?\s*:|value\s*:|result\s*:|"
    r"medication|diagnosis|patient_name)\b",
    re.I,
)


def _strip_noise(line: str) -> str:
    s = line.strip()
    if s.startswith("//") or s.startswith("*") or s.startswith("/*"):
        return ""
    # JSX attributes / empties are not "data presented as real"
    if re.search(r'(placeholder|className|aria-[\w-]+|id|name)\s*=\s*["\']', s):
        return ""
    if re.search(r"=\s*\[\s*\]", s) or "useState([])" in s:
        return ""
    return s


def _array_is_object_shaped(lines: list, start_idx: int) -> bool:
    """After a `... = [` at lines[start_idx], is the first non-empty
    element an object literal `{` (record-shaped data) rather than a
    bare string/number (a UI-affordance list, e.g. example query
    prompts)? Adjudicated distinction: mock CLINICAL DATA presented as
    real is record-shaped; `EXAMPLE_QUERIES = ['...','...']` is search
    prompts, not fiction-as-fact."""
    tail = lines[start_idx].split("[", 1)[1] if "[" in lines[start_idx] else ""
    for chunk in [tail] + lines[start_idx + 1:start_idx + 4]:
        s = chunk.strip()
        if not s:
            continue
        return s[0] == "{"
    return False


def mock_as_real_hits(source: str) -> list:
    """Lines where hardcoded/sample data is bound to a name that will
    feed a render. Identifier signal (mock/sample/...-named array OF
    OBJECTS — record-shaped, not a UI string list) + record-literal
    signal (array of clinical-record objects)."""
    lines = source.splitlines()
    hits = []
    for i, raw in enumerate(lines, 1):
        line = _strip_noise(raw)
        if not line:
            continue
        m = _NAME.search(line)
        if m and _MOCKISH.search(m.group(1)) and _array_is_object_shaped(lines, i - 1):
            hits.append(f"{i}: {raw.strip()[:90]}")
            continue
        if _RECORD_LITERAL.search(line):
            hits.append(f"{i}: {raw.strip()[:90]}")
    return hits


def _read(rel: str) -> str:
    return (_SRC / rel).read_text(encoding="utf-8", errors="replace")


def test_typec_files_exist():
    """An orphan path would make the guard pass vacuously."""
    missing = [p for p in _TYPEC_PATH if not (_SRC / p).exists()]
    assert not missing, f"Type-C path enumeration broken, missing: {missing}"
    assert (_SRC / _KNOWN_MOCK).exists(), f"positive control {_KNOWN_MOCK} missing"


def test_detector_bites_on_known_offpath_mock():
    """Non-vacuity: the SAME detector must flag PatientEHR's
    mockVitalsData. If it can't catch the known mock, a clean Type-C
    result is meaningless."""
    hits = mock_as_real_hits(_read(_KNOWN_MOCK))
    assert any("mockVitalsData" in h or "mock" in h.lower() for h in hits), (
        f"detector did NOT flag the known off-path mock in {_KNOWN_MOCK} "
        f"-> it is vacuous; hits={hits}"
    )


@pytest.mark.parametrize("rel", _TYPEC_PATH)
def test_typec_path_renders_no_mock_as_real(rel):
    hits = mock_as_real_hits(_read(rel))
    assert not hits, (
        f"{rel} presents hardcoded/sample data as real on the Type-C "
        f"demo path:\n  " + "\n  ".join(hits)
    )
