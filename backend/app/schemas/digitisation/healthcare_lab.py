"""
NHLS (National Health Laboratory Service) Document Extraction Schemas
Two form types:
  1. CRDM Specimen Submission Form — NICD Centre for Respiratory Diseases and Meningitis
  2. Public Health Request Form — NHLS Greenpoint environmental/food/water sample requests

DOCUMENT_TYPES: see NHLS_DOC_TYPES registry at bottom
INDUSTRY_TYPE = "healthcare_lab"
TENANT_SLUG = "nhls"
ZDR_REQUIRED = True  — patient/PHI data throughout
"""

from typing import Optional, List
from pydantic import BaseModel, Field


# =============================================================================
# CRDM SPECIMEN SUBMISSION FORM — Sub-models
# =============================================================================

class CRDMHeader(BaseModel):
    """Tracking identifiers at top of CRDM form.
    Maps to: lab_extractions (header section)
    """
    crdm_unique_no: Optional[str] = Field(None, description="CRDM unique number (top-left of form)")
    crdm_lab_no: Optional[str] = Field(None, description="CRDM laboratory number")
    trak_no: Optional[str] = Field(None, description="Trak system tracking number")
    date_received: Optional[str] = Field(None, description="Date specimen received at CRDM lab (dd-mm-yyyy)")


class CRDMPatientInfo(BaseModel):
    """Patient identifying information from CRDM form.
    Maps to: lab_extractions (patient_info section)
    SA context: Military/hospital patients use service/hospital numbers as identifiers.
    """
    identifier_or_hospital_no: Optional[str] = Field(None, description="Patient identifier or hospital number")
    surname: Optional[str] = Field(None, description="Patient surname")
    first_name: Optional[str] = Field(None, description="Patient first name(s)")
    age: Optional[str] = Field(None, description="Patient age (if date of birth not provided)")
    date_of_birth: Optional[str] = Field(None, description="Patient date of birth (dd-mm-yyyy)")
    gender: Optional[str] = Field(None, description="Patient gender: Male, Female, or Unknown")
    facility_hospital: Optional[str] = Field(None, description="Referring facility or hospital name")


class CRDMSubmitterInfo(BaseModel):
    """Contact person for results — the submitter/requester.
    Maps to: lab_extractions (submitter_info section)
    """
    surname: Optional[str] = Field(None, description="Submitter surname")
    first_name: Optional[str] = Field(None, description="Submitter first name")
    laboratory: Optional[str] = Field(None, description="Submitter's laboratory name")
    city_country: Optional[str] = Field(None, description="City and country of submitter")
    contact_number: Optional[str] = Field(None, description="Contact telephone number with country code")
    email: Optional[str] = Field(None, description="Email address for results")


class CRDMSpecimenDetails(BaseModel):
    """Specimen collection details and type checkboxes.
    Maps to: lab_extractions (specimen_details section)
    Specimen types are checkboxes on the form — extracted as a list of checked values.
    """
    collection_date: Optional[str] = Field(None, description="Specimen collection date (dd-mm-yyyy)")
    specimen_types: Optional[List[str]] = Field(
        None,
        description=(
            "List of specimen types checked on form. Valid values: "
            "Combined NP/OP swab, Nasopharyngeal (NP) aspirate, Nasal swab, "
            "Nasopharyngeal (NP) swab, Bronchoalveolar lavage (BAL), Sputum, "
            "Oropharyngeal (OP) swab, Pleural fluid, CSF, "
            "Tracheal aspirate (TA), Blood culture, Serum, Whole blood, Other"
        )
    )
    specimen_type_other: Optional[str] = Field(None, description="If 'Other' specimen type is checked, specify here")


