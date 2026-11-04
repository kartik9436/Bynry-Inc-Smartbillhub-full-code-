# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-013 (the delivery dashboard + re-queue, row AND bulk) —
#           DEF-NOT-10650 (PO 2026-10-29, ruled "1A 2A 3B 4B, start")
#           Screens: S8 (Settings → Notifications → Messages needing attention)
# Rules:    BR-NOT-005 (a re-queue never bypasses batching) · BR-PAY-018 (held
#           rows release by address verification only) · BR-TEN-017 (the
#           contact record is the customers module's; a delivery correction
#           does not write it) · BR-TEN-003 / HR-1 · CLAUDE.md rules 1, 6, 7
# ───────────────────────────────────────────────────────
"""DEF-NOT-10650 — the four PO rulings of 2026-10-29, at the API boundary.

1A  the list can be narrowed to the messages NEEDING ATTENTION, and the screen
    gets that count on every read;
2A  *"Select all N matching"* is resolved by the SERVER from the same filter
    the list used, capped at 500 and REFUSED above it — an empty selection
    never means all;
3B  *Fix address and retry* queues a NEW message to the corrected address and
    leaves the failed one — and the customer's contact — exactly as they were,
    with an audit row naming old → new;
4B  the last attempt's diagnostics are served on the row (no history store).
"""

from __future__ import annotations

import uuid

import pytest

from apps.notifications import api as notifications_api
from apps.notifications import models, rendering
from core import errors

from tests.test_def_128_notifications_api import a_row, an_account, call
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def a_failed_email(tenant, **overrides):
    values = dict(
        channel=models.CHANNEL_EMAIL,
        recipient_address="jo.prather@exmaple.com",
        status=models.STATUS_FAILED,
        attempts=3,
        last_error="550 5.1.1 mailbox does not exist",
        provider_reference="esp-7781-ab",
        provider_response={"code": 550, "reason": "mailbox does not exist"},
        template_code="email_bill_ready",
        render_context=rendering.encode_context({"amount_due": "612.75"}),
    )
    values.update(overrides)
    return a_row(tenant, **values)


# ══════════════════════════════════════════════════════════════════════════
# 1A — THE ATTENTION VIEW AND ITS COUNT
# ══════════════════════════════════════════════════════════════════════════
def test_1a_the_attention_filter_returns_only_rows_needing_attention(brazos, dana):
    with tenant_ctx(brazos):
        wanted = {
            str(a_row(brazos, status=status).pk)
            for status in (
                models.STATUS_FAILED,
                models.STATUS_BOUNCED,
                models.STATUS_BOUNCED_HARD,
                models.STATUS_BOUNCED_SOFT,
                models.STATUS_COMPLAINED,
            )
        }
        a_row(brazos)  # queued
        a_row(brazos, status=models.STATUS_SENT)
        a_row(brazos, status=models.STATUS_UNSUBSCRIBED)  # a choice, not a fault

    response = call(notifications_api.outbound, "get", brazos, dana, query={"f.attention": "true"})

    assert response.status_code == 200
    assert {row["id"] for row in response.data["results"]} == wanted
    assert response.data["count"] == 5


def test_1a_the_attention_count_is_served_whatever_view_is_open(brazos, dana):
    """The switch carries a count on *Needing attention* in BOTH views, so it is
    served on every list read rather than only when that view is open."""
    with tenant_ctx(brazos):
        for _ in range(3):
            a_row(brazos, status=models.STATUS_FAILED)
        for _ in range(4):
            a_row(brazos, status=models.STATUS_SENT)

    every = call(notifications_api.outbound, "get", brazos, dana)
    narrowed = call(notifications_api.outbound, "get", brazos, dana, query={"f.attention": "true"})

    assert every.data["count"] == 7
    assert every.data["attention_count"] == 3
    assert narrowed.data["attention_count"] == 3


def test_4b_the_row_carries_the_last_attempt_diagnostics(brazos, dana):
    """4B — the LAST attempt only: when, what the provider said, its reference,
    and when the next try is due. No per-attempt history is served."""
    with tenant_ctx(brazos):
        a_failed_email(brazos)

    row = call(notifications_api.outbound, "get", brazos, dana, query={"f.attention": "true"}).data[
        "results"
    ][0]

    assert row["provider_response"] == {"code": 550, "reason": "mailbox does not exist"}
    assert row["provider_reference"] == "esp-7781-ab"
    assert row["last_error"] == "550 5.1.1 mailbox does not exist"
    assert "next_attempt_at" in row and "last_attempt_at" in row and "queued_at" in row
    # The re-queueable set travels with the list so the screen draws a checkbox
    # exactly where the server would accept it.
    vocabulary = call(notifications_api.outbound, "get", brazos, dana).data["vocabulary"]
    assert set(vocabulary["requeueable_statuses"]) == {
        models.STATUS_FAILED,
        models.STATUS_BOUNCED,
        models.STATUS_BOUNCED_SOFT,
        models.STATUS_QUEUED,
    }
    assert set(vocabulary["retry_to_statuses"]) == {
        models.STATUS_FAILED,
        models.STATUS_BOUNCED,
        models.STATUS_BOUNCED_HARD,
        models.STATUS_BOUNCED_SOFT,
    }
    assert set(vocabulary["retry_to_channels"]) == {models.CHANNEL_EMAIL, models.CHANNEL_SMS}


