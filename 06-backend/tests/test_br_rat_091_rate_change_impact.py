# ── Trace ──────────────────────────────────────────────
# Rules:    BR-RAT-091 clause 2 (RATE CHANGE: worst-case bill change above 10%
#           needs a second approval — PO ruling 2026-08-20, closing OQ-284) ·
#           BR-RAT-087 (a *_display companion) · BR-RAT-092 / OQ-286 (a percent
#           stores six decimals) · BR-RAT-031 as-modified (no approval hold) ·
#           CLAUDE.md hard rule 2 (never float, never cents)
# Change:   CR-013 part 1 step 4 — the MANDATORY impact analysis
# Defects:  DEF-434 (three of four figures had no endpoint) · DEF-435 (clause 2
#           had no server counterpart — it was a screen constant)
# Questions:OQ-318 (what a filing above the bar does) · OQ-319 (portion or whole
#           bill) · OQ-320 (unmeasured ≠ clear) · OQ-321 (annualised basis)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""BR-RAT-091 clause 2, and the four figures it was told already existed.

THE RATIFIED WORKED EXAMPLE, WHICH THIS FILE PINS AND MAY NOT MOVE
------------------------------------------------------------------
BR-RAT-091, verbatim: *"the water +6% filing moves an 11 kgal household
`$59.00 → $62.54`, `+$3.54`/month, `$38,826`/year across 914 accounts — and it
FLOWS, because 6% is under the bar."*

    +6.00%    $59.00 → $62.54 · +$3.54/mo · $38,826/yr · 914 accounts   FLOWS
    +10.00%   exactly at the bar                                        FLOWS
    +10.50%   above the bar                                             REFUSED
    unmeasured                                                          null

`10%` exactly FLOWS because the rule says **above**. `secondApprovalRequired`
returns `None` — never `False` — for an unmeasured filing, so no surface can
report one as clear (DEF-434).

THE FIXTURE, AND WHY THE NUMBERS ARE THESE NUMBERS
--------------------------------------------------
A two-block inclining water rate, which is the shape r10 draws and the shape a
small utility files: `0–5 kgal @ $4.00`, `5 kgal–∞ @ $6.50`. An 11 kgal
household therefore pays `5 × 4.00 + 6 × 6.50 = 20.00 + 39.00 = $59.00`. The
+6% filing moves both blocks to `$4.24` and `$6.89`, and the same household
pays `21.20 + 41.34 = $62.54`. Nothing is asserted that the engine did not
produce: the prices are the INPUT and both totals come back out of
`engine.price_period`, the call a bill run makes.

The base charge is `$0.00` and is stated on the PLAN, which is where
BR-RAT-012/027 put it — a DEF-277 *"stated, and free"* zero, not an absence. It
is deliberately not moved by the filing: `gather._base_charge_for` REFUSES a
schedule whose non-zero base disagrees with its plan's (OQ-238), so a version
that changes its own base column cannot be measured at all while the plan states
one, and this file asserts that refusal rather than papering over it.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from apps.rating import api, impact, models, selectors, services
from core import errors, sample_fixture

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — env/growth_plan fixtures
from tests.test_us_rat_helpers import FakeUser, api_call, tenant_ctx

pytestmark = pytest.mark.django_db

# The ratified fixture (see the module docstring). Two blocks, 11 kgal.
BEFORE_TIERS = [
    {"from_qty": "0", "to_qty": "5", "unit_price": "4.00"},
    {"from_qty": "5", "to_qty": None, "unit_price": "6.50"},
]
AFTER_TIERS_6PCT = [
    {"from_qty": "0", "to_qty": "5", "unit_price": "4.24"},
    {"from_qty": "5", "to_qty": None, "unit_price": "6.89"},
]
#: 10.5% — the repricing the bar is set to stop. `4.42` / `7.1825` gives
#: `22.10 + 43.095 = 65.195 → 65.20` against `59.00`, i.e. `+10.508475%`.
AFTER_TIERS_10_5PCT = [
    {"from_qty": "0", "to_qty": "5", "unit_price": "4.42"},
    {"from_qty": "5", "to_qty": None, "unit_price": "7.1825"},
]
#: EXACTLY 10%: `$59.00 → $64.90`. `4.40 / 7.15` gives `22.00 + 42.90 = 64.90`,
#: which is `+10.000000%` — the boundary the rule's word *above* decides.
AFTER_TIERS_10PCT = [
    {"from_qty": "0", "to_qty": "5", "unit_price": "4.40"},
    {"from_qty": "5", "to_qty": None, "unit_price": "7.15"},
]
ELEVEN_KGAL = Decimal("11")


