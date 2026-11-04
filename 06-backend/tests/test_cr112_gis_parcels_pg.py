# ── Trace ──────────────────────────────────────────────
# Story:    CR-112 — the parcel reconciliation run's WRITE half.
# Rules:    CLAUDE.md hard-won law 14 (a failed statement poisons the whole
#           PostgreSQL transaction; the test suite runs on SQLite, which does
#           not, so the naive fix passes everything and loses production data)
#           · BR-INT-074 (preview writes nothing)
# Tests:    this file
# Impacts:  apps/integrations/gis_parcels._persist (the SAVEPOINT this proves)
# ───────────────────────────────────────────────────────
"""**DOES ONE REFUSED ROW LOSE THE OTHER THIRTY-NINE THOUSAND?**

⚠ **THIS FILE EXISTS BECAUSE THE DEFAULT SUITE CANNOT ASK THE QUESTION**
(CLAUDE.md hard-won law 14). `config/settings/test.py` hardcodes **in-memory
SQLite**, and SQLite has **no aborted-transaction state at all**. So a
`_persist` written the obvious way —

    try:
        write(actor, row_id, patch)
    except DatabaseError:
        continue

— passes the entire suite, green, on every machine, and on PostgreSQL loses the
whole run: once any statement errors inside a transaction, every later query
raises `InFailedSqlTransaction` and the work is discarded at COMMIT **having
reported success**. The nested `transaction.atomic()` in `_persist` is a
SAVEPOINT, and it is the only thing that makes that `continue` mean what it
reads as.

**A reconciliation run is exactly the shape that gets bitten**: it walks up to
40,000 rows and expects some of them to be refused — a premises deleted between
the read and the write, an owner that went away, a value another lane changed.
One of those must cost one row and not the run.

⚠⚠ **THIS FILE HAS NOT BEEN RUN GREEN, AND SAYING SO IS THE POINT (hard-won
law 1: a comment claiming a guarantee is not the guarantee).** An earlier draft
of this docstring claimed the savepoint had been proved red against real
PostgreSQL. **It had not been, and the claim was removed rather than left to be
believed.**

**What actually happened, on 2026-09-17.** PostgreSQL is running in this
container and accepting connections, and every attempt to build a test database
against it failed during migration with

    django.db.utils.IntegrityError: duplicate key value violates unique
    constraint "pg_type_typname_nsp_index"
    DETAIL: Key (typname, typnamespace)=(account_budget_status, 2200) already
    exists.

— under `--reuse-db` and under `--create-db` alike. **It is not this change.**
The decisive check is the one hard-won law 7 habit 1 asks for: an existing,
completely untouched PostgreSQL test file — `tests/test_cr066_gl_defaults_live_pg.py`,
last modified 2026-09-14 in `68e0e4e3`, not a file this lane has opened — fails
**identically**, 9 errors, same constraint, same table. `pg_database` shows five
`test_sbh_*` databases from sibling lanes, so the shared server is mid-use by
other work.

**So the status of the savepoint is: WRITTEN, REASONED, AND UNPROVEN ON THE
DATABASE THAT MATTERS.** The default SQLite suite exercises that `_persist`
takes a savepoint (`tests/test_cr112_gis_parcels.py` runs the apply path under
`django_db`), which is worth something and is **not** the thing law 14 is about.
The four cases below are the thing law 14 is about, and somebody with a working
PostgreSQL must run them:

    DJANGO_SETTINGS_MODULE=config.settings.local \
    DATABASE_URL="postgres://…" JOBS_EAGER=false \
    pytest tests/test_cr112_gis_parcels_pg.py --create-db

**And the red proof is still owed.** Remove the nested `transaction.atomic()`
from `gis_parcels._persist` and `test_one_refused_row_does_not_lose_the_others`
must fail with `TransactionManagementError` while the SQLite suite stays green.
Until somebody has watched that happen, the savepoint is an argument rather than
a measurement.
"""

from __future__ import annotations

import pytest
from django.db import DatabaseError, connection, transaction

from apps.integrations import gis_esri_fixtures as fx
from apps.integrations import gis_parcels
from apps.integrations.gis_parcels import APPLY
from core import errors
from tests.isolation_helpers import requires_postgres

#: ⚠ **`requires_postgres` IS THE REPO'S OWN HELPER AND A HAND-ROLLED `skipif`
#: WAS THE WRONG REFLEX** — the same lesson as `push_paths.sh`: before writing
#: a helper, look for the one this repo already owns. It is a skipif keyed on
#: `connection.vendor`, so the default SQLite run skips these with a vendor
#: reason and a PostgreSQL run executes them. **A green SQLite run here would be
#: measuring a database that cannot express the failure** (law 14).
pytestmark = [pytest.mark.django_db, requires_postgres]

