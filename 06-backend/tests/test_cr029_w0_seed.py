# ── Trace ──────────────────────────────────────────────
# Change:   CR-029 (Routes & Cycles) — wave RC-W0, task W0-T1 (B17 §7):
#           *"Seed routes and cycles to the full model: RT-001… / CY-001…
#           grammar, routes with service sets and areas (closes the
#           seeded-routes-are-empty defect), … cycles across frequencies.
#           Done when: the demo tenant exercises the area filter, the cascade
#           and every wizard field; zero routes with null service/area."*
# Rules:    D5 (*"Rt-001 is good"*) · D7 (*"Yes - please do it"* — seeded routes
#           get real service/area) · D9 (bill day + due days stay on the cycle
#           as DEFAULTS) · B17 §2 (start day · frequency · days to complete) ·
#           BR-MET-073/074/077/078 · BR-MET-083 (the tagging cascade) ·
#           CLAUDE.md rule 1 (every write inside tenant context) · rule 7.
# Note:     The command's LIVE double-run is Postgres-gated in
#           tests/test_seed_demo.py. This file runs the same two seeding
#           methods against the sqlite test tenant, because the question it
#           asks — *what does the seeded data look like* — is answerable
#           without a GUC and was answerable by nothing before.
# ───────────────────────────────────────────────────────
"""The demo fixture's routes and cycles, asserted against the rulings.

WHY A SECOND SEED TEST FILE EXISTS
----------------------------------
`tests/test_seed_demo.py` asks whether the command RUNS and whether its money
figures trace to a ratified source. Neither question can see the defect W0-T1
is here to close: **every seeded route carried a NULL service and a NULL area**
(B17 §5 gap G7), so the SET-06.2 area chips filtered a fixture in which no route
had ever held an area, and the only tenant a reviewer ever opens could not
exercise the filter, the cascade, or the wizard's own fields. The seed ran
perfectly and produced data the product could not be judged on.

So these cases assert the CONTENT, not the run:

* the `RT-001` / `CY-001` grammar (D5), on every row;
* **zero routes with a null service or a null area** — the headline done-when;
* every cycle carries the three ruled fields about time, and its frequency is
  one of B17 §2's eight business words;
* the day-of-month defaults the cycle still holds (D9) are ordered as
  BR-MET-077 requires, and no money field exists anywhere near either table;
* the area filter returns rows — the exact assertion DEF-220 was filed for;
* membership stamps reach the service points (BR-MET-033), including the two
  routes that share a premises for two different services (BR-MET-074);
* **RT-001 carries a real service SET** — D10's *"Water + Electric"* — beside
  the split pair, so both shapes are in front of a reviewer at once;
* one meter exclusion, the building's master, with its two-word reason.

⚠ ONE PART OF W0-T1 IS STILL OWED, AND IT IS NOT A SEEDING OVERSIGHT. D11's
per-PREMISES walk order has a table (`RoutePremisesOrder`, RC-W1 W1-T4) and
**no writer** — its own docstring says *"THE FIRST WRITER IS RC-W3-T3's
drag-to-reorder"*. Seeding it would mean the tenancy command writing a metering
table directly, which is a cross-module write (B1) and breaks the command's own
honesty contract. `test_the_seed_uses_every_route_field_the_schema_actually_has`
holds the line: the moment a service function exists, that test asks for the
orders.
"""

from __future__ import annotations

from datetime import date

import pytest

from apps.metering import models as metering_models
from apps.metering import schedule, selectors as metering_selectors
from apps.metering import services as metering_services
from apps.tenancy.management.commands import seed_demo as seed_demo_module

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

CMD = seed_demo_module

pytestmark = pytest.mark.django_db


@pytest.fixture()
def seeded(brazos, dana):
    """The fixture's premises, units, cycles and routes, through the command's
    own methods — no reimplementation, so a divergence between this test and
    the seed is impossible by construction."""
    command = CMD.Command()
    with tenant_ctx(brazos):
        premises_made, units_made, index = command._seed_premises_and_units(dana)
        cycles_made, routes_made = command._seed_cycles_and_routes(dana, index)
        assets_made = command._seed_assets(dana, index)
        # The exclusion runs LAST because it names an asset — the same order
        # `handle()` uses, so this fixture cannot drift from the real run.
        exclusions_made = command._apply_route_exclusions(dana)
        yield {
            "command": command,
            "tenant": brazos,
            "index": index,
            "counts": {
                "premises": premises_made,
                "units": units_made,
                "cycles": cycles_made,
                "routes": routes_made,
                "assets": assets_made,
                "exclusions": exclusions_made,
            },
        }


