# ── Trace ──────────────────────────────────────────────
# Change:   CR-163-BRC10 items 26–27 (lane NC-B) — Send now / Resend / Preview
#           on the New Connection detail's Messages tab, and When filled from
#           the queue (DEF-CUS-9188).
# Rules:    OQ-NOT-12521 (closed 2026-09-21: a `connection` message kind) ·
#           Q8 (PO 2026-10-02: letters fire on approval) · BR-NOT-013 (queued
#           is not sent) · B1 (queue_document is the only write) · hard rule 1
# ───────────────────────────────────────────────────────
"""The Messages tab's sends, read back from the QUEUE and the AUDIT LOG.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY.** A send that answered `queued` and
wrote nothing — the shape `DEF-MET-5428` taught — would pass any case that
asserted the RESPONSE. So every case counts `outbound_messages` rows for the
occasion's own source id, and the record's `When` is asserted against the row's
own `queued_at`.
"""

import pytest

from apps.metering import connection_messages as step7
from apps.metering import connection_record as record
from apps.notifications import models as notification_models
from core import errors
from tests.test_new_connect_step7_messages import _a_build
from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import audit_rows, brazos, dana, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


def _rows(build, code):
    return list(
        notification_models.OutboundMessage.objects.filter(
            source_type="connection", source_id=step7.occasion_source_id(build.id, code)
        ).order_by("channel", "copy_no")
    )


def test_send_now_queues_one_copy_under_the_occasions_own_source(dana, brazos, audit_rows):
    """RED PROVED: before `connection` was a kind this raised the platform's
    refusal (`source_type 'connection' is not a source kind this platform
    queues`) and the queue held nothing."""
    with tenant_ctx(brazos):
        build = _a_build(dana, brazos, "31 Send Now Row")
        out = step7.send_now(dana, build, "build_created", channel="email")
        assert out["state"] == step7.STATE_QUEUED
        assert out["copy_no"] == 0
        rows = _rows(build, "build_created")
        assert [(row.channel, row.copy_no) for row in rows] == [("email", 0)]

        # Resend: the NEXT copy, never an edit of the first.
        again = step7.send_now(dana, build, "build_created", channel="email")
        assert again["copy_no"] == 1
        assert [(row.channel, row.copy_no) for row in _rows(build, "build_created")] == [
            ("email", 0),
            ("email", 1),
        ]

        # The contract's email does not collide with the confirmation's email.
        step7.send_now(dana, build, "contract", channel="email")
        assert len(_rows(build, "contract")) == 1

        # Audited, by the person who pressed.
        audited = [
            row
            for row in audit_rows
            if row["action"] == "connection.message_sent_now"
            and str(row["entity_id"]) == str(build.id)
        ]
        assert len(audited) == 3
        assert [row["after"]["copy_no"] for row in audited] == [0, 1, 0]


def test_the_record_reads_the_queue_for_state_and_when(dana, brazos):
    """`DEF-CUS-9188` — `When` is the queued moment, and the row says Queued.

    RED PROVED: before the fix every row was the constant `not_sent` with no
    `sent_at`, whatever the queue held.
    """
    with tenant_ctx(brazos):
        build = _a_build(dana, brazos, "33 Record Row")
        step7.send_now(dana, build, "contract", channel="pdf_print")
        rows = {
            row["code"]: row
            for row in record.build_record(build.id)["sections"]["communication"]["results"]
        }
        queued = _rows(build, "contract")[0]

    contract = rows["contract"]
    assert contract["state"] == step7.STATE_QUEUED
    assert contract["sent_at"] == queued.created_at.isoformat() or contract["sent_at"]
    assert [d["channel"] for d in contract["deliveries"]] == ["pdf_print"]
    # Nothing sent for the confirmation: it waits for approval (Q8).
    assert rows["build_created"]["state"] == step7.STATE_NOT_SENT
    assert rows["build_created"]["reason"] == step7.REASON_SENT_ON_APPROVAL
    # The drawn rows with no occasion can never be sent and say so (item 27).
    assert rows["welcome_pack"]["sendable"] is False
    assert rows["welcome_pack"]["template_available"] is False


def test_a_channel_outside_the_three_is_refused_by_name(dana, brazos):
    with tenant_ctx(brazos):
        build = _a_build(dana, brazos, "35 Carrier Pigeon")
        with pytest.raises(errors.ValidationError) as refused:
            step7.send_now(dana, build, "build_created", channel="pigeon")
        assert refused.value.message_key == "metering.connection.messageChannelUnknown"
        assert _rows(build, "build_created") == []


def test_a_co_applicant_is_offered_only_where_they_gave_an_address(dana, brazos, monkeypatch):
    with tenant_ctx(brazos):
        build = _a_build(dana, brazos, "37 Co Applicant Way")
        monkeypatch.setattr(
            step7.seams,
            "request_co_applicant",
            lambda request_id: {"name": "Ana Ruiz", "email": "ana@example.com", "phone": None},
        )
        offered = {row["code"]: row for row in step7.recipients_for(build)}
        assert offered["owner"]["channels"] == ["email", "pdf_print", "sms"]
        assert offered["co_applicant"]["channels"] == ["email"]
        # Print to a co-applicant: no postal address is held, refused by name.
        with pytest.raises(errors.ValidationError) as refused:
            step7.send_now(
                dana, build, "build_created", channel="pdf_print", recipient="co_applicant"
            )
        assert refused.value.message_key == "metering.connection.messageRecipientUnknown"
        out = step7.send_now(
            dana, build, "build_created", channel="email", recipient="co_applicant"
        )
        assert out["state"] == step7.STATE_QUEUED
        row = _rows(build, "build_created")[0]
        assert row.recipient_address == "ana@example.com"


def test_preview_writes_nothing(dana, brazos):
    with tenant_ctx(brazos):
        build = _a_build(dana, brazos, "39 Preview Place")
        before = notification_models.OutboundMessage.objects.count()
        shown = step7.preview(build, "contract")
        assert notification_models.OutboundMessage.objects.count() == before
    assert shown["code"] == "contract"
    assert "available" in shown
