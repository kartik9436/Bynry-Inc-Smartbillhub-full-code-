# ── Trace ──────────────────────────────────────────────
# Change:   CR-029 (Routes & Cycles) — wave RC-W4, tasks T1–T6 (B17 §7).
#           PO ruling 2026-08-23, verbatim: *"D4 yes member resolve at run
#           time"* and *"D13 - Cycles are not directlya ssing to accounts it is
#           derived and determined at the time of bill run"*.
# Source:   B17 §5 "The dynamism audit" and its D4 answer, verbatim: *"scoping
#           questions — who is on this route right now? which units does CY-001
#           bill? is anyone uncovered? — are derived live from the current tags
#           at the moment Reads or Billing asks. Stored rows keep exactly two
#           jobs: explicit human choices (a hand-picked premises, an excluded
#           meter, a walk order) and immutable history (the route stamped on
#           each collected read)."*
# Fixtures: tests/cr029_dynamism_fixtures.py — RC-W0 built one builder per audit
#           row and every one of them RECORDS today's answer and judges nothing.
#           This file is where the judging lives (B17 §7 W4-T2).
# Defects:  DEF-225 (a unit added to a routed premises is never read and never
#           billed) · DEF-249 (a membership with no service point is invisible
#           to the bill run, so a base-only unit can never bill) — both close
#           BY CONSTRUCTION here, and each has its own named test below.
# Rules:    BR-MET-082 + Amendment 1 (a route is a cascade, not a list;
#           resolution at RUN TIME; a varying count between runs is CORRECT) ·
#           BR-MET-074 (≤1 route per service) · BR-MET-076 (a draft affects
#           nothing) · BR-MET-078 (no money on these surfaces) · D10 (a route
#           serves a service SET) · CLAUDE.md rule 1 (tenant scoping), rule 6
#           (bill-run idempotency), rule 3 (explicit UoM).
# ───────────────────────────────────────────────────────
"""RC-W4 — membership resolved at run time, proved against the audit it closes.

**THE TEST OF WHETHER THIS WAS BUILT RIGHT IS THAT NO CASCADE WAS ADDED.**
B17 §7 W4-T1: *"Done when: every RED row of B17 §5's dynamism audit turns green
with NO new cascade code — that is the test of whether you did it right. If you
find yourself adding a cascade to patch a stored row, you have built the old
design again."* So every scenario test below asserts BOTH halves:

* the STORED rows are exactly what they were before D4 — no new write path
  touched them, and the fixture's own `observed` bag is the evidence; and
* the DERIVED answer is the one the current tags imply.

A test that only checked the second half could be passed by a cascade.

**WHY THE DERIVED ANSWER CAN DISAGREE WITH A STORED MEMBERSHIP ROW.** A
membership on a route that carries an AREA is a projection of the area tag —
that is how `cascade_area_to_routes` writes it and how the wizard's area-filtered
step 2 selects it. When the premises leaves that area the projection no longer
holds, so the row is STALE and the derivation does not read it. A membership on a
route with NO area is a genuine hand-pick that no tag explains, and it is
honoured — that is B17 §5's *"explicit human choices (a hand-picked premises…)"*.
Both halves are asserted here.
"""

from __future__ import annotations

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.metering import derivation, models, selectors, services

from tests import identity_fixtures
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

# ⚠ IMPORTED AS A MODULE, NOT AS NAMES. `tests.test_us_met_helpers` exports its
# own `make_premises(actor, **overrides)` through the star import above, and the
# fixture module's `make_premises(actor, address_line, *, area_code=None)` is a
# different function with the same name — importing both by name silently gives
# whichever came last, which is how this file first failed with
# `TypeError: make_premises() takes 1 positional argument but 2 were given`.
from tests import cr029_dynamism_fixtures as dyn  # noqa: E402
from tests.cr029_dynamism_fixtures import (  # noqa: E402
    DYNAMISM_AUDIT,
    account_opened_and_closed_on_a_routed_unit,
    meter_attached_to_draft_routed_unit,
    premises_moved_between_areas,
    route_area_changed,
    routed_unit_with_no_meter,
    unit_moved_between_premises,
)

active_cycle = dyn.active_cycle
active_route = dyn.active_route
make_area = dyn.make_area
make_premises = dyn.make_premises
make_unit = dyn.make_unit

pytestmark = pytest.mark.django_db


def _route_code(unit_id, service_code: str) -> str | None:
    resolved = derivation.route_for_unit(unit_id, service_code)
    return resolved.route_code if resolved is not None else None


def _member_unit_ids(route_id) -> list[str]:
    return sorted(row["unit_id"] for row in derivation.members_of_route(route_id))


# ═══════════════════════════════════════════════════════════════════════════
# W4-T2 · THE DYNAMISM AUDIT, ROW BY ROW — B17 §5
# ═══════════════════════════════════════════════════════════════════════════