# ── fixture plumbing ────────────────────────────────────────────────────────
def _meter_on(env, unit, service="water", uom="kgal", asset_no="M-9001"):
    """A meter on a real unit, written directly — HISTORY SETUP ONLY.

    The same disposition `tests/test_us_met_reads_helpers.commit_read` records
    one module over: *"these rows are the past a test starts from, and building
    each one through a five-step wizard would make the fixture, not the
    behaviour, the thing under test."* Every row still carries its EXPLICIT unit
    (CLAUDE.md hard rule 3).
    """
    from apps.assets import models as asset_models
    from apps.metering import models as metering_models
    from apps.tenancy import models as tenancy_models

    service_row = tenancy_models.Service.objects.get(code=service)
    point = metering_models.ServicePoint.objects.create(
        tenant=env.tenant, unit=unit, service=service_row
    )
    asset_type, _ = asset_models.AssetType.objects.get_or_create(
        tenant=env.tenant,
        code="meter",
        defaults={"name": "Meter", "category": "meters", "is_system": True},
    )
    stage, _ = asset_models.AssetLifecycleStage.objects.get_or_create(
        tenant=env.tenant,
        code="active",
        defaults={"name": "Installed / Active", "behavior_class": "in_service"},
    )
    return asset_models.Asset.objects.create(
        tenant=env.tenant,
        asset_no=asset_no,
        type=asset_type,
        status=stage,
        service_point=point,
        unit=uom,
        multiplier=Decimal("1"),
    )


def _read(env, asset, quantity, uom="kgal", day="2026-07-31"):
    from apps.metering import models as metering_models

    return metering_models.MeterRead.objects.create(
        tenant=env.tenant,
        asset=asset,
        read_at=datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc),
        channel="total",
        current_value=Decimal(str(quantity)),
        prior_value=Decimal("0"),
        multiplier=Decimal("1"),
        consumption=Decimal(str(quantity)),
        unit=uom,
        source="import",
        status="ok",
        lifecycle="committed",
    )


def _state_the_zero_base(env):
    """State this tenant's water base as `$0.00` on the CHARGE CODE too.

    ⚠ **BR-RAT-091's RATIFIED FIGURE AND THE SAMPLE UTILITY'S SIGNED `$8` BASE
    CANNOT BOTH BE TRUE OF ONE TENANT, AND THE PRODUCT IS RIGHT TO SAY SO
    (`DEF-RAT-7140`).** This file's worked example is `$59.00 → $62.54`, which
    is the two usage blocks and a base of `$0.00` stated on the plan — a
    DEF-277 *"stated, and free"* zero. `BR-RAT-088` (PO 2026-08-20) then made
    the CHARGE CODE the first question, and `tests/test_us_rat_helpers`
    auto-declares every enabled service's base code at
    `core.sample_fixture`'s signed figure — `[W] §1 "Base/mo … Water $8"`.
    So the plan said `0.00`, the code said `8.0000`, and
    `gather._base_charge_for` refused the pair by name:

        GatherProblem: Two base charges for water. Clear 0.00 on the plan.

    **That refusal is the product working, not a bug** — a bill produced from
    whichever of two disagreeing figures the code reached first is `DEF-154`.
    What was wrong is the FIXTURE: it asked for a utility that charges no
    water base and then declared one for it.

    **NOTHING SIGNED MOVES HERE.** `$8` is the SAMPLE utility's figure and
    stays `$8`; `BASE_CHARGE_AMOUNTS` already seeds trash and sewer at `0`, so
    a `$0.00` base is a lawful thing for a utility to have. `$59.00 → $62.54`,
    `+$3.54`/month and `+6.00%` are re-measured unchanged with this in place.

    It is declared the way a utility would — on the Charge codes screen,
    through `create_charge`, with `is_base` set — and BEFORE the schedule, so
    `declare_base_charge_code`'s idempotent read finds it and leaves it alone
    rather than writing `$8` over it. `DEF-528`'s invariant is untouched: the
    service still HAS a base code, and it states zero.
    """
    with tenant_ctx(env.tenant):
        services.create_charge(
            env.admin,
            {
                "code": "BASE-W",
                "name": "Water base service",
                "service": "water",
                "charge_type": "recurring",
                "amount_rule": "flat",
                "amount": "0.00",
                "is_base": True,
             "effective_from": "2000-01-01"},
        )


