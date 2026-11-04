# ── Trace ──────────────────────────────────────────────
# Change:  CR-142-BRC07 — the Reports Build Brief, Phase 4 `P4.11` (the screen),
#          `P4.12` (period and comparison) and `P4.13` (the panel→report
#          handoff, *"which must carry the period across"*). Screen `3·1`,
#          drawn on p036–p038, read as IMAGES per B14 rule 42.
# Rules:   BR-REP-024 (a tile never computes a figure; an absent one is a null
#          WITH its reason) · BR-TEN-022 (a period is COMPUTED) · BR-TEN-043
#          (a window is an argument, never a clock) · BR-SHL-011 (an impossible
#          parameter FALLS BACK) · CLAUDE.md hard rule 2 (money 4 dp stored,
#          never a float) · hard-won law 2's mirror · law 7
# ───────────────────────────────────────────────────────
"""Screen `3·1` — the Reports Dashboard tab, server half.

⚠ **WHAT WOULD MAKE THESE CHECKS PASS WRONGLY** (law 7 clause 2), asked before
a line of this file was written:

  · **Asserting a payload has `kpis` and `panels`** would pass over four tiles
    that are all null and five panels that all refuse — which is a screen, and
    not a dashboard. So each case names the FIGURE it expects and builds the
    one condition that should produce it.
  · **Asserting the ageing panel "has bands"** would pass on five em-dashes.
    `ar_aging` given a RANGE refuses every band total through
    `additivity.footer`, and a first draft of `dashboard_tab.py` did exactly
    that: it would have shipped an Outstanding tile and a `Where the money
    sits` panel that were five dashes and a reason, on every tenant, with every
    test green — because a refusal IS a valid payload. The case therefore
    asserts a band carries a DECIMAL STRING, and a second case asserts the
    handoff spells `f.as_of` rather than `f.from`, which is what keeps them so.
  · **Asserting the router answers 200** would be answered just as readily by
    `reports/<str:key>` having swallowed the word *dashboard* and the viewer
    refusing a report of that name. The case resolves the PATTERN.
  · **Asserting a panel "has a link"** would pass whether or not the link
    carried the period. The case reads the period out of the handoff and
    compares it with the period the panel was computed over.
"""

from datetime import date

import pytest

from apps.reports import dashboard_tab, dashboard_tab_api
from apps.reports import dashboard_tab_period as vocab

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures

pytestmark = pytest.mark.django_db


# ═══════════════════════════════════════════════════════════════════════════
# `P4.12` — THE PERIOD VOCABULARY. No database, no clock: every window is an
# argument (BR-TEN-043), so these cases are signed arithmetic rather than
# fixtures.
# ═══════════════════════════════════════════════════════════════════════════
def _monthly(start_year: int = 2025, start_month: int = 10):
    """A tenant whose accounting period is the calendar month, as a callable.

    Stands in for `report_seams.current_period`, which is the ONLY thing that
    knows a tenant's cadence. Written here rather than mocked so the walk-back
    is exercised against real month lengths — February included.
    """
    import calendar

    def current_period(reference: date):
        last = calendar.monthrange(reference.year, reference.month)[1]
        return {
            "start": date(reference.year, reference.month, 1).isoformat(),
            "end": date(reference.year, reference.month, last).isoformat(),
            "fy_label": f"FY{reference.year}",
            "period": reference.month,
        }

    return current_period


def test_the_menu_offers_twelve_periods_newest_first_and_walks_real_month_lengths():
    options, _ = vocab.period_options(as_of=date(2026, 9, 15), current_period=_monthly())
    assert [o["id"] for o in options] == [
        "2026-09-01", "2026-08-01", "2026-07-01", "2026-06-01",
        "2026-05-01", "2026-04-01", "2026-03-01", "2026-02-01",
        "2026-01-01", "2025-12-01", "2025-11-01", "2025-10-01",
    ]
    # February is 28 days in 2026 and the walk-back must not have invented a
    # 30th — the case that a `start - 30 days` implementation fails.
    february = next(o for o in options if o["id"] == "2026-02-01")
    assert february["end"] == date(2026, 2, 28)


