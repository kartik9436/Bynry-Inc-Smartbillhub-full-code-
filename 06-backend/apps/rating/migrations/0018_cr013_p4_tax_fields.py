"""rating 0017 — CR-013 part 4's tax data model, in ONE pass.

HUMAN-OWNED (RLS policies + migration ordering are CLAUDE.md rule-1 🔒 paths).

HUMAN-REVIEW-PENDING — AI-authored 2026-08-21 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Row per file in
12-governance/09-human-review-ledger.md; not RATIFIED without a human sign-off.

FOUR DEFECTS, ONE SCHEMA PASS
-----------------------------
* **DEF-385** — the fields TAX-02 is specified to collect and had no column:
  `code`, `bill_label`, `tax_type`, `rounding_rule`, `due_date_rule`,
  `remit_method`, `remit_reference`, `collection_allowance_percent` + its own
  `collection_allowance_gl_account_id`, `interest_penalty_percent` +
  `interest_penalty_basis`, and `filing_reminder_recipient`.
* **DEF-382** — `discount_treatment`, which part 4 states is *"statutory"* and
  *"per tax"*, and which the product answered identically for every authority.
* **DEF-387** — `is_draft`, the ONE lifecycle fact that cannot be derived. The
  other three statuses come from dates already stored (`selectors.tax_status`).
* **DEF-383** — `tax_exemption_categories` + `tax_exemption_certificates`: an
  exemption is a category with a certificate and an expiry, which no array on
  `taxes` can carry.
* **DEF-384** — `corrects` / `superseded_by` / `correction_reason`, so a typo in
  an in-force rate can be fixed by *"a documented correction version"* instead
  of by an edit that rewrites rate history.

NOTHING HERE MOVES A FIGURE, AND THAT IS BY CONSTRUCTION
--------------------------------------------------------
Every added column is NULLABLE with no default except two, and both defaults are
today's behaviour exactly: `discount_treatment="before"` is the single rule the
engine has always applied (`$1.00` off a Bexar County bill leaves that line at
`$3.78`), and `is_draft=False` means every row that exists — and every row any
code path creates from here on — is IN FORCE, as it is today.

⚠ **`is_draft` IS A BOOLEAN DEFAULTING TO FALSE, AND THAT IS THE DESIGN.** The
first version of this migration added a nullable `activated_at` and BACKFILLED
it, with draft = NULL. It reads better and it is the same bug pointing at bills:
the fixture seeder, the sample-data seeder and every test create taxes with
`models.Tax.objects.create(...)`, so each would have minted a silent DRAFT that
never prices — **the ruled Texas rates would have stopped charging on the next
tenant provisioned**, with nothing red. Four tests caught it (`Tax Texas State`
billing `$0.00` instead of `$6.25`). A default of False needs no backfill, no
data write and no code path to remember: hard-won law 3, *the unsafe option must
be the one you type.* There is therefore NO `RunPython` in this migration.

⚠ THE RLS POLICIES ARE IN **THIS** MIGRATION, NOT THE NEXT ONE
---------------------------------------------------------------
`rating 0003_rls_w1_policies` exists only because an earlier lane documented
policies it never wrote, and nine tenant tables shipped with no isolation at
all. A tenant table is unprotected for exactly as long as its policy is a
separate piece of work, and `tax_exemption_certificates` names WHICH OF A
UTILITY'S CUSTOMERS DOES NOT PAY TAX — so the ENABLE + FORCE lands in the same
operation list that creates the tables. Policies live in the signed template
file `06-backend/db/rls_rating_cr013_p4.sql`; Postgres only, proved live by the
G5 isolation suite (NFR-10, zero tolerance, release blocker).
"""

import core.dbfields
import django.db.models.deletion
import django.db.models.functions.text
from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL, load_db_sql


