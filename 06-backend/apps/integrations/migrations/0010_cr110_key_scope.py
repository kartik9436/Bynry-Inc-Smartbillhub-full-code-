# ── Trace ──────────────────────────────────────────────
# Story:    CR-110-BRC04 wave D — migration 2 of 2. "A key names the APIs it
#           may call." Blueprint p017, `CR-4`, tagged *SECURITY SHAPE · RULED:
#           SCOPE IT*; PO 2026-09-16, verbatim: *"we ahve to build it - pelase
#           let me know what you need - i already answer it"*, over a row that
#           named "which calls a partner's key may make" among three controls.
# Rules:    BR-INT-053 (a machine credential is scoped to one tenant — this
#           narrows it further, to named operations) · BR-INT-025 (a credential
#           is versioned, never updated: a scope belongs to ONE version) ·
#           CLAUDE.md hard-won law 3 (blank grants nothing) · 🔒 migration
#           ordering + webhook keys/credentials
# ───────────────────────────────────────────────────────
"""integrations 0010 — `integration_credential.scope`: which of our APIs one key may call.

HUMAN-OWNED (🔒 migration ordering, and the column decides what an unsigned-in
machine may reach). HUMAN-REVIEW-PENDING — AI-authored 2026-09-16 under the PO
ruling of 2026-08-09; the review-ledger row is in
`12-governance/09-human-review-ledger.md`.

ONE COLUMN, AND THE BLUEPRINT ALREADY CALLED THE ABSENCE A DEFECT
------------------------------------------------------------------
p017, verbatim: *"a partner handed a key to push meter readings can call every
other inbound API on that connector — because there is no field that says which
ones they may call."* This is that field. Six connectors issue keys today — the
five ERPs and the kiosk network — and until this column each key opened every
operation its connector declares, and would have opened a seventh the day one
was added to the manifest.

⚠ **ON THE CREDENTIAL AND NOT ON THE CONNECTION, WHICH IS THE ONLY INTERESTING
CHOICE IN THIS FILE.** A scope on the connection would be a property of the
relationship, and it would silently carry forward: `BR-INT-025` says a
credential is versioned and never updated, so replacing a key writes v(n+1) —
and replacing a key is precisely the moment a partner's reach is meant to be
reconsidered. On the credential, v(n) and v(n+1) may lawfully differ and the
audit row records both sides. On the connection, the new key would inherit the
old one's reach and nobody would be asked.

⚠ **`DEFAULT '[]'` MEANS GRANTED NOTHING, WHICH IS THE OPPOSITE OF WHAT THE
DRAWING SAYS AND IS THE WHOLE POINT.** The wireframe puts *"Leave blank for
everything the key allows"* under its Scope box — the widest permission as the
default — and `CR-110-BRC04` decision 5 refuses it under hard-won law 3: the
unsafe option must be the one you type. Two guards point the same way and both
are needed: `machine_auth._validated_scope` refuses to MINT an empty scope, and
`serve.scope_permits` refuses to HONOUR one if a row ever arrives by another
road. The column default is the third, in the database, for a row written by
some future path that forgets — it arrives powerless rather than omnipotent.

⚠ **NOT NULLABLE, DELIBERATELY.** A NULL here would be a third state — *nobody
said* — sitting between *nothing* and *something*, and every reader would have
to decide what it meant. One of them would eventually decide it meant
everything. `jsonb NOT NULL DEFAULT '[]'` has two states and the empty one is
the safe one.

⚠ **NO BACKFILL, AND A BACKFILL WOULD HAVE BEEN THE BUG.** There are **0
`integration_credential` rows** in this product — verified in the change
request: nothing issues a key outside an authenticated API call, no seed or
fixture issues one, and the set-up screen has no route at all, so no partner
anywhere holds a key. Had there been rows, the tempting backfill is *"grant
each existing key everything it can do today, so nothing breaks"* — which would
write the defect into the database as data on the day it was supposed to be
fixed, and leave no way to tell a deliberate grant from an inherited one. The
correct answer for an existing key would have been to re-issue it.

⚠ **THE COLUMN INHERITS `integration_credential`'s RLS.** `0002_rls_force` put
`FORCE ROW LEVEL SECURITY` on the table and the policy is over the ROW, not
over a column list, so a column added later is covered the moment it exists.
Nothing here re-states the policy; a lane checking that should read `0002`.

⚠⚠ **ADDING THIS COLUMN SILENTLY DESTROYED THE ONE-ACTIVE-CREDENTIAL GUARD ON
SQLITE, AND PUTTING IT BACK IS HALF THIS MIGRATION.**

`BR-INT-025` — exactly one ACTIVE credential per connection — is enforced by
the database, and `0001` writes it two ways: an `EXCLUDE` constraint on
PostgreSQL, and on SQLite a hand-written partial index,
`ux_integration_credential_one_active ON integration_credential (connection_id)
WHERE is_active`. **SQLite cannot add a column in place, so Django's SQLite
backend REBUILDS THE TABLE** — create, copy, drop, rename — and a rebuild
carries only the indexes Django knows about from the model. A partial index
created by raw SQL in an earlier migration is not one of them, so it is dropped
and never recreated.

**Nothing says so.** The migration applies cleanly, every column is right, and
the guarantee is simply gone. `test_us_int_014_the_database_refuses_a_second_
active_credential_on_sqlite_too` caught it with *"DID NOT RAISE
IntegrityError"* — and had that case not existed, the ENTIRE test suite would
have carried on green over a vendor where two live keys can exist on one
connection at once, which is the shape of `BR-INT-025` this product's tests are
measured against.

PostgreSQL is untouched: `ALTER TABLE … ADD COLUMN` does not rebuild, so the
`EXCLUDE` survives. **That asymmetry is the trap**: the vendor that keeps its
guarantee is the one nobody tests on by default, and the vendor that loses it
is the one every lane runs.

⚠ **THE GENERAL LESSON IS NOT ABOUT THIS COLUMN.** Any future `AddField`,
`AlterField` or `RemoveField` on `integration_credential` will do this again.
The index is recreated below with `IF NOT EXISTS`, so re-running is safe — and
a lane touching this table should copy that block rather than rediscover it.

REVERSING IT
-------------
`RemoveField`, which drops the column and the permissions with it. Reversing
this migration re-opens the defect the blueprint named, so it is a rollback of
last resort rather than a tidy-up: after it, every issued key can call
everything on its connector again. ⚠ The reverse ALSO rebuilds the table on
SQLite, so `restore_one_active` is its own reverse — the guard is put back
whichever direction this migration is run in.
"""

