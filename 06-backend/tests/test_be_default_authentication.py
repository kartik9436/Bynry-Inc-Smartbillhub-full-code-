# ── Trace ──────────────────────────────────────────────
# Component: the platform-wide DRF authentication default —
#            REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] in
#            config/settings/base.py, reading the identity session through
#            apps/identity/auth.IdentitySessionAuthentication. Deploy defect
#            09-infra/02 §10.14 ("most tenant endpoints do not accept the
#            session cookie").
# Rules:     BR-IDN-006 (one tenant per session; foreign path ⇒ 404) ·
#            BR-IDN-009 / BR-SHL-025 (the SERVER enforces the role, every call) ·
#            BR-TEN-003 / HR-1 (cross-tenant is 404, never 403) ·
#            11b G12/G18 (the public surface is throttled and named)
# Tests:     this file · the cross-tenant half is
#            tests/test_path_tenancy_session_binding.py · BE-04's own matrix is
#            tests/test_be04_permissions.py
# Impacts:   every endpoint in the product, present and future
# ───────────────────────────────────────────────────────
"""One authenticator for the whole product, and proof it opened nothing.

Until 2026-08-10 `authentication_classes = [IdentitySessionAuthentication]` was
something each view had to remember. Identity and audit remembered; tenancy
remembered on three platform paths; rating, metering and assets never declared
it at all. DRF therefore fell back to its OWN defaults on those views —
SessionAuthentication + BasicAuthentication, neither of which has ever heard of
the identity `sessions` table — so a signed-in browser got **401 from most of
the product**: Settings, Lookups, Plans & Rates, Premises, Units, Routes,
Cycles, Assets and the S62 checklist (09-infra/02 §10.14 lists them).

The fix is the default, not seventy declarations: a per-view rule that must be
repeated is a per-view rule that will be forgotten by view seventy-one.

Which raises the only question that matters here — does reading the session
GRANT anything? It must not. Authentication says who is calling;
authorisation says what they may do, and that stays with the BE-04 permission
classes and the service-layer @require_role guards. The tests below are
written to catch the failure mode where "now everyone is authenticated"
quietly becomes "now everyone is allowed":

  * a REGISTRY SWEEP over every route Django serves — exactly four are public,
    named one by one; every other route both reads the session AND demands a
    tenant role. A new endpoint that forgets its gate, or a public list that
    grows a fifth member, fails here rather than in production;
  * the public four still answer with no cookie, and still answer with a
    stale one (a signup from a browser that already holds another utility's
    session is the ordinary case, not an edge case);
  * the endpoints that used to 401 everyone now answer their OWN tenant, still
    refuse a foreign one with 404, still refuse the wrong role with 403, and
    still refuse an anonymous caller with 401.
"""

import uuid

import pytest
from django.test import Client
from django.urls import get_resolver
from rest_framework.settings import api_settings

from apps.identity.auth import SESSION_COOKIE, IdentitySessionAuthentication
from apps.identity.native_auth import NativeBearerAuthentication
from core import tenancy as core_tenancy
from core.permissions import ROLES, RoleRequired
from tests.test_us_idn_helpers import (  # noqa: F401 (fixture import)
    BM,
    SC,
    _FakeConnection,
    api_get,
    api_path,
    idn,
    signed_in_client,
)


@pytest.fixture()
def sqlite_tenant_guc(monkeypatch):
    """`app.tenant_id` is a Postgres GUC; sqlite has no `set_config()`, so the
    statements go to a recording fake (the shim every tier in this suite uses).
    Vendor-guarded on purpose — on Postgres the shipping kernel writes the real
    GUC and nothing here may stand in front of it."""
    from django.db import connection as db_connection

    if db_connection.vendor != "postgresql":
        monkeypatch.setattr(core_tenancy, "connection", _FakeConnection())
    yield


