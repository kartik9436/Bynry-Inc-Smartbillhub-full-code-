# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-013 (the platform delivery dashboard + re-queue, over HTTP) ·
#           US-NOT-014 (returned mail — AND the payments hand-off that turns a
#           returned letter into the account's bad-address flag) ·
#           US-NOT-001 (the queue table's idempotency key, exercised by a
#           resend) · US-NOT-009 (the notice record and the certified-mail
#           register)   Screens: S8 · S30 · S34 · S35
# Rules:    BR-NOT-005 (the queue; no synchronous send endpoint may exist) ·
#           BR-TEN-041 #8 · BR-PAY-018 (returned → bad-address → suppression;
#           BALANCES UNAFFECTED) · BR-CUS-039 (certified mail on the final
#           tier) · BR-BIL-016 (one delivery record per document per channel) ·
#           BR-TEN-003 / HR-1 · BR-TEN-043 (a business date is an input) ·
#           CLAUDE.md rule 1 · rule 2 · rule 6 · rule 7
# ───────────────────────────────────────────────────────
"""DEF-128 — the seven routes 7,084 lines of engine had never had.

THE FIRST TWO CASES ARE THE ONES THAT MATTER MOST and they are deliberately
about plumbing rather than about messages. An `api.py` that exports
`urlpatterns` is not an endpoint until `config/urls.py` includes it, and a route
the URLconf knows is not reachable until a real request survives the middleware,
the authentication and the permission class. So every path is resolved through
the REAL root URLconf and then called over real HTTP with no session: **401
means the route exists and asked for a sign-in; 404 means there is no route at
all**, which is what all seven answered before this lane.

THE THREE CASES THAT COST REAL MONEY IF THEY REGRESS:

  `test_us_not_001_tc5__a_resend_replay_writes_no_second_letter` — the resend's `copy_no` IS the
  idempotency key (CLAUDE.md rule 6). A repeated submit must find its own row
  and post nothing. A duplicated 48-hour final notice costs certified postage
  AND misstates the legal record.

  `test_returned_mail_flags_the_account_through_payments` — `delivery_ops` emits
  the event and `apps/payments/returned_mail` consumes it, and until this lane
  NOTHING CALLED THE SECOND. Both modules reported the gap in their own
  trailers. This asserts a `delivery_return_events` ROW, not a docstring.

  `test_notices_report_when_the_record_cannot_be_opened` — an unreadable record
  and a customer who was never contacted must never render the same (DEF-075).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

import pytest

from apps.notifications import api as notifications_api
from apps.notifications import delivery_ops, models, payments_seam
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

RETURNED_ON = "2026-08-16"
#: US-NOT-009 §4's own figure — the RECON charge code a disconnect notice
#: prints. Money, so it travels as a STRING with its currency, never as a float.
RECONNECT_FEE = Decimal("45.00")


# ── fixtures ────────────────────────────────────────────────────────────────
def an_account(actor, tenant, *, account_no="A-11455"):
    from apps.customers import models as customer_models

    premises = make_premises(actor, address_line=f"{account_no} Route 4")
    unit = make_unit(actor, premises["id"], label=account_no, services=["electric"])
    return customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        status=customer_models.AccountStatus.objects.filter(tenant=tenant).first(),
        account_type=customer_models.AccountType.objects.first(),
        account_no=account_no,
    )


def a_row(tenant, **overrides):
    """One queue row, written directly — the dispatcher's own test fixtures do
    the same, because this file is about the SURFACE over the table."""
    values = dict(
        tenant_id=tenant.id,
        source_type="invoice",
        source_id=uuid.uuid4(),
        channel=models.CHANNEL_PRINT,
        template_code="bill_residential",
        template_id=uuid.uuid4(),
        template_version=2,
        recipient_address="1901 Bluestem Ln",
        status=models.STATUS_QUEUED,
    )
    values.update(overrides)
    return models.OutboundMessage.objects.create(**values)


def call(view, method, tenant, actor, *, role="system_admin", **kwargs):
    return api_call(view, method, user=actor.user, role=role, tenant=tenant, **kwargs)


# ══════════════════════════════════════════════════════════════════════════
# THE TWO CASES THIS LANE EXISTS FOR — is the module REACHABLE at all?
# ══════════════════════════════════════════════════════════════════════════
def test_def_128_every_notification_route_is_actually_mounted(brazos):
    """HARD-WON LAW 2 at the routing layer — the defect that opened this lane.

    `apps/notifications/api.py` exporting `urlpatterns` is not an endpoint until
    `config/urls.py` includes it. This resolves the REAL paths through the REAL
    root URLconf, so a forgotten one-line include goes red here rather than in a
    support ticket six weeks later.
    """
    from django.urls import resolve

    message_id = uuid.uuid4()
    expected = {
        "/api/brazosbend/outbound": notifications_api.outbound,
        "/api/brazosbend/outbound/summary": notifications_api.outbound_summary,
        "/api/brazosbend/outbound/requeue": notifications_api.outbound_requeue_bulk,
        f"/api/brazosbend/outbound/{message_id}/requeue": notifications_api.outbound_requeue,
        f"/api/brazosbend/outbound/{message_id}/resend": notifications_api.outbound_resend,
        "/api/brazosbend/deliveries/returned": notifications_api.deliveries_returned,
        "/api/brazosbend/notices": notifications_api.notices,
    }
    for path, view in expected.items():
        assert resolve(path).func is view, f"{path} does not resolve to its view"


def test_def_128_the_routes_are_reachable_through_the_whole_stack(brazos):
    """The other half of "mounted": a real HTTP request ARRIVES at these views.

    `resolve()` proves the URLconf knows the path. It does not prove a request
    can get there — the tenant middleware, the session authentication and the
    permission class all sit in front, and any one of them answering 404 leaves
    the module exactly as unreachable as it was. So an UNAUTHENTICATED call is
    made and its refusal is read: **401 AUTH-001 = the route exists and asked
    for a session; 404 = there is no route**, which is what all seven answered
    before this lane.
    """
    from django.test import Client

    message_id = uuid.uuid4()
    probes = (
        ("get", f"/api/{brazos.subdomain}/outbound"),
        ("get", f"/api/{brazos.subdomain}/outbound/summary"),
        ("post", f"/api/{brazos.subdomain}/outbound/requeue"),
        ("post", f"/api/{brazos.subdomain}/outbound/{message_id}/requeue"),
        ("post", f"/api/{brazos.subdomain}/outbound/{message_id}/resend"),
        ("post", f"/api/{brazos.subdomain}/deliveries/returned"),
        ("get", f"/api/{brazos.subdomain}/notices"),
    )
    for method, path in probes:
        response = getattr(Client(), method)(path)
        assert response.status_code == 401, (
            f"{method.upper()} {path} answered {response.status_code}: a 404 here means the "
            "route is still not reachable, whatever the URLconf says"
        )
        assert response.json()["code"] == errors.AUTH_UNAUTHENTICATED


def test_def_128_no_send_endpoint_exists_on_this_module(brazos):
    """A11 Addendum r2 §4, verbatim: *"no synchronous send endpoint anywhere
    (queue only, BR-NOT-005)"* — and minting one is a gate failure.

    Asserted as a PROPERTY of the exported routes rather than left to review: a
    lane under pressure to make a screen "work" adds `POST /outbound/{id}/send`,
    every test passes, and the dispatcher stops being the only sender.
    """
    routes = [str(entry.pattern) for entry in notifications_api.urlpatterns]
    assert not [r for r in routes if r.endswith("/send") or r.endswith("/dispatch")], routes


# ══════════════════════════════════════════════════════════════════════════
# US-NOT-013 — the dispatch home
# ══════════════════════════════════════════════════════════════════════════
def test_us_not_013_tc1__the_summary_counts_tie_to_the_rows(brazos, dana):
    """US-NOT-013 TC-1 over HTTP: *"Counts tie to rows exactly."*"""
    with tenant_ctx(brazos):
        for _ in range(6):
            a_row(brazos, status=models.STATUS_FAILED, attempts=3, last_error="provider timeout")
        for _ in range(4):
            a_row(brazos)

    response = call(notifications_api.outbound_summary, "get", brazos, dana)

    assert response.status_code == 200
    assert response.data["totals"][models.STATUS_FAILED] == 6
    assert response.data["totals"][models.STATUS_QUEUED] == 4
    assert response.data["retry_exhausted"] == 6
    assert response.data["queued_by_channel"][models.CHANNEL_PRINT] == 4


def test_us_not_013_the_two_provider_statuses_are_served_as_not_reported(brazos, dana):
    """⚠ THE HONESTY CASE, at the API boundary.

    `delivered` and `bounced` are provider facts and no provider adapter exists
    on any channel (PO ruling 2026-08-15). "0 delivered of 142 sent" reads as a
    delivery failure when the truth is that nobody is reporting, so the two are
    served as `unpopulated_statuses` with the reason in `problems`. A screen
    that renders a zero there is rendering a lie, and this asserts the data it
    needs in order not to.
    """
    with tenant_ctx(brazos):
        a_row(brazos)

    response = call(notifications_api.outbound_summary, "get", brazos, dana)

    assert set(response.data["unpopulated_statuses"]) == {
        models.STATUS_DELIVERED,
        models.STATUS_BOUNCED,
    }
    codes = [problem["code"] for problem in response.data["problems"]]
    assert "provider_statuses_never_written" in codes


def test_us_not_013_tc2__the_list_puts_failures_first(brazos, dana):
    """EP-NOT-04's capability row: *"failed+bounced first, then queued_at."*

    The dispatch home is opened when something has gone wrong; a queue sorted
    newest-first buries the six failures under the nine hundred that are fine.
    """
    with tenant_ctx(brazos):
        for _ in range(5):
            a_row(brazos)  # queued, and NEWER than the failure below
        failed = a_row(brazos, status=models.STATUS_FAILED, last_error="provider timeout")
        models.OutboundMessage.objects.filter(pk=failed.pk).update(
            created_at=datetime(2020, 1, 1, tzinfo=dt_timezone.utc)
        )

    response = call(notifications_api.outbound, "get", brazos, dana)

    rows = response.data["results"]
    assert rows[0]["id"] == str(failed.pk), "the oldest FAILED row must still sort first"
    assert rows[0]["last_error"] == "provider timeout"


def test_us_not_013_tc3__requeue_over_http_clears_the_batch_id(brazos, dana, audit_rows):
    """US-NOT-013 TC-3, and the one line without which nothing ever moves.

    `delivery_ops.requeue`'s box: the dispatcher never re-selects a row it has
    claimed, so a crashed hand-off leaves rows `queued` WITH a batch id, matching
    neither branch of its predicate, forever. A re-queue that reset only the
    STATUS would look correct on every screen and fix nothing. This asserts the
    CLEARED COLUMN rather than the status, over the real endpoint.
    """
    with tenant_ctx(brazos):
        row = a_row(
            brazos,
            status=models.STATUS_FAILED,
            batch_id=uuid.uuid4(),
            attempts=3,
            last_error="provider timeout",
        )

    response = call(
        notifications_api.outbound_requeue, "post", brazos, dana, message_id=str(row.pk)
    )

    assert response.status_code == 200
    assert response.data["requeued"] == [str(row.pk)]
    assert response.data["dispatched"] is False  # a re-queue never bypasses batching
    with tenant_ctx(brazos):
        row.refresh_from_db()
    assert row.status == models.STATUS_QUEUED
    assert row.batch_id is None, "a re-queue that leaves batch_id set never moves again"
    assert row.attempts == 3, "attempts count PROVIDER tries and are never zeroed"


def test_us_not_013_tc4__a_held_row_is_refused_by_the_endpoint(brazos, dana):
    """US-NOT-013 TC-4: *"held rows release only via address verification."*

    Refused as DATA rather than as an exception, because a bulk selection with
    one held row in it is a normal Tuesday and must not kill the other ten.
    """
    with tenant_ctx(brazos):
        row = a_row(brazos, status=models.STATUS_FAILED, held=True, held_reason="bad_address")
        clean = a_row(brazos, status=models.STATUS_FAILED)

    response = call(
        notifications_api.outbound_requeue_bulk,
        "post",
        brazos,
        dana,
        data={"message_ids": [str(row.pk), str(clean.pk)]},
    )

    assert response.data["requeued"] == [str(clean.pk)]
    assert response.data["refused"][0]["code"] == "held_row_not_requeueable"


def test_us_not_013_tc5__a_forged_row_id_from_another_tenant_is_a_404(brazos, lonestar, dana):
    """US-NOT-013 TC-5 / HR-1: another tenant's id, an unknown id and a
    malformed id are ONE answer, so existence cannot be probed."""
    with tenant_ctx(lonestar):
        theirs = a_row(lonestar)

    response = call(
        notifications_api.outbound_requeue, "post", brazos, dana, message_id=str(theirs.pk)
    )

    assert response.status_code == 404, "another tenant's id must read as absent, never as 403"


def test_us_not_013_a_bulk_requeue_with_no_selection_is_refused(brazos, dana):
    """An empty selection is refused rather than read as *everything*: a bulk
    action that quietly meant "all" would return nine hundred rows to the pool
    because a checkbox did not register."""
    response = call(
        notifications_api.outbound_requeue_bulk, "post", brazos, dana, data={"message_ids": []}
    )

    assert response.status_code == 422
    assert response.data["code"] == errors.VAL_REQUIRED
    assert response.data["message_key"] == notifications_api.KEY_IDS_REQUIRED


# ══════════════════════════════════════════════════════════════════════════
# THE RESEND — CLAUDE.md rule 6, and real certified postage
# ══════════════════════════════════════════════════════════════════════════
def test_resend_without_a_copy_number_is_refused(brazos, marcus):
    """`copy_no` IS the idempotency key, so a resend without one is refused.

    An endpoint that allocated the number itself would post a second letter on
    every double click, every retried request and every impatient refresh — and
    would look perfectly correct doing it. `apps/payments/api.py` records the
    same reasoning for its own required token: *"generating one here would
    dedupe nothing while looking as if it had"*.
    """
    with tenant_ctx(brazos):
        row = a_row(brazos, status=models.STATUS_SENT)

    response = call(
        notifications_api.outbound_resend,
        "post",
        brazos,
        marcus,
        role="billing_clerk",
        data={},
        message_id=str(row.pk),
    )

    assert response.status_code == 422
    assert response.data["message_key"] == notifications_api.KEY_COPY_NO_REQUIRED
    with tenant_ctx(brazos):
        assert models.OutboundMessage.objects.filter(source_id=row.source_id).count() == 1


def test_resend_writes_a_new_row_at_the_stated_copy_number(brazos, marcus, audit_rows):
    """US-NOT-011 §5 / US-BIL-024 TC-4: a staff re-send *"creates new queue
    rows, audited"* — never an edit of the row the customer already has.

    The copy renders the SAME pinned template version (BR-BIL-026) and goes to
    the recipient SNAPSHOTTED at queue time (BR-TEN-017).
    """
    with tenant_ctx(brazos):
        row = a_row(brazos, status=models.STATUS_SENT)

    response = call(
        notifications_api.outbound_resend,
        "post",
        brazos,
        marcus,
        role="billing_clerk",
        data={"copy_no": 1},
        message_id=str(row.pk),
    )

    assert response.status_code == 201
    assert response.data["created"] is True
    assert response.data["dispatched"] is False  # queueing is not sending
    with tenant_ctx(brazos):
        copy = models.OutboundMessage.objects.get(
            tenant_id=brazos.id, source_id=row.source_id, copy_no=1
        )
    assert copy.pk != row.pk, "a resend is a NEW row, never an edit"
    assert copy.template_id == row.template_id and copy.template_version == row.template_version
    assert copy.recipient_address == row.recipient_address
    assert copy.status == models.STATUS_QUEUED
    # The unruled half is REPORTED on every call rather than left to be found.
    assert "OQ-223" in {problem.get("oq_ref") for problem in response.data["problems"]}


def test_us_not_001_tc5__a_resend_replay_writes_no_second_letter(brazos, marcus, audit_rows):
    """⚠ THE CASE THAT COSTS REAL POSTAGE. CLAUDE.md rule 6.

    The same resend submitted twice — a double click, a retried request, an
    impatient refresh — must find its own row in the DATABASE and post nothing.
    A duplicated 48-hour final notice costs certified postage AND misstates the
    legal record: two mailings where `notice_history` shows one.

    RED-PROVED before it was trusted green (hard-won law 7) — see the lane
    report for the transcript with `copy_no` auto-allocated instead of stated.
    """
    with tenant_ctx(brazos):
        row = a_row(brazos, source_type="notice", template_code="disconnect_notice")

    body = {"copy_no": 1}
    first = call(
        notifications_api.outbound_resend,
        "post",
        brazos,
        marcus,
        role="billing_clerk",
        data=body,
        message_id=str(row.pk),
    )
    second = call(
        notifications_api.outbound_resend,
        "post",
        brazos,
        marcus,
        role="billing_clerk",
        data=body,
        message_id=str(row.pk),
    )

    assert first.data["created"] is True and first.status_code == 201
    assert second.data["created"] is False and second.status_code == 200
    assert first.data["messages"][0]["id"] == second.data["messages"][0]["id"]
    with tenant_ctx(brazos):
        assert (
            models.OutboundMessage.objects.filter(
                tenant_id=brazos.id, source_id=row.source_id
            ).count()
            == 2
        ), "the original and ONE copy — a second letter was posted"
    # The screen needs this to put the confirmation in FRONT of a clerk.
    assert first.data["is_notice"] is True


def test_resend_refuses_a_held_row(brazos, marcus):
    """A held row is a letter to an address the customer's own mail already came
    back from (BR-PAY-018). Sending it again is the one outcome the hold exists
    to prevent."""
    with tenant_ctx(brazos):
        row = a_row(brazos, held=True, held_reason=delivery_ops.HELD_BAD_ADDRESS)

    response = call(
        notifications_api.outbound_resend,
        "post",
        brazos,
        marcus,
        role="billing_clerk",
        data={"copy_no": 1},
        message_id=str(row.pk),
    )

    assert response.data["code"] == errors.BIZ_STATE
    assert response.data["message_key"] == notifications_api.KEY_RESEND_HELD
    with tenant_ctx(brazos):
        assert models.OutboundMessage.objects.filter(source_id=row.source_id).count() == 1


# ══════════════════════════════════════════════════════════════════════════
# US-NOT-014 — returned mail, and the hand-off nothing had ever made
# ══════════════════════════════════════════════════════════════════════════
def test_returned_mail_flags_the_account_through_payments(brazos, marcus, dana, audit_rows):
    """⚠ THE GAP TWO MODULES EACH REPORTED AND NEITHER COULD CLOSE.

    `delivery_ops.py`'s trailer: *"`mark_returned` emits the delivery-return
    event; a caller that ignores it leaves the account unflagged and nothing
    here can stop that."* `apps/payments/returned_mail.mark_returned_bulk` is
    the consumer, and until this lane NOTHING CALLED IT.

    So this asserts a ROW in payments' `delivery_return_events`, not a
    docstring, and it asserts the account reads bad-address afterwards through
    payments' own derived read.
    """
    from apps.payments import returned_mail

    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        row = a_row(brazos, account_id=account.pk, status=models.STATUS_SENT)

    response = call(
        notifications_api.deliveries_returned,
        "post",
        brazos,
        marcus,
        role="billing_clerk",
        data={"message_ids": [str(row.pk)], "returned_on": RETURNED_ON},
    )

    assert response.status_code == 200
    assert response.data["marked"][0]["message_id"] == str(row.pk)
    assert response.data["balances_affected"] is False  # BR-PAY-018, on the wire
    assert response.data["flagged_accounts"][0]["account_id"] == str(account.pk)
    with tenant_ctx(brazos):
        row.refresh_from_db()
        assert row.returned_at is not None
        assert row.returned_at.date() == date.fromisoformat(RETURNED_ON)
        assert row.status == models.STATUS_SENT, "a returned letter WAS sent; status never moves"
        assert returned_mail.bad_address_for(account.pk) is True


def test_returned_mail_marked_twice_flags_once(brazos, marcus, dana, audit_rows):
    """CLAUDE.md rule 6 on the obvious Tuesday accident — a stack of fourteen
    worked twice. The queue row is idempotent by `returned_at` and payments'
    event table by `UNIQUE (tenant, outbound_message_id)`, so the account is
    flagged once and no second event is written."""
    from apps.payments.collections_models import DeliveryReturnEvent

    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11460")
        row = a_row(brazos, account_id=account.pk, status=models.STATUS_SENT)

    body = {"message_ids": [str(row.pk)], "returned_on": RETURNED_ON}
    for _ in range(2):
        call(
            notifications_api.deliveries_returned,
            "post",
            brazos,
            marcus,
            role="billing_clerk",
            data=body,
        )

    with tenant_ctx(brazos):
        assert (
            DeliveryReturnEvent.objects.filter(
                tenant_id=brazos.id, outbound_message_id=row.pk
            ).count()
            == 1
        )


def test_us_not_014_tc6__an_email_row_cannot_be_marked_returned(brazos, marcus, dana):
    """TC-6: an email that did not arrive comes back as a provider BOUNCE on a
    webhook — a fact from an ESP, not something a clerk can observe about an
    envelope. Refused by name, with the other rows in the selection unaffected.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11461")
        email_row = a_row(brazos, account_id=account.pk, channel=models.CHANNEL_EMAIL)

    response = call(
        notifications_api.deliveries_returned,
        "post",
        brazos,
        marcus,
        role="billing_clerk",
        data={"message_ids": [str(email_row.pk)], "returned_on": RETURNED_ON},
    )

    assert response.data["marked"] == []
    assert response.data["refused"][0]["code"] == "not_a_paper_row"