from django.db import migrations, models

#: `0001`'s own SQL, repeated verbatim rather than imported, because a
#: migration is a record of what was done and must read the same in a year.
ONE_ACTIVE_SQLITE = """
CREATE UNIQUE INDEX IF NOT EXISTS ux_integration_credential_one_active
  ON integration_credential (connection_id) WHERE is_active;
"""

#: The DATABASE default. Django uses a field default to BACKFILL an `AddField`
#: and then **drops it** (`ALTER COLUMN … DROP DEFAULT`), because it applies
#: defaults in Python. This puts it back.
SCOPE_DEFAULT_PG = """
ALTER TABLE integration_credential ALTER COLUMN scope SET DEFAULT '[]'::jsonb;
"""


def restore_one_active(apps_registry, schema_editor):
    """Put `BR-INT-025`'s SQLite guard back after the table rebuild.

    ⚠ **IT IS ITS OWN REVERSE, AND THAT IS DELIBERATE.** Both directions of an
    `AddField` rebuild the table on SQLite, so both directions lose the index.
    A reverse that dropped it would leave a rolled-back database weaker than
    the one it rolled back to.

    PostgreSQL never rebuilds on `ADD COLUMN`, so its `EXCLUDE` constraint is
    untouched and this is a no-op there.
    """
    if schema_editor.connection.vendor != "sqlite":
        return
    schema_editor.execute(ONE_ACTIVE_SQLITE)


