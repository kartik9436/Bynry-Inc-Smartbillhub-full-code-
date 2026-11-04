# ── Trace ──────────────────────────────────────────────
# Story:    DEF-273 (the tax model could not carry a customer-class exemption or
#           a premises-geography scope) + DEF-254 (jurisdictions seeded, rates
#           not)   Screens: S13 (Taxes & fees) · S31.2 (the lines it produces)
# Rules:    BR-RAT-036 (percent · flat-per-bill · per-unit forms) · BR-RAT-005
#           (tax base = usage + base) · BR-RAT-006 (exemption is account-level)
#           · BR-BIL-069 (a tax line names its authority) · BR-TEN-012 (a
#           tenant-touched row is never overwritten by a fixture) · CLAUDE.md
#           hard rule 2 (money is NUMERIC(18,6)) · hard-won law 3 (fail closed)
# Golden:   NONE MOVES. GT-1's ❄️ FROZEN 8.30 on a 100.58 base is the
#           unconditional 6.25 % + 2.00 % pair and is asserted UNCHANGED below,
#           because a conditional tax model must leave the unconditional case
#           byte-identical or it has rewritten a finance-signed figure.
# Tests:    this file
# Impacts:  apps/rating/models.Tax · apps/rating/selectors.plan_tax_rules ·
#           apps/rating/pricing/stages/compute_tax.py 🔒 · apps/billing/gather.py
# ───────────────────────────────────────────────────────
"""The PO's five ruled Texas tax rows, each with the condition it comes with.

PO ruling 2026-08-18 (decision log; DEF-254 → DEF-273), verbatim twice: *"Tax
jurisdiction rates (5 TX rows) - already answered"* and *"I ahve already
answered it; close it"*. The answer is prototype r10's own tax table:

  | row                          | rate            | who it reaches                  |
  |------------------------------|-----------------|---------------------------------|
  | TX State Utility Tax         | 6.25 %          | commercial + industrial ONLY    |
  | Local · Bexar County         | 2.00 %          | every class, every service      |
  | PUC Regulatory Fee           | $0.85 flat/bill | electric only                   |
  | City Franchise Fee           | 1.50 %          | inside city limits, electric+gas|
  | Water Conservation Surcharge | $0.25 / kgal    | water, above 10 kgal            |

**EVERY FIGURE IN THIS FILE IS A WORKED DOLLAR AMOUNT ON A $100.00 BILL**, not a
shape. That is deliberate: a test that asserts "a rule was returned" passes just
as happily when the rule is the wrong one, and the failure this whole change
exists to prevent is a customer being charged money they do not owe.

**THE RED-PROOF IS INSIDE EACH TEST.** Every case names the figure TODAY'S CODE
produced before the fix — `6.25` charged to a residential customer r10 exempts,
`1.50` charged to an outside-city premises r10 exempts, `0.00` where a `$0.85`
flat fee belongs — so a regression cannot pass by asserting nothing.

**PROVED RED AT HEAD, IN A CLEAN `git worktree`, TWICE — structurally and in
money.** Structurally, 9 of the 10 cases in this file fail, the first of them
with the honest failure that the resolver had nowhere to put the facts because
the model had nowhere to put the conditions:

    E  TypeError: plan_tax_rules() got an unexpected keyword argument 'customer_class'
    E  TypeError: Tax() got unexpected keyword arguments: 'applies_to_customer_classes'
    E  TypeError: Tax() got unexpected keyword arguments: 'premises_scope_kind', 'premises_scope_value'
    E  TypeError: TaxRule.__init__() missing 1 required positional argument: 'rate'
    E  TypeError: _taxes_for() got an unexpected keyword argument 'customer_class'
    E  AttributeError: module 'apps.billing.gather' has no attribute '_tax_exempt_on'
    E  AttributeError: module 'apps.rating.services' has no attribute 'TAX_CUSTOMER_CLASSES'
    E  AttributeError: module 'apps.rating.services' has no attribute 'PREMISES_SCOPE_KINDS'

And in MONEY, which is the failure that matters — the same three ruled rows
seeded at HEAD, billed to a RESIDENTIAL, OUTSIDE-CITY, electric customer on a
$100.00 bill, printed verbatim:

    HEAD charges a RESIDENTIAL, OUTSIDE-CITY, electric customer on a $100.00
    bill: {'Tax City': Decimal('1.50'), 'Tax Texas State': Decimal('6.25')}

**$7.75 that r10 says this customer does not owe** — and the $0.85 PUC fee they
DO owe is missing from that dict entirely, because a flat tax resolved to no
rule at all. Both directions wrong on one bill.
"""

