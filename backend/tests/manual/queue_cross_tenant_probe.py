"""
Synthetic two-tenant cross-read probe for the rebuilt reception queue.

Mounts ONLY the queue routes from server.py via the app's api_router and
overrides get_current_user per tenant. Workspace A = demo-gp, B = typec.
Reuses existing patients; checks a patient into A's queue, asserts B cannot
see/mutate it, then deletes the queue row it created.

Requires migration 034 (queue_entries) applied. DEV only.
Run: PYTHONPATH=. .venv/bin/python tests/manual/queue_cross_tenant_probe.py
"""
import os, sys
from fastapi import FastAPI
from fastapi.testclient import TestClient

import server
from app.api.auth import get_current_user

A = {"workspace_id": "demo-gp-workspace-001", "tenant_id": "demo-tenant-001",
     "email": "probe-a@test", "patient_id": "42d73864-6dfa-4ede-9bf8-bde07741d92e"}
B = {"workspace_id": "typec-workspace-001", "tenant_id": "typec-tenant-001",
     "email": "probe-b@test", "patient_id": "496f6883-f098-471f-acdd-83b601e6aece"}

sb = server.supabase
app = FastAPI()
app.include_router(server.api_router)  # api_router already carries prefix="/api"

_who = {"u": A}
app.dependency_overrides[get_current_user] = lambda: _who["u"]
client = TestClient(app)

def as_(u): _who["u"] = u

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}  {detail if not cond else ''}")

queue_id = None
try:
    # --- A checks a patient in ---
    as_(A)
    r = client.post("/api/queue/check-in", json={
        "patient_id": A["patient_id"], "reason_for_visit": "probe", "priority": "normal"})
    check("A check-in 200", r.status_code == 200, r.text)
    queue_id = r.json().get("queue_id")

    # A sees it; A's stats count it
    cur = client.get("/api/queue/current").json()
    check("A sees own entry in current", any(e["id"] == queue_id for e in cur.get("queue", [])))
    check("A stats count >=1", client.get("/api/queue/stats").json()["stats"]["total_checked_in"] >= 1)

    # --- B cross-tenant: blocked ---
    as_(B)
    bcur = client.get("/api/queue/current").json()
    check("B current excludes A's entry", all(e["id"] != queue_id for e in bcur.get("queue", [])),
          f"leaked {queue_id}")
    check("B call-next on A's entry -> 404",
          client.post(f"/api/queue/{queue_id}/call-next", params={"station": "vitals"}).status_code == 404)
    check("B update-status on A's entry -> 404",
          client.put(f"/api/queue/{queue_id}/update-status", json={"status": "completed"}).status_code == 404)

    # --- A positive control: owner can advance + complete ---
    as_(A)
    check("A call-next own -> 200",
          client.post(f"/api/queue/{queue_id}/call-next", params={"station": "vitals"}).status_code == 200)
    check("A update-status own -> 200",
          client.put(f"/api/queue/{queue_id}/update-status", json={"status": "completed"}).status_code == 200)
finally:
    if queue_id:
        sb.table("queue_entries").delete().eq("id", queue_id).execute()
    print("\ncleanup done: queue_id =", queue_id)

print(f"\n=== {len(PASS)} passed, {len(FAIL)} failed ===")
sys.exit(1 if FAIL else 0)
