# ── Trace ──────────────────────────────────────────────
# Change:   **CR-063 task C3** (the seeded fire tariff) and **task C5** (the
#           demo warehouse: one 6" line and two private hydrants).
#           **AMENDED 2026-09-03** — PO: *"remove private hydrants from list"*.
#           `HYD` is withdrawn, so the warehouse bills **$60.00** on ONE line
#           rather than $110.00 on two, and the per-size grouping that C5
#           exists to prove is carried by tc2b (a 6" line and two 2" lines,
#           $84.00) instead. Fire's ladder goes 7 -> 6.
# Defect:   **DEF-3093** — a fire property carrying two different sizes could
#           not be billed at all: `metering.connection_size_for` answered
#           `None` for it BY DESIGN and the run refused the unit.
# Rules:    **BR-RAT-090** (a capacity service's quantity is a COUNT of its
#           assets — and, for the COUNTING pair trash and fire, a count PER
#           SIZE, one bill line each: decision log 2026-09-02) · BR-RAT-120 (an
#           unpriced size is REFUSED, never substituted) · BR-MET-108 (the
#           ruled zero: the utility looked and there is nothing) · BR-AST-500
#           (the size lives on the DEVICE) · CLAUDE.md rule 3 (a quantity
#           always carries its unit) · CLAUDE.md rule 2 (money stored to 4,
#           displayed to 2)
# Tests:    this file
# Impacts:  apps/rating/sample_data.fire_schedule_payload ·
#           apps/billing/gather · apps/billing/stages/measure_consumption ·
#           apps/metering/selectors.billable_asset_size_counts
# ───────────────────────────────────────────────────────
"""**A FIRE CUSTOMER IS BILLED REAL MONEY, AND A MIXED PROPERTY BILLS TWO LINES.**

`CR-063` shipped fire end to end and the line on the document read **`$0.00`**.
The real prices existed — `service_size_classes.FIRE_DEFAULT_PRICES`, and
`fire_charge()` computed `$12.00` and `$110.00` from them — and **nothing in the
product called any of it**. That is hard-won law 2 (*built is not wired*) on a
money path: every test was green, the bill footed and printed, and the customer
was charged nothing.

⚠ **AND ONE OF THOSE TWO FIGURES WAS SUPERSEDED THE DAY AFTER IT WAS SIGNED.**
PO 2026-09-03, verbatim: *"remove private hydrants from list"*. `HYD` "Private
hydrant" at `$25.0000` has left fire's size list — a hydrant is an ASSET, not a
utility-service size — so **the warehouse that billed `$110.00` on two lines
now bills `$60.00` on one**: `−$50.00` a month on that customer. Nothing was
wrong with the arithmetic; the PO decided a hydrant is not a thing this product
bills as a utility service. **Nothing already issued is rewritten** (hard rule
4); the seeded tariff is re-seeded, never amended.

**THE FIGURES THIS FILE PROVES REACH A REAL BILL:**

  * one **2" fire line**              → `1 × $12.0000`             = **`$12.00`**
  * the **warehouse's 6" line**       → `1 × $60.0000`             = **`$60.00`**
    on **ONE LINE**, its two hydrants equipment on file rather than money.
  * one **6" line + two 2" lines**    → `1 × $60.00 + 2 × $12.00`  = **`$84.00`**
    on **ONE LINE** of 3 connections since 2026-09-30 (PO *"per service"*,
    `DEF-BIL-8151`; it read *"on TWO LINES, `$60.00` and `$24.00`, never one
    blended line"* until then — the AMOUNT never moved, each size is still
    priced at its own price, and the line's wording names both sizes).

⚠ **THE THIRD CASE IS THE ONE THE HYDRANT WAREHOUSE USED TO CARRY, AND IT IS
HERE ON PURPOSE.** The ruling removed a PRICE ROW; it did not remove the
per-size arithmetic, which is `CR-063` C5's whole subject and a 🔒 rating-math
path. Deleting tc2's two-line assertion and calling the job done would have
dropped that coverage silently, on the one code path where a wrong answer is a
plausible number on a real invoice.

**RED PROOF FOR THE 2026-09-03 WITHDRAWAL (law 7), MEASURED on PostgreSQL 16
with the six-band list in place and this file still asserting seven.** The
warehouse case failed on the figure itself, before it was rewritten:

    tc2  AssertionError: assert [Decimal('0.0...('60.000000')] == [Decimal('50....
         At index 0 diff: Decimal('0.000000') != Decimal('50.00')

and the price-list case failed by name, which is the refusal working:

    KeyError: "'HYD' is not a fire size class (FL-2, FL-4, FL-6, FL-8, FL-10,
    FL-12). A code this list does not hold is a typo, and skipping it would
    bill a fire line at nothing."

**RED PROOF FOR THE ORIGINAL C3/C5 BUILD (r11 step 2d), MEASURED on PostgreSQL
16 before a line was changed.** Eleven of the twelve cases failed and the two
that matter read:

    tc1  AssertionError: assert Decimal('0.000000') == Decimal('12.00')
    tc2  two sizes on the unit is two lines, got
         ['base  | fire | fire base charge | None None          | 0.000000',
          'usage | fire | fire usage      | 3.000000 connection | 0.000000']

⚠ **AND `tc2`'S RED IS NOT THE ONE `DEF-3093` PREDICTED, WHICH IS WORTH THE INK.**
That row expected the warehouse to be REFUSED — `connection_size_unresolved_for_
sized_schedule`, two recorded sizes on one connection. It was not refused: it
BILLED, as a single blended line of **three connections at `$0.00`**. The refusal
was never armed because the seeded fire schedule carried no per-size prices, so
`gather` had no `size_groups` to demand a size for. **The two failures compound
rather than cancel** — pricing fire per size without grouping per size would have
turned that quiet `$0.00` into the refusal, which is why `C3` and `C5` land in
one commit and not in two.

⚠ **WHAT MUST NOT MOVE, AND `tc4` IS HERE TO PROVE IT.** The ruling narrowed
*"one connection, one size"* to METERED connections and to nothing else. A water
or electric point carrying two different recorded sizes is still a data error,
still answers `None`, and still refuses by name — because there the size picks a
TIER LADDER and picking one would price a bill on a coin toss. Without `tc4`
this lane would have traded one defect for a worse one on a bigger money path.

⚠ **AND `tc5` IS THE OTHER HALF.** A unit whose fire service has no equipment on
it at all bills **`$0.00`** and ISSUES — `BR-MET-108`'s ruled zero, the utility
looked and there is nothing — rather than refusing for want of a size. That is
the trap this change had to walk past: arming the per-size axis without it would
have turned every empty fire unit on every fire tenant into an exception row.
"""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.assets import services as asset_services
from apps.billing import models as billing_models
from apps.billing import gather, runs
from apps.customers import models as customer_models
from apps.customers import services as customer_services
from apps.metering import models as metering_models
from apps.metering import selectors as metering_selectors
from apps.metering import services as metering_services
from apps.rating import sample_data as rating_sample_data
from apps.rating import services as rating_services
from apps.tenancy import models as tenancy_models
from apps.tenancy import service_size_classes

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    make_plan,
    make_premises,
    make_unit,
    tenant_ctx,
)
from tests.test_br_cus_068_master_bill import _cycle

