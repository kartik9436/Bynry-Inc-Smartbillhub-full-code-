# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-012 (write-offs: initiated in Payments, approved + reported
#           in Finance)   Screens: S34 · S35 · S36
# Rules:    BR-PAY-020 (initiate in payments, approve in finance, bad-debt GL) ·
#           BR-PAY-002 (append-only) · BR-PAY-037 (both acts recorded
#           distinctly) · BR-PAY-016 as amended (a write-off CLOSES the plan —
#           PO 2026-08-12, OQ-171) · CLAUDE.md rule 4 · rule 5 · rule 7
# ───────────────────────────────────────────────────────
"""US-PAY-012 on its own figure: **A-10802 Novak $948.20**.

TC-1's requirement is an ABSENCE — *"NO balance/ledger effect yet"* — and it is
the assertion this file cares about most: an initiation that quietly reduced AR
would be a write-off nobody approved.

RED-PROVED FIRST (hard-won law 7): moving `ledger_seam.post_write_off` from
`approve_write_off` into `request_write_off` makes TC-1 fail — the request
posts DR write-off / CR AR and the account's outstanding balance drops to 0.00
before any Owner/Admin has seen it. Transcript in the lane report.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from core import errors

from apps.payments import outstandings, writeoffs
from apps.payments.collections_models import (
    WRITE_OFF_APPROVED,
    WRITE_OFF_REASON_UNCOLLECTIBLE,
    WRITE_OFF_REQUESTED,
    WriteOff,
)
from apps.payments.exceptions import PaymentRuleError

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_001_record_payment import an_issued_bill
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

#: US-PAY-012 §4, verbatim: "A-10802 Novak, P.: balance $948.20, 91 days late".
NOVAK = Decimal("948.20")
NOTE = "120+ days, 3 notices, phone contact failed ×4"
REQUESTED_ON = date(2026, 8, 15)
POSTED_AT = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)


def _a_debtor(brazos, dana, *, account_no="A-10802", total=NOVAK):
    account = an_account(dana, brazos, account_no=account_no)
    an_issued_bill(
        brazos,
        account,
        number="BL-2605-018100",
        total=total,
        issued_on=date(2026, 5, 16),
        due_date=date(2026, 5, 16),
    )
    return account


def test_us_pay_012_tc1__an_initiation_moves_no_money(brazos, dana):
    """TC-1 — *"Pending-approval record; NO balance/ledger effect yet"*."""
    with tenant_ctx(brazos):
        account = _a_debtor(brazos, dana)
        result = writeoffs.request_write_off(
            dana,
            account_id=account.pk,
            amount=NOVAK,
            reason=WRITE_OFF_REASON_UNCOLLECTIBLE,
            note=NOTE,
            requested_on=REQUESTED_ON,
        )
        assert result.status == WRITE_OFF_REQUESTED
        assert result.posted_to_ledger is False
        row = WriteOff.objects.get(pk=result.write_off_id)
        assert row.journal_entry_id is None
        assert row.gl_account_id is None
        # The debt is still on the books and still on S34.
        view = outstandings.outstandings(as_of=REQUESTED_ON)
        assert view.total_owed == NOVAK


def test_us_pay_012_tc2__approval_posts_dr_write_off_cr_ar(brazos, dana):
    """TC-2 — **948.20 / 948.20**, balanced, and the balance closes.

    The GL is resolved BY DESIGNATION (`write_off`) and never by number —
    field-map P-17 records what happens when a screen names GL codes instead.
    """
    with tenant_ctx(brazos):
        account = _a_debtor(brazos, dana, account_no="A-10803")
        requested = writeoffs.request_write_off(
            dana,
            account_id=account.pk,
            amount=NOVAK,
            reason=WRITE_OFF_REASON_UNCOLLECTIBLE,
            note=NOTE,
            requested_on=REQUESTED_ON,
        )
        approved = writeoffs.approve_write_off(
            actor=dana,
            write_off_id=requested.write_off_id,
            approved_on=REQUESTED_ON,
            posted_at=POSTED_AT,
        )
        assert approved.status == WRITE_OFF_APPROVED
        assert approved.posted_to_ledger is True
        row = WriteOff.objects.get(pk=approved.write_off_id)
        assert row.journal_entry_id is not None
        assert row.gl_account_id is not None
        # BR-PAY-037: BOTH acts on the row, separately.
        assert row.requested_by_id is not None and row.approved_by_id is not None


def test_us_pay_012_tc2b__approving_twice_does_not_post_twice(brazos, dana):
    """An approved write-off has already reduced AR; a second click must not
    halve it again."""
    with tenant_ctx(brazos):
        account = _a_debtor(brazos, dana, account_no="A-10804")
        requested = writeoffs.request_write_off(
            dana,
            account_id=account.pk,
            amount=NOVAK,
            reason=WRITE_OFF_REASON_UNCOLLECTIBLE,
            note=NOTE,
            requested_on=REQUESTED_ON,
        )
        first = writeoffs.approve_write_off(
            actor=dana,
            write_off_id=requested.write_off_id,
            approved_on=REQUESTED_ON,
            posted_at=POSTED_AT,
        )
        second = writeoffs.approve_write_off(
            actor=dana,
            write_off_id=requested.write_off_id,
            approved_on=REQUESTED_ON,
            posted_at=POSTED_AT,
        )
        assert str(second.journal_entry_id) == str(first.journal_entry_id)
        assert "already_approved" in {problem["code"] for problem in second.problems}


def test_us_pay_012_tc5__the_note_is_required(brazos, dana):
    """TC-5 — the prototype marks it *Required* and so does the server."""
    with tenant_ctx(brazos):
        account = _a_debtor(brazos, dana, account_no="A-10805")
        with pytest.raises(PaymentRuleError) as refusal:
            writeoffs.request_write_off(
                dana,
                account_id=account.pk,
                amount=NOVAK,
                reason=WRITE_OFF_REASON_UNCOLLECTIBLE,
                note="   ",
                requested_on=REQUESTED_ON,
            )
        assert "note" in str(refusal.value)


def test_us_pay_012_more_than_the_account_owes_is_refused(brazos, dana):
    """Writing off more than was billed would put revenue into bad debt that no
    customer was ever charged. Checked against COMPUTED AR, never the cache."""
    with tenant_ctx(brazos):
        account = _a_debtor(brazos, dana, account_no="A-10806")
        with pytest.raises(PaymentRuleError) as refusal:
            writeoffs.request_write_off(
                dana,
                account_id=account.pk,
                amount=NOVAK + Decimal("1.00"),
                reason=WRITE_OFF_REASON_UNCOLLECTIBLE,
                note=NOTE,
                requested_on=REQUESTED_ON,
            )
        assert "actually owes" in str(refusal.value)


def test_us_pay_012_an_unratified_reason_is_refused(brazos, dana):
    """P-4/P-5 — *"send to collections agency"* has no rule and no value."""
    with tenant_ctx(brazos):
        account = _a_debtor(brazos, dana, account_no="A-10807")
        with pytest.raises(PaymentRuleError):
            writeoffs.request_write_off(
                dana,
                account_id=account.pk,
                amount=NOVAK,
                reason="sent_to_collections_agency",
                note=NOTE,
                requested_on=REQUESTED_ON,
            )


def test_us_pay_012_tc5b__approval_is_owner_admin_only_and_server_enforced(brazos, marcus, dana):
    """TC-5 — a Billing Clerk may INITIATE and may not APPROVE (BR-PAY-020).

    Server-enforced: a screen that hides the button is not an authorisation
    (BR-SHL-025).
    """
    with tenant_ctx(brazos):
        account = _a_debtor(brazos, dana, account_no="A-10808")
        requested = writeoffs.request_write_off(
            marcus,
            account_id=account.pk,
            amount=NOVAK,
            reason=WRITE_OFF_REASON_UNCOLLECTIBLE,
            note=NOTE,
            requested_on=REQUESTED_ON,
        )
        with pytest.raises(errors.AuthError):
            writeoffs.approve_write_off(
                actor=marcus,
                write_off_id=requested.write_off_id,
                approved_on=REQUESTED_ON,
                posted_at=POSTED_AT,
            )


def test_us_pay_012_tc7__isolation_a_write_off_of_another_tenant_is_invisible(
    brazos, dana, lonestar
):
    """TC-7 — *"Its GL accounts + approvals only; Brazos Bend rows invisible"*."""
    with tenant_ctx(brazos):
        account = _a_debtor(brazos, dana, account_no="A-10809")
        requested = writeoffs.request_write_off(
            dana,
            account_id=account.pk,
            amount=NOVAK,
            reason=WRITE_OFF_REASON_UNCOLLECTIBLE,
            note=NOTE,
            requested_on=REQUESTED_ON,
        )
    with tenant_ctx(lonestar):
        with pytest.raises(PaymentRuleError):
            writeoffs.approve_write_off(
                actor=dana,
                write_off_id=requested.write_off_id,
                approved_on=REQUESTED_ON,
                posted_at=POSTED_AT,
            )


# ══════════════════════════════════════════════════════════════════════════
# DEF-100 — the approval QUEUE. Without it the two-person split is nominal.
# ══════════════════════════════════════════════════════════════════════════
#
# BR-PAY-020 splits a write-off on purpose: initiated in Payments, approved and
# reported in FINANCE. The backend served POST and POST-approve and no GET at
# all, so nothing could answer *"what is awaiting my approval?"* — and the only
# write-off id a browser could hold was the one the requester's own screen had
# just minted. The Approve control therefore had to sit beside the request.
#
# ⚠ WHAT THIS DOES **NOT** CHANGE: BR-PAY-037 is CONFIRMED and says the SAME
# user holding the approver role MAY initiate AND approve in v1, both acts
# recorded distinctly; enforced separation-of-duties is v2. No test here asserts
# a different-person refusal and no code was written for one — an implementing
# lane does not overturn a confirmed rule. What is asserted is that the queue is
# LISTABLE, which is what lets the control live on the Finance screen.


def test_def_100_tc1__the_queue_lists_what_is_awaiting_approval(brazos, dana):
    """The read that did not exist. A **948.20** request is findable by a second
    person who never saw the screen that made it."""
    with tenant_ctx(brazos):
        account = _a_debtor(brazos, dana, account_no="A-10810")
        requested = writeoffs.request_write_off(
            dana,
            account_id=account.pk,
            amount=NOVAK,
            reason=WRITE_OFF_REASON_UNCOLLECTIBLE,
            note=NOTE,
            requested_on=REQUESTED_ON,
        )
        queue = writeoffs.write_off_queue(status=WRITE_OFF_REQUESTED)

    ids = [row["id"] for row in queue]
    assert requested.write_off_id in ids, (
        "the whole defect: a write-off that exists and cannot be listed can only "
        "be approved by whoever is holding its id — the requester"
    )
    row = next(row for row in queue if row["id"] == requested.write_off_id)
    assert row["amount"] == "948.2000"
    # CLAUDE.md rule 2 / DEF-099 — the figure never travels without its code.
    assert row["currency"] == "USD"
    assert row["status"] == WRITE_OFF_REQUESTED
    assert row["posted_to_ledger"] is False, (
        "a request moves nothing until approved (US-PAY-012 TC-1) and the queue "
        "must say so, or Finance is approving something it thinks already posted"
    )
    assert row["account_no"] == "A-10810"
    assert row["approved_on"] is None and row["approved_by"] is None


def test_def_100_tc2__an_approved_write_off_leaves_the_pending_queue(brazos, dana):
    """A queue that still shows approved rows is not a queue — the approver
    cannot tell what is left to do, which is the reason for having one."""
    with tenant_ctx(brazos):
        account = _a_debtor(brazos, dana, account_no="A-10811")
        requested = writeoffs.request_write_off(
            dana,
            account_id=account.pk,
            amount=NOVAK,
            reason=WRITE_OFF_REASON_UNCOLLECTIBLE,
            note=NOTE,
            requested_on=REQUESTED_ON,
        )
        assert requested.write_off_id in [
            row["id"] for row in writeoffs.write_off_queue(status=WRITE_OFF_REQUESTED)
        ]
        writeoffs.approve_write_off(
            actor=dana,
            write_off_id=requested.write_off_id,
            approved_on=REQUESTED_ON,
            posted_at=POSTED_AT,
        )
        pending = writeoffs.write_off_queue(status=WRITE_OFF_REQUESTED)
        approved = writeoffs.write_off_queue(status=WRITE_OFF_APPROVED)

    assert requested.write_off_id not in [row["id"] for row in pending]
    row = next(row for row in approved if row["id"] == requested.write_off_id)
    assert row["posted_to_ledger"] is True and row["journal_entry_id"] is not None
    # BR-PAY-037 — BOTH acts, separately, on the row a reviewer reads.
    assert row["requested_by"] is not None and row["approved_by"] is not None


def test_def_100_tc3__an_unknown_status_filter_refuses_rather_than_answering_empty(brazos, dana):
    """An empty queue and an unanswerable one look identical on a screen, and
    one of them means *approve nothing today*."""
    with tenant_ctx(brazos):
        with pytest.raises(PaymentRuleError) as excinfo:
            writeoffs.write_off_queue(status="pending")
    assert "not a write-off status" in str(excinfo.value)


def test_def_100_tc4__the_queue_never_crosses_a_tenant_boundary(brazos, dana, lonestar):
    """Hard rule 1. Another utility's bad debt must not appear in this
    utility's approval queue — it is money and it is a decision."""
    with tenant_ctx(brazos):
        account = _a_debtor(brazos, dana, account_no="A-10812")
        mine = writeoffs.request_write_off(
            dana,
            account_id=account.pk,
            amount=NOVAK,
            reason=WRITE_OFF_REASON_UNCOLLECTIBLE,
            note=NOTE,
            requested_on=REQUESTED_ON,
        )
    with tenant_ctx(lonestar):
        theirs = writeoffs.write_off_queue()
    assert mine.write_off_id not in [row["id"] for row in theirs]


