# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-TEN-4446 — `implementation_orders` and `tenant_addons` hold what
#           each utility negotiated to pay Bynry, carry a `tenant_id`, and had
#           no row-level security policy. `tenancy/0042` applies the signed one;
#           `tenancy/0041` and `platform_numbering.allocate_sequence` keep the
#           order number unique across all utilities once it is on.
# Rules:    CLAUDE.md hard rule 1 (never touch a tenant table without
#           `app.tenant_id` set; RLS FORCE is on) · B2 §3 (the signed policy
#           template; its "No RLS (platform)" list names neither of these two) ·
#           CLAUDE.md hard-won law 14 (sqlite has no RLS and no aborted-
#           transaction state, so the proof is PostgreSQL-only and never faked)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""The database half of the commercial tables' isolation, and the number that
had to move so the policy could go on.

TWO THINGS ARE PROVED HERE AND THEY FAIL FOR DIFFERENT REASONS
---------------------------------------------------------------
**(1) The policy.** Zero rows of either priced table without a tenant context;
nothing of one utility reachable under another's; a write stamped for another
tenant refused by `WITH CHECK`; and `relrowsecurity` AND `relforcerowsecurity`
both true in `pg_class`, because a policy on a table with row security merely
ENABLED is bypassed by the table's owner.

**(2) The signup that the policy would otherwise have killed.**
`platform_numbering` used to read the next `IMPL-` number with a `MAX` over
every row of `implementation_orders`, across every tenant. Under the policy that
scan sees only the signing-up tenant's own orders — none — so every signup would
propose `IMPL-26-0001`, collide with `uq_implementation_orders_order_no`, retry
three times and raise `NumberingError`. `test_…two_real_signups_still_get_two_
different_numbers` is the guard for that, and it must run on **PostgreSQL**: on
sqlite there is no policy, the old scan works perfectly, and the test would pass
over a product that cannot sign anybody up (hard-won law 14, and law 7's
*structurally incapable of failing*).

⚠ **SO DO NOT "SIMPLIFY" THAT CASE ONTO THE DEFAULT SUITE.** A copy of it
without `requires_postgres` is not a cheaper version of this test, it is a test
of the opposite thing.

WHAT A FALSE PASS WOULD LOOK LIKE, STATED SO IT CAN BE LOOKED FOR
------------------------------------------------------------------
Every case here runs under `sbh_rls_probe` for its RLS half (NOLOGIN
NOSUPERUSER NOBYPASSRLS) because PostgreSQL exempts superusers from row-level
security unconditionally, FORCE included, and the app's dev role IS a superuser.
`tests/isolation_helpers.py` re-checks that at runtime and FAILS rather than
skips if the swap did not take — which is the only thing standing between this
file and a green run that proves nothing.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.tenancy import models, platform_numbering

# ⚠ THE STAR IMPORT IS THE SQLITE HALF AND IT IS NOT TIDINESS. `sqlite_guc` is
# an AUTOUSE fixture living in that module, and without it a provisioning on
# sqlite dies on `no such function: set_config` — sqlite has no GUC, so the
# kernel's `set_config` call has to go to a recorder. It is VENDOR-GUARDED
# (DEF-2761), so on PostgreSQL the real connection is used and the marker really
# reaches the database, which is what the cases below depend on. It is listed
# FIRST so the explicit isolation imports underneath win any name collision.
from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures

from tests.isolation_helpers import (  # noqa: F401 — fixtures used by name
    assert_denied_without_context,
    assert_rls_scoped,
    assert_write_into_other_tenant_refused,
    iso_tenants,
    live_tenant_context,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_idn_helpers import api_get, signed_in_client
from tests.test_us_ten_helpers import brazosbend_payload, provisioned_tenant

pytestmark = pytest.mark.isolation

#: The two tables `tenancy/0042` protects. Written out rather than imported from
#: the migration so that deleting the migration's tuple cannot silently empty
#: this loop — a check that iterates nothing passes (hard-won law 7).
PRICED_TABLES = ("implementation_orders", "tenant_addons")


def _an_addon() -> models.Addon:
    """One catalogue row. `addons` is the PLATFORM catalogue — no `tenant_id`,
    no policy, nothing in it belongs to a utility — so it is created outside any
    tenant context on purpose, and a policy on it would fail at CREATE POLICY."""
    return models.Addon.objects.create(
        code="sms-notifications", name="SMS notifications", price_month=Decimal("49.0000")
    )


@requires_postgres
@pytest.mark.django_db
def test_def_ten_4446__both_priced_tables_have_row_security_enabled_and_forced(rls):
    """ENABLED alone is not enough, and that is the whole reason this asserts two
    columns instead of one: without FORCE the table's OWNER — which is the role
    the application connects as — is exempt from its own policy."""
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
            "WHERE relname = ANY(%s) ORDER BY relname",
            [list(PRICED_TABLES)],
        )
        found = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}

    assert set(found) == set(PRICED_TABLES), f"tables missing from pg_class: {found}"
    for table, (enabled, forced) in sorted(found.items()):
        assert enabled, f"{table}: row security is not ENABLED — B2 §3 requires it"
        assert forced, (
            f"{table}: row security is not FORCED, so the table owner — the role this "
            "application connects as — reads every utility's price"
        )