pytestmark = pytest.mark.django_db

#: The seeded default prices, read from the ratified module rather than retyped.
#: `OQ-1360` is the going-live customer's own list and is OPEN; these are what a
#: utility STARTS with on Settings → Service sizes.
PRICES = service_size_classes.FIRE_DEFAULT_PRICES

TWO_INCH_LINE = Decimal("12.00")  # 1 × $12.0000
SIX_INCH_LINE = Decimal("60.00")  # 1 × $60.0000
TWO_TWO_INCH_LINES = Decimal("24.00")  # 2 × $12.0000
WAREHOUSE = Decimal("60.00")  # PO 2026-09-03 — was $110.00 with two hydrants
MIXED_PROPERTY = Decimal("84.00")  # $60.00 + $24.00, on ONE line since 2026-09-30 (DEF-BIL-8151)
NOTHING = Decimal("0.00")

#: ⚠ **THE FIGURE THIS FILE USED TO ASSERT, KEPT AS A NUMBER SO A READER WHO
#: MEETS IT ELSEWHERE KNOWS WHICH SIDE OF THE RULING THEY ARE ON.** `$110.00`
#: was the warehouse with `HYD` in the list; the difference is `−$50.00` a
#: month on that customer. It is asserted against nothing — deliberately: there
#: is no code path left that can produce it.
SUPERSEDED_WAREHOUSE_2026_09_02 = Decimal("110.00")

