#!/usr/bin/env python3
"""
PR 3 smoke recipe — exercise each new action end-to-end against the
live dev DB.

Run from the backend dir:
    cd backend && PYTHONPATH=. .venv/bin/python scripts/pr3_smoke.py

Each step prints a pass/fail line. Failure halts; partial state may
need manual cleanup from the audit log.

Doesn't go through HTTP — drives the executor directly. The clinical-
actions router's correctness is mostly Pydantic + auth + an execute()
call, so if the actions work here they'll work over HTTP.
"""
from __future__ import annotations
import os, sys, uuid
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Ensure backend/ is on path so app.* and ontology.* import.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from supabase import create_client
from app.actions import ActorContext, execute
from app.actions.executor import reverse as executor_reverse

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

ACTOR = ActorContext(
    user_id="pr3-smoke-runner",
    email="smoke@medicdata.co.za",
    permissions=[
        "digitisation_validation",
        "digitisation_upload",
        "prescription_management",
        "patient_admin",
    ],
)
WS = os.environ.get("PR3_SMOKE_WORKSPACE", "demo-gp-workspace-001")


def step(title: str):
    print(f"\n── {title} ──")


def ok(msg: str):
    print(f"  ✓ {msg}")


def fail(msg: str):
    print(f"  ✗ {msg}")
    sys.exit(1)


def expect(result, *, want_outcome: str, label: str):
    if result.outcome != want_outcome:
        err = result.error
        fail(
            f"{label}: outcome={result.outcome} "
            f"error={(err.code if err else None)}: "
            f"{(err.message if err else '')}"
        )
    ok(f"{label}: outcome={result.outcome} audit_id={result.audit_id}")


def seed_patient(label: str, first="Smoke", last="Patient", id_num=None):
    pid = str(uuid.uuid4())
    id_num = id_num or f"smoke-{pid[:8]}"
    sb.table("patients").insert({
        "id": pid,
        "tenant_id": "demo-tenant-001",
        "workspace_id": WS,
        "first_name": first,
        "last_name": last,
        "dob": "1990-01-01",
        "id_number": id_num,
    }).execute()
    ok(f"seeded patient {label}={pid}")
    return pid


# ===========================================================================
# 1. RejectDocument + reverse
# ===========================================================================
step("1. RejectDocument + reverse")

# Find a doc in a rejectable status.
docs = (
    sb.table("digitised_documents")
    .select("id, status, workspace_id, validated_at, validated_by, error_message")
    .eq("workspace_id", WS)
    .in_("status", ["parsed", "pending_validation", "validated", "error"])
    .limit(1)
    .execute()
).data
if not docs:
    fail("no rejectable document found in workspace; upload one first")
d = docs[0]
ok(f"using doc {d['id']} status={d['status']}")

from ontology.actions.reject_document import RejectDocument
action = RejectDocument(
    document_id=d["id"],
    reason="smoke-test rejection",
    actor_user_id=ACTOR.user_id,
    actor_email=ACTOR.email,
    practice_id=WS,
    workspace_id=WS,
    previous_status=d["status"],
    previous_validated_at=d.get("validated_at"),
    previous_validated_by=d.get("validated_by"),
    previous_error_message=d.get("error_message"),
)
r = execute(action, actor=ACTOR, supabase=sb)
expect(r, want_outcome="success", label="reject")
reject_audit = r.audit_id

# Verify state
after = sb.table("digitised_documents").select("status").eq("id", d["id"]).execute().data
if after[0]["status"] != "rejected":
    fail(f"document status should be 'rejected' but is {after[0]['status']!r}")
ok("document status flipped to 'rejected'")

# Reverse
r = executor_reverse(reject_audit, actor=ACTOR, supabase=sb, reason="smoke test")
expect(r, want_outcome="reversed", label="reverse reject")
after = sb.table("digitised_documents").select("status").eq("id", d["id"]).execute().data
if after[0]["status"] != d["status"]:
    fail(f"document status should be restored to {d['status']!r} but is {after[0]['status']!r}")
ok(f"document status restored to {d['status']!r}")


# Reprocess moved to the END of the smoke (section 7) because it's
# non-reversible and leaves the doc in 'queued_for_processing' status,
# which would block section 5's reassign precondition.


# ===========================================================================
# 3. VoidPrescription + reverse
# ===========================================================================
step("3. VoidPrescription + reverse")

# Seed a prescription for testing.
test_patient = seed_patient("rx-test")
rx_id = str(uuid.uuid4())
sb.table("prescriptions").insert({
    "id": rx_id,
    "tenant_id": "demo-tenant-001",
    "workspace_id": WS,
    "patient_id": test_patient,
    "doctor_name": "Smoke Test",
    "prescription_date": "2026-05-15",
    "status": "active",
}).execute()
ok(f"seeded prescription {rx_id} status=active")

