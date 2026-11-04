# ── Trace ──────────────────────────────────────────────
# Change:   CR-029 (Routes & Cycles) — wave RC-W4, task W4-T1 (B17 §7):
#           *"Derived membership through the tags at the moment Reads or
#           Billing asks; stored rows keep only human choices and immutable
#           history."*
# Ruling:   PO, verbatim 2026-08-23: *"D4 yes member resolve at run time"* and
#           *"D13 - Cycles are not directlya ssing to accounts it is derived and
#           determined at the time of bill run"*.
# Rules:    BR-MET-082 + Amendment 1 (a route is a cascade, not a list;
#           resolution at RUN TIME; a varying count run-to-run is CORRECT) ·
#           BR-MET-074 (≤1 route per service) · BR-MET-076 (a draft affects
#           nothing) · BR-MET-078 (no money) · D10 (a route serves a service
#           SET) · CLAUDE.md rule 1 (every read tenant-scoped).
# Defects:  DEF-225 · DEF-249 — both close by construction here.
# Tests:    tests/test_cr029_rcw4_derivation.py (RED first at the commit before
#           this one: `ImportError: cannot import name 'derivation'`).
# ───────────────────────────────────────────────────────
"""D4 — *who is on this route right now?*, asked instead of remembered.

WHAT THIS MODULE IS
-------------------
B17 §5, verbatim: *"scoping questions — who is on this route right now? which
units does CY-001 bill? is anyone uncovered? — are **derived live** from the
current tags at the moment Reads or Billing asks. Stored rows keep exactly two
jobs: **explicit human choices** (a hand-picked premises, an excluded meter, a
walk order) and **immutable history** (the route stamped on each collected read,
which audits and delete-guards depend on)."*

So this module answers the scoping questions and writes nothing. Every stored
row it reads is read as EVIDENCE OF A HUMAN CHOICE, never as the answer itself.

⚠ **THERE IS NO CASCADE IN HERE, AND THERE MUST NEVER BE.** B17 §7 W4-T1 makes
that the acceptance test: *"every RED row of B17 §5's dynamism audit turns green
with NO new cascade code — that is the test of whether you did it right. If you
find yourself adding a cascade to patch a stored row, you have built the old
design again."* Nothing below writes to the database.

THE RESOLUTION, IN ONE PARAGRAPH
--------------------------------
For one unit and one service, exactly one ACTIVE route may claim it, and there
are three ways to claim. They are the three links of the tag chain B17 §5 names
— `area→routes · premises→units · unit→service & account` — and they are ranked
in BR-MET-083's own order (*"siblings win ties per service"*):

1. **BY HAND** — a `route_memberships` row for this unit. That row is the
   *"hand-picked premises"* B17 protects.
2. **BY PREMISES** — a SIBLING unit at the same building holds such a row.
   BR-MET-082 clause 2: *"Grouping a premises groups every unit in it."*
3. **BY AREA** — the route carries an area and the unit's premises is tagged
   into it or into one of its sub-areas. The upgraded prototype states it as
   product copy where members render: *"Members derive from area tags — changes
   apply at the next read window."*

⚠ **TWO GATES, AND THEY ARE THE WHOLE JUDGMENT IN THIS MODULE.** Both are stated
here because both had a wrong wider version that a test caught.

**GATE 1 — A PICK GOES STALE WHEN THE PREMISES IS RE-TAGGED OUT OF THE ROUTE'S
AREA, AND ONLY THEN** (`_pick_is_live`). A membership on an area-drawn route is
how `cascade_area_to_routes` writes membership and how SET-06 step 2's
area-filtered picker selects it; the choice underneath it is *"this building is
in North"*, so when the building leaves North the choice has been revised. It is
**not** stale when the route has no area (a pure hand-pick no tag can
contradict) and **not** stale when the premises has no area (`premises.area_id`
is nullable and every premises predates the column — the ordinary state of a
shipped tenant).

**GATE 2 — THE AREA FILLS A ROUTE THAT HOLDS NO LIVE PICK; IT NEVER OVERRULES
ONE.** SET-06 step 2 lets an admin choose a DELIBERATE SUBSET of an area's
premises. Adding the rest of the area back here would overrule that decision
and, because this is billing's scope seam, would put premises **nobody selected
into a bill run** — the one direction a guess must never take. So a route still
holding a live pick is defined by its picks; a route holding none is defined by
its area. Re-drawing a route's area makes its old picks stale, which is what
turns it back into an area route and makes B17 §5's row 2 green.

**Worked, on B17 §5's own first row (DYN-1 in the RC-W0 fixtures):** RT-DYN1N
covers area North, RT-DYN1S covers South, and unit U at 1408 Bluestem Ln is a
stored member of RT-DYN1N. The premises is re-districted into South. The stored
row still says RT-DYN1N and the service point is still stamped RT-DYN1N — and
this module answers **RT-DYN1S**, because North's claim was the North tag, the
North tag is gone, and RT-DYN1S holds no pick of its own so its area answers. No
row was rewritten to make that true.

WHAT THIS SUPERSEDES, STATED RATHER THAN IMPLIED (hard-won law 1)
----------------------------------------------------------------
`BR-MET-083` boundary 4 says *"UNTAGGING CASCADES NOTHING OFF — clearing or
changing a premises' area does not remove it from routes it is already on"*. That
boundary is about the STORED row and it still holds exactly as written: nothing
here deletes a membership, and removing a premises from a route is still the
wizard's audited act. What D4 changes is which question the stored row answers.
B17 §5 lists that same event as a RED row D4 collapses, so the derived answer
follows the tag while the stored row stays put — and both halves are asserted
together in every scenario test.

PERFORMANCE IS A CORRECTNESS CONCERN (B17 §7's standing instruction)
--------------------------------------------------------------------
Deriving live means the read path does more work, so it is done in a **fixed**
number of queries — seven in the resolution, plus the two that bound the
candidate set — whatever the size of the route or the cycle. Nothing below loops
a query, and that includes looping over ROUTES: the area tree is read once into
a dict rather than through `selectors._area_ids_for` per route, because an N+1
whose N is the number of routes in a cycle is invisible to a one-route fixture.
`tests/test_cr029_rcw4_derivation.py` asserts the count is identical for a
2-unit route and an 8-unit route, which is the shape of the N+1 D7 already ruled
against.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db.models import Q

from apps.metering import models
from core import tenancy as core_tenancy

#: The service key a resolution uses when the unit's service is genuinely
#: unknown — a unit with no service point at all, claimed by a legacy
#: ALL-SERVICES route (`routes.service_id` NULL and no `route_services` rows).
#: It is NOT a service code and never reaches an API payload; it exists so that
#: "this unit is on this route" stays answerable when "for which service" has no
#: recorded answer. `route_for_unit(unit, "water")` falls back to it.
ANY_SERVICE = "*"

#: Claim ranks — lower wins, and the order is BR-MET-083's own: *"Siblings come
#: FIRST and win ties per service: where a human has put unit A on a route, unit
#: B joins unit A, not whatever the area says it should be."* A unit's own pick
#: outranks its siblings', which outranks the area.
_RANK_PICKED = 0
_RANK_SIBLING = 1
_RANK_AREA = 2


@dataclass(frozen=True)
class DerivedRoute:
    """One resolved answer. NO MONEY (BR-MET-078) and no stored-row identity —
    a membership row id would invite a caller to treat this as the row it came
    from, and on three of the audit's six rows it did not come from one."""

    unit_id: str
    service_code: str
    route_id: str
    route_code: str
    cycle_id: str | None
    cycle_code: str | None
    #: `"picked"` (a human put this unit here), `"premises"` (a human put its
    #: BUILDING here and BR-MET-082 clause 2 groups every unit in it) or
    #: `"area"` (the tag puts it here). The SET-06D audit tab renders the
    #: difference — *"12 premises moved in from RT-002 (re-districting)"* is an
    #: area claim; an exclusion is a pick.
    basis: str


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def seams_service_ids(codes: list[str]) -> list[Any]:
    """The catalog ids for a run's service scope, through metering's own seam —
    the same resolution `units_in_cycle` used before it derived."""
    from apps.metering import seams

    return list(seams.service_ids_for_codes(codes))


