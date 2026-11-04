# ── Trace ──────────────────────────────────────────────
# Change:   Record links (PO ruling 2026-10-19, decision log "Record links
#           (navigation design)") — job B's GROUP 2: the server sends the id
#           behind a number a screen prints, so the number can open its record.
# Rules:    B14 rule 31 (an id builds an ADDRESS, never a visible value) ·
#           CLAUDE.md hard rule 1 (tenant scoping; RLS FORCE) · hard-won law 14
#           (run on PostgreSQL, not only on the SQLite default suite)
# Impacts:  apps/payments/selectors.py (`batch_id`) ·
#           apps/payments/settlements_read.py (`account_id`) ·
#           apps/ledger/reporting.py + wire.py (`source_id`) ·
#           apps/metering/selectors.py (`account_id` on a unit row) ·
#           apps/billing/run_scope.py (`account_id` on the scope-list rows)
#           (`unit_plan.id` is asserted in test_us_cus_003_account_write.py and
#           the waived list's `account_id` in test_bbr_fixed_charge_next_bill.py,
#           beside the cases that already build those worlds.)
# ───────────────────────────────────────────────────────
"""Each id the screens now link with, served — and never across a tenant.

Run on PostgreSQL (hard-won law 14):

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
    DATABASE_URL=postgres://smartbillhub:smartbillhub@localhost:5432/<db> \\
        pytest tests/test_record_links_job_b_pg.py

It runs on the default SQLite suite too: every case here is a READ, and the
tenant half asserts the APP-LAYER filter each read writes out. RLS itself is the
G5 suite's subject and is not re-proved here.

**What would make these pass wrongly** (law 7 habit 2): a key that is present
but always null. So every case asserts the id EQUALS the row it should name,
not merely that the key exists.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from apps.billing import run_scope_api
from apps.customers import selectors as customer_selectors
from apps.ledger import api as ledger_api
from apps.ledger import models as ledger_models
from apps.ledger import reporting, wire
from apps.metering import models as metering_models
from apps.metering import selectors as metering_selectors
from apps.payments import models as payment_models
from apps.payments import selectors as payment_selectors
from apps.payments import settlement_models, settlements, settlements_read
from core.pagination import ListParams

from tests.test_bulk_run_scope import counted_world
from tests.test_cr135_p1_source_and_batch import POSTED_AT, _a_payment
from tests.test_cr139_p5_settlements import _payout, three_card_payments  # noqa: F401
from tests.test_def_led_6493_journal_pages_in_sql import _open_write_window, _request
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    FakeUser,
    api_call,
    brazos,
    dana,
    erin,
    lonestar,
    tenant_ctx,
)
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db


# ══ Payments — the Batch cell opens the deposit batch ═══════════════════════
def _a_deposit_batch(tenant, *, code: str):
    """One banked batch, whose CODE and ID are what the read serves.

    ⚠ **NOT `test_cr135_p1_source_and_batch._a_deposit_batch`, WHICH CANNOT RUN
    ON POSTGRESQL** — it creates a batch with no counter session, and
    `trg_deposit_batch_needs_session` (`payments/0033`) refuses that BY NAME.
    Measured here first: the borrowed helper passed on SQLite and raised
    `BR-PAY-025 … cannot be created without a counter session` on PostgreSQL
    16 (hard-won law 14). The subject of this file is the READ, so the guard is
    disabled for this transaction the way
    `test_cr136_p2_10_11_wire.a_legacy_batch` documents — `ALTER TABLE` is
    transactional on PostgreSQL and the test's rollback restores it.
    """
    from django.db import connection

    from apps.payments import bankrec_models
    from apps.tenancy import models as tenancy_models

    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute(
                "alter table deposit_batches disable trigger trg_deposit_batch_needs_session"
            )
    method, _ = tenancy_models.PaymentMethod.objects.get_or_create(
        tenant_id=tenant.id, code="check", defaults={"name": "Check"}
    )
    return bankrec_models.DepositBatch.objects.create(
        tenant_id=tenant.id,
        code=code,
        session=None,
        method=method,
        deposited_on=POSTED_AT.date(),
        status=bankrec_models.BATCH_IN_TRANSIT,
    )


def test_a_banked_payment_serves_its_deposit_batch_id(brazos, dana):
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-RL-0001")
        payment = _a_payment(brazos, account, origin=payment_models.PAYMENT_ORIGIN_ENTRY)
        batch = _a_deposit_batch(brazos, code="DEP-261019-0001")
        payment_models.Payment.objects.filter(pk=payment.pk).update(deposit_batch_id=batch.pk)
        payment.refresh_from_db()

        [row] = payment_selectors.payment_rows([payment])
        assert row["batch_ref"] == "DEP-261019-0001"
        assert row["batch_kind"] == "deposit"
        assert row["batch_id"] == str(batch.pk)
        # The single-row path (the payment page) answers the same.
        assert payment_selectors.payment_row(payment)["batch_id"] == str(batch.pk)


def test_a_payment_in_no_batch_serves_no_batch_id(brazos, dana):
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-RL-0002")
        payment = _a_payment(brazos, account, origin=payment_models.PAYMENT_ORIGIN_ENTRY)
        row = payment_selectors.payment_row(payment)
    assert row["batch_ref"] is None
    assert row["batch_id"] is None


def test_another_tenants_batch_id_never_reaches_a_payment_row(brazos, lonestar, dana, erin):
    """A payment stamped with a batch id that belongs to ANOTHER utility (only
    possible by a defect, and that is the point) resolves to no batch at all:
    the label read filters `deposit_batches` on the caller's tenant."""
    with tenant_ctx(lonestar):
        theirs = _a_deposit_batch(lonestar, code="DEP-261019-9999")
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-RL-0003")
        payment = _a_payment(brazos, account, origin=payment_models.PAYMENT_ORIGIN_ENTRY)
        payment.deposit_batch_id = theirs.pk  # in memory only — never written
        row = payment_selectors.payment_rows([payment])[0]
    assert row["batch_id"] is None
    assert row["batch_ref"] is None


