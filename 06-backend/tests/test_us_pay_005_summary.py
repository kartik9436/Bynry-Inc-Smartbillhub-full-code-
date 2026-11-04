# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-005 (S32 Payments summary: today, method mix, failed,
#           collections, needs-attention)   Screens: S32
# Rules:    BR-PAY-027 (figures tie to the lists EXACTLY) · BR-PAY-021 (today =
#           POSTED today) · the mix is posted + cleared money by POSTING date
#           (PO ruling 2026-10-21, DEF-PAY-10342) · BR-PAY-015 (no charging and
#           no retry) · BR-PAY-018 (the returned-mail chip)
# ───────────────────────────────────────────────────────
"""S32's panels, each tied to the rows a clerk can open.

US-PAY-005 §4's own fixtures: the PE-10 receipts of 8 Aug — checks **292.87 +
142.30 + 36.22** and cash **105.36 + 16.42**.

RED-PROVED FIRST (hard-won law 7): replacing the collections panel's delegation
to `outstandings.outstandings` with its own `Account.objects.filter(balance__gt
=0).count()` makes TC-4 fail — the tile reports the cached balance while S34
reports the computed one, and the two disagree by whatever the cache has not
caught up on. Transcript in the lane report.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.payments import services, summary

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_001_record_payment import an_issued_bill
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

AS_OF = date(2026, 8, 8)
POSTED_AT = datetime(2026, 8, 8, 10, 30, tzinfo=UTC)

#: US-PAY-005 §4, verbatim: "PE-10 receipts (checks 292.87 + 142.30 + 36.22;
#: cash 105.36 + 16.42)".
CHECKS = (Decimal("292.87"), Decimal("142.30"), Decimal("36.22"))
CASH = (Decimal("105.36"), Decimal("16.42"))
PE10_TOTAL = sum(CHECKS + CASH, Decimal("0"))


def _a_receipt_day(brazos, dana):
    account = an_account(dana, brazos, account_no="A-10432")
    for index, amount in enumerate(CHECKS):
        services.record_payment(
            dana,
            account_id=account.pk,
            amount=amount,
            posted_at=POSTED_AT,
            cleared_at=POSTED_AT,
            method_code="check",
            idempotency_reference=uuid.uuid4(),
        )
    for amount in CASH:
        services.record_payment(
            dana,
            account_id=account.pk,
            amount=amount,
            posted_at=POSTED_AT,
            cleared_at=POSTED_AT,
            method_code="cash",
            idempotency_reference=uuid.uuid4(),
        )
    return account


def test_us_pay_005_tc1__today_ties_to_the_rows(brazos, dana):
    """TC-1 — Σ / count / average over payments POSTED today (BR-PAY-021)."""
    with tenant_ctx(brazos):
        _a_receipt_day(brazos, dana)
        view = summary.summary(as_of=AS_OF)
        assert view.today["count"] == 5
        assert Decimal(view.today["amount"]) == PE10_TOTAL
        assert Decimal(view.today["average"]) == PE10_TOTAL / 5


def test_us_pay_005_tc5__a_day_with_no_money_has_no_average(brazos, dana):
    """TC-5 — the zero state. `average` is **null**, never 0.00.

    A utility that took no money did not take an average payment of nothing; a
    0.00 there is a claim about a division that never happened (A18).
    """
    with tenant_ctx(brazos):
        view = summary.summary(as_of=AS_OF)
        assert view.today["count"] == 0
        assert view.today["average"] is None
        assert view.method_mix == []


def test_us_pay_005_tc2__the_method_mix_sums_to_one_hundred(brazos, dana):
    """TC-2 — per-method shares over POSTED money (posted + cleared, by posting
    date since 2026-10-21, `DEF-PAY-10342`); Σ = 100%."""
    with tenant_ctx(brazos):
        _a_receipt_day(brazos, dana)
        view = summary.summary(as_of=AS_OF)
        shares = [Decimal(row["share"]) for row in view.method_mix]
        assert sum(shares) == Decimal("100.0")
        assert {row["method"] for row in view.method_mix} == {"check", "cash"}


def test_us_pay_005_tc4__the_collections_panel_ties_to_s34(brazos, dana):
    """TC-4 — the tile IS the S34 aggregate, not a second count of it."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-10802")
        an_issued_bill(
            brazos,
            account,
            number="BL-2605-018100",
            total=Decimal("948.20"),
            issued_on=date(2026, 5, 16),
            due_date=date(2026, 5, 16),
        )
        view = summary.summary(as_of=AS_OF)
        assert view.collections["accounts_owing"] == 1
        assert Decimal(view.collections["total_owed"]) == Decimal("948.20")
        assert Decimal(view.collections["write_offs_ytd"]) == Decimal("0")


