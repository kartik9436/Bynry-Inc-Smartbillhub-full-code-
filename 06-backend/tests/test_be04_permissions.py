# ── Trace ──────────────────────────────────────────────
# Component: BE-04 tests (core/permissions.py) — 3-role enforcement, deny-by-default,
#            service-layer require_role. No DB, no live endpoints.
# ───────────────────────────────────────────────────────
"""BE-04 unit tests: the A4 matrix as executable checks. UI gating is
convenience; these classes/decorators are the enforcement (BR-SHL-025)."""

import pytest

from core import errors, permissions


class FakeUser:
    def __init__(self, authenticated=True):
        self.is_authenticated = authenticated


class FakeRequest:
    def __init__(self, role=None, authenticated=True, method="GET"):
        self.user = FakeUser(authenticated)
        # DEF-196: one gate now answers differently by VERB, so the fake has to
        # carry one. Defaults to GET, which leaves every existing case above
        # unchanged — none of the role-only classes reads it.
        self.method = method
        if role is not None:
            self.tenant_role = role


class FakeActor:
    def __init__(self, role):
        self.role = role


def allowed(permission_cls, request):
    return permission_cls().has_permission(request, view=None)


# ── DRF permission classes ──────────────────────────────────────────────────
def test_be04_tc01_unauthenticated_is_denied_everywhere():
    request = FakeRequest(role=permissions.SYSTEM_ADMIN, authenticated=False)
    for cls in (
        permissions.AnyTenantRole,
        permissions.SystemAdminOnly,
        permissions.AdminOrClerk,
        permissions.AdminOrExecutive,
    ):
        assert allowed(cls, request) is False


def test_be04_tc02_missing_role_is_denied_by_default():
    # Until the identity story attaches tenant_role, every gate refuses —
    # same deny-by-default posture as RLS.
    request = FakeRequest(role=None)
    for cls in (permissions.AnyTenantRole, permissions.SystemAdminOnly):
        assert allowed(cls, request) is False


def test_be04_tc03_unknown_role_value_is_denied():
    assert allowed(permissions.AnyTenantRole, FakeRequest(role="owner")) is False
    assert allowed(permissions.AnyTenantRole, FakeRequest(role="")) is False


def test_be04_tc04_system_admin_only_matches_the_a4_matrix():
    assert allowed(permissions.SystemAdminOnly, FakeRequest(role=permissions.SYSTEM_ADMIN))
    assert not allowed(permissions.SystemAdminOnly, FakeRequest(role=permissions.BILLING_CLERK))
    assert not allowed(permissions.SystemAdminOnly, FakeRequest(role=permissions.EXECUTIVE))


def test_def_196__settings_reads_are_open_to_every_role_and_writes_are_not():
    """DEF-196 — the ruling the product contradicted for a day.

    PO 2026-08-16 (CR-005/006/007): a Billing Clerk and an Executive **may LOOK
    at** numbering formats, routes, cycles and templates and **may not change
    them**; A4 gives both roles `Settings & lookup tables: View`. Eight views in
    `apps/tenancy/api.py` served GET and a write from one function under
    `SystemAdminOnly`, so the READ answered 403 and every `readOnly` branch in
    those screens was unreachable code.

    Asserted per VERB and per ROLE rather than per role alone, because "the
    Executive is allowed" and "the Executive is allowed to WRITE" are the two
    halves this defect confused, and a role-only assertion cannot tell them
    apart — which is how the shipped gate looked correct.

    ⚠ **AND THE READ IS NOT OPEN TO ALL THREE ROLES.** The first cut of the fix
    opened it to every role and this case was written to match, so it passed.
    `US-TEN-009 TC-5` caught it — a story case asserting *"clerk denied at the
    reference-data surface"* since that surface was built. A4's
    `settings_lookups` row is `{"system_admin": "Full", "executive": "View"}`
    and **a Billing Clerk has no cell at all**. The old test was right and the
    new fix was wrong.
    """
    cls = permissions.SettingsReadAnyWriteSystemAdmin

    # A4 "Full" and "View" both READ. GET is the defect; HEAD/OPTIONS ride along.
    for role in (permissions.SYSTEM_ADMIN, permissions.EXECUTIVE):
        for verb in ("GET", "HEAD", "OPTIONS"):
            assert allowed(cls, FakeRequest(role=role, method=verb)) is True, (
                f"{role} must be able to READ a Settings tab ({verb}) — this is "
                "the PO's ruling and the whole of DEF-196"
            )

    # A4 gives the Billing Clerk NO cell here, so the read stays shut for them.
    for verb in ("GET", "HEAD", "OPTIONS"):
        assert allowed(cls, FakeRequest(role=permissions.BILLING_CLERK, method=verb)) is False, (
            "a Billing Clerk has no `settings_lookups` cell in A4 — no access, "
            "not read-only access (US-TEN-009 TC-5)"
        )

    # Only the System Admin WRITES. Every mutating verb, named individually.
    for verb in ("PUT", "POST", "PATCH", "DELETE"):
        assert allowed(cls, FakeRequest(role=permissions.SYSTEM_ADMIN, method=verb)) is True
        for role in (permissions.BILLING_CLERK, permissions.EXECUTIVE):
            assert allowed(cls, FakeRequest(role=role, method=verb)) is False, (
                f"{role} must NOT be able to {verb} a Settings tab — opening the "
                "read must not have opened the write"
            )