def _area_parents() -> dict[str, str | None]:
    """`{area id: parent id}` for the whole tenant, in one read.

    `selectors._area_ids_for` documents the size — *"a per-tenant list of at
    most a few dozen rows"* — and reading it whole is what keeps the query
    count flat as routes and areas multiply.
    """
    from apps.tenancy import models as tenancy_models

    return {
        str(row_id): (str(parent_id) if parent_id else None)
        for row_id, parent_id in tenancy_models.Area.objects.filter(
            tenant_id=_tenant_id()
        ).values_list("id", "parent_id")
    }


def _covering_areas(area_id: str | None, parents: dict[str, str | None]) -> set[str]:
    """The areas whose route covers a premises tagged into `area_id` — itself
    and its parent, which is `services._routes_for_area`'s own one-level walk
    (BR-MET-066b: two levels, exactly)."""
    if not area_id:
        return set()
    covering = {area_id}
    parent = parents.get(area_id)
    if parent:
        covering.add(parent)
    return covering


def _pick_is_live(route: models.Route, premises_area_id: str | None, parents: dict) -> bool:
    """Is this stored membership still the choice a human made?

    ⚠ **THE NARROW TEST, AND THE WIDE ONE WAS WRONG.** A row is stale only when
    the premises carries an area tag that the route's area no longer covers —
    the premises has been re-districted out from under the pick, which is B17
    §5's row 1 exactly. Two cases that look similar and are NOT stale:

    * **the route has no area** — a pure hand-pick, which no tag can contradict.
      B17 §5 protects it: *"stored rows keep … explicit human choices (a
      hand-picked premises …)"*.
    * **the premises has no area** — `premises.area_id` is nullable and *"every
      premises in every tenant predates the column"*, so an untagged building
      hand-picked onto an area-drawn route is the ordinary state of a shipped
      tenant, not a stale projection. Treating it as one emptied a live route
      and dropped its unit out of the bill run — caught by
      `test_def227_all_services_route_stamp.py::test_the_stolen_point_falls_out
      _of_the_bill_run`, which is the money-shaped test written for exactly that
      shape of mistake.
    """
    if route.area_id is None or premises_area_id is None:
        return True
    return str(route.area_id) in _covering_areas(premises_area_id, parents)