CONNECTION = {"layer_url": fx.FIXTURE_LAYER}


def our_register():
    return {
        "premises": [
            {"id": "P1", "premise_no": "P-00001", "label": "P-00001",
             "address_line": "100 N Maple St", "city": "Riverbend", "state": "MI",
             "postal_code": "48104", "lat": None, "lng": None,
             "gis_parcel_id": None, "gis_parcel_id_was": None, "gis_status": None},
            {"id": "P2", "premise_no": "P-00002", "label": "P-00002",
             "address_line": "220 Oak Ave", "city": "Riverbend", "state": "MI",
             "postal_code": "48104", "lat": None, "lng": None,
             "gis_parcel_id": None, "gis_parcel_id_was": None, "gis_status": None},
            {"id": "P3", "premise_no": "P-00003", "label": "P-00003",
             "address_line": "44 W Birch Ln", "city": "Riverbend", "state": "MI",
             "postal_code": "07001", "lat": None, "lng": None,
             "gis_parcel_id": None, "gis_parcel_id_was": None, "gis_status": None},
        ],
        "units_by_premises": {},
    }


class RefusesTheSecondRow:
    """A writer that fails on one row with a REAL database error.

    ⚠ **IT MUST BE A REAL STATEMENT AGAINST THE REAL CONNECTION.** A bare
    `raise DatabaseError` would leave the transaction perfectly healthy and this
    test would pass without a savepoint — hard-won law 7's *what would make this
    pass wrongly*. So it executes deliberately invalid SQL, which is what
    actually puts PostgreSQL into the aborted state.

    ⚠⚠ **AND THE GOOD ROWS MUST TOUCH THE DATABASE TOO, WHICH THIS FIXTURE DID
    NOT UNTIL 2026-09-17 (`DEF-INT-5669`).** It recorded P1 and P3 by appending
    to a Python list and issuing no statement, so `written == ["P1", "P3"]` was
    true **whether or not `_persist` took a savepoint**: nothing the assertion
    depends on ever asks the poisoned connection a question. Measured by
    sabotage on that date — with the savepoint removed,
    `test_one_refused_row_does_not_lose_the_others` **passed**, and this file's
    own docstring said it *"must fail with TransactionManagementError"*. That is
    hard-won law 7's *structurally incapable of failing*, sitting inside the one
    file written to prove law 14. The `SELECT 1` below is the whole fix: after
    P2 poisons the transaction, an unsavepointed P3 now raises
    `InFailedSqlTransaction` and the test says so.
    """

    def __init__(self):
        self.written: list[str] = []

    def __call__(self, actor, row_id, patch):
        if row_id == "P2":
            with connection.cursor() as cursor:
                cursor.execute("SELECT this_column_does_not_exist FROM premises")
        # A REAL statement on the good rows — see the warning above. A writer
        # that only appends to a list cannot tell a healthy connection from an
        # aborted one, which is the exact question this file exists to ask.
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        self.written.append(row_id)


def test_one_refused_row_does_not_lose_the_others():
    """⚠ **THE WHOLE OF LAW 14, IN ONE ASSERTION.**

    Without the SAVEPOINT in `_persist`, P3's write raises
    `TransactionManagementError` and `written` is `["P1"]`.
    """
    writer = RefusesTheSecondRow()
    result = gis_parcels.run(
        "actor",
        connection_config=CONNECTION,
        ours=our_register(),
        transport=fx.recorded_transport,
        mode=APPLY,
        update_premises=writer,
        update_unit=lambda *a, **k: None,
        hand_off=lambda key, batch: True,
    )
    assert writer.written == ["P1", "P3"], (
        "P3 was written AFTER the refused row — that is the savepoint working. "
        "Without it PostgreSQL refuses every later statement in the transaction."
    )
    assert result["applied"]["rows_refused"] == 1


def test_the_transaction_is_still_usable_after_the_run():
    """The run must not hand back a poisoned connection."""
    writer = RefusesTheSecondRow()
    gis_parcels.run(
        "actor", connection_config=CONNECTION, ours=our_register(),
        transport=fx.recorded_transport, mode=APPLY,
        update_premises=writer, update_unit=lambda *a, **k: None,
        hand_off=lambda key, batch: True,
    )
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            assert cursor.fetchone() == (1,)


