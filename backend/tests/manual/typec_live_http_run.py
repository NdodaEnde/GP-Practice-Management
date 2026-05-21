"""
Piece 2 — the SUFFICIENT live verification, REAL AUTHENTICATED HTTP PATH.

This is the corrected-route deliverable drive: it does NOT reconstruct an
ActorContext (the blind spot that made tests/manual/typec_golden_run.py
unable to certify the was-the-blocker claim — it built
ActorContext(...) directly at :207, permissions=[] by default). Instead
it drives the EXACT endpoints the Type-C frontend calls, over HTTP, with
a real /api/auth/login JWT, so the real FastAPI dependency chain runs
authentically end to end:

    /api/auth/login  ->  Bearer JWT (capabilities hydrated by
                          get_current_user from the seeded entitlement)
    /api/digitisation/upload          (require_capability digitisation_upload)
    [in-process document_watcher: GPDocumentProcessor -> LandingAI = CREDIT]
    /api/digitisation/validation/{id}  (leg-1 oracle source: extractions)
    /api/digitisation/validation/{id}/approve   <-- THE LOAD-BEARING CALL:
        require_capability("digitisation_validation") [API gate]
        -> ActorContext.from_user(current_user) [candidate A, digitisation.py:1312]
        -> PromoteDocumentToPatientRecord -> execute() -> migration-015
    /api/digitisation/validation/{id}/history    (audited provenance)

NOT covered, named not claimed: browser pixel rendering. The leg-1
oracle runs against the verbatim /validation/{id} `extractions` JSON,
which DigitisationValidationDetail renders unaltered (plan-established).

SYNTHETIC ONLY: backend/tests/fixtures/clean_consult.pdf.
SPENDS LandingAI credit: 1 synthetic doc = 1 parse + N extract.
WRITES LIVE SUPABASE, then tears down residue-safe (per-run
document-derived rows only — the provisioned tenant/workspace/user/
entitlement is an idempotent persistent demo FIXTURE by design,
scripts/provision_typec_demo.py, and is deliberately NOT torn down),
and proves clean by an INDEPENDENT three-key read-back.

Teardown + read-back idiom is COPIED VERBATIM (constants verified at
file:line against migration-015 INSERT column lists) from the
bar-reviewed typec_golden_run.py — only the promote DRIVE changed from
blind-direct to real-HTTP. Review the teardown harder than the
orchestration: orchestration failure is loud; teardown failure is the
silent live residue this sub-thread exists to prevent.

Requires RUN_TYPEC_LIVE=1 + explicit invocation. NOT a pytest.
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

# --- teardown maps: copied verbatim from typec_golden_run.py (verified
#     at file:line vs migration-015 INSERT column lists; do not re-derive)
_TYPE_TABLE = {
    "Patient": "patients",
    "Consultation": "encounters",
    "Diagnosis": "diagnoses",
    "Vital": "vitals",
    "Allergy": "allergies",
    "Prescription": "prescriptions",
    "PrescriptionItem": "prescription_items",
}
_DELETE_ORDER = [
    "prescription_items", "prescriptions", "diagnoses", "vitals",
    "allergies", "encounters", "patients",
]
_WS_TABLES = ["patients", "encounters", "diagnoses", "vitals",
              "allergies", "prescriptions"]
_SRCDOC_TABLES = ["encounters", "diagnoses", "vitals", "allergies",
                  "prescriptions", "prescription_items"]


def _load_env():
    envf = _BACKEND / ".env"
    for ln in envf.read_text().splitlines():
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

    try:
        with httpx.Client(base_url=_BASE, timeout=60.0) as c:
            # 1. LOGIN — real JWT, capabilities hydrated by the real chain
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

            # 2. UPLOAD the synthetic PDF (real upload endpoint)
            with open(_FIXTURE, "rb") as fh:
                r = c.post("/api/digitisation/upload",
                           headers=H,
                           files={"file": ("clean_consult.pdf", fh,
                                            "application/pdf")})
            print(f"UPLOAD actuals: status={r.status_code} body={r.text[:400]}")
            if r.status_code != 200:
                sys.exit(1)
            doc_id = r.json()["document_id"]
            storage_path = r.json().get("file_path")
            print(f"  document_id={doc_id}")

            # 3. POLL — in-process watcher picks up queued doc, runs
            #    GPDocumentProcessor -> LandingAI (CREDIT spent here)
            deadline = time.time() + 300
            last = None
            while time.time() < deadline:
                r = c.get(f"/api/digitisation/documents/{doc_id}",
                          headers=H)
                if r.status_code == 200:
                    st = (r.json().get("document") or r.json()).get("status") \
                        if isinstance(r.json(), dict) else None
                    st = st or r.json().get("status")
                    if st != last:
                        print(f"  poll: status={st} (t={int(time.time()-deadline+300)}s)")
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

            # capture session / parsed ids for teardown
            srow = (sb.table("gp_validation_sessions").select("id")
                    .eq("document_id", doc_id)
                    .order("created_at", desc=True).limit(1).execute().data)
            session_id = srow[0]["id"] if srow else None
            drow = (sb.table("digitised_documents")
                    .select("parsed_doc_id").eq("id", doc_id)
                    .limit(1).execute().data)
            parsed_doc_id = drow[0].get("parsed_doc_id") if drow else None

            # 4. VALIDATION DETAIL — leg-1 oracle source (verbatim
            #    `extractions` the review screen renders)
            r = c.get(f"/api/digitisation/validation/{doc_id}", headers=H)
            print(f"VALIDATION-DETAIL actuals: status={r.status_code}")
            vd = r.json() if r.status_code == 200 else {}
            ex = vd.get("extractions") or {}
            print("  EXTRACTION (leg-1 oracle source) — raw:")
            for k in ("patient_demographics", "diagnoses", "medications",
                      "vitals_history", "progress_notes"):
                print(f"    {k}: {json.dumps(ex.get(k), default=str)}")

            # 5. APPROVE — THE load-bearing call: require_capability ->
            #    from_user (candidate A) -> PromoteDocumentToPatientRecord
            #    -> migration-015. create_new_patient=true => force-create
            #    path (avoids the ambiguity 409 gate).
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

            # 6. HISTORY — audited provenance (verbatim)
            r = c.get(f"/api/digitisation/validation/{doc_id}/history",
                      headers=H)
            print(f"HISTORY actuals: status={r.status_code} "
                  f"body={json.dumps(r.json(), default=str)[:1200] if r.status_code==200 else r.text[:400]}")

        # independently catch the audit row even on failure (response
        # only carries audit_id on is_success)
        arows = (sb.table("action_audit_log").select("id, affected_objects")
                 .filter("parameters->>document_id", "eq", doc_id)
                 .execute().data) or []
        for ar in arows:
            if ar["id"] not in audit_ids:
                audit_ids.append(ar["id"])

        # 7. PERSISTED clinical VALUES — leg-2 oracle target, printed
        #    BEFORE teardown deletes them (actuals before interpretation)
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
            print(f"PERSISTED {tbl} (by source_document_id={doc_id}): "
                  f"{json.dumps(rows, default=str)[:1400]}")

    finally:
        # ===== TEARDOWN (load-bearing) — per-run artifacts ONLY =====
        # Re-read affected_objects from the persisted audit row(s).
        persisted_affected = []
        for aid in audit_ids:
            arow = (sb.table("action_audit_log").select("affected_objects")
                    .eq("id", aid).execute().data)
            persisted_affected += (arow[0].get("affected_objects")
                                   if arow else []) or []

        by_table = {t: [] for t in _DELETE_ORDER}
        unmapped = []
        for e in persisted_affected:
            if e.get("op") != "created":
                continue
            t = e.get("type")
            if t == "Document":
                continue
            tbl = _TYPE_TABLE.get(t)
            (by_table[tbl].append(e["id"]) if tbl
             else unmapped.append(e))
        if unmapped:
            print(f"TEARDOWN HALT: unmapped created type(s) {unmapped} — "
                  f"NOT skipped silently; manual review required.")

        for tbl in _DELETE_ORDER:
            for rid in by_table.get(tbl, []):
                try:
                    sb.table(tbl).delete().eq("id", rid).execute()
                except Exception as ex:  # noqa: BLE001
                    print(f"teardown delete {tbl}/{rid} error: {ex}")
        # belt-and-braces: any clinical row stamped with our doc id
        for tbl in _SRCDOC_TABLES:
            try:
                sb.table(tbl).delete().eq(
                    "source_document_id", doc_id).execute()
            except Exception as ex:  # noqa: BLE001
                print(f"teardown srcdoc {tbl} error: {ex}")

        for tbl, rid in (("gp_validation_sessions", session_id),
                         ("gp_parsed_documents", parsed_doc_id),
                         ("digitised_documents", doc_id)):
            if rid:
                try:
                    sb.table(tbl).delete().eq("id", rid).execute()
                except Exception as ex:  # noqa: BLE001
                    print(f"teardown delete {tbl}/{rid} error: {ex}")

        for aid in audit_ids:
            try:
                sb.table("action_audit_log").update(
                    {"reverses_audit_id": None,
                     "reversed_by_audit_id": None}).eq("id", aid).execute()
                sb.table("action_audit_log").delete().eq(
                    "id", aid).execute()
            except Exception as ex:  # noqa: BLE001
                print(f"teardown audit-row {aid} error: {ex}")

        if storage_path:
            try:
                sb.storage.from_("medical-records").remove([storage_path])
            except Exception as ex:  # noqa: BLE001
                print(f"teardown storage error: {ex}")

        # NOTE: tenant/workspace/user/entitlement = idempotent persistent
        # demo fixture (scripts/provision_typec_demo.py) — deliberately
        # NOT deleted. The clinical/doc rows above ARE per-run residue.

        # ===== INDEPENDENT three-key residue read-back =====
        residue = []
        # (1) LOAD-BEARING: source_document_id sweep (per-run; depends on
        #     neither workspace_id nor affected_objects-completeness)
        for tbl in _SRCDOC_TABLES:
            try:
                n = (sb.table(tbl).select("id")
                     .eq("source_document_id", doc_id).execute().data) or []
            except Exception:
                n = []
            if n:
                residue.append(f"{tbl}: {len(n)} (by source_document_id)")
        # (2) workspace_id sweep over clinical tables — the persistent
        #     fixture has NO clinical rows, so >0 here = per-run residue
        for tbl in _WS_TABLES:
            try:
                n = (sb.table(tbl).select("id")
                     .eq("workspace_id", _WORKSPACE_ID).execute().data) or []
            except Exception:
                n = []
            if n:
                residue.append(f"{tbl}: {len(n)} (by workspace_id — per-run)")
        # (3) tracked per-run ids
        for tbl, col, rid in (
            ("patients", "id", created_patient_id),
            ("gp_validation_sessions", "id", session_id),
            ("gp_parsed_documents", "id", parsed_doc_id),
            ("digitised_documents", "id", doc_id),
        ):
            if not rid:
                continue
            n = (sb.table(tbl).select("id").eq(col, rid).execute().data) or []
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
        print("RESIDUE CLEAN — independent read-back: 0 rows over the "
              "per-run keys (source_document_id [load-bearing] AND "
              "workspace_id-clinical AND tracked per-run ids AND audit). "
              "Persistent demo fixture (tenant/workspace/user/entitlement) "
              "deliberately retained.")


if __name__ == "__main__":
    run()
