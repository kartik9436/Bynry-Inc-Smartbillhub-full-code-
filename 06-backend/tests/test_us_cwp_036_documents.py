# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-036 (EP-CWP-07) — documents and letters: what we sent, when,
#           and by which route. Screen: CWP-031
# Rules:    BR-CWP-083 (post and email remain the DELIVERY RECORD) ·
#           BR-CWP-045 (documents are SERVED, never re-rendered) ·
#           BR-CWP-010 (tenant AND the account set, both in the query) ·
#           BR-BIL-036 (an account with no email address is NORMAL — the
#           absence is RECORDED) · B14 rule 31 (no database id is a visible
#           value) · `OQ-1399` CLOSED — the portal is a convenience copy
# Tests:    this file
# Impacts:  apps/notifications/correspondence_reads.py (the published read) ·
#           apps/portal/seams/notifications_seam.py · apps/portal/selectors.py
# ───────────────────────────────────────────────────────
"""`US-CWP-036`'s cases — and the one the whole screen turns on.

⚠ **THE SCREEN MAY SAY *WE SENT THIS* AND MAY NEVER SAY *YOU RECEIVED THIS*.**
`outbound_messages` records what left the building; `delivered` and `bounced`
are provider facts and no provider adapter exists on print, email or SMS. Every
test below that asserts a state is really asserting that boundary, and TC-DEL
asserts it directly: a row the dispatcher never touched reads *queued*, never
*delivered*, and never an empty cell that a reader would fill in themselves.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from apps.notifications import correspondence_reads, models as notifications_models
from apps.portal import selectors as portal_selectors
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import (
    an_issued_bill,
    elm_street_account,
    switch_on,
)

AUGUST = date(2026, 8, 30)
JULY = date(2026, 7, 30)

#: The demo script's own figures (`US-CWP-036` §4).
AUGUST_BILL = "142.1800"
JULY_BILL = "138.4400"


def a_message(
    tenant,
    account,
    *,
    source_type,
    source_id,
    channel,
    on,
    template_code=None,
    status=notifications_models.STATUS_QUEUED,
    address="1408 Elm St · A",
    unavailable_reason=None,
    held=False,
    held_reason=None,
    sent_at=None,
):
    """One queue row, in the shape the dispatcher would have met it."""
    row = notifications_models.OutboundMessage.objects.create(
        tenant=tenant,
        account=account,
        source_type=source_type,
        source_id=source_id,
        channel=channel,
        template_code=template_code,
        status=status,
        recipient_address=address,
        unavailable_reason=unavailable_reason,
        held=held,
        held_reason=held_reason,
        sent_at=sent_at,
    )
    # `created_at` is `auto_now_add`, so the fixture's day is set afterwards —
    # the read orders on it and TC-1 asserts newest first.
    notifications_models.OutboundMessage.objects.filter(pk=row.pk).update(
        created_at=datetime(on.year, on.month, on.day, 9, 0, tzinfo=UTC)
    )
    row.refresh_from_db()
    return row


def read(tenant, account_ids):
    with tenant_context(tenant.id):
        return correspondence_reads.account_correspondence(account_ids=account_ids)


def portal_read(tenant, account):
    """`DEF-CWP-3969` — the PORTAL's own rows, which is where the group and the
    naming facts are decided. `read` above returns the notifications module's
    published row, one layer earlier, and carries neither."""
    with tenant_context(tenant.id):
        return portal_selectors.documents(account)["documents"]


@pytest.mark.django_db
def test_us_cwp_036_tc2_a_bill_sent_BOTH_WAYS_is_ONE_row_naming_BOTH_routes(pine_hill, sarah):
    """`BR-CWP-083` — *Post · Email*, one document, every route it went by.

    The queue's grain is one row per document per CHANNEL, so the August bill
    posted and emailed is TWO rows. A customer asking *"what did you send me"*
    is owed ONE document, and the grouping is in the read rather than in a
    screen — J47 step 4's *"every row's How names every route it went by"*.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        bill = an_issued_bill(
            pine_hill, account, number="BL-2608-0141", total=AUGUST_BILL, issued_on=AUGUST
        )
        for channel in (notifications_models.CHANNEL_PRINT, notifications_models.CHANNEL_EMAIL):
            a_message(
                pine_hill,
                account,
                source_type="invoice",
                source_id=bill.pk,
                channel=channel,
                on=AUGUST,
                template_code="bill_residential",
            )
    rows = read(pine_hill, [account.pk])
    assert len(rows) == 1, "two channels of one bill are ONE document"
    assert {route["channel"] for route in rows[0]["routes"]} == {
        notifications_models.CHANNEL_PRINT,
        notifications_models.CHANNEL_EMAIL,
    }
    assert rows[0]["kind"] == "bill"


