# ── Trace ──────────────────────────────────────────────
# Journey:  J65 — the offline day, one sync (08-qa/01-e2e/journeys/
#           J65-offline-day-one-sync.md). THIS FILE IS ITS ACTIVATION.
# Story:    US-WRK-044 · US-WRK-045 · US-WRK-047 · US-WRK-048
# Rules:    BR-WRK-041 · BR-WRK-042 · BR-WRK-039 · BR-WRK-015 · BR-MET-110 ·
#           hard rule 1 · hard rule 3
# ───────────────────────────────────────────────────────
"""**`J65` ACTIVATED — the handoff contract, made executable.**

⚠ **WHY THIS IS A `.py` AND NOT THE `.spec.ts` THE PLAN NAMES.**
`10-execution-plan.md` line 282 says a demonstrating wave *"writes the
`.spec.ts` beside the other journey specs"*. **There are no other journey
specs.** No `.spec.ts` exists anywhere in this repository, `08-qa/01-e2e/`
holds journeys and expectations and no runner, and nothing in CI would execute
such a file. Writing one would have produced a check that cannot fail — the
exact shape hard-won law 7 spends four paragraphs on — and it would have been
the FOURTH wave to claim an activation that did not run (`E6`, `H3`, `I3`
each did; `J60`, `J62`, `J63`, `J66`, `J67` still carry their banners).
So the spec is written where the journey's subject actually lives: a journey
is a **cross-module handoff contract about what upstream leaves in the
database**, and that is a backend test. Recorded in the decision log so the
next lane does not read this as carelessness.

⚠ **WHAT AN ACTIVATION ASSERTS, AND WHAT IT DELIBERATELY DOES NOT.**
`J65` is a fourteen-step table; a test per drawn cell would be a second copy
of the journey free to disagree with the first. What downstream actually
depends on is the file's own **"This journey leaves (for downstream)"**
paragraph plus its **INVARIANCE** row, so that is what is asserted here, one
test per clause, each naming the clause it holds. `J61` picks these up.

⚠ **WHAT IS PROVED ELSEWHERE AND IS NOT RE-PROVED HERE** — stated rather than
quietly skipped:
  * **The SAVEPOINT (law 14)** — `tests/test_us_wrk_044_sync_pg.py`, on real
    PostgreSQL. SQLite has no aborted-transaction state, so a green here says
    nothing about it and this file must not pretend otherwise.
  * **The photograph resize and the 100 KB ceiling** —
    `tests/test_us_wrk_047_049_evidence.py` and `..._048_evidence_pg.py`.
  * **The screens** — `10-scripts/render-checks/cr070-l-the-offline-day-and-
    the-read.mjs`, which clicks them. No gate in this repo reads rendered
    output (law 6).
"""

from __future__ import annotations

import pytest

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.metering import models as metering_models
from apps.work import sync
from apps.work.sync_models import WorkSyncReceipt
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import field_actor  # CR-168 P1.34 — sync as the field
from tests.test_us_met_helpers import take_required_photos  # DEF-WRK-9625
from tests.test_us_met_helpers import make_asset, make_premises, tenant_ctx
from tests.test_us_wrk_032_copies import _published_template
from tests.test_us_wrk_044_046_sync import _batch, _rows

pytestmark = pytest.mark.django_db

#: The handset's own times. **Deliberately not today**: the whole of
#: `BR-WRK-003` is that a read lands on the day it was READ, and a fixture
#: whose completion is today can pass by the two dates coinciding.
CLOSED_AT = "2026-03-15T16:07:00+00:00"


def _a_days_work(actor, tenant, *, jobs=3, connection_id=None):
    """D. Ortiz's day: `jobs` orders on their own meters, each ready to close.

    Returns `(order_id, batch)` per job, so a caller can replay exactly what
    the phone sent — which is what the re-sync clause needs.

    ⚠ **ONE TEMPLATE FOR THE WHOLE DAY, AND THAT IS NOT AN OPTIMISATION.**
    `tests/test_us_wrk_044_046_sync._order_on_a_meter` publishes a fresh
    template per call, and `_published_template` creates the three parts by
    fixed part number — so a second call in the SAME test dies on
    `uq_parts_tenant_part_no_ci`, which reads like a broken fixture and is
    really the catalogue refusing a duplicate correctly. A technician's day is
    several jobs off ONE published template anyway, so this is also the shape
    `J65` describes.
    """
    tid = _published_template(actor, tenant)
    premises = make_premises(
        actor, address_line="221 Oak Ave", services_available=["electric"]
    )
    made = []
    for n in range(jobs):
        asset = make_asset(actor, asset_no=f"E1P-3310{n}")
        oid = w6.create_work_order(
            actor,
            None,
            {
                "premises_id": str(premises["id"]),
                "asset_id": str(asset["id"]),
                "type": "Meter exchange",
                "template_id": str(tid),
                # ⚠ OPTIONAL, AND `J61` NEEDS IT. A job with no build never
                # reaches the message queue, so the letter clause cannot be
                # proved on one (`DEF-WRK-3635`). `J65`'s own clauses do not
                # care, so the default stays as the journey draws it.
                **({"connection_id": str(connection_id)} if connection_id else {}),
            },
        )["id"]
        # `DEF-WRK-9625` — the photographs travel #77 BEFORE the batch, as on
        # the phone; a close is refused while a required one is missing.
        take_required_photos(field_actor(oid, actor), oid)
        batch = _batch(oid, _rows(oid), prefix=f"ortiz-01-2026-03-15-{n}")
        made.append((oid, batch))
    return made


