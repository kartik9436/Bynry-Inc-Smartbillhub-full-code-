# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-018 (S24 payment-plan wizard)   Screens: S24
# Rules:    BR-CUS-043 (schedule math; edits re-sum exactly; one live plan per
#           account) · BR-CUS-044 (activation on the CUSTOMER's signature
#           alone; ⚠ its `defaulted` state and {missed_count} default clause
#           SUPERSEDED — PO 2026-08-11) · BR-CUS-037 (customers writes no
#           financial table) · BR-BIL-073 (a plan does not suspend the current
#           bill — PO 2026-08-11, OQ-138) · BR-BIL-001 as amended 2026-08-11
#           (the $25.00 floor, REUSED from billing) · CLAUDE.md rule 7 (audit)
# ───────────────────────────────────────────────────────
"""US-CUS-018 §3 — and the second live defect the PO closed on 2026-08-11.

`tc1b` is the one to read first: a customer on the frozen PE-13 plan owes
**$220.42** in October — the $36.22 instalment AND October's $184.20 bill — and
the current bill is chased like anybody else's. Before the ruling, the dunning
pause a plan grants was read as covering the whole account, so a customer on a
plan could stop paying current bills for six months unchased.

`tc9` is the other ruling: nobody is dropped off a plan.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.customers import payment_plan, payment_plan_service, seams

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_bil_025_026_bills_read import an_account

pytestmark = pytest.mark.django_db

# ❄️ PE-13 / GT-47 verbatim.
PE13_BALANCE = Decimal("267.30")
PE13_DOWN = Decimal("50")
PE13_INSTALLMENT = Decimal("36.22")
PE13_FINAL = Decimal("36.20")

# OQ-138's own worked October (PO ruling 2026-08-11).
OCTOBER_BILL = Decimal("184.20")
OCTOBER_DUE = Decimal("220.42")

# The prototype's S24 fixture (US-CUS-018 §4) — NOT a B5 figure.
PROTO_BALANCE = Decimal("247.30")
TODAY = date(2026, 8, 25)
FIRST_DUE = date(2026, 9, 1)


def a_preview(**overrides):
    kwargs = dict(
        balance_to_spread=PROTO_BALANCE,
        account_balance=PROTO_BALANCE,
        installments=4,
        cadence=payment_plan.CADENCE_MONTHLY,
        first_due_date=FIRST_DUE,
        as_of=TODAY,
        currency="USD",
        live_plan_exists=False,
    )
    kwargs.update(overrides)
    return payment_plan_service.preview(**kwargs)


def test_us_cus_018_tc1__the_schedule_matches_the_prototype_to_the_cent(brazos, marcus):
    """A-10432's $247.30 over 4 monthly from Sep 1 → 61.83 / 61.83 / 61.83 /
    61.81, remaining 185.47 / 123.64 / 61.81 / 0.00 (S24 step 2)."""
    plan = a_preview()
    rows = plan.schedule.installments
    assert tuple(r.amount for r in rows) == (
        Decimal("61.83"),
        Decimal("61.83"),
        Decimal("61.83"),
        Decimal("61.81"),
    )
    assert tuple(r.remaining for r in rows) == (
        Decimal("185.47"),
        Decimal("123.64"),
        Decimal("61.81"),
        Decimal("0.00"),
    )
    assert rows[-1].final is True

    # The step-3 summary states the ruling on its face rather than leaving a
    # clerk to infer it — the whole defect is people believing otherwise.
    assert plan.as_dict()["current_bill_still_due"] is True


def test_us_cus_018_tc1b__a_plan_does_not_suspend_the_current_bill(brazos, marcus):
    """**THE LIVE DEFECT (DEF-061), closed.** PO 2026-08-11, verbatim: *"no
    there is monthly charges that thye have to pay nad it is due every month"*.

    ❄️ PE-13's instalment is **36.22**; October's ordinary cycle bill is
    **184.20**; the customer owes **220.42** in October — not 36.22, which is
    what a product that treats the plan as satisfying the account asks for.

    The rejected reading is asserted alongside the rule, in figures, so the
    defect is visible rather than described.
    """
    assert (
        payment_plan.amount_due_this_month(
            installment_amount=PE13_INSTALLMENT, current_bill_amount=OCTOBER_BILL
        )
        == OCTOBER_DUE
    )
    assert OCTOBER_DUE != PE13_INSTALLMENT  # what the product used to ask for
    assert OCTOBER_DUE != OCTOBER_BILL  # …and the other half-answer

    # And the pause is over the ARREARS, never over the current bill.
    assert payment_plan.plan_pauses_current_bill() is False


def test_us_cus_018_tc1c__the_current_bills_late_fee_is_billings_and_is_not_restated(
    brazos, marcus
):
    """BR-BIL-001 as amended 2026-08-11 — the $25.00 floor lives in
    `apps/billing/late_fee.py` and is reached, never copied.

    A plan's `suspend_late_fees` election covers the arrears it spreads; the
    current bill's fee is billing's own calculation, unchanged. Asserted through
    the SEAM, so the day it is unwired the test says so rather than passing on a
    number this module invented.
    """
    fee = seams.assess_late_fee(
        overdue_amount=OCTOBER_BILL,
        percent=Decimal("0.015"),
        minimum=Decimal("5"),
        due_date=date(2026, 10, 22),
        as_of=date(2026, 11, 5),
        grace_days=5,
        grace_mode="calendar",
    )
    # max($5, 1.5% × 184.20) = max(5, 2.763) = 5.00, and 184.20 is over the
    # $25.00 balance floor so the threshold does not suppress it.
    assert fee == Decimal("5.00")

    # The threshold itself is NOT a number this module knows: it is billing's,
    # and this is the proof the seam reaches the same one.
    from apps.billing import late_fee

    assert seams.assess_late_fee(
        overdue_amount=Decimal("2.40"),
        percent=Decimal("0.015"),
        minimum=Decimal("5"),
        due_date=date(2026, 10, 22),
        as_of=date(2026, 11, 5),
        grace_days=5,
        grace_mode="calendar",
    ) == Decimal("0.00")
    assert late_fee.LATE_FEE_BALANCE_FLOOR == Decimal("25.00")


def test_us_cus_018_tc3__a_step_two_edit_rebalances_onto_the_final_row(brazos, marcus):
    """Instalment 1 raised to $100.00 — the remaining column recomputes and the
    final row absorbs the difference, so Σ is still 247.30 exactly."""
    plan = a_preview()
    edited = payment_plan.apply_edits(schedule=plan.schedule, amounts={1: Decimal("100.00")})
    amounts = tuple(r.amount for r in edited.installments)
    assert amounts[0] == Decimal("100.00")
    assert sum(amounts, Decimal("0")) == PROTO_BALANCE
    assert edited.installments[-1].remaining == Decimal("0.00")


def test_us_cus_018_tc4__a_down_payment_divides_the_remainder_exactly(brazos, marcus):
    """$47.30 down over 4 → 4 × $50.00 exactly (US-CUS-018 TC-4)."""
    plan = a_preview(down_payment=Decimal("47.30"))
    assert tuple(r.amount for r in plan.schedule.installments) == (Decimal("50.00"),) * 4
    assert plan.schedule.spread == Decimal("200.00")


def test_us_cus_018_tc5__a_schedule_that_does_not_re_sum_is_blocked(brazos, marcus):
    """Edits summing to 240.00 against a 247.30 total block Continue, and
    nothing is sent (BR-CUS-043)."""
    plan = a_preview()
    short = payment_plan.Schedule(
        total=PROTO_BALANCE,
        down_payment=Decimal("0"),
        spread=PROTO_BALANCE,
        installments=tuple(
            payment_plan.Installment(
                seq=i, due_date=FIRST_DUE, amount=Decimal("60.00"), remaining=Decimal("0")
            )
            for i in range(1, 5)
        ),
    )
    with pytest.raises(payment_plan.PaymentPlanRuleError, match="must equal the total"):
        payment_plan.validate_schedule(schedule=short)

    # …and the wizard's own send path re-checks it rather than trusting what
    # `preview` built, because step 2's edits happen between the two.
    plan = payment_plan_service.PlanPreview(
        schedule=short,
        cadence=plan.cadence,
        autopay_enabled=True,
        suspend_late_fees=False,
        suspend_disconnect=True,
        currency="USD",
    )
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus)
        with pytest.raises(payment_plan.PaymentPlanRuleError, match="must equal the total"):
            payment_plan_service.send_agreement(
                actor=marcus,
                account_id=account.id,
                plan=plan,
                channels=(payment_plan.CHANNEL_EMAIL,),
                on_date=TODAY,
            )


def test_us_cus_018_tc6__zero_installments_and_an_over_balance_spread_are_refused(brazos, marcus):
    """US-CUS-018 TC-6's inline errors, and the first-date rule beside them."""
    with pytest.raises(payment_plan.PaymentPlanRuleError, match="at least one instalment"):
        a_preview(installments=0)
    with pytest.raises(payment_plan.PaymentPlanRuleError, match="more than the account owes"):
        a_preview(balance_to_spread=Decimal("500.00"))
    with pytest.raises(payment_plan.PaymentPlanRuleError, match="not after"):
        a_preview(first_due_date=TODAY)