# ═══════════════════════════════════════════════════════════════════════════
# THE GRAPH — every fact the resolution needs, loaded in seven queries
# ═══════════════════════════════════════════════════════════════════════════
class Resolution:
    """The derived membership of a bounded set of units, resolved once.

    Built for a set of unit ids because the resolution of one unit depends on
    nothing about any other unit — so narrowing to the units a question is about
    is exact, not approximate. `units_in_cycle` and `members_of_route` build the
    candidate set first and hand it here.
    """

    def __init__(
        self,
        unit_ids: list[Any],
        *,
        premises_override: dict[str, tuple[Any, Any]] | None = None,
    ) -> None:
        """`premises_override` answers *"and if this unit were somewhere else?"*

        ⚠ **IT IS OPTIONAL AND ABSENT MEANS NOTHING CHANGES.** Every existing
        caller — `units_in_cycle`, `members_of_route`, `route_for_unit`,
        `routes_for_unit` — resolves byte-for-byte as before, because the
        override is applied to the ROW LIST step 2 already reads and to nothing
        else.

        `{unit id: (premises id, area id)}`. It exists for one question and one
        caller: `move_preview` has to name the route and cycle a unit will be
        read on AFTER a move, and BR-MET-082 clause 2 makes that a fact about
        the DESTINATION building — *"grouping a premises groups every unit in
        it"*, which `_resolve_one` reads through `self._premises_picks`.
        Resolving the destination's OWN units instead would be an approximation
        in the two cases the answer is most likely to be read for: it cannot see
        this unit's service set (a unit taking water resolves against a water
        route, whatever its new neighbours take), and it cannot see a pick on
        THIS unit that survives the move because the destination is still inside
        the picked route's area.

        ⛔ **IT WRITES NOTHING AND MUST NOT BE MADE TO.** A move is committed by
        `services.move_unit`; this is the read that lets a screen state the
        consequence before the press.
        """
        tenant_id = _tenant_id()
        self.unit_ids: list[str] = list(dict.fromkeys(str(value) for value in unit_ids))
        self.by_unit: dict[str, dict[str, DerivedRoute]] = {}
        self.routes: dict[str, models.Route] = {}
        self.stored_order: dict[tuple[str, str], int | None] = {}
        self.unit_services: dict[str, set[str]] = {}
        self._service_set_map: dict[str, list[str]] = {}
        if not self.unit_ids:
            return

        # 1 · the area tree, in one read. BR-MET-083 boundary 3: *"A PARENT'S
        #     ROUTE COVERS ITS SUB-AREAS"* — a premises tagged `SOUTH-SE` joins
        #     a route drawn for `SOUTH`. Read here exactly as
        #     `services._routes_for_area` reads it, so the two cannot disagree.
        #     The whole table, because `selectors._area_ids_for` already
        #     documents it as *"a per-tenant list of at most a few dozen rows"*
        #     and one read is what keeps the query count flat.
        parents = _area_parents()

        # 2 · the units, with the premises tag that routes them.
        units = list(
            models.Unit.objects.filter(
                tenant_id=tenant_id,
                id__in=self.unit_ids,
                deleted_at__isnull=True,
                premises__deleted_at__isnull=True,
            ).values_list("id", "premises_id", "premises__area_id")
        )
        if premises_override:
            # The ONE place the override lands. Everything downstream — the
            # covering areas of step 4, the sibling picks of step 6 and
            # `_resolve_one` itself — reads this list, so re-tagging it here is
            # the whole of "resolve as if the unit had already moved".
            units = [
                (
                    unit_id,
                    *(premises_override.get(str(unit_id)) or (premises_id, area_id)),
                )
                for unit_id, premises_id, area_id in units
            ]

        # 3 · the stored human choices — ⚠ **PER PREMISES (`CR-131-BRC07`).**
        #
        #     PO ruling 2026-09-22: a route stores WHICH BUILDINGS are on it and
        #     derives everything inside them. So the pick is read from
        #     `route_premises_memberships` and reaches every unit of the
        #     building — which is `BR-MET-082` clause 2, *"grouping a premises
        #     groups every unit in it"*, now expressed in the stored grain
        #     instead of being reconstructed from 726 rows that all said the
        #     same thing.
        #
        #     ⚠ **`by_hand` AND `by_sibling` COLLAPSE INTO ONE, AND THE `basis`
        #     A UNIT REPORTS CHANGES FROM `"premises"` TO `"picked"` FOR THE
        #     SIBLINGS.** That is honest — a human picked the BUILDING, so every
        #     unit in it is picked and none of them is a bystander — and it is
        #     called out because `move_preview` publishes `basis` in its API
        #     payload. No screen renders the word (checked, 2026-09-22: the
        #     front end carries no catalogue key for it), so this changes a
        #     value nothing displays; if one ever does, it will say the truer
        #     thing.
        memberships: dict[str, set[str]] = {}
        member_route_ids: set[str] = set()
        premises_of_unit = {
            str(unit_id): str(premises_id) for unit_id, premises_id, _area in units
        }
        picked_premises = sorted({value for value in premises_of_unit.values()})
        routes_by_premises: dict[str, set[str]] = {}
        for premises_id, route_id in models.RoutePremisesMembership.objects.filter(
            tenant_id=tenant_id, premises_id__in=picked_premises
        ).values_list("premises_id", "route_id"):
            routes_by_premises.setdefault(str(premises_id), set()).add(str(route_id))
            member_route_ids.add(str(route_id))
        for unit_id, premises_id in premises_of_unit.items():
            found = routes_by_premises.get(premises_id)
            if found:
                memberships[unit_id] = set(found)
        # ⚠ **THE SUPERSEDED PER-UNIT ORDER IS NO LONGER READ, AND IT IS 0 ROWS
        # EITHER WAY.** `route_memberships.walk_order` has never had a writer
        # (B17 §5 gap G5) and `selectors._ordered_members` overrides whatever it
        # returns with the stop number from `route_premises_orders` — the ruled
        # grain, re-affirmed by the PO on 2026-09-22 (*"a is okay"*). The map is
        # kept, empty, because callers read it and an absent key is the same
        # answer a null column gave.
        self.stored_order = {}

        # 4 · the ACTIVE routes that could possibly claim one of these units —
        #     drawn over one of their areas, or naming one of them by hand.
        #     BR-MET-076: a DRAFT route stamps nothing and answers nothing, and
        #     IS-1's INACTIVE *"used to run and no longer does"* is the same
        #     silence with its history intact.
        covering_area_ids: set[str] = set()
        for _unit_id, _premises_id, area_id in units:
            covering_area_ids |= _covering_areas(str(area_id) if area_id else None, parents)
        route_filter = Q(pk__in=member_route_ids) if member_route_ids else Q(pk__in=[])
        if covering_area_ids:
            route_filter = route_filter | Q(area_id__in=list(covering_area_ids))
        routes = list(
            models.Route.objects.filter(tenant_id=tenant_id, status="active")
            .filter(route_filter)
            .select_related("cycle", "service")
            .order_by("code", "id")
        )
        self.routes = {str(row.id): row for row in routes}

        # 5 · D10 — the route's service SET. The head `routes.service_id` is the
        #     transitional projection of its first member; the SET is what the
        #     route reads, and resolving against it is what closes W4-T6's hole.
        service_set: dict[str, list[str]] = {}
        for route_id, code in models.RouteService.objects.filter(
            tenant_id=tenant_id, route_id__in=list(self.routes)
        ).values_list("route_id", "service__code"):
            service_set.setdefault(str(route_id), []).append(code)
        self._service_set_map = service_set

        # 6 · ⚠ DOES EACH CANDIDATE ROUTE STILL HOLD A LIVE PICK? — the fact the
        #     AREA claim is gated on. See `_resolve_one`. Every membership row of
        #     these routes, with the premises tag that decides whether it is
        #     still live; one read for the whole set.
        #     The same read answers BR-MET-082 clause 2 — *"grouping a premises
        #     groups every unit in it"* — by recording which PREMISES hold a live
        #     pick on which route, so a unit joins the route its siblings are on.
        #     ⚠ **READ FROM `route_premises_memberships` (`CR-131-BRC07`).** A
        #     row IS a statement about a building, so the join through units is
        #     gone and with it the last place a route's cost grew with its UNIT
        #     count rather than its PREMISES count.
        self._has_live_pick: set[str] = set()
        self._premises_picks: dict[str, set[str]] = {}
        for route_id, premises_id, area_id in models.RoutePremisesMembership.objects.filter(
            tenant_id=tenant_id, route_id__in=list(self.routes)
        ).values_list("route_id", "premises_id", "premises__area_id"):
            # ⚠ **THE OVERRIDE IS A FACT ABOUT A UNIT AND THIS ROW IS A FACT
            # ABOUT A BUILDING, SO IT DOES NOT APPLY HERE ANY MORE.** Moving a
            # unit out of a building does not move the building's pick — the
            # pick stays exactly where it is, and it is the MOVING unit whose
            # premises changes. `units` above already carries the override, so
            # `_resolve_one` looks the unit up under its DESTINATION building
            # and finds that building's picks. The preview answers the same
            # question it always did, one hop earlier.
            route = self.routes[str(route_id)]
            if _pick_is_live(route, str(area_id) if area_id else None, parents):
                self._has_live_pick.add(str(route_id))
                self._premises_picks.setdefault(str(premises_id), set()).add(str(route_id))

        # 7 · the unit→service tag. A unit's service points are what it actually
        #     takes; a unit with NONE is W4-T4's meterless routed unit, and the
        #     route's set is then the only answer available.
        unit_services: dict[str, set[str]] = {}
        for unit_id, code in models.ServicePoint.objects.filter(
            tenant_id=tenant_id, unit_id__in=self.unit_ids, deleted_at__isnull=True
        ).values_list("unit_id", "service__code"):
            unit_services.setdefault(str(unit_id), set()).add(code)
        self.unit_services = unit_services

        for unit_id, premises_id, area_id in units:
            self.by_unit[str(unit_id)] = self._resolve_one(
                unit_id=str(unit_id),
                premises_id=str(premises_id),
                area_id=str(area_id) if area_id else None,
                parents=parents,
                picked=memberships.get(str(unit_id), set()),
                takes=unit_services.get(str(unit_id), set()),
            )

    # ── one unit ───────────────────────────────────────────────────────────
    def _resolve_one(
        self,
        *,
        unit_id: str,
        premises_id: str,
        area_id: str | None,
        parents: dict[str, str | None],
        picked: set[str],
        takes: set[str],
    ) -> dict[str, DerivedRoute]:
        covering = _covering_areas(area_id, parents)
        # BR-MET-082 clause 2, verbatim: *"Grouping a premises groups every unit
        # in it."* A sibling's live pick is a human's statement about THIS
        # BUILDING, so it reaches every unit in it — which is what carries a unit
        # that has just been MOVED to a routed premises (B17 §5 row 3) onto that
        # premises' route with no cascade on the move path.
        siblings = self._premises_picks.get(premises_id, set())

        claims: dict[str, list[tuple[int, str, models.Route, str]]] = {}
        for route_id, route in self.routes.items():
            by_area = route.area_id is not None and str(route.area_id) in covering
            by_hand = route_id in picked
            by_sibling = route_id in siblings and not by_hand
            if not by_area and not by_hand and not by_sibling:
                continue
            if by_hand and not _pick_is_live(route, area_id, parents):
                # ⚠ A STALE PICK — the premises this row was written for has
                # been re-tagged out of the route's area. See `_pick_is_live`;
                # this branch is what makes B17 §5's rows 1, 2 and 3 turn green
                # without a line of cascade code.
                continue
            if by_area and not by_hand and not by_sibling and route_id in self._has_live_pick:
                # ⚠ THE AREA FILLS AN EMPTY ROUTE, IT DOES NOT OVERRULE A PICKED
                # ONE. SET-06 step 2 lets an admin choose a DELIBERATE SUBSET of
                # an area's premises, and adding the rest back here would be
                # this function overruling a human decision — and putting
                # premises nobody selected into a BILL RUN, which is the one
                # direction a guess must never take (*"guesses in billing become
                # silent production errors"*). So a route that still holds a live
                # pick is defined by its picks, and a route holding none is
                # defined by its area. Both halves are what turn DYN-2 green:
                # re-drawing a route's area makes its old picks stale, and the
                # route is then an area route again.
                continue
            if by_hand:
                basis, rank = "picked", _RANK_PICKED
            elif by_sibling:
                basis, rank = "premises", _RANK_SIBLING
            else:
                basis, rank = "area", _RANK_AREA
            for code in self._codes_for(route_id, route, takes):
                claims.setdefault(code, []).append((rank, route.code, route, basis))

        resolved: dict[str, DerivedRoute] = {}
        for code, entries in claims.items():
            rank, _code, route, basis = min(entries, key=lambda entry: (entry[0], entry[1]))
            resolved[code] = DerivedRoute(
                unit_id=unit_id,
                service_code=code,
                route_id=str(route.id),
                route_code=route.code,
                cycle_id=str(route.cycle_id) if route.cycle_id else None,
                cycle_code=route.cycle.code if route.cycle_id else None,
                basis=basis,
            )
        return resolved

    def _codes_for(self, route_id: str, route: models.Route, takes: set[str]) -> list[str]:
        """Which services this route reads AT THIS UNIT.

        Three cases, and the middle one is W4-T4:

        * the route serves a SET and the unit takes some of them → the overlap.
          A water-only unit on a "Water + Electric" route is read for water and
          is NOT put into an electric run it has no meter for.
        * the route serves a SET and the unit takes **nothing** → the whole set.
          A routed unit with no meter has no service point (B17 §5 row 5), and
          W4-T4 rules that it *"becomes billable-visible"* rather than dropping
          silently out of every run — base-only billing is a staff choice
          (CLAUDE.md law 10) and a base-only unit is exactly this unit.
        * the route serves NOTHING (the legacy all-services route) → the unit's
          own services, or `ANY_SERVICE` when it has none.
        """
        codes = self._service_set(route_id, route)
        if codes is None:
            return sorted(takes) if takes else [ANY_SERVICE]
        if not takes:
            return sorted(codes)
        overlap = sorted(set(codes) & takes)
        return overlap

    def _service_set(self, route_id: str, route: models.Route) -> list[str] | None:
        stored = self._service_set_map.get(route_id)
        if stored:
            return stored
        # A route created before D10's `route_services` table, or one whose set
        # was never written: the transitional head is then the whole set.
        if route.service_id:
            return [route.service.code]
        return None

    # ── the questions ──────────────────────────────────────────────────────
    def for_unit(self, unit_id: Any, service_code: str) -> DerivedRoute | None:
        answers = self.by_unit.get(str(unit_id), {})
        return answers.get(service_code) or answers.get(ANY_SERVICE)

    def routes_of(self, unit_id: Any) -> dict[str, DerivedRoute]:
        return self.by_unit.get(str(unit_id), {})

    def units_of_route(self, route_id: Any) -> list[str]:
        wanted = str(route_id)
        return [
            unit_id
            for unit_id in self.unit_ids
            if any(answer.route_id == wanted for answer in self.by_unit.get(unit_id, {}).values())
        ]


