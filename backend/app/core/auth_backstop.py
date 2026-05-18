"""
Deny-by-default authentication backstop — the STRUCTURAL FLOOR.

Why a global middleware and not per-route decorators: per-route gating
fails by silent omission (forget the dependency -> open route). That is
the exact failure mode that left 81/84 server.py @api_router routes
unauthenticated. The floor is enforced for EVERY request to EVERY route
on the app, so a newly added route inherits *deny* with no human action.
Per-route `require_capability(...)` stays as the authorization
GRANULARITY layer on top of this authentication FLOOR.

This module is built in two parts, deliberately:
  * phase 1 (this commit's first step): the PUBLIC allowlist + the
    `is_public` predicate ONLY. No enforcement.
  * phase 2: `AuthBackstopMiddleware`, added only AFTER the class-closed
    test is proven to bite without it.

The allowlist is deliberately MINIMAL and every entry carries its
justification. It is the single diff-visible exception surface; the test
proves it non-vacuous — removing any entry must flip that path to 401.
"""
from __future__ import annotations

from typing import Optional

# Exact-match public paths. Each entry MUST carry its justification.
PUBLIC_PATHS: frozenset = frozenset({
    "/api/auth/login",     # cannot require a token to obtain a token
    "/api/auth/refresh",   # token refresh: same reason
    "/api/",               # root liveness (@api_router GET "/" under /api prefix)
    "/api/health",         # health probe (Docker HEALTHCHECK / load balancers)
})

# REVIEW (schema exposure): FastAPI auto-docs. Keeping these public leaves
# the API inspectable, but /openapi.json leaks the full route map. Gating
# them behind auth is the stronger posture and is an explicit decision for
# the per-route granularity pass — recorded here so it is NOT a silent
# permanent exception.
_DOCS_PUBLIC = {"/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect"}


def is_public(method: str, path: str) -> bool:
    """True iff this request bypasses the authentication floor.

    PUBLIC_PATHS is read at call time (module attribute lookup), so the
    non-vacuity test can remove an entry and observe the floor re-engage.
    """
    if method.upper() == "OPTIONS":
        # CORS preflight is unauthenticated by spec and exposes no data.
        return True
    if path in PUBLIC_PATHS:
        return True
    if path in _DOCS_PUBLIC or path.startswith("/docs/"):
        return True
    return False


def extract_bearer(authorization: Optional[str]) -> Optional[str]:
    """Return the bearer token from an Authorization header, or None."""
    if not authorization:
        return None
    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        return None
    return parts[1].strip()


# ---------------------------------------------------------------------------
# phase 2: enforcement. Added only after the class-closed test was proven to
# bite without it.
# ---------------------------------------------------------------------------

from starlette.middleware.base import BaseHTTPMiddleware  # noqa: E402
from starlette.requests import Request  # noqa: E402
from starlette.responses import JSONResponse  # noqa: E402

# Reuse the existing JWT primitive — do not reinvent token validation.
from app.api.auth import decode_token  # noqa: E402

def _deny() -> JSONResponse:
    # Fresh response per call (a shared instance must not be reused across
    # requests). Shape mirrors FastAPI's HTTPBearer 401 so the frontend's
    # existing 401->refresh interceptor handles it uniformly.
    return JSONResponse(
        {"detail": "Not authenticated"},
        status_code=401,
        headers={"WWW-Authenticate": "Bearer"},
    )


class AuthBackstopMiddleware(BaseHTTPMiddleware):
    """Deny-by-default authentication floor for EVERY route on the app.

    Fails closed: any token problem -> 401, never pass-through. This is
    the authentication floor only; per-route `require_capability(...)`
    remains the authorization granularity layer above it.
    """

    async def dispatch(self, request: Request, call_next):
        method = request.method
        path = request.url.path
        if is_public(method, path):
            return await call_next(request)

        token = extract_bearer(request.headers.get("Authorization"))
        if not token:
            return _deny()
        try:
            payload = decode_token(token)
        except Exception:
            # decode_token raises HTTPException(401) on bad token; any
            # other failure is also treated as auth failure (fail closed).
            return _deny()
        if not isinstance(payload, dict) or payload.get("type") != "access":
            # Parity with get_current_user: refresh tokens are not access.
            return _deny()
        return await call_next(request)
