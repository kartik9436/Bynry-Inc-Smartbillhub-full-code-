# ── Trace ──────────────────────────────────────────────
# Defects: DEF-438 (the R1–R7 chain has no production caller) · DEF-452 (no
#          seeded plan carries a customer class) · DEF-455 (the seeder writes no
#          base charge codes) · DEF-466 (R5's factor can never be anything but
#          1.0) · DEF-477 (a cleared base does not stay cleared) · DEF-484
#          (gather passes no connection size)
# Rules:   BR-RAT-001 (the METER multiplier scales the QUANTITY, before tiers) ·
#          BR-MET-019 (`consumption = (current − prior) × multiplier`) ·
#          BR-MET-056 (a read stores the multiplier USED) · BR-RAT-007 (the
#          version in force at the SERVICE date) · BR-RAT-030 (published plans
#          only) · BR-RAT-088 (the charge code owns the base)
# Tests:   this file
# ───────────────────────────────────────────────────────
"""THE PARITY HARNESS: price one tenant BOTH WAYS and name every step that differs.

WHY A HARNESS AND NOT A FLIP
----------------------------
`apps/rating/resolution.py` implements design §A2's R1–R7 narrowing and has NO
PRODUCTION CALLER (DEF-438). The bill run reaches rating through
`apps/billing/gather.py`, which resolves other functions entirely. So there are
two implementations of "which of these many prices applies to this customer",
only one of them can produce an invoice, and **nobody has ever compared them**.

This file compares them, step by step, on real database rows. It is the
deliverable whether or not anything is flipped:

  * where the two agree, that agreement is the PERMISSION to flip that step —
    a cutover with a green parity assertion behind it is a provable one;
  * where they disagree, the failure NAMES THE STEP (R1..R7) and BOTH FIGURES,
    which is a map of the gap rather than an opinion about it.

⚠ **IT NEVER MAKES A DIFFERENCE GO AWAY BY MOVING A FIGURE.** Every divergence
below is either an already-filed defect (cited by id at the assertion) or an
open question. B4 money math and B5 goldens are ❄️ FROZEN and no figure in this
file is one of theirs: every number here is `core/sample_fixture.py`'s, which is
Silver Creek's own configuration, or is derived from it in the test itself.

HOW A DIVERGENCE IS RECORDED — AND WHY `xfail(strict=True)`
------------------------------------------------------------
A step the two paths do NOT agree on is an `xfail(strict=True)` naming its
defect. Strict is the whole point: the day someone closes the gap the test
XPASSES, and a strict xpass FAILS THE SUITE (DEF-488 is the precedent, one
module over). So this file cannot quietly go on describing a gap that has been
closed — which is the exact failure mode hard-won law 1 is about, and the one
`resolve_discounts` sat in for a day (DEF-361).

WHAT "LINE BY LINE" MEANS HERE
-------------------------------
Not the invoice's rendered lines — those are stage 6's, and stage 6 writes. It
means every INPUT the two paths resolve before any money is computed: the plan
version, the schedule version id per service, the connection size, the billable
quantity, the charge codes, the money factor, the discounts and the taxes.
Comparing totals would hide two errors that cancel; comparing inputs cannot.

THE ONE TRAP THAT WOULD HAVE MADE THIS HARNESS LIE (read before editing)
------------------------------------------------------------------------
**R3b IS DUPLICATED, NOT MISSING, AND THE DUPLICATE IS UPSTREAM.**
`apps/metering/validation.compute_consumption` stores
`consumption = (current − prior) × multiplier` on the read row (BR-MET-019), and
`apps/metering/selectors.billing_reads_for_unit` says so in terms:
*"`consumption` is metering's stored figure … and it is ALREADY
POST-MULTIPLIER"*. So the quantity billing holds has been through R3b once
already.

`resolution.billable_quantity(meter, register_quantity)` multiplies by the
multiplier AGAIN. Feeding it the stored consumption would bill **100×** on a ×10
register — a plausible-looking document and a customer's ruin. This harness
therefore feeds the chain the REGISTER DIFFERENCE and compares its output to
metering's stored figure, which is the comparison that actually proves the two
implementations of R3b agree. `test_r3b_*` below is that proof, and it is the
only test in this file whose FAILURE would mean a live bill is wrong today.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pytest
from django.test import override_settings

from apps.billing import gather
from apps.rating import models as rating_models
from apps.rating import resolution, resolution_catalogue
from apps.customers import models as customer_models
from apps.metering import models as metering_models
from apps.tenancy import models as tenancy_models
from core import sample_fixture as fixture

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (
    make_plan,
    make_premises,
    make_unit,
    state_size_axis,
    tenant_ctx,
)
from tests.test_us_met_reads_helpers import RATIFIED_BAND, a_meter, commit_read

pytestmark = pytest.mark.django_db

PERIOD_START = date(2026, 7, 1)
PERIOD_END = date(2026, 7, 31)
SERVICE_DATE = PERIOD_END
CYCLE_DAYS = 31

#: Silver Creek's own water ladder and base, read from the fixture and never
#: re-typed (B12 §No hard-coded values). A second literal here would be a second
#: source of truth for the figure this harness exists to check.
WATER_BASE = Decimal(fixture.WATER_BASE)

#: The connection size this harness prices water at, and — since BR-RAT-120 (PO
#: 2026-08-28) — the size `_water_plan` CONFIGURES on the schedule version.
#:
#: ⚠ **IT USED TO BE A TEST ARGUMENT AND NOTHING ELSE.** `build_catalogue` took
#: a `served_sizes` keyword, so naming a size here made the schedule serve it —
#: which is exactly why R3's *"this size is not served"* refusal could never
#: fire (`DEF-1810`: `served_sizes=('5/8',)` resolved $8.00 and
#: `served_sizes=('3-inch',)`, a size the utility never priced, resolved $8.00
#: as well). The keyword is gone. The size is now written to `rate_size_rows`,
#: where a real tenant would put it, and the harness measures the same figures
#: it always did — see `test_br_rat_120_size_refusal.py` for the size that is
#: NOT configured and therefore refuses.
WATER_SIZE = "5/8"


# ══════════════════════════════════════════════════════════════════════════
# The finding type — what a parity failure SAYS
# ══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class Divergence:
    """One step where the two paths disagree.

    `step` is the design's own R-number, because "billing and rating disagree"
    is not actionable and "R4 resolved 0 charge codes where the chain resolved
    1" is. `live` and `chain` are the two values verbatim — never a boolean,
    never a summary: the figures are the finding.
    """

    step: str
    service: str
    live: object
    chain: object
    note: str = ""

    def __str__(self) -> str:  # pragma: no cover - a message, not a branch
        tail = f" — {self.note}" if self.note else ""
        return f"{self.step} [{self.service}]: live={self.live!r} chain={self.chain!r}{tail}"


def _report(divergences: list[Divergence]) -> str:  # pragma: no cover - message
    return "\n".join(f"  {d}" for d in divergences) or "  (none)"


# ══════════════════════════════════════════════════════════════════════════
# Fixture — Silver Creek's shape, on real rows across four modules
# ══════════════════════════════════════════════════════════════════════════


def _water_plan(tenant, *, dated=True, base_code=True):
    """A published water plan priced the way rating really stores an inclining
    ladder — the prices are TIERS (BR-RAT-032), not a column.

    ⚠ **THE BASE IS ON A CHARGE CODE FROM 2026-09-28, AND THE PLAN'S COLUMN IS
    WRITTEN BESIDE IT AS A DISPLAY (`DEF-BIL-7170`).** This paragraph read: *"The
    base is `plan_services.base_charge`, which is where BR-RAT-012 and
    BR-RAT-027 put it and where `gather._base_charge_for` reads it. BR-RAT-088
    has since moved it onto the charge code; that migration has not run on any
    tenant (DEF-455), and this fixture states the world as it IS."* The Product
    Owner ended that world — *"we will never take default value from plan $8.0 -
    that is retired"* — so a plan with no `is_base` charge code cannot bill at
    all, and a fixture without one measures a refusal rather than a price.

    `base_code=True` mints ONE unscoped water base code at the SAME `WATER_BASE`
    the plan states, so **no figure in this harness moves**: it is the same
    `$8.00`, stated on the object that now owns it. `base_code=False` is for the
    files that mint their own codes — a second one here would be `DEF-468`'s
    ambiguity and would refuse every case in them.

    ⚠ `dated` DEFAULTS TO TRUE AND THE SHIPPED PRODUCT DEFAULTS TO FALSE, which
    is the R1 divergence below. Every test that wants to compare a step PAST R1
    has to state the dates first, because the chain refuses the account outright
    without them — so the divergence is not merely one finding among several,
    it is the gate in front of all the others. `dated=False` is the one test
    that measures it.
    """
    from apps.rating import selectors as rating_selectors

    # `dated` reaches `make_plan` itself: since `DEF-2816` it states a start
    # date of its own, and this fixture's whole `dated=False` branch exists to
    # reproduce a plan that has none.
    plan = make_plan(tenant, name="Silver Creek Residential", services=("water",), dated=dated)
    if dated:
        rating_models.RatePlan.objects.filter(pk=plan.id).update(
            effective_from=date(2026, 1, 1), effective_to=None
        )
    for row in rating_selectors.plan_rate_schedules(plan.id):
        version = rating_models.TariffVersion.objects.create(
            tenant=tenant,
            tariff=row["tariff"],
            model="tiered",
            base_charge=WATER_BASE,
            uom=fixture.WATER_UOM,
            currency="USD",
            effective_from=date(2026, 1, 1),
        )
        # BR-RAT-120 — the size axis is CONFIGURATION, so the harness configures
        # it. `minimum_bill=None` is deliberate: it means "this size has no
        # minimum bill" (r10's em-dash), which is the same answer the scalar
        # fallback gave before this row existed, so no figure in this harness
        # moves. The row's job is to say the schedule PRICES 5/8" at all.
        rating_models.RateSizeRow.objects.update_or_create(
            tenant=tenant,
            tariff_version=version,
            size_class=WATER_SIZE,
            defaults={"minimum_bill": None, "currency": "USD"},
        )
        # ⚠ **AND THE RATIFIED LADDER TOO, FROM 2026-09-01 (`DEF-2816`).**
        # `WATER_SIZE` above is `"5/8"` — the vocabulary `DEF-1810` was written
        # in, and **not a code any meter can carry**: `BR-TEN-171` names water's
        # sizes `W-58`, `W-34`, `W-1` … and `assets.size_class` is validated
        # against that list. So this version priced exactly one size that no
        # connection is, and every account on it refused at R3 the moment the PO
        # ruled the step on — first as *"has no connection size"* while the
        # fixture's meters were unsized, then as *"connection size 'W-58' has no
        # row on the rate schedule version"* once they were given one. The
        # `"5/8"` row STAYS because four other files read `WATER_SIZE` as a
        # token and it is their subject; what is added is the ladder a real
        # schedule states, through `sample_size_rows` — one row per RATIFIED
        # class, `minimum_bill` NULL, moving no money (no live pricing read
        # touches `rate_size_rows`).
        state_size_axis(version, "water")
        for seq, (from_qty, to_qty, price) in enumerate(fixture.WATER_TIERS, start=1):
            rating_models.RateTier.objects.create(
                tenant=tenant,
                tariff_version=version,
                seq=seq,
                from_qty=Decimal(from_qty),
                to_qty=None if to_qty is None else Decimal(to_qty),
                unit_price=Decimal(price),
            )
        # ⚠ `make_plan` writes the SCHEDULE BINDING and no `plan_services` row,
        # so the plan's declared service set is empty on every fixture in this
        # repo that uses it. The row is created here rather than assumed,
        # because `plan_services.base_charge` is what `gather._base_charge_for`
        # reads as the PLAN's figure (BR-RAT-012 / BR-RAT-027) and a missing row
        # silently demotes the comparison to the schedule's column — which is
        # DEF-154's exact shape and would make this harness agree with itself
        # about the wrong number.
        rating_models.PlanService.objects.update_or_create(
            tenant=tenant,
            rate_plan_id=plan.id,
            service_id=row["service_id"],
            defaults={"base_charge": WATER_BASE},
        )
    if base_code:
        # ── `DEF-BIL-7170` · WHAT ACTUALLY PRICES THE BASE NOW ──────────────
        # Unscoped (`BR-RAT-108`: NULL or `[]` is EVERY class) and at the SAME
        # figure the plan states, so this adds a source and moves no money.
        #
        # ⚠ **AND THE SCHEDULE NAMES IT, FROM 2026-10-06 (`DEF-RAT-9832`).** The
        # PO ruled that a schedule naming no base code bills `$0.00` — nothing
        # is taken from the charge-code list by class — so this fixture does
        # what activation does when one code could serve (`services.
        # _require_a_named_base_code`): it names it. Same `$8.00`, now reached
        # by the ruled chain.
        parity_base, _ = rating_models.Charge.objects.get_or_create(
            tenant=tenant,
            code="BASE-W-PARITY",
            defaults=dict(
                name="Water base",
                charge_type="recurring",
                service=tenancy_models.Service.objects.get(code="water"),
                amount_rule="flat",
                amount=WATER_BASE,
                is_base=True,
                applies_to_customer_classes=[],
            ),
        )
        rating_models.TariffVersion.objects.filter(
            tenant=tenant, tariff_id__in=[row["tariff"].id for row in rating_selectors.plan_rate_schedules(plan.id)]
        ).update(base_charge_code_id=parity_base.id)
    return plan


def price_water_base_by_size(tenant):
    """Give the parity water base a price that DEPENDS ON THE SIZE (`DEF-BIL-9054`).

    Since `DEF-RAT-8822` (PO 2026-10-01, option A: *"Hold back only where the
    price depends on the size"*) an unsized meter is billed on a base that is
    one price for all sizes and held only on a per-size base. `_water_plan`'s
    base is the first kind, so a case that tests the HOLD calls this. One basis
    per code (CR-013): the all-sizes price is REPLACED, never stated beside it —
    the smallest ratified size at the same `WATER_BASE`, the largest at $34.00.
    """
    from apps.rating import charge_prices
    from apps.rating.constants import PRICE_HISTORY_EPOCH
    from apps.tenancy import service_size_classes

    charge = rating_models.Charge.objects.get(tenant=tenant, is_base=True, service__code="water")
    sizes = [code for code, _name in service_size_classes.size_classes_for_service("water")]
    target = {(sizes[0], None): Decimal(WATER_BASE), (sizes[-1], None): Decimal("34.00")}
    charge_prices.save_prices(charge, target, effective_from=PRICE_HISTORY_EPOCH, effective_to=None)


def _account_on(
    tenant, actor, plan, *, multiplier="1", register="1200", prior="1150",
    size_class=RATIFIED_BAND,
):
    """One account, one unit, one water meter, one committed read.

    `multiplier` is the meter's, and it is the fact R3b turns a register
    difference into a billable quantity with. `commit_read` writes the read the
    way metering does — `consumption` ALREADY multiplied — so the fixture
    reproduces the duplication the module docstring warns about instead of
    hiding it.

    ⚠ **`size_class` IS EXPLICIT FROM 2026-09-01 (`DEF-2965`).** This helper used
    to say nothing about the connection size, so it inherited `a_meter`'s old
    `None` default — a meter with no size recorded. That was free while nothing
    read the column and became a REFUSAL the day the PO ruled R3 on: water is a
    banded service, so `resolve_served_size` stops the bill rather than pricing
    a size the utility never priced. The default is now the service's smallest
    ratified band (`BR-TEN-171`), which is `a_meter`'s own default and never a
    string typed here.

    **`size_class=None` still builds a meter with no size recorded**, and the
    case whose subject IS that absence passes it —
    `test_def_1900_connection_size.py::test_TC7`, which proves the column's
    migration cannot move a figure. The distinction matters: an unsized meter
    must stay reachable, and it must be ASKED FOR rather than inherited.
    """
    premises = make_premises(actor, address_line="4 Quarry Hill Rd", services_available=["water"])
    unit = make_unit(actor, premises["id"], label="Unit A", services=["water"])
    asset = a_meter(
        actor,
        asset_no="M-9001",
        service="water",
        uom=fixture.WATER_UOM,
        multiplier=multiplier,
        unit_id=unit["id"],
        size_class=size_class,
    )
    from apps.metering import services as metering_services

    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(plan.id), "effective_from": "2026-01-01"}
    )
    register_delta = Decimal(register) - Decimal(prior)
    commit_read(
        actor,
        asset["id"],
        day="2026-07-28",
        value=register,
        prior_value=prior,
        # BR-MET-019 — what metering itself would have stored. The harness
        # writes the SAME arithmetic rather than a hand-picked number, so a
        # multiplier change moves the fixture and the expectation together.
        consumption=register_delta * Decimal(multiplier),
        unit=fixture.WATER_UOM,
        multiplier=multiplier,
    )
    account = customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        account_no="SCW-0001",
        status=customer_models.AccountStatus.objects.get(tenant=tenant, code="active"),
        # ⚠ AMENDED 2026-10-01 (billing red triage, `DEF-BIL-8712`): this read
        # `AccountType.objects.first()` — no tenant, no order. The seeded types
        # are uuid7 rows written in the same millisecond, so WHICH one is
        # "first" is the random tail of the id, and on some runs the account
        # was COMMERCIAL: `test_def_bil_7170`'s residential account was then
        # charged the commercial-scoped `$34.00` base, correctly, and the case
        # failed one run in three. The cases built on this helper say
        # residential, so it is named.
        account_type=customer_models.AccountType.objects.get(tenant=tenant, code="residential"),
    )
    return account, unit, asset, register_delta


# ══════════════════════════════════════════════════════════════════════════
# The two paths
# ══════════════════════════════════════════════════════════════════════════


def _price_live(account):
    """THE PATH A CUSTOMER CAN REACH — `apps/billing/gather.py`.

    Everything an invoice is built from passes through here today. Nothing is
    re-implemented: this calls billing's own function with billing's own
    arguments.
    """
    reads = _readings_for(account)
    return gather.gather_account(
        account=account,
        service_date=SERVICE_DATE,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        cycle_days=CYCLE_DAYS,
        readings=reads,
    )


def _readings_for(account):
    """Metering's own seam, exactly as `apps/billing/runs.py` calls it."""
    from apps.billing.contracts import ServiceReading
    from apps.billing import rating_seam
    from apps.metering import selectors as metering_selectors

    rows = metering_selectors.billing_reads_for_unit(
        account.unit_id, period_start=PERIOD_START, period_end=PERIOD_END
    )
    readings = []
    for row in rows:
        quantity = None
        if row["consumption"] is not None:
            quantity = rating_seam.Quantity(amount=row["consumption"], unit=row["unit"])
        readings.append(
            ServiceReading(
                service_code=row["service_code"],
                service_id=row["service_id"],
                consumption=quantity,
                estimated=row["estimated"],
                absent_reason=row["absent_reason"],
                prior_read=row["prior_value"],
                current_read=row["current_value"],
                read_id=row["read_id"],
            )
        )
    return tuple(readings)


def _price_chain(account, *, sizes, register_deltas, multipliers, past_r4=False, enrolments=()):
    """THE RULED PATH — `apps/rating/resolution.resolve`, through the adapter.

    ⚠ `register_deltas` are REGISTER DIFFERENCES, pre-multiplier, and that is
    the module docstring's trap made explicit in a signature. Handing this
    metering's stored `consumption` would apply the multiplier twice.

    ⚠⚠ **`past_r4` IS A HARNESS SCAFFOLD AND THE PRODUCT MAY NOT DO IT.**
    On a real tenant R4 refuses before R5, R6 or R7 is ever reached — five
    provisioned charge codes state no amount R4's contract can express, and
    `resolve()` runs `resolve_charge_codes` for the whole bill (see
    `test_r4_ON_A_REAL_TENANT_REFUSES_EVERY_BILL_FIVE_TIMES_OVER`). So without
    this flag the ONLY thing this harness could ever report is *"R4 refused"*,
    and every other step would be unmeasured — which is precisely the state
    DEF-438 has been in, one layer up.

    `past_r4=True` drops the codes R4 cannot price, **so that the steps AFTER it
    can be compared at all**. It is not a fix, it is not a proposal, and it must
    never be copied into `apps/`: dropping a charge code a utility configured is
    dropping money the utility charges. It is stated here, loudly, rather than
    done quietly inside the adapter — where it would have looked like a design.
    """
    unit = metering_models.Unit.objects.get(pk=account.unit_id)
    # ⚠ **NO `served_sizes` — BR-RAT-120 REMOVED IT (PO 2026-08-28).** `sizes`
    # below is still what this account's meters ARE, and R3 looks that up; what
    # the schedule SERVES is read from the schedule (`_water_plan` writes the
    # `rate_size_rows` row). Handing the catalogue the size under test is the
    # bug DEF-1810 names, and it is now a `TypeError` rather than a habit.
    #: ⚠ **BUILT BEFORE THE CATALOGUE SINCE `DEF-2824`.** R7's candidate query
    #: is narrowed by the ACCOUNT's class, the PREMISES' geography and the
    #: plan's services, and `rating.selectors.plan_tax_rules` fails closed on
    #: every one of them — so a catalogue built without these facts carries only
    #: the UNRESTRICTED taxes and R7 has nothing to attach. These two objects
    #: used to be constructed below, after the catalogue, which is why they
    #: could not reach it.
    facts = resolution.AccountFacts(
        account_no=account.account_no,
        unit_id=str(account.unit_id),
        customer_class=getattr(account.account_type, "code", None),
        # DEF-502 — the account's enrolment CODES, for the R6 comparison. The
        # chain narrows them against the catalogue (plan-bound discounts);
        # the live path's gather applies the same two gates through
        # `rating.selectors.billable_discount_rules`.
        enrolments=tuple(enrolments),
        # DEF-383 / DEF-2824 — WHOSE bill, so an exemption certificate can be
        # found. The one tax gate whose absence OVER-charges.
        account_id=str(account.id),
    )
    premises = resolution.PremisesFacts(
        inside_city_limits=getattr(unit.premises, "inside_city_limits", None),
        # DEF-2824 — the two keys `premises_in_scope` reads besides the flag.
        city=getattr(unit.premises, "city", None),
        state=getattr(unit.premises, "state", None),
    )
    catalogue = resolution_catalogue.build_catalogue(
        plan_id=unit.rate_plan_id,
        service_date=SERVICE_DATE,
        account=facts,
        premises=premises,
    )
    if past_r4:
        catalogue = resolution.replace(
            catalogue,
            charge_codes=tuple(
                code
                for code in catalogue.charge_codes
                if code.flat_amount is not None or code.amounts
            ),
        )
    meters = tuple(
        resolution.MeterFacts(
            service=service,
            connection_size=size,
            multiplier=multipliers[service],
        )
        for service, size in sizes.items()
    )
    return resolution.resolve(
        catalogue=catalogue,
        account=facts,
        premises=premises,
        meters=meters,
        quantities=dict(register_deltas),
        service_date=SERVICE_DATE,
    )


def _compare(data, resolved) -> list[Divergence]:
    """Every step, both figures. The function the whole file exists for.

    ⚠ **AN EMPTY COMPARISON IS A FAILURE, NOT A PASS.** A parity checker that
    compares nothing returns no divergences and reads as green — which is the
    single way this file could tell a comfortable lie, and it very nearly did:
    `make_plan` writes no `plan_services` row, so `PlanVersion.services` came
    back empty, the per-service loop never ran once, and the headline test
    reported PARITY over zero services compared. It is asserted here rather than
    in each test so no future case can be written without the guard.
    """
    if not resolved.services:
        raise AssertionError(
            "the chain resolved ZERO services, so this comparison compared nothing. "
            "A parity harness that measures nothing reports parity — fix the fixture, "
            "never the assertion."
        )
    if not data.tariffs:
        raise AssertionError(
            "the live path resolved ZERO tariffs, so this comparison compared nothing."
        )
    found: list[Divergence] = []

    # ── R1 · the plan version ────────────────────────────────────────────
    if str(data.rate_plan_id) != str(resolved.plan.plan_id):
        found.append(
            Divergence("R1", "-", data.rate_plan_id, resolved.plan.plan_id, "plan version")
        )

    live_by_service = {config.service: config for config in data.tariffs}
    for service_resolution in resolved.services:
        service = service_resolution.service
        config = live_by_service.get(service)
        if config is None:
            found.append(
                Divergence(
                    "R2",
                    service,
                    None,
                    service_resolution.schedule_version_id,
                    "the live path resolved no tariff for this service",
                )
            )
            continue
        # ── R2 · the schedule VERSION in force at the service date ───────
        if str(config.version_id) != str(service_resolution.schedule_version_id):
            found.append(
                Divergence("R2", service, config.version_id, service_resolution.schedule_version_id)
            )
        # ── R3 / BR-RAT-088 · the base charge, and WHO supplied it ───────
        if _dec(config.base_charge) != _dec(service_resolution.base_charge):
            found.append(
                Divergence(
                    "R3/R4",
                    service,
                    config.base_charge,
                    service_resolution.base_charge,
                    f"base_source={service_resolution.base_source}",
                )
            )
    return found


def _dec(value):
    return None if value is None else Decimal(str(value))


def _seeded_priced_total() -> Decimal:
    """What the provisioning fixture's PRICED charge codes add up to.

    ⚠ **READ FROM THE FIXTURE, NEVER TYPED — `DEF-RAT-6980`.** The figure this
    replaced was `Decimal("799.95")`, correct when it was measured and wrong
    from 2026-09-21, when `OQ-CUS-12518` took `RECON` from `$45.00` to
    `$75.00` on the PO's own words (*"reconnection fee is $75 - fix the code
    and seed"*). The test then sat RED for six days in a suite nobody runs
    whole, and the next reader's cheapest move was to type `829.95` over it —
    which is how a figure nobody has checked becomes the signed one.

    The reading lives in `tests/seeded_charge_codes.py` because the SAME
    constant was typed into `test_def_498_def_493_charge_code_recurrence.py`
    too, and two copies of a stale number is how one of them gets quietly
    "fixed" to disagree with the other.
    """
    from tests.seeded_charge_codes import seeded_priced_total

    return seeded_priced_total()


# ══════════════════════════════════════════════════════════════════════════
# R3b — THE ONE THAT WOULD MEAN A LIVE BILL IS WRONG
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("multiplier", ["1", "10"])
def test_r3b_the_chain_reproduces_metering_s_quantity_exactly(brazos, dana, multiplier):
    """R3b PARITY: `billable_quantity(register delta)` == metering's stored figure.

    **This is the assertion that proves the duplicate is harmless AND that the
    order is right.** Metering already applies the multiplier (BR-MET-019); the
    chain applies it to the register difference (BR-RAT-001). Given the same
    two facts the two must land on the same Decimal, and on a ×10 register that
    Decimal is ten times the raw difference — 50 kgal of register becomes
    **500**, which is a different tier band, not merely a bigger number.

    A failure here means one of the two implementations of R3b has moved and a
    real customer's usage is being scaled wrongly.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        account, _unit, _asset, register_delta = _account_on(
            brazos, dana, plan, multiplier=multiplier
        )
        rows = _readings_for(account)
        metering_quantity = rows[0].consumption.amount

        chain_quantity = resolution.billable_quantity(
            resolution.MeterFacts(
                service="water", connection_size="5/8", multiplier=Decimal(multiplier)
            ),
            register_delta,
        )

        assert chain_quantity == metering_quantity, (
            f"R3b [water]: metering stored {metering_quantity} and the chain resolved "
            f"{chain_quantity} from a register delta of {register_delta} × {multiplier}. "
            "One of the two implementations of BR-RAT-001 has moved."
        )
        assert chain_quantity == register_delta * Decimal(multiplier)


def test_r3b_feeding_the_chain_the_stored_consumption_would_bill_100x(brazos, dana):
    """THE TRAP, ASSERTED — so nobody wires R3b the obvious wrong way.

    A lane cutting billing over to the chain has one shape of the mistake
    available: hand `billable_quantity` the quantity billing already holds. That
    quantity is post-multiplier. On a ×10 register the result is **100×** the
    customer's real usage, every line individually well-formed.

    This test exists so that the wrong wiring fails HERE, in a test named for
    it, rather than on a document.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        account, _unit, _asset, register_delta = _account_on(brazos, dana, plan, multiplier="10")
        stored = _readings_for(account)[0].consumption.amount

        correct = resolution.billable_quantity(
            resolution.MeterFacts("water", "5/8", Decimal("10")), register_delta
        )
        wrong = resolution.billable_quantity(
            resolution.MeterFacts("water", "5/8", Decimal("10")), stored
        )

        assert correct == Decimal("500")
        assert wrong == Decimal("5000")
        assert wrong == correct * 10, (
            "the double-multiplied figure must be exactly 10× the right one on a ×10 "
            "register — if this ratio changes, the fixture stopped exercising the trap"
        )


def test_r3b_an_unstated_multiplier_refuses_rather_than_defaulting_to_one(brazos):
    """BR-MET-056's absence, and it must never be read as 1.

    A ×10 register whose multiplier nobody recorded bills a TENTH of the
    customer's consumption on a document that looks entirely normal. The chain
    refuses; this asserts the refusal survives any cutover.
    """
    with pytest.raises(resolution.MeterMultiplierUnstated):
        resolution.billable_quantity(resolution.MeterFacts("water", "5/8", None), Decimal("50"))


# ══════════════════════════════════════════════════════════════════════════
# R1 / R2 — where the two paths meet, and where they do not
# ══════════════════════════════════════════════════════════════════════════


def test_r2_both_paths_resolve_the_same_schedule_version(brazos, dana):
    """R2 PARITY, GREEN — and this is the step a cutover may take first.

    `gather._tariff_config_for` resolves the version through
    `rating.selectors.pricing_inputs(tariff, service_date)`; the chain resolves
    it through `resolve_schedule` over `tariff_versions` narrowed by
    `in_force_on`. Two different code paths, one answer — which is what makes
    flipping R2 provable rather than hopeful.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        account, _unit, _asset, delta = _account_on(brazos, dana, plan)
        data = _price_live(account)
        resolved = _price_chain(
            account,
            sizes={"water": "5/8"},
            register_deltas={"water": delta},
            multipliers={"water": Decimal("1")},
            past_r4=True,
        )
        live_version = data.tariffs[0].version_id
        chain_version = resolved.services[0].schedule_version_id
        assert str(live_version) == str(
            chain_version
        ), f"R2 [water]: live={live_version} chain={chain_version}"


def test_r1_a_published_plan_with_no_dates_diverges_and_the_harness_names_it(brazos, dana):
    """R1 DIVERGENCE, MEASURED — the two paths mean different things by *in force*.

    `rating.selectors.plan_ref` — what the bill run reads — filters on
    `status="published"` and consults **no date at all**, so a plan whose
    `effective_from` nobody typed bills forever. `resolution.PlanVersion
    .in_force_on` requires a stated start date, so the same plan is in force
    **never** and R1 refuses.

    Both are defensible readings of BR-RAT-007 and the rule does not choose
    between them, so this test CHOOSES NEITHER. It pins the divergence with the
    two behaviours side by side, which is what makes it a finding a human can
    rule on rather than an opinion a lane acted on.

    ⚠ **IT STATES THE SWITCH STATE FROM 2026-09-01, AND THE REASON IS ITSELF A
    FINDING (`DEF-2815`).** A divergence between two implementations can only be
    observed while both are running. Since the PO ruled R3 + R4 on (`CR-057`)
    there is only ONE path for a served step — and, worse than that,
    `resolution_switch.apply` runs the chain END TO END before substituting
    anything, so **a refusal at R1 stops the live bill even though R1 is not
    switched on.** With the pair on, `_price_live` here raises R1's
    `NoPlanInForce` through `gather` and the sentence *"the LIVE path bills
    it"* is simply no longer true.

    So the case is run with nothing switched on, which is the state it has
    always been describing and never had to say. The divergence itself is
    unchanged and still unruled: `DEF-438` stands, and a deployment that types
    the one-line rollback (`SBH_BILLING_RESOLUTION_STEPS=` emptied) is exactly
    the world this case measures.
    """
    with override_settings(BILLING_RESOLUTION_STEPS=""), tenant_ctx(brazos):
        plan = _water_plan(brazos, dated=False)
        assert plan.effective_from is None, (
            "the fixture must reproduce the shipped shape: no seeded plan carries "
            "effective dates"
        )
        account, _unit, _asset, delta = _account_on(brazos, dana, plan)

        # The LIVE path bills it — with nothing switched on. See the docstring:
        # with the pair ON it does not, and that is DEF-2815 rather than this
        # divergence.
        data = _price_live(account)
        assert str(data.rate_plan_id) == str(plan.id)

        # The CHAIN refuses it, by name, at R1.
        with pytest.raises(resolution.NoPlanInForce) as refusal:
            _price_chain(
                account,
                sizes={"water": "5/8"},
                register_deltas={"water": delta},
                multipliers={"water": Decimal("1")},
            )
        assert "R1" in str(refusal.value)


def test_r1_parity_holds_once_the_plan_states_its_dates(brazos, dana):
    """R1 PARITY, GREEN — with dates typed, the two agree.

    Which localises the divergence above precisely: it is not that the two
    resolve different plans, it is that one of them treats an ABSENT date as
    *forever* and the other as *never*. Every other input is identical.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        account, _unit, _asset, delta = _account_on(brazos, dana, plan)
        data = _price_live(account)
        resolved = _price_chain(
            account,
            sizes={"water": "5/8"},
            register_deltas={"water": delta},
            multipliers={"water": Decimal("1")},
            past_r4=True,
        )
        assert str(data.rate_plan_id) == str(resolved.plan.plan_id)
        assert _compare(data, resolved) == [], _report(_compare(data, resolved))


# ══════════════════════════════════════════════════════════════════════════
# R4 — ABSENT from the live path entirely
# ══════════════════════════════════════════════════════════════════════════


def test_r4_the_live_path_resolves_no_charge_codes_at_all(brazos, dana):
    """R4 IS NOT DIFFERENT — IT DOES NOT RUN.

    `apps/billing/gather.py` builds `AccountBillingData` from tariffs, taxes and
    a snapshot, and the string `charge` appears in it only as `base_charge`.
    There is no per-account charge-code resolution anywhere on the path an
    invoice is produced by, so BR-RAT-088's base-by-charge-code, BR-RAT-108's
    customer-class narrowing and CR-013 part 2's per-size amounts are all
    enforced nowhere a customer can reach.

    Asserted as a property of the CONTRACT rather than by grepping source, so it
    goes red the moment somebody adds the field — which is the day this test
    should be re-read.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
        data = _price_live(account)
        assert not hasattr(data, "charge_codes"), (
            "AccountBillingData has gained a charge-code field — R4 may now be "
            "comparable and this test is the one to update (DEF-438)"
        )


def test_r4_ON_A_REAL_TENANT_NO_LONGER_REFUSES_AND_NO_LONGER_BILLS_THE_PRICE_LIST(brazos, dana):
    """⚠ **THE HEADLINE FINDING OF THIS HARNESS, AND ITS CLOSURE.**

    **THIS TEST USED TO ASSERT THE OPPOSITE, AND THE TWO FIGURES IT NOW PINS ARE
    WHY R4 COULD NOT BE FLIPPED** (`DEF-498` + `DEF-493`, closed 2026-08-28).
    Every tenant is provisioned with `lookup_defaults.json`'s charge-code
    catalogue — **23 codes on this fixture** — and R4 narrowed them by exactly
    three things: service, customer class and connection size.

    **IT BROKE IN TWO WAYS AT ONCE AND THE FIRST HID THE SECOND.**

    **(1) FIVE CODES REFUSED THE WHOLE BILL, EACH INDEPENDENTLY.** `LATE`,
    `TAP`, `IMPACT`, `DAMAGE` and `BULK-WATER` carry **no `amount`** — `LATE` is
    `percent_with_minimum` 1.5% / $5.00 (BR-BIL-001's *max($5, 1.5% × overdue)*)
    and the other four are `pricing: per_case`. `ChargeCode` had `flat_amount`
    and a per-size `amounts` table and nothing else, so all four of
    `charges.amount_rule`'s rules were inexpressible, and the refusal blamed the
    connection size:

        R4: charge code 'LATE' applies to this account and states no amount for
        connection size None on service None.

    **(2) IF THEY HAD BEEN PRICED, THE OTHER 18 WOULD HAVE LANDED ON EVERY
    BILL** — a `$250.00` tamper fee, a `$45.00` connection fee, a `$30.00` NSF
    fee and fifteen more, **`$829.95` summed from the tenant's own rows, added
    to a bill whose base is `$8.00`.**

    ⚠ **THAT TOTAL READ `$799.95` UNTIL 2026-09-27 AND IT WAS A CONSTANT, NOT A
    MEASUREMENT — `DEF-RAT-6980`.** It was measured correctly the day it was
    written and then the PO repriced one of the eighteen: `OQ-CUS-12518`,
    CLOSED 2026-09-21, PO verbatim *"reconnection fee is $75 - fix the code and
    seed"*, over `BR-CUS-104` which the PO had already SIGNED on `$75.00` on
    2026-08-25. `RECON` moved from `$45.00` to `$75.00` in
    `apps/tenancy/fixtures/lookup_defaults.json`, and `rating/0042` moved it on
    every tenant already provisioned at exactly `45.000000`. **`$829.95 −
    $799.95 = $30.00`, which is that one repricing and nothing else** — the
    count is 18 on both sides of the ruling and no code was added or removed.
    **So the DATA was right and this number was stale**, and the arithmetic is
    recorded here rather than left to be re-derived by the next lane that meets
    a red assertion and is tempted to type whatever the failure printed.

    ⚠ **AND IT IS NO LONGER A CONSTANT, WHICH IS THE POINT.** The expected
    total is summed from the same fixture rows the tenant is provisioned FROM,
    so the next PO repricing cannot make this red — while the eighteen-code
    COUNT and `RECON`'s own ruled `$75.00` are still pinned by name, so a code
    silently appearing, vanishing or being repriced by a lane rather than by a
    ruling still is. A test whose expected value is a number somebody typed is
    a test that goes stale the first time the product is right.

    **WHAT THIS ASSERTS NOW, and both numbers are measured off the same rows:**

    * **0 of 23 refuse.** Not because the amounts appeared — `charge_code_facts`
      returns the same five unpriced codes it always did — but because
      `BR-RAT-730` asks *does this code ride a periodic bill* BEFORE it asks
      *what does it cost*, and every one of the five is `one_time` or `penalty`.
      A code with a different trigger is not an error.
    * **0 of the 18 priced codes ride, and they add `$0.00`.** No code on this
      tenant is both `recurring` and `auto_apply`, and none declares `is_base`.

    ⚠ **`$0.00` IS THE HONEST ANSWER AND IT IS NOT SILENCE.** `BR-RAT-117` (PO
    2026-08-22) already priced this direction — a fee the tenant has not ticked
    bills nothing, and a `$12.00` recurring auto-apply fee across 1,247
    connections is the `$14,964.00` a month that ruling exists to unlock. The
    utility declares it on the charge-code wizard; nothing here guesses on their
    behalf.

    **NOTHING IS SWITCHED ON.** R4 still has no production caller and no bill
    changes — see `test_br_rat_120_size_refusal.py::TC6`.
    """
    with tenant_ctx(brazos):
        # ⚠ **`base_code=False` FROM 2026-09-28 (`DEF-BIL-7170`), AND IT IS THE
        # ONE PLACE IN THIS FILE THAT NEEDS IT.** `_water_plan` now mints an
        # `is_base` water code, because the PO retired the plan's own figure and
        # a plan without one cannot bill. **This case counts the catalogue the
        # TENANT WAS PROVISIONED WITH** — 23 codes from `lookup_defaults.json`,
        # and the sentence below asserts *"none declares `is_base`"* — so a code
        # this fixture minted would be counted as one the utility configured.
        # The case never prices a base: it asks what R4 narrows and what rides.
        plan = _water_plan(brazos, base_code=False)
        account, _unit, _asset, delta = _account_on(brazos, dana, plan)

        catalogue = resolution_catalogue.charge_code_facts()
        assert len(catalogue) == 23, len(catalogue)

        # (1) — the five that used to stop the bill are still UNPRICED on the
        # table, and the chain no longer refuses on them.
        unpriced = sorted(
            code.code for code in catalogue if code.flat_amount is None and not code.amounts
        )
        assert unpriced == ["BULK-WATER", "DAMAGE", "IMPACT", "LATE", "TAP"], unpriced

        resolved = _price_chain(
            account,
            sizes={"water": "5/8"},
            register_deltas={"water": delta},
            multipliers={"water": Decimal("1")},
        )

        # (2) — and the priced remainder does NOT ride.
        priced = [code for code in catalogue if code.flat_amount is not None]
        priced_total = sum((code.flat_amount for code in priced), Decimal("0"))
        assert len(priced) == 18, len(priced)
        # DEF-RAT-6980 — summed from the fixture this tenant was provisioned
        # FROM, never re-typed, so a PO repricing moves both sides together.
        # `$829.95` today; it was `$799.95` until `OQ-CUS-12518` took `RECON`
        # from `$45.00` to `$75.00` on 2026-09-21.
        assert priced_total == _seeded_priced_total(), (
            f"the catalogue totals {priced_total} and the seed fixture totals "
            f"{_seeded_priced_total()} — one of them was edited without the other"
        )
        # ...and the ruled figure is pinned BY NAME, because a total that
        # derives itself cannot notice a repricing (OQ-CUS-12518, PO 2026-09-21:
        # "reconnection fee is $75 - fix the code and seed"; BR-CUS-104 signed
        # $75.00 on 2026-08-25). A lane moving this one needs a ruling.
        recon = next(code for code in catalogue if code.code == "RECON")
        assert recon.flat_amount == Decimal("75.0000"), recon.flat_amount

        riding = sum((amount for _code, amount in resolved.charge_codes), Decimal("0"))
        assert resolved.charge_codes == (), (
            f"R4 [bill]: {len(resolved.charge_codes)} code(s) worth {riding} ride this "
            f"tenant's monthly bill. {len(priced)} priced codes totalling {priced_total} "
            f"exist and NONE is both recurring and auto-apply, so the answer is 0 and "
            f"{Decimal('0.00')} — anything else is DEF-493 reopening"
        )
        assert riding == Decimal("0")


def test_r4_narrows_by_service_class_and_size_and_by_nothing_else(brazos, dana):
    """THE MECHANISM behind the test above, pinned so a fix is visible.

    `resolve_charge_codes` is a pure function; this asserts its narrowing set
    directly rather than through a bill, so the day `charge_type` or
    `auto_apply` joins it this test goes RED and names what changed.

    A one-time `$45.00` connection fee and a recurring `$2.00` paper-bill fee
    used to be indistinguishable to it: both are service-`None`,
    class-unrestricted codes with a flat amount, and both resolved. On a monthly
    bill exactly one of them belongs, and **since `BR-RAT-730` exactly one does.**

    ⚠ **THE ASSERTION IS INVERTED FROM WHAT IT SAID UNTIL 2026-08-28**, which is
    the point: it named the narrowing set as *exactly three* and promised to go
    RED the day a fourth arrived. It did, and this is that day.
    """
    account = resolution.AccountFacts(account_no="A-1", unit_id="u-1", customer_class="residential")
    catalogue = resolution.Catalogue(
        charge_codes=(
            # The utility's own two declarations, on the two columns the
            # charge-code wizard has always written.
            resolution.ChargeCode(
                code="CONN", charge_type="one_time", flat_amount=Decimal("45.00")
            ),
            resolution.ChargeCode(
                code="PAPER",
                charge_type="recurring",
                auto_apply=True,
                flat_amount=Decimal("2.00"),
            ),
        )
    )
    resolved = resolution.resolve_charge_codes(catalogue, account, ("water",), {"water": "5/8"})
    assert sorted(code.code for code, _amount in resolved) == ["PAPER"], (
        "R4 narrows by service, class, size AND recurrence (BR-RAT-730). A "
        "one-time $45.00 connection fee riding a monthly bill is DEF-493 reopening"
    )


# ══════════════════════════════════════════════════════════════════════════
# R5 — stored, resolvable, and never applied to money on either path
# ══════════════════════════════════════════════════════════════════════════


def test_r5_both_paths_agree_only_because_the_factor_can_never_be_set(brazos, dana):
    """R5 PARITY ON THE SHIPPED TENANT — and it is still an agreement AT `1`.

    ⚠ **THIS DOCSTRING SAID SOMETHING THAT STOPPED BEING TRUE ON 2026-08-21, and
    the correction is the useful part (hard-won law 1).** It read *"`gather
    ._tariff_config_for` never sets it, so it is `1` on every bill"* and
    *"nothing at any layer of this product can set it"*. `gather` sets it now:
    `_jurisdiction_factor_for` applies BR-RAT-102's two gates per service and
    `_tariff_config_for` puts the answer on `TariffConfig.jurisdiction_factor`,
    so **the live path implements R5** and `test_r5_parity_holds_when_the_plan
    _states_a_factor` below compares the two on a plan that states one.

    What has NOT changed is why this particular fixture agrees: its plan carries
    no factor, so `money_factor` short-circuits to `1` and the premises is never
    consulted, exactly as the live path does. That is the SHIPPED state of every
    plan of every tenant — nothing writes `rate_plans.outside_city_factor`
    (DEF-515) and nothing writes `premises.inside_city_limits` (DEF-517) — so a
    harness that only reported "R5: match" would still be telling a comfortable
    lie, and the `stored is None` assertion below is what keeps it honest.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        account, _unit, _asset, delta = _account_on(brazos, dana, plan)
        resolved = _price_chain(
            account,
            sizes={"water": "5/8"},
            register_deltas={"water": delta},
            multipliers={"water": Decimal("1")},
            past_r4=True,
        )
        assert resolved.services[0].money_factor == Decimal("1")
        stored = rating_models.RatePlan.objects.get(pk=plan.id).outside_city_factor
        assert stored is None, (
            "rate_plans.outside_city_factor is no longer NULL — DEF-466 may be fixed, "
            "and R5 parity must then be re-proved rather than assumed"
        )
        # And the LIVE path agrees, for the same reason and not by accident.
        assert _price_live(account).tariffs[0].jurisdiction_factor == Decimal("1")


@pytest.mark.parametrize("inside,expected", [(False, "1.15"), (True, "1")])
def test_r5_parity_holds_when_the_plan_states_a_factor(brazos, dana, inside, expected):
    """R5 PARITY, GREEN — on the case that could not be measured until today.

    The step above compares the two paths where BOTH short-circuit, which proves
    only that neither surcharges when nobody asked for one. This drives the case
    the rule is actually about: a plan stating `1.15` (BR-RAT-102's own figure)
    over a premises that IS on one side of the line.

    Two implementations of R5 exist on purpose — `resolution.money_factor` is
    the chain's and `gather._jurisdiction_factor_for` is the live path's — for
    the reason this whole file exists: billing may not import rating's modules
    (B1) and the chain has no production caller (DEF-438). So they are compared,
    step by step, rather than trusted to have been written the same way.

    ⚠ The factor and the flag are written through the ORM because **nothing in
    the product can write either** (DEF-515, DEF-517). That is the gap those two
    rows record, and it is the reason this test can exist at all.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        rating_models.RatePlan.objects.filter(pk=plan.id).update(
            outside_city_factor=Decimal("1.15")
        )
        account, unit, _asset, delta = _account_on(brazos, dana, plan)
        metering_models.Premises.objects.filter(pk=unit["premises_id"]).update(
            inside_city_limits=inside
        )

        live = _price_live(account).tariffs[0].jurisdiction_factor
        resolved = _price_chain(
            account,
            sizes={"water": "5/8"},
            register_deltas={"water": delta},
            multipliers={"water": Decimal("1")},
            past_r4=True,
        )
        chain = resolved.services[0].money_factor

    assert (
        live == chain == Decimal(expected)
    ), f"R5 [water]: live={live} chain={chain} for inside_city_limits={inside}"


def test_r5_both_paths_refuse_a_surcharging_plan_over_an_unstated_premises(brazos, dana):
    """R5's REFUSAL, on both paths, on the state every seeded premises is in.

    BR-RAT-102: *"a plan stating a factor over a premises whose flag is `None`
    STOPS THE BILL"*. The chain raises `JurisdictionUnstated`; the live path
    raises a reason-coded `GatherProblem` so `runs.prepare_run` can block ONE
    account and carry on (BR-BIL-055). **Different exception types, same
    decision** — and that difference is deliberate rather than a divergence: an
    exception the bill run can group on is billing's contract, and the chain is
    pure.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        rating_models.RatePlan.objects.filter(pk=plan.id).update(
            outside_city_factor=Decimal("1.15")
        )
        account, unit, _asset, delta = _account_on(brazos, dana, plan)
        assert (
            metering_models.Premises.objects.get(pk=unit["premises_id"]).inside_city_limits is None
        ), "the fixture must reproduce the shipped shape: no premises carries the flag"

        with pytest.raises(resolution.JurisdictionUnstated):
            _price_chain(
                account,
                sizes={"water": "5/8"},
                register_deltas={"water": delta},
                multipliers={"water": Decimal("1")},
                past_r4=True,
            )
        with pytest.raises(gather.GatherProblem) as refusal:
            _price_live(account)
    assert refusal.value.reason == gather.GATHER_JURISDICTION_UNSTATED


# ══════════════════════════════════════════════════════════════════════════
# R7 — both paths run it, through the SAME selector
# ══════════════════════════════════════════════════════════════════════════


def test_r6_both_paths_grant_the_same_discounts(brazos, dana):
    """R6 PARITY, GREEN SINCE 2026-08-22 (DEF-502) — and this file's own
    trailer said R6 was *"compared as an ABSENCE"* because the live path did
    not run it. It runs now: `gather` reads `rating.selectors
    .billable_discount_rules` (enrolment ∩ plan binding, BR-RAT-069/110), and
    the chain's `resolve_discounts` narrows the same enrolments against the
    same catalogue. This test holds the two to ONE answer on the case where
    they could diverge: an account enrolled in TWO discounts, only one of
    which the plan binds.

    Both paths must grant SENIOR (bound + enrolled) and drop CAP (enrolled,
    unbound) — the drop is BR-RAT-069's *"plan attachment makes a discount
    available, not granted"* read from the other end, and reading it any other
    way is a 15% revenue error on every account of the plan (BR-RAT-110's own
    worked figure).
    """
    from apps.rating import discounts as discount_models

    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        account, _unit, _asset, delta = _account_on(brazos, dana, plan)
        for code, name, bind in (
            ("SENIOR", "Senior citizen discount", True),
            ("CAP", "Customer assistance program", False),
        ):
            discount = discount_models.Discount.objects.create(
                tenant=brazos, code=code, name=name, status=discount_models.DISCOUNT_ACTIVE
            )
            discount_models.DiscountVersion.objects.create(
                tenant=brazos,
                discount=discount,
                version_no=1,
                status=discount_models.VERSION_ACTIVE,
                discount_type=discount_models.DISCOUNT_PERCENTAGE,
                value=Decimal("15"),
                currency="USD",
                applies_to=discount_models.SCOPE_WHOLE_BILL,
                effective_from=date(2026, 1, 1),
            )
            if bind:
                discount_models.PlanDiscountRule.objects.create(
                    tenant=brazos, rate_plan_id=plan.id, discount=discount
                )
            discount_models.DiscountEnrolment.objects.create(
                tenant=brazos,
                discount=discount,
                account=account,
                enrolled_on=date(2026, 6, 1),
                verification_status=discount_models.VERIFICATION_VERIFIED,
            )

        data = _price_live(account)
        resolved = _price_chain(
            account,
            sizes={"water": "5/8"},
            register_deltas={"water": delta},
            multipliers={"water": Decimal("1")},
            past_r4=True,
            enrolments=("SENIOR", "CAP"),
        )
        live = sorted((d.code, _dec(d.value)) for d in data.discounts)
        chain = sorted((code, _dec(value)) for code, value in resolved.discounts.applied)
        assert live == chain, f"R6 [bill]: live={live} chain={chain}"
        assert live == [("SENIOR", Decimal("15"))]


def test_r7_both_paths_attach_the_same_taxes(brazos, dana):
    """R7 PARITY, GREEN — and green for a good reason rather than by luck.

    Both paths read `rating.selectors.plan_tax_rules`, so they cannot disagree
    about WHICH taxes exist. What they could disagree about is the narrowing.

    ⚠ **THIS DOCSTRING USED TO SAY THEY DO NOT, AND FOR A YEAR THEY DID
    (`DEF-2824`, 2026-08-31).** It read: *"the selector applies the
    customer-class and premises gates (DEF-273) and `resolve_taxes` applies the
    service gate over the result … the adapter passes NO customer classes onto
    `TaxRule` precisely so the narrowing happens ONCE."* The selector applied
    NOTHING: `tax_facts` called it with no class, no premises and no service
    list, all three restrictions fail closed, and every restricted tax was
    dropped from every ruled bill. **This test stayed green throughout**, because
    `_account_on` gives its account `AccountType.objects.first()` and the seeded
    class-restricted tax then falls out of BOTH paths — the same answer for two
    different reasons, which is the one thing a parity harness cannot see.

    It is green now for the reason it always claimed: `tax_facts` passes the
    facts, and `tests/test_def2824_tax_narrowing_facts.py` is where the
    class-restricted case is asserted on purpose rather than by fixture luck.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        account, _unit, _asset, delta = _account_on(brazos, dana, plan)
        data = _price_live(account)
        resolved = _price_chain(
            account,
            sizes={"water": "5/8"},
            register_deltas={"water": delta},
            multipliers={"water": Decimal("1")},
            past_r4=True,
        )
        live_ids = sorted(str(t.tax_id) for t in data.taxes if getattr(t, "tax_id", None))
        chain_ids = sorted(str(t.tax_id) for t in resolved.taxes if t.tax_id)
        assert live_ids == chain_ids, f"R7 [bill]: live={live_ids} chain={chain_ids}"


# ══════════════════════════════════════════════════════════════════════════
# The whole-account report
# ══════════════════════════════════════════════════════════════════════════


def test_the_full_chain_agrees_with_the_live_path_on_a_dated_plan(brazos, dana):
    """THE HEADLINE: with the one precondition met, every comparable step agrees.

    "Comparable" is doing real work in that sentence and is not a hedge: R4 has
    no live-path counterpart to compare AGAINST (it does not run), and
    `_compare` therefore reports on R1, R2 and the base charge — the steps where
    both paths produce a value. (R6 stopped being an absence on 2026-08-22 —
    DEF-502 — and has its own value-for-value comparison above,
    `test_r6_both_paths_grant_the_same_discounts`.)

    A green here is the permission to flip R1, R2 and the base source. It is not
    permission to flip R3, R4 or R5, and the tests above say why for each.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        account, _unit, _asset, delta = _account_on(brazos, dana, plan)
        data = _price_live(account)
        resolved = _price_chain(
            account,
            sizes={"water": "5/8"},
            register_deltas={"water": delta},
            multipliers={"water": Decimal("1")},
            past_r4=True,
        )
        divergences = _compare(data, resolved)
        assert divergences == [], "PARITY FAILURES:\n" + _report(divergences)

        # And the base is the fixture's own figure on BOTH paths, not zero —
        # DEF-154's regression, asserted from both directions at once.
        assert _dec(data.tariffs[0].base_charge) == WATER_BASE
        assert _dec(resolved.services[0].base_charge) == WATER_BASE


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-438 + CR-013 §A2 + `apps/rating/resolution.py` +
#         `apps/billing/gather.py` + BR-RAT-001/007/030/088 + BR-MET-019/056
# generated: 2026-08-21 by the DEF-438 Wave A cutover lane
# checklist: A✔ B✔ C✔ D=n/a(no API half) E=n/a(no frontend half) F✔ G✔
#         H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · 10-scripts/03-golden-verify.py 33 PASS / 0 FAIL✔ ·
#         tests/golden unchanged✔
# exceptions: R4 is compared as an ABSENCE, not as a figure, because the live
#         path does not run it — there is no counterpart to be equal to.
#         Stated in the test rather than silently skipped. ⚠ R6 CAME OFF THIS
#         LINE ON 2026-08-22 (DEF-502): the live path now gathers discounts
#         through `rating.selectors.billable_discount_rules` and
#         `test_r6_both_paths_grant_the_same_discounts` compares the two paths
#         value for value, including the enrolled-but-unbound drop
#         (BR-RAT-069/110).
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