from decimal import Decimal

import pytest

from apps.billing import rating_seam
from apps.rating import models as rating_models
from apps.rating import selectors, services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_plan, tenant_ctx

pytestmark = pytest.mark.django_db

USD = "USD"
TAXED = rating_seam.AccountContext(currency=USD, tax_exempt=False)
FULL_MONTH = rating_seam.BillingPeriod(cycle_days=30, service_days=30)

#: A bill whose taxable base is EXACTLY $100.00, so every tax figure below is
#: readable as its own percentage without arithmetic in the reader's head. The
#: base charge is the whole of it and usage prices to zero — B4.2's base is
#: usage + base, and 0 + 100.00 = 100.00.
HUNDRED = rating_seam.TariffConfig(
    service="electric",
    model="flat",
    billed_unit="kWh",
    base_charge=Decimal("100.00"),
    unit_price=Decimal("0"),
)
NO_USAGE = rating_seam.Quantity(amount=Decimal("0"), unit="kWh")

INSIDE_CITY = {"city": "San Antonio", "state": "TX", "postal_code": "78205"}
OUTSIDE_CITY = {"city": "Helotes", "state": "TX", "postal_code": "78023"}
NO_GEOGRAPHY: dict[str, str] = {}


# ── plumbing ────────────────────────────────────────────────────────────────
def a_tax(tenant, jurisdiction_name, **fields):
    """One `taxes` row on its own authority, written the way the seed writes it."""
    jurisdiction, _ = rating_models.TaxJurisdiction.objects.get_or_create(
        tenant=tenant, name=jurisdiction_name
    )
    return (
        rating_models.Tax.objects.create(tenant=tenant, jurisdiction=jurisdiction, **fields),
        jurisdiction,
    )


def attach(tenant, plan, jurisdiction):
    rating_models.PlanTaxRule.objects.get_or_create(
        tenant=tenant, rate_plan=plan, jurisdiction=jurisdiction
    )


def bill(rules):
    """Price a $100.00 taxable bill under exactly these resolved rules.

    The rules go through the SAME adaptation `apps/billing/gather.py` performs,
    so what is measured is the resolver's output priced by the real engine —
    not a hand-built spec that could agree with the code and be wrong (the
    mistake `tests/test_us_bil_002_gather.py`'s own trailer records).
    """
    return rating_seam.price_period(
        tariff=HUNDRED,
        consumption=NO_USAGE,
        period=FULL_MONTH,
        account=TAXED,
        taxes=tuple(
            rating_seam.TaxRule(
                code=rule["code"],
                rate=None if rule.get("rate") is None else Decimal(str(rule["rate"])),
                tax_id=rule.get("tax_id"),
                flat_amount=(
                    None if rule.get("flat_amount") is None else Decimal(str(rule["flat_amount"]))
                ),
            )
            for rule in rules
        ),
    )


def tax_amounts(priced):
    return {line.description: line.amount for line in priced.lines_of("tax")}


