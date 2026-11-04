# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-798 (2026-08-26) — *"MONTHLY USAGE SUMS ACROSS CHANNELS,
#           UNIT-BLIND: monthly_usage.month_figure adds consumption over every
#           usable read for the account, so a demand peak-delta lands in the
#           ENERGY total and TOU window reads are double-counted against total.
#           Measured: 684 + 14 = 698 kWh where the truth is 684 kWh."*
# Change:   CR-038 · ADDITION 2026-08-26 — W5 task 8 (trailing-12-month
#           consumption on account AND meter). PO verbatim: *"We ahve to
#           calcualet last 12 month consumption from these readings and display
#           it on account and meters"*.
#           Screens: S21 (Usage tab — the surface the defect corrupts) ·
#           S50 (asset detail — the new meter strip)
# Rules:    BR-MET-106 (the stored month) · BR-MET-135 (`generation` is NEVER
#           summed with consumption) · BR-AST-029 (`export` likewise) ·
#           BR-RAT-014 (demand measures kW, not kWh) · BR-MET-059 (the channel
#           model is EXTENSIBLE — which is why there is no default branch) ·
#           CLAUDE.md hard rule 3 (an explicit unit, always)
# Questions: OQ-421 CLOSED 2026-08-27 — *"(b) Store it per meter too"*; the
#           asset/channel grain is BR-MET-141 and TC-10 below is amended,
#           not replaced, with the RED it produced quoted in its docstring
# ───────────────────────────────────────────────────────
"""DEF-798 — the register-blind sum, and the meter strip built on the fix.

**THE MEASURED NUMBER IS THE TEST.** DEF-798 states 684 + 14 = 698 kWh where
the truth is 684, and TC-1 below builds exactly that account: one meter, a
684 kWh energy total for July and a 14 kW demand peak-delta on the same meter
on the same day. Before the fix the stored July figure is 698; after it, 684.

⚠ **WHY THE EXISTING MIXED-UNIT GUARD COULD NOT HAVE CAUGHT THIS, ASSERTED
RATHER THAN CLAIMED (TC-2).** `MeterRead.unit` is stamped per ASSET, so the
demand row and the energy row on one meter both read `kWh` even though the
peak is really kW. OQ-358's guard compares units and sees one. The test builds
the defect with matched units on purpose, because that is the shape that
actually shipped.
"""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from apps.assets import services as asset_services
from apps.customers import services as customers_services
from apps.metering import asset_usage
from apps.metering import models as metering_models
from apps.metering import monthly_usage as usage_rules
from apps.metering import monthly_usage_reads as usage_reads
from apps.metering import monthly_usage_service as usage_service
from apps.metering.monthly_usage_asset import AssetMonthlyUsage
from apps.metering import services as metering_services
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models

from tests import identity_fixtures
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    FakeUser,
    brazos,
    lonestar,
    make_premises,
    make_unit,
    marcus,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


# ── fixture plumbing (same shape as test_br_met_106_monthly_usage) ──────────
def _plan(tenant, service_code="electric", name="Small Commercial"):
    service = tenancy_models.Service.objects.get(code=service_code)
    plan, _ = rating_models.RatePlan.objects.get_or_create(
        tenant=tenant,
        name=name,
        defaults={"code": name.lower().replace(" ", "-"), "status": "published"},
    )
    tariff, _ = rating_models.Tariff.objects.get_or_create(
        tenant=tenant, name=f"{name} — {service_code}", service=service
    )
    rating_models.PlanRateSchedule.objects.get_or_create(
        tenant=tenant, rate_plan=plan, service=service, defaults={"tariff": tariff}
    )
    return plan


def _account_on(actor, tenant, *, service="electric"):
    premises = make_premises(actor)
    unit = make_unit(actor, premises["id"], label="Unit A")
    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(_plan(tenant, service).id)}
    )
    metering_services.ensure_service_point(unit["id"], service)
    account = customers_services.create_account(
        actor,
        {
            "unit_id": unit["id"],
            "account_type": "residential",
            "opened_at": "2024-01-05",
            "contact": {"full_name": "Sarah Chen", "email": "sarah@example.test"},
            # `BR-CUS-1024` (PO 2026-09-01) — the door refuses an account whose
            # customer identifies nobody, and this fixture's own name went in above.
            # ONE shape for every fixture in the suite: tests/identity_fixtures.py.
            "customer": identity_fixtures.customer_block("Sarah Chen", account_type="residential"),
        },
    )
    return account, unit


