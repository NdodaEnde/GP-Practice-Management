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
    "/api/leads",          # LOCKED public: marketing lead-capture, no
                           # authenticated principal by definition.
                           # §F abuse-hardening tracked separately.
})

# REVIEW (schema exposure): FastAPI auto-docs. Keeping these public leaves
# the API inspectable, but /openapi.json leaks the full route map. Gating
# them behind auth is the stronger posture and is an explicit decision for
# the per-route granularity pass — recorded here so it is NOT a silent
# permanent exception.
_DOCS_PUBLIC = {"/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect"}

# LOCKED public (reference data): NAPPI is the public SA drug-code
# registry — no patient/tenant/workspace scope. The proposed
# prescription_writing gate was overruled at lock: gating it to the
# current sole caller breaks the Type-C digitisation reviewer resolving
# NAPPI codes (a legitimate caller the wedge depends on). Prefix covers
# /api/medications/search and /api/medications/{medication_id}.
_PUBLIC_PREFIXES = ("/docs/", "/api/medications/")


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
    if path in _DOCS_PUBLIC or any(path.startswith(p) for p in _PUBLIC_PREFIXES):
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

        # Capability GRANULARITY layer (Fork-1 LOCKED: central map).
        # required_capability is None for §E / public / sick-note's own
        # Depends / genuinely-floor-only routes -> no hydration, no DB.
        cap = required_capability(request.app, method, path)
        if cap is not None:
            caps = hydrate_capabilities(payload.get("workspace_id"))
            if cap not in caps:
                return _forbid(cap)
        return await call_next(request)


# ---------------------------------------------------------------------------
# phase 3: the capability GRANULARITY layer — central ROUTE_CAPABILITIES map.
#
# Fork-1 LOCKED: a central map, NOT ~68 per-route decorators. Per-route
# decoration is the silent-omission failure mode the floor exists to kill
# ("forget route 47 of 68" == "forget route 47 of 84"); the granularity
# layer is structural for the identical reason the floor is. This map is
# the lock made executable in ONE diff-visible block; the bite-proving
# test is parametrised over it and proves it non-vacuous BOTH ways
# (wrong-cap -> 403 naming the cap; removing an entry flips that route).
#
# Fork-2 LOCKED: capability-only. This decides WHICH authenticated
# principal — it does NOT make routes tenant-correct. Post-application
# the A–D surface is authentication-and-authorization correct but NOT
# yet uniformly tenant-correct (the sick-note cut fixed the worst single
# instance; the rest is its own deliberate tracked crossing). That is the
# recorded intended shape, chosen — see ZERO_CAPABILITY_TABLE.md.
#
# NOT in this map (by design):
#   * sick-note family — already gated by its own per-route Depends
#     (commit 8f2486b); not double-gated here.
#   * the 3 pre-existing CAP'd routes (analytics_cohorts /
#     digitisation_export_fhir / analytics_drug_spend) — unchanged.
#   * §E (dispense*, analytics summary/operational/financial) — stays
#     floor-only, capability-UNDECIDED; the test asserts §E immovability
#     non-vacuously (an §E row gaining a cap must fail the test).
#   * explicitly-public (leads, medications/*) — in PUBLIC_PATHS, above.
# ---------------------------------------------------------------------------

from app.api.auth import supabase as _auth_sb  # noqa: E402
from app.services.entitlements import practice_capabilities  # noqa: E402
from starlette.routing import Match  # noqa: E402

