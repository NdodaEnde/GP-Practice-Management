"""
GP Patient EHR Extraction Schema — Full Tabbed Architecture
South African private practice (Egoli File + HPCSA SOAP notes)

Each top-level sub-model maps to:
  1. A database table (see db/models.py)
  2. A UI tab in the validation panel (see EHRValidationPanel.jsx)
  3. A section in the ADE extraction prompt

ZDR_REQUIRED = True — all patient data is PHI
DOCUMENT_TYPE = "GP_PATIENT_RECORD"

Drop-in for PreTripChecklistExtraction in groundtruth-clean/backend/main.py:
  Replace: schema = pydantic_to_json_schema(PreTripChecklistExtraction)
  With:    schema = pydantic_to_json_schema(GPPatientRecordExtraction)
"""

from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum


# ══════════════════════════════════════════════════════════════════════════════
# ENUMS
# ══════════════════════════════════════════════════════════════════════════════

class TitleEnum(str, Enum):
    MR = "Mr"
    MRS = "Mrs"
    MISS = "Miss"
    DR = "Dr"
    PROF = "Prof"
    OTHER = "Other"

class MaritalStatusEnum(str, Enum):
    SINGLE = "S"
    MARRIED = "M"
    DIVORCED = "D"
    WIDOWED = "W"

class SexEnum(str, Enum):
    MALE = "M"
    FEMALE = "F"

class DiagnosisStatusEnum(str, Enum):
    ACTIVE = "active"
    CHRONIC = "chronic"
    RESOLVED = "resolved"
    SUSPECTED = "suspected"

class MedicationStatusEnum(str, Enum):
    ACTIVE = "active"
    DISCONTINUED = "discontinued"
    COMPLETED = "completed"
    PRN = "prn"

class InvestigationStatusEnum(str, Enum):
    ORDERED = "ordered"
    RESULTED = "resulted"
    REVIEWED = "reviewed"
    PENDING = "pending"

class ReferralUrgencyEnum(str, Enum):
    ROUTINE = "routine"
    URGENT = "urgent"
    EMERGENCY = "emergency"

class ReferralStatusEnum(str, Enum):
    PENDING = "pending"
    SEEN = "seen"
    DECLINED = "declined"
    UNKNOWN = "unknown"


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — DEMOGRAPHICS & REGISTRATION
# DB table: patients, patient_medical_aid, patient_contacts, patient_dependents
# ══════════════════════════════════════════════════════════════════════════════

class PatientDemographics(BaseModel):
    """
    Cover page patient identifying information.
    Maps to: patients table
    """
    file_number: Optional[str] = Field(
        None,
        description="Practice-assigned file or computer number in the top-right 'FILE / COMPUTER NO' field — the practice's unique patient identifier e.g. GP-2024-0847"
    )
    full_names: Optional[str] = Field(
        None,
        description="Patient's first name(s) from the 'Full Name/s' field in PATIENT DETAILS section"
    )
    surname: Optional[str] = Field(
        None,
        description="Patient surname from the 'Surname' field in PATIENT DETAILS section"
    )
    title: Optional[TitleEnum] = Field(
        None,
        description="Title indicated by checkbox: Mr, Mrs, Miss, Dr, Prof, or Other"
    )
    id_number: Optional[str] = Field(
        None,
        description="South African 13-digit ID number from the 'ID No.' field"
    )
    date_of_birth: Optional[str] = Field(
        None,
        description="Date of birth — derive from ID number digits 1-6 (YYMMDD) if not explicitly written. Format YYYY-MM-DD"
    )
    sex: Optional[SexEnum] = Field(
        None,
        description="Sex — derive from ID number digits 7-10: 0000-4999 = Female, 5000-9999 = Male"
    )
    email: Optional[str] = Field(None, description="Patient email from the 'E-Mail' field in PATIENT DETAILS")
    telephone_cell: Optional[str] = Field(None, description="Patient cell/telephone from 'Tel./Cell' field in PATIENT DETAILS")
    address: Optional[str] = Field(None, description="Patient residential address")


