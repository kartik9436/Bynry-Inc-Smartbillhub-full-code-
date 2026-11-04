# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-PAY-10700 (lockbox audit LBX-01 — a $0.00 batch reconciles)
# Rulings:  decision log 2026-10-30 "LBX-01, LBX-02 and LBX-04 are fixed (PO)";
#           2026-10-21 CR-186-BRC10 — reconciling a batch clears its payments
# Rules:    CLAUDE.md hard rule 4 (payments/0051's `clearing` list — the one
#           door a posted payment moves through) · hard rule 7 (audit) ·
#           hard-won law 14 (proved on PostgreSQL, NON-superuser role)
# ───────────────────────────────────────────────────────
"""LBX-01 on PostgreSQL — the one-click *Reconcile ✓* clears six cheques.

The screen's *Reconcile ✓* (`DepositBatchPage.handleReconcileAtZero`) posts
`/deposit-batches/{id}/reconcile` with `resolutions: []`. That server path was
proved only on SQLite until lane FINAL-WALK (2026-10-30). SQLite has no RLS, no
`payments_payment_immutable()` trigger and no aborted-transaction state, so the
one thing it cannot show is that the trigger's `clearing` list really lets the
six `posted` rows move to `cleared` under an app role that cannot bypass RLS.

The tester's day: DEP-261026-0007, six cheques **$870.50**, the bank's
**$870.50** line auto-matched on import, difference **$0.00** → Reconcile ✓ → six
payments **Cleared** on the bank line's date, one `payment.cleared` audit row
each, and a second press is refused by name and changes nothing.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest
from django.db import connection

from apps.payments import api as payments_api
from apps.payments import bankrec_models as bankrec
from apps.payments import models, reconciliation
from apps.payments import settings_seam

from tests.isolation_helpers import requires_postgres
from tests.test_lbx05_09_statement_lines_post import (
    WORKED_AT,
    import_the_statement,
    line,
    the_lockbox_day,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana · audit_rows
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_020_023_bankrec_surface import call

pytestmark = [pytest.mark.django_db, requires_postgres]


def test_pg_the_role_is_not_a_superuser():
    with connection.cursor() as cursor:
        cursor.execute("select rolsuper, rolbypassrls from pg_roles where rolname = current_user")
        assert cursor.fetchone() == (False, False)


def test_lbx01_pg__reconcile_at_zero_clears_the_six_cheques(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        payments, batch = the_lockbox_day(dana, brazos)
        assert batch.recorded_total == Decimal("870.50")
        statement_id = import_the_statement(dana, brazos).statement_import_id
        deposit_line = line(statement_id, "LBX4521-1026")

        # The import auto-matched the bank's $870.50 line to the batch
        # (the tester's "auto-matched, difference $0.00"): nothing to explain.
        batch.refresh_from_db()
        assert batch.status == bankrec.BATCH_MATCHED
        assert deposit_line.deposit_batch_id == batch.pk

        # Exactly the body the screen's Reconcile ✓ sends.
        body = {"posted_at": WORKED_AT.isoformat(), "resolutions": []}
        first = call(
            payments_api.deposit_batch_reconcile,
            "post",
            brazos,
            user=dana,
            data=body,
            batch_id=str(batch.pk),
        )
        assert first.status_code == 200, first.data
        assert Decimal(first.data["difference"]) == Decimal("0")
        assert Decimal(first.data["recorded_total"]) == Decimal("870.50")
        assert first.data["resolutions"] == []

    # `api_call` enters and LEAVES the tenant context around the view, which
    # puts `app.tenant_id` back to the nil tenant; RLS then (correctly) shows
    # nothing. Re-enter it before reading, as the next request would.
    with tenant_ctx(brazos):
        rows = list(models.Payment.objects.filter(deposit_batch_id=batch.pk).order_by("confirmation"))
        assert [row.confirmation for row in rows] == ["4101", "4102", "4103", "4104", "4105", "4106"]
        assert {row.status for row in rows} == {models.PAYMENT_CLEARED}
        # The clearing date is the BANK's: the matched line's posting date, at
        # midnight in the utility's own zone.
        zone = settings_seam.tenant_timezone()
        assert {row.cleared_at.astimezone(zone).date() for row in rows} == {deposit_line.posted_on}
        assert deposit_line.posted_on == date(2026, 10, 27)
        cleared_rows = [r for r in audit_rows if r["action"] == reconciliation.AUDIT_PAYMENT_CLEARED]
        assert len(cleared_rows) == 6
        assert bankrec.DepositBatch.objects.get(pk=batch.pk).status == bankrec.BATCH_RECONCILED

        # A second press is refused by name (the batch is LOCKED, BR-PAY-004)
        # and changes nothing.
        again = call(
            payments_api.deposit_batch_reconcile,
            "post",
            brazos,
            user=dana,
            data=body,
            batch_id=str(batch.pk),
        )
        assert again.status_code == 422, again.data
        assert "LOCKED" in again.data["params"]["detail"]
    with tenant_ctx(brazos):
        assert models.Payment.objects.filter(
            deposit_batch_id=batch.pk, status=models.PAYMENT_CLEARED
        ).count() == 6
        assert len([r for r in audit_rows if r["action"] == reconciliation.AUDIT_PAYMENT_CLEARED]) == 6

        # And the connection is still usable afterwards (hard-won law 14).
        with connection.cursor() as cursor:
            cursor.execute("select 1")
            assert cursor.fetchone() == (1,)
        assert isinstance(rows[0].cleared_at, datetime)
