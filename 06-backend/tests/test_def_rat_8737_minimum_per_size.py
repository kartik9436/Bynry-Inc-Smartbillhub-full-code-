# ── Trace ──────────────────────────────────────────────
# Change:  DEF-RAT-8737 · PO ruling 2026-10-01, option A — decision log "RATE
#          SCHEDULES: THE MINIMUM IS SET PER METER SIZE AND BILLING CHARGES IT;
#          THE PER-VERSION MINIMUM RATE ON THIS VERSION IS REMOVED" ·
#          CR-157-BRC10 · migration `rating/0053`
# Rules:   BR-RAT-028 mode (A) AMENDED (the source is the size row) · mode (B)
#          unchanged · OQ-1166 (b) base-only exemption · hard rule 2 (money)
# Golden:  WE-3 / GT-19 ($16.42) is NOT re-derived here; it is asserted,
#          untouched, by `test_br_rat_028_minimum_bill.py` and
#          `test_cr090_minimum_reads_from_the_schedule.py`.
# Tests:   this file
# ───────────────────────────────────────────────────────
"""The minimum is the meter SIZE's, and billing charges it.

PO 2026-10-01, verbatim: *"A · Minimum per size - this is correct"*. The
worked example put to the PO, Water — Residential, two customers using 1 kgal:

    5/8"  $8.00 base + 1 × $4.4096 = $12.41, 5/8" minimum $15.00 → $15.00
    2"   $28.00 base + 1 × $4.4096 = $32.41, 2"   minimum $40.00 → $40.00
    a size with *No minimum*                                   → $12.41

Two halves, the shape `test_cr090_minimum_reads_from_the_schedule.py` uses:
the HOP (a row in `rate_size_rows` reaches `TariffConfig.minimum_amount`
through `rating.selectors.pricing_inputs` and `billing.gather`) and the MONEY
(the engine prices the PO's dollars from that figure). A hop test alone is
blind to the arithmetic and an arithmetic test alone is blind to the source.
"""

from __future__ import annotations

import importlib
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.apps import apps as django_apps
from django.db import connection

from apps.billing import gather, rating_seam
from apps.rating import models as rating_models
from apps.rating import selectors as rating_selectors
from apps.rating import services as rating_services
from apps.tenancy import models as tenancy_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_plan, tenant_ctx

UNTAXED = rating_seam.AccountContext(currency="USD", tax_exempt=False)
FULL_MONTH = rating_seam.BillingPeriod(cycle_days=30, service_days=30)
SERVICE_DATE = date(2026, 8, 15)

RATE = Decimal("4.4096")  # per kgal, the PO's figure
BASE = {"W-58": Decimal("8.00"), "W-2": Decimal("28.00"), "W-34": Decimal("8.00")}
MINIMUM = {"W-58": Decimal("15.00"), "W-2": Decimal("40.00")}


def _schedule(tenant, *, version_minimum=None):
    """A water schedule with three size rows: 5/8" $15.00, 2" $40.00 and 3/4"
    stating *No minimum*. 1" has no row at all."""
    plan = make_plan(tenant, name="Water — Residential", services=("water",))
    bound = rating_models.PlanRateSchedule.objects.get(rate_plan_id=plan.id)
    version = rating_models.TariffVersion.objects.create(
        tenant=tenant,
        tariff=bound.tariff,
        model="flat",
        uom="kgal",
        minimum_bill=version_minimum,
        effective_from=date(2026, 1, 1),
    )
    for size, minimum in (("W-58", MINIMUM["W-58"]), ("W-2", MINIMUM["W-2"]), ("W-34", None)):
        rating_models.RateSizeRow.objects.create(
            tenant=tenant, tariff_version=version, size_class=size, minimum_bill=minimum
        )
    assert rating_selectors.in_force_version(bound.tariff, SERVICE_DATE) == version
    return bound.tariff, version


def _minimum(tariff, size):
    inputs = rating_selectors.pricing_inputs(tariff, SERVICE_DATE, size)
    return inputs["minimum_bill"]


def _bill(size, minimum, *, base_only=False, plan_floor=None):
    config = rating_seam.TariffConfig(
        service="water",
        model="flat",
        billed_unit="kgal",
        base_charge=BASE[size],
        unit_price=RATE,
        minimum_amount=minimum,
        plan_minimum_bill_amount=plan_floor,
    )
    if base_only:
        # OQ-1166 (b): a vacant unit reaches the engine as a BASE-ONLY service.
        return rating_seam.price_bill(
            base_only_services=(config,),
            period=FULL_MONTH,
            account=UNTAXED,
            taxes=(),
            fees=(),
        )
    return rating_seam.price_bill(
        services=((config, rating_seam.Quantity(amount=Decimal("1"), unit="kgal")),),
        period=FULL_MONTH,
        account=UNTAXED,
        taxes=(),
        fees=(),
    )


# ── 1 · THE HOP — the size row is the figure, and nothing else is ───────────


@pytest.mark.django_db
def test_the_minimum_published_for_a_connection_is_its_sizes(brazos):
    with tenant_ctx(brazos):
        tariff, _version = _schedule(brazos)
        assert _minimum(tariff, "W-58") == Decimal("15.000000")
        assert _minimum(tariff, "W-2") == Decimal("40.000000")
        assert _minimum(tariff, "W-34") is None, "a size stating No minimum is not topped up"
        assert _minimum(tariff, "W-1") is None, "a size with no row is not topped up"
        assert rating_selectors.pricing_inputs(tariff, SERVICE_DATE)["minimum_bill"] is None