def test_dyn1_a_premises_moved_between_areas_is_read_by_its_NEW_areas_route(brazos, dana):
    """B17 §5 row 1 — *"a premises moved between areas (keeps old routes)"*.

    The fixture's own worked example of how RC-W4 consumes it:

        # today: s.observed["stamped_route_code"] is still the NORTH route
        assert derived_route_for(s.unit_id, "water") == s.south_route_code
    """
    with tenant_ctx(brazos):
        scenario = premises_moved_between_areas(dana, brazos)
        derived = _route_code(scenario["unit_id"], "water")
        north_members = _member_unit_ids(scenario["north_route_id"])
        south_members = _member_unit_ids(scenario["south_route_id"])

    # HALF ONE — the stored answer did NOT move. No cascade was added.
    assert scenario.observed["stamped_route_code_after_move"] == scenario["north_route_code"]
    assert scenario.observed["membership_route_codes_after_move"] == [scenario["north_route_code"]]
    # HALF TWO — the DERIVED answer follows the tag that actually moved.
    assert derived == scenario["south_route_code"]
    assert north_members == []
    assert south_members == [str(scenario["unit_id"])]


def test_dyn2_a_route_redrawn_onto_another_area_re_derives_both_ways(brazos, dana):
    """B17 §5 row 2 — *"a route whose area changes (members not re-derived)"*.

    Both directions in one assertion pair: the old area's unit LEAVES and the
    new area's unit JOINS, neither of them having been written to.
    """
    with tenant_ctx(brazos):
        scenario = route_area_changed(dana, brazos)
        members = _member_unit_ids(scenario["route_id"])
        north_route = _route_code(scenario["north_unit_id"], "water")
        south_route = _route_code(scenario["south_unit_id"], "water")

    # HALF ONE — the stored membership still names the unit from the OLD area.
    assert scenario.observed["member_unit_ids_after"] == [str(scenario["north_unit_id"])]
    # HALF TWO — derived: the North unit is out, the South unit is in.
    assert members == [str(scenario["south_unit_id"])]
    assert north_route is None
    assert south_route == scenario["route_code"]


def test_dyn3_a_unit_moved_between_premises_follows_its_new_premises(brazos, dana):
    """B17 §5 row 3 — *"a unit moved between premises (no cascade found on that
    path)"*. BR-MET-082 clause 7: *"when you move premises from 1 route to
    another; all accounts and meter units etc will move to"*."""
    with tenant_ctx(brazos):
        scenario = unit_moved_between_premises(dana, brazos)
        derived = _route_code(scenario["unit_id"], "water")
        north_members = _member_unit_ids(scenario["north_route_id"])
        south_members = _member_unit_ids(scenario["south_route_id"])

    # HALF ONE — nothing moved the stored row; the move service never touched it.
    assert scenario.observed["stamped_route_code_after_move"] == scenario["north_route_code"]
    # HALF TWO — the unit is read by the route its NEW premises belongs to.
    assert derived == scenario["south_route_code"]
    assert north_members == []
    assert south_members == sorted([str(scenario["unit_id"]), str(scenario["sibling_unit_id"])])


def test_dyn5_a_routed_unit_with_no_meter_is_visible_to_the_bill_run(brazos, dana):
    """B17 §5 row 5 — *"a routed unit with no meter (no service point →
    invisible to the bill run)"*, and B17 §7 **W4-T4**: *"Meterless routed units
    become billable-visible"*.

    The meterless unit is a member of the route on every screen, and a base-only
    unit is exactly the unit that has no meter (CLAUDE.md law 10 records
    base-only billing as a staff choice). Today it is silently absent from the
    run's scope; under D4 it is present.
    """
    with tenant_ctx(brazos):
        scenario = routed_unit_with_no_meter(dana, brazos)
        scoped = selectors.units_in_cycle(scenario["cycle_id"])
        members = _member_unit_ids(scenario["route_id"])

    # HALF ONE — the unit still has NO service point. Nothing was created for it.
    assert scenario.observed["meterless_unit_service_points"] == 0
    assert scenario.observed["meterless_unit_stamped_route_code"] is None
    # HALF TWO — and it is nevertheless in the route and in the run.
    assert str(scenario["meterless_unit_id"]) in members
    assert str(scenario["meterless_unit_id"]) in scoped
    assert str(scenario["metered_unit_id"]) in scoped


