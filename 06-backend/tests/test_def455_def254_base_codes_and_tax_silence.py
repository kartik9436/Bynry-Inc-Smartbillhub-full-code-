# ── Trace ──────────────────────────────────────────────
# Story:    US-RAT-008 (charge codes) · US-TEN-003 (the S62 setup checklist)
#           Screens: S10/PLN-03 step 4 · S12 · S62
# Rules:    BR-RAT-088 (the CHARGE CODE owns the base amount; a plan displays it,
#           never defines it) · BR-RAT-108 (a charge code prices ONE customer
#           class; the base is narrowed by SERVICE -> ACCOUNT TYPE -> METER SIZE)
#           · BR-RAT-120 (the R1-R7 chain still has no production caller) ·
#           BR-TEN-015 (the checklist is computed from LIVE data, never stored)
# Defects:  DEF-455 (the sample seeder writes no base charge codes, so PLN-03
#           step 4 is unwalkable) · DEF-528 (a PARTIAL declaration arms a
#           tenant-wide gate) · DEF-254 (tax jurisdictions are seeded and tax
#           rates are not, and nothing warns)
# ───────────────────────────────────────────────────────
"""Two silences the product could not see, and the money each one hides.

**DEF-455.** `BR-RAT-088` moved the base amount off the plan and onto the charge
code on 2026-08-20; the FIXTURE was never moved with it. `grep` for `is_base` and
`BASE-` across `apps/rating/sample_data.py` returned zero, so PLN-03 step 4 read
*"No base charge code for this service"* for water, sewer AND trash on the tenant
the product ships. The gate was behaving correctly — it had no input.

**DEF-254.** Tax authorities are seeded at provisioning and their RATES are not,
so a tenant that declines the sample data issues every bill with no tax at all
and the S62 checklist reads finished.

⚠ **THE LOAD-BEARING ASSERTION IN THIS FILE IS THE ONE THAT PROVES NO MONEY
MOVED.** `DEF-455`'s own prevention says to seed the codes *"and STOP seeding
`plan_services.base_charge` in the same commit"*, and doing that today would bill
every seeded account `$0.00` for base: the live path reads the PLAN's column
(`gather._base_charge_for`) and `BR-RAT-120` (CONFIRMED 2026-08-28) states that
the chain reading the CODE's column *"still has no production caller"*. So both
sources exist for now, they agree to the cent by construction, and
`test_def455_tc4` is what stops them drifting apart.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.rating import models as rating_models
from apps.rating import sample_data, selectors
from apps.tenancy import selectors as tenancy_selectors
from apps.tenancy import service_size_classes
from core import sample_fixture as fixture

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from apps.rating.charge_prices import flat_amount as _flat  # CR-156-BRC10: the amount is a dated row
from apps.rating.constants import ALL_SIZES
from tests.test_us_met_helpers import (
    brazosbend_payload,
    provisioned_tenant,
    seed_physical_series,
    staff_actor,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


@pytest.fixture()
def silver_creek(growth_plan, identity_seam):  # noqa: F405 — W0 helper fixtures
    """The water/sewer/trash estate `apps/rating/sample_data` actually prices —
    it seeds schedules for those three services and for nothing else, because
    there is no signed figure for an electric or gas tariff."""
    tenant, _ = provisioned_tenant(
        brazosbend_payload(
            name="Silver Creek Water",
            subdomain="silvercreekwater",
            services=["water", "sewer", "trash"],
        )
    )
    seed_physical_series(tenant)
    return tenant


@pytest.fixture()
def seeded(silver_creek):
    """Through rating's REAL seam, so this file cannot drift from what a tenant
    receives when somebody presses "Load sample data"."""
    actor = staff_actor(silver_creek)
    with tenant_ctx(silver_creek):
        sample_data.seed_sample_records(actor)
        yield silver_creek, actor


def _codes() -> dict[str, rating_models.Charge]:
    return {
        row.code: row
        for row in rating_models.Charge.objects.select_related("service").filter(
            deleted_at__isnull=True, is_base=True
        )
    }


def _base_of(charge: rating_models.Charge) -> Decimal:
    """WHAT THIS CODE CHARGES THE SMALLEST CONNECTION — `DEF-6440`.

    ⚠ **THIS HELPER EXISTS BECAUSE THE BASE MOVED HOUSE, NOT BECAUSE THE RULE
    CHANGED.** Until 2026-09-07 every seeded base code stated ONE flat
    `charges.amount` and the two tests below read it directly. `DEF-6440` gave
    water, electric and gas a per-size ladder, and CR-013 part 2 gives a code
    exactly ONE basis — `_validate_charge` refuses a code holding both a scalar
    and a table, and `resolve_charge_codes` refuses the BILL — so a laddered
    code's `amount` is now `None` and the figure lives in `charge_code_amounts`.

    **THE GUARANTEE UNDER TEST IS UNTOUCHED.** The code and the plan must state
    the same base to the cent or `gather._base_charge_for` refuses the account
    by name. What moved is which column the code keeps it in, so this reads the
    ladder's FIRST rung — the smallest ratified size, whose multiplier is `1` by
    construction — which is exactly the figure `plan_services.base_charge` still
    states. Had this helper compared against any other rung, TC4 would go green
    while the plan and the code disagreed, which is the `DEF-154` failure the
    test exists to catch.

    A code with NO ladder keeps its flat amount and is returned unchanged, so
    TC4's sewer `$0.00` and trash `$0.00` are the same assertions they were.
    """
    rows = {
        row.size_class: row.amount
        for row in rating_models.ChargeCodeAmount.objects.filter(
            charge_id=charge.id, killed_at__isnull=True
        ).exclude(size_class=ALL_SIZES)
    }
    if not rows:
        return _flat(charge)
    smallest, _name = service_size_classes.size_classes_for_service(charge.service.code)[0]
    assert smallest in rows, (
        f"{charge.code} prices per size and states nothing for {smallest}, the "
        "smallest size — every connection of that size would refuse rather than "
        "bill (DEF-6440), and the plan's own figure would have nothing to agree with"
    )
    return rows[smallest]


def test_def455_tc1__every_seeded_service_has_a_declared_base_code(seeded):
    """DEF-455 · the absence PLN-03 step 4 was printing is gone.

    ⚠ **ALL THREE OR NONE — this is DEF-528 and it is why the assertion is a set
    comparison and not three separate `assert x in codes`.**
    `_guard_base_charge_code` SELF-ACTIVATES per tenant: it returns early while a
    tenant has NO `is_base` code and refuses the moment it has SOME. Declaring
    one code therefore arms a tenant-wide gate for EVERY service, and the seed
    once declared `BASE-W` and not `BASE-E` — after which `seed_demo` could not
    create a single electric schedule on a fresh database.
    """
    codes = _codes()
    assert {row.service.code for row in codes.values()} == {"water", "sewer", "trash"}


def test_def455_tc2__water_states_two_amounts_separated_by_CLASS(seeded):
    """BR-RAT-108's own worked example, on the tenant it was written about.

    *"Silver Creek's water base is `$8.00` residential and `$15.00` commercial —
    one service, two amounts, and a charge code is per TENANT where the plan
    column it replaces was per PLAN."* Without the class column the two could not
    both exist, and the only migration available was two codes distinguished by
    NAME — which `BR-RAT-088`'s own docstring warns against because name-matching
    fails silently.
    """
    codes = _codes()
    # `_base_of` and not `.amount` since `DEF-6440`: water is priced per
    # connection size now, so the code states $8.00 at 5/8" rather than
    # $8.00 flat. Same figure, same rule, different column.
    assert _base_of(codes["BASE-W"]) == Decimal(fixture.WATER_BASE)
    assert _base_of(codes["BASE-W-COM"]) == Decimal(fixture.COMMERCIAL_WATER_BASE)

    # ⚠ **THE RULE, NOT A LITERAL LIST — this assertion was STALE and RED.**
    # It read `== ["residential"]` and `== ["commercial"]`. `base_code_classes`
    # derives the list from `PLAN_CLASS_ACCOUNT_TYPES`, and `municipal` rides
    # with `residential` so a civic account is covered by SOME base code — a
    # class no code claims bills nothing at all, silently. The literal could
    # not survive that widening, and could not survive the next one either.
    #
    # What BR-RAT-108 actually requires is that the two codes SEPARATE the
    # classes, so that is what is asserted: each covers its own, neither
    # claims the other's, and no account can match both (`DEF-468` refuses a
    # bill where two base codes survive the narrowing).
    residential = set(codes["BASE-W"].applies_to_customer_classes)
    commercial = set(codes["BASE-W-COM"].applies_to_customer_classes)
    assert "residential" in residential and "commercial" not in residential
    assert "commercial" in commercial and "residential" not in commercial
    assert not residential & commercial, (
        f"{sorted(residential & commercial)} is claimed by BOTH water base codes; "
        "an account of that type would refuse rather than bill (DEF-468)"
    )
    # And the civic account is covered by one of them — DEF-3282's own fix,
    # pinned so it cannot be quietly narrowed again.
    assert "municipal" in residential | commercial


def test_def455_tc3__a_base_code_is_never_also_auto_applied(seeded):
    """BR-RAT-117 makes `recurring` + `auto_apply` land on every bill as an
    ADDITIONAL line and says in terms that it *"does not move the base"*. A base
    that was also auto-applied would be the `$24.00`-for-one-`$12.00`-base double
    that BR-RAT-088 exists to forbid — §A3 prices that failure at `$23,069.50` a
    month across 1,247 connections, *"and no test catches it, because both rows
    are individually correct."* This is that test.
    """
    for row in _codes().values():
        assert row.auto_apply is False, f"{row.code} would bill its base twice"


def test_def455_tc4__the_code_and_the_plan_state_THE_SAME_FIGURE(seeded):
    """⚠ **THE ONE THAT PROVES NO BILL MOVED, AND THE ONE TO READ BEFORE
    RETIRING `plan_services.base_charge`.**

    The live path takes its base from `gather._base_charge_for(service,
    plan_base, schedule_base)` — the PLAN's column. `BR-RAT-088`'s R4 reads the
    CODE's column and runs only in `apps/billing/resolution_shadow.py`;
    `BR-RAT-120` (CONFIRMED 2026-08-28) says so in as many words: *"the chain
    still has no production caller"*. So declaring these codes changes nothing a
    customer is charged **only while the two sources agree**. This pins that.

    When R4 gains a production caller, this test is the safe place to delete the
    plan's figure from: it goes red the moment the two disagree, which is exactly
    the `DEF-154` failure (a base sourced from the wrong column billed `$0.00` on
    every bill for weeks) caught one commit earlier.
    """
    codes = _codes()
    residential = selectors.plan_detail(sample_data.residential_plan_id())
    by_service = {line["service"]: line["base_charge"] for line in residential["services"]}
    assert Decimal(by_service["water"]) == _base_of(codes["BASE-W"])
    assert Decimal(by_service["sewer"]) == _base_of(codes["BASE-S"])
    assert Decimal(by_service["trash"]) == _base_of(codes["BASE-T"])

    commercial = selectors.plan_detail(sample_data.commercial_plan_id())
    com_by_service = {line["service"]: line["base_charge"] for line in commercial["services"]}
    assert Decimal(com_by_service["water"]) == _base_of(codes["BASE-W-COM"])


def test_def455_tc5__seeding_twice_writes_nothing(seeded):
    """BR-TEN-063 — idempotent by natural key, like every other block here."""
    _tenant, actor = seeded
    assert sample_data.seed_sample_base_charge_codes(actor) == 0


def test_def254_tc1__authorities_with_no_prices_are_REPORTED(seeded):
    """DEF-254 · the silence becomes a sentence.

    A tenant with authorities and no rates bills every customer no tax, and
    before this the S62 `rates_taxes` item read `done` from the schedule count
    alone — so the checklist said finished over a wide-open gap.
    """
    from django.utils import timezone

    # Take the PRICES away and leave the AUTHORITIES — which is exactly the
    # state of a real tenant that declined the sample data.
    rating_models.Tax.objects.update(deleted_at=timezone.now())

    gap = selectors.tax_pricing_gap()
    assert gap["jurisdictions"] > 0
    assert gap["priced"] == 0

    item = next(
        row
        for row in tenancy_selectors.checklist()["items"]
        if row["item"] == "rates_taxes"
    )
    assert item["notice"] == {
        "code": "tax_rates_unpriced",
        "jurisdictions": gap["jurisdictions"],
        "priced": 0,
    }
    # ⚠ `done` IS UNTOUCHED ON PURPOSE. Flipping it would strand a utility that
    # genuinely charges no tax on a checklist they can never complete — the same
    # failure wearing the other coat. The fact is reported; a human decides.
    assert item["done"] is True


def test_def254_tc2__a_priced_tenant_is_told_nothing(seeded):
    """No notice where there is no gap. A warning that fires on a correctly
    configured tenant is noise, and noise is how a real warning gets ignored."""
    assert selectors.tax_pricing_gap()["priced"] > 0
    item = next(
        row
        for row in tenancy_selectors.checklist()["items"]
        if row["item"] == "rates_taxes"
    )
    assert "notice" not in item


def test_def254_tc3__the_scaffold_is_never_given_an_invented_rate(seeded):
    """⚠ **THE RULING THIS FIX MUST NOT REVERSE.** The rate-less jurisdiction
    scaffold is deliberate: *a wrong rate charges real customers real money*. The
    seam counts and reports; it must never create a `taxes` row. Pinned because
    "just seed a rate" is the obvious fix and it is the wrong one.
    """
    before = rating_models.Tax.objects.count()
    selectors.tax_pricing_gap()
    tenancy_selectors.checklist()
    assert rating_models.Tax.objects.count() == before


def test_def515_def202_tc1__THE_EXACT_PAYLOAD_THE_SCREEN_EMITS_IS_ACCEPTED(seeded):
    """⚠ **THE SEAM BETWEEN THE TWO HALVES BUILT TODAY, AND THE ONE ASSERTION
    NEITHER SIDE'S OWN SUITE COULD MAKE.**

    `DEF-466` and `DEF-515` were both filed for the same class: *"the engine's
    own tests pass a tariff carrying the factor directly, so the arithmetic is
    proven and the SOURCING is untested."* The frontend suite proves what
    `planPayload` BUILDS; the backend suite proves what `create_plan` STORES.
    **Nothing asserted that the first is accepted by the second** — which is
    exactly how a field with storage, validation, a serializer and a screen can
    still not work.

    So this posts the payload shape `PlanWizard.planPayload` emits, key for key,
    and reads back what the database holds:

      * `outside_city_factor` as a STRING, trimmed, never re-rounded;
      * `outside_city_exempt` on EVERY service row including the false one;
      * `deposit_rules` with a real figure and no row for a category left blank.

    If a lane renames a key on either side, this goes red and neither suite
    alone would have.
    """
    _tenant, actor = seeded
    from apps.rating import services as rating_services

    account_type_id = sample_data._account_type_id("residential")
    plan = rating_services.create_plan(
        actor,
        {
            "name": "Payload seam check",
            "code": "SEAM-CHECK",
            "description": None,
            # ⚠ **THE LIST, NOT THE SINGULAR — `DEF-RAT-6980`.** `DEF-RAT-5768`
            # replaced `rate_plans.account_type_id` with `account_type_ids`
            # (`[]` meaning EVERY class) on 2026-09-23, and `create_plan`
            # refuses an unknown field BY NAME, so this call died on
            # `VAL-002 rating.unknown_field` for four days. The wizard this
            # case exists to mirror already posts the list —
            # `planWizardBetaWalk.dom.test.tsx` asserts the singular key is
            # ABSENT from its payload — so the front end was never wrong here.
            # ⚠ The `deposit_rules` row below keeps the SINGULAR on purpose:
            # `plan_deposit_rules.account_type_id` is a different column on a
            # different table and the ruling did not touch it.
            "account_type_ids": [account_type_id],
            "budget_billing": False,
            "effective_from": None,
            "effective_to": None,
            "eligibility": {},
            # BR-RAT-102 — what the wizard posts for "surcharge by 15 percent".
            "outside_city_factor": "1.15",
            "services": [
                {"service": "water", "outside_city_exempt": False},
                {"service": "sewer", "outside_city_exempt": True},
            ],
            "charge_rules": [],
            # BR-RAT-020/023 — one category priced, the rest simply absent.
            "deposit_rules": [{"account_type_id": account_type_id, "amount": "150.0000"}],
            "tax_rules": [],
            "discounts": [],
        },
    )

    stored = selectors.plan_detail(plan["id"])
    # ⚠ Served at the column's SIX places — storage precision, not a display
    # string. The wizard trims the zeros for its input and posts back what the
    # utility typed, so `1.15` in and `1.150000` out is the round trip working.
    assert Decimal(stored["outside_city_factor"]) == Decimal("1.15")
    exempt = {line["service"]: line["outside_city_exempt"] for line in stored["services"]}
    assert exempt == {"water": False, "sewer": True}
    # ⚠ **`150.000000`, NOT `150.0000` — and this assertion was WRONG first time
    # round, which is worth leaving written down.** `selectors._money` serves
    # every decimal at the COLUMN's six places: that is STORAGE precision (DB-3),
    # not money rounding, and half-up 2dp happens only at invoice-line
    # finalization (BR-RAT-003). Compared as a `Decimal` so this pins the VALUE
    # and not the serialiser's zero-padding — a string compare here would go red
    # on a precision change that moved no money, which is the kind of brittle
    # assertion that gets deleted rather than fixed.
    assert len(stored["deposit_rules"]) == 1
    rule = stored["deposit_rules"][0]
    assert rule["account_type_id"] == str(account_type_id)
    assert Decimal(rule["amount"]) == Decimal("150.00")
    # CLAUDE.md hard rule 2 — CHAR(3), defaulted by the server because the screen
    # deliberately offers no per-deposit currency control.
    assert rule["currency"] == "USD"


# ── Lifecycle ─────────────────────────────────────────────
# generated: 2026-08-28 by the rating write-path lane (DEF-455 · DEF-254)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