def test_returned_mail_needs_the_date_and_never_reads_a_clock(brazos, marcus):
    """BR-TEN-043 / gate G6: Tuesday's stack is marked as TUESDAY even when it
    is worked on Wednesday, so the date is an input and its absence is a
    refusal naming the field — never a default from the server's day."""
    with tenant_ctx(brazos):
        row = a_row(brazos)

    response = call(
        notifications_api.deliveries_returned,
        "post",
        brazos,
        marcus,
        role="billing_clerk",
        data={"message_ids": [str(row.pk)]},
    )

    assert response.status_code == 422
    assert response.data["message_key"] == notifications_api.KEY_RETURNED_DATE
    with tenant_ctx(brazos):
        row.refresh_from_db()
        assert row.returned_at is None, "nothing was stamped by a request that was refused"


# ══════════════════════════════════════════════════════════════════════════
# THE NOTICE RECORD + THE CERTIFIED-MAIL REGISTER
# ══════════════════════════════════════════════════════════════════════════
def a_recorded_notice(brazos, account, actor, **overrides):
    """One `notice_history` row through payments' REAL writer — never the ORM.

    The row shape matters: `detail` is what `apps/notifications/notices.py`
    hands back as a `HistoryAppend`, and the certified register reads it.
    """
    from apps.payments import notices as payments_notices

    values = dict(
        account_id=account.pk,
        notice_type="disconnect",
        outcome="sent",
        on_date=date(2026, 8, 14),
        tier="final_48_hour",
        channel=models.CHANNEL_PRINT,
        detail={
            "cut_date": "2026-08-18",
            "certified_mail": True,
            "template_version": 2,
            "reconnect_fee": str(RECONNECT_FEE),
        },
        actor=actor,
    )
    values.update(overrides)
    return payments_notices.record_notice(**values)


