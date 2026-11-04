# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-002 (payment purpose: bill · deposit · plan-down · prepay)
#           Screens: S22 · S33 · S35
# Rules:    BR-PAY-012 (the four purposes; unapplied → account credit; a deposit
#           is HELD; plan-down links to its plan) · BR-PAY-010 (a prepay meets
#           open bills in the ratified order — and with none, carries credit) ·
#           BR-CUS-043 (one live plan per account) · CLAUDE.md rule 1 · rule 2
# ───────────────────────────────────────────────────────
"""US-PAY-002's own test cases, on its own figures.

Every expected number in this file is quoted from the story beside the
assertion that uses it. PE-6's deposit is **$150.00**, PE-13's down payment is
**$50.00**, and TC-4's prepay is **$200.00** — none of them is recomputed here,
because a test that derives its own expectation agrees with a broken
implementation.

TWO GUARDS WERE DRIVEN RED BEFORE BEING TRUSTED GREEN (hard-won law 7):
`purposes.live_plan_or_refuse` (deleting the refusal lets a plan-down payment
record with no plan behind it) and the deposit exclusion in
`selectors.account_credit_position` (removing it makes a $150.00 deposit read as
$150.00 of spendable credit). Both transcripts are in the lane report.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.payments import credit, models, purposes, selectors, services
from apps.payments.collections_models import PLAN_PROPOSED, PaymentPlan
from apps.payments.exceptions import PaymentRuleError

from tests.isolation_helpers import requires_postgres
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_001_record_payment import an_issued_bill
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

#: US-PAY-002 §4, verbatim: "ACC-1350 (move-in Sep 1, 2026; plan_deposit_rules
#: Residential $150.00) … ACC-1310 plan per PE-13 (balance 267.30, down 50.00).
#: ACC-1090 prepay $200.00."
PE6_DEPOSIT = Decimal("150.00")
PE13_DOWN = Decimal("50.00")
TC4_PREPAY = Decimal("200.00")

POSTED_AT = datetime(2026, 8, 8, 10, 30, tzinfo=UTC)


def _record(actor, account, *, amount, purpose, **overrides):
    values = dict(
        account_id=account.pk,
        amount=amount,
        posted_at=POSTED_AT,
        cleared_at=POSTED_AT,
        purpose=purpose,
        idempotency_reference=uuid.uuid4(),
    )
    values.update(overrides)
    return services.record_payment(actor, **values)


def _a_proposed_plan(tenant, account):
    """PE-13's plan, in `proposed` — the state a down payment arrives against."""
    return PaymentPlan.objects.create(
        tenant=tenant,
        account=account,
        total_amount=Decimal("267.30"),
        down_payment=PE13_DOWN,
        installment_count=6,
        status=PLAN_PROPOSED,
        proposed_on=date(2026, 8, 20),
    )


def test_us_pay_002_tc1__a_deposit_is_held_and_is_not_account_credit(brazos, dana):
    """TC-1 — PE-6: a $150.00 pre-move-in deposit, no bill in existence.

    The story's expectation, verbatim: *"no allocation to any invoice; account
    credit NOT created — the money is held against the deposit line"*. Both
    halves are asserted, and the second is the one that matters: a deposit read
    as credit would be spent on the customer's first bill, and the utility owes
    it back at move-out.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11350")
        result = _record(dana, account, amount=PE6_DEPOSIT, purpose=models.PURPOSE_DEPOSIT)

        assert result.created is True
        assert result.applied == Decimal("0")
        assert result.credit_carried == Decimal("0")
        assert models.Allocation.objects.filter(payment_id=result.payment_id).count() == 0
        # The whole point: NOT credit.
        assert selectors.account_credit_position(account.pk) == Decimal("0")
        # But visible to billing, so BR-BIL-012's line can be satisfied at issue.
        assert credit.deposit_payments_for_account(account.pk) == PE6_DEPOSIT


def test_us_pay_002_tc2__the_deposit_is_published_for_billing_and_nothing_calls_it(brazos, dana):
    """TC-2 — served on THIS side of the boundary, and honest about the other.

    *"The deposit-purpose payment satisfies the deposit line at issue"* needs
    billing's issue path to draw on this figure. It does not, `apps/billing`
    belongs to another lane, and the recording says so on its own result rather
    than in a docstring nobody reads (hard-won law 1/2).
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11351")
        result = _record(dana, account, amount=PE6_DEPOSIT, purpose=models.PURPOSE_DEPOSIT)
        codes = {problem["code"] for problem in result.problems}
        assert purposes.DEPOSIT_LINE_NOT_SATISFIED in codes
        # And the requirement read that would make TC-5's refusal real.
        assert purposes.DEPOSIT_REQUIREMENT_UNCHECKED in codes
        assert purposes.deposit_requirement(account.pk) is None