# ── 1 · CUSTOMER CLASS — r10: "Comm, Industrial only · Residential exempt" ──
def test_def273_state_tax__residential_pays_nothing_and_commercial_pays_625(brazos, dana):
    """THE $6.25 CASE, and the one that cost the most to get wrong.

    RED ON THE OLD CODE: `taxes` had no class column, so this same row applied
    to everybody and a RESIDENTIAL customer on a $100.00 bill was charged
    **6.25** — the figure r10 says they do not owe. The assertion below states
    that number explicitly so the regression cannot come back quietly.
    """
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Residential Standard")
        _tax, jurisdiction = a_tax(
            brazos,
            "Texas State",
            name="TX State Utility Tax",
            kind="percent",
            rate=Decimal("0.062500"),
            applies_to_customer_classes=["commercial", "industrial"],
        )
        attach(brazos, plan, jurisdiction)

        residential = selectors.plan_tax_rules(
            plan.id, customer_class="residential", premises=INSIDE_CITY, services=("electric",)
        )
        commercial = selectors.plan_tax_rules(
            plan.id, customer_class="commercial", premises=INSIDE_CITY, services=("electric",)
        )
        industrial = selectors.plan_tax_rules(
            plan.id, customer_class="industrial", premises=INSIDE_CITY, services=("electric",)
        )
        unknown_class = selectors.plan_tax_rules(
            plan.id, customer_class=None, premises=INSIDE_CITY, services=("electric",)
        )

    # NO LINE AT ALL, not a zero one: a $0.00 tax line is a claim that the
    # authority charges this customer nothing, and r10 says it does not reach
    # them in the first place.
    assert residential == []
    assert tax_amounts(bill(residential)) == {}
    assert bill(residential).tax_total == Decimal("0.00")
    assert bill(residential).total == Decimal("100.00")

    assert tax_amounts(bill(commercial)) == {"Tax Texas State": Decimal("6.25")}
    assert tax_amounts(bill(industrial)) == {"Tax Texas State": Decimal("6.25")}
    # THE RED FIGURE, stated: this is what a residential bill carried before.
    assert bill(commercial).tax_total == Decimal("6.25")

    # An account whose class could not be resolved gets NO restricted tax. Under-
    # charging is recoverable; over-charging an exempt customer is a refund.
    assert unknown_class == []


# ── 2 · PREMISES GEOGRAPHY — r10: "Inside city limits" (61 exempt) ──────────
def test_def273_franchise_fee__outside_city_pays_nothing_inside_city_pays_150(brazos, dana):
    """THE $1.50 CASE.

    RED ON THE OLD CODE: `taxes` had no geography column, so the franchise fee
    reached every premises and each of r10's **61 outside-city accounts** was
    charged **1.50** on a $100.00 bill. Three absences are asserted, not one —
    outside the city, no city recorded at all, and a scope the utility switched
    on and never named a city for.
    """
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Residential Standard")
        _tax, jurisdiction = a_tax(
            brazos,
            "City",
            name="City Franchise Fee",
            kind="percent",
            rate=Decimal("0.015000"),
            applies_to_services=["electric", "gas"],
            premises_scope_kind="city_limits",
            premises_scope_value="San Antonio",
        )
        attach(brazos, plan, jurisdiction)

        inside = selectors.plan_tax_rules(
            plan.id, customer_class="residential", premises=INSIDE_CITY, services=("electric",)
        )
        outside = selectors.plan_tax_rules(
            plan.id, customer_class="residential", premises=OUTSIDE_CITY, services=("electric",)
        )
        unrecorded = selectors.plan_tax_rules(
            plan.id, customer_class="residential", premises=NO_GEOGRAPHY, services=("electric",)
        )
        # …and case-insensitively, because a clerk types "san antonio".
        sloppy = selectors.plan_tax_rules(
            plan.id,
            customer_class="residential",
            premises={"city": "  san antonio "},
            services=("electric",),
        )

    assert tax_amounts(bill(inside)) == {"Tax City": Decimal("1.50")}
    assert tax_amounts(bill(sloppy)) == {"Tax City": Decimal("1.50")}
    # THE RED FIGURES: each of these three carried 1.50 before the fix.
    assert outside == [] and bill(outside).tax_total == Decimal("0.00")
    assert unrecorded == [] and bill(unrecorded).tax_total == Decimal("0.00")

    # The seeded shape: the scope is ON and the utility has not named their city
    # yet. It must reach NOBODY rather than everybody (hard-won law 3).
    with tenant_ctx(brazos):
        rating_models.Tax.objects.filter(tenant=brazos, name="City Franchise Fee").update(
            premises_scope_value=None
        )
        unconfigured = selectors.plan_tax_rules(
            plan.id, customer_class="residential", premises=INSIDE_CITY, services=("electric",)
        )
    assert unconfigured == []


