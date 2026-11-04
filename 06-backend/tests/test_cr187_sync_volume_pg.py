# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 lane S-SYNC — T-46 (the savepoint proof on real
#           PostgreSQL) and T-30 (1,000 readings in 20 batches of 50) on the
#           database production runs
# Rules:    R47 (a savepoint around each item; one refused row never costs
#           the other forty-nine) · BR-WRK-042 · **hard-won law 14** · law 7
#           (a guard is proved red before it is trusted green)
# Tests:    this file — skipped on SQLite BY DESIGN, and the skip is the point
# ───────────────────────────────────────────────────────
"""The savepoint, proved where it matters, and proved able to FAIL.

Run it on PostgreSQL::

    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.pgtest \\
        DATABASE_URL=postgres://… JOBS_EAGER=false \\
        pytest tests/test_cr187_sync_volume_pg.py --ds=config.settings.pgtest

⚠ **THE POISON IS A REAL FAILED STATEMENT, AND THE FIRST CHOICE WOULD NOT HAVE
BEEN ONE.** A duplicate key repeated inside one batch looks like the obvious
way to make the database refuse a row — but `sync._one_item` reads the receipts
table BEFORE inserting, and inside one transaction that read SEES the first
copy, so the repeat answers *duplicate* without the unique constraint ever
firing and the savepoint is never exercised. So the poison here is a reading of
`1e20`: `work_order_readings.value` is `NUMERIC(18,4)`, the receipt INSERT
succeeds, and the UPDATE of the reading is refused by PostgreSQL with
`numeric field overflow` — a failed statement INSIDE the item, which is exactly
the case law 14 is about. (SQLite stores it without complaint, which is the
other half of why this file exists.)

⚠ **WHAT THE BROKEN VERSION ACTUALLY DOES IS WORSE THAN A LOST BATCH.** Proved
2026-10-21 by deleting ONLY the item's `with transaction.atomic():` in
`sync._one_item` and running the poison case here: item 25 came back
`'result': 'duplicate'` with `ack: True`. `evidence.set_reading` wraps its own
save in a savepoint, so the overflow rolled back only the reading; the receipt
written before it SURVIVED, `_hold` then hit the unique key, and the item was
answered *duplicate* — **acknowledged, so the phone deletes it, over a reading
the server never stored.** Silent loss with every count looking right; both
poison cases below went red on it (`accepted: 24, duplicate: 1`).

⚠ **AND THE RED PROOF IS IN THE FILE, NOT ONLY IN A COMMIT MESSAGE.**
`test_without_the_savepoint_the_same_batch_is_LOST_on_postgres` strips the
nested `atomic()` out of `apps/work/sync.py` for one run and asserts the batch
dies — so a future change that made the poison stop poisoning (and this whole
file prove nothing) goes red here first.
"""

from __future__ import annotations

import contextlib
import time

import pytest
from django.db import connection, transaction

