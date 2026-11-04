# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-017 (plan rows + schedule math + activation on signature)
#           Screens: S24 · S34
# Rules:    BR-CUS-043 (the schedule re-sums exactly; one live plan per account)
#           · BR-CUS-044 (activation on the CUSTOMER's e-signature alone; ⚠ its
#           `defaulted` state SUPERSEDED — PO 2026-08-11) · BR-PAY-016 (⚠ "2nd
#           miss VOIDS" SUPERSEDED by the same ruling) · BR-PAY-021 (on-time is
#           the POSTING date) · CLAUDE.md rule 2 · rule 7
# Golden:   PE-13 → GT-47 (B5 ❄️ FROZEN): 267.30 − 50.00 down over 6 →
#           5 × 36.22 + 36.20
# ───────────────────────────────────────────────────────
"""The plan rows, and the two halves of the product finally meeting.

The wizard's arithmetic (`apps/customers/payment_plan.build_schedule`) has been
live, tested and frozen as GT-47 since it shipped, and had nowhere to be saved:
`send_agreement` raised `PaymentPlanUnavailable` on every call. These tests
drive the REAL wizard schedule into the REAL payments rows, which is the join
that was missing.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.customers import payment_plan as wizard
from apps.payments import plans
from apps.payments.collections_models import (
    PLAN_ACTIVE,
    PLAN_AGREEMENT_SENT,
    PLAN_CLOSED,
    PaymentPlan,
    PaymentPlanInstallment,
)
from apps.payments.exceptions import PaymentRuleError

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

#: PE-13 verbatim (B5 ❄️ FROZEN, GT-47). Not recomputed here and not restated:
#: the schedule comes out of the wizard, which is the one place it is derived.
BALANCE = Decimal("267.30")
DOWN = Decimal("50.00")
PROPOSED_ON = date(2026, 8, 20)


def a_schedule():
    """GT-47 through the WIZARD, not through a literal in this file."""
    schedule = wizard.build_schedule(
        total=BALANCE,
        down_payment=DOWN,
        installments=6,
        cadence="monthly",
        first_due_date=date(2026, 9, 1),
    )
    return tuple((row.seq, row.due_date, row.amount) for row in schedule.installments)


def a_plan(brazos, dana, account, **overrides):
    values = dict(
        actor=dana,
        account_id=account.id,
        total_amount=BALANCE,
        down_payment=DOWN,
        installments=6,
        cadence="monthly",
        currency="USD",
        schedule=a_schedule(),
        proposed_on=PROPOSED_ON,
    )
    values.update(overrides)
    return plans.propose_payment_plan(**values)


def test_us_pay_017_tc1__the_frozen_schedule_lands_as_rows_to_the_cent(brazos, dana):
    """TC-1 — PE-13/GT-47: 5 × 36.22 + a final 36.20, Σ + down = 267.30.

    The figures are the WIZARD's; what is asserted here is that they reached the
    table unchanged. A plan whose rows disagree with the agreement the customer
    signed is the failure this whole split exists to prevent.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        created = a_plan(brazos, dana, account)

        plan = PaymentPlan.objects.get(pk=created["id"])
        rows = list(plan.installments.all().order_by("seq"))
        assert [row.amount for row in rows] == [
            Decimal("36.220000"),
            Decimal("36.220000"),
            Decimal("36.220000"),
            Decimal("36.220000"),
            Decimal("36.220000"),
            Decimal("36.200000"),
        ]
        assert sum((row.amount for row in rows), Decimal("0")) + plan.down_payment == Decimal(
            "267.300000"
        )
        assert plan.status == PLAN_AGREEMENT_SENT
        assert created["status"] == "proposed", (
            "the RETURNED status is what the wizard's own state machine validates "
            "FROM — returning agreement_sent would make next_status_on_send raise"
        )


def test_us_pay_017_tc3__a_schedule_that_does_not_re_sum_never_reaches_a_row(brazos, dana):
    """TC-3 — BR-CUS-043's one invariant, re-checked at the table.

    US-CUS-018 TC-5's shape: edits totalling less than the spread. The wizard
    already refuses it; this refuses it again, because the wizard is a screen
    and this is the table, and an agreement whose own numbers disagree is one a
    customer signs.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        short = tuple(
            (seq, due, Decimal("30.00")) for seq, due, _ in a_schedule()
        )  # 6 × 30.00 + 50 down = 230.00, not 267.30
        with pytest.raises(PaymentRuleError) as refusal:
            a_plan(brazos, dana, account, schedule=short)
        assert "does not re-sum" in str(refusal.value)
        assert not PaymentPlan.objects.exists()


def test_us_pay_017_tc2__the_customers_signature_alone_activates(brazos, dana):
    """TC-2 + TC-7 — BR-CUS-044: no countersignature exists and none is waited for.

    And the negative half in the same test, because they are one rule: an
    activation attempted from a state that never saw a signature is REJECTED and
    the plan stays where it was. A plan activated early pauses dunning on a debt
    nobody agreed to.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        created = a_plan(brazos, dana, account)
        activated = plans.activate_payment_plan(
            actor=dana, plan_id=created["id"], signed_on=date(2026, 9, 1)
        )
        assert activated["status"] == PLAN_ACTIVE
        assert PaymentPlan.objects.get(pk=created["id"]).signed_on == date(2026, 9, 1)

        with pytest.raises(PaymentRuleError) as refusal:
            plans.activate_payment_plan(
                actor=dana, plan_id=created["id"], signed_on=date(2026, 9, 2)
            )
        assert "signature" in str(refusal.value)