# ═══════════════════════════════════════════════════════════════════════════
# CANDIDATES — the bounded set of units a question could possibly be about
# ═══════════════════════════════════════════════════════════════════════════
def _candidate_unit_ids(routes: list[models.Route]) -> list[str]:
    """Every unit one of these routes could claim: the units its area covers,
    plus the units a human named on it. Two queries, whatever the size."""
    if not routes:
        return []
    tenant_id = _tenant_id()
    route_ids = [route.id for route in routes]
    area_ids = [route.area_id for route in routes if route.area_id is not None]
    found: dict[str, None] = {}
    if area_ids:
        # A route drawn for SOUTH covers SOUTH · SE — the same sentence
        # `_routes_for_area` reads upward for one premises, read downward here.
        #
        # ⚠ **ONE READ FOR THE WHOLE AREA TREE, not `selectors._area_ids_for`
        # per route.** That selector runs its own query, so calling it in this
        # loop would make the query count grow with the number of ROUTES in the
        # cycle — an N+1 whose N is small enough that a one-route fixture could
        # never see it, which is exactly how D7's original N+1 survived.
        parents = _area_parents()
        children: dict[str, list[str]] = {}
        for area_id, parent_id in parents.items():
            if parent_id:
                children.setdefault(parent_id, []).append(area_id)
        covered: list[str] = []
        for area_id in area_ids:
            covered.append(str(area_id))
            covered.extend(children.get(str(area_id), []))
        if covered:
            for unit_id in (
                models.Unit.objects.filter(
                    tenant_id=tenant_id,
                    premises__area_id__in=covered,
                    premises__deleted_at__isnull=True,
                    deleted_at__isnull=True,
                )
                .order_by("id")
                .values_list("id", flat=True)
            ):
                found.setdefault(str(unit_id), None)
    # ⚠ **THE HAND-NAMED HALF IS NOW *THE UNITS OF THE BUILDINGS A HUMAN
    # NAMED* (`CR-131-BRC07`).** Two queries still, whatever the size: the
    # route's premises, then their units. It cannot be one join through
    # `route_memberships` any more and must not be — those rows are the legacy
    # projection step 8 retires, and reading them here would make the candidate
    # set quietly wrong on the first route saved after this landed.
    picked_premises = list(
        models.RoutePremisesMembership.objects.filter(
            tenant_id=tenant_id, route_id__in=route_ids
        ).values_list("premises_id", flat=True)
    )
    if picked_premises:
        for unit_id in (
            models.Unit.objects.filter(
                tenant_id=tenant_id,
                premises_id__in=picked_premises,
                premises__deleted_at__isnull=True,
                deleted_at__isnull=True,
            )
            .order_by("id")
            .values_list("id", flat=True)
        ):
            found.setdefault(str(unit_id), None)
    return list(found)


