# ── Trace ──────────────────────────────────────────────
# Task:     Finance blueprint `P0.1` — *"A line posted today names the customer
#           who held the account then, and a later transfer does not change
#           it"*. Migration `ledger/0017`.
# Story:    `US-LED-002` TC-4 (a historical line keeps its stamped dimensions
#           for ever) · `BR-LED-001` (the dimension set lives on the LINE)
# Rules:    CLAUDE.md hard rule 4 (a posted line is never UPDATEd, so there is
#           no backfill and NULL is permanent on old rows) · hard rule 1
# Impacts:  apps/ledger/models.py (`JournalLine.customer`) ·
#           apps/ledger/posting.py (`P0.3` is what WRITES it)
# ───────────────────────────────────────────────────────
"""The sixth dimension, and the three ways it could have been wrong.

⚠ **WHAT WOULD MAKE THIS SUITE PASS WRONGLY** (hard-won law 7, habit 2), because
that is what decided which cases are here:

1. **The column reaches the PARENT and not the PARTITIONS.** `journal_lines` is
   a partitioned parent (`ledger/0005`), and every row actually lives in
   `journal_lines_2026` or a sibling. A test that read
   `information_schema.columns` for `journal_lines` alone would pass over a
   column that no row can carry. So `tc2` reads the parent **and both
   partitions by name**.
2. **The index looks absent when it is present.** A partitioned parent's index
   has CHILD indexes with GENERATED names, so looking for
   `ix_journal_lines_customer` on `journal_lines_2026` finds nothing and proves
   nothing. `tc3` walks `pg_inherits` from the parent index instead. The first
   probe written for this task got that wrong in both directions and reported
   ABSENT over two live indexes.
3. **The FK is declared in Django and not in the database.** A model-level
   `ForeignKey` that never reached PostgreSQL would still let `tsc`, the ORM
   and every ordinary test pass, and would admit a stale id silently — which is
   the whole point of `P0.4` one task later. `tc4` makes the DATABASE refuse a
   bad id, rather than asking Django whether it thinks there is a constraint.

`tc2`–`tc5` are **PostgreSQL-only and skip loudly** rather than silently: the
default suite is SQLite, which has no partitions and does not enforce a FK the
same way, so a green run there says nothing at all about any of this. Run them
with `--ds=config.settings.pgtest`.
"""

import uuid

import pytest
from django.db import IntegrityError, connection, transaction

from apps.customers import models as customer_models
from apps.ledger import models as ledger_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

PARTITIONS = ("journal_lines_2026", "journal_lines_2027")

postgres_only = pytest.mark.skipif(
    connection.vendor != "postgresql",
    reason=(
        "journal_lines is a PARTITIONED table and this asserts DATABASE-level "
        "constraints; SQLite has neither, so a pass here would be meaningless. "
        "Run with --ds=config.settings.pgtest (hard-won law 14)."
    ),
)


def test_tc1_the_model_declares_the_customer_as_a_protected_optional_fk():
    """The four properties the rule depends on, read off the field itself.

    `null=True` because there is no backfill (hard rule 4). `PROTECT` because
    `US-LED-002` TC-4 wants *forever* to be the database's problem. `db_column`
    because the wire name is `customer_id` and `attname` has to keep matching
    what `posting.py` writes.
    """
    field = ledger_models.JournalLine._meta.get_field("customer")
    assert field.null is True
    assert field.remote_field.model is not None
    assert field.remote_field.on_delete.__name__ == "PROTECT"
    assert field.db_column == "customer_id"
    assert field.attname == "customer_id"


@postgres_only
def test_tc2_the_column_reaches_the_parent_and_every_partition():
    """See note 1 in the module docstring — the parent is not where rows live."""
    with connection.cursor() as cursor:
        for table in ("journal_lines", *PARTITIONS):
            cursor.execute(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = %s AND column_name = 'customer_id'",
                [table],
            )
            assert cursor.fetchone(), f"{table} has no customer_id column"


