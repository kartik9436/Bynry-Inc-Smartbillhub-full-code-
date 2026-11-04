# ── Trace ──────────────────────────────────────────────
# Story:    US-IDN-010 — configure tenant security policy (EP-IDN-04, S8)
# Rules:    BR-IDN-006/016/019/020/025/026/028
# Tests:    per-TC below; TC-9's RLS half = G5 suite. TC-10 (View audit log →
#           S61) is audit-module navigation — no identity backend half.
# ───────────────────────────────────────────────────────
"""US-IDN-010 TCs: policy save + enforcement wiring.

E2 note (reported, not resolved): the 11b §2.3 row says the self-lockout
guard answers "422 BIZ-STATE"; the B12 §3 catalog (core.errors) maps
BIZ-STATE → 409 — the catalog wins here, asserted as 409."""

import pytest
from django.test import Client

from apps.identity.models import SecurityPolicy
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
    api_post,
    api_put,
    api_sign_in,
    idn,
    signed_in_client,
)

pytestmark = pytest.mark.django_db

SEED_DEFAULTS = {
    "pw_min_length": 8,
    "pw_require_mixed": True,
    "pw_require_symbol": False,
    "pw_expiry_days": None,
    "session_timeout_minutes": 60,
    # `CR-145-BRC08` — the five new settings, each at the value that was a
    # platform constant until 2026-09-28 (ruling 3: nothing moves on the day it
    # ships). This dict held six keys until the backend lane's first run, and
    # the case below went red on the five it did not name — correctly.
    "absolute_session_hours": 12,
    "keep_signed_in_offered": True,
    "keep_signed_in_days": 30,
    "lockout_max_failed": 5,
    "lockout_minutes": 15,
    "ip_allowlist": [],
    # PO 2026-10-21 — the field app's capture life: 168 hours = BR-WRK-060's 7 days.
    "field_capture_hours": 168,
    "password_link_valid_days": 7,  # CR-188-BRC10 (PO 2026-10-22) — seeded at BR-IDN-025's 7
}

#: The settings whose allowed values the read serves under `limits`. Typed out
#: here rather than read off `services.SETTING_LIMITS`, because a check that
#: reads the table it checks moves with it and can never see a key go missing.
LIMITED_SETTINGS = {
    "session_timeout_minutes",
    "absolute_session_hours",
    "keep_signed_in_offered",
    "keep_signed_in_days",
    "lockout_max_failed",
    "lockout_minutes",
    # DEF-IDN-7501 — the two password dropdowns, so the tab keeps no copy.
    "pw_min_length",
    "pw_expiry_days",
    # PO 2026-10-21, *"this should come from settings"* — the field app's
    # capture life, in hours (seeded 168).
    "field_capture_hours",
    "password_link_valid_days",  # CR-188-BRC10
}


def test_us_idn_010_tc1__stricter_policy_governs_the_next_password_change(idn):
    idn.seed_silvercreek()
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    response = api_put(
        alex,
        "/settings/security-policy",
        {"pw_min_length": 10, "pw_require_symbol": True},
    )
    assert response.status_code == 200
    policy = SecurityPolicy.objects.get(tenant=idn.silvercreek)
    assert (policy.pw_min_length, policy.pw_require_symbol) == (10, True)
    (row,) = idn.rows_for("settings.security_updated")
    assert row["before"] == {"pw_min_length": 8, "pw_require_symbol": False}
    assert row["after"] == {"pw_min_length": 10, "pw_require_symbol": True}
    priya = signed_in_client("priya@silvercreek.example", "Meadow2026sage")
    rejected = api_post(
        priya,
        "/me/password",
        {
            "current_password": "Meadow2026sage",
            "new_password": "Prairie2026wind",  # 15 chars but no symbol
            "confirm_password": "Prairie2026wind",
        },
    )
    assert rejected.status_code == 422
    accepted = api_post(
        priya,
        "/me/password",
        {
            "current_password": "Meadow2026sage",
            "new_password": "Prairie-2026-wind",
            "confirm_password": "Prairie-2026-wind",
        },
    )
    assert accepted.status_code == 204


