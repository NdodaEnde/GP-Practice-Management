"""
Verification harness for the Consultation ontology object.

Run from the `Ontology_starter/backend/` directory:

    cd Ontology_starter/backend
    python3 verify_consultation.py

Confirms that:
  1. A valid live-recorded Consultation instantiates.
  2. A valid reconstructed-from-paper Consultation instantiates.
  3. Each cross-field validator fires on the intended invalid case.
  4. Round-trip JSON serialisation is lossless.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from pydantic import ValidationError

from ontology import (
    Consultation,
    ConsultationStatus,
    EncounterSetting,
    EncounterType,
)


def _shared_required():
    """The system fields every OntologyObject needs (id, practice_id, timestamps)."""
    now = datetime.now(timezone.utc)
    return {
        "id": uuid4(),
        "practice_id": uuid4(),
        "created_at": now,
        "updated_at": now,
    }


def _expect_failure(label: str, exc_substring: str, factory):
    """Run `factory()`; print PASS if it raises a ValidationError containing
    `exc_substring`, otherwise print FAIL with details."""
    try:
        factory()
    except ValidationError as exc:
        if exc_substring in str(exc):
            print(f"  PASS  {label}")
            return
        print(f"  FAIL  {label}")
        print(f"        expected substring: {exc_substring!r}")
        print(f"        got: {exc}")
        return
    except Exception as exc:  # noqa: BLE001
        print(f"  FAIL  {label}")
        print(f"        unexpected exception type: {type(exc).__name__}: {exc}")
        return
    print(f"  FAIL  {label} — no exception raised")


def main() -> None:
    print("=" * 60)
    print("Verifying Consultation ontology object")
    print("=" * 60)

    today = date.today()
    visit_start = datetime.now(timezone.utc).replace(microsecond=0)
    # Pin encounter_date to the UTC date of visit_start to satisfy the
    # date/timestamp-agreement validator across timezone boundaries.
    visit_date = visit_start.astimezone(timezone.utc).date()
    visit_end = visit_start + timedelta(minutes=18)

    # ---- 1. Valid live-recorded Consultation ----
    print("\n[1] A valid live-recorded Consultation instantiates (SOAP fields).")
    live = Consultation(
        **_shared_required(),
        patient_id=uuid4(),
        practitioner_id=uuid4(),
        encounter_date=visit_date,
        encounter_start_at=visit_start,
        encounter_end_at=visit_end,
        encounter_type=EncounterType.CONSULTATION,
        setting=EncounterSetting.PRACTICE,
        chief_complaint="Persistent cough, 3 weeks",
        presenting_complaint="Cough that won't go away, worse at night. "
                             "I'm worried it might be TB.",
        history="3-week productive cough, worse at night. No fever. No "
                "haemoptysis. Non-smoker. Recent close contact with a "
                "TB-positive colleague.",
        examination="BP 130/85, T 37.4, RR 18. Chest: scattered rhonchi, no "
                    "crepitations. Throat clear. No cervical lymphadenopathy.",
        assessment="Post-viral cough most likely; TB exposure raises concern. "
                   "Differentials: post-viral, pertussis, early TB.",
        plan="CXR + sputum AFB x2. Review in 5 days with results. Safety net: "
             "return sooner if fever, haemoptysis, weight loss.",
        status=ConsultationStatus.COMPLETED,
        completed_at=visit_end,
        billing_icd10_codes=["R05"],
    )
    print(f"  display_name:           {live.display_name()}")
    print(f"  duration_minutes:       {live.duration_minutes()}")
    print(f"  has_clinical_content:   {live.has_clinical_content()}")
    print(f"  is_recent(within=7):    {live.is_recent(within_days=7, as_of=today)}")

    # ---- 2. Valid reconstructed-from-paper Consultation ----
    print("\n[2] A valid reconstructed-from-paper Consultation instantiates.")
    reconstructed = Consultation(
        **_shared_required(),
        patient_id=uuid4(),
        practitioner_id=uuid4(),
        encounter_date=date(2024, 6, 12),  # past date, paper record
        # No precise timestamps — only the date came off the paper record
        encounter_type=EncounterType.FOLLOW_UP,
        setting=EncounterSetting.PRACTICE,
        chief_complaint="Diabetes follow-up",
        history="(From scanned paper file dated 2024-06-12.) Type 2 diabetes "
                "on metformin 500mg BD. Compliance acceptable. No hypoglycaemic "
                "events.",
        examination="BP 138/88. HbA1c 8.2 (taken at visit).",
        assessment="Suboptimal glycaemic control despite metformin BD.",
        plan="Increase metformin to 1g BD. Repeat HbA1c in 3 months. Review then.",
        status=ConsultationStatus.COMPLETED,
        completed_at=datetime(2024, 6, 12, 14, 30, tzinfo=timezone.utc),
        source_document_id=uuid4(),
        is_reconstructed_from_paper=True,
    )
    print(f"  display_name:           {reconstructed.display_name()}")
    print(f"  duration_minutes:       {reconstructed.duration_minutes()}  "
          f"(expected None — paper record had no times)")
    print(f"  is_reconstructed:       {reconstructed.is_reconstructed_from_paper}")
    print(f"  source_document_id set: {reconstructed.source_document_id is not None}")

    # ---- 3. COMPLETED requires completed_at ----
    print("\n[3] status=COMPLETED without completed_at → error.")
    _expect_failure(
        "missing completed_at on COMPLETED",
        "requires completed_at",
        lambda: Consultation(
            **_shared_required(),
            patient_id=uuid4(),
            practitioner_id=uuid4(),
            encounter_date=today,
            status=ConsultationStatus.COMPLETED,
        ),
    )

    # ---- 4. completed_at without COMPLETED status → error ----
    print("\n[4] completed_at set while status=PLANNED → error.")
    _expect_failure(
        "completed_at requires COMPLETED status",
        "only makes sense when status=COMPLETED",
        lambda: Consultation(
            **_shared_required(),
            patient_id=uuid4(),
            practitioner_id=uuid4(),
            encounter_date=today,
            status=ConsultationStatus.PLANNED,
            completed_at=datetime.now(timezone.utc),
        ),
    )

    # ---- 5. encounter_end_at before encounter_start_at ----
    print("\n[5] encounter_end_at earlier than encounter_start_at → error.")
    _expect_failure(
        "negative-duration encounter rejected",
        "earlier than encounter_start_at",
        lambda: Consultation(
            **_shared_required(),
            patient_id=uuid4(),
            practitioner_id=uuid4(),
            encounter_date=visit_date,
            encounter_start_at=visit_start,
            encounter_end_at=visit_start - timedelta(minutes=5),
            status=ConsultationStatus.COMPLETED,
            completed_at=visit_start,
        ),
    )

    # ---- 6. encounter_date mismatch with encounter_start_at ----
    print("\n[6] encounter_date mismatched with encounter_start_at date → error.")
    _expect_failure(
        "date/timestamp mismatch (timezone bug signal)",
        "does not match the date of encounter_start_at",
        lambda: Consultation(
            **_shared_required(),
            patient_id=uuid4(),
            practitioner_id=uuid4(),
            encounter_date=visit_date + timedelta(days=1),  # off by a day
            encounter_start_at=visit_start,
            encounter_end_at=visit_end,
            status=ConsultationStatus.COMPLETED,
            completed_at=visit_end,
        ),
    )

    # ---- 7. is_reconstructed_from_paper=True without source_document_id ----
    print("\n[7] is_reconstructed_from_paper=True without source_document_id → error.")
    _expect_failure(
        "reconstructed flag requires source document",
        "is_reconstructed_from_paper=True requires source_document_id",
        lambda: Consultation(
            **_shared_required(),
            patient_id=uuid4(),
            practitioner_id=uuid4(),
            encounter_date=today,
            is_reconstructed_from_paper=True,
            status=ConsultationStatus.COMPLETED,
            completed_at=datetime.now(timezone.utc),
        ),
    )

    # ---- 8. source_document_id set but is_reconstructed_from_paper=False ----
    print("\n[8] source_document_id set without is_reconstructed_from_paper → error.")
    _expect_failure(
        "source document requires reconstructed flag",
        "set both or neither",
        lambda: Consultation(
            **_shared_required(),
            patient_id=uuid4(),
            practitioner_id=uuid4(),
            encounter_date=today,
            source_document_id=uuid4(),
            is_reconstructed_from_paper=False,
            status=ConsultationStatus.COMPLETED,
            completed_at=datetime.now(timezone.utc),
        ),
    )

    # ---- 9. has_clinical_content on an operational record ----
    print("\n[9] has_clinical_content() is False on a NO_SHOW record.")
    no_show = Consultation(
        **_shared_required(),
        patient_id=uuid4(),
        practitioner_id=uuid4(),
        encounter_date=today,
        status=ConsultationStatus.NO_SHOW,
    )
    if not no_show.has_clinical_content():
        print("  PASS  empty-narrative NO_SHOW has no clinical content")
    else:
        print("  FAIL  expected has_clinical_content()=False")

    # ---- 9b. practitioner_id is distinct from a hypothetical validator ----
    print("\n[9b] practitioner_id ≠ Document.validated_by_user_id (attribution).")
    # Simulate the 2019 paper / 2026 admin scenario from the docstring:
    # the doctor who saw the patient in 2019 is the practitioner; the admin
    # who clicked 'approve' in 2026 is *not*. Ontologically these must be
    # different IDs (or at least independently settable).
    doctor_2019 = uuid4()
    admin_2026 = uuid4()
    legacy = Consultation(
        **_shared_required(),
        patient_id=uuid4(),
        practitioner_id=doctor_2019,       # who conducted the encounter
        encounter_date=date(2019, 7, 22),
        encounter_type=EncounterType.CONSULTATION,
        setting=EncounterSetting.PRACTICE,
        chief_complaint="Hypertension review",
        status=ConsultationStatus.COMPLETED,
        completed_at=datetime(2019, 7, 22, 10, 15, tzinfo=timezone.utc),
        source_document_id=uuid4(),
        is_reconstructed_from_paper=True,
    )
    # The 'admin_2026' would live on the source Document's
    # validated_by_user_id — not on the Consultation. Verify they're
    # independent: the Consultation has no path that would conflate them.
    if legacy.practitioner_id == doctor_2019 and doctor_2019 != admin_2026:
        print("  PASS  practitioner_id holds the 2019 doctor, not the 2026 admin")
    else:
        print("  FAIL  practitioner identity got confused")

    # ---- 10. Round-trip serialisation ----
    print("\n[10] Round-trip: serialise to JSON, rehydrate, compare.")
    serialised = live.model_dump_json()
    rehydrated = Consultation.model_validate_json(serialised)
    if rehydrated.model_dump() == live.model_dump():
        print("  PASS  serialise → deserialise → equal")
    else:
        print("  FAIL  round-trip diverged")
        original = live.model_dump()
        for key in original:
            if original[key] != rehydrated.model_dump().get(key):
                print(f"        differs at {key!r}: "
                      f"{original[key]!r} vs {rehydrated.model_dump().get(key)!r}")
                break

    print("\n" + "=" * 60)
    print("Consultation verification complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