def directly_stamped_units(cycle_ids: list[Any]) -> dict[str, set[str]]:
    """`{cycle id: unit ids}` for service points that name a CYCLE and no ROUTE.

    ⚠ **THIS IS THE ONE STAMP THE DERIVATION STILL READS, AND IT READS IT AS AN
    EXPLICIT CHOICE.** B17 §5 keeps two jobs for stored rows, and the first is
    *"explicit human choices"*. `service_points.cycle_id` is normally a
    PROJECTION of route membership — the three stampers write `route` and
    `cycle` in one statement — so a stamp that carries a route is re-derived
    like any other projection, and a stale one is dropped.

    A stamp with **no route** is a different row: nothing about routing explains
    it, so it is a standing statement that this unit bills on this cycle and
    nothing in the tag chain contradicts it. Honouring it is also the safe
    direction for a seam that decides who gets a bill — **no unit that the
    stamped implementation billed stops being billed by the derived one**,
    unless a live route says otherwise (an inactive route, IS-1) or the cycle
    itself is a draft.

    A route-less cycle stamp is written today only from outside the route model
    — the billing suite's own fixtures build a cycle's population this way, and
    a migration or a data fix can too.
    """
    tenant_id = _tenant_id()
    out: dict[str, set[str]] = {}
    for cycle_id, unit_id in models.ServicePoint.objects.filter(
        tenant_id=tenant_id,
        cycle_id__in=list(cycle_ids),
        route_id__isnull=True,
        deleted_at__isnull=True,
        unit__deleted_at__isnull=True,
    ).values_list("cycle_id", "unit_id").order_by().distinct():
        # `DISTINCT` in SQL (`DEF-MET-8732`): a unit has a point per service,
        # so without it a 40,000-unit cycle shipped ~160,000 pairs to Python to
        # be folded into 40,000 by the set below.
        out.setdefault(str(cycle_id), set()).add(str(unit_id))
    return out