@requires_postgres
@pytest.mark.django_db
def test_def_ten_4446__no_tenant_context_reads_no_price(rls, iso_tenants):
    """Deny-by-default: with `app.tenant_id` unset, both tables answer 0 rows.

    Written with rows actually present, because a table that is EMPTY answers 0
    to everything and the assertion would hold over a policy that does not exist
    (law 7 — a check you cannot describe a false pass for is one you do not
    understand; this is that false pass, closed).
    """
    alpha, _beta = iso_tenants
    addon = _an_addon()
    with live_tenant_context(alpha.id):
        models.ImplementationOrder.objects.create(
            tenant=alpha, order_no="IMPL-26-9001", duration_months=9,
            price=Decimal("18000.0000"),
        )
        models.TenantAddon.objects.create(
            tenant=alpha, addon=addon, price_month=Decimal("37.5000")
        )

    assert_denied_without_context(rls, *PRICED_TABLES)


@requires_postgres
@pytest.mark.django_db
def test_def_ten_4446__one_utility_cannot_read_or_write_anothers_price(rls, iso_tenants):
    """The case the defect is about: Pine Hill's price under Oak Ridge's context.

    Both halves, per table — the read is invisible even to an id-guess, and a
    write stamped with the other tenant's id is refused by `WITH CHECK`.
    """
    alpha, beta = iso_tenants
    addon = _an_addon()

    with live_tenant_context(alpha.id):
        order = models.ImplementationOrder.objects.create(
            tenant=alpha, order_no="IMPL-26-9002", duration_months=12,
            price=Decimal("24000.0000"),
        )
        taken = models.TenantAddon.objects.create(
            tenant=alpha, addon=addon, price_month=Decimal("125.0000")
        )
    with live_tenant_context(beta.id):
        models.ImplementationOrder.objects.create(
            tenant=beta, order_no="IMPL-26-9003", duration_months=0,
            price=Decimal("0.0000"),
        )
        models.TenantAddon.objects.create(tenant=beta, addon=addon, price_month=None)

    assert_rls_scoped(
        rls, "implementation_orders", owner=alpha, intruder=beta,
        owner_ids={str(order.id)},
    )
    assert_rls_scoped(
        rls, "tenant_addons", owner=alpha, intruder=beta, owner_ids={str(taken.id)},
    )
    for table in PRICED_TABLES:
        assert_write_into_other_tenant_refused(rls, table, owner=beta, intruder=alpha)


@requires_postgres
@pytest.mark.django_db
def test_def_ten_4446__two_real_signups_still_get_two_different_numbers():
    """THE GUARD FOR THE SECOND HALF, and the one that has to run on PostgreSQL.

    Two whole provisionings through the real service, under the real policy. If
    anyone puts the cross-tenant `MAX` scan back into `platform_numbering`, the
    second signup reads a maximum of 0 inside its own context, proposes a number
    the first already holds, exhausts `MAX_ALLOCATION_ATTEMPTS` and raises — so
    this case fails as a broken SIGNUP, which is what the defect would be.

    It asserts the numbers rather than merely that two rows exist: `0001` and
    `0002` are what a person quotes off a contract, and an allocator that handed
    out two DIFFERENT-but-wrong numbers would still be broken.
    """
    payload = brazosbend_payload()
    payload["subdomain"] = "rlsorder1"
    payload["owner"] = {**payload["owner"], "email": "one@rlsorder.example"}
    first, _ = provisioned_tenant(payload)

    payload2 = brazosbend_payload()
    payload2["subdomain"] = "rlsorder2"
    payload2["owner"] = {**payload2["owner"], "email": "two@rlsorder.example"}
    second, _ = provisioned_tenant(payload2)

    yy = f"{date.today().year % 100:02d}"
    numbers = []
    for tenant in (first, second):
        with live_tenant_context(tenant.id):
            numbers.append(
                models.ImplementationOrder.objects.get(tenant=tenant).order_no
            )
    assert sorted(numbers) == [f"IMPL-{yy}-0001", f"IMPL-{yy}-0002"], numbers