def test_us_cus_018_tc7__a_second_live_plan_is_blocked(brazos, marcus):
    """A3 as enforced: exactly one live plan per account (proposed,
    agreement_sent and active all count as live)."""
    with pytest.raises(payment_plan.PaymentPlanRuleError, match="already has a live payment plan"):
        a_preview(live_plan_exists=True)
    assert payment_plan.LIVE_PLAN_STATUSES == (
        payment_plan.PLAN_PROPOSED,
        payment_plan.PLAN_AGREEMENT_SENT,
        payment_plan.PLAN_ACTIVE,
    )


def test_us_cus_018_tc2__the_plan_activates_on_the_customers_signature_alone(
    brazos, marcus, audit_rows, monkeypatch
):
    """`proposed → agreement_sent → active`, and the audit row states what the
    activation does NOT do.

    BR-CUS-044: the CUSTOMER's e-signature alone — no countersignature exists.
    Payments' service is published here by name, which is exactly the state a
    deployment is in the day that lane lands.
    """
    from apps.payments import services as payments_services

    monkeypatch.setattr(
        payments_services,
        "propose_payment_plan",
        lambda **kw: {"id": "plan-1", "status": payment_plan.PLAN_PROPOSED},
        raising=False,
    )
    monkeypatch.setattr(
        payments_services,
        "activate_payment_plan",
        lambda **kw: {"id": "plan-1", "status": payment_plan.PLAN_ACTIVE},
        raising=False,
    )

    with tenant_ctx(brazos):
        account = an_account(brazos, marcus)
        plan = a_preview()
        sent = payment_plan_service.send_agreement(
            actor=marcus,
            account_id=account.id,
            plan=plan,
            channels=(payment_plan.CHANNEL_EMAIL,),
            on_date=TODAY,
        )
        assert sent["status"] == payment_plan.PLAN_AGREEMENT_SENT

        activated = payment_plan_service.activate(
            actor=marcus,
            plan_id=sent["id"],
            current_status=sent["status"],
            signed_on=date(2026, 8, 26),
        )
        assert activated["status"] == payment_plan.PLAN_ACTIVE

    proposed = [r for r in audit_rows if r["action"] == "payment_plan.proposed"][-1]
    assert proposed["after"]["current_bill_still_due"] is True
    activated_row = [r for r in audit_rows if r["action"] == "payment_plan.activated"][-1]
    assert activated_row["after"]["dunning_paused_over"] == "the arrears this plan spreads"
    assert activated_row["after"]["current_bill_still_due"] is True

    # A plan cannot activate before its agreement was sent.
    with pytest.raises(payment_plan.PaymentPlanRuleError, match="activates on signature"):
        payment_plan.next_status_on_signature(payment_plan.PLAN_PROPOSED)


