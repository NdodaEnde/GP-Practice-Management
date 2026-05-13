"""
extraction_promoter — promotion of validated digitisation extractions
into the structured EHR tables.

PR 2 transition
---------------

The heavy lifting (ICD-10 lookups, NAPPI lookups, patient match/create,
encounter creation, wipe-and-rewrite idempotency, per-row inserts) now
lives in PL/pgSQL — see backend/migrations/015_extraction_promoter_plpgsql.sql.
The Python `promote_extractions()` function below is a thin RPC-dispatch
shim retained for one PR cycle. It raises DeprecationWarning so any
remaining caller surfaces in test logs.

PR 3 removes this module entirely. The remaining helpers
(`find_match_candidates`, `_match_or_create_patient`, `_normalise_date`,
`_summarise_patient`) are kept because the /preview-match endpoint
calls them directly to render candidates before approval commits.

What was deleted in PR 2
------------------------

`_wipe_prior_promotion`, `_create_encounters`, `_promote_diagnoses`,
`_promote_medications`, `_promote_vitals`, `_promote_allergies`,
`_resolve_icd10`, `_resolve_nappi`, `_InferenceCache`,
`ICD10_ABBREVIATIONS`, `_encounter_for_row`, `_collect_consultation_dates`,
`_delete_prior`, `_now_iso`, `_new_id`, `_coerce_int`, `_coerce_float`,
`_normalise_severity`, `_allergy_substances`.

All of these had Python-layer correlates in the PL/pgSQL port. The
ICD10_ABBREVIATIONS dict became `icd10_abbreviations` table (seeded by
migration 016).
"""

from __future__ import annotations

import logging
import uuid
import warnings
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class PromotionResult:
    """What landed where after a promote_extractions call.

    Mirrors the JSONB return shape of the PL/pgSQL RPC
    execute_action_promote_document. The test
    test_promote_rpc_return_shape_matches_promotion_result asserts the
    field names stay in sync.
    """
    patient_id:    str
    patient_kind:  str                       # 'matched' | 'matched_explicit' | 'created'
    match_confidence: str = "n/a"            # 'id_number' | 'name_dob' | 'explicit' | 'n/a'
    patient_summary: Optional[Dict[str, Any]] = None
    encounter_ids: List[str]               = field(default_factory=list)
    counts:        Dict[str, int]          = field(default_factory=dict)
    warnings:      List[str]               = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "patient_id":       self.patient_id,
            "patient_kind":     self.patient_kind,
            "match_confidence": self.match_confidence,
            "patient_summary":  self.patient_summary,
            "encounter_ids":    self.encounter_ids,
            "counts":           self.counts,
            "warnings":         self.warnings,
        }

    @classmethod
    def from_rpc_payload(cls, payload: Dict[str, Any]) -> "PromotionResult":
        """Reconstruct from the JSONB the PL/pgSQL RPC returns. Ignores
        affected_objects — that's consumed separately by the ActionExecutor."""
        return cls(
            patient_id=payload.get("patient_id"),
            patient_kind=payload.get("patient_kind"),
            match_confidence=payload.get("match_confidence", "n/a"),
            patient_summary=payload.get("patient_summary"),
            encounter_ids=list(payload.get("encounter_ids") or []),
            counts=dict(payload.get("counts") or {}),
            warnings=list(payload.get("warnings") or []),
        )


# ---------------------------------------------------------------------------
# Helpers kept for the /preview-match endpoint
# ---------------------------------------------------------------------------

def _normalise_date(raw: Any) -> Optional[str]:
    """Best-effort YYYY-MM-DD. Accepts date, datetime, ISO strings, or
    common SA formats (DD/MM/YYYY). Returns None when unparseable.

    Kept in Python because /preview-match calls it directly to normalise
    the demographic blob before searching candidate patients.
    """
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


def _split_full_name(full: Optional[str]) -> Tuple[str, str]:
    """Returns (first_name, middle_or_remaining)."""
    if not full:
        return "Unknown", ""
    parts = str(full).strip().split()
    if not parts:
        return "Unknown", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def _summarise_patient(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "first_name": row.get("first_name"),
        "last_name":  row.get("last_name"),
        "dob":        row.get("dob"),
        "id_number":  row.get("id_number"),
    }


def _tenant_for_workspace(supabase, workspace_id: str) -> str:
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


# ---------------------------------------------------------------------------
# Patient match — exposed for /preview-match endpoint
# ---------------------------------------------------------------------------

