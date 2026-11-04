# ── Trace ──────────────────────────────────────────────
# Story:    US-RAT-013 (totals: tax base + account exemption)
#           Screens: — (totals render in S31.2)
# Rules:    BR-RAT-005 (tax base = usage + base only; fees/late never taxed) ·
#           BR-RAT-006 (exemption is ACCOUNT-level, regardless of service) ·
#           BR-RAT-003 (round per line, half-up, 2dp, at finalization) ·
#           BR-RAT-036 (percent tax form; no tax-on-tax, no fee taxation)
# Golden:   GT-10 · GT-11 — B5 ❄️ FROZEN 2026-08-08 (GT-10's total re-signed
#           2026-08-10 under HUMAN-GUIDE §6, DEF-028). The FIGURES are asserted
#           in 06-backend/tests/golden/; this file asserts the rules.
# Tests:    this file (US-RAT-013 TC-1/2/7 + the rounding boundary)
# Impacts:  apps/rating/engine.py 🔒 · apps/rating/pricing/stages/**
# ───────────────────────────────────────────────────────
"""US-RAT-013 — the totals pass: what is taxed, what is never taxed, and when.

B4.2's claim is STRUCTURAL, and `test_..._tc7` is why that word matters: a fee
line that arrives from a mis-seeded charge code with `taxable=True` still cannot
enter a percent base, because the engine decides the base by line KIND and not
by a flag alone. A data-driven reading of B4.2 would let one bad reference row
tax a late fee across every bill in a run.
"""

from decimal import Decimal

from apps.billing import rating_seam

USD = "USD"
TAXED = rating_seam.AccountContext(currency=USD, tax_exempt=False)
EXEMPT = rating_seam.AccountContext(currency=USD, tax_exempt=True)
FULL_MONTH = rating_seam.BillingPeriod(cycle_days=30, service_days=30)
TAX_8_25 = (rating_seam.TaxRule(code="STATE+LOCAL", rate=Decimal("0.0825")),)

TARIFF = rating_seam.TariffConfig(
    service="electric",
    model="flat",
    billed_unit="kWh",
    base_charge=Decimal("18.50"),
    unit_price=Decimal("0.12"),
)


def price(account, taxes=TAX_8_25, fees=()):
    return rating_seam.price_period(
        tariff=TARIFF,
        consumption=rating_seam.Quantity(amount=Decimal("684"), unit="kWh"),
        period=FULL_MONTH,
        account=account,
        taxes=taxes,
        fees=fees,
    )


def fee_line(taxable: bool) -> rating_seam.RatedLine:
    return rating_seam.RatedLine(
        kind="fee", description="Late fee", amount=Decimal("8.13"), taxable=taxable
    )


def test_us_rat_013_tc1_a_fee_on_the_bill_stays_out_of_the_tax_base():
    """TC-1 — the tax is identical whether or not a fee sits on the bill."""
    without_fee = price(TAXED)
    with_fee = price(TAXED, fees=(fee_line(taxable=False),))

    assert with_fee.taxable_subtotal == without_fee.taxable_subtotal
    assert with_fee.tax_total == without_fee.tax_total
    # The fee is on the bill — it is in the total and in fee_total, and only there.
    assert with_fee.fee_total == Decimal("8.13")
    assert with_fee.total - without_fee.total == Decimal("8.13")


def test_us_rat_013_tc2_exemption_zeroes_a_tax_that_would_otherwise_apply():
    """TC-2 — B4.2/BR-RAT-006: account-level, regardless of service.

    The tax RULES are still supplied, so the exemption has to zero a live tax
    rather than inherit an absent one — and nothing else about the bill moves.
    """
    taxed = price(TAXED, fees=(fee_line(taxable=False),))
    exempt = price(EXEMPT, fees=(fee_line(taxable=False),))

    assert exempt.tax_total == Decimal("0")
    assert exempt.lines_of("tax") == ()  # no zero-valued tax line on the bill
    # "same as GT-10 but flagged exempt": every other line is untouched.
    assert exempt.taxable_subtotal == taxed.taxable_subtotal
    assert exempt.fee_total == taxed.fee_total
    assert exempt.sole_line("usage").amount == taxed.sole_line("usage").amount
    assert exempt.sole_line("base").amount == taxed.sole_line("base").amount
    assert taxed.total - exempt.total == taxed.tax_total


def test_us_rat_013_tc7_a_fee_wrongly_flagged_taxable_still_never_taxes():
    """TC-7 — B4.2 is structural, not data-driven.

    A mis-seeded charge code hands the engine a fee with taxable=True. The tax
    base must not move: the engine decides by line KIND. This is the assertion
    that separates "we set a flag correctly" from "the rule cannot be violated
    by data".
    """
    honest = price(TAXED, fees=(fee_line(taxable=False),))
    mis_seeded = price(TAXED, fees=(fee_line(taxable=True),))

    assert mis_seeded.taxable_subtotal == honest.taxable_subtotal
    assert mis_seeded.tax_total == honest.tax_total
    assert mis_seeded.total == honest.total
    # The line's own flag is reported back as it arrived — the engine does not
    # silently rewrite the caller's data, it declines to be governed by it.
    assert mis_seeded.sole_line("fee").taxable is True