def _resolution_for(routes: list[models.Route]) -> Resolution:
    return resolve(_candidate_unit_ids(routes))


def resolve(unit_ids: list[Any]) -> Resolution:
    """The public constructor — one resolution for a bounded set of units."""
    return Resolution(list(unit_ids))


# ═══════════════════════════════════════════════════════════════════════════
# THE THREE SCOPING QUESTIONS B17 §5 NAMES
# ═══════════════════════════════════════════════════════════════════════════
def route_for_unit(unit_id: Any, service_code: str) -> DerivedRoute | None:
    """*"Which route reads this unit for this service, right now?"*"""
    return resolve([unit_id]).for_unit(unit_id, service_code)


def routes_for_unit(unit_id: Any) -> dict[str, DerivedRoute]:
    """Every service the unit is read for, and the route that reads it."""
    return resolve([unit_id]).routes_of(unit_id)


def routes_if_moved(unit_id: Any, premises_id: Any) -> dict[str, DerivedRoute]:
    """*"And which route would read it once it is on THAT building?"*

    CR-089 `PUJ-46`: a move is also a change of **who reads the meter and when
    it bills**, because a unit takes its route from its building (BR-MET-082
    clause 2). The move screen has to name both sides before the press, and
    naming the second one is this function.

    The destination's own units are resolved ALONGSIDE the moving unit, so a
    route the destination is on only by a sibling's live pick is a candidate
    route here — without them, `Resolution` would never load it and the answer
    would silently be *"no route"*.

    ⛔ Reads only. The move itself is `services.move_unit`.
    """
    premises = models.Premises.objects.filter(tenant_id=_tenant_id(), pk=premises_id).first()
    if premises is None:
        return {}
    neighbours = list(
        models.Unit.objects.filter(
            tenant_id=premises.tenant_id, premises_id=premises.pk, deleted_at__isnull=True
        ).values_list("id", flat=True)
    )
    resolution = Resolution(
        [unit_id, *neighbours],
        premises_override={str(unit_id): (str(premises.pk), premises.area_id)},
    )
    return resolution.routes_of(unit_id)


