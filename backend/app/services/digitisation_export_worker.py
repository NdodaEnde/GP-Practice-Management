"""
digitisation_export_worker — Phase B FHIR bundle generator.

Picks up queued rows from `digitisation_export_jobs`, fetches each
referenced document's validated extractions from
`gp_validation_sessions`, maps them into FHIR R4 resources via the
existing `fhir_export.py` mappers, wraps everything into a single
batch Bundle, and writes the JSON to local Storage. Updates the job
row with status (success / partial / failed) and bundle_url.

Phase B is local-Storage only. Pushing to a downstream FHIR server
(via a configured `digitisation_fhir_connections` row) is a future
follow-up — the bundle is generated and downloadable today.

Triggered via FastAPI BackgroundTasks from the POST /exports
endpoint. Designed to also be runnable from a CLI for retries.
"""

from __future__ import annotations

import json
import logging
import os
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.services.fhir_export import build_patient_bundle


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

# Local on-disk path for generated FHIR bundles. Lives next to the document
# storage. Each export gets its own file.
EXPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "storage" / "exports"


def _bundle_path(workspace_id: str, batch_id: str) -> Path:
    """Where this batch's bundle lives on disk."""
    safe_ws = workspace_id.replace("/", "_")
    safe_batch = batch_id.replace("/", "_")
    return EXPORTS_DIR / safe_ws / f"{safe_batch}.json"


def _bundle_url(job_id: str) -> str:
    """The URL the frontend should fetch to download the bundle. Routes to
    GET /api/digitisation/exports/{job_id}/download which serves the file."""
    return f"/api/digitisation/exports/{job_id}/download"


# ---------------------------------------------------------------------------
# Extractions → mapper-compatible row adapters
# ---------------------------------------------------------------------------
# The fhir_export mappers expect rows shaped like the live `patients`,
# `allergies`, `diagnoses`, etc. tables. Validated digitisation extractions
# are a different (richer) JSONB shape captured during AI extraction. These
# adapters reshape the JSONB so build_patient_bundle works unchanged.

def _split_full_name(full: str) -> Tuple[Optional[str], Optional[str]]:
    if not full:
        return None, None
    parts = str(full).strip().split()
    if not parts:
        return None, None
    if len(parts) == 1:
        return parts[0], None
    return parts[0], " ".join(parts[1:])


def _adapt_patient(extractions: Dict[str, Any], doc_id: str) -> Dict[str, Any]:
    demo = (extractions or {}).get("patient_demographics") or {}
    first, last = _split_full_name(demo.get("full_names") or "")
    return {
        "id":            doc_id,                              # synthetic — keyed by source doc
        "first_name":    first,
        "last_name":     demo.get("surname") or last,
        "id_number":     demo.get("id_number"),
        "date_of_birth": demo.get("date_of_birth"),
        "gender":        demo.get("gender"),
    }


def _adapt_allergies(extractions: Dict[str, Any], doc_id: str) -> List[Dict[str, Any]]:
    hx = (extractions or {}).get("clinical_history") or {}
    raw = hx.get("known_allergies")
    items: List[str] = []
    if isinstance(raw, list):
        items = [str(x) for x in raw if x]
    elif isinstance(raw, str) and raw.strip():
        # Comma / newline separated free text — split conservatively.
        items = [p.strip() for p in raw.replace("\n", ",").split(",") if p.strip()]
    return [
        {
            "id":         f"{doc_id}-allergy-{i}",
            "substance":  s,
            "status":     "active",
            "severity":   None,
            "notes":      None,
            "created_at": None,
        }
        for i, s in enumerate(items)
    ]


