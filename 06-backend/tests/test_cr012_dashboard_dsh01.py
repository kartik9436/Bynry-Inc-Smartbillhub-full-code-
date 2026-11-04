# ── Trace ──────────────────────────────────────────────
# Story:    US-REP-019 (S7 / DSH-01)   Screens: S7   Change: CR-012
# Rules:    BR-REP-025 (the TENANT's own services, all of them, seed order —
#           PO 2026-08-19) · BR-REP-026 (bars are a share
#           of the LARGEST) · BR-REP-027 (the cycle status line's four states) ·
#           BR-REP-028 (regions load, empty and FAIL independently) ·
#           BR-REP-029 (money and counts arrive pre-formatted) · BR-REP-030
#           (five aging buckets; arrangements in their TRUE bucket; shares need
#           not total 100%) · BR-REP-031 (activity: 24h, max 6, audit log) ·
#           BR-REP-032 (to do: max 4, owner-generated) · BR-REP-033 (nothing
#           mutates; the two page actions are role-gated) · BR-REP-034 (the MTD
#           sub-line is a TYPED tenant target; untyped ⇒ figure alone) ·
#           BR-REP-024 (a tile never computes a figure) · CLAUDE.md rule 1/2
# Golden:   the PO's own worked examples — Electric 238,400 / Water 76,200 /
#           Sewer 28,100 → bars 100 / 32 / 12 / — / — (11-change-requests.md
#           §"THE BAR RULE, WORKED"); MTD 342,700 against a 400,000 target →
#           `86% of $400,000 target` (02-decision-log.md, PO answered "B").
# ───────────────────────────────────────────────────────
"""CR-012 · DSH-01 — the five things the PO's requirement CHANGED, each proved.

**RED PROVED FIRST, and the failures are quoted where each case sits.** This
file was written before `apps/reports/dashboard_regions.py` existed and the
whole module went red on
`ImportError: cannot import name 'dashboard_regions' from 'apps.reports'`; the
per-behaviour failures that followed are quoted in the docstring of the case
that closed them, because a check nobody watched fail is a check nobody can
trust (hard-won law 7).

**WHY THE NEGATIVE ASSERTIONS OUTNUMBER THE POSITIVE ONES.** Every one of these
regions has a plausible way to look finished and be wrong:

    service mix    omit the services that billed nothing — which reads as
                   "this utility does not sell trash" rather than "trash
                   billed nothing this month"
    the bars       compute a share of the TOTAL, which is what r10's own file
                   hardcodes and what the PO explicitly reversed
    aging          move payment-arrangement accounts into Current, which is
                   what the naive implementation does and is the opposite of
                   the rule
    the MTD tile   put a number after "of" — any number — rather than nothing
    regions        assert the page renders when every seam answers, which
                   proves nothing about the acceptance criterion "one section
                   failing must not blank the page"
"""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.reports import api as reports_api
from apps.reports import dashboard, dashboard_format as fmt
from apps.reports import dashboard_regions as regions
from apps.reports import dashboard_seams as seams

from tests.isolation_helpers import writing_as_tenant
from tests.ledger_le_fixtures import JULY_END, make_accounts, post_le1_month
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import FakeUser, tenant_ctx
from tests.test_us_ten_helpers import api_call

#: Silver Creek's own five, as the tenant CONFIGURED them — which is what this
#: panel draws since the PO's ruling of 2026-08-19. Named here rather than
#: hard-coded in each case, because the point of the ruling is that the list is
#: a tenant's answer and no longer a constant in the product: the PO's five
#: worked bar examples are unchanged by it, and that is the thing to prove.
#:
#: NOTE the ORDER: seed order puts Gas THIRD (BR-RAT-024), so the drawn rows
#: read electric · water · gas · sewer · trash. The old hard-coded list read
#: electric · water · sewer · trash · gas, and the difference is the one visible
#: consequence of ordering by the platform seed rather than by a constant.
SILVER_CREEK_SERVICES = ("electric", "water", "sewer", "trash", "gas")
SILVER_CREEK_ROWS = ["electric", "water", "gas", "sewer", "trash"]

pytestmark = pytest.mark.django_db


def fiscal_calendar(tenant):
    """`seed_demo.REGIONAL_SETTINGS`' fiscal fields — BR-TEN-022 needs them."""
    from apps.tenancy import models as tenancy_models

    # ⚠ INSIDE THE TENANT'S OWN CONTEXT (DEF-GOV-4024/4036, 2026-09-05), and
    # `update_or_create` is the shape that makes this bite twice. With no
    # `app.tenant_id` the SELECT half matches nothing — the row is there, the
    # policy hides it — so it falls through to the INSERT half, which
    # `tenant_settings`' WITH CHECK then refuses outright. The visible failure
    # is a write error on a row that already exists.
    with writing_as_tenant(tenant):
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


def summary(tenant, **kwargs):
    """CR-012's payload, asked for LE-1's month.

    ⚠ `period="this_period"` was added by CR-015 and is not a test fix: the
    accounting period used to be the only window this read model had, and it is
    now one of four with the last completed cycle as the ruled default. A case
    that means *"LE-1's July"* has to say so.
    """
    kwargs.setdefault("period", "this_period")
    with tenant_ctx(tenant):
        return dashboard.dashboard_summary(as_of=kwargs.pop("as_of", JULY_END), **kwargs)


def service_row(payload, code):
    rows = payload["regions"]["service_mix"]["data"]["rows"]
    return next(row for row in rows if row["service_code"] == code)


