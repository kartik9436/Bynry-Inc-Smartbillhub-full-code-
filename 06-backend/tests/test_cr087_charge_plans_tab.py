# ── Trace ──────────────────────────────────────────────
# Change:   CR-087 — the Charge codes detail page's `Plans` tab body. PO ruling
#           2026-09-10, verbatim: *"build"* (decision log, THE FOUR EMPTY TAB
#           BODIES GET BUILT). The tab shipped rendering ONE SENTENCE saying it
#           could not do its job, and that sentence is the text the blueprint
#           quotes back as the defect.
#           Screens: S12 / CHG-01 · `?tab=plans`
# Defects:  DEF-RAT-4832 — the count under this tab reads `0` for a code that
#           prices every connection on its service, because only ONE of the two
#           routes was ever counted.
# Rules:    BR-RAT-088 (the CHARGE CODE owns the base amount; a plan displays
#           it, never defines it — PO 2026-08-20) · DEF-RAT-4664 (a plan is
#           assigned to a UNIT, so a count of them says units) · NFR-3
#           (universal server pagination) · NFR-5 (no hard cap anywhere) ·
#           B14 rule 31 (no database id is a visible value) · B14 rule 37 (a
#           drawn figure is an illustration, never a fact to build to)
# Tests:    this file
# Impacts:  apps/rating/selectors.{charge_reach_plan_ids,charge_reach_queryset,
#           charge_reach_rows} · apps/rating/api.charge_plans ·
#           GET /charges/{id}/plans
# ───────────────────────────────────────────────────────
"""WHICH plans a charge code reaches, and by WHICH OF THE TWO ROUTES.

── WHY THE SECOND ROUTE IS THE WHOLE POINT ───────────────────────────────────

`charge_used_by` counts `plan_charge_rules` and nothing else, which is the
*named on the plan* route. `BR-RAT-088` gave the charge code the BASE amount —
PO 2026-08-20, verbatim: *"the CHARGE CODE owns the base amount; a plan
displays it, never defines it"* — so a code that DECLARES itself its service's
base is read by every plan carrying a rate schedule for that service, and that
plan names no charge rule at all.

**So the Overview tile reads `0` over a code that prices every connection on
its service.** That is not a rendering bug: it is the count meaning one of two
things while the label says both. This file pins the honest answer and leaves
`charge_used_by` alone, because that function feeds the DELETE lock and
widening a lock is a different decision from widening a screen count.

── PROVED RED FIRST (hard-won law 7), through `pytest`, the harness that runs
── them. What each printed before the selector existed ──────────────────────

* `test_a_named_plan_and_a_base_plan_are_both_reached` —

      AttributeError: module 'apps.rating.selectors' has no attribute
      'charge_reach_queryset'

  and, with a `charge_reach_queryset` built the obvious way (the `PlanChargeRule`
  ids alone, which is what `charge_used_by` already returns):

      AssertionError: assert 1 == 2

  — the base plan missing, which is `DEF-RAT-4832` reproduced in one line.

* `test_the_route_is_a_word_and_the_plan_code_states_its_own_absence` — with
  the row built to report `plan.code` on every row rather than only on a named
  one:

      AssertionError: assert 'cr087-base-water' is None

  A plan that does not NAME this code must not print its own code beside *the
  base of a rate schedule*: it reads as an attachment that does not exist, and
  a clerk would then look for a row to detach.

* `test_a_non_base_code_on_a_service_reaches_nothing_by_the_base_route` — with
  `charge.is_base and` removed from the guard:

      AssertionError: assert ['CR087C · WaterNB'] == []

* `test_a_base_code_reaches_only_ITS_service` — with the SERVICE dropped from
  the base query, so it names every plan carrying any rate schedule at all:

      AssertionError: assert ['CR087C · E4', 'CR087C · W4'] == ['CR087C · W4']

⚠ **AND ONE CASE HERE CANNOT BE MADE RED, WHICH IS WORTH MORE THAN THE ONES
THAT CAN.** `test_an_account_level_code_reaches_nothing_through_the_base_route`
was written believing it guarded `is_base and service_id`. It does not, and the
mutation proved it: a late fee's `service_id` IS `None`, so
`PlanRateSchedule.filter(service_id=None)` matches nothing and the case stays
green whichever half of the guard is taken away. It is kept as a statement of
the CONFIGURATION — an account-level code reaches nothing by the base route —
and the guard it appeared to protect is proved by the WaterNB case above, which
was added for exactly the half it could not see. Law 7's *"ask what would make
this check pass wrongly"*, answered by asking rather than assumed.

* `test_the_list_is_paged_in_sql_and_the_count_is_the_whole_set` — with the
  selector returning a built LIST instead of a queryset, DRF pages the list in
  Python and the assertion that the API's `count` exceeds the page length
  still passes — which is why this case asserts the SELECTOR's own type and
  its `.count()` rather than only the envelope. `NFR-3` is about how the count
  is reached, and an envelope alone cannot tell you.
"""

