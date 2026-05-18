"""
Candidate-A bite-test — ActorContext.from_user reads the LIVE authz key.

The defect (diagnosed read-only at file:line, layer audit (b)):
ActorContext.from_user populated `permissions` from
current_user.get("permissions", ...) — but the auth layer produces
authorization data under "capabilities" EVERYWHERE
(get_current_user / require_capability / entitlements) and "permissions"
NOWHERE. So `.get("permissions", [])` was universally dead and every
audited action's HasPermission(...) precondition was unsatisfiable in
production for every actor — even one who holds the capability the API
gate already enforced. Premise verified before the fix: migrations/023
+ the products seed define ALL FOUR HasPermission strings used in the
codebase (digitisation_validation, digitisation_upload, patient_admin,
prescription_management) as real, granted capability ids — so reading
"capabilities" is the correct, complete fix, not a deferral.

Why this test exercises the REAL path, end to end:
  * It goes through ActorContext.from_user (the fixed code) — NEVER
    constructs ActorContext(permissions=[...]) directly, which would
    bypass the exact line under test and make the test a tautology.
  * It asserts through the REAL precondition HasPermission(cap).check(),
    which only reads ctx.actor.has_permission — DB-free, no Supabase,
    so ExecutorContext(supabase=None, ...) is maximally faithful.

Non-vacuous BOTH ways (the flip is genuine, not an artifact):
  * capability PRESENT under "capabilities"  -> satisfiable (True).
    Against the *unfixed* code this assertion FAILS (old code read the
    dead "permissions" key, so a "capabilities"-only user had no
    perms) — i.e. test 1 itself bites the bug.
  * capability ABSENT                          -> NOT satisfiable (False).
  * capability present ONLY under the OLD dead "permissions" key, no
    "capabilities" -> NOT satisfiable (False). This proves from_user no
    longer honours the dead key, and that test 1 cannot be passing
    vacuously via the legacy key (and that an over-broad "read both
    keys" pseudo-fix would fail here).
  * the truth table is asserted co-located for one representative cap so
    the flip (True / False / False) is self-evidently non-vacuous.

Parametrized over the four real capability strings so the fix is proven
for every HasPermission gate that actually exists in the codebase, not
just one.
"""
import pytest

try:
    from app.actions.base import ActorContext, ExecutorContext
    from app.actions.primitives import HasPermission
except Exception as e:  # pragma: no cover - env-dependent
    pytest.skip(f"cannot import code under test ({e})", allow_module_level=True)

# Every distinct string passed to HasPermission(...) anywhere in the
# audited-action codebase. Each is a real, granted capability id
# (migrations/023_pr3_capabilities_seed.sql + the products seed) — so
# "satisfiable when present" is the correct production expectation.
_REAL_CAPS = [
    "digitisation_validation",
    "digitisation_upload",
    "patient_admin",
    "prescription_management",
]


def _satisfied_via_from_user(current_user: dict, cap: str) -> bool:
    """Run HasPermission(cap) against an actor built by the FIXED path.

    Routes through ActorContext.from_user (the line under test) and the
    real HasPermission.check — never touches ActorContext.__init__
    directly, so a regression in from_user is observable here.
    """
    actor = ActorContext.from_user(current_user)
    ctx = ExecutorContext(
        supabase=None, actor=actor, practice_id="", workspace_id="",
    )
    return HasPermission(cap).check(ctx).passed


@pytest.mark.parametrize("cap", _REAL_CAPS)
def test_capability_present_under_capabilities_is_satisfiable(cap):
    """The fix: an actor whose live-key 'capabilities' contains the cap
    passes HasPermission(cap). FAILS against the unfixed (dead-key) code."""
    user = {"id": "u-1", "email": "u@x.test", "capabilities": [cap]}
    assert _satisfied_via_from_user(user, cap) is True, (
        f"capability {cap!r} present under the live 'capabilities' key "
        f"but HasPermission still unsatisfiable through from_user — the "
        f"audited-action authz layer is still dead"
    )


@pytest.mark.parametrize("cap", _REAL_CAPS)
def test_capability_absent_is_not_satisfiable(cap):
    """Safety direction: the fix did NOT make HasPermission vacuously
    pass — an actor with no capabilities is correctly rejected."""
    user = {"id": "u-1", "email": "u@x.test", "capabilities": []}
    assert _satisfied_via_from_user(user, cap) is False, (
        f"actor holds NO capabilities yet HasPermission({cap}) passed — "
        f"the fix over-broadened authz instead of correcting the key"
    )


@pytest.mark.parametrize("cap", _REAL_CAPS)
def test_legacy_permissions_key_alone_is_not_satisfiable(cap):
    """Bug-regression lock: the cap supplied ONLY under the old dead
    'permissions' key (no 'capabilities') must NOT satisfy. Proves
    from_user now keys off 'capabilities', that test 1 is not passing
    via the legacy key, and that a 'read both keys' over-fix would fail."""
    user = {"id": "u-1", "email": "u@x.test", "permissions": [cap]}
    assert _satisfied_via_from_user(user, cap) is False, (
        f"{cap!r} under the legacy dead 'permissions' key still "
        f"satisfied HasPermission — from_user is still reading the "
        f"wrong key (or reading both); candidate A not truly applied"
    )


def test_truth_table_flip_is_non_vacuous():
    """The flip co-located for one representative cap: True / False /
    False. If any leg did not flip, tests 1-3 could pass against broken
    code — this proves the satisfiability genuinely keys off the live
    'capabilities' key and nothing else."""
    cap = "digitisation_validation"
    present = _satisfied_via_from_user(
        {"id": "u", "email": "e", "capabilities": [cap]}, cap)
    absent = _satisfied_via_from_user(
        {"id": "u", "email": "e", "capabilities": []}, cap)
    legacy_only = _satisfied_via_from_user(
        {"id": "u", "email": "e", "permissions": [cap]}, cap)
    assert (present, absent, legacy_only) == (True, False, False), (
        f"non-vacuity FAILED: (present, absent, legacy_only)="
        f"{(present, absent, legacy_only)}; expected (True, False, False)"
    )
