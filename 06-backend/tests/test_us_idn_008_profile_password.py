# ── Trace ──────────────────────────────────────────────
# Story:    US-IDN-008 — my profile & change password (EP-IDN-03, S48)
# Rules:    BR-IDN-015/016/021/027 (+ BR-IDN-017 v1 email path, BR-IDN-029)
# Tests:    per-TC below. TC-2 carries an E2 CONTRADICTION (reported, not
#           resolved): the story has Priya changing her OWN email via /me, but
#           BR-IDN-017 + flows §8 + the PO-RATIFIED 11b §2.2 row say email
#           change is SysAdmin-only via the users endpoint in v1 — the
#           ratified row is implemented; both halves are asserted below.
# ───────────────────────────────────────────────────────
"""US-IDN-008 TCs: self-service profile + password change."""

import pytest
from django.test import Client

from core.audit import REFUSAL_ATTEMPT_ACTION
from tests.test_us_idn_helpers import (  # noqa: F401 (fixture import)
    BM,
    api_get,
    api_patch,
    api_post,
    api_sign_in,
    idn,
    live_sessions_for,
    signed_in_client,
)

pytestmark = pytest.mark.django_db


def test_us_idn_008_tc1__own_name_and_phone_update_audited(idn):
    users = idn.seed_silvercreek()
    priya = signed_in_client("priya@silvercreek.example", "Meadow2026sage")
    response = api_patch(
        priya, "/me", {"full_name": "Priya Menon-Rao", "phone": "+1 (512) 555-0139"}
    )
    assert response.status_code == 200
    users.priya.refresh_from_db()
    assert users.priya.full_name == "Priya Menon-Rao"
    assert users.priya.phone == "+1 (512) 555-0139"
    (row,) = idn.rows_for("user.profile_updated")
    assert row["before"]["full_name"] == "Priya Menon"
    # New name visible in the S8 user list (server half).
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    names = [r["name"] for r in api_get(alex, "/users").json()["results"]]
    assert "Priya Menon-Rao" in names


def test_us_idn_008_tc2__email_change_is_admin_endpoint_in_v1_e2_reported(idn):
    users = idn.seed_silvercreek()
    # Self-service half (the story's expectation): REFUSED per the ratified
    # 11b row — E2 contradiction reported to the PO batch, not resolved here.
    priya = signed_in_client("priya@silvercreek.example", "Meadow2026sage")
    refused = api_patch(priya, "/me", {"email": "priya.menon@silvercreek.example"})
    assert refused.status_code == 403
    assert refused.json()["br_ref"] == "BR-IDN-017"
    # Admin path (BR-IDN-017 v1): uniqueness checked, atomic, audited,
    # NO verification email exists to send (BR-IDN-027/021).
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    changed = api_patch(
        alex, f"/users/{users.priya.id}", {"email": "priya.menon@silvercreek.example"}
    )
    assert changed.status_code == 200
    (row,) = idn.rows_for("user.email_changed")
    assert row["before"]["email"] == "p***@silvercreek.example"  # masked PII
    # Her next sign-in uses the new address only.
    assert api_sign_in(Client(), "priya@silvercreek.example", "Meadow2026sage").status_code == 401
    assert (
        api_sign_in(Client(), "priya.menon@silvercreek.example", "Meadow2026sage").status_code
        == 201
    )


def test_us_idn_008_tc3__wrong_current_password_changes_nothing(idn):
    users = idn.seed_silvercreek()
    other = signed_in_client("priya@silvercreek.example", "Meadow2026sage")
    priya = signed_in_client("priya@silvercreek.example", "Meadow2026sage")
    response = api_post(
        priya,
        "/me/password",
        {
            "current_password": "wrong-password",
            "new_password": "Prairie2026wind",
            "confirm_password": "Prairie2026wind",
        },
    )
    assert response.status_code == 422
    assert response.json()["message_key"] == "errors.identity.current_password_incorrect"
    assert live_sessions_for(users.priya) == 2  # no session revoked
    assert api_sign_in(Client(), "priya@silvercreek.example", "Meadow2026sage").status_code == 201
    assert api_get(other, "/me").status_code == 200