def test_us_pay_017_tc6__one_live_plan_per_account_is_held_by_the_database(brazos, dana):
    """TC-6 (negative) — BR-CUS-043 / US-CUS-018 TC-7.

    Enforced by a partial unique index, not by a SELECT-then-INSERT: two clerks
    on two screens is exactly the race a Python check loses, and the loser gives
    one debt two schedules with no rule for which one the customer signed.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        a_plan(brazos, dana, account)
        with pytest.raises(PaymentRuleError) as refusal:
            a_plan(brazos, dana, account)
        assert "already has a live payment plan" in str(refusal.value)
        assert PaymentPlan.objects.count() == 1


def test_us_pay_017_tc4__an_instalment_posted_on_its_due_date_is_on_time(brazos, dana):
    """TC-4 — BR-PAY-021: posting date, never clearing date.

    A cheque POSTED 1 Oct (the due date) that CLEARS 3 Oct is on time. Nothing
    in this path reads a clearing date, and the absence is the rule.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        created = a_plan(brazos, dana, account)
        plans.activate_payment_plan(actor=dana, plan_id=created["id"], signed_on=date(2026, 9, 1))
        result = plans.record_installment_payment(
            actor=dana,
            plan_id=created["id"],
            seq=1,
            payment_id=None,
            posted_on=date(2026, 9, 1),
        )
        assert result["on_time"] is True
        plan = PaymentPlan.objects.get(pk=created["id"])
        assert not plans.outstanding_installments(plan, as_of=date(2026, 9, 1))


def test_us_pay_017_tc5__the_final_instalment_closes_the_plan(brazos, dana):
    """TC-5 — and the ONLY way a plan ends (PO 2026-08-11, "nodrop")."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        created = a_plan(brazos, dana, account)
        plans.activate_payment_plan(actor=dana, plan_id=created["id"], signed_on=date(2026, 9, 1))
        for seq in range(1, 7):
            outcome = plans.record_installment_payment(
                actor=dana,
                plan_id=created["id"],
                seq=seq,
                payment_id=None,
                posted_on=date(2026, 9, 1),
            )
        assert outcome["status"] == PLAN_CLOSED
        assert PaymentPlan.objects.get(pk=created["id"]).closed_on == date(2026, 9, 1)


def test_us_pay_017_tc9__nobody_is_dropped_off_and_there_is_nothing_to_count(brazos, dana):
    """**PO 2026-08-11: "nodrop we chase for payments until write off".**

    Ten missed instalments. The plan is still ACTIVE, there is no `missed_count`
    column, no `defaulted` status and no `void` status anywhere in the payments
    vocabulary — and the absence is asserted rather than assumed, because the
    next lane to read BR-PAY-016 without its supersession will try to add one
    back.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        created = a_plan(brazos, dana, account)
        plans.activate_payment_plan(actor=dana, plan_id=created["id"], signed_on=date(2026, 9, 1))
        plan = PaymentPlan.objects.get(pk=created["id"])

        # Every instalment comes and goes unpaid — ten evaluations, deep past
        # the superseded two-miss threshold.
        for _ in range(10):
            missed = plans.outstanding_installments(plan, as_of=date(2027, 6, 1))
            assert len(missed) == 6
            plan.refresh_from_db()
            assert plan.status == PLAN_ACTIVE

        assert not hasattr(plan, "missed_count")
        assert "missed_count" not in {field.name for field in PaymentPlan._meta.get_fields()}
        from apps.payments import collections_models

        assert collections_models.PLAN_STATUSES == (
            "proposed",
            "agreement_sent",
            "active",
            "closed",
        )
        assert "void" not in collections_models.PLAN_STATUSES
        assert "defaulted" not in collections_models.PLAN_STATUSES


def test_us_pay_017_tc8__plans_never_cross_tenants(brazos, dana):
    """TC-8 (isolation) — the service half; RLS is the G5 suite's, on Postgres."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        a_plan(brazos, dana, account)
        assert PaymentPlan.objects.filter(tenant=brazos).count() == PaymentPlan.objects.count()
        assert (
            PaymentPlanInstallment.objects.filter(tenant=brazos).count()
            == PaymentPlanInstallment.objects.count()
        )
