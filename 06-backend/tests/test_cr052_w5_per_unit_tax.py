# ── Trace ──────────────────────────────────────────────
# Change:  CR-052 W5 task 16 — "Price a per-unit tax — the tier-3 usage figure
#          the stage is not handed today".
# Rules:   BR-RAT-036 (tax forms: percent · flat-per-bill · per-unit · per-meter)
#          · BR-RAT-042 (CONFIRMED, PO closing OQ-054 option (a) — the per-unit
#          "applies above N units" threshold is MARGINAL: only units ABOVE it
#          are taxed) · BR-RAT-005 / B4.2 (no tax-on-tax) · BR-RAT-003 (one
#          rounding event per line) · CLAUDE.md hard rule 3 (a quantity always
#          carries its unit) · BR-RAT-038 (no silent conversion)
# Golden:  ❄️ B5 is UNMOVED — every fixture here states a per-unit rule, which no
#          frozen figure carries. GT-1/10/11/17 are asserted unchanged by
#          `tests/golden` and by `10-scripts/03-golden-verify.py` (33 PASS).
# ───────────────────────────────────────────────────────
"""The third tax form, worked on r10's own surcharge.

r10 draws a **Water Conservation Surcharge — `$0.25 / kgal · Tier 3+ usage
only`** and this product priced it at nothing: `compute_tax` carried a paragraph
saying per-unit *"needs the tier-3 usage this stage does not receive"* and
`plan_tax_rules` skipped every `per_unit` row.

**Both halves of that were wrong.** `OQ-054` asked this exact question —
*"usage quantity or tier reference … how does a tax resolve tier numbers across
plans with different tier tables?"* — and the PO closed it as **`BR-RAT-042`,
option (a): MARGINAL, only units above the threshold are taxed.** So the
threshold is a QUANTITY the tax states, never a pointer into a tier table. And
the quantity was already on the stage's input: every usage line carries its own
`quantity` and `unit`.

**The figure this file exists to pin is `EP-RAT-05` TC-6's own:
`0.25 x 3.72 = 0.93`.**
"""

from decimal import Decimal

import pytest

from apps.billing import rating_seam

USD = "USD"
TAXED = rating_seam.AccountContext(currency=USD, tax_exempt=False)
EXEMPT = rating_seam.AccountContext(currency=USD, tax_exempt=True)
FULL_MONTH = rating_seam.BillingPeriod(cycle_days=30, service_days=30)

#: r10's residential water schedule: 0–5 @ 3.20, 5–15 @ 4.80, 15+ @ 7.20.
WATER = rating_seam.TariffConfig(
    service="water",
    model="tiered",
    billed_unit="kgal",
    base_charge=Decimal("8.00"),
    tiers=(
        rating_seam.Tier(upper=Decimal("5"), unit_price=Decimal("3.20")),
        rating_seam.Tier(upper=Decimal("15"), unit_price=Decimal("4.80")),
        rating_seam.Tier(upper=None, unit_price=Decimal("7.20")),
    ),
)
ELECTRIC = rating_seam.TariffConfig(
    service="electric",
    model="flat",
    billed_unit="kWh",
    base_charge=Decimal("18.50"),
    unit_price=Decimal("0.12"),
)

#: r10's own surcharge, and BR-RAT-042's threshold read as the rule states it.
SURCHARGE = rating_seam.TaxRule(
    code="Water Conservation Surcharge",
    tax_id="tax-water-conservation",
    per_unit_amount=Decimal("0.25"),
    per_unit_uom="kgal",
    applies_above_units=Decimal("15"),
    applies_to_services=("water",),
)


def price(taxes, quantity=Decimal("18.72"), services=None):
    return rating_seam.price_bill(
        services=services or ((WATER, rating_seam.Quantity(amount=quantity, unit="kgal")),),
        period=FULL_MONTH,
        account=TAXED,
        taxes=taxes,
    )


def tax_lines(bill):
    return [line for line in bill.lines if line.kind == "tax"]


# ── TC-1 · the worked figure ─────────────────────────────────────────────────