# ═══════════════════════════════════════════════════════════════════════════
# THE HEADLINE — zero routes with a null service or a null area
# ═══════════════════════════════════════════════════════════════════════════
def test_no_seeded_route_has_a_null_service_or_a_null_area(seeded):
    """B17 §5 G7, closed by D7. The old fixture had FIVE of five wrong — every
    seeded route NULL on both columns; this asserts the number is zero.

    ⚠ A NULL service is not merely "unset" — DEF-227 records what an
    all-services route does to a service point that already belongs to a route
    drawn for its own service: it takes it, and stamps its own (absent) cycle
    over the top, so the unit drops out of the bill run entirely.
    """
    rows = list(metering_models.Route.objects.filter(tenant_id=seeded["tenant"].id))
    assert rows, "the seed created no routes at all"
    nulls = [row.code for row in rows if row.service_id is None or row.area_id is None]
    assert nulls == [], f"routes seeded with a null service or area: {nulls}"


def test_the_route_and_cycle_codes_use_the_ruled_grammar(seeded):
    """D5, PO verbatim: *"Rt-001 is good"* — replacing "Route 1..7" and
    "Cycle 08-A"."""
    routes = sorted(row["code"] for row in metering_selectors.routes_list())
    cycles = sorted(row["code"] for row in metering_selectors.cycles_list())
    assert routes == [f"RT-{n:03d}" for n in range(1, len(routes) + 1)]
    assert cycles == [f"CY-{n:03d}" for n in range(1, len(cycles) + 1)]


