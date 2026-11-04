# ── Trace ──────────────────────────────────────────────
# Change:   CR-174-BRC10 — US Payments (Prime): the three calls they make to us
# Rules:    PO 2026-10-07 D1–D4 · BR-INT-058 (superseded for this connector
#           only) · BR-PAY-003/028 · BR-PAY-010 · BR-PAY-013 · BR-TEN-081 ·
#           CLAUDE.md hard rules 1, 2, 4, 5, 6, 7 · law 14
# ───────────────────────────────────────────────────────
"""US Payments (Prime) — every case the coordinator's brief named, through the REAL view.

Rosa's account owes two bills: **$45.00** (July) and **$102.85** (August) —
**$147.85** in all. She pays **$150.00** cash at a kiosk. The July bill is met
first (oldest first, BR-PAY-001), then August, and **$2.15** carries as credit
(BR-PAY-010), so the next lookup answers `amountDue: -2.15`. Then the bank
returns a different, ACH payment with `R01` and both bills are due again.

⚠ **THE CONCURRENT-DUPLICATE CASE IS `requires_postgres` AND THAT IS LAW 14,
NOT CONVENIENCE.** SQLite serialises writers, so two simultaneous identical
payments can never race there; only PostgreSQL can show that the unique index
decides and the loser is answered `409` rather than `500`.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from django.db import connection, connections

from apps.integrations import inbound, mappings, models, services
from apps.integrations.registry import REGISTRY
from apps.integrations.runners import serve
from apps.payments import models as payment_models
from core import crypto
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

requires_postgres = pytest.mark.skipif(
    connection.vendor != "postgresql",
    reason="CLAUDE.md law 14 — only PostgreSQL can race two writers on one unique index.",
)

USP = "pay_uspayments"
KEY = "sbh_live_USP7_brazosbend_do_not_reuse"
HINT = "••••USP7"
ADDRESS = "198.51.100.12"
ROSA = "00012345"  # leading zeros are part of it
CONNECT = {
    "environment": models.ENVIRONMENT_PRODUCTION,
    "cadence": models.CADENCE_MANUAL,
    "label": None,
    "fields": {},
}


# ══════════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════════


def _method(tenant, code, name):
    from apps.tenancy.models import PaymentMethod

    found = PaymentMethod.objects.filter(tenant=tenant, code=code).first()
    return found or PaymentMethod.objects.create(tenant=tenant, code=code, name=name)


def _connect(tenant, actor, *, key=KEY, hint=HINT, config=None):
    row = models.IntegrationConnection.objects.create(
        tenant=tenant,
        provider_key=USP,
        label="USPayments",
        environment=models.ENVIRONMENT_PRODUCTION,
        status=models.STATUS_WORKING,
        enabled=True,
        cadence=models.CADENCE_MANUAL,
        config=config or {},
    )
    services.record_credential(
        actor=actor,
        connection=row,
        payload=key,
        masked_hint=hint,
        blind_index=crypto.blind_index(key, context=serve.ISSUED_KEY_BLIND_INDEX_CONTEXT),
        scope=[one.name for one in REGISTRY.require(USP).operations if one.they_call_us],
    )
    return row


def _map_tenders(tenant, actor):
    for code, name in (("cash", "Cash"), ("check", "Check"), ("ach", "ACH"), ("card", "Card"), ("other", "Other")):
        _method(tenant, code, name)
    mappings.set_rows(
        actor=actor,
        tenant_id=tenant.id,
        provider_key=USP,
        rows=[
            {"entity_type": "tender", "external_value": word, "local_value": code}
            for word, code in (
                ("CASH", "cash"),
                ("CHECK", "check"),
                ("ACHCHECK", "ach"),
                ("ACHSAVINGS", "ach"),
                ("CREDIT", "card"),
                ("OTHER", "other"),
            )
        ],
    )


@pytest.fixture()
def usp(brazos, dana):
    serve.reset_partner_limits()
    with tenant_ctx(brazos):
        _map_tenders(brazos, dana)
        return _connect(brazos, dana)


def _bill(tenant, account, *, number, total, issued_on, due_on):
    from apps.billing import models as billing_models

    amount = Decimal(total)
    return billing_models.Invoice.objects.create(
        tenant=tenant,
        account=account,
        invoice_no=number,
        status=billing_models.INVOICE_ISSUED,
        service_date=issued_on,
        period_start=issued_on.replace(day=1),
        period_end=issued_on,
        due_date=due_on,
        subtotal=amount,
        tax_total=Decimal("0"),
        total=amount,
        issued_at=datetime(issued_on.year, issued_on.month, issued_on.day, 9, 0, tzinfo=UTC),
    )


@pytest.fixture()
def rosa(brazos, dana, usp):
    """Rosa's account `00012345`: July $45.00 (late) and August $102.85."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no=ROSA)
        july = _bill(brazos, account, number="BL-2607-0001", total="45.0000", issued_on=date(2026, 7, 1), due_on=date(2026, 7, 22))
        august = _bill(brazos, account, number="BL-2608-0002", total="102.8500", issued_on=date(2026, 8, 1), due_on=date(2099, 8, 22))
    return account, july, august


