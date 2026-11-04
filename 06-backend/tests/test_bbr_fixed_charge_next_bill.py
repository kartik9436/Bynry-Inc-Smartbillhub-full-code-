# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-037 AMENDED (bulk Check decisions) — the five fixed-charge
#           cases of `04-docs/05-modules/07-billing/16-check-decisions-next-bill.md`
#           §2, each RULED by the PO on 2026-09-30 (decision log, five rows).
# Proof:    every test is a TWO-MONTH case: month 1 is decided and its bill
#           issued, month 2 is prepared, and the ruled figure is asserted on
#           month 2 (and on month 1 where the ruling names one). Written red
#           first against 2.412.0; also run on PostgreSQL
#           (`--ds=config.settings.pgtest`).
# ───────────────────────────────────────────────────────
"""The five fixed-charge rulings, as the PO put them:

1. **Bill without it** — the service's BASE is billed this month, only the
   usage waits; the bill says the usage is billed next bill. Sep water base
   $8.00 billed; October's reading bills all the usage since the last read.
2. **Standing charges only → Waive** — a reason is required, the account is not
   billed, Sign off shows *Waived $26*, and NOTHING is carried forward: next
   month bills one base, normally.
3. **Held** — the next bill starts the day after the account's last bill
   (Sep 1 – Oct 31), bills all usage since then and ONE base ($26 once).
4. **Overlap** — the bill starts the day after the account's last bill: last
   bill to Sep 30, run Sep 15 – Oct 14 → Oct 1–14, base $8 × 14/30 = $3.73.
   "Bill as is" is not offered for an overlap.
5. **Plan instalment → Skip** — the plan is EXTENDED by one month through the
   payments module's own service: still $45 an instalment, total unchanged
   ($270), the last instalment one month later, never $90 in one month.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import decisions, runs
from apps.billing import models as billing_models

from tests.test_bbr_check_engine import a_cycle
from tests.test_us_bil_001_prepare import a_billed_unit, a_priced_plan, an_account
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_met_reads_helpers import (
    accept_warnings,
    commit_read,
    csv_body,
    seed_config,
    stage,
)

pytestmark = pytest.mark.django_db

AUGUST = (date(2026, 8, 1), date(2026, 8, 31))
SEPTEMBER = (date(2026, 9, 1), date(2026, 9, 30))
OCTOBER = (date(2026, 10, 1), date(2026, 10, 31))
CENT = Decimal("0.01")


# ── helpers ────────────────────────────────────────────────────────────────
def _setup(brazos, dana, *, account_no, asset_no, base, status_code="active"):
    from apps.assets import models as asset_models
    from apps.metering import models as metering_models
    from apps.rating import models as rating_models
    from apps.tenancy import models as tenancy_models

    seed_config()
    cycle = a_cycle(brazos)
    # `base_code=False`: this file mints its own base code below, at its own
    # figure, and a second one would be DEF-468's ambiguity (DEF-BIL-8671).
    plan = a_priced_plan(brazos, base_code=False)
    # The base comes from the service's BASE CHARGE CODE (DEF-BIL-7170); the
    # plan's own figure is retired and never read.
    from tests.base_code_naming import name_base_code

    name_base_code(  # DEF-RAT-9832 (PO 2026-10-06) — an unnamed schedule bills $0.00
        brazos,
        rating_models.Charge.objects.create(
            tenant=brazos,
            code="BASE-E",
            name="Electric base charge",
            charge_type="recurring",
            amount_rule="flat",
            amount=Decimal(base),
            service=tenancy_models.Service.objects.get(code="electric"),
            is_base=True,
        ),
    )
    unit = a_billed_unit(dana, brazos, cycle, plan, asset_no=asset_no, label="U", consumption=None)
    account = an_account(brazos, unit["id"], account_no, status_code=status_code)
    point = metering_models.ServicePoint.objects.get(tenant=brazos, unit_id=unit["id"])
    asset = asset_models.Asset.objects.get(tenant=brazos, service_point=point)
    return cycle, account, asset


def _read(dana, asset_no, day, value, month):
    from apps.metering import services as metering_services

    batch = stage(dana, csv_body(f"{asset_no},{day},{value},total,E,"), period_month=month)
    metering_services.validate_read_batch(dana, batch["id"])
    accept_warnings(dana, batch["id"])
    metering_services.commit_read_batch(dana, batch["id"], {"certified": True})


def _run(cycle, window, bill_date, label):
    run = runs.create_run(
        cycle_id=cycle.id,
        period_start=window[0],
        period_end=window[1],
        bill_date=bill_date,
        label=label,
    )
    prepared = runs.prepare_run(
        cycle_id=cycle.id, period_start=window[0], period_end=window[1], service_date=bill_date
    )
    return run, prepared


def _bill_and_issue(brazos, prepared, run, account):
    runs.calculate_run(decisions.apply_decisions(prepared, bill_run=run), bill_run=run)
    bill = billing_models.Invoice.objects.filter(
        tenant=brazos, account=account, bill_run=run
    ).first()
    if bill is not None:
        billing_models.Invoice.objects.filter(pk=bill.pk).update(
            status=billing_models.INVOICE_ISSUED
        )
        bill.refresh_from_db()
    return bill


def _lines(bill, kind):
    return [
        line.amount.quantize(CENT)
        for line in billing_models.InvoiceLine.objects.filter(invoice=bill, kind=kind)
    ]


def _electric_id():
    from apps.tenancy import selectors as tenancy_selectors

    return tenancy_selectors.service_ids_by_code()["electric"]


def _mine(prepared, account_no):
    return [d for d in prepared.ready if d.account_no == account_no]


def _base_of(data):
    priced = runs.price_account(data).priced
    return [line.amount.quantize(CENT) for line in priced.lines_of("base")]


# ── 1 · Bill without it → the base is billed, the usage waits ──────────────
# BULK-CHG-48
# BULK-CHG-27 (plan T8: the two-month tests)
def test_us_bil_037_case1__bill_without_it_bills_the_base_and_the_usage_next_bill(brazos, dana):
    with tenant_ctx(brazos):
        cycle, account, asset = _setup(
            brazos, dana, account_no="A-09101", asset_no="M-9101", base="8"
        )
        commit_read(
            dana,
            asset.id,
            day="2026-08-31",
            value="1000",
            prior_value="990",
            consumption="10.000000",
            unit="kWh",
        )
        september, prepared = _run(cycle, SEPTEMBER, date(2026, 10, 1), "September")
        decisions.record_decision(
            bill_run=september,
            account_id=str(account.id),
            case="missing_read",
            choice="bill_without_service",
            service_id=_electric_id(),
        )
        sep_bill = _bill_and_issue(brazos, prepared, september, account)
        assert sep_bill is not None, "the base is billed this month — the account is not dropped"
        assert _lines(sep_bill, "base") == [Decimal("8.00")]
        assert _lines(sep_bill, "usage") == []
        [service] = sep_bill.bill_payload["services"]
        assert service["absent_reason"] == "usage_billed_next_bill"
        assert service["read_id"] is None

        _read(dana, "M-9101", "2026-10-28", "1012", "2026-10-01")
        _october, prepared_oct = _run(cycle, OCTOBER, date(2026, 11, 1), "October")

    [data] = _mine(prepared_oct, "A-09101")
    usage = data.readings[0].consumption
    print(
        f"\nPROOF case 1: Sep base 8.00 + no usage; Oct usage {usage.amount} {usage.unit} + base {_base_of(data)}"
    )
    assert (usage.amount, usage.unit) == (Decimal("12"), "kWh"), "all usage since August's read"
    assert _base_of(data) == [Decimal("8.00")]


# BULK-CHG-48
def test_us_bil_037_case1__the_bill_says_the_usage_is_billed_next_bill():
    from apps.billing import documents
    from apps.billing.stages import measure_consumption

    assert measure_consumption.ABSENT_USAGE_NEXT_BILL == "usage_billed_next_bill"
    assert (
        measure_consumption.ABSENT_USAGE_NEXT_BILL in measure_consumption.EXEMPT_FROM_MISSING_READ
    )
    assert documents.SERVICE_ABSENCE_SENTENCES["usage_billed_next_bill"] == (
        "usage: no reading, billed next bill"
    )


# ── 2 · Standing charges only → Waive ──────────────────────────────────────
# BULK-CHG-49
def test_us_bil_037_case2__waive_needs_a_reason_bills_nothing_and_carries_nothing(brazos, dana):
    from apps.billing import release
    from apps.billing.exceptions import BillingRuleError

    with tenant_ctx(brazos):
        cycle, account, asset = _setup(
            brazos,
            dana,
            account_no="A-09102",
            asset_no="M-9102",
            base="26",
            status_code="vacation_hold",
        )
        assert decisions.CHOICES_BY_CASE["base_only_billing"] == ("include", "waive")
        commit_read(
            dana,
            asset.id,
            day="2026-09-28",
            value="1000",
            prior_value="1000",
            consumption="0.000000",
            unit="kWh",
        )
        september, prepared = _run(cycle, SEPTEMBER, date(2026, 10, 1), "September")
        assert _mine(prepared, "A-09102"), (prepared.blocked, prepared.decisions)
        with pytest.raises(BillingRuleError):
            decisions.record_decision(
                bill_run=september,
                account_id=str(account.id),
                case="base_only_billing",
                choice="waive",
            )
        decisions.record_decision(
            bill_run=september,
            account_id=str(account.id),
            case="base_only_billing",
            choice="waive",
            reason="Owner abroad; agreed by phone",
        )
        applied = decisions.apply_decisions(prepared, bill_run=september)
        assert _mine(applied, "A-09102") == []
        runs.calculate_run(applied, bill_run=september)
        assert not billing_models.Invoice.objects.filter(
            account=account, bill_run=september
        ).exists()
        # Nothing carried forward: no pending-queue row for a catch-up run.
        assert not billing_models.BillRunExclusion.objects.filter(
            account=account, bill_run=september
        ).exists()
        summary = release.summary_for(september)
        assert [(w["account_no"], w["amount"]) for w in summary.waived] == [
            ("A-09102", Decimal("26.00"))
        ]
        assert summary.as_payload()["waived_total"] == "26.000000"  # the column's scale
        # Record links (PO 2026-10-19): the waived account's number opens the
        # account on Sign off, so its id travels — the RIGHT id, not merely one.
        assert [w["account_id"] for w in summary.waived] == [str(account.pk)]
        assert [w["account_id"] for w in summary.as_payload()["waived"]] == [str(account.pk)]

        commit_read(
            dana,
            asset.id,
            day="2026-10-28",
            value="1000",
            prior_value="1000",
            consumption="0.000000",
            unit="kWh",
        )
        _october, prepared_oct = _run(cycle, OCTOBER, date(2026, 11, 1), "October")
        [data] = _mine(prepared_oct, "A-09102")
        assert data.period_start == OCTOBER[0], "next month bills normally, its own period"
    assert _base_of(data) == [Decimal("26.00")], "one base — the waived month is not made up"


# ── 3 · Held → next bill from the day after the last bill, ONE base ────────
# BULK-CHG-50
def test_us_bil_037_case3__a_held_account_next_bills_from_its_last_bill_with_one_base(brazos, dana):
    with tenant_ctx(brazos):
        cycle, account, asset = _setup(
            brazos, dana, account_no="A-09103", asset_no="M-9103", base="26"
        )
        commit_read(
            dana,
            asset.id,
            day="2026-07-31",
            value="990",
            prior_value="980",
            consumption="10.000000",
            unit="kWh",
        )
        _read(dana, "M-9103", "2026-08-31", "1000", "2026-08-01")
        august, prepared = _run(cycle, AUGUST, date(2026, 9, 1), "August")
        aug_bill = _bill_and_issue(brazos, prepared, august, account)
        assert aug_bill is not None and _lines(aug_bill, "base") == [Decimal("26.00")]

        september, prepared = _run(cycle, SEPTEMBER, date(2026, 10, 1), "September")
        decisions.record_decision(
            bill_run=september,
            account_id=str(account.id),
            case="missing_read",
            choice="hold",
            service_id=_electric_id(),
            reason="field visit",
        )
        assert _bill_and_issue(brazos, prepared, september, account) is None

        _read(dana, "M-9103", "2026-10-28", "1050", "2026-10-01")
        _october, prepared_oct = _run(cycle, OCTOBER, date(2026, 11, 1), "October")

    [data] = _mine(prepared_oct, "A-09103")
    usage = data.readings[0].consumption
    print(
        f"\nPROOF case 3: Oct bill {data.period_start}–{data.period_end}, usage {usage.amount}, base {_base_of(data)}"
    )
    assert (data.period_start, data.period_end) == (date(2026, 9, 1), date(2026, 10, 31))
    assert usage.amount == Decimal("50"), "all usage since the August bill's read"
    assert _base_of(data) == [Decimal("26.00")], "ONE base — the held month's base is not billed"
    assert "billing_continuity" not in [p.reason for p in prepared_oct.decisions]


# ── 4 · Overlap → from the day after the last bill, base prorated ──────────
# BULK-CHG-51
def test_us_bil_037_case4__an_overlap_bills_from_the_day_after_the_last_bill_prorated(brazos, dana):
    with tenant_ctx(brazos):
        cycle, account, asset = _setup(
            brazos, dana, account_no="A-09104", asset_no="M-9104", base="8"
        )
        commit_read(
            dana,
            asset.id,
            day="2026-08-31",
            value="990",
            prior_value="980",
            consumption="10.000000",
            unit="kWh",
        )
        _read(dana, "M-9104", "2026-09-28", "1000", "2026-09-01")
        september, prepared = _run(cycle, SEPTEMBER, date(2026, 10, 1), "September")
        assert _bill_and_issue(brazos, prepared, september, account) is not None

        _read(dana, "M-9104", "2026-10-12", "1014", "2026-10-01")
        window = (date(2026, 9, 15), date(2026, 10, 14))
        _mid, prepared_mid = _run(cycle, window, date(2026, 10, 15), "Mid")

    [data] = _mine(prepared_mid, "A-09104")
    print(
        f"\nPROOF case 4: bill {data.period_start}–{data.period_end}, {data.service_days}/{data.cycle_days} days, base {_base_of(data)}"
    )
    assert (data.period_start, data.period_end) == (date(2026, 10, 1), date(2026, 10, 14))
    assert (data.service_days, data.cycle_days) == (14, 30)
    assert _base_of(data) == [Decimal("3.73")], "$8 × 14/30"
    assert data.readings[0].consumption.amount == Decimal("14")
    assert "billing_continuity" not in [p.reason for p in prepared_mid.decisions]


# BULK-CHG-51
def test_us_bil_037_case4__bill_as_is_is_not_offered_for_an_overlap():
    assert decisions.CONTINUITY_CHOICES_BY_STATE["overlap"] == ("investigate",)
    assert "bill_as_is" in decisions.CONTINUITY_CHOICES_BY_STATE["gap"]


# ── 5 · Plan instalment → Skip extends the plan by one month ───────────────
# BULK-CHG-52
def test_us_bil_037_case5__skipping_an_instalment_extends_the_plan_by_one_month(brazos, dana):
    from apps.payments import plans as payment_plans
    from apps.payments.collections_models import PaymentPlan, PaymentPlanInstallment

    with tenant_ctx(brazos):
        cycle, account, asset = _setup(
            brazos, dana, account_no="A-09105", asset_no="M-9105", base="26"
        )
        plan = PaymentPlan.objects.create(
            tenant=brazos,
            account=account,
            total_amount=Decimal("270"),
            installment_count=6,
            status="active",
            proposed_on=date(2026, 8, 1),
            signed_on=date(2026, 8, 2),
        )
        for seq in range(1, 7):
            PaymentPlanInstallment.objects.create(
                tenant=brazos,
                plan=plan,
                seq=seq,
                due_date=date(2026, 7 + seq, 15) if seq <= 5 else date(2027, 1, 15),
                amount=Decimal("45"),
                # August's instalment is paid; September's is the one due.
                paid_posted_on=date(2026, 8, 14) if seq == 1 else None,
            )
        before_last = date(2027, 1, 15)
        september = runs.create_run(
            cycle_id=cycle.id,
            period_start=SEPTEMBER[0],
            period_end=SEPTEMBER[1],
            bill_date=date(2026, 10, 1),
            label="September",
        )
        from apps.billing import check_store, payments_seam

        check_store.check_run(september)
        [fact] = [
            f
            for f in check_store.account_findings(september, str(account.id))["findings"]
            if f["code"] == "plan_instalment_due"
        ]
        assert (fact["params"]["seq"], fact["params"]["due_on"]) == (2, "2026-09-15")
        decisions.record_decision(
            bill_run=september,
            account_id=str(account.id),
            case="plan_instalment_due",
            choice="skip",
            reason="hardship",
        )
        outcome = payments_seam.extend_plans_for_skips(
            bill_run=september, account_id=str(account.id)
        )
        again = payments_seam.extend_plans_for_skips(bill_run=september, account_id=str(account.id))
        rows = list(PaymentPlanInstallment.objects.filter(plan=plan).order_by("seq"))

    dues = [r.due_date for r in rows]
    print(
        f"\nPROOF case 5: instalments {[str(r.amount) for r in rows]} due {dues}; ends {outcome['ends_on']}"
    )
    assert outcome["extended"] is True and again["extended"] is False, "idempotent per skip"
    assert [r.amount for r in rows] == [Decimal("45")] * 6
    assert sum(r.amount for r in rows) == Decimal("270"), "total unchanged"
    assert dues[0] == date(2026, 8, 15), "a paid-or-earlier instalment does not move"
    assert date(2026, 9, 15) not in dues, "the skipped month has no instalment"
    assert dues[-1] == date(2027, 2, 15) and outcome["ends_on"] == "2027-02-15"
    assert dues[-1] > before_last
    per_month: dict[tuple[int, int], Decimal] = {}
    for row in rows:
        key = (row.due_date.year, row.due_date.month)
        per_month[key] = per_month.get(key, Decimal("0")) + row.amount
    assert max(per_month.values()) == Decimal("45"), "never $90 in one month"
    assert payment_plans.extend_plan_one_month.__module__ == "apps.payments.plans"


# BULK-CHG-52
def test_us_bil_037_case5__issue_extends_the_plan_through_the_seam():
    """Wiring (hard-won law 2): issue calls the payments seam for a skip."""
    import inspect

    from apps.billing import issue

    assert "payments_seam.extend_plans_for_skips(" in inspect.getsource(issue.issue_invoice)


# ── §3 · "Paid after cut-off → apply to this bill" is never counted twice ──
# BULK-CHG-38 · BULK-CHG-37
def test_us_bil_037_paid_after_cutoff_apply_to_this_bill_is_not_counted_twice(brazos, dana):
    """*Apply to this bill* (DEF-BIL-8243, built 2026-09-30): the account is
    BILLED, and the $120.00 posted Oct 1 is counted ONCE — by payments, which
    posted it and allocated it against August's bill. September's bill adds no
    line for it; its balance-forward block (stamped at issue from payments'
    allocations, BR-BIL-035) and Sign off's *payments applied* read it from
    that one allocation. Until 2026-09-30 this choice HELD the account.
    *Apply next bill* bills as gathered too."""
    from datetime import datetime, timezone

    from apps.billing import customers_seam, issue, payments_seam, signoff
    from apps.payments import models as payment_models

    with tenant_ctx(brazos):
        cycle, account, asset = _setup(
            brazos, dana, account_no="A-09106", asset_no="M-9106", base="8"
        )
        august = runs.create_run(
            cycle_id=cycle.id,
            period_start=AUGUST[0],
            period_end=AUGUST[1],
            bill_date=date(2026, 9, 1),
            label="August",
        )
        august_bill = billing_models.Invoice.objects.create(
            tenant=brazos,
            account=account,
            bill_run=august,
            service_date=AUGUST[1],
            period_start=AUGUST[0],
            period_end=AUGUST[1],
            status=billing_models.INVOICE_ISSUED,
            currency="USD",
            subtotal=Decimal("200"),
            invoice_no="BL-2609-009106",
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
            status=payment_models.PAYMENT_CLEARED,
            posted_at=datetime(2026, 10, 1, 15, 0, tzinfo=timezone.utc),
        )
        payment_models.Allocation.objects.create(
            tenant=brazos, payment=payment, invoice=august_bill, amount=Decimal("120")
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
        september, prepared = _run(cycle, SEPTEMBER, date(2026, 10, 1), "September")
        decisions.record_decision(
            bill_run=september,
            account_id=str(account.id),
            case="paid_after_cutoff",
            choice="apply_this_bill",
        )
        runs.calculate_run(decisions.apply_decisions(prepared, bill_run=september), bill_run=september)
        bill = billing_models.Invoice.objects.get(account=account, bill_run=september)
        kinds = set(billing_models.InvoiceLine.objects.filter(invoice=bill).values_list("kind", flat=True))
        position = payments_seam.prior_position_for_account(
            account.id,
            totals_by_invoice_id=issue._prior_bill_totals(bill),
            opening=customers_seam.opening_position_for_account(account.id),
        )
        summary = signoff.sign_off_summary(september)
        queued = billing_models.BillRunExclusion.objects.filter(
            account=account, bill_run=september
        ).exists()

    print(
        f"\nPROOF apply this bill: billed {bill.total}; previous {position.previous_balance} − "
        f"paid {position.payments_credits} (once, payments' allocation)"
    )
    assert not queued, "billed, not held"
    assert kinds <= {"usage", "base", "minimum"}, "no line on the bill for the payment"
    assert position.previous_balance == Decimal("200") and position.payments_credits == Decimal("120")
    money = summary["payments_and_balances"]
    assert Decimal(money["payments_and_credits_applied"]) == Decimal("120")
    assert money["accounts_with_payments_applied"] == 1
    assert money["reconciles"] is True
