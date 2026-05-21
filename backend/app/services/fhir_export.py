"""
fhir_export.py — Build a FHIR R4 Bundle from a patient's SurgiScan record.

Phase 2.5 (Module 01 Digitisation §11 commitment in v1.2 brochure): doctors
who already run another EHR want to take their digitised data away in a
standards-compliant format. FHIR R4 with US Core profile is the only export
format major SA EHRs (Discovery Practice Studio, Healthbridge, etc.) accept
without bespoke integration work.

Scope decisions (v1):
  • Bundle type: 'searchset' — simpler than 'document' (no Composition required)
  • Resources mapped: Patient, AllergyIntolerance, Condition, MedicationStatement,
    Observation (vitals), Encounter
  • Coding systems:
      ICD-10:      http://hl7.org/fhir/sid/icd-10
      LOINC:       http://loinc.org   (vitals)
      NAPPI:       http://surgiscan.co.za/nappi   (custom — NAPPI isn't HL7-official)
  • Defensive: missing fields are dropped from the output (FHIR spec lets them
    be absent), never defaulted to 'N/A' or similar — keeps the export clean.

NOT mapped in v1 (deliberate):
  • Procedures, immunizations — defer to v2 expansion
  • Practitioner / Organization references — would require reading user_profiles
  • Composition resource — only needed for Bundle type='document'
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fhir.resources.R4B.allergyintolerance import AllergyIntolerance
from fhir.resources.R4B.bundle import Bundle, BundleEntry
from fhir.resources.R4B.codeableconcept import CodeableConcept
from fhir.resources.R4B.coding import Coding
from fhir.resources.R4B.address import Address
from fhir.resources.R4B.condition import Condition
from fhir.resources.R4B.contactpoint import ContactPoint
from fhir.resources.R4B.coverage import Coverage
from fhir.resources.R4B.encounter import Encounter
from fhir.resources.R4B.humanname import HumanName
from fhir.resources.R4B.identifier import Identifier
from fhir.resources.R4B.medicationstatement import MedicationStatement
from fhir.resources.R4B.observation import Observation
from fhir.resources.R4B.patient import Patient
from fhir.resources.R4B.quantity import Quantity
from fhir.resources.R4B.reference import Reference

# Coding system URLs
SYS_ICD10 = "http://hl7.org/fhir/sid/icd-10"
SYS_LOINC = "http://loinc.org"
SYS_NAPPI = "http://surgiscan.co.za/nappi"
SYS_SURGISCAN_PATIENT = "http://surgiscan.co.za/patient-id"

# Severity mappings: SurgiScan severity → FHIR criticality
SEVERITY_TO_CRITICALITY = {
    "mild": "low",
    "moderate": "low",
    "severe": "high",
    "life_threatening": "high",
}

# Common LOINC codes for vital signs
# Keys MUST match the vitals_history / vitals-table field names the export
# adapter emits (DS-EXPORT-5: they previously used systolic_bp/temperature/
# weight, so almost no vital was ever exported).
LOINC_VITALS = {
    "bp_systolic":           ("8480-6",  "Systolic blood pressure",       "mm[Hg]"),
    "bp_diastolic":          ("8462-4",  "Diastolic blood pressure",      "mm[Hg]"),
    "heart_rate":            ("8867-4",  "Heart rate",                    "/min"),
    "temperature_c":         ("8310-5",  "Body temperature",              "Cel"),
    "respiratory_rate":      ("9279-1",  "Respiratory rate",              "/min"),
    "oxygen_saturation":     ("59408-5", "Oxygen saturation in arterial blood by pulse oximetry", "%"),
    "weight_kg":             ("29463-7", "Body weight",                   "kg"),
    "height_cm":             ("8302-2",  "Body height",                   "cm"),
    "bmi":                   ("39156-5", "Body mass index (BMI)",         "kg/m2"),
    "hba1c":                 ("4548-4",  "Hemoglobin A1c/Hemoglobin.total in Blood", "%"),
    "blood_glucose_fasting": ("1558-6",  "Fasting glucose [Mass/volume] in Serum or Plasma", "mg/dL"),
}


def _patient_reference(patient_id: str) -> Reference:
    return Reference(reference=f"Patient/{patient_id}")


def map_patient(row: Dict[str, Any]) -> Patient:
    """Map a SurgiScan `patients` row to a FHIR Patient resource."""
    name = HumanName(
        family=row.get("last_name") or row.get("surname") or None,
        given=[row["first_name"]] if row.get("first_name") else None,
    )

    identifiers = [
        Identifier(system=SYS_SURGISCAN_PATIENT, value=row["id"]),
    ]
    if row.get("id_number"):
        # SA national ID — use the South African home affairs OID where possible.
        identifiers.append(Identifier(system="urn:oid:2.16.840.1.113883.4.301", value=row["id_number"]))

    # Contact details (DS-EXPORT-2): carry validated phone/email/address into
    # the bundle — previously dropped, leaving the exported record incomplete.
    telecom = []
    phone = row.get("contact_number") or row.get("telephone_cell")
    if phone:
        telecom.append(ContactPoint(system="phone", value=str(phone)))
    if row.get("email"):
        telecom.append(ContactPoint(system="email", value=str(row["email"])))
    address = [Address(text=str(row["address"]))] if row.get("address") else None

    p = Patient(
        id=row["id"],
        identifier=identifiers,
        name=[name],
        gender=_normalise_gender(row.get("gender")),
        birthDate=row.get("date_of_birth") or row.get("dob"),
        telecom=telecom or None,
        address=address,
    )
    return p


def _normalise_gender(raw: Optional[str]) -> Optional[str]:
    """FHIR gender enum: male | female | other | unknown."""
    if not raw:
        return None
    r = str(raw).strip().lower()
    if r in {"m", "male"}:
        return "male"
    if r in {"f", "female"}:
        return "female"
    if r in {"o", "other"}:
        return "other"
    return "unknown"


def map_allergy(row: Dict[str, Any], patient_id: str) -> AllergyIntolerance:
    """Map a SurgiScan `allergies` row to a FHIR AllergyIntolerance resource."""
    code = CodeableConcept(text=row.get("substance"))
    severity = (row.get("severity") or "").lower()

    return AllergyIntolerance(
        id=row["id"],
        clinicalStatus=CodeableConcept(coding=[Coding(
            system="http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical",
            code="active" if row.get("status") == "active" else "inactive",
        )]),
        code=code,
        patient=_patient_reference(patient_id),
        criticality=SEVERITY_TO_CRITICALITY.get(severity),
        recordedDate=row.get("created_at"),
        note=[{"text": row["notes"]}] if row.get("notes") else None,
    )


def map_diagnosis(row: Dict[str, Any], patient_id: str) -> Condition:
    """Map a SurgiScan `diagnoses` row to a FHIR Condition resource."""
    code_codings: List[Coding] = []
    if row.get("icd10_code"):
        code_codings.append(Coding(
            system=SYS_ICD10,
            code=row["icd10_code"],
            display=row.get("description") or row.get("name"),
        ))

    return Condition(
        id=row["id"],
        clinicalStatus=CodeableConcept(coding=[Coding(
            system="http://terminology.hl7.org/CodeSystem/condition-clinical",
            code=_normalise_condition_status(row.get("status")),
        )]),
        code=CodeableConcept(
            coding=code_codings or None,
            text=row.get("description") or row.get("name"),
        ),
        subject=_patient_reference(patient_id),
        recordedDate=row.get("created_at"),
    )


def map_coverage(row: Dict[str, Any], patient_id: str) -> Coverage:
    """Map a medical-aid record to a FHIR Coverage resource (DS-EXPORT-3).
    row keys: scheme_name / name, member_number, plan."""
    # FHIR R4(B) Coverage: status + beneficiary + payor are the load-bearing
    # fields (payor is required in R4; it became `insurer` in R5).
    scheme = row.get("scheme_name") or row.get("name") or row.get("medical_aid")
    cov = Coverage(
        status="active",
        beneficiary=_patient_reference(patient_id),
        payor=[Reference(display=scheme or "Unknown scheme")],
    )
    if row.get("member_number"):
        cov.subscriberId = str(row["member_number"])
    return cov


def _normalise_condition_status(raw: Optional[str]) -> str:
    """FHIR condition-clinical: active | recurrence | relapse | inactive | remission | resolved."""
    if not raw:
        return "active"
    r = raw.strip().lower()
    return r if r in {"active", "recurrence", "relapse", "inactive", "remission", "resolved"} else "active"


def map_medication(row: Dict[str, Any], patient_id: str) -> MedicationStatement:
    """Map a SurgiScan `current_medications` (or `patient_medications`) row to a FHIR MedicationStatement."""
    med_codings: List[Coding] = []
    if row.get("nappi_code"):
        med_codings.append(Coding(
            system=SYS_NAPPI,
            code=row["nappi_code"],
            display=row.get("medication_name"),
        ))

    return MedicationStatement(
        id=row["id"],
        status=row.get("status") or "active",
        # FHIR R4 uses medicationCodeableConcept (the choice element); R5
        # replaced it with `medication` (CodeableReference).
        medicationCodeableConcept=CodeableConcept(
            coding=med_codings or None,
            text=row.get("medication_name") or row.get("generic_name"),
        ),
        subject=_patient_reference(patient_id),
        dosage=[{"text": _build_dosage_text(row)}] if _build_dosage_text(row) else None,
    )


def _build_dosage_text(row: Dict[str, Any]) -> str:
    """Compose human-readable dosage string from row fields."""
    parts = []
    for k in ("dosage", "frequency", "duration", "quantity"):
        v = row.get(k)
        if v:
            parts.append(str(v))
    return " ".join(parts).strip()


def map_vitals_observations(row: Dict[str, Any], patient_id: str) -> List[Observation]:
    """A single vitals row produces multiple FHIR Observations — one per measurement.
    LOINC codes per the LOINC_VITALS table at module top."""
    out: List[Observation] = []
    effective = row.get("recorded_at") or row.get("created_at")

    for field, (loinc_code, display, unit) in LOINC_VITALS.items():
        v = row.get(field)
        if v is None or v == "":
            continue
        try:
            value = float(str(v).replace(",", "."))  # SA decimal comma (e.g. 36,7)
        except (ValueError, TypeError):
            continue

        obs = Observation(
            # FHIR resource ids allow only [A-Za-z0-9-.] — field names have
            # underscores (bp_systolic), so map them to hyphens.
            id=f"{row['id']}-{field.replace('_', '-')}",
            status="final",
            code=CodeableConcept(coding=[Coding(system=SYS_LOINC, code=loinc_code, display=display)]),
            subject=_patient_reference(patient_id),
            effectiveDateTime=effective,
            valueQuantity=Quantity(value=value, unit=unit, system="http://unitsofmeasure.org", code=unit),
        )
        out.append(obs)
    return out


def map_encounter(row: Dict[str, Any], patient_id: str) -> Encounter:
    """Map a SurgiScan `encounters` row to a FHIR Encounter resource."""
    return Encounter(
        id=row["id"],
        status=_normalise_encounter_status(row.get("status")),
        # FHIR R4(B) Encounter.class is a SINGLE Coding (`class_fhir` is the
        # fhir.resources alias for the `class` keyword). R5 made it a list of
        # CodeableConcept; R4 uses one Coding, and the period is `period`.
        class_fhir=Coding(
            system="http://terminology.hl7.org/CodeSystem/v3-ActCode",
            code="AMB",
            display="ambulatory",
        ),
        subject=_patient_reference(patient_id),
        period={"start": row.get("encounter_date") or row.get("consultation_date") or row.get("created_at")},
    )


def _normalise_encounter_status(raw: Optional[str]) -> str:
    """FHIR R4 encounter status: planned | arrived | triaged | in-progress | onleave | finished | cancelled | entered-in-error | unknown."""
    if not raw:
        return "finished"
    r = raw.strip().lower()
    mapping = {
        "in-progress": "in-progress",
        "in_progress": "in-progress",
        "completed":   "finished",
        "finished":    "finished",
        "billed":      "finished",
        "cancelled":   "cancelled",
        "no_show":     "cancelled",
    }
    return mapping.get(r, "finished")


def build_patient_bundle(
    patient_row: Dict[str, Any],
    allergies: List[Dict[str, Any]],
    diagnoses: List[Dict[str, Any]],
    medications: List[Dict[str, Any]],
    vitals: List[Dict[str, Any]],
    encounters: List[Dict[str, Any]],
    coverage: Optional[Dict[str, Any]] = None,
) -> Bundle:
    """Assemble all of a patient's resources into a FHIR Bundle of type 'searchset'.

    Returns a Bundle object — caller calls .model_dump(by_alias=True, exclude_none=True)
    or .model_dump_json(...) for serialisation.
    """
    patient_id = patient_row["id"]

    entries: List[BundleEntry] = []

    # Patient first
    entries.append(BundleEntry(resource=map_patient(patient_row)))

    for a in allergies or []:
        try:
            entries.append(BundleEntry(resource=map_allergy(a, patient_id)))
        except Exception:
            continue  # Drop unmappable rows rather than fail the whole export

    for d in diagnoses or []:
        try:
            entries.append(BundleEntry(resource=map_diagnosis(d, patient_id)))
        except Exception:
            continue

    for m in medications or []:
        try:
            entries.append(BundleEntry(resource=map_medication(m, patient_id)))
        except Exception:
            continue

    for v in vitals or []:
        try:
            for obs in map_vitals_observations(v, patient_id):
                entries.append(BundleEntry(resource=obs))
        except Exception:
            continue

    for e in encounters or []:
        try:
            entries.append(BundleEntry(resource=map_encounter(e, patient_id)))
        except Exception:
            continue

    # Coverage (medical aid) — DS-EXPORT-3. Only when a scheme/member is present.
    if coverage and (coverage.get("scheme_name") or coverage.get("name") or coverage.get("member_number")):
        try:
            entries.append(BundleEntry(resource=map_coverage(coverage, patient_id)))
        except Exception:
            pass

    bundle = Bundle(
        type="searchset",
        timestamp=datetime.utcnow().isoformat() + "Z",
        total=len(entries),
        entry=entries,
    )
    return bundle


__all__ = [
    "build_patient_bundle",
    "map_patient",
    "map_allergy",
    "map_diagnosis",
    "map_medication",
    "map_vitals_observations",
    "map_encounter",
]
