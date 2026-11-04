# ── Trace ──────────────────────────────────────────────
# Rulings: PO 2026-09-30, decision log (seven rows at the top of
#          12-governance/02-decision-log.md), built as build plan B1 · B2 ·
#          B3 · B5 · B6 · B8 (04-docs/05-modules/07-billing/
#          12-one-time-bill-build-plan.md):
#            B1 — a %-of-service (sewer) has no service point of its own and is
#                 billed whenever its basis service (water) is billed;
#            B2 — no asset = not in service, even when the account took the
#                 service (%-of-service is the one exception);
#            B3 — not in service prints NO line (it counts as $0) and still
#                 lands on BR-BIL-301's review list;
#            B5 — two meters on one metered service are two lines, each on its
#                 own tier ladder with its own base: 2 × ($21.20 + $8.00) =
#                 $58.40 (was $29.20);
#            B6 — a counted service charges its base per asset: 2 carts at
#                 $15.00 with a $3.00 base = 2 × ($15.00 + $3.00) = $36.00
#                 (was $33.00);
#            B8 — an account with no service agreements on file is billed for
#                 every connected service AND carries a warning.
# Rules:   BR-BIL-300 · BR-BIL-301 · BR-BIL-1048 · BR-RAT-015 · BR-RAT-090 ·
#          CLAUDE.md hard rules 2 (money 4dp) and 3 (units explicit)
# Tests:   this file
# Impacts: apps/billing/gather.py (_unconnected_plan_services,
#          _plan_services_not_taken, _per_size_configs, _tariffs_for_plan,
#          gather_account) · apps/billing/runs.py (readings_for_account,
#          price_account, _decisions_for) · apps/billing/stages/
#          measure_consumption.py (_reading_for) · apps/rating/engine.py
#          (basis summed across a service's meters)
# ───────────────────────────────────────────────────────
"""**THE 2026-09-30 SERVICES RULINGS, ONE CASE EACH, PRICED THROUGH THE REAL
`runs.price_account`** — stages 1 → 5, the same function a bill run and the
one-time bill call, so a figure asserted here is the figure a customer reads.

── RED BEFORE THE FIX (law 7), quoted in each case's docstring ──────────────
Every case was run against the lane's base `3c457db` first; the failure each
one printed is quoted where it is asserted.

⚠ **THE FIXTURE PUBLISHES `assets.asset_ids_for_service_point`, AND WITHOUT IT
NOTHING HERE IS PROVED.** An unpublished seam is *nobody can tell* and must
narrow nothing (the three-valued rule every absence on this path follows), so
a world that forgot it would bill gas and fire exactly as the tip does and the
B2 cases would pass for the wrong reason. `tc_b2_2` asserts the degrade
explicitly.

⚠ **THE RESOLUTION CHAIN IS ROLLED BACK FOR THE REASON THE SIBLING FILES
GIVE** (`test_br_bil_1048_account_takes_a_subset.py`): its rating catalogue
reads `app.tenant_id`, which a fixture of plain namespaces cannot supply.
Every ruling here acts in `gather` BEFORE `resolution_switch.apply`.
"""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.billing import gather, resolution_shadow, runs
from apps.billing.contracts import ServiceReading
from apps.billing.rating_seam import Quantity

PERIOD_START = date(2026, 6, 1)
PERIOD_END = date(2026, 6, 30)
SERVICE_DATE = date(2026, 6, 30)
#: The catalogue key the other lanes render (`13-one-time-bill-api-contract.md`).
WARN_NO_AGREEMENTS = "billing.oneTime.warn.noAgreements"


@pytest.fixture(autouse=True)
def _rolled_back_resolution_chain(settings, monkeypatch):
    settings.BILLING_RESOLUTION_STEPS = ""
    # `_continuity_decisions` reads the invoice table for the tenant; it is a
    # neighbouring rule and this fixture has no tenant context (the same stub
    # `test_br_bil_301_not_connected_zero_line.py::tc8` takes).
    monkeypatch.setattr(runs, "_continuity_decisions", lambda *_a, **_k: [])


