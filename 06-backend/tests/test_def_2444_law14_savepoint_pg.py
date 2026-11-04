# ── Trace ──────────────────────────────────────────────
# Defect: DEF-2444 — `metering_seam` catches a database error and continues
#         INSIDE `issue_invoice`'s transaction, with no SAVEPOINT. On
#         PostgreSQL that aborts the whole transaction and the BILL IS LOST;
#         on SQLite it passes, green, every time.
# Rules:  CLAUDE.md hard-won law 14 (a failed statement poisons the whole
#         Postgres transaction, and the suite runs SQLite, which does not) ·
#         BR-BIL-055 (a break never blocks the run) · hard rule 4 (an issued
#         bill is immutable, so a bill lost at issue is a bill nobody has)
# Tests:  this file
# ───────────────────────────────────────────────────────
"""Law 14, proved on the database that actually has the failure mode.

⚠ **THIS FILE IS SKIPPED ON SQLITE ON PURPOSE, AND THE SKIP IS THE POINT.**
`config/settings/test.py` hardcodes in-memory SQLite, which has NO
aborted-transaction state, so the version of `metering_seam` WITHOUT its
savepoints passes the entire suite on every machine. The only way to see the
defect is to execute a failing statement inside a transaction on real
PostgreSQL and then try to execute another one.

Run it with a real database:

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
        pytest tests/test_def_2444_law14_savepoint_pg.py

What it asserts is deliberately NOT about billing at all — it is about the two
lines of Python that the seam's two `except` blocks depend on, executed against
the connection billing uses. A test that needed a whole bill run to say this
would be a test nobody runs.
"""

from __future__ import annotations

import pytest
from django.db import connection, transaction
from django.db.utils import DatabaseError, ProgrammingError

pytestmark = pytest.mark.django_db(transaction=False)

POSTGRES_ONLY = pytest.mark.skipif(
    connection.vendor != "postgresql",
    reason=(
        "law 14 has no failure mode on SQLite — an aborted transaction does not "
        "exist there, which is exactly why the unguarded code passes green"
    ),
)


def _fail_a_statement() -> None:
    """One statement PostgreSQL refuses. Any refusal aborts the transaction."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM a_table_that_does_not_exist")


def _a_statement_that_should_work() -> int:
    with connection.cursor() as cursor:
        cursor.execute("SELECT 42")
        return cursor.fetchone()[0]


@POSTGRES_ONLY
def test_def_2444__catching_without_a_savepoint_poisons_everything_after_it():
    """The defect itself: `except … : continue` and the next statement dies.

    This is `metering_seam` as it stood before CR-052 — and it is what would
    have happened inside `issue_invoice`'s transaction to `invoice.save()`, the
    GL stamps, the posting handoff and the audit row.
    """
    with pytest.raises(DatabaseError) as poisoned:
        with transaction.atomic():
            try:
                _fail_a_statement()
            except (DatabaseError, ProgrammingError):
                pass  # "carry on" — the shape law 14 is about
            # In production this line is `invoice.save()`, then the GL stamps,
            # then the posting handoff, then the audit row. Every one of them
            # raises, and the transaction cannot be committed either, so the
            # BILL IS LOST — not issued-without-a-chart, LOST.
            _a_statement_that_should_work()
    assert "current transaction is aborted" in str(poisoned.value).lower() or (
        "you can't execute queries" in str(poisoned.value).lower()
    ), f"expected an aborted-transaction refusal, got: {poisoned.value}"


@POSTGRES_ONLY
def test_def_2444__a_savepoint_makes_the_catch_work_and_the_bill_survives():
    """The fix, and it is the ONLY fix: a nested `atomic()` is a SAVEPOINT.

    The rollback to the savepoint un-aborts the transaction, so the statement
    after the caught error runs normally — which in production is the bill
    being issued without its usage chart, instead of the bill being lost.
    """
    with transaction.atomic():
        try:
            with transaction.atomic():  # SAVEPOINT
                _fail_a_statement()
        except (DatabaseError, ProgrammingError):
            pass
        assert _a_statement_that_should_work() == 42
