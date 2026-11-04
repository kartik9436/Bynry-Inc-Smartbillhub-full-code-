# ── Trace ──────────────────────────────────────────────
# Change:    CR-144-BRC07 (X1, X2, X3, X6) — the SPA moves to its own host.
# Rules:     decision log 2026-09-28 ruling 1 — two hosts, `app[-env].bynry.com`
#            and `api-smart360[-env].bynry.com`.
# Component: corsheaders.middleware.CorsMiddleware (settings only) ·
#            core/origin_guard.py · AUTH_COOKIE_SECURE at the three sign-in
#            cookie sites.
# Impacts:   every state-changing API call, and every sign-in.
# ───────────────────────────────────────────────────────
"""CORS grants what a browser may READ; the Origin guard decides what we DO.

⚠ **THE SECOND HALF IS THE ONE THAT DEFENDS ANYTHING, AND IT IS EASY TO THINK
CORS ALREADY DID IT.** `app-*.bynry.com` and `api-*.bynry.com` are the same
SITE, so a `SameSite=Lax` session cookie rides along from any `*.bynry.com`
page; DRF's default parsers accept form posts; and the session authenticator is
a custom cookie class with no CSRF check. A cross-origin `<form method=post>`
is therefore SENT, with the victim's cookie, and CORS only hides the response
from the attacker's script — after the write has happened.

`test_cross_origin_form_post_is_refused` is that exact request.
"""

import pytest
from django.test import Client

ALLOWED = "https://app.bynry.com"
STRANGER = "https://app.bynry.com.attacker.example"
SAME_SITE_STRANGER = "https://evil.bynry.com"

#: Any state-changing endpoint will do — the guard runs in middleware, ahead of
#: every view, so which one it is cannot matter. This one is chosen because it
#: needs no database to be refused.
A_WRITE_PATH = "/api/acme/auth/session"


def _client() -> Client:
    return Client()


class TestCors:
    #: ⚠ **A FIXTURE AND NOT `@override_settings` ON THE CLASS** — that decorator
    #: only works on `SimpleTestCase` subclasses and raises at COLLECTION time
    #: on a plain pytest class, which is how this was found.
    @pytest.fixture(autouse=True)
    def _two_hosts(self, settings):
        settings.CORS_ALLOWED_ORIGINS = [ALLOWED]
        settings.ORIGIN_GUARD_ALLOWED_ORIGINS = [ALLOWED]

    def test_allowed_origin_gets_a_credentialed_grant(self):
        response = _client().options(
            A_WRITE_PATH,
            HTTP_ORIGIN=ALLOWED,
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
        )
        assert response.headers.get("Access-Control-Allow-Origin") == ALLOWED
        assert response.headers.get("Access-Control-Allow-Credentials") == "true"

    def test_any_other_origin_gets_no_grant(self):
        """⚠ **AND `Access-Control-Allow-Origin: *` IS NOT A LAXER ANSWER, IT IS
        A BROKEN ONE** — a browser refuses the wildcard together with
        credentials, and the session cookie IS the credential. So the assertion
        is that the header is ABSENT, not that it is permissive."""
        for origin in (STRANGER, SAME_SITE_STRANGER, "https://example.com"):
            response = _client().options(
                A_WRITE_PATH,
                HTTP_ORIGIN=origin,
                HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            )
            assert "Access-Control-Allow-Origin" not in response.headers, origin

    def test_the_allowed_origin_is_an_exact_string_never_a_suffix(self):
        """`https://app.bynry.com.attacker.example` ENDS WITH nothing useful and
        STARTS WITH the allowed origin. A prefix or suffix match would grant it."""
        response = _client().options(
            A_WRITE_PATH,
            HTTP_ORIGIN=STRANGER,
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
        )
        assert "Access-Control-Allow-Origin" not in response.headers


