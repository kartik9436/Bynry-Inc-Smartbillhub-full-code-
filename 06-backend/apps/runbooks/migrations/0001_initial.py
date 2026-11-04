# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-041 (EP-RBS-01) — CR-075 wave A task A3: the seven tables.
# Rules:    CLAUDE.md 🔒 migration ordering · hard rule 1 (RLS FORCE arrives in
#           0002, its own migration) · hard rule 2 (money NUMERIC(18,4) with a
#           CHAR(3) partner) · hard rule 6 (idempotency by a UNIQUE index) ·
#           B2 §2 `### Module: runbooks` + Addendum r24 (anchored FIRST, in the
#           commit before this one — CR-075 wave A task A1)
# Tests:    06-backend/tests/test_us_rbs_041_module.py (the shapes) ·
#           06-backend/tests/test_us_rbs_041_pg.py (TC-RBS-7 isolation, and the
#           idempotency index, on PostgreSQL only)
# Impacts:  every read and write in apps/runbooks
# ───────────────────────────────────────────────────────
"""runbooks 0001 — the seven tables, and nothing else.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-06 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*); row in
12-governance/09-human-review-ledger.md. It reaches lifecycle RATIFIED only on a
recorded human sign-off.

ORDERING, WHICH IS THE 🔒 PART
------------------------------
Two dependencies and no more: `tenancy` (every table carries `tenant_id`) and
`identity` (the five reviewed `users(id)` pointers — B2 Addendum r24). It
depends on NO other module, which is the schema half of `BR-RBS-039`: this
module reads eleven others and is coupled to two.

**The schema brief was written first, on purpose.** `CR-069`'s `C34` set the
rule — *"the re-cut register begins at the migration"* — and `CR-075`'s
execution plan repeats it for this module: a table that is not in B2 when its
migration is written is a table nobody reviewed. `git log` shows A1's commit
before this one.

WHAT IS DELIBERATELY NOT HERE
-----------------------------
* **No RLS.** ENABLE + FORCE for all seven is `0002_rls_force`, its own
  migration, because a policy is a statement about WHO may see a row and is
  separate from WHAT the row is — a reviewer of the sensitive path then reads
  one short file with seven identical blocks instead of hunting `ALTER TABLE`s
  through six hundred lines of column definitions. Every RLS migration in this
  repository records the same reason.
* **No partitioning.** `runbook_runs` takes one row per RUN, not per attempt —
  about 7,000 a year for a tenant at the top of the ICP running nineteen
  scheduled runbooks daily. `integration_run` is partitioned because it takes
  one row per ATTEMPT; the shapes differ and so does the answer (B2 r24).
* **No foreign key on `runbook_run_records.subject_id`.** Which table it points
  at is decided by `subject_type` on the same row; twelve nullable FK columns
  would give this module a hard link into tables it is forbidden to write.
* **No trigger.** Nothing in these seven is financially immutable under hard
  rule 4: a run record is this module's own audit of its own work, and the
  append-only guarantee it needs is `UNIQUE (tenant_id, idempotency_key)`,
  which is already here.
"""

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("identity", "0005_cr070_f_field_technician"),
        ("tenancy", "0040_cr070_k_attachment_source"),
    ]

    operations = [
        migrations.CreateModel(
            name="CutoverPlan",
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
                ("name", models.TextField()),
                ("go_live_on", models.DateField(blank=True, null=True)),
                ("status", models.TextField(default="open")),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
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
                "db_table": "cutover_plans",
            },
        ),
        migrations.CreateModel(
            name="Runbook",
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
                ("key", models.TextField()),
                ("name", models.TextField()),
                ("kind", models.TextField(choices=[("check", "check"), ("action", "action")])),
                (
                    "category",
                    models.TextField(
                        choices=[
                            ("platform", "platform"),
                            ("onboarding_cutover", "onboarding_cutover"),
                            ("data_hygiene", "data_hygiene"),
                            ("premises", "premises"),
                            ("plans_rates", "plans_rates"),
                            ("assets", "assets"),
                            ("accounts", "accounts"),
                            ("reads", "reads"),
                            ("billing", "billing"),
                            ("collections", "collections"),
                            ("payments", "payments"),
                            ("finance", "finance"),
                            ("work", "work"),
                            ("customer_portal", "customer_portal"),
                            ("business", "business"),
                            ("data_sync", "data_sync"),
                        ]
                    ),
                ),
                ("tags", models.JSONField(blank=True, default=list)),
                (
                    "origin",
                    models.TextField(
                        choices=[
                            ("shipped", "shipped"),
                            ("cloned", "cloned"),
                            ("composed", "composed"),
                        ],
                        default="shipped",
                    ),
                ),
                ("template_key", models.TextField(blank=True, null=True)),
                (
                    "subject_type",
                    models.TextField(
                        choices=[
                            ("tenant", "tenant"),
                            ("account", "account"),
                            ("premise", "premise"),
                            ("meter", "meter"),
                            ("meter_day", "meter_day"),
                            ("bill", "bill"),
                            ("payment", "payment"),
                            ("bank_line", "bank_line"),
                            ("deposit", "deposit"),
                            ("parcel", "parcel"),
                            ("contact_feedback", "contact_feedback"),
                            ("period", "period"),
                        ]
                    ),
                ),
                ("unit_of_work", models.TextField()),
                ("enabled", models.BooleanField(default=True)),
                (
                    "trigger_kind",
                    models.TextField(
                        choices=[
                            ("manual", "manual"),
                            ("schedule", "schedule"),
                            ("event", "event"),
                        ],
                        default="manual",
                    ),
                ),
                ("cron", models.TextField(blank=True, null=True)),
                (
                    "event_kind",
                    models.TextField(
                        blank=True,
                        choices=[
                            ("batch.landed", "batch.landed"),
                            ("feedback.landed", "feedback.landed"),
                            ("bill_run.completed", "bill_run.completed"),
                        ],
                        null=True,
                    ),
                ),
                ("timezone", models.TextField(default="UTC")),
                ("cap", models.IntegerField(blank=True, null=True)),
                ("gate_mode", models.TextField(default="approve_each_run")),
                ("current_version", models.IntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "cloned_from",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="runbooks.runbook",
                    ),
                ),
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
                "db_table": "runbooks",
            },
        ),
        migrations.CreateModel(
            name="RunbookRun",
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
                ("version", models.IntegerField()),
                (
                    "mode",
                    models.TextField(choices=[("dry", "dry"), ("live", "live")], default="dry"),
                ),
                (
                    "trigger",
                    models.TextField(
                        choices=[
                            ("manual", "manual"),
                            ("schedule", "schedule"),
                            ("event", "event"),
                        ],
                        default="manual",
                    ),
                ),
                ("event_ref", models.TextField(blank=True, null=True)),
                (
                    "status",
                    models.TextField(
                        choices=[
                            ("queued", "queued"),
                            ("running", "running"),
                            ("awaiting_approval", "awaiting_approval"),
                            ("approved", "approved"),
                            ("acting", "acting"),
                            ("done", "done"),
                            ("failed", "failed"),
                            ("stopped", "stopped"),
                        ],
                        default="queued",
                    ),
                ),
                ("scope_fingerprint", models.TextField(blank=True, null=True)),
                ("counts", models.JSONField(blank=True, default=dict)),
                ("report", models.JSONField(blank=True, default=list)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("approved_count", models.IntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "approved_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="approved_by",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="identity.user",
                    ),
                ),
                (
                    "parent_run",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="children",
                        to="runbooks.runbookrun",
                    ),
                ),
                (
                    "runbook",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="runs",
                        to="runbooks.runbook",
                    ),
                ),
                (
                    "stopped_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="stopped_by",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="identity.user",
                    ),
                ),
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
                "db_table": "runbook_runs",
            },
        ),
        migrations.CreateModel(
            name="CutoverPlanItem",
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
                ("seq", models.IntegerField()),
                ("title", models.TextField()),
                ("owner", models.TextField(blank=True, null=True)),
                ("due_on", models.DateField(blank=True, null=True)),
                ("runbook_key", models.TextField(blank=True, null=True)),
                ("evidence_ref", models.TextField(blank=True, null=True)),
                ("status", models.TextField(default="open")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "plan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="runbooks.cutoverplan",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
                (
                    "last_run",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="runbooks.runbookrun",
                    ),
                ),
            ],
            options={
                "db_table": "cutover_plan_items",
            },
        ),
        migrations.CreateModel(
            name="RunbookRunRecord",
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
                (
                    "subject_type",
                    models.TextField(
                        choices=[
                            ("tenant", "tenant"),
                            ("account", "account"),
                            ("premise", "premise"),
                            ("meter", "meter"),
                            ("meter_day", "meter_day"),
                            ("bill", "bill"),
                            ("payment", "payment"),
                            ("bank_line", "bank_line"),
                            ("deposit", "deposit"),
                            ("parcel", "parcel"),
                            ("contact_feedback", "contact_feedback"),
                            ("period", "period"),
                        ]
                    ),
                ),
                ("subject_id", models.UUIDField(blank=True, null=True)),
                ("planned_action", models.TextField()),
                ("decided_by_rule", models.TextField(blank=True, null=True)),
                ("outcome", models.TextField(blank=True, null=True)),
                ("reason", models.TextField(blank=True, null=True)),
                ("fix_route", models.TextField(blank=True, null=True)),
                ("decision", models.TextField(blank=True, null=True)),
                ("decided_at", models.DateTimeField(blank=True, null=True)),
                (
                    "amount",
                    models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True),
                ),
                ("currency", models.CharField(blank=True, max_length=3, null=True)),
                ("data", models.JSONField(blank=True, default=dict)),
                ("idempotency_key", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "decided_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="decided_by",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="identity.user",
                    ),
                ),
                (
                    "run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="records",
                        to="runbooks.runbookrun",
                    ),
                ),
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
                "db_table": "runbook_run_records",
            },
        ),
        migrations.CreateModel(
            name="RunbookVersion",
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
                ("version", models.IntegerField()),
                ("definition", models.JSONField(default=dict)),
                ("changed_at", models.DateTimeField(auto_now_add=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "changed_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="changed_by",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="identity.user",
                    ),
                ),
                (
                    "runbook",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="versions",
                        to="runbooks.runbook",
                    ),
                ),
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
                "db_table": "runbook_versions",
            },
        ),
        migrations.CreateModel(
            name="WorkItem",
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
                (
                    "source_kind",
                    models.TextField(
                        choices=[
                            ("finding", "finding"),
                            ("exception", "exception"),
                            ("human_task", "human_task"),
                        ]
                    ),
                ),
                ("fingerprint", models.TextField()),
                ("title", models.TextField()),
                ("weight", models.IntegerField(default=0)),
                ("subject_ref", models.TextField(blank=True, null=True)),
                ("fix_route", models.TextField(blank=True, null=True)),
                ("due_on", models.DateField(blank=True, null=True)),
                ("status", models.TextField(default="open")),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "owner_user",
                    models.ForeignKey(
                        blank=True,
                        db_column="owner_user_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="identity.user",
                    ),
                ),
                (
                    "source_run",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="work_items",
                        to="runbooks.runbookrun",
                    ),
                ),
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
                "db_table": "work_items",
            },
        ),
        migrations.AddIndex(
            model_name="cutoverplan",
            index=models.Index(fields=["tenant", "status"], name="ix_cutover_plans_status"),
        ),
        migrations.AddIndex(
            model_name="runbook",
            index=models.Index(fields=["tenant", "category"], name="ix_runbooks_category"),
        ),
        migrations.AddConstraint(
            model_name="runbook",
            constraint=models.UniqueConstraint(
                fields=("tenant", "key"), name="uq_runbooks_tenant_key"
            ),
        ),
        migrations.AddIndex(
            model_name="runbookrun",
            index=models.Index(
                fields=["tenant", "runbook", "-started_at"], name="ix_runbook_runs_recent"
            ),
        ),
        migrations.AddIndex(
            model_name="runbookrun",
            index=models.Index(fields=["tenant", "status"], name="ix_runbook_runs_status"),
        ),
        migrations.AddConstraint(
            model_name="cutoverplanitem",
            constraint=models.UniqueConstraint(
                fields=("tenant", "plan", "seq"), name="uq_cutover_plan_items_seq"
            ),
        ),
        migrations.AddIndex(
            model_name="runbookrunrecord",
            index=models.Index(fields=["tenant", "run"], name="ix_runbook_records_run"),
        ),
        migrations.AddIndex(
            model_name="runbookrunrecord",
            index=models.Index(
                fields=["tenant", "subject_type", "subject_id"], name="ix_runbook_records_subject"
            ),
        ),
        migrations.AddConstraint(
            model_name="runbookrunrecord",
            constraint=models.UniqueConstraint(
                fields=("tenant", "idempotency_key"), name="uq_runbook_run_records_idem"
            ),
        ),
        migrations.AddConstraint(
            model_name="runbookversion",
            constraint=models.UniqueConstraint(
                fields=("tenant", "runbook", "version"), name="uq_runbook_versions_number"
            ),
        ),
        migrations.AddIndex(
            model_name="workitem",
            index=models.Index(fields=["tenant", "status", "-weight"], name="ix_work_items_list"),
        ),
        migrations.AddConstraint(
            model_name="workitem",
            constraint=models.UniqueConstraint(
                fields=("tenant", "fingerprint"), name="uq_work_items_fingerprint"
            ),
        ),
    ]
