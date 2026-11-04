# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-BIL-10200 (the bill run never applied a late fee) ·
#           DEF-BIL-10201 (a Flat late-fee code charged $0.00)
# Ruling:   decision log 2026-10-17 *"THE LATE FEE IS APPLIED BY THE BILL RUN,
#           AND MAY BE FLAT OR A PERCENTAGE"* + *"once per billing period"* +
#           payment plans *"no"*
# Rules:    BR-BIL-001 as amended · BR-BIL-008/002 · BR-BIL-071 · BR-BIL-003 ·
#           BR-RAT-1011 · BR-CUS-043 / BR-BIL-073 (superseded in part) ·
#           CLAUDE.md hard rules 1, 2, 4, 5, 7
# Golden:   GT-8 ❄️ $542.10 → $8.13, unchanged
# ───────────────────────────────────────────────────────
"""The late fee the bill run adds — Check, Calculate and Issue, end to end.

THE WORLD. A June 2026 run (bill date **1 Jul**) over one electric account on
a published plan pointed at the tenant's seeded `LATE` code (1.5%, minimum
$5.00, grace 5 calendar days). Before it, the account holds ISSUED bills of
earlier periods, written directly with their due dates and totals, and
payments allocated against them with the day the money cleared. Every figure
asserted is one the PO was shown or is computed from one:

  * $100.00 due 10 Jun, grace to 15 Jun, paid **20 Jun** (late) → **$5.00**
  * the same paid **13 Jun** (inside grace) → nothing
  * $24.99 overdue → nothing · $25.00 → **$5.00** (strictly under)
  * ❄️ $542.10 → **$8.13** (GT-8, the percent path, unchanged)
  * Flat $10.00 on $900.00 overdue → **$10.00**
  * A $100 (already late at the last bill) + B $80 (late since) → ONE fee on
    $180 = max($5, $2.70) = **$5.00**
  * a live payment plan → nothing (Ana, $62 → **$0.00**)
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from apps.billing import check_store, decisions, issue, late_fee, late_fee_run, models, runs
from apps.billing import selectors as billing_selectors
from apps.billing.exceptions import BillingRuleError
from apps.ledger import models as ledger_models
from apps.payments import models as payment_models
from apps.rating import models as rating_models

from tests.test_bbr_check_engine import BILL_DATE, PERIOD_END, PERIOD_START, a_cycle
from tests.test_def_719_late_fee_charge_code import LATE_GL_CODE, _account_by_code, a_mapped_late_fee_code
from tests.test_us_bil_001_prepare import a_billed_unit, a_priced_plan, an_account
from tests.test_us_bil_005_issue import ISSUED_AT, TEMPLATE_ID, TEMPLATE_VERSION
from tests.test_us_bil_005_release_gate import a_release
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

UTC = timezone.utc


# ── the world ──────────────────────────────────────────────────────────────
def _late_code(tenant):
    return rating_models.Charge.objects.get(tenant=tenant, code="LATE", deleted_at__isnull=True)


def a_flat_late_code(tenant, amount=Decimal("10.00")):
    """A penalty code of amount rule FLAT — DEF-BIL-10201's case."""
    charge = rating_models.Charge.objects.create(
        tenant=tenant,
        code="LATEFLAT",
        name="Late fee (flat)",
        charge_type="penalty",
        amount_rule="flat",
        amount=amount,
        grace_days=5,
        grace_mode="calendar",
    )
    from apps.rating import charge_prices

    charge_prices.write_flat_amount_directly(charge, amount)
    return charge


def an_overdue_account(tenant, actor, *, no="10200", late_code=None, cycle=None, plan_name=None):
    cycle = cycle or a_cycle(tenant, code=f"06-{no}")
    plan = a_priced_plan(tenant, name=plan_name or f"Plan {no}")
    code = late_code or _late_code(tenant)
    rating_models.RatePlan.objects.filter(pk=plan.pk).update(late_fee_charge=code)
    unit = a_billed_unit(actor, tenant, cycle, plan, asset_no=f"M-{no}", label=f"Unit {no}")
    account = an_account(tenant, unit["id"], f"A-{no}")
    return cycle, account


