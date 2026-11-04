# ── Trace ──────────────────────────────────────────────
# Change:    CR-144-BRC07 — the move to ECS Fargate behind an Application Load
#            Balancer. Tasks H1, H2, H7, H8.
# Rules:     decision log 2026-09-28 ruling 2 — the health path is
#            `/api/health`, answered by MIDDLEWARE PLACED FIRST, needing no
#            sign-in, no database and no Redis.
# Component: core/health.py (HealthCheckMiddleware), first entry of
#            config/settings/base.py MIDDLEWARE.
# Impacts:   every deployed environment — this is the check that decides
#            whether an ECS task is allowed to serve traffic at all.
# ───────────────────────────────────────────────────────
"""The load balancer's probe, and the four ways a health endpoint normally dies.

WHY A MIDDLEWARE AND NOT A VIEW
===============================
The load balancer addresses the task by its **private IP**, so the request
arrives with `Host: 10.0.1.23`. `ALLOWED_HOSTS` carries the public API name and
nothing else, so Django answers **400 before any view runs** — a health *view*
can never be reached, whatever it is mounted on. Placing the answer in the first
middleware is the only shape that works, and `test_health_answers_a_private_ip_host`
is the case that proves it.

The other three cases are the other three ways this fails in production:

  * a probe that needs a cookie (the balancer has none, and never will);
  * a probe behind an HTTPS redirect (the balancer speaks plain HTTP to the
    task on port 8000, and a `301` is not a `200`);
  * a probe that touches the database (then a slow or unreachable database
    fails the health check, every task is replaced, and a degraded service
    becomes no service at all).

⚠ **NO `django_db` MARKER ANYWHERE IN THIS FILE, AND THAT IS THE ASSERTION.**
A test that asks for the database cannot prove the code does not use it.
`test_health_answers_with_the_database_unreachable` goes further and makes the
connection raise, so a future edit that adds a query goes red rather than slow.
"""

import pytest
from django.db.backends.base.base import BaseDatabaseWrapper
from django.db.utils import OperationalError
from django.test import Client, override_settings

HEALTH_PATHS = ("/api/health", "/api/health/")

#: The shape of a deployed API task: the public name is allowed, the private IP
#: the balancer actually dials is NOT — which is the whole point.
API_HOST_ONLY = ["api-smart360.bynry.com"]
TASK_PRIVATE_IP = "10.0.1.23"


def _fresh_client() -> Client:
    """A Client built AFTER an `override_settings` has taken effect.

    `ClientHandler` loads the middleware chain once and keeps it, so a client
    created at import time would carry the settings that were live then. Every
    case here builds its own.
    """
    return Client()


@pytest.mark.parametrize("path", HEALTH_PATHS)
def test_health_answers_ok(path):
    response = _fresh_client().get(path)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize("path", HEALTH_PATHS)
def test_health_answers_a_private_ip_host(path):
    """H2 — the reason this is middleware and not a view."""
    with override_settings(ALLOWED_HOSTS=API_HOST_ONLY, DEBUG=False):
        response = _fresh_client().get(path, HTTP_HOST=TASK_PRIVATE_IP)
    assert response.status_code == 200, (
        f"{response.status_code} for Host: {TASK_PRIVATE_IP} — Django refused the "
        "balancer's own address before the probe could answer"
    )
    assert response.json() == {"status": "ok"}


def test_health_answers_with_no_cookie():
    client = _fresh_client()
    assert client.cookies == {} or not client.cookies
    response = client.get("/api/health")
    assert response.status_code == 200


def test_health_answers_through_the_https_redirect():
    """H7 — `SECURE_SSL_REDIRECT` turns every other plain-HTTP request into a
    301. The balancer speaks HTTP to port 8000 and would read that as a failed
    check, so the probe must sit AHEAD of `SecurityMiddleware`."""
    with override_settings(SECURE_SSL_REDIRECT=True):
        response = _fresh_client().get("/api/health")
    assert response.status_code == 200, (
        f"{response.status_code} — the probe was redirected instead of answered"
    )


def test_health_answers_with_the_database_unreachable(monkeypatch):
    """H7 — and it is stronger than 'no `django_db` marker'.

    Every connection attempt raises, so a future edit that adds so much as a
    `SELECT 1` fails here loudly instead of turning the health check into a
    database check.
    """

    def _refuse(self, *args, **kwargs):
        raise OperationalError("simulated: the database is unreachable")

    monkeypatch.setattr(BaseDatabaseWrapper, "ensure_connection", _refuse)
    monkeypatch.setattr(BaseDatabaseWrapper, "connect", _refuse)

    response = _fresh_client().get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize("path", HEALTH_PATHS)
def test_health_accepts_head(path):
    response = _fresh_client().head(path)
    assert response.status_code == 200
    assert response.content == b""


@pytest.mark.parametrize("path", HEALTH_PATHS)
def test_health_refuses_post(path):
    response = _fresh_client().post(path, {})
    assert response.status_code == 405
    assert "GET" in response.headers.get("Allow", "")
    assert "HEAD" in response.headers.get("Allow", "")


@pytest.mark.parametrize(
    "path", ["/api/healthz", "/api/health/extra", "/api/acme/accounts", "/", "/apihealth"]
)
def test_health_does_not_swallow_other_paths(path):
    """The middleware is FIRST in the chain, so a bug here would shadow the
    whole product. It answers exactly two paths and passes everything else on,
    untouched, on the line it arrived.

    ⚠ **CALLED DIRECTLY RATHER THAN THROUGH `Client`, ON PURPOSE.** Every other
    path falls through to `TenantContextMiddleware`, which opens the database —
    so a `Client` version of this case would need the `django_db` marker, and
    this whole file's assertion is that the probe needs no database. Here the
    rest of the chain is a sentinel, so what is proved is exactly the
    pass-through and nothing else.
    """
    from django.test import RequestFactory

    from core.health import HealthCheckMiddleware

    sentinel = object()
    middleware = HealthCheckMiddleware(lambda request: sentinel)
    assert middleware(RequestFactory().get(path)) is sentinel
    assert middleware(RequestFactory().post(path)) is sentinel