AUG_START, AUG_END = date(2026, 8, 1), date(2026, 8, 31)
INSTALL = date(2026, 1, 5)

#: `backflow` is one of `BR-AST-042`'s ratified twelve and is the device a
#: utility actually records on a fire service connection. The DEMO estate names
#: fire's own types; this file uses a ratified one so the fixture proves the
#: BILLING and never a catalogue addition it does not own.
FIRE_ASSET_TYPE = "backflow"


def _assert_capacity_basis(tenant, code):
    """`BR-TEN-1180` — the tenant's row says this service is priced by CAPACITY.

    ⚠ **NOTHING IS WRITTEN HERE, AND THAT IS THE ASSERTION.** `trash`'s own
    fixtures had to declare `metered=False` by hand because no screen wrote it;
    fire arrives already declared, because `_default_basis_for` reads
    `tenancy.services.SERVICE_DEFAULT_UOMS`, where `CR-063` task A2 put fire's
    **capacity / `connection`** row. If that ever stops being true this file
    fails HERE, naming the declaration, rather than three hundred lines later
    with a bill that quietly demanded a meter reading.
    """
    service = tenancy_models.Service.objects.get(code=code)
    row = tenancy_models.TenantService.objects.get(tenant=tenant, service=service)
    assert row.billing_basis == tenancy_models.BILLING_BASIS_CAPACITY, (
        f"{code} is declared {row.billing_basis!r}; BR-TEN-1180 and CR-063 A2 make it "
        "capacity, and a metered declaration would demand a register fire has not got"
    )


def _fire_plan(tenant, actor):
    """ONE plan pricing FIRE, built from **the product's own seeded payload**.

    ⚠ **THIS IS THE POINT OF THE FIXTURE AND IT IS NOT A CONVENIENCE.** A test
    that typed its own per-size tiers would prove that the ENGINE can price
    them and would say nothing about what a real utility is seeded with — which
    is precisely the gap that let the shipped fire line read `$0.00` while
    `fire_charge()` computed `$12.00` in a module nothing called. Building the
    schedule from `rating.sample_data`'s payload means this file goes red the
    day the SEED stops pricing fire, which is the failure that reached a
    customer.
    """
    estate = SimpleNamespace(services=("fire",))
    # `BR-RAT-088` / `DEF-528` — `_guard_base_charge_code` SELF-ACTIVATES, so a
    # fire schedule cannot be activated at all without fire's own `is_base`
    # code. The code and its `$0.00` amount are the seeder's own
    # (`CAPACITY_BASE_CODE["fire"] = "BASE-FIRE"`, `fixture.CAPACITY_BASE`), so
    # a `$12.00` line below is the SIZE price and nothing else.
    for row in rating_sample_data.capacity_base_charge_codes(estate):
        rating_services.create_charge(
            actor,
            {
                "code": row["code"],
                "name": row["name"],
                "service": row["service"],
                "charge_type": "recurring",
                "amount_rule": "flat",
                "amount": row["amount"],
                "is_base": True,
                "auto_apply": False,
                "taxable_default": True,
                "applies_to_customer_classes": row["applies_to_customer_classes"],
             "effective_from": "2000-01-01"},
        )
    plan = make_plan(tenant, name="Fire protection only", services=("fire",))
    payloads = rating_sample_data.capacity_schedule_payloads(estate)
    assert payloads, "the seeder produced no capacity schedule for fire"
    schedule_ids = {}
    for payload in payloads:
        created = rating_services.create_rate_schedule(actor, dict(payload))
        schedule_ids[payload["name"]] = created["id"]
    from apps.rating import models as rating_models

    rating_models.PlanRateSchedule.objects.filter(tenant=tenant, rate_plan=plan).update(
        tariff_id=schedule_ids[rating_sample_data.capacity_schedule_name("fire")]
    )
    return plan


