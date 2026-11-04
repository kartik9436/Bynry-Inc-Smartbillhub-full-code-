# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-6426 — a Billing Clerk saw no sub-categories on New account
#           and Move-in: the picker read `GET /lookups/account_subtypes`, a
#           Settings door (`SettingsReadAnyWriteSystemAdmin`) that answers the
#           clerk 403 by signed law (A4 `settings_lookups`, US-TEN-009 TC-5).
# Ruling:   OQ-CUS-12618 (PO 2026-09-23): sub-categories come from Settings →
#           Reference data → account categories and sub-categories.
# Tests:    this file
# ───────────────────────────────────────────────────────
"""**The clerk gets a read of their own; the Settings door stays as signed.**

RED-FIRST (hard-won law 7): before `GET /accounts/subcategories` existed the
first case failed at the attribute lookup of the view; the second case passes
before AND after, and that is its job — it proves the fix did not widen the
Settings door to get green.

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY:** a case run as an admin (the admin
reads both doors) — so both cases are the Billing Clerk; and a list that is
non-empty because it serves INACTIVE rows — so one row is deactivated and must
not come back.
"""

import pytest

from apps.customers import api as customers_api
from apps.customers import models as customers_models
from apps.customers import services as customers_services
from apps.tenancy import api as tenancy_api

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import FakeUser, api_call, brazos, marcus, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


def test_a_billing_clerk_reads_the_active_subcategories_with_their_category(brazos, marcus):
    with tenant_ctx(brazos):
        customers_services.ensure_account_subtypes()
        retired = customers_models.AccountSubtype.objects.filter(tenant_id=brazos.id).first()
        retired.active = False
        retired.save(update_fields=["active"])
        active = customers_models.AccountSubtype.objects.filter(
            tenant_id=brazos.id, active=True
        ).count()

    response = api_call(
        customers_api.account_subcategories,
        "get",
        user=FakeUser(marcus.id),
        role="billing_clerk",
        tenant=brazos,
    )

    assert response.status_code == 200
    rows = response.data["results"]
    assert len(rows) == active > 0
    assert retired.code not in {row["code"] for row in rows}
    assert all(row["parent_code"] for row in rows)
    assert set(rows[0]) == {"id", "code", "name", "parent_code"}


def test_the_settings_door_still_refuses_the_clerk(brazos, marcus):
    response = api_call(
        tenancy_api.lookups,
        "get",
        user=FakeUser(marcus.id),
        role="billing_clerk",
        tenant=brazos,
        list_code="account_subtypes",
    )
    assert response.status_code == 403
