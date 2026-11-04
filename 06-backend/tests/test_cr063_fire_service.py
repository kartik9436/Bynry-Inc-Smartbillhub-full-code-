# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-010 · US-TEN-019   Screens: S110 (sign-up), S8 (Settings →
#           Services & UoM, Service sizes)
# Change:   CR-063 — Fire becomes the ELEVENTH utility service, because a real
#           utility is being onboarded and it sells fire protection.
#           CR-063 AMENDED 2026-09-03 — PO: *"remove private hydrants from
#           list"*. `HYD` "Private hydrant" at $25.0000 is WITHDRAWN, fire goes
#           7 bands -> 6, and the warehouse that was $110.00 now bills $60.00.
# Rules:    BR-RAT-024 (CONFIRMED-AS-AMENDED 2026-09-02 — ELEVEN services,
#           `fire` APPENDED at 11, nothing renumbered) · BR-TEN-171 (fire's
#           six bands since 2026-09-03) · BR-RAT-090 (a capacity service's quantity is a COUNT
#           of its assets on the unit) · BR-BIL-010 (a service with no revenue
#           account fails its whole bill at issue) · CLAUDE.md hard rule 2
#           (money 4 dp, displayed 2)
# Tests:    this file
# Impacts:  apps/tenancy/migrations/0033_cr063_fire_service.py ·
#           apps/tenancy/service_size_classes.py · apps/tenancy/services.py ·
#           apps/ledger/chart.py · core/sample_fixture.py
# ───────────────────────────────────────────────────────
"""**CAN A UTILITY THAT SELLS FIRE PROTECTION ACTUALLY BE BILLED?**

`CR-063` exists for one reason and it is not a tidy catalogue: **a real customer
is being onboarded and they sell fire lines.** PO verbatim, 2026-09-02: *"we
have to do it ; curenlty we need it for one of the customer we want to go live"*.
So this file asks the going-live question in the order a customer meets it — the
service exists, it has a unit, it has sizes, those sizes have prices, and the
prices produce the figures the record carries.

⚠ **ONE OF THOSE FIGURES MOVED THE DAY AFTER IT WAS SIGNED, AND THAT IS WHY THIS
FILE READS THE WAY IT DOES.** `CR-063` was approved on 2026-09-02 with a
warehouse billing **`$110.00`** — a 6" line at `$60.00` plus two private
hydrants at `$25.00` each. On 2026-09-03 the PO said *"remove private hydrants
from list"*, and that warehouse now bills **`$60.00`**: **`−$50.00` a month on a
real customer.** The six line diameters and their prices did not move — a 2"
line still bills `$12.00` — and fire still COUNTS rather than SUMS. What changed
is which sizes exist, and nothing about the arithmetic over them.

WHY THE ARITHMETIC IS THE FIRST THING ASSERTED, AND NOT THE LAST
-----------------------------------------------------------------
The PO's whole specification of Fire's billing is four words — *"exactly like
trash"* — and since `CR-062` those four words are **ambiguous in this codebase
in a way that costs money.** A `capacity` service is one of two arithmetics:

    trash  COUNTS what is installed   3 carts x $15.00        = $45.00
    solar  SUMS what is installed     2 + 4 + 8 kW x $14.00   = $196.00

Both are called *capacity based*, both live behind the same enum value, and
**nothing in the product would have gone red if Fire had been given the wrong
one.** A 6" fire line priced as a summable capacity is not a crash; it is a
plausible number on a real invoice. So `test_fire_counts_it_does_not_sum` is the
load-bearing case in this file, and it asserts the mechanical answer
(`capacity_uom_for_service` / `total_capacity`) rather than reading a comment.

⚠ **THE SIX PRICES ASSERTED HERE ARE NOT SIGNED FIGURES AND THIS FILE MUST
NEVER BE CITED AS IF THEY WERE.** Every other price pinned by a test in this
repository traces to a finance signature or a PO ruling. These six were
authored by the `CR-063` lane; the going-live customer's real list is `OQ-1360`
and is OPEN. **The 2026-09-03 ruling did not close it** — the PO removed a row,
they did not ratify the six that remain or the amounts beside them, and a
signature covers only what was shown (PO 2026-08-11). What the assertions buy is
that the SEEDED DEFAULT cannot drift silently — which is worth having whatever
the numbers turn out to be, because the day the customer's own figures arrive,
these tests are where they land.
"""

from decimal import Decimal

import pytest

