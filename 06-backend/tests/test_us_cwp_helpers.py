# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-001 · US-CWP-069 · US-CWP-070 §4 — Pine Hill Water & Power
#           and Oak Ridge, built from the SAME payloads the demo fixture uses.
# Rules:    10-execution-plan.md *Fixture* (own tenants; no Brazos Bend figure
#           moves) · BR-CWP-005 (every read runs under the tenant's context)
# Tests:    imported by tests/test_us_cwp_001_front.py · _069_settings.py ·
#           _070_branding.py · _001_pg.py
# Impacts:  apps/portal/sample_data.py (the payloads)
# ───────────────────────────────────────────────────────
"""Shared fixtures for the customer-portal stories."""

from __future__ import annotations

import copy
from types import SimpleNamespace

import pytest

from apps.portal import sample_data, settings_service
from apps.portal.seams import tenancy_seam
from apps.tenancy import services as tenancy_services
from core.permissions import BILLING_CLERK, EXECUTIVE, SYSTEM_ADMIN
from core.tenancy import tenant_context
from tests.test_us_met_helpers import *  # noqa: F401,F403 — growth_plan · identity_seam · audit_rows
from tests.test_us_met_helpers import staff_actor
from tests.test_us_ten_helpers import provisioned_tenant


@pytest.fixture(autouse=True)
def fresh_guest_throttle():
    """⚠ **THE ANONYMOUS THROTTLE IS PER ADDRESS PER MINUTE, AND A TEST PROCESS
    IS ONE ADDRESS** (`DEF-CWP-3707`, found 2026-09-04).

    `PublicOnboardingThrottle` allows sixty guest requests a minute
    (`BR-CWP-022`) and keeps its counter in the Django cache, which lives for
    the whole pytest process. Wave C's four files make far more than sixty guest
    calls between them, so **every later test in the run was answered `429`** —
    including wave A's and wave B's, which had passed alone minutes earlier.
    The failures read as *"the front page 404s"*, *"the report was not created"*,
    *"the branding payload has no strapline"*: twenty of them, in five files, none
    of them about what they appeared to be about.

    Clearing the counter before each test is the honest fix: a real visitor is
    one address making a handful of requests, not one address making six hundred.

    ⚠ **THE NAME HAS NO LEADING UNDERSCORE AND THAT IS LOAD-BEARING.** Every
    portal test file picks these fixtures up with `from tests.test_us_cwp_helpers
    import *`, and a star import **skips names beginning with an underscore** —
    so the first draft of this fixture, called `_fresh_guest_throttle`, was
    collected by nothing and the twenty failures stayed exactly as they were.
    ⚠ **It does NOT weaken the throttle test** — `US-CWP-015` TC-5's *sixty-first
    request in a minute* makes its own sixty-one calls inside a single test and
    is unaffected.
    """
    from django.core.cache import cache

    cache.clear()
    yield


@pytest.fixture(autouse=True)
def behind_one_load_balancer(settings):
    """The portal suite runs as production does: ONE load balancer of ours in
    front (`TRUSTED_PROXY_COUNT = 1`, the AWS shape), so the single
    `X-Forwarded-For` value a case sends IS the address the balancer saw.

    ⚠ **ADDED 2026-10-30 (`DEF-CWP-10710`, audit L3-02).** Until then the
    lockout read `X-Forwarded-For`'s FIRST value whatever the proxy count, and
    these cases told two visitors apart by changing that header — which is the
    forgery the defect is about. The lockout now reads the throttle's identity,
    and with no trusted proxy that ignores the header entirely, so every case
    here would have been one visitor. Saying how many proxies are trusted is
    what makes the header mean something; `test_us_cwp_002_lockout.py` proves
    the forged-prefix and no-proxy cases separately. Assigning
    `REST_FRAMEWORK` fires `setting_changed`, which reloads DRF's
    `api_settings`, exactly as `test_be_trusted_proxy.py` does.
    """
    settings.TRUSTED_PROXY_COUNT = 1
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "NUM_PROXIES": 1}
    yield


def _provision(spec):
    tenant, _result = provisioned_tenant(copy.deepcopy(spec["signup"]))
    return tenant


@pytest.fixture()
def pine_hill(growth_plan, identity_seam):
    """Pine Hill Water & Power — provisioned, branded, portal NOT yet on
    (a fresh tenant reads the R8 defaults until a person switches it on)."""
    tenant = _provision(sample_data.PINE_HILL)
    with tenant_context(tenant.id):
        actor = SimpleNamespace(id=None, role=SYSTEM_ADMIN)
        tenancy_services.save_company_profile(actor, dict(sample_data.PINE_HILL["company"]))
    return tenant


@pytest.fixture()
def oak_ridge(growth_plan, identity_seam):
    """The isolation tenant, with its own strapline and colours."""
    tenant = _provision(sample_data.OAK_RIDGE)
    with tenant_context(tenant.id):
        actor = SimpleNamespace(id=None, role=SYSTEM_ADMIN)
        tenancy_services.save_company_profile(actor, dict(sample_data.OAK_RIDGE["company"]))
    return tenant


@pytest.fixture()
def sarah(pine_hill):
    """Sarah Miller — Pine Hill's System Admin (the provisioned owner)."""
    return staff_actor(pine_hill, "system_admin", sample_data.PINE_HILL["signup"]["owner"]["email"])


