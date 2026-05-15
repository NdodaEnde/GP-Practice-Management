"""
clinical_actions — REST endpoints for PR 3 patient/prescription actions
that don't fit under /digitisation/*.

Four endpoints, each routes through the ActionExecutor:
  - POST /clinical/prescriptions/{prescription_id}/void
  - POST /clinical/patients/{patient_id}/soft-delete
  - POST /clinical/documents/{document_id}/reassign
  - POST /clinical/patients/merge
  - POST /clinical/audit/{audit_id}/reverse

Each handler is thin: snapshot any required previous-state, build the
Action, call execute(), translate the outcome to an HTTP status code.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.auth import get_current_user, require_capability
from app.actions import ActorContext, execute
from app.actions.executor import reverse as executor_reverse


router = APIRouter(prefix="/clinical", tags=["clinical-actions"])


# Lazy-load supabase client at first request (avoids hard-failing at
# import time if env isn't set during test collection).
_supabase = None
def _sb():
    global _supabase
    if _supabase is None:
        from supabase import create_client
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_KEY missing")
        _supabase = create_client(url, key)
    return _supabase


# ----------------------------------------------------------------------------
# Pydantic request bodies
# ----------------------------------------------------------------------------

class VoidPrescriptionRequest(BaseModel):
    void_reason: str


class SoftDeletePatientRequest(BaseModel):
    erasure_reason: str


class ReassignDocumentRequest(BaseModel):
    new_patient_id: str
    reason: str = ""


class MergePatientRequest(BaseModel):
    source_patient_id: str
    target_patient_id: str
    merge_reason: str
    confirmed_at: Optional[str] = None
    survivor_choice_evidence: str = ""


class ReverseRequest(BaseModel):
    reason: Optional[str] = None


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def _result_to_http(result):
    """Translate an ActionResult outcome to an HTTPException (if non-success)."""
    if result.outcome in ("success", "reversed", "dry_run"):
        return
    err = result.error
    code = err.code if err else None
    if code == "not_found":
        status_code = status.HTTP_404_NOT_FOUND
    elif code == "action_locked":
        status_code = status.HTTP_423_LOCKED
    elif code in ("precondition_failed", "cannot_reverse_dry_run"):
        status_code = status.HTTP_409_CONFLICT
    elif code == "permission_denied":
        status_code = status.HTTP_403_FORBIDDEN
    else:
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    raise HTTPException(
        status_code=status_code,
        detail=err.message if err else f"action outcome={result.outcome}",
    )


# ----------------------------------------------------------------------------
# Endpoints
# ----------------------------------------------------------------------------

@router.post("/prescriptions/{prescription_id}/void")
async def void_prescription(
    prescription_id: str,
    body: VoidPrescriptionRequest,
    current_user: dict = Depends(require_capability("prescription_management")),
):
    """Soft-cancel an active prescription. Audited + reversible."""
    workspace_id = current_user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="No workspace context")

    # Snapshot previous_status for the audit row.
    sb = _sb()
    snap = (
        sb.table("prescriptions").select("id, status, workspace_id")
        .eq("id", prescription_id).execute()
    )
    if not snap.data:
        raise HTTPException(status_code=404, detail="Prescription not found")

    from ontology.actions.void_prescription import VoidPrescription
    actor = ActorContext.from_user(current_user)
    action = VoidPrescription(
        prescription_id=prescription_id,
        void_reason=body.void_reason,
        actor_user_id=actor.user_id,
        actor_email=actor.email,
        practice_id=workspace_id,
        workspace_id=workspace_id,
        previous_status=snap.data[0].get("status", "active"),
    )
    result = execute(action, actor=actor, supabase=sb)
    _result_to_http(result)
    return {"status": "success", "audit_id": result.audit_id}


@router.post("/patients/{patient_id}/soft-delete")
async def soft_delete_patient(
    patient_id: str,
    body: SoftDeletePatientRequest,
    current_user: dict = Depends(require_capability("patient_admin")),
):
    """Soft-delete a patient (POPIA right-to-erasure). Blocks on active
    prescriptions or pending-validation documents. Audited + reversible."""
    workspace_id = current_user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="No workspace context")

    from ontology.actions.soft_delete_patient import SoftDeletePatient
    actor = ActorContext.from_user(current_user)
    action = SoftDeletePatient(
        patient_id=patient_id,
        erasure_reason=body.erasure_reason,
        actor_user_id=actor.user_id,
        actor_email=actor.email,
        practice_id=workspace_id,
        workspace_id=workspace_id,
    )
    result = execute(action, actor=actor, supabase=_sb())
    _result_to_http(result)
    return {"status": "success", "audit_id": result.audit_id}


@router.post("/documents/{document_id}/reassign")
async def reassign_document(
    document_id: str,
    body: ReassignDocumentRequest,
    current_user: dict = Depends(require_capability("patient_admin")),
):
    """Re-point a document and its child rows to a different patient.
    PL/pgSQL RPC-backed for atomicity + lock. Audited + reversible."""
    workspace_id = current_user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="No workspace context")

    from ontology.actions.reassign_document import ReassignDocument
    actor = ActorContext.from_user(current_user)
    action = ReassignDocument(
        document_id=document_id,
        new_patient_id=body.new_patient_id,
        reason=body.reason,
        actor_user_id=actor.user_id,
        actor_email=actor.email,
        practice_id=workspace_id,
        workspace_id=workspace_id,
    )
    result = execute(action, actor=actor, supabase=_sb())
    _result_to_http(result)
    return {"status": "success", "audit_id": result.audit_id, "affected_objects": result.affected_objects}


@router.post("/patients/merge")
async def merge_patient(
    body: MergePatientRequest,
    current_user: dict = Depends(require_capability("patient_admin")),
):
    """Consolidate two patient records. Requires fresh confirmation
    (5-minute window). Highest blast radius — PL/pgSQL RPC + locks both
    patient rows. Audited + reversible."""
    workspace_id = current_user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="No workspace context")

    from ontology.actions.merge_patient import MergePatient, MergeConfirmation
    actor = ActorContext.from_user(current_user)
    confirmed_at = datetime.now(timezone.utc)
    if body.confirmed_at:
        confirmed_at = datetime.fromisoformat(body.confirmed_at.replace("Z", "+00:00"))

    action = MergePatient(
        source_patient_id=body.source_patient_id,
        target_patient_id=body.target_patient_id,
        merge_reason=body.merge_reason,
        confirmation=MergeConfirmation(
            confirmed_by_user_id=actor.user_id,
            confirmed_at=confirmed_at,
            survivor_choice_evidence=body.survivor_choice_evidence,
        ),
        actor_user_id=actor.user_id,
        actor_email=actor.email,
        practice_id=workspace_id,
        workspace_id=workspace_id,
    )
    result = execute(action, actor=actor, supabase=_sb())
    _result_to_http(result)
    return {"status": "success", "audit_id": result.audit_id, "affected_objects": result.affected_objects}


@router.post("/audit/{audit_id}/reverse")
async def reverse_action(
    audit_id: str,
    body: Optional[ReverseRequest] = None,
    current_user: dict = Depends(get_current_user),
):
    """Universal reverse endpoint — reverse any audited mutation.

    The executor.reverse() handles dispatch to the right reverse path
    (RPC for PromoteDocument/ReassignDocument/MergePatient, Python
    Effects for RejectDocument/EditExtractionField/VoidPrescription/
    SoftDeletePatient).

    Permission check is on the original action's reversal — currently
    we accept any authenticated user; PR 4 may scope by action type."""
    actor = ActorContext.from_user(current_user)
    result = executor_reverse(
        audit_id,
        actor=actor,
        supabase=_sb(),
        reason=(body.reason if body else None),
    )
    _result_to_http(result)
    return {"status": "success", "audit_id": result.audit_id, "outcome": result.outcome}
