"""
Flexible Vital Signs Extraction
Works with messy, informal vital signs recordings
"""

from pydantic import BaseModel, Field
from typing import Optional, List


class VitalSignsEntry(BaseModel):
    """
    Single vital signs entry - FLEXIBLE
    Extracts whatever numbers are legible
    """
    
    # Date
    date: Optional[str] = Field(
        None,
        description="Date of measurement, any format"
    )
    
    # Blood Pressure (most common)
    bp_systolic: Optional[int] = Field(
        None,
        description="Systolic BP (top number)"
    )
    
    bp_diastolic: Optional[int] = Field(
        None,
        description="Diastolic BP (bottom number)"
    )
    
    bp_raw: Optional[str] = Field(
        None,
        description="Raw BP as written, e.g., 'BP 147/98' or '138/83'"
    )
    
    # Pulse/Heart Rate
    pulse: Optional[int] = Field(
        None,
        description="Pulse in bpm"
    )
    
    pulse_raw: Optional[str] = Field(
        None,
        description="Raw pulse as written, e.g., 'P:96/min' or 'P-94'"
    )
    
    # Temperature
    temperature: Optional[float] = Field(
        None,
        description="Temperature in Celsius"
    )
    
    temperature_raw: Optional[str] = Field(
        None,
        description="Raw temperature as written, e.g., 'TEMP -36,7°' or 'T=36.1'"
    )
    
    # Weight
    weight_kg: Optional[float] = Field(
        None,
        description="Weight in kg"
    )
    
    weight_raw: Optional[str] = Field(
        None,
        description="Raw weight as written, e.g., 'WEIGHT - 96,1KG' or 'WF 96,7'"
    )
    
    # Height
    height_cm: Optional[float] = Field(
        None,
        description="Height in cm"
    )
    
    height_raw: Optional[str] = Field(
        None,
        description="Raw height as written, e.g., 'HEIGHT-170CM' or 'Hgt: = 48'"
    )
    
    # Other measurements
    other_measurements: Optional[str] = Field(
        None,
        description="Any other measurements mentioned, as written"
    )
    
    # Context
    notes: Optional[str] = Field(
        None,
        description="Any context or notes about the measurements"
    )


class VitalSignsExtraction(BaseModel):
    """
    All vital signs found in document
    """
    
    vital_entries: List[VitalSignsEntry] = Field(
        default_factory=list,
        description="All vital signs entries found"
    )
    
    # Quick summary for GP
    latest_bp: Optional[str] = Field(
        None,
        description="Most recent BP reading"
    )
    
    latest_weight: Optional[float] = Field(
        None,
        description="Most recent weight"
    )
    
    latest_date: Optional[str] = Field(
        None,
        description="Date of most recent vitals"
    )
    
    # Trends
    bp_trend: Optional[str] = Field(
        None,
        description="BP trend if multiple readings: 'Increasing', 'Decreasing', 'Stable', 'Variable'"
    )
    
    weight_trend: Optional[str] = Field(
        None,
        description="Weight trend if multiple readings"
    )