def test_us_idn_008_tc4__policy_violating_new_password_rejected(idn):
    idn.seed_silvercreek()
    priya = signed_in_client("priya@silvercreek.example", "Meadow2026sage")
    response = api_post(
        priya,
        "/me/password",
        {
            "current_password": "Meadow2026sage",
            "new_password": "creekside",
            "confirm_password": "creekside",
        },
    )
    assert response.status_code == 422
    assert {e["field"] for e in response.json()["field_errors"]} == {"new_password"}
    assert api_sign_in(Client(), "priya@silvercreek.example", "Meadow2026sage").status_code == 201


def test_us_idn_008_tc5__confirm_mismatch_rejected(idn):
    idn.seed_silvercreek()
    priya = signed_in_client("priya@silvercreek.example", "Meadow2026sage")
    response = api_post(
        priya,
        "/me/password",
        {
            "current_password": "Meadow2026sage",
            "new_password": "Prairie2026wind",
            "confirm_password": "Prairie2026wine",
        },
    )
    assert response.status_code == 422
    assert response.json()["message_key"] == "errors.identity.password_confirm_mismatch"
    assert api_sign_in(Client(), "priya@silvercreek.example", "Meadow2026sage").status_code == 201


def test_us_idn_008_tc6__sign_out_other_sessions_keeps_only_current(idn):
    users = idn.seed_silvercreek()
    desktop = signed_in_client("priya@silvercreek.example", "Meadow2026sage")
    laptop = signed_in_client("priya@silvercreek.example", "Meadow2026sage")
    tablet = signed_in_client("priya@silvercreek.example", "Meadow2026sage")
    response = api_post(
        desktop,
        "/me/password",
        {
            "current_password": "Meadow2026sage",
            "new_password": "Prairie2026wind",
            "confirm_password": "Prairie2026wind",
            "sign_out_other_sessions": True,  # the default
        },
    )
    assert response.status_code == 204
    assert live_sessions_for(users.priya) == 1  # the 2 others revoked
    assert api_get(laptop, "/me").status_code == 401
    assert api_get(tablet, "/me").status_code == 401
    assert api_get(desktop, "/me").status_code == 200  # current survives
    assert len(idn.rows_for("auth.password_changed")) == 1


def test_us_idn_008_tc7__role_in_profile_payload_denied_and_audited(idn):
    users = idn.seed_silvercreek()
    priya = signed_in_client("priya@silvercreek.example", "Meadow2026sage")
    response = api_patch(priya, "/me", {"role": "System Admin"})
    assert response.status_code == 403  # privilege-escalation guard (BR-IDN-027)
    users.priya_m.refresh_from_db()
    assert users.priya_m.role.code == "billing_clerk"
    attempts = idn.rows_for(REFUSAL_ATTEMPT_ACTION)
    assert attempts and attempts[-1]["after"]["br_ref"] == "BR-IDN-027"


def test_us_idn_008_tc8__role_shown_is_current_tenant_membership_only(idn):
    idn.seed_silvercreek()
    idn.make_user(idn.silvercreek, "marcus.webb@example.com", "Marcus Webb", password="Web2026sc")
    idn.make_user(
        idn.bluemesa,
        "marcus.webb@example.com",
        "Marcus Webb",
        password="Web2026bm",
        role="system_admin",
    )
    marcus_sc = signed_in_client("marcus.webb@example.com", "Web2026sc")
    body = api_get(marcus_sc, "/me").json()
    assert body["role"] == "billing_clerk"  # nothing reveals the Blue Mesa role


def test_us_idn_008_tc9__email_uniqueness_is_per_tenant(idn):
    users = idn.seed_silvercreek()
    idn.seed_bluemesa_admin()  # jordan@bluemesa.example exists at BLUE MESA
    idn.make_user(  # ... and, for the in-tenant half, also at Silver Creek
        idn.silvercreek, "taken@silvercreek.example", "Taken Person", password="Tkn2026pass"
    )
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    # In-tenant collision → rejected (BR-IDN-029).
    conflict = api_patch(alex, f"/users/{users.priya.id}", {"email": "taken@silvercreek.example"})
    assert conflict.status_code == 409
    assert conflict.json()["br_ref"] == "BR-IDN-029"
    # The same email existing in a DIFFERENT tenant is NOT a conflict.
    allowed = api_patch(alex, f"/users/{users.priya.id}", {"email": "jordan@bluemesa.example"})
    assert allowed.status_code == 200


