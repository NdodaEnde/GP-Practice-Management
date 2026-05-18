"""
ZERO — first concrete capability cut: the sick-note family.

The cut is two non-severable properties on `POST /api/sick-notes` and
`GET /api/sick-notes/patient/{id}`; this test proves BOTH bite, both ways
(the §2.4/PR-F + PR-D standard), or the cut is not done:

  (1) CAPABILITY gate bites — DB-free:
      * no token            -> 401 (the floor still composes underneath)
      * token, cap MISSING  -> 403, and the 403 names patient_ehr_basic
                               (non-vacuity: it is THIS gate biting, not
                               an incidental 403)
      * token, cap PRESENT  -> past the gate (handler's tenant guard
                               reached: 400 "No workspace/tenant context")
                               — proves the gate does not false-block.

  (2) TENANT fix bites — RUN_INTEGRATION, residue-safe, read-back (PR-D
      idiom), parametrised over TWO distinct workspaces so the stored
      workspace/tenant is proven DERIVED from the principal, not the DEMO
      constant: if it were constant, the second workspace's read-back
      assertion fails. Plus cross-workspace GET isolation (the mirror
      read defect).

Scaffolding to the code bar: reviewed before run; dependency_overrides
cleared in teardown (in-process residue); Part 2 deletes every row it
writes and is the only shared-state writer here — surfaced, not assumed.
"""
import os
import uuid
from datetime import datetime, timezone

import pytest

try:
    import server
    from app.api.auth import create_access_token, get_current_user
except Exception as e:  # pragma: no cover - env-dependent
    pytest.skip(f"cannot import app under test ({e})", allow_module_level=True)

from fastapi.testclient import TestClient

_DEMO_WS = os.environ.get("DEMO_WORKSPACE_ID", "demo-gp-workspace-001")
_DEMO_TENANT = os.environ.get("DEMO_TENANT_ID", "demo-tenant-001")

_SICK_NOTE_BODY = {
    "patient_id": "pat-cut-test",
    "doctor_name": "Dr Test",
    "issue_date": "2026-05-17",
    "start_date": "2026-05-17",
    "end_date": "2026-05-19",
    "diagnosis": "Influenza",
    "fitness_status": "unfit",
}


def _token(workspace_id="ws-x", tenant_id="t-x"):
    # Real signed access token so the deny-by-default floor passes; the
    # capability/identity is controlled separately via dependency_overrides.
    return create_access_token({
        "user_id": "u-test", "email": "t@test", "role": "clinical",
        "workspace_id": workspace_id, "tenant_id": tenant_id,
    })


def _override(caps, workspace_id="ws-x", tenant_id="t-x"):
    server.app.dependency_overrides[get_current_user] = lambda: {
        "user_id": "u-test", "email": "t@test", "role": "clinical",
        "workspace_id": workspace_id, "tenant_id": tenant_id,
        "capabilities": caps,
    }


@pytest.fixture
def client():
    c = TestClient(server.app)
    yield c
    server.app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# (1) capability gate — DB-free, always runs
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("method,path", [
    ("post", "/api/sick-notes"),
    ("get", "/api/sick-notes/patient/pat-1"),
])
def test_no_token_is_401_floor_composes(client, method, path):
    r = client.request(method, path, json=_SICK_NOTE_BODY if method == "post" else None)
    assert r.status_code == 401, f"{method} {path} -> {r.status_code}, floor not composing"


@pytest.mark.parametrize("method,path", [
    ("post", "/api/sick-notes"),
    ("get", "/api/sick-notes/patient/pat-1"),
])
def test_cap_missing_is_403_and_names_the_capability(client, method, path):
    _override(caps=["digitisation_upload"])  # authenticated, wrong tier
    r = client.request(method, path, headers={"Authorization": f"Bearer {_token()}"},
                       json=_SICK_NOTE_BODY if method == "post" else None)
    assert r.status_code == 403, f"{method} {path} -> {r.status_code}, gate did not bite"
    body = r.json()
    # non-vacuity: it is the patient_ehr_basic gate biting specifically
    assert body.get("detail", {}).get("capability") == "patient_ehr_basic", body


@pytest.mark.parametrize("method,path,expect_detail", [
    ("post", "/api/sick-notes", "No workspace/tenant context"),
    ("get", "/api/sick-notes/patient/pat-1", "No workspace context"),
])
def test_cap_present_passes_gate_not_false_blocked(client, method, path, expect_detail):
    # cap present but identity carries no workspace -> we get PAST the gate
    # to the handler's own tenant guard. Proves the gate does not
    # false-block, DB-free (handler returns 400 before any Supabase call).
    _override(caps=["patient_ehr_basic"], workspace_id=None, tenant_id=None)
    r = client.request(method, path, headers={"Authorization": f"Bearer {_token()}"},
                       json=_SICK_NOTE_BODY if method == "post" else None)
    assert r.status_code == 400, f"{method} {path} -> {r.status_code} (expected past-gate 400)"
    assert expect_detail in str(r.json().get("detail")), r.json()


# ---------------------------------------------------------------------------
# (2) tenant fix — RUN_INTEGRATION, residue-safe, read-back (PR-D idiom)
#
# Premise corrected after a first-run scaffolding failure (the PR-F/G/H
# recurring class): sick_notes.patient_id FKs to patients, so the fixture
# must seed a REAL tenant->workspace->patient triple (shape mirrors
# conftest.seed_practice + the live patients column shape introspected
# from the DB), not fabricate ids. Residue-safe AND residue-verified
# across every table written.
# ---------------------------------------------------------------------------

