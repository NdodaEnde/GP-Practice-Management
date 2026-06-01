"""
Mining Gateway / Financial-Disclosure — FastAPI endpoints.

MVP surface (matches the plan at step 2g + the spec §7 API examples):

    POST   /api/fd/documents                upload a public report (PDF) and ingest
    GET    /api/fd/documents                list ingested documents in this workspace
    GET    /api/fd/documents/{doc_id}       status + ingest metrics for one document
    GET    /api/fd/needs_review             quarantine queue (low-confidence surface forms)
    POST   /api/fd/needs_review/{id}/merge  human resolves a quarantined surface form

Every route resolves the workspace via `Depends(get_current_user)` and scopes
queries by ``current_user["workspace_id"]`` — matching the existing pattern in
backend/api/*.py and backend/app/api/gp_endpoints.py.

This file is wired into server.py via one ``include_router`` line.
"""

from __future__ import annotations

import hashlib
import logging
import os
import tempfile
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from app.api.auth import get_current_user
from app.services.fd_ontology_mapper import IngestError
from app.services.fd_processor import FDDocumentProcessor

logger = logging.getLogger(__name__)


# No internal prefix — the platform's api_router has prefix="/api" and this
# router is included with prefix="/fd" by server.py. The URLs above are the
# composition.
router = APIRouter(tags=["Mining / Financial-Disclosure"])


# =============================================================================
# Supabase client accessor — mirrors gp_endpoints._get_supabase().
# =============================================================================


def _get_supabase():
    """Pull the configured Supabase client from server module."""
    try:
        import server  # type: ignore  # late import to avoid cycles at startup
        return getattr(server, "supabase", None)
    except ImportError:
        return None


def _require_supabase():
    sb = _get_supabase()
    if sb is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase client not initialised",
        )
    return sb


def _require_workspace(current_user: Dict[str, Any]) -> str:
    workspace_id = current_user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No workspace bound to the active session",
        )
    return workspace_id


# =============================================================================
# Health
# =============================================================================


@router.get("/health")
async def fd_health_check():
    """Module-level health: confirms FDDocumentProcessor + Supabase + ADE env are wired up."""
    processor_status = "unavailable"
    try:
        # Don't instantiate (it would need ADE creds); just confirm import.
        from app.services.fd_processor import FDDocumentProcessor as _FDP  # noqa: F401
        processor_status = "importable"
    except Exception as exc:
        processor_status = f"import_error: {exc}"

    db_status = "unchecked"
    sb = _get_supabase()
    if sb is not None:
        try:
            sb.table("fd_entity_registry").select("id", count="exact").limit(1).execute()
            db_status = "connected"
        except Exception as exc:
            db_status = f"error: {exc}"

    ade_status = (
        "configured"
        if (os.environ.get("VISION_AGENT_API_KEY") or os.environ.get("LANDING_AI_API_KEY"))
        else "missing_api_key"
    )

    return {"module": "fd", "processor": processor_status, "supabase": db_status, "ade": ade_status}


# =============================================================================
# Documents
# =============================================================================


class IngestSummary(BaseModel):
    """Response shape for POST /documents."""

    success: bool
    doc_id: str
    elapsed_seconds: Optional[float] = None
    entity_resolution_confidence: Optional[float] = None
    nodes_written: Dict[str, int] = Field(default_factory=dict)
    edges_written: Dict[str, int] = Field(default_factory=dict)
    quarantined: int = 0
    rejected: List[str] = Field(default_factory=list)


@router.post(
    "/documents",
    response_model=IngestSummary,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_document(
    file: UploadFile = File(..., description="Public Exxaro report PDF"),
    doc_id: str = Form(..., description="Stable identifier, e.g. 'EXXARO-IR-2024'"),
    doc_type: str = Form(..., description="'integrated' | 'sustainability' | 'investor'"),
    fiscal_year: int = Form(..., description="4-digit fiscal year, e.g. 2024"),
    title: str = Form(..., description="Report title, e.g. 'Integrated Report 2024'"),
    current_user: dict = Depends(get_current_user),
):
    """
    Upload one Exxaro report. Synchronously runs the ingest pipeline:
    LandingAI parse → extract → entity resolution → ontology mapping → write.

    Idempotent on (workspace_id, doc_id): re-uploading the same report is a
    no-op against everything except fd_documents (the latency / confidence
    fields refresh).

    Returns the IngestSummary directly. For very long ingests a future
    revision will queue the work and return a job_id; the MVP keeps it
    synchronous to match the §7.5 demo's single-request flow.
    """
    if doc_type not in ("integrated", "sustainability", "investor"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"doc_type must be one of integrated/sustainability/investor (got {doc_type!r})",
        )
    if not (1990 <= fiscal_year <= 2100):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"fiscal_year out of expected range (got {fiscal_year})",
        )

    workspace_id = _require_workspace(current_user)
    supabase = _require_supabase()

    # Read once, hash, then stream-write to tempfile so LandingAI can read it.
    payload = await file.read()
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )
    sha256 = hashlib.sha256(payload).hexdigest()

    suffix = os.path.splitext(file.filename or "")[1].lower() or ".pdf"
    tmp = tempfile.NamedTemporaryFile(prefix=f"fd-{doc_id}-", suffix=suffix, delete=False)
    try:
        tmp.write(payload)
        tmp.flush()
        tmp.close()

        storage_path = f"fd/{workspace_id}/{doc_id}{suffix}"

        processor = FDDocumentProcessor(supabase_client=supabase)
        try:
            result = await processor.process_document(
                workspace_id=workspace_id,
                file_path=tmp.name,
                doc_id=doc_id,
                doc_type=doc_type,
                fiscal_year=fiscal_year,
                title=title,
                storage_path=storage_path,
                sha256=sha256,
            )
        except IngestError as ie:
            # Honesty-rule rejections: surface them to the caller as 422 so the
            # UI can render the message verbatim. Status of fd_documents was
            # already set to 'failed' by the processor's except branch.
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(ie),
            )
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass

    return IngestSummary(**result)


