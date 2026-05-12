"""
Patient mapper: Supabase `patients` row → Patient ontology object.

Single entry point: `hydrate_patient_from_row(row)`. Pure dict-in,
Patient-out. No DB access here; the caller pulls the row.

Design notes
------------

The mapper is deliberately STRICT — it raises pydantic.ValidationError on
rows that violate Patient's invariants (sentinel DOB + real SA ID,
deceased without deceased_date, etc.). The calling endpoint wraps the
call in try/except and falls back to the legacy response shape so the
wire format stays stable while data-quality issues become queryable
through structured logs.

Out-of-scope DB columns (this pass)
-----------------------------------

  - `tenant_id`             — Tenant lives above Practice. The Tenant
                              ontology type doesn't exist yet. **TODO**
                              when multi-tenant rollouts justify it.
  - `medical_aid`           — Flat TEXT whose contents are ambiguous
                              (scheme name vs plan vs member number).
                              Becomes structured when MedicalAidScheme
                              is an ontology object. Until then the
                              endpoint serves it from the raw row.
  - `chronic_conditions`,
    `current_medications`,
    `allergies`,
    `latest_vitals`         — JSONB blobs. Become first-class Diagnosis /
                              Medication / Allergy / Vitals ontology
                              objects in a later pass. Served raw by the
                              endpoint's legacy section.
  - `validation_status`     — Belongs on Document, not Patient. Endpoint
                              surfaces it from the raw row for legacy
                              compatibility.

Mapper defaults (flag data-quality gaps without crashing)
---------------------------------------------------------

  - `biological_sex` → BiologicalSex.UNKNOWN
      No DB column today. UNKNOWN is the conservative default; the
      SA-ID/sex cross-check on Patient is skipped for UNKNOWN, so this
      doesn't gratuitously break hydration. A future cleanup task can
      decode sex from SA IDs (validate_and_decode_sa_id() already does
      this) — see plan's biological_sex risk note.

  - `identifier_type` → IdentifierType.SA_ID
      Matches production reality — `id_number` is overwhelmingly SA IDs.
      If the value doesn't decode as one, the SA-ID validator raises
      with a clear error.

  - `status` → PatientStatus.ACTIVE
      No lifecycle column today; live patients are the only category.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Optional
from uuid import UUID

from ontology.enums.patient_enums import (
    BiologicalSex,
    IdentifierType,
    PatientStatus,
)
from ontology.objects.patient import Patient


def hydrate_patient_from_row(row: dict[str, Any]) -> Patient:
    """Build a validated Patient from a Supabase `patients` row dict.

    Raises pydantic.ValidationError on rows that don't satisfy Patient's
    invariants. The caller decides whether to fail loud or fall back to a
    legacy response shape.

    Required keys (NOT NULL in the base schema): id, workspace_id,
    first_name, last_name, dob, id_number. Missing required keys raise
    KeyError, which the caller catches the same way as ValidationError.
    """
    created_at = _parse_datetime(row.get("created_at")) or datetime.now(timezone.utc)
    updated_at = _parse_datetime(row.get("updated_at")) or created_at

    return Patient(
        id=UUID(row["id"]),
        # practice_id is `str` on the ontology (per base.py docstring) — pass
        # through whatever the DB stores. Production values are slug-style
        # (e.g. 'typec-workspace-001'); a future DB migration to UUID PKs
        # would store UUID-shaped strings here, and this mapper still works.
        practice_id=row["workspace_id"],
        created_at=created_at,
        updated_at=updated_at,
        first_name=row["first_name"],
        surname=row["last_name"],
        date_of_birth=date.fromisoformat(row["dob"]),
        biological_sex=BiologicalSex.UNKNOWN,
        identifier_type=IdentifierType.SA_ID,
        identifier_number=row.get("id_number"),
        primary_phone=row.get("contact_number"),
        email=row.get("email"),
        physical_address=row.get("address"),
        status=PatientStatus.ACTIVE,
    )


def _parse_datetime(value: Any) -> Optional[datetime]:
    """Parse a Supabase timestamp (ISO string or datetime) → datetime, or
    None if the value is missing or unparseable.

    Supabase returns timestamps as ISO strings like
    "2026-03-08T14:23:00.123456+00:00". We parse explicitly (rather than
    letting Pydantic coerce) so the mapper can return None for missing
    values and fall back to created_at / now as appropriate.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None
