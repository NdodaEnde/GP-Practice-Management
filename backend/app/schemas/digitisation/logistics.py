"""
TRT (Tshwane Rapid Transit) Document Extraction Schemas
Phase 1 Digitisation — Finance, HR, Operations departments

Each model maps to a document type in the TRT scanning inventory.
Indexing fields from `Files for scanning.xlsx` are the minimum extraction targets.
Additional fields will be added once sample documents are reviewed.

DOCUMENT_TYPES: see TRT_DOC_TYPES registry at bottom
INDUSTRY_TYPE = "transport"
TENANT_SLUG = "trt-transit"
"""

from typing import Optional, List
from pydantic import BaseModel, Field


# =============================================================================
# FINANCE DEPARTMENT
# =============================================================================

class FinancePaymentsExtraction(BaseModel):
    """Finance payments file extraction.
    DB: trt_extractions (doc_type='finance_payments')
    Indexing fields: Period, Supplier Name
    """
    period: Optional[str] = Field(None, description="Financial period (e.g., '2024/25 Q3', 'March 2024')")
    supplier_name: Optional[str] = Field(None, description="Supplier or vendor name")
    invoice_number: Optional[str] = Field(None, description="Invoice reference number")
    amount: Optional[str] = Field(None, description="Payment amount")
    payment_date: Optional[str] = Field(None, description="Date of payment")
    description: Optional[str] = Field(None, description="Payment description or purpose")


class FinanceJournalsExtraction(BaseModel):
    """Finance journals file extraction.
    DB: trt_extractions (doc_type='finance_journals')
    Indexing fields: Period, Journal Number
    """
    period: Optional[str] = Field(None, description="Financial period")
    journal_number: Optional[str] = Field(None, description="Journal entry number")
    description: Optional[str] = Field(None, description="Journal entry description")
    debit_amount: Optional[str] = Field(None, description="Debit amount")
    credit_amount: Optional[str] = Field(None, description="Credit amount")
    account_code: Optional[str] = Field(None, description="General ledger account code")


class FinanceGeneralAdminExtraction(BaseModel):
    """Finance general admin file extraction.
    DB: trt_extractions (doc_type='finance_general_admin')
    Indexing fields: Period, Document Name
    """
    period: Optional[str] = Field(None, description="Financial period")
    document_name: Optional[str] = Field(None, description="Document title or name")
    document_date: Optional[str] = Field(None, description="Date on document")
    summary: Optional[str] = Field(None, description="Brief summary of document content")


# =============================================================================
# HR DEPARTMENT — Recruitment
# =============================================================================

class HRRecruitmentExtraction(BaseModel):
    """HR recruitment file extraction (all recruitment subtypes).
    DB: trt_extractions (doc_type='hr_recruitment_*')
    Indexing fields: Position Name, Year
    Covers: support staff, drivers, apprenticeship, learnerships, internships
    """
    position_name: Optional[str] = Field(None, description="Name of the position (e.g., 'Operations Support Officer')")
    year: Optional[str] = Field(None, description="Recruitment year")
    recruitment_type: Optional[str] = Field(None, description="Type: support, drivers, apprenticeship, learnership, internship")
    department: Optional[str] = Field(None, description="Recruiting department")
    status: Optional[str] = Field(None, description="Recruitment status (open, closed, filled)")
    num_applicants: Optional[str] = Field(None, description="Number of applicants if mentioned")
    closing_date: Optional[str] = Field(None, description="Application closing date")


# =============================================================================
# HR DEPARTMENT — Industrial Relations
# =============================================================================

class HRIndustrialRelationsExtraction(BaseModel):
    """HR industrial relations file extraction (unions, disciplinary, CCMA).
    DB: trt_extractions (doc_type='hr_ir_*')
    Indexing fields: Subject, Period, Depot (for disciplinary), Union (for union reports)
    Covers: SATAWU, NUMSA, disciplinary BRT/Mamelodi, CCMA/Labour court, union monthly reports
    """
    subject: Optional[str] = Field(None, description="Subject or case description")
    period: Optional[str] = Field(None, description="Period or date range")
    union_name: Optional[str] = Field(None, description="Union name (SATAWU, NUMSA) if applicable")
    depot: Optional[str] = Field(None, description="Depot location (BRT, Mamelodi) if applicable")
    case_type: Optional[str] = Field(None, description="Type: union, disciplinary, ccma, labour_court")
    case_number: Optional[str] = Field(None, description="Case or reference number")
    outcome: Optional[str] = Field(None, description="Outcome or resolution if documented")
    employee_name: Optional[str] = Field(None, description="Employee name if disciplinary case")


