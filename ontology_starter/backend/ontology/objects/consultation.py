"""
Consultation ontology object.

A Consultation represents a clinical encounter between a patient and a
practitioner — the third corner of the Patient-Document-Consultation
beachhead. Every clinical fact in the system (a Diagnosis, a Medication,
a Vitals reading, a LabResult) is recorded *at* a Consultation.

What a Consultation IS vs. what it CONTAINS — the line not to cross
--------------------------------------------------------------------

A Consultation has three layers of content, and only the first two live
on this object:

  1. The encounter itself: when, where, who, what type. These are
     properties on Consultation (encounter_date, setting, practitioner_id,
     encounter_type).

  2. The findings recorded during the encounter, as free-text narrative:
     chief_complaint, presenting_complaint, history, examination,
     assessment, plan. These ARE properties on Consultation, tagged
     SEMANTIC for embedding. This is a conscious choice: the search
     payoff comes from these fields, and they're authored as text by
     the clinician anyway, so modelling them as separate objects would
     buy little. Note: for now.

  3. The structured clinical objects parsed OUT of those findings:
     Diagnosis (ICD-10-coded), Medication (NAPPI-coded), Vitals,
     LabResult, OpenLoop. These are NOT properties on Consultation —
     they are independent ontology objects with their own lifecycle,
     audit trail, and coding workflow, and they link back here via
     the registry (Consultation <- recorded_diagnosis - Diagnosis,
     etc.).

The line you don't want to cross: a `diagnoses: list[Diagnosis]` field
directly on Consultation. Embedding would conflate the encounter record
with its derived facts, make the audit graph harder to traverse, and
make every Diagnosis edit require a Consultation rewrite. Don't do it.

Design notes
------------

  - The model is read-shaped. Mutations flow through Actions
    (RecordConsultation, AmendConsultationNotes, CancelConsultation,
    CompleteConsultation). Direct mutation bypasses the audit log.

  - Narrative fields are tagged search=SEMANTIC. The embedding itself
    is NOT a property on this object — there is no `embedding: list[float]`
    field. The action layer emits ConsultationCreated/Updated events,
    a separate indexer worker reads those events plus the SEMANTIC
    metadata flag, and writes vectors into a pgvector store keyed by
    (consultation_id, field_name). Object declares intent; worker does
    the work.

  - Billing codes are present but light-touch. A full billing model
    (line items, modifiers, claim status, reconciliation) belongs in a
    separate Claim object that links to this one. Here we capture the
    ICD-10s that justify the consultation and the procedure codes that
    were performed, because they're authored by the clinician at the
    point of encounter.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import ClassVar, Optional
from uuid import UUID

from pydantic import model_validator

from ontology.base import OntologyObject, PIILevel, Prop, SearchBehaviour
from ontology.enums.consultation_enums import (
    ConsultationStatus,
    EncounterSetting,
    EncounterType,
)


class Consultation(OntologyObject):
    """A clinical encounter at a practice.

    A Consultation has two creation paths:

    1. Recorded live — the clinician opens the platform during/after
       the visit, types into structured fields. Status moves through
       PLANNED → IN_PROGRESS → COMPLETED.

    2. Reconstructed from paper — the digitisation pipeline extracts a
       past encounter from a scanned record and promotes it. Status is
       typically COMPLETED immediately, `is_reconstructed_from_paper`
       is True, and `source_document_id` points back to the Document.

    Both paths produce the same shape of record, which is the point —
    queries and briefings don't care how the data arrived.
    """

    # ---- Class-level metadata -------------------------------------------

    __object_type_name__: ClassVar[str] = "Consultation"
    __display_template__: ClassVar[str] = "{encounter_date} consultation"
    __fhir_resource__: ClassVar[Optional[str]] = "Encounter"
    __pii_level__: ClassVar[PIILevel] = PIILevel.HIGH
    __audited__: ClassVar[bool] = True

    # ---- Identity & scoping ---------------------------------------------

    patient_id: UUID = Prop(
        pii=PIILevel.HIGH,
        fhir="subject",
        search=SearchBehaviour.FACETED,
        display_label="Patient",
        description="The patient this consultation is about. Foreign reference; "
                    "the patient record itself lives on the Patient object.",
        link_to="Patient",
        link_cardinality="one",
        immutable_after_create=True,
    )

    practitioner_id: UUID = Prop(
        pii=PIILevel.LOW,
        fhir="participant.individual",
        search=SearchBehaviour.FACETED,
        display_label="Practitioner",
        description=(
            "The HPCSA-registered clinician who actually CONDUCTED the encounter. "
            "Required. Critically distinct from the user who VALIDATED the "
            "digitised record (Document.validated_by_user_id) — that's often a "
            "receptionist or admin clicking 'approve' in the queue, not the "
            "doctor who saw the patient. "
            "Example: a 2019 paper consultation scanned and validated in 2026 "
            "by an admin assistant — practitioner_id is the doctor named on the "
            "2019 record, NOT the 2026 admin. Conflating these silently "
            "misattributes years of clinical activity to admin staff, which is "
            "an HPCSA-grade regulatory hazard. "
            "TODO: once a Practitioner ontology object exists (HPCSA number, "
            "scope of practice, qualifications, signature image), repoint "
            "link_to. For now, link to User and rely on a User.is_practitioner "
            "flag or equivalent."
        ),
        link_to="User",
        link_cardinality="one",
    )

    # ---- Temporal -------------------------------------------------------

    encounter_date: date = Prop(
        pii=PIILevel.MEDIUM,
        fhir="period.start",
        search=SearchBehaviour.FACETED,
        display_label="Date",
        description=(
            "The calendar day the encounter actually HAPPENED — clinical "
            "reality. CRITICALLY DISTINCT from `created_at` (inherited from "
            "OntologyObject), which is when this row was first persisted. "
            "Example that exercises every timestamp on the platform: a paper "
            "consultation from 2019, scanned in 2026 and promoted yesterday. "
            "encounter_date is 2019. created_at is yesterday. The source "
            "Document carries its own uploaded_at, parsed_at, validated_at. "
            "All are correct. "
            "Query layer MUST be explicit about which date a question means. "
            "  - 'recent consultations' (clinician view): encounter_date "
            "  - 'recent data entry' (practice manager / billing audit): created_at "
            "  - 'docs awaiting validation' (ops): Document.uploaded_at "
            "Type is `date`, not `datetime`, on purpose. Most SA primary care "
            "consultations don't capture start times — only the day. When "
            "precise times ARE recorded, they go on encounter_start_at / "
            "encounter_end_at below. Do not 'fix' encounter_date back to "
            "datetime — you'll break paper-reconstruction promotion (where "
            "no time-of-day exists) and force a fake midnight value that "
            "skews downstream analytics."
        ),
    )

    encounter_start_at: Optional[datetime] = Prop(
        default=None,
        pii=PIILevel.MEDIUM,
        fhir="period.start",
        search=SearchBehaviour.NONE,
        display_label="Started at",
        description="Precise timestamp the encounter began. Null for "
                    "reconstructed-from-paper records that captured only the date.",
    )

    encounter_end_at: Optional[datetime] = Prop(
        default=None,
        pii=PIILevel.MEDIUM,
        fhir="period.end",
        search=SearchBehaviour.NONE,
        display_label="Ended at",
        description="Precise timestamp the encounter ended. Used for duration "
                    "computation and (for billing) for time-based codes.",
    )

    # ---- Type & setting -------------------------------------------------

    encounter_type: EncounterType = Prop(
        default=EncounterType.CONSULTATION,
        pii=PIILevel.MEDIUM,
        fhir="class",
        search=SearchBehaviour.FACETED,
        display_label="Type",
        description="What kind of encounter this was. Drives billing rules "
                    "and the documentation template shown in the UI.",
    )

    setting: EncounterSetting = Prop(
        default=EncounterSetting.PRACTICE,
        pii=PIILevel.MEDIUM,
        fhir="location.physicalType",
        search=SearchBehaviour.FACETED,
        display_label="Setting",
        description="Where the encounter physically (or virtually) took place. "
                    "Distinct from type: a TELEHEALTH encounter has setting "
                    "REMOTE; a HOME_VISIT has setting PATIENT_HOME.",
    )

    # ---- Clinical narrative (the SOAP-shaped findings) ------------------
    # These six fields are the verbatim findings authored by the clinician.
    # All carry search=SEMANTIC: the indexer worker reads this flag and
    # populates the pgvector store. No embedding lives on this object.
    #
    # The structured clinical objects parsed OUT of these fields (Diagnosis,
    # Medication, Vitals, LabResult, OpenLoop) are separate ontology objects
    # that link back to this Consultation. See the module docstring for the
    # IS-vs-CONTAINS rationale.

    chief_complaint: Optional[str] = Prop(
        default=None,
        pii=PIILevel.HIGH,
        fhir="reasonCode",
        search=SearchBehaviour.SEMANTIC,
        display_label="Chief complaint",
        description="Short clinician-authored summary of why the patient "
                    "presented. The encounter's headline in lists and briefings. "
                    "Distinct from presenting_complaint (which is the patient's "
                    "own words). For 'cough 3/52', chief_complaint is 'persistent "
                    "cough'; presenting_complaint might be 'I've been coughing "
                    "for weeks and I'm scared it's TB'.",
        max_length=500,
    )

    presenting_complaint: Optional[str] = Prop(
        default=None,
        pii=PIILevel.HIGH,
        fhir=None,
        search=SearchBehaviour.SEMANTIC,
        display_label="Presenting complaint",
        description="The patient's own description of what brought them in, "
                    "in their words (or paraphrased into them). Embedded for "
                    "semantic search — this is the field that lets clinicians "
                    "find 'recent chest pain' or 'concerned about TB' across "
                    "the whole patient history, even when the structured "
                    "diagnosis says something different.",
        max_length=4000,
    )

    history: Optional[str] = Prop(
        default=None,
        pii=PIILevel.HIGH,
        fhir=None,
        search=SearchBehaviour.SEMANTIC,
        display_label="History",
        description="History of presenting illness plus relevant past medical, "
                    "family, social, and medication history captured at this "
                    "encounter. The 'S' in SOAP. Semantic search target — this "
                    "is where 'TB exposure' or 'recent travel to Limpopo' will "
                    "show up.",
        max_length=8000,
    )

    examination: Optional[str] = Prop(
        default=None,
        pii=PIILevel.HIGH,
        fhir=None,
        search=SearchBehaviour.SEMANTIC,
        display_label="Examination",
        description="Physical examination findings recorded at the encounter. "
                    "The 'O' in SOAP. Free-text; structured Vitals (BP, pulse, "
                    "temperature, SpO2) are separate Vitals objects that link "
                    "back to this Consultation, not duplicated here.",
        max_length=8000,
    )

    assessment: Optional[str] = Prop(
        default=None,
        pii=PIILevel.HIGH,
        fhir=None,
        search=SearchBehaviour.SEMANTIC,
        display_label="Assessment",
        description="Clinical reasoning / working diagnosis / differential. "
                    "The 'A' in SOAP. Distinct from the coded Diagnosis objects "
                    "(which are separate ontology objects with ICD-10 codes) — "
                    "this is the prose; those are the codes. Both exist because "
                    "the prose carries reasoning that the code can't.",
        max_length=8000,
    )

    plan: Optional[str] = Prop(
        default=None,
        pii=PIILevel.HIGH,
        fhir=None,
        search=SearchBehaviour.SEMANTIC,
        display_label="Plan",
        description="Agreed care plan, prescriptions written, investigations "
                    "ordered, follow-up instructions, safety-netting. The 'P' "
                    "in SOAP. Semantic search target because open-loop detectors "
                    "('stress test recommended', 'review in 6 weeks', "
                    "'specialist referral pending') read this field to spawn "
                    "follow-up trackers.",
        max_length=4000,
    )

    # ---- Lifecycle ------------------------------------------------------

    status: ConsultationStatus = Prop(
        default=ConsultationStatus.COMPLETED,
        pii=PIILevel.LOW,
        fhir="status",
        search=SearchBehaviour.FACETED,
        display_label="Status",
        description="Lifecycle of the consultation record. Reconstructed-from-"
                    "paper consultations default to COMPLETED; live encounters "
                    "move through the lifecycle.",
    )

    completed_at: Optional[datetime] = Prop(
        default=None,
        pii=PIILevel.NONE,
        fhir=None,
        search=SearchBehaviour.FACETED,
        display_label="Completed at",
        description="When status moved to COMPLETED. Required when the "
                    "consultation is in a completed state; null otherwise.",
    )

    # ---- Source provenance ----------------------------------------------

    source_document_id: Optional[UUID] = Prop(
        default=None,
        pii=PIILevel.NONE,
        fhir=None,
        search=SearchBehaviour.NONE,
        display_label="Source document",
        description="When this consultation was reconstructed from a scanned "
                    "record, points to the Document it came from. Null for "
                    "live-recorded consultations.",
        link_to="Document",
        link_cardinality="one",
    )

    is_reconstructed_from_paper: bool = Prop(
        default=False,
        pii=PIILevel.NONE,
        fhir=None,
        search=SearchBehaviour.FACETED,
        display_label="Reconstructed from paper",
        description="True when this record was extracted from a scanned "
                    "historical document rather than typed live. Affects "
                    "trust scoring (older, paper-sourced records have less "
                    "complete narrative) and surfaces a 'sourced from PDF' "
                    "indicator in the UI.",
    )

    # ---- Billing-adjacent (light touch) ---------------------------------

    billing_icd10_codes: Optional[list[str]] = Prop(
        default=None,
        pii=PIILevel.LOW,
        fhir="reasonCode.coding",
        search=SearchBehaviour.FACETED,
        display_label="ICD-10 codes",
        description="ICD-10 diagnosis codes that justify the consultation for "
                    "billing. Empty list and None are treated as 'no codes "
                    "captured yet' — both mean the same thing to consumers.",
    )

    procedure_codes: Optional[list[str]] = Prop(
        default=None,
        pii=PIILevel.LOW,
        fhir=None,
        search=SearchBehaviour.FACETED,
        display_label="Procedure codes",
        description="Procedure/tariff codes performed during the encounter "
                    "(SAMA codes in SA). The full claim model lives on the "
                    "Claim object; these are captured at the point of "
                    "encounter because the clinician authors them, not the "
                    "biller.",
    )

    # ---- Validation -----------------------------------------------------

    @model_validator(mode="after")
    def _check_completed_consistency(self) -> "Consultation":
        """COMPLETED consultations must have completed_at set, and vice versa.

        Without the timestamp, downstream consumers (last-seen calculation,
        recall queries, billing windows) can't anchor when the encounter
        actually concluded.
        """
        if self.status == ConsultationStatus.COMPLETED and self.completed_at is None:
            raise ValueError(
                "status=COMPLETED requires completed_at to be set."
            )
        if self.completed_at is not None and self.status not in (
            ConsultationStatus.COMPLETED,
        ):
            raise ValueError(
                f"completed_at is set but status={self.status.value} — "
                "completed_at only makes sense when status=COMPLETED."
            )
        return self

    @model_validator(mode="after")
    def _check_encounter_time_ordering(self) -> "Consultation":
        """encounter_end_at must be at or after encounter_start_at when both set.

        A negative-duration encounter is a data-entry bug almost always —
        clock skew between systems, a copy-paste of timestamps in the
        wrong order, or a UI form that swapped fields. Catching it at write
        time keeps the duration calculations honest.
        """
        if (
            self.encounter_start_at is not None
            and self.encounter_end_at is not None
            and self.encounter_end_at < self.encounter_start_at
        ):
            raise ValueError(
                f"encounter_end_at ({self.encounter_end_at.isoformat()}) is "
                f"earlier than encounter_start_at "
                f"({self.encounter_start_at.isoformat()})."
            )
        return self

    @model_validator(mode="after")
    def _check_encounter_date_matches_start(self) -> "Consultation":
        """encounter_date must equal the date portion of encounter_start_at.

        Mismatches usually indicate a timezone mishandling bug (the date was
        captured in one zone, the timestamp in another). Both fields exist
        because reconstructed records often have only the date — but when
        both are present they have to agree.
        """
        if self.encounter_start_at is None:
            return self
        # Compare in UTC to avoid local/aware confusion; require the date
        # portion of the timestamp to match the explicit date field.
        start_date = self.encounter_start_at.astimezone(timezone.utc).date()
        if start_date != self.encounter_date:
            raise ValueError(
                f"encounter_date ({self.encounter_date.isoformat()}) does not "
                f"match the date of encounter_start_at "
                f"({start_date.isoformat()}, UTC). Likely a timezone bug — "
                "one of these was captured in a different zone."
            )
        return self

    @model_validator(mode="after")
    def _check_reconstructed_has_source(self) -> "Consultation":
        """A consultation marked as reconstructed-from-paper must point to its
        source document. Otherwise the provenance trail is broken — we know
        this came from a scan but can't say which one.
        """
        if (
            self.is_reconstructed_from_paper
            and self.source_document_id is None
        ):
            raise ValueError(
                "is_reconstructed_from_paper=True requires source_document_id "
                "to be set."
            )
        return self

    @model_validator(mode="after")
    def _check_source_implies_reconstructed(self) -> "Consultation":
        """The reverse: if a source document is referenced, the consultation
        must be flagged as reconstructed. Without this, the UI 'sourced from
        PDF' indicator silently drops off on consultations whose flag was
        forgotten at write time.
        """
        if (
            self.source_document_id is not None
            and not self.is_reconstructed_from_paper
        ):
            raise ValueError(
                "source_document_id is set but is_reconstructed_from_paper is "
                "False — these flags are linked; set both or neither."
            )
        return self

    # ---- Convenience accessors -----------------------------------------

    def duration_minutes(self) -> Optional[int]:
        """Length of the encounter in whole minutes, or None when either
        endpoint timestamp is missing."""
        if self.encounter_start_at is None or self.encounter_end_at is None:
            return None
        delta = self.encounter_end_at - self.encounter_start_at
        return int(delta.total_seconds() // 60)

    def is_recent(
        self,
        within_days: int = 30,
        as_of: Optional[date] = None,
    ) -> bool:
        """True when this consultation occurred within the last `within_days`."""
        reference = as_of or date.today()
        return (reference - self.encounter_date) <= timedelta(days=within_days)

    def has_clinical_content(self) -> bool:
        """True when any narrative field is non-empty.

        A consultation without any narrative is either a stub (PLANNED, not
        yet started) or an operational record (CANCELLED, NO_SHOW). This
        helper lets briefing queries cheaply skip records that have nothing
        clinical to surface.
        """
        return any(
            (self.chief_complaint, self.presenting_complaint, self.history,
             self.examination, self.assessment, self.plan)
        )
