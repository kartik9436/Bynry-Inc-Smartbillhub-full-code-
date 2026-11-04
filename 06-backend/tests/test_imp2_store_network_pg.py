# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-PAY-10759 · migration payments/0054
# Ruling:   decision log 2026-10-30 "Eight open payment questions answered
#           (PO)" — Q6 (the store network name from a column in the file)
# Rules:    CLAUDE.md hard rule 4 (the name is frozen after INSERT) · hard-won
#           law 14 (proved on PostgreSQL, under a NON-superuser role)
# ───────────────────────────────────────────────────────
"""The database half of Q6.

1. The 29 Oct file (two lockbox rows, two Hy-Vee rows) banks in two batches on
   PostgreSQL too — the per-row SAVEPOINT loader and the channel-day uniques are
   the real ones here.
2. `payments.store_network` cannot be changed after INSERT: the immutability
   trigger compares the whole row, so `payments/0054` needed no trigger change.
"""

from __future__ import annotations

import pytest
from django.db import DatabaseError, connection, transaction

from apps.payments import models as payment_models

from tests.isolation_helpers import requires_postgres
from tests.test_imp2_store_network import (
    test_lockbox_and_hy_vee_rows_on_29_oct_bank_in_two_batches as _two_batches,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx

pytestmark = [pytest.mark.django_db, requires_postgres]


def test_two_batches_on_postgres(brazos, dana):
    _two_batches(brazos, dana)


def test_the_network_name_is_frozen_after_insert(brazos, dana):
    _two_batches(brazos, dana)
    with tenant_ctx(brazos):
        payment = payment_models.Payment.objects.filter(store_network="Hy-Vee").first()
        assert payment is not None
        with pytest.raises(DatabaseError):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE payments SET store_network = %s WHERE id = %s",
                        ["CheckFreePay", str(payment.pk)],
                    )
        payment.refresh_from_db()
        assert payment.store_network == "Hy-Vee"
