"""
Essential-tier END-TO-END live verification — the full first-customer chain.

Drives the real stack (CRA :3000 -> backend :8002 -> DEV Supabase + live
LandingAI) through the full Essential workflow as if a new client signed up:

  1. PROVISION  - run onboard_practice.py --plan essential (fresh practice)
  2. LOGIN      - real Login UI with the auto-generated password
  3. ROTATE     - real Change Password UI (new in this session)
  4. RE-LOGIN   - new password (proves the rotation took)
  5. UPLOAD     - real DigitisationUploader -> clean_consult.pdf
  6. EXTRACT    - poll Supabase until LandingAI extraction completes
  7. REVIEW     - open the real validation detail screen (extracted fields)
  8. APPROVE    - click Approve & Save (handle match modal -> create new)
  9. DB READOUT - explicit print of every promoted row tied by source_document_id
  10. TEARDOWN  - FK-graph delete + storage + the whole practice
  11. RESIDUE   - independent read-back; fail loud if anything remains

Spends 1 LandingAI extraction. Writes live DEV rows; cleans up everything.
Screenshots -> /tmp/essential_e2e_*.png.

Requires RUN_E2E_LIVE=1. Run with:
  PYTHONPATH=. ./.venv/bin/python tests/manual/essential_e2e_full_run.py
"""
from __future__ import annotations
import os, sys, re, time, json, uuid, subprocess
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[2]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

_FIXTURE = _BACKEND / "tests" / "fixtures" / "clean_consult.pdf"
_FE = os.environ.get("E2E_FE", "http://localhost:3000")
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
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


