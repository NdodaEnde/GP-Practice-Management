"""
Link registry.

Where object types are the nouns of the ontology, links are the verbs. A
link is a typed, directional, optionally-attributed relationship between
two object types. The registry lives in one file so the graph's shape is
visible at a glance.

Why a registry rather than just foreign keys on the objects?

  1. Bidirectional traversal. A foreign key knows "Patient.id is referenced
     by Consultation.patient_id" but doesn't make the reverse traversal
     (Patient -> their Consultations) a first-class operation. The registry
     does.

  2. Link metadata. Many relationships have their own properties — the
     confidence of an extraction link, the timestamp of when a Document was
     promoted to a Patient, the actor who confirmed a patient match. A
     registry lets these live as first-class data, not buried in join tables.

  3. Query composition. The query layer (Phase 3) compiles ontology-level
     traversals into SQL. It needs to know what's a valid traversal and
     what isn't. The registry is that source of truth.

This file is the *declaration*. The actual storage of link instances
(when needed beyond a simple FK) is in tables like document_patient_links,
consultation_diagnoses, etc., managed by SQLAlchemy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Cardinality(str, Enum):
    ONE_TO_ONE = "1:1"
    ONE_TO_MANY = "1:N"
    MANY_TO_MANY = "N:M"


@dataclass(frozen=True)
class LinkType:
    """A declared relationship between two object types."""

    name: str                       # "has_consultation", "extracts_data_for"
    source_type: str                # "Patient"
    target_type: str                # "Consultation"
    cardinality: Cardinality
    inverse_name: str               # name of the link when traversed in reverse
    description: str
    # Optional properties carried on the link itself (not on either endpoint)
    link_properties: tuple[str, ...] = field(default_factory=tuple)
    # Whether the link is automatic (FK-derived) or explicit (separate join table)
    explicit_table: Optional[str] = None


# ---- Registered links ---------------------------------------------------
# Listed in clusters that map to the three first-object-types beachhead.
# Add new links here as new object types come online; this file is the
# canonical place to see the shape of the graph.

LINKS: tuple[LinkType, ...] = (

    # Patient <-> Consultation -----------------------------------------
    LinkType(
        name="has_consultation",
        source_type="Patient",
        target_type="Consultation",
        cardinality=Cardinality.ONE_TO_MANY,
        inverse_name="consulted_patient",
        description="A Patient has many Consultations. The patient_id FK on "
                    "Consultation is the storage; the registry makes the "
                    "traversal first-class in the query layer.",
    ),

    # Document -> extraction targets ----------------------------------
    # A scanned document, after extraction and validation, contributes data
    # to one or more clinical objects. The link is *explicit* because it
    # carries metadata: extraction confidence, validation status, the actor
    # who promoted it.
    LinkType(
        name="extracts_data_for_patient",
        source_type="Document",
        target_type="Patient",
        cardinality=Cardinality.MANY_TO_MANY,
        inverse_name="sourced_from_documents",
        description="A Document, after promotion, contributes data to a Patient "
                    "record. The link carries the confidence score and the "
                    "patient-match confirmation evidence.",
        link_properties=("confidence_score", "promoted_at", "promoted_by_user_id",
                         "patient_match_evidence"),
        explicit_table="document_patient_links",
    ),
    LinkType(
        name="documents_consultation",
        source_type="Document",
        target_type="Consultation",
        cardinality=Cardinality.MANY_TO_MANY,
        inverse_name="documented_by",
        description="A Document is the source of one or more Consultations. "
                    "The link carries the extraction confidence and the "
                    "validation status at promotion time.",
        link_properties=("confidence_score", "validation_status"),
        explicit_table="document_consultation_links",
    ),

    # Patient <-> Patient (entity resolution outcome) ------------------
    LinkType(
        name="merged_into",
        source_type="Patient",
        target_type="Patient",
        cardinality=Cardinality.ONE_TO_ONE,
        inverse_name="absorbed_duplicates",
        description="When ER determines two Patient records are the same person, "
                    "the duplicate is soft-deleted with this link pointing to "
                    "the canonical record.",
    ),

    # MedicalAidScheme -> Patient -------------------------------------
    LinkType(
        name="covers_patient",
        source_type="MedicalAidScheme",
        target_type="Patient",
        cardinality=Cardinality.ONE_TO_MANY,
        inverse_name="member_of_scheme",
        description="A scheme covers many patients. Foreign-key sourced from "
                    "Patient.medical_aid_scheme_id.",
    ),

    # Practice -> Patient ---------------------------------------------
    LinkType(
        name="registered_patient",
        source_type="Practice",
        target_type="Patient",
        cardinality=Cardinality.ONE_TO_MANY,
        inverse_name="registered_at_practice",
        description="The multi-tenancy boundary. Queries are always scoped by "
                    "the actor's practice access. Sourced from Patient.practice_id.",
    ),
)


def get_links_from(object_type: str) -> tuple[LinkType, ...]:
    """All outgoing links from a given object type."""
    return tuple(link for link in LINKS if link.source_type == object_type)


def get_links_to(object_type: str) -> tuple[LinkType, ...]:
    """All incoming links to a given object type (for reverse traversal)."""
    return tuple(link for link in LINKS if link.target_type == object_type)


def find_link(source: str, target: str, name: Optional[str] = None) -> Optional[LinkType]:
    """Look up a specific link by endpoints (and optionally name)."""
    for link in LINKS:
        if link.source_type == source and link.target_type == target:
            if name is None or link.name == name:
                return link
    return None
