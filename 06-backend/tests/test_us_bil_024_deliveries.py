# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-023 (the outbound delivery seam — one record per bill per
#           channel, queued and never sent) ·
#           US-BIL-024 (the READ half: where a bill went, on S30's delivery
#           panel)   Screens: S30 (bill detail → Delivery)
# Rules:    BR-BIL-016 (delivery is a QUEUE — per channel, per bill) ·
#           BR-BIL-036 (print is the floor and no election can remove it) ·
#           BR-BIL-026 (the queue row carries the bill's own template pin) ·
#           BR-TEN-003 / HR-1 (a cross-tenant id reads as absent) ·
#           CLAUDE.md rule 1 (tenant scoping)
# Tests:    this file
# Impacts:  apps/notifications/selectors.deliveries_for_source (the publish) ·
#           apps/billing/delivery_seam.deliveries_for_bill (the seam) ·
#           apps/billing/selectors._deliveries_for (the API shape) ·
#           07-frontend BillDetailPage's DeliveryPanel, which has rendered its
#           absence branch on every bill in the product until now
# ───────────────────────────────────────────────────────
"""US-BIL-023/024 — an engine that writes and a screen that reads, with no
question between them.

`issue.py` has written a delivery row for every bill it issued since
2026-08-11. `BillDetailPage`'s `DeliveryPanel` has been able to draw those rows
since the detail screen landed. In between, `GET /invoices/{id}` served
`"deliveries": None` from a hardcoded literal with the comment *"what is
missing is this READ"* beside it — so the panel rendered its absence branch on
every bill, and the only thing missing was the question.

**THE ASSERTION THIS FILE EXISTS FOR IS THE ONE ABOUT `None` VERSUS `[]`**, and
it is not pedantry. `[]` means the queue was asked and holds nothing for this
bill — true of a DRAFT, because queueing happens at issue. `None` means the
notifications module publishes no read and nobody can say. Serving `[]` for the
second case would draw an empty delivery table on an ISSUED bill and tell a
clerk it was never sent to anyone. That is the zero-that-means-I-don't-know,
which is the defect class of this release.

**NOTHING HERE ASSERTS A SEND.** Every row rests `queued`: R2 has no dispatcher
(US-NOT-002) and no provider adapter (US-NOT-003), both OUT OF THE RELEASE BY
RULING rather than unfinished. A queued row is the finished state of a bill run
today, and a test that expected `sent` would be asserting a product decision
that was made the other way.
"""

import uuid

import pytest

from apps.billing import delivery_seam, selectors
from apps.notifications import models as notification_models
from apps.notifications import selectors as notification_selectors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_bil_022_documents import an_issued_bill as _an_issued_bill
from tests.test_us_bil_005_issue import a_priced_draft, an_authorised_run
from tests.test_w3_billing_models import a_run, an_account

pytestmark = pytest.mark.django_db


def issued(tenant, dana, *, account=None, run=None, **overrides):
    """One issued bill on a SHARED account and run.

    `an_issued_bill` mints its own account each call and `accounts.account_no`
    is unique per tenant, so two bills in one test collide. The account is the
    caller's here because the cases that need two bills need them on the SAME
    account — the question is whether one bill's delivery rows leak onto
    another's panel, and two accounts would hide a tenant-wide filter bug
    behind an account-wide one.
    """
    account = account or an_account(dana, tenant)
    run = run or an_authorised_run(tenant, dana)
    return _an_issued_bill(tenant, dana, account=account, run=run, **overrides)


def queued_row(tenant, invoice, *, channel="print", copy_no=0, status="queued"):
    """One `outbound_messages` row, written the way `issue.py` writes it.

    Through the ORM rather than through `queue_document`, deliberately: the
    subject here is the READ, and driving the write path would make a read
    failure look like a queueing failure.

    `unavailable_reason` is set and `recipient_address` is not, which is the
    shape a BILL's row really has: billing names no recipient (the address is
    customers' to answer) and `ck_outbound_msgs_address_or_reason` requires one
    of the two. A fixture carrying a made-up address would be testing a row this
    product does not write.
    """
    return notification_models.OutboundMessage.objects.create(
        tenant=tenant,
        source_type="invoice",
        source_id=invoice.pk,
        account=invoice.account,
        channel=channel,
        copy_no=copy_no,
        status=status,
        template_version=invoice.template_version,
        unavailable_reason="recipient_not_resolved_by_billing",
    )


