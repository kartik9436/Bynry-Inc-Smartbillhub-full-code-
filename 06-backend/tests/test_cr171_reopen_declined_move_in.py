# ── Trace ──────────────────────────────────────────────
# Change:   CR-171-BRC10 (move-in redesign) · lane MVI-FLOW · Reopen (image 08)
# Rules:    PO ruling 2026-10-05, OQ-CUS-12789 CLOSED → (a), verbatim:
#           "Reopen: SR-26-0014 goes back to "To approve". Same number, her
#           documents stay, and the decline stays in its history." (decision
#           log "THREE PO RULINGS IN ONE REPLY") · supersedes, for MOVE-IN
#           requests only, the 2026-09-19 ruling that a refusal is terminal ·
#           CLAUDE.md hard rule 7 (audit_log)
# Tests:    this file (+ the hold-expiry case in test_cr171_move_in_request_view.py)
# ───────────────────────────────────────────────────────
"""**Reopen on a declined move-in request — proved through its door.**

RED-FIRST (law 7): written before the code; first run on the base tip
`492d316d9` failed on every case (`NotImplementedError: OQ-CUS-12789`,
`assert () == ('reopen',)`, `Resolver404` for the route).

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2):

  * **A reopen that wipes the refusal.** The history case asserts the REFUSED
    timeline row is still there, unchanged, beside the new one.
  * **A reopen that mints a new request.** The same-number case compares the
    `request_no` and the row id before and after, and counts the rows.
  * **A reopen that is open to every request.** The scope case declines a
    request whose resolver did NOT suggest a move-in and proves it is refused,
    and the generic `/transitions` door still refuses `reopen` by name.
"""

import pytest
from django.urls import resolve

from core import errors

from apps.customers import models as customers_models
from apps.customers import move_in_jobs, move_in_request
from apps.customers import service_request as rules
from apps.customers import service_request_api as api
from apps.customers import service_request_service as sr

from tests.test_cr171_move_in_request_view import _post, _to_approve
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import audit_rows, brazos, dana, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

TOLD = "We cannot confirm the lease for Unit 4A."


def _declined(actor, tenant):
    request, unit = _to_approve(actor, tenant)
    sr.refuse_request(
        actor,
        request.id,
        reason=TOLD,
        reason_code=rules.REFUSAL_OTHER,
        message_to_applicant=TOLD,
    )
    return sr.request_row(request.id), unit


def test_a_declined_request_offers_reopen_and_nothing_else():
    """Image 08: *Declined — More: Reopen*."""
    assert move_in_request.request_actions(rules.REFUSED) == ("reopen",)


def test_the_reopen_route_resolves_through_the_root_urlconf():
    assert (
        resolve("/api/brazos/service-requests/abc/reopen").func is api.service_request_reopen
    )


def test_reopen_returns_the_same_request_to_to_approve_with_its_documents(brazos, dana):
    """*"SR-26-0014 goes back to "To approve". Same number, her documents stay."*"""
    with tenant_ctx(brazos):
        request, _unit = _declined(dana, brazos)
        assert request.state == rules.REFUSED
        number, rows = request.request_no, customers_models.ServiceRequest.objects.count()
        docs = sorted(
            str(d.id)
            for d in customers_models.ServiceRequestDocument.objects.filter(request_id=request.id)
        )
        assert docs

        move_in_request.reopen(dana, request.id, reason="Lease received.")

        row = sr.request_row(request.id)
        assert row.request_no == number
        assert customers_models.ServiceRequest.objects.count() == rows
        assert row.state == rules.SUBMITTED
        assert move_in_request.request_status(row.state) == move_in_request.STATUS_TO_APPROVE
        # The decision is lifted off the row — it is undecided again — and
        # nothing else about the application moves.
        assert row.outcome is None and row.decided_at is None and row.closed_at is None
        assert row.decision_reason is None and row.refusal_message is None
        assert row.reason_code is None
        assert (
            sorted(
                str(d.id)
                for d in customers_models.ServiceRequestDocument.objects.filter(
                    request_id=request.id
                )
            )
            == docs
        )


def test_the_decline_stays_in_its_history_and_reopen_writes_audit_log(brazos, dana, audit_rows):
    """*"…and the decline stays in its history."* Append-only timeline: the
    refused row is still there with its reason; the reopen is a NEW row. Hard
    rule 7: the reopen lands an audit row carrying what was lifted."""
    with tenant_ctx(brazos):
        request, _unit = _declined(dana, brazos)
        audit_rows.clear()
        move_in_request.reopen(dana, request.id, reason="She sent the lease on 6 Oct.")

        events = list(
            customers_models.ServiceRequestEvent.objects.filter(
                request_id=request.id, kind=customers_models.ServiceRequestEvent.KIND_STATE
            ).order_by("at", "id")
        )
        moves = [(e.from_state, e.to_state) for e in events]
        assert (rules.MORE_INFO, rules.REFUSED) in moves or any(
            to == rules.REFUSED for _f, to in moves
        )
        refused = next(e for e in events if e.to_state == rules.REFUSED)
        assert refused.note == TOLD
        assert moves[-1] == (rules.REFUSED, rules.SUBMITTED)
        assert events[-1].note == "She sent the lease on 6 Oct."

    reopened = [r for r in audit_rows if r.get("action") == "service_request.reopened"]
    assert len(reopened) == 1, [r.get("action") for r in audit_rows]
    assert reopened[0]["before"]["state"] == rules.REFUSED
    assert reopened[0]["before"]["decision_reason"] == TOLD
    assert reopened[0]["after"]["state"] == rules.SUBMITTED