def test_us_cus_018_tc2b__the_wizard_saves_through_payments_and_still_refuses_to_fake_one(
    brazos, marcus, monkeypatch
):
    """**REWRITTEN 2026-08-11 — the claim this test used to make became false.**

    It read *"payments publishes no service yet, so Send REFUSES"*, and asserted
    the refusal. That was the honest state for as long as `apps/payments/
    services.py` — the module's published write surface (B1) — did not import
    `plans.propose_payment_plan`. It now does, so the refusal no longer fires and
    the docstring was describing a product that had moved. Hard-won law 1 applied
    to the change that falsified it: the claim is rewritten, not the assertion
    deleted.

    The GUARANTEE the test was written for is unchanged and is still asserted
    below — a "sent ✓" toast may never appear over a plan that no row holds. What
    changed is which branch delivers it. Both halves are pinned here:

      1. **It saves.** No monkeypatch, no stub: the seam resolves the real
         payments service by name and a `payment_plans` row with its instalments
         exists afterwards.
      2. **It still refuses when it cannot save.** Take the published name away —
         the state this repo was in an hour ago, and the state any un-landed lane
         is in — and the wizard raises `PaymentPlanUnavailable` naming the table,
         writing nothing.
    """
    from apps.payments import services as payments_services
    from apps.payments.collections_models import PaymentPlan, PaymentPlanInstallment

    # 1 — BUILT *AND* WIRED. The seam resolves by name; this asserts the name is
    # actually there rather than trusting the import that put it there.
    assert seams.resolve("payments", "propose_payment_plan") is not None
    assert seams.resolve("payments", "activate_payment_plan") is not None

    with tenant_ctx(brazos):
        account = an_account(brazos, marcus)
        plan = a_preview()
        sent = payment_plan_service.send_agreement(
            actor=marcus,
            account_id=account.id,
            plan=plan,
            channels=(payment_plan.CHANNEL_EMAIL,),
            on_date=TODAY,
        )
        assert sent["status"] == payment_plan.PLAN_AGREEMENT_SENT

        row = PaymentPlan.objects.get(tenant_id=brazos.id, pk=sent["id"])
        assert str(row.account_id) == str(account.id)
        assert row.total_amount == PROTO_BALANCE
        # The four instalments the wizard computed, in the table, to the cent.
        stored = list(
            PaymentPlanInstallment.objects.filter(tenant_id=brazos.id, plan=row)
            .order_by("seq")
            .values_list("amount", flat=True)
        )
        assert stored == [
            Decimal("61.83"),
            Decimal("61.83"),
            Decimal("61.83"),
            Decimal("61.81"),
        ]

    # 2 — the refusal is still armed. Remove the published name and the wizard
    # says so rather than reporting a plan it did not create.
    monkeypatch.delattr(payments_services, "propose_payment_plan")
    with tenant_ctx(brazos):
        other = an_account(brazos, marcus, account_no="A-10433", label="Unit B")
        before = PaymentPlan.objects.filter(tenant_id=brazos.id).count()
        with pytest.raises(payment_plan_service.PaymentPlanUnavailable, match="payment_plans"):
            payment_plan_service.send_agreement(
                actor=marcus,
                account_id=other.id,
                plan=a_preview(),
                channels=(payment_plan.CHANNEL_EMAIL,),
                on_date=TODAY,
            )
        assert PaymentPlan.objects.filter(tenant_id=brazos.id).count() == before


