# ── Trace ──────────────────────────────────────────────
# Change:  CR-157-BRC10 wave B — the API reads behind the rebuilt rate-schedule
#          screens (List columns · Rates tab Base charges · Plans tab · tiles).
# Drawing: 05-prototype/rate-schedules-2026-10-01/images/01, 09, 10, 33
# Rules:   BR-RAT-088 · BR-RAT-1025 · NFR-3 · B14 rule 31 · the minimum is per
#          meter size (PO 2026-10-01, option A)
# ───────────────────────────────────────────────────────
"""What the rebuilt screens read, asserted on the figures the drawings show.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7 clause 2):

  · *Sizes priced* counted from the base code instead of the schedule — a code
    pricing every size would read `n of n` for a schedule that prices three of
    them. The fixture's code prices TWO of the schedule's THREE sizes, so only
    the schedule-side count reads `2 of 3`.
  · rows ordered by CODE — `W-1, W-34, W-58` is code order and `5/8", 3/4", 1"`
    is size order; the assertion is on the order of NAMES.
  · a missing price drawn as `$0.00` — the unpriced row must carry `priced:
    False` and a null amount, never a zero.
  · *Class differs* read on names — two classes with the same name would match;
    the rule is asserted on a plan whose class id differs.
  · the per-VERSION minimum leaking back — option A (PO 2026-10-01) removes it
    from screen, so the *All sizes* row must read no minimum even when the
    version still stores one (the fixture writes `5.00` on purpose).
"""

from __future__ import annotations

from datetime import date

import pytest

from apps.rating import models, schedule_reads, seams, selectors, services
from core.pagination import ListParams

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos, dana
from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures (env)
from tests.test_us_rat_helpers import RES_WATER_TIERS, seeding_ctx, tenant_ctx

pytestmark = pytest.mark.django_db

WATER_SIZES = (("W-58", 'Water 5/8"'), ("W-34", 'Water 3/4"'), ("W-1", 'Water 1"'))


def _sizes(tenant):
    from apps.tenancy import models as tenancy_models

    with seeding_ctx(tenant):
        for code, name in WATER_SIZES:
            tenancy_models.MeterSizeClass.objects.update_or_create(
                tenant=tenant, code=code, defaults={"name": name, "active": True}
            )


def _base_w(env):
    """BASE-W priced for 5/8" and 3/4" only — 1" deliberately unpriced."""
    with tenant_ctx(env.tenant):
        return services.create_charge(
            env.admin,
            {
                "code": "BASE-W",
                "name": "Water base",
                "service": "water",
                "charge_type": "recurring",
                "amount_rule": "flat",
                "is_base": True,
                "effective_from": "2026-01-01",
                "size_amounts": [
                    {"size_class": "W-58", "amount": "8.00"},
                    {"size_class": "W-34", "amount": "8.50"},
                ],
            },
        )


def _water_schedule(env, **overrides):
    _sizes(env.tenant)
    env.declare_base_charge_code("electric")
    _base_w(env)
    payload = {
        # sizes listed in CODE order on purpose: W-1 sorts first as text
        "size_rows": [
            {"size_class": "W-1"},
            {"size_class": "W-34"},
            {"size_class": "W-58", "minimum_bill": "8.00"},
        ],
    }
    payload.update(overrides)
    return env.tiered_schedule("Water — Residential", "water", RES_WATER_TIERS, **payload)


def test_the_rates_tab_lists_the_schedules_sizes_in_size_order_with_price_version_dates(env):
    schedule = _water_schedule(env)
    with tenant_ctx(env.tenant):
        rates = schedule_reads.schedule_rates(schedule["id"])
    assert rates["base_code"]["code"] == "BASE-W"
    names = [row["size_name"] for row in rates["base_rows"]]
    assert names == ['Water 5/8"', 'Water 3/4"', 'Water 1"']
    assert [row["seq"] for row in rates["base_rows"]] == [1, 2, 3]
    first, second, third = rates["base_rows"]
    assert (first["amount_display"], first["version"], first["effective_from"]) == (
        "8.00",
        1,
        "2026-01-01",
    )
    assert first["effective_to"] is None and first["priced"] is True
    assert second["amount_display"] == "8.50"
    # 1" is on the schedule and the code has no price for it: NOT PRICED, never $0.00
    assert third["priced"] is False
    assert third["amount"] is None and third["version"] is None
    # option A — the size row's own minimum, nothing else
    assert first["minimum_display"] == "8.00"
    assert second["minimum_display"] is None
    assert (rates["sizes_priced"], rates["sizes_total"]) == (2, 3)


