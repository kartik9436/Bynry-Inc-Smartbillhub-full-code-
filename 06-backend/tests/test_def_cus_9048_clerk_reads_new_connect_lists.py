# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-9048 — a Billing Clerk running New Connect got no device,
#           no size and no work template on step 3: `GET /lookups/asset_types`,
#           `GET /lookups/service_size_classes` and `GET /work/templates` each
#           answered 403 (A4 `settings_lookups` gives the clerk no cell).
# Ruling:   PO 2026-10-02, verbatim: *"5. Should a billing clerk see the size
#           lists New Connection needs? A · Let the billing clerk read the size
#           and equipment lists (read only)."* — decision log, top row.
# Rules:    A4 (04-docs/01-spec/04-roles-permissions.md, addendum 2026-10-02) ·
#           DEF-196 (the Settings gate is NOT widened) · BR-SHL-025
# ───────────────────────────────────────────────────────
"""**The clerk READS the three lists New Connect step 3 needs — and nothing else.**

RED FIRST (law 7): with the two views still on `SettingsReadAnyWriteSystemAdmin`
the three read cases answered 403; the refusal cases passed before and after,
and that is their job — they prove the read did not open a write or a
neighbouring list.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY:** a case run as an admin (every case
here is the Billing Clerk); a read that opened the WHOLE Settings door (so a
third list, `uoms`, must still refuse); and a read that opened the write (so a
POST to each of the three must still refuse).
"""

import pytest

from apps.tenancy import api as tenancy_api
from apps.work import api as work_api
from core import permissions

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import FakeUser, api_call, provisioned_tenant

pytestmark = pytest.mark.django_db

CLERK = "billing_clerk"


def _get_lookup(tenant, list_code, role=CLERK):
    return api_call(
        tenancy_api.lookups, "get", user=FakeUser(), role=role, tenant=tenant, list_code=list_code
    )


@pytest.mark.parametrize("list_code", ["asset_types", "service_size_classes"])
def test_the_billing_clerk_reads_new_connects_size_and_equipment_lists(
    growth_plan, identity_seam, list_code
):
    tenant, _ = provisioned_tenant()
    response = _get_lookup(tenant, list_code)
    assert response.status_code == 200, response.data
    assert "results" in response.data


def test_the_billing_clerk_reads_the_work_templates_list(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    response = api_call(work_api.templates, "get", user=FakeUser(), role=CLERK, tenant=tenant)
    assert response.status_code == 200, response.data
    assert "results" in response.data


@pytest.mark.parametrize("list_code", ["asset_types", "service_size_classes"])
def test_the_billing_clerk_still_cannot_write_those_lists(growth_plan, identity_seam, list_code):
    tenant, _ = provisioned_tenant()
    response = api_call(
        tenancy_api.lookups,
        "post",
        user=FakeUser(),
        role=CLERK,
        tenant=tenant,
        data={"code": "X-1", "name": "Made up"},
        list_code=list_code,
    )
    assert response.status_code == 403 and response.data["code"] == "AUTH-002"


def test_the_billing_clerk_still_cannot_write_a_work_template(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    response = api_call(
        work_api.templates, "post", user=FakeUser(), role=CLERK, tenant=tenant, data={"name": "X"}
    )
    assert response.status_code == 403 and response.data["code"] == "AUTH-002"


def test_every_other_list_still_refuses_the_clerk(growth_plan, identity_seam):
    """US-TEN-009 TC-5 stands: the grant is two lists by NAME, not the door."""
    tenant, _ = provisioned_tenant()
    assert _get_lookup(tenant, "uoms").status_code == 403


def test_the_grant_is_the_role_table_amendment_and_nothing_wider():
    """The permission classes and the role table name the same three lists."""
    from apps.identity.models import A4_CLERK_READ_GRANTS, A4_MATRIX

    [(role, row, lists, cell)] = A4_CLERK_READ_GRANTS
    assert (role, row, cell) == ("billing_clerk", "settings_lookups", "View")
    assert set(lists) == {f"lookups/{c}" for c in permissions.NEW_CONNECTION_CLERK_LOOKUPS} | {
        "work/templates"
    }
    # The signed grid itself is untouched: the clerk still has no cell there.
    cells = next(c for code, _label, c in A4_MATRIX if code == "settings_lookups")
    assert "billing_clerk" not in cells
    assert permissions.SettingsReadAnyWriteSystemAdmin.allowed_roles == frozenset(
        {permissions.SYSTEM_ADMIN, permissions.EXECUTIVE}
    )
