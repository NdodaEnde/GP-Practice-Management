"""
extraction_promoter — promote validated digitisation extractions into the
structured EHR tables (patients, encounters, allergies, diagnoses, vitals,
prescriptions / prescription_items) so analytics, patient-EHR views,
drug-class breakdowns, and DDI checks can see the data.

Without this, validated extractions live forever in
gp_validation_sessions.extractions JSONB and never reach the relational
tables. This is why /analytics shows empty cohorts, why the patient
EHR view of digitised patients is blank, and why drug-class analytics
only sees pharmacy-originated prescriptions.

Triggered from /api/digitisation/validation/{document_id}/approve.

Design:
  - Idempotent. Every promoted row is stamped source_document_id =
    digitised_documents.id. Re-running for the same doc deletes the
    prior set first, then re-inserts. No duplicates.
  - Patient match-or-create:
      1. exact match on (workspace_id, id_number) when SA ID present
      2. fuzzy match on (workspace_id, lower(first_name+surname), dob)
      3. create new
  - One encounter per unique consultation_date found across the
    extractions (with a fallback "today" encounter when there are no
    dates).
  - Each downstream row (diagnosis, vital, medication, ...) is linked
    to the encounter whose date matches its consultation_date, falling
    back to the first encounter when there's no date or no match.

Failure mode: any step failing rolls the whole promotion back via
explicit deletes — better to leave the doc unpromoted than half-
promoted.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# ICD-10 abbreviation lexicon
# ---------------------------------------------------------------------------
# Curated SA-GP shorthand seen in handwritten / typed clinical notes.
# Maps the lowercased extracted description to the WHO ICD-10 code that's
# the most clinically common interpretation. Reviewers can edit any
# resolved code in the patient EHR after promotion. The lookup is:
#     1. exact normalized match in this map  (high confidence)
#     2. ilike search against icd10_codes.who_full_desc (medium)
#     3. None → diagnosis row gets code=NULL
#
# Add entries here as a free way to lift inference quality. Order:
# alphabetical by abbreviation. Comments give the WHO description.

ICD10_ABBREVIATIONS: Dict[str, str] = {
    # NB: codes here MUST exist in the live `icd10_codes` table. The SA
    # WHO ICD-10 dataset uses 3- or 4-character codes (J45 not J45.9 in
    # some chapters; .9 = "unspecified" form where it exists). When a
    # mapped code is missing from the table the lookup falls through to
    # Tier 2 fuzzy or returns None.

    # respiratory
    "urti":       "J06.9",
    "urfi":       "J06.9",
    "urt":        "J06.9",
    "lrti":       "J22",
    "asthma":     "J45.9",
    "copd":       "J44.9",
    "bronchitis": "J40",
    "pneumonia":  "J18.9",
    "tonsillitis":"J03.9",
    "pharyngitis":"J02.9",
    "sinusitis":  "J32.9",
    "otitis media":"H66.9",
    "om":         "H66.9",
    "dyspnea":    "R06.0",
    "dyspnoea":   "R06.0",
    "cough":      "R05",

    # cardiovascular
    "hpt":        "I10",
    "htn":        "I10",
    "hypertension":"I10",
    "ihd":        "I25.9",
    "cva":        "I63.9",
    "tia":        "G45.9",
    "afib":       "I48",
    "af":         "I48",
    "chf":        "I50.9",
    "heart failure":"I50.9",

    # endocrine
    "dm":         "E11.9",
    "t2dm":       "E11.9",
    "t1dm":       "E10.9",
    "diabetes":   "E11.9",
    "thyroid":    "E07.9",
    "hypothyroid":"E03.9",
    "hyperthyroid":"E05.9",

    # gastrointestinal
    "gerd":       "K21.9",
    "gord":       "K21.9",
    "ibs":        "K58.9",
    "gastritis":  "K29.7",
    "constipation":"K59.0",
    "diarrhea":   "A09",
    "diarrhoea":  "A09",

    # musculoskeletal
    "arthritis":  "M13.9",   # other arthritis, unspecified
    "ra":         "M06.9",
    "oa":         "M19.9",   # other arthrosis, unspecified site
    "back pain":  "M54.9",
    "lbp":        "M54.5",
    "low back pain":"M54.5",
    "myalgia":    "M79.1",

    # neuro
    "headache":   "G44",     # "Other headache syndromes" — broadest available
    "migraine":   "G43",
    "vertigo":    "R42",
    "epilepsy":   "G40.9",

    # genitourinary
    "uti":        "N39.0",
    "cystitis":   "N30.9",
    "bph":        "N40",

    # infections
    "hiv":        "B20",
    "tb":         "A15.9",
    "tuberculosis":"A15.9",
    "malaria":    "B54",

    # mental
    "depression": "F32.9",
    "anxiety":    "F41.9",
    "gad":        "F41.1",

    # symptoms / signs
    "pyrexia":    "R50.9",
    "fever":      "R50.9",
    "anaemia":    "D64.9",
    "anemia":     "D64.9",
    "fatigue":    "R53",
    "vomiting":   "R11",
    "nausea":     "R11",
    "rash":       "R21",

    # mother/child / OB
    "pregnancy":  "Z34.9",
    "antenatal":  "Z34.9",
    "labour":     "O80",
    "well child": "Z00.1",
}


# ---------------------------------------------------------------------------
# Inference cache — populated once per promote_extractions call to avoid
# round-tripping the same lookup multiple times.
# ---------------------------------------------------------------------------

@dataclass
class _InferenceCache:
    """One per promotion run. Memoises icd10/nappi lookups so a doc with
    7 paracetamol prescriptions only hits the DB once."""
    icd10: Dict[str, Optional[Tuple[str, str]]] = field(default_factory=dict)   # key = normalised desc
    nappi: Dict[str, Optional[Dict[str, Any]]] = field(default_factory=dict)    # key = normalised drug name


def _norm_text(s: str) -> str:
    """Loose normalisation for lookup keys."""
    if not s:
        return ""
    return " ".join(str(s).lower().strip().split())


def _resolve_icd10(
    supabase, description: str, cache: _InferenceCache
) -> Optional[Tuple[str, str]]:
    """Returns (code, who_full_desc) or None.
    Lookup tiers:
      1. ICD10_ABBREVIATIONS map (exact normalised match)
      2. icd10_codes.who_full_desc ilike search (top result if non-ambiguous)
    """
    if not description:
        return None
    key = _norm_text(description)
    if key in cache.icd10:
        return cache.icd10[key]

    # Tier 1 — abbreviation map
    if key in ICD10_ABBREVIATIONS:
        code = ICD10_ABBREVIATIONS[key]
        try:
            res = (
                supabase.table("icd10_codes")
                .select("code, who_full_desc")
                .eq("code", code)
                .limit(1)
                .execute()
            )
            if res.data:
                hit = (res.data[0]["code"], res.data[0]["who_full_desc"])
                cache.icd10[key] = hit
                return hit
        except Exception as e:
            logger.warning(f"[promoter] icd10 abbr lookup for {code} failed: {e}")
        # Code present in the map but missing from the table — fall through
        # rather than return a code that won't validate
        cache.icd10[key] = None
        return None

    # Tier 2 — fuzzy. Only safe to attempt when the input is a multi-word
    # phrase (≥ 2 tokens) OR a single longish token (≥ 10 chars). For short
    # abbreviations like "Arthrog" or "URTI", substring search against ICD
    # descriptions is a false-positive magnet (e.g. "Arthrog%" → Q74.3
    # "Arthrogryposis multiplex congenita"). When the abbreviation map
    # didn't catch them, just return None — better to leave a NULL than
    # a wrong code.
    if len(description.strip()) < 10 and " " not in description.strip():
        cache.icd10[key] = None
        return None

    try:
        res = (
            supabase.table("icd10_codes")
            .select("code, who_full_desc")
            .ilike("who_full_desc", f"%{description.strip()}%")
            .eq("valid_clinical_use", True)
            .limit(2)
            .execute()
        )
        rows = res.data or []
        if len(rows) == 1:
            hit = (rows[0]["code"], rows[0]["who_full_desc"])
            cache.icd10[key] = hit
            return hit
    except Exception as e:
        logger.warning(f"[promoter] icd10 fuzzy lookup for {description!r} failed: {e}")

    cache.icd10[key] = None
    return None


def _resolve_nappi(
    supabase, drug_name: str, cache: _InferenceCache
) -> Optional[Dict[str, Any]]:
    """Returns {nappi_code, atc_code, atc_class_desc, generic_name, brand_name}
    or None. Uses the existing nappi_codes table — covers both real_nappi rows
    and curated OTCs (CURATED-* synthetic IDs).

    Lookup tiers:
      1. exact ilike match on brand_name
      2. exact ilike match on generic_name
    """
    if not drug_name:
        return None
    key = _norm_text(drug_name)
    if key in cache.nappi:
        return cache.nappi[key]

    cleaned = drug_name.strip()
    cols = "nappi_code, brand_name, generic_name, atc_code, atc_class_desc"
    try:
        # Brand-first match (more specific)
        res = supabase.table("nappi_codes").select(cols).ilike("brand_name", cleaned).limit(1).execute()
        if not res.data:
            res = supabase.table("nappi_codes").select(cols).ilike("generic_name", cleaned).limit(1).execute()
        if res.data:
            cache.nappi[key] = res.data[0]
            return res.data[0]
    except Exception as e:
        logger.warning(f"[promoter] nappi lookup for {drug_name!r} failed: {e}")

    cache.nappi[key] = None
    return None


@dataclass
class PromotionResult:
    """What landed where after a promote_extractions call."""
    patient_id:    str
    patient_kind:  str                       # 'matched' | 'created'
    match_confidence: str = "n/a"            # 'id_number' | 'name_dob' | 'n/a' (created)
    patient_summary: Optional[Dict[str, Any]] = None    # name, dob, id_number — for reviewer visibility
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


def _split_full_name(full: Optional[str]) -> Tuple[str, str]:
    """Returns (first_name, middle_or_remaining). Surname comes from a
    separate field — this handles 'first names' (SA convention)."""
    if not full:
        return "Unknown", ""
    parts = str(full).strip().split()
    if not parts:
        return "Unknown", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def _normalise_date(raw: Any) -> Optional[str]:
    """Best-effort YYYY-MM-DD. Accepts date, datetime, ISO strings, or
    common SA formats (DD/MM/YYYY). Returns None when unparseable."""
    if raw is None or raw == "":
        return None
    if isinstance(raw, (date, datetime)):
        return raw.strftime("%Y-%m-%d")
    s = str(raw).strip()
    # Already ISO?
    if len(s) >= 10 and s[4] == '-' and s[7] == '-':
        return s[:10]
    # DD/MM/YYYY or DD-MM-YYYY
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


def _coerce_int(raw: Any) -> Optional[int]:
    if raw is None or raw == "":
        return None
    try:
        return int(float(str(raw).strip()))
    except (TypeError, ValueError):
        return None


def _coerce_float(raw: Any) -> Optional[float]:
    if raw is None or raw == "":
        return None
    try:
        return float(str(raw).strip())
    except (TypeError, ValueError):
        return None


def _normalise_severity(raw: Any) -> Optional[str]:
    if not raw:
        return None
    r = str(raw).strip().lower()
    if "life" in r or "anaphyl" in r:
        return "life_threatening"
    if "severe" in r:
        return "severe"
    if "moderate" in r:
        return "moderate"
    if "mild" in r:
        return "mild"
    return "unknown"


def _allergy_substances(extractions: Dict[str, Any]) -> List[str]:
    hx = (extractions or {}).get("clinical_history") or {}
    raw = hx.get("known_allergies")
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if x and str(x).strip()]
    if isinstance(raw, str) and raw.strip():
        # Split on common separators, ignore "NKDA" / "none"
        if raw.strip().lower() in {"nkda", "none", "n/a", "no known allergies"}:
            return []
        out: List[str] = []
        for part in raw.replace(";", ",").replace("\n", ",").split(","):
            p = part.strip()
            if p:
                out.append(p)
        return out
    return []


# ---------------------------------------------------------------------------
# Patient match-or-create
# ---------------------------------------------------------------------------

def _match_patient(
    supabase, workspace_id: str, demographics: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Look for an existing patient. Returns the row dict or None."""
    id_number = (demographics.get("id_number") or "").strip()
    if id_number:
        res = (
            supabase.table("patients")
            .select("id, first_name, last_name, id_number, dob")
            .eq("workspace_id", workspace_id)
            .eq("id_number", id_number)
            .limit(1)
            .execute()
        )
        if res.data:
            return res.data[0]

    # Fuzzy fallback — same workspace + same surname + same dob
    surname = (demographics.get("surname") or "").strip()
    dob = _normalise_date(demographics.get("date_of_birth"))
    if surname and dob:
        res = (
            supabase.table("patients")
            .select("id, first_name, last_name, id_number, dob")
            .eq("workspace_id", workspace_id)
            .ilike("last_name", surname)
            .eq("dob", dob)
            .limit(5)
            .execute()
        )
        if res.data:
            # Prefer the first hit; reviewers can manually merge later.
            return res.data[0]
    return None


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

    # Tier 1 — SA ID number
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

    # Tier 2 — surname + DOB
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


