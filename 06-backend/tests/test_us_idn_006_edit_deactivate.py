# ── Trace ──────────────────────────────────────────────
# Story:    US-IDN-006 — edit role · deactivate · reactivate (EP-IDN-02, S8)
# Rules:    BR-IDN-008/009/012/013
# Tests:    per-TC below; TC-7's RLS half = G5 suite
# ───────────────────────────────────────────────────────
"""US-IDN-006 TCs: role changes apply on the very next request; deactivation
kills sessions at once; the last active System Admin is untouchable."""

import pytest
from django.test import Client

from apps.identity.models import Role, TenantMembership
from core.audit import REFUSAL_ATTEMPT_ACTION
from tests.isolation_helpers import (  # noqa: F401 (fixture import)
    assert_denied_without_context,
    assert_rls_scoped,
    assert_write_into_other_tenant_refused,
    live_tenant_context,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_idn_helpers import (  # noqa: F401 (fixture import)
    BM,
    api_get,
    api_patch,
    api_post,
    api_sign_in,
    idn,
    signed_in_client,
)

pytestmark = pytest.mark.django_db


def test_us_idn_006_tc1__role_change_applies_on_the_very_next_request(idn):
    users = idn.seed_silvercreek()
    priya = signed_in_client("priya@silvercreek.example", "Meadow2026sage")
    # As Billing Clerk, the Security tab read is denied (A4 Settings: Clerk —).
    assert api_get(priya, "/settings/security-policy").status_code == 403
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    response = api_patch(alex, f"/users/{users.priya.id}", {"role": "executive"})
    assert response.status_code == 200
    assert response.json()["user"]["role"] == "executive"
    # Very next request carries Executive permissions — no re-login.
    assert api_get(priya, "/settings/security-policy").status_code == 200
    (row,) = idn.rows_for("user.role_changed")
    assert row["before"] == {"role": "billing_clerk"}
    assert row["after"] == {"role": "executive"}


def test_us_idn_006_tc2__deactivate_revokes_sessions_at_once(idn):
    users = idn.seed_silvercreek()
    desktop = signed_in_client("priya@silvercreek.example", "Meadow2026sage")
    laptop = signed_in_client("priya@silvercreek.example", "Meadow2026sage")
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    response = api_post(alex, f"/users/{users.priya.id}/deactivate")
    assert response.status_code == 200
    assert response.json()["user"]["status"] == "deactivated"
    assert api_get(desktop, "/me").status_code == 401  # in-flight request dies
    assert api_get(laptop, "/me").status_code == 401
    denied = api_sign_in(Client(), "priya@silvercreek.example", "Meadow2026sage")
    assert denied.status_code == 401  # US-IDN-001 TC-4 behavior
    assert len(idn.rows_for("user.deactivated")) == 1


def test_us_idn_006_tc3__reactivate_restores_existing_password(idn):
    users = idn.seed_silvercreek()
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    response = api_post(alex, f"/users/{users.carla.id}/reactivate")
    assert response.status_code == 200
    assert response.json()["user"]["status"] == "active"
    assert api_sign_in(Client(), "carla@silvercreek.example", "River2026stone").status_code == 201
    assert len(idn.rows_for("user.reactivated")) == 1


def test_us_idn_006_tc4__last_active_system_admin_cannot_be_demoted(idn):
    users = idn.seed_silvercreek()  # Alex is the only active System Admin
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    response = api_patch(alex, f"/users/{users.alex.id}", {"role": "billing_clerk"})
    assert response.status_code == 409
    body = response.json()
    assert body["message_key"] == "errors.identity.last_system_admin"
    assert body["br_ref"] == "BR-IDN-013"
    users.alex_m.refresh_from_db()
    assert users.alex_m.role.code == "system_admin"


def test_us_idn_006_tc5__last_active_system_admin_cannot_be_deactivated(idn):
    users = idn.seed_silvercreek()
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    response = api_post(alex, f"/users/{users.alex.id}/deactivate")
    assert response.status_code == 409
    assert response.json()["message_key"] == "errors.identity.last_system_admin"
    users.alex_m.refresh_from_db()
    assert users.alex_m.status == "active"


def test_us_idn_006_tc6__clerk_role_change_denied_and_attempt_audited(idn):
    users = idn.seed_silvercreek()
    priya = signed_in_client("priya@silvercreek.example", "Meadow2026sage")
    response = api_patch(priya, f"/users/{users.priya.id}", {"role": "system_admin"})
    assert response.status_code == 403  # server-side (BR-IDN-009)
    users.priya_m.refresh_from_db()
    assert users.priya_m.role.code == "billing_clerk"
    # BR-AUD-018 attempt row, written centrally by the BE-02 handler.
    attempts = idn.rows_for(REFUSAL_ATTEMPT_ACTION)
    assert attempts and attempts[-1]["after"]["code"] == "AUTH-002"


def test_us_idn_006_tc7__cross_tenant_edit_returns_404_and_changes_nothing(idn):
    # App-filter half; RLS half = G5 suite.
    users = idn.seed_silvercreek()
    idn.seed_bluemesa_admin()
    jordan = signed_in_client("jordan@bluemesa.example", "Mesa2026bluff", tenant=BM)
    response = api_patch(jordan, f"/users/{users.priya.id}", {"role": "executive"}, tenant=BM)
    assert response.status_code == 404
    users.priya_m.refresh_from_db()
    assert users.priya_m.role.code == "billing_clerk"


@pytest.mark.isolation
@requires_postgres
def test_us_idn_006_tc7_rls__cross_tenant_membership_invisible(idn, rls):
    """US-IDN-006 TC-7, RLS half — the cross-tenant edit has nothing to edit.

    A role change is an UPDATE on `tenant_memberships`. Under Blue Mesa's
    `app.tenant_id` that UPDATE matches ZERO rows — not because the service
    checked, but because the policy's USING clause never offers the row. Priya
    keeps her role even if every app-layer guard above it were removed.
    """
    users = idn.seed_silvercreek()
    idn.seed_bluemesa_admin()

    assert_rls_scoped(
        rls,
        "tenant_memberships",
        owner=idn.silvercreek,
        intruder=idn.bluemesa,
        owner_ids={str(users.priya_m.id)},
    )
    executive_role_id = str(Role.objects.get(code="executive").id)
    with live_tenant_context(idn.bluemesa.id):
        assert rls.count("tenant_memberships", "id = %s", [str(users.priya_m.id)]) == 0
        assert (
            rls.affected(
                "UPDATE tenant_memberships SET role_id = %s WHERE id = %s",
                [executive_role_id, str(users.priya_m.id)],
            )
            == 0
        )
        # Deactivation is the other half of this story's write surface.
        assert (
            rls.affected(
                "UPDATE tenant_memberships SET status = 'deactivated' WHERE id = %s",
                [str(users.priya_m.id)],
            )
            == 0
        )
    # Re-read AS SILVER CREEK: the membership is its row, and with the GUC
    # cleared the policy matches nothing, so `refresh_from_db` raises
    # `DoesNotExist` — deny-by-default, not a deleted row.
    with live_tenant_context(idn.silvercreek.id):
        users.priya_m.refresh_from_db()
    assert users.priya_m.role.code == "billing_clerk"
    assert users.priya_m.status == TenantMembership.STATUS_ACTIVE
    assert_write_into_other_tenant_refused(
        rls, "tenant_memberships", owner=idn.silvercreek, intruder=idn.bluemesa
    )
    assert_denied_without_context(rls, "tenant_memberships")


def test_us_idn_006_tc8__deactivation_is_per_tenant_only(idn):
    # r11 per-tenant identity: the "same" person at two tenants is two user
    # rows — deactivating the Silver Creek one leaves Blue Mesa untouched.
    idn.seed_silvercreek()
    idn.seed_bluemesa_admin()
    sc_marcus, _sc_m = idn.make_user(
        idn.silvercreek, "marcus.webb@example.com", "Marcus Webb (SC)", password="Web2026sc"
    )
    idn.make_user(
        idn.bluemesa,
        "marcus.webb@example.com",
        "Marcus Webb (BM)",
        password="Web2026bm",
        role="system_admin",
    )
    bm_session = signed_in_client("marcus.webb@example.com", "Web2026bm", tenant=BM)
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    assert api_post(alex, f"/users/{sc_marcus.id}/deactivate").status_code == 200
    # Blue Mesa membership and sessions unaffected.
    assert api_get(bm_session, "/me", tenant=BM).status_code == 200
    assert (
        TenantMembership.objects.get(
            tenant=idn.bluemesa, user__email="marcus.webb@example.com"
        ).status
        == "active"
    )
