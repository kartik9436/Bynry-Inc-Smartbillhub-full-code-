"""CR-179-BRC10 — the Rate Impact report, server half: every figure by hand.

THE WORLD (Brazos Bend, the utility's today pinned to 2026-10-12)
──────────────────────────────────────────────────────────────────
`months=3` is July, August and September 2026 — three whole months ending LAST
month (CR-179 §1 row 3).

**Water, a flat schedule, two versions.** v1 from 2025-01-01 to 2025-12-31 at
`$3.5000`/kgal, v2 from 2026-01-01 at `$4.0000`/kgal. Both name the base code
`RI-BASE-W` (5/8" `$10.0000`, 1" `$25.0000`); the 5/8" size has a `$15.00`
minimum, the 1" none. The plan also carries the recurring charge code
`RI-STORM` at a flat `$5.0000`.

    account   class        meter  usage Jul/Aug/Sep kgal  billed (water lines)
    RI-A      residential  5/8"   2 / 10 / 5              20 + 50 + 30 = 100.00
    RI-B      commercial   1"     20 / 30 / 25            100 + 100 + 100 = 300.00
    RI-C      residential  5/8"   4 / 4 / 4               (no bill)   -> not worked out
    RI-D      residential  5/8"   (no usage)              40.00       -> not worked out
    RI-E      residential  none   3 / 3 / 3               30.00       -> not worked out

RI-B's Jul bill CROSSES the window start (15 Jun – 14 Jul) and counts in July
(confirmed rule 1); its August bill was CORRECTED — original 120.00, rebill
100.00 — so 100.00 counts; a bill ending 14 Oct (999.00) is outside the window.
RI-A's August bill carries a 3.00 TAX line that is not schedule revenue.

**Proposed water rows** — 5/8": base 10.00, price 4.50, min 20.00 · 1": base
25.00, price 4.00, no minimum:

    RI-A  Jul max(10 + 2×4.50, 20) = 20.00 · Aug 10 + 45 = 55.00 · Sep 10 + 22.50
          = 32.50 → 107.50, now 100.00, change +7.50, +7.5%
    RI-B  Jul 25 + 80 = 105 · Aug 25 + 120 = 145 · Sep 25 + 100 = 125 → 375.00,
          now 300.00, change +75.00, +25%

**Fire, counted per size** (a tiered schedule of one open-ended tier per size —
`sample_data.fire_schedule_payload`'s shape — FL-2 `$12.0000`, FL-6 `$60.0000`,
no base code so the base is `$0.00`):

    RI-F  commercial   one 6" + two 2"  billed 3 × 84.00 = 252.00
    RI-G  residential  one 2"           billed 3 × 12.00 = 36.00

Proposed per item FL-2 13.00, FL-6 66.00: RI-F (66 + 2×13) × 3 = 276.00
(+24.00), RI-G 13 × 3 = 39.00 (+3.00).

**The charge code** `RI-STORM`, proposed 6.00/month: RI-A billed 3 × 5.00 =
15.00, proposed 6.00 × 3 = 18.00 (+3.00, +20%).

RED PROVED FIRST (hard-won law 7) — see `test_tc_red_first__rows_reach_the_viewer_through_bind`.
Run green on SQLite (21 passed) and on PostgreSQL 16 through
`config.settings.pgtest` (21 passed), where `reports/0010` ran under `FORCE`.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

import pytest

from apps.billing import models as billing_models
from apps.customers import models as customer_models
from apps.metering import models as metering_models
from apps.rating import models as rating_models
from apps.reports import catalogue_read, exports, rate_impact, report_seams, runner
from apps.tenancy import models as tenancy_models
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import make_plan, make_premises, make_unit, tenant_ctx
from tests.test_us_met_reads_helpers import a_meter

pytestmark = pytest.mark.django_db

TODAY = date(2026, 10, 12)
JUL, AUG, SEP = date(2026, 7, 1), date(2026, 8, 1), date(2026, 9, 1)
ISSUED_AT = datetime(2026, 10, 3, 14, 0, tzinfo=dt_timezone.utc)
OPENED = date(2025, 1, 1)


@pytest.fixture(autouse=True)
def _pinned_today(monkeypatch):
    """The utility's business date, pinned so *last month* is September 2026."""
    monkeypatch.setattr(report_seams, "tenant_today", lambda: TODAY)


def D(text: str) -> Decimal:
    return Decimal(text)


# ── the world ────────────────────────────────────────────────────────────────
def _service(code):
    return tenancy_models.Service.objects.get(code=code)


def _account(tenant, unit_id, number, class_code):
    return customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit_id,
        account_no=number,
        status=customer_models.AccountStatus.objects.get(tenant=tenant, code="active"),
        account_type=customer_models.AccountType.objects.get(tenant=tenant, code=class_code),
        opened_at=OPENED,
    )


def _usage(tenant, account, service, month, quantity, unit="kgal"):
    metering_models.MonthlyUsage.objects.create(
        tenant=tenant,
        account=account,
        service=_service(service),
        period_month=month,
        quantity=D(quantity),
        unit=unit,
        read_count=1,
        source_read_ids=[],
        source_fingerprint=f"ri-{account.account_no}-{month.isoformat()}",
        computed_at=ISSUED_AT,
    )