# ═══════════════════════════════════════════════════════════════════════════
# BR-REP-029 — MONEY AND COUNTS ARRIVE PRE-FORMATTED (TC-17)
#
# RED, quoted: the first `money_display` returned `'$184320.00'` —
#   AssertionError: assert '$184320.00' == '$184,320.00'
# and the `1.234,56` convention returned `'184.320,00€'`, missing the U+00A0
#   AssertionError: assert '184.320,00€' == '184.320,00\xa0€'
# Both strings below are what `Intl.NumberFormat` itself emits, taken from node
# rather than from memory, so the server and `MoneyCell` agree by construction.
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    "amount,currency,number_format,expected",
    [
        (Decimal("184320"), "USD", "1,234.56", "$184,320.00"),
        (Decimal("-42.5"), "USD", "1,234.56", "-$42.50"),
        (Decimal("0"), "USD", "1,234.56", "$0.00"),
        (Decimal("8.2985"), "USD", "1,234.56", "$8.30"),  # half-up, BR-TEN-080
        (Decimal("184320"), "EUR", "1,234.56", "€184,320.00"),
        (Decimal("184320"), "CAD", "1,234.56", "CA$184,320.00"),
        (Decimal("184320"), "MXN", "1,234.56", "MX$184,320.00"),
        (Decimal("184320"), "GBP", "1,234.56", "£184,320.00"),
        (Decimal("184320"), "EUR", "1.234,56", "184.320,00 €"),
        (Decimal("184320"), "XYZ", "1,234.56", "184,320.00 XYZ"),  # unknown code
        (None, "USD", "1,234.56", None),  # absent in, absent out — never $0.00
    ],
)
def test_cr012_tc17__money_is_formatted_on_the_server(amount, currency, number_format, expected):
    """The server's string IS `MoneyCell`'s string (BR-REP-029).

    The last case is the load-bearing one: a figure an owner declined to state
    formats to `None`, never to `$0.00`. DEF-104 is a `$0.00` that meant "I do
    not know" reaching a customer-facing screen.
    """
    assert fmt.money_display(amount, currency=currency, number_format=number_format) == expected


def test_cr012_tc17b__money_never_passes_through_a_float():
    """CLAUDE.md rule 2, enforced at the boundary rather than trusted."""
    with pytest.raises(TypeError):
        fmt.money_display(184320.0, currency="USD")


@pytest.mark.parametrize(
    "value,number_format,expected",
    [
        (1247, "1,234.56", "1,247"),
        (1247, "1.234,56", "1.247"),
        (0, "1,234.56", "0"),
        (None, None, None),
    ],
)
def test_cr012_tc17c__counts_are_grouped_with_the_tenants_own_separator(
    value, number_format, expected
):
    assert fmt.count_display(value, number_format=number_format) == expected


def test_cr012_tc17d__the_service_mix_value_is_abbreviated_like_r10():
    """r10's `.val` column reads `$238k`, not `$238,400.00`."""
    assert fmt.money_display_short(Decimal("238400"), currency="USD") == "$238k"
    assert fmt.money_display_short(Decimal("76200"), currency="USD") == "$76k"
    assert fmt.money_display_short(Decimal("28100"), currency="USD") == "$28k"
    # Below a thousand the abbreviation would destroy the figure, so it does not
    # happen: LE-1's own 553.69 stays readable.
    assert fmt.money_display_short(Decimal("553.69"), currency="USD") == "$553.69"


# ═══════════════════════════════════════════════════════════════════════════
# BR-REP-026 — THE BARS. The PO's five worked examples, as arithmetic (TC-13).
#
# RED, quoted: the first pass computed a share of the TOTAL and gave
#   AssertionError: assert [70, 22, 8, 0, 0] == [100, 32, 12, None, None]
# which is exactly the number r10's own markup hardcodes — the failure this
# case exists to make impossible to reintroduce.
# ═══════════════════════════════════════════════════════════════════════════
def test_cr012_tc13__example_a_the_r10_fixture_is_a_share_of_the_largest():
    """238,400 / 76,200 / 28,100 → **100 / 32 / 12**, NOT r10's 70 / 22 / 8.

    The ruled column sums to 144% and is not meant to reach 100.
    """
    rows = regions.mix_rows(
        {"electric": Decimal("238400"), "water": Decimal("76200"), "sewer": Decimal("28100")},
        codes=regions.panel_service_codes(SILVER_CREEK_SERVICES),
        currency="USD",
        number_format="1,234.56",
    )
    assert [row["service_code"] for row in rows] == SILVER_CREEK_ROWS, (
        "BR-REP-025 as amended 2026-08-19: the tenant's OWN services, all of them, in the "
        "platform's seed order — which puts Gas third"
    )
    by_code = {row["service_code"]: row["bar_pct"] for row in rows}
    assert [by_code[code] for code in ("electric", "water", "sewer")] == [100, 32, 12]
    assert sum(row["bar_pct"] for row in rows) == 144


def test_cr012_tc13b__example_b_the_100_percent_bar_belongs_to_whoever_billed_most():
    """A water-only utility: Water 100 / Sewer 33 / Trash 14, Electric empty."""
    rows = regions.mix_rows(
        {"water": Decimal("94300"), "sewer": Decimal("31500"), "trash": Decimal("12800")},
        codes=regions.panel_service_codes(SILVER_CREEK_SERVICES),
        currency="USD",
        number_format="1,234.56",
    )
    by_code = {row["service_code"]: row for row in rows}
    assert by_code["water"]["bar_pct"] == 100
    assert by_code["sewer"]["bar_pct"] == 33
    assert by_code["trash"]["bar_pct"] == 14
    assert by_code["electric"]["bar_pct"] == 0
    assert by_code["electric"]["display"] == fmt.EM_DASH


def test_cr012_tc13c__example_c_two_services_almost_level_draw_100_and_99():
    """51,200 vs 50,900 → **100% and 99%**. Share-of-total drew both at 50% and
    made a photo finish look like a deliberate half-and-half split — the PO's
    own strongest argument for the rule."""
    rows = regions.mix_rows(
        {"electric": Decimal("51200"), "water": Decimal("50900")},
        codes=regions.panel_service_codes(SILVER_CREEK_SERVICES),
        currency="USD",
        number_format="1,234.56",
    )
    by_code = {row["service_code"]: row for row in rows}
    assert (by_code["electric"]["bar_pct"], by_code["water"]["bar_pct"]) == (100, 99)


def test_cr012_tc13d__example_d_nothing_billed_divides_by_nothing_and_shows_no_zero_percent():
    """Day one of the cycle: five em-dashes, no division, and **no `0%`**, which
    would read as *we sell this and sold none of it*."""
    rows = regions.mix_rows(
        {},
        codes=regions.panel_service_codes(SILVER_CREEK_SERVICES),
        currency="USD",
        number_format="1,234.56",
    )
    assert len(rows) == 5
    for row in rows:
        assert row["display"] == fmt.EM_DASH
        assert row["bar_pct"] == 0
        assert row["share_display"] is None, "a share of nothing is undefined, never 0%"


