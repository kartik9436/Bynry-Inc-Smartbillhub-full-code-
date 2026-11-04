# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-001 (EP-CWP-01) — the guest surface under load, per the PO
#           ruling of 2026-09-03 (NFR-38–41). Screens: CWP-001
# Rules:    NFR-39 (rate limits per tenant as well as per address; a connection
#           budget so a portal spike cannot exhaust the pool the staff app
#           draws from) · NFR-41 (a guest lookup is one indexed read per table
#           and no join across a tenant's history) · BR-CWP-022 (the
#           per-address sixty stays)
# Tests:    this file — the per-tenant throttle refuses the tenant's next
#           visitor and nobody else's; the in-flight budget refuses with 429 +
#           Retry-After before the first query and releases its slot; the
#           front page costs a fixed, small number of queries
# Impacts:  apps/portal/guards.py · guest_api.py · config/settings/base.py
# ───────────────────────────────────────────────────────
"""US-CWP-001 under load — the guards NFR-39 and NFR-41 ask for, proved."""

import pytest
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext, override_settings
from rest_framework.test import APIRequestFactory

from apps.portal import guards, guest_api
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import brand_fully, switch_on


@pytest.fixture(autouse=True)
def _clean_cache():
    """Both guards count in the default cache; a count carried between tests
    would make the second one's verdict depend on the first's."""
    cache.clear()
    yield
    cache.clear()


def _reads(queries):
    """The SELECTs a request cost. On PostgreSQL `tenant_context` also issues
    `SELECT set_config('app.tenant_id', …)` to set the tenant, which is the
    price of isolation and not a read of anything — it is left out so the
    count means the same thing on both vendors (hard-won law 14)."""
    return [q["sql"] for q in queries if "set_config" not in q["sql"] and not q["sql"].lstrip().upper().startswith("SET ")]


def _guest_request(tenant, address="198.51.100.10"):
    """A visitor: no user, no role, the tenant resolved from the path the way
    BE-01 resolves it, from `address`."""
    request = APIRequestFactory().get(
        f"/api/{tenant.subdomain}/portal/public/front", REMOTE_ADDR=address
    )
    request.tenant_slug = tenant.subdomain
    request.tenant_id = tenant.id
    return request


def _front(tenant, address="198.51.100.10"):
    with tenant_context(tenant.id):
        return guest_api.front(_guest_request(tenant, address))


@override_settings(PORTAL_TENANT_RATE="3/min")
@pytest.mark.django_db
def test_us_cwp_001_load_one_tenants_spike_is_refused_for_that_tenant_only(pine_hill, sarah, oak_ridge, elena):
    """NFR-39: three visitors from three DIFFERENT addresses are each well under
    the per-address sixty, and together they are Pine Hill's whole allowance
    for the minute. The fourth is refused; Oak Ridge's first is not."""
    switch_on(pine_hill, sarah)
    switch_on(oak_ridge, elena)
    for n in range(3):
        assert _front(pine_hill, address=f"203.0.113.{n + 1}").status_code == 200
    refused = _front(pine_hill, address="203.0.113.99")
    assert refused.status_code == 429
    assert refused["Retry-After"]
    assert refused.data["message_key"] == "errors.rate-limited"
    assert _front(oak_ridge, address="203.0.113.99").status_code == 200  # a different utility


@override_settings(PORTAL_INFLIGHT_MAX=1)
@pytest.mark.django_db
def test_us_cwp_001_load_over_budget_is_refused_before_the_first_query_and_the_slot_is_freed(pine_hill, sarah):
    """NFR-39: the connection budget. With one slot held (a request in flight
    on another worker), the next visitor is told to come back in a second
    without costing a single query; when the slot frees, the same visitor is
    served."""
    switch_on(pine_hill, sarah)
    assert guards._take_slot() is True  # the request in flight elsewhere
    with CaptureQueriesContext(connection) as queries:
        refused = _front(pine_hill)
    assert refused.status_code == 429
    assert refused["Retry-After"] == str(guards.INFLIGHT_RETRY_AFTER_SECONDS)
    assert _reads(queries) == [], _reads(queries)
    guards._release_slot()
    assert guards.inflight() == 0
    assert _front(pine_hill).status_code == 200
    assert guards.inflight() == 0  # released on exit, every time


@pytest.mark.django_db
def test_us_cwp_001_load_a_served_request_releases_its_slot_even_when_the_view_raises(pine_hill):
    with tenant_context(pine_hill.id):
        request = _guest_request(pine_hill)
        request.tenant_id = None  # resolves to nothing → require_tenant raises 404 inside DRF
        assert guest_api.front(request).status_code == 404
    assert guards.inflight() == 0


@pytest.mark.django_db
def test_us_cwp_001_load_the_front_page_is_five_point_reads_and_no_history_join(pine_hill, sarah):
    """NFR-41, made a number: the tenant row by primary key, the settings row by
    primary key, the enabled services by the tenant's own indexed foreign key,
    and — since wave D — whether ANY help answer is published and whether ANY
    service centre is shown. A sixth query here is a red test, not a slow
    afternoon.

    ⚠ **THIS SAID THREE UNTIL 2026-09-04 AND HAD BEEN RED SINCE WAVE D
    (`DEF-CWP-3777`).** The two extra reads are `BR-CWP-093` doing its job: a
    link to an empty Help page is worse than no link, and you cannot know the
    page is empty without asking. They were added with the screens that need
    them and this budget was never moved, so the guard sat red — invisibly,
    because nothing had run the whole portal suite in one go.

    ⚠ **AND THE BUDGET IS RAISED, NOT REMOVED.** Five is still every read by a
    tenant-indexed key and no join over history; the point of the number is
    that a SIXTH has to be argued for. A guard that gets deleted the first time
    it is inconvenient was never a guard.
    """
    switch_on(pine_hill, sarah)
    brand_fully(pine_hill, sarah)
    with CaptureQueriesContext(connection) as queries:
        assert _front(pine_hill).status_code == 200
    sql = _reads(queries)
    assert len(sql) == 5, sql
    for statement in sql:
        assert "tenant_id" in statement or "tenants" in statement, statement
        assert "service_requests" not in statement and "invoices" not in statement, statement
    # And the OFF branch is two reads — the row is what says it is off.
    with tenant_context(pine_hill.id):
        from apps.portal import settings_service

        settings_service.save_settings(sarah, pine_hill.id, {"is_live": False})
    with CaptureQueriesContext(connection) as queries:
        assert _front(pine_hill).data["is_live"] is False
    assert len(_reads(queries)) == 2, _reads(queries)
