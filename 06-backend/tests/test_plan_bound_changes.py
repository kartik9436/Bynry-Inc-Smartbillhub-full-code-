# ── Trace ──────────────────────────────────────────────
# Rules:    PO ruling 2026-09-18, verbatim: *"yes we should build this. It measn
#           every time Rate, taxes, Charge code, Discounts are changed, at
#           apporval we need to take action to inform Plan about it - Fix this"* ·
#           BR-RAT-088 (the plan BINDS, it does not price) ·
#           BR-RAT-037 (a plan version — and this is NOT one) ·
#           BR-RAT-1011 (the late-fee code the plan names directly) ·
#           NFR-3 (universal server pagination) · NFR-5 (no hard caps) ·
#           CLAUDE.md hard rule 1 · hard-won law 7
# Defect:   DEF-RAT-5738 — no tax or discount change reaches `rate_change_log`,
#           so this view is blind to two of the four kinds the PO named. That is
#           asserted here rather than described, so the day it is fixed a test
#           goes red and names it.
# Tests:    this file
# ───────────────────────────────────────────────────────
"""`GET /plans/{id}/bound-changes` — what moved underneath a plan.

⚠ **THE TEST THAT MATTERS IS `a_change_to_a_bound_schedule_reaches_the_plan`.**
Everything else here describes the shape. That one is the ruling: a clerk looking
at a plan could not see that the rate it binds had moved, and now can.

⚠ **AND THE SECOND ONE THAT MATTERS IS `the_answer_says_what_it_cannot_see`.**
A view that showed an empty list for taxes would be truthful about what it can
see and false about the world — hard-won law 7's *reporting zero over a scope it
silently excludes*. The absence is served as data and asserted as data.
"""

import pytest