#: The complete public surface (11b §2.1 + G18). Anything reachable without a
#: session is on this list, by name, or it is a defect. `auth/session` is the
#: POST half of sign-in — the class carries `authentication_classes = []`
#: because a caller who could already authenticate would not be signing in;
#: its DELETE half authenticates by hand inside the view.
PUBLIC_ROUTES = {
    "api/public/subdomain-check",  # S110 slug availability
    "api/public/pricing-plans",  # S1/S112 catalog
    "api/tenants",  # S114 provisioning — no tenant exists yet
    "api/{tenant}/auth/session",  # S3 sign-in
    # ⚠ **ADDED 2026-09-28 · `CR-145-BRC08`, DELIBERATELY AND NOT BY WIDENING
    # THE ASSERTION** — which is the whole reason this list is exact, and what
    # `DEF-INT-4256` records the cost of skipping.
    #
    # **What it returns: one boolean, `keep_signed_in_offered`.** The PO made
    # *"Keep me signed in"* a per-utility switch, and the SIGN-IN FORM has to
    # know whether to draw the tick box — a form rendered before anybody has a
    # session, so a gated read cannot answer it. Without this the box would be
    # drawn on a utility that switched it off and the person ticking it would
    # be refused with no explanation.
    #
    # **Why it is safe to be world-readable, in three parts:**
    #   * it returns NOTHING ELSE — not the timeouts, not the lockout numbers,
    #     not the password rules. Those would tell a password sprayer how to
    #     pace itself; this one says only whether a checkbox appears;
    #   * it is a fact the utility publishes ANYWAY the moment anybody loads
    #     its sign-in page, because the box is either drawn or it is not;
    #   * it names no tenant it did not already have to name: an unknown
    #     utility gets the DEFAULT answer, never a 404, so it is not an
    #     existence oracle (the same enumeration `BR-IDN-002` closes on the
    #     door beside it).
    #
    # It is throttled like every other public read — `PublicOnboardingThrottle`,
    # asserted below beside the other three.
    "api/{tenant}/auth/sign-in-options",  # CR-145 — is the tick box offered
    # ⚠ **ADDED 2026-10-21 · `CR-187-BRC10`, DELIBERATELY AND NOT BY WIDENING
    # THE ASSERTION.** The native field app's four doors (`07-endpoints.md`
    # N24). Each is public for `auth/session`'s reason — a caller who could
    # already authenticate would not be signing in, refreshing an expired
    # token, or claiming an account — and each is throttled per address
    # (asserted below), on top of the per-login lockout (`auth/token`), the
    # single-use rotation (`refresh`) and the five-wrong-emails burn
    # (`activation/*`). `auth/token`'s DELETE half authenticates by hand with
    # the bearer, as `auth/session`'s DELETE does with the cookie.
    "api/{tenant}/auth/token",  # CR-187 — native sign-in (POST) / sign-out (DELETE)
    "api/{tenant}/auth/token/refresh",  # CR-187 — spend a refresh token once
    "api/{tenant}/auth/activation/check",  # CR-187 — FF-56, code + email
    "api/{tenant}/auth/activation/complete",  # CR-187 — FF-57, own password
    # ⚠ **ADDED 2026-10-24 · `DEF-FLD-10580` (beta MQ-006), DELIBERATELY AND
    # NOT BY WIDENING THE ASSERTION.** PO: *"the code from the office sets the
    # utility"*. A new handset knows only the office's code, so this door has
    # NO utility in its path: a code in, the utility that holds it out, and
    # nothing else. Throttled per address AND per device by a platform-wide
    # limit (asserted below); one refusal for every dead code.
    "api/auth/activation/lookup",  # DEF-FLD-10580 — which utility holds this code
    # ── machines, not people (CR-069) ─────────────────────────────────────
    # ⚠ ADDED 2026-09-06 · DEF-INT-4256. These four are reachable without a
    # session BY DESIGN — a partner or a kiosk presents a key we issued, and a
    # caller who could already authenticate would not be one. They are named
    # here rather than the assertion being widened, which is what
    # `partner_api.py`'s own docstring instructs and what wave S did not do:
    # its three routes were opted out on 2026-09-06 and never listed, and
    # nobody noticed because this test had ALREADY been red since 2026-09-04
    # (54 portal routes carry a third authenticator class the sweep below does
    # not classify, and that assertion fires first). A breach sheltering
    # behind an older breach is DEF-INT-4256; the portal half is NOT fixed
    # here and the row says so.
    "api/{tenant}/v1/payments",  # US-INT-041 — a partner's page of payments
    "api/{tenant}/v1/billing",  # US-INT-041 — a partner's page of bills
    "api/{tenant}/v1/openapi.json",  # US-INT-041 — what the two above will do
    # ⚠ ADDED 2026-09-16 · `CR-110-BRC04` phase 2 waves 0 and 1. The five
    # phase-2 partner addresses, `partner` and never a vendor name (PO
    # 2026-09-16). Every one of them presents a key at `serve.resolve_caller`
    # before it does anything at all — nine checks, one refusal — so being
    # off the default authenticator is what makes the door the door, and it is
    # NAMED here rather than the assertion being widened, exactly as the four
    # rows above it were and for the reason `DEF-INT-4256` records.
    # ── the partner surface ──────────────────────────────────────────────
    # ⚠⚠ **THESE READ `api/{tenant}/partner/v1/…` UNTIL 2026-09-17 AND HAD BEEN
    # WRONG SINCE `DEF-INT-5546` LANDED THE DAY BEFORE (`DEF-INT-5588`).**
    # That defect took the utility OUT of every partner URL — PO 2026-09-16,
    # *"we agreed not to use utility names in partner apis"* — and moved the five
    # routes to `partner_urls.py`, mounted outside the tenant include. This list
    # was not moved with them. Dated from the history rather than assumed:
    # `PUBLIC_ROUTES` last moved in `c2ef372f` (CR-110 phase 2 waves 0–1), and
    # `DEF-INT-5546` landed in `68aadd5d` after it.
    #
    # **WHAT THAT COST, AND IT IS WORSE THAN A RED LINE.** With the spellings
    # wrong, the five real addresses matched nothing here, so
    # `..._every_route_reads_the_session_or_is_named_public` reported them as an
    # unexpected public surface AND `..._grants_nothing_every_private_route_
    # still_gates` reported them as ungated `AllowAny` routes. **Both tests were
    # red, and this file is the one guard that would notice a new world-readable
    # address appearing.** A guard that is red is a guard nobody reads
    # (hard-won law 7).
    #
    # ⚠ **EVERY ADDRESS APPEARS TWICE**, with and without a trailing slash
    # (`CR-111-BRC04`): Invoice Cloud's document writes `/bill-download/` with a
    # slash and the others without, and `APPEND_SLASH` would answer a `301` that
    # a partner's client may not follow and may drop the bearer token on.
    "api/partner/v1/reference",  # every code we emit, with its meaning
    "api/partner/v1/reference/",
    # ⚠ **`DEF-INT-5623` — `accounts` IS THE ADDRESS AND `customers` IS ITS
    # RETIREMENT.** The PO ruled the surface must call an account an account;
    # the old address stays registered and answers `410` naming the new one,
    # because a deleted route and a stolen key are the same `404` here and a
    # partner would read *your key is bad*. Both are added deliberately rather
    # than by widening the assertion, which is what this file exists for.
    "api/partner/v1/accounts",  # phase 2 wave 2
    "api/partner/v1/accounts/",
    "api/partner/v1/customers",  # RETIRED 2026-09-17 -> /partner/v1/accounts
    "api/partner/v1/customers/",
    "api/partner/v1/bills",  # phase 2 wave 3
    "api/partner/v1/bills/",
    "api/partner/v1/payments",  # phase 2 wave 4
    "api/partner/v1/payments/",
    "api/partner/v1/ledger",  # phase 2 wave 5
    "api/partner/v1/ledger/",
    # ⚠ **`CR-111-BRC04` — TWO NEW ADDRESSES, ADDED DELIBERATELY AND NOT BY
    # WIDENING THE ASSERTION.** `partner_api.py`'s own docstring says so in as
    # many words: *"if that test goes red naming this file, the answer is to add
    # these deliberately, never to widen the assertion."*
    "api/partner/v1/consumer-info",  # one account, by number (DEF-INT-5622)
    "api/partner/v1/consumer-info/",
    "api/partner/v1/bill-download",  # one bill, as a PDF
    "api/partner/v1/bill-download/",
    # ⚠ **`CR-132-BRC07` — NEW WORLD / LOGOS, ADDED DELIBERATELY, AND THIS
    # TEST WENT RED NAMING THE FILE FIRST.** That is the mechanism working:
    # the assertion is EXACT, so a ninth partner address cannot arrive without
    # somebody writing this line and saying why. Widening the assertion is what
    # `DEF-INT-4256` records happening the one time it was not done — wave S's
    # three routes were opted out and never listed, and nobody noticed because
    # the test had already been red for two days on an unrelated breach.
    #
    # It presents a key at `serve.resolve_caller` before it does anything at
    # all — nine checks, one refusal, padded to the floor — so being off the
    # default authenticator is what makes the door the door.
    "api/partner/v1/receipts",  # CR-132-BRC07 — our receipts as their XML
    "api/partner/v1/receipts/",
    # ⚠⚠ **2026-09-24 — THE FIRST PARTNER ADDRESS THAT IS NOT A READ, AND THE
    # ONLY WORLD-REACHABLE ROUTE IN THIS PRODUCT THAT CREATES MONEY.** Invoice
    # Cloud POSTs us a payment a customer made on their portal (PO 2026-09-18,
    # *"they post to us daily"*; the whole design walked and confirmed
    # 2026-09-24). **This test went RED naming `partner_api.py` first and the
    # address is written here deliberately, never by widening the assertion** —
    # which is what that file's own docstring instructs and what
    # `DEF-INT-4256` records the cost of skipping.
    #
    # Being off the default authenticator is what makes the door the door: it
    # presents a KEY at `serve.resolve_caller` before the body is touched, and
    # **it is refused unless that key's own scope names `record_payment`** —
    # check 5, in the same bytes and the same padded time an unknown key gets.
    # No key issued before that operation existed holds it, and no ERP key can
    # hold it at all, because only `pay_invoicecloud_partner` declares it.
    "api/partner/v1/make-payment",  # ⚠ POST — money in
    "api/partner/v1/make-payment/",
    # `DEF-INT-10020` (PO 2026-10-07) — US Payments' three calls, moved here
    # from the per-utility inbound address it could never reach. Built from
    # the manifest's `served_path`; the key in the `password` header opens the
    # utility, and `inbound.receive` is the door, unchanged.
    "api/partner/v1/account-lookup",  # GET — what is owed
    "api/partner/v1/account-lookup/",
    "api/partner/v1/add-payment",  # ⚠ POST — money in
    "api/partner/v1/add-payment/",
    "api/partner/v1/add-return",  # ⚠ POST — money reversed
    "api/partner/v1/add-return/",
    # US-INT-044 — the inbound door a payment kiosk POSTs to. Authenticated by
    # `X-Kiosk-Key` + the source allowlist inside the view, before the body is
    # read (BR-INT-021, BR-INT-044).
    "api/{tenant}/integrations/inbound/<str:key>/<str:operation>",
    # CR-198-BRC10 — Twilio's two callbacks (the platform's ONE account).
    # Authenticated by `X-Twilio-Signature` against the address WE published,
    # before anything is looked up (`platform_door.verify`, BR-INT-085).
    "api/{tenant}/integrations/platform/sms_twilio/status",
    "api/hooks/twilio/reply",
}