def test_us_cus_018_tc9__nobody_is_dropped_off_a_payment_plan(brazos, marcus):
    """**PO ruling 2026-08-11, verbatim: "nodrop we chase for payments until
    write off".**

    BR-CUS-044's template default clause ("plan voids on {missed_count} missed
    → full balance due; fees resume"), its PROPOSED `defaulted` state and
    BR-PAY-016's "2nd miss VOIDS plan" are all SUPERSEDED. J13 step 6 — the
    journey's own 2nd-miss VOID — no longer describes this product.

    The tenth miss leaves the plan exactly where the first did, and there is no
    `defaulted` or `void` state to reach.
    """
    for miss in range(1, 11):
        assert payment_plan.record_missed_instalment(missed_count=miss) == (
            payment_plan.PLAN_ACTIVE
        )

    assert "defaulted" not in payment_plan.PLAN_STATUSES
    assert "void" not in payment_plan.PLAN_STATUSES
    assert payment_plan.PLAN_STATUSES == ("proposed", "agreement_sent", "active", "closed")
    assert not hasattr(payment_plan, "MISSED_COUNT_DEFAULT")


def test_us_cus_018_tc10__a_payment_meets_the_plan_instalment_first(brazos, marcus):
    """**PO ruling 2026-08-12, verbatim: _"plan first"_ — OQ-139 CLOSED.**

    This test used to assert the REFUSAL, and its docstring said why the answer
    could not be guessed: on the worked October a customer sending exactly
    $184.20 plainly means this month, while BR-PAY-010's default sends it onto
    the arrears the plan already covers. That fork is now decided.

    **The exception matters more than the order.** Under plain oldest-first, a
    customer paying exactly what they agreed has it spent on the debt the plan is
    already spreading — so they fall behind on the current month and get chased
    for money they just sent. That is what "plan first" prevents.
    """
    # ❄️ PE-13's instalment 36.22 · October's bill 184.20 · both due = 220.42.
    assert payment_plan.split_payment_between(
        amount=OCTOBER_DUE,
        installment_amount=PE13_INSTALLMENT,
        current_bill_amount=OCTOBER_BILL,
    ) == (PE13_INSTALLMENT, OCTOBER_BILL)

    # The case the ruling was written for: a payment the size of the BILL does
    # not go to the bill. The instalment is met first, and the rest follows.
    assert payment_plan.split_payment_between(
        amount=OCTOBER_BILL,
        installment_amount=PE13_INSTALLMENT,
        current_bill_amount=OCTOBER_BILL,
    ) == (PE13_INSTALLMENT, OCTOBER_BILL - PE13_INSTALLMENT)

    # Short of the instalment: NOTHING reaches the bill. A part-paid instalment
    # is still a missed instalment, and the customer must not be told otherwise.
    assert payment_plan.split_payment_between(
        amount=Decimal("20.00"),
        installment_amount=PE13_INSTALLMENT,
        current_bill_amount=OCTOBER_BILL,
    ) == (Decimal("20.00"), Decimal("0.00"))

    # A surplus is NOT allocated here — where an overpayment goes is payments'
    # rule (BR-PAY-012), and reporting it as allocated would be a claim.
    to_plan, to_bill = payment_plan.split_payment_between(
        amount=Decimal("300.00"),
        installment_amount=PE13_INSTALLMENT,
        current_bill_amount=OCTOBER_BILL,
    )
    assert (to_plan, to_bill) == (PE13_INSTALLMENT, OCTOBER_BILL)
    assert Decimal("300.00") - to_plan - to_bill == Decimal("79.58")

    # Money never comes back OUT through this door.
    with pytest.raises(payment_plan.PaymentPlanRuleError, match="negative"):
        payment_plan.split_payment_between(
            amount=Decimal("-1.00"), installment_amount=PE13_INSTALLMENT
        )


