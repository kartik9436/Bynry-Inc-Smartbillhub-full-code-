# ── Trace ──────────────────────────────────────────────
# Change:  CR-165-BRC10 round 2 task 3 — the taxes & fees redesign's back end.
# Defects: DEF-RAT-9280 (two taxes of one authority refuse the bill) ·
#          DEF-RAT-9283 (no new-rate-from-a-date path) · DEF-RAT-9276 (a
#          correction of a coded tax is refused as a duplicate code)
# Rules:   BR-RAT-037 (a rate change is a new row) · BR-RAT-104 (corrections) ·
#          CLAUDE.md hard rule 1 (RLS FORCE on the new table, rating/0058)
# Tests:   06-backend/tests/test_cr165_tax_versions.py ·
#          06-backend/tests/test_cr165_tax_versions_pg.py
# ───────────────────────────────────────────────────────
"""rating 0056 — the SCHEMA half: a tax CHAIN, its version number, the
new-rate link, and the utility's accounts with its tax authorities.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING (migration ordering). Row in
`12-governance/09-human-review-ledger.md`, 2026-10-03, CR-165-BRC10 r2 t3.

Three migrations, one per transaction, because PostgreSQL refuses an ALTER on a
table with pending trigger events in the same transaction as the rows it
changed: **0056** schema (this file) · **0057** backfill of `chain_id` and
`version_no` along the existing correction links · **0058** PostgreSQL-only
SQL — the insert trigger, the two exclusion constraints and RLS on
`tax_authority_accounts`.

⚠ **`uq_taxes_tenant_code_ci` IS DROPPED HERE** — every version of a tax now
shares its code (CR-165 §7 item 6, closes `DEF-RAT-9276`); `rating/0058`'s
`ex_taxes_code_one_chain` replaces it on PostgreSQL ("one code names one
chain"), and `_validate_tax` refuses the same thing at the field on every
database.

DOWN PATH: reversing this migration drops `chain_id`, `version_no`,
`follows_tax_id`, `authority_account_id` and the `tax_authority_accounts`
table (every authority account a utility typed is LOST), and RE-CREATES
`uq_taxes_tenant_code_ci` — which FAILS if any chain holds two coded versions.
Clear `code` on every superseded or ended version first
(`UPDATE taxes SET code = NULL WHERE chain_id <> id`), then reverse.
"""

import core.dbfields
import django.db.models.deletion
import django.db.models.functions.text
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rating", "0055_def_2340_seeded_codes_per_case"),
        ("tenancy", "0058_storm_water_flat_size"),
    ]

    operations = [
        migrations.CreateModel(
            name="TaxAuthorityAccount",
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
                ("authority_name", models.TextField()),
                ("account_number", models.TextField()),
                ("active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "tax_authority_accounts",
            },
        ),
        migrations.RemoveConstraint(
            model_name="tax",
            name="uq_taxes_tenant_code_ci",
        ),
        migrations.AddField(
            model_name="tax",
            name="chain_id",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="tax",
            name="follows",
            field=models.ForeignKey(
                blank=True,
                db_column="follows_tax_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="followed_by",
                to="rating.tax",
            ),
        ),
        migrations.AddField(
            model_name="tax",
            name="version_no",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="taxauthorityaccount",
            name="jurisdiction",
            field=models.ForeignKey(
                blank=True,
                db_column="jurisdiction_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="rating.taxjurisdiction",
            ),
        ),
        migrations.AddField(
            model_name="taxauthorityaccount",
            name="tenant",
            field=models.ForeignKey(
                db_column="tenant_id",
                on_delete=django.db.models.deletion.PROTECT,
                to="tenancy.tenant",
            ),
        ),
        migrations.AddField(
            model_name="tax",
            name="authority_account",
            field=models.ForeignKey(
                blank=True,
                db_column="authority_account_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="taxes",
                to="rating.taxauthorityaccount",
            ),
        ),
        migrations.AddConstraint(
            model_name="taxauthorityaccount",
            constraint=models.UniqueConstraint(
                models.F("tenant"),
                django.db.models.functions.text.Lower("authority_name"),
                django.db.models.functions.text.Lower("account_number"),
                name="uq_tax_authority_accounts_tenant_name_number_ci",
            ),
        ),
    ]
