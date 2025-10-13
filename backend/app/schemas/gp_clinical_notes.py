"""
Flexible Clinical Notes Schema
Designed for REAL messy doctor handwriting
Extracts what's readable, flags what's not
"""

from pydantic import BaseModel, Field
from typing import Optional, List


class ClinicalEntry(BaseModel):
    """
    Single clinical entry/visit
    FLEXIBLE - extracts whatever is legible
    """
    
    # Date (usually legible)
    date: Optional[str] = Field(
        None,
        description="Date of visit in ANY format found (DD/MM/YY, DD-MM-YYYY, etc)"
    )
    
    # Chief Complaint/Presenting Problem (usually somewhat legible)
    presenting_complaint: Optional[str] = Field(
        None,
        description="Main complaint or reason for visit, as written by doctor. May include hashtags like '#Chest pain', abbreviations, or informal notes"
    )
    
    # Vital Signs (numbers usually legible)
    vital_signs_text: Optional[str] = Field(
        None,
        description="Any vital signs mentioned - BP, pulse, temp, weight, height - exactly as written. Example: 'BP 147/98 P:96/min' or 'HEIGHT-170CM WEIGHT - 96,1KG'"
    )
    
    # Diagnosis/Assessment (often abbreviated or unclear)
    diagnosis_text: Optional[str] = Field(
        None,
        description="Diagnosis or clinical assessment as written. May be abbreviated (e.g., 'URT', 'Arthritis', 'Myalgie') or use medical shorthand"
    )
    
    # Medications/Treatment (often illegible)
    medications_text: Optional[str] = Field(
        None,
        description="Any medications or treatments mentioned, exactly as written. May be illegible or abbreviated. Example: '① Diem x40 ② Rub Rub ③ Stilmenex20'"
    )
    
    # Additional Clinical Notes (free text)
    clinical_notes: Optional[str] = Field(
        None,
        description="Any other clinical observations, symptoms, or notes written by doctor. Include everything readable, even if informal or abbreviated"
    )
    
    # Lab Results (if mentioned)
    lab_results: Optional[str] = Field(
        None,
        description="Any lab results mentioned, as written. Example: 'HB: 9.4 ↓'"
    )
    
    # Legibility Assessment
    partially_illegible: bool = Field(
        False,
        description="True if parts of this entry are illegible or unclear"
    )
    
    illegible_sections: Optional[List[str]] = Field(
        default_factory=list,
        description="List of sections that are illegible, e.g., ['medications', 'some clinical notes']"
    )
    
    # Raw text for validation
    raw_text: Optional[str] = Field(
        None,
        description="Complete raw text of this clinical entry, including illegible parts, for human validation"
    )


class ClinicalNotesHistory(BaseModel):
    """
    All clinical notes from the document
    FLEXIBLE - no rigid structure, just extract what's there
    """
    
    patient_name: Optional[str] = Field(
        None,
        description="Patient name if visible in clinical notes"
    )
    
    # All clinical entries
    clinical_entries: List[ClinicalEntry] = Field(
        default_factory=list,
        description="All clinical consultation entries found, in chronological order if possible"
    )
    
    # Overall assessment
    total_entries: int = Field(
        0,
        description="Total number of clinical entries found"
    )
    
    date_range: Optional[str] = Field(
        None,
        description="Date range of clinical notes (earliest to latest)"
    )
    
    # Handwriting quality
    overall_legibility: Optional[str] = Field(
        None,
        description="Overall legibility assessment: 'Good', 'Fair', 'Poor', 'Mixed'"
    )
    
    notes_for_validation: Optional[str] = Field(
        None,
        description="Any notes for human validator about challenges in extraction"
    )