@pytest.mark.isolation
def test_us_cus_018_tc8__the_wizard_is_tenant_scoped(brazos, marcus, lonestar, erin):
    """J. Okafor cannot open S24 for a Brazos Bend account id (RLS / HR-1).

    The wizard reaches the account through customers' own tenant-scoped read,
    which raises the 404-never-403 refusal for a cross-tenant id rather than
    letting the plan be proposed against somebody else's arrears.
    """
    from apps.customers import selectors as customer_selectors
    from core import errors

    with tenant_ctx(brazos):
        brazos_account = an_account(brazos, marcus, account_no="A-10432")

    with tenant_ctx(lonestar):
        with pytest.raises(errors.NotFoundError):
            customer_selectors.account_or_404(brazos_account.id)


def test_the_live_plan_refusal_carries_a_catalogue_key_and_no_rule_id(monkeypatch):
    """PO 2026-10-11 ("DEBTORS DETAIL … SHOWS THE PAYMENT PLAN'S INSTALMENTS")
    — the wizard printed *"… a live payment plan (BR-CUS-043 / A3)"* to a
    clerk. The refusal now names its catalogue sentence (*"This account
    already has a plan."*) and no rule id reaches the wire's English either
    (B14 rule 32). The other reasons have no key and say so with `None`.
    """
    live = {"id": "p-1", "live": True}
    monkeypatch.setattr(seams, "payment_plans_for", lambda account_id, as_of: [live])
    account = {"id": "a-1", "balance": "100.00", "currency": "USD"}
    context = payment_plan_service.wizard_context(account=account, as_of=date(2026, 10, 11))
    assert context["can_propose"] is False
    assert context["cannot_propose_reason_key"] == "customers.paymentPlan.alreadyHasPlan"
    assert "BR-" not in context["cannot_propose_reason"]

    monkeypatch.setattr(seams, "payment_plans_for", lambda account_id, as_of: [])
    clear = payment_plan_service.wizard_context(account=account, as_of=date(2026, 10, 11))
    assert clear["can_propose"] is True
    assert clear["cannot_propose_reason_key"] is None
    unread = payment_plan_service.wizard_context(
        account={**account, "balance": None}, as_of=date(2026, 10, 11)
    )
    assert unread["cannot_propose_reason_key"] is None
    assert "ledger" in unread["cannot_propose_reason"]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CUS-018@bbed56d (05-golden-tests.md + EP-CUS-06-payment-plan.md + 03-customers/02-business-rules.md + J13-payment-plan-life.md)
