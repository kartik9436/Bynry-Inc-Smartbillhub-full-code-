# ── Trace ──────────────────────────────────────────────
# Change:   CR-029 (Routes & Cycles, PO ruling *"G0 - Yes now"* 2026-08-23) —
#           wave RC-W0, task W0-T2 (B17 §7): *"a scenario per dynamism-audit
#           row"*.
# Source:   B17 §5 "The dynamism audit", verbatim: *"Events that today do not
#           re-wire: a premises moved between areas (keeps old routes) · a
#           route whose area changes (members not re-derived) · a unit moved
#           between premises (no cascade found on that path) · an account
#           opened/closed (no modelled link at all) · a routed unit with no
#           meter (no service point → invisible to the bill run)."* Plus G4's
#           *"the meter-attach path skips the draft check — a draft route's
#           stamp can reach billing"*.
# Consumed by: RC-W4-T1/T2 (*"the audit's scenarios as tests — each re-scopes
#           correctly at next use"*), RC-W4-T3 (the draft leak), RC-W4-T4
#           (meterless routed units), RC-W4-T5 (account → unit → route → cycle
#           at bill-run time). The schedule half is
#           tests/cr029_schedule_fixtures.py.
# Rules:    D4 (*"yes member resolve at run time"*) — the fixtures RECORD what
#           the stored rows say today and assert nothing about what is right ·
#           BR-MET-076 (a draft affects nothing) · BR-MET-083 (the tagging
#           cascade and its four boundaries) · BR-MET-074 (≤1 route per
#           service) · CLAUDE.md rule 1 (every write inside `tenant_ctx`) ·
#           rule 3 (every meter here declares its UoM) · rule 7 (every write
#           goes through the audited service — no ORM shortcuts).
# Note:     NO MONEY. Routes and cycles are grouping only (BR-MET-078, hardened
#           by this CR), so nothing in this file carries an amount, a rate, a
#           fee or a balance — not even on the account scenario, which stops at
#           opening and closing the account.
# ───────────────────────────────────────────────────────
"""The CR-029 dynamism scenarios — one builder per row of B17 §5's audit.

WHY THESE ARE FIXTURES AND NOT TESTS
------------------------------------
B17 §5 lists five events that *"today do not re-wire"*, and D4 rules the
answer: *"yes member resolve at run time"* — scoping questions are **derived
live** from the current tags at the moment Reads or Billing asks, and stored
rows keep only explicit human choices and immutable history. RC-W4 is the wave
that makes that true. Its tests need each event set up exactly, repeatedly, and
identically to the ones RC-W2 and the seed use — so the SET-UP lives here and
the ASSERTIONS live in RC-W4.

⚠ **EVERY BUILDER RECORDS, IT DOES NOT JUDGE.** Each returns an `observed`
mapping holding what the stored rows say *at the moment the event finished* —
today's behaviour, whatever it is. Nothing here asserts that the observed value
is correct: on four of these six scenarios it is precisely what D4 exists to
change. A fixture that baked in today's answer would go red when RC-W4 fixed
the bug, which is backwards. `tests/test_cr029_w0_fixtures.py` asserts only the
scenario's SHAPE (the rows exist, the event happened, the ids line up).

WHY THIS FILE IS NOT NAMED `test_*`
-----------------------------------
pytest collects `tests/test_*.py`. A helper that defined pytest fixtures AND
was imported by several test modules would register them twice — the failure
mode `tests/cost_of_service_fixtures.py` records (every test in the importing
file errors with `assert not self._finalizers`). So this module holds PLAIN
FUNCTIONS, in the shape of `tests/ledger_le_fixtures.py`.

HOW RC-W4 IS MEANT TO USE THIS
------------------------------
    from tests.cr029_dynamism_fixtures import premises_moved_between_areas

    def test_the_move_re_scopes_at_next_use(brazos, dana):
        with tenant_ctx(brazos):
            s = premises_moved_between_areas(dana, brazos)
            # today: s.observed["stamped_route_code"] is still the NORTH route
            assert derived_route_for(s.unit_id, "water") == s.south_route_code

Every builder takes `(actor, tenant)` and must be called inside `tenant_ctx`
(CLAUDE.md rule 1 — `app.tenant_id` set, RLS FORCE on). `suffix` keeps codes
unique when one test builds several scenarios in one tenant.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from apps.assets import services as asset_services
from apps.customers import services as customer_services
from apps.metering import models, services
from apps.tenancy import models as tenancy_models

from tests import identity_fixtures

# ── vocabulary the fixtures write ──────────────────────────────────────────
#: The frequency these scenarios' cycles carry. B17 §2's business word, which
#: is what `cycles.frequency` stores since RC-W1 landed the vocabulary
#: (`apps/metering/schedule.FREQUENCIES`, commit d47fa88, 2026-08-23) — it was
#: the CR-006 lowercase `monthly` until then, and this constant is the one line
#: that had to move.
SEED_FREQUENCY = "Monthly"

#: Every meter these fixtures create declares its unit of measure — CLAUDE.md
#: rule 3, *"consumption always with an explicit unit; never assume"*.
WATER_UOM = "kgal"
ELECTRIC_UOM = "kWh"

# ── the fixture's dates, literal (BR-TEN-043 — nothing here reads a clock) ──
#: Every dated event these fixtures write is in the PAST and stays there. A
#: fixture that used "today" would be refused by `move_unit`'s future-date
#: guard the moment the tenant's timezone put it a day behind UTC — which is
#: exactly how this constant was found.
ACCOUNT_OPENED_ON = "2026-07-01"
UNIT_MOVED_ON = "2026-08-20"
ACCOUNT_CLOSED_ON = "2026-08-20"
METER_INSTALLED_ON = "2026-06-01"


@dataclass
class Scenario:
    """One dynamism-audit row, built.

    `observed` is what the stored rows said when the event finished — evidence,
    never an expectation. `question` is the sentence B17 §5 asks of this row,
    kept beside the data so the RC-W4 test that consumes it can quote it.
    """

    scenario_id: str
    title: str
    question: str
    ids: dict[str, Any] = field(default_factory=dict)
    observed: dict[str, Any] = field(default_factory=dict)

    def __getitem__(self, key: str) -> Any:  # convenience: s["unit_id"]
        return self.ids[key]


# ═══════════════════════════════════════════════════════════════════════════
# Shared builders — all through the real, audited services (CLAUDE.md rule 7)
# ═══════════════════════════════════════════════════════════════════════════
def make_area(tenant: Any, code: str, name: str, parent: Any = None) -> Any:
    """An area/sub-area. `tenancy.Area` has no create service of its own — the
    S8 reference screen writes it — so the CR-006 test files build it exactly
    this way (`tests/test_br_met_083_cascade.py::make_area`)."""
    return tenancy_models.Area.objects.create(
        tenant_id=tenant.id, code=code, name=name, parent=parent
    )


def owner_for(actor: Any, name: str | None = None) -> str:
    """A typed owner id, REUSING the party if this tenant already holds it.

    ⚠ **THE SECOND COPY OF THIS HELPER, AND THE DUPLICATION IS THE DEFECT'S OWN
    ESCAPE ROUTE (`DEF-650`).** `tests/test_us_met_helpers.py` has one too, and
    when `BR-MET-401` made the owner required at premises creation the first copy
    was updated and this one was not — **616 tests went red from that single
    gap**, because the seeded fixture failed and everything needing seed data
    failed behind it. It is the shape `DEF-1126` names one level up: a contract
    changed, one caller was swept, the other was not.

    Kept as a second copy rather than imported, because this module is imported
    BY `test_us_met_helpers`'s consumers and the reverse import would be a cycle.
    What is not duplicated is the RULE: both copies call the product's own
    `resolve_owner_name`, so neither can drift into inventing a party.
    """
    from apps.metering import premises_owners

    text = (str(name or "").strip()) or "Whitfield Rentals LLC"
    found = premises_owners.resolve_owner_name(text)
    if found["match"] == "exact":
        return str(found["owner"]["id"])
    return str(
        premises_owners.create_premises_owner(
            actor, {"name": text, "category": "landlord"}
        )["id"]
    )


def make_premises(actor: Any, address_line: str, *, area_code: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "address_line": address_line,
        "city": "Katy",
        "state": "TX",
        "postal_code": "77494",
        "premises_type": "single_family",
        "services_available": ["electric", "water"],
        # BR-MET-401 (PO 2026-08-27, DEF-650) — the owner is REQUIRED at
        # creation. See `owner_for` above for why this line is the one that was
        # missed and what it cost.
        "owner_id": owner_for(actor),
    }
    if area_code is not None:
        payload["area_code"] = area_code
    return services.create_premises(actor, payload)


def make_unit(
    actor: Any, premises_id: Any, label: str = "Unit A", *, services_: list[str] | None = None
) -> dict[str, Any]:
    """A unit with NO service point unless the scenario creates one itself.

    ⚠ `DEF-MET-8815` — since `BR-MET-119` was amended (PO 2026-09-25, *"the
    premises' list is what a unit takes, the tick-list stays, and a clerk may
    untick"*, built 630f472c3) a create with NO `services` key inherits the
    address's list, so every unit here silently gained electric + water points
    and the meterless / pointless scenarios stopped being either. `[]` is the
    clerk-unticked case the ruling keeps lawful, and it is the world every
    scenario in this file was written to describe: points appear only where a
    scenario calls `ensure_service_point` or attaches a meter.
    """
    return services.create_unit(
        actor,
        {
            "premises_id": premises_id,
            "label": label,
            "unit_type": "residential",
            "services": [] if services_ is None else services_,
        },
    )


def active_cycle(actor: Any, code: str, name: str = "Monthly reads") -> models.Cycle:
    """A cycle that a bill run can see. `create_cycle` opens it as a draft in
    some paths, so the status is set explicitly — BR-MET-076: *"a draft cycle is
    invisible to a bill run"*, and every scenario here needs a visible one."""
    row = services.create_cycle(actor, {"code": code, "name": name, "frequency": SEED_FREQUENCY})
    models.Cycle.objects.filter(pk=row["id"]).update(status="active")
    return models.Cycle.objects.get(pk=row["id"])


def _route(
    actor: Any,
    *,
    code: str,
    name: str,
    status: str,
    route_type: str = "walk",
    area: Any = None,
    service_code: str | None = None,
    cycle: models.Cycle | None = None,
    unit_ids: list[Any] | None = None,
) -> models.Route:
    """One route, created through the real service and then put into `status`.

    `service_code` is OMITTED rather than sent as None when absent: `_resolve_
    service` reads "key not present" as *leave the column alone* and "key
    present but empty" as *the legacy all-services route*, and those are
    different rows (`tests/test_def227_all_services_route_stamp.py` records the
    distinction and why it is load-bearing).
    """
    payload: dict[str, Any] = {"code": code, "name": name, "route_type": route_type}
    if service_code is not None:
        payload["service_code"] = service_code
    if area is not None:
        payload["area_code"] = area.code
    if cycle is not None:
        payload["cycle_id"] = str(cycle.id)
    if unit_ids:
        payload["unit_ids"] = [str(u) for u in unit_ids]
    created = services.create_route(actor, payload)
    models.Route.objects.filter(pk=created["id"]).update(status=status)
    return models.Route.objects.get(pk=created["id"])


def active_route(actor: Any, **kwargs: Any) -> models.Route:
    return _route(actor, status="active", **kwargs)


def draft_route(actor: Any, **kwargs: Any) -> models.Route:
    """BR-MET-076: *"a draft route stamps no service point"* — so a draft is
    the only way to hold membership that Reads and Billing must not see."""
    return _route(actor, status="draft", **kwargs)


def stamped_route_code(tenant: Any, unit_id: Any, service_code: str) -> str | None:
    """What the unit's service point says its route is, right now — or None
    when the unit has no service point for that service at all."""
    point = models.ServicePoint.objects.filter(
        tenant_id=tenant.id, unit_id=unit_id, service__code=service_code
    ).first()
    if point is None or point.route_id is None:
        return None
    return models.Route.objects.get(pk=point.route_id).code


def stamped_cycle_code(tenant: Any, unit_id: Any, service_code: str) -> str | None:
    point = models.ServicePoint.objects.filter(
        tenant_id=tenant.id, unit_id=unit_id, service__code=service_code
    ).first()
    if point is None or point.cycle_id is None:
        return None
    return models.Cycle.objects.get(pk=point.cycle_id).code


def membership_route_codes(tenant: Any, unit_id: Any) -> list[str]:
    """Every route the unit holds a STORED membership row for, by code."""
    rows = models.RouteMembership.objects.filter(tenant_id=tenant.id, unit_id=unit_id)
    return sorted(models.Route.objects.get(pk=row.route_id).code for row in rows)


def member_unit_ids(tenant: Any, route: models.Route) -> list[str]:
    return sorted(
        str(row.unit_id)
        for row in models.RouteMembership.objects.filter(tenant_id=tenant.id, route=route)
    )


def _meter(
    actor: Any,
    *,
    asset_no: str,
    unit_id: Any,
    service_code: str,
    uom: str,
) -> dict[str, Any]:
    """A meter on a unit, created through the assets service — which is the
    path that calls `ensure_service_point` and therefore the path G4 is about.

    ⚠ The UoM is EXPLICIT (CLAUDE.md rule 3). A meter created without one takes
    the service default, and "took a default" is exactly the assumption the
    rule forbids a fixture from making on the product's behalf.
    """
    return asset_services.create_asset(
        actor,
        {
            "type": "meter",
            "asset_no": asset_no,
            "service": service_code,
            "unit": uom,
            # `read_method` is the ASSET catalog's vocabulary (ami · amr ·
            # manual · mobile · walk_by), which is NOT the route's
            # walk | drive | ami — two lists, two owners, deliberately not
            # merged (BR-AST-043).
            "read_method": "walk_by",
            "multiplier": "1",
            "unit_id": str(unit_id),
            "install_date": METER_INSTALLED_ON,
        },
    )


def _published_plan(tenant: Any, name: str, service_code: str = "water") -> Any:
    """A PUBLISHED rate plan with NO PRICES IN IT — the minimum BR-MET-040 asks.

    ⚠ **This is not money on a route or a cycle, and it is not optional.**
    BR-MET-040: *"Plan is REQUIRED at account activation; a unit without a plan
    blocks with a message"*, and the account DERIVES its plan from the unit (PO
    ruling 2026-08-11). So DYN-6 cannot open an occupying account at all
    without one. What is created is an empty container: a published plan and a
    tariff shell, no rate, no charge, no amount — the same shape
    `tests/test_us_cus_004_005_move_in_out.py::_plan` uses, and for the same
    reason (the plan's CONTENT is EP-RAT-01's story, not this fixture's).
    `status="published"` is load-bearing: BR-RAT-030 makes only published plans
    assignable.
    """
    from apps.rating import models as rating_models

    service = tenancy_models.Service.objects.get(code=service_code)
    plan, _ = rating_models.RatePlan.objects.get_or_create(
        tenant=tenant,
        name=name,
        defaults={"code": name.lower().replace(" ", "-"), "status": "published"},
    )
    tariff, _ = rating_models.Tariff.objects.get_or_create(
        tenant=tenant, name=f"{name} — {service_code}", service=service
    )
    rating_models.PlanRateSchedule.objects.get_or_create(
        tenant=tenant, rate_plan=plan, service=service, defaults={"tariff": tariff}
    )
    return plan


def _account(actor: Any, unit_id: Any, *, opened_on: str, full_name: str) -> dict[str, Any]:
    """An OCCUPYING account on the unit (BR-CUS-017 through `_make_occupying`).

    No money: no deposit, no balance, no plan — the account exists so RC-W4-T5
    can derive account → unit → route → cycle, and D12 removed the Balance
    column from the route's Accounts tab for the same reason.
    """
    return customer_services.create_account(
        actor,
        {
            "unit_id": str(unit_id),
            "account_type": "residential",
            "status": "active",
            "opened_at": opened_on,
            "contact": {"full_name": full_name, "email": "resident@example.test"},
            # `BR-CUS-1024` (PO 2026-09-01) — the door refuses an account whose
            # customer identifies nobody, and this fixture's own name went in above.
            # ONE shape for every fixture in the suite: tests/identity_fixtures.py.
            "customer": identity_fixtures.customer_block(full_name, account_type="residential"),
        },
    )


# ═══════════════════════════════════════════════════════════════════════════
# ROW 1 — *"a premises moved between areas (keeps old routes)"*
# ═══════════════════════════════════════════════════════════════════════════
def premises_moved_between_areas(actor: Any, tenant: Any, suffix: str = "01") -> Scenario:
    """North and South each have a water route; a North premises is routed on
    North's, then its area tag is changed to South.

    The stored membership and the service-point stamp are what they are after
    the move — recorded, not judged. BR-MET-083's fourth boundary says the
    cascade must NOT un-route a premises when its tag changes, so today the
    unit keeps the North route; D4 says the question *"who is on this route
    right now"* must be answered from the CURRENT tag when Reads or Billing
    asks.
    """
    north = make_area(tenant, f"N-{suffix}", "North")
    south = make_area(tenant, f"S-{suffix}", "South")
    cycle = active_cycle(actor, f"CY-DYN1-{suffix}")
    north_route = active_route(
        actor,
        code=f"RT-DYN1N-{suffix}",
        name="North water walk",
        area=north,
        service_code="water",
        cycle=cycle,
    )
    south_route = active_route(
        actor,
        code=f"RT-DYN1S-{suffix}",
        name="South water walk",
        area=south,
        service_code="water",
        cycle=cycle,
    )
    premises = make_premises(actor, f"1408 Bluestem Ln #{suffix}", area_code=north.code)
    unit = make_unit(actor, premises["id"])
    services.ensure_service_point(unit["id"], "water")
    services.update_route(actor, north_route.id, {"unit_ids": [unit["id"]]})

    before = stamped_route_code(tenant, unit["id"], "water")

    # THE EVENT: the premises is re-districted into South.
    services.update_premises(actor, premises["id"], {"area_code": south.code})

    return Scenario(
        scenario_id="DYN-1",
        title="A premises moved between areas",
        question=(
            "B17 §5: a premises moved between areas keeps its old routes. After "
            "re-districting, which route reads this unit at the next window?"
        ),
        ids={
            "premises_id": premises["id"],
            "unit_id": unit["id"],
            "north_area_code": north.code,
            "south_area_code": south.code,
            "north_route_id": str(north_route.id),
            "south_route_id": str(south_route.id),
            "north_route_code": north_route.code,
            "south_route_code": south_route.code,
            "cycle_id": str(cycle.id),
            "cycle_code": cycle.code,
            "service_code": "water",
        },
        observed={
            "stamped_route_code_before_move": before,
            "stamped_route_code_after_move": stamped_route_code(tenant, unit["id"], "water"),
            "membership_route_codes_after_move": membership_route_codes(tenant, unit["id"]),
            "premises_area_code_after_move": south.code,
        },
    )


# ═══════════════════════════════════════════════════════════════════════════
# ROW 2 — *"a route whose area changes (members not re-derived)"*
# ═══════════════════════════════════════════════════════════════════════════
def route_area_changed(actor: Any, tenant: Any, suffix: str = "02") -> Scenario:
    """One route, tagged North, holding a North premises' unit. A second
    premises sits in South and is on no route. The ROUTE's area is then changed
    to South.

    Two facts the scenario makes checkable at once: the old member is still a
    stored member, and the South premises still is not — *"members not
    re-derived"*.
    """
    north = make_area(tenant, f"N-{suffix}", "North")
    south = make_area(tenant, f"S-{suffix}", "South")
    cycle = active_cycle(actor, f"CY-DYN2-{suffix}")
    route = active_route(
        actor,
        code=f"RT-DYN2-{suffix}",
        name="Water walk",
        area=north,
        service_code="water",
        cycle=cycle,
    )
    in_north = make_premises(actor, f"2201 Cane Island Pkwy #{suffix}", area_code=north.code)
    north_unit = make_unit(actor, in_north["id"])
    services.ensure_service_point(north_unit["id"], "water")
    services.update_route(actor, route.id, {"unit_ids": [north_unit["id"]]})

    in_south = make_premises(actor, f"3450 Pin Oak Dr #{suffix}", area_code=south.code)
    south_unit = make_unit(actor, in_south["id"])
    services.ensure_service_point(south_unit["id"], "water")

    members_before = member_unit_ids(tenant, route)

    # THE EVENT: the route is redrawn onto the South area.
    services.update_route(actor, route.id, {"area_code": south.code})

    return Scenario(
        scenario_id="DYN-2",
        title="A route whose area changed",
        question=(
            "B17 §5: a route whose area changes does not re-derive its members. "
            "After the redraw, does the North unit leave and the South unit join?"
        ),
        ids={
            "route_id": str(route.id),
            "route_code": route.code,
            "north_area_code": north.code,
            "south_area_code": south.code,
            "north_premises_id": in_north["id"],
            "south_premises_id": in_south["id"],
            "north_unit_id": north_unit["id"],
            "south_unit_id": south_unit["id"],
            "cycle_id": str(cycle.id),
            "service_code": "water",
        },
        observed={
            "member_unit_ids_before": members_before,
            "member_unit_ids_after": member_unit_ids(tenant, route),
            "route_area_code_after": south.code,
            "south_unit_stamped_route_code": stamped_route_code(tenant, south_unit["id"], "water"),
        },
    )


# ═══════════════════════════════════════════════════════════════════════════
# ROW 3 — *"a unit moved between premises (no cascade found on that path)"*
# ═══════════════════════════════════════════════════════════════════════════
def unit_moved_between_premises(actor: Any, tenant: Any, suffix: str = "03") -> Scenario:
    """A unit on a North premises, routed on North's route, is MOVED to a South
    premises that belongs to South's route (BR-MET-095 — a dated, reasoned move).

    The move service is deliberate and audited; what it does not do is touch
    membership, which is what makes this an audit row rather than a bug report.
    """
    north = make_area(tenant, f"N-{suffix}", "North")
    south = make_area(tenant, f"S-{suffix}", "South")
    cycle = active_cycle(actor, f"CY-DYN3-{suffix}")
    north_route = active_route(
        actor,
        code=f"RT-DYN3N-{suffix}",
        name="North water walk",
        area=north,
        service_code="water",
        cycle=cycle,
    )
    south_route = active_route(
        actor,
        code=f"RT-DYN3S-{suffix}",
        name="South water walk",
        area=south,
        service_code="water",
        cycle=cycle,
    )
    source = make_premises(actor, f"2200 Riverbend Ct #{suffix}", area_code=north.code)
    target = make_premises(actor, f"77 Gulf Fwy #{suffix}", area_code=south.code)
    target_unit = make_unit(actor, target["id"], label="Unit Z")
    services.ensure_service_point(target_unit["id"], "water")
    services.update_route(actor, south_route.id, {"unit_ids": [target_unit["id"]]})

    unit = make_unit(actor, source["id"], label="Unit A")
    services.ensure_service_point(unit["id"], "water")
    services.update_route(actor, north_route.id, {"unit_ids": [unit["id"]]})

    before = stamped_route_code(tenant, unit["id"], "water")

    # THE EVENT: BR-MET-095's dated move — never a bare field write.
    services.move_unit(
        actor,
        unit["id"],
        {
            "premises_id": target["id"],
            "effective_date": UNIT_MOVED_ON,
            "reason": "CR-029 dynamism fixture — the unit physically sits at the other address.",
        },
    )

    return Scenario(
        scenario_id="DYN-3",
        title="A unit moved between premises",
        question=(
            "B17 §5: no cascade was found on the unit-move path. After the move, "
            "which route reads the unit — its old one, or the route its NEW "
            "premises belongs to?"
        ),
        ids={
            "unit_id": unit["id"],
            "source_premises_id": source["id"],
            "target_premises_id": target["id"],
            "north_route_id": str(north_route.id),
            "south_route_id": str(south_route.id),
            "north_route_code": north_route.code,
            "south_route_code": south_route.code,
            "sibling_unit_id": target_unit["id"],
            "cycle_id": str(cycle.id),
            "service_code": "water",
        },
        observed={
            "stamped_route_code_before_move": before,
            "stamped_route_code_after_move": stamped_route_code(tenant, unit["id"], "water"),
            "membership_route_codes_after_move": membership_route_codes(tenant, unit["id"]),
        },
    )


# ═══════════════════════════════════════════════════════════════════════════
# ROW 4 — G4, *"a meter attached to a draft-routed unit"*
# ═══════════════════════════════════════════════════════════════════════════
def meter_attached_to_draft_routed_unit(actor: Any, tenant: Any, suffix: str = "04") -> Scenario:
    """A DRAFT route holds a member unit that has no service point yet; a meter
    is then attached to that unit.

    This is B17's **G4**: *"the meter-attach path skips the draft check — a
    draft route's stamp can reach billing (likely bug, no ruling needed)"*. The
    mechanism is one lookup: `services.ensure_service_point` takes
    `membership.route` (and `membership.route.cycle`) with no filter on
    `route.status`, so the row a draft route wrote in step 2 of the wizard
    becomes a live stamp the moment a meter arrives — and
    `selectors.units_in_cycle`, billing's scope seam, reads exactly that column.

    BR-MET-076 is the rule it breaks: *"a draft route stamps no service point"*.
    RC-W4-T3 fixes it test-first; this fixture is the test's setup and must
    keep REPRODUCING the leak until then, which is why it records the stamp
    rather than asserting it away.
    """
    area = make_area(tenant, f"D-{suffix}", "Draft district")
    cycle = active_cycle(actor, f"CY-DYN4-{suffix}")
    premises = make_premises(actor, f"500 Mason Rd #{suffix}", area_code=area.code)
    unit = make_unit(actor, premises["id"])
    route = draft_route(
        actor,
        code=f"RT-DYN4-{suffix}",
        name="Draft water walk",
        area=area,
        service_code="water",
        cycle=cycle,
        unit_ids=[unit["id"]],
    )

    points_before = models.ServicePoint.objects.filter(
        tenant_id=tenant.id, unit_id=unit["id"]
    ).count()

    # THE EVENT: a meter is attached, which runs `ensure_service_point`.
    asset = _meter(
        actor,
        asset_no=f"M-DYN4-{suffix}",
        unit_id=unit["id"],
        service_code="water",
        uom=WATER_UOM,
    )

    return Scenario(
        scenario_id="DYN-4",
        title="A meter attached to a draft-routed unit (G4)",
        question=(
            "BR-MET-076: a draft route stamps no service point. The unit is a "
            "member of a DRAFT route and a meter has just been attached — does "
            "the draft route's stamp now reach the service point, and through "
            "`units_in_cycle`, the bill run?"
        ),
        ids={
            "unit_id": unit["id"],
            "premises_id": premises["id"],
            "draft_route_id": str(route.id),
            "draft_route_code": route.code,
            "cycle_id": str(cycle.id),
            "cycle_code": cycle.code,
            "asset_id": asset["id"],
            "asset_no": asset["asset_no"],
            "service_code": "water",
            "uom": WATER_UOM,
        },
        observed={
            "route_status": "draft",
            "service_points_before_attach": points_before,
            "stamped_route_code_after_attach": stamped_route_code(tenant, unit["id"], "water"),
            "stamped_cycle_code_after_attach": stamped_cycle_code(tenant, unit["id"], "water"),
            "membership_route_codes": membership_route_codes(tenant, unit["id"]),
        },
    )


# ═══════════════════════════════════════════════════════════════════════════
# ROW 5 — *"a routed unit with no meter (no service point → invisible)"*
# ═══════════════════════════════════════════════════════════════════════════
def routed_unit_with_no_meter(actor: Any, tenant: Any, suffix: str = "05") -> Scenario:
    """A unit that is a member of a live route and has NO meter and NO service
    point at all — so nothing in Reads or Billing can see it.

    A second unit at the same premises DOES have a meter, so the scenario can
    tell "this route is empty" apart from "this route has a hole in it", which
    is what RC-W4-T4 (*"meterless routed units become billable-visible"*) has
    to be able to report. The upgraded prototype's SET-06.4 review step calls
    them *"No meter · verify · 3"*.
    """
    area = make_area(tenant, f"M-{suffix}", "Meterless district")
    cycle = active_cycle(actor, f"CY-DYN5-{suffix}")
    premises = make_premises(actor, f"3450 Pin Oak Dr #{suffix}", area_code=area.code)
    metered = make_unit(actor, premises["id"], label="Unit A")
    bare = make_unit(actor, premises["id"], label="Unit B")
    services.ensure_service_point(metered["id"], "water")
    route = active_route(
        actor,
        code=f"RT-DYN5-{suffix}",
        name="Pin Oak water walk",
        area=area,
        service_code="water",
        cycle=cycle,
        unit_ids=[metered["id"], bare["id"]],
    )
    asset = _meter(
        actor,
        asset_no=f"M-DYN5-{suffix}",
        unit_id=metered["id"],
        service_code="water",
        uom=WATER_UOM,
    )

    return Scenario(
        scenario_id="DYN-5",
        title="A routed unit with no meter",
        question=(
            "B17 §5: a routed unit with no meter has no service point, so the "
            "bill run cannot see it. Does the route report it as a hole "
            '(SET-06.4\'s "No meter · verify") rather than silently omitting it?'
        ),
        ids={
            "route_id": str(route.id),
            "route_code": route.code,
            "premises_id": premises["id"],
            "metered_unit_id": metered["id"],
            "meterless_unit_id": bare["id"],
            "cycle_id": str(cycle.id),
            "asset_id": asset["id"],
            "service_code": "water",
            "uom": WATER_UOM,
        },
        observed={
            "member_unit_ids": member_unit_ids(tenant, route),
            "meterless_unit_service_points": models.ServicePoint.objects.filter(
                tenant_id=tenant.id, unit_id=bare["id"]
            ).count(),
            "metered_unit_stamped_route_code": stamped_route_code(tenant, metered["id"], "water"),
            "meterless_unit_stamped_route_code": stamped_route_code(tenant, bare["id"], "water"),
        },
    )


# ═══════════════════════════════════════════════════════════════════════════
# ROW 6 — *"an account opened/closed (no modelled link at all)"*
# ═══════════════════════════════════════════════════════════════════════════
def account_opened_and_closed_on_a_routed_unit(
    actor: Any, tenant: Any, suffix: str = "06"
) -> Scenario:
    """One routed, metered unit; an account is opened on it and then moved out.
    A SECOND routed unit keeps its account open, so the scenario holds both
    states at once.

    D13 rules what this is for: *"Cycles are not directlya ssing to accounts it
    is derived and determined at the time of bill run"*. So RC-W4-T5 derives
    account → unit → route → cycle live, and the coverage question (*"is anyone
    uncovered?"*) is answered from these two accounts — one that should be in
    the cycle's scope and one that should have dropped out of it.

    No money (BR-MET-078 / D12): the accounts are opened and closed and nothing
    is billed, charged or deposited.
    """
    area = make_area(tenant, f"A-{suffix}", "Accounts district")
    cycle = active_cycle(actor, f"CY-DYN6-{suffix}")
    premises = make_premises(actor, f"1408 Elm St #{suffix}", area_code=area.code)
    closing_unit = make_unit(actor, premises["id"], label="Unit A")
    staying_unit = make_unit(actor, premises["id"], label="Unit B")
    services.ensure_service_point(closing_unit["id"], "water")
    services.ensure_service_point(staying_unit["id"], "water")
    route = active_route(
        actor,
        code=f"RT-DYN6-{suffix}",
        name="Elm St water walk",
        area=area,
        service_code="water",
        cycle=cycle,
        unit_ids=[closing_unit["id"], staying_unit["id"]],
    )
    _meter(
        actor,
        asset_no=f"M-DYN6A-{suffix}",
        unit_id=closing_unit["id"],
        service_code="water",
        uom=WATER_UOM,
    )
    _meter(
        actor,
        asset_no=f"M-DYN6B-{suffix}",
        unit_id=staying_unit["id"],
        service_code="water",
        uom=WATER_UOM,
    )

    # BR-MET-040 — an account cannot ACTIVATE on a unit with no plan, and the
    # account derives its plan from the unit. See `_published_plan`: an empty
    # published container, no prices.
    plan = _published_plan(tenant, f"CR-029 fixture plan {suffix}")
    for unit_id in (closing_unit["id"], staying_unit["id"]):
        services.assign_unit_plan(actor, unit_id, {"tariff_id": str(plan.id)})

    closing = _account(
        actor, closing_unit["id"], opened_on=ACCOUNT_OPENED_ON, full_name="Elena Rivera"
    )
    staying = _account(
        actor, staying_unit["id"], opened_on=ACCOUNT_OPENED_ON, full_name="Marcus Vega"
    )

    # THE EVENT: one occupant leaves (BR-CUS-030); the other stays.
    closed = customer_services.move_out(actor, closing["id"], {"moved_out_on": ACCOUNT_CLOSED_ON})

    return Scenario(
        scenario_id="DYN-6",
        title="An account opened and closed on a routed unit",
        question=(
            "B17 §5: an account has no modelled link to a cycle at all. D13: the "
            "cycle derives account -> unit -> route -> cycle at bill-run time. Is "
            "the closed account out of the cycle's scope and the open one in it?"
        ),
        ids={
            "route_id": str(route.id),
            "route_code": route.code,
            "cycle_id": str(cycle.id),
            "cycle_code": cycle.code,
            "premises_id": premises["id"],
            "closed_unit_id": closing_unit["id"],
            "open_unit_id": staying_unit["id"],
            "closed_account_id": closing["id"],
            "open_account_id": staying["id"],
            "service_code": "water",
            "uom": WATER_UOM,
        },
        observed={
            "closed_account_status": closed.get("status"),
            "closed_account_closed_at": closed.get("closed_at"),
            "open_account_status": staying.get("status"),
            "closed_unit_stamped_cycle_code": stamped_cycle_code(
                tenant, closing_unit["id"], "water"
            ),
            "open_unit_stamped_cycle_code": stamped_cycle_code(tenant, staying_unit["id"], "water"),
        },
    )


# ═══════════════════════════════════════════════════════════════════════════
# The audit, as a table — B17 §5's five rows plus G4
# ═══════════════════════════════════════════════════════════════════════════
#: `(scenario_id, builder, the wave task that consumes it)`. RC-W4-T2 is
#: *"the audit's scenarios as tests"* — it iterates this.
DYNAMISM_AUDIT: tuple[tuple[str, Any, str], ...] = (
    ("DYN-1", premises_moved_between_areas, "RC-W4-T1/T2"),
    ("DYN-2", route_area_changed, "RC-W4-T1/T2"),
    ("DYN-3", unit_moved_between_premises, "RC-W4-T1/T2"),
    ("DYN-4", meter_attached_to_draft_routed_unit, "RC-W4-T3"),
    ("DYN-5", routed_unit_with_no_meter, "RC-W4-T4"),
    ("DYN-6", account_opened_and_closed_on_a_routed_unit, "RC-W4-T5"),
)


def build_all(actor: Any, tenant: Any) -> dict[str, Scenario]:
    """Every scenario in one tenant, with distinct codes — the shape RC-W4-T2
    needs when it asserts that each one re-scopes correctly at next use."""
    return {
        scenario_id: builder(actor, tenant, suffix=scenario_id.replace("DYN-", "0"))
        for scenario_id, builder, _consumer in DYNAMISM_AUDIT
    }