def test_us_pay_002_tc3__a_plan_down_payment_links_to_its_plan(brazos, dana):
    """TC-3 — PE-13's **$50.00** down payment reaches the plan AND the arrears.

    Both are asserted because both are the rule: BR-PAY-012 says *"plan-down
    links to its plan"*, and the plan's own arithmetic (267.30 total, 50.00
    down, instalments summing to 217.30) only works if the 50.00 also reduced
    the debt. A down payment that linked but paid nothing would leave the
    customer paying 217.30 against bills still showing 267.30.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11310")
        plan = _a_proposed_plan(brazos, account)
        an_issued_bill(
            brazos,
            account,
            number="BL-2607-018400",
            total=Decimal("267.30"),
            issued_on=date(2026, 7, 1),
        )
        result = _record(dana, account, amount=PE13_DOWN, purpose=models.PURPOSE_PLAN_DOWN)

        payment = models.Payment.objects.get(pk=result.payment_id)
        assert payment.plan_id == plan.pk
        assert payment.purpose == models.PURPOSE_PLAN_DOWN
        assert result.applied == PE13_DOWN  # the arrears fell by 50.00


def test_us_pay_002_tc4__a_prepay_with_no_open_bill_carries_as_credit(brazos, dana):
    """TC-4 — **$200.00** on an account with zero open bills.

    *"Carried as account credit; auto-applies to the account's next issued
    bill"*. No special case produces this: BR-PAY-010's default oldest-first
    walk over an empty list carries the whole payment, which is why `purposes`
    gives prepay no branch of its own.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11090")
        result = _record(dana, account, amount=TC4_PREPAY, purpose=models.PURPOSE_PREPAY)

        assert result.applied == Decimal("0")
        assert result.credit_carried == TC4_PREPAY
        assert selectors.account_credit_position(account.pk) == TC4_PREPAY


def test_us_pay_002_tc5__plan_down_with_no_live_plan_is_a_named_linkage_error(brazos, dana):
    """TC-5 — *"Rejected with a named linkage error; no orphan purpose links"*.

    The refusal happens BEFORE the payment row is created, which is what makes
    "no orphan" true rather than tidy: no row, no number from the PMT- series,
    no audit entry.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11311")
        before = models.Payment.objects.count()
        with pytest.raises(PaymentRuleError) as refusal:
            _record(dana, account, amount=PE13_DOWN, purpose=models.PURPOSE_PLAN_DOWN)
        assert "no live payment plan" in str(refusal.value)
        assert refusal.value.br_ref == "BR-PAY-012"
        assert models.Payment.objects.count() == before


def test_us_pay_002_tc5b__a_fifth_purpose_does_not_exist(brazos, dana):
    """The closed set (BR-PAY-012). A typo must not become a silent `bill`."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11352")
        with pytest.raises(PaymentRuleError) as refusal:
            _record(dana, account, amount=Decimal("10.00"), purpose="donation")
        assert "not one of the payment purposes" in str(refusal.value)


def test_us_pay_002_tc3b__only_a_plan_down_payment_may_name_a_plan(brazos, dana):
    """`ck_payments_plan_only_on_plan_down` — the database's half of TC-3.

    A bill payment carrying a plan link would make "which payment was the down
    payment?" unanswerable, so the constraint refuses it. SQLite enforces CHECK
    constraints, so this one runs everywhere.
    """
    from django.db import IntegrityError, transaction

    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11353")
        plan = _a_proposed_plan(brazos, account)
        with pytest.raises(IntegrityError), transaction.atomic():
            models.Payment.objects.create(
                tenant=brazos,
                account=account,
                amount=Decimal("10.00"),
                posted_at=POSTED_AT,
                purpose=models.PURPOSE_BILL,
                plan=plan,
            )


@requires_postgres
def test_us_pay_002_tc6__isolation_a_plan_of_another_tenant_is_invisible(
    brazos, dana, lonestar, erin
):
    """TC-6 — *"Brazos Bend plan ids 404 (RLS)"*.

    The plan lookup is tenant-scoped by its queryset AND by RLS FORCE; naming
    another tenant's plan finds nothing and refuses, rather than linking a Lone
    Star Ridge payment to a Brazos Bend arrangement.
    """
    with tenant_ctx(brazos):
        brazos_account = an_account(dana, brazos, account_no="A-11354")
        brazos_plan = _a_proposed_plan(brazos, brazos_account)

    with tenant_ctx(lonestar):
        # Named from the OTHER tenant's session, the Brazos Bend plan is not
        # found — the queryset is tenant-scoped and RLS FORCE is the second,
        # independent guarantee.
        with pytest.raises(PaymentRuleError):
            purposes.live_plan_or_refuse(brazos_account.pk, plan_id=brazos_plan.pk)
