# ── Trace ──────────────────────────────────────────────
# Task:     Finance blueprint `P0.1` (2026-09-24) — *"A line posted today names
#           the customer who held the account then, and a later transfer does
#           not change it"*.
# Story:    `US-LED-002` TC-4 (a historical line keeps its stamped dimensions
#           for ever) · `BR-LED-001` (the dimension set lives on the LINE)
# Rules:    CLAUDE.md hard rule 4 (no UPDATE on an issued journal line — so
#           there is NO BACKFILL) · hard rule 1 (the RLS policy on
#           `journal_lines` is untouched) · `BR-CUS-1030` (a sale reassigns an
#           account, which is the mutation this column exists to survive)
# Tests:    06-backend/tests/test_p0_1_customer_on_the_journal_line.py
# ───────────────────────────────────────────────────────
"""ledger 0017 — **a journal line names the customer who held the account.**

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering and the shape of the
books are on CLAUDE.md's sensitive-paths list. Ledger row:
`12-governance/09-human-review-ledger.md`, *"A journal line names the customer
who held the account when it was posted"*.

WHAT WAS WRONG, IN ONE SENTENCE
-------------------------------
`journal_lines` carried an `account_id` and no customer, so *"what did this
person owe us in August?"* was answered by walking to the account and reading
**who holds it now**. `BR-CUS-1030` lets an account change hands — a property
sale, a move-in — and on the day it does, every historical line re-attributes
itself to the new holder. **Nothing goes red. The figures still foot. They are
simply about the wrong person.**

WHAT THIS ADDS
--------------
One nullable `customer_id` on `journal_lines`, `ON DELETE` handled by Django's
`PROTECT`, plus `ix_journal_lines_customer` on `(tenant_id, customer_id)` — the
same shape as the six dimension indexes already on the table.

**PARTITION-AWARE, AND THAT IS MEASURED RATHER THAN ASSUMED.** `journal_lines`
is a PARTITIONED parent (`ledger/0005`, RANGE on `created_at`, yearly) with
`journal_lines_2026` and `journal_lines_2027` beneath it today and more minted
by the create-ahead job. On PostgreSQL 12+ both `ADD COLUMN` and `ADD
CONSTRAINT … FOREIGN KEY` on a partitioned parent propagate to every existing
partition and are inherited by every future one, and `CREATE INDEX` on the
parent creates a partitioned index with one child per partition. The test
asserts the column, the foreign key and the index on **the parent and on both
partitions by name** — seven catalog reads, not one — because a migration that
reached only the parent would leave the guarantee off the table the rows are
actually in.

⚠ **THERE IS NO BACKFILL, AND THE ABSENCE IS THE DESIGN.** Hard rule 4 forbids
an UPDATE on an issued journal line, and the only source for a historical value
would be TODAY's `customer_accounts` link — the exact reading this column exists
to stop trusting. Writing it would therefore be both unlawful and wrong. So
**every row that existed before this migration reads NULL, for ever**: measured
on the seeded database (PostgreSQL 16.13, tenant `brazosbend`, 2026-09-24),
**661 of 661 live journal lines**. NULL means *"posted before the stamp
existed"* and every reader has to handle it.

REVERSIBLE, AND THE REVERSE INVENTS NOTHING
-------------------------------------------
`AddField` reverses to `DROP COLUMN` and `AddIndex` to `DROP INDEX`, both
propagating down the partition tree the same way. The reverse writes no row and
deletes no row: it drops a column that, at the moment this ships, is NULL on
every row in the table. Proved forward → back → forward against real
PostgreSQL, with the column, the FK and the index observed present → absent →
present on the parent AND on both partitions.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0069_def_cus_6431_resale"),
        ("ledger", "0016_cr136_cash_over_short_designation"),
        ("metering", "0061_cr131_premises_membership"),
        ("rating", "0043_cr130_percent_basis"),
        ("tenancy", "0048_p0_13_je_series_format"),
    ]

    operations = [
        migrations.AddField(
            model_name="journalline",
            name="customer",
            field=models.ForeignKey(
                blank=True,
                db_column="customer_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="customers.customer",
            ),
        ),
        migrations.AddIndex(
            model_name="journalline",
            index=models.Index(fields=["tenant", "customer"], name="ix_journal_lines_customer"),
        ),
    ]