def _fire_asset(actor, unit_id, number, size_class):
    """One fire device on the unit's fire service point, carrying its SIZE.

    It DECLARES `service: fire`, because `BR-RAT-090`'s count runs asset →
    service point → service: a device without one is invisible to billing,
    which is `DEF-496` with extra rows.
    """
    return asset_services.create_asset(
        actor,
        {
            "type": FIRE_ASSET_TYPE,
            "asset_no": f"FIRE-{number:04d}",
            "service": "fire",
            "unit_id": str(unit_id),
            "install_date": INSTALL.isoformat(),
            # BR-AST-500 — the size lives on the DEVICE, and for a COUNTING
            # service it is what picks the price.
            "size_class": size_class,
        },
    )


def _world(actor, tenant, *, cycle_code, equipment):
    """A unit taking FIRE only, declared unmetered, carrying `equipment`.

    `equipment` is a tuple of size-class codes — `("FL-2",)` for the
    walkthrough house, `("FL-6",)` for the warehouse, `("FL-6", "FL-2", "FL-2")`
    for the mixed property that proves the per-size split, `()` for the unit the
    utility looked at and found nothing on.

    ⚠ The warehouse was `("FL-6", "HYD", "HYD")` until 2026-09-03. Its two
    hydrants are still on the ground; they are now an ASSET RECORD rather than a
    fire-service size, so they are not equipment this fixture installs.
    """
    from apps.metering import premises_owners
    from apps.tenancy import services as tenancy_services

    tenancy_services.update_tenant_service(actor, "fire", {"enabled": True})
    _assert_capacity_basis(tenant, "fire")
    cycle = _cycle(tenant, cycle_code)
    plan = _fire_plan(tenant, actor)
    owner = premises_owners.create_premises_owner(
        actor, {"name": f"Brazos Fire {cycle_code}", "category": "landlord"}
    )
    premises = make_premises(
        actor,
        address_line=f"41 Standpipe Way {cycle_code}",
        services_available=["fire"],
        owner_id=owner["id"],
    )
    unit = make_unit(actor, premises["id"], label="Unit 1", services=["fire"])
    metering_models.ServicePoint.objects.filter(tenant=tenant, unit_id=unit["id"]).update(
        cycle=cycle
    )
    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(plan.id), "effective_from": "2025-01-01"}
    )
    made = [_fire_asset(actor, unit["id"], n + 1, size) for n, size in enumerate(equipment)]
    created = customer_services.create_account(
        actor,
        {
            "unit_id": str(unit["id"]),
            "account_type": "residential",
            "opened_at": AUG_START.isoformat(),
            "contact": {"full_name": "Ruth Alvarez"},
            # `BR-CUS-1024` (2026-09-01) — an account needs an identifier at the
            # door. A phone is the cheapest lawful one for a fixture that is
            # about a fire tariff and not about identity matching.
            "customer": {
                "display_name": f"Ruth Alvarez {cycle_code}",
                "kind": "person",
                "identity": {"phone": "+1-555-0164"},
            },
            "addresses": [
                {"kind": "mailing", "line1": "41 Standpipe Way", "city": "Katy", "state": "TX"}
            ],
        },
    )
    customer_services.activate_account(actor, created["id"])
    account = customer_models.Account.objects.get(pk=created["id"])
    return cycle, unit, account, made


def _bill(tenant, cycle, tag, *, start=AUG_START, end=AUG_END):
    prepared = runs.prepare_run(
        cycle_id=cycle.id, period_start=start, period_end=end, service_date=end
    )
    assert prepared.ready, (
        "the fixture produced no billable account — the test would be vacuous. "
        f"blocked: {[(getattr(b, 'reason', None), str(getattr(b, 'detail', b))[:300]) for b in prepared.blocked]}"
    )
    run = billing_models.BillRun.objects.create(
        tenant=tenant, cycle=cycle, period_start=start, period_end=end, idempotency_key=tag
    )
    return runs.calculate_account(prepared.ready[0], bill_run=run, service_date=end)