ROUTE_CAPABILITIES: dict = {
    # --- A. clinical / legal write ---
    ("POST", "/api/patients"): "patient_ehr_basic",
    ("PUT", "/api/patients/{patient_id}"): "patient_ehr_basic",
    ("POST", "/api/encounters"): "patient_ehr_basic",
    ("PUT", "/api/encounters/{encounter_id}"): "patient_ehr_basic",
    ("POST", "/api/ai-scribe/transcribe"): "ai_scribe",
    ("POST", "/api/ai-scribe/generate-soap"): "ai_scribe",
    ("POST", "/api/ai-scribe/extract-clinical-actions"): "ai_scribe",
    ("POST", "/api/ai-scribe/save-consultation"): "ai_scribe",
    ("POST", "/api/prescriptions"): "prescription_writing",
    ("POST", "/api/referrals"): "patient_ehr_basic",
    # --- B. PII / clinical read ---
    ("GET", "/api/patients"): "patient_ehr_basic",
    ("GET", "/api/patients/{patient_id}"): "patient_ehr_basic",
    ("GET", "/api/patients/{patient_id}/conditions"): "patient_ehr_basic",
    ("GET", "/api/patients/{patient_id}/medications"): "patient_ehr_basic",
    ("GET", "/api/encounters/patient/{patient_id}"): "patient_ehr_basic",
    ("GET", "/api/encounters/{encounter_id}"): "patient_ehr_basic",
    ("GET", "/api/prescriptions/patient/{patient_id}"): "prescription_writing",
    ("GET", "/api/prescriptions/{prescription_id}"): "prescription_writing",
    ("GET", "/api/referrals/patient/{patient_id}"): "patient_ehr_basic",
    # --- C. clinical-ops / sensitive metadata ---
    ("POST", "/api/queue/check-in"): "queue_display",
    ("POST", "/api/queue/{queue_id}/call-next"): "queue_display",
    ("PUT", "/api/queue/{queue_id}/update-status"): "queue_display",
    ("GET", "/api/queue/current"): "queue_display",
    ("GET", "/api/queue/stats"): "queue_display",
    # --- D. Professional clinical data + billing (gated 2026-05-22, Pass A) ---
    # Previously floor-only: any authenticated user (incl. Essential-tier
    # digitisation users) could reach these. Now capability-fenced. NOTE:
    # gating closes the cross-TIER hole; the per-router tenancy fixes
    # (workspace_id from token vs DEMO_WORKSPACE_ID / patient-derived) are
    # tracked separately (Pass A step 2) and required before Professional ships.
    # (vitals: the standalone /api/vitals router was removed — dead, drifted,
    #  no consumer. Vitals are captured via the encounter, which is scoped.)
    # allergies
    ("POST", "/api/allergies"): "patient_ehr_basic",
    ("GET", "/api/allergies/patient/{patient_id}"): "patient_ehr_basic",
    ("GET", "/api/allergies/{allergy_id}"): "patient_ehr_basic",
    ("PUT", "/api/allergies/{allergy_id}"): "patient_ehr_basic",
    ("DELETE", "/api/allergies/{allergy_id}"): "patient_ehr_basic",
    ("POST", "/api/allergies/check-prescription"): "patient_ehr_basic",
    # diagnoses
    ("POST", "/api/diagnoses"): "patient_ehr_basic",
    ("GET", "/api/diagnoses/patient/{patient_id}"): "patient_ehr_basic",
    ("GET", "/api/diagnoses/{diagnosis_id}"): "patient_ehr_basic",
    ("PATCH", "/api/diagnoses/{diagnosis_id}"): "patient_ehr_basic",
    ("DELETE", "/api/diagnoses/{diagnosis_id}"): "patient_ehr_basic",
    ("GET", "/api/diagnoses/encounter/{encounter_id}"): "patient_ehr_basic",
    # lab orders / results
    ("POST", "/api/lab-orders"): "patient_ehr_basic",
    ("GET", "/api/lab-orders/patient/{patient_id}"): "patient_ehr_basic",
    ("GET", "/api/lab-orders/{order_id}"): "patient_ehr_basic",
    ("PUT", "/api/lab-orders/{order_id}/status"): "patient_ehr_basic",
    ("DELETE", "/api/lab-orders/{order_id}"): "patient_ehr_basic",
    ("POST", "/api/lab-results"): "patient_ehr_basic",
    ("GET", "/api/lab-results/order/{order_id}"): "patient_ehr_basic",
    ("GET", "/api/lab-results/patient/{patient_id}/test/{test_name}"): "patient_ehr_basic",
    ("GET", "/api/lab-results/patient/{patient_id}/abnormal"): "patient_ehr_basic",
    # billing / invoices / payments / claims / reports
    ("POST", "/api/invoices"): "billing_invoicing",
    ("GET", "/api/invoices"): "billing_invoicing",
    ("GET", "/api/invoices/patient/{patient_id}"): "billing_invoicing",
    ("GET", "/api/invoices/{invoice_id}"): "billing_invoicing",
    ("POST", "/api/payments"): "billing_invoicing",
    ("GET", "/api/payments/invoice/{invoice_id}"): "billing_invoicing",
    ("POST", "/api/claims"): "billing_invoicing",
    ("GET", "/api/claims"): "billing_invoicing",
    ("GET", "/api/claims/{claim_id}"): "billing_invoicing",
    ("PATCH", "/api/claims/{claim_id}/status"): "billing_invoicing",
    ("GET", "/api/reports/revenue"): "billing_invoicing",
    ("GET", "/api/reports/outstanding"): "billing_invoicing",
}

# §E — explicitly NOT gated; floor-only; capability UNDECIDED (product
# decision owed). Listed so the test can assert immovability
# non-vacuously: required_capability() MUST return None for every entry.
SECTION_E_ROUTES: frozenset = frozenset({
    ("POST", "/api/dispense"),
    ("GET", "/api/dispense/encounter/{encounter_id}"),
    ("GET", "/api/analytics/summary"),
    ("GET", "/api/analytics/operational"),
    ("GET", "/api/analytics/financial"),
})


def _resolve_template(app, method: str, path: str):
    """Concrete request path -> the matched route's template, using
    Starlette's own matcher (BaseHTTPMiddleware runs before routing, so
    request.scope['route'] is not yet populated — we match explicitly)."""
    scope = {"type": "http", "method": method, "path": path}
    for route in app.router.routes:
        try:
            match, _ = route.matches(scope)
        except Exception:  # noqa: BLE001
            continue
        if match == Match.FULL:
            return getattr(route, "path", None)
    return None


def required_capability(app, method: str, path: str):
    """The capability this request requires, or None if the route is not
    in ROUTE_CAPABILITIES (floor-only: §E, public, sick-note's own dep,
    or genuinely needs no extra capability). Pure w.r.t. the map — the
    test reads ROUTE_CAPABILITIES at call time so removing an entry flips
    the route's expectation (the map's own non-vacuity)."""
    template = _resolve_template(app, method, path)
    if template is None:
        return None
    return ROUTE_CAPABILITIES.get((method.upper(), template))


def hydrate_capabilities(workspace_id) -> list:
    """Reuse the existing entitlement primitive (do not reinvent). Fails
    CLOSED — any hydration failure yields no capabilities, so a mapped
    route denies rather than leaks. Indirected through this module
    function so the bite-proving test can stub it DB-free."""
    if not workspace_id:
        return []
    try:
        return practice_capabilities(_auth_sb, workspace_id) or []
    except Exception:  # noqa: BLE001
        return []


def _forbid(capability: str) -> JSONResponse:
    # Body shape mirrors require_capability()'s 403 exactly, so behaviour
    # is identical whether a route is gated by this map or by a per-route
    # Depends (the sick-note cut), and the frontend renders one upsell.
    return JSONResponse(
        status_code=403,
        content={
            "error": "capability_required",
            "capability": capability,
            "message": (
                f"This feature requires the '{capability}' capability. "
                f"Contact sales@surgiscan.co.za to add the corresponding "
                f"module to your plan."
            ),
        },
    )
