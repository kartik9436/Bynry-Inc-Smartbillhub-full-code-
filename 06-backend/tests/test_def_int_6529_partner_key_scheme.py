# ── Trace ──────────────────────────────────────────────
# Defect: DEF-INT-6529 — the partner API published as PUBLIC in the OpenAPI
#         contract. 23 operations carried `security: [{}]`, which in OpenAPI
#         means *this endpoint needs no credentials*, and one of them was
#         `POST /api/partner/v1/make-payment/`.
# Rules:  BR-INT-044 (the refusals are ONE refusal — same bytes, same status,
#         same time) · BR-TEN-003 (the tenant comes from the key, never from
#         anything a caller asserts) · CLAUDE.md hard rule 1 · hard-won law 7
#         (name the false pass first; prove the guard RED, in the harness that
#         will run it)
# Tests:  this file · the contract half is tests/test_be11_openapi.py::
#         test_be11_tc02_… · the authenticator opt-out list is
#         tests/test_be_default_authentication.py::PUBLIC_ROUTES
# ───────────────────────────────────────────────────────
"""THE DOOR WAS NEVER OPEN. THIS FILE IS WHY WE GET TO SAY THAT.

`DEF-INT-6529` reads, at a glance, like a world-readable payment endpoint. It
is not one, and the difference between *a hole* and *a wrong sign on a shut
door* is the whole of what a Product Owner needs to be told — so it is proved
here rather than reasoned about anywhere.

WHAT WOULD MAKE THESE CHECKS PASS WRONGLY — asked first, per law 7
------------------------------------------------------------------
**1 · `assert response.status_code == 404` proves NOTHING on this surface.**
An address that does not exist is also a 404, and so is a typo in the path, a
route that failed to register, and a middleware that refused before the view
ran. `test_invoice_cloud_make_payment.py` records this trap in its own words.
So every case below is a PAIR: the same address is called **with a valid key**
and **with no key at all**, in one test, and the assertion is that the two
answers DIFFER and that only the second is the refusal. A 404 that a missing
route would also produce cannot satisfy it, because the valid-key half would
be a 404 too.

**2 · The refusal could be a DIFFERENT refusal.** A door that answered *no
Authorization header* faster, or in other words, than it answers a stolen key
would hand an attacker an oracle (`BR-INT-044`). So the no-key answer is
compared BYTE FOR BYTE against the answer a key we have never issued gets.

**3 · The decorator could be on twelve of the thirteen views.** A hand-written
list of partner views here would go stale the first time a fourteenth door
landed — which is exactly how the defect arrived, and `partner_api.py`'s own
docstring records the same rot costing it *"these three"* when there were
eleven. So the rule is asserted, not the list: **every view in `partner_api`
that opts out of the authenticator carries `partner_key_required`**, derived
from the module at run time.

**4 · The runtime and the contract could describe different doors.** The
schema could name a bearer scheme while the code read a header called
something else. `_presented_key` is exercised directly against the exact
header spelling the published scheme promises.

PROVED RED FIRST, in `pytest` — the harness that runs it (`DEF-GOV-3733`):
  * `@partner_key_required` removed from `partner_make_payment` →
    `test_every_partner_view_declares_the_key_it_demands` fails naming that
    view, and `test_be11_tc02_…` fails naming the two `make-payment` spellings.
  * `serve._credential_matching`'s `if not presented: return None` replaced
    with a pass-through → `test_the_partner_door_refuses_a_caller_with_no_key`
    fails on the valid/no-key pair no longer differing.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from django.test import Client

from apps.integrations import invoice_cloud_payment as ic
from apps.integrations import partner_api, partner_urls
from apps.integrations.runners import serve
from tests.test_be11_openapi import _export_to_string

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_int_041_partner_surface import ALLOWED_ADDRESS
from tests.test_invoice_cloud_make_payment import (
    ACCOUNT_NO,
    BILL_NO,
    KEY,
    _account,
    _connect,
    _issue,
)

#: A key that was never issued. The no-key answer is compared against THIS
#: one's, not against a status code (false pass 2).
NEVER_ISSUED = "sbh_live_this_was_never_issued"


def _call(method: str, path: str, *, key: str | None, body: dict | None = None):
    """One partner request through the REAL router.

    ⚠ **THE DJANGO TEST CLIENT AND NOT `APIRequestFactory`, WHICH IS THE POINT
    OF THIS FILE.** The read and write suites call the view FUNCTION with
    `request.tenant_id` pre-set and the tenant context already open — correct
    for what they assert, and it skips both things this file exists to prove:
    URL resolution, and `partner_urls._with_utility_from_key` opening the
    utility from the key before DRF dispatches. A door proved by calling the
    room behind it is not a proved door.
    """
    client = Client(REMOTE_ADDR=ALLOWED_ADDRESS)
    headers = {"HTTP_AUTHORIZATION": f"Bearer {key}"} if key is not None else {}
    if method == "post":
        return client.post(
            path, data=json.dumps(body or {}), content_type="application/json", **headers
        )
    return client.get(path, **headers)


def _bytes(response) -> bytes:
    """What goes on the wire. `.json()` would compare parsed objects and miss a
    difference in ordering, whitespace or content type."""
    return b"".join(response.streaming_content) if response.streaming else response.content


# ════════════════════════════════════════════════════════════════════════
# 1 · THE RUNTIME DOOR — shut, and shut in the one way
# ════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_the_partner_door_refuses_a_caller_with_no_key(brazos, dana):
    """⚠ **THE SENTENCE THIS WHOLE DEFECT TURNS ON.**

    A caller presenting NO `Authorization` header at all reaches
    `_presented_key` → `None` → `serve._credential_matching`'s
    `if not presented: return None` → `KEY_UNKNOWN`. That path was never
    covered: `_six_refusals` walks *a key we have never seen*, *revoked*,
    *expired*, *blocked address*, *connector off* and *scope* — six ways of
    presenting a BAD key, and no way of presenting NONE. A `None` that fell
    through to a query matching a row with a null blind index would have opened
    every one of these addresses, and nothing in the suite would have said so.
    """
    with tenant_ctx(brazos):
        _connect(brazos, dana)
        account = _account(brazos, dana)
        _issue(brazos, account)

    # …the address is REAL and it SERVES (false pass 1). Without this half a
    # 404 below would be indistinguishable from a route that does not exist.
    #
    # ⚠ **THE FIELD NAMES ARE THE MODULE'S CONSTANTS, NEVER TYPED.** A first
    # draft wrote `AccountNumber`/`BillNumber`/`PaymentAmount` — none of which
    # this door has ever accepted; the real spellings are `consumer_id`,
    # `bill_id` and `amount`. The case still PASSED, because a body the door
    # rejects is a `400` and `400 != 404`. That is the discriminator working
    # and the proof being worth less than it looks: it showed the door admitted
    # the caller, not that the address serves. Asserting the success status
    # closes it.
    served = _call(
        "post",
        "/api/partner/v1/make-payment/",
        key=KEY,
        body={
            ic.FIELD_ACCOUNT: ACCOUNT_NO,
            ic.FIELD_BILL: BILL_NO,
            ic.FIELD_REFERENCE: "TID-DEF-INT-6529",
            ic.FIELD_DATE: "20-06-2026",
            ic.FIELD_AMOUNT: "10.00",
            ic.FIELD_METHOD: "card",
        },
    )
    assert served.status_code == 200, (
        "the valid-key call did not serve, so the no-key assertion below would "
        f"prove nothing: {served.status_code} {_bytes(served)!r}"
    )

    # …and with no key at all it is refused, in the one refusal.
    no_key = _call("post", "/api/partner/v1/make-payment/", key=None, body={})
    stranger = _call("post", "/api/partner/v1/make-payment/", key=NEVER_ISSUED, body={})
    assert no_key.status_code == 404
    assert _bytes(no_key) == _bytes(stranger), (
        "a caller with NO key must get the same bytes as a caller with a key we "
        f"never issued (BR-INT-044): {_bytes(no_key)!r} vs {_bytes(stranger)!r}"
    )
    assert json.loads(_bytes(no_key))["code"] == "REFUSED"


@pytest.mark.django_db
def test_every_partner_address_refuses_a_caller_with_no_key(brazos, dana):
    """The same property over the whole route table, derived not typed.

    ⚠ **`PARTNER_ROUTES` IS THE AUTHORITY** — `partner_urls.py` says so in as
    many words — so a fourteenth address is covered the day it is registered
    rather than the day somebody remembers this file.
    """
    with tenant_ctx(brazos):
        _connect(brazos, dana)

    stranger_bytes = _bytes(_call("get", "/api/partner/v1/reference", key=NEVER_ISSUED))
    for name in partner_urls.PARTNER_ROUTES:
        method = "post" if name == "make-payment" else "get"
        response = _call(method, f"/api/partner/v1/{name}", key=None, body={})
        assert response.status_code == 404, f"{method} {name} answered a caller with no key"
        assert _bytes(response) == stranger_bytes, (
            f"{method} {name} refuses a no-key caller differently from a stolen "
            "key — that difference is an oracle (BR-INT-044)"
        )


def test_the_published_header_is_the_header_the_code_reads():
    """False pass 4. The contract promises `Authorization: Bearer …`; this is
    the function that reads it. A scheme describing one header while the door
    read another would document a credential nobody could present."""

    class _Req:
        def __init__(self, header):
            self.META = {"HTTP_AUTHORIZATION": header} if header else {}

    assert partner_api.PARTNER_KEY_SECURITY_SCHEME["type"] == "http"
    assert partner_api.PARTNER_KEY_SECURITY_SCHEME["scheme"] == "bearer"
    assert partner_api._presented_key(_Req("Bearer sbh_live_abc")) == "sbh_live_abc"
    assert partner_api._presented_key(_Req("bearer sbh_live_abc")) == "sbh_live_abc"
    assert partner_api._presented_key(_Req(None)) is None
    assert partner_api._presented_key(_Req("Basic sbh_live_abc")) is None
    # …and the refusal floor the scheme's own description promises is real.
    assert serve.REFUSAL_FLOOR_S > 0


# ════════════════════════════════════════════════════════════════════════
# 2 · THE SIGN ON THE DOOR — the rule, never a list
# ════════════════════════════════════════════════════════════════════════


def _partner_views():
    """Every view in `partner_api` that opts out of the session authenticator.

    That opt-out IS the definition of a partner door in this module: the three
    manager views (`access_log`, `subprocessor_register`, `grant_authority`)
    inherit the default authenticator and are reached by a signed-in System
    Admin. Deriving the set this way means the assertion below covers a door
    nobody has written yet.
    """
    found = {}
    for name in dir(partner_api):
        view = getattr(partner_api, name)
        view_class = getattr(view, "cls", None)
        if view_class is None or not name.startswith("partner_"):
            continue
        if list(view_class.authentication_classes) == []:
            found[name] = view_class
    return found


def _served_paths():
    """`{view class: [(method, published path)]}` for everything Django serves.

    The router's spelling is translated to the CONTRACT's the same way
    `core.openapi.name_the_tenant_segment` does it, because that is the
    spelling the published document uses and the one a partner reads. Django's
    `<str:name>` converters become `{name}` for the same reason.
    """
    import re

    from django.urls import get_resolver

    def walk(resolver, prefix=""):
        for pattern in resolver.url_patterns:
            if hasattr(pattern, "url_patterns"):
                yield from walk(pattern, prefix + str(pattern.pattern))
            else:
                yield prefix + str(pattern.pattern), pattern.callback

    served: dict[Any, list[tuple[str, str]]] = {}
    for route, callback in walk(get_resolver()):
        view_class = getattr(callback, "cls", None)
        if view_class is None:
            continue
        path = "/" + route.replace("^api/[-a-zA-Z0-9_]+/", "api/{tenant}/", 1)
        path = re.sub(r"<[^:>]+:([^>]+)>", r"{\1}", path)
        for method in getattr(view_class, "http_method_names", []):
            if method in ("options", "head", "trace"):
                continue
            if hasattr(view_class, method) or method in {
                verb.lower() for verb in getattr(callback, "actions", {})
            }:
                served.setdefault(view_class, []).append((method, path))
    return served


def test_every_partner_view_declares_the_key_it_demands():
    """False pass 3. **The rule is asserted against the PUBLISHED DOCUMENT, not
    against a list typed here and not against the decorator object.**

    A hand-written list of the thirteen partner views would go stale the first
    time a fourteenth door landed — which is how this defect arrived, and what
    `partner_api.py`'s own docstring records costing it *"these three"* when
    there were eleven. So the set is derived from the module (every view that
    opts out of the authenticator IS a partner door here; the three manager
    views inherit the default and are reached by a signed-in System Admin), its
    addresses are derived from the router, and the answer is read out of the
    schema the export command actually emits.

    Checking `view.schema.get_auth()` instead would be checking the mechanism
    rather than the outcome — and it cannot be done at all: DRF's schema
    descriptor refuses to be read off a class, which is itself a small
    demonstration that a check aimed at the machinery is the fragile one.
    """
    views = _partner_views()
    assert len(views) == 13, f"the partner surface changed shape: {sorted(views)}"

    schema = json.loads(_export_to_string())
    want = [{partner_api.PARTNER_KEY_SCHEME_NAME: []}]

    served = _served_paths()
    undeclared, unpublished = [], []
    for name, view_class in views.items():
        for method, path in served.get(view_class, []):
            operation = (schema["paths"].get(path) or {}).get(method)
            if operation is None:
                unpublished.append(f"{method} {path} ({name})")
            elif operation.get("security") != want:
                undeclared.append(f"{method} {path} ({name}): {operation.get('security')}")

    assert unpublished == [], (
        "a partner door is served but absent from the published contract, so "
        f"this test could not see it either: {unpublished}"
    )
    assert undeclared == [], (
        "these partner doors publish no credential requirement, so the contract "
        f"tells a client generator they are public (DEF-INT-6529): {undeclared}"
    )
    # …and it is not vacuous: thirteen views, and every one of them is served.
    assert sum(len(served.get(vc, [])) for vc in views.values()) == 23


def test_the_scheme_is_defined_where_the_hook_can_find_it():
    """The name and the definition are ONE object, imported by
    `core.openapi.key_security_schemes()` rather than retyped — a mismatch
    would publish an operation naming a scheme nobody defines, which is invalid
    OpenAPI that no test in this repository would otherwise notice."""
    from core import openapi

    schemes = openapi.key_security_schemes()
    assert schemes[partner_api.PARTNER_KEY_SCHEME_NAME] is (partner_api.PARTNER_KEY_SECURITY_SCHEME)


def test_the_hook_declares_only_what_an_operation_names():
    """A scheme left defined after the last operation stopped naming it is a
    stale claim nothing re-checks (hard-won law 1). The hook reads the document
    back, so the definitions and the requirements cannot disagree."""
    from core import openapi

    name = partner_api.PARTNER_KEY_SCHEME_NAME

    nobody_asks = openapi.declare_the_key_schemes({"paths": {}})
    assert name not in nobody_asks.get("components", {}).get("securitySchemes", {})

    somebody_asks = openapi.declare_the_key_schemes(
        {"paths": {"/x": {"get": {"security": [{name: []}]}}}}
    )
    assert somebody_asks["components"]["securitySchemes"][name] is (
        partner_api.PARTNER_KEY_SECURITY_SCHEME
    )

    # …and a scheme a real authenticator already resolved is never overwritten.
    already = {"type": "apiKey", "in": "cookie", "name": "sbh_session"}
    kept = openapi.declare_the_key_schemes(
        {
            "paths": {"/x": {"get": {"security": [{name: []}]}}},
            "components": {"securitySchemes": {name: already}},
        }
    )
    assert kept["components"]["securitySchemes"][name] is already


def test_the_contract_fix_did_not_touch_the_runtime_door():
    """The two halves are independent, and this is what says so.

    `authentication_classes` is what the AUTHENTICATOR sweep in
    `tests/test_be_default_authentication.py` reads and what DRF acts on;
    `extend_schema` writes only to the schema class. If a later lane "tidied"
    the fix by giving these views an authenticator instead, every partner
    address would start reading a session cookie it must never read, and
    `PUBLIC_ROUTES` would have to be widened — which that file exists to
    prevent.
    """
    for name, view_class in _partner_views().items():
        assert list(view_class.authentication_classes) == [], name
        assert [cls.__name__ for cls in view_class.permission_classes] == ["AllowAny"], name


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-INT-6529 (no story — a defect on the published contract; the surface is US-INT-041 / CR-110-BRC04 phase 2)
# generated: 2026-09-24 by lane PARTNER-CONTRACT
# checklist: A✔ B=n/a(no screen) C✔ D✔ E=n/a F✔ G✔ H=n/a(the guarded logic is runners/serve.py, untouched)
# gates: pytest tests/test_def_int_6529_partner_key_scheme.py · tests/test_be11_openapi.py · tests/test_be_default_authentication.py · tests/test_us_int_041_partner_surface.py · tests/test_invoice_cloud_make_payment.py
# exceptions: the no-key half of the door is proved on SQLite here and was measured on PostgreSQL 16 through the same router on 2026-09-24 (see the decision-log entry)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