def _summarise_patient(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "first_name": row.get("first_name"),
        "last_name":  row.get("last_name"),
        "dob":        row.get("dob"),
        "id_number":  row.get("id_number"),
    }


def _match_or_create_patient(
    supabase, workspace_id: str, demographics: Dict[str, Any],
    *,
    forced_patient_id: Optional[str] = None,
    force_create: bool = False,
) -> Tuple[str, str, str, Dict[str, Any]]:
    """Returns (patient_id, kind, match_confidence, patient_summary).

    Override-aware:
      - forced_patient_id: skip auto-match; use this exact id (expects
        the caller to have validated it exists in the workspace).
      - force_create: skip auto-match; create a new patient even if
        matches exist.
      - neither set: original behaviour (Tier 1 → Tier 2 → create).

    kind = 'matched' | 'matched_explicit' | 'created'.
    match_confidence = 'id_number' | 'name_dob' | 'explicit' | 'n/a'.
    """
    # Caller-forced explicit patient
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

    # Caller-forced "create even if there are matches"
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

    # Either force_create=True OR no candidates — create
    first_name, _ = _split_full_name(demographics.get("full_names"))
    last_name = demographics.get("surname") or "Unknown"
    medical_aid_blob = (demographics.get("medical_aid")
                        or demographics.get("scheme_name") or None)

    new_id = _new_id()
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
    logger.info(f"[promoter] created patient {new_id} in workspace {workspace_id}")
    return new_id, "created", "n/a", {
        "first_name": row["first_name"],
        "last_name":  row["last_name"],
        "dob":        row["dob"],
        "id_number":  row["id_number"],
    }


