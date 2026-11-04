# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-039 TC-5 (payments and balances) · J73 S2
# Defects:  DEF-BIL-8696 (Sign off asked three questions per account) ·
#           DEF-BIL-8720 (Sign off's Amount due ignored a plan's part not yet due)
# Rules:    BR-BIL-035 · BR-BIL-1061 (PO 2026-10-01, ruling 1: $62 + $45 = $107)
#           · BR-BIL-1065 (OQ-217: the whole account since the last bill) ·
#           BR-BIL-160 (the migrated opening balance)
# ───────────────────────────────────────────────────────
"""Sign off's payments and balances, read for the whole run at once, are the
figures the per-account reads gave — and the figures the bills will print.

ONE RUN, FIVE ACCOUNTS, each a shape the balance forward has a rule for:

  * A-08601 — a payment plan: $270 owed, six $45 instalments, $62 of new
    charges, due 22 Oct → the bill asks **$107.00**, $225.00 not yet due;
  * A-08602 — overpaid: a $34.00 bill, $120.00 paid, $37.25 new → **−$48.75**;
  * A-08603 — ❄️ WE-1: one unpaid $45.00 bill, $247.87 new → **$292.87**;
  * A-08604 — nothing before: $50.00 new → **$50.00**;
  * A-08605 — ❄️ GT-16's migrated $267.30, $20.00 new → **$287.30**.

Three ways of reading the same run must agree:
  (1) the batched read (this lane's), (2) the per-account read it replaced
  (every batch switched off, so each seam is asked per account exactly as
  before), and (3) the bills — `issue._stamp_balance_forward`, the stamp Send
  writes. (1) = (2) on every figure except the one DEF-BIL-8720 moves on
  purpose, and (1) = (3) to the cent.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from apps.billing import customers_seam, issue, payments_seam, signoff
from apps.billing import models as billing_models

from tests.test_cr044_open_balance_reader import GT16_BUCKETS, GT16_CUTOVER
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_w3_billing_models import a_cycle, an_account

pytestmark = pytest.mark.django_db

UTC = timezone.utc
SEPTEMBER = (date(2026, 9, 1), date(2026, 9, 30))
DUE = date(2026, 10, 22)  # bill date 1 Oct + 21 days


def _bill(tenant, account, *, no, total, start, end, issued_at=None, run=None):
    return billing_models.Invoice.objects.create(
        tenant=tenant,
        account=account,
        bill_run=run,
        service_date=end,
        period_start=start,
        period_end=end,
        status=billing_models.INVOICE_ISSUED if issued_at else billing_models.INVOICE_DRAFT,
        currency="USD",
        subtotal=Decimal(total),
        invoice_no=no,
        issued_at=issued_at,
        tax_total=Decimal("0"),
        total=Decimal(total),
    )


def _pay(tenant, account, amount, posted_at, *, against=None, applied=None):
    from apps.payments import models as payment_models

    payment = payment_models.Payment.objects.create(
        tenant=tenant,
        account=account,
        amount=Decimal(amount),
        currency="USD",
        status=payment_models.PAYMENT_CLEARED,
        posted_at=posted_at,
    )
    if against is not None:
        payment_models.Allocation.objects.create(
            tenant=tenant, payment=payment, invoice=against, amount=Decimal(applied)
        )


def _world(brazos, dana):
    """The run and its five drafts (see the module docstring)."""
    from apps.customers import models as customer_models
    from apps.payments.collections_models import PaymentPlan, PaymentPlanInstallment

    run = billing_models.BillRun.objects.create(
        tenant=brazos,
        cycle=a_cycle(brazos),
        period_start=SEPTEMBER[0],
        period_end=SEPTEMBER[1],
        bill_date=date(2026, 10, 1),
        due_days=21,
        idempotency_key="d8696|2026-09",
    )
    august = (date(2026, 8, 1), date(2026, 8, 31))
    issued = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)
    accounts = {no: an_account(dana, brazos, account_no=no) for no in (
        "A-08601", "A-08602", "A-08603", "A-08604", "A-08605")}

    plan_account = accounts["A-08601"]
    _bill(brazos, plan_account, no="BL-08601-08", total="270.00", start=august[0], end=august[1],
          issued_at=issued)
    plan = PaymentPlan.objects.create(
        tenant=brazos, account=plan_account, total_amount=Decimal("270"), installment_count=6,
        status="active", proposed_on=date(2026, 9, 20), signed_on=date(2026, 9, 21),
    )
    for seq in range(1, 7):
        PaymentPlanInstallment.objects.create(
            tenant=brazos, plan=plan, seq=seq,
            due_date=date(2026, 9 + seq, 15) if seq <= 3 else date(2027, seq - 3, 15),
            amount=Decimal("45"),
        )
    overpaid = _bill(brazos, accounts["A-08602"], no="BL-08602-08", total="34.00",
                     start=august[0], end=august[1], issued_at=issued)
    _pay(brazos, accounts["A-08602"], "120.00", datetime(2026, 9, 5, 12, 0, tzinfo=UTC),
         against=overpaid, applied="34.00")
    _bill(brazos, accounts["A-08603"], no="BL-08603-08", total="45.00", start=august[0],
          end=august[1], issued_at=issued)
    for bucket, amount in GT16_BUCKETS:
        customer_models.AccountOpeningBucket.objects.create(
            tenant=brazos, account=accounts["A-08605"], as_of=GT16_CUTOVER, bucket=bucket,
            amount=amount, currency="USD",
        )
    news = {"A-08601": "62.00", "A-08602": "37.25", "A-08603": "247.87", "A-08604": "50.00",
            "A-08605": "20.00"}
    drafts = {
        no: _bill(brazos, accounts[no], no=None, total=total, start=SEPTEMBER[0],
                  end=SEPTEMBER[1], run=run)
        for no, total in news.items()
    }
    return run, drafts


# BULK-CHG-37 · DEF-BIL-8696
def test_the_whole_run_read_gives_each_bill_what_the_per_account_read_gave(
    brazos, dana, monkeypatch
):
    with tenant_ctx(brazos):
        run, _drafts = _world(brazos, dana)
        batched = signoff._payments_and_balances(run, signoff._bills(run))
        reads = signoff._run_reads(run, signoff._bills(run))
        # The read DEF-BIL-8682 left (2.422.3): each batch THIS lane added
        # answering None, so `_payments_and_balances` asks payments' open bills,
        # customers' opening balance, billing's prior totals and the plan split
        # per account, exactly as before.
        for name in ("open_positions_for_accounts", "plan_instalments_for_accounts"):
            monkeypatch.setattr(payments_seam, name, lambda *_a, **_k: None)
        monkeypatch.setattr(customers_seam, "opening_positions_for_accounts", lambda *_a: None)
        real = signoff._run_reads

        def per_account_reads(run, bills):
            out = real(run, bills)
            out["totals"] = None  # issue._prior_bill_totals, per bill
            return out

        monkeypatch.setattr(signoff, "_run_reads", per_account_reads)
        one_by_one = signoff._payments_and_balances(run, signoff._bills(run))
    print(f"\nPROOF batched {batched['amount_due']} · per account {one_by_one['amount_due']}")
    assert reads["open"] is not None and reads["opening"] is not None and reads["totals"] is not None
    assert batched == one_by_one
    assert Decimal(batched["amount_due"]) == Decimal("688.42")


# BULK-CHG-37 · DEF-BIL-8696 · DEF-BIL-8720
def test_sign_off_reads_what_the_bills_will_print_to_the_cent(brazos, dana):
    with tenant_ctx(brazos):
        run, drafts = _world(brazos, dana)
        money = signoff._payments_and_balances(run, signoff._bills(run))
        blocks = {
            no: issue._stamp_balance_forward(bill, currency="USD", due_date=DUE)
            for no, bill in drafts.items()
        }
    due = {no: Decimal(block["total_due"]) for no, block in blocks.items()}
    print(f"\nPROOF bills {due} · Sign off {money['amount_due']}")
    assert due == {
        "A-08601": Decimal("107"),
        "A-08602": Decimal("-48.75"),
        "A-08603": Decimal("292.87"),
        "A-08604": Decimal("50"),
        "A-08605": Decimal("287.30"),
    }
    assert Decimal(money["amount_due"]) == sum(due.values()) == Decimal("688.42")
    assert Decimal(money["plan_not_yet_due"]) == Decimal(blocks["A-08601"]["plan_not_yet_due"])
    assert Decimal(money["plan_not_yet_due"]) == Decimal("225")
    assert Decimal(money["previous_balance"]) == sum(
        Decimal(block["previous_balance"]) for block in blocks.values()
    )
    assert Decimal(money["payments_and_credits_applied"]) == sum(
        Decimal(block["payments_credits"]) for block in blocks.values()
    )
    assert money["reconciles"] is True
    # How it is paid adds back to the amount due, and the credit covers the
    # overpaid account's bill.
    assert sum(Decimal(v["amount"]) for v in money["how_paid"].values()) == Decimal("688.42")
    assert money["how_paid"]["credit_covers"]["bills"] == 1


# DEF-BIL-8720 — a clerk's *Skip this month* leaves this month's $45 not yet due too
def test_skip_this_month_holds_back_the_instalment_on_sign_off_as_on_the_bill(
    brazos, dana, monkeypatch
):
    from apps.billing import decisions

    with tenant_ctx(brazos):
        run, drafts = _world(brazos, dana)
        decisions.record_decision(
            bill_run=run, account_id=drafts["A-08601"].account_id, case="plan_instalment_due",
            choice=decisions.CHOICE_SKIP,
        )
        money = signoff._payments_and_balances(run, signoff._bills(run))
        block = issue._stamp_balance_forward(drafts["A-08601"], currency="USD", due_date=DUE)
    # 270 owed: $225 + $45 not yet due, so the bill asks the new $62 alone.
    assert Decimal(block["total_due"]) == Decimal("62")
    assert Decimal(money["plan_not_yet_due"]) == Decimal("270")


def test_the_plan_arithmetic_is_the_bills_own():
    from apps.billing import open_balance

    split = {"due_now": Decimal("45"), "not_yet_due": Decimal("225")}
    assert open_balance.plan_not_yet_due(split, skipped=False, stands=Decimal("270")) == {
        "not_yet_due": Decimal("225"), "due_now": Decimal("45")}
    # capped at what the account owes from before this bill
    assert open_balance.plan_not_yet_due(split, skipped=False, stands=Decimal("100"))[
        "not_yet_due"] == Decimal("100")
    assert open_balance.plan_not_yet_due(split, skipped=False, stands=Decimal("-5")) is None
    assert open_balance.plan_not_yet_due(None, skipped=False, stands=Decimal("270")) is None