#: Endpoints §10.14 named as unreachable-with-a-cookie, one per module that
#: declared no authenticator, plus the role each needs.
FORMERLY_401 = [
    ("/settings/company", "system_admin"),  # tenancy
    ("/lookups/uoms", "system_admin"),
    ("/tenants/checklist", "billing_clerk"),
    ("/plans", "billing_clerk"),  # rating
    ("/premises", "billing_clerk"),  # metering
    ("/assets", "billing_clerk"),  # assets
]

CREDENTIALS = {
    "system_admin": ("alex@silvercreek.example", "Canyon2026rapids"),
    "billing_clerk": ("priya@silvercreek.example", "Meadow2026sage"),
    "executive": ("diana@silvercreek.example", "Vista2026peak"),
}


def _routes():
    """(normalised route, view class) for every route Django serves."""

    def walk(resolver, prefix=""):
        for pattern in resolver.url_patterns:
            if hasattr(pattern, "url_patterns"):
                yield from walk(pattern, prefix + str(pattern.pattern))
            else:
                yield prefix + str(pattern.pattern), pattern.callback

    for route, callback in walk(get_resolver()):
        # config/urls.py mounts the tenant-scoped API behind a NON-capturing
        # regex (so no view receives a client-shaped `tenant=` kwarg); read it
        # back as the segment it stands for.
        normalised = route.replace("^api/[-a-zA-Z0-9_]+/", "api/{tenant}/")
        yield normalised, getattr(callback, "cls", None)