def test_dyn6_the_cycle_derives_its_accounts_and_the_closed_one_drops_out(brazos, dana):
    """B17 §5 row 6 — *"an account opened/closed (no modelled link at all)"* —
    and **D13**, verbatim: *"Cycles are not directlya ssing to accounts it is
    derived and determined at the time of bill run"*.

    account → unit → route → cycle, walked live. The closed account is out and
    the open one is in, with no column anywhere pairing an account with a cycle.
    """
    with tenant_ctx(brazos):
        scenario = account_opened_and_closed_on_a_routed_unit(dana, brazos)
        accounts = derivation.accounts_in_cycle(scenario["cycle_id"])
        account_ids = {row["account_id"] for row in accounts}
        count = selectors.cycle_account_count(scenario["cycle_id"])

    assert str(scenario["open_account_id"]) in account_ids
    assert str(scenario["closed_account_id"]) not in account_ids
    assert count == 1
    # BR-MET-078 / D12 — nothing about money travels on this payload.
    assert not any(
        key in row for row in accounts for key in ("balance", "amount", "due", "currency")
    )


def test_the_whole_audit_re_scopes_in_one_tenant(brazos, dana):
    """B17 §7 W4-T2: *"The audit's scenarios as tests"* — every row, together.

    `build_all` puts all six in one tenant, which is where a resolution that
    only works in isolation falls over: six areas, seven routes and six cycles
    all answering at once.
    """
    from tests.cr029_dynamism_fixtures import build_all

    with tenant_ctx(brazos):
        scenarios = build_all(dana, brazos)
        answers = {
            "DYN-1": _route_code(scenarios["DYN-1"]["unit_id"], "water"),
            "DYN-2": _route_code(scenarios["DYN-2"]["south_unit_id"], "water"),
            "DYN-3": _route_code(scenarios["DYN-3"]["unit_id"], "water"),
            "DYN-4": _route_code(scenarios["DYN-4"]["unit_id"], "water"),
            "DYN-5": _route_code(scenarios["DYN-5"]["meterless_unit_id"], "water"),
            "DYN-6": _route_code(scenarios["DYN-6"]["open_unit_id"], "water"),
        }

    assert len(DYNAMISM_AUDIT) == 6
    assert answers["DYN-1"] == scenarios["DYN-1"]["south_route_code"]
    assert answers["DYN-2"] == scenarios["DYN-2"]["route_code"]
    assert answers["DYN-3"] == scenarios["DYN-3"]["south_route_code"]
    assert answers["DYN-4"] is None, "a draft route is not an answer to any scoping question"
    assert answers["DYN-5"] == scenarios["DYN-5"]["route_code"]
    assert answers["DYN-6"] == scenarios["DYN-6"]["route_code"]


# ═══════════════════════════════════════════════════════════════════════════
# W4-T3 · THE DRAFT LEAK (B17 §5 gap G4)
# ═══════════════════════════════════════════════════════════════════════════


def test_dyn4_the_meter_attach_path_does_not_stamp_a_draft_routes_stamp(brazos, dana):
    """G4, verbatim: *"The meter-attach path skips the draft check — a draft
    route's stamp can reach billing (likely bug, no ruling needed)"*.

    `services.ensure_service_point` takes `membership.route` and
    `membership.route.cycle` with **no filter on `route.status`**, so the row a
    draft route wrote in step 2 of the wizard becomes a live stamp the moment a
    meter arrives. BR-MET-076 is the rule it breaks: *"a draft route stamps no
    service point"* — the rule both other stamping paths (`_stamp_service_points`
    and `_stamp_added_service_points`) already enforce.
    """
    with tenant_ctx(brazos):
        scenario = meter_attached_to_draft_routed_unit(dana, brazos)
        scoped = selectors.units_in_cycle(scenario["cycle_id"])

    # the setup is intact — the draft route DOES hold the membership row
    assert scenario.observed["membership_route_codes"] == [scenario["draft_route_code"]]
    # …and the stamp the meter attach used to write is gone.
    assert scenario.observed["stamped_route_code_after_attach"] is None
    assert scenario.observed["stamped_cycle_code_after_attach"] is None
    # …so the draft cannot reach the bill run through `units_in_cycle` either.
    assert scoped == []


def test_a_meter_attached_to_an_ACTIVE_routed_unit_still_inherits(brazos, dana):
    """The other half of the draft guard, and the reason it is not a blanket
    refusal: BR-MET-082 clause 5 — *"when you add new meter … it automatically
    understand which route and cycle it should be in"*. Only DRAFT is silent."""
    with tenant_ctx(brazos):
        area = make_area(brazos, "A-LIVE", "Live district")
        cycle = active_cycle(dana, "CY-LIVE")
        premises = make_premises(dana, "12 Live Way", area_code=area.code)
        unit = make_unit(dana, premises["id"])
        route = active_route(
            dana,
            code="RT-LIVE",
            name="Live water walk",
            area=area,
            service_code="water",
            cycle=cycle,
            unit_ids=[unit["id"]],
        )
        point_id = services.ensure_service_point(unit["id"], "water")
        point = models.ServicePoint.objects.get(pk=point_id)

    assert str(point.route_id) == str(route.id)
    assert str(point.cycle_id) == str(cycle.id)


# ═══════════════════════════════════════════════════════════════════════════
# THE TWO OPEN DEFECTS, CLOSED BY CONSTRUCTION
# ═══════════════════════════════════════════════════════════════════════════