@postgres_only
def test_tc3_the_index_reaches_every_partition_under_its_generated_name():
    """See note 2 — the child indexes are NOT called `ix_journal_lines_customer`.

    Asserted through `pg_inherits` from the parent index, which is the only
    question that distinguishes *"the index was created on the parent and
    propagated"* from *"the index exists on the parent alone"*.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM pg_inherits h "
            "JOIN pg_class child ON child.oid = h.inhrelid "
            "WHERE h.inhparent = (SELECT oid FROM pg_class WHERE relname = %s)",
            ["ix_journal_lines_customer"],
        )
        (children,) = cursor.fetchone()
    assert children == len(PARTITIONS), (
        f"ix_journal_lines_customer has {children} partition indexes, "
        f"expected one per partition ({len(PARTITIONS)})"
    )


@postgres_only
def test_tc4_the_foreign_key_names_customers_and_reaches_every_partition():
    """See note 3 — a model-level FK that never reached PostgreSQL proves
    nothing, and an FK pointing at the WRONG table proves less than nothing.

    Two facts per table, not one: that a foreign key on `customer_id` exists,
    and that it REFERENCES `customers`. `LIKE 'FOREIGN KEY (customer_id)%'`
    alone would pass on a constraint aimed anywhere.

    A parent-only FK would leave the guarantee off the tables the rows are
    actually in, so every partition is asked by name.
    """
    with connection.cursor() as cursor:
        for table in ("journal_lines", *PARTITIONS):
            cursor.execute(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE contype = 'f' AND conrelid = %s::regclass "
                "  AND pg_get_constraintdef(oid) LIKE 'FOREIGN KEY (customer_id)%%'",
                [table],
            )
            row = cursor.fetchone()
            assert row, f"{table} has no foreign key on customer_id"
            assert "REFERENCES customers(id)" in row[0], (
                f"{table}'s customer_id foreign key points somewhere else: {row[0]}"
            )


@postgres_only
def test_tc5_the_database_refuses_a_customer_id_that_names_nobody(brazos, dana):
    """**The refusal is the deliverable and it has to come from PostgreSQL.**

    ⚠ `journal_lines` is fenced by `trg_journal_lines_sole_writer`
    (`ledger/0004`), so a raw INSERT there is refused for a DIFFERENT reason —
    and a test that only checked *"the write failed"* would pass on the fence's
    refusal while the foreign key was absent. That is hard-won law 7's *looking
    at the wrong thing*, and it is why this asserts against `customer_accounts`
    instead: an unfenced table carrying the identical `REFERENCES customers(id)`
    shape, so the only thing that can refuse the write is the constraint under
    test. `tc4` holds the catalog proof for `journal_lines` itself.

    ⚠ **A SAVEPOINT, not a bare try/except.** On PostgreSQL a failed statement
    poisons the whole transaction, so without one this test would leave the
    connection unusable for its own teardown — the naive fix that passes the
    entire SQLite suite and loses the work in production. That is hard-won
    law 14, and `P0.9` is the task that proves it.

    ⚠ **AND THE REFUSAL ARRIVES AT COMMIT, NOT AT THE STATEMENT — WHICH THIS
    TEST FOUND BY BEING WRONG FIRST.** Every foreign key Django writes here is
    `DEFERRABLE INITIALLY DEFERRED`, so PostgreSQL accepts the offending
    statement and judges it when the transaction commits. The first version of
    this case did the UPDATE inside a savepoint and asserted a raise; it got
    `DID NOT RAISE IntegrityError`, because releasing a SAVEPOINT does not
    check deferred constraints. **A test written without that knowledge would
    have been quietly deleted as "flaky" and the guarantee would have gone with
    it.** `SET CONSTRAINTS ALL IMMEDIATE` brings the check forward to here;
    it is transaction-scoped and the savepoint rollback undoes it.

    The practical consequence, which is worth carrying into `P0.4`: a stale id
    is refused **when the work commits**, so the caller's whole unit of work
    fails — never a bad row that lands and is found on a report later.
    """
    stranger = str(uuid.uuid4())
    with tenant_ctx(brazos):
        # A real link, so there is a row for the UPDATE to break.
        premises = make_premises(dana)  # noqa: F405 — shared fixture helper
        account = customer_models.Account.objects.create(
            tenant=brazos,
            account_no=f"AC-{uuid.uuid4().hex[:8]}",
            status=customer_models.AccountStatus.objects.filter(tenant=brazos).first(),
            account_type=customer_models.AccountType.objects.first(),
            kind="master",
            premises_id=premises["id"],
        )
        customer = customer_models.Customer.objects.create(
            tenant=brazos, kind="person", display_name="Rosa Pemberton"
        )
        customer_models.CustomerAccount.objects.create(
            tenant=brazos, customer=customer, account=account
        )

        with pytest.raises(IntegrityError) as caught:
            with transaction.atomic():  # the SAVEPOINT
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE customer_accounts SET customer_id = %s WHERE account_id = %s",
                        [stranger, str(account.pk)],
                    )
                    # See the docstring: without this the deferred constraint
                    # is not judged until COMMIT and the savepoint hides it.
                    cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
        assert "customer" in str(caught.value).lower()

        # ...and the connection is still usable, which is the half a naive
        # `except IntegrityError: pass` would have destroyed.
        assert ledger_models.JournalLine.objects.count() >= 0
