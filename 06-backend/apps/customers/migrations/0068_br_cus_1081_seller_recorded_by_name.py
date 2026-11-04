# ── Trace ──────────────────────────────────────────────
# Change:   `BR-CUS-1081` T1, decided 2026-09-23 — a sale of an account with no
#           customer linked goes AHEAD and the seller is recorded by the name on
#           the account (`DEF-CUS-6387`).
# Rules:    `BR-CUS-1030` (a sale reassigns one account) · `BR-CUS-1023` (no
#           customer number without an identifier — which is why no seller
#           customer is minted here) · CLAUDE.md hard rule 1 (the RLS policy
#           on `transfers` is untouched)
# Decision: 12-governance/02-decision-log.md, 2026-09-23 — *"CORRECTED BY THE
#           PO: T1's SEARCH IS FOR THE BUYER, ON STEP 2 — AND WHAT THAT LEAVES
#           FOR THE SELLER"*
# ───────────────────────────────────────────────────────
"""customers 0068 — **`transfers.customer_id` may be NULL; `transfers.seller_name`.**

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is on CLAUDE.md's
sensitive-paths list, so the marker is here because the PATH is the category.
Ledger row: `12-governance/09-human-review-ledger.md`.

WHAT WAS WRONG
--------------
`transfers.customer_id` was `NOT NULL` (0021), and `transfers._seller_of`
therefore REFUSED an account with nobody linked — *"A-11512 is not linked to a
customer. Link it to one first."* — at step 5 of 5, on the PO's own sample
account. The PO moved the customer search to the BUYER (step 2), so nothing in
the wizard could fix an unlinked seller any more, and the sale could not be
completed at all.

WHAT THIS DOES — TWO COLUMN CHANGES ON THE UNMANAGED `transfers` TABLE
-----------------------------------------------------------------------
1. **`customer_id` DROP NOT NULL.** NULL means *nobody was on file for the
   account being sold*. No seller customer is minted in its place: a customer
   number needs an identifier (`BR-CUS-1023`) and the seller gave none.
2. **`seller_name text NULL`** — the name on the account on the day it was
   sold, written by `start_transfer` on EVERY sale, so a record names the
   seller whether or not a customer row existed, and a later rename of that
   customer cannot rewrite who sold the house.

Frozen DDL text for both vendors, never derived from the live model (0021's
reasoning). **SQLite cannot `DROP NOT NULL`**, so on SQLite — the test database
only — the table is rebuilt from its own stored `CREATE TABLE` text with that
one clause changed, rows copied, and its indexes recreated from their own
stored SQL. PostgreSQL gets the two `ALTER TABLE`s.

REVERSIBLE, WITH ONE CONDITION STATED: the reverse re-imposes `NOT NULL`, which
fails loudly if any sale of an unlinked account has been committed meanwhile —
the right answer, because dropping such a row would lose a real sale.
"""

import re

from django.db import migrations, models

PG_FORWARD = (
    "ALTER TABLE transfers ALTER COLUMN customer_id DROP NOT NULL;",
    "ALTER TABLE transfers ADD COLUMN seller_name text NULL;",
)
PG_REVERSE = (
    "ALTER TABLE transfers DROP COLUMN seller_name;",
    "ALTER TABLE transfers ALTER COLUMN customer_id SET NOT NULL;",
)

#: The clause 0021 wrote for SQLite, and the one it becomes.
_SQLITE_NOT_NULL = re.compile(r"(customer_id\s+char\(32\)\s+)NOT NULL(\s+REFERENCES customers\(id\))")


def _sqlite_rebuild(schema_editor, *, nullable: bool) -> None:  # type: ignore[no-untyped-def]
    cursor = schema_editor.connection.cursor()
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='transfers'")
    table_sql = cursor.fetchone()[0]
    cursor.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='transfers' AND sql IS NOT NULL"
    )
    index_sql = [row[0] for row in cursor.fetchall()]
    if nullable:
        rebuilt, n = _SQLITE_NOT_NULL.subn(r"\1NULL    \2", table_sql)
    else:
        rebuilt, n = re.subn(
            r"(customer_id\s+char\(32\)\s+)NULL(\s+REFERENCES customers\(id\))",
            r"\1NOT NULL\2",
            table_sql,
        )
    if n != 1:
        raise RuntimeError(f"customers 0068: expected one customer_id clause, found {n}")
    rebuilt = re.sub(r"CREATE TABLE\s+\"?transfers\"?", "CREATE TABLE transfers__0068", rebuilt, count=1)
    schema_editor.execute(rebuilt)
    schema_editor.execute("INSERT INTO transfers__0068 SELECT * FROM transfers")
    schema_editor.execute("DROP TABLE transfers")
    schema_editor.execute("ALTER TABLE transfers__0068 RENAME TO transfers")
    for statement in index_sql:
        schema_editor.execute(statement)


def forward(apps, schema_editor):  # type: ignore[no-untyped-def]
    if schema_editor.connection.vendor == "sqlite":
        _sqlite_rebuild(schema_editor, nullable=True)
        schema_editor.execute("ALTER TABLE transfers ADD COLUMN seller_name text NULL;")
        return
    for statement in PG_FORWARD:
        schema_editor.execute(statement)


def reverse(apps, schema_editor):  # type: ignore[no-untyped-def]
    if schema_editor.connection.vendor == "sqlite":
        schema_editor.execute("ALTER TABLE transfers DROP COLUMN seller_name;")
        _sqlite_rebuild(schema_editor, nullable=False)
        return
    for statement in PG_REVERSE:
        schema_editor.execute(statement)


class Migration(migrations.Migration):
    dependencies = [
        ("customers", "0067_def_cus_6408_billing_address_parts"),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
        migrations.AlterField(
            model_name="transfer",
            name="customer",
            field=models.ForeignKey(
                db_column="customer_id",
                null=True,
                on_delete=models.deletion.PROTECT,
                to="customers.customer",
            ),
        ),
        migrations.AddField(
            model_name="transfer",
            name="seller_name",
            field=models.TextField(blank=True, null=True),
        ),
    ]