def test_a_refused_row_is_counted_and_not_silently_dropped():
    """A run that refused rows and one that had none must not read the same."""
    writer = RefusesTheSecondRow()
    result = gis_parcels.run(
        "actor", connection_config=CONNECTION, ours=our_register(),
        transport=fx.recorded_transport, mode=APPLY,
        update_premises=writer, update_unit=lambda *a, **k: None,
        hand_off=lambda key, batch: True,
    )
    assert result["applied"]["rows_refused"] == 1
    assert result["applied"]["keys_taken"] >= 2


def test_a_bare_database_error_would_not_have_proved_anything():
    """⚠ Law 7, habit 2 — what would make the test above pass wrongly.

    A writer that merely `raise DatabaseError(...)` leaves the transaction
    healthy, so the savepoint is not exercised at all and the test passes over
    an implementation that has none. This records the distinction so nobody
    "simplifies" the fixture above into a plain raise.
    """

    class RaisesWithoutTouchingTheDatabase:
        def __init__(self):
            self.written = []

        def __call__(self, actor, row_id, patch):
            if row_id == "P2":
                raise DatabaseError("nothing actually happened to the connection")
            self.written.append(row_id)

    writer = RaisesWithoutTouchingTheDatabase()
    gis_parcels.run(
        "actor", connection_config=CONNECTION, ours=our_register(),
        transport=fx.recorded_transport, mode=APPLY,
        update_premises=writer, update_unit=lambda *a, **k: None,
        hand_off=lambda key, batch: True,
    )
    assert writer.written == ["P1", "P3"], (
        "this passes with OR without the savepoint — which is exactly why the "
        "fixture above executes real invalid SQL instead"
    )


# ═══════════════════════════════════════════════════════════════════════════
# 2026-09-17 · `DEF-INT-5629` — THE SAVEPOINT CAUGHT ONE EXCEPTION AND THE RUN
# RAISES FOUR
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **THE FIRST HALF OF THIS DEFECT WAS FIXED ON 2026-09-17 AND THE SECOND HALF
# WAS NOT.** `2836c242a` put the four run-written columns into metering's known
# sets, so the patches `_persist` builds are now accepted. That closed the
# *every* row fails case and left the *one* row fails case exactly as it was:
# `_persist` caught `DatabaseError` alone, and the writer it calls —
# `metering.services.update_premises` — raises a PRODUCT refusal for everything
# a run legitimately meets in 40,000 rows.
#
# **Four things a row can do to a run, and only one of them was a
# `DatabaseError`:**
#
#   * a value metering will not take → `core.errors.ValidationError`;
#   * the premises was deleted between the read and the write →
#     `core.errors.NotFoundError`, via `deny_as_not_found`, which is the case
#     this file's own docstring already names and could not survive;
#   * a business rule stopped the row → `core.errors.BizError`;
#   * a constraint → `DatabaseError`, the one that was caught.
#
# Every one of the first three escaped `_persist` entirely and killed the run on
# the row it met — **`rows_refused` could never reach 1 by any of them.**
#
# ⚠ **AND THE FIX IS NOT `except Exception`.** A role refusal is not a property
# of a row: if the actor may not write premises, EVERY row fails, and swallowing
# that would report *40,000 rows refused* for a run that was never allowed to
# start. `test_an_authorisation_refusal_stops_the_run` is what holds that line.


def test_a_product_refusal_costs_one_row_and_not_the_whole_run():
    """⚠ **`DEF-INT-5629`, THE HALF THAT WAS STILL OPEN.**

    Metering refuses a value on P2. Before the fix `run()` RAISED
    `ValidationError` out of `_persist` and P3 was never attempted, so a single
    bad row cost the other 39,999.
    """

    class RefusesTheSecondRowAsAProduct:
        def __init__(self):
            self.written: list[str] = []

        def __call__(self, actor, row_id, patch):
            if row_id == "P2":
                raise errors.ValidationError(
                    errors.VAL_FORMAT, message_key="metering.unknown_field"
                )
            self.written.append(row_id)

    writer = RefusesTheSecondRowAsAProduct()
    result = gis_parcels.run(
        "actor", connection_config=CONNECTION, ours=our_register(),
        transport=fx.recorded_transport, mode=APPLY,
        update_premises=writer, update_unit=lambda *a, **k: None,
        hand_off=lambda key, batch: True,
    )
    assert writer.written == ["P1", "P3"]
    assert result["applied"]["rows_refused"] == 1


