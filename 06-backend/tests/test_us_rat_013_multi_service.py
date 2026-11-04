# ── Trace ──────────────────────────────────────────────
# Story:    US-RAT-013 (totals — the tax base) · US-BIL-029 (the run's stages
#           over an account that has several services)   Screens: S31.2
# Rules:    BR-RAT-005 (tax base = usage + base only) · BR-RAT-006 (exemption
#           is ACCOUNT-level, regardless of service) · BR-RAT-003 (round per
#           line, half-up, 2dp, at finalization only) · BR-RAT-025 (a plan is a
#           bundle: one schedule per service) · B4.2 (the tax base, re-signed
#           2026-08-11: summed from ROUNDED line amounts)
# Golden:   GT-17 (= WE-1, the multi-service reference bill; machine-verified
#           by 10-scripts/03-golden-verify.py) — the fixture this rule is
#           frozen in
# ───────────────────────────────────────────────────────
"""A bill with several services is taxed ONCE, over the combined base.

Not per service and summed. That distinction sounds like bookkeeping and is
worth exactly one cent per bill per authority — which is the whole point, since
a cent that does not foot is what a customer telephones about.

WHERE THE RULE COMES FROM. Three signed sources, and they agree:

  * **B5 GT-17** — the WE-1 reference bill. Five services' lines are rounded
    per line, summed into ONE taxable base of 221.90, and one tax pass emits
    FOUR lines, one per authority. Not four per service.
  * **EP-BIL-01 §7**, tracing the same bill: "stage 3 Σ usage + base +
    capacity = … 221.90 (all taxable) → … stage 5 tax … split by authority."
  * **B4.2, re-signed 2026-08-11**: the base is summed from the ROUNDED line
    amounts, *"because a customer who adds up the four printed lines and
    applies the rate"* must get the number the bill prints.

That last one is what settles it, and `tc2` is that sentence as arithmetic: per
service the printed lines and the printed tax do not foot, and the customer
doing the check by hand is right while the bill is wrong.

WHAT THESE TESTS ARE NOT. They are not GT-17. GT-17's fixture uses TOU,
capacity and percent-of-service models the engine deliberately does not
implement (no frozen figure for any of them). These drive the flat model the
engine does implement, over the same RULE. When those models land, GT-17 itself
becomes assertable and should be added under tests/golden/.
"""

from decimal import Decimal

import pytest

from apps.billing import rating_seam

USD = "USD"
PERIOD = rating_seam.BillingPeriod(cycle_days=30, service_days=30)
ACCOUNT = rating_seam.AccountContext(currency=USD, tax_exempt=False)

#: 7.5% is chosen deliberately, not arbitrarily: at this rate the two readings
#: of the rule give DIFFERENT money on this fixture, which is the only kind of
#: fixture that can prove which one is implemented. At 8.25% they happen to
#: agree, and a test that passes either way proves nothing.
TAX = (rating_seam.TaxRule(code="STATE", rate=Decimal("0.075")),)

#: Each service: base 5.05 + usage 50 × 0.10 = 5.00 ⇒ 10.05 taxable.
ELECTRIC = rating_seam.TariffConfig(
    service="electric",
    model="flat",
    billed_unit="kWh",
    base_charge=Decimal("5.05"),
    unit_price=Decimal("0.10"),
)
WATER = rating_seam.TariffConfig(
    service="water",
    model="flat",
    billed_unit="kgal",
    base_charge=Decimal("5.05"),
    unit_price=Decimal("0.10"),
)
SERVICES = (
    (ELECTRIC, rating_seam.Quantity(amount=Decimal("50"), unit="kWh")),
    (WATER, rating_seam.Quantity(amount=Decimal("50"), unit="kgal")),
)


def test_us_rat_013_tc11__a_two_service_bill_is_taxed_once_on_the_combined_base():
    """The rule, on the fixture where the two readings disagree.

    Combined base 20.10 × 7.5% = 1.5075 → **1.51**, one tax line.
    """
    bill = rating_seam.price_bill(services=SERVICES, period=PERIOD, account=ACCOUNT, taxes=TAX)

    assert bill.taxable_subtotal == Decimal("20.10")  # 10.05 + 10.05
    assert bill.tax_total == Decimal("1.51")  # ONE pass, rounded once
    # One line per AUTHORITY, not per authority per service. Two services and
    # one tax rule give one tax line — GT-17's shape (five services, four
    # authorities, four lines).
    assert len(bill.lines_of("tax")) == 1
    assert bill.lines_of("tax")[0].description == "Tax STATE"
    # Both services' own lines are all present and rounded individually.
    assert [line.amount for line in bill.lines_of("usage")] == [Decimal("5.00"), Decimal("5.00")]
    assert [line.amount for line in bill.lines_of("base")] == [Decimal("5.05"), Decimal("5.05")]
    assert bill.total == Decimal("21.61")  # 20.10 + 1.51