def test_cr012_tc13e__example_e_a_tiny_service_still_draws_a_visible_bar():
    """$1,900 beside $238,400 is **1%**, never nothing. A service that billed
    real money must not render as absent."""
    rows = regions.mix_rows(
        {"electric": Decimal("238400"), "trash": Decimal("1900")},
        codes=regions.panel_service_codes(SILVER_CREEK_SERVICES),
        currency="USD",
        number_format="1,234.56",
    )
    trash = next(row for row in rows if row["service_code"] == "trash")
    assert trash["bar_pct"] == 1
    assert (
        trash["display"] == "$2k"
        or trash["display"] == "$1,900.00"
        or trash["display"].endswith("k")
    )


def test_cr012_tc11__an_unsold_service_shows_an_em_dash_and_never_a_zero():
    """BR-REP-025 decision 3: `$0.00` is never printed in this column, because a
    printed zero and an absent service look identical to a reader and mean
    opposite things."""
    rows = regions.mix_rows(
        {"electric": Decimal("238400"), "trash": Decimal("0")},
        codes=regions.panel_service_codes(SILVER_CREEK_SERVICES),
        currency="USD",
        number_format="1,234.56",
    )
    trash = next(row for row in rows if row["service_code"] == "trash")
    assert trash["display"] == fmt.EM_DASH
    assert trash["display"] != "$0.00"
    assert trash["bar_pct"] == 0


def test_cr012_tc12__revenue_outside_the_five_is_a_named_remainder_never_dropped():
    """BR-REP-025: the panel may not foot to less than the period's revenue.

    A late fee is charged to an ACCOUNT and carries no service; solar is a
    platform service the panel does not draw. Both are reported as a remainder
    rather than folded into one of the five (which would be a wrong figure) or
    dropped (which would be a silent shortfall — BR-REP-002's own rule).
    """
    payload = regions.service_mix_data(
        [
            SimpleNamespace(service_id="1", service_code="electric", total_billed=Decimal("100")),
            SimpleNamespace(service_id="2", service_code="solar", total_billed=Decimal("40")),
            SimpleNamespace(service_id=None, service_code=None, total_billed=Decimal("5")),
        ],
        configured_services=SILVER_CREEK_SERVICES,
        currency="USD",
        number_format="1,234.56",
    )
    assert payload["remainder"] is not None
    assert payload["remainder"]["amount"] == "45.000000"
    assert payload["remainder"]["services"] == 2
    assert [row["service_code"] for row in payload["rows"]] == SILVER_CREEK_ROWS


# ═══════════════════════════════════════════════════════════════════════════
# THE 2026-08-19 RULINGS — five changes the PO made after seeing the built
# screen, each proved here rather than in the CR record alone.
#
# RED, quoted, for the first of them: before `panel_service_codes` existed,
#   TypeError: service_mix_data() got an unexpected keyword argument
#   'configured_services'
# and with the old constant still in place a broadband-and-water tenant drew
#   ['electric', 'water', 'sewer', 'trash', 'gas']
# — five rows, three of them permanently empty, and its own two services in the
# remainder footnote. That output is the defect this section exists to forbid.
# ═══════════════════════════════════════════════════════════════════════════
def test_cr012_r1__a_broadband_and_water_utility_sees_broadband_and_water():
    """PO 2026-08-19, decision 1: *"draw the tenant's own configured services —
    always all of them"*.

    The utility that motivated the ruling: it sells **broadband and water**. Under
    the hard-coded five it met Electric, Sewer, Trash and Gas — four rows it will
    never fill — while its broadband revenue sat in "remainder". It now meets two
    rows, both its own, and NOTHING is in the remainder.
    """
    payload = regions.service_mix_data(
        [
            SimpleNamespace(service_code="broadband", total_billed=Decimal("81000")),
            SimpleNamespace(service_code="water", total_billed=Decimal("27000")),
        ],
        configured_services=("broadband", "water"),
        currency="USD",
        number_format="1,234.56",
    )
    assert [row["service_code"] for row in payload["rows"]] == ["water", "broadband"], (
        "seed order (BR-RAT-024) puts water second and broadband eighth, so water leads"
    )
    assert payload["remainder"] is None, "no revenue is homeless once the rows are the tenant's"
    by_code = {row["service_code"]: row for row in payload["rows"]}
    assert by_code["broadband"]["bar_pct"] == 100
    assert by_code["water"]["bar_pct"] == 33


def test_cr012_r1b__all_ten_platform_services_draw_in_the_seed_order():
    """*"always all of them, in the platform's fixed seed order"* — BR-RAT-024's
    ten, and the order is the SEED's (Gas third), not the old constant's."""
    codes = regions.panel_service_codes(
        # deliberately shuffled: the tenant's answer is a SET, the order is ours
        ("battery", "electric", "thermal_heat", "gas", "solar", "water", "storm_water",
         "broadband", "trash", "sewer")
    )
    assert codes == (
        "electric",
        "water",
        "gas",
        "sewer",
        "trash",
        "storm_water",
        "solar",
        "broadband",
        "thermal_heat",
        "battery",
    )


def test_cr012_r1c__a_configured_service_that_billed_nothing_is_an_em_dash_never_a_zero():
    """The half of BR-REP-025 the ruling did NOT change, re-proved against the new
    row set: a configured-but-unbilled service draws an em-dash and a zero-width
    bar. `$0.00` says "we sold none of this"; the em-dash says "nothing here"."""
    payload = regions.service_mix_data(
        [SimpleNamespace(service_code="water", total_billed=Decimal("500"))],
        configured_services=("water", "solar", "battery"),
        currency="USD",
        number_format="1,234.56",
    )
    by_code = {row["service_code"]: row for row in payload["rows"]}
    assert set(by_code) == {"water", "solar", "battery"}
    for code in ("solar", "battery"):
        assert by_code[code]["display"] == fmt.EM_DASH
        assert by_code[code]["display"] != "$0.00"
        assert by_code[code]["bar_pct"] == 0
        assert by_code[code]["share_display"] is None


