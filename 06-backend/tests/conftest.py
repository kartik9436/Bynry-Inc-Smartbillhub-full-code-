# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-2395 (2026-09-01) — CLAUDE.md law 14 REQUIRES transaction-
#           sensitive code to be proved on real PostgreSQL, and three lanes
#           found in one day that they could not get there. Two separate
#           things blocked it. DEF-566's write-nothing identity stub was one
#           (fixed in tests/test_us_ten_helpers.py); THIS FILE is the other.
#           DEF-2874 (2026-09-01) — the row filed for the half below.
# Rules:    CLAUDE.md hard-won law 14 (a failed statement poisons the whole
#           PostgreSQL transaction; the default suite is in-memory SQLite,
#           which has no aborted-transaction state) · law 7 (prove a guard RED
#           first) · law 3 (defaults fail closed)
# ───────────────────────────────────────────────────────
"""Suite-wide plumbing that only matters on PostgreSQL.

WHY THIS FILE EXISTS AT ALL
===========================
Law 14 says transaction-sensitive code MUST be proved on real PostgreSQL. A
proof of that kind needs `@pytest.mark.django_db(transaction=True)`: the plain
`django_db` marker wraps the test in one atomic block that is rolled back, so
the COMMIT semantics an aborted transaction is about are never reached.

**And `transaction=True` did not work on PostgreSQL at all.** Measured
2026-09-01 on PostgreSQL 16.13, with a test that writes NOTHING:

    @pytest.mark.django_db(transaction=True)
    def test_probe__empty_transactional_test_can_tear_down():
        assert True

    E  psycopg.errors.FeatureNotSupported: cannot truncate a table referenced
       in a foreign key constraint
    E  DETAIL:  Table "transfers" references "customers".
    E  HINT:  Truncate table "transfers" at the same time, or use
       TRUNCATE ... CASCADE.
    E  CommandError: Database test_sbh_… couldn't be flushed.

THE MECHANISM, AND IT IS THE SCHEMA RATHER THAN ANY TEST'S DATA
---------------------------------------------------------------
`transaction=True` tears down by FLUSHING, and Django's flush emits one
`TRUNCATE` naming only the tables of MANAGED models. This repo has 25
`managed = False` models whose tables really exist and really carry foreign
keys into managed ones — `transfers` → `customers` and
`meter_read_asset_monthly_usage` → `services` are two that were hit within an
hour of each other. PostgreSQL refuses to truncate a table an un-named table
references, so the flush fails.

**It is invisible on the default suite by construction.** `config/settings/
test.py` hardcodes in-memory SQLite (law 14 names that file), and SQLite's
flush is `DELETE FROM` — no such restriction — so every one of these tests is
green on every machine and fails only on the database law 14 sends you to.

⚠ **AND THE COST IS NOT THE ONE ERROR — IT IS THAT THE FAILED FLUSH LEAVES THE
TEST DATABASE DIRTY.** Teardown aborts part-done, so the next test in the same
`--reuse-db` database inherits the previous one's rows. On 2026-09-01 that
turned into five unrelated red tests in
`tests/test_us_cus_003_account_race.py`, every one of them refusing with
`BIZ-STATE (signup.subdomain_taken)` — a leftover tenant, reported as a
product refusal, in a file that had nothing to do with the run that left it
there. That is precisely DEF-2395's *"three lanes each losing an hour"*: the
visible failure names the wrong thing.

WHAT THE FIX BELOW DOES
-----------------------
Exactly what PostgreSQL's own HINT asks for, and exactly what Django already
does when it is told it may: `TRUNCATE … CASCADE`. Django's
`DatabaseOperations.sql_flush` takes `allow_cascade`, and `TransactionTestCase`
passes False unless `available_apps` is set — which pytest-django's marker does
not expose. So this forces it on for the suite.

It is SAFE rather than merely convenient: the flush already names every managed
table, so CASCADE reaches only the unmanaged tables hanging off them, which are
tables the flush was trying and failing to clear anyway. Nothing outside the
test database can be touched — this patch is installed by a pytest fixture and
exists only inside a test session.

⚠ **IT IS SCOPED TO POSTGRESQL AND MUST STAY THAT WAY.** On SQLite the flush
already works, and law 3 says the unsafe option is the one you type: a patch
that fired on every vendor would be changing behaviour on the path that has no
problem, for no reason.

WHAT THIS DOES **NOT** FIX, SAID RATHER THAN LEFT TO BE DISCOVERED
------------------------------------------------------------------
A flush empties migration-seeded PLATFORM reference data too — `roles`,
`permissions`, `subscription_plans` (the catalog
`tenancy/migrations/0005_seed_subscription_plans.py` writes, whose absence made
every signup fail with `signup.plan_unknown` once before, in 2026-08-10's
deploy-blocker lane). Django's answer to that is `serialized_rollback`, which
pytest-django spells `@pytest.mark.django_db(transaction=True,
serialized_rollback=True)`; it is the CALLER's decision because it costs a
serialize/deserialize per test. This file does not make it for them. **If a
transactional test of yours dies on missing reference data, that is the flag
you want, and it is not a bug in this file.**
"""