from __future__ import annotations

from datetime import date

import pytest

from apps.rating import models as rating_models
from apps.rating import selectors
from apps.tenancy import models as tenancy_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_plan, make_premises, make_unit, tenant_ctx

pytestmark = pytest.mark.django_db

#: Every row this file creates is prefixed, for the reason the sibling CR-087
#: tax file states in its own words: the `brazos` fixture provisions plans and
#: charge codes of its own at provisioning time, and a helper reaching for one
#: by name would measure a row nobody here set up.
PREFIX = "CR087C · "


def a_charge(tenant, code, *, service_code=None, is_base=False):
    """One `charges` row, optionally declaring itself its service's base."""
    service = None
    if service_code is not None:
        service = tenancy_models.Service.objects.get(code=service_code)
    return rating_models.Charge.objects.create(
        tenant=tenant,
        code=f"{PREFIX[:6]}{code}",
        name=f"{PREFIX}{code}",
        charge_type="one_time",
        amount_rule="flat",
        service=service,
        is_base=is_base,
    )


def units_on(actor, tenant, plan, count, *, closed=0):
    """`count` CURRENT unit assignments on this plan, plus `closed` historic ones.

    The historic rows exist so the count proves it reads `assigned_to` and not
    simply every row that ever existed.

    ⚠ **THE NUMBERS ARE THIS FILE'S OWN AND NOT THE BLUEPRINT'S.** B14 rule 37
    (PO 2026-09-10) names a test asserting a drawn figure as the first thing it
    rules out. The frame inks `74`, `12` and `132`; those say a unit count goes
    in that column and nothing about what any real row holds.
    """
    premises = make_premises(actor)
    for index in range(count + closed):
        unit = make_unit(actor, premises["id"], label=f"{plan.code[:6]}-{index}")
        rating_models.UnitPlanAssignment.objects.create(
            tenant=tenant,
            unit_id=unit["id"],
            rate_plan=plan,
            plan_version=1,
            assigned_from=date(2026, 1, 1),
            assigned_to=None if index < count else date(2026, 6, 1),
            source="import",
        )


def rows_for(charge):
    """The whole set, enriched — what the API returns for a one-page result."""
    plans = list(selectors.charge_reach_queryset(charge))
    return selectors.charge_reach_rows(charge, plans)


# ══════════════════════════════════════════════════════════════════════════
# The two routes
# ══════════════════════════════════════════════════════════════════════════


def test_a_named_plan_and_a_base_plan_are_both_reached(brazos, dana):
    """The drawn table's whole reason: two routes, both counted.

    One plan NAMES the code through `plan_charge_rules`; another carries a
    water rate schedule and names nothing, and reaches the same code because
    the code declares itself water's base.
    """
    with tenant_ctx(brazos):
        base_code = a_charge(brazos, "BASE-W", service_code="water", is_base=True)
        named_plan = make_plan(brazos, name=f"{PREFIX}Named", services=("water",))
        base_plan = make_plan(brazos, name=f"{PREFIX}BaseOnly", services=("water",))
        rating_models.PlanChargeRule.objects.create(
            tenant=brazos, rate_plan=named_plan, charge=base_code
        )

        rows = rows_for(base_code)
        assert len(rows) == 2
        by_name = {row["plan_name"]: row for row in rows}
        assert by_name[f"{PREFIX}Named"]["reached_by"] == selectors.CHARGE_REACH_NAMED
        assert by_name[f"{PREFIX}BaseOnly"]["reached_by"] == selectors.CHARGE_REACH_BASE


