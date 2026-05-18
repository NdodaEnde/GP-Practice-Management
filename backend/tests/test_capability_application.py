"""
ZERO Item 1 — the load-bearing artifact for the central capability map.

Proves, parametrised over `auth_backstop.ROUTE_CAPABILITIES` itself
(never a hardcoded copy), and non-vacuous in BOTH directions:

  * wrong-capability principal -> 403 *naming the assigned capability*
    (not an incidental 403). The 403 happens AT the middleware before
    call_next, so the handler never runs -> DB-free for ALL methods
    incl. POST/DELETE (no mutation possible in this test).
  * the floor still composes underneath: no token -> 401 before the
    capability is evaluated.
  * the map's OWN non-vacuity: removing any entry flips that route to
    not-403 (the map cannot rot silently — the allowlist rider, applied
    to the capability map).
  * every map key binds to a REAL live route whose template equals the
    key (a typo'd/orphan key would silently never gate — caught here).
  * §E immovability, proven not assumed: required_capability() is None
    for every §E route (all methods, pure), and adding a §E key to the
    map would flip that (the immovability check itself bites). Plus a
    GET-only HTTP check that §E is not capability-blocked (no mutation).
  * explicitly-public (leads, medications/*) reachable unauthenticated.

DB-free: `auth_backstop.hydrate_capabilities` is stubbed (the middleware
calls it by module attribute, so the stub takes effect); tokens are real
so the floor passes; the 403 path never reaches a handler.
"""
import re

import pytest

try:
    import server
    from app.core import auth_backstop
    from app.api.auth import create_access_token
except Exception as e:  # pragma: no cover - env-dependent
    pytest.skip(f"cannot import app under test ({e})", allow_module_level=True)

from fastapi.testclient import TestClient

_PARAM = re.compile(r"\{[^}]+\}")
_MAP_ITEMS = sorted(auth_backstop.ROUTE_CAPABILITIES.items())
_E_ITEMS = sorted(auth_backstop.SECTION_E_ROUTES)


def _concrete(template: str) -> str:
    return _PARAM.sub("1", template)


def _client():
    return TestClient(server.app)


def _token(ws="ws-x", tn="t-x"):
    return create_access_token({
        "user_id": "u", "email": "e@t", "role": "clinical",
        "workspace_id": ws, "tenant_id": tn,
    })


@pytest.fixture(autouse=True)
def _restore_map(monkeypatch):
    # Any test that monkeypatches ROUTE_CAPABILITIES gets it restored.
    yield


def test_every_map_key_binds_to_a_real_route():
    """A typo'd/orphan (method,template) would silently never gate. Each
    key must resolve to a live route whose template equals the key."""
    bad = []
    for (method, template), _cap in _MAP_ITEMS:
        resolved = auth_backstop._resolve_template(
            server.app, method, _concrete(template))
        if resolved != template:
            bad.append(f"{method} {template} -> resolved {resolved!r}")
    assert not bad, "map keys not binding to real routes:\n  " + "\n  ".join(bad)


@pytest.mark.parametrize("key", [k for k, _ in _MAP_ITEMS],
                         ids=[f"{m} {t}" for (m, t), _ in _MAP_ITEMS])
def test_wrong_capability_is_403_naming_it(monkeypatch, key):
    method, template = key
    cap = auth_backstop.ROUTE_CAPABILITIES[key]
    monkeypatch.setattr(auth_backstop, "hydrate_capabilities", lambda _ws: [])
    r = _client().request(
        method, _concrete(template),
        headers={"Authorization": f"Bearer {_token()}"})
    assert r.status_code == 403, (
        f"{method} {template}: wrong-cap principal got {r.status_code}, "
        f"capability gate did not bite")
    assert r.json().get("capability") == cap, r.json()


@pytest.mark.parametrize("key", [k for k, _ in _MAP_ITEMS[:12]],
                         ids=[f"{m} {t}" for (m, t), _ in _MAP_ITEMS[:12]])
def test_no_token_is_401_floor_composes(key):
    method, template = key
    r = _client().request(method, _concrete(template))
    assert r.status_code == 401, (
        f"{method} {template}: no token gave {r.status_code}, floor not "
        f"composing under the capability layer")


@pytest.mark.parametrize(
    "key",
    [k for k, _ in _MAP_ITEMS if k[0] == "GET"],
    ids=[f"{m} {t}" for (m, t), _ in _MAP_ITEMS if m == "GET"])