def _bill(tenant, account, start, end, lines, *, status=billing_models.INVOICE_ISSUED):
    """One bill and its lines: `(kind, amount, tariff_version, charge, service)`."""
    invoice = billing_models.Invoice.objects.create(
        tenant=tenant,
        account=account,
        service_date=end,
        period_start=start,
        period_end=end,
        status=status,
        issued_at=ISSUED_AT,
        currency="USD",
    )
    for kind, amount, version, charge, service in lines:
        billing_models.InvoiceLine.objects.create(
            tenant=tenant,
            invoice=invoice,
            account=account,
            service=_service(service),
            tariff_version=version,
            charge=charge,
            kind=kind,
            description=f"{service} {kind}",
            amount=D(amount),
            period_start=start,
            period_end=end,
        )
    return invoice


def _water_version(tenant, tariff, base_code, start, end, price):
    version = rating_models.TariffVersion.objects.create(
        tenant=tenant,
        tariff=tariff,
        model="flat",
        uom="kgal",
        currency="USD",
        base_charge_code=base_code,
        effective_from=start,
        effective_to=end,
    )
    rating_models.RateTier.objects.create(
        tenant=tenant, tariff_version=version, seq=1, from_qty=D("0"), to_qty=None,
        unit_price=D(price),
    )
    rating_models.RateSizeRow.objects.create(
        tenant=tenant, tariff_version=version, size_class="W-58", minimum_bill=D("15.00")
    )
    rating_models.RateSizeRow.objects.create(
        tenant=tenant, tariff_version=version, size_class="W-1", minimum_bill=None
    )
    return version


def _price_row(tenant, charge, size, amount):
    rating_models.ChargeCodeAmount.objects.create(
        tenant=tenant, charge=charge, size_class=size, amount=D(amount),
        effective_from=date(2000, 1, 1),
    )


def build_world(tenant, actor):
    from apps.assets import services as asset_services
    from apps.metering import services as metering_services
    from apps.tenancy import services as tenancy_services

    tenancy_services.update_tenant_service(actor, "fire", {"enabled": True})

    # ── water: plan, schedule (two versions), base code, charge code ────────
    water_plan = make_plan(tenant, name="RI Water", services=("water",))
    water_tariff = rating_models.PlanRateSchedule.objects.get(rate_plan=water_plan).tariff
    base = rating_models.Charge.objects.create(
        tenant=tenant, code="RI-BASE-W", name="RI water base", charge_type="recurring",
        amount_rule="flat", service=_service("water"), is_base=True,
        applies_to_customer_classes=[],
    )
    _price_row(tenant, base, "W-58", "10.0000")
    _price_row(tenant, base, "W-1", "25.0000")
    v1 = _water_version(tenant, water_tariff, base, date(2025, 1, 1), date(2025, 12, 31), "3.5000")
    v2 = _water_version(tenant, water_tariff, base, date(2026, 1, 1), None, "4.0000")
    storm = rating_models.Charge.objects.create(
        tenant=tenant, code="RI-STORM", name="RI storm drain fee", charge_type="recurring",
        amount_rule="flat", service=_service("water"), is_base=False,
        applies_to_customer_classes=[],
    )
    _price_row(tenant, storm, "All sizes", "5.0000")
    rating_models.PlanChargeRule.objects.create(
        tenant=tenant, rate_plan=water_plan, charge=storm, recurrence="recurring"
    )

    # ── fire: plan, a tiered schedule of one open tier per size ─────────────
    fire_plan = make_plan(tenant, name="RI Fire", services=("fire",))
    fire_tariff = rating_models.PlanRateSchedule.objects.get(rate_plan=fire_plan).tariff
    fire_v = rating_models.TariffVersion.objects.create(
        tenant=tenant, tariff=fire_tariff, model="tiered", uom="connection", currency="USD",
        effective_from=date(2025, 1, 1),
    )
    for seq, (size, price) in enumerate((("FL-2", "12.0000"), ("FL-6", "60.0000")), start=1):
        rating_models.RateTier.objects.create(
            tenant=tenant, tariff_version=fire_v, seq=seq, size_class=size,
            from_qty=D("0"), to_qty=None, unit_price=D(price),
        )

    def water_account(number, class_code, size):
        premises = make_premises(
            actor, address_line=f"{number} Pecan St", services_available=["water"]
        )
        unit = make_unit(actor, premises["id"], label="Unit 1", services=["water"])
        a_meter(actor, asset_no=f"M-{number}", service="water", uom="kgal",
                unit_id=unit["id"], size_class=size)
        metering_services.assign_unit_plan(
            actor, unit["id"], {"tariff_id": str(water_plan.id), "effective_from": "2025-01-01"}
        )
        return _account(tenant, unit["id"], number, class_code)

    def fire_account(number, class_code, sizes):
        premises = make_premises(
            actor, address_line=f"{number} Standpipe Way", services_available=["fire"]
        )
        unit = make_unit(actor, premises["id"], label="Unit 1", services=["fire"])
        metering_services.assign_unit_plan(
            actor, unit["id"], {"tariff_id": str(fire_plan.id), "effective_from": "2025-01-01"}
        )
        for n, size in enumerate(sizes, start=1):
            asset_services.create_asset(
                actor,
                {
                    "type": "backflow",
                    "asset_no": f"FIRE-{number}-{n}",
                    "service": "fire",
                    "unit_id": str(unit["id"]),
                    "install_date": "2026-01-05",
                    "size_class": size,
                },
            )
        return _account(tenant, unit["id"], number, class_code)

    a = water_account("RI-A", "residential", "W-58")
    b = water_account("RI-B", "commercial", "W-1")
    c = water_account("RI-C", "residential", "W-58")
    d = water_account("RI-D", "residential", "W-58")
    e = water_account("RI-E", "residential", None)
    f = fire_account("RI-F", "commercial", ("FL-6", "FL-2", "FL-2"))
    g = fire_account("RI-G", "residential", ("FL-2",))

    for month, qty in ((JUL, "2"), (AUG, "10"), (SEP, "5")):
        _usage(tenant, a, "water", month, qty)
    for month, qty in ((JUL, "20"), (AUG, "30"), (SEP, "25")):
        _usage(tenant, b, "water", month, qty)
    for month in (JUL, AUG, SEP):
        _usage(tenant, c, "water", month, "4")
        _usage(tenant, e, "water", month, "3")

    W = "water"
    # RI-A — three bills, the minimum topped up in July; a tax line in August.
    _bill(tenant, a, JUL, date(2026, 7, 31), [
        ("base", "10.00", v2, None, W), ("usage", "8.00", v2, None, W),
        ("minimum", "2.00", v2, None, W), ("fee", "5.00", None, storm, W)])
    _bill(tenant, a, AUG, date(2026, 8, 31), [
        ("base", "10.00", v2, None, W), ("usage", "40.00", v2, None, W),
        ("tax", "3.00", v2, None, W), ("fee", "5.00", None, storm, W)])
    _bill(tenant, a, SEP, date(2026, 9, 30), [
        ("base", "10.00", v2, None, W), ("usage", "20.00", v2, None, W),
        ("fee", "5.00", None, storm, W)])
    # RI-B — a crossing bill, a corrected bill and its rebill, and one too late.
    _bill(tenant, b, date(2026, 6, 15), date(2026, 7, 14), [("usage", "100.00", v2, None, W)])
    _bill(tenant, b, AUG, date(2026, 8, 31), [("usage", "120.00", v2, None, W)],
          status=billing_models.INVOICE_CORRECTED)
    _bill(tenant, b, AUG, date(2026, 8, 31), [("usage", "100.00", v2, None, W)])
    _bill(tenant, b, SEP, date(2026, 9, 30), [("usage", "100.00", v2, None, W)])
    _bill(tenant, b, date(2026, 9, 15), date(2026, 10, 14), [("usage", "999.00", v2, None, W)])
    # RI-D and RI-E — billed; RI-C never billed.
    _bill(tenant, d, SEP, date(2026, 9, 30), [("usage", "40.00", v2, None, W)])
    _bill(tenant, e, SEP, date(2026, 9, 30), [("usage", "30.00", v2, None, W)])
    # Fire — one line per service per month.
    for month, end in ((JUL, date(2026, 7, 31)), (AUG, date(2026, 8, 31)), (SEP, date(2026, 9, 30))):
        _bill(tenant, f, month, end, [("usage", "84.00", fire_v, None, "fire")])
        _bill(tenant, g, month, end, [("usage", "12.00", fire_v, None, "fire")])

    return {
        "water_tariff": water_tariff, "v1": v1, "v2": v2, "storm": storm,
        "fire_tariff": fire_tariff, "fire_v": fire_v,
    }


