"""
Patient ontology object.

This is the first object type to be modelled in the ontology layer. It is
deliberately rich in metadata: every property carries its PII classification,
its FHIR mapping, its search behaviour, its display semantics. Downstream
consumers — search indexer, FHIR exporter, audit log, frontend codegen,
access control — read this metadata rather than reimplementing it.

Design notes:

- The model is **read-shaped**, not write-shaped. It represents a patient
  as the platform thinks of them, not as a form to fill in. Write paths go
  through Actions (see ontology/actions/), not by mutating this directly.

- SA-specific concerns are inline, not abstracted. ID number, medical aid
  scheme membership, population group — these are first-class fields
  because they ARE the domain.

- Links to other ontology objects are declared via `link_to=` on Prop().
  The links registry (ontology/links/) reads these to build the graph.

- The model does not know about persistence. A mapper (mappers/patient.py,
  not included in this starter) hydrates Patient from the SQLAlchemy row.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import ClassVar, Optional
from uuid import UUID

from pydantic import field_validator, model_validator

from ontology.base import OntologyObject, PIILevel, Prop, SearchBehaviour
from ontology.enums.patient_enums import (
    BiologicalSex,
    HomeLanguage,
    IdentifierType,
    PatientStatus,
    PopulationGroup,
    Title,
)
from ontology.validators.sa_id import InvalidSAIDError, validate_and_decode_sa_id


class Patient(OntologyObject):
    """A patient registered at a practice.

    The Patient object is the spine of the clinical ontology — almost every
    other clinical object (Consultation, Diagnosis, Medication, LabResult,
    OpenLoop, Document-after-promotion) links back to a Patient.

    Identity is by `id` (UUID). External identifiers — SA ID number,
    passport, medical aid membership number — are properties, not the
    primary key. This matters because:

    - Patients can be registered before they have a verified ID
      (emergency walk-ins, minors, refugees).
    - Patients sometimes change their ID number (corrections, naturalisation).
    - Entity resolution may merge two records that initially had different
      identifiers but turn out to be the same person.

    The `merged_into_patient_id` field supports the ER outcome: when two
    Patient records are determined to be the same person, the duplicate is
    soft-deleted with this pointer set, so historical references still
    resolve.
    """

    # ---- Class-level metadata -------------------------------------------

    __object_type_name__: ClassVar[str] = "Patient"
    __display_template__: ClassVar[str] = "{surname}, {first_name} ({date_of_birth})"
    __fhir_resource__: ClassVar[Optional[str]] = "Patient"
    __pii_level__: ClassVar[PIILevel] = PIILevel.HIGH
    __audited__: ClassVar[bool] = True

    # ---- Identity & demographics ----------------------------------------

    title: Optional[Title] = Prop(
        default=None,
        pii=PIILevel.LOW,
        fhir="name.prefix",
        search=SearchBehaviour.NONE,
        display_label="Title",
        description="Honorific. Optional — empty is fine.",
    )

    first_name: str = Prop(
        pii=PIILevel.MEDIUM,
        fhir="name.given",
        search=SearchBehaviour.TOKENISED,
        display_label="First name",
        description="Given name as written on the patient's primary ID document.",
        min_length=1,
        max_length=100,
    )

    middle_names: Optional[str] = Prop(
        default=None,
        pii=PIILevel.MEDIUM,
        fhir="name.given",
        search=SearchBehaviour.TOKENISED,
        display_label="Middle names",
        description="All middle names as a single string. Splitting is a UI concern.",
        max_length=200,
    )

    surname: str = Prop(
        pii=PIILevel.MEDIUM,
        fhir="name.family",
        search=SearchBehaviour.TOKENISED,
        display_label="Surname",
        description="Family name. Indexed for fuzzy search to handle "
                    "transliteration variants (Mthembu/Mtembu).",
        min_length=1,
        max_length=100,
    )

    preferred_name: Optional[str] = Prop(
        default=None,
        pii=PIILevel.MEDIUM,
        fhir="name.use",
        search=SearchBehaviour.TOKENISED,
        display_label="Preferred name",
        description="How the patient prefers to be addressed. Falls back to "
                    "first_name when empty.",
        max_length=100,
    )

    date_of_birth: date = Prop(
        pii=PIILevel.HIGH,
        fhir="birthDate",
        search=SearchBehaviour.FACETED,
        display_label="Date of birth",
        description="Confirmed date of birth. If only an SA ID number is "
                    "available, this should be set from the decoded ID and "
                    "the cross-check enforced in the validator.",
        immutable_after_create=False,  # corrections are allowed via action
    )

    biological_sex: BiologicalSex = Prop(
        pii=PIILevel.HIGH,
        fhir="gender",
        search=SearchBehaviour.FACETED,
        display_label="Sex",
        description="Biological sex for clinical purposes. Gender identity, "
                    "if captured, is a separate property.",
    )

    population_group: Optional[PopulationGroup] = Prop(
        default=None,
        pii=PIILevel.SPECIAL,
        fhir=None,
        search=SearchBehaviour.FACETED,
        display_label="Population group",
        description="Self-declared only. Never inferred. Used for equity "
                    "reporting and required by some medical aid schemes for "
                    "BEE-linked benefit reporting.",
    )

    home_language: Optional[HomeLanguage] = Prop(
        default=None,
        pii=PIILevel.LOW,
        fhir="communication.language",
        search=SearchBehaviour.FACETED,
        display_label="Home language",
        description="Drives interpreter scheduling and printed-material language.",
    )

    # ---- Identifiers ----------------------------------------------------

    identifier_type: IdentifierType = Prop(
        default=IdentifierType.SA_ID,
        pii=PIILevel.HIGH,
        fhir="identifier.type",
        search=SearchBehaviour.FACETED,
        display_label="ID document type",
        description="What kind of identity document the patient provided. "
                    "Drives which validators run on `identifier_number`.",
    )

    identifier_number: Optional[str] = Prop(
        default=None,
        pii=PIILevel.HIGH,
        fhir="identifier.value",
        search=SearchBehaviour.EXACT,
        display_label="ID / passport number",
        description="The verbatim identifier from the ID document. For SA IDs, "
                    "the validator cross-checks DOB and sex.",
        max_length=50,
    )

    # ---- Contact --------------------------------------------------------

    primary_phone: Optional[str] = Prop(
        default=None,
        pii=PIILevel.MEDIUM,
        fhir="telecom.value",
        search=SearchBehaviour.EXACT,
        display_label="Primary phone",
        description="E.164 preferred (+27...). Validation is permissive — many "
                    "patients only have a partial number on file.",
        max_length=20,
    )

    email: Optional[str] = Prop(
        default=None,
        pii=PIILevel.MEDIUM,
        fhir="telecom.value",
        search=SearchBehaviour.EXACT,
        display_label="Email",
        description="Used for appointment reminders and patient-portal access.",
        max_length=200,
    )

    physical_address: Optional[str] = Prop(
        default=None,
        pii=PIILevel.MEDIUM,
        fhir="address.text",
        search=SearchBehaviour.TOKENISED,
        display_label="Physical address",
        description="Stored as a single string. SA addresses are often informal "
                    "(settlement names, no street numbers) — parsing into "
                    "structured fields adds complexity without much value.",
        max_length=500,
    )

    # ---- Medical aid ----------------------------------------------------

    medical_aid_scheme_id: Optional[UUID] = Prop(
        default=None,
        pii=PIILevel.MEDIUM,
        fhir="extension:medical-aid-scheme",
        search=SearchBehaviour.FACETED,
        display_label="Medical aid scheme",
        description="Foreign reference to the MedicalAidScheme registry. "
                    "Null if the patient is private/cash-paying.",
        link_to="MedicalAidScheme",
        link_cardinality="one",
    )

    medical_aid_plan: Optional[str] = Prop(
        default=None,
        pii=PIILevel.MEDIUM,
        fhir="extension:medical-aid-plan",
        search=SearchBehaviour.FACETED,
        display_label="Medical aid plan",
        description="The specific plan within the scheme (e.g. 'KeyCare Plus', "
                    "'Classic Smart'). Free text because the plan catalogue "
                    "changes faster than we want to model.",
        max_length=100,
    )

    medical_aid_membership_number: Optional[str] = Prop(
        default=None,
        pii=PIILevel.MEDIUM,
        fhir="identifier.value",
        search=SearchBehaviour.EXACT,
        display_label="Membership number",
        description="The scheme-issued member number. Strong ER signal when present.",
        max_length=50,
    )

    medical_aid_dependent_code: Optional[str] = Prop(
        default=None,
        pii=PIILevel.MEDIUM,
        fhir=None,
        search=SearchBehaviour.NONE,
        display_label="Dependent code",
        description="The dependent number within the membership (00 = main "
                    "member, 01+ = dependents). Required for accurate claims.",
        max_length=10,
    )

    # ---- Clinical context (denormalised, refreshed by maintainer) -------
    # These are summaries kept on the Patient for fast access on briefings.
    # The authoritative data lives on linked Consultation/Diagnosis/Medication.
    # A background worker keeps them in sync.

    active_chronic_conditions_summary: Optional[str] = Prop(
        default=None,
        pii=PIILevel.HIGH,
        fhir=None,
        search=SearchBehaviour.SEMANTIC,
        display_label="Chronic conditions",
        description="Materialised summary of the patient's active chronic "
                    "diagnoses, ranked by clinical weight. Refreshed by the "
                    "PatientSummaryMaintainer worker after any Diagnosis change.",
    )

    known_allergies_summary: Optional[str] = Prop(
        default=None,
        pii=PIILevel.HIGH,
        fhir="extension:allergy-summary",
        search=SearchBehaviour.TOKENISED,
        display_label="Known allergies",
        description="Materialised allergy list. Surfaced on every prescribing "
                    "screen as a safety check.",
    )

    last_consultation_at: Optional[datetime] = Prop(
        default=None,
        pii=PIILevel.MEDIUM,
        fhir=None,
        search=SearchBehaviour.FACETED,
        display_label="Last seen",
        description="Timestamp of the most recent consultation. Drives recall "
                    "queries ('patients not seen in 6 months').",
    )

    # ---- Lifecycle ------------------------------------------------------

    status: PatientStatus = Prop(
        default=PatientStatus.ACTIVE,
        pii=PIILevel.LOW,
        fhir="active",
        search=SearchBehaviour.FACETED,
        display_label="Status",
        description="Lifecycle status. Distinct from soft-delete: an inactive "
                    "patient is not deleted, just dormant.",
    )

    deceased_date: Optional[date] = Prop(
        default=None,
        pii=PIILevel.HIGH,
        fhir="deceasedDateTime",
        search=SearchBehaviour.NONE,
        display_label="Date of death",
        description="When status == DECEASED. Must be on or after date_of_birth.",
    )

    merged_into_patient_id: Optional[UUID] = Prop(
        default=None,
        pii=PIILevel.NONE,
        fhir=None,
        search=SearchBehaviour.NONE,
        display_label="Merged into",
        description="When this record was determined to be a duplicate, this "
                    "points to the canonical record. The merge is performed "
                    "by the MergePatients action.",
        link_to="Patient",
        link_cardinality="one",
    )

    # ---- Validation -----------------------------------------------------

    @field_validator("identifier_number")
    @classmethod
    def _normalise_identifier(cls, v: Optional[str]) -> Optional[str]:
        """Strip whitespace from identifiers — receptionists often include
        spaces that break downstream exact-match search."""
        if v is None:
            return None
        cleaned = "".join(v.split())
        return cleaned or None

    @model_validator(mode="after")
    def _cross_check_sa_id(self) -> "Patient":
        """If the identifier is an SA ID number, the encoded DOB and sex
        must match the captured date_of_birth and biological_sex. Mismatches
        are almost always transcription errors — surface them as validation
        errors so they're corrected at the source.

        Permanent residents and unknown-citizenship cases are handled by
        treating the SA ID validator as authoritative; if your domain needs
        to permit known-mismatches (e.g. confirmed gender transition), add
        an explicit `identifier_cross_check_waived` flag rather than weakening
        this check.
        """
        if self.identifier_type != IdentifierType.SA_ID:
            return self
        if not self.identifier_number:
            return self

        try:
            decoded = validate_and_decode_sa_id(self.identifier_number)
        except InvalidSAIDError as exc:
            raise ValueError(f"SA ID number invalid: {exc}") from exc

        if decoded.date_of_birth != self.date_of_birth:
            raise ValueError(
                f"Date of birth ({self.date_of_birth}) does not match the date "
                f"encoded in the SA ID number ({decoded.date_of_birth}). "
                "One of them is wrong — please verify against the ID document."
            )

        # Map BiologicalSex enum to the M/F codes the validator returns
        expected = "M" if self.biological_sex == BiologicalSex.MALE else (
            "F" if self.biological_sex == BiologicalSex.FEMALE else None
        )
        # Only enforce when sex is M or F; intersex/unknown bypass the check.
        if expected is not None and decoded.sex != expected:
            raise ValueError(
                f"Biological sex ({self.biological_sex.value}) does not match "
                f"the sex encoded in the SA ID number ({decoded.sex})."
            )

        return self

    @model_validator(mode="after")
    def _check_deceased_consistency(self) -> "Patient":
        if self.status == PatientStatus.DECEASED and self.deceased_date is None:
            raise ValueError("status=DECEASED requires deceased_date to be set.")
        if self.deceased_date and self.deceased_date < self.date_of_birth:
            raise ValueError("deceased_date cannot be earlier than date_of_birth.")
        return self

    # ---- Convenience accessors -----------------------------------------

    def full_name(self) -> str:
        """Render the patient's full name for display."""
        parts = []
        if self.title:
            parts.append(self.title.value)
        parts.append(self.first_name)
        if self.middle_names:
            parts.append(self.middle_names)
        parts.append(self.surname)
        return " ".join(parts)

    def age_in_years(self, as_of: Optional[date] = None) -> int:
        """Calculate the patient's age in completed years.

        Use the patient's `deceased_date` as the cap when applicable, so
        deceased patients don't keep ageing on the dashboard.
        """
        reference = as_of or date.today()
        if self.deceased_date and self.deceased_date < reference:
            reference = self.deceased_date

        age = reference.year - self.date_of_birth.year
        # Subtract one if birthday hasn't occurred yet this year
        if (reference.month, reference.day) < (
            self.date_of_birth.month,
            self.date_of_birth.day,
        ):
            age -= 1
        return age

    def is_minor(self, as_of: Optional[date] = None) -> bool:
        """SA minors (under 18) have different consent and POPIA rules."""
        return self.age_in_years(as_of=as_of) < 18
