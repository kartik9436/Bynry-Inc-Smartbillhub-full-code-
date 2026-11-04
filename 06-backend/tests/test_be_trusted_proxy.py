# ── Trace ──────────────────────────────────────────────
# Component: the client-address source shared by BR-IDN-020 (per-tenant IP
#            allowlist) and DRF throttling — apps/identity/auth.client_ip() +
#            settings.TRUSTED_PROXY_COUNT / REST_FRAMEWORK["NUM_PROXIES"]
#            (config/settings/base.py). Deploy defect 09-infra/02 §10.15.
# Rules:     BR-IDN-020 (allowlist enforced at sign-in and on every
#            authenticated request) · 11b G12 (public surface is throttled)
# Tests:     this file · the allowlist's own TCs live in
#            tests/test_us_idn_010_security_policy.py (US-IDN-010 TC-6)
# Impacts:   every deployment behind a load balancer
# ───────────────────────────────────────────────────────
"""Behind a load balancer, WHO is calling? (09-infra/02 §10.15.)

`REMOTE_ADDR` is the peer that opened the connection. On AWS that is the ALB, on
every request, so an IP allowlist admits everyone or nobody and every caller in
the world shares one throttle bucket. The repair cannot be "read
X-Forwarded-For", because XFF is a request header: anything the client writes
arrives in it, so a caller could both claim an allowlisted address and mint an
unlimited number of throttle identities by prepending one hop per request.

`TRUSTED_PROXY_COUNT` is how many proxies of OURS stand in front. Each appends
the address it saw, so the client is that many entries from the right of
`XFF + [REMOTE_ADDR]`; anything further left came from outside and is ignored.
The three cases below are the whole contract:

  0 (default)  — trust nothing. A prepended XFF changes NOTHING.
  1 (AWS: one ALB) — the client is the address the ALB appended, i.e. the last
                     XFF entry, sitting one hop left of REMOTE_ADDR.
  forgery      — a longer chain only grows the ignored left-hand side, so the
                 answer does not move however many hops a client invents.

Both readers take the same number: `client_ip()` for BR-IDN-020, DRF's
`NUM_PROXIES` for throttle identity. A test that they AGREE is here too — two
different answers to "who is calling" would be a bug that no single-reader test
could see.
"""

import pytest
from django.conf import settings as django_settings
from django.test import Client, override_settings
from rest_framework.settings import api_settings
from rest_framework.test import APIRequestFactory
from rest_framework.throttling import BaseThrottle

from apps.identity.auth import client_ip
from tests.test_us_idn_helpers import (  # noqa: F401 (fixture import)
    JSON,
    api_path,
    api_put,
    idn,
    signed_in_client,
)

#: The shape of a real hop chain on AWS: the browser talks to the ALB, the ALB
#: talks to the task. `REMOTE_ADDR` is the ALB; the last XFF entry is the caller.
CLIENT = "203.0.113.50"
ALB = "10.0.0.7"
FORGED = "198.51.100.9"


def trusted_proxies(count: int):
    """Override BOTH readers together — they are one setting by construction
    (base.py feeds TRUSTED_PROXY_COUNT into REST_FRAMEWORK["NUM_PROXIES"]), and
    a test that moved only one would prove nothing about the deployed pair."""
    return override_settings(
        TRUSTED_PROXY_COUNT=count,
        REST_FRAMEWORK={**django_settings.REST_FRAMEWORK, "NUM_PROXIES": count},
    )


def _request(**meta):
    request = APIRequestFactory().get("/api/public/pricing-plans")
    request.META.pop("REMOTE_ADDR", None)  # the factory invents 127.0.0.1
    request.META.update(meta)
    return request


def _sign_in_behind(*credentials, remote_addr, forwarded_for=None):
    """Sign in the way a request arrives through a load balancer: REMOTE_ADDR is
    the balancer, X-Forwarded-For is whatever reached it (the helper in
    test_us_idn_helpers takes only REMOTE_ADDR)."""
    email, password = credentials
    extra = {"REMOTE_ADDR": remote_addr}
    if forwarded_for is not None:
        extra["HTTP_X_FORWARDED_FOR"] = forwarded_for
    return Client().post(
        api_path("/auth/session"),
        data={"email": email, "password": password, "keep_signed_in": False},
        content_type=JSON,
        **extra,
    )


# ── the default: trust nothing ──────────────────────────────────────────────
def test_be_trusted_proxy_default_is_zero_so_the_header_is_ignored():
    """Shipping default = today's behavior. A deployment that never sets the
    variable is WRONG-BUT-SAFE (allowlists over-restrict), never fooled."""
    assert django_settings.TRUSTED_PROXY_COUNT == 0
    request = _request(REMOTE_ADDR=ALB, HTTP_X_FORWARDED_FOR=f"{FORGED}, {CLIENT}")
    assert client_ip(request) == ALB


def test_be_trusted_proxy_zero_ignores_a_prepended_chain_however_long():
    with trusted_proxies(0):
        for chain in (FORGED, f"{FORGED}, {CLIENT}", ", ".join([FORGED] * 20)):
            assert client_ip(_request(REMOTE_ADDR=ALB, HTTP_X_FORWARDED_FOR=chain)) == ALB


# ── one ALB in front: the AWS value ─────────────────────────────────────────
def test_be_trusted_proxy_one_reads_the_hop_our_own_proxy_appended():
    """With one trusted proxy the client is one hop left of REMOTE_ADDR — i.e.
    the LAST X-Forwarded-For entry, the one the ALB itself wrote."""
    with trusted_proxies(1):
        assert client_ip(_request(REMOTE_ADDR=ALB, HTTP_X_FORWARDED_FOR=CLIENT)) == CLIENT
        # …and with a client that sent its own XFF, the ALB appended the truth
        # to the right of the lie: last-but-one of the full chain
        # [FORGED, CLIENT, REMOTE_ADDR].
        forged = _request(REMOTE_ADDR=ALB, HTTP_X_FORWARDED_FOR=f"{FORGED}, {CLIENT}")
        assert client_ip(forged) == CLIENT