from __future__ import annotations

import pytest


@pytest.fixture(scope="session", autouse=True)
def _postgres_flush_allows_cascade():
    """Let a `transaction=True` teardown flush actually complete on PostgreSQL.

    Session-scoped and autouse: `sql_flush` is called only by a transactional
    test's teardown, so installing it once before the first test and taking it
    off at the end is the whole lifetime it needs.

    ⚠ **IT DEPENDS ON NOTHING, AND `django_db_setup` IS THE DEPENDENCY IT MUST
    NOT TAKE.** That is the obvious way to be sure Django is configured, and it
    would make an autouse SESSION fixture pull the whole database setup into
    **every** run — so `pytest tests/test_something_with_no_database.py` would
    start paying for a full migrate. It is not needed: pytest-django calls
    `django.setup()` in `pytest_configure`, long before any fixture, and
    `connection.vendor` is read off the configured `ENGINE` without opening a
    connection.

    ⚠ NOT TIDINESS — see the module docstring. Without it, EVERY
    `transaction=True` test on PostgreSQL errors at teardown and leaves the
    test database dirty for whatever runs next. Do not "simplify" it away; the
    default suite is SQLite and cannot show you what it is for.
    """
    from django.db import connection

    if connection.vendor != "postgresql":
        # SQLite flushes with DELETE FROM and has no such restriction. Law 3:
        # do not change the path that works.
        yield
        return

    from django.db.backends.postgresql.operations import DatabaseOperations

    original = DatabaseOperations.sql_flush

    def sql_flush(self, style, tables, *, reset_sequences=False, allow_cascade=False):
        # `allow_cascade=True`, always. The caller is Django's own
        # TransactionTestCase teardown, which passes False because
        # pytest-django never sets `available_apps`.
        return original(self, style, tables, reset_sequences=reset_sequences, allow_cascade=True)

    DatabaseOperations.sql_flush = sql_flush
    try:
        yield
    finally:
        DatabaseOperations.sql_flush = original


# ── Exports on an S3 EMULATOR, through the real client (PO 2026-10-02) ──────
#
# The PO ruled that export files live in S3 in EVERY environment, through one
# code path, with no filesystem stand-in (decision log, *"EXPORT FILES MOVE FROM
# THE SHARED DISK TO S3 — THE DESIGN IS APPROVED"*: *"keep the same mechanism
# everywhere"*). So the suite does not swap the export store for local disk; it
# swaps AWS for `moto`, an in-process S3 emulator, and the boto3 client, the
# requests and the responses are the real ones. No test needs AWS credentials.
#
# ⚠ LAZY ON PURPOSE. The emulator starts the first time a test actually asks
# the export store for a client, so the thousands of tests that never export
# pay nothing for it. It is stopped after the test that started it, which also
# empties the bucket — no export survives from one test into the next.
@pytest.fixture(autouse=True)
def _export_store_on_s3_emulator():
    from apps.tenancy import export_storage

    state: dict = {}

    def factory():
        if "client" not in state:
            import boto3
            from django.conf import settings
            from moto import mock_aws

            mock = mock_aws()
            mock.start()
            state["mock"] = mock
            client = boto3.client("s3", region_name="us-east-1")
            client.create_bucket(Bucket=settings.DOCUMENT_STORAGE_BUCKET or "sbh-test-bucket")
            state["client"] = client
        return state["client"]

    # Under config.settings.local (the PostgreSQL runs law 14 requires) no
    # bucket is named; give the emulator one so those runs reach the same path.
    from django.conf import settings as django_settings
    from django.test import override_settings

    bucket_override = (
        None
        if getattr(django_settings, "DOCUMENT_STORAGE_BUCKET", "")
        else override_settings(DOCUMENT_STORAGE_BUCKET="sbh-test-bucket")
    )
    if bucket_override is not None:
        bucket_override.enable()
    export_storage.set_client_factory(factory)
    try:
        yield factory
    finally:
        export_storage.set_client_factory(None)
        if "mock" in state:
            state["mock"].stop()
        if bucket_override is not None:
            bucket_override.disable()


@pytest.fixture
def export_bucket(_export_store_on_s3_emulator):
    """The emulated bucket's client, started now — for a test that puts a
    non-export object beside the exports, or reads one back directly."""
    return _export_store_on_s3_emulator()