def _meter(actor, unit_id, *, asset_no, service="electric", uom="kWh"):
    return asset_services.create_asset(
        actor,
        {
            "type": "meter",
            "asset_no": asset_no,
            "service": service,
            "unit": uom,
            "read_method": "walk_by",
            "multiplier": "1",
            "unit_id": unit_id,
            "install_date": "2024-01-05",
            "status": "active",
        },
    )


def _read(tenant, account_id, asset_id, *, day, consumption, channel="total", unit="kWh"):
    """One committed read on ONE REGISTER — HISTORY SETUP only.

    ⚠ `unit` defaults to the ASSET's UoM for every channel deliberately: that
    is what the product actually stores (`MeterRead` law 3), and it is the
    reason the OQ-358 unit guard cannot see DEF-798.
    """
    return metering_models.MeterRead.objects.create(
        tenant_id=tenant.id,
        account_id=account_id,
        asset_id=asset_id,
        read_at=datetime(day.year, day.month, day.day, tzinfo=timezone.utc),
        channel=channel,
        current_value=Decimal("1000"),
        consumption=Decimal(str(consumption)),
        unit=unit,
        source="import",
        status="ok",
        lifecycle="committed",
    )


def _july(account_id):
    return metering_models.MonthlyUsage.objects.filter(
        account_id=account_id,
        period_month=date(2026, 7, 1),
        superseded_by_id__isnull=True,
    ).first()


# ══════════════════════════════════════════════════════════════════════════
# TC-1 · DEF-798's OWN NUMBER: a demand peak-delta must not join the energy
#        total. 684 + 14 = 698 was the defect; 684 is the truth.
# ══════════════════════════════════════════════════════════════════════════
def test_def_798_tc1__a_demand_peak_delta_never_lands_in_the_energy_total(brazos, marcus):
    with tenant_ctx(brazos):
        account, unit = _account_on(marcus, brazos)
        meter = _meter(marcus, unit["id"], asset_no="M-4412")
        # The energy the customer used, on the `total` register.
        _read(brazos, account["id"], meter["id"], day=date(2026, 7, 15), consumption="684.000000")
        # BR-RAT-014's MAX-DEMAND register, on the SAME meter, the SAME day.
        # Its figure is a delta between two maxima in kW. Nobody consumed 14 of
        # anything; before the fix this was added to the 684 above.
        _read(
            brazos,
            account["id"],
            meter["id"],
            day=date(2026, 7, 15),
            consumption="14.000000",
            channel="demand",
        )

        usage_service.recompute_account(account["id"], actor=marcus)

        row = _july(account["id"])
        assert row is not None, "July was read; BR-MET-106 states a figure for it"
        assert row.quantity == Decimal("684.000000"), (
            "DEF-798: the demand peak-delta joined the energy sum — "
            f"got {row.quantity}, the defect's own measured wrong answer was 698"
        )
        assert row.unit == "kWh"  # hard rule 3
        # `read_count` counts what the QUANTITY is over, not every row on file.
        # A count of 2 beside a figure of 684 would be a figure derived from
        # more evidence than it was.
        assert row.read_count == 1


# ══════════════════════════════════════════════════════════════════════════
# TC-2 · THE OTHER HALF: TOU windows are not counted on top of `total`
# ══════════════════════════════════════════════════════════════════════════
def test_def_798_tc2__tou_windows_are_not_double_counted_against_total(brazos, marcus):
    """DEF-798's second finding: *"TOU window reads are double-counted against
    total"*. The windows ARE the total; a meter reporting both reports one
    month's energy twice."""
    with tenant_ctx(brazos):
        account, unit = _account_on(marcus, brazos)
        meter = _meter(marcus, unit["id"], asset_no="M-4413")
        _read(brazos, account["id"], meter["id"], day=date(2026, 7, 10), consumption="600.000000")
        for channel, qty in (("tou_on", "250"), ("tou_mid", "200"), ("tou_off", "150")):
            _read(
                brazos,
                account["id"],
                meter["id"],
                day=date(2026, 7, 10),
                consumption=f"{qty}.000000",
                channel=channel,
            )

        usage_service.recompute_account(account["id"], actor=marcus)

        row = _july(account["id"])
        assert row.quantity == Decimal("600.000000"), (
            "DEF-798: the three TOU windows were added on top of `total` — "
            f"got {row.quantity}, the double count is 1200"
        )
        assert row.read_count == 1


