# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-INT-10020 — US Payments could not reach us. Its three calls
#           were served only at `/api/{utility}/integrations/inbound/
#           pay_uspayments/{operation}`, an address naming the utility and our
#           connector; US Payments sends neither in any URL.
# Rules:    PO ruling 2026-10-07 (*"go - for USPayments partner API URL Fix"*)
#           · the 2026-09-16 partner-URL rule (no utility and no vendor in a
#           partner URL; the key names the utility) · BR-TEN-003 · BR-INT-044 ·
#           BR-INT-037 · CR-174-BRC10 D1–D4 · CLAUDE.md hard rule 1 · law 14
# ───────────────────────────────────────────────────────
"""US Payments at the three partner addresses, called EXACTLY the way US Payments calls.

    GET  /api/partner/v1/account-lookup?accountId=00012345
    POST /api/partner/v1/add-payment
    POST /api/partner/v1/add-return

    password: <the key the utility issued>      (no `Bearer`, value as given)
    username: <anything — a label, never checked>

WHAT WOULD MAKE THESE CHECKS PASS WRONGLY — asked first (law 7)
---------------------------------------------------------------
**One utility in the fixture.** A directory that answered *the only tenant there
is* would pass every case. So the isolation case builds two, each with its own
key and its own account under the SAME number, and reads the BALANCE back.

**Opening a tenant in the test.** `CR-174`'s own cases did exactly that and
called the view with the utility in the path — which is how a door US Payments
could never reach passed 27 tests (`DEF-INT-10020`'s escape reason). Every case
here goes through `django.test.Client` at the real address with the tenant
CLEARED first, so the only thing that can open a utility is the key.

**A refusal that is the same words but not the same refusal.** The unknown,
wrong, revoked and Bearer-instead-of-password cases compare the status AND the
bytes AND that each one waited the floor.
"""

from __future__ import annotations

import json
import logging
import time
from decimal import Decimal

import pytest
from django.urls import resolve

