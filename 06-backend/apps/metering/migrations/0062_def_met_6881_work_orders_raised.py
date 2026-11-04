"""metering 0062 — the raise date gets an index (`DEF-MET-6881`, 2026-09-27).

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-27 under the PO ruling of
2026-08-09; row in `12-governance/09-human-review-ledger.md`.

ONE `AddIndex`, AND THE WHOLE ARGUMENT IS WHICH THREE COLUMNS AND IN WHICH ORDER.

──────────────────────────────────────────────────────────────────────────────
WHAT WAS MEASURED, AND ON WHAT
──────────────────────────────────────────────────────────────────────────────
Real PostgreSQL 16.13, one tenant holding **40,025 work orders** — the top of
T5, which is the whole ICP — seeded by `10-scripts/ds_small_datasets_cost.py`
and read through `apps/work/work_orders_dataset.py` at its own default sort
(`raised_on` → `("created_at", "id")`, direction `desc`). Median of 7 after a
discarded warm-up, `per=50`, index dropped and re-created in one process so the
two halves differ in one variable:

    the PAGE QUERY alone        page 1    0.0655s → 0.0034s   19.3x
                                page 801  0.0953s → 0.0259s    3.7x

    the whole dataset call      page 1    0.156s  → 0.131s     1.19x
    (page + the tile aggregates) page 801 0.876s  → 0.694s     1.26x

⚠ **THE TWO ROWS ARE BOTH TRUE AND THE SECOND ONE IS THE HONEST HEADLINE.**
This index fixes the PAGE, and the page is not the whole cost of the call. The
tiles (`raised`, `completed`, `open`, duration, average-days-to-close, on-time)
are SQL aggregates over the WHOLE filtered set by design — that is what makes
them foot to the report whatever page is cut — and an aggregate over 40,025 rows
reads 40,025 rows whether this index exists or not. What is left after this
migration is that aggregate, and no index removes it. A later lane measuring the
dataset call and finding ~0.13s should not conclude the index is absent.

The statement count is **2 before and 2 after**, which is exactly why no
existing check could see this: an N+1 shows in a statement count and a missing
index does not.

──────────────────────────────────────────────────────────────────────────────
THE PLAN, WHICH IS THE ACTUAL EVIDENCE
──────────────────────────────────────────────────────────────────────────────
`EXPLAIN (ANALYZE, BUFFERS)`, page 801 (`LIMIT 50 OFFSET 40000`), BEFORE:

    Gather Merge  (actual time=46.705..72.711 rows=40025 loops=1)
      ->  Sort  (actual time=43.655..48.950 rows=20012 loops=2)
            Sort Key: created_at DESC, id DESC
            Sort Method: external merge  Disk: 4288kB
            Worker 0:  Sort Method: external merge  Disk: 2736kB
            ->  Parallel Seq Scan on work_orders (rows=20012 loops=2)
    Execution Time: 74.646 ms

AFTER:

    Limit  (actual time=29.707..29.733 rows=25 loops=1)
      ->  Index Scan Backward using ix_work_orders_raised on work_orders
            Index Cond: (tenant_id = (NULLIF(current_setting('app.tenant_id'...
    Execution Time: 29.809 ms

**The `Sort` node and its `external merge  Disk: 4288kB` are gone** — there is
no sort at all, in either plan, because the index already holds the order. Page
1 fell the same way: `Seq Scan` + `Sort (top-N heapsort)` at 63.089 ms became
`Index Scan Backward` at 0.082 ms.

⚠ **THE DEEP PAGE READS MORE BUFFERS AFTER, NOT FEWER** — `shared hit=1654`
became `shared hit=17676` — and it is still three times faster. An `OFFSET
40000` walk touches every heap tuple it skips, so the index trades buffer hits
for a sort it no longer has to do and a spill it no longer has to write. A
reader checking BUFFERS alone would read this as a regression; the figure that
moved is `temp read=878 written=880` → **none at all**.

⚠ **ONE CLAIM IN `DEF-MET-6881`'s OWN ROW DID NOT REPRODUCE, AND IT IS SAID
HERE RATHER THAN QUIETLY DROPPED.** The row states the disk spill happens *"on
EVERY page including page 1"*. On this server page 1 sorted **in memory** —
`Sort Method: top-N heapsort  Memory: 38kB` — because a `LIMIT 50` top-N fits
in `work_mem` and only the deep OFFSET pages, which must order the whole set,
spill. Page 1 was still a full `Seq Scan` of all 40,025 rows and still 63 ms of
server time, so the defect is real and the fix is the same one; the spill is a
deep-page symptom rather than a first-page one, and a later lane reading *"every
page"* against a first-page plan would conclude the defect was gone.

──────────────────────────────────────────────────────────────────────────────
WHY ASCENDING, WITH NO `DESC` ON EITHER COLUMN
──────────────────────────────────────────────────────────────────────────────
The probe index quoted in the defect row was `(tenant_id, created_at DESC,
id DESC)`. This one is plain ascending, and it is not a weaker version of that:
PostgreSQL serves `ORDER BY created_at DESC, id DESC` from it by scanning
**backward**, and serves the ascending sort — which the same screen offers, as
a direction toggle — by scanning it forward. Both were measured here and neither
plan carries a `Sort` node. A `DESC` index would serve the default and leave the
other toggle on a Seq Scan. It also matches this table's four existing indexes,
none of which declares a direction.

──────────────────────────────────────────────────────────────────────────────
WHAT IT COSTS, AT THE TOP OF THE ICP
──────────────────────────────────────────────────────────────────────────────
At 40,025 orders in one tenant the index measured **2,320 kB** against a
**13 MB** table — 17.4% — and it is the fifth index on a table that already
carries four. It is paid for on every INSERT and on any UPDATE touching
`created_at`, which is `auto_now_add` and therefore never updated after the
raise. A work order is raised a few hundred times a day at a 40,000-account
utility and read on every dispatcher's screen and every R33 run, so the trade is
one-sided.

⚠ **`NFR-5`: THIS ADDS NO CAP OF ANY KIND.** It is an index; it constrains
nothing and makes no row unreachable, and the T4/T3 flexibility clause is
untouched — the same index serves 160,000 orders, more usefully, not less.

──────────────────────────────────────────────────────────────────────────────
REVERSIBLE, AND PROVED SO
──────────────────────────────────────────────────────────────────────────────
`AddIndex`'s own reverse is `RemoveIndex`; `migrate metering 0061` and back to
`0062` were both run against this database and both applied cleanly.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("metering", "0061_cr131_premises_membership"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="workorder",
            index=models.Index(
                fields=["tenant", "created_at", "id"], name="ix_work_orders_raised"
            ),
        ),
    ]
