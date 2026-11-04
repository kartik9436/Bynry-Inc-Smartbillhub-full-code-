# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CWP-3961 — the server still serialises an engine diagnostic to
#           a customer on eight portal routes. The rule was applied on the
#           ninth (api._webhook_view, DEF-CWP-3926) and nowhere else.
# Rules:    US-CWP-006 TC-4 (a refusal must not reveal whether a reference
#           exists) · B14 rule 32 (no internal code in customer-facing copy) ·
#           hard-won law 5 (one source)
# Cases:    the scrub itself · the constants are not hollowed out · a REAL
#           request through the middleware · the staff side is untouched
# ───────────────────────────────────────────────────────
"""`problems[].detail` MUST NOT REACH A CUSTOMER, ON ANY PORTAL ROUTE.

⚠ **THE CASE THAT MATTERS IS THE ONE THROUGH THE REAL REQUEST**, and it is the
only one that could have caught this defect. Every other check in this repo
looks at a SEAM or at a SCREEN: the seam is where the `detail` is legitimately
written, and the screen stopped declaring the field when `DEF-CWP-3926` was
half-fixed — so a front-end check cannot see a field the client type does not
have, and `tsc` is clean either way. The leak lived in the space between them,
which is the wire, and nothing in this repo was reading the wire.
"""

from __future__ import annotations

import pytest
from django.test import Client

from apps.portal import wire
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import (
    MARIA_EMAIL,
    MARIA_PASSWORD,
    elm_street_account,
    enrol_maria,
    switch_on,
)


def signed_in(tenant):
    client = Client()
    answer = client.post(
        f"/api/{tenant.subdomain}/portal/auth/sign-in",
        data={"email": MARIA_EMAIL, "password": MARIA_PASSWORD},
        content_type="application/json",
    )
    assert answer.status_code == 200, answer.content
    return client


def details_in(payload) -> list[str]:
    """Every `problems[].detail` anywhere in a body, at any depth."""
    found: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key == "problems" and isinstance(value, list):
                found += [
                    entry["detail"]
                    for entry in value
                    if isinstance(entry, dict) and "detail" in entry
                ]
            found += details_in(value)
    elif isinstance(payload, list):
        for item in payload:
            found += details_in(item)
    return found


# ── the scrub itself ──────────────────────────────────────────────────────


def test_the_code_travels_and_the_sentence_does_not():
    """`code`, `br_ref` and `oq_ref` are identifiers a support engineer looks
    up and carry no customer data. `detail` is prose written for a developer."""
    body = {
        "problems": [
            {"code": "late_fee_history_not_readable", "detail": "a late fee is an invoice line…"},
            {"code": "x", "br_ref": "BR-CWP-047", "oq_ref": "OQ-CWP-1600", "detail": "…"},
        ]
    }
    out = wire.customer_safe(body)
    assert out["problems"][0] == {"code": "late_fee_history_not_readable"}
    assert out["problems"][1] == {"code": "x", "br_ref": "BR-CWP-047", "oq_ref": "OQ-CWP-1600"}


def test_it_reaches_a_nested_problems_list():
    """⚠ `selectors.home` nests a balance block carrying its own list, and
    `pay_now` returns a position inside an envelope. A one-level scrub would be
    true only of the payload its author happened to be looking at."""
    body = {"balance": {"problems": [{"code": "mixed_currency", "detail": "this login's…"}]}}
    assert details_in(wire.customer_safe(body)) == []


def test_it_does_not_hollow_out_the_module_level_constants():
    """⚠ **THE TRAP THIS FUNCTION IS BUILT AGAINST.** `DEPOSIT_NOT_PRICED` and
    `LATE_FEE_NOT_READABLE` are `dict`s at IMPORT time, shared by every request
    in the process. A scrub that popped the key in place would clean the first
    response and serve a permanently hollowed constant to a developer reading
    logs forever after — and `dict(CONSTANT)` at the call site is a SHALLOW
    copy, so it would not have protected them either."""
    from apps.portal import selectors

    before = dict(selectors.LATE_FEE_NOT_READABLE)
    wire.customer_safe({"problems": [selectors.LATE_FEE_NOT_READABLE]})
    assert selectors.LATE_FEE_NOT_READABLE == before
    assert "detail" in selectors.LATE_FEE_NOT_READABLE, "the sentence still exists in the source"


