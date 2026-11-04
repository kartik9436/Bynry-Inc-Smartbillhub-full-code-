"""metering 0050 — the twelve dispatch columns: a promise, a place, an owner.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path; `human_owned.txt`
guards every numbered migration under `apps/*/migrations/0*.py`).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-05 under the PO ruling of
2026-08-09 (*"AI will do it; we will review it later as human"*). Its row is in
`12-governance/09-human-review-ledger.md` (task `G5`); not RATIFIED without a
recorded sign-off.

`CR-070` wave G task `G1` · `US-WRK-024` · `US-WRK-011` · `BR-WRK-018` ·
`BR-WRK-022` · `BR-WRK-023` · `03-field-map.md` §3 rows 6–15 · hard rule 1.

WHY A METERING MIGRATION IN A WORK WAVE
---------------------------------------
`work_orders` is METERING's table today. Work owns it by the ruling of
2026-09-03 and `03-field-map.md` §4 records HOW it moves as pending the
blueprint's §16. Django resolves a migration's `model_name` inside its own app,
so an `AddField` on `workorder` written into `apps/work/migrations` raises
before it can run. `G1` says `work/000N`; the plan is amended in the same commit
as this file, exactly as wave P amended `P1` for the same reason.

WHAT IT ADDS — TWELVE COLUMNS, TWO CHECKS, TWO INDEXES
------------------------------------------------------
  * `priority_id` → `work_priorities` · `due_at` · `window_start` /
    `window_end` — the PROMISE. `BR-WRK-018`: `due_at` defaults to the raise
    time plus the priority's SLA hours, STAMPED at the raise so that moving
    Urgent from 4 h to 2 h does not move a job already in the field.
  * `dispatch_state` — `BR-WRK-023`'s third axis, seven values, `ck_work_orders_
    dispatch_state`. The ONLY non-nullable one here: every order is somewhere on
    the run, and an order with no dispatch state is not a fact, it is a column
    nobody filled in.
  * `rule_id` — `BR-WRK-024`'s second half. A plain uuid, the B11 F-3 deferred-FK
    convention `gate_order_id` already uses, because `work_order_rules` is wave
    M's table.
  * `assignee_technician_id` / `assignee_crew_id` / `assigned_at` /
    `assigned_by` — a CACHE of the latest row in `work_order_assignments`, which
    is the record (`03-field-map.md` §3 row 12 says *"a cache"* in those words).
    `ck_work_orders_one_assignee`: a person or a crew, never both.
  * `est_duration` — copied from the job type at the raise. A `DurationField`,
    which is what `work_order_types.est_duration` already is: hard rule 3 is met
    by the TYPE rather than by a name suffix, because a `timedelta` cannot be
    read in the wrong unit.
  * `area_id` → `tenancy.areas`. `BR-WRK-022`, verbatim: *"Areas are
    `tenancy.Area` … it never duplicates it."*

⚠ **`source` AND `source_ref` ARE NOT HERE.** `G1` lists `source` among its own
columns; `metering/0049` (wave P) already built it and closed its vocabulary at
fourteen with `ck_work_orders_source`. `DEF-WRK-3726` is that collision, ruled
before it happened: this wave READS the column and draws it as RAISED BY, adds
nothing and narrows nothing.

RLS IS UNTOUCHED, AND WHY THAT IS SAFE
--------------------------------------
`work_orders` has had `ENABLE` + `FORCE` row-level security since
`metering/0027`. A policy is on the TABLE, not on its columns, so twelve new
columns are covered by the existing policy on the day they exist — the same
statement `metering/0049` made about its two. `tests/test_us_wrk_rls_pg.py`
reads `relrowsecurity` and `relforcerowsecurity` out of `pg_class` rather than
trusting any file's claim about it.

THE ONE BACKFILL, AND WHY IT IS RAW SQL IN A `NO FORCE` WINDOW
--------------------------------------------------------------
`ADD COLUMN … DEFAULT 'queued'` is DDL and lands on every existing row. But an
order that is already `completed` or `cancelled` would then read *Queued* on the
dispatch axis — a false statement about a real job, which is the exact cost
`metering/0049` refused to pay when it left `source` NULL rather than guessing.

⚠ **AND A `RunPython` BACKFILL WOULD HAVE UPDATED NOTHING, SILENTLY.** `FORCE`
row-level security applies to the table's OWNER, which is the role migrations
run as, and `app.tenant_id` is unset during a migration — so the policy's
`USING (tenant_id = NULL)` matches zero rows and the UPDATE reports success
having touched none of them. That is a whole class of migration bug this repo
has not written down before, and it is why the correction is bracketed by
`NO FORCE` / `FORCE` (the shape `billing/0002` and `audit/0006` already use) and
why the statement's row count is what the PostgreSQL test asserts.

Skipped on SQLite (`PostgresOnlySQL`), which has no row-level security and
whose test database is built fresh from the models on every run anyway.
"""