@pytest.mark.django_db
def test_def_196__the_read_roles_match_the_a4_matrix_itself():
    """The anti-drift guard, and the one that would have caught the bad fix.

    Every other assertion in this file restates A4 in a second place, so a fix
    and its tests can agree with each other and both be wrong — which is exactly
    what happened. This one reads `A4_MATRIX` and derives the answer, so the
    permission class cannot drift from the signed matrix without going RED.
    """
    from apps.identity.models import A4_MATRIX

    cells = next(c for code, _label, c in A4_MATRIX if code == "settings_lookups")
    expected = frozenset(role for role, cell in cells.items() if cell in ("Full", "View"))
    assert permissions.SettingsReadAnyWriteSystemAdmin.allowed_roles == expected, (
        "the Settings read gate and A4's settings_lookups row disagree — one of "
        f"them moved. A4 says {sorted(expected)}"
    )
    # …and only a "Full" cell writes.
    assert [r for r, c in cells.items() if c == "Full"] == [permissions.SYSTEM_ADMIN]


def test_def_196__the_read_gate_still_refuses_the_signed_out_and_the_unknown():
    """Opening a read must not open it to everyone — deny-by-default holds.

    Kept separate because the test above proves the ruling and this one proves
    the thing the fix could most easily have broken: `has_permission` is now
    hand-written rather than inherited, so the base class's checks are no longer
    doing the work for it.
    """
    cls = permissions.SettingsReadAnyWriteSystemAdmin
    assert allowed(cls, FakeRequest(role=permissions.SYSTEM_ADMIN, authenticated=False)) is False
    assert allowed(cls, FakeRequest(role=None)) is False
    assert allowed(cls, FakeRequest(role="owner")) is False   # not one of the three
    assert allowed(cls, FakeRequest(role="")) is False
    # …and none of those may write either.
    assert allowed(cls, FakeRequest(role="owner", method="PUT")) is False


def test_be04_tc05_admin_or_clerk_covers_operational_writes():
    assert allowed(permissions.AdminOrClerk, FakeRequest(role=permissions.SYSTEM_ADMIN))
    assert allowed(permissions.AdminOrClerk, FakeRequest(role=permissions.BILLING_CLERK))
    assert not allowed(permissions.AdminOrClerk, FakeRequest(role=permissions.EXECUTIVE))


def test_be04_tc06_admin_or_executive_covers_finance_and_approvals():
    assert allowed(permissions.AdminOrExecutive, FakeRequest(role=permissions.SYSTEM_ADMIN))
    assert allowed(permissions.AdminOrExecutive, FakeRequest(role=permissions.EXECUTIVE))
    assert not allowed(permissions.AdminOrExecutive, FakeRequest(role=permissions.BILLING_CLERK))


def test_be04_tc07_any_tenant_role_admits_all_three_roles():
    for role in permissions.ROLES:
        assert allowed(permissions.AnyTenantRole, FakeRequest(role=role))


# ── require_role service decorator ──────────────────────────────────────────
def test_be04_tc08_allowed_actor_runs_the_service():
    @permissions.require_role(permissions.SYSTEM_ADMIN)
    def change_settings(payload, actor):
        return "changed"

    assert change_settings({"k": "v"}, actor=FakeActor(permissions.SYSTEM_ADMIN)) == "changed"
    # positional actor works too — binding is by parameter name, not call style
    assert change_settings({"k": "v"}, FakeActor(permissions.SYSTEM_ADMIN)) == "changed"


def test_be04_tc09_wrong_role_raises_auth_002_with_br_ref():
    @permissions.require_role(permissions.SYSTEM_ADMIN, permissions.EXECUTIVE)
    def approve_write_off(item, actor):  # A4: Approve = System Admin, Executive
        return "approved"

    with pytest.raises(errors.AuthError) as exc_info:
        approve_write_off("W-1", actor=FakeActor(permissions.BILLING_CLERK))
    assert exc_info.value.code == errors.AUTH_PERMISSION_DENIED
    assert exc_info.value.br_ref == "BR-IDN-009"  # default; callers may override


def test_be04_tc10_br_ref_override_is_carried():
    @permissions.require_role(permissions.SYSTEM_ADMIN, br_ref="BR-SHL-025")
    def gated(actor):
        return "ok"

    with pytest.raises(errors.AuthError) as exc_info:
        gated(actor=FakeActor(permissions.EXECUTIVE))
    assert exc_info.value.br_ref == "BR-SHL-025"


def test_be04_tc11_missing_or_roleless_actor_is_denied():
    @permissions.require_role(permissions.SYSTEM_ADMIN)
    def gated(actor=None):
        return "ok"

    with pytest.raises(errors.AuthError):
        gated()  # no actor bound → denied, never silently allowed
    with pytest.raises(errors.AuthError):
        gated(actor=object())  # actor with no role attribute → denied


def test_be04_tc12_decorator_misuse_fails_at_import_time():
    with pytest.raises(ValueError):
        permissions.require_role("superuser")  # roles are platform-defined (A4)

    with pytest.raises(TypeError):

        @permissions.require_role(permissions.SYSTEM_ADMIN)
        def no_actor_param(payload):  # services must carry the actor (B12 §6a)
            return payload


# ── Lifecycle ─────────────────────────────────────────────
# packet: BE-04@87ece49 (component packet — B13 §3 row + signed contracts; hash = sha256/7 of B12)
# generated: 2026-08-09 by story-coder v1 (W0 kernel lane, B13 rows BE-01..BE-05)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-08)
# gates: ruff✔ black✔ pytest 12/12✔ (this file) · suite 92/92✔ · run_gates 10-PASS/0-FAIL✔ · trace_lint✔ · mypy NOT run — B8 strict scope is services/engines
# exceptions: none stubbed; E2-candidates reported to the PO batch via the build report (404/40x codes absent from the B12 §3 catalog · BR-AUD-018 attempt-row event code pending SC-3 · G7 guard list lacks core/tenancy.py)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
