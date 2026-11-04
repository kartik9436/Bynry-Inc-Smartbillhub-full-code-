# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-019 (dunning + disconnect pause while active & current)
#           Screens: S21 · S34
# Rules:    BR-CUS-043 (pause while active AND current; late-fee suspension is
#           a per-plan election) · BR-BIL-073 (a plan does NOT suspend the
#           current bill — PO 2026-08-11, OQ-138) · BR-PAY-016 (⚠ its void +
#           "dunning resumes" clause SUPERSEDED — PO 2026-08-11 "nodrop") ·
#           BR-PAY-017 (the resumed ladder is the tenant sequence) · BR-PAY-021
# ───────────────────────────────────────────────────────
"""What a plan stops, what it does not, and what a missed instalment does.

Two PO rulings of 2026-08-11 meet in this module and their JOIN is the subject
of every test here:

  * a plan does not suspend the current bill (*"there is monthly charges that
    thye have to pay nad it is due every month"*), so **current** cannot mean
    "paying the instalment";
  * nobody is dropped off a plan (*"nodrop we chase for payments until write
    off"*), so falling behind lifts the PAUSE and ends nothing.
"""

from datetime import date

import pytest

from apps.payments import dunning, plans
from apps.payments.collections_models import PLAN_ACTIVE, PaymentPlan

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_017_payment_plans import a_plan
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db


def an_active_plan(brazos, dana, *, account_no="A-11340", **overrides):
    account = an_account(dana, brazos, account_no=account_no)
    created = a_plan(brazos, dana, account, **overrides)
    plans.activate_payment_plan(actor=dana, plan_id=created["id"], signed_on=date(2026, 9, 1))
    return account, PaymentPlan.objects.get(pk=created["id"])


def test_us_pay_019_tc1__an_active_current_plan_pauses_the_ladder_over_the_arrears(brazos, dana):
    """TC-1 — and the SCOPE of the pause, which is the whole ruling.

    The ladder pauses over *the arrears this plan spreads*. It does NOT pause
    the current month's bill — DEF-061, closed by the PO on 2026-08-11 — and the
    decision says so on its own result rather than leaving a screen to imply it.
    """
    with tenant_ctx(brazos):
        account, _ = an_active_plan(brazos, dana)
        decision = dunning.collections_pause_for(account.id, as_of=date(2026, 9, 1))
        assert decision.paused is True
        assert decision.covers == "the arrears this plan spreads"
        assert "CURRENT month's bill" in decision.not_covered
        assert dunning.plan_pauses_current_bill() is False


def test_us_pay_019_tc3__a_missed_instalment_lifts_the_pause_and_ends_nothing(brazos, dana):
    """**The join of the two rulings, and the reading this lane had to make.**

    BR-CUS-043 is CONFIRMED and untouched: the pause holds *while active AND
    current*. An instalment that came and went unpaid means the plan is not
    current, so the pause lifts and the ladder resumes over the arrears — while
    the plan stays ACTIVE, for the tenth miss as for the first, because "nodrop"
    superseded the DROP-OFF and not the word "current".

    ⚠ US-PAY-019 TC-3 expects the opposite (*"One miss (below threshold) → pause
    holds"*) and says why in its own words: *below threshold*. That threshold was
    BR-PAY-016's two-miss void, which no longer exists. **OQ-170** puts the
    question the missing threshold leaves open — is there a grace period first? —
    to the PO rather than inventing a number of days here.
    """
    with tenant_ctx(brazos):
        account, plan = an_active_plan(brazos, dana)
        # Instalment 1 came due on 1 Sep and nothing was posted.
        decision = dunning.collections_pause_for(account.id, as_of=date(2026, 9, 2))
        assert decision.paused is False
        assert decision.reason == dunning.PAUSE_PLAN_BEHIND
        assert "stays active" in decision.detail
        assert "OQ-170" in decision.detail

        plan.refresh_from_db()
        assert plan.status == PLAN_ACTIVE, "nobody is dropped off a plan (PO 2026-08-11)"


def test_us_pay_019_tc3b__ten_misses_change_nothing_about_the_plan(brazos, dana):
    """The absence at scale — no counter, no threshold, no transition."""
    with tenant_ctx(brazos):
        account, plan = an_active_plan(brazos, dana)
        for _ in range(10):
            dunning.collections_pause_for(account.id, as_of=date(2027, 6, 1))
            plan.refresh_from_db()
            assert plan.status == PLAN_ACTIVE
        assert "missed_count" not in {f.name for f in PaymentPlan._meta.get_fields()}


