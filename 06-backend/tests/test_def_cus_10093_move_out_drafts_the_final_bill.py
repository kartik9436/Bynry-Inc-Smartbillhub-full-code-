"""DEF-CUS-10093 — the move-out's Complete drafts the final bill, BEFORE the close.

PO ruling 2026-10-13, option B, verbatim: *"Go with this - I recommend B:
nothing can be forgotten, readings are typed once, and the clerk still reviews
the bill before it goes out."* (decision log, the last entry of that date).

What is pinned here, one case each:

* Complete creates EXACTLY ONE final DRAFT and closes the account;
* the draft's total IS step 3's figure (the preview the wizard showed) — with a
  committed read and with a read keyed on step 2 and committed at Complete;
* a draft that cannot be created stops the move-out: no close, no reads, no
  run, no invoice (atomic — proved on PostgreSQL by the `--ds=config.settings.
  pgtest` run named in the lane report);
* the draft can be SENT after the close — the one carve-out — and its issue
  applies the deposit (BR-BIL-013, OQ-248 option A);
* nothing else on the closed account can be billed.

Reproduction on the demo (2026-10-12): AC-2026-00001, move-out 10/12/2026,
step 3 drew a $186.36 draft, Complete raised no invoice, One-time → Final then
refused `account_already_closed_for_billing`.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.billing import final_bill, one_time, one_time_send, release
from apps.billing import models as billing_models
from core import errors
from apps.customers import models as customer_models
from apps.customers import services as customer_services
from tests.test_br_bil_013_final_bill_preview import _a_moving_out_account
from tests.test_def_bil_10052_move_out_draft_bill_values import _unread_account
from tests.test_us_bil_001_prepare import PERIOD_START
from tests.test_us_bil_011_final_bill import MOVE_OUT
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

SENT_AT = datetime(2026, 6, 15, 15, 30, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _days_to_pay(monkeypatch):
    """The account's cycle answers its days to pay through metering's own read.

    The fixture cycle is a bare metering row; `cycle_terms_for_unit` is the
    read the draft takes BR-BIL-024's due days from, so it is answered here
    exactly as `test_otb_a_one_time_api_contract.py` answers it.
    """
    from apps.metering import selectors as metering_selectors

    monkeypatch.setattr(
        metering_selectors,
        "cycle_terms_for_unit",
        lambda unit_id: {"code": "06-S", "name": "Cycle 06", "due_days": 21},
    )


def _finals(account):
    return billing_models.Invoice.objects.filter(account_id=account.id, bill_type="final")


def test_complete_creates_exactly_one_final_draft_and_closes_the_account(brazos, dana, monkeypatch):
    with tenant_ctx(brazos):
        account = _a_moving_out_account(brazos, dana, monkeypatch, asset_no="M-9301", account_no="A-13001")
        step3 = final_bill.preview_final_bill(account_id=account.id, moved_out_on=MOVE_OUT)
        assert step3["priced"] is True, step3.get("priced_unavailable")
        assert _finals(account).count() == 0

        result = customer_services.move_out(dana, account.id, {"moved_out_on": MOVE_OUT.isoformat()})

        drafted = result["final_bill"]
        assert drafted["outcome"] == "drafted", drafted
        (invoice,) = _finals(account)
        assert invoice.status == billing_models.INVOICE_DRAFT
        assert str(invoice.pk) == drafted["invoice_id"]
        assert invoice.invoice_no and invoice.invoice_no == drafted["invoice_no"]
        assert invoice.period_end == MOVE_OUT
        assert invoice.period_start == date.fromisoformat(step3["period_start"])
        # The ONE carve-out is keyed off this marker and nothing wider.
        assert final_bill.move_out_final_draft(invoice) is True
        account.refresh_from_db()
        assert account.closed_at == MOVE_OUT
        # Its run bills on the move day, at the cycle's days to pay.
        run = billing_models.BillRun.objects.get(pk=invoice.bill_run_id)
        assert run.bill_date == MOVE_OUT and run.due_days == 21
    # The two warnings the draft makes false no longer ride the answer.
    codes = {row["code"] for row in result["warnings"]}
    assert "final_bill_not_issued" not in codes
    assert "deposit_not_settled" not in codes


def test_the_draft_equals_step_3_with_a_committed_read(brazos, dana, monkeypatch):
    with tenant_ctx(brazos):
        account = _a_moving_out_account(brazos, dana, monkeypatch, asset_no="M-9302", account_no="A-13002")
        step3 = final_bill.preview_final_bill(account_id=account.id, moved_out_on=MOVE_OUT)
        result = customer_services.move_out(dana, account.id, {"moved_out_on": MOVE_OUT.isoformat()})
        (invoice,) = _finals(account)
    assert Decimal(result["final_bill"]["total"]) == Decimal(step3["total"])
    assert invoice.total == Decimal(step3["total"])
    assert invoice.lines.count() == len(step3["lines"])


def test_the_draft_equals_step_3_when_the_reading_was_keyed_on_step_2(brazos, dana, monkeypatch):
    """The wizard's own order: step 3 prices the KEYED read, Complete commits it."""
    keyed = [{"meter_no": "M-9303", "value": "14400"}]
    with tenant_ctx(brazos):
        account = _unread_account(brazos, dana, monkeypatch, asset_no="M-9303", account_no="A-13003")
        step3 = final_bill.preview_final_bill(
            account_id=account.id, moved_out_on=MOVE_OUT, keyed_reads=keyed
        )
        assert step3["priced"] is True, step3.get("priced_unavailable")
        result = customer_services.move_out(
            dana, account.id, {"moved_out_on": MOVE_OUT.isoformat(), "final_reads": keyed}
        )
        (invoice,) = _finals(account)
    assert result["final_bill"]["outcome"] == "drafted"
    assert invoice.total == Decimal(step3["total"]), (str(invoice.total), step3["total"])


