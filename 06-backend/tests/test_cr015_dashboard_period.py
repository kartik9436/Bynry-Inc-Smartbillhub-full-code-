# ── Trace ──────────────────────────────────────────────
# Story:    US-REP-019 (S7 / DSH-01)   Screens: S7
# Change:   CR-015 (12-governance/11-change-requests.md §CR-015 — *"we will
#           ahve to allow period filter on dashbaord … default filter can be
#           last cycle or last 30 days and let user to change the peiod"*)
# Defect:   DEF-299 (the screen labelled itself as of a date eleven days in the
#           future) · DEF-298 (a calendar month is the wrong window for
#           cycle-shaped work)
# Rules:    BR-REP-035 (the period vocabulary and its ruled default) ·
#           BR-REP-036 (`as_of` is the READ moment clamped into the period) ·
#           BR-REP-028 (regions load, empty and FAIL independently) ·
#           BR-TEN-022 (periods are COMPUTED) · BR-TEN-043 (a window is an
#           argument, never a clock) · BR-SHL-011 (an unknown parameter falls
#           back, never errors)
# ───────────────────────────────────────────────────────
"""CR-015 · the period filter, and DEF-299's `as_of`.

**RED PROVED FIRST — the failure that started this file is quoted, and it was
found on a booted stack rather than in a fixture.** On 2026-08-19, against the
live Brazos Bend tenant:

    as_of 2026-08-31 period {'start': '2026-08-01', 'end': '2026-08-31'}
    today 2026-08-19

Eleven days in the future, on the first screen after every sign-in. Nothing
disagreed with anything else, which is why every check in the repo was green:
the value was CARRIED correctly everywhere. What was wrong was what it MEANT.

The per-behaviour reds are quoted in the case that closed each one.

**WHY THE NEGATIVE ASSERTIONS MATTER MOST HERE.** A period filter has three
plausible ways to look finished and be wrong, and each has a case below:

    the default   default to whatever is first in the list, or to the calendar
                  month, which is the exact thing this change exists to stop
    the clamp     clamp only the upper end, so a closed period reads correctly
                  and nothing ever exercises the lower one
    the failure   read SET-07's cycles in the page body and let a metering
                  outage blank the whole landing screen — which happened, and
                  is quoted below
"""

from datetime import date

import pytest

from apps.metering import models as metering_models
from apps.reports import api as reports_api
from apps.reports import dashboard
from apps.reports import dashboard_period as period_vocab
from apps.reports import dashboard_seams as seams

from tests.ledger_le_fixtures import JULY_END, make_accounts, post_le1_month
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import FakeUser, tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db


def fiscal_calendar(tenant):
    """`seed_demo.REGIONAL_SETTINGS`' fiscal fields — BR-TEN-022 needs them."""
    from apps.tenancy import models as tenancy_models

    tenancy_models.TenantSettings.objects.update_or_create(
        tenant_id=tenant.id,
        defaults={
            "fy_start_month": 10,
            "fy_start_day": 1,
            "close_cadence": "monthly",
            "close_day": "3rd business day",
            "number_format": "1,234.56",
        },
    )


def a_july(tenant, dana):
    fiscal_calendar(tenant)
    accounts = make_accounts(dana, tenant, {})
    post_le1_month(tenant, accounts)
    return accounts


def a_cycle(tenant, *, code, window_start, bill_date, status="active"):
    """One SET-07 cycle definition — the row `cycles_list` publishes.

    ⚠ **THE KEYWORD IS STILL CALLED `window_start` AND THE COLUMN IS GONE
    (W5-T2).** metering 0021 dropped `cycles.window_start`/`window_end`; the
    window is derived from `start_day` + `days_to_complete`. The helper's
    signature is left alone on purpose — every case here is about the
    dashboard's PERIOD MENU, not about the cycle's storage, and rewriting a
    dozen call sites would obscure what each case is actually asserting. What
    it writes is the ruled generation.
    """
    return metering_models.Cycle.objects.create(
        tenant_id=tenant.id,
        code=code,
        frequency="Monthly",
        start_day=window_start.day,
        days_to_complete=max((bill_date - window_start).days, 0) + 1,
        # ⚠ **`bill_date` IS NO LONGER A COLUMN (RC-W6, metering 0023 / OQ-344)**
        # — the surviving default is a bill DAY, and billing derives a run's
        # date as *"the bill day, in the month after the period ends"*. The
        # keyword stays, for the same reason `window_start`'s does one line up:
        # every case here is about the dashboard's PERIOD MENU, and it is the
        # derived WINDOW those cases read, never this value.
        bill_day=bill_date.day,
        status=status,
    )