def test_a_body_with_no_problems_is_returned_unchanged():
    body = {"bills": [{"number": "BL-2608-0141", "total": "142.1800"}], "n": 1, "x": None}
    assert wire.customer_safe(body) == body


# ── through the real request, which is the only place the rule lives ──────


@pytest.mark.django_db
def test_no_portal_route_serves_a_diagnostic_to_a_signed_in_customer(pine_hill, sarah):
    """⚠ **EVERY ROUTE, NOT THE NINE SOMEBODY LISTED.** The defect was eight
    routes carrying what one route had been taught to drop, and the reason a
    list of call sites is the wrong fix is that half these problems are not
    written in the portal at all — `pay_now_seam` does `[dict(one) for one in
    answer.problems]` and `payments_seam` does `problems.extend(...)`, copying
    whole dicts out of another module. This walks the addresses instead."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    enrol_maria(pine_hill, sarah)
    client = signed_in(pine_hill)
    base = f"/api/{pine_hill.subdomain}/portal"
    addresses = [
        f"{base}/home",
        f"{base}/bills",
        f"{base}/payments",
        f"{base}/accounts",
        f"{base}/accounts/{account.pk}/balance",
        f"{base}/accounts/{account.pk}/documents",
        f"{base}/accounts/{account.pk}/pay-now",
        f"{base}/accounts/{account.pk}/where-things-stand",
        f"{base}/accounts/{account.pk}/help-paying",
        f"{base}/accounts/{account.pk}/final-bill",
    ]
    reached = 0
    for address in addresses:
        answer = client.get(address)
        if answer.status_code == 404:
            continue  # the route moved or the fixture has no such case
        assert answer.status_code < 500, (address, answer.content[:400])
        if answer.status_code != 200:
            continue
        reached += 1
        leaked = details_in(answer.json())
        assert leaked == [], f"{address} served an engine diagnostic: {leaked!r}"
    # ⚠ A test that reached NOTHING would pass silently — the failure mode this
    # whole file exists to prevent.
    assert reached >= 4, f"only {reached} portal routes answered 200; the walk proves nothing"


@pytest.mark.django_db
def test_the_guest_edge_is_covered_by_the_same_rule(pine_hill, sarah):
    """`guest_api` never calls `_no_store`, so a fix on that wrapper would have
    reached none of these. The middleware is scoped by PATH."""
    switch_on(pine_hill, sarah)
    client = Client()
    base = f"/api/{pine_hill.subdomain}/portal/public"
    for address in (f"{base}/front", f"{base}/service-centres", f"{base}/reports"):
        answer = client.get(address)
        if answer.status_code != 200:
            continue
        assert details_in(answer.json()) == [], address


# ── and the staff side, which is the other half of the rule ───────────────


def test_the_staff_side_keeps_its_diagnostics():
    """⚠ **`detail` IS FOR A CLERK AND IS NOT BEING REMOVED FROM THE PRODUCT.**
    It is how a clerk is told why a screen is showing less than it would like
    to. `CR-068` wave D put the PORTAL's own settings in the STAFF app at
    `settings/portal/branding`, so a substring test — `"portal/" in path` —
    would have reached a clerk's screen and quietly taken the explanation off
    it. Checked rather than assumed."""
    scrub = wire.PortalDiagnosticScrub(lambda request: request)

    class FakeRequest:
        def __init__(self, path):
            self.path = path

    assert scrub._is_customer_path(FakeRequest("/api/pine-hill/portal/bills"))
    assert scrub._is_customer_path(FakeRequest("/api/pine-hill/portal/public/front"))
    assert not scrub._is_customer_path(FakeRequest("/api/pine-hill/settings/portal/branding"))
    assert not scrub._is_customer_path(FakeRequest("/api/pine-hill/settings/portal"))
    assert not scrub._is_customer_path(FakeRequest("/api/pine-hill/billing/runs"))
