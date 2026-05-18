"""
Generator for the Piece-2 demo / test fixtures, in the SAME 3-page
format as the platform's `demo_patient_full.pdf`:

  Page 1  MEDICAL FILE intake form  — PATIENT DETAILS, PERSON
          RESPONSIBLE FOR ACCOUNT, MEDICAL AID, NEAREST FAMILY/FRIEND,
          DEPENDENTS table, CLIENT CONSENT (boxed fields, title +
          marital-status checkboxes).
  Page 2  CONSULTATION NOTES        — multiple dated SOAP encounters
          (S/O/A/P) with GP shorthand and inline ICD-10 codes.
  Page 3  PathCare Laboratories     — sectioned result table
          (TEST / RESULT / UNIT / REFERENCE RANGE / FLAG, HIGH/LOW).

100% SYNTHETIC. Fictional names, test ID numbers, test addresses,
test medical-aid numbers, and a "SYNTHETIC TEST FIXTURE — NOT REAL
PATIENT DATA" stamp on every page so a file can never be mistaken for
PHI even in a log. The generator ships with the fixtures so content is
legible and regenerable (provenance verified by reading, not trusted).

Add a patient by appending a dict to _RECORDS (same shape) and re-run.

Run:  python backend/tests/fixtures/make_demo_records.py
Deps: reportlab (in the venv).
"""
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas

_DIR = Path(__file__).resolve().parent
_PW, _PH = A4
_M = 18 * mm                       # page margin
_BAR = colors.HexColor("#E7DFCF")  # section header bar (beige)
_BARTX = colors.HexColor("#3A3526")
_BOX = colors.HexColor("#B9A77E")  # field box border
_VAL = colors.HexColor("#1F3B73")  # filled value text (blue)
_NAVY = colors.HexColor("#16264F")  # lab report header
_STAMP = colors.HexColor("#B0392F")

# ---------------------------------------------------------------------------
# Low-level drawing helpers (canvas-based; faithful to the form layout)
# ---------------------------------------------------------------------------

def _stamp(c):
    c.setFont("Helvetica-Bold", 7.5)
    c.setFillColor(_STAMP)
    c.drawCentredString(_PW / 2, _PH - 8 * mm,
                        "SYNTHETIC TEST FIXTURE — NOT REAL PATIENT DATA")


def _section(c, y, title):
    c.setFillColor(_BAR)
    c.rect(_M, y - 6 * mm, _PW - 2 * _M, 6.5 * mm, fill=1, stroke=0)
    c.setFillColor(_BARTX)
    c.setFont("Helvetica-Bold", 9.5)
    c.drawString(_M + 3 * mm, y - 4.4 * mm, title)
    return y - 11 * mm


def _field(c, x, y, label, value, w, lw=34 * mm):
    c.setFont("Helvetica", 7)
    c.setFillColor(colors.HexColor("#6B6450"))
    c.drawString(x, y + 1.2 * mm, label)
    c.setStrokeColor(_BOX)
    c.setLineWidth(0.6)
    c.roundRect(x + lw, y - 1.5 * mm, w - lw, 6 * mm, 1.2 * mm,
                fill=0, stroke=1)
    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColor(_VAL)
    c.drawString(x + lw + 2 * mm, y + 0.6 * mm, str(value))
    return y - 9 * mm


def _checks(c, x, y, label, options, chosen):
    c.setFont("Helvetica", 7)
    c.setFillColor(colors.HexColor("#6B6450"))
    c.drawString(x, y + 1 * mm, label)
    cx = x + 34 * mm
    for opt in options:
        c.setStrokeColor(_BOX)
        c.setLineWidth(0.6)
        c.rect(cx, y - 0.8 * mm, 3.6 * mm, 3.6 * mm, fill=0, stroke=1)
        if opt == chosen:
            c.setFont("Helvetica-Bold", 8)
            c.setFillColor(_VAL)
            c.drawString(cx + 0.5 * mm, y - 0.3 * mm, "X")
        c.setFont("Helvetica", 7.5)
        c.setFillColor(colors.black)
        c.drawString(cx + 5 * mm, y, opt)
        cx += 5 * mm + c.stringWidth(opt, "Helvetica", 7.5) + 9 * mm
    return y - 8 * mm