def summary(tenant, **kwargs):
    kwargs.setdefault("as_of", JULY_END)
    with tenant_ctx(tenant):
        return dashboard.dashboard_summary(**kwargs)


def option_ids(payload):
    return [option["id"] for option in payload["period_filter"]["options"]]


# ═══════════════════════════════════════════════════════════════════════════
# DEF-299 · `as_of` IS THE READ MOMENT, CLAMPED — BR-REP-036
# ═══════════════════════════════════════════════════════════════════════════
def test_cr015__as_of_mid_period_is_today_and_not_the_period_end(brazos, dana):
    """THE DEFECT, exactly as it was reported.

    RED, before the fix, with `as_of=2026-07-15`:
    `AssertionError: assert '2026-07-31' == '2026-07-15'` — the read model
    returned the period END for a read taken on the 15th.
    """
    with tenant_ctx(brazos):
        a_july(brazos, dana)
    payload = summary(brazos, as_of=date(2026, 7, 15), period="this_period")

    assert payload["period"] == {"start": "2026-07-01", "end": "2026-07-31"}
    assert payload["as_of"] == "2026-07-15", (
        "the PO's ruling, option (a): as_of is the moment the figures were READ, "
        "clamped into the period — so mid-period it is today"
    )
    assert payload["read_on"] == "2026-07-15"


def test_cr015__as_of_on_a_closed_period_is_the_period_end_not_today(brazos, dana):
    """The other half of the same ruling: *"once a period closes it is the
    period end"*. `read_on` stays the day the figures were read, so the header
    can say what day it is while the body says what the figures are as of."""
    with tenant_ctx(brazos):
        a_july(brazos, dana)
    payload = summary(brazos, as_of=date(2026, 8, 19), period="last_period")

    assert payload["period"] == {"start": "2026-07-01", "end": "2026-07-31"}
    assert payload["as_of"] == "2026-07-31"
    assert payload["read_on"] == "2026-08-19"


def test_cr015__the_clamp_has_a_lower_end_too():
    """The lower clamp, proved directly, because no OPTION exercises it today.

    A window entirely in the future takes its START rather than claiming the
    figures were read before it began. Asserted on the pure function so the
    behaviour is pinned before an option that needs it ever exists — the
    alternative is a half-clamp that reads correctly for a year.
    """
    window = (date(2026, 9, 1), date(2026, 9, 30))
    assert period_vocab.clamp_as_of(date(2026, 8, 19), window) == date(2026, 9, 1)
    assert period_vocab.clamp_as_of(date(2026, 9, 15), window) == date(2026, 9, 15)
    assert period_vocab.clamp_as_of(date(2026, 10, 4), window) == date(2026, 9, 30)
    assert period_vocab.clamp_as_of(date(2026, 8, 19), None) == date(2026, 8, 19)


def test_cr015__as_of_never_reads_a_clock_when_it_is_given_one(brazos, dana):
    """BR-TEN-043 survives the fix, and this is the case that proves it.

    The temptation in DEF-299 was to make `as_of` a `date.today()` call inside
    the read — the value would then have been right on every screen and the
    read model would have become untestable against a signed figure. So the
    tenant's clock seam is BROKEN here, and a caller who passed `as_of` must
    still get a complete answer.
    """
    with tenant_ctx(brazos):
        a_july(brazos, dana)

    def boom(**_):
        raise AssertionError("tenant_today must not be reached when as_of is given")

    original = seams.tenant_today
    seams.tenant_today = boom
    try:
        payload = summary(brazos, as_of=date(2026, 7, 15), period="this_period")
    finally:
        seams.tenant_today = original

    assert payload["as_of"] == "2026-07-15"
    assert payload["kpis"]["ar_outstanding"] is not None


