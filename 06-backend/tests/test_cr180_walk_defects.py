# ── Trace ──────────────────────────────────────────────
# Change:   CR-180-BRC10 (Fix a bill, revamped) — defects found by the
#           end-to-end walk J-FIX-TWENTY on 2026-10-12, each RED first.
# Journey:  08-qa/01-e2e/journeys/J-FIX-TWENTY-the-fix-a-bill-scenario-suite.md
# ───────────────────────────────────────────────────────
"""Defects the J-FIX-TWENTY walk found, pinned so they cannot come back.

DEF-BIL-10077 — a corrected bill printed the replaced bill's amount again in
its *Total due*. Walked on BL-2610-000053 ($198.90, unpaid) corrected to
$183.60: the new bill printed *Previous balance 414.12 · Payments 215.22 ·
Total due 382.50* where the customer owes $183.60, because the rebill was
issued while the original still read `issued` and so counted as an open bill.
On the test world: July $373.00 unpaid, corrected to $213.00 → Total due
**213.00**; July $373.00 paid in full, corrected to $213.00 → Total due
**−160.00** (a $160.00 credit), never 213.00.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.billing import models
from apps.billing.correction_models import CorrectionCase

from tests.test_cr180_fix_a_bill_revamp import (  # noqa: F401 — the autouse template pin
    _send,
    CORRECTED_JULY,
    ORIGINAL_JULY,
    _approve_and_issue,
    _july_world,
    _one_customer,
    _pay,
    _sent_case,
    _the_rebill_template,
    _wrong_read,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _corrected_bill(tenant, actor, world):
    preview, sent = _sent_case(tenant, actor, _one_customer(world), [_wrong_read(world)])
    done = _approve_and_issue(tenant, actor, sent["id"], preview["preview_hash"])
    assert done.status_code == 200, done.data
    with tenant_ctx(tenant):
        return models.Invoice.objects.get(corrects_invoice_id=world.invoice.pk)


def test_def_bil_10077_an_unpaid_bill_corrected_prints_only_the_new_amount_due(brazos, dana):
    with tenant_ctx(brazos):
        world = _july_world(brazos, dana)
    new = _corrected_bill(brazos, dana, world)
    block = new.bill_payload["balance_forward"]
    assert new.total == CORRECTED_JULY
    assert Decimal(block["total_due"]) == CORRECTED_JULY, (
        f"the customer owes only the corrected bill, 213.00; the page printed {block}"
    )


def test_def_bil_10077_a_paid_bill_corrected_down_prints_the_credit(brazos, dana):
    with tenant_ctx(brazos):
        world = _july_world(brazos, dana)
        _pay(dana, world.account, ORIGINAL_JULY)
    new = _corrected_bill(brazos, dana, world)
    block = new.bill_payload["balance_forward"]
    assert Decimal(block["total_due"]) == CORRECTED_JULY - ORIGINAL_JULY, (
        f"373.00 paid against a bill now worth 213.00 leaves a 160.00 credit; the page printed {block}"
    )


def test_def_bil_10080_the_corrected_reading_names_the_bill_never_a_database_id(brazos, dana):
    """B14 rule 31: the reason Meter Reads prints is *Fix a bill — <bill no>*."""
    import re

    from apps.metering import models as metering_models

    with tenant_ctx(brazos):
        world = _july_world(brazos, dana)
    _corrected_bill(brazos, dana, world)
    uuid = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
    with tenant_ctx(brazos):
        correction = metering_models.ReadCorrection.objects.get(invoice_id=world.invoice.pk)
        head = metering_models.MeterRead.objects.get(id=correction.superseding_read_id)
        for words in (correction.reason, head.supersede_reason):
            assert not uuid.search(words or ""), words
            assert world.invoice.invoice_no in words, words


def test_def_bil_10081_a_missed_charge_is_issued_not_refused_at_approve(brazos, dana):
    """RECONNECT $15.00 × 2 on July: previewed at $403.00, and the new bill
    ISSUES at $403.00 — the added line carries its counting unit (rule 3)."""
    from apps.rating import models as rating_models
    from apps.tenancy import models as tenancy_models

    from tests.test_cr180_fix_a_bill_revamp import _a_revenue_account

    with tenant_ctx(brazos):
        world = _july_world(brazos, dana)
        rating_models.Charge.objects.create(
            tenant=brazos,
            code="RECONNECT",
            name="Reconnection fee",
            charge_type="one_time",
            amount_rule="flat",
            amount=Decimal("15.00"),
            service=tenancy_models.Service.objects.get(code="water"),
            gl_account_id=_a_revenue_account(brazos),
        )
    items = [{"reason": "missed_charge", "item": "RECONNECT", "value": "2"}]
    preview, sent = _sent_case(brazos, dana, _one_customer(world), items)
    done = _approve_and_issue(brazos, dana, sent["id"], preview["preview_hash"])
    assert done.status_code == 200, done.data
    assert done.data["result"]["failed"] == [], done.data["result"]
    with tenant_ctx(brazos):
        new = models.Invoice.objects.get(corrects_invoice_id=world.invoice.pk)
        assert new.total == ORIGINAL_JULY + Decimal("30.00")
        line = new.lines.get(kind="fee")
        assert (line.quantity, line.unit) == (Decimal("2"), "unit")


def test_def_bil_10083_a_missed_charge_with_no_gl_account_is_refused_at_preview(brazos, dana):
    """A code with no GL account can never issue (BR-BIL-010), so the preview
    refuses it by name instead of letting it fail after approval."""
    from apps.rating import models as rating_models
    from apps.tenancy import models as tenancy_models

    from tests.test_cr180_fix_a_bill_revamp import _preview

    with tenant_ctx(brazos):
        world = _july_world(brazos, dana)
        rating_models.Charge.objects.create(
            tenant=brazos,
            code="NOGL",
            name="Meter test on request",
            charge_type="one_time",
            amount_rule="flat",
            amount=Decimal("60.00"),
            service=tenancy_models.Service.objects.get(code="water"),
            gl_account_id=None,
        )
    answer = _preview(
        brazos,
        dana,
        _one_customer(world),
        [{"reason": "missed_charge", "item": "NOGL", "value": "1"}],
    )
    assert answer.status_code == 422, answer.data
    assert answer.data["message_key"] == "billing.correction.itemInvalid"
    assert "GL account" in answer.data["params"]["detail"]


def test_def_bil_10084_for_finance_accounts_add_up_to_the_net_when_a_charge_is_added(brazos, dana):
    """RECONNECT $15.00 × 2 added: the net is +30.00 and the account table must
    carry the charge code's own account at +30.00 — every row sums to the net."""
    from apps.rating import models as rating_models
    from apps.tenancy import models as tenancy_models

    from tests.test_cr180_fix_a_bill_revamp import _a_revenue_account, _preview

    with tenant_ctx(brazos):
        world = _july_world(brazos, dana)
        gl = _a_revenue_account(brazos)
        rating_models.Charge.objects.create(
            tenant=brazos,
            code="RECONNECT",
            name="Reconnection fee",
            charge_type="one_time",
            amount_rule="flat",
            amount=Decimal("15.00"),
            service=tenancy_models.Service.objects.get(code="water"),
            gl_account_id=gl,
        )
    answer = _preview(
        brazos,
        dana,
        _one_customer(world),
        [{"reason": "missed_charge", "item": "RECONNECT", "value": "2"}],
    )
    assert answer.status_code == 200, answer.data
    finance = answer.data["finance"]
    assert Decimal(finance["net"]) == Decimal("30.00")
    total = sum(Decimal(row["change"]) for row in finance["accounts"])
    assert total == Decimal(finance["net"]), finance["accounts"]


