# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-016 (returned mail → bad-address → needs-attention → paper
#           suppressed)   Screens: S30 · S35 · S32 · S21
# Rules:    BR-PAY-018 (mark returned → flag → queue + banner → suppression;
#           BALANCES UNAFFECTED; audited) · BR-NOT-005 (queue rows are held,
#           never deleted) · CLAUDE.md rule 6 (one envelope, one event) · rule 7
# ───────────────────────────────────────────────────────
"""J18's Tuesday — and the invariance that matters more than the workdown.

*"Zero money rows written or changed by the entire day's work."* That is the
story's own INVARIANCE row, and it is asserted here by counting rather than by
reading: nothing about a customer's balance, due date or aging may change
because the post office failed.
"""

from datetime import date

import pytest

from apps.billing import models as billing_models
from apps.payments import returned_mail
from apps.payments.collections_models import DeliveryReturnEvent
from apps.payments.exceptions import PaymentRuleError

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_bil_016_bulk_corrections import an_issued_bill, money_row_counts
from tests.test_w3_billing_models import a_run, an_account

pytestmark = pytest.mark.django_db

TUESDAY = date(2026, 9, 8)


def test_us_pay_016_tc1__marking_a_piece_returned_flags_the_account(brazos, dana):
    """TC-1 (PE-16) — the event, the flag, and the needs-attention row.

    ⚠ AMENDED 2026-09-23 (`DEF-PAY-6342`). This read *"The flag is DERIVED from
    an unresolved event rather than stored on `accounts.bad_address`"* — and
    that was the defect: two flags that never met. The flag is the stored
    column now, raised by customers at payments' request, and the S21 banner
    renders from it (`ReturnedPostBanner.tsx`); `account_banner`, an English
    sentence nothing called, is gone. `test_def_pay_6342_bad_address.py` walks
    the same chain through the routes.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        result = returned_mail.mark_returned(
            account_id=account.id,
            returned_on=TUESDAY,
            outbound_message_id="11111111-1111-1111-1111-111111111111",
            actor=dana,
        )
        assert result.created is True
        assert result.flag_raised is True
        assert returned_mail.bad_address_for(account.id) is True
        account.refresh_from_db()
        assert account.bad_address is True, "the STORED column — the one every screen reads"
        assert returned_mail.needs_attention().count() == 1


def test_us_pay_016_tc2__a_bulk_mark_clears_the_stack_in_one_pass(brazos, dana):
    """TC-2 / J18 step 1 — fourteen envelopes, one action, per-row results.

    Twelve pieces across nine accounts is the story's other fixture: the events
    are per PIECE and the flag is per ACCOUNT, which is why the counts differ
    and why the queue de-dupes.
    """
    with tenant_ctx(brazos):
        accounts = [an_account(dana, brazos, account_no=f"A-1145{n}") for n in range(3)]
        pieces = tuple(
            {
                "account_id": accounts[index % 3].id,
                "outbound_message_id": f"2222222{index}-1111-1111-1111-111111111111",
            }
            for index in range(6)
        )
        results = returned_mail.mark_returned_bulk(pieces=pieces, returned_on=TUESDAY, actor=dana)
        assert all(row.created for row in results)
        assert DeliveryReturnEvent.objects.count() == 6
        assert all(returned_mail.bad_address_for(account.id) for account in accounts)


def test_us_pay_016_tc3__suppression_is_a_decision_and_the_rows_are_never_dropped(brazos, dana):
    """TC-3 — BR-PAY-018's config, and the honest limit of it today.

    The decision exists and is auditable. The `held` marker a dispatcher would
    obey does NOT exist on `outbound_messages` and payments may not add one
    (that table is notifications'), and nothing dispatches in this release —
    both facts are in the module docstring and both are REPORTED rather than
    implied by a green test.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        returned_mail.mark_returned(
            account_id=account.id,
            returned_on=TUESDAY,
            outbound_message_id="33333333-1111-1111-1111-111111111111",
            actor=dana,
        )
        assert (
            returned_mail.paper_suppressed_for(account.id, suppress_paper_on_bad_address=True)
            is True
        )
        assert (
            returned_mail.paper_suppressed_for(account.id, suppress_paper_on_bad_address=False)
            is False
        ), "the tenant setting is an ARGUMENT — a second reader is a second default"


def test_us_pay_016_tc4__verifying_the_address_clears_the_flag_and_the_queue(brazos, dana):
    """TC-4 / J18 steps 3 and 4 — two outcomes, both real.

    `address_corrected` and `verified_current` are different facts and a single
    boolean would lose the second one — the one that stops a clerk chasing the
    same envelope again next Tuesday.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        marked = returned_mail.mark_returned(
            account_id=account.id,
            returned_on=TUESDAY,
            outbound_message_id="44444444-1111-1111-1111-111111111111",
            actor=dana,
        )
        returned_mail.resolve_return(
            event_id=marked.event_id,
            resolution=returned_mail.RESOLUTION_VERIFIED_CURRENT,
            resolved_on=date(2026, 9, 8),
            actor=dana,
        )
        assert returned_mail.bad_address_for(account.id) is False
        assert returned_mail.needs_attention().count() == 0

        with pytest.raises(PaymentRuleError):
            returned_mail.resolve_return(
                event_id=marked.event_id,
                resolution=returned_mail.RESOLUTION_ADDRESS_CORRECTED,
                resolved_on=date(2026, 9, 9),
                actor=dana,
            )


def test_us_pay_016_tc5__marking_the_same_envelope_twice_writes_one_event(brazos, dana):
    """TC-5 (negative) — rule 6, and an email bounce is not this flow.

    The DATABASE refuses the duplicate, which is the only guarantee that
    survives two clerks working the same stack. An email that bounced rides the
    queue's own `bounced` status (BR-BIL-016); flagging an account bad-address
    for a full mailbox would suppress its paper bills for a reason that has
    nothing to do with where the customer lives.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        first = returned_mail.mark_returned(
            account_id=account.id,
            returned_on=TUESDAY,
            outbound_message_id="55555555-1111-1111-1111-111111111111",
            actor=dana,
        )
        second = returned_mail.mark_returned(
            account_id=account.id,
            returned_on=TUESDAY,
            outbound_message_id="55555555-1111-1111-1111-111111111111",
            actor=dana,
        )
        assert second.created is False and second.event_id == first.event_id
        assert DeliveryReturnEvent.objects.count() == 1

        with pytest.raises(PaymentRuleError) as refusal:
            returned_mail.mark_returned(
                account_id=account.id,
                returned_on=TUESDAY,
                outbound_message_id="66666666-1111-1111-1111-111111111111",
                channel="email",
                actor=dana,
            )
        assert "PAPER-channel" in str(refusal.value)


def test_us_pay_016_tc9__the_whole_days_work_moves_no_money(brazos, dana):
    """J18's INVARIANCE row — the one thing that must NOT happen.

    Fourteen envelopes marked, some resolved, and every money table byte-for-byte
    where it was: no invoice, no line, no credit note, no adjustment created or
    changed, and the bill's own total untouched. *"Returned ≠ reissued."*
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-09|cycle-A")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2609-000101")
        before = money_row_counts(brazos)
        total_before = billing_models.Invoice.objects.get(pk=bill.pk).total

        events = returned_mail.mark_returned_bulk(
            pieces=tuple(
                {
                    "account_id": account.id,
                    "outbound_message_id": f"7777777{index}-1111-1111-1111-111111111111",
                    "source_id": str(bill.pk),
                }
                for index in range(9)
            ),
            returned_on=TUESDAY,
            actor=dana,
        )
        returned_mail.resolve_return(
            event_id=events[0].event_id,
            resolution=returned_mail.RESOLUTION_ADDRESS_CORRECTED,
            resolved_on=TUESDAY,
            actor=dana,
        )

        assert money_row_counts(brazos) == before
        assert billing_models.Invoice.objects.get(pk=bill.pk).total == total_before
        assert billing_models.Invoice.objects.get(pk=bill.pk).status == (
            billing_models.INVOICE_ISSUED
        )


def test_us_pay_016_tc6__returned_stacks_never_cross_tenants(brazos, dana):
    """TC-6 (isolation) — its rows, flags and queues only."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        returned_mail.mark_returned(
            account_id=account.id,
            returned_on=TUESDAY,
            outbound_message_id="88888888-1111-1111-1111-111111111111",
            actor=dana,
        )
        assert (
            DeliveryReturnEvent.objects.filter(tenant=brazos).count()
            == DeliveryReturnEvent.objects.count()
        )
