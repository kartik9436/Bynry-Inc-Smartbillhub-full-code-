# ── Trace ──────────────────────────────────────────────
# Change:   CR-186-BRC10 — hard rule 4's second narrowing (`payments/0051`)
# Rules:    CLAUDE.md hard rule 4 · hard-won law 14 (SQLite has no triggers;
#           every case here SKIPS there and runs on PostgreSQL)
# ───────────────────────────────────────────────────────
"""`payments_payment_immutable()` after `payments/0051`, proved in BOTH directions.

PO 2026-10-21: a payment is `posted` at entry; it becomes `cleared`, with its
clearing date, when its deposit batch is reconciled; `cancelled` only from
`posted`. So the database lets a POSTED row change `status` → `cleared` (with
`cleared_at`, written once) or → `cancelled`, and NOTHING else. Every refusal
below is a raw cursor UPDATE that bypasses every Python check — the trigger is
the guarantee, not the service.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from django.db import DatabaseError, connection, transaction

from apps.payments import models as payment_models
from apps.payments import services

from tests.isolation_helpers import requires_postgres
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · marcus
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_020_023_bank_rec import an_account_of

pytestmark = [pytest.mark.django_db, requires_postgres]

POSTED = datetime(2026, 10, 14, 15, 0, tzinfo=UTC)


def _posted(actor, tenant):
    account = an_account_of(actor, tenant)
    recorded = services.record_payment(
        actor,
        account_id=account.pk,
        amount=Decimal("300.00"),
        posted_at=POSTED,
        method_code="cash",
        idempotency_reference=uuid.uuid4(),
    )
    payment = payment_models.Payment.objects.get(pk=recorded.payment_id)
    assert payment.status == payment_models.PAYMENT_POSTED
    return payment


def _update(sql, params):
    with connection.cursor() as cursor:
        cursor.execute(sql, params)


def _refused(sql, params, match):
    with pytest.raises(DatabaseError) as refusal, transaction.atomic():
        _update(sql, params)
    assert match in str(refusal.value), str(refusal.value)
    return str(refusal.value)


def test_pg_posted_to_cleared_with_its_date_is_allowed(brazos, marcus):
    with tenant_ctx(brazos):
        p = _posted(marcus, brazos)
        _update(
            "UPDATE payments SET status='cleared', cleared_at=%s WHERE id=%s",
            [datetime(2026, 10, 16, tzinfo=UTC), p.pk],
        )
        p.refresh_from_db()
        assert p.status == "cleared" and p.cleared_at.date().isoformat() == "2026-10-16"


def test_pg_posted_to_cancelled_is_allowed(brazos, marcus):
    with tenant_ctx(brazos):
        p = _posted(marcus, brazos)
        _update("UPDATE payments SET status='cancelled' WHERE id=%s", [p.pk])
        p.refresh_from_db()
        assert p.status == "cancelled"


def test_pg_posted_refuses_every_other_column(brazos, marcus):
    with tenant_ctx(brazos):
        p = _posted(marcus, brazos)
        _refused("UPDATE payments SET amount=1 WHERE id=%s", [p.pk], "append-only")
        _refused(
            "UPDATE payments SET status='cleared', cleared_at=now(), amount=1 WHERE id=%s",
            [p.pk],
            "append-only",
        )


def test_pg_posted_refuses_any_other_status(brazos, marcus):
    with tenant_ctx(brazos):
        p = _posted(marcus, brazos)
        for target in ("processing", "failed", "reversed"):
            _refused(
                "UPDATE payments SET status=%s WHERE id=%s", [target, p.pk], "may move only to"
            )


def test_pg_clearing_needs_its_date_and_a_date_needs_the_clearing(brazos, marcus):
    with tenant_ctx(brazos):
        p = _posted(marcus, brazos)
        _refused("UPDATE payments SET status='cleared' WHERE id=%s", [p.pk], "without its clearing date")
        _refused("UPDATE payments SET cleared_at=now() WHERE id=%s", [p.pk], "only as it moves to cleared")


def test_pg_cleared_is_frozen_both_back_to_posted_and_its_date(brazos, marcus):
    with tenant_ctx(brazos):
        p = _posted(marcus, brazos)
        _update(
            "UPDATE payments SET status='cleared', cleared_at=%s WHERE id=%s",
            [datetime(2026, 10, 16, tzinfo=UTC), p.pk],
        )
        _refused("UPDATE payments SET status='posted' WHERE id=%s", [p.pk], "append-only")
        _refused("UPDATE payments SET cleared_at=now() WHERE id=%s", [p.pk], "append-only")
        _refused("UPDATE payments SET status='cancelled' WHERE id=%s", [p.pk], "append-only")


def test_pg_cancelled_is_frozen(brazos, marcus):
    with tenant_ctx(brazos):
        p = _posted(marcus, brazos)
        _update("UPDATE payments SET status='cancelled' WHERE id=%s", [p.pk])
        _refused("UPDATE payments SET status='posted' WHERE id=%s", [p.pk], "append-only")


def test_pg_delete_is_refused_in_every_status(brazos, marcus):
    with tenant_ctx(brazos):
        p = _posted(marcus, brazos)
        _refused("DELETE FROM payments WHERE id=%s", [p.pk], "cannot be removed")


def test_pg_the_deployed_body_carries_the_clearing_array(brazos):
    with connection.cursor() as cursor:
        cursor.execute("SELECT prosrc FROM pg_proc WHERE proname='payments_payment_immutable'")
        body = cursor.fetchone()[0]
    assert "clearing text[] := ARRAY['status', 'cleared_at', 'updated_at']" in body
    assert "OLD.status = 'posted'" in body


# ── payments/0052 · PO 2026-10-21 "Allow, back to Posted" ─────────────────
def _cleared(actor, tenant):
    p = _posted(actor, tenant)
    _update(
        "UPDATE payments SET status='cleared', cleared_at=%s WHERE id=%s",
        [datetime(2026, 10, 16, tzinfo=UTC), p.pk],
    )
    return p


def _window(value):
    _update("SELECT set_config('app.payment_unclearing', %s, true)", [value])


def test_pg_unreconcile_window_lets_cleared_go_back_to_posted(brazos, marcus):
    with tenant_ctx(brazos), transaction.atomic():
        p = _cleared(marcus, brazos)
        _window(str(p.deposit_batch_id))
        _update("UPDATE payments SET status='posted', cleared_at=NULL WHERE id=%s", [p.pk])
        p.refresh_from_db()
        assert p.status == payment_models.PAYMENT_POSTED and p.cleared_at is None
        # and it can clear again, with the new reconciliation's date
        _window("")
        _update(
            "UPDATE payments SET status='cleared', cleared_at=%s WHERE id=%s",
            [datetime(2026, 10, 17, tzinfo=UTC), p.pk],
        )


def test_pg_back_to_posted_is_refused_without_the_window(brazos, marcus):
    with tenant_ctx(brazos):
        p = _cleared(marcus, brazos)
        _refused(
            "UPDATE payments SET status='posted', cleared_at=NULL WHERE id=%s",
            [p.pk],
            "append-only",
        )


def test_pg_back_to_posted_is_refused_for_another_batchs_window(brazos, marcus):
    with tenant_ctx(brazos):
        p = _cleared(marcus, brazos)
        with pytest.raises(DatabaseError) as refusal, transaction.atomic():
            _window(str(uuid.uuid4()))
            _update("UPDATE payments SET status='posted', cleared_at=NULL WHERE id=%s", [p.pk])
        assert "append-only" in str(refusal.value)


def test_pg_the_window_moves_status_and_date_only(brazos, marcus):
    with tenant_ctx(brazos):
        p = _cleared(marcus, brazos)
        with pytest.raises(DatabaseError) as refusal, transaction.atomic():
            _window(str(p.deposit_batch_id))
            _update(
                "UPDATE payments SET status='posted', cleared_at=NULL, amount=amount+1 WHERE id=%s",
                [p.pk],
            )
        assert "amount" in str(refusal.value)
        with pytest.raises(DatabaseError) as refusal, transaction.atomic():
            _window(str(p.deposit_batch_id))
            _update("UPDATE payments SET status='posted' WHERE id=%s", [p.pk])
        assert "without a clearing date" in str(refusal.value)
        with pytest.raises(DatabaseError), transaction.atomic():
            _window(str(p.deposit_batch_id))
            _update("UPDATE payments SET status='cancelled' WHERE id=%s", [p.pk])


def test_pg_the_deployed_body_carries_the_unclearing_door(brazos):
    with connection.cursor() as cursor:
        cursor.execute("SELECT prosrc FROM pg_proc WHERE proname='payments_payment_immutable'")
        body = cursor.fetchone()[0]
    assert "unclearing text[] := ARRAY['status', 'cleared_at', 'updated_at']" in body
    assert "current_setting('app.payment_unclearing', true)" in body