def test_us_rat_013_no_tax_on_tax():
    """BR-RAT-036 — a tax line never joins the base another tax is computed on."""
    bill = price(
        TAXED,
        taxes=(
            rating_seam.TaxRule(code="STATE", rate=Decimal("0.0625")),
            rating_seam.TaxRule(code="LOCAL", rate=Decimal("0.02")),
        ),
    )
    lines = bill.lines_of("tax")

    assert len(lines) == 2
    assert all(line.taxable is False for line in lines)
    # Each authority prices on the SAME base — the first tax does not enlarge it.
    assert lines[0].amount == (bill.taxable_subtotal * Decimal("0.0625")).quantize(Decimal("0.01"))
    assert lines[1].amount == (bill.taxable_subtotal * Decimal("0.02")).quantize(Decimal("0.01"))


def test_us_rat_013_rounding_is_half_up_2dp_and_happens_once():
    """BR-RAT-003 / B4.4 — per line, half-up, 2dp, at finalization only.

    GT-1 pins the ordinary case (8.2979 -> 8.30). Half-up is only DISTINGUISHABLE
    from banker's rounding at an exact tie, and no B5 figure in GT-1..11 reaches
    one — so the tie is pinned here, on a line amount that ties exactly.
    """
    half = rating_seam.price_period(
        tariff=rating_seam.TariffConfig(
            service="electric",
            model="flat",
            billed_unit="kWh",
            base_charge=None,
            unit_price=Decimal("0.005"),
        ),
        consumption=rating_seam.Quantity(amount=Decimal("1"), unit="kWh"),
        period=FULL_MONTH,
        account=TAXED,
    )
    # 1 x 0.005 = 0.005 — an exact tie at 2dp. Half-up rounds AWAY from zero
    # (0.01); banker's rounding would give 0.00 and this assertion would fail.
    assert half.sole_line("usage").amount == Decimal("0.01")
    assert half.total == Decimal("0.01")

    # And the intermediate that produced it was never itself rounded: 3 units at
    # 0.005 is 0.015 -> 0.02, not 3 x 0.01 = 0.03.
    three = rating_seam.price_period(
        tariff=rating_seam.TariffConfig(
            service="electric",
            model="flat",
            billed_unit="kWh",
            base_charge=None,
            unit_price=Decimal("0.005"),
        ),
        consumption=rating_seam.Quantity(amount=Decimal("3"), unit="kWh"),
        period=FULL_MONTH,
        account=TAXED,
    )
    assert three.sole_line("usage").amount == Decimal("0.02")


def test_us_rat_013_totals_are_sums_of_the_lines_a_customer_can_read():
    """The bill reconciles: no total is computed from a hidden intermediate."""
    bill = price(TAXED, fees=(fee_line(taxable=False),))

    assert bill.total == sum(line.amount for line in bill.lines)
    assert bill.taxable_subtotal == sum(
        line.amount for line in bill.lines if line.kind in ("usage", "base")
    )
    assert bill.tax_total == sum(line.amount for line in bill.lines_of("tax"))
    assert bill.fee_total == sum(line.amount for line in bill.lines_of("fee"))


# ══════════════════════════════════════════════════════════════════════════
# THE TAX BASE IS SUMMED FROM THE ROUNDED LINES — PO ruling 2026-08-11.
#
# B4.4 fixes rounding (half-up, 2dp, at line finalization) and B4.2 fixes WHICH
# lines are taxable. Neither said whether the tax is charged on the finalized
# figures or on the unrounded values behind them, and every frozen case is
# exact under both readings ($100.58 x 8.25% = 8.2979 -> 8.30 either way) — so
# no golden test decided it, and until 2026-08-11 NOTHING IN THE SUITE DID.
#
# That was measured, not assumed: switching `finalize.taxable_base` to sum the
# unrounded candidate amounts left the ENTIRE suite green — 12 golden tests, 41
# rating tests, no failures. A ratified figure with no test behind it is just a
# sentence in a document, and the review mechanism this repo adopted the same
# morning says a ruling is only recorded once a test asserts it. These two are
# that test.
# ══════════════════════════════════════════════════════════════════════════

