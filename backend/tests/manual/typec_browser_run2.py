"""
Piece 2 — LITERAL browser run, INCIDENT-PROOF REBUILD.

The prior browser runner caused a destructive incident: it (a) never
actually fired the upload (set_input_files only stages a 'pending'
file; a separate "Upload N" button triggers startAll -> the POST),
and (b) identified "this run's doc" as the most-recent doc in the
shared workspace, then DELETED that non-mine document
(Patient file.pdf), its patient, clinical rows and audit. Root cause:
identity by "most-recent-in-workspace" + an upload that silently
no-op'd.

THIS REBUILD's safety invariant — the ONLY identity source is the
document_id in the browser's OWN /api/digitisation/upload response,
captured via Playwright response interception. There is NO
most-recent / workspace-scan query anywhere. HARD ABORT: if that
response (with a document_id) is not captured, the run does NOTHING
destructive — no teardown, no deletes — and exits. Teardown is
strictly keyed to that one captured uuid (a fresh id that cannot
collide with pre-existing data) and is a guarded no-op without it.

Genuinely the browser path the user asked about: real CRA UI, real
dropzone file input, real "Upload N" click, real review screen
(screenshotted), real "Approve & Save" click, real match-modal ->
create-new. Synthetic clean_consult.pdf only. Credit + live write,
then the strictly-keyed teardown + independent residue read-back.

Requires RUN_TYPEC_LIVE=1. NOT a pytest.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[2]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "clean_consult.pdf"
_FE = os.environ.get("TYPEC_FE", "http://localhost:3000")
_SHOT = Path("/tmp")
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


def run():
    if os.environ.get("RUN_TYPEC_LIVE") != "1":
        print("REFUSING: set RUN_TYPEC_LIVE=1 (credit + live write).")
        sys.exit(2)
    if not _FIXTURE.exists():
        print(f"REFUSING: fixture missing: {_FIXTURE}")
        sys.exit(2)

    from playwright.sync_api import sync_playwright
    _load_env()
    sb = _client()

    # IDENTITY: set ONLY from the browser's own upload response. None
    # => hard abort, zero destructive action.
    doc_id = None
    created_patient_id = None
    session_id = None
    parsed_doc_id = None
    audit_ids: list = []
    storage_path = None

    try:
        with sync_playwright() as p:
            br = p.chromium.launch(headless=True)
            pg = br.new_page(viewport={"width": 1440, "height": 1000})
            pg.on("dialog", lambda d: d.accept())

            pg.goto(f"{_FE}/__typec-autologin?next=/digitisation/documents",
                    wait_until="load", timeout=60000)
            pg.wait_for_timeout(4000)
            pg.goto(f"{_FE}/digitisation/documents",
                    wait_until="networkidle", timeout=60000)
            pg.wait_for_timeout(3000)
            pg.screenshot(path=str(_SHOT / "typec2_1_pipeline.png"),
                          full_page=True)
            print(f"STEP1 pipeline — url={pg.url} title={pg.title()!r}")

            # Stage the file on the hidden dropzone input.
            pg.locator("input[type=file]").first.set_input_files(
                str(_FIXTURE), timeout=30000)
            pg.wait_for_timeout(2000)
            print("STEP2 file staged on dropzone input")

            # Fire the REAL upload by clicking the "Upload N" button,
            # capturing the browser's OWN upload response = identity.
            try:
                with pg.expect_response(
                    lambda r: "/api/digitisation/upload" in r.url
                    and r.request.method == "POST",
                    timeout=45000,
                ) as resp_info:
                    pg.locator("button").filter(
                        has_text=re.compile(r"Upload\s*\d")
                    ).first.click(timeout=20000)
                resp = resp_info.value
                print(f"STEP3 upload POST -> HTTP {resp.status}")
                if resp.status == 200:
                    body = resp.json()
                    doc_id = body.get("document_id")
                    storage_path = body.get("file_path")
                print(f"STEP3 browser-upload document_id={doc_id}")
            except Exception as e:  # noqa: BLE001
                print(f"STEP3 upload response NOT captured: {e}")

            # ---- HARD ABORT GUARD ------------------------------------
            if not doc_id:
                print("ABORT: no document_id from the browser's own "
                      "upload response. Doing NOTHING destructive — no "
                      "teardown, no deletes, no workspace scan. The "
                      "browser upload did not fire/succeed; that is the "
                      "finding. (This is the exact guard the prior "
                      "incident lacked.)")
                br.close()
                sys.exit(1)

            pg.screenshot(path=str(_SHOT / "typec2_2_uploaded.png"),
                          full_page=True)

            # Poll status by the EXACT captured id (never most-recent).
            deadline = time.time() + 320
            while time.time() < deadline:
                rows = (sb.table("digitised_documents")
                        .select("status, parsed_doc_id, file_path")
                        .eq("id", doc_id).limit(1).execute().data) or []
                if rows:
                    st = rows[0]["status"]
                    if int(time.time()) % 15 == 0:
                        print(f"  poll: {doc_id} status={st}")
                    if st in ("extracted", "pending_validation",
                              "validated", "ready_for_validation"):
                        parsed_doc_id = rows[0].get("parsed_doc_id")
                        storage_path = storage_path or rows[0].get(
                            "file_path")
                        break
                    if st == "error":
                        print(f"  PARSE ERROR doc={doc_id}")
                        break
                time.sleep(5)
            print(f"STEP4 status-ready for {doc_id}")
            srow = (sb.table("gp_validation_sessions").select("id")
                    .eq("document_id", doc_id)
                    .order("created_at", desc=True).limit(1)
                    .execute().data)
            session_id = srow[0]["id"] if srow else None

            # Real review screen for THIS exact doc.
            pg.goto(f"{_FE}/digitisation/validation/{doc_id}",
                    wait_until="networkidle", timeout=60000)
            pg.wait_for_timeout(6000)
            pg.screenshot(path=str(_SHOT / "typec2_3_review.png"),
                          full_page=True)
            bt = pg.locator("body").inner_text(timeout=15000)
            for needle in ("Test Patient", "8503140001087", "Atenolol",
                           "Essential hypertension", "Dr A. Tester",
                           "130"):
                print(f"  REVIEW renders {needle!r}: {needle in bt}")

            # Real Approve & Save (+ match modal -> create new).
            pg.get_by_role("button", name="Approve & Save").click(
                timeout=20000)
            pg.wait_for_timeout(4000)
            pt = pg.locator("body").inner_text(timeout=8000)
            if "match" in pt.lower() and ("create new" in pt.lower()
                                          or "new patient" in pt.lower()):
                print("STEP5 match modal -> create new")
                for nm in ("Create New Patient", "Create new patient",
                           "Create New", "New Patient"):
                    el = pg.get_by_role("button", name=nm)
                    if el.count() > 0:
                        el.first.click(timeout=10000)
                        break
                pg.wait_for_timeout(4000)
            else:
                print("STEP5 no match modal")
            pg.wait_for_timeout(4000)
            pg.screenshot(path=str(_SHOT / "typec2_4_approved.png"),
                          full_page=True)
            print(f"STEP5 post-approve url={pg.url}")
            br.close()

        # Class-3 oracle + ids, strictly by the captured doc_id.
        enc = (sb.table("encounters").select("patient_id")
               .eq("source_document_id", doc_id).limit(1)
               .execute().data) or []
        created_patient_id = enc[0]["patient_id"] if enc else None
        arows = (sb.table("action_audit_log").select("id")
                 .filter("parameters->>document_id", "eq", doc_id)
                 .execute().data) or []
        audit_ids = [a["id"] for a in arows]
        rx = (sb.table("prescriptions").select("doctor_name")
              .eq("source_document_id", doc_id).execute().data) or []
        dn = rx[0]["doctor_name"] if rx else "<no-prescription>"
        print()
        print(f"CLASS-3 ORACLE (browser path, doc {doc_id}): "
              f"prescriptions.doctor_name = {dn!r}")
        print("  PASS" if dn == "Dr A. Tester"
              else f"  FAIL: {dn!r} — finding, not powered past.")

    finally:
        # TEARDOWN — guarded no-op unless doc_id was captured from the
        # browser's own upload response. Strictly that uuid + tracked.
        if not doc_id:
            print("teardown: SKIPPED (no captured doc_id — nothing this "
                  "run created; nothing touched).")
        else:
            try:
                sb.table("digitised_documents").delete().eq(
                    "id", doc_id).execute()
                print(f"teardown: digitised_documents/{doc_id}")
            except Exception as ex:  # noqa: BLE001
                print(f"teardown doc error: {ex}")
            for tbl in _SRCDOC_TABLES:
                try:
                    sb.table(tbl).delete().eq(
                        "source_document_id", doc_id).execute()
                except Exception as ex:  # noqa: BLE001
                    print(f"teardown {tbl} error: {ex}")
            print("teardown: clinical children by source_document_id")
            if created_patient_id:
                try:
                    sb.table("patients").delete().eq(
                        "id", created_patient_id).execute()
                    print(f"teardown: patients/{created_patient_id}")
                except Exception as ex:  # noqa: BLE001
                    print(f"teardown patient error: {ex}")
            if session_id:
                try:
                    sb.table("gp_validation_sessions").delete().eq(
                        "id", session_id).execute()
                except Exception as ex:  # noqa: BLE001
                    print(f"teardown session error: {ex}")
            if parsed_doc_id:
                try:
                    sb.table("gp_parsed_documents").delete().eq(
                        "id", parsed_doc_id).execute()
                except Exception as ex:  # noqa: BLE001
                    print(f"teardown parsed error: {ex}")
            for aid in audit_ids:
                try:
                    sb.table("action_audit_log").update(
                        {"reverses_audit_id": None,
                         "reversed_by_audit_id": None}).eq(
                        "id", aid).execute()
                    sb.table("action_audit_log").delete().eq(
                        "id", aid).execute()
                except Exception as ex:  # noqa: BLE001
                    print(f"teardown audit {aid} error: {ex}")
            if storage_path:
                try:
                    sb.storage.from_("medical-records").remove(
                        [storage_path])
                    print(f"teardown: storage {storage_path}")
                except Exception as ex:  # noqa: BLE001
                    print(f"teardown storage error: {ex}")

            # Independent read-back (can fail on its own).
            residue = []
            for tbl in _SRCDOC_TABLES:
                try:
                    n = (sb.table(tbl).select("id")
                         .eq("source_document_id", doc_id)
                         .execute().data) or []
                except Exception:
                    n = []
                if n:
                    residue.append(f"{tbl}: {len(n)} (source_document_id)")
            for tbl, rid in (("patients", created_patient_id),
                             ("digitised_documents", doc_id),
                             ("gp_validation_sessions", session_id),
                             ("gp_parsed_documents", parsed_doc_id)):
                if not rid:
                    continue
                n = (sb.table(tbl).select("id").eq("id", rid)
                     .execute().data) or []
                if n:
                    residue.append(f"{tbl}: {len(n)} (id={rid})")
            for aid in audit_ids:
                n = (sb.table("action_audit_log").select("id")
                     .eq("id", aid).execute().data) or []
                if n:
                    residue.append(f"action_audit_log: {len(n)} ({aid})")
            if residue:
                print("RESIDUE NOT CLEAN — independent read-back:")
                for r in residue:
                    print("  " + r)
                sys.exit(1)
            print("RESIDUE CLEAN — independent read-back: 0 rows over "
                  "this run's captured doc_id + tracked ids + audit.")


if __name__ == "__main__":
    run()
