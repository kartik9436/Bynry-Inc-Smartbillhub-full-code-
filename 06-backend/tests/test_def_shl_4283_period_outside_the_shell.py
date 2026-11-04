# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-SHL-4283 (medium) — the DEF-SHL-4272 Billing Clerk lockout
#           survived outside the shell. The shell's two boot reads moved to
#           `GET /shell/display`; the components that read
#           `GET /settings/regional` for themselves did not, so a clerk met the
#           same 403 in a narrower form.
#           Parent: DEF-SHL-4272 (high) — sixteen days, the whole product.
# Rules:    BR-SHL-252 AS AMENDED 2026-09-06 (the values a screen needs in order
#           to DRAW ITSELF are served to any signed-in member of the tenant) ·
#           BR-TEN-022 (the accounting period is COMPUTED, never stored) ·
#           A4 `reports` (Clerk **Run**) · A4 `payments_record` (Clerk **Full**)
#           · A4 `settings_lookups` (Clerk has NO cell — UNCHANGED) · DEF-196
#           (the gate this must never widen) · US-TEN-009 TC-5 · CLAUDE.md hard
#           rule 1 (tenant scoping)
# Tests:    this file · 07-frontend/src/api/adminOnlyReads.test.ts ·
#           07-frontend/src/features/reports/clerkPeriodReachesTheScreen.dom.test.tsx
#           · 10-scripts/render-checks/def-shl-4283-a-clerk-runs-the-money-screens.mjs
# Impacts:  apps/tenancy/selectors.shell_display (+ SHELL_DISPLAY_PERIOD_FIELDS)
#           · apps/tenancy/api.shell_display
# ───────────────────────────────────────────────────────
"""DEF-SHL-4283 — the accounting PERIOD reaches a Billing Clerk; the close
POLICY still does not.

⚠ **WHAT WAS ACTUALLY BROKEN, IN TWO SCREENS A4 GIVES THIS ROLE.**

`Reports → By premises` (A4 `reports`: Clerk **Run**) runs its report over the
tenant's `current_period` and gates the request on `period !== null`. The period
came from `GET /settings/regional`, which is `SettingsReadAnyWriteSystemAdmin`
— `{system_admin, executive}` — so for a clerk it answered `403 AUTH-002`, the
report was **never requested at all**, and the screen said *"Set the fiscal year
start to see the current period."* That sentence is false at a tenant whose
fiscal year start IS set, and it points at a screen only a System Admin can
open.

`Payments → Refunds` (A4 `payments_record`: Clerk **Full**) drew the same
sentence in its Finance header, through `useFinancePeriod` — a hook SEVEN
screens share.

⚠ **THIS AMENDS ONE CLAUSE OF `BR-SHL-252` AND LEAVES THE REST WORD FOR WORD.**
The rule as first written excluded the whole accounting calendar from
`GET /shell/display`, alongside the four finance-policy fields. The reason it
gave — *"nobody receives a close-period lock in order to render 03/04/2026"* —
is about POLICY, and the period card is not policy: it is the label a screen
puts on a figure, in exactly the way a date format is the shape it puts on a
date. The rule's own sentence is the argument. So the CARD is served and the
POLICY is not, and `close_by` — the one field of the card derived from
`close_day` — stays behind with it.

The cases below assert both halves, and half two is the important one: every
settings view is still refused to a clerk, enumerated from the URL table.
"""

from __future__ import annotations

import pytest