def test_def225_a_unit_added_the_way_a_CLERK_adds_one_reaches_the_bill_run(brazos, dana):
    """DEF-225, and its own prevention column names the shape:

    *"DURABLE GUARD, and it is the shape no current test has: create a route,
    THEN add a unit to one of its premises, and assert the unit is on the route
    — every existing fixture creates the route and asserts in the same breath,
    so none of them can express the passage of time."*

    And DEF-249's: *"a test that creates a unit the way a CLERK does (no
    services, no meter) and asserts it reaches the bill run, with no helper
    called in between."* This test is both — no `ensure_service_point`, no
    meter grid, no second call.
    """
    with tenant_ctx(brazos):
        area = make_area(brazos, "N-CLERK", "North")
        cycle = active_cycle(dana, "CY-CLERK")
        premises = make_premises(dana, "39 Clerk Way", area_code=area.code)
        active_route(
            dana,
            code="RT-CLERK",
            name="North water walk",
            area=area,
            service_code="water",
            cycle=cycle,
        )
        # …time passes, and a clerk adds a unit to the building.
        late = make_unit(dana, premises["id"], label="Unit B")
        scoped = selectors.units_in_cycle(cycle.id)
        points = models.ServicePoint.objects.filter(tenant_id=brazos.id, unit_id=late["id"]).count()

    assert points == 0, "the clerk created no service point — that is the whole point"
    assert str(late["id"]) in scoped


def test_def249_membership_without_a_service_point_is_in_the_runs_scope(brazos, dana):
    """DEF-249 — *"A unit with a route membership but NO service point is
    invisible to the bill run, so a meterless base-only unit can never be
    billed"*.

    B17 §7 W4-T4 rules the direction the defect row left open: *"Meterless
    routed units become billable-visible"*, so the seam RESOLVES the state
    rather than creation refusing it.
    """
    with tenant_ctx(brazos):
        cycle = active_cycle(dana, "CY-BASEONLY")
        premises = make_premises(dana, "7 Base Only Ln")
        unit = make_unit(dana, premises["id"])
        active_route(
            dana,
            code="RT-BASEONLY",
            name="Hand-picked walk",
            service_code="water",
            cycle=cycle,
            unit_ids=[unit["id"]],
        )
        scoped = selectors.units_in_cycle(cycle.id)
        points = models.ServicePoint.objects.filter(tenant_id=brazos.id, unit_id=unit["id"]).count()

    assert points == 0
    assert scoped == [str(unit["id"])]


# ═══════════════════════════════════════════════════════════════════════════
# W4-T5 · NO ACCOUNT-LEVEL CYCLE ASSIGNMENT EXISTS (D13, asserted absent)
# ═══════════════════════════════════════════════════════════════════════════


def test_no_account_model_field_pairs_an_account_with_a_cycle():
    """D13, verbatim: *"Cycles are not directlya ssing to accounts it is derived
    and determined at the time of bill run"*, and B17 §3: *"No account-level
    cycle assignment exists."*

    RC-W3b asserted no ROUTE pairs "cycle" with "assign"; this is the model-side
    equivalent, because a column is how such an assignment would come back.
    """
    from django.apps import apps as django_apps

    account = django_apps.get_model("customers", "Account")
    names = {field.name for field in account._meta.get_fields()}
    assert not any(
        "cycle" in name for name in names
    ), "an account carrying a cycle would be the assignment D13 forbids"
    for model_name in ("Account", "ServiceAgreement"):
        try:
            model = django_apps.get_model("customers", model_name)
        except LookupError:
            continue
        columns = {
            field.column
            for field in model._meta.get_fields()
            if getattr(field, "column", None) is not None
        }
        assert not any("cycle" in column for column in columns), model_name


def test_no_customers_service_assigns_a_cycle():
    """The write half of the same absence — a service function is the other way
    an assignment would arrive."""
    from apps.customers import services as customer_services

    offenders = [
        name
        for name in dir(customer_services)
        if "cycle" in name.lower() and "assign" in name.lower()
    ]
    assert offenders == []


