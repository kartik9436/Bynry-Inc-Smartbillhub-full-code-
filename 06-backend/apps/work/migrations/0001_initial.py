"""work 0001 — the six tables the Work module owns, and RLS follows in 0002.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path; `human_owned.txt`
guards every numbered migration under `apps/*/migrations/0*.py`).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-04 under the PO ruling of
2026-08-09 (*"AI will do it; we will review it later as human"*). Its row is
in `12-governance/09-human-review-ledger.md`, shared with `0002_rls_force`
because a reviewer reading about the wall wants the tables in front of them;
neither file is RATIFIED without a recorded sign-off.

`CR-070` wave C task C1 · `US-WRK-007` · `US-WRK-008` · `US-WRK-009` ·
`US-WRK-010` · `US-WRK-012` · `03-field-map.md` §2.1.

SIX NEW TABLES, AND NOT ONE EXISTING ONE MOVED
----------------------------------------------
`work_order_types` · `work_priorities` · `work_skills` · `work_safety_kits` ·
`part_categories` · `parts`. Every one is new; every one is tenant-scoped; not
one is another module's.

**The six tables that already exist stay exactly where they are.** `connections`,
`connection_services`, `work_orders`, `work_order_templates`, `connection_todos`
and `service_characteristics` live in `apps/metering/connections.py` with two
migrations, an audit trail and a test suite behind them. `03-field-map.md` §4
lists three ways to honour the ruling that Work owns them and records the choice
as **PENDING the blueprint's §16** — a section this repo has never been able to
read. Wave C does not decide it and does not move them: nothing in this wave
needs the move, and a six-table migration-graph operation is not a thing to do
on the side of a Settings wave. The two columns wave C adds to
`work_order_templates` are therefore metering's own migration (`metering/0045`).

WHAT IS NOT IN `parts`, AND WHY THAT IS THE POINT
-------------------------------------------------
There is **no `on_hand`, no `reorder_at` and no `location` column**. The
wireframe draws all three; the commitment card that specifies the same screen
says *"No stock levels, no reorder points"*, and `CR-028` §11-D5 parked the
parts-stock table when Assets was ruled into scope. The contradiction is
`DEF-WRK-3550` and the question is `OQ-WRK-1490`, OPEN. Adding one of those
columns in a later migration would ANSWER that question by building it, which
is the one thing the prime directive forbids.

MONEY AND UNITS (CLAUDE.md hard rules 2 and 3)
----------------------------------------------
`parts.unit_cost` is `numeric(18,4)` — four decimals stored, two displayed:
`MTR-W58` is `92.4000` in the column and `$92.40` on the screen.
`parts.unit_of_measure` is NOT NULL because a quantity with no unit is exactly
what hard rule 3 forbids, and `work_priorities.sla_hours` carries its unit in
its own name for the same reason.

⚠ **RLS IS IN 0002, IN THIS SAME COMMIT AND THIS SAME WAVE.** `CR-070` §3 asks
for *"the RLS policy in the same migration"* as the table. It is in the same
COMMIT and the migration immediately after, split for one reason: the policy
SQL is a 🔒 sensitive path under CLAUDE.md and carries `HUMAN-REVIEW-PENDING`
with a row in `12-governance/09-human-review-ledger.md`, and a reviewer reading
one file should be reading the policy and nothing else. Neither can reach a
deployment without the other — they are one `migrate` and one commit — and
`test_us_wrk_rls_pg.py` proves `relrowsecurity` AND `relforcerowsecurity` on all
six tables on real PostgreSQL, because SQLite has no row-level security at all
and a green test there would prove nothing (hard-won law 14).
"""

