# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-006 (EP-CWP-02) — an idempotent inbound payment webhook,
#           wired to the sandbox provider. Screens: none
# Rules:    BR-CWP-059 (idempotent on the reserved key — the same settlement
#           twice leaves ONE payment row) · BR-CWP-061 (a bounce is a new
#           negative row, never an edit) · BR-PAY-003 (dedupe on `webhook_key`)
#           · BR-TEN-003 (the tenant comes from the PATH, never the payload) ·
#           CLAUDE.md hard rule 1 · rule 6 · rule 7 · hard-won law 2 (built is
#           not wired — this file is the WIRING half) · law 3 (defaults fail
#           closed) · law 14 (the SAVEPOINT, proved on PostgreSQL)
# Tests:    this file
# Impacts:  apps/portal/api.payments_webhook (the mount) ·
#           apps/payments/webhooks.ingest · webhooks.settle_charge
# ───────────────────────────────────────────────────────
"""`US-CWP-006` — the half that was missing, and it was the half that mattered.

⚠ **`apps/payments/webhooks.py` HAS BEEN COMPLETE AND UNREACHABLE SINCE
2026-09-03**, and it said so itself. Its lifecycle block, verbatim:

    E2 the endpoint that calls this is NOT mounted by this lane. A webhook URL
       is unauthenticated by construction and its exemption from the tenant
       middleware and from CSRF is a platform decision, not a payments one.
       `ingest` is written, tested and callable; mounting it is REPORTED as the
       remaining half. Hard-won law 2 in the open: the service exists and no
       gateway can reach it yet.

**577 lines, 15 tests, and no address.** So the first case below is not a
formality: it resolves the URL a real processor would POST to and asserts the
view behind it is the one that verifies signatures. That is the assertion the
whole story turns on, and no test in this repository could have made it
yesterday.

THE TENANT COMES FROM THE PATH (TC-6)
=====================================
`/api/{tenant}/portal/webhooks/payments/{provider}` — `TenantMiddleware` reads
the first segment and sets `app.tenant_id` from it, and `BR-TEN-003` says that
is the ONLY input consulted. A body naming its own tenant would be a way to put
money on any account of any utility, which is why the case below hands in a
payload whose `tenant` field names somebody else and asserts it changes nothing.

⚠ **THE CONTRACT'S ADDRESS HAS NO TENANT SEGMENT AND THIS ONE DOES.**
`07-endpoints.md` §4 writes it `POST /webhooks/payments/{provider}`. A route
with no tenant segment can resolve a tenant only from the body — the one input
`BR-TEN-003` forbids reading — so it is mounted one prefix along instead. The
divergence is deliberate, is recorded on the view, and is the reason this file
asserts the address it actually serves.

PROVED ON POSTGRESQL, NOT ON THE SUITE'S SQLITE (law 14)
=========================================================
`settle_charge` records the delivery row and THEN tries to record a payment,
inside a nested `transaction.atomic()`. **On PostgreSQL, without that SAVEPOINT,
a refused payment aborts the whole transaction and the delivery row goes with
it** — losing the record precisely on the deliveries that most needed one. SQLite
has no aborted-transaction state, so the broken version passes the entire suite.
The `requires_postgres` case below is the only thing that can see it. Run with:

    DATABASE_URL="postgres://smartbillhub:sbh@127.0.0.1:5432/sbh_portalfix3" \\
    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
    python3 -m pytest tests/test_us_cwp_006_webhook_door.py
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from django.test import override_settings
from django.urls import resolve

from apps.integrations.adapters import payments_sandbox
from apps.payments import models as payment_models
from apps.payments import webhooks
from apps.portal import api as portal_api
from core.tenancy import tenant_context
from tests.isolation_helpers import requires_postgres
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import an_issued_bill, elm_street_account, switch_on

pytestmark = pytest.mark.django_db

PROVIDER = payments_sandbox.PaymentsSandboxAdapter.key
SECRET = "whsec_test_only_never_a_real_one"
SECRETS = {PROVIDER: SECRET}

#: `US-CWP-006` §4's own settlement.
EVENT = "STL-2609-0031"
THE_KEY = "pay_26_08841"
THE_BILL = "142.1800"
BILL_NO = "BL-2608-0141"
RECEIVED_AT = datetime(2026, 9, 5, 10, 0, tzinfo=UTC)
PAID_AT = "2026-09-05T09:59:00+00:00"


def a_bill(tenant, actor):
    account = elm_street_account(tenant, actor)
    with tenant_context(tenant.id):
        an_issued_bill(
            tenant, account, number=BILL_NO, total=THE_BILL,
            issued_on=date(2026, 8, 26), due_on=date(2026, 9, 14),
        )
    return account


def a_body(account, **extra):
    body = {
        "type": "payment_intent.succeeded",
        "account_id": str(account.pk),
        "amount": THE_BILL,
        "currency": "USD",
        "posted_at": PAID_AT,
        "cleared_at": PAID_AT,
        "reference": EVENT,
    }
    body.update(extra)
    return body


def signed(body):
    """The raw bytes and their signature, exactly as a provider would send them.

    ⚠ **OVER THE BYTES**, computed from the same `raw` that is handed in. A test
    that signed a re-serialised dict would pass while production failed.
    """
    raw = json.dumps(body).encode("utf-8")
    return raw, "sha256=" + hmac.new(SECRET.encode("utf-8"), raw, hashlib.sha256).hexdigest()


def deliver(body, *, event_id=EVENT, signature=None, raw=None):
    computed_raw, computed_signature = signed(body)
    return webhooks.ingest(
        provider=PROVIDER,
        event_id=event_id,
        raw_body=raw if raw is not None else computed_raw,
        signature=computed_signature if signature is None else signature,
        received_at=RECEIVED_AT,
    )


# ═══════════════════════════════════════════════════════════════════════════
# THE MISSING HALF — the address, and what is behind it
# ═══════════════════════════════════════════════════════════════════════════


def test_us_cwp_006_the_webhook_has_an_address_a_gateway_can_post_to(pine_hill):
    """⚠ **HARD-WON LAW 2, CLOSED.** The service existed and no gateway could
    reach it; `webhooks.py`'s own lifecycle block said so. This resolves the URL.

    **RED PROOF:** with the `urlpatterns +=` block removed from
    `apps/portal/api.py` this fails with `Resolver404`.
    """
    match = resolve(f"/api/{pine_hill.subdomain}/portal/webhooks/payments/{PROVIDER}")
    assert match.func is portal_api.payments_webhook
    assert match.kwargs["provider"] == PROVIDER

    view = portal_api.payments_webhook.cls
    # ⚠ UNAUTHENTICATED BY CONSTRUCTION AND THAT IS NOT A HOLE — a processor
    # holds no login. What guards it is the signature, and a deployment with no
    # secret refuses every delivery (law 3).
    assert view.authentication_classes == []
    assert portal_api.PortalTenantThrottle in view.throttle_classes


def test_us_cwp_006_the_three_pay_now_addresses_are_mounted_too(pine_hill):
    """The screen half of the same wave (`US-CWP-045`), asserted the same way —
    an endpoint nothing routes is a feature that does not exist."""
    base = f"/api/{pine_hill.subdomain}/portal/accounts/acc-1/pay-now"
    assert resolve(base).func is portal_api.pay_now
    assert resolve(base + "/preview").func is portal_api.pay_now_preview
    assert resolve(base + "/commit").func is portal_api.pay_now_commit
    for view in (portal_api.pay_now, portal_api.pay_now_preview, portal_api.pay_now_commit):
        # `BR-CWP-011` — the portal edge's own authentication and its own
        # permission class, never the staff app's (`G91`, `G97`).
        assert view.cls.authentication_classes != []
        assert view.cls.permission_classes != []


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 · TC-2 — one settlement, and the same settlement twice
# ═══════════════════════════════════════════════════════════════════════════


@override_settings(PAYMENT_WEBHOOK_SECRETS=SECRETS)
def test_us_cwp_006_tc1_one_settlement_is_one_payment_allocated_and_in_the_books(
    pine_hill, sarah
):
    from apps.payments import billing_seam

    switch_on(pine_hill, sarah)
    account = a_bill(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        bill = _invoice(pine_hill, BILL_NO)
        result = deliver(a_body(account))

        assert result.status == payment_models.WEBHOOK_ACCEPTED
        assert result.signature_verified is True
        payment = payment_models.Payment.objects.get(pk=result.payment_id)
        # CR-186-BRC10 (PO 2026-10-21): posted at entry, cleared at reconciliation.
        assert payment.status == payment_models.PAYMENT_POSTED
        assert payment.amount == Decimal(THE_BILL)
        assert billing_seam.allocated_so_far(bill.pk) == Decimal(THE_BILL)
        assert payment.journal_entry_id is not None, "CLAUDE.md hard rule 5"


@override_settings(PAYMENT_WEBHOOK_SECRETS=SECRETS)
def test_us_cwp_006_tc2_the_same_settlement_twice_leaves_one_payment(pine_hill, sarah):
    """⚠ **THE PRIMARY REQUIREMENT.** *"the gateway re-sending the same
    settlement produces ONE payment, not two."* A duplicate that created a second
    payment is money the customer did not pay, sitting on their account — and
    the allocation engine would spend it on their next bill."""
    switch_on(pine_hill, sarah)
    account = a_bill(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        first = deliver(a_body(account))
        second = deliver(a_body(account))
        third = deliver(a_body(account))

        assert first.created is True
        assert second.created is False and third.created is False
        assert payment_models.Payment.objects.filter(account_id=account.pk).count() == 1
        assert payment_models.PaymentWebhookEvent.objects.count() == 1


# ═══════════════════════════════════════════════════════════════════════════
# TC-4 — an unknown reference is refused, recorded, and reveals nothing
# ═══════════════════════════════════════════════════════════════════════════


@override_settings(PAYMENT_WEBHOOK_SECRETS=SECRETS)
def test_us_cwp_006_tc4_an_unknown_reference_reveals_nothing(pine_hill, sarah):
    """⚠ **NEGATIVE.** *"Refused and recorded. No payment row, and the response
    does not reveal whether the reference exists."*

    The served body is the one a provider would actually see, so the assertion
    is over `_webhook_view` and not over the internal result object.
    """
    import uuid

    switch_on(pine_hill, sarah)
    a_bill(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        stranger = uuid.uuid4()
        result = deliver({**a_body(_Stub(stranger)), "account_id": str(stranger)})
        served = portal_api._webhook_view(result)

    assert result.status == payment_models.WEBHOOK_REFUSED
    assert payment_models.Payment.objects.count() == 0
    assert payment_models.PaymentWebhookEvent.objects.count() == 1, "refused, and RECORDED"
    # ⚠ Nothing about the account, the balance or the customer is on the wire.
    assert set(served) == {"status", "created", "signature_verified", "problems"}
    body = json.dumps(served)
    # ⚠ **THIS ASSERTION FOUND A REAL LEAK AND IS THE REASON THE VIEW DROPS
    # `detail`.** The first draft served the whole problem dict, and `payments`'
    # refusal reads *"account '<uuid>' is not an account of this tenant"* — the
    # caller's own id echoed back with the rule that refused it, which answers
    # the exact question TC-4 says must not be answered.
    assert str(stranger) not in body, "the id the caller sent is not echoed back"
    assert "is not an account" not in body, "no developer prose on an open endpoint"
    # The CODE still travels, because that is what a support engineer groups on,
    # and the same code is stamped on the delivery row a person opens.
    assert any(one["code"] == webhooks.REFUSED_RULE for one in served["problems"])
    assert payment_models.PaymentWebhookEvent.objects.get().outcome == webhooks.REFUSED_RULE
    # ⚠ **AND THE SENTENCE IS NOT ON THE ROW EITHER, WHICH IS REPORTED RATHER
    # THAN QUIETLY FIXED HERE.** `_refuse` stamps the CODE in `outcome`, so
    # dropping `detail` from the response leaves the refusal's own words in the
    # returned object only — which the mount discards. Widening `outcome` to
    # carry the sentence touches `payments/0020`'s frozen column set and the
    # fifteen `C21` cases that assert the code, so it is a payments change and
    # not a portal one. Stated, not implied (hard-won law 1).


# ═══════════════════════════════════════════════════════════════════════════
# TC-6 — the tenant comes from the PATH, never the payload
# ═══════════════════════════════════════════════════════════════════════════


@override_settings(PAYMENT_WEBHOOK_SECRETS=SECRETS)
def test_us_cwp_006_tc6_a_payload_naming_another_tenant_changes_nothing(
    pine_hill, oak_ridge, sarah, elena
):
    """⚠ **TENANT ISOLATION, WITH THE ACCOUNT FACTS HELD CONSTANT** (`BR-TEN-003`).

    The delivery is processed inside Pine Hill's context — which is what the
    URL's first segment sets — and the body claims to be Oak Ridge's. The payment
    lands on Pine Hill's account and Oak Ridge sees nothing, because nothing on
    this path ever reads a tenant out of a payload.
    """
    switch_on(pine_hill, sarah)
    switch_on(oak_ridge, elena)
    account = a_bill(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        result = deliver(a_body(account, tenant=str(oak_ridge.id), tenant_slug=oak_ridge.subdomain))
        assert result.status == payment_models.WEBHOOK_ACCEPTED
        assert payment_models.Payment.objects.filter(tenant_id=pine_hill.id).count() == 1
    with tenant_context(oak_ridge.id):
        assert payment_models.Payment.objects.filter(tenant_id=oak_ridge.id).count() == 0
        assert payment_models.PaymentWebhookEvent.objects.filter(tenant_id=oak_ridge.id).count() == 0


# ═══════════════════════════════════════════════════════════════════════════
# Law 3 — a deployment with no secret refuses every delivery
# ═══════════════════════════════════════════════════════════════════════════


@override_settings(PAYMENT_WEBHOOK_SECRETS={})
def test_us_cwp_006_an_unsigned_deployment_refuses_everything(pine_hill, sarah):
    """⚠ **THE UNSAFE OPTION MUST BE THE ONE YOU TYPE.** An endpoint that created
    payments from unverified callbacks would be an unauthenticated way to put
    money on any account."""
    switch_on(pine_hill, sarah)
    account = a_bill(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        result = deliver(a_body(account))
        assert result.status == payment_models.WEBHOOK_REFUSED
        assert result.outcome == webhooks.REFUSED_NO_SECRET
        assert payment_models.Payment.objects.count() == 0
        assert payment_models.PaymentWebhookEvent.objects.count() == 1, "and still recorded"


# ═══════════════════════════════════════════════════════════════════════════
# `settle_charge` — the in-process door, and its duplicate
# ═══════════════════════════════════════════════════════════════════════════


def test_us_cwp_006_a_charge_we_started_goes_through_the_same_door(pine_hill, sarah):
    """⚠ **ONE DOOR, ONE KEY.** A charge the portal initiated is recorded by the
    same three steps a provider's callback is — so the allocation, the balanced
    pair and the audit row are the existing tested ones. Its delivery row is
    marked so a person reading the table can tell the two apart."""
    switch_on(pine_hill, sarah)
    account = a_bill(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        recorded = webhooks.settle_charge(
            provider=PROVIDER,
            key=THE_KEY,
            body={
                "account_id": str(account.pk),
                "amount": THE_BILL,
                "currency": "USD",
                "posted_at": PAID_AT,
                "cleared_at": PAID_AT,
                "method": "card",
                "reference": THE_KEY,
            },
            received_at=RECEIVED_AT,
            portal_actor={"portal_customer_id": "maria", "channel": "customer_portal"},
        )
        assert recorded.status == payment_models.WEBHOOK_ACCEPTED
        assert recorded.payment_no is not None
        row = payment_models.PaymentWebhookEvent.objects.get()
        assert row.event_type == webhooks.CHARGE_SETTLED
        # ⚠ NO SIGNATURE IS PRETENDED. There was no delivery to verify, and a
        # blanket True would destroy the one distinction this column carries.
        assert row.signature_verified is False

        # The provider's own settlement for this charge carries the same key.
        again = webhooks.settle_charge(
            provider=PROVIDER, key=THE_KEY, body={}, received_at=RECEIVED_AT
        )
        assert again.created is False
        assert payment_models.Payment.objects.count() == 1


# ═══════════════════════════════════════════════════════════════════════════
# TC-5 · PostgreSQL — the SAVEPOINT (CLAUDE.md hard-won law 14)
# ═══════════════════════════════════════════════════════════════════════════


@requires_postgres
def test_us_cwp_006_tc5_pg_a_refused_charge_keeps_its_delivery_row(pine_hill, sarah):
    """⚠ **THE CASE THE DEFAULT SUITE CANNOT SEE** (hard-won law 14).

    `settle_charge` writes the delivery row and then tries to write the payment.
    The payment here is refused by a rule — the body names no amount — and the
    delivery row must SURVIVE, because *the money is real at the gateway and
    somebody has to see it.*

    **On PostgreSQL, without the nested `transaction.atomic()` in `_record`,**
    the failed statement aborts the whole transaction, every later query raises
    `InFailedSqlTransaction`, and the delivery row is lost at COMMIT — on exactly
    the deliveries that most needed recording. **On SQLite the broken version
    passes**, which is why this case is marked and the others are not.
    """
    switch_on(pine_hill, sarah)
    account = a_bill(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        refused = webhooks.settle_charge(
            provider=PROVIDER,
            key=THE_KEY,
            # No amount — refused by `_amount`, inside the SAVEPOINT.
            body={"account_id": str(account.pk), "currency": "USD", "posted_at": PAID_AT},
            received_at=RECEIVED_AT,
        )
        assert refused.status == payment_models.WEBHOOK_REFUSED
        assert refused.outcome == webhooks.REFUSED_RULE
        # ⚠ THE ROW SURVIVED, AND THIS IS THE ASSERTION THE SAVEPOINT EXISTS FOR.
        assert payment_models.PaymentWebhookEvent.objects.count() == 1
        assert payment_models.Payment.objects.count() == 0
        # And the connection is still usable — the proof it was not aborted.
        assert payment_models.PaymentWebhookEvent.objects.filter(event_id=THE_KEY).exists()


@requires_postgres
@override_settings(PAYMENT_WEBHOOK_SECRETS=SECRETS)
def test_us_cwp_006_pg_rls_refuses_a_cross_tenant_settlement(pine_hill, oak_ridge, sarah, elena):
    """⚠ **RLS `FORCE` IS THE SECOND GUARD AND IT IS INVISIBLE TO SQLITE.**
    Under Oak Ridge's context, Pine Hill's account is not an account, so the
    settlement is refused without ever learning whether the id was real."""
    switch_on(pine_hill, sarah)
    switch_on(oak_ridge, elena)
    account = a_bill(pine_hill, sarah)
    with tenant_context(oak_ridge.id):
        result = deliver(a_body(account))
        assert result.status == payment_models.WEBHOOK_REFUSED
        assert payment_models.Payment.objects.filter(tenant_id=oak_ridge.id).count() == 0


class _Stub:
    """An account-shaped stand-in whose `pk` is a uuid nothing owns."""

    def __init__(self, pk):
        self.pk = pk


def _invoice(tenant, number):
    from apps.billing import models as billing_models

    return billing_models.Invoice.objects.get(tenant_id=tenant.id, invoice_no=number)
