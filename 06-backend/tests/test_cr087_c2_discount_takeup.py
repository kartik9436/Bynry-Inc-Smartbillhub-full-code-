# ── Trace ──────────────────────────────────────────────
# Change:   CR-087 task C2 (PRB-20's computable half) — the count that decides
#           TAKE-UP on a discount programme.
#           Screens: DIS-01 detail Overview (`09-screen-inventory.md` §18 row 11)
# Rules:    BR-RAT-069 (AVAILABLE ≠ GRANTED — plans offer, enrolments grant) ·
#           B2 r16 #6 (`unit_plan_assignments` is rating-owned) · CR-087 §6 C2
# Tests:    this file
# Impacts:  apps/rating/selectors.py (`discount_offered_unit_count`,
#           `discount_detail`)
# ───────────────────────────────────────────────────────
"""`31` is trivia; `31 of 86` is take-up.

⚠ **WHAT IS COUNTED, AND WHAT IS DELIBERATELY NOT.** `enrolled` counts ACCOUNTS
with an open enrolment — `discount_enrolments` carries an FK to
`customers.Account` and always has. `offered_units` counts UNITS on a current
plan assignment whose plan carries the discount. Two different kinds, each
labelled with what it is, and **no fraction is asserted between them**, because a
vacant unit has no account and cannot enrol.

⚠ **AND NEITHER OF THEM IS `eligible`.** `PRB-20` asks how many accounts are
ELIGIBLE; eligibility on a discount is free text a person wrote (*"Age 65 or
over"*) and nothing in this product evaluates one. Offered is computable, so it
is computed; eligible is not, so it is stated as an absence rather than drawn
from the nearest available number.
"""

from datetime import date

import pytest

from apps.rating import discount_sample_data, discount_services, selectors
from apps.rating import discounts as discount_models
from apps.rating import models

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import tenant_ctx
from tests.test_us_met_helpers import make_plan, make_premises, make_unit

pytestmark = pytest.mark.django_db


def _assign(tenant, plan, unit_id, when=date(2026, 6, 1)):
    """One CURRENT unit→plan assignment, written the way the history stores it."""
    return models.UnitPlanAssignment.objects.create(
        tenant=tenant,
        unit_id=unit_id,
        rate_plan=plan,
        plan_version=plan.version,
        assigned_from=when,
        assigned_to=None,
        source="import",
    )


def _seed(env):
    with tenant_ctx(env.tenant):
        return discount_sample_data.seed_sample_discounts(env.admin)


def test_the_detail_serves_the_offered_count(env):
    """The take-up denominator reaches the screen at all — this was missing."""
    _seed(env)
    with tenant_ctx(env.tenant):
        discount = discount_models.Discount.objects.filter(tenant=env.tenant).first()
        detail = selectors.discount_detail(discount.id)
    assert "offered_units" in detail
    assert isinstance(detail["offered_units"], int)


def test_a_discount_no_plan_carries_is_offered_to_nobody(env):
    """Zero here is a FACT — nothing offers it — not a missing figure."""
    with tenant_ctx(env.tenant):
        discount = discount_services.create_discount(
            env.admin,
            {
                "code": "LONELY",
                "name": "Offered by nothing",
                "discount_type": discount_models.DISCOUNT_PERCENTAGE,
                "value": "5",
                "applies_to": discount_models.SCOPE_WHOLE_BILL,
            },
        )
        detail = selectors.discount_detail(discount["id"])
    assert detail["offered_units"] == 0


def test_it_counts_the_units_on_every_plan_that_carries_it(env):
    """⚠ UNITS, not accounts, and not plans. A plan is assigned to a UNIT, so
    the population a programme reaches is the units its plans are on.

    ⚠ **THE DATA IS BUILT HERE RATHER THAN HOPED FOR.** A first draft leaned on
    the sample fixture and SKIPPED when it turned out to attach no unit to a
    plan carrying a discount — a test reporting `s` over the one thing it exists
    to measure, which is CLAUDE.md law 7's *incapable of failing* shape wearing a
    skip. Two units on one plan, one of them vacant, is the case that matters.
    """
    with tenant_ctx(env.tenant):
        premises = make_premises(env.admin, address_line="7 Take-Up Row")
        one = make_unit(env.admin, premises["id"], label="Unit 1")
        two = make_unit(env.admin, premises["id"], label="Unit 2")
        plan_row = make_plan(env.tenant, code="TAKEUP", name="Take-up plan")
        for unit in (one, two):
            _assign(env.tenant, plan_row, unit["id"])
        discount = discount_services.create_discount(
            env.admin,
            {
                "code": "TAKEUP",
                "name": "Take-up discount",
                "discount_type": discount_models.DISCOUNT_PERCENTAGE,
                "value": "5",
                "applies_to": discount_models.SCOPE_WHOLE_BILL,
            },
        )
        discount_row = discount_models.Discount.objects.get(
            tenant=env.tenant, id=discount["id"]
        )
        # Before any plan carries it, it is offered to nobody.
        assert selectors.discount_offered_unit_count(discount_row) == 0
        discount_services.attach_discount_to_plan(env.admin, plan_row.id, discount_row.id)
        # ⚠ TWO, INCLUDING THE VACANT ONE. A vacant unit still has a plan and
        # still gets a base charge on somebody's bill, so it is part of the
        # population the programme is offered to.
        assert selectors.discount_offered_unit_count(discount_row) == 2
        assert selectors.discount_detail(discount_row.id)["offered_units"] == 2


def test_an_ended_plan_assignment_is_not_offered_anything(env):
    """`assigned_to` ends an assignment. A unit that has moved off the plan is
    no longer offered the discount, and counting it would inflate the
    denominator and make take-up look worse than it is."""
    with tenant_ctx(env.tenant):
        premises = make_premises(env.admin, address_line="9 Moved On Way")
        one = make_unit(env.admin, premises["id"], label="Unit 1")
        two = make_unit(env.admin, premises["id"], label="Unit 2")
        plan_row = make_plan(env.tenant, code="MOVEDON", name="Moved-on plan")
        _assign(env.tenant, plan_row, one["id"])
        ended = _assign(env.tenant, plan_row, two["id"])
        discount = discount_services.create_discount(
            env.admin,
            {
                "code": "MOVEDON",
                "name": "Moved-on discount",
                "discount_type": discount_models.DISCOUNT_PERCENTAGE,
                "value": "5",
                "applies_to": discount_models.SCOPE_WHOLE_BILL,
            },
        )
        discount_row = discount_models.Discount.objects.get(
            tenant=env.tenant, id=discount["id"]
        )
        discount_services.attach_discount_to_plan(env.admin, plan_row.id, discount_row.id)
        assert selectors.discount_offered_unit_count(discount_row) == 2
        ended.assigned_to = ended.assigned_from
        ended.save(update_fields=["assigned_to"])
        assert selectors.discount_offered_unit_count(discount_row) == 1