# ---------------------------------------------------------------------------
# Encounter shaping
# ---------------------------------------------------------------------------

def _collect_consultation_dates(extractions: Dict[str, Any]) -> List[str]:
    """All distinct consultation_date strings found across the extraction.
    Sorted. Empty + unparseable dates excluded."""
    dates: set = set()
    for section in ("vitals_history", "diagnoses", "medications",
                    "investigations", "referrals", "progress_notes"):
        for row in (extractions or {}).get(section) or []:
            d = _normalise_date(row.get("consultation_date") or row.get("date"))
            if d:
                dates.add(d)
    return sorted(dates)


def _wipe_prior_promotion(supabase, document_id: str) -> None:
    """Delete every previously-promoted row for this document, in reverse
    FK order. Called once at the start of promote_extractions so individual
    per-table inserts can run cleanly without order-of-deletion FK failures.

    Order: prescription_items → prescriptions → diagnoses → vitals →
    allergies → encounters. (patients are NOT deleted — they may be
    shared across documents and cleaning up "orphaned" patients is a
    separate concern.)

    digitised_documents.encounter_id and patient_id are also unlinked
    BEFORE the encounters delete; without that, the doc's own FK back
    to its first-encounter blocks the encounters wipe and the row count
    silently doubles on retry.
    """
    # 1. Break the digitised_documents → encounters FK so we can delete
    #    encounters cleanly. patient_id is left intact — patients aren't
    #    wiped during promotion (they can be re-found by match logic).
    try:
        supabase.table("digitised_documents") \
            .update({"encounter_id": None}) \
            .eq("id", document_id) \
            .execute()
    except Exception as e:
        logger.warning(f"[promoter] could not null doc.encounter_id for {document_id[:8]}: {e}")

    # 2. prescription_items don't have source_document_id — wipe via parent FK
    prior_rxs = (
        supabase.table("prescriptions")
        .select("id")
        .eq("source_document_id", document_id)
        .execute()
    )
    prior_rx_ids = [r["id"] for r in (prior_rxs.data or [])]
    if prior_rx_ids:
        supabase.table("prescription_items") \
            .delete().in_("prescription_id", prior_rx_ids).execute()

    # 3. Delete in reverse FK order. Don't swallow errors — re-raise so
    #    the outer promote_extractions catches them and the API surfaces
    #    promotion_error instead of silently leaving stale rows behind.
    for tbl in ("prescriptions", "diagnoses", "vitals", "allergies", "encounters"):
        supabase.table(tbl) \
            .delete().eq("source_document_id", document_id).execute()