# ── 3 · THE FLAT FORM — r10: "PUC Regulatory Fee · $0.85 flat / bill" ───────
def test_def273_puc_fee__is_085_flat_on_any_electric_bill_and_absent_from_water(brazos, dana):
    """THE $0.85 CASE — flat means flat.

    RED ON THE OLD CODE: `plan_tax_rules` returned ONLY `kind="percent"`, so a
    flat tax resolved to **no rule and no line**, and the ruled fee billed
    **0.00** on every electric bill in the product. The dollar figure must not
    move with the size of the bill, so it is asserted on $100.00 AND on
    $4,000.00 — a percent implementation would give 0.85 on one of them and
    something else on the other.
    """
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Residential Standard", services=("electric", "water"))
        _tax, jurisdiction = a_tax(
            brazos,
            "Texas Public Utility Commission",
            name="PUC Regulatory Fee",
            kind="flat_per_bill",
            flat_amount=Decimal("0.850000"),
            flat_frequency="per_bill",
            applies_to_services=["electric"],
        )
        attach(brazos, plan, jurisdiction)

        electric = selectors.plan_tax_rules(
            plan.id, customer_class="residential", premises=INSIDE_CITY, services=("electric",)
        )
        water_only = selectors.plan_tax_rules(
            plan.id, customer_class="residential", premises=INSIDE_CITY, services=("water",)
        )
        no_service_context = selectors.plan_tax_rules(
            plan.id, customer_class="residential", premises=INSIDE_CITY
        )

    assert tax_amounts(bill(electric)) == {"Tax PUC Regulatory Fee": Decimal("0.85")}

    big = rating_seam.price_period(
        tariff=rating_seam.TariffConfig(
            service="electric",
            model="flat",
            billed_unit="kWh",
            base_charge=Decimal("4000.00"),
            unit_price=Decimal("0"),
        ),
        consumption=NO_USAGE,
        period=FULL_MONTH,
        account=TAXED,
        taxes=(rating_seam.TaxRule(code="PUC Regulatory Fee", flat_amount=Decimal("0.85")),),
    )
    assert big.taxable_subtotal == Decimal("4000.00")
    assert tax_amounts(big) == {"Tax PUC Regulatory Fee": Decimal("0.85")}  # NOT 34.00, NOT 0.00

    # A water-only bill carries none of it — r10's "Electric" column.
    assert water_only == [] and bill(water_only).tax_total == Decimal("0.00")
    # And a caller that could not say what is on the bill gets no service-scoped
    # tax either: the same fail-closed direction as the other two conditions.
    assert no_service_context == []


# ── 4 · NO CONDITION AT ALL — r10: Bexar County, "all classes", "All" ───────
def test_def273_bexar_county__200_percent_reaches_every_class_and_service(brazos, dana):
    """THE $2.00 CASE, and the control for all three conditions above.

    r10: *"Customer class · All · No residential exemption at county level."* A
    tax that states no restriction must be untouched by every gate this change
    added — if it is not, the change has quietly narrowed a rate somebody is
    already collecting.
    """
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Residential Standard", services=("electric", "water"))
        _tax, jurisdiction = a_tax(
            brazos,
            "Local",
            name="Local · Bexar County",
            kind="percent",
            rate=Decimal("0.020000"),
        )
        attach(brazos, plan, jurisdiction)

        cases = {
            "residential/electric/inside": selectors.plan_tax_rules(
                plan.id, customer_class="residential", premises=INSIDE_CITY, services=("electric",)
            ),
            "commercial/water/outside": selectors.plan_tax_rules(
                plan.id, customer_class="commercial", premises=OUTSIDE_CITY, services=("water",)
            ),
            "government/no-geography": selectors.plan_tax_rules(
                plan.id, customer_class="government", premises=NO_GEOGRAPHY, services=("water",)
            ),
            "no context at all": selectors.plan_tax_rules(plan.id),
        }

    for label, rules in cases.items():
        assert tax_amounts(bill(rules)) == {"Tax Local": Decimal("2.00")}, label