@router.get("/documents")
async def list_documents(
    fiscal_year: Optional[int] = None,
    doc_type: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """List all documents ingested into this workspace, newest first."""
    workspace_id = _require_workspace(current_user)
    supabase = _require_supabase()

    q = (
        supabase.table("fd_documents")
        .select(
            "doc_id,doc_type,fiscal_year,title,ingest_status,"
            "extraction_latency_seconds,entity_resolution_confidence,created_at"
        )
        .eq("workspace_id", workspace_id)
    )
    if fiscal_year is not None:
        q = q.eq("fiscal_year", fiscal_year)
    if doc_type is not None:
        q = q.eq("doc_type", doc_type)
    resp = q.order("created_at", desc=True).execute()
    return {"documents": getattr(resp, "data", None) or []}


@router.get("/documents/{doc_id}")
async def get_document_status(
    doc_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Status + metrics for one document."""
    workspace_id = _require_workspace(current_user)
    supabase = _require_supabase()

    resp = (
        supabase.table("fd_documents")
        .select("*")
        .eq("workspace_id", workspace_id)
        .eq("doc_id", doc_id)
        .limit(1)
        .execute()
    )
    rows = getattr(resp, "data", None) or []
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"doc_id={doc_id!r} not found")
    return rows[0]


# =============================================================================
# Needs-review queue (spec §4.2 quarantine)
# =============================================================================


@router.get("/needs_review")
async def list_needs_review(
    resolved: Optional[bool] = False,
    current_user: dict = Depends(get_current_user),
):
    """List quarantined surface forms (low-confidence resolves)."""
    workspace_id = _require_workspace(current_user)
    supabase = _require_supabase()
    q = (
        supabase.table("fd_facts_needs_review")
        .select("id,raw_surface_form,best_match_canonical_id,surface_form_confidence,ade_output,doc_id,page,resolved,resolved_canonical_id,created_at")
        .eq("workspace_id", workspace_id)
    )
    if resolved is not None:
        q = q.eq("resolved", resolved)
    resp = q.order("created_at", desc=True).execute()
    return {"items": getattr(resp, "data", None) or []}


class MergeBody(BaseModel):
    canonical_id: str = Field(..., description="The canonical_id this surface form maps to.")
    add_to_registry: bool = Field(
        True,
        description=(
            "If True (default), append the raw_surface_form to the registry "
            "entry's surface_forms array so future ADE outputs resolve cleanly. "
            "If False, mark the quarantine row resolved without updating the "
            "registry — useful when the form was a one-off typo."
        ),
    )


@router.post("/needs_review/{review_id}/merge")
async def merge_needs_review(
    review_id: str,
    body: MergeBody,
    current_user: dict = Depends(get_current_user),
):
    """
    Resolve a quarantined surface form by binding it to a canonical_id.
    Optionally adds the raw form to the registry's surface_forms[] so future
    extractions resolve confidently.

    This endpoint does NOT retroactively create the node/edge that was
    quarantined — re-upload the source document to trigger the mapping with
    the now-confident resolve.
    """
    workspace_id = _require_workspace(current_user)
    supabase = _require_supabase()

    review = (
        supabase.table("fd_facts_needs_review")
        .select("*")
        .eq("workspace_id", workspace_id)
        .eq("id", review_id)
        .limit(1)
        .execute()
    )
    rows = getattr(review, "data", None) or []
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="needs_review row not found")
    item = rows[0]
    if item.get("resolved"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="already resolved")

    # 1. Confirm the canonical_id exists in this workspace's registry.
    reg = (
        supabase.table("fd_entity_registry")
        .select("id,surface_forms")
        .eq("workspace_id", workspace_id)
        .eq("canonical_id", body.canonical_id)
        .limit(1)
        .execute()
    )
    reg_rows = getattr(reg, "data", None) or []
    if not reg_rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"canonical_id={body.canonical_id!r} not found in registry for this workspace",
        )
    reg_row = reg_rows[0]

    # 2. Optionally extend the registry.
    if body.add_to_registry:
        existing = reg_row.get("surface_forms") or []
        if item["raw_surface_form"] not in existing:
            new_forms = list(existing) + [item["raw_surface_form"]]
            supabase.table("fd_entity_registry").update(
                {"surface_forms": new_forms}
            ).eq("id", reg_row["id"]).execute()

    # 3. Mark the quarantine row resolved.
    supabase.table("fd_facts_needs_review").update(
        {
            "resolved": True,
            "resolved_canonical_id": body.canonical_id,
            "resolved_by": current_user.get("email") or current_user.get("user_id"),
            "resolved_at": "now()",
        }
    ).eq("id", review_id).execute()

    return {
        "success": True,
        "review_id": review_id,
        "resolved_canonical_id": body.canonical_id,
        "registry_updated": body.add_to_registry,
    }