def _fire_lines(invoice):
    """The USAGE lines for fire, in bill order, as `(amount, quantity, unit)`."""
    return [
        (line.amount, line.quantity, line.unit)
        for line in invoice.lines.all().order_by("id")
        if line.kind == "usage" and line.service_id and line.service.code == "fire"
    ]


def _describe(invoice):
    """Every line as `kind | service | description | qty unit | amount`, for a
    failure message that says what the bill actually LOOKS like."""
    return [
        f"{line.kind} | {line.service.code if line.service_id else '-'} | "
        f"{line.description} | {line.quantity} {line.unit} | {line.amount}"
        for line in invoice.lines.all().order_by("id")
    ]


# ══════════════════════════════════════════════════════════════════════════
# (1) THE DELIVERABLE — a 2" fire line bills $12.00 and not $0.00
# ══════════════════════════════════════════════════════════════════════════
def test_cr063_c3_tc1__a_two_inch_fire_line_bills_twelve_dollars(brazos, dana):
    """**`1 × $12.0000` = `$12.00`, off the SEEDED tariff.**

    RED BEFORE THE FIX: this exact fixture billed `Decimal('0.00')`. The seeded
    capacity schedule quoted one flat `fixture.CAPACITY_UNIT_PRICES["fire"]`,
    which is the string `"0"` — so a fire line of any diameter priced at
    nothing, on a document that footed and printed.
    """
    with tenant_ctx(brazos):
        cycle, _unit, _account, _kit = _world(
            dana, brazos, cycle_code="FIRE-1", equipment=("FL-2",)
        )

        invoice = _bill(brazos, cycle, "cr063-c3-tc1")

        lines = _fire_lines(invoice)
        assert len(lines) == 1, f"one size on the unit is one line, got {_describe(invoice)}"
        amount, quantity, unit = lines[0]
        assert amount == TWO_INCH_LINE
        # CLAUDE.md rule 3 — the line carries the unit the price is quoted per.
        assert (quantity, unit) == (Decimal("1.000000"), "connection")
        assert invoice.total == TWO_INCH_LINE


# ══════════════════════════════════════════════════════════════════════════
# (2) THE WAREHOUSE — ONE line, $60.00, because its hydrants stopped billing
# ══════════════════════════════════════════════════════════════════════════
def test_cr063_c5_tc2__the_warehouse_bills_sixty_after_the_hydrants_leave(brazos, dana):
    """**`$60.00` ON ONE LINE — and this figure MOVED BY PO RULING.**

    ⚠ **WHAT IS SUPERSEDED, QUOTED, BECAUSE IT WAS PUT TO THE PO IN PLAIN
    ENGLISH AND APPROVED.** The decision log's worked table of 2026-09-02 read:

        Fire — 6" line            1 connection   60.0000    60.00
        Fire — private hydrants   2 hydrants     25.0000    50.00
        Fire, total                                        110.00

    PO 2026-09-03: *"remove private hydrants from list"*. The warehouse has the
    same equipment on the ground and bills **`$60.00`** — **`−$50.00` a month on
    that customer** — because two of its three items are no longer things this
    product bills as a utility service.

    RED BEFORE THIS CHANGE, on PostgreSQL 16 with the six-band list already in
    place: `assert [Decimal('0.00...'), Decimal('60.000000')] == [Decimal('50.00'),
    Decimal('60.00')]` — the hydrant line survived as a `$0.00` unsized group
    because the schedule no longer prices `HYD`.

    ⚠ **ONE LINE IS THE ASSERTION, NOT MERELY THE TOTAL.** A `$110.00` that had
    quietly become `$60.00 + $50.00 × 0` would foot to the same number as a
    correct single line, and only the line COUNT tells them apart. The per-size
    split itself is proved by `tc2b` below, which is where `DEF-3093`'s coverage
    went — it did not go away.

    **NOTHING ALREADY ISSUED IS REWRITTEN** (hard rule 4). This fixture bills a
    fresh period; an invoice issued before the ruling keeps its `$110.00`.
    """
    with tenant_ctx(brazos):
        cycle, _unit, _account, _kit = _world(
            dana, brazos, cycle_code="FIRE-2", equipment=("FL-6",)
        )

        invoice = _bill(brazos, cycle, "cr063-c5-tc2")

        lines = _fire_lines(invoice)
        assert len(lines) == 1, (
            "the warehouse's hydrants stopped being a billable size on 2026-09-03, "
            f"so its bill is ONE line, got {_describe(invoice)}"
        )
        amount, quantity, unit = lines[0]
        assert amount == SIX_INCH_LINE
        assert (quantity, unit) == (Decimal("1.000000"), "connection")
        assert invoice.total == WAREHOUSE
        assert invoice.total != SUPERSEDED_WAREHOUSE_2026_09_02, (
            "$110.00 is the figure the PO superseded on 2026-09-03. If this bill "
            "reads $110.00 again, HYD has come back into fire's size list."
        )


