# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-017 (plan rows + instalments) · US-PAY-001 (the payment write
#           path) · US-PAY-019 (the dunning pause) · US-PAY-018 (plan notices)
#           Screens: S21 · S22 · S24 · S35
# Change:   CR-059 CS-23 — *"Nothing links a payment to its instalment on the
#           running product."* A DEFECT, not a feature: `record_installment_
#           payment` had no caller but the demo seeder, so every instalment
#           stayed unmarked, the pause never applied, missed notices went to
#           customers who missed nothing, and the plan could never close.
# Rules:    BR-PAY-021 (an instalment is on time when a payment POSTED by its
#           due date, whatever the clearing date) · BR-CUS-043 (the pause holds
#           while a plan is active AND current; one live plan per account) ·
#           BR-CUS-044 (a plan activates on the customer's e-signature) ·
#           BR-PAY-012 (a down payment carries purpose plan_down) · BR-BIL-073
#           (a plan does NOT suspend the current bill) · CLAUDE.md rule 7
# Golden:   PE-13 → GT-47 (B5 ❄️ FROZEN): 267.30 − 50.00 down over 6 →
#           5 × 36.22 + 36.20. Copied, never recomputed.
# ───────────────────────────────────────────────────────
"""**THE PROOF CR-059 CS-23 NAMES, AND IT COULD NOT PASS BEFORE THIS FIX.**

Verbatim from the change request: *"Pay every instalment on its due date: the
pause holds throughout, no notice is sent, and the plan closes on the last one.
That test cannot pass today."*

`test_cr059_cs23_the_proof__every_instalment_paid_on_its_due_date` is that
sentence as a test, and it was RUN RED first (hard-won law 7). Against the
unfixed tree it failed on the FIRST instalment — the pause had already lifted
the day after 1 September and a missed-instalment notice was due — for a
customer who had paid on the day they agreed.

WHAT THE OTHER CASES PIN, because each is a rule and not a preference:

  * **the earliest unmet instalment** is the one a payment meets, whether or not
    the amount matches it exactly (CR-059 CS-23, and it is the only half of this
    change that was ours to decide);
  * **one payment meets at most ONE instalment.** A surplus is not a second
    instalment — that follows from `apps/customers/payment_plan.
    split_payment_between`, the PO's *"plan first"* ruling of 2026-08-12, which
    takes ONE instalment amount and says in its own worked figures that anything
    beyond it is payments' credit rule and not the schedule's;
  * **short of the instalment, nothing is met.** Same ruling, same function:
    *"a part-paid instalment is still a missed instalment and the customer needs
    to know that"*;
  * a **down payment** is not an instalment (BR-PAY-012 / BR-CUS-043: the
    schedule is what remains AFTER the down payment);
  * a plan that is **not yet signed** has no schedule to meet (BR-CUS-044);
  * a **processing** payment meets no instalment for the same reason it meets no
    bill — the money has not arrived.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from apps.payments import dunning, models, notices, plans, services
from apps.payments.collections_models import (
    PLAN_ACTIVE,
    PLAN_CLOSED,
    PaymentPlan,
)

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_017_payment_plans import DOWN, a_plan
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

#: PE-13 verbatim (B5 ❄️ FROZEN, GT-47) — 5 × 36.22 + a final 36.20. Copied from
#: the ratified figure, never recomputed here.
PE13_INSTALLMENT = Decimal("36.22")
PE13_FINAL_INSTALLMENT = Decimal("36.20")

SIGNED_ON = date(2026, 9, 1)


def _at(on_date):
    """A posting moment on a business date. An ARGUMENT, never a clock.

    BR-PAY-033: the posting date is the user's. Every date in this file is
    written down, so a run in June and a run in December assert the same thing.
    """
    return datetime(on_date.year, on_date.month, on_date.day, 10, 0, tzinfo=UTC)


def an_active_plan(brazos, dana, *, account_no="A-59023"):
    """The frozen PE-13 plan, signed, on a fresh account."""
    account = an_account(dana, brazos, account_no=account_no)
    created = a_plan(brazos, dana, account)
    plans.activate_payment_plan(actor=dana, plan_id=created["id"], signed_on=SIGNED_ON)
    plan = PaymentPlan.objects.get(pk=created["id"])
    return account, plan


def schedule_of(plan):
    """The plan's instalment rows, in the customer's own numbering."""
    return list(plan.installments.all().order_by("seq"))


def pay(actor, account, amount, on_date, **overrides):
    """One payment through the REAL write path — no ORM shortcut, no stub."""
    values = dict(
        account_id=account.pk,
        amount=amount,
        posted_at=_at(on_date),
        cleared_at=_at(on_date),
        idempotency_reference=f"cr059:{account.pk}:{on_date}:{amount}",
    )
    values.update(overrides)
    return services.record_payment(actor, **values)


def missed_notices(plan, *, as_of):
    """The MISSED and SECOND notices due today — the ones a paying customer
    must never receive. Reminders are excluded on purpose: a −3-day reminder
    before the NEXT instalment is correct behaviour and is not what CS-23 is
    about."""
    return [
        (kind, row.seq)
        for kind, row in notices.plan_notices_due(plan, as_of=as_of)
        if kind in (notices.NOTICE_PLAN_MISSED, notices.NOTICE_PLAN_SECOND)
    ]


# ── THE PROOF ───────────────────────────────────────────────────────────────
def test_cr059_cs23_the_proof__every_instalment_paid_on_its_due_date(brazos, dana):
    """**CR-059 CS-23's own sentence, run.**

    *"Pay every instalment on its due date: the pause holds throughout, no
    notice is sent, and the plan closes on the last one."*

    Nothing in this test names an instalment: the payments go through
    `record_payment` exactly as the S22 counter form and the API send them, and
    the link is the product's own. That is the point — the defect was that the
    ordinary path never touched the instalment row.
    """
    with tenant_ctx(brazos):
        account, plan = an_active_plan(brazos, dana)
        rows = schedule_of(plan)
        assert [row.amount for row in rows] == [
            Decimal("36.220000"),
            Decimal("36.220000"),
            Decimal("36.220000"),
            Decimal("36.220000"),
            Decimal("36.220000"),
            Decimal("36.200000"),
        ], "PE-13/GT-47 — the frozen schedule, copied"

        for installment in rows:
            due = installment.due_date
            result = pay(dana, account, installment.amount, due)
            assert result.created is True

            # (1) the instalment row is STAMPED — the link this change is about.
            installment.refresh_from_db()
            assert installment.paid_posted_on == due, (
                f"instalment {installment.seq} was paid on its due date and the row "
                "still says nothing met it"
            )
            assert str(installment.paid_payment_id) == result.payment_id

            # (2) the pause HOLDS the day after — a customer who pays on time is
            #     not chased (BR-CUS-043).
            day_after = due + timedelta(days=1)
            plan.refresh_from_db()
            if plan.status == PLAN_ACTIVE:
                decision = dunning.collections_pause_for(account.pk, as_of=day_after)
                assert (
                    decision.paused is True
                ), f"the pause lifted the day after instalment {installment.seq} was PAID"
                assert decision.reason == dunning.PAUSE_ACTIVE_AND_CURRENT

            # (3) no missed-instalment notice is due — for any instalment.
            assert missed_notices(plan, as_of=day_after) == []

            # (4) and the result tells the S22 modal what it met.
            assert result.installment_seq == installment.seq
            assert result.plan_id == str(plan.pk)
            assert result.installment_on_time is True, "BR-PAY-021 — posted ON the due date"

        # (5) the plan closes on the last one — the only way a plan ends by
        #     payment (PO 2026-08-11, "nodrop").
        plan.refresh_from_db()
        assert plan.status == PLAN_CLOSED
        assert plan.closed_on == rows[-1].due_date
        assert plans.live_plan_for(account.pk) is None


# ── (a) WHICH INSTALMENT, WHEN THE AMOUNT IS NOT AN EXACT MATCH ─────────────
def test_cr059_cs23__a_non_matching_amount_meets_the_earliest_unmet_instalment(brazos, dana):
    """**The earliest unmet one.** CR-059 CS-23, and it is ours to decide.

    $40.00 is not $36.22 and it still meets instalment 1: a customer who rounds
    up has paid their instalment, and a product that required an exact match
    would report them behind on money it had taken.
    """
    with tenant_ctx(brazos):
        account, plan = an_active_plan(brazos, dana)
        first, second = schedule_of(plan)[:2]

        result = pay(dana, account, Decimal("40.00"), first.due_date)
        assert result.installment_seq == 1

        first.refresh_from_db()
        second.refresh_from_db()
        assert first.paid_posted_on == first.due_date
        assert second.paid_posted_on is None, "the surplus 3.78 is not a second instalment"

        # And the NEXT payment moves on to instalment 2 — "earliest UNMET".
        again = pay(dana, account, PE13_INSTALLMENT, second.due_date)
        assert again.installment_seq == 2


# ── (b) WHAT HAPPENS WHEN ONE PAYMENT COVERS TWO INSTALMENTS ────────────────
def test_cr059_cs23__one_payment_meets_at_most_one_instalment(brazos, dana):
    """**One payment, one instalment.** $100.00 covers 36.22 twice over and
    meets instalment 1 alone.

    The ruled splitter (`apps/customers/payment_plan.split_payment_between`, PO
    2026-08-12 *"plan first"*) takes ONE instalment amount and states that the
    surplus is payments' credit rule rather than the schedule's. So a surplus is
    money on the account, never a second dated obligation discharged early.
    """
    with tenant_ctx(brazos):
        account, plan = an_active_plan(brazos, dana)
        rows = schedule_of(plan)

        result = pay(dana, account, Decimal("100.00"), rows[0].due_date)
        assert result.installment_seq == 1

        for row in rows:
            row.refresh_from_db()
        assert [row.paid_posted_on is not None for row in rows] == [
            True,
            False,
            False,
            False,
            False,
            False,
        ]
        plan.refresh_from_db()
        assert plan.status == PLAN_ACTIVE, "a surplus does not close a plan early"


# ── SHORT OF THE INSTALMENT ─────────────────────────────────────────────────
def test_cr059_cs23__short_of_the_instalment_meets_nothing(brazos, dana):
    """**A part-paid instalment is still a missed one** — PO 2026-08-12.

    $20.00 against a $36.22 instalment leaves the instalment unmet, so the
    customer is told (the missed notice is due) rather than reassured by a
    schedule that reads paid on money that did not cover it.
    """
    with tenant_ctx(brazos):
        account, plan = an_active_plan(brazos, dana)
        first = schedule_of(plan)[0]

        result = pay(dana, account, Decimal("20.00"), first.due_date)
        assert result.installment_seq is None
        assert plans.INSTALLMENT_NOT_COVERED in {row["code"] for row in result.problems}

        first.refresh_from_db()
        assert first.paid_posted_on is None
        day_after = first.due_date + timedelta(days=1)
        assert missed_notices(plan, as_of=day_after) == [(notices.NOTICE_PLAN_MISSED, 1)]


# ── THE CLERK'S OVERRIDE (CR-059 CS-23: "with the option to change it") ─────
def test_cr059_cs23__a_named_instalment_wins_over_the_earliest_unmet(brazos, dana):
    """S22/S35 show which instalment this payment is meeting, with the option to
    change it. The server takes the clerk's choice and refuses a seq that is not
    on this plan — a typo must not become a silent link to instalment 1."""
    with tenant_ctx(brazos):
        account, plan = an_active_plan(brazos, dana)
        rows = schedule_of(plan)

        result = pay(dana, account, PE13_INSTALLMENT, rows[2].due_date, installment_seq=3)
        assert result.installment_seq == 3
        for row in rows:
            row.refresh_from_db()
        assert rows[0].paid_posted_on is None
        assert rows[2].paid_posted_on == rows[2].due_date

        with pytest.raises(services.PaymentRuleError) as refusal:
            pay(dana, account, PE13_INSTALLMENT, rows[0].due_date, installment_seq=99)
        assert "instalment 99" in str(refusal.value)
        # Nothing was written: the refusal takes the payment with it.
        assert models.Payment.objects.filter(account=account).count() == 1


# ── THE PURPOSES THAT MEET NO INSTALMENT ────────────────────────────────────
def test_cr059_cs23__a_down_payment_is_not_an_instalment(brazos, dana):
    """BR-PAY-012 / BR-CUS-043 — the schedule is what remains AFTER the down
    payment, so a down payment that marked instalment 1 would have the customer
    pay for the same $36.22 twice."""
    with tenant_ctx(brazos):
        account, plan = an_active_plan(brazos, dana)

        result = pay(
            dana,
            account,
            DOWN,
            SIGNED_ON,
            purpose=models.PURPOSE_PLAN_DOWN,
            plan_id=plan.pk,
        )
        assert result.installment_seq is None
        assert plans.INSTALLMENT_NOT_A_SCHEDULE_PAYMENT in {row["code"] for row in result.problems}
        assert [row.paid_posted_on for row in schedule_of(plan)] == [None] * 6


def test_cr059_cs23__an_unsigned_plan_has_no_schedule_to_meet(brazos, dana):
    """BR-CUS-044 — a plan pauses nothing and settles nothing before the
    customer signs it."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-59024")
        created = a_plan(brazos, dana, account)  # proposed → agreement_sent, unsigned
        plan = PaymentPlan.objects.get(pk=created["id"])

        result = pay(dana, account, PE13_INSTALLMENT, SIGNED_ON)
        assert result.installment_seq is None
        assert plans.INSTALLMENT_PLAN_NOT_ACTIVE in {row["code"] for row in result.problems}
        assert [row.paid_posted_on for row in schedule_of(plan)] == [None] * 6