def _table(c, y, headers, rows, widths):
    x0 = _M
    rh = 6.5 * mm
    c.setFillColor(_BAR)
    c.rect(x0, y - rh, sum(widths), rh, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 7.5)
    c.setFillColor(_BARTX)
    cx = x0
    for h, w in zip(headers, widths):
        c.drawString(cx + 2 * mm, y - 4.3 * mm, h)
        cx += w
    y -= rh
    for row in rows:
        c.setStrokeColor(colors.HexColor("#D8CFB8"))
        c.setLineWidth(0.5)
        c.rect(x0, y - rh, sum(widths), rh, fill=0, stroke=1)
        c.setFont("Helvetica", 7.5)
        c.setFillColor(_VAL)
        cx = x0
        for cell, w in zip(row, widths):
            c.drawString(cx + 2 * mm, y - 4.3 * mm, str(cell))
            cx += w
        y -= rh
    return y - 4 * mm


def _wrap(c, x, y, text, font, size, max_w, leading):
    c.setFont(font, size)
    words = text.split()
    line = ""
    for w in words:
        t = (line + " " + w).strip()
        if c.stringWidth(t, font, size) > max_w and line:
            c.drawString(x, y, line)
            y -= leading
            line = w
        else:
            line = t
    if line:
        c.drawString(x, y, line)
        y -= leading
    return y


# ---------------------------------------------------------------------------
# Page renderers
# ---------------------------------------------------------------------------

