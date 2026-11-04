# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-017 (plan rows + schedule math + activation on signature —
#           the PAYMENTS-owned half)   Screens: S24 · S34
# Rules:    BR-CUS-043 (schedule = (total − down) ÷ n, 2dp half-up, remainder on
#           the FINAL instalment; step-2 edits must re-sum EXACTLY; one live
#           plan per account; late-fee suspension is a per-plan election) ·
#           BR-CUS-044 (proposed → agreement_sent → active ON THE CUSTOMER'S
#           E-SIGNATURE ALONE → closed; ⚠ its `defaulted` state and
#           {missed_count} clause are SUPERSEDED — PO 2026-08-11) · BR-PAY-012
#           (a down payment carries purpose plan_down) · BR-PAY-016 (⚠ its
#           "2nd miss VOIDS plan" clause is SUPERSEDED by the same ruling) ·
#           BR-PAY-021 (an instalment is on time when a payment POSTED by its
#           due date, whatever the clearing date) · BR-CUS-037 (customers writes
#           no financial table — it hands the schedule here) · BR-TEN-043 (event
#           time is an argument) · CLAUDE.md rule 2 · rule 6 · rule 7
# Golden:   PE-13 → **GT-47** (B5 ❄️ FROZEN): 267.30 − 50.00 down over 6 →
#           **5 × 36.22 + 36.20**. This module does not COMPUTE that — it
#           persists what the wizard computed and re-checks that it re-sums.
# Change:   CR-059 CS-23 (2026-09-01) — `record_installment_payment` had no
#           caller on the running product. `link_payment_to_installment` below
#           is it, and `services.record_payment` calls it in the payment's own
#           transaction. No new rule: the choice of instalment and the
#           covers-in-full test both come from the PO's "plan first" ruling of
#           2026-08-12 (OQ-139) via apps/customers/payment_plan.
# Tests:    06-backend/tests/test_us_pay_017_payment_plans.py ·
#           06-backend/tests/test_cr059_cs23_installment_link.py
# Impacts:  apps/customers/payment_plan_service.py (the S24 wizard that has been
#           refusing to save since it shipped) · apps/customers/seams.py (which
#           resolves `apps.payments.services.propose_payment_plan` BY NAME) ·
#           apps/payments/services.record_payment (CR-059 CS-23 — its caller) ·
#           apps/customers/payment_plan.split_payment_between (the "plan first"
#           rule, resolved BY NAME) · apps/payments/dunning.py ·
#           apps/payments/notices.py
# ───────────────────────────────────────────────────────
"""The plan ROWS. The arithmetic is the wizard's and is not repeated here.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — 🔒 money math: these rows decide what a
customer in arrears is asked to pay and when. AI-authored 2026-08-11 under the
PO ruling of 2026-08-09; row in 12-governance/09-human-review-ledger.md.

════════════════════════════════════════════════════════════════════════════
THE SCHEDULE MATH IS NOT DUPLICATED. IT IS VALIDATED.
════════════════════════════════════════════════════════════════════════════
`apps/customers/payment_plan.build_schedule` owns BR-CUS-043's arithmetic —
`(total − down) ÷ n`, 2dp half-up, **remainder on the FINAL instalment** — and
it is frozen as GT-47. This module receives the rows the wizard produced and
checks ONE invariant: Σ instalments + down payment = total, to the cent.

That split is deliberate and it is the difference between a check and a second
implementation. A check catches a wrong schedule. A second implementation
eventually disagrees with the first, and then two places in one product tell a
customer two different instalments — which is exactly what
`apps/customers/payment_plan.py` says about the $25 late-fee floor: *"a second
copy of a ruled figure is how two figures start disagreeing."*

════════════════════════════════════════════════════════════════════════════
NOBODY IS DROPPED OFF A PLAN (PO 2026-08-11, OQ-141)
════════════════════════════════════════════════════════════════════════════
Verbatim: **"nodrop we chase for payments until write off"**.

There is no `void`, no `defaulted`, no `missed_count` and no auto-transition in
this module, and their absence is the RULE rather than work left undone. A plan
ends exactly one way here: PAID (`closed`). An account that falls behind is
chased through the ordinary collections path to write-off and stays on its plan
while that happens. `notices.py` still sends — a miss is a fact worth telling
somebody about — and nothing about the plan changes.

════════════════════════════════════════════════════════════════════════════
THE SEAM — AND THE TWO LINES THAT FINALLY WIRED IT (2026-08-11)
════════════════════════════════════════════════════════════════════════════
`apps/customers/seams.propose_payment_plan` resolves
**`apps.payments.services.propose_payment_plan`** by name. The functions are
here, in `plans.py`, because `apps/payments/services.py` belonged to another
lane the day they were written; that lane's file now re-exports both —

    from apps.payments.plans import activate_payment_plan, propose_payment_plan

— and they are declared in its `__all__`, so it is a published re-export rather
than an accident of import order.

**This paragraph used to say the opposite** ("until two import lines are added
there, the S24 wizard keeps raising `PaymentPlanUnavailable`"), and it stayed
true for exactly as long as those lines were missing. It is corrected here
because a docstring describing a state the product has left is hard-won law 1,
and the test that pins the new state is
`tests/test_us_cus_018_payment_plan.py::test_us_cus_018_tc2b` — which asserts
BOTH that the wizard now saves and that it still refuses if the name goes away.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from importlib import import_module
from typing import Any

from django.db import IntegrityError, transaction

from apps.payments.collections_models import (
    LIVE_PLAN_STATUSES,
    PLAN_ACTIVE,
    PLAN_AGREEMENT_SENT,
    PLAN_CLOSED,
    PLAN_PROPOSED,
    PaymentPlan,
    PaymentPlanInstallment,
)
from apps.payments.exceptions import PaymentRuleError
from core import audit, money
from core import tenancy as core_tenancy

ZERO = Decimal("0")


def _tenant_id() -> Any:
    from core import errors

    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


@dataclass(frozen=True)
class PlanRow:
    """What the wizard is told about the plan it just handed over."""

    id: str
    status: str
    installments: int


def validate_schedule_sums(
    *,
    total: Decimal,
    down_payment: Decimal,
    schedule: tuple[tuple[int, date, Decimal], ...],
) -> None:
    """BR-CUS-043's ONE invariant, re-checked at the point of persistence.

    US-CUS-018 TC-5 — edits totalling 240.00 against a 247.30 total — must never
    reach a row. The wizard already refuses it; this refuses it again, because
    the wizard is a screen and this is the table, and an agreement whose own
    numbers disagree is one a customer signs.
    """
    if not schedule:
        raise PaymentRuleError(
            "a payment plan needs at least one instalment (BR-CUS-043).",
            br_ref="BR-CUS-043",
        )
    seqs = [seq for seq, _, _ in schedule]
    if sorted(seqs) != list(range(1, len(schedule) + 1)):
        raise PaymentRuleError(
            f"the instalment sequence {sorted(seqs)} is not 1..{len(schedule)}. The "
            "sequence is the customer's own numbering on the agreement they signed, and "
            "a gap in it makes 'instalment 3' mean two different rows.",
            br_ref="BR-CUS-043",
        )
    scheduled = sum((amount for _, _, amount in schedule), ZERO)
    if money.finalize(scheduled + down_payment) != money.finalize(total):
        raise PaymentRuleError(
            f"the schedule does not re-sum: {len(schedule)} instalment(s) totalling "
            f"{money.finalize(scheduled)} plus a down payment of "
            f"{money.finalize(down_payment)} comes to "
            f"{money.finalize(scheduled + down_payment)}, and the balance being spread is "
            f"{money.finalize(total)} (BR-CUS-043). The plan was not saved.",
            br_ref="BR-CUS-043",
        )
    if any(amount <= ZERO for _, _, amount in schedule):
        raise PaymentRuleError(
            "every instalment must be more than 0.00 — a zero row is a date on a schedule "
            "with no payment behind it (BR-CUS-043).",
            br_ref="BR-CUS-043",
        )


def live_plan_for(account_id: Any) -> PaymentPlan | None:
    """The account's one live plan, or None (BR-CUS-043 / US-CUS-018 TC-7)."""
    return (
        PaymentPlan.objects.filter(
            tenant_id=_tenant_id(), account_id=account_id, status__in=LIVE_PLAN_STATUSES
        )
        .order_by("-created_at")
        .first()
    )