@pytest.fixture()
def world(brazos, dana):
    with tenant_ctx(brazos):
        return build_world(brazos, dana)


# ── helpers over the run ─────────────────────────────────────────────────────
WATER_ROWS = [
    {"capacity": "W-58", "base": "10.00", "price": "4.50", "min": "20.00"},
    {"capacity": "W-1", "base": "25.00", "price": "4.00", "min": None},
]
FIRE_ROWS = [
    {"capacity": "FL-2", "base": "13.00", "price": None, "min": None},
    {"capacity": "FL-6", "base": "66.00", "price": None, "min": None},
]


def _rows(world, *, water_version=None, water=True, fire=True, charge=True):
    out = []
    if water:
        for row in WATER_ROWS:
            out.append({"type": "rate", "item": str(world["water_tariff"].id),
                        "version": str((water_version or world["v2"]).id), **row})
    if fire:
        for row in FIRE_ROWS:
            out.append({"type": "rate", "item": str(world["fire_tariff"].id),
                        "version": str(world["fire_v"].id), **row})
    if charge:
        payload = run_report({"months": "3"})
        version = next(v["value"] for v in _choices(payload)["versions"]
                       if v["item"] == str(world["storm"].id))
        out.append({"type": "charge", "item": str(world["storm"].id), "version": version,
                    "capacity": "", "base": "6.00", "price": None, "min": None})
    return out


def run_report(params):
    return runner.run(rate_impact.KEY, params).payload


def _choices(payload):
    (table,) = [one for one in payload["controls"]["inputs"] if one["param"] == "rows"]
    return table["choices"]


def _groups(payload):
    """`{group value: (group row, [fact rows])}`."""
    out, current = {}, None
    for row in payload["rows"]:
        if row.get("__kind__") == "group":
            current = row["value"]
            out[current] = (row, [])
        else:
            out[current][1].append(row)
    return out


def _group_for(payload, label_start):
    (hit,) = [value for value in _groups(payload) if value.startswith(label_start)]
    return _groups(payload)[hit]


def _run(brazos, world, **kw):
    with tenant_ctx(brazos):
        rows = _rows(world, **kw)
        return run_report({"months": "3", "services": "water,fire", "rows": json.dumps(rows)})


