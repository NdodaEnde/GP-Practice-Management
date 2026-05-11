"""
Verification harness for the Patient mapper.

Run from the backend/ directory:

    cd /Users/luzuko/GP-Practice-Management/backend
    python3 verify_patient_mapper.py

Pure dict-in, Patient-out. No DB access. Exercises:

  [1] Clean row with valid SA ID + matching DOB → success.
  [2] Sentinel DOB '1900-01-01' + real SA ID    → ValidationError (the
                                                   sentinel-row failure
                                                   case the endpoint
                                                   will see in dev DB).
  [3] Row missing all optional columns          → success with None
                                                   fallbacks.
  [4] id_number with trailing whitespace        → normalised on
                                                   hydration (the
                                                   normalisation-only
                                                   diff case the
                                                   plan's success
                                                   criterion accepts).
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import ValidationError

from ontology.mappers.patient import hydrate_patient_from_row


# Verified Luhn-valid SA ID; decodes to dob=1985-03-14, sex=F, SA citizen.
THANDI_SA_ID = "8503140001087"


def _base_row(**overrides) -> dict:
    """A clean row matching the production schema. Override individual
    fields per test case."""
    row = {
        "id": str(uuid4()),
        "tenant_id": "tenant-abc",
        "workspace_id": str(uuid4()),
        "first_name": "Thandi",
        "last_name": "Mthembu",
        "dob": "1985-03-14",
        "id_number": THANDI_SA_ID,
        "contact_number": "+27821234567",
        "email": "thandi@example.co.za",
        "address": "12 Main Rd, Khayelitsha",
        "medical_aid": "Discovery Health Classic Smart",
        "created_at": "2026-03-08T14:23:00+00:00",
    }
    row.update(overrides)
    return row


def main() -> None:
    print("=" * 60)
    print("Verifying patient mapper")
    print("=" * 60)

    # --- [1] Clean row hydrates ----------------------------------------
    print("\n[1] Clean row, valid SA ID, matching DOB → hydrates.")
    patient = hydrate_patient_from_row(_base_row())
    print(f"  display_name:      {patient.display_name()}")
    print(f"  identifier_number: {patient.identifier_number!r}")
    print(f"  biological_sex:    {patient.biological_sex.value}  "
          f"(UNKNOWN by design — no DB column yet)")
    print("  PASS")

    # --- [2] Sentinel DOB + real SA ID → cross-check fires --------------
    print("\n[2] dob='1900-01-01' + real SA ID → ValidationError.")
    try:
        hydrate_patient_from_row(_base_row(dob="1900-01-01"))
    except ValidationError as exc:
        text = str(exc)
        if "Date of birth" in text and "SA ID" in text:
            print("  PASS — SA-ID DOB cross-check fires on sentinel.")
        else:
            print(f"  FAIL — wrong validation message:\n{text}")
    except Exception as exc:  # noqa: BLE001
        print(f"  FAIL — unexpected exception {type(exc).__name__}: {exc}")
    else:
        print("  FAIL — expected ValidationError, got success.")

    # --- [3] Row missing optional columns → None fallbacks --------------
    print("\n[3] Row missing optional columns → hydrates with None.")
    minimal = {
        "id": str(uuid4()),
        "workspace_id": str(uuid4()),
        "first_name": "Sipho",
        "last_name": "Dlamini",
        "dob": "1985-03-14",
        "id_number": THANDI_SA_ID,
        "created_at": "2026-03-08T14:23:00+00:00",
    }
    patient = hydrate_patient_from_row(minimal)
    assertions = {
        "primary_phone is None": patient.primary_phone is None,
        "email is None": patient.email is None,
        "physical_address is None": patient.physical_address is None,
        "title is None": patient.title is None,
        "medical_aid_scheme_id is None": patient.medical_aid_scheme_id is None,
        "active_chronic_conditions_summary is None":
            patient.active_chronic_conditions_summary is None,
        "deleted_at is None": patient.deleted_at is None,
        "updated_at == created_at": patient.updated_at == patient.created_at,
    }
    failed = [name for name, ok in assertions.items() if not ok]
    if not failed:
        print(f"  display_name: {patient.display_name()}")
        print(f"  email: {patient.email}  phone: {patient.primary_phone}  "
              f"address: {patient.physical_address}")
        print("  PASS — all 8 optional-field fallbacks hold.")
    else:
        print(f"  FAIL — broken assertions: {failed}")

    # --- [4] Trailing whitespace on id_number → normalised --------------
    print("\n[4] id_number='8503140001087 ' (trailing space) → normalised.")
    patient = hydrate_patient_from_row(_base_row(id_number=THANDI_SA_ID + " "))
    if patient.identifier_number == THANDI_SA_ID:
        print(f"  PASS — '{THANDI_SA_ID} ' → {patient.identifier_number!r} "
              "(the wire-format-divergence case the plan's success "
              "criterion accepts as normalisation-only).")
    else:
        print(f"  FAIL — got {patient.identifier_number!r}")

    # --- [5] Bonus: round-trip via model_dump_json → re-hydrate ---------
    print("\n[5] Bonus: round-trip through model_dump_json.")
    original = hydrate_patient_from_row(_base_row())
    rehydrated = type(original).model_validate_json(original.model_dump_json())
    if rehydrated.model_dump() == original.model_dump():
        print("  PASS — serialise → deserialise → equal.")
    else:
        print("  FAIL — round-trip diverged.")

    print("\n" + "=" * 60)
    print("Patient mapper verification complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
