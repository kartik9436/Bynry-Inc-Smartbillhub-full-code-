# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-NOT-10537 (the rules matrix still said print, email and text
#           "none of them leaves the building" while email sends) and its
#           sibling sentences, swept by lane NOT-SENT-SWEEP
# Ruling:   PO 2026-10-22, *"A. Each channel tells the clerk the truth about
#           itself, in one short line."* (decision log, *The four placement
#           details …* item 4, and the NOT-SENT-SWEEP judgments entry)
# ───────────────────────────────────────────────────────
"""Every server sentence that said nothing leaves the building, asked again
with a mail server connected.

The worked case is the decision log's: email switched on, Custom SMTP
`smtp.office365.com` connected and able to send, text messages off, no print
vendor. On that deployment an email test DOES go out, so a sentence saying it
will not is false, and each case below asserts the sentence is gone and the
live state is served in its place.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from apps.customers import notifications_seam
from apps.notifications import rules_api, seed_templates, settings_api, templates_api
from tests.test_us_int_helpers_b import *  # noqa: F401,F403 — smtp_adapter
from tests.test_us_int_helpers_b import (
    GOOD_PASSWORD,
    post_connect,
    post_credential,
    smtp_adapter,  # noqa: F401 — a FIXTURE
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_ten_helpers import api_call

# Imported AFTER the star imports, which export integrations' own `models`.
from apps.notifications import models as notification_models  # noqa: E402

pytestmark = pytest.mark.django_db

CONNECTOR_FIELDS = {
    "host": "smtp.office365.com",
    "port": "587",
    "username": "billing@springfieldwater.example",
    "password": GOOD_PASSWORD,
    "send_from": "billing@springfieldwater.example",
}

#: The claims this sweep removed. None may be served on a deployment that sends.
FALSE_CLAIMS = (
    "leaves the building",
    "leave the building",
    "not switched on yet",
    "sending is not switched on",
    "no provider is connected",
    "no mail provider",
    "delivered by the product itself",
    "no delivery adapter",
    "until an adapter",
)


def _email_on(tenant, *, connect: bool, actor=None) -> None:
    if connect:
        assert post_connect(tenant, actor, "email_smtp", CONNECTOR_FIELDS).status_code == 201
        post_credential(tenant, actor, "email_smtp", {"password": GOOD_PASSWORD})
    with tenant_ctx(tenant):
        row, _ = notification_models.NotificationSettings.objects.get_or_create(tenant_id=tenant.pk)
        row.email_dispatch_active = True
        row.save()


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for one in value.values():
            yield from _strings(one)
    elif isinstance(value, (list, tuple)):
        for one in value:
            yield from _strings(one)


def _assert_no_false_claim(payload) -> None:
    for text in _strings(payload):
        for claim in FALSE_CLAIMS:
            assert claim not in text.lower(), f"{claim!r} is still served: {text!r}"


def _call(view, method, tenant, actor, **kwargs):
    return api_call(view, method, user=actor.user, role="system_admin", tenant=tenant, **kwargs)


# ── 1 · the rules matrix — DEF-NOT-10537 itself ────────────────────────────
def test_the_rules_matrix_serves_no_release_sentence_and_names_email_as_sending(
    brazos, dana, smtp_adapter
):
    _email_on(brazos, connect=True, actor=dana)
    with tenant_ctx(brazos):
        response = _call(rules_api.notification_rules, "get", brazos, dana)
    assert response.status_code == 200
    assert "no_dispatcher_reason" not in response.data
    # Derived from the dispatcher's own verdict, never a hard-coded list.
    assert notification_models.CHANNEL_EMAIL in response.data["dispatchable_channels"]
    assert notification_models.CHANNEL_IN_APP in response.data["dispatchable_channels"]
    assert notification_models.CHANNEL_SMS not in response.data["dispatchable_channels"]
    _assert_no_false_claim(response.data)


def test_the_rule_rail_keeps_the_fact_and_drops_the_false_reason(brazos, dana):
    with tenant_ctx(brazos):
        response = _call(rules_api.notification_rule, "get", brazos, dana, event_key="bill_ready")
    assert response.data["delivery_counts_available"] is False
    assert response.data["delivery_counts_reason"] == "No provider reports these back yet."
    assert "no_dispatcher_reason" not in response.data
    # `last_30_days`' own refusals are NOT asserted here: `delivery_counts`
    # already picks them from the tenant's live connection (CR-069 wave F).


# ── 2 · "Send test" on the rules page ──────────────────────────────────────
def test_a_rules_test_on_a_sending_channel_says_it_will_be_delivered(brazos, dana, smtp_adapter):
    _email_on(brazos, connect=True, actor=dana)
    with tenant_ctx(brazos):
        response = _call(
            rules_api.queue_test_message,
            "post",
            brazos,
            dana,
            event_key="bill_ready",
            data={"channel": notification_models.CHANNEL_EMAIL},
        )
    assert response.status_code == 200, response.data
    assert response.data["queued"] is True
    assert response.data["dispatchable"] is True
    assert response.data["will_be_delivered"] is True
    assert response.data["channel_line"] == {
        "channel": "email",
        "state": "sending",
        "provider": "Custom SMTP",
        "host": "smtp.office365.com",
    }


def test_a_rules_test_with_no_mail_server_carries_that_line(brazos, dana):
    _email_on(brazos, connect=False)
    with tenant_ctx(brazos):
        response = _call(
            rules_api.queue_test_message,
            "post",
            brazos,
            dana,
            event_key="bill_ready",
            data={"channel": notification_models.CHANNEL_EMAIL},
        )
    assert response.data["queued"] is True
    assert response.data["will_be_delivered"] is False
    assert response.data["channel_line"]["state"] == "noMailServer"


# ── 3 · "Send test to me" on the template page ─────────────────────────────
def _seed(actor):
    seed_templates.seed_notice_templates(actor, on_date=date(2026, 8, 30))


def test_the_template_offer_on_a_sending_email_channel_is_true(brazos, dana, smtp_adapter):
    _email_on(brazos, connect=True, actor=dana)
    with tenant_ctx(brazos):
        _seed(dana)
        detail = _call(templates_api.template_detail, "get", brazos, dana, code="email_bill_ready")
        result = _call(
            templates_api.queue_template_test, "post", brazos, dana, code="email_bill_ready"
        )
    assert detail.data["test_send_label"] == "Sends to you"
    assert dana.user.email in detail.data["test_send_reason"]
    assert "next send" in detail.data["test_send_reason"]
    _assert_no_false_claim([detail.data["test_send_reason"], detail.data["test_send_label"]])
    assert result.data["will_be_delivered"] is True
    assert result.data["channel_line"]["state"] == "sending"


def test_the_template_offer_on_a_switched_off_channel_names_no_provider(brazos, dana):
    with tenant_ctx(brazos):
        _seed(dana)
        detail = _call(templates_api.template_detail, "get", brazos, dana, code="email_bill_ready")
        result = _call(
            templates_api.queue_template_test, "post", brazos, dana, code="email_bill_ready"
        )
    assert detail.data["test_send_label"] == "Queues, does not send"
    assert "waits on the queue" in detail.data["test_send_reason"]
    _assert_no_false_claim([detail.data["test_send_reason"]])
    assert result.data["channel_line"]["state"] == "off"


def test_the_in_app_offer_prints_no_user_id(brazos, dana):
    with tenant_ctx(brazos):
        _seed(dana)
        detail = _call(
            templates_api.template_detail, "get", brazos, dana, code="staff_bulk_summary"
        )
    reason = detail.data["test_send_reason"]
    assert str(dana.user.pk) not in reason, reason
    assert "your own messages" in reason
    _assert_no_false_claim([reason])


# ── 4 · the Settings read and the customers seam ───────────────────────────
def test_the_receipt_election_detail_makes_no_release_claim(brazos, dana):
    with tenant_ctx(brazos):
        response = _call(settings_api.notification_settings, "get", brazos, dana)
    _assert_no_false_claim(response.data["election_consumers"])


def test_the_customers_seam_outcomes_make_no_release_claim():
    message = SimpleNamespace(
        created=True, message_id="m-1", event_key="move_in_welcome", channels=("email",),
        problems=(), template_code="move_in_welcome", address="a@b.example", party="buyer",
    )
    outcomes = [
        *notifications_seam._outcome(message, what="welcome"),
        notifications_seam._applicant_outcome(message, what="letter"),
        notifications_seam._transfer_outcome(message, what="letter"),
    ]
    for outcome in outcomes:
        assert outcome["detail"].endswith("are all real."), outcome["detail"]
    _assert_no_false_claim([o["detail"] for o in outcomes])