def plan_ends_on(account_id: Any) -> dict[str, Any] | None:
    """The account's live plan's LAST instalment — `{ends_on, amount,
    currency}` — or None with no live plan. READ-ONLY, one query; published
    for billing's next bill to say *the plan now ends a month later* after a
    clerk skipped an instalment (DEF-BIL-8248, PO ruling 2026-09-30, fixed-
    charge case 5). The date is this module's, never recomputed by billing."""
    plan = live_plan_for(account_id)
    if plan is None:
        return None
    last = (
        PaymentPlanInstallment.objects.filter(tenant_id=plan.tenant_id, plan=plan)
        .order_by("-due_date", "-seq")
        .values("due_date", "amount", "currency")
        .first()
    )
    if last is None:
        return None
    return {
        "ends_on": last["due_date"].isoformat(),
        "amount": str(last["amount"]),
        "currency": last["currency"],
    }


def _one_month_later(day: date) -> date:
    """The same day next month, clamped to that month's last day (Jan 31 →
    Feb 28). A calendar step, never a count of days."""
    import calendar

    year, month = (day.year + 1, 1) if day.month == 12 else (day.year, day.month + 1)
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


@transaction.atomic
def extend_plan_one_month(
    *, account_id: Any, seq: int, due_on: date, actor: Any = None
) -> dict[str, Any]:
    """🔒 PO ruling 2026-09-30 (fixed-charge case 5) — a bill-run clerk chose
    *"Skip this month"* for a payment-plan instalment, and the plan is
    EXTENDED BY ONE MONTH. PO verbatim: *"Extend the plan by one month: still
    $45 a month, 7 instalments, total unchanged"*.

    So the skipped instalment and every later UNPAID one move one calendar
    month on: the amounts do not change, the total does not change ($270 stays
    $270), the schedule's last instalment falls one month later, and no month
    ever carries two ($90). Paid instalments never move. This is the payments
    module's own write; billing reaches it through `billing/payments_seam`.

    IDEMPOTENT ON THE SKIP ITSELF: it acts only while instalment `seq` is
    still unpaid AND still due on `due_on` — the fact the bill run's Check
    recorded. Once moved it is due a month later, so a second call (a re-issue,
    a retried job) changes nothing and says so.
    """
    plan = live_plan_for(account_id)
    if plan is None:
        return {"extended": False, "reason": "no_live_plan", "ends_on": None}
    unpaid = list(
        PaymentPlanInstallment.objects.filter(
            tenant_id=plan.tenant_id, plan=plan, paid_posted_on__isnull=True, seq__gte=seq
        ).order_by("seq")
    )
    last = (
        PaymentPlanInstallment.objects.filter(tenant_id=plan.tenant_id, plan=plan)
        .order_by("-due_date", "-seq")
        .values_list("due_date", flat=True)
        .first()
    )
    if not unpaid or unpaid[0].seq != seq or unpaid[0].due_date != due_on:
        return {
            "extended": False,
            "reason": "already_extended_or_paid",
            "ends_on": last.isoformat() if last else None,
        }
    for row in unpaid:
        row.due_date = _one_month_later(row.due_date)
        row.save(update_fields=["due_date", "updated_at"])
    ends_on = max(row.due_date for row in unpaid)
    if last is not None and last > ends_on:
        ends_on = last
    audit.money_action(
        actor,
        "payment_plan.extended_one_month",
        "payment_plan",
        str(plan.pk),
        before={"ends_on": last.isoformat() if last else None, "skipped_seq": seq},
        after={"ends_on": ends_on.isoformat(), "moved": len(unpaid)},
    )
    return {"extended": True, "reason": None, "ends_on": ends_on.isoformat()}