def _create_encounters(
    supabase, workspace_id: str, patient_id: str,
    extractions: Dict[str, Any], document_id: str,
) -> Dict[str, str]:
    """One encounter per distinct consultation_date. Returns
    {date_iso: encounter_id}. Always creates at least one (today's
    encounter) when no dates exist."""
    dates = _collect_consultation_dates(extractions)
    if not dates:
        dates = [datetime.now(tz=timezone.utc).date().isoformat()]
    out: Dict[str, str] = {}
    for d in dates:
        eid = _new_id()
        row = {
            "id":                 eid,
            "patient_id":         patient_id,
            "workspace_id":       workspace_id,
            "encounter_date":     f"{d}T00:00:00+00:00",
            "status":             "completed",
            "chief_complaint":    None,
            "vitals_json":        None,
            "gp_notes":           f"Created from digitised document {document_id}",
            "source_document_id": document_id,
        }
        supabase.table("encounters").insert(row).execute()
        out[d] = eid
    return out


def _encounter_for_row(
    encounter_map: Dict[str, str], row: Dict[str, Any]
) -> str:
    """Pick the encounter for a downstream row by date match; fall back
    to the first encounter when no date or no match."""
    d = _normalise_date(row.get("consultation_date") or row.get("date"))
    if d and d in encounter_map:
        return encounter_map[d]
    # First (= earliest) encounter is the default
    return next(iter(encounter_map.values()))