def _silver_creek_water(env, households=(ELEVEN_KGAL,)):
    """One water schedule, one plan, and one metered household per quantity.

    Returns `(schedule, plan, units)`. The plan states the base charge — `$0.00`,
    a DEF-277 stated zero — so `_base_charge_for` takes the PLAN's figure and the
    whole bill is the two usage blocks.
    """
    env.enable("water")
    env.set_billed_uom("water", "kgal")
    _state_the_zero_base(env)
    schedule = env.tiered_schedule("Res Water · Inclining", "water", BEFORE_TIERS)
    plan = env.plan(
        "Residential",
        "RES",
        [{"service": "water", "base_charge": "0.00", "tariff": schedule["id"]}],
        publish=True,
    )
    units = []
    for index, quantity in enumerate(households):
        unit = env.unit(label=f"Unit {index + 1}")
        env.assign(plan["id"], unit)
        asset = _meter_on(env, unit, asset_no=f"M-90{index:02d}")
        _read(env, asset, quantity)
        units.append(unit)
    return schedule, plan, units


def _file_new_version(env, schedule_id, tiers, effective_from="2027-01-01"):
    with tenant_ctx(env.tenant):
        return services.create_rate_schedule_version(
            env.admin,
            schedule_id,
            {
                "name": "Res Water · Inclining",
                "service": "water",
                "model": "tiered",
                "uom": "kgal",
                "effective_from": effective_from,
                "structure": {"tiers": tiers},
                "reason": "Annual cost-of-service filing",
            },
        )


def _impact(env, schedule_id, **kwargs):
    with tenant_ctx(env.tenant):
        return selectors.rate_change_impact(schedule_id, **kwargs)


# ── the ratified worked example ─────────────────────────────────────────────
def test_br_rat_091__the_ratified_water_filing_is_59_00_to_62_54_and_it_FLOWS(env):
    """`$59.00 → $62.54`, `+$3.54`/month, `+6.00%` — and it is written.

    Both totals come out of `engine.price_period`. If this test moves, either
    the engine's arithmetic moved or the impact analysis stopped pricing through
    it; BR-RAT-091's figure is finance-shown and neither is allowed to happen
    quietly.
    """
    schedule, _plan, _units = _silver_creek_water(env)
    _file_new_version(env, schedule["id"], AFTER_TIERS_6PCT)

    figures = _impact(env, schedule["id"], effective_from=date(2027, 1, 1))

    assert figures["accounts_affected"] == 1
    assert figures["accounts_priced"] == 1
    assert figures["worst_case_pct"] == "6.000000"
    assert figures["worst_case_pct_display"] == "6.00%"
    assert figures["average_change"] == "3.540000"
    assert figures["average_change_display"] == "3.54"
    # 6% is under the bar, so the filing needs no second approval — and the
    # answer is a real `False`, not the `None` an unmeasured filing gets.
    assert figures["second_approval_required"] is False
    assert figures["second_approval_threshold_pct_display"] == "10.00%"


def test_br_rat_091__the_two_totals_are_the_ENGINES_own(env):
    """`$59.00` and `$62.54` are produced, not asserted into existence.

    Priced through `selectors._price_one` — the same `engine.price_period` call
    `apps/billing` makes — so this fails if the engine ever prices an 11 kgal
    household on a 4.00/6.50 ladder at anything but 59.00.
    """
    schedule, _plan, _units = _silver_creek_water(env)
    with tenant_ctx(env.tenant):
        tariff = selectors.tariff_or_404(schedule["id"])
        version = selectors.latest_version(tariff)
        inputs = selectors.pricing_inputs_for_version(version, date(2026, 8, 1))
        before = selectors._price_one(
            selectors._engine_tariff(inputs, "water", Decimal("0")),
            ELEVEN_KGAL,
            "kgal",
            "USD",
        )
    assert before == Decimal("59.00")