def _read_mid_window_account(brazos, dana, monkeypatch, *, asset_no, account_no):
    """A committed read on 5 June — INSIDE the closing window, before the move day."""
    from tests import test_us_bil_011_final_bill as fb

    original = fb.a_unit_read_before_the_move

    def read_mid_window(actor, tenant, cycle, plan, *, asset_no, label, day):
        return original(
            actor, tenant, cycle, plan, asset_no=asset_no, label=label, day=date(2026, 6, 5)
        )

    monkeypatch.setattr(
        "tests.test_br_bil_013_final_bill_preview.a_unit_read_before_the_move", read_mid_window
    )
    return _a_moving_out_account(brazos, dana, monkeypatch, asset_no=asset_no, account_no=account_no)


def test_def_met_10110_a_move_day_reading_typed_over_an_earlier_committed_read_is_priced(
    brazos, dana, monkeypatch
):
    """Ana Alvarez's shape: a committed read on 5 June (13800 -> 14100), the
    clerk types 14400 for the 12 June move day. Step 3 must price BOTH legs —
    300 + 300 = 600 kWh — because the move-out commits the typed reading after
    the head; it priced 300 and dropped the typed one (`DEF-MET-10110`)."""
    keyed = [{"meter_no": "M-9308", "value": "14400"}]
    with tenant_ctx(brazos):
        account = _read_mid_window_account(
            brazos, dana, monkeypatch, asset_no="M-9308", account_no="A-13008"
        )
        step3 = final_bill.preview_final_bill(
            account_id=account.id, moved_out_on=MOVE_OUT, keyed_reads=keyed
        )
        assert step3["priced"] is True, step3.get("priced_unavailable")
        assert step3["priced_from_uncommitted_reads"] is True
        result = customer_services.move_out(
            dana, account.id, {"moved_out_on": MOVE_OUT.isoformat(), "final_reads": keyed}
        )
        (invoice,) = _finals(account)
        usage = sum(
            (line.quantity or Decimal("0"))
            for line in invoice.lines.all()
            if line.quantity is not None and "base" not in (line.description or "")
        )
    assert result["final_bill"]["outcome"] == "drafted"
    assert usage == Decimal("600"), usage
    assert invoice.total == Decimal(step3["total"]), (str(invoice.total), step3["total"])


def test_a_draft_that_cannot_be_created_stops_the_move_out_and_closes_nothing(
    brazos, dana, monkeypatch
):
    """No move-in date and no issued bill: the window cannot be derived, so the
    draft is refused — and the reads, the close and the run all roll back."""
    from apps.metering import models as metering_models

    keyed = [{"meter_no": "M-9304", "value": "14400"}]
    with tenant_ctx(brazos):
        account = _unread_account(brazos, dana, monkeypatch, asset_no="M-9304", account_no="A-13004")
        customer_models.Account.objects.filter(pk=account.pk).update(opened_at=None)
        reads_before = metering_models.MeterRead.objects.filter(tenant=brazos).count()
        runs_before = billing_models.BillRun.objects.filter(tenant=brazos).count()

        with pytest.raises(errors.BizError) as refused:
            customer_services.move_out(
                dana, account.id, {"moved_out_on": MOVE_OUT.isoformat(), "final_reads": keyed}
            )

        account.refresh_from_db()
        assert account.closed_at is None
        assert metering_models.MeterRead.objects.filter(tenant=brazos).count() == reads_before
        assert billing_models.BillRun.objects.filter(tenant=brazos).count() == runs_before
        assert _finals(account).count() == 0
    assert refused.value.message_key == "customers.move_out.final_bill_not_drafted"
    assert refused.value.params["reason"]