# ── the setting itself ──────────────────────────────────────────────────────
def test_be_default_authentication_is_the_identity_session_class():
    assert api_settings.DEFAULT_AUTHENTICATION_CLASSES == [IdentitySessionAuthentication]
    # DRF's own defaults are GONE, deliberately: SessionAuthentication reads
    # django.contrib.auth's request.user (no AuthenticationMiddleware is
    # installed, so it never matched) and BasicAuthentication would accept a
    # password on every single request. Their removal is a narrowing.
    names = {cls.__name__ for cls in api_settings.DEFAULT_AUTHENTICATION_CLASSES}
    assert "BasicAuthentication" not in names and "SessionAuthentication" not in names


def test_be_default_permission_denies_by_default():
    """The other half of "authentication is not authorisation": DRF ships
    AllowAny, so a view that declares an authenticator but forgets a permission
    class would be world-readable. The default is a role gate."""
    assert all(
        issubclass(cls, RoleRequired) for cls in api_settings.DEFAULT_PERMISSION_CLASSES
    ), api_settings.DEFAULT_PERMISSION_CLASSES


# ── the registry sweep ──────────────────────────────────────────────────────
def test_be_default_authentication_every_route_reads_the_session_or_is_named_public():
    reads_session, public, unclassified = set(), set(), []
    for route, view_class in _routes():
        if view_class is None:  # not a DRF view — none exist today
            unclassified.append(route)
            continue
        authenticators = list(view_class.authentication_classes)
        if authenticators == [IdentitySessionAuthentication]:
            reads_session.add(route)
        elif authenticators == [NativeBearerAuthentication, IdentitySessionAuthentication]:
            # `CR-187-BRC10` — the field routes take the native app's bearer
            # IN FRONT OF the cookie; they still read the session. Exactly
            # which routes is `test_cr187_native_auth.py`'s sweep.
            reads_session.add(route)
        elif authenticators == []:
            public.add(route)
        else:
            unclassified.append(f"{route}: {[c.__name__ for c in authenticators]}")

    assert unclassified == []
    assert public == PUBLIC_ROUTES, f"the public surface changed: {public ^ PUBLIC_ROUTES}"
    assert len(reads_session) > 70  # the whole tenant-scoped API, not a sample


