"""
Document ontology object.

A Document represents a single scanned or uploaded clinical artefact — a
referral letter, an old paper file page, a lab report image — moving
through the platform's parse → validate → promote pipeline.

Why Document is modelled before its extracted children (Diagnosis,
Medication, Vitals, LabResult): the Document is the *provenance anchor*.
Every clinical fact in the system traces back to a Document (or to a
live entry by a doctor). When a regulator, an auditor, or a clinician
asks "where did this fact come from?", the Document is the answer.

Design notes:

- The model is **read-shaped**. Mutations to a Document's state flow
  through Actions (UploadDocument, ParseDocument, ValidateDocument,
  PromoteDocumentToPatientRecord, RejectDocument). Direct mutation
  bypasses the audit log.

- Lifecycle is encoded in `status`. Timestamps for each transition
  (`parsed_at`, `validated_at`, `promoted_at`, `rejected_at`) are
  set as the document moves through the pipeline and are subject to
  monotonic ordering checks (you can't promote before validating).

- Promotion outcome (`promoted_to_patient_id`, `promoted_to_consultation_id`)
  is denormalised onto the Document for fast lookup. The authoritative
  N:M relationship lives in the `document_patient_links` and
  `document_consultation_links` tables declared in the link registry.

- The raw extracted JSONB (the LandingAI / ADE output) is NOT modelled
  here. It currently lives in the legacy `digitised_documents.extraction`
  column. Once Diagnosis / Medication / Vitals / LabResult become
  ontology objects, the structured content moves there and this
  Document only holds metadata. Adding a transitional `extraction_payload`
  field now would create a property that won't survive the next phase.
"""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar, Optional
from uuid import UUID

from pydantic import field_validator, model_validator

from ontology.base import OntologyObject, PIILevel, Prop, SearchBehaviour
from ontology.enums.document_enums import DocumentSource, DocumentStatus