# ══════════════════════════════════════════════════════════════════════════
# 2A — SELECT ALL N MATCHING, RESOLVED BY THE SERVER, CAPPED AT 500
# ══════════════════════════════════════════════════════════════════════════
def test_2a_select_all_matching_returns_every_id_in_the_filtered_view(brazos, dana):
    with tenant_ctx(brazos):
        failed = {str(a_row(brazos, status=models.STATUS_FAILED).pk) for _ in range(60)}
        a_row(brazos, status=models.STATUS_SENT)

    response = call(
        notifications_api.outbound_selection,
        "get",
        brazos,
        dana,
        query={"f.attention": "true", "per": "50"},
    )

    assert response.status_code == 200
    # Not the page of fifty: every row the FILTER matches.
    assert set(response.data["message_ids"]) == failed
    assert response.data["count"] == 60
    assert response.data["cap"] == 500


def test_2a_select_all_matching_above_500_is_refused_and_selects_nothing(brazos, dana):
    with tenant_ctx(brazos):
        models.OutboundMessage.objects.bulk_create(
            [
                models.OutboundMessage(
                    tenant_id=brazos.id,
                    source_type="invoice",
                    source_id=uuid.uuid4(),
                    channel=models.CHANNEL_PRINT,
                    template_code="bill_residential",
                    template_id=uuid.uuid4(),
                    template_version=2,
                    recipient_address="1901 Bluestem Ln",
                    status=models.STATUS_FAILED,
                )
                for _ in range(501)
            ]
        )

    response = call(
        notifications_api.outbound_selection, "get", brazos, dana, query={"f.attention": "true"}
    )

    assert response.status_code == 422
    assert response.data["message_key"] == notifications_api.KEY_SELECTION_TOO_MANY
    assert response.data["params"]["count"] == 501
    assert response.data["params"]["cap"] == 500
    assert "message_ids" not in response.data


def test_2a_a_view_matching_nothing_selects_nothing_never_everything(brazos, dana):
    with tenant_ctx(brazos):
        a_row(brazos, status=models.STATUS_SENT)

    response = call(
        notifications_api.outbound_selection, "get", brazos, dana, query={"f.attention": "true"}
    )

    assert response.status_code == 200
    assert response.data["message_ids"] == []
    assert response.data["count"] == 0


def test_2a_the_bulk_requeue_tallies_each_row_with_its_reason(brazos, dana):
    """*"48 re-queued. 2 could not be: already sent."* — the screen composes
    that sentence from these codes, so every refused row carries one."""
    with tenant_ctx(brazos):
        moved = [a_row(brazos, status=models.STATUS_FAILED) for _ in range(3)]
        sent = a_row(brazos, status=models.STATUS_SENT)
        hard = a_row(brazos, status=models.STATUS_BOUNCED_HARD)

    response = call(
        notifications_api.outbound_requeue_bulk,
        "post",
        brazos,
        dana,
        data={"message_ids": [str(row.pk) for row in [*moved, sent, hard]]},
    )

    assert response.status_code == 200
    assert sorted(response.data["requeued"]) == sorted(str(row.pk) for row in moved)
    assert sorted(entry["code"] for entry in response.data["refused"]) == [
        "already_sent_not_requeueable",
        "status_not_requeueable",
    ]


def test_2a_an_empty_selection_is_refused_rather_than_read_as_all(brazos, dana):
    with tenant_ctx(brazos):
        row = a_row(brazos, status=models.STATUS_FAILED)

    response = call(
        notifications_api.outbound_requeue_bulk, "post", brazos, dana, data={"message_ids": []}
    )

    assert response.status_code == 422
    assert response.data["code"] == errors.VAL_REQUIRED
    with tenant_ctx(brazos):
        row.refresh_from_db()
    assert row.status == models.STATUS_FAILED


