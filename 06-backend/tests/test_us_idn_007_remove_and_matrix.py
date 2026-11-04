# ── Trace ──────────────────────────────────────────────
# Story:    US-IDN-007 — remove a user · read-only roles & permissions matrix
#           (EP-IDN-02, S8; remove REWORKED to BR-IDN-030, PO 2026-08-09)
# Rules:    BR-IDN-008/009/013/014 · BR-IDN-030 (remove = PERMANENT deactivation,
#           email retained, add → 409 pointing to Reactivate — supersedes the
#           BR-IDN-012 delete-membership/audit-lock remove; tension reported)
# Tests:    per-TC below; TC-6's RLS half = G5 suite
# ───────────────────────────────────────────────────────
"""US-IDN-007 TCs as reworked by BR-IDN-030: remove = permanent deactivation
(row, email, and history kept), and the A4 matrix served verbatim from the
platform catalog + signed grid."""

import uuid

import pytest
from django.test import Client

from apps.audit.models import AuditLog
from apps.identity.models import (
    A4_MATRIX,
    WORK_ACCEPT,
    RolePermission,
    TenantMembership,
    User,
)
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
    api_delete,
    api_get,
    api_patch,
    api_post,
    api_sign_in,
    idn,
    signed_in_client,
)

pytestmark = pytest.mark.django_db


def test_us_idn_007_tc1__remove_deactivates_permanently_row_and_email_kept(idn):
    users = idn.seed_silvercreek()
    idn.make_user(  # the "same" email exists at Blue Mesa — a different user
        idn.bluemesa,
        "marcus@silvercreek.example",
        "Marcus Webb",
        password="Mesa2026webb",
        role="system_admin",
    )
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    response = api_delete(alex, f"/users/{users.marcus.id}")
    assert response.status_code == 204
    # BR-IDN-030: NOTHING is deleted — the membership row stays, deactivated.
    users.marcus_m.refresh_from_db()
    assert users.marcus_m.status == "deactivated"
    users.marcus.refresh_from_db()  # user row + email stay exactly as they are
    assert users.marcus.email == "marcus@silvercreek.example"
    assert users.marcus.password_hash is not None  # kept as-is (reactivation path)
    # Sign-in is dead all the same — the deactivated membership refuses it.
    assert api_sign_in(Client(), "marcus@silvercreek.example", "Temp-Mrcs-2026").status_code == 401
    assert User.objects.filter(tenant=idn.bluemesa, email="marcus@silvercreek.example").exists()
    (row,) = idn.rows_for("user.removed")
    assert row["actor_user_id"] == users.alex.id
    assert row["after"]["status"] == "deactivated"


def test_us_idn_007_tc2__remove_referenced_member_keeps_history_intact(idn):
    # BR-IDN-030 rework: removal deletes nothing, so the old BR-IDN-012
    # reference-count audit-lock no longer blocks — the referenced member is
    # permanently deactivated with every history row still attached by name.
    users = idn.seed_silvercreek()
    for _ in range(3):  # Priya's activity trail
        AuditLog.objects.create(
            tenant_id=idn.silvercreek.id,
            actor_user_id=users.priya.id,
            action="reads.imported",
            entity_type="meter_read",
            entity_id=uuid.uuid4(),
        )
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    response = api_delete(alex, f"/users/{users.priya.id}")
    assert response.status_code == 204
    users.priya_m.refresh_from_db()
    assert users.priya_m.status == "deactivated"  # row kept — permanent deactivation
    # Her audit history is intact and still names her user id.
    assert AuditLog.objects.filter(actor_user_id=users.priya.id).count() == 3
    users.priya.refresh_from_db()
    assert users.priya.full_name == "Priya Menon"  # name intact on all history


def test_us_idn_007_br030__removed_email_not_freed_reactivate_is_the_way_back(idn):
    users = idn.seed_silvercreek()
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    assert api_delete(alex, f"/users/{users.priya.id}").status_code == 204
    # The email is NOT freed for re-use: add answers 409 pointing to Reactivate.
    denied = api_post(
        alex,
        "/users",
        {"full_name": "Priya Menon", "email": "priya@silvercreek.example", "role": "billing_clerk"},
    )
    assert denied.status_code == 409
    body = denied.json()
    assert body["code"] == "BIZ-STATE"
    assert body["br_ref"] == "BR-IDN-030"
    assert body["message_key"] == "errors.identity.email_deactivated_reactivate"
    assert body["params"]["user_id"] == str(users.priya.id)
    assert (
        User.objects.filter(
            tenant=idn.silvercreek, email__iexact="priya@silvercreek.example"
        ).count()
        == 1
    )
    # The returning person is REACTIVATED (existing row), never re-added.
    reactivated = api_post(alex, f"/users/{users.priya.id}/reactivate")
    assert reactivated.status_code == 200
    assert reactivated.json()["user"]["status"] == "active"
    assert api_sign_in(Client(), "priya@silvercreek.example", "Meadow2026sage").status_code == 201