# ---------------------------------------------------------------------------
# Per-category writers
# ---------------------------------------------------------------------------

def _delete_prior(supabase, table: str, document_id: str) -> int:
    """Idempotency: wipe rows previously promoted from this document."""
    res = (
        supabase.table(table)
        .delete()
        .eq("source_document_id", document_id)
        .execute()
    )
    return len(res.data or [])


def _promote_allergies(
    supabase, *, workspace_id: str, tenant_id: str, patient_id: str,
    extractions: Dict[str, Any], document_id: str, created_by: str,
) -> int:
    rows = []
    for substance in _allergy_substances(extractions):
        rows.append({
            "id":                 _new_id(),
            "tenant_id":          tenant_id,
            "workspace_id":       workspace_id,
            "patient_id":         patient_id,
            "substance":          substance,
            "status":             "active",
            "source":             "document_extraction",
            "source_document_id": document_id,
            "created_by":         created_by,
        })
    if rows:
        supabase.table("allergies").insert(rows).execute()
    return len(rows)


def _promote_diagnoses(
    supabase, *, workspace_id: str, tenant_id: str, patient_id: str,
    encounter_map: Dict[str, str], extractions: Dict[str, Any],
    document_id: str, created_by: str, cache: _InferenceCache,
) -> Tuple[int, int]:
    """Returns (inserted, icd10_inferred). icd10_inferred = of those
    inserted, how many got a code via the inference layer (not the
    extraction itself)."""
    rows = []
    inferred_count = 0
    for d in (extractions or {}).get("diagnoses") or []:
        if not (d.get("description") or d.get("icd10_code")):
            continue
        existing_code = (d.get("icd10_code") or "").strip() or None
        resolved_code = existing_code
        resolved_desc = d.get("description")

        if not resolved_code and d.get("description"):
            hit = _resolve_icd10(supabase, d["description"], cache)
            if hit:
                resolved_code, resolved_desc = hit[0], hit[1]
                inferred_count += 1

        rows.append({
            "id":                 _new_id(),
            "tenant_id":          tenant_id,
            "workspace_id":       workspace_id,
            "encounter_id":       _encounter_for_row(encounter_map, d),
            "patient_id":         patient_id,
            "code":               resolved_code,
            "coding_system":      "ICD-10" if resolved_code else "local",
            "display":            d.get("description") or resolved_desc or "Unspecified",
            "diagnosis_type":     d.get("type") or "primary",
            "status":             d.get("status") or "active",
            "onset_date":         _normalise_date(d.get("onset_date")),
            "source":             "document_extraction",
            "source_document_id": document_id,
            "created_by":         created_by,
            "diagnosed_date":     _normalise_date(d.get("consultation_date")),
        })
    if rows:
        supabase.table("diagnoses").insert(rows).execute()
    return len(rows), inferred_count