def test_cr012_r1d__revenue_naming_no_service_still_has_nowhere_but_the_remainder():
    """⚠ THE REMAINDER SURVIVES THE RULING. A late fee is charged to an ACCOUNT
    and names no service, so however complete the row list is there is no row it
    belongs in. Folding it into a service row is a wrong figure; dropping it makes
    the panel foot to LESS than the period's revenue."""
    payload = regions.service_mix_data(
        [
            SimpleNamespace(service_code="water", total_billed=Decimal("900")),
            SimpleNamespace(service_code=None, total_billed=Decimal("42.50")),
            # billed earlier in the period, switched off since — still not ours to drop
            SimpleNamespace(service_code="gas", total_billed=Decimal("7.50")),
        ],
        configured_services=("water",),
        currency="USD",
        number_format="1,234.56",
    )
    assert [row["service_code"] for row in payload["rows"]] == ["water"]
    assert payload["remainder"]["amount"] == "50.000000"
    assert payload["remainder"]["services"] == 2
    water = payload["rows"][0]
    assert water["amount"] == "900.000000", "the late fee is NOT folded into water"


def test_cr012_r1e__tenancy_unable_to_answer_lists_what_billed_and_names_the_gap():
    """`None` is not `()`. Tenancy could not say which services this utility
    sells, so the panel draws the ones that BILLED — every figure still appears
    and the panel still foots — and reports the gap by name. **The old five are
    not substituted**: they are the wrong list for most utilities."""
    payload = regions.service_mix_data(
        [
            SimpleNamespace(service_code="solar", total_billed=Decimal("120")),
            SimpleNamespace(service_code="water", total_billed=Decimal("300")),
        ],
        configured_services=None,
        currency="USD",
        number_format="1,234.56",
    )
    assert [row["service_code"] for row in payload["rows"]] == ["water", "solar"]
    assert [gap["code"] for gap in payload["unavailable"]] == [
        "configured_services_are_not_published_by_tenancy"
    ]
    assert "trash" not in [row["service_code"] for row in payload["rows"]]


def test_cr012_r1f__a_tenant_with_no_service_enabled_draws_no_row_rather_than_five():
    """`()` is an ANSWER — "this utility has enabled nothing" — and it is not
    turned back into the old five. A row list nobody configured is an invention.

    This is now the ONLY case that reaches the empty state (see the next case)."""
    payload = regions.service_mix_data(
        [], configured_services=(), currency="USD", number_format="1,234.56"
    )
    assert payload["rows"] == []
    assert payload["state"] == "empty"


def test_cr012_r1g__a_month_with_nothing_billed_still_shows_the_utility_its_services():
    """⚠ *"ALWAYS all of them"* — INCLUDING on the first of the month.

    RED, quoted, and found by driving the built stack in a browser rather than
    by any gate: on a freshly seeded tenant the panel rendered *"Nothing was
    billed in this period, so there is no service mix to show."* and the two
    rows the ruling had just put into the payload were on the wire and on no
    screen. `state` was `"ok" if billed_anything or remainder else "empty"`,
    which was defensible while the rows were a hard-coded five that said nothing
    about the reader's own utility, and is not defensible now.

    Each row is still the em-dash and the zero-width bar the requirement asks
    for, so the panel says "nothing here yet" per service, where a reader is
    already looking. `$0.00` still never appears.
    """
    payload = regions.service_mix_data(
        [],
        configured_services=("electric", "water"),
        currency="USD",
        number_format="1,234.56",
    )
    assert payload["state"] == "ok"
    assert [row["service_code"] for row in payload["rows"]] == ["electric", "water"]
    for row in payload["rows"]:
        assert row["display"] == fmt.EM_DASH
        assert row["display"] != "$0.00"
        assert row["bar_pct"] == 0


def test_cr012_r3__a_todo_row_the_owner_cannot_size_shows_no_number_ever():
    """PO 2026-08-19, decision 3: *"Show 'Review billing exceptions' with no
    number"*. A `0` tells the operator nothing needs their attention, which is
    FALSE when the owner simply could not answer.

    ⚠ **DEF-304 lives in this case.** `seams.open_finance_close()` publishes a
    DICT naming the period a close is outstanding for, and `todo_rows` used to
    call `int()` on it — so the day the ledger lands that read, the whole To-do
    region would have failed into its error state. A finance close is inherently
    a countless task: the row is the label alone.
    """
    rows = regions.todo_rows(
        billing_exceptions=3,
        onboarding=[],
        rate_approvals=None,
        disconnect_eligible=None,
        finance_close={"period": "2026-07", "status": "open"},
        number_format="1,234.56",
    )
    by_code = {row["code"]: row for row in rows}
    assert by_code["finance_close"]["count"] is None
    assert by_code["finance_close"]["count_display"] is None, (
        "a display string beside a null count is exactly how a zero gets back on screen"
    )
    assert by_code["billing_exceptions"]["count"] == 3
    for row in rows:
        assert row["count"] != 0
        if row["count"] is None:
            assert row["count_display"] is None


def test_cr012_r3b__an_owner_that_counted_zero_still_adds_no_row_at_all():
    """The two absences stay apart. `0` means the owner COUNTED and found
    nothing — no row. `None` on an emitted row means the owner could not count —
    a row with no number. Collapsing them is how the false zero returns."""
    assert (
        regions.todo_rows(
            billing_exceptions=0,
            onboarding=[],
            rate_approvals=0,
            disconnect_eligible=0,
            finance_close=None,
            number_format="1,234.56",
        )
        == []
    )


def test_cr012_r6__the_activity_panel_publishes_the_window_it_read():
    """PO 2026-08-19: *"yes it shoudl state the window"*. *"Nothing has happened
    here yet"* means something very different at 24 hours than at forever, and on
    a utility's first Monday the difference is the whole message."""
    assert regions.ACTIVITY_WINDOW_HOURS == regions.ACTIVITY_WINDOW_DAYS * 24
    assert regions.ACTIVITY_WINDOW_HOURS == 24