class CRDMTestDetails(BaseModel):
    """Laboratory tests requested — checkboxes on the form.
    Maps to: lab_extractions (test_details section)
    Page 2 of the form lists PCR diagnostic test panel compositions.
    """
    tests_requested: Optional[List[str]] = Field(
        None,
        description=(
            "List of laboratory tests checked on form. Valid values: "
            "Avian influenza, Influenza / RSV, MERS-CoV, Neonatal sepsis, "
            "Bordetella pertussis, Legionella spp., Atypical pneumonia, Bacterial meningitis, "
            "C. diphtheriae, Respiratory panel (bacterial & viral), Viral meningitis, "
            "Group A streptococcus, Community-acquired pneumonia (bacteria), SARS-CoV-2, "
            "Group B streptococcus, Hospital-acquired pneumonia (bacteria), Other"
        )
    )
    test_other: Optional[str] = Field(None, description="If 'Other' test is checked, specify here")


class CRDMClinicalPresentation(BaseModel):
    """Clinical presentation, symptoms, risk factors, hospitalisation status, and outcome.
    Maps to: lab_extractions (clinical_presentation section)
    """
    date_of_symptom_onset: Optional[str] = Field(None, description="Date symptoms started (dd-mm-yyyy)")
    clinical_diagnoses: Optional[List[str]] = Field(
        None,
        description=(
            "Clinical diagnosis checkboxes. Valid values: "
            "Acute rheumatic fever, Meningococcal disease, Lower respiratory tract infection, "
            "Diphtheria, Influenza-like illness, Upper respiratory tract infection, "
            "Pertussis, Meningitis, Other"
        )
    )
    diagnosis_other: Optional[str] = Field(None, description="If 'Other' diagnosis, specify here")
    symptoms: Optional[List[str]] = Field(
        None,
        description=(
            "Symptom checkboxes. Valid values: "
            "Fever (≥38°C), Sore Throat, Cough, Headache, Stiff neck, "
            "Shortness of breath, Vomiting, Diarrhoea, "
            "Paroxysmal cough/inspiratory whoop, Apnoea, Other, Unknown, None"
        )
    )
    symptom_other: Optional[str] = Field(None, description="If 'Other' symptom, specify here")
    underlying_risk_factors: Optional[List[str]] = Field(
        None,
        description=(
            "Risk factor checkboxes. Valid values: "
            "Asthma, Chronic Lung Disease, Diabetes, HIV, Pregnancy, TB, "
            "Heart Disease, Other, Unknown, None"
        )
    )
    risk_factor_other: Optional[str] = Field(None, description="If 'Other' risk factor, specify here")
    hospitalisation_status: Optional[str] = Field(
        None,
        description="Hospitalisation status: Outpatient, Inpatient — not admitted ICU, Inpatient — admitted to ICU, Unknown"
    )
    outcome: Optional[str] = Field(
        None,
        description="Patient outcome: Still hospitalised, Survived, Died, Unknown"
    )


class CRDMTravelEntry(BaseModel):
    """Single travel history entry (form allows up to 2)."""
    area_country: Optional[str] = Field(None, description="Area or country travelled to")
    date_travel_to: Optional[str] = Field(None, description="Date of travel to this area (dd-mm-yyyy)")
    date_travel_from: Optional[str] = Field(None, description="Date of travel from this area (dd-mm-yyyy)")


class CRDMAnimalExposure(BaseModel):
    """Animal contact exposure entry."""
    animal_type: Optional[str] = Field(
        None,
        description="Animal type: Swine, Wildbirds, Poultry (eg. chickens, ostrich, ducks), Other"
    )
    animal_type_other: Optional[str] = Field(None, description="If 'Other' animal type, specify here")
    date_of_exposure: Optional[str] = Field(None, description="Date of animal exposure (dd-mm-yyyy)")
    exposure_type: Optional[str] = Field(None, description="Type of exposure (e.g., direct contact, market visit)")


class CRDMExposureHistory(BaseModel):
    """Travel and animal contact exposure history.
    Maps to: lab_extractions (exposure_history section)
    """
    travel_in_14_days: Optional[str] = Field(None, description="Did the patient travel in 14 days prior to symptom onset? Yes, No, Unknown")
    travel_entries: Optional[List[CRDMTravelEntry]] = Field(None, description="Travel history entries (up to 2)")
    animal_contact_in_14_days: Optional[str] = Field(None, description="Did the patient have animal contact in 14 days prior? Yes, No, Unknown")
    animal_exposures: Optional[List[CRDMAnimalExposure]] = Field(None, description="Animal exposure entries")