def test_tc1__the_surcharge_is_charged_on_the_units_above_the_threshold_only():
    """`5 + 10 + 3.72 = 18.72 kgal`, threshold `15` → taxed on **3.72** → `$0.93`.

    The number this whole task turns on. Read as a whole-bill levy the same rule
    charges `18.72 x 0.25 = $4.68`, which is the customer paying the surcharge on
    the first fifteen thousand gallons BR-RAT-042 exempts — a **$3.75** error on
    one bill, every month, on every conserving household.
    """
    bill = price((SURCHARGE,))
    (line,) = tax_lines(bill)
    assert line.quantity == Decimal("3.72")
    assert line.unit == "kgal"
    assert line.unit_price == Decimal("0.25")
    assert line.amount == Decimal("0.93")
    assert bill.tax_total == Decimal("0.93")


def test_tc2__the_line_foots_against_its_own_printed_figures():
    """A customer multiplying the printed quantity by the printed rate must get
    the printed amount. B4.2's 2026-08-11 re-signing states the principle for the
    tax base and it applies to a line that prints a quantity at all."""
    (line,) = tax_lines(price((SURCHARGE,)))
    assert line.quantity * line.unit_price == line.amount


# ── TC-3 · the boundaries of the threshold ───────────────────────────────────


def test_tc3__under_the_threshold_is_a_real_zero_and_the_line_still_prints():
    """`12.00 kgal` against a threshold of `15` is **0** taxed units.

    Zero is an ANSWER here and not an absence: the surcharge applies to this
    account and levies nothing this month, which is what BR-RAT-042 means. It is
    the one place a `$0.00` tax line is correct, and it is different from
    DEF-273's *"a tax that does not apply produces no line at all"* — that one is
    decided upstream, by whether a rule is built.
    """
    (line,) = tax_lines(price((SURCHARGE,), quantity=Decimal("12.00")))
    assert line.quantity == Decimal("0")
    assert line.amount == Decimal("0.00")


def test_tc4__exactly_at_the_threshold_taxes_nothing():
    """`15.00 kgal` is not ABOVE `15`. The boundary belongs to the exempt side —
    "only units above the threshold are taxed", read literally."""
    (line,) = tax_lines(price((SURCHARGE,), quantity=Decimal("15.00")))
    assert line.quantity == Decimal("0")
    assert line.amount == Decimal("0.00")


def test_tc5__no_threshold_taxes_every_billed_unit():
    """`None` is NO threshold, never a threshold of zero — and here the two agree
    numerically, which is why the field is read for absence rather than truth."""
    rule = rating_seam.TaxRule(
        code="Conservation (no threshold)",
        tax_id="tax-2",
        per_unit_amount=Decimal("0.25"),
        per_unit_uom="kgal",
        applies_to_services=("water",),
    )
    (line,) = tax_lines(price((rule,)))
    assert line.quantity == Decimal("18.72")
    assert line.amount == Decimal("4.68")


# ── TC-6 · hard rule 3, both directions ──────────────────────────────────────


def test_tc6__a_per_unit_rule_with_no_unit_refuses():
    """CLAUDE.md hard rule 3. `$0.25` per WHAT — the engine never assumes."""
    rule = rating_seam.TaxRule(
        code="Conservation (no unit)",
        tax_id="tax-3",
        per_unit_amount=Decimal("0.25"),
        applies_to_services=("water",),
    )
    with pytest.raises(Exception) as refusal:
        price((rule,))
    assert "no unit of measure is recorded" in str(refusal.value)


def test_tc7__a_unit_that_is_not_the_measured_unit_refuses_and_names_both():
    """kWh cannot be added to kgal and this engine holds no conversion factor
    (BR-RAT-038). The refusal names both units and asks for the scope, which is
    the fix — `$0.25 per kgal` is a statement about water."""
    rule = rating_seam.TaxRule(
        code="Conservation (kWh)",
        tax_id="tax-4",
        per_unit_amount=Decimal("0.25"),
        per_unit_uom="kWh",
        applies_to_services=("water",),
    )
    with pytest.raises(Exception) as refusal:
        price((rule,))
    message = str(refusal.value)
    assert "'kWh'" in message and "'kgal'" in message
    assert "nothing here converts between them" in message