def _call(tenant, operation, *, body=None, query=None, key=KEY, method="POST", headers=None, provider=USP):
    """One US Payments call the way US Payments makes it — at the address the
    manifest publishes, `password` header and all, with NO utility open.

    ⚠ **THIS OPENED THE UTILITY ITSELF AND CALLED `inbound_door` AT
    `/api/{utility}/integrations/inbound/pay_uspayments/{operation}` UNTIL
    `DEF-INT-10020` (2026-10-07)** — an address US Payments can never call,
    since it sends no utility and no connector name in any URL. Every case
    below passed over a door nobody outside could reach. Now the KEY opens the
    utility, through `django.test.Client` at `/api/partner/v1/…`, so `tenant`
    is kept only so the cases read as before: it selects nothing.
    """
    from django.test import Client

    from core import tenancy as core_tenancy

    del tenant  # the key names the utility; see the docstring
    address = "/api" + inbound.operation_named(REGISTRY.require(provider), operation).served_path
    extra = {"REMOTE_ADDR": ADDRESS, "HTTP_USERNAME": "uspayments"}
    if key is not None:
        extra["HTTP_PASSWORD"] = key
    for name, value in (headers or {}).items():
        extra["HTTP_" + name.upper()] = value
    core_tenancy.clear_current_tenant()
    client = Client()
    if method == "GET":
        return client.get(address, query or {}, **extra)
    return client.post(address, data=json.dumps(body or {}), content_type="application/json", **extra)


def _json(response):
    return json.loads(response.content, parse_float=Decimal)


def _lookup(tenant, account_ref, **kw):
    return _call(tenant, "account_lookup", method="GET", query={"accountId": account_ref}, **kw)


def _payment(payment_id=900000000123, *, account=ROSA, amount=150.00, method="CASH", when="2026-10-07T18:32:05Z", **extra):
    return {
        "paymentId": payment_id,
        "accountId": account,
        "paymentDateTime": when,
        "channel": "KIOSK",
        "kioskId": 4471,
        "method": method,
        "amount": amount,
        "someFutureField": {"ignored": True},
        **extra,
    }


def _return(payment_id=900000000123, *, account=ROSA, amount=150.00, code="R01", when="2026-10-09T15:00:00Z"):
    return {**_payment(payment_id, account=account, amount=amount), "returnDateTime": when, "returnCode": code}


def _payments(tenant):
    return list(payment_models.Payment.objects.filter(tenant=tenant).order_by("created_at"))


def _open(invoice):
    from apps.payments import billing_seam

    return invoice.total - billing_seam.allocated_so_far(invoice.pk)


# ══════════════════════════════════════════════════════════════════════════
# The manifest — the card is the connector, the kiosk is untouched
# ══════════════════════════════════════════════════════════════════════════


