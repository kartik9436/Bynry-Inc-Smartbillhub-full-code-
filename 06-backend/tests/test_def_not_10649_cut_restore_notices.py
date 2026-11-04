# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-NOT-10649 — after *Mark as cut* the customer is told nothing,
#           and nothing when service is restored
# Ruling:   PO 2026-10-29, verbatim *"1 A, 2 A, 3 A, 4 A"* then *"start"*
#           (decision log *"A cut and a restoration TELL THE CUSTOMER"*):
#           (1) both messages · (2) email + SMS, each only where the customer
#           has it and (SMS) consented · (3) automatic, on by default,
#           switchable per utility · (4) a short default safety text the
#           utility edits. ONE shared pipeline; the account-message helper
#           extended to take channels rather than a second path.
# Rules:    CLAUDE.md hard rules 1, 2 (money 4dp stored / 2dp shown), 3 (the
#           closing reading WITH its unit), 6 (idempotent), 8 (the address is
#           walked from the premises) · hard-won law 14 (a savepoint, proved on
#           PostgreSQL where usable)
# ───────────────────────────────────────────────────────
"""A cut and a restoration tell the customer — by email, and by text where
they chose texts — through the one shared notification pipeline.

Every case here was run against the code BEFORE the fix and failed there
(red first, hard-won law 7); the lane report quotes the failures.
"""

from datetime import date
from decimal import Decimal as D

import pytest

from apps.customers import disconnects
from apps.customers import models as customers_models
from apps.customers import notifications_seam
from apps.notifications import catalogs, customer_events, rendering, rule_catalog, rule_service
from apps.notifications import models as notification_models
from apps.notifications import seed_templates

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import brazos, marcus, staff_actor, tenant_ctx  # noqa: F401
from tests.test_w7_cut_reconnect import CUT_ON, TODAY, _scheduled
from tests.test_w7_disconnects import _owes

pytestmark = pytest.mark.django_db

#: The worked figure put to the PO: $612.75 owed, the $75.00 fee issued at the
#: cut, so the position AFTER the cut is $687.75.
POSITION_AFTER_CUT = D("687.75")


@pytest.fixture(autouse=True)
def _fee_and_reads_at_the_boundary(monkeypatch):
    """The two other modules' answers, stubbed AT the customers seam.

    The fee is billing's to raise (BR-CUS-037); the closing reading is
    metering's to answer. Each is the module boundary, never their internals.
    """
    monkeypatch.setattr(
        disconnects.seams,
        "raise_and_issue_charge_fee",
        lambda *_a, **_k: {"invoice_id": None, "stubbed_at": "the customers/billing seam"},
    )
    monkeypatch.setattr(
        disconnects.seams,
        "reads_for_unit",
        lambda *_a, **_k: {
            "meters": [
                {
                    "asset_no": "E-5043",
                    "registers": [
                        {"current_value": "2645.000000", "unit": "kWh", "read_at": "2026-08-24"},
                        # An OLDER reading must not be printed as the closing one.
                        {"current_value": "2500.000000", "unit": "kWh", "read_at": "2026-07-31"},
                    ],
                }
            ]
        },
    )


def _reachable(account_id, *, email="rita@example.com", phone="+1 512 555 0142", sms=True):
    """Give the account's primary contact an email and a phone, and the
    account its SMS choice — the facts the recipient read decides on."""
    contact = customers_models.Contact.objects.filter(account_id=account_id).first()
    contact.email = email
    contact.phone = phone
    contact.save()
    customers_models.Account.objects.filter(id=account_id).update(sms_reminders=sms)


def _rows(tenant, **filters):
    return notification_models.OutboundMessage.objects.filter(
        tenant=tenant, source_type=customer_events.SOURCE_SERVICE_STATE, **filters
    )


def _cut(actor, tenant, monkeypatch, **reach):
    account = _scheduled(actor, tenant, monkeypatch, owed=POSITION_AFTER_CUT)
    if reach.pop("reachable", True):
        _reachable(account["id"], **reach)
    payload = disconnects.commit_cut(actor, account["id"], cut_on=CUT_ON, as_of=TODAY)
    return account, payload