def test_the_route_is_a_word_and_the_plan_code_states_its_own_absence(brazos, dana):
    """`plan_code` is `null` on a base row, and the ROUTE is served as a word.

    A screen that read the route off the blank code cell would decide a fact
    the server already knows, and the two would part company the first time a
    plan carried a code with no printed reference.
    """
    with tenant_ctx(brazos):
        base_code = a_charge(brazos, "BASE-W2", service_code="water", is_base=True)
        named_plan = make_plan(brazos, name=f"{PREFIX}Named2", services=("water",))
        make_plan(brazos, name=f"{PREFIX}BaseOnly2", services=("water",))
        rating_models.PlanChargeRule.objects.create(
            tenant=brazos, rate_plan=named_plan, charge=base_code
        )

        by_name = {row["plan_name"]: row for row in rows_for(base_code)}
        assert by_name[f"{PREFIX}Named2"]["plan_code"] == named_plan.code
        assert by_name[f"{PREFIX}BaseOnly2"]["plan_code"] is None
        # B14 rule 31 — the id travels so a screen can key a row, and every
        # column a clerk READS is a name, a code or a count.
        assert set(by_name[f"{PREFIX}BaseOnly2"]) == {
            "plan_id",
            "plan_name",
            "plan_code",
            "reached_by",
            "units",
        }


def test_a_plan_on_both_routes_is_reported_as_NAMED_once(brazos, dana):
    """One row per plan, and the route a clerk can act on locally wins.

    Renaming a plan's charge is local; changing a base moves every size on a
    schedule. A plan that does both is reported as `named` because that is the
    one it can do something about here.
    """
    with tenant_ctx(brazos):
        base_code = a_charge(brazos, "BASE-W3", service_code="water", is_base=True)
        both = make_plan(brazos, name=f"{PREFIX}Both", services=("water",))
        rating_models.PlanChargeRule.objects.create(
            tenant=brazos, rate_plan=both, charge=base_code
        )

        rows = rows_for(base_code)
        assert len(rows) == 1
        assert rows[0]["reached_by"] == selectors.CHARGE_REACH_NAMED


def test_an_account_level_code_reaches_nothing_through_the_base_route(brazos, dana):
    """A late fee has no service, so it can be no service's base.

    ⚠ **THIS CASE CANNOT BE MADE RED BY BREAKING THE GUARD, AND SAYING SO IS
    THE POINT OF THE COMMENT.** It was written believing it protected
    `is_base and service_id`; a late fee's `service_id` is `None`, so the base
    query matches nothing whichever half is removed. It stands as a statement
    of the configuration — an account-level code reaches nobody by that route —
    and the guard itself is proved by the case above it.
    """
    with tenant_ctx(brazos):
        late = a_charge(brazos, "LATE")
        make_plan(brazos, name=f"{PREFIX}Water", services=("water",))
        make_plan(brazos, name=f"{PREFIX}Electric", services=("electric",))

        assert rows_for(late) == []


def test_a_non_base_code_on_a_service_reaches_nothing_by_the_base_route(brazos, dana):
    """The half `is_base` guards, and the half a late fee cannot reach.

    ⚠ **THIS CASE EXISTS BECAUSE THE ONE ABOVE COULD NOT SEE THE GUARD.**
    Removing `charge.is_base and` leaves the late fee's assertion green — its
    `service_id` is `None`, so the base query matches nothing either way. A
    connection fee ON water and NOT declared water's base is the configuration
    where the guard is the only thing standing between a code that reaches
    nobody by that route and one that reaches every water plan.
    """
    with tenant_ctx(brazos):
        not_base = a_charge(brazos, "CONN-W", service_code="water", is_base=False)
        make_plan(brazos, name=f"{PREFIX}WaterNB", services=("water",))

        assert [row["plan_name"] for row in rows_for(not_base)] == []


