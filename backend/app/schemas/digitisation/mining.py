"""
Mining Document Extraction Schemas

Placeholder schemas for the mining vertical. Initial doc types cover the
three highest-frequency operational artifacts in SA mining ops:
  - shift_log:       per-shift production / safety log
  - assay_report:    laboratory assay results
  - incident_report: HSE incident report

Refine with real mining customer documents when a deal closes.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class MiningShiftLogExtraction(BaseModel):
    shift_date: Optional[str] = Field(None, description="Date of the shift (any format)")
    shift: Optional[str] = Field(None, description="Shift identifier — A / B / C / Day / Night.")
    site: Optional[str] = Field(None, description="Mine site or section.")
    supervisor_name: Optional[str] = Field(None, description="Shift supervisor.")
    crew_count: Optional[int] = Field(None, description="Crew on shift.")
    tonnes_mined: Optional[float] = Field(None, description="Tonnes mined this shift.")
    incidents: Optional[List[str]] = Field(None, description="Brief list of incidents (free text per item).")
    notes: Optional[str] = Field(None, description="Free-form supervisor notes.")


class MiningAssayReportExtraction(BaseModel):
    sample_id: Optional[str] = Field(None, description="Lab sample identifier.")
    sample_date: Optional[str] = Field(None, description="Date sampled.")
    site: Optional[str] = Field(None, description="Sample origin (pit / level / drift).")
    grade_au_g_per_t: Optional[float] = Field(None, description="Gold grade (g/t).")
    grade_cu_pct: Optional[float] = Field(None, description="Copper grade (%).")
    grade_other: Optional[str] = Field(None, description="Other commodity grade(s) — free text.")
    lab_name: Optional[str] = Field(None, description="Lab that ran the assay.")
    notes: Optional[str] = Field(None, description="Notes / methodology.")


class MiningIncidentReportExtraction(BaseModel):
    incident_date: Optional[str] = Field(None, description="Date and time of incident.")
    site: Optional[str] = Field(None, description="Where the incident occurred.")
    severity: Optional[str] = Field(None, description="Minor / Major / Critical / Fatal.")
    incident_type: Optional[str] = Field(None, description="Fall-of-ground, machinery, fire, etc.")
    description: Optional[str] = Field(None, description="What happened, narrative.")
    persons_involved: Optional[List[str]] = Field(None, description="Names / IDs of personnel involved.")
    immediate_action: Optional[str] = Field(None, description="Action taken at the scene.")
    reporter_name: Optional[str] = Field(None, description="Person filing the report.")


MINING_DOC_TYPES = {
    "mining_shift_log":       {"schema": MiningShiftLogExtraction,        "department": "Operations",  "sub_category": "Shift Log",       "display_name": "Shift Log"},
    "mining_assay_report":    {"schema": MiningAssayReportExtraction,     "department": "Lab",         "sub_category": "Assay Report",    "display_name": "Assay Report"},
    "mining_incident_report": {"schema": MiningIncidentReportExtraction,  "department": "HSE",         "sub_category": "Incident Report", "display_name": "Incident Report"},
}