def test_the_uspayments_card_is_live_with_three_inbound_operations():
    manifest = REGISTRY.require(USP)
    assert manifest.display_name == "USPayments"
    assert not manifest.disposition.coming_soon
    assert [one.name for one in manifest.operations] == ["payments", "account_lookup", "returns"]
    assert all(one.they_call_us for one in manifest.operations), "they call us; we never call them"
    assert manifest.auth.mode == "they_hold_ours" and manifest.auth.header == "password"
    assert {one.name for one in manifest.fields} >= {"issued_key", "allowed_addresses"}


def test_the_kiosk_declares_no_apply_and_so_still_applies_nothing():
    """`payments_kiosk` was not ruled; it stays exactly as it was."""
    kiosk = REGISTRY.require("payments_kiosk")
    assert all(one.applies is None for one in kiosk.operations)
    assert all(one.respond_after in ("dedupe", "authenticate") for one in kiosk.operations)


# ══════════════════════════════════════════════════════════════════════════
# Account lookup
# ══════════════════════════════════════════════════════════════════════════


def test_lookup_answers_the_live_balance_and_the_overdue_part(brazos, rosa):
    answer = _lookup(brazos, ROSA)
    assert answer.status_code == 200
    body = _json(answer)
    assert body["accountValid"] is True
    assert body["amountDue"] == Decimal("147.85")
    assert body["pastDue"] == Decimal("45.00"), "July is late; August is not due"
    assert body["allowPayments"] is body["allowCheck"] is body["allowCredit"] is body["allowDebit"] is True
    assert body["displayCredit"] is True
    assert b'"amountDue": 147.85' in answer.content, "a JSON NUMBER, two decimals, no float"


def test_lookup_is_the_same_figure_the_customer_portal_reads(brazos, rosa):
    from apps.portal.seams import payments_seam as portal_seam

    account, _july, _august = rosa
    with tenant_ctx(brazos):
        portal = portal_seam.account_balance(account.pk)
    assert Decimal(portal["owing"]) == _json(_lookup(brazos, ROSA))["amountDue"]


def test_lookup_of_an_unknown_account_is_200_and_account_valid_false(brazos, usp):
    answer = _lookup(brazos, "99999999")
    assert answer.status_code == 200
    assert _json(answer) == {"accountValid": False}


def test_leading_zeros_are_part_of_the_account_id(brazos, rosa):
    assert _json(_lookup(brazos, ROSA))["accountValid"] is True
    assert _json(_lookup(brazos, "12345"))["accountValid"] is False


def test_lookup_of_another_utilitys_account_is_account_valid_false(brazos, lonestar, erin, rosa):
    from apps.customers import models as customer_models
    from tests.test_us_met_helpers import make_premises, make_unit

    with tenant_ctx(lonestar):
        premises = make_premises(erin, address_line="12 Lone Star Rd", services_available=["water"])
        unit = make_unit(erin, premises["id"], label="Unit A", services=["water"])
        customer_models.Account.objects.create(
            tenant=lonestar,
            unit_id=unit["id"],
            status=customer_models.AccountStatus.objects.filter(tenant=lonestar).first(),
            account_type=customer_models.AccountType.objects.filter(tenant=lonestar).first(),
            account_no="LS-777",
        )
    with tenant_ctx(lonestar):
        assert customer_models.Account.objects.filter(account_no="LS-777").exists()
    assert _json(_lookup(brazos, "LS-777")) == {"accountValid": False}


def test_a_cash_only_account_may_pay_but_not_by_cheque_card_or_bank(brazos, rosa):
    """The product's one real restriction (BR-PAY-013's cash-only flag)."""
    account, _j, _a = rosa
    with tenant_ctx(brazos):
        type(account).objects.filter(pk=account.pk).update(cash_only_no_autopay=True)
    body = _json(_lookup(brazos, ROSA))
    assert body["allowPayments"] is True
    assert body["allowCheck"] is body["allowCredit"] is body["allowDebit"] is False