# ══════════════════════════════════════════════════════════════════════════
# (2b) ⚠ THE PER-SIZE SPLIT ITSELF — two sizes, TWO LINES, $84.00
# ══════════════════════════════════════════════════════════════════════════
def test_cr063_c5_tc2b__a_property_with_two_line_sizes_bills_84_on_one_line(brazos, dana):
    """**`$60.00` + `$24.00` = `$84.00`, on ONE fire line — `CR-063` C5's
    actual subject, on sizes the 2026-09-03 ruling left alone.**

    ⚠ **AMENDED 2026-09-30 (`DEF-BIL-8151`) — THE LAYOUT MOVED, THE AMOUNT DID
    NOT.** This case was named *"still bills two lines"* and asserted two
    usage lines, `$60.00` and `$24.00`. The PO ruled on 2026-09-30 (decision
    log *"ONE-TIME BILL: SIX ANSWERS"* (5)), verbatim: *"per service"* —
    *"Counted services: ONE base line PER SERVICE (count and sizes in the
    line's quantity/description), not one line per asset or per size … `CR-063`'s
    fire worked figure ($60.00 + 2 × $12.00 = $84.00) keeps its AMOUNT and now
    prints as ONE fire line of $84.00 rather than two"*. So the case now
    asserts ONE line of `$84.00`, quantity **3** connections, its wording
    naming both sizes — and still the `$84.00`, which is the figure that must
    never move. RED on the tip before the fix: `assert 2 == 1`.

    What the paragraphs below argued for two lines is kept as the record of
    why the per-size ARITHMETIC matters: it still prices each size at its own
    price (`3 × $60.00` would be `$180.00`, `3 × $12.00` `$36.00`), and the
    one line's wording keeps the sizes tellable apart for the customer.

    ⚠ **THIS CASE EXISTS BECAUSE A RULING REMOVED THE FIXTURE THAT USED TO
    CARRY IT, NOT BECAUSE ANYTHING NEW WAS BUILT.** Until 2026-09-03 the
    warehouse's `("FL-6", "HYD", "HYD")` proved both *the warehouse's total* and
    *a mixed property bills one line per size*. The PO withdrew `HYD`, which
    settles the first and says nothing whatever about the second — so the second
    is asserted here on two fire LINE diameters instead. **The code path is
    identical**: `gather` builds one `TariffConfig` per size, `_count_for` gives
    each its own count, and `DEF-3093`'s refusal stays disarmed for a COUNTING
    capacity service.

    ⚠ **ONE BLENDED LINE WOULD BE THE WRONG ANSWER even at the right total**,
    which is why the per-line amounts are asserted and not merely the sum: they
    are different equipment at different prices, and a single quantity of `3`
    would hide that from the customer and from the clerk. `3 × $60.00` would be
    `$180.00` and `3 × $12.00` would be `$36.00`; neither is `$84.00`.
    """
    with tenant_ctx(brazos):
        cycle, _unit, _account, _kit = _world(
            dana, brazos, cycle_code="FIRE-2B", equipment=("FL-6", "FL-2", "FL-2")
        )

        invoice = _bill(brazos, cycle, "cr063-c5-tc2b")

        lines = _fire_lines(invoice)
        assert len(lines) == 1, f"one fire line per service, got {_describe(invoice)}"
        ((amount, quantity, unit),) = lines
        assert amount == SIX_INCH_LINE + TWO_TWO_INCH_LINES == MIXED_PROPERTY
        assert (quantity, unit) == (Decimal("3.000000"), "connection")
        fire_rows = [
            line for line in invoice.lines.all() if line.service_id and line.service.code == "fire"
        ]
        assert len(fire_rows) == 1, _describe(invoice)
        assert invoice.total == MIXED_PROPERTY


