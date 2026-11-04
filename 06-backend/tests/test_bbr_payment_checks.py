# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-037 TC-10 (bulk run · Check — Payments & balances)
# Rules:    BR-BIL-1053 (payments at Check) · BR-BIL-017 (auto re-level at ±20%
#           drift — the threshold level pay off track reuses) · BR-PAY-010 /
#           BR-PAY-012 (an overpayment or unapplied money is held on the
#           account) · CLAUDE.md hard rule 1 (tenant scoping)
# Plan:     15-bulk-bill-run-build-plan.md B12 · changes row 38
# Defects:  DEF-BIL-8240 (unmatched payment; bounced payment not reversed) ·
#           DEF-BIL-8241 (level pay off track)
# Decision: 12-governance/02-decision-log.md 2026-09-30 *"THE FOUR PAYMENT
#           CHECKS WITH NO DATA BEHIND THEM ARE BUILT, NOT PUT TO THE PO"*
# ───────────────────────────────────────────────────────
"""The Payments & balances facts that had no reader: written red first.

* **Unmatched payment** — PO option B (2026-09-30): a payment RECEIVED that
  could not be matched to an account, tied to this one by the payer's details or
  a clerk, and not yet posted. Never a credit balance. A DECISION: Hold, or bill
  without it. Worked: a $120.00 transfer tied by the payer's name → flagged;
  the $80.00 June credit → not flagged.
* **Level pay off track** — a level-pay account whose trailing average has
  drifted MORE than the tenant's re-level threshold (±20% seeded, BR-BIL-017)
  from its level. Worked: level $242, trailing $300 → +23.97% → tagged; trailing
  $260 → +7.44% → not tagged. A WARNING: the account still bills and the Check
  re-levels nothing.
* **Bounced payment not reversed** — stays DECLARED ABSENT: no table holds a
  bank return advice against one of our payments without also holding its
  reversal (see `bill_run_checks.UNAVAILABLE`).

`BULK-CHG-38` is changes row 38 — *Payments & balances* is a Check category.
The payment reads are also run on PostgreSQL 16 (`--ds=config.settings.pgtest`).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from apps.billing import models as billing_models
from apps.payments import models as payment_models

from tests.test_bbr_check_engine import BILL_DATE, codes_for, prepare, three_accounts
from tests.test_us_bil_025_026_bills_read import an_account as a_bare_account
from tests.test_us_bil_025_026_bills_read import an_invoice
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

DUE_DATE = date(2026, 7, 22)
WINDOW = (BILL_DATE, DUE_DATE)
JUNE_20 = datetime(2026, 6, 20, 15, 0, tzinfo=timezone.utc)


def a_payment(tenant, account, amount, **extra):
    values = dict(
        tenant=tenant,
        account=account,
        amount=Decimal(amount),
        currency="USD",
        status=payment_models.PAYMENT_CLEARED,
        posted_at=JUNE_20,
    )
    values.update(extra)
    return payment_models.Payment.objects.create(**values)


def a_may_bill(tenant, account, number):
    """An issued May bill, so the June run starts the day after it."""
    return an_invoice(
        tenant,
        account,
        invoice_no=number,
        period_start=date(2026, 5, 1),
        period_end=date(2026, 5, 31),
        service_date=date(2026, 5, 31),
    )


def findings(prepared, account, code):
    return [f for f in prepared.findings.get(str(account.id), ()) if f.code == code]


# ══════════════════════════════════════════════════════════════════════════
# DEF-BIL-8240 (a) · UNMATCHED PAYMENT — PO option B (2026-09-30, *"b"*): a
# payment RECEIVED that could not be matched to an account, tied to this one by
# the payer's details or a clerk. NEVER a credit balance.
# ══════════════════════════════════════════════════════════════════════════
def an_import_row(tenant, account, amount, *, method, batch_status=None, row_no=1, **extra):
    """One line of a received remittance file, staged and not yet posted."""
    batch = payment_models.PaymentImportBatch.objects.create(
        tenant=tenant,
        file_name=f"lockbox-{row_no}.csv",
        status=batch_status or payment_models.IMPORT_VALIDATED,
    )
    values = dict(
        tenant=tenant,
        batch=batch,
        row_no=row_no,
        payer_name_raw="M ALVAREZ",
        amount_raw=amount,
        amount=Decimal(amount),
        paid_on=date(2026, 6, 24),
        reference="TRF-5521",
        account=account,
        match_method=method,
        match_state=(
            payment_models.ROW_CLEAN
            if method == payment_models.MATCH_MANUAL
            else payment_models.ROW_REVIEW
        ),
    )
    values.update(extra)
    return payment_models.PaymentImportRow.objects.create(**values)


# BULK-CHG-38
def test_unmatched__a_received_transfer_tied_by_the_payers_name_is_a_decision(brazos, dana):
    """The PO's worked case: a $120.00 bank transfer with no account number,
    tied to Maria's account by the payer's name and not yet posted → *Unmatched
    payment*, a DECISION (Hold / bill without it)."""
    with tenant_ctx(brazos):
        cycle, _plan, accounts = three_accounts(brazos, dana)
        maria = accounts["A-00106"]
        an_import_row(brazos, maria, "120.00", method=payment_models.MATCH_NAME_AMOUNT)
        prepared = prepare(cycle, payment_window=WINDOW)
        unavailable = prepared_unavailable(cycle)

    assert codes_for(prepared, maria) == ["unmatched_payment"]
    [fact] = findings(prepared, maria, "unmatched_payment")
    assert Decimal(fact.params["received"]) == Decimal("120")
    assert fact.params["receipts"] == 1
    assert fact.params["reference"] == "TRF-5521"
    assert fact.params["received_on"] == "2026-06-24"
    assert fact.params["linked_by"] == "name_amount"
    assert fact.severity == "decision"
    [row] = [d for d in prepared.decisions if d.account_no == "A-00106"]
    assert row.reason == "unmatched_payment"
    assert "unmatched_payment" not in {u["code"] for u in unavailable}
    assert "level_pay_off_track" not in {u["code"] for u in unavailable}


# BULK-CHG-38
def test_unmatched__a_credit_balance_is_never_flagged(brazos, dana):
    """PO option B: *"never a credit balance"*. Maria paid $80.00 on 20 June
    against no bill — that credit comes off the next bill and is NOT a Check
    question. Nor is $40.00 left over from $100.00 with $60.00 on a bill."""
    with tenant_ctx(brazos):
        cycle, _plan, accounts = three_accounts(brazos, dana)
        a_payment(brazos, accounts["A-00106"], "80.000000", payment_no="PMT-0080")
        bill = a_may_bill(brazos, accounts["A-00101"], "BL-2605-000101")
        part = a_payment(brazos, accounts["A-00101"], "100.000000")
        payment_models.Allocation.objects.create(
            tenant=brazos, payment=part, invoice=bill, amount=Decimal("60.000000")
        )
        prepared = prepare(cycle, payment_window=WINDOW)

    assert findings(prepared, accounts["A-00106"], "unmatched_payment") == []
    assert findings(prepared, accounts["A-00101"], "unmatched_payment") == []


# BULK-CHG-38
def test_unmatched__a_clerk_linked_receipt_counts_and_posted_or_unlinked_ones_do_not(brazos, dana):
    """A clerk placed a $55.00 lockbox line on A-00101 and it is not posted →
    flagged. A row already posted (it is a payment now), a row in a discarded
    file, and a row that names no account are not."""
    with tenant_ctx(brazos):
        cycle, _plan, accounts = three_accounts(brazos, dana)
        an_import_row(brazos, accounts["A-00101"], "55.00", method=payment_models.MATCH_MANUAL)
        posted = a_payment(brazos, accounts["A-00102"], "70.000000")
        an_import_row(
            brazos,
            accounts["A-00102"],
            "70.00",
            method=payment_models.MATCH_MANUAL,
            row_no=2,
            payment_id=posted.pk,
        )
        an_import_row(
            brazos,
            accounts["A-00102"],
            "90.00",
            method=payment_models.MATCH_NAME_AMOUNT,
            row_no=3,
            batch_status=payment_models.IMPORT_DISCARDED,
        )
        an_import_row(brazos, None, "33.00", method=payment_models.MATCH_NONE, row_no=4)
        prepared = prepare(cycle, payment_window=WINDOW)

    [fact] = findings(prepared, accounts["A-00101"], "unmatched_payment")
    assert Decimal(fact.params["received"]) == Decimal("55")
    assert fact.params["linked_by"] == "manual"
    assert findings(prepared, accounts["A-00102"], "unmatched_payment") == []


# BULK-CHG-38 · CLAUDE.md hard rule 1
def test_unmatched__another_tenants_receipt_never_tags_this_tenant(brazos, dana, lonestar, erin):
    """Lone Star holds a $500.00 received transfer tied to its own account and a
    landed bank return; Brazos's accounts are untagged, and asking under
    Brazos's context for Lone Star's account answers nothing."""
    from apps.payments import bill_run_checks

    with tenant_ctx(lonestar):
        theirs = a_bare_account(lonestar, erin, account_no="LS-0001", service="water")
        an_import_row(lonestar, theirs, "500.00", method=payment_models.MATCH_NAME_AMOUNT)
        payment_models.PaymentWebhookEvent.objects.create(
            tenant=lonestar,
            provider="payments_kiosk",
            event_id="K-88231|return",
            status=payment_models.WEBHOOK_RECEIVED,
            body={"eventType": "return", "accountNumber": "A-00106", "returnCode": "R01"},
            received_at=datetime(2026, 6, 25, 15, 0, tzinfo=timezone.utc),
        )
        assert bill_run_checks.unmatched_payments([theirs.id], period_end=date(2026, 6, 30))

    with tenant_ctx(brazos):
        cycle, _plan, accounts = three_accounts(brazos, dana)
        prepared = prepare(cycle, payment_window=WINDOW)
        assert bill_run_checks.unmatched_payments([theirs.id], period_end=date(2026, 6, 30)) == []
        assert (
            bill_run_checks.payment_facts_for_accounts(
                [theirs.id], period_end=date(2026, 6, 30), bill_date=BILL_DATE, due_date=DUE_DATE
            )
            == {}
        )

    for account in accounts.values():
        assert codes_for(prepared, account) == []


# BULK-CHG-38
def test_unmatched__the_definition_is_one_function():
    """The tag's meaning lives in `unmatched_payments` and nowhere else."""
    import inspect

    from apps.payments import bill_run_checks

    [reader] = [r for code, r in bill_run_checks.FACT_READERS if code == "unmatched_payment"]
    assert "unmatched_payments(" in inspect.getsource(reader)
    assert inspect.getsource(bill_run_checks).count("FACT_UNMATCHED,") == 2