@pytest.mark.django_db
def test_the_per_version_minimum_is_no_longer_billed(brazos):
    """A figure left on the VERSION reaches no bill — the PO removed it."""
    with tenant_ctx(brazos):
        tariff, _version = _schedule(brazos, version_minimum=Decimal("99.00"))
        assert _minimum(tariff, "W-58") == Decimal("15.000000")
        assert _minimum(tariff, "W-34") is None
        assert _minimum(tariff, "W-1") is None


@pytest.mark.django_db
def test_gather_carries_the_sizes_minimum_onto_the_tariff(brazos):
    """The seam the engine reads: `gather._tariff_config_for(size_class=…)`."""
    with tenant_ctx(brazos):
        tariff, _version = _schedule(brazos)
        rating_models.Charge.objects.get_or_create(
            tenant=brazos,
            code="BASE-W-8737",
            defaults=dict(
                name="Water base",
                charge_type="recurring",
                service=tenancy_models.Service.objects.get(code="water"),
                amount_rule="flat",
                amount=Decimal("8.00"),
                is_base=True,
                applies_to_customer_classes=[],
            ),
        )
        for size, expected in (
            ("W-58", Decimal("15.000000")),
            ("W-2", Decimal("40.000000")),
            ("W-34", None),
        ):
            config = gather._tariff_config_for(tariff, "water", SERVICE_DATE, size_class=size)
            assert config.minimum_amount == expected, size
        # The flag that keeps a multi-size capacity unit from being topped up
        # once per group is unchanged.
        later = gather._tariff_config_for(
            tariff, "water", SERVICE_DATE, size_class="W-58", carries_service_minimum=False
        )
        assert later.minimum_amount is None


# ── 2 · THE MONEY — the PO's own figures ────────────────────────────────────


def test_five_eighths_twelve_forty_one_is_raised_to_fifteen():
    assert _bill("W-58", None).total == Decimal("12.41")
    assert _bill("W-58", MINIMUM["W-58"]).total == Decimal("15.00")


def test_two_inch_thirty_two_forty_one_is_raised_to_forty():
    assert _bill("W-2", None).total == Decimal("32.41")
    assert _bill("W-2", MINIMUM["W-2"]).total == Decimal("40.00")


def test_a_size_with_no_minimum_stays_twelve_forty_one():
    assert _bill("W-34", None).total == Decimal("12.41")


def test_the_base_only_exemption_still_holds():
    """OQ-1166 (b): a vacant unit pays its base and is never topped up."""
    bill = _bill("W-58", MINIMUM["W-58"], base_only=True)
    assert bill.total == Decimal("8.00")
    assert not [line for line in bill.lines if line.kind == "minimum_adjustment"]


def test_the_plan_floor_is_separate_and_unchanged():
    """Mode B tops the WHOLE bill up AFTER the size's minimum: $15.00 → $50.00."""
    bill = _bill("W-58", MINIMUM["W-58"], plan_floor=Decimal("50.00"))
    assert bill.total == Decimal("50.00")
    adjustments = {
        line.service: line.amount for line in bill.lines if line.kind == "minimum_adjustment"
    }
    # The size's top-up first ($12.41 → $15.00), then the plan floor over it.
    assert adjustments == {"water": Decimal("2.59"), None: Decimal("35.00")}


# ── 3 · THE API — a version minimum is refused by name ──────────────────────


def test_a_stated_version_minimum_is_refused_and_null_is_accepted():
    fe: list = []
    cleaned = rating_services._validate_version_fields(
        {"model": "flat", "uom": "kgal", "minimum_bill": "15.00"}, fe, require_effective_from=False
    )
    assert [error["field"] for error in fe if error.get("field") == "minimum_bill"] == [
        "minimum_bill"
    ]
    assert cleaned["minimum_bill"] is None
    fe = []
    cleaned = rating_services._validate_version_fields(
        {"model": "flat", "uom": "kgal", "minimum_bill": None}, fe, require_effective_from=False
    )
    assert not [error for error in fe if error.get("field") == "minimum_bill"]
    assert cleaned["minimum_bill"] is None


# ── 4 · THE MIGRATION — no floor is silently lost ───────────────────────────


@pytest.mark.django_db
def test_the_migration_copies_a_version_minimum_to_sizes_that_had_none(brazos, capsys):
    migration = importlib.import_module("apps.rating.migrations.0053_def_rat_8737_minimum_per_size")
    with tenant_ctx(brazos):
        _tariff, moved = _schedule(brazos, version_minimum=Decimal("17.00"))
        bare_plan = make_plan(brazos, name="Water — Bare", services=("water",))
        bare_bound = rating_models.PlanRateSchedule.objects.get(rate_plan_id=bare_plan.id)
        bare = rating_models.TariffVersion.objects.create(
            tenant=brazos,
            tariff=bare_bound.tariff,
            model="flat",
            uom="kgal",
            minimum_bill=Decimal("20.00"),
            effective_from=date(2026, 1, 1),
        )
    migration.move_version_minimums_onto_sizes(django_apps, SimpleNamespace(connection=connection))
    with tenant_ctx(brazos):
        rows = dict(
            rating_models.RateSizeRow.objects.filter(tariff_version=moved).values_list(
                "size_class", "minimum_bill"
            )
        )
        # 3/4" said No minimum and now carries the version's $17.00; the two
        # sizes that stated their own keep them.
        assert rows == {
            "W-58": Decimal("15.000000"),
            "W-2": Decimal("40.000000"),
            "W-34": Decimal("17.000000"),
        }
        moved.refresh_from_db()
        assert moved.minimum_bill is None
        # No size rows at all: nowhere to go, so the figure stays, listed.
        bare.refresh_from_db()
        assert bare.minimum_bill == Decimal("20.000000")
    out = capsys.readouterr().out
    assert "1 size row(s) given it" in out
    assert "2 size row(s) already stated a DIFFERENT figure" in out
    assert "1 version(s) have no size rows" in out