def test_us_idn_010_tc2__seed_defaults_render_before_any_edit(idn):
    idn.seed_silvercreek()
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    response = api_get(alex, "/settings/security-policy")
    assert response.status_code == 200
    body = response.json()
    # `limits` rides beside the values (CR-145-BRC08) and is not a value.
    limits = body.pop("limits")
    assert set(limits) == LIMITED_SETTINGS
    # So does the PLATFORM's flag (CR-195-BRC10) — not a utility's setting.
    assert body.pop("field_app_pinning_enabled") is False
    assert body == SEED_DEFAULTS  # BR-IDN-025/026 confirmed seed
    # No 2FA-requirement section exists anywhere (BR-IDN-028).
    assert not any("2fa" in key.lower() or "two_factor" in key.lower() for key in body)


def test_us_idn_010_tc3__timeout_change_adopted_by_existing_sessions(idn):
    idn.seed_silvercreek()
    priya = signed_in_client("priya@silvercreek.example", "Meadow2026sage")
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    assert (
        api_put(alex, "/settings/security-policy", {"session_timeout_minutes": 30}).status_code
        == 200
    )
    # Existing session adopts the new idle window on its next request.
    idn.clock.advance(minutes=29)
    assert api_get(priya, "/me").status_code == 200
    idn.clock.advance(minutes=31)
    assert api_get(priya, "/me").status_code == 401


def test_us_idn_010_tc4__invalid_cidr_rejected_nothing_saved(idn):
    idn.seed_silvercreek()
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    response = api_put(
        alex,
        "/settings/security-policy",
        {"ip_allowlist": ["203.0.113.0/33", "banana"]},
    )
    assert response.status_code == 422
    assert len(response.json()["field_errors"]) == 2  # both bad values named
    assert not SecurityPolicy.objects.filter(tenant=idn.silvercreek).exists()


def test_us_idn_010_tc5__self_lockout_guard_blocks_the_save(idn):
    idn.seed_silvercreek()
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids", ip="203.0.113.7")
    response = api_put(
        alex,
        "/settings/security-policy",
        {"ip_allowlist": ["198.51.100.0/24"]},  # excludes the admin's own IP
        ip="203.0.113.7",
    )
    assert response.status_code == 409  # catalog BIZ-STATE (11b said 422 — E2 reported)
    body = response.json()
    assert body["br_ref"] == "BR-IDN-020"
    assert body["params"]["ip"] == "203.0.113.7"
    assert not SecurityPolicy.objects.filter(tenant=idn.silvercreek).exists()


def test_us_idn_010_tc6__allowlist_enforced_at_sign_in(idn):
    idn.seed_silvercreek()
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids", ip="203.0.113.7")
    assert (
        api_put(
            alex,
            "/settings/security-policy",
            {"ip_allowlist": ["203.0.113.0/24"]},
            ip="203.0.113.7",
        ).status_code
        == 200
    )
    outside = api_sign_in(Client(), "priya@silvercreek.example", "Meadow2026sage", ip="192.0.2.44")
    assert outside.status_code == 403  # generic denial; attempt logged (BR-AUD-018)
    assert outside.json()["message_key"] == "errors.auth.sign_in_failed"
    inside = api_sign_in(Client(), "priya@silvercreek.example", "Meadow2026sage", ip="203.0.113.50")
    assert inside.status_code == 201


def test_us_idn_010_tc7__executive_reads_but_cannot_save(idn):
    idn.seed_silvercreek()
    diana = signed_in_client("diana@silvercreek.example", "Vista2026peak")
    assert api_get(diana, "/settings/security-policy").status_code == 200  # A4: View
    response = api_put(diana, "/settings/security-policy", {"pw_min_length": 12})
    assert response.status_code == 403


def test_us_idn_010_tc8__billing_clerk_gets_403(idn):
    idn.seed_silvercreek()
    priya = signed_in_client("priya@silvercreek.example", "Meadow2026sage")
    assert api_get(priya, "/settings/security-policy").status_code == 403  # A4: —