# ═══════════════════════════════════════════════════════════════════════════
# The framework: declared inputs pass bind, unchanged
# ═══════════════════════════════════════════════════════════════════════════
def test_tc_red_first__rows_reach_the_viewer_through_bind(brazos, world):
    """RED FIRST (law 7): before `runner.declared_inputs`, `bind` dropped all
    four of these names — the dataset `rate_schedules` declares none of them
    and `_RUN_CONTROLS` names none. Proved 2026-10-12 by emptying
    `rate_impact.MODULE_INPUTS` and running this test through pytest (the
    harness that runs it): `E  KeyError: 'services'` at the first assertion —
    `bind` had dropped every declared input."""
    encoded = json.dumps([{"type": "rate", "item": "x", "version": "y", "capacity": "",
                           "base": "1.00", "price": "2.0000", "min": None}])
    params = {"services": "water,fire", "classes": "residential", "months": "3",
              "rows": encoded, "nonsense": "dropped"}
    with tenant_ctx(brazos):
        definition = runner.resolve(rate_impact.KEY)
        bound = runner.bind(definition, params)
        dropped = runner.dropped(definition, params)
    assert {k: bound[k] for k in rate_impact.INPUT_PARAMS} == {
        k: params[k] for k in rate_impact.INPUT_PARAMS
    }
    # The JSON string survives byte for byte, and an undeclared name is dropped.
    assert bound["rows"] == encoded
    assert "nonsense" not in bound and dropped == ("nonsense",)


def test_tc_declared_inputs_are_this_reports_only(brazos, world):
    """Generic, not a hole: another report's bind does not hear of `rows`."""
    with tenant_ctx(brazos):
        statement = runner.resolve("statement")
        assert "rows" not in runner.bind(statement, {"rows": "[]"})
        assert runner.declared_inputs("statement") == ()
        assert runner.declared_inputs(rate_impact.KEY) == rate_impact.INPUT_PARAMS


def test_tc_rows_survive_export_filters_and_rerun_unchanged(brazos, world):
    """An export's filters are `dict[str, str]` — the kernel does `str(v)` —
    and the run history replays the same map: the JSON string is unchanged and
    the file's lines equal the screen's lines."""
    from apps.tenancy import exports as export_kernel

    with tenant_ctx(brazos):
        rows = json.dumps(_rows(world))
        resource = export_kernel.export_resource(rate_impact.KEY)
        assert resource is not None and set(rate_impact.INPUT_PARAMS) <= set(resource.filters)
        params = export_kernel.params_from_payload(
            resource, {"filters": {"months": "3", "services": "water,fire", "rows": rows}}
        )
        assert params.filters["rows"] == rows
        file_rows = list(resource.select(params))
        screen = run_report(dict(params.filters))
    assert file_rows == [row for row in screen["rows"] if row.get("__kind__") != "group"]
    assert file_rows and all("item_label" in row for row in file_rows)


# ═══════════════════════════════════════════════════════════════════════════
# The inputs and the choices
# ═══════════════════════════════════════════════════════════════════════════
def test_tc_inputs_and_choices_shape(brazos, world):
    with tenant_ctx(brazos):
        payload = run_report({"months": "3", "services": "water,fire"})
    inputs = payload["controls"]["inputs"]
    assert [one["param"] for one in inputs] == list(rate_impact.INPUT_PARAMS)
    assert [one["kind"] for one in inputs] == ["multi", "multi", "select", "table"]
    months = inputs[2]
    assert months["default"] == "12"
    assert [opt["value"] for opt in months["options"]] == ["1", "2", "3", "6", "9", "12"]
    table = inputs[3]
    assert [c["name"] for c in table["columns"]] == [
        "type", "item", "version", "effective_from", "service", "capacity", "base", "price", "min",
    ]
    assert table["shortcuts"][0]["options"] == ["-10", "-5", "2", "3", "5", "8", "10", "15", "20"]
    choices = table["choices"]
    items = {i["value"]: i for i in choices["items"]}
    water = items[str(world["water_tariff"].id)]
    assert (water["type"], water["item_kind"], water["service"], water["unit"]) == (
        "rate", "metered", "water", "kgal")
    fire = items[str(world["fire_tariff"].id)]
    assert (fire["item_kind"], fire["item_noun"]) == ("capacity", "connection")
    storm = items[str(world["storm"].id)]
    assert storm["item_kind"] == "charge"
    # The schedule's BASE code is part of the schedule, never a second item.
    assert all(i["label"] != "RI water base" for i in choices["items"])
    # Versions: the one in force first; every label a word, never an id.
    water_versions = [v for v in choices["versions"] if v["item"] == water["value"]]
    assert [v["value"] for v in water_versions] == [str(world["v2"].id), str(world["v1"].id)]
    assert [v["in_force"] for v in water_versions] == [True, False]
    assert water_versions[0]["effective_from"] == "2026-01-01"
    # Capacities with their NOW figures.
    caps = {(c["version"], c["value"]): c for c in choices["capacities"]}
    assert caps[(str(world["v2"].id), "W-58")]["now"] == {
        "base": "10.0000", "price": "4.0000", "min": "15.0000"}
    assert caps[(str(world["v2"].id), "W-1")]["now"] == {
        "base": "25.0000", "price": "4.0000", "min": None}
    # Fire's box is the price PER ITEM; its price and minimum boxes are hidden.
    assert caps[(str(world["fire_v"].id), "FL-2")]["now"] == {
        "base": "12.0000", "price": None, "min": None}
    assert caps[(str(world["fire_v"].id), "FL-6")]["now"]["base"] == "60.0000"
    storm_caps = [c for c in choices["capacities"]
                  if c["version"] in {v["value"] for v in choices["versions"]
                                      if v["item"] == storm["value"]}]
    assert [(c["value"], c["now"]["base"]) for c in storm_caps] == [("", "5.0000")]
    assert all(c["label"] for c in choices["capacities"] if c["value"])
    # With no rows: the inputs and an EMPTY result.
    assert payload["rows"] == [] and payload["unavailable"] == []
    assert [o["label_key"] for o in table["columns"][0]["options"]] == [
        "reports.rateImpact.input.type.rate", "reports.rateImpact.input.type.charge"]


