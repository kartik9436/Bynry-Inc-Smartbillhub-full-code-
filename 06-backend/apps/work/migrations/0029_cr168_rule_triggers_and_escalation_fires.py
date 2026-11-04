# ── Trace ──────────────────────────────────────────────
# Story:    CR-168-BRC10 round 2, lane SRV-1 — the schema for P3.65 (several
#           triggers on one rule) and P3.57 (an escalation fires once per job
#           per kind). The READERS are SRV-4's (round 5); round 2 lands the
#           tables so nothing is later built onto a schema that does not exist.
# Rules:    CR-168-BRC10 §7.3 (row work/0029) · the 26 Sep drawing ("several
#           triggers, any raises the job") · BR-WRK-033 (narrowed by ruling 34)
#           · CLAUDE.md hard rule 1 (RLS in work/0030)
# Tests:    06-backend/tests/test_cr168_srv1_migrations_pg.py
# ───────────────────────────────────────────────────────
"""work 0029 — a rule's triggers become rows; an escalation remembers firing.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-10-04 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.

  * **`work_order_rule_triggers`** — every existing rule's `trigger_kind` and
    `params` are COPIED IN as its row 1. ⚠ **The two columns on
    `work_order_rules` are KEPT** as lawful containers and the nightly sweep
    still reads them, so this migration changes no rule's behaviour and a
    rollback loses no rule (§8 *Rollback*).
  * **`work_order_rule_escalation_fires`** — UNIQUE `(tenant, work_order,
    kind)`: *once per job per kind*, the `work_order_rule_raises` shape.

RLS ENABLE + FORCE on both is `work/0030`. ⚠ `work_order_rules` already carries
FORCE (`work/0021`), and FORCE binds the migration role, so the copy visits each
tenant under its own `app.tenant_id` and restores the GUC to its arrival state —
`work/0027`'s shape, followed rather than re-derived.

THE REVERSE drops both tables. The copied rows were copies; the originals never
moved.
"""

import django.db.models.deletion
from django.db import migrations, models

import core.dbfields


def copy_triggers(apps_registry, schema_editor):
    Tenant = apps_registry.get_model("tenancy", "Tenant")
    Rule = apps_registry.get_model("work", "WorkOrderRule")
    Trigger = apps_registry.get_model("work", "WorkOrderRuleTrigger")
    connection = schema_editor.connection
    is_postgres = connection.vendor == "postgresql"

    arrival = None
    if is_postgres:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.tenant_id', true)")
            arrival = cursor.fetchone()[0]

    copied = rules = 0
    try:
        for tenant_id in Tenant.objects.values_list("id", flat=True):
            if is_postgres:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)]
                    )
            for rule in Rule.objects.filter(tenant_id=tenant_id):
                rules += 1
                if Trigger.objects.filter(rule_id=rule.id).exists():
                    continue
                Trigger.objects.create(
                    tenant_id=tenant_id,
                    rule_id=rule.id,
                    seq=1,
                    kind=rule.trigger_kind,
                    params=rule.params or {},
                )
                copied += 1
    finally:
        if is_postgres:
            with connection.cursor() as cursor:
                if arrival is None:
                    cursor.execute("RESET app.tenant_id")
                else:
                    cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [arrival])
    print(f"cr-168 rule triggers: {rules} rule(s) read — {copied} trigger row(s) copied")


class Migration(migrations.Migration):

    dependencies = [
        ("work", "0028_cr168_hold_reasons_and_columns"),
        ("metering", "0071_cr168_acceptance_and_hold_columns"),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkOrderRuleTrigger",
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
                ("seq", models.IntegerField(default=1)),
                ("kind", models.TextField()),
                ("params", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "rule",
                    models.ForeignKey(
                        db_column="rule_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="trigger_rows",
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
            ],
            options={"db_table": "work_order_rule_triggers"},
        ),
        migrations.AddConstraint(
            model_name="workorderruletrigger",
            constraint=models.UniqueConstraint(
                fields=("rule", "seq"), name="uq_work_order_rule_triggers_seq"
            ),
        ),
        migrations.CreateModel(
            name="WorkOrderRuleEscalationFire",
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
                ("kind", models.TextField()),
                ("fired_at", models.DateTimeField(auto_now_add=True)),
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
                        db_column="work_order_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="escalation_fires",
                        to="metering.workorder",
                    ),
                ),
            ],
            options={"db_table": "work_order_rule_escalation_fires"},
        ),
        migrations.AddConstraint(
            model_name="workorderruleescalationfire",
            constraint=models.UniqueConstraint(
                fields=("tenant", "work_order", "kind"),
                name="uq_work_order_rule_escalation_fires_once",
            ),
        ),
        migrations.RunPython(copy_triggers, migrations.RunPython.noop),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-168-BRC10 §7.3 (row work/0029)
# generated: 2026-10-04 by CR-168 round 2 lane SRV-1
# checklist: A✔ B✔ C=n/a D=n/a E=n/a F✔ G✔ H✔ (🔒 migration ordering → review-ledger row)
# gates: makemigrations --check · migrate up → down → up on PostgreSQL 16
# exceptions: none
# status: HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────