def an_earlier_bill(tenant, account, *, total, due, period=(date(2026, 5, 1), date(2026, 5, 31)),
                    bill_date=date(2026, 6, 1), no=None, status=models.INVOICE_ISSUED):
    """An ISSUED bill of an earlier period — the facts the late fee reads."""
    return models.Invoice.objects.create(
        tenant=tenant,
        account=account,
        invoice_no=no or f"BL-{account.account_no}-{due.isoformat()}",
        service_date=bill_date,
        period_start=period[0],
        period_end=period[1],
        due_date=due,
        status=status,
        subtotal=Decimal(total),
        total=Decimal(total),
        issued_at=datetime.combine(bill_date, datetime.min.time(), tzinfo=UTC),
    )


def a_payment(tenant, account, bill, *, amount, cleared, posted=None):
    """Money that met `bill`, cleared (arrived) on `cleared`."""
    posted = posted or cleared
    payment = payment_models.Payment.objects.create(
        tenant=tenant,
        account=account,
        amount=Decimal(amount),
        status="cleared",
        posted_at=datetime.combine(posted, datetime.min.time(), tzinfo=UTC),
        cleared_at=datetime.combine(cleared, datetime.min.time(), tzinfo=UTC),
    )
    payment_models.Allocation.objects.create(
        tenant=tenant, payment=payment, invoice=bill, amount=Decimal(amount)
    )
    return payment


def a_run(cycle):
    return runs.create_run(
        cycle_id=cycle.id,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        bill_date=BILL_DATE,
        label="June 2026 · late fees",
    )


def late_findings(run):
    check_store.check_run(run)
    return {
        row["account_no"]: row
        for row in check_store.tag_accounts(run, "late_fee", {"per": 100})["results"]
    }


def calculate(run):
    prepared = decisions.apply_decisions(billing_selectors.prepared_for(run), bill_run=run)
    runs.calculate_run(prepared, bill_run=run)
    return prepared


def fee_lines(run, account):
    bill = models.Invoice.objects.filter(bill_run=run, account=account).first()
    assert bill is not None, "the account must be billed"
    return bill, list(models.InvoiceLine.objects.filter(invoice=bill, kind="fee"))


# ── 1 · past grace → one fee; within grace → none ──────────────────────────
def test_paid_after_grace_counts_and_the_october_bill_carries_five_dollars(brazos, dana):
    """The PO's worked example, moved to June: $100.00 due 10 Jun, grace to
    15 Jun, money arrived 20 Jun → the next bill carries $5.00."""
    with tenant_ctx(brazos):
        a_mapped_late_fee_code(brazos)
        cycle, account = an_overdue_account(brazos, dana)
        bill = an_earlier_bill(brazos, account, total="100.00", due=date(2026, 6, 10))
        a_payment(brazos, account, bill, amount="100.00", cleared=date(2026, 6, 20))
        run = a_run(cycle)
        found = late_findings(run)["A-10200"]
        assert found["params"]["amount"] == "5.00"
        assert found["params"]["overdue"] == "100.00"
        assert found["answer"] == decisions.CHOICE_APPLY and found["answer_source"] == "default"
        assert check_store.account_findings(run, str(account.id))["status"] == "ready"
        calculate(run)
        _bill, fees = fee_lines(run, account)
        assert [f.amount for f in fees] == [Decimal("5.00")]
        assert fees[0].taxable is False
        assert str(fees[0].charge_id) == str(_late_code(brazos).id)


def test_paid_inside_grace_owes_no_fee(brazos, dana):
    with tenant_ctx(brazos):
        cycle, account = an_overdue_account(brazos, dana)
        bill = an_earlier_bill(brazos, account, total="100.00", due=date(2026, 6, 10))
        a_payment(brazos, account, bill, amount="100.00", cleared=date(2026, 6, 13))
        assert late_findings(a_run(cycle)) == {}