def test_the_list_card_carries_class_base_code_and_sizes_of(env):
    schedule = _water_schedule(env)
    with tenant_ctx(env.tenant):
        card = selectors.schedule_card(models.Tariff.objects.get(pk=schedule["id"]))
    assert card["base_code"] == "BASE-W"
    assert (card["sizes_priced"], card["sizes_total"]) == (2, 3)
    # no class on the schedule: the screen says *Every class*
    assert card["customer_class_name"] is None


def test_a_named_class_is_served_as_its_name_never_its_id(env):
    with tenant_ctx(env.tenant):
        residential = seams.account_type_id_by_code("residential")
    schedule = _water_schedule(env, account_type_id=str(residential))
    with tenant_ctx(env.tenant):
        card = selectors.schedule_card(models.Tariff.objects.get(pk=schedule["id"]))
    assert card["customer_class_name"] == "Residential"
    assert str(residential) not in str(card["customer_class_name"])


def test_a_flat_base_code_and_no_size_rows_is_one_all_sizes_row(env):
    env.declare_base_charge_code("water")
    env.declare_base_charge_code("electric")
    schedule = env.flat_schedule("Sewer-ish water flat", "water")
    with tenant_ctx(env.tenant):
        # The API refuses a version minimum since 2.433.0; a row written before
        # `rating/0053` can still hold one, so the fixture writes it directly.
        models.TariffVersion.objects.filter(tariff_id=schedule["id"]).update(minimum_bill="5.00")
        rates = schedule_reads.schedule_rates(schedule["id"])
        card = selectors.schedule_card(models.Tariff.objects.get(pk=schedule["id"]))
    assert len(rates["base_rows"]) == 1
    row = rates["base_rows"][0]
    assert row["size_class"] is None and row["priced"] is True
    # option A — the version's stored 5.00 is NOT shown: *No minimum*
    assert row["minimum_display"] is None
    assert (rates["sizes_priced"], rates["sizes_total"]) == (0, 0)  # *One amount*
    assert (card["sizes_priced"], card["sizes_total"]) == (0, 0)


def test_the_plans_tab_pages_in_sql_and_marks_a_class_that_differs(env):
    with tenant_ctx(env.tenant):
        residential = seams.account_type_id_by_code("residential")
        commercial = seams.account_type_id_by_code("commercial")
    schedule = _water_schedule(env, account_type_id=str(residential))
    same = env.plan(
        "Residential standard",
        "RES-STD",
        [{"service": "water", "tariff": schedule["id"]}],
        publish=True,
        account_type_ids=[str(residential)],
    )
    other = env.plan(
        "Small commercial",
        "COM-SM",
        [{"service": "water", "tariff": schedule["id"]}],
        publish=True,
        account_type_ids=[str(commercial)],
    )
    env.assign(same["id"], env.unit("Unit A"))
    env.assign(same["id"], env.unit("Unit B"))
    with tenant_ctx(env.tenant):
        tariff = models.Tariff.objects.get(pk=schedule["id"])
        qs = schedule_reads.schedule_plans_queryset(tariff)
        assert qs.count() == 2
        rows = schedule_reads.schedule_plan_rows(tariff, list(qs[:1]))
        all_rows = schedule_reads.schedule_plan_rows(tariff, list(qs))
    # one page of one — the page is cut in the database, not in Python
    assert [row["plan_name"] for row in rows] == ["Residential standard"]
    by_code = {row["plan_code"]: row for row in all_rows}
    assert by_code["RES-STD"]["class_differs"] is False
    assert by_code["RES-STD"]["customer_classes"] == ["Residential"]
    assert by_code["RES-STD"]["units"] == 2
    assert by_code["COM-SM"]["class_differs"] is True
    assert by_code["COM-SM"]["customer_classes"] == ["Commercial"]
    assert other["id"] == by_code["COM-SM"]["plan_id"]


def test_the_list_service_filter_still_pages_in_sql(env):
    _water_schedule(env)
    env.flat_schedule("Electric flat", "electric", uom="kWh")
    with tenant_ctx(env.tenant):
        params = ListParams(sort="name", dir="asc", filters={"service": "water"})
        assert selectors.schedule_list_is_sql_pageable(params)
        rows, total = selectors.schedule_page(params)
    assert total == 1 and rows[0]["service"] == "water"


