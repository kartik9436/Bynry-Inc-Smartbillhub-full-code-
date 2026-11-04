# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-037 TC-2 (proved on PostgreSQL; the same test with the
#           savepoint removed fails with InFailedSqlTransaction)
# Rules:    BR-BIL-1052 · CLAUDE.md hard-won law 14
# Proof:    10-scripts/bbr_check_engine_pg_proof.py (green, and red with the
#           savepoints removed)
# ───────────────────────────────────────────────────────
# BULK-CHG-27 (plan T2: the per-account savepoint, on PostgreSQL)
"""A DATABASE error on one account never poisons the next — on PostgreSQL.

SQLite has no aborted-transaction state, so on the default suite this passes
with or without the savepoints and proves nothing; it is skipped there. On
PostgreSQL a failed statement aborts the whole transaction, and only the
per-check / per-account `transaction.atomic()` in `check_engine` lets the
next account be checked.
"""

from __future__ import annotations

import pytest
from django.db import connection

from apps.billing import gather, runs

from tests.test_bbr_check_engine import BILL_DATE, PERIOD_END, PERIOD_START, three_accounts
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


# BULK-CHG-26
@pytest.mark.skipif(connection.vendor != "postgresql", reason="law 14: PostgreSQL only")
def test_tc2_pg__a_database_error_on_the_middle_account_blocks_only_it(brazos, dana, monkeypatch):
    real = gather.gather_account

    def double(**kwargs):
        if kwargs["account"].account_no == "A-00102":
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1 / 0")  # a real statement error: division_by_zero
        return real(**kwargs)

    monkeypatch.setattr(gather, "gather_account", double)
    with tenant_ctx(brazos):
        cycle, _plan, _accounts = three_accounts(brazos, dana)
        prepared = runs.prepare_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=BILL_DATE,
        )
    print(
        "\nPROOF pg savepoint: ready="
        + ",".join(sorted(d.account_no for d in prepared.ready))
        + " blocked="
        + ",".join(f"{p.account_no}:{p.reason}" for p in prepared.blocked)
    )
    assert sorted(d.account_no for d in prepared.ready) == ["A-00101", "A-00106"]
    assert [(p.account_no, p.reason) for p in prepared.blocked] == [
        ("A-00102", "check_failed_unexpectedly")
    ]