def test_the_notice_record_is_readable_and_money_carries_its_currency(brazos, dana, audit_rows):
    """The record a utility shows a regulator, served — and CLAUDE.md rule 2.

    `notice_history` had a writer since 2026-08-11 and NO READER, so every
    disconnect letter and every medical-hold skip was recorded where no surface
    could open it.

    The reconnect fee is money on a document a customer receives, so it is a
    STRING at NUMERIC(18,6) fidelity travelling with the tenant's currency —
    never a JSON number (which is a double) and never a bare figure a reader
    denominates for themselves.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11024")
        a_recorded_notice(brazos, account, dana)

    response = call(notifications_api.notices, "get", brazos, dana)

    assert response.data["available"] is True
    row = response.data["results"][0]
    assert row["tier"] == "final_48_hour"
    assert row["certified_mail"] is True
    assert row["reconnect_fee"] == str(RECONNECT_FEE)
    assert isinstance(row["reconnect_fee"], str), "money is never a JSON number"
    assert response.data["currency"] == row["currency"]
    assert row["currency"], "a money figure without its currency is a figure nobody can read"


def test_us_not_009_tc2__the_certified_register_narrows_to_the_final_tier(brazos, dana, audit_rows):
    """BR-CUS-039 — certified mail is REQUIRED on the 48-hour final tier and on
    no other, so `f.certified=true` IS a tier filter.

    ⚠ The certified NUMBER is NULL on every row and the response says why: it
    arrives on a print provider's response at dispatch and no provider adapter
    exists on any channel (PO 2026-08-15). A tracking number is never fabricated
    onto a legal record.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11340")
        a_recorded_notice(brazos, account, dana)
        a_recorded_notice(
            brazos,
            account,
            dana,
            tier="first_10_day",
            detail={"cut_date": "2026-08-30", "certified_mail": False, "template_version": 2},
        )

    response = call(notifications_api.notices, "get", brazos, dana, query={"f.certified": "true"})

    assert response.data["certified_only"] is True
    tiers = {row["tier"] for row in response.data["results"]}
    assert tiers == {"final_48_hour"}, "the 10-day letter is not a certified notice"
    assert response.data["results"][0]["certified_number"] is None
    codes = [problem["code"] for problem in response.data["problems"]]
    assert "certified_number_unavailable" in codes


