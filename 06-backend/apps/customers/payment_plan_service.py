# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-018 (S24 payment-plan wizard — the three steps and their
#           handoffs)   Screens: S24 (entry S21; payments' S34 bulk reuses it)
# Rules:    BR-CUS-043 (schedule math; step-2 edits re-sum exactly; one live
#           plan per account) · BR-CUS-044 (agreement from the S67 template;
#           activation on the CUSTOMER's signature alone; ⚠ its `defaulted`
#           state and {missed_count} default clause SUPERSEDED — PO
#           2026-08-11) · BR-CUS-037 (customers writes NO financial table —
#           the plan rows are payments' and are reached through the seam) ·
#           BR-BIL-073 (a plan does not suspend the current bill — PO
#           2026-08-11, OQ-138) · BR-TEN-043 (event time is an argument) ·
#           CLAUDE.md rule 7 (every money action writes audit_log)
# Golden:   PE-13 → GT-47 (B5 ❄️ FROZEN): 267.30 − 50 over 6 → 5 × 36.22 + 36.20
# Tests:    06-backend/tests/test_us_cus_018_payment_plan.py
# Impacts:  apps/customers/seams.py (propose/activate → payments' service) ·
#           apps/payments (owns the rows — NOT written from here)
# ───────────────────────────────────────────────────────
"""The S24 wizard's orchestration: validate, compute, hand off, audit.

The maths and the rules are `apps/customers/payment_plan.py` and none of them is
repeated here. This module is the three steps in order:

  1 **Amount & term** — `preview` validates step 1 and returns the schedule
    step 2 renders. It writes nothing: a clerk looking at a schedule has not
    committed to one, the same reasoning `billing.runs.prepare_run` records.
  2 **Schedule** — the caller applies edits through `payment_plan.apply_edits`,
    which re-sums or refuses (BR-CUS-043).
  3 **Agreement** — `send_agreement` hands the plan to PAYMENTS' service through
    the seam and audits it; `activate` records the customer's signature.

**IT WRITES NO TABLE OF ITS OWN AND NONE OF ANOTHER MODULE'S.** `payment_plans`
and `payment_plan_installments` are payments-owned (B2 §2) and BR-CUS-037 is
explicit. While payments has not published its service the seam returns None and
this module REFUSES — it does not report a plan it did not create. That refusal
is the honest state of the product today and it is stated on the screen rather
than hidden: hard-won law 2 is about the opposite, a wizard that says "sent ✓"
over storage that does not exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from apps.customers import payment_plan, seams
from core import audit

ZERO = Decimal("0")

#: Why the wizard cannot open, when it cannot. Reasons, never a silent empty
#: form: S24 asks a clerk for a "balance to spread" and validates it against
#: what the account owes (US-CUS-018 TC-6), so a screen that opened with the
#: figure missing would invite them to type one and be refused at the end.
PLANS_UNREADABLE = "payments publishes no payment-plan read on this deployment"
BALANCE_UNREADABLE = "the ledger could not be asked what this account owes"
#: The live-plan refusal's catalogue sentence — *"This account already has a
#: plan."* — so the screen never prints server English with a rule id in it.
LIVE_PLAN_REASON_KEY = "customers.paymentPlan.alreadyHasPlan"


class PaymentPlanUnavailable(payment_plan.PaymentPlanRuleError):
    """Payments has not published the service that owns the plan rows.

    A distinct exception rather than a generic refusal, because the two mean
    different things to a clerk: "your numbers are wrong" is something they can
    fix on the screen, and "this product cannot store a plan yet" is not.
    """


@dataclass(frozen=True)
class PlanPreview:
    """What S24 step 2 renders, and what step 3 summarises."""

    schedule: payment_plan.Schedule
    cadence: str
    autopay_enabled: bool
    suspend_late_fees: bool
    suspend_disconnect: bool
    currency: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "total": str(self.schedule.total),
            "down_payment": str(self.schedule.down_payment),
            "spread": str(self.schedule.spread),
            "currency": self.currency,
            "cadence": self.cadence,
            "installment_count": self.schedule.count,
            "autopay_enabled": self.autopay_enabled,
            "suspend_late_fees": self.suspend_late_fees,
            "suspend_disconnect": self.suspend_disconnect,
            # PO ruling 2026-08-11 — put on the SUMMARY rather than left for a
            # clerk to infer, because the whole defect it closes is people
            # believing the plan replaces the bill.
            "current_bill_still_due": True,
            "installments": [
                {
                    "seq": row.seq,
                    "due_date": row.due_date.isoformat(),
                    "amount": str(row.amount),
                    "remaining": str(row.remaining),
                    "final": row.final,
                }
                for row in self.schedule.installments
            ],
        }


def wizard_context(*, account: dict[str, Any], as_of: date) -> dict[str, Any]:
    """Everything S24 needs to OPEN, including what it could not find out.

    Added 2026-08-16 with the endpoints. Three of its keys are absences with
    reasons rather than values, and each one is a defect this product has
    already had:

    * **`balance` may be `null`.** It is the LEDGER's figure (DEF-127) reached
      through `selectors`, and when the books cannot be asked it is null with
      `balance_unavailable` naming why. **The wizard must not open with 0.00 in
      the amount box** — a clerk would spread nothing, or type a figure the
      final validation then refuses against a balance nobody could read. A zero
      that means "I don't know" is the defect of this release.
    * **`plans` may be `null`.** Payments publishes the read; an unwired
      deployment answers `null` with `plans_unavailable`, which is NOT the empty
      list an account with no plan answers.
    * **`live_plan`** is the one live plan (BR-CUS-043: exactly one), or null.
      While `plans` is unreadable this is null too and `can_propose` is false —
      proposing a second plan blind is how one debt gets two schedules.

    Everything else is a rule stated as data: the three cadences S24 offers, the
    three agreement channels, the prototype's own toggle defaults, and
    `current_bill_still_due`, which the step-3 summary must print on its face
    (PO 2026-08-11, and believing otherwise IS DEF-061).
    """
    plans = seams.payment_plans_for(account["id"], as_of=as_of)
    balance = account.get("balance")
    live = None
    if plans is not None:
        live = next((row for row in plans if row["live"]), None)
    blocked: str | None = None
    blocked_key: str | None = None
    if plans is None:
        blocked = PLANS_UNREADABLE
    elif live is not None:
        # ⚠ NO RULE ID IN THIS SENTENCE (B14 rule 32). It read
        # "… (BR-CUS-043 / A3)" and the wizard printed it to a clerk verbatim.
        # The screen now reads `cannot_propose_reason_key` instead; this English
        # stays for the audit trail and API callers, without the citation.
        blocked = "this account already has a live payment plan"
        blocked_key = LIVE_PLAN_REASON_KEY
    elif balance is None:
        blocked = BALANCE_UNREADABLE
    return {
        "account_id": str(account["id"]),
        "account_no": account.get("account_no"),
        "name": account.get("name"),
        # ⚠ The figure and its CHAR(3), together or not at all (rule 2).
        "balance": balance,
        "currency": account.get("balance_currency") or account.get("currency"),
        "balance_unavailable": account.get("balance_unavailable"),
        "balance_basis": account.get("balance_basis"),
        "as_of": as_of.isoformat(),
        "plans": plans,
        "plans_unavailable": None if plans is not None else PLANS_UNREADABLE,
        "live_plan": live,
        "can_propose": blocked is None,
        "cannot_propose_reason": blocked,
        # The catalogue key a screen renders for `cannot_propose_reason`, or
        # `None` where the reason has no keyed sentence yet and the screen
        # falls back to quoting it. PO 2026-10-11 ("DEBTORS DETAIL … SHOWS THE
        # PAYMENT PLAN'S INSTALMENTS"): "This account already has a plan."
        "cannot_propose_reason_key": blocked_key,
        "cadences": list(payment_plan.CADENCES),
        "agreement_channels": list(payment_plan.AGREEMENT_CHANNELS),
        "defaults": {
            "autopay_enabled": True,
            "suspend_late_fees": False,
            "suspend_disconnect": True,
        },
        # PO 2026-08-11 (OQ-138) — on the CONTEXT as well as on every plan row,
        # so no surface can draw the wizard without the sentence available.
        "current_bill_still_due": True,
        # PO 2026-08-11 (OQ-141) — stated so a screen never offers a control for
        # a transition this product does not have.
        "plan_can_be_voided": False,
    }


def preview(
    *,
    balance_to_spread: Decimal,
    account_balance: Decimal,
    installments: int,
    cadence: str,
    first_due_date: date,
    as_of: date,
    currency: str,
    live_plan_exists: bool,
    down_payment: Decimal = ZERO,
    autopay_enabled: bool = True,
    suspend_late_fees: bool = False,
    suspend_disconnect: bool = True,
) -> PlanPreview:
    """Steps 1 → 2. Validates, then generates the schedule. **Writes nothing.**

    The three toggle DEFAULTS are the prototype's own (auto-charge ON,
    late-fee suspend OFF, disconnect suspend ON — US-CUS-018 §1), and they are
    defaults of this signature rather than values invented downstream.

    ❄️ GT-47: 267.30 with 50.00 down over 6 monthly → 5 × 36.22 + 36.20.
    """
    payment_plan.validate_proposal(
        balance_to_spread=balance_to_spread,
        account_balance=account_balance,
        installments=installments,
        cadence=cadence,
        first_due_date=first_due_date,
        as_of=as_of,
        live_plan_exists=live_plan_exists,
    )
    schedule = payment_plan.build_schedule(
        total=balance_to_spread,
        down_payment=down_payment,
        installments=installments,
        cadence=cadence,
        first_due_date=first_due_date,
    )
    return PlanPreview(
        schedule=schedule,
        cadence=cadence,
        autopay_enabled=autopay_enabled,
        suspend_late_fees=suspend_late_fees,
        suspend_disconnect=suspend_disconnect,
        currency=currency,
    )


def apply_preview_edits(*, plan: PlanPreview, edits: Any) -> PlanPreview:
    """Step 2's per-row edits, applied through `payment_plan.apply_edits`.

    The wire shape is a list of `{seq, amount?, due_date?}`. The ARITHMETIC is
    not here and is not repeated: `payment_plan.apply_edits` rebalances onto the
    final row (BR-CUS-043) or REFUSES, which is US-CUS-018 TC-3 and TC-5. This
    function only turns JSON into the two dictionaries that rule takes.

    A money amount arrives as TEXT and a float is refused, for the reason
    CLAUDE.md rule 2 gives: `float("36.22")` re-sums to something the agreement
    does not say.
    """
    if not isinstance(edits, list):
        raise payment_plan.PaymentPlanRuleError(
            "the schedule edits must be a list of rows, each naming the instalment it "
            "changes (US-CUS-018 §1 step 2)."
        )
    amounts: dict[int, Decimal] = {}
    due_dates: dict[int, date] = {}
    for row in edits:
        if not isinstance(row, dict) or not isinstance(row.get("seq"), int):
            raise payment_plan.PaymentPlanRuleError(
                "every schedule edit names the instalment number it changes; one of them "
                "does not. The sequence is the customer's own numbering on the agreement "
                "they sign (BR-CUS-043)."
            )
        seq = int(row["seq"])
        if "amount" in row and row["amount"] is not None:
            raw = row["amount"]
            if isinstance(raw, float):
                raise payment_plan.PaymentPlanRuleError(
                    f"instalment {seq}'s amount arrived as a decimal number rather than as "
                    "text. Money is NUMERIC(18,6) and never a float (CLAUDE.md rule 2) — a "
                    "float schedule re-sums to a total the agreement does not state."
                )
            try:
                amounts[seq] = Decimal(str(raw))
            except (ArithmeticError, ValueError) as bad:
                raise payment_plan.PaymentPlanRuleError(
                    f"instalment {seq}'s amount {raw!r} is not an amount."
                ) from bad
        if "due_date" in row and row["due_date"] is not None:
            try:
                due_dates[seq] = date.fromisoformat(str(row["due_date"]))
            except ValueError as bad:
                raise payment_plan.PaymentPlanRuleError(
                    f"instalment {seq}'s due date {row['due_date']!r} is not a date. Every "
                    "instalment carries the day it falls due — a schedule without dates is "
                    "not a schedule."
                ) from bad
    edited = payment_plan.apply_edits(
        schedule=plan.schedule, amounts=amounts or None, due_dates=due_dates or None
    )
    return PlanPreview(
        schedule=edited,
        cadence=plan.cadence,
        autopay_enabled=plan.autopay_enabled,
        suspend_late_fees=plan.suspend_late_fees,
        suspend_disconnect=plan.suspend_disconnect,
        currency=plan.currency,
    )


def send_agreement(
    *,
    actor: Any,
    account_id: Any,
    plan: PlanPreview,
    channels: tuple[str, ...],
    on_date: date,
) -> dict[str, Any]:
    """Step 3 — **Send agreement ✓**: `proposed → agreement_sent`.

    The plan row is PAYMENTS' (BR-CUS-037), so this validates, hands the whole
    schedule over through the seam, and audits. It refuses with
    `PaymentPlanUnavailable` when payments has published nothing — never a toast
    over a table that does not exist.

    The schedule is re-validated here even though `preview` built it: step 2's
    edits happen between the two, and BR-CUS-043's "Σ must equal the total
    exactly" is a rule about what is SENT, not about what was generated.
    """
    payment_plan.validate_agreement_channels(channels)
    payment_plan.validate_schedule(schedule=plan.schedule)

    created = seams.propose_payment_plan(
        actor=actor,
        account_id=account_id,
        total_amount=plan.schedule.total,
        down_payment=plan.schedule.down_payment,
        installments=plan.schedule.count,
        cadence=plan.cadence,
        autopay_enabled=plan.autopay_enabled,
        suspend_late_fees=plan.suspend_late_fees,
        suspend_disconnect=plan.suspend_disconnect,
        currency=plan.currency,
        schedule=tuple((row.seq, row.due_date, row.amount) for row in plan.schedule.installments),
        proposed_on=on_date,
    )
    if created is None:
        raise PaymentPlanUnavailable(
            "the payment plan cannot be saved: `payment_plans` and "
            "`payment_plan_installments` are payments-owned (B2 §2, EP-PAY-05) and "
            "`apps.payments.services.propose_payment_plan` is not published yet. The "
            "schedule above is correct and re-sums exactly — nothing was sent, nothing "
            "was recorded, and the customer has not been told a plan exists. "
            "BR-CUS-037 forbids customers writing that table itself."
        )

    status = payment_plan.next_status_on_send(
        str(created.get("status", payment_plan.PLAN_PROPOSED))
    )
    audit.money_action(
        actor,
        "payment_plan.proposed",
        "payment_plans",
        created.get("id"),
        after={
            "account_id": str(account_id),
            "total_amount": str(plan.schedule.total),
            "down_payment": str(plan.schedule.down_payment),
            "installments": plan.schedule.count,
            "cadence": plan.cadence,
            "channels": list(channels),
            "status": status,
            # PO 2026-08-11 — recorded on the money action itself so a year-old
            # trail says what the plan did NOT do.
            "current_bill_still_due": True,
        },
    )
    return {"id": created.get("id"), "status": status, "plan": plan.as_dict()}


def activate(*, actor: Any, plan_id: Any, current_status: str, signed_on: date) -> dict[str, Any]:
    """The customer signed: `agreement_sent → active` (BR-CUS-044).

    **The customer's e-signature ALONE.** No countersignature exists and none is
    waited for — BR-CUS-044 supersedes A19 §3's countersign block in those words.

    On activation, dunning and disconnect pause **over the arrears this plan
    spreads** and over nothing else: the current month's bill is still due and
    still chased (PO 2026-08-11). The audit row says so explicitly, because the
    opposite belief is the defect this closes.
    """
    status = payment_plan.next_status_on_signature(current_status)
    recorded = seams.activate_payment_plan(actor=actor, plan_id=plan_id, signed_on=signed_on)
    if recorded is None:
        raise PaymentPlanUnavailable(
            "the signature cannot be recorded: `apps.payments.services."
            "activate_payment_plan` is not published and `payment_plans` is "
            "payments-owned (BR-CUS-037). Activating in this module would pause "
            "dunning on a plan no table holds."
        )
    audit.money_action(
        actor,
        "payment_plan.activated",
        "payment_plans",
        plan_id,
        before={"status": current_status},
        after={
            "status": status,
            "signed_on": signed_on.isoformat(),
            "dunning_paused_over": "the arrears this plan spreads",
            "current_bill_still_due": True,
        },
    )
    return {"id": plan_id, "status": status}


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CUS-018@bbed56d (ships with apps/customers/payment_plan.py — the same four sources)
# generated: 2026-08-11 by story-coder (W4 payment-plan lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — S24 has no endpoint because the rows it would write are payments-owned and `payment_plans` does not exist; REPORTED) E=deferred(no-frontend-half — S24 is not built) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: MEASURED 2026-08-11, not claimed — `ruff check apps` **All checks passed!** · `black --check --line-length 100 apps tests` **402 files would be left unchanged** · `python manage.py makemigrations --check` **No changes detected** · `pytest tests -m "not golden and not isolation" -q` **1 failed, 1771 passed, 38 skipped, 127 deselected in 439.43s** — the one failure is `test_us_cus_003_tc1` (`link_customer() missing 1 required keyword-only argument: 'account_id'`), the CUSTOMER-ENTITY lane's change to apps/customers/services.py, a file this lane never opened · `pytest tests -m golden -q` **23 passed, 1913 deselected, 1 xfailed** · `pytest tests -m isolation -q` **23 passed, 80 skipped, 1834 deselected** · `10-scripts/03-golden-verify.py` **33 PASS, 0 FAIL** (unchanged baseline) · `10-scripts/gates/run_gates.py` **14 PASS/4 FAIL/1 SKIP, then 15 PASS/3 FAIL/1 SKIP on the last run** as a neighbouring lane fixed its own — the count moved between runs because three other lanes were committing throughout, which is why it is quoted as a range rather than as one number. The lane's own baseline at start was **18 PASS/0 FAIL/1 SKIP** and **every failure across every run named another lane's file**: G6 apps/payments/lockbox.py:106 (since fixed by that lane), G7 db/rls_payments_refunds.sql + rls_payments_w5.sql + apps/payments/migrations/0005+0006, G10 US-PAY-010, G15 de.json customers.account.customer.identity. **NONE named a file this lane wrote**, and the one G7 row that DID — apps/billing/migrations/0013 — was fixed here by adding its full repo-relative path to the review ledger. REPORTED rather than smoothed: this lane cannot fix payments or the i18n catalogues and did not try.
# exceptions: (1) THE PLAN IS PERSISTED SINCE 2026-08-11 — amended, because this
#         line said "THE PLAN IS NOT PERSISTED TODAY" and that stopped being true
#         the hour `apps/payments/services.py` re-exported `propose_payment_plan`
#         and `activate_payment_plan` from `apps/payments/plans.py`. It happened
#         with NO edit in this file, which is what resolving the seam BY NAME was
#         for. `payment_plans` / `payment_plan_installments` remain payments-owned
#         (B2 §2) and BR-CUS-037 still forbids customers writing them; this module
#         still writes neither. The refusal stays armed for the un-published case
#         and `tests/test_us_cus_018_payment_plan.py::test_us_cus_018_tc2b` pins
#         both halves — it saves, and it refuses when it cannot. (2) No notification is queued and no
#         DocuSign envelope is created: the agreement DOCUMENT is notifications'
#         (S67 template, BR-NOT-004 ①) and the e-sign envelope is integrations'
#         (B7) — this module records the channel ELECTION and nothing else.
#         (3) There is no `defaulted`/`void` path: PO 2026-08-11 "nodrop we
#         chase for payments until write off".
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