def _active_routes(
    *, route_ids: list[Any] | None = None, cycle_id: Any = None
) -> list[models.Route]:
    qs = models.Route.objects.filter(tenant_id=_tenant_id(), status="active")
    if route_ids is not None:
        qs = qs.filter(pk__in=list(route_ids))
    if cycle_id is not None:
        qs = qs.filter(cycle_id=cycle_id)
    return list(qs.select_related("cycle", "area", "service").order_by("code", "id"))


def members_of_route(route_id: Any) -> list[dict[str, Any]]:
    """*"Who is on this route right now?"* — unit ids with the basis of each
    claim, in no particular order (the caller sorts by the ruled stop)."""
    return members_of_routes([route_id]).get(str(route_id), [])


def members_of_routes(route_ids: list[Any]) -> dict[str, list[dict[str, Any]]]:
    """The same question for a whole page of routes, in one resolution (D7)."""
    routes = _active_routes(route_ids=list(route_ids))
    out: dict[str, list[dict[str, Any]]] = {str(value): [] for value in route_ids}
    if not routes:
        return out
    resolution = _resolution_for(routes)
    for unit_id in resolution.unit_ids:
        for answer in resolution.routes_of(unit_id).values():
            rows = out.setdefault(answer.route_id, [])
            if any(row["unit_id"] == unit_id for row in rows):
                continue
            rows.append(
                {
                    "unit_id": unit_id,
                    "basis": answer.basis,
                    "walk_order": resolution.stored_order.get((unit_id, answer.route_id)),
                }
            )
    return out