def test_coverage_reads_live_and_names_what_the_account_LACKS(brazos, dana):
    """B17 §7 W4-T5: *"coverage reads live"*, and D13's remedy: *"Uncovered
    accounts are shown with what they actually lack (a route); the remedy is to
    route them."*

    The account is uncovered, then its premises is tagged into the route's area
    — no route is edited, no membership is written — and coverage follows.
    """
    with tenant_ctx(brazos):
        area = make_area(brazos, "N-COVER", "North")
        cycle = active_cycle(dana, "CY-COVER")
        active_route(
            dana,
            code="RT-COVER",
            name="North water walk",
            area=area,
            service_code="water",
            cycle=cycle,
        )
        scenario = account_opened_and_closed_on_a_routed_unit(dana, brazos, suffix="CV")
        # a second building, on no route at all
        premises = make_premises(dana, "88 Uncovered Way")
        unit = make_unit(dana, premises["id"])
        services.assign_unit_plan(
            dana,
            unit["id"],
            {
                "tariff_id": str(
                    __import__("apps.rating.models", fromlist=["models"])
                    .RatePlan.objects.filter(tenant=brazos)
                    .first()
                    .id
                )
            },
        )
        from apps.customers import services as customer_services

        stranded = customer_services.create_account(
            dana,
            {
                "unit_id": str(unit["id"]),
                "account_type": "residential",
                "status": "active",
                "opened_at": "2026-07-01",
                "contact": {"full_name": "Uncovered Ursula", "email": "u@example.test"},
                # `BR-CUS-1024` (PO 2026-09-01) — the door refuses an account whose
                # customer identifies nobody, and this fixture's own name went in above.
                # ONE shape for every fixture in the suite: tests/identity_fixtures.py.
                "customer": identity_fixtures.customer_block(
                    "Uncovered Ursula", account_type="residential"
                ),
            },
        )
        before = selectors.uncovered_account_count()
        # THE EVENT: the premises is tagged into the covered area. Nothing else.
        services.update_premises(dana, premises["id"], {"area_code": area.code})
        after = selectors.uncovered_account_count()

    stranded_id = str(stranded["id"])
    assert stranded_id in {row["account_id"] for row in before["uncovered"]}
    assert all(row["lacks"] == "route" for row in before["uncovered"])
    assert stranded_id not in {row["account_id"] for row in after["uncovered"]}
    assert after["uncovered_accounts"] == before["uncovered_accounts"] - 1
    # the closed account of the DYN-6 scenario is never "uncovered" — it is not
    # an open account at all, and coverage counts open accounts (BR-MET-080).
    assert str(scenario["closed_account_id"]) not in {
        row["account_id"] for row in before["uncovered"]
    }


# ═══════════════════════════════════════════════════════════════════════════
# W4-T6 · THE MULTI-SERVICE MEMBERSHIP HOLE (D10 + D4)
# ═══════════════════════════════════════════════════════════════════════════


def _multi_service_world(actor, tenant, suffix="MS"):
    """A "Water + Electric" route (D10's own example: RT-001) holding one unit,
    plus an ELECTRIC-only route that will try to take it.

    ⚠ **BOTH ROUTES ARE HAND-PICKED (no area), deliberately.** With no area tag
    in play the STORED rows are the whole truth, so what this exercises is the
    write-side rule — which membership a save is allowed to leave standing —
    rather than the area derivation the audit rows already cover. That is where
    the hole lived: `_set_route_membership` asked its conflict question of
    `routes.service_id` alone.
    """
    cycle = active_cycle(actor, f"CY-{suffix}")
    other_cycle = active_cycle(actor, f"CY-{suffix}-E", name="Electric reads")
    premises = make_premises(actor, f"1 Multi Service Way {suffix}")
    unit = make_unit(actor, premises["id"])
    services.ensure_service_point(unit["id"], "water")
    services.ensure_service_point(unit["id"], "electric")
    both = services.create_route(
        actor,
        {
            "code": f"RT-{suffix}-BOTH",
            "name": "Water + Electric",
            "route_type": "walk",
            "service_codes": ["water", "electric"],
            "cycle_id": str(cycle.id),
            "unit_ids": [unit["id"]],
        },
    )
    models.Route.objects.filter(pk=both["id"]).update(status="active")
    electric = services.create_route(
        actor,
        {
            "code": f"RT-{suffix}-E",
            "name": "Electric only",
            "route_type": "walk",
            "service_codes": ["electric"],
            "cycle_id": str(other_cycle.id),
        },
    )
    models.Route.objects.filter(pk=electric["id"]).update(status="active")
    return {
        "unit_id": unit["id"],
        "both_id": both["id"],
        "both_code": both["code"],
        "electric_id": electric["id"],
        "electric_code": electric["code"],
        "cycle_id": str(cycle.id),
        "other_cycle_id": str(other_cycle.id),
    }


def test_t6_the_multi_service_route_reads_the_unit_for_EVERY_service_in_its_set(brazos, dana):
    """D10: *"yes it will be multi service"*. RT-001 is *"Water + Electric"*, so
    the derivation must answer with that route for BOTH words — not only for the
    transitional head `routes.service_id`."""
    with tenant_ctx(brazos):
        world = _multi_service_world(dana, brazos)
        water = _route_code(world["unit_id"], "water")
        electric = _route_code(world["unit_id"], "electric")

    assert water == world["both_code"]
    assert electric == world["both_code"]