def test_a_commercial_account_is_not_residential(brazos, rosa):
    from apps.customers import models as customer_models

    account, _j, _a = rosa
    with tenant_ctx(brazos):
        residential = customer_models.AccountType.objects.filter(tenant=brazos, code="residential").first()
        commercial = customer_models.AccountType.objects.filter(tenant=brazos, code="commercial").first()
        assert residential is not None and commercial is not None
        type(account).objects.filter(pk=account.pk).update(account_type=residential)
    assert _json(_lookup(brazos, ROSA))["isResidential"] is True
    with tenant_ctx(brazos):
        type(account).objects.filter(pk=account.pk).update(account_type=commercial)
    assert _json(_lookup(brazos, ROSA))["isResidential"] is False


# ══════════════════════════════════════════════════════════════════════════
# The credential
# ══════════════════════════════════════════════════════════════════════════


def test_a_wrong_key_is_401_even_on_the_lookup(brazos, rosa):
    for answer in (
        _lookup(brazos, ROSA, key="sbh_live_wrong"),
        _lookup(brazos, ROSA, key=None),
        _call(brazos, "payments", body=_payment(), key="sbh_live_wrong"),
    ):
        assert answer.status_code == 401
        assert json.loads(answer.content) == {"error": serve.REFUSAL_SENTENCE}
    with tenant_ctx(brazos):
        assert _payments(brazos) == []


def test_a_company_id_that_names_another_utility_is_401(brazos, dana, rosa, usp):
    with tenant_ctx(brazos):
        models.IntegrationConnection.objects.filter(pk=usp.pk).update(
            config={"enterprise_id": "ENT-55", "company_id": "BRZ-01"}
        )
    assert _lookup(brazos, ROSA, headers={"companyId": "BRZ-01", "enterpriseId": "ENT-55"}).status_code == 200
    assert _lookup(brazos, ROSA, headers={"companyId": "OTHER-9"}).status_code == 401
    assert _call(brazos, "payments", body=_payment(), headers={"enterpriseId": "ENT-99"}).status_code == 401
    assert _lookup(brazos, ROSA).status_code == 200, "not sent is not checked"


def test_the_password_never_reaches_a_log_line_or_a_run_row(brazos, rosa, caplog):
    caplog.set_level(logging.DEBUG)
    _lookup(brazos, ROSA)
    _call(brazos, "payments", body=_payment())
    _call(brazos, "payments", body=_payment(), key="sbh_live_a_wrong_secret_value")
    assert KEY not in caplog.text and "sbh_live_a_wrong_secret_value" not in caplog.text
    with tenant_ctx(brazos):
        for run in models.IntegrationRun.objects.filter(tenant=brazos):
            row = json.dumps({k: str(v) for k, v in run.__dict__.items()})
            assert KEY not in row and "sbh_live_a_wrong" not in row
        for event in payment_models.PaymentWebhookEvent.objects.filter(tenant=brazos):
            assert KEY not in json.dumps(event.body)


# ══════════════════════════════════════════════════════════════════════════
# A payment
# ══════════════════════════════════════════════════════════════════════════


def test_a_payment_posts_oldest_first_carries_credit_balances_and_is_audited(brazos, rosa, audit_rows):
    _account, july, august = rosa
    answer = _call(brazos, "payments", body=_payment())
    assert answer.status_code == 200
    with tenant_ctx(brazos):
        (payment,) = _payments(brazos)
        assert payment.amount == Decimal("150.0000")
        # CR-186-BRC10 (PO 2026-10-21): posted at entry, cleared at reconciliation.
        assert payment.status == payment_models.PAYMENT_POSTED
        assert payment.origin == payment_models.PAYMENT_ORIGIN_AGENT
        assert payment.method.code == "cash"
        assert payment.confirmation == "900000000123"
        assert _open(july) == 0 and _open(august) == 0
        from apps.ledger import models as ledger_models

        lines = ledger_models.JournalLine.objects.filter(tenant=brazos, journal_entry__status=ledger_models.JE_POSTED)
        debits = sum((one.amount for one in lines if one.side == "debit"), Decimal("0"))
        credits = sum((one.amount for one in lines if one.side == "credit"), Decimal("0"))
        assert debits == credits == Decimal("150.0000"), "balanced pairs (hard rule 5)"
        event = payment_models.PaymentWebhookEvent.objects.get(tenant=brazos, provider=USP)
        assert event.payment_id == payment.pk and event.status == payment_models.WEBHOOK_ACCEPTED
        assert event.body["kioskId"] == 4471 and event.body["channel"] == "KIOSK", "raw kept"
    assert [row for row in audit_rows if row["action"] == "payment.recorded"], "hard rule 7"
    lookup = _json(_lookup(brazos, ROSA))
    assert lookup["amountDue"] == Decimal("-2.15"), "the overpayment is held as credit"
    assert lookup["pastDue"] == Decimal("0.00")


