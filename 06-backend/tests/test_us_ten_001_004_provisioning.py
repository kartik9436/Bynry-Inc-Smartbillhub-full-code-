# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-001 (idempotent tenant provisioning at S114 commit) ·
#           US-TEN-004 (failure handling, retry, conflict paths)
# Rules:    BR-TEN-001 · BR-TEN-003 · BR-TEN-010 · BR-TEN-011 · BR-TEN-013 ·
#           BR-TEN-014 · BR-TEN-016
# Journeys: J1 step 2 (tenant + owner membership + trial exist, atomic)
# Note:     owner-user rows are created through the DOCUMENTED identity seam
#           (apps/tenancy/seams.py); the stub here proves tenancy's half, and
#           the seam-integration TCs below run against the REAL identity
#           functions (wired 2026-08-09 — skip-until-wired lifted).
#           TCs needing live RLS carry honest G5 skips (sqlite cannot RLS).
# ───────────────────────────────────────────────────────
"""US-TEN-001 / US-TEN-004 — provisioning transaction, idempotency, failures."""

import uuid
from datetime import timedelta

import pytest

import apps.identity.services as identity_services
from apps.tenancy import api, models
from apps.tenancy import selectors as tenancy_selectors
from apps.tenancy import services
from core import errors

from tests.isolation_helpers import (  # noqa: F401 — fixtures used by name
    assert_denied_without_context,
    assert_no_foreign_rows_anywhere,
    assert_rls_scoped,
    assert_write_into_other_tenant_refused,
    live_tenant_context,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (
    api_call,
    audit_actions,
    brazosbend_payload,
    lonestarridge_payload,
    provisioned_tenant,
)

pytestmark = pytest.mark.django_db


# ── US-TEN-001 ──────────────────────────────────────────────────────────────
def test_us_ten_001_tc1__commit_creates_tenant_trial_services_audit(
    growth_plan, identity_seam, audit_rows
):
    tenant, result = provisioned_tenant()
    assert result["created"] is True
    assert tenant.subdomain == "brazosbend"
    assert tenant.provisioned_at is not None
    # owner via the identity seam, System Admin membership is identity's half
    assert identity_seam.provisioned[0]["email"] == "dana@brazosbendutilities.com"
    assert identity_seam.provisioned[0]["tenant_id"] == tenant.id
    # BR-TEN-014: trial subscription, +14 days, no payment method involved
    subscription = models.Subscription.objects.get(tenant=tenant)
    assert subscription.status == "trial"
    assert subscription.trial_ends_at == tenant.provisioned_at + timedelta(days=14)
    # exactly 2 tenant_services rows (Electric + Water)
    codes = set(
        models.TenantService.objects.filter(tenant=tenant, enabled=True).values_list(
            "service__code", flat=True
        )
    )
    assert codes == {"electric", "water"}
    assert "tenant.provisioned" in audit_actions(audit_rows)  # BR-TEN-016


def test_us_ten_001_tc2__replay_returns_same_tenant_no_duplicates(
    growth_plan, identity_seam, audit_rows
):
    tenant, first = provisioned_tenant()
    counts = (
        models.Tenant.objects.count(),
        models.Subscription.objects.count(),
        models.TenantService.objects.count(),
        models.Uom.objects.count(),
    )
    replay = services.provision_tenant(brazosbend_payload())
    assert replay["created"] is False
    assert replay["id"] == first["id"]  # SAME tenant id
    assert (
        models.Tenant.objects.count(),
        models.Subscription.objects.count(),
        models.TenantService.objects.count(),
        models.Uom.objects.count(),
    ) == counts  # row counts unchanged (BR-TEN-010)


def test_us_ten_001_tc3__subdomain_taken_by_other_owner_is_409_nothing_written(
    growth_plan, identity_seam
):
    provisioned_tenant()
    before = models.Tenant.objects.count()
    with pytest.raises(errors.BizError) as excinfo:
        services.provision_tenant(lonestarridge_payload(subdomain="brazosbend"))
    assert excinfo.value.code == errors.BIZ_STATE
    assert excinfo.value.http_status == 409
    assert excinfo.value.br_ref == "BR-TEN-011"
    assert models.Tenant.objects.count() == before  # no rows written


@pytest.mark.parametrize(
    "bad,problem",
    [
        ("-brazos_bend!", "charset"),
        ("api", "reserved"),
        ("ab", "length"),
        ("-brazosbend", "edge_hyphen"),
    ],
)
def test_us_ten_001_tc4__bad_or_reserved_subdomain_is_422_naming_rule(
    growth_plan, identity_seam, bad, problem
):
    with pytest.raises(errors.ValidationError) as excinfo:
        services.provision_tenant(brazosbend_payload(subdomain=bad))
    assert excinfo.value.http_status == 422
    field_errors = {fe["field"]: fe for fe in excinfo.value.field_errors}
    assert field_errors["subdomain"]["params"]["problem"] == problem
    assert models.Tenant.objects.count() == 0  # nothing created


@pytest.mark.isolation
@requires_postgres
def test_us_ten_001_tc5__rls_isolation_lone_star_sees_zero_brazos_rows(
    growth_plan, identity_seam, rls
):
    """US-TEN-001 TC-5 — two provisioned tenants, zero reachable rows between them.

    Provisioning is the moment a tenant's whole W0 footprint is written at once
    (subscription, services, UoMs, settings, number series, seed run). Under
    Lone Star's `app.tenant_id` the database must not surface ONE of Brazos
    Bend's rows on ANY of those tables — asserted under the non-superuser probe
    role, so the policies are genuinely consulted (isolation_helpers docstring).
    """
    brazos, _ = provisioned_tenant(brazosbend_payload())
    lonestar, _ = provisioned_tenant(lonestarridge_payload())

    # The tables provisioning actually fills, so the sweep cannot be vacuous.
    written = {
        "subscriptions": models.Subscription,
        "tenant_services": models.TenantService,
        "uoms": models.Uom,
        "tenant_settings": models.TenantSettings,
        "reference_seed_runs": models.ReferenceSeedRun,
    }
    # ⚠ THE "SOMETHING WAS PROVISIONED" CHECK READS UNDER BRAZOS BEND'S OWN
    # CONTEXT. Contextless it returns False on a connection RLS applies to —
    # deny-by-default — and this guard would then report *"nothing
    # provisioned"* about a tenant that was provisioned perfectly. That is the
    # vacuity this line exists to prevent, arriving through the check itself.
    for table, model in written.items():
        with live_tenant_context(brazos.id):
            assert model.objects.filter(tenant=brazos).exists(), f"{table}: nothing provisioned"
        assert_rls_scoped(rls, table, owner=brazos, intruder=lonestar)

    # Deny-by-default over the same set, and no leak in the other direction.
    assert_denied_without_context(rls, *written)
    assert_no_foreign_rows_anywhere(rls, lonestar, written)

    # Lone Star cannot write itself into Brazos either (policy WITH CHECK).
    assert_write_into_other_tenant_refused(rls, "uoms", owner=lonestar, intruder=brazos)

    # The app-layer half stays asserted next to it: same answer, two mechanisms.
    # (Note the shape — the app filter lives in the SELECTORS, so that is what is
    # called here. A bare `Model.objects.filter(tenant=brazos)` would still find
    # Brazos rows, because the app's own DB role is a superuser and bypasses RLS;
    # that gap is exactly what the probe role above closes.)
    with live_tenant_context(lonestar.id):
        enabled = {
            row["service"] for row in tenancy_selectors.services_overview() if row["enabled"]
        }
        assert enabled == {"water"}  # Brazos Bend's Electric row is not Lone Star's
        assert tenancy_selectors.regional_settings()["currency"] == "USD"
        assert tenancy_selectors.number_series_overview()  # its own series, not Brazos's


# ── US-TEN-004 ──────────────────────────────────────────────────────────────
def test_us_ten_004_tc1__mid_transaction_crash_leaves_nothing_retry_succeeds(
    growth_plan, identity_seam, audit_rows, monkeypatch
):
    # fault injection: identity seam blows up AFTER the tenants insert
    def exploding_owner(**kwargs):
        raise RuntimeError("identity store crashed mid-provisioning")

    monkeypatch.setattr(identity_services, "provision_owner", exploding_owner, raising=False)
    with pytest.raises(RuntimeError):
        services.provision_tenant(brazosbend_payload())
    # BR-TEN-001: rollback, not cleanup — zero rows for that subdomain anywhere
    assert models.Tenant.objects.filter(subdomain="brazosbend").count() == 0
    assert models.Uom.objects.count() == 0
    assert models.Subscription.objects.count() == 0
    # BR-TEN-016: failure trace, no PII (subdomain + error class only)
    failed = [row for row in audit_rows if row["action"] == "tenant.provision_failed"]
    assert len(failed) == 1
    assert failed[0]["after"] == {"subdomain": "brazosbend", "error": "RuntimeError"}
    assert "dana" not in str(failed[0]).lower()  # no owner PII in the trace

    # retry from S114 succeeds fully with no manual cleanup
    monkeypatch.setattr(
        identity_services, "provision_owner", identity_seam.provision_owner, raising=False
    )
    tenant, result = provisioned_tenant()
    assert result["created"] is True
    # EVERY catalogue row since 2026-08-18 (PO New mandate 4, 2026-08-17: "we
    # will provdie full list for all services … more is better ; less is
    # contraint") — the two signup picks enabled, the rest present-but-off.
    #
    # ⚠ **ELEVEN SINCE `CR-063` (2026-09-02), AND THE COUNT IS DERIVED FROM THE
    # CATALOGUE RATHER THAN RETYPED.** What this case asserts is that a tenant
    # gets a row for EVERY service and not only the ones it ticked — the number
    # is scaffolding, and a twelfth service must not break it. Reading the
    # `services` table is also stricter than a literal: it fails if the seed and
    # the catalogue disagree, which a typed 11 could never see.
    assert (
        models.TenantService.objects.filter(tenant=tenant).count()
        == models.Service.objects.filter(active=True).count()
    )
    assert models.TenantService.objects.filter(tenant=tenant, enabled=True).count() == 2


def test_us_ten_004_tc2__commit_time_subdomain_race_loser_gets_409(
    growth_plan, identity_seam, monkeypatch
):
    provisioned_tenant()  # winner committed first

    # Simulate the same-second race: the loser's pre-check ran BEFORE the
    # winner's commit (sees nothing), so its INSERT hits the UNIQUE constraint.
    class _NothingFound:
        def first(self):
            return None

    original_filter = models.Tenant.objects.filter
    monkeypatch.setattr(models.Tenant.objects, "filter", lambda *a, **k: _NothingFound())
    with pytest.raises(errors.BizError) as excinfo:
        services.provision_tenant(lonestarridge_payload(subdomain="brazosbend"))
    assert excinfo.value.code == errors.BIZ_STATE
    assert excinfo.value.br_ref == "BR-TEN-011"
    monkeypatch.setattr(models.Tenant.objects, "filter", original_filter)
    assert models.Tenant.objects.filter(subdomain="brazosbend").count() == 1  # exactly one


def test_us_ten_004_tc3__owner_email_existing_on_other_tenant_still_provisions(
    growth_plan, identity_seam
):
    lonestar, _ = provisioned_tenant(
        lonestarridge_payload(
            owner={
                "full_name": "Dana Whitfield",
                "email": "dana@brazosbendutilities.com",  # Dana is a clerk there first
                "password": "LSR!passw0rd",
                "phone": None,
            }
        )
    )
    brazos, result = provisioned_tenant()
    assert result["created"] is True  # BR-IDN-029: two tenants, two separate users
    seam_tenants = [call["tenant_id"] for call in identity_seam.provisioned]
    assert seam_tenants == [lonestar.id, brazos.id]  # one owner-user call per tenant
    assert models.Tenant.objects.count() == 2


def test_us_ten_004_tc4__replay_after_success_is_idempotent_200_not_email_error(
    growth_plan, identity_seam
):
    _, first = provisioned_tenant()
    replay = services.provision_tenant(brazosbend_payload())
    assert replay["created"] is False and replay["id"] == first["id"]


@pytest.mark.isolation
@requires_postgres
def test_us_ten_004_tc5__no_orphan_rows_visible_cross_tenant(
    growth_plan, identity_seam, monkeypatch, rls
):
    """US-TEN-004 TC-5 — a crashed provisioning leaves nothing for anyone to see.

    BR-TEN-001 is rollback, not cleanup. The failure mode this guards is the
    nasty one: a half-written tenant whose orphan rows stay reachable, and then
    surface inside the NEXT tenant's lists. Two proofs, because either alone is
    weak — the app filter finds nothing, AND the database exposes nothing under
    the survivor's `app.tenant_id`.
    """

    def exploding_owner(**kwargs):
        raise RuntimeError("identity store crashed mid-provisioning")

    monkeypatch.setattr(identity_services, "provision_owner", exploding_owner, raising=False)
    with pytest.raises(RuntimeError):
        services.provision_tenant(brazosbend_payload())
    monkeypatch.setattr(
        identity_services, "provision_owner", identity_seam.provision_owner, raising=False
    )

    # The survivor provisions cleanly afterwards (no manual cleanup, BR-TEN-001).
    lonestar, result = provisioned_tenant(lonestarridge_payload())
    assert result["created"] is True

    swept = (
        "subscriptions",
        "tenant_services",
        "uoms",
        "tenant_settings",
        "reference_seed_runs",
        "number_series",
        "holiday_calendars",
        "user_preferences",
        "jobs",
        # `bell_events` was swept here until 2026-09-03 and the table is gone
        # (DEF-3422): it had no writer, no reader and no caller, so the bell's
        # one store is `outbound_messages` + `in_app_messages`.
        "users",
        "tenant_memberships",
    )
    # Not one row on any W0 tenant table belongs to anyone but Lone Star …
    assert_no_foreign_rows_anywhere(rls, lonestar, swept)
    # … and the crashed tenant's subdomain never became a tenant row at all.
    assert models.Tenant.objects.filter(subdomain="brazosbend").count() == 0
    with live_tenant_context(lonestar.id):
        assert models.Uom.objects.exclude(tenant=lonestar).count() == 0
        assert models.Subscription.objects.count() == 1
    # And with no context at all the orphans would still be unreachable.
    assert_denied_without_context(rls, *swept)


# ── identity-seam integration (UNSKIPPED 2026-08-09: the wiring lane authored
#    apps.identity.services.provision_owner/owner_email_for — the documented
#    seam in apps/tenancy/seams.py is live; no stub fixture here on purpose) ──
def test_us_ten_001_seam__provisioning_through_real_identity_service(growth_plan):
    from apps.identity.models import Session, TenantMembership
    from apps.identity.models import User as IdentityUser

    tenant, result = provisioned_tenant()
    owner = IdentityUser.objects.get(tenant_id=tenant.id, email="dana@brazosbendutilities.com")
    assert result["owner_user_id"] == str(owner.id)
    membership = TenantMembership.objects.get(tenant_id=tenant.id, user=owner)
    assert membership.role.code == "system_admin"  # A4: owner role
    assert membership.status == "active"  # active immediately — no temp-password flow
    assert owner.must_change_password is False  # signup owners set their OWN password
    assert owner.password_hash and "S3cure!passw0rd" not in owner.password_hash  # never raw
    # US-TEN-001 §6 "the owner is signed in", now actually deliverable (PO
    # ruling 2026-08-10 supersedes BR-TEN-045): exactly one live session, bound
    # to THIS tenant, and its id is what the endpoint puts in the cookie.
    session = Session.objects.get(user=owner, tenant_id=tenant.id, revoked_at__isnull=True)
    assert result["owner_session_id"] == str(session.id)
    assert session.persistent is False  # keep-me-signed-in is an explicit choice


def test_us_ten_001_seam__a_replay_is_never_signed_in(growth_plan):
    """BR-TEN-010 replay matches on subdomain + owner email and checks NO
    password. Handing it a session would turn a public slug plus a guessable
    owner address into a login — so the replay path issues none, and no second
    session appears for the owner either."""
    from apps.identity.models import Session
    from apps.identity.models import User as IdentityUser

    tenant, first = provisioned_tenant()
    owner = IdentityUser.objects.get(tenant_id=tenant.id)
    replay = services.provision_tenant(
        brazosbend_payload(
            owner={
                **brazosbend_payload()["owner"],
                "password": "completely-wrong-password",
            }
        )
    )
    assert replay["created"] is False
    assert replay["owner_session_id"] is None
    assert Session.objects.filter(user=owner, revoked_at__isnull=True).count() == 1


def test_us_ten_001_seam__replay_and_conflict_through_real_owner_email_check(growth_plan):
    tenant, first = provisioned_tenant()
    # BR-TEN-010 replay: same subdomain + same owner email → the SAME tenant,
    # decided by the REAL apps.identity.services.owner_email_for.
    replay = services.provision_tenant(brazosbend_payload())
    assert replay["created"] is False
    assert replay["id"] == first["id"]
    from apps.identity.models import User as IdentityUser

    assert IdentityUser.objects.filter(tenant_id=tenant.id).count() == 1  # no second owner
    # Different owner email on the same subdomain stays a lawful 409.
    with pytest.raises(errors.BizError) as excinfo:
        services.provision_tenant(lonestarridge_payload(subdomain="brazosbend"))
    assert excinfo.value.br_ref == "BR-TEN-011"


# ── API half (11b §2.1: POST /tenants · GET /public/*) ──────────────────────
def test_us_ten_001_tc1_api__post_tenants_201_location_then_200_replay(growth_plan, identity_seam):
    response = api_call(api.tenants, "post", "/tenants", data=brazosbend_payload())
    assert response.status_code == 201
    assert response["Location"].endswith(response.data["id"])
    replay = api_call(api.tenants, "post", "/tenants", data=brazosbend_payload())
    assert replay.status_code == 200
    assert replay.data["id"] == response.data["id"]


def test_us_ten_001_tc1_api__the_owner_comes_back_signed_in(growth_plan, identity_seam):
    """PO ruling 2026-08-10 — path tenancy OBSOLETES BR-TEN-045's success-screen
    handoff. One origin, so the session opened at commit rides home as the
    ordinary httpOnly cookie and the SPA goes straight to /{subdomain} → S62."""
    response = api_call(api.tenants, "post", "/api/tenants", data=brazosbend_payload())
    assert response.status_code == 201
    assert response.data["signed_in"] is True

    cookie = response.cookies["sbh_session"]
    assert cookie.value == identity_seam.sessions[0]["session_id"]
    assert cookie["httponly"] is True  # the SPA must never read it
    assert cookie["samesite"] == "Lax"
    # …and the credential is ONLY in the cookie: a session id in the JSON body
    # would land in the SPA's memory, its logs and its error reports.
    assert "owner_session_id" not in response.data
    assert identity_seam.sessions[0]["tenant_id"] == uuid.UUID(response.data["id"])


def test_us_ten_001_tc1_api__a_replay_gets_no_cookie(growth_plan, identity_seam):
    api_call(api.tenants, "post", "/api/tenants", data=brazosbend_payload())
    replay = api_call(api.tenants, "post", "/api/tenants", data=brazosbend_payload())
    assert replay.status_code == 200
    assert replay.data["signed_in"] is False
    assert "sbh_session" not in replay.cookies
    assert len(identity_seam.sessions) == 1  # the first commit's, and only that one


def test_us_ten_001_tc4__every_route_shadowing_name_is_reserved(growth_plan, identity_seam):
    """PO ruling 2026-08-10: the slug is a URL path segment now, so the
    reserved list has to cover ROUTES as well as hostnames. A tenant named
    `api` would shadow the whole API surface; one named `jobs` or `exports`
    would be unreachable at its own endpoints forever."""
    for name in (
        "api",
        "signup",
        "signin",
        "pricing",
        "static",
        "assets",
        "public",
        "jobs",
        "exports",
        "health",
        "tenants",
    ):
        assert tenancy_selectors.subdomain_problem(name) == "reserved", name
        assert tenancy_selectors.subdomain_availability(name) == {
            "subdomain": name,
            "available": False,
            "problem": "reserved",
        }
        with pytest.raises(errors.ValidationError):
            services.provision_tenant(brazosbend_payload(subdomain=name))
    assert models.Tenant.objects.count() == 0  # not one of them got through


def test_us_ten_001_tc1_api__a_fresh_database_completes_a_signup_end_to_end(db):
    """09-infra/02 §10.3 — the last hard deploy blocker, as a test.

    Everything else in this file hands the service a plan the `growth_plan`
    fixture minted first. That is what let a green suite sit on top of a broken
    deployment: nothing seeded `subscription_plans`, so on a freshly migrated
    production database `_validate_signup` found no plan, appended
    `signup.plan_unknown`, and EVERY signup failed — while
    `GET /api/public/pricing-plans` returned `[]` next door.

    So this test takes no fixtures but `db` (a migrated database and nothing
    more), calls the real URL over HTTP through the middleware, and lets the
    REAL identity seam create the owner. If tenancy migration 0005 stops
    seeding the catalog, this is the test that goes red — and it fails the same
    way the deployment did, with `signup.plan_unknown`."""
    from django.test import Client

    from apps.identity.models import Session
    from apps.identity.models import User as IdentityUser

    catalog = Client().get("/api/public/pricing-plans")
    assert catalog.status_code == 200
    assert [row["code"] for row in catalog.json()] == ["starter", "growth", "scale"]

    response = Client().post(
        "/api/tenants", data=brazosbend_payload(), content_type="application/json"
    )
    assert response.status_code == 201, response.content  # not 422 signup.plan_unknown
    body = response.json()
    tenant = models.Tenant.objects.get(pk=uuid.UUID(body["id"]))
    assert models.Subscription.objects.get(tenant=tenant).plan.code == "growth"
    # …and the owner really landed signed in on the same origin (PO 2026-08-10).
    assert body["signed_in"] is True
    owner = IdentityUser.objects.get(tenant_id=tenant.id)
    assert response.cookies["sbh_session"].value == str(
        Session.objects.get(user=owner, tenant_id=tenant.id, revoked_at__isnull=True).id
    )


def test_us_ten_001_tc3_api__conflict_renders_409_envelope(growth_plan, identity_seam):
    api_call(api.tenants, "post", "/tenants", data=brazosbend_payload())
    response = api_call(
        api.tenants,
        "post",
        "/tenants",
        data=lonestarridge_payload(subdomain="brazosbend"),
    )
    assert response.status_code == 409
    assert response.data["code"] == "BIZ-STATE"
    assert response.data["br_ref"] == "BR-TEN-011"
    assert response.data["trace_id"]


def test_us_ten_004_api__live_subdomain_check_is_advisory(growth_plan, identity_seam):
    free = api_call(api.subdomain_check, "get", query={"subdomain": "brazosbend"})
    assert free.data == {"subdomain": "brazosbend", "available": True, "problem": None}
    provisioned_tenant()
    taken = api_call(api.subdomain_check, "get", query={"subdomain": "brazosbend"})
    assert taken.data["available"] is False and taken.data["problem"] == "taken"
    reserved = api_call(api.subdomain_check, "get", query={"subdomain": "api"})
    assert reserved.data["problem"] == "reserved"


def test_us_ten_001_api__public_pricing_plans_with_etag_304(db):
    """S1/S112 read the WHOLE ratified catalog, not whatever a fixture minted.

    AMENDED 2026-08-10 (deploy-blocker lane, 09-infra/02 §10.3): the plans are
    seeded by tenancy migration 0005, so this asserts all three SKUs at their
    ratified prices (A10 "Real business constants" · A13 addendum 2026-08-07 ·
    A1 §S112) in the order `selectors.pricing_plans()` sorts them (price, code).
    The `growth_plan` fixture is deliberately NOT requested — an empty catalog
    must fail here, which is exactly what a fresh deployment had."""
    response = api_call(api.pricing_plans, "get")
    assert response.status_code == 200
    assert [(row["code"], row["price_month"]) for row in response.data] == [
        # NUMERIC(18,6), rendered as a string — never a float (CLAUDE.md rule 2)
        ("starter", "1000.000000"),
        ("growth", "5000.000000"),
        ("scale", "8000.000000"),
    ]
    assert [(row["min_accounts"], row["max_accounts"]) for row in response.data] == [
        (0, 300),  # "up to 300" — advisory only (BR-TEN-002)
        (300, 1000),
        (1000, 3000),
    ]
    assert {row["currency"] for row in response.data} == {"USD"}
    tag = response["ETag"]
    cached = api_call(api.pricing_plans, "get", headers={"If-None-Match": tag})
    assert cached.status_code == 304


# ── Default timezone from the signup state (PO ruling 2026-08-10) ────────────
# "on this screen you have to give default time zones" — provisioning used to
# leave tenant_settings.timezone NULL, so a brand-new utility opened Settings →
# Regional to an empty field, every date rendered in UTC, and the live preview
# read "not set". The state is already collected at signup.


def test_us_ten_001_tc_default_timezone__unambiguous_state_is_prefilled(db):
    from apps.tenancy.services import default_timezone_for_state

    assert default_timezone_for_state("CA") == "America/Los_Angeles"
    assert default_timezone_for_state("NY") == "America/New_York"
    assert default_timezone_for_state("AZ") == "America/Phoenix"  # no DST
    assert default_timezone_for_state("HI") == "Pacific/Honolulu"
    assert default_timezone_for_state("PR") == "America/Puerto_Rico"


def test_us_ten_001_tc_default_timezone__case_and_whitespace_tolerated(db):
    from apps.tenancy.services import default_timezone_for_state

    assert default_timezone_for_state(" tn ") == "America/Chicago"
    assert default_timezone_for_state("Tn") == "America/Chicago"


def test_us_ten_001_tc_default_timezone__unknown_state_stays_unset(db):
    """An unset zone the user must choose beats a wrong zone nobody noticed."""
    from apps.tenancy.services import default_timezone_for_state

    assert default_timezone_for_state(None) is None
    assert default_timezone_for_state("") is None
    assert default_timezone_for_state("ZZ") is None


def test_us_ten_001_tc_default_timezone__every_state_maps_into_the_s8_zone_list(db):
    """A default the S8 type-ahead cannot display is worse than no default:
    the field would show a value its own dropdown does not contain."""
    from apps.tenancy.services import US_STATE_TIMEZONES

    s8_zones = {
        "America/New_York",
        "America/Chicago",
        "America/Denver",
        "America/Phoenix",
        "America/Los_Angeles",
        "America/Anchorage",
        "Pacific/Honolulu",
        "America/Puerto_Rico",
    }
    assert set(US_STATE_TIMEZONES.values()) <= s8_zones
    assert len(US_STATE_TIMEZONES) == 52  # 50 states + DC + PR


def test_us_ten_001_tc_default_timezone__split_zone_states_are_declared_not_hidden(db):
    """Thirteen states span two zones. The map picks the more populous one as a
    DEFAULT; this pins the list so nobody later mistakes it for a determination."""
    from apps.tenancy.services import SPLIT_ZONE_STATES, US_STATE_TIMEZONES

    assert SPLIT_ZONE_STATES == {
        "AK",
        "FL",
        "ID",
        "IN",
        "KS",
        "KY",
        "MI",
        "ND",
        "NE",
        "OR",
        "SD",
        "TN",
        "TX",
    }
    assert SPLIT_ZONE_STATES <= set(US_STATE_TIMEZONES)


def test_us_ten_001_tc_more_date_formats__seven_offered(db):
    """PO 2026-08-10: "more date formats", then "we also need DD-MMM-YY".

    This test was written asserting SIX and all-numeric, and failed the moment
    the seventh landed — correctly. Six are numeric; the seventh carries a month
    NAME, which is only safe because Intl produces it in the app's current
    language rather than a catalogue that would go stale on the twelfth locale.
    """
    from apps.tenancy.services import DATE_FORMATS

    numeric = {"MM/DD/YYYY", "DD/MM/YYYY", "YYYY-MM-DD", "DD.MM.YYYY", "DD-MM-YYYY", "YYYY/MM/DD"}
    assert set(DATE_FORMATS) == numeric | {"DD-MMM-YY"}
    # The six stay free of any letter that is not a date placeholder…
    for fmt in numeric:
        assert not any(c.isalpha() and c not in "DMY" for c in fmt)
    # …and exactly one format asks for a month name.
    assert [f for f in DATE_FORMATS if "MMM" in f] == ["DD-MMM-YY"]
