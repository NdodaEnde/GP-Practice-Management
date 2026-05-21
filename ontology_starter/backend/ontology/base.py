"""
Base classes for ontology objects.

Every object type in the ontology inherits from OntologyObject. The base class
exists to enforce a consistent interface: every object has a stable identity,
a display template, a PII classification, declared link targets, and metadata
that downstream consumers (serialisers, search, FHIR export, UI codegen,
audit log) can introspect uniformly.

The ontology layer sits *above* persistence. SQLAlchemy models stay where
they are; ontology objects are hydrated from rows via mappers defined per
object type.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, ClassVar, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PIILevel(str, Enum):
    """How sensitive is this property under POPIA.

    The classification drives access control, audit logging granularity,
    and what can appear in search indexes vs only the authoritative record.
    """

    NONE = "none"           # not personal data (e.g. system timestamps)
    LOW = "low"             # personal but not sensitive (e.g. preferred language)
    MEDIUM = "medium"       # identifying (e.g. name, contact)
    HIGH = "high"           # sensitive personal info (e.g. health data, ID number)
    SPECIAL = "special"     # special-category under POPIA s26 (e.g. biometric, sexual orientation)


class SearchBehaviour(str, Enum):
    """How this property participates in search.

    Drives both the search index pipeline (which fields get embedded,
    tokenised, or indexed verbatim) and the query layer (what filters
    are available).
    """

    NONE = "none"               # excluded from search entirely
    EXACT = "exact"             # exact-match only (e.g. ID number, scheme membership number)
    TOKENISED = "tokenised"     # standard text tokenisation (e.g. names, addresses)
    SEMANTIC = "semantic"       # embedded for vector search (e.g. consultation notes, complaints)
    FACETED = "faceted"         # available as a structured filter (e.g. sex, age band, scheme)


class OntologyProperty:
    """Metadata wrapper for an object property.

    Use as a Pydantic Field default factory companion to attach ontology
    metadata to a property declaration. The metadata is read by the
    schema generator, the search indexer, the FHIR exporter, and the
    audit log to know how to treat each field.
    """

    def __init__(
        self,
        *,
        pii: PIILevel = PIILevel.NONE,
        fhir: Optional[str] = None,
        search: SearchBehaviour = SearchBehaviour.NONE,
        display_label: Optional[str] = None,
        description: Optional[str] = None,
        link_to: Optional[str] = None,             # if this property is a foreign reference
        link_cardinality: Optional[str] = None,    # "one" | "many" — defaults inferred from type
        immutable_after_create: bool = False,
        deprecated: bool = False,
    ) -> None:
        self.pii = pii
        self.fhir = fhir
        self.search = search
        self.display_label = display_label
        self.description = description
        self.link_to = link_to
        self.link_cardinality = link_cardinality
        self.immutable_after_create = immutable_after_create
        self.deprecated = deprecated


def Prop(
    default: Any = ...,
    *,
    pii: PIILevel = PIILevel.NONE,
    fhir: Optional[str] = None,
    search: SearchBehaviour = SearchBehaviour.NONE,
    display_label: Optional[str] = None,
    description: Optional[str] = None,
    link_to: Optional[str] = None,
    link_cardinality: Optional[str] = None,
    immutable_after_create: bool = False,
    deprecated: bool = False,
    **field_kwargs: Any,
) -> Any:
    """Shortcut: declare a property with ontology metadata in one call.

    Usage:
        surname: str = Prop(pii=PIILevel.MEDIUM, fhir="name.family",
                            search=SearchBehaviour.TOKENISED)
    """
    metadata = OntologyProperty(
        pii=pii,
        fhir=fhir,
        search=search,
        display_label=display_label,
        description=description,
        link_to=link_to,
        link_cardinality=link_cardinality,
        immutable_after_create=immutable_after_create,
        deprecated=deprecated,
    )
    # Stash the metadata in Pydantic's json_schema_extra so the schema
    # generator and downstream consumers can read it back out.
    json_schema_extra = field_kwargs.pop("json_schema_extra", {}) or {}
    json_schema_extra["ontology"] = {
        "pii": metadata.pii.value,
        "fhir": metadata.fhir,
        "search": metadata.search.value,
        "display_label": metadata.display_label,
        "description": metadata.description,
        "link_to": metadata.link_to,
        "link_cardinality": metadata.link_cardinality,
        "immutable_after_create": metadata.immutable_after_create,
        "deprecated": metadata.deprecated,
    }
    return Field(default, json_schema_extra=json_schema_extra, **field_kwargs)


class OntologyObject(BaseModel):
    """Base class for every object type in the ontology.

    Subclasses declare class-level metadata (display template, FHIR resource
    name, PII level, audited flag) and per-field metadata via Prop().

    The base reserves the system fields every object needs: id, practice_id
    (multi-tenancy boundary), created_at, updated_at, soft-delete marker.
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    # ---- Class-level ontology metadata (override in subclasses) -----------

    __object_type_name__: ClassVar[str] = ""
    __display_template__: ClassVar[str] = "{id}"
    __fhir_resource__: ClassVar[Optional[str]] = None
    __pii_level__: ClassVar[PIILevel] = PIILevel.NONE
    __audited__: ClassVar[bool] = True

    # ---- System fields present on every object ----------------------------

    id: UUID = Prop(
        description="Stable identity across all systems and exports.",
        immutable_after_create=True,
    )
    practice_id: UUID = Prop(
        description="The practice this object belongs to. Multi-tenancy boundary — "
                    "queries are always scoped by this.",
        immutable_after_create=True,
        link_to="Practice",
        link_cardinality="one",
    )
    created_at: datetime = Prop(
        description="When this object was first persisted.",
        immutable_after_create=True,
    )
    updated_at: datetime = Prop(
        description="When this object was last mutated by any action.",
    )
    deleted_at: Optional[datetime] = Prop(
        default=None,
        description="Soft-delete marker. Objects are never hard-deleted; they are "
                    "tombstoned for audit and recoverability.",
    )

    # ---- Helpers ----------------------------------------------------------

    def display_name(self) -> str:
        """Render the configured display template against this instance's values."""
        try:
            return self.__display_template__.format(**self.model_dump(mode="python"))
        except (KeyError, AttributeError):
            return f"{self.__object_type_name__}({self.id})"

    @classmethod
    def ontology_schema(cls) -> dict[str, Any]:
        """Emit a JSON description of this object type for codegen and introspection.

        Consumers: frontend TypeScript codegen, /api/ontology/schema endpoint,
        FHIR exporter, search indexer config.
        """
        schema = cls.model_json_schema()
        return {
            "object_type": cls.__object_type_name__,
            "display_template": cls.__display_template__,
            "fhir_resource": cls.__fhir_resource__,
            "pii_level": cls.__pii_level__.value,
            "audited": cls.__audited__,
            "properties": schema.get("properties", {}),
            "required": schema.get("required", []),
        }