def test_be_default_authentication_grants_nothing_every_private_route_still_gates():
    """Reading the cookie must not be the same as being allowed. Every route
    that is not on the public list demands a tenant role — the BE-04 classes,
    never AllowAny and never an empty list."""
    ungated = []
    for route, view_class in _routes():
        if route in PUBLIC_ROUTES:
            continue
        classes = list(view_class.permission_classes)
        # SecurityPolicyView narrows further per method in get_permissions();
        # the class attribute is the floor, and the floor must be a role gate.
        if not classes or not all(
            issubclass(cls, RoleRequired) and cls.allowed_roles <= ROLES and cls.allowed_roles
            for cls in classes
        ):
            ungated.append(f"{route}: {[c.__name__ for c in classes]}")
    assert ungated == []


def test_be_default_authentication_the_public_four_are_throttled():
    """11b G12: unauthenticated does not mean unlimited. The three onboarding
    reads and `CR-145`'s sign-in-options read carry PublicOnboardingThrottle
    (60/min); sign-in's own brute-force protection is BR-IDN-025 account
    lockout, not a rate limit.

    ⚠ The name says *four* and there are now four assertions, which was luck
    the day `CR-145` added one — the list below is the check and this
    docstring is not."""
    by_route = dict(_routes())
    for route in (
        "api/public/subdomain-check",
        "api/public/pricing-plans",
        "api/tenants",
        # `CR-145-BRC08` — the fourth, added with the route above. A public
        # read that is not on this line is a public read nobody throttles.
        "api/{tenant}/auth/sign-in-options",
    ):
        assert [c.__name__ for c in by_route[route].throttle_classes] == [
            "PublicOnboardingThrottle"
        ], route
    # `CR-187-BRC10` — the native app's four public doors, each throttled per
    # address by a subclass of the same throttle (tighter rates, own buckets).
    from apps.tenancy.api import PublicOnboardingThrottle

    for route in (
        "api/{tenant}/auth/token",
        "api/{tenant}/auth/token/refresh",
        "api/{tenant}/auth/activation/check",
        "api/{tenant}/auth/activation/complete",
        "api/auth/activation/lookup",  # DEF-FLD-10580
    ):
        classes = list(by_route[route].throttle_classes)
        assert classes and all(issubclass(c, PublicOnboardingThrottle) for c in classes), route


