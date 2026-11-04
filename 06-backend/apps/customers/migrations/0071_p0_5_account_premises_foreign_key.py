# ── Trace ──────────────────────────────────────────────
# Task:     Finance blueprint `P0.5` (2026-09-24) — the fourth of the four
#           remaining deferred FKs. Outcome: *"Ten deferred FKs become zero"*.
# Rules:    `BR-CUS-1010` (an owner's account is anchored on a PREMISES, which
#           is why this column exists at all) · `B11 F-3` (the DEFERRED-FK
#           convention) · CLAUDE.md hard rule 8 (the address lives on
#           `premises` and everything else walks to it) · hard rule 1
# Tests:    06-backend/tests/test_p0_4_gl_pointers_are_foreign_keys.py
# ───────────────────────────────────────────────────────
"""customers 0071 — **an account's premises is a real reference.**

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering. Ledger row:
`12-governance/09-human-review-ledger.md`, *"A stale GL account id is refused
when it is saved"* (this column travels with that group).

WHAT THIS DOES
--------------
    accounts.premises_id -> metering.premises(id)

`accounts.premises_id` was written under `B11 F-3` as a plain uuid and says so
in its own comment — *"BR-CUS-1010 (deferred FK → metering)"*. It is the anchor
for a premises-anchored master account, and `ck_accounts_anchored` already
makes *unit OR premises* a database guarantee. What was still missing is that
the premises it names is one that EXISTS.

⚠ **THIS IS THE ADDRESS CHAIN, WHICH IS WHY IT MATTERS MORE THAN AN ORDINARY
POINTER.** CLAUDE.md hard rule 8 puts the address on `premises` and has every
other entity — asset, account, route, invoice, work order, map pin — *"derive
it by walking to the premises"*. An account whose `premises_id` names nothing
therefore has **no address at all**, and the failure is silent: the walk
returns null and a bill prints with an empty service address. `DEF-CUS-3653` is
the same shape one column over — a header line that would have returned null on
every account for ever, with `tsc` and every test green.

PROVED NO ORPHANS FIRST — `P0.4`'s instruction, applied here
--------------------------------------------------------------
Measured on the seeded database (PostgreSQL 16.13, tenant `brazosbend`,
2026-09-24): `accounts.premises_id` — **75 rows, 75 set, 0 orphans**. And the
constraint validates every row itself, so a stale id would refuse this
migration rather than ship inside it.

WHY THE MODEL DOES NOT BECOME A `ForeignKey` FIELD
----------------------------------------------------
`billing/0030` states the general reasoning. **Here there is a second, sharper
one:** `accounts.premises_id` is named inside `ck_accounts_anchored`'s `Q()`
and inside `ix_accounts_tenant_premises`'s `fields=[...]`, and `Meta.indexes`
takes FIELD names rather than attnames — so renaming the field would require
hand-editing a CHECK constraint and an index on the busiest table in the
product, in a module two other lanes are editing today, for no behaviour the
constraint does not already provide.

⚠ **ONE CONSEQUENCE, STATED:** the delete behaviour is PostgreSQL's `NO
ACTION`, so a premises that an account is anchored on can no longer be deleted.
That is the correct answer and the one `on_delete=PROTECT` would have given —
and it is a REAL behaviour change worth a reviewer's eye, because deleting a
premises is something a clerk can attempt. It fails loudly now instead of
leaving an account pointing at nothing.

REVERSIBLE; SQLITE KEEPS THE PLAIN COLUMN
------------------------------------------
`DROP CONSTRAINT IF EXISTS`; no row created, changed or deleted in either
direction. `ALTER TABLE … ADD CONSTRAINT` does not exist on SQLite (the default
test tier), so nothing is written there — `ledger/0005`'s posture.
"""

from django.db import migrations

FOREIGN_KEYS = (("fk_accounts_premises", "accounts", "premises_id", "premises"),)


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
        ("customers", "0070_p0_2_primary_holder"),
        ("metering", "0061_cr131_premises_membership"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunPython(_add, _drop)],
            state_operations=[],
        ),
    ]
