# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-652 (critical — the PO's tax ruling of 2026-08-27 never reached
#           the data: every `taxes` row on every tenant still said `before`, so
#           every discounted bill taxed the REDUCED base)
# Rules:    BR-RAT-650 (the stored answer is `after` — the utility remits tax on
#           the full service value) · BR-RAT-106 (the treatment is statutory and
#           PER TAX, and stays per tax) · BR-RAT-071 (R6 before R7; each tax
#           picks its own base) · B4 ❄ (half-up 2dp at finalization — untouched)
# Tests:    this file
# Impacts:  apps/rating/models.py (the column default) · apps/rating/migrations/
#           0023_def652_discount_treatment_after.py 🔒 · apps/rating/services.py
#           (the blank-payload fallback) · 10-scripts/03-golden-verify.py part 3
# ───────────────────────────────────────────────────────
"""DEF-652 — a discounted bill is taxed on the FULL service value.

THE RULING THIS FILE PINS
-------------------------
PO, 2026-08-27, verbatim: *"Does a discount come off before or after tax? Tax
the full amount before discount — The utility remits tax on the full service
value; the discount is the utility's cost, not the tax authority's. - what does
the tax law in the US say - lets go with it"*, confirming an earlier *"this is
correct - A $62.14 bill with a 25% senior discount of $15.54 — is the 6.85% tax
charged on $62.14 ($4.26)"*.

THE WORKED FIGURES
------------------
    taxable tariff amount                       62.14
    SENIOR −25%            25% × 62.14 = 15.535 → 15.54
    tax, treatment 'after' 6.85% × 62.14 = 4.256590 → 4.26   ← the ruling
    tax, treatment 'before' 6.85% × 46.60 = 3.192100 → 3.19  ← what shipped
    the difference                                   1.07 per discounted bill

⚠ NO FROZEN FIGURE MOVES. B4/B5 are silent on discounts (checked by grep, and
recorded in the decision log on 2026-08-22 when the discount stage landed); the
golden harness reads 33 PASS / 0 FAIL before and after this change. `$4.26` is
the PO's own figure from the ruling, not a finance-signed golden.

WHAT IS *NOT* CLAIMED HERE
--------------------------
`before` is still lawful and still per tax (BR-RAT-106). What changed is the
answer a row carries when nobody has said otherwise. The last test in this file
is the one that would fail if a later lane "simplified" the column away.
"""

from decimal import Decimal

import pytest

from apps.billing import rating_seam
from apps.rating import models as rating_models
from apps.rating import selectors, services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

D = Decimal

#: A bill whose taxable tariff amount is EXACTLY $62.14 — the PO's own bill.
SIXTY_TWO_FOURTEEN = rating_seam.TariffConfig(
    service="electric",
    model="flat",
    billed_unit="kWh",
    base_charge=D("62.14"),
    unit_price=D("0"),
)
NO_USAGE = rating_seam.Quantity(amount=D("0"), unit="kWh")
PERIOD = rating_seam.BillingPeriod(cycle_days=30, service_days=30)
ACCOUNT = rating_seam.AccountContext(currency="USD", tax_exempt=False)

#: Silver Creek's own rate, and the one the PO worked the ruling on.
SIX_EIGHT_FIVE = D("0.0685")


def _senior_25():
    return rating_seam.DiscountRule(
        code="SENIOR",
        name="Senior citizen discount",
        discount_type="percentage",
        value=D("25"),
        currency="USD",
        applies_to="whole_bill",
    )


def _bill(*, treatment):
    return rating_seam.price_bill(
        services=((SIXTY_TWO_FOURTEEN, NO_USAGE),),
        period=PERIOD,
        account=ACCOUNT,
        taxes=(
            rating_seam.TaxRule(
                code="SILVER",
                rate=SIX_EIGHT_FIVE,
                tax_id="tax-652",
                discount_treatment=treatment,
            ),
        ),
        discounts=(_senior_25(),),
    )


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE MONEY — the ruling's own bill, both ways
# ══════════════════════════════════════════════════════════════════════════
def test_def652_the_ruled_treatment_taxes_the_full_service_value():
    """`after` = the authority never sees the discount → 6.85% × $62.14 = $4.26."""
    bill = _bill(treatment="after")
    assert bill.sole_line("discount").amount == D("-15.54")
    assert bill.sole_line("tax").amount == D("4.26")
    # The full tariff amount is still what the bill reports as taxable
    # (BR-RAT-068: the reduction is its own line, never a smaller usage line).
    assert bill.taxable_subtotal == D("62.14")
    assert bill.total == D("50.86")  # 62.14 − 15.54 + 4.26


