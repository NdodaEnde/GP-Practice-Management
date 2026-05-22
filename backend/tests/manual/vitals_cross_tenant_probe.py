"""
Synthetic two-tenant cross-read probe for the rebuilt vitals module.

Mounts ONLY api/vitals.router and overrides get_current_user per tenant.
Workspace A = demo-gp, B = typec. Reuses existing patients; creates a vitals
record in A, asserts B cannot see/delete it, then deletes it.

Requires migration 035 (vitals.encounter_id nullable). DEV only.
Run: PYTHONPATH=. .venv/bin/python tests/manual/vitals_cross_tenant_probe.py
"""
import os, sys
from fastapi import FastAPI
from fastapi.testclient import TestClient

import server  # vitals router does `from server import supabase`
from api import vitals
from app.api.auth import get_current_user

A = {"workspace_id": "demo-gp-workspace-001", "tenant_id": "demo-tenant-001",
     "email": "probe-a@test", "patient_id": "42d73864-6dfa-4ede-9bf8-bde07741d92e"}
B = {"workspace_id": "typec-workspace-001", "tenant_id": "typec-tenant-001",
     "email": "probe-b@test", "patient_id": "496f6883-f098-471f-acdd-83b601e6aece"}

sb = server.supabase
app = FastAPI()
app.include_router(vitals.router)

_who = {"u": A}
app.dependency_overrides[get_current_user] = lambda: _who["u"]
client = TestClient(app)

def as_(u): _who["u"] = u

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}  {detail if not cond else ''}")

vital_id = None
try:
    # --- A records a vital (no encounter — manual entry) ---
    as_(A)
    r = client.post("/vitals", json={
        "patient_id": A["patient_id"], "measurement_date": "2026-05-22T09:00:00+00:00",
        "blood_pressure_systolic": 128, "blood_pressure_diastolic": 82,
        "heart_rate": 72, "weight": 80.5, "height": 175})
    check("A create vital 200", r.status_code == 200, r.text)
    body = r.json()
    vital_id = body.get("id")
    check("response maps real cols -> API names", body.get("blood_pressure_systolic") == 128 and body.get("weight") == 80.5, str(body))

    # A reads its own
    av = client.get(f"/vitals/patient/{A['patient_id']}").json()
    check("A sees own vital", any(v["id"] == vital_id for v in av))

    # --- B cross-tenant: blocked ---
    as_(B)
    bv = client.get(f"/vitals/patient/{A['patient_id']}").json()
    check("B vitals-for-A's-patient empty/excluded", all(v["id"] != vital_id for v in bv), f"leaked {vital_id}")
    check("B delete A's vital -> 404", client.delete(f"/vitals/{vital_id}").status_code == 404)

    # A's vital still there after B's failed delete
    as_(A)
    av2 = client.get(f"/vitals/patient/{A['patient_id']}").json()
    check("A's vital survived B's delete attempt", any(v["id"] == vital_id for v in av2))

    # --- A positive control: owner can delete ---
    check("A delete own vital -> 200", client.delete(f"/vitals/{vital_id}").status_code == 200)
    vital_id = None  # already deleted
finally:
    if vital_id:
        sb.table("vitals").delete().eq("id", vital_id).execute()
    print("\ncleanup done.")

print(f"\n=== {len(PASS)} passed, {len(FAIL)} failed ===")
sys.exit(1 if FAIL else 0)