import core.dbfields
import django.db.models.deletion
import django.db.models.functions.text
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("metering", "0044_cr070_a_work_order_anchors"),
        ("tenancy", "0036_def3422_drop_bell_events"),
    ]

    operations = [
        migrations.CreateModel(
            name="PartCategory",
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
                ("code", models.TextField()),
                ("name", models.TextField()),
                ("is_system", models.BooleanField(default=False)),
                ("active", models.BooleanField(default=True)),
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
                "db_table": "part_categories",
            },
        ),
        migrations.CreateModel(
            name="Part",
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
                ("part_no", models.TextField()),
                ("name", models.TextField()),
                ("unit_of_measure", models.TextField()),
                ("unit_cost", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("is_system", models.BooleanField(default=False)),
                ("active", models.BooleanField(default=True)),
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
                (
                    "category",
                    models.ForeignKey(
                        blank=True,
                        db_column="category_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="parts",
                        to="work.partcategory",
                    ),
                ),
            ],
            options={
                "db_table": "parts",
            },
        ),
        migrations.CreateModel(
            name="WorkPriority",
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
                ("code", models.TextField()),
                ("name", models.TextField()),
                ("rank", models.IntegerField()),
                ("sla_hours", models.IntegerField(default=0)),
                ("colour", models.TextField(default="neutral")),
                ("is_system", models.BooleanField(default=False)),
                ("active", models.BooleanField(default=True)),
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
                "db_table": "work_priorities",
            },
        ),
        migrations.CreateModel(
            name="WorkOrderType",
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
                ("code", models.TextField()),
                ("name", models.TextField()),
                ("est_duration", models.DurationField(blank=True, null=True)),
                ("customer_present", models.BooleanField(default=False)),
                ("is_system", models.BooleanField(default=False)),
                ("active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "default_template",
                    models.ForeignKey(
                        blank=True,
                        db_column="default_template_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="default_for_types",
                        to="metering.workordertemplate",
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
                    "default_priority",
                    models.ForeignKey(
                        blank=True,
                        db_column="default_priority_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="default_for_types",
                        to="work.workpriority",
                    ),
                ),
            ],
            options={
                "db_table": "work_order_types",
            },
        ),
        migrations.CreateModel(
            name="WorkSafetyKit",
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
                ("code", models.TextField()),
                ("name", models.TextField()),
                ("items", models.JSONField(blank=True, default=list)),
                ("is_system", models.BooleanField(default=False)),
                ("active", models.BooleanField(default=True)),
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
                "db_table": "work_safety_kits",
            },
        ),
        migrations.CreateModel(
            name="WorkSkill",
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
                ("code", models.TextField()),
                ("name", models.TextField()),
                ("is_system", models.BooleanField(default=False)),
                ("active", models.BooleanField(default=True)),
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
                "db_table": "work_skills",
            },
        ),
        migrations.AddConstraint(
            model_name="partcategory",
            constraint=models.UniqueConstraint(
                models.F("tenant"),
                django.db.models.functions.text.Lower("code"),
                name="uq_part_categories_tenant_code_ci",
            ),
        ),
        migrations.AddConstraint(
            model_name="part",
            constraint=models.UniqueConstraint(
                models.F("tenant"),
                django.db.models.functions.text.Lower("part_no"),
                name="uq_parts_tenant_part_no_ci",
            ),
        ),
        migrations.AddConstraint(
            model_name="workpriority",
            constraint=models.UniqueConstraint(
                models.F("tenant"),
                django.db.models.functions.text.Lower("code"),
                name="uq_work_priorities_tenant_code_ci",
            ),
        ),
        migrations.AddConstraint(
            model_name="workpriority",
            constraint=models.UniqueConstraint(
                fields=("tenant", "rank"), name="uq_work_priorities_tenant_rank"
            ),
        ),
        migrations.AddConstraint(
            model_name="workordertype",
            constraint=models.UniqueConstraint(
                models.F("tenant"),
                django.db.models.functions.text.Lower("code"),
                name="uq_work_order_types_tenant_code_ci",
            ),
        ),
        migrations.AddConstraint(
            model_name="worksafetykit",
            constraint=models.UniqueConstraint(
                models.F("tenant"),
                django.db.models.functions.text.Lower("code"),
                name="uq_work_safety_kits_tenant_code_ci",
            ),
        ),
        migrations.AddConstraint(
            model_name="workskill",
            constraint=models.UniqueConstraint(
                models.F("tenant"),
                django.db.models.functions.text.Lower("code"),
                name="uq_work_skills_tenant_code_ci",
            ),
        ),
    ]
