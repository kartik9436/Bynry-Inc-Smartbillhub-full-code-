# ── Trace ──────────────────────────────────────────────
# Change:  CR-052 W4 tasks 14 and 15 — "Build the paperless and SMS preference
#          columns and publish the election read" · "Queue email and SMS rows
#          for accounts that elected them; print stays the floor and is
#          unconditional".
# Rules:   BR-BIL-036 (CONFIRMED, PO 2026-08-10 closing OQ-091 — PRINT is the
#          primary channel and the FLOOR; email and SMS are notifications of the
#          amount, never a replacement for the document) · BR-CUS-028 (the
#          preference capture set) · BR-BIL-016 (one delivery record per bill
#          per channel) · CLAUDE.md rule 6 (idempotency — queueing twice for one
#          bill is a customer receiving two texts) · hard-won law 3 (defaults
#          fail closed)
# ───────────────────────────────────────────────────────
"""The election a customer can now make, and the floor it cannot lower.

`apps/billing/delivery_seam.py` has asked customers for this election BY NAME
since W3 — `ELECTION_READ = "delivery_channel_election_for_account"` — and
nothing answered, so every bill this product ever issued queued one print row
and reported `delivery_election_unreadable`. That is hard-won law 2 at its
longest running: an engine that wrote and a read that did not exist.

**THE COUNT IS THE CLAIM.** An account that elected nothing queues **1** row.
Paperless on queues **2**. Both on queues **3**. Nothing ever queues **0**, and
the `pdf_print` row is present and identical in all three — a paperless customer
still receives the document, which is BR-BIL-036 in one sentence.
"""

import pytest

from apps.billing import delivery_seam, issue
from apps.customers import selectors as customer_selectors
from apps.customers import services as customer_services
from apps.notifications import models as outbound

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_bil_005_issue import (
    ISSUED_AT,
    TEMPLATE_ID,
    TEMPLATE_VERSION,
    a_priced_draft,
    an_authorised_run,
    electric_gl_accounts,
)
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db


def issue_one(brazos, dana, *, paperless=False, sms=False, account_no="A-1042", invoice_no):
    """One bill for an account with a stated election. Returns (billed, account)."""
    electric_gl_accounts()
    account = an_account(dana, brazos, account_no=account_no)
    if paperless or sms:
        account.paperless = paperless
        account.sms_reminders = sms
        account.save(update_fields=["paperless", "sms_reminders", "updated_at"])
    run = an_authorised_run(brazos, dana)
    draft = a_priced_draft(brazos, account, run, invoice_no=invoice_no)
    billed = issue.issue_invoice(
        draft,
        issued_at=ISSUED_AT,
        template_id=TEMPLATE_ID,
        template_version=TEMPLATE_VERSION,
    )
    return billed, account


def channels_for(invoice_pk):
    return sorted(
        outbound.OutboundMessage.objects.filter(source_id=invoice_pk).values_list(
            "channel", flat=True
        )
    )


# ── TASK 14 · the read ───────────────────────────────────────────────────────


def test_tc1__an_account_that_elected_nothing_answers_an_empty_tuple_not_none(brazos, dana):
    """`()` and `None` are different answers and the seam is built around the
    difference. Before migration 0034 every account answered `None`; now the
    honest answer is "elected nothing", which is a fact about the CUSTOMER."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-2001")
        assert customer_selectors.delivery_channel_election_for_account(account.pk) == ()
        assert delivery_seam.elected_channels(account.pk) == ((), None)


def test_tc2__paperless_elects_email_and_sms_reminders_elects_sms(brazos, dana):
    """Ordered `email` then `sms`, so two callers comparing tuples compare sets
    and the queue writes rows in a stable order across runs."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-2002")
        account.paperless = True
        account.save(update_fields=["paperless", "updated_at"])
        assert customer_selectors.delivery_channel_election_for_account(account.pk) == ("email",)
        account.sms_reminders = True
        account.save(update_fields=["sms_reminders", "updated_at"])
        assert customer_selectors.delivery_channel_election_for_account(account.pk) == (
            "email",
            "sms",
        )


def test_tc3__print_is_never_in_the_election(brazos, dana):
    """The election ADDS channels; it can never name the floor. If `pdf_print`
    could appear here, a future reader could imagine it could also be removed."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-2003")
        account.paperless = True
        account.sms_reminders = True
        account.save(update_fields=["paperless", "sms_reminders", "updated_at"])
        elected = customer_selectors.delivery_channel_election_for_account(account.pk)
        assert outbound.CHANNEL_PRINT not in elected


def test_tc4__an_account_that_is_not_this_tenants_answers_none(brazos, dana):
    """A fact about the PLATFORM: nobody could ask. The seam then keeps the
    print floor and reports the gap rather than deciding this customer wants
    paper."""
    with tenant_ctx(brazos):
        assert (
            customer_selectors.delivery_channel_election_for_account(
                "00000000-0000-0000-0000-000000000000"
            )
            is None
        )


def test_tc5__the_columns_default_to_not_elected_which_is_the_fail_closed_direction(brazos, dana):
    """Hard-won law 3 — the unsafe option must be the one you type. A NULLable
    column would have made the election unreadable on every existing row and the
    seam would have gone on reporting the same absence with a column behind it."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-2004")
        assert account.paperless is False
        assert account.sms_reminders is False


