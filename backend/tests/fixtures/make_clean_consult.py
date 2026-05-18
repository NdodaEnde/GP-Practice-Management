"""
Generator for clean_consult.pdf — the Piece-2 golden-path live-run
fixture (#1). 100% SYNTHETIC. No real patient data anywhere.

Why a generator script ships with the fixture: a binary test asset with
no provenance is opaque — anyone auditing must trust it is synthetic.
This script makes the synthetic content legible and the PDF
regenerable, so its provenance is verifiable by reading, not trusted.

Content is modelled on the repo's already-vetted synthetic extraction
shape (backend/tests/conftest.py `validated_document_row`): Test
Patient, ID 8503140001087, Hypertension/I10, Atenolol 50mg, BP 130/85.
The document itself carries a "SYNTHETIC TEST FIXTURE — NOT REAL PATIENT
DATA" stamp so it cannot be mistaken for PHI even if it lands in a log.

Run:  python backend/tests/fixtures/make_clean_consult.py
Deps: Pillow only (already in the venv; no new dependency).
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

_OUT = Path(__file__).with_name("clean_consult.pdf")

# A4-ish at ~150 DPI, white page.
_W, _H = 1240, 1754
_MARGIN = 90

_LINES = [
    ("DEMO FAMILY PRACTICE", 34, True),
    ("SYNTHETIC TEST FIXTURE — NOT REAL PATIENT DATA", 18, False),
    ("Dr A. Tester  |  HPCSA: TEST-0000  |  Practice no: 9999999", 20, False),
    ("", 10, False),
    ("PATIENT CONSULTATION NOTE", 28, True),
    ("", 10, False),
    ("Patient:               Test Patient", 24, False),
    ("Date of birth:         1985-03-14", 24, False),
    ("ID number:             8503140001087", 24, False),
    ("Contact:               +27 82 123 4567", 24, False),
    ("Address:               12 Test Rd, Testville", 24, False),
    ("Date of consultation:  2026-05-01", 24, False),
    ("", 14, False),
    ("Presenting complaint:", 24, True),
    ("Routine follow-up for hypertension. No acute symptoms.", 24, False),
    ("", 12, False),
    ("Examination / Vitals:", 24, True),
    ("Blood pressure: 130/85 mmHg", 24, False),
    ("Pulse: 72 bpm    Temperature: 36.6 C    Weight: 78 kg", 24, False),
    ("", 12, False),
    ("Diagnosis:", 24, True),
    ("Essential hypertension (ICD-10: I10)", 24, False),
    ("", 12, False),
    ("Medication / Prescription:", 24, True),
    ("Atenolol 50 mg — one tablet daily", 24, False),
    ("", 12, False),
    ("Plan / Notes:", 24, True),
    ("Stable on current treatment. Continue Atenolol.", 24, False),
    ("Review in 3 months. Lifestyle advice reinforced.", 24, False),
    ("", 20, False),
    ("Signed: Dr A. Tester", 22, False),
    ("(synthetic test fixture — contains no real patient data)", 16, False),
]

_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _font(size: int, bold: bool):
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:  # noqa: BLE001
                continue
    return ImageFont.load_default()


def build() -> Path:
    img = Image.new("RGB", (_W, _H), "white")
    d = ImageDraw.Draw(img)
    y = _MARGIN
    for text, size, bold in _LINES:
        if text:
            d.text((_MARGIN, y), text, fill="black", font=_font(size, bold))
        y += int(size * 1.7) + 4
    img.save(_OUT, "PDF", resolution=150.0)
    return _OUT


if __name__ == "__main__":
    p = build()
    print(f"wrote {p} ({p.stat().st_size} bytes)")