def test_def_bil_10085_for_finance_shows_the_goodwill_entry(brazos, dana):
    """A $10.00 goodwill-only case posts DR write-off / CR customer credit; the
    Check step's finance entries carry it, not *0.00 · 0.00 · net 0.00*."""
    from tests.test_cr180_fix_a_bill_revamp import _preview

    with tenant_ctx(brazos):
        world = _july_world(brazos, dana)
    answer = _preview(
        brazos,
        dana,
        _one_customer(world),
        [{"reason": "goodwill", "item": "credit", "value": "10"}],
    )
    assert answer.status_code == 200, answer.data
    entries = {row["entry"]: Decimal(row["amount"]) for row in answer.data["finance"]["entries"]}
    assert entries.get("goodwill") == Decimal("10.00"), answer.data["finance"]


def test_def_bil_10087_carried_credit_is_counted_once_across_the_bills_of_one_account(brazos, dana):
    """June and July $373.00 each, paid $846.00 (both + $100.00 carried credit);
    RECONNECT $15.00 × 4 added to both → each new bill $433.00. One pool:
    June takes 433.00 of 473.00, leaving 40.00; July takes 413.00 of 413.00 and
    still owes **20.00**. The preview must promise exactly what approval does."""
    from apps.payments import models as payment_models
    from apps.rating import models as rating_models
    from apps.tenancy import models as tenancy_models

    from tests.test_cr180_fix_a_bill_revamp import _a_revenue_account, _preview, _two_month_world

    with tenant_ctx(brazos):
        world = _two_month_world(brazos, dana)
        rating_models.Charge.objects.create(
            tenant=brazos,
            code="RECONNECT",
            name="Reconnection fee",
            charge_type="one_time",
            amount_rule="flat",
            amount=Decimal("15.00"),
            service=tenancy_models.Service.objects.get(code="water"),
            gl_account_id=_a_revenue_account(brazos),
        )
        _pay(dana, world.account, world.june.total + world.july.total + Decimal("100.00"))
    scope = _one_customer(world, world.june, world.july)
    items = [{"reason": "missed_charge", "item": "RECONNECT", "value": "4"}]
    preview = _preview(brazos, dana, scope, items)
    assert preview.status_code == 200, preview.data
    promised = {b["invoice_no"]: Decimal(b["still_owed"]) for b in preview.data["bills"]}
    sent = _send(brazos, dana, scope, items, preview.data["preview_hash"])
    assert sent.status_code == 201, sent.data
    done = _approve_and_issue(brazos, dana, sent.data["id"], preview.data["preview_hash"])
    assert done.status_code == 200, done.data
    with tenant_ctx(brazos):
        actual = {}
        for old in (world.june, world.july):
            new = models.Invoice.objects.get(corrects_invoice_id=old.pk)
            met = sum(
                (a.amount for a in payment_models.Allocation.objects.filter(invoice_id=new.pk)),
                Decimal("0"),
            )
            actual[old.invoice_no] = new.total - met
    assert sum(promised.values()) == sum(actual.values()) == Decimal("20.00"), (promised, actual)
    assert promised == actual, (promised, actual)