def test_us_pay_019_tc2__late_fee_suspension_is_a_per_plan_election(brazos, dana):
    """TC-2 — BR-CUS-043: elected, not global.

    Election ON → billing's late-fee candidates exclude the account while it is
    current. Election OFF → late fees continue on a plan that is current. The
    fee ITSELF is billing's (BR-BIL-001 and its $25.00 floor as amended on
    2026-08-11) and is not restated anywhere in payments.
    """
    with tenant_ctx(brazos):
        account_on, _ = an_active_plan(brazos, dana, suspend_late_fees=True)
        assert dunning.late_fee_suspended_for(account_on.id, as_of=date(2026, 9, 1)) is True

        account_off, _ = an_active_plan(brazos, dana, account_no="A-11341", suspend_late_fees=False)
        assert dunning.late_fee_suspended_for(account_off.id, as_of=date(2026, 9, 1)) is False


def test_us_pay_019_tc6__a_forced_disconnect_is_refused_server_side(brazos, dana):
    """TC-6 (negative) — BR-CUS-043, and the election that can decline the block.

    A plan agreed WITHOUT a disconnect hold does not block disconnect: that is
    the customer's own election (`suspend_disconnect`), not a bug, and the two
    answers must be distinguishable on the S34 column.
    """
    with tenant_ctx(brazos):
        account, _ = an_active_plan(brazos, dana)
        blocked, why = dunning.disconnect_blocked(account.id, as_of=date(2026, 9, 1))
        assert blocked is True
        assert "server-side" in why

        without_hold, _ = an_active_plan(
            brazos, dana, account_no="A-11341", suspend_disconnect=False
        )
        blocked, why = dunning.disconnect_blocked(without_hold.id, as_of=date(2026, 9, 1))
        assert blocked is False
        assert "WITHOUT a disconnect hold" in why


def test_us_pay_019_tc0__a_plan_that_is_not_yet_signed_pauses_nothing(brazos, dana):
    """BR-CUS-044 — a plan pauses nothing before the customer signs it.

    A plan activated early would stop chasing a debt nobody has agreed to.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        a_plan(brazos, dana, account)
        decision = dunning.collections_pause_for(account.id, as_of=date(2026, 8, 25))
        assert decision.paused is False
        assert decision.reason == dunning.PAUSE_PLAN_NOT_ACTIVE


def test_us_pay_019_tc4__what_ends_a_plan_other_than_paying_it_is_unruled(brazos, dana):
    """TC-4 — **PO ruling 2026-08-12: _"Write-off closes"_ (OQ-171 CLOSED).**

    There is still no VOID: nobody is dropped off a plan and the miss-driven
    drop is superseded. What ends a plan other than paying it is a WRITE-OFF,
    and the PO's ruling is as much about who decides as what happens — *"these
    are user business decision, they will make a decision, we have to provide a
    mechanism and report it"*.

    This test asserted the refusal until then. The refusal mattered: one live
    plan per account (BR-CUS-043) meant a plan that could never close locked
    that customer out of ever agreeing another one.
    """
    with tenant_ctx(brazos):
        _, plan = an_active_plan(brazos, dana)
        closed = dunning.close_plan_on_write_off(
            actor=dana,
            plan_id=plan.pk,
            written_off_on=date(2026, 8, 12),
            reason="arrears written off",
        )
        assert closed["status"] == "closed"
        assert closed["created"] is True

        plan.refresh_from_db()
        assert plan.status == "closed"
        assert plan.closed_on == date(2026, 8, 12)

        # A second click closes nothing twice — the mechanism is idempotent, so
        # a double-submitted write-off cannot produce two closures in the trail.
        assert (
            dunning.close_plan_on_write_off(
                actor=dana, plan_id=plan.pk, written_off_on=date(2026, 8, 12)
            )["created"]
            is False
        )

        # And the account is free to take a new plan, which is the whole point.
        assert plans.live_plan_for(plan.account_id) is None


def test_us_pay_019_tc5__a_closed_plan_pauses_nothing(brazos, dana):
    """TC-5 — the account is settled and no ladder applies to a debt that is gone."""
    with tenant_ctx(brazos):
        account, plan = an_active_plan(brazos, dana)
        for seq in range(1, 7):
            plans.record_installment_payment(
                actor=dana,
                plan_id=plan.pk,
                seq=seq,
                payment_id=None,
                posted_on=date(2026, 9, 1),
            )
        decision = dunning.collections_pause_for(account.id, as_of=date(2027, 3, 1))
        assert decision.paused is False
        assert decision.reason == dunning.PAUSE_NO_PLAN


def test_us_pay_019_tc7__pause_gates_never_cross_tenants(brazos, dana):
    """TC-7 (isolation) — the gate reads this tenant's plans only."""
    with tenant_ctx(brazos):
        account, _ = an_active_plan(brazos, dana)
        assert dunning.collections_pause_for(account.id, as_of=date(2026, 9, 1)).plan_id
        assert PaymentPlan.objects.filter(tenant=brazos).count() == PaymentPlan.objects.count()