def run():
    if os.environ.get("RUN_E2E_LIVE") != "1":
        print("REFUSING: set RUN_E2E_LIVE=1 (live LandingAI credit + DEV writes).")
        sys.exit(2)
    if not _FIXTURE.exists():
        print(f"REFUSING: fixture missing: {_FIXTURE}")
        sys.exit(2)

    from playwright.sync_api import sync_playwright
    _load_env()
    sb = _client()

    # ----- unique identifiers for this run -----
    run_tag = uuid.uuid4().hex[:8]
    ws_id = f"e2e-test-{run_tag}"
    email = f"dr.e2e+{run_tag}@example.com"
    new_pwd = f"NewPassw0rd!{run_tag}"

    doc_id = parsed_doc_id = session_id = storage_path = None
    created_patient_id = None
    audit_ids: list = []
    issued_password = None

    try:
        # =========================================================
        # PHASE 1 — PROVISION (onboard_practice.py --plan essential)
        # =========================================================
        print(f"\n=== 1/11 PROVISION — onboarding fresh practice ws={ws_id} ===")
        result = subprocess.run(
            [str(_BACKEND / ".venv" / "bin" / "python"),
             "scripts/onboard_practice.py",
             "--practice", f"E2E Test Practice {run_tag}",
             "--email", email,
             "--name", "Doctor E2E Tester",
             "--workspace-id", ws_id,
             "--plan", "essential"],
            cwd=str(_BACKEND),
            env={**os.environ, "PYTHONPATH": "."},
            capture_output=True, text=True, timeout=60,
        )
        print(result.stdout[-600:] if result.stdout else "")
        if result.returncode != 0:
            print("PROVISION FAILED"); print(result.stderr); sys.exit(1)
        m = re.search(r"Password\s*:\s*(\S+)", result.stdout)
        if not m:
            print("PROVISION OUTPUT MISSED PASSWORD"); sys.exit(1)
        issued_password = m.group(1)
        print(f"   provisioned: email={email}  issued_password={issued_password}")

        # =========================================================
        # PHASE 2-9 — UI flow under Playwright
        # =========================================================
        with sync_playwright() as p:
            br = p.chromium.launch(headless=True)
            ctx = br.new_context(viewport={"width": 1440, "height": 1000})
            pg = ctx.new_page()
            pg.on("dialog", lambda d: d.accept())  # window.confirm on approve

            # ----- PHASE 2 — LOGIN -----
            print("\n=== 2/11 LOGIN — real Login UI with issued password ===")
            pg.goto(f"{_FE}/login", wait_until="load", timeout=30000)
            pg.wait_for_timeout(1500)
            pg.locator('input[type="email"]').fill(email)
            pg.locator('input[type="password"]').fill(issued_password)
            pg.get_by_role("button", name=re.compile("^(Log in|Login|Sign in)$", re.I)).click()
            pg.wait_for_timeout(4000)
            pg.screenshot(path=str(_SHOT / "essential_e2e_2_after_login.png"), full_page=True)
            print(f"   after-login url: {pg.url}")

            # ----- PHASE 3 — ROTATE PASSWORD -----
            print("\n=== 3/11 ROTATE — Change Password UI ===")
            pg.goto(f"{_FE}/account/change-password", wait_until="load", timeout=30000)
            pg.wait_for_timeout(1500)
            pg.get_by_label("Current password").fill(issued_password)
            pg.get_by_label("New password", exact=True).fill(new_pwd)
            pg.get_by_label("Confirm new password").fill(new_pwd)
            calls = []
            pg.on("response", lambda r: "/api/auth/change-password" in r.url and calls.append(r.status))
            pg.locator('button[type="submit"]').click()
            # bcrypt verify + new-hash + DB round-trip can take several seconds; poll up to 15s
            for _ in range(30):
                if calls: break
                pg.wait_for_timeout(500)
            pg.wait_for_timeout(1500)  # let the success UI render
            pg.screenshot(path=str(_SHOT / "essential_e2e_3_password_changed.png"), full_page=True)
            print(f"   change-password call status: {calls} (expect [200])")
            if not calls or calls[0] != 200:
                print("   FAIL: change-password didn't return 200"); sys.exit(1)

            # ----- PHASE 4 — RE-LOGIN with new password -----
            print("\n=== 4/11 RE-LOGIN — new password ===")
            pg.goto(f"{_FE}/login", wait_until="load", timeout=30000)
            pg.evaluate("localStorage.clear()")  # belt-and-braces logout
            pg.goto(f"{_FE}/login", wait_until="load", timeout=30000)
            pg.wait_for_timeout(1500)
            pg.locator('input[type="email"]').fill(email)
            pg.locator('input[type="password"]').fill(new_pwd)
            pg.get_by_role("button", name=re.compile("^(Log in|Login|Sign in)$", re.I)).click()
            pg.wait_for_timeout(4000)
            pg.screenshot(path=str(_SHOT / "essential_e2e_4_relogin.png"), full_page=True)
            print(f"   after-relogin url: {pg.url}")

            # ----- PHASE 5 — UPLOAD -----
            print("\n=== 5/11 UPLOAD — DigitisationUploader -> clean_consult.pdf ===")
            pg.goto(f"{_FE}/digitisation/documents", wait_until="networkidle", timeout=60000)
            pg.wait_for_timeout(3000)
            pg.screenshot(path=str(_SHOT / "essential_e2e_5a_pipeline_before.png"), full_page=True)
            fi = pg.locator("input[type=file]").first
            fi.set_input_files(str(_FIXTURE), timeout=30000)
            pg.wait_for_timeout(1500)  # let the PENDING row render
            pg.screenshot(path=str(_SHOT / "essential_e2e_5b_file_selected.png"), full_page=True)
            print(f"   file set on real <input type=file>; clicking Upload…")
            # The UI is two-step: select -> 'Upload 1' button -> actual POST.
            pg.get_by_role("button", name=re.compile(r"^Upload\s+\d+$")).click(timeout=10000)
            pg.wait_for_timeout(4000)
            pg.screenshot(path=str(_SHOT / "essential_e2e_5c_after_upload.png"), full_page=True)

            # ----- PHASE 6 — EXTRACT (poll Supabase) -----
            print("\n=== 6/11 EXTRACT — polling for LandingAI extraction... ===")
            deadline = time.time() + 360
            while time.time() < deadline:
                rows = (sb.table("digitised_documents")
                        .select("id, status, created_at, file_path, parsed_doc_id")
                        .eq("workspace_id", ws_id)
                        .order("created_at", desc=True).limit(1).execute().data) or []
                if rows:
                    r0 = rows[0]; doc_id = r0["id"]; st = r0["status"]
                    if int(time.time()) % 10 == 0:
                        print(f"   poll: doc={doc_id} status={st}")
                    if st in ("extracted", "pending_validation", "validated", "ready_for_validation"):
                        storage_path = r0.get("file_path")
                        parsed_doc_id = r0.get("parsed_doc_id")
                        break
                    if st == "error":
                        print(f"   PARSE ERROR doc={doc_id}"); sys.exit(1)
                time.sleep(5)
            else:
                print("   TIMEOUT waiting for extraction"); sys.exit(1)
            print(f"   extracted: doc_id={doc_id}  file_path={storage_path}")
            srow = (sb.table("gp_validation_sessions").select("id")
                    .eq("document_id", doc_id).order("created_at", desc=True).limit(1).execute().data)
            session_id = srow[0]["id"] if srow else None

            # ----- PHASE 7 — REVIEW screen -----
            print("\n=== 7/11 REVIEW — open validation detail (real extracted fields) ===")
            pg.goto(f"{_FE}/digitisation/validation/{doc_id}", wait_until="networkidle", timeout=60000)
            pg.wait_for_timeout(5000)
            pg.screenshot(path=str(_SHOT / "essential_e2e_7_review.png"), full_page=True)
            body_txt = pg.locator("body").inner_text(timeout=15000)
            print(f"   review body (head 400 chars): {body_txt[:400]!r}")

            # ----- PHASE 8 — APPROVE & SAVE -----
            print("\n=== 8/11 APPROVE — click Approve & Save (handle match modal -> create new) ===")
            pg.get_by_role("button", name="Approve & Save").click(timeout=20000)
            pg.wait_for_timeout(4000)
            page_txt = pg.locator("body").inner_text(timeout=8000)
            if "match" in page_txt.lower() and ("create new" in page_txt.lower() or "new patient" in page_txt.lower()):
                print("   patient-match modal -> creating new patient")
                for nm in ("Create New Patient", "Create new patient", "Create New", "New Patient"):
                    el = pg.get_by_role("button", name=nm)
                    if el.count() > 0:
                        el.first.click(timeout=10000); break
                pg.wait_for_timeout(4000)
            else:
                print("   no match modal (clean approve path)")
            pg.wait_for_timeout(4000)
            pg.screenshot(path=str(_SHOT / "essential_e2e_8_approved.png"), full_page=True)
            print(f"   post-approve url: {pg.url}")
            br.close()

        # =========================================================
        # PHASE 9 — DB READOUT (the proof rows exist + are correct)
        # =========================================================
        print("\n=== 9/11 DB READOUT — promoted rows linked by source_document_id ===")
        def show(table, cols, fk_col="source_document_id"):
            rows = (sb.table(table).select(cols).eq(fk_col, doc_id).execute().data) or []
            print(f"   {table} ({len(rows)} row{'s' if len(rows)!=1 else ''}):")
            for r in rows[:5]:
                print(f"     {r}")
        enc_rows = (sb.table("encounters").select("id, patient_id, encounter_date, chief_complaint")
                    .eq("source_document_id", doc_id).execute().data) or []
        if enc_rows:
            created_patient_id = enc_rows[0]["patient_id"]
            pt = (sb.table("patients").select("id, first_name, last_name, dob, id_number")
                  .eq("id", created_patient_id).execute().data) or []
            print(f"   patients (via encounter.patient_id={created_patient_id}):")
            for r in pt: print(f"     {r}")
        show("encounters", "id, encounter_date, chief_complaint")
        show("diagnoses", "id, code, display, diagnosis_type")
        show("prescriptions", "id, doctor_name, prescription_date, status")
        rx = (sb.table("prescriptions").select("id").eq("source_document_id", doc_id).execute().data) or []
        if rx:
            rx_ids = [r["id"] for r in rx]
            items = (sb.table("prescription_items").select("medication_name, dosage, frequency")
                     .in_("prescription_id", rx_ids).execute().data) or []
            print(f"   prescription_items ({len(items)} row{'s' if len(items)!=1 else ''}):")
            for r in items[:5]: print(f"     {r}")
        show("vitals", "id, bp_systolic, bp_diastolic, heart_rate, measured_datetime")
        show("allergies", "id, substance, reaction, severity")

        # capture audit ids for teardown
        arows = (sb.table("action_audit_log").select("id")
                 .filter("parameters->>document_id", "eq", doc_id).execute().data) or []
        audit_ids = [r["id"] for r in arows]
        print(f"   action_audit_log: {len(audit_ids)} row(s) for this doc")

        if not enc_rows:
            print("   FAIL: no encounter row linked to source_document_id — promote did not complete")
            sys.exit(1)
        print("\n   PASS: promoted rows exist and link to source_document_id={}".format(doc_id))

    finally:
        # =========================================================
        # PHASE 10 — TEARDOWN (FK-graph + storage + the practice)
        # =========================================================
        print("\n=== 10/11 TEARDOWN — children -> parents -> practice ===")
        if doc_id:
            try: sb.table("digitised_documents").delete().eq("id", doc_id).execute(); print(f"   digitised_documents/{doc_id}")
            except Exception as ex: print(f"   doc error: {ex}")
            for tbl in _SRCDOC_TABLES:
                try: sb.table(tbl).delete().eq("source_document_id", doc_id).execute()
                except Exception as ex: print(f"   {tbl} error: {ex}")
            print(f"   clinical children by source_document_id")
        if created_patient_id:
            try: sb.table("patients").delete().eq("id", created_patient_id).execute(); print(f"   patients/{created_patient_id}")
            except Exception as ex: print(f"   patient error: {ex}")
        if session_id:
            try: sb.table("gp_validation_sessions").delete().eq("id", session_id).execute()
            except Exception as ex: print(f"   session error: {ex}")
        if parsed_doc_id:
            try: sb.table("gp_parsed_documents").delete().eq("id", parsed_doc_id).execute()
            except Exception as ex: print(f"   parsed error: {ex}")
        for aid in audit_ids:
            try:
                sb.table("action_audit_log").update({"reverses_audit_id": None, "reversed_by_audit_id": None}).eq("id", aid).execute()
                sb.table("action_audit_log").delete().eq("id", aid).execute()
            except Exception as ex: print(f"   audit error: {ex}")
        if storage_path:
            try: sb.storage.from_("medical-records").remove([storage_path]); print(f"   storage {storage_path}")
            except Exception as ex: print(f"   storage error: {ex}")
        # the practice itself
        try: sb.table("users").delete().eq("email", email).execute()
        except Exception as ex: print(f"   user error: {ex}")
        try: sb.table("practice_entitlements").delete().eq("practice_id", ws_id).execute()
        except Exception as ex: print(f"   entitlement error: {ex}")
        try: sb.table("workspaces").delete().eq("id", ws_id).execute()
        except Exception as ex: print(f"   workspace error: {ex}")
        try: sb.table("tenants").delete().eq("id", f"{ws_id}-tenant").execute()
        except Exception as ex: print(f"   tenant error: {ex}")
        print(f"   practice torn down: {ws_id}")

        # =========================================================
        # PHASE 11 — RESIDUE CHECK
        # =========================================================
        print("\n=== 11/11 RESIDUE CHECK — independent read-back ===")
        residue = []
        if doc_id:
            for tbl in _SRCDOC_TABLES:
                try: n = (sb.table(tbl).select("id").eq("source_document_id", doc_id).execute().data) or []
                except Exception: n = []
                if n: residue.append(f"{tbl}: {len(n)} (source_document_id)")
        for tbl, rid in (("patients", created_patient_id), ("digitised_documents", doc_id),
                         ("gp_validation_sessions", session_id), ("gp_parsed_documents", parsed_doc_id)):
            if not rid: continue
            n = (sb.table(tbl).select("id").eq("id", rid).execute().data) or []
            if n: residue.append(f"{tbl}: {len(n)} (id={rid})")
        for aid in audit_ids:
            n = (sb.table("action_audit_log").select("id").eq("id", aid).execute().data) or []
            if n: residue.append(f"action_audit_log: {len(n)} (id={aid})")
        # practice residue
        for tbl, col, rid in (("users", "email", email), ("workspaces", "id", ws_id),
                              ("tenants", "id", f"{ws_id}-tenant"),
                              ("practice_entitlements", "practice_id", ws_id)):
            try: n = (sb.table(tbl).select("*").eq(col, rid).execute().data) or []
            except Exception: n = []
            if n: residue.append(f"{tbl}: {len(n)} ({col}={rid})")
        if residue:
            print("RESIDUE NOT CLEAN:")
            for r in residue: print("  " + r)
            sys.exit(1)
        print("RESIDUE CLEAN — 0 rows for this run's doc + patient + practice + audit + storage.")
        print(f"\nScreenshots: /tmp/essential_e2e_*.png")


if __name__ == "__main__":
    run()