def test_def_bil_10089_a_closed_accounts_issued_bill_can_be_corrected(brazos, dana):
    """July $373.00 issued; the account is then CLOSED. A missed RECONNECT
    $15.00 × 1 is previewed at $388.00 and issued — the balance stays on the
    closed account (PO 2026-10-12), never refused as 'terminal'."""
    from apps.customers import models as customer_models
    from apps.rating import models as rating_models
    from apps.tenancy import models as tenancy_models

    from tests.test_cr180_fix_a_bill_revamp import _a_revenue_account

    with tenant_ctx(brazos):
        world = _july_world(brazos, dana)
        rating_models.Charge.objects.create(
            tenant=brazos,
            code="RECONNECT",
            name="Reconnection fee",
            charge_type="one_time",
            amount_rule="flat",
            amount=Decimal("15.00"),
            service=tenancy_models.Service.objects.get(code="water"),
            gl_account_id=_a_revenue_account(brazos),
        )
        closed = customer_models.AccountStatus.objects.filter(
            tenant=brazos, code="closed"
        ).first()
        assert closed is not None, "the tenant seeds a closed status"
        customer_models.Account.objects.filter(pk=world.account.pk).update(status=closed)
    items = [{"reason": "missed_charge", "item": "RECONNECT", "value": "1"}]
    preview, sent = _sent_case(brazos, dana, _one_customer(world), items)
    assert Decimal(preview["bills"][0]["becomes_total"]) == ORIGINAL_JULY + Decimal("15.00")
    done = _approve_and_issue(brazos, dana, sent["id"], preview["preview_hash"])
    assert done.status_code == 200, done.data
    assert done.data["result"]["failed"] == [], done.data["result"]