def _page_intake(c, r):
    _stamp(c)
    c.setFont("Helvetica-Bold", 26)
    c.setFillColor(colors.HexColor("#222"))
    c.drawString(_M, _PH - 22 * mm, "MEDICAL")
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(colors.HexColor("#6B6450"))
    c.drawString(_PW - _M - 70 * mm, _PH - 18 * mm, "FILE / COMPUTER NO:")
    c.setStrokeColor(_BOX)
    c.roundRect(_PW - _M - 70 * mm, _PH - 24 * mm, 70 * mm, 8 * mm,
                1.5 * mm, fill=0, stroke=1)
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(_VAL)
    c.drawString(_PW - _M - 40 * mm, _PH - 21.5 * mm, r["file_no"])

    p = r["patient"]
    fw = _PW - 2 * _M
    y = _PH - 32 * mm
    y = _section(c, y, "PATIENT DETAILS")
    y = _checks(c, _M, y, "Full Name/s:  " + p["full_names"],
                ["Mr", "Mrs", "Miss", "Other"], p["title"])
    y = _field(c, _M, y, "Surname:", p["surname"], fw / 2 - 4 * mm)
    _field(c, _M + fw / 2, y + 9 * mm, "ID No:", p["id"], fw / 2,
           lw=20 * mm)
    y = _field(c, _M, y, "E-Mail:", p["email"], fw / 2 - 4 * mm)
    _field(c, _M + fw / 2, y + 9 * mm, "Tel./Cell:", p["cell"], fw / 2,
           lw=22 * mm)
    y = _field(c, _M, y, "Address:", p["address"], fw)

    a = r["account"]
    y = _section(c, y, "PERSON RESPONSIBLE FOR ACCOUNT (Main Member of Medical Aid)")
    y = _checks(c, _M, y, "Full Name/s:  " + p["full_names"],
                ["Mr", "Mrs", "Miss", "Other"], p["title"])
    y = _field(c, _M, y, "Surname:", p["surname"], fw / 2 - 4 * mm)
    _field(c, _M + fw / 2, y + 9 * mm, "Date of Birth:", p["dob"],
           fw / 2, lw=24 * mm)
    y = _checks(c, _M, y, "Marital Status:",
                ["S", "M", "D", "W"], p["marital"])
    y = _field(c, _M, y, "Employer:", a["employer"], fw / 2 - 4 * mm)
    _field(c, _M + fw / 2, y + 9 * mm, "Occupation:", a["occupation"],
           fw / 2, lw=24 * mm)
    y = _field(c, _M, y, "Work Address:", a["work_address"], fw)

    m = r["medical_aid"]
    y = _section(c, y, "MEDICAL AID")
    y = _field(c, _M, y, "Medical Aid:", m["name"], fw / 2 - 4 * mm)
    _field(c, _M + fw / 2, y + 9 * mm, "Number:", m["number"], fw / 2,
           lw=20 * mm)
    y = _field(c, _M, y, "Plan:", m["plan"], fw / 2 - 4 * mm)
    _field(c, _M + fw / 2, y + 9 * mm, "Other:", m["other"], fw / 2,
           lw=20 * mm)

    f = r["family"]
    y = _section(c, y, "NEAREST FAMILY / FRIEND")
    y = _field(c, _M, y, "Name:", f["name"], fw / 2 - 4 * mm)
    _field(c, _M + fw / 2, y + 9 * mm, "Relationship:",
           f["relationship"], fw / 2, lw=24 * mm)
    y = _field(c, _M, y, "Tel./Cell:", f["cell"], fw)

    y = _section(c, y, "DEPENDENTS ON MEDICAL AID")
    y = _table(c, y,
               ["Name", "Sex", "Date of Birth", "Dep. Code", "Allergies"],
               [[d["name"], d["sex"], d["dob"], d["code"], d["allergies"]]
                for d in r["dependents"]],
               [fw * 0.30, fw * 0.10, fw * 0.22, fw * 0.16, fw * 0.22])

    y = _section(c, y, "CLIENT CONSENT & DECLARATION")
    c.setFillColor(colors.black)
    _wrap(c, _M, y - 1 * mm,
          f"I, {p['full_names']} {p['surname']} (full names and surname) "
          "hereby consent to all my and my dependants' personal "
          "information being recorded and/or used and/or shared, as may "
          "be necessary, to provide the best professional service to the "
          "patient. I understand and accept the aforementioned terms and "
          "conditions.", "Helvetica", 7.5, _PW - 2 * _M, 4 * mm)
    c.showPage()


def _page_notes(c, r):
    _stamp(c)
    p = r["patient"]
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(colors.black)
    c.drawString(_M, _PH - 20 * mm, "CONSULTATION NOTES")
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(_PW - _M, _PH - 20 * mm,
                      f"{p['surname']}, {p['full_names']}  |  {r['file_no']}")
    c.setStrokeColor(colors.HexColor("#999"))
    c.line(_M, _PH - 22 * mm, _PW - _M, _PH - 22 * mm)
    y = _PH - 30 * mm
    for enc in r["encounters"]:
        if y < 45 * mm:
            c.showPage()
            _stamp(c)
            y = _PH - 25 * mm
        c.setFont("Helvetica-Bold", 9.5)
        c.setFillColor(_VAL)
        c.drawString(_M, y, enc["date"])
        c.setStrokeColor(_VAL)
        c.line(_M, y - 1.5 * mm, _M + 40 * mm, y - 1.5 * mm)
        y -= 6 * mm
        for tag, lines in (("S:", enc["S"]), ("O:", enc["O"]),
                           ("A:", enc["A"]), ("P:", enc["P"])):
            c.setFont("Courier-Bold", 8.5)
            c.setFillColor(colors.black)
            c.drawString(_M, y, tag)
            for ln in lines:
                y = _wrap(c, _M + 8 * mm, y, ln, "Courier", 8.5,
                          _PW - 2 * _M - 8 * mm, 4.6 * mm)
            y -= 1.5 * mm
        c.setStrokeColor(colors.HexColor("#CCC"))
        c.setDash(1, 2)
        c.line(_M, y, _PW - _M, y)
        c.setDash()
        y -= 7 * mm
    c.showPage()