# ═══════════════════════════════════════════════════════════════════════════
# BR-REP-035 · THE VOCABULARY AND THE RULED DEFAULT
# ═══════════════════════════════════════════════════════════════════════════
def test_cr015__the_default_is_the_rolling_thirty_days(brazos, dana):
    """⚠ **SUPERSEDED (CR-029 D8① 2026-08-23 → the completed-cycle window is
    removed).** This case asserted `default == "last_cycle"`, over a definition
    of *"completed"* this lane derived, flagged as a judgment and raised as
    OQ-268. The PO's answer was **"dont build it"**, so the option is gone and
    the default is the rolling window CR-015's own ruling named as the
    alternative — *"default filter can be last cycle or last 30 days"*.

    The original RED is kept because it still describes this file's first
    failure: before `default_option_id` existed, `KeyError: 'period_filter'`.
    """
    with tenant_ctx(brazos):
        a_july(brazos, dana)
        a_cycle(brazos, code="07-A", window_start=date(2026, 7, 1), bill_date=date(2026, 7, 8))
    payload = summary(brazos, as_of=date(2026, 7, 31))

    assert payload["period_filter"]["default"] == "last_30_days"
    assert payload["period_filter"]["selected"] == "last_30_days"
    assert payload["period"] == {"start": "2026-07-02", "end": "2026-07-31"}


def test_cr015__a_billed_cycle_no_longer_moves_the_reported_window(brazos, dana):
    """⚠ **SUPERSEDED (CR-029 D8①)** — this was
    `test_cr015__the_cycle_window_runs_to_the_BILL_date_not_the_read_window_end`,
    and it pinned the judgment itself: *a cycle is complete when its bill date
    has passed, and its window runs `window_start` … `bill_date`*.

    The judgment is withdrawn, so the assertion is INVERTED rather than
    deleted: cycle 08-B, reading 12–16 Aug and billing on the 19th, changes the
    reported window not at all. Kept in this shape because a later lane
    reintroducing the completed-cycle window would go red here and be sent back
    to the ruling.
    """
    with tenant_ctx(brazos):
        a_july(brazos, dana)
        # W5-T2: the window is derived, so "closes on the 16th" is said as a
        # 5-day window opening on the 12th rather than by writing an end date.
        cycle = a_cycle(
            brazos, code="08-B", window_start=date(2026, 8, 12), bill_date=date(2026, 8, 19)
        )
        cycle.days_to_complete = 5
        cycle.save(update_fields=["days_to_complete"])
    payload = summary(brazos, as_of=date(2026, 8, 19))

    assert payload["period"] == {"start": "2026-07-21", "end": "2026-08-19"}
    assert "last_cycle" not in option_ids(payload)


def test_cr015__the_missing_cycle_window_carries_its_reason(brazos, dana):
    """⚠ **SUPERSEDED (CR-029 D8①)** — was
    `test_cr015__a_cycle_that_has_not_billed_yet_is_not_completed`.

    The absence is still STATED, and what changed is what it is an absence OF:
    the old sentence said *this tenant has no completed cycle yet* (a fact about
    data, which would come right by itself); the new one says a cycle window is
    not offered at all (a fact about the product, true for every tenant).
    """
    with tenant_ctx(brazos):
        a_july(brazos, dana)
        a_cycle(brazos, code="09-A", window_start=date(2026, 9, 1), bill_date=date(2026, 9, 8))
    payload = summary(brazos, as_of=date(2026, 8, 19))

    assert "last_cycle" not in option_ids(payload)
    assert payload["period_filter"]["default"] == "last_30_days"
    assert any(
        entry["code"] == "billing_cycle_window_is_not_offered" for entry in payload["unavailable"]
    ), "the absence carries its reason"
    assert not any(
        entry["code"] == "no_completed_billing_cycle" for entry in payload["unavailable"]
    ), "and the superseded reason is gone rather than served beside it"