def test_a_tenant_with_no_fiscal_calendar_is_offered_nothing_and_is_told_why():
    """BR-TEN-022 — a period is COMPUTED, so a tenant with no settings has none.

    ⚠ A calendar month is NOT substituted. p037 ② is the whole reason: a window
    the utility does not close its books on heads every figure on the screen
    with an answer to nobody's question.
    """
    options, unavailable = vocab.period_options(
        as_of=date(2026, 9, 15), current_period=lambda _reference: None
    )
    assert options == []
    assert vocab.GAP_NO_ACCOUNTING_PERIOD["code"] in [gap["code"] for gap in unavailable]


def test_budget_is_named_as_absent_rather_than_quietly_dropped():
    """p036 draws THREE comparisons and this product can honour two.

    Nothing publishes a budget for billed, collected, outstanding or days to
    collect, so `budget` is not on the menu — and the payload SAYS so, because
    a third choice that silently vanished is indistinguishable from a bug.
    """
    assert [c["id"] for c in vocab.comparison_options()] == [
        "same_period_last_year",
        "previous_period",
    ]
    _, unavailable = vocab.period_options(as_of=date(2026, 9, 15), current_period=_monthly())
    assert vocab.GAP_BUDGET_NOT_OFFERED["code"] in [gap["code"] for gap in unavailable]
    # BR-SHL-011: asking for it FALLS BACK rather than refusing.
    assert vocab.resolve_comparison("budget") == vocab.COMPARE_DEFAULT
    assert vocab.resolve_comparison("nonsense") == vocab.COMPARE_DEFAULT


def test_the_two_comparisons_name_the_windows_the_drawing_names():
    options, _ = vocab.period_options(as_of=date(2026, 9, 15), current_period=_monthly())
    september = options[0]
    previous = vocab.comparison_window(
        september, vocab.COMPARE_PREVIOUS_PERIOD, current_period=_monthly()
    )
    last_year = vocab.comparison_window(
        september, vocab.COMPARE_SAME_PERIOD_LAST_YEAR, current_period=_monthly()
    )
    assert (previous["start"], previous["end"]) == (date(2026, 8, 1), date(2026, 8, 31))
    assert (last_year["start"], last_year["end"]) == (date(2025, 9, 1), date(2025, 9, 30))


def test_a_period_older_than_the_menu_is_honoured_because_a_menu_is_not_a_cap():
    """`NFR-5` — `PERIODS_OFFERED` bounds what is DRAWN and caps nothing."""
    options, _ = vocab.period_options(as_of=date(2026, 9, 15), current_period=_monthly())
    chosen = vocab.resolve(options, "2024-03-01", current_period=_monthly())
    assert chosen["id"] == "2024-03-01"


def test_an_unreadable_period_falls_back_to_the_newest_rather_than_refusing():
    """BR-SHL-011. `?f.period=` is the part of a URL a person edits by hand."""
    options, _ = vocab.period_options(as_of=date(2026, 9, 15), current_period=_monthly())
    assert vocab.resolve(options, "not-a-date", current_period=_monthly())["id"] == "2026-09-01"
    assert vocab.resolve(options, None, current_period=_monthly())["id"] == "2026-09-01"


# ═══════════════════════════════════════════════════════════════════════════
# `P4.11` — THE FOUR TILES AND THE FIVE PANELS
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **THE REPORTS ARE INJECTED, WHICH IS WHAT MAKES THESE ASSERTIONS ABOUT THE
# ASSEMBLY RATHER THAN ABOUT THE SEED.** `dashboard()` takes its `run` and its
# `current_period`, so a case can state a signed figure and read it back — and
# a change to the demo fixture can never turn one of these green or red.
def _reports(**payloads):
    """A `run` that answers the named keys and raises for anything else.

    Raising rather than returning `{}` is deliberate: a panel that asked for a
    report this case did not set up must FAIL the case, never quietly render an
    empty panel that reads exactly like a real empty period.
    """
    def run(key, params):
        if key not in payloads:
            raise AssertionError(f"the screen asked for an unexpected report: {key} {params}")
        answer = payloads[key]
        return answer(params) if callable(answer) else answer

    return run