def _page_labs(c, r):
    lab = r["labs"]
    p = r["patient"]
    c.setFillColor(_NAVY)
    c.rect(0, _PH - 34 * mm, _PW, 34 * mm, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 20)
    c.setFillColor(colors.white)
    c.drawString(_M, _PH - 20 * mm, "PathCare Laboratories")
    c.setFont("Helvetica", 8)
    c.drawString(_M, _PH - 27 * mm,
                 "Tel: 011 234 1000  |  www.pathcare.co.za  |  "
                 "Laboratory Reg No: L04/009")
    _stamp(c)
    y = _PH - 44 * mm
    c.setStrokeColor(colors.HexColor("#AAB"))
    c.roundRect(_M, y - 14 * mm, _PW - 2 * _M, 16 * mm, 1.5 * mm,
                fill=0, stroke=1)
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(colors.HexColor("#444"))
    c.drawString(_M + 3 * mm, y - 3 * mm, "PATIENT:")
    c.drawString(_M + 70 * mm, y - 3 * mm, "ID NUMBER:")
    c.drawString(_M + 130 * mm, y - 3 * mm, "DATE COLLECTED:")
    c.setFont("Helvetica", 8.5)
    c.setFillColor(_VAL)
    c.drawString(_M + 3 * mm, y - 8 * mm,
                 f"{p['surname']}, {p['full_names']}")
    c.drawString(_M + 70 * mm, y - 8 * mm, p["id"])
    c.drawString(_M + 130 * mm, y - 8 * mm, lab["collected"])
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(colors.HexColor("#444"))
    c.drawString(_M + 3 * mm, y - 12.5 * mm,
                 f"REF DOCTOR: {lab['ref_doctor']}")
    c.drawString(_M + 70 * mm, y - 12.5 * mm,
                 f"MEDICAL AID: {lab['medical_aid']}")
    y -= 22 * mm
    fw = _PW - 2 * _M
    widths = [fw * 0.40, fw * 0.13, fw * 0.13, fw * 0.22, fw * 0.12]
    for sec in lab["sections"]:
        if y < 40 * mm:
            c.showPage()
            _stamp(c)
            y = _PH - 25 * mm
        c.setFillColor(_NAVY)
        c.rect(_M, y - 6 * mm, fw, 6.5 * mm, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(colors.white)
        c.drawString(_M + 2 * mm, y - 4.3 * mm, sec["title"])
        y -= 6 * mm
        c.setFont("Helvetica-Bold", 7)
        c.setFillColor(colors.HexColor("#555"))
        for h, x in zip(["TEST", "RESULT", "UNIT", "REFERENCE RANGE",
                         "FLAG"],
                        [_M, _M + widths[0], _M + widths[0] + widths[1],
                         _M + sum(widths[:3]), _M + sum(widths[:4])]):
            c.drawString(x + 2 * mm, y - 4 * mm, h)
        y -= 6.5 * mm
        c.setStrokeColor(colors.HexColor("#CBD2E0"))
        c.setLineWidth(0.5)
        c.line(_M, y + 1.5 * mm, _M + fw, y + 1.5 * mm)
        y -= 2.5 * mm
        for row in sec["rows"]:
            c.setFont("Helvetica", 7.5)
            c.setFillColor(colors.black)
            c.drawString(_M + 2 * mm, y, row["test"])
            c.setFillColor(_VAL)
            c.drawString(_M + widths[0] + 2 * mm, y, row["result"])
            c.setFillColor(colors.HexColor("#555"))
            c.drawString(_M + widths[0] + widths[1] + 2 * mm, y,
                         row["unit"])
            c.drawString(_M + sum(widths[:3]) + 2 * mm, y, row["ref"])
            if row.get("flag"):
                c.setFillColor(_STAMP)
                c.setFont("Helvetica-Bold", 7.5)
                c.drawString(_M + sum(widths[:4]) + 2 * mm, y, row["flag"])
            y -= 5.2 * mm
        y -= 4 * mm
    c.setFont("Helvetica-Oblique", 7)
    c.setFillColor(colors.HexColor("#888"))
    c.drawString(_M, 22 * mm,
                 f"Authorised by: {lab['authorised']}  |  Lab Director  "
                 "|  HIGH/LOW flags indicate results outside reference "
                 "range. Interpret in clinical context.")
    c.drawString(_M, 18 * mm,
                 "PathCare Laboratories — accredited by SANAS  "
                 "(synthetic test fixture — contains no real patient data)")
    c.showPage()


def build_one(r) -> Path:
    out = _DIR / r["file"]
    c = canvas.Canvas(str(out), pagesize=A4)
    _page_intake(c, r)
    _page_notes(c, r)
    _page_labs(c, r)
    c.save()
    return out


# ---------------------------------------------------------------------------
# The four synthetic records (same shape as demo_patient_full; vary names)
# ---------------------------------------------------------------------------

_RECORDS = [
    {
        "file": "demo_abongile_rhaqa.pdf", "file_no": "GP-2026-1042",
        "patient": {"title": "Mr", "full_names": "Abongile",
                    "surname": "Rhaqa", "id": "9007220001083",
                    "dob": "22/07/1990", "email": "a.rhaqa@example.test",
                    "cell": "073 555 0142",
                    "address": "8 Marula Street, Mthatha, 5099",
                    "marital": "M"},
        "account": {"employer": "Eastern Cape Dept of Education",
                    "occupation": "Teacher",
                    "work_address": "Sutherland Rd, Mthatha"},
        "medical_aid": {"name": "Bonitas", "number": "B7741920",
                        "plan": "Standard", "other": "N/A"},
        "family": {"name": "Zinhle Rhaqa", "relationship": "Wife",
                   "cell": "072 555 0143"},
        "dependents": [
            {"name": "Zinhle Rhaqa", "sex": "F", "dob": "03/05/1992",
             "code": "01", "allergies": "None known"},
            {"name": "Lwazi Rhaqa", "sex": "M", "dob": "19/08/2017",
             "code": "02", "allergies": "None known"},
        ],
        "encounters": [
            {"date": "12/04/2026",
             "S": ["Follow-up of type 2 diabetes. Reports increased "
                   "thirst + fatigue x 3/52. Adherent to metformin.",
                   "PMHx: T2DM (dx 2023). No known DM complications."],
             "O": ["T: 36.7C  HR: 80  BP: 138/88  Wt: 92kg  BMI: 30.1",
                   "FBS: 9.1 mmol/L  HbA1c: 8.4%  Feet: no ulcers, "
                   "monofilament intact."],
             "A": ["Type 2 Diabetes Mellitus - suboptimal control  "
                   "ICD-10: E11.9"],
             "P": ["1. Up-titrate Metformin 850mg BD (was 500mg BD)",
                   "2. Reinforce diet + exercise; refer dietician",
                   "3. Bloods 3/12: HbA1c, U&E, lipogram",
                   "4. RTF 3/12 or sooner if symptomatic"]},
            {"date": "20/07/2026",
             "S": ["Diabetes review. Feels better, less fatigue. "
                   "Tolerating metformin well."],
             "O": ["BP: 130/82  Wt: 89kg (down 3kg)  FBS: 7.4 mmol/L  "
                   "HbA1c: 7.3% (improved)"],
             "A": ["T2DM - improving on current regimen  ICD-10: E11.9"],
             "P": ["1. Continue Metformin 850mg BD",
                   "2. Continue lifestyle measures; RTF 4/12"]},
        ],
        "labs": {"collected": "12/04/2026", "ref_doctor": "Dr N. Dlamini",
                 "medical_aid": "Bonitas B7741920",
                 "authorised": "Dr M. Naidoo",
                 "sections": [
                     {"title": "CHEMISTRY — GLUCOSE & DIABETES MONITORING",
                      "rows": [
                          {"test": "Fasting Blood Glucose",
                           "result": "9.1", "unit": "mmol/L",
                           "ref": "3.9 - 6.1", "flag": "HIGH"},
                          {"test": "HbA1c", "result": "8.4",
                           "unit": "%", "ref": "< 7.0", "flag": "HIGH"},
                      ]},
                     {"title": "RENAL FUNCTION — UREA & ELECTROLYTES",
                      "rows": [
                          {"test": "Creatinine", "result": "84",
                           "unit": "umol/L", "ref": "62 - 106",
                           "flag": ""},
                          {"test": "eGFR", "result": "92",
                           "unit": "mL/min", "ref": "> 60", "flag": ""},
                      ]},
                     {"title": "LIPOGRAM — CARDIOVASCULAR RISK",
                      "rows": [
                          {"test": "Total Cholesterol", "result": "5.6",
                           "unit": "mmol/L", "ref": "< 5.2",
                           "flag": "HIGH"},
                          {"test": "LDL Cholesterol", "result": "3.4",
                           "unit": "mmol/L", "ref": "< 3.0 (DM)",
                           "flag": "HIGH"},
                      ]},
                 ]},
    },
    {
        "file": "demo_bonakele_mfene.pdf", "file_no": "GP-2026-1058",
        "patient": {"title": "Mrs", "full_names": "Bonakele",
                    "surname": "Mfene", "id": "7811050002081",
                    "dob": "05/11/1978", "email": "b.mfene@example.test",
                    "cell": "082 555 0199",
                    "address": "14 Protea Avenue, Bloemfontein, 9301",
                    "marital": "M"},
        "account": {"employer": "Free State Provincial Hospital",
                    "occupation": "Administrator",
                    "work_address": "Markgraaff St, Bloemfontein"},
        "medical_aid": {"name": "Discovery Health", "number": "D5582013",
                        "plan": "KeyCare Plus", "other": "N/A"},
        "family": {"name": "Sipho Mfene", "relationship": "Husband",
                   "cell": "071 555 0200"},
        "dependents": [
            {"name": "Sipho Mfene", "sex": "M", "dob": "11/02/1976",
             "code": "01", "allergies": "Aspirin"},
            {"name": "Naledi Mfene", "sex": "F", "dob": "27/09/2010",
             "code": "02", "allergies": "None known"},
        ],
        "encounters": [
            {"date": "18/04/2026",
             "S": ["Recurrent wheeze + SOB, worse at night + on "
                   "exertion. Using salbutamol >3x/week. No fever."],
             "O": ["T: 36.5C  HR: 88  BP: 124/78  RR: 22  O2 Sat: 96% RA",
                   "Chest: bilateral expiratory wheeze. Peak flow: "
                   "320 L/min (predicted 450)."],
             "A": ["Asthma, moderate persistent - poorly controlled  "
                   "ICD-10: J45.4"],
             "P": ["1. Salbutamol inhaler 100mcg - 2 puffs PRN",
                   "2. Add Beclomethasone inhaler 200mcg BD",
                   "3. Inhaler technique demonstrated; spacer issued",
                   "4. Written asthma action plan given",
                   "5. RTF 6/52 for review"]},
            {"date": "06/06/2026",
             "S": ["Asthma review. Night symptoms much improved. "
                   "Salbutamol use down to 1x/week."],
             "O": ["RR: 16  O2 Sat: 98%  Chest: clear. Peak flow: "
                   "410 L/min (improved)."],
             "A": ["Asthma - well controlled on ICS  ICD-10: J45.4"],
             "P": ["1. Continue Beclomethasone 200mcg BD + Salbutamol PRN",
                   "2. RTF 3/12; sooner if exacerbation"]},
        ],
        "labs": {"collected": "18/04/2026", "ref_doctor": "Dr P. Naidoo",
                 "medical_aid": "Discovery Health D5582013",
                 "authorised": "Dr M. Naidoo",
                 "sections": [
                     {"title": "HAEMATOLOGY — FULL BLOOD COUNT (FBC)",
                      "rows": [
                          {"test": "Haemoglobin", "result": "13.2",
                           "unit": "g/dL", "ref": "12.0 - 15.5",
                           "flag": ""},
                          {"test": "White Cell Count", "result": "8.1",
                           "unit": "x10^9/L", "ref": "4.0 - 11.0",
                           "flag": ""},
                          {"test": "Eosinophils", "result": "0.62",
                           "unit": "x10^9/L", "ref": "0.0 - 0.45",
                           "flag": "HIGH"},
                      ]},
                 ]},
    },
    {
        "file": "demo_celumzi_sibanyoni.pdf", "file_no": "GP-2026-1071",
        "patient": {"title": "Mr", "full_names": "Celumzi",
                    "surname": "Sibanyoni", "id": "6502170003089",
                    "dob": "17/02/1965", "email": "c.sib@example.test",
                    "cell": "060 555 0123",
                    "address": "27 Acacia Road, Polokwane, 0699",
                    "marital": "M"},
        "account": {"employer": "Self-employed",
                    "occupation": "Shop Owner",
                    "work_address": "27 Acacia Road, Polokwane"},
        "medical_aid": {"name": "Momentum Health", "number": "M3390471",
                        "plan": "Custom", "other": "Gap cover"},
        "family": {"name": "Thandi Sibanyoni", "relationship": "Wife",
                   "cell": "060 555 0124"},
        "dependents": [
            {"name": "Thandi Sibanyoni", "sex": "F", "dob": "30/06/1968",
             "code": "01", "allergies": "Sulfa drugs"},
        ],
        "encounters": [
            {"date": "25/04/2026",
             "S": ["Routine review of HTN + high cholesterol. "
                   "Asymptomatic. Adherent to amlodipine + statin."],
             "O": ["T: 36.6C  HR: 76  BP: 152/94  Wt: 81kg  BMI: 28.1",
                   "CVS: normal. Peripheral oedema: nil. "
                   "Fundoscopy: no hypertensive changes."],
             "A": ["1. Essential hypertension - suboptimal  ICD-10: I10",
                   "2. Hyperlipidaemia  ICD-10: E78.5"],
             "P": ["1. Increase Amlodipine 5mg -> 10mg OD",
                   "2. Continue Atorvastatin 20mg nocte",
                   "3. Bloods 4/52: U&E, lipogram",
                   "4. Lifestyle advice; RTF 4/52 with results"]},
            {"date": "23/05/2026",
             "S": ["BP review. No side effects from increased "
                   "amlodipine. Feels well."],
             "O": ["BP: 136/86  HR: 74  Wt: 80kg"],
             "A": ["HTN - improved control  ICD-10: I10",
                   "Hyperlipidaemia - on treatment  ICD-10: E78.5"],
             "P": ["1. Continue Amlodipine 10mg OD + Atorvastatin "
                   "20mg nocte",
                   "2. RTF 6/12 with repeat lipogram"]},
        ],
        "labs": {"collected": "25/04/2026",
                 "ref_doctor": "Dr S. van der Merwe",
                 "medical_aid": "Momentum Health M3390471",
                 "authorised": "Dr M. Naidoo",
                 "sections": [
                     {"title": "RENAL FUNCTION — UREA & ELECTROLYTES",
                      "rows": [
                          {"test": "Urea", "result": "5.9",
                           "unit": "mmol/L", "ref": "2.5 - 7.5",
                           "flag": ""},
                          {"test": "Creatinine", "result": "98",
                           "unit": "umol/L", "ref": "62 - 106",
                           "flag": ""},
                          {"test": "Potassium", "result": "4.3",
                           "unit": "mmol/L", "ref": "3.5 - 5.1",
                           "flag": ""},
                      ]},
                     {"title": "LIPOGRAM — CARDIOVASCULAR RISK",
                      "rows": [
                          {"test": "Total Cholesterol", "result": "6.4",
                           "unit": "mmol/L", "ref": "< 5.2",
                           "flag": "HIGH"},
                          {"test": "LDL Cholesterol", "result": "4.1",
                           "unit": "mmol/L", "ref": "< 3.0",
                           "flag": "HIGH"},
                          {"test": "Triglycerides", "result": "2.6",
                           "unit": "mmol/L", "ref": "< 1.7",
                           "flag": "HIGH"},
                      ]},
                 ]},
    },
    {
        "file": "demo_funeka_gqakaza.pdf", "file_no": "GP-2026-1085",
        "patient": {"title": "Miss", "full_names": "Funeka",
                    "surname": "Gqakaza", "id": "0109300004085",
                    "dob": "30/09/2001", "email": "f.gqakaza@example.test",
                    "cell": "071 555 0177",
                    "address": "5 Aloe Close, Gqeberha, 6001",
                    "marital": "S"},
        "account": {"employer": "Nelson Mandela University",
                    "occupation": "Student",
                    "work_address": "University Way, Gqeberha"},
        "medical_aid": {"name": "Fedhealth", "number": "F2218840",
                        "plan": "FlexiFED 2", "other": "N/A"},
        "family": {"name": "Nosipho Gqakaza", "relationship": "Mother",
                   "cell": "082 555 0178"},
        "dependents": [],
        "encounters": [
            {"date": "03/05/2026",
             "S": ["Sore throat, fever + painful swallowing x 3/7. "
                   "No cough. No SOB. Reduced oral intake."],
             "O": ["T: 38.4C  HR: 96  BP: 118/74  Wt: 64kg",
                   "Throat: tonsils enlarged + erythematous with "
                   "exudate. Tender cervical lymphadenopathy. "
                   "Chest: clear."],
             "A": ["Acute tonsillitis (bacterial)  ICD-10: J03.9"],
             "P": ["1. Amoxicillin 500mg TDS x 5/7",
                   "2. Paracetamol 1g QDS PRN fever/pain",
                   "3. Adequate fluids, rest",
                   "4. RTF 48hrs if not improving or unable to swallow"]},
            {"date": "10/05/2026",
             "S": ["Follow-up tonsillitis. Symptoms resolved. "
                   "Completed antibiotic course. Eating normally."],
             "O": ["T: 36.6C  Throat: tonsils normal, no exudate. "
                   "No lymphadenopathy."],
             "A": ["Acute tonsillitis - resolved  ICD-10: J03.9"],
             "P": ["1. No further treatment required",
                   "2. Safety-net advice given; RTF PRN"]},
        ],
        "labs": {"collected": "03/05/2026", "ref_doctor": "Dr L. Khumalo",
                 "medical_aid": "Fedhealth F2218840",
                 "authorised": "Dr M. Naidoo",
                 "sections": [
                     {"title": "HAEMATOLOGY — FULL BLOOD COUNT (FBC)",
                      "rows": [
                          {"test": "Haemoglobin", "result": "12.8",
                           "unit": "g/dL", "ref": "12.0 - 15.5",
                           "flag": ""},
                          {"test": "White Cell Count", "result": "13.6",
                           "unit": "x10^9/L", "ref": "4.0 - 11.0",
                           "flag": "HIGH"},
                          {"test": "Neutrophils", "result": "9.8",
                           "unit": "x10^9/L", "ref": "2.0 - 7.5",
                           "flag": "HIGH"},
                      ]},
                     {"title": "INFLAMMATORY MARKERS",
                      "rows": [
                          {"test": "C-Reactive Protein (CRP)",
                           "result": "48", "unit": "mg/L",
                           "ref": "< 5", "flag": "HIGH"},
                      ]},
                 ]},
    },
]


def build_all():
    return [(build_one(r), (_DIR / r["file"]).stat().st_size)
            for r in _RECORDS]


if __name__ == "__main__":
    for path, size in build_all():
        print(f"wrote {path} ({size} bytes)")