def _adapt_diagnoses(extractions: Dict[str, Any], doc_id: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for i, d in enumerate((extractions or {}).get("diagnoses") or []):
        out.append({
            "id":          f"{doc_id}-dx-{i}",
            "icd10_code":  d.get("icd10_code"),
            "description": d.get("description"),
            "status":      d.get("status") or "active",
            "created_at":  d.get("consultation_date"),
        })
    return out


def _adapt_medications(extractions: Dict[str, Any], doc_id: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for i, m in enumerate((extractions or {}).get("medications") or []):
        out.append({
            "id":              f"{doc_id}-med-{i}",
            "nappi_code":      m.get("nappi_code"),
            "medication_name": m.get("drug_name") or m.get("medication_name"),
            "generic_name":    m.get("generic_name"),
            "status":          m.get("status") or "active",
            "dosage":          m.get("dosage"),
            "frequency":       m.get("frequency"),
            "duration":        m.get("duration"),
            "quantity":        m.get("quantity"),
        })
    return out


def _adapt_vitals(extractions: Dict[str, Any], doc_id: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for i, v in enumerate((extractions or {}).get("vitals_history") or []):
        out.append({
            "id":                    f"{doc_id}-vital-{i}",
            "consultation_date":     v.get("consultation_date"),
            "temperature_c":         v.get("temperature_c"),
            "heart_rate":            v.get("heart_rate"),
            "bp_systolic":           v.get("bp_systolic"),
            "bp_diastolic":          v.get("bp_diastolic"),
            "oxygen_saturation":     v.get("oxygen_saturation"),
            "weight_kg":             v.get("weight_kg"),
            "bmi":                   v.get("bmi"),
            "hba1c":                 v.get("hba1c"),
            "blood_glucose_fasting": v.get("blood_glucose_fasting"),
        })
    return out


def _adapt_encounters(extractions: Dict[str, Any], doc_id: str) -> List[Dict[str, Any]]:
    """Encounters are derived from the progress_notes timeline; each note
    represents a consultation. Falls back to an empty list when there are
    no notes."""
    out: List[Dict[str, Any]] = []
    for i, n in enumerate((extractions or {}).get("progress_notes") or []):
        out.append({
            "id":                f"{doc_id}-enc-{i}",
            "consultation_date": n.get("consultation_date") or n.get("date"),
            "status":            n.get("status") or "finished",
            "type":              "consultation",
        })
    return out


# ---------------------------------------------------------------------------
# Resource-mapping filter
# ---------------------------------------------------------------------------
# A FHIR connection's metadata.resource_mapping (Step 03 in the wizard) lets
# the user pick which categories to include. Default = all enabled.

_DEFAULT_RESOURCE_FILTER = {
    "patient":      True,
    "allergies":    True,
    "diagnoses":    True,
    "medications":  True,
    "vitals":       True,
    "encounters":   True,
}


def _resource_filter(connection_metadata: Optional[Dict[str, Any]]) -> Dict[str, bool]:
    """Merge user-selected resource flags over the default. Unknown keys are
    ignored. Patient is always included (a Bundle without a Patient subject
    is meaningless for our use case)."""
    flags = dict(_DEFAULT_RESOURCE_FILTER)
    user = (connection_metadata or {}).get("resource_mapping") or {}
    for k in flags:
        if k in user:
            flags[k] = bool(user[k])
    flags["patient"] = True
    return flags


# ---------------------------------------------------------------------------
# Per-document bundle
# ---------------------------------------------------------------------------

def _bundle_for_document(
    doc_id: str,
    extractions: Dict[str, Any],
    flags: Dict[str, bool],
) -> Dict[str, Any]:
    """Generate a FHIR Bundle dict for a single document's extractions."""
    patient_row = _adapt_patient(extractions, doc_id)
    allergies   = _adapt_allergies(extractions,   doc_id) if flags["allergies"]   else []
    diagnoses   = _adapt_diagnoses(extractions,   doc_id) if flags["diagnoses"]   else []
    medications = _adapt_medications(extractions, doc_id) if flags["medications"] else []
    vitals      = _adapt_vitals(extractions,      doc_id) if flags["vitals"]      else []
    encounters  = _adapt_encounters(extractions,  doc_id) if flags["encounters"]  else []

    bundle = build_patient_bundle(
        patient_row=patient_row,
        allergies=allergies,
        diagnoses=diagnoses,
        medications=medications,
        vitals=vitals,
        encounters=encounters,
    )
    return bundle.model_dump(by_alias=True, exclude_none=True, mode="json")


# ---------------------------------------------------------------------------
# Worker entry point
# ---------------------------------------------------------------------------

def run_export_job(supabase, job_id: str) -> None:
    """Move a queued export job all the way to success / failed.

    Flow:
      1. SELECT job; bail unless still 'queued'
      2. Mark 'running', stamp started_at
      3. Resolve the configured FHIR connection (default for workspace) so
         we can pick up its resource_mapping flags. If none configured,
         all resources are included.
      4. For each document_id: fetch validated extractions, build a
         per-document Bundle dict, append to outer batch
      5. Write outer batch JSON to disk under EXPORTS_DIR
      6. Mark 'success' (or 'partial' if some documents failed),
         stamp completed_at + bundle_url
    """
    logger.info(f"[export-worker] starting job {job_id}")

    # 1. Fetch + status check
    res = (
        supabase.table("digitisation_export_jobs")
        .select("*")
        .eq("id", job_id)
        .limit(1)
        .execute()
    )
    if not res.data:
        logger.error(f"[export-worker] job {job_id} not found")
        return
    job = res.data[0]
    if job.get("status") != "queued":
        logger.info(f"[export-worker] job {job_id} status={job.get('status')}, skipping")
        return

    # 2. Mark running
    now_iso = datetime.now(tz=timezone.utc).isoformat()
    supabase.table("digitisation_export_jobs").update({
        "status":     "running",
        "started_at": now_iso,
    }).eq("id", job_id).execute()

    workspace_id = job["workspace_id"]
    document_ids = job.get("document_ids") or []

    try:
        # 3. Resolve connection metadata
        conn_res = (
            supabase.table("digitisation_fhir_connections")
            .select("metadata, name, fhir_url, environment")
            .eq("workspace_id", workspace_id)
            .eq("is_default", True)
            .limit(1)
            .execute()
        )
        connection = conn_res.data[0] if conn_res.data else None
        flags = _resource_filter(connection.get("metadata") if connection else None)

        # 4. Per-document mapping
        per_doc_bundles: List[Dict[str, Any]] = []
        failed_docs: List[Tuple[str, str]] = []
        for doc_id in document_ids:
            try:
                vs = (
                    supabase.table("gp_validation_sessions")
                    .select("extractions")
                    .eq("document_id", doc_id)
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )
                if not vs.data:
                    failed_docs.append((doc_id, "no validation session found"))
                    continue
                extractions = vs.data[0].get("extractions") or {}
                bundle_dict = _bundle_for_document(doc_id, extractions, flags)
                per_doc_bundles.append(bundle_dict)
            except Exception as e:
                logger.warning(f"[export-worker] doc {doc_id} mapping failed: {e}")
                failed_docs.append((doc_id, str(e)))

        # 5. Write batch bundle
        outer_bundle = {
            "resourceType": "Bundle",
            "type":         "batch",
            "timestamp":    datetime.now(tz=timezone.utc).isoformat(),
            "meta": {
                "tag": [
                    {"system": "https://surgiscan.health/export", "code": job["batch_id"]},
                    {"system": "https://surgiscan.health/connection",
                     "code": (connection or {}).get("name") or "no-connection"},
                ],
            },
            "entry": [{"resource": b} for b in per_doc_bundles],
        }
        path = _bundle_path(workspace_id, job["batch_id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(outer_bundle, indent=2), encoding="utf-8")

        # 6. Final status
        completed_iso = datetime.now(tz=timezone.utc).isoformat()
        if not per_doc_bundles:
            # Every doc failed — count as failed, not partial.
            err = "; ".join(f"{d[:8]}…: {m}" for d, m in failed_docs[:3])
            supabase.table("digitisation_export_jobs").update({
                "status":        "failed",
                "error_message": f"No documents mapped successfully. {err}",
                "completed_at":  completed_iso,
            }).eq("id", job_id).execute()
            logger.error(f"[export-worker] job {job_id} failed: every document failed")
            return

        final_status = "partial" if failed_docs else "success"
        update = {
            "status":       final_status,
            "completed_at": completed_iso,
            "bundle_url":   _bundle_url(job_id),
        }
        if failed_docs:
            update["error_message"] = (
                f"{len(failed_docs)} of {len(document_ids)} documents failed: "
                + "; ".join(f"{d[:8]}…: {m}" for d, m in failed_docs[:3])
            )
        supabase.table("digitisation_export_jobs").update(update).eq("id", job_id).execute()
        logger.info(
            f"[export-worker] job {job_id} {final_status}: "
            f"{len(per_doc_bundles)}/{len(document_ids)} documents → {path}"
        )

    except Exception as e:
        logger.error(f"[export-worker] job {job_id} crashed: {e}\n{traceback.format_exc()}")
        supabase.table("digitisation_export_jobs").update({
            "status":        "failed",
            "error_message": f"{type(e).__name__}: {e}",
            "completed_at":  datetime.now(tz=timezone.utc).isoformat(),
        }).eq("id", job_id).execute()