def test_unpaid_but_still_inside_grace_on_the_bill_date_owes_no_fee(brazos, dana):
    with tenant_ctx(brazos):
        cycle, account = an_overdue_account(brazos, dana)
        # due 28 Jun + 5 days → grace runs out after 3 Jul; the bill date is 1 Jul.
        an_earlier_bill(brazos, account, total="100.00", due=date(2026, 6, 28))
        assert late_findings(a_run(cycle)) == {}


# ── 2 · the $25.00 floor, strictly under ───────────────────────────────────
@pytest.mark.parametrize("owed, fee", [("24.99", None), ("25.00", "5.00")])
def test_the_floor_is_strict(brazos, dana, owed, fee):
    with tenant_ctx(brazos):
        cycle, account = an_overdue_account(brazos, dana)
        an_earlier_bill(brazos, account, total=owed, due=date(2026, 6, 10))
        found = late_findings(a_run(cycle))
        assert (found["A-10200"]["params"]["amount"] if found else None) == fee


# ── 3 · GT-8 unchanged; flat $10 ───────────────────────────────────────────
def test_gt8_percent_path_is_unchanged(brazos, dana):
    with tenant_ctx(brazos):
        cycle, account = an_overdue_account(brazos, dana)
        an_earlier_bill(brazos, account, total="542.10", due=date(2026, 6, 10))
        assert late_findings(a_run(cycle))["A-10200"]["params"]["amount"] == "8.13"


def test_a_flat_ten_dollar_code_charges_ten_dollars_on_nine_hundred(brazos, dana):
    with tenant_ctx(brazos):
        flat = a_flat_late_code(brazos)
        cycle, account = an_overdue_account(brazos, dana, late_code=flat)
        an_earlier_bill(brazos, account, total="900.00", due=date(2026, 6, 10))
        run = a_run(cycle)
        found = late_findings(run)["A-10200"]
        assert found["params"]["amount"] == "10.00"
        assert found["params"]["amount_rule"] == "flat"
        calculate(run)
        _bill, fees = fee_lines(run, account)
        assert [f.amount for f in fees] == [Decimal("10.00")]
        assert str(fees[0].charge_id) == str(flat.id)


def test_flat_terms_and_its_floor_and_grace(brazos, dana):
    """The flat path runs the same two gates as the percent path."""
    with tenant_ctx(brazos):
        flat = a_flat_late_code(brazos)
        terms = late_fee.LateFeeTerms(
            percent=Decimal("0"), minimum=Decimal("0"), charge_id=str(flat.id), code="LATEFLAT",
            amount_rule="flat", flat_amount=Decimal("10.00"),
        )

        def fee(overdue, as_of=date(2026, 7, 1)):
            return late_fee.assess_late_fee_on_terms(
                terms, overdue_amount=Decimal(overdue), due_date=date(2026, 6, 10), as_of=as_of,
                grace_days=5, grace_mode="calendar",
            )

        assert fee("900.00") == Decimal("10.00")
        assert fee("24.99") == Decimal("0.00")
        assert fee("900.00", as_of=date(2026, 6, 15)) == Decimal("0.00")


def test_a_flat_code_with_no_amount_refuses_rather_than_charging_zero(brazos, dana):
    with tenant_ctx(brazos):
        flat = a_flat_late_code(brazos)
        from apps.rating import charge_prices

        charge_prices.write_flat_amount_directly(flat, None)
        cycle, account = an_overdue_account(brazos, dana, late_code=flat)
        an_earlier_bill(brazos, account, total="900.00", due=date(2026, 6, 10))
        run = a_run(cycle)
        check_store.check_run(run)
        codes = [f["code"] for f in check_store.account_findings(run, str(account.id))["findings"]]
        assert "check_refused" in codes and "late_fee" not in codes


