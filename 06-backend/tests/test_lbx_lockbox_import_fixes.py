# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-PAY-10696 (LBX-06 — an imported lockbox payment carries no
#           payment method) · DEF-PAY-10697 (LBX-08 — a cheque repeated in one
#           file is posted twice; keep-latest keyed on the cheque alone)
# Rulings:  decision log 2026-10-30 "Lockbox audit: what is fixed, what is not,
#           and three answers (PO)" · CR-186-BRC10 (every payment is POSTED at
#           entry; it clears only when its batch is reconciled)
# ───────────────────────────────────────────────────────
"""The tester's lockbox file, through the REAL writer and the REAL record path.

The worked figure is the tester's own: a six-row lockbox file totalling
**$870.50** must read on the batch's *Totals by tender* as
**Lockbox · 6 · $870.50**, every row `posted` (never `cleared` on its paid
date — a payment clears only when its batch is reconciled with the bank).
Before the fix the tender column was BLANK for all six, because the writer
named no method and no "tenant default tender" exists.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from apps.payments import import_writer, reconciliation
from apps.payments import bankrec_models as bankrec
from apps.payments import models as payment_models
from apps.tenancy import models as tenancy_models
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · marcus
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_020_023_bank_rec import an_account_of

pytestmark = pytest.mark.django_db

PAID_AT = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)

#: The tester's six cheques. 76.40 + 154.00 + 120.00 + 210.10 + 95.00 + 215.00
#: = 870.50.
SIX = ("76.40", "154.00", "120.00", "210.10", "95.00", "215.00")


def _import_row(actor, account, amount, *, reference):
    return import_writer.create_payment_from_import(
        actor=actor,
        payload={
            "account_ref": account.account_no,
            "amount": amount,
            "paid_at": PAID_AT,
            "reference": reference,
            "idempotency_reference": f"lockbox-run:{uuid.uuid4().hex}",
        },
    )


def test_lbx06_six_imported_cheques_read_lockbox_6_870_50_and_stay_posted(brazos, marcus):
    with tenant_ctx(brazos):
        created = []
        for n, amount in enumerate(SIX, start=1):
            account = an_account_of(marcus, brazos)
            created.append(_import_row(marcus, account, amount, reference=f"CHK-{1000 + n}"))
        rows = payment_models.Payment.objects.filter(pk__in=[one["id"] for one in created])
        assert rows.count() == 6
        for row in rows:
            assert row.method_id is not None, "an imported lockbox payment names its tender"
            assert row.method.code == "lockbox"
            assert row.status == payment_models.PAYMENT_POSTED, "posted at entry, never cleared"
            assert row.cleared_at is None, "it clears only when its batch is reconciled"
        batch_ids = {row.deposit_batch_id for row in rows}
        assert len(batch_ids) == 1, "one lockbox file on one day is one batch"
        batch = bankrec.DepositBatch.objects.get(pk=batch_ids.pop())
        totals = reconciliation.tender_totals(batch)
        assert len(totals) == 1, totals
        (only,) = totals
        assert only["count"] == 6
        assert Decimal(str(only["amount"])) == Decimal("870.50")
        assert (
            only.get("code") or only.get("method__code") or only.get("method_code")
        ) == "lockbox", only


def test_lbx06_a_tenant_that_retired_lockbox_is_refused_by_name_not_written_blank(brazos, marcus):
    """A tenant that deactivated its Lockbox method has said stop using it, so the
    row is refused with its own reason rather than written with a blank tender."""
    with tenant_ctx(brazos):
        tenancy_models.PaymentMethod.objects.filter(tenant_id=brazos.id, code="lockbox").update(
            active=False
        )
        account = an_account_of(marcus, brazos)
        with pytest.raises(errors.ApiError) as refused:
            _import_row(marcus, account, "76.40", reference="CHK-2001")
        assert refused.value.message_key == import_writer.REFUSAL_LOCKBOX_METHOD_OFF
        assert not payment_models.Payment.objects.filter(account_id=account.pk).exists()


# ══ DEF-PAY-10697 (LBX-08) — payments' read of cheques it already has ════════


def test_lbx08_a_cheque_already_recorded_is_found_and_another_customers_is_not(brazos, marcus):
    with tenant_ctx(brazos):
        mine = an_account_of(marcus, brazos)
        theirs = an_account_of(marcus, brazos)
        created = _import_row(marcus, mine, "76.40", reference="CHK-1042")
        same = import_writer.cheque_key(mine.pk, "76.4", " chk-1042")
        other_customer = import_writer.cheque_key(theirs.pk, "76.40", "CHK-1042")
        other_amount = import_writer.cheque_key(mine.pk, "67.40", "CHK-1042")
        found = import_writer.posted_cheques([same, other_customer, other_amount])
        assert found == {same: created["payment_no"]}


def test_lbx08_a_cancelled_cheque_is_not_called_already_recorded(brazos, marcus):
    """A cheque taken back out of the books may lawfully come in again. A posted
    row may move to `cancelled` (`payments/0051`'s clearing list), so this
    update is one the database itself allows."""
    with tenant_ctx(brazos):
        account = an_account_of(marcus, brazos)
        created = _import_row(marcus, account, "76.40", reference="CHK-3001")
        payment_models.Payment.objects.filter(pk=created["id"]).update(
            status=payment_models.PAYMENT_CANCELLED
        )
        key = import_writer.cheque_key(account.pk, "76.40", "CHK-3001")
        assert import_writer.posted_cheques([key]) == {}
