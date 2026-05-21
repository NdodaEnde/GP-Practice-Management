"""
Piece 2 — SINGLE re-verified real-path run AFTER migration 030
(class-3 prescriber-provenance fix), applied by the principal's hand.

Same real authenticated HTTP drive as typec_live_http_run.py
(/api/auth/login JWT -> require_capability -> from_user -> the audited
action -> migration-015's now-030-replaced execute_action_promote_document)
— NOT the blind harness, NOT a reconstructed ActorContext.

THE LOAD-BEARING ASSERTION (singular this run): the fixture is
single-prescriber ("Signed: Dr A. Tester" -> extraction
medications[].prescribed_by = "Dr A. Tester"), so the three-case CASE
must hit the exactly-one-distinct branch and persist
    prescriptions.doctor_name == 'Dr A. Tester'
NOT the sentinel '(Digitised record — prescriber not extracted)'
(fix didn't take / didn't reach this path) and NOT any other value
(three-case logic produced something the source doesn't support — the
class-3 lie in a new payload). Asserted literally, not by plausibility.

TEARDOWN — REBUILT FROM THE OBSERVED FK GRAPH, not the discarded
harness idiom that imported the blind spot and caused the prior
residue-safety failure. The observed FK error last run was
digitised_documents_encounter_id_fkey: digitised_documents.encounter_id
-> encounters.id, stamped by the real approve path (digitisation.py:1338)
which the harness never exercised. FK-correct delete order, proven by
the independently-verified corrective _typec_run_cleanup.py:
  1. digitised_documents row FIRST (it references encounter + patient;
     deleting it frees both)
  2. prescription_items -> prescriptions, diagnoses, vitals, allergies,
     encounters  (all by source_document_id = this run's unique uuid;
     prescription_items DOES carry source_document_id — migration
     015:1019-1036 / 030)
  3. patients by tracked id (no source_document_id column)
  4. sessions / parsed / audit (audit: null self-FKs then delete)
  5. storage blob
Persistent demo fixture (tenant/workspace/user/entitlement) deliberately
NOT torn down (idempotent by design).

INDEPENDENT three-key residue read-back that CAN FAIL ON ITS OWN
(sys.exit 1): source_document_id sweep [load-bearing, per-upload uuid,
cannot collide with the pre-existing non-mine demo accumulation] +
tracked per-run ids + audit. The workspace_id-clinical sweep is
DELIBERATELY NOT a residue signal here — the demo workspace carries
pre-existing non-mine rows (observed last run: 17 encounters etc.);
keying residue off it would be a false positive. This run creates the
most clinical rows and uses the rebuilt teardown, so the teardown doing
its job IS part of what is being verified — the prior teardown failed
exactly here.

Requires RUN_TYPEC_LIVE=1. NOT a pytest. Credit + live write.
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
_BASE = os.environ.get("TYPEC_BASE", "http://127.0.0.1:8002")
_EMAIL = "typec@surgiscan.com"
_PASSWORD = "password123"
_WORKSPACE_ID = "typec-workspace-001"   # persistent fixture — NOT torn down
_EXPECT_PRESCRIBER = "Dr A. Tester"     # the literal load-bearing oracle

# FK-correct order, from the observed graph (NOT the harness idiom).
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
        print(f"REFUSING: synthetic fixture missing: {_FIXTURE}")
        sys.exit(2)

    import httpx
    _load_env()
    sb = _client()

    doc_id = None
    session_id = None
    parsed_doc_id = None
    audit_ids: list = []
    created_patient_id = None
    storage_path = None
    persisted_doctor_name = "<not-read>"

    try:
        with httpx.Client(base_url=_BASE, timeout=60.0) as c:
            r = c.post("/api/auth/login",
                       json={"email": _EMAIL, "password": _PASSWORD})
            print(f"LOGIN actuals: status={r.status_code}")
            if r.status_code != 200:
                print(f"  body={r.text[:800]}")
                sys.exit(1)
            lj = r.json()
            token = lj["access_token"]
            caps = (lj.get("user") or {}).get("capabilities")
            print(f"  user.capabilities={caps}")
            H = {"Authorization": f"Bearer {token}"}

            with open(_FIXTURE, "rb") as fh:
                r = c.post("/api/digitisation/upload", headers=H,
                           files={"file": ("clean_consult.pdf", fh,
                                            "application/pdf")})
            print(f"UPLOAD actuals: status={r.status_code} body={r.text[:400]}")
            if r.status_code != 200:
                sys.exit(1)
            doc_id = r.json()["document_id"]
            storage_path = r.json().get("file_path")
            print(f"  document_id={doc_id}")

            deadline = time.time() + 300
            last = None
            while time.time() < deadline:
                r = c.get(f"/api/digitisation/documents/{doc_id}", headers=H)
                if r.status_code == 200:
                    body = r.json()
                    st = (body.get("document") or body).get("status") \
                        if isinstance(body, dict) else None
                    st = st or body.get("status")
                    if st != last:
                        print(f"  poll: status={st} "
                              f"(t={300-int(deadline-time.time())}s)")
                        last = st
                    if st in ("extracted", "pending_validation",
                              "validated", "ready_for_validation"):
                        break
                    if st == "error":
                        print(f"  PARSE ERROR body={r.text[:600]}")
                        sys.exit(1)
                time.sleep(5)
            else:
                print("  TIMEOUT waiting for extraction")
                sys.exit(1)

            srow = (sb.table("gp_validation_sessions").select("id")
                    .eq("document_id", doc_id)
                    .order("created_at", desc=True).limit(1).execute().data)
            session_id = srow[0]["id"] if srow else None
            drow = (sb.table("digitised_documents").select("parsed_doc_id")
                    .eq("id", doc_id).limit(1).execute().data)
            parsed_doc_id = drow[0].get("parsed_doc_id") if drow else None

            r = c.get(f"/api/digitisation/validation/{doc_id}", headers=H)
            print(f"VALIDATION-DETAIL actuals: status={r.status_code}")
            ex = (r.json() if r.status_code == 200 else {}).get(
                "extractions") or {}
            print("  EXTRACTION (leg-1 oracle source) — raw:")
            for k in ("patient_demographics", "diagnoses", "medications",
                      "vitals_history", "progress_notes"):
                print(f"    {k}: {json.dumps(ex.get(k), default=str)}")

            r = c.post(f"/api/digitisation/validation/{doc_id}/approve",
                       headers=H, json={"create_new_patient": True})
            print(f"APPROVE actuals: status={r.status_code}")
            aj = r.json() if r.headers.get("content-type", "").startswith(
                "application/json") else {"_raw": r.text[:800]}
            print(f"  PROMOTE outcome (verbatim): "
                  f"{json.dumps(aj, default=str)[:1500]}")
            promo = (aj or {}).get("promotion") or {}
            created_patient_id = promo.get("patient_id")
            if promo.get("audit_id"):
                audit_ids.append(promo["audit_id"])

            r = c.get(f"/api/digitisation/validation/{doc_id}/history",
                      headers=H)
            print(f"HISTORY actuals: status={r.status_code} "
                  f"body={json.dumps(r.json(), default=str)[:900] if r.status_code==200 else r.text[:300]}")

        arows = (sb.table("action_audit_log").select("id, affected_objects")
                 .filter("parameters->>document_id", "eq", doc_id)
                 .execute().data) or []
        for ar in arows:
            if ar["id"] not in audit_ids:
                audit_ids.append(ar["id"])

        # ---- PERSISTED rows raw — leg-2; the load-bearing one is
        #      prescriptions.doctor_name (printed BEFORE teardown).
        if created_patient_id:
            prow = (sb.table("patients").select("*")
                    .eq("id", created_patient_id).execute().data)
            print(f"PERSISTED patient({created_patient_id}): "
                  f"{json.dumps(prow[0] if prow else None, default=str)}")
        for tbl in ("encounters", "diagnoses", "vitals", "prescriptions",
                    "prescription_items"):
            try:
                rows = (sb.table(tbl).select("*")
                        .eq("source_document_id", doc_id).execute().data) or []
            except Exception:
                rows = []
            print(f"PERSISTED {tbl} (source_document_id={doc_id}): "
                  f"{json.dumps(rows, default=str)[:1400]}")
            if tbl == "prescriptions" and rows:
                persisted_doctor_name = rows[0].get("doctor_name")

        # ---- THE singular load-bearing assertion, literal, adversarial
        print()
        print(f"CLASS-3 ORACLE: prescriptions.doctor_name = "
              f"{persisted_doctor_name!r}")
        _SENTINEL = "(Digitised record — prescriber not extracted)"
        if persisted_doctor_name == _EXPECT_PRESCRIBER:
            print(f"  PASS: == {_EXPECT_PRESCRIBER!r} (the real extracted "
                  f"value; exactly-one-distinct branch; class-3 lie fixed "
                  f"on the real path).")
        elif persisted_doctor_name == _SENTINEL:
            print("  FAIL: still the SENTINEL — the fix did not take or "
                  "did not reach this path. This is the finding.")
        else:
            print(f"  FAIL: neither the real value nor the sentinel — the "
                  f"three-case logic produced {persisted_doctor_name!r}, "
                  f"a value the source does not support (class-3 lie, new "
                  f"payload). This is the finding.")

    finally:
        # ===== TEARDOWN — FK-correct, from the observed graph =====
        # 1. digitised_documents FIRST (references encounter + patient).
        if doc_id:
            try:
                sb.table("digitised_documents").delete().eq(
                    "id", doc_id).execute()
                print(f"teardown: deleted digitised_documents/{doc_id}")
            except Exception as ex:  # noqa: BLE001
                print(f"teardown digitised_documents error: {ex}")
        # 2. clinical children -> encounter, by this run's unique uuid.
        if doc_id:
            for tbl in _SRCDOC_TABLES:
                try:
                    sb.table(tbl).delete().eq(
                        "source_document_id", doc_id).execute()
                    print(f"teardown: deleted {tbl} by "
                          f"source_document_id={doc_id}")
                except Exception as ex:  # noqa: BLE001
                    print(f"teardown {tbl} error: {ex}")
        # 3. patient by tracked id (no source_document_id column).
        if created_patient_id:
            try:
                sb.table("patients").delete().eq(
                    "id", created_patient_id).execute()
                print(f"teardown: deleted patients/{created_patient_id}")
            except Exception as ex:  # noqa: BLE001
                print(f"teardown patients error: {ex}")
        # 4. sessions / parsed / audit.
        if session_id:
            try:
                sb.table("gp_validation_sessions").delete().eq(
                    "id", session_id).execute()
                print(f"teardown: deleted gp_validation_sessions/{session_id}")
            except Exception as ex:  # noqa: BLE001
                print(f"teardown session error: {ex}")
        if parsed_doc_id:
            try:
                sb.table("gp_parsed_documents").delete().eq(
                    "id", parsed_doc_id).execute()
                print(f"teardown: deleted gp_parsed_documents/{parsed_doc_id}")
            except Exception as ex:  # noqa: BLE001
                print(f"teardown parsed error: {ex}")
        for aid in audit_ids:
            try:
                sb.table("action_audit_log").update(
                    {"reverses_audit_id": None,
                     "reversed_by_audit_id": None}).eq("id", aid).execute()
                sb.table("action_audit_log").delete().eq(
                    "id", aid).execute()
                print(f"teardown: deleted action_audit_log/{aid}")
            except Exception as ex:  # noqa: BLE001
                print(f"teardown audit {aid} error: {ex}")
        # 5. storage blob.
        if storage_path:
            try:
                sb.storage.from_("medical-records").remove([storage_path])
                print(f"teardown: deleted storage {storage_path}")
            except Exception as ex:  # noqa: BLE001
                print(f"teardown storage error: {ex}")

        # ===== INDEPENDENT three-key read-back (can fail on its own) =====
        residue = []
        if doc_id:
            for tbl in _SRCDOC_TABLES:
                try:
                    n = (sb.table(tbl).select("id")
                         .eq("source_document_id", doc_id).execute().data) or []
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
            n = (sb.table(tbl).select("id").eq("id", rid).execute().data) or []
            if n:
                residue.append(f"{tbl}: {len(n)} (id={rid})")
        for aid in audit_ids:
            n = (sb.table("action_audit_log").select("id")
                 .eq("id", aid).execute().data) or []
            if n:
                residue.append(f"action_audit_log: {len(n)} (id={aid})")

        if residue:
            print("RESIDUE NOT CLEAN — independent read-back found:")
            for r in residue:
                print("  " + r)
            sys.exit(1)
        print("RESIDUE CLEAN — independent read-back: 0 rows over this "
              "run's source_document_id [load-bearing] + tracked per-run "
              "ids + audit. Persistent demo fixture deliberately retained; "
              "workspace_id-clinical sweep intentionally NOT a residue "
              "signal (pre-existing non-mine accumulation).")


if __name__ == "__main__":
    run()
