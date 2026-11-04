# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 lane S-SYNC — T-31 (tombstones) and T-32 (the per-table
#           cursor) on real PostgreSQL
# Rules:    R56 · R57 · BR-WRK-063 · BR-WRK-025 (assignment history is
#           append-only) · CLAUDE.md hard rule 1 · hard-won laws 1 and 14
# Tests:    this file — skipped on SQLite BY DESIGN
# ───────────────────────────────────────────────────────
"""The change feed on the database production runs.

Two things SQLite cannot show: the keyset compares UUIDs as PostgreSQL orders
them (the cursor's id half is a `uuid > %s` on this database and a string
compare on SQLite), and the *deleted* tombstone the feed does NOT have is
justified by a refusal only PostgreSQL enforces — the append-only trigger on
`work_order_assignments` (`work/0009`) and the foreign key on `work_orders`.
"""

from __future__ import annotations

import pytest
from django.db import connection, transaction
from django.db.models.deletion import ProtectedError

from apps.work import connection_models as work_tables
from apps.work import models as work_models
from tests import test_cr187_sync_feed as feed
from tests.isolation_helpers import requires_postgres
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_ten_helpers import tenant_ctx

pytestmark = [pytest.mark.django_db, requires_postgres]


# ══════════════════════════════════════════════════════════════════════════
# The SQLite cases, re-run here — uuid keysets and the history walk
# ══════════════════════════════════════════════════════════════════════════
def test_the_reassign_tombstone_holds_on_postgres(brazos, dana):
    feed.test_a_reassigned_job_arrives_as_a_tombstone_for_the_old_technician(brazos, dana)


def test_the_unassign_tombstone_holds_on_postgres(brazos, dana):
    feed.test_an_unassigned_job_arrives_as_a_tombstone(brazos, dana)


def test_the_schedule_tombstone_holds_on_postgres(brazos, dana):
    feed.test_a_SCHEDULE_naming_somebody_else_moves_the_job_with_no_unassign_row_and_still_tombstones(
        brazos, dana
    )


def test_the_cancel_tombstone_holds_on_postgres(brazos, dana):
    feed.test_a_cancelled_job_arrives_as_a_tombstone_and_leaves_the_day(brazos, dana)


def test_the_day_cursor_delta_holds_on_postgres(brazos, dana):
    feed.test_the_day_read_hands_out_a_cursor_and_the_refresh_after_it_is_a_delta(brazos, dana)


def test_the_paging_holds_on_postgres(brazos, dana):
    feed.test_the_feed_pages_with_no_cap_and_loses_or_doubles_nothing(brazos, dana)


def test_the_tenant_boundary_holds_on_postgres(brazos, dana, lonestar, erin):
    feed.test_a_second_tenants_jobs_never_appear_in_the_feed(brazos, dana, lonestar, erin)


# ══════════════════════════════════════════════════════════════════════════
# T-31 · "deleted" cannot happen to a job anybody was given — at the database
# ══════════════════════════════════════════════════════════════════════════
def test_a_job_anybody_was_given_cannot_be_deleted_so_it_needs_no_deleted_tombstone(brazos, dana):
    """The feed has no *deleted* reason, and this is why: proved here rather
    than assumed (hard-won law 1). Three doors, all shut:

    * the ORM — `WorkOrderAssignment.work_order` is `PROTECT`;
    * the history — `work/0009`'s trigger refuses DELETE on the append-only
      `work_order_assignments`, so the protection cannot be cleared first;
    * raw SQL on the order — the foreign key, checked immediately.

    Each attempt runs in its OWN savepoint, which is law 14 again: the first
    refusal would otherwise abort the transaction and the next two would
    "pass" on `InFailedSqlTransaction` instead of on their own refusal — the
    `"aborted" not in …` assertions are there to tell the two apart.
    """
    assert connection.vendor == "postgresql"
    with tenant_ctx(brazos):
        feed._seed()
        ortiz = feed._technician(brazos, "d-ortiz@brazos.test", "D. Ortiz")
        oid = feed._raise(dana, "221 Oak Ave")
        feed._assign(dana, oid, ortiz)

        with pytest.raises(ProtectedError):
            with transaction.atomic():
                work_tables.WorkOrder.objects.filter(pk=oid).delete()

        with pytest.raises(Exception) as history:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("DELETE FROM work_order_assignments WHERE work_order_id = %s", [oid])
        assert "aborted" not in str(history.value), history.value

        with pytest.raises(Exception) as order:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
                    cursor.execute("DELETE FROM work_orders WHERE id = %s", [oid])
        message = str(order.value).lower()
        assert "aborted" not in message, order.value
        assert "foreign key" in message or "violates" in message, order.value

        assert work_tables.WorkOrder.objects.filter(pk=oid).exists()
        assert work_models.WorkOrderAssignment.objects.filter(work_order_id=oid).count() >= 1