def test_cr015__a_draft_or_retired_cycle_is_never_the_window(brazos, dana):
    """BR-MET-076: a draft cycle stamps no service point and an inactive one is
    retired. Neither is a window anybody billed in."""
    with tenant_ctx(brazos):
        a_july(brazos, dana)
        a_cycle(
            brazos,
            code="07-DRAFT",
            window_start=date(2026, 7, 1),
            bill_date=date(2026, 7, 8),
            status="draft",
        )
    payload = summary(brazos, as_of=date(2026, 7, 31))

    assert "last_cycle" not in option_ids(payload)


def test_cr015__last_30_days_is_thirty_dates_inclusive(brazos, dana):
    """The fence-post, pinned. `as_of - 29 … as_of` is thirty dates, and a
    window that labels itself "30 days" and covers 31 is the kind of error that
    is invisible on every screen and wrong in every reconciliation."""
    with tenant_ctx(brazos):
        a_july(brazos, dana)
    payload = summary(brazos, as_of=date(2026, 8, 19), period="last_30_days")

    assert payload["period"] == {"start": "2026-07-21", "end": "2026-08-19"}
    start = date.fromisoformat(payload["period"]["start"])
    end = date.fromisoformat(payload["period"]["end"])
    assert (end - start).days + 1 == 30


def test_cr015__the_two_accounting_windows_are_computed_and_adjacent(brazos, dana):
    """BR-TEN-022 is untouched: both are COMPUTED from the fiscal settings, and
    `last_period` is the period containing the day before this one starts —
    never "minus one month", because a month is not what a period is."""
    with tenant_ctx(brazos):
        a_july(brazos, dana)
    payload = summary(brazos, as_of=date(2026, 8, 19))

    options = {option["id"]: option for option in payload["period_filter"]["options"]}
    assert options["this_period"]["start"] == "2026-08-01"
    assert options["this_period"]["end"] == "2026-08-31"
    assert options["last_period"]["start"] == "2026-07-01"
    assert options["last_period"]["end"] == "2026-07-31"
    assert options["this_period"]["fy_label"] == "FY2026"


def test_cr015__the_menu_is_offered_in_one_fixed_order(brazos, dana):
    """⚠ AMENDED (CR-029 D8①): the cycle window is no longer first, because it
    is no longer offered. The rolling window leads and the two accounting
    windows come after, so a finance officer reconciling against S36 still
    finds the period by name in the same place."""
    with tenant_ctx(brazos):
        a_july(brazos, dana)
        a_cycle(brazos, code="07-A", window_start=date(2026, 7, 1), bill_date=date(2026, 7, 8))
    payload = summary(brazos, as_of=date(2026, 8, 19))

    assert option_ids(payload) == ["last_30_days", "this_period", "last_period"]


# ═══════════════════════════════════════════════════════════════════════════
# BR-SHL-011 · AN UNKNOWN VALUE FALLS BACK, IT NEVER REFUSES
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("requested", ["", "last_quarter", "LAST_CYCLE", "../etc/passwd"])
def test_cr015__an_impossible_period_falls_back_to_the_default(brazos, dana, requested):
    """A landing page that 500s on a hand-edited URL is a locked front door."""
    with tenant_ctx(brazos):
        a_july(brazos, dana)
    payload = summary(brazos, as_of=date(2026, 8, 19), period=requested)

    assert payload["period_filter"]["selected"] == payload["period_filter"]["default"]
    assert payload["period"]["start"] is not None


def test_cr015__the_route_reads_f_period_and_answers_200(brazos, dana):
    """BR-SHL-011's URL grammar spells a filter `f.<name>`, so a period a person
    is looking at is SHAREABLE — paste the link, see the same window."""
    with tenant_ctx(brazos):
        a_july(brazos, dana)
    response = api_call(
        reports_api.dashboard_summary,
        "get",
        user=FakeUser(),
        role="billing_clerk",
        tenant=brazos,
        query={"f.period": "last_period", "asOf": "2026-08-19"},
    )

    assert response.status_code == 200
    assert response.data["period_filter"]["selected"] == "last_period"
    assert response.data["period"] == {"start": "2026-07-01", "end": "2026-07-31"}
    assert response.data["as_of"] == "2026-07-31"
    assert response.data["read_on"] == "2026-08-19"