def test_correct_capability_not_false_blocked(monkeypatch, key):
    # GET-only (read, no mutation): cap present -> NOT a capability-403,
    # i.e. the request passes the gate to the handler. Proves the gate
    # does not false-block.
    method, template = key
    cap = auth_backstop.ROUTE_CAPABILITIES[key]
    monkeypatch.setattr(auth_backstop, "hydrate_capabilities", lambda _ws: [cap])
    r = _client().request(
        method, _concrete(template),
        headers={"Authorization": f"Bearer {_token()}"})
    assert r.status_code != 403, (
        f"{method} {template}: correct-cap principal was 403'd "
        f"(false-block); body={r.text[:200]}")


def test_section_E_is_not_gated_pure():
    """§E immovability, pure + DB-free + all methods: the map must NOT
    assign a capability to any §E route."""
    leaked = []
    for method, template in _E_ITEMS:
        cap = auth_backstop.required_capability(
            server.app, method, _concrete(template))
        if cap is not None:
            leaked.append(f"{method} {template} -> {cap}")
    assert not leaked, "§E routes gained a capability (must stay floor-only):\n  " \
        + "\n  ".join(leaked)


def test_section_E_immovability_check_is_non_vacuous(monkeypatch):
    """If the immovability check couldn't detect a §E row being gated it
    would be vacuous. Add a §E key to the map -> required_capability must
    then return it (the check bites)."""
    method, template = next(iter(_E_ITEMS))
    patched = dict(auth_backstop.ROUTE_CAPABILITIES)
    patched[(method, template)] = "patient_ehr_basic"
    monkeypatch.setattr(auth_backstop, "ROUTE_CAPABILITIES", patched)
    assert auth_backstop.required_capability(
        server.app, method, _concrete(template)) == "patient_ehr_basic"


@pytest.mark.parametrize(
    "key",
    [k for k in _E_ITEMS if k[0] == "GET"],
    ids=[f"{m} {t}" for (m, t) in _E_ITEMS if m == "GET"])
def test_section_E_get_not_capability_blocked(monkeypatch, key):
    method, template = key
    monkeypatch.setattr(auth_backstop, "hydrate_capabilities", lambda _ws: [])
    r = _client().request(
        method, _concrete(template),
        headers={"Authorization": f"Bearer {_token()}"})
    assert r.status_code != 403, (
        f"§E {method} {template} was capability-403'd — §E must stay "
        f"floor-only, undecided")


@pytest.mark.parametrize("key", [k for k, _ in _MAP_ITEMS],
                         ids=[f"{m} {t}" for (m, t), _ in _MAP_ITEMS])
def test_map_is_non_vacuous_each_entry_bites(monkeypatch, key):
    """The rider: each entry is load-bearing. Proven at the DECISION
    layer (pure, DB-free, all methods safe — no handler executes): with
    the entry, required_capability returns the cap; remove it and the
    same route's decision flips to None. A non-biting entry is dead."""
    method, template = key
    cap = auth_backstop.ROUTE_CAPABILITIES[key]
    concrete = _concrete(template)
    assert auth_backstop.required_capability(server.app, method, concrete) == cap
    patched = dict(auth_backstop.ROUTE_CAPABILITIES)
    patched.pop(key)
    monkeypatch.setattr(auth_backstop, "ROUTE_CAPABILITIES", patched)
    assert auth_backstop.required_capability(
        server.app, method, concrete) is None, (
        f"removing {method} {template} did not flip its decision — vacuous")


def test_explicitly_public_is_floor_exempt_pure():
    """LOCKED public: leads + medications/* must be floor-exempt. Pure
    (is_public), so no handler runs — POST /api/leads is a write; this
    must not mutate to prove a lock."""
    assert auth_backstop.is_public("POST", "/api/leads")
    assert auth_backstop.is_public("GET", "/api/medications/search")
    assert auth_backstop.is_public("GET", "/api/medications/12345")


@pytest.mark.parametrize("path", ["/api/medications/search", "/api/medications/1"])
def test_medications_reachable_unauthenticated_readonly(path):
    # GET only (read, no mutation): end-to-end proof the public lock holds
    # through the live middleware, not just the predicate.
    r = _client().get(path)
    assert r.status_code != 401, f"GET {path} public-locked but floor 401'd it"