@pytest.mark.django_db
def test_us_cwp_036_tc3_a_receipt_sent_by_EMAIL_ONLY_names_one_route(pine_hill, sarah):
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        bill = an_issued_bill(
            pine_hill, account, number="BL-2607-0140", total=JULY_BILL, issued_on=JULY
        )
        a_message(
            pine_hill,
            account,
            source_type="payment",
            source_id=bill.pk,
            channel=notifications_models.CHANNEL_EMAIL,
            on=date(2026, 8, 12),
            template_code="payment_receipt",
            address="maria@example.test",
        )
    rows = read(pine_hill, [account.pk])
    assert [route["channel"] for route in rows[0]["routes"]] == [notifications_models.CHANNEL_EMAIL]


@pytest.mark.django_db
def test_us_cwp_036_tc1_the_list_is_NEWEST_FIRST(pine_hill, sarah):
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        august = an_issued_bill(
            pine_hill, account, number="BL-2608-0141", total=AUGUST_BILL, issued_on=AUGUST
        )
        july = an_issued_bill(
            pine_hill, account, number="BL-2607-0140", total=JULY_BILL, issued_on=JULY
        )
        a_message(
            pine_hill,
            account,
            source_type="invoice",
            source_id=july.pk,
            channel=notifications_models.CHANNEL_PRINT,
            on=JULY,
            template_code="bill_residential",
        )
        a_message(
            pine_hill,
            account,
            source_type="invoice",
            source_id=august.pk,
            channel=notifications_models.CHANNEL_PRINT,
            on=AUGUST,
            template_code="bill_residential",
        )
    rows = read(pine_hill, [account.pk])
    assert [row["queued_on"] for row in rows] == ["2026-08-30", "2026-07-30"]


@pytest.mark.django_db
def test_us_cwp_036_tc4_a_new_account_gets_an_EMPTY_LIST_and_not_a_null(pine_hill, sarah):
    """⚠ **`[]` AND `None` ARE DIFFERENT ANSWERS.** The queue was ASKED and this
    account has nothing — which for a new customer is the truth, and is the
    commonest first impression the portal makes."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    assert read(pine_hill, [account.pk]) == []


@pytest.mark.django_db
def test_us_cwp_036_tc5_an_INTERNAL_letter_addressed_to_no_account_is_ABSENT(pine_hill, sarah):
    """⚠ **EXCLUDED BY THE SHAPE OF THE QUERY, NOT BY A LIST OF KINDS.**
    `account_id` is nullable for the staff-addressed rows and `account_id__in`
    cannot match NULL, so a document the customer may not see cannot reach this
    read even if somebody later adds a kind and forgets to filter it."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        bill = an_issued_bill(
            pine_hill, account, number="BL-2608-0141", total=AUGUST_BILL, issued_on=AUGUST
        )
        a_message(
            pine_hill,
            account,
            source_type="invoice",
            source_id=bill.pk,
            channel=notifications_models.CHANNEL_PRINT,
            on=AUGUST,
            template_code="bill_residential",
        )
        internal = notifications_models.OutboundMessage.objects.create(
            tenant=pine_hill,
            account=None,  # a scheduled report, addressed to staff
            source_type="report",
            source_id=bill.pk,
            channel=notifications_models.CHANNEL_EMAIL,
            status=notifications_models.STATUS_QUEUED,
            recipient_address="clerk@pinehill.test",
        )
    rows = read(pine_hill, [account.pk])
    assert len(rows) == 1
    assert all(row["source_type"] != "report" for row in rows)
    assert internal.account_id is None


