# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-003 (post-signup checklist surfacing Company gaps, S62)
# Rules:    BR-TEN-015 (computed from live data; manual mark-done advisory only;
#           dismissal persists) · BR-TEN-016 (mark/dismiss audited)
# Journeys: J1 step 4 (gaps computed live; links resolve to Settings tabs)
# ───────────────────────────────────────────────────────
"""US-TEN-003 — S62 checklist: computed state, manual marks, role gates."""

import pytest

from apps.tenancy import api, models, selectors, services
from core import errors

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (
    FakeUser,
    admin_actor,
    api_call,
    audit_actions,
    clerk_actor,
    lonestarridge_payload,
    provisioned_tenant,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def _items(payload):
    return {item["item"]: item for item in payload["items"]}


def test_us_ten_003_tc1__fresh_tenant_company_incomplete_services_complete(
    growth_plan, identity_seam
):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        result = selectors.checklist()
    items = _items(result)
    assert items["company_profile"]["done"] is False  # no EIN/legal name yet
    assert items["services_uom"]["done"] is True  # Electric + Water from signup
    assert result["progress"] == {"done": 1, "total": 6}  # "1 of 6 complete"
    assert items["company_profile"]["target"] == "settings/company"  # deep-link


def test_us_ten_003_tc2__filling_company_data_completes_item_without_toggle(
    growth_plan, identity_seam
):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        services.save_company_profile(
            admin_actor(),
            {
                "legal_name": "Brazos Bend Utility District No. 1",
                "ein": "74-3182640",
                "mailing_address": "9410 FM 1093 Rd, Katy, TX 77494",
                "remit_to_address": "PO Box 2210, Katy, TX 77492",
            },
        )
        result = selectors.checklist()
    items = _items(result)
    assert items["company_profile"]["done"] is True  # completed by DATA, no click
    assert items["company_profile"]["source"] == "computed"
    assert result["progress"]["done"] == 2


def test_us_ten_003_tc3__manual_mark_persists_across_sessions(
    growth_plan, identity_seam, audit_rows
):
    tenant, _ = provisioned_tenant()
    actor = admin_actor()
    with tenant_ctx(tenant):
        result = services.mark_checklist_item(actor, "numbering_documents")
        assert _items(result)["numbering_documents"]["done"] is True
    # a NEW session (fresh read) still sees the persisted state
    with tenant_ctx(tenant):
        again = selectors.checklist()
    assert _items(again)["numbering_documents"]["source"] == "manual"
    assert "checklist.item_marked_done" in audit_actions(audit_rows)  # BR-TEN-016
    stored = models.Tenant.objects.get(pk=tenant.pk).checklist_state
    assert "numbering_documents" in stored["manual_done"]  # keys = known item codes


def test_us_ten_003_tc3b__computed_item_refuses_manual_mark(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        with pytest.raises(errors.BizError) as excinfo:
            services.mark_checklist_item(admin_actor(), "company_profile")
    assert excinfo.value.br_ref == "BR-TEN-015"
    with tenant_ctx(tenant):
        with pytest.raises(errors.NotFoundError):
            services.mark_checklist_item(admin_actor(), "not_a_known_item")


def test_us_ten_003_tc4__clerk_read_allowed_writes_rejected_server_side(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    # service-layer enforcement (BR-SHL-025): clerk mark-done refused
    with tenant_ctx(tenant):
        with pytest.raises(errors.AuthError) as excinfo:
            services.mark_checklist_item(clerk_actor(), "numbering_documents")
    assert excinfo.value.code == errors.AUTH_PERMISSION_DENIED
    # API layer: clerk can VIEW the checklist (items render disabled per IS-6)…
    view = api_call(api.checklist, "get", user=FakeUser(), role="billing_clerk", tenant=tenant)
    assert view.status_code == 200
    # …but the dismiss endpoint denies with the 403 envelope
    denied = api_call(
        api.checklist_item_dismiss,
        "post",
        user=FakeUser(),
        role="billing_clerk",
        tenant=tenant,
        item="numbering_documents",
    )
    assert denied.status_code == 403
    assert denied.data["code"] == "AUTH-002"


def test_us_ten_003_tc5__checklist_state_is_per_tenant(growth_plan, identity_seam):
    brazos, _ = provisioned_tenant()
    lonestar, _ = provisioned_tenant(lonestarridge_payload())
    with tenant_ctx(brazos):
        services.mark_checklist_item(admin_actor(), "numbering_documents")
    with tenant_ctx(lonestar):
        result = selectors.checklist()
    assert _items(result)["numbering_documents"]["done"] is False  # marks invisible
    # (RLS FORCE half of this TC = G5 isolation suite on live Postgres)