# =============================================================================
# CRDM MASTER EXTRACTION MODEL
# =============================================================================

class CRDMSpecimenSubmissionExtraction(BaseModel):
    """CRDM Specimen Submission Form — NICD Centre for Respiratory Diseases and Meningitis.
    DB: lab_extractions (doc_type='nhls_crdm_specimen')
    Form version: V3 Feb 2020
    Source: CRDM_specimen_submission_form_v3_14_Feb_2020_Elect.pdf
    """
    header: Optional[CRDMHeader] = None
    patient_info: Optional[CRDMPatientInfo] = None
    submitter_info: Optional[CRDMSubmitterInfo] = None
    specimen_details: Optional[CRDMSpecimenDetails] = None
    test_details: Optional[CRDMTestDetails] = None
    clinical_presentation: Optional[CRDMClinicalPresentation] = None
    exposure_history: Optional[CRDMExposureHistory] = None


# =============================================================================
# PUBLIC HEALTH REQUEST FORM — Sub-models
# =============================================================================

class PHSampleInfo(BaseModel):
    """Sample collection information.
    Maps to: lab_extractions (sample_info section)
    """
    collection_date: Optional[str] = Field(None, description="Date samples were collected")
    collection_time: Optional[str] = Field(None, description="Time samples were collected")
    location_source: Optional[str] = Field(None, description="Location or source of sample collection")
    collected_by: Optional[str] = Field(None, description="Name of person who collected the samples")
    tel_cell: Optional[str] = Field(None, description="Telephone or cell number of collector")
    signature: Optional[str] = Field(None, description="Signature of collector (text representation)")
    notes_reason: Optional[str] = Field(None, description="Notes or reason for request (free text)")
    reason_type: Optional[str] = Field(None, description="Request type: Outbreak or Routine")


class PHAccountDetails(BaseModel):
    """Account/invoice details for billing.
    Maps to: lab_extractions (account_details section)
    """
    name: Optional[str] = Field(None, description="Account holder name")
    company: Optional[str] = Field(None, description="Company name")
    department: Optional[str] = Field(None, description="Department name")
    address: Optional[str] = Field(None, description="Billing address")
    account_no: Optional[str] = Field(None, description="Account number")
    telephone: Optional[str] = Field(None, description="Telephone number")
    cell_phone: Optional[str] = Field(None, description="Cell phone number")
    email_for_results: Optional[str] = Field(None, description="Email address for results delivery")
    alternative_contact: Optional[str] = Field(None, description="Alternative contact person or number")


class PHSampleRow(BaseModel):
    """Single sample entry in the samples collected table (form allows up to 20)."""
    sample_no: Optional[int] = Field(None, description="Sample number (1-20)")
    sample_reference_number: Optional[str] = Field(None, description="Sample reference number or ID")
    sample_type_description: Optional[str] = Field(None, description="Sample type or description")


class PHFoodTests(BaseModel):
    """Food sample test checkboxes.
    Maps to: lab_extractions (food_tests section)
    """
    tests: Optional[List[str]] = Field(
        None,
        description=(
            "Food tests checked. Valid values: "
            "Total Bacterial Count, Coliforms & E. coli, E. coli O157, "
            "Salmonella species, Listeria monocytogenes, Coagulase Positive Staph, "
            "Clostridium perfringens, Shigella species, Vibrio species, "
            "Campylobacter species, Bacillus cereus, Listeria species, "
            "Yeast/Mould count, Other"
        )
    )
    other_tests: Optional[str] = Field(None, description="If 'Other' food test, specify here")


class PHWaterTests(BaseModel):
    """Water sample type and test checkboxes.
    Maps to: lab_extractions (water_tests section)
    """
    water_type: Optional[str] = Field(None, description="Water type: Potable, Non-potable, Moore pad, Dialysis water, Other")
    water_type_other: Optional[str] = Field(None, description="If 'Other' water type, specify here")
    tests: Optional[List[str]] = Field(
        None,
        description=(
            "Water tests checked. Valid values: "
            "Total Bacterial Count, Total Coliforms & E. coli, Faecal coliforms, "
            "Vibrio cholerae, Yeast/Mould, Pseudomonas aeruginosa, "
            "Enterococcus species, Salmonella species, Legionella pneumophila, Other"
        )
    )
    other_tests: Optional[str] = Field(None, description="If 'Other' water test, specify here")


