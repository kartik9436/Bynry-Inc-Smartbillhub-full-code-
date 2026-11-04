# ── Trace ──────────────────────────────────────────────
# Defects: DEF-491 (OQ-303 was answered and the answer never reached the
#          fixture) · DEF-496 (no carts are seeded on any unit) · DEF-495
#          (`tenant_services.metered` has no reader) · DEF-497 (`_trash_uom`
#          read keys its seam never returns) · DEF-161 (an unmetered service is
#          treated as a missing read)
# Rules:   BR-RAT-090 (an unmetered service's quantity is a COUNT of its assets
#          on the unit — PO 2026-08-20, option A, closing OQ-283) ·
#          BR-RAT-081 (a service is declared metered or unmetered) ·
#          CLAUDE.md rule 3 (a quantity carries its unit)
# Rulings: PO 2026-08-21 closing OQ-303, verbatim: *"they are bill 1 trash can
#          $15 - for example if you have 3 you multiple by 3"*
# Questions: OQ-317 (does the $18.00 monthly base survive beside the per-cart
#          price?) — OPEN, and this file asserts only what is ruled
# ───────────────────────────────────────────────────────
"""CR-019: three carts bill $45.00 — the ruled figure, asserted.

⚠ **THIS IS AN ORDINARY TEST AND DELIBERATELY NOT A GOLDEN ONE.** B4 money math
and B5's GT-1..61 are ❄️ FROZEN, finance-signed 2026-08-08, and a figure enters
that set only by a finance re-sign through HUMAN-GUIDE §6 — never by a lane
adding a case. `$15.00` per cart is a PO ruling of 2026-08-21 over a fixture
figure; it belongs here, where it is checked on every run and moves nothing
frozen. `10-scripts/03-golden-verify.py` and `tests/golden` are untouched.

WHAT IS ASSERTED, AND WHAT IS DELIBERATELY NOT
-----------------------------------------------
**Asserted: the CART LINE is `$45.00` for three carts.** That is BR-RAT-090's
own worked figure and the PO's own sentence, and it is `$45.00` under BOTH
readings of OQ-303's closure — the arithmetic `3 × $15.00` does not depend on
what happens to the monthly base.

**NOT asserted: the bill TOTAL.** Whether the `$18.00` monthly base survives
beside the per-cart price was not ruled (OQ-317, OPEN): retiring it makes the
bill `$45.00` and keeping it makes the same bill `$63.00`. Asserting either
would pick, and the prime directive forbids a lane resolving an open question by
choosing a value — so this file pins the half that IS ruled and leaves the half
that is not visibly open.

WHY THERE IS NO END-TO-END CASE HERE, STATED RATHER THAN QUIETLY OMITTED
-------------------------------------------------------------------------
The brief asked for an E2E case where three carts bill $45.00. **It cannot be
written today, and the reason is three filed defects rather than an oversight:**

  * **DEF-496** — no carts are seeded on any unit, so
    `assets.selectors.billable_asset_count` truthfully answers `0` for every
    account in the product.
  * **DEF-495** — `tenant_services.metered` has no reader anywhere, so the bill
    run cannot tell an unmetered service from a service whose meter was not
    read.
  * **DEF-161** — so the run treats trash as a missing read, and
    `apps/billing/sample_data._decide_the_unmetered_services` records
    `bill_without_service`, which **DELETES the trash line from every seeded
    bill**.

Writing a browser case now would therefore assert `$45.00` against a bill that
carries no trash line at all — a check that passes against the broken screen,
which is the exact failure Addendum r11's step 2d names. What IS written is the
whole chain from the seeded price to the ruled figure, through the real
functions, so that the day those three joints close the E2E case has something
true to sit on.
"""

from decimal import Decimal

import pytest

from apps.rating import models as rating_models
from apps.rating import resolution, sample_data
from core import sample_fixture as fixture

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

#: The PO's own two numbers, read from the fixture and never re-typed.
PER_CART = Decimal(fixture.TRASH_PER_CART)
CARTS = 3
RULED_CART_LINE = Decimal("45.00")


def test_the_ruled_price_is_fifteen_dollars_a_cart():
    """OQ-303's closure, in the one place the seeder reads it from.

    A second literal for this figure anywhere would be a second source of truth
    for exactly the fact DEF-491 is about — an answer that reached one place and
    not another.
    """
    assert PER_CART == Decimal("15.00")


def test_three_carts_bill_forty_five_dollars():
    """**THE RULED ARITHMETIC, END TO END THROUGH THE REAL FUNCTIONS.**

    `counted_quantity` is BR-RAT-090's own implementation of *"a COUNT OF ITS
    ASSETS ON THE UNIT"*, and the price is the seeded schedule's. Nothing here
    re-implements either: a test that recomputes the thing it is checking proves
    only that its author was consistent with themselves.

    3 carts × `$15.00` = **`$45.00`**.
    """
    counted = resolution.counted_quantity(
        resolution.AssetCountFacts(service="trash", count=CARTS)
    )
    assert counted == Decimal(CARTS)
    assert counted * PER_CART == RULED_CART_LINE


def test_removing_a_cart_moves_the_next_bill_to_thirty_dollars():
    """The second half of the ratified example, and the half that proves the
    count is a QUANTITY rather than a flag.

    BR-RAT-090: *"remove one and the next bill is `$30.00`"*. A price that did
    not multiply would give `$45.00` here too, and the difference between a
    per-cart rate and a flat charge would be invisible.
    """
    counted = resolution.counted_quantity(
        resolution.AssetCountFacts(service="trash", count=CARTS - 1)
    )
    assert counted * PER_CART == Decimal("30.00")