def test_a_replayed_payment_is_409_and_nothing_is_processed_twice(brazos, rosa):
    assert _call(brazos, "payments", body=_payment()).status_code == 200
    again = _call(brazos, "payments", body=_payment())
    assert again.status_code == 409
    with tenant_ctx(brazos):
        assert len(_payments(brazos)) == 1


def test_guard_two_alone_still_refuses_a_second_payment(brazos, rosa, monkeypatch):
    """DEF-058 — with the door's landing guard blinded, the payment key holds."""
    from apps.integrations.seams import payments as payments_seam
    from apps.payments import agent_door

    # Two LANDING rows under two different door keys — guard 1 cannot see a
    # repeat — and both post the same agent payment id. Only the payment's own
    # key (`agent|pay_uspayments:900000000123|payment`) stands between them.
    received = datetime(2026, 10, 7, 18, 32, tzinfo=UTC)
    with tenant_ctx(brazos):
        outcomes = []
        for blind in ("first-landing", "second-landing"):
            landed = payments_seam.land_inbound_delivery(
                provider=USP, event_id=blind, body=_payment(), received_at=received
            )
            outcomes.append(
                agent_door.post_payment(
                    provider=USP,
                    door_key="900000000123|payment",
                    event_row_id=landed.event_row_id,
                    account_ref=ROSA,
                    amount=Decimal("150.00"),
                    paid_at=received,
                    method_code="cash",
                    confirmation="900000000123",
                )
            )
        assert len(_payments(brazos)) == 1, "uq_payments_webhook_key held the line on its own"
    assert [one.replayed for one in outcomes] == [False, True]


def test_a_zero_or_negative_amount_is_400_and_nothing_is_kept(brazos, rosa):
    for amount in (0, -5.00, "abc", 1.005):
        answer = _call(brazos, "payments", body=_payment(amount=amount))
        assert answer.status_code == 400, amount
    with tenant_ctx(brazos):
        assert _payments(brazos) == []
        assert not payment_models.PaymentWebhookEvent.objects.filter(tenant=brazos).exists()


def test_the_payment_date_is_the_utilitys_own_day(brazos, rosa):
    """`2026-10-08T03:30Z` is 7 October on a utility in Chicago (BR-TEN-081)."""
    from apps.tenancy import models as tenancy_models

    with tenant_ctx(brazos):
        tenancy_models.TenantSettings.objects.filter(tenant_id=brazos.id).update(timezone="America/Chicago")
    assert _call(brazos, "payments", body=_payment(when="2026-10-08T03:30:00Z")).status_code == 200
    from apps.tenancy import selectors as tenancy_selectors

    with tenant_ctx(brazos):
        (payment,) = _payments(brazos)
        local = payment.posted_at.astimezone(tenancy_selectors.tenant_timezone())
    assert local.date() == date(2026, 10, 7)


def test_an_unknown_method_lands_under_the_utilitys_other(brazos, rosa, usp):
    assert _call(brazos, "payments", body=_payment(method="DRIVEUP")).status_code == 200
    with tenant_ctx(brazos):
        (payment,) = _payments(brazos)
        assert payment.method.code == "other"
        row = models.IntegrationTargetReference.objects.get(tenant=brazos, target_key=USP, external_value="DRIVEUP")
        assert row.local_value is None, "a red row for a clerk, never a refusal"