# ── the bar itself: 10 flows, 10.5 does not, unmeasured is neither ──────────
def test_br_rat_091__10_5_pct_is_REFUSED_and_the_version_is_not_written(env):
    """Above the bar, the write fails CLOSED and names the rule (OQ-318).

    BR-RAT-091 says such a filing needs a SECOND APPROVAL; BR-RAT-031
    as-modified deleted the rate-schedule approval workflow, so there is nowhere
    for one to land. A CONFIRMED rule whose precondition cannot be satisfied
    must not be reported as satisfied.
    """
    schedule, _plan, _units = _silver_creek_water(env)

    with pytest.raises(errors.BizError) as raised:
        _file_new_version(env, schedule["id"], AFTER_TIERS_10_5PCT)
    assert "BR-RAT-091" in str(raised.value) or "second_approval_required" in str(raised.value)

    # The refusal fired inside the atomic block, so nothing was left behind.
    with tenant_ctx(env.tenant):
        tariff = selectors.tariff_or_404(schedule["id"])
        assert len(selectors.tariff_versions(tariff)) == 1


def test_br_rat_091__EXACTLY_10_pct_flows_because_the_rule_says_ABOVE(env):
    """`$59.00 → $64.90` is `+10.000000%`, and it is written.

    The boundary is the rule's own word. A `>=` here would refuse a filing the
    PO was shown as lawful, and no figure on any screen would look different.
    """
    schedule, _plan, _units = _silver_creek_water(env)
    _file_new_version(env, schedule["id"], AFTER_TIERS_10PCT)

    figures = _impact(env, schedule["id"], effective_from=date(2027, 1, 1))
    assert figures["worst_case_pct"] == "10.000000"
    assert figures["second_approval_required"] is False


def test_br_rat_091__an_unmeasured_filing_is_null_and_NEVER_false(env):
    """A schedule nobody is on: no accounts, no reads, no worst case.

    `null` is the third state. A `False` here would let the API answer, the
    audit row and the screen each report a rate change nobody measured as CLEAR
    — which is the whole of DEF-434 (OQ-320).
    """
    env.enable("water")
    env.set_billed_uom("water", "kgal")
    schedule = env.tiered_schedule("Unused Water", "water", BEFORE_TIERS)
    _file_new_version(env, schedule["id"], AFTER_TIERS_10_5PCT)  # 10.5% and it is WRITTEN

    figures = _impact(env, schedule["id"], effective_from=date(2027, 1, 1))
    assert figures["accounts_affected"] == 0
    assert figures["worst_case_pct"] is None
    assert figures["second_approval_required"] is None
    assert figures["second_approval_required"] is not False


def test_br_rat_091__the_pure_gate_holds_all_four_states(env=None):
    """The gate as a function, so the figure is provable without a database.

    This is the SERVER's copy of the four assertions
    `RateScheduleWizard.test.tsx` makes on the screen's copy. Both must hold, or
    the wire has a bar on one side and a different bar on the other — which is
    exactly the state DEF-435 describes.
    """
    assert impact.RATE_CHANGE_SECOND_APPROVAL_PCT == Decimal("10")
    assert impact.second_approval_required(Decimal("6"))[0] is False
    assert impact.second_approval_required(Decimal("10"))[0] is False
    assert impact.second_approval_required(Decimal("10.5"))[0] is True
    assert impact.second_approval_required(None)[0] is None
    assert impact.second_approval_required(None)[0] is not False
    # The threshold travels beside the answer, the shape clause 1 uses.
    assert impact.second_approval_required(None)[1] == Decimal("10")


