"""
PromoteDocumentToPatientRecord — the platform's highest-stakes mutation,
modelled as a first-class Action.

Why this action matters:

  Promoting a scanned document into a Patient's clinical record is the
  moment when extracted data becomes "true" — it stops being a candidate
  and starts being something the doctor will trust on the morning briefing.
  Get this wrong and you've put the wrong diagnosis on the wrong patient.

The Action pattern gives us four things for free that scattered endpoint
code does not:

  1. **Preconditions** declared as a list, checked uniformly before any
     mutation runs. If a precondition fails, nothing happens — no half-
     promoted record, no orphaned diagnoses.

  2. **Effects** declared as a list, executed in a transaction. The action
     either fully succeeds or fully rolls back.

  3. **Audit metadata** captured by construction. Every action invocation
     writes a row to the audit log with: what action, what parameters,
     which actor, against which objects, when, with what outcome. The
     audit feature in the UI just queries this table.

  4. **Reversal** declared alongside the forward path. Mistakes happen;
     reversibility is what makes the platform trustworthy enough for
     clinical use.

This file is illustrative — the surrounding ActionExecutor and audit
infrastructure is not included in this starter. The Action class itself
shows the shape your real implementation should take.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID

if TYPE_CHECKING:
    from ontology.objects.patient import Patient
    # from ontology.objects.document import Document    # to be added
    # from ontology.objects.consultation import Consultation  # to be added


@dataclass(frozen=True)
class PatientMatchEvidence:
    """The structured proof that a document belongs to a patient.

    Captured at the moment a human clicks 'yes, this is the right patient'
    in the validation queue. The platform refuses to promote without it.

    Fields:
        confirmed_by_user_id  — who clicked the confirm button
        confirmed_at          — timestamp of the click
        match_signals         — what evidence the system showed the human
                                ('SA ID number exact match', 'name + DOB +
                                scheme number match', 'fuzzy name match
                                with manual override')
        confidence_score      — system's pre-confirmation score [0, 1]
    """

    confirmed_by_user_id: UUID
    confirmed_at: datetime
    match_signals: tuple[str, ...]
    confidence_score: float


@dataclass
class PromoteDocumentToPatientRecord:
    """Promote a validated document's extracted data into a Patient's record.

    Usage pattern (with the executor not shown here):

        action = PromoteDocumentToPatientRecord(
            document_id=document.id,
            target_patient_id=patient.id,
            confirmation=patient_match_evidence,
            actor_user_id=current_user.id,
            practice_id=current_practice.id,
        )
        result = action_executor.execute(action)

    The executor runs preconditions(), then effects() in a transaction,
    writes the audit log, and returns a result object with the IDs of all
    newly-created clinical objects.
    """

    # ---- Action metadata (used by the executor) -------------------------

    __action_name__ = "PromoteDocumentToPatientRecord"
    __reversible__ = True
    __pii_level__ = "high"

    # ---- Parameters ----------------------------------------------------

    document_id: UUID
    target_patient_id: UUID
    confirmation: PatientMatchEvidence
    actor_user_id: UUID
    practice_id: UUID

    # Optional: if the document represents a new consultation, the actor
    # can supply a date that overrides the extracted one. Useful when the
    # extraction misread the date stamp.
    consultation_date_override: Optional[datetime] = None

    # ---- Preconditions -------------------------------------------------
    # Each precondition is a callable that raises a clear exception if it
    # fails. The executor catches these and translates them into structured
    # errors for the UI.

    def preconditions(self) -> list[str]:
        """Declarative list of what must be true before this action can run.

        Returned as strings here for illustration; the real implementation
        returns a list of callable precondition objects that the executor
        evaluates against the DB state at execution time.
        """
        return [
            "Document exists and belongs to the actor's practice.",
            "Document.validation_status == 'validated'.",
            "Document is not already promoted (document.promoted_at is None).",
            "Target Patient exists and belongs to the actor's practice.",
            "Target Patient is not soft-deleted and not merged into another.",
            "PatientMatchEvidence.confirmed_by_user_id == actor_user_id.",
            "PatientMatchEvidence.confirmed_at is within the last 15 minutes "
            "(confirmation cannot be reused or stale).",
            "Actor has the 'promote_document' permission for this practice.",
        ]

    # ---- Effects -------------------------------------------------------

    def effects(self) -> list[str]:
        """Declarative list of state changes this action causes.

        The executor runs all of these in a single transaction. If any
        step fails, the whole transaction rolls back.
        """
        return [
            "Create a Consultation linked to target_patient (from extracted data).",
            "Create Diagnosis objects for each extracted diagnosis, linked to "
            "the Consultation and coded with ICD-10.",
            "Create Medication objects for each extracted prescription, linked "
            "to the Consultation and coded with NAPPI + ATC class.",
            "Create Vitals object if vitals were extracted, linked to the "
            "Consultation.",
            "Create LabResult objects for any extracted results.",
            "Create a Document->Patient link with the PatientMatchEvidence "
            "attached.",
            "Create Document->Consultation link with extraction confidence.",
            "Mark Document.promoted_at = now, promoted_by_user_id = actor_user_id.",
            "Refresh Patient.last_consultation_at and recompute "
            "active_chronic_conditions_summary via PatientSummaryMaintainer.",
            "Open any OpenLoop objects implied by the extracted content "
            "(e.g. recommended stress test -> 'specialist-referral-pending' loop).",
            "Emit a domain event: DocumentPromoted(document_id, patient_id, ...) "
            "for downstream consumers (search indexer, FHIR exporter, "
            "morning briefing materialiser).",
            "Write audit log entry with action name, parameters, actor, "
            "affected object IDs, and outcome.",
        ]

    # ---- Reversal ------------------------------------------------------

    def reversal(self) -> list[str]:
        """How to undo this action if the doctor realises it was wrong.

        Reversal is not the same as deletion. Reversal soft-deletes the
        created objects, restores the document to its pre-promotion state,
        and writes a reversal entry to the audit log — preserving the full
        forensic trail of 'this was promoted, then unpromoted, by these
        actors at these times'.
        """
        return [
            "Soft-delete all Diagnosis, Medication, Vitals, LabResult objects "
            "created by this action (deleted_at = now).",
            "Soft-delete the Consultation created by this action.",
            "Soft-delete the Document->Patient and Document->Consultation links.",
            "Reset Document.promoted_at = None, validation_status back to "
            "'validated' (ready for re-promotion to a different patient).",
            "Close any OpenLoops opened by this action that have not since "
            "been independently confirmed.",
            "Recompute Patient.active_chronic_conditions_summary.",
            "Write audit log entry for the reversal, linked to the original "
            "action's audit row.",
        ]

    # ---- Description for the UI ----------------------------------------

    def describe_for_user(self) -> str:
        """Human-readable summary, used in the validation queue UI and the
        audit log display."""
        return (
            f"Promote document {self.document_id} to patient "
            f"{self.target_patient_id}, confirmed by user "
            f"{self.confirmation.confirmed_by_user_id} with "
            f"{len(self.confirmation.match_signals)} match signals "
            f"(confidence {self.confirmation.confidence_score:.2f})."
        )