def test_tc8__an_unscoped_per_unit_tax_on_a_mixed_bill_refuses_rather_than_guessing():
    """An unscoped `$0.25/kgal` rule on water + electric would have to add kgal
    to kWh. It refuses instead of silently counting one of them."""
    unscoped = rating_seam.TaxRule(
        code="Conservation (unscoped)",
        tax_id="tax-5",
        per_unit_amount=Decimal("0.25"),
        per_unit_uom="kgal",
    )
    with pytest.raises(Exception):
        rating_seam.price_bill(
            services=(
                (WATER, rating_seam.Quantity(amount=Decimal("18.72"), unit="kgal")),
                (ELECTRIC, rating_seam.Quantity(amount=Decimal("684"), unit="kWh")),
            ),
            period=FULL_MONTH,
            account=TAXED,
            taxes=(unscoped,),
        )


def test_tc9__scoped_to_water_it_ignores_the_electric_beside_it():
    """The same bill with the tax scoped to water bills the SAME `$0.93` it does
    on a water-only bill — the electric is neither counted nor an obstacle."""
    bill = rating_seam.price_bill(
        services=(
            (WATER, rating_seam.Quantity(amount=Decimal("18.72"), unit="kgal")),
            (ELECTRIC, rating_seam.Quantity(amount=Decimal("684"), unit="kWh")),
        ),
        period=FULL_MONTH,
        account=TAXED,
        taxes=(SURCHARGE,),
    )
    (line,) = tax_lines(bill)
    assert line.quantity == Decimal("3.72")
    assert line.amount == Decimal("0.93")


# ── TC-10 · it does not disturb the other two forms ──────────────────────────


def test_tc10__a_percent_tax_beside_it_is_unmoved_and_neither_taxes_the_other():
    """`6.25%` of the `98.78` taxable base is `6.17`; the surcharge is `0.93`.
    Neither figure moves because of the other — BR-RAT-036's no-tax-on-tax, and
    the per-unit line is `taxable=False` like every tax line."""
    percent = rating_seam.TaxRule(code="STATE", tax_id="tax-state", rate=Decimal("0.0625"))
    bill = price((percent, SURCHARGE))
    amounts = {line.description: line.amount for line in tax_lines(bill)}
    assert amounts["Tax STATE"] == Decimal("6.17")
    assert amounts["Tax Water Conservation Surcharge"] == Decimal("0.93")
    assert bill.taxable_subtotal == Decimal("98.78")
    assert bill.tax_total == Decimal("7.10")
    assert all(not line.taxable for line in tax_lines(bill))


def test_tc11__a_flat_rule_still_prints_no_quantity_and_no_rate():
    """A `$0.85` PUC fee is not a percent of anything and not a rate on
    anything. Printing `0` beside it would be a figure the customer cannot
    reconcile — the reason this was already true for `unit_price` and is now
    also true for `quantity`."""
    flat = rating_seam.TaxRule(
        code="PUC Regulatory Fee", tax_id="tax-puc", flat_amount=Decimal("0.85")
    )
    (line,) = tax_lines(price((flat,)))
    assert line.amount == Decimal("0.85")
    assert line.quantity is None
    assert line.unit is None
    assert line.unit_price is None


def test_tc12__an_exempt_account_gets_no_per_unit_line_either():
    """B4.2 / BR-RAT-006 (GT-11): exemption is ACCOUNT-level and applies
    regardless of service or tax FORM."""
    bill = rating_seam.price_bill(
        services=((WATER, rating_seam.Quantity(amount=Decimal("18.72"), unit="kgal")),),
        period=FULL_MONTH,
        account=EXEMPT,
        taxes=(SURCHARGE,),
    )
    assert tax_lines(bill) == []
    assert bill.tax_total == Decimal("0.00")


def test_tc13__a_rule_stating_none_of_the_three_forms_still_refuses():
    """Hard-won law 3 — the unsafe option must be the one you type. A `$0.00`
    tax line is a claim that the authority charges nothing."""
    with pytest.raises(Exception) as refusal:
        price((rating_seam.TaxRule(code="EMPTY", tax_id="tax-6"),))
    assert "no per-unit amount" in str(refusal.value)


# ── TC-14 · the base charge is not a quantity ────────────────────────────────


def test_tc14__the_base_charge_contributes_no_units():
    """The `$8.00` water base carries no quantity and could not contribute one.
    The filter is on KIND, exactly as `finalize.taxable_base` filters money, so
    a base, a fee, a deposit or a discount can never move a per-unit tax."""
    bill = price((SURCHARGE,))
    base = [line for line in bill.lines if line.kind == "base"]
    assert base and base[0].quantity is None
    (line,) = tax_lines(bill)
    assert line.quantity == Decimal("3.72")