def test_us_not_009_tc4__a_skipped_notice_is_on_the_record(brazos, dana, audit_rows):
    """J4 step 2: *"every send AND skip"*. An account excluded for a medical
    hold must never be indistinguishable from one nobody ever chased."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11020")
        a_recorded_notice(
            brazos,
            account,
            dana,
            outcome="skipped",
            skip_reason="medical_hold",
            detail={"cut_date": "2026-08-18"},
        )

    response = call(notifications_api.notices, "get", brazos, dana)

    row = response.data["results"][0]
    assert row["outcome"] == "skipped"
    assert row["skip_reason"] == "medical_hold"


def test_notices_report_when_the_record_cannot_be_opened(brazos, dana, monkeypatch):
    """⚠ DEF-075's shape, refused. An unreadable record and a customer who was
    never contacted MUST NOT render the same.

    The seam is unpublished here on purpose — the same experiment DEF-075's
    prevention column asks for — and the endpoint must answer `available: false`
    with a named reason rather than an empty list that a screen would render as
    "this customer was never told".
    """
    monkeypatch.setattr(payments_seam, "_resolve", lambda *a, **k: None)

    response = call(notifications_api.notices, "get", brazos, dana)

    assert response.data["available"] is False
    assert response.data["results"] == []
    codes = [problem["code"] for problem in response.data["problems"]]
    assert payments_seam.NOTICE_HISTORY_UNAVAILABLE in codes


def test_returned_mail_reports_when_payments_cannot_be_reached(
    brazos, marcus, dana, monkeypatch, audit_rows
):
    """The same posture on the write side: the queue row is stamped, NO account
    is flagged, and the response SAYS the letters will keep going to the same
    address — rather than reporting a clean success."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11462")
        row = a_row(brazos, account_id=account.pk, status=models.STATUS_SENT)
    monkeypatch.setattr(payments_seam, "_resolve", lambda *a, **k: None)

    response = call(
        notifications_api.deliveries_returned,
        "post",
        brazos,
        marcus,
        role="billing_clerk",
        data={"message_ids": [str(row.pk)], "returned_on": RETURNED_ON},
    )

    assert response.data["flagged_accounts"] == []
    codes = [problem["code"] for problem in response.data["problems"]]
    assert payments_seam.RETURN_CONSUMER_UNAVAILABLE in codes


