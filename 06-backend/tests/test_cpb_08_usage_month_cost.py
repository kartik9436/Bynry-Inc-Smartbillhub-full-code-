# ── Trace ──────────────────────────────────────────────
# Change:   CR-085 blueprint specification CPB-08 — *"A usage month says what it
#           cost"*. Screens 50 · 32. Done is *"The Usage screen reads '800 kWh at
#           $0.1150 = $92.00' for August, and the figure is the bill's own line,
#           not a re-calculation."* The blueprint names the gap in five words:
#           *"Nothing joins a usage month to the bill line it produced."*
# Rules:    CLAUDE.md hard rule 2 (money stored 4 / displayed 2; a RATE shows
#           FOUR — PO 2026-08-27, *"A rate is not money and not a quantity - 4
#           decimal places"*) · hard rule 3 (the quantity carries its unit) ·
#           B4 ❄️ FROZEN (nothing here prices anything) · B14 rule 31 (the bill
#           NUMBER, never an invoice id)
# ⚠ NOTHING IS PRICED HERE. Every figure is read off an ISSUED bill's own stored
#   line. That is the specification's own requirement — *"not a re-calculation"*
#   — and it is also what keeps this off B4's frozen ground entirely.
# ───────────────────────────────────────────────────────
"""What a month of usage actually cost, from the paper the customer holds."""

from __future__ import annotations

from datetime import date

from apps.portal.seams import billing_seam


def test_cpb08_tc1__a_month_is_joined_to_the_bill_that_covers_its_LAST_day():
    """A usage month is complete on its last day, so that is the day matched
    against a bill's service period — the same period match `CWP-034` already
    uses for a reading, one level up.

    ⚠ **THE LAST DAY AND NOT THE FIRST.** A bill issued mid-month covers the
    start of August and not its end; joining on 1 August would attach August's
    usage to a bill that stopped before most of it happened.
    """
    assert billing_seam.month_end("2026-08") == date(2026, 8, 31)
    assert billing_seam.month_end("2026-02") == date(2026, 2, 28)
    # A leap year is arithmetic nobody should be doing by hand.
    assert billing_seam.month_end("2024-02") == date(2024, 2, 29)
    assert billing_seam.month_end("2026-12") == date(2026, 12, 31)


def test_cpb08_tc2__a_malformed_month_answers_None_rather_than_raising():
    """The month key comes off a payload; a read model that raised on one would
    take a whole screen down for a cell."""
    assert billing_seam.month_end("nonsense") is None
    assert billing_seam.month_end("") is None


#: ⚠ **THE REAL SHAPE OF A BILL LINE, COPIED OFF ONE.** These are Ana's own
#: July electric lines from the `pine-hill` demo, printed out of
#: `billing_seam.bill_detail_for`. The first version of this file INVENTED a
#: shape — `quantity_display`, one line, a `service_code` group key — and every
#: case passed against it while the join answered `None` on every account in the
#: product. **A fixture you wrote yourself proves your code agrees with you.**
TIER_1 = {
    "description": "electric usage tier 1 (0-500 kWh)",
    "quantity": "500",
    "unit": "kWh",
    "rate": "0.1100",
    "rate_basis": "per_unit",
    "rate_percent": None,
    "amount": "55.000000",
    "amount_display": "55.00",
    "kind": "usage",
}
TIER_2 = {
    **TIER_1,
    "description": "electric usage tier 2 (500-1000 kWh)",
    "quantity": "300",
    "rate": "0.1350",
    "amount": "40.500000",
    "amount_display": "40.50",
}


def test_cpb08_tc3__a_TIERED_month_serves_every_line_and_the_bills_own_total():
    """⚠ **THE BLUEPRINT DRAWS ONE LINE AND THE PRODUCT BILLS TWO.**

    Ana's July electric is `500 kWh at $0.1100 = $55.00` **and** `300 kWh at
    $0.1350 = $40.50` — a tiered tariff, which is what most utilities actually
    charge. Serving only the first would show a customer `$55.00` for a month
    that cost `$95.50` and call it an explanation.

    The total is the sum of the lines' own STORED 2 dp amounts — the same
    figures the printed column foots to — so the panel foots against the paper
    by construction. Nothing is multiplied.
    """
    view = billing_seam.usage_cost_view(
        [TIER_1, TIER_2], month="2026-07", bill_number="BL-2608-000052"
    )
    assert view is not None
    assert view["total_display"] == "95.50"
    assert view["unit"] == "kWh"
    assert [line["quantity"] for line in view["lines"]] == ["500", "300"]
    assert [line["rate"] for line in view["lines"]] == ["0.1100", "0.1350"]
    assert [line["amount_display"] for line in view["lines"]] == ["55.00", "40.50"]
    assert view["bill_number"] == "BL-2608-000052"


def test_cpb08_tc4__a_line_with_a_quantity_and_no_unit_is_dropped():
    """CLAUDE.md hard rule 3. `_quantity_of` already serves the pair or NEITHER,
    so this states the invariant rather than trusting it — a later lane may
    rewrite that read, and a bare `500` under a service heading means whatever
    the reader assumes."""
    view = billing_seam.usage_cost_view(
        [TIER_1, {**TIER_2, "unit": None}], month="2026-07", bill_number="BL-1"
    )
    assert view is not None
    assert len(view["lines"]) == 1
    # …and the total is of what SURVIVED, so the panel still foots to itself.
    assert view["total_display"] == "55.00"


def test_cpb08_tc5__no_lines_and_no_bill_are_both_ordinary_answers():
    """A month nobody has billed yet — Ana's August is one — states nothing
    rather than `$0.00`, which is a claim that the month was free."""
    assert billing_seam.usage_cost_view([], month="2026-08", bill_number="BL-1") is None
    assert billing_seam.usage_cost_view([TIER_1], month="2026-08", bill_number=None) is None


def test_cpb08_tc6__a_line_with_no_rate_still_says_what_it_cost():
    """A flat or minimum charge has an amount and no per-unit rate. *"800 kWh
    cost $92.00"* is still the answer to *why does it cost this*."""
    view = billing_seam.usage_cost_view(
        [{**TIER_1, "rate": None, "rate_basis": None}], month="2026-07", bill_number="BL-1"
    )
    assert view is not None
    assert view["lines"][0]["rate"] is None
    assert view["total_display"] == "55.00"


def test_cpb08_tc7__the_group_key_is_service_and_NOT_service_code():
    """⚠ **THE BUG THIS CASE EXISTS FOR.** `_grouped_lines` serves `service`,
    `service_name`, `lines` and `subtotal_display` — there is no `service_code`
    key on that shape. The first draft read `service_code`, matched nothing on
    every account in the product, and every unit test passed because none of
    them walked a real group. Found by running the join over live `pine-hill`
    data and watching it answer `None` where a bill plainly existed.

    This asserts the KEY NAME against the function that mints it, so a rename on
    either side goes red rather than silently answering nothing."""
    import inspect

    source = inspect.getsource(billing_seam.usage_cost_for_month)
    assert 'group.get("service")' in source
    # `service_code` is this function's own ARGUMENT and is compared against the
    # group's `service`; what must not appear is a READ of a `service_code` key
    # off the group, which is the shape that matched nothing.
    assert 'group.get("service_code")' not in source
    assert 'group["service_code"]' not in source
    minted = inspect.getsource(billing_seam._grouped_lines)
    assert '"service":' in minted