def test_a_base_code_reaches_only_ITS_service(brazos, dana):
    """The base route is per SERVICE, not per tenant."""
    with tenant_ctx(brazos):
        water_base = a_charge(brazos, "BASE-W4", service_code="water", is_base=True)
        water_plan = make_plan(brazos, name=f"{PREFIX}W4", services=("water",))
        make_plan(brazos, name=f"{PREFIX}E4", services=("electric",))

        rows = rows_for(water_base)
        assert [row["plan_name"] for row in rows] == [water_plan.name]


# ══════════════════════════════════════════════════════════════════════════
# The UNITS column
# ══════════════════════════════════════════════════════════════════════════


def test_units_counts_CURRENT_assignments_and_says_units(brazos, dana):
    """`assigned_to IS NULL`, the same predicate every other unit count uses.

    `unit_plan_assignments` is append-only history: a closed row is where a
    unit USED to be, and counting it would inflate every figure on this table.
    """
    with tenant_ctx(brazos):
        code = a_charge(brazos, "CONN")
        plan = make_plan(brazos, name=f"{PREFIX}Counted", services=("water",))
        rating_models.PlanChargeRule.objects.create(
            tenant=brazos, rate_plan=plan, charge=code
        )
        units_on(dana, brazos, plan, 3, closed=2)

        assert rows_for(code)[0]["units"] == 3


def test_a_plan_nobody_is_on_reads_zero_rather_than_vanishing(brazos, dana):
    """A real zero. The plan carries the code and reaches nobody yet, which is
    a fact a clerk about to change a price needs — not a row to hide."""
    with tenant_ctx(brazos):
        code = a_charge(brazos, "CONN2")
        plan = make_plan(brazos, name=f"{PREFIX}Empty", services=("water",))
        rating_models.PlanChargeRule.objects.create(
            tenant=brazos, rate_plan=plan, charge=code
        )

        assert rows_for(code)[0]["units"] == 0


# ══════════════════════════════════════════════════════════════════════════
# NFR-3 · the paging is SQL's, and the count is the whole set
# ══════════════════════════════════════════════════════════════════════════


def test_the_list_is_paged_in_sql_and_the_count_is_the_whole_set(brazos, dana):
    """A QUERYSET, so DRF issues a `COUNT` over the set and a `LIMIT` for the page.

    ⚠ **THE ENVELOPE ALONE CANNOT TELL YOU THIS.** A built list handed to the
    paginator produces the same `count` and the same page — in Python, having
    materialised every row of a 40,000-account tenant to render fifty. So this
    asserts the selector's own type and that its `.count()` answers without the
    rows being fetched, which is the property `NFR-3` is actually about.
    """
    from django.db.models import QuerySet

    with tenant_ctx(brazos):
        code = a_charge(brazos, "CONN3")
        for index in range(3):
            plan = make_plan(brazos, name=f"{PREFIX}P{index}", services=("water",))
            rating_models.PlanChargeRule.objects.create(
                tenant=brazos, rate_plan=plan, charge=code
            )

        queryset = selectors.charge_reach_queryset(code)
        assert isinstance(queryset, QuerySet)
        assert queryset.count() == 3
        # Ordered for a screen, and stably: the id is the secondary sort, so
        # paging cannot show one plan twice and skip another (IS-2).
        assert queryset.query.order_by == ("name", "id")
        # …and only the PAGE is enriched. Handing this the plan id would decide
        # the paging a second time, in a second place.
        assert len(selectors.charge_reach_rows(code, list(queryset[:2]))) == 2


def test_a_code_nothing_carries_returns_an_empty_queryset(brazos, dana):
    """`Nothing carries it` — a drawn STATE, and the empty set rather than a
    query that names every plan in the utility."""
    with tenant_ctx(brazos):
        orphan = a_charge(brazos, "ORPH")
        make_plan(brazos, name=f"{PREFIX}Unrelated", services=("water",))

        assert selectors.charge_reach_queryset(orphan).count() == 0
        assert selectors.charge_reach_rows(orphan, []) == []