# ── 5 · THE FROZEN FIGURE THIS CHANGE MUST NOT MOVE ────────────────────────
def test_def273_gt1__the_unconditional_625_plus_200_pair_still_taxes_10058_at_830():
    """B5 GT-1 ❄️ FROZEN — 8.25 % on a $100.58 base is **8.30**.

    This is here and not only in the golden suite because the risk this change
    carries is precise: a conditional tax model that fails closed one notch too
    eagerly would drop a rate that has no condition, and every existing tax row
    in every tenant has no condition. If this line ever goes red, the change has
    rewritten a finance-signed figure and must be reverted, not adjusted.
    """
    priced = rating_seam.price_period(
        tariff=rating_seam.TariffConfig(
            service="electric",
            model="flat",
            billed_unit="kWh",
            base_charge=Decimal("18.50"),
            unit_price=Decimal("0.12"),
        ),
        consumption=rating_seam.Quantity(amount=Decimal("684"), unit="kWh"),
        period=FULL_MONTH,
        account=TAXED,
        taxes=(rating_seam.TaxRule(code="STATE+LOCAL", rate=Decimal("0.0825")),),
    )
    assert priced.taxable_subtotal == Decimal("100.58")
    assert priced.tax_total == Decimal("8.30")
    assert priced.total == Decimal("108.88")


# ── 6 · THE ENGINE REFUSES A RULE IT CANNOT PRICE ──────────────────────────
def test_def273_a_tax_rule_with_neither_a_rate_nor_a_flat_amount_refuses():
    """Hard-won law 3 — the unsafe option must be the one you type.

    A rule carrying no figure is a configuration gap. Pricing it as 0.00 would
    print a line saying the authority charges nothing, which is a claim nobody
    made; the engine refuses by name instead, the same way it refuses an
    unregistered pricing model rather than falling back to flat.

    ⚠ **THIS CASE USED TO QUOTE THE SENTENCE AND THE SENTENCE MOVED (DEF-2827,
    2026-08-31).** It asserted `"neither a percent rate nor a flat amount"`.
    `BR-RAT-036` has THREE computation forms and the per-unit one was built on
    2026-08-31 (CR-052 W5 task 16), so the engine now says:

        *"tax rule 'MYSTERY' carries no percent rate, no flat amount and no
        per-unit amount, so there is no arithmetic to perform. A tax has
        exactly one form of calculation and this one states none."*

    The refusal was CORRECT on both days and the tax is still refused BY NAME;
    only the wording widened. A message assertion is a copy of a string with no
    link back to its source, so the two drift with nothing able to see it —
    which is why what is asserted below is the STABLE half: that the rule is
    named (S31.3's exception row needs that) and that the refusal is the
    engine's own unpriceable-tax refusal. The full sentence is quoted HERE, in
    the docstring, where it documents rather than gates.
    """
    with pytest.raises(rating_seam.PricingRefused) as raised:
        rating_seam.price_period(
            tariff=HUNDRED,
            consumption=NO_USAGE,
            period=FULL_MONTH,
            account=TAXED,
            taxes=(rating_seam.TaxRule(code="MYSTERY"),),
        )
    # The engine's own `TaxRuleUnpriceable`, adapted onto billing's refusal type
    # exactly as every other rating refusal is — and it NAMES the rule, so the
    # exception row on S31.3 says which tax nobody priced.
    assert "MYSTERY" in str(raised.value)
    # The STABLE half (DEF-2827): the rule is named and the reason is that the
    # rule states no computation form at all — true whatever the form COUNT is.
    assert "A tax has exactly one form of calculation" in str(raised.value)
    assert "this one states none" in str(raised.value)


