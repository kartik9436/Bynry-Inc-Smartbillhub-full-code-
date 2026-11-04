# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-PAY-10323 — a payment in a reconciled deposit read "Banked, not
#           matched" on its page when the batch was tied to its bank line 1:1.
# Change:   CR-186-BRC10 (posted → cleared at bank reconciliation)
# Code:     apps/payments/payment_detail._reconciled
# ───────────────────────────────────────────────────────
"""The RECONCILED tile on the payment page, for every shape a tie can take.

`payment_detail._reconciled` read the tie only from `bank_rec_match_members`
(a CS-17 match SET). An ordinary one-to-one match lives on
`bank_lines.deposit_batch_id` and was never consulted, so a batch reconciled
1:1 served `matched_at: null` — which the screen draws as *Banked, not matched*
beside a *Cleared* status. Every earlier test of the tile used a set or no
match at all. These four cases cover 1:1, a set, matched-not-reconciled and
unmatched, each through the real write path.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.payments import bankrec_models as bankrec
from apps.payments import payment_detail, reconciliation
from apps.payments import models as payment_models

from tests.test_cr186_paycore import BANK_AT, _pay, _reconcile, _row
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · marcus
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_020_023_bank_rec import a_bank_account, a_statement

pytestmark = pytest.mark.django_db


def _tile(row):
    row.refresh_from_db()
    return payment_detail.payment_detail(row)["reconciled"]


def _import(actor, tenant, rows):
    account = a_bank_account(tenant, name="Chase tile")
    imported = reconciliation.import_bank_statement(
        actor=actor,
        bank_account_id=account.pk,
        period_start=date(2026, 10, 1),
        period_end=date(2026, 10, 31),
        payload=a_statement(rows),
        imported_at=BANK_AT,
    )
    return list(
        bankrec.BankLine.objects.filter(statement_import_id=imported.statement_import_id)
    )


def test_one_to_one_reconciled_batch_reads_reconciled_with_its_bank_line(brazos, marcus):
    """The defect's own case: PY-… in DEP-…, reconciled 1:1."""
    with tenant_ctx(brazos):
        row = _row(_pay(marcus, brazos, "60.00"))
        batch = bankrec.DepositBatch.objects.get(pk=row.deposit_batch_id)
        _reconcile(marcus, brazos, batch, "60.00")
        row.refresh_from_db()
        assert row.status == payment_models.PAYMENT_CLEARED

        tile = _tile(row)
        assert tile["batch_code"] == batch.code
        assert tile["batch_status"] == bankrec.BATCH_RECONCILED
        assert tile["matched_at"] is not None, "a 1:1 tie is a tie — not 'Banked, not matched'"
        assert tile["bank_line_count"] == 1
        assert tile["batch_count"] == 1
        assert tile["bank_posted_on"] == "2026-10-16", "the bank line's own date"
        assert tile["reconciled_at"] is not None


def test_grouped_match_set_reads_every_line_and_batch(brazos, marcus):
    with tenant_ctx(brazos):
        ic = _row(_pay(marcus, brazos, "40.00", source="webhook", ref="invoice_cloud:T1"))
        pm = _row(_pay(marcus, brazos, "25.00", source="webhook", ref="paymentus:T2"))
        assert ic.deposit_batch_id != pm.deposit_batch_id
        (line,) = _import(marcus, brazos, [("2026-10-16", "COMBINED CREDIT", "65.00")])
        assert line.deposit_batch_id is None, "no single batch equals the credit"
        reconciliation.match_set(
            actor=marcus,
            bank_line_ids=[line.pk],
            batch_ids=[ic.deposit_batch_id, pm.deposit_batch_id],
            occurred_at=BANK_AT,
        )
        reconciliation.reconcile_batch(
            actor=marcus, batch_id=ic.deposit_batch_id, posted_at=BANK_AT
        )

        tile = _tile(ic)
        assert tile["batch_status"] == bankrec.BATCH_RECONCILED
        assert tile["matched_at"] is not None
        assert tile["bank_line_count"] == 1
        assert tile["batch_count"] == 2
        assert tile["bank_posted_on"] == "2026-10-16"
        assert tile["reconciled_at"] is not None

        sibling = _tile(pm)
        assert sibling["batch_status"] == bankrec.BATCH_MATCHED
        assert sibling["matched_at"] is not None
        assert sibling["reconciled_at"] is None, "matched inside the set, not yet reconciled"


def test_matched_but_not_reconciled_reads_matched(brazos, marcus):
    with tenant_ctx(brazos):
        row = _row(_pay(marcus, brazos, "45.00"))
        batch = bankrec.DepositBatch.objects.get(pk=row.deposit_batch_id)
        (line,) = _import(marcus, brazos, [("2026-10-16", f"DEPOSIT {batch.code}", "45.00")])
        if line.deposit_batch_id is None:
            reconciliation.match_bank_line(
                actor=marcus, batch_id=batch.pk, bank_line_id=line.pk, occurred_at=BANK_AT
            )

        tile = _tile(row)
        assert tile["batch_status"] == bankrec.BATCH_MATCHED
        assert tile["matched_at"] is not None
        assert tile["bank_line_count"] == 1 and tile["batch_count"] == 1
        assert tile["bank_posted_on"] == "2026-10-16"
        assert tile["reconciled_at"] is None
        assert row.status == payment_models.PAYMENT_POSTED


def test_unmatched_batch_reads_banked_not_matched(brazos, marcus):
    with tenant_ctx(brazos):
        row = _row(_pay(marcus, brazos, "33.00"))
        batch = bankrec.DepositBatch.objects.get(pk=row.deposit_batch_id)
        tile = _tile(row)
        assert tile["batch_code"] == batch.code
        assert tile["matched_at"] is None
        assert tile["bank_line_count"] is None and tile["batch_count"] is None
        assert tile["bank_posted_on"] is None and tile["reconciled_at"] is None


def test_unreconciled_batch_reads_banked_not_matched_again(brazos, marcus):
    """Unreconcile returns the batch to `unmatched`; the write-once line link
    stays on `bank_lines`, so the batch's own status — not the link — decides."""
    with tenant_ctx(brazos):
        row = _row(_pay(marcus, brazos, "61.00"))
        batch = bankrec.DepositBatch.objects.get(pk=row.deposit_batch_id)
        _reconcile(marcus, brazos, batch, "61.00")
        reconciliation.unreconcile_batch(
            actor=marcus, batch_id=batch.pk, reason="wrong line", posted_at=BANK_AT
        )
        tile = _tile(row)
        assert tile["batch_status"] == bankrec.BATCH_UNMATCHED
        assert tile["matched_at"] is None
        assert tile["reconciled_at"] is None
        assert Decimal(row.amount) == Decimal("61.00")
