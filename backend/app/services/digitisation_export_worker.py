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
#
# Production: Supabase Storage bucket `digitisation-exports`. One-time setup
# in Supabase Studio → Storage → Create bucket → name 'digitisation-exports',
# private (no public access — the API proxies via the download endpoint).
#
# Dev fallback: local disk under backend/storage/exports/. Used automatically
# when the Storage bucket isn't reachable (so a fresh checkout doesn't break).

EXPORTS_DIR    = Path(__file__).resolve().parent.parent.parent / "storage" / "exports"
EXPORTS_BUCKET = "digitisation-exports"


# Per-format artifact metadata. fhir_r4 / json both serialise to a FHIR JSON
# bundle today; csv produces a flat long-format records file.
_FORMAT_EXT = {"fhir_r4": ".json", "json": ".json", "csv": ".csv"}
_FORMAT_CONTENT_TYPE = {
    "fhir_r4": "application/fhir+json",
    "json":    "application/fhir+json",
    "csv":     "text/csv",
}


def _ext_for_format(fmt: Optional[str]) -> str:
    return _FORMAT_EXT.get((fmt or "fhir_r4").lower(), ".json")


def _content_type_for_format(fmt: Optional[str]) -> str:
    return _FORMAT_CONTENT_TYPE.get((fmt or "fhir_r4").lower(), "application/fhir+json")


def _bundle_storage_key(workspace_id: str, batch_id: str, ext: str = ".json") -> str:
    """Object key inside the Supabase Storage bucket."""
    return f"{workspace_id.replace('/', '_')}/{batch_id.replace('/', '_')}{ext}"


def _bundle_path(workspace_id: str, batch_id: str, ext: str = ".json") -> Path:
    """Local-disk fallback path."""
    safe_ws    = workspace_id.replace("/", "_")
    safe_batch = batch_id.replace("/", "_")
    return EXPORTS_DIR / safe_ws / f"{safe_batch}{ext}"


def _bundle_url(job_id: str) -> str:
    """The URL the frontend should fetch to download the bundle. Routes to
    GET /api/digitisation/exports/{job_id}/download which serves it after
    auth + tenancy check."""
    return f"/api/digitisation/exports/{job_id}/download"


def _store_bundle(
    supabase, workspace_id: str, batch_id: str, content: str,
    *, ext: str = ".json", content_type: str = "application/fhir+json",
) -> str:
    """Write the generated artifact somewhere durable. Tries Supabase
    Storage first; falls back to local disk if the bucket isn't reachable.
    Returns the storage location for diagnostic logging — not user-facing."""
    key = _bundle_storage_key(workspace_id, batch_id, ext)
    bytes_ = content.encode("utf-8")
    try:
        # Use upsert so re-runs of the same batch_id overwrite cleanly.
        supabase.storage.from_(EXPORTS_BUCKET).upload(
            path=key,
            file=bytes_,
            file_options={"content-type": content_type, "upsert": "true"},
        )
        return f"supabase://{EXPORTS_BUCKET}/{key}"
    except Exception as e:
        logger.warning(
            f"[export-worker] Supabase Storage upload failed (falling back "
            f"to disk): {e}"
        )
        path = _bundle_path(workspace_id, batch_id, ext)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"file://{path}"


def fetch_bundle(supabase, workspace_id: str, batch_id: str, ext: str = ".json") -> Optional[bytes]:
    """Read the artifact content for download. Tries Supabase Storage first,
    then local disk. Returns None if neither has it."""
    key = _bundle_storage_key(workspace_id, batch_id, ext)
    # Try Storage
    try:
        return supabase.storage.from_(EXPORTS_BUCKET).download(key)
    except Exception as e:
        logger.debug(f"[export-worker] Storage download miss for {key}: {e}")
    # Fall back to local disk
    path = _bundle_path(workspace_id, batch_id, ext)
    if path.exists():
        return path.read_bytes()
    return None


# ---------------------------------------------------------------------------
# Phase C — auto-POST to configured FHIR endpoint
# ---------------------------------------------------------------------------

