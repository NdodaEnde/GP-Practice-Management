"""
Multi-industry SCHEMA_REGISTRY for the digitisation pipeline.

Pattern lifted from groundtruth-clean-gp/backend/main.py and adapted to the
GP-Practice-Management capability + workspace model.

Resolution rules (most-specific-first):
  1. exact (industry_type, doc_type) match
  2. industry default (industry_type, None)
  3. ultimate fallback: GPPatientRecordExtraction (healthcare)

Industry IDs are normalised (lowercased, hyphens → underscores). The
workspaces.industry_type column drives selection; if absent, healthcare is
assumed for backward compatibility with the existing demo workspace.
"""

from typing import Any, Dict, List, Optional, Tuple, Type

from pydantic import BaseModel

# Healthcare (GP)
from app.schemas.digitisation.gp_patient import GPPatientRecordExtraction

# Healthcare lab (NHLS)
from app.schemas.digitisation.healthcare_lab import (
    NHLS_DOC_TYPES,
    CRDMSpecimenSubmissionExtraction,
)

# Logistics (transport)
from app.schemas.digitisation.logistics import TRT_DOC_TYPES

# Other industries (placeholders — refine when pilots land)
from app.schemas.digitisation.mining import MINING_DOC_TYPES
from app.schemas.digitisation.legal import LEGAL_DOC_TYPES
from app.schemas.digitisation.finance import FINANCE_DOC_TYPES


# ---------------------------------------------------------------------------
# Industry catalogue — display metadata for the Documents Pipeline filter chips
# ---------------------------------------------------------------------------

INDUSTRIES: Dict[str, Dict[str, Any]] = {
    "healthcare":     {"display_name": "Healthcare (GP)",        "default_doc_type": "gp_cover_page"},
    "healthcare_lab": {"display_name": "Healthcare Lab (NHLS)",  "default_doc_type": "nhls_crdm_specimen"},
    "logistics":      {"display_name": "Logistics / Transport",  "default_doc_type": "ops_inspection_forms"},
    "mining":         {"display_name": "Mining",                 "default_doc_type": "mining_shift_log"},
    "legal":          {"display_name": "Legal",                  "default_doc_type": "legal_contract"},
    "finance":        {"display_name": "Finance",                "default_doc_type": "finance_invoice"},
}


# ---------------------------------------------------------------------------
# Healthcare (GP) — single rich schema covers all GP doc types. We register
# explicit doc-type aliases for the chip filter on the Documents Pipeline.
# ---------------------------------------------------------------------------

GP_DOC_TYPES: Dict[str, Dict[str, Any]] = {
    "gp_cover_page":      {"schema": GPPatientRecordExtraction, "department": "Clinical", "sub_category": "Cover Page",      "display_name": "Patient Cover Page"},
    "gp_soap_note":       {"schema": GPPatientRecordExtraction, "department": "Clinical", "sub_category": "SOAP Note",       "display_name": "SOAP Note"},
    "gp_lab_report":      {"schema": GPPatientRecordExtraction, "department": "Clinical", "sub_category": "Lab Report",      "display_name": "Lab Report"},
    "gp_prescription":    {"schema": GPPatientRecordExtraction, "department": "Clinical", "sub_category": "Prescription",    "display_name": "Prescription"},
    "gp_referral_letter": {"schema": GPPatientRecordExtraction, "department": "Clinical", "sub_category": "Referral Letter", "display_name": "Referral Letter"},
}


# ---------------------------------------------------------------------------
# Build the registry
# ---------------------------------------------------------------------------

SCHEMA_REGISTRY: Dict[Tuple[str, Optional[str]], Type[BaseModel]] = {
    # Industry defaults (doc_type=None falls through to here)
    ("healthcare",     None): GPPatientRecordExtraction,
    ("healthcare_lab", None): CRDMSpecimenSubmissionExtraction,
    # Logistics / mining / legal / finance defaults are set below from their
    # DOC_TYPES dicts — first registered doc_type's schema becomes the default.
}