def _promote_vitals(
    supabase, *, workspace_id: str, tenant_id: str, patient_id: str,
    encounter_map: Dict[str, str], extractions: Dict[str, Any],
    document_id: str, created_by: str,
) -> int:
    rows = []
    for v in (extractions or {}).get("vitals_history") or []:
        # Skip empty rows where every measurement is null/blank
        measurements = [
            v.get(k) for k in ("temperature_c", "heart_rate",
                                "bp_systolic", "bp_diastolic",
                                "oxygen_saturation", "weight_kg",
                                "bmi", "hba1c", "blood_glucose_fasting")
        ]
        if not any(measurements):
            continue
        cdate = _normalise_date(v.get("consultation_date"))
        rows.append({
            "id":                       _new_id(),
            "tenant_id":                tenant_id,
            "workspace_id":             workspace_id,
            "encounter_id":             _encounter_for_row(encounter_map, v),
            "patient_id":               patient_id,
            "bp_systolic":              _coerce_int(v.get("bp_systolic")),
            "bp_diastolic":             _coerce_int(v.get("bp_diastolic")),
            "heart_rate":               _coerce_int(v.get("heart_rate")),
            "temperature":              _coerce_float(v.get("temperature_c")),
            "spo2":                     _coerce_int(v.get("oxygen_saturation")),
            "weight_kg":                _coerce_float(v.get("weight_kg")),
            # height_cm not in extraction shape today; skip → BMI generated col stays null
            "hba1c":                    _coerce_float(v.get("hba1c")),
            "blood_glucose_fasting":    _coerce_float(v.get("blood_glucose_fasting")),
            "measured_datetime":        f"{cdate}T00:00:00+00:00" if cdate else _now_iso(),
            "consultation_date_text":   str(v.get("consultation_date") or "") or None,
            "source":                   "document_extraction",
            "source_document_id":       document_id,
            "created_by":               created_by,
        })
    if rows:
        supabase.table("vitals").insert(rows).execute()
    return len(rows)


def _promote_medications(
    supabase, *, workspace_id: str, tenant_id: str, patient_id: str,
    encounter_map: Dict[str, str], extractions: Dict[str, Any],
    document_id: str, created_by: str, cache: _InferenceCache,
) -> Tuple[int, int]:
    """Each consultation_date gets one prescription row; medications listed
    on that date become prescription_items linked to it. Cleanup of prior
    rows happens centrally in _wipe_prior_promotion.

    Returns (item_count, nappi_inferred). nappi_inferred = of those inserted,
    how many got a NAPPI/ATC via the inference layer."""
    meds = (extractions or {}).get("medications") or []
    if not meds:
        return 0, 0

    # Group meds by consultation_date so each date becomes a single Rx
    by_date: Dict[str, List[Dict[str, Any]]] = {}
    for m in meds:
        d = _normalise_date(m.get("consultation_date")) or "_unknown"
        by_date.setdefault(d, []).append(m)

    total_items = 0
    nappi_inferred = 0
    for d, group in by_date.items():
        rx_id = _new_id()
        rx_row = {
            "id":                  rx_id,
            "tenant_id":           tenant_id,
            "workspace_id":        workspace_id,
            "patient_id":          patient_id,
            "encounter_id":        _encounter_for_row(
                encounter_map,
                {"consultation_date": d if d != "_unknown" else None},
            ),
            "doctor_name":         "(Digitised record — prescriber not extracted)",
            "prescription_date":   d if d != "_unknown" else None,
            "status":              "active",
            "source":              "document_extraction",
            "source_document_id":  document_id,
        }
        supabase.table("prescriptions").insert(rx_row).execute()

        items = []
        for m in group:
            med_name = (m.get("drug_name") or m.get("medication_name") or "").strip()
            if not med_name:
                continue  # nothing to insert

            # NAPPI/ATC inference — only when the extraction didn't already
            # attach codes (it never does today, but future-proof anyway).
            existing_nappi = m.get("nappi_code")
            existing_atc   = m.get("atc_code")
            generic_extr   = (m.get("generic_name") or "").strip() or None

            resolved_nappi = existing_nappi
            resolved_atc   = existing_atc
            resolved_generic = generic_extr
            if not existing_nappi:
                hit = _resolve_nappi(supabase, med_name, cache)
                if hit:
                    resolved_nappi   = hit.get("nappi_code")
                    resolved_atc     = resolved_atc or hit.get("atc_code")
                    resolved_generic = resolved_generic or hit.get("generic_name")
                    nappi_inferred += 1

            # Several columns on prescription_items are NOT NULL in the
            # production schema (dosage in particular). Digitised records
            # often have those fields blank. Substitute a placeholder so
            # the row lands; reviewers can fill them in later via the
            # patient EHR.
            items.append({
                "id":                 _new_id(),
                "prescription_id":    rx_id,
                "medication_name":    med_name,
                "generic_name":       resolved_generic,
                "nappi_code":         resolved_nappi,
                "atc_code":           resolved_atc,
                "dosage":             (m.get("dosage") or "").strip() or "—",
                "frequency":          (m.get("frequency") or "").strip() or "—",
                "duration":           (m.get("duration") or "").strip() or "—",
                "quantity":           _coerce_int(m.get("quantity")),
                "instructions":       (m.get("instructions") or "").strip() or None,
                "source":             "document_extraction",
                "source_document_id": document_id,
            })
        if items:
            supabase.table("prescription_items").insert(items).execute()
            total_items += len(items)
    return total_items, nappi_inferred