def test_def_100_tc5__the_route_answers_get_and_the_url_resolves(brazos, dana):
    """LAW 0 / hard-won law 2 — a service function is not an endpoint.

    The defect was in `apps/payments/api.py`, not in the service: the path was
    registered POST-only, so a Finance screen calling it got 405 and the
    approval queue could not be built at all. This calls the REAL view through
    the REAL urlpatterns entry, because that is the thing that was missing.
    """
    from apps.payments import api as payments_api

    from tests.test_us_ten_helpers import api_call

    with tenant_ctx(brazos):
        account = _a_debtor(brazos, dana, account_no="A-10813")
        writeoffs.request_write_off(
            dana,
            account_id=account.pk,
            amount=NOVAK,
            reason=WRITE_OFF_REASON_UNCOLLECTIBLE,
            note=NOTE,
            requested_on=REQUESTED_ON,
        )

    route = next(entry for entry in payments_api.urlpatterns if str(entry.pattern) == "write-offs")
    assert "get" in route.callback.cls.http_method_names, (
        "DEF-100 exactly: the path was registered POST-only, so every GET was a "
        "405 from the router and no queue could exist on any screen"
    )
    response = api_call(
        payments_api.write_offs,
        "get",
        user=_FakeUser(),
        role="system_admin",
        tenant=brazos,
        query={"f.status": WRITE_OFF_REQUESTED},
    )
    assert response.status_code == 200, response.data
    rows = response.data["rows"]
    assert [row["amount"] for row in rows] == ["948.2000"]
    assert rows[0]["currency"] == "USD"
    assert rows[0]["posted_to_ledger"] is False


class _FakeUser:
    """The shape `api_call` force-authenticates with (see tests/test_us_ten_helpers)."""

    is_authenticated = True
    pk = None
    id = None