# ── 6b · CR-013 PART 4 — AN EXPIRED CERTIFICATE REINSTATES THE TAX ─────────
def test_def273_cr013p4__an_expired_exemption_certificate_reinstates_the_tax_silently():
    """PO verbatim (CR-013 part 4, 2026-08-18): *"Expired exemption certificates
    reinstate the tax on the next run with no exception raised — it's expected
    behaviour."*

    RED ON THE OLD CODE: `accounts.tax_exempt_expires` existed and NOTHING read
    it, so a certificate that expired on 2024-12-31 still zeroed the tax on
    every bill for ever. On a $100.00 base under Bexar's 2.00 %, the account was
    charged **0.00** where it owes **2.00** — a silent UNDER-tax, which is the
    same failure as DEF-273's over-tax pointing the other way: the utility owes
    an authority money it never collected.

    NO EXCEPTION IS RAISED, and that is the part to leave alone. Every other
    stale input in `gather` becomes a `GatherProblem`; this one was ruled
    explicitly not to.
    """
    from datetime import date
    from types import SimpleNamespace

    from apps.billing import gather

    service_date = date(2026, 6, 30)

    def account(**overrides):
        values = dict(tax_exempt=True, tax_exempt_expires=None)
        values.update(overrides)
        return SimpleNamespace(**values)

    # Open-ended certificate — still exempt. A blank date is "no end", never
    # "expired yesterday".
    assert gather._tax_exempt_on(account(), service_date) is True
    # In force on the service date, to the day.
    assert gather._tax_exempt_on(account(tax_exempt_expires=service_date), service_date) is True
    # EXPIRED — the tax comes back, quietly.
    assert (
        gather._tax_exempt_on(account(tax_exempt_expires=date(2024, 12, 31)), service_date) is False
    )
    # Never exempt in the first place.
    assert gather._tax_exempt_on(account(tax_exempt=False), service_date) is False

    # …and the worked money figure the reinstatement is worth on a $100.00 bill
    # under Bexar County's ruled 2.00 %.
    reinstated = rating_seam.price_period(
        tariff=HUNDRED,
        consumption=NO_USAGE,
        period=FULL_MONTH,
        account=rating_seam.AccountContext(currency=USD, tax_exempt=False),
        taxes=(rating_seam.TaxRule(code="Local", rate=Decimal("0.02")),),
    )
    assert tax_amounts(reinstated) == {"Tax Local": Decimal("2.00")}  # was 0.00


# ── 6c · CR-013 PART 4 — THE FIVE SCOPE MECHANISMS ─────────────────────────
def test_def273_cr013p4__all_five_scope_mechanisms_store_and_three_fail_closed(brazos, dana):
    """PO verbatim (CR-013 part 4, TAX-02 step 1): *"how the system decides a
    premise is in scope (city limits, county, state, taxing district, explicit
    premise list)"*.

    All five are STORABLE from this migration — widening an enum later is the
    avoidable cost — and only two can be ANSWERED against what `premises`
    records today. The other three must reach NOBODY rather than everybody, and
    that is asserted here so "not built yet" can never quietly become "applies
    to all".
    """
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Residential Standard")
        for index, kind in enumerate(services.PREMISES_SCOPE_KINDS):
            tax, jurisdiction = a_tax(
                brazos,
                f"Scope {kind}",
                name=f"Scope test {kind}",
                kind="percent",
                rate=Decimal("0.010000"),
                premises_scope_kind=kind,
                premises_scope_value="TX" if kind == "state" else "San Antonio",
            )
            attach(brazos, plan, jurisdiction)
            assert tax.pk is not None, index  # all five STORE (the CHECK allows them)

        reached = {
            rule["code"]
            for rule in selectors.plan_tax_rules(
                plan.id,
                customer_class="commercial",
                premises=INSIDE_CITY,
                services=("electric",),
            )
        }

    # city_limits and state resolve; county, taxing_district and premise_list
    # have no fact to resolve against and fail closed.
    assert reached == {"Scope city_limits", "Scope state"}
    assert set(services.PREMISES_SCOPE_KINDS_RESOLVABLE) == {"city_limits", "state"}

    # And the FLAG wins over the recorded city name the day metering adds it
    # (part 4: "premise city-limit flags drive attachment").
    with tenant_ctx(brazos):
        flagged_out = selectors.plan_tax_rules(
            plan.id,
            customer_class="commercial",
            premises={**INSIDE_CITY, "inside_city_limits": False},
            services=("electric",),
        )
        flagged_in = selectors.plan_tax_rules(
            plan.id,
            customer_class="commercial",
            premises={"city": "Helotes", "state": "TX", "inside_city_limits": True},
            services=("electric",),
        )
    assert "Scope city_limits" not in {rule["code"] for rule in flagged_out}
    assert "Scope city_limits" in {rule["code"] for rule in flagged_in}