# ── GET /me/permissions (PO directive 2026-08-09 — "create endpoints for all
# and integrate"). Not a §3 TC of the story: the endpoint post-dates it, so the
# numbering continues this file's sequence and each test says what it proves.
def test_us_idn_008_tc10__a_clerk_reads_only_their_own_permission_row(idn):
    """The gap this closes: /roles is System-Admin-only, so a Billing Clerk had
    to probe each Settings tab and read the 403 to learn what she may reach.
    She now reads HER row — and only hers (BR-IDN-014's grid, one column)."""
    idn.seed_silvercreek()
    priya = signed_in_client("priya@silvercreek.example", "Meadow2026sage")
    response = api_get(priya, "/me/permissions")
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "billing_clerk"
    assert body["role_name"]  # the catalog's display name, not a code echo
    access = {row["code"]: row["access"] for row in body["permissions"]}
    # Verbatim from the signed A4 addendum grid — the Clerk column, all 9 rows.
    assert access == {
        "settings_lookups": "—",
        "user_management": "—",
        "plans_rates": "View",
        "premises_accounts": "Full",
        "reads_billing_runs": "Full",
        "payments_record": "Full",
        "adjustment_approval": "Request",
        "finance_reconcile_export": "—",
        "reports": "Run",
    }
    # No other role's cells, and no role catalog, are reachable from here.
    serialized = response.content.decode()
    assert "system_admin" not in serialized and "executive" not in serialized
    assert "cells" not in body["permissions"][0]
    # ETag/304 like the other reference reads (11b G6).
    etag = response["ETag"]
    assert api_get(priya, "/me/permissions", HTTP_IF_NONE_MATCH=etag).status_code == 304


def test_us_idn_008_tc11__every_role_reads_its_own_row_from_the_same_source(idn):
    """One transcription of A4 (BR-IDN-014): each role's /me/permissions row
    equals its own column of the /roles grid, cell for cell."""
    idn.seed_silvercreek()
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    grid = api_get(alex, "/roles").json()
    cells_by_permission = {row["code"]: row["cells"] for row in grid["permissions"]}
    for email, password, role in (
        ("alex@silvercreek.example", "Canyon2026rapids", "system_admin"),
        ("priya@silvercreek.example", "Meadow2026sage", "billing_clerk"),
        ("diana@silvercreek.example", "Vista2026peak", "executive"),
    ):
        body = api_get(signed_in_client(email, password), "/me/permissions").json()
        assert body["role"] == role
        assert {row["code"]: row["access"] for row in body["permissions"]} == {
            code: cells[role] for code, cells in cells_by_permission.items()
        }


def test_us_idn_008_tc12__permission_set_is_session_derived_and_tenant_scoped(idn):
    """The role comes from the membership of the PATH-resolved tenant (PO ruling
    2026-08-10; was the subdomain) — never client input — and an unauthenticated
    caller gets nothing (G18)."""
    idn.seed_silvercreek()
    idn.seed_bluemesa_admin()
    assert api_get(Client(), "/me/permissions", tenant=BM).status_code == 401
    jordan = signed_in_client("jordan@bluemesa.example", "Mesa2026bluff", tenant=BM)
    body = api_get(jordan, "/me/permissions", tenant=BM).json()
    assert body["role"] == "system_admin"  # HIS tenant's membership
    # A forged role claim changes nothing — the payload is server-derived.
    forged = api_get(jordan, "/me/permissions?role=executive", tenant=BM).json()
    assert forged["role"] == "system_admin"
    # ... and it carries no cross-tenant data at all (no ids, no tenant names).
    assert set(body) == {"role", "role_name", "permissions"}