def test_us_idn_010_tc9__policies_are_per_tenant(idn):
    # App-filter half; RLS half = G5 suite.
    idn.seed_silvercreek()
    idn.seed_bluemesa_admin()
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    assert api_put(alex, "/settings/security-policy", {"pw_min_length": 12}).status_code == 200
    jordan = signed_in_client("jordan@bluemesa.example", "Mesa2026bluff", tenant=BM)
    bm_policy = api_get(jordan, "/settings/security-policy", tenant=BM).json()
    assert bm_policy["pw_min_length"] == 8  # Blue Mesa unchanged
    # A Blue Mesa forced change validates against Blue Mesa's OWN policy: an
    # 8-char mixed password passes there though Silver Creek now requires 12.
    temp = api_post(
        jordan,
        "/users",
        {"full_name": "Nina Frost", "email": "nina@bluemesa.example", "role": "billing_clerk"},
        tenant=BM,
    ).json()["temp_password"]
    nina = signed_in_client("nina@bluemesa.example", temp, tenant=BM)
    assert (
        api_post(
            nina,
            "/me/password",
            {"new_password": "Mesa2026n", "confirm_password": "Mesa2026n"},
            tenant=BM,
        ).status_code
        == 204
    )


@pytest.mark.isolation
@requires_postgres
def test_us_idn_010_tc9_rls__policy_rows_invisible_cross_tenant(idn, rls):
    """US-IDN-010 TC-9, RLS half — one tenant cannot read or relax another's policy.

    `security_policies` is the row that decides password strength, session
    timeout and IP allow-listing. A tenant that could see (worse, weaken) a
    neighbour's row would own the neighbour, so both directions are asserted:
    invisible under the other's context, and unwritable into it.
    """
    idn.seed_silvercreek()
    idn.seed_bluemesa_admin()
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    assert api_put(alex, "/settings/security-policy", {"pw_min_length": 12}).status_code == 200
    jordan = signed_in_client("jordan@bluemesa.example", "Mesa2026bluff", tenant=BM)
    assert (
        api_put(
            jordan, "/settings/security-policy", {"session_timeout_minutes": 30}, tenant=BM
        ).status_code
        == 200
    )

    # Each row is read UNDER ITS OWN TENANT's context. A `.get(tenant=…)` with
    # no `app.tenant_id` set now matches zero rows — the RLS policy denies by
    # default (hard rule 1) — so the filter argument alone is not enough on a
    # connection row-level security actually applies to.
    with live_tenant_context(idn.silvercreek.id):
        sc_policy = SecurityPolicy.objects.get(tenant=idn.silvercreek)
    with live_tenant_context(idn.bluemesa.id):
        bm_policy = SecurityPolicy.objects.get(tenant=idn.bluemesa)
    assert_rls_scoped(
        rls,
        "security_policies",
        owner=idn.silvercreek,
        intruder=idn.bluemesa,
        owner_ids={str(sc_policy.id)},
    )
    with live_tenant_context(idn.bluemesa.id):
        assert rls.ids("security_policies") == {str(bm_policy.id)}
        # The attack this guards: weaken the neighbour's password floor.
        assert (
            rls.affected(
                "UPDATE security_policies SET pw_min_length = 4 WHERE id = %s",
                [str(sc_policy.id)],
            )
            == 0
        )
    with live_tenant_context(idn.silvercreek.id):
        sc_policy.refresh_from_db()
    assert sc_policy.pw_min_length == 12  # untouched
    assert_write_into_other_tenant_refused(
        rls, "security_policies", owner=idn.silvercreek, intruder=idn.bluemesa
    )
    assert_denied_without_context(rls, "security_policies")


@pytest.mark.skip(
    reason="TC-10 (View audit log → S61) is navigation into the audit module's "
    "viewer — no identity backend half exists to test"
)
def test_us_idn_010_tc10__view_audit_log_navigates_to_s61():
    raise NotImplementedError