def test_reopen_needs_a_reason(brazos, dana):
    """`BR-CUS-072` (CONFIRMED): *"REOPENING REQUIRES A REASON"*. Blank is
    refused and nothing moves."""
    with tenant_ctx(brazos):
        request, _unit = _declined(dana, brazos)
        with pytest.raises(errors.ValidationError) as caught:
            move_in_request.reopen(dana, request.id, reason="  ")
        assert sr.request_row(request.id).state == rules.REFUSED
    assert caught.value.message_key == "customers.serviceRequest.reasonRequired"


def test_reopen_is_refused_unless_the_request_is_declined(brazos, dana):
    with tenant_ctx(brazos):
        request, _unit = _to_approve(dana, brazos)
        with pytest.raises(errors.BizError) as caught:
            move_in_request.reopen(dana, request.id, reason="Lease received.")
    assert caught.value.message_key == "customers.serviceRequest.transitionNotAllowed"


def test_reopen_is_refused_for_a_request_that_is_not_a_move_in(brazos, dana):
    """The ruling is about MOVE-IN requests. A declined request whose resolver
    did not suggest a move-in (no served, vacant unit) keeps the 2026-09-19
    rule: a refusal is final there."""
    with tenant_ctx(brazos):
        request, _unit = _declined(dana, brazos)
        customers_models.ServiceRequest.objects.filter(id=request.id).update(
            resolution_kind=customers_models.ServiceRequest.RESOLUTION_NO_PREMISE
        )
        with pytest.raises(errors.BizError) as caught:
            move_in_request.reopen(dana, request.id, reason="Lease received.")
        assert sr.request_row(request.id).state == rules.REFUSED
    assert caught.value.message_key == "customers.serviceRequest.reopenNotAMoveIn"


def test_the_generic_transitions_door_still_refuses_reopen(brazos, dana):
    """The request page's own door is unchanged: `reopen` is not one of its
    four moves, so nothing outside the move-in view can reopen anything."""
    assert rules.REOPEN not in rules.TRANSITIONS
    assert rules.REOPEN not in rules.actions_available(rules.REFUSED)
    with tenant_ctx(brazos):
        request, _unit = _declined(dana, brazos)
        with pytest.raises(errors.BizError):
            sr.transition(dana, request.id, rules.REOPEN, reason="x")


def test_reopen_through_the_route_then_approve_raises_the_job(brazos, dana):
    """The whole loop of image 08 → 03 → 18: reopened, it is approvable again
    and approval raises the *Not started* job exactly as a first approval does."""
    with tenant_ctx(brazos):
        request, _unit = _declined(dana, brazos)

    response = _post(
        api.service_request_reopen,
        f"/api/brazos/service-requests/{request.id}/reopen",
        request.id,
        {"reason": "Lease received."},
        brazos,
        dana,
    )
    assert response.status_code == 200, response.data
    assert response.data["header"]["state"] == rules.SUBMITTED

    approved = _post(
        api.service_request_approve,
        f"/api/brazos/service-requests/{request.id}/approve",
        request.id,
        {"outcome": "move_in"},
        brazos,
        dana,
    )
    assert approved.status_code == 200, approved.data
    with tenant_ctx(brazos):
        assert sr.request_row(request.id).state == rules.APPROVED
        job = move_in_jobs.MoveInJob.objects.get(request_id=request.id)
        assert job.state == move_in_jobs.STATE_PENDING


def test_the_statement_the_po_signed_on_2026_10_06(brazos, dana):
    """⚖️ THE HUMAN SIGN-OFF, ASSERTED SO DRIFT GOES RED (PO 2026-10-06,
    decision log *"SIX MOVE-IN MONEY FILES SIGNED"*, verbatim: *"Money-file
    review: approve these six? - all good - go ahead"*). Statement 5 of six,
    exactly as shown, for `service_request_service.reopen_declined_move_in`:

    *"Request SR-26-0014 was declined. A clerk can reopen it with a reason: it
    keeps the same number, goes back to "To approve", keeps her documents, and
    the decline stays in its history. No money moves."*

    SR-26-0014 is the example's number; the test asserts the number BEFORE is
    the number AFTER. "No money moves" is asserted on every money table a
    request can touch: payments, refunds, journal entries.
    """
    from apps.ledger import models as ledger_models
    from apps.payments import models as payment_models

    def _money():
        return (
            payment_models.Payment.objects.count(),
            payment_models.Refund.objects.count(),
            ledger_models.JournalEntry.objects.count(),
            ledger_models.JournalLine.objects.count(),
        )

    with tenant_ctx(brazos):
        request, _unit = _declined(dana, brazos)
        number = request.request_no
        docs = sorted(
            str(d.id)
            for d in customers_models.ServiceRequestDocument.objects.filter(request_id=request.id)
        )
        money_before = _money()

        # With a reason — and only with one.
        with pytest.raises(errors.ValidationError):
            move_in_request.reopen(dana, request.id, reason="")
        move_in_request.reopen(dana, request.id, reason="Lease received.")

        row = sr.request_row(request.id)
        docs_after = sorted(
            str(d.id)
            for d in customers_models.ServiceRequestDocument.objects.filter(request_id=request.id)
        )
        history = [
            e.to_state
            for e in customers_models.ServiceRequestEvent.objects.filter(
                request_id=request.id, kind=customers_models.ServiceRequestEvent.KIND_STATE
            ).order_by("at", "id")
        ]
        money_after = _money()

    assert row.request_no == number
    assert move_in_request.request_status(row.state) == move_in_request.STATUS_TO_APPROVE
    assert docs and docs_after == docs
    assert rules.REFUSED in history and history[-1] == rules.SUBMITTED
    assert money_after == money_before