@pytest.mark.django_db
def test_us_cwp_036_tc6_TENANT_ISOLATION_an_oak_ridge_session_sees_no_pine_hill_document(
    pine_hill, sarah, oak_ridge, elena
):
    """`BR-CWP-010` — **BOTH halves are in the query**, and this proves the
    tenant half from the dangerous side.

    The account-set half is trivially the caller's argument; the half that has
    to hold under a forged id is the TENANT, so the test hands an Oak Ridge
    session Pine Hill's own account id — the exact shape `US-NOT-013` TC-5
    calls *"forged row ids from another tenant"* — and asserts it answers
    NOTHING rather than the other utility's post. The same read under Pine
    Hill's own context still answers, so the empty list is isolation and not a
    broken query.
    """
    switch_on(pine_hill, sarah)
    switch_on(oak_ridge, elena)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        bill = an_issued_bill(
            pine_hill, account, number="BL-2608-0141", total=AUGUST_BILL, issued_on=AUGUST
        )
        a_message(
            pine_hill,
            account,
            source_type="invoice",
            source_id=bill.pk,
            channel=notifications_models.CHANNEL_PRINT,
            on=AUGUST,
            template_code="bill_residential",
        )
    assert read(oak_ridge, [account.pk]) == [], "an Oak Ridge session read Pine Hill's post"
    assert len(read(pine_hill, [account.pk])) == 1, "the read itself still works"


@pytest.mark.django_db
def test_us_cwp_036_a_queued_row_reads_QUEUED_and_NEVER_delivered(pine_hill, sarah):
    """⚠ **THE ONE THAT DECIDES WHETHER THIS SCREEN IS HONEST.**

    Nothing on this deployment can write `delivered` or `bounced`
    (`delivery_ops.UNPOPULATED_STATUSES`), and no dispatcher runs on print or
    email. So a bill that was queued a month ago is still *queued* — it has not
    failed and it has not arrived — and the read says exactly that, with
    `delivery_reported: False` and its reason carried as data rather than as a
    convention a screen might forget.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        bill = an_issued_bill(
            pine_hill, account, number="BL-2608-0141", total=AUGUST_BILL, issued_on=AUGUST
        )
        a_message(
            pine_hill,
            account,
            source_type="invoice",
            source_id=bill.pk,
            channel=notifications_models.CHANNEL_PRINT,
            on=AUGUST,
            template_code="bill_residential",
        )
    row = read(pine_hill, [account.pk])[0]
    assert row["state"] == correspondence_reads.STATE_QUEUED
    assert row["state"] != "delivered"
    assert row["sent_on"] is None
    assert row["delivery_reported"] is False
    assert "never that it arrived" in row["delivery_not_reported_reason"]
    assert "delivered" not in correspondence_reads.DOCUMENT_STATES
    assert "bounced" not in correspondence_reads.DOCUMENT_STATES


@pytest.mark.django_db
def test_us_cwp_036_a_row_with_NO_ADDRESS_reads_COULD_NOT_SEND_with_its_reason(pine_hill, sarah):
    """`BR-BIL-036` — *"an account with NO email address is normal"*. The row
    EXISTS, carries the reason, and is not quietly dropped from the history."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        bill = an_issued_bill(
            pine_hill, account, number="BL-2608-0141", total=AUGUST_BILL, issued_on=AUGUST
        )
        a_message(
            pine_hill,
            account,
            source_type="invoice",
            source_id=bill.pk,
            channel=notifications_models.CHANNEL_EMAIL,
            on=AUGUST,
            template_code="bill_residential",
            address=None,
            unavailable_reason=notifications_models.REASON_NO_EMAIL,
        )
    row = read(pine_hill, [account.pk])[0]
    assert row["state"] == correspondence_reads.STATE_COULD_NOT_SEND
    assert row["routes"][0]["reason"] == notifications_models.REASON_NO_EMAIL


