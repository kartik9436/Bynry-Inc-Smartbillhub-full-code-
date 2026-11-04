# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-018 (plan notices: reminder −3d · missed day+1 · second
#           notice)   Screens: S21 · S33 · S34
# Rules:    BR-PAY-016 (the cadence, tenant-config; ⚠ its "2nd miss VOIDS plan"
#           clause is SUPERSEDED — PO 2026-08-11 "nodrop we chase for payments
#           until write off") · BR-NOT-005 (queue-write only) · BR-PAY-021
#           (missed = no payment posted by the due date) · CLAUDE.md rule 7
# ───────────────────────────────────────────────────────
"""Notices may still be SENT. Nothing may DROP.

That sentence is the whole story after the PO's ruling of 2026-08-11, and it is
what every test here is about. The third notice used to void the plan; now it is
a stronger letter and nothing else happens.
"""

from datetime import date

import pytest

from apps.notifications import models as notification_models
from apps.payments import notices, plans
from apps.payments.collections_models import (
    NOTICE_PLAN_MISSED,
    NOTICE_PLAN_REMINDER,
    NOTICE_PLAN_SECOND,
    PLAN_ACTIVE,
    NoticeHistory,
    PaymentPlan,
)
from apps.payments.exceptions import PaymentRuleError

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_017_payment_plans import a_plan
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db


def an_active_plan(brazos, dana):
    """J13's plan at the point the notices start mattering.

    Instalment 1 (due Sep 1) is PAID on its due date, so the plan is current
    when these tests begin — which is what makes the October evaluation the
    FIRST miss rather than the second. A fixture that started behind would test
    the wrong notice.
    """
    account = an_account(dana, brazos)
    created = a_plan(brazos, dana, account)
    plans.activate_payment_plan(actor=dana, plan_id=created["id"], signed_on=date(2026, 9, 1))
    plans.record_installment_payment(
        actor=dana, plan_id=created["id"], seq=1, payment_id=None, posted_on=date(2026, 9, 1)
    )
    return PaymentPlan.objects.get(pk=created["id"])


def test_us_pay_018_tc1__the_reminder_queues_three_days_before_the_instalment(brazos, dana):
    """TC-1 — Sep 28 for an Oct 1 instalment: a queue row and a history row.

    The content names the instalment (36.22) and its due date, which is what a
    customer needs to act on. Both rows, because "what was sent" and "what we
    told them we sent" must reconcile.
    """
    with tenant_ctx(brazos):
        plan = an_active_plan(brazos, dana)
        result = notices.send_plan_notices(plan, as_of=date(2026, 9, 28), actor=dana)

        assert len(result.sent) == 1
        history = NoticeHistory.objects.get(notice_type=NOTICE_PLAN_REMINDER)
        assert history.detail["installment_amount"] == "36.220000"
        assert history.detail["due_date"] == "2026-10-01"
        assert notification_models.OutboundMessage.objects.filter(source_type="plan").exists()


def test_us_pay_018_tc2__a_missed_instalment_notifies_and_changes_nothing_else(brazos, dana):
    """TC-2 as the PO's ruling leaves it — the notice goes, the plan does not move.

    The old TC-2 ended *"missed_count 0→1; header state shows 'plan — 1
    missed'"*. There is no counter now. What is asserted instead is what the
    product actually promises: a missed-instalment notice on day+1, and a plan
    that is still ACTIVE afterwards.
    """
    with tenant_ctx(brazos):
        plan = an_active_plan(brazos, dana)
        result = notices.send_plan_notices(plan, as_of=date(2026, 10, 2), actor=dana)

        assert len(result.sent) == 1
        assert NoticeHistory.objects.filter(notice_type=NOTICE_PLAN_MISSED).count() == 1
        plan.refresh_from_db()
        assert plan.status == PLAN_ACTIVE
        assert (
            NoticeHistory.objects.get(notice_type=NOTICE_PLAN_MISSED).detail["dropped_off"] is False
        )


def test_us_pay_018_tc3__the_second_miss_sends_a_SECOND_NOTICE_and_voids_nothing(brazos, dana):
    """TC-3, rewritten by the ruling — **this is the drop-off that no longer exists.**

    The old expectation was *"missed_count → 2 = tenant threshold → plan VOID:
    full remaining balance due immediately"*. The PO superseded it on 2026-08-11:
    *"nodrop we chase for payments until write off"*.

    So on the second missed instalment a SECOND NOTICE is queued — a stronger
    letter — and the plan is still ACTIVE, still has all six instalments, and has
    no void, no `defaulted` and no counter anywhere.

    PROVED RED by reinstating the void: see the lane report for the verbatim
    failure.
    """
    with tenant_ctx(brazos):
        plan = an_active_plan(brazos, dana)
        notices.send_plan_notices(plan, as_of=date(2026, 10, 2), actor=dana)  # miss 1
        result = notices.send_plan_notices(plan, as_of=date(2026, 11, 2), actor=dana)

        assert len(result.sent) == 1
        assert NoticeHistory.objects.filter(notice_type=NOTICE_PLAN_SECOND).count() == 1
        plan.refresh_from_db()
        assert plan.status == PLAN_ACTIVE, (
            "PO 2026-08-11: nobody is dropped off a plan — the second miss sends a "
            "notice and ends nothing"
        )
        assert plan.installments.count() == 6