@transaction.atomic
def propose_payment_plan(
    *,
    actor: Any = None,
    account_id: Any,
    total_amount: Decimal,
    down_payment: Decimal = ZERO,
    installments: int,
    cadence: str = "monthly",
    autopay_enabled: bool = True,
    suspend_late_fees: bool = False,
    suspend_disconnect: bool = True,
    currency: str = "USD",
    schedule: tuple[tuple[int, date, Decimal], ...],
    proposed_on: date,
) -> dict[str, Any]:
    """The S24 wizard's step 3 — **Send agreement ✓** — as ROWS.

    Called through `apps/customers/seams.propose_payment_plan`, whose published
    contract this signature is. It writes the plan, its instalments, and moves
    the plan to `agreement_sent` in the same transaction, because the seam is
    only ever reached from the "Send agreement" button: a plan row that stopped
    at `proposed` would leave the wizard reporting a state the table denies.

    **THE RETURNED `status` IS THE PRE-TRANSITION VALUE, DELIBERATELY.** The
    caller feeds it to `payment_plan.next_status_on_send`, whose whole job is to
    refuse a send from anything but `proposed` — returning `agreement_sent`
    would make the built wizard raise on its own success. `row_status` carries
    what the row actually says, so nothing here has to be inferred.

    One live plan per account is enforced by the DATABASE (partial unique
    index): two clerks on two screens is exactly the race a SELECT-then-INSERT
    loses, and the loser gives one debt two schedules.

    The down payment itself is NOT recorded here — it is a PAYMENT with purpose
    `plan_down` (BR-PAY-012) and goes through the ordinary intake path
    (US-PAY-001/002), which is the only writer of `payments`.
    """
    validate_schedule_sums(total=total_amount, down_payment=down_payment, schedule=tuple(schedule))
    if len(schedule) != installments:
        raise PaymentRuleError(
            f"the plan says {installments} instalment(s) and the schedule carries "
            f"{len(schedule)}. The count on the agreement and the rows behind it are the "
            "same fact and cannot disagree.",
            br_ref="BR-CUS-043",
        )
    tenant_id = _tenant_id()
    #: ⚠ **THE SAME BRANCH `core.audit.money_action` MAKES, AND FOR ITS REASON**
    #: (`CR-085` `CPB-21`, `OQ-CWP-1567` option (a)). An `AutomationActor` has
    #: no `.id` and no `.pk`, so `getattr` alone would resolve it to `None` and
    #: write a blank — which is the right answer here, but only by accident.
    #: It is written as an explicit fall-through so that a plan raised by a job
    #: says *nobody recorded a person* rather than borrowing one; `audit.py`'s
    #: own docstring is emphatic about not making the wrong call quiet.
    offered_by_user_id = getattr(actor, "id", None) or getattr(actor, "pk", None)
    try:
        with transaction.atomic():
            plan = PaymentPlan.objects.create(
                tenant_id=tenant_id,
                account_id=account_id,
                offered_by_id=offered_by_user_id,
                total_amount=money.finalize(total_amount),
                down_payment=money.finalize(down_payment),
                currency=currency,
                installment_count=installments,
                cadence=cadence,
                status=PLAN_PROPOSED,
                suspend_late_fees=suspend_late_fees,
                suspend_disconnect=suspend_disconnect,
                autopay_enabled=autopay_enabled,
                proposed_on=proposed_on,
            )
    except IntegrityError as clash:
        existing = live_plan_for(account_id)
        raise PaymentRuleError(
            "this account already has a live payment plan"
            + (f" ({existing.pk}, {existing.status})" if existing else "")
            + ". One live plan per account (BR-CUS-043 / A3) — a second would give the "
            "same arrears two schedules and no rule for which one the customer signed.",
            br_ref="BR-CUS-043",
        ) from clash

    PaymentPlanInstallment.objects.bulk_create(
        [
            PaymentPlanInstallment(
                tenant_id=tenant_id,
                plan=plan,
                seq=seq,
                due_date=due_date,
                amount=money.finalize(amount),
                currency=currency,
            )
            for seq, due_date, amount in schedule
        ]
    )
    plan.status = PLAN_AGREEMENT_SENT
    plan.agreement_sent_on = proposed_on
    plan.save(update_fields=["status", "agreement_sent_on", "updated_at"])

    audit.money_action(
        actor,
        "payment_plan.rows_written",
        "payment_plans",
        str(plan.pk),
        after={
            "account_id": str(account_id),
            "total_amount": str(money.finalize(total_amount)),
            "down_payment": str(money.finalize(down_payment)),
            "installments": installments,
            "currency": currency,
            "status": PLAN_AGREEMENT_SENT,
            # PO 2026-08-11 — recorded on the row's own trail so a year-old
            # audit says what the plan does NOT do.
            "current_bill_still_due": True,
            "drop_off_on_missed_installments": "none — PO 2026-08-11, nodrop",
        },
    )
    return {
        "id": str(plan.pk),
        "status": PLAN_PROPOSED,
        "row_status": PLAN_AGREEMENT_SENT,
        "installments": installments,
    }


@transaction.atomic
def activate_payment_plan(*, actor: Any = None, plan_id: Any, signed_on: date) -> dict[str, Any]:
    """The customer signed. `agreement_sent → active` (BR-CUS-044).

    **The customer's e-signature ALONE.** No countersignature is waited for and
    none exists — BR-CUS-044 supersedes A19 §3's countersign block in those
    words. US-PAY-017 TC-7: an activation attempted through the API with no
    signature event is REJECTED, and the plan stays `agreement_sent`, because a
    plan activated before signature pauses dunning on a debt nobody agreed to.
    """
    tenant_id = _tenant_id()
    plan = PaymentPlan.objects.select_for_update().get(tenant_id=tenant_id, pk=plan_id)
    if plan.status != PLAN_AGREEMENT_SENT:
        raise PaymentRuleError(
            f"a plan activates on the customer's signature from {PLAN_AGREEMENT_SENT!r}; "
            f"this plan is {plan.status!r} (BR-CUS-044). Activation is the CUSTOMER's "
            "signature and nothing else.",
            br_ref="BR-CUS-044",
        )
    plan.status = PLAN_ACTIVE
    plan.signed_on = signed_on
    plan.save(update_fields=["status", "signed_on", "updated_at"])
    audit.money_action(
        actor,
        "payment_plan.activated",
        "payment_plans",
        str(plan.pk),
        before={"status": PLAN_AGREEMENT_SENT},
        after={
            "status": PLAN_ACTIVE,
            "signed_on": signed_on.isoformat(),
            # BR-CUS-044 — the rule id stays in the comment (DEF-2377).
            "activated_by": "customer e-signature alone",
            # The scope of the pause, spelled out because believing it covers
            # everything is DEF-061, closed by the PO on 2026-08-11.
            "dunning_paused_over": "the arrears this plan spreads, while it stays current",
            "current_bill_still_due": True,
        },
    )
    return {"id": str(plan.pk), "status": PLAN_ACTIVE}


