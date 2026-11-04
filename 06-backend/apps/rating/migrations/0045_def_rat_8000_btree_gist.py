# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-RAT-8000 — B2 §2's `EXCLUDE USING gist` no-overlap constraint on
#          `tariff_versions` has never existed, because `btree_gist` has never
#          been installed. `rating/0004`'s own header reported that and left it
#          "for the human review of this row"; the review never happened.
# Rules:   B2 §2 (the signed constraint) · CLAUDE.md 🔒 migration ordering ·
#          hard-won law 3 (the unsafe option is the one you type — this one is
#          `IF NOT EXISTS`, so a database that already has it is untouched)
# Tests:   06-backend/tests/test_def_rat_8000_no_overlap_pg.py
# ───────────────────────────────────────────────────────
"""rating 0045 — **install `btree_gist`, which is step A1 and nothing else.**

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is a sensitive path
(CLAUDE.md, PO 2026-08-09: *"AI will do it; we will review it later as
human"*). Row in `12-governance/09-human-review-ledger.md`.

**WHY IT IS ITS OWN MIGRATION, AHEAD OF THE REPAIR AND AHEAD OF THE
CONSTRAINT.** The ordering is load-bearing three ways and a later step fails if
an earlier one is skipped:

    0045  the extension      — without it 0047's DDL cannot even parse
    0046  the data repair    — without it 0047 refuses on the violating rows
    0047  the constraint

An `EXCLUDE` that mixes an equality column (`tenant_id WITH =`) with a range
operator (`daterange(...) WITH &&`) needs gist operator classes for the scalar
types, and core gist does not ship them. That single missing extension is the
whole reason B2 §2's signed constraint was never materialised, and the whole
reason a rate schedule can hold four versions in force on one date.

⚠ **`06-backend/db/000_extensions.sql` GETS THE SAME LINE AND IS NOT ENOUGH ON
ITS OWN.** That file runs from `docker-entrypoint-initdb.d`, i.e. only on a
database being created for the first time. Every database that already exists
— which is every one that has this defect — will never run it again. That is
hard-won law 4 in schema form (*"a template change never reaches a host that
already has a `.env`"*), and it is why `tenancy/0001` already creates
`pgcrypto` and `citext` idempotently from a migration as well. This is the
third extension to take the same route, for the same reason.

⚠ **SQLITE GETS NOTHING AND THAT IS HONEST, NOT A GAP.** The test suite runs on
in-memory SQLite (`config/settings/test.py`), which has neither extensions nor
range-exclusion constraints, so the guarantee this chain adds **cannot be
exercised there at all** — hard-won law 14's shape for DDL. The live assertion
is `tests/test_def_rat_8000_no_overlap_pg.py`, which skips itself by name on
any vendor but PostgreSQL rather than passing vacuously.
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL


class Migration(migrations.Migration):
    dependencies = [
        ("rating", "0044_p0_4_p0_5_deferred_fks"),
    ]

    operations = [
        PostgresOnlySQL(
            sql="CREATE EXTENSION IF NOT EXISTS btree_gist;",
            # ⚠ THE REVERSE IS A NO-OP AND NOT `DROP EXTENSION`. Dropping it
            # would take every OTHER object that depends on it with it
            # (`DROP EXTENSION` cascades or refuses), and nothing about
            # un-applying this migration means the estate no longer wants the
            # extension. 0047 drops its own constraint on reverse; that is the
            # thing this migration exists to make possible, and it is the thing
            # a reverse should remove.
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
