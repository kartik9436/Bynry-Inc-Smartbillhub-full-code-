# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-SHL-4272 (high) — a Billing Clerk could not use SMARTBillHub at
#           all between 2026-08-21 (19bf8f6e) and 2026-09-06: the app shell's
#           two boot reads were Admin/Executive only, so every screen rendered
#           "We couldn't load your regional settings." with a dead Retry.
# Rules:    BR-SHL-252 (formatting and branding are not settings administration)
#           · A4 settings_lookups (unchanged — the settings SURFACE stays
#           admin/executive) · DEF-196 (the gate this deliberately does not
#           widen) · US-TEN-009 TC-5 (clerk denied at the reference-data surface)
#           · CLAUDE.md hard rule 1 (tenant scoping)
# Tests:    this file
# Impacts:  core/permissions.ShellDisplayRead · apps/tenancy/api.shell_display ·
#           apps/tenancy/selectors.shell_display · 07-frontend ShellWithSession
# ───────────────────────────────────────────────────────
"""DEF-SHL-4272 — the shell boots for a Billing Clerk, and Settings still does not.

⚠ **THIS FILE HAS TWO HALVES AND THE SECOND ONE IS THE IMPORTANT ONE.**

The first half proves the fix: a Billing Clerk can now obtain the tenant's date
format and branding, so the product draws.

The second half proves the fix did NOT become the fix that was already made and
reverted once. `DEF-196`'s first cut opened the settings read to every role, and
that widening **passed every test written for the defect** — it was caught only
by `US-TEN-009 TC-5`, a story case written weeks earlier. So the cases below
enumerate every view in `apps/tenancy/api.py` still gated by
`SettingsReadAnyWriteSystemAdmin` — by reading the URL table, not from a list
typed here — and assert a Billing Clerk is refused at each. Ten such views were
found when this file was written; a view added later is covered without anyone
remembering to add it, and a view WIDENED later goes red here.
"""

from __future__ import annotations

import pytest
from django.urls import URLPattern