@transaction.atomic
def record_installment_payment(
    *,
    actor: Any = None,
    plan_id: Any,
    seq: int,
    payment_id: Any,
    posted_on: date,
) -> dict[str, Any]:
    """Link a payment to its instalment. On-time-ness is the POSTING date.

    BR-PAY-021, and US-PAY-017 TC-4 is the case that matters: a cheque POSTED on
    1 Oct (the due date) that CLEARS on 3 Oct is ON TIME. Nothing in this
    function reads a clearing date, and the absence is the rule.

    When the last instalment is met the plan CLOSES — the only way a plan ends
    (PO 2026-08-11, "nodrop"). Closing is idempotent: a replayed link finds the
    plan already closed and changes nothing.

    ⚠ **THIS FUNCTION HAD NO CALLER ON THE RUNNING PRODUCT UNTIL 2026-09-01, and
    that was CR-059 CS-23** — a defect, not a missing feature. The demo seeder
    and these tests called it and the ordinary payment path never did, so every
    instalment stayed unmarked: from the day after the first one fell due the
    plan read as BEHIND, BR-CUS-043's dunning pause never applied, a customer
    paying perfectly on time was chased up the collection ladder, missed-
    instalment notices went to customers who had missed nothing, and the plan
    could never close — because completion is detected right here, in the
    function nothing called. `link_payment_to_installment` below is the caller,
    and `services.record_payment` calls IT inside the payment's own transaction.

    It stays a low-level write and takes the seq it is given: it validates no
    instruction, decides no amount and asks no rule. Everything that chooses
    WHICH instalment and WHETHER the money covers it lives one level up, so the
    seeder's explicit per-seq calls keep behaving exactly as they always have.
    """
    tenant_id = _tenant_id()
    installment = PaymentPlanInstallment.objects.select_for_update().get(
        tenant_id=tenant_id, plan_id=plan_id, seq=seq
    )
    installment.paid_payment_id = payment_id
    installment.paid_posted_on = posted_on
    installment.save(update_fields=["paid_payment", "paid_posted_on", "updated_at"])

    plan = PaymentPlan.objects.select_for_update().get(tenant_id=tenant_id, pk=plan_id)
    outstanding = PaymentPlanInstallment.objects.filter(
        tenant_id=tenant_id, plan=plan, paid_posted_on__isnull=True
    ).count()
    if outstanding == 0 and plan.status != PLAN_CLOSED:
        plan.status = PLAN_CLOSED
        plan.closed_on = posted_on
        plan.save(update_fields=["status", "closed_on", "updated_at"])
        audit.money_action(
            actor,
            "payment_plan.closed",
            "payment_plans",
            str(plan.pk),
            after={"status": PLAN_CLOSED, "closed_on": posted_on.isoformat()},
        )
    return {
        "id": str(plan.pk),
        "status": plan.status,
        "installment_seq": seq,
        "on_time": posted_on <= installment.due_date,
        "outstanding_installments": outstanding,
    }


# ══════════════════════════════════════════════════════════════════════════
# CR-059 CS-23 · THE LINK THAT WAS MISSING — an ordinary payment meets its
# instalment. 🔒 money-adjacent: it decides whether a paying customer is chased.
# ══════════════════════════════════════════════════════════════════════════
#
# `record_installment_payment` above has existed since 2026-08-11 and had no
# caller but the demo seeder and its tests. CR-059 CS-23 measured what that
# cost on the running product: every instalment stayed unmarked, so from the
# day after the first one fell due the plan read as BEHIND, the BR-CUS-043
# pause never applied, missed-instalment notices went to customers who had
# missed nothing, and the plan could never close — because completion is
# detected in the very function nothing called.
#
# Everything below is the CALLER. No rule is invented here and the two that
# decide it were already ruled:
#
#   * **"plan first"** — PO 2026-08-12, OQ-139 CLOSED. An instalment payment
#     reaches the PLAN before the oldest open bill; a NAMED EXCEPTION to
#     BR-PAY-010, and it applies to instalment payments only.
#   * **`apps/customers/payment_plan.split_payment_between`** is that ruling as
#     code, with the PO's own worked figures on the frozen PE-13 plan. It takes
#     ONE instalment amount and answers how much of a payment reaches it. Both
#     of CS-23's open questions fall straight out of it and neither needed a new
#     rule — see `meets_installment` below.

#: The audit action for the link (CLAUDE.md rule 7). A code, never prose: the
#: trail is grouped on it, and this event decides whether a customer is chased.
AUDIT_INSTALLMENT_MET = "payment_plan.installment_met"

#: Outcome codes carried on `services.RecordedPayment.problems`, which travels
#: verbatim to the S22 modal (`selectors.recorded_payment_dict`). A CODE plus a
#: sentence, never prose a screen would have to parse — the same discipline as
#: `RECORD_UNAVAILABLE` and the deposit-notice outcomes.
INSTALLMENT_MET = "plan_installment_met"
INSTALLMENT_NOT_COVERED = "plan_installment_not_covered"
INSTALLMENT_ALL_MET = "plan_installments_all_met"
INSTALLMENT_PLAN_NOT_ACTIVE = "plan_not_active_no_installment_link"
INSTALLMENT_NOT_A_SCHEDULE_PAYMENT = "payment_is_not_a_schedule_payment"
INSTALLMENT_NOT_CLEARED = "not_cleared_so_no_installment_link"
INSTALLMENT_RULE_UNAVAILABLE = "plan_first_rule_unavailable"
INSTALLMENT_LINK_FAILED = "plan_installment_link_failed"

#: The customers-side rule, resolved BY NAME rather than copied — the seam
#: idiom `dunning.plan_pauses_current_bill` already uses across this same
#: boundary, and for the reason `apps/customers/payment_plan.py` states about
#: the $25 late-fee floor: *"a second copy of a ruled figure is how two figures
#: start disagreeing."*
PLAN_FIRST_MODULE = "customers"
PLAN_FIRST_RULE = "split_payment_between"