# ---------------------------------------------------------------------------
# Public entry point
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
    """Idempotently promote a validated document's extractions into the
    structured EHR tables.

    Returns a PromotionResult describing what was matched/created and how
    many rows landed in each table. Caller is expected to also stamp
    digitised_documents.patient_id/encounter_id from the result.
    """
    created_by = created_by or "promoter"
    extractions = extractions or {}
    demographics = extractions.get("patient_demographics") or {}

    tenant_id = _tenant_for_workspace(supabase, workspace_id)

    # All cleanup of prior rows happens upfront in reverse-FK order.
    _wipe_prior_promotion(supabase, document_id)

    patient_id, kind, confidence, summary = _match_or_create_patient(
        supabase, workspace_id, demographics,
        forced_patient_id=forced_patient_id,
        force_create=force_create_patient,
    )
    encounter_map = _create_encounters(
        supabase, workspace_id, patient_id, extractions, document_id,
    )

    cache = _InferenceCache()

    diagnoses_count, icd10_inferred = _promote_diagnoses(
        supabase, workspace_id=workspace_id, tenant_id=tenant_id,
        patient_id=patient_id, encounter_map=encounter_map,
        extractions=extractions, document_id=document_id,
        created_by=created_by, cache=cache,
    )
    rx_items_count, nappi_inferred = _promote_medications(
        supabase, workspace_id=workspace_id, tenant_id=tenant_id,
        patient_id=patient_id, encounter_map=encounter_map,
        extractions=extractions, document_id=document_id,
        created_by=created_by, cache=cache,
    )

    counts = {
        "encounters":          len(encounter_map),
        "allergies":           _promote_allergies(
            supabase, workspace_id=workspace_id, tenant_id=tenant_id,
            patient_id=patient_id, extractions=extractions,
            document_id=document_id, created_by=created_by,
        ),
        "diagnoses":           diagnoses_count,
        "vitals":              _promote_vitals(
            supabase, workspace_id=workspace_id, tenant_id=tenant_id,
            patient_id=patient_id, encounter_map=encounter_map,
            extractions=extractions, document_id=document_id, created_by=created_by,
        ),
        "prescription_items":  rx_items_count,
    }
    inference_summary = {
        "icd10_codes_inferred":   icd10_inferred,
        "nappi_codes_inferred":   nappi_inferred,
    }

    logger.info(
        f"[promoter] doc={document_id[:8]}… patient={patient_id[:8]}… "
        f"({kind}) → {counts} | inference: {inference_summary}"
    )

    return PromotionResult(
        patient_id=patient_id,
        patient_kind=kind,
        match_confidence=confidence,
        patient_summary=summary,
        encounter_ids=list(encounter_map.values()),
        counts={**counts, **inference_summary},
    )