# ── 4 · once per billing period ────────────────────────────────────────────
def test_two_late_bills_in_one_period_make_one_fee(brazos, dana):
    """A $100 (April, already late at May's bill) + B $80 (May, late since)."""
    with tenant_ctx(brazos):
        a_mapped_late_fee_code(brazos)
        cycle, account = an_overdue_account(brazos, dana)
        an_earlier_bill(brazos, account, total="100.00", due=date(2026, 5, 10),
                        period=(date(2026, 4, 1), date(2026, 4, 30)), bill_date=date(2026, 5, 1))
        an_earlier_bill(brazos, account, total="80.00", due=date(2026, 6, 10))
        run = a_run(cycle)
        found = late_findings(run)["A-10200"]
        assert found["params"]["overdue"] == "180.00" and found["params"]["bills"] == 2
        assert found["params"]["amount"] == "5.00"
        calculate(run)
        _bill, fees = fee_lines(run, account)
        assert [f.amount for f in fees] == [Decimal("5.00")]


def _inputs(account, bills, *, as_of, looked):
    return late_fee_run.LateFeeInputs(
        as_of=as_of,
        bills={str(account.id): bills},
        previous_look={str(account.id): looked} if looked else {},
    )


def test_the_next_period_still_overdue_gets_its_own_fee_and_a_bill_paid_late_is_fined_once(
    brazos, dana
):
    """The decision log's own figures: A $100 due 09/21 unpaid, B $80 due 10/21
    unpaid → October $5.00 on $100; November $5.00 on $180. And A paid late
    (10/05) is fined by October and NOT again by November."""
    with tenant_ctx(brazos):
        _cycle, account = an_overdue_account(brazos, dana)
        plan_id = str(rating_models.RatePlan.objects.get(name="Plan 10200").id)
        a_bill = late_fee_run.EarlierBill("a", "A", date(2026, 9, 21), Decimal("100.00"))
        b_bill = late_fee_run.EarlierBill("b", "B", date(2026, 10, 21), Decimal("80.00"))
        october = late_fee_run.assess_account(
            _inputs(account, [a_bill], as_of=date(2026, 10, 1), looked=date(2026, 9, 1)),
            account.id, rate_plan_id=plan_id, customer_class=None,
        )
        assert (october.amount, october.overdue) == (Decimal("5.00"), Decimal("100.00"))
        november = late_fee_run.assess_account(
            _inputs(account, [a_bill, b_bill], as_of=date(2026, 11, 1), looked=date(2026, 10, 1)),
            account.id, rate_plan_id=plan_id, customer_class=None,
        )
        assert (november.amount, november.overdue) == (Decimal("5.00"), Decimal("180.00"))
        paid_late = late_fee_run.EarlierBill(
            "a", "A", date(2026, 9, 21), Decimal("100.00"),
            receipts=(late_fee.PaymentReceipt(Decimal("100.00"), date(2026, 10, 5), date(2026, 10, 5)),),
        )
        assert late_fee_run.assess_account(
            _inputs(account, [paid_late], as_of=date(2026, 11, 1), looked=date(2026, 10, 1)),
            account.id, rate_plan_id=plan_id, customer_class=None,
        ) is None, "paid late: fined once, by October, never again"


def test_re_prepare_and_re_calculate_never_add_a_second_fee(brazos, dana):
    with tenant_ctx(brazos):
        a_mapped_late_fee_code(brazos)
        cycle, account = an_overdue_account(brazos, dana)
        an_earlier_bill(brazos, account, total="100.00", due=date(2026, 6, 10))
        run = a_run(cycle)
        late_findings(run)
        late_findings(run)
        calculate(run)
        calculate(run)
        assert models.Invoice.objects.filter(bill_run=run, account=account).count() == 1
        _bill, fees = fee_lines(run, account)
        assert [f.amount for f in fees] == [Decimal("5.00")]


def test_a_bill_for_this_period_already_carrying_the_fee_stops_a_second(brazos, dana):
    with tenant_ctx(brazos):
        cycle, account = an_overdue_account(brazos, dana)
        an_earlier_bill(brazos, account, total="100.00", due=date(2026, 6, 10))
        same = an_earlier_bill(brazos, account, total="5.00", due=date(2026, 7, 22),
                               period=(PERIOD_START, PERIOD_END), bill_date=BILL_DATE,
                               no="BL-SAME-PERIOD")
        models.InvoiceLine.objects.create(
            tenant=brazos, invoice=same, account=account, kind="fee", description="Late fee",
            amount=Decimal("5.00"), taxable=False, charge=_late_code(brazos),
        )
        run = a_run(cycle)
        check_store.check_run(run)
        codes = [f["code"] for f in (check_store.account_findings(run, str(account.id)) or {}).get("findings", [])]
        assert "late_fee" not in codes