# ── the annualised figure, at the ratified scale ────────────────────────────
def test_br_rat_091__914_accounts_at_plus_3_54_a_month_is_38_826_a_year():
    """The ratified `$38,826`/year, asserted at its own scale.

    `+$3.54 × 914 × 12 = $38,826.72`, which is the `$38,826` the PO was shown
    (r10 prints this figure to whole dollars). Pure arithmetic over
    `impact.summarise`, so the scale costs no database: 914 rows through the
    engine would make this a performance test rather than an arithmetic one.

    OQ-321 asks whether the year should instead restate twelve BILLED months.
    On a flat year the two agree, which is why that answer cannot move `$38,826`.
    """
    changes = tuple(
        impact.AccountChange(
            unit_id=str(index),
            plan_id="RES",
            plan_name="Residential",
            quantity=ELEVEN_KGAL,
            unit="kgal",
            before=Decimal("59.00"),
            after=Decimal("62.54"),
        )
        for index in range(914)
    )
    figures = impact.summarise(changes, accounts_affected=914)

    assert figures.accounts_priced == 914
    assert figures.worst_case_pct == Decimal("6.000000")
    assert figures.average_change == Decimal("3.54")
    assert figures.monthly_revenue_change == Decimal("3235.56")
    assert figures.annualised_revenue_change == Decimal("38826.72")
    assert int(figures.annualised_revenue_change) == 38826


# ── the worst case is the WORST, not the average ───────────────────────────
def test_br_rat_091__the_worst_case_is_the_heaviest_user_not_the_mean(env):
    """Three households on one schedule; the gate reads the largest increase.

    `1 kgal`, `11 kgal` and `40 kgal` all move by the same +6% on this ladder,
    so the interesting property here is the one that would break silently: an
    account that cannot be priced must NOT be averaged in at `0.00%` and drag
    the worst case toward the middle.
    """
    schedule, plan, _units = _silver_creek_water(
        env, households=(Decimal("1"), ELEVEN_KGAL, Decimal("40"))
    )
    # A fourth account on the same plan with NO meter and no read at all.
    unmetered = env.unit(label="Unit 4 (never read)")
    env.assign(plan["id"], unmetered)
    _file_new_version(env, schedule["id"], AFTER_TIERS_6PCT)

    figures = _impact(env, schedule["id"], effective_from=date(2027, 1, 1))
    assert figures["accounts_affected"] == 4
    assert figures["accounts_priced"] == 3
    assert figures["accounts_unpriced"] == 1
    assert figures["unpriced_reasons"] == {"no_metered_consumption": 1}
    assert figures["worst_case_pct"] == "6.000000"


# ── what is counted but not priced, and never priced at zero ───────────────
def test_br_rat_091__a_read_in_the_wrong_unit_is_UNPRICED_not_converted(env):
    """BR-RAT-038: the engine holds no conversion factor and refuses by name.

    The account stays in `accounts_affected` and lands in `accounts_unpriced`
    with the engine's own exception named. Pricing it at zero would report a
    household as unaffected by a rate change that will bill them.
    """
    env.enable("water")
    env.set_billed_uom("water", "kgal")
    _state_the_zero_base(env)
    schedule = env.tiered_schedule("Res Water · Inclining", "water", BEFORE_TIERS)
    plan = env.plan(
        "Residential",
        "RES",
        [{"service": "water", "base_charge": "0.00", "tariff": schedule["id"]}],
        publish=True,
    )
    unit = env.unit(label="Unit A")
    env.assign(plan["id"], unit)
    asset = _meter_on(env, unit, uom="gal")
    _read(env, asset, Decimal("11000"), uom="gal")  # gallons, not kgal
    _file_new_version(env, schedule["id"], AFTER_TIERS_6PCT)

    figures = _impact(env, schedule["id"], effective_from=date(2027, 1, 1))
    assert figures["accounts_affected"] == 1
    assert figures["accounts_priced"] == 0
    assert figures["worst_case_pct"] is None
    assert figures["second_approval_required"] is None
    assert list(figures["unpriced_reasons"]) == ["engine:UomMismatch"]


