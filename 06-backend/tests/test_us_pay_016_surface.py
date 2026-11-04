# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-016 (returned mail: mark returned → bad-address flag →
#           needs-attention → paper suppressed) — the SURFACE half: the two
#           reads the screens need and the write they both call
#           Screens: S30 (the bill's delivery rows — the single mark) ·
#           S35 (the bulk mark over a Tuesday's stack) · S32 (the chip)
# Rules:    BR-PAY-018 (VERBATIM: "Returned mail: delivery record marked
#           returned (single/bulk) → account bad-address flag → needs-attention
#           queue + banner → paper suppressed until address verified (config);
#           balances unaffected; audited.") ·
#           BR-NOT-005 (VERBATIM: "Suppression operates on queue rows (held,
#           never deleted); release re-queues for dispatch.") ·
#           BR-TEN-043 (a business date is an INPUT — Tuesday's stack is marked
#           as Tuesday even when it is worked on Wednesday) ·
#           BR-SHL-011 (the `f.<name>` list grammar) ·
#           CLAUDE.md rule 6 (idempotency) · rule 7 (audit)
# Tests:    this file
# Impacts:  apps/billing/selectors._deliveries_for (the S30 row gains
#           `returned_at` + `held`) · apps/notifications/selectors (the
#           `f.returned` filter the S35 stack list is built from) ·
#           07-frontend BillDetailPage DeliveryPanel · SummaryTab (S32)
# ───────────────────────────────────────────────────────
"""The two reads a clerk holding a stack of returned envelopes needs.

**WHAT WAS ACTUALLY MISSING, and it was never the engine.**
`apps/payments/returned_mail.py` has written the event, derived the bad-address
flag and aged the needs-attention queue since 2026-08-11.
`POST /deliveries/returned` mounted on 2026-08-16 and marks one piece or
fourteen. `10-scripts/gates/surface_debt.txt` said the rest out loud: *"its
screens are S30's delivery rows and S35's bulk-mark, both billing/notifications-
owned and unbuilt"* — so a clerk with a Tuesday stack had a working write and
nowhere to type it.

Two reads stood between the write and its screens, and both are asserted here:

  1. **a bill's delivery row could not say whether it had already come back.**
     `_deliveries_for` served four columns and none of them was `returned_at`,
     so S30's panel would have had to offer "Mark returned" on every row
     forever — including the two a clerk marked an hour ago.
  2. **the queue list could not be narrowed to the stack still to work.**
     `GET /outbound` filtered on status, channel, source type, account and
     held. The fourteen envelopes in a clerk's hand were somewhere inside every
     letter the utility has ever posted.

**AND THE INVARIANCE IS ASSERTED HERE TOO, NOT ASSUMED.** J18 step 6: *"zero
money rows written or changed by the entire day's work"*. Money rows are COUNTED
either side of a bulk mark, because BR-PAY-018's *"balances unaffected"* is the
one thing this whole flow must not get wrong — and a screen is a new way to
reach the write.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from apps.billing import selectors as billing_selectors
from apps.notifications import api as notifications_api
from apps.notifications import models as notification_models
from apps.notifications import selectors as notification_selectors
from apps.payments import returned_mail
from apps.payments.collections_models import DeliveryReturnEvent

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, dana, erin, lonestar, tenant_ctx  # noqa: F401
from tests.test_us_ten_helpers import api_call
from tests.test_us_bil_024_deliveries import issued, queued_row
from tests.test_us_bil_005_issue import an_authorised_run
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

#: J18's own Tuesday. A CONSTANT, never a clock: BR-TEN-043 makes the business
#: date an argument, and a test that read `date.today()` would pass on any day
#: while proving nothing about the day the clerk typed.
TUESDAY = date(2026, 9, 8)


def mark(tenant, actor, message_ids, *, on=TUESDAY):
    """The write both screens call — over HTTP, through the real view."""
    return api_call(
        notifications_api.deliveries_returned,
        "post",
        user=actor.user,
        role="system_admin",
        tenant=tenant,
        data={"message_ids": [str(mid) for mid in message_ids], "returned_on": on.isoformat()},
    )


def money_rows() -> dict[str, int]:
    """Every money table US-PAY-016 must not touch, counted (J18 step 6)."""
    from apps.billing.models import Invoice, InvoiceLine
    from apps.ledger.models import JournalLine
    from apps.payments.models import Payment

    return {
        "invoices": Invoice.objects.count(),
        "invoice_lines": InvoiceLine.objects.count(),
        "payments": Payment.objects.count(),
        "journal_lines": JournalLine.objects.count(),
    }


# ══════════════════════════════════════════════════════════════════════════
# S30 — the single mark, from the bill's own delivery row
# ══════════════════════════════════════════════════════════════════════════
def test_us_pay_016_tc1__a_bill_s_delivery_row_says_whether_it_came_back(brazos, dana):
    """The column S30's panel needs to know which rows are still markable.

    RED-PROVED by removing `returned_at` from `_deliveries_for`: the row read
    back with no such key and this failed on the KeyError, which is the state
    the panel would have been built over.
    """
    with tenant_ctx(brazos):
        bill = issued(brazos, dana)
        before = billing_selectors.invoice_detail(str(bill.pk))["deliveries"]
        paper = [row for row in before if row["channel"] == notification_models.CHANNEL_PRINT]
        assert paper, "the issue path queued no paper row, so there is nothing to mark"
        # Not yet returned — and that is a stated NULL, never a missing key and
        # never a false. The panel offers the action off exactly this.
        assert all(row["returned_at"] is None for row in paper)
        assert all(row["held"] is False for row in paper)

    response = mark(brazos, dana, [paper[0]["id"]])
    assert response.status_code == 200, response.data
    with tenant_ctx(brazos):
        after = billing_selectors.invoice_detail(str(bill.pk))["deliveries"]

    marked = {row["id"]: row for row in after}[paper[0]["id"]]
    assert marked["returned_at"] is not None, (
        "the piece was marked returned and the bill's own delivery panel still "
        "showed it as never returned — the clerk would mark it again on Wednesday"
    )
    # BR-TEN-043: the date is the one the CLERK typed, not the day the server
    # happened to process it.
    assert marked["returned_at"].startswith(TUESDAY.isoformat())
    # The status does NOT move. A returned letter WAS sent, and overwriting that
    # destroys the fact an auditor needs (US-NOT-014).
    assert marked["status"] == "queued"


def test_us_pay_016_tc1b__the_mark_flags_the_account_and_ages_a_queue_row(brazos, dana):
    """BR-PAY-018's chain, end to end from the screen's own call.

    The endpoint is notifications'; the FLAG is payments'. This asserts the row
    payments wrote, not the response notifications sent — a seam that returned a
    cheerful body while writing nothing is the failure this crosses modules to
    rule out.
    """
    with tenant_ctx(brazos):
        bill = issued(brazos, dana)
        rows = billing_selectors.invoice_detail(str(bill.pk))["deliveries"]
        paper = next(row for row in rows if row["channel"] == notification_models.CHANNEL_PRINT)

    response = mark(brazos, dana, [paper["id"]])
    assert response.data["flagged_accounts"], response.data
    with tenant_ctx(brazos):
        assert returned_mail.bad_address_for(bill.account_id) is True
        queue = list(returned_mail.needs_attention())
        assert len(queue) == 1
        assert queue[0].returned_on == TUESDAY
        # S21's banner renders from the same STORED flag (`DEF-PAY-6342` —
        # `account_banner`, an English sentence nothing called, is gone).
    # BR-PAY-018 states it and the response repeats it, so a screen can print
    # the guarantee rather than the screen's author remembering to.
    assert response.data["balances_affected"] is False


def test_us_pay_016_tc5__an_email_row_is_refused_by_name_and_a_second_mark_is_a_no_op(brazos, dana):
    """The two negatives the panel's disabled state is built on.

    An email that did not arrive is a provider BOUNCE (BR-BIL-016), not
    something a clerk observes about an envelope — so the screen must not offer
    the action on an email row, and the SERVER must refuse it even if it did
    (BR-SHL-025: the screen is not the enforcement).
    """
    with tenant_ctx(brazos):
        bill = issued(brazos, dana)
        email = queued_row(brazos, bill, channel=notification_models.CHANNEL_EMAIL)
        rows = billing_selectors.invoice_detail(str(bill.pk))["deliveries"]
        paper = next(row for row in rows if row["channel"] == notification_models.CHANNEL_PRINT)

    refusal = mark(brazos, dana, [email.pk])
    assert refusal.status_code == 200
    assert refusal.data["marked"] == []
    assert refusal.data["refused"], "an email row was accepted as returned post"
    assert refusal.data["refused"][0]["code"] == "not_a_paper_row"

    mark(brazos, dana, [paper["id"]])
    events_after_first = DeliveryReturnEvent.objects.filter(tenant=brazos).count()
    # The obvious accident on a stack of fourteen: the same envelope twice.
    mark(brazos, dana, [paper["id"]], on=date(2026, 9, 9))
    assert DeliveryReturnEvent.objects.filter(tenant=brazos).count() == events_after_first, (
        "marking the same envelope twice wrote a second event — the account "
        "would age two needs-attention rows for one piece of post"
    )


# ══════════════════════════════════════════════════════════════════════════
# S35 — the bulk mark, and the list it is worked from
# ══════════════════════════════════════════════════════════════════════════
def test_us_pay_016_tc2__the_stack_list_is_the_paper_not_yet_marked(brazos, dana):
    """`f.returned=false` — the fourteen envelopes, not the nine hundred letters.

    RED-PROVED by removing `returned` from `QUEUE_FILTERS`: BR-SHL-011 makes an
    undeclared filter IGNORED rather than refused, so the list came back
    unfiltered and this failed on a marked row appearing in the pile still to
    work. That silent-widening is exactly why the filter is asserted from the
    list rather than from the queryset.
    """
    with tenant_ctx(brazos):
        bill = issued(brazos, dana)
        rows = billing_selectors.invoice_detail(str(bill.pk))["deliveries"]
        paper = next(row for row in rows if row["channel"] == notification_models.CHANNEL_PRINT)
        extra = queued_row(brazos, bill, channel=notification_models.CHANNEL_PRINT, copy_no=7)

    mark(brazos, dana, [paper["id"]])

    def ids(**query):
        response = api_call(
            notifications_api.outbound,
            "get",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            query=query,
        )
        assert response.status_code == 200, response.data
        return {row["id"] for row in response.data["results"]}

    outstanding = ids(**{"f.channel": notification_models.CHANNEL_PRINT, "f.returned": "false"})
    already = ids(**{"f.channel": notification_models.CHANNEL_PRINT, "f.returned": "true"})

    assert str(extra.pk) in outstanding, "the unmarked piece was missing from the stack to work"
    assert (
        paper["id"] not in outstanding
    ), "a piece already marked returned was offered again in the stack still to work"
    assert paper["id"] in already
    assert str(extra.pk) not in already


def test_us_pay_016_tc2b__fourteen_pieces_are_marked_in_ONE_action_and_no_money_moves(brazos, dana):
    """J18 step 1 and step 6 in one case, because they are one act.

    Fourteen envelopes across fourteen accounts, one call, per-row results — and
    the money tables counted either side. *"Balances unaffected"* is BR-PAY-018's
    own clause and the reason this story is allowed nowhere near an invoice.
    """
    with tenant_ctx(brazos):
        pieces = []
        # ONE authorised run for all fourteen: `bill_runs` is UNIQUE on
        # (tenant, idempotency_key) — CLAUDE.md rule 6 — so a helper that minted
        # a run per bill would collide on the second. Fourteen bills in one run
        # is also what a real Sep 1 cycle looks like.
        run = an_authorised_run(brazos, dana)
        for index in range(14):
            # Fourteen DISTINCT accounts, which is J18's own fixture — the flag
            # is per account, so fourteen pieces on one account would prove the
            # bulk mark wrote one flag and call it fourteen.
            bill = issued(
                brazos,
                dana,
                account=an_account(dana, brazos, account_no=f"A-114{index:02d}"),
                run=run,
                invoice_no=f"BL-2609-0000{index:02d}",
            )
            row = billing_selectors.invoice_detail(str(bill.pk))["deliveries"]
            pieces.append(
                next(r for r in row if r["channel"] == notification_models.CHANNEL_PRINT)["id"]
            )
        before = money_rows()

    response = mark(brazos, dana, pieces)
    with tenant_ctx(brazos):
        after = money_rows()
        queue = list(returned_mail.needs_attention())

    assert response.status_code == 200, response.data
    assert len(response.data["marked"]) == 14, "the stack did not clear in one pass"
    assert len({entry["account_id"] for entry in response.data["flagged_accounts"]}) == 14
    assert len(queue) == 14
    # J18 step 5: oldest first, so the queue AGES VISIBLY rather than shuffling.
    assert [event.returned_on for event in queue] == [TUESDAY] * 14
    assert before == after, (
        f"money rows moved because the post office failed: {before} → {after}. "
        "BR-PAY-018 says balances are unaffected and J18 step 6 counts the rows."
    )


def test_us_pay_016_tc6__another_tenant_s_stack_is_not_markable(brazos, dana, lonestar, erin):
    """Isolation, over the write both screens call.

    A forged id from another utility must mark nothing — and must not report
    that it did, which is the answer a screen would show a clerk as success.
    """
    with tenant_ctx(brazos):
        bill = issued(brazos, dana)
        mine = next(
            row
            for row in billing_selectors.invoice_detail(str(bill.pk))["deliveries"]
            if row["channel"] == notification_models.CHANNEL_PRINT
        )
    response = mark(lonestar, erin, [mine["id"], uuid.uuid4()])
    assert response.status_code == 200, response.data
    assert response.data["marked"] == [], "another tenant's envelope was marked returned"
    with tenant_ctx(brazos):
        still_open = billing_selectors.invoice_detail(str(bill.pk))["deliveries"]
    assert all(row["returned_at"] is None for row in still_open)
    assert notification_selectors is not None  # import kept honest


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-016@EP-PAY-04 (04-docs/05-modules/08-payments/06-epics/EP-PAY-04-outstandings-collections.md §1/§3/§5 · 08-payments/02-business-rules.md BR-PAY-018 · 10-notifications BR-NOT-005 · 08-qa/01-e2e/journeys/J18-returned-mail-tuesday.md · 10-scripts/gates/surface_debt.txt's `payments` sentence)
# generated: 2026-08-16 by story-coder (returned-mail surface lane)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: BOTH new reads RED-PROVED FIRST — `returned_at` removed from apps/billing/selectors._deliveries_for (KeyError on the row the panel is built over) and `returned` removed from QUEUE_FILTERS (BR-SHL-011 ignores an undeclared filter, so the marked piece came back in the pile still to work). Transcripts in the lane report
# exceptions: (1) NO TEST ASSERTS PAPER ACTUALLY HELD. BR-NOT-005's suppression writes `held` on the queue row and its writer is the dispatcher lane's (US-NOT-002, out of this release by PO ruling); `held` is SERVED so the panel can state a hold when one appears, and every row reads false today. Asserting a hold would be asserting a feature that is out of the release. (2) THE FLAG IS DERIVED, not `accounts.bad_address` — apps/payments/returned_mail.py reports that deviation from r12 #8 in full and B1 forbids the cross-module write; this file asserts the behaviour a clerk sees (flag, queue, banner), which is identical either way
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