@pytest.mark.django_db
def test_us_cwp_036_a_held_paper_row_reads_HELD_with_its_reason(pine_hill, sarah):
    """`BR-PAY-018` — written, marked held, never dispatched, **never lost**.
    `held` is a FLAG rather than a status, and the customer is told the more
    useful of the two facts: the one with a reason and a fix."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        bill = an_issued_bill(
            pine_hill, account, number="BL-2608-0141", total=AUGUST_BILL, issued_on=AUGUST
        )
        a_message(
            pine_hill,
            account,
            source_type="invoice",
            source_id=bill.pk,
            channel=notifications_models.CHANNEL_PRINT,
            on=AUGUST,
            template_code="bill_residential",
            held=True,
            held_reason="bad_address_paper_suppression",
        )
    row = read(pine_hill, [account.pk])[0]
    assert row["state"] == correspondence_reads.STATE_HELD
    assert row["routes"][0]["reason"] == "bad_address_paper_suppression"


@pytest.mark.django_db
def test_us_cwp_036_a_document_with_no_frozen_copy_says_so_rather_than_offering_one(
    pine_hill, sarah
):
    """`BR-CWP-045` — a document is SERVED, never re-rendered. Where none was
    kept the row carries the store's own reason so the control renders VISIBLY
    HELD with it (`BR-CWP-056`) instead of disappearing."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        bill = an_issued_bill(
            pine_hill, account, number="BL-2608-0141", total=AUGUST_BILL, issued_on=AUGUST
        )
        a_message(
            pine_hill,
            account,
            source_type="invoice",
            source_id=bill.pk,
            channel=notifications_models.CHANNEL_PRINT,
            on=AUGUST,
            template_code="bill_residential",
        )
    row = read(pine_hill, [account.pk])[0]
    assert row["stored_document"]["available"] is False
    assert row["stored_document"]["reason"] is not None


@pytest.mark.django_db
def test_us_cwp_036_an_unruled_template_class_has_NO_KIND_rather_than_the_nearest_one(
    pine_hill, sarah
):
    """⚠ `OQ-1164` decides which classes are legal documents. A class the map
    does not name gets `kind: None` and the screen says *a letter from us* —
    calling it a bill would be a screen deciding an open question."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        bill = an_issued_bill(
            pine_hill, account, number="BL-2608-0141", total=AUGUST_BILL, issued_on=AUGUST
        )
        a_message(
            pine_hill,
            account,
            source_type="notice",
            source_id=bill.pk,
            channel=notifications_models.CHANNEL_PRINT,
            on=AUGUST,
            template_code="a_class_nobody_has_ruled_on",
        )
    row = read(pine_hill, [account.pk])[0]
    assert row["kind"] is None
    assert correspondence_reads.document_kind("bill_residential") == "bill"


@pytest.mark.django_db
def test_us_cwp_036_the_portal_body_carries_NO_DATABASE_ID_and_names_the_bill(pine_hill, sarah):
    """B14 rule 31 — and `DEF-3158`, which is a TRUNCATED uuid being the same
    breach as a whole one. The published read carries `source_id` because a
    caller must resolve the human number; the portal's own body carries the
    NUMBER and nothing that is or contains an id."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        bill = an_issued_bill(
            pine_hill, account, number="BL-2608-0141", total=AUGUST_BILL, issued_on=AUGUST
        )
        a_message(
            pine_hill,
            account,
            source_type="invoice",
            source_id=bill.pk,
            channel=notifications_models.CHANNEL_PRINT,
            on=AUGUST,
            template_code="bill_residential",
        )


    with tenant_context(pine_hill.id):
        body = portal_selectors.documents(account)
    text = repr(body)
    assert body["documents"] is not None
    assert body["documents"][0]["reference"] == "BL-2608-0141"
    assert str(bill.pk) not in text
    assert str(bill.pk)[:8] not in text
    assert str(account.pk) not in text
    assert body["documents"][0]["group"] == "bill"


