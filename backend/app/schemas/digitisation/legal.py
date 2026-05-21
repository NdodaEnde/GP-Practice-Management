"""
Legal Document Extraction Schemas

Placeholder schemas for the Phase 2 Legal vertical. Initial doc types:
  - contract:        commercial contract — clauses, parties, dates, jurisdiction
  - case_brief:      compiled case brief (citation, holdings, ratio)
  - opinion:         legal opinion / memo

Refine when SAFLII corpus ingestion lands and real customer doc samples arrive.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class LegalContractExtraction(BaseModel):
    title: Optional[str] = Field(None, description="Contract title.")
    parties: Optional[List[str]] = Field(None, description="Named parties.")
    effective_date: Optional[str] = Field(None, description="Effective date.")
    end_date: Optional[str] = Field(None, description="Termination / end date.")
    governing_law: Optional[str] = Field(None, description="Governing law / jurisdiction.")
    key_clauses: Optional[List[str]] = Field(None, description="Headings or short summaries of key clauses.")
    risky_clauses: Optional[List[str]] = Field(None, description="Clauses flagged as non-standard or risky.")
    notes: Optional[str] = Field(None, description="Other relevant notes.")


class LegalCaseBriefExtraction(BaseModel):
    case_name: Optional[str] = Field(None, description="Case name (parties).")
    citation: Optional[str] = Field(None, description="Neutral citation, e.g. [2024] ZACC 12.")
    court: Optional[str] = Field(None, description="Constitutional Court / SCA / High Court / etc.")
    judges: Optional[List[str]] = Field(None, description="Judges who heard the matter.")
    decision_date: Optional[str] = Field(None, description="Date of decision.")
    legal_issues: Optional[List[str]] = Field(None, description="Issues considered.")
    holdings: Optional[List[str]] = Field(None, description="Holdings / ratio.")
    status: Optional[str] = Field(None, description="good_law / superseded / overruled.")


class LegalOpinionExtraction(BaseModel):
    subject: Optional[str] = Field(None, description="Subject / matter.")
    counsel: Optional[str] = Field(None, description="Author (counsel) name.")
    opinion_date: Optional[str] = Field(None, description="Date of opinion.")
    instructing_party: Optional[str] = Field(None, description="Instructing attorney / firm.")
    issues_addressed: Optional[List[str]] = Field(None, description="Issues addressed in the opinion.")
    conclusion: Optional[str] = Field(None, description="Bottom-line conclusion.")
    cited_authorities: Optional[List[str]] = Field(None, description="Cases / statutes cited.")


LEGAL_DOC_TYPES = {
    "legal_contract":   {"schema": LegalContractExtraction,   "department": "Commercial",   "sub_category": "Contracts",  "display_name": "Contract"},
    "legal_case_brief": {"schema": LegalCaseBriefExtraction,  "department": "Litigation",   "sub_category": "Case Briefs","display_name": "Case Brief"},
    "legal_opinion":    {"schema": LegalOpinionExtraction,    "department": "Counsel",      "sub_category": "Opinions",   "display_name": "Legal Opinion"},
}