# ══ Settlements — the member's account number opens the account ═════════════
def test_a_settlement_member_serves_its_account_id(brazos, dana, three_card_payments):  # noqa: F811
    with tenant_ctx(brazos):
        result = settlements.ingest_payout(actor=dana, **_payout())
        payout = settlement_models.Settlement.objects.get(pk=result.settlement_id)
        rows = settlements_read.member_rows(
            settlements_read.member_list_queryset(payout, ListParams())
        )
    by_payment = {row["account_no"]: row for row in rows}
    assert len(rows) == 3
    for payment in three_card_payments.values():
        row = by_payment[payment.account.account_no]
        assert row["account_id"] == str(payment.account_id)


def test_another_tenant_reads_no_members_of_this_payout(
    brazos, lonestar, dana, three_card_payments  # noqa: F811
):
    with tenant_ctx(brazos):
        result = settlements.ingest_payout(actor=dana, **_payout())
        payout = settlement_models.Settlement.objects.get(pk=result.settlement_id)
    with tenant_ctx(lonestar):
        rows = settlements_read.member_rows(
            settlements_read.member_list_queryset(payout, ListParams())
        )
    assert rows == []


# ══ Journal — the Source cell opens the bill, payment or refund ═════════════
def _an_entry(tenant, *, source_type: str, source_id, key: str):
    """One POSTED, BALANCED entry — born a draft, lined both sides, then posted,
    the order `ledger/0002`'s immutability trigger permits. (One line was the
    first draft, and `ledger_assert_balanced` refused it on PostgreSQL — the
    trigger SQLite does not have.)"""
    _open_write_window()
    account = ledger_models.LedgerAccount.objects.filter(tenant=tenant).first()
    entry = ledger_models.JournalEntry.objects.create(
        tenant=tenant,
        entry_date=date(2026, 10, 1),
        type=ledger_models.JE_STANDARD,
        status=ledger_models.JE_DRAFT,
        currency="USD",
        memo=f"record links {key}",
        source_type=source_type,
        source_id=source_id,
        posting_key=f"rl-{key}",
    )
    for side in (ledger_models.SIDE_DEBIT, ledger_models.SIDE_CREDIT):
        ledger_models.JournalLine.objects.create(
            tenant=tenant,
            journal_entry=entry,
            ledger_account=account,
            side=side,
            amount=Decimal("12.0000"),
        )
    ledger_models.JournalEntry.objects.filter(pk=entry.pk).update(status=ledger_models.JE_POSTED)
    return entry


