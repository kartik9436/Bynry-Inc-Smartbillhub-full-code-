# ── Trace ──────────────────────────────────────────────
# Task:     Finance blueprint `P0.4` · `P0.5` · `P0.12` — *"A stale or typo'd
#           GL id is refused at write, not found on a report"*, and *"Ten
#           deferred FKs become zero"*.
# Rules:    `B11 F-3` (the DEFERRED-FK convention being retired) · `B2 §2` ·
#           CLAUDE.md hard rule 1
# Code:     billing/0030 · rating/0044 · tenancy/0049 · customers/0071
# ───────────────────────────────────────────────────────
"""Every deferred pointer is a real reference now — proved on the database.

⚠ **WHAT WOULD MAKE THIS SUITE PASS WRONGLY** (hard-won law 7, habit 2):

1. **A constraint that exists but points at the wrong table.** `LIKE 'FOREIGN
   KEY (gl_account_id)%'` is satisfied by a reference to anything at all, so
   every case reads the constraint's FULL definition and asserts the target.
2. **A constraint on the PARTITIONED PARENT only.** `invoice_lines` is a
   partitioned parent and every row lives in `invoice_lines_2026` or a sibling;
   a parent-only constraint leaves the guarantee off the table the rows are in.
   `tc2` asks both partitions by name.
3. **A refusal that never fires because the statement is deferred.** Every FK
   here is `DEFERRABLE INITIALLY DEFERRED`, so PostgreSQL accepts the offending
   statement and judges it at COMMIT. A test that wrote a bad id inside a
   savepoint and expected a raise gets **`DID NOT RAISE`** and looks like a
   broken test rather than a deferred constraint — which is how a real one gets
   deleted as flaky. `tc3` forces the check with `SET CONSTRAINTS ALL
   IMMEDIATE`, and says so.
4. **A count that drifts.** `tc4` asserts the FULL set by name, so a constraint
   quietly dropped in a later migration goes red here rather than being noticed
   on a report.

PostgreSQL-only, and it skips loudly: SQLite has no `ALTER TABLE … ADD
CONSTRAINT`, so the migrations deliberately write nothing there and a green run
on the default suite says nothing whatever about any of this (hard-won law 14).
Run with `--ds=config.settings.pgtest`.
"""

import uuid

import pytest
from django.db import IntegrityError, connection, transaction

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

postgres_only = pytest.mark.skipif(
    connection.vendor != "postgresql",
    reason=(
        "these are DATABASE constraints and SQLite has no ALTER TABLE ADD "
        "CONSTRAINT, so the migrations write nothing there. A pass here would "
        "be meaningless — run with --ds=config.settings.pgtest (law 14)."
    ),
)

#: The whole set, as the four migrations install it: (constraint, table,
#: column, referenced table). Ten pointers — `P0.5`'s outcome sentence is
#: *"ten deferred FKs become zero"* — plus the four the blueprint's own count
#: missed, which the decision log records and `DEF-LED-6483` counts.
EXPECTED = (
    # billing/0030
    ("fk_invoice_lines_gl_account", "invoice_lines", "gl_account_id", "ledger_accounts"),
    ("fk_adjustments_gl_account", "adjustments", "gl_account_id", "ledger_accounts"),
    # rating/0044 — P0.4
    ("fk_charges_gl_account", "charges", "gl_account_id", "ledger_accounts"),
    ("fk_plan_services_gl_account", "plan_services", "gl_account_id", "ledger_accounts"),
    ("fk_discounts_gl_account", "discounts", "gl_account_id", "ledger_accounts"),
    ("fk_taxes_liability_gl_account", "taxes", "liability_gl_account_id", "ledger_accounts"),
    (
        "fk_taxes_collection_allowance_gl_account",
        "taxes",
        "collection_allowance_gl_account_id",
        "ledger_accounts",
    ),
    # rating/0044 — P0.5
    (
        "fk_tax_exemption_certificates_account",
        "tax_exemption_certificates",
        "account_id",
        "accounts",
    ),
    (
        "fk_tax_exemption_certificates_verified_by",
        "tax_exemption_certificates",
        "verified_by_id",
        "users",
    ),
    (
        "fk_plan_deposit_rules_account_type",
        "plan_deposit_rules",
        "account_type_id",
        "account_types",
    ),
    # tenancy/0049
    (
        "fk_reason_codes_default_gl_account",
        "reason_codes",
        "default_gl_account_id",
        "ledger_accounts",
    ),
    (
        "fk_payment_methods_clearing_gl_account",
        "payment_methods",
        "clearing_gl_account_id",
        "ledger_accounts",
    ),
    # customers/0071 — P0.5's fourth
    ("fk_accounts_premises", "accounts", "premises_id", "premises"),
)