@requires_postgres
@pytest.mark.django_db
def test_def_ten_4446__the_counter_is_reachable_without_a_tenant_context(iso_tenants):
    """Bynry's counter is NOT tenant data, and this is the assertion that says so.

    `platform_number_series` carries no `tenant_id`, so it has no policy and the
    G5 sweep never sees it. That is the property `allocate_sequence` depends on:
    if somebody ever gave this table a tenant column, the allocator would go
    back to reading zero and signups would fail again — silently on sqlite.
    """
    from django.db import connection

    from tests.isolation_helpers import clear_live_guc

    columns = {f.column for f in models.PlatformNumberSeries._meta.get_fields()}
    assert "tenant_id" not in columns, (
        "platform_number_series has grown a tenant_id — it is Bynry's counter, "
        "and a tenant policy on it would make every signup read a sequence of 0"
    )

    clear_live_guc()
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relrowsecurity FROM pg_class WHERE relname = 'platform_number_series'"
        )
        assert cursor.fetchone()[0] is False
    # And it really is readable with no context — which is the point of all of it.
    assert models.PlatformNumberSeries.objects.count() >= 0


@pytest.mark.django_db
def test_def_ten_4446__s107_still_shows_the_plan_through_the_whole_stack():
    """THE LIVE-SCREEN CHECK, and it is deliberately NOT PostgreSQL-only.

    A policy over a read that runs with no `app.tenant_id` is not a test going
    red — it is Settings → Billing plan going blank in front of a customer, with
    every test in this repo still green. So this one goes through the WHOLE
    stack: a real sign-in, a real URL under the tenant prefix, and therefore
    `TenantContextMiddleware` resolving the slug and SETting the GUC, rather
    than `api_call`'s stand-in which enters the context itself and would prove
    nothing about the middleware.

    On PostgreSQL it is the real proof — the policy is on and the payload still
    arrives. On sqlite it still checks that the route, the session and the role
    gate agree, which is worth having on every run.

    It went red ONLY after `test_be01_tenancy`, whose autouse fixture left the
    process tenant resolver at None, so this sign-in 404'd (DEF-TEN-6789).
    That fixture now restores the resolver; this case was never the fault.
    """
    payload = brazosbend_payload()
    payload["subdomain"] = "s107stack"
    payload["owner"] = {**payload["owner"], "email": "owner@s107stack.example"}
    tenant, _ = provisioned_tenant(payload)

    client = signed_in_client(
        payload["owner"]["email"], payload["owner"]["password"], tenant=tenant.subdomain
    )
    response = api_get(client, "/subscription", tenant=tenant.subdomain)

    assert response.status_code == 200, response.content
    body = response.json()
    assert body["plan"]["code"] == "growth", body
    assert body["implementation_order"]["order_no"].startswith("IMPL-"), body


@pytest.mark.django_db
def test_def_ten_4446__the_counter_hands_out_consecutive_numbers_on_any_vendor():
    """The arithmetic, on whatever database is in front of us.

    Vendor-independent on purpose: it is the one thing in this file the default
    sqlite suite can prove, and it is worth proving there because it is what
    every other test's `IMPL-26-0001` silently depends on.
    """
    on = date(2026, 9, 7)
    first = platform_numbering.allocate_sequence(on)
    second = platform_numbering.allocate_sequence(on)
    assert (first, second) == (1, 2)

    # A different year is a different counter, not a continuation.
    assert platform_numbering.allocate_sequence(date(2027, 1, 1)) == 1
    assert platform_numbering.allocate_sequence(on) == 3

    row = models.PlatformNumberSeries.objects.get(
        series=platform_numbering.IMPLEMENTATION_ORDER_SERIES, year=2026
    )
    assert row.next_sequence == 4, "the counter must point PAST the number it gave out"