def _attempt_push(
    supabase,
    job_id: str,
    workspace_id: str,
    bundle_content: str,
    connection: Optional[Dict[str, Any]],
) -> None:
    """Best-effort push of the generated bundle to the workspace's default
    FHIR connection. Records push_status / push_status_code / push_error /
    pushed_at on the job row. Push failure does NOT change the job's
    overall `status` — the bundle is still downloadable.

    No connection configured → push_status='not_attempted'.
    """
    import httpx

    if not connection:
        supabase.table("digitisation_export_jobs").update({
            "push_status":        "not_attempted",
            "push_error":         "No default FHIR connection configured",
            "pushed_at":          datetime.now(tz=timezone.utc).isoformat(),
        }).eq("id", job_id).execute()
        return

    fhir_url = (connection.get("fhir_url") or "").rstrip("/")
    if not fhir_url:
        return

    # SSRF guard: workspace-supplied URL — refuse internal targets before POST.
    from app.core.url_safety import assert_safe_external_url, UnsafeURLError
    _ssrf_refused: Optional[str] = None
    try:
        assert_safe_external_url(fhir_url)
    except UnsafeURLError as e:
        _ssrf_refused = f"refused URL (SSRF guard): {e}"
        logger.warning(f"[export-worker] {_ssrf_refused}")

    headers = {
        "Content-Type": "application/fhir+json",
        "Accept":       "application/fhir+json,application/json",
    }
    creds = (connection.get("metadata") or {}).get("credentials") or {}
    if connection.get("auth_method") == "bearer" and creds.get("token"):
        headers["Authorization"] = f"Bearer {creds['token']}"

    pushed_at_iso = datetime.now(tz=timezone.utc).isoformat()
    status_code: Optional[int] = None
    error: Optional[str] = None
    ok = False
    try:
        if _ssrf_refused:
            error = _ssrf_refused
        else:
            with httpx.Client(timeout=30.0, follow_redirects=False) as client:
                r = client.post(fhir_url, headers=headers, content=bundle_content)
            status_code = r.status_code
            # FHIR transaction success: 200 OK with OperationOutcome bundle
            # response. 201/202 also acceptable for some servers.
            if 200 <= r.status_code < 300:
                ok = True
            else:
                error = f"HTTP {r.status_code}: {r.text[:200].strip()}"
    except httpx.ConnectError as e:
        error = f"Could not reach {fhir_url}: {e}"
    except httpx.TimeoutException:
        error = f"Timeout after 30s pushing to {fhir_url}"
    except Exception as e:
        error = f"{type(e).__name__}: {e}"

    supabase.table("digitisation_export_jobs").update({
        "push_status":        "success" if ok else "failed",
        "push_status_code":   status_code,
        "push_error":         error,
        "pushed_at":          pushed_at_iso,
        "push_connection_id": connection.get("id"),
    }).eq("id", job_id).execute()
    logger.info(
        f"[export-worker] push to {fhir_url}: "
        f"{'OK' if ok else 'FAIL'} ({status_code}) {error or ''}"
    )


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
        # extraction uses 'sex'; FHIR wants gender (DS-EXPORT-2)
        "gender":        demo.get("gender") or demo.get("sex"),
        "contact_number": demo.get("telephone_cell") or demo.get("cell_number") or demo.get("phone"),
        "email":         demo.get("email"),
        "address":       demo.get("address") or demo.get("home_address") or demo.get("postal_address"),
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
    coverage    = (extractions or {}).get("medical_aid") or None  # DS-EXPORT-3

    bundle = build_patient_bundle(
        patient_row=patient_row,
        allergies=allergies,
        diagnoses=diagnoses,
        medications=medications,
        vitals=vitals,
        encounters=encounters,
        coverage=coverage,
    )
    return bundle.model_dump(by_alias=True, exclude_none=True, mode="json")


# ---------------------------------------------------------------------------
# CSV (long format) — one row per clinical record, keyed by document_id
# ---------------------------------------------------------------------------
# Customer-facing flat export for analysis / import into another system.
# Every row carries document_id + patient_name + patient_id_number so each
# clinical row is self-identifying; `record_type` discriminates the row.
# Reuses the same _adapt_* shaping as the FHIR path, so CSV and FHIR see
# identical data. Only fields actually present are emitted — never fabricated.

CSV_COLUMNS = [
    "document_id", "record_type", "sequence",
    "patient_name", "patient_id_number", "date",
    "code", "description", "status",
    "dosage", "frequency", "duration", "quantity", "generic_name",
    "temperature_c", "heart_rate", "bp_systolic", "bp_diastolic",
    "oxygen_saturation", "weight_kg", "bmi", "hba1c", "blood_glucose_fasting",
    "gender", "date_of_birth", "contact_number", "email", "address",
    "medical_aid_scheme", "medical_aid_number", "medical_aid_plan",
]