def test_br_rat_091__a_zero_before_price_has_NO_percentage(env):
    """A household that consumed nothing has no percentage change.

    `bill_change_pct(0, x)` is undefined, not infinite and not zero. The account
    is counted and reported as unpriced rather than averaged in.
    """
    assert impact.bill_change_pct(Decimal("0"), Decimal("5")) is None
    assert impact.bill_change_pct(Decimal("59"), None) is None
    assert impact.bill_change_pct(None, Decimal("62.54")) is None


# ── the endpoint, through the route a screen calls ─────────────────────────
def test_br_rat_091__the_endpoint_serves_the_four_figures(env):
    """DEF-434: `GET /rate-schedules/{id}/impact`, which did not exist.

    Until this route existed, `GET /rate-schedules/{id}` served `used_by_plans`
    and `applied_to_accounts` and RAT-03 step 4 drew three stated absences.
    """
    schedule, _plan, _units = _silver_creek_water(env)
    _file_new_version(env, schedule["id"], AFTER_TIERS_6PCT)

    response = api_call(
        api.rate_schedule_impact,
        "get",
        user=FakeUser(env.owner.id),
        # A4 gives Billing Clerk *View* on `plans_rates`, and reading what a rate
        # change would do is a read. The ENFORCEMENT is on the write, which stays
        # System-Admin-only, so nothing depends on a client having asked first.
        role="billing_clerk",
        tenant=env.tenant,
        query={"effective_from": "2027-01-01"},
        tariff_id=str(schedule["id"]),
    )
    assert response.status_code == 200
    body = response.data
    assert body["accounts_affected"] == 1
    assert body["worst_case_pct_display"] == "6.00%"
    assert body["annualised_revenue_change_display"] == "42.48"  # 3.54 x 1 x 12
    assert body["second_approval_required"] is False
    assert body["second_approval_threshold_pct_display"] == "10.00%"
    # CR-013 part 1 asks for the breakdown "per class" and nothing joins an
    # affected unit to a customer class — named, never relabelled (OQ-319).
    assert body["by_class_unavailable_reason"] == "OQ-319"
    assert body["accounts_by_plan"][0]["accounts"] == 1


# ── DEF-499 · the SIXTH writer, and the one with no gate ───────────────────
def test_def499__the_BULK_batch_is_gated_too_because_it_writes_versions_itself(
    env, job_store, audit_rows
):
    """One clerk, one click, every schedule up 40% — and nothing objected.

    `_apply_batch_to_schedule` is the only writer of `tariff_versions` that does
    NOT go through `_write_version`: it calls `TariffVersion.objects.create()`
    and then rebuilds the size rows, seasons, tiers, windows, capacity and
    demand children itself. So the gate this lane put on
    `create_rate_schedule_version` covered five writers and missed the SIXTH —
    and the sixth is the one that can do the most damage, because a bulk uplift
    moves every schedule a utility has at once.

    +40% on an 11 kgal household is `$59.00 → $82.60`, which is `40.00%` — four
    times the bar. It refuses, exactly as the batch already refuses a schedule
    with no version at all (`rating.bulk.entity_without_version`), and BR-RAT-040
    makes the consequence the WHOLE batch: `apply_rate_change_batch` wraps every
    entity in one `transaction.atomic()`, so nothing is written for any of them.
    """
    schedule, _plan, _units = _silver_creek_water(env)
    audit_rows.clear()
    with tenant_ctx(env.tenant):
        accepted = services.request_rate_change_batch(
            env.admin,
            {
                "entities": [{"type": "schedule", "id": schedule["id"]}],
                "change": {"kind": "percent", "value": "40.0"},
                "effective_from": "2027-01-01",
                "reason": "Cost-of-service repricing",
            },
        )
    with pytest.raises(errors.BizError) as raised:
        services.run_rate_change_job(accepted["job_id"])
    assert "second_approval_required" in str(raised.value)

    with tenant_ctx(env.tenant):
        tariff = selectors.tariff_or_404(schedule["id"])
        # One atomic batch: the schedule still prices on its single version.
        assert len(selectors.tariff_versions(tariff)) == 1
    figures = _impact(env, schedule["id"], effective_from=date(2027, 1, 1))
    # And with nothing new filed there is nothing to compare, so the answer is
    # the third state rather than a reassuring `false`.
    assert figures["second_approval_required"] is None