from apps.tenancy import api, selectors
from core import permissions

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (
    FakeUser,
    admin_actor,
    api_call,
    provisioned_tenant,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

#: The four fields on `GET /settings/regional` that are a utility's FINANCE
#: POLICY and its accounting calendar. Nobody receives these in order to render
#: a date, which is half of why the fix is a separation and not a widening.
#:
#: ⚠ **AMENDED 2026-09-06 BY `DEF-SHL-4283`, AND THE LIST BELOW DID NOT MOVE.**
#: These are asserted absent from the `regional` BLOCK, and they still are. The
#: computed period CARD is now served as a SIBLING block, `period`, because
#: withholding it locked a Billing Clerk out of `Reports → By premises` and gave
#: `Payments → Refunds` a false header — two screens A4 gives that role. The
#: card carries no `close_by`, so no field named here reaches a clerk by any
#: route. `tests/test_def_shl_4283_period_outside_the_shell.py` asserts that
#: half; this file is unchanged and still asserts this one.
FINANCE_POLICY_FIELDS = (
    "accounting_method",
    "close_cadence",
    "close_day",
    "lock_closed_periods",
    "fy_start_month",
    "fy_start_day",
    "current_period",
)

#: The settings values a clerk must not receive from the shell's boot read.
#: `ein` is encrypted at rest (BR-CUS-092's family) and the rest are the
#: company's legal identity and contact record, not its branding.
COMPANY_NON_BRANDING_FIELDS = (
    "ein",
    "state_utility_id",
    "mailing_address",
    "support_phone",
    "support_email",
    "remit_to_address",
    "remit_payable_to",
)


def _settings_gated_views():
    """Every view in tenancy's URL table gated by the Settings read class.

    Read off `urlpatterns` rather than typed out, so a view added under that
    class tomorrow is asserted without anyone remembering to come back here.
    `@api_view` hangs the generated CBV on the handler as `.cls`, and DRF keeps
    `permission_classes` there.
    """
    found = []
    for entry in api.urlpatterns:
        if not isinstance(entry, URLPattern):
            continue
        view_cls = getattr(entry.callback, "cls", None)
        if view_cls is None:
            continue
        if permissions.SettingsReadAnyWriteSystemAdmin in getattr(
            view_cls, "permission_classes", ()
        ):
            found.append((str(entry.pattern), entry.callback))
    return found


# ══════════════════════════════════════════════════════════════════════════
# HALF ONE — the product draws for a Billing Clerk
# ══════════════════════════════════════════════════════════════════════════
def test_def_shl_4272__the_shell_boots_for_a_billing_clerk(growth_plan, identity_seam):
    """THE DEFECT, INVERTED. A clerk reads the shell's boot endpoint and gets
    the two things the shell cannot draw a screen without: a date format and a
    tenant name.

    ⚠ **RED BEFORE THE FIX, AND THE RED IS THE DEFECT ITSELF.** At the tip this
    call reached `GET /settings/regional` under
    `SettingsReadAnyWriteSystemAdmin`, which answered `403 AUTH-002` to a
    Billing Clerk, and `ShellWithSession` rendered
    `settings.regional.failedTitle` over every route in the product.
    """
    tenant, _ = provisioned_tenant()
    response = api_call(
        api.shell_display,
        "get",
        user=FakeUser(),
        role=permissions.BILLING_CLERK,
        tenant=tenant,
    )
    assert response.status_code == 200, (
        "a Billing Clerk cannot boot the app shell — this is DEF-SHL-4272 and "
        f"the product is unusable for them. Got {response.status_code} "
        f"{getattr(response, 'data', None)}"
    )
    # The two facts the shell blocks on: `tenantRegionalOf` needs BOTH a
    # timezone and a drawable date format or it returns null and the shell
    # refuses to render any screen at all (DEF-SHL-3964's decision D3).
    assert response.data["regional"]["timezone"]
    assert response.data["regional"]["date_format"]
    # …and the sidebar's name, which is what `tenantName` falls back through.
    assert "dba_name" in response.data["company"]
    assert "legal_name" in response.data["company"]


def test_def_shl_4272__all_three_roles_boot_and_the_signed_out_do_not(growth_plan, identity_seam):
    """Drawing a screen is not a permission — every signed-in member of the
    tenant may do it. Being signed OUT still is: 401, unchanged."""
    tenant, _ = provisioned_tenant()
    for role in (permissions.SYSTEM_ADMIN, permissions.BILLING_CLERK, permissions.EXECUTIVE):
        response = api_call(api.shell_display, "get", user=FakeUser(), role=role, tenant=tenant)
        assert response.status_code == 200, f"{role} cannot boot the shell"

    anonymous = api_call(api.shell_display, "get", tenant=tenant)
    assert anonymous.status_code in (401, 403)


def test_def_shl_4272__the_boot_read_carries_no_finance_policy(growth_plan, identity_seam):
    """THE SECOND REASON THE FIX IS A SEPARATION AND NOT A WIDENING.

    `GET /settings/regional` also serves the accounting method, the close
    cadence, the close day and the closed-period lock. A clerk should not
    receive a utility's finance policy in order to print `03/04/2026`, and this
    case is what stops a later lane "simplifying" the selector into a passthrough
    of `regional_settings()`.
    """
    tenant, _ = provisioned_tenant()
    response = api_call(
        api.shell_display,
        "get",
        user=FakeUser(),
        role=permissions.BILLING_CLERK,
        tenant=tenant,
    )
    regional = response.data["regional"]
    company = response.data["company"]
    for field in FINANCE_POLICY_FIELDS:
        assert field not in regional, (
            f"`{field}` is finance policy or the accounting calendar and must "
            "not ride along on the shell's boot read (BR-SHL-252)"
        )
    for field in COMPANY_NON_BRANDING_FIELDS:
        assert field not in company, (
            f"`{field}` is the company's identity or contact record, not the "
            "branding the shell paints (BR-SHL-252)"
        )
    # …and it does carry the whole of what the shell draws with.
    assert set(regional) == set(selectors.SHELL_DISPLAY_REGIONAL_FIELDS)
    assert set(company) == set(selectors.SHELL_DISPLAY_COMPANY_FIELDS)
    # `DEF-SHL-10116` — the utility's own state reaches a Billing Clerk, so New
    # Connection step 2 no longer reads the admin-only regional page for it.
    assert "state" in regional


def test_def_shl_4272__the_boot_read_agrees_with_the_settings_screen(growth_plan, identity_seam):
    """One source of truth. Every value the boot read serves is the SAME value
    the Settings screen edits — composed from the two existing selectors, so a
    clerk and an admin can never be shown two different date formats."""
    tenant, _ = provisioned_tenant()
    response = api_call(
        api.shell_display,
        "get",
        user=FakeUser(),
        role=permissions.BILLING_CLERK,
        tenant=tenant,
    )
    with tenant_ctx(tenant):
        regional = selectors.regional_settings()
        company = selectors.company_profile()
    for field, value in response.data["regional"].items():
        assert value == regional[field], f"`{field}` drifted from Settings → Regional"
    for field, value in response.data["company"].items():
        assert value == company[field], f"`{field}` drifted from Settings → Company"


def test_def_shl_4272__the_boot_read_is_per_tenant(growth_plan, identity_seam):
    """Hard rule 1. `shell_display()` takes no tenant argument at all, so there
    is no id a caller could supply to draw another utility's branding."""
    from tests.test_us_ten_helpers import lonestarridge_payload

    brazos, _ = provisioned_tenant()
    lonestar, _ = provisioned_tenant(lonestarridge_payload())
    from apps.tenancy import services

    with tenant_ctx(brazos):
        services.save_company_profile(admin_actor(), {"dba_name": "Brazos Bend Utilities"})

    seen = api_call(
        api.shell_display,
        "get",
        user=FakeUser(),
        role=permissions.BILLING_CLERK,
        tenant=lonestar,
    )
    assert seen.data["company"]["dba_name"] != "Brazos Bend Utilities"


# ══════════════════════════════════════════════════════════════════════════
# HALF TWO — the Settings surface did NOT move, and cannot be moved quietly
# ══════════════════════════════════════════════════════════════════════════
def test_def_shl_4272__a_clerk_is_still_denied_at_the_two_settings_reads(
    growth_plan, identity_seam
):
    """The named pair, spelled out because they are the two the shell used to
    boot on and are therefore the two a later lane would reach for first."""
    tenant, _ = provisioned_tenant()
    for view, name in ((api.regional_settings, "regional"), (api.company_settings, "company")):
        denied = api_call(
            view, "get", user=FakeUser(), role=permissions.BILLING_CLERK, tenant=tenant
        )
        assert denied.status_code == 403 and denied.data["code"] == "AUTH-002", (
            f"GET /settings/{name} answered {denied.status_code} to a Billing "
            "Clerk. A4 gives them no `settings_lookups` cell and US-TEN-009 "
            "TC-5 has asserted this since the surface was built — DEF-SHL-4272 "
            "was fixed by adding a door, never by widening this one"
        )


def test_def_shl_4272__a_clerk_is_denied_at_every_settings_view(growth_plan, identity_seam):
    """THE ANTI-WIDENING GUARD, ENUMERATED FROM THE URL TABLE.

    Ten views carried `SettingsReadAnyWriteSystemAdmin` when this was written
    (company · regional · subscription · number-series · custom-fields ×2 ·
    lookups ×3 · holidays). The count is deliberately not asserted — a new
    settings view should be covered here silently, and only a WIDENED one
    should go red.
    """
    tenant, _ = provisioned_tenant()
    gated = _settings_gated_views()
    assert gated, "no settings view is gated any more — the read class was removed?"
    for pattern, _view in gated:
        assert "shell/display" not in pattern, (
            "the shell's boot read must never be gated by the Settings class — "
            "that is the defect"
        )
    for view_cls in {view.cls for _pattern, view in gated}:
        for permission in view_cls.permission_classes:
            if permission is permissions.SettingsReadAnyWriteSystemAdmin:
                assert permissions.BILLING_CLERK not in permission.allowed_roles


def test_def_shl_4272__the_shell_gate_is_not_the_settings_gate():
    """Two classes, two different questions, and the sets differ ON PURPOSE.

    `SettingsReadAnyWriteSystemAdmin.allowed_roles` is derived from A4's signed
    `settings_lookups` row and `test_def_196__the_read_roles_match_the_a4_matrix`
    holds it there. `ShellDisplayRead.allowed_roles` is every role, because
    drawing a screen is not a cell in that matrix — it is what the product does
    before any screen exists to have a permission about.
    """
    shell = permissions.ShellDisplayRead
    settings_gate = permissions.SettingsReadAnyWriteSystemAdmin
    assert shell.allowed_roles == permissions.ROLES
    assert shell.allowed_roles != settings_gate.allowed_roles
    assert permissions.BILLING_CLERK not in settings_gate.allowed_roles


def test_def_shl_4272__the_boot_read_has_no_write_door(growth_plan, identity_seam):
    """Read-only for EVERY role, the System Admin included.

    Not a tidiness rule: a `PUT` here would be a second way into the tenant's
    regional settings that skips `PUT /settings/regional`'s validation, its
    currency lock (BR-TEN-042) and its audit row (hard rule 7). The permission
    class refuses the verb, so adding a handler to the view would not open one.
    """
    for role in permissions.ROLES:
        for verb in ("PUT", "POST", "PATCH", "DELETE"):
            request = _FakeRequest(role=role, method=verb)
            assert permissions.ShellDisplayRead().has_permission(request, None) is False, (
                f"{role} may {verb} the shell's boot read — there must be no "
                "write door here at all"
            )
    tenant, _ = provisioned_tenant()
    refused = api_call(
        api.shell_display,
        "put",
        user=FakeUser(),
        role=permissions.SYSTEM_ADMIN,
        tenant=tenant,
        data={"date_format": "DD/MM/YYYY"},
    )
    assert refused.status_code in (403, 405)


def test_def_shl_4272__the_route_is_registered_at_the_address_the_shell_calls():
    """The address, asserted by STRING, because a screen that is registered
    somewhere other than where its caller looks is hard-won law 7's "looking at
    the wrong thing" — and the front end hardcodes this path."""
    registered = {
        str(entry.pattern): entry.callback
        for entry in api.urlpatterns
        if isinstance(entry, URLPattern)
    }
    assert (
        "shell/display" in registered
    ), "the front end calls `/shell/display`; nothing is mounted there"
    assert registered["shell/display"].cls.permission_classes == [permissions.ShellDisplayRead]


class _FakeRequest:
    """Enough of a request for a permission class: an authenticated user, a
    server-attached role and a verb."""

    def __init__(self, role: str, method: str = "GET") -> None:
        self.user = FakeUser()
        self.tenant_role = role
        self.method = method


# ── Lifecycle ─────────────────────────────────────────────
# defect: DEF-SHL-4272 (CR-069 wave M lane found it; this lane fixed it)
# generated: 2026-09-06 by the DEF-SHL-4272 lane
# gates: pytest 06-backend/tests/test_def_shl_4272_shell_boot_read.py
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
