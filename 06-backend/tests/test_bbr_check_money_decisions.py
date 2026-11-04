# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-037 TC-10 (bulk run · Check — Payments & balances decisions)
# Rules:    BR-BIL-1053 (paid after cut-off: apply to this bill / next bill;
#           plan instalment due: add to bill / skip) · BR-BIL-035 (the balance
#           forward: previous balance − payments received + this period) ·
#           CLAUDE.md hard rules 4, 5 and 7
# Plan:     16-check-decisions-next-bill.md §3 (*"Payments are booked once in
#           the ledger; 'apply to this bill' is tested for double counting"*)
# Defects:  DEF-BIL-8243 (a decision whose money step is not built holds the
#           account) · DEF-BIL-8412 (apply NEXT bill — the bulk lane's; not
#           touched here, the two choices stay distinct)
# ───────────────────────────────────────────────────────
"""The two money answers at the Check that used to HOLD the account.

* **Add to bill** (plan instalment due): the account is BILLED and the due
  instalment is printed on the bill as its own line — never a charge, because
  it is a slice of arrears already on earlier bills and already in the balance
  forward. Worked: $270 on a plan of $45 × 6; instalment 2 of $45.00 due
  15 Sep → *"Instalment 2: 45.00 USD due 2026-09-15."*; the bill's total is its
  own charges.
* **Apply to this bill** (paid after cut-off): the $120.00 posted 1 Oct is on
  September's bill once, as *payments received*, and October's bill carries
  the debt it reduced — $80.00 of August, not $200.00 — so across two months it
  is counted exactly once.

`BULK-CHG-38` is changes row 38. Run on PostgreSQL too (`--ds=config.settings.pgtest`).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from apps.billing import decisions, runs
from apps.billing.exceptions import BillingRuleError
from apps.billing import models as billing_models

from tests.test_bbr_fixed_charge_next_bill import AUGUST, OCTOBER, SEPTEMBER, _setup
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_met_reads_helpers import commit_read

pytestmark = pytest.mark.django_db


def a_plan(tenant, account):
    """$270 on $45 × 6; August's instalment paid, September's (seq 2) due."""
    from apps.payments.collections_models import PaymentPlan, PaymentPlanInstallment

    plan = PaymentPlan.objects.create(
        tenant=tenant,
        account=account,
        total_amount=Decimal("270"),
        installment_count=6,
        status="active",
        proposed_on=date(2026, 8, 1),
        signed_on=date(2026, 8, 2),
    )
    for seq in range(1, 7):
        PaymentPlanInstallment.objects.create(
            tenant=tenant,
            plan=plan,
            seq=seq,
            due_date=date(2026, 7 + seq, 15) if seq <= 5 else date(2027, 1, 15),
            amount=Decimal("45"),
            paid_posted_on=date(2026, 8, 14) if seq == 1 else None,
        )
    return plan


def a_checked_run(cycle, window, bill_date, label):
    from apps.billing import check_store

    run = runs.create_run(
        cycle_id=cycle.id,
        period_start=window[0],
        period_end=window[1],
        bill_date=bill_date,
        label=label,
    )
    check_store.check_run(run)
    prepared = runs.prepare_run(
        cycle_id=cycle.id,
        period_start=window[0],
        period_end=window[1],
        service_date=bill_date,
        payment_window=(bill_date, date(bill_date.year, bill_date.month, 22)),
    )
    return run, prepared


def the_bill(tenant, account, run):
    return billing_models.Invoice.objects.filter(
        tenant=tenant, account=account, bill_run=run
    ).first()


# ══════════════════════════════════════════════════════════════════════════
# ADD TO BILL — the instalment on its own line, never a charge
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-38
def test_8243__add_to_bill_bills_the_account_and_prints_the_instalment(brazos, dana):
    from apps.billing import documents, issue

    with tenant_ctx(brazos):
        cycle, account, asset = _setup(
            brazos, dana, account_no="A-09201", asset_no="M-9201", base="26"
        )
        a_plan(brazos, account)
        commit_read(
            dana,
            asset.id,
            day="2026-09-28",
            value="1000",
            prior_value="990",
            consumption="10.000000",
            unit="kWh",
        )
        september, prepared = a_checked_run(cycle, SEPTEMBER, date(2026, 10, 1), "September")
        assert "plan_instalment_due" in {p.reason for p in prepared.decisions}
        decisions.record_decision(
            bill_run=september,
            account_id=str(account.id),
            case="plan_instalment_due",
            choice="add_to_bill",
        )
        runs.calculate_run(
            decisions.apply_decisions(prepared, bill_run=september), bill_run=september
        )
        bill = the_bill(brazos, account, september)
        assert bill is not None, "billed, not held"
        total_before = bill.total
        kinds = set(
            billing_models.InvoiceLine.objects.filter(invoice=bill).values_list("kind", flat=True)
        )
        issue._stamp_plan_instalment(bill)
        bill.refresh_from_db()
        queued = billing_models.BillRunExclusion.objects.filter(
            account=account, bill_run=september
        ).exists()

    assert not queued
    assert kinds <= {"usage", "base", "minimum"}, "the instalment is not a charge line"
    assert bill.total == total_before, "the stamp moves no money"
    line = bill.bill_payload["payment_plan_instalment"]
    assert (line["seq"], line["due_on"], line["currency"]) == (2, "2026-09-15", "USD")
    assert Decimal(line["amount"]) == Decimal("45")
    fields, _absent = documents._footer(bill.bill_payload)
    printed = [f.value for f in fields if f.label == "Payment plan"]
    assert printed == ["Instalment 2: 45.00 USD due 2026-09-15."]


# BULK-CHG-38
def test_8243__skip_still_prints_no_instalment_line(brazos, dana):
    from apps.billing import issue

    with tenant_ctx(brazos):
        cycle, account, asset = _setup(
            brazos, dana, account_no="A-09202", asset_no="M-9202", base="26"
        )
        a_plan(brazos, account)
        commit_read(
            dana,
            asset.id,
            day="2026-09-28",
            value="1000",
            prior_value="990",
            consumption="10.000000",
            unit="kWh",
        )
        september, prepared = a_checked_run(cycle, SEPTEMBER, date(2026, 10, 1), "September")
        decisions.record_decision(
            bill_run=september,
            account_id=str(account.id),
            case="plan_instalment_due",
            choice="skip",
            reason="hardship",
        )
        runs.calculate_run(
            decisions.apply_decisions(prepared, bill_run=september), bill_run=september
        )
        bill = the_bill(brazos, account, september)
        issue._stamp_plan_instalment(bill)
        bill.refresh_from_db()

    assert "payment_plan_instalment" not in (bill.bill_payload or {})


# BULK-CHG-38
def test_8243__issue_stamps_the_instalment_and_add_to_bill_is_applied():
    """Wiring (hard-won law 2): the stamp is called by the real issue path, and
    the answer is no longer a holding one."""
    import inspect

    from apps.billing import issue

    assert "_stamp_plan_instalment(locked)" in inspect.getsource(issue.issue_invoice)
    assert ("plan_instalment_due", "add_to_bill") in decisions.APPLIED_CHOICES
    assert ("plan_instalment_due", "add_to_bill") not in decisions.CHECK_HOLDING
    # DEF-BIL-8412's choice is the bulk lane's and stays its own word.
    assert decisions.CHOICE_APPLY_THIS_BILL != decisions.CHOICE_APPLY_NEXT_BILL


# ══════════════════════════════════════════════════════════════════════════
# APPLY TO THIS BILL — counted exactly once across two months
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-38
@pytest.mark.parametrize("arrived", [True, False], ids=["cleared", "processing"])
def test_8243__apply_to_this_bill_counts_the_payment_once_across_two_months(
    brazos, dana, arrived
):
    """August billed $200.00. $120.00 posted 1 Oct (after September's cut-off),
    allocated by PAYMENTS against August. September: *Apply to this bill* →
    previous $200.00 − paid $120.00 = $80.00 carried. October: the debt it
    carries from August is still $80.00 — the $120.00 has not reduced it a
    second time, and billing wrote no line and no payment row for it.

    DEF-BIL-8651: the same setup with the $120.00 still PROCESSING (not
    arrived) is REFUSED when the clerk answers *Apply to this bill* — both
    rules guarded in one place. The payment here carries no `payment_no`,
    which is why billing asks payments by account and window, not by number."""
    from apps.billing import customers_seam, issue, payments_seam
    from apps.payments import models as payment_models

    def net_prior(bill):
        position = payments_seam.prior_position_for_account(
            bill.account_id,
            totals_by_invoice_id=issue._prior_bill_totals(bill),
            opening=customers_seam.opening_position_for_account(bill.account_id),
        )
        return position.previous_balance - position.payments_credits, position

    with tenant_ctx(brazos):
        cycle, account, asset = _setup(
            brazos, dana, account_no="A-09203", asset_no="M-9203", base="8"
        )
        august_run = runs.create_run(
            cycle_id=cycle.id,
            period_start=AUGUST[0],
            period_end=AUGUST[1],
            bill_date=date(2026, 9, 1),
            label="August",
        )
        august = billing_models.Invoice.objects.create(
            tenant=brazos,
            account=account,
            bill_run=august_run,
            service_date=AUGUST[1],
            period_start=AUGUST[0],
            period_end=AUGUST[1],
            status=billing_models.INVOICE_ISSUED,
            currency="USD",
            subtotal=Decimal("200"),
            invoice_no="BL-2609-009203",
            issued_at=datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc),
            due_date=date(2026, 9, 22),
            tax_total=Decimal("0"),
            total=Decimal("200"),
        )
        payment = payment_models.Payment.objects.create(
            tenant=brazos,
            account=account,
            amount=Decimal("120.000000"),
            currency="USD",
            status=payment_models.PAYMENT_CLEARED if arrived else payment_models.PAYMENT_PROCESSING,
            posted_at=datetime(2026, 10, 1, 15, 0, tzinfo=timezone.utc),
        )
        if arrived:  # money that has not arrived is never allocated
            payment_models.Allocation.objects.create(
                tenant=brazos, payment=payment, invoice=august, amount=Decimal("120")
            )
        commit_read(
            dana,
            asset.id,
            day="2026-09-28",
            value="1000",
            prior_value="990",
            consumption="10.000000",
            unit="kWh",
        )
        september_run, prepared = a_checked_run(cycle, SEPTEMBER, date(2026, 10, 1), "September")
        assert "paid_after_cutoff" in {p.reason for p in prepared.decisions}
        if not arrived:
            with pytest.raises(BillingRuleError) as refused:
                decisions.record_decision(
                    bill_run=september_run,
                    account_id=str(account.id),
                    case="paid_after_cutoff",
                    choice="apply_this_bill",
                )
            assert refused.value.message_key == "billing.check.paidAfterCutoff.notArrived"
            return
        decisions.record_decision(
            bill_run=september_run,
            account_id=str(account.id),
            case="paid_after_cutoff",
            choice="apply_this_bill",
        )
        runs.calculate_run(
            decisions.apply_decisions(prepared, bill_run=september_run), bill_run=september_run
        )
        september = the_bill(brazos, account, september_run)
        september_net, september_position = net_prior(september)
        billing_models.Invoice.objects.filter(pk=september.pk).update(
            status=billing_models.INVOICE_ISSUED,
            issued_at=datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc),
        )
        september.refresh_from_db()
        commit_read(
            dana,
            asset.id,
            day="2026-10-28",
            value="1012",
            prior_value="1000",
            consumption="12.000000",
            unit="kWh",
        )
        october_run, prepared = a_checked_run(cycle, OCTOBER, date(2026, 11, 1), "October")
        runs.calculate_run(
            decisions.apply_decisions(prepared, bill_run=october_run), bill_run=october_run
        )
        october = the_bill(brazos, account, october_run)
        october_net, _ = net_prior(october)
        payment_lines = billing_models.InvoiceLine.objects.filter(
            invoice__in=(september, october)
        ).exclude(kind__in=("usage", "base", "minimum", "tax"))
        payments_rows = payment_models.Payment.objects.filter(account=account).count()
        allocations = payment_models.Allocation.objects.filter(payment=payment).count()

    print(
        f"\nPROOF apply once: Sep carried {september_net} (200 − 120); Oct carried "
        f"{october_net} = 80 + September {september.total}"
    )
    assert september_position.payments_credits == Decimal("120")
    assert september_net == Decimal("80"), "September: $200 − $120"
    assert october_net == Decimal("80") + september.total, "the $120 reduced the debt once"
    assert not payment_lines.exists(), "billing never writes the payment as a charge line"
    assert payments_rows == 1 and allocations == 1, "booked once, by payments"