def test_def499__a_bulk_uplift_UNDER_the_bar_still_lands(env, job_store, audit_rows):
    """The gate must not turn the bulk path off. +3% is the routine annual
    adjustment `test_us_rat_011_tc1` files, and it goes through untouched."""
    schedule, _plan, _units = _silver_creek_water(env)
    audit_rows.clear()
    with tenant_ctx(env.tenant):
        accepted = services.request_rate_change_batch(
            env.admin,
            {
                "entities": [{"type": "schedule", "id": schedule["id"]}],
                "change": {"kind": "percent", "value": "3.0"},
                "effective_from": "2027-01-01",
                "reason": "Board order 2026-12 annual adjustment",
            },
        )
    services.run_rate_change_job(accepted["job_id"])

    with tenant_ctx(env.tenant):
        tariff = selectors.tariff_or_404(schedule["id"])
        assert len(selectors.tariff_versions(tariff)) == 2
    figures = _impact(env, schedule["id"], effective_from=date(2027, 1, 1))
    assert figures["second_approval_required"] is False
    assert figures["worst_case_pct_display"] == "3.00%"


# ── the SEEDED tenant's own rate case, priced end to end ───────────────────
def test_br_rat_091__silver_creeks_OWN_water_filing_reads_5_28_pct_not_6_pct(env, capsys):
    """The fixture's figures, not this file's — and they do NOT read `+6.00%`.

    `core/sample_fixture.py` is the seeded tenant: `WATER_TIERS` is
    `0–5 @ $4.00`, `5–15 @ $6.50`, `15+ @ $8.00`; `WATER_BASE` is **`$8.00`**;
    and `WATER_V2_UPLIFT` is **`1.06`** — *"+6%, the rate case r10 draws on
    Residential Water"*, i.e. BR-RAT-091's own filing, with its prices DERIVED
    (`4.24 / 6.89 / 8.48`) rather than retyped.

    ⚠ **PRICED ON THAT FIXTURE, THE +6% FILING MOVES AN 11 kgal HOUSEHOLD FROM
    `$67.00` TO `$70.54` — `+$3.54`/month, AND `+5.283582%`, NOT `+6%`.** The
    dollar change is exactly the rule's `+$3.54`; the PERCENTAGE is not the
    rule's `6%`, and the reason is one line of arithmetic: **the filing raises
    the tier prices and does not touch the `$8.00` base**, so the base sits in
    the denominator and dilutes the increase. `59.00 × 1.06 = 62.54` only holds
    for a bill that is ALL usage.

    **Neither figure is wrong and this test asserts both.** BR-RAT-091's
    `$59.00 → $62.54` is ratified and is pinned by the tests above, on a bill
    with a stated `$0.00` base. This one is what the product will actually
    compute for Silver Creek. **The gap between them is `OQ-319`** — what the
    `10%` bar is measured against — and it is bigger than it looks: the same
    filing reads `6.00%` on a no-base bill, `5.28%` on Silver Creek's water
    bill, and about `1.5%` on a whole bill carrying trash and sewer too. Both
    of those clear `10%`; a repricing near the bar would not clear all three.
    """
    env.enable("water")
    env.set_billed_uom("water", "kgal")
    seeded = [
        {"from_qty": lo, "to_qty": hi, "unit_price": price}
        for lo, hi, price in sample_fixture.WATER_TIERS
    ]
    filed = [
        {"from_qty": lo, "to_qty": hi, "unit_price": price}
        for lo, hi, price in zip(
            [lo for lo, _hi, _p in sample_fixture.WATER_TIERS],
            [hi for _lo, hi, _p in sample_fixture.WATER_TIERS],
            # The fixture's own derivation, called rather than copied.
            sample_fixture._uplift(sample_fixture.WATER_TIERS, sample_fixture.WATER_V2_UPLIFT),
        )
    ]
    # v1 opens on the fixture's first billed period, exactly as the seeder does;
    # v2 opens 2026-08-01, which is `WATER_V2_FROM`. The DATES are the
    # load-bearing part (BR-RAT-007) — v2 must not re-price the billed June.
    schedule = env.tiered_schedule(
        "Res Water · Inclining",
        "water",
        seeded,
        effective_from=sample_fixture.PERIODS[0]["start"].isoformat(),
    )
    plan = env.plan(
        "Residential",
        "SCW-RES",
        # [W] §1 "Base/mo … Water $8" — the seeded tenant's real base.
        [{"service": "water", "base_charge": sample_fixture.WATER_BASE, "tariff": schedule["id"]}],
        publish=True,
    )
    unit = env.unit(label="Unit A")
    env.assign(plan["id"], unit)
    asset = _meter_on(env, unit)
    _read(env, asset, ELEVEN_KGAL)
    _file_new_version(env, schedule["id"], filed, effective_from=sample_fixture.WATER_V2_FROM)

    figures = _impact(env, schedule["id"], effective_from=date(2026, 8, 1))

    # $8.00 base + 5x4.00 + 6x6.50 = 8.00 + 20.00 + 39.00 = $67.00
    # $8.00 base + 5x4.24 + 6x6.89 = 8.00 + 21.20 + 41.34 = $70.54
    assert figures["average_change_display"] == "3.54"  # the rule's own +$3.54
    assert figures["worst_case_pct"] == "5.283582"
    assert figures["worst_case_pct_display"] == "5.28%"
    assert figures["second_approval_required"] is False
    assert figures["annualised_revenue_change_display"] == "42.48"  # 3.54 x 1 x 12
    # Printed so the lane report can quote the endpoint rather than a hand sum.
    with capsys.disabled():
        print(
            f"\n  SEEDED TENANT · water +6% filing: {figures['worst_case_pct_display']} "
            f"worst case · {figures['average_change_display']}/month · "
            f"second approval required: {figures['second_approval_required']}"
        )