class Migration(migrations.Migration):

    # ⚠ RENUMBERED 0017 -> 0018 ON MERGE (2026-08-21). Two lanes each took 0017
    # against their own copy of the tree — this one and
    # `0017_br_rat_103_charge_customer_classes` — leaving two leaf nodes and a
    # `makemigrations --merge` demand. The chain is made LINEAR rather than
    # merged: a merge node is a no-op that documents nothing, and both
    # migrations are purely additive so the order carries no meaning to
    # recover. This one now follows the other.
    dependencies = [
        ("rating", "0017_br_rat_103_charge_customer_classes"),
        ("tenancy", "0016_br_rat_081_service_metered"),
    ]

    operations = [
        migrations.CreateModel(
            name="TaxExemptionCategory",
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
                ("requires_certificate", models.BooleanField(default=True)),
                ("certificate_requirement", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "db_table": "tax_exemption_categories",
            },
        ),
        migrations.CreateModel(
            name="TaxExemptionCertificate",
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
                ("certificate_ref", models.TextField(blank=True, null=True)),
                ("issued_on", models.DateField(blank=True, null=True)),
                ("expires_on", models.DateField(blank=True, null=True)),
                ("verified_by_id", models.UUIDField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "db_table": "tax_exemption_certificates",
            },
        ),
        migrations.AddField(
            model_name="tax",
            name="bill_label",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tax",
            name="code",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tax",
            name="collection_allowance_gl_account_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tax",
            name="collection_allowance_percent",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True),
        ),
        migrations.AddField(
            model_name="tax",
            name="correction_reason",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tax",
            name="corrects",
            field=models.ForeignKey(
                blank=True,
                db_column="corrects_tax_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="corrections",
                to="rating.tax",
            ),
        ),
        migrations.AddField(
            model_name="tax",
            name="discount_treatment",
            field=models.TextField(default="before"),
        ),
        migrations.AddField(
            model_name="tax",
            name="due_date_rule",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tax",
            name="filing_reminder_recipient",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tax",
            name="interest_penalty_basis",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tax",
            name="interest_penalty_percent",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True),
        ),
        migrations.AddField(
            model_name="tax",
            name="is_draft",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="tax",
            name="remit_method",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tax",
            name="remit_reference",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tax",
            name="rounding_rule",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tax",
            name="superseded_by",
            field=models.ForeignKey(
                blank=True,
                db_column="superseded_by_tax_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="supersedes",
                to="rating.tax",
            ),
        ),
        migrations.AddField(
            model_name="tax",
            name="tax_type",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="tax",
            constraint=models.CheckConstraint(
                condition=models.Q(("discount_treatment__in", ("before", "after"))),
                name="ck_taxes_discount_treatment",
            ),
        ),
        migrations.AddConstraint(
            model_name="tax",
            constraint=models.UniqueConstraint(
                models.F("tenant"),
                django.db.models.functions.text.Lower("code"),
                condition=models.Q(("code__isnull", False)),
                name="uq_taxes_tenant_code_ci",
            ),
        ),
        migrations.AddConstraint(
            model_name="tax",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("corrects__isnull", True),
                    models.Q(("corrects", models.F("id")), _negated=True),
                    _connector="OR",
                ),
                name="ck_taxes_corrects_not_self",
            ),
        ),
        migrations.AddField(
            model_name="taxexemptioncategory",
            name="tax",
            field=models.ForeignKey(
                db_column="tax_id",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="exemption_categories",
                to="rating.tax",
            ),
        ),
        migrations.AddField(
            model_name="taxexemptioncategory",
            name="tenant",
            field=models.ForeignKey(
                db_column="tenant_id",
                on_delete=django.db.models.deletion.PROTECT,
                to="tenancy.tenant",
            ),
        ),
        migrations.AddField(
            model_name="taxexemptioncertificate",
            name="category",
            field=models.ForeignKey(
                db_column="category_id",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="certificates",
                to="rating.taxexemptioncategory",
            ),
        ),
        migrations.AddField(
            model_name="taxexemptioncertificate",
            name="tenant",
            field=models.ForeignKey(
                db_column="tenant_id",
                on_delete=django.db.models.deletion.PROTECT,
                to="tenancy.tenant",
            ),
        ),
        migrations.AddConstraint(
            model_name="taxexemptioncategory",
            constraint=models.UniqueConstraint(
                models.F("tax"),
                django.db.models.functions.text.Lower("code"),
                name="uq_tax_exemption_categories_tax_code_ci",
            ),
        ),
        migrations.AddConstraint(
            model_name="taxexemptioncertificate",
            constraint=models.UniqueConstraint(
                condition=models.Q(("revoked_at__isnull", True)),
                fields=("category", "account_id"),
                name="uq_tax_exemption_certificates_category_account_live",
            ),
        ),
        # Hard rule 1, in the SAME operation list as the CreateModel above.
        PostgresOnlySQL(
            sql=load_db_sql("rls_rating_cr013_p4.sql"),
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