# ── 7 · THE MIRRORED VOCABULARY CANNOT DRIFT ───────────────────────────────
def test_def273_the_class_vocabulary_mirrors_the_platform_account_types():
    """`services.TAX_CUSTOMER_CLASSES` is a MIRROR of customers' platform
    catalog (r5 #12 [D5]), kept because rating does not read customers' storage
    (B2 §2). A mirror nobody checks is how the two silently part — this is the
    same guard `apps.payments.allocation` carries for the four line classes it
    mirrors from billing.

    If this goes red, a consumer category was added or renamed and a tax
    restricted to the old spelling now reaches NOBODY (fail-closed), which is
    safe and wrong. Update both, in the same commit.

    ✅ **IT WAS RED FROM 2026-08-24 TO 2026-08-30 AND IT IS GREEN NOW —
    `DEF-738`, closed the way this docstring asked.** `BR-CUS-094` (CONFIRMED,
    PO 2026-08-24) expanded the signed four-code vocabulary to seven —
    *"Expand the signed list to seven"* — plus `government` kept as
    `legacy=True`, so the platform table seeds eight rows while
    `rating.TAX_CUSTOMER_CLASSES` stayed the pre-ruling four. The consequence,
    in a sentence: **no tax could be restricted to an Agricultural,
    Institutional, Municipal or Builder-developer customer**, and rating refused
    those spellings outright. It was a money surface, so it was reported rather
    than patched until BR-RAT-103 and BR-RAT-108 had been read; neither turned
    out to restrict WHO a tax may be scoped to.

    ⚠ **AND THE THING THAT MAKES THIS TEST WORTH KEEPING IS THAT IT STILL ASKS A
    REAL QUESTION.** `TAX_CUSTOMER_CLASSES` is now DERIVED from
    `customers.AccountType`'s declared constants, not from its rows — so this
    assertion has not become a tautology. It compares the vocabulary AS RULED
    against the vocabulary AS SEEDED, and it goes red the day a migration seeds
    a code the ruling does not name, or names one it does not seed.

    ⚠ **AMENDED 2026-09-17 — READ THIS BEFORE YOU "SIMPLIFY" IT.** The PO ruled
    that *"utility can get their own account types"*, so consumers now read the
    ROWS through `seams.selectable_account_type_codes()`. `TAX_CUSTOMER_CLASSES`
    and `seams.account_type_codes()` deliberately DID NOT move: they stay the
    vocabulary AS RULED precisely so this comparison keeps two different sides.
    **Pointing either of them at the table makes this line compare the rows with
    themselves, and it can then never go red** — `DEF-182`, and it is the one
    property the lane implementing that ruling was told not to destroy.

    ⚠ **AND THIS ASSERTION WILL NEED NARROWING WHEN `account_types` BECOMES
    TENANT-OWNED.** It reads EVERY row, so the first tenant that adds a class of
    its own makes it red for a lawful reason. The narrowed form — seeded
    (`is_system=True`) rows only — is already written and passing as
    `tests/test_br_cus_094a_tenant_account_types.py::
    test_the_seeded_rows_still_match_the_ruling`. It is deliberately NOT applied
    here by that lane: the row set is the tenant-ownership lane's to change, and
    two lanes editing one assertion is how a guard ends up asserting nothing.
    """
    from apps.customers import models as customers_models

    live = {row.code for row in customers_models.AccountType.objects.all()}
    assert live == set(services.TAX_CUSTOMER_CLASSES), (
        f"platform account_types are {sorted(live)} and rating mirrors "
        f"{sorted(services.TAX_CUSTOMER_CLASSES)}"
    )


