# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-PAY-6342 (parts 2–4) — marking post returned wrote an event and
#           reached nobody: the account page read a column nothing wrote, there
#           was no needs-attention list, and nothing could clear the flag.
# Rules:    BR-PAY-018 (VERBATIM: "Returned mail: delivery record marked
#           returned (single/bulk) → account bad-address flag → needs-attention
#           queue + banner → paper suppressed until address verified (config);
#           balances unaffected; audited.") · BR-CWP-086 (the customer's own
#           correction clears it) · CLAUDE.md rule 7 (audit) · B1 (customers
#           writes `accounts`; payments asks)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""ONE bad-address fact, reached through the routes a clerk uses.

Every effect BR-PAY-018 names is asserted through a ROUTE — `POST
/deliveries/returned`, `GET /accounts/{id}`, `GET /returned-mail`, `POST
/returned-mail/clear`, `GET /outstandings` — never by calling the function
that implements it. The defect's own escape reason is that every function was
unit-tested in isolation and nothing asked whether any was reachable.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from apps.customers import api as customers_api
from apps.customers import models as customer_models
from apps.notifications import api as notifications_api
from apps.notifications import models as outbound
from apps.notifications import services as notification_services
from apps.payments import api as payments_api
from apps.payments import returned_mail, returned_mail_api
from apps.payments.collections_models import DeliveryReturnEvent
from tests.test_def_pay_6342_service_address import _account
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401 — fixtures by name
    api_call,
    audit_actions,
    brazos,
    dana,
    marcus,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

PIN = notification_services.TemplatePin(
    code="bill_residential", template_id=uuid4(), version=3, language="en-US"
)
MAILING = {"line1": "PO Box 77", "city": "Sugar Land", "state": "TX", "postal_code": "77478"}


def _letter(account_id) -> str:
    """One paper letter queued the way a bill release queues it — so its
    envelope snapshot is the real recipient read's, `source` included."""
    source_id = uuid4()
    notification_services.queue_document(
        source_type="invoice", source_id=source_id, channels=(), template=PIN, account_id=account_id
    )
    row = outbound.OutboundMessage.objects.get(source_id=source_id, channel=outbound.CHANNEL_PRINT)
    return str(row.pk)


def _mark(tenant, clerk, message_ids, *, on="2026-09-08"):
    response = api_call(
        notifications_api.deliveries_returned,
        "post",
        user=clerk.user,
        role="billing_clerk",
        tenant=tenant,
        data={"message_ids": list(message_ids), "returned_on": on},
    )
    assert response.status_code == 200, response.data
    return response.data


def _page(tenant, clerk, account_id):
    response = api_call(
        customers_api.account_item,
        "get",
        user=clerk.user,
        role="billing_clerk",
        tenant=tenant,
        account_id=str(account_id),
    )
    assert response.status_code == 200, response.data
    return response.data


def _list(tenant, clerk, **query):
    response = api_call(
        returned_mail_api.returned_mail_list,
        "get",
        user=clerk.user,
        role="billing_clerk",
        tenant=tenant,
        query=query,
    )
    assert response.status_code == 200, response.data
    return response.data


def _clear(tenant, clerk, account_id, *, resolution="verified_current", on="2026-09-09"):
    return api_call(
        returned_mail_api.returned_mail_clear,
        "post",
        user=clerk.user,
        role="billing_clerk",
        tenant=tenant,
        data={"account_id": str(account_id), "resolution": resolution, "resolved_on": on},
    )


def test_marking_a_return_makes_the_account_page_read_bad_address_yes(brazos, marcus, audit_rows):
    """THE DEFECT. Before: the event was written and the page read `False`."""
    with tenant_ctx(brazos):
        account_id, _p, _u = _account(marcus)
        letter = _letter(account_id)
    assert _page(brazos, marcus, account_id)["bad_address"] is False

    marked = _mark(brazos, marcus, [letter])

    assert marked["balances_affected"] is False
    assert _page(brazos, marcus, account_id)["bad_address"] is True
    actions = audit_actions(audit_rows)
    assert "delivery.returned" in actions
    assert "account.bad_address.flagged" in actions


def test_the_needs_attention_list_is_oldest_first_and_says_where_each_letter_went(brazos, marcus):
    """J18 step 5 — it AGES visibly — and the PO's *"mailing or service"*."""
    with tenant_ctx(brazos):
        service_id, _p, _u = _account(marcus, street="412 Cypress Row", label="Unit 2")
        mailing_id, _p2, _u2 = _account(marcus, mailing=MAILING)
        service_letter = _letter(service_id)
        mailing_letter = _letter(mailing_id)
    _mark(brazos, marcus, [mailing_letter], on="2026-09-10")
    _mark(brazos, marcus, [service_letter], on="2026-09-08")

    body = _list(brazos, marcus)

    assert body["count"] == 2
    first, second = body["results"]
    assert (first["returned_on"], first["went_to"], first["address"]) == (
        "2026-09-08",
        "service_address",
        "412 Cypress Row · Unit 2",
    )
    assert (second["returned_on"], second["went_to"], second["address"]) == (
        "2026-09-10",
        "mailing_address",
        "PO Box 77",
    )
    assert first["account_no"] and second["account_no"]
    narrowed = _list(brazos, marcus, **{"f.account_id": str(mailing_id)})
    assert [row["went_to"] for row in narrowed["results"]] == ["mailing_address"]