from apps.ledger import chart
from apps.tenancy import service_size_classes as sizes
from apps.tenancy.services import SERVICE_DEFAULT_UOMS
from core import sample_fixture

pytestmark = pytest.mark.django_db


def _catalogue_codes() -> tuple[str, ...]:
    """The platform catalogue in seed order — read from the MIGRATIONS, which
    are the authority `BR-RAT-024` names, and never from a constant that merely
    agrees with them."""
    from importlib import import_module

    seed = import_module("apps.tenancy.migrations.0001_initial")
    fire = import_module("apps.tenancy.migrations.0033_cr063_fire_service")
    return tuple(code for code, _ in seed.SERVICE_SEED) + tuple(
        code for code, _ in fire.FIRE_SEED
    )


# ── A1 · the service exists, APPENDED ──────────────────────────────────────


def test_the_catalogue_is_eleven_and_fire_is_the_eleventh():
    """`BR-RAT-024`, amended 2026-09-02.

    ⚠ **APPENDED, NOT INSERTED — and the assertion is on the ORDER and not only
    on the membership.** The seed order IS the ruling: `CLAUDE.md` records that
    this repository's own service-count line said *six* while the seed carried
    ten, for weeks. A membership check would pass on a fire row inserted at
    position 3 with every other service silently renumbered, which is precisely
    the mass rewrite `CR-063` refuses to make on a live customer's database.
    """
    codes = _catalogue_codes()
    assert len(codes) == 11, f"the catalogue is ELEVEN services (BR-RAT-024), got {codes}"
    assert codes[-1] == "fire", "fire is APPENDED at position 11 — nothing above it moves"
    assert codes[:10] == (
        "electric",
        "water",
        "gas",
        "sewer",
        "trash",
        "storm_water",
        "solar",
        "broadband",
        "thermal_heat",
        "battery",
    ), "the first ten are untouched — a renumbering here would rewrite every tenant's rows"


def test_the_migration_appends_and_never_updates():
    """The migration seeds fire with `get_or_create`, not `update_or_create`.

    ⚠ **THIS IS A REAL DIFFERENCE AND NOT A STYLE PREFERENCE.** Every earlier
    catalogue change in this repo was written under the PO's beta posture —
    *"I will delete the DB and relaunch"* — and `CR-063` is the first that is
    not: a live utility is being onboarded on this catalogue. `update_or_create`
    would reset a name or a sort a tenant's own operator had changed. The test
    reads the source rather than the behaviour because the behaviour is
    identical on an empty database, which is the only database CI has.
    """
    import inspect
    from importlib import import_module

    mod = import_module("apps.tenancy.migrations.0033_cr063_fire_service")
    # ⚠ **THE FUNCTION'S SOURCE, NOT THE FILE'S.** A whole-file grep for
    # `update_or_create` fails on the docstring that EXPLAINS why the migration
    # does not use it — so the check would be red for the best possible reason,
    # which is a check that cannot distinguish pass from fail (CLAUDE.md law 11,
    # the `--stat` lesson). `inspect.getsource` reads the function that runs.
    body = inspect.getsource(mod.seed_fire)
    assert "get_or_create" in body
    assert "update_or_create" not in body, (
        "a live customer is being onboarded on this catalogue (CR-063 §3), so the "
        "seed is insert-if-absent. update_or_create rewrites rows an operator may "
        "have changed."
    )
    assert mod.FIRE_SORT == 11


# ── A2/A3 · the unit ────────────────────────────────────────────────────────


def test_fire_is_capacity_based_and_its_unit_is_connection():
    """`connection`, not `line` — because a private hydrant is not a line.

    Both are billed off the one tick on the one service, so a unit named for
    either would be wrong for the other. Decided by the lane and recorded in the
    decision log (CLAUDE.md law 13); reversible by a clerk on Settings.
    """
    from apps.tenancy import models

    row = SERVICE_DEFAULT_UOMS["fire"]
    assert row.basis == models.BILLING_BASIS_CAPACITY
    assert row.primary == "connection"
    assert row.alt is None, "fire has one unit; a second would need a reason nobody has given"


def test_connection_is_scoped_to_fire_alone():
    """The derived seed scope — `connection` belongs to fire the way `cart`
    belongs to trash.

    A unit claimed by two services stays NULL ("All services") by design; this
    one is claimed by exactly one, so it narrows. The assertion exists because
    the scope is DERIVED from `SERVICE_DEFAULT_UOMS` rather than typed, and a
    derivation is exactly the thing a reader assumes rather than checks.
    """
    from apps.tenancy.services import SEEDED_UOM_SERVICE_SCOPE

    assert SEEDED_UOM_SERVICE_SCOPE["connection"] == "fire"


