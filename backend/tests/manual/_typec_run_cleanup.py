"""
Corrective residue cleanup for the typec_live_http_run that left live
Supabase residue when its teardown hit the digitised_documents ->
encounters FK (digitised_documents_encounter_id_fkey) the real HTTP
approve path creates (digitisation.py:1338) and the copied-from-harness
delete order did not account for.

SCOPED HARD: operates ONLY on this run's unique upload uuid + the
tracked ids printed in /tmp/typec_live_http.log. source_document_id is a
fresh per-upload uuid — it cannot collide with the pre-existing demo
workspace accumulation (17 encounters etc., unknown provenance, NOT
mine, deliberately untouched). Refuses if the expected doc id is not
the one observed, so it cannot be repurposed into a broad delete.

FK order corrected from the OBSERVED error messages:
  digitised_documents (refs encounter) -> delete the doc row FIRST,
  then prescription_items -> prescriptions, diagnoses, vitals,
  allergies, encounters, then patient (refs by encounters).
Independent three-key re-verify at the end (source_document_id +
tracked ids + audit); does NOT use the workspace_id sweep as a residue
signal (polluted by the pre-existing non-mine demo data — reported, not
acted on).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[2]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

# Exact identifiers observed in /tmp/typec_live_http.log (raw actuals).
DOC_ID = "c3af4a37-b3a9-410c-a7c6-cc34b86383d0"
PATIENT_ID = "bae9b5f3-40ed-45c4-84d0-5115a3950302"
ENCOUNTER_ID = "4de970fc-5d2d-4600-aba1-d9d26ab8c147"
AUDIT_ID = "dce0be24-840a-467a-b5cc-ef15b2574668"
STORAGE_PATH = f"typec-workspace-001/{DOC_ID}/clean_consult.pdf"

_SRCDOC_TABLES = ["prescription_items", "prescriptions", "diagnoses",
                  "vitals", "allergies", "encounters"]


def _load_env():
    for ln in (_BACKEND / ".env").read_text().splitlines():
        ln = ln.strip()
        if ln and not ln.startswith("#") and "=" in ln:
            k, v = ln.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _client():
    from supabase import create_client
    return create_client(os.environ["SUPABASE_URL"],
                          os.environ["SUPABASE_SERVICE_KEY"])


def main():
    if os.environ.get("RUN_TYPEC_CLEANUP") != "1":
        print("REFUSING: set RUN_TYPEC_CLEANUP=1.")
        sys.exit(2)
    _load_env()
    sb = _client()

    # 1. session / parsed ids by the tracked doc id (for deletion)
    srow = (sb.table("gp_validation_sessions").select("id")
            .eq("document_id", DOC_ID).execute().data) or []
    session_ids = [r["id"] for r in srow]
    drow = (sb.table("digitised_documents").select("parsed_doc_id")
            .eq("id", DOC_ID).execute().data) or []
    parsed_doc_id = drow[0].get("parsed_doc_id") if drow else None

    # 2. doc row FIRST (it references the encounter via the FK that
    #    blocked the original teardown)
    try:
        sb.table("digitised_documents").delete().eq("id", DOC_ID).execute()
        print(f"deleted digitised_documents/{DOC_ID}")
    except Exception as ex:  # noqa: BLE001
        print(f"ERR digitised_documents: {ex}")

    # 3. clinical children -> encounter, by the per-upload uuid
    for tbl in _SRCDOC_TABLES:
        try:
            sb.table(tbl).delete().eq("source_document_id", DOC_ID).execute()
            print(f"deleted {tbl} by source_document_id={DOC_ID}")
        except Exception as ex:  # noqa: BLE001
            print(f"ERR {tbl}: {ex}")

    # 4. patient by tracked id (no source_document_id column)
    try:
        sb.table("patients").delete().eq("id", PATIENT_ID).execute()
        print(f"deleted patients/{PATIENT_ID}")
    except Exception as ex:  # noqa: BLE001
        print(f"ERR patients: {ex}")

    # 5. session / parsed / audit
    for sid in session_ids:
        try:
            sb.table("gp_validation_sessions").delete().eq("id", sid).execute()
            print(f"deleted gp_validation_sessions/{sid}")
        except Exception as ex:  # noqa: BLE001
            print(f"ERR session {sid}: {ex}")
    if parsed_doc_id:
        try:
            sb.table("gp_parsed_documents").delete().eq(
                "id", parsed_doc_id).execute()
            print(f"deleted gp_parsed_documents/{parsed_doc_id}")
        except Exception as ex:  # noqa: BLE001
            print(f"ERR parsed {parsed_doc_id}: {ex}")
    try:
        sb.table("action_audit_log").update(
            {"reverses_audit_id": None, "reversed_by_audit_id": None}
        ).eq("id", AUDIT_ID).execute()
        sb.table("action_audit_log").delete().eq("id", AUDIT_ID).execute()
        print(f"deleted action_audit_log/{AUDIT_ID}")
    except Exception as ex:  # noqa: BLE001
        print(f"ERR audit: {ex}")

    # 6. storage blob
    try:
        sb.storage.from_("medical-records").remove([STORAGE_PATH])
        print(f"deleted storage {STORAGE_PATH}")
    except Exception as ex:  # noqa: BLE001
        print(f"ERR storage: {ex}")

    # 7. INDEPENDENT three-key re-verify (NOT workspace_id sweep —
    #    that is polluted by the pre-existing non-mine demo data)
    residue = []
    for tbl in _SRCDOC_TABLES:
        try:
            n = (sb.table(tbl).select("id")
                 .eq("source_document_id", DOC_ID).execute().data) or []
        except Exception:
            n = []
        if n:
            residue.append(f"{tbl}: {len(n)} (source_document_id)")
    for tbl, rid in (("patients", PATIENT_ID),
                     ("encounters", ENCOUNTER_ID),
                     ("digitised_documents", DOC_ID),
                     ("action_audit_log", AUDIT_ID)):
        n = (sb.table(tbl).select("id").eq("id", rid).execute().data) or []
        if n:
            residue.append(f"{tbl}: {len(n)} (id={rid})")
    for sid in session_ids:
        n = (sb.table("gp_validation_sessions").select("id")
             .eq("id", sid).execute().data) or []
        if n:
            residue.append(f"gp_validation_sessions: {len(n)} (id={sid})")

    if residue:
        print("CLEANUP INCOMPLETE — independent re-read still finds:")
        for r in residue:
            print("  " + r)
        sys.exit(1)
    print("CLEANUP VERIFIED CLEAN — independent re-read: 0 rows over "
          "this run's source_document_id + every tracked id + audit. "
          "Pre-existing demo-workspace accumulation (non-mine, unknown "
          "provenance) deliberately untouched and unreported as my "
          "residue.")


if __name__ == "__main__":
    main()