def test_def652_the_shipped_treatment_taxed_the_reduced_base_and_the_gap_is_a_dollar_seven():
    """What every tenant was getting: 6.85% × $46.60 = $3.19, $1.07 short."""
    shipped = _bill(treatment="before")
    assert shipped.sole_line("tax").amount == D("3.19")
    ruled = _bill(treatment="after")
    assert ruled.sole_line("tax").amount - shipped.sole_line("tax").amount == D("1.07")


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE DATA — the stored answer, which is what DEF-652 is actually about
# ══════════════════════════════════════════════════════════════════════════
def test_def652_a_tax_created_without_stating_a_treatment_stores_the_ruled_answer(brazos, dana):
    """The defect in one assertion: the engine has always been able to do this
    and no row anywhere ever said so."""
    with tenant_ctx(brazos):
        jurisdiction = rating_models.TaxJurisdiction.objects.create(
            tenant=brazos, name="DEF-652 · Silver Creek"
        )
        stored = services.create_tax(
            dana,
            {
                "name": "Silver Creek utility tax",
                "kind": "percent",
                "rate": str(SIX_EIGHT_FIVE),
                "jurisdiction": str(jurisdiction.id),
            },
        )
    assert stored["discount_treatment"] == "after"


def test_def652_the_model_itself_carries_the_ruled_default(brazos):
    """Not only `create_tax`: every path that builds a `Tax` — the fixture
    seeder, the sample-data seeder, every test — gets the ruled answer, which
    is the same reasoning `is_draft=False` records one field above it."""
    with tenant_ctx(brazos):
        jurisdiction = rating_models.TaxJurisdiction.objects.create(
            tenant=brazos, name="DEF-652 · direct create"
        )
        tax = rating_models.Tax.objects.create(
            tenant=brazos,
            jurisdiction=jurisdiction,
            name="Direct",
            kind="percent",
            rate=SIX_EIGHT_FIVE,
        )
    assert tax.discount_treatment == "after"


def test_def652_the_seam_publishes_the_stored_answer_to_the_bill_run(brazos):
    """The column reaching the engine is the whole point — a default nothing
    publishes is the same defect wearing a different hat (hard-won law 2)."""
    with tenant_ctx(brazos):
        jurisdiction = rating_models.TaxJurisdiction.objects.create(
            tenant=brazos, name="DEF-652 · seam"
        )
        tax = rating_models.Tax.objects.create(
            tenant=brazos,
            jurisdiction=jurisdiction,
            name="Seam",
            kind="percent",
            rate=SIX_EIGHT_FIVE,
        )
        published = selectors.discount_treatments_for_taxes((str(tax.id),))
    assert published[str(tax.id)] == "after"


# ══════════════════════════════════════════════════════════════════════════
# 3 · STILL PER TAX — BR-RAT-106 is not collapsed into a constant
# ══════════════════════════════════════════════════════════════════════════
def test_def652_a_utility_can_still_set_one_authority_the_other_way(brazos, dana):
    """*"statutory and per tax"* — an authority that levies on the discounted
    amount is still expressible, and stays that way."""
    with tenant_ctx(brazos):
        jurisdiction = rating_models.TaxJurisdiction.objects.create(
            tenant=brazos, name="DEF-652 · per tax"
        )
        stored = services.create_tax(
            dana,
            {
                "name": "An authority that levies on the discounted amount",
                "kind": "percent",
                "rate": "0.02",
                "jurisdiction": str(jurisdiction.id),
                "discount_treatment": "before",
            },
        )
    assert stored["discount_treatment"] == "before"
    assert selectors.taxable_subtotal_for("before", D("62.14"), D("46.60")) == D("46.60")