# ══════════════════════════════════════════════════════════════════════════
# "This journey leaves" — clause 1: three COMPLETED orders, accepted by NOBODY
# ══════════════════════════════════════════════════════════════════════════
def test_j65_leaves_three_completed_orders_that_nobody_has_accepted(brazos, dana):
    """*Three completed orders on `Work-009`, `accepted_by` NULL.*

    This is the handoff itself: `J61` step 7 opens the approval queue and
    expects to FIND them, and `J61` step 10 expects the acceptance still to be
    available to make. An order that arrived already accepted would leave
    `J61` with nothing to do and `BR-MET-110` unproved.
    """
    with tenant_ctx(brazos):
        day = _a_days_work(dana, brazos)
        for oid, batch in day:
            sync.sync_batch(field_actor(oid, dana), oid, batch)

        rows = list(work_tables.WorkOrder.objects.filter(id__in=[oid for oid, _ in day]))

    assert len(rows) == 3
    assert {r.state for r in rows} == {"completed"}, [r.state for r in rows]
    assert {r.outcome for r in rows} == {"passed"}
    # ⚠ THE NULL **IS** THE REVIEW QUEUE (`BR-WRK-007`). It is asserted as a
    # set rather than per row so a single accepted order cannot hide.
    assert {r.accepted_by_id for r in rows} == {None}, "something accepted a job at CLOSE"


def test_j65_leaves_completed_at_at_the_HANDSETS_time_not_the_syncs(brazos, dana):
    """*`completed_at` at the phone's times.*

    `J61`'s whole exit test is that the read is dated to the COMPLETION, and
    `accept_field_result` takes that date from this column. If the close
    stamped the sync's clock instead, `J61` would post every read on the day
    the signal came back and every assertion downstream would still pass.
    """
    with tenant_ctx(brazos):
        day = _a_days_work(dana, brazos, jobs=1)
        oid, batch = day[0]
        sync.sync_batch(field_actor(oid, dana), oid, batch)
        order = work_tables.WorkOrder.objects.get(id=oid)

    assert order.completed_at is not None
    assert order.completed_at.isoformat() == CLOSED_AT, order.completed_at
    # Paired with the positive that makes it mean something: the sync ran
    # today, so the two are genuinely different days and this cannot pass by
    # the fixture and the clock agreeing.
    assert order.completed_at.date().isoformat() == "2026-03-15"


# ══════════════════════════════════════════════════════════════════════════
# INVARIANCE — "no close activated anything; zero meter_reads"
# ══════════════════════════════════════════════════════════════════════════
def test_j65_leaves_ZERO_meter_reads_because_a_close_activates_nothing(brazos, dana):
    """*Zero `meter_reads` rows* — `BR-MET-110`, the rule the journey is about.

    ⚠ **COUNTED ACROSS THE WHOLE TENANT, BEFORE AND AFTER, NOT ASSERTED AS AN
    ABSENCE.** `assert count == 0` passes just as happily on a tenant that
    never had a read and on a pipeline that silently wrote none — and it would
    also fail for an unrelated seeded read. The comparison is what carries the
    meaning: whatever was there before the day was worked is exactly what is
    there after it.
    """
    with tenant_ctx(brazos):
        before = metering_models.MeterRead.objects.count()
        day = _a_days_work(dana, brazos)
        for oid, batch in day:
            sync.sync_batch(field_actor(oid, dana), oid, batch)
        after = metering_models.MeterRead.objects.count()

    assert after == before, (
        f"a close wrote {after - before} meter read(s) — only Accept may (BR-MET-110)"
    )


