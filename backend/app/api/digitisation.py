"""
Digitisation API — Type C entry point.

Read-only endpoints that power the Type C "Digitisation Workspace" pages
(/digitisation, /digitisation/documents, /digitisation/validation, etc.).
All endpoints require the `digitisation_upload` capability — provisioned by
purchase of `module_digitisation` — and are workspace-scoped.

Upload / parse / extract / validate operations continue to live in server.py
under /api/documents/* and /api/validation/*. Phase B layer adds capability
gating and an industry-aware schema registry on top.
"""

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Body, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from supabase import create_client

from app.api.auth import get_current_user, require_capability
from app.services.schema_registry import (
    list_doc_types,
    list_industries,
    normalise_industry,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/digitisation", tags=["Digitisation"])

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _workspace_industry(workspace_id: str) -> str:
    """
    Look up the industry_type for a workspace. Defaults to 'healthcare' when
    the column is missing or NULL — keeps existing healthcare workspaces working
    until the multi-industry column lands.
    """
    if not workspace_id:
        return "healthcare"
    try:
        # Try the multi-industry column first; fall back if it doesn't exist yet.
        result = (
            supabase.table("workspaces")
            .select("industry_type, type")
            .eq("id", workspace_id)
            .execute()
        )
        if result.data:
            row = result.data[0]
            industry = row.get("industry_type") or row.get("type")
            return normalise_industry(industry)
    except Exception as e:
        logger.warning(f"Failed to fetch workspace industry for {workspace_id}: {e}")
    return "healthcare"


# ---------------------------------------------------------------------------
# Industry & schema catalogue
# ---------------------------------------------------------------------------

@router.get("/industries")
async def list_industries_endpoint(
    current_user: dict = Depends(require_capability("digitisation_upload")),
):
    """List the industries the platform supports (admin schema-picker UI)."""
    return {"industries": list_industries()}


@router.get("/doc-types")
async def doc_types_for_workspace(
    industry_type: Optional[str] = Query(None, description="Override the workspace's industry. Optional."),
    current_user: dict = Depends(require_capability("digitisation_upload")),
):
    """
    List document types available for the active workspace's industry. The
    Documents Pipeline screen renders these as filter chips.
    """
    industry = industry_type or _workspace_industry(current_user.get("workspace_id"))
    return {
        "industry_type": industry,
        "doc_types": list_doc_types(industry),
    }


# ---------------------------------------------------------------------------
# Type C Dashboard summary
# ---------------------------------------------------------------------------

@router.get("/dashboard")
async def dashboard_summary(
    current_user: dict = Depends(require_capability("digitisation_upload")),
):
    """
    Compact summary used by the Type C dashboard widgets:
      - page credits: used / total this month
      - awaiting validation: count + how many high-confidence
      - recent activity: latest 4 batches
      - quick stats: total digitised, this-month, validation accuracy

    Page-credit numbers are placeholder until Phase 4 (page_credit_grants) lands.
    Other counts come from the live digitised_documents table.
    """
    workspace_id = current_user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No workspace context")

    industry = _workspace_industry(workspace_id)

    docs_resp = (
        supabase.table("digitised_documents")
        .select("id, filename, status, created_at")
        .eq("workspace_id", workspace_id)
        .order("created_at", desc=True)
        .limit(200)
        .execute()
    )
    docs: List[Dict[str, Any]] = docs_resp.data or []

    # Counts by status — high-confidence count is a placeholder until the
    # extraction pipeline starts persisting per-document confidence scores.
    # `extracted` is the LandingAI post-extract / pre-validation state and
    # belongs in awaiting_total alongside `parsed` / `pending_validation`.
    awaiting_total = 0
    validated = 0
    rejected = 0
    for d in docs:
        s = (d.get("status") or "").lower()
        if s in ("extracted", "parsed", "pending_validation"):
            awaiting_total += 1
        elif s in ("validated", "approved"):
            validated += 1
        elif s == "rejected":
            rejected += 1
    awaiting_high_conf = 0

    # Recent activity: latest 4 individual documents (no batch grouping yet).
    recent: List[Dict[str, Any]] = [
        {
            "name":        d.get("filename") or d["id"],
            "status":      (d.get("status") or "uploaded").upper(),
            "document_id": d["id"],
        }
        for d in docs[:4]
    ]

    total_digitised = validated
    avg_conf = None  # placeholder — wire to real confidence scores in Phase B+

    # Page credits: placeholder until page_credit_grants migration runs
    credits_total = 1500
    credits_used = min(total_digitised, credits_total)

    return {
        "industry_type": industry,
        "page_credits": {
            "used":    credits_used,
            "total":   credits_total,
            "percent": round((credits_used / credits_total) * 100) if credits_total else 0,
        },
        "awaiting_validation": {
            "total":           awaiting_total,
            "high_confidence": awaiting_high_conf,
        },
        "recent_activity":     recent,
        "quick_stats": {
            "total_digitised":     total_digitised,
            "this_month":          total_digitised,  # placeholder until we filter on month
            "validation_accuracy": avg_conf,
        },
    }


# ---------------------------------------------------------------------------
# Document list (Documents Pipeline + Archive)
# ---------------------------------------------------------------------------

@router.get("/validation/queue")
async def validation_queue(
    limit: int = Query(100, ge=1, le=500),
    current_user: dict = Depends(require_capability("digitisation_validation")),
):
    """
    Documents waiting for human validation in the active workspace. Returns
    queue + stats so the queue page can render counters without a second
    round-trip. Workspace-scoped; capability-gated.

    NOTE: declared BEFORE /validation/{document_id} so FastAPI doesn't match
    "queue" as a document_id.
    """
    workspace_id = current_user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No workspace context")

    industry = _workspace_industry(workspace_id)

    # Pull a wider window than `limit` so stats reflect everything in the
    # workspace, not just what's on the queue.
    all_resp = (
        supabase.table("digitised_documents")
        .select("id, filename, file_size, file_path, status, doc_type, created_at, upload_date, pages_count, source, parsed_doc_id, validated_at, validated_by, error_message")
        .eq("workspace_id", workspace_id)
        .order("upload_date", desc=True)
        .limit(500)
        .execute()
    )
    all_docs: List[Dict[str, Any]] = all_resp.data or []

    queue_statuses = {"parsed", "pending_validation", "extracted"}
    queue: List[Dict[str, Any]] = [d for d in all_docs if (d.get("status") or "").lower() in queue_statuses][:limit]

    stats = {
        "parsed":     sum(1 for d in all_docs if (d.get("status") or "").lower() == "parsed"),
        "pending":    sum(1 for d in all_docs if (d.get("status") or "").lower() in ("pending_validation", "extracted")),
        "validated":  sum(1 for d in all_docs if (d.get("status") or "").lower() in ("validated", "approved")),
        "rejected":   sum(1 for d in all_docs if (d.get("status") or "").lower() == "rejected"),
        "total":      len(all_docs),
    }

    return {
        "industry_type": industry,
        "queue":         queue,
        "stats":         stats,
    }


@router.get("/validation/{document_id}")
async def validation_detail(
    document_id: str,
    current_user: dict = Depends(require_capability("digitisation_validation")),
):
    """
    Full validation payload for a single document — metadata + parsed chunks
    + extracted fields + signed PDF URL. Workspace-scoped; capability-gated.
    """
    workspace_id = current_user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No workspace context")

    # 1. Document metadata + workspace tenancy check
    doc_resp = (
        supabase.table("digitised_documents")
        .select("*")
        .eq("id", document_id)
        .eq("workspace_id", workspace_id)
        .execute()
    )
    if not doc_resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    doc = doc_resp.data[0]

    # 2. Signed PDF URL (1-hour expiry; the frontend re-fetches on mount).
    pdf_url = None
    file_path = doc.get("file_path")
    if file_path:
        try:
            signed = supabase.storage.from_("medical-records").create_signed_url(
                path=file_path,
                expires_in=3600,
            )
            pdf_url = signed.get("signedURL") or signed.get("signed_url")
        except Exception as e:
            logger.warning(f"Failed to sign PDF URL for {document_id}: {e}")

    # 3. Chunks come from gp_parsed_documents.parsed_data.chunks
    chunks: List[Dict[str, Any]] = []
    parsed_doc_id = doc.get("parsed_doc_id") or doc.get("gp_parsed_doc_id")
    if parsed_doc_id:
        try:
            parsed_resp = (
                supabase.table("gp_parsed_documents")
                .select("parsed_data, document_id")
                .or_(f"id.eq.{parsed_doc_id},document_id.eq.{document_id}")
                .limit(1)
                .execute()
            )
            if parsed_resp.data:
                pd = parsed_resp.data[0].get("parsed_data") or {}
                chunks = pd.get("chunks") or []
        except Exception as e:
            logger.warning(f"Failed to fetch parsed doc {parsed_doc_id}: {e}")

    # 4. Extractions + LandingAI per-field grounding metadata.
    extractions: Dict[str, Any]            = {}
    extraction_metadata: Dict[str, Any]    = {}
    confidence_scores: Dict[str, Any]      = {}
    try:
        vs_resp = (
            supabase.table("gp_validation_sessions")
            .select("extractions, confidence_scores, extraction_metadata, created_at")
            .eq("document_id", document_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if vs_resp.data:
            row = vs_resp.data[0]
            extractions      = row.get("extractions") or {}
            confidence_scores = row.get("confidence_scores") or {}
            # Prefer the dedicated column (post-migration 004); fall back to the
            # nested location used while the column was being added.
            extraction_metadata = (
                row.get("extraction_metadata")
                or confidence_scores.pop("_extraction_metadata", None)
                or {}
            )
    except Exception as e:
        # If the SELECT itself fails because the column doesn't exist yet, retry without it.
        if "extraction_metadata" in str(e).lower():
            try:
                vs_resp = (
                    supabase.table("gp_validation_sessions")
                    .select("extractions, confidence_scores, created_at")
                    .eq("document_id", document_id)
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )
                if vs_resp.data:
                    row = vs_resp.data[0]
                    extractions = row.get("extractions") or {}
                    confidence_scores = row.get("confidence_scores") or {}
                    extraction_metadata = confidence_scores.pop("_extraction_metadata", None) or {}
            except Exception as e2:
                logger.warning(f"Failed to fetch validation session for {document_id}: {e2}")
        else:
            logger.warning(f"Failed to fetch validation session for {document_id}: {e}")

    return {
        "document":            doc,
        "pdf_url":             pdf_url,
        "chunks":              chunks,
        "extractions":         extractions,
        "extraction_metadata": extraction_metadata,    # per-field {value, references} from LandingAI
        "confidence_scores":   confidence_scores,      # section-level rollup (legacy)
    }


# ---------------------------------------------------------------------------
# ICD-10 lookup — backed by the SA-edition icd10_codes table (41,008 rows).
# ---------------------------------------------------------------------------

@router.get("/icd10/validate")
async def icd10_validate(
    code: str = Query(..., description="ICD-10 code to validate, e.g. 'I10' or 'E11.9'"),
    current_user: dict = Depends(require_capability("digitisation_validation")),
):
    """
    Validate a single ICD-10 code against the SA-edition reference table.
    Returns the shape the EHR validation panel expects:

      { valid, hipaa_valid, description, code_3char_desc, group_desc, chapter_desc, age_range, gender }

    `valid` = the code exists in the SA reference table.
    `hipaa_valid` = the code is precise enough for billing/clinical use
                   (icd10_codes.valid_clinical_use is True).
    """
    code_norm = (code or "").strip().upper()
    if not code_norm:
        return {"valid": False, "hipaa_valid": False, "code": code, "description": ""}

    try:
        res = (
            supabase.table("icd10_codes")
            .select("code, code_3char, code_3char_desc, group_desc, chapter_desc, who_full_desc, valid_clinical_use, valid_primary, age_range, gender")
            .eq("code", code_norm)
            .limit(1)
            .execute()
        )
    except Exception as e:
        logger.error(f"ICD-10 validate failed for {code_norm}: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="ICD-10 lookup failed")

    if res.data:
        row = res.data[0]
        return {
            "valid":           True,
            "hipaa_valid":     bool(row.get("valid_clinical_use")),
            "valid_primary":   bool(row.get("valid_primary")),
            "code":            row.get("code"),
            "description":     row.get("who_full_desc") or row.get("code_3char_desc"),
            "group_desc":      row.get("group_desc"),
            "chapter_desc":    row.get("chapter_desc"),
            "code_3char":      row.get("code_3char"),
            "code_3char_desc": row.get("code_3char_desc"),
            "age_range":       row.get("age_range"),
            "gender":          row.get("gender"),
        }

    # Not exact — try 3-char parent so we can hint the user toward a more specific code.
    parent_code = code_norm.split(".")[0][:3]
    try:
        parent = (
            supabase.table("icd10_codes")
            .select("code, code_3char, code_3char_desc, group_desc, chapter_desc")
            .eq("code", parent_code)
            .limit(1)
            .execute()
        )
    except Exception:
        parent = None

    if parent and parent.data:
        row = parent.data[0]
        return {
            "valid":           False,    # exact code not found
            "hipaa_valid":     False,
            "code":            code,
            "description":     f"Not found. Parent {parent_code} = {row.get('code_3char_desc')}",
            "parent_code":     parent_code,
            "code_3char_desc": row.get("code_3char_desc"),
            "group_desc":      row.get("group_desc"),
            "chapter_desc":    row.get("chapter_desc"),
        }

    return {"valid": False, "hipaa_valid": False, "code": code, "description": "Not found in SA ICD-10 reference"}


@router.get("/icd10/search")
async def icd10_search(
    q: str = Query(..., min_length=2, description="Free-text search across description / chapter"),
    limit: int = Query(20, ge=1, le=100),
    only_billable: bool = Query(True, description="Restrict to codes valid for clinical/billing use."),
    current_user: dict = Depends(require_capability("digitisation_validation")),
):
    """
    Free-text ICD-10 search. Used by the validation panel when a clinician
    needs to replace an extracted code with the right one. Searches the
    `who_full_desc`, `code_3char_desc`, and `group_desc` columns.
    """
    qstr = (q or "").strip()
    if len(qstr) < 2:
        return {"results": []}

    # Tokenise — every whitespace-separated word must appear somewhere in
    # the description. AND across tokens, OR across columns per token.
    tokens = [t for t in qstr.split() if t]
    try:
        query = (
            supabase.table("icd10_codes")
            .select("code, code_3char, code_3char_desc, group_desc, chapter_desc, who_full_desc, valid_clinical_use")
        )
        for token in tokens:
            pattern = f"%{token}%"
            query = query.or_(f"who_full_desc.ilike.{pattern},code_3char_desc.ilike.{pattern},group_desc.ilike.{pattern},code.ilike.{token.upper()}%")
        query = query.limit(limit)
        if only_billable:
            query = query.eq("valid_clinical_use", True)
        res = query.execute()
    except Exception as e:
        logger.error(f"ICD-10 search failed for {qstr!r}: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="ICD-10 search failed")

    results: List[Dict[str, Any]] = []
    for row in res.data or []:
        results.append({
            "code":            row.get("code"),
            "description":     row.get("who_full_desc") or row.get("code_3char_desc"),
            "code_3char_desc": row.get("code_3char_desc"),
            "group_desc":      row.get("group_desc"),
            "chapter_desc":    row.get("chapter_desc"),
            "hipaa_valid":     bool(row.get("valid_clinical_use")),
        })
    return {"query": qstr, "count": len(results), "results": results}


# ---------------------------------------------------------------------------
# NAPPI lookup — backed by the SA nappi_codes table (1,637 rows).
# ---------------------------------------------------------------------------

def _strip_drug_modifiers(name: str) -> str:
    """
    Strip noise tokens that shouldn't be used for NAPPI matching.
    Examples: "Panado syrup" → "Panado"; "Metformin XR" → "Metformin";
              "Amoxil 500mg tabs" → "Amoxil".
    """
    import re
    if not name:
        return ""
    cleaned = name
    # Drop strength / route / form tokens
    noise = r"\b(tablets?|tabs?|caps?|capsules?|syrup|suspension|sus|inj|injection|cream|ointment|drops?|spray|inhaler|XR|SR|MR|CR|ER|IR|er|sr|cr|xr|extended.release|sustained.release|modified.release|controlled.release)\b"
    cleaned = re.sub(noise, "", cleaned, flags=re.IGNORECASE)
    # Drop trailing dosage like "500mg" "1g" "10ml"
    cleaned = re.sub(r"\b\d+(\.\d+)?\s*(mg|g|ml|mcg|µg|iu|units?)\b", "", cleaned, flags=re.IGNORECASE)
    # Collapse whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _strength_token(s: str) -> Optional[str]:
    """Extract a strength token like '500mg' / '10ml' from arbitrary text."""
    import re
    if not s:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*(mg|g|ml|mcg|µg|iu|units?)\b", s, flags=re.IGNORECASE)
    if not m:
        return None
    return f"{m.group(1)}{m.group(2).lower()}"


@router.get("/nappi/lookup")
async def nappi_lookup(
    drug_name: str = Query(..., description="Drug name as extracted from a prescription, e.g. 'Panado' or 'Metformin XR 1g'"),
    strength: Optional[str] = Query(None, description="Optional strength hint, e.g. '500mg'. If omitted, parsed from drug_name."),
    current_user: dict = Depends(require_capability("digitisation_validation")),
):
    """
    Look up a drug by extracted name. Tries exact match → brand → generic →
    substring on cleaned name. Prefers rows whose `strength` matches the
    extracted strength when one is present. Returns the best match plus a few
    alternates so the reviewer can pick.

    Response shape (matches what the EHR validation panel expects + extras):
      {
        found:        bool,
        nappi_code:   str | null,
        brand_name:   str | null,
        generic_name: str | null,
        strength:     str | null,
        schedule:     str | null,
        match_type:   'exact' | 'brand' | 'generic' | 'fuzzy' | 'none',
        alternates:   [{nappi_code, brand_name, generic_name, strength, schedule}, ...]
      }
    """
    raw = (drug_name or "").strip()
    if not raw:
        return {"found": False, "nappi_code": None, "match_type": "none"}

    cleaned = _strip_drug_modifiers(raw)
    extracted_strength = (strength or "").strip().lower() or _strength_token(raw)

    select_cols = "nappi_code, brand_name, generic_name, strength, dosage_form, schedule, atc_code, atc_class_desc"

    def _rank_by_strength(rows):
        """Stable-sort rows: strength-match first, then by row order."""
        if not extracted_strength:
            return rows
        keyed = []
        for r in rows:
            row_strength = (r.get("strength") or "").lower()
            keyed.append((0 if extracted_strength in row_strength else 1, r))
        keyed.sort(key=lambda x: x[0])
        return [r for _, r in keyed]

    def _format(row, match_type):
        return {
            "found":          True,
            "nappi_code":     row.get("nappi_code"),
            "brand_name":     row.get("brand_name"),
            "generic_name":   row.get("generic_name"),
            "strength":       row.get("strength"),
            "dosage_form":    row.get("dosage_form"),
            "schedule":       row.get("schedule"),
            "atc_code":       row.get("atc_code"),
            "atc_class_desc": row.get("atc_class_desc"),
            "match_type":     match_type,
        }

    try:
        # 1. Exact brand match (case-insensitive)
        res = supabase.table("nappi_codes").select(select_cols).ilike("brand_name", raw).limit(10).execute()
        if res.data:
            rows = _rank_by_strength(res.data)
            best = _format(rows[0], "exact-brand")
            best["alternates"] = [{k: r.get(k) for k in ("nappi_code", "brand_name", "generic_name", "strength", "schedule")} for r in rows[1:6]]
            return best

        # 2. Exact generic match
        res = supabase.table("nappi_codes").select(select_cols).ilike("generic_name", raw).limit(10).execute()
        if res.data:
            rows = _rank_by_strength(res.data)
            best = _format(rows[0], "exact-generic")
            best["alternates"] = [{k: r.get(k) for k in ("nappi_code", "brand_name", "generic_name", "strength", "schedule")} for r in rows[1:6]]
            return best

        # 3. Substring on cleaned name across brand + generic + ingredients
        if cleaned:
            pattern = f"%{cleaned}%"
            res = (
                supabase.table("nappi_codes")
                .select(select_cols)
                .or_(f"brand_name.ilike.{pattern},generic_name.ilike.{pattern},ingredients.ilike.{pattern}")
                .limit(15)
                .execute()
            )
            if res.data:
                rows = _rank_by_strength(res.data)
                # Decide match_type from where the hit landed
                best_row = rows[0]
                cleaned_l = cleaned.lower()
                if cleaned_l in (best_row.get("brand_name") or "").lower():
                    mt = "brand"
                elif cleaned_l in (best_row.get("generic_name") or "").lower():
                    mt = "generic"
                else:
                    mt = "fuzzy"
                best = _format(best_row, mt)
                best["alternates"] = [{k: r.get(k) for k in ("nappi_code", "brand_name", "generic_name", "strength", "schedule")} for r in rows[1:6]]
                return best
    except Exception as e:
        logger.error(f"NAPPI lookup failed for {raw!r}: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="NAPPI lookup failed")

    return {
        "found":        False,
        "nappi_code":   None,
        "brand_name":   None,
        "generic_name": None,
        "strength":     None,
        "schedule":     None,
        "match_type":   "none",
        "alternates":   [],
        "searched":     {"raw": raw, "cleaned": cleaned, "strength": extracted_strength},
    }


@router.get("/nappi/search")
async def nappi_search(
    q: str = Query(..., min_length=2),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_capability("digitisation_validation")),
):
    """
    Free-text NAPPI search across brand_name + generic_name + ingredients.
    Multi-word queries are AND-tokenised — every word must appear somewhere.
    """
    qstr = (q or "").strip()
    if len(qstr) < 2:
        return {"results": []}
    tokens = [t for t in qstr.split() if t]
    try:
        query = (
            supabase.table("nappi_codes")
            .select("nappi_code, brand_name, generic_name, strength, dosage_form, schedule, ingredients")
        )
        for token in tokens:
            pattern = f"%{token}%"
            query = query.or_(f"brand_name.ilike.{pattern},generic_name.ilike.{pattern},ingredients.ilike.{pattern}")
        res = query.limit(limit).execute()
    except Exception as e:
        logger.error(f"NAPPI search failed for {qstr!r}: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="NAPPI search failed")

    results = [
        {
            "nappi_code":   r.get("nappi_code"),
            "brand_name":   r.get("brand_name"),
            "generic_name": r.get("generic_name"),
            "strength":     r.get("strength"),
            "dosage_form":  r.get("dosage_form"),
            "schedule":     r.get("schedule"),
        }
        for r in (res.data or [])
    ]
    return {"query": qstr, "count": len(results), "results": results}


@router.get("/validation/{document_id}/history")
async def validation_history(
    document_id: str,
    limit: int = Query(200, ge=1, le=1000),
    current_user: dict = Depends(require_capability("digitisation_validation")),
):
    """
    Return the append-only edit log for a single document — every reviewer
    edit, accept, approve, reject, plus reprocess events. Workspace-scoped.

    Response shape:
      {
        document_id: str,
        original:    JSONB | null,    # AI baseline at extract time (extractions_original)
        approved:    JSONB | null,    # current/approved extractions
        history:     [
          { id, action, field_path, from_value, to_value, user_email, notes, created_at },
          ...
        ]
      }
    """
    workspace_id = current_user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No workspace context")

    # Tenancy check
    existing = (
        supabase.table("digitised_documents")
        .select("id, workspace_id")
        .eq("id", document_id)
        .eq("workspace_id", workspace_id)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # Pull session for original / approved values.
    original = None
    approved = None
    try:
        sess = (
            supabase.table("gp_validation_sessions")
            .select("extractions, extractions_original")
            .eq("document_id", document_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if sess.data:
            approved = sess.data[0].get("extractions")
            original = sess.data[0].get("extractions_original")
    except Exception as e:
        if "extractions_original" in str(e).lower():
            # column doesn't exist yet (migration 005 not run)
            try:
                sess = (
                    supabase.table("gp_validation_sessions")
                    .select("extractions")
                    .eq("document_id", document_id)
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )
                if sess.data:
                    approved = sess.data[0].get("extractions")
            except Exception:
                pass
        else:
            logger.error(f"Failed to fetch validation session for history: {e}")

    # Pull edit log.
    history: List[Dict[str, Any]] = []
    try:
        log_resp = (
            supabase.table("validation_edit_log")
            .select("id, action, field_path, from_value, to_value, user_email, notes, metadata, created_at")
            .eq("document_id", document_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        history = log_resp.data or []
    except Exception as e:
        if "validation_edit_log" in str(e).lower() or "relation" in str(e).lower():
            logger.warning("validation_edit_log table missing — returning empty history. Run migration 005 to fix.")
        else:
            logger.error(f"Failed to fetch validation edit log: {e}")

    return {
        "document_id": document_id,
        "original":    original,
        "approved":    approved,
        "history":     history,
    }


@router.post("/documents/{document_id}/reprocess")
async def reprocess_document(
    document_id: str,
    current_user: dict = Depends(require_capability("digitisation_upload")),
):
    """
    Flip a document back to status='queued_for_processing' so the
    document_watcher re-runs the LandingAI parse + extract pipeline against it.

    Use this after upgrading the extraction schema (rich GPPatientRecordExtraction)
    to backfill existing docs without a fresh upload.

    Workspace-scoped + capability-gated.
    NOTE: this DOES re-spend LandingAI API credits — one parse + one extract per call.
    """
    workspace_id = current_user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No workspace context")

    existing = (
        supabase.table("digitised_documents")
        .select("id, workspace_id, status, filename")
        .eq("id", document_id)
        .eq("workspace_id", workspace_id)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    now = datetime.now(timezone.utc).isoformat()
    supabase.table("digitised_documents").update({
        "status":     "queued_for_processing",
        "updated_at": now,
        "error_message": None,  # clear any prior failure
    }).eq("id", document_id).execute()

    return {
        "status":  "queued",
        "document_id": document_id,
        "filename": existing.data[0].get("filename"),
        "message": "Document re-queued. The watcher will re-process within ~15s.",
    }


@router.post("/validation/{document_id}/save")
async def save_validation_edits(
    document_id: str,
    payload: Optional[Dict[str, Any]] = None,
    current_user: dict = Depends(require_capability("digitisation_validation")),
):
    """
    Persist edited extractions back to gp_validation_sessions. Body shape:
    {"extractions": {...}}. Workspace-scoped + capability-gated.
    Does NOT change status — call /approve separately when the reviewer is done.
    """
    workspace_id = current_user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No workspace context")

    # Tenancy check
    existing = (
        supabase.table("digitised_documents")
        .select("id, workspace_id")
        .eq("id", document_id)
        .eq("workspace_id", workspace_id)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # Guard against empty / malformed payloads wiping out extractions. A valid
    # save MUST contain a non-empty extractions object; if a reviewer wants to
    # truly empty the record they should reject the document instead.
    new_extractions = (payload or {}).get("extractions")
    if not isinstance(new_extractions, dict) or not new_extractions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="extractions must be a non-empty object. Reject the document instead if there's nothing to save.",
        )
    now = datetime.now(timezone.utc).isoformat()
    user_email = current_user.get("email")

    # Pull the prior extractions so we can compute a per-field diff for the audit log.
    sess = (
        supabase.table("gp_validation_sessions")
        .select("id, extractions")
        .eq("document_id", document_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    session_id: Optional[str] = None
    prior_extractions: Dict[str, Any] = {}
    if sess.data:
        session_id        = sess.data[0]["id"]
        prior_extractions = sess.data[0].get("extractions") or {}

    # Diff and log every changed leaf as a separate audit row.
    prior_flat = _flatten_for_diff(prior_extractions)
    new_flat   = _flatten_for_diff(new_extractions)
    changed_paths = sorted({*prior_flat.keys(), *new_flat.keys()})
    diff_count = 0
    for p in changed_paths:
        if prior_flat.get(p) != new_flat.get(p):
            _write_edit_log(
                document_id=document_id,
                workspace_id=workspace_id,
                user_email=user_email,
                action="edit",
                session_id=session_id,
                field_path=p,
                from_value=prior_flat.get(p),
                to_value=new_flat.get(p),
            )
            diff_count += 1

    # Update the latest validation session.
    if session_id:
        supabase.table("gp_validation_sessions").update({
            "extractions": new_extractions,
            "updated_at":  now,
        }).eq("id", session_id).execute()
    else:
        new_session_id = str(uuid.uuid4())
        supabase.table("gp_validation_sessions").insert({
            "id":             new_session_id,
            "document_id":    document_id,
            "extractions":    new_extractions,
            "extractions_original": new_extractions,  # no AI run; reviewer-authored
            "workspace_id":   workspace_id,
            "tenant_id":      current_user.get("tenant_id"),
            "status":         "edited",
            "created_at":     now,
            "updated_at":     now,
        }).execute()
        session_id = new_session_id

    # Touch the digitised_documents row so the queue picks up the activity.
    supabase.table("digitised_documents").update({
        "updated_at": now,
    }).eq("id", document_id).execute()

    return {
        "status":         "success",
        "saved_keys":     list(new_extractions.keys()),
        "edits_logged":   diff_count,
    }


@router.post("/validation/{document_id}/preview-match")
async def preview_patient_match(
    document_id: str,
    current_user: dict = Depends(require_capability("digitisation_validation")),
):
    """Run the patient matcher against the latest extractions WITHOUT
    writing anything. Returns 0+ candidates with name/dob/id/match_kind
    so the validation panel can show a confirmation modal before /approve
    commits.

    Reviewers see this list and pick one of:
        - an existing patient (frontend then POSTs /approve with
          confirmed_patient_id)
        - a brand new patient (frontend POSTs /approve with
          create_new_patient=true)
    """
    workspace_id = current_user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="No workspace context")

    # Tenancy check
    doc = (
        supabase.table("digitised_documents")
        .select("id")
        .eq("id", document_id)
        .eq("workspace_id", workspace_id)
        .limit(1)
        .execute()
    )
    if not doc.data:
        raise HTTPException(status_code=404, detail="Document not found")

    # Latest validated extractions
    sess = (
        supabase.table("gp_validation_sessions")
        .select("extractions")
        .eq("document_id", document_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    extractions = (sess.data[0].get("extractions") if sess.data else None) or {}
    demographics = (extractions.get("patient_demographics") or {})

    from app.services.extraction_promoter import find_match_candidates
    candidates = find_match_candidates(supabase, workspace_id, demographics, limit=5)

    return {
        "document_id":    document_id,
        "demographics":   {
            "full_names":    demographics.get("full_names"),
            "surname":       demographics.get("surname"),
            "id_number":     demographics.get("id_number"),
            "date_of_birth": demographics.get("date_of_birth"),
        },
        "candidates":     candidates,
        "candidate_count": len(candidates),
    }


@router.post("/validation/{document_id}/approve")
async def approve_validation(
    document_id: str,
    background_tasks: BackgroundTasks,
    payload: Optional[Dict[str, Any]] = None,
    current_user: dict = Depends(require_capability("digitisation_validation")),
):
    """
    Approve a document. Workspace-scoped + capability-gated.

    On approval:
      1. Flip digitised_documents.status='validated' and stamp validator
      2. Promote the validated extractions into the structured tables
         (patients, encounters, diagnoses, vitals, allergies, prescriptions
         + prescription_items) via extraction_promoter — idempotent, keyed
         by source_document_id
      3. Stamp digitised_documents.patient_id with the matched/created id
      4. Append an `approve` audit row including the promotion summary

    Promotion failure does NOT block the approval status flip — it gets
    surfaced in the response under `promotion.error` so reviewers can
    see what happened. The doc remains validated; promotion can be
    re-attempted later.
    """
    workspace_id = current_user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No workspace context")

    # Tenancy check
    existing = (
        supabase.table("digitised_documents")
        .select("id, workspace_id")
        .eq("id", document_id)
        .eq("workspace_id", workspace_id)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    payload = payload or {}
    notes                  = payload.get("notes")
    confirmed_patient_id   = payload.get("confirmed_patient_id")
    create_new_patient     = bool(payload.get("create_new_patient", False))

    # Ambiguity gate: if neither override is set and the matcher finds 1+
    # candidates, refuse to auto-pick — return 409 with the candidates so
    # the frontend can show the modal. Only kicks in when the doc has
    # demographics worth matching on.
    if not confirmed_patient_id and not create_new_patient:
        sess_for_match = (
            supabase.table("gp_validation_sessions")
            .select("extractions")
            .eq("document_id", document_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        demo_for_match = (
            (sess_for_match.data[0].get("extractions") if sess_for_match.data else None) or {}
        ).get("patient_demographics") or {}
        from app.services.extraction_promoter import find_match_candidates
        candidates = find_match_candidates(supabase, workspace_id, demo_for_match, limit=5)
        if candidates:
            # Surface as a non-error response with a clear gate flag so the
            # frontend (or curl power-users) can act on it cleanly.
            raise HTTPException(
                status_code=409,
                detail={
                    "needs_confirmation": True,
                    "message": "Patient match requires confirmation. Pass confirmed_patient_id or create_new_patient=true.",
                    "candidates":         candidates,
                    "candidate_count":    len(candidates),
                    "demographics":       {
                        "full_names":    demo_for_match.get("full_names"),
                        "surname":       demo_for_match.get("surname"),
                        "id_number":     demo_for_match.get("id_number"),
                        "date_of_birth": demo_for_match.get("date_of_birth"),
                    },
                },
            )

    update_payload = {
        "status":       "validated",
        "validated_at": now,
        "validated_by": current_user.get("email") or "system",
        "approved_at":  now,
        "updated_at":   now,
    }
    if notes is not None:
        update_payload["error_message"] = None  # clear previous reject reason if any

    result = supabase.table("digitised_documents").update(update_payload).eq("id", document_id).execute()

    # Pull latest session — needed for both the audit log and the promotion.
    sess = (
        supabase.table("gp_validation_sessions")
        .select("id, extractions")
        .eq("document_id", document_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    session_id = sess.data[0]["id"] if sess.data else None
    extractions = (sess.data[0].get("extractions") if sess.data else None) or {}

    # ---- Promote into structured tables ------------------------------
    promotion: Optional[Dict[str, Any]] = None
    promotion_error: Optional[str] = None
    try:
        from app.services.extraction_promoter import promote_extractions
        result_obj = promote_extractions(
            supabase,
            workspace_id=workspace_id,
            document_id=document_id,
            extractions=extractions,
            created_by=current_user.get("email"),
            forced_patient_id=confirmed_patient_id,
            force_create_patient=create_new_patient,
        )
        promotion = result_obj.to_dict()
        # Link the document to the matched/created patient + first encounter
        link = {
            "patient_id":   result_obj.patient_id,
            "encounter_id": result_obj.encounter_ids[0] if result_obj.encounter_ids else None,
        }
        supabase.table("digitised_documents").update(link).eq("id", document_id).execute()
    except Exception as e:
        logger.error(f"approve_validation: promotion failed for {document_id}: {e}", exc_info=True)
        promotion_error = f"{type(e).__name__}: {e}"

    # Audit: record the approval, including the promotion summary so the
    # validation-history drawer can show what landed where.
    _write_edit_log(
        document_id=document_id,
        workspace_id=workspace_id,
        user_email=current_user.get("email"),
        action="approve",
        session_id=session_id,
        notes=notes,
        metadata={
            "promotion":       promotion,
            "promotion_error": promotion_error,
        } if (promotion or promotion_error) else None,
    )
    # Re-fetch the doc so the response reflects the post-promotion linkage
    # (patient_id, encounter_id) — the earlier `result` was captured before
    # the promoter ran.
    final = (
        supabase.table("digitised_documents")
        .select("*")
        .eq("id", document_id)
        .limit(1)
        .execute()
    )

    # Background: re-index the document for semantic search. Runs after
    # the API responds so the user doesn't wait for the OpenAI round-trip.
    # Failure to index is logged but doesn't surface (search is best-effort).
    if not promotion_error:
        from app.services.semantic_search import index_document
        background_tasks.add_task(index_document, supabase, document_id)

    return {
        "status":   "success",
        "document": final.data[0] if final.data else (result.data[0] if result.data else None),
        "promotion": promotion,
        "promotion_error": promotion_error,
    }


@router.post("/validation/{document_id}/reject")
async def reject_validation(
    document_id: str,
    payload: Optional[Dict[str, Any]] = None,
    current_user: dict = Depends(require_capability("digitisation_validation")),
):
    """Reject a document. Workspace-scoped + capability-gated."""
    workspace_id = current_user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No workspace context")

    existing = (
        supabase.table("digitised_documents")
        .select("id, workspace_id")
        .eq("id", document_id)
        .eq("workspace_id", workspace_id)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    reason = (payload or {}).get("reason") or "Rejected by reviewer"

    result = supabase.table("digitised_documents").update({
        "status":        "rejected",
        "validated_at":  now,
        "validated_by":  current_user.get("email") or "system",
        "error_message": reason,
        "updated_at":    now,
    }).eq("id", document_id).execute()

    # Audit: record the rejection with reason.
    sess = (
        supabase.table("gp_validation_sessions")
        .select("id")
        .eq("document_id", document_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    _write_edit_log(
        document_id=document_id,
        workspace_id=workspace_id,
        user_email=current_user.get("email"),
        action="reject",
        session_id=sess.data[0]["id"] if sess.data else None,
        notes=reason,
    )
    return {"status": "success", "document": result.data[0] if result.data else None}


ALLOWED_UPLOAD_EXTS = {'.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif'}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50MB per file


# ---------------------------------------------------------------------------
# Edit-log writer + diff helper.
# ---------------------------------------------------------------------------

def _flatten_for_diff(node: Any, path: str = "", out: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Flatten a nested extractions tree to {fieldPath: value} pairs."""
    if out is None:
        out = {}
    if node is None or isinstance(node, (str, int, float, bool)):
        out[path] = node
        return out
    if isinstance(node, list):
        for i, item in enumerate(node):
            _flatten_for_diff(item, f"{path}[{i}]", out)
        return out
    if isinstance(node, dict):
        if not node and path:
            out[path] = {}
            return out
        for k, v in node.items():
            sub = f"{path}.{k}" if path else k
            _flatten_for_diff(v, sub, out)
        return out
    out[path] = node
    return out


def _write_edit_log(
    document_id: str,
    workspace_id: str,
    user_email: Optional[str],
    action: str,
    *,
    session_id: Optional[str] = None,
    field_path: Optional[str] = None,
    from_value: Any = None,
    to_value: Any = None,
    notes: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Append a single audit entry to validation_edit_log. Fail-safe: a failed
    log write must never break the user's save/approve/reject — log + continue.
    """
    try:
        supabase.table("validation_edit_log").insert({
            "document_id":  document_id,
            "session_id":   session_id,
            "workspace_id": workspace_id,
            "user_email":   user_email,
            "action":       action,
            "field_path":   field_path,
            "from_value":   from_value,
            "to_value":     to_value,
            "notes":        notes,
            "metadata":     metadata,
        }).execute()
    except Exception as e:
        # If the table doesn't exist (migration 005 not yet run) downgrade silently.
        msg = str(e).lower()
        if "validation_edit_log" in msg or "relation" in msg:
            logger.warning("validation_edit_log table missing — skipping audit write. Run migration 005 to fix.")
            return
        logger.error(f"Failed to write edit log: {e}")


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(..., description="PDF or image to digitise"),
    current_user: dict = Depends(require_capability("digitisation_upload")),
):
    """
    Single-document upload — workspace-scoped, capability-gated.

    Uploads the file to Supabase Storage (medical-records bucket) and inserts
    a digitised_documents row with status='queued_for_processing'. The
    background document_watcher picks the row up within ~15s and runs the
    parse → split → extract pipeline against it.

    Returns the document_id so the frontend can poll status.
    """
    workspace_id = current_user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No workspace context")

    filename = file.filename or "document"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_UPLOAD_EXTS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type {ext}. Allowed: {sorted(ALLOWED_UPLOAD_EXTS)}",
        )

    file_content = await file.read()
    if len(file_content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large ({len(file_content)} bytes). Max is {MAX_UPLOAD_BYTES} bytes.",
        )

    document_id = str(uuid.uuid4())
    storage_path = f"{workspace_id}/{document_id}/{filename}"

    # 1. Upload to Supabase Storage
    try:
        supabase.storage.from_("medical-records").upload(
            path=storage_path,
            file=file_content,
            file_options={
                "content-type": file.content_type or "application/octet-stream",
                "upsert": "false",
            },
        )
    except Exception as e:
        logger.error(f"Storage upload failed for {storage_path}: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Storage upload failed: {e}",
        )

    # 2. Insert digitised_documents row — queued so the watcher processes it
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id":           document_id,
        "workspace_id": workspace_id,
        "filename":     filename,
        "file_path":    storage_path,
        "file_size":    len(file_content),
        "mime_type":    file.content_type,
        "status":       "queued_for_processing",
        "source":       "manual_upload",
        "uploaded_by":  current_user.get("email"),
        "upload_date":  now,
        "created_at":   now,
        "updated_at":   now,
        "template_used": True,
        "retry_count":  0,
    }
    try:
        supabase.table("digitised_documents").insert(record).execute()
    except Exception as e:
        logger.error(f"DB insert failed for {document_id}: {e}")
        # Best-effort cleanup of the orphan blob
        try:
            supabase.storage.from_("medical-records").remove([storage_path])
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register document: {e}",
        )

    return {
        "document_id": document_id,
        "filename":    filename,
        "file_size":   len(file_content),
        "status":      "queued_for_processing",
        "file_path":   storage_path,
    }


@router.get("/documents/{document_id}")
async def get_document_status(
    document_id: str,
    current_user: dict = Depends(require_capability("digitisation_upload")),
):
    """Single-document lookup for status polling. Workspace-scoped."""
    workspace_id = current_user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No workspace context")

    res = (
        supabase.table("digitised_documents")
        .select("id, filename, file_size, status, doc_type, pages_count, error_message, created_at, updated_at")
        .eq("id", document_id)
        .eq("workspace_id", workspace_id)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return {"document": res.data[0]}


@router.get("/documents")
async def list_documents(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (uploaded, parsing, parsed, pending_validation, validated, rejected)"),
    doc_type:      Optional[str] = Query(None, description="Filter by detected doc_type."),
    limit:         int           = Query(50, ge=1, le=200),
    current_user:  dict          = Depends(require_capability("digitisation_upload")),
):
    """List documents for the active workspace; optional status / doc_type filters."""
    workspace_id = current_user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No workspace context")

    query = (
        supabase.table("digitised_documents")
        .select("id, filename, file_size, file_path, status, doc_type, created_at, pages_count, source, workspace_id")
        .eq("workspace_id", workspace_id)
        .order("created_at", desc=True)
        .limit(limit)
    )
    if status_filter:
        query = query.eq("status", status_filter)
    if doc_type:
        query = query.eq("doc_type", doc_type)

    result = query.execute()
    return {"documents": result.data or []}


# ---------------------------------------------------------------------------
# Export jobs (Export Centre history + queueing)
# ---------------------------------------------------------------------------
# Phase A: tracking only. POST records the request as a 'queued' job; the
# actual FHIR/CSV bundle generation is deferred to Phase B (will turn the
# job 'running' → 'success'/'failed' and stash bundle_url). The UI becomes
# honest (no sample data) the moment the table exists, even with no jobs
# in it.

_EXPORT_FORMATS = {"fhir_r4", "csv", "json"}
_EXPORT_STATUSES_RUNNING = ("queued", "running")


def _next_batch_id(workspace_id: str) -> str:
    """EXP-YYYY-NNNN where NNNN is the next zero-padded sequence per year for
    this workspace. Pure cosmetic — collisions don't matter for storage; the
    UUID id is the real key. Used to mirror the human-friendly id from the
    mockup."""
    year = datetime.now(tz=timezone.utc).year
    prefix = f"EXP-{year}-"
    existing = (
        supabase.table("digitisation_export_jobs")
        .select("batch_id")
        .eq("workspace_id", workspace_id)
        .like("batch_id", f"{prefix}%")
        .execute()
        .data
        or []
    )
    max_n = 0
    for r in existing:
        bid = r.get("batch_id") or ""
        try:
            n = int(bid[len(prefix):])
        except ValueError:
            continue
        if n > max_n:
            max_n = n
    return f"{prefix}{max_n + 1:04d}"


@router.post("/exports")
async def create_export_job(
    background_tasks: BackgroundTasks,
    payload: dict = Body(..., description=(
        "Required: format ('fhir_r4'|'csv'|'json'). Optional: document_ids "
        "(list of validated doc IDs to include — defaults to all currently "
        "validated docs in the workspace), target_system (free text), "
        "metadata (object)."
    )),
    current_user: dict = Depends(require_capability("digitisation_export_basic")),
):
    """Queue a new export job. Returns the row immediately — bundle
    generation runs in the background (Phase B worker)."""
    workspace_id = current_user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="No workspace context")

    fmt = (payload.get("format") or "").lower().strip()
    if fmt not in _EXPORT_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"format must be one of {sorted(_EXPORT_FORMATS)}",
        )

    requested_ids = payload.get("document_ids") or []
    if requested_ids and not isinstance(requested_ids, list):
        raise HTTPException(status_code=400, detail="document_ids must be a list")

    # If no doc list given, snapshot all currently-validated docs in the
    # workspace. The job records the snapshot — re-running later won't pick
    # up newly-validated docs unless explicitly re-requested.
    if not requested_ids:
        snapshot = (
            supabase.table("digitised_documents")
            .select("id")
            .eq("workspace_id", workspace_id)
            .in_("status", ["validated", "approved"])
            .limit(2000)
            .execute()
            .data
            or []
        )
        requested_ids = [d["id"] for d in snapshot]

    if not requested_ids:
        raise HTTPException(
            status_code=400,
            detail="No validated documents to export. Validate at least one document first.",
        )

    batch_id = _next_batch_id(workspace_id)
    row = {
        "workspace_id":  workspace_id,
        "batch_id":      batch_id,
        "format":        fmt,
        "target_system": payload.get("target_system"),
        "record_count":  len(requested_ids),
        "document_ids":  requested_ids,
        "status":        "queued",
        "requested_by":  current_user.get("email"),
        "metadata":      payload.get("metadata") or None,
    }
    res = supabase.table("digitisation_export_jobs").insert(row).execute()
    job = (res.data or [{}])[0]

    # Phase B: kick off the bundle worker out-of-band so the API call
    # returns immediately with the queued row. The worker mutates the
    # same row's status / bundle_url when it finishes.
    if job.get("id"):
        from app.services.digitisation_export_worker import run_export_job
        background_tasks.add_task(run_export_job, supabase, job["id"])

    return {"job": job}


@router.get("/exports")
async def list_export_jobs(
    limit: int = Query(50, ge=1, le=500),
    current_user: dict = Depends(require_capability("digitisation_export_basic")),
):
    """List the most recent export jobs for this workspace."""
    workspace_id = current_user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="No workspace context")

    res = (
        supabase.table("digitisation_export_jobs")
        .select(
            "id, batch_id, format, target_system, record_count, status, "
            "error_message, bundle_url, requested_by, created_at, "
            "started_at, completed_at"
        )
        .eq("workspace_id", workspace_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return {"exports": res.data or []}


@router.get("/exports/{job_id}")
async def get_export_job(
    job_id: str,
    current_user: dict = Depends(require_capability("digitisation_export_basic")),
):
    """Single-job detail for the receipt drawer."""
    workspace_id = current_user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="No workspace context")

    res = (
        supabase.table("digitisation_export_jobs")
        .select("*")
        .eq("id", job_id)
        .eq("workspace_id", workspace_id)
        .limit(1)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Export job not found")
    return {"job": res.data[0]}


@router.get("/exports/{job_id}/download")
async def download_export_bundle(
    job_id: str,
    current_user: dict = Depends(require_capability("digitisation_export_basic")),
):
    """Stream the generated FHIR bundle JSON. Only available once the
    job has run (bundle_url is set). Returns 409 if the job exists but
    isn't done yet, 404 if neither Supabase Storage nor local disk has
    the bundle."""
    from fastapi.responses import Response
    from app.services.digitisation_export_worker import fetch_bundle

    workspace_id = current_user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="No workspace context")

    res = (
        supabase.table("digitisation_export_jobs")
        .select("id, batch_id, status, bundle_url, workspace_id")
        .eq("id", job_id)
        .eq("workspace_id", workspace_id)
        .limit(1)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Export job not found")
    job = res.data[0]
    if job["status"] in ("queued", "running"):
        raise HTTPException(status_code=409, detail=f"Export still {job['status']}; try again shortly")
    if job["status"] == "failed" or not job.get("bundle_url"):
        raise HTTPException(status_code=404, detail="No bundle was generated for this job")

    content = fetch_bundle(supabase, workspace_id, job["batch_id"])
    if content is None:
        raise HTTPException(status_code=404, detail="Bundle missing from Storage and disk")

    return Response(
        content=content,
        media_type="application/fhir+json",
        headers={"Content-Disposition": f'attachment; filename="{job["batch_id"]}.fhir.json"'},
    )


# ---------------------------------------------------------------------------
# FHIR connections (Type C downstream EHR push)
# ---------------------------------------------------------------------------
# Phase A: connection CRUD + saved metadata only. Auth credentials and
# real connection tests come in Phase B (needs Supabase Vault for secrets).

_FHIR_ENVIRONMENTS = {"sandbox", "staging", "production"}
_FHIR_AUTH_METHODS = {"none", "basic", "bearer",
                       "oauth2_client_credentials", "smart_on_fhir"}


def _redact_fhir_connection(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Strip secrets from a connection row before returning it via the API.

    Bearer tokens (and any future basic / OAuth credentials) live under
    `metadata.credentials.*`. The DB stores them in plaintext JSONB until
    Supabase Vault lands; the API surface MUST never echo them back so
    they don't leak via tool inspect, browser dev-tools, frontend caches,
    or screenshots. The connection-test endpoint reads credentials from
    the table directly, so the redaction here doesn't break test flow.
    """
    if not row:
        return row
    redacted = dict(row)
    md = redacted.get("metadata")
    if isinstance(md, dict) and "credentials" in md:
        md = dict(md)
        creds = md.get("credentials") or {}
        if isinstance(creds, dict) and creds:
            md["credentials"] = {
                "configured": list(creds.keys()),  # which fields are stored
            }
        redacted["metadata"] = md
    return redacted


def _validate_fhir_payload(payload: dict, *, partial: bool = False) -> dict:
    """Validate connection payload. partial=True for update (every field
    optional); partial=False for create (name, fhir_url required)."""
    out: dict = {}
    if not partial or "name" in payload:
        name = (payload.get("name") or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="name is required")
        out["name"] = name
    if not partial or "fhir_url" in payload:
        url = (payload.get("fhir_url") or "").strip()
        if not url.startswith(("http://", "https://")):
            raise HTTPException(status_code=400, detail="fhir_url must be an http(s) URL")
        out["fhir_url"] = url
    if "environment" in payload:
        env = (payload.get("environment") or "").strip().lower()
        if env not in _FHIR_ENVIRONMENTS:
            raise HTTPException(status_code=400, detail=f"environment must be one of {sorted(_FHIR_ENVIRONMENTS)}")
        out["environment"] = env
    if "auth_method" in payload:
        am = (payload.get("auth_method") or "").strip().lower()
        if am not in _FHIR_AUTH_METHODS:
            raise HTTPException(status_code=400, detail=f"auth_method must be one of {sorted(_FHIR_AUTH_METHODS)}")
        out["auth_method"] = am
    if "is_default" in payload:
        out["is_default"] = bool(payload.get("is_default"))
    if "metadata" in payload:
        out["metadata"] = payload.get("metadata")
    return out


@router.get("/fhir/connections")
async def list_fhir_connections(
    current_user: dict = Depends(require_capability("digitisation_export_basic")),
):
    """All saved FHIR connections for this workspace."""
    workspace_id = current_user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="No workspace context")

    res = (
        supabase.table("digitisation_fhir_connections")
        .select(
            "id, name, fhir_url, environment, auth_method, is_default, "
            "last_test_at, last_test_ok, last_test_error, created_at, updated_at"
        )
        .eq("workspace_id", workspace_id)
        .order("is_default", desc=True)
        .order("created_at", desc=True)
        .execute()
    )
    return {"connections": res.data or []}


@router.post("/fhir/connections")
async def create_fhir_connection(
    payload: dict = Body(..., description=(
        "Required: name, fhir_url. Optional: environment "
        "(sandbox|staging|production, default sandbox), auth_method "
        "(default 'none'), is_default (default false), metadata."
    )),
    current_user: dict = Depends(require_capability("digitisation_export_basic")),
):
    workspace_id = current_user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="No workspace context")

    fields = _validate_fhir_payload(payload, partial=False)

    # If is_default is set, clear existing default first (respects the partial
    # unique index added by migration 009).
    if fields.get("is_default"):
        supabase.table("digitisation_fhir_connections") \
            .update({"is_default": False}) \
            .eq("workspace_id", workspace_id) \
            .eq("is_default", True) \
            .execute()

    row = {
        "workspace_id":  workspace_id,
        "environment":   "sandbox",
        "auth_method":   "none",
        "is_default":    False,
        "created_by":    current_user.get("email"),
        **fields,
    }
    res = supabase.table("digitisation_fhir_connections").insert(row).execute()
    conn = (res.data or [{}])[0]
    return {"connection": _redact_fhir_connection(conn)}


@router.patch("/fhir/connections/{conn_id}")
async def update_fhir_connection(
    conn_id: str,
    payload: dict = Body(...),
    current_user: dict = Depends(require_capability("digitisation_export_basic")),
):
    workspace_id = current_user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="No workspace context")

    fields = _validate_fhir_payload(payload, partial=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    fields["updated_at"] = datetime.now(tz=timezone.utc).isoformat()

    if fields.get("is_default") is True:
        supabase.table("digitisation_fhir_connections") \
            .update({"is_default": False}) \
            .eq("workspace_id", workspace_id) \
            .eq("is_default", True) \
            .neq("id", conn_id) \
            .execute()

    res = (
        supabase.table("digitisation_fhir_connections")
        .update(fields)
        .eq("id", conn_id)
        .eq("workspace_id", workspace_id)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Connection not found")
    return {"connection": _redact_fhir_connection(res.data[0])}


@router.delete("/fhir/connections/{conn_id}")
async def delete_fhir_connection(
    conn_id: str,
    current_user: dict = Depends(require_capability("digitisation_export_basic")),
):
    workspace_id = current_user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="No workspace context")

    res = (
        supabase.table("digitisation_fhir_connections")
        .delete()
        .eq("id", conn_id)
        .eq("workspace_id", workspace_id)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Connection not found")
    return {"deleted": True, "id": conn_id}


@router.post("/fhir/connections/{conn_id}/test")
async def test_fhir_connection(
    conn_id: str,
    current_user: dict = Depends(require_capability("digitisation_export_basic")),
):
    """GET {fhir_url}/metadata — the FHIR CapabilityStatement endpoint.
    A 200 + JSON content-type is taken as success. Records the result on
    the connection row (last_test_*).
    """
    import httpx
    workspace_id = current_user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="No workspace context")

    res = (
        supabase.table("digitisation_fhir_connections")
        .select("id, fhir_url, auth_method, metadata")
        .eq("id", conn_id)
        .eq("workspace_id", workspace_id)
        .limit(1)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Connection not found")
    conn = res.data[0]

    base = (conn["fhir_url"] or "").rstrip("/")
    metadata_url = f"{base}/metadata"

    # Build auth headers from the connection's metadata. Phase B supports
    # 'none' and 'bearer'; basic + oauth2/SMART live in metadata.credentials
    # but aren't applied yet (would need Vault for storage of secrets).
    headers = {"Accept": "application/fhir+json,application/json"}
    creds = (conn.get("metadata") or {}).get("credentials") or {}
    if conn.get("auth_method") == "bearer" and creds.get("token"):
        headers["Authorization"] = f"Bearer {creds['token']}"

    now_iso = datetime.now(tz=timezone.utc).isoformat()
    ok = False
    err: Optional[str] = None
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            r = client.get(metadata_url, headers=headers)
        if r.status_code == 200:
            ctype = r.headers.get("content-type", "")
            if "json" in ctype.lower():
                ok = True
            else:
                err = f"200 OK but unexpected content-type: {ctype}"
        else:
            # Try to extract a useful FHIR OperationOutcome error from the body.
            body_snip = r.text[:200].replace("\n", " ").strip()
            err = f"HTTP {r.status_code}: {body_snip}"
    except httpx.ConnectError as e:
        err = f"Could not reach {metadata_url}: {e}"
    except httpx.TimeoutException:
        err = f"Timeout after 10s contacting {metadata_url}"
    except Exception as e:
        err = f"{type(e).__name__}: {e}"

    update = {
        "last_test_at":    now_iso,
        "last_test_ok":    ok,
        "last_test_error": err if not ok else None,
    }
    supabase.table("digitisation_fhir_connections") \
        .update(update) \
        .eq("id", conn_id) \
        .execute()
    return {"ok": ok, "error": err, "tested_at": now_iso, "metadata_url": metadata_url}


# ---------------------------------------------------------------------------
# Semantic search (TRACEABILITY §9)
# ---------------------------------------------------------------------------

# Naive in-process rate limiter for /search. OpenAI embedding cost is small
# (~$0.0000013/query) but a runaway frontend bug or malicious actor could
# still rack up bills. 30 queries / minute / user is generous for human
# typing, blocks robots cheaply. Replace with Redis-backed limiter for
# multi-instance deploy.
import time as _time
from collections import deque as _deque
from threading import Lock as _Lock
_search_rate_lock  = _Lock()
_search_rate_state: Dict[str, _deque] = {}
_SEARCH_RATE_WINDOW_S  = 60
_SEARCH_RATE_MAX       = 30


def _enforce_search_rate_limit(user_email: str) -> None:
    now = _time.monotonic()
    with _search_rate_lock:
        bucket = _search_rate_state.setdefault(user_email, _deque())
        # drop old hits
        while bucket and now - bucket[0] > _SEARCH_RATE_WINDOW_S:
            bucket.popleft()
        if len(bucket) >= _SEARCH_RATE_MAX:
            retry = int(_SEARCH_RATE_WINDOW_S - (now - bucket[0])) + 1
            raise HTTPException(
                status_code=429,
                detail=f"Search rate limit: {_SEARCH_RATE_MAX}/min. Retry in {retry}s.",
                headers={"Retry-After": str(retry)},
            )
        bucket.append(now)


@router.get("/search")
async def search_documents(
    q:           str  = Query(..., min_length=2, description="natural-language query"),
    limit:       int  = Query(20, ge=1, le=100),
    patient_id:  Optional[str] = Query(None, description="restrict to one patient"),
    scope:       str  = Query("workspace", regex="^(workspace|all)$",
                              description="'workspace' (default) or 'all' to federate across "
                                          "every workspace the user has access to (TRACEABILITY §11)"),
    current_user: dict = Depends(require_capability("digitisation_validation")),
):
    _enforce_search_rate_limit(current_user.get("email") or "anonymous")
    """Embed the query and return ranked chunks across the workspace's
    indexed documents. Results include the source document_id +
    patient_id so the caller can deep-link into the validation panel
    or patient EHR.

    No-results case returns an empty `hits` list — never errors.
    """
    workspace_id = current_user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="No workspace context")

    # Resolve the workspace list the search will federate across.
    # scope='workspace' (default): just the active workspace.
    # scope='all': every workspace this user has access to via user_workspaces.
    target_workspaces: list = [workspace_id]
    if scope == "all":
        from app.api.auth import list_user_workspaces
        accessible = list_user_workspaces(current_user.get("user_id") or "")
        if accessible:
            target_workspaces = [w["workspace_id"] for w in accessible]

    try:
        from app.services.semantic_search import search as do_search
        # Per-workspace search; merge by similarity, keep top N.
        all_hits = []
        for ws in target_workspaces:
            all_hits.extend(do_search(
                supabase,
                workspace_id=ws,
                query=q,
                limit=limit,
                patient_id=patient_id,
            ))
        all_hits.sort(key=lambda h: -h.similarity)
        hits = all_hits[:limit]
    except Exception as e:
        logger.error(f"semantic search failed for workspaces={target_workspaces} q={q!r}: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {type(e).__name__}: {e}")

    # Group hits by document_id so the UI can render one card per doc
    by_doc: Dict[str, Dict[str, Any]] = {}
    for h in hits:
        d = by_doc.setdefault(h.document_id, {
            "document_id":   h.document_id,
            "patient_id":    h.patient_id,
            "top_similarity": h.similarity,
            "snippets":      [],
        })
        if h.similarity > d["top_similarity"]:
            d["top_similarity"] = h.similarity
        d["snippets"].append({
            "section":    h.chunk_section,
            "text":       h.chunk_text,
            "similarity": h.similarity,
        })

    # Order docs by their best chunk
    docs = sorted(by_doc.values(), key=lambda x: -x["top_similarity"])
    return {
        "query":   q,
        "limit":   limit,
        "hits":    [h.to_dict() for h in hits],
        "docs":    docs,
        "count":   len(hits),
    }


@router.post("/search/reindex/{document_id}")
async def reindex_document(
    document_id:        str,
    background_tasks:   BackgroundTasks,
    current_user: dict = Depends(require_capability("digitisation_validation")),
):
    """Re-index a single document on demand (admin / debug)."""
    workspace_id = current_user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="No workspace context")
    # tenancy check
    res = (
        supabase.table("digitised_documents")
        .select("id")
        .eq("id", document_id)
        .eq("workspace_id", workspace_id)
        .limit(1)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Document not found")
    from app.services.semantic_search import index_document
    background_tasks.add_task(index_document, supabase, document_id)
    return {"status": "queued", "document_id": document_id}
