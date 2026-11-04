# ── Trace ──────────────────────────────────────────────
# Change:   Finance blueprint `P0.13` (2026-09-24) — the `JE-` series format the
#           PO ruled on 2026-09-23, verbatim: *"you need je-MMDDYY- nnnn like
#           this otherwise it will not work"*.
# Rules:    `BR-TEN-035` (numbering: format + monotonic counter, per tenant,
#           validated grammar, ≤24 chars, pad ≤8) · `BR-LED-021` (a journal
#           entry carries a `JE-` number, stamped AT POST) · CLAUDE.md hard
#           rule 1 (the RLS policy on `number_series` is untouched)
# Tests:    06-backend/tests/test_p0_13_je_series_format.py
# ───────────────────────────────────────────────────────
"""tenancy 0048 — **the `JE-` series becomes `JE-MMDDYY-nnnn`.**

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is on CLAUDE.md's
sensitive-paths list, so the marker is here because the PATH is the category.
Ledger row: `12-governance/09-human-review-ledger.md`, *"The journal-entry
number a finance officer reads aloud"*.

WHAT CHANGES
------------
`core.numbering.SERIES_CATALOG[JOURNAL_ENTRY]` now leads with
`JE-{MM}{DD}{YY}-{0000}`, so every tenant provisioned from now on is seeded
with it. This migration is the other half: it moves the tenants that ALREADY
have a row.

    UPDATE number_series
       SET format = 'JE-{MM}{DD}{YY}-{0000}'
     WHERE series = 'journal_entry'
       AND format = 'JE-{000000}'
       AND next_number = 1;

**THE PREDICATE IS THREE CLAUSES AND EVERY ONE OF THEM IS LOAD-BEARING.**

* `series = 'journal_entry'` — no other series moves. `DEP-`, `BL-`, `PY-` and
  the twenty-eight others are untouched; the PO ruled about this one.
* `format = 'JE-{000000}'` — **only the SEEDED default moves.** A utility that
  went to Settings → Numbering and chose `JE-{YYYY}-{0000}` keeps it. Their
  choice is a tenant setting and a platform upgrade may not overwrite one.
* `next_number = 1` — **only a series that has NEVER ISSUED A NUMBER moves.**
  This is the clause that makes the change safe rather than merely tidy. Once
  a tenant has posted `JE-000104`, changing the format would leave the books
  holding two spellings of the same series with no way to order or group them,
  and `journal_entries.number` is frozen by `ledger_journal_entry_immutable()`
  (`ledger/0007`) so the old ones could never be re-spelled. A tenant in that
  state is LEFT ALONE and changes format, if they want to, from the Numbering
  tab with their eyes open.

WHAT WAS MEASURED BEFORE THIS WAS WRITTEN
-----------------------------------------
On the seeded development database (PostgreSQL 16.13, tenant `brazosbend`),
2026-09-24:

    journal_entries               167 rows,   0 carry a number
    journal_lines                 661 rows
    number_series.journal_entry   format 'JE-{000000}', next_number 1

So the move costs nothing today: **no number exists to be re-spelled**, which
is exactly the window this migration is being run in. The blueprint records the
same fact as *"Free today — 0 of 168 entries carry a number, so there is
nothing to migrate"*; the live figure is 167, and the part that matters — zero
numbered — is identical.

⚠ **AND THE WINDOW CLOSES.** `P0.3` makes `posting.post()` allocate a number on
every system-posted entry. From the first bill run after that lands, this
series is consumed and the `next_number = 1` clause stops matching. That is the
stated reason this task goes FIRST.

REVERSIBLE, WITH ONE ASYMMETRY STATED
-------------------------------------
The reverse is the same UPDATE with the two formats swapped, under the same
`next_number = 1` guard. It invents no row and deletes none.

⚠ **It is not a perfect inverse, and the difference is worth naming:** a tenant
who is provisioned AFTER this migration, or who deliberately picks
`JE-{MM}{DD}{YY}-{0000}` from the Numbering tab and has not yet issued, is
moved to `JE-{000000}` by the reverse. That is the right answer for the first
(it is what the pre-migration world would have seeded them) and the wrong one
for the second (it discards a choice). Rolling this back is therefore a
*format* decision, not a data recovery, and no number is ever affected because
none has been issued.
"""

from django.db import migrations

# FROZEN SQL, and the two format strings are frozen module constants below —
# neither is read from `core.numbering`. `customers/0069`'s reasoning: a
# migration that consulted the live catalog would silently change meaning the
# next time the catalog moves, which is the one thing a migration may never do.
# They travel as BOUND PARAMETERS rather than inline literals because they
# contain `{` and `}` and would otherwise sit inside a Python format context.
# `CURRENT_TIMESTAMP` rather than `now()` because the default test tier is
# SQLite, which has no `now()`.
UPDATE_SQL = """
    UPDATE number_series
       SET format = %s, updated_at = CURRENT_TIMESTAMP
     WHERE series = 'journal_entry'
       AND format = %s
       AND next_number = 1
"""

NEW_FORMAT = "JE-{MM}{DD}{YY}-{0000}"
OLD_FORMAT = "JE-{000000}"


def _reformat(schema_editor, *, to_format: str, from_format: str) -> None:
    """Move every unconsumed `journal_entry` series, ONE TENANT AT A TIME.

    ⚠ **THE PER-TENANT LOOP IS NOT CEREMONY — WITHOUT IT THIS MIGRATION DOES
    NOTHING AT ALL, SILENTLY.** `number_series` carries
    `ENABLE ROW LEVEL SECURITY` **and `FORCE`** (`tenancy/0002`), and FORCE
    applies to the table OWNER as well, so a policy of
    `tenant_id = current_setting('app.tenant_id')::uuid` hides EVERY row from a
    session that has not set the GUC. A migration has not set it.

    Measured on PostgreSQL 16.13 before this was written, as the same role the
    migration runs as: `SELECT count(*) FROM number_series` with no
    `app.tenant_id` returns **0**, and with it set returns the tenant's rows.
    So a bare `RunSQL` here would report success, touch nothing, and the PO's
    ruling would silently not be in the product — hard-won law 7's *structurally
    incapable of failing* shape, in a migration.

    `tenants` itself carries **no** RLS (measured: `relrowsecurity = false`), so
    it can be enumerated without context. That is the door `assets/0003` already
    uses for exactly this, and `customers/0003`'s own docstring names it.

    On SQLite (the default test tier) there is no RLS and no `set_config`, so
    the statement runs once, unscoped, and means the same thing.
    """
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        if connection.vendor != "postgresql":
            cursor.execute(UPDATE_SQL, [to_format, from_format])
            return
        cursor.execute("SELECT id FROM tenants")
        tenant_ids = [row[0] for row in cursor.fetchall()]
        for tenant_id in tenant_ids:
            # SET LOCAL: scoped to this transaction, discarded on commit, so
            # the migration cannot leak a tenant context into whatever runs
            # next (CLAUDE.md hard rule 1).
            cursor.execute("SELECT set_config('app.tenant_id', %s, true)", [str(tenant_id)])
            cursor.execute(UPDATE_SQL, [to_format, from_format])


def forwards(_apps, schema_editor):
    _reformat(schema_editor, to_format=NEW_FORMAT, from_format=OLD_FORMAT)


def backwards(_apps, schema_editor):
    _reformat(schema_editor, to_format=OLD_FORMAT, from_format=NEW_FORMAT)


class Migration(migrations.Migration):
    dependencies = [
        ("tenancy", "0047_def_ten_6425_payment_plan_document_kinds"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