class Document(OntologyObject):
    """A scanned or uploaded clinical document under the platform's care.

    A Document carries the *file* (filename, mime type, storage path,
    size, hash) plus the *journey* (who uploaded it, when, what state
    it's in, who validated, who promoted, where it ended up).

    The same physical PDF uploaded twice produces two Documents — the
    SHA-256 hash lets the platform detect this and surface a "duplicate
    upload" warning in the UI, but the records remain distinct because
    their provenance (uploader, timestamp, workspace) differs.
    """

    # ---- Class-level metadata -------------------------------------------

    __object_type_name__: ClassVar[str] = "Document"
    # Full UUID is verbose in UI; we override display_name() below to use
    # short_id() instead. The template is here for completeness / codegen.
    __display_template__: ClassVar[str] = "DOC-{id} {original_filename}"
    __fhir_resource__: ClassVar[Optional[str]] = "DocumentReference"
    __pii_level__: ClassVar[PIILevel] = PIILevel.HIGH
    __audited__: ClassVar[bool] = True

    # ---- Identity & storage ---------------------------------------------

    original_filename: str = Prop(
        pii=PIILevel.LOW,
        fhir="content.attachment.title",
        search=SearchBehaviour.TOKENISED,
        display_label="Filename",
        description="The filename as the user/scan-agent/watcher uploaded it. "
                    "Often informative ('Mthembu_referral_2024_03.pdf') and "
                    "occasionally meaningful for deduplication signal.",
        min_length=1,
        max_length=500,
    )

    mime_type: str = Prop(
        pii=PIILevel.NONE,
        fhir="content.attachment.contentType",
        search=SearchBehaviour.FACETED,
        display_label="File type",
        description="IANA media type (e.g. 'application/pdf', 'image/jpeg'). "
                    "Stored as a string rather than an enum because new image "
                    "formats appear faster than we want to track via enum changes.",
        max_length=100,
    )

    storage_path: str = Prop(
        pii=PIILevel.LOW,
        fhir="content.attachment.url",
        search=SearchBehaviour.NONE,
        display_label="Storage path",
        description="Object key in Supabase Storage (typically "
                    "'medical-records/<workspace_id>/<filename>'). Not user-facing.",
        max_length=1000,
    )

    file_size_bytes: int = Prop(
        pii=PIILevel.NONE,
        fhir="content.attachment.size",
        search=SearchBehaviour.NONE,
        display_label="File size",
        description="Size in bytes at upload. Used for storage quota accounting "
                    "and cost projections. Zero-byte files are treated as upload "
                    "errors rather than valid documents.",
        gt=0,
    )

    page_count: Optional[int] = Prop(
        default=None,
        pii=PIILevel.NONE,
        fhir=None,
        search=SearchBehaviour.FACETED,
        display_label="Pages",
        description="Number of pages once known (typically after parsing). "
                    "Null for non-paginated formats or pre-parse state.",
        ge=0,
    )

    sha256_hash: Optional[str] = Prop(
        default=None,
        pii=PIILevel.LOW,
        fhir=None,
        search=SearchBehaviour.EXACT,
        display_label="Content hash",
        description="SHA-256 hex digest of the file contents. Drives the "
                    "'this exact file has been uploaded before' detector. "
                    "Null until computed by the upload pipeline. Format is "
                    "enforced by the validator: exactly 64 lowercase hex chars.",
    )

    # ---- Source & provenance --------------------------------------------

    source: DocumentSource = Prop(
        default=DocumentSource.MANUAL_UPLOAD,
        pii=PIILevel.NONE,
        fhir=None,
        search=SearchBehaviour.FACETED,
        display_label="Ingest source",
        description="How this document entered the platform. Drives provenance "
                    "trust scoring and per-source billing meters.",
    )

    uploaded_by_user_id: Optional[UUID] = Prop(
        default=None,
        pii=PIILevel.LOW,
        fhir=None,
        search=SearchBehaviour.NONE,
        display_label="Uploaded by",
        description="The user who initiated the upload. Null when source is "
                    "automated (storage_watcher, scan_agent, batch with no "
                    "personal actor).",
        link_to="User",
        link_cardinality="one",
    )

    uploaded_at: datetime = Prop(
        pii=PIILevel.NONE,
        fhir=None,
        search=SearchBehaviour.FACETED,
        display_label="Uploaded at",
        description="When the file first arrived in the platform. Anchor "
                    "timestamp for all downstream pipeline ordering.",
    )

    scan_agent_workstation_id: Optional[str] = Prop(
        default=None,
        pii=PIILevel.LOW,
        fhir=None,
        search=SearchBehaviour.FACETED,
        display_label="Scan agent workstation",
        description="Identifier of the scanning workstation that uploaded the "
                    "file. Only meaningful when source == SCAN_AGENT. Useful "
                    "for diagnosing 'why are this workstation's scans not "
                    "appearing' support tickets.",
        max_length=200,
    )

    # ---- Parse pipeline -------------------------------------------------

    parse_model: Optional[str] = Prop(
        default=None,
        pii=PIILevel.NONE,
        fhir=None,
        search=SearchBehaviour.FACETED,
        display_label="Parser",
        description="Identifier of the model that extracted structured data "
                    "(e.g. 'landingai_ade'). Tracking this lets us correlate "
                    "regressions with a specific parser change.",
        max_length=100,
    )

    parse_model_version: Optional[str] = Prop(
        default=None,
        pii=PIILevel.NONE,
        fhir=None,
        search=SearchBehaviour.FACETED,
        display_label="Parser version",
        description="Specific version/build of the parser model. Pinned in "
                    "the document at parse time so we can pin re-runs.",
        max_length=100,
    )

    parsed_at: Optional[datetime] = Prop(
        default=None,
        pii=PIILevel.NONE,
        fhir=None,
        search=SearchBehaviour.FACETED,
        display_label="Parsed at",
        description="Timestamp parsing completed (success or failure).",
    )

    parse_confidence_avg: Optional[float] = Prop(
        default=None,
        pii=PIILevel.NONE,
        fhir=None,
        search=SearchBehaviour.FACETED,
        display_label="Parse confidence",
        description="Average confidence score across extracted fields, 0.0-1.0. "
                    "Used to triage the validation queue (low-confidence "
                    "documents surface first).",
        ge=0.0,
        le=1.0,
    )

    parse_error: Optional[str] = Prop(
        default=None,
        pii=PIILevel.MEDIUM,
        fhir=None,
        search=SearchBehaviour.NONE,
        display_label="Parse error",
        description="Error message when parsing failed. MEDIUM PII because "
                    "the message can embed extracted snippets from the document.",
        max_length=2000,
    )

    # ---- Validation pipeline --------------------------------------------

    validated_at: Optional[datetime] = Prop(
        default=None,
        pii=PIILevel.NONE,
        fhir=None,
        search=SearchBehaviour.FACETED,
        display_label="Validated at",
        description="When the human reviewer approved the extracted fields.",
    )

    validated_by_user_id: Optional[UUID] = Prop(
        default=None,
        pii=PIILevel.LOW,
        fhir=None,
        search=SearchBehaviour.NONE,
        display_label="Validated by",
        description="The user who validated the extracted fields. The accountable "
                    "party for the data's accuracy at promotion time.",
        link_to="User",
        link_cardinality="one",
    )

    validation_corrections_count: Optional[int] = Prop(
        default=None,
        pii=PIILevel.NONE,
        fhir=None,
        search=SearchBehaviour.FACETED,
        display_label="Corrections made",
        description="How many extracted fields the human changed during "
                    "validation. A long-running signal of parser quality — "
                    "rising correction counts on a stable parser version mean "
                    "drift in document type or quality.",
        ge=0,
    )

    # ---- Promotion outcome (denormalised pointers) ----------------------
    # The authoritative N:M relationship lives in document_patient_links and
    # document_consultation_links. These pointers are for the common 1:1
    # case (one document → one patient → one consultation) and for fast UI.

    promoted_at: Optional[datetime] = Prop(
        default=None,
        pii=PIILevel.NONE,
        fhir=None,
        search=SearchBehaviour.FACETED,
        display_label="Promoted at",
        description="When the document's data was written into the patient "
                    "record. Set by the PromoteDocumentToPatientRecord action.",
    )

    promoted_by_user_id: Optional[UUID] = Prop(
        default=None,
        pii=PIILevel.LOW,
        fhir=None,
        search=SearchBehaviour.NONE,
        display_label="Promoted by",
        description="The user who confirmed the patient match and triggered "
                    "promotion. Accountable for the patient-match decision.",
        link_to="User",
        link_cardinality="one",
    )

    promoted_to_patient_id: Optional[UUID] = Prop(
        default=None,
        pii=PIILevel.HIGH,
        fhir="subject",
        search=SearchBehaviour.FACETED,
        display_label="Promoted to patient",
        description="The patient this document's data was promoted into. The "
                    "patient-match decision is captured in the link properties "
                    "(see document_patient_links).",
        link_to="Patient",
        link_cardinality="one",
    )

    promoted_to_consultation_id: Optional[UUID] = Prop(
        default=None,
        pii=PIILevel.HIGH,
        fhir="context",
        search=SearchBehaviour.NONE,
        display_label="Promoted to consultation",
        description="The Consultation reconstructed from this document. "
                    "Null when the document didn't represent a consultation "
                    "(e.g. a standalone lab report attached to an existing "
                    "consultation).",
        link_to="Consultation",
        link_cardinality="one",
    )

    # ---- Rejection ------------------------------------------------------

    rejected_at: Optional[datetime] = Prop(
        default=None,
        pii=PIILevel.NONE,
        fhir=None,
        search=SearchBehaviour.FACETED,
        display_label="Rejected at",
        description="When the human determined the document was not useful "
                    "(wrong patient, illegible, duplicate, off-topic).",
    )

    rejected_by_user_id: Optional[UUID] = Prop(
        default=None,
        pii=PIILevel.LOW,
        fhir=None,
        search=SearchBehaviour.NONE,
        display_label="Rejected by",
        description="The user who rejected the document.",
        link_to="User",
        link_cardinality="one",
    )

    rejection_reason: Optional[str] = Prop(
        default=None,
        pii=PIILevel.MEDIUM,
        fhir=None,
        search=SearchBehaviour.TOKENISED,
        display_label="Rejection reason",
        description="Free-text explanation captured at rejection time. MEDIUM "
                    "PII because the reason may include patient context.",
        max_length=2000,
    )

    # ---- Lifecycle ------------------------------------------------------

    status: DocumentStatus = Prop(
        default=DocumentStatus.UPLOADED,
        pii=PIILevel.NONE,
        fhir="status",
        search=SearchBehaviour.FACETED,
        display_label="Status",
        description="Current pipeline state. Validators enforce that the "
                    "supporting timestamps and references match the status.",
    )

    # ---- Validation -----------------------------------------------------

    @field_validator("sha256_hash", mode="before")
    @classmethod
    def _normalise_sha256(cls, v: Optional[str]) -> Optional[str]:
        """Normalise to lowercase 64-char hex; reject anything else.

        Catches whole categories of upload-pipeline bugs cheaply: callers
        passing 'sha256:<hex>', uppercase digests, hex with stray whitespace,
        or empty strings. Doing this at the write boundary means downstream
        consumers (dedup detector, FHIR export hash field) can trust the
        format without re-validating.
        """
        if v is None:
            return None
        cleaned = v.strip().lower()
        if len(cleaned) != 64:
            raise ValueError(
                f"sha256_hash must be 64 hex characters, got {len(cleaned)}."
            )
        if not all(c in "0123456789abcdef" for c in cleaned):
            raise ValueError(
                "sha256_hash must contain only hexadecimal characters [0-9a-f]."
            )
        return cleaned

    @model_validator(mode="after")
    def _check_promoted_consistency(self) -> "Document":
        """PROMOTED documents must have the full promotion provenance set.

        Without all three of (promoted_at, promoted_by_user_id,
        promoted_to_patient_id), the audit trail is incomplete and the
        platform can't answer 'who promoted what, when, into where'.
        """
        if self.status != DocumentStatus.PROMOTED:
            return self

        missing = [
            name
            for name, value in (
                ("promoted_at", self.promoted_at),
                ("promoted_by_user_id", self.promoted_by_user_id),
                ("promoted_to_patient_id", self.promoted_to_patient_id),
            )
            if value is None
        ]
        if missing:
            raise ValueError(
                "status=PROMOTED requires "
                f"{', '.join(missing)} to be set."
            )
        return self

    @model_validator(mode="after")
    def _check_rejected_consistency(self) -> "Document":
        if self.status != DocumentStatus.REJECTED:
            return self
        if self.rejected_at is None or not self.rejection_reason:
            raise ValueError(
                "status=REJECTED requires both rejected_at and rejection_reason "
                "to be set."
            )
        return self

    @model_validator(mode="after")
    def _check_parse_failed_consistency(self) -> "Document":
        if self.status != DocumentStatus.PARSE_FAILED:
            return self
        if not self.parse_error:
            raise ValueError(
                "status=PARSE_FAILED requires parse_error to be set."
            )
        if self.parse_confidence_avg is not None:
            raise ValueError(
                "status=PARSE_FAILED is incompatible with a non-null "
                "parse_confidence_avg — failure means no confidence was produced."
            )
        return self

    @model_validator(mode="after")
    def _check_lifecycle_monotonic(self) -> "Document":
        """Timestamps must respect pipeline ordering: upload ≤ parse ≤ validate ≤ promote.

        Mismatches almost always indicate a backfill bug or a clock skew issue,
        which silently corrupts audit ordering. Surface them at write time.
        """
        sequence = [
            ("uploaded_at", self.uploaded_at),
            ("parsed_at", self.parsed_at),
            ("validated_at", self.validated_at),
            ("promoted_at", self.promoted_at),
        ]
        last_name, last_ts = None, None
        for name, ts in sequence:
            if ts is None:
                continue
            if last_ts is not None and ts < last_ts:
                raise ValueError(
                    f"{name} ({ts.isoformat()}) is earlier than {last_name} "
                    f"({last_ts.isoformat()}). Pipeline timestamps must be "
                    "monotonically non-decreasing."
                )
            last_name, last_ts = name, ts
        return self

    @model_validator(mode="after")
    def _check_scan_agent_workstation(self) -> "Document":
        """A scan-agent upload without a workstation id is unattributable.

        We use it to debug 'scans from this workstation aren't arriving' tickets,
        so a missing id defeats the purpose.
        """
        if (
            self.source == DocumentSource.SCAN_AGENT
            and not self.scan_agent_workstation_id
        ):
            raise ValueError(
                "source=SCAN_AGENT requires scan_agent_workstation_id."
            )
        return self

    @model_validator(mode="after")
    def _check_parsed_requires_timestamp(self) -> "Document":
        """Any status downstream of parsing requires parsed_at to be set.

        Without it, the audit trail can't answer 'when was this parsed' for
        rows whose lifecycle has clearly moved past parsing. Surfacing the
        missing timestamp at write time prevents silently broken audit history.
        """
        post_parse_states = {
            DocumentStatus.PARSED,
            DocumentStatus.VALIDATING,
            DocumentStatus.VALIDATED,
            DocumentStatus.PROMOTED,
        }
        if self.status in post_parse_states and self.parsed_at is None:
            raise ValueError(
                f"status={self.status.value} requires parsed_at to be set."
            )
        return self

    @model_validator(mode="after")
    def _check_validated_requires_provenance(self) -> "Document":
        """VALIDATED (and any downstream state) requires both validated_at
        and validated_by_user_id.

        These are the accountable-party fields. Promoting a document whose
        validator is unknown breaks the regulatory story — surface the
        missing fields rather than letting a half-attributed row through.
        """
        post_validation_states = {
            DocumentStatus.VALIDATED,
            DocumentStatus.PROMOTED,
        }
        if self.status in post_validation_states:
            missing = [
                name
                for name, value in (
                    ("validated_at", self.validated_at),
                    ("validated_by_user_id", self.validated_by_user_id),
                )
                if value is None
            ]
            if missing:
                raise ValueError(
                    f"status={self.status.value} requires "
                    f"{', '.join(missing)} to be set."
                )
        return self

    @model_validator(mode="after")
    def _check_terminal_exclusivity(self) -> "Document":
        """PROMOTED and REJECTED are mutually exclusive terminal states.

        A document can't have both promotion provenance and rejection
        provenance set — those represent contradictory decisions about
        the same artefact. Either it became part of a patient record or
        it didn't; pick one.
        """
        has_promotion = any(
            v is not None
            for v in (
                self.promoted_at,
                self.promoted_by_user_id,
                self.promoted_to_patient_id,
            )
        )
        has_rejection = any(
            v is not None
            for v in (self.rejected_at, self.rejected_by_user_id)
        ) or bool(self.rejection_reason)
        if has_promotion and has_rejection:
            raise ValueError(
                "Document cannot have both promotion and rejection fields set "
                "— these are mutually exclusive terminal outcomes."
            )
        return self

    @model_validator(mode="after")
    def _check_no_orphan_consultation_pointer(self) -> "Document":
        """promoted_to_consultation_id only makes sense alongside a patient.

        A Consultation is always scoped to a Patient. A Document pointing at
        a consultation without also pointing at its patient is a corruption
        signal — almost certainly a partial write.
        """
        if (
            self.promoted_to_consultation_id is not None
            and self.promoted_to_patient_id is None
        ):
            raise ValueError(
                "promoted_to_consultation_id is set but promoted_to_patient_id "
                "is null — a Consultation always belongs to a Patient, so the "
                "patient pointer must be set whenever the consultation pointer is."
            )
        return self

    # ---- Convenience accessors -----------------------------------------

    def short_id(self) -> str:
        """First 8 chars of the UUID, uppercased — the form used in UI badges."""
        return str(self.id)[:8].upper()

    def display_name(self) -> str:
        """UI-friendly name. Note this overrides the class-level template,
        which still uses {id} for codegen/schema consumers that can't call
        methods. Do not "fix" the class template back to {short_id} — it
        would silently break codegen because Pydantic's model_dump() only
        exposes fields, not methods.
        """
        return f"DOC-{self.short_id()} {self.original_filename}"

    def is_terminal(self) -> bool:
        """True once the document has reached an end state."""
        return self.status in (
            DocumentStatus.PROMOTED,
            DocumentStatus.REJECTED,
            DocumentStatus.ARCHIVED,
        )

    def awaiting_validation(self) -> bool:
        """True when the document is ready for or currently being reviewed by a human."""
        return self.status in (DocumentStatus.PARSED, DocumentStatus.VALIDATING)

    def awaiting_promotion(self) -> bool:
        """True when validation is complete but promotion has not yet occurred."""
        return self.status == DocumentStatus.VALIDATED
