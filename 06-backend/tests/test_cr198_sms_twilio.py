"""`CR-198-BRC10` — text messages through ONE shared platform Twilio account.

PO 2026-10-29, verbatim: *"1A 2A 4B 5 US 6A(ONly Stop option is required), start"*.

WHAT EACH GROUP GUARDS, AND WHAT WOULD MAKE IT PASS WRONGLY (law 7, habit 2):

  * **Twilio's answers** — every case asserts OUR sentence, the retry verdict
    AND that no secret byte is in what a clerk reads. A test asserting only
    *ok is False* passes on an adapter that refuses everything.
  * **The signature** — the right signature is proved to PASS in the same
    file as every wrong one fails, and each failure asserts NOTHING WAS SAVED
    (the event table and the queue row both read back). A door that refused
    everything would pass every 401 case and fail the first one.
  * **Once per (message, status)** — `sent` then `delivered` must BOTH land;
    a door that deduped on the sid alone (the placeholder manifest's mistake)
    would land one and pass a test that only replayed `delivered`.
  * **STOP** — asserts the list row, the tick, the audit row AND that the next
    text is held — the fact the customer experiences.
  * **Isolation** — utility B's callback cannot move utility A's message, and
    a STOP reaches only a utility that has texted that number.

⚠ **NOTHING HERE REACHES TWILIO.** Every answer is a mocked HTTP transport.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone as dt_timezone
from urllib.parse import parse_qsl, urlencode

import pytest

from apps.integrations import platform_door, platform_sms
from apps.integrations.adapters import sms_twilio
from apps.integrations.adapters.base import ConnectionView
from apps.integrations.adapters.esp_email import HttpAnswer
from apps.integrations.registry import REGISTRY
from apps.integrations.seams import notifications as notifications_seam
from apps.notifications import models as nmodels
from apps.notifications import provider_seam, suppression
from apps.notifications.sms_feedback_models import ProviderStatusEvent
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

ACCOUNT = "AC" + "a" * 32
TOKEN = "tok_" + "9" * 28
SERVICE = "MG" + "b" * 32
BASE = "https://api-sand.example.test"
NUMBER = "+14025551049"
TYPED = "(402) 555-1049"
NOW = datetime(2026, 10, 29, 15, 0, tzinfo=dt_timezone.utc)


@pytest.fixture()
def twilio(settings):
    """The platform's account, configured — every secret a recognisable string
    so a leak can be grepped for."""
    settings.TWILIO_ACCOUNT_SID = ACCOUNT
    settings.TWILIO_AUTH_TOKEN = TOKEN
    settings.TWILIO_API_KEY_SID = ""
    settings.TWILIO_API_KEY_SECRET = ""
    settings.TWILIO_MESSAGING_SERVICE_SID = SERVICE
    settings.TWILIO_FROM_NUMBER = ""
    settings.TWILIO_SENDER_BY_UTILITY = ""
    settings.TWILIO_API_BASE_URL = "https://api.twilio.com"
    settings.PUBLIC_API_BASE_URL = BASE
    return settings


@pytest.fixture()
def no_twilio(settings):
    for name in (
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "TWILIO_API_KEY_SID",
        "TWILIO_API_KEY_SECRET",
        "TWILIO_MESSAGING_SERVICE_SID",
        "TWILIO_FROM_NUMBER",
        "TWILIO_SENDER_BY_UTILITY",
        "PUBLIC_API_BASE_URL",
    ):
        setattr(settings, name, "")
    return settings


class FakeTwilio:
    """A transport that records each request and answers what it is told."""

    def __init__(self, status=201, body=None):
        self.calls: list[dict] = []
        self.status = status
        self.body = body if body is not None else {"sid": "SM" + "1" * 32, "status": "queued"}

    def __call__(self, method, url, headers, payload, timeout_s):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers),
                "form": dict(parse_qsl((payload or b"").decode())),
            }
        )
        return HttpAnswer(status=self.status, body=self.body, text=str(self.body))


def _view(**config):
    base = {"base_url": "https://api.twilio.com", "account_sid": ACCOUNT}
    base.update(config)
    return ConnectionView(provider_key="sms_twilio", environment="production", config=base)


SECRETS = {"account_sid": ACCOUNT, "auth_token": TOKEN, "api_key_sid": "", "api_key_secret": ""}


# ══════════════════════════════════════════════════════════════════════════
# 1 · Twilio's answers, through a mocked HTTP layer
# ══════════════════════════════════════════════════════════════════════════


def test_a_sent_text_is_form_encoded_with_one_sender_and_keeps_the_sid():
    fake = FakeTwilio()
    adapter = sms_twilio.SmsTwilioAdapter(transport=fake)
    result = adapter.execute(
        _view(messaging_service_sid=SERVICE, from_number="+15550001111", status_callback=BASE + "/cb"),
        SECRETS,
        [{"ref": "r1", "address": NUMBER, "body": "Your bill is ready."}],
    )
    (item,) = result.items
    assert item.outcome == "succeeded"
    assert item.provider_reference == "SM" + "1" * 32
    (call,) = fake.calls
    assert call["method"] == "POST"
    assert call["url"] == f"https://api.twilio.com/2010-04-01/Accounts/{ACCOUNT}/Messages.json"
    assert call["headers"]["Content-Type"] == "application/x-www-form-urlencoded"
    assert call["headers"]["Authorization"].startswith("Basic ")
    # EXACTLY ONE sender — the Messaging Service wins when both are present.
    assert call["form"]["MessagingServiceSid"] == SERVICE
    assert "From" not in call["form"]
    assert call["form"]["To"] == NUMBER
    assert call["form"]["StatusCallback"] == BASE + "/cb"


def test_a_from_number_is_used_when_no_messaging_service_is_set():
    fake = FakeTwilio()
    sms_twilio.SmsTwilioAdapter(transport=fake).execute(
        _view(from_number="+15550001111"), SECRETS, [{"ref": "r", "address": NUMBER, "body": "Hi"}]
    )
    form = fake.calls[0]["form"]
    assert form["From"] == "+15550001111" and "MessagingServiceSid" not in form
    assert "StatusCallback" not in form, "no public address ⇒ no callback asked for"


@pytest.mark.parametrize(
    ("status", "code", "sentence", "retryable"),
    [
        (401, 20003, sms_twilio.WRONG_LOGIN, True),
        (400, 21211, sms_twilio.BAD_NUMBER, False),
        (400, 21608, sms_twilio.TRIAL_ACCOUNT, False),
        (400, 21610, sms_twilio.OPTED_OUT, False),
    ],
)
def test_each_twilio_refusal_reads_as_our_sentence_with_their_words_under_it(
    status, code, sentence, retryable
):
    fake = FakeTwilio(
        status=status,
        body={"code": code, "message": f"refused with {TOKEN} echoed", "status": status},
    )
    (item,) = (
        sms_twilio.SmsTwilioAdapter(transport=fake)
        .execute(_view(messaging_service_sid=SERVICE), SECRETS, [{"ref": "r", "address": NUMBER, "body": "x"}])
        .items
    )
    assert item.outcome == "failed"
    assert item.detail == sentence
    assert item.retryable is retryable
    assert item.provider_code == str(code)
    assert str(code) in (item.provider_text or "")
    # The secret Twilio echoed back never reaches a clerk.
    assert TOKEN not in (item.provider_text or "") and TOKEN not in (item.detail or "")


def test_the_login_check_reads_the_account_and_texts_nobody():
    fake = FakeTwilio(status=200, body={"sid": ACCOUNT, "status": "active", "type": "Full"})
    (item,) = (
        sms_twilio.SmsTwilioAdapter(transport=fake)
        .execute(_view(), SECRETS, [{"ref": "v", "operation": "validate_credentials"}])
        .items
    )
    assert item.outcome == "succeeded" and item.detail == sms_twilio.LOGIN_OK
    assert fake.calls[0]["method"] == "GET"
    assert fake.calls[0]["url"].endswith(f"/2010-04-01/Accounts/{ACCOUNT}.json")


def test_a_201_with_no_sid_is_not_a_success():
    fake = FakeTwilio(status=201, body={})
    (item,) = (
        sms_twilio.SmsTwilioAdapter(transport=fake)
        .execute(_view(messaging_service_sid=SERVICE), SECRETS, [{"ref": "r", "address": NUMBER, "body": "x"}])
        .items
    )
    assert item.outcome == "failed"


def test_the_status_words_map_to_ours():
    assert {w: sms_twilio.map_status(w) for w in ("queued", "sending", "sent")} == {
        "queued": "in_transit",
        "sending": "in_transit",
        "sent": "in_transit",
    }
    assert sms_twilio.map_status("delivered") == "delivered"
    assert sms_twilio.map_status("undelivered") == "failed"
    assert sms_twilio.map_status("failed") == "failed"


def test_only_stop_words_are_stop():
    for word in ("STOP", "stop ", "StopAll", "UNSUBSCRIBE", "cancel", "END", "quit"):
        assert sms_twilio.is_stop(word), word
    for word in ("START", "HELP", "yes", "stop please"):
        assert not sms_twilio.is_stop(word), word
    assert sms_twilio.is_stop("arrêt", "STOP"), "Twilio's own OptOutType=STOP counts"


# ══════════════════════════════════════════════════════════════════════════
# 2 · Routing: lifted only when the platform is configured; fails closed
# ══════════════════════════════════════════════════════════════════════════


def test_the_card_is_live_and_held_by_the_platform():
    manifest = REGISTRY.require("sms_twilio")
    assert manifest.disposition.kind == "live"
    assert manifest.auth.mode == "platform_holds_ours"
    assert REGISTRY.adapter_for("sms_twilio") is sms_twilio.SmsTwilioAdapter
    assert "sms" not in provider_seam.DEFERRED_UNTIL, "the v1.1 deferral is SUPERSEDED"


def test_with_credentials_sms_is_dispatchable_and_without_them_it_is_not(brazos, twilio):
    with tenant_ctx(brazos):
        route = provider_seam.channel_route("sms", active=True)
        assert route.dispatchable is True
        status = provider_seam.provider_status("sms")
        assert status["connected"] is True and status["provider_name"] == "Twilio"
        # The utility's own switch still decides.
        off = provider_seam.channel_route("sms", active=False)
        assert off.dispatchable is False and off.problem["deferred_until"] is None
    for name in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN"):
        setattr(twilio, name, "")
    with tenant_ctx(brazos):
        route = provider_seam.channel_route("sms", active=True)
        assert route.dispatchable is False
        assert route.problem["code"] == provider_seam.ROUTE_PROVIDER_STATUS_UNKNOWN


def test_no_credentials_fail_closed_and_dial_nobody(brazos, no_twilio, monkeypatch):
    fake = FakeTwilio()
    monkeypatch.setattr(sms_twilio, "_urllib_transport", fake)
    with tenant_ctx(brazos):
        answer = notifications_seam.dispatch_outbound_batch(
            "sms", ({"id": "m1", "address": TYPED, "artifact": {"body": "Hi"}},)
        )
    assert answer["m1"]["status"] == "failed" and answer["m1"]["retryable"] is True
    assert fake.calls == []


def test_a_batch_goes_through_the_platform_account_and_keeps_the_sid(brazos, twilio, monkeypatch):
    fake = FakeTwilio()
    monkeypatch.setattr(sms_twilio, "_urllib_transport", fake)
    with tenant_ctx(brazos):
        answer = notifications_seam.dispatch_outbound_batch(
            "sms",
            (
                {"id": "m1", "address": TYPED, "artifact": {"body": "Past due $42.18"}},
                {"id": "m2", "address": "not a phone", "artifact": {"body": "x"}},
            ),
        )
    assert answer["m1"] == {
        "status": "sent",
        "provider_reference": "SM" + "1" * 32,
        "response": {"provider": "sms_twilio"},
    }
    assert answer["m2"]["status"] == "failed" and answer["m2"]["retryable"] is False
    (call,) = fake.calls
    assert call["form"]["To"] == NUMBER, "a typed number is sent in E.164"
    assert call["form"]["StatusCallback"] == (
        f"{BASE}/api/{brazos.subdomain}/integrations/platform/sms_twilio/status"
    )


def test_one_hand_off_is_capped_at_the_providers_minute(twilio):
    assert provider_seam.batch_limit("sms", 500) == 60
    assert provider_seam.batch_limit("email", 500) == 500


def test_a_utility_on_the_servers_map_sends_from_its_own_sender(brazos, lonestar, twilio):
    twilio.TWILIO_SENDER_BY_UTILITY = f"{brazos.subdomain}:MG{'c' * 32}"
    assert platform_sms.sender_for(brazos.subdomain).value == "MG" + "c" * 32
    assert platform_sms.sender_for(lonestar.subdomain).value == SERVICE


def test_a_utility_cannot_connect_the_platform_card(brazos, dana):
    from apps.integrations import services
    from core import errors

    with tenant_ctx(brazos), pytest.raises(errors.BizError) as refused:
        services.connect_with_fields(
            actor=dana,
            tenant_id=brazos.id,
            provider_key="sms_twilio",
            environment="production",
            cadence="manual",
            label=None,
            fields={"account_sid": ACCOUNT, "auth_token": TOKEN},
        )
    assert refused.value.message_key == services.REFUSAL_PLATFORM_PROVIDED


def test_the_card_read_serves_no_secret(brazos, dana, twilio):
    from apps.integrations import platform_api
    from tests.test_us_ten_helpers import api_call

    response = api_call(
        platform_api.platform_card,
        "get",
        f"/api/{brazos.subdomain}/integrations/sms_twilio/platform",
        user=dana.user if hasattr(dana, "user") else dana,
        role="system_admin",
        tenant=brazos,
        key="sms_twilio",
    )
    assert response.status_code == 200
    text = str(response.data)
    for secret in (ACCOUNT, TOKEN, SERVICE):
        assert secret not in text
    assert response.data["configured"] is True
    assert response.data["provided_by_platform"] is True
    assert response.data["sender_hint"] == "••••" + SERVICE[-4:]


# ══════════════════════════════════════════════════════════════════════════
# 3 · The status door: signature, once per (message, status), isolation
# ══════════════════════════════════════════════════════════════════════════


def _sent_text(tenant, *, sid="SM" + "7" * 32, address=TYPED, account=None):
    return nmodels.OutboundMessage.objects.create(
        tenant_id=tenant.id,
        source_type="account",
        source_id=uuid.uuid4(),
        channel=nmodels.CHANNEL_SMS,
        template_code="past_due_reminder",
        template_id=uuid.uuid4(),
        template_version=1,
        recipient_address=address,
        status=nmodels.STATUS_SENT,
        provider_reference=sid,
        account=account,
    )


def _post(view, path, fields, *, token=TOKEN, url=None, tenant=None, tamper=None):
    from rest_framework.test import APIRequestFactory

    pairs = list(fields.items())
    signature = platform_door.expected_signature(token, url or (BASE + path), pairs)
    sent = dict(fields)
    if tamper:
        sent.update(tamper)
    request = APIRequestFactory().post(
        path,
        data=urlencode(list(sent.items())),
        content_type="application/x-www-form-urlencoded",
        HTTP_X_TWILIO_SIGNATURE=signature,
    )
    if tenant is not None:
        request.tenant_id = tenant.id
        with tenant_ctx(tenant):
            return view(request)
    return view(request)


def _status(tenant, fields, **kwargs):
    from apps.integrations import platform_api

    path = f"/api/{tenant.subdomain}/integrations/platform/sms_twilio/status"
    return _post(platform_api.twilio_status, path, fields, tenant=tenant, **kwargs)


def _events(tenant):
    with tenant_ctx(tenant):
        # Filtered by tenant AS WELL AS scoped by context: the suite runs on
        # SQLite, which has no RLS, so the context alone would read every row.
        return list(
            ProviderStatusEvent.objects.filter(tenant_id=tenant.id)
            .order_by("created_at")
            .values_list("event_key", flat=True)
        )


def test_a_signed_delivered_moves_the_text_and_is_audited(brazos, twilio, audit_rows):
    with tenant_ctx(brazos):
        row = _sent_text(brazos)
    response = _status(brazos, {"MessageSid": row.provider_reference, "MessageStatus": "delivered"})
    assert response.status_code == 200
    with tenant_ctx(brazos):
        row.refresh_from_db()
    assert row.status == nmodels.STATUS_DELIVERED
    assert "delivery.status_reported" in [one["action"] for one in audit_rows]


@pytest.mark.parametrize(
    "how",
    ["wrong_token", "changed_field", "wrong_url", "no_header", "no_public_address"],
)
def test_a_bad_signature_is_401_and_nothing_is_saved(brazos, twilio, how):
    from apps.integrations import platform_api
    from rest_framework.test import APIRequestFactory

    with tenant_ctx(brazos):
        row = _sent_text(brazos)
    fields = {"MessageSid": row.provider_reference, "MessageStatus": "delivered"}
    path = f"/api/{brazos.subdomain}/integrations/platform/sms_twilio/status"
    if how == "wrong_token":
        response = _status(brazos, fields, token="not-the-token")
    elif how == "changed_field":
        response = _status(brazos, fields, tamper={"MessageStatus": "failed"})
    elif how == "wrong_url":
        response = _status(brazos, fields, url="https://evil.example" + path)
    elif how == "no_header":
        request = APIRequestFactory().post(
            path, data=urlencode(fields), content_type="application/x-www-form-urlencoded"
        )
        request.tenant_id = brazos.id
        with tenant_ctx(brazos):
            response = platform_api.twilio_status(request)
    else:
        twilio.PUBLIC_API_BASE_URL = ""
        response = _status(brazos, fields)
    assert response.status_code == 401
    assert _events(brazos) == []
    with tenant_ctx(brazos):
        row.refresh_from_db()
    assert row.status == nmodels.STATUS_SENT


def test_sent_then_delivered_both_land_and_a_repeat_lands_once(brazos, twilio):
    with tenant_ctx(brazos):
        row = _sent_text(brazos)
    sid = row.provider_reference
    for status in ("sent", "delivered", "delivered"):
        assert _status(brazos, {"MessageSid": sid, "MessageStatus": status}).status_code == 200
    assert _events(brazos) == [f"{sid}|sent", f"{sid}|delivered"]


def test_a_failed_text_keeps_twilios_error_code(brazos, twilio):
    with tenant_ctx(brazos):
        row = _sent_text(brazos)
    _status(
        brazos,
        {
            "MessageSid": row.provider_reference,
            "MessageStatus": "undelivered",
            "ErrorCode": "30003",
            "ErrorMessage": "Unreachable destination handset",
        },
    )
    with tenant_ctx(brazos):
        row.refresh_from_db()
    assert row.status == nmodels.STATUS_FAILED
    assert "30003" in row.last_error


def test_utility_b_cannot_move_utility_as_text(brazos, lonestar, twilio):
    with tenant_ctx(brazos):
        row = _sent_text(brazos)
    # Lonestar's address, signed correctly, naming Brazos's sid.
    response = _status(lonestar, {"MessageSid": row.provider_reference, "MessageStatus": "failed"})
    assert response.status_code == 200
    with tenant_ctx(brazos):
        row.refresh_from_db()
    assert row.status == nmodels.STATUS_SENT
    assert _events(brazos) == []


# ══════════════════════════════════════════════════════════════════════════
# 4 · STOP: the list, the tick (audited), and the next text held
# ══════════════════════════════════════════════════════════════════════════


def _account_with_texts(tenant, actor):
    from apps.customers import models as customer_models
    from tests.test_us_met_helpers import make_premises, make_unit

    status = customer_models.AccountStatus.objects.get(tenant=tenant, code="active")
    premises = make_premises(actor, address_line="12 Pecan St", services_available=["water"])
    unit = make_unit(actor, premises["id"], label="1", services=["water"])
    account = customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        account_no="A-20498",
        status=status,
        account_type=customer_models.AccountType.objects.first(),
        sms_reminders=True,
    )
    customer_models.Contact.objects.create(
        tenant=tenant, account=account, full_name="Rao, Arjun", is_primary=True, phone=TYPED
    )
    return account


def _reply(fields, **kwargs):
    from apps.integrations import platform_api

    return _post(platform_api.twilio_reply, "/api/hooks/twilio/reply", fields, **kwargs)


def test_stop_lists_the_number_turns_the_tick_off_and_holds_the_next_text(
    brazos, dana, twilio, audit_rows
):
    from apps.customers import models as customer_models

    with tenant_ctx(brazos):
        account = _account_with_texts(brazos, dana)
        _sent_text(brazos, account=account)
        waiting = nmodels.OutboundMessage.objects.create(
            tenant_id=brazos.id,
            source_type="account",
            source_id=uuid.uuid4(),
            channel=nmodels.CHANNEL_SMS,
            template_code="past_due_reminder",
            template_id=uuid.uuid4(),
            template_version=1,
            recipient_address="402.555.1049",
            status=nmodels.STATUS_QUEUED,
            account=account,
        )
    response = _reply(
        {"MessageSid": "SM" + "5" * 32, "From": NUMBER, "To": "+15550001111",
         "MessagingServiceSid": SERVICE, "Body": "STOP"}
    )
    assert response.status_code == 200
    assert "<Response>" in response.content.decode()
    with tenant_ctx(brazos):
        assert suppression.is_suppressed(channel="sms", address=TYPED) is True
        assert customer_models.Account.objects.get(pk=account.pk).sms_reminders is False
        waiting.refresh_from_db()
        assert waiting.held is True and waiting.held_reason == suppression.HELD_SUPPRESSED
        from apps.customers.selectors import _text_recipient

        fresh = customer_models.Account.objects.get(pk=account.pk)
        assert _text_recipient(fresh, None, "Arjun")["unavailable_reason"] == "no_sms_opt_in"
    actions = [one["action"] for one in audit_rows]
    assert "account.sms_reminders_turned_off" in actions
    assert "delivery.suppressed" in actions
    # A retried STOP lands once and changes nothing more.
    _reply(
        {"MessageSid": "SM" + "5" * 32, "From": NUMBER, "To": "+15550001111",
         "MessagingServiceSid": SERVICE, "Body": "STOP"}
    )
    assert _events(brazos) == ["SM" + "5" * 32 + "|reply"]


@pytest.mark.parametrize("word", ["START", "HELP", "thanks"])
def test_start_help_and_chat_are_not_acted_on(brazos, dana, twilio, word):
    with tenant_ctx(brazos):
        _sent_text(brazos)
    response = _reply(
        {"MessageSid": "SM" + "6" * 32, "From": NUMBER, "To": "+1555", "MessagingServiceSid": SERVICE,
         "Body": word}
    )
    assert response.status_code == 200
    with tenant_ctx(brazos):
        assert suppression.is_suppressed(channel="sms", address=NUMBER) is False


def test_an_unsigned_stop_is_refused_and_changes_nothing(brazos, dana, twilio):
    with tenant_ctx(brazos):
        _sent_text(brazos)
    response = _reply(
        {"MessageSid": "SM" + "8" * 32, "From": NUMBER, "To": "+1555", "MessagingServiceSid": SERVICE,
         "Body": "STOP"},
        token="forged",
    )
    assert response.status_code == 401
    with tenant_ctx(brazos):
        assert suppression.is_suppressed(channel="sms", address=NUMBER) is False


def test_a_stop_reaches_only_a_utility_that_texted_that_number(brazos, lonestar, twilio):
    with tenant_ctx(brazos):
        _sent_text(brazos)
    _reply(
        {"MessageSid": "SM" + "9" * 32, "From": NUMBER, "To": "+1555", "MessagingServiceSid": SERVICE,
         "Body": "STOP"}
    )
    with tenant_ctx(brazos):
        assert suppression.is_suppressed(channel="sms", address=NUMBER) is True
    with tenant_ctx(lonestar):
        assert suppression.is_suppressed(channel="sms", address=NUMBER) is False
        assert list(ProviderStatusEvent.objects.filter(tenant_id=lonestar.id)) == []


def test_a_stop_to_another_utilitys_own_sender_does_not_reach_this_one(brazos, lonestar, twilio):
    own = "MG" + "d" * 32
    twilio.TWILIO_SENDER_BY_UTILITY = f"{lonestar.subdomain}:{own}"
    with tenant_ctx(brazos):
        _sent_text(brazos)
    _reply(
        {"MessageSid": "SM" + "4" * 32, "From": NUMBER, "To": "+1555", "MessagingServiceSid": own,
         "Body": "STOP"}
    )
    with tenant_ctx(brazos):
        assert suppression.is_suppressed(channel="sms", address=NUMBER) is False


def test_twilio_21610_on_a_send_is_the_same_fact_as_stop(brazos, dana, twilio):
    from apps.customers import models as customer_models

    with tenant_ctx(brazos):
        account = _account_with_texts(brazos, dana)
        row = _sent_text(brazos, account=account)
    _status(
        brazos,
        {"MessageSid": row.provider_reference, "MessageStatus": "failed", "ErrorCode": "21610"},
    )
    with tenant_ctx(brazos):
        assert suppression.is_suppressed(channel="sms", address=NUMBER) is True
        assert customer_models.Account.objects.get(pk=account.pk).sms_reminders is False