def test_the_two_routes_resolve_to_their_own_views():
    from django.urls import resolve

    from apps.rating import api

    assert resolve("/api/brazosbend/rate-schedules/abc/rates").func is api.rate_schedule_rates
    assert resolve("/api/brazosbend/rate-schedules/abc/plans").func is api.rate_schedule_plans


def test_unit_counts_by_size_class_counts_in_service_assets_of_the_service(brazos, dana):
    """The seam behind the Units column, on real assets: two units on 5/8", one
    on 3/4", and an electric meter on the same unit that must not count."""
    from tests.test_us_met_helpers import make_asset, make_premises, make_unit

    with tenant_ctx(brazos):
        premise = make_premises(dana)
        units = [make_unit(dana, premise["id"], label=f"Unit {n}") for n in range(3)]
        for index, (unit, size) in enumerate(zip(units, ("W-58", "W-58", "W-34"))):
            make_asset(
                dana,
                asset_no=f"WM-{index}",
                service="water",
                unit="kgal",
                size_class=size,
                unit_id=unit["id"],
                install_date="2026-01-01",
            )
        make_asset(
            dana,
            asset_no="EM-9",
            service="electric",
            unit_id=units[0]["id"],
            install_date="2026-01-01",
        )
        counts = seams.unit_counts_by_size_class(
            [unit["id"] for unit in units], "water", date(2026, 6, 1)
        )
        before_install = seams.unit_counts_by_size_class(
            [unit["id"] for unit in units], "water", date(2025, 6, 1)
        )
    assert counts == {"W-58": 2, "W-34": 1}
    assert before_install == {}


def _plan_minimum(env, size_rows):
    schedule = _water_schedule(env, size_rows=size_rows)
    plan = env.plan("Residential standard", "RES-STD", [{"service": "water", "tariff": schedule["id"]}])
    with tenant_ctx(env.tenant):
        detail = selectors.plan_detail(plan["id"])
    (line,) = [row for row in detail["services"] if row["service"] == "water"]
    return line["schedule_minimum_amount_display"]


def test_def_rat_8759_plan_detail_shows_the_one_per_size_minimum_every_size_states(env):
    # `rating/0053` emptied the version's figure; the plan read it and showed nothing.
    rows = [{"size_class": code, "minimum_bill": "15.00"} for code, _ in WATER_SIZES]
    assert _plan_minimum(env, rows) == "15.00"


def test_def_rat_8759_sizes_that_differ_show_no_single_minimum(env):
    rows = [
        {"size_class": "W-58", "minimum_bill": "15.00"},
        {"size_class": "W-34", "minimum_bill": "15.00"},
        {"size_class": "W-1", "minimum_bill": "40.00"},
    ]
    assert _plan_minimum(env, rows) is None


def test_a_base_code_priced_once_prices_every_size_of_the_schedule(env):
    # The seeded `BASE-W` is one $8.00 row for all sizes; billing prices every
    # size at it (`charge_prices.answer_from_rows`), so the tab must too.
    _sizes(env.tenant)
    env.declare_base_charge_code("water")
    env.declare_base_charge_code("electric")
    schedule = env.tiered_schedule(
        "Water — Residential", "water", RES_WATER_TIERS,
        size_rows=[{"size_class": code} for code, _ in WATER_SIZES],
    )
    with tenant_ctx(env.tenant):
        rates = schedule_reads.schedule_rates(schedule["id"])
    assert all(row["priced"] for row in rates["base_rows"]), rates["base_rows"]
    assert (rates["sizes_priced"], rates["sizes_total"]) == (3, 3)


def test_a_price_backfilled_from_the_2000_epoch_shows_no_from_date(env):
    # The flat-only `declare_base_charge_code` row starts at PRICE_HISTORY_EPOCH,
    # exactly like a wave-A backfill; `01/01/2000` must not reach the screen.
    _sizes(env.tenant)
    env.declare_base_charge_code("water")
    env.declare_base_charge_code("electric")
    schedule = env.tiered_schedule(
        "Water — Residential", "water", RES_WATER_TIERS,
        size_rows=[{"size_class": code} for code, _ in WATER_SIZES],
    )
    with tenant_ctx(env.tenant):
        rates = schedule_reads.schedule_rates(schedule["id"])
    assert rates["base_rows"] and all(row["priced"] for row in rates["base_rows"])
    assert [row["effective_from"] for row in rates["base_rows"]] == [None, None, None]
