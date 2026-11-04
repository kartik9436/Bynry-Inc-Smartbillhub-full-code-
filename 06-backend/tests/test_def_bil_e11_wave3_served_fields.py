# ── Trace ──────────────────────────────────────────────
# Journey:  J72 § E11 wave 3 — the last eight bulk-run states that differed from
#           the D1 drawings, each waiting on a field the server did not send
# Defects:  DEF-BIL-8691 (Scope: "Cycle is monthly.") · DEF-BIL-8701 (Check:
#           "Water · W-10442") · DEF-BIL-8685 (Sent: "Meter reads: Locked") ·
#           DEF-BIL-8682 (Sign off: payments apart from credits)
# Drawing:  05-prototype/bulk-bill-run-2026-09-30/04, 11–14, 25, 28, 35
# ───────────────────────────────────────────────────────
"""The fields the bulk run's last drawn differences waited on, served.

Each test was written to fail on 2.422.0, the build that had the difference.
"""

from __future__ import annotations

import pytest

from tests.test_bulk_run_scope import (
    a_cycle,
    a_june_run_behind,
    a_published_template,
    check,
    warning,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


# ── DEF-BIL-8691 — the cycle's frequency, as the business word ──────────────


@pytest.mark.parametrize(
    ("stored", "served"),
    [("Monthly", "Monthly"), ("monthly", "Monthly"), ("bi_monthly", "Bimonthly")],
)
def test_def_bil_8691_period_length_serves_the_cycles_frequency_word(brazos, stored, served):
    """D1 04 writes *"45 days. Cycle is monthly."* — the screen translates the
    word, so the server must send ONE spelling of it, whatever a shipped row
    still holds (`metering.schedule.business_frequency`)."""
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos, frequency=stored)
        a_june_run_behind(brazos, cycle)
        result = check(
            cycle, a_published_template(), period_end="2026-08-14", bill_date="2026-09-01"
        )
    problem = warning(result, "period_length")
    assert problem.params["days"] == 45
    assert problem.params["frequency"] == served


# ── DEF-BIL-8701 — the meter NUMBER on a Check row ───────────────────────────


def test_def_bil_8701_the_seam_names_each_units_meter_by_its_number(brazos, dana):
    from apps.billing import metering_seam
    from tests.test_bulk_run_scope import a_billed_unit, a_priced_plan

    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit_a = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-8701", label="Unit A")
        unit_b = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-8702", label="Unit B")
        found = metering_seam.meter_numbers_for_units([unit_a["id"], unit_b["id"]])
    assert found == {
        str(unit_a["id"]): {"electric": ["M-8701"]},
        str(unit_b["id"]): {"electric": ["M-8702"]},
    }


def test_def_bil_8701_a_check_row_carries_its_meter_number(brazos, dana, monkeypatch):
    from apps.assets import models as asset_models
    from apps.billing import check_store
    from tests.test_bbr_check_engine import reads_without_unit, three_accounts
    from tests.test_bbr_check_store import a_run

    with tenant_ctx(brazos):
        cycle, _plan, accounts = three_accounts(brazos, dana)
        unit_id = accounts["A-00102"].unit_id
        reads_without_unit(monkeypatch, unit_id, meter_unit="kWh")
        run = a_run(cycle)
        check_store.check_run(run)
        page = check_store.tag_accounts(run, "reading_has_no_unit", {})
        meter = (
            asset_models.Asset.objects.filter(tenant=brazos, service_point__unit_id=unit_id)
            .values_list("asset_no", flat=True)
            .get()
        )
    row = page["results"][0]
    assert row["service_code"] == "electric"
    assert row["meters"] == [meter]


# ── DEF-BIL-8685 — the BILLED lock across a sent run ─────────────────────────


def _reads_of(tenant, unit_id):
    from apps.metering import models as metering_models

    return list(
        metering_models.MeterRead.objects.filter(
            tenant=tenant, asset__service_point__unit_id=unit_id
        )
        .order_by("read_at", "id")
        .values_list("id", flat=True)
    )


def test_def_bil_8685_meter_reads_answer_how_many_of_a_runs_reads_are_locked(brazos, dana):
    from apps.billing import metering_seam
    from apps.metering import models as metering_models
    from apps.metering import selectors as metering_selectors
    from tests.test_bulk_run_scope import a_billed_unit, a_priced_plan

    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(
            dana, brazos, cycle, plan, asset_no="M-8851", label="Unit A", read_last_month=True
        )
        may, june = _reads_of(brazos, unit["id"])
        bills = [{"services": [{"read_id": str(may)}]}, {"services": [{"read_id": str(june)}]}]
        lock = metering_seam.read_lock_for_bills(bills)
        assert lock.as_dict() == {"state": "open", "reads": 2, "locked": 0}
        metering_models.MeterRead.objects.filter(id=may).update(lifecycle="billed")
        lock = metering_seam.read_lock_for_bills(bills)
        assert lock.as_dict() == {"state": "partly", "reads": 2, "locked": 1}
        metering_models.MeterRead.objects.filter(id=june).update(lifecycle="billed")
        lock = metering_seam.read_lock_for_bills(bills)
        assert lock.as_dict() == {"state": "locked", "reads": 2, "locked": 2}
        assert (
            metering_seam.read_lock_for_bills([{"services": [{"read_id": None}]}]).state == "none"
        )
        counts = metering_selectors.read_lock_counts([str(june), "not-a-uuid"])
    assert counts == {"reads": 1, "locked": 1}