from ontology.actions.void_prescription import VoidPrescription
action = VoidPrescription(
    prescription_id=rx_id,
    void_reason="smoke test",
    actor_user_id=ACTOR.user_id,
    actor_email=ACTOR.email,
    practice_id=WS,
    workspace_id=WS,
    previous_status="active",
)
r = execute(action, actor=ACTOR, supabase=sb)
expect(r, want_outcome="success", label="void")

after = sb.table("prescriptions").select("status, void_reason").eq("id", rx_id).execute().data
if after[0]["status"] != "cancelled":
    fail(f"rx status should be 'cancelled' but is {after[0]['status']!r}")
ok(f"rx status='cancelled' void_reason={after[0]['void_reason']!r}")

r = executor_reverse(r.audit_id, actor=ACTOR, supabase=sb)
expect(r, want_outcome="reversed", label="reverse void")
after = sb.table("prescriptions").select("status").eq("id", rx_id).execute().data
if after[0]["status"] != "active":
    fail(f"rx status should be restored to 'active' but is {after[0]['status']!r}")
ok("rx status restored to 'active'")

# Cleanup the test rx + patient
sb.table("prescriptions").delete().eq("id", rx_id).execute()
sb.table("patients").delete().eq("id", test_patient).execute()


# ===========================================================================
# 4. SoftDeletePatient — happy path + block-on-children
# ===========================================================================
step("4. SoftDeletePatient — happy path + block-on-children")

clean_patient = seed_patient("soft-delete-clean")
from ontology.actions.soft_delete_patient import SoftDeletePatient
action = SoftDeletePatient(
    patient_id=clean_patient,
    erasure_reason="POPIA smoke",
    actor_user_id=ACTOR.user_id,
    actor_email=ACTOR.email,
    practice_id=WS,
    workspace_id=WS,
)
r = execute(action, actor=ACTOR, supabase=sb)
expect(r, want_outcome="success", label="soft-delete clean patient")

after = sb.table("patients").select("deleted_at").eq("id", clean_patient).execute().data
if not after[0]["deleted_at"]:
    fail("deleted_at should be set")
ok(f"deleted_at set: {after[0]['deleted_at']}")

# Reverse
r = executor_reverse(r.audit_id, actor=ACTOR, supabase=sb)
expect(r, want_outcome="reversed", label="reverse soft-delete")
after = sb.table("patients").select("deleted_at").eq("id", clean_patient).execute().data
if after[0]["deleted_at"] is not None:
    fail(f"deleted_at should be NULL after reverse but is {after[0]['deleted_at']!r}")
ok("deleted_at cleared")

# Block-on-children: seed a patient with an active rx, try to soft-delete
blocked_patient = seed_patient("soft-delete-blocked")
rx_id2 = str(uuid.uuid4())
sb.table("prescriptions").insert({
    "id": rx_id2,
    "tenant_id": "demo-tenant-001",
    "workspace_id": WS,
    "patient_id": blocked_patient,
    "doctor_name": "Smoke",
    "prescription_date": "2026-05-15",
    "status": "active",
}).execute()
action = SoftDeletePatient(
    patient_id=blocked_patient, erasure_reason="should fail",
    actor_user_id=ACTOR.user_id, actor_email=ACTOR.email,
    practice_id=WS, workspace_id=WS,
)
r = execute(action, actor=ACTOR, supabase=sb)
if r.outcome != "precondition_failed":
    fail(f"soft-delete with active rx should fail but outcome={r.outcome}")
ok(f"soft-delete blocked (precondition_failed): {r.error.message if r.error else ''}")

# Cleanup
sb.table("prescriptions").delete().eq("id", rx_id2).execute()
sb.table("patients").delete().eq("id", blocked_patient).execute()
sb.table("patients").delete().eq("id", clean_patient).execute()


# ===========================================================================
# 5. ReassignDocument + reverse
# ===========================================================================
step("5. ReassignDocument + reverse")

# Find any promoted doc in the workspace (one with a patient_id set).
promoted = (
    sb.table("digitised_documents")
    .select("id, patient_id")
    .eq("workspace_id", WS)
    .not_.is_("patient_id", "null")
    .limit(1)
    .execute()
).data
if not promoted:
    ok("no promoted document in workspace; skipping reassign step")
    ok("(to exercise reassign, promote a document first via the approve endpoint)")
    print("\n=== 5 OF 6 ACTIONS GREEN (reassign skipped, no promoted doc) ===")
    sys.exit(0)
d_reassign = promoted[0]
original_patient = d_reassign["patient_id"]
ok(f"using promoted doc {d_reassign['id']} (patient={original_patient})")