def _csv_rows_for_document(
    doc_id: str, extractions: Dict[str, Any], flags: Dict[str, bool],
) -> List[Dict[str, Any]]:
    """Long-format rows for one document's validated extractions."""
    patient = _adapt_patient(extractions, doc_id)
    pname = " ".join(x for x in [patient.get("first_name"), patient.get("last_name")] if x) or None
    pid = patient.get("id_number")

    def base(record_type: str) -> Dict[str, Any]:
        return {
            "document_id": doc_id,
            "record_type": record_type,
            "patient_name": pname,
            "patient_id_number": pid,
        }

    rows: List[Dict[str, Any]] = []

    # Patient (always — patient is the Bundle subject)
    rows.append({
        **base("patient"),
        "description":    pname,
        "gender":         patient.get("gender"),
        "date_of_birth":  patient.get("date_of_birth"),
        "contact_number": patient.get("contact_number"),
        "email":          patient.get("email"),
        "address":        patient.get("address"),
    })

    # Medical aid / coverage
    ma = (extractions or {}).get("medical_aid")
    if isinstance(ma, dict) and ma:
        rows.append({
            **base("medical_aid"),
            "medical_aid_scheme": ma.get("scheme_name") or ma.get("name") or ma.get("medical_aid"),
            "medical_aid_number": ma.get("member_number"),
            "medical_aid_plan":   ma.get("plan"),
        })

    if flags["allergies"]:
        for i, a in enumerate(_adapt_allergies(extractions, doc_id)):
            rows.append({**base("allergy"), "sequence": i,
                         "description": a.get("substance"), "status": a.get("status")})
    if flags["diagnoses"]:
        for i, d in enumerate(_adapt_diagnoses(extractions, doc_id)):
            rows.append({**base("diagnosis"), "sequence": i, "code": d.get("icd10_code"),
                         "description": d.get("description"), "status": d.get("status"),
                         "date": d.get("created_at")})
    if flags["medications"]:
        for i, m in enumerate(_adapt_medications(extractions, doc_id)):
            rows.append({**base("medication"), "sequence": i, "code": m.get("nappi_code"),
                         "description": m.get("medication_name"), "status": m.get("status"),
                         "dosage": m.get("dosage"), "frequency": m.get("frequency"),
                         "duration": m.get("duration"), "quantity": m.get("quantity"),
                         "generic_name": m.get("generic_name")})
    if flags["vitals"]:
        for i, v in enumerate(_adapt_vitals(extractions, doc_id)):
            rows.append({**base("vital"), "sequence": i, "date": v.get("consultation_date"),
                         "temperature_c": v.get("temperature_c"), "heart_rate": v.get("heart_rate"),
                         "bp_systolic": v.get("bp_systolic"), "bp_diastolic": v.get("bp_diastolic"),
                         "oxygen_saturation": v.get("oxygen_saturation"), "weight_kg": v.get("weight_kg"),
                         "bmi": v.get("bmi"), "hba1c": v.get("hba1c"),
                         "blood_glucose_fasting": v.get("blood_glucose_fasting")})
    if flags["encounters"]:
        for i, e in enumerate(_adapt_encounters(extractions, doc_id)):
            rows.append({**base("encounter"), "sequence": i, "date": e.get("consultation_date"),
                         "description": e.get("type"), "status": e.get("status")})
    return rows


def build_records_csv(all_rows: List[Dict[str, Any]]) -> str:
    """Serialise long-format rows to a CSV string with the fixed header.
    Unknown keys are ignored; missing keys render as blank cells."""
    import csv
    import io
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for row in all_rows:
        writer.writerow(row)
    return buf.getvalue()


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
        fmt = (job.get("format") or "fhir_r4").lower()

        # 4. Per-document mapping. CSV and FHIR share the fetch + the _adapt_*
        # shaping; they differ only in how each document's data is emitted.
        per_doc_bundles: List[Dict[str, Any]] = []
        csv_rows: List[Dict[str, Any]] = []
        mapped_count = 0
        failed_docs: List[Tuple[str, str]] = []
        for doc_id in document_ids:
            try:
                vs = (
                    supabase.table("gp_validation_sessions")
                    .select("extractions")
                    .eq("document_id", doc_id)
                    .eq("workspace_id", workspace_id)  # defense-in-depth: never bundle another tenant's session (DS-EXPORT-1)
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )
                if not vs.data:
                    failed_docs.append((doc_id, "no validation session found"))
                    continue
                extractions = vs.data[0].get("extractions") or {}
                if fmt == "csv":
                    csv_rows.extend(_csv_rows_for_document(doc_id, extractions, flags))
                else:
                    per_doc_bundles.append(_bundle_for_document(doc_id, extractions, flags))
                mapped_count += 1
            except Exception as e:
                logger.warning(f"[export-worker] doc {doc_id} mapping failed: {e}")
                failed_docs.append((doc_id, str(e)))

        # 5. Build + write the artifact (Supabase Storage with local-disk fallback)
        if fmt == "csv":
            content = build_records_csv(csv_rows)
        else:
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
            content = json.dumps(outer_bundle, indent=2)

        storage_loc = _store_bundle(
            supabase, workspace_id, job["batch_id"], content,
            ext=_ext_for_format(fmt), content_type=_content_type_for_format(fmt),
        )

        # Phase C — auto-POST to the workspace's default FHIR connection.
        # Only meaningful for FHIR; a CSV is a customer download, not an EHR
        # transaction, so we never push it to a FHIR server.
        if fmt in ("fhir_r4", "json"):
            _attempt_push(supabase, job_id, workspace_id, content, connection)

        # 6. Final status
        completed_iso = datetime.now(tz=timezone.utc).isoformat()
        if mapped_count == 0:
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
            f"[export-worker] job {job_id} {final_status} ({fmt}): "
            f"{mapped_count}/{len(document_ids)} documents → {storage_loc}"
        )

    except Exception as e:
        logger.error(f"[export-worker] job {job_id} crashed: {e}\n{traceback.format_exc()}")
        supabase.table("digitisation_export_jobs").update({
            "status":        "failed",
            "error_message": f"{type(e).__name__}: {e}",
            "completed_at":  datetime.now(tz=timezone.utc).isoformat(),
        }).eq("id", job_id).execute()
