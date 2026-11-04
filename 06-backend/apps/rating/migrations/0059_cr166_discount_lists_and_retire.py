# ── Trace ──────────────────────────────────────────────
# Change:  CR-166-BRC10 round 2 task 3 — the discounts redesign's back end.
# Rules:   PO 2026-10-03 rulings (the three dropdowns; ruling 4, the dated
#          retire) · CLAUDE.md hard rule 1 (RLS FORCE on the new table,
#          rating/0061)
# Tests:   06-backend/tests/test_cr166_discounts_round2.py ·
#          06-backend/tests/test_cr166_discounts_round2_pg.py
# ───────────────────────────────────────────────────────
"""rating 0059 — the SCHEMA half: the three per-utility discount lists, who
qualifies as a code, and the dated retire.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING (migration ordering). Row in
`12-governance/09-human-review-ledger.md`, 2026-10-03, CR-166-BRC10 r2 t3.

Three migrations, one per transaction (the `rating/0056`–`0058` shape):
**0059** schema (this file) · **0060** data — seed the drawn values for every
utility, map today's free text onto them, and put every APPROVED-but-never-
activated version in force (ruling 1) · **0061** PostgreSQL only — RLS FORCE on
`discount_list_values` and the overlap lock widened to cover approved versions.

DOWN PATH: reversing drops `discount_list_values` (every value a utility added
or renamed is LOST — the codes stay on the discounts as plain text, so no
discount changes), `discount_versions.eligibility_code` (the label is still in
`eligibility_summary`) and `discounts.retire_on` (a retirement already written
onto the version windows STAYS: the windows are what price, and reversing a
schema cannot un-end a discount — reopen its window by hand if that is meant).
"""

import core.dbfields
import django.db.models.deletion
import django.db.models.functions.text
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rating", "0058_cr165_tax_chain_constraints_and_rls"),
        ("tenancy", "0058_storm_water_flat_size"),
    ]

    operations = [
        migrations.AddField(
            model_name="discount",
            name="retire_on",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="discountversion",
            name="eligibility_code",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="DiscountListValue",
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
                ("list_code", models.TextField()),
                ("code", models.TextField()),
                ("label", models.TextField()),
                ("checked_by", models.TextField(blank=True, null=True)),
                ("check_key", models.TextField(blank=True, null=True)),
                ("is_system", models.BooleanField(default=False)),
                ("active", models.BooleanField(default=True)),
                ("sort_order", models.IntegerField(default=100)),
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
                "db_table": "discount_list_values",
                "indexes": [
                    models.Index(
                        fields=["tenant", "list_code"], name="ix_discount_list_values_list"
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        models.F("tenant"),
                        models.F("list_code"),
                        django.db.models.functions.text.Lower("code"),
                        name="uq_discount_list_values_code_ci",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("list_code__in", ("program_owner", "exclusivity_group", "eligibility"))
                        ),
                        name="ck_discount_list_values_list",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("checked_by__isnull", True),
                            ("checked_by__in", ("system", "proof")),
                            _connector="OR",
                        ),
                        name="ck_discount_list_values_checked_by",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("check_key__isnull", True),
                            ("check_key__in", ("everyone", "autopay", "paperless", "government")),
                            _connector="OR",
                        ),
                        name="ck_discount_list_values_check_key",
                    ),
                ],
            },
        ),
    ]