@dataclass(frozen=True)
class InstallmentLink:
    """What one payment did to the schedule — and what it did not.

    `seq is None` is the honest answer for every case that meets no instalment,
    and `problems` always says WHICH case it was. A caller must never have to
    read the absence of a number (hard-won law 1).
    """

    plan_id: str | None = None
    plan_status: str | None = None
    seq: int | None = None
    on_time: bool | None = None
    problems: tuple[dict[str, Any], ...] = ()


def meets_installment(amount: Decimal, installment_amount: Decimal) -> bool | None:
    """Does this payment cover that instalment IN FULL? `None` = unanswerable.

    **BOTH OF CR-059 CS-23's OPEN QUESTIONS ARE ANSWERED BY THE RULING THAT
    ALREADY EXISTS, and this function is where that is stated once.**

    `apps/customers/payment_plan.split_payment_between` is the PO's *"plan
    first"* ruling of 2026-08-12 (OQ-139) as code. It takes ONE instalment
    amount and returns `(to_instalment, to_current_bill)`, and its own worked
    figures on the frozen PE-13 plan settle both questions:

      * **(a) which instalment, when the amount is not an exact match.** The
        splitter meets the instalment out of whatever arrives — its worked case
        *"pays 100.00 → (36.22, 63.78)"* is not an exact match and the
        instalment is whole. So a non-matching amount still meets THE EARLIEST
        UNMET INSTALMENT (CS-23's own sentence), and requiring an exact match
        would report a customer behind on money the utility had taken.
      * **(b) what happens when one payment covers two instalments. IT MEETS
        ONE.** The splitter is given a single instalment and says of everything
        beyond it: *"THE SURPLUS IS DELIBERATELY NOT PLACED … where an
        overpayment goes is payments' rule (BR-PAY-012's credit) — not this
        module's."* So a surplus is money on the account, never a second dated
        obligation discharged early. Three reasons it must stay that way: the
        row records WHICH payment met it (`paid_payment_id`) and one payment
        cannot be two; the schedule is a set of DATED obligations, so meeting a
        future one early would make the plan read current on a day the customer
        has not reached; and a plan that closes early frees the one-live-plan
        slot (BR-CUS-043) on arrears that are still owed. A customer paying two
        instalments at once records two payments, or the clerk names the second
        one on S22.

    And the SHORT case is ruled outright — *"pays 20.00 → (20.00, 0.00) short of
    the instalment: none reaches the bill, because a part-paid instalment is
    still a missed instalment and the customer needs to know that"*. So a
    payment that does not cover the instalment meets nothing, the row stays
    unmet, and the missed notice goes as it should.

    Returns None when customers publishes no such rule. That is REPORTED by the
    caller, never substituted with a local `amount >= installment_amount` — an
    unreachable rule is not a rule, and a second copy of it is how the S24
    wizard and this table would come to disagree about the same $36.22.
    """
    try:
        module = import_module(f"apps.{PLAN_FIRST_MODULE}.payment_plan")
    except ImportError:  # pragma: no cover - customers ships in this repo
        return None
    rule = getattr(module, PLAN_FIRST_RULE, None)
    if not callable(rule):  # pragma: no cover - defensive
        return None
    to_installment, _ = rule(amount=amount, installment_amount=installment_amount)
    return money.finalize(to_installment) == money.finalize(installment_amount)


def earliest_unmet_installment(plan: PaymentPlan) -> PaymentPlanInstallment | None:
    """The instalment a payment meets by default — CR-059 CS-23, THE EARLIEST.

    Ordered by the customer's OWN numbering (`seq`), which is what the agreement
    they signed is numbered by, and NOT by due date: a schedule whose rows were
    edited in the wizard still runs 1..n, and two rows can share a due date.

    **It reads no clock and takes no `as_of`**, and that is the difference
    between this and `outstanding_installments`. That one answers *"which
    instalments has this customer MISSED by a given day"* — a question about
    lateness. This one answers *"which obligation is next"*, which is a question
    about the schedule and has the same answer on every day of the month.
    """
    return (
        PaymentPlanInstallment.objects.filter(
            tenant_id=plan.tenant_id, plan=plan, paid_posted_on__isnull=True
        )
        .order_by("seq")
        .first()
    )


def _problem(code: str, br_ref: str, detail: str) -> dict[str, Any]:
    return {"code": code, "br_ref": br_ref, "detail": detail}