def test_tc6__the_account_detail_serves_both_so_a_screen_can_show_what_it_collected(brazos, dana):
    """A preference captured and never read back is a control that lies."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-2005")
        detail = customer_selectors.account_detail_dict(account)
        assert detail["paperless"] is False
        assert detail["sms_reminders"] is False
        assert detail["template_override_id"] is None


def test_tc7__the_account_edit_can_set_them_so_the_columns_have_a_writer(brazos, dana):
    """A column with no writer is a promise (`apps/customers/models.py` says so
    in its own words). Both left `REFUSED_FIELDS` in the same commit that built
    them."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-2006")
        updated = customer_services.update_account(
            dana, account.pk, {"paperless": True, "sms_reminders": True}
        )
        assert updated["paperless"] is True
        assert updated["sms_reminders"] is True
        assert customer_selectors.delivery_channel_election_for_account(account.pk) == (
            "email",
            "sms",
        )


# ── TASK 15 · what the run queues ────────────────────────────────────────────


def test_tc8__an_account_that_elected_nothing_queues_exactly_the_print_row(brazos, dana):
    """ONE row. The floor, and nothing else."""
    with tenant_ctx(brazos):
        billed, _ = issue_one(brazos, dana, invoice_no="BL-2607-000201")
        assert channels_for(billed.pk) == ["pdf_print"]


def test_tc9__paperless_queues_print_AND_email_and_the_print_row_is_still_there(brazos, dana):
    """TWO rows. **This is the case that has to survive every future
    optimisation**: paperless is a preference about NOTIFICATION and not
    permission to stop sending the document (BR-BIL-036)."""
    with tenant_ctx(brazos):
        billed, _ = issue_one(
            brazos, dana, paperless=True, account_no="A-2010", invoice_no="BL-2607-000202"
        )
        assert channels_for(billed.pk) == ["email", "pdf_print"]
        assert sorted(billed.delivery.channels) == ["email", "pdf_print"]


def test_tc10__both_elections_queue_three_rows(brazos, dana):
    """THREE rows, and print is one of them."""
    with tenant_ctx(brazos):
        billed, _ = issue_one(
            brazos,
            dana,
            paperless=True,
            sms=True,
            account_no="A-2011",
            invoice_no="BL-2607-000203",
        )
        assert channels_for(billed.pk) == ["email", "pdf_print", "sms"]


def test_tc11__the_floor_is_reported_as_added_rather_than_assumed(brazos, dana):
    """The queue owner NAMES the channel it added, so a reader of the result can
    see that print was not something the caller asked for."""
    with tenant_ctx(brazos):
        billed, _ = issue_one(
            brazos, dana, paperless=True, account_no="A-2012", invoice_no="BL-2607-000204"
        )
        codes = {entry["code"] for entry in billed.delivery.problems}
        assert "print_floor_channel_added" in codes
        assert "delivery_election_unreadable" not in codes


def test_tc12__an_elected_sms_row_is_queued_with_its_reason_and_no_address(brazos, dana):
    """`DEF-2700`, AMENDED 2026-10-05 (`DEF-NOT-9668`, lane FIX-7). This read
    *"Consent is now recorded and the NUMBER is not … so the row carries
    `recipient_not_resolvable`"*. The election is offered only with a phone and
    says *"Goes to the phone above."*, so the recipient read now addresses the
    text to that phone. THIS account holds no contact and no phone at all, so
    the row carries `no_mobile_number` — a fact about the customer, still never
    an invented address. `outbound_messages`' own check constraint makes
    *address or reason* structural, so this can never become a silently dropped
    message."""
    with tenant_ctx(brazos):
        billed, _ = issue_one(
            brazos, dana, sms=True, account_no="A-2013", invoice_no="BL-2607-000205"
        )
        row = outbound.OutboundMessage.objects.get(source_id=billed.pk, channel="sms")
        assert row.recipient_address is None
        assert row.unavailable_reason == "no_mobile_number"
        assert {"pdf_print", "sms"} <= set(channels_for(billed.pk))


# ── CLAUDE.md rule 6 — queueing twice is a customer receiving two texts ──────


def test_tc13__queueing_the_same_bill_twice_writes_no_second_row_on_any_channel(brazos, dana):
    """The idempotency key is the DATABASE's — `(tenant, source_type, source_id,
    channel, copy_no)` — which is the only guarantee that survives a retry that
    never called the writer twice at all.

    Asserted per CHANNEL and not only in total, because the failure this guards
    is *a paperless customer gets two emails*, which a total of three rows on a
    two-channel bill would hide."""
    with tenant_ctx(brazos):
        billed, _ = issue_one(
            brazos,
            dana,
            paperless=True,
            sms=True,
            account_no="A-2014",
            invoice_no="BL-2607-000206",
        )
        assert len(billed.delivery.queued) == 3
        again = delivery_seam.queue_bill_delivery(billed, actor=None)
        assert again.queued == ()
        assert len(again.already_queued) == 3
        for channel in ("pdf_print", "email", "sms"):
            assert (
                outbound.OutboundMessage.objects.filter(
                    source_id=billed.pk, channel=channel
                ).count()
                == 1
            )
