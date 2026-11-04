"""`DEF-CUS-10042` — messages a clerk ADDS to a request's *What the customer is told*.

PO 2026-10-11, on New request step 4: *"use table array componnet and allow user
to add more communcation to user"*. The automatic rows are
`test_cr094_applicant_messages_block.py`'s; these cases cover the added list:
saved, replaced whole while unfired, queued at the moment chosen and once only,
a text row stored and recorded as not queued, and nothing ever claims *sent*.
"""
from __future__ import annotations

import pytest

from apps.customers import request_extra_messages as extra
from apps.customers import service_request_api as api
from apps.customers import service_request_service as sr
from apps.customers.applicant_message_models import ServiceRequestExtraMessage
from apps.notifications import models as notification_models
from apps.notifications import service_request_events
from core import errors
from tests.test_cr094_applicant_messages_block import CAPTURE, _ready_to_approve
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx  # noqa: F401
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

TO = "landlord@example.test"


def _a_template() -> str:
    """A code the picker offers; the approval class when nothing is published."""
    offered = extra.template_choices()["results"]
    return offered[0]["code"] if offered else service_request_events.TEMPLATE_APPROVED


def _queued_for(row_id) -> list:
    return list(
        notification_models.OutboundMessage.objects.filter(
            source_type=service_request_events.SOURCE_SERVICE_REQUEST, source_id=str(row_id)
        )
    )


def test_a_saved_row_comes_back_with_its_template_name_and_planned(brazos, dana):
    with tenant_ctx(brazos):
        request = sr.create_request(dana, CAPTURE)
        code = _a_template()
        rows = extra.save(
            dana,
            request.id,
            [{"template_code": code, "channel": "email", "to_address": TO, "send_when": "on_submit"}],
        )
    assert len(rows) == 1
    assert rows[0]["template_code"] == code
    assert rows[0]["template_name"]
    assert rows[0]["to_address"] == TO
    assert rows[0]["state"] == "planned"


def test_a_save_replaces_the_unfired_rows_whole(brazos, dana):
    with tenant_ctx(brazos):
        request = sr.create_request(dana, CAPTURE)
        code = _a_template()
        row = {"template_code": code, "channel": "email", "to_address": TO}
        extra.save(dana, request.id, [row, row])
        rows = extra.save(dana, request.id, [row])
    assert len(rows) == 1


@pytest.mark.parametrize(
    "bad, key",
    [
        ({"template_code": ""}, "customers.serviceRequest.extra.templateRequired"),
        ({"channel": "fax"}, "customers.serviceRequest.extra.channelUnknown"),
        ({"send_when": "next_tuesday"}, "customers.serviceRequest.extra.whenUnknown"),
        ({"to_address": ""}, "customers.serviceRequest.extra.addressRequired"),
    ],
)
def test_a_bad_row_is_refused_by_name(brazos, dana, bad, key):
    with tenant_ctx(brazos):
        request = sr.create_request(dana, CAPTURE)
        row = {"template_code": _a_template(), "channel": "email", "to_address": TO, **bad}
        with pytest.raises(errors.ValidationError) as refused:
            extra.save(dana, request.id, [row])
    assert refused.value.message_key == key


def test_an_on_submit_email_row_is_queued_at_submit_once_and_never_called_sent(brazos, dana):
    with tenant_ctx(brazos):
        request = sr.create_request(dana, CAPTURE)
        extra.save(
            dana,
            request.id,
            [{"template_code": _a_template(), "channel": "email", "to_address": TO, "send_when": "on_submit"}],
        )
        sr.submit(dana, request.id)
        sr.submit(dana, request.id)  # a replay fires nothing
        row = ServiceRequestExtraMessage.objects.get(request_id=request.id)
        queued = _queued_for(row.id)
        view = extra.rows_for(request.id)[0]
    assert row.fired_at is not None
    assert row.fired_state == "queued"
    assert len(queued) == 1
    assert queued[0].recipient_address == TO
    assert view["state"] == "queued"
    assert "sent" not in view["state"]


def test_a_text_row_is_recorded_as_not_queued_and_says_why(brazos, dana):
    with tenant_ctx(brazos):
        request = sr.create_request(dana, CAPTURE)
        extra.save(
            dana,
            request.id,
            [{"template_code": _a_template(), "channel": "text", "to_address": "555-0142"}],
        )
        sr.submit(dana, request.id)
        row = ServiceRequestExtraMessage.objects.get(request_id=request.id)
    assert row.fired_state == "not_sent"
    assert row.fired_reason == extra.REASON_TEXT_NOT_WRITTEN
    assert _queued_for(row.id) == []


def test_an_on_approve_row_waits_for_the_approval_and_a_fired_row_survives_a_later_save(brazos, dana):
    with tenant_ctx(brazos):
        request = sr.create_request(dana, CAPTURE)
        code = _a_template()
        extra.save(
            dana,
            request.id,
            [{"template_code": code, "channel": "email", "to_address": TO, "send_when": "on_approve"}],
        )
        ready = _ready_to_approve_from(dana, request)
        assert ServiceRequestExtraMessage.objects.get(request_id=ready.id).fired_at is None
        sr.approve_and_raise(dana, ready.id)
        row = ServiceRequestExtraMessage.objects.get(request_id=ready.id)
        assert row.fired_state == "queued"
        # A decided request takes no new rows, and an empty save keeps the fired one.
        with pytest.raises(errors.BizError):
            extra.save(dana, ready.id, [{"template_code": code, "to_address": TO}])
        extra.save(dana, ready.id, [])
        assert ServiceRequestExtraMessage.objects.filter(request_id=ready.id).count() == 1


def _ready_to_approve_from(actor, request):
    """`_ready_to_approve` builds its own request; this walks an existing one."""
    doc = sr.attach_document(
        actor, request.id, doc_type="proof_of_identity", name="id.pdf", storage_ref="s3://id"
    )
    sr.submit(actor, request.id)
    sr.resolve_address(actor, request.id)
    sr.link_customer(actor, request.id, customer_id=None)
    sr.decide_outcome(actor, request.id, outcome="new_connection")
    sr.verify_document(actor, doc.id)
    return sr.request_row(request.id)


def test_the_route_round_trips_with_the_body_the_screen_sends(brazos, dana):
    with tenant_ctx(brazos):
        request = sr.create_request(dana, CAPTURE)
        code = _a_template()
    put = api_call(
        api.service_request_extra_messages,
        "put",
        f"/api/brazos/service-requests/{request.id}/extra-messages",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        data={"rows": [{"template_code": code, "channel": "email", "to_address": TO, "send_when": "on_submit"}]},
        request_id=str(request.id),
    )
    assert put.status_code == 200
    assert len(put.data["rows"]) == 1
    got = api_call(
        api.service_request_extra_messages,
        "get",
        f"/api/brazos/service-requests/{request.id}/extra-messages",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        request_id=str(request.id),
    )
    assert got.status_code == 200
    assert got.data["rows"][0]["to_address"] == TO
    assert "results" in got.data["templates"]


# `_ready_to_approve` is imported so this file breaks loudly if the shared walk moves.
assert callable(_ready_to_approve)