def test_t6_a_unit_on_a_multi_service_route_cannot_also_join_another_routes_service(brazos, dana):
    """B17 §7 W4-T6, verbatim: *"a "Water + Electric" route enforces per-service
    membership uniqueness for WATER ONLY — so the same unit can also join an
    electric route and be read twice."*

    Done when: *"a unit on a multi-service route cannot also join another route
    for ANY service in that set."* BR-MET-074's answer to a conflict is a MOVE,
    not a refusal (*"selecting moves them, with confirm"*), so the unit lands on
    exactly one route for electric — never on two.
    """
    with tenant_ctx(brazos):
        world = _multi_service_world(dana, brazos)
        services.update_route(dana, world["electric_id"], {"unit_ids": [world["unit_id"]]})
        electric = _route_code(world["unit_id"], "electric")
        water = _route_code(world["unit_id"], "water")
        stored = sorted(
            models.Route.objects.get(pk=row.route_id).code
            for row in models.RouteMembership.objects.filter(
                tenant_id=brazos.id, unit_id=world["unit_id"]
            )
        )

    # ONE route for electric, and it is the one that just claimed it.
    assert electric == world["electric_code"]
    # …and the unit is no longer read twice: the multi-service route lost it.
    #
    # ⚠ **AND IT LOST THE WHOLE UNIT, WATER INCLUDED — a REPORTED consequence,
    # not an oversight.** A membership row is per (route, unit) because a route
    # is one crew visit, so a unit cannot be half on a route. Moving it onto a
    # narrower route therefore takes it off the wider one entirely, and the
    # water gap it leaves is VISIBLE — `uncovered_account_count` reports it, and
    # the alternative (leaving both rows standing) is the double read this task
    # exists to close.
    assert water is None
    assert stored == [world["electric_code"]], (
        "the unit is stored on exactly one route — the move happened, "
        "not a silent second membership"
    )


def test_t6_the_unit_is_never_in_two_cycles_for_one_service(brazos, dana):
    """The money-shaped consequence of the hole, asserted at billing's own seam:
    a unit read twice is a unit billed twice."""
    with tenant_ctx(brazos):
        world = _multi_service_world(dana, brazos)
        services.update_route(dana, world["electric_id"], {"unit_ids": [world["unit_id"]]})
        first = selectors.units_in_cycle(world["cycle_id"], service_codes=["electric"])
        second = selectors.units_in_cycle(world["other_cycle_id"], service_codes=["electric"])

    assert str(world["unit_id"]) not in first
    assert str(world["unit_id"]) in second


def test_t6_the_resolution_answers_at_most_one_route_per_unit_and_service(brazos, dana):
    """The structural half: whatever the stored rows say, the derivation is a
    FUNCTION of (unit, service) and can only ever return one route."""
    with tenant_ctx(brazos):
        world = _multi_service_world(dana, brazos, suffix="MS2")
        # force the exact shape the hole allowed: a second stored membership for
        # a service the multi-service route already covers.
        models.RouteMembership.objects.create(
            tenant_id=brazos.id,
            route_id=world["electric_id"],
            unit_id=world["unit_id"],
            service_id=models.RouteService.objects.filter(route_id=world["electric_id"])
            .first()
            .service_id,
        )
        resolved = derivation.route_for_unit(world["unit_id"], "electric")
        members_both = _member_unit_ids(world["both_id"])
        members_electric = _member_unit_ids(world["electric_id"])

    assert resolved is not None
    assert (str(world["unit_id"]) in members_both) != (
        str(world["unit_id"]) in members_electric
    ), "the unit appears on exactly one of the two routes, never on both"


def test_t6_two_routes_may_read_one_unit_for_DIFFERENT_services(brazos, dana):
    """The other half of the guarantee, and the half a blunt fix would break.

    BR-MET-074 exists because *"a house on water AND electric is legitimately
    read by two different crews on two different routes"*. So the rule closed
    above must forbid two routes reading one unit for **the same** service and
    must still allow two routes reading it for different ones — here an
    area-drawn "Water + Electric" route and a hand-picked electric route, which
    is the realistic shape of D10's RT-001 beside a special-case walk.
    """
    with tenant_ctx(brazos):
        area = make_area(brazos, "H-MIX", "Here")
        cycle = active_cycle(dana, "CY-MIX")
        other = active_cycle(dana, "CY-MIX-E", name="Electric reads")
        premises = make_premises(dana, "2 Mixed Way", area_code=area.code)
        unit = make_unit(dana, premises["id"])
        services.ensure_service_point(unit["id"], "water")
        services.ensure_service_point(unit["id"], "electric")
        both = services.create_route(
            dana,
            {
                "code": "RT-MIX-BOTH",
                "name": "Water + Electric",
                "route_type": "walk",
                "service_codes": ["water", "electric"],
                "area_code": area.code,
                "cycle_id": str(cycle.id),
            },
        )
        models.Route.objects.filter(pk=both["id"]).update(status="active")
        hand = active_route(
            dana,
            code="RT-MIX-E",
            name="Electric special",
            service_code="electric",
            cycle=other,
            unit_ids=[unit["id"]],
        )
        water = _route_code(unit["id"], "water")
        electric = _route_code(unit["id"], "electric")
        electric_scope_here = selectors.units_in_cycle(cycle.id, service_codes=["electric"])
        electric_scope_there = selectors.units_in_cycle(other.id, service_codes=["electric"])

    assert water == "RT-MIX-BOTH", "the area route still reads it for water"
    assert electric == hand.code, "and the hand-picked route reads it for electric"
    # ONE electric run covers it, never two.
    assert str(unit["id"]) not in electric_scope_here
    assert str(unit["id"]) in electric_scope_there


