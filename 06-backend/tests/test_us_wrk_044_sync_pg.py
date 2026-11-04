# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-044 TC-3 (a duplicate key inside a batch does not poison the
#           rest) · TC-6 (a swapped phone) · US-WRK-046 TC-4/TC-5 (a refusal
#           rolls the acceptance back)
# Rules:    BR-WRK-042 · BR-WRK-003 · CLAUDE.md hard rule 1 (RLS FORCE) ·
#           **hard-won law 14** — the reason this file exists at all
# Tests:    this file — skipped on SQLite BY DESIGN, and the skip is the point
# ───────────────────────────────────────────────────────
"""US-WRK-044 — the three guarantees the suite's own database cannot check.

Run it with a real database, as a role that row security actually applies to::

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
        DATABASE_URL=postgres://sbh_gate_iso:sbh_gate_iso@localhost:5432/sbh_rlsrole \\
        pytest tests/test_us_wrk_044_sync_pg.py --reuse-db

⚠ **THE SAVEPOINT IS WHY THIS FILE EXISTS, AND IT IS HARD-WON LAW 14 EXACTLY.**
`apps/work/sync.py` applies each item inside a nested `transaction.atomic()`.
Written the obvious way instead — `try: apply(item) except IntegrityError:
continue` — **the whole PostgreSQL transaction aborts on the first duplicate
key**: every later statement raises `InFailedSqlTransaction` and everything that
had succeeded is discarded at COMMIT. A duplicate on item 5 of 20 therefore
destroys items 1–4 as well as 6–20, while the response cheerfully reports 19
accepted.

**And the suite cannot see any of it.** `config/settings/test.py` hardcodes
in-memory SQLite and ignores `DATABASE_URL`; SQLite has **no aborted-transaction
state**, so the broken version passes every case in
`tests/test_us_wrk_044_046_sync.py`, green, on every machine — including the
duplicate-key case, which is the one that looks like it would catch it.

⚠ **AND A RUN AS THE ORDINARY `smartbillhub` ROLE PROVES NOTHING ABOUT THE RLS
CASE EITHER**: it holds SUPERUSER, and PostgreSQL exempts a superuser from row
security unconditionally, `FORCE` included (`DEF-2717`). The `rls` fixture
REFUSES rather than skips when handed a bypassing role, which is what makes a
green here mean something.
"""

from __future__ import annotations