@pytest.fixture()
def pine_clerk(pine_hill):
    """A Pine Hill Billing Clerk — refused at every Settings door (A4)."""
    return staff_actor(pine_hill, "billing_clerk", "clerk@pinehillwp.test")


@pytest.fixture()
def pine_exec(pine_hill):
    """A Pine Hill Executive — may READ Settings, never write (A4 View)."""
    return staff_actor(pine_hill, "executive", "exec@pinehillwp.test")


@pytest.fixture()
def elena(oak_ridge):
    return staff_actor(oak_ridge, "system_admin", sample_data.OAK_RIDGE["signup"]["owner"]["email"])


def switch_on(tenant, actor, **switches):
    """Turn the portal live for `tenant`, with the R8 defaults unless overridden."""
    with tenant_context(tenant.id):
        return settings_service.save_settings(actor, tenant.id, {"is_live": True, **switches})


def brand_fully(tenant, actor, spec=None):
    """Apply the fixture's strapline, chips, hours and emergency number."""
    spec = spec or sample_data.PINE_HILL
    with tenant_context(tenant.id):
        by_code = {row["code"]: row["id"] for row in tenancy_seam.enabled_services(tenant.id)}
        branding = dict(spec["branding"])
        codes = branding.pop("front_page_services")
        branding["front_page_service_ids"] = [by_code[code] for code in codes]
        return settings_service.save_branding(actor, tenant.id, branding)


def seed_addresses_for(tenant, actor):
    """Pine Hill's street AND its prices — the SAME code the demo fixture runs,
    so a figure the walkthrough shows and a figure a test asserts can never come
    from two different seeders.

    ⚠ **BOTH HALVES, IN ORDER.** `seed_street` (wave B) creates the addresses
    the burst is on, with no services and no plan; `seed_priced_addresses`
    (wave C) adds `31 Palm Ct` with its fees and puts a live account on
    `1408 Elm St · A`, which is what makes that address read as a MOVE-IN. The
    second reads the first's rows, so calling it alone would seed a street with
    no Elm St in it and TC-3 would pass over nothing.
    """
    with tenant_context(tenant.id):
        sample_data.seed_street(actor)
        return sample_data.seed_priced_addresses(actor)




# ═══════════════════════════════════════════════════════════════════════════
# CR-068 wave E — Maria, the landlord, and the four accounts that total 872.82
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **THE BILLS ARE WRITTEN THROUGH BILLING'S ORM AND NOT THROUGH ITS ISSUE
# PATH**, which is the shape `tests/test_us_pay_001_record_payment.py` already
# established and states its own reason for: the issue path drags the rating
# engine, the GL stamp and the release gate into a test about what happens to a
# bill AFTER it exists. What wave E is about is a READ over issued bills, and
# `status`, `total`, `due_date` and `issued_at` are the only issue-time facts
# that read consults.

MARIA_EMAIL = "maria.alvarez@example.test"
MARIA_PASSWORD = "Elm-Street-1408"
#: `US-CWP-024` TC-2's four figures. 142.18 + 0.00 + 318.04 + 412.60 = 872.82.
LANDLORD_BILLS = ("142.1800", "0.0000", "318.0400", "412.6000")
LANDLORD_TOTAL = "872.8200"
#: TC-3 — one 142.18 bill with 40.00 against it is neither paid nor unpaid.
PART_PAID_OPEN = "102.1800"


def an_issued_bill(tenant, account, *, number, total, issued_on, due_on=None):
    """One ISSUED bill, in the shape the balance read will meet it."""
    from datetime import UTC, datetime
    from decimal import Decimal

    from apps.billing import models as billing_models

    amount = Decimal(total)
    return billing_models.Invoice.objects.create(
        tenant=tenant,
        account=account,
        invoice_no=number,
        status=billing_models.INVOICE_ISSUED,
        service_date=issued_on,
        period_start=issued_on.replace(day=1),
        period_end=issued_on,
        due_date=due_on or issued_on,
        subtotal=amount,
        tax_total=Decimal("0"),
        total=amount,
        issued_at=datetime(issued_on.year, issued_on.month, issued_on.day, 9, 0, tzinfo=UTC),
    )


def elm_street_account(tenant, actor):
    """Maria's account at `1408 Elm St · A`, seeded by the wave-C fixture."""
    from apps.customers import models as customers_models

    seed_addresses_for(tenant, actor)
    with tenant_context(tenant.id):
        return (
            customers_models.Account.objects.filter(
                tenant_id=tenant.id, unit__premises__address_line=sample_data.ELM_ST
            )
            .select_related("unit")
            .first()
        )


def enrol_maria(tenant, actor, *, email: str = MARIA_EMAIL, password: str = MARIA_PASSWORD):
    """A credential attached to the customer already on file (`BR-CWP-029`).

    Through `credentials.create_credential`, which is the ONE door — a test that
    wrote the row itself would prove nothing about the door the product uses.
    """
    from apps.portal import credentials, models as portal_models

    account = elm_street_account(tenant, actor)
    with tenant_context(tenant.id):
        return credentials.create_credential(
            tenant.id,
            account=account,
            email=email,
            password=password,
            otp_channel=portal_models.CHANNEL_SMS,
        )


ROLE_OF = {"system_admin": SYSTEM_ADMIN, "billing_clerk": BILLING_CLERK, "executive": EXECUTIVE}