def test_us_rat_013_tc12__per_service_tax_would_give_a_different_and_wrong_number():
    """THE TEST THAT MAKES tc11 MEAN SOMETHING.

    Without this, tc11 asserts a number without showing that the other
    implementation reaches a different one — and a fixture where both readings
    agree cannot fail on the rule it claims to test.

    Priced per service, each half taxes 10.05 × 7.5% = 0.75375 → 0.75, and the
    two sum to 1.50. The bill prints two taxable lines per service totalling
    20.10 and a tax of 1.50; a customer applying 7.5% to 20.10 gets 1.51. The
    document does not foot against itself, which is exactly what B4.2's
    2026-08-11 re-signing forbids.
    """
    per_service = sum(
        rating_seam.price_period(
            tariff=tariff, consumption=consumption, period=PERIOD, account=ACCOUNT, taxes=TAX
        ).tax_total
        for tariff, consumption in SERVICES
    )

    assert per_service == Decimal("1.50")  # the WRONG answer, made visible
    combined = rating_seam.price_bill(services=SERVICES, period=PERIOD, account=ACCOUNT, taxes=TAX)
    assert combined.tax_total == Decimal("1.51")
    assert combined.tax_total != per_service  # the cent this rule is about


def test_us_rat_013_tc13__a_bill_level_fee_is_charged_once_not_once_per_service():
    """A late fee is a fact about the ACCOUNT, not about its water.

    Passing the fees down each service's pass would multiply them by the number
    of services — and it would look right on a single-service account, which is
    every fixture that existed before this one.
    """
    fee = rating_seam.RatedLine(
        kind="fee", description="Late fee", amount=Decimal("8.13"), taxable=False
    )
    bill = rating_seam.price_bill(
        services=SERVICES, period=PERIOD, account=ACCOUNT, taxes=TAX, fees=(fee,)
    )

    assert [line.amount for line in bill.lines_of("fee")] == [Decimal("8.13")]  # once
    assert bill.fee_total == Decimal("8.13")
    # B4.2 / BR-RAT-005 — the fee is on the bill and NOT in the tax base, which
    # is unchanged from the no-fee case.
    assert bill.taxable_subtotal == Decimal("20.10")
    assert bill.tax_total == Decimal("1.51")
    assert bill.total == Decimal("29.74")  # 20.10 + 8.13 + 1.51


def test_us_rat_013_tc14__exemption_removes_tax_from_every_service_at_once():
    """BR-RAT-006 / B4.2 — exemption is an ACCOUNT fact, regardless of service.

    On a multi-service bill that means NO tax lines at all, not one exempt
    service and one taxed. The engine reads the exemption from the account, so
    it cannot differ per service — and this asserts that rather than assuming
    it, because the combined pass reuses one service's normalized input and a
    per-service exemption would have made that reuse silently wrong.
    """
    exempt = rating_seam.AccountContext(currency=USD, tax_exempt=True)
    bill = rating_seam.price_bill(services=SERVICES, period=PERIOD, account=exempt, taxes=TAX)

    assert bill.lines_of("tax") == ()  # no lines, not zero-valued ones
    assert bill.tax_total == Decimal("0.00")
    assert bill.total == Decimal("20.10")


def test_us_rat_013_tc15b__a_base_only_service_bills_its_base_and_no_usage_line():
    """BR-BIL-028 CONFIRMED — "base charges and flat services continue the full
    month" while usage lines stop.

    The distinction this proves is not arithmetic: a $0.00 usage line and NO
    usage line come to the same total and say different things to a customer.
    One states that their meter was read and showed nothing; the other states
    nothing at all, which is the true position on a vacation hold. Only one of
    them is defensible in a dispute.
    """
    bill = rating_seam.price_bill(
        services=(SERVICES[0],),  # electric measured
        base_only_services=(WATER,),  # water held — base continues
        period=PERIOD,
        account=ACCOUNT,
        taxes=TAX,
    )

    assert [line.description for line in bill.lines_of("usage")] == ["electric usage"]
    assert len(bill.lines_of("base")) == 2  # BOTH services keep their base charge
    # 5.00 + 5.05 + 5.05 = 15.10 taxable; × 7.5% = 1.1325 → 1.13
    assert bill.taxable_subtotal == Decimal("15.10")
    assert bill.tax_total == Decimal("1.13")


def test_us_rat_013_tc15__a_bill_with_no_priced_service_is_refused():
    """An account whose plan resolves to nothing priceable is an EXCEPTION.

    Returning an empty $0.00 bill would issue a document with a tax line and no
    charges, and it would issue silently. BR-BIL-015 makes it a human's problem
    instead.
    """
    with pytest.raises(Exception) as raised:
        rating_seam.price_bill(services=(), period=PERIOD, account=ACCOUNT, taxes=TAX)
    assert "no services" in str(raised.value)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-013@70a0044 (sha1[:7] of the four frozen sources, concatenated in
#         order: 04-docs/02-decisions/05-golden-tests.md ·
#         04-docs/02-decisions/04-money-math-rules.md ·
#         04-docs/05-modules/06-rating/06-epics/EP-RAT-05-engine.md ·
#         04-docs/05-modules/06-rating/02-business-rules.md)
# generated: 2026-08-11 by Eng-Lead (W3 bill-run lane — DEF-032)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure engine) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests -m golden 12 PASS (unchanged)✔
# exceptions: (1) these are NOT GT-17. GT-17's own fixture uses TOU, capacity
#         and percent-of-service models the engine does not implement and B5
#         freezes no figure for; when those land, GT-17 becomes assertable and
#         belongs under tests/golden/. What is asserted here is the RULE GT-17
#         freezes, on the flat model, with a rate chosen so the two readings of
#         it give different money
#         (2) BR-RAT-028's PLAN-LEVEL MINIMUM FLOOR is the other genuinely
#         per-bill computation and is NOT implemented: "per-service minimums
#         apply first, then the plan floor tops up the total" needs a threshold
#         the seam carries nowhere, and GT-13 is PROPOSED. price_bill is where
#         it will go when the input exists. REPORTED, not approximated
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