# BULK-CHG-38
def test_bounced__still_declared_absent_and_only_it_and_credit_covers_bill():
    from apps.payments import bill_run_checks

    absent = {row["code"]: row for row in bill_run_checks.UNAVAILABLE}
    assert set(absent) == {"bounced_payment_not_reversed", "credit_covers_bill"}
    assert absent["bounced_payment_not_reversed"]["reason"] == "no_return_advice_without_reversal"


def prepared_unavailable(cycle):
    from apps.billing import check_engine

    ctx = check_engine.CheckContext.for_pass(
        period_start=date(2026, 6, 1),
        period_end=date(2026, 6, 30),
        price_date=date(2026, 6, 30),
        cycle_days=30,
        scope_services=None,
        payment_window=WINDOW,
    )
    return ctx.unavailable


# ══════════════════════════════════════════════════════════════════════════
# DEF-BIL-8241 · LEVEL PAY OFF TRACK — BR-BIL-017's ±20%, a WARNING
# ══════════════════════════════════════════════════════════════════════════
def on_level_pay(tenant, account, level, trailing, *, months=12):
    """Enrol at `level` and issue `months` monthly bills of `trailing` each,
    the newest ending in May 2026 (before this June run)."""
    billing_models.AccountBudgetStatus.objects.create(
        tenant=tenant,
        account=account,
        level=Decimal(level),
        currency="USD",
        enrolled_on=date(2025, 6, 1),
        last_leveled_at=date(2025, 6, 1),
    )
    for back in range(months):
        year, month = 2026, 5 - back
        while month <= 0:
            year, month = year - 1, month + 12
        start = date(year, month, 1)
        end = date(year + (month == 12), month % 12 + 1, 1)
        an_invoice(
            tenant,
            account,
            invoice_no=f"BL-{account.account_no}-{year}{month:02d}",
            period_start=start,
            period_end=date.fromordinal(end.toordinal() - 1),
            service_date=start,
            total=Decimal(trailing),
            subtotal=Decimal(trailing),
            tax_total=Decimal("0"),
        )