# generated: 2026-08-11 by story-coder (W4 payment-plan lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — S24 has no endpoint because the rows are payments-owned and unbuilt; REPORTED) E=deferred(no-frontend-half — S24 is not built) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: MEASURED 2026-08-11, not claimed — `ruff check apps` **All checks passed!** · `black --check --line-length 100 apps tests` **402 files would be left unchanged** · `python manage.py makemigrations --check` **No changes detected** · `pytest tests -m "not golden and not isolation" -q` **1 failed, 1771 passed, 38 skipped, 127 deselected in 439.43s** — the one failure is `test_us_cus_003_tc1` (`link_customer() missing 1 required keyword-only argument: 'account_id'`), the CUSTOMER-ENTITY lane's change to apps/customers/services.py, a file this lane never opened · `pytest tests -m golden -q` **23 passed, 1913 deselected, 1 xfailed** · `pytest tests -m isolation -q` **23 passed, 80 skipped, 1834 deselected** · `10-scripts/03-golden-verify.py` **33 PASS, 0 FAIL** (unchanged baseline) · `10-scripts/gates/run_gates.py` **14 PASS/4 FAIL/1 SKIP, then 15 PASS/3 FAIL/1 SKIP on the last run** as a neighbouring lane fixed its own — the count moved between runs because three other lanes were committing throughout, which is why it is quoted as a range rather than as one number. The lane's own baseline at start was **18 PASS/0 FAIL/1 SKIP** and **every failure across every run named another lane's file**: G6 apps/payments/lockbox.py:106 (since fixed by that lane), G7 db/rls_payments_refunds.sql + rls_payments_w5.sql + apps/payments/migrations/0005+0006, G10 US-PAY-010, G15 de.json customers.account.customer.identity. **NONE named a file this lane wrote**, and the one G7 row that DID — apps/billing/migrations/0013 — was fixed here by adding its full repo-relative path to the review ledger. REPORTED rather than smoothed: this lane cannot fix payments or the i18n catalogues and did not try.
# exceptions: (1) `tc2` publishes payments' two service functions with
#         monkeypatch — the seam resolves BY NAME at call time, so this is
#         exactly the deployment state the day that lane lands, and `tc2b`
#         asserts the UNPATCHED refusal so the absence is covered too.
#         (2) J13 step 6's "2nd miss → plan VOIDS" is SUPERSEDED and `tc9`
#         asserts the replacement; the journey file lives under 08-qa/ and is
#         another lane's to stamp — REPORTED.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
