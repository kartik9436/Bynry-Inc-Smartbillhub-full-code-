# ── Trace ──────────────────────────────────────────────
# Change:   **CR-062 task D6** (2026-09-02) — storm water's capacity is a fact
#           recorded on the UNIT, so the one capacity service with no device to
#           carry its size stops billing $0.00. Closes `DEF-2388`.
# Rules:    PO ruling 2026-09-02 (`12-governance/02-decision-log.md`) ·
#           BR-RAT-090 as amended (a capacity quantity is a COUNT for a BANDED
#           service, a SUM of installed equipment for four capacity services,
#           and a fact ON THE UNIT for storm water) · BR-MET-108 (the shape of
#           a unit-and-service characteristic, and the ruled zero) ·
#           BR-TEN-171 (the five ratified storm-water property sizes and what
#           each is worth) · BR-MET-003 (never a characteristic for a service
#           the tenant does not sell) · CLAUDE.md hard rule 3 (an explicit unit)
#           · CLAUDE.md hard rule 2 (money and its factors at four decimals)
# Tests:    this file
# Impacts:  core/sample_fixture.storm_water_assessment_plan ·
#           apps/metering/sample_data._seed_cr062_storm_water_assessments ·
#           apps/metering/connections.UNIT_CAPACITY_CHARACTERISTIC ·
#           apps/metering/selectors._stamp_unit_recorded_capacity (🔒)
# ───────────────────────────────────────────────────────
"""**STORM WATER BILLS MONEY. IT BILLED `$0.00` ON EVERY TENANT UNTIL TODAY.**

PO verbatim, 2026-09-02:

    "In case of strom water - we have to take it from Unit - B ⭐ Take the size
     from the property, not from equipment. Storm water becomes the one
     capacity service whose quantity comes from the premises"

They chose **option B** of three **and corrected it in the same sentence**: the
option as written said *from the property*; the ruling says **from the UNIT**.
That correction is the substance and this file is written around it — a bill is
for an account, an account serves a unit, and the apartment block is where the
premises reading goes wrong first (6 units, one figure, no ruled way to split
it).

WHY IT COULD NOT BE BUILT BEFORE
--------------------------------
A capacity quantity is the SUM of `Asset.size_class` reached through the asset's
service point, so a capacity service needs **a device to carry its size**. Solar
has panels, battery has batteries, broadband has modems, trash has carts.
**Storm water has nothing** — an ERU measures hard surface on a property and
nobody installs one. The sum was `0` on every unit and the line printed
`$0.00`.

⚠ **AND NOTHING IN THIS REPO COULD SEE IT.** The line exists, foots and prints,
so the invoice count, the service-coverage scoreboard and every golden check
passed straight over it. That is `DEF-2388`'s escape reason and it is the reason
the cases below assert **money on a named unit**, never "a line exists".

RED FIRST (r11 step 2d · hard-won law 7)
----------------------------------------
Run against an **untouched checkout of the branch tip** (`c0e54d9e`), extracted
into its own tree, on real PostgreSQL 16.13, before a line of this change was
written. Unit indexes were LITERALS in that run, because the constants this
change adds do not exist at the tip. **5 failed, 1 passed**, verbatim::

    AssertionError: unit 3 (a single-family house, 1 ERU) bills 0.000000 for
    storm water, not $4.50 -- 1 ERU at the seeded $4.5000 per ERU
    assert Decimal('0.000000') == Decimal('4.50')

    AssertionError: the block's six flats bill {40: Decimal('0.000000'), 41:
    Decimal('0.000000'), 42: Decimal('0.000000'), 43: Decimal('0.000000'), 44:
    Decimal('0.000000'), 45: Decimal('0.000000')}; 6 ERU spread equally is
    $4.50 each and $27.00 across the block

    AssertionError: the commercial suite bills 0.000000; 4 ERU at $4.5000 is
    $18.00

    AssertionError: the demo estate bills 0.000000 for storm water; 54 ERU at
    $4.5000 is $243.00

**THE ONE THAT PASSED AT THE TIP IS THE ONE THAT MATTERS MOST**: the four OTHER
capacity services already billed `$196.00` solar, `$30.00` battery, `$50.00`
broadband and `$45.00` trash on that same seven-service tenant, and they still
do. A change that made them read a unit field would have implemented the ruling
and broken four working services, three of which started billing real money the
same day.

⚠ **A SIXTH FAILURE IN THAT RUN WAS THE PROBE'S OWN BUG AND IS RECORDED SO
NOBODY READS IT AS A FROZEN FIGURE MOVING.** The probe asserted ❄️ `GT-17` by
summing EVERY water line on the reference bill and got `47.500000`. `GT-17` is a
**per-LINE `usage`** figure — `$39.50` — and the other `$8.00` is the water BASE
charge, which was there before this change and is there after it.
`test_live_gt17_is_unmoved` below asserts it the way the frozen case states it.

⚠ **$243.00 IS THE ASSESSMENT AND $247.50 IS WHAT THE UTILITY COLLECTS — FOUND
BY MEASURING, NOT BY DERIVING.** The first green run read `247.500000` where the
ruling says `$243.00`, and the cause is a signed rule this change never touches:
`BR-RAT-101`/`BR-RAT-102` multiply every base and variable line on a premises
OUTSIDE the city limits by **1.5** (r10's Residential Standard, verbatim:
*"Premises outside city limits multiply base and variable by 1.5 — set on the
premise record."*). The seeded estate has **two** such houses, so their
storm-water lines read **`$6.75`** and the month is `$243.00 + 2 × $2.25`.
**The ruling's figure is the QUANTITY — 54 ERU — and a surcharge multiplies the
price, never the measurement**, so both are asserted, separately, rather than one
being adjusted to fit the other.

⚠ **AND THE ESTATE TOTAL IS COUNTED PER UNIT, BECAUSE SUMMING EVERY LINE IN THE
PERIOD GIVES `55` ERU.** Also measured, and it took three runs to stop guessing
at it: `CASE_OVERCHARGE` (unit 31) is the fixture's *wrong June read, corrected
by restatement*, so that account holds **two invoices for the same period** and
its storm-water line is on both. The restatement supersedes the original; it does
not bill a second ERU. **The 55 is asserted rather than filtered away**, because
the month-wide query is the one the next lane will reach for.

⚠ **EVERY ESTATE-WIDE FIGURE IN THE PARAGRAPHS ABOVE WAS MEASURED ON A
FORTY-EIGHT-UNIT ESTATE AND THE ESTATE IS NOW FIFTY (`DEF-2368`, 2026-09-02).**
They are left standing because they are a RECORD of a run that happened, and
correcting a past measurement falsifies it. What they say now: `CR-062`'s
addendum appended `601 Quarry Hill Ct` (the municipal depot, `SW-SF`, 1 ERU,
unit 48) and `603 Silver Creek Rd` (the industrial plant, `SW-COM-S`, 4 ERU,
unit 49), so the estate assesses **59 ERU across 43 premises — `$265.50`, and
`$270.00` collected**. Three cases in this file were red on it for a day, and
the reason is the reason this note exists: **they were the three that stated a
figure as a LITERAL.** The rest derived, and derived cases cannot go stale.

⚠ **AND THE THIRD OF THOSE THREE WAS DIAGNOSED WRONG WHEN IT WAS FILED, WHICH
IS WORTH MORE THAN THE FIX.** `DEF-2368`'s row records *"unit 49's `$18.00` of
storm water does not reach a bill at all"*. It does reach a bill. The measured
failure is::

    AssertionError: these units do not bill their assessment:
    {49: Decimal('18.000000')}

— the money is ON an issued invoice and the TEST expected `$4.50`, because
`expected` was built from the literal `COMMERCIAL_UNIT` and `COMMERCIAL_UNIT +
1` and the estate had since grown a THIRD commercial premises. A stale
expectation reads exactly like unbilled money when the diff is skimmed rather
than read. **So `expected` is DERIVED from the plan and the ratified ladder
below**, which is the only version of this case that cannot say it again.

WHAT THIS FILE DELIBERATELY DOES NOT CLAIM
------------------------------------------
**The `$0.00` line is not STAMPED with the reason it is zero.** `BR-MET-108` as
amended asks for the absence to be surfaced so a utility can list every unit
billed at zero for want of a number, and `connections.units_priced_at_zero` is
that half — it now has a real key to be asked with. But the invoice LINE carries
no reason, and that is `DEF-3084`: it is true of every capacity service
including trash, it was true before this change, and half-fixing it for one
service would be worse than naming it.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.db import transaction

from apps.billing import models as billing_models
from apps.billing.stages import measure_consumption
from apps.rating import service_base_amounts
from apps.customers import models as customer_models
from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.metering import models as metering_models
from apps.metering import selectors as metering_selectors
from apps.tenancy import sample_data as tenancy_sample_data
from apps.tenancy import service_size_classes as sizes
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

#: A utility selling storm water AND the four capacity services that must NOT
#: change, plus water + sewer so ❄️ `GT-17`'s reference bill is on the same
#: tenant and any movement in it is visible in the same run.
SHAPE: tuple[str, ...] = (
    "water",
    "sewer",
    "storm_water",
    "solar",
    "battery",
    "broadband",
    "trash",
)

#: A single-family house that anchors no signed figure — chosen, not stumbled
#: onto: it is outside `AWKWARD_UNITS` and carries no capacity equipment.
HOUSE_UNIT = 3
#: The apartment block's six flats, in fixture order. **6 ERU spread equally is
#: 1 ERU each, not 6 each** — the case the whole allocation decision is about.
APARTMENT_UNITS: tuple[int, ...] = (40, 41, 42, 43, 44, 45)
#: `Creekside Laundromat` — a commercial suite, one unit, assessed `SW-COM-S`.
#:
#: ⚠ **IT IS ONE OF THREE SUCH UNITS AND WAS ONE OF TWO UNTIL 2026-09-02
#: (`DEF-2368`).** `CR-062`'s addendum appended the mill building at unit 49,
#: which is a third `commercial_building` and bills the same `$18.00`. This
#: constant still names ONE unit on purpose — the case below wants a suite it
#: can point at by name — but **nothing derives the SET from it any more**: the
#: estate case builds its expectation from the plan and the ladder, because
#: `{46, 47}` written by hand is what went stale.
COMMERCIAL_UNIT = 46


def _assessment_by_unit() -> dict[int, Decimal]:
    """**WHAT EVERY SEEDED UNIT'S STORM-WATER LINE MUST READ, DERIVED — the fix
    for `DEF-2368` and the reason this file cannot go stale on an appended seat
    again.**

    Three facts, each taken from the one place that owns it and none of them
    typed here: WHICH size class each premises is (`storm_water_assessment_
    plan`), what that code is WORTH in ERU (`BR-TEN-171`'s ratified ladder, via
    `total_capacity`), and the price per ERU (`CAPACITY_UNIT_PRICES`). The
    equal split across a premises' units is the seeder's own rule.

    ⚠ **`BR-RAT-101`'s 1.5x IS APPLIED ONLY WHERE THE PLAN STATES A FACTOR, AND
    THAT IS THE RESIDENTIAL PLAN ALONE.** `_plan_payloads` puts
    `outside_city_factor` on the residential plan and deliberately not on the
    commercial one, so *"this premises is outside the city"* is not on its own
    enough — the account's plan has to price by jurisdiction as well. Reading
    only the premises flag would surcharge a commercial seat that bills flat,
    which is a wrong number arrived at through a rule that was never consulted.
    """
    price = Decimal(fixture.CAPACITY_UNIT_PRICES["storm_water"])
    factor = Decimal(fixture.OUTSIDE_CITY_FACTOR)
    outside = set(fixture.OUTSIDE_CITY_PREMISES_INDEXES)
    # `OUTSIDE_CITY_PREMISES_INDEXES` are ordinals of `premises_plan()`, NOT
    # unit indexes. They coincide for the first 36 houses and stop coinciding at
    # the first duplex, so the ordinal is resolved rather than assumed.
    ordinal_of = {
        entry["address_line"]: index
        for index, entry in enumerate(fixture.premises_plan())
    }
    out: dict[int, Decimal] = {}
    for row in fixture.storm_water_assessment_plan():
        capacity = Decimal(str(sizes.total_capacity("storm_water", [row["size_class"]])))
        share = capacity / Decimal(len(row["unit_indexes"]))
        surcharged = ordinal_of[row["address_line"]] in outside
        for index in row["unit_indexes"]:
            amount = share * price
            if surcharged and fixture.plan_class_for(index) == "residential":
                amount *= factor
            out[index] = amount
    return out


# ══════════════════════════════════════════════════════════════════════════
# PART 1 · THE PURE LAYER — no database, milliseconds, fails first
# ══════════════════════════════════════════════════════════════════════════


def test_pure_only_storm_water_takes_its_capacity_from_the_unit():
    """**THE GUARD ON THE THING A CARELESS BUILD WOULD BREAK.**

    Solar, battery, broadband and trash still read INSTALLED EQUIPMENT. If this
    case ever fails for one of them, four working services have been rewired by
    a change that was only ever about the fifth — and three of those four began
    billing real money on the day this ruling was made.
    """
    assert w6.unit_capacity_key("storm_water") == "assessment"
    for service in ("solar", "battery", "broadband", "trash", "fire"):
        assert w6.unit_capacity_key(service) is None, (
            f"{service} now reads its capacity off a unit characteristic. The PO "
            "ruled that of STORM WATER alone; every other capacity service sums "
            "or counts what is installed"
        )
    # `DEF-RAT-9058` — `CR-080` (2026-09-07, `1c157a237`) made THERMAL the
    # second unit-carried capacity: connected tonnage, recorded on the unit.
    # The five equipment-carried services above are still untouched.
    assert w6.unit_capacity_key("thermal_heat") == "connected_capacity"
    assert set(w6.UNIT_CAPACITY_CHARACTERISTIC) == {"storm_water", "thermal_heat"}


def test_pure_the_key_carries_no_unit_of_measure():
    """`BR-MET-108`'s third argument, applied to the key this change mints.

    *"The unit never goes in the key name"* — `storm_impervious_sqft` is a unit
    encoded in an identifier that nothing can validate, compare or migrate. A
    key of `eru` would be the same mistake in shorter letters.
    """
    for service, key in w6.UNIT_CAPACITY_CHARACTERISTIC.items():
        uom = sizes.capacity_uom_for_service(service)
        assert uom and uom.lower() not in key.lower(), (
            f"the {service} characteristic key {key!r} spells its unit of "
            f"measure ({uom!r}); the unit is DATA in `unit_of_measure`"
        )


def test_pure_every_seeded_unit_is_assessed_exactly_once():
    """43 premises, 50 units, one assessment each.

    ⚠ **THE THREE PREMISES WITH NO UNIT ARE THE `57`-versus-`54` DISCREPANCY IN
    `CR-062` D6's OWN TEXT.** It said *"57 ERU across 44 premises"* and its rows
    added to 54. On this ruling that dissolves rather than needing a fix: a
    premises with no unit has nowhere to record an ERU and nothing to bill, so
    *the estate minus the premises with no unit* was always the billable figure
    and the task text is amended.

    ⚠ **AND THE TWO NUMBERS IN THE FIRST LINE WERE `41` AND `48` UNTIL
    2026-09-02, WHEN `CR-062`'s ADDENDUM APPENDED TWO SEATS UNDER THEM
    (`DEF-2368`).** `STORM_WATER_ASSESSED_PREMISES` is DERIVED now, so the
    assertion against it is a tautology and is kept only to prove it is wired;
    the two that carry weight are the ones below it — `PREMISES_COUNT - 3`,
    which is an independent statement of the same fact, and the literal a person
    read.
    """
    plan = fixture.storm_water_assessment_plan()
    assert len(plan) == fixture.STORM_WATER_ASSESSED_PREMISES
    assert len(plan) == fixture.PREMISES_COUNT - 3 == 43

    indexes = fixture.storm_water_assessed_unit_indexes()
    assert len(indexes) == len(set(indexes)) == fixture.UNIT_COUNT == 50, (
        "every seeded unit stands on ground with hard surface, so every one of "
        "them carries an assessment; a unit assessed twice would double-bill it"
    )


def test_pure_the_estate_is_fifty_nine_eru_and_every_premises_divides_exactly():
    """**59 ERU, re-derived from `BR-TEN-171`'s ladder rather than restated.**

    The stated constant and the ladder are two independent statements of one
    figure, and this is what stops them drifting apart in silence.

    ⚠ **IT SAID 54 UNTIL 2026-09-02 AND THE SENTENCE ABOVE IS STILL TRUE —
    `DEF-2368` IS WHAT IT LOOKS LIKE WHEN IT WORKS.** The two statements DID
    drift apart, this case is what said so, and it took a day only because
    nobody ran it. `STORM_WATER_ESTATE_ERU` stays a literal deliberately (see
    its own comment: totalling ERU needs the ratified ladder, and
    `core/sample_fixture` may not import Django), so the drift is what gets the
    check — `10-scripts/gates/g73_storm_water_estate.py` makes the same
    comparison with no database, in one second, on every lane.

    ⚠ **AND THE SPLIT IS EXACT ON EVERY PREMISES.** An inexact split would
    quietly lose or gain ERU across a premises — a premises whose units no
    longer sum to its own assessment — so the seeder logs one when it happens
    and this case proves the seeded estate never does.
    """
    total = Decimal("0")
    for row in fixture.storm_water_assessment_plan():
        capacity = sizes.total_capacity("storm_water", [row["size_class"]])
        units = len(row["unit_indexes"])
        share = Decimal(str(capacity)) / Decimal(units)
        assert share * units == Decimal(str(capacity)), (
            f"{row['address_line']} assesses {capacity} ERU across {units} units, "
            "which does not divide evenly"
        )
        total += Decimal(str(capacity))
    assert total == fixture.STORM_WATER_ESTATE_ERU == Decimal("59")
    # The estate's monthly figure, on the seeded price. ⚠ This is the
    # ASSESSMENT, not the invoiced total: two of the 43 premises are outside the
    # city limits and `BR-RAT-101`'s 1.5 puts the collected figure at $270.00.
    # The live case asserts both, separately.
    assert total * Decimal(fixture.CAPACITY_UNIT_PRICES["storm_water"]) == Decimal("265.5000")


def test_pure_the_apartment_block_is_one_eru_a_flat_and_not_six():
    """**THE ALLOCATION DECISION, ISOLATED.** The block's 6 ERU is 1 ERU on each
    of its six flats — the posture `MASTER_METER`'s `allocation_rule: "equal"`
    already takes for a block's water.

    Six on each would bill the block **`$162.00`** a month instead of
    **`$27.00`**, on a document that foots.
    """
    block = [
        row
        for row in fixture.storm_water_assessment_plan()
        if row["size_class"] == fixture.STORM_WATER_SIZE_APARTMENT
    ]
    assert len(block) == 1, "the fixture has exactly one apartment block"
    (row,) = block
    capacity = Decimal(str(sizes.total_capacity("storm_water", [row["size_class"]])))
    assert capacity == Decimal("6")
    assert tuple(row["unit_indexes"]) == APARTMENT_UNITS
    share = capacity / Decimal(len(row["unit_indexes"]))
    assert share == Decimal("1")
    assert share * Decimal(fixture.CAPACITY_UNIT_PRICES["storm_water"]) == Decimal("4.5000")


def test_pure_every_size_code_is_one_of_the_ratified_five():
    """`BR-TEN-171` owns the vocabulary; this fixture may not teach one.

    A code the ladder does not hold is skipped by the seeder with its reason
    logged — the unit then keeps `BR-MET-108`'s ruled `$0.00`, which is the safe
    direction — but a fixture that shipped one would be seeding a demo that
    silently bills nothing.
    """
    ratified = {row.code for row in sizes.RATIFIED_SERVICE_SIZE_CLASSES["storm_water"]}
    used = {row["size_class"] for row in fixture.storm_water_assessment_plan()}
    assert used <= ratified, f"not ratified: {sorted(used - ratified)}"


# ══════════════════════════════════════════════════════════════════════════
# PART 2 · LIVE — real PostgreSQL, a provisioned tenant, real bills
# ══════════════════════════════════════════════════════════════════════════


def _plant(services: list[str]):
    payload = dict(brazosbend_payload())
    payload["subdomain"] = f"cr062d6-{uuid.uuid4().hex[:10]}"
    payload["name"] = "CR-062 D6"
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
def storm_water_tenant(django_db_setup, django_db_blocker):
    """ONE seven-service utility for the file — module-scoped because a plant is
    minutes rather than seconds, and because every case below should be reading
    the SAME end state."""
    with django_db_blocker.unblock():
        # ⚠ `DEF-RAT-9057` — ONE TRANSACTION, ROLLED BACK WHEN THE MODULE ENDS.
        # This plant used to be written for good and never removed, and on
        # PostgreSQL the next FILE in the session counted its 102 invoices and
        # its account types as its own (`us_bil_013` read 103 invoices where it
        # wrote one). Nothing can delete it afterwards — issued invoices take no
        # DELETE (hard rule 4) — so it must never outlive the module. Each case
        # below still runs in its own savepoint inside this block.
        with transaction.atomic():
            yield _plant(list(SHAPE))
            transaction.set_rollback(True)


def _unit(tenant, unit_index: int):
    unit_no = {u["unit_index"]: u["unit_no"] for u in fixture.units_flat()}[unit_index]
    return metering_models.Unit.objects.get(tenant_id=tenant.id, unit_no=unit_no)


def _lines(tenant, unit_index: int):
    unit = _unit(tenant, unit_index)
    account = customer_models.Account.objects.get(tenant_id=tenant.id, unit_id=unit.id)
    invoice = (
        billing_models.Invoice.objects.filter(tenant_id=tenant.id, account_id=account.id)
        .order_by("period_start")
        .first()
    )
    assert invoice is not None, f"unit {unit_index} produced no bill at all"
    return list(
        billing_models.InvoiceLine.objects.filter(
            tenant_id=tenant.id, invoice_id=invoice.id
        ).select_related("service")
    )


def _service_total(
    tenant, unit_index: int, service: str, kind: str | None = "usage"
) -> Decimal:
    """What this unit's FIRST bill charges for one service's CAPACITY, in dollars.

    ⚠ `DEF-RAT-9058` — **`kind="usage"` BY DEFAULT, BECAUSE THE BILL GREW A
    BASE LINE.** Since `7a7638d70` (2026-09-07, `service_base_amounts`) storm
    water carries a researched `$2.00` monthly base, battery `$5.00` and
    broadband `$30.00`, so the whole-service sum read `$6.50` for a house whose
    ERU charge is still exactly `$4.50`. The capacity figures below are about
    the CAPACITY line; the base is asserted beside them from its own source.
    `kind=None` sums every line of the service.
    """
    return sum(
        (
            line.amount
            for line in _lines(tenant, unit_index)
            if line.service_id is not None
            and line.service.code == service
            and (kind is None or line.kind == kind)
        ),
        Decimal("0"),
    )


def _quantity(tenant, unit_index: int, service: str):
    for line in _lines(tenant, unit_index):
        if (
            line.service_id is not None
            and line.service.code == service
            and line.quantity is not None
        ):
            return line.quantity, line.unit
    return None, None


@_live
@requires_postgres
def test_live_the_assessments_are_actually_on_the_units(storm_water_tenant):
    """**Hard-won law 2 — built is not wired.** Before the bills, the rows.

    A case that only read the bill would pass on a tenant with no assessments
    and a coincidental price, and would not say which half was missing.
    """
    tenant, _actor, _summary = storm_water_tenant
    with tenant_ctx(tenant):
        rows = {
            str(row.unit_id): row
            for row in work_tables.ServiceCharacteristic.objects.filter(
                tenant_id=tenant.id, service__code="storm_water", key="assessment"
            )
        }
        wanted = {
            str(_unit(tenant, index).id): index
            for index in fixture.storm_water_assessed_unit_indexes()
        }
    assert set(wanted) <= set(rows), (
        f"{len(set(wanted) - set(rows))} of the estate's 48 units carry no "
        "storm-water assessment"
    )
    for unit_id, index in wanted.items():
        row = rows[unit_id]
        # CLAUDE.md hard rule 3 — the number never travels without its unit.
        assert row.unit_of_measure == "ERU", (
            f"unit {index}'s assessment is recorded in {row.unit_of_measure!r}"
        )
        # BR-TEN-057 — a seeded row the remover must be able to take away.
        assert row.is_sample is True
        assert Decimal(row.value) > 0
    assert Decimal(rows[str(_unit(tenant, HOUSE_UNIT).id)].value) == Decimal("1.0000")
    assert Decimal(rows[str(_unit(tenant, COMMERCIAL_UNIT).id)].value) == Decimal("4.0000")
    for index in APARTMENT_UNITS:
        assert Decimal(rows[str(_unit(tenant, index).id)].value) == Decimal("1.0000"), (
            f"apartment unit {index} is assessed "
            f"{rows[str(_unit(tenant, index).id)].value} ERU; the block's 6 ERU is "
            "spread EQUALLY across its six flats, so each flat is 1"
        )


@_live
@requires_postgres
def test_live_a_house_bills_four_fifty(storm_water_tenant):
    """**1 ERU × `$4.50` = `$4.50` a month**, on a seeded tenant, from a fact
    recorded on the unit rather than from a device that does not exist.

    It billed `$0.00` the hour before, on a line that footed and printed.
    """
    tenant, _actor, _summary = storm_water_tenant
    with tenant_ctx(tenant):
        billed = _service_total(tenant, HOUSE_UNIT, "storm_water")
        quantity, unit = _quantity(tenant, HOUSE_UNIT, "storm_water")
    assert billed == Decimal("4.50"), (
        f"unit {HOUSE_UNIT} (a single-family house, 1 ERU) bills {billed} for "
        "storm water, not $4.50 at the seeded $4.5000 per ERU"
    )
    # CLAUDE.md hard rule 3 — the quantity says what 1 of.
    assert (quantity, unit) == (Decimal("1.000000"), "ERU")
    # `DEF-RAT-9058` — and the base beside it is the researched one, so the
    # whole storm-water charge is the ERU line plus that base and nothing else.
    with tenant_ctx(tenant):
        whole = _service_total(tenant, HOUSE_UNIT, "storm_water", kind=None)
    base = Decimal(service_base_amounts.base_for("storm_water", fixture.CAPACITY_BASE))
    assert base == Decimal("2.0000")
    assert whole == billed + base


@_live
@requires_postgres
def test_live_the_apartment_block_bills_twenty_seven_and_not_one_sixty_two(
    storm_water_tenant,
):
    """**THE CASE THE ALLOCATION DECISION EXISTS FOR.** Six flats, `$4.50` each,
    `$27.00` across the block — not `$27.00` on one flat and not `$162.00`
    across six.

    This is also why the ruling is *the UNIT* and not *the premises*: on the
    premises there would be one figure, six accounts and no ruled way to split
    it, and every other quantity on those bills is a unit fact.
    """
    tenant, _actor, _summary = storm_water_tenant
    with tenant_ctx(tenant):
        flats = {i: _service_total(tenant, i, "storm_water") for i in APARTMENT_UNITS}
    assert flats == {i: Decimal("4.50") for i in APARTMENT_UNITS}, (
        f"the block's six flats bill {flats}; 6 ERU spread equally is $4.50 each"
    )
    assert sum(flats.values()) == Decimal("27.00")


@_live
@requires_postgres
def test_live_a_commercial_suite_bills_eighteen(storm_water_tenant):
    """**4 ERU × `$4.50` = `$18.00`** — a different number from the house next
    door, which is what makes the demo show a CAPACITY rather than a flat charge
    dressed up as one.
    """
    tenant, _actor, _summary = storm_water_tenant
    with tenant_ctx(tenant):
        billed = _service_total(tenant, COMMERCIAL_UNIT, "storm_water")
        quantity, unit = _quantity(tenant, COMMERCIAL_UNIT, "storm_water")
    assert billed == Decimal("18.00"), (
        f"the commercial suite bills {billed}; 4 ERU at $4.5000 is $18.00"
    )
    assert (quantity, unit) == (Decimal("4.000000"), "ERU")


@_live
@requires_postgres
def test_live_the_estate_charges_fifty_nine_eru_and_bills_two_seventy(
    storm_water_tenant,
):
    """**59 ERU across the demo estate, which at `$4.50` is `$265.50`, and the
    accounts are billed `$270.00` between them.**

    ⚠ **THIS CASE READ `54` / `$243.00` / `$247.50` AND BUILT ITS PER-UNIT
    EXPECTATION FROM TWO HAND-TYPED UNIT NUMBERS UNTIL 2026-09-02 (`DEF-2368`).**
    `CR-062`'s addendum appended a third commercial premises at unit 49, so the
    case asserted `$4.50` where the bill correctly said `$18.00` — a stale
    expectation that reads, in a skimmed diff, exactly like unbilled money.
    **`expected` is DERIVED now** (`_assessment_by_unit`), from the plan and the
    ratified ladder, and so are the two totals below it; the only literals left
    are the three figures a person read, which is what a literal is for.

    ⚠ **THE `$4.50` DIFFERENCE IS A SIGNED RULE THIS CHANGE DID NOT TOUCH, AND
    IT IS ASSERTED RATHER THAN ROUNDED AWAY.** `BR-RAT-101`/`BR-RAT-102`
    surcharge every base and variable line on a premises OUTSIDE the city limits
    by **1.5** — r10's Residential Standard schedule, verbatim: *"Premises
    outside city limits multiply base and variable by 1.5 — set on the premise
    record."* The seeded estate has **two** such houses
    (`OUTSIDE_CITY_PREMISES_INDEXES`, derived from r10's own 61-of-1,247 ratio),
    so their storm-water lines read **`$6.75`** rather than `$4.50` and the
    estate's storm-water revenue is `$265.50 + 2 × $2.25` = **`$270.00`**.

    **THE RULED FIGURE IS THE QUANTITY AND IT IS EXACTLY 59 ERU.** A surcharge
    multiplies the PRICE, never the measurement, so the ERU total is untouched
    by it — which is why this case asserts the quantity total as well as the
    money, and why the two are stated separately instead of one being quietly
    adjusted to fit the other.

    ⚠ **AND THE ESTATE TOTAL IS COUNTED PER UNIT, NOT BY SUMMING EVERY LINE IN
    THE MONTH — WHICH GIVES ONE ERU MORE.** That was measured too, and the cause
    is `CASE_OVERCHARGE` (unit 31): the fixture's own correction story is *a
    wrong June read, corrected by restatement*, so that account holds **two
    invoices for the same period** and its storm-water line appears on both. The
    restatement supersedes the original; it does not bill a second ERU. Summing
    the period's lines counts it twice and is the wrong question — **so this case
    asserts the doubling explicitly** rather than filtering it away, because a
    later lane measuring "what does the estate bill" will reach for the same
    query and get the wrong answer. It was `55` against `54` when this file was
    written and it is **`60` against `59`** now; the assertion is the estate plus
    that one unit's own share, derived, so the pair moves together.
    """
    tenant, _actor, _summary = storm_water_tenant
    per_unit: dict[int, Decimal] = {}
    per_unit_eru: dict[int, Decimal] = {}
    with tenant_ctx(tenant):
        for row in fixture.units_flat():
            index = row["unit_index"]
            per_unit[index] = _service_total(tenant, index, "storm_water")
            per_unit_eru[index] = sum(
                (
                    line.quantity or Decimal("0")
                    for line in _lines(tenant, index)
                    if line.service_id is not None
                    and line.service.code == "storm_water"
                    and line.kind == "usage"
                ),
                Decimal("0"),
            )
        # The naive month-wide read, kept because it is the query the next lane
        # will reach for and because its answer is 55 rather than 54.
        first = fixture.PERIODS[0]["start"]
        month_lines = list(
            billing_models.InvoiceLine.objects.filter(
                tenant_id=tenant.id,
                invoice__period_start=first,
                service__code="storm_water",
            ).select_related("service", "invoice")
        )
        restated = billing_models.Invoice.objects.filter(
            tenant_id=tenant.id,
            period_start=first,
            account__unit_id=_unit(tenant, fixture.CASE_OVERCHARGE).id,
        ).count()

    money = sum(per_unit.values(), Decimal("0"))
    eru = sum(per_unit_eru.values(), Decimal("0"))
    month_eru = sum(
        (line.quantity or Decimal("0") for line in month_lines), Decimal("0")
    )

    # ⚠ **DERIVED, NOT TYPED — `DEF-2368`.** This was a loop over
    # `range(UNIT_COUNT)` branching on `COMMERCIAL_UNIT` and `COMMERCIAL_UNIT +
    # 1`, and when the estate grew a THIRD commercial premises the case asserted
    # $4.50 against a correct $18.00 bill. The three sources are the plan, the
    # ratified ladder and the seeded price; none of them is a number in this
    # file. Sorted so the failure message reads in unit order.
    expected = _assessment_by_unit()
    assert per_unit == expected, (
        "these units do not bill their assessment: "
        + str(
            {
                i: f"billed {v}, assessed {expected[i]}"
                for i, v in sorted(per_unit.items())
                if v != expected[i]
            }
        )
    )
    assert eru == fixture.STORM_WATER_ESTATE_ERU == Decimal("59"), (
        f"the demo estate is assessed {eru} ERU; the fixture states "
        f"{fixture.STORM_WATER_ESTATE_ERU} and a person read 59. "
        f"Per unit: {per_unit_eru}"
    )
    assert money == sum(expected.values(), Decimal("0")) == Decimal("270.00"), (
        f"the demo estate bills {money} for storm water in a month. 59 ERU at "
        "$4.5000 is $265.50, plus BR-RAT-101's outside-city 1.5x on two houses "
        f"(2 x $2.25). Per unit: {per_unit}"
    )
    # ⚠ THE TRAP, ASSERTED RATHER THAN FILTERED AWAY. `CASE_OVERCHARGE` is the
    # fixture's *wrong June read, corrected by restatement*, so that account
    # holds TWO invoices for this period and its storm-water line is on both.
    # The restatement supersedes the original; it does not bill a second ERU.
    assert restated == 2, (
        f"unit {fixture.CASE_OVERCHARGE} holds {restated} invoice(s) for the "
        "first period; the fixture's correction story seeds an original and a "
        "restatement, and this case exists to say why the month-wide sum is one "
        "ERU over the estate"
    )
    # The estate PLUS that one unit's own share — derived, so the pair moves
    # together when a seat is appended. It was 55 against 54 and is 60 against
    # 59; the literal is kept beside it as the figure a person read.
    doubled = eru + (per_unit_eru[fixture.CASE_OVERCHARGE] or Decimal("0"))
    assert month_eru == doubled == Decimal("60"), (
        f"summing every storm-water line in the period gives {month_eru} ERU. "
        f"It should be {doubled} — {eru} of assessment plus the restated line on "
        f"unit {fixture.CASE_OVERCHARGE} counted twice — and if that has changed, "
        "the correction story or the estate has moved and this case should say "
        "which"
    )


@_live
@requires_postgres
def test_live_a_unit_with_no_assessment_bills_a_ruled_zero_not_a_refusal(
    storm_water_tenant,
):
    """**`BR-MET-108`'s ruled zero (PO 2026-08-25, *"Bill it as zero"*), and the
    distinction that decides whether the customer gets a document at all.**

    A quantity of **`0 ERU`** prices `$0.00` and puts the LINE on the bill. A
    quantity of **`None`** refuses the whole account by name. Those are the two
    outcomes, they are one `if` apart, and this asserts which one an absent
    assessment produces — on a real unit of a real tenant, with the row deleted
    and put back.

    ⚠ **IT IS ASSERTED AT THE SEAM AND AT THE BILLING STAGE RATHER THAN BY
    RE-BILLING, AND THAT IS STATED RATHER THAN GLOSSED.** `_summed_quantity`
    returning `Quantity(0, "ERU")` instead of `None` IS the fact that decides a
    `$0.00` line against a refusal; that a zero capacity then produces a line on
    the document is the identical code path
    `test_cr062_d3_d7_capacity_equipment.test_live_d7_the_none_unit_bills_the_
    ruled_zero_beside_real_numbers` already proves live for solar, battery and
    broadband. **And the zero sits beside real numbers on the same tenant** —
    every other case in this file is a non-zero storm-water bill.

    ⚠ **THE LINE IS NOT STAMPED WITH ITS REASON — `DEF-3084`, and NOT this
    change.** `connections.units_priced_at_zero("storm_water", "assessment", …)`
    is the ruling's surfacing half and now has a real key to be asked with; the
    invoice LINE carries no reason, which has been true of every capacity
    service including trash since before any of this.
    """
    tenant, _actor, _summary = storm_water_tenant
    with tenant_ctx(tenant):
        unit = _unit(tenant, HOUSE_UNIT)
        row = work_tables.ServiceCharacteristic.objects.get(
            tenant_id=tenant.id, unit_id=unit.id, service__code="storm_water", key="assessment"
        )
        keep = (row.value, row.unit_of_measure)
        period = fixture.PERIODS[0]
        try:
            row.delete()
            reads = metering_selectors.billing_reads_for_unit(
                unit.id,
                period_start=period["start"],
                period_end=period["end"],
                service_codes=["storm_water"],
            )
            (absent_read,) = [r for r in reads if r["service_code"] == "storm_water"]
            # The unit is now one a utility would find on the priced-at-zero
            # list — the ruling's surfacing half, asked with a real key.
            listed = w6.units_priced_at_zero("storm_water", "assessment", [str(unit.id)])
            with_row = w6.units_priced_at_zero(
                "storm_water", "assessment", [str(_unit(tenant, COMMERCIAL_UNIT).id)]
            )
        finally:
            work_tables.ServiceCharacteristic.objects.update_or_create(
                tenant_id=tenant.id,
                unit_id=unit.id,
                service=row.service,
                key="assessment",
                defaults={"value": keep[0], "unit_of_measure": keep[1], "is_sample": True},
            )
        restored = metering_selectors.billing_reads_for_unit(
            unit.id,
            period_start=period["start"],
            period_end=period["end"],
            service_codes=["storm_water"],
        )
        (restored_read,) = [r for r in restored if r["service_code"] == "storm_water"]

    assert absent_read["installed_capacity"] == Decimal("0"), (
        "an unrecorded assessment must be BR-MET-108's ruled ZERO, not None — "
        f"got {absent_read['installed_capacity']!r}, which refuses the whole "
        "account's bill instead of printing $0.00"
    )
    # Hard rule 3 survives the absence: a zero is still a zero OF something.
    assert absent_read["capacity_uom"] == "ERU"

    tariff = SimpleNamespace(model="flat", billed_unit="ERU", service="storm_water")
    assert measure_consumption.bills_installed_capacity(
        SimpleNamespace(**absent_read), tariff
    )
    zero = measure_consumption._summed_quantity(SimpleNamespace(**absent_read))
    assert zero is not None and zero.amount == Decimal("0") and zero.unit == "ERU", (
        f"a $0.00 storm-water line needs a quantity of 0 ERU; got {zero!r}. "
        "None here is a REFUSAL and the customer gets no document"
    )

    assert [row["unit_id"] for row in listed] == [str(unit.id)]
    assert with_row == [], "a unit that HAS an assessment must not be listed at zero"
    # And the row is back, so the rest of the module still reads $4.50 there.
    assert restored_read["installed_capacity"] == Decimal("1.0000")


@_live
@requires_postgres
def test_live_the_other_four_capacity_services_are_untouched(storm_water_tenant):
    """**THE THING A CARELESS BUILD WOULD BREAK, asserted in money.**

    Solar, battery, broadband and trash still read INSTALLED EQUIPMENT, on the
    same tenant, in the same run. Three of the four began billing real money the
    same day this ruling was made; a change that made them read a unit field
    would have implemented the ruling and taken all four back to `$0.00`.
    """
    tenant, _actor, _summary = storm_water_tenant
    with tenant_ctx(tenant):
        got = {
            "solar": _service_total(tenant, fixture.SOLAR_UNIT_WITH_THREE_PANELS, "solar"),
            "battery": _service_total(tenant, fixture.BATTERY_UNIT_WITH_TEN_KW, "battery"),
            "broadband": _service_total(tenant, 10, "broadband"),
            "trash": _service_total(tenant, fixture.CART_UNIT_WITH_THREE, "trash"),
        }
    assert got == {
        # 2 + 4 + 8 kW = 14 kW at $14.0000 — the PO's own array.
        "solar": Decimal("196.00"),
        # 10 kW at $3.0000.
        "battery": Decimal("30.00"),
        # 500 Mbps at $0.1000.
        "broadband": Decimal("50.00"),
        # 3 carts × $15.00 — a COUNT, not a sum, and still a count.
        "trash": Decimal("45.00"),
    }, f"the four equipment-carried capacity services bill {got}"


@_live
@requires_postgres
def test_live_gt17_is_unmoved(storm_water_tenant):
    """**❄️ `GT-17` — water `$39.50`, sewer `$36.00` (re-signed 2026-09-08, `CR-081`), on a bill that now also
    carries a priced storm-water line.**

    Asserted as PER-LINE `usage` figures, which is how the frozen case states
    them: adding a service ADDS a line and moves neither. **If this fails the
    change STOPS** — a frozen figure moves only by a finance re-sign
    (HUMAN-GUIDE §6), never by a lane.
    """
    tenant, _actor, _summary = storm_water_tenant
    with tenant_ctx(tenant):
        lines = _lines(tenant, fixture.CASE_REFERENCE_BILL)

    def total(service: str, kind: str) -> Decimal:
        return sum(
            (
                line.amount
                for line in lines
                if line.service_id is not None
                and line.service.code == service
                and line.kind == kind
            ),
            Decimal("0"),
        )

    assert total("water", "usage") == Decimal("39.50"), (
        "❄️ GT-17's water usage line moved. STOP — this is a finance re-sign "
        "(HUMAN-GUIDE §6), never an inline edit"
    )
    # ❄️ RE-SIGNED 2026-09-08 (`CR-081`, HUMAN-GUIDE §6, B5's own table):
    # sewer is 90% of the water volume at $5.00 — 7.2 kgal → **$36.00**. It
    # read $15.80 (40% of the water charge) here until `DEF-RAT-9058`.
    assert total("sewer", "usage") == Decimal("36.00"), (
        "❄️ GT-17's sewer line moved. STOP — finance re-sign (HUMAN-GUIDE §6)"
    )
    # The reference unit is a single-family house, so it carries an assessment
    # like every other — a new line, beside the frozen ones, not instead of one.
    assert total("storm_water", "usage") == Decimal("4.50")
