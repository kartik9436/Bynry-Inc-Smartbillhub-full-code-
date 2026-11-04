"""CLAUDE.md law 14, made checkable: a failed statement poisons the whole
PostgreSQL transaction, and a SAVEPOINT is the only way to carry on.

⚠ **THIS FILE IS THE PROOF THAT `config/settings/pgtest.py` CAN SEE WHAT
`config/settings/test.py` CANNOT.** The law says a `try/except IntegrityError:
continue` is broken on PostgreSQL and passes the entire suite on SQLite. That is
a claim about two databases, so it needs a test that RUNS on both and answers
DIFFERENTLY — otherwise the settings module is a green run proving nothing,
which is law 7's "incapable of failing" shape.

Two lanes found this independently on 2026-08-29, in different modules, weeks
apart, neither aware of the other. One was skipping import rows; the other was
queueing a payment receipt. Same trap.

RUN IT BOTH WAYS — the second one is the point:

    pytest tests/test_law14_postgres_transaction_shape.py                          # SQLite: the naive case SKIPS
    pytest tests/test_law14_postgres_transaction_shape.py --ds=config.settings.pgtest   # PostgreSQL: it RUNS
"""

import pytest
from django.db import IntegrityError, connection, transaction

pytestmark = pytest.mark.django_db(transaction=False)

on_postgres = pytest.mark.skipif(
    connection.vendor != "postgresql",
    reason=(
        "law 14 is a statement about PostgreSQL's aborted-transaction state, which "
        "SQLite does not have. Run with --ds=config.settings.pgtest to exercise it. "
        "A SKIP here is the law being true, not the test being unavailable."
    ),
)


def _a_refused_statement():
    """One statement PostgreSQL will refuse, with no table of our own needed."""
    with connection.cursor() as cur:
        cur.execute("SELECT 1/0")


@on_postgres
def test_law14__a_failed_statement_poisons_the_rest_of_the_transaction():
    """THE NAIVE PATTERN. Catch and carry on — and the NEXT query raises.

    This is the shape the law forbids. It is asserted rather than described so
    that a future PostgreSQL that behaved differently would go red here and not
    silently in a money path.
    """
    with pytest.raises(Exception):
        _a_refused_statement()

    # The transaction is now aborted. Any further query raises, whatever it is.
    with pytest.raises(Exception) as caught:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
    text = f"{type(caught.value).__name__}: {caught.value}".lower()
    assert "transaction" in text or "aborted" in text, (
        "expected the aborted-transaction refusal law 14 names "
        f"(InFailedSqlTransaction / TransactionManagementError), got: {text}"
    )


@on_postgres
def test_law14__a_savepoint_is_what_makes_carrying_on_work():
    """THE ONLY FIX. A nested `transaction.atomic()` is a SAVEPOINT, so the
    refusal is rolled back to it and the outer transaction survives.

    The law's own words: *"A SAVEPOINT — a nested `transaction.atomic()` — is
    not the tidy option, it is the ONLY option."*
    """
    try:
        with transaction.atomic():
            _a_refused_statement()
    except Exception:
        pass  # rolled back to the savepoint, not to the whole transaction

    with connection.cursor() as cur:
        cur.execute("SELECT 1")
        assert cur.fetchone()[0] == 1, (
            "the outer transaction should have survived the savepoint rollback"
        )


def test_law14__the_settings_module_refuses_to_run_green_on_sqlite():
    """`pgtest.py` FAILS CLOSED, and this is the assertion that says so.

    A settings module that silently left SQLite in place would report a green
    run over the exact class of bug it exists to catch. It raises instead, and
    the message names the law.
    """
    import config.settings.pgtest as pgtest

    assert "law 14" in pgtest.__doc__.lower()
    engine = pgtest.DATABASES["default"]["ENGINE"]
    assert engine == "django.db.backends.postgresql", (
        f"pgtest must resolve PostgreSQL, got {engine!r}"
    )
    assert "TEST" in pgtest.DATABASES["default"], (
        "pgtest must carry base.py's per-checkout TEST name — re-deriving one "
        "here would opt out of DEF-054's mitigation (a worktree shares the database)"
    )
