"""
Medical document schemas for AI extraction.
Refactored from the original Historic_document_processor.py with improvements.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class DocumentType(str, Enum):
    """All supported medical document types"""
    CERTIFICATE_OF_FITNESS = "certificate_of_fitness"
    VISION_TEST = "vision_test"
    AUDIOMETRIC_TEST = "audiometric_test"
    SPIROMETRY_REPORT = "spirometry_report"
    CONSENT_FORM = "consent_form"
    MEDICAL_QUESTIONNAIRE = "medical_questionnaire"


# =============================================================================
# DOCUMENT SCHEMAS
# =============================================================================

class MedicalExaminationTest(BaseModel):
    """Medical test result"""
    test_name: str = Field(description='The name of the medical test.', title='Test Name')
    done: bool = Field(description='Indicates if the test was performed (true if checked/✓, false if X).', title='Test Done')
    result: str = Field(description='The result or outcome of the test.', title='Test Result')


class CertificateOfFitnessSchema(BaseModel):
    """Certificate of Fitness - Complete schema"""
    
    initials_and_surname: str = Field(description="Employee name", title='Initials and Surname')
    id_number: str = Field(description="ID or employee number", title='ID Number')
    company_name: str = Field(description="Company name", title='Company Name')
    examination_date: str = Field(description="Date of examination", title='Date of Examination')
    expiry_date: str = Field(description="Certificate expiry date", title='Expiry Date')
    job_title: str = Field(description="Employee job title", title='Job Title')
    pre_employment: bool = Field(
        description='Indicates if the examination is for pre-employment (true if checked, false otherwise).',
        title='Pre-Employment'
    )
    periodical: bool = Field(
        description='Indicates if the examination is a periodical check (true if checked, false otherwise).',
        title='Periodical'
    )
    exit: bool = Field(
        description='Indicates if the examination is for exit (true if checked, false otherwise).',
        title='Exit'
    )
    medical_examination_tests: List[MedicalExaminationTest] = Field(
        description='A list of tests conducted during the medical examination, including their status and results.',
        title='Medical Examination Conducted Tests'
    )
    referred_or_follow_up_actions: List[str] = Field(
        description='A list of actions or recommendations for follow-up or referral.',
        title='Referred or Follow Up Actions'
    )
    review_date: str = Field(description='The date scheduled for review, if specified.', title='Review Date')
    restrictions: List[str] = Field(
        description='A list of restrictions or special conditions applicable to the employee.',
        title='Restrictions'
    )
    medical_fitness_declaration: str = Field(
        description='The outcome of the medical fitness assessment.',
        title='Medical Fitness Declaration'
    )
    comments: str = Field(description='Additional comments or notes provided by the practitioner.', title='Comments')
    signature: str = Field(description="A description or representation of the practitioner's signature.", title='Signature')
    stamp: str = Field(description='A description or representation of the official stamp on the certificate.', title='Stamp')


class VisionTestSchema(BaseModel):
    """Vision Test - Complete schema for eye examinations"""

    document_classification: str = Field(description="Document type: vision test", default="vision_test")
    
    # Patient info
    patient_name: Optional[str] = Field(description="Patient name")
    test_date: Optional[str] = Field(description="Date of vision test")
    occupation: Optional[str] = Field(description="Patient occupation")
    age: Optional[str] = Field(description="Patient age")
    
    # Vision correction
    wears_glasses: Optional[str] = Field(description="Does patient wear glasses")
    wears_contacts: Optional[str] = Field(description="Does patient wear contacts")
    vision_correction_type: Optional[str] = Field(description="Distance only, Reading, Multifocals")
    
    # Visual acuity tests
    right_eye_acuity: Optional[str] = Field(description="Right eye visual acuity results")
    left_eye_acuity: Optional[str] = Field(description="Left eye visual acuity results")
    both_eyes_acuity: Optional[str] = Field(description="Both eyes visual acuity results")
    
    # Color vision tests
    color_vision_severe: Optional[str] = Field(description="Severe color vision test result")
    color_vision_mild: Optional[str] = Field(description="Mild color vision test result")
    
    # Field tests
    horizontal_field_test: Optional[str] = Field(description="Horizontal field test results")
    vertical_field_test: Optional[str] = Field(description="Vertical field test results")
    
    # Coordination and depth tests
    phoria_results: Optional[str] = Field(description="Phoria eye coordination test")
    stereopsis_results: Optional[str] = Field(description="Stereopsis depth perception test")
    
    # Additional tests
    contrast_sensitivity: Optional[str] = Field(description="Contrast sensitivity results")
    glare_recovery: Optional[str] = Field(description="Glare recovery test results")


class AudiometricSummary(BaseModel):
    """Audiometric test summary data"""
    current_plh: Optional[float] = Field(description="Current PLH value")
    previous_plh: Optional[float] = Field(description="Previous PLH value")
    curr_prev_diff: Optional[float] = Field(description="Difference between current and previous PLH")
    baseline_plh: Optional[float] = Field(description="Baseline PLH value")
    bl_shift: Optional[float] = Field(description="Baseline shift value")


class OtoscopicReport(BaseModel):
    """Otoscopic examination report"""
    left_ear: Optional[str] = Field(description="Left ear otoscopic findings")
    right_ear: Optional[str] = Field(description="Right ear otoscopic findings")
    sts_l: Optional[int] = Field(description="STS value for left ear")
    sts_r: Optional[int] = Field(description="STS value for right ear")
    sts_av: Optional[int] = Field(description="Average STS value")
    pass_25db: Optional[str] = Field(description="Pass 25dB test result")


class EarThresholds(BaseModel):
    """Hearing threshold measurements for one ear"""
    freq_500: Optional[int] = Field(description="500 Hz threshold")
    freq_1000: Optional[int] = Field(description="1000 Hz threshold")
    freq_2000: Optional[int] = Field(description="2000 Hz threshold")
    freq_3000: Optional[int] = Field(description="3000 Hz threshold")
    freq_4000: Optional[int] = Field(description="4000 Hz threshold")
    freq_6000: Optional[int] = Field(description="6000 Hz threshold")
    freq_8000: Optional[int] = Field(description="8000 Hz threshold")
    sts: Optional[int] = Field(description="STS value")
    avg: Optional[float] = Field(description="Average threshold")


class AudiometricTestSchema(BaseModel):
    """Audiometric Test Results"""
    document_classification: str = Field(description="Document type: audiometric test results", default="audiometric_test_results")
    name: Optional[str] = Field(description="Patient name")
    id_number: Optional[str] = Field(description="Patient ID number")
    company: Optional[str] = Field(description="Company name")
    occupation: Optional[str] = Field(description="Patient occupation")
    tested_by: Optional[str] = Field(description="Who conducted the test")
    date_of_test: Optional[str] = Field(description="Test date")
    audio_type: Optional[str] = Field(description="Type of audiometric test")
    noise_exposure: Optional[str] = Field(description="Noise exposure level")
    age: Optional[int] = Field(description="Patient age")
    time: Optional[str] = Field(description="Test time")
    exposure_date: Optional[str] = Field(description="Exposure date")
    summary: Optional[AudiometricSummary] = Field(description="Test summary data")
    otoscopic_report: Optional[OtoscopicReport] = Field(description="Otoscopic examination findings")
    left_ear_thresholds: Optional[List[EarThresholds]] = Field(description="Left ear hearing thresholds")
    right_ear_thresholds: Optional[List[EarThresholds]] = Field(description="Right ear hearing thresholds")


class SpirometryResults(BaseModel):
    """Spirometry test measurements"""
    FVC_best_pre: Optional[float] = Field(description="Best pre-test FVC value")
    FEV1_best_pre: Optional[float] = Field(description="Best pre-test FEV1 value")
    FEV1_percent_best_pre: Optional[float] = Field(description="Best pre-test FEV1% value")
    PEFR_best_pre: Optional[float] = Field(description="Best pre-test PEFR value")
    FVC_pred: Optional[float] = Field(description="Predicted FVC value")
    FEV1_pred: Optional[float] = Field(description="Predicted FEV1 value")
    FEV1_percent_pred: Optional[float] = Field(description="Predicted FEV1% value")
    PEFR_pred: Optional[float] = Field(description="Predicted PEFR value")
    FVC_best_post: Optional[float] = Field(description="Best post-test FVC value")
    FEV1_best_post: Optional[float] = Field(description="Best post-test FEV1 value")
    FEV1_percent_best_post: Optional[float] = Field(description="Best post-test FEV1% value")
    PEFR_best_post: Optional[float] = Field(description="Best post-test PEFR value")


class SpirometrySchema(BaseModel):
    """Spirometry Report"""
    document_classification: str = Field(description="Document type: spirometry report", default="spirometry_report")
    name: Optional[str] = Field(description="Patient name")
    id_number: Optional[str] = Field(description="Patient ID number")
    date_of_birth: Optional[str] = Field(description="Patient date of birth")
    age: Optional[int] = Field(description="Patient age")
    gender: Optional[str] = Field(description="Patient gender")
    occupation: Optional[str] = Field(description="Patient occupation")
    company: Optional[str] = Field(description="Company name")
    height_cm: Optional[int] = Field(description="Patient height in cm")
    weight_kg: Optional[int] = Field(description="Patient weight in kg")
    bmi: Optional[float] = Field(description="Body Mass Index")
    ethnic: Optional[str] = Field(description="Patient ethnicity")
    smoking: Optional[str] = Field(description="Smoking history")
    test_date: Optional[str] = Field(description="Test date")
    test_time: Optional[str] = Field(description="Test time")
    operator: Optional[str] = Field(description="Test operator")
    environment: Optional[str] = Field(description="Test environment conditions")
    test_position: Optional[str] = Field(description="Patient position during test")
    spirometry_results: Optional[SpirometryResults] = Field(description="Spirometry measurements")
    interpretation: Optional[str] = Field(description="Test interpretation")
    bronchodilator: Optional[str] = Field(description="Bronchodilator information")


class ConsentFormSchema(BaseModel):
    """Drug Test Consent Form - Complete schema"""
    document_classification: str = Field(description="Document type: consent form", default="consent_form")

    # Patient info
    patient_name: Optional[str] = Field(description="Patient name")
    id_number: Optional[str] = Field(description="Patient ID number")
    consent_date: Optional[str] = Field(description="Date of consent")
    
    # Test details
    test_type: Optional[str] = Field(description="Type of drug test")
    medications_disclosed: Optional[str] = Field(description="Medications disclosed by patient")
    
    # Test procedure confirmations
    sample_confirmation: Optional[str] = Field(description="Confirmation sample is patient's own")
    urine_is_own: Optional[str] = Field(description="Confirmation that urine sample is patient's own")
    test_device_sealed: Optional[str] = Field(description="Confirmation that test device was sealed")
    test_device_expiry_valid: Optional[str] = Field(description="Confirmation that test device expiry was valid")
    test_device_expiry_date: Optional[str] = Field(description="Test device expiry date")
    
    # Test conduct and results
    illicit_drugs_taken: Optional[str] = Field(description="Whether illicit drugs were taken")
    test_conducted_in_presence: Optional[str] = Field(description="Whether test was conducted in patient presence")
    test_result: Optional[str] = Field(description="Test result")
    
    # Signatures
    patient_signature: Optional[str] = Field(description="Patient signature status")
    employee_signature: Optional[str] = Field(description="Employee signature status")
    witness_signature: Optional[str] = Field(description="Witness signature status")
    ohp_signature: Optional[str] = Field(description="OHP signature status")


class MedicalQuestionnaireSchema(BaseModel):
    """Medical Questionnaire - Comprehensive schema"""
    
    document_classification: Optional[str] = Field(description="Document type: medical questionnaire", default="medical_questionnaire")
    
    # Personal Information
    company_name: Optional[str] = Field(description="Company name from header")
    employee_name: Optional[str] = Field(description="Employee name")
    initials: Optional[str] = Field(description="Patient initials")
    surname: Optional[str] = Field(description="Patient surname") 
    first_names: Optional[str] = Field(description="Patient first names")
    id_number: Optional[str] = Field(description="ID number")
    date_of_birth: Optional[str] = Field(description="Date of birth")
    marital_status: Optional[str] = Field(description="Marital status: Single/Married/Divorced/Widow/Widower")
    position: Optional[str] = Field(description="Job position/title")
    department: Optional[str] = Field(description="Department")
    examination_type: Optional[str] = Field(description="Pre-Employment/Baseline/Transfer/Periodical/Exit/Other")
    
    # Medical History - Cardiovascular
    heart_disease_or_high_bp: Optional[bool] = Field(description="Heart disease or high blood pressure")
    epilepsy_or_convulsions: Optional[bool] = Field(description="Epilepsy or convulsions")
    
    # Physical Measurements
    height_cm: Optional[str] = Field(description="Height in cm")
    weight_kg: Optional[str] = Field(description="Weight in kg")
    bmi: Optional[str] = Field(description="BMI value")
    pulse_rate: Optional[str] = Field(description="Pulse rate per minute")
    bp_systolic: Optional[str] = Field(description="Blood pressure systolic")
    bp_diastolic: Optional[str] = Field(description="Blood pressure diastolic")
    
    # Vision/Hearing
    vision_far_right: Optional[str] = Field(description="Vision far right eye")
    vision_far_left: Optional[str] = Field(description="Vision far left eye")
    vision_near_right: Optional[str] = Field(description="Vision near right eye")
    vision_near_left: Optional[str] = Field(description="Vision near left eye")
    audio_plh: Optional[str] = Field(description="Audio PLH value")
    
    # Respiratory
    spirometry_fvc: Optional[str] = Field(description="Spirometry FVC value")
    spirometry_fvc1: Optional[str] = Field(description="Spirometry FVC1 value")
    spirometry_fvc1_fvc_ratio: Optional[str] = Field(description="FVC1/FVC ratio")
    chest_xrays: Optional[str] = Field(description="Chest X-rays results")
    
    # System Examinations
    eyes_clinical_abnormalities: Optional[str] = Field(description="Eyes, clinical abnormalities - Normal/Abnormal")
    ear_nose_throat_hearing: Optional[str] = Field(description="Ear, Nose, Throat including defect of hearing - Normal/Abnormal")
    respiratory_system: Optional[str] = Field(description="Respiratory System - Normal/Abnormal")
    cardiovascular_system: Optional[str] = Field(description="Cardiovascular system Including Heart size/sound - Normal/Abnormal")
    digestive_system: Optional[str] = Field(description="Digestive System - Normal/Abnormal")
    nervous_system: Optional[str] = Field(description="Nervous System - Normal/Abnormal")
    musculoskeletal_system: Optional[str] = Field(description="Musculoskeletal System - Normal/Abnormal")
    general_examination: Optional[str] = Field(description="General examination - Normal/Abnormal")
    
    # Fitness and Recommendations
    fitness_status: Optional[str] = Field(description="Fitness status")
    restrictions: Optional[str] = Field(description="Restrictions")
    recommendation_comments: Optional[str] = Field(description="Comments from recommendations")
    
    # Signatures
    signature_nurse: Optional[str] = Field(description="Signature of Nurse")
    signature_ohp: Optional[str] = Field(description="Signature of OHP")
    signature_omp: Optional[str] = Field(description="Signature of OMP")


# Detection Schema
class SimpleDocumentTypeDetection(BaseModel):
    """Simple document type detection schema"""
    
    document_types_present: str = Field(
        description=(
            "List the medical document types you can identify in this file. "
            "Choose from: certificate_of_fitness, vision_test, audiometric_test, "
            "spirometry_report, consent_form, medical_questionnaire. "
            "Format as comma-separated list like: 'certificate_of_fitness, vision_test'"
        )
    )
    
    primary_document: str = Field(
        description="The main or most prominent document type in this file"
    )


# =============================================================================
# SCHEMA MAPPINGS AND PATTERNS
# =============================================================================

DOCUMENT_SCHEMAS = {
    DocumentType.CERTIFICATE_OF_FITNESS: CertificateOfFitnessSchema,
    DocumentType.VISION_TEST: VisionTestSchema,
    DocumentType.AUDIOMETRIC_TEST: AudiometricTestSchema,
    DocumentType.SPIROMETRY_REPORT: SpirometrySchema,
    DocumentType.CONSENT_FORM: ConsentFormSchema,
    DocumentType.MEDICAL_QUESTIONNAIRE: MedicalQuestionnaireSchema,
}

# Content patterns for fallback detection
DETECTION_PATTERNS = {
    DocumentType.CERTIFICATE_OF_FITNESS: [
        "certificate of fitness", "medical certificate", "fitness declaration", 
        "pre-employment", "periodical", "exit", "medical examination conducted"
    ],
    DocumentType.VISION_TEST: [
        "vision test", "visual acuity", "keystone", "vs-v gt", "eye test", 
        "color vision", "field test", "phoria", "stereopsis"
    ],
    DocumentType.AUDIOMETRIC_TEST: [
        "audiometric", "hearing test", "otoscopic", "decibel", "frequency",
        "left ear", "right ear", "threshold", "noise exposure"
    ],
    DocumentType.SPIROMETRY_REPORT: [
        "spirometry", "lung function", "fvc", "fev1", "flow volume",
        "forced vital capacity", "forced expiratory", "spirometer"
    ],
    DocumentType.CONSENT_FORM: [
        "consent", "drug test", "urine sample", "test device", "sealed",
        "expiry date", "illicit drugs", "employee signature"
    ],
    DocumentType.MEDICAL_QUESTIONNAIRE: [
        "questionnaire", "medical history", "medications", "allergies",
        "family history", "health survey", "lifestyle"
    ]
}