# ══════════════════════════════════════════════════════════════════════════
# TC-3 · A TOU METER WITH NO `total` — the windows ARE the month
# ══════════════════════════════════════════════════════════════════════════
def test_def_798_tc3__windows_are_summed_when_the_meter_reports_no_total(brazos, marcus):
    """The fix must not become "drop the windows". A meter that reports only
    its three windows has measured a real month, and dropping them would erase
    a customer's whole usage — a worse defect than the one being fixed."""
    with tenant_ctx(brazos):
        account, unit = _account_on(marcus, brazos)
        meter = _meter(marcus, unit["id"], asset_no="M-4414")
        for channel, qty in (("tou_on", "250"), ("tou_mid", "200"), ("tou_off", "150")):
            _read(
                brazos,
                account["id"],
                meter["id"],
                day=date(2026, 7, 10),
                consumption=f"{qty}.000000",
                channel=channel,
            )

        usage_service.recompute_account(account["id"], actor=marcus)

        row = _july(account["id"])
        assert row.quantity == Decimal("600.000000")
        assert row.read_count == 3


# ══════════════════════════════════════════════════════════════════════════
# TC-4 · THE CHOICE IS PER METER, NOT PER SERVICE
# ══════════════════════════════════════════════════════════════════════════
def test_def_798_tc4__a_flat_meter_keeps_its_total_beside_a_tou_meter(brazos, marcus):
    """One account, one service, two meters — a flat one and a TOU one. Making
    the total-vs-windows choice once for the whole service would drop the flat
    meter's `total` because a DIFFERENT meter reported windows, and lose a real
    month of real usage. `select_consumption_facts` groups on asset_id for
    exactly this reachable state."""
    with tenant_ctx(brazos):
        account, unit = _account_on(marcus, brazos)
        flat = _meter(marcus, unit["id"], asset_no="M-4415")
        tou = _meter(marcus, unit["id"], asset_no="M-4416")
        _read(brazos, account["id"], flat["id"], day=date(2026, 7, 10), consumption="100.000000")
        for channel, qty in (("tou_on", "10"), ("tou_mid", "20"), ("tou_off", "30")):
            _read(
                brazos,
                account["id"],
                tou["id"],
                day=date(2026, 7, 11),
                consumption=f"{qty}.000000",
                channel=channel,
            )

        usage_service.recompute_account(account["id"], actor=marcus)

        row = _july(account["id"])
        # 100 (flat total) + 60 (the TOU meter's three windows) = 160.
        assert row.quantity == Decimal("160.000000")
        assert row.read_count == 4


# ══════════════════════════════════════════════════════════════════════════
# TC-5 · export AND generation are NEVER consumption (BR-AST-029/BR-MET-135)
# ══════════════════════════════════════════════════════════════════════════
def test_def_798_tc5__export_and_generation_never_join_the_sum(brazos, marcus):
    """BR-MET-135, verbatim: `generation` is *"never summed with consumption"*.
    BR-AST-029 says the same of a net meter's `export`. A solar site with both
    would otherwise report using energy it PUT BACK."""
    with tenant_ctx(brazos):
        account, unit = _account_on(marcus, brazos)
        meter = _meter(marcus, unit["id"], asset_no="M-4417")
        _read(brazos, account["id"], meter["id"], day=date(2026, 7, 9), consumption="500.000000")
        _read(
            brazos,
            account["id"],
            meter["id"],
            day=date(2026, 7, 9),
            consumption="300.000000",
            channel="export",
        )
        _read(
            brazos,
            account["id"],
            meter["id"],
            day=date(2026, 7, 9),
            consumption="612.000000",
            channel="generation",
        )

        usage_service.recompute_account(account["id"], actor=marcus)

        row = _july(account["id"])
        assert row.quantity == Decimal("500.000000"), (
            "export/generation joined the consumption sum — got "
            f"{row.quantity}; blind addition gives 1412"
        )


