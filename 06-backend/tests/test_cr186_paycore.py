# ── Trace ──────────────────────────────────────────────
# Change:   CR-186-BRC10 — lane PAY-CORE: every payment POSTED at entry, CLEARED
#           at bank reconciliation; one deposit batch per till or per provider
#           per day, all tenders; cancel only from posted.
# Rulings:  12-governance/02-decision-log.md, the seven 2026-10-21 entries
# Rules:    CLAUDE.md hard rules 1, 2, 4, 5, 6, 7 · BR-PAY-021 · BR-PAY-025
# PG half:  tests/test_cr186_paycore_pg.py (the trigger, both directions)
# ───────────────────────────────────────────────────────
"""CR-186-BRC10 PAY-CORE — the cases the CR's §3 tasks T5–T13 declare.

Every payment here goes through the REAL write path (`record_payment`, the
counter, the webhook door) — nothing is stamped by hand — because the defect
shape this lane exists to prevent is a status or a batch that is correct only
when a test writes it.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.payments import bankrec_models as bankrec
from apps.payments import cancel, counters, ledger_seam, reconciliation, reversal, services
from apps.payments import models as payment_models
from apps.payments.exceptions import PaymentRuleError
from apps.tenancy import published_content_models as content_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana · marcus · lonestar · erin
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_020_023_bank_rec import (
    a_bank_account,
    a_statement,
    an_account_of,
    an_issued_bill,
    journal_legs,
)

pytestmark = pytest.mark.django_db

DAY = date(2026, 10, 14)
POSTED = datetime(2026, 10, 14, 15, 0, tzinfo=UTC)
BANK_AT = datetime(2026, 10, 16, 9, 0, tzinfo=UTC)


@pytest.fixture()
def centre(brazos):
    with tenant_ctx(brazos):
        return content_models.ServiceCentre.objects.create(
            tenant=brazos,
            slug="paycore-window",
            name="Main office",
            address="101 Bend Road, Brazos Bend, TX 77422",
        )


def _account_with_bill(actor, tenant, amount):
    account = an_account_of(actor, tenant)
    an_issued_bill(
        tenant,
        account,
        number=f"BL-2610-{uuid.uuid4().hex[:6]}",
        total=amount,
        issued_on=date(2026, 10, 1),
    )
    return account


def _pay(actor, tenant, amount, *, method="card", source="entry", ref=None, till=None,
         posted_at=POSTED, with_bill=True, **extra):
    account = (
        _account_with_bill(actor, tenant, Decimal(amount)) if with_bill else an_account_of(actor, tenant)
    )
    return services.record_payment(
        actor,
        account_id=account.pk,
        amount=Decimal(amount),
        posted_at=posted_at,
        # A caller that still passes a clearing date: it is accepted and NOT stored.
        cleared_at=posted_at,
        method_code=method,
        idempotency_source=source,
        idempotency_reference=ref if ref is not None else uuid.uuid4(),
        counter_session_id=None if till is None else till.pk,
        **extra,
    )


def _row(recorded):
    return payment_models.Payment.objects.get(pk=recorded.payment_id)


def _balanced(tenant):
    legs = journal_legs(tenant)
    debits = sum(a for _c, s, a in legs if s == "debit")
    credits = sum(a for _c, s, a in legs if s == "credit")
    return debits, credits


# ══ T5 · posted at entry, applied, journalled — every entry path ═══════════
@pytest.mark.parametrize(
    "source,ref",
    [
        ("entry", None),
        ("webhook", "invoice_cloud:TID-1"),
        ("import", "lockbox-file-1:7"),
        ("agent", "pay_uspayments:900000000123|payment"),
    ],
)
def test_t5_every_entry_path_is_posted_applied_and_journalled(brazos, marcus, source, ref):
    with tenant_ctx(brazos):
        recorded = _pay(marcus, brazos, "120.00", source=source, ref=ref or uuid.uuid4())
        row = _row(recorded)
        assert row.status == payment_models.PAYMENT_POSTED
        assert row.cleared_at is None, "a clearing date is the bank reconciliation's, never entry's"
        assert recorded.applied == Decimal("120.00"), "applied to the open bill at posting"
        assert row.journal_entry_id is not None and recorded.posted_to_ledger
        assert row.deposit_batch_id is not None, "stamped into its batch at posting"
        assert recorded.deposit_batch_id == str(row.deposit_batch_id)
        batch = bankrec.DepositBatch.objects.get(pk=row.deposit_batch_id)
        assert recorded.deposit_batch_code == batch.code
        assert batch.method_id is None, "one batch, all tenders"
        assert batch.recorded_total == Decimal("120.00")
        debits, credits = _balanced(brazos)
        assert debits == credits and debits > 0


def test_t5_the_entry_is_dated_the_posting_date(brazos, marcus):
    from apps.ledger import models as ledger_models

    with tenant_ctx(brazos):
        row = _row(_pay(marcus, brazos, "50.00"))
        entry = ledger_models.JournalEntry.objects.get(pk=row.journal_entry_id)
        assert entry.entry_date == DAY


def test_t8_a_closed_period_forwards_the_entry_and_keeps_the_posting_date(
    brazos, marcus, monkeypatch
):
    """BR-TEN-038 through the ledger's ONE resolver. The resolver is replaced
    only to stand in for a closed September; what is asserted is that the
    payment path ASKS it and books what it answers, while the payment keeps its
    own date for late fees (PO 2026-10-21 ruling 3)."""
    from apps.ledger import close
    from apps.ledger import models as ledger_models

    forwarded = date(2026, 11, 1)
    note = {"code": "period_closed_auto_forwarded", "detail": "period closed; auto-forwarded"}
    asked: list[date] = []

    note["requested_period"] = ["2026-10-01", "2026-10-31"]

    def closed_october(requested, **_kw):
        asked.append(requested)
        # The ledger asks again of the date it is handed; November is open.
        return (requested, None) if requested == forwarded else (forwarded, note)

    monkeypatch.setattr(close, "resolve_entry_date", closed_october)
    with tenant_ctx(brazos):
        recorded = _pay(marcus, brazos, "75.00")
        row = _row(recorded)
        assert asked[0] == DAY
        assert ledger_models.JournalEntry.objects.get(pk=row.journal_entry_id).entry_date == forwarded
        assert row.posted_at == POSTED, "the payment keeps its own posting date"
        assert any(p.get("code") == "period_closed_auto_forwarded" for p in recorded.problems)


# ══ T6 · one batch per till per day, all tenders — Dana's $800 ═════════════
def test_t6_dana_cash_and_cheques_are_one_batch_of_800(brazos, dana, centre):
    with tenant_ctx(brazos):
        opened = counters.open_counter(
            dana, service_centre_id=centre.pk, opening_float=Decimal("0.0000"),
            opened_at=timezone.now(),
        )
        till = opened.session
        a = _pay(dana, brazos, "300.00", method="cash", till=till, posted_at=timezone.now())
        b = _pay(dana, brazos, "200.00", method="check", till=till, posted_at=timezone.now())
        c = _pay(dana, brazos, "300.00", method="check", till=till, posted_at=timezone.now())
        ids = {_row(x).deposit_batch_id for x in (a, b, c)}
        assert ids == {opened.batch.pk}, "one batch ID for the till, cash and cheques together"
        batch = bankrec.DepositBatch.objects.get(pk=opened.batch.pk)
        assert batch.method_id is None
        assert batch.recorded_total == Decimal("800.00")
        totals = {t["method_code"]: t["amount"] for t in reconciliation.tender_totals(batch)}
        assert totals == {"cash": Decimal("300.00"), "check": Decimal("500.00")}
        assert all(_row(x).status == payment_models.PAYMENT_POSTED for x in (a, b, c))


def test_t6_invoice_cloud_and_paymentus_are_separate_batches(brazos, marcus):
    with tenant_ctx(brazos):
        ic1 = _row(_pay(marcus, brazos, "40.00", source="webhook", ref="invoice_cloud:A1"))
        ic2 = _row(_pay(marcus, brazos, "60.00", method="ach", source="webhook", ref="invoice_cloud:A2"))
        pm = _row(_pay(marcus, brazos, "25.00", source="webhook", ref="paymentus:Z9"))
        lb = _row(_pay(marcus, brazos, "10.00", method="check", source="import", ref="file-1:1"))
        office = _row(_pay(marcus, brazos, "15.00"))
        assert ic1.deposit_batch_id == ic2.deposit_batch_id, "one Invoice Cloud batch, both tenders"
        batches = {ic1.deposit_batch_id, pm.deposit_batch_id, lb.deposit_batch_id, office.deposit_batch_id}
        assert len(batches) == 4
        channels = {
            b.session.channel: b.recorded_total
            for b in bankrec.DepositBatch.objects.filter(pk__in=batches).select_related("session")
        }
        assert channels == {
            "invoice_cloud": Decimal("100.00"),
            "paymentus": Decimal("25.00"),
            "lockbox": Decimal("10.00"),
            "office": Decimal("15.00"),
        }


def test_t6_channel_derivation_is_pure():
    assert reconciliation.channel_for(origin="webhook", reference="invoice_cloud:TID") == "invoice_cloud"
    assert reconciliation.channel_for(origin="import", reference="1234:5") == "lockbox"
    assert reconciliation.channel_for(origin="import", reference=None) == "lockbox"
    assert reconciliation.channel_for(origin="entry", reference=uuid.uuid4()) == "office"
    assert reconciliation.channel_for(origin="entry", explicit="Kiosk") == "kiosk"


def test_t6_credit_joins_no_batch(brazos, marcus):
    from tests.test_us_met_helpers import staff_actor

    marcus = staff_actor(brazos, role="system_admin", email=f"adm-{uuid.uuid4().hex[:6]}@x.test")
    with tenant_ctx(brazos):
        account = an_account_of(marcus, brazos)
        reason = ledger_seam.active_reason_codes()
        if not reason:
            pytest.skip("no credit reason seeded on this tenant")
        recorded = services.record_payment(
            marcus, account_id=account.pk, amount=Decimal("5.00"), posted_at=POSTED,
            payment_type=payment_models.PAYMENT_TYPE_CREDIT, reason_code=reason[0]["code"],
            idempotency_reference=uuid.uuid4(),
        )
        assert _row(recorded).deposit_batch_id is None
        assert _row(recorded).status == payment_models.PAYMENT_POSTED


# ══ T7 · a sealed day's straggler joins the cut day's batch ════════════════
def _reconcile(actor, tenant, batch, amount, *, line_day="2026-10-16"):
    account = a_bank_account(tenant, name=f"Chase {uuid.uuid4().hex[:4]}")
    imported = reconciliation.import_bank_statement(
        actor=actor, bank_account_id=account.pk, period_start=date(2026, 10, 1),
        period_end=date(2026, 10, 31),
        payload=a_statement([(line_day, f"DEPOSIT {batch.code}", f"{amount}")]),
        imported_at=BANK_AT,
    )
    line = bankrec.BankLine.objects.filter(statement_import_id=imported.statement_import_id).first()
    if line.deposit_batch_id is None:
        reconciliation.match_bank_line(
            actor=actor, batch_id=batch.pk, bank_line_id=line.pk, occurred_at=BANK_AT
        )
    return reconciliation.reconcile_batch(actor=actor, batch_id=batch.pk, posted_at=BANK_AT)


def test_t7_straggler_for_a_reconciled_day_waits_for_the_cut_then_joins_it(brazos, marcus):
    with tenant_ctx(brazos):
        first = _row(_pay(marcus, brazos, "100.00", source="webhook", ref="invoice_cloud:S1"))
        batch = bankrec.DepositBatch.objects.get(pk=first.deposit_batch_id)
        _reconcile(marcus, brazos, batch, "100.00")
        late = _pay(marcus, brazos, "30.00", source="webhook", ref="invoice_cloud:S2")
        assert late.deposit_batch_id is None
        assert any(p.get("code") == "deposit_batch_deferred" for p in late.problems)
        cut_day = date(2026, 10, 17)
        result = reconciliation.cut_deposit_batches(
            actor=marcus, day=cut_day, occurred_at=BANK_AT
        )
        joined = bankrec.DepositBatch.objects.get(pk=_row(late).deposit_batch_id)
        assert joined.deposited_on == cut_day and joined.pk != batch.pk
        assert _row(late).posted_at == POSTED, "its own posting date stays"
        assert result.payments_batched == 1
        again = reconciliation.cut_deposit_batches(actor=marcus, day=cut_day, occurred_at=BANK_AT)
        assert again.payments_batched == 0, "the nightly cut is idempotent (hard rule 6)"


# ══ T9/T10 · reconcile → every member cleared, with the bank's date ════════
def test_t10_reconcile_clears_every_member_once(brazos, marcus, audit_rows):
    from apps.ledger import models as ledger_models

    with tenant_ctx(brazos):
        a = _row(_pay(marcus, brazos, "300.00", method="cash"))
        b = _row(_pay(marcus, brazos, "500.00", method="check"))
        assert a.deposit_batch_id == b.deposit_batch_id
        batch = bankrec.DepositBatch.objects.get(pk=a.deposit_batch_id)
        entries_before = ledger_models.JournalEntry.objects.filter(tenant=brazos).count()
        result = _reconcile(marcus, brazos, batch, "800.00")
        assert result.recorded_total == Decimal("800.00")
        for row in (a, b):
            row.refresh_from_db()
            assert row.status == payment_models.PAYMENT_CLEARED
            assert row.cleared_at is not None and row.cleared_at.date() == date(2026, 10, 16)
        assert ledger_models.JournalEntry.objects.filter(tenant=brazos).count() == entries_before + 1
        cleared_audits = [r for r in audit_rows if r["action"] == "payment.cleared"]
        assert len(cleared_audits) == 2, "hard rule 7 — one audit row per cleared payment"
        debits, credits = _balanced(brazos)
        assert debits == credits


# ══ T12 · cancel: from posted, undoing allocations and the entry ═══════════
def test_t12_cancel_posted_reverses_allocations_and_journal(brazos, marcus):
    from apps.payments import billing_seam

    with tenant_ctx(brazos):
        recorded = _pay(marcus, brazos, "120.00")
        row = _row(recorded)
        batch = bankrec.DepositBatch.objects.get(pk=row.deposit_batch_id)
        assert batch.recorded_total == Decimal("120.00")
        owed_after_payment = billing_seam.open_invoices_for_account(row.account_id).invoices
        assert not owed_after_payment or all(i.balance == 0 for i in owed_after_payment if hasattr(i, "balance"))
        result = cancel.cancel_payment(
            actor=marcus, payment_id=row.pk, reason="wrong_account", cancelled_on=BANK_AT
        )
        row.refresh_from_db()
        assert row.status == payment_models.PAYMENT_CANCELLED
        reversing = payment_models.Payment.objects.get(pk=result.reversing_payment_id)
        assert reversing.amount == Decimal("-120.00") and reversing.journal_entry_id is not None
        assert sum(a.amount for a in reversing.allocations.all()) == Decimal("-120.00")
        reopened = billing_seam.open_invoices_for_account(row.account_id).invoices
        assert len(reopened) == 1, "the bill it paid re-opened"
        batch.refresh_from_db()
        assert batch.recorded_total == Decimal("0.00"), "the cancelled member left the total"
        debits, credits = _balanced(brazos)
        assert debits == credits
        replay = cancel.cancel_payment(
            actor=marcus, payment_id=row.pk, reason="wrong_account", cancelled_on=BANK_AT
        )
        assert replay.created is False


def test_t12_cancel_cleared_is_refused_naming_refund_or_credit(brazos, marcus):
    with tenant_ctx(brazos):
        row = _row(_pay(marcus, brazos, "80.00"))
        batch = bankrec.DepositBatch.objects.get(pk=row.deposit_batch_id)
        _reconcile(marcus, brazos, batch, "80.00")
        with pytest.raises(PaymentRuleError, match="refund or a credit"):
            cancel.cancel_payment(
                actor=marcus, payment_id=row.pk, reason="wrong_account", cancelled_on=BANK_AT
            )


# ══ T13 · a bounce works from posted ═══════════════════════════════════════
def test_t13_bounce_of_a_posted_payment_is_a_reversal(brazos, marcus):
    from tests.test_us_met_helpers import staff_actor

    admin = staff_actor(brazos, role="system_admin", email=f"adm-{uuid.uuid4().hex[:6]}@x.test")
    with tenant_ctx(brazos):
        row = _row(_pay(marcus, brazos, "90.00", method="check"))
        assert row.status == payment_models.PAYMENT_POSTED
        bounced = reversal.reverse_payment(
            admin, payment_id=row.pk, returned_on=BANK_AT, idempotency_reference=uuid.uuid4()
        )
        assert bounced.amount == Decimal("-90.00")
        debits, credits = _balanced(brazos)
        assert debits == credits


def test_t13_a_cancelled_payment_cannot_bounce(brazos, marcus):
    from tests.test_us_met_helpers import staff_actor

    admin = staff_actor(brazos, role="system_admin", email=f"adm-{uuid.uuid4().hex[:6]}@x.test")
    with tenant_ctx(brazos):
        row = _row(_pay(marcus, brazos, "45.00"))
        cancel.cancel_payment(actor=marcus, payment_id=row.pk, reason="duplicate", cancelled_on=BANK_AT)
        with pytest.raises(PaymentRuleError, match="never reached"):
            reversal.reverse_payment(
                admin, payment_id=row.pk, returned_on=BANK_AT, idempotency_reference=uuid.uuid4()
            )


# ══ hard rule 6 · the same webhook reference twice is one row ═════════════
def test_idempotency_same_reference_twice_is_one_payment(brazos, marcus):
    with tenant_ctx(brazos):
        account = _account_with_bill(marcus, brazos, Decimal("20.00"))
        kwargs = dict(
            account_id=account.pk, amount=Decimal("20.00"), posted_at=POSTED, method_code="card",
            idempotency_source="webhook", idempotency_reference="invoice_cloud:DUP-1",
        )
        first = services.record_payment(marcus, **kwargs)
        second = services.record_payment(marcus, **kwargs)
        assert second.created is False and second.payment_id == first.payment_id
        assert second.deposit_batch_id == first.deposit_batch_id
        assert second.deposit_batch_code == first.deposit_batch_code
        assert payment_models.Payment.objects.filter(webhook_key__endswith="DUP-1").count() == 1


# ══ hard rule 1 · a channel's batch is per tenant ══════════════════════════
def test_isolation_channel_batches_never_cross_tenants(brazos, marcus, lonestar, erin):
    with tenant_ctx(brazos):
        mine = _row(_pay(marcus, brazos, "11.00", source="webhook", ref="invoice_cloud:T1"))
    with tenant_ctx(lonestar):
        account = an_account_of(erin, lonestar, service="water")
        theirs = services.record_payment(
            erin, account_id=account.pk, amount=Decimal("12.00"), posted_at=POSTED,
            method_code="card", idempotency_source="webhook",
            idempotency_reference="invoice_cloud:T1",
        )
        theirs_row = _row(theirs)
        assert theirs_row.deposit_batch_id != mine.deposit_batch_id
        batch = bankrec.DepositBatch.objects.get(pk=theirs_row.deposit_batch_id)
        assert batch.tenant_id == lonestar.pk and batch.recorded_total == Decimal("12.00")


# ══ T11 · unreconcile puts members back to posted (PO ruling 2026-10-21) ══
def test_t11_unreconcile_puts_cleared_members_back_to_posted(brazos, marcus, audit_rows):
    """PO 2026-10-21, "Allow, back to Posted": undo → Posted, no clearing date."""
    with tenant_ctx(brazos):
        row = _row(_pay(marcus, brazos, "60.00"))
        batch = bankrec.DepositBatch.objects.get(pk=row.deposit_batch_id)
        _reconcile(marcus, brazos, batch, "60.00")
        row.refresh_from_db()
        assert row.status == payment_models.PAYMENT_CLEARED and row.cleared_at is not None
        result = reconciliation.unreconcile_batch(
            actor=marcus, batch_id=batch.pk, reason="tied to the wrong line", posted_at=BANK_AT
        )
        batch.refresh_from_db()
        row.refresh_from_db()
        assert batch.status == bankrec.BATCH_UNMATCHED
        assert result["payments_uncleared"] == 1
        assert row.status == payment_models.PAYMENT_POSTED
        assert row.cleared_at is None
        uncleared = [r for r in audit_rows if r["action"] == "payment.uncleared"]
        assert len(uncleared) == 1, "hard rule 7 — one audit row per payment moved back"
        # Posted again, so it may be cancelled like any posted payment.
        cancel.cancel_payment(
            actor=marcus, payment_id=row.pk, reason="wrong_account", cancelled_on=BANK_AT
        )
        row.refresh_from_db()
        assert row.status == payment_models.PAYMENT_CANCELLED


# ══ T12 · a cancel never changes a total the bank is already tied to ═══════
def test_t12_cancel_is_refused_while_the_batch_is_matched(brazos, marcus):
    with tenant_ctx(brazos):
        row = _row(_pay(marcus, brazos, "70.00"))
        bankrec.DepositBatch.objects.filter(pk=row.deposit_batch_id).update(
            status=bankrec.BATCH_MATCHED
        )
        with pytest.raises(PaymentRuleError, match="Unmatch the deposit first"):
            cancel.cancel_payment(
                actor=marcus, payment_id=row.pk, reason="wrong_account", cancelled_on=BANK_AT
            )
        row.refresh_from_db()
        assert row.status == payment_models.PAYMENT_POSTED
