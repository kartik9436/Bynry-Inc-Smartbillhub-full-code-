# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-019 (EP-TEN-03 — tenant sample data: seed it, TAG it, report
#           it, remove it)   Screens: S8 (Sample data panel) · S62
# Rules:    BR-TEN-057 (the tag is `is_sample boolean NOT NULL DEFAULT false`
#           on each sampled table, written ONLY by that module's own service
#           function on the sample path) · BR-TEN-061 (removal deletes on this
#           predicate and on nothing else) · BR-TEN-013 (tenancy may not add a
#           column to another module's table) · CLAUDE.md rule 1
# ───────────────────────────────────────────────────────
"""customers 0010 — BR-TEN-057's `is_sample` tag on `accounts` · `customers` · `customer_accounts` · `contacts` · `addresses` · `service_agreements`.

HUMAN-OWNED (migration ordering 🔒). HUMAN-REVIEW-PENDING — AI-authored
2026-08-16 under the PO ruling of 2026-08-09 ("AI will do it; we will review it
later as human"). Row in 12-governance/09-human-review-ledger.md.

WHY THIS COLUMN IS THE WHOLE BLOCKER DEF-153 NAMES
---------------------------------------------------
Until this migration, `apps/tenancy/seams.py` documented five sample-data
contracts that NOT ONE MODULE IMPLEMENTED, and the reason was not that a lane
forgot: BR-TEN-057 puts the tag on the OWNING row, tenancy may not add a column
to another module's table (B1 / BR-TEN-013), and no owning lane had added it.
So the Sample data panel on Settings loaded nothing and reported, honestly and
uselessly, that every seam was unwired — and a brand-new tenant was empty, with
zero accounts and zero bills, which is what the Product Owner saw in production.

A tag rather than a registry, for BR-TEN-057's own reason: a central
`sample_rows(table, pk)` index would make every sample insert a CROSS-MODULE
WRITE. A boolean on your own row is written only by your own service.

NOT NULL DEFAULT false — and Django gives only half of that. `BooleanField(
default=False)` applies its default in PYTHON; the database column is left with
no DEFAULT after the AddField completes, so an INSERT from a repair script or a
COPY would hit NOT NULL rather than getting `false`. The DEFAULT is therefore
set explicitly below on Postgres, where the product runs; sqlite is the
developer database and the Python-side default covers it. This is the same
correction `metering 0006` made for `custom_data DEFAULT '{}'`.

**Every existing row becomes `is_sample = false`, which is the correct answer:**
a tenant's own data was never sample data, and removal must never be able to
reach it. That is the one-way property worth stating — the tag can only ever be
turned ON by a seeder, and the seeder only ever creates NEW rows.
"""

from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL

#: BR-TEN-057's literal `DEFAULT false`, which Django's Python-side default
#: does not create. One line per table, the same boring pattern (LAW 0).
COLUMN_DEFAULT_SQL = """
ALTER TABLE accounts ALTER COLUMN is_sample SET DEFAULT false;
ALTER TABLE customers ALTER COLUMN is_sample SET DEFAULT false;
ALTER TABLE customer_accounts ALTER COLUMN is_sample SET DEFAULT false;
ALTER TABLE contacts ALTER COLUMN is_sample SET DEFAULT false;
ALTER TABLE addresses ALTER COLUMN is_sample SET DEFAULT false;
ALTER TABLE service_agreements ALTER COLUMN is_sample SET DEFAULT false;
"""



class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0009_br_pay_013_privilege_flag"),
    ]

    operations = [
        migrations.AddField(
            model_name="account",
            name="is_sample",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="address",
            name="is_sample",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="contact",
            name="is_sample",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="customer",
            name="is_sample",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="customeraccount",
            name="is_sample",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="serviceagreement",
            name="is_sample",
            field=models.BooleanField(default=False),
        ),
        PostgresOnlySQL(COLUMN_DEFAULT_SQL),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-TEN-019@c3b7d18 (EP-TEN-03 — the tag BR-TEN-057 names; DEF-153's structural blocker)
# generated: 2026-08-16 by story-coder (DEF-153 sample-data lane)
# checklist: A✔ B✔ C=deferred(schema only — the tests are on the seeders this column exists for, tests/test_us_ten_019_sample_records.py) D=deferred(no-API-half — a column has no endpoint) E=deferred(no-frontend-half — the S8 Sample data panel is the surface) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report — makemigrations --check clean · migrate from empty on live PostgreSQL 16
# exceptions: the column is added to EVERY table BR-TEN-061's removal order names for this module, not only the ones a first seeder happens to write, because a row without the tag can never be removed and BR-TEN-061 rolls the whole delete back on one FK violation
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