def test_br_rat_091__a_base_written_on_the_version_moves_nothing_the_code_owns_it(env):
    """OQ-238, reached from the other side — and since `BR-RAT-088` there is only
    ONE side.

    ⚠ **AMENDED 2026-10-01 (CR-157-BRC10 wave B), RED ON 9910f15a8 (CR-156-BRC10
    wave A) AND EVERY TIP SINCE.** This case asserted the filing was UNPRICED,
    because `gather._base_charge_for` once refused when the plan's base and the
    version's base disagreed. `BR-RAT-088` (PO 2026-08-20) made the CHARGE CODE
    the only source of a service's base and retired both columns, so neither
    the plan's `15.00` nor a `15.90` written onto the new version is read any
    more. The guarantee that matters is the opposite one now, and it is
    asserted exactly: the filing is priced, its whole change is the usage
    (`+$3.54`), and the base on both sides is the code's `$8.00` —
    `$3.54 / ($8.00 + $59.00) = 5.283582%`. A version base leaking back into
    the arithmetic moves both figures and turns this red.
    """
    env.enable("water")
    env.set_billed_uom("water", "kgal")
    schedule = env.tiered_schedule("Res Water · Inclining", "water", BEFORE_TIERS)
    plan = env.plan(
        "Residential",
        "RES",
        [{"service": "water", "base_charge": "15.00", "tariff": schedule["id"]}],
        publish=True,
    )
    unit = env.unit(label="Unit A")
    env.assign(plan["id"], unit)
    asset = _meter_on(env, unit)
    _read(env, asset, ELEVEN_KGAL)
    _file_new_version(env, schedule["id"], AFTER_TIERS_6PCT)
    with tenant_ctx(env.tenant):
        tariff = selectors.tariff_or_404(schedule["id"])
        models.TariffVersion.objects.filter(tariff=tariff, effective_from=date(2027, 1, 1)).update(
            base_charge=Decimal("15.90")
        )

    figures = _impact(env, schedule["id"], effective_from=date(2027, 1, 1))
    assert figures["accounts_priced"] == 1
    assert figures["unpriced_reasons"] == {}
    assert figures["average_change"] == "3.540000"  # usage only — the 15.90 moved nothing
    assert figures["worst_case_pct"] == "5.283582"  # 3.54 on $8.00 code base + $59.00 usage
    assert figures["second_approval_required"] is False