def test_a_final_draft_already_raised_for_the_window_refuses_the_move_out(brazos, dana, monkeypatch):
    """BR-BIL-005: a clerk's own One-time Final draft for the window is not
    silently adopted (its readings may differ) — it is named, and nothing closes."""
    with tenant_ctx(brazos):
        account = _a_moving_out_account(brazos, dana, monkeypatch, asset_no="M-9305", account_no="A-13005")
        step3 = final_bill.preview_final_bill(account_id=account.id, moved_out_on=MOVE_OUT)
        one_time.create(
            one_time.OneTimeRequest(
                account_id=str(account.id),
                kind=one_time.KIND_FINAL,
                period_start=date.fromisoformat(step3["period_start"]),
                period_end=MOVE_OUT,
                bill_date=MOVE_OUT,
                due_days=21,
            ),
            run_by=dana,
            actor=dana,
        )
        with pytest.raises(errors.BizError) as refused:
            customer_services.move_out(dana, account.id, {"moved_out_on": MOVE_OUT.isoformat()})
        account.refresh_from_db()
        assert account.closed_at is None
        assert _finals(account).count() == 1
    assert refused.value.params["cause_key"] == "billing.oneTime.duplicateDraft"


def _send(run, actor):
    from apps.billing import api as billing_api

    template_id, template_version, explicit = billing_api._template_pin_for({}, run=run)
    return one_time_send.send(
        run,
        delivery="email",
        sent_at=SENT_AT,
        template_id=template_id,
        template_version=template_version,
        template_pin_explicit=explicit,
        approved_by=None,
        confirmations=release.Confirmations(
            compliance=True,
            email_mandate=True,
            sms_mandate=True,
            autopay_mandate=True,
            final=True,
        ),
        confirmed_by=getattr(actor, "id", None),
        actor=actor,
    )


def test_the_move_out_draft_can_be_sent_after_the_close_and_applies_the_deposit(
    brazos, dana, monkeypatch
):
    from apps.ledger import models as ledger_models

    with tenant_ctx(brazos):
        account = _a_moving_out_account(brazos, dana, monkeypatch, asset_no="M-9306", account_no="A-13006")
        customer_services.move_out(dana, account.id, {"moved_out_on": MOVE_OUT.isoformat()})
        (invoice,) = _finals(account)
        run = billing_models.BillRun.objects.get(pk=invoice.bill_run_id)

        outcome = _send(run, dana)

        invoice.refresh_from_db()
        assert invoice.status == billing_models.INVOICE_ISSUED
        assert outcome.created is True
        entries = ledger_models.JournalEntry.objects.filter(
            tenant=brazos, source_type="invoice", source_id=invoice.pk
        )
        assert entries.count() >= 2, "the bill's own entry and the deposit applied"
        for entry in entries:
            lines = list(ledger_models.JournalLine.objects.filter(journal_entry=entry))
            debits = sum(line.amount for line in lines if line.side == "debit")
            credits = sum(line.amount for line in lines if line.side == "credit")
            assert debits == credits, (entry.memo, debits, credits)
        # BR-BIL-013 — the deposit and its interest apply FIRST, at issue: the
        # liability is debited by the whole credit (150.00 + 3.50 = 153.50).
        applied = ledger_models.JournalLine.objects.filter(
            journal_entry__in=entries,
            side="debit",
            ledger_account__designation="deposit_liability",
        )
        assert sum(line.amount for line in applied) == Decimal("153.50")


def test_nothing_else_on_the_closed_account_can_be_billed(brazos, dana, monkeypatch):
    from apps.billing import gather

    with tenant_ctx(brazos):
        account = _a_moving_out_account(brazos, dana, monkeypatch, asset_no="M-9307", account_no="A-13007")
        customer_services.move_out(dana, account.id, {"moved_out_on": MOVE_OUT.isoformat()})
        later = date(MOVE_OUT.year, MOVE_OUT.month, MOVE_OUT.day + 1)
        with pytest.raises(gather.GatherProblem) as refused:
            one_time.create(
                one_time.OneTimeRequest(
                    account_id=str(account.id),
                    kind=one_time.KIND_FINAL,
                    period_start=later,
                    period_end=later,
                    bill_date=later,
                    due_days=21,
                ),
                run_by=dana,
                actor=dana,
            )
        assert refused.value.reason == final_bill.FINAL_ACCOUNT_ALREADY_CLOSED
        assert _finals(account).count() == 1
    assert PERIOD_START < MOVE_OUT