# ═══════════════════════════════════════════════════════════════════════════
# `DEF-CWP-3969` — a row is named after the DOCUMENT, not after its class
#
# ⚠ **AND THE FIRST TEST BELOW IS THE ONE THAT MATTERS ON THE LIVE
# DEPLOYMENT.** All 100 invoice queue rows there carry an EMPTY
# `template_code`, so `document_kind` correctly answers `None` and every bill
# was being filed under *letters*. The screen listed a customer's bills and
# the *Bills* filter matched none of them.
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_def_cwp_3969_a_bill_whose_queue_row_pinned_no_template_is_still_a_BILL(
    pine_hill, sarah
):
    """The group falls back to the SOURCE, and the kind stays honestly `None`.

    ⚠ **THE TWO HALVES ARE DELIBERATELY DIFFERENT.** `document_kind` refuses to
    derive a KIND from `source_type` and says why — three notices share
    `source_type = 'notice'`. That reasoning is untouched: `kind` is still
    `None` here and the screen still declines to name a class `OQ-1164` has not
    ruled on. What is derived is only WHICH OF THREE PILES the row goes in, and
    a document produced from an invoice is in the bill pile."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        bill = an_issued_bill(
            pine_hill, account, number="BL-2608-0141", total=AUGUST_BILL, issued_on=AUGUST
        )
        a_message(
            pine_hill,
            account,
            source_type="invoice",
            source_id=bill.pk,
            channel=notifications_models.CHANNEL_PRINT,
            on=AUGUST,
            template_code="",  # exactly what the live deployment writes
        )
    row = portal_read(pine_hill, account)[0]
    assert row["kind"] is None, "the class was not pinned and is not guessed"
    assert row["group"] == "bill", "a document made from an invoice is a bill"
    # …and it carries WHICH MONTH, which is what names it on screen.
    assert row["period_start"] == bill.period_start.isoformat()
    assert row["period_end"] == bill.period_end.isoformat()


@pytest.mark.django_db
def test_def_cwp_3969_a_known_kind_still_decides_the_pile_before_the_source_does(
    pine_hill, sarah
):
    """A dunning letter about a bill is `source_type = 'invoice'` and is a
    LETTER ABOUT a bill, not a bill. The order — kind first, source second — is
    the whole safety of the fallback."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        bill = an_issued_bill(
            pine_hill, account, number="BL-2608-0141", total=AUGUST_BILL, issued_on=AUGUST
        )
        a_message(
            pine_hill,
            account,
            source_type="invoice",
            source_id=bill.pk,
            channel=notifications_models.CHANNEL_PRINT,
            on=AUGUST,
            #: A dunning letter is a LETTER that is about a bill, and its
            #: class IS ruled on — which is what makes it the case that proves
            #: the ordering. (`email_corrected_bill` would have been the more
            #: obvious example and is deliberately UNRULED in
            #: `DOCUMENT_KIND_BY_TEMPLATE_CLASS`, so it would have proved the
            #: fallback rather than the precedence.)
            template_code="dunning",
        )
    row = portal_read(pine_hill, account)[0]
    assert row["kind"] == "dunning_letter"
    assert row["group"] == "letter", "a letter about a bill is not a bill"


@pytest.mark.django_db
def test_def_cwp_3969_a_receipt_carries_WHAT_IT_WAS_FOR(pine_hill, sarah):
    """`Receipt for $38.44` — the only thing that distinguishes one receipt
    from another once they all stop being called *Receipt*.

    The figure is the STORED 4dp one; rounding to money's two places happens at
    display, where hard rule 2 puts it."""
    from tests.test_us_cwp_024_balance import allocate

    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        bill = an_issued_bill(
            pine_hill, account, number="BL-2608-0141", total=AUGUST_BILL, issued_on=AUGUST
        )
        payment = allocate(pine_hill, account, bill, "38.4400")
        a_message(
            pine_hill,
            account,
            source_type="payment",
            source_id=payment.pk,
            channel=notifications_models.CHANNEL_EMAIL,
            on=AUGUST,
            template_code="",  # the live rows for receipts carry a code; this
                               # asserts the fallback works without one too
        )
    row = portal_read(pine_hill, account)[0]
    assert row["group"] == "receipt"
    assert row["amount"] == "38.4400"
    assert row["currency"] == "USD"