def test_us_idn_007_tc3__matrix_matches_the_a4_addendum_grid(idn):
    """⚠ **AMENDED 2026-09-05 (CR-070 wave F). THREE ROLES BECAME FOUR AND NINE
    PERMISSIONS BECAME TEN, AND ONLY ONE OF THOSE TWO CHANGES IS VISIBLE HERE.**

    `OQ-WRK-1494`, ruled 2026-09-04, adds the `field_technician` role — a login
    that opens the phone and not the web app. It appears in `/roles` because
    that endpoint enumerates the platform catalogue, and every one of the nine
    signed rows renders **"—"** for it, which is *"holds no staff permission"*
    stated by the product rather than by a comment. That is asserted below.

    `OQ-WRK-1492`, ruled the same day, adds the `work_accept` permission held
    by the three office roles. It is deliberately NOT an A4 row and therefore
    NOT one of the nine here: `A4_MATRIX` transcribes a SIGNED grid verbatim
    (`BR-IDN-014`) and a tenth row would make the transcription untrue. So the
    count below stays **9**, and the `seeded == expected` check at the end now
    subtracts the permissions declared outside the grid before comparing —
    otherwise it would fail on a real grant that is correct.
    """
    idn.seed_silvercreek()
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    response = api_get(alex, "/roles")
    assert response.status_code == 200
    body = response.json()
    assert [role["code"] for role in body["roles"]] == [
        "system_admin",
        "billing_clerk",
        "executive",
        "field_technician",
    ]
    assert len(body["permissions"]) == 9  # exactly the A4 rows — work_accept is not one
    by_code = {row["code"]: row["cells"] for row in body["permissions"]}
    assert by_code["user_management"] == {
        "system_admin": "Full",
        "billing_clerk": "—",
        "executive": "—",
    }
    assert by_code["adjustment_approval"] == {
        "system_admin": "Approve",
        "billing_clerk": "Request",
        "executive": "Approve",
    }
    # ⚠ `US-WRK-023` TC-4's other half, asserted from the matrix rather than
    # from a comment: the Field technician holds NOTHING. Nine rows, nine
    # dashes. The day somebody grants that role a staff permission by accident,
    # this line is what says so.
    assert {row["cells"]["field_technician"] for row in body["permissions"]} == {"—"}
    # ETag/304 (11b G6): a conditional re-read answers 304.
    etag = response["ETag"]
    assert api_get(alex, "/roles", HTTP_IF_NONE_MATCH=etag).status_code == 304
    # Catalog consistency: the seeded role_permissions memberships equal the
    # non-"—" cells of the signed A4 grid (cell VALUES stay code-side — the
    # no-B2-column gap is reported, not invented).
    #
    # ⚠ **`work_accept` IS SUBTRACTED, NOT IGNORED** — it is asserted on its own
    # two lines below, so a grant that goes missing still turns this red.
    seeded = set(RolePermission.objects.values_list("permission__code", "role__code"))
    expected = {(code, role) for code, _label, cells in A4_MATRIX for role in cells}
    assert {pair for pair in seeded if pair[0] != WORK_ACCEPT} == expected
    # `OQ-WRK-1492`: the three OFFICE roles hold it and the Field technician
    # does not — *"clark can do it sicne it s a day to day work"*.
    assert {role for code, role in seeded if code == WORK_ACCEPT} == {
        "system_admin",
        "billing_clerk",
        "executive",
    }


def test_us_idn_007_tc4__catalog_writes_have_no_route(idn):
    idn.seed_silvercreek()
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    response = api_patch(alex, "/roles", {"name": "Renamed"})
    assert response.status_code == 405  # no tenant-facing mutation endpoint exists


def test_us_idn_007_tc5__last_active_system_admin_cannot_remove_self(idn):
    users = idn.seed_silvercreek()
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    response = api_delete(alex, f"/users/{users.alex.id}")
    assert response.status_code == 409
    assert response.json()["br_ref"] == "BR-IDN-013"
    assert TenantMembership.objects.filter(user=users.alex).exists()


def test_us_idn_007_tc6__cross_tenant_remove_returns_404_row_survives(idn):
    # App-filter half; RLS half = G5 suite.
    users = idn.seed_silvercreek()
    idn.seed_bluemesa_admin()
    jordan = signed_in_client("jordan@bluemesa.example", "Mesa2026bluff", tenant=BM)
    response = api_delete(jordan, f"/users/{users.marcus.id}", tenant=BM)
    assert response.status_code == 404
    assert TenantMembership.objects.filter(user=users.marcus).exists()  # survives


@pytest.mark.isolation
@requires_postgres
def test_us_idn_007_tc6_rls__cross_tenant_remove_invisible(idn, rls):
    """US-IDN-007 TC-6, RLS half — a cross-tenant remove deletes nothing.

    Remove is the most destructive verb identity owns, so the database gets
    asserted directly: under Blue Mesa's `app.tenant_id` a raw DELETE aimed at
    Marcus's Silver Creek membership matches zero rows, and both his membership
    and his user row survive intact.
    """
    users = idn.seed_silvercreek()
    idn.seed_bluemesa_admin()

    assert_rls_scoped(
        rls,
        "tenant_memberships",
        owner=idn.silvercreek,
        intruder=idn.bluemesa,
        owner_ids={str(users.marcus_m.id)},
    )
    with live_tenant_context(idn.bluemesa.id):
        assert rls.count("tenant_memberships", "id = %s", [str(users.marcus_m.id)]) == 0
        assert (
            rls.affected("DELETE FROM tenant_memberships WHERE id = %s", [str(users.marcus_m.id)])
            == 0
        )
        assert rls.affected("DELETE FROM users WHERE id = %s", [str(users.marcus.id)]) == 0
    # Both survival checks read AS SILVER CREEK. Contextless they would be
    # empty querysets on a connection RLS applies to, which would assert the
    # rows were DESTROYED when in fact they were merely invisible.
    with live_tenant_context(idn.silvercreek.id):
        assert TenantMembership.objects.filter(pk=users.marcus_m.id).exists()  # survives
        assert User.objects.filter(pk=users.marcus.id).exists()  # BR-IDN-030: email retained
    assert_denied_without_context(rls, "tenant_memberships", "users")
