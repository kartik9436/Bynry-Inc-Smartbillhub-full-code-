# ── Trace ──────────────────────────────────────────────
# Change:  CR-072 (2026-09-04) — the report IS the service request. The two new
#          columns land on a table an ANONYMOUS request from the public internet
#          now writes, and this file is the only place that is proved.
# Rules:   CLAUDE.md hard rule 1 (RLS ENABLE + FORCE; no tenant → nothing) ·
#          BR-CWP-005 (the tenant is resolved from the path before anything is
#          read) · BR-CWP-026 (a guest write creates work and changes no
#          account) · hard-won law 14 (proved on PostgreSQL, never on SQLite)
# Tests:   this file — the policy is really ON and FORCED (pg_class, both
#          columns); zero rows without context under the NON-SUPERUSER probe;
#          Pine Hill's report invisible under Oak Ridge; a cross-tenant write
#          refused by the policy itself; the widened columns cross no boundary
# Impacts: apps/customers/migrations/0040_cr072_report_is_the_request.py ·
#          apps/customers/migrations/0018 (the policy this inherits)
# ───────────────────────────────────────────────────────
"""CR-072 on PostgreSQL — and `service_requests` just changed who writes it.

⚠ **THIS TABLE HAS ALWAYS CARRIED RLS AND HAS NOT ALWAYS CARRIED STRANGERS.**
Until `CR-068` wave B every row was written by a signed-in clerk. Since
`CR-072` the FIRST thing a passer-by with no account does — reporting a burst
main — lands here, and `problem_kind` and `interruption_id` are the columns
that let it. So the policy is re-proved on the widened table rather than
assumed to have come along: a new column inherits the table's policy, and
"inherits" is exactly the kind of sentence hard-won law 1 is about.

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
    DATABASE_URL=postgres://smartbillhub:smartbillhub@localhost:5432/<db> \\
        pytest tests/test_cr072_pg.py --reuse-db

⚠ **RUN UNDER `sbh_rls_probe`, WHICH IS NOT A SUPERUSER.** The dev role IS one,
superusers bypass row-level security unconditionally, and every RLS assertion
made on that connection is vacuous. `rls.assert_is_a_real_proof()` re-reads
`pg_roles` and FAILS rather than skips (`tests/isolation_helpers.py`).

Every case carries `requires_postgres` and SKIPS on the default SQLite suite
rather than passing vacuously (hard-won law 14).
"""

import pytest
from django.db import connection

from apps.customers import models as customers_models
from apps.portal import guest_api
from tests.isolation_helpers import (  # noqa: F401 — fixtures used by name
    assert_denied_without_context,
    assert_rls_scoped,
    assert_write_into_other_tenant_refused,
    live_tenant_context,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import switch_on
from tests.test_us_ten_helpers import api_call

REPORT = {
    "kind": "leak_or_burst",
    "location_text": "1408 Elm St, Austin TX 78702",
    "notes": "Water coming up through the pavement outside number 1412.",
    "reporter_name": "D. Okafor",
    "reporter_phone": "(512) 555-7730",
}


def _report(tenant):
    """The guest call: NO user, NO role — a passer-by holding nothing."""
    return api_call(
        guest_api.reports,
        "post",
        f"/api/{tenant.subdomain}/portal/public/reports",
        tenant=tenant,
        data=dict(REPORT),
        headers={"X-Forwarded-For": "198.51.100.10"},
    )


@requires_postgres
@pytest.mark.django_db
def test_cr072_pg_the_policy_is_enabled_and_forced_on_the_widened_table(pine_hill, sarah, rls):
    """⚠ **BOTH FLAGS, READ OUT OF `pg_class`, BECAUSE THEY ARE TWO DIFFERENT
    PROMISES.** `relrowsecurity` turns the policy on; `relforcerowsecurity`
    applies it to the TABLE OWNER as well. Without the second, the role the app
    connects as — which owns these tables — walks straight past it and every
    other case in this file would pass while production leaked.
    """
    rls.assert_is_a_real_proof()
    switch_on(pine_hill, sarah)
    _report(pine_hill)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
            "WHERE oid = 'service_requests'::regclass"
        )
        enabled, forced = cursor.fetchone()
    assert enabled, "service_requests: ROW LEVEL SECURITY is not enabled"
    assert forced, "service_requests: RLS is not FORCED, so the owner bypasses it"

    # And the two columns CR-072 added are really on the table the policy guards
    # — a column added to a different table would prove nothing here.
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'service_requests' "
            "AND column_name IN ('problem_kind', 'interruption_id')"
        )
        found = {row[0] for row in cursor.fetchall()}
    assert found == {"problem_kind", "interruption_id"}