def test_the_seed_created_what_its_constants_declare(seeded):
    assert seeded["counts"]["cycles"] == len(CMD.CYCLES) == 6
    assert seeded["counts"]["routes"] == len(CMD.ROUTES) == 6
    assert seeded["counts"]["premises"] == len(CMD.PREMISES) == 6
    assert seeded["counts"]["units"] == sum(len(entry["units"]) for entry in CMD.PREMISES) == 10
    assert seeded["counts"]["assets"] == len(CMD.ASSETS)
    assert seeded["counts"]["exclusions"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# THE CYCLES — the three ruled fields, the eight words, the D9 defaults
# ═══════════════════════════════════════════════════════════════════════════
def test_every_cycle_carries_the_three_ruled_fields_about_time(seeded):
    """B17 §2, from the PO's pre-CR ruling: *"we can capture start day,
    frequency, … and days to complete it"*."""
    rows = list(metering_models.Cycle.objects.filter(tenant_id=seeded["tenant"].id))
    assert len(rows) == len(CMD.CYCLES)
    for row in rows:
        assert row.frequency in schedule.FREQUENCIES, f"{row.code}: {row.frequency!r}"
        assert row.start_day is not None, f"{row.code} has no start day"
        assert row.days_to_complete is not None and row.days_to_complete >= 1


def test_the_seeded_cycles_span_several_frequencies(seeded):
    """W0-T1: *"cycles spanning several frequencies"*.

    Five of B17 §2's eight words are seeded. Daily is `n/a` for a start day by
    that same table, and Weekly and Fortnightly anchor on a WEEKDAY that no
    column holds — `cycles.start_day` validates 1–31 and no rule gives a
    weekday meaning to an integer in that range — so seeding one would invent
    the meaning rather than exercise it.
    """
    words = {row.frequency for row in metering_models.Cycle.objects.all()}
    assert words == {"Monthly", "Quarterly", "Bimonthly", "Semiannual", "Annual"}
    assert words <= set(schedule.FREQUENCIES)


def test_the_cycle_keeps_its_bill_day_and_due_days_as_defaults(seeded):
    """D9, PO verbatim: *"when we configure Cycle we are provideing default
    values; mostly it wil remain as it is but user can over ride them during
    billing"*. So they are ON the cycle, and BR-MET-077's order holds — stated
    now in the ruled fields' own terms, because W5-T2 dropped the day pair:
    the bill day may not fall before the day the derived window CLOSES."""
    for row in metering_models.Cycle.objects.all():
        assert row.bill_day is not None, f"{row.code} carries no bill-day default"
        assert row.due_days == 20, f"{row.code}: EP-MET-02 §4's '+20 days'"
        close = min(row.start_day + row.days_to_complete - 1, 31)
        assert row.start_day <= close <= row.bill_day, row.code


def test_the_derived_window_is_start_day_plus_days_to_complete(seeded):
    """*"start day + N days IS the read window"* (B17 §2), INCLUSIVE.

    ⚠ **THIS ASSERTED THE MAINTAINED LEGACY COPY UNTIL W5-T2** — that
    `read_day_from == start_day` and `read_day_to == start_day + days - 1` — and
    that copy is gone with its columns. What is left is the fact the copy was
    checking: the window a reader is SERVED is exactly those two fields, so it
    is asserted where a reader actually sees it.
    """
    served = {row["code"]: row for row in metering_selectors.cycles_list()}
    for row in metering_models.Cycle.objects.all():
        window = schedule.derive_read_window(row.start_day, row.days_to_complete, date(2026, 8, 1))
        assert window is not None, row.code
        assert window[0].day == row.start_day, row.code
        assert (window[1] - window[0]).days == row.days_to_complete - 1, row.code
        assert served[row.code]["read_window_source"] == "derived", row.code


def test_one_cycle_is_deliberately_left_with_no_routes(seeded):
    """The SET-05 cycles landing states its own coverage — *"42 accounts sit on
    no cycle — they are never read and never billed until one is assigned"* —
    and SET-07D has a whole Coverage tab about the gap. Neither is reviewable
    against a fixture in which every cycle is full."""
    empty = [row["code"] for row in metering_selectors.cycles_list() if not row.get("routes")]
    assert empty == ["CY-006"]


# ═══════════════════════════════════════════════════════════════════════════
# THE AREA FILTER AND THE CASCADE — the thing that could not be exercised
# ═══════════════════════════════════════════════════════════════════════════
def test_the_area_filter_returns_rows_on_the_demo_fixture(seeded):
    """DEF-220's exact symptom, on the seed rather than in a unit test: the
    SET-06.2 area chips took the picker from *"9 premises match"* to *"0
    premises match"* every time, because `premises.area_id` had never held a
    value on any tenant. Every seeded area must now match at least one row.

    ⚠ **AMENDED 2026-08-27 (DEF-836) — THIS CHECK COULD NOT FAIL, AND IT IS THE
    REASON THE DEFECT SURVIVED.** It called `premises_list` with a filter named
    `area_codes`, and until CR-039 wave E `selectors.premises_list` read `type`
    and `status` and NOTHING else — `core.pagination.parse_list_params`
    documents that *"undeclared filter names are ignored"*. So every call here
    returned the WHOLE tenant and `assert list(matched)` was true for `NORTH`,
    for `IND` and for a code that does not exist. Two changes, both so the
    assertion can go RED:

      · the filter name is `area`, which is what the endpoint declares
        (`api.PREMISES_FILTERS`) and what `ROUTE_FILTERS` has always used;
      · a filter must return FEWER rows than no filter, and an unknown code
        must return NONE — the two facts a "returns something" check cannot
        distinguish from a filter that does nothing at all.

    The seeded codes also grew a second level (BR-MET-066c), so NORTH's own
    premises are tagged `NORTH-NW` / `NORTH-NE`; a NORTH chip that matched only
    rows literally tagged NORTH would return zero, which is DEF-220's symptom
    wearing a different hat. BR-MET-072 is what makes it return them.
    """
    tagged = metering_models.Premises.objects.filter(
        tenant_id=seeded["tenant"].id, area__isnull=False
    ).count()
    assert tagged == len(CMD.PREMISES), "a seeded premises carries no area tag"

    everything = metering_selectors.premises_list().count()
    assert everything > 0
    assert (
        list(metering_selectors.premises_list(filters={"area": "NOT-AN-AREA"})) == []
    ), "an unknown area returned rows — the filter is not wired (DEF-836)"

    for code in ("NORTH", "DTWN", "EAST", "IND"):
        matched = metering_selectors.premises_list(filters={"area": code})
        assert list(matched), f"the area filter returns nothing for {code}"
        assert (
            matched.count() < everything
        ), f"filtering by {code} returned every premises — the filter is being ignored"


def test_membership_stamps_reach_the_service_points(seeded):
    """BR-MET-033: membership drives `service_points.route_id`, and the cycle
    rides the same stamp. A route whose members are stored but never stamped is
    invisible to Reads and to the bill run.

    ⚠ **THE STAMP IS CHECKED AGAINST THE SERVICE SET, NOT THE HEAD (CR-029 D10 +
    RC-W4-T6).** This asserted `route.service_id == point.service_id`, which is
    the pre-D10 reading and is now too narrow: RT-001 is *"Water + Electric"*, so
    it stamps its members' electric points as well as their water ones, and a
    head-only assertion would insist a multi-service route leave half of what it
    reads unrouted. DEF-227's protection is unchanged and is what the `in` below
    keeps — the stamp must still be a route that reads THIS point's service.
    """
    stamped = metering_models.ServicePoint.objects.filter(
        tenant_id=seeded["tenant"].id, route__isnull=False
    )
    assert stamped.count() > 0
    for point in stamped:
        route = metering_models.Route.objects.get(pk=point.route_id)
        service_ids = set(
            metering_models.RouteService.objects.filter(
                tenant_id=seeded["tenant"].id, route=route
            ).values_list("service_id", flat=True)
        ) or ({route.service_id} if route.service_id else set())
        # An empty set is the legacy ALL-SERVICES route, which reads everything.
        assert (
            not service_ids or point.service_id in service_ids
        ), f"{route.code} stamped a foreign service"
        assert point.cycle_id == route.cycle_id


def test_rt_001_carries_a_real_service_set(seeded):
    """D10, PO verbatim: *"yes it will be multi service"* — and the upgraded
    prototype draws RT-001 as **"Water + Electric"**. Before `route_services`
    existed there was no field that sentence could be true of, and the fixture
    is where a reviewer first sees whether it is.

    The head `routes.service_id` is the SET's first member — the transitional
    projection `route_memberships.service` denormalizes from — so the ORDER the
    seed writes is load-bearing, not cosmetic.
    """
    route = metering_models.Route.objects.get(tenant_id=seeded["tenant"].id, code="RT-001")
    members = list(
        metering_models.RouteService.objects.filter(
            tenant_id=seeded["tenant"].id, route=route
        ).select_related("service")
    )
    assert {row.service.code for row in members} == {"water", "electric"}
    assert route.service.code == "water", "the head must be the set's first member"

    # …and every OTHER route holds its set too, so the table is never the
    # empty half of a half-migrated fixture.
    for row in metering_models.Route.objects.filter(tenant_id=seeded["tenant"].id):
        count = metering_models.RouteService.objects.filter(
            tenant_id=seeded["tenant"].id, route=row
        ).count()
        assert count >= 1, f"{row.code} carries no service set"


def test_one_premises_is_read_by_two_crews_for_two_services(seeded):
    """BR-MET-074's own case, kept BESIDE RT-001's service set: 2200 Riverbend
    Ct is on RT-003 for electric and RT-004 for water — one address, two crews.

    The fixture holds both shapes on purpose. A reviewer has to be able to tell
    "one route that reads two services" (RT-001) from "two routes that split
    them" (RT-003/RT-004), and a fixture with only one of them makes the other
    unreviewable.
    """
    premises_id = seeded["index"]["premises"]["2200 Riverbend Ct"]
    units = list(
        metering_models.Unit.objects.filter(tenant_id=seeded["tenant"].id, premises_id=premises_id)
    )
    assert units
    for unit in units:
        codes = sorted(
            metering_models.Route.objects.get(pk=row.route_id).code
            for row in metering_models.RouteMembership.objects.filter(unit=unit)
        )
        assert codes == ["RT-003", "RT-004"], f"{unit.label}: {codes}"


def test_the_master_meter_is_excluded_with_its_two_word_reason(seeded):
    """BR-MET-075 + B17 §6: *"`route_meter_exclusions.reason` — two words, shown
    in place"*, which SET-06D's Assets tab renders beside the row.

    ⚠ **AN EXCLUSION IS A ROW, NEVER A CHANGE TO THE ASSET.** The master meter
    keeps its premises, its unit, its service point and everything it bills;
    the one thing that changes is which crew sheet it appears on. This test
    asserts both halves, because a "fix" that un-metered the master would
    satisfy the first one on its own.
    """
    from apps.assets import models as asset_models

    rows = list(metering_models.RouteMeterExclusion.objects.filter(tenant_id=seeded["tenant"].id))
    assert len(rows) == 1
    exclusion = rows[0]
    assert metering_models.Route.objects.get(pk=exclusion.route_id).code == "RT-002"

    asset = asset_models.Asset.objects.get(pk=exclusion.asset_id)
    assert asset.asset_no == "M-7200"
    assert exclusion.reason == "master metered"
    assert len(exclusion.reason.split()) == 2, "the design's shape is two words"

    # the asset is untouched — still placed, still on its service point
    assert asset.service_point_id is not None


# ═══════════════════════════════════════════════════════════════════════════
# BR-MET-078 — grouping only, no money, on either table
# ═══════════════════════════════════════════════════════════════════════════
def test_the_seed_puts_no_money_on_a_route_or_a_cycle(seeded):
    """*"routes and cycles are grouping only - so we will not tag late fees ,
    etc"* — hardened by this CR, and D12 dropped the Balance column for the
    same reason. Matched as whole underscore-separated words: `feeder_ref`
    contains "fee" and is not money."""
    money_words = {"amount", "balance", "fee", "fees", "price", "rate", "deposit", "penalty"}
    for model in (metering_models.Route, metering_models.Cycle):
        columns = {f.name.lower() for f in model._meta.get_fields() if hasattr(f, "attname")}
        offenders = {c for c in columns if money_words & set(c.split("_"))}
        assert not offenders, f"{model.__name__}: {offenders}"
    for entry in (*CMD.ROUTES, *CMD.CYCLES):
        offenders = {k for k in entry if money_words & set(k.split("_"))}
        assert not offenders, f"{entry['code']} seeds a money-shaped field: {offenders}"


# ═══════════════════════════════════════════════════════════════════════════
# WHAT W0-T1 STILL OWES — named, so the gap is a fact and not an omission
# ═══════════════════════════════════════════════════════════════════════════
def test_the_seed_uses_every_route_field_the_schema_actually_has(seeded):
    """The remaining three parts of W0-T1, guarded so the gap cannot outlive
    the column it is waiting for.

    ⚠ **THE SHAPE OF THIS GUARD IS THE POINT, AND THE OBVIOUS VERSION WAS
    WRONG.** It was first written as *assert the columns are absent* — "so it
    goes red the day they land". In a tree six lanes share, that is a test
    engineered to break a sibling's green build for doing exactly what its own
    wave says to do, and the lane that broke it would have no idea why. This
    version asserts the IMPLICATION instead: **if the column exists, the seed
    must be using it.** Green while the column is absent, green once the seed
    catches up, red only in the window where the schema is ahead of the
    fixture — which is the only state anybody needs telling about.

    Two of the three are now SEEDED (RC-W1's W1-T4 landed the columns): D10's
    service SET is on RT-001, and the exclusion reason is on M-7200. The third
    is still owed and it is owed for a reason no seed can fix:

    * **D11, the per-PREMISES walk order** (*"Per premises"* — one stop, many
      meters). `RoutePremisesOrder` now EXISTS, and **it has no writer**: its
      own docstring says *"THE FIRST WRITER IS RC-W3-T3's drag-to-reorder"*.
      The seed's honesty contract is that every write goes through the owning
      module's service (CLAUDE.md rule 7), so seeding the order would mean a
      raw ORM insert from the tenancy module into a metering table — a
      cross-module write, forbidden by B1 — or inventing the service function,
      which is another lane's file. Reported, not worked around.
    """

    def columns(model):
        return {f.name for f in model._meta.get_fields()}

    # D10 — the service SET. The signal is the MODEL, not a Route column:
    # `route_services` is its own table and shows up on `Route` only as a
    # reverse accessor.
    if hasattr(metering_models, "RouteService"):
        assert any(
            {"services", "service_codes", "service_set"} & set(entry) for entry in CMD.ROUTES
        ), "D10's service set exists and the demo fixture still seeds a single service"

    # D11 — the per-PREMISES walk order. Seeded the moment it has a SERVICE to
    # write it: the table alone is not enough, because the seed may not write a
    # metering table directly (B1, and the command's own honesty contract).
    if hasattr(metering_models, "RoutePremisesOrder") and hasattr(
        metering_services, "set_route_premises_order"
    ):
        assert any("walk_orders" in entry or "walk_order" in entry for entry in CMD.ROUTES), (
            "D11's per-premises walk order has a writer now and the demo fixture "
            "seeds none — W0-T1 asks for a walk route carrying real orders"
        )

    # The exclusion reason — two words, rendered in place on SET-06D.
    if "reason" in columns(metering_models.RouteMeterExclusion):
        assert any("exclusions" in entry for entry in CMD.ROUTES), (
            "`route_meter_exclusions.reason` exists and the demo fixture seeds no "
            "exclusion — W0-T1 asks for at least one carrying its two-word reason"
        )

    # Whatever else moves, every seeded route names the service(s) it reads.
    assert all(
        "service_code" in entry or {"services", "service_codes"} & set(entry)
        for entry in CMD.ROUTES
    )
