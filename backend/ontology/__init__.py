"""
Ontology layer for the clinical document intelligence platform.

This package is the source of truth for what the platform's domain *is*.
Object types, links, and actions are declared here once and consumed by
every other part of the system:

    backend/ontology/
        base.py                  OntologyObject, Prop, PIILevel, SearchBehaviour
        objects/                 Object type declarations (Patient first)
        links/                   Typed relationships between objects
        actions/                 Declarative mutations with audit + reversal
        enums/                   Domain enums (SA-specific)
        validators/              Domain validators (SA ID, etc.)

Downstream consumers:
    backend/api/                 FastAPI routers — return ontology objects
    backend/search/              pgvector indexer reads search metadata
    backend/fhir/                FHIR exporter reads fhir mappings
    backend/audit/               Audit log reads __audited__ flag
    frontend/src/types/          TypeScript generated from /api/ontology/schema
"""

from ontology.base import (
    OntologyObject,
    OntologyProperty,
    PIILevel,
    Prop,
    SearchBehaviour,
)
from ontology.enums.consultation_enums import (
    ConsultationStatus,
    EncounterSetting,
    EncounterType,
)
from ontology.enums.document_enums import DocumentSource, DocumentStatus
from ontology.objects.consultation import Consultation
from ontology.objects.document import Document
from ontology.objects.patient import Patient

__all__ = [
    "OntologyObject",
    "OntologyProperty",
    "PIILevel",
    "Prop",
    "SearchBehaviour",
    "Patient",
    "Document",
    "DocumentSource",
    "DocumentStatus",
    "Consultation",
    "ConsultationStatus",
    "EncounterSetting",
    "EncounterType",
]