# ══════════════════════════════════════════════════════════════════════════
# TC-6 · A REGISTER NOBODY CLASSIFIED STOPS THE SUM — it does not join it
# ══════════════════════════════════════════════════════════════════════════
def test_def_798_tc6__an_unclassified_register_refuses_rather_than_defaulting_in():
    """BR-MET-059 makes the channel vocabulary EXTENSIBLE — *"adding a register
    means adding a string"*. `generation` was minted on 2026-08-26. Had this
    function carried an else-branch, a solar device's production would have
    joined every site's usage on the day that string landed and NOTHING would
    have failed. A pure-rules test: no tenant, no row, no transaction."""
    facts = [
        usage_rules.ReadFact(
            read_id="r1",
            read_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
            consumption=Decimal("10"),
            unit="kWh",
            is_estimate=False,
            asset_id="a1",
            channel="reactive_power",  # a register no rule in this repo names
        )
    ]
    with pytest.raises(usage_rules.UnclassifiedChannel) as excinfo:
        usage_rules.select_consumption_facts(
            facts,
            total_channel=metering_models.CHANNEL_TOTAL,
            tou_windows=metering_models.TOU_WINDOW_CHANNELS,
            never_consumption=usage_service.NEVER_CONSUMPTION,
        )
    assert "DEF-798" in str(excinfo.value)
    assert "reactive_power" in str(excinfo.value)


# ══════════════════════════════════════════════════════════════════════════
# TC-7 · THE UNIT GUARD CANNOT SEE THIS, AND THAT IS WHY THE DEFECT SHIPPED
# ══════════════════════════════════════════════════════════════════════════
def test_def_798_tc7__the_oq_358_unit_guard_sees_one_unit_on_the_defect_shape(brazos, marcus):
    """DEF-798's escape_reason, verbatim: *"The mixed-unit guard (OQ-358) cannot
    see it, because every channel on one meter is stamped the SAME asset unit -
    so a kW peak and a kWh total are indistinguishable to a check that compares
    units."* Asserted, so nobody later "simplifies" the register rule away on
    the grounds that the unit check covers it."""
    with tenant_ctx(brazos):
        account, unit = _account_on(marcus, brazos)
        meter = _meter(marcus, unit["id"], asset_no="M-4418")
        energy = _read(
            brazos, account["id"], meter["id"], day=date(2026, 7, 15), consumption="684.000000"
        )
        peak = _read(
            brazos,
            account["id"],
            meter["id"],
            day=date(2026, 7, 15),
            consumption="14.000000",
            channel="demand",
        )
        # The two rows disagree about WHAT they measure and agree about the unit.
        assert energy.unit == peak.unit == "kWh"
        assert energy.channel != peak.channel


# ══════════════════════════════════════════════════════════════════════════
# TC-8 · THE METER STRIP: one series per register, nothing blended (task 8)
# ══════════════════════════════════════════════════════════════════════════
def test_cr038_t8_tc8__the_meter_strip_publishes_one_series_per_register(brazos, marcus):
    with tenant_ctx(brazos):
        account, unit = _account_on(marcus, brazos)
        meter = _meter(marcus, unit["id"], asset_no="M-4419")
        _read(brazos, account["id"], meter["id"], day=date(2026, 7, 15), consumption="684.000000")
        _read(
            brazos,
            account["id"],
            meter["id"],
            day=date(2026, 7, 15),
            consumption="14.000000",
            channel="demand",
        )

        payload = asset_usage.asset_usage_payload(meter["id"], months=12, today=date(2026, 7, 20))

        by_channel = {s["channel"]: s for s in payload["series"]}
        assert set(by_channel) == {"total", "demand"}, "each register gets its OWN series"
        assert by_channel["total"]["is_consumption"] is True
        # DEF-798's fact, on the wire: a demand register is DRAWN and LABELLED,
        # so a clerk sees the peak and nothing can total it into usage.
        assert by_channel["demand"]["is_consumption"] is False

        july_total = [p for p in by_channel["total"]["points"] if p["month"] == "2026-07"][0]
        july_demand = [p for p in by_channel["demand"]["points"] if p["month"] == "2026-07"][0]
        assert july_total["quantity"] == "684.000000"
        assert july_demand["quantity"] == "14.000000"
        # Hard rule 3: the unit rides on every point, never once at the top.
        assert july_total["unit"] == "kWh"
        # Nothing anywhere adds them.
        assert "698" not in str(payload)


