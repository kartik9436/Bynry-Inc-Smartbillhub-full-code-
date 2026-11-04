# ── Trace ──────────────────────────────────────────────
# Rules:   BR-RAT-1010 (PO 2026-09-01, verbatim: "rate schedule will not
#          provdie the size, charge code will provide") · BR-RAT-088 (the rule
#          this completes — the charge code owns the base AMOUNT, CONFIRMED
#          2026-08-20; its clause "a size absent from the SCHEDULE still means
#          not served" is SUPERSEDED at that word) · BR-RAT-690 (the per-size
#          table's writer and its three readings) · BR-RAT-120 (the axis
#          narrows and never widens; the sequencing) · BR-RAT-108 (a code is
#          scoped to customer classes) · BR-RAT-015 / BR-TEN-171 (sewer)
# Defects: DEF-2878 (R3's comparison compared one value with itself, so the
#          REFUSAL is R3's only independent evidence — this file is that
#          evidence pointed at the object the PO ruled it must read)
# Tests:   this file
# ───────────────────────────────────────────────────────
"""BR-RAT-1010 — THE CHARGE CODE STATES WHICH CONNECTION SIZES ARE PRICED.

PO ruling 2026-09-01, in one sentence: *"rate schedule will not provdie the
size, charge code will provide"* — said in the same breath as *"What can
actually release R3 — The refusal."*

WHAT WAS SPLIT, AND WHY IT MATTERED
-----------------------------------
`BR-RAT-088` moved the base AMOUNT onto the charge code on 2026-08-20 and its
own consequence clause left the MEMBERSHIP question behind: *"a size absent
from the SCHEDULE still means not served"*. So from that day the product
answered two halves of one question from two different objects — **what does a
5/8" water connection cost** off `charge_code_amounts`, and **is a 5/8" water
connection priced at all** off the rate schedule's `rate_size_rows`. A utility
that priced `BASE-W` per size on the screen `BR-RAT-690` built could still have
its meter refused by a schedule that knew nothing about it.

WHAT THIS FILE PINS
-------------------
  TC1  the code's per-size table IS the axis — the sizes it states, and no
       others.
  TC2  **the ruling itself**: a size the SCHEDULE configures and the CODE does
       not is REFUSED. The schedule cannot widen the code's axis.
  TC3  the refusal names the CHARGE CODE, because a refusal that sends a clerk
       to the wrong screen is not curable (`BR-RAT-120`'s own cost clause).
  TC4  a code pricing FLAT states no axis and the schedule answers, unchanged —
       which is every tenant on this database, so no fixture moves.
  TC5  no `is_base` code at all: the schedule answers, unchanged.
  TC6  the union across two class-scoped codes (`BR-RAT-108`), and the reason
       it is a union: R3 answers WHICH SIZE and R4 answers WHOSE CODE.
  TC7  `BR-RAT-690`'s middle state survives: a row with a NULL amount is a size
       that EXISTS at R3 and refuses at R4 by name.
  TC8  sewer is untouched — ruled sizeless, blank size resolves.

⚠ **NOTHING IS SWITCHED ON AND NO BILL CHANGES.** `SERVED_BY_CHAIN_DEFAULT` is
empty and no deployment names a step (`BR-RAT-120`), so this changes what the
chain WILL do, never what any invoice says today.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.rating import models as rating_models
from apps.rating import resolution, resolution_catalogue
from apps.tenancy import models as tenancy_models

from tests.test_def_438_parity import SERVICE_DATE, WATER_SIZE, _water_plan
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

#: A second size, priced by the code in TC1 and by nobody in TC2.
BIG_SIZE = "2-inch"
#: A size the SCHEDULE configures and the CODE never mentions. TC2's whole point.
SCHEDULE_ONLY_SIZE = "4-inch"

NO_TAX_FACTS = {
    "account": resolution.AccountFacts(account_no="", unit_id=""),
    "premises": resolution.PremisesFacts(),
}


def _water_version(tenant):
    plan = _water_plan(tenant)
    version = next(
        v
        for v in resolution_catalogue.build_catalogue(
            plan_id=plan.id, service_date=SERVICE_DATE, **NO_TAX_FACTS
        ).schedule_versions
        if v.service == "water"
    )
    return plan, version


def _base_code(tenant, *, code, service_code="water", sizes=None, flat=None, classes=None):
    """An `is_base` charge code, priced per size or flat — never both.

    `resolve_charge_codes` refuses a code carrying both (CR-013 part 2, *"one
    basis"*), so this helper cannot build that shape either: passing `sizes`
    leaves `amount` NULL. `sizes` maps a size class to its amount, and a
    **`None` amount is deliberate and meaningful** — `BR-RAT-690`'s middle
    reading, *the utility does not serve this size*, which TC7 pins.
    """
    service = tenancy_models.Service.objects.get(code=service_code)
    row = rating_models.Charge.objects.create(
        tenant=tenant,
        code=code,
        name=code,
        service=service,
        is_base=True,
        charge_type="recurring",
        amount_rule="flat",
        amount=flat,
        applies_to_customer_classes=list(classes or []),
    )
    for size, amount in (sizes or {}).items():
        rating_models.ChargeCodeAmount.objects.create(
            tenant=tenant, charge=row, size_class=size, amount=amount, currency="USD"
        )
    return row


def _meter(size):
    return resolution.MeterFacts(service="water", connection_size=size)


# ── TC1 · the code's table is the axis ──────────────────────────────────────


def test_TC1_the_codes_per_size_table_is_the_axis(brazos, dana):
    """`BASE-W` prices 5/8" and 2". Those two sizes, and no others, are served.

    The figures are this file's own and price nothing here: R3 is a MEMBERSHIP
    test since `DEF-2823` and the money is R4's.
    """
    with tenant_ctx(brazos):
        _base_code(
            brazos,
            code="BASE-W",
            sizes={WATER_SIZE: Decimal("8.0000"), BIG_SIZE: Decimal("34.0000")},
        )
        _plan, water = _water_version(brazos)

        assert sorted(water.size_rows) == sorted([WATER_SIZE, BIG_SIZE]), (
            "the axis must be exactly what the charge code states — "
            f"got {sorted(water.size_rows)}"
        )
        assert water.size_axis_source == "charge_code"
        assert resolution.resolve_served_size(water, _meter(WATER_SIZE)) == WATER_SIZE
        assert resolution.resolve_served_size(water, _meter(BIG_SIZE)) == BIG_SIZE


# ── TC2 · THE RULING · the schedule cannot widen the code's axis ────────────


def test_TC2_a_size_the_schedule_configures_and_the_code_does_not_refuses(brazos, dana):
    """**This is the ruling, and it is the one case that changes behaviour.**

    `_water_plan` writes a `rate_size_rows` row, so the SCHEDULE says it prices
    that size. Before 2026-09-01 that row WAS the axis and a 4" meter resolved.
    With a base charge code stating its own table, the schedule's row is not
    consulted and the 4" refuses by name.
    """
    with tenant_ctx(brazos):
        _base_code(brazos, code="BASE-W", sizes={WATER_SIZE: Decimal("8.0000")})
        plan, water = _water_version(brazos)
        version_id = water.version_id

        # The schedule DOES state the size — this is not an absent row.
        rating_models.RateSizeRow.objects.create(
            tenant=brazos,
            tariff_version_id=version_id,
            size_class=SCHEDULE_ONLY_SIZE,
            minimum_bill=Decimal("5.0000"),
            currency="USD",
        )
        _plan, water = _water_version(brazos)
        assert SCHEDULE_ONLY_SIZE in resolution_catalogue.size_classes_for(version_id), (
            "the schedule must genuinely configure this size, or TC2 proves nothing"
        )

        assert SCHEDULE_ONLY_SIZE not in water.size_rows
        with pytest.raises(resolution.SizeNotServed):
            resolution.resolve_served_size(water, _meter(SCHEDULE_ONLY_SIZE))


# ── TC3 · the refusal names the object a person has to open ─────────────────


def test_TC3_the_refusal_names_the_charge_code_not_the_schedule(brazos, dana):
    """A refusal is only useful if it sends the clerk to the right screen.

    `BR-RAT-120` accepted a real cost — *"the system refuses bills that price
    perfectly well today"* — on the understanding that the refusal is CURABLE.
    Naming the rate schedule when the axis was read off the charge code makes
    it uncurable: the size is missing from a table on another screen.
    """
    with tenant_ctx(brazos):
        _base_code(brazos, code="BASE-W", sizes={WATER_SIZE: Decimal("8.0000")})
        _plan, water = _water_version(brazos)

        with pytest.raises(resolution.SizeNotServed) as refused:
            resolution.resolve_served_size(water, _meter(BIG_SIZE))
        sentence = str(refused.value)
        assert "base charge code" in sentence, sentence
        assert "rate schedule version" not in sentence, sentence
        assert BIG_SIZE in sentence, sentence


# ── TC4 · a flat code states no axis ────────────────────────────────────────


def test_TC4_a_flat_code_states_no_axis_and_the_schedule_answers(brazos, dana):
    """**The shipped fixture's own case, and why nothing moved today.**

    `BR-RAT-088` seeds `BASE-W` flat at `$8.00` deliberately, and `BR-RAT-690`
    says what a flat amount IS: *"a per-size table is the flat amount stated
    once per size"*. A code pricing flat therefore makes no statement about
    which sizes exist, and reading it as an EMPTY axis would refuse every meter
    of every tenant on this database.
    """
    with tenant_ctx(brazos):
        _base_code(brazos, code="BASE-W", flat=Decimal("8.0000"))
        _plan, water = _water_version(brazos)

        assert water.size_axis_source == "schedule"
        assert WATER_SIZE in water.size_rows
        assert resolution.resolve_served_size(water, _meter(WATER_SIZE)) == WATER_SIZE


# ── TC5 · no base code at all ───────────────────────────────────────────────


def test_TC5_no_base_charge_code_leaves_the_schedule_answering(brazos, dana):
    """Unchanged, and it is the control for every case above.

    A utility that has not adopted `BR-RAT-088` keeps the axis it has always
    had. The fallback is the SAME legacy ladder R4 uses for the amount, not a
    second mechanism.
    """
    with tenant_ctx(brazos):
        assert not rating_models.Charge.objects.filter(tenant=brazos, is_base=True).exists()
        _plan, water = _water_version(brazos)

        assert water.size_axis_source == "schedule"
        assert resolution.resolve_served_size(water, _meter(WATER_SIZE)) == WATER_SIZE


# ── TC6 · two class-scoped codes union, and R4 does the narrowing ───────────


def test_TC6_class_scoped_codes_union_because_R3_is_asked_per_service(brazos, dana):
    """`BR-RAT-108` scopes a code to customer classes, so one service can hold
    `BASE-W` (residential) and `BASE-W-COM` (commercial) with different tables.

    R3 is handed no customer class — it answers WHICH SIZE, and WHICH CODE is
    R4's narrowing. So the axis is the union, and a size priced for one class
    and not the other passes R3 and refuses at **R4** by name. Narrowing here
    would refuse a commercial meter for a size its own code prices, naming the
    wrong step to the person who has to fix it.
    """
    with tenant_ctx(brazos):
        _base_code(
            brazos,
            code="BASE-W",
            sizes={WATER_SIZE: Decimal("8.0000")},
            classes=["residential"],
        )
        _base_code(
            brazos,
            code="BASE-W-COM",
            sizes={BIG_SIZE: Decimal("34.0000")},
            classes=["commercial"],
        )
        _plan, water = _water_version(brazos)

        assert sorted(water.size_rows) == sorted([WATER_SIZE, BIG_SIZE])
        assert resolution.resolve_served_size(water, _meter(BIG_SIZE)) == BIG_SIZE
        # And the class narrowing is still owed — by R4, on the code itself.
        code = resolution.ChargeCode(
            code="BASE-W",
            service="water",
            customer_classes=("residential",),
            is_base=True,
            amounts={WATER_SIZE: Decimal("8.0000")},
        )
        with pytest.raises(resolution.ChargeCodeAmountMissing):
            resolution.charge_code_amount(code, BIG_SIZE)


# ── TC7 · BR-RAT-690's middle state survives the move ───────────────────────


def test_TC7_a_null_amount_is_a_size_that_exists_and_refuses_at_R4(brazos, dana):
    """`BR-RAT-690` keeps three readings apart and this move must not fuse two.

    *No row* is a size nobody priced — R3 refuses. *A row with a NULL amount*
    is the utility saying it does not serve that size — the size EXISTS on the
    axis and the refusal is about MONEY, so it fires at R4. Collapsing them
    would send a clerk to add a row that is already there.
    """
    with tenant_ctx(brazos):
        _base_code(
            brazos,
            code="BASE-W",
            sizes={WATER_SIZE: Decimal("8.0000"), BIG_SIZE: None},
        )
        _plan, water = _water_version(brazos)

        assert BIG_SIZE in water.size_rows, "a stated size with no amount still EXISTS"
        assert resolution.resolve_served_size(water, _meter(BIG_SIZE)) == BIG_SIZE

        code = resolution.ChargeCode(
            code="BASE-W",
            service="water",
            is_base=True,
            amounts={WATER_SIZE: Decimal("8.0000"), BIG_SIZE: None},
        )
        with pytest.raises(resolution.ChargeCodeAmountMissing):
            resolution.charge_code_amount(code, BIG_SIZE)


# ── TC8 · sewer is untouched ────────────────────────────────────────────────


def test_TC8_sewer_is_untouched_by_the_move(brazos, dana):
    """`BR-RAT-015` prices sewer as a share of the water usage charge, so a
    sewer connection has no size class and never will. The move must not turn
    *ruled to have none* into *nobody priced it* — the two readings that
    `apps/tenancy/service_size_classes.py` exists to keep apart.
    """
    with tenant_ctx(brazos):
        _base_code(brazos, code="BASE-S", service_code="sewer", flat=Decimal("0.0000"))
        assert resolution_catalogue.base_code_sizes_for("sewer") == ()
        assert resolution_catalogue.configured_sizes_for(None, "sewer") == (
            resolution_catalogue.NO_SIZE_AXIS,
        )