def test_cr059_cs23__a_processing_payment_meets_no_instalment(brazos, dana):
    """The money has not arrived. It meets no bill (the shipped rule) and it
    meets no instalment either — and the result SAYS so rather than leaving the
    silence to be read as a link."""
    with tenant_ctx(brazos):
        account, plan = an_active_plan(brazos, dana)
        first = schedule_of(plan)[0]

        result = pay(dana, account, PE13_INSTALLMENT, first.due_date, cleared_at=None)
        assert result.status == models.PAYMENT_PROCESSING
        assert result.installment_seq is None
        assert plans.INSTALLMENT_NOT_CLEARED in {row["code"] for row in result.problems}

        first.refresh_from_db()
        assert first.paid_posted_on is None


# ── HARD RULE 7 ─────────────────────────────────────────────────────────────
def test_cr059_cs23__the_link_writes_an_audit_row(brazos, dana, audit_rows):
    """CLAUDE.md rule 7 — the link decides whether a customer is chased and
    whether their plan closes, so it leaves a trail with its own figures."""
    with tenant_ctx(brazos):
        account, plan = an_active_plan(brazos, dana)
        first = schedule_of(plan)[0]
        pay(dana, account, PE13_INSTALLMENT, first.due_date)

        linked = [row for row in audit_rows if row["action"] == plans.AUDIT_INSTALLMENT_MET]
        assert len(linked) == 1
        after = linked[0]["after"]
        assert after["installment_seq"] == 1
        assert after["amount"] == "36.22"
        assert after["on_time"] is True
        assert after["posted_on"] == first.due_date.isoformat()