# ═══════════════════════════════════════════════════════════════════════════
# BR-REP-028 · THE OUTAGE THAT ALMOST SHIPPED
# ═══════════════════════════════════════════════════════════════════════════
def test_cr015__a_metering_outage_costs_the_cycle_option_and_not_the_page(brazos, dana):
    """RED, and this one was found by an EXISTING test rather than a new one.

    The first version of the period vocabulary called `seams.cycles_list()`
    bare, in the page body, and `test_cr012_tc15` went red with:

        RuntimeError: cycles_list is on fire

    — a metering outage blanking the whole landing screen, which is the
    guarantee CR-012 built (BR-REP-028: *"one section failing must not blank
    the page"*). The read is memoised now, so the failure costs the
    cycle-status region and nothing else.

    ⚠ AMENDED (CR-029 D8①): it used to cost the `last_cycle` option too. The
    period filter no longer reads cycles at all, so that half of the blast
    radius is gone — and the assertion is KEPT, because "the option is absent"
    is now true for a different and stronger reason.
    """
    with tenant_ctx(brazos):
        a_july(brazos, dana)

    def boom(*_args, **_kwargs):
        raise RuntimeError("cycles_list is on fire")

    original = seams.cycles_list
    seams.cycles_list = boom
    try:
        payload = summary(brazos, as_of=date(2026, 8, 19))
    finally:
        seams.cycles_list = original

    assert "last_cycle" not in option_ids(payload)
    assert payload["period_filter"]["default"] == "last_30_days"
    assert payload["kpis"]["ar_outstanding"] is not None, "the page still carries its money"
    assert payload["regions"]["cycle_status"]["state"] == "error"


def test_cr015__the_cycle_line_counts_down_from_TODAY_not_from_a_closed_window(brazos, dana):
    """The one region that reads `read_on` and not `as_of`.

    *"Cycle 08-A closes in N days"* is a statement about the future from NOW.
    Fed the clamped `as_of` of a window that ended in July it would count down
    from a date in the past and report a cycle as closing in a NEGATIVE number
    of days — a sentence no operator can act on.
    """
    with tenant_ctx(brazos):
        a_july(brazos, dana)
        cycle = a_cycle(
            brazos, code="08-A", window_start=date(2026, 8, 1), bill_date=date(2026, 8, 8)
        )
        # W5-T2 — `read_day_to` is a dropped column and the countdown reads
        # `next_cycle_date`. The cycle needs a first run so the period engine
        # can anchor one; the assertion below is unchanged and is about WHICH
        # clock the countdown uses, not about where the date comes from.
        cycle.frequency = "Monthly"
        cycle.first_run_date = date(2026, 8, 25)
        cycle.days_to_complete = 3
        cycle.start_day = 25
        cycle.save(update_fields=["frequency", "first_run_date", "days_to_complete", "start_day"])
    payload = summary(brazos, as_of=date(2026, 8, 19), period="last_period")

    assert payload["as_of"] == "2026-07-31", "the BODY is as of the closed period"
    assert payload["read_on"] == "2026-08-19", "the HEADER is as of now"
    days = (payload["regions"]["cycle_status"]["data"] or {}).get("days")
    assert days is None or days >= 0, f"counted down from a past date: {days}"


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-015 (12-governance/11-change-requests.md §CR-015) · 12-governance/02-decision-log.md 2026-08-19 §"FOUR RULINGS" 3 and 4 · 04-docs/05-modules/12-reports/02-business-rules.md BR-REP-035/036
# screens: S7
# generated: 2026-08-19 by story-coder (CR-015 lane)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — the as_of case was proved against the LIVE booted fixture reading `as_of 2026-08-31` on 2026-08-19, and the BR-REP-028 case was proved by an EXISTING test going red with `RuntimeError: cycles_list is on fire`. Both failures are quoted where they sit.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