AGEING = {
    "basis": "posting",
    "currency": "USD",
    "totals": {
        "current": "28104.4000",
        "d1_30": "11882.1000",
        "d31_60": "4118.0000",
        "d61_90": "2204.2400",
        "d90_plus": "1912.4000",
        "total": "48221.1400",
    },
    "rows": [],
}
REVENUE = {
    "basis": "posting",
    "currency": "USD",
    "totals": {"total": "124855.5600"},
    "rows": [
        {"service_code": "water", "total": "84486.1000"},
        {"service_code": "sewer", "total": "31459.4600"},
        {"service_code": "trash", "total": "8910.0000"},
        {"service_code": None, "total": "0.0000"},
    ],
}
CASH = {"basis": "clearing", "currency": "USD", "totals": {"amount": "117604.1000"}, "rows": []}
PACK = {
    "basis": "posting",
    "currency": "USD",
    "totals": {"release_blocked": False},
    "rows": [
        {
            "check": "accounts_receivable",
            "value_a": "48221.1400",
            "value_b": "48221.1400",
            "difference": "0.0000",
            "result": "agreed",
        }
    ],
}


def _dashboard(**overrides):
    payloads = {
        "revenue_by_service_rate": REVENUE,
        "payments_by_method": CASH,
        "ar_aging": AGEING,
        "close_pack": PACK,
    }
    payloads.update(overrides.pop("payloads", {}))
    return dashboard_tab.dashboard(
        as_of=date(2026, 9, 15),
        run=_reports(**payloads),
        current_period=_monthly(),
        # ⚠ **ALL FOUR SEAMS, NOT TWO.** The service ORDER and the currency are
        # other modules' reads and they raise `AuthError AUTH-003` outside a
        # tenant context — so a first draft of this file failed EVERY panel
        # case in a traceback that named `report_seams.enabled_service_codes`
        # and said nothing about a missing fixture. Injected, these assertions
        # are about the ASSEMBLY and a change to the demo seed can neither turn
        # one green nor turn one red.
        enabled_services=lambda: ("water", "sewer", "trash"),
        regional=lambda: {"currency": "USD"},
        **overrides,
    )


def test_four_tiles_in_the_drawing_s_order_each_carrying_its_own_figure():
    """p037 ④ — *billed, collected, outstanding, days to collect*. FOUR, not five."""
    payload = _dashboard()
    assert [tile["id"] for tile in payload["kpis"]] == [
        "billed",
        "collected",
        "outstanding",
        "days_to_collect",
    ]
    by_id = {tile["id"]: tile for tile in payload["kpis"]}
    assert by_id["billed"]["value"] == "124855.5600"
    assert by_id["collected"]["value"] == "117604.1000"
    assert by_id["outstanding"]["value"] == "48221.1400"


def test_the_tile_whose_owner_publishes_no_count_says_so_rather_than_showing_zero():
    """p037 ④ — *"A tile whose owner publishes no count reads Not counted yet
    with its reason"*, and BR-REP-024 forbids the alternative.

    Days-sales-outstanding is a ratio of the receivable to a period's billing
    and NO definition in the catalogue publishes it. Computing it here is the
    one thing p038 forbids; dropping the tile would leave the drawn band of
    four silently three. So it is DRAWN, with no figure and with its reason.
    """
    days = {tile["id"]: tile for tile in _dashboard()["kpis"]}["days_to_collect"]
    assert days["value"] is None
    assert days["reason_code"] == dashboard_tab.GAP_DAYS_TO_COLLECT["code"]
    assert dashboard_tab.GAP_DAYS_TO_COLLECT["code"] in [
        gap["code"] for gap in _dashboard()["unavailable"]
    ]


def test_a_report_that_answers_with_no_figure_still_carries_a_reason():
    """BR-REP-024 — an absent figure is a null WITH a reason, never a blank.

    `payments_by_method` over a period with no payments answers
    `{"count": 0, "amount": null}`: it ran, it is not refused, and it published
    nothing for this window. Measured on this deployment's PostgreSQL for
    September 2026. Without a reason the tile is a gap that reads identically
    to a broken seam.
    """
    payload = _dashboard(payloads={"payments_by_method": {"totals": {"amount": None}, "rows": []}})
    collected = {tile["id"]: tile for tile in payload["kpis"]}["collected"]
    assert collected["value"] is None
    assert collected["reason_code"] == dashboard_tab.REASON_NO_FIGURE_PUBLISHED