# ── 8 · THE FACTS ACTUALLY REACH THE RESOLVER (hard-won law 2) ─────────────
def test_def273_gather_passes_the_class_and_the_premises_to_the_resolver(monkeypatch):
    """BUILT IS NOT WIRED — four defects in one day, and G13 exists for it.

    The three columns, the three gates and the five seeded rows are all worth
    nothing if `apps/billing/gather.py` never tells the resolver who is being
    billed. This records the kwargs the real gather sends, off a real premises
    row shape, so a future refactor cannot drop one and stay green.
    """
    from types import SimpleNamespace

    from apps.billing import gather

    seen = {}

    def fake_plan_tax_rules(plan_id, service_date, **context):
        seen.update(context)
        return []

    monkeypatch.setattr(
        gather,
        "_resolve",
        lambda module, attribute, kind="selectors": (
            fake_plan_tax_rules if attribute == "plan_tax_rules" else None
        ),
    )
    gather._taxes_for(
        "plan-1",
        None,
        customer_class="commercial",
        premises={"city": "San Antonio"},
        services=("electric", "water"),
        account_id="acct-1",
    )
    # ⚠ AMENDED 2026-08-21 (DEF-383, the Wave D taxes lane). A FOURTH fact now
    # crosses this seam: `account_id`, so rating can find an exemption
    # CERTIFICATE against one authority's tax. The assertion is still exact —
    # that is the whole point of this test, and widening it to a subset would
    # let the next refactor drop a fact and stay green — so the new key is added
    # rather than the equality relaxed. Nothing about the original three moved.
    assert seen == {
        "customer_class": "commercial",
        "premises": {"city": "San Antonio"},
        "services": ("electric", "water"),
        "account_id": "acct-1",
    }

    # …and the two readers that build those facts, off the row shapes billing
    # actually receives.
    account = SimpleNamespace(account_type=SimpleNamespace(code="commercial"))
    assert gather._customer_class(account) == "commercial"
    assert gather._customer_class(SimpleNamespace(account_type=None)) is None

    # ⚠ AMENDED 2026-08-21 (DEF-484/DEF-466, the DEF-438 cutover step-5 lane).
    # TWO IDENTITY KEYS now ride beside the three scope facts, and **this exact
    # assertion is what caught the change** — which is the argument for keeping
    # it exact rather than a subset, made by the test on itself.
    #
    # `premises_id` and `address_line` are NOT scope facts and `rating.selectors
    # .premises_in_scope` never reads them (it asks for `inside_city_limits`,
    # `city` and `state` by name), so nothing about tax attachment moves. They
    # exist because BR-RAT-102 stops a bill when the plan surcharges and the
    # premises' city-limits flag is `None`, and a refusal that cannot name the
    # premises tells a clerk nothing they can act on.
    #
    # The keys are ADDED rather than the equality relaxed, for the reason the
    # DEF-383 note above gives: a subset assertion would let the next refactor
    # drop a fact and stay green.
    unit = SimpleNamespace(
        premises=SimpleNamespace(city="San Antonio", state="TX", postal_code="78205")
    )
    assert gather._premises_geography(unit) == {
        "city": "San Antonio",
        "state": "TX",
        "postal_code": "78205",
        # A row shape that carries no identity yields absences, never the
        # strings "None" — a refusal built from these has to read as English.
        "premises_id": None,
        "address_line": None,
    }
    identified = SimpleNamespace(
        premises=SimpleNamespace(
            id="01a02000-0000-7000-8000-000000000001",
            address_line="9 Quarry Hill Rd",
            city="San Antonio",
            state="TX",
            postal_code="78205",
        )
    )
    assert gather._premises_geography(identified) == {
        "city": "San Antonio",
        "state": "TX",
        "postal_code": "78205",
        "premises_id": "01a02000-0000-7000-8000-000000000001",
        "address_line": "9 Quarry Hill Rd",
    }
    assert gather._premises_geography(SimpleNamespace(premises=None)) == {}


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-254 + DEF-273 (12-governance/10-defect-log.csv) · the decision-log
#         row of 2026-08-18 · 05-prototype/r10-2026-08-16/SMARTBillHub.dc.html
#         (the Taxes & fees table and the tax detail drawer)
# generated: 2026-08-18 by the tax-conditions lane
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — S13 already serves these fields
#            through tax_row) E=deferred(no-frontend-half; the S13 controls the
#            columns need are specified in the lane's write-back, not built here)
#            F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED-PROVED in a clean `git worktree` at HEAD before the change — every
#        case in this file fails with `TypeError: plan_tax_rules() got an
#        unexpected keyword argument 'customer_class'`, which is the honest
#        first failure: the resolver had nowhere to put the facts because the
#        model had nowhere to put the conditions.
# exceptions: the per-unit form (r10's Water Conservation Surcharge, $0.25/kgal
#             above 10 kgal) is SEEDED with its whole condition and prices
#             NOTHING — the seam's TaxRule carries no usage, and approximating a
#             quantity price as a percent would put a wrong number on a real
#             bill. Asserted as an omission by the reference-seed report rather
#             than by a money test, because there is no money to assert.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
