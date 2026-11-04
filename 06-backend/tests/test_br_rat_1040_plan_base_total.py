# ── Trace ──────────────────────────────────────────────
# Rules:   BR-RAT-1040 (PO ruling 2026-09-27, verbatim *"a is good"*) — the
#          plan list shows the REAL monthly base total and no longer sorts by
#          it · BR-RAT-088 (PO 2026-08-20 — the CHARGE CODE owns the base) ·
#          BR-RAT-1025 (PO 2026-09-19 — plan → rate schedule → charge code →
#          base charges) · NFR-3 (universal server pagination and SQL sorting)
# Defect:  DEF-RAT-6927 — `Monthly base total` read $0.00 on every plan
# Tests:   this file
# Impacts: 06-backend/apps/rating/selectors.py (_plan_base_total, plan_row,
#          plan_queryset, plan_list_queryset, PLAN_SORTS) ·
#          07-frontend/src/api/endpoints.ts (PLAN_SORTS) ·
#          07-frontend/src/features/rating/PlansTab.tsx
# ───────────────────────────────────────────────────────
"""The plan's monthly base is the one the charge codes state, and it no longer sorts.

WHAT WAS WRONG, IN ONE SENTENCE
-------------------------------
`Monthly base total` summed `plan_services.base_charge` — the column
`BR-RAT-088` retired when the charge code took the base over — so on every plan
written since that ruling it read **`$0.00`**, arithmetically correct over its
own input and the wrong input. `DEF-RAT-6927`.

⚠ **AND THE FIGURE WAS ALSO THE LIST'S SQL SORT KEY**, so a clerk sorting by
base charge got an order as meaningless as the number, which merely looked
plausible. The PO was shown exactly that — *"ten plans all reading `$0.00`, and
a clerk clicks the column to sort by base charge"* — and ruled option (a): show
the real figure, drop the sort.

⚠ **`NFR-3` IS NOT WEAKENED BY ANY CASE IN THIS FILE.** The list still pages
and sorts in SQL. One sort OPTION is withdrawn because the value behind it
needs the charge codes narrowed by customer class and size, which is a walk.
`TC-4` pins the remaining sorts so nobody can read this as licence to sort a
list in Python.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.rating import models, selectors
from core.pagination import ListParams
from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared env fixture
from tests.test_us_rat_helpers import RES_WATER_TIERS, tenant_ctx

pytestmark = pytest.mark.django_db


def _params(**kwargs):
    return ListParams(**{"sort": "name", "dir": "asc", **kwargs})


# ══════════════════════════════════════════════════════════════════════════
# TC-1 · THE FIGURE IS THE CHARGE CODES', NOT THE RETIRED COLUMN'S
# ══════════════════════════════════════════════════════════════════════════
def test_tc1__the_base_total_is_summed_from_the_charge_codes(env):
    """`$8.00` water + `$12.00` electric = **`$20.00`**, and the plan's own
    retired `base_charge` column says something else entirely.

    The figures are the repo's signed ones — `core.sample_fixture`, `[W] §1
    "Base/mo … Water $8 · Electric $12"` — read through the same fixture
    helper `apps/rating/sample_data.BASE_CHARGE_CODES` and `seed_demo` use, so
    this case states no number of its own.

    **THE PLAN'S `base_charge` VALUES ARE DELIBERATELY DIFFERENT.** `18.50` and
    `12.00` sum to `$30.50`, which is what this screen served until today. If
    this assertion ever reads `30.50` again, the retired column has come back.
    """
    env.enable("water", "electric")
    electric = env.tiered_schedule("Res Electric · Tiered", "electric", RES_WATER_TIERS)
    water = env.tiered_schedule("Res Water · Inclining", "water", RES_WATER_TIERS)
    plan = env.plan(
        "Residential Standard",
        "RES-STD",
        [
            {"service": "electric", "base_charge": "18.50", "tariff": electric["id"]},
            {"service": "water", "base_charge": "12.00", "tariff": water["id"]},
        ],
        publish=True,
    )
    with tenant_ctx(env.tenant):
        row = selectors.plan_detail(plan["id"])
    assert row["base_charges_unavailable"] is None, row["base_charges_unavailable"]
    assert Decimal(row["base_charges"]) == Decimal("20.00"), row["base_charges"]
    assert row["base_charges_display"] == "20.00"
    # ...and the retired column still holds the old numbers, untouched. The fix
    # changed where the figure is READ from, and wrote nothing.
    with tenant_ctx(env.tenant):
        retired = sorted(
            str(value)
            for value in models.PlanService.objects.filter(rate_plan_id=plan["id"]).values_list(
                "base_charge", flat=True
            )
        )
    assert retired == ["12.000000", "18.500000"], retired


# ══════════════════════════════════════════════════════════════════════════
# TC-2 · AN ABSENCE IS `null` AND A NAMED REASON, NEVER `$0.00`
# ══════════════════════════════════════════════════════════════════════════
def test_tc2__a_plan_with_no_rate_schedule_states_the_absence(env):
    """A plan nobody has attached a schedule to has no base to state.

    ⚠ **`0.00` IS THE ANSWER THIS WHOLE DEFECT IS ABOUT.** A figure that looks
    like a figure is worse than a stated gap, because a clerk reads `$0.00` as
    *this plan charges no base* — a claim about their pricing — rather than as
    *the product cannot tell you*. `impact.summarise` already takes this exact
    posture for the same reason.
    """
    env.enable("water")
    plan = env.plan("Unbound", "UNBOUND", [])
    with tenant_ctx(env.tenant):
        row = selectors.plan_detail(plan["id"])
    assert row["base_charges"] is None
    assert row["base_charges_display"] is None
    assert row["base_charges_unavailable"] == selectors.BASE_TOTAL_NO_SCHEDULE


# ══════════════════════════════════════════════════════════════════════════
# TC-3 · THE SORT IS WITHDRAWN, AND ASKING FOR IT IS NOT AN ERROR
# ══════════════════════════════════════════════════════════════════════════
def test_tc3__base_charges_is_no_longer_an_offered_sort(env):
    """`BR-RAT-1040`. The option is gone from the declared set.

    ⚠ **A CLIENT THAT STILL ASKS FOR IT FALLS BACK TO `name` RATHER THAN
    FAILING**, which is deliberate: a bookmarked URL or a stale bundle asking
    for a withdrawn sort should show the list, not an error page. What it must
    never do is silently order by the retired column again — `TC-4` is the
    half that proves the fallback lands on `name`.
    """
    assert "base_charges" not in selectors.PLAN_SORTS
    assert selectors.PLAN_SORTS == ("name", "accounts", "status")


def test_tc4__every_remaining_sort_is_still_SQL_and_NFR_3_is_intact(env):
    """⚠ **READ THIS BEFORE CONCLUDING ANYTHING ABOUT `NFR-3` FROM THIS FILE.**

    The Plans list still PAGES and SORTS in the database. `BR-RAT-1040`
    withdrew one sort OPTION because the value behind it cannot be computed
    there; it did not move sorting into Python and nobody may read it that way.

    This asserts the ORDER BY clause the queryset actually carries, so a lane
    that "restores" the base sort by ordering a list in memory goes red here
    and not in a browser.
    """
    env.enable("water", "electric")
    with tenant_ctx(env.tenant):
        for sort in selectors.PLAN_SORTS:
            qs = selectors.plan_list_queryset(_params(sort=sort))
            assert qs.query.order_by, sort
            assert str(qs.query).lower().count("order by") == 1, sort
        # The withdrawn one falls back to `name`, never to the retired column.
        withdrawn = selectors.plan_list_queryset(_params(sort="base_charges"))
        assert withdrawn.query.order_by == ("name", "id"), withdrawn.query.order_by
        assert "base_charge" not in str(withdrawn.query)