# BULK-CHG-38
def test_level_pay__drift_past_twenty_percent_is_a_warning_not_a_decision(brazos, dana):
    """Level $242, trailing twelve bills of $300 → +23.97% → *Level pay off
    track*, a WARNING. The account stays ready, nothing is asked, nothing is
    re-levelled."""
    with tenant_ctx(brazos):
        cycle, _plan, accounts = three_accounts(brazos, dana)
        on_level_pay(brazos, accounts["A-00106"], "242", "300.00")
        prepared = prepare(cycle, payment_window=WINDOW)
        status = billing_models.AccountBudgetStatus.objects.get(account=accounts["A-00106"])

    assert codes_for(prepared, accounts["A-00106"]) == ["level_pay_off_track"]
    [fact] = findings(prepared, accounts["A-00106"], "level_pay_off_track")
    assert fact.severity == "warning"
    assert fact.params["level"] == "242.00"
    assert fact.params["trailing_average"] == "300.00"
    assert fact.params["drift_pct"] == "23.97"
    assert fact.params["threshold_pct"] == "20.00"
    assert "A-00106" in {d.account_no for d in prepared.ready}
    assert "A-00106" not in {d.account_no for d in prepared.decisions}
    assert "A-00106" in {w.account_no for w in prepared.warnings}
    assert status.level == Decimal("242")  # the Check never re-levels


# BULK-CHG-38
def test_level_pay__inside_the_band_or_without_a_full_year_is_not_tagged(brazos, dana):
    """$260 against $242 is +7.44% — inside ±20%. An account with only six
    bills has no trailing year to average, so no figure is made up for it."""
    with tenant_ctx(brazos):
        cycle, _plan, accounts = three_accounts(brazos, dana)
        on_level_pay(brazos, accounts["A-00101"], "242", "260.00")
        on_level_pay(brazos, accounts["A-00102"], "242", "400.00", months=6)
        prepared = prepare(cycle, payment_window=WINDOW)

    assert findings(prepared, accounts["A-00101"], "level_pay_off_track") == []
    assert findings(prepared, accounts["A-00102"], "level_pay_off_track") == []


# BULK-CHG-38
def test_level_pay__the_taxonomy_says_warning_and_offers_no_re_level():
    from apps.billing import check_taxonomy, decisions

    assert check_taxonomy.severity_of("level_pay_off_track") == check_taxonomy.WARNING
    assert "level_pay_off_track" not in decisions.CHECK_CHOICES_BY_CASE
    assert "level_pay_off_track" not in decisions.MUST_ANSWER_CASES