def test_tc_an_older_version_changes_only_the_now_figures(brazos, world):
    """Confirmed rule 3 — v1's now price is 3.5000; revenue now is unchanged."""
    with tenant_ctx(brazos):
        payload = run_report({"months": "3", "services": "water"})
    caps = {(c["version"], c["value"]): c for c in _choices(payload)["capacities"]}
    assert caps[(str(world["v1"].id), "W-58")]["now"]["price"] == "3.5000"
    on_v2 = _run(brazos, world, fire=False, charge=False)
    on_v1 = _run(brazos, world, water_version=world["v1"], fire=False, charge=False)
    assert on_v1["totals"]["revenue_now"] == on_v2["totals"]["revenue_now"] == "400.0000"


# ═══════════════════════════════════════════════════════════════════════════
# The worked figures
# ═══════════════════════════════════════════════════════════════════════════
def test_tc_metered_flat_at_two_capacities_with_a_minimum(brazos, world):
    payload = _run(brazos, world, fire=False, charge=False)
    head, lines = _group_for(payload, "RI Water")
    by_capacity = {line["capacity"]: line for line in lines}
    assert len(lines) == 2
    small = next(line for cap, line in by_capacity.items() if "5/8" in (cap or ""))
    large = next(line for cap, line in by_capacity.items() if "5/8" not in (cap or ""))
    # RI-A: 20.00 (topped up to the minimum) + 55.00 + 32.50.
    assert small["revenue_proposed"] == "107.5000"
    assert small["revenue_now"] == "100.0000"
    assert small["change"] == "7.5000" and small["change_pct"] == "7.500000"
    assert (small["usage"], small["unit"], small["accounts"]) == ("17", "kgal", 1)
    assert small["class"] == "Residential"
    # RI-B: 105 + 145 + 125, no floor.
    assert large["revenue_proposed"] == "375.0000"
    assert large["revenue_now"] == "300.0000"
    assert large["change"] == "75.0000" and large["change_pct"] == "25.000000"
    assert head["subtotals"]["revenue_now"] == "400.0000"
    assert head["subtotals"]["revenue_proposed"] == "482.5000"
    assert head["subtotals"]["accounts"] == 2
    assert head["drill_unavailable"] == "rate_impact_no_drill"


def test_tc_counted_items_times_price_times_months(brazos, world):
    payload = _run(brazos, world, water=False, charge=False)
    head, lines = _group_for(payload, "RI Fire")
    by_class = {line["class"]: line for line in lines}
    mixed = by_class["Commercial"]
    # RI-F: (1 × 66.00 + 2 × 13.00) × 3 months — one line naming both sizes.
    assert mixed["items"] == 3 and mixed["item_noun"] == "connections"
    assert mixed["revenue_proposed"] == "276.0000"
    assert mixed["revenue_now"] == "252.0000"
    assert mixed["change"] == "24.0000"
    assert "+" in mixed["capacity"]
    single = by_class["Residential"]
    assert single["revenue_proposed"] == "39.0000" and single["revenue_now"] == "36.0000"
    assert head["subtotals"]["revenue_proposed"] == "315.0000"


def test_tc_charge_amount_times_months(brazos, world):
    payload = _run(brazos, world, water=False, fire=False)
    head, lines = _group_for(payload, "RI storm drain fee")
    (line,) = lines
    assert line["revenue_proposed"] == "18.0000"  # 6.00 × 3
    assert line["revenue_now"] == "15.0000"
    assert line["change"] == "3.0000" and line["change_pct"] == "20.000000"
    assert head["value"].startswith("RI storm drain fee · v1")


def test_tc_grand_total_and_kpis(brazos, world):
    payload = _run(brazos, world)
    assert payload["totals"]["revenue_now"] == "703.0000"  # 400 + 288 + 15
    assert payload["totals"]["revenue_proposed"] == "815.5000"  # 482.50 + 315 + 18
    assert payload["totals"]["change"] == "112.5000"
    assert [k["key"] for k in payload["kpis"]] == [
        "revenue_now", "revenue_proposed", "change", "change_pct"]
    assert payload["kpis"][0]["value"] == "703.0000"
    assert payload["currency"] == "USD"
    assert payload["window"] == {"start": "2026-07-01", "end": "2026-09-30", "months": 3}
    assert {n["code"] for n in payload["notes"]} == {"size_today_used"}
    # The screen lane's reading: `unit` and `item_noun` are row FIELDS, never
    # columns, and printed through `column_meta.unit_from`.
    assert list(payload["columns"]) == [
        "capacity", "class", "accounts", "usage", "items",
        "revenue_now", "revenue_proposed", "change", "change_pct"]
    meta = payload["column_meta"]
    assert (meta["usage"]["type"], meta["usage"]["unit_from"]) == ("quantity", "unit")
    assert (meta["items"]["type"], meta["items"]["unit_from"]) == ("count", "item_noun")
    assert {meta[n]["type"] for n in ("revenue_now", "revenue_proposed", "change")} == {"money"}
    assert meta["change_pct"]["type"] == "percent"
    assert len(payload["proposed_used"]) == 5