def test_only_the_move_out_final_draft_may_be_sent_after_the_close(brazos, dana, monkeypatch):
    """The carve-out is exactly one kind of draft. An INTERIM drafted while the
    account was open is refused at Send once the move-out has closed it."""
    with tenant_ctx(brazos):
        # A committed read on 5 June gives the interim something to price.
        account = _read_mid_window_account(
            brazos, dana, monkeypatch, asset_no="M-9309", account_no="A-13009"
        )
        interim = one_time.create(
            one_time.OneTimeRequest(
                account_id=str(account.id),
                kind=one_time.KIND_INTERIM,
                period_start=PERIOD_START,
                period_end=date(2026, 6, 5),
                bill_date=date(2026, 6, 5),
                due_days=21,
            ),
            run_by=dana,
            actor=dana,
        )
        customer_services.move_out(dana, account.id, {"moved_out_on": MOVE_OUT.isoformat()})
        interim_run = billing_models.BillRun.objects.get(pk=interim["run_id"])
        with pytest.raises(one_time_send.SendRefused) as refused:
            _send(interim_run, dana)
        assert refused.value.message_key == "billing.oneTime.err.alreadyClosed"
        assert billing_models.Invoice.objects.get(pk=interim["invoice_id"]).status == "draft"
        (final,) = _finals(account)
        _send(billing_models.BillRun.objects.get(pk=final.bill_run_id), dana)
        final.refresh_from_db()
        assert final.status == billing_models.INVOICE_ISSUED


# ── what the issued draft does to the deposit (BR-BIL-013 · OQ-248 option A) ──
#
# The money rules are the existing ones and nothing here adds one: the deposit
# and its interest apply FIRST, against everything outstanding (OQ-158), and
# what is left over is refunded through customer credit in the SAME entry
# (OQ-248, PO 2026-09-30, *"A for deposit refund"*). The move-out writes no
# off (PO 2026-10-12): no `write_off` line appears in either case.


def _deposit_entry(brazos, invoice):
    from apps.ledger import models as ledger_models

    (entry,) = ledger_models.JournalEntry.objects.filter(
        tenant=brazos,
        source_type="invoice",
        source_id=invoice.pk,
        posting_key__endswith="|deposit_applied",
    )
    lines = list(ledger_models.JournalLine.objects.filter(journal_entry=entry))
    by = {}
    for line in lines:
        key = (line.ledger_account.designation, line.side)
        by[key] = by.get(key, Decimal("0")) + line.amount
    debits = sum(line.amount for line in lines if line.side == "debit")
    credits = sum(line.amount for line in lines if line.side == "credit")
    assert debits == credits, (debits, credits)
    return by


def test_issuing_the_move_out_draft_refunds_what_the_deposit_leaves_over(
    brazos, dana, monkeypatch
):
    """Deposit + credit: a $153.50 deposit (150.00 + 3.50 interest) against a
    final bill smaller than it settles the bill and moves the rest to customer
    credit, which is where the refund is paid from."""
    with tenant_ctx(brazos):
        account = _a_moving_out_account(brazos, dana, monkeypatch, asset_no="M-9310", account_no="A-13010")
        customer_services.move_out(dana, account.id, {"moved_out_on": MOVE_OUT.isoformat()})
        (invoice,) = _finals(account)
        assert invoice.total < Decimal("153.50"), invoice.total  # the scenario's premise
        _send(billing_models.BillRun.objects.get(pk=invoice.bill_run_id), dana)
        by = _deposit_entry(brazos, invoice)
    assert by[("deposit_liability", "debit")] == Decimal("153.50")
    assert by[("accounts_receivable", "credit")] == invoice.total
    assert by[("customer_credit_balance", "credit")] == Decimal("153.50") - invoice.total
    assert not any(designation == "write_off" for designation, _side in by)


def test_issuing_the_move_out_draft_applies_the_deposit_and_leaves_the_rest_owed(
    brazos, dana, monkeypatch
):
    """Deposit + owes: $500.00 of arrears beside the final bill. The whole
    deposit discharges receivable and nothing is refunded; the rest stays owed
    on the closed account (BR-CUS-082 follows it up)."""
    with tenant_ctx(brazos):
        account = _a_moving_out_account(
            brazos, dana, monkeypatch, asset_no="M-9311", account_no="A-13011", arrears=Decimal("500")
        )
        customer_services.move_out(dana, account.id, {"moved_out_on": MOVE_OUT.isoformat()})
        (invoice,) = _finals(account)
        _send(billing_models.BillRun.objects.get(pk=invoice.bill_run_id), dana)
        by = _deposit_entry(brazos, invoice)
        balance = customer_services_balance(account)
    assert by[("deposit_liability", "debit")] == Decimal("153.50")
    assert by[("accounts_receivable", "credit")] == Decimal("153.50")
    assert ("customer_credit_balance", "credit") not in by
    assert balance == Decimal("500") + invoice.total - Decimal("153.50"), balance