# ── CLAUDE.md LAW 14 ────────────────────────────────────────────────────────
def test_cr059_cs23__a_database_refusal_on_the_link_does_not_bounce_the_payment(
    brazos, dana, monkeypatch
):
    """The link is caught in a SAVEPOINT and the money still lands.

    A customer handed the cash over: their payment must not be refused because
    a schedule row was unavailable. The failure is reported by name instead, so
    it looks like a problem a person must fix rather than like a payment that
    happened to meet no instalment.

    ⚠ **WHAT THIS PROVES AND WHAT IT CANNOT.** It proves the CONTROL FLOW — the
    payment, its allocation and its ledger entry survive the refusal and the
    code reaches the result. It does NOT prove CLAUDE.md law 14's actual
    subject: `config/settings/test.py` hardcodes in-memory SQLite, which has no
    aborted-transaction state, so a version WITHOUT the nested
    `transaction.atomic()` would pass this test and lose the payment on
    PostgreSQL. The savepoint is the prescribed shape and the PostgreSQL run is
    owed — no PostgreSQL was reachable in the container this was written in.
    """
    from django.db import DatabaseError

    def refuse(**_kwargs):
        raise DatabaseError("payment_plan_installments is unavailable")

    with tenant_ctx(brazos):
        account, plan = an_active_plan(brazos, dana)
        first = schedule_of(plan)[0]
        monkeypatch.setattr(plans, "link_payment_to_installment", refuse)

        result = pay(dana, account, PE13_INSTALLMENT, first.due_date)

        assert result.created is True, "the customer's money is recorded"
        assert result.posted_to_ledger is True, "and it reached the books"
        assert result.installment_seq is None
        codes = {row["code"] for row in result.problems}
        assert plans.INSTALLMENT_LINK_FAILED in codes

        first.refresh_from_db()
        assert first.paid_posted_on is None