from django.db import migrations, models

from apps.metering.connections import DISPATCH_STATES
from core.migrationtools import PostgresOnlySQL

#: Correct the two dispatch states a finished order should already be in. Every
#: other existing row keeps the DDL default `queued`, which is true of it: it is
#: an open job nobody has dispatched, because until this migration there was no
#: dispatcher to do it.
BACKFILL = """
ALTER TABLE work_orders NO FORCE ROW LEVEL SECURITY;
UPDATE work_orders SET dispatch_state = 'complete'  WHERE state = 'completed';
UPDATE work_orders SET dispatch_state = 'cancelled' WHERE state = 'cancelled';
ALTER TABLE work_orders FORCE ROW LEVEL SECURITY;
"""

#: Reversing puts every row back on the DDL default the dropped column had.
#: Stated rather than left as `RunSQL.noop`, because a reverse that silently
#: does nothing is the same lie in the other direction.
BACKFILL_REVERSE = """
ALTER TABLE work_orders NO FORCE ROW LEVEL SECURITY;
UPDATE work_orders SET dispatch_state = 'queued';
ALTER TABLE work_orders FORCE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("metering", "0049_cr070_p_work_order_source"),
        ("tenancy", "0001_initial"),
        ("identity", "0001_initial"),
        # `work/0006` created `technicians` and `crews`; `work/0001` created
        # `work_priorities`. Named so the FKs below cannot be applied against a
        # database that has not built them yet.
        ("work", "0006_cr070_f_workforce"),
    ]

    operations = [
        migrations.AddField(
            model_name="workorder",
            name="priority",
            field=models.ForeignKey(
                blank=True,
                db_column="priority_id",
                null=True,
                on_delete=models.PROTECT,
                related_name="work_orders",
                to="work.workpriority",
            ),
        ),
        migrations.AddField(
            model_name="workorder",
            name="due_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="workorder",
            name="window_start",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="workorder",
            name="window_end",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="workorder",
            name="dispatch_state",
            field=models.TextField(default="queued"),
        ),
        migrations.AddField(
            model_name="workorder",
            name="rule_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="workorder",
            name="assignee_technician",
            field=models.ForeignKey(
                blank=True,
                db_column="assignee_technician_id",
                null=True,
                on_delete=models.PROTECT,
                related_name="work_orders",
                to="work.technician",
            ),
        ),
        migrations.AddField(
            model_name="workorder",
            name="assignee_crew",
            field=models.ForeignKey(
                blank=True,
                db_column="assignee_crew_id",
                null=True,
                on_delete=models.PROTECT,
                related_name="work_orders",
                to="work.crew",
            ),
        ),
        migrations.AddField(
            model_name="workorder",
            name="assigned_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="workorder",
            name="assigned_by",
            field=models.ForeignKey(
                blank=True,
                db_column="assigned_by",
                null=True,
                on_delete=models.PROTECT,
                related_name="+",
                to="identity.user",
            ),
        ),
        migrations.AddField(
            model_name="workorder",
            name="est_duration",
            field=models.DurationField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="workorder",
            name="area",
            field=models.ForeignKey(
                blank=True,
                db_column="area_id",
                null=True,
                on_delete=models.PROTECT,
                related_name="+",
                to="tenancy.area",
            ),
        ),
        migrations.AddConstraint(
            model_name="workorder",
            constraint=models.CheckConstraint(
                condition=models.Q(dispatch_state__in=DISPATCH_STATES),
                name="ck_work_orders_dispatch_state",
            ),
        ),
        migrations.AddConstraint(
            model_name="workorder",
            constraint=models.CheckConstraint(
                condition=models.Q(assignee_technician__isnull=True)
                | models.Q(assignee_crew__isnull=True),
                name="ck_work_orders_one_assignee",
            ),
        ),
        migrations.AddIndex(
            model_name="workorder",
            index=models.Index(
                fields=["tenant", "dispatch_state"], name="ix_work_orders_dispatch"
            ),
        ),
        migrations.AddIndex(
            model_name="workorder",
            index=models.Index(fields=["tenant", "due_at"], name="ix_work_orders_due"),
        ),
        PostgresOnlySQL(BACKFILL, reverse_sql=BACKFILL_REVERSE),
    ]