from apps.rating import api, models, selectors

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import (
    RES_WATER_TIERS,
    FakeUser,
    api_call,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def _plan_with_a_schedule(env):
    schedule = env.tiered_schedule("Res Water · Inclining", "water", RES_WATER_TIERS)
    plan = env.plan(
        "Sample — Residential",
        "SCW-RES",
        [{"service": "water", "base_charge": "8.00", "tariff": schedule["id"]}],
        publish=True,
    )
    return plan, schedule


def _read(env, plan_id, **params):
    return api_call(
        api.plan_bound_changes,
        "get",
        user=FakeUser(env.owner.id),
        role="system_admin",
        tenant=env.tenant,
        query=params,
        plan_id=plan_id,
    )


def _log(env, entity_type, entity_id, reason, after=None):
    """A `rate_change_log` row exactly as the module's own writers write one."""
    with tenant_ctx(env.tenant):
        return models.RateChangeLog.objects.create(
            tenant=env.tenant,
            entity_type=entity_type,
            entity_id=entity_id,
            before={"name": "before"},
            after=after if after is not None else {"name": "after"},
            reason=reason,
            actor_id=env.owner.id,
        )


# ── THE RULING ──────────────────────────────────────────────────────────────


def test_a_change_to_a_bound_schedule_reaches_the_plan(env):
    """⚠ **THE RULING.** A plan showed WHICH schedule it binds and never that
    the bound schedule's price had moved. PO: *"every time Rate … are changed …
    we need to take action to inform Plan about it"*.

    RED before the fix: `AttributeError: module 'apps.rating.api' has no
    attribute 'plan_bound_changes'`.
    """
    plan, schedule = _plan_with_a_schedule(env)
    _log(env, "schedule", schedule["id"], "Water raised for the 2027 filing.")

    response = _read(env, plan["id"])
    assert response.status_code == 200, response.data
    rows = response.data["results"]
    assert len(rows) == 1, rows
    assert rows[0]["entity_type"] == "schedule"
    assert rows[0]["reason"] == "Water raised for the 2027 filing."
    # DEF-367 — a person, never a uuid.
    assert rows[0]["actor"]["id"] == str(env.owner.id)


def test_the_answer_says_what_it_cannot_see(env):
    """⚠ **HARD-WON LAW 7 — a declared blind spot with no NUMBER attached is
    indistinguishable from an empty one.** The PO named four kinds; only two are
    ever written to `rate_change_log` (`DEF-RAT-5738`), so the answer names both
    lists and the screen says so.

    ⚠ **THIS TEST GOES RED WHEN `DEF-RAT-5738` IS FIXED, AND THAT IS ITS JOB.**
    Whoever makes a tax write a log row has to delete `"tax"` from the uncovered
    list here — which is the moment the screen should stop apologising.
    """
    plan, _schedule = _plan_with_a_schedule(env)
    coverage = _read(env, plan["id"]).data["coverage"]
    assert coverage["covered"] == ["schedule", "charge"]
    assert coverage["uncovered"] == ["tax", "discount"]
    assert coverage["uncovered_defect"] == "DEF-RAT-5738"

    # And the claim underneath it, asserted against the CODE rather than trusted:
    # a tax change genuinely writes nothing this view could find.
    with tenant_ctx(env.tenant):
        assert not models.RateChangeLog.objects.filter(entity_type="tax").exists()


# ── WHAT IT DELIBERATELY DOES NOT SHOW ──────────────────────────────────────


def test_a_change_to_the_plan_itself_is_not_in_this_list(env):
    """The Audit tab already draws the plan's own history in full. Folding the
    two together would let a plan's own edits drown the one signal this view
    exists to carry."""
    plan, schedule = _plan_with_a_schedule(env)
    _log(env, "plan", plan["id"], "The plan was re-bound by the board.")
    _log(env, "schedule", schedule["id"], "Water raised.")

    rows = _read(env, plan["id"]).data["results"]
    assert [row["entity_type"] for row in rows] == ["schedule"]


def test_another_plans_schedule_is_not_in_this_list(env):
    """The filter is the binding, not the tenant. A plan that binds nothing of
    this schedule must not be told about it."""
    plan, _schedule = _plan_with_a_schedule(env)
    other = env.tiered_schedule("Com Water · Flat", "water", RES_WATER_TIERS)
    _log(env, "schedule", other["id"], "A schedule this plan does not bind.")

    assert _read(env, plan["id"]).data["count"] == 0


def test_a_plan_that_binds_nothing_returns_nothing_not_everything(env):
    """⚠ **THE FALSE PASS THIS GATE IS WRITTEN AGAINST** (law 7's habit 2: ask
    what would make the check pass WRONGLY). Building the filter from an empty
    id list without an explicit match-nothing predicate yields a `Q()` that
    matches EVERY row — so a plan binding nothing would be told about the whole
    tenant's log, which looks like a working feature."""
    with tenant_ctx(env.tenant):
        bare = models.RatePlan.objects.create(
            tenant=env.tenant, code="BARE-1", name="Binds nothing", status="draft"
        )
    _log(env, "schedule", bare.id, "A row belonging to nothing this plan binds.")

    response = _read(env, str(bare.id))
    assert response.status_code == 200, response.data
    assert response.data["count"] == 0, response.data["results"]


# ── THE LATE-FEE CODE, WHICH IS THE CHARGE EVERY PLAN HAS ───────────────────


def test_the_late_fee_code_counts_as_bound(env):
    """`BR-RAT-1011` — the plan names its late-fee code DIRECTLY, with no
    `PlanChargeRule` row. Reading only the attached codes would miss the one
    charge code a plan is most likely to have."""
    plan, _schedule = _plan_with_a_schedule(env)
    with tenant_ctx(env.tenant):
        row = models.RatePlan.objects.get(pk=plan["id"])
        charge = models.Charge.objects.filter(tenant=env.tenant).first()
        assert charge is not None, "the fixture must seed at least one charge code"
        row.late_fee_charge = charge
        row.save(update_fields=["late_fee_charge"])
        bound = selectors.plan_bound_entity_ids(row)
    assert charge.id in bound["charge"]

    _log(env, "charge", charge.id, "The late fee moved to $30.00.")
    rows = _read(env, plan["id"]).data["results"]
    assert [one["entity_type"] for one in rows] == ["charge"]


# ── NFR-3 / NFR-5, AND HARD RULE 1 ──────────────────────────────────────────


def test_the_page_is_cut_by_the_server_and_the_count_is_the_whole_set(env):
    """⚠ **`NFR-3`, ASSERTED AS THE TWO THINGS THAT ACTUALLY DIFFER.**

    A built list paginated afterwards produces the SAME `count` and the SAME
    `results` as a queryset does, so neither of those alone can tell the two
    apart — which is exactly the false pass this test has to be written against
    (hard-won law 7, habit 2). What distinguishes them is **what the database
    was asked for**, so both halves are asserted:

      · the selector hands back a `QuerySet`, so DRF issues a SQL `COUNT` and a
        SQL `LIMIT`/`OFFSET` rather than materialising the set in Python;
      · and over a set LARGER than one page, `count` is the whole set while
        `results` is one page.

    `per` clamps to `PAGE_SIZES` and its floor is 50 (`clamp_page_size` — a
    smaller number is raised, never honoured), so the set has to cross 50 for
    the cut to be observable at all. Fifty-one rows is the cheapest set that
    proves it, and asking for `per=2` — which reads like a page of two and is
    silently a page of fifty — is how this test would otherwise have passed over
    a list paginated in Python.
    """
    from django.db.models import QuerySet

    plan, schedule = _plan_with_a_schedule(env)
    with tenant_ctx(env.tenant):
        models.RateChangeLog.objects.bulk_create(
            [
                models.RateChangeLog(
                    tenant=env.tenant,
                    entity_type="schedule",
                    entity_id=schedule["id"],
                    before={"name": "before"},
                    after={"name": "after"},
                    reason=f"change {n}",
                    actor_id=env.owner.id,
                )
                for n in range(51)
            ]
        )
        assert isinstance(
            selectors.plan_bound_changes_queryset(plan["id"]), QuerySet
        ), "a built list here is NFR-3's breach, not its plumbing"

    response = _read(env, plan["id"])
    assert response.data["count"] == 51, "the count is the WHOLE set"
    assert len(response.data["results"]) == 50, "the page is what the server cut"
    assert response.data["next"], "there is a next page to walk to"


def test_newest_first(env):
    plan, schedule = _plan_with_a_schedule(env)
    _log(env, "schedule", schedule["id"], "older")
    _log(env, "schedule", schedule["id"], "newer")
    rows = _read(env, plan["id"]).data["results"]
    assert [one["reason"] for one in rows] == ["newer", "older"]


def test_another_tenants_plan_is_absent_not_forbidden(env, other_env):
    """Hard rule 1 / HR-1: a cross-tenant id is ABSENT, so nothing leaks the
    fact that the row exists."""
    plan, _schedule = _plan_with_a_schedule(env)
    response = api_call(
        api.plan_bound_changes,
        "get",
        user=FakeUser(other_env.owner.id),
        role="system_admin",
        tenant=other_env.tenant,
        plan_id=plan["id"],
    )
    assert response.status_code == 404, response.data