def test_no_carts_recorded_refuses_and_zero_carts_bills_nothing():
    """The two absences BR-RAT-090 keeps apart, at the price that now makes the
    difference visible.

    `count=0` is a real answer — the utility looked and this unit has no carts —
    and bills `$0.00` for carts. `count=None` is *nobody can tell*, and refuses.
    A `None` silently read as `0` is a household with three carts billed for
    none: **`$45.00` a month, on a document that looks entirely normal.**
    """
    assert resolution.counted_quantity(
        resolution.AssetCountFacts(service="trash", count=0)
    ) * PER_CART == Decimal("0")

    with pytest.raises(resolution.AssetCountUnavailable):
        resolution.counted_quantity(resolution.AssetCountFacts(service="trash", count=None))


def test_the_seeded_trash_schedule_prices_a_cart_and_not_a_month(env):
    """**THE DEFECT ITSELF: the ruled figure reaches the SEEDED schedule.**

    This is what DEF-491 says did not happen — the answer existed and the
    fixture went on seeding `$0.00`. It reads the payload the seeder actually
    posts rather than a constant, because the constant was never the problem.

    ⚠ It also pins the UNIT (DEF-497). A price of `$15.00` per *month* against a
    quantity of three *carts* satisfies CLAUDE.md rule 3 in form and is wrong in
    substance, which is worse than a missing unit because it reads as correct.
    """
    env.enable("water", "sewer", "trash")
    with tenant_ctx(env.tenant):
        payloads = {row["name"]: row for row in sample_data._schedule_payloads()}

    trash = payloads[sample_data.SCHEDULE_TRASH]
    assert trash["structure"]["unit_price"] == fixture.TRASH_PER_CART
    assert Decimal(trash["structure"]["unit_price"]) == PER_CART
    assert trash["uom"] == fixture.TRASH_UOM == "cart", (
        f"the trash schedule prices {trash['structure']['unit_price']} per "
        f"{trash['uom']!r} — a per-cart price quoted per month is DEF-497"
    )


def test_the_eighteen_dollar_monthly_base_is_left_exactly_where_it_was():
    """**OQ-317, ASSERTED AS AN OPEN QUESTION RATHER THAN ANSWERED.**

    [W] §1's *"Trash flat $18"* is a signed figure. OQ-303's closure ruled the
    per-cart price and did not say whether this survives beside it — option (A)
    retires it (`$45.00` a bill), option (C) keeps it (`$63.00`) — so the lane
    that seeded `$15.00` deliberately did not touch this.

    This test exists so the untouched-ness is a CHECKED FACT rather than an
    intention: a later lane that quietly drops the base to make a total come out
    at `$45.00` fails here, and reads why.
    """
    # ⚠ **`OQ-317` CLOSED ON 2026-08-27, OPTION A: THE `$18.00` MONTHLY BASE IS
    # RETIRED AND THIS CONSTANT IS NO LONGER SEEDED ANYWHERE (`DEF-2490`,
    # `BR-RAT-832`).** The assertions below are UNCHANGED and still right — a
    # signed `[W] §1` figure is superseded and RECORDED, never deleted, so the
    # constant keeps its value and its distinctness from the per-cart price, and
    # a lane that collapses the two still fails here. What is no longer true is
    # the *"left standing on the seeded plan"* reading above: the plan's trash
    # base and `BASE-T` both read `fixture.TRASH_BASE` (`$0.00`) now, so a
    # three-cart household bills **$45.00**, which is option (A) below.
    assert fixture.TRASH_FLAT == "18.00"
    assert fixture.TRASH_BASE == "0", (
        "OQ-317 closed on option A — the seeded trash base is retired to $0.00 "
        "and a three-cart household bills $45.00, not $63.00 (DEF-2490)"
    )
    assert fixture.TRASH_FLAT != fixture.TRASH_PER_CART, (
        "the monthly base and the per-cart price must stay two different figures "
        "— collapsing them is OQ-303's option (B), which was offered and refused"
    )


def test_the_cart_line_is_forty_five_dollars_under_both_readings_of_oq_303():
    """Why the CR-019 walkthrough is not blocked by OQ-317.

    The open question moves the bill TOTAL and not the cart line. Stated as an
    executable fact so a reader does not have to take the argument on trust:
    under option (A) the bill is the cart line alone; under option (C) it is the
    base plus the cart line; the cart line is `$45.00` in both.
    """
    cart_line = Decimal(CARTS) * PER_CART
    option_a_total = cart_line
    option_c_total = Decimal(fixture.TRASH_FLAT) + cart_line
    assert cart_line == RULED_CART_LINE
    assert option_a_total == Decimal("45.00")
    assert option_c_total == Decimal("63.00")
    assert option_c_total - option_a_total == Decimal(fixture.TRASH_FLAT)


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-491 + OQ-303's closure (verbatim) + BR-RAT-090 + CR-019 +
#         billing workbook [W] §1 + core/sample_fixture.py
# generated: 2026-08-21 by the DEF-438 Wave A cutover lane
# checklist: A✔ B✔ C✔ D=n/a(no API half) E=deferred(no-frontend-half — the cart
#         line cannot reach a screen until DEF-495/496 close; stated in the
#         module docstring rather than omitted) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · 10-scripts/03-golden-verify.py 33 PASS / 0 FAIL✔ —
#         B5 is ❄️ FROZEN and nothing here is added to it
# exceptions: the BILL TOTAL is deliberately NOT asserted — OQ-317 is open and
#         asserting either $45.00 or $63.00 would resolve it by choosing.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
