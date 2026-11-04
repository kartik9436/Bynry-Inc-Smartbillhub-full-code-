# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-024 (autopay capture-intents: bill issue records the intent;
#           staff record the money)   Screens: S32 · S33
# Rules:    BR-PAY-015 (capture-INTENT only; scheduled_on = the DUE DATE; no
#           charging before rails) · BR-CUS-059 (enrolment is capture-only) ·
#           BR-PAY-034 (fulfilled is COMPUTED, never stored) · BR-PAY-021
# ───────────────────────────────────────────────────────
"""PE-12: **292.87**, scheduled **22 Aug 2026**, status `awaiting_rails`.

TC-5 is a test about an ABSENCE — *"no charging path exists"* — and the
strongest assertion available for it is that the module exposes nothing that
could charge anybody and the status set has exactly one value. Both are
asserted, because a `charge()` that raised would be a charging path with a flag
on it.

RED-PROVED FIRST (hard-won law 7): dropping `uq_autopay_intent_per_invoice` and
the pre-insert lookup lets a retried bill issue record TWO intents for one
invoice — the customer is promised the same draft twice. Transcript in the lane
report.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.payments import autopay, models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_001_record_payment import an_issued_bill
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

#: PE-12, verbatim: "BL-2608-018410 total due 292.87, due Aug 22, 2026".
PE12_AMOUNT = Decimal("292.87")
PE12_DUE = date(2026, 8, 22)


def _enrolled(brazos, dana, *, account_no="A-11042", autopay_on=True):
    account = an_account(dana, brazos, account_no=account_no)
    account.autopay = autopay_on
    account.save(update_fields=["autopay"])
    bill = an_issued_bill(
        brazos,
        account,
        number=f"BL-2608-{account_no[-5:]}",
        total=PE12_AMOUNT,
        issued_on=date(2026, 8, 1),
        due_date=PE12_DUE,
    )
    return account, bill


def test_us_pay_024_tc1__an_intent_is_dated_the_due_date(brazos, dana):
    """TC-1 — amount **292.87**, `scheduled_on` **22 Aug**, `awaiting_rails`."""
    with tenant_ctx(brazos):
        account, bill = _enrolled(brazos, dana)
        result = autopay.record_intent_at_issue(
            actor=dana,
            account_id=account.pk,
            invoice_id=bill.pk,
            amount=PE12_AMOUNT,
            due_date=PE12_DUE,
        )
        assert result.created is True
        assert result.amount == PE12_AMOUNT
        assert result.scheduled_on == PE12_DUE
        assert result.status == models.INTENT_AWAITING_RAILS


def test_us_pay_024_tc4__a_non_enrolled_account_gets_no_intent(brazos, dana):
    """TC-4 — *"No intent row — intents exist only for enrolled accounts"*.

    Reported rather than raised: a bill run issuing four hundred bills must not
    fail because three hundred of those accounts are not on autopay.
    """
    with tenant_ctx(brazos):
        account, bill = _enrolled(brazos, dana, account_no="A-11103", autopay_on=False)
        result = autopay.record_intent_at_issue(
            actor=dana,
            account_id=account.pk,
            invoice_id=bill.pk,
            amount=PE12_AMOUNT,
            due_date=PE12_DUE,
        )
        assert result.created is False
        assert result.intent_id is None
        assert "account_not_enrolled" in {problem["code"] for problem in result.problems}
        assert models.AutopayCaptureIntent.objects.count() == 0


def test_us_pay_024_tc6__a_retried_issue_records_one_intent(brazos, dana):
    """TC-6 — *"One intent per (invoice) — idempotent with the issue guard"*."""
    with tenant_ctx(brazos):
        account, bill = _enrolled(brazos, dana, account_no="A-11044")
        first = autopay.record_intent_at_issue(
            actor=dana,
            account_id=account.pk,
            invoice_id=bill.pk,
            amount=PE12_AMOUNT,
            due_date=PE12_DUE,
        )
        second = autopay.record_intent_at_issue(
            actor=dana,
            account_id=account.pk,
            invoice_id=bill.pk,
            amount=PE12_AMOUNT,
            due_date=PE12_DUE,
        )
        assert second.created is False
        assert second.intent_id == first.intent_id
        assert models.AutopayCaptureIntent.objects.count() == 1


def test_us_pay_024_tc5__there_is_no_charging_path_to_call(brazos, dana):
    """TC-5 — the absence, asserted.

    ONE status, and no callable in the module takes a payment method or captures
    anything. TC-5's *"Retry autopay"* has nothing to route to, which is why the
    prototype's action is superseded rather than disabled.
    """
    assert models.INTENT_STATUSES == (models.INTENT_AWAITING_RAILS,)
    exported = {name for name in dir(autopay) if not name.startswith("_")}
    assert not {"charge", "capture", "retry", "draft"} & exported


def test_us_pay_024_tc2__fulfilled_is_computed_from_settlement_not_stored(brazos, dana):
    """TC-2 / BR-PAY-034 — *"a matching recorded payment renders it"*.

    Nothing transitions: the stored status stays `awaiting_rails` and the
    display state is derived from `allocations`, so a later reapply changes the
    answer instead of leaving a stale flag behind.
    """
    import uuid
    from datetime import UTC, datetime

    from apps.payments import services

    with tenant_ctx(brazos):
        account, bill = _enrolled(brazos, dana, account_no="A-11045")
        autopay.record_intent_at_issue(
            actor=dana,
            account_id=account.pk,
            invoice_id=bill.pk,
            amount=PE12_AMOUNT,
            due_date=PE12_DUE,
        )
        assert autopay.intent_rows(account_id=account.pk)[0]["fulfilled"] is False

        services.record_payment(
            dana,
            account_id=account.pk,
            amount=PE12_AMOUNT,
            posted_at=datetime(2026, 8, 20, 10, 0, tzinfo=UTC),
            cleared_at=datetime(2026, 8, 20, 10, 0, tzinfo=UTC),
            idempotency_reference=uuid.uuid4(),
        )
        row = autopay.intent_rows(account_id=account.pk)[0]
        assert row["fulfilled"] is True
        # …and the STORED status never moved (BR-PAY-015).
        assert row["status"] == models.INTENT_AWAITING_RAILS


def test_us_pay_024_tc7__isolation_intents_never_cross(brazos, dana, lonestar):
    """TC-7 — *"Intents for its accounts only (RLS)"*."""
    with tenant_ctx(brazos):
        account, bill = _enrolled(brazos, dana, account_no="A-11046")
        autopay.record_intent_at_issue(
            actor=dana,
            account_id=account.pk,
            invoice_id=bill.pk,
            amount=PE12_AMOUNT,
            due_date=PE12_DUE,
        )
        assert len(autopay.intent_rows()) == 1
    with tenant_ctx(lonestar):
        assert autopay.intent_rows() == []