from apps.integrations import key_directory, machine_auth, models
from apps.integrations.registry import REGISTRY
from apps.integrations.runners import serve
from apps.payments import models as payment_models
from core import tenancy as core_tenancy
from tests.test_cr174_us_payments import (  # noqa: F401 — fixtures
    ADDRESS,
    KEY,
    ROSA,
    USP,
    _bill,
    _connect,
    _map_tenders,
    _payment,
    _payments,
    _return,
    rosa,
    usp,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

LOOKUP = "/api/partner/v1/account-lookup"
PAY = "/api/partner/v1/add-payment"
RETURN = "/api/partner/v1/add-return"
THE_THREE = (LOOKUP, PAY, RETURN)

LONESTAR_KEY = "sbh_live_USP9_lonestar_do_not_reuse"


def _call(client, address, *, key=KEY, query=None, body=None, bearer=False, extra=None):
    """One call the way US Payments makes it, with NO utility open beforehand."""
    core_tenancy.clear_current_tenant()
    headers = {"REMOTE_ADDR": ADDRESS, "HTTP_USERNAME": "uspayments", **(extra or {})}
    if key is not None:
        if bearer:
            headers["HTTP_AUTHORIZATION"] = f"Bearer {key}"
        else:
            headers["HTTP_PASSWORD"] = key
    if address.endswith("account-lookup") or address.endswith("account-lookup/"):
        return client.get(address, query or {}, **headers)
    return client.post(
        address + ("?" + "&".join(f"{k}={v}" for k, v in query.items()) if query else ""),
        data=json.dumps(body or {}),
        content_type="application/json",
        **headers,
    )


def _owed(client, key=KEY, account=ROSA):
    answer = _call(client, LOOKUP, key=key, query={"accountId": account})
    assert answer.status_code == 200, answer.content
    return json.loads(answer.content, parse_float=Decimal)


# ══════════════════════════════════════════════════════════════════════════
# 1 · the addresses
# ══════════════════════════════════════════════════════════════════════════


def test_the_three_addresses_resolve_with_and_without_the_slash_and_name_nobody():
    for address in THE_THREE:
        assert "uspayments" not in address.lower() and "{" not in address
        for spelling in (address, address + "/"):
            resolve(spelling)  # Resolver404 is the failure


def test_the_manifest_declares_the_three_addresses_it_is_served_at():
    """The routes are BUILT from this declaration — never typed beside it."""
    served = {one.name: one.served_path for one in REGISTRY.require(USP).operations}
    assert served == {
        "account_lookup": "/partner/v1/account-lookup",
        "payments": "/partner/v1/add-payment",
        "returns": "/partner/v1/add-return",
    }


# ══════════════════════════════════════════════════════════════════════════
# 2 · the whole conversation, by the key in `password` alone
# ══════════════════════════════════════════════════════════════════════════


def test_lookup_pay_lookup_return_lookup_by_the_password_header_alone(client, brazos, rosa):
    """Rosa owes $147.85, pays $150.00 → -$2.15 credit; the $150.00 comes back
    R01 → $147.85 owed again. No utility in any URL, none opened by the test."""
    assert _owed(client)["amountDue"] == Decimal("147.85")
    paid = _call(client, PAY, body=_payment(amount=150.00, method="ACHCHECK"))
    assert paid.status_code == 200, paid.content
    assert _owed(client)["amountDue"] == Decimal("-2.15")
    back = _call(client, RETURN, body=_return(amount=150.00, code="R01"))
    assert back.status_code == 200, back.content
    assert _owed(client)["amountDue"] == Decimal("147.85")
    with tenant_ctx(brazos):
        rows = _payments(brazos)
    assert len(rows) == 2 and {row.origin for row in rows} == {"agent"}


def test_the_trailing_slash_spelling_works_too(client, brazos, rosa):
    answer = _call(client, LOOKUP + "/", query={"accountId": ROSA})
    assert answer.status_code == 200 and json.loads(answer.content)["accountValid"] is True
    assert _call(client, PAY + "/", body=_payment()).status_code == 200


def test_a_repeated_payment_id_is_409_and_posts_once(client, brazos, rosa):
    assert _call(client, PAY, body=_payment()).status_code == 200
    assert _call(client, PAY, body=_payment()).status_code == 409
    assert _call(client, RETURN, body=_return()).status_code == 200
    assert _call(client, RETURN, body=_return()).status_code == 409
    with tenant_ctx(brazos):
        assert len(_payments(brazos)) == 2  # the payment and its one reversal


def test_username_is_a_label_and_is_never_checked(client, brazos, rosa):
    for label in ("uspayments", "", "somebody-else"):
        answer = _call(client, LOOKUP, query={"accountId": ROSA}, extra={"HTTP_USERNAME": label})
        assert answer.status_code == 200


# ══════════════════════════════════════════════════════════════════════════
# 3 · isolation — the key decides, and nothing the caller sends does
# ══════════════════════════════════════════════════════════════════════════


@pytest.fixture()
def lonestar_rosa(lonestar, erin):
    """ANOTHER utility with its OWN US Payments key and an account under the
    SAME number, owing a different figure ($61.00)."""
    from datetime import date

    from apps.customers import models as customer_models
    from tests.test_us_met_helpers import make_premises, make_unit

    with tenant_ctx(lonestar):
        _map_tenders(lonestar, erin)
        _connect(lonestar, erin, key=LONESTAR_KEY, hint="••••USP9")
        # Lone Star offers water only (the same build `CR-174`'s own
        # other-utility case uses); `an_account` asks for electric.
        premises = make_premises(erin, address_line="12 Lone Star Rd", services_available=["water"])
        unit = make_unit(erin, premises["id"], label="Unit A", services=["water"])
        statuses = customer_models.AccountStatus.objects.filter(tenant=lonestar)
        account = customer_models.Account.objects.create(
            tenant=lonestar,
            unit_id=unit["id"],
            status=statuses.filter(code="active").first() or statuses.first(),
            account_type=customer_models.AccountType.objects.filter(tenant=lonestar).first(),
            account_no=ROSA,
        )
        _bill(lonestar, account, number="LS-2608-0001", total="61.0000", issued_on=date(2026, 8, 1), due_on=date(2099, 8, 22))
    return account


def test_each_utilitys_key_reaches_only_that_utility(client, brazos, lonestar, rosa, lonestar_rosa):
    assert _owed(client, key=KEY)["amountDue"] == Decimal("147.85")
    assert _owed(client, key=LONESTAR_KEY)["amountDue"] == Decimal("61.00")
    assert _call(client, PAY, key=LONESTAR_KEY, body=_payment(amount=61.00)).status_code == 200
    with tenant_ctx(brazos):
        assert _payments(brazos) == [], "B's key posted nothing into A"
    with tenant_ctx(lonestar):
        assert len(_payments(lonestar)) == 1
    assert _owed(client, key=KEY)["amountDue"] == Decimal("147.85")
    assert _owed(client, key=LONESTAR_KEY)["amountDue"] == Decimal("0.00")


def test_a_utility_named_in_the_query_body_or_a_header_is_ignored(client, brazos, lonestar, rosa, lonestar_rosa):
    """Brazos's key, with every way a caller might try to name Lone Star."""
    claim = {"utility": lonestar.subdomain, "tenant": lonestar.subdomain, "tenant_id": str(lonestar.id)}
    answer = _call(
        client,
        LOOKUP,
        query={"accountId": ROSA, **claim},
        extra={"HTTP_X_TENANT": lonestar.subdomain, "HTTP_X_TENANT_ID": str(lonestar.id)},
    )
    assert json.loads(answer.content, parse_float=Decimal)["amountDue"] == Decimal("147.85")
    paid = _call(client, PAY, query=claim, body={**_payment(), **claim})
    assert paid.status_code == 200
    with tenant_ctx(lonestar):
        assert _payments(lonestar) == []
    with tenant_ctx(brazos):
        assert len(_payments(brazos)) == 1


def test_no_utility_is_left_open_after_the_call(client, brazos, rosa):
    _owed(client)
    assert core_tenancy.current_tenant_id() is None


# ══════════════════════════════════════════════════════════════════════════
# 4 · the one refusal — words, status and time
# ══════════════════════════════════════════════════════════════════════════


def _refusals(client, brazos, dana):
    """(name, response, seconds) for every way a key can be wrong."""
    out = []
    for name, kwargs in (
        ("unknown key", {"key": "sbh_live_never_issued_anywhere"}),
        ("no key", {"key": None}),
        ("right key as Bearer", {"bearer": True}),
    ):
        started = time.monotonic()
        response = _call(client, PAY, body=_payment(), **kwargs)
        out.append((name, response, time.monotonic() - started))
    with tenant_ctx(brazos):
        connection = models.IntegrationConnection.objects.get(tenant=brazos, provider_key=USP)
        machine_auth.revoke_key(actor=dana, connection=connection)
    started = time.monotonic()
    response = _call(client, LOOKUP, query={"accountId": ROSA})
    out.append(("revoked key", response, time.monotonic() - started))
    return out


def test_a_wrong_unknown_or_revoked_key_gets_the_one_refusal_padded_to_the_floor(client, brazos, dana, rosa):
    seen = _refusals(client, brazos, dana)
    for name, response, seconds in seen:
        assert response.status_code == 401, name
        assert json.loads(response.content) == {"error": serve.REFUSAL_SENTENCE}, name
        assert seconds >= serve.REFUSAL_FLOOR_S, f"{name} answered in {seconds:.3f}s"
    assert len({response.content for _n, response, _s in seen}) == 1, "one refusal, byte for byte"
    with tenant_ctx(brazos):
        assert _payments(brazos) == []


def test_the_password_never_reaches_a_log_line(client, brazos, rosa, caplog):
    caplog.set_level(logging.DEBUG)
    _owed(client)
    _call(client, PAY, body=_payment(), key="sbh_live_a_wrong_secret_value")
    assert KEY not in caplog.text and "sbh_live_a_wrong_secret_value" not in caplog.text


# ══════════════════════════════════════════════════════════════════════════
# 5 · the Bearer partners are unchanged, and the two doors do not mix
# ══════════════════════════════════════════════════════════════════════════


def test_a_bearer_partner_is_served_exactly_as_before(client, brazos, dana):
    from tests.test_cr110_phase2_partner_reference import ALLOWED_ADDRESS
    from tests.test_cr110_phase2_partner_reference import _connect as connect_erp

    serve.reset_partner_limits()
    erp_key = "sbh_live_ERP1_bearer_do_not_reuse"
    with tenant_ctx(brazos):
        connect_erp(brazos, dana, key=erp_key, hint="••••ERP1")
    core_tenancy.clear_current_tenant()
    answer = client.get("/api/partner/v1/reference", REMOTE_ADDR=ALLOWED_ADDRESS, HTTP_AUTHORIZATION=f"Bearer {erp_key}")
    assert answer.status_code == 200, answer.content
    core_tenancy.clear_current_tenant()
    as_password = client.get("/api/partner/v1/reference", REMOTE_ADDR=ALLOWED_ADDRESS, HTTP_PASSWORD=erp_key)
    assert as_password.status_code != 200, "a Bearer route still reads Bearer, and only Bearer"


def test_the_us_payments_key_opens_none_of_the_bearer_routes(client, brazos, rosa):
    for address in ("/api/partner/v1/payments", "/api/partner/v1/make-payment/", "/api/partner/v1/accounts"):
        core_tenancy.clear_current_tenant()
        response = client.get(address, REMOTE_ADDR=ADDRESS, HTTP_AUTHORIZATION=f"Bearer {KEY}")
        assert response.status_code != 200, address


# ══════════════════════════════════════════════════════════════════════════
# 6 · the old per-utility address no longer answers US Payments
# ══════════════════════════════════════════════════════════════════════════


def _old_door(tenant, operation, *, body=None, query=None, method="POST"):
    from rest_framework.test import APIRequestFactory

    from apps.integrations import inbound_api

    factory = APIRequestFactory()
    path = f"/api/{tenant.subdomain}/integrations/inbound/{USP}/{operation}"
    if method == "GET":
        request = factory.get(path, data=query or {}, REMOTE_ADDR=ADDRESS)
    else:
        request = factory.post(path, data=json.dumps(body or {}).encode(), content_type="application/json", REMOTE_ADDR=ADDRESS)
    request.META["HTTP_PASSWORD"] = KEY
    request.tenant_id = tenant.id
    with core_tenancy.tenant_context(tenant.id):
        return inbound_api.inbound_door(request, key=USP, operation=operation)


def test_the_old_address_refuses_us_payments_in_the_ordinary_way_and_says_so_in_the_log(brazos, rosa, caplog):
    caplog.set_level(logging.INFO)
    for operation, kwargs in (
        ("payments", {"body": _payment()}),
        ("returns", {"body": _return()}),
        ("account_lookup", {"method": "GET", "query": {"accountId": ROSA}}),
    ):
        answer = _old_door(brazos, operation, **kwargs)
        assert answer.status_code == 401, operation
        assert json.loads(answer.content) == {"error": serve.REFUSAL_SENTENCE}
    with tenant_ctx(brazos):
        assert _payments(brazos) == []
        assert payment_models.PaymentWebhookEvent.objects.filter(tenant=brazos).count() == 0
    assert "/partner/v1/add-payment" in caplog.text, "the refusal names where it moved"
    assert KEY not in caplog.text


# ══════════════════════════════════════════════════════════════════════════
# 7 · every issued key has its directory row
# ══════════════════════════════════════════════════════════════════════════


def test_an_issued_us_payments_key_has_its_directory_row(brazos, dana):
    """Issued through the card's own path (`machine_auth.issue_key` →
    `services.record_credential` → `key_directory.record`), the key resolves
    its utility with no tenant open."""
    with tenant_ctx(brazos):
        connection = models.IntegrationConnection.objects.create(
            tenant=brazos,
            provider_key=USP,
            label="USPayments",
            environment=models.ENVIRONMENT_PRODUCTION,
            status=models.STATUS_WORKING,
            enabled=True,
            cadence=models.CADENCE_MANUAL,
            config={},
        )
        row, secret = machine_auth.issue_key(
            actor=dana,
            connection=connection,
            scope=[one.name for one in REGISTRY.require(USP).operations],
        )
    core_tenancy.clear_current_tenant()
    assert key_directory.tenant_for(secret) == brazos.id
    assert models.IntegrationKeyDirectory.objects.filter(credential_id=row.id, tenant_id=brazos.id).exists()


def test_the_check_command_lists_a_key_with_no_directory_row_and_changes_nothing(brazos, dana, usp):
    from io import StringIO

    from django.core.management import call_command

    out = StringIO()
    call_command("check_key_directory", stdout=out)
    assert "0 missing" in out.getvalue(), out.getvalue()

    models.IntegrationKeyDirectory.objects.filter(connection_id=usp.id).delete()
    out = StringIO()
    call_command("check_key_directory", stdout=out)
    text = out.getvalue()
    assert "1 missing" in text and USP in text and brazos.subdomain in text, text
    assert KEY not in text
    assert not models.IntegrationKeyDirectory.objects.filter(connection_id=usp.id).exists(), "read-only"


def test_the_check_command_fix_writes_the_row_and_the_key_works_again(client, brazos, dana, rosa, usp):
    from io import StringIO

    from django.core.management import call_command

    models.IntegrationKeyDirectory.objects.filter(connection_id=usp.id).delete()
    refused = _call(client, LOOKUP, query={"accountId": ROSA})
    assert refused.status_code == 401, "no row: the key opens no utility and reads as a wrong key"
    out = StringIO()
    call_command("check_key_directory", "--fix", stdout=out)
    assert "1 missing · 1 written" in out.getvalue(), out.getvalue()
    assert key_directory.tenant_for(KEY) == brazos.id
    assert _owed(client)["amountDue"] == Decimal("147.85")


# ══════════════════════════════════════════════════════════════════════════
# 8 · the card shows what a System Admin copies
# ══════════════════════════════════════════════════════════════════════════


def test_the_uspayments_card_shows_the_three_addresses_as_dialled(brazos, dana, usp):
    """The API table on Settings → Integrations → USPayments is what a System
    Admin copies into US Payments' set-up — so it must be the address that
    ANSWERS, `/api` included, and it must be the one the router serves."""
    from apps.integrations import selectors

    with tenant_ctx(brazos):
        grid = selectors.grid(brazos.id)
    card = next(one for one in grid["providers"] if one["key"] == USP)
    endpoints = {one["name"]: one["endpoint"] for one in card["operations"]}
    assert endpoints == {"account_lookup": LOOKUP, "payments": PAY, "returns": RETURN}
    for address in endpoints.values():
        resolve(address)