# ── A4/A5 · the sizes, and the arithmetic they imply ───────────────────────


def test_fire_has_six_size_classes_in_the_seeded_order():
    """**SIX since 2026-09-03, and it was seven the day before.**

    PO verbatim: *"remove private hydrants from list"*. `HYD` "Private hydrant"
    left this tuple — a hydrant is an ASSET, not a utility-service size — and
    the six line diameters are untouched, in the order they were seeded.
    """
    rows = sizes.size_classes_for_service("fire")
    assert rows == (
        ("FL-2", 'Fire line 2"'),
        ("FL-4", 'Fire line 4"'),
        ("FL-6", 'Fire line 6"'),
        ("FL-8", 'Fire line 8"'),
        ("FL-10", 'Fire line 10"'),
        ("FL-12", 'Fire line 12"'),
    )
    assert "HYD" not in dict(rows), (
        "`HYD` was withdrawn by PO ruling on 2026-09-03 and must not come back "
        "through a merge. A hydrant is an asset (OQ-1361, hydrant half ruled), "
        "and re-seeding it would put $25.00 a month back on a customer's bill."
    )


def test_fire_counts_it_does_not_sum():
    """**THE LOAD-BEARING CASE IN THIS FILE.** *"Exactly like trash"* means the
    size PICKS the price and the COUNT multiplies it — not that the sizes add up.

    Asserted mechanically, against the one call that tells the two shapes apart,
    because a comment saying "fire counts" is not a guarantee that it does
    (CLAUDE.md hard-won law 1). If these two lines ever flip, a 6" fire line
    starts pricing as a summable quantity and produces a plausible wrong number
    on a real invoice with nothing else going red.
    """
    assert sizes.capacity_uom_for_service("fire") is None, (
        "fire is BANDED: the size picks the rate. A unit here would mean the sizes "
        "sum, which is solar's shape and not trash's."
    )
    assert sizes.capacity_uom_for_service("trash") is None, "the shape fire was ruled to copy"
    assert sizes.capacity_uom_for_service("solar") == "kW", "the shape fire is NOT"

    with pytest.raises(sizes.NotACapacityService):
        sizes.total_capacity("fire", ["FL-6", "FL-2"])


def test_every_fire_size_is_a_band_carrying_no_number():
    """Invariant 1 of the module, applied to fire: a band's capacity is `None`
    and never `0`. A zero would sum silently into a wrong total."""
    for row in sizes.RATIFIED_SERVICE_SIZE_CLASSES["fire"]:
        assert row.is_band and not row.is_capacity
        assert row.capacity is None and row.capacity_uom is None


# ── D3 · the two worked figures, verbatim from CR-063 step 5 ───────────────


def test_a_house_with_one_two_inch_sprinkler_line_bills_twelve_dollars():
    """`CR-063` step 5, worked: **one 2" line = $12.00.**"""
    assert sizes.fire_charge({"FL-2": 1}) == Decimal("12.00")


def test_the_warehouse_bills_sixty_dollars_because_its_hydrants_are_not_billable():
    """⚠ **THIS FIGURE MOVED BY PO RULING ON 2026-09-03 AND THE SUPERSESSION IS
    THE POINT OF THE CASE.**

    `CR-063` step 5 was signed on 2026-09-02 with *"a warehouse with a 6-inch
    line and two private hydrants is charged `$60.00` for the line plus `$25.00`
    for each hydrant — **`$110.00`** in total, printed as two separate lines"*.
    The PO then said *"remove private hydrants from list"*, so the same
    warehouse, with the same equipment on the ground, bills **`$60.00`** —
    **`−$50.00` a month on that customer**.

    Nothing was wrong with the old arithmetic. The PO decided a hydrant is not a
    thing this product bills as a utility service, so the two hydrants are
    equipment on file and no longer money on a bill.

    **Both halves are asserted**, because the interesting failure is the old
    figure coming back: the total is `$60.00`, AND `HYD` is refused by name
    rather than silently skipped — a skipped code would bill a hydrant at
    nothing and look identical to this.
    """
    assert sizes.fire_charge({"FL-6": 1}) == Decimal("60.00")

    with pytest.raises(KeyError) as caught:
        sizes.fire_charge({"FL-6": 1, "HYD": 2})
    assert "not a fire size class" in str(caught.value)