# ── 5 · waive, per account, never in bulk ──────────────────────────────────
def test_waive_one_account_and_the_bill_carries_no_fee(brazos, dana):
    with tenant_ctx(brazos):
        cycle, account = an_overdue_account(brazos, dana)
        an_earlier_bill(brazos, account, total="100.00", due=date(2026, 6, 10))
        run = a_run(cycle)
        late_findings(run)
        decisions.record_decision(
            bill_run=run, account_id=str(account.id), case="late_fee",
            choice=decisions.CHOICE_WAIVE, reason="first time", decided_by=dana.user,
        )
        totals = check_store.late_fee_totals(run)
        assert totals == {"accounts": 0, "total": "0.00", "waived": 1, "currency": "USD"}
        calculate(run)
        _bill, fees = fee_lines(run, account)
        assert fees == []


def test_waive_for_all_is_refused(brazos, dana):
    with tenant_ctx(brazos):
        cycle, _account = an_overdue_account(brazos, dana)
        run = a_run(cycle)
        with pytest.raises(BillingRuleError):
            decisions.set_standing_answer(bill_run=run, case="late_fee", choice=decisions.CHOICE_WAIVE)


def test_the_tag_totals_count_and_sum_every_account(brazos, dana):
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos, code="06-TOT")
        _c, one = an_overdue_account(brazos, dana, no="10201", cycle=cycle)
        _c, two = an_overdue_account(brazos, dana, no="10202", cycle=cycle)
        an_earlier_bill(brazos, one, total="100.00", due=date(2026, 6, 10))
        an_earlier_bill(brazos, two, total="542.10", due=date(2026, 6, 10))
        run = a_run(cycle)
        page = (check_store.check_run(run), check_store.tag_accounts(run, "late_fee", {}))[1]
        assert page["late_fees"] == {"accounts": 2, "total": "13.13", "waived": 0, "currency": "USD"}


# ── 6 · payment plans (PO 2026-10-17, *"no"*) ──────────────────────────────
@pytest.mark.parametrize("status, charged", [("active", False), ("proposed", True)])
def test_a_live_payment_plan_is_charged_no_late_fee(brazos, dana, status, charged):
    """Ana: October $62 unpaid past grace on a live plan → $0.00 (was $5.00)."""
    from apps.payments.collections_models import PaymentPlan

    with tenant_ctx(brazos):
        cycle, account = an_overdue_account(brazos, dana)
        an_earlier_bill(brazos, account, total="62.00", due=date(2026, 6, 10))
        PaymentPlan.objects.create(
            tenant=brazos, account=account, total_amount=Decimal("270.00"),
            installment_count=6, status=status, proposed_on=date(2026, 6, 1),
        )
        found = late_findings(a_run(cycle))
        assert ("A-10200" in found) is charged


# ── 7 · tenant isolation (hard rule 1) ─────────────────────────────────────
def test_another_tenants_overdue_bill_is_never_read(brazos, lonestar, dana):
    with tenant_ctx(brazos):
        cycle, account = an_overdue_account(brazos, dana)
        run = a_run(cycle)
    # An overdue bill written for the brazos account id under LONESTAR's tenant
    # is a cross-tenant row; the brazos read must not see it.
    with tenant_ctx(lonestar):
        models.Invoice.objects.create(
            tenant=lonestar, account_id=account.id, invoice_no="BL-LS-X",
            service_date=date(2026, 6, 1), period_start=date(2026, 5, 1),
            period_end=date(2026, 5, 31), due_date=date(2026, 6, 10),
            status=models.INVOICE_ISSUED, total=Decimal("900.00"),
        )
    with tenant_ctx(brazos):
        inputs = late_fee_run.load_inputs(
            [account.id], as_of=BILL_DATE, period_start=PERIOD_START, period_end=PERIOD_END
        )
        assert inputs.bills == {}
        assert late_findings(run) == {}