def _seed_triplet(sb, idx):
    """Real tenant -> workspace -> patient, code-bar shape. Distinct
    patient per workspace (patients.id is the FK target; one row, one
    workspace)."""
    s = uuid.uuid4().hex[:6]
    t = {"tenant_id": f"test-tn-{s}", "workspace_id": f"test-ws-{s}",
         "patient_id": f"test-pat-{s}"}
    sb.table("tenants").insert(
        {"id": t["tenant_id"], "name": "Test Tenant (sick-note cut)"}).execute()
    sb.table("workspaces").insert(
        {"id": t["workspace_id"], "tenant_id": t["tenant_id"],
         "name": "Test WS (sick-note cut)", "type": "gp"}).execute()
    sb.table("patients").insert({
        "id": t["patient_id"], "workspace_id": t["workspace_id"],
        "tenant_id": t["tenant_id"], "first_name": "Test", "last_name": "Patient",
        "dob": "1985-03-14", "id_number": f"850314{idx:04d}087",
        "contact_number": "+27821234567", "email": f"sncut-{s}@test.local",
        "address": "1 Test Rd", "medical_aid": "None",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }).execute()
    return t


def _destroy_triplet(sb, t):
    for tbl, col, val in (
        ("sick_notes", "patient_id", t["patient_id"]),
        ("patients", "id", t["patient_id"]),
        ("workspaces", "id", t["workspace_id"]),
        ("tenants", "id", t["tenant_id"]),
    ):
        try:
            sb.table(tbl).delete().eq(col, val).execute()
        except Exception:  # noqa: BLE001
            pass


@pytest.mark.integration
def test_tenant_fix_bites_by_readback_two_workspaces(client, supabase_client):
    """A note created by a workspace-X principal reads back as workspace X
    (not DEMO); a workspace-Y principal's note reads back as Y. Two
    distinct workspaces => the stored value is DERIVED from the principal,
    not the DEMO constant (a constant cannot pass a two-workspace
    parametrisation). Plus the mirror read-isolation: a workspace-Y
    principal querying workspace-X's patient sees nothing."""
    sb = supabase_client
    triplets = []
    try:
        for i in range(2):
            triplets.append(_seed_triplet(sb, i))

        for t in triplets:
            assert t["workspace_id"] != _DEMO_WS  # bite invisible if equal
            _override(caps=["patient_ehr_basic"],
                      workspace_id=t["workspace_id"], tenant_id=t["tenant_id"])
            body = {**_SICK_NOTE_BODY, "patient_id": t["patient_id"]}
            r = client.post(
                "/api/sick-notes",
                headers={"Authorization":
                         f"Bearer {_token(t['workspace_id'], t['tenant_id'])}"},
                json=body)
            assert r.status_code == 200, (t["workspace_id"], r.status_code, r.text)
            sid = r.json()["sick_note_id"]
            row = sb.table("sick_notes").select("*").eq("id", sid).execute().data
            assert row, f"sick note {sid} not found on read-back"
            stored = row[0]
            assert stored["workspace_id"] == t["workspace_id"], (
                f"tenant fix did NOT bite: stored ws={stored['workspace_id']} "
                f"expected {t['workspace_id']} (DEMO={_DEMO_WS})")
            assert stored["tenant_id"] == t["tenant_id"], stored
            assert stored["workspace_id"] != _DEMO_WS

        # mirror read-isolation
        t0, t1 = triplets
        _override(caps=["patient_ehr_basic"],
                  workspace_id=t0["workspace_id"], tenant_id=t0["tenant_id"])
        own = client.get(
            f"/api/sick-notes/patient/{t0['patient_id']}",
            headers={"Authorization":
                     f"Bearer {_token(t0['workspace_id'], t0['tenant_id'])}"})
        assert own.status_code == 200, own.text
        own_ws = {n["workspace_id"] for n in own.json()["sick_notes"]}
        assert own_ws == {t0["workspace_id"]}, f"own read wrong: {own_ws}"

        _override(caps=["patient_ehr_basic"],
                  workspace_id=t1["workspace_id"], tenant_id=t1["tenant_id"])
        cross = client.get(
            f"/api/sick-notes/patient/{t0['patient_id']}",
            headers={"Authorization":
                     f"Bearer {_token(t1['workspace_id'], t1['tenant_id'])}"})
        assert cross.status_code == 200, cross.text
        assert cross.json()["sick_notes"] == [], (
            "GET leaked across workspaces: workspace-Y principal saw "
            f"workspace-X patient's notes: {cross.json()['sick_notes']}")
    finally:
        for t in triplets:
            _destroy_triplet(sb, t)

    # Sufficiency: residue verified clean by INDEPENDENT read-back across
    # EVERY table written, keyed by the throwaway natural keys (not tracked
    # row ids), so a missed delete OR an extra row is also caught. Green
    # test => residue clean; not assumed.
    for t in triplets:
        for tbl, col, val in (
            ("sick_notes", "patient_id", t["patient_id"]),
            ("patients", "id", t["patient_id"]),
            ("workspaces", "id", t["workspace_id"]),
            ("tenants", "id", t["tenant_id"]),
        ):
            left = sb.table(tbl).select(
                "id" if tbl != "sick_notes" else "id"
            ).eq(col, val).execute().data or []
            assert not left, (
                f"RESIDUE NOT CLEAN: {len(left)} {tbl} row(s) remain for "
                f"{col}={val} after teardown")
