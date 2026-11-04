# ── Trace ──────────────────────────────────────────────
# Rules:    BR-RAT-087 (PO ruling 2026-08-20: "store 4 decimal and display 2
#           decimal - amount and percetnage both") · B4 ❄️ (NUMERIC(18,6) —
#           untouched by this) · BR-RAT-003 (money rounding happens at
#           finalization, and this is NOT that)
# Defects:  DEF-364 (percent rendered as the raw stored fraction) ·
#           DEF-291 (one instance of it, caught on the Taxes screen)
# ───────────────────────────────────────────────────────
"""The display half of BR-RAT-087, asserted at the seam that produces it.

WHY THE SERVER AND NOT THE COMPONENT
------------------------------------
`ChargeCodesTab.tsx` and `TaxesFeesTab.tsx` each carry a note saying they render
the stored value because *"converting to 1.5 on screen would be client-side money
arithmetic on a value the server owns."* That is correct and it is B4's rule. The
half nobody built is its consequence — **if the client may not format, the server
must** — so a percent shipped as `0.015000` and a customer read `0.015000`.

Fixing this in React would have been faster and would have broken the rule the
comments were protecting. The tests below therefore assert the STRING THE SERVER
SENDS, which is the only place the fix can be correct.

WHAT THIS DELIBERATELY DOES NOT TOUCH
-------------------------------------
The stored six-place value. B4 is ❄️ FROZEN at `NUMERIC(18,6)` and the display
string sits BESIDE it, never instead of it — which is what keeps this change out
of HUMAN-GUIDE §6 entirely. Whether STORAGE should become four places is a
different question and is open as OQ-285.
"""

from decimal import Decimal

from apps.rating.selectors import _display_money, _display_percent


class TestPercentReadsAsAPercent:
    def test_the_def_364_case__one_and_a_half_percent(self):
        """`0.015` is what the column holds; `1.50%` is what a person reads."""
        assert _display_percent(Decimal("0.015")) == "1.50%"

    def test_the_def_291_case__the_tax_screen_said_0_062500(self):
        """DEF-291, verbatim: the Taxes & fees screen *"states a tax rate as the
        stored FRACTION — 0.062500 of the taxable base"*."""
        assert _display_percent(Decimal("0.062500")) == "6.25%"

    def test_a_rate_with_more_precision_than_two_places_rounds_half_up(self):
        """Half-up, matching B4.4's per-line rule so the two never disagree on a
        boundary a customer can see."""
        assert _display_percent(Decimal("0.012345")) == "1.23%"
        assert _display_percent(Decimal("0.012350")) == "1.24%"

    def test_none_stays_none__an_absent_rate_is_not_zero_percent(self):
        """The em-dash-versus-$0.00 distinction the whole CR turns on: a charge
        code with no percent is not a charge code at 0.00%."""
        assert _display_percent(None) is None


class TestMoneyReadsAsMoney:
    def test_a_stored_six_place_amount_displays_at_two(self):
        assert _display_money(Decimal("18.500000")) == "18.50"

    def test_the_worked_case_from_the_ruling(self):
        """1.5% of $100.58 is $1.5087 — the figure put to the PO. It DISPLAYS as
        $1.51 while the stored value keeps every place it had."""
        assert _display_money(Decimal("1.5087")) == "1.51"

    def test_none_stays_none(self):
        assert _display_money(None) is None


def test_the_stored_value_is_not_touched_by_the_display_helpers():
    """The guard that keeps this change away from ❄️ FROZEN B4.

    If a later lane 'simplifies' by rounding at storage, this fails — which is
    the correct place to fail, because that is OQ-285 and needs a finance
    re-sign, not a refactor.
    """
    stored = Decimal("0.015000")
    assert _display_percent(stored) == "1.50%"
    assert stored == Decimal("0.015000")
    assert stored.as_tuple().exponent == -6
