"""
Finance Document Extraction Schemas

Placeholder schemas for the Phase 2 Finance vertical. Initial doc types:
  - bank_statement:  bank statement page
  - invoice:         supplier or customer invoice
  - kyc_form:        KYC / FICA application

Refine when an FSP or insurer customer is in pilot.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class FinanceBankStatementExtraction(BaseModel):
    account_holder: Optional[str] = Field(None, description="Account holder name.")
    account_number: Optional[str] = Field(None, description="Account number (often masked).")
    bank: Optional[str] = Field(None, description="Bank name.")
    statement_period: Optional[str] = Field(None, description="Statement period (e.g. 2026-04-01 to 2026-04-30).")
    opening_balance: Optional[float] = Field(None, description="Opening balance for the period.")
    closing_balance: Optional[float] = Field(None, description="Closing balance for the period.")
    total_deposits: Optional[float] = Field(None, description="Total deposits in the period.")
    total_withdrawals: Optional[float] = Field(None, description="Total withdrawals in the period.")


class FinanceInvoiceExtraction(BaseModel):
    invoice_number: Optional[str] = Field(None, description="Invoice number.")
    issue_date: Optional[str] = Field(None, description="Invoice issue date.")
    due_date: Optional[str] = Field(None, description="Payment due date.")
    supplier_name: Optional[str] = Field(None, description="Supplier / vendor name.")
    customer_name: Optional[str] = Field(None, description="Bill-to customer name.")
    subtotal: Optional[float] = Field(None, description="Subtotal before VAT.")
    vat: Optional[float] = Field(None, description="VAT amount.")
    total: Optional[float] = Field(None, description="Total payable (incl. VAT).")
    line_items: Optional[List[str]] = Field(None, description="Description of line items (free text per item).")


class FinanceKYCFormExtraction(BaseModel):
    full_name: Optional[str] = Field(None, description="Applicant full name.")
    id_number: Optional[str] = Field(None, description="SA ID / passport number.")
    date_of_birth: Optional[str] = Field(None, description="Date of birth.")
    residential_address: Optional[str] = Field(None, description="Residential address.")
    contact_number: Optional[str] = Field(None, description="Contact number.")
    email: Optional[str] = Field(None, description="Email.")
    employer: Optional[str] = Field(None, description="Current employer.")
    source_of_funds: Optional[str] = Field(None, description="Source of funds declaration.")
    risk_rating: Optional[str] = Field(None, description="Risk rating if assigned.")


FINANCE_DOC_TYPES = {
    "finance_bank_statement": {"schema": FinanceBankStatementExtraction, "department": "Treasury",   "sub_category": "Bank Statements", "display_name": "Bank Statement"},
    "finance_invoice":        {"schema": FinanceInvoiceExtraction,       "department": "Accounts",   "sub_category": "Invoices",        "display_name": "Invoice"},
    "finance_kyc_form":       {"schema": FinanceKYCFormExtraction,       "department": "Compliance", "sub_category": "KYC / FICA",      "display_name": "KYC Form"},
}
