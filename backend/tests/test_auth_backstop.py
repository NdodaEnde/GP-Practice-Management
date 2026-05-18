"""
The class-closed authentication-floor test — the load-bearing artifact of ZERO.

Non-vacuous in BOTH directions (the locked rider):
  (a) the route set is enumerated from `server.app` AT RUNTIME, so any
      newly added route is asserted automatically and inherits *deny*
      with no human action; a vacuity guard asserts the asserted-route
      count cannot silently collapse to a passing-but-empty set.
  (b) the public allowlist is proven load-bearing: removing ANY entry
      must flip that path to 401. An allowlist entry that does not bite
      is a silent exception and fails this test.

DB-free: the floor rejects at the middleware BEFORE any route handler /
Supabase access, so the unauthenticated assertions never touch the DB.

Scaffolding written to the code bar: reviewed before run; the only
shared state is the in-process app object (no teardown / no residue);
the bite was demonstrated pre-fix with a read-only GET probe so the
comprehensive all-method run only ever executes once the floor
short-circuits before handlers (no pre-fix mutation).
"""
import re

import pytest

# Live-or-skip, consistent with conftest's Supabase philosophy.
try:
    import server
    from app.core import auth_backstop
except Exception as e:  # pragma: no cover - env-dependent
    pytest.skip(f"cannot import app under test ({e})", allow_module_level=True)

from fastapi.testclient import TestClient
from starlette.routing import Route

_PARAM = re.compile(r"\{[^}]+\}")
_METHOD_PREFERENCE = ("GET", "POST", "PUT", "PATCH", "DELETE")


def _client() -> TestClient:
    # No context manager -> no lifespan/startup -> the document-watcher
    # background task never starts.
    return TestClient(server.app)


def _route_matrix():
    """(method, concrete_path, raw_path) for every concrete HTTP route on
    the live app. Path params -> '1' so the request reaches the real
    route instead of 404-ing on literal braces."""
    out = []
    for r in server.app.routes:
        if not isinstance(r, Route) or not getattr(r, "methods", None):
            continue
        methods = {m for m in r.methods if m not in ("HEAD", "OPTIONS")}
        if not methods:
            continue
        method = next((m for m in _METHOD_PREFERENCE if m in methods), None)
        if method is None:
            continue
        out.append((method, _PARAM.sub("1", r.path), r.path))
    return out


def test_every_non_public_route_rejects_unauthenticated():
    client = _client()
    asserted = 0
    leaks = []
    for method, path, raw in _route_matrix():
        if auth_backstop.is_public(method, path):
            continue
        asserted += 1
        resp = client.request(method, path)
        if resp.status_code != 401:
            leaks.append(f"{method} {raw} -> {resp.status_code} (want 401)")
    # Direction (a) vacuity guard: enumeration cannot silently empty out.
    assert asserted >= 50, (
        f"only {asserted} non-public routes asserted — route enumeration "
        f"is broken; the test would pass vacuously"
    )
    assert not leaks, (
        f"{len(leaks)} non-public route(s) reachable UNAUTHENTICATED:\n  "
        + "\n  ".join(sorted(leaks))
    )


def test_public_paths_reachable_unauthenticated():
    client = _client()
    for p in sorted(auth_backstop.PUBLIC_PATHS):
        # Public => floor must not 401. Handler may 200/405/422 — all fine;
        # we only assert the floor did not reject it.
        assert client.get(p).status_code != 401, f"public path {p} got 401"


def test_allowlist_is_non_vacuous_each_entry_bites(monkeypatch):
    """Direction (b): every allowlist entry is load-bearing. Remove it and
    the floor must re-engage (401). A non-biting entry is a silent
    exception, which fails here."""
    client = _client()
    full = set(auth_backstop.PUBLIC_PATHS)
    for entry in sorted(full):
        monkeypatch.setattr(auth_backstop, "PUBLIC_PATHS",
                            frozenset(full - {entry}))
        code = client.get(entry).status_code
        monkeypatch.setattr(auth_backstop, "PUBLIC_PATHS", frozenset(full))
        assert code == 401, (
            f"removing {entry!r} from the allowlist did not re-engage the "
            f"floor (got {code}) — the entry is vacuous"
        )
