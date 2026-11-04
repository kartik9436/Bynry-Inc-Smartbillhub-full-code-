# ── Trace ──────────────────────────────────────────────
# Change:   CR-030 W3 task 3.8 (the ACC-01 Usage tab)   Screens: S21 (Usage)
# Rules:    BR-MET-106 (a month's usage per account per service is computed
#           from meter reads, STORED, and displayed — PO 2026-08-24) ·
#           BR-MET-028 (estimates carry consumption, no current_value) ·
#           CLAUDE.md hard rule 3 (an explicit unit, always) · hard rule 4
#           (corrections are new rows) · hard rule 1 (RLS lands in 0025)
# Tests:    06-backend/tests/test_br_met_106_monthly_usage.py
# Impacts:  apps/metering/monthly_usage_service.py (the sole writer) ·
#           apps/metering/monthly_usage_reads.py (the Usage tab's read model)
# ───────────────────────────────────────────────────────
"""metering 0024 — `meter_read_monthly_usage`, BR-MET-106's stored month.
HUMAN-OWNED (migration ordering is a 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-08-24 under the PO ruling of 2026-08-09
("AI will do it; we will review it later as human"). Row in
12-governance/09-human-review-ledger.md; not RATIFIED without human sign-off.

ADDITIVE ONLY: one new table, no existing table altered, nothing backfilled and
no row anywhere changing meaning on this commit. The table is EMPTY after this
migration and stays empty until `monthly_usage_service.recompute_account` is
called — an unread month is ABSENT (BR-MET-106), and so is an uncomputed one.

⚠ **RLS LANDS IN 0025, IMMEDIATELY AFTER.** A tenant table with no policy is a
CLAUDE.md rule-1 violation between the two migrations and the pair must be
applied together — the same pairing metering 0014/0015 documents.

⚠ **NOT PARTITIONED, DELIBERATELY.** `meter_reads` is partitioned monthly on
`read_at` (DB-7/NFR-24, BR-MET-055) because it grows with every register on
every read day. This table grows with accounts × services × months and is three
orders of magnitude smaller for the <3,000-connection utility this product is
for. Stated here because the next lane adding a metering table will read 0003
and 0004 first, and inheriting the partition machinery would buy nothing.
"""

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0018_rls_cr031_service_requests"),
        ("metering", "0023_cr029_drop_cycle_bill_date"),
        ("tenancy", "0017_br_ast_048_mapping_templates"),
    ]

    operations = [
        migrations.CreateModel(
            name="MonthlyUsage",
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
                ("period_month", models.DateField()),
                ("quantity", models.DecimalField(decimal_places=6, max_digits=18)),
                ("unit", models.TextField()),
                ("read_count", models.IntegerField()),
                ("estimated_read_count", models.IntegerField(default=0)),
                ("source_read_ids", models.JSONField(default=list)),
                ("source_fingerprint", models.TextField()),
                ("computed_at", models.DateTimeField()),
                ("superseded_by_id", models.UUIDField(blank=True, null=True)),
                ("superseded_at", models.DateTimeField(blank=True, null=True)),
                ("supersede_reason", models.TextField(blank=True, null=True)),
                ("is_sample", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "account",
                    models.ForeignKey(
                        db_column="account_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="customers.account",
                    ),
                ),
                (
                    "service",
                    models.ForeignKey(
                        db_column="service_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.service",
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
                "db_table": "meter_read_monthly_usage",
                "indexes": [
                    models.Index(
                        fields=["tenant", "account", "period_month"],
                        name="ix_monthly_usage_acct_month",
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("superseded_by_id__isnull", True)),
                        fields=("tenant", "account", "service", "period_month"),
                        name="uq_monthly_usage_head",
                    )
                ],
            },
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CUS-011@a1fbf3f (the S21 operational tabs — Usage is the first of
#         the five; BR-MET-106 snapshot 2026-08-24)
# generated: 2026-08-24 by the CR-030 W3 task 3.8 lane (schema half)
# checklist: A✔ B=deferred(table-half only — the behaviour TCs land with monthly_usage_service.py in this same lane) C✔ D=deferred(no-API-half — a CreateModel) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09 — migrations 🔒 HUMAN-REVIEW-PENDING; the ledger row is written to this lane's scratchpad because 12-governance/09-human-review-ledger.md is another lane's file today, and is REPORTED for the orchestrator to land)
# gates: makemigrations --check clean · ruff✔ black✔ · sqlite migrate applied
# exceptions: NOT partitioned although it lives beside the partitioned meter_reads — see the docstring; NFR-24's mandatory list does not name it and G16 agrees · `quantity` is NUMERIC(18,6) rather than CLAUDE.md rule 2's 4 dp because it is a CONSUMPTION, not money: rule 3 governs it, and 18,6 is the precision meter_reads.consumption already carries so the sum is exact
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