import pytest
from django.db import connection

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.metering import models as metering_models
from apps.work import models as work_models
from apps.work import sync
from apps.work.sync_models import WorkSyncReceipt
from tests.isolation_helpers import (  # noqa: F401 — `rls` needs `rls_probe_role`
    assert_denied_without_context,
    assert_rls_scoped,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import field_actor  # CR-168 P1.34 — sync as the field
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_wrk_044_046_sync import _batch, _order_on_a_meter, _rows

pytestmark = [pytest.mark.django_db, requires_postgres]


# ══════════════════════════════════════════════════════════════════════════
# 1 · LAW 14 — one refused item, and the other nineteen still commit
# ══════════════════════════════════════════════════════════════════════════
def test_tc3_044_a_duplicate_key_inside_a_batch_does_not_poison_the_rest(brazos, dana):
    """TC-3 — item 5 of the batch carries a key already accepted.

    **Items 1–4 and 6–N COMMIT; item 5 answers *duplicate*.**

    ⚠ **THIS IS THE ONE CASE IN WAVE L THAT THE SQLITE SUITE CANNOT DISTINGUISH
    FROM ITS OWN OPPOSITE.** Without the savepoint in `sync.py`, on this
    database the `IntegrityError` raised by item 5 aborts the transaction and
    every later item raises `InFailedSqlTransaction`; the receipts written for
    items 1–4 are discarded at COMMIT and the day's work is lost. Run the same
    broken code on SQLite and this file's assertions all pass.
    """
    with tenant_ctx(brazos):
        oid = _order_on_a_meter(dana, brazos)
        rows = _rows(oid)
        items = _batch(oid, rows)["items"]
        assert len(items) >= 6, "the fixture must be long enough for an item 5"

        # ⚠ **THE DUPLICATE MUST ARRIVE *INSIDE* THE BATCH, AND THE FIRST DRAFT
        # OF THIS CASE GOT IT WRONG IN A WAY THAT MADE IT UNABLE TO FAIL.**
        #
        # It delivered item 5 in a SEPARATE call first, so by the time the batch
        # arrived its key was already in the receipts table — and `sync_batch`'s
        # cheap `exists()` read answered *duplicate* and moved on **without ever
        # touching the unique constraint**. No `IntegrityError` was raised, so
        # the savepoint was never exercised, and the case passed with the
        # savepoint DELETED. Found by running the law-7 sabotage rather than by
        # reading the test (`DEF-WRK-4079`).
        #
        # A duplicate WITHIN one batch is also the real-world shape: a handset
        # that re-queued an item it had already queued sends both in the same
        # flush. The first `create` succeeds; the SECOND hits
        # `uq_work_sync_receipts_key` — which is the only path on which a failed
        # statement can poison this transaction.
        items.insert(5, {**items[2], "seq": 99})

        out = sync.sync_batch(field_actor(oid, dana), oid, {"items": items})

        # ── The assertion law 14 is about ─────────────────────────────────
        # Item 5 (index 5) is the repeat of item 3. Everything before it and
        # everything after it must still land.
        assert out["items"][5]["result"] == "duplicate", out["items"][5]
        assert out["duplicate"] == 1, out
        assert out["accepted"] == len(items) - 1, out
        assert out["refused"] == 0, [i for i in out["items"] if i["result"] == "refused"]

        # …and it is TRUE AFTER COMMIT, not merely in the response. A poisoned
        # transaction reports the same numbers and then throws the rows away —
        # so the count is the assertion that cannot be satisfied by a response
        # object alone.
        assert WorkSyncReceipt.objects.filter(work_order_id=oid).count() == len(items) - 1
        order = work_tables.WorkOrder.objects.get(pk=oid)
        assert order.state == "completed", "the close was lost with the aborted transaction"
        assert order.completed_at.isoformat().startswith("2026-03-15T16:07")


def test_044_the_batch_survives_a_REFUSAL_too_not_only_a_duplicate(brazos, dana):
    """The same trap on the other error path.

    A refused item raises a `BizError`, not an `IntegrityError` — but by then
    the statement inside its savepoint may already have failed at the database,
    and without the savepoint that poisons the transaction identically. Proving
    only the duplicate case would leave half the mechanism unchecked.

    ⚠ **REWRITTEN 2026-10-04 TO THE PO's NO-DROP RULE (`DEF-WRK-9659`).** This
    case sent a task tick naming a row that belongs to no job and expected
    *refused*. Since `TECHNICIAN SYNC DESIGN` (2) — *"we cant drop data record
    in sync process both ways"* — the server STORES such an item and flags it
    *Needs review* (`held_for_review`), so the case no longer reached a refusal
    at all and went red on PostgreSQL (it skips on SQLite, which is why
    FIELD-FIX's run never saw it). **The one refusal left for a technician's
    genuine item is the safety lock (`BIZ-LOCKED`)**, which the technician fixes
    on the spot and which stays in the phone's outbox, so it drops nothing. So
    the refused item is now a task ticked BEFORE the safety rows, between good
    items — and the held case is asserted beside it, so both the ruled
    behaviours are pinned.

    ⚠ **AMENDED AGAIN 2026-10-21 — THE HELD CASE IS GONE.** PO, *"back to the
    technician"*: `BR-WRK-063` is superseded for field items, so the bad task
    tick is REFUSED too, with its reason, and stores nothing. Both refusals
    sit between good items, which makes this case a stronger proof of the
    savepoint than before — two failed statements, not one, and everything
    around them still commits.
    """
    with tenant_ctx(brazos):
        oid = _order_on_a_meter(dana, brazos)
        rows = _rows(oid)
        assert len(rows["safety"]) >= 2, "the lock needs a safety row still unticked"
        items = _batch(oid, rows)["items"]
        # Item 2 of the queue: a task ticked while a safety row is still open.
        items.insert(1, {
            "key": "ortiz-01-2026-03-15-locked",
            "kind": "task_tick",
            "seq": 98,
            "captured_at": "2026-03-15T15:16:00Z",
            "payload": {"task_id": str(rows["tasks"][0].id)},
        })
        # …and a task tick naming a row that belongs to no job: refused BACK.
        items.insert(5, {
            "key": "ortiz-01-2026-03-15-bad",
            "kind": "task_tick",
            "seq": 99,
            "captured_at": "2026-03-15T15:30:00Z",
            "payload": {"task_id": "00000000-0000-0000-0000-000000000000"},
        })
        out = sync.sync_batch(field_actor(oid, dana), oid, {"items": items})

        assert out["items"][1]["result"] == "refused", out["items"][1]
        assert out["items"][5]["result"] == "refused", out["items"][5]
        assert out["items"][5]["ack"] is False
        assert out["refused"] == 2 and out["held_for_review"] == 0, out
        assert out["accepted"] == len(items) - 2, out
        # The items after the refusal still COMMIT — the assertion law 14 is about.
        assert work_tables.WorkOrder.objects.get(pk=oid).state == "completed"
        # A refused item leaves NO receipt — it takes it down with the savepoint
        # — so the phone may legitimately re-queue the same key. Since
        # 2026-10-21 that is true of every refusal: the phone holds the item.
        assert not WorkSyncReceipt.objects.filter(
            work_order_id=oid, key="ortiz-01-2026-03-15-locked"
        ).exists()
        assert not WorkSyncReceipt.objects.filter(
            work_order_id=oid, key="ortiz-01-2026-03-15-bad"
        ).exists()


# ══════════════════════════════════════════════════════════════════════════
# 2 · RLS — read out of pg_class, not out of the migration
# ══════════════════════════════════════════════════════════════════════════
def test_rls_is_enabled_and_forced_on_the_receipts_table():
    """`relrowsecurity` AND `relforcerowsecurity`, from the catalogue.

    ⚠ **`ENABLE` ALONE WOULD BE A HOLE**: it exempts the table's OWNER, and the
    application's migration role owns every table in this schema. Read from
    `pg_class` rather than trusting that `work/0019` ran — a migration that ran
    is not a policy that exists (hard-won law 1).
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
            "WHERE relname = 'work_sync_receipts'"
        )
        assert cursor.fetchone() == (True, True)


def test_tc6_044_a_receipt_is_invisible_across_the_tenant_boundary(rls, brazos, lonestar, dana):
    """TC-6 — and the damage a leak here would do is DESTRUCTION, not exposure.

    A receipt is the server's answer to *have I seen this key before*. Visible
    across a boundary, a Lone Star phone queueing an item whose short key
    happened to equal a Brazos Bend key would be told **duplicate**, and its
    safety tick, its reading or its CLOSE would be dropped with the sync
    reporting success — in the one place a technician has no way to notice.
    """
    with tenant_ctx(brazos):
        oid = _order_on_a_meter(dana, brazos)
        rows = _rows(oid)
        sync.sync_batch(field_actor(oid, dana), oid, _batch(oid, rows))
        ids = set(
            str(v)
            for v in WorkSyncReceipt.objects.filter(work_order_id=oid).values_list("id", flat=True)
        )

    assert_rls_scoped(
        rls, "work_sync_receipts", owner=brazos, intruder=lonestar, owner_ids=ids
    )


def test_the_receipts_table_is_denied_with_no_tenant_in_context(rls):
    """Deny by default. An unset `app.tenant_id` reads NOTHING rather than
    everything — `OQ-354`/`DEF-622`'s `NULLIF` form."""
    assert_denied_without_context(rls, "work_sync_receipts")


# ══════════════════════════════════════════════════════════════════════════
# 3 · US-WRK-046 TC-4/TC-5 — a refused read rolls the ACCEPTANCE back
# ══════════════════════════════════════════════════════════════════════════
def test_tc5_046_a_read_the_pipeline_refuses_rolls_the_whole_acceptance_back(brazos, dana):
    """TC-5 — the order stays on `Work-009` and the meter gains nothing.

    ⚠ **ON SQLITE THIS PASSES WHATEVER THE CODE DOES.** `accept_field_result`
    runs in one `transaction.atomic()`; whether that rollback is real is a
    property of the database, and the suite's own has no aborted-transaction
    state to make it observable. Here the refusal is genuine.

    *"Accepting field data the read pipeline refuses would activate a service
    off a reading that does not exist"* — `BR-MET-129` (2), in its own words.
    """
    from core import errors

    with tenant_ctx(brazos):
        oid = _order_on_a_meter(dana, brazos)
        sync.sync_batch(field_actor(oid, dana), oid, _batch(oid, _rows(oid)))
        # A NEGATIVE register value: the read pipeline's own ERROR (*"a register
        # cannot read negative"*), refused before anything commits.
        work_models.WorkOrderReading.objects.filter(
            work_order_id=oid, posts_as_meter_read=True
        ).update(value="-1")
        # ⚠ **A DELTA, NOT AN ABSOLUTE.** `config.settings.local` seeds a whole
        # sample utility, so this tenant already carries hundreds of meter reads
        # and `== 0` would be measuring the fixture rather than the code — which
        # is what it did until the sabotage run printed `assert 403 == 0`.
        before_reads = metering_models.MeterRead.objects.filter(tenant_id=brazos.id).count()

        with pytest.raises(errors.ApiError):
            w6.accept_field_result(dana, oid)

        order = work_tables.WorkOrder.objects.get(pk=oid)
        assert order.accepted_at is None, "the order was accepted over a refused read"
        assert order.accepted_by_id is None
        assert (
            metering_models.MeterRead.objects.filter(tenant_id=brazos.id).count() == before_reads
        ), "a read was posted over a refused acceptance"