# =============================================================================
# HR DEPARTMENT — Payroll & Benefits
# =============================================================================

class HRPayrollExtraction(BaseModel):
    """HR payroll file extraction.
    DB: trt_extractions (doc_type='hr_payroll')
    Indexing fields: Month, Period
    """
    month: Optional[str] = Field(None, description="Payroll month (e.g., 'March 2024')")
    period: Optional[str] = Field(None, description="Payroll period")
    total_employees: Optional[str] = Field(None, description="Number of employees on payroll")
    gross_total: Optional[str] = Field(None, description="Gross payroll total")
    net_total: Optional[str] = Field(None, description="Net payroll total")


class HRBenefitClaimsExtraction(BaseModel):
    """HR employee benefit claims extraction (Momentum).
    DB: trt_extractions (doc_type='hr_benefit_claims')
    Indexing fields: Claim Type, Period
    """
    claim_type: Optional[str] = Field(None, description="Type of benefit claim")
    period: Optional[str] = Field(None, description="Claim period")
    employee_name: Optional[str] = Field(None, description="Employee name")
    claim_amount: Optional[str] = Field(None, description="Claim amount")
    claim_date: Optional[str] = Field(None, description="Date of claim submission")


# =============================================================================
# HR DEPARTMENT — Performance & Employee Records
# =============================================================================

class HRPerformanceReviewExtraction(BaseModel):
    """HR performance review evidence extraction.
    DB: trt_extractions (doc_type='hr_performance_reviews')
    Indexing fields: Employee Name, Surname, Period, Quarter
    """
    employee_name: Optional[str] = Field(None, description="Employee first name")
    surname: Optional[str] = Field(None, description="Employee surname")
    period: Optional[str] = Field(None, description="Review period (e.g., '2024/25')")
    quarter: Optional[str] = Field(None, description="Quarter (Q1, Q2, Q3, Q4)")
    rating: Optional[str] = Field(None, description="Performance rating if available")
    reviewer_name: Optional[str] = Field(None, description="Reviewer or manager name")


class HREmployeePersonalFileExtraction(BaseModel):
    """HR employee personal file extraction.
    DB: trt_extractions (doc_type='hr_employee_personal')
    Indexing fields: Initials, Surname, Employee No., Depot
    """
    initials: Optional[str] = Field(None, description="Employee initials")
    surname: Optional[str] = Field(None, description="Employee surname")
    employee_no: Optional[str] = Field(None, description="Employee number")
    depot: Optional[str] = Field(None, description="Depot assignment (BRT, Mamelodi)")
    id_number: Optional[str] = Field(None, description="SA ID number")
    position: Optional[str] = Field(None, description="Job title or position")
    date_of_employment: Optional[str] = Field(None, description="Date of employment")
    department: Optional[str] = Field(None, description="Department")


class HRTerminationsExtraction(BaseModel):
    """HR terminations file extraction.
    DB: trt_extractions (doc_type='hr_terminations')
    """
    employee_name: Optional[str] = Field(None, description="Employee name")
    surname: Optional[str] = Field(None, description="Employee surname")
    employee_no: Optional[str] = Field(None, description="Employee number")
    termination_date: Optional[str] = Field(None, description="Date of termination")
    reason: Optional[str] = Field(None, description="Reason for termination")
    termination_type: Optional[str] = Field(None, description="Type: resignation, dismissal, retrenchment, retirement")


# =============================================================================
# OPERATIONS DEPARTMENT
# =============================================================================

class OpsInspectionFormExtraction(BaseModel):
    """Operations vehicle inspection form extraction.
    Reuses existing transport inspection schema concepts.
    DB: trt_extractions (doc_type='ops_inspection_forms')
    """
    vehicle_reg_no: Optional[str] = Field(None, description="Vehicle registration number")
    drivers_name: Optional[str] = Field(None, description="Driver's name")
    date: Optional[str] = Field(None, description="Inspection date")
    vehicle_mileage: Optional[str] = Field(None, description="Vehicle mileage reading")
    route: Optional[str] = Field(None, description="Route or service line")
    inspection_result: Optional[str] = Field(None, description="Overall inspection result (pass/fail)")
    defects: Optional[List[str]] = Field(None, description="List of defects found")


class OpsAccountsPayableExtraction(BaseModel):
    """Operations accounts payable extraction.
    DB: trt_extractions (doc_type='ops_accounts_payable')
    """
    period: Optional[str] = Field(None, description="Financial period")
    supplier_name: Optional[str] = Field(None, description="Supplier name")
    invoice_number: Optional[str] = Field(None, description="Invoice number")
    amount: Optional[str] = Field(None, description="Amount payable")
    due_date: Optional[str] = Field(None, description="Payment due date")


