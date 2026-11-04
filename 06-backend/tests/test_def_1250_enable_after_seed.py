# ── Trace ──────────────────────────────────────────────
# Defect:   **DEF-1250** — switching a service on AFTER the sample data is
#           loaded left every account on a plan that could not price it, and the
#           idempotent replay was never going to fix it. **DEF-2490** — OQ-317
#           closed on 2026-08-27 (option A, the `$18.00` monthly trash base
#           RETIRED) and the closure never reached the fixture. **DEF-2491** /
#           **DEF-2492** — the two halves deliberately not built here.
# Rules:    **BR-TEN-063** (the sample load is idempotent) as READ AT ITS OWN
#           GRAIN — see `BR-RAT-830` / `BR-MET-831` · BR-TEN-068 (a sample plan
#           a real account is on becomes the operator's own) · BR-TEN-012 (a
#           fixture never overwrites what the tenant already priced) ·
#           BR-TEN-060 (a gap is NAMED, never a silent skip) · BR-RAT-037 (a
#           published plan's content change bumps its version and states a
#           reason) · BR-RAT-111 (the filing record) · BR-MET-119 (a unit may
#           only take a service its ADDRESS offers) · BR-BIL-300 (which services
#           a bill charges is derived from the UNIT) · BR-RAT-090 (an unmetered
#           service's quantity is a COUNT of its assets — 3 carts x `$15.00` =
#           `$45.00`) · CLAUDE.md rule 2 (money) · rule 7 (audited)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""DEF-1250 — a utility switches trash on, reloads the sample data, and gets billed for it.

**WHAT A UTILITY CAN DO NOW THAT IT COULD NOT.** Provision on water and sewer,
run the demo, then decide to sell refuse: switch **trash** on at Settings ->
Services & UoM and press *Load sample data* again. Before this lane that second
press produced a trash RATE SCHEDULE that no plan pointed at, no offer at any
address, no service point on any unit and **not one line on any bill**. Now the
plan gains trash, the estate gains trash, the carts land, and the three-cart
household on the CR-019 walkthrough unit bills **3 x $15.00 = $45.00**.

**THE DEFECT WAS A GRAIN MISMATCH, NOT A MISSING RULE — WHICH IS WHY IT READ AS
CORRECT IN BOTH FILES.** `BR-TEN-063` says a replay must not double anything.
Taxes, base charge codes, rate schedules, schedule versions and discounts each
implement that keyed on their OWN natural key, so a replay adds an object that
is genuinely new. **Plans were keyed on the plan's `code` and premises on the
address**, so an existing parent was skipped whole — contents included — and a
service switched on afterwards could never reach either. *"If the parent exists,
add nothing"* is strictly STRONGER than the rule it implements: strong enough to
also refuse what is genuinely absent.

**MEASURED ON A BOOTED TENANT BEFORE THE FIX** — provision `water + sewer`, load
the sample data, switch trash on, load again:

    AFTER RUN 1 (trash OFF)
      plan SCW-RES  services=[('water', 8.000000), ('sewer', 0.000000)]
      service points: {'water': 75, 'sewer': 49}
    AFTER REPLAY (trash ON)
      plan SCW-RES  services=[('water', 8.000000), ('sewer', 0.000000)]
      schedules:  ... + 'Sample - Trash (monthly, not measured)'
      service points: {'water': 75, 'sewer': 49}

The schedule arrived — it is keyed per object. The plan and the estate did not.

⚠ **THE DEFECT ROW'S OWN MECHANISM IS HALF STALE AND THIS FILE CORRECTS IT.**
`DEF-1250` says *"metering.sample_data seeds trash service points regardless of
the flag"*. It has not since CR-039 wave A (`DEF-795`) replaced the literal
`water/sewer/trash` intersection with `fixture.estate_plan(enabled...)`. The
metering half of this defect is the MIRROR image: an existing address is never
revisited, so a later-enabled service reaches no offer and no point at all. Both
halves are real and neither is the one that was written down.

