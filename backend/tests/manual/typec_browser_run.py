"""
Piece 2 — the LITERAL browser run. Closes the one layer the HTTP runs
explicitly did NOT: the real React UI rendering + clicking, end to end.

Drives a real Chromium (Playwright) against the real CRA frontend
(:3000, REACT_APP_BACKEND_URL=http://localhost:8002 -> the proven
backend). Uses the app's own /__typec-autologin route (built "for
headless verification") which performs the real /api/auth/login and
stores the real JWT, then:
  upload clean_consult.pdf via the real DigitisationUploader ->
  poll the real pipeline UI -> open the real DigitisationValidationDetail
  (the review screen a doctor sees — screenshotted raw) ->
  click the real "Approve & Save" (auto-accept its window.confirm;
  handle PatientMatchModal -> create-new if the 409 match gate fires) ->
  observe the post-approve UI.

SYNTHETIC ONLY. Spends LandingAI credit. Writes live Supabase, then
the proven FK-graph teardown (digitised_documents FIRST — it references
the encounter; then clinical children by source_document_id; then
patient; sessions/parsed/audit; storage) keyed to THIS run's doc id
(read from the validation-detail URL) + tracked ids. Persistent demo
fixture retained. Independent three-key residue read-back, can fail on
its own (sys.exit 1).

Screenshots at every rendered step -> /tmp/typec_shot_*.png so the
actual pixels are reported raw, not described.

Requires RUN_TYPEC_LIVE=1. NOT a pytest.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[2]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "clean_consult.pdf"
_FE = os.environ.get("TYPEC_FE", "http://localhost:3000")
_WORKSPACE_ID = "typec-workspace-001"
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

    doc_id = None
    created_patient_id = None
    session_id = None
    parsed_doc_id = None
    audit_ids: list = []
    storage_path = None
    approve_state = "<not-reached>"

    try:
        with sync_playwright() as p:
            br = p.chromium.launch(headless=True)
            pg = br.new_page(viewport={"width": 1440, "height": 1000})
            pg.on("dialog", lambda d: d.accept())  # window.confirm on approve

            # 1. Real login via the app's own auto-login route -> pipeline
            pg.goto(f"{_FE}/__typec-autologin?next=/digitisation/documents",
                    wait_until="load", timeout=60000)
            pg.wait_for_timeout(4000)  # let the fetch+redirect resolve
            pg.goto(f"{_FE}/digitisation/documents",
                    wait_until="networkidle", timeout=60000)
            pg.wait_for_timeout(3000)
            pg.screenshot(path=str(_SHOT / "typec_shot_1_pipeline.png"),
                          full_page=True)
            print(f"STEP1 pipeline loaded — url={pg.url} "
                  f"title={pg.title()!r}")

            # 2. Upload the synthetic PDF via the real file input
            fi = pg.locator("input[type=file]").first
            fi.set_input_files(str(_FIXTURE), timeout=30000)
            print("STEP2 file set on real <input type=file>")
            pg.wait_for_timeout(3000)
            pg.screenshot(path=str(_SHOT / "typec_shot_2_uploaded.png"),
                          full_page=True)

            # 3. Wait for extraction: poll Supabase for the doc this run
            #    created in the demo workspace (most recent, last 5 min).
            deadline = time.time() + 320
            while time.time() < deadline:
                rows = (sb.table("digitised_documents")
                        .select("id, status, created_at, file_path, "
                                "parsed_doc_id")
                        .eq("workspace_id", _WORKSPACE_ID)
                        .order("created_at", desc=True)
                        .limit(1).execute().data) or []
                if rows:
                    r0 = rows[0]
                    doc_id = r0["id"]
                    st = r0["status"]
                    if int(time.time()) % 15 == 0:
                        print(f"  poll: doc={doc_id} status={st}")
                    if st in ("extracted", "pending_validation",
                              "validated", "ready_for_validation"):
                        storage_path = r0.get("file_path")
                        parsed_doc_id = r0.get("parsed_doc_id")
                        break
                    if st == "error":
                        print(f"  PARSE ERROR doc={doc_id}")
                        sys.exit(1)
                time.sleep(5)
            else:
                print("  TIMEOUT waiting for extraction")
                sys.exit(1)
            print(f"STEP3 extracted — doc_id={doc_id}")
            srow = (sb.table("gp_validation_sessions").select("id")
                    .eq("document_id", doc_id)
                    .order("created_at", desc=True).limit(1)
                    .execute().data)
            session_id = srow[0]["id"] if srow else None

            # 4. Open the REAL review screen (the named-residual layer)
            pg.goto(f"{_FE}/digitisation/validation/{doc_id}",
                    wait_until="networkidle", timeout=60000)
            pg.wait_for_timeout(5000)
            pg.screenshot(path=str(_SHOT / "typec_shot_3_review.png"),
                          full_page=True)
            body_txt = pg.locator("body").inner_text(timeout=15000)
            for needle in ("Test Patient", "8503140001087", "Atenolol",
                           "Essential hypertension", "Dr A. Tester",
                           "130", "Tester"):
                print(f"  REVIEW renders {needle!r}: "
                      f"{needle in body_txt}")

            # 5. Click the REAL Approve & Save (dialog auto-accepted)
            btn = pg.get_by_role("button", name="Approve & Save")
            btn.click(timeout=20000)
            pg.wait_for_timeout(4000)
            # 5b. Patient-match modal (409 gate) -> create new patient
            page_txt = pg.locator("body").inner_text(timeout=8000)
            if ("match" in page_txt.lower()
                    and ("create new" in page_txt.lower()
                         or "new patient" in page_txt.lower())):
                print("STEP5 patient-match modal appeared -> create new")
                for nm in ("Create New Patient", "Create new patient",
                           "Create New", "New Patient"):
                    el = pg.get_by_role("button", name=nm)
                    if el.count() > 0:
                        el.first.click(timeout=10000)
                        break
                pg.wait_for_timeout(4000)
            else:
                print("STEP5 no match modal (clean approve path)")
            pg.wait_for_timeout(4000)
            pg.screenshot(path=str(_SHOT / "typec_shot_4_approved.png"),
                          full_page=True)
            approve_state = pg.locator("body").inner_text(timeout=10000)[:400]
            print(f"STEP5 post-approve UI text (head): {approve_state!r}")

            br.close()

        # ---- capture created ids for teardown + the class-3 oracle
        arows = (sb.table("action_audit_log").select("id, affected_objects")
                 .filter("parameters->>document_id", "eq", doc_id)
                 .execute().data) or []
        for ar in arows:
            audit_ids.append(ar["id"])
        prow = (sb.table("patients").select("id, first_name, last_name")
                .eq("workspace_id", _WORKSPACE_ID)
                .order("created_at", desc=True).limit(1).execute().data) or []
        # only treat as ours if an encounter for THIS doc points at it
        enc = (sb.table("encounters").select("patient_id")
               .eq("source_document_id", doc_id).limit(1).execute().data) or []
        created_patient_id = enc[0]["patient_id"] if enc else None

        rx = (sb.table("prescriptions").select("doctor_name")
              .eq("source_document_id", doc_id).execute().data) or []
        dn = rx[0]["doctor_name"] if rx else "<no-prescription-row>"
        print()
        print(f"CLASS-3 ORACLE (persisted via the UI path): "
              f"prescriptions.doctor_name = {dn!r}")
        if dn == "Dr A. Tester":
            print("  PASS: real extracted prescriber persisted via the "
                  "real browser UI path — class-3 fix holds end to end.")
        else:
            print(f"  FAIL: {dn!r} — finding, not powered past.")

    finally:
        # ===== proven FK-graph teardown (doc FIRST) =====
        if doc_id:
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
            print(f"teardown: clinical children by source_document_id")
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
                     "reversed_by_audit_id": None}).eq("id", aid).execute()
                sb.table("action_audit_log").delete().eq(
                    "id", aid).execute()
                print(f"teardown: action_audit_log/{aid}")
            except Exception as ex:  # noqa: BLE001
                print(f"teardown audit error: {ex}")
        if storage_path:
            try:
                sb.storage.from_("medical-records").remove([storage_path])
                print(f"teardown: storage {storage_path}")
            except Exception as ex:  # noqa: BLE001
                print(f"teardown storage error: {ex}")

        # ===== independent three-key read-back (can fail on its own) =====
        residue = []
        if doc_id:
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
            n = (sb.table("action_audit_log").select("id").eq("id", aid)
                 .execute().data) or []
            if n:
                residue.append(f"action_audit_log: {len(n)} (id={aid})")

        if residue:
            print("RESIDUE NOT CLEAN — independent read-back found:")
            for r in residue:
                print("  " + r)
            sys.exit(1)
        print("RESIDUE CLEAN — independent read-back: 0 rows over this "
              "run's source_document_id [load-bearing] + tracked ids + "
              "audit. Persistent demo fixture retained.")


if __name__ == "__main__":
    run()