# =============================================================================
# MASTER EXTRACTION MODEL — wraps all TRT doc types
# =============================================================================

class TRTDocumentExtraction(BaseModel):
    """
    Master extraction model for TRT documents.
    The active sub-model is selected based on doc_type (from Split API or manual override).
    Only the relevant section is populated for each document.
    """
    # Finance
    finance_payments: Optional[FinancePaymentsExtraction] = None
    finance_journals: Optional[FinanceJournalsExtraction] = None
    finance_general_admin: Optional[FinanceGeneralAdminExtraction] = None

    # HR - Recruitment
    hr_recruitment: Optional[HRRecruitmentExtraction] = None

    # HR - Industrial Relations
    hr_industrial_relations: Optional[HRIndustrialRelationsExtraction] = None

    # HR - Payroll & Benefits
    hr_payroll: Optional[HRPayrollExtraction] = None
    hr_benefit_claims: Optional[HRBenefitClaimsExtraction] = None

    # HR - Performance & Employee Records
    hr_performance_reviews: Optional[HRPerformanceReviewExtraction] = None
    hr_employee_personal: Optional[HREmployeePersonalFileExtraction] = None
    hr_terminations: Optional[HRTerminationsExtraction] = None

    # Operations
    ops_inspection_forms: Optional[OpsInspectionFormExtraction] = None
    ops_accounts_payable: Optional[OpsAccountsPayableExtraction] = None


# =============================================================================
# DOC TYPE REGISTRY — maps doc_type string to schema + department
# =============================================================================

TRT_DOC_TYPES = {
    # Finance
    "finance_payments": {"schema": FinancePaymentsExtraction, "department": "Finance", "sub_category": "Payments"},
    "finance_journals": {"schema": FinanceJournalsExtraction, "department": "Finance", "sub_category": "Journals"},
    "finance_general_admin": {"schema": FinanceGeneralAdminExtraction, "department": "Finance", "sub_category": "General Admin"},

    # HR - Recruitment
    "hr_recruitment_support": {"schema": HRRecruitmentExtraction, "department": "HR", "sub_category": "Recruitment"},
    "hr_recruitment_drivers": {"schema": HRRecruitmentExtraction, "department": "HR", "sub_category": "Recruitment"},
    "hr_recruitment_apprenticeship": {"schema": HRRecruitmentExtraction, "department": "HR", "sub_category": "Recruitment"},
    "hr_recruitment_learnerships": {"schema": HRRecruitmentExtraction, "department": "HR", "sub_category": "Recruitment"},
    "hr_recruitment_internships": {"schema": HRRecruitmentExtraction, "department": "HR", "sub_category": "Recruitment"},

    # HR - Industrial Relations
    "hr_ir_satawu": {"schema": HRIndustrialRelationsExtraction, "department": "HR", "sub_category": "Industrial Relations"},
    "hr_ir_numsa": {"schema": HRIndustrialRelationsExtraction, "department": "HR", "sub_category": "Industrial Relations"},
    "hr_ir_disciplinary_brt": {"schema": HRIndustrialRelationsExtraction, "department": "HR", "sub_category": "Disciplinary"},
    "hr_ir_disciplinary_mamelodi": {"schema": HRIndustrialRelationsExtraction, "department": "HR", "sub_category": "Disciplinary"},
    "hr_ir_ccma": {"schema": HRIndustrialRelationsExtraction, "department": "HR", "sub_category": "CCMA/Labour Court"},
    "hr_ir_union_reports": {"schema": HRIndustrialRelationsExtraction, "department": "HR", "sub_category": "Union Reports"},

    # HR - Payroll & Benefits
    "hr_payroll": {"schema": HRPayrollExtraction, "department": "HR", "sub_category": "Payroll"},
    "hr_benefit_claims": {"schema": HRBenefitClaimsExtraction, "department": "HR", "sub_category": "Benefits"},

    # HR - Performance & Employee Records
    "hr_performance_reviews": {"schema": HRPerformanceReviewExtraction, "department": "HR", "sub_category": "Performance"},
    "hr_employee_personal": {"schema": HREmployeePersonalFileExtraction, "department": "HR", "sub_category": "Employee Files"},
    "hr_terminations": {"schema": HRTerminationsExtraction, "department": "HR", "sub_category": "Terminations"},

    # Operations
    "ops_inspection_forms": {"schema": OpsInspectionFormExtraction, "department": "Operations", "sub_category": "Inspections"},
    "ops_accounts_payable": {"schema": OpsAccountsPayableExtraction, "department": "Operations", "sub_category": "Accounts Payable"},
}