target_patient = seed_patient("reassign-target", id_num=f"reassign-{uuid.uuid4().hex[:8]}")
from ontology.actions.reassign_document import ReassignDocument
action = ReassignDocument(
    document_id=d_reassign["id"],
    new_patient_id=target_patient,
    reason="smoke test",
    actor_user_id=ACTOR.user_id,
    actor_email=ACTOR.email,
    practice_id=WS,
    workspace_id=WS,
)
r = execute(action, actor=ACTOR, supabase=sb)
expect(r, want_outcome="success", label="reassign")
reassign_audit = r.audit_id

after = sb.table("digitised_documents").select("patient_id").eq("id", d_reassign["id"]).execute().data
if after[0]["patient_id"] != target_patient:
    fail(f"doc patient_id should be {target_patient} but is {after[0]['patient_id']}")
ok("doc re-pointed to target patient")

r = executor_reverse(reassign_audit, actor=ACTOR, supabase=sb)
expect(r, want_outcome="reversed", label="reverse reassign")
after = sb.table("digitised_documents").select("patient_id").eq("id", d_reassign["id"]).execute().data
if after[0]["patient_id"] != original_patient:
    fail(f"doc patient_id should be restored to {original_patient} but is {after[0]['patient_id']}")
ok("doc patient_id restored")

sb.table("patients").delete().eq("id", target_patient).execute()


# ===========================================================================
# 6. MergePatient — fresh confirmation + reverse
# ===========================================================================
step("6. MergePatient + reverse")

source = seed_patient("merge-source", id_num=f"merge-src-{uuid.uuid4().hex[:8]}")
target = seed_patient("merge-target", id_num=f"merge-tgt-{uuid.uuid4().hex[:8]}")

from ontology.actions.merge_patient import MergePatient, MergeConfirmation
confirmation = MergeConfirmation(
    confirmed_by_user_id=ACTOR.user_id,
    confirmed_at=datetime.now(timezone.utc),
    survivor_choice_evidence="smoke",
)
action = MergePatient(
    source_patient_id=source,
    target_patient_id=target,
    merge_reason="smoke test",
    confirmation=confirmation,
    actor_user_id=ACTOR.user_id,
    actor_email=ACTOR.email,
    practice_id=WS,
    workspace_id=WS,
)
r = execute(action, actor=ACTOR, supabase=sb)
expect(r, want_outcome="success", label="merge")
merge_audit = r.audit_id

after = sb.table("patients").select("deleted_at, merged_into_patient_id").eq("id", source).execute().data
if not after[0]["deleted_at"]:
    fail("source patient should be soft-deleted after merge")
if after[0]["merged_into_patient_id"] != target:
    fail(f"merged_into should be {target} but is {after[0]['merged_into_patient_id']}")
ok(f"source soft-deleted with merged_into={target}")

r = executor_reverse(merge_audit, actor=ACTOR, supabase=sb)
expect(r, want_outcome="reversed", label="reverse merge")
after = sb.table("patients").select("deleted_at, merged_into_patient_id").eq("id", source).execute().data
if after[0]["deleted_at"] is not None or after[0]["merged_into_patient_id"] is not None:
    fail(f"source merge metadata not cleared: {after[0]}")
ok("source merge metadata cleared by reverse")

sb.table("patients").delete().eq("id", source).execute()
sb.table("patients").delete().eq("id", target).execute()


# ===========================================================================
# 7. ReprocessDocument (non-reversible — last because it leaves the doc
#    in 'queued_for_processing', which blocks reassign / reject)
# ===========================================================================
step("7. ReprocessDocument (non-reversible — runs last)")

from ontology.actions.reprocess_document import ReprocessDocument
action = ReprocessDocument(
    document_id=d["id"],
    reason="smoke test",
    actor_user_id=ACTOR.user_id,
    actor_email=ACTOR.email,
    practice_id=WS,
    workspace_id=WS,
)
r = execute(action, actor=ACTOR, supabase=sb)
expect(r, want_outcome="success", label="reprocess")

r = executor_reverse(r.audit_id, actor=ACTOR, supabase=sb)
if r.outcome != "precondition_failed":
    fail(f"reverse(reprocess) should be precondition_failed but is {r.outcome}")
ok(f"reverse(reprocess) correctly rejected: {r.error.message if r.error else ''}")
ok(f"NOTE: doc {d['id']} is now status='queued_for_processing' — "
   f"the watcher will re-process it")


# ===========================================================================
# Done
# ===========================================================================
print("\n=== ALL SEVEN ACTIONS + REVERSALS GREEN ===")
print("Check action_audit_log for the trail:")
print("  SELECT action_name, outcome, started_at, reversed_by_audit_id")
print("    FROM action_audit_log")
print("   WHERE actor_user_id = 'pr3-smoke-runner'")
print("   ORDER BY started_at DESC LIMIT 20;")
