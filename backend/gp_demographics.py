# app/schemas/gp_demographics.py

from pydantic import BaseModel, Field
from typing import Optional

class PatientDemographics(BaseModel):
    """
    Extract from GP patient registration form
    Target: Typed/printed forms (high accuracy)
    """
    
    # Core Identity
    surname: str = Field(
        description="Patient surname/family name"
    )
    first_names: str = Field(
        description="Patient first name(s) or given names"
    )
    date_of_birth: str = Field(
        description="Date of birth in any format (DD.MM.YYYY, YYYY-MM-DD, etc)"
    )
    id_number: str = Field(
        description="South African ID number (13 digits) or passport number"
    )
    gender: Optional[str] = Field(
        description="Gender: Male, Female, or Other",
        default=None
    )
    
    # Contact Details
    home_language: Optional[str] = Field(
        description="Home/primary language (English, Afrikaans, Sesotho, Zulu, etc)",
        default=None
    )
    marital_status: Optional[str] = Field(
        description="Marital status: Single, Married, Divorced, Widowed",
        default=None
    )
    cell_number: Optional[str] = Field(
        description="Cell/mobile phone number",
        default=None
    )
    telephone: Optional[str] = Field(
        description="Home/work telephone number",
        default=None
    )
    email: Optional[str] = Field(
        description="Email address",
        default=None
    )
    
    # Address
    home_address_street: Optional[str] = Field(
        description="Street address including street number and name",
        default=None
    )
    home_address_suburb: Optional[str] = Field(
        description="Suburb/area name",
        default=None
    )
    home_address_city: Optional[str] = Field(
        description="City or town",
        default=None
    )
    home_address_code: Optional[str] = Field(
        description="Postal code",
        default=None
    )
    postal_address: Optional[str] = Field(
        description="Full postal address if different from residential",
        default=None
    )
    
    # Medical Aid (Critical for GP)
    medical_aid_name: Optional[str] = Field(
        description="Medical aid scheme name (e.g., Discovery, Bonitas, Gems, Medihelp)",
        default=None
    )
    medical_aid_number: Optional[str] = Field(
        description="Medical aid membership or account number",
        default=None
    )
    medical_aid_plan: Optional[str] = Field(
        description="Medical aid plan or option name (e.g., Essential, Comprehensive)",
        default=None
    )
    medical_aid_main_member: Optional[str] = Field(
        description="Main member name if patient is a dependant",
        default=None
    )
    
    # Employment
    occupation: Optional[str] = Field(
        description="Patient occupation or job title",
        default=None
    )
    employer: Optional[str] = Field(
        description="Employer name or company",
        default=None
    )
    employer_address: Optional[str] = Field(
        description="Employer/work address",
        default=None
    )
    work_phone: Optional[str] = Field(
        description="Work phone number",
        default=None
    )
    
    # Emergency Contact / Next of Kin
    next_of_kin_name: Optional[str] = Field(
        description="Next of kin full name",
        default=None
    )
    next_of_kin_relationship: Optional[str] = Field(
        description="Relationship to patient (parent, spouse, sibling, child, etc)",
        default=None
    )
    next_of_kin_contact: Optional[str] = Field(
        description="Next of kin phone number",
        default=None
    )
    next_of_kin_address: Optional[str] = Field(
        description="Next of kin address",
        default=None
    )