@pytest.mark.isolation
def test_2a_select_all_matching_never_reaches_another_tenant(brazos, lonestar, dana):
    with tenant_ctx(lonestar):
        a_row(lonestar, status=models.STATUS_FAILED)
    with tenant_ctx(brazos):
        mine = a_row(brazos, status=models.STATUS_FAILED)

    response = call(
        notifications_api.outbound_selection, "get", brazos, dana, query={"f.attention": "true"}
    )

    assert response.data["message_ids"] == [str(mine.pk)]


# ══════════════════════════════════════════════════════════════════════════
# 3B — FIX ADDRESS AND RETRY: THIS MESSAGE ONLY
# ══════════════════════════════════════════════════════════════════════════
def retry_to(tenant, actor, row, address, *, role="billing_clerk"):
    return call(
        notifications_api.outbound_retry_to,
        "post",
        tenant,
        actor,
        role=role,
        data={"address": address},
        message_id=str(row.pk),
    )


def test_3b_retry_to_queues_a_new_message_to_the_corrected_address(brazos, marcus, audit_rows):
    with tenant_ctx(brazos):
        original = a_failed_email(brazos)
        before = models.OutboundMessage.objects.values().get(pk=original.pk)

    response = retry_to(brazos, marcus, original, "  jo.prather@example.com ")

    assert response.status_code == 201, response.data
    assert response.data["created"] is True
    assert response.data["dispatched"] is False
    with tenant_ctx(brazos):
        new = models.OutboundMessage.objects.get(pk=response.data["message"]["id"])
        # The failed message stays EXACTLY as it was — it is the record.
        assert models.OutboundMessage.objects.values().get(pk=original.pk) == before
        # ONE new row and no second paper copy: the print floor went out at copy 0.
        siblings = models.OutboundMessage.objects.filter(
            tenant_id=brazos.id, source_id=original.source_id
        )
        assert siblings.count() == 2
    assert new.pk != original.pk
    assert new.recipient_address == "jo.prather@example.com"
    assert new.channel == models.CHANNEL_EMAIL
    assert new.status == models.STATUS_QUEUED
    assert new.copy_no == original.copy_no + 1
    assert (new.template_id, new.template_version) == (
        original.template_id,
        original.template_version,
    )
    assert rendering.decode_context(new.render_context) == {"amount_due": "612.75"}
    assert new.attempts == 0 and new.last_error is None

    trail = [row for row in audit_rows if row.get("action") == "delivery.retried_to_new_address"]
    assert len(trail) == 1
    assert trail[0]["entity_id"] == str(original.pk)
    assert trail[0]["before"]["recipient_address"] == "jo.prather@exmaple.com"
    assert trail[0]["after"]["recipient_address"] == "jo.prather@example.com"
    assert trail[0]["after"]["message_id"] == str(new.pk)
    assert trail[0]["after"]["contact_record_changed"] is False


def test_3b_retry_to_never_touches_the_customers_contact(brazos, marcus, dana):
    from apps.customers import models as customer_models

    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        contact = customer_models.Contact.objects.create(
            tenant=brazos, account=account, full_name="Jo Prather", email="jo.prather@exmaple.com"
        )
        original = a_failed_email(brazos, account_id=account.id)

    response = retry_to(brazos, marcus, original, "jo.prather@example.com")

    assert response.status_code == 201
    with tenant_ctx(brazos):
        contact.refresh_from_db()
    assert contact.email == "jo.prather@exmaple.com", "3B: the contact record is unchanged"


def test_3b_a_double_click_queues_one_message_not_two(brazos, marcus):
    with tenant_ctx(brazos):
        original = a_failed_email(brazos)

    first = retry_to(brazos, marcus, original, "jo.prather@example.com")
    second = retry_to(brazos, marcus, original, "jo.prather@example.com")

    assert first.status_code == 201 and second.status_code == 200
    assert second.data["created"] is False
    assert first.data["message"]["id"] == second.data["message"]["id"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"status": models.STATUS_SENT},
        {"status": models.STATUS_DELIVERED},
        {"status": models.STATUS_QUEUED},
        {"status": models.STATUS_COMPLAINED},
        {"held": True, "held_reason": "bad_address"},
    ],
    ids=["sent", "delivered", "queued", "complained", "held"],
)
def test_3b_retry_to_is_refused_where_it_would_be_wrong(brazos, marcus, overrides):
    with tenant_ctx(brazos):
        original = a_failed_email(brazos, **overrides)

    response = retry_to(brazos, marcus, original, "jo.prather@example.com")

    assert response.status_code == 409  # BIZ-STATE: the message's state forbids it
    assert response.data["code"] == errors.BIZ_STATE
    assert response.data["message_key"] == notifications_api.KEY_RETRY_TO_REFUSED
    with tenant_ctx(brazos):
        assert models.OutboundMessage.objects.filter(source_id=original.source_id).count() == 1