class AccountResponsible(BaseModel):
    """
    Person responsible for the account — main medical aid member if patient is a dependent.
    Maps to: patients table (account_responsible columns)
    """
    full_names: Optional[str] = Field(
        None,
        description="Full names from 'PERSON RESPONSIBLE FOR ACCOUNT' section — may differ from patient if patient is a dependent"
    )
    surname: Optional[str] = Field(None, description="Surname of account responsible person")
    title: Optional[TitleEnum] = Field(None, description="Title of account responsible person")
    id_number: Optional[str] = Field(None, description="ID number of account responsible person")
    date_of_birth: Optional[str] = Field(None, description="Date of birth of account responsible person, YYYY-MM-DD")
    marital_status: Optional[MaritalStatusEnum] = Field(
        None,
        description="Marital status checkbox: S=Single, M=Married, D=Divorced, W=Widowed"
    )
    telephone_cell: Optional[str] = Field(None, description="Cell number of account responsible person")
    home_address: Optional[str] = Field(None, description="Home address of account responsible person")
    employer: Optional[str] = Field(None, description="Employer name from 'Name of Employer' field")
    occupation: Optional[str] = Field(None, description="Occupation")
    work_address: Optional[str] = Field(None, description="Work address")


class MedicalAid(BaseModel):
    """
    Medical aid scheme details.
    Maps to: patient_medical_aid table
    """
    main_member_name: Optional[str] = Field(
        None,
        description="Main member name and surname from 'MEDICAL AID' section — 'Main Members Name & Surname' field"
    )
    scheme_name: Optional[str] = Field(
        None,
        description="Medical aid scheme name e.g. Discovery Health, Bonitas, GEMS, Momentum, Medihelp, Fedhealth"
    )
    member_number: Optional[str] = Field(
        None,
        description="Medical aid membership/card number from 'Number' field"
    )
    plan: Optional[str] = Field(
        None,
        description="Medical aid plan name e.g. KeyCare Plus, Executive Plan, Classic Comprehensive, Essential"
    )
    hospital_plan: Optional[str] = Field(
        None,
        description="Hospital plan if separately noted in 'Other eg. Hospital Plan' field"
    )


class NextOfKin(BaseModel):
    """Maps to: patient_contacts table (contact_type = 'next_of_kin')"""
    name: Optional[str] = Field(None, description="Full name from 'NEAREST FAMILY / FRIEND' section")
    relationship: Optional[str] = Field(None, description="Relationship: Spouse, Parent, Sibling, Friend")
    address: Optional[str] = Field(None, description="Address of next of kin")
    email: Optional[str] = Field(None, description="Email of next of kin")
    telephone_cell: Optional[str] = Field(None, description="Contact number of next of kin")


class Dependent(BaseModel):
    """Maps to: patient_dependents table"""
    name: Optional[str] = Field(
        None,
        description="Dependent's full name from the Name column in DEPENDENTS ON MEDICAL AID table"
    )
    sex: Optional[SexEnum] = Field(None, description="Sex: M or F from Sex column")
    date_of_birth: Optional[str] = Field(
        None,
        description="Date of birth from Date of Birth column in dependents table, YYYY-MM-DD"
    )
    dependency_code: Optional[str] = Field(
        None,
        description="Medical aid dependency code from Dep. Code column"
    )
    allergies: Optional[str] = Field(
        None,
        description="Known allergies from Allergies column in dependents table"
    )