# Healthcare GP doc types
for _doc_type, _info in GP_DOC_TYPES.items():
    SCHEMA_REGISTRY[("healthcare", _doc_type)] = _info["schema"]

# NHLS lab doc types
for _doc_type, _info in NHLS_DOC_TYPES.items():
    SCHEMA_REGISTRY[("healthcare_lab", _doc_type)] = _info["schema"]

# Logistics / transport doc types (TRT lineage from groundtruth)
for _doc_type, _info in TRT_DOC_TYPES.items():
    SCHEMA_REGISTRY[("logistics", _doc_type)] = _info["schema"]
SCHEMA_REGISTRY[("logistics", None)] = next(iter(TRT_DOC_TYPES.values()))["schema"]

# Mining doc types
for _doc_type, _info in MINING_DOC_TYPES.items():
    SCHEMA_REGISTRY[("mining", _doc_type)] = _info["schema"]
SCHEMA_REGISTRY[("mining", None)] = next(iter(MINING_DOC_TYPES.values()))["schema"]

# Legal doc types
for _doc_type, _info in LEGAL_DOC_TYPES.items():
    SCHEMA_REGISTRY[("legal", _doc_type)] = _info["schema"]
SCHEMA_REGISTRY[("legal", None)] = next(iter(LEGAL_DOC_TYPES.values()))["schema"]

# Finance doc types
for _doc_type, _info in FINANCE_DOC_TYPES.items():
    SCHEMA_REGISTRY[("finance", _doc_type)] = _info["schema"]
SCHEMA_REGISTRY[("finance", None)] = next(iter(FINANCE_DOC_TYPES.values()))["schema"]


# ---------------------------------------------------------------------------
# Doc-type catalogue per industry (for the Documents Pipeline filter chips)
# ---------------------------------------------------------------------------

DOC_TYPES_BY_INDUSTRY: Dict[str, Dict[str, Dict[str, Any]]] = {
    "healthcare":     GP_DOC_TYPES,
    "healthcare_lab": NHLS_DOC_TYPES,
    "logistics":      TRT_DOC_TYPES,
    "mining":         MINING_DOC_TYPES,
    "legal":          LEGAL_DOC_TYPES,
    "finance":        FINANCE_DOC_TYPES,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalise_industry(industry_type: Optional[str]) -> str:
    """Normalise an industry_type from the workspaces table or query param."""
    if not industry_type:
        return "healthcare"
    return industry_type.strip().lower().replace("-", "_")


def get_extraction_schema(industry_type: str, doc_type: Optional[str] = None) -> Type[BaseModel]:
    """
    Look up the Pydantic extraction schema for a given industry + doc_type.
    Falls back through industry default → healthcare default.
    """
    industry = normalise_industry(industry_type)

    # Exact match
    schema = SCHEMA_REGISTRY.get((industry, doc_type))
    if schema:
        return schema

    # Industry default (doc_type=None)
    schema = SCHEMA_REGISTRY.get((industry, None))
    if schema:
        return schema

    # Ultimate fallback — never hand a 500 back to the upload pipeline.
    return GPPatientRecordExtraction


def list_doc_types(industry_type: str) -> List[Dict[str, Any]]:
    """
    Return the doc-type catalogue for a given industry — used to render filter
    chips on the Documents Pipeline screen and the per-tenant schema picker.
    """
    industry = normalise_industry(industry_type)
    catalogue = DOC_TYPES_BY_INDUSTRY.get(industry, {})
    return [
        {
            "doc_type":      doc_type,
            "display_name":  info.get("display_name", doc_type),
            "department":    info.get("department"),
            "sub_category":  info.get("sub_category"),
        }
        for doc_type, info in catalogue.items()
    ]


def list_industries() -> List[Dict[str, Any]]:
    """Return the industry catalogue. Used by the schema-picker UI."""
    return [
        {"industry_type": industry_id, **meta}
        for industry_id, meta in INDUSTRIES.items()
    ]