def test_us_bil_024_tc1__an_issued_bill_says_where_it_went(brazos, dana):
    """The panel's four columns, off the row THE REAL ISSUE PATH wrote.

    Nothing is hand-queued here and that is deliberate: `issue.issue_invoice`
    writes the print row itself, inside its own transaction (BR-BIL-016 /
    BR-BIL-036 — print is the floor), so this asserts the whole write→read
    chain rather than a fixture talking to a selector. The channel is the
    queue's own `pdf_print` and is read off the row rather than typed here,
    because the channel vocabulary is notifications' and this test must not
    become a second copy of it.

    RED-PROVED: `invoice_detail` returned a hardcoded `None`, so this failed on
    "an issued bill's delivery history read as unanswerable".
    """
    with tenant_ctx(brazos):
        bill = issued(brazos, dana)
        detail = selectors.invoice_detail(str(bill.pk))

    rows = detail["deliveries"]
    assert rows is not None, "an issued bill's delivery history read as unanswerable"
    assert rows, "the issue path queued a delivery and the bill's panel showed none"
    assert {row["status"] for row in rows} == {"queued"}
    # Every row carries a QUEUED time. `at` is not a sent time and the screen
    # says so — nothing in R2 sends, so a null-fed column would read as a
    # delivery that failed rather than one never attempted.
    assert all(row["at"] is not None for row in rows)
    assert all(row["id"] for row in rows)


def test_us_bil_024_tc1b__a_second_channel_appears_beside_the_print_floor(brazos, dana):
    """An elected channel lists WITH the print row, never instead of it.

    BR-BIL-036: print is the floor and no election can remove it. So a bill on
    two channels shows two rows, and the ordering is the queue's — by channel,
    so a clerk reading two bills reads them the same way twice.
    """
    with tenant_ctx(brazos):
        bill = issued(brazos, dana)
        queued_row(brazos, bill, channel="email")
        detail = selectors.invoice_detail(str(bill.pk))

    channels = [row["channel"] for row in detail["deliveries"]]
    assert "email" in channels
    assert len(channels) >= 2, "the elected channel replaced the print floor"
    assert channels == sorted(channels)