def test_a_journal_row_serves_its_source_id_on_the_list_and_the_detail(brazos, dana):
    invoice_id = uuid.uuid4()
    with tenant_ctx(brazos):
        entry = _an_entry(brazos, source_type="invoice", source_id=invoice_id, key="inv")
        manual = _an_entry(brazos, source_type="manual_je", source_id=None, key="man")
        rows = ledger_api.journal_entries(_request(brazos, dana, per="100")).data["results"]
        detail = wire.journal_entry_detail_dict(
            reporting.journal_entry_detail(entry.pk), currency="USD"
        )
    by_id = {row["entry_id"]: row for row in rows}
    assert by_id[str(entry.pk)]["source_type"] == "invoice"
    assert by_id[str(entry.pk)]["source_id"] == str(invoice_id)
    assert by_id[str(manual.pk)]["source_id"] is None
    assert detail["entry"]["source_id"] == str(invoice_id)


def test_another_tenants_journal_never_lists_this_entry(brazos, lonestar, dana, erin):
    with tenant_ctx(brazos):
        entry = _an_entry(brazos, source_type="payment", source_id=uuid.uuid4(), key="pay")
    with tenant_ctx(lonestar):
        rows = ledger_api.journal_entries(_request(lonestar, erin, per="100")).data["results"]
    assert str(entry.pk) not in {row["entry_id"] for row in rows}


# ══ Units — the Occupant cell opens the occupying account ═══════════════════
def test_an_occupied_unit_row_serves_its_account_id(brazos, dana):
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-RL-0010")
        unit = metering_models.Unit.objects.get(pk=account.unit_id)
        row = metering_selectors.unit_list_dict(unit)
    assert row["occupancy"] == "occupied"
    assert row["account_no"] == "A-RL-0010"
    assert row["account_id"] == str(account.pk)


def test_another_tenant_cannot_read_the_occupying_account(brazos, lonestar, dana):
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-RL-0011")
    with tenant_ctx(lonestar):
        assert customer_selectors.active_account_for_unit(account.unit_id) is None


# ══ Bulk run Scope — the missing-meter row's account opens the account ══════
def _listed(tenant, query):
    return api_call(
        run_scope_api.scope_list,
        "get",
        user=FakeUser(),
        role="executive",
        tenant=tenant,
        query=query,
    )


def test_the_missing_meter_row_serves_its_account_id(brazos, dana):
    with tenant_ctx(brazos):
        cycle, accounts = counted_world(brazos, dana)
    response = _listed(brazos, {"cycle_id": str(cycle.id), "list": "missing_meter"})
    assert response.status_code == 200, response.data
    [row] = response.data["results"]
    account_d = next(one for one in accounts if one.account_no == "A-9104")
    assert row["account_no"] == "A-9104"
    assert row["account_id"] == str(account_d.pk)


def test_another_tenant_lists_nothing_from_this_cycle(brazos, lonestar, dana):
    with tenant_ctx(brazos):
        cycle, _accounts = counted_world(brazos, dana)
    response = _listed(lonestar, {"cycle_id": str(cycle.id), "list": "missing_meter"})
    rows = response.data.get("results", []) if response.status_code == 200 else []
    assert all(row.get("account_no") != "A-9104" for row in rows)