@requires_postgres
@pytest.mark.django_db
def test_cr072_pg_no_context_sees_no_report(pine_hill, sarah, rls):
    """No `app.tenant_id` → the database answers nothing at all, to a role RLS
    applies to. This is the guarantee `BR-CWP-005` rests on: the guest edge
    resolves the tenant from the path, and this is what makes that a guarantee
    rather than a habit."""
    switch_on(pine_hill, sarah)
    _report(pine_hill)
    assert_denied_without_context(rls, "service_requests")


@requires_postgres
@pytest.mark.django_db
def test_cr072_pg_pine_hills_report_is_invisible_under_oak_ridge(
    pine_hill, sarah, oak_ridge, elena, rls
):
    switch_on(pine_hill, sarah)
    switch_on(oak_ridge, elena)
    _report(pine_hill)
    _report(oak_ridge)
    owner_ids = {
        str(row_id)
        for row_id in customers_models.ServiceRequest.objects.filter(
            tenant_id=pine_hill.id, problem_kind__isnull=False
        ).values_list("id", flat=True)
    }
    assert owner_ids, "the fixture wrote no report, so this case would prove nothing"
    assert_rls_scoped(
        rls,
        "service_requests",
        owner=pine_hill,
        intruder=oak_ridge,
        owner_ids=owner_ids,
    )


@requires_postgres
@pytest.mark.django_db
def test_cr072_pg_the_widened_columns_cross_no_boundary(
    pine_hill, sarah, oak_ridge, elena, rls
):
    """⚠ **A LEAK CHECK ON THE NEW COLUMNS THEMSELVES, NOT ONLY ON THE ROW.**
    `assert_rls_scoped` reads ids; a serialiser or a policy written per-column
    could still expose a value. So this reads `problem_kind` back under the
    WRONG tenant and asserts the query returns nothing — the reporter's chosen
    kind is as scoped as the row it sits on."""
    switch_on(pine_hill, sarah)
    switch_on(oak_ridge, elena)
    _report(pine_hill)
    with live_tenant_context(oak_ridge.id):
        seen = rls.rows(
            "SELECT problem_kind, interruption_id FROM service_requests "
            "WHERE problem_kind IS NOT NULL"
        )
    assert seen == [], f"LEAK — Oak Ridge read Pine Hill's report kind: {seen}"


@requires_postgres
@pytest.mark.django_db
def test_cr072_pg_a_cross_tenant_write_is_refused_by_the_policy(
    pine_hill, sarah, oak_ridge, rls
):
    """The policy's WITH CHECK, in the database's own words."""
    switch_on(pine_hill, sarah)
    _report(pine_hill)
    message = assert_write_into_other_tenant_refused(
        rls, "service_requests", owner=pine_hill, intruder=oak_ridge
    )
    assert "row-level security" in message


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-072 §4 (the ruled shape) + CLAUDE.md hard rule 1
# generated: 2026-09-04 by the CR-072 build lane
# checklist: A✔ B✔ C✔ D✔ E=n/a(test file) F✔ G✔ H=PENDING(the 🔒 half is customers/0040 — review-ledger row)
# gates: run under DJANGO_SETTINGS_MODULE=config.settings.local on PostgreSQL 16 as a NON-SUPERUSER probe; proved RED first by dropping the policy off service_requests
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