def test_def_bil_10089_a_closed_accounts_bill_across_a_price_change_is_corrected(brazos, dana):
    """The same carve-out on a bill cut at a mid-month price change (each part
    is gathered on its own): $21.00, read 1010 → 1020 re-prices to $42.00."""
    from datetime import date
    from types import SimpleNamespace

    from apps.billing import models as billing_models
    from apps.customers import models as customer_models
    from apps.metering import models as metering_models

    from tests.test_br_rat_114_midperiod_split import (
        PERIOD_END,
        PERIOD_START,
        a_cycled_water_unit,
        a_repricing_water_plan,
    )
    from tests.test_br_rat_114_midperiod_split import a_cycle as r114_cycle
    from tests.test_cr180_fix_a_bill_revamp import _issue
    from tests.test_us_bil_001_prepare import an_account as w3_account
    from tests.test_us_bil_005_release_gate import a_release

    with tenant_ctx(brazos):
        plan, _versions = a_repricing_water_plan(brazos)
        cycle = r114_cycle(brazos, "FIX-S13")
        unit = a_cycled_water_unit(
            dana, brazos, cycle, plan, asset_no="W-18913",
            reads=[(date(2026, 5, 31), "0"), (PERIOD_END, "10.000000")],
        )
        account = w3_account(brazos, unit["id"], "FIX-S13")
        run = billing_models.BillRun.objects.create(
            tenant=brazos, cycle=cycle, period_start=PERIOD_START, period_end=PERIOD_END,
            bill_date=date(2026, 7, 1), idempotency_key="fix|s13",
        )
        a_release(brazos, run, dana)
        invoice = _issue(dana, account, run, start=PERIOD_START, end=PERIOD_END)
        asset_id = str(
            metering_models.MeterRead.objects.filter(tenant=brazos).latest("read_at").asset_id
        )
        closed = customer_models.AccountStatus.objects.get(tenant=brazos, code="closed")
        customer_models.Account.objects.filter(pk=account.pk).update(status=closed)
    world = SimpleNamespace(account=account, invoice=invoice)
    items = [{"reason": "wrong_read", "item": asset_id, "value": "1020"}]
    preview, sent = _sent_case(brazos, dana, _one_customer(world), items)
    assert Decimal(preview["bills"][0]["becomes_total"]) == Decimal("42.00")
    done = _approve_and_issue(brazos, dana, sent["id"], preview["preview_hash"])
    assert done.status_code == 200, done.data
    assert done.data["result"]["failed"] == [], done.data["result"]


def test_def_bil_10090_the_run_list_filters_by_bill_type(brazos, dana):
    """`GET /billing/runs?f.bill_type=cycle` answers the cycle's run and never a
    correction's one-bill rebill run."""
    from apps.billing import selectors

    with tenant_ctx(brazos):
        world = _july_world(brazos, dana)
    _corrected_bill(brazos, dana, world)
    with tenant_ctx(brazos):
        every = selectors.bill_runs_page(per=50)
        cycle = selectors.bill_runs_page(per=50, bill_type="cycle")
        assert {row["bill_type"] for row in every["rows"]} == {"cycle", "rebill"}
        assert {row["bill_type"] for row in cycle["rows"]} == {"cycle"}
        assert "bill_type" in selectors.BILL_RUN_LIST_FILTERS


def test_def_bil_10096_one_unpriceable_bill_is_left_out_of_a_bulk_case(brazos, dana, monkeypatch):
    """Three July bills in one run; the second cannot be priced. The bulk
    preview answers the other two and names the third as left out — never a
    refusal of the whole case."""
    from apps.billing import correction_items
    from apps.billing.exceptions import BillingRuleError

    from tests.test_cr180_fix_a_bill_revamp import _bulk_preview as _preview

    with tenant_ctx(brazos):
        first = _july_world(brazos, dana, n=31)
        second = _july_world(brazos, dana, n=32, plan=first.plan, run=first.run)
        third = _july_world(brazos, dana, n=33, plan=first.plan, run=first.run)
        schedule = str(first.invoice.lines.filter(kind="usage").first().tariff_version.tariff_id)
    real = correction_items.prepare_bill

    def _cannot_price_the_second(invoice, pins, **kwargs):
        if str(invoice.pk) == str(second.invoice.pk):
            raise BillingRuleError("water still has no usable read and no decision")
        return real(invoice, pins, **kwargs)

    monkeypatch.setattr(correction_items, "prepare_bill", _cannot_price_the_second)
    scope = {"kind": "run", "bill_run_id": str(first.run.pk)}
    answer = _preview(brazos, dana, scope, [{"reason": "wrong_rate", "item": schedule}])
    assert answer.status_code == 200, answer.data
    assert answer.data["count"] == 2
    assert {b["invoice_no"] for b in answer.data["bills"]} == {
        first.invoice.invoice_no,
        third.invoice.invoice_no,
    }
    assert [(p["code"], p["detail"]) for p in answer.data["problems"]] == [
        ("cannot_price", second.invoice.invoice_no)
    ]


