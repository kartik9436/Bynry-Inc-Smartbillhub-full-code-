# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 · Phase 13 T-35 (freshness on the template step) and
#           T-34 (one row per money change pushed to a phone)
# Rules:    R17 (PO ruled: money older than 5 minutes is warned, never blocked;
#           proceeding on stale data is recorded as unverified) · R18 (derived:
#           freshness sits on the template step; no code knows what a
#           disconnect is) · R19 (PO ruled: the server pushes when money
#           changes) · R111 (a reconnect fee is its own question) · BR-WRK-008
#           (a job copies its template) · CLAUDE.md 🔒 migration ordering
# Tests:    06-backend/tests/test_cr187_money_freshness.py ·
#           tests/test_cr187_money_push.py · tests/test_cr187_money_pg.py
# ───────────────────────────────────────────────────────
"""work 0039 — a step can need fresh money; a job records proceeding on it.

* `wot_tasks.money_fresh_minutes INT NULL` (CHECK ≥ 1) and
  `wot_tasks.money_charge_code TEXT NULL` — the template step's declaration,
  beside `photo_required` and `is_mandatory` (R18). NULL = the step reads no
  money, which is every existing step, so nothing existing changes.
* the same two on `work_order_tasks`, COPIED at raise (`BR-WRK-008`), plus the
  record of the proceed — `money_as_at`, `money_proceeded_at`,
  `money_unverified` (NULL = never proceeded on a money check).
* `work_money_pushes` — one row per (tenant, account, payments' change stamp);
  RLS ENABLE + FORCE is `work/0040`.

No backfill: every job raised before today was raised from steps that declared
no money check, and NULL is that fact.

**Down:** drops the columns and the table. Every recorded proceed verdict is
lost with them, which is stated; the audit rows written at the time remain.

⚠ **ANOTHER LANE (S-SYNC) MAY ADD A `work` MIGRATION IN PARALLEL.** If both
land as `0039`, the coordinator renumbers this one and its dependant `0040`;
nothing in either depends on the other lane's columns.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is a CLAUDE.md 🔒
sensitive path. AI-authored 2026-10-21 under the PO ruling of 2026-08-09.
"""

import django.db.models.deletion
from django.db import migrations, models

import core.dbfields

_POSITIVE_OR_NULL = models.Q(
    ("money_fresh_minutes__isnull", True), ("money_fresh_minutes__gte", 1), _connector="OR"
)


class Migration(migrations.Migration):
    dependencies = [("work", "0038_cr168_technician_daily_job_limit")]

    operations = [
        migrations.AddField(
            model_name="workordertemplatetask",
            name="money_fresh_minutes",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="workordertemplatetask",
            name="money_charge_code",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="workordertemplatetask",
            constraint=models.CheckConstraint(
                condition=_POSITIVE_OR_NULL, name="ck_wot_tasks_money_fresh_positive"
            ),
        ),
        migrations.AddField(
            model_name="workordertask",
            name="money_fresh_minutes",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="workordertask",
            name="money_charge_code",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="workordertask",
            name="money_as_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="workordertask",
            name="money_proceeded_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="workordertask",
            name="money_unverified",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="workordertask",
            constraint=models.CheckConstraint(
                condition=_POSITIVE_OR_NULL, name="ck_work_order_tasks_money_fresh_positive"
            ),
        ),
        migrations.CreateModel(
            name="WorkMoneyPush",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=core.dbfields.uuid7,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("account_id", models.UUIDField()),
                ("change_at", models.DateTimeField()),
                ("orders", models.JSONField(default=list)),
                ("devices", models.IntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "work_money_pushes",
                "indexes": [
                    models.Index(
                        fields=["tenant", "-change_at"], name="ix_work_money_pushes_recent"
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("tenant", "account_id", "change_at"),
                        name="uq_work_money_pushes_change",
                    )
                ],
            },
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-014@3e02d12e (CR-187-BRC10 Phase 13 T-34/T-35 — the template's task steps; R17/R18/R19; sha1[:8] of Rules.txt R16–R19 + WorkToDo.txt T-33..T-35, the design canvas of 2026-10-21)
# generated: 2026-10-21 by the CR-187 Phase 13 lane S-MONEY
# checklist: A✔ B✔ C=deferred(n/a) D=deferred(n/a) E=deferred(n/a) F✔ G✔ H✔ [🔒 migration ordering → review-ledger row owed]
# gates: makemigrations --check · migrate up → down → up on PostgreSQL 16
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