def an_account(**overrides):
    values = dict(
        id="acct-930",
        account_no="AC-2026-00930",
        unit_id="unit-930",
        status=SimpleNamespace(behavior_class="billable"),
        tax_exempt=False,
        opened_at=None,
        closed_at=None,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


#: The worked figures, held where a reader can count them.
WATER_TIERS = [
    {"upper": "5", "unit_price": "3.25"},
    {"upper": None, "unit_price": "4.50"},
]
BASES = {
    "water": "8.00",
    "sewer": "5.00",
    "gas": "6.00",
    "fire": "9.00",
    "trash": "3.00",
    "electric": "10.00",
}


#: Sewer's own rate, per kgal of the water it takes (BR-RAT-1015, CR-081).
SEWER_RATE = "5.00"


def _pricing_inputs(tariff, _service_date, *_size, sewer_basis="usage", **_kw):
    service = getattr(tariff, "service", None)
    common = {
        "version_id": f"v-{service}",
        "minimum_bill": None,
        "currency": "USD",
        "tiers": [],
        "unit_price": None,
    }
    if service == "water":
        return {**common, "model": "tiered", "billed_unit": "kgal", "tiers": WATER_TIERS}
    if service == "sewer":
        # ⚠ **THE SIGNED SEWER RULE IS BR-RAT-1015 (2026-09-08), NOT BR-RAT-015**:
        # sewer is 40% of the water QUANTITY priced at sewer's OWN rate — the
        # `usage` basis, and the default here. `charge` (40% of water's usage
        # DOLLARS) is the tenant's other setting (`tariff_versions
        # .percent_basis`, CR-130) and is exercised by `b5_tc3` beside it.
        # Every sewer figure below is the ENGINE's; nothing is hand-priced.
        if sewer_basis == "charge":
            return {
                **common,
                "model": "percent_of_service",
                "billed_unit": "kgal",
                "percent": "40",
                "basis_service": "water",
                "percent_basis": "charge",
            }
        return {
            **common,
            "model": "percent_of_service",
            "billed_unit": "kgal",
            "unit_price": SEWER_RATE,
            "percent": "40",
            "basis_service": "water",
            "percent_basis": "usage",
        }
    if service == "fire":
        return {
            **common,
            "model": "flat",
            "billed_unit": "connection",
            "unit_price": "60.00",
            "size_groups": ["FL-2", "FL-4", "FL-6", "FL-8", "FL-10", "FL-12"],
        }
    if service == "trash":
        return {**common, "model": "flat", "billed_unit": "cart", "unit_price": "15.00"}
    if service == "gas":
        return {**common, "model": "flat", "billed_unit": "therm", "unit_price": "1.00"}
    return {**common, "model": "flat", "billed_unit": "kWh", "unit_price": "0.10"}


def _world(
    *,
    plan_services,
    unit_services,
    assets,
    size_groups=None,
    taken="unpublished",
    sewer_basis="usage",
):
    """`unit_services` — which service POINTS exist · `assets` — which of those
    points carry an asset (`{service: [asset ids]}`) · `taken` — the account's
    agreements: `"unpublished"` (nobody can tell), `None` (published, no
    agreement on file) or a tuple of codes."""
    size_groups = size_groups or {}
    world = {
        "metering.service_points_for": lambda _id: [
            {"id": f"sp-{code}", "service": code, "route_id": None}
            for code in unit_services
        ],
        "assets.asset_ids_for_service_point": lambda point_id: list(
            assets.get(str(point_id).removeprefix("sp-"), [])
        ),
        "metering.connection_size_for": lambda _unit, code: (
            "FL-6" if code == "fire" and assets.get("fire") else None
        ),
        "metering.billing_multiplier_for": lambda _unit, _code: Decimal("1"),
        "metering.billable_size_groups": lambda _unit, code, _as_of: (
            dict(size_groups[code]) if code in size_groups else None
        ),
        "metering.unit_row": lambda _id: SimpleNamespace(
            id="unit-930", label="Unit 1", rate_plan_id="plan-res", premises=None
        ),
        "rating.plan_ref": lambda _id: {"id": "plan-res", "name": "Residential", "version": 1},
        "rating.plan_rate_schedules": lambda _id: [
            {"service_code": code, "tariff": SimpleNamespace(id=f"t-{code}", service=code)}
            for code in plan_services
        ],
        "rating.pricing_inputs": (
            lambda tariff, service_date, *size, **kw: _pricing_inputs(
                tariff, service_date, *size, sewer_basis=sewer_basis, **kw
            )
        ),
        "rating.base_charge_from_charge_code": lambda service_code, **_k: {
            "amount": BASES[service_code],
            "code": f"BASE-{service_code.upper()}",
            "refusal": None,
        },
        "rating.plan_tax_rules": lambda *_a, **_k: [],
        "tenancy.regional_settings": lambda: {"currency": "USD"},
    }
    if taken != "unpublished":
        world["customers.billed_service_codes_for"] = lambda _a, **_k: (
            None if taken is None else tuple(taken)
        )
    return world


def _install(monkeypatch, published):
    def resolve(module, attribute, kind="selectors"):
        return published.get(f"{module}.{attribute}")

    monkeypatch.setattr(gather, "_resolve", resolve)
    monkeypatch.setattr(resolution_shadow, "_seam", resolve)


def _gather(readings):
    return gather.gather_account(
        account=an_account(),
        service_date=SERVICE_DATE,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        cycle_days=30,
        readings=tuple(readings),
    )


def _water(amount, *, asset_id=None):
    # `asset_id` is passed only when a case names a meter, so every case that
    # is not about two meters constructs exactly the reading the tip could.
    extra = {} if asset_id is None else {"asset_id": asset_id}
    return ServiceReading(
        service_code="water",
        consumption=Quantity(amount=Decimal(str(amount)), unit="kgal"),
        **extra,
    )


def _lines(priced, service):
    return [line for line in priced.priced.lines if line.service == service]


def _total(priced, service=None):
    return sum(
        (line.amount for line in priced.priced.lines if service is None or line.service == service),
        Decimal("0"),
    )


# ══════════════════════════════════════════════════════════════════════════
# B1 · SEWER HAS NO SERVICE POINT AND FOLLOWS WATER
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-1
def test_b1_tc1__sewer_with_no_point_bills_40_percent_of_water(monkeypatch):
    """**5 kgal of water; sewer is 40% of it = 2 kgal at sewer's own $5.00 =
    `$10.00`** (BR-RAT-1015, the `usage` basis), plus its own $5.00 base. The
    unit has NO sewer point — the PO: *"for % of service there will not be any
    service point"*.

    RED BEFORE THE FIX: sewer was marked *not connected* and billed a `$0.00`
    line — `AssertionError: assert [] == ['sewer']` on the tariff list, and
    the whole sewer charge was lost (`$76.50` a month on the BR-BIL-1048
    measured account).
    """
    _install(
        monkeypatch,
        _world(
            plan_services=["water", "sewer"],
            unit_services=["water"],
            assets={"water": ["m-1"]},
        ),
    )
    data = _gather([_water(5)])

    assert [c.service for c in data.tariffs if c.service == "sewer"] == ["sewer"]
    assert "sewer" not in data.unconnected_services
    priced = runs.price_account(data)
    sewer_usage = [line for line in _lines(priced, "sewer") if line.kind == "usage"]
    assert len(sewer_usage) == 1, [(ln.kind, ln.description) for ln in _lines(priced, "sewer")]
    assert sewer_usage[0].amount == Decimal("10.00")
    assert _total(priced) == Decimal("16.25") + Decimal("8.00") + Decimal("10.00") + Decimal("5.00")


# BULK-CHG-1
def test_b1_tc2__sewer_follows_water_into_not_in_service(monkeypatch):
    """**Water has a point and no meter, so water is not in service — and sewer
    follows it.** Neither prints a line; both reach the clerk's review list.
    Without this, sewer would be priced over a water line that does not exist
    and refuse on `BasisUnavailable` — the account stopped over a service the
    PO has ruled is simply absent.
    """
    _install(
        monkeypatch,
        _world(
            plan_services=["water", "sewer", "electric"],
            unit_services=["water", "electric"],
            assets={"electric": ["e-1"]},
        ),
    )
    reads = [
        ServiceReading(service_code="water", absent_reason="no_meter"),
        ServiceReading(
            service_code="electric", consumption=Quantity(amount=Decimal("100"), unit="kWh")
        ),
    ]
    data = _gather(reads)

    assert [c.service for c in data.tariffs] == ["electric"]
    assert set(data.unconnected_services) == {"water", "sewer"}
    priced = runs.price_account(data)
    assert {line.service for line in priced.priced.lines} == {"electric"}


# BULK-CHG-1
def test_b1_tc3__sewer_is_taken_whenever_water_is_even_with_no_sewer_agreement(monkeypatch):
    """**A sewer point cannot exist, so a sewer AGREEMENT cannot either.** The
    account holds water only; sewer is on the bill because water is. Treating
    the missing sewer agreement as *not bought* would drop the same `$10.00`
    the other way.
    """
    _install(
        monkeypatch,
        _world(
            plan_services=["water", "sewer"],
            unit_services=["water"],
            assets={"water": ["m-1"]},
            taken=("water",),
        ),
    )
    data = _gather([_water(5)])

    assert sorted(c.service for c in data.tariffs) == ["sewer", "water"]


# BULK-CHG-1
def test_b1_tc4__sewer_is_not_taken_when_water_is_not_taken(monkeypatch):
    """The mirror: the account did not buy water, so sewer is not on the bill
    either — and NOT on the review list, because nothing is missing from the
    property; the customer declined it (BR-BIL-1048's *no line of any kind*)."""
    _install(
        monkeypatch,
        _world(
            plan_services=["water", "sewer", "electric"],
            unit_services=["water", "electric"],
            assets={"water": ["m-1"], "electric": ["e-1"]},
            taken=("electric",),
        ),
    )
    data = _gather(
        [
            ServiceReading(
                service_code="electric",
                consumption=Quantity(amount=Decimal("100"), unit="kWh"),
            )
        ]
    )

    assert [c.service for c in data.tariffs] == ["electric"]
    assert "sewer" not in data.unconnected_services


# ══════════════════════════════════════════════════════════════════════════
# B2 + B3 · NO ASSET = NOT IN SERVICE, AND NOT IN SERVICE PRINTS NO LINE
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-2
def test_b2_tc1__gas_with_no_meter_prints_no_line_and_the_bill_completes(monkeypatch):
    """**The PO's six-service unit, reduced to its point:** gas has a service
    point and no meter. It is not in service — no tariff, no line, no refusal —
    and the account still lands on BR-BIL-301's review list.

    RED BEFORE THE FIX: `apps.billing.gather.GatherProblem: account
    AC-2026-00930: gas still has no usable read and no decision. BR-BIL-015
    makes that a choice …` — the whole account was refused as a missing read.
    """
    _install(
        monkeypatch,
        _world(
            plan_services=["water", "gas"],
            unit_services=["water", "gas"],
            assets={"water": ["m-1"]},
        ),
    )
    reads = [_water(5), ServiceReading(service_code="gas", absent_reason="no_meter")]
    data = _gather(reads)
    priced = runs.price_account(data)

    assert [c.service for c in data.tariffs] == ["water"]
    assert _lines(priced, "gas") == []
    assert [f for f in data.fees if f.service == "gas"] == []
    assert _total(priced) == Decimal("16.25") + Decimal("8.00")
    # B3 — still on the list a clerk works through, and NOT as a missing read.
    rows = runs._decisions_for(data, ("gas",))
    assert [(r.reason, r.service_code) for r in rows] == [("service_not_connected", "gas")]


# BULK-CHG-2
def test_b2_tc2__an_unpublished_assets_seam_narrows_nothing(monkeypatch):
    """**Nobody can tell ≠ nobody installed anything.** With the assets seam
    unpublished gas keeps its tariff and the missing read still stops the
    account by name — the degrade moves no money."""
    published = _world(
        plan_services=["water", "gas"],
        unit_services=["water", "gas"],
        assets={"water": ["m-1"]},
    )
    published.pop("assets.asset_ids_for_service_point")
    _install(monkeypatch, published)
    data = _gather([_water(5), ServiceReading(service_code="gas", absent_reason="no_meter")])

    assert sorted(c.service for c in data.tariffs) == ["gas", "water"]
    with pytest.raises(gather.GatherProblem) as raised:
        runs.price_account(data)
    assert raised.value.reason == runs.CALC_UNRESOLVED_READ


# BULK-CHG-2
def test_b2_tc3__a_metered_service_with_a_meter_and_no_read_still_refuses(monkeypatch):
    """**The half of the ruling that is NOT a relaxation**: *"A metered
    service WITH a meter and no reading is still a real missing read."*"""
    _install(
        monkeypatch,
        _world(
            plan_services=["water", "gas"],
            unit_services=["water", "gas"],
            assets={"water": ["m-1"], "gas": ["g-1"]},
        ),
    )
    data = _gather([_water(5), ServiceReading(service_code="gas", absent_reason="no_read")])

    with pytest.raises(gather.GatherProblem) as raised:
        runs.price_account(data)
    assert raised.value.reason == runs.CALC_UNRESOLVED_READ


# BULK-CHG-2
def test_b2_tc4__fire_with_no_asset_prints_no_line_and_no_base(monkeypatch):
    """**Fire has a point and nothing on it.** No line, and — the expensive
    half — no `$9.00` base charge for a connection with nothing on it.

    RED BEFORE THE FIX: the empty size map built a fire config carrying its
    base — `AssertionError: assert ['water', 'fire'] == ['water']`, and the
    bill charged `$9.00` a month for fire.
    """
    _install(
        monkeypatch,
        _world(
            plan_services=["water", "fire"],
            unit_services=["water", "fire"],
            assets={"water": ["m-1"]},
            size_groups={"fire": {}},
        ),
    )
    reads = [
        _water(5),
        ServiceReading(
            service_code="fire",
            absent_reason="service_not_metered",
            asset_count=0,
            asset_size_counts={},
        ),
    ]
    data = _gather(reads)
    priced = runs.price_account(data)

    assert [c.service for c in data.tariffs] == ["water"]
    assert _lines(priced, "fire") == []
    assert [f for f in data.fees if f.service == "fire"] == []
    assert _total(priced) == Decimal("24.25")
    assert "fire" in data.unconnected_services


# BULK-CHG-2
def test_b3_tc1__not_in_service_prints_no_line_on_any_channel(monkeypatch):
    """**PO 2026-09-30: *"sane no line - and use 0"*.** The `$0.00 (not
    connected)` line BR-BIL-301 printed since 2026-09-25 is gone from the
    document; the service is still carried as data for the screen.

    RED BEFORE THE FIX: `AssertionError` — `data.fees` held
    `fire (not connected)` at `0.0000`.
    """
    _install(
        monkeypatch,
        _world(plan_services=["water", "fire"], unit_services=["water"], assets={"water": ["m-1"]}),
    )
    data = _gather([_water(5)])

    assert [f.description for f in data.fees] == []
    assert data.unconnected_services == ("fire",)


# ══════════════════════════════════════════════════════════════════════════
# B5 · TWO WATER METERS, TWO LINES, $58.40
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-4
def test_b5_tc1__two_water_meters_bill_two_lines_each_with_its_own_ladder(monkeypatch):
    """**2 × ($21.20 + $8.00) = `$58.40`.** Each meter: 5 kgal × $3.25 =
    $16.25 + 1.1 kgal × $4.50 = $4.95 → $21.20 usage, plus its own $8.00 base.

    RED BEFORE THE FIX: `AssertionError: assert Decimal('29.20') ==
    Decimal('58.40')` — one config, one reading, and the second meter's
    usage and base were never charged.
    """
    _install(
        monkeypatch,
        _world(plan_services=["water"], unit_services=["water"], assets={"water": ["m-1", "m-2"]}),
    )
    data = _gather([_water("6.1", asset_id="m-1"), _water("6.1", asset_id="m-2")])
    priced = runs.price_account(data)

    assert [(c.service, c.asset_id) for c in data.tariffs] == [
        ("water", "m-1"),
        ("water", "m-2"),
    ]
    assert _total(priced) == Decimal("58.40")
    for meter in ("m-1", "m-2"):
        mine = [line for line in priced.priced.lines if line.asset_id == meter]
        assert sum((line.amount for line in mine), Decimal("0")) == Decimal("29.20"), meter
        assert sorted(line.kind for line in mine) == ["base", "usage", "usage"]


# BULK-CHG-4
def test_b5_tc2__each_meter_is_paired_with_its_own_reading(monkeypatch):
    """**Different usage on each meter proves the pairing** — two equal reads
    would pass even if both configs picked up the first one. 6.1 kgal →
    $21.20 and 3 kgal → $9.75; with $8.00 base each: `$46.95`."""
    _install(
        monkeypatch,
        _world(plan_services=["water"], unit_services=["water"], assets={"water": ["m-1", "m-2"]}),
    )
    data = _gather([_water("6.1", asset_id="m-1"), _water("3", asset_id="m-2")])
    priced = runs.price_account(data)

    assert _total(priced) == Decimal("46.95")
    m2 = [line for line in priced.priced.lines if line.asset_id == "m-2" and line.kind == "usage"]
    assert [line.amount for line in m2] == [Decimal("9.75")]


# BULK-CHG-1
@pytest.mark.parametrize(
    ("sewer_basis", "expected"),
    [
        # 40% × (6.1 + 6.1) kgal = 4.88 kgal at sewer's own $5.00.
        ("usage", Decimal("24.40")),
        # 40% × ($21.20 + $21.20) of water usage charges.
        ("charge", Decimal("16.96")),
    ],
)
def test_b5_tc3__sewer_is_one_line_on_both_meters_combined(monkeypatch, sewer_basis, expected):
    """**Sewer has no meter of its own, so it is ONE line on the COMBINED
    water basis** — PO 2026-09-30, by the tenant's own `percent_basis`:
    `usage` → 40% × the summed water QUANTITY at sewer's rate (4.88 kgal ×
    $5.00 = `$24.40`); `charge` → 40% × the summed water usage CHARGES
    (`$16.96`).

    RED BEFORE THE FIX (the engine half, proved with `apps/rating/engine.py`
    at the lane's base and everything else built): the basis was stored per
    SERVICE, so the second meter OVERWROTE the first — `usage` priced
    `Decimal('12.20')` and `charge` `Decimal('8.48')`: half the sewer.
    """
    _install(
        monkeypatch,
        _world(
            plan_services=["water", "sewer"],
            unit_services=["water"],
            assets={"water": ["m-1", "m-2"]},
            sewer_basis=sewer_basis,
        ),
    )
    data = _gather([_water("6.1", asset_id="m-1"), _water("6.1", asset_id="m-2")])
    priced = runs.price_account(data)

    assert [c.asset_id for c in data.tariffs if c.service == "sewer"] == [None]
    sewer_usage = [line for line in _lines(priced, "sewer") if line.kind == "usage"]
    assert [line.amount for line in sewer_usage] == [expected]


# BULK-CHG-4
def test_b5_tc4__readings_for_account_keeps_one_row_per_meter(monkeypatch):
    """**`runs.readings_for_account` dropped the second reading of a service**
    (`if reading.service_code in seen: continue`). Metering now publishes one
    row per meter with its `asset_id`; both must reach the gather.

    RED BEFORE THE FIX: `assert 1 == 2`.
    """
    rows = [
        {
            "service_code": "water",
            "service_id": "svc-w",
            "service_point_id": "sp-water",
            "asset_id": meter,
            "consumption": Decimal("6.1"),
            "unit": "kgal",
            "estimated": False,
            "absent_reason": None,
            "prior_value": None,
            "current_value": None,
            "read_id": f"r-{meter}",
            "multiplier": Decimal("1"),
            "windows": [],
            "demand": None,
        }
        for meter in ("m-1", "m-2")
    ]
    _install(monkeypatch, {"metering.billing_reads_for_unit": lambda *_a, **_k: rows})

    readings, _unmeasured = runs.readings_for_account(
        an_account(),
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        scope_services=None,
    )

    assert [(r.service_code, r.asset_id, r.read_id) for r in readings] == [
        ("water", "m-1", "r-m-1"),
        ("water", "m-2", "r-m-2"),
    ]


# ══════════════════════════════════════════════════════════════════════════
# B6 · A COUNTED SERVICE CHARGES ITS BASE PER ASSET
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-5
def test_b6_tc1__two_carts_bill_two_bases(monkeypatch):
    """**PO option B: 2 × ($15.00 + $3.00) = `$36.00`** (was `$33.00`, one
    base for the connection).

    RED BEFORE THE FIX: `AssertionError: assert Decimal('33.00') ==
    Decimal('36.00')`.
    """
    _install(
        monkeypatch,
        _world(
            plan_services=["trash"],
            unit_services=["trash"],
            assets={"trash": ["c-1", "c-2"]},
            size_groups={"trash": {"CART-96": 2}},
        ),
    )
    reads = [
        ServiceReading(
            service_code="trash",
            absent_reason="service_not_metered",
            asset_count=2,
            asset_size_counts={"CART-96": 2},
        )
    ]
    data = _gather(reads)
    priced = runs.price_account(data)

    assert _total(priced) == Decimal("36.00")
    # ⚠ AMENDED 2026-09-30 (DEF-BIL-8151) — this asserted a `$6.00` base LINE.
    # The same day's later ruling (*"SIX ANSWERS"* (5), PO verbatim: *"per
    # service"*) prints a counted service as ONE line, so the `$30.00` usage
    # and the `$6.00` base are one `$36.00` line of 2 carts at `$18.00`. The
    # per-asset base (option B) is still in it: `$36.00`, not `$33.00`.
    (line,) = _lines(priced, "trash")
    assert (line.amount, line.quantity, line.unit_price) == (
        Decimal("36.00"),
        Decimal("2"),
        Decimal("18.00"),
    )


# BULK-CHG-5
def test_b6_tc2__the_base_is_per_asset_on_one_line_per_service(monkeypatch):
    """**The fire warehouse: one 6" line and two 2" lines.** The base is per
    asset — `3 × $9.00 = $27.00`, where it was ONE `$9.00` — and, by the PO's
    later ruling the same day (*"SIX ANSWERS"* (5), *"per service"*), it is ONE
    base line for the service: the whole `$27.00` rides on the first group
    (`FL-2`, sorted first) and the other group states none.

    RED against this lane's first cut (base per GROUP): `[('FL-2', 18.00),
    ('FL-6', 9.00)]` — two base lines."""
    _install(
        monkeypatch,
        _world(
            plan_services=["fire"],
            unit_services=["fire"],
            assets={"fire": ["f-1", "f-2", "f-3"]},
            size_groups={"fire": {"FL-6": 1, "FL-2": 2}},
        ),
    )
    reads = [
        ServiceReading(
            service_code="fire",
            absent_reason="service_not_metered",
            asset_count=3,
            asset_size_counts={"FL-6": 1, "FL-2": 2},
        )
    ]
    data = _gather(reads)

    bases = sorted((c.size_class, c.base_charge) for c in data.tariffs)
    assert bases == [("FL-2", Decimal("27.00")), ("FL-6", None)]


# ══════════════════════════════════════════════════════════════════════════
# B8 · NO AGREEMENTS ON FILE — BILL EVERY CONNECTED SERVICE, AND WARN
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-6
def test_b8_tc1__no_agreements_bills_everything_and_warns(monkeypatch):
    """**PO option C: *"The bill still goes out, and the clerk sees the gap and
    can fix the account."*** Customers answers `None` — the account holds no
    agreement at all (an older import). Every connected service bills, and a
    named warning rides with the priced result.

    RED BEFORE THE FIX: `AttributeError: 'AccountBillingData' object has no
    attribute 'warnings'`.
    """
    _install(
        monkeypatch,
        _world(
            plan_services=["water", "electric"],
            unit_services=["water", "electric"],
            assets={"water": ["m-1"], "electric": ["e-1"]},
            taken=None,
        ),
    )
    reads = [
        _water(5),
        ServiceReading(
            service_code="electric", consumption=Quantity(amount=Decimal("100"), unit="kWh")
        ),
    ]
    data = _gather(reads)
    priced = runs.price_account(data)

    assert sorted(c.service for c in data.tariffs) == ["electric", "water"]
    assert [w["key"] for w in data.warnings] == [WARN_NO_AGREEMENTS]
    assert all(set(w) == {"key", "params"} for w in data.warnings)
    assert tuple(priced.warnings) == tuple(data.warnings)
    from apps.billing import contracts

    assert contracts.WARN_NO_AGREEMENTS == WARN_NO_AGREEMENTS


# BULK-CHG-6
def test_b8_tc2__an_account_with_agreements_carries_no_warning(monkeypatch):
    """The discriminator: agreements on file → no warning. And *nobody can
    tell* (customers unpublished) → no warning either, because nobody looked."""
    for taken in (("water",), "unpublished"):
        _install(
            monkeypatch,
            _world(
                plan_services=["water"],
                unit_services=["water"],
                assets={"water": ["m-1"]},
                taken=taken,
            ),
        )
        assert _gather([_water(5)]).warnings == (), taken


# BULK-CHG-4
def test_b5_tc5__the_minimum_applies_to_each_meter(monkeypatch):
    """**PO 2026-09-30 (*"SIX ANSWERS"* (4)): *"consider them 2 lines anc
    charge"*.** Minimum $10.00: meter A's usage $6.00 is lifted to $10.00,
    meter B's $14.00 stands — usage `$24.00`, not `$20.00`.

    RED against this lane's first cut (minimum on the first meter only): the
    usage total read `$20.00`."""
    minimum = {"minimum_bill": "10.00"}

    def with_minimum(tariff, service_date, *size, **kw):
        inputs = _pricing_inputs(tariff, service_date, *size, **kw)
        if getattr(tariff, "service", None) == "water":
            # A flat $1.00 per kgal so the usage figures are the PO's own.
            inputs = {**inputs, **minimum, "model": "flat", "unit_price": "1.00", "tiers": []}
        return inputs

    world = _world(
        plan_services=["water"], unit_services=["water"], assets={"water": ["m-1", "m-2"]}
    )
    world["rating.pricing_inputs"] = with_minimum
    # A $0.00 base, stated: a minimum is measured against usage AND base
    # (BR-RAT-028), and the PO's figure is usage alone.
    world["rating.base_charge_from_charge_code"] = lambda service_code, **_k: {
        "amount": "0.00",
        "code": "BASE-W",
        "refusal": None,
    }
    _install(monkeypatch, world)
    # The $14.00 meter is FIRST, so a minimum on the first meter only (this
    # lane's first cut) would leave the $6.00 meter unlifted: $20.00.
    data = _gather([_water("14", asset_id="m-1"), _water("6", asset_id="m-2")])
    priced = runs.price_account(data)

    non_base = [line for line in priced.priced.lines if line.kind != "base"]
    assert sum((line.amount for line in non_base), Decimal("0")) == Decimal("24.00"), [
        (line.kind, line.asset_id, line.amount) for line in non_base
    ]