# ══════════════════════════════════════════════════════════════════════════
# "43 receipts in work_sync_receipts" — the server's memory, and the re-sync
# ══════════════════════════════════════════════════════════════════════════
def test_j65_leaves_a_receipt_for_every_item_and_a_re_sync_adds_NOTHING(brazos, dana):
    """*A re-sync of the same three jobs adds nothing* — `WM-48`'s own figure.

    ⚠ **ASSERTED AS A COUNT COMPARISON, WHICH IS THE ENTIRE POINT.** A check
    that only said *the second sync did not throw* would pass over a server
    that cheerfully applied everything twice — the exact failure being ruled
    out. So the receipts, the orders and the reads are counted before and
    after, and every replayed item must answer *duplicate* rather than merely
    not be accepted.
    """
    with tenant_ctx(brazos):
        day = _a_days_work(dana, brazos)
        sent = []
        for oid, batch in day:
            sent.append((oid, batch, sync.sync_batch(field_actor(oid, dana), oid, batch)))

        receipts_before = WorkSyncReceipt.objects.count()
        completed_before = work_tables.WorkOrder.objects.filter(state="completed").count()
        reads_before = metering_models.MeterRead.objects.count()

        again = [(oid, sync.sync_batch(field_actor(oid, dana), oid, batch)) for oid, batch, _ in sent]

        receipts_after = WorkSyncReceipt.objects.count()
        completed_after = work_tables.WorkOrder.objects.filter(state="completed").count()
        reads_after = metering_models.MeterRead.objects.count()

    # The positive first — a receipt for every item the phone sent, or the
    # three zeros below would be a statement about an empty database.
    items_sent = sum(len(batch["items"]) for _, batch, _ in sent)
    assert items_sent > 0
    assert receipts_before == items_sent, f"{receipts_before} receipts for {items_sent} items"

    for oid, out in again:
        assert out["duplicate"] == len(out["items"]), (oid, out)
        assert out["accepted"] == 0, (oid, out)

    assert receipts_after == receipts_before, "a re-sync wrote a receipt"
    assert completed_after == completed_before, "a re-sync completed something twice"
    assert reads_after == reads_before, "a re-sync posted a read"


# ══════════════════════════════════════════════════════════════════════════
# The ONE refusal on a reading — hard rule 3
# ══════════════════════════════════════════════════════════════════════════
def test_j65_a_reading_with_no_unit_is_refused_and_the_rest_of_the_batch_survives(
    brazos, dana
):
    """*A value with no unit is refused (the one refusal)* — `J65` step 5.

    ⚠ **AND THE OTHER HALF IS WHAT MAKES IT A JOURNEY ASSERTION:** the refusal
    must not take the rest of the day's work with it. That is `BR-WRK-042`'s
    per-item promise and law 14's savepoint, and the ORDERING here is the
    journey's own — a refused item sits in the middle of a batch, not at
    its end.
    """
    with tenant_ctx(brazos):
        oid, batch = _a_days_work(dana, brazos, jobs=1)[0]
        # Strip the unit off the reading item, leaving everything else intact.
        for item in batch["items"]:
            if item["kind"] == "reading":
                item["payload"].pop("unit", None)
        out = sync.sync_batch(field_actor(oid, dana), oid, batch)

    reading_results = [r for r in out["items"] if r.get("kind") == "reading"]
    assert reading_results, out
    # ⚠ AMENDED 2026-10-21 (PO: *"back to the technician"* — BR-WRK-063
    # superseded for field items; 2026-10-04 to 2026-10-21 it was stored,
    # flagged and acknowledged): the reading with no unit is REFUSED with its
    # reason and NOT acknowledged, so the phone keeps it for the technician to
    # fix (hard rule 3). What this journey proves is unchanged: it is not
    # APPLIED, and the rest of the batch still lands.
    assert all(r["result"] == "refused" for r in reading_results), reading_results
    assert all(r["key"] not in out["acknowledged"] for r in reading_results)
    assert all(r["detail"]["reason"] for r in reading_results), reading_results
    # The positive: everything that was not the bad item still landed.
    assert out["accepted"] == len(out["items"]) - len(reading_results), out


# ══════════════════════════════════════════════════════════════════════════
# ISOLATION — hard rule 1
# ══════════════════════════════════════════════════════════════════════════
def test_j65_leaves_lone_star_ridge_unable_to_sync_or_see_any_of_it(
    brazos, lonestar, dana, erin
):
    """*Lone Star Ridge unable to fetch any of it* — `J65` step 13.

    A swapped phone: a queued item for another tenant's order answers **404**,
    byte-identical to an absent row, because existence must not leak.
    """
    with tenant_ctx(brazos):
        oid, batch = _a_days_work(dana, brazos, jobs=1)[0]
        sync.sync_batch(field_actor(oid, dana), oid, batch)

    with tenant_ctx(lonestar):
        with pytest.raises(Exception) as refused:
            sync.sync_batch(erin, oid, batch)

    assert "404" in str(refused.value) or "not found" in str(refused.value).lower(), refused.value

    # And the positive on the other side of the wall: Brazos Bend's own work is
    # still there. A test that only proved Lone Star saw nothing would pass on
    # a database where the sync had silently failed for everybody.
    with tenant_ctx(brazos):
        assert work_tables.WorkOrder.objects.filter(id=oid, state="completed").exists()


# ── Lifecycle ─────────────────────────────────────────────
# packet: J65 (08-qa/01-e2e/journeys/J65-offline-day-one-sync.md) · CR-070 wave L task L5
# generated: 2026-09-05 by the wave-L leftovers lane (L4 desktop + J61/J65 activation)
# checklist: A✔ B=n/a(no screen) C✔ D✔ E=n/a F✔ G✔ H=n/a
# gates: pytest 06-backend/tests/test_j65_offline_day_one_sync.py
# exceptions: the SAVEPOINT is NOT asserted here and cannot be — SQLite has no
#   aborted-transaction state; tests/test_us_wrk_044_sync_pg.py holds it on real
#   PostgreSQL, and this file's docstring says so rather than implying coverage
#   it does not have
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
