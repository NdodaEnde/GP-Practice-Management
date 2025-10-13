"""
Flexible Chronic Disease & Medication Extraction
Works with real-world mentions, not perfect lists
"""

from pydantic import BaseModel, Field
from typing import Optional, List


class ChronicConditionMention(BaseModel):
    """
    Mention of a chronic condition
    FLEXIBLE - just capture what's written
    """
    
    condition_name: str = Field(
        ...,
        description="Condition name as written - may be abbreviated or informal. Examples: 'Arthritis', 'URT', 'Hypertension', '#Chest pain'"
    )
    
    mentioned_date: Optional[str] = Field(
        None,
        description="Date this condition was mentioned"
    )
    
    context: Optional[str] = Field(
        None,
        description="Any context around the mention"
    )
    
    is_chronic: Optional[bool] = Field(
        None,
        description="True if appears to be chronic/ongoing, False if acute episode, None if unclear"
    )


class MedicationMention(BaseModel):
    """
    Mention of a medication
    FLEXIBLE - captures whatever is legible
    """
    
    medication_name: str = Field(
        ...,
        description="Medication name as written - may be brand name, generic, or partially illegible. Examples: 'Metformin', 'Rub Rub', 'Stilmenex20', 'Diem x40'"
    )
    
    dosage_info: Optional[str] = Field(
        None,
        description="Any dosage information as written, e.g., 'x40', '500mg', '10mg BD'"
    )
    
    mentioned_date: Optional[str] = Field(
        None,
        description="Date medication was mentioned"
    )
    
    context: Optional[str] = Field(
        None,
        description="Context - prescribed, ongoing, discontinued, etc."
    )
    
    legibility: Optional[str] = Field(
        None,
        description="Legibility: 'Clear', 'Partial', 'Unclear'"
    )


class ChronicPatientSummary(BaseModel):
    """
    Summary of chronic conditions and medications
    Built from ALL mentions in document, not rigid lists
    """
    
    # Conditions mentioned
    conditions_mentioned: List[ChronicConditionMention] = Field(
        default_factory=list,
        description="All conditions mentioned throughout document"
    )
    
    # Likely chronic conditions (appears multiple times or flagged as chronic)
    likely_chronic_conditions: List[str] = Field(
        default_factory=list,
        description="Conditions that appear to be chronic based on multiple mentions or context. Examples: 'Hypertension', 'Type 2 Diabetes'"
    )
    
    # Medications mentioned
    medications_mentioned: List[MedicationMention] = Field(
        default_factory=list,
        description="All medications mentioned throughout document"
    )
    
    # Current medications (best guess from most recent mentions)
    likely_current_medications: List[str] = Field(
        default_factory=list,
        description="Medications that appear to be current/ongoing based on recent mentions"
    )
    
    # Allergies (if mentioned)
    allergies: Optional[List[str]] = Field(
        default_factory=list,
        description="Any allergies mentioned"
    )
    
    # Summary stats
    total_condition_mentions: int = Field(
        0,
        description="Total number of times conditions were mentioned"
    )
    
    total_medication_mentions: int = Field(
        0,
        description="Total number of times medications were mentioned"
    )
    
    # Validation notes
    needs_validation: bool = Field(
        True,
        description="Always true - chronic summary should be validated by human"
    )
    
    validation_notes: Optional[str] = Field(
        None,
        description="Notes for validator about unclear medications, illegible text, etc."
    )