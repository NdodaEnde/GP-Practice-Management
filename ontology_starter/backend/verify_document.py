"""
Verification harness for the Document ontology object.

Run from the `Ontology_starter/backend/` directory:

    cd Ontology_starter/backend
    python3 verify_document.py

Confirms that:
  1. A valid Document instantiates and renders its display template.
  2. Each cross-field validator fires on the intended invalid case.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from pydantic import ValidationError

from ontology import Document, DocumentSource, DocumentStatus


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
    print("Verifying Document ontology object")
    print("=" * 60)

    # ---- 1. Valid construction ----
    print("\n[1] A valid Document instantiates.")
    upload_time = datetime.now(timezone.utc)
    doc = Document(
        **_shared_required(),
        original_filename="Mthembu_referral_2024_03.pdf",
        mime_type="application/pdf",
        storage_path="medical-records/acme/Mthembu_referral_2024_03.pdf",
        file_size_bytes=482_117,
        uploaded_at=upload_time,
        source=DocumentSource.MANUAL_UPLOAD,
        status=DocumentStatus.UPLOADED,
    )
    print(f"  display_name: {doc.display_name()}")
    print(f"  short_id:     {doc.short_id()}")
    print(f"  is_terminal:  {doc.is_terminal()}")
    print(f"  awaiting:     validation={doc.awaiting_validation()} "
          f"promotion={doc.awaiting_promotion()}")

    # ---- 2. PROMOTED requires full promotion provenance ----
    print("\n[2] status=PROMOTED without promotion fields → error.")
    _expect_failure(
        "missing promoted_at / promoted_by_user_id / promoted_to_patient_id",
        "status=PROMOTED requires",
        lambda: Document(
            **_shared_required(),
            original_filename="x.pdf",
            mime_type="application/pdf",
            storage_path="x",
            file_size_bytes=100,
            uploaded_at=upload_time,
            status=DocumentStatus.PROMOTED,
        ),
    )

    # ---- 3. REJECTED requires reason and timestamp ----
    print("\n[3] status=REJECTED without rejection_reason → error.")
    _expect_failure(
        "missing rejection_reason",
        "status=REJECTED requires",
        lambda: Document(
            **_shared_required(),
            original_filename="x.pdf",
            mime_type="application/pdf",
            storage_path="x",
            file_size_bytes=100,
            uploaded_at=upload_time,
            status=DocumentStatus.REJECTED,
            rejected_at=upload_time,
        ),
    )

    # ---- 4. PARSE_FAILED requires parse_error ----
    print("\n[4] status=PARSE_FAILED without parse_error → error.")
    _expect_failure(
        "missing parse_error",
        "status=PARSE_FAILED requires parse_error",
        lambda: Document(
            **_shared_required(),
            original_filename="x.pdf",
            mime_type="application/pdf",
            storage_path="x",
            file_size_bytes=100,
            uploaded_at=upload_time,
            parsed_at=upload_time + timedelta(minutes=1),
            status=DocumentStatus.PARSE_FAILED,
        ),
    )

    # ---- 5. PARSE_FAILED with confidence is contradictory ----
    print("\n[5] status=PARSE_FAILED with non-null confidence → error.")
    _expect_failure(
        "PARSE_FAILED + confidence is contradictory",
        "incompatible with a non-null",
        lambda: Document(
            **_shared_required(),
            original_filename="x.pdf",
            mime_type="application/pdf",
            storage_path="x",
            file_size_bytes=100,
            uploaded_at=upload_time,
            parsed_at=upload_time + timedelta(minutes=1),
            parse_error="upstream model timed out",
            parse_confidence_avg=0.4,
            status=DocumentStatus.PARSE_FAILED,
        ),
    )

    # ---- 6. Lifecycle ordering must be monotonic ----
    print("\n[6] promoted_at earlier than parsed_at → error.")
    _expect_failure(
        "promoted_at earlier than parsed_at",
        "monotonically non-decreasing",
        lambda: Document(
            **_shared_required(),
            original_filename="x.pdf",
            mime_type="application/pdf",
            storage_path="x",
            file_size_bytes=100,
            uploaded_at=upload_time,
            parsed_at=upload_time + timedelta(hours=2),
            validated_at=upload_time + timedelta(hours=3),
            promoted_at=upload_time + timedelta(hours=1),  # earlier than parsed_at
            promoted_by_user_id=uuid4(),
            promoted_to_patient_id=uuid4(),
            status=DocumentStatus.PROMOTED,
        ),
    )

    # ---- 7. SCAN_AGENT requires workstation id ----
    print("\n[7] source=SCAN_AGENT without scan_agent_workstation_id → error.")
    _expect_failure(
        "missing scan_agent_workstation_id",
        "source=SCAN_AGENT requires",
        lambda: Document(
            **_shared_required(),
            original_filename="x.pdf",
            mime_type="application/pdf",
            storage_path="x",
            file_size_bytes=100,
            uploaded_at=upload_time,
            source=DocumentSource.SCAN_AGENT,
            status=DocumentStatus.UPLOADED,
        ),
    )

    # ---- 8. PARSED requires parsed_at ----
    print("\n[8] status=PARSED without parsed_at → error.")
    _expect_failure(
        "missing parsed_at on PARSED",
        "requires parsed_at",
        lambda: Document(
            **_shared_required(),
            original_filename="x.pdf",
            mime_type="application/pdf",
            storage_path="x",
            file_size_bytes=100,
            uploaded_at=upload_time,
            status=DocumentStatus.PARSED,
        ),
    )

    # ---- 9. VALIDATED requires both validated_at and validated_by_user_id ----
    print("\n[9] status=VALIDATED without validation provenance → error.")
    _expect_failure(
        "missing validated_at / validated_by_user_id",
        "requires validated_at, validated_by_user_id",
        lambda: Document(
            **_shared_required(),
            original_filename="x.pdf",
            mime_type="application/pdf",
            storage_path="x",
            file_size_bytes=100,
            uploaded_at=upload_time,
            parsed_at=upload_time + timedelta(minutes=1),
            status=DocumentStatus.VALIDATED,
        ),
    )

    # ---- 10. Terminal-state exclusivity ----
    print("\n[10] Document with both promotion AND rejection fields → error.")
    _expect_failure(
        "promotion + rejection are exclusive",
        "mutually exclusive terminal outcomes",
        lambda: Document(
            **_shared_required(),
            original_filename="x.pdf",
            mime_type="application/pdf",
            storage_path="x",
            file_size_bytes=100,
            uploaded_at=upload_time,
            parsed_at=upload_time + timedelta(minutes=1),
            validated_at=upload_time + timedelta(minutes=2),
            validated_by_user_id=uuid4(),
            promoted_at=upload_time + timedelta(minutes=3),
            promoted_by_user_id=uuid4(),
            promoted_to_patient_id=uuid4(),
            rejection_reason="wrong patient",
            status=DocumentStatus.PROMOTED,
        ),
    )

    # ---- 11. Orphan consultation pointer ----
    print("\n[11] promoted_to_consultation_id without promoted_to_patient_id → error.")
    _expect_failure(
        "orphan consultation pointer",
        "Consultation always belongs to a Patient",
        lambda: Document(
            **_shared_required(),
            original_filename="x.pdf",
            mime_type="application/pdf",
            storage_path="x",
            file_size_bytes=100,
            uploaded_at=upload_time,
            parsed_at=upload_time + timedelta(minutes=1),
            validated_at=upload_time + timedelta(minutes=2),
            validated_by_user_id=uuid4(),
            promoted_to_consultation_id=uuid4(),  # no patient pointer
            status=DocumentStatus.VALIDATED,
        ),
    )

    # ---- 12. SHA-256 hash validation ----
    print("\n[12] SHA-256 hex validation and normalisation.")
    _expect_failure(
        "sha256 wrong length",
        "must be 64 hex characters",
        lambda: Document(
            **_shared_required(),
            original_filename="x.pdf",
            mime_type="application/pdf",
            storage_path="x",
            file_size_bytes=100,
            sha256_hash="abc123",
            uploaded_at=upload_time,
        ),
    )
    _expect_failure(
        "sha256 with non-hex chars",
        "only hexadecimal characters",
        lambda: Document(
            **_shared_required(),
            original_filename="x.pdf",
            mime_type="application/pdf",
            storage_path="x",
            file_size_bytes=100,
            sha256_hash="z" * 64,
            uploaded_at=upload_time,
        ),
    )
    # Uppercase normalises to lowercase rather than erroring
    mixed_case_hash = "ABCDEF" + ("a" * 58)
    doc_mixed = Document(
        **_shared_required(),
        original_filename="x.pdf",
        mime_type="application/pdf",
        storage_path="x",
        file_size_bytes=100,
        sha256_hash=mixed_case_hash,
        uploaded_at=upload_time,
    )
    if doc_mixed.sha256_hash == mixed_case_hash.lower():
        print("  PASS  uppercase hash normalised to lowercase")
    else:
        print(f"  FAIL  expected lowercase normalisation, got {doc_mixed.sha256_hash}")

    # ---- 13. file_size_bytes must be > 0 ----
    print("\n[13] file_size_bytes = 0 → error (zero-byte uploads are bugs).")
    _expect_failure(
        "zero-byte file rejected",
        "greater than 0",
        lambda: Document(
            **_shared_required(),
            original_filename="empty.pdf",
            mime_type="application/pdf",
            storage_path="x",
            file_size_bytes=0,
            uploaded_at=upload_time,
        ),
    )

    # ---- 14. A fully-promoted Document with full provenance trail ----
    print("\n[14] A fully-promoted Document with the full provenance trail.")
    promoted = Document(
        **_shared_required(),
        original_filename="lab_report_HbA1c.pdf",
        mime_type="application/pdf",
        storage_path="medical-records/acme/lab_report_HbA1c.pdf",
        file_size_bytes=215_482,
        sha256_hash="a" * 64,
        uploaded_at=upload_time,
        source=DocumentSource.STORAGE_WATCHER,
        parse_model="landingai_ade",
        parse_model_version="2026-03",
        parsed_at=upload_time + timedelta(minutes=2),
        parse_confidence_avg=0.91,
        validated_at=upload_time + timedelta(hours=4),
        validated_by_user_id=uuid4(),
        validation_corrections_count=3,
        promoted_at=upload_time + timedelta(hours=5),
        promoted_by_user_id=uuid4(),
        promoted_to_patient_id=uuid4(),
        promoted_to_consultation_id=uuid4(),
        status=DocumentStatus.PROMOTED,
    )
    print(f"  display_name: {promoted.display_name()}")
    print(f"  is_terminal:  {promoted.is_terminal()}  (expected True)")
    print(f"  awaiting:     validation={promoted.awaiting_validation()} "
          f"promotion={promoted.awaiting_promotion()}  (expected both False)")

    # ---- 15. Round-trip serialisation ----
    print("\n[15] Round-trip: serialise to JSON, rehydrate, compare.")
    serialised = promoted.model_dump_json()
    rehydrated = Document.model_validate_json(serialised)
    if rehydrated.model_dump() == promoted.model_dump():
        print("  PASS  serialise → deserialise → equal")
    else:
        print("  FAIL  round-trip diverged")
        # Show the first difference for diagnosis
        original = promoted.model_dump()
        for key in original:
            if original[key] != rehydrated.model_dump().get(key):
                print(f"        differs at {key!r}: "
                      f"{original[key]!r} vs {rehydrated.model_dump().get(key)!r}")
                break

    print("\n" + "=" * 60)
    print("Document verification complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