def test_the_change_is_a_percentage_to_six_decimals_and_is_null_against_nothing():
    """CLAUDE.md hard rule 2 — percentages to SIX, displayed at two.

    **$124,855.56 against $117,004.00.** The difference is $7,851.56 and
    `7851.56 / 117004 * 100` is `6.710505623739359338…`, which is
    **`6.710506`** at six decimal places and `6.71%` on screen.

    ⚠ **THIS CASE FIRST ASSERTED `6.710540` AND THE CODE WAS RIGHT.** The
    expected figure was worked out by hand and two digits were transposed, so a
    correct engine went red against a wrong constant — the mirror of the
    failure a golden test exists to catch, and the reason the working is written
    out here rather than left as a number to be trusted. The figure is now
    computed the way the engine computes it: exact `Decimal` arithmetic,
    quantised once, at the end.

    A change against ZERO is null and never `+∞%`: a board pack with an infinity
    on it is worse than a board pack with a blank.
    """
    payload = _dashboard(
        payloads={
            "revenue_by_service_rate": lambda params: (
                REVENUE
                if params.get("from") == "2026-09-01"
                else {"totals": {"total": "117004.0000"}, "rows": []}
            )
        }
    )
    billed = {tile["id"]: tile for tile in payload["kpis"]}["billed"]
    assert billed["comparison"]["value"] == "117004.0000"
    assert billed["comparison"]["change_pct"] == "6.710506"

    against_nothing = _dashboard(
        payloads={
            "revenue_by_service_rate": lambda params: (
                REVENUE if params.get("from") == "2026-09-01" else {"totals": {"total": "0"}, "rows": []}
            )
        }
    )
    assert {t["id"]: t for t in against_nothing["kpis"]}["billed"]["comparison"]["change_pct"] is None


def test_five_panels_in_the_drawing_s_order():
    """p036 regions ⑤–⑨."""
    assert [panel["id"] for panel in _dashboard()["panels"]] == [
        "revenue_12_months",
        "where_the_money_sits",
        "service_mix",
        "biggest_movers",
        "month_closed",
    ]


def test_the_ageing_bands_carry_figures_and_shares_that_are_not_forced_to_100():
    """p037 ⑥ — *"shares rounded and not forced to 100, which is why they read
    58+25+9+4+4"*.

    ⚠ **THE FIGURE IS ASSERTED AS A DECIMAL STRING AND NOT MERELY AS PRESENT.**
    A band whose total `additivity.footer` refused is a MAPPING carrying an
    em-dash, and a case that only checked the key existed would pass on it —
    which is how the range-versus-`as_of` bug would have shipped.
    """
    panel = {p["id"]: p for p in _dashboard()["panels"]}["where_the_money_sits"]
    assert [band["band"] for band in panel["bands"]] == ["current", "1-30", "31-60", "61-90", "90+"]
    assert panel["bands"][0]["value"] == "28104.4000"
    assert [band["share_pct"] for band in panel["bands"]] == ["58.3", "24.6", "8.5", "4.6", "4.0"]
    # 58.3 + 24.6 + 8.5 + 4.6 + 4.0 = 100.0 here by luck, and the panel does not
    # redistribute a remainder to make it so — the assertion is on each share.


def test_the_service_mix_keeps_the_named_remainder_last_and_sums_nothing_it_did_not_read():
    """p037 ⑦ — *every enabled service, in seed order, plus the named remainder*.

    A row with no service is the drawing's *Not attributable*. Dropping it
    would make the panel's rows fail to add up to the report's own total,
    silently — which is the failure mode this whole screen is arranged against.
    """
    panel = {p["id"]: p for p in _dashboard()["panels"]}["service_mix"]
    assert panel["services"][-1]["service_code"] is None
    codes = [row["service_code"] for row in panel["services"]]
    assert set(codes) == {"water", "sewer", "trash", None}


def test_the_movers_panel_states_its_absence_and_keeps_its_door():
    """p037 ⑧ wants *top 3 by change, one service at a time*.

    `usage_and_ranking` is producible and serves the READS; nothing in this
    product publishes a per-account usage comparison between two periods.
    Computing one here is the arithmetic p038 forbids. So the panel shows no
    rows and names why — and its LINK stays live, because the report itself
    opens and is real. Two different sentences.
    """
    panel = {p["id"]: p for p in _dashboard()["panels"]}["biggest_movers"]
    assert panel["movers"] == []
    assert panel["reason_code"] == dashboard_tab.GAP_MOVERS["code"]
    assert panel["opens"] is True
    assert panel["report_params"] is not None


