# ── Trace ──────────────────────────────────────────────
# Task:     Finance blueprint `P0.4` / `P0.12` (2026-09-24) — *"A stale or
#           typo'd GL id is refused at write, not found on a report"*, and
#           *"Three modules own the columns; each needs its own migration in
#           the same release"*. This is billing's half.
# Rules:    `B11 F-3` (the DEFERRED-FK convention these columns were written
#           under — a plain uuid until the target table exists) · `B2 §2`
#           (cross-module FKs are the reviewed interface set) · CLAUDE.md hard
#           rule 1 (no RLS policy is touched)
# Tests:    06-backend/tests/test_p0_4_gl_pointers_are_foreign_keys.py
# ───────────────────────────────────────────────────────
"""billing 0030 — **a GL pointer on a bill line is a real reference.**

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is on CLAUDE.md's
sensitive-paths list. Ledger row: `12-governance/09-human-review-ledger.md`,
*"A stale GL account id is refused when it is saved"*.

WHAT WAS DEFERRED, AND WHY IT IS NO LONGER DEFERRABLE
------------------------------------------------------
`invoice_lines.gl_account_id` and `adjustments.gl_account_id` were written as
bare `uuid` columns under `B11 F-3`, for a reason that was correct at the time
and each said so in its own comment: **`ledger_accounts` did not exist yet.**
It has existed since W5. What the columns kept in the meantime is the ability
to hold an id that names nothing — a mapping deleted, a value copied from
another tenant, a typo — and nothing refuses it until somebody reads a report
and finds money under an account that is not in the chart.

WHAT THIS DOES
--------------
Two `FOREIGN KEY … REFERENCES ledger_accounts(id) DEFERRABLE INITIALLY
DEFERRED` constraints, matching the shape every other cross-module FK in this
database already carries.

**PROVED NO ORPHANS FIRST**, which is `P0.4`'s own instruction. Measured on the
seeded database (PostgreSQL 16.13, tenant `brazosbend`, 2026-09-24):

    invoice_lines.gl_account_id     637 rows, 637 set, 0 orphans
    adjustments.gl_account_id         0 rows,   0 set, 0 orphans

⚠ **AND THE CONSTRAINT IS ITS OWN PROOF.** `ADD CONSTRAINT … FOREIGN KEY`
validates every existing row; PostgreSQL refuses the migration if one id names
nothing. So the pre-check above is a courtesy — it says what a failure would
mean before an operator sees one — and the guarantee comes from the database.

⚠ **`invoice_lines` IS A PARTITIONED PARENT**, with `invoice_lines_2026` and
`invoice_lines_2027` beneath it today and more minted by the create-ahead job.
On PostgreSQL 12+ a foreign key on a partitioned parent is propagated to every
existing partition and inherited by every future one; the test asserts it on
the parent AND on both partitions by name, because a parent-only constraint
would leave the guarantee off the tables the rows are actually in.

WHY THE MODELS DO NOT BECOME `ForeignKey` FIELDS
-------------------------------------------------
This is `SeparateDatabaseAndState` with **database operations only**, and the
choice is deliberate rather than lazy. Turning `gl_account_id` into a Django
`ForeignKey` renames the FIELD (to `gl_account`, with `db_column` unchanged),
and while `.gl_account_id` keeps working, `Meta.indexes`, `Q()` objects inside
`CheckConstraint`s and `values_list` arguments do not all follow the same rule
— so it is a wide, hand-verified change across modules two other lanes are
editing today, in exchange for nothing the database does not already give.

**What `P0.4` asks for is that the DATABASE refuse a bad id**, and that is what
a constraint does. The deferred-FK convention was always about the database
constraint being deferred, not about the Python type — the model comments say
*"DEFERRED FK → ledger_accounts"*, meaning *a foreign key we have put off*.
This is that foreign key.

⚠ **ONE CONSEQUENCE, STATED:** with no Django field, the delete behaviour is
PostgreSQL's default for a plain reference — `NO ACTION`, which REFUSES the
deletion of a referenced `ledger_accounts` row. That is the same answer
`on_delete=PROTECT` gives, arrived at from the database side, and it is the
right one: a chart account with money pointing at it may not vanish.

REVERSIBLE, AND THE REVERSE INVENTS NOTHING
-------------------------------------------
`DROP CONSTRAINT IF EXISTS`, propagating down the partition tree the same way.
No row is created, changed or deleted in either direction. Proved forward →
back → forward on real PostgreSQL with each constraint observed present →
absent → present on the parent and on both partitions.

**SQLite (the default test tier) keeps the plain columns**, exactly as
`ledger/0005` and `apps/metering/0003` do: `ALTER TABLE … ADD CONSTRAINT` does
not exist there, and writing a fake would be a lie about a guarantee. The live
assertions are the PostgreSQL suite's.
"""

from django.db import migrations

#: (constraint name, table, column, referenced table). Frozen text — never
#: derived from the live models, so this migration cannot change meaning when
#: a model does (`customers/0069`'s reasoning).
FOREIGN_KEYS = (
    ("fk_invoice_lines_gl_account", "invoice_lines", "gl_account_id", "ledger_accounts"),
    ("fk_adjustments_gl_account", "adjustments", "gl_account_id", "ledger_accounts"),
)


def _add(_apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        for name, table, column, target in FOREIGN_KEYS:
            cursor.execute(
                f"ALTER TABLE {table} ADD CONSTRAINT {name} "
                f"FOREIGN KEY ({column}) REFERENCES {target}(id) "
                "DEFERRABLE INITIALLY DEFERRED"
            )


def _drop(_apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        for name, table, _column, _target in FOREIGN_KEYS:
            cursor.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name}")


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0029_br_bil_1045_backfill_run_status"),
        # `ledger_accounts` must exist before anything may reference it.
        ("ledger", "0001_w5_journal_core"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunPython(_add, _drop)],
            state_operations=[],
        ),
    ]