# ══════════════════════════════════════════════════════════════════════════
# (3) EVERY ONE OF THE SIX PRICES REACHES A BILL
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("code", sorted(PRICES))
def test_cr063_c3_tc3__every_seeded_fire_size_prices_its_own_amount(brazos, dana, code):
    """**All six bands, one at a time**, so no size is served by another's
    ladder — `BR-RAT-120`: an unpriced size is REFUSED and never substituted,
    and a size served at the WRONG price is the failure that rule guards.

    ⚠ **IT PARAMETRISES OVER THE RATIFIED MODULE AND NEVER OVER A TYPED LIST**,
    which is what made the 2026-09-03 withdrawal a one-line change here: `HYD`
    left `FIRE_DEFAULT_PRICES` and this case simply stopped running for it. A
    list typed out in this file would have kept billing a code the product no
    longer seeds, green.
    """
    with tenant_ctx(brazos):
        cycle, _unit, _account, _kit = _world(
            dana, brazos, cycle_code=f"FIRE-3-{code}", equipment=(code,)
        )

        invoice = _bill(brazos, cycle, f"cr063-c3-tc3-{code}")

        expected = PRICES[code].quantize(Decimal("0.01"))
        assert _fire_lines(invoice)[0][0] == expected
        assert invoice.total == expected


# ══════════════════════════════════════════════════════════════════════════
# (4) ⚠ THE ONE THAT MUST NOT MOVE — a METERED connection still refuses
# ══════════════════════════════════════════════════════════════════════════
def test_cr063_tc4__two_sizes_on_a_METERED_connection_still_refuse_by_name(brazos, dana):
    """**The narrowing is to COUNTING capacity services and to nothing else.**

    Decision log 2026-09-02, verbatim: *"Metered connections keep the rule
    exactly as it stands. Two sizes on a water or electric point is still a data
    error, still answers `None`, and still refuses by name. A test must assert
    this after the change, or the fix has traded one defect for a worse one on a
    bigger money path."* This is that test.

    On a metered service the size picks a TIER LADDER, so answering one of two
    would price a bill on a coin toss — the reasoning
    `metering.connection_size_for` records in its own docstring, unchanged.
    """
    from apps.tenancy import services as tenancy_services
    from apps.metering import premises_owners

    with tenant_ctx(brazos):
        tenancy_services.update_tenant_service(dana, "water", {"enabled": True})
        owner = premises_owners.create_premises_owner(
            dana, {"name": "Brazos Water TC4", "category": "landlord"}
        )
        premises = make_premises(
            dana,
            address_line="9 Two Meters Row",
            services_available=["water"],
            owner_id=owner["id"],
        )
        unit = make_unit(dana, premises["id"], label="Unit 1", services=["water"])
        for n, size in enumerate(('5/8"', '2"')):
            asset_services.create_asset(
                dana,
                {
                    "type": "meter",
                    "asset_no": f"W-TC4-{n:04d}",
                    "service": "water",
                    "unit_id": str(unit["id"]),
                    "install_date": INSTALL.isoformat(),
                    "meter_type": "walk_by",
                    "unit": "kgal",
                    "size_class": size,
                },
            )

        assert metering_selectors.connection_size_for(unit["id"], "water") is None, (
            "two different recorded sizes on a METERED point must still answer None. "
            "Picking one selects a tier ladder, and therefore prices a bill, on a "
            "coin toss (decision log 2026-08-27, narrowed but NOT reversed 2026-09-02)"
        )