def customer_services_balance(account):
    """The account's balance as customers serves it — the ledger's own Σ."""
    from apps.customers import selectors as customer_selectors

    return Decimal(str(customer_selectors.account_detail(account.id)["balance"]))


def test_a_failure_after_the_draft_was_written_rolls_back_the_run_reads_and_close(
    brazos, dana, monkeypatch
):
    """Law 14: the engine writes the run and the invoice, THEN refuses. The
    savepoint must discard both and the move-out's own transaction must still
    be usable to raise the refusal — on PostgreSQL a caught error inside an
    un-savepointed block aborts everything after it."""
    from apps.billing import gather
    from apps.metering import models as metering_models

    real_create = one_time.create

    def create_then_refuse(*args, **kwargs):
        real_create(*args, **kwargs)
        raise gather.GatherProblem("values_missing", "refused after the draft was written")

    keyed = [{"meter_no": "M-9312", "value": "14400"}]
    with tenant_ctx(brazos):
        account = _unread_account(brazos, dana, monkeypatch, asset_no="M-9312", account_no="A-13012")
        reads_before = metering_models.MeterRead.objects.filter(tenant=brazos).count()
        runs_before = billing_models.BillRun.objects.filter(tenant=brazos).count()
        invoices_before = billing_models.Invoice.objects.filter(tenant=brazos).count()
        monkeypatch.setattr(one_time, "create", create_then_refuse)
        with pytest.raises(errors.BizError) as refused:
            customer_services.move_out(
                dana, account.id, {"moved_out_on": MOVE_OUT.isoformat(), "final_reads": keyed}
            )
        account.refresh_from_db()
        assert account.closed_at is None
        assert metering_models.MeterRead.objects.filter(tenant=brazos).count() == reads_before
        assert billing_models.BillRun.objects.filter(tenant=brazos).count() == runs_before
        assert billing_models.Invoice.objects.filter(tenant=brazos).count() == invoices_before
    assert refused.value.message_key == "customers.move_out.final_bill_not_drafted"
    assert refused.value.params["reason"] == "values_missing"


def test_def_met_10111_an_estimated_sub_meter_on_the_point_keeps_the_main_typed_reading(
    brazos, dana, monkeypatch
):
    """AC-2026-00043's shape: the main meter is typed and a SUB-METER on the
    same service point is ticked Estimate. The sub-meter, keyed after the main
    meter, overwrote the main meter's entry on a row that names no meter, so
    step 3 dropped the typed reading (10 kgal priced, 15 billed). Step 3 must
    price exactly what it prices without the sub-meter, and the draft must
    equal it."""
    from types import SimpleNamespace

    from apps.assets import models as asset_models
    from apps.metering import seams as metering_seams

    keyed = [{"meter_no": "M-9313", "value": "14400"}]
    with tenant_ctx(brazos):
        account = _read_mid_window_account(
            brazos, dana, monkeypatch, asset_no="M-9313", account_no="A-13013"
        )
        main = asset_models.Asset.objects.get(asset_no="M-9313")
        sub_meter = SimpleNamespace(
            id="00000000-0000-4000-8000-0000000c0105",
            asset_no="SM-9313",
            service_point=main.service_point,
        )
        real_by_no = metering_seams.meter_by_no
        monkeypatch.setattr(
            metering_seams,
            "meter_by_no",
            lambda no: sub_meter if no == "SM-9313" else real_by_no(no),
        )
        alone = final_bill.preview_final_bill(
            account_id=account.id, moved_out_on=MOVE_OUT, keyed_reads=keyed
        )
        with_sub = final_bill.preview_final_bill(
            account_id=account.id,
            moved_out_on=MOVE_OUT,
            keyed_reads=keyed + [{"meter_no": "SM-9313", "estimate": True}],
        )
        assert alone["priced"] is True, alone.get("priced_unavailable")
        assert with_sub["total"] == alone["total"], (with_sub["total"], alone["total"])
        customer_services.move_out(
            dana, account.id, {"moved_out_on": MOVE_OUT.isoformat(), "final_reads": keyed}
        )
        (invoice,) = _finals(account)
    assert invoice.total == Decimal(with_sub["total"])
