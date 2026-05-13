"""
PromoteDocumentToPatientRecord — the platform's highest-stakes mutation,
modelled as a first-class Action.

Why this action matters
-----------------------

Promoting a scanned document into a Patient's clinical record is the
moment when extracted data becomes "true" — it stops being a candidate
and starts being something the doctor will trust on the morning briefing.
Get this wrong and you've put the wrong diagnosis on the wrong patient.

The Action pattern (PR 1) gives us four things scattered endpoint code
does not:

  1. **Preconditions** declared as a list, checked uniformly before any
     mutation runs. If a precondition fails, nothing happens.

  2. **Effects** declared as a list, recorded into the audit row.
     PR 1: effects apply via app-level Python calls (no multi-statement
     ACID — same fragility as the previous endpoint, no worse).
     PR 2: effects swap to a PL/pgSQL RPC for real atomicity. The Action
     declaration doesn't change.

  3. **Audit metadata** captured by construction. Every invocation writes
     a row to action_audit_log with: action name, parameters, actor,
     affected objects, outcome. The Phase 4 audit-trail UI just queries
     this table.

  4. **Reversal** declared alongside the forward path. PR 1 ships the
     declaration + the audit row's column reservations; PR 2 ships the
     functional reversal.

Implementation choice — PR 1 wraps the existing promoter
--------------------------------------------------------

PromoteExtractionsViaPromoter (in app.actions.primitives) is a single
Effect that wraps the existing `promote_extractions()` service. The
heavy lifting (ICD-10 lookups, NAPPI lookups, patient match/create,
encounter creation, etc.) stays in `app.services.extraction_promoter`
for PR 1. PR 2 ports it to PL/pgSQL; the Action declaration stays
identical.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.actions.base import Action, CheckResult, ExecutorContext, Precondition, Effect
from app.actions.primitives import (
    BelongsToPractice,
    ConfirmationFresh,
    HasPermission,
    HasStatus,
    NotSoftDeleted,
    ObjectExists,
    PromoteExtractionsViaPromoter,
    ReverseDocumentPromotionViaRpc,
)
from app.actions.registry import register_action


# ---------------------------------------------------------------------------
# PatientMatchEvidence — the structured proof of patient identity
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PatientMatchEvidence:
    """The structured proof that a document belongs to a patient.

    Captured at the moment a human clicks 'yes, this is the right patient'
    in the validation queue. The action's ConfirmationFresh precondition
    rejects evidence older than 15 minutes — clicks can't be replayed
    from yesterday.

    Fields:
        confirmed_by_user_id  — who clicked confirm
        confirmed_at          — timestamp of the click
        match_signals         — what evidence the system showed the human
                                (e.g. 'SA ID exact match', 'name + DOB',
                                'manual override')
        confidence_score      — system's pre-confirmation score [0, 1]
    """
    confirmed_by_user_id: str
    confirmed_at: datetime
    match_signals: List[str] = field(default_factory=list)
    confidence_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "confirmed_by_user_id": self.confirmed_by_user_id,
            "confirmed_at": self.confirmed_at.isoformat() if self.confirmed_at else None,
            "match_signals": list(self.match_signals),
            "confidence_score": self.confidence_score,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PatientMatchEvidence":
        confirmed_at_raw = d.get("confirmed_at")
        confirmed_at = (
            datetime.fromisoformat(confirmed_at_raw.replace("Z", "+00:00"))
            if confirmed_at_raw else datetime.now(timezone.utc)
        )
        return cls(
            confirmed_by_user_id=d["confirmed_by_user_id"],
            confirmed_at=confirmed_at,
            match_signals=list(d.get("match_signals") or []),
            confidence_score=float(d.get("confidence_score", 0.0)),
        )


# ---------------------------------------------------------------------------
# Custom precondition — confirmation actor must match action actor
# ---------------------------------------------------------------------------

@dataclass
class _ConfirmationActorMatches:
    """Verify the user who clicked 'confirm match' is the same user who
    invoked the action. This is the anti-replay defense: a confirmation
    from user A cannot be reused by user B to promote into a different
    patient.
    """
    confirmation_user_id: str
    actor_user_id: str
    name: str = "ConfirmationActorMatches"

    def check(self, ctx: ExecutorContext) -> CheckResult:
        passed = self.confirmation_user_id == self.actor_user_id
        return CheckResult(
            name=self.name,
            passed=passed,
            detail=None if passed else (
                f"confirmation was made by {self.confirmation_user_id!r}, "
                f"but action actor is {self.actor_user_id!r}"
            ),
        )


# ---------------------------------------------------------------------------
# PromoteDocumentToPatientRecord
# ---------------------------------------------------------------------------

@register_action
@dataclass(eq=False)
class PromoteDocumentToPatientRecord(Action):
    """Promote a validated document's extracted data into a Patient's record.

    Usage:
        action = PromoteDocumentToPatientRecord(
            document_id=document_id,
            target_patient_id=patient_id,
            confirmation=patient_match_evidence,
            actor_user_id=current_user["id"],
            practice_id=workspace_id,
            workspace_id=workspace_id,
            extractions=extraction_jsonb,
        )
        result = execute(action, actor=ActorContext.from_user(current_user),
                         supabase=supabase)
    """

    __action_name__: str = "PromoteDocumentToPatientRecord"
    __action_version__: int = 1
    __reversible__: bool = True   # functional reversal lands in PR 2
    __pii_level__: str = "high"

    # ---- Parameters ----------------------------------------------------

    document_id: str = ""
    target_patient_id: str = ""
    confirmation: Optional[PatientMatchEvidence] = None
    actor_user_id: str = ""
    practice_id: str = ""
    workspace_id: str = ""

    # The extracted JSONB the executor passes through to the promoter.
    # NOT serialised into the audit row (would bloat it 10-100KB per
    # promotion); PR 2 reversal re-fetches from the source document.
    extractions: Dict[str, Any] = field(default_factory=dict)

    # Optional overrides surfaced by the validation UI
    forced_patient_id: Optional[str] = None
    force_create_patient: bool = False
    consultation_date_override: Optional[datetime] = None

    # ---- Preconditions -------------------------------------------------

    def preconditions(self) -> List[Precondition]:
        """Checks run uniformly before any effect.apply().

        Note: "document not already promoted" is deliberately omitted in
        PR 1. The existing extraction_promoter uses a wipe-and-rewrite
        idempotency model (re-promotion is supported by design). The
        precondition would be a behaviour change; capturing it as a
        future hardening once the wipe-and-rewrite semantics are revisited.
        """
        return [
            # Document side
            ObjectExists("digitised_documents", self.document_id),
            BelongsToPractice("digitised_documents", self.document_id, self.workspace_id),
            HasStatus(
                "digitised_documents", self.document_id,
                expected_status="validated",
                column="status",
            ),

            # Target patient side
            # NB: NotSoftDeleted("patients", ...) is NOT included because
            # the patients table doesn't have a deleted_at column in
            # setup_supabase.sql. When the schema migrates to support
            # soft-deletion (future cleanup), add the precondition back.
            ObjectExists("patients", self.target_patient_id),
            BelongsToPractice("patients", self.target_patient_id, self.workspace_id),

            # Confirmation provenance
            _ConfirmationActorMatches(
                confirmation_user_id=(
                    self.confirmation.confirmed_by_user_id if self.confirmation else ""
                ),
                actor_user_id=self.actor_user_id,
            ),
            ConfirmationFresh(
                confirmed_at=(
                    self.confirmation.confirmed_at if self.confirmation
                    else datetime.now(timezone.utc)
                ),
                # Default 15-minute window
            ),

            # Actor permission
            HasPermission("digitisation_validation"),
        ]

    # ---- Effects -------------------------------------------------------

    def effects(self) -> List[Effect]:
        """The single effect for PR 1: wrap the existing promoter.

        The PromoteExtractionsViaPromoter primitive:
          - plan(ctx) — returns a descriptor counting diagnoses/medications
            etc. from the extraction JSONB.
          - apply(ctx) — calls promote_extractions() from
            app.services.extraction_promoter, records affected objects.

        PR 2 swaps this Effect's apply() to call a PL/pgSQL RPC for true
        ACID. The Action declaration doesn't change.
        """
        return [
            PromoteExtractionsViaPromoter(
                document_id=self.document_id,
                workspace_id=self.workspace_id,
                extractions=self.extractions,
                actor_email=None,  # filled from actor in executor; for now use audit
                forced_patient_id=self.forced_patient_id,
                force_create_patient=self.force_create_patient,
            ),
        ]

    # ---- Reversal (PR 2) -----------------------------------------------

    def reversal(self) -> List[Effect]:
        """Effects describing the reversal pathway.

        PR 2: returns a single ReverseDocumentPromotionViaRpc Effect.
        The audit_id and actor_user_id placeholders are populated by
        executor.reverse() at reverse-time — they are not known at
        action-construction-time and the reverse pathway does not
        round-trip through .effects().

        This method is primarily informational for UIs and audit-trail
        rendering ("what would reversing this look like?"). The
        load-bearing path is executor.reverse(audit_id) which builds
        and applies the Effect directly.
        """
        return [
            ReverseDocumentPromotionViaRpc(
                audit_id="<populated-at-reverse>",
                actor_user_id="<populated-at-reverse>",
            ),
        ]

    # ---- Description ---------------------------------------------------

    def describe_for_user(self) -> str:
        nsignals = len(self.confirmation.match_signals) if self.confirmation else 0
        score = self.confirmation.confidence_score if self.confirmation else 0.0
        return (
            f"Promote document {self.document_id} to patient "
            f"{self.target_patient_id}, confirmed by user "
            f"{self.actor_user_id} with {nsignals} match signals "
            f"(confidence {score:.2f})."
        )

    # ---- Audit parameter serialisation ---------------------------------

    def to_audit_parameters(self) -> Dict[str, Any]:
        """JSON-encodable snapshot for the audit row.

        DELIBERATELY does NOT include `extractions` — that JSONB is
        typically 10-100KB and would bloat audit log size. PR 2 reversal
        re-fetches from the source document.
        """
        return {
            "document_id":               self.document_id,
            "target_patient_id":         self.target_patient_id,
            "confirmation":              (
                self.confirmation.to_dict() if self.confirmation else None
            ),
            "actor_user_id":             self.actor_user_id,
            "practice_id":               self.practice_id,
            "workspace_id":              self.workspace_id,
            "forced_patient_id":         self.forced_patient_id,
            "force_create_patient":      self.force_create_patient,
            "consultation_date_override": (
                self.consultation_date_override.isoformat()
                if self.consultation_date_override else None
            ),
        }

    @classmethod
    def from_audit_parameters(cls, params: Dict[str, Any]) -> "PromoteDocumentToPatientRecord":
        """Reconstruct from an audit row's `parameters` JSONB.

        Used by reversal (PR 2). Re-fetches `extractions` from the source
        document if needed — not yet implemented.
        """
        confirmation = (
            PatientMatchEvidence.from_dict(params["confirmation"])
            if params.get("confirmation") else None
        )
        consultation_date_override_raw = params.get("consultation_date_override")
        consultation_date_override = (
            datetime.fromisoformat(consultation_date_override_raw.replace("Z", "+00:00"))
            if consultation_date_override_raw else None
        )
        return cls(
            document_id=params["document_id"],
            target_patient_id=params["target_patient_id"],
            confirmation=confirmation,
            actor_user_id=params["actor_user_id"],
            practice_id=params["practice_id"],
            workspace_id=params["workspace_id"],
            forced_patient_id=params.get("forced_patient_id"),
            force_create_patient=bool(params.get("force_create_patient", False)),
            consultation_date_override=consultation_date_override,
            # extractions deliberately not reconstructable from audit params; PR 2
            extractions={},
        )