INVOICE_LINE_PARTITIONS = ("invoice_lines_2026", "invoice_lines_2027")


def _definition(name: str) -> str | None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = %s", [name]
        )
        row = cursor.fetchone()
    return row[0] if row else None


@postgres_only
@pytest.mark.parametrize("name, table, column, target", EXPECTED, ids=[e[0] for e in EXPECTED])
def test_tc1_each_pointer_is_a_foreign_key_naming_the_right_table(name, table, column, target):
    """See note 1 — the TARGET is asserted, not merely the existence."""
    definition = _definition(name)
    assert definition, f"{table}.{column} has no constraint called {name}"
    assert definition.startswith(f"FOREIGN KEY ({column})"), definition
    assert f"REFERENCES {target}(id)" in definition, (
        f"{name} points somewhere other than {target}: {definition}"
    )


@postgres_only
def test_tc2_the_bill_line_constraint_reaches_every_partition():
    """See note 2 — `invoice_lines` is a partitioned parent and no row is in it.

    A parent-only foreign key would leave every actual invoice line unguarded
    while the catalog looked correct.
    """
    with connection.cursor() as cursor:
        for table in ("invoice_lines", *INVOICE_LINE_PARTITIONS):
            cursor.execute(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE contype = 'f' AND conrelid = %s::regclass "
                "  AND pg_get_constraintdef(oid) LIKE 'FOREIGN KEY (gl_account_id)%%'",
                [table],
            )
            row = cursor.fetchone()
            assert row, f"{table} has no foreign key on gl_account_id"
            assert "REFERENCES ledger_accounts(id)" in row[0], row[0]


@postgres_only
def test_tc3_the_database_refuses_a_gl_id_that_names_nothing(brazos, dana):
    """**The refusal is the deliverable.** A stale or typo'd GL id must be
    refused by the database rather than discovered on a report.

    ⚠ See note 3: the constraint is DEFERRABLE INITIALLY DEFERRED, so the
    offending UPDATE is ACCEPTED and judged at COMMIT. `SET CONSTRAINTS ALL
    IMMEDIATE` brings the judgement forward into the savepoint, which is both
    how the assertion becomes possible and the honest statement of when a real
    caller finds out: **their whole unit of work fails**, rather than a bad row
    landing and turning up later.

    ⚠ The savepoint is not tidiness. On PostgreSQL a failed statement poisons
    the transaction, so without one this test could not finish its own teardown
    (hard-won law 14).
    """
    stranger = str(uuid.uuid4())
    with tenant_ctx(brazos):
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM payment_methods")
            (count,) = cursor.fetchone()
        assert count > 0, "the fixture tenant has no payment methods to point at a GL account"

        with pytest.raises(IntegrityError) as caught:
            with transaction.atomic():  # the SAVEPOINT
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE payment_methods SET clearing_gl_account_id = %s", [stranger]
                    )
                    cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
        assert "fk_payment_methods_clearing_gl_account" in str(caught.value), (
            "something refused the write, but not the constraint under test — "
            f"got: {caught.value}"
        )


@postgres_only
def test_tc4_nothing_in_the_set_has_gone_missing():
    """See note 4 — the whole set, by name, in one assertion.

    `P0.5`'s outcome sentence is *"ten deferred FKs become zero"*. There are
    thirteen here: the blueprint's own count of the GL pointers in billing,
    rating and tenancy was six and the code holds nine (decision log
    2026-09-24, `DEF-LED-6483`). This list is the measured set, so a
    constraint dropped in a later migration goes red HERE rather than being
    found on a report.
    """
    missing = [name for name, *_ in EXPECTED if _definition(name) is None]
    assert missing == [], f"these foreign keys are gone: {missing}"
    assert len(EXPECTED) == 13


@postgres_only
def test_tc5_a_null_pointer_is_still_lawful(brazos, dana):
    """**Unmapped is a real state and must stay one.**

    Both tenancy columns' own comments say a NULL means *nobody has mapped
    this*, and the posting path resolves a designation instead. A foreign key
    refuses an id that names nothing; it must not refuse the absence of an id.
    Without this case, tightening a column to NOT NULL would pass every other
    test here and break Settings for every tenant that has not mapped a tender.
    """
    with tenant_ctx(brazos), connection.cursor() as cursor:
        cursor.execute("UPDATE payment_methods SET clearing_gl_account_id = NULL")
        cursor.execute(
            "SELECT count(*) FROM payment_methods WHERE clearing_gl_account_id IS NULL"
        )
        (nulls,) = cursor.fetchone()
    assert nulls > 0