def test_3b_retry_to_is_refused_on_a_channel_with_no_typed_address(brazos, marcus):
    with tenant_ctx(brazos):
        letter = a_row(brazos, status=models.STATUS_FAILED)  # print

    response = retry_to(brazos, marcus, letter, "jo.prather@example.com")

    assert response.status_code == 409  # BIZ-STATE: the message's state forbids it
    assert response.data["code"] == errors.BIZ_STATE
    assert response.data["message_key"] == notifications_api.KEY_RETRY_TO_REFUSED


@pytest.mark.parametrize(
    ("channel", "address", "stored"),
    [
        (models.CHANNEL_EMAIL, "not-an-email", None),
        (models.CHANNEL_SMS, "555-01", None),
        (models.CHANNEL_SMS, "(512) 555-0104", "+15125550104"),
    ],
)
def test_3b_the_address_is_validated_for_its_channel(brazos, marcus, channel, address, stored):
    with tenant_ctx(brazos):
        original = a_failed_email(
            brazos,
            channel=channel,
            recipient_address="+15125550000" if channel == models.CHANNEL_SMS else "a@b.com",
        )

    response = retry_to(brazos, marcus, original, address)

    if stored is None:
        assert response.status_code == 422
        assert response.data["code"] == errors.VAL_FORMAT
        assert response.data["field_errors"][0]["field"] == "address"
    else:
        assert response.status_code == 201
        with tenant_ctx(brazos):
            new = models.OutboundMessage.objects.get(pk=response.data["message"]["id"])
        assert new.recipient_address == stored


def test_3b_an_executive_cannot_retry(brazos, dana):
    with tenant_ctx(brazos):
        original = a_failed_email(brazos)

    response = retry_to(brazos, dana, original, "jo.prather@example.com", role="executive")

    assert response.status_code == 403


def test_3b_another_tenants_message_reads_as_absent(brazos, lonestar, marcus):
    with tenant_ctx(lonestar):
        theirs = a_failed_email(lonestar)

    response = retry_to(brazos, marcus, theirs, "jo.prather@example.com")

    assert response.status_code == 404



# ══════════════════════════════════════════════════════════════════════════
# DEF-NOT-10665 — PO 2026-10-29 D1 A: a failed message already retried to a
# corrected address shows "Retried to a new address" and LEAVES Needing
# attention (filter AND count); it stays under All messages.
# ══════════════════════════════════════════════════════════════════════════
def test_def_not_10665_a_retried_failure_leaves_needing_attention(brazos, marcus, dana):
    """RED on the tip: the retried row was still in ``f.attention`` and in
    ``attention_count`` (``assert 2 == 1``), with no field saying it had gone."""
    with tenant_ctx(brazos):
        original = a_failed_email(brazos)
        untouched = a_failed_email(brazos)
    assert retry_to(brazos, marcus, original, "jo.prather@example.com").status_code == 201

    narrowed = call(notifications_api.outbound, "get", brazos, dana, query={"f.attention": "true"})
    every = call(notifications_api.outbound, "get", brazos, dana)

    assert [row["id"] for row in narrowed.data["results"]] == [str(untouched.pk)]
    assert narrowed.data["count"] == 1
    assert narrowed.data["attention_count"] == 1
    assert every.data["attention_count"] == 1
    by_id = {row["id"]: row for row in every.data["results"]}
    # Still listed under All messages — the failed row is the record (3B).
    assert by_id[str(original.pk)]["status"] == models.STATUS_FAILED
    assert by_id[str(original.pk)]["retried_to_new_address"] is True
    assert by_id[str(untouched.pk)]["retried_to_new_address"] is False
    # The new copy is not itself "retried".
    new = [row for row in every.data["results"] if row["copy_no"] == original.copy_no + 1]
    assert [row["retried_to_new_address"] for row in new] == [False]


def test_def_not_10665_a_later_copy_to_the_same_address_is_not_a_retry_to_a_new_one(brazos, dana):
    """Only a copy to a DIFFERENT address counts: a resend to the same mailbox
    fixed nothing, so the failure still needs attention."""
    with tenant_ctx(brazos):
        original = a_failed_email(brazos)
        a_row(
            brazos,
            channel=models.CHANNEL_EMAIL,
            source_type=original.source_type,
            source_id=original.source_id,
            copy_no=original.copy_no + 1,
            recipient_address=original.recipient_address,
        )

    narrowed = call(notifications_api.outbound, "get", brazos, dana, query={"f.attention": "true"})
    assert [row["id"] for row in narrowed.data["results"]] == [str(original.pk)]
    assert narrowed.data["attention_count"] == 1