# ═══════════════════════════════════════════════════════════════════════════
# Billed revenue — issued lines only, a correction included, crossing bills
# ═══════════════════════════════════════════════════════════════════════════
def test_tc_billed_revenue_is_issued_lines_with_the_correction(brazos, world):
    """RI-B: 100 (crossing) + 100 (the REBILL, not the corrected 120) + 100;
    the bill ending 14 Oct is outside; RI-A's tax line is not schedule revenue."""
    from apps.billing import reporting

    with tenant_ctx(brazos):
        rows = reporting.rate_impact_billed(
            tariff_ids=[world["water_tariff"].id], start=JUL, end=date(2026, 9, 30)
        )
        accounts = {
            str(a.id): a.account_no for a in customer_models.Account.objects.filter(
                account_no__in=["RI-A", "RI-B", "RI-D", "RI-E"])
        }
    by_no = {accounts[row["account_id"]]: row["amount"] for row in rows}
    assert by_no == {"RI-A": D("100.00"), "RI-B": D("300.00"), "RI-D": D("40.00"),
                     "RI-E": D("30.00")}


def test_tc_a_crossing_bill_counts_in_its_end_month(brazos, world):
    """Confirmed rule 1 — a July-only window still holds the 15 Jun–14 Jul bill,
    and a June-only window does not."""
    from apps.billing import reporting

    with tenant_ctx(brazos):
        july = reporting.rate_impact_billed(
            tariff_ids=[world["water_tariff"].id], start=JUL, end=date(2026, 7, 31))
        june = reporting.rate_impact_billed(
            tariff_ids=[world["water_tariff"].id], start=date(2026, 6, 1), end=date(2026, 6, 30))
        b = customer_models.Account.objects.get(account_no="RI-B")
    assert {r["account_id"]: r["amount"] for r in july}[str(b.id)] == D("100.00")
    assert june == []


# ═══════════════════════════════════════════════════════════════════════════
# Not worked out
# ═══════════════════════════════════════════════════════════════════════════
def test_tc_not_worked_out_reasons(brazos, world):
    payload = _run(brazos, world, fire=False, charge=False)
    head, _lines = _group_for(payload, "RI Water")
    # RI-C has usage and no bill (confirmed rule 2), RI-D a bill and no usage,
    # RI-E no meter size on a schedule priced by size.
    assert head["not_worked_out"] == {
        "no_bills_in_period": 1, "no_usage_in_period": 1, "no_capacity_on_file": 1}
    by_code = {u["code"]: u for u in payload["unavailable"]}
    assert {code: u.get("count") for code, u in by_code.items()} == {
        "no_bills_in_period": 1, "no_usage_in_period": 1, "no_capacity_on_file": 1,
        # Confirmed rule 4's note rides in `unavailable` with NO count.
        "size_today_used": None}
    assert "count" not in by_code["size_today_used"]
    assert by_code["no_bills_in_period"]["message_key"] == "reports.rateImpact.notWorkedOut.noBills"


def test_tc_classes_narrow_the_accounts(brazos, world):
    with tenant_ctx(brazos):
        rows = json.dumps(_rows(world, fire=False, charge=False))
        payload = run_report({"months": "3", "services": "water", "classes": "commercial",
                              "rows": rows})
    head, lines = _group_for(payload, "RI Water")
    assert [line["class"] for line in lines] == ["Commercial"]
    assert head["subtotals"]["revenue_now"] == "300.0000"


# ═══════════════════════════════════════════════════════════════════════════
# Refusals — every one names a catalogue key
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    "params, key",
    [
        ({"months": "4"}, "reports.rateImpact.refusal.badMonths"),
        ({"rows": "not json"}, "reports.rateImpact.refusal.badRows"),
        ({"rows": json.dumps({"a": 1})}, "reports.rateImpact.refusal.badRows"),
        ({"rows": json.dumps([{"type": "rate", "item": "nope", "version": "x",
                               "capacity": ""}])}, "reports.rateImpact.refusal.unknownItem"),
    ],
)
def test_tc_refusals(brazos, world, params, key):
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as caught:
            run_report(params)
    assert caught.value.message_key == key


def test_tc_a_metered_row_needs_a_price_and_figures_are_decimals(brazos, world):
    with tenant_ctx(brazos):
        good = _rows(world, fire=False, charge=False)
        for broken, key in (
            ({**good[0], "price": None}, "reports.rateImpact.refusal.priceRequired"),
            ({**good[0], "price": "abc"}, "reports.rateImpact.refusal.badFigure"),
            ({**good[0], "price": "-1"}, "reports.rateImpact.refusal.badFigure"),
            ({**good[0], "capacity": "W-6"}, "reports.rateImpact.refusal.unknownCapacity"),
            ({**good[0], "version": str(world["fire_v"].id)},
             "reports.rateImpact.refusal.unknownVersion"),
        ):
            with pytest.raises(errors.ValidationError) as caught:
                run_report({"months": "3", "rows": json.dumps([broken])})
            assert caught.value.message_key == key, broken
        with pytest.raises(errors.ValidationError) as caught:
            run_report({"months": "3", "rows": json.dumps([good[0], good[0]])})
        assert caught.value.message_key == "reports.rateImpact.refusal.duplicateRow"