# ════════════════════════════════════════════════════════════════════════════
# 1 · THE CUT TELLS THE CUSTOMER
# ════════════════════════════════════════════════════════════════════════════
def test_a_cut_queues_the_disconnected_email_and_text_with_the_figures_and_the_unit(
    brazos, marcus, monkeypatch
):
    with tenant_ctx(brazos):
        account, payload = _cut(marcus, brazos, monkeypatch)
        rows = _rows(brazos, account_id=account["id"], template_code__in=(
            customer_events.TEMPLATE_SERVICE_DISCONNECTED,
            customer_events.TEMPLATE_SERVICE_DISCONNECTED_SMS,
        ))
        by_channel = {row.channel: row for row in rows}
        assert set(by_channel) == {"email", "sms"}
        # 2A is email and SMS — no posted letter rides along (the walk of
        # 2026-10-29 found one when this queued under `account`'s print floor).
        assert not _rows(brazos, account_id=account["id"], channel="pdf_print").exists()
        assert by_channel["email"].recipient_address == "rita@example.com"
        assert by_channel["sms"].recipient_address == "+1 512 555 0142"

        email = rendering.render_for_dispatch(by_channel["email"])
        body = email.body
        # Hard rule 2 — 2dp shown, with the currency's mark.
        assert "$612.75" in body  # balance owed = position − fee
        assert "$75.00" in body  # the reconnection fee
        assert "$687.75" in body  # total to restore = the position
        # Hard rule 3 — the closing reading WITH its unit, and only the closing one.
        assert "E-5043: 2645 kWh" in body
        assert "2500" not in body
        # The safety text (ruling 4).
        assert "Do not reconnect" in body or "do not reconnect" in body.lower()
        assert email.subject

        text = rendering.render_for_dispatch(by_channel["sms"]).body
        assert "$687.75" in text

        # The cut's own answer says what was queued.
        queued = payload["notification_queued"]
        assert queued["event_key"] == "service_disconnected"
        assert sorted(queued["channels"]) == ["email", "sms"]


def test_the_figures_are_stored_at_four_places_and_carry_a_currency(brazos, marcus, monkeypatch):
    with tenant_ctx(brazos):
        account, _payload = _cut(marcus, brazos, monkeypatch)
        row = _rows(brazos, account_id=account["id"], channel="email").get()
        stored = rendering.decode_context(row.render_context)
        for token, figure in (
            ("balance_owed", "612.75"),
            ("reconnect_fee", "75.00"),
            ("total_to_restore", "687.75"),
        ):
            value = stored[token]
            assert isinstance(value, rendering.Money), token
            assert value.amount == D(figure), token
            assert value.currency == "USD", token


def test_without_sms_consent_no_text_is_addressed(brazos, marcus, monkeypatch):
    with tenant_ctx(brazos):
        account, _payload = _cut(marcus, brazos, monkeypatch, sms=False)
        sms = _rows(brazos, account_id=account["id"], channel="sms")
        # A row that SAYS why — the receipt's precedent — and no number to text.
        assert all(row.recipient_address in (None, "") for row in sms)
        assert {row.unavailable_reason for row in sms} <= {"no_sms_opt_in"}
        assert _rows(brazos, account_id=account["id"], channel="email").count() == 1


def test_switched_off_on_settings_nothing_is_written(brazos, marcus, monkeypatch):
    with tenant_ctx(brazos):
        admin = staff_actor(brazos, "system_admin")
        rule_service.update_rule(event_key="service_disconnected", actor=admin, enabled=False)
        account, payload = _cut(marcus, brazos, monkeypatch)
        assert not _rows(brazos, account_id=account["id"]).exists()
        assert payload["notification_queued"]["message_ids"] == []
        # The cut itself stands.
        assert payload["state"] == disconnects.STATE_CUT


def test_no_contact_writes_the_row_with_the_reason_and_sends_nothing(brazos, marcus, monkeypatch):
    with tenant_ctx(brazos):
        account, _payload = _cut(marcus, brazos, monkeypatch, reachable=False)
        email = _rows(brazos, account_id=account["id"], channel="email").get()
        assert not email.recipient_address
        assert email.unavailable_reason == "no_email_address"


def test_a_refused_cut_queues_nothing(brazos, marcus, monkeypatch):
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch, owed=POSITION_AFTER_CUT)
        _reachable(account["id"])
        with pytest.raises(disconnects.DisconnectRuleError):
            disconnects.commit_cut(
                marcus, account["id"], cut_on=date(2026, 8, 23), as_of=TODAY
            )
        assert not _rows(brazos, account_id=account["id"]).exists()


def test_a_cut_rolled_back_after_the_queue_leaves_no_message(brazos, marcus, monkeypatch):
    """The queue is INSIDE the cut's transaction: if the cut fails after it,
    the message goes with it — there is never a letter about a cut that did
    not happen."""
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch, owed=POSITION_AFTER_CUT)
        _reachable(account["id"])

        def _boom(*_a, **_k):
            raise RuntimeError("audit write failed")

        monkeypatch.setattr(disconnects, "_audit", _boom)
        with pytest.raises(RuntimeError):
            disconnects.commit_cut(marcus, account["id"], cut_on=CUT_ON, as_of=TODAY)
        assert not _rows(brazos, account_id=account["id"]).exists()
        assert disconnects.open_case_for(account["id"]).cut_on is None


