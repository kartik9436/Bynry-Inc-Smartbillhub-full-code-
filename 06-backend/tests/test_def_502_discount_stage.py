# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-502 (discounts are priced by NOTHING on the bill path — the
#           seven-stage pipeline had no discount stage at all)
# Rules:    BR-RAT-071 (discounts apply at R6, BEFORE taxes; each tax picks its
#           own base) · BR-RAT-106 (discount treatment is statutory and PER TAX
#           — `taxes.discount_treatment`, before|after, default before) ·
#           BR-RAT-068 (a discount is an OVERLAY: the bill shows the full
#           tariff amount AND the reduction as its own line) · BR-RAT-069 /
#           BR-RAT-110 (plan attachment makes a discount AVAILABLE, enrolment
#           GRANTS it — both gates) · BR-BIL-037 as amended 2026-08-22 (stage 5
#           apply-discounts) · B4 ❄ (silent on discounts — placement recorded
#           in the decision log 2026-08-22)
# Tests:    this file
# Impacts:  apps/rating/engine.py 🔒 · apps/rating/pricing/stages/
#           apply_discounts.py 🔒 · apps/billing/gather.py ·
#           apps/rating/selectors.py (discount block)
# ───────────────────────────────────────────────────────
"""DEF-502 — a granted discount REACHES THE BILL, and an unbound one does not.

THE WORKED FIGURES THIS FILE PINS (decision log, 2026-08-22)
------------------------------------------------------------
$59.00 of usage · SENIOR −10% whole-bill · one 8.25% percent tax:

    reduction               10% × 59.00           =  5.90
    tax, treatment 'before' 8.25% × 53.10 = 4.380750 → 4.38
    tax, treatment 'after'  8.25% × 59.00 = 4.867500 → 4.87
    total (before)          59.00 − 5.90 + 4.38    = 57.48
    total (after)           59.00 − 5.90 + 4.87    = 57.97

The two treatments differ by $0.49 on this one bill — which is why BR-RAT-106
makes the choice statutory and per tax, and why nothing here guesses it.

WHAT IS DELIBERATELY REFUSED, NOT PRICED (each asserted below):
  * a SERVICE-SCOPED tax whose treatment is 'before' (the default) on a
    discounted bill — no signed rule states what a scoped tax's discounted base
    was (OQ-331 — CLOSED 2026-08-22 as BR-RAT-116: the scoped base is the
    scoped services' own lines, untouched by the discount); 'after' and
    prices;
  * (until 2026-10-03, `DEF-RAT-9327`) a `named_codes` scope — it now selects
    the base line by its charge code, and an off-tariff code is refused at
    approval instead;
  * a fixed-amount discount in another currency (hard rule 2);
  * an exhausted budget under `suspend` — refused per account as a named break
    (BR-BIL-055: a break never blocks the run; decision log 2026-08-22).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import rating_seam

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_reads_helpers import *  # noqa: F401,F403 — meter/read fixtures

D = Decimal

PERIOD = rating_seam.BillingPeriod(cycle_days=30, service_days=30)
ACCOUNT = rating_seam.AccountContext(currency="USD")


def _flat(service="electric", unit_price="1"):
    return rating_seam.TariffConfig(
        service=service, model="flat", billed_unit="kWh", unit_price=D(unit_price)
    )


def _usage(amount="59"):
    return rating_seam.Quantity(amount=D(amount), unit="kWh")


def _tax(**kwargs):
    defaults = dict(code="STATE", rate=D("0.0825"), tax_id="tax-1")
    defaults.update(kwargs)
    return rating_seam.TaxRule(**defaults)


def _senior(**kwargs):
    defaults = dict(
        code="SENIOR",
        name="Senior citizen discount",
        discount_type="percentage",
        value=D("10"),
        currency="USD",
        applies_to="whole_bill",
    )
    defaults.update(kwargs)
    return rating_seam.DiscountRule(**defaults)


def _bill(*, discounts=(), taxes=(), services=None):
    return rating_seam.price_bill(
        services=services if services is not None else ((_flat(), _usage()),),
        period=PERIOD,
        account=ACCOUNT,
        taxes=taxes,
        discounts=discounts,
    )


# ══════════════════════════════════════════════════════════════════════════
# The stage itself — the worked figures
# ══════════════════════════════════════════════════════════════════════════


def test_def502_a_granted_discount_reduces_the_bill_by_the_worked_figure():
    """THE DEFECT'S OWN CASE: $59.00 usage, SENIOR −10% → a −$5.90 line.

    This test was written BEFORE the wiring and proved RED (law 7): the first
    run failed with `AttributeError: module 'apps.billing.rating_seam' has no
    attribute 'DiscountRule'` — the seam could not even NAME a discount, let
    alone carry one, which is DEF-502 verbatim.
    """
    bill = _bill(discounts=(_senior(),))
    lines = bill.lines_of("discount")
    assert len(lines) == 1
    line = lines[0]
    assert line.amount == D("-5.90")
    # BR-RAT-068 / DIS-02 step 1: the discount's NAME is the bill line label.
    assert line.description == "Senior citizen discount"
    assert line.taxable is False
    # BR-RAT-068: the bill shows the FULL tariff amount and the reduction as
    # its own line — the usage line is untouched.
    assert bill.sole_line("usage").amount == D("59.00")
    assert bill.total == D("53.10")


def test_def502_an_absent_discount_changes_nothing():
    """No discounts → byte-identical to the pre-DEF-502 bill."""
    bill = _bill(taxes=(_tax(),))
    assert bill.lines_of("discount") == ()
    assert bill.sole_line("tax").amount == D("4.87")  # 8.25% × 59.00
    assert bill.total == D("63.87")


def test_def502_treatment_before_taxes_the_reduced_subtotal():
    """BR-RAT-106: 'before' = the discount lands BEFORE the tax, so the
    authority levies on the REDUCED subtotal. 8.25% × 53.10 → $4.38."""
    bill = _bill(discounts=(_senior(),), taxes=(_tax(discount_treatment="before"),))
    assert bill.sole_line("tax").amount == D("4.38")
    assert bill.total == D("57.48")
    # The REPORTED taxable subtotal stays the full tariff amount (BR-RAT-068:
    # the bill shows both figures; the reduction is its own line).
    assert bill.taxable_subtotal == D("59.00")


def test_def502_treatment_default_is_before():
    """BR-RAT-106: a NULL treatment answers 'before' — the single behaviour the
    engine has always had, so a row nobody restated moves nothing."""
    bill = _bill(discounts=(_senior(),), taxes=(_tax(discount_treatment=None),))
    assert bill.sole_line("tax").amount == D("4.38")


def test_def502_treatment_after_taxes_the_full_tariff_amount():
    """BR-RAT-106: 'after' = the authority never sees the discount.
    8.25% × 59.00 → $4.87, and the two treatments differ by $0.49."""
    bill = _bill(discounts=(_senior(),), taxes=(_tax(discount_treatment="after"),))
    assert bill.sole_line("tax").amount == D("4.87")
    assert bill.total == D("57.97")


def test_def502_a_scoped_discount_takes_its_own_scope():
    """BR-RAT-068: a scoped percentage is a percentage of the TARIFF lines in
    its scope. base_only −50% on a $12 base reduces $6.00, not 10% of the bill."""
    tariff = rating_seam.TariffConfig(
        service="water",
        model="flat",
        billed_unit="kgal",
        unit_price=D("2"),
        base_charge=D("12"),
    )
    bill = _bill(
        services=((tariff, rating_seam.Quantity(amount=D("10"), unit="kgal")),),
        discounts=(
            _senior(code="BASEHELP", name="Base assistance", value=D("50"), applies_to="base_only"),
        ),
    )
    assert bill.lines_of("discount")[0].amount == D("-6.00")
    assert bill.total == D("26.00")  # 20.00 usage + 12.00 base − 6.00


def test_def502_an_unverified_enrolment_reduces_nothing():
    """Proof before first reduction (BR-RAT-076): the bill charges in full."""
    bill = _bill(discounts=(_senior(verified=False),), taxes=(_tax(),))
    assert bill.lines_of("discount") == ()
    assert bill.total == D("63.87")


def test_def502_the_floor_stops_the_reduction():
    """BR-RAT-074: a discount may take a bill to its floor, never below it."""
    bill = _bill(
        discounts=(_senior(discount_type="fixed_amount", value=D("100")),),
    )
    # $59.00 of tariff, floor 0 → the credit is trimmed to $59.00.
    assert bill.lines_of("discount")[0].amount == D("-59.00")
    assert bill.total == D("0.00")


# ══════════════════════════════════════════════════════════════════════════
# The refusals — nothing is guessed
# ══════════════════════════════════════════════════════════════════════════


def test_br_rat_116_a_scoped_tax_on_a_discounted_bill_prices_on_its_own_lines():
    """⚠ **THIS WAS OQ-331's REFUSAL, INVERTED BY THE RULING THAT CLOSED IT.**
    BR-RAT-116 (PO 2026-08-22, verbatim: *"tax is always on Utility service
    charge + base fees"*): the scoped base is the scoped services' own taxable
    lines and the whole-bill discount does not shrink it — the OQ's own worked
    figure, 1.5% × $59.00 electric = **$0.89**, never $0.74 or $0.80, with the
    SENIOR −10% still on the bill."""
    bill = _bill(
        discounts=(_senior(),),
        taxes=(_tax(code="FRANCHISE", rate=D("0.015"), applies_to_services=("electric",)),),
    )
    assert bill.sole_line("tax").amount == D("0.89")
    assert bill.lines_of("discount")  # the discount is genuinely on this bill


def test_def502_a_scoped_tax_with_treatment_after_still_prices():
    """'after' is well-defined for a scoped tax — it never sees the discount.
    1.5% × 59.00 electric → $0.89."""
    bill = _bill(
        discounts=(_senior(),),
        taxes=(
            _tax(
                code="FRANCHISE",
                rate=D("0.015"),
                applies_to_services=("electric",),
                discount_treatment="after",
            ),
        ),
    )
    assert bill.sole_line("tax").amount == D("0.89")


def test_def502_a_flat_tax_is_untouched_by_a_discount():
    """A flat-per-bill tax is not a percent of anything (BR-RAT-036): $0.85 is
    $0.85 on a discounted bill too, whatever its scope or treatment."""
    bill = _bill(
        discounts=(_senior(),),
        taxes=(
            _tax(code="PUC", rate=None, flat_amount=D("0.85"), applies_to_services=("electric",)),
        ),
    )
    assert bill.sole_line("tax").amount == D("0.85")


def test_def502_named_codes_scope_never_stops_the_bill():
    """⚠ AMENDED 2026-10-03 (`DEF-RAT-9327`). This test asserted that a
    `named_codes` scope REFUSED the bill, and that refusal was the defect: it
    stopped every enrolled account's whole bill. The base line now carries its
    charge code (`tests/test_def_rat_9327_named_codes_waiver.py` pins the
    walk's $60.00 → $52.00); a code no line on THIS bill carries reduces
    nothing and the bill prices. A code that can never be on a tariff line (a
    fee such as CONN) is refused at APPROVAL instead."""
    bill = _bill(discounts=(_senior(applies_to="named_codes", applies_to_charge_codes=("CONN",)),))
    assert bill.lines_of("discount") == ()
    assert bill.total == D("59.00")


def test_def502_a_foreign_currency_credit_refuses():
    """Hard rule 2: a €25 credit is not $25 of anything."""
    with pytest.raises(rating_seam.PricingRefused):
        _bill(discounts=(_senior(discount_type="fixed_amount", value=D("25"), currency="EUR"),))


def test_def502_budget_exhaustion_under_suspend_never_holds_the_bill():
    """⚖️ `BR-RAT-075` "suspend" SUPERSEDED (PO 2026-10-04: *"We cannot hold the
    bill; we need to make discount value to 0 and move on - we cannot stop the
    billing"*). This asserted a named break — the account's whole bill held —
    until that ruling. A spent budget now prices the bill in full with no
    discount line."""
    full = _bill()
    bill = _bill(discounts=(_senior(budget_remaining=D("0")),))
    assert bill.lines_of("discount") == ()
    assert bill.total == full.total


# ══════════════════════════════════════════════════════════════════════════
# The live path — gather reads the enrolment THROUGH the plan binding
# ══════════════════════════════════════════════════════════════════════════

django_db = pytest.mark.django_db


@django_db
def test_def502_gather_carries_a_bound_and_enrolled_discount(brazos, dana):
    """BOTH GATES (BR-RAT-069 / BR-RAT-110): plan binding makes it available,
    the enrolment grants it — and then gather carries it to the engine."""
    from tests.test_us_met_helpers import tenant_ctx

    with tenant_ctx(brazos):
        account, plan = _enrolled_account(brazos, dana, bind_to_plan=True)
        data = _gathered(account)
        assert [d.code for d in data.discounts] == ["SENIOR"]
        assert data.discounts[0].name == "Senior citizen discount"
        assert data.discounts[0].value == D("10")


@django_db
def test_def502_an_unbound_discount_changes_nothing(brazos, dana):
    """Enrolled but NOT bound to the account's plan → no discount reaches the
    bill (BR-RAT-110: a bill run reads enrolments AND the plan's binding;
    `resolution.resolve_discounts` drops the same enrolment on the R-chain)."""
    from tests.test_us_met_helpers import tenant_ctx

    with tenant_ctx(brazos):
        account, plan = _enrolled_account(brazos, dana, bind_to_plan=False)
        data = _gathered(account)
        assert data.discounts == ()


@django_db
def test_def502_a_drafted_bill_carries_the_discount_line(brazos, dana):
    """END TO END on the live path: prepare-shaped gather → calculate_account →
    a DRAFT invoice whose lines include the negative SENIOR line."""
    from apps.billing import runs
    from tests.test_us_met_helpers import tenant_ctx

    with tenant_ctx(brazos):
        account, plan = _enrolled_account(brazos, dana, bind_to_plan=True)
        data = _gathered(account)
        invoice = runs.calculate_account(data, service_date=date(2026, 7, 31))
        rows = list(invoice.lines.all())
        discount_rows = [row for row in rows if row.kind == "discount"]
        assert len(discount_rows) == 1
        assert discount_rows[0].description == "Senior citizen discount"
        assert discount_rows[0].amount < 0
        # −10% of (usage + base): the worked figure is asserted against the
        # fixture's own numbers rather than re-typed — BR-RAT-068's overlay.
        tariff_total = sum(row.amount for row in rows if row.kind in ("usage", "base"))
        expected = -(tariff_total * D("10") / D("100")).quantize(D("0.01"))
        assert discount_rows[0].amount == expected
        assert D(invoice.total) == tariff_total + discount_rows[0].amount


# ── fixture plumbing (mirrors tests/test_def_438_parity.py) ────────────────


def _enrolled_account(tenant, actor, *, bind_to_plan):
    from apps.rating import discounts as discount_models
    from tests.test_def_438_parity import _account_on, _water_plan

    plan = _water_plan(tenant)
    account, _unit, _asset, _delta = _account_on(tenant, actor, plan)
    discount = discount_models.Discount.objects.create(
        tenant=tenant,
        code="SENIOR",
        name="Senior citizen discount",
        status=discount_models.DISCOUNT_ACTIVE,
    )
    discount_models.DiscountVersion.objects.create(
        tenant=tenant,
        discount=discount,
        version_no=1,
        status=discount_models.VERSION_ACTIVE,
        discount_type=discount_models.DISCOUNT_PERCENTAGE,
        value=Decimal("10"),
        currency="USD",
        applies_to=discount_models.SCOPE_WHOLE_BILL,
        effective_from=date(2026, 1, 1),
    )
    if bind_to_plan:
        discount_models.PlanDiscountRule.objects.create(
            tenant=tenant, rate_plan_id=plan.id, discount=discount
        )
    discount_models.DiscountEnrolment.objects.create(
        tenant=tenant,
        discount=discount,
        account=account,
        enrolled_on=date(2026, 6, 1),
        verification_status=discount_models.VERIFICATION_VERIFIED,
    )
    return account, plan


def _gathered(account):
    from tests.test_def_438_parity import _price_live

    return _price_live(account)


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-502 + BR-RAT-068/069/071/074/076/106/110 + BR-BIL-037 (amended
#         2026-08-22) + B4 ❄ (grepped for "discount": SILENT — recorded in the
#         decision log 2026-08-22) + decision log rows 2026-08-22
# generated: 2026-08-22 by the W9a DEF-502 lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a(no screen half in this wave — the S31.2
#         preview renders lines generically) F✔ G✔ H=deferred(PO 2026-08-09 —
#         🔒 rating math, HUMAN-REVIEW-PENDING, ledger row appended)
# gates: pytest tests/test_def_502_discount_stage.py · golden-verify 33/33
#         before AND after · proved RED first (the first run failed with
#         "price_bill() got an unexpected keyword argument 'discounts'")
# exceptions: the live-path tests borrow test_def_438_parity's fixture builders
#         rather than duplicating them — one fixture, two harnesses, so the
#         parity file and this one cannot drift apart about what Silver Creek
#         looks like
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
