# ── Trace ──────────────────────────────────────────────
# Change:   **CR-062 tasks D3–D7** (2026-09-02) — plant the billable capacity
#           equipment on the demo estate, so a seeded capacity PRICE has
#           something installed to multiply by.
# Rules:    BR-RAT-090 (as amended 2026-09-02 — a capacity quantity is a COUNT
#           for a BANDED service and a SUM for a service whose size classes
#           carry a capacity) · BR-TEN-171 (which codes are ratified, and what
#           each is worth) · BR-AST-500 (the size class lives on the device) ·
#           BR-AST-009 (a non-measuring device declares no register) ·
#           BR-MET-108 (the ruled zero — no equipment bills $0.00, it does not
#           refuse) · BR-MET-003 (never a service point for a service the
#           tenant does not sell) · CLAUDE.md hard rule 3 (an explicit unit)
# Tests:    this file
# Impacts:  core/sample_fixture.capacity_equipment_plan ·
#           apps/assets/sample_data._seed_cr062_capacity_equipment ·
#           tests/test_cr062_e_rates.test_live_what_each_priced_service_
#           actually_bills_today (updated by this change, by its own request)
# ───────────────────────────────────────────────────────
"""**THE PRODUCT OWNER'S SOLAR ARRAY BILLS `$196.00` ON A SEEDED TENANT.**

PO verbatim, 2026-09-02:

    "on given Unit we have installed 3 panels with 2Kw, 4Kw and 8 Kw , it means
     the totla capacity will be 14 Kw ; rate will be for 1 Kw = 14 $ per KW"

14 kW at `$14.0000` is **`$196.00`**. (Their message says *156*; 14 × 14 is 196,
they were told so in the same session and did not dispute it, and `$156` is
written nowhere in this repo.)

**THIS IS THE THIRD OF THREE LANES AND NEITHER OF THE OTHER TWO PRODUCED A
DOLLAR ON ITS OWN.** `CR-062` E3 seeded the price. `CR-062` D1/H2 made the
quantity the SUM of installed capacity rather than a COUNT of panels — `$42.00`
became `$196.00` **in that file's own fixture**. And a SEEDED tenant still billed
`$0.00` for solar, battery, broadband and storm water, because the estate had no
capacity equipment standing on it at all. Both lanes wrote that boundary down
rather than leaving it to be found: *"the estate seeds no capacity equipment, so
a seeded tenant exercises the sum with 0 on every unit until they land"*. D3–D7
is the landing and this file is its proof.

RED FIRST (r11 step 2d · hard-won law 7)
----------------------------------------
These cases were run against an **untouched checkout of the branch tip**
(`133630e8`), extracted into its own tree, on real PostgreSQL 16.13, before a
line of the fixture changed. Unit indexes were LITERALS in that run, because the
constants this change adds do not exist at the tip and a probe that imported them
would have failed on the import and proved nothing about money.

**5 failed, 1 passed.** The failures, verbatim::

    AssertionError: unit 4's solar line is 0.000000, not $196.00 -- nothing is
    installed to multiply the seeded $14.0000 per kW by
    assert Decimal('0.000000') == Decimal('196.00')

    AssertionError: assert Decimal('0.000000') == Decimal('70.00')

    AssertionError: 10 kW x $3.0000 is $30.00; the bill says 0.000000
    assert Decimal('0.000000') == Decimal('30.00')

    AssertionError: broadband bills {8: Decimal('0.000000'), 10:
    Decimal('0.000000'), 20: Decimal('0.000000')}, expected {8: Decimal('10.00'),
    10: Decimal('50.00'), 20: Decimal('100.00')}

    AssertionError: solar bills $0.00 on EVERY unit, so this case proves nothing
    -- a zero is only a real answer when it sits beside a real number
    assert Decimal('0.000000') > 0

**AND THE ONE THAT PASSED AT THE TIP MATTERS JUST AS MUCH**, because it is the
half that must not move: ❄️ `GT-17`'s water `$39.50` and sewer `$15.80`. It is
green on both trees and is named rather than counted as a win.

WHAT IS NOT HERE, AND IT IS NAMED RATHER THAN LEFT TO BE DISCOVERED
------------------------------------------------------------------
**Storm water (`D6`) is NOT planted and cannot be, and the obstacle is
vocabulary rather than arithmetic.** A capacity total is read off
`Asset.size_class` through the asset's service point, so an ERU has to arrive on
a DEVICE — and there is no device. `BR-AST-042`'s ratified twelve asset types
hold a meter, a sub-meter, a backflow preventer, a comms endpoint, a PV array, a
battery, an EV charger, a transformer, a generator, a container/cart and a
modem/CPE. **None of them is a storm-water connection**, an impervious-area
assessment is not equipment, and `OQ-348` was CLOSED by the Product Owner
choosing a typed characteristic on the unit and REJECTING tenant-extended asset
types for exactly this class of thing. That is filed as `DEF-2388` with its
options; nothing here invents a thirteenth type. **Storm water therefore still
bills `$0.00` on a seeded tenant and its `$4.5000` per ERU is still unexercised.**
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.assets import models as asset_models
from apps.billing import models as billing_models
from apps.customers import models as customer_models
from apps.metering import models as metering_models
from apps.tenancy import sample_data as tenancy_sample_data
from apps.tenancy import service_size_classes as sizes
from apps.rating import service_base_amounts
from core import sample_fixture as fixture

from tests.isolation_helpers import requires_postgres
from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (
    brazosbend_payload,
    provisioned_tenant,
    tenant_ctx,
)

#: No module-level `django_db` mark: Part 1 reads no database and must be able
#: to fail in milliseconds. The live cases carry the mark themselves.
_live = pytest.mark.django_db

#: A utility selling WATER + SEWER (so ❄️ `GT-17`'s reference bill is on the same
#: tenant and any movement in it is visible immediately) and the capacity
#: services this change plants.
#:
#: ⚠ **FIRE IS NOT HERE, AND `FIRE_SHAPE` BELOW IS WHY (`DEF-AST-9083`).**
#: `8a4b3c245` (2026-09-07) appended `fire_line_plan()` to
#: `capacity_equipment_plan()` and did not give this file a tenant that sells
#: fire, so the seeder skipped all six `FS-` lines BY NAME — correctly — and the
#: estate case was red for 25 days, unread because it is `@requires_postgres`.
#: Fire gets a tenant of its own so this file's estate stays the one its
#: figures were written for.
#:
#: ⚠ **CORRECTED 2026-10-02 (`DEF-RAT-9092`).** This note said a tenant selling
#: fire *"is seeded a different plan (base charges on battery, broadband and
#: sewer; sewer at 90% of water volume)"*. **Every tenant is**, this one
#: included — measured on PostgreSQL 16 the same day. The bases came on
#: 2026-09-07 (`7a7638d70`, `service_base_amounts.RESEARCHED_BASES`) and the
#: sewer volume on 2026-09-08 (`ace95d812`, `CR-081`, ❄️ `GT-17` RE-SIGNED), and
#: the cases below now assert each LINE KIND against its own ruling.
SHAPE: tuple[str, ...] = ("water", "sewer", "solar", "battery", "broadband")
#: The fire-selling utility: water and sewer, so it is an ordinary estate, plus
#: fire.
FIRE_SHAPE: tuple[str, ...] = ("water", "sewer", "fire")


# ══════════════════════════════════════════════════════════════════════════
# PART 1 · THE PURE LAYER — no database, milliseconds, fails first
# ══════════════════════════════════════════════════════════════════════════


def test_pure_no_capacity_equipment_stands_on_an_awkward_unit():
    """**The frozen-figure guard, applied to WHERE rather than to HOW MUCH.**

    `AWKWARD_UNITS` is every unit the fixture's narrative cases touch — the
    ❄️ `GT-17` reference bill, the disputed read, the meter swap, the refund, the
    write-off. Planting equipment on one of them changes a bill somebody has
    already signed off. `trash_cart_plan` chose its three units on exactly this
    rule and said so; this asserts it for the four capacity services rather than
    trusting a comment, on the plan AND on the deliberately-empty units.
    """
    planted = {entry["unit_index"] for entry in fixture.capacity_equipment_plan()}
    empty = set(fixture.CAPACITY_UNITS_WITH_NONE.values())
    assert not (planted & fixture.AWKWARD_UNITS), (
        f"capacity equipment stands on awkward unit(s) {sorted(planted & fixture.AWKWARD_UNITS)}; "
        "unit 0 alone is GT-17's $39.50 water / $15.80 sewer reference bill"
    )
    assert not (empty & fixture.AWKWARD_UNITS)
    assert fixture.CASE_REFERENCE_BILL not in planted


def test_pure_every_size_code_is_in_its_services_ratified_ladder():
    """**BR-TEN-171 — a demo tenant may not teach a vocabulary the product does
    not have.** The codes are checked against the ratified list here (cheap) as
    well as against the TENANT's own list in the seeder (correct), because those
    are two different failures: a typo in the fixture, and a tenant that has
    edited its ladder on Settings.
    """
    for entry in fixture.capacity_equipment_plan():
        ratified = {code for code, _name in sizes.size_classes_for_service(entry["service"])}
        assert entry["size_class"] in ratified, (
            f"{entry['asset_no']} claims {entry['size_class']!r}, which is not a "
            f"ratified {entry['service']} size class: {sorted(ratified)}"
        )


def test_pure_the_pos_own_array_is_two_plus_four_plus_eight_kilowatts():
    """**D3 · 2 + 4 + 8 = 14 kW, computed from the ratified rows and not from a
    number typed here.** `total_capacity` is tenancy's arithmetic; this asserts
    the FIXTURE feeds it the array the PO described.
    """
    on_unit = [
        entry["size_class"]
        for entry in fixture.capacity_equipment_plan()
        if entry["service"] == "solar"
        and entry["unit_index"] == fixture.SOLAR_UNIT_WITH_THREE_PANELS
    ]
    assert len(on_unit) == 3, f"the PO's example is THREE panels; the fixture plants {on_unit}"
    assert sizes.total_capacity("solar", on_unit) == Decimal("14")
    assert sizes.capacity_uom_for_service("solar") == "kW"
    # 14 kW × the seeded $14.0000 — quantised the way money is stored (rule 2).
    assert Decimal("14") * Decimal(fixture.CAPACITY_UNIT_PRICES["solar"]) == Decimal("196.0000")


def test_pure_the_several_one_none_shape_holds_for_every_planted_service():
    """**D7 · so a `$0.00` line is provably a real answer and not a gap.**

    `trash_cart_plan`'s three-case shape, copied: at least one unit carrying
    equipment, at least one carrying a DIFFERENT amount, and one named unit
    carrying none. Broadband's three units are three different tiers rather than
    a several/one pair, which is `D5` as written — a household buys one line, not
    three — so what it must have is what every service here must have: a unit
    with something, a unit with something else, and a unit with nothing.
    """
    for service in ("solar", "battery", "broadband"):
        by_unit: dict[int, list[str]] = {}
        for entry in fixture.capacity_equipment_plan():
            if entry["service"] == service:
                by_unit.setdefault(entry["unit_index"], []).append(entry["size_class"])
        assert len(by_unit) >= 2, f"{service} needs equipment on at least two units"
        totals = {sizes.total_capacity(service, codes) for codes in by_unit.values()}
        assert len(totals) >= 2, (
            f"every {service} unit carries the same total {totals}; the demo cannot "
            "show that the quantity is a SUM"
        )
        none_unit = fixture.CAPACITY_UNITS_WITH_NONE[service]
        assert none_unit not in by_unit, (
            f"{service}'s stated empty unit {none_unit} also carries equipment"
        )


def test_pure_no_asset_number_collides_with_anything_already_seeded():
    """**`BR-AST-033`'s duplicate-number hard block refuses at SEED time, on a
    tenant, in the middle of provisioning.** `PV-0001` and `BAT-0001` are
    `BTM_DEVICE_PLAN`'s and `CR028_DEVICE_PLAN`'s customer-owned devices, which
    is why this block numbers from 1001.
    """
    mine = list(fixture.capacity_equipment_numbers())
    assert len(mine) == len(set(mine)), "the plan repeats an asset number"
    taken = set(fixture.cr028_asset_numbers())
    taken |= {entry["asset_no"] for entry in fixture.BTM_DEVICE_PLAN}
    taken |= {entry["asset_no"] for entry in fixture.meter_plan()}
    taken |= {entry["asset_no"] for entry in fixture.sub_meter_plan()}
    assert not (set(mine) & taken), f"already seeded: {sorted(set(mine) & taken)}"


#: **`BR-AST-042`'s ratified asset types, PINNED BY NAME.**
#:
#: ⚠ **THIS TEST READ `assert len(ratified) == 12` UNTIL 2026-09-07, AND THE
#: COUNT WAS THE WEAK PART OF IT.** A bare number cannot tell a deliberate,
#: ruled addition from a type invented by a lane on its way past — which is the
#: thing this guard exists to refuse — and it cannot see a RENAME at all, since
#: swapping one code for another leaves the count untouched. The set is named
#: instead, so both failures are caught and the message says which code appeared
#: or vanished.
RATIFIED_ASSET_TYPE_CODES = frozenset(
    {
        "meter",
        "net_meter",
        "sub_meter",
        "backflow",
        "comms",
        "pv",
        "battery",
        "ev_charger",
        "transformer",
        "generator",
        "container_cart",
        "modem_cpe",
        # ── THE THIRTEENTH, ADDED 2026-09-07 UNDER `OQ-1361` ────────────────
        # Fire is the eleventh utility service and is priced by a COUNT of what
        # stands on the unit (`BR-RAT-090`). Until this row existed a tenant
        # selling fire received service points that nothing could ever stand on,
        # so every fire line billed `BR-MET-108`'s ruled `$0.00` on a bill that
        # looked entirely normal — `DEF-AST-4493`. `OQ-1361` records the choice
        # as this lane's to take, because it changes a PLATFORM CATALOGUE.
        "fire_line",
    }
)


def test_pure_the_planted_types_are_ratified_and_none_is_invented():
    """**Every planted type is one `BR-AST-042` ratifies, and the ratified set is
    exactly the one named above.**

    Solar is a `pv`, storage is a `battery`, a broadband line is a `modem_cpe`
    and a fire connection is a `fire_line` — all four in the platform list.
    **This is also the case that records why storm water is absent:** its ERU has
    no device to sit on, and inventing one would reverse `OQ-348`'s closure
    (`DEF-2388`). The PO re-ruled that same point on 2026-09-07 — the ERU belongs
    on the UNIT — so the absence asserted below is now ruled twice, and a later
    lane meeting it should read it as settled rather than missing.
    """
    from apps.assets.services import SEED_ASSET_TYPES

    ratified = {code for code, _name, _tab in SEED_ASSET_TYPES}
    assert ratified == RATIFIED_ASSET_TYPE_CODES, (
        "the seeded asset-type catalogue no longer matches the ratified set — "
        f"added: {sorted(ratified - RATIFIED_ASSET_TYPE_CODES)}; "
        f"removed: {sorted(RATIFIED_ASSET_TYPE_CODES - ratified)}. A new type is a "
        "PLATFORM CATALOGUE change (BR-AST-042): it needs a ruling and a decision-log "
        "row, not an edit to the list above."
    )
    for entry in fixture.capacity_equipment_plan():
        assert entry["type"] in ratified, f"{entry['asset_no']} invents a type"
    assert not any(entry["service"] == "storm_water" for entry in fixture.capacity_equipment_plan())


# ══════════════════════════════════════════════════════════════════════════
# PART 2 · THE LIVE RUN — one provisioning, on real PostgreSQL
# ══════════════════════════════════════════════════════════════════════════


def _plant(services: list[str]):
    """A tenant through the REAL signup service, then seeded.

    The actor is the provisioning OWNER and never an invented uuid —
    `DEF-2722`'s trap: `tenancy.sample_data._attributed` strips one, and
    `BR-BIL-058`'s release gate then refuses to issue anything, so every money
    assertion in the file fails for a reason unrelated to this change.
    """
    payload = dict(brazosbend_payload())
    payload["subdomain"] = f"cr062d-{uuid.uuid4().hex[:10]}"
    payload["name"] = "CR-062 D3-D7"
    payload["services"] = services
    owner = dict(payload["owner"])
    owner["email"] = f"owner@{payload['subdomain']}.test"
    payload["owner"] = owner
    tenant, result = provisioned_tenant(payload)
    owner_id = result["owner_user_id"]
    actor = SimpleNamespace(
        id=uuid.UUID(str(owner_id)),
        pk=uuid.UUID(str(owner_id)),
        role="system_admin",
        roles=("system_admin",),
        is_authenticated=True,
    )
    with tenant_ctx(tenant):
        summary = tenancy_sample_data.seed_sample_data(actor)
    return tenant, actor, summary


@pytest.fixture(scope="module")
def capacity_tenant(django_db_setup, django_db_blocker):
    """ONE water + sewer + solar + battery + broadband utility for the file.

    Module-scoped because a plant is minutes rather than seconds, and because
    every case below should be reading the SAME end state — two provisionings
    that disagreed would be the harder bug to find.
    """
    with django_db_blocker.unblock():
        yield _plant(list(SHAPE))


@pytest.fixture(scope="module")
def fire_tenant(django_db_setup, django_db_blocker):
    """A water + sewer + FIRE utility — the estate's six fire lines' home."""
    with django_db_blocker.unblock():
        yield _plant(list(FIRE_SHAPE))


def _estate_rows(tenant):
    with tenant_ctx(tenant):
        return {
            row.asset_no: row
            for row in asset_models.Asset.objects.filter(
                tenant_id=tenant.id, asset_no__in=list(fixture.capacity_equipment_numbers())
            )
        }


def _service_total(tenant, unit_index: int, service: str, kind: str | None = None) -> Decimal:
    """What this unit's FIRST bill charges for one service, in dollars.

    `kind` narrows it to one line kind — `"usage"` or `"base"` — because since
    2026-09-07 (`7a7638d70`) a capacity service carries a BASE line beside its
    usage line, and the two come from different rulings (`DEF-RAT-9092`).
    """
    unit_no = {u["unit_index"]: u["unit_no"] for u in fixture.units_flat()}[unit_index]
    unit = metering_models.Unit.objects.get(tenant_id=tenant.id, unit_no=unit_no)
    account = customer_models.Account.objects.get(tenant_id=tenant.id, unit_id=unit.id)
    invoice = (
        billing_models.Invoice.objects.filter(tenant_id=tenant.id, account_id=account.id)
        .order_by("period_start")
        .first()
    )
    assert invoice is not None, f"unit {unit_index} produced no bill at all"
    return sum(
        (
            line.amount
            for line in billing_models.InvoiceLine.objects.filter(
                tenant_id=tenant.id, invoice_id=invoice.id
            ).select_related("service")
            if line.service_id is not None
            and line.service.code == service
            and (kind is None or line.kind == kind)
        ),
        Decimal("0"),
    )


def _base(service: str) -> Decimal:
    """The seeded monthly base for `service` — read from the module that OWNS
    the figure, never restated here, so a PO correcting one row moves this file
    with it (`DEF-RAT-9092`)."""
    return Decimal(service_base_amounts.base_for(service, "0"))


def _quantity(tenant, unit_index: int, service: str):
    unit_no = {u["unit_index"]: u["unit_no"] for u in fixture.units_flat()}[unit_index]
    unit = metering_models.Unit.objects.get(tenant_id=tenant.id, unit_no=unit_no)
    account = customer_models.Account.objects.get(tenant_id=tenant.id, unit_id=unit.id)
    invoice = (
        billing_models.Invoice.objects.filter(tenant_id=tenant.id, account_id=account.id)
        .order_by("period_start")
        .first()
    )
    # ⚠ ORDERED BY `id` AND NOT BY `seq`: `billing.InvoiceLine` HAS NO `seq`
    # COLUMN. Written as `order_by("seq")` first, which raised
    # `FieldError: Cannot resolve keyword 'seq' into field` on five live cases —
    # after the money assertions above them had already passed, so the run
    # reported five reds over a helper while the change itself was green.
    for line in (
        billing_models.InvoiceLine.objects.filter(tenant_id=tenant.id, invoice_id=invoice.id)
        .select_related("service")
        .order_by("id")
    ):
        if (
            line.service_id is not None
            and line.service.code == service
            and line.quantity is not None
        ):
            return line.quantity, line.unit
    return None, None


@_live
@requires_postgres
def test_live_the_equipment_is_actually_on_the_estate(capacity_tenant):
    """**Hard-won law 2 — built is not wired.** Before the bills, the rows: nine
    assets, each on its unit, each carrying the size class the fixture declares.

    A case that only read the bill would pass on a tenant with no equipment and
    a coincidental price, and would fail without saying which half was missing.
    """
    tenant, _actor, _summary = capacity_tenant
    rows = _estate_rows(tenant)
    # ⚠ `DEF-AST-9083` — the plan holds every service's equipment and this
    # tenant sells five of them. A row for a service it does not sell is
    # skipped BY NAME by the seeder (`BR-MET-003`), so it is asserted ABSENT
    # here and PRESENT on `fire_tenant` below — never silently dropped.
    planned = {
        entry["asset_no"]: entry
        for entry in fixture.capacity_equipment_plan()
        if entry["service"] in SHAPE
    }
    unsold = {e["asset_no"] for e in fixture.capacity_equipment_plan()} - set(planned)
    assert unsold and not (unsold & set(rows)), sorted(unsold & set(rows))
    assert set(rows) == set(planned), (
        f"missing from the estate: {sorted(set(planned) - set(rows))}"
    )
    for asset_no, entry in planned.items():
        assert rows[asset_no].size_class == entry["size_class"], (
            f"{asset_no} was seeded with size_class {rows[asset_no].size_class!r}; a "
            "capacity that cannot be stated REFUSES the whole account's bill"
        )
        # BR-TEN-057 — a seeded row the remover must be able to take away again.
        assert rows[asset_no].is_sample is True


@_live
@requires_postgres
def test_live_d3_the_pos_own_array_bills_one_hundred_and_ninety_six(capacity_tenant):
    """**D3 · three panels of 2 kW, 4 kW and 8 kW bill `$196.00` on a SEEDED
    tenant** — the Product Owner's own example, end to end, off seeded rows and
    a seeded price rather than a test's own fixture.

    ⚠ **AND ONE LINE, NOT THREE.** Solar SUMS, so mixed sizes on one connection
    are the normal case and `metering.connection_size_for`'s refusal is never
    armed (decision log 2026-09-02 — *"one connection, one size" is a rule about
    METERED connections*). A counting service is the opposite shape and bills one
    line per size; if this ever produces three solar lines, the model has been
    misread.
    """
    tenant, _actor, _summary = capacity_tenant
    with tenant_ctx(tenant):
        billed = _service_total(tenant, fixture.SOLAR_UNIT_WITH_THREE_PANELS, "solar")
        quantity, unit = _quantity(tenant, fixture.SOLAR_UNIT_WITH_THREE_PANELS, "solar")
    assert billed == Decimal("196.00"), (
        f"unit {fixture.SOLAR_UNIT_WITH_THREE_PANELS}'s solar line is {billed}, not "
        "$196.00 — 14 kW at the seeded $14.0000 per kW. $42.00 would mean the "
        "panels were COUNTED; $0.00 means nothing is installed to multiply by"
    )
    # CLAUDE.md hard rule 3 — the quantity says what 14 of.
    assert (quantity, unit) == (Decimal("14.000000"), "kW")


@_live
@requires_postgres
def test_live_d3_one_five_kilowatt_panel_bills_seventy(capacity_tenant):
    """**D3 · the *one* of several/one/none.** A single `SOL-P5` is 5 kW, and at
    `$14.0000` that is `$70.00` — a different number from the array next door,
    which is what makes the demo show a SUM rather than a flat charge.
    """
    tenant, _actor, _summary = capacity_tenant
    with tenant_ctx(tenant):
        billed = _service_total(tenant, fixture.SOLAR_UNIT_WITH_ONE_PANEL, "solar")
        quantity, unit = _quantity(tenant, fixture.SOLAR_UNIT_WITH_ONE_PANEL, "solar")
    assert billed == Decimal("70.00")
    assert (quantity, unit) == (Decimal("5.000000"), "kW")


@_live
@requires_postgres
def test_live_d4_two_batteries_bill_thirty_and_sixty(capacity_tenant):
    """**D4 · 10 kW and 20 kW at the seeded `$3.0000` per kW.**

    The 10 kW one stands beside the solar array on unit 4, which is what
    `CR028_DEVICE_PLAN` has said in its own comment since `BAT-0001` was seeded —
    *"the solar household stores what it makes"*. `BAT-0001` itself declares no
    service and is not in this total, which is the demo showing both kinds of
    thing: a device the utility records and does not bill, and one it bills.

    ⚠ **AND A `$5.00` BASE LINE BESIDE IT SINCE 2026-09-07 (`DEF-RAT-9092`).**
    `7a7638d70` gave battery a researched monthly base (`BASE-BAT`, Evergy and
    Green Mountain Power, `service_base_amounts`), whose own comment works this
    exact unit: *"A 10 kW battery totals $35.00 a month"*. The per-kW USAGE line
    is still `$30.00` and `$60.00`, asserted on its own; the base is asserted
    from the module that owns it; and the total is the two together.
    """
    tenant, _actor, _summary = capacity_tenant
    with tenant_ctx(tenant):
        ten = _service_total(tenant, fixture.BATTERY_UNIT_WITH_TEN_KW, "battery", "usage")
        twenty = _service_total(tenant, fixture.BATTERY_UNIT_WITH_TWENTY_KW, "battery", "usage")
        ten_base = _service_total(tenant, fixture.BATTERY_UNIT_WITH_TEN_KW, "battery", "base")
        ten_all = _service_total(tenant, fixture.BATTERY_UNIT_WITH_TEN_KW, "battery")
        quantity, unit = _quantity(tenant, fixture.BATTERY_UNIT_WITH_TEN_KW, "battery")
    assert ten == Decimal("30.00"), f"10 kW × $3.0000 is $30.00; the bill says {ten}"
    assert twenty == Decimal("60.00"), f"20 kW × $3.0000 is $60.00; the bill says {twenty}"
    assert _base("battery") == Decimal("5.0000")
    assert ten_base == _base("battery"), f"battery base line is {ten_base}"
    assert ten_all == Decimal("35.00"), f"$30.00 + $5.00 base is $35.00; the bill says {ten_all}"
    assert (quantity, unit) == (Decimal("10.000000"), "kW")


@_live
@requires_postgres
def test_live_d5_three_broadband_tiers_bill_ten_fifty_and_one_hundred(capacity_tenant):
    """**D5 · 100, 500 and 1,000 Mbps at the seeded `$0.1000` per Mbps.**

    `$10.00`, `$50.00` and `$100.00`. The tier is the CPE's size class, which is
    what turns a speed written in a display name into a number the engine can
    multiply.

    ⚠ **AND A `$30.00` BASE LINE ON EACH SINCE 2026-09-07 (`DEF-RAT-9092`).**
    `7a7638d70` gave broadband a researched base (`BASE-BB`, Longmont's
    NextLight), whose own comment works the totals: *"$30.00 + $10.00 = $40.00
    for a 100 Mbps connection"* and *"$30.00 + $100.00 = $130.00"* at a gig.
    The per-Mbps USAGE figures above are unchanged and asserted on their own.
    """
    tenant, _actor, _summary = capacity_tenant
    expected = {8: Decimal("10.00"), 10: Decimal("50.00"), 20: Decimal("100.00")}
    with_base = {8: Decimal("40.00"), 10: Decimal("80.00"), 20: Decimal("130.00")}
    got: dict[int, Decimal] = {}
    bases: dict[int, Decimal] = {}
    totals: dict[int, Decimal] = {}
    with tenant_ctx(tenant):
        for unit_index, _size in fixture.BROADBAND_UNITS_BY_TIER:
            got[unit_index] = _service_total(tenant, unit_index, "broadband", "usage")
            bases[unit_index] = _service_total(tenant, unit_index, "broadband", "base")
            totals[unit_index] = _service_total(tenant, unit_index, "broadband")
        quantity, unit = _quantity(tenant, 20, "broadband")
    assert got == expected, f"broadband bills {got}, expected {expected}"
    assert _base("broadband") == Decimal("30.0000")
    assert set(bases.values()) == {_base("broadband")}, f"broadband base lines {bases}"
    assert totals == with_base, f"broadband totals {totals}, expected {with_base}"
    assert (quantity, unit) == (Decimal("1000.000000"), "Mbps")


@_live
@requires_postgres
def test_live_fire_the_seeded_lines_bill_from_their_sizes(fire_tenant):
    """**`DEF-AST-9083` · the demo's fire units carry their sized fire lines, and
    the bill counts them.** `fixture.fire_line_plan()` — the `$84.00` unit's 6"
    and two 2" lines, a residential 4", a government 6", an industrial 8".

    Unit 24: **`1 × $60.00 + 2 × $12.00 = $84.00`** on ONE fire line of 3
    connections (PO 2026-09-30 *"per service"*); unit 26: **`$30.00`** for its
    one 4" line; unit 28 (`FIRE_UNIT_WITH_NONE`) has a fire point and no line and
    bills the ruled **`$0.00`** — at the seeded default prices
    (`service_size_classes.FIRE_DEFAULT_PRICES`; `OQ-1360` stays open).

    RED before the fix: this file's only tenant did not sell fire, so the
    seeder skipped all six lines by name and unit 24 had no fire line at all.
    """
    tenant, _actor, _summary = fire_tenant
    rows = _estate_rows(tenant)
    fire_plan = {e["asset_no"]: e for e in fixture.fire_line_plan()}
    assert set(fire_plan) <= set(rows), sorted(set(fire_plan) - set(rows))
    for asset_no, entry in fire_plan.items():
        assert rows[asset_no].size_class == entry["size_class"], asset_no
        assert rows[asset_no].type.code == "fire_line", asset_no
    with tenant_ctx(tenant):
        unit_no = {u["unit_index"]: u["unit_no"] for u in fixture.units_flat()}[
            fixture.FIRE_UNIT_WITH_SIX_AND_TWO_TWOS
        ]
        unit = metering_models.Unit.objects.get(tenant_id=tenant.id, unit_no=unit_no)
        sizes_on_unit = sorted(
            asset_models.Asset.objects.filter(
                tenant_id=tenant.id,
                service_point__unit=unit,
                service_point__service__code="fire",
                type__code="fire_line",
            ).values_list("size_class", flat=True)
        )
        mixed = _service_total(tenant, fixture.FIRE_UNIT_WITH_SIX_AND_TWO_TWOS, "fire")
        quantity, unit_word = _quantity(tenant, fixture.FIRE_UNIT_WITH_SIX_AND_TWO_TWOS, "fire")
        residential = _service_total(tenant, fixture.FIRE_UNIT_RESIDENTIAL, "fire")
        none = _service_total(tenant, fixture.FIRE_UNIT_WITH_NONE, "fire")
    assert sizes_on_unit == ["FL-2", "FL-2", "FL-6"], sizes_on_unit
    assert mixed == Decimal("84.00"), f"the 6\" + two 2\" unit bills {mixed} for fire"
    assert (quantity, unit_word) == (Decimal("3.000000"), "connection")
    assert residential == Decimal("30.00")
    assert none == Decimal("0.00")


@_live
@requires_postgres
def test_live_d7_the_none_unit_bills_the_ruled_zero_beside_real_numbers(capacity_tenant):
    """**D7 · `BR-MET-108`'s ruled zero, and the reason the shape matters.**

    A unit with no equipment sums to `0` and BILLS — `$0.00` on the document
    rather than a refusal or a silence. **A zero is only a real answer when it
    sits beside a real number**, which is the whole argument for the
    several/one/none shape, so this case asserts BOTH halves on the same tenant:
    the named empty unit is `$0.00` AND some other unit of the same service is
    not.

    ⚠ **THE `$0.00` LINE IS NOT STAMPED, AND THAT IS `DEF-3084` AND NOT THIS
    CHANGE.** `BR-MET-108` as amended asks for the absence to be surfaced so a
    utility can list every unit billed at zero for want of a number; it is not,
    and it never was — true of trash since before any of this. Filed, not fixed
    here, and not silently asserted away either.
    """
    tenant, _actor, _summary = capacity_tenant
    with tenant_ctx(tenant):
        for service, none_unit in fixture.CAPACITY_UNITS_WITH_NONE.items():
            if service == "trash":
                continue  # not one of this tenant's services
            zero = _service_total(tenant, none_unit, service)
            assert zero == Decimal("0.00"), (
                f"{service} on unit {none_unit} bills {zero}; this unit is stated "
                "as carrying no equipment, so its line is BR-MET-108's ruled zero"
            )
        alive = _service_total(tenant, fixture.SOLAR_UNIT_WITH_THREE_PANELS, "solar")
    assert alive > 0, (
        "solar bills $0.00 on EVERY unit, so the zero above proves nothing — a "
        "zero is only a real answer when it sits beside a real number"
    )


@_live
@requires_postgres
def test_live_gt17_is_unmoved_by_planting_the_equipment(capacity_tenant):
    """**❄️ THE FROZEN-FIGURE GUARD. If this fails, the change STOPS.**

    `GT-17`'s reference bill is water **`$39.50`** and sewer **`$15.80`**, and
    they are PER-LINE figures — so a bill that gains a solar line gains a line
    and moves neither. Unit 0 carries no capacity equipment by construction
    (`test_pure_no_capacity_equipment_stands_on_an_awkward_unit`), which is what
    makes this a guard rather than a coincidence. A frozen figure moves only by a
    finance re-sign (HUMAN-GUIDE §6), never by a lane.

    ⚠ **AND ONE WAS: SEWER IS ❄️ `$36.00` SINCE THE 2026-09-08 RE-SIGN
    (`CR-081`, `DEF-RAT-9092`).** `05-golden-tests.md`'s re-sign table:
    *"`GT-17` / `WE-1` (the reference bill) | 8 kgal | 7.2 kgal | $15.80 |
    **$36.00**"* — 90% of the water VOLUME at `$5.00` (`ace95d812`), where it was
    40% of the water charge. This guard asserted `$15.80` for 25 days after,
    red and unread. The SEWER BASE `$9.00` (`BASE-S`) is a separate line and a
    separate ruling — PO 2026-10-01, *"Is $9.00 a month right for the demo
    sewer base? Yes"* — so the frozen figure is asserted on the USAGE line
    alone, and the base beside it.
    """
    tenant, _actor, _summary = capacity_tenant
    with tenant_ctx(tenant):
        water = _service_total(tenant, fixture.CASE_REFERENCE_BILL, "water")
        sewer = _service_total(tenant, fixture.CASE_REFERENCE_BILL, "sewer", "usage")
        sewer_base = _service_total(tenant, fixture.CASE_REFERENCE_BILL, "sewer", "base")
        solar_on_the_reference_unit = _service_total(
            tenant, fixture.CASE_REFERENCE_BILL, "solar"
        )
    assert water == Decimal("39.50") + Decimal(str(fixture.WATER_BASE)), (
        f"GT-17 ❄️: the reference unit's water charge is {water}. The usage half is "
        "$39.50 (5 kgal × $4.00 + 3 kgal × $6.50) and the seeded base is $8.00"
    )
    assert sewer == Decimal("36.00"), (
        "GT-17 ❄️ RE-SIGNED 2026-09-08 (CR-081): sewer is 90% of the WATER VOLUME, "
        f"7.2 kgal × $5.00 = $36.00; the usage line says {sewer}"
    )
    assert _base("sewer") == Decimal("9.0000")
    assert sewer_base == _base("sewer"), f"sewer base line is {sewer_base}"
    assert solar_on_the_reference_unit == Decimal("0.00"), (
        "the GT-17 reference unit gained solar equipment; it is in AWKWARD_UNITS "
        "and must carry none"
    )


@_live
@requires_postgres
def test_live_gt15s_per_panel_utility_is_untouched_by_the_seeded_per_kw_price(
    capacity_tenant,
):
    """**❄️ `GT-15` — solar `$40.00` and battery `$24.00` — quoted PER PANEL, and
    this change cannot reach them.**

    `GT-15`'s utility prices solar per `panel`; this estate's prices solar per
    `kW`. `measure_consumption.bills_installed_capacity` asks whether the
    tariff's unit IS the unit the service sums in, so the two utilities take
    different arms of the same function and neither can move the other. Asserted
    on the SEED rather than on `GT-15`'s own fixture (which
    `test_cr062_d1_installed_capacity_sums::test_tc7` already covers), because
    what this change could have broken is the seed quoting the wrong unit.
    """
    tenant, _actor, _summary = capacity_tenant
    with tenant_ctx(tenant):
        _quantity_value, unit = _quantity(
            tenant, fixture.SOLAR_UNIT_WITH_THREE_PANELS, "solar"
        )
    assert unit == "kW", (
        f"the seeded solar line is quoted per {unit!r}. GT-15 ❄️ prices solar per "
        "'panel' at $40.00; a seed that also said 'panel' while charging $14.0000 "
        "would be DEF-497 on a live money path"
    )
    assert sizes.capacity_uom_for_service("solar") == "kW"
    assert sizes.capacity_uom_for_service("battery") == "kW"


@_live
@requires_postgres
def test_live_storm_water_still_bills_nothing_and_the_reason_is_recorded(
    capacity_tenant,
):
    """**D6 IS NOT DONE, AND THIS CASE SAYS SO OUT LOUD RATHER THAN LEAVING A
    GAP.**

    Storm water's `$4.5000` per ERU is seeded and its five property sizes are
    ratified, and a seeded tenant bills `$0.00` for it — because an ERU has to
    arrive on a DEVICE (the capacity total is read off `Asset.size_class`) and
    `BR-AST-042`'s twelve asset types contain no storm-water connection.
    `OQ-348` closed by choosing a typed characteristic on the unit and rejecting
    tenant-extended asset types for exactly this. Filed as `DEF-2388`.

    **This asserts today's incomplete answer on purpose**, the same mechanism the
    rates lane used against this lane: when storm water is planted this goes RED
    and names itself as the thing to update, which is the signal that `D6`
    landed and not a regression.
    """
    assert "storm_water" not in {
        entry["service"] for entry in fixture.capacity_equipment_plan()
    }, (
        "storm water equipment is now planted — that is DEF-2388 closing. UPDATE "
        "this case and the D6 sentence in CR-062 beside it; do not delete it"
    )
    tenant, _actor, _summary = capacity_tenant
    with tenant_ctx(tenant):
        assert not metering_models.ServicePoint.objects.filter(
            tenant_id=tenant.id, service__code="storm_water"
        ).exists(), "this tenant does not sell storm water; it should have no such point"