# ── the public surface still works ──────────────────────────────────────────
@pytest.mark.django_db
def test_be_default_authentication_public_reads_answer_without_a_cookie():
    assert Client().get("/api/public/pricing-plans").status_code == 200
    assert Client().get("/api/public/subdomain-check?subdomain=brazosbend").status_code == 200


@pytest.mark.django_db
def test_be_default_authentication_a_stale_cookie_cannot_break_a_public_call(sqlite_tenant_guc):
    """The failure this opt-out exists to prevent. With the authenticator
    inherited, a browser holding an unknown/expired `sbh_session` would be
    refused 401 by the AUTHENTICATOR before the public view ever ran — and on
    `/api/tenants`, which carries no `/{tenant}/` segment, a VALID cookie would
    have entered the old tenant's context for a transaction whose whole job is
    to create a new one."""
    stale = Client()
    stale_value = str(uuid.uuid4())  # a session that never existed
    stale.cookies[SESSION_COOKIE] = stale_value
    assert stale.get("/api/public/pricing-plans").status_code == 200
    assert stale.get("/api/public/subdomain-check?subdomain=brazosbend").status_code == 200

    from tests.test_us_ten_helpers import brazosbend_payload

    signup = stale.post("/api/tenants", data=brazosbend_payload(), content_type="application/json")
    assert signup.status_code == 201, signup.content
    # …and the reply replaces the stale cookie with the new owner's session.
    assert signup.cookies[SESSION_COOKIE].value != stale_value


@pytest.mark.django_db
def test_be_default_authentication_sign_in_is_still_reachable_by_a_stranger(idn):
    idn.seed_silvercreek()
    response = Client().post(
        api_path("/auth/session"),
        data={"email": CREDENTIALS["system_admin"][0], "password": CREDENTIALS["system_admin"][1]},
        content_type="application/json",
    )
    assert response.status_code == 201


