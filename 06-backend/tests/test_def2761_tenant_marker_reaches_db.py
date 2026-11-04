# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-2761 (2026-08-31) — `tests/test_us_ten_helpers.sqlite_guc` is an
#           AUTOUSE fixture that replaced `core.tenancy.connection` with a
#           recording fake on EVERY vendor. Through the star-import chain
#           test_us_ten_helpers -> test_us_met_helpers ->
#           {test_us_met_reads_helpers, test_us_rat_helpers} it reaches 447
#           collected test modules / 6,575 cases, in all of which
#           `set_config('app.tenant_id', …)` went to a Python list and never
#           reached PostgreSQL. A green Postgres run of those modules was never
#           evidence of tenant scoping, and nothing anywhere said so.
# Rules:    CLAUDE.md hard rule 1 (never touch a tenant table without
#           app.tenant_id set; RLS FORCE is on) · hard-won law 7 (prove a guard
#           RED before trusting it green) · hard-won law 1 (a comment claiming a
#           guarantee is not the guarantee) · B2 §3 RLS template · B3/BE-01.
# Contract: core/tenancy.py — the SHIPPING kernel that SETs the GUC.
# ───────────────────────────────────────────────────────
"""Does the tenant marker actually reach the database in the ORDINARY tier?

WHY THIS FILE EXISTS, AND WHY IT IS NOT PART OF THE G5 ISOLATION SUITE
---------------------------------------------------------------------
G5 already proves that PostgreSQL refuses a cross-tenant row. It has always
been honest, because `isolation_helpers.live_tenant_context` deliberately swaps
the REAL connection back before it asserts anything — its docstring says so in
as many words: *"On Postgres that recorder would swallow the very statement
this suite exists to verify."*

What nothing proved is the sentence one level down: **that the other 447
modules — the ordinary tier, the overwhelming majority of this suite — are
running against the real kernel at all.** They were not. G5 could be perfectly
green while every other module on the same database silently opted out of
tenant scoping, and for as long as the app role was `SUPERUSER` there was no
observable difference between the two, because RLS is bypassed and no policy is
ever consulted.

So this file asserts the PRECONDITION of every other file's tenant claims,
which is why it lives in the ordinary tier and star-imports the shared helpers
exactly the way its 447 neighbours do: **it is subject to the same autouse
fixture they are.** If someone re-widens `sqlite_guc`, this file is the thing
that goes red, in the same tier where the damage would be.

PROVED RED BEFORE IT WAS TRUSTED GREEN (hard-won law 7)
-------------------------------------------------------
Against real PostgreSQL 16.13, under `smartbillhub` at `rolsuper=f
rolbypassrls=f`, with the un-narrowed fixture in place:

    core.tenancy.connection is  : FakeGucConnection
    ContextVar mirror says      : 11111111-1111-1111-1111-111111111111
    current_setting says        : '00000000-0000-0000-0000-000000000000'

    AssertionError: app.tenant_id never reached the database

and with the fixture narrowed to `connection.vendor != 'postgresql'`:

    core.tenancy.connection is  : ConnectionProxy
    current_setting says        : '11111111-1111-1111-1111-111111111111'

(The nil UUID is the sentinel `apps/tenancy/migrations/0004_…` leaves on the
session — castable under the DEF-639 policy, and matching no row, i.e. the
deny-everything value. It is what an unset marker looks like on this database,
which is precisely why the failure was silent rather than loud.)

VENDOR
------
On sqlite the recorder is still necessary and still installed — sqlite has no
`set_config()`. `test_sqlite_still_gets_the_recorder` asserts that, so a future
lane cannot "fix" this defect by deleting the fixture and breaking the default
suite instead.
"""

import uuid

import pytest
from django.db import connection

from core import tenancy as core_tenancy
from tests.test_us_ten_helpers import *  # noqa: F401,F403 — the autouse sqlite_guc, as the 447 get it

pytestmark = pytest.mark.django_db

requires_postgres = pytest.mark.skipif(
    connection.vendor != "postgresql",
    reason=(
        "app.tenant_id is a PostgreSQL GUC and RLS does not exist on sqlite — "
        "run under DJANGO_SETTINGS_MODULE=config.settings.local against Postgres"
    ),
)

NIL_SENTINEL = "00000000-0000-0000-0000-000000000000"