# ═══════════════════════════════════════════════════════════════════════════
# BR-REP-027 — THE CYCLE STATUS LINE'S FOUR STATES (TC-14)
#
# RED, quoted: before `cycle_status_data` existed —
#   AttributeError: module 'apps.reports.dashboard_regions' has no attribute
#   'cycle_status_data'
# and the first implementation returned `closes_in` with `days=-2` for a cycle
# whose window had already shut:
#   AssertionError: assert 'closes_in' == 'closed_pending_run'
# ═══════════════════════════════════════════════════════════════════════════
def a_cycle(code, *, next_cycle_date, accounts, status="active"):
    """One row of what `cycles_list` publishes, as the region reads it.

    ⚠ **THE KEY IS `next_cycle_date` NOW, AND IT USED TO BE `read_day_to` +
    `bill_day` (CR-029 D8② then W5-T2).** The PO ruled which date the countdown
    counts to — verbatim, *"② which date 'closes in 4 days' counts to - Next
    cycle date"* — and W5-T2 dropped the day-of-month column the old derivation
    used. The region asks metering for the date rather than computing one from
    two defaults, so the dashboard and SET-07D's Schedule card cannot disagree
    about the same cycle.
    """
    return {
        "code": code,
        "name": None,
        "next_cycle_date": next_cycle_date,
        "accounts": accounts,
        "lifecycle_status": status,
    }


@pytest.mark.parametrize(
    "as_of,expected_state,expected_days",
    [
        (date(2026, 8, 2), "closes_in", 4),
        (date(2026, 8, 6), "closes_today", 0),
    ],
)
def test_cr012_tc14__the_cycle_states_that_survive_d8(as_of, expected_state, expected_days):
    """r10's own line, driven by `as_of` and never by a clock (BR-TEN-043).

    A cycle whose next date is **6 Aug**: *closes in 4 days* on Aug 2, *closes
    today* on Aug 6.

    ⚠ **THIS WAS `test_..._the_four_cycle_states` AND TWO OF THE FOUR ARE GONE.
    BR-REP-027 NEEDS AMENDING AND THAT IS REPORTED, NOT DECIDED HERE.**

      · `closed_pending_run` was *"the read window has shut and the cycle's bill
        day has not arrived"* — derived ENTIRELY from `read_day_to` + `bill_day`,
        and its own gap note already recorded that it could not say whether a
        run had actually happened because billing publishes no per-cycle run
        read. `read_day_to` is dropped (metering 0021), so the state is
        unreachable. The constant and `GAP_CYCLE_RUN_NOT_PUBLISHED` are kept
        unrendered and name the read that would restore it honestly
        (`apps.billing.selectors.last_run_for_cycle`).
      · the fourth case here — *"past the bill day → next month"*, 25 days —
        was the same derivation rolling into the following month. The period
        engine answers the next occurrence directly now, so there is nothing to
        roll.

    Two states remain live (`closes_in`, `closes_today`) plus `not_configured`,
    which the two cases below still cover.
    """
    data = regions.cycle_status_data(
        [a_cycle("08-A", next_cycle_date="2026-08-06", accounts=842)], as_of=as_of
    )
    assert data["state"] == expected_state
    assert data["cycle_code"] == "08-A"
    if expected_days is not None:
        assert data["days"] == expected_days


def test_cr012_tc14b__a_tie_is_broken_by_account_count_and_a_draft_is_never_named():
    """*"tie broken by account count"* (PO verbatim) — the bigger cycle is the
    one a one-person utility means. A DRAFT cycle stamps no service point
    (BR-MET-076) and is never named."""
    data = regions.cycle_status_data(
        [
            a_cycle("08-B", next_cycle_date="2026-08-06", accounts=405),
            a_cycle("08-A", next_cycle_date="2026-08-06", accounts=842),
            a_cycle("08-Z", next_cycle_date="2026-08-03", accounts=9999, status="draft"),
        ],
        as_of=date(2026, 8, 2),
    )
    assert data["cycle_code"] == "08-A", "the tie goes to the cycle with more accounts"


def test_cr012_tc14c__no_active_cycle_states_the_fact_and_offers_no_link():
    """The fourth state. A countdown to a cycle that does not exist is the one
    thing worse than no countdown."""
    data = regions.cycle_status_data([], as_of=date(2026, 8, 2))
    assert data["state"] == "not_configured"
    assert data["cycle_code"] is None
    assert data["days"] is None
    assert "settings_target" not in data, (
        "PO 2026-08-19, decision 5 — *'no provide any link'*. The line reflects the "
        "configured state; cycle set-up lives in Settings -> Routes & Cycles (CR-006), "
        "which is in the sidebar on every screen. A served target nothing renders is "
        "dead payload (hard-won law 2)."
    )


def test_cr012_tc14d__a_cycle_that_does_not_say_when_it_closes_is_not_named():
    """A cycle the period engine cannot resolve — most often one with no
    first-run date to anchor from, or one sitting on an unruled month-end
    (OQ-339) — publishes no `next_cycle_date`. It cannot say when it closes, so
    it is not chosen and the line falls back to `not_configured` rather than
    inventing a day.

    W5-T2 removed the transitional day-of-month fallback that used to catch this
    case, so the remedy for such a tenant is a first-run date on the cycle — a
    field the wizard asks for — rather than a date this file derives.
    """
    data = regions.cycle_status_data(
        [a_cycle("OLD", next_cycle_date=None, accounts=50)], as_of=date(2026, 8, 2)
    )
    assert data["state"] == "not_configured"


# ═══════════════════════════════════════════════════════════════════════════
# BR-REP-034 — THE MTD-REVENUE SUB-LINE (TC-23 / TC-24)
#
# RED, quoted: with the seam dark the first implementation still rendered a
# sub-line reading `86% of $0 target` —
#   AssertionError: assert {'text': '86% of $0 target'} is None
# which is the exact failure the PO's ruling forbids: a wrong denominator on the
# first screen after sign-in.
# ═══════════════════════════════════════════════════════════════════════════
def test_cr012_tc24__with_no_target_typed_the_tile_is_the_figure_alone(brazos, dana):
    """**The default state for every tenant on this deployment, proved FIRST.**

    PO ruling 2026-08-18: *"With no target typed, the tile degrades to option A
    — the figure alone, no sub-line"*. No percentage, no bar, no delta, and
    nothing derived from last month or last year anywhere in the payload.
    """
    with tenant_ctx(brazos):
        a_july(brazos, dana)
    payload = summary(brazos)
    tile = next(
        t for t in payload["regions"]["kpi_band"]["data"]["tiles"] if t["id"] == "mtd-revenue"
    )
    assert tile["display"] is not None, "the FIGURE still shows — only the comparison is withheld"
    assert tile["sub"] is None, "no sub-line, no percentage, no delta, no bar"
    assert "%" not in str(tile)