# ── the endpoints §10.14 named ──────────────────────────────────────────────
@pytest.mark.django_db
@pytest.mark.parametrize("path,role", FORMERLY_401)
def test_be_default_authentication_a_signed_in_session_now_reaches_its_own_tenant(idn, path, role):
    idn.seed_silvercreek()
    client = signed_in_client(*CREDENTIALS[role])
    assert api_get(client, path).status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("path,role", FORMERLY_401)
def test_be_default_authentication_no_cookie_is_still_401(idn, path, role):
    """Nothing became reachable to a caller who is not signed in."""
    idn.seed_silvercreek()
    assert Client().get(api_path(path)).status_code == 401


@pytest.mark.django_db
@pytest.mark.parametrize("path,role", FORMERLY_401)
def test_be_default_authentication_a_foreign_session_is_still_404(idn, path, role):
    """BR-IDN-006 / HR-1 — the acceptance criterion of the path-tenancy ruling
    survives the change, and now covers these endpoints too (they inherited it
    from the shared class, with no per-endpoint code)."""
    idn.seed_silvercreek()
    idn.seed_bluemesa_admin()
    client = signed_in_client(*CREDENTIALS[role])
    assert api_get(client, path, tenant=BM).status_code == 404


@pytest.mark.django_db
def test_be_default_authentication_the_wrong_role_is_403_not_a_free_pass(idn):
    """A Billing Clerk is now AUTHENTICATED on Settings and Lookups where they
    used to get a blanket 401. A4 says System Admin only — so the answer moves
    from "who are you" to "not you", never to 200."""
    idn.seed_silvercreek()
    clerk = signed_in_client(*CREDENTIALS["billing_clerk"])
    for path in ("/settings/company", "/settings/regional", "/lookups/uoms"):
        response = api_get(clerk, path)
        assert response.status_code == 403, (path, response.status_code, response.content)
        assert response.json()["code"] == "AUTH-002"
    # …and the System Admin the rule DOES admit is served.
    admin = signed_in_client(*CREDENTIALS["system_admin"])
    assert api_get(admin, "/settings/company").status_code == 200


@pytest.mark.django_db
def test_be_default_authentication_a_revoked_session_is_refused_where_it_used_to_be_ignored(idn):
    """Before the default, these endpoints ignored the cookie entirely, so a
    revoked session got the same 401 as any other unauthenticated call. Now the
    cookie is READ — and a revoked one must still be refused, not honoured."""
    idn.seed_silvercreek()
    client = signed_in_client(*CREDENTIALS["system_admin"])
    assert api_get(client, "/settings/company").status_code == 200
    client.delete(api_path("/auth/session"))  # sign out revokes the row
    assert api_get(client, "/settings/company").status_code == 401


# ── Lifecycle ─────────────────────────────────────────────
# packet: BE-04@87ece49 (the RBAC kernel this default is paired with; the defect itself is 09-infra/02 §10.14, which has no story of its own — co-packet US-IDN-003@402b6db for the session class)
# generated: 2026-08-10 by story-coder (deploy-blocker lane)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half) F✔ G✔ H=n/a(not a 🔒 file)
# gates: black✔ ruff✔ · pytest tests/test_be_default_authentication.py 30 passed · suite `pytest tests -m "not golden and not isolation"` 843 passed / 9 skipped (818 baseline) · `-m isolation` 32 passed / 12 skipped (32 baseline) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔
# exceptions: the registry sweep reads `view.cls.authentication_classes`, i.e. what DRF resolved at import — it therefore proves the DEFAULT reached every view, which is the claim; a view that swapped authenticators at runtime would not be caught here (none does, and DRF offers no hook to) · SecurityPolicyView's class-level permission is the inherited default and its real gate is per-method in get_permissions(); the sweep asserts the FLOOR is a role gate, which is the property that matters
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