def units_in_cycle(cycle_id: Any, *, service_codes: list[str] | None = None) -> list[str]:
    """*"Which units does CY-001 bill?"* — billing's scope seam, derived.

    ⚠ **BR-MET-082 AMENDMENT 1'S TWO SENTENCES BOTH HOLD, AND THEY ARE ABOUT
    DIFFERENT WINDOWS.** *"every run it is not necessry it will ahve same number
    of accounts or meters - since Utility will make changes"* is RUN-TO-RUN and
    is what this function now honours. `units_in_cycle`'s own standing promise —
    *"a run scoped twice covers the same accounts in the same order"* — is about
    ONE run's preview-to-issue window, and it still holds two ways: the answer is
    a pure function of the tags, so it is identical while they are; and the run's
    real freeze is the DRAFT INVOICE set `issue.issue_run` works from, which is
    written once and never re-scoped. A varying count between two runs is
    correct behaviour and no guard may treat it as drift.

    A DRAFT cycle scopes nothing (BR-MET-076) — the same silence the stamp gave
    it, arrived at by asking instead of remembering.
    """
    cycle = models.Cycle.objects.filter(tenant_id=_tenant_id(), pk=cycle_id).first()
    if cycle is None or cycle.status == "draft":
        return []
    scope = None if service_codes is None else set(service_codes)
    found: set[str] = set()

    routes = _active_routes(cycle_id=cycle.id)
    if routes:
        wanted = {str(route.id) for route in routes}
        resolution = _resolution_for(routes)
        for unit_id in resolution.unit_ids:
            for code, answer in resolution.routes_of(unit_id).items():
                if answer.route_id not in wanted:
                    continue
                # An EMPTY scope covers nothing — that is not the same as "no
                # scope given" (None = every service), and collapsing the two
                # would silently bill every service on a run scoped to none.
                if scope is not None and code != ANY_SERVICE and code not in scope:
                    continue
                found.add(unit_id)
                break

    # …plus the units whose service point names this cycle and NO route — an
    # explicit statement nothing in the tag chain contradicts. See
    # `directly_stamped_units`.
    direct = directly_stamped_units([cycle.id]).get(str(cycle.id), set())
    if direct:
        if scope is None:
            found |= direct
        else:
            service_ids = set(seams_service_ids(sorted(scope)))
            found |= {
                str(unit_id)
                for unit_id in models.ServicePoint.objects.filter(
                    tenant_id=_tenant_id(),
                    cycle_id=cycle.id,
                    route_id__isnull=True,
                    deleted_at__isnull=True,
                    unit_id__in=list(direct),
                    service_id__in=list(service_ids),
                ).values_list("unit_id", flat=True)
            }
    # Stable and sorted, exactly as the stamp-based seam ordered it.
    return sorted(found)


def accounts_in_cycle(cycle_id: Any) -> list[dict[str, Any]]:
    """**D13 — the account's cycle, derived: account → unit → route → cycle.**

    PO, verbatim: *"Cycles are not directlya ssing to accounts it is derived and
    determined at the time of bill run"*. There is no column anywhere pairing an
    account with a cycle and none is added; the chain is walked, in one batched
    read through the reviewed customers seam.

    NO MONEY (BR-MET-078 / D12 — *"not required"* on the Balance column): the row
    carries who and where, never what they owe.
    """
    from apps.metering import seams

    unit_ids = units_in_cycle(cycle_id)
    if not unit_ids:
        return []
    accounts = seams.accounts_for_units(unit_ids)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for unit_id in unit_ids:
        account = accounts.get(unit_id)
        if not account or not account.get("id"):
            continue
        account_id = str(account["id"])
        if account_id in seen:
            continue
        seen.add(account_id)
        rows.append(
            {
                "account_id": account_id,
                "account_no": account.get("account_no"),
                "customer_name": account.get("customer_name"),
                "status": account.get("status"),
                "unit_id": unit_id,
            }
        )
    return rows


def covered_unit_ids(extra_route_ids: list[Any] | None = None) -> set[str]:
    """*"Is anyone uncovered?"* — the units a cycle reaches today, derived.

    `extra_route_ids` is the set the cycle wizard has just selected and not yet
    saved: their units count as covered, because the figure a staff member needs
    on step 3 is *"what will still be unscheduled after I press create"*.
    """
    routes = [
        route
        for route in _active_routes()
        if route.cycle_id is not None and route.cycle and route.cycle.status != "draft"
    ]
    extra = [str(value) for value in (extra_route_ids or [])]
    if extra:
        routes = routes + [
            route
            for route in _active_routes(route_ids=extra)
            if str(route.id) not in {str(row.id) for row in routes}
        ]
    covered: set[str] = set()
    for units in directly_stamped_units(
        [route.cycle_id for route in routes if route.cycle_id]
    ).values():
        covered |= units
    if not routes:
        return covered
    wanted = {str(route.id) for route in routes}
    resolution = _resolution_for(routes)
    return covered | {
        unit_id
        for unit_id in resolution.unit_ids
        if any(answer.route_id in wanted for answer in resolution.routes_of(unit_id).values())
    }