@pytest.mark.parametrize("hops", [1, 2, 5, 50])
def test_be_trusted_proxy_a_forged_longer_chain_cannot_move_the_answer(hops):
    """Prepending only grows the part we already ignore."""
    with trusted_proxies(1):
        chain = ", ".join([FORGED] * hops + [CLIENT])
        assert client_ip(_request(REMOTE_ADDR=ALB, HTTP_X_FORWARDED_FOR=chain)) == CLIENT


def test_be_trusted_proxy_falls_back_when_the_chain_is_shorter_than_configured():
    """A hop that did not forward leaves fewer entries than we expect. The
    leftmost is then the furthest back we can honestly see — never an index
    error, and never REMOTE_ADDR silently masquerading as the client."""
    with trusted_proxies(2):
        assert client_ip(_request(REMOTE_ADDR=ALB, HTTP_X_FORWARDED_FOR=CLIENT)) == CLIENT
        assert client_ip(_request(REMOTE_ADDR=ALB)) == ALB  # no header at all
        assert client_ip(_request(REMOTE_ADDR=ALB, HTTP_X_FORWARDED_FOR="  ,  ")) == ALB


def test_be_trusted_proxy_no_remote_addr_is_none_not_empty_string():
    """BR-IDN-020 treats a missing address as "not in the allowlist" — that
    only works if the absence is None rather than ''."""
    assert client_ip(_request()) is None


# ── the throttle identity reads the SAME number ─────────────────────────────
def test_be_trusted_proxy_drf_throttle_identity_agrees_with_client_ip():
    """§10.15's second half. Left unset, DRF joins the WHOLE chain into the
    throttle key, so prepending a hop buys a fresh 60/min bucket on the public
    onboarding surface. Wired to the same count, the two readers cannot
    disagree about who is calling."""
    assert api_settings.NUM_PROXIES == django_settings.TRUSTED_PROXY_COUNT

    throttle = BaseThrottle()
    forged_chain = f"{FORGED}, {CLIENT}"
    with trusted_proxies(0):
        request = _request(REMOTE_ADDR=ALB, HTTP_X_FORWARDED_FOR=forged_chain)
        assert throttle.get_ident(request) == ALB == client_ip(request)
    with trusted_proxies(1):
        request = _request(REMOTE_ADDR=ALB, HTTP_X_FORWARDED_FOR=forged_chain)
        assert throttle.get_ident(request) == CLIENT == client_ip(request)
        # Two requests that differ ONLY in the forged prefix must land in the
        # same bucket — that is what makes the throttle unbypassable.
        other = _request(REMOTE_ADDR=ALB, HTTP_X_FORWARDED_FOR=f"192.0.2.1, {CLIENT}")
        assert throttle.get_ident(other) == throttle.get_ident(request)


# ── BR-IDN-020 end to end (US-IDN-010 TC-6, behind a proxy) ─────────────────
@pytest.mark.django_db
def test_be_trusted_proxy_br_idn_020_allowlist_sees_the_caller_not_the_balancer(idn):
    """The allowlist half of §10.15, proven through the real sign-in endpoint.

    Silver Creek allows 203.0.113.0/24. Every request below arrives from the
    ALB (`REMOTE_ADDR=10.0.0.7`), which is NOT in that range — so with the
    default of 0 the tenant is locked out of its own account, and with 1 the
    rule applies to the human who actually called."""
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
    credentials = ("priya@silvercreek.example", "Meadow2026sage")

    with trusted_proxies(0):
        # The address the allowlist sees is the balancer's: a legitimate user
        # inside the allowed range is refused (BR-IDN-020, generic 403).
        locked_out = _sign_in_behind(*credentials, remote_addr=ALB, forwarded_for=CLIENT)
        assert locked_out.status_code == 403
        # …and the header cannot be used to talk the server round, either.
        forged = _sign_in_behind(*credentials, remote_addr=ALB, forwarded_for=f"{CLIENT}, {FORGED}")
        assert forged.status_code == 403

    with trusted_proxies(1):
        allowed = _sign_in_behind(*credentials, remote_addr=ALB, forwarded_for=CLIENT)
        assert allowed.status_code == 201, allowed.content
        # An outsider cannot claim an allowlisted address: the ALB appends its
        # peer to the RIGHT of whatever the client sent, and only that is read.
        outsider = _sign_in_behind(
            *credentials, remote_addr=ALB, forwarded_for=f"{CLIENT}, 192.0.2.44"
        )
        assert outsider.status_code == 403


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-IDN-010@493ea2f (BR-IDN-020's input; the deploy defect is 09-infra/02 §10.15, which has no story of its own)
# generated: 2026-08-10 by story-coder (deploy-blocker lane)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half) F✔ G✔ H=n/a(not a 🔒 file)
# gates: black✔ ruff✔ · pytest tests/test_be_trusted_proxy.py 11 passed · suite `pytest tests -m "not golden and not isolation"` 843 passed / 9 skipped (818 baseline) · `-m isolation` 32 passed / 12 skipped (32 baseline) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔
# exceptions: the arithmetic is deliberately IDENTICAL to DRF's BaseThrottle.get_ident (bounded index from the right) so the allowlist and the throttle can never disagree — a divergence would be a defect, not a design choice · IPv6 is untested here because BR-IDN-020's own implementation is IPv4-only (services._check_ip_allowed parses IPv4Address/IPv4Network); widening the rule is a PO question, REPORTED, not decided here
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