def link_payment_to_installment(
    *,
    actor: Any = None,
    account_id: Any,
    amount: Decimal,
    payment_id: Any,
    posted_on: date,
    seq: int | None = None,
) -> InstallmentLink:
    """Meet this account's next instalment with this payment (CR-059 CS-23).

    **CALLED FROM INSIDE `services.record_payment`'s TRANSACTION** — the payment
    row, its allocations, its journal entry, its audit rows and this link all
    commit together or none of them does. A link written in a second transaction
    could survive a rolled-back payment and would mark an instalment met by a
    payment that does not exist.

    `posted_on` is the PAYMENT'S OWN POSTING DATE and nothing here reads a clock
    (BR-PAY-021 / BR-TEN-043). US-PAY-017 TC-4 is the case that matters: a
    cheque POSTED on 1 Oct that CLEARS on 3 Oct is ON TIME, and no clearing date
    reaches this function.

    `seq` is the clerk's choice on S22/S35 — CR-059 CS-23 puts *"the option to
    change it"* on those screens. `None` means the ruled default, the EARLIEST
    UNMET instalment. A `seq` that is not on this plan REFUSES rather than
    falling back to the earliest one: a typo must not become a silent link to a
    different instalment than the one the clerk read on the screen, and the
    refusal rolls the whole payment back with nothing written.

    **This moves NO money and writes no `allocations` row.** The payment's money
    was already placed by the allocator. What this records is which dated
    obligation of the schedule it discharged and when it POSTED — the two facts
    BR-PAY-021 and BR-CUS-043 judge a plan on.
    """
    plan = live_plan_for(account_id)
    if plan is None:
        # No plan, nothing to say. Reported as an ABSENCE would be noise on
        # every payment of every account that never agreed a schedule.
        return InstallmentLink()

    if plan.status != PLAN_ACTIVE:
        return InstallmentLink(
            plan_id=str(plan.pk),
            plan_status=plan.status,
            problems=(
                _problem(
                    INSTALLMENT_PLAN_NOT_ACTIVE,
                    "BR-CUS-044",
                    f"this account's payment plan is {plan.status!r}: a plan activates on the "
                    "CUSTOMER's e-signature and settles nothing before it (BR-CUS-044). The "
                    "payment is recorded and allocated normally; no instalment was met, "
                    "because until the customer signs there is no schedule to meet.",
                ),
            ),
        )

    if seq is None:
        installment = earliest_unmet_installment(plan)
        if installment is None:
            # DEFENSIVE, and said so rather than left to look live (law 1):
            # `record_installment_payment` CLOSES a plan the moment its last
            # instalment is met, and `live_plan_for` does not return a closed
            # plan — so an ACTIVE plan with nothing outstanding is a state the
            # normal path cannot produce. It is handled anyway because the
            # alternative is an AttributeError on a money path.
            return InstallmentLink(
                plan_id=str(plan.pk),
                plan_status=plan.status,
                problems=(
                    _problem(
                        INSTALLMENT_ALL_MET,
                        "BR-CUS-043",
                        "every instalment on this plan is already met, so this payment met "
                        "none of them. It was allocated as an ordinary payment — a plan "
                        "spreads the ARREARS and never the current month's bill "
                        "(BR-BIL-073), which is still due.",
                    ),
                ),
            )
    else:
        installment = PaymentPlanInstallment.objects.filter(
            tenant_id=plan.tenant_id, plan=plan, seq=seq
        ).first()
        if installment is None:
            # BR-CUS-043 — the sequence is the customer's OWN numbering on the
            # agreement they signed, which is why an out-of-range seq refuses
            # rather than clamping. The rule id rides `br_ref` as structured
            # data and is deliberately NOT in the sentence: G28 and B14 rule 31
            # keep an internal reference out of refusal prose, because that
            # prose reaches the audit row and the server log.
            raise PaymentRuleError(
                f"instalment {seq} is not on this account's payment plan, which runs 1.."
                f"{plan.installment_count}. Nothing was written.",
                br_ref="BR-CUS-043",
            )
        if installment.paid_posted_on is not None:
            # BR-PAY-021 — a schedule row states ONE fact about ONE payment, so
            # re-pointing a met instalment would replace the record of which
            # payment met it. The rule id rides `br_ref` and is kept out of the
            # sentence for the reason given at the refusal above.
            raise PaymentRuleError(
                f"instalment {seq} was already met by a payment posted on "
                f"{installment.paid_posted_on.isoformat()}. Name a different instalment, or "
                "leave it to the earliest unmet one. Nothing was written.",
                br_ref="BR-PAY-021",
            )

    covered = meets_installment(amount, installment.amount)
    if covered is None:  # pragma: no cover - customers ships in this repo
        return InstallmentLink(
            plan_id=str(plan.pk),
            plan_status=plan.status,
            problems=(
                _problem(
                    INSTALLMENT_RULE_UNAVAILABLE,
                    "BR-PAY-012",
                    f"apps.{PLAN_FIRST_MODULE}.payment_plan.{PLAN_FIRST_RULE} is not published, "
                    "so whether this payment covers the instalment could not be decided. It is "
                    "NOT decided here instead: the PO's 'plan first' ruling of 2026-08-12 lives "
                    "in one place, and a second copy of it would be free to disagree with the "
                    "figure the S24 wizard shows the customer. No instalment was met.",
                ),
            ),
        )
    if not covered:
        return InstallmentLink(
            plan_id=str(plan.pk),
            plan_status=plan.status,
            problems=(
                _problem(
                    INSTALLMENT_NOT_COVERED,
                    "BR-CUS-043",
                    f"{money.finalize(amount)} does not cover instalment {installment.seq}, "
                    f"which is {money.finalize(installment.amount)} due "
                    f"{installment.due_date.isoformat()}. A PART-PAID INSTALMENT IS STILL A "
                    "MISSED INSTALMENT (PO 2026-08-12) — the row stays unmet so the customer "
                    "is told, rather than shown a schedule that reads paid on money that did "
                    "not cover it. The payment itself is recorded and allocated in full.",
                ),
            ),
        )

    outcome = record_installment_payment(
        actor=actor,
        plan_id=plan.pk,
        seq=installment.seq,
        payment_id=payment_id,
        posted_on=posted_on,
    )
    # ── hard rule 7, in the same transaction as the payment ─────────────────
    # This link moves no money and it decides two things that reach a customer:
    # whether the collection ladder chases them next month, and whether their
    # plan is finished. Both belong on the trail with their own figures.
    audit.money_action(
        actor,
        AUDIT_INSTALLMENT_MET,
        "payment_plan_installments",
        str(installment.pk),
        before={"paid_payment_id": None, "paid_posted_on": None},
        after={
            "plan_id": str(plan.pk),
            "installment_seq": installment.seq,
            "amount": str(money.finalize(installment.amount)),
            "paid_by_payment_id": str(payment_id) if payment_id is not None else None,
            "payment_amount": str(money.finalize(amount)),
            "posted_on": posted_on.isoformat(),
            "due_date": installment.due_date.isoformat(),
            # BR-PAY-021 — the POSTING date decides it. The clearing date is not
            # read here and its absence is the rule.
            "on_time": outcome["on_time"],
            "judged_on": "the posting date, never the clearing date",
            "plan_status": outcome["status"],
            "outstanding_installments": outcome["outstanding_installments"],
            "selected_by": "the clerk" if seq is not None else "the earliest unmet instalment",
            "job": None if actor is not None else "payments.record",
        },
    )
    return InstallmentLink(
        plan_id=str(plan.pk),
        plan_status=outcome["status"],
        seq=installment.seq,
        on_time=outcome["on_time"],
        problems=(
            _problem(
                INSTALLMENT_MET,
                "BR-PAY-021",
                f"this payment met instalment {installment.seq} of "
                f"{plan.installment_count} ({money.finalize(installment.amount)} due "
                f"{installment.due_date.isoformat()}), posted "
                f"{posted_on.isoformat()} — "
                + ("ON TIME" if outcome["on_time"] else "LATE")
                + ". On-time-ness is the POSTING date, whatever the clearing date "
                "(BR-PAY-021). "
                + (
                    "That was the last one and the plan is now CLOSED."
                    if outcome["status"] == PLAN_CLOSED
                    else f"{outcome['outstanding_installments']} instalment(s) remain."
                ),
            ),
        ),
    )


