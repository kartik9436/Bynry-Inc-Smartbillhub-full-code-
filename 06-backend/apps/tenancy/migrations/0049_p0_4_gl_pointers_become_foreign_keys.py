# ── Trace ──────────────────────────────────────────────
# Task:     Finance blueprint `P0.4` / `P0.12` (2026-09-24). Tenancy's half:
#           the two settings-side GL pointers.
# Rules:    `B11 F-3` (the DEFERRED-FK convention) · `B2 §2` · CLAUDE.md hard
#           rule 1 (no RLS policy is touched)
# Tests:    06-backend/tests/test_p0_4_gl_pointers_are_foreign_keys.py
# ───────────────────────────────────────────────────────
"""tenancy 0049 — **the two settings GL pointers become real references.**

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering. Ledger row:
`12-governance/09-human-review-ledger.md`, *"A stale GL account id is refused
when it is saved"*.

WHAT THIS DOES
--------------
    reason_codes.default_gl_account_id     -> ledger_accounts
    payment_methods.clearing_gl_account_id -> ledger_accounts

Both are **settings** a System Admin types on Settings → Accounting, which is
what makes them the likeliest of the nine to hold a wrong id: a chart account
deleted after it was mapped, or a value pasted from another tenant's setup. A
NULL here is a real and lawful state — both columns' own comments say so, and
the posting path resolves a designation instead — so this refuses only an id
that names NOTHING, and leaves *unmapped* exactly as it was.

PROVED NO ORPHANS FIRST — `P0.4`'s own instruction
----------------------------------------------------
Measured on the seeded database (PostgreSQL 16.13, tenant `brazosbend`,
2026-09-24), as `rows / set / orphans`:

    reason_codes.default_gl_account_id        5 / 5 / 0
    payment_methods.clearing_gl_account_id    8 / 8 / 0

⚠ And the constraint validates every row itself, so a stale id would refuse
this migration rather than ship inside it.

WHY THE MODELS DO NOT BECOME `ForeignKey` FIELDS — see `billing/0030`
----------------------------------------------------------------------
Same reasoning, stated in full there. Database operations only; the delete
behaviour is PostgreSQL's `NO ACTION`, which refuses the deletion of a
referenced chart account — the answer `on_delete=PROTECT` gives, reached from
the database side.

⚠ **A REVIEWER'S NOTE ON WHAT THIS DOES *NOT* GUARD.** A foreign key checks
that the id names a row in `ledger_accounts`. It does **not** check that the
row belongs to the SAME TENANT: PostgreSQL foreign keys run as the table owner
and see past row-level security. That is true of every cross-module FK already
in this database (`journal_lines` carries eight of them) and is not a
regression — tenant scoping is enforced in the application, by `hard rule 1`
and the RLS policies on the reading path. Stated so it is not mistaken for a
guarantee this constraint makes.

REVERSIBLE; SQLITE KEEPS THE PLAIN COLUMNS
-------------------------------------------
`DROP CONSTRAINT IF EXISTS` for each; no row created, changed or deleted in
either direction. `ALTER TABLE … ADD CONSTRAINT` does not exist on SQLite (the
default test tier), so nothing is written there — `ledger/0005`'s posture.
"""

from django.db import migrations

#: (constraint name, table, column, referenced table). Frozen text, never
#: derived from the live models.
FOREIGN_KEYS = (
    ("fk_reason_codes_default_gl_account", "reason_codes", "default_gl_account_id", "ledger_accounts"),
    (
        "fk_payment_methods_clearing_gl_account",
        "payment_methods",
        "clearing_gl_account_id",
        "ledger_accounts",
    ),
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
        ("tenancy", "0048_p0_13_je_series_format"),
        ("ledger", "0001_w5_journal_core"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunPython(_add, _drop)],
            state_operations=[],
        ),
    ]