# ══════════════════════════════════════════════════════════════════════════
# (5) THE RULED ZERO — a fire unit with NO equipment bills $0.00 and ISSUES
# ══════════════════════════════════════════════════════════════════════════
def test_cr063_c3_tc5__a_fire_unit_with_no_equipment_bills_zero_and_issues(brazos, dana):
    """**`BR-MET-108`'s ruled zero, and it is the trap this change had to pass.**

    ⚠⚠ **AMENDED 2026-09-30 — SUPERSEDED BY THE PO: NO ASSET = NOT IN SERVICE.**
    PO ruling of that date: *"if unit has 6 utility services and user only add
    1 or 3 assets to it - it means you will consider only 3 service point
    exist"*, and a service not in service prints NO line (*"sane no line - and
    use 0"*). A fire connection with nothing on it is therefore NOT billed at
    all: no line and no base. This world's plan prices fire ALONE, so there is
    nothing left to bill and the account stops on `GATHER_NO_TARIFF` (*"a bill
    with no services is not a $0.00 bill"*), exactly as a unit with no point at
    all does (`test_br_bil_301_*::tc5`). RED against the ruling's code before
    this edit: `the fixture produced no billable account`.

    What still stands from the original case: nothing lands on the clerk's
    DECISIONS list as a missing read — there is no read to miss.
    """
    with tenant_ctx(brazos):
        cycle, _unit, _account, _kit = _world(dana, brazos, cycle_code="FIRE-5", equipment=())

        prepared = runs.prepare_run(
            cycle_id=cycle.id, period_start=AUG_START, period_end=AUG_END, service_date=AUG_END
        )
        assert prepared.ready == ()
        assert [b.reason for b in prepared.blocked] == [gather.GATHER_NO_TARIFF]
        assert [d.reason for d in prepared.decisions if d.reason == "missing_read"] == []


# ══════════════════════════════════════════════════════════════════════════
# (6) ⚠ A SIZE NOBODY RECORDED IS A REFUSAL, NEVER A ZERO
# ══════════════════════════════════════════════════════════════════════════
def test_cr063_c3_tc6__an_unrecorded_size_refuses_and_never_bills_zero(brazos, dana):
    """**Decision log 2026-09-02:** *"A size nobody recorded is still a refusal,
    not a zero. An item whose type was never entered stops that customer's bill
    and says so."*

    A 6" fire line whose size nobody entered would bill `$0.00` if the unknown
    were skipped, on a document that foots and prints — `BR-RAT-090`'s own
    distinction: *"'no carts recorded' and 'zero carts' are different facts and
    only one of them is billable."*
    """
    with tenant_ctx(brazos):
        cycle, unit, _account, _kit = _world(dana, brazos, cycle_code="FIRE-6", equipment=("FL-6",))
        from apps.assets import models as asset_models

        asset_models.Asset.objects.filter(tenant=brazos, asset_no="FIRE-0001").update(
            size_class=None
        )

        # ⚠ IT REFUSES AT PREPARE, WHICH IS ONE ACCOUNT AND NEVER THE RUN
        # (`BR-BIL-055`). `prepare_run` catches the `GatherProblem` per account
        # and records it in `blocked`, so a clerk sees ONE named row on the
        # S31.2 exception tab and every other account still drafts.
        prepared = runs.prepare_run(
            cycle_id=cycle.id,
            period_start=AUG_START,
            period_end=AUG_END,
            service_date=AUG_END,
        )
        assert not prepared.ready, "an unrecorded size must stop this account"
        reasons = [getattr(row, "reason", None) for row in prepared.blocked]
        assert reasons == [gather.GATHER_SIZE_UNRESOLVED], (
            "asserted on the REASON and not merely 'something refused': a generic "
            "missing-read refusal would send a clerk to the Reads tab to estimate a "
            f"register fire has not got. got {reasons}"
        )
        # `DEF-BIL-6760` — the sentence was cut to B14 rules 32 and 33 (it carried
        # a closed defect id and about forty words of rationale onto a clerk's
        # screen). This asserts what the clerk NEEDS rather than the old wording:
        # the sizes the schedule prices, so the person fixing it knows what to
        # record, and no internal id.
        detail = str(prepared.blocked[0].detail)
        assert "FL-6" in detail, f"the refusal must name the sizes. got {detail}"
        assert "DEF-" not in detail, f"B14 rule 32 — no internal id. got {detail}"
