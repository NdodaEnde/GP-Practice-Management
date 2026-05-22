"""
Synthetic two-tenant cross-read probe for the rebuilt billing module.

Mounts ONLY api/billing.router (it owns its own supabase client, no server
import) and overrides get_current_user per tenant. Workspace A = demo-gp,
B = typec. Reuses existing patients; creates billing rows in A, asserts B
cannot read/mutate them, then deletes everything it created.

DEV only. No LandingAI, no prod. Run: .venv/bin/python tests/manual/billing_cross_tenant_probe.py
"""
import os, sys
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import billing
from app.api.auth import get_current_user

A = {"workspace_id": "demo-gp-workspace-001", "tenant_id": "demo-tenant-001",
     "email": "probe-a@test", "patient_id": "42d73864-6dfa-4ede-9bf8-bde07741d92e"}
B = {"workspace_id": "typec-workspace-001", "tenant_id": "typec-tenant-001",
     "email": "probe-b@test", "patient_id": "496f6883-f098-471f-acdd-83b601e6aece"}

sb = billing.supabase
app = FastAPI()
app.include_router(billing.router)

_who = {"u": A}
app.dependency_overrides[get_current_user] = lambda: _who["u"]
client = TestClient(app)

def as_(u): _who["u"] = u

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}  {detail if not cond else ''}")

created = {"invoice": None, "payment": None, "claim": None}
try:
    # --- A creates an invoice, payment, claim ---
    as_(A)
    r = client.post("/invoices", json={
        "patient_id": A["patient_id"], "invoice_date": "2026-05-22",
        "items": [{"item_type": "consultation", "description": "GP consult", "quantity": 1, "unit_price": 500.0}],
    })
    check("A create invoice 200", r.status_code == 200, r.text)
    inv = r.json()["invoice_id"]; created["invoice"] = inv

    r = client.post("/payments", json={
        "invoice_id": inv, "payment_date": "2026-05-22", "amount": 100.0, "payment_method": "cash"})
    check("A record payment 200", r.status_code == 200, r.text)
    created["payment"] = r.json().get("payment_id")

    r = client.post("/claims", json={
        "invoice_id": inv, "medical_aid_name": "Discovery", "medical_aid_number": "123",
        "claim_amount": 400.0, "primary_diagnosis_code": "J06.9",
        "primary_diagnosis_description": "URTI"})
    check("A create claim 200", r.status_code == 200, r.text)
    claim = r.json()["claim_id"]; created["claim"] = claim

    # --- A positive control (owner can read) ---
    as_(A)
    check("A GET own invoice 200", client.get(f"/invoices/{inv}").status_code == 200)
    check("A GET own claim 200", client.get(f"/claims/{claim}").status_code == 200)

    # --- B cross-tenant: must be blocked ---
    as_(B)
    check("B GET A's invoice -> 404", client.get(f"/invoices/{inv}").status_code == 404)
    check("B GET A's claim -> 404", client.get(f"/claims/{claim}").status_code == 404)
    check("B PATCH A's claim status -> 404",
          client.patch(f"/claims/{claim}/status", params={"status": "submitted"}).status_code == 404)
    check("B record payment on A's invoice -> 404",
          client.post("/payments", json={"invoice_id": inv, "payment_date": "2026-05-22",
                                          "amount": 50.0, "payment_method": "cash"}).status_code == 404)
    lst = client.get("/invoices").json().get("invoices", [])
    check("B list invoices excludes A's", all(i["id"] != inv for i in lst), f"leaked {inv}")
    cl = client.get("/claims").json().get("claims", [])
    check("B list claims excludes A's", all(c["id"] != claim for c in cl), f"leaked {claim}")
    pays = client.get(f"/payments/invoice/{inv}").json()
    check("B payments-for-A's-invoice empty", pays.get("count") == 0, str(pays))
    pi = client.get(f"/invoices/patient/{A['patient_id']}").json()
    check("B invoices-for-A's-patient excludes A's",
          all(i["id"] != inv for i in pi.get("invoices", [])), f"leaked {inv}")
finally:
    # --- cleanup everything we created (children first) ---
    if created["claim"]:
        sb.table("medical_aid_claims").delete().eq("id", created["claim"]).execute()
    if created["payment"]:
        sb.table("payments").delete().eq("id", created["payment"]).execute()
    if created["invoice"]:
        sb.table("invoice_items").delete().eq("invoice_id", created["invoice"]).execute()
        sb.table("invoices").delete().eq("id", created["invoice"]).execute()
    print("\ncleanup done:", created)

print(f"\n=== {len(PASS)} passed, {len(FAIL)} failed ===")
sys.exit(1 if FAIL else 0)