from apps.work import sync
from apps.work import models as work_models
from apps.work.sync_models import WorkSyncReceipt
from tests.isolation_helpers import requires_postgres
from tests.test_cr187_sync_volume import (
    BATCH,
    READINGS,
    RETRIED,
    as_field,
    assert_landed_once,
    batches,
    read_route,
    reading_items,
    seed_reference,
    send_the_day,
    technician,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_ten_helpers import tenant_ctx

pytestmark = [pytest.mark.django_db, requires_postgres]

#: Position (0-based) of the poisoned item inside each batch of fifty.
POISON_AT = 24


def _poison(items):
    """Every batch's 25th reading is `1e20` — refused by PostgreSQL."""
    out = []
    for batch in batches(items):
        batch = [dict(i, payload=dict(i["payload"])) for i in batch]
        batch[POISON_AT]["payload"]["value"] = "1e20"
        out.extend(batch)
    return out


# ══════════════════════════════════════════════════════════════════════════
# T-30 on PostgreSQL — the same day the SQLite file sends, on the real thing
# ══════════════════════════════════════════════════════════════════════════
def test_1000_readings_in_20_batches_with_two_retried_mid_way_land_once_on_postgres(brazos, dana, audit_rows):
    assert connection.vendor == "postgresql"
    with tenant_ctx(brazos):
        seed_reference()
        tech = technician(brazos)
        oid, rows = read_route(dana, brazos, tech, readings=READINGS)
        timings = []

        def send(batch):
            started = time.monotonic()
            out = sync.sync_batch(as_field(tech), oid, {"items": batch})
            timings.append(time.monotonic() - started)
            return out

        totals = send_the_day(send, reading_items(oid, rows))
        assert_landed_once([(oid, rows)], audit_rows)

    assert totals["accepted"] == READINGS and totals["duplicate"] == RETRIED[7] + RETRIED[13], totals
    # Data.txt §4: *"a web worker is given sixty seconds"*. Printed for the
    # record (`-s`), asserted only against the worker's own limit.
    print(f"\n[T-30 pg] {len(timings)} requests · slowest {max(timings):.2f}s · "
          f"total {sum(timings):.1f}s for {READINGS} readings")
    assert max(timings) < 60


# ══════════════════════════════════════════════════════════════════════════
# T-46 · a refused row inside every batch, and the other 49 still commit
# ══════════════════════════════════════════════════════════════════════════
def test_a_failed_statement_inside_every_batch_costs_only_its_own_item_on_postgres(brazos, dana):
    with tenant_ctx(brazos):
        seed_reference()
        tech = technician(brazos)
        oid, rows = read_route(dana, brazos, tech, readings=READINGS)
        items = _poison(reading_items(oid, rows))
        answers = []
        for batch in batches(items):
            out = sync.sync_batch(as_field(tech), oid, {"items": batch})
            answers.append(out)
        stored = WorkSyncReceipt.objects.filter(work_order_id=oid).count()
        values = list(
            work_models.WorkOrderReading.objects.filter(work_order_id=oid, seq__gt=10_000)
            .order_by("seq").values_list("value", flat=True)
        )

    for out in answers:
        results = [i["result"] for i in out["items"]]
        # Item 25 goes BACK to the technician, not acknowledged and not stored
        # (PO 2026-10-21, *"back to the technician"*; until then it was stored
        # and flagged) — and items 1–24 AND 26–50 still commit around it.
        assert results[POISON_AT] == "refused", out["items"][POISON_AT]
        assert out["items"][POISON_AT]["ack"] is False
        assert results.count("accepted") == BATCH - 1, results
    assert stored == READINGS - READINGS // BATCH
    poisoned = {POISON_AT + k * BATCH for k in range(READINGS // BATCH)}
    assert all(values[n] is None for n in poisoned), "a refused value was written"
    assert all(values[n] is not None for n in range(READINGS) if n not in poisoned), "an item was lost"


# ══════════════════════════════════════════════════════════════════════════
# LAW 7 · the guard above goes RED without the savepoint
# ══════════════════════════════════════════════════════════════════════════
class _OnlyTheOuterAtomic:
    """`transaction` as `sync.py` sees it, with every NESTED `atomic()` made a
    no-op — the obvious `try/except: continue` the module docstring warns
    against, built without editing the file."""

    def __init__(self):
        self.depth = 0

    @contextlib.contextmanager
    def atomic(self, *args, **kwargs):
        if self.depth:
            yield
            return
        self.depth += 1
        try:
            with transaction.atomic(*args, **kwargs):
                yield
        finally:
            self.depth -= 1


def test_without_the_savepoint_a_refused_item_is_ACKNOWLEDGED_AND_DROPPED_on_postgres(
    brazos, dana, monkeypatch
):
    """⚠ **REWRITTEN 2026-10-21 — THE SAME SAVEPOINT, A DIFFERENT DAMAGE.**

    Until the PO's correction (*"back to the technician"*) a refused item was
    HELD: `_hold` wrote a SECOND receipt for the same key, and without the
    savepoint that insert collided with the first and poisoned the whole
    transaction — this case asserted the batch was LOST. A refusal now stores
    nothing, so there is no second insert, and the batch commits either way.
    **What the savepoint protects now is the KEY:** the receipt is written
    before the act, and only the savepoint takes it back down when the act
    fails. Without it the refused item's receipt SURVIVES the failed act, so
    the server answers the item *duplicate* and ACKNOWLEDGES it — the phone
    lets it go, nothing was applied, and the technician's reading is gone
    without a word to anyone. Measured 2026-10-21: that is exactly what this
    case sees. With the savepoint (the case below) the poisoned item is
    refused, not acknowledged, its key is not spent, and its fix posts."""
    with tenant_ctx(brazos):
        seed_reference()
        tech = technician(brazos)
        oid, rows = read_route(dana, brazos, tech, readings=BATCH)
        batch = _poison(reading_items(oid, rows))
        poisoned = batch[POISON_AT]
        monkeypatch.setattr(sync, "transaction", _OnlyTheOuterAtomic())
        out = sync.sync_batch(as_field(tech), oid, {"items": batch})
        monkeypatch.undo()
        spent = WorkSyncReceipt.objects.filter(work_order_id=oid, key=poisoned["key"]).exists()
        fixed = dict(poisoned, payload=dict(poisoned["payload"], value="10"))
        resent = sync.sync_batch(as_field(tech), oid, {"items": [fixed]})

    answer = out["items"][POISON_AT]
    # Acknowledged as though the server had it — the phone drops the item…
    assert answer["result"] == "duplicate" and answer.get("ack") is True, answer
    assert poisoned["key"] in out["acknowledged"]
    assert spent, "the failed item's receipt survives WITHOUT the savepoint"
    # …and the technician's fix is swallowed as a duplicate too.
    assert resent["items"][0]["result"] == "duplicate", resent["items"][0]


def test_with_the_savepoint_the_fixed_item_posts_on_postgres(brazos, dana):
    """The control for the case above, on the real code: the refused key is
    not spent, and the fixed item under the SAME key is accepted."""
    with tenant_ctx(brazos):
        seed_reference()
        tech = technician(brazos)
        oid, rows = read_route(dana, brazos, tech, readings=BATCH)
        batch = _poison(reading_items(oid, rows))
        poisoned = batch[POISON_AT]
        sync.sync_batch(as_field(tech), oid, {"items": batch})
        spent = WorkSyncReceipt.objects.filter(work_order_id=oid, key=poisoned["key"]).exists()
        fixed = dict(poisoned, payload=dict(poisoned["payload"], value="10"))
        resent = sync.sync_batch(as_field(tech), oid, {"items": [fixed]})

    assert not spent
    assert resent["items"][0]["result"] == "accepted", resent["items"][0]


# ══════════════════════════════════════════════════════════════════════════
# The batch across jobs on PostgreSQL — one job's poison costs no other job
# ══════════════════════════════════════════════════════════════════════════
def test_the_batch_across_jobs_commits_every_job_around_a_poisoned_item_on_postgres(brazos, dana):
    with tenant_ctx(brazos):
        seed_reference()
        tech = technician(brazos)
        jobs = [read_route(dana, brazos, tech, readings=25, address=f"{600 + n} Main St") for n in range(2)]
        items = []
        for i, (oid, rows) in enumerate(jobs):
            items.extend(reading_items(oid, rows, route=f"x{i}", with_order=True))
        items[3]["payload"] = dict(items[3]["payload"], value="1e20")
        out = sync.sync_across_jobs(as_field(tech), {"items": items})
        counts = [WorkSyncReceipt.objects.filter(work_order_id=oid).count() for oid, _ in jobs]

    # The poisoned item goes back to the technician (PO 2026-10-21) and stores
    # nothing; every other item of BOTH jobs commits around it.
    assert out["accepted"] == 49 and out["held_for_review"] == 0 and out["refused"] == 1, out["jobs"]
    assert counts == [24, 25]



# ══════════════════════════════════════════════════════════════════════════
# T-46 (proof lane) · a REFUSED item — the one that goes back to the
# technician — costs only itself, leaves no receipt, and the SAME KEY lands
# once the technician has fixed it. And without the savepoint it does not.
# ══════════════════════════════════════════════════════════════════════════
#
# Why this is not the poison case above: a refusal raises a BUSINESS error
# (`BIZ-LOCKED`, the safety lock — the one refusal a technician's genuine item
# can get today, `sync._FIXABLE_ON_THE_PHONE`), AFTER the item's receipt row
# was INSERTed inside its savepoint. What the savepoint does here is take the
# receipt back with the refusal. Without it the receipt SURVIVES the refusal,
# so when the technician fixes the item and the phone sends the same key again
# (FF-50 "Fix and send again" — PO 2026-10-21, refusals go back to the
# technician), the server answers *duplicate*, ACKED: the phone deletes the
# item and the tick is never applied. Silent loss.
#
# Written by the proof lane before the PO's correction landed; on merge the
# server answers `refused` for every item the technician must fix, and the test
# below holds that path.

def _locked_then_fixed(oid):
    from tests.test_us_wrk_044_046_sync import _rows

    rows = _rows(oid)
    assert len(rows["safety"]) >= 2, "the lock needs a safety row still unticked"
    locked = {
        "key": "ortiz-locked-task",
        "kind": "task_tick",
        "seq": 2,
        "captured_at": "2026-03-15T15:16:00Z",
        "payload": {"task_id": str(rows["tasks"][0].id)},
    }
    items = [
        {"key": "ortiz-safety-0", "kind": "safety_tick", "seq": 1, "captured_at": "2026-03-15T15:15:00Z",
         "payload": {"safety_id": str(rows["safety"][0].id)}},
        locked,
    ]
    for row in rows["safety"][1:]:
        n = len(items) + 1
        items.append({"key": f"ortiz-safety-{n}", "kind": "safety_tick", "seq": n,
                      "captured_at": "2026-03-15T15:17:00Z", "payload": {"safety_id": str(row.id)}})
    for row in rows["tasks"][1:]:
        n = len(items) + 1
        items.append({"key": f"ortiz-task-{n}", "kind": "task_tick", "seq": n,
                      "captured_at": "2026-03-15T15:30:00Z", "payload": {"task_id": str(row.id)}})
    return rows, locked, items


def test_a_refused_item_costs_only_itself_and_the_same_key_lands_when_fixed_on_postgres(brazos, dana):
    from tests.test_us_met_helpers import field_actor
    from tests.test_us_wrk_044_046_sync import _order_on_a_meter

    assert connection.vendor == "postgresql"
    with tenant_ctx(brazos):
        oid = _order_on_a_meter(dana, brazos)
        _rows, locked, items = _locked_then_fixed(oid)
        out = sync.sync_batch(field_actor(oid, dana), oid, {"items": items})
        results = [i["result"] for i in out["items"]]
        assert results[1] == "refused", out["items"][1]
        assert out["items"][1].get("ack") is not True and locked["key"] not in out["acknowledged"]
        assert results.count("accepted") == len(items) - 1, results
        # Everything after the refusal COMMITTED…
        stored = set(WorkSyncReceipt.objects.filter(work_order_id=oid).values_list("key", flat=True))
        assert stored == {i["key"] for i in items} - {locked["key"]}
        # …and the refused item left NO receipt: the savepoint took it back.
        assert not WorkSyncReceipt.objects.filter(work_order_id=oid, key=locked["key"]).exists()

        # The safety rows are ticked now (they came in the same batch); the
        # phone sends THE SAME KEY again.
        again = sync.sync_batch(field_actor(oid, dana), oid, {"items": [locked]})
        assert again["items"][0]["result"] == "accepted", again["items"][0]
        assert locked["key"] in again["acknowledged"]
        assert WorkSyncReceipt.objects.filter(work_order_id=oid, key=locked["key"]).count() == 1


# ⚠ ITS LAW-7 TWIN WAS REMOVED ON MERGE (2026-10-21): it stripped the savepoint
# and expected the refused item's RECEIPT to survive. Since the PO's correction
# (*"back to the technician"*) a refused item writes NOTHING before it is
# refused, so stripping the savepoint cannot make it keep a receipt — the test
# could no longer fail (law 7, "incapable of failing"). The savepoint's red
# proof for the refused path is
# `test_without_the_savepoint_a_refused_item_is_ACKNOWLEDGED_AND_DROPPED_on_postgres`
# above, written by the lane that made the change.