# ── 8 · issued: untaxed, and posted to the ledger as a balanced pair ──────
def test_the_fee_is_issued_untaxed_and_the_books_balance(brazos, dana):
    with tenant_ctx(brazos):
        a_mapped_late_fee_code(brazos)
        cycle, account = an_overdue_account(brazos, dana)
        an_earlier_bill(brazos, account, total="100.00", due=date(2026, 6, 10))
        run = a_run(cycle)
        late_findings(run)
        calculate(run)
        draft, fees = fee_lines(run, account)
        a_release(brazos, run, dana)
        issued = issue.issue_invoice(
            draft, issued_at=ISSUED_AT, template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION, actor=dana,
        )
        stored = models.Invoice.objects.get(pk=issued.pk)
        assert stored.status == models.INVOICE_ISSUED
        fee = stored.lines.get(kind="fee")
        assert fee.amount == Decimal("5.00") and fee.taxable is False
        assert str(fee.gl_account_id) == str(_account_by_code(LATE_GL_CODE).id)
        entry = ledger_models.JournalEntry.objects.filter(tenant=brazos, source_id=stored.pk).first() \
            or ledger_models.JournalEntry.objects.filter(tenant=brazos).latest("created_at")
        lines = ledger_models.JournalLine.objects.filter(tenant=brazos, journal_entry=entry)
        debits = sum((l.amount for l in lines if l.side == "debit"), Decimal("0"))
        credits = sum((l.amount for l in lines if l.side == "credit"), Decimal("0"))
        assert debits == credits == stored.total
        late_credit = sum(
            (l.amount for l in lines if l.side == "credit" and l.ledger_account.code == LATE_GL_CODE),
            Decimal("0"),
        )
        assert late_credit == Decimal("5.00")



# ── 9 · DEF-BIL-10201 at the formula's own door ───────────────────────────
def test_the_production_entry_point_charges_a_flat_code_its_flat_amount(brazos, dana):
    """`late_fee.assess_late_fee_for_plan` on a plan naming a Flat $10.00 code:
    before DEF-BIL-10201 the terms read served percent 0 and minimum 0 and the
    fee came to **$0.00**; it is **$10.00**."""
    with tenant_ctx(brazos):
        flat = a_flat_late_code(brazos)
        an_overdue_account(brazos, dana, late_code=flat)
        plan_id = rating_models.RatePlan.objects.get(name="Plan 10200").id
        fee, terms = late_fee.assess_late_fee_for_plan(
            rate_plan_id=plan_id, overdue_amount=Decimal("900.00"),
            due_date=date(2026, 6, 10), as_of=date(2026, 7, 1),
        )
        assert fee == Decimal("10.00")
        assert getattr(terms, "amount_rule", None) == "flat"



# ── 10 · a 0% penalty with no minimum is refused (DEF-BIL-10201) ───────────
@pytest.mark.parametrize("percent, minimum, refused", [("0", None, True), ("0", "5.00", False), ("0.015", None, False)])
def test_a_zero_percent_penalty_with_no_minimum_is_refused(brazos, dana, percent, minimum, refused):
    from apps.rating import services as rating_services
    from core import errors

    payload = {
        "code": f"PEN{len(percent)}{minimum or 'X'}"[:20],
        "name": "Penalty",
        "charge_type": "penalty",
        "amount_rule": "percent" if minimum is None else "percent_with_minimum",
        "percent": percent,
        "effective_from": "2026-01-01",
    }
    if minimum is not None:
        payload["min_amount"] = minimum
    with tenant_ctx(brazos):
        if refused:
            with pytest.raises(errors.ValidationError) as caught:
                rating_services.create_charge(dana, payload)
            assert "rating.charges.penalty_needs_percent_or_minimum" in str(caught.value.__dict__)
        else:
            rating_services.create_charge(dana, payload)