def restore_scope_default(apps_registry, schema_editor):
    """Put the DATABASE default back, because the docstring promises it.

    ⚠ **THIS EXISTS BECAUSE THE PARAGRAPH ABOUT `DEFAULT '[]'` WAS A CLAIM AND
    NOT A FACT, AND A SIBLING'S TEST SAID SO.** `AddField(default=list)` tells
    Django what to backfill existing rows with; Django then **drops the
    default**, because it applies defaults in Python. So a row written by any
    path that does not go through the ORM — a raw `INSERT`, a data migration, a
    DBA — would have hit `null value in column "scope" … violates not-null
    constraint` instead of arriving with nothing granted.

    That is exactly what happened: `test_us_int_014_pg.py::test_..._tc1_the_
    database_refuses_a_second_active_credential`, which is somebody else's case
    about a different guarantee entirely, started failing because its raw
    `INSERT` omitted a column that did not exist when it was written. **It was
    right to fail**, and it named the real gap rather than the one it was
    watching.

    The third guard this migration's docstring describes — *a row written by
    some future path that forgets arrives powerless rather than omnipotent* —
    is this line, and until now it was a sentence rather than a default.

    PostgreSQL only: SQLite has no `ALTER COLUMN`, and Django's table rebuild
    there writes the column with its default already in the `CREATE TABLE`.
    """
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(SCOPE_DEFAULT_PG)


def drop_scope_default(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("ALTER TABLE integration_credential ALTER COLUMN scope DROP DEFAULT;")


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0009_cr110_rate_limit_store"),
    ]

    operations = [
        migrations.AddField(
            model_name="integrationcredential",
            name="scope",
            field=models.JSONField(blank=True, default=list),
        ),
        # ⚠ NOT OPTIONAL AND NOT TIDY-UP. See the docstring — the AddField
        # above rebuilds this table on SQLite and takes BR-INT-025's guard with
        # it, silently.
        migrations.RunPython(restore_one_active, restore_one_active),
        # ⚠ AND THE DATABASE DEFAULT, WHICH `AddField` CREATES AND THEN DROPS.
        # Without it a raw INSERT gets a NOT NULL violation instead of a row
        # that grants nothing — see `restore_scope_default`.
        migrations.RunPython(restore_scope_default, drop_scope_default),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-110-BRC04 (PO rulings 2026-09-16) + blueprint p017 CR-4 + BR-INT-053
# generated: 2026-09-16 by the CR-110-BRC04 wave D build lane
# checklist: A✔ B=n/a(the Scope box is another lane's screen) C✔ D✔(POST /integrations/{key}/key takes `scope`) E=n/a F✔ G✔ H=PENDING(🔒 — row in 09-human-review-ledger.md)
# gates: makemigrations --check clean · sqlmigrate prints one ADD COLUMN (NOT NULL with a default, no table rewrite on PG 11+) · tests/test_us_int_014_tables.py (the one-active guard still bites on SQLite AFTER this migration) · tests/test_cr110_key_scope.py (an empty scope cannot be issued; an unknown operation cannot be issued; the door refuses an operation outside the scope in the SAME five words and the same time as a wrong key)
# exceptions: the RunPython is NOT an index of this migration's own — it RESTORES `BR-INT-025`'s SQLite partial unique index, which Django's SQLite table-rebuild drops silently on any AddField. Found by test_us_int_014_..._on_sqlite_too going DID NOT RAISE. No backfill: every existing row would read `[]`, and there are none
# status: VERIFIED-UNRATIFIED (🔒 HUMAN-REVIEW-PENDING)
# ──────────────────────────────────────────────────────────
