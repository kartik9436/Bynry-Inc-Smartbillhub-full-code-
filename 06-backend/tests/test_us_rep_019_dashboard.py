# ── Trace ──────────────────────────────────────────────
# Story:    US-REP-019 (S7 — the landing screen; every tile carries the owner's
#           figure or reports that it cannot answer)   Screens: S7
# Rules:    BR-REP-024 (a dashboard tile never computes a figure) · BR-REP-002
#           (read-models only) · BR-REP-001 (every money figure labels its date
#           basis) · BR-REP-012 (Active connections = Active + Marked
#           disconnect + Vacation hold) · BR-TEN-022 (the period is COMPUTED
#           from fiscal settings) · BR-TEN-043 (a window is an argument, never
#           a clock) · BR-TEN-003 / HR-1 (cross-tenant reads as absent) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 2 (money is a decimal
#           string beside its currency, never a float)
# Golden:   LE-1 — AR **152.32** · billed in period **553.69** · footing
#           598.69 = 598.69. Nothing here recomputes an expectation.
# ───────────────────────────────────────────────────────
"""`GET /dashboard/summary` — and the five figures it REFUSES to invent.

**THE DEFECT THIS FILE EXISTS FOR (DEF-129).** The tenant dashboard is the first
screen after every single sign-in and it did not exist: `App.tsx` redirected
`/{tenant}` to `dashboard`, no route with that path was declared, the request
fell through the router's catch-all, and a browser rendered the literal string
`SMARTBillHub — W0 scaffold`. A11 had contracted `GET /dashboard/summary` since
the first spec pass and nothing served it. **Hard-won law 8 for the second
time** — a screen in the inventory that no story owned.

**WHAT IS EASY TO GET WRONG HERE, AND WHY EVERY NEGATIVE CASE BELOW IS
DELIBERATE.** The tempting way to make a dashboard look finished is to fill it.
Every one of these substitutions was available in the owning module, would have
passed any shape test, and is a lie:

    unbilled reads      count the rows `metering.selectors.read_list` returns
    active connections  render `accounts_rollup()["accounts"]` — which counts
                        the Pending-activation and Closed accounts BR-REP-012
                        EXCLUDES
    failed payments     `len(summary().failed)` — a list sliced [:50], so a
                        tenant with eighty failures reads **50**
    AR aging            four zeroed bands, which read as "nothing is overdue"
    recent activity     an empty feed, which reads as "nothing happened today"

This product has already paid for that shape twice. **DEF-104**: four surfaces
disagreed about one customer's balance — the account screen said **$0.00** while
the ledger held an issued, unpaid **$108.88**. **DEF-075**: a seam that could not
answer returned `False`, the caller read it as *"there is nothing"*, and a tenant
holding issued bill BL-2606-000001 (**108.88 USD**) re-denominated its books at
HTTP 200. So the tests below assert the NULLS, under their contracted names,
with their reasons travelling beside them.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.reports import api as reports_api
from apps.reports import dashboard, dashboard_seams

from tests.ledger_le_fixtures import (
    BILLED_IN_PERIOD,
    JULY_END,
    LE1_AR,
    make_accounts,
    post_le1_month,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import FakeUser, tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db


def wire_money(value: Decimal) -> str:
    """The exact decimal STRING of a NUMERIC(18,6) (CLAUDE.md rule 2).

    Derived from the LE constant rather than transcribed as "152.320000", so the
    expectation stays anchored to the signed fixture and not to a copy of it.
    """
    return str(Decimal(value).quantize(Decimal("0.000001")))


def a_july(tenant, dana):
    """LE-1's July, posted through the real posting service, on a tenant whose
    fiscal calendar is the demo fixture's.

    The calendar is set explicitly because BR-TEN-022 makes the accounting
    period COMPUTED from it and never stored — a tenant with no fiscal settings
    genuinely has no period, and `seed_demo` gives Brazos Bend the US-TEN-006 §4
    signed set (FY starts **1 October**, monthly close), so a July reference date
    lands in the period 2026-07-01 .. 2026-07-31 that LE-1 posts into.
    """
    fiscal_calendar(tenant)
    accounts = make_accounts(dana, tenant, {})
    post_le1_month(tenant, accounts)
    return accounts


def fiscal_calendar(tenant):
    """`seed_demo.REGIONAL_SETTINGS`' own fiscal fields, on this tenant's row."""
    from apps.tenancy import models as tenancy_models

    tenancy_models.TenantSettings.objects.update_or_create(
        tenant_id=tenant.id,
        defaults={
            "fy_start_month": 10,
            "fy_start_day": 1,
            "close_cadence": "monthly",
            "close_day": "3rd business day",
        },
    )


def codes(payload) -> set[str]:
    """The `unavailable` codes — the reason half of every null on this screen."""
    return {entry["code"] for entry in payload["unavailable"]}


def summary_for_july(tenant):
    """S7's read model asked for LE-1's month.

    `as_of` is stated rather than left to the clock, which is BR-TEN-043 and is
    also the only way a test can assert a signed figure: a read model that read
    `date.today()` internally would agree with LE-1 for exactly one month of the
    year and silently pass on an empty August for the other eleven.

    ⚠ **`period="this_period"` IS NEW AND IT IS NOT A TEST FIX (CR-015).** The
    accounting period used to be the ONLY window this read model had, so asking
    for it was the same as asking for nothing. It is now one of four, and the
    ruled DEFAULT is the last completed cycle — so every case below that means
    *"LE-1's month"* has to say so. Deleting the argument would silently move
    these assertions onto a rolling thirty-day window ending 31 Jul, which on
    this fixture starts on the 2nd and would still pass most of them.
    """
    with tenant_ctx(tenant):
        return dashboard.dashboard_summary(as_of=JULY_END, period="this_period")


# ═══════════════════════════════════════════════════════════════════════════
# TC-2 — THE ROUTE EXISTS. This is the half DEF-129 was missing.
# ═══════════════════════════════════════════════════════════════════════════
def test_us_rep_019_tc2__the_dashboard_route_is_actually_mounted(brazos):
    """A11's S7 row is `GET /dashboard/summary`, and nothing served it.

    `resolve()` through the REAL root URLconf, for the same reason
    `test_us_led_008_tc1` does it: an `api.py` that exports `urlpatterns` is not
    an endpoint until `config/urls.py` includes it, and this file's route sits
    inside an include that was already there — so a route added to the wrong
    module's `urlpatterns` would look fine in review and 404 in a browser.
    """
    from django.urls import resolve

    assert (
        resolve(f"/api/{brazos.subdomain}/dashboard/summary").func is reports_api.dashboard_summary
    )


def test_us_rep_019_tc2b__the_route_is_reachable_through_the_whole_stack(brazos):
    """Mounted is not reachable: middleware, authentication and the permission
    class all sit in front. An UNAUTHENTICATED call must be REFUSED (the route
    exists and wants a session), never 404 (there is no route)."""
    from django.test import Client

    response = Client().get(f"/api/{brazos.subdomain}/dashboard/summary")
    assert (
        response.status_code != 404
    ), "404 means the dashboard endpoint does not exist — DEF-129's own state"
    assert response.status_code in (401, 403)


def test_us_rep_019_tc2c__a_signed_in_clerk_gets_a_payload(brazos):
    """A4 row for S7 is "All staff", so a Billing Clerk reads it."""
    response = api_call(
        reports_api.dashboard_summary,
        "get",
        user=FakeUser(),
        role="billing_clerk",
        tenant=brazos,
    )
    assert response.status_code == 200
    assert response.data["basis"] == "posting"
    assert "kpis" in response.data


# ═══════════════════════════════════════════════════════════════════════════
# TC-3 — the two money figures are the LEDGER'S, to the cent
# ═══════════════════════════════════════════════════════════════════════════
def test_us_rep_019_tc3__ar_and_revenue_are_le1s_own_figures(brazos, dana):
    """AR **152.32** and billed **553.69**, both POSTING basis, both labeled.

    These are the SAME numbers S36 shows, because they come from the same call
    to the same read model. That is the entire mechanism by which S7 cannot
    become a fifth opinion on the busiest surface in the app (BR-REP-024).
    """
    with tenant_ctx(brazos):
        a_july(brazos, dana)
    payload = summary_for_july(brazos)

    assert payload["kpis"]["ar_outstanding"] == wire_money(LE1_AR)
    assert payload["kpis"]["period_revenue"] == wire_money(BILLED_IN_PERIOD)
    # BR-REP-001 + CLAUDE.md rule 2: a basis label and a currency, always.
    assert payload["basis"] == "posting"
    assert payload["currency"] == "USD"
    assert payload["period"]["start"] == "2026-07-01"
    assert payload["period"]["end"] == "2026-07-31"


def test_us_rep_019_tc3b__the_service_mix_comes_from_the_same_call(brazos, dana):
    """One `revenue_and_ar` call answers the strip AND the panel, so the two
    cannot straddle a posting and disagree — the shape of DEF-104."""
    with tenant_ctx(brazos):
        a_july(brazos, dana)
    payload = summary_for_july(brazos)

    # ⚠ CR-012 moved this panel to `regions.service_mix`, and the PO's ruling of
    # 2026-08-19 made its row set THE TENANT'S OWN configured services rather
    # than a hard-coded five. Brazos Bend has enabled electric and water, so it
    # draws two rows and no longer meets three it can never fill. What this case
    # still asserts is the original claim, which neither change touched: the
    # panel and the KPI strip come from ONE `revenue_and_ar` call (memoised in
    # `dashboard._once`), so they cannot straddle a posting and disagree —
    # DEF-104's shape.
    rows = payload["regions"]["service_mix"]["data"]["rows"]
    from apps.tenancy.selectors import enabled_service_codes

    with tenant_ctx(brazos):
        configured = list(enabled_service_codes())
    assert [row["service_code"] for row in rows] == configured, (
        "PO 2026-08-19: the panel draws what this tenant sells, all of it, in seed order"
    )
    assert configured, "the fixture tenant must sell something for this case to mean anything"
    assert any(row["amount"] for row in rows), "LE-1's July posted revenue"
    for row in rows:
        assert row["amount"] is None or isinstance(
            row["amount"], str
        ), "money is a decimal STRING, never a float"


# ═══════════════════════════════════════════════════════════════════════════
# TC-4 — THE REFUSALS. Every one of these could have been a plausible zero.
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    "kpi,code",
    [
        ("unbilled_reads", "unbilled_read_count_is_not_published_by_metering"),
        ("active_connections", "active_connection_classes_are_not_published_by_customers"),
        ("failed_payments", "failed_payment_count_is_not_published_by_payments"),
    ],
)
def test_us_rep_019_tc4__an_unpublished_count_is_null_with_a_named_reason(brazos, dana, kpi, code):
    """`null` + a code, never 0.

    A zero here is not a smaller truth. "0 unbilled reads" tells a one-person
    utility their reading round is done; "0 failed payments" tells them no
    customer's bank refused this month. Both are statements this deployment
    cannot make, and both would pass a schema test.
    """
    with tenant_ctx(brazos):
        a_july(brazos, dana)
    payload = summary_for_july(brazos)

    assert payload["kpis"][kpi] is None, f"{kpi} must be null, never a substituted count"
    assert code in codes(payload), "a null without its reason is a screen that looks broken"


def test_us_rep_019_tc4b__the_account_total_is_never_served_as_active_connections(brazos, dana):
    """BR-REP-012's exclusion, mechanised.

    `accounts_rollup()["accounts"]` IS published and IS served — under its own
    name, `accounts_on_file`. It counts Pending-activation and Closed accounts,
    which BR-REP-012 excludes, so under the Active-connections label it would be
    a WRONG figure rather than an approximate one. This asserts the two never
    collapse into one member.
    """
    with tenant_ctx(brazos):
        a_july(brazos, dana)
    payload = summary_for_july(brazos)

    assert payload["kpis"]["active_connections"] is None
    assert (
        payload["accounts_on_file"] is not None
    ), "the account total is a real published fact and is served — just not as the KPI"


def test_us_rep_019_tc5__aging_is_null_and_the_refusal_is_quantified(brazos, dana):
    """The ledger's own null, passed through with its reason.

    And QUANTIFIED: `ar_outstanding` is the total the missing bands would have to
    add up to, which is what makes the absence actionable rather than adjectival
    — the posture S60 already ships.
    """
    with tenant_ctx(brazos):
        a_july(brazos, dana)
    payload = summary_for_july(brazos)

    # ⚠ AMENDED BY CR-012, 2026-08-18 — this case used to assert `aging is None`
    # and it is now BUILT. The reason the old assertion was right and is no
    # longer: the LEDGER cannot age (a journal line carries no due date, which
    # is `aging_buckets_need_invoice_due_dates_and_opening_buckets`, still
    # served and still true), but `payments.outstandings` CAN — it ages each
    # account on its oldest unpaid bill's due date and publishes all five bands
    # with their shares. The panel reads that owner instead (BR-REP-030).
    #
    # What has NOT changed is the assertion underneath: the AR total is the
    # ledger's own figure, unrecomputed, so the strip and the panel still cannot
    # disagree about how much is owed.
    assert "aging_buckets_need_invoice_due_dates_and_opening_buckets" in codes(payload)
    assert payload["kpis"]["ar_outstanding"] == wire_money(LE1_AR)
    aging = payload["regions"]["aging"]
    assert aging["state"] in ("ok", "empty")
    assert [row["bucket"] for row in aging["data"]["rows"]] == [
        "current",
        "1-30",
        "31-60",
        "61-90",
        "90+",
    ]


def test_us_rep_019_tc5b__the_activity_feed_says_there_is_no_read_model(brazos, dana):
    """An EMPTY feed would read as "nothing happened today" on a day a bill run
    issued three invoices. `null` plus a reason is the only honest answer."""
    with tenant_ctx(brazos):
        a_july(brazos, dana)
    payload = summary_for_july(brazos)

    # ⚠ AMENDED BY CR-012, 2026-08-18. This case used to assert `activity is
    # None` on the stated ground that *"no module in this product publishes an
    # event read-model"*. **That was true of the operational modules and was
    # never true of `apps.audit`** (hard-won law 1 — a note claiming an absence
    # is not the absence), so the panel is built and reads the trail
    # (BR-REP-031). The assertion that survives is the one the case was really
    # about: an EMPTY feed must never read as "nothing happened today", so an
    # empty region says `empty` in its own state rather than rendering nothing.
    activity = payload["regions"]["activity"]
    assert activity["state"] in ("ok", "empty")
    assert activity["error"] is None
    if activity["state"] == "ok":
        assert len(activity["data"]["rows"]) <= 6, "BR-REP-031's cap"


def test_us_rep_019_tc4c__every_null_kpi_has_a_reason_and_every_reason_is_complete(brazos, dana):
    """The pair is the contract: a null with no reason, or a reason with no
    null, is a half-built refusal. Also asserts the gap SHAPE — a screen keys
    its translated sentence on `code` (TD-16/B8: the server sends keys, the UI
    renders language), so a gap missing its code is unrenderable."""
    with tenant_ctx(brazos):
        a_july(brazos, dana)
    payload = summary_for_july(brazos)

    for entry in payload["unavailable"]:
        assert entry["code"], "a gap with no code cannot be rendered in any language"
        assert entry["br_ref"], "a gap must cite the rule it comes from"
        assert len(entry["detail"]) > 40, "a one-word reason is how a register becomes an excuse"
        assert isinstance(entry["wanted_reads"], list)

    null_kpis = {name for name, value in payload["kpis"].items() if value is None}
    assert null_kpis, "this deployment refuses at least three KPIs — see the module docstring"
    assert len(payload["unavailable"]) >= len(null_kpis)


# ═══════════════════════════════════════════════════════════════════════════
# BR-REP-024 — the seam contract itself
# ═══════════════════════════════════════════════════════════════════════════
def test_us_rep_019__the_dark_seams_resolve_to_none_and_nothing_substitutes(brazos):
    """The three documented-but-unauthored reads answer None, by NAME.

    This is DEF-075's assertion at the source: a `None` here must mean *"the
    owner cannot answer"* and must never be turned into a value on the way out.
    """
    with tenant_ctx(brazos):
        fiscal_calendar(brazos)
        assert dashboard_seams.unbilled_read_rollup() is None
        assert dashboard_seams.account_status_class_counts() is None
        assert dashboard_seams.failed_payment_count(as_of=JULY_END) is None
        # …and the five wired ones DO resolve, so a rename anywhere upstream
        # turns this red instead of silently blanking the dashboard.
        assert dashboard_seams.revenue_and_ar is not None
        assert dashboard_seams.regional_settings() is not None
        assert dashboard_seams.current_period(reference_date=JULY_END) is not None
        assert dashboard_seams.invoices_rollup() is not None
        assert dashboard_seams.accounts_rollup() is not None


def test_us_rep_019__no_fiscal_calendar_withdraws_two_options_not_every_figure(
    brazos, dana, monkeypatch
):
    """⚠ **SUPERSEDED BY CR-015 (2026-08-19) AND INVERTED, NOT DELETED.**

    It used to be named `..._means_no_figure_at_all` and it asserted that a
    tenant with no fiscal calendar saw NOTHING — every money figure null, every
    service row an em-dash. The reasoning was right for the product as it stood:
    *"a KPI headed 'this period' over a substituted calendar month is a wrong
    number wearing a right label"* (BR-TEN-022).

    CR-015 removed the PREMISE rather than the reasoning. The screen now STATES
    the window it is reporting over, in dates, above the figures — so it is no
    longer headed *"this period"* over something that is not one. A tenant with
    no fiscal calendar loses the two ACCOUNTING options and keeps its figures
    over the windows that need no calendar at all.

    The old assertion is kept as the thing that must NOT happen: a brand-new
    tenant meeting a page of nulls on its first sign-in.
    """
    with tenant_ctx(brazos):
        a_july(brazos, dana)
    monkeypatch.setattr(dashboard.seams, "current_period", lambda **_: None)
    with tenant_ctx(brazos):
        payload = dashboard.dashboard_summary(as_of=JULY_END)

    # The reason survives, under its own code, and now says what it means.
    assert "fiscal_period_not_configured" in codes(payload)
    offered = {option["id"] for option in payload["period_filter"]["options"]}
    assert "this_period" not in offered
    assert "last_period" not in offered
    # And the rolling window is still offered, is the default, and ANSWERS.
    assert offered == {"last_30_days"}
    assert payload["period_filter"]["default"] == "last_30_days"
    assert payload["period"]["start"] == "2026-07-02"
    assert payload["period"]["end"] == "2026-07-31"
    assert payload["kpis"]["ar_outstanding"] is not None, (
        "the inverted assertion: a tenant with no fiscal calendar used to meet a "
        "page of nulls, and that is the state CR-015 exists to remove"
    )


def test_us_rep_019__an_unwired_ledger_never_falls_back_to_a_cached_balance(
    brazos, dana, monkeypatch
):
    """DEF-104's column, named and refused.

    `accounts.balance` is right there and is exactly where the $0.00 came from
    while the ledger held an issued, unpaid $108.88. With the ledger read
    unresolvable, the money is ABSENT — it does not quietly become a cache read.
    """
    with tenant_ctx(brazos):
        a_july(brazos, dana)
    monkeypatch.setattr(dashboard.seams, "revenue_and_ar", lambda **_: None)
    payload = summary_for_july(brazos)

    assert payload["kpis"]["ar_outstanding"] is None
    assert payload["kpis"]["period_revenue"] is None
    assert "ledger_read_model_is_not_published" in codes(payload)


def test_us_rep_019__the_read_model_takes_an_as_of_and_never_a_clock(brazos, dana):
    """BR-TEN-043. Asked for a month with no postings, the figures move — which
    proves the window is real and not decoration."""
    with tenant_ctx(brazos):
        a_july(brazos, dana)
    with tenant_ctx(brazos):
        january = dashboard.dashboard_summary(as_of=date(2026, 1, 15), period="this_period")
    assert january["period"]["start"] == "2026-01-01"
    # CR-015 / DEF-299: `as_of` is the READ moment clamped into the window. The
    # 15th is inside January, so it stays the 15th — it does NOT become the
    # 31st, which is what this payload used to say about a day that had not
    # happened yet.
    assert january["as_of"] == "2026-01-15"
    assert january["read_on"] == "2026-01-15"
    assert january["kpis"]["period_revenue"] == wire_money(Decimal("0")), (
        "January posted nothing, and zero billed in January is a TRUE zero — "
        "which is exactly why the refusals above are nulls and not zeroes"
    )


# ═══════════════════════════════════════════════════════════════════════════
# TC-9 — isolation
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.isolation
def test_us_rep_019_tc9__another_tenants_figures_never_appear(brazos, lonestar, dana):
    """CLAUDE.md rule 1 + HR-1. Lone Star Ridge posted nothing, so its dashboard
    must not carry Brazos Bend's 152.32 — RLS FORCE plus the read models' own
    tenant filters, asserted end to end rather than assumed."""
    with tenant_ctx(brazos):
        a_july(brazos, dana)
    with tenant_ctx(lonestar):
        fiscal_calendar(lonestar)
        theirs = dashboard.dashboard_summary(as_of=JULY_END)
    assert theirs["kpis"]["ar_outstanding"] != wire_money(LE1_AR)