def test_a_payment_for_an_account_we_cannot_find_is_200_parked_and_alerted(brazos, rosa, monkeypatch):
    """D2's residue — landed, nothing posted, a clerk told."""
    alerts = []
    from apps.integrations.seams import notifications as notifications_seam

    monkeypatch.setattr(notifications_seam, "queue_staff_alert", lambda **kw: alerts.append(kw))
    answer = _call(brazos, "payments", body=_payment(account="CLOSED-1"))
    assert answer.status_code == 200
    with tenant_ctx(brazos):
        assert _payments(brazos) == []
        event = payment_models.PaymentWebhookEvent.objects.get(tenant=brazos, provider=USP)
        assert event.status == payment_models.WEBHOOK_REFUSED
        assert event.outcome == "account_not_found"
    assert len(alerts) == 1 and alerts[0]["actor"] is None


def test_an_internal_failure_is_500_keeps_nothing_and_the_resend_posts(brazos, rosa, monkeypatch):
    from apps.payments import agent_door

    real = agent_door.post_payment
    calls = {"n": 0}

    def once_broken(**kw):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("the database went away")
        return real(**kw)

    monkeypatch.setattr(agent_door, "post_payment", once_broken)
    assert _call(brazos, "payments", body=_payment()).status_code == 500
    with tenant_ctx(brazos):
        assert not payment_models.PaymentWebhookEvent.objects.filter(tenant=brazos).exists()
    assert _call(brazos, "payments", body=_payment()).status_code == 200, "a first delivery, not a 409"
    with tenant_ctx(brazos):
        assert len(_payments(brazos)) == 1


def test_us_payments_money_never_enters_the_new_world_receipts(brazos, rosa):
    from apps.integrations.seams import payments as payments_seam

    _call(brazos, "payments", body=_payment())
    with tenant_ctx(brazos):
        assert len(_payments(brazos)) == 1
        online = payments_seam.collectable(origin=payments_seam.ORIGIN_ONLINE)
        assert online.count() == 0, "D3 — the New World feed selects `webhook` and only `webhook`"


# ══════════════════════════════════════════════════════════════════════════
# A return
# ══════════════════════════════════════════════════════════════════════════


def test_a_return_reverses_releases_and_stores_the_bank_code(brazos, rosa):
    _account, july, august = rosa
    assert _call(brazos, "payments", body=_payment(amount=147.85, method="ACHCHECK")).status_code == 200
    with tenant_ctx(brazos):
        assert _open(july) == 0 and _open(august) == 0
    answer = _call(brazos, "returns", body=_return(amount=147.85, code="R01"))
    assert answer.status_code == 200, answer.content
    with tenant_ctx(brazos):
        original, reversal_row = _payments(brazos)
        assert reversal_row.reverses_payment_id == original.pk, "the original is kept"
        assert reversal_row.amount == Decimal("-147.8500")
        assert reversal_row.return_code == "R01"
        assert reversal_row.reversal_reason == payment_models.REVERSAL_REASON_NSF
        assert _open(july) == Decimal("45.0000") and _open(august) == Decimal("102.8500")
        assert july.due_date == date(2026, 7, 22), "due again from its OWN due date"
    assert _json(_lookup(brazos, ROSA))["amountDue"] == Decimal("147.85")


def test_a_replayed_return_is_409(brazos, rosa):
    _call(brazos, "payments", body=_payment(amount=147.85))
    assert _call(brazos, "returns", body=_return(amount=147.85)).status_code == 200
    assert _call(brazos, "returns", body=_return(amount=147.85)).status_code == 409
    with tenant_ctx(brazos):
        assert len(_payments(brazos)) == 2


