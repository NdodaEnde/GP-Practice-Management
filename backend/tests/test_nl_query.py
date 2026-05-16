"""
PR C — NL mapping tests. DB-free, network-free, every commit.

THE load-bearing gate is `test_nl_disabled_constructs_no_client_and_
makes_no_network_call`: it is PR C's silent-dead-link / inertness
equivalent — the one property the entire merge stands on, proven
un-mockably on the REAL path with the flag off, asserting silence at
three independent layers (client construction, outbound socket, provider
import). The rest proves the output-domain constraint (NOT mapping
correctness — that is unverified at merge by design) and that NL adds no
new data path.
"""

from __future__ import annotations

import builtins
import json
import socket
import types

import pytest

import app.services.nl_query as nlq


# ===========================================================================
# THE NAMED DEFAULT-OFF GATE (build first, prove un-mockable, then the rest)
# ===========================================================================

def test_default_is_structurally_off():
    """The merge default: the env var is absent and no commit sets it,
    so the real setting is False without any monkeypatching."""
    from app.core.config import settings
    assert settings.NL_QUERY_LLM_ENABLED is False


def test_nl_disabled_constructs_no_client_and_makes_no_network_call(monkeypatch):
    """Flag off, REAL `classify_question`, deliberately PII-bearing
    input. Three independent traps — a `_client` sentinel, a
    `socket.socket.connect` trap, an `__import__` trap on the provider
    module — must ALL stay silent. This is un-mockable: the refusal
    happens before `_client()`, before any import, before any network,
    so none of the three can fire if the gate holds. (Three layers, not
    one, because the regression is a future refactor moving the import
    to module scope or calling `_client()` before the gate — a single
    trap at the wrong layer would miss it.)"""
    from app.core.config import settings
    monkeypatch.setattr(settings, "NL_QUERY_LLM_ENABLED", False)

    fired = {"client": False, "socket": False, "import": False}

    def _sentinel_client(*a, **k):
        fired["client"] = True
        raise AssertionError("_client() reached with flag off")
    monkeypatch.setattr(nlq, "_client", _sentinel_client)

    real_connect = socket.socket.connect

    def _trap_connect(self, *a, **k):
        fired["socket"] = True
        raise AssertionError("outbound socket.connect attempted with flag off")
    monkeypatch.setattr(socket.socket, "connect", _trap_connect)

    real_import = builtins.__import__

    def _trap_import(name, *a, **k):
        if name == "openai" or name.startswith("openai."):
            fired["import"] = True
            raise AssertionError("provider module imported with flag off")
        return real_import(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", _trap_import)

    # Deliberately PII-bearing: a real patient name in the question.
    result = nlq.classify_question("show me Jane Doe's recent consultations")

    monkeypatch.setattr(builtins, "__import__", real_import)
    monkeypatch.setattr(socket.socket, "connect", real_connect)

    assert isinstance(result, nlq.NLRefusal)
    assert result.reason == "nl_disabled"
    assert result.answerable, "refusal must still carry the answerable list"
    # The whole point: nothing fired.
    assert fired == {"client": False, "socket": False, "import": False}


def test_traps_are_non_vacuous_each_fires_with_flag_ON(monkeypatch):
    """The discriminating check: a gate proven only by SILENCE is not
    proven — the flag-off green could mean "boundary held" OR "the path
    that would trip the traps was never reached" (the
    superseded_count=0-for-the-wrong-reason / ratchet-must-bite
    discipline). So with the flag ON, each trap MUST fire on the thing
    it guards. Three independent flag-on invocations, one trap armed
    each (armed together they pre-empt each other — the `_client`
    sentinel would fire before the import trap, etc.). If any of these
    does NOT fire, the corresponding flag-off silence is worthless.
    Shipped (not a one-time local check) so the non-vacuity is a
    permanent CI property, exactly like PR B's ratchet."""
    from app.core.config import settings

    # (a) `_client` sentinel — proves the construction-layer trap bites.
    monkeypatch.setattr(settings, "NL_QUERY_LLM_ENABLED", True)
    fired_a = {"v": False}

    def _sentinel(*a, **k):
        fired_a["v"] = True
        raise AssertionError("_client reached")
    monkeypatch.setattr(nlq, "_client", _sentinel)
    try:
        nlq.classify_question("anything")
    except BaseException:  # noqa: BLE001 — we only care that it fired
        pass
    assert fired_a["v"], "_client sentinel did NOT fire flag-on — vacuous"
    monkeypatch.undo()

    # (b) `__import__` trap — proves the provider-import-layer trap bites.
    #     No `_client` monkeypatch, so the REAL _client() runs and
    #     `from openai import OpenAI` is reached (openai is importable;
    #     the import precedes the api-key check, so no key needed).
    monkeypatch.setattr(settings, "NL_QUERY_LLM_ENABLED", True)
    fired_b = {"v": False}
    real_import = builtins.__import__

    def _trap_import(name, *a, **k):
        if name == "openai" or name.startswith("openai."):
            fired_b["v"] = True
            raise AssertionError("provider import reached")
        return real_import(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", _trap_import)
    try:
        nlq.classify_question("anything")
    except BaseException:  # noqa: BLE001
        pass
    monkeypatch.setattr(builtins, "__import__", real_import)
    assert fired_b["v"], "__import__ trap did NOT fire flag-on — vacuous"
    monkeypatch.undo()

    # (c) `socket.connect` trap — proves the network-layer trap bites.
    #     Real _client() + real import + OpenAI(api_key=dummy)
    #     (construction is network-free); the outbound connect happens
    #     in _invoke()'s completions call → the trap fires there.
    monkeypatch.setattr(settings, "NL_QUERY_LLM_ENABLED", True)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-not-a-real-key-for-trap-test")
    monkeypatch.setattr(nlq, "_llm_client", None)  # force re-construct
    fired_c = {"v": False}
    real_connect = socket.socket.connect

    def _trap_connect(self, *a, **k):
        fired_c["v"] = True
        raise AssertionError("outbound connect reached")
    monkeypatch.setattr(socket.socket, "connect", _trap_connect)
    try:
        nlq.classify_question("anything")
    except BaseException:  # noqa: BLE001
        pass
    monkeypatch.setattr(socket.socket, "connect", real_connect)
    assert fired_c["v"], "socket.connect trap did NOT fire flag-on — vacuous"


def test_direct_client_call_also_refuses_when_disabled(monkeypatch):
    """Defence in depth: even a DIRECT `_client()` call (bypassing
    classify_question) refuses with the flag off — the provider import
    is never reached."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "NL_QUERY_LLM_ENABLED", False)
    with pytest.raises(RuntimeError, match="NL_QUERY_LLM_ENABLED off"):
        nlq._client()


# ===========================================================================
# The /ask endpoint with the flag off — the named gate at the HTTP surface
# ===========================================================================

from fastapi import FastAPI                                     # noqa: E402
from fastapi.testclient import TestClient                       # noqa: E402

import app.api.query as query_api                               # noqa: E402
from app.api.auth import get_current_user                       # noqa: E402


def _app_and_client(monkeypatch, *, recorder=None):
    """Minimal app mounting the real query router; only get_current_user
    overridden, so the REAL require_capability gate runs (PR A's
    test_query_api harness). A run_template recorder proves the
    no-new-data-path property when wired."""
    app = FastAPI()
    app.include_router(query_api.router)

    if recorder is not None:
        def fake_run_template(supabase, template_id, params, *, workspace_id):
            recorder["run_template"] = {
                "template_id": template_id, "params": params,
                "workspace_id": workspace_id,
            }
            from ontology.query.result import (
                Provenance, QueryResult, QueryRow,
            )
            return QueryResult(
                template_id=template_id, template_version=1,
                workspace_id=workspace_id,
                rows=[QueryRow(data={"patient_id": "p1"},
                               provenance=Provenance(source_kind="diagnosis",
                                                     source_document_id="d1"))],
                row_count=1, data_maturity="populated",
            )

        def fake_resolve(supabase, result, *, workspace_id):
            recorder["resolve_provenance"] = {"workspace_id": workspace_id}
            return result  # to_dict() is enough for the assertions

        # patch on a tiny shim object so .to_dict() works
        class _R:
            def __init__(self, r): self._r = r
            def to_dict(self): return {"rows": [], "row_count": self._r.row_count}

        monkeypatch.setattr(query_api, "run_template", fake_run_template)
        monkeypatch.setattr(query_api, "resolve_provenance",
                            lambda s, r, *, workspace_id: (
                                recorder.__setitem__(
                                    "resolve_provenance",
                                    {"workspace_id": workspace_id}) or _R(r)))
        monkeypatch.setattr(query_api, "_sb", lambda: object())

    def make_user(**over):
        u = {"email": "doc@x", "workspace_id": "ws-AUTH",
             "capabilities": ["clinical_query"]}
        u.update(over)
        return u

    app.dependency_overrides[get_current_user] = lambda: make_user()
    app.state._make_user = make_user
    return app, TestClient(app), make_user


def test_ask_endpoint_hard_refuses_when_disabled(monkeypatch):
    """Named gate at the HTTP surface. Real router + REAL
    require_capability (only get_current_user overridden), flag off:
    POST /api/query/ask returns the feature-gated refusal with the
    answerable list; run_template is never called; no _sb()/network."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "NL_QUERY_LLM_ENABLED", False)

    called = {"run_template": False, "sb": False}
    monkeypatch.setattr(query_api, "run_template",
                        lambda *a, **k: called.__setitem__("run_template", True))
    monkeypatch.setattr(query_api, "_sb",
                        lambda: called.__setitem__("sb", True))

    _app, client, _mk = _app_and_client(monkeypatch)
    r = client.post("/api/query/ask",
                    json={"question": "show me Jane Doe's medications"})
    assert r.status_code == 403
    body = r.json()["detail"]
    assert body["reason"] == "nl_disabled"
    assert body["answerable"], "refusal must carry the answerable list"
    assert called == {"run_template": False, "sb": False}


# ===========================================================================
# Output-domain constraint — the drift gate (registry ⇔ tool schema)
# ===========================================================================

def test_tool_schema_is_exactly_the_registry():
    """The anti-drift gate. The model's entire callable surface is the
    registry-derived tool set + the synthetic `refuse` — it cannot list
    an unregistered template, omit a registered one, or surface a
    `validator` (callable, unserialisable). Same drift-impossible status
    as PR B's registry-iterating invariants."""
    from ontology.query import all_templates

    tools = nlq.build_tool_schema()
    names = {t["function"]["name"] for t in tools}
    registry_ids = {t.id for t in all_templates()}
    assert names == registry_ids | {nlq.REFUSE_TOOL}

    by_name = {t["function"]["name"]: t for t in tools}
    for tpl in all_templates():
        params = by_name[tpl.id]["function"]["parameters"]
        assert set(params["properties"]) == {p.name for p in tpl.params}
        assert set(params["required"]) == {
            p.name for p in tpl.params if p.required
        }
    # No validator / no callable anywhere in the serialised schema.
    blob = json.dumps(tools, default=lambda o: "<UNSERIALISABLE>")
    assert "<UNSERIALISABLE>" not in blob
    assert "validator" not in blob


# ===========================================================================
# Mocked-LLM WIRING (NOT intelligence — labelled). Flag ON, fake _invoke.
# ===========================================================================

def _fake_resp(tool_name, args: dict | None, *, no_tool=False, bad_json=False):
    if no_tool:
        msg = types.SimpleNamespace(tool_calls=[])
    else:
        arg_str = "{not json" if bad_json else json.dumps(args or {})
        fn = types.SimpleNamespace(name=tool_name, arguments=arg_str)
        msg = types.SimpleNamespace(
            tool_calls=[types.SimpleNamespace(function=fn)])
    return types.SimpleNamespace(
        choices=[types.SimpleNamespace(message=msg)])


def _enable_with_fake(monkeypatch, resp):
    from app.core.config import settings
    monkeypatch.setattr(settings, "NL_QUERY_LLM_ENABLED", True)
    monkeypatch.setattr(nlq, "_client", lambda: object())  # never network
    monkeypatch.setattr(nlq, "_invoke",
                        lambda client, messages, tools, model: resp)


@pytest.mark.parametrize("tpl,params", [
    ("patients_with_diagnosis_prefix", {"icd10_prefix": "E11"}),
    ("patients_not_seen_since", {"days_since": 180}),
    ("patient_active_medications", {"patient_id": "p1"}),
    ("patient_recent_consultations", {"patient_id": "p1", "limit": 5}),
    ("patients_with_abnormal_recent_vitals", {"within_days": 90}),
    ("patient_open_documents", {}),
    ("patients_with_lab_threshold", {"test_code": "HBA1C"}),
])
def test_wiring_passes_tool_selection_through_uninterpreted(
        monkeypatch, tpl, params):
    """WIRING ONLY — proves: given the model selects tool T with args A,
    classify_question returns NLClassification(T, A) with params passed
    through UNINTERPRETED (the runner validates, not this module). It
    does NOT prove the model picks T for any real phrasing — that is
    accuracy, unverified at merge, only knowable via the opt-in eval."""
    _enable_with_fake(monkeypatch, _fake_resp(tpl, params))
    out = nlq.classify_question("(phrasing irrelevant — LLM mocked)")
    assert isinstance(out, nlq.NLClassification)
    assert out.template_id == tpl
    assert out.params == params  # uninterpreted passthrough


# ===========================================================================
# Refusal matrix — Decision-4 hazard shapes (NOT generic gibberish)
# ===========================================================================

def test_refuse_tool_yields_refusal_with_answerable_list(monkeypatch):
    _enable_with_fake(monkeypatch, _fake_resp(nlq.REFUSE_TOOL, {}))
    out = nlq.classify_question("something the model declines")
    assert isinstance(out, nlq.NLRefusal)
    assert out.reason == "out_of_set"
    assert {a["id"] for a in out.answerable}  # non-empty answerable list


def test_hallucinated_unregistered_tool_is_refused_never_executed(monkeypatch):
    """A plausible-but-unregistered shape: the model names a tool that
    is not in the registry. Must refuse with the answerable list, NEVER
    approximate to the nearest template, never execute."""
    _enable_with_fake(monkeypatch,
                      _fake_resp("patients_with_unicorns", {"x": 1}))
    out = nlq.classify_question("how many unicorn patients do I have")
    assert isinstance(out, nlq.NLRefusal)
    assert out.reason == "out_of_set"
    assert any(a["id"] == "patients_with_diagnosis_prefix"
               for a in out.answerable)


def test_no_tool_call_is_refused(monkeypatch):
    _enable_with_fake(monkeypatch, _fake_resp(None, None, no_tool=True))
    out = nlq.classify_question("...")
    assert isinstance(out, nlq.NLRefusal)
    assert out.reason == "low_confidence"


def test_malformed_arguments_are_refused_not_guessed(monkeypatch):
    _enable_with_fake(monkeypatch,
                      _fake_resp("patient_active_medications", None,
                                 bad_json=True))
    out = nlq.classify_question("meds for someone")
    assert isinstance(out, nlq.NLRefusal)
    assert out.reason == "low_confidence"


def test_near_miss_pair_one_maps_one_refuses(monkeypatch):
    """The Decision-4 hazard the structural gates CANNOT see: two
    phrasings differing by a clinically material term — one is a valid
    mapping, the near-miss must refuse. WIRING form: we fixture the
    model's *decision* (accuracy is the eval's job, not this test's);
    this proves the SYSTEM executes the mapped one and refuses the
    refused one, never approximating. The model actually making that
    call correctly is accuracy — unverified at merge, labelled."""
    # Phrasing A — maps cleanly.
    _enable_with_fake(monkeypatch,
                      _fake_resp("patients_not_seen_since",
                                 {"days_since": 180}))
    a = nlq.classify_question("patients not seen in 6 months")
    assert isinstance(a, nlq.NLClassification)
    assert a.template_id == "patients_not_seen_since"
    # Phrasing B — the near-miss (e.g. "patients I should NOT see again")
    # — the model (correctly) declines; the system must refuse, not
    # approximate to patients_not_seen_since.
    _enable_with_fake(monkeypatch, _fake_resp(nlq.REFUSE_TOOL, {}))
    b = nlq.classify_question("patients I should not see again")
    assert isinstance(b, nlq.NLRefusal)
    assert b.reason == "out_of_set"


# ===========================================================================
# No new data path + tenant scope (mirrors PR A's forged-body-inert)
# ===========================================================================

def test_ask_reaches_data_only_through_run_template(monkeypatch):
    """A successful /ask reaches data via EXACTLY
    run_template→resolve_provenance — the same chokepoint /run uses,
    nothing else. The classifier is mocked to a fixed mapping (wiring,
    not accuracy)."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "NL_QUERY_LLM_ENABLED", True)
    monkeypatch.setattr(
        nlq, "classify_question",
        lambda q, **k: nlq.NLClassification(
            template_id="patient_active_medications",
            params={"patient_id": "p1"}))

    rec: dict = {}
    _app, client, _mk = _app_and_client(monkeypatch, recorder=rec)
    r = client.post("/api/query/ask",
                    json={"question": "what is p1 on",
                          "workspace_id": "ws-EVIL"})  # forged — inert
    assert r.status_code == 200, r.text
    # The runner got the AUTH workspace, never the forged body value.
    assert rec["run_template"]["workspace_id"] == "ws-AUTH"
    assert rec["run_template"]["template_id"] == "patient_active_medications"
    assert "resolve_provenance" in rec  # the only other data touchpoint
    assert r.json()["interpreted_as"] == {
        "template_id": "patient_active_medications",
        "params": {"patient_id": "p1"},
    }


def test_ask_capability_gated(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "NL_QUERY_LLM_ENABLED", True)
    app, client, mk = _app_and_client(monkeypatch)
    app.dependency_overrides[get_current_user] = lambda: mk(capabilities=[])
    r = client.post("/api/query/ask", json={"question": "anything"})
    assert r.status_code == 403
    assert r.json()["detail"]["capability"] == "clinical_query"


def test_ask_requires_workspace(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "NL_QUERY_LLM_ENABLED", True)
    monkeypatch.setattr(
        nlq, "classify_question",
        lambda q, **k: nlq.NLClassification("patient_open_documents", {}))
    app, client, mk = _app_and_client(monkeypatch)
    app.dependency_overrides[get_current_user] = lambda: mk(workspace_id=None)
    r = client.post("/api/query/ask", json={"question": "open docs"})
    assert r.status_code == 400