# ═══════════════════════════════════════════════════════════════════════════
# PERFORMANCE IS A CORRECTNESS CONCERN — the read path does more work now
# ═══════════════════════════════════════════════════════════════════════════


def _seeded_route(actor, tenant, *, units: int, suffix="PERF"):
    area = make_area(tenant, f"P-{suffix}", "Perf district")
    cycle = active_cycle(actor, f"CY-{suffix}")
    route = active_route(
        actor,
        code=f"RT-{suffix}",
        name="Perf water walk",
        area=area,
        service_code="water",
        cycle=cycle,
    )
    for index in range(units):
        premises = make_premises(actor, f"{100 + index} Perf Way {suffix}", area_code=area.code)
        unit = make_unit(actor, premises["id"])
        services.ensure_service_point(unit["id"], "water")
    return route, cycle


#: Billing's scope seam, measured. THIRTEEN reads, and the number is a CEILING
#: that may fall and never rise — the same ratchet shape D7's other counts use.
#:
#: 1 the cycle · 2 its active routes · 3–5 the candidate set (area tree, the
#: units those areas cover, the routes' stored members) · 6–12 the resolution
#: (area tree, units, their memberships, the active routes that could claim
#: them, the routes' service SETS, the routes' members with the tag that decides
#: whether each pick is still live, the units' service points) · 13 the
#: route-less cycle stamps.
#:
#: The STAMPED implementation was ONE query, and that is the honest cost of
#: D4: a snapshot is cheap to read and wrong (DEF-225, DEF-249). Thirteen flat
#: reads is the price of the answer being right, and flat is the part that had
#: to be engineered — see the equality assertion below.
UNITS_IN_CYCLE_QUERY_CEILING = 13


def test_the_derivation_does_not_grow_a_query_per_member(brazos, dana):
    """RC-W3b measured a per-row path at 31 queries against a batched page at 8.
    Deriving live means more work per ask; it must not mean more work per ROW."""
    with tenant_ctx(brazos):
        _small_route, small_cycle = _seeded_route(dana, brazos, units=2, suffix="P2")
        _big_route, big_cycle = _seeded_route(dana, brazos, units=8, suffix="P8")
        with CaptureQueriesContext(connection) as small:
            assert len(selectors.units_in_cycle(small_cycle.id)) == 2
        with CaptureQueriesContext(connection) as big:
            assert len(selectors.units_in_cycle(big_cycle.id)) == 8

    assert len(big.captured_queries) == len(small.captured_queries), (
        f"{len(small.captured_queries)} queries for 2 units and "
        f"{len(big.captured_queries)} for 8 — that is an N+1"
    )
    assert len(big.captured_queries) <= UNITS_IN_CYCLE_QUERY_CEILING, len(big.captured_queries)


def test_the_route_membership_read_does_not_grow_a_query_per_member(brazos, dana):
    with tenant_ctx(brazos):
        small_route, _c1 = _seeded_route(dana, brazos, units=2, suffix="M2")
        big_route, _c2 = _seeded_route(dana, brazos, units=8, suffix="M8")
        with CaptureQueriesContext(connection) as small:
            assert len(selectors.route_members(small_route.id)) == 2
        with CaptureQueriesContext(connection) as big:
            assert len(selectors.route_members(big_route.id)) == 8

    assert len(big.captured_queries) == len(
        small.captured_queries
    ), f"{len(small.captured_queries)} → {len(big.captured_queries)}"


# ═══════════════════════════════════════════════════════════════════════════
# WHAT MUST NOT CHANGE
# ═══════════════════════════════════════════════════════════════════════════


def test_the_scope_is_stable_and_ordered_when_nothing_moved(brazos, dana):
    """`units_in_cycle`'s standing promise — *"a run scoped twice covers the
    same accounts in the same order"* — is about ONE run's preview-to-issue
    window, and BR-MET-082 Amendment 1's *"every run it is not necessry it will
    ahve same number"* is about run-to-run. Both hold: the answer is a pure
    function of the tags, so it is identical while the tags are."""
    with tenant_ctx(brazos):
        _route, cycle = _seeded_route(dana, brazos, units=5, suffix="STABLE")
        first = selectors.units_in_cycle(cycle.id)
        second = selectors.units_in_cycle(cycle.id)

    assert first == second
    assert first == sorted(first), "the order is the stable one the seam promises"
    assert len(first) == 5