def test_clearing_lowers_the_flag_empties_the_list_and_audits_both(brazos, marcus, audit_rows):
    with tenant_ctx(brazos):
        account_id, _p, _u = _account(marcus)
        letter = _letter(account_id)
    _mark(brazos, marcus, [letter])

    cleared = _clear(brazos, marcus, account_id)

    assert cleared.status_code == 200, cleared.data
    assert cleared.data["returns_resolved"] == 1
    assert cleared.data["flag_cleared"] is True
    assert cleared.data["balances_affected"] is False
    assert _page(brazos, marcus, account_id)["bad_address"] is False
    assert _list(brazos, marcus)["count"] == 0
    actions = audit_actions(audit_rows)
    assert "bad_address.cleared" in actions  # the return event, payments' row
    assert "account.bad_address.cleared" in actions  # the flag, customers' row
    with tenant_ctx(brazos):
        event = DeliveryReturnEvent.objects.get(account_id=account_id)
    assert (event.resolution, event.resolved_on) == ("verified_current", date(2026, 9, 9))


def test_a_flag_with_no_return_behind_it_can_still_be_cleared(brazos, marcus):
    """A migration brings the flag across with no event (`IMPORT_ACCOUNT_FIELDS`).
    A clear step keyed on events alone could never lower it."""
    with tenant_ctx(brazos):
        account_id, _p, _u = _account(marcus)
        customer_models.Account.objects.filter(pk=account_id).update(bad_address=True)

    cleared = _clear(brazos, marcus, account_id, resolution="address_corrected")

    assert cleared.status_code == 200, cleared.data
    assert (cleared.data["returns_resolved"], cleared.data["flag_cleared"]) == (0, True)
    assert _page(brazos, marcus, account_id)["bad_address"] is False


def test_clearing_nothing_is_refused_by_name(brazos, marcus):
    with tenant_ctx(brazos):
        account_id, _p, _u = _account(marcus)
    refused = _clear(brazos, marcus, account_id)
    assert refused.status_code == 409, refused.data
    assert refused.data["message_key"] == "payments.returnedMail.clear.refused"


def test_the_account_serves_where_its_service_address_lives(brazos, marcus):
    """The clear step's premises LINK needs the premises, never an edit of it."""
    with tenant_ctx(brazos):
        account_id, premises_id, _u = _account(marcus)
    assert _page(brazos, marcus, account_id)["service_premises_id"] == str(premises_id)


def test_the_debtors_list_reads_the_same_stored_flag(brazos, dana, marcus):
    """The Debtors filter and cell derived their own flag from return events,
    so an account flagged by a migration read `No` there and `Yes` on its own
    page. Both now read `accounts.bad_address`."""
    from tests.test_us_bil_023_delivery_queue import issue_one

    with tenant_ctx(brazos):
        billed, account, _run = issue_one(brazos, dana)
        customer_models.Account.objects.filter(pk=account.pk).update(bad_address=True)

    response = api_call(
        payments_api.outstandings,
        "get",
        user=marcus.user,
        role="billing_clerk",
        tenant=brazos,
        query={"as_of": "2026-12-31", "f.bad_address": "true"},
    )

    assert response.status_code == 200, response.data
    rows = response.data["rows"]
    assert [row["account_id"] for row in rows] == [str(account.pk)]
    assert rows[0]["bad_address"] is True


def test_a_second_envelope_flags_once_and_one_clear_resolves_both(brazos, marcus, audit_rows):
    with tenant_ctx(brazos):
        account_id, _p, _u = _account(marcus)
        letters = [_letter(account_id), _letter(account_id)]
    _mark(brazos, marcus, letters)

    assert audit_actions(audit_rows).count("account.bad_address.flagged") == 1
    cleared = _clear(brazos, marcus, account_id)
    assert cleared.data["returns_resolved"] == 2


def test_resolving_the_last_open_return_one_at_a_time_lowers_the_flag(brazos, marcus):
    with tenant_ctx(brazos):
        account_id, _p, _u = _account(marcus)
        first = returned_mail.mark_returned(
            account_id=account_id, returned_on=date(2026, 9, 8), outbound_message_id=uuid4()
        )
        second = returned_mail.mark_returned(
            account_id=account_id, returned_on=date(2026, 9, 8), outbound_message_id=uuid4()
        )
        returned_mail.resolve_return(
            event_id=first.event_id, resolution="verified_current", resolved_on=date(2026, 9, 9)
        )
        assert returned_mail.bad_address_for(account_id) is True
        returned_mail.resolve_return(
            event_id=second.event_id, resolution="verified_current", resolved_on=date(2026, 9, 9)
        )
        assert returned_mail.bad_address_for(account_id) is False