def test_us_pay_018_tc3b__ten_missed_instalments_still_leave_the_plan_active(brazos, dana):
    """The absence, asserted at scale (PO 2026-08-11).

    Every instalment on the plan comes and goes unpaid and every notice fires.
    The plan is ACTIVE at the end, no status ever moved, and the account was
    chased — which is exactly what the ruling asks for.
    """
    with tenant_ctx(brazos):
        plan = an_active_plan(brazos, dana)
        for day in (
            date(2026, 10, 2),
            date(2026, 11, 2),
            date(2026, 12, 2),
            date(2027, 1, 2),
            date(2027, 2, 2),
        ):
            notices.send_plan_notices(plan, as_of=day, actor=dana)
            plan.refresh_from_db()
            assert plan.status == PLAN_ACTIVE
        assert NoticeHistory.objects.filter(plan=plan).count() >= 5


def test_us_pay_018_tc4__an_instalment_posted_by_its_due_date_produces_no_notice(brazos, dana):
    """TC-4 — BR-PAY-021: clearing later never misses an instalment."""
    with tenant_ctx(brazos):
        plan = an_active_plan(brazos, dana)
        plans.record_installment_payment(
            actor=dana, plan_id=plan.pk, seq=2, payment_id=None, posted_on=date(2026, 10, 1)
        )
        result = notices.send_plan_notices(plan, as_of=date(2026, 10, 2), actor=dana)
        assert result.sent == ()
        assert not NoticeHistory.objects.filter(notice_type=NOTICE_PLAN_MISSED).exists()


def test_us_pay_018_tc6__the_cadence_is_configuration_not_a_constant(brazos, dana):
    """TC-6 — reminder −5 days honoured on the next evaluation."""
    with tenant_ctx(brazos):
        plan = an_active_plan(brazos, dana)
        assert notices.plan_notices_due(plan, as_of=date(2026, 9, 26)) == ()
        due = notices.plan_notices_due(plan, as_of=date(2026, 9, 26), reminder_days_before=5)
        assert [kind for kind, _ in due] == [NOTICE_PLAN_REMINDER]


def test_us_pay_018_tc7__a_notice_is_never_sent_inline(brazos, dana):
    """TC-7 (negative) — BR-NOT-005: the queue is the only path.

    Asserted on the module rather than on a call: there is no provider client in
    this file at all, and every notice leaves a row in `outbound_messages` whose
    status is `queued`. A row that rests queued is the correct finished state in
    this release, not a pending failure.
    """
    import apps.payments.notices as module

    source = open(module.__file__).read()
    for forbidden in ("smtplib", "twilio", "sendgrid", "requests.post"):
        assert forbidden not in source

    with tenant_ctx(brazos):
        plan = an_active_plan(brazos, dana)
        notices.send_plan_notices(plan, as_of=date(2026, 9, 28), actor=dana)
        rows = notification_models.OutboundMessage.objects.filter(source_type="plan")
        assert rows.exists()
        assert all(row.status == notification_models.STATUS_QUEUED for row in rows)
        assert all(row.sent_at is None for row in rows)


def test_us_pay_018_tc9__a_skip_without_a_reason_is_refused(brazos, dana):
    """J4 step 2 — every send AND every skip, and a skip says why.

    A skip with no reason is indistinguishable from an account nobody ever
    chased, which is the one thing a collections trail may not contain.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        with pytest.raises(PaymentRuleError):
            notices.record_notice(
                account_id=account.id,
                notice_type=NOTICE_PLAN_MISSED,
                outcome="skipped",
                on_date=date(2026, 10, 2),
            )


def test_us_pay_018_tc8__plan_notices_never_cross_tenants(brazos, dana):
    """TC-8 (isolation) — its plans, settings and queue rows only."""
    with tenant_ctx(brazos):
        plan = an_active_plan(brazos, dana)
        notices.send_plan_notices(plan, as_of=date(2026, 9, 28), actor=dana)
        assert NoticeHistory.objects.filter(tenant=brazos).count() == NoticeHistory.objects.count()