def test_tc_every_refusal_key_is_in_the_catalogues():
    import pathlib
    import re

    source = pathlib.Path(rate_impact.__file__).read_text()
    keys = set(re.findall(r'"(reports\.rateImpact\.[A-Za-z.]+)"', source))
    locales = pathlib.Path(__file__).resolve().parents[2] / "07-frontend/src/i18n/locales"
    catalogues = sorted(locales.glob("*.json"))
    assert len(catalogues) == 11
    mine = {k for k in keys if ".refusal." in k or ".notWorkedOut." in k
            or k.endswith(".note.sizeToday") or k.endswith(".unavailable")}
    assert mine
    for path in catalogues:
        held = json.loads(path.read_text())
        missing = sorted(mine - set(held))
        assert not missing, f"{path.name} lacks {missing}"


# ═══════════════════════════════════════════════════════════════════════════
# Isolation — one utility never sees another's schedules or accounts
# ═══════════════════════════════════════════════════════════════════════════
def test_tc_isolation(brazos, world, lonestar):
    with tenant_ctx(lonestar):
        other = build_lonestar_schedule(lonestar)
        theirs = run_report({"months": "3", "services": "water"})
    their_items = {i["value"] for i in _choices(theirs)["items"]}
    assert str(other.id) in their_items
    assert str(world["water_tariff"].id) not in their_items
    assert str(world["storm"].id) not in their_items

    with tenant_ctx(brazos):
        ours = run_report({"months": "3", "services": "water,fire"})
        assert str(other.id) not in {i["value"] for i in _choices(ours)["items"]}
        # Brazos asking for Lone Star's schedule by id is refused by name.
        with pytest.raises(errors.ValidationError) as caught:
            run_report({"months": "3", "rows": json.dumps([
                {"type": "rate", "item": str(other.id), "version": "x", "capacity": "",
                 "price": "1"}])})
    assert caught.value.message_key == "reports.rateImpact.refusal.unknownItem"

    # Lone Star running its own schedule sees none of Brazos's accounts or bills.
    with tenant_ctx(lonestar):
        version = rating_models.TariffVersion.objects.get(tariff=other)
        payload = run_report({"months": "3", "services": "water", "rows": json.dumps([
            {"type": "rate", "item": str(other.id), "version": str(version.id),
             "capacity": "", "base": "1", "price": "1", "min": None}])})
    assert payload["totals"]["accounts"] == 0
    assert payload["totals"]["revenue_now"] == "0.0000"


def build_lonestar_schedule(tenant):
    plan = make_plan(tenant, name="LSR Water", services=("water",))
    tariff = rating_models.PlanRateSchedule.objects.get(rate_plan=plan).tariff
    version = rating_models.TariffVersion.objects.create(
        tenant=tenant, tariff=tariff, model="flat", uom="kgal", currency="USD",
        effective_from=date(2025, 1, 1),
    )
    rating_models.RateTier.objects.create(
        tenant=tenant, tariff_version=version, seq=1, from_qty=D("0"), to_qty=None,
        unit_price=D("2.0000"),
    )
    return tariff


# ═══════════════════════════════════════════════════════════════════════════
# The catalogue card
# ═══════════════════════════════════════════════════════════════════════════
def test_tc_the_card_is_available_in_billing_readiness(brazos, world):
    with tenant_ctx(brazos):
        body = catalogue_read.catalogue_payload(
            {"per": 100, "q": "Rate Impact"}, role="system_admin"
        )
    (card,) = [c for c in body["cards"] if c["key"] == rate_impact.KEY]
    assert card["available"] is True
    assert card["kind"] == "viewer"
    assert (card["group"], card["sub_group"]) == ("billing", "billing_readiness")
    assert card["reason_code"] is None
    assert exports.SLUGS[rate_impact.KEY] == "rate-impact"


# ═══════════════════════════════════════════════════════════════════════════
# The walk of 2026-10-12 (`05-prototype/rate-impact-2026-10-12/walk/`)
# ═══════════════════════════════════════════════════════════════════════════
def test_tc_walk_one_capacity_on_two_versions_is_refused_never_counted_twice(brazos, world):
    """MONEY. The walk modelled the water schedule's 5/8" on v2026-10-01 AND on
    v2026-08-01: two groups holding the SAME 40 accounts and the SAME billed
    $7,991.50, and the grand total added both ($35,350.50 = 19,367.50 +
    7,991.50 + 7,991.50). Confirmed rule 3 makes revenue now the schedule's
    billed revenue whichever version is picked, so the second group was the
    first one's money again (decision log 2026-10-12, *ONE CAPACITY, ONE
    VERSION*).

    RED on the code before the fix: the run returned, with `revenue_now`
    `200.0000` — RI-A's $100.00 counted once per version."""
    with tenant_ctx(brazos):
        on_v2 = {"type": "rate", "item": str(world["water_tariff"].id),
                 "version": str(world["v2"].id), **WATER_ROWS[0]}
        on_v1 = {**on_v2, "version": str(world["v1"].id)}
        with pytest.raises(errors.ValidationError) as caught:
            run_report({"months": "3", "services": "water", "rows": json.dumps([on_v2, on_v1])})
    assert caught.value.message_key == "reports.rateImpact.refusal.capacityOnTwoVersions"
    assert caught.value.params == {"row": 2}