def test_us_bil_024_tc2__a_draft_answers_an_EMPTY_list_not_an_absence(brazos, dana):
    """`[]` is a real answer: a draft has never been queued.

    Queueing happens at issue (BR-BIL-016, inside `issue_invoice`'s
    transaction), so a draft with no rows is the queue answering truthfully
    rather than the queue being unreachable.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        draft = a_priced_draft(brazos, account, a_run(brazos), invoice_no="BL-2607-000901")
        detail = selectors.invoice_detail(str(draft.pk))

    assert detail["deliveries"] == []


def test_us_bil_024_tc3__an_unreachable_queue_answers_None_and_never_an_empty_list(
    brazos, dana, monkeypatch
):
    """The distinction the whole seam exists for.

    A deployment whose notifications module publishes no read cannot say where
    a bill went. Answering `[]` would draw an empty delivery table on an issued
    bill and tell a clerk it was never sent to anyone — a claim about a
    customer's post, made because a module was missing.
    """
    with tenant_ctx(brazos):
        bill = issued(brazos, dana)
        queued_row(brazos, bill)
        monkeypatch.delattr(
            notification_selectors, delivery_seam.DELIVERY_READ, raising=True
        )
        detail = selectors.invoice_detail(str(bill.pk))

    assert detail["deliveries"] is None, (
        "an unreachable queue reported an empty delivery history, which asserts "
        "the bill was never sent"
    )


def test_us_bil_024_tc4__a_reprint_lists_under_its_original(brazos, dana):
    """Order is channel then `copy_no`, so a reprint reads beneath the row it
    copies rather than above it, and two channels list the same way twice."""
    with tenant_ctx(brazos):
        bill = issued(brazos, dana)
        queued_row(brazos, bill, channel="reprint", copy_no=1)
        queued_row(brazos, bill, channel="reprint", copy_no=0)
        detail = selectors.invoice_detail(str(bill.pk))
        reprints = [row for row in detail["deliveries"] if row["channel"] == "reprint"]
        copies = [
            notification_models.OutboundMessage.objects.get(pk=row["id"]).copy_no
            for row in reprints
        ]

    assert copies == [0, 1], "a reprint listed above the row it copies"


def test_us_bil_024_tc5__one_bill_s_rows_never_include_another_s(brazos, dana):
    """Scoped to the SOURCE id, not to the tenant alone.

    A read that filtered on tenant and source_type only would show every bill
    in the utility on every bill's delivery panel — which reads as plausible on
    a one-bill fixture and is catastrophic on a real one.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = an_authorised_run(brazos, dana)
        bill = issued(brazos, dana, account=account, run=run)
        other = issued(
            brazos, dana, account=account, run=run, invoice_no="BL-2607-000902"
        )
        queued_row(brazos, other, channel="email")
        detail = selectors.invoice_detail(str(bill.pk))
        other_detail = selectors.invoice_detail(str(other.pk))

    # Each bill sees ITS OWN rows and none of the other's. A read filtered on
    # tenant and source_type alone would show every bill in the utility on
    # every panel — plausible on a one-bill fixture, catastrophic on a real one.
    mine = {row["id"] for row in detail["deliveries"]}
    theirs = {row["id"] for row in other_detail["deliveries"]}
    assert mine and theirs
    assert mine.isdisjoint(theirs)
    assert "email" not in {row["channel"] for row in detail["deliveries"]}


def test_us_bil_024_tc6__an_unknown_source_id_is_an_empty_list_not_a_crash(brazos):
    """The seam is asked about ids that may not exist (a deleted draft, a stale
    tab). It answers nothing rather than raising — the caller has already
    resolved the invoice through `invoice_or_404`, so HR-1 is settled upstream.
    """
    with tenant_ctx(brazos):
        assert notification_selectors.deliveries_for_source("invoice", uuid.uuid4()) == []
        assert notification_selectors.deliveries_for_source("invoice", None) == []


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-024@5397d5f (04-docs/05-modules/07-billing/06-epics/EP-BIL-06-templates-delivery.md US-BIL-023/024 · 07-billing/02-business-rules.md BR-BIL-016/036 · 04-docs/01-spec/11b-api-audit.md §2.8's `GET /invoices/{id}/deliveries` row · apps/billing/delivery_seam.py, whose own DELIVERY_UNAVAILABLE names the dispatcher gap this read must not paper over)
# generated: 2026-08-16 by story-coder (billing-9 lane — the read half of a queue that had been written to for five days)
# checklist: A✔ B✔ C✔ D✔(served on GET /invoices/{id}) E✔(S30's DeliveryPanel, which had rendered its absence branch on every bill) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — tc1 read `deliveries: None` off the hardcoded literal in `selectors.invoice_detail` and failed on "an issued bill's delivery history read as unanswerable"; tc3 was proved by deleting the published selector. Quoted in the lane report. ruff✔ black✔
# exceptions: (1) NO TEST ASSERTS A `sent` OR `delivered` ROW, and that is a product decision rather than a gap in coverage: R2 has no dispatcher (US-NOT-002) and no provider adapter (US-NOT-003), both OUT OF THE RELEASE BY PO RULING, so a queued row is the finished state of a bill run. (2) Rows are written through the ORM, not through `queue_document`: the subject is the READ, and driving the write path would make a read failure look like a queueing one. (3) `at` is the QUEUED time. `sent_at` is null on every row on every bill for the reason in (1), and a column fed from it would read as a delivery that FAILED rather than one never attempted
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