@pytest.mark.django_db
def test_def_cwp_3969_a_letter_carries_no_naming_facts_rather_than_empty_ones(
    pine_hill, sarah
):
    """All four are `None` on a letter, so the screen falls back to the kind
    word instead of composing a name around a blank."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        bill = an_issued_bill(
            pine_hill, account, number="BL-2608-0141", total=AUGUST_BILL, issued_on=AUGUST
        )
        a_message(
            pine_hill,
            account,
            source_type="notice",
            source_id=bill.pk,
            channel=notifications_models.CHANNEL_PRINT,
            on=AUGUST,
            template_code="dunning",
        )
    row = portal_read(pine_hill, account)[0]
    assert row["group"] == "letter"
    assert (row["period_start"], row["period_end"], row["amount"], row["currency"]) == (
        None, None, None, None,
    )


@pytest.mark.django_db
def test_def_cwp_4411_a_ONE_TIME_SIGN_IN_CODE_is_NOT_a_document(pine_hill, sarah):
    """⚠ **THE PRODUCT OWNER'S ROW: *A letter from us · Letter · How: Text
    message*.**

    A portal enrolment code is queued with the customer's `account_id` — a
    resend has to find the person — so it was listed on *Documents and
    letters*, with no kind (no template class is catalogued for it) and nothing
    to open (a code freezes no document). `models.SOURCE_TYPES` already said
    what it is: *"a code is not a document, there is no envelope for it, and it
    is worthless within ten minutes"*.

    ⚠ **THE ROW IS STILL WRITTEN, AND THAT HALF IS ASSERTED FIRST.** *A message
    that was never queued leaves no trace* is why the queue writes one even
    when nothing can be delivered, and `US-CWP-017` reads the code back off it.
    This test would pass on a fix that simply stopped queueing, which would be
    a worse defect than the one being closed — so it proves the row exists
    before it proves the list does not show it.

    Driven through `credentials.issue_code` + `queue_code`, the real writers,
    rather than a hand-made row: the fixture never enrolled anybody, which is
    exactly why no test had a credential row in the list.
    """
    from apps.portal import credentials as portal_credentials
    from apps.portal import models as portal_models

    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        bill = an_issued_bill(
            pine_hill, account, number="BL-2608-0141", total=AUGUST_BILL, issued_on=AUGUST
        )
        a_message(
            pine_hill,
            account,
            source_type="invoice",
            source_id=bill.pk,
            channel=notifications_models.CHANNEL_PRINT,
            on=AUGUST,
            template_code="bill_residential",
        )
        issued = portal_credentials.issue_code(
            pine_hill.id,
            purpose=portal_models.PURPOSE_ENROL,
            account=account,
            channel=portal_models.CHANNEL_SMS,
            masked="••• ••• 1000",
        )
        portal_credentials.queue_code(
            pine_hill.id, account=account, issued=issued, destination="+1 (402) 555-1000"
        )

        # 1 · the code IS on the queue, on SMS, addressed to this account.
        queued = notifications_models.OutboundMessage.objects.filter(
            tenant=pine_hill, source_type="portal", account=account
        )
        assert queued.count() == 1, "the code must still be queued — US-CWP-017 reads it back"
        assert queued.first().channel == notifications_models.CHANNEL_SMS

    # 2 · …and it is not a document, on either read.
    rows = read(pine_hill, [account.pk])
    assert [row["source_type"] for row in rows] == ["invoice"]

    listed = portal_read(pine_hill, account)
    assert [row["group"] for row in listed] == ["bill"], (
        "a sign-in code was listed as a letter — DEF-CWP-4411"
    )
    assert all(row["kind"] is not None or row["group"] == "bill" for row in listed)