def test_the_bill_run_idempotency_key_is_untouched():
    """CLAUDE.md hard rule 6 — a bill run is idempotent on (tenant · cycle ·
    period). Nothing in this wave may relax it, and a derivation that changed
    WHICH units a run covers must not change WHICH RUNS ARE THE SAME RUN.

    Asserted at both ends: the key is composed of the cycle and both period
    dates, and the database's unique is `(tenant, idempotency_key)`.
    """
    from datetime import date

    from apps.billing import models as billing_models
    from core import idempotency

    key = idempotency.bill_run_key(
        cycle_id="cy-1", period_start=date(2026, 9, 1), period_end=date(2026, 9, 30)
    )
    assert key.startswith("cy-1")
    assert "2026-09-01" in key and "2026-09-30" in key
    assert key == idempotency.bill_run_key(
        cycle_id="cy-1", period_start=date(2026, 9, 1), period_end=date(2026, 9, 30)
    )
    uniques = {
        tuple(constraint.fields)
        for constraint in billing_models.BillRun._meta.constraints
        if hasattr(constraint, "fields")
    }
    assert ("tenant", "idempotency_key") in uniques, uniques


def test_a_draft_cycle_is_still_invisible_to_a_bill_run(brazos, dana):
    """BR-MET-076 — a draft cycle stamps nothing and scopes nothing. Deriving
    must not resurrect it."""
    with tenant_ctx(brazos):
        area = make_area(brazos, "D-CYC", "Draft cycle district")
        row = services.create_cycle(
            dana, {"code": "CY-DRAFT", "name": "Draft", "frequency": "Monthly"}
        )
        models.Cycle.objects.filter(pk=row["id"]).update(status="draft")
        cycle = models.Cycle.objects.get(pk=row["id"])
        premises = make_premises(dana, "5 Draft Cycle Way", area_code=area.code)
        make_unit(dana, premises["id"])
        active_route(
            dana,
            code="RT-DRAFTCYC",
            name="Water walk",
            area=area,
            service_code="water",
            cycle=cycle,
        )
        scoped = selectors.units_in_cycle(cycle.id)

    assert scoped == []


def test_an_inactive_route_scopes_nothing(brazos, dana):
    """IS-1 — *"inactive means used to run and no longer does"*. It keeps its
    history and stops answering scoping questions."""
    with tenant_ctx(brazos):
        area = make_area(brazos, "I-OFF", "Retired district")
        cycle = active_cycle(dana, "CY-OFF")
        premises = make_premises(dana, "9 Retired Way", area_code=area.code)
        unit = make_unit(dana, premises["id"])
        services.ensure_service_point(unit["id"], "water")
        route = active_route(
            dana,
            code="RT-OFF",
            name="Retired walk",
            area=area,
            service_code="water",
            cycle=cycle,
            unit_ids=[unit["id"]],
        )
        assert selectors.units_in_cycle(cycle.id) == [str(unit["id"])]
        models.Route.objects.filter(pk=route.id).update(status="inactive")
        after = selectors.units_in_cycle(cycle.id)

    assert after == []


def test_a_hand_picked_premises_on_an_AREALESS_route_is_honoured(brazos, dana):
    """B17 §5: *"Stored rows keep exactly two jobs: explicit human choices (a
    hand-picked premises, an excluded meter, a walk order) and immutable
    history"*. A route with no area is a pure hand-pick and no tag can contradict
    it, so the stored row IS the answer."""
    with tenant_ctx(brazos):
        area = make_area(brazos, "N-HAND", "North")
        cycle = active_cycle(dana, "CY-HAND")
        premises = make_premises(dana, "3 Hand Picked Ct", area_code=area.code)
        unit = make_unit(dana, premises["id"])
        services.ensure_service_point(unit["id"], "water")
        hand = active_route(
            dana,
            code="RT-HAND",
            name="Hand-picked walk",
            service_code="water",
            cycle=cycle,
            unit_ids=[unit["id"]],
        )
        # an area route drawn over the same district afterwards
        active_route(
            dana,
            code="RT-AREA",
            name="North water walk",
            area=area,
            service_code="water",
            cycle=cycle,
        )
        derived = _route_code(unit["id"], "water")

    assert derived == hand.code, "a hand-pick outranks an area claim"


def test_no_money_reaches_the_derivation(brazos, dana):
    """BR-MET-078, hardened by CR-029: *"routes and cycles are grouping only -
    so we will not tag late fees , etc"*."""
    with tenant_ctx(brazos):
        scenario = routed_unit_with_no_meter(dana, brazos, suffix="NM")
        rows = derivation.members_of_route(scenario["route_id"])

    forbidden = {"amount", "balance", "currency", "rate", "fee", "due", "price"}
    for row in rows:
        assert not (forbidden & set(row)), row