class PHMilkTests(BaseModel):
    """Milk sample type and test checkboxes.
    Maps to: lab_extractions (milk_tests section)
    """
    milk_type: Optional[str] = Field(None, description="Milk type: Pasteurised, Raw, Infant formula/Powder, Other")
    milk_type_other: Optional[str] = Field(None, description="If 'Other' milk type, specify here")
    tests: Optional[List[str]] = Field(
        None,
        description=(
            "Milk tests checked. Valid values: "
            "Total aerobic count, Total coliform/E. coli, Phosphatase, "
            "Methylene Blue Reductase, Antimicrobial substances, Other"
        )
    )
    other_tests: Optional[str] = Field(None, description="If 'Other' milk test, specify here")


class PHEnvironmentalSwabs(BaseModel):
    """Environmental/hygiene swab test checkboxes.
    Maps to: lab_extractions (environmental_swabs section)
    """
    surface_area_size: Optional[str] = Field(None, description="Collection surface area: 10cm², Unmeasured")
    tests: Optional[List[str]] = Field(
        None,
        description=(
            "Environmental swab tests checked. Valid values: "
            "Total Bacterial Count, Total coliforms & E.coli, Yeast/Mould count, "
            "Listeria monocytogenes, Salmonella species, Other"
        )
    )
    other_tests: Optional[str] = Field(None, description="If 'Other' environmental test, specify here")


class PHAirSettlePlates(BaseModel):
    """Air settle plate type checkboxes.
    Maps to: lab_extractions (air_settle_plates section)
    """
    plates: Optional[List[str]] = Field(
        None,
        description="Air settle plate types checked. Valid values: Blood plate, Total SAB plate, Nutrient agar"
    )


class PHReception(BaseModel):
    """Reception/receiving details at bottom of form.
    Maps to: lab_extractions (reception section)
    """
    notes: Optional[str] = Field(None, description="Notes on temperature, condition, missing items, etc.")
    received_by: Optional[str] = Field(None, description="Name of person who received the samples at the lab")
    date: Optional[str] = Field(None, description="Date samples received at lab")
    time: Optional[str] = Field(None, description="Time samples received at lab")


# =============================================================================
# PUBLIC HEALTH MASTER EXTRACTION MODEL
# =============================================================================

class PublicHealthRequestExtraction(BaseModel):
    """NHLS Greenpoint Public Health Request Form for environmental/food/water samples.
    DB: lab_extractions (doc_type='nhls_public_health')
    Form: NHLS Greenpoint_Public Health Inhouse Form001
    Source: Public-Health-Request-form-01-June-2023-Greenpoint.pdf
    """
    sample_info: Optional[PHSampleInfo] = None
    account_details: Optional[PHAccountDetails] = None
    samples_collected: Optional[List[PHSampleRow]] = None
    food_tests: Optional[PHFoodTests] = None
    water_tests: Optional[PHWaterTests] = None
    milk_tests: Optional[PHMilkTests] = None
    environmental_swabs: Optional[PHEnvironmentalSwabs] = None
    air_settle_plates: Optional[PHAirSettlePlates] = None
    sterility_testing: Optional[bool] = Field(None, description="Whether sterility testing is requested")
    reception: Optional[PHReception] = None


# =============================================================================
# DOC TYPE REGISTRY
# =============================================================================

NHLS_DOC_TYPES = {
    "nhls_crdm_specimen": {
        "schema": CRDMSpecimenSubmissionExtraction,
        "department": "CRDM",
        "sub_category": "Specimen Submission",
        "display_name": "CRDM Specimen Submission",
    },
    "nhls_public_health": {
        "schema": PublicHealthRequestExtraction,
        "department": "Public Health",
        "sub_category": "Request Form",
        "display_name": "Public Health Request",
    },
}