def _guc() -> str:
    """Whatever `app.tenant_id` the session carries, read on the REAL connection."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('app.tenant_id', true)")
        return cursor.fetchone()[0] or ""


@requires_postgres
def test_the_shipping_kernel_is_not_standing_behind_a_fake():
    """`core.tenancy.connection` must BE the real connection on PostgreSQL.

    The failure this catches is not a wrong value — it is a wrong OBJECT, and
    it is invisible to every assertion written in terms of values, because the
    Python-side ContextVar mirror keeps answering correctly while the database
    hears nothing.
    """
    from django.db import connection as real_connection

    assert core_tenancy.connection is real_connection, (
        "core.tenancy.connection is "
        f"{type(core_tenancy.connection).__name__}, not the real connection — a "
        "test fixture is standing in front of the kernel that sets app.tenant_id, "
        "so nothing in this tier is exercising tenant scoping (DEF-2761)"
    )


@requires_postgres
def test_set_current_tenant_reaches_the_database():
    """The marker RLS reads must be the one the kernel was asked to write."""
    tenant_id = uuid.uuid4()
    core_tenancy.set_current_tenant(tenant_id)
    assert _guc() == str(tenant_id), (
        f"app.tenant_id reads {_guc()!r} on the very next statement — same "
        f"connection, same transaction — after the kernel was asked for "
        f"{tenant_id}. The Python mirror says {core_tenancy.current_tenant_id()}, "
        "so app-layer filters would still pass while the DATABASE has no idea "
        "which tenant this session is (DEF-2761)"
    )


@requires_postgres
def test_clearing_returns_the_session_to_deny_everything():
    """Cleared context must be NO access, never someone else's access."""
    core_tenancy.set_current_tenant(uuid.uuid4())
    core_tenancy.clear_current_tenant()
    assert _guc() in ("", NIL_SENTINEL), (
        f"app.tenant_id still reads {_guc()!r} after clear_current_tenant() — a "
        "later case on this connection would inherit a tenant it never asked for"
    )
    assert core_tenancy.current_tenant_id() is None


@requires_postgres
def test_the_fixture_leaves_no_tenant_adopted_by_a_neighbour():
    """Deny-by-default at the START of a case, not merely at the end of one.

    Django reuses one connection across a run. This case adopts no tenant at
    all; if it can see a marker, some earlier case's context leaked into it and
    every "scoped" assertion in this tier could be passing on a neighbour's
    session rather than its own.
    """
    assert _guc() in ("", NIL_SENTINEL), (
        f"this case adopted no tenant and app.tenant_id already reads {_guc()!r} "
        "— tenant context is leaking between tests (CLAUDE.md hard rule 1)"
    )


@requires_postgres
def test_this_proof_is_not_vacuous():
    """FAIL, never skip, if the connected role could bypass RLS.

    Copied in shape from `isolation_helpers.assert_is_a_real_proof`, and here
    for the same reason: a role that bypasses row-level security makes every
    tenant assertion in this suite pass without the policies existing, and
    DEF-2761 is exactly what that concealed for as long as it was true.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"
        )
        row = cursor.fetchone()
    assert row is not None, "the connected role is not in pg_roles"
    rolsuper, rolbypassrls = bool(row[0]), bool(row[1])
    assert not rolsuper, (
        "the app role is a SUPERUSER — it bypasses row-level security "
        "unconditionally, FORCE included, so tenant scoping is unproven here "
        "however green this run looks (DEF-2717/DEF-2760)"
    )
    assert not rolbypassrls, "the app role carries BYPASSRLS — tenant scoping is unproven here"


def test_sqlite_still_gets_the_recorder():
    """The narrowing must not break the default suite, which IS sqlite.

    sqlite has no `set_config()`; without the recorder every `tenant_ctx` in
    the 447 modules dies on `sqlite3.OperationalError: no such function:
    set_config`. So the fix for DEF-2761 is a NARROWING, never a deletion, and
    this case is what says so to whoever reads the fixture next.
    """
    if connection.vendor == "postgresql":
        pytest.skip("this case states the sqlite half of the contract")
    assert type(core_tenancy.connection).__name__ == "FakeGucConnection", (
        "the sqlite tier lost its set_config recorder — tenant_ctx cannot work "
        "on sqlite without it"
    )