def payment_plans_for_account(
    account_id: Any, *, as_of: date | None = None
) -> list[dict[str, Any]]:
    """Every plan this account has ever had, newest first — the S24 READ.

    Added 2026-08-16 with the S24 wizard's endpoints. The wizard could WRITE a
    plan since 2026-08-11 and nothing could ever read one back: `payment_plans`
    is payments-owned (B2 §2) and B1 forbids customers touching this ORM, so
    without a published read the account screen could not say a plan existed.
    A wizard whose result is invisible is DEF-112's shape one table along.

    **EVERY FIGURE CARRIES ITS CURRENCY AND EVERY INSTALMENT CARRIES ITS DATE**
    (CLAUDE.md rule 2): the amounts leave here as NUMERIC(18,6) TEXT, never as
    floats, and each row states the day it falls due — a schedule is a set of
    dated obligations and an amount without its date is not one.

    `as_of` is BR-TEN-043's business date and is the CALLER's. It decides only
    which instalments are reported as MISSED (`due_date < as_of` and unmet by
    its due date, BR-PAY-021); passing nothing reports no misses rather than
    reading a clock to invent some. **A missed instalment changes NOTHING about
    the plan** (PO 2026-08-11, *"nodrop we chase for payments until write
    off"*) — it is reported so a clerk can chase, and `status` stays `active`.
    A PART-PAID instalment is still a missed one (PO 2026-08-12, OQ-139).
    """
    tenant_id = _tenant_id()
    rows = (
        PaymentPlan.objects.filter(tenant_id=tenant_id, account_id=account_id)
        .select_related("offered_by")
        .prefetch_related("installments")
        .order_by("-created_at")
    )
    plans: list[dict[str, Any]] = []
    for plan in rows:
        installments = sorted(plan.installments.all(), key=lambda row: row.seq)
        paid = sum(
            (row.amount for row in installments if row.paid_posted_on is not None), Decimal("0")
        )
        missed = [
            row.seq
            for row in installments
            if as_of is not None
            and row.due_date < as_of
            and (row.paid_posted_on is None or row.paid_posted_on > row.due_date)
        ]
        plans.append(
            {
                "id": str(plan.pk),
                "status": plan.status,
                "currency": plan.currency,
                "total_amount": str(money.finalize(plan.total_amount)),
                "down_payment": str(money.finalize(plan.down_payment)),
                "spread": str(money.finalize(plan.total_amount - plan.down_payment)),
                "paid_to_date": str(money.finalize(paid)),
                "installment_count": plan.installment_count,
                "cadence": plan.cadence,
                "autopay_enabled": plan.autopay_enabled,
                "suspend_late_fees": plan.suspend_late_fees,
                "suspend_disconnect": plan.suspend_disconnect,
                "proposed_on": plan.proposed_on.isoformat() if plan.proposed_on else None,
                "agreement_sent_on": (
                    plan.agreement_sent_on.isoformat() if plan.agreement_sent_on else None
                ),
                "signed_on": plan.signed_on.isoformat() if plan.signed_on else None,
                "closed_on": plan.closed_on.isoformat() if plan.closed_on else None,
                "live": plan.status in LIVE_PLAN_STATUSES,
                # `CR-085` `CPB-21` — WHO offered it, as an id for a caller to
                # resolve. ⚠ **NO SCREEN EVER RENDERS THIS** (B14 rule 31): the
                # portal seam turns it into a name and drops it, and the staff
                # side reads a name the same way. `None` means nobody was
                # recorded — a plan older than the column, or one a job wrote.
                "offered_by_user_id": (
                    str(plan.offered_by_id) if plan.offered_by_id else None
                ),
                # ⚠ **THE NAME, RESOLVED HERE, BECAUSE THE PORTAL MAY NOT ASK.**
                # `BR-CWP-004` forbids a customer credential resolving into a
                # staff role and `G91` enforces it by reading the portal's
                # identity seam with `ast` and failing on a second model. So the
                # module that OWNS the plan resolves the person — the same
                # posture `notice_history.actor` already takes — and the portal
                # reads a word. An empty `full_name` (a user still invited,
                # `US-IDN-004`) is published as `None` rather than as "", so a
                # screen cannot print a blank where a person should be.
                "offered_by_name": (plan.offered_by.full_name or None) if plan.offered_by else None,
                # PO 2026-08-11 — carried on the ROW rather than left to a screen
                # to remember, because believing the plan replaces the bill is
                # the defect this closes (DEF-061 / BR-BIL-073).
                "current_bill_still_due": True,
                "missed_installment_seqs": missed,
                # Only meaningful when the caller named a date; `null` says
                # "nobody asked", which is a different fact from "none missed".
                "missed_as_of": as_of.isoformat() if as_of is not None else None,
                "installments": [
                    {
                        "seq": row.seq,
                        "due_date": row.due_date.isoformat(),
                        "amount": str(money.finalize(row.amount)),
                        "currency": row.currency,
                        "paid_posted_on": (
                            row.paid_posted_on.isoformat() if row.paid_posted_on else None
                        ),
                        "on_time": (
                            None
                            if row.paid_posted_on is None
                            else row.paid_posted_on <= row.due_date
                        ),
                    }
                    for row in installments
                ],
            }
        )
    return plans


