"""
PR A — HTTP surface tests for POST /api/query/run. No DB.

The load-bearing one is `test_forged_body_workspace_is_inert`: it proves
the tenant boundary on the highest-blast-radius read surface is not a
check that can be fooled but the *absence of any path* from the request
body to the workspace scope. The rest prove the endpoint never emits a
row without a resolved source and surfaces the cohort-level
unresolvable_count a clinician actually reads.
"""

from __future__ import annotations

import types

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.query as query_api
from app.api.auth import get_current_user
from ontology.query.result import LIVE_ENTRY, Provenance, QueryResult, QueryRow


# --- a fake Supabase good enough for the real resolver --------------------

class _FakeTable:
    def __init__(self, rows):
        self._rows, self._ids, self._ws = rows, None, None

    def select(self, *_a, **_k):
        return self

    def in_(self, _c, vals):
        self._ids = set(vals)
        return self

    def eq(self, c, v):
        if c == "workspace_id":
            self._ws = v
        return self

    def execute(self):
        out = [r for r in self._rows
               if (self._ids is None or r["id"] in self._ids)
               and (self._ws is None or r.get("workspace_id") == self._ws)]
        return types.SimpleNamespace(data=out)


class _FakeBucket:
    def create_signed_url(self, path, expires_in):
        return {"signedURL": f"https://signed.example/{path}"}


class _FakeStorage:
    def from_(self, _b):
        return _FakeBucket()


class FakeSupabase:
    def __init__(self, docs):
        self._docs = docs
        self.storage = _FakeStorage()

    def table(self, _n):
        return _FakeTable(self._docs)


_DOC = {
    "id": "doc-present-1",
    "workspace_id": "ws-AUTH",
    "filename": "Patient file.pdf",
    "file_path": "ws-AUTH/doc-present-1/Patient file.pdf",
    "upload_date": "2026-05-07T17:03:10",
    "created_at": "2026-05-07T17:03:10",
}


@pytest.fixture
def client_and_recorder(monkeypatch):
    """Minimal app mounting only the query router. get_current_user is
    overridden (so the REAL require_capability gate runs against our fake
    user). run_template is recorded; resolve_provenance is the real one
    over a FakeSupabase."""
    app = FastAPI()
    app.include_router(query_api.router)

    recorder = {}

    def fake_run_template(supabase, template_id, params, *, workspace_id):
        recorder["template_id"] = template_id
        recorder["params"] = params
        recorder["workspace_id"] = workspace_id
        return QueryResult(
            template_id=template_id, template_version=1,
            workspace_id=workspace_id,
            rows=[
                QueryRow(data={"patient_id": "p1"},
                         provenance=Provenance(source_kind="diagnosis",
                                               source_document_id="doc-present-1")),
                QueryRow(data={"patient_id": "p2"},
                         provenance=Provenance(source_kind="diagnosis",
                                               source_document_id="11112222e15a71")),
                QueryRow(data={"patient_id": "p3"},
                         provenance=Provenance(source_kind=LIVE_ENTRY)),
            ],
            row_count=3, data_maturity="populated",
        )

    monkeypatch.setattr(query_api, "run_template", fake_run_template)
    monkeypatch.setattr(query_api, "_sb", lambda: FakeSupabase([_DOC]))

    def make_user(**over):
        u = {"email": "doc@x", "workspace_id": "ws-AUTH",
             "capabilities": ["clinical_query"]}
        u.update(over)
        return u

    app.state._make_user = make_user
    app.dependency_overrides[get_current_user] = lambda: make_user()
    return app, TestClient(app), recorder, make_user


def test_forged_body_workspace_is_inert(client_and_recorder):
    """A client that puts workspace_id in the body achieves nothing: the
    model has no such field and the runner is handed the AUTH workspace."""
    app, client, recorder, _ = client_and_recorder
    r = client.post("/api/query/run", json={
        "template_id": "patients_with_diagnosis_prefix",
        "params": {"icd10_prefix": "E11"},
        "workspace_id": "ws-EVIL",          # forged — must be ignored
        "params_workspace": "ws-EVIL",
    })
    assert r.status_code == 200, r.text
    assert recorder["workspace_id"] == "ws-AUTH"   # NOT ws-EVIL
    assert r.json()["workspace_id"] == "ws-AUTH"


def test_every_row_is_resolved_and_unresolvable_is_visible(client_and_recorder):
    app, client, recorder, _ = client_and_recorder
    r = client.post("/api/query/run", json={
        "template_id": "patients_with_diagnosis_prefix",
        "params": {"icd10_prefix": "E11"},
    })
    body = r.json()
    assert r.status_code == 200, r.text
    assert body["unresolvable_count"] == 1
    sources = [row["source"] for row in body["rows"]]
    # No row ever ships without a source object.
    assert all(s is not None and "status" in s for s in sources)
    present, missing, live = sources
    assert present["status"] == "openable" and present["signed_url"]
    assert missing["status"] == "unresolvable"
    assert missing["signed_url"] is None
    assert "…e15a71" in missing["citation"]          # locked decision #3
    assert missing["unresolvable_reason"] == \
        "source_document_not_found_in_workspace"
    assert live["status"] == "no_source"             # not counted, not a failure


def test_capability_gate_blocks_without_clinical_query(client_and_recorder):
    """The REAL require_capability gate runs (only get_current_user is
    overridden). A user without the capability gets a structured 403."""
    app, client, recorder, make_user = client_and_recorder
    app.dependency_overrides[get_current_user] = \
        lambda: make_user(capabilities=[])
    r = client.post("/api/query/run", json={
        "template_id": "patients_with_diagnosis_prefix",
        "params": {"icd10_prefix": "E11"},
    })
    assert r.status_code == 403
    assert r.json()["detail"]["capability"] == "clinical_query"


def test_missing_workspace_context_is_400(client_and_recorder):
    app, client, recorder, make_user = client_and_recorder
    app.dependency_overrides[get_current_user] = \
        lambda: make_user(workspace_id=None)
    r = client.post("/api/query/run", json={
        "template_id": "patients_with_diagnosis_prefix",
        "params": {"icd10_prefix": "E11"},
    })
    assert r.status_code == 400


@pytest.mark.parametrize("code,expected", [
    ("unknown_template", 404),
    ("invalid_param", 422),
    ("template_unavailable", 503),
    ("provenance_missing", 500),
    ("something_else", 400),
])
def test_query_error_codes_map_to_http_status(client_and_recorder, monkeypatch,
                                               code, expected):
    app, client, recorder, _ = client_and_recorder
    from ontology.query import QueryError

    def boom(*_a, **_k):
        raise QueryError(code, f"simulated {code}", {"x": 1})

    monkeypatch.setattr(query_api, "run_template", boom)
    r = client.post("/api/query/run", json={
        "template_id": "whatever", "params": {},
    })
    assert r.status_code == expected
    assert r.json()["detail"]["error"] == code


def test_templates_listing_is_capability_gated(client_and_recorder):
    app, client, recorder, make_user = client_and_recorder
    ok = client.get("/api/query/templates")
    assert ok.status_code == 200
    assert any(t["id"] == "patients_with_diagnosis_prefix"
               for t in ok.json()["templates"])
    app.dependency_overrides[get_current_user] = \
        lambda: make_user(capabilities=[])
    assert client.get("/api/query/templates").status_code == 403