def test_us_pay_005_tc4b__the_two_chips_count_their_own_queues(brazos, dana):
    """TC-4 — the autopay-scheduled chip and the returned-mail chip."""
    from apps.payments import autopay
    from apps.payments.collections_models import DeliveryReturnEvent

    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11455")
        account.autopay = True
        account.save(update_fields=["autopay"])
        bill = an_issued_bill(
            brazos,
            account,
            number="BL-2608-018410",
            total=Decimal("292.87"),
            issued_on=date(2026, 8, 1),
            due_date=date(2026, 8, 22),
        )
        autopay.record_intent_at_issue(
            actor=dana,
            account_id=account.pk,
            invoice_id=bill.pk,
            amount=Decimal("292.87"),
            due_date=date(2026, 8, 22),
        )
        DeliveryReturnEvent.objects.create(
            tenant=brazos, account=account, returned_on=date(2026, 8, 12)
        )
        view = summary.summary(as_of=AS_OF)
        assert view.chips["autopay_scheduled"] == 1
        assert view.chips["returned_mail"] == 1


def test_us_pay_005_tc6__isolation_summaries_never_cross(brazos, dana, lonestar):
    """TC-6 — *"Its rows only; Brazos Bend totals never leak"*."""
    with tenant_ctx(brazos):
        _a_receipt_day(brazos, dana)
        assert summary.summary(as_of=AS_OF).today["count"] == 5
    with tenant_ctx(lonestar):
        view = summary.summary(as_of=AS_OF)
        assert view.today["count"] == 0
        assert Decimal(view.today["amount"]) == Decimal("0")


def test_def_pay_10342__the_mix_reads_the_posting_date_not_the_reconciliation(brazos, dana):
    """`DEF-PAY-10342` — PO ruling 2026-10-21 (decision log *"Two CR-186
    follow-up rulings"*, item 2): *"a card payment taken 14 Oct and reconciled
    16 Oct"* is money of the day it was taken.

    $40.00 posted 14 Oct is in the October mix on 14 Oct before its batch is
    reconciled (status `posted`, no clearing date) and after (status `cleared`,
    16 Oct). A $25.00 taken the same day and cancelled is never in it. And the
    month edge: $60.00 posted 30 Sep and reconciled 2 Oct is SEPTEMBER's mix,
    not October's.
    """
    from apps.payments import cancel
    from apps.payments import models as payment_models

    def mix(as_of):
        view = summary.summary(as_of=as_of)
        return {row["method"]: Decimal(row["amount"]) for row in view.method_mix}

    def pay(account, amount, when):
        return services.record_payment(
            dana,
            account_id=account.pk,
            amount=amount,
            posted_at=when,
            method_code="cash",
            idempotency_reference=uuid.uuid4(),
        )

    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-10433")
        taken = datetime(2026, 10, 14, 15, 0, tzinfo=UTC)
        card = pay(account, Decimal("40.00"), taken)
        mistake = pay(account, Decimal("25.00"), taken)
        cancel.cancel_payment(
            actor=dana, payment_id=mistake.payment_id, reason="wrong_account", cancelled_on=taken
        )
        late = pay(account, Decimal("60.00"), datetime(2026, 9, 30, 15, 0, tzinfo=UTC))
        assert payment_models.Payment.objects.get(pk=card.payment_id).status == (
            payment_models.PAYMENT_POSTED
        )

        before = mix(date(2026, 10, 14))
        # The batches are reconciled — written directly; the read is under test.
        payment_models.Payment.objects.filter(pk=card.payment_id).update(
            status=payment_models.PAYMENT_CLEARED,
            cleared_at=datetime(2026, 10, 16, 11, 0, tzinfo=UTC),
        )
        payment_models.Payment.objects.filter(pk=late.payment_id).update(
            status=payment_models.PAYMENT_CLEARED,
            cleared_at=datetime(2026, 10, 2, 11, 0, tzinfo=UTC),
        )
        after = mix(date(2026, 10, 14))
        on_16 = mix(date(2026, 10, 16))
        september = mix(date(2026, 9, 30))

    assert before == {"cash": Decimal("40.00")}
    assert after == {"cash": Decimal("40.00")}
    assert on_16 == {"cash": Decimal("40.00")}
    assert september == {"cash": Decimal("60.00")}