def test_two_fire_lines_of_different_sizes_still_add_up_per_size():
    """**THE ARITHMETIC THE HYDRANT RULING DID NOT TOUCH**, kept under test
    because the warehouse case above used to carry it.

    Fire COUNTS per size — the size picks the price, the count multiplies it —
    so a property with a 6" line and two 2" lines is `$60.00 + 2 × $12.00` =
    **`$84.00`**. That is the same code path the `$110.00` warehouse exercised;
    only the sizes on it changed.

    ⚠ **THE ENGINE CANNOT PRODUCE THIS AS ONE LINE AND `DEF-3093` SAYS SO.** Two
    different recorded sizes on one connection make
    `metering.connection_size_for` answer `None` BY DESIGN (*"one connection has
    one size"*, 2026-08-27), so the bill carries one line per size. This
    assertion pins the ARITHMETIC — what the seeded price list says the month
    costs — and `test_cr063_c3_fire_priced.py` proves it reaches a real bill.
    """
    assert sizes.fire_charge({"FL-6": 1, "FL-2": 2}) == Decimal("84.00")


def test_the_seeded_price_list_is_the_six_that_remain_after_the_hydrant_ruling():
    """Pinned so the SEEDED DEFAULT cannot move quietly.

    ⚠ **THE SIX DIAMETER PRICES DID NOT MOVE ON 2026-09-03 — ONLY THE SEVENTH
    ENTRY LEFT.** A 2" line still bills `$12.00`. The withdrawn row was `"HYD":
    Decimal("25.0000")`, and it is named here so a reader can tell a
    WITHDRAWAL from a repricing at a glance: the PO removed a thing, they did
    not change what anything costs.

    ⚠ These are NOT signed figures — see the module docstring and `OQ-1360`,
    which the removal did NOT close. What is asserted is that the seed matches
    what the record says, so the day the customer's real list arrives it
    replaces a known set rather than an assumed one.
    """
    assert sizes.FIRE_DEFAULT_PRICES == {
        "FL-2": Decimal("12.0000"),
        "FL-4": Decimal("30.0000"),
        "FL-6": Decimal("60.0000"),
        "FL-8": Decimal("100.0000"),
        "FL-10": Decimal("160.0000"),
        "FL-12": Decimal("230.0000"),
    }
    assert "HYD" not in sizes.FIRE_DEFAULT_PRICES, (
        "a price with no size class is refused by fire_charge anyway, so the "
        "two must never be separated: PO 2026-09-03 withdrew both together"
    )
    # Money is STORED to 4 decimals (CLAUDE.md hard rule 2).
    for code, amount in sizes.FIRE_DEFAULT_PRICES.items():
        assert amount.as_tuple().exponent == -4, f"{code} is not stored to 4 decimal places"


def test_a_price_list_covers_every_seeded_size_and_no_others():
    """A size with no price is REFUSED and never substituted (`BR-RAT-120`), so
    a list that has drifted apart from the size classes must be impossible."""
    assert set(sizes.FIRE_DEFAULT_PRICES) == {
        row.code for row in sizes.RATIFIED_SERVICE_SIZE_CLASSES["fire"]
    }


def test_no_fire_equipment_is_zero_and_a_typo_refuses():
    """`BR-RAT-090`'s own distinction, one service along: *"no carts recorded"*
    and *"zero carts"* are different facts and only one of them is billable.

    An EMPTY mapping is a real answer — a unit with no fire equipment owes
    nothing for fire — and an UNKNOWN code refuses rather than being skipped,
    because a silently skipped `FL-3` is a fire line billed at nothing.
    """
    assert sizes.fire_charge({}) == Decimal("0.00")
    assert sizes.fire_charge({"FL-6": 0}) == Decimal("0.00")
    with pytest.raises(KeyError):
        sizes.fire_charge({"FL-3": 1})
    with pytest.raises(ValueError):
        sizes.fire_charge({"FL-6": -1})


# ── C1/C4 · the estate and the revenue account ─────────────────────────────