def test_tc_walk_two_versions_at_different_capacities_count_each_account_once(brazos, world):
    """The lawful shape of two versions of one schedule: each capacity on ONE
    version. RI-A (5/8") is priced on v2 and RI-B (1") on v1, and the grand
    total is every billed dollar exactly once: 100.00 + 300.00 = 400.00 —
    the same figure the one-version run states."""
    with tenant_ctx(brazos):
        rows = [
            {"type": "rate", "item": str(world["water_tariff"].id),
             "version": str(world["v2"].id), **WATER_ROWS[0]},
            {"type": "rate", "item": str(world["water_tariff"].id),
             "version": str(world["v1"].id), **WATER_ROWS[1]},
        ]
        payload = run_report({"months": "3", "services": "water", "rows": json.dumps(rows)})
    groups = _groups(payload)
    assert len(groups) == 2
    subtotal = sum(D(head["subtotals"]["revenue_now"]) for head, _ in groups.values())
    assert payload["totals"]["revenue_now"] == "400.0000" == f"{subtotal:.4f}"
    assert payload["totals"]["accounts"] == 2


def test_tc_walk_the_accounts_column_is_a_count_never_money(brazos, world):
    """The walk: the group row's ACCOUNTS cell printed **$47.00**. The column
    had no `column_meta`, and a subtotal under an undeclared column is drawn
    as money. RED before the fix: `KeyError: 'accounts'`."""
    payload = _run(brazos, world, fire=False, charge=False)
    assert payload["column_meta"]["accounts"]["type"] == "count"
    head, _lines = _group_for(payload, "RI Water")
    assert head["subtotals"]["accounts"] == 2


def test_tc_walk_versions_read_v_numbers_never_bare_dates(brazos, world):
    """The walk: the version picker read `2026-09-20`. A version is numbered as
    the schedule's Audit tab numbers it — in the order it was SAVED
    (`DEF-RAT-9003`) — and a FILED label wins. RED before the fix:
    `[None, None]` (the screen then fell back to the ISO date)."""
    with tenant_ctx(brazos):
        payload = run_report({"months": "3", "services": "water"})
        water = [v for v in _choices(payload)["versions"]
                 if v["item"] == str(world["water_tariff"].id)]
        assert [(v["label"], v["in_force"]) for v in water] == [("v2", True), ("v1", False)]
        world["v1"].version_label = "2025 GRC"
        world["v1"].save(update_fields=["version_label"])
        payload = run_report({"months": "3", "services": "water"})
    water = [v for v in _choices(payload)["versions"] if v["item"] == str(world["water_tariff"].id)]
    assert [v["label"] for v in water] == ["v2", "2025 GRC"]
    head, _ = _group_for(_run(brazos, world, fire=False, charge=False), "RI Water")
    assert head["value"] == "RI Water — water · v2, from 2026-01-01"


def test_tc_walk_history_summary_names_rows_by_label_never_by_id(brazos, world):
    """B14 rule 31. The walk: History's PARAMETERS cell printed the raw `rows`
    JSON — schedule and version DATABASE IDS and size codes (`W-58`). The run
    now carries a `summary` in words and figures, and no id or size code is in
    it. RED before the fix: `KeyError: 'summary'`."""
    from apps.reports import run_history

    with tenant_ctx(brazos):
        rows = _rows(world, fire=False)
        filters = {"months": "3", "services": "water,fire", "classes": "residential",
                   "rows": json.dumps(rows)}
        presented = run_history.present(
            {"id": "job-1", "resource": rate_impact.KEY, "status": "failed",
             "ran_at": None, "filters": filters, "progress": {}}
        )
    summary = presented["summary"]
    assert presented["filters"] == filters  # "Open in report" still replays these
    text = json.dumps(summary)
    for row in rows:
        assert row["item"] not in text and row["version"] not in text
    assert "W-58" not in text and '"W-1"' not in text
    head, *lines = summary
    assert head["parts"][-1] == {"label_key": "reports.input.months_other", "params": {"count": 3}}
    assert [line["parts"][:2] for line in lines] == [
        [{"text": "RI Water — water"}, {"text": "v2"}],
        [{"text": "RI Water — water"}, {"text": "v2"}],
        [{"text": "RI storm drain fee"}, {"text": "v1"}],
    ]
    # Figures at their STORED precision; the screen rounds for display (hard
    # rule 2: an amount at 2, a unit price up to 4).
    assert lines[0]["figures"] == [
        {"label_key": "reports.rateImpact.input.rows.column.base", "kind": "money",
         "value": "10.0000"},
        {"label_key": "reports.rateImpact.input.rows.column.price", "kind": "unit_price",
         "value": "4.5000"},
        {"label_key": "reports.rateImpact.input.rows.column.min", "kind": "money",
         "value": "20.0000"},
    ]
    assert lines[2]["figures"] == [
        {"label_key": "reports.rateImpact.input.rows.column.base", "kind": "money",
         "value": "6.0000"},
    ]
    # A history row whose stored rows no longer resolve says so in no words —
    # it carries no summary rather than an id.
    with tenant_ctx(brazos):
        broken = run_history.present(
            {"id": "job-2", "resource": rate_impact.KEY, "status": "failed", "ran_at": None,
             "filters": {"rows": "not json"}, "progress": {}}
        )
        other = run_history.present(
            {"id": "job-3", "resource": "statement", "status": "failed", "ran_at": None,
             "filters": {"from": "2026-09-01"}, "progress": {}}
        )
    assert broken["summary"] is None and other["summary"] is None