def test_cr012_tc23__a_typed_target_reads_86_percent_of_400000(brazos, dana, monkeypatch):
    """The PO's own worked figure: **342,700 ÷ 400,000 = 85.675% → `86%`**.

    Rounded half-up to a WHOLE number, the same rounding BR-REP-026 applies to
    the bars, so no two numbers on this screen round differently.
    """
    with tenant_ctx(brazos):
        a_july(brazos, dana)
    monkeypatch.setattr(seams, "monthly_revenue_target", lambda: Decimal("400000"))
    sub = regions.revenue_target_sub(
        Decimal("342700"), target=Decimal("400000"), currency="USD", number_format="1,234.56"
    )
    assert sub == {
        "percent": 86,
        "percent_display": "86%",
        "target": "400000.000000",
        "target_display": "$400,000.00",
    }


def test_cr012_tc23b__a_zero_or_absent_target_yields_no_sub_line():
    """A target of zero is not a target. No division is performed on it."""
    assert (
        regions.revenue_target_sub(
            Decimal("342700"), target=Decimal("0"), currency="USD", number_format="1,234.56"
        )
        is None
    )
    assert (
        regions.revenue_target_sub(
            Decimal("342700"), target=None, currency="USD", number_format="1,234.56"
        )
        is None
    )
    assert (
        regions.revenue_target_sub(
            None, target=Decimal("400000"), currency="USD", number_format="1,234.56"
        )
        is None
    ), "no billed figure ⇒ nothing to compare; the tile refuses rather than reading 0%"


# ═══════════════════════════════════════════════════════════════════════════
# BR-REP-030 — AR AGING (TC-18 / TC-19)
#
# RED, quoted: the panel first served the ledger's four-band collapse —
#   AssertionError: assert ['current', '31-60', '61-90', '90+'] == ['current',
#   '1-30', '31-60', '61-90', '90+']
# ═══════════════════════════════════════════════════════════════════════════
class FakeAgeing:
    """`payments.outstandings.OutstandingsView`'s published shape, exactly.

    Written out rather than mocked loosely, because the ENTIRE point of reading
    that view is that its buckets come from the oldest unpaid bill's DUE DATE
    and not from `payment_plans.status` — which is what makes BR-REP-030's
    arrangement rule true without this module doing anything.
    """

    def __init__(self, ageing, total):
        self._ageing = ageing
        self.total_owed = total

    def ageing(self):
        return self._ageing


def test_cr012_tc18__five_buckets_with_a_rounded_share_that_need_not_total_100():
    """*"rounded, need not total 100%"* (PO verbatim) — no fudge row."""
    view = FakeAgeing(
        [
            {"bucket": "current", "amount": "118240.0000", "accounts": 982, "share": "64.1"},
            {"bucket": "1-30", "amount": "34120.0000", "accounts": 146, "share": "18.5"},
            {"bucket": "31-60", "amount": "18540.0000", "accounts": 62, "share": "10.1"},
            {"bucket": "61-90", "amount": "8210.0000", "accounts": 28, "share": "4.5"},
            {"bucket": "90+", "amount": "5210.0000", "accounts": 18, "share": "2.8"},
        ],
        Decimal("184320"),
    )
    data = regions.aging_data(view, currency="USD", number_format="1,234.56")
    assert [row["bucket"] for row in data["rows"]] == [
        "current",
        "1-30",
        "31-60",
        "61-90",
        "90+",
    ]
    assert data["rows"][0]["amount_display"] == "$118,240.00"
    assert data["rows"][0]["accounts_display"] == "982"
    assert [row["share_display"] for row in data["rows"]] == ["64%", "19%", "10%", "5%", "3%"]
    assert sum(row["share"] for row in data["rows"]) == 101, (
        "the rounded shares sum to 101 and that is CORRECT — a balancing row would "
        "be a fudge and the PO ruled it out by name"
    )
    # r10 puts its danger emphasis on the OLDEST bucket alone.
    assert [row["emphasis"] for row in data["rows"]] == [None, None, None, None, "danger"]
    assert data["total_display"] == "$184,320.00"


def test_cr012_tc19__an_arrangement_account_stays_in_its_true_bucket():
    """**The money rule, and the naive implementation does the opposite.**

    This module NEVER re-buckets, and that is what the test asserts: whatever
    `payments.outstandings` says a bucket holds is what renders. An account 45
    days late on an active payment plan is in `31-60` there — because that view
    buckets on the oldest unpaid bill's due date and reads `plan_status` only as
    a column — and it is still in `31-60` here.
    """
    view = FakeAgeing(
        [
            {"bucket": "current", "amount": "0.0000", "accounts": 0, "share": None},
            {"bucket": "1-30", "amount": "0.0000", "accounts": 0, "share": None},
            {"bucket": "31-60", "amount": "480.0000", "accounts": 1, "share": "100.0"},
            {"bucket": "61-90", "amount": "0.0000", "accounts": 0, "share": None},
            {"bucket": "90+", "amount": "0.0000", "accounts": 0, "share": None},
        ],
        Decimal("480"),
    )
    data = regions.aging_data(view, currency="USD", number_format="1,234.56")
    by_bucket = {row["bucket"]: row for row in data["rows"]}
    assert by_bucket["31-60"]["accounts"] == 1
    assert (
        by_bucket["current"]["accounts"] == 0
    ), "an account on an active arrangement counts in its TRUE bucket, not Current"
    # And nothing in this module recomputes a share from the amounts.
    assert by_bucket["31-60"]["share"] == 100


