# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-RAT-9307 — a tax's Bill label never reached the bill.
# Change:   CR-165-BRC10 round 4 task 10.
# Ruling:   decision log 2026-10-03 "A TAX PRINTS ITS BILL LABEL ON THE BILL".
#           Put to the PO: the walk printed "Tax County utility tax $1.20"
#           where the clerk typed Bill label "County tax"; amounts unchanged;
#           issued bills keep their wording. PO verbatim: "Okay".
# Rules:    BR-BIL-069 (a tax line names its tax; the description is DISPLAY
#           text and nothing matches on it) · hard rule 4 (issued lines are
#           never reworded — this changes what NEW lines say, nothing else)
# Golden:   NONE MOVES. Only `description` changes, and only on a tax that
#           stores a bill label; no ❄️ B5 fixture stores one.
# Impacts:  apps/rating/selectors.plan_tax_rules 🔒 · apps/billing/gather
#           ._taxes_for 🔒 · apps/billing/rating_seam.TaxRule 🔒 ·
#           apps/rating/pricing/{contracts,stages/normalize,stages/compute_tax} 🔒
# ───────────────────────────────────────────────────────
"""A tax prints its BILL LABEL on the bill (DEF-RAT-9307).

The clerk's New tax form has a *Bill label* field (help: *"Empty shows the
name."*). It was stored, served on the read and shown on every rating screen,
and the bill ignored it: the line read ``"Tax " + name``. The walk's worked
case, and the figure this file pins: **County utility tax, Bill label "County
tax", 2 % on a $60.00 bill — the line must read "County tax" for $1.20**, not
"Tax County utility tax".

Every test runs the real path a bill run takes: ``rating.selectors
.plan_tax_rules`` → ``billing.gather._taxes_for`` (the seam projection) →
the engine's compute-tax stage. A test that built the seam rule by hand would
pass while the projection dropped the label, which is exactly how this defect
hid (``bill_label`` was served on the read and no test read a bill line).

Where NO label is stored the line keeps the wording every bill has had,
``"Tax " + name`` — our judgment (decision log, same day): the ruling is about
the label being ignored, and rewording every unlabelled tax line on every
utility's next bill is a change nobody asked for.
"""

from decimal import Decimal

import pytest

from apps.billing import gather, rating_seam
from apps.rating import models as rating_models
from apps.rating import services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_plan, tenant_ctx

pytestmark = pytest.mark.django_db

USD = "USD"
TAXED = rating_seam.AccountContext(currency=USD, tax_exempt=False)
FULL_MONTH = rating_seam.BillingPeriod(cycle_days=30, service_days=30)

#: A bill whose taxable base is EXACTLY $60.00 — the walk's October bill.
SIXTY = rating_seam.TariffConfig(
    service="electric",
    model="flat",
    billed_unit="kWh",
    base_charge=Decimal("60.00"),
    unit_price=Decimal("0"),
)
NO_USAGE = rating_seam.Quantity(amount=Decimal("0"), unit="kWh")


def county_utility_tax(tenant, **fields):
    """The walk's own tax: 2 % on an authority the platform seed does not use."""
    jurisdiction, _ = rating_models.TaxJurisdiction.objects.get_or_create(
        tenant=tenant, name="Walkland County"
    )
    tax = rating_models.Tax.objects.create(
        tenant=tenant,
        jurisdiction=jurisdiction,
        name="County utility tax",
        kind="percent",
        rate=Decimal("0.020000"),
        **fields,
    )
    return tax, jurisdiction


def tax_lines_for(plan_id):
    """Price the $60.00 bill under the plan's taxes, through the bill run's
    own projection — never a hand-built seam rule."""
    taxes = gather._taxes_for(plan_id, None, services=("electric",))
    priced = rating_seam.price_period(
        tariff=SIXTY,
        consumption=NO_USAGE,
        period=FULL_MONTH,
        account=TAXED,
        taxes=taxes,
    )
    return [(line.description, line.amount) for line in priced.lines_of("tax")]


def test_tc1__an_attached_tax_prints_its_bill_label(brazos, dana):
    """THE WORKED FIGURE: "County tax" $1.20, not "Tax County utility tax"."""
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Walk Residential")
        tax, _j = county_utility_tax(brazos, bill_label="County tax")
        services.attach_tax_to_plan(
            dana, plan.id, {"tax": str(tax.id), "reason": "DEF-RAT-9307 TC-1"}
        )
        lines = tax_lines_for(plan.id)

    assert lines == [("County tax", Decimal("1.20"))]


def test_tc2__a_tax_the_authority_binding_brings_prints_its_bill_label_too(brazos):
    """The other way a tax reaches a bill — the plan binds the AUTHORITY and
    its one percent tax is derived. That row used to carry the authority's
    name; with a label stored, the label is what the customer reads."""
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Walk Bound")
        _tax, jurisdiction = county_utility_tax(brazos, bill_label="County tax")
        rating_models.PlanTaxRule.objects.get_or_create(
            tenant=brazos, rate_plan=plan, jurisdiction=jurisdiction
        )
        lines = tax_lines_for(plan.id)

    assert lines == [("County tax", Decimal("1.20"))]


def test_tc3__no_label_keeps_the_wording_every_bill_has_had(brazos, dana):
    """No label stored → the line reads exactly as before the fix, so a
    utility that never typed a label sees no change on its next bill."""
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Walk Unlabelled")
        tax, _j = county_utility_tax(brazos)
        services.attach_tax_to_plan(
            dana, plan.id, {"tax": str(tax.id), "reason": "DEF-RAT-9307 TC-3"}
        )
        lines = tax_lines_for(plan.id)

    assert lines == [("Tax County utility tax", Decimal("1.20"))]


def test_tc4__a_blank_label_is_no_label(brazos, dana):
    """A label of only spaces is treated as empty — a line must never print
    as a blank description beside $1.20."""
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Walk Blank")
        tax, _j = county_utility_tax(brazos, bill_label="   ")
        services.attach_tax_to_plan(
            dana, plan.id, {"tax": str(tax.id), "reason": "DEF-RAT-9307 TC-4"}
        )
        lines = tax_lines_for(plan.id)

    assert lines == [("Tax County utility tax", Decimal("1.20"))]


def test_tc5__the_label_changes_wording_only_never_the_amount():
    """Engine-level: the same rule with and without a label prices the same
    cents. The label is display text and never an input to arithmetic."""
    base = dict(code="County utility tax", tax_id="tax-county", rate=Decimal("0.020000"))

    def priced(rule):
        return rating_seam.price_period(
            tariff=SIXTY, consumption=NO_USAGE, period=FULL_MONTH, account=TAXED,
            taxes=(rule,),
        )

    with_label = priced(rating_seam.TaxRule(bill_label="County tax", **base))
    without = priced(rating_seam.TaxRule(**base))
    assert [line.description for line in with_label.lines_of("tax")] == ["County tax"]
    assert [line.description for line in without.lines_of("tax")] == ["Tax County utility tax"]
    assert with_label.tax_total == without.tax_total == Decimal("1.20")
    assert with_label.total == without.total == Decimal("61.20")