def test_the_close_pack_verdict_is_the_report_s_own_and_is_never_re_derived():
    """p037 ⑨ — *the one panel that can be red*.

    `close_pack` publishes `result` per row and `release_blocked` over the set
    (BR-LED-007). A panel that decided *red* from a non-zero difference would
    be a second opinion about a release blocker, and an UNVERIFIABLE check —
    one that never ran — would come out green.
    """
    panel = {p["id"]: p for p in _dashboard()["panels"]}["month_closed"]
    assert panel["checks"][0]["result"] == "agreed"
    assert panel["blocked"] is False


def test_twelve_bars_oldest_first_with_the_selected_period_accented():
    """p037 ⑤ — *bars, current period accented*, and the axis reads Oct → Sep."""
    panel = {p["id"]: p for p in _dashboard()["panels"]}["revenue_12_months"]
    assert len(panel["bars"]) == dashboard_tab.REVENUE_BARS
    assert panel["bars"][0]["period_id"] == "2025-10-01"
    assert panel["bars"][-1]["period_id"] == "2026-09-01"
    assert [bar["current"] for bar in panel["bars"]] == [False] * 11 + [True]


# ═══════════════════════════════════════════════════════════════════════════
# `P4.13` — THE PERIOD CROSSES INTO THE REPORT
# ═══════════════════════════════════════════════════════════════════════════
def test_every_panel_hands_the_selected_period_to_the_report_behind_it():
    """p038 ⓸, verbatim: *"opening a panel opens that report **already set to
    this period**. A dashboard that drops you into a report on a different
    window is worse than one with no links."*

    ⚠ **THE CASE READS THE PERIOD OUT OF THE HANDOFF.** Asserting a panel *has*
    `report_params` would pass whether or not the window in them was the one
    the panel was computed over, which is the only question `P4.13` asks.
    """
    payload = _dashboard()
    period = payload["period"]
    for panel in payload["panels"]:
        params = panel["report_params"]
        assert params is not None, panel["id"]
        if "f.as_of" in params:
            assert params["f.as_of"] == period["end"], panel["id"]
        else:
            assert params["f.from"] == period["start"], panel["id"]
            assert params["f.to"] == period["end"], panel["id"]


def test_the_ageing_hands_over_an_as_at_date_and_never_a_range():
    """⚠ **THIS IS THE CASE THAT CATCHES THE BUG THAT ALMOST SHIPPED.**

    `ar_aging` is a POSITION at a date. Given a RANGE,
    `slicers.footer_across` adds `time` to what the footer spans and
    `additivity.footer` replaces every band total with an em-dash and
    `balance_does_not_sum_across_time`. Measured on this deployment before the
    argument existed: `ar_aging?from=2026-09-01&to=2026-09-30` refuses `total`;
    `ar_aging?as_of=2026-09-30` serves `8372.060000`.

    So a panel showing `$48,221.14` that handed over a range would open a
    report showing five dashes — *"the numbers change under you and nothing
    says why"*, which p038 calls worse than having no link at all.
    """
    panel = {p["id"]: p for p in _dashboard()["panels"]}["where_the_money_sits"]
    assert panel["report_params"] == {"f.as_of": "2026-09-30"}
    assert "f.from" not in panel["report_params"]


def test_nothing_on_this_screen_is_remembered():
    """p036 ④ and p038 ⓸ — *"Nothing. No write of any kind, not even a
    remembered period."*

    Two calls with different periods return different windows and leave no
    trace between them: the second call does not inherit the first.
    """
    september = _dashboard(period="2026-09-01")["period"]
    august = _dashboard(period="2026-08-01")["period"]
    assert september["id"] == "2026-09-01"
    assert august["id"] == "2026-08-01"
    assert _dashboard()["period"]["id"] == "2026-09-01"


# ═══════════════════════════════════════════════════════════════════════════
# THE ROUTE
# ═══════════════════════════════════════════════════════════════════════════
def test_the_router_resolves_reports_dashboard_to_its_own_view_and_not_the_viewer():
    """`P0.8`'s reserved segment, one layer down.

    ⚠ **THE ROUTER, NOT A STATUS CODE.** `dashboard` sits in the same URL
    position as a report key — it is one of the four reserved segments
    precisely because a utility might name a report *Dashboard*. A catch-all
    declared first would swallow this and a client asking for the tab would get
    a 422 about a report of that name, which a status assertion would not tell
    apart from a working screen.
    """
    from django.urls import resolve

    match = resolve("/api/brazosbend/reports/dashboard")
    assert match.func is dashboard_tab_api.reports_dashboard
