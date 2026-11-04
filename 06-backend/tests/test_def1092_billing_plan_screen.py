# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-022 (EP-TEN-05) — S107 Settings → Billing plan · Plan tab.
#           Authored 2026-08-27 for DEF-1092, hard-won law 8 ("every screen
#           needs a story"), BEFORE the screen was built.
# Defect:   DEF-1092 — "THE ENTIRE COMMERCIAL MODEL — SUBSCRIPTION,
#           IMPLEMENTATION ORDER AND ADD-ONS — HAS NO SCREEN ANYWHERE".
#           DEF-1220 (r10 prices per connection; the product prices in bands) ·
#           DEF-1222 (A1 prices packages in weeks; the column is months)
# Rules:    BR-TEN-002 (the band is a commercial tier, NEVER enforced) ·
#           BR-TEN-014 (the subscription is created `trial`, +14 days, no card)
#           BR-TEN-240 (the zero-month self-serve order at signup) ·
#           CLAUDE.md hard rule 1 (no cross-tenant queryset) · hard rule 2
#           (money 4dp stored, 2 displayed) · A4 `settings_lookups`
# Tests:    this file
# ───────────────────────────────────────────────────────
"""S107's read — `GET /subscription`, contracted 2026-08-09 and unserved until now.

⚠ **CORRECTED 2026-09-07 (`DEF-TEN-4446`).** This paragraph used to open *"THE
FOUR TABLES THIS COVERS ARE RLS-EXEMPT PLATFORM DATA"*, citing `tenancy/0021`'s
docstring, and concluded that the selector's `tenant_id=` filter was *"the only
thing standing between one utility and another utility's price"*. It was an
accurate description of the database as it then stood, and B2 §3 had never
permitted it: `implementation_orders` and `tenant_addons` carry a `tenant_id`
and are on neither of B2's lists as exempt. `tenancy/0042` applies the signed
policy to both, so the database now refuses a cross-tenant read of these tables
whatever this selector does.

**The case below is still load-bearing and is still worth its two real
tenants**, for a reason that has nothing to do with which guard is first: this
file runs on sqlite, where row-level security does not exist at all, so this is
where the APP-layer half is proved. The DATABASE half is proved on PostgreSQL in
`tests/test_def_ten_4446_commercial_rls.py`. Neither test covers the other's
ground, and a green run of this file alone says nothing about RLS.

⚠ **AND THE THREE ABSENCES ARE ASSERTED AS ABSENCES.** r10 SET-15 draws a
per-connection rate, an entitlement count and three Bynry invoices. None exists
in this product. A test that only checked what IS served would pass just as
happily over a screen that had quietly invented all three, which is the shape of
DEF-1220.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.tenancy import api, models, selectors

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (
    FakeUser,
    api_call,
    brazosbend_payload,
    provisioned_tenant,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def _payload(subdomain: str, email: str):
    payload = brazosbend_payload()
    payload["subdomain"] = subdomain
    payload["owner"] = {**payload["owner"], "email": email}
    return payload


# ── TC-1 · the plan a signup actually bought renders, banded and priced ─────
def test_def1092__the_plan_renders_with_its_banded_price_and_not_a_rate():
    """DEF-1220: the price is the CATALOGUE's, never a rate times a count."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        payload = selectors.subscription_overview()

    plan = payload["plan"]
    assert plan is not None, "a provisioned tenant always has a subscription plan"
    assert plan["code"] == "growth"  # S112 pre-selects Growth
    assert Decimal(plan["price_month"]) == Decimal("5000")
    assert plan["currency"] == "USD"
    # The BAND is served (BR-TEN-002 — commercial, never enforced) …
    assert plan["min_accounts"] == 300
    assert plan["max_accounts"] == 1000
    # … and NO per-connection rate is served, because none exists (DEF-1220).
    assert "rate_per_connection" not in plan
    assert "estimated_invoice" not in payload