# ══════════════════════════════════════════════════════════════════════════
# ISOLATION — CLAUDE.md hard rule 1
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.isolation
def test_us_not_013_tc6__one_tenants_dashboard_never_shows_anothers_traffic(
    brazos, lonestar, dana, erin
):
    """US-NOT-013 TC-6: *"Its rows only; counts never include Brazos Bend
    traffic (RLS)."* Both directions, because a leak in one is a leak."""
    with tenant_ctx(brazos):
        for _ in range(3):
            a_row(brazos)
    with tenant_ctx(lonestar):
        a_row(lonestar, recipient_address="12 Ridge Rd")

    theirs = call(notifications_api.outbound, "get", lonestar, erin)
    ours = call(notifications_api.outbound, "get", brazos, dana)

    assert theirs.data["count"] == 1
    assert ours.data["count"] == 3
    assert {row["recipient_address"] for row in theirs.data["results"]} == {"12 Ridge Rd"}


@pytest.mark.isolation
def test_the_notice_record_never_crosses_a_tenant(brazos, lonestar, dana, erin, audit_rows):
    """US-NOT-009 TC-7: *"Lone Star Ridge sees only its own notices (RLS)."*"""
    with tenant_ctx(brazos):
        a_recorded_notice(brazos, an_account(dana, brazos, account_no="A-11024"), dana)

    response = call(notifications_api.notices, "get", lonestar, erin)

    assert response.data["results"] == []