def find_match_candidates(
    supabase, workspace_id: str, demographics: Dict[str, Any], limit: int = 5,
) -> List[Dict[str, Any]]:
    """Returns ALL candidate patient matches (not just the first). Each
    row has match_kind = 'id_number' | 'name_dob' so the caller can show
    confidence per row in the UI. Used by the /preview-match endpoint
    so reviewers can choose explicitly before approval commits.

    Order: id_number matches first (highest confidence), then name_dob.
    Deduped by patient id.
    """
    id_number = (demographics.get("id_number") or "").strip()
    surname   = (demographics.get("surname")   or "").strip()
    dob       = _normalise_date(demographics.get("date_of_birth"))

    seen: set = set()
    out: List[Dict[str, Any]] = []
    cols = "id, first_name, last_name, id_number, dob, contact_number, medical_aid, created_at"

    if id_number:
        res = (
            supabase.table("patients")
            .select(cols)
            .eq("workspace_id", workspace_id)
            .eq("id_number", id_number)
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


def _match_or_create_patient(
    supabase, workspace_id: str, demographics: Dict[str, Any],
    *,
    forced_patient_id: Optional[str] = None,
    force_create: bool = False,
) -> Tuple[str, str, str, Dict[str, Any]]:
    """Returns (patient_id, kind, match_confidence, patient_summary).

    Kept for the /preview-match endpoint's "what would happen if I
    approved now" preview. The promote-document RPC has its own
    PL/pgSQL implementation of the same logic — kept in sync by the
    test_promote_rpc_match_or_create_parity test (verification §7).
    """
    if forced_patient_id:
        res = (
            supabase.table("patients")
            .select("id, first_name, last_name, id_number, dob")
            .eq("workspace_id", workspace_id)
            .eq("id", forced_patient_id)
            .limit(1)
            .execute()
        )
        if not res.data:
            raise RuntimeError(
                f"forced_patient_id {forced_patient_id} not found in workspace {workspace_id}"
            )
        return res.data[0]["id"], "matched_explicit", "explicit", _summarise_patient(res.data[0])

    if not force_create:
        candidates = find_match_candidates(supabase, workspace_id, demographics, limit=2)
        if candidates:
            r = candidates[0]
            summary = _summarise_patient(r)
            confidence = r["match_kind"]
            if len(candidates) > 1:
                summary["ambiguous"] = True
                summary["other_candidates"] = len(candidates) - 1
            return r["id"], "matched", confidence, summary

    first_name, _ = _split_full_name(demographics.get("full_names"))
    last_name = demographics.get("surname") or "Unknown"
    medical_aid_blob = (demographics.get("medical_aid")
                        or demographics.get("scheme_name") or None)

    new_id = str(uuid.uuid4())
    tenant_id = _tenant_for_workspace(supabase, workspace_id)
    row = {
        "id":             new_id,
        "tenant_id":      tenant_id,
        "workspace_id":   workspace_id,
        "first_name":     first_name,
        "last_name":      last_name,
        "dob":            _normalise_date(demographics.get("date_of_birth")) or "1900-01-01",
        "id_number":      demographics.get("id_number") or f"unknown-{new_id[:8]}",
        "contact_number": demographics.get("telephone_cell") or demographics.get("phone"),
        "email":          demographics.get("email"),
        "address":        demographics.get("address"),
        "medical_aid":    medical_aid_blob,
    }
    supabase.table("patients").insert(row).execute()
    logger.info(f"[promoter] /preview-match created patient {new_id} in workspace {workspace_id}")
    return new_id, "created", "n/a", _summarise_patient(row)


# ---------------------------------------------------------------------------
# promote_extractions() — RPC-dispatch shim (PR 2 transitional)
# ---------------------------------------------------------------------------

def promote_extractions(
    supabase,
    *,
    workspace_id: str,
    document_id: str,
    extractions: Dict[str, Any],
    created_by: Optional[str] = None,
    forced_patient_id: Optional[str] = None,
    force_create_patient: bool = False,
) -> PromotionResult:
    """DEPRECATED — dispatch to execute_action_promote_document RPC.

    PR 2 keeps this entry point for ONE PR cycle in case any third caller
    appears during the rollout. Real callers should go through the
    ActionExecutor pathway (PromoteDocumentToPatientRecord action) so
    every promotion lands in action_audit_log.

    DeprecationWarning fires on every call. PR 3 will delete this
    function — at which point any forgotten callsite becomes a test
    failure, not silent breakage.
    """
    warnings.warn(
        "promote_extractions() is deprecated. Route through the "
        "ActionExecutor (PromoteDocumentToPatientRecord) so every "
        "promotion is audited. This shim will be removed in PR 3.",
        DeprecationWarning,
        stacklevel=2,
    )

    response = supabase.rpc(
        "execute_action_promote_document",
        {
            "p_document_id":          document_id,
            "p_workspace_id":         workspace_id,
            "p_extractions":          extractions or {},
            "p_created_by":           created_by or "promoter",
            "p_forced_patient_id":    forced_patient_id,
            "p_force_create_patient": force_create_patient,
        },
    ).execute()

    payload = response.data if hasattr(response, "data") else response
    if not isinstance(payload, dict):
        raise RuntimeError(
            f"execute_action_promote_document returned unexpected payload "
            f"type {type(payload).__name__}"
        )
    return PromotionResult.from_rpc_payload(payload)
