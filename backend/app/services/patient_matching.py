"""
patient_matching — helpers for the /preview-match endpoint and any
future "what would happen if I approved now" preview flow.

PR 3 extracted these from the deprecated `extraction_promoter.py`
module. The promote-document RPC (migration 015) has its own PL/pgSQL
implementation of the same match logic that runs inside the
single-transaction promote pipeline; these Python helpers serve the
read-only preview path that runs BEFORE the user clicks approve.

The two implementations must stay aligned:
- ICD-10 / NAPPI inference parity is enforced by
  test_icd10_and_nappi_lookups_match_python_behaviour (PR 2).
- Patient match parity is enforced by manual review during PR 3
  development; a CI test (TODO post-PR 3) would assert the Python
  resolver and the PL/pgSQL resolver pick the same patient for a
  given demographic blob.

PR 3 also added a `WHERE deleted_at IS NULL` filter to
find_match_candidates so soft-deleted patients are invisible to the
match preview. The promote-document RPC has the equivalent filter
through `_promote_doc_resolve_patient_match` (migration 015) —
verify a future patient_admin who soft-deleted a patient doesn't
see them re-appear when approving a fresh document.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# Date / string utilities
# ----------------------------------------------------------------------------

def normalise_date(raw: Any) -> Optional[str]:
    """Best-effort YYYY-MM-DD. Accepts date, datetime, ISO strings, or
    common SA formats (DD/MM/YYYY)."""
    if raw is None or raw == "":
        return None
    if isinstance(raw, (date, datetime)):
        return raw.strftime("%Y-%m-%d")
    s = str(raw).strip()
    if len(s) >= 10 and s[4] == '-' and s[7] == '-':
        return s[:10]
    for sep in ("/", "-"):
        if s.count(sep) == 2:
            parts = s.split(sep)
            if len(parts) == 3 and len(parts[2]) == 4:
                d, m, y = parts
                try:
                    return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
                except ValueError:
                    pass
    return None


def split_full_name(full: Optional[str]) -> Tuple[str, str]:
    """Returns (first_name, middle_or_remaining)."""
    if not full:
        return "Unknown", ""
    parts = str(full).strip().split()
    if not parts:
        return "Unknown", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def summarise_patient(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "first_name": row.get("first_name"),
        "last_name":  row.get("last_name"),
        "dob":        row.get("dob"),
        "id_number":  row.get("id_number"),
    }


def tenant_for_workspace(supabase, workspace_id: str) -> str:
    res = (
        supabase.table("workspaces")
        .select("tenant_id")
        .eq("id", workspace_id)
        .limit(1)
        .execute()
    )
    if not res.data:
        raise RuntimeError(f"Workspace {workspace_id} not found in workspaces table")
    return res.data[0]["tenant_id"]


# ----------------------------------------------------------------------------
# Patient match — exposed for /preview-match
# ----------------------------------------------------------------------------

def find_match_candidates(
    supabase, workspace_id: str, demographics: Dict[str, Any], limit: int = 5,
) -> List[Dict[str, Any]]:
    """Returns ALL candidate patient matches with match_kind labels.

    Tier 1: SA ID exact match. Tier 2: surname (ILIKE) + dob (exact).
    Deduped by patient id. Soft-deleted patients (deleted_at IS NOT NULL,
    added by migration 020) are excluded.
    """
    id_number = (demographics.get("id_number") or "").strip()
    surname   = (demographics.get("surname")   or "").strip()
    dob       = normalise_date(demographics.get("date_of_birth"))

    seen: set = set()
    out: List[Dict[str, Any]] = []
    cols = "id, first_name, last_name, id_number, dob, contact_number, medical_aid, created_at"

    if id_number:
        res = (
            supabase.table("patients")
            .select(cols)
            .eq("workspace_id", workspace_id)
            .eq("id_number", id_number)
            .is_("deleted_at", "null")
            .limit(limit)
            .execute()
        )
        for r in res.data or []:
            if r["id"] in seen:
                continue
            seen.add(r["id"])
            out.append({**r, "match_kind": "id_number"})

    if surname and dob and len(out) < limit:
        res = (
            supabase.table("patients")
            .select(cols)
            .eq("workspace_id", workspace_id)
            .ilike("last_name", surname)
            .eq("dob", dob)
            .is_("deleted_at", "null")
            .limit(limit)
            .execute()
        )
        for r in res.data or []:
            if r["id"] in seen:
                continue
            seen.add(r["id"])
            out.append({**r, "match_kind": "name_dob"})
            if len(out) >= limit:
                break
    return out


def match_or_create_patient(
    supabase, workspace_id: str, demographics: Dict[str, Any],
    *,
    forced_patient_id: Optional[str] = None,
    force_create: bool = False,
) -> Tuple[str, str, str, Dict[str, Any]]:
    """Returns (patient_id, kind, match_confidence, patient_summary).

    Used by /preview-match for the "what would happen if I approved now"
    preview. The actual promote-document RPC has its own equivalent
    inside the single-transaction pipeline."""
    if forced_patient_id:
        res = (
            supabase.table("patients")
            .select("id, first_name, last_name, id_number, dob")
            .eq("workspace_id", workspace_id)
            .eq("id", forced_patient_id)
            .is_("deleted_at", "null")
            .limit(1)
            .execute()
        )
        if not res.data:
            raise RuntimeError(
                f"forced_patient_id {forced_patient_id} not found / soft-deleted "
                f"in workspace {workspace_id}"
            )
        return res.data[0]["id"], "matched_explicit", "explicit", summarise_patient(res.data[0])

    if not force_create:
        candidates = find_match_candidates(supabase, workspace_id, demographics, limit=2)
        if candidates:
            r = candidates[0]
            summary = summarise_patient(r)
            confidence = r["match_kind"]
            if len(candidates) > 1:
                summary["ambiguous"] = True
                summary["other_candidates"] = len(candidates) - 1
            return r["id"], "matched", confidence, summary

    first_name, _ = split_full_name(demographics.get("full_names"))
    last_name = demographics.get("surname") or "Unknown"
    medical_aid_blob = (demographics.get("medical_aid")
                        or demographics.get("scheme_name") or None)

    new_id = str(uuid.uuid4())
    tenant_id = tenant_for_workspace(supabase, workspace_id)
    row = {
        "id":             new_id,
        "tenant_id":      tenant_id,
        "workspace_id":   workspace_id,
        "first_name":     first_name,
        "last_name":      last_name,
        "dob":            normalise_date(demographics.get("date_of_birth")) or "1900-01-01",
        "id_number":      demographics.get("id_number") or f"unknown-{new_id[:8]}",
        "contact_number": demographics.get("telephone_cell") or demographics.get("phone"),
        "email":          demographics.get("email"),
        "address":        demographics.get("address"),
        "medical_aid":    medical_aid_blob,
    }
    supabase.table("patients").insert(row).execute()
    logger.info(f"[patient_matching] /preview-match created patient {new_id} in workspace {workspace_id}")
    return new_id, "created", "n/a", summarise_patient(row)