# ═══════════════════════════════════════════════════════════════════════════
# BR-REP-031 — RECENT ACTIVITY (TC-20)
# ═══════════════════════════════════════════════════════════════════════════
def test_cr012_tc20__only_operator_relevant_actions_reach_the_feed():
    """*"filtered to operator-relevant types"* — the six classes the PO named.

    A settings edit, a user administration event and a sign-in are not operator
    WORK. They are in the audit log, they belong on S61, and putting them on the
    first screen after sign-in would bury the bill run under the login that
    reached it.
    """
    assert regions.is_operator_relevant("bill_run.released")
    assert regions.is_operator_relevant("payment.recorded")
    assert regions.is_operator_relevant("read_batch.posted")
    assert regions.is_operator_relevant("correction.executed")
    assert regions.is_operator_relevant("notice.sent")
    assert regions.is_operator_relevant("account.created")
    for noise in (
        "settings.billing_defaults.updated",
        "auth.sign_in",
        "user.owner_provisioned",
        "security.attempt_refused",
    ):
        assert not regions.is_operator_relevant(noise), f"{noise} is not operator work"


def test_cr012_tc20b__a_role_never_sees_an_event_from_a_module_it_cannot_read():
    """*"events the role can't see in their own module are excluded"*.

    A4's addendum: the Billing Clerk has NO Finance access (`—` on the
    Finance/reconcile/export row), so a journal posting never reaches their
    feed even if a later lane allowlists it. The System Admin and the Executive
    both read Finance and both see it.
    """
    assert not regions.role_may_see("journal.posted", "billing_clerk")
    assert regions.role_may_see("journal.posted", "system_admin")
    assert regions.role_may_see("journal.posted", "executive")
    assert regions.role_may_see("payment.recorded", "billing_clerk")
    # An unknown role is trusted with nothing it has not been granted.
    assert not regions.role_may_see("journal.posted", "some_future_role")


def test_cr012_tc20c__the_window_is_24_hours_of_as_of_and_the_cap_is_six():
    """Six rows, newest first, none older than 24h — and `as_of` is an ARGUMENT,
    never a clock (BR-TEN-043), which is the only way a test can pin it."""
    as_of = date(2026, 8, 18)
    assert regions.activity_window(as_of) == (
        date(2026, 8, 17),
        as_of,
    ), "24 hours back from the as-of day"
    rows = [
        {"created_at": f"2026-08-18T0{n}:00:00+00:00", "action": "payment.recorded"}
        for n in range(9)
    ]
    assert len(regions.activity_rows(rows, currency="USD", number_format="1,234.56")) == 6


def test_cr012_tc20d__an_activity_row_carries_an_em_dash_and_never_a_derived_amount():
    """`audit_log` has no money column (`apps/audit/models.py`). Reading an
    amount out of a stored before/after diff would make this screen a second
    opinion on money — BR-REP-024's whole subject."""
    rows = regions.activity_rows(
        [{"created_at": "2026-08-18T08:42:00+00:00", "action": "payment.recorded"}],
        currency="USD",
        number_format="1,234.56",
    )
    assert rows[0]["amount"] is None
    assert rows[0]["amount_display"] == fmt.EM_DASH


# ═══════════════════════════════════════════════════════════════════════════
# BR-REP-028 — REGIONS FAIL INDEPENDENTLY (TC-15)
#
# **THE ACCEPTANCE CRITERION MOST LIKELY TO BE FAKED.** Asserting that the page
# renders when every seam answers proves nothing at all about "one section
# failing must not blank the page". So this makes a region fail ON PURPOSE.
#
# RED, quoted: before the per-region boundary existed the whole request died —
#   RuntimeError: the ledger is on fire
# raised straight out of `dashboard_summary`, i.e. a blank page, which is the
# acceptance criterion inverted.
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    "seam_name,broken_region",
    [
        ("revenue_and_ar", "service_mix"),
        ("cycles_list", "cycle_status"),
        ("outstandings", "aging"),
        ("audit_recent", "activity"),
        ("invoices_rollup", "todo"),
    ],
)
def test_cr012_tc15__one_region_failing_never_blanks_the_page(
    brazos, dana, monkeypatch, seam_name, broken_region
):
    """Break ONE seam and the other five still answer, with the page head intact.

    Each parameter is a different region's own owner, so this is five separate
    proofs rather than one boundary tested five times.
    """
    with tenant_ctx(brazos):
        a_july(brazos, dana)

    def boom(*args, **kwargs):
        raise RuntimeError(f"{seam_name} is on fire")

    monkeypatch.setattr(seams, seam_name, boom)
    payload = summary(brazos)

    broken = payload["regions"][broken_region]
    assert broken["state"] == "error", f"{broken_region} must report its own failure"
    assert broken["error"]["code"] == "region_read_failed"
    assert broken["data"] is None
    # …and the page is still a page.
    assert payload["basis"] == "posting"
    assert payload["as_of"] is not None
    healthy = [name for name, region in payload["regions"].items() if region["state"] != "error"]
    assert len(healthy) >= 4, f"only {healthy} survived — a failing region blanked the page"


def test_cr012_tc15b__the_failure_never_leaks_the_exception_text_to_a_clerk():
    """BR-SHL-020 — plain language, keyed on a stable code. A billing clerk must
    never read `RuntimeError: relation "journal_lines" does not exist`."""
    region = regions.guard("service_mix", lambda: (_ for _ in ()).throw(RuntimeError("relation x")))
    assert region["state"] == "error"
    assert "relation x" not in str(region)
    assert region["error"]["region"] == "service_mix"


# ═══════════════════════════════════════════════════════════════════════════
# BR-REP-033 — ROLE GATING AND THE NO-MUTATION CLAIM (TC-22)
# ═══════════════════════════════════════════════════════════════════════════
def test_cr012_tc22__the_two_page_actions_are_refused_for_a_view_only_role(brazos, dana):
    """*"Both hidden for read-only roles"* (PO verbatim).

    A4's addendum makes the Executive view-only on Reads & Billing runs, so the
    SERVER says so and the screen hides them. The decision is the server's
    because a hidden control that the API would have accepted is not a
    permission, it is a suggestion.
    """
    with tenant_ctx(brazos):
        a_july(brazos, dana)
    for role, allowed in (("system_admin", True), ("billing_clerk", True), ("executive", False)):
        payload = summary(brazos, role=role)
        actions = payload["page_actions"]
        assert actions["import_reads"] is allowed, role
        assert actions["run_billing"] is allowed, role