def test_a_return_before_its_payment_is_503_keeps_nothing_and_alerts_on_the_third(brazos, rosa, monkeypatch):
    alerts = []
    from apps.integrations.seams import notifications as notifications_seam

    monkeypatch.setattr(notifications_seam, "queue_staff_alert", lambda **kw: alerts.append(kw))
    for attempt in range(1, 5):
        answer = _call(brazos, "returns", body=_return())
        assert answer.status_code == 503, attempt
        assert len(alerts) == (1 if attempt >= inbound.NOT_YET_ALERT_AT else 0), attempt
    with tenant_ctx(brazos):
        assert not payment_models.PaymentWebhookEvent.objects.filter(tenant=brazos).exists()
    _call(brazos, "payments", body=_payment())
    assert _call(brazos, "returns", body=_return()).status_code == 200, "the resend now lands"


def test_a_return_larger_than_its_payment_or_on_another_account_is_400(brazos, rosa):
    _call(brazos, "payments", body=_payment(amount=100.00))
    assert _call(brazos, "returns", body=_return(amount=100.01)).status_code == 400
    assert _call(brazos, "returns", body=_return(amount=100.00, account="00099999")).status_code == 400
    with tenant_ctx(brazos):
        assert len(_payments(brazos)) == 1
        assert payment_models.PaymentWebhookEvent.objects.filter(tenant=brazos).count() == 1


# ══════════════════════════════════════════════════════════════════════════
# Switching it on
# ══════════════════════════════════════════════════════════════════════════


def test_switching_on_is_refused_until_other_is_mapped_and_then_suggests(brazos, dana):
    from core import errors

    with tenant_ctx(brazos):
        for code, name in (("cash", "Cash"), ("card", "Card"), ("other", "Other")):
            _method(brazos, code, name)
        with pytest.raises(errors.BizError) as refused:
            services.connect_with_fields(actor=dana, tenant_id=brazos.id, provider_key=USP, **CONNECT)
        assert refused.value.message_key == "integrations.refusal.fallback_unmapped"
        assert not models.IntegrationConnection.objects.filter(tenant=brazos, provider_key=USP).exists()
        mappings.set_rows(
            actor=dana,
            tenant_id=brazos.id,
            provider_key=USP,
            rows=[{"entity_type": "tender", "external_value": "OTHER", "local_value": "other"}],
        )
        from apps.tenancy.models import PaymentMethod

        PaymentMethod.objects.filter(tenant=brazos, code="ach").update(active=False)
        ours = set(
            PaymentMethod.objects.filter(tenant=brazos, active=True).values_list("code", flat=True)
        )
        services.connect_with_fields(actor=dana, tenant_id=brazos.id, provider_key=USP, **CONNECT)
        suggested = REGISTRY.require(USP).vocabularies[0].suggested
        for word, code in suggested.items():
            found = mappings.local_for(brazos.id, USP, "tender", word)
            if code in ours:
                assert found is not None and found["value"] == code, word
            else:
                assert found is None, f"{word}: nothing is created — {code} is not one of ours"
        assert mappings.local_for(brazos.id, USP, "tender", "ACHSAVINGS") is None
        assert mappings.local_for(brazos.id, USP, "tender", "APPLEPAY")["value"] == "card"


# ══════════════════════════════════════════════════════════════════════════
# PostgreSQL 16 — two identical payments at the same instant
# ══════════════════════════════════════════════════════════════════════════


@requires_postgres
@pytest.mark.django_db(transaction=True)
def test_pg_two_identical_payments_at_once_post_once_and_the_loser_gets_409(brazos, rosa):
    barrier = threading.Barrier(2)
    statuses: list[int] = []
    errors_seen: list[BaseException] = []

    def one():
        try:
            barrier.wait()
            statuses.append(_call(brazos, "payments", body=_payment()).status_code)
        except BaseException as caught:  # noqa: BLE001
            errors_seen.append(caught)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=one) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert not errors_seen, errors_seen
    assert sorted(statuses) == [200, 409], statuses
    with tenant_ctx(brazos):
        assert len(_payments(brazos)) == 1
        assert payment_models.PaymentWebhookEvent.objects.filter(tenant=brazos).count() == 1