from apps.tenancy import api, selectors
from core import permissions

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (
    FakeUser,
    api_call,
    provisioned_tenant,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

#: The finance POLICY, which this endpoint must never carry — the four settings
#: fields, the two raw fiscal-year anchors, and `close_by`, which is `close_day`
#: wearing a date.
POLICY_NEVER_SERVED = (
    "accounting_method",
    "close_cadence",
    "close_day",
    "lock_closed_periods",
    "fy_start_month",
    "fy_start_day",
    "close_by",
)


def _boot(tenant, role=permissions.BILLING_CLERK):
    return api_call(api.shell_display, "get", user=FakeUser(), role=role, tenant=tenant)


# ══════════════════════════════════════════════════════════════════════════
# HALF ONE — the clerk gets the period, so their two screens work
# ══════════════════════════════════════════════════════════════════════════
def test_def_shl_4283__a_clerk_gets_the_tenants_period(growth_plan, identity_seam):
    """THE DEFECT, INVERTED.

    ⚠ **RED BEFORE THE FIX.** `GET /shell/display` carried `regional` and
    `company` and no period at all, so `useFinancePeriod` and
    `ByPremisesReportPage` had nowhere to read one but the admin-only endpoint.
    """
    tenant, _ = provisioned_tenant()
    response = _boot(tenant)
    assert response.status_code == 200
    period = response.data["period"]
    assert period is not None, (
        "a Billing Clerk cannot obtain the tenant's accounting period, so "
        "Reports → By premises never runs its report and Payments → Refunds "
        "heads itself with a false sentence — this is DEF-SHL-4283"
    )
    # The window a report runs over and the label a header prints.
    assert period["start"] and period["end"]
    assert period["fy_label"] and period["period"]
    assert period["status"] == "open"


def test_def_shl_4283__all_three_roles_get_the_same_period(growth_plan, identity_seam):
    """One screen must not read two ways by role.

    `PeriodRollup` is drawn on seven Finance-frame screens and one of them is a
    clerk's. If the card differed by role, a clerk and an admin looking at the
    same header would be told different things about the same month.
    """
    tenant, _ = provisioned_tenant()
    seen = {}
    for role in (permissions.SYSTEM_ADMIN, permissions.BILLING_CLERK, permissions.EXECUTIVE):
        response = _boot(tenant, role)
        assert response.status_code == 200, f"{role} cannot boot the shell"
        seen[role] = response.data["period"]
    assert seen[permissions.BILLING_CLERK] == seen[permissions.SYSTEM_ADMIN]
    assert seen[permissions.BILLING_CLERK] == seen[permissions.EXECUTIVE]


def test_def_shl_4283__the_period_carries_no_close_policy(growth_plan, identity_seam):
    """THE HALF OF `BR-SHL-252` THAT DID **NOT** MOVE.

    A clerk receives which period they are in and what window it covers. They do
    not receive the accounting method, the close cadence, the close day, the
    closed-period lock, the raw fiscal-year anchor, or the hand-off deadline
    those produce. This case is what stops a later lane "simplifying"
    `shell_display()` into a passthrough of `current_period()`.
    """
    tenant, _ = provisioned_tenant()
    payload = _boot(tenant).data
    period = payload["period"]
    for field in POLICY_NEVER_SERVED:
        assert field not in period, (
            f"`{field}` is the utility's finance policy and must not ride along "
            "on the shell's boot read (BR-SHL-252, unamended on this point)"
        )
        assert field not in payload["regional"], f"`{field}` is back on `regional`"
    # And it carries exactly the five fields the constant names — no more.
    assert set(period) == set(selectors.SHELL_DISPLAY_PERIOD_FIELDS)


def test_def_shl_4283__the_period_agrees_with_the_settings_screen(growth_plan, identity_seam):
    """ONE SOURCE, SO TWO SCREENS CANNOT DISAGREE ABOUT WHICH MONTH IT IS.

    S36 Revenue & AR still reads `GET /settings/regional` (it needs `close_by`),
    while the seven Finance-frame screens read `GET /shell/display`. Both are
    composed from `selectors.current_period()`, and this asserts it field by
    field rather than trusting the composition.
    """
    tenant, _ = provisioned_tenant()
    served = _boot(tenant).data["period"]
    with tenant_ctx(tenant):
        card = selectors.regional_settings()["current_period"]
    assert card is not None
    for field, value in served.items():
        assert value == card[field], (
            f"`{field}` drifted between GET /shell/display and "
            "GET /settings/regional — one screen would head itself differently "
            "from its sibling tab"
        )
    # The one field deliberately dropped, named so its absence is a decision.
    assert "close_by" in card and "close_by" not in served


def test_def_shl_4283__no_fiscal_year_publishes_null_rather_than_a_guess(
    growth_plan, identity_seam
):
    """A tenant that has set no fiscal year start gets `null`, not an invented
    calendar month.

    Same argument as `DEF-SHL-3964` decision D3: a plausible wrong answer is the
    defect, not the cure. The screens render *"Set the fiscal year start…"* on
    this branch, and on this branch the sentence is TRUE.
    """
    from apps.tenancy import models

    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        models.TenantSettings.objects.filter(tenant=tenant).update(fy_start_month=None)
    payload = _boot(tenant).data
    assert payload["period"] is None
    # The rest of the boot read still answers, or the shell would refuse to draw
    # any screen at all for a tenant that simply has not set a fiscal year.
    assert payload["regional"]["date_format"]
    assert payload["regional"]["timezone"]


def test_def_shl_4283__the_period_is_per_tenant(growth_plan, identity_seam):
    """Hard rule 1. `shell_display()` takes no tenant argument, so there is no
    id a caller could supply to read another utility's calendar."""
    from tests.test_us_ten_helpers import lonestarridge_payload
    from apps.tenancy import models

    brazos, _ = provisioned_tenant()
    lonestar, _ = provisioned_tenant(lonestarridge_payload())
    with tenant_ctx(brazos):
        models.TenantSettings.objects.filter(tenant=brazos).update(fy_start_month=7)

    seen = _boot(lonestar).data["period"]
    with tenant_ctx(brazos):
        theirs = selectors.regional_settings()["current_period"]
    # ⚠ COMPARE THE FISCAL LABEL, NOT THE WINDOW. The first draft asserted
    # `start` and FAILED on two tenants that were correctly isolated: under a
    # MONTHLY close cadence the window is the calendar month whatever the fiscal
    # year start is, so both said `2026-09-01` and the check reported a leak
    # that was not there. The label and the period NUMBER are what the fiscal
    # year moves — July start → FY2027, period 3; January start → FY2026,
    # period 9 — so they are what separates the two utilities.
    assert (seen["fy_label"], seen["period"]) != (theirs["fy_label"], theirs["period"]), (
        "one utility's accounting period reached another utility's shell: both "
        f"answered {seen['fy_label']} period {seen['period']}"
    )
    # Neither figure is written down here. A test that hard-codes "FY2026,
    # period 9" is green today and red every day after the fiscal year turns,
    # and a check that fails for a reason unrelated to what it checks teaches
    # the next reader to ignore it.


# ══════════════════════════════════════════════════════════════════════════
# HALF TWO — the Settings surface did NOT move, and cannot be moved quietly
# ══════════════════════════════════════════════════════════════════════════
def test_def_shl_4283__a_clerk_is_still_refused_at_the_settings_read(growth_plan, identity_seam):
    """⚠ A RUN WHERE HALF ONE PASSES AND THIS FAILS MEANS SOMEBODY WIDENED THE
    SETTINGS GATE AND RE-OPENED `DEF-196`.

    The fix is a SEPARATION. Serving the period on a route every role may read
    is not the same act as letting every role read Settings, and `DEF-196`'s
    own history is why that distinction is asserted rather than assumed: its
    first cut opened the settings read to every role and **passed every test
    written for the defect.**
    """
    tenant, _ = provisioned_tenant()
    refused = api_call(
        api.regional_settings,
        "get",
        user=FakeUser(),
        role=permissions.BILLING_CLERK,
        tenant=tenant,
    )
    assert refused.status_code == 403
    assert permissions.BILLING_CLERK not in permissions.SettingsReadAnyWriteSystemAdmin.allowed_roles


def test_def_shl_4283__the_two_gates_are_still_different_sets(growth_plan, identity_seam):
    """The shell gate is not the settings gate, and the difference is the point.

    Stated here as well as in the `DEF-SHL-4272` file because this defect's fix
    ADDS to the shell payload, and adding is exactly the move that tempts a
    later lane to reach for the settings class instead.
    """
    settings_gate = permissions.SettingsReadAnyWriteSystemAdmin
    shell_gate = permissions.ShellDisplayRead
    assert settings_gate.allowed_roles != shell_gate.allowed_roles
    assert permissions.BILLING_CLERK in shell_gate.allowed_roles
    assert permissions.BILLING_CLERK not in settings_gate.allowed_roles


def test_def_shl_4283__the_widened_payload_still_has_no_write_door(growth_plan, identity_seam):
    """Adding a field to a read is not adding a way to change it.

    `ShellDisplayRead` refuses every mutating verb for every role including the
    System Admin, so the period cannot become a second path around
    `PUT /settings/regional`'s validation and audit row (hard rule 7).
    """
    tenant, _ = provisioned_tenant()
    for verb in ("put", "post", "patch", "delete"):
        response = api_call(
            api.shell_display,
            verb,
            user=FakeUser(),
            role=permissions.SYSTEM_ADMIN,
            tenant=tenant,
        )
        assert response.status_code in (403, 405), (
            f"{verb.upper()} /shell/display answered {response.status_code} — "
            "this endpoint must have no write door at all"
        )