# A real water bill that lands on the boundary: 20,021 gallons at half a cent.
BOUNDARY_TARIFF = rating_seam.TariffConfig(
    service="water",
    model="flat",
    billed_unit="gal",
    base_charge=Decimal("18.50"),
    unit_price=Decimal("0.005"),
)
BOUNDARY_USAGE = rating_seam.Quantity(amount=Decimal("20021"), unit="gal")
#   usage           20,021 x 0.005 = 100.105  -> the printed line reads 100.11
#   taxable base    100.11 + 18.50 = 118.61   (rounded — what the bill shows)
#                   100.105 + 18.50 = 118.605 (unrounded — the rejected reading)
#   tax @ 8.25%     118.61  x 0.0825 = 9.785325  -> 9.79   RULED
#                   118.605 x 0.0825 = 9.7849125 -> 9.78   REJECTED
TAX_ON_ROUNDED_LINES = Decimal("9.79")
TAX_ON_UNROUNDED_INTERMEDIATES = Decimal("9.78")


def test_us_rat_013_tc9__the_tax_base_sums_the_rounded_line_amounts():
    """The bill must foot: line amounts + this rate = the tax the bill prints.

    This is the PO's whole stated reason for the ruling. Under the rejected
    reading a customer adds up the amounts printed on their own bill, applies
    the printed rate, gets 9.78, and the bill says 9.79 — they cannot reproduce
    your number from the document you sent them.
    """
    bill = rating_seam.price_period(
        tariff=BOUNDARY_TARIFF,
        consumption=BOUNDARY_USAGE,
        period=FULL_MONTH,
        account=TAXED,
        taxes=TAX_8_25,
    )

    printed = [line.amount for line in bill.lines_of("usage")] + [
        line.amount for line in bill.lines_of("base")
    ]
    assert sum(printed, Decimal("0.00")) == Decimal("118.61")  # what the bill shows

    tax = sum((line.amount for line in bill.lines_of("tax")), Decimal("0.00"))
    assert tax == TAX_ON_ROUNDED_LINES
    assert tax != TAX_ON_UNROUNDED_INTERMEDIATES  # the reading the PO rejected

    # And the document foots: the printed lines at the printed rate ARE the tax.
    assert (sum(printed, Decimal("0.00")) * Decimal("0.0825")).quantize(Decimal("0.01")) == tax


def test_us_rat_013_tc9__the_taxable_subtotal_is_built_from_finalized_lines():
    """The same rule one level down, where a future refactor would break it.

    The end-to-end test above proves the OUTPUT; this proves the MECHANISM, so
    a change that reaches the same total by a different route still has to
    state its intent. 165.6364 unrounded against 165.63 printed — the four-line
    case the PO was shown.

    ⚠ THIS ONE DOES NOT BITE ON ITS OWN, measured not assumed: it calls
    `taxable_base` directly, so the mutation that matters — `finalize` handing
    the stage an unrounded subtotal instead — leaves it GREEN. The end-to-end
    test above is what caught that (9.78 against the ruled 9.79). Recorded as a
    limit rather than left reading like a second line of defence, per hard-won
    law 1.
    """
    from apps.rating.pricing.contracts import KIND_BASE, KIND_USAGE, LineCandidate
    from apps.rating.pricing.stages import finalize as finalize_stage

    candidates = (
        LineCandidate(
            kind=KIND_USAGE, description="Electric", amount=Decimal("124.1132"), taxable=True
        ),
        LineCandidate(
            kind=KIND_BASE, description="Electric base", amount=Decimal("18.50"), taxable=True
        ),
        LineCandidate(
            kind=KIND_USAGE, description="Water", amount=Decimal("11.0232"), taxable=True
        ),
        LineCandidate(
            kind=KIND_BASE, description="Water base", amount=Decimal("12.00"), taxable=True
        ),
    )
    finalized = tuple(finalize_stage.finalize_line(c) for c in candidates)

    assert finalize_stage.taxable_base(finalized) == Decimal("165.63")
    assert finalize_stage.taxable_base(finalized) != Decimal("165.6364")


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-013@70a0044 (sha1[:7] of the four frozen sources, concatenated in
#         order: 04-docs/02-decisions/05-golden-tests.md ·
#         04-docs/02-decisions/04-money-math-rules.md ·
#         04-docs/05-modules/06-rating/06-epics/EP-RAT-05-engine.md ·
#         04-docs/05-modules/06-rating/02-business-rules.md — recomputed 2026-08-10)
# generated: 2026-08-10 by story-coder (rating-engine lane — EP-RAT-05)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure engine) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_us_rat_013_totals.py✔ · pytest tests -m golden → 7 passed / 4 xfailed✔ · 10-scripts/03-golden-verify.py 33 PASS/0 FAIL✔ · run_gates 14 PASS/0 FAIL/1 SKIP✔
# exceptions: US-RAT-013 TC-3/TC-4 (minimum bill, both modes) are NOT covered — the seam carries neither the per-service minimum nor the plan floor, and GT-13 is PROPOSED rather than frozen. TC-5 (per-jurisdiction rate override), TC-6 (flat + per-unit tax forms, BR-RAT-036 PROPOSED) and TC-8 (exemption EXPIRY, BR-CUS-063) each need a field the seam's TaxRule/AccountContext does not carry. TC-9 (isolation) is the caller's RLS boundary — see US-RAT-012's note. Every gap is a missing input, not a declined rule.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
