# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-008 (EP-CWP-03) TC-5 · US-CWP-007 TC-6 · US-CWP-010 TC-6 —
#           the isolation only PostgreSQL can prove.
# Rules:    CLAUDE.md hard rule 1 (RLS FORCE; no tenant → nothing) · BR-CWP-005
#           (the tenant is resolved from the path before anything is read) ·
#           hard-won law 14 (proved on PostgreSQL, never faked on SQLite)
# Tests:    this file — zero rows without context under the non-superuser
#           probe role; Pine Hill's interruption invisible under Oak Ridge; a
#           cross-tenant insert refused by the policy itself
# Impacts:  apps/metering/migrations/0047_rls_interruptions.py
# ───────────────────────────────────────────────────────
"""US-CWP-008 on PostgreSQL — and this table matters more than the others.

Every other tenant table in this product is reached by a signed-in member of one
tenant. `interruptions` is WRITTEN by an anonymous request from the public
internet and READ by another. The application resolves the tenant from the first
path segment (`BR-CWP-005`); this policy is what makes that a guarantee.

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
    DATABASE_URL=postgres://smartbillhub:smartbillhub@localhost:5432/<db> \\
        pytest tests/test_us_cwp_008_pg.py

Every case carries `requires_postgres` and SKIPS on the default SQLite suite
rather than passing vacuously (hard-won law 14).
"""

import pytest

from apps.portal import guest_api
from tests.isolation_helpers import (  # noqa: F401 — fixtures used by name
    assert_denied_without_context,
    assert_rls_scoped,
    assert_write_into_other_tenant_refused,
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
    "notes": "Water coming up through the pavement.",
    "reporter_name": "D. Okafor",
    "reporter_phone": "(512) 555-7730",
}


def _report(tenant):
    return api_call(
        guest_api.reports,
        "post",
        f"/api/{tenant.subdomain}/portal/public/reports",
        tenant=tenant,
        data=dict(REPORT),
        headers={"X-Forwarded-For": "198.51.100.10"},
    )


def _open(tenant, actor):
    """A report, and then a CLERK opening the interruption — `CR-072`.

    ⚠ **WITHOUT THE SECOND HALF THESE CASES WOULD PASS OVER AN EMPTY TABLE.**
    A report used to write the `interruptions` row itself; it does not any more,
    so every assertion below would be made against nothing — and
    `assert_rls_scoped`'s `min_owner_rows` is the only reason that fails loudly
    instead of going quietly green. Named here because a fixture that writes no
    rows is the classic way an isolation suite proves nothing.
    """
    from apps.customers import models as customers_models
    from apps.metering import interruption_service
    from apps.customers import service_request_service
    from core.tenancy import tenant_context

    _report(tenant)
    request = customers_models.ServiceRequest.objects.filter(tenant_id=tenant.id).latest(
        "created_at"
    )
    with tenant_context(tenant.id):
        row = interruption_service.create_interruption(
            actor, kind=REPORT["kind"], location_text=REPORT["location_text"]
        )
        service_request_service.attach_interruption(actor, request.id, interruption_id=row.id)
    return row


@requires_postgres
@pytest.mark.django_db
def test_us_cwp_008_pg_no_context_sees_no_interruption(pine_hill, sarah, rls):
    switch_on(pine_hill, sarah)
    _open(pine_hill, sarah)
    assert_denied_without_context(rls, "interruptions")


@requires_postgres
@pytest.mark.django_db
def test_us_cwp_008_tc5_pg_pine_hills_burst_is_invisible_under_oak_ridge(
    pine_hill, sarah, oak_ridge, elena, rls
):
    switch_on(pine_hill, sarah)
    switch_on(oak_ridge, elena)
    _open(pine_hill, sarah)
    _open(oak_ridge, elena)
    from apps.metering import interruptions as interruption_models

    owner_ids = {
        str(row_id)
        for row_id in interruption_models.Interruption.objects.filter(
            tenant_id=pine_hill.id
        ).values_list("id", flat=True)
    }
    assert_rls_scoped(
        rls,
        "interruptions",
        owner=pine_hill,
        intruder=oak_ridge,
        owner_ids=owner_ids,
    )


@requires_postgres
@pytest.mark.django_db
def test_us_cwp_008_pg_a_cross_tenant_write_is_refused_by_the_policy(pine_hill, sarah, oak_ridge, rls):
    switch_on(pine_hill, sarah)
    _open(pine_hill, sarah)
    assert_write_into_other_tenant_refused(rls, "interruptions", owner=pine_hill, intruder=oak_ridge)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-008@d6d31c46 (EP-CWP-03 §3 TC-5 + CLAUDE.md hard rule 1)
# generated: 2026-09-04 by the CR-068 wave B build lane · AMENDED 2026-09-04 by the CR-072 lane (a CLERK opens the interruption; a report no longer writes that table, so the fixture had to move or these cases would have run against zero rows)
# checklist: A✔ B✔ C✔ D✔ E=n/a(test file) F✔ G✔ H=PENDING(the 🔒 half is metering/0047 — review-ledger row)
# gates: run under DJANGO_SETTINGS_MODULE=config.settings.local on PostgreSQL 16; proved RED first by dropping the policy
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