def test_a_replayed_queue_writes_one_message_per_channel(brazos, marcus, monkeypatch):
    with tenant_ctx(brazos):
        account, _payload = _cut(marcus, brazos, monkeypatch)
        case = disconnects.DisconnectCase.objects.get(account_id=account["id"])
        again = notifications_seam.queue_service_disconnected(
            case_id=case.id, account_id=account["id"], cut_on=CUT_ON, actor=marcus
        )
        assert again["created"] is False
        assert _rows(brazos, account_id=account["id"], channel="email").count() == 1
        assert _rows(brazos, account_id=account["id"], channel="sms").count() == 1
        # And the cut itself is recorded once, so a second click queues nothing new.
        with pytest.raises(disconnects.DisconnectRuleError):
            disconnects.commit_cut(marcus, account["id"], cut_on=CUT_ON, as_of=TODAY)
        assert _rows(brazos, account_id=account["id"]).count() == 2


# ════════════════════════════════════════════════════════════════════════════
# 2 · THE RESTORATION TELLS THE CUSTOMER
# ════════════════════════════════════════════════════════════════════════════
def test_restoring_service_queues_the_restored_message(brazos, marcus, monkeypatch):
    with tenant_ctx(brazos):
        account, _payload = _cut(marcus, brazos, monkeypatch)
        _owes(monkeypatch, D("0.00"))
        disconnects.mark_reconnecting(marcus, account["id"], on_date=date(2026, 8, 28))
        restored = disconnects.restore_service(marcus, account["id"], on_date=date(2026, 8, 29))
        rows = _rows(
            brazos,
            account_id=account["id"],
            template_code__in=(
                customer_events.TEMPLATE_SERVICE_RESTORED,
                customer_events.TEMPLATE_SERVICE_RESTORED_SMS,
            ),
        )
        assert {row.channel for row in rows} == {"email", "sms"}
        body = rendering.render_for_dispatch(rows.get(channel="email")).body
        assert "slowly" in body  # ruling 4's safety text
        assert restored["notification_queued"]["event_key"] == "service_restored"


# ════════════════════════════════════════════════════════════════════════════
# 3 · THE CATALOGUE, THE TEMPLATES AND THE SHARED HELPER
# ════════════════════════════════════════════════════════════════════════════
def test_both_events_are_in_the_rules_catalogue_on_by_default_on_email_and_text():
    for key in ("service_disconnected", "service_restored"):
        event = rule_catalog.event(key)
        assert set(event.channels) == {"email", "sms"}
        assert event.trigger_blocked_by is None  # a live writer → seeded ON
        assert event.source_type == "service_state"
        assert event.category == rule_catalog.CATEGORY_COLLECTIONS
        for channel, code in event.template_classes.items():
            assert catalogs.catalog_for(code) is not None, code
            assert catalogs.catalog_for(code).channel == channel, code
            assert code in catalogs.LISTINGS, code
            assert any(seed.code == code for seed in seed_templates.SEEDABLE), code
    # None of the four is seeded wording with no rule to send it.
    unruled = set(rule_catalog.seeded_wording_without_rule())
    assert not unruled & {
        "service_disconnected_guide",
        "sms_service_disconnected",
        "service_restored",
        "sms_service_restored",
    }


def test_the_rules_screen_lists_both_events(brazos):
    with tenant_ctx(brazos):
        keys = {view.event.key for view in rule_service.rules()}
    assert {"service_disconnected", "service_restored"} <= keys


def test_the_shared_helper_honours_channels_and_still_defaults_to_email(brazos, marcus, monkeypatch):
    """Regression: the account-closed letter keeps going by email only."""
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch, owed=POSITION_AFTER_CUT)
        _reachable(account["id"])
        closed = customer_events.queue_account_closed(
            case_id="5b1e3f0c-1f5e-4c33-9d0e-6a8e0b8a7c11",
            account_id=account["id"],
            closed_on=date(2026, 9, 30),
        )
        # Email, and the `account` kind's print floor (BR-NOT-024) — never SMS.
        assert "email" in closed.channels and "sms" not in closed.channels
        both = customer_events._queue_account_message(
            event_key="service_disconnected",
            template_code=customer_events.TEMPLATE_SERVICE_DISCONNECTED,
            channel_templates={"sms": customer_events.TEMPLATE_SERVICE_DISCONNECTED_SMS},
            channels=("email", "sms"),
            source_type=customer_events.SOURCE_SERVICE_STATE,
            occasion_id="0c7f3a52-8a0b-4f63-9a54-3f2a1d7c9e10",
            account_id=account["id"],
            on_date=CUT_ON,
            context={},
        )
        assert sorted(both.channels) == ["email", "sms"]


def test_every_queue_kind_has_a_word_on_the_messages_screen():
    """DEF-NOT-10656 — Settings › Notifications › Messages needing attention
    names a row's TYPE through `notifications.queue.source.<kind>`. A kind
    added with no word renders its raw key; the walk of 2026-10-29 found
    `service_state` doing it and three older kinds already doing it."""
    import json
    import pathlib

    catalogue = json.loads(
        (
            pathlib.Path(__file__).resolve().parents[2] / "07-frontend/src/i18n/locales/en.json"
        ).read_text(encoding="utf-8")
    )
    missing = [
        kind
        for kind in notification_models.SOURCE_TYPES
        if f"notifications.queue.source.{kind}" not in catalogue
    ]
    assert missing == []
