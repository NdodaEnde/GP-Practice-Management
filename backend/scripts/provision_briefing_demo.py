#!/usr/bin/env python3
"""
provision_briefing_demo.py — Phase 3 PR B, carried constraint (ii).

PURPOSE (primary, stated, and the ONLY reason this script exists):
verify the PR B briefing templates' provenance-resolution end-to-end on a
real *entitled* workspace. The only naturally-entitled workspace
(demo-gp-workspace-001, via legacy_full_access_grant) has every clinical
fact NULL-sourced, so its briefing rows all resolve NO_SOURCE and the
OPENABLE/UNRESOLVABLE resolution path is never exercised there. This
script provisions a platform-tier workspace whose facts ARE
document-sourced, so the resolver's OPENABLE path is exercised on an
entitled workspace through the real HTTP surface.

═══════════════════════════════════════════════════════════════════════
LEGITIMACY CONTRACT — read before editing. This is enforced at review,
not by convention.

  The mechanical test of legitimacy (Decision 2 rider): *does this
  script produce clinical facts ONLY by calling the same action code
  path production uses?* It does, in two real-path steps:

    (1) the patient SUBJECT is resolved/created by
        app.services.patient_matching.match_or_create_patient(...) — the
        SAME production helper the /preview-match endpoint calls; the
        `patients` insert lives inside that production code, never in
        this script. (The promote action's preconditions REQUIRE the
        patient to pre-exist, so production always does this first; this
        script mirrors it, it does not shortcut it.)

    (2) every clinical FACT (encounter / diagnosis / prescription /
        vital) is produced EXCLUSIVELY by
        `execute(PromoteDocumentToPatientRecord(...))` — the identical
        executor entrypoint the digitisation "approve" endpoint calls,
        each fact stamped source_document_id = DOC_ID.

  This script itself contains ZERO `.table("<fact>").insert(...)` calls
  for ANY clinical fact table (patients, encounters, diagnoses,
  prescriptions, prescription_items, vitals, allergies, lab_*) — the
  patient insert is production code (step 1), the facts are the executor
  (step 2). **Any direct fact-table INSERT added to THIS script is the
  seeded-to-order anti-pattern and FAILS REVIEW.**

  The only rows this script writes directly are the *prerequisite
  inputs* the production upload→parse→validate flow itself produces
  before a human ever clicks "approve": the tenant, the workspace, its
  practice_entitlements row, a digitised_documents row, a
  gp_validation_sessions row, and a real (minimal) PDF object in the
  `medical-records` bucket. Those are not facts; they are the document
  and its extraction — exactly what ingestion creates and what the
  promote action consumes. Creating them is not seeding facts; it is
  staging the input the real path acts on. (Precedent:
  scripts/provision_typec_demo.py creates workspace + entitlement rows
  the same way.)

PRE-COMMITTED FAILURE-TO-PRODUCE OUTCOME (Decision 2 rider — this wording
travels with the artifact, not only the plan):

  This script seeds via the real promote path, so its facts point at a
  REAL, present digitised_documents row and resolve OPENABLE. A clean
  realistic seed therefore produces OPENABLE and (for any NULL-source
  fact) NO_SOURCE rows, and — expectedly — **no orphaned-source row**,
  because orphans are an artifact of a document being deleted AFTER its
  facts were promoted, not of normal ingestion. This script MUST NOT
  delete the document to manufacture an orphan, and MUST NOT inject an
  orphaned-source fact by any means. If the carried browser-contrast
  (constraint i) therefore cannot show a UNRESOLVABLE row from this
  workspace, the recorded, accepted outcome is verbatim:

      "orphan-rendering remains probe-verified-only
       (verify_query_phase0.py probe iv/v + the unit form in
       test_query_layer_invariants.py); the browser contrast confirmed
       OPENABLE and NO_SOURCE rendering only; no orphan was injected to
       complete the demo."

  That is the EXPECTED path, not a failure. The orphaned-source case is
  the dominant *corpus* finding (15/24 on test-workspace-* tenants) and
  is verified there by the probe, never manufactured here.
═══════════════════════════════════════════════════════════════════════

Re-runnable: deterministic ids; prerequisite rows upserted; if the
document is already promoted the script reports and exits 0 without
re-promoting (the promote RPC's FOR UPDATE NOWAIT + 'validated' status
precondition make a double-run a safe no-op anyway).

Usage:
  cd backend && PYTHONPATH=. .venv/bin/python scripts/provision_briefing_demo.py
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from supabase import create_client

# Deterministic identities (re-runnable).
WS = "demo-briefing-workspace-001"
TENANT = "demo-briefing-tenant-001"
DOC_ID = "briefingdemo-doc-0000-0000-000000000001"
STORAGE_BUCKET = "medical-records"
FILE_PATH = f"{WS}/{DOC_ID}/Briefing demo patient file.pdf"
PRODUCT = "platform_professional"  # entitles clinical_query (migration 025)

# A minimal, valid, single-page PDF. The OPENABLE path needs the
# signed-URL target to be a real readable object; this is a genuine
# (tiny) PDF, not a 1-byte placeholder, so clicking it in the browser
# opens an actual document.
_MINIMAL_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 144]"
    b"/Resources<</Font<</F1 4 0 R>>>>/Contents 5 0 R>>endobj\n"
    b"4 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
    b"5 0 obj<</Length 74>>stream\n"
    b"BT /F1 12 Tf 20 90 Td (SurgiScan briefing-demo source scan) Tj ET\n"
    b"endstream endobj\n"
    b"xref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n"
    b"0000000052 00000 n \n0000000101 00000 n \n0000000209 00000 n \n"
    b"0000000277 00000 n \ntrailer<</Size 6/Root 1 0 R>>\n"
    b"startxref\n398\n%%EOF\n"
)

# A realistic extraction, shaped EXACTLY like a real
# gp_validation_sessions.extractions row (probed live 2026-05-16 from a
# known-promoted document — the schema the promote RPC consumes). Small
# but multi-fact so the promote path produces document-sourced
# encounters, prescriptions+items, and vitals → the briefing templates
# resolve OPENABLE on this entitled workspace.
EXTRACTIONS = {
    "patient_demographics": {
        "sex": "F",
        "title": "Mrs",
        "surname": "Briefingdemo",
        "full_names": "Thandiwe",
        "id_number": "8806120123088",
        "date_of_birth": "1988-06-12",
        "telephone_cell": "082 555 0142",
        "email": "thandiwe.briefingdemo@example.co.za",
        "address": None,
        "file_number": None,
    },
    "diagnoses": [
        {
            "status": "active",
            "icd10_code": "E11.9",
            "description": "Type 2 diabetes mellitus",
            "consultation_date": "2026-01-08",
            "differential_notes": None,
        }
    ],
    "medications": [
        {
            "route": "oral",
            "dosage": "500 mg",
            "status": "active",
            "duration": "ongoing",
            "drug_name": "Metformin",
            "frequency": "BD",
            "instructions": "with meals",
            "prescribed_by": "Dr Demo",
            "consultation_date": "2026-01-08",
        },
        {
            "route": "oral",
            "dosage": "10 mg",
            "status": "active",
            "duration": "ongoing",
            "drug_name": "Enalapril",
            "frequency": "OD",
            "instructions": "",
            "prescribed_by": "Dr Demo",
            "consultation_date": "2026-01-08",
        },
    ],
    "vitals_history": [
        {
            "bmi": None,
            "hba1c": "8.1",
            "height_cm": "164",
            "weight_kg": "78",
            "heart_rate": "82",
            "bp_systolic": "148",
            "bp_diastolic": "94",
            "temperature_c": "36.7",
            "respiratory_rate": "16",
            "consultation_date": "2026-01-08",
            "oxygen_saturation": "98",
            "blood_glucose_fasting": "9.2",
        }
    ],
    "progress_notes": [
        {
            "plan": "Continue metformin, add enalapril, review HbA1c in 3/12",
            "objective": "BP 148/94, BMI elevated",
            "assessment": "T2DM with suboptimal control + new HTN",
            "subjective": "Polyuria, mild fatigue",
            "doctor_signed": True,
            "consultation_date": "2026-01-08",
            "follow_up_instruction": "Review in 12 weeks",
        }
    ],
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    url = os.environ["SUPABASE_URL"]
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ["SUPABASE_KEY"]
    sb = create_client(url, key)
    now = _now_iso()

    # ── Prerequisite 0: tenant (workspaces.tenant_id → tenants FK; the
    #     real signup flow creates tenant + workspace together) ─────────
    sb.table("tenants").upsert({
        "id": TENANT, "name": "Briefing Demo Tenant",
    }).execute()
    print(f"✓ tenant {TENANT}")

    # ── Prerequisite 1: workspace (input the signup flow produces) ──────
    sb.table("workspaces").upsert({
        "id": WS, "tenant_id": TENANT,
        "name": "Briefing Demo Practice", "type": "gp",
        "created_at": now,
    }).execute()
    print(f"✓ workspace {WS}")

    # ── Prerequisite 2: entitlement → clinical_query resolves ──────────
    # platform_professional is mapped to clinical_query by migration 025.
    existing = (
        sb.table("practice_entitlements")
        .select("practice_id, product_id, status")
        .eq("practice_id", WS).eq("product_id", PRODUCT).execute()
    )
    if not existing.data:
        sb.table("practice_entitlements").insert({
            "practice_id": WS, "product_id": PRODUCT,
            "status": "active", "payment_status": "manual",
            "starts_at": now, "ends_at": None,
            "metadata": {"provisioned_via": "scripts/provision_briefing_demo.py"},
        }).execute()
    print(f"✓ entitlement {PRODUCT} (clinical_query resolvable)")

    # ── Prerequisite 3: a real PDF object in storage ───────────────────
    try:
        sb.storage.from_(STORAGE_BUCKET).upload(
            path=FILE_PATH, file=_MINIMAL_PDF,
            file_options={"content-type": "application/pdf", "upsert": "true"},
        )
    except Exception as e:  # noqa: BLE001 — re-run: object may already exist
        if "exist" not in str(e).lower() and "duplicate" not in str(e).lower():
            print(f"  ⚠ storage upload note: {e}")
    print(f"✓ source PDF uploaded → {STORAGE_BUCKET}/{FILE_PATH}")

    # ── Prerequisite 4: digitised_documents (input ingestion produces) ─
    # status='validated' is the promote precondition. Re-run safe: if
    # already promoted (patient_id set) we stop before re-promoting.
    doc = (
        sb.table("digitised_documents").select("id, status, patient_id")
        .eq("id", DOC_ID).execute()
    )
    if doc.data and doc.data[0].get("patient_id"):
        print(f"✓ document {DOC_ID} already promoted "
              f"(patient_id={doc.data[0]['patient_id']}) — no-op, exiting 0")
        print("\nProvisioned. Briefing templates can now be run on "
              f"workspace {WS!r} (entitled, document-sourced).")
        return 0
    sb.table("digitised_documents").upsert({
        "id": DOC_ID, "workspace_id": WS,
        "filename": "Briefing demo patient file.pdf",
        "file_path": FILE_PATH, "status": "validated",
        "created_at": now, "upload_date": now,
    }).execute()
    print(f"✓ digitised_documents {DOC_ID} (status=validated)")

    # ── Prerequisite 5: gp_validation_sessions (the extraction the ─────
    #     real approve endpoint pulls and hands to the promote action) ──
    vs = (
        sb.table("gp_validation_sessions").select("id")
        .eq("document_id", DOC_ID).execute()
    )
    if not vs.data:
        sb.table("gp_validation_sessions").insert({
            "session_id": f"sess-{DOC_ID}",   # NOT NULL, no default
            "document_id": DOC_ID, "workspace_id": WS,
            "extractions": EXTRACTIONS, "created_at": now,
        }).execute()
    print("✓ gp_validation_sessions (extraction staged)")

    # ── THE REAL PATH ──────────────────────────────────────────────────
    # The promote action's preconditions REQUIRE the target patient to
    # already exist (ObjectExists(patients,…) + BelongsToPractice) — the
    # `force_create_patient` flag is consumed by the effect, not the
    # precondition. Production therefore resolves/creates the patient
    # subject FIRST, via app.services.patient_matching.match_or_create_patient
    # (the same helper /preview-match uses; the patients insert lives in
    # that PRODUCTION code, never in this script — this is the real path,
    # not a script-side fact insert), then promotes onto it.
    #
    # The patient is the data SUBJECT, created by the real matching
    # helper. Every clinical FACT (encounter / diagnosis / prescription /
    # vital) is then produced EXCLUSIVELY by
    # execute(PromoteDocumentToPatientRecord), each with
    # source_document_id = DOC_ID → the resolver renders them OPENABLE
    # against the real PDF uploaded above. Zero fact-table inserts in
    # this script; the legitimacy test ("same action code path
    # production uses") holds end to end.
    from app.actions import ActorContext, execute
    from app.services.patient_matching import match_or_create_patient
    from ontology.actions.promote_document import (
        PatientMatchEvidence, PromoteDocumentToPatientRecord,
    )

    patient_id, kind, _conf, _summary = match_or_create_patient(
        sb, WS, EXTRACTIONS["patient_demographics"], force_create=True,
    )
    print(f"✓ patient subject via real match_or_create_patient: "
          f"{patient_id} ({kind})")

    confirmation = PatientMatchEvidence(
        confirmed_by_user_id="briefing-demo-provisioner",
        confirmed_at=datetime.now(timezone.utc),  # fresh (<15min precondition)
        match_signals=["explicit_confirmed_patient_id"],
        confidence_score=1.0,
    )
    action = PromoteDocumentToPatientRecord(
        document_id=DOC_ID,
        target_patient_id=patient_id,
        confirmation=confirmation,
        actor_user_id="briefing-demo-provisioner",
        practice_id=WS,
        workspace_id=WS,
        extractions=EXTRACTIONS,
        forced_patient_id=patient_id,
        force_create_patient=False,   # patient now exists; promote facts
    )
    result = execute(
        action,
        actor=ActorContext(
            user_id="briefing-demo-provisioner",
            email="provisioner@medicdata.co.za",
            permissions=["digitisation_validation"],  # promote precondition
        ),
        supabase=sb,
    )

    outcome = getattr(result, "outcome", None)
    print(f"\npromote outcome: {outcome}")
    affected = getattr(result, "affected_objects", None) or []
    kinds: dict[str, int] = {}
    for a in affected:
        kinds[a.get("type", "?")] = kinds.get(a.get("type", "?"), 0) + 1
    print("affected_objects:", kinds or "(none)")

    if outcome not in ("success", "succeeded"):
        ed = getattr(result, "error_detail", None)
        print(f"✗ promote did not succeed: {ed}")
        return 1

    print(
        f"\n✓ Provisioned via the real promote path. Workspace {WS!r} is "
        f"entitled (clinical_query) and its facts are document-sourced "
        f"(source_document_id={DOC_ID}) → briefing templates resolve "
        f"OPENABLE here. Per the pre-committed contract above, this seed "
        f"produces OPENABLE + NO_SOURCE only and no orphan; "
        f"orphan-rendering stays probe-verified-only."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