# ══════════════════════════════════════════════════════════════════════════
# TC-9 · AN UNREAD MONTH IS ABSENT ON THE METER STRIP TOO, NEVER 0
# ══════════════════════════════════════════════════════════════════════════
def test_cr038_t8_tc9__an_unread_month_draws_no_bar_on_the_meter_strip(brazos, marcus):
    """BR-MET-106: *"zero usage and no read are different claims about a
    customer"*. The account tab honours it; so must the meter strip, or the two
    surfaces tell the same customer different stories about the same silence."""
    with tenant_ctx(brazos):
        account, unit = _account_on(marcus, brazos)
        meter = _meter(marcus, unit["id"], asset_no="M-4420")
        _read(brazos, account["id"], meter["id"], day=date(2026, 7, 15), consumption="684.000000")

        payload = asset_usage.asset_usage_payload(meter["id"], months=12, today=date(2026, 7, 20))
        total = payload["series"][0]
        assert total["months_present"] == 1
        assert total["months_absent"] == 11
        june = [p for p in total["points"] if p["month"] == "2026-06"][0]
        assert june["absent"] is True
        assert june["quantity"] is None, "an unread month is ABSENT, never 0"
        assert june["quantity_display"] is None


# ══════════════════════════════════════════════════════════════════════════
# TC-10 · THE METER STRIP AND THE ACCOUNT TAB AGREE — the anti-drift pin
# ══════════════════════════════════════════════════════════════════════════
def test_cr038_t8_tc10__meter_strip_and_account_tab_agree_on_the_single_meter_case(brazos, marcus):
    """CR-038 asks task 8 to read *"the SAME stored monthly-usage source"*. One
    account, one meter, one register: the two surfaces MUST print the same
    figure, or one of them is lying to the same customer.

    ⚠ **AMENDED 2026-08-27, NOT REPLACED — OQ-421 IS CLOSED.** This test was
    written while the stored row had no asset grain, so its last two lines
    asserted the honest statement of that gap:

        assert meter_payload["source"] == "computed_from_reads"
        assert meter_payload["stored_source_absent"]["tracks"] == "OQ-421"

    The PO ruled on 2026-08-27 — *"(b) Store it per meter too - otherwise we
    will ahve to calculate it again and again"* — so the meter strip now reads
    a STORED row (BR-MET-141) and those two lines went RED, verbatim:

        AssertionError: assert 'stored' == 'computed_from_reads'

    **The agreement clause is unchanged and is the point of the test**; what is
    amended is only the claim about WHERE the figure came from. The decision
    log's one constraint on that build — *"the existing test that holds the two
    surfaces against each other stays, and now holds the stored row against the
    computed one"* — is discharged here (the third assertion below) and, case by
    case, in `tests/test_oq_421_per_meter_monthly_usage.py`.
    """
    with tenant_ctx(brazos):
        account, unit = _account_on(marcus, brazos)
        meter = _meter(marcus, unit["id"], asset_no="M-4421")
        _read(brazos, account["id"], meter["id"], day=date(2026, 7, 3), consumption="684.000000")
        _read(brazos, account["id"], meter["id"], day=date(2026, 7, 31), consumption="158.000000")
        usage_service.recompute_account(account["id"], actor=marcus)

        account_payload = usage_reads.usage_payload(
            account["id"], months=12, today=date(2026, 7, 20)
        )
        meter_payload = asset_usage.asset_usage_payload(
            meter["id"], months=12, today=date(2026, 7, 20)
        )

        account_july = [
            p for p in account_payload["series"][0]["points"] if p["month"] == "2026-07"
        ][0]
        meter_july = [p for p in meter_payload["series"][0]["points"] if p["month"] == "2026-07"][0]

        assert account_july["quantity"] == meter_july["quantity"] == "842.000000"
        assert account_july["unit"] == meter_july["unit"] == "kWh"
        # BR-MET-141: the figure now comes from a row, and the payload says so
        # rather than implying it (hard-won law 1 — the claim travels).
        assert meter_payload["source"] == "stored"
        assert meter_payload["stored_source_absent"] is None
        assert meter_payload["grain_rule_ref"] == "BR-MET-141"

        # ⚠ **AND THE STORED ROW IS HELD AGAINST THE COMPUTED ONE**, which is
        # the decision log's own words for what this test must now do. Delete
        # every stored row and the SAME payload comes back from the reads — a
        # cache, not a fact.
        AssetMonthlyUsage.objects.filter(asset_id=meter["id"]).delete()
        recomputed = asset_usage.asset_usage_payload(
            meter["id"], months=12, today=date(2026, 7, 20)
        )
        recomputed_july = [p for p in recomputed["series"][0]["points"] if p["month"] == "2026-07"][
            0
        ]
        assert recomputed_july == meter_july, "the stored figure and the computed one differ"
        assert recomputed["source"] == "computed_from_reads"