def outstanding_installments(
    plan: PaymentPlan, *, as_of: date
) -> tuple[PaymentPlanInstallment, ...]:
    """Instalments DUE by `as_of` that no payment met by their due date.

    **These are FACTS, not a counter** (PO 2026-08-11, "nodrop"). Nothing
    increments, nothing is stored, and nothing transitions on the length of this
    tuple. `notices.py` reads it to decide which notice to send; the plan's
    status is not a function of it, and a test asserts that ten of these leave
    the plan ACTIVE.

    On-time-ness is `paid_posted_on ≤ due_date` (BR-PAY-021) — a payment posted
    late does not retroactively make an instalment on time, and a payment posted
    on the due date is on time however long it takes to clear.
    """
    # `__lt`, not `__lte`: an instalment due TODAY is not missed today. The
    # customer has the whole of its due date (BR-PAY-021 judges on `posted_at ≤
    # due_date`), which is also why BR-PAY-016's missed notice is day+1 and not
    # day+0. An `lte` here would put every plan "behind" on the morning of every
    # instalment and lift the dunning pause on a customer who is about to pay.
    rows = PaymentPlanInstallment.objects.filter(
        tenant_id=plan.tenant_id, plan=plan, due_date__lt=as_of
    ).order_by("seq")
    return tuple(
        row for row in rows if row.paid_posted_on is None or row.paid_posted_on > row.due_date
    )


def outstanding_installment_counts(plan_ids: Any, *, as_of: date) -> dict[Any, int]:
    """HOW MANY instalments each of these plans has missed — **one query.**

    ⛔ **THE SECOND HALF OF THE LADDER'S N+1** (`CR-138-BRC07` `P4.2`).
    `collections_pause_for` asked `outstanding_installments` per account, so a
    board of 2,046 debtors with plans on a tenth of them made a query per plan
    on top of a query per account.

    ⚠ **IT RETURNS A COUNT AND NOT THE ROWS, WHICH IS THE WHOLE POINT.**
    `outstanding_installments` returns FACTS a caller may read one by one, and
    its docstring is emphatic that nothing transitions on the length of that
    tuple. The pause decision reads exactly that length and nothing else, so
    this answers the length in SQL and the singular keeps the rows.

    **The same two rules, not a copy of them:** `due_date__lt=as_of` — an
    instalment due TODAY is not missed today (BR-PAY-021, and why BR-PAY-016's
    missed notice is day+1) — and on-time-ness is `paid_posted_on <= due_date`,
    so a payment posted late does not retroactively make an instalment on time.
    A test asserts this agrees with the singular on the same plan.
    """
    from django.db.models import Count, F, Q

    ids = [pk for pk in (plan_ids or []) if pk is not None]
    if not ids:
        return {}
    rows = (
        PaymentPlanInstallment.objects.filter(
            tenant_id=_tenant_id(), plan_id__in=ids, due_date__lt=as_of
        )
        .values("plan_id")
        .annotate(
            missed=Count(
                "id",
                filter=Q(paid_posted_on__isnull=True) | Q(paid_posted_on__gt=F("due_date")),
            )
        )
    )
    return {row["plan_id"]: row["missed"] for row in rows}


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-017@7b2ce54 (ships with apps/payments/collections_models.py — the same four sources)
# generated: 2026-08-11 by story-coder (W5 corrections + notices lane)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
#         D and E were `deferred` from 2026-08-11 to 2026-08-16 and both are now
#         TRUE: the S24 routes are mounted in apps/customers/api.py (the wizard's
#         own module owns them — the plan rows are payments' and the SCREEN is
#         customers') and `07-frontend/src/features/customers/PaymentPlanWizard.tsx`
#         draws the three steps. `payment_plans_for_account` is the read that
#         made the account screen able to say a plan exists at all.
# gates: see the lane report for the verbatim RED transcript — the one-live-plan
#         index and the re-sum refusal were each broken deliberately, RUN, and
#         the measured failure quoted before either was trusted green
# exceptions: (1) THE WIRING IS COMPLETE SINCE 2026-08-11 and the ROUTES since
#         2026-08-16 — this line used to read "THE WIRING IS ONE FILE SHORT"
#         and that stopped being true the hour `apps/payments/services.py`
#         re-exported the two write names. Corrected rather than left, because a
#         trailer describing a gap the tree has closed is hard-won law 1.
#         `payment_plans_for_account` is re-exported the same way, and it is a
#         pure READ: it writes nothing and transitions nothing.
#         (2) NO `void`, NO `defaulted`, NO `missed_count` — PO 2026-08-11.
#         `outstanding_installments` returns FACTS and changes nothing.
#         (3) THE SCHEDULE ARITHMETIC IS NOT HERE. GT-47 lives in
#         `apps/customers/payment_plan.build_schedule`; this module validates
#         the invariant and persists the rows.
#         (4) The DOWN PAYMENT is a `payments` row with purpose plan_down
#         (BR-PAY-012) and is recorded through US-PAY-001/002, the only writer
#         of that table — not from here.
#         (5) CR-059 CS-23, 2026-09-01 — `record_installment_payment` HAD NO
#         CALLER on the running product and that was a defect that undid the
#         feature: unmarked instalments, a dunning pause that never applied,
#         missed notices to customers who missed nothing, and a plan that could
#         never close. `link_payment_to_installment` is the caller and
#         `services.record_payment` calls it inside the payment's own
#         transaction. NO NEW RULE: which instalment (the earliest unmet) and
#         whether the money covers it both come out of the PO's "plan first"
#         ruling of 2026-08-12 through `apps/customers/payment_plan.
#         split_payment_between`, resolved BY NAME and never copied.
#         (6) STILL UNWIRED, and named so the silence is not read as done: a
#         REVERSED instalment payment does not unmark its instalment
#         (apps/payments/reversal.py has no plan step), and a PROCESSING payment
#         that clears later is never linked, because nothing in this product
#         links an instalment at clearing time. Both are REPORTED, neither is
#         closed here.
#         ⚠ **AND BOTH NOW HAVE A REGISTER ROW — `DEF-2403` and `DEF-2399`,
#         filed 2026-09-01.** They were named HERE and nowhere else for a day,
#         which is hard-won law 1 exactly: *a comment is a note, never a plan*,
#         and a gap that lives only in a trailer is a gap nothing will ever
#         triage. Both are `high` and both are consequences of this very fix:
#         until `record_installment_payment` had a production caller no
#         instalment was ever marked, so there was nothing for a reversal to
#         unmark and nothing for a clearing to complete. A bounced cheque now
#         leaves its instalment MET, which keeps the dunning pause on and can
#         close a plan on money that came back; a cheque that clears three days
#         after its posting date meets no instalment at all, so a customer who
#         paid on time is chased. Neither is fixed here.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