def test_def_bil_10098_a_bill_cut_at_a_price_change_saves_no_estimate_over_its_real_reading(brazos, dana):
    """BR-RAT-114's mid-month world: 10 kgal measured, the bill cut into two
    parts at the price change. Issuing it must save NO estimated reading — the
    parts are shares of the real one — and correcting it again re-prices the
    same 10 kgal ($21.00 → $21.00 with goodwill only), never one part's share."""
    from datetime import date

    from apps.billing import models as billing_models
    from apps.metering import models as metering_models

    from tests.test_br_rat_114_midperiod_split import (
        PERIOD_END,
        PERIOD_START,
        a_cycled_water_unit,
        a_repricing_water_plan,
    )
    from tests.test_br_rat_114_midperiod_split import a_cycle as r114_cycle
    from tests.test_cr180_fix_a_bill_revamp import _issue
    from tests.test_us_bil_001_prepare import an_account as w3_account
    from tests.test_us_bil_005_release_gate import a_release

    with tenant_ctx(brazos):
        plan, _versions = a_repricing_water_plan(brazos)
        cycle = r114_cycle(brazos, "FIX-EST")
        unit = a_cycled_water_unit(
            dana, brazos, cycle, plan, asset_no="W-18998",
            reads=[(date(2026, 5, 31), "0"), (PERIOD_END, "10.000000")],
        )
        account = w3_account(brazos, unit["id"], "FIX-EST")
        run = billing_models.BillRun.objects.create(
            tenant=brazos, cycle=cycle, period_start=PERIOD_START, period_end=PERIOD_END,
            bill_date=date(2026, 7, 1), idempotency_key="fix|est",
        )
        a_release(brazos, run, dana)
        invoice = _issue(dana, account, run, start=PERIOD_START, end=PERIOD_END)
        assert invoice.total == Decimal("21.00")
        estimated = metering_models.MeterRead.objects.filter(
            tenant=brazos, account_id=account.pk, source="estimated"
        ).count()
        assert estimated == 0, "a split part's share of a real reading is not an estimate"


def test_def_bil_10099_figures_moved_after_send_refuse_the_approval(brazos, dana, monkeypatch):
    """Sent at $213.00; a price moves before approval, so the bill would now be
    $214.00. The approval is REFUSED with *Figures changed. Check again.* —
    the case stays waiting and nothing is written."""
    from dataclasses import replace as dc_replace

    from apps.billing import correction_items

    with tenant_ctx(brazos):
        world = _july_world(brazos, dana)
    preview, sent = _sent_case(brazos, dana, _one_customer(world), [_wrong_read(world)])
    real = correction_items.price

    def _moved(data):
        rated = real(data)
        return dc_replace(rated, total=rated.total + Decimal("1.00"))

    monkeypatch.setattr(correction_items, "price", _moved)
    done = _approve_and_issue(brazos, dana, sent["id"], preview["preview_hash"])
    assert done.status_code == 422, done.data
    assert done.data["message_key"] == "billing.correction.figuresMoved"
    with tenant_ctx(brazos):
        case = CorrectionCase.objects.get(pk=sent["id"])
        assert case.status == "pending_approval"
        assert not models.Invoice.objects.filter(corrects_invoice_id=world.invoice.pk).exists()


def test_def_bil_10100_a_case_closed_without_correcting_says_so(brazos, dana):
    from apps.billing import bulk_corrections, selectors
    from datetime import date

    with tenant_ctx(brazos):
        world = _july_world(brazos, dana)
    _preview_answer, sent = _sent_case(brazos, dana, _one_customer(world), [_wrong_read(world)])
    with tenant_ctx(brazos):
        case = CorrectionCase.objects.get(pk=sent["id"])
        assert selectors.correction_case_row(case)["closed_without_correcting"] is False
        bulk_corrections.abandon(
            case, reason="Sent back by the approver.", actor=dana, on_date=date(2026, 8, 16)
        )
        case.refresh_from_db()
        assert selectors.correction_case_row(case)["closed_without_correcting"] is True