**RED PROOF (r11 step 2d).** Every case below was run against an untouched copy
of the tree at this lane's starting commit; the lane report quotes the failures.
The lines to break: `_reconcile_plan_services`' call site in
`apps/rating/sample_data.seed_sample_records` (tc1, tc4, tc6 go red) and
`_reconcile_estate_services`' call site in `apps/metering/sample_data`
(tc5, tc6). The mutation worth naming is guard 2 — send `_plan_payloads`' own
list to `update_plan` instead of the plan's restated rows and `tc3` bills an
operator's retyped water base back to the fixture's `$8.00`, silently, with
every other test in this repo still green.
"""

from decimal import Decimal

import pytest

from apps.metering import models as metering_models
from apps.rating import models as rating_models
from apps.rating import sample_data as rating_sample
from apps.rating import services as rating_services
from apps.tenancy import services as tenancy_services
from core import sample_fixture as fixture

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import seed_physical_series, staff_actor, tenant_ctx
from tests.test_us_ten_helpers import brazosbend_payload, provisioned_tenant

pytestmark = pytest.mark.django_db

#: BR-RAT-090 / OQ-303 (PO 2026-08-21) — the price of ONE cart.
PER_CART = Decimal("15.00")
#: OQ-317, CLOSED 2026-08-27 on option A: the workbook's `$18.00` monthly trash
#: base is RETIRED. Typed as the RULING rather than read from the fixture, so a
#: fixture edit that quietly restores `$18.00` fails here instead of agreeing
#: with itself (`DEF-2490` is exactly that failure, one ruling earlier).
RULED_TRASH_BASE = Decimal("0")
#: The CR-019 walkthrough figure, ratified: 3 carts x $15.00.
THREE_CARTS = Decimal("45.00")


def _water_sewer_tenant(name, subdomain, email):
    """A utility that sells water and sewer and does NOT sell trash."""
    tenant, _ = provisioned_tenant(
        brazosbend_payload(
            name=name,
            subdomain=subdomain,
            services=["water", "sewer"],
            owner={
                "full_name": "T Owner",
                "email": email,
                "password": "S3cure!passw0rd",
                "phone": None,
            },
        )
    )
    seed_physical_series(tenant)
    return tenant, staff_actor(tenant, "system_admin", f"admin.{subdomain}@example.test")


def _seed_rating_and_estate(actor):
    """The two blocks this lane owns, in `SAMPLE_MODULES`' own order.

    The whole orchestrator is not run for most cases: it seeds ten blocks and
    two bill runs, and the fact under test is what the rating and metering
    blocks do to a tenant they have already seeded once.
    """
    rating_sample.seed_sample_records(actor)
    from apps.metering import sample_data as metering_sample

    metering_sample.seed_sample_records(actor)


def _plan_services(code):
    plan = rating_models.RatePlan.objects.get(code=code)
    return {
        row.service.code: row.base_charge
        for row in rating_models.PlanService.objects.filter(rate_plan=plan).select_related(
            "service"
        )
    }


# ══════════════════════════════════════════════════════════════════════════
# (1) THE DELIVERABLE — the plan gains the service that was switched on
# ══════════════════════════════════════════════════════════════════════════
def test_def_1250_tc1__enabling_a_service_then_reloading_puts_it_on_the_plan(brazos, dana):
    """**Switch trash on, load the sample data again, and the plan prices it.**

    RED before this lane: `SCW-RES` held `water` and `sewer` after the replay
    exactly as it did before it, because `seed_sample_records` skipped a plan
    whose `code` it already had.
    """
    tenant, actor = _water_sewer_tenant("Reload Water Co", "reloadwater", "a@reloadwater.test")
    with tenant_ctx(tenant):
        _seed_rating_and_estate(actor)
        assert "trash" not in _plan_services(
            rating_sample.PLAN_RESIDENTIAL
        ), "the tenant does not sell trash yet — the test would be vacuous"

        tenancy_services.update_tenant_service(actor, "trash", {"enabled": True})
        _seed_rating_and_estate(actor)

        after = _plan_services(rating_sample.PLAN_RESIDENTIAL)
        assert "trash" in after, (
            "the plan still does not price trash. A service switched on after the sample "
            "plans were published can never reach them, so every account on this plan is "
            "badged for a service its plan cannot price (DEF-1250)"
        )
        # And the plan actually POINTS at the trash schedule, not merely at a
        # base row: a service row with no tariff prices no consumption.
        priced = {
            row["service"]
            for row in rating_sample._current_plan_services(
                str(rating_models.RatePlan.objects.get(code=rating_sample.PLAN_RESIDENTIAL).id)
            )
            if row.get("tariff")
        }
        assert "trash" in priced, "the plan gained a trash row with no rate schedule on it"


# ══════════════════════════════════════════════════════════════════════════
# (2) BR-TEN-063 STILL HOLDS — a replay writes nothing and doubles nothing
# ══════════════════════════════════════════════════════════════════════════
def test_def_1250_tc2__a_third_load_adds_nothing_and_doubles_nothing(brazos, dana):
    """The rule the fix must not weaken, asserted as a count and as a version.

    `plans.version` is the sharp end: BR-RAT-037 bumps it on every content
    change to a published plan, so a reconciliation that ran unconditionally
    would file a rate change every time anybody pressed the button.
    """
    tenant, actor = _water_sewer_tenant("Twice Water Co", "twicewater", "a@twicewater.test")
    with tenant_ctx(tenant):
        _seed_rating_and_estate(actor)
        tenancy_services.update_tenant_service(actor, "trash", {"enabled": True})
        _seed_rating_and_estate(actor)

        plan = rating_models.RatePlan.objects.get(code=rating_sample.PLAN_RESIDENTIAL)
        rows_before = rating_models.PlanService.objects.filter(rate_plan=plan).count()
        version_before = plan.version
        points_before = metering_models.ServicePoint.objects.count()

        _seed_rating_and_estate(actor)

        plan.refresh_from_db()
        assert rating_models.PlanService.objects.filter(rate_plan=plan).count() == rows_before
        assert plan.version == version_before, (
            "a replay that changes nothing still filed a rate change (BR-RAT-037) — "
            "the reconciliation is not idempotent"
        )
        assert metering_models.ServicePoint.objects.count() == points_before


# ══════════════════════════════════════════════════════════════════════════
# (3) ADDITIVE, NEVER A REWRITE — the operator's own edits survive
# ══════════════════════════════════════════════════════════════════════════
def test_def_1250_tc3__the_reconciliation_never_overwrites_what_the_operator_priced(brazos, dana):
    """BR-TEN-012 — a fixture does not reprice a tenant's own figures.

    ⚠ **THE MUTATION THIS CASE EXISTS FOR.** `update_plan` REPLACES the service
    set, so sending `_plan_payloads`' own list would be one line shorter and
    would silently reset a retyped water base to the fixture's `$8.00`. Nothing
    else in this repo would go red.
    """
    tenant, actor = _water_sewer_tenant("Edited Water Co", "editedwater", "a@editedwater.test")
    with tenant_ctx(tenant):
        _seed_rating_and_estate(actor)
        plan = rating_models.RatePlan.objects.get(code=rating_sample.PLAN_RESIDENTIAL)
        current = rating_sample._current_plan_services(str(plan.id))
        for row in current:
            if row["service"] == "water":
                row["base_charge"] = "9.99"
        rating_services.update_plan(
            actor, str(plan.id), {"services": current, "reason": "the operator's own price"}
        )

        tenancy_services.update_tenant_service(actor, "trash", {"enabled": True})
        _seed_rating_and_estate(actor)

        after = _plan_services(rating_sample.PLAN_RESIDENTIAL)
        assert after["water"] == Decimal("9.990000"), (
            "the replay reverted the operator's own water base to the fixture's figure — "
            "a sample load is not a rewrite (BR-TEN-012)"
        )
        assert "trash" in after


# ══════════════════════════════════════════════════════════════════════════
# (4) BR-TEN-068 — a PROMOTED plan is the operator's, and is not touched
# ══════════════════════════════════════════════════════════════════════════
def test_def_1250_tc4__a_promoted_plan_is_left_alone(brazos, dana):
    """A sample plan a real account is on stops being sample data (BR-TEN-068).

    Adding a priced service to it would be a fixture changing a live tariff.
    """
    tenant, actor = _water_sewer_tenant("Promo Water Co", "promowater", "a@promowater.test")
    with tenant_ctx(tenant):
        _seed_rating_and_estate(actor)
        rating_models.RatePlan.objects.filter(code=rating_sample.PLAN_RESIDENTIAL).update(
            is_sample=False
        )
        tenancy_services.update_tenant_service(actor, "trash", {"enabled": True})
        _seed_rating_and_estate(actor)

        assert "trash" not in _plan_services(rating_sample.PLAN_RESIDENTIAL), (
            "the fixture added a priced service to a plan that is now the operator's own "
            "(BR-TEN-068) — that is a rate change nobody asked for"
        )
        # The plan that is STILL sample data did gain it, so the guard is a
        # guard and not a switch that turned the whole feature off.
        assert "trash" in _plan_services(rating_sample.PLAN_COMMERCIAL)


# ══════════════════════════════════════════════════════════════════════════
# (5) THE ESTATE — the address offers it and the units take it
# ══════════════════════════════════════════════════════════════════════════
def test_def_1250_tc5__the_seeded_estate_gains_the_service_too(brazos, dana):
    """BR-MET-119 / BR-BIL-300 — without this the plan's new price bills nobody.

    A bill's services are derived from the UNIT's service points (BR-BIL-300),
    and a unit may only take a service its ADDRESS offers (BR-MET-119). An
    address that is never revisited therefore blocks the whole chain, carts
    included: `assets.sample_data` plants its four `container_cart` assets
    through `create_asset`, which refuses with `metering.service_not_at_premises`
    while the address offers water and sewer only.
    """
    tenant, actor = _water_sewer_tenant("Estate Water Co", "estatewater", "a@estatewater.test")
    with tenant_ctx(tenant):
        _seed_rating_and_estate(actor)
        assert not metering_models.ServicePoint.objects.filter(service__code="trash").exists()

        tenancy_services.update_tenant_service(actor, "trash", {"enabled": True})
        _seed_rating_and_estate(actor)

        offered = [
            row.services_available
            for row in metering_models.Premises.objects.filter(is_sample=True)
            if "trash" in (row.services_available or [])
        ]
        assert offered, "no seeded address offers trash, so no unit can ever take it"
        assert metering_models.ServicePoint.objects.filter(service__code="trash").exists(), (
            "the units gained no trash service point, so BR-BIL-300 derives no trash "
            "service and no bill can charge for it"
        )
        # BR-MET-119's deliberate hold-back survives: one address offers less
        # than the utility sells, so the refusal stays demonstrable on a demo.
        narrow = metering_models.Premises.objects.filter(
            premise_no=__import__(
                "apps.metering.sample_data", fromlist=["x"]
            ).NARROW_OFFER_PREMISE_NO
        ).first()
        if narrow is not None:
            assert "trash" not in (narrow.services_available or [])


# ══════════════════════════════════════════════════════════════════════════
# (6) THE RULED FIGURE — OQ-317 option A, and the walkthrough's $45.00
# ══════════════════════════════════════════════════════════════════════════
def test_def_1250_tc6__the_seeded_trash_price_is_the_ruled_one(brazos, dana):
    """**DEF-2490.** OQ-317 closed on 2026-08-27 retiring the `$18.00` monthly
    trash base, and the fixture went on seeding it — DEF-491's own shape, one
    ruling later.

    Worked here rather than described: the plan states a `$0.00` base, the
    schedule prices `$15.00` per **cart**, so the three-cart household on the
    CR-019 walkthrough unit owes **$45.00** and not `$63.00`.
    """
    tenant, actor = _water_sewer_tenant("Ruled Water Co", "ruledwater", "a@ruledwater.test")
    with tenant_ctx(tenant):
        _seed_rating_and_estate(actor)
        tenancy_services.update_tenant_service(actor, "trash", {"enabled": True})
        _seed_rating_and_estate(actor)

        bases = _plan_services(rating_sample.PLAN_RESIDENTIAL)
        assert bases["trash"] == RULED_TRASH_BASE, (
            f"the seeded trash base is {bases['trash']} — OQ-317 closed on option A "
            "on 2026-08-27 and RETIRED the $18.00 monthly base"
        )
        # A stored ZERO, never an omission: a blank base means *this size is not
        # served* and stops the bill (CR-013 part 1 / DEF-277).
        assert bases["trash"] is not None

        tariff = rating_models.Tariff.objects.get(name=rating_sample.SCHEDULE_TRASH)
        version = rating_models.TariffVersion.objects.filter(tariff=tariff).first()
        assert version.uom == "cart", "CLAUDE.md rule 3 — the price carries the unit it is per"
        tier = rating_models.RateTier.objects.filter(tariff_version=version).first()
        assert tier.unit_price == Decimal("15.000000")
        assert Decimal("3") * PER_CART == THREE_CARTS  # the ratified walkthrough

        # And the base charge code agrees with the plan to the cent (DEF-455).
        from apps.rating import selectors as rating_selectors
        from core.pagination import ListParams

        codes = {row["code"]: row for row in rating_selectors.charge_list(ListParams(per=1000))}
        assert Decimal(codes["BASE-T"]["amount"]) == RULED_TRASH_BASE

        assert fixture.TRASH_BASE == "0"
        # The workbook figure is RECORDED, not deleted — a superseded signed
        # figure stays readable — and nothing seeds it any more.
        assert fixture.TRASH_FLAT == "18.00"


# ══════════════════════════════════════════════════════════════════════════
# (7) PREVENTION (a) — say what this tenant sells that no plan prices
# ══════════════════════════════════════════════════════════════════════════
def test_def_1250_tc7__the_run_names_every_enabled_service_no_plan_prices(brazos, dana):
    """`DEF-1250` prevention (a), as a READ.

    The reconciliation repairs the SAMPLE plans for the services the sample
    estate is shaped for. A utility that switches **gas** on is not helped by
    it at all: nothing the fixture builds prices gas, and under BR-BIL-300 /
    OQ-670 every account whose unit takes it bills `$0.00` for it. That is
    DEF-1060's silence wearing a line item, so the run says it by name
    (BR-TEN-060).
    """
    tenant, actor = _water_sewer_tenant("Gassy Water Co", "gassywater", "a@gassywater.test")
    with tenant_ctx(tenant):
        _seed_rating_and_estate(actor)
        assert (
            rating_sample.enabled_services_no_published_plan_prices() == ()
        ), "every enabled service is priced right after a clean seed"
        tenancy_services.update_tenant_service(actor, "gas", {"enabled": True})
        assert "gas" in rating_sample.enabled_services_no_published_plan_prices()
        # It is a READ: naming the gap changes nothing.
        assert not rating_models.PlanService.objects.filter(service__code="gas").exists()


# ══════════════════════════════════════════════════════════════════════════
# (8) THE WALKTHROUGH, END TO END — the bins land and 3 x $15.00 is countable
# ══════════════════════════════════════════════════════════════════════════
def test_def_1250_tc8__the_carts_land_and_the_walkthrough_unit_counts_three(brazos, dana):
    """**The last link, and it is the one that was easiest to argue and hardest
    to believe: the BINS.**

    `BR-RAT-090` prices an unmetered service by a COUNT of its assets on the
    unit, OBSERVED and never typed, and `assets.sample_data` seeds exactly the
    three cases the rule needs — three carts on one unit, one on another, none
    on a third. That block is idempotent per ASSET NUMBER, so it would happily
    plant them on a replay. **It could not, and the reason was two modules
    away:** `create_asset` calls `metering.ensure_service_point`, which refuses
    with `metering.service_not_at_premises` unless the ADDRESS offers the
    service (`BR-MET-119`) — and an already-seeded address was never revisited.

    So this case asserts the thing the whole lane is for, on the real chain and
    not on the argument: switch trash on, reload, and the CR-019 walkthrough
    unit counts **3**, which at the seeded `$15.00` a cart is **$45.00**.

    RED before this lane, and the failure is the mechanism itself rather than a
    wrong number: `core.errors.ValidationError: VAL-005
    (metering.service_not_at_premises)`. The test never reaches the count —
    `create_asset` refuses the first cart, because the address still offers
    water and sewer only. (This docstring said the count *"answered 0"* until it
    was actually run; the real failure is one step earlier and is better, and a
    stated failure nobody produced is exactly the claim hard-won law 1 is
    about.)
    """
    tenant, actor = _water_sewer_tenant("Walkthru Water Co", "walkthruwater", "a@wtw.test")
    with tenant_ctx(tenant):
        from apps.assets import sample_data as assets_sample
        from apps.metering import selectors as metering_selectors

        _seed_rating_and_estate(actor)
        assets_sample.seed_sample_records(actor)

        tenancy_services.update_tenant_service(actor, "trash", {"enabled": True})
        _seed_rating_and_estate(actor)
        assets_sample.seed_sample_records(actor)

        unit = metering_models.Unit.objects.filter(
            is_sample=True, deleted_at__isnull=True
        ).order_by("unit_no")[fixture.CART_UNIT_WITH_THREE]
        counted = metering_selectors.billable_asset_count(
            str(unit.id), "trash", fixture.PERIODS[-1]["end"]
        )
        assert counted == 3, (
            f"the walkthrough unit counts {counted} carts, not 3 — the carts could not be "
            "planted because the address still offered water and sewer only (BR-MET-119)"
        )
        # BR-RAT-090's ratified arithmetic, over the price this tenant actually
        # carries rather than over a literal.
        tariff = rating_models.Tariff.objects.get(name=rating_sample.SCHEDULE_TRASH)
        version = rating_models.TariffVersion.objects.filter(tariff=tariff).first()
        per_cart = rating_models.RateTier.objects.get(tariff_version=version).unit_price
        assert Decimal(counted) * per_cart == Decimal("45.000000")
        # And the plan can price it, which is the other half: a count with no
        # tariff to multiply is DEF-1250 wearing a number.
        assert "trash" in _plan_services(rating_sample.PLAN_RESIDENTIAL)
