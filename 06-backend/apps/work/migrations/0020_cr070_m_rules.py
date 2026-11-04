# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-037 (EP-WRK-07) — the two tables behind the overnight sweep.
# Rules:    BR-WRK-033 · BR-WRK-024 · CLAUDE.md hard rule 1 (the RLS half is
#           `0019`, which is the 🔒 path and carries its own review-ledger row)
# Tests:    06-backend/tests/test_us_wrk_037_rules.py
# ───────────────────────────────────────────────────────
"""work 0020 — `work_order_rules` and `work_order_rule_raises`.

Two tables, and the second one is the idempotency: `uq_work_order_rule_raises_
subject` is what makes *"running the sweep twice raises nothing the second
time"* a database guarantee rather than a service-layer intention. See
`apps/work/rules_models.py` for why the memory of a raise cannot live on
`work_orders.rule_id`.

⚠ **`work_orders.rule_id` STAYS A PLAIN `uuid` AND NO FK IS ADDED HERE.** The
column's own comment in `apps/metering/connections.py` predicts that *"the FK is
added by the migration that creates the table it would point at"* — this file —
and that prediction is **not followed**, deliberately. B11 F-3, the convention
that comment itself cites, is *"deferred FK: a uuid column, NO cross-module
constraint"*, and the precedent it names three lines above (`gate_order_id`) is
still a plain uuid today. Adding the constraint would also mint a NEW
metering → work cross-module FK, which is B2 §2's reviewed interface set and not
a build lane's to add on its own. Filed as `DEF-WRK-4082` so the comment is
corrected rather than quietly diverged from.

⚠ **THIS CITED `DEF-WRK-4072` FIRST, THEN `DEF-WRK-4075`, AND BOTH WERE TAKEN
BY SIBLING LANES WITHIN THE HOUR.** Each number was computed correctly from the
register's maximum at the moment it was taken, and a sibling working in its own
worktree had rows in NONE of the places that listing can see until it pushed —
CLAUDE.md hard-won law 11's allocated-id collision, twice on one citation.
`10-scripts/allocate.py defect --verify` caught both at push time, which is the
only moment the answer can be final.

**THE THIRD ATTEMPT DOES WHAT THE FIRST TWO DID NOT: it writes the register row
in the SAME COMMIT as the citation.** `allocate.py` cannot reserve — nothing it
does touches the remote — so an id stays free until a row claiming it is pushed,
and a citation without its row is an invitation to the next lane's arithmetic.

HUMAN-OWNED — migration ordering is a CLAUDE.md 🔒 sensitive path (`DEF-GOV-8547`).
"""

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        # ⚠ **THIS FILE WAS `0018` UNTIL WAVE `L` LANDED `0018`/`0019` WHILE
        # THIS LANE WAS BUILDING.** Both lanes computed "the next free number"
        # correctly and got the same answer, which is hard-won law 11's
        # allocated-id collision with migration numbers rather than defect ids;
        # Django reported it as *"Conflicting migrations detected; multiple leaf
        # nodes"*, which names neither lane. Renumbered to `0020`/`0021` at push
        # time — the re-derivation this law asks for, applied to a number.
        #
        # Named explicitly rather than left at the autodetector's pick, which
        # was `metering/0052`: migration ORDERING is a CLAUDE.md 🔒 path, and
        # depending on the LATEST node of another app couples this file to
        # whichever lane pushed last (wave K's `0016` says the same in its own
        # words). `work_order_templates` is created by `metering/0026` and
        # `work_orders` is older still; `0050` is the node wave K settled on and
        # is reused so the two Work waves name one metering ancestor.
        ("metering", "0050_cr070_g_dispatch"),
        # `tenancy.Tenant` — every table here carries its FK. Its own creation
        # migration, not a recent one, for the same reason.
        ("tenancy", "0001_initial"),
        ("work", "0019_rls_force_sync"),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkOrderRule",
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
                ("source_module", models.TextField()),
                ("trigger_kind", models.TextField()),
                ("params", models.JSONField(blank=True, default=dict)),
                ("assignment", models.JSONField(blank=True, default=dict)),
                ("notifications", models.JSONField(blank=True, default=dict)),
                ("escalation", models.JSONField(blank=True, default=dict)),
                ("enabled", models.BooleanField(default=True)),
                ("is_sample", models.BooleanField(default=False)),
                ("created_by", models.UUIDField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "priority",
                    models.ForeignKey(
                        blank=True,
                        db_column="priority_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="raising_rules",
                        to="work.workpriority",
                    ),
                ),
                (
                    "template",
                    models.ForeignKey(
                        db_column="template_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="raising_rules",
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
            ],
            options={
                "db_table": "work_order_rules",
            },
        ),
        migrations.CreateModel(
            name="WorkOrderRuleRaise",
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
                ("subject_kind", models.TextField()),
                ("subject_key", models.TextField()),
                ("raised_at", models.DateTimeField(auto_now_add=True)),
                (
                    "rule",
                    models.ForeignKey(
                        db_column="rule_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="raises",
                        to="work.workorderrule",
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
                    "work_order",
                    models.ForeignKey(
                        blank=True,
                        db_column="work_order_id",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="rule_raises",
                        to="metering.workorder",
                    ),
                ),
            ],
            options={
                "db_table": "work_order_rule_raises",
            },
        ),
        migrations.AddIndex(
            model_name="workorderrule",
            index=models.Index(fields=["tenant", "enabled"], name="ix_work_order_rules_enabled"),
        ),
        migrations.AddConstraint(
            model_name="workorderrule",
            constraint=models.UniqueConstraint(
                fields=("tenant", "name"), name="uq_work_order_rules_tenant_name"
            ),
        ),
        migrations.AddIndex(
            model_name="workorderruleraise",
            index=models.Index(
                fields=["tenant", "rule", "raised_at"], name="ix_wo_rule_raises_month"
            ),
        ),
        migrations.AddConstraint(
            model_name="workorderruleraise",
            constraint=models.UniqueConstraint(
                fields=("tenant", "rule", "subject_kind", "subject_key"),
                name="uq_work_order_rule_raises_subject",
            ),
        ),
    ]