def test_def_bil_8685_a_sent_runs_detail_says_its_meter_reads_are_locked(brazos, dana):
    from datetime import UTC, date, datetime
    from decimal import Decimal

    from apps.billing import models as billing_models
    from apps.billing import selectors
    from apps.metering import models as metering_models
    from tests.test_bulk_run_scope import a_billed_unit, a_priced_plan
    from tests.test_us_bil_001_prepare import an_account

    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        june_run = a_june_run_behind(brazos, cycle)
        unit = a_billed_unit(
            dana, brazos, cycle, a_priced_plan(brazos), asset_no="M-8852", label="Unit A"
        )
        (read_id,) = _reads_of(brazos, unit["id"])
        account = an_account(brazos, unit["id"], "A-88520")
        billing_models.Invoice.objects.create(
            tenant=brazos,
            account=account,
            bill_run=june_run,
            invoice_no="BL-2606-885200",
            bill_type="cycle",
            status=billing_models.INVOICE_ISSUED,
            service_date=date(2026, 6, 30),
            period_start=date(2026, 6, 1),
            period_end=date(2026, 6, 30),
            due_date=date(2026, 7, 21),
            issued_at=datetime(2026, 7, 1, 9, 0, tzinfo=UTC),
            subtotal=Decimal("10.00"),
            tax_total=Decimal("0.00"),
            total=Decimal("10.00"),
            currency="USD",
            template_version=1,
            payload_version=1,
            bill_payload={"services": [{"code": "electric", "read_id": str(read_id)}]},
        )
        # DEF-BIL-8809 — on its own read (`GET …/read-lock`) since it left the
        # run read, which every screen of the bulk run page waits for.
        assert "meter_reads" not in selectors.run_detail_dict(june_run)
        assert selectors.run_read_lock_dict(june_run)["meter_reads"] is None  # not sent yet
        billing_models.BillRunRelease.objects.create(
            tenant=brazos,
            bill_run=june_run,
            summary={},
            account_count=1,
            bill_count=1,
            total_amount=Decimal("10.0000"),
            currency="USD",
            confirmed_by=getattr(dana, "user", dana),
            confirmed_at=datetime(2026, 7, 1, 8, 0, tzinfo=UTC),
            released_at=datetime(2026, 7, 1, 9, 0, tzinfo=UTC),
        )
        assert selectors.run_read_lock_dict(june_run)["meter_reads"]["state"] == "open"
        metering_models.MeterRead.objects.filter(id=read_id).update(lifecycle="billed")
        detail = selectors.run_read_lock_dict(june_run)
    assert detail["meter_reads"] == {"state": "locked", "reads": 1, "locked": 1}


# ── DEF-BIL-8682 — Sign off parts payments from credits, on ruling 6's read ──


def test_def_bil_8682_sign_off_reads_the_bills_window_and_parts_payments_from_credits(brazos, dana):
    """PO ruling 6 (OQ-217): $34.00 − paid $120.00 + $37.25 = $48.75 credit.
    Here the account also had a $10.00 goodwill credit and $5.00 refunded, so
    the bill will print 34.00 − 125.00 + 37.25 = −53.75; Sign off must say the
    same, and part the 125.00 as payments 115.00 (120 − the 5 refunded) and
    credits 10.00 — payments' own type column, the two adding back exactly."""
    from datetime import UTC, date, datetime
    from decimal import Decimal

    from apps.billing import issue, signoff
    from apps.billing import models as billing_models
    from apps.payments import models as payment_models
    from tests.test_po_20261001_overpaid_bill_reads_whole_account import _bill, _pay, _setup

    with tenant_ctx(brazos):
        cycle, account, _asset = _setup(
            brazos, dana, account_no="A-86820", asset_no="M-8682", base="8"
        )
        september = _bill(
            brazos,
            account,
            no="BL-2609-868201",
            total="34.00",
            start=date(2026, 9, 1),
            end=date(2026, 9, 30),
            issued_at=datetime(2026, 10, 1, 9, 0, tzinfo=UTC),
        )
        _pay(
            brazos,
            account,
            "120.00",
            datetime(2026, 10, 5, 12, 0, tzinfo=UTC),
            against=september,
            applied="34.00",
        )
        payment_models.Payment.objects.create(
            tenant=brazos,
            account=account,
            amount=Decimal("10.00"),
            currency="USD",
            status=payment_models.PAYMENT_CLEARED,
            posted_at=datetime(2026, 10, 7, 12, 0, tzinfo=UTC),
            type=payment_models.PAYMENT_TYPE_CREDIT,
        )
        payment_models.Refund.objects.create(
            tenant=brazos,
            account=account,
            amount=Decimal("5.00"),
            currency="USD",
            status=payment_models.REFUND_ISSUED,
            issued_at=datetime(2026, 10, 8, 12, 0, tzinfo=UTC),
        )
        run = billing_models.BillRun.objects.create(
            tenant=brazos,
            cycle=cycle,
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 31),
            status="draft",
            idempotency_key="def-bil-8682",
        )
        october = _bill(
            brazos,
            account,
            no="BL-2610-868201",
            total="37.25",
            start=date(2026, 10, 1),
            end=date(2026, 10, 31),
        )
        october.bill_run = run
        october.save(update_fields=["bill_run"])
        shown = signoff._payments_and_balances(run, [october])
        block = issue._stamp_balance_forward(october, currency="USD", due_date=date(2026, 11, 22))

    def money(value):
        return Decimal(value).quantize(Decimal("0.01"))

    assert (
        money(shown["payments_and_credits_applied"])
        == money(block["payments_credits"])
        == Decimal("125.00")
    )
    assert money(shown["previous_balance"]) == money(block["previous_balance"])
    assert money(shown["amount_due"]) == money(block["total_due"]) == Decimal("-53.75")
    assert money(shown["payments_applied"]) == Decimal("115.00")
    assert money(shown["credits_applied"]) == Decimal("10.00")
    assert (shown["payments_count"], shown["credits_count"]) == (1, 1)
    assert shown["reconciles"] is True