# ── TC-2 · the trial (BR-TEN-014) ──────────────────────────────────────────
def test_def1092__the_subscription_renders_its_trial_state():
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        payload = selectors.subscription_overview()

    subscription = payload["subscription"]
    assert subscription["status"] == "trial"
    assert subscription["trial_ends_at"] is not None  # +14d, BR-TEN-014


# ── TC-3 · the implementation order a human can finally see ────────────────
def test_def1092__the_implementation_order_is_rendered_with_its_number():
    """The whole of DEF-1092's headline: `IMPL-26-0001` reaches a screen."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        payload = selectors.subscription_overview()

    order = payload["implementation_order"]
    assert order is not None, "BR-TEN-240 — a tenant cannot exist without one"
    assert order["order_no"].startswith("IMPL-")
    # DEF-1222: MONTHS, the PO's ruled unit — never A1's weeks.
    assert order["duration_months"] == 0
    assert Decimal(order["price"]) == Decimal("0")
    assert order["currency"] == "USD"
    assert order["instalments"] == 1
    assert order["status"] == "delivered"
    assert order["is_self_serve"] is True
    # `delivered_on` is deliberately absent — nothing was delivered on a date.
    assert order["delivered_on"] is None


# ── TC-4 · the add-on catalogue is EMPTY by ruling, and says which empty ───
def test_def1092__an_empty_addon_catalogue_is_distinguishable_from_none_taken():
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        payload = selectors.subscription_overview()

    assert payload["addons"] == []
    # The PO named no add-on (2026-08-27), so the CATALOGUE is empty too — and
    # the screen must be able to tell "you have taken none" from "there is
    # nothing to take".
    assert payload["addon_catalogue_size"] == 0


def test_def1092__a_taken_addon_renders_the_catalogue_price_when_it_has_none():
    """`tenant_addons.price_month` null = *whatever the catalogue says today*."""
    tenant, _ = provisioned_tenant()
    addon = models.Addon.objects.create(
        code="portal-plus", name="Portal Plus", price_month=Decimal("250.0000"), priced=True
    )
    models.TenantAddon.objects.create(tenant=tenant, addon=addon, price_month=None)
    with tenant_ctx(tenant):
        payload = selectors.subscription_overview()

    row = payload["addons"][0]
    assert row["code"] == "portal-plus"
    assert Decimal(row["price_month"]) == Decimal("250.0000")
    assert row["price_source"] == "catalogue"
    assert row["priced"] is True
    assert payload["addon_catalogue_size"] == 1


def test_def1092__a_negotiated_addon_price_wins_and_says_so():
    tenant, _ = provisioned_tenant()
    addon = models.Addon.objects.create(code="ami", name="AMI ingestion")  # $1.00, priced=False
    models.TenantAddon.objects.create(tenant=tenant, addon=addon, price_month=Decimal("99.5000"))
    with tenant_ctx(tenant):
        row = selectors.subscription_overview()["addons"][0]

    assert Decimal(row["price_month"]) == Decimal("99.5000")
    assert row["price_source"] == "negotiated"
    # A negotiated figure is one somebody CHOSE, so it is priced even though the
    # catalogue row still carries the PO's $1.00 placeholder.
    assert row["priced"] is True


def test_def1092__an_unpriced_catalogue_addon_is_marked_unpriced():
    """The $1.00 default must never look like a considered price."""
    tenant, _ = provisioned_tenant()
    addon = models.Addon.objects.create(code="sms", name="SMS notices")
    models.TenantAddon.objects.create(tenant=tenant, addon=addon, price_month=None)
    with tenant_ctx(tenant):
        row = selectors.subscription_overview()["addons"][0]

    assert Decimal(row["price_month"]) == Decimal("1.0000")
    assert row["priced"] is False


# ── TC-5 · the three stated absences (r10 draws all three; we have none) ────
def test_def1092__the_three_absences_are_stated_and_never_zero():
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        payload = selectors.subscription_overview()

    # OQ-660 — "connection" is defined in no glossary and the band boundary it
    # decides is $5,000 against $8,000. null, never 0.
    assert payload["connections"] is None
    assert payload["connections_unavailable"] == "OQ-660"
    # S108 — no platform invoice table exists. null, never [].
    assert payload["invoices"] is None
    assert payload["invoices_unavailable"] == "S108"
    # S109 — OQ-015 ruled v1 takes no card at all.
    assert payload["payment_method"] is None
    assert payload["payment_method_unavailable"] == "S109"


# ── TC-6 · isolation. THE tenant-scoping case, and it is load-bearing ──────
def test_def1092__the_read_is_scoped_to_the_calling_tenant():
    """The APP-layer half of the isolation, on the vendor this suite runs on.

    ⚠ **THE FIRST LINE OF THIS DOCSTRING READ *"These tables are RLS-EXEMPT, so
    the selector's filter IS the isolation"* UNTIL 2026-09-07** — true when
    written, and made false by `tenancy/0042`, which gives both priced tables
    the signed B2 §3 policy (`DEF-TEN-4446`). The filter is no longer the only
    guard.

    It is still the only guard THIS file can see. sqlite has no row-level
    security, so on the default suite the database half does not exist and a
    dropped filter would leak here exactly as it always would have. The
    PostgreSQL half lives in `tests/test_def_ten_4446_commercial_rls.py`.

    Both tenants take the same plan on purpose: if the filter were dropped the
    PLAN would still look right and only the ORDER NUMBER would betray it,
    which is exactly how this class of bug survives a review.
    """
    first, _ = provisioned_tenant(_payload("silvercreek", "a@silvercreek.example"))
    second, _ = provisioned_tenant(_payload("brazosbend2", "b@brazosbend2.example"))

    with tenant_ctx(first):
        first_payload = selectors.subscription_overview()
    with tenant_ctx(second):
        second_payload = selectors.subscription_overview()

    first_no = first_payload["implementation_order"]["order_no"]
    second_no = second_payload["implementation_order"]["order_no"]
    assert first_no != second_no
    # And neither read can see the other's row at all.
    with tenant_ctx(first):
        again = selectors.subscription_overview()
    assert again["implementation_order"]["order_no"] == first_no


# ── TC-7 · the wired route, over the real view, per role (A4) ──────────────
def test_def1092__the_endpoint_is_reachable_and_serves_the_screen_payload():
    tenant, _ = provisioned_tenant()
    response = api_call(
        api.subscription, "get", "/api/subscription", user=FakeUser(), role="system_admin",
        tenant=tenant,
    )
    assert response.status_code == 200
    assert response.data["implementation_order"]["order_no"].startswith("IMPL-")
    assert response.data["plan"]["code"] == "growth"


def test_def1092__an_executive_may_read_it_and_a_clerk_may_not():
    """A4 `settings_lookups`: Full / View / no cell (DEF-196's own split)."""
    tenant, _ = provisioned_tenant()
    executive = api_call(
        api.subscription, "get", "/api/subscription", user=FakeUser(), role="executive",
        tenant=tenant,
    )
    assert executive.status_code == 200

    clerk = api_call(
        api.subscription, "get", "/api/subscription", user=FakeUser(), role="billing_clerk",
        tenant=tenant,
    )
    assert clerk.status_code == 403


def test_def1092__the_route_is_registered_at_the_contracted_path():
    """11b §2.16 names `GET /subscription`. A view nothing routes is dead code."""
    registered = {
        str(getattr(entry, "pattern", "")) for entry in api.urlpatterns
    }
    assert "subscription" in registered


def test_def1092__there_is_no_write_verb_on_this_resource():
    """GET only, deliberately: a plan change has no rule and `OQ-610` owns the
    editable-order half. `@api_view(["GET"])` refuses everything else."""
    tenant, _ = provisioned_tenant()
    for method in ("post", "put", "patch", "delete"):
        response = api_call(
            api.subscription, method, "/api/subscription", user=FakeUser(),
            role="system_admin", tenant=tenant,
        )
        assert response.status_code == 405, method
