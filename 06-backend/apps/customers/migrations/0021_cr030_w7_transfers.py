"""customers 0021 — CR-030 W7 task 7.1: the `transfers` table and its RLS.

HUMAN-OWNED (RLS policies + migration ordering are CLAUDE.md rule-1 🔒 paths).

HUMAN-REVIEW-PENDING — AI-authored 2026-08-25 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). A row in
`12-governance/09-human-review-ledger.md` is OWED and this lane may not write
that file; it is REPORTED. Not RATIFIED without a recorded sign-off.

WHAT THIS TABLE IS FOR
──────────────────────
B18 §5.7: *"The same customer, a new address — **one job, not a move-out
followed by a move-in.**"* One row is one job. It carries the FROM account, the
TO account once it exists, the customer both belong to, the target unit, the two
dates, which of the five steps the clerk has reached, and the single
`committed_at` instant at which BOTH halves became true.

⚠ **THERE IS NO MONEY COLUMN, AND THE ABSENCE IS THE DESIGN.** B18 §5.7.2's
MONEY cell stacks `deposit carried $153.50` and `arrear follows $542.10`; both
figures are COMPUTED at read time by `apps.customers.transfers.money_statement`
from the deposit position and the account balance, and BOTH carry a stated
absence because no signed rule authorises moving either (see that module's
docstring). A stored `deposit_carried` column would be a figure that reads as
money that MOVED, on a path where nothing moved — hard-won law 1, in a column
instead of a comment. What IS stored is the clerk's ELECTION (two booleans and
the instant it was taken), because an election is a decision and not a transfer.

⚠ **WHY THE TABLE IS CREATED BY RAW DDL AND THE MODEL IS `managed = False`.**
Every other customers table is a `CreateModel` over a model declared in
`apps/customers/models.py`. That file is NOT in this lane's write scope, and a
model Django never imports at startup is invisible to the autodetector — so a
`CreateModel` here would leave migration STATE holding a model the app registry
does not have, and `python manage.py makemigrations --check` would answer with
a `DeleteModel`. Measured, not assumed. So: this migration carries DDL only and
no model state, the model in `transfers.py` is `managed = False`, and the two
are held together by `tests/test_w7_transfers.py::test_tc_trf_12_*`, which
introspects the LIVE table and asserts a column for every model field and no
column the model does not declare. **The one line that retires all of this is
`from apps.customers import transfers` (carrying a `noqa: F401` comment) at
the foot of `apps/customers/models.py`** — exactly the line
`apps/rating/models.py:1628` carries for `apps/rating/discounts.py`, which is this repo's own precedent for
models living outside `models.py`. It is REPORTED, not slipped in.

⚠ **`to_unit_id` CARRIES NO FOREIGN KEY, DELIBERATELY.** The unit belongs to
metering. B2 §2 makes cross-module FKs *the reviewed interface set*, and this
one is not in it — `accounts.unit_id` is, and was reviewed. So the column holds
the id and `transfers.py` resolves it through `seams.unit_row`, which is the
boundary customers already uses for every other metering read. Adding an
unreviewed cross-module FK to close a nicety is the thing B2 §2 exists to make
somebody think about first. REPORTED.

⚠ **THE POLICY IS THE `NULLIF` FORM, NOT THE BARE CAST (DEF-639).**

    NULLIF(current_setting('app.tenant_id', true), '')::uuid

`, true` makes an unset GUC return NULL instead of raising; `NULLIF(…, '')`
turns the empty string into NULL; `tenant_id = NULL` is NULL, which is not TRUE,
so no row is visible and no row may be written. Deny-by-default (hard rule 1)
with one fewer way to brick a fresh deploy — the bare cast ERRORS during the
deferred FK validation at a migration's exit and is why `migrate` on an empty
database died at step 12 (OQ-354/DEF-622). G41 ratchets the old form; this
table is born in the new one. The migration clears no tenant context, so it
leaves no `''` marker behind and needs no nil sentinel.

RLS is Postgres-only, so it is a `PostgresOnlySQL` and skips honestly on the
sqlite test database. The live proof is the G5 isolation suite under the
NON-SUPERUSER probe role — the app connects as a superuser and superusers bypass
RLS unconditionally, which makes any assertion on the app's own connection
vacuous (`tests/isolation_helpers.py`).
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

TABLE = "transfers"

TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"

#: PostgreSQL DDL. `numeric` appears nowhere — see the module docstring on why
#: this table stores no money figure.
POSTGRES_DDL = (
    """
    CREATE TABLE transfers (
        id                     uuid        PRIMARY KEY,
        tenant_id              uuid        NOT NULL REFERENCES tenants(id),
        from_account_id        uuid        NOT NULL REFERENCES accounts(id),
        to_account_id          uuid        NULL     REFERENCES accounts(id),
        customer_id            uuid        NOT NULL REFERENCES customers(id),
        to_unit_id             uuid        NULL,
        out_date               date        NULL,
        in_date                date        NULL,
        step                   smallint    NOT NULL,
        state                  text        NOT NULL,
        deposit_carry_elected  boolean     NULL,
        arrears_follow_elected boolean     NULL,
        money_decided_at       timestamptz NULL,
        committed_at           timestamptz NULL,
        cancelled_at           timestamptz NULL,
        is_sample              boolean     NOT NULL,
        created_at             timestamptz NOT NULL,
        updated_at             timestamptz NOT NULL
    );
    """,
    """
    CREATE INDEX ix_transfers_tenant_state ON transfers (tenant_id, state);
    """,
    """
    CREATE INDEX ix_transfers_from_account ON transfers (tenant_id, from_account_id);
    """,
    """
    CREATE INDEX ix_transfers_to_account ON transfers (tenant_id, to_account_id);
    """,
    # ONE open job per outgoing account. A second open transfer off the same
    # account is two jobs claiming one tenancy, and step 5 would close it twice.
    """
    CREATE UNIQUE INDEX uq_transfers_open_from
        ON transfers (tenant_id, from_account_id)
        WHERE committed_at IS NULL AND cancelled_at IS NULL;
    """,
    # An account may be the INCOMING half of exactly one transfer, ever. Two
    # transfers pointing at one new account would each claim to have opened it.
    """
    CREATE UNIQUE INDEX uq_transfers_to_account
        ON transfers (tenant_id, to_account_id)
        WHERE to_account_id IS NOT NULL;
    """,
)

#: sqlite DDL — the test database. Types are Django's own sqlite mappings
#: (UUIDField → char(32), DateTimeField → datetime, BooleanField → bool), so an
#: ORM read/write over this table behaves identically on both vendors.
SQLITE_DDL = (
    """
    CREATE TABLE transfers (
        id                     char(32) NOT NULL PRIMARY KEY,
        tenant_id              char(32) NOT NULL REFERENCES tenants(id),
        from_account_id        char(32) NOT NULL REFERENCES accounts(id),
        to_account_id          char(32) NULL     REFERENCES accounts(id),
        customer_id            char(32) NOT NULL REFERENCES customers(id),
        to_unit_id             char(32) NULL,
        out_date               date     NULL,
        in_date                date     NULL,
        step                   smallint NOT NULL,
        state                  text     NOT NULL,
        deposit_carry_elected  bool     NULL,
        arrears_follow_elected bool     NULL,
        money_decided_at       datetime NULL,
        committed_at           datetime NULL,
        cancelled_at           datetime NULL,
        is_sample              bool     NOT NULL,
        created_at             datetime NOT NULL,
        updated_at             datetime NOT NULL
    );
    """,
    """
    CREATE INDEX ix_transfers_tenant_state ON transfers (tenant_id, state);
    """,
    """
    CREATE INDEX ix_transfers_from_account ON transfers (tenant_id, from_account_id);
    """,
    """
    CREATE INDEX ix_transfers_to_account ON transfers (tenant_id, to_account_id);
    """,
    """
    CREATE UNIQUE INDEX uq_transfers_open_from
        ON transfers (tenant_id, from_account_id)
        WHERE committed_at IS NULL AND cancelled_at IS NULL;
    """,
    """
    CREATE UNIQUE INDEX uq_transfers_to_account
        ON transfers (tenant_id, to_account_id)
        WHERE to_account_id IS NOT NULL;
    """,
)


def create_table(apps, schema_editor):  # type: ignore[no-untyped-def]
    """The table, in the DDL of whichever vendor is actually connected.

    Frozen text on both sides, on purpose: a migration that reached into the
    live model class for its DDL would silently change what it builds every
    time somebody edits the model, which is the Django anti-pattern that makes
    a fresh database and an upgraded one disagree about columns.
    """
    statements = POSTGRES_DDL if schema_editor.connection.vendor == "postgresql" else SQLITE_DDL
    for statement in statements:
        schema_editor.execute(statement)


def drop_table(apps, schema_editor):  # type: ignore[no-untyped-def]
    schema_editor.execute("DROP TABLE IF EXISTS transfers;")


POLICY = f"""
ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY;
CREATE POLICY {TABLE}_tenant_isolation ON {TABLE}
  USING      (tenant_id = {TENANT})
  WITH CHECK (tenant_id = {TENANT});
"""

REVERSE = f"""
DROP POLICY IF EXISTS {TABLE}_tenant_isolation ON {TABLE};
ALTER TABLE {TABLE} NO FORCE ROW LEVEL SECURITY;
ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):
    """⚠ **NAMED `0021_cr030_w7_transfers` AND THE NUMBER MAY COLLIDE.** Lane
    S3 is writing `apps/customers/disconnects.py` and its own migration into
    this directory in the same session. Both of us depend on `0020`, so if S3
    also lands a `0021_*`, Django reports *"Conflicting migrations detected;
    multiple leaf nodes in the migration graph"* and a `--merge` migration is
    owed. The highest number present when this was written was 0020 (measured,
    `ls apps/customers/migrations/`). REPORTED rather than worked around: a
    lane may not renumber to dodge a collision it cannot see."""

    dependencies = [("customers", "0020_rls_sr_document_requirements")]

    operations = [
        migrations.RunPython(create_table, drop_table),
        PostgresOnlySQL(POLICY, reverse_sql=REVERSE),
    ]