class ConsentDeclaration(BaseModel):
    """Maps to: patients table (consent columns)"""
    patient_signature_present: Optional[bool] = Field(
        None,
        description="Whether the patient signature line in CLIENT CONSENT & DECLARATION section is signed"
    )
    consent_date: Optional[str] = Field(
        None,
        description="Date written next to patient signature in consent section, YYYY-MM-DD"
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — CLINICAL HISTORY
# DB table: clinical_history
# ══════════════════════════════════════════════════════════════════════════════

class ClinicalHistory(BaseModel):
    """
    Patient's medical background — synthesised from cover page and all consultation notes.
    Maps to: clinical_history table (upserted — not duplicated on rescan)
    """
    chief_complaints: Optional[List[str]] = Field(
        None,
        description="Primary complaints or reasons for initial registration — from first consultation note or cover page notes"
    )
    known_allergies: Optional[List[str]] = Field(
        None,
        description="All allergies mentioned anywhere in the record — cover page, dependents table, or consultation notes. E.g. ['Penicillin', 'Sulfonamides', 'Aspirin']"
    )
    chronic_conditions: Optional[List[str]] = Field(
        None,
        description="Conditions that appear across multiple consultations or are explicitly labelled chronic/ongoing e.g. ['Hypertension', 'Type 2 Diabetes Mellitus', 'Asthma']"
    )
    past_medical_history: Optional[str] = Field(
        None,
        description="Previous illnesses, hospitalisations, or significant medical events noted in consultation histories. Often written as 'PMHx:' in SA clinical notes"
    )
    surgical_history: Optional[str] = Field(
        None,
        description="Previous surgeries or procedures noted anywhere in the record"
    )
    family_history: Optional[str] = Field(
        None,
        description="Family medical history noted in consultation notes — often written as 'FHx:'"
    )
    social_history: Optional[str] = Field(
        None,
        description="Social history: smoking status, alcohol use, occupation risk factors — often written as 'SHx:' in SA notes"
    )
    obstetric_history: Optional[str] = Field(
        None,
        description="For female patients: gravida, para, last menstrual period if noted — 'OBHx:' or 'LMP:'"
    )
    immunisation_notes: Optional[str] = Field(
        None,
        description="Any vaccination or immunisation records noted in the folder"
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — VITALS
# DB table: vitals (one row per consultation_date)
# ══════════════════════════════════════════════════════════════════════════════

class VitalsReading(BaseModel):
    """
    Vital signs from a single consultation's Objective section.
    Maps to: vitals table
    SA doctors commonly record: T (temperature), HR, BP, O2 Sat, Wt, BMI, RR
    """
    consultation_date: Optional[str] = Field(
        None,
        description="Date of the consultation this vitals reading belongs to, YYYY-MM-DD"
    )
    temperature_c: Optional[str] = Field(
        None,
        description="Temperature in Celsius from O section — written as 'T: 38.1°C' or 'Temp 38.1'"
    )
    heart_rate: Optional[str] = Field(
        None,
        description="Heart rate / pulse in beats per minute — written as 'HR: 88' or 'P: 88' or 'Pulse: 88'"
    )
    bp_systolic: Optional[str] = Field(
        None,
        description="Systolic blood pressure — the top number in 'BP: 124/78', extract only 124"
    )
    bp_diastolic: Optional[str] = Field(
        None,
        description="Diastolic blood pressure — the bottom number in 'BP: 124/78', extract only 78"
    )
    respiratory_rate: Optional[str] = Field(
        None,
        description="Respiratory rate — written as 'RR: 18' or 'Resp: 18'"
    )
    oxygen_saturation: Optional[str] = Field(
        None,
        description="Oxygen saturation percentage — written as 'O2 Sat: 98%' or 'SpO2: 98%' or 'SATs: 98%'"
    )
    weight_kg: Optional[str] = Field(
        None,
        description="Patient weight in kilograms — written as 'Wt: 87kg' or 'Weight: 87'"
    )
    height_cm: Optional[str] = Field(
        None,
        description="Patient height in centimetres — written as 'Ht: 175cm'"
    )
    bmi: Optional[str] = Field(
        None,
        description="Body mass index — written as 'BMI: 29.4'"
    )
    blood_glucose_fasting: Optional[str] = Field(
        None,
        description="Fasting blood sugar or glucose — written as 'FBS: 9.2 mmol/L' or 'RBS:' or 'BGL:'"
    )
    hba1c: Optional[str] = Field(
        None,
        description="HbA1c percentage — written as 'HbA1c: 7.8%' — common in diabetic patient notes"
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — DIAGNOSES
# DB table: diagnoses (one row per diagnosis per consultation)
# ══════════════════════════════════════════════════════════════════════════════

class Diagnosis(BaseModel):
    """
    Single diagnosis from a consultation's Assessment section.
    Maps to: diagnoses table
    SA doctors commonly write ICD-10 codes explicitly e.g. 'ICD-10: J06.9'
    """
    consultation_date: Optional[str] = Field(
        None,
        description="Date of the consultation where this diagnosis was recorded, YYYY-MM-DD"
    )
    icd10_code: Optional[str] = Field(
        None,
        description="ICD-10 code explicitly written in the Assessment section e.g. J06.9, I10, E11.9, J45.0"
    )
    description: Optional[str] = Field(
        None,
        description="Diagnosis description from Assessment section e.g. 'URTI', 'Hypertension', 'Type 2 Diabetes Mellitus', 'Viral pharyngitis'"
    )
    status: Optional[DiagnosisStatusEnum] = Field(
        None,
        description="Whether this is active, chronic (recurring across visits), resolved, or suspected based on context"
    )
    differential_notes: Optional[str] = Field(
        None,
        description="Any differential diagnosis notes or 'query' diagnoses written e.g. '?Pneumonia', 'R/O TB'"
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — MEDICATIONS & PRESCRIPTIONS
# DB table: medications (one row per prescription line)
# ══════════════════════════════════════════════════════════════════════════════

class Medication(BaseModel):
    """
    Single medication line from a consultation's Plan section or prescription script.
    Maps to: medications table
    SA prescription shorthand: OD=once daily, BD=twice daily, TDS=three times daily,
    QID=four times daily, PRN=as needed, x5/7=for 5 days, x2/52=for 2 weeks
    """
    consultation_date: Optional[str] = Field(
        None,
        description="Date this medication was prescribed, YYYY-MM-DD"
    )
    drug_name: Optional[str] = Field(
        None,
        description="Medication name — generic or trade name e.g. 'Panado', 'Paracetamol', 'Amlodipine', 'Metformin XR', 'Amoxicillin'"
    )
    dosage: Optional[str] = Field(
        None,
        description="Dose amount and unit e.g. '1g', '500mg', '10ml', '10mg'"
    )
    frequency: Optional[str] = Field(
        None,
        description="Dosing frequency using SA clinical shorthand: OD (once daily), BD (twice daily), TDS (three times daily), QID (four times), PRN (as needed), STAT (immediately)"
    )
    duration: Optional[str] = Field(
        None,
        description="Duration of prescription using SA shorthand: x5/7 (5 days), x2/52 (2 weeks), x1/12 (1 month), Ongoing, Chronic"
    )
    route: Optional[str] = Field(
        None,
        description="Route of administration if specified: oral, topical, IV, IM, inhaled, sublingual"
    )
    instructions: Optional[str] = Field(
        None,
        description="Additional instructions e.g. 'take with food', 'avoid alcohol', 'taper dose'"
    )
    status: Optional[MedicationStatusEnum] = Field(
        None,
        description="Active (ongoing), completed (short course finished), discontinued (stopped), or PRN (as needed)"
    )
    prescribed_by: Optional[str] = Field(
        None,
        description="Prescribing doctor name or initials if identifiable from the note or signature"
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 6 — PROGRESS NOTES
# DB table: progress_notes (one row per consultation_date)
# ══════════════════════════════════════════════════════════════════════════════

class ProgressNote(BaseModel):
    """
    Full SOAP note for a single consultation.
    Maps to: progress_notes table
    This is the narrative record — one entry per visit date.
    """
    consultation_date: Optional[str] = Field(
        None,
        description="Date written at the top of this consultation note, YYYY-MM-DD"
    )
    subjective: Optional[str] = Field(
        None,
        description="Patient's complaint and history — the S section of SOAP notes. Written after 'S:' or as the opening paragraph of the consultation. Includes the presenting complaint, duration, and relevant history"
    )
    objective: Optional[str] = Field(
        None,
        description="Clinical examination findings — the O section. Written after 'O:'. Includes vital signs, physical examination findings. E.g. 'Throat: erythematous. Chest: clear bilaterally'"
    )
    assessment: Optional[str] = Field(
        None,
        description="Clinical impression or diagnosis — the A section. Written after 'A:'. May include ICD-10 codes, differential diagnoses, clinical reasoning"
    )
    plan: Optional[str] = Field(
        None,
        description="Treatment plan — the P section. Written after 'P:'. Includes prescriptions, lifestyle advice, follow-up instructions, referrals"
    )
    follow_up_instruction: Optional[str] = Field(
        None,
        description="Specific follow-up instruction e.g. 'RTF 48hrs if no improvement', 'Follow-up 3/12', 'Review bloods in 6 weeks'"
    )
    doctor_signed: Optional[bool] = Field(
        None,
        description="Whether a doctor signature or initials appears at the bottom of this consultation note"
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 7 — LABS & INVESTIGATIONS
# DB table: investigations (one row per test)
# ══════════════════════════════════════════════════════════════════════════════

class Investigation(BaseModel):
    """
    Lab result or investigation — from inline notes or loose lab slips in folder.
    Maps to: investigations table
    Common SA lab shorthand: FBC=full blood count, U&E=urea & electrolytes,
    LFT=liver function, TFT=thyroid function, HbA1c, lipogram, CXR, ECG, USS
    """
    consultation_date: Optional[str] = Field(
        None,
        description="Date the investigation was ordered or result was reviewed, YYYY-MM-DD"
    )
    test_name: Optional[str] = Field(
        None,
        description="Name of the test or investigation e.g. 'HbA1c', 'FBC', 'U&E', 'Lipogram', 'CXR', 'ECG', 'Creatinine', 'TSH', 'Urine MCS'"
    )
    result_value: Optional[str] = Field(
        None,
        description="The numeric or descriptive result e.g. '7.8%', '9.2 mmol/L', '88 μmol/L', 'Normal', 'Positive'"
    )
    result_unit: Optional[str] = Field(
        None,
        description="Unit of measurement e.g. 'mmol/L', '%', 'μmol/L', 'g/dL', 'IU/L'"
    )
    reference_range: Optional[str] = Field(
        None,
        description="Normal reference range if noted e.g. '< 7.0%', '3.9–5.5 mmol/L'. Often noted in brackets after result"
    )
    result_interpretation: Optional[str] = Field(
        None,
        description="Doctor's interpretation if written e.g. 'Improved', 'Elevated', 'Within range', 'Suboptimal'"
    )
    status: Optional[InvestigationStatusEnum] = Field(
        None,
        description="Ordered (test requested), resulted (results received), reviewed (doctor reviewed results), pending"
    )
    lab_name: Optional[str] = Field(
        None,
        description="Laboratory that performed the test if noted e.g. 'PathCare', 'Lancet Laboratories', 'Ampath'"
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 8 — REFERRALS
# DB table: referrals (one row per referral)
# ══════════════════════════════════════════════════════════════════════════════

class Referral(BaseModel):
    """
    Specialist referral or allied health referral from Plan section.
    Maps to: referrals table
    Common SA referral patterns: 'Refer to cardiologist', 'Refer dietician',
    'Refer physio', 'Refer for CXR', 'Refer to Tembisa Hospital'
    """
    referral_date: Optional[str] = Field(
        None,
        description="Date referral was made — from the consultation note date, YYYY-MM-DD"
    )
    referred_to: Optional[str] = Field(
        None,
        description="Specialty or professional referred to e.g. 'Cardiologist', 'Dietician', 'Physiotherapist', 'Ophthalmologist', 'Tembisa Hospital Casualty'"
    )
    reason: Optional[str] = Field(
        None,
        description="Clinical reason for referral e.g. 'weight management', 'suboptimal BP control', 'diabetic eye screening'"
    )
    urgency: Optional[ReferralUrgencyEnum] = Field(
        None,
        description="Urgency: routine (non-urgent), urgent (within days), emergency (immediate)"
    )
    referral_letter_present: Optional[bool] = Field(
        None,
        description="Whether a referral letter is present as a loose document in the folder"
    )
    outcome: Optional[str] = Field(
        None,
        description="Outcome if noted in a later consultation e.g. 'Patient seen by cardiologist 12/03/2024', 'Declined by patient'"
    )
    status: Optional[ReferralStatusEnum] = Field(
        None,
        description="Pending (referral made but outcome unknown), seen, declined by patient, or unknown"
    )


# ══════════════════════════════════════════════════════════════════════════════
# MASTER SCHEMA — composes all 8 tabs
# ══════════════════════════════════════════════════════════════════════════════

class GPPatientRecordExtraction(BaseModel):
    """
    Complete EHR extraction from a South African GP patient folder.

    Architecture: each sub-model maps to a DB table AND a UI tab.

    Tab 1  Demographics  → patients, patient_medical_aid, patient_contacts, patient_dependents
    Tab 2  Hx & History  → clinical_history
    Tab 3  Vitals        → vitals (one row per consultation)
    Tab 4  Diagnoses     → diagnoses (one row per diagnosis per consultation)
    Tab 5  Medications   → medications (one row per prescription line)
    Tab 6  Progress Notes→ progress_notes (one row per consultation)
    Tab 7  Labs & Invest → investigations
    Tab 8  Referrals     → referrals

    ZDR REQUIRED: True — PHI throughout.
    All fields Optional — ADE assigns confidence per field.
    Validators review low-confidence fields before DB write.
    """

    # ── TAB 1: Demographics ───────────────────────────────────────────────────
    patient_demographics: Optional[PatientDemographics] = Field(
        None,
        description="Patient identifying information from the PATIENT DETAILS section at the top of the cover page"
    )
    account_responsible: Optional[AccountResponsible] = Field(
        None,
        description="Person responsible for account payment from PERSON RESPONSIBLE FOR ACCOUNT section"
    )
    medical_aid: Optional[MedicalAid] = Field(
        None,
        description="Medical aid scheme details from the MEDICAL AID section"
    )
    next_of_kin: Optional[NextOfKin] = Field(
        None,
        description="Emergency contact from the NEAREST FAMILY / FRIEND section"
    )
    dependents: Optional[List[Dependent]] = Field(
        None,
        description="List of dependents from the DEPENDENTS ON MEDICAL AID table"
    )
    consent: Optional[ConsentDeclaration] = Field(
        None,
        description="Patient consent signature and date from CLIENT CONSENT & DECLARATION"
    )

    # ── TAB 2: Clinical History ───────────────────────────────────────────────
    clinical_history: Optional[ClinicalHistory] = Field(
        None,
        description="Synthesised medical background drawn from cover page and all consultation notes"
    )

    # ── TAB 3: Vitals ─────────────────────────────────────────────────────────
    vitals_history: Optional[List[VitalsReading]] = Field(
        None,
        description="Vital signs readings from the Objective (O) section of each consultation note — one entry per visit date"
    )

    # ── TAB 4: Diagnoses ──────────────────────────────────────────────────────
    diagnoses: Optional[List[Diagnosis]] = Field(
        None,
        description="All diagnoses from Assessment (A) sections across all consultation notes — include ICD-10 codes where explicitly written"
    )

    # ── TAB 5: Medications ────────────────────────────────────────────────────
    medications: Optional[List[Medication]] = Field(
        None,
        description="All medications prescribed across all consultation notes — one entry per prescription line in the Plan (P) sections"
    )

    # ── TAB 6: Progress Notes ─────────────────────────────────────────────────
    progress_notes: Optional[List[ProgressNote]] = Field(
        None,
        description="Full SOAP note for each consultation date — one entry per visit in chronological order"
    )

    # ── TAB 7: Labs & Investigations ──────────────────────────────────────────
    investigations: Optional[List[Investigation]] = Field(
        None,
        description="Lab results and investigations from Objective sections and any loose lab slips in the folder"
    )

    # ── TAB 8: Referrals ──────────────────────────────────────────────────────
    referrals: Optional[List[Referral]] = Field(
        None,
        description="Specialist or allied health referrals from Plan sections across all consultation notes"
    )