def test_def_bil_10101_a_corrected_schedule_version_is_not_offered(brazos, dana):
    from apps.billing import correction_answer
    from apps.rating import models as rating_models

    with tenant_ctx(brazos):
        world = _july_world(brazos, dana)
        old = world.invoice.lines.filter(kind="usage").first().tariff_version
        new = rating_models.TariffVersion.objects.get(pk=old.pk)
        new.pk = None
        new.id = None
        new.corrects_id = old.pk
        new.save()
        rating_models.TariffVersion.objects.filter(pk=old.pk).update(superseded_by=new)
        offered = next(
            s for s in correction_answer._schedules() if s["id"] == str(old.tariff_id)
        )["versions"]
        ids = [v["id"] for v in offered]
        assert str(old.pk) not in ids, "a corrected-away version is no longer a price"
        assert str(new.pk) in ids


def test_def_bil_10102_a_one_time_bills_correction_issues(brazos, dana):
    """A bill whose run has no cycle (a one-time run names its account): the
    replacement's run must name the account too, or the database refuses it."""
    from datetime import date

    from apps.billing import models as billing_models

    from tests.test_cr180_fix_a_bill_revamp import (
        JUL_1,
        JUL_31,
        _an_account,
        _issue,
        _water_plan,
    )
    from tests.test_us_bil_005_release_gate import a_release

    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        account, asset = _an_account(
            brazos, dana, plan, n=41,
            reads=[("2026-06-28", "1100", "1150"), ("2026-07-28", "1150", "1200")],
        )
        run = billing_models.BillRun.objects.create(
            tenant=brazos, cycle=None, scope_account=account, period_start=JUL_1,
            period_end=JUL_31, bill_date=date(2026, 8, 1), due_days=21, idempotency_key="fix|onetime",
        )
        a_release(brazos, run, dana)
        invoice = _issue(dana, account, run, start=JUL_1, end=JUL_31)
    from types import SimpleNamespace

    world = SimpleNamespace(account=account, asset=asset, invoice=invoice)
    preview, sent = _sent_case(brazos, dana, _one_customer(world), [_wrong_read(world)])
    done = _approve_and_issue(brazos, dana, sent["id"], preview["preview_hash"])
    assert done.status_code == 200, done.data
    assert done.data["result"]["failed"] == [], done.data["result"]


def test_def_bil_10103_a_bulk_bill_whose_total_does_not_move_is_left_as_it_is(
    brazos, dana, monkeypatch
):
    """Three July bills in one run; the re-price moves two and leaves the third
    at its billed $373.00. The case pins two, and Check counts two credit notes
    and two new bills — the third is left as it is, as the screen says."""
    from dataclasses import replace as dc_replace

    from apps.billing import correction_items

    from tests.test_cr180_fix_a_bill_revamp import _preview

    with tenant_ctx(brazos):
        first = _july_world(brazos, dana, n=51)
        second = _july_world(brazos, dana, n=52, plan=first.plan, run=first.run)
        third = _july_world(brazos, dana, n=53, plan=first.plan, run=first.run)
        schedule = str(first.invoice.lines.filter(kind="usage").first().tariff_version.tariff_id)
    real = correction_items.price

    def _third_unchanged(data):
        rated = real(data)
        if str(data.account_id) == str(third.account.pk):
            return dc_replace(rated, total=ORIGINAL_JULY)
        return dc_replace(rated, total=rated.total + Decimal("5.00"))

    monkeypatch.setattr(correction_items, "price", _third_unchanged)
    scope = {"kind": "run", "bill_run_id": str(first.run.pk)}
    items = [{"reason": "wrong_rate", "item": schedule}]
    from tests.test_cr180_fix_a_bill_revamp import _bulk_preview, _bulk_send

    answer = _bulk_preview(brazos, dana, scope, items)
    assert answer.status_code == 200, answer.data
    assert answer.data["totals"]["unchanged"] == 1
    assert answer.data["bulk"]["credit_notes"] == 2
    assert answer.data["bulk"]["new_bills"] == 2
    sent = _bulk_send(brazos, dana, scope, items, answer)
    assert sent.status_code == 201, sent.data
    assert len(sent.data["bills_detail"]) == 2, "the unchanged bill is not pinned"
