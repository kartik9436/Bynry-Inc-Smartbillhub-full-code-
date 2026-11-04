"""billing 0041 — `correction_case_items`, one row per correction (`CR-180-BRC10` B3).

HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering and an RLS policy are
CLAUDE.md 🔒 paths. AI-authored 2026-10-12 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*); row in
12-governance/09-human-review-ledger.md.

WHAT IT ADDS. The Fix a bill wizard's ONE "What was wrong" table (PO
2026-10-12, decision log *FIX A BILL REVAMP* items 7 and 10): a case carries N
correction rows, each naming the reason, the item, the value it should have
been and the bills it applies to. Written at Send with the case; execution
re-prices FROM them. See `correction_models.CorrectionCaseItem`.

THE POLICY IS THE SIGNED B2 §3 TEMPLATE, VERBATIM — the same shape as `0015`
for its three siblings, and none of its own. A correction row names a
customer's meter, plan and the value their bill should have carried; it is
not metadata. ENABLE + FORCE, `tenant_id = current_setting('app.tenant_id')`.

DOWN PATH. Reversible while the table is empty, which is every tenant on the
day it ships (CR-180 §Version and rollback: *"one forward migration, reversible
while empty"*). Dropping it after cases were sent loses which corrections
those cases were approved on; their pinned bills and figures are unaffected
(they live on `correction_case_bills`).

Postgres only for the policy: SQLite has no RLS, and the developer database is
SQLite, so the isolation half is proved on PostgreSQL (`--ds=config.settings.
pgtest`).
"""

import django.db.models.deletion
from django.db import migrations, models

import core.dbfields

POLICY_SQL = """
ALTER TABLE correction_case_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE correction_case_items FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS correction_case_items_tenant_isolation ON correction_case_items;
CREATE POLICY correction_case_items_tenant_isolation ON correction_case_items
  USING      (tenant_id = current_setting('app.tenant_id')::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);
"""

DROP_SQL = """
DROP POLICY IF EXISTS correction_case_items_tenant_isolation ON correction_case_items;
ALTER TABLE correction_case_items NO FORCE ROW LEVEL SECURITY;
ALTER TABLE correction_case_items DISABLE ROW LEVEL SECURITY;
"""


def apply_policy(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(POLICY_SQL)


def drop_policy(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(DROP_SQL)


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0040_def_2430_invoice_line_discount_code"),
        ("tenancy", "0008_rls_custom_field"),
    ]

    operations = [
        migrations.CreateModel(
            name="CorrectionCaseItem",
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
                ("position", models.IntegerField()),
                ("reason", models.TextField()),
                ("correction_class", models.TextField()),
                ("item", models.TextField(blank=True, null=True)),
                ("act", models.TextField(blank=True, null=True)),
                ("value", models.TextField(blank=True, null=True)),
                ("value2", models.TextField(blank=True, null=True)),
                ("bill_ids", models.JSONField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "case",
                    models.ForeignKey(
                        db_column="case_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="items",
                        to="billing.correctioncase",
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
                "db_table": "correction_case_items",
                "indexes": [
                    models.Index(fields=["tenant", "case"], name="ix_corr_items_case"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("tenant", "case", "position"),
                        name="uq_correction_case_item_position",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            correction_class__in=("restatement", "credit_only", "document")
                        ),
                        name="ck_correction_case_item_class",
                    ),
                ],
            },
        ),
        migrations.RunPython(apply_policy, drop_policy),
    ]