def test_cr012_tc22b__no_kpi_tile_carries_a_navigation_target(brazos, dana):
    """*"KPI cells do not navigate in v1"* — asserted on the payload so a screen
    cannot quietly add one back."""
    with tenant_ctx(brazos):
        a_july(brazos, dana)
    for tile in summary(brazos)["regions"]["kpi_band"]["data"]["tiles"]:
        assert "target" not in tile and "href" not in tile


# ═══════════════════════════════════════════════════════════════════════════
# THE ENDPOINT — `asOf` added, the route NOT renamed (contract decision)
# ═══════════════════════════════════════════════════════════════════════════
def test_cr012__the_route_is_still_a11s_own_s7_row_and_takes_an_as_of(brazos, dana):
    """The PO's spec names `GET /api/dashboard?tenantId&asOf`; A11's S7 row
    contracts `GET /dashboard/summary` and that is a SIGNED interface, so the
    route is unchanged and gained `asOf` only. **The tenant is never a query
    parameter** (hard rule 1) — it comes from the request context."""
    from django.urls import resolve

    with tenant_ctx(brazos):
        a_july(brazos, dana)
    assert (
        resolve(f"/api/{brazos.subdomain}/dashboard/summary").func is reports_api.dashboard_summary
    )
    response = api_call(
        reports_api.dashboard_summary,
        "get",
        user=FakeUser(),
        role="billing_clerk",
        tenant=brazos,
        query={"asOf": "2026-07-31"},
    )
    assert response.status_code == 200
    assert response.data["as_of"] == "2026-07-31"


def test_cr012__a_malformed_as_of_falls_back_and_never_500s(brazos, dana):
    """BR-SHL-011: an undeclared or impossible parameter falls back rather than
    refusing. A landing page that 500s on a hand-edited URL is a locked door."""
    with tenant_ctx(brazos):
        a_july(brazos, dana)
    response = api_call(
        reports_api.dashboard_summary,
        "get",
        user=FakeUser(),
        role="billing_clerk",
        tenant=brazos,
        query={"asOf": "not-a-date"},
    )
    assert response.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# TC-16 — A BRAND-NEW TENANT. Every region empty, and not one zero anywhere.
# ═══════════════════════════════════════════════════════════════════════════
def test_cr012_tc16__a_new_tenant_shows_no_history_and_never_a_zero(brazos):
    """*"New tenants show `—` KPIs with 'No billing history yet' and remaining
    onboarding steps in To do."*

    No book has been posted on this tenant, so the money regions are empty. The
    assertion that matters is the negative one: an empty month must not render
    as `$0.00`, which reads as *"we billed nothing and we are sure"*.
    """
    fiscal_calendar(brazos)
    payload = summary(brazos, as_of=date(2026, 7, 31))
    assert payload["regions"]["service_mix"]["state"] in ("empty", "ok")
    for row in payload["regions"]["service_mix"]["data"]["rows"]:
        assert row["display"] == fmt.EM_DASH
        assert row["bar_pct"] == 0
    todo = payload["regions"]["todo"]["data"]["rows"]
    assert any(
        row["kind"] == "onboarding" for row in todo
    ), "the remaining onboarding steps are the new tenant's To do"
    assert len(todo) <= 4, "BR-REP-032: max four"


# ═══════════════════════════════════════════════════════════════════════════
# TC-21 — TO DO
# ═══════════════════════════════════════════════════════════════════════════
def test_cr012_tc21__todo_is_capped_at_four_and_an_owner_with_nothing_adds_no_row():
    """BR-REP-032: an item whose owner publishes nothing is not rendered at all
    rather than rendered empty — a to-do row saying "0 billing exceptions" is a
    task that does not exist."""
    rows = regions.todo_rows(
        billing_exceptions=3,
        onboarding=[{"item": "rates_taxes", "target": "plans-rates"}],
        rate_approvals=None,
        disconnect_eligible=None,
        finance_close=None,
        number_format="1,234.56",
    )
    assert len(rows) <= 4
    kinds = [row["kind"] for row in rows]
    assert "action" in kinds, "billing exceptions are the `action` kind"
    assert all(row.get("count") != 0 for row in rows)
    assert (
        regions.todo_rows(
            billing_exceptions=0,
            onboarding=[],
            rate_approvals=None,
            disconnect_eligible=None,
            finance_close=None,
            number_format="1,234.56",
        )
        == []
    )


# ═══════════════════════════════════════════════════════════════════════════
# ISOLATION — hard rule 1
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.isolation
def test_cr012__another_tenants_figures_never_reach_this_screen(brazos, lonestar, dana):
    """RLS FORCE. Brazos Bend's book is posted; Lone Star Ridge's dashboard must
    show its own nothing rather than someone else's something."""
    with tenant_ctx(brazos):
        a_july(brazos, dana)
    fiscal_calendar(lonestar)
    payload = summary(lonestar)
    for row in payload["regions"]["service_mix"]["data"]["rows"]:
        assert row["amount"] is None or Decimal(row["amount"]) == 0


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-012 (12-governance/11-change-requests.md §CR-012 — the screenshot enumerated, r10's markup quoted, the PO's build spec and the FULL DSH-01 requirements, all verbatim; plus §"THE BAR RULE, WORKED") · 04-docs/05-modules/12-reports/02-business-rules.md BR-REP-024..034 · 04-docs/05-modules/12-reports/06-epics/EP-REP-05-dashboards.md §US-REP-019 AMENDMENT TC-11..TC-24 · 12-governance/02-decision-log.md 2026-08-18 (two rulings) · 04-docs/01-spec/01-screen-inventory.md S7
# screens: S7
# generated: 2026-08-18 by story-coder (CR-012 DSH-01 lane)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST for every behaviour — the module-level ImportError, then per-case failures quoted in the section headers above (bars 70/22/8 instead of 100/32/12 · a four-band aging collapse · `closes_in` with days=-2 · `86% of $0 target` on a dark target seam · a RuntimeError escaping the whole request).
# exceptions: (1) the aging and activity cases drive PUBLISHED shapes through fakes rather than posting a book, because what is under test is this module's REFUSAL to re-bucket and re-total, and a real book would prove the owner's arithmetic instead of ours · (2) TC-23's typed target is monkeypatched onto the seam: the Settings FIELD is `apps/tenancy`'s to add and is outside this lane's territory, which is REPORTED — the untyped state (TC-24) is the one every tenant is actually in and is proved against the real stack
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