def test_fire_rides_the_estate_as_a_capacity_companion():
    """Fire needs no metered backbone, exactly as trash does not.

    A fire-only tenant therefore gets an estate with no backbone at all — the
    shape a trash-only tenant has had since `DEF-2414` — and is declared
    UNMETERED so the run stops demanding a register it will never have.
    """
    assert "fire" in sample_fixture.CAPACITY_ESTATE_SERVICES
    assert "fire" in sample_fixture.UNMETERED_ESTATE_SERVICES
    assert "fire" not in sample_fixture.METERED_ESTATE_SERVICES

    plan = sample_fixture.estate_plan(
        ["fire"], default_uoms={"fire": SERVICE_DEFAULT_UOMS["fire"].primary}
    )
    # ⚠ `plan.metered`, NOT `plan.backbone` — `CR-062` C3 REMOVED that field
    # rather than shimming it, precisely so a caller written against the old
    # one-metered-service shape breaks loudly instead of quietly reading the
    # first of several. This case was written against `backbone` while that
    # change was in flight and went red the moment the estate lane landed; it is
    # brought onto the shipped shape here rather than given a compatibility
    # read, which is the whole reason that field was deleted.
    #
    # An EMPTY `metered` is the answer and not a gap: a fire-only tenant holds no
    # register at all, which is what a trash-only tenant has had since
    # `DEF-2414`. All four fields are asserted, because "fire is a companion" and
    # "fire is not metered" and "fire is refused nothing" are three different
    # facts and only the three together say the estate is right.
    assert plan.metered == (), f"fire needs no metered service, got {plan.metered}"
    assert plan.metered_codes == (), "a fire-only tenant has no register to read"
    assert plan.companions == ("fire",)
    assert plan.services == ("fire",), (
        "the estate must SPEAK fire — a plan that shapes premises and units and does "
        "not name the service is DEF-3224's shape: bills that carry nothing for it"
    )
    assert plan.refused == (), f"a fire-only tenant is refused nothing, got {plan.refused}"


def test_fire_has_its_own_revenue_account_and_it_is_not_solars():
    """**`BR-BIL-010`: a service with no revenue account fails its WHOLE bill at
    issue**, which is why every catalogue service must appear in this map.

    `4155` sits between `4150` Capacity and `4160` Storm water in the chart's own
    ladder. Fire does NOT share `4150`: the ❄️ frozen line names ONE account for
    *solar/battery* by name, and adding a third service to it would make the
    ledger say something that line does not.
    """
    assert chart.SERVICE_REVENUE_ACCOUNTS["fire"] == ("4155", None)
    assert set(chart.SERVICE_REVENUE_ACCOUNTS) == set(_catalogue_codes()), (
        "every catalogue service is mapped, or it provisions with a NULL revenue "
        "account and cannot be invoiced (BR-BIL-010)"
    )
    row = {r.code: r for r in chart.SEED_CHART}["4155"]
    assert (row.name, row.type) == ("Fire", "revenue")


def test_4155_is_unsigned_and_says_so():
    """It arrived on the `4160`/`4170`/`4180` posture: the PO ruled that the
    SERVICE exists, the CODE and the NAME are the lane's reading of the ladder,
    and only a dated HUMAN-GUIDE §6 addendum makes it signed.

    The pin is here as well as in the ledger suite because a lane adding a
    twelfth service will read THIS file, and *"just copy how fire did it"* has
    to carry the unsigned posture with it rather than dropping it.
    """
    assert "4155" in chart.PENDING_FINANCE_RE_SIGN
    assert not {r.code: r for r in chart.SEED_CHART}["4155"].signed
    assert "4155" in chart.PENDING_FINANCE_RE_SIGN_SOURCE, (
        "a reviewer reading the source sentence must be told where 4155 came from, "
        "or they are told about every unsigned code except the newest one"
    )


# ── D5 · nothing frozen moved ──────────────────────────────────────────────


def test_no_frozen_figure_moved_when_fire_arrived():
    """`GT-17`'s reference bill states water **$39.50** and sewer **$15.80** as
    figures on their own LINES. Fire is new money on new lines, so it adds a
    line and moves neither — checked rather than assumed, because *"it cannot
    have moved"* is exactly the reasoning `CR-062`'s own note warns about.

    ⚠ Water and sewer's revenue mappings are the assertion, not the amounts:
    the amounts are asserted by `06-backend/tests/golden/`, which runs the
    ENGINE. What could plausibly have moved HERE is a chart row or a service
    mapping renumbered on the way past, and that is what this pins.
    """
    assert chart.SERVICE_REVENUE_ACCOUNTS["water"] == ("4110", "4115")
    assert chart.SERVICE_REVENUE_ACCOUNTS["sewer"] == ("4120", None)
    assert sizes.size_classes_for_service("sewer") == (), "sewer is ruled to have NONE"
    assert len(sizes.size_classes_for_service("water")) == 9, "water's nine bands are untouched"
    assert len(sizes.size_classes_for_service("trash")) == 7, "trash's seven are untouched"