def test_a_row_that_vanished_between_the_read_and_the_write_costs_one_row():
    """The case this file's docstring named and the code could not survive.

    `metering.services._premises_row` raises `deny_as_not_found()` — a
    `NotFoundError`, which is not an `ApiError` and not a `DatabaseError`. A
    reconciliation reads 40,000 rows and writes them afterwards; a premises
    deleted in between is ORDINARY, and it used to end the run.
    """

    class TheRowWentAway:
        def __init__(self):
            self.written: list[str] = []

        def __call__(self, actor, row_id, patch):
            if row_id == "P2":
                raise errors.deny_as_not_found("BR-TEN-003")
            self.written.append(row_id)

    writer = TheRowWentAway()
    result = gis_parcels.run(
        "actor", connection_config=CONNECTION, ours=our_register(),
        transport=fx.recorded_transport, mode=APPLY,
        update_premises=writer, update_unit=lambda *a, **k: None,
        hand_off=lambda key, batch: True,
    )
    assert writer.written == ["P1", "P3"]
    assert result["applied"]["rows_refused"] == 1


def test_a_refusal_raised_after_a_failed_statement_still_leaves_the_others():
    """⚠ **THE ONE CASE THAT IS ABOUT POSTGRESQL AND NOT ABOUT PYTHON.**

    The two cases above fail identically on SQLite, because nothing touched the
    connection. This one is law 14 itself: a service that catches a database
    error and re-raises it as a PRODUCT refusal — which is what a validator
    translating a constraint into a sentence a clerk can read does — leaves the
    transaction ABORTED and hands back an exception that is not a
    `DatabaseError`. Catching it outside the savepoint would count the row and
    then lose every row after it to `InFailedSqlTransaction`.
    """

    class TranslatesAConstraintIntoASentence:
        def __init__(self):
            self.written: list[str] = []

        def __call__(self, actor, row_id, patch):
            if row_id == "P2":
                try:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT this_column_does_not_exist FROM premises")
                except DatabaseError as exc:  # noqa: F841
                    raise errors.ValidationError(
                        errors.VAL_FORMAT, message_key="metering.unknown_field"
                    ) from exc
            self.written.append(row_id)

    writer = TranslatesAConstraintIntoASentence()
    result = gis_parcels.run(
        "actor", connection_config=CONNECTION, ours=our_register(),
        transport=fx.recorded_transport, mode=APPLY,
        update_premises=writer, update_unit=lambda *a, **k: None,
        hand_off=lambda key, batch: True,
    )
    assert writer.written == ["P1", "P3"], (
        "the savepoint is what un-poisons the transaction; the catch alone "
        "would have counted P2 and then lost P3 to InFailedSqlTransaction"
    )
    assert result["applied"]["rows_refused"] == 1
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            assert cursor.fetchone() == (1,)


def test_an_authorisation_refusal_stops_the_run_rather_than_counting_40000():
    """⚠ **LAW 7, HABIT 2 — WHAT WOULD MAKE THE FIX PASS WRONGLY.**

    `except Exception: continue` would pass every test above and turn *you may
    not write premises* into *40,000 rows refused* — a run that reported work it
    never had permission to do. A role refusal is a property of the ACTOR, not
    of a row, so it must end the run on the first one.
    """

    class TheActorMayNot:
        def __init__(self):
            self.written: list[str] = []

        def __call__(self, actor, row_id, patch):
            raise errors.AuthError(errors.AUTH_PERMISSION_DENIED)

    with pytest.raises(errors.AuthError):
        gis_parcels.run(
            "actor", connection_config=CONNECTION, ours=our_register(),
            transport=fx.recorded_transport, mode=APPLY,
            update_premises=TheActorMayNot(), update_unit=lambda *a, **k: None,
            hand_off=lambda key, batch: True,
        )


def test_a_refused_row_is_named_and_not_only_counted():
    """A count of 37 over 40,000 rows tells nobody WHICH 37.

    `BR-RBS-035`'s shape — a row for what it acted on and a COUNT for the rest —
    borrowed here because the number alone is a check that does not check: a
    clerk cannot act on it and nobody can tell one refused row from another.
    The label is the premises NUMBER, never the database id (B14 rule 31).
    """

    class RefusesTheSecondRowAsAProduct:
        def __call__(self, actor, row_id, patch):
            if row_id == "P2":
                raise errors.ValidationError(
                    errors.VAL_FORMAT, message_key="metering.unknown_field"
                )

    result = gis_parcels.run(
        "actor", connection_config=CONNECTION, ours=our_register(),
        transport=fx.recorded_transport, mode=APPLY,
        update_premises=RefusesTheSecondRowAsAProduct(),
        update_unit=lambda *a, **k: None,
        hand_off=lambda key, batch: True,
    )
    refusals = result["refusals"]
    assert [one["label"] for one in refusals] == ["P-00002"]
    assert refusals[0]["level"] == "premises"
    assert refusals[0]["reason"]
    assert "P2" not in str(refusals), "a database id must not be the visible value"
