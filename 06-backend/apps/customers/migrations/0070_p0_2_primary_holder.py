# ── Trace ──────────────────────────────────────────────
# Task:     Finance blueprint `P0.2` (2026-09-24) — *"An account with two live
#           customers names which one is billed; `P0.1` has an answer to
#           stamp"*. The blueprint's cross-module register calls it a
#           **prerequisite** for stamping a customer on a journal line.
# Rules:    `BR-CUS-054` (the customer link is N:M — a jointly-held account is
#           LAWFUL and stays lawful) · `BR-CUS-1030` (a sale ENDS a link rather
#           than deleting it, which is why the constraint is partial on
#           `ended_at`) · CLAUDE.md hard rule 1 (tenant scoping — see
#           `_backfill`, where it is the whole difficulty)
# Tests:    06-backend/tests/test_p0_2_primary_holder.py
# ───────────────────────────────────────────────────────
"""customers 0070 — **which of two joint holders is the one billed.**

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is on CLAUDE.md's
sensitive-paths list, and this one carries a BACKFILL over live links. Ledger
row: `12-governance/09-human-review-ledger.md`, *"Which of two joint holders is
the one billed"*.

WHAT WAS MISSING
----------------
`customer_accounts` is N:M by design (B2 r9 #1) so that an account can be held
jointly — and **nothing in it said which holder is billed**. Everything that has
to name one person then takes whichever row the database hands back first: the
statement header, a notice's addressee, and, from `P0.1`, the customer stamped
onto a journal line, which is immutable the moment it posts.

WHAT THIS ADDS — A COLUMN, A BACKFILL AND A CONSTRAINT, IN THAT ORDER
---------------------------------------------------------------------
1. `is_primary boolean NOT NULL DEFAULT false`.
2. The backfill, below.
3. `uq_customer_accounts_primary_live` — UNIQUE on `(account_id)` WHERE
   `is_primary AND ended_at IS NULL`.

**THE ORDER IS LOAD-BEARING.** The constraint goes on AFTER the backfill, so it
validates the rows the backfill wrote. Adding it first would validate an
all-false table — which cannot violate a uniqueness rule — and the backfill
would then be the one unguarded step.

THE BACKFILL, AND WHAT IT DELIBERATELY DOES NOT DO
--------------------------------------------------
The blueprint's words: *"backfill where a link is the only live one"*. So:

    an account with EXACTLY ONE live link   ->  that link becomes primary
    an account with TWO OR MORE live links  ->  nothing is written

The second line is the important one. Two joint holders and no stated
preference is a fact the product does not know, and inventing an answer — the
oldest link, the alphabetically first name — would put a stranger's name on a
bill and leave no trace that anybody guessed. **An account whose live links are
all `false` is therefore a REAL state**, and callers must handle it.

⚠ THE TENANT LOOP IS NOT CEREMONY — WITHOUT IT THIS BACKFILL WRITES NOTHING
---------------------------------------------------------------------------
`customer_accounts` carries `ENABLE ROW LEVEL SECURITY` **and `FORCE`**
(`customers/0002`), and FORCE applies to the table OWNER as well. The policy is
`tenant_id = current_setting('app.tenant_id')::uuid`, so a session that has not
set that GUC sees **no rows at all** — and a migration has not set it.

Measured as the role the migration runs as, on PostgreSQL 16.13, 2026-09-24:
`SELECT count(*) FROM customer_accounts` with no `app.tenant_id` returns **0**;
with it set it returns **54**. A backfill written the obvious way would
therefore report success, touch nothing, and leave every account unnominated
while the migration history said it had been done — hard-won law 7's
*structurally incapable of failing* shape, in a data migration.

`tenants` carries **no** RLS (measured: `relrowsecurity = false`), so it can be
enumerated without context; that is the door `assets/0003` already uses and
`customers/0003`'s own docstring names. `SET LOCAL` keeps the context inside
this transaction, so nothing downstream inherits a tenant.

On SQLite (the default test tier) there is no RLS and no `set_config`, so the
statement runs once, unscoped, and means exactly the same thing.

REVERSIBLE, AND THE REVERSE INVENTS NOTHING
-------------------------------------------
`AddConstraint` reverses to `DROP CONSTRAINT`; `AddField` to `DROP COLUMN`. The
backfill's reverse is a no-op **by design, and it says so**: the column it wrote
into is dropped by the step that follows it, so there is nothing to restore, and
a reverse that set rows back to `false` would only be writing to a column on its
way out. No `customer_accounts` row is created or deleted in either direction.
"""

from django.db import migrations, models

# Frozen SQL. An account with exactly one LIVE link gets that link nominated;
# an account with two or more gets nothing. `ended_at IS NULL` is
# `CustomerAccount.live()`'s definition written out in SQL, and the two must
# stay equal — the test asserts the behaviour, not the string.
BACKFILL_SQL = """
    UPDATE customer_accounts AS ca
       SET is_primary = TRUE
     WHERE ca.ended_at IS NULL
       AND ca.is_primary = FALSE
       AND (
             SELECT count(*)
               FROM customer_accounts AS peer
              WHERE peer.tenant_id  = ca.tenant_id
                AND peer.account_id = ca.account_id
                AND peer.ended_at IS NULL
           ) = 1
"""


def _backfill(_apps, schema_editor):
    """Nominate the sole live holder of every singly-held account.

    See the module docstring for why this loops over tenants instead of running
    one statement: RLS FORCE makes the obvious version a silent no-op.
    """
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        if connection.vendor != "postgresql":
            cursor.execute(BACKFILL_SQL)
            return
        cursor.execute("SELECT id FROM tenants")
        tenant_ids = [row[0] for row in cursor.fetchall()]
        for tenant_id in tenant_ids:
            cursor.execute("SELECT set_config('app.tenant_id', %s, true)", [str(tenant_id)])
            cursor.execute(BACKFILL_SQL)


def _unbackfill(_apps, _schema_editor):
    """Deliberately nothing — see the module docstring.

    The column this wrote into is dropped by the `AddField` reverse that runs
    immediately after it, so there is no state left to restore, and writing to a
    column on its way out would only obscure that.
    """
    return None


class Migration(migrations.Migration):
    dependencies = [
        ("customers", "0069_def_cus_6431_resale"),
        ("identity", "0005_cr070_f_field_technician"),
        ("tenancy", "0048_p0_13_je_series_format"),
    ]

    operations = [
        migrations.AddField(
            model_name="customeraccount",
            name="is_primary",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(_backfill, _unbackfill),
        migrations.AddConstraint(
            model_name="customeraccount",
            constraint=models.UniqueConstraint(
                condition=models.Q(("ended_at__isnull", True), ("is_primary", True)),
                fields=("account",),
                name="uq_customer_accounts_primary_live",
            ),
        ),
    ]