class TestOriginGuard:
    #: ⚠ **A FIXTURE AND NOT `@override_settings` ON THE CLASS** — that decorator
    #: only works on `SimpleTestCase` subclasses and raises at COLLECTION time
    #: on a plain pytest class, which is how this was found.
    @pytest.fixture(autouse=True)
    def _two_hosts(self, settings):
        settings.CORS_ALLOWED_ORIGINS = [ALLOWED]
        settings.ORIGIN_GUARD_ALLOWED_ORIGINS = [ALLOWED]

    @pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
    def test_a_state_changing_call_from_a_stranger_is_refused(self, method):
        response = getattr(_client(), method)(A_WRITE_PATH, HTTP_ORIGIN=SAME_SITE_STRANGER)
        assert response.status_code == 403
        assert response.json()["br_ref"] == "CR-144-BRC07"

    def test_cross_origin_form_post_is_refused(self):
        """X6 — the request CORS cannot stop.

        A plain HTML form post is not a request the browser asks permission
        for: it is sent, with the cookie, and only the RESPONSE is hidden. So
        the refusal has to happen here, before any view runs.
        """
        response = _client().post(
            A_WRITE_PATH,
            data={"email": "dana@example.com", "password": "x"},
            content_type="application/x-www-form-urlencoded",
            HTTP_ORIGIN=SAME_SITE_STRANGER,
        )
        assert response.status_code == 403

    @pytest.mark.parametrize(
        "origin",
        [
            pytest.param(ALLOWED, id="our-own-front-end"),
            pytest.param("http://testserver", id="the-api-s-own-host"),
            pytest.param(None, id="no-origin-header-at-all"),
        ],
    )
    def test_these_are_let_through(self, origin):
        """⚠ **THE MIDDLEWARE IS CALLED DIRECTLY, AND THAT IS NOT LAZINESS.**
        Letting a request THROUGH means it reaches a view, and every write view
        in this product opens the database — so a `Client` version of these
        three would need a tenant, a user and a credential to assert one thing
        about middleware. Here the rest of the chain is a sentinel, so what is
        proved is exactly "not refused" and nothing else.

        The three cases are the three that MUST pass:
          * our own front end, which is the entire point;
          * the API's own host, so the browsable API and the OpenAPI UI are not
            refused by their own server;
          * **NO `Origin` HEADER AT ALL — the stated blind spot, asserted so it
            cannot drift shut by accident.** `curl`, the partner surface at
            `/api/partner/v1/…` and inbound payment webhooks all send none, and
            a browser always sends one on these methods. Refusing a missing
            header would break every integration and defend nothing.
        """
        from django.test import RequestFactory

        from core.origin_guard import OriginGuardMiddleware

        sentinel = object()
        middleware = OriginGuardMiddleware(lambda request: sentinel)
        extra = {"HTTP_ORIGIN": origin} if origin else {}
        request = RequestFactory().post(A_WRITE_PATH, **extra)
        assert middleware(request) is sentinel

    def test_a_stranger_is_refused_at_the_same_call_site(self):
        """The mirror of the case above, through the same door, so the two
        cannot be passing for different reasons."""
        from django.test import RequestFactory

        from core.origin_guard import OriginGuardMiddleware

        sentinel = object()
        middleware = OriginGuardMiddleware(lambda request: sentinel)
        request = RequestFactory().post(A_WRITE_PATH, HTTP_ORIGIN=SAME_SITE_STRANGER)
        response = middleware(request)
        assert response is not sentinel
        assert response.status_code == 403

    @pytest.mark.parametrize("method", ["get", "head", "options"])
    def test_reads_are_not_examined(self, method):
        """`OPTIONS` especially: it is the CORS preflight and must reach
        `CorsMiddleware`. Refusing it here would present as a CORS
        misconfiguration and send the next reader to the wrong file."""
        response = getattr(_client(), method)(
            "/api/health", HTTP_ORIGIN=SAME_SITE_STRANGER
        )
        assert response.status_code != 403


class TestSecureCookie:
    """X3 — one setting, three sites. The suite runs it OFF (a test `Client`
    speaks plain HTTP), so these cases turn it back on for themselves — which is
    the only way the flag is proved at all."""

    def test_the_setting_defaults_to_secure(self):
        """Hard-won law 3: the unsafe option is the one you TYPE. Read from
        base.py rather than from the suite's override, because the suite's value
        is False and asserting that would prove the opposite of the rule."""
        import importlib

        base = importlib.import_module("config.settings.base")
        source = open(base.__file__.replace(".pyc", ".py")).read()
        assert 'env.bool("SBH_AUTH_COOKIE_SECURE", default=True)' in source

    @pytest.mark.django_db
    def test_the_three_cookie_sites_read_the_setting(self):
        """⚠ **A GREP, AND IT IS SAID OUT LOUD THAT IT IS ONE** (law 7: describe
        the false pass). Exercising all three sign-in paths end to end needs a
        tenant, a user, a credential and a portal account, and those fixtures
        live in three different suites. What this asserts is that no site holds
        a LITERAL — which is the failure that actually happens: two of three
        get changed and the third is remembered a release later."""
        from pathlib import Path

        for path in (
            "apps/identity/api.py",
            "apps/tenancy/api.py",
            "apps/portal/api.py",
        ):
            source = Path(path).read_text()
            assert "secure=settings.AUTH_COOKIE_SECURE" in source, path
            assert "secure=True" not in source, path
            assert "secure=False" not in source, path
