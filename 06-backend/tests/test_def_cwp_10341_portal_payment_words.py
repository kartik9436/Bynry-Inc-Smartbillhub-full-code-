# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CWP-10341 — customer portal payment words did not follow the
#           CR-186 lifecycle (every payment `posted` at entry, `cleared` only on
#           bank reconciliation, `cancelled` only from `posted`)
# Story:    US-CWP-010 TC-7 (guest Track anything) · US-CWP-048 (money list)
#           Screens: CWP-012 · CWP-041
# Rules:    BR-CWP-024 (progress, never the reason) · BR-CWP-061 (a bounce is
#           two rows) · CLAUDE.md hard rule 4 (a cancel is new rows)
# Impacts:  apps/portal/selectors.py PAYMENT_PROGRESS_WORDS ·
#           apps/portal/seams/payments_seam.py _payment_state / _payment_view
# ───────────────────────────────────────────────────────
"""Every payment status reads as its own customer word, and none falls through.

⚠ **THE FAILURE THIS FILE EXISTS FOR WAS A SILENT FALLBACK.** `cancelled` was
added to `payments` with no entry in either portal map, so the guest read
*processing* and the money list read *cleared*; and a cancel's reversing row
read *bounced* / *returned by the bank*. The first test below reads
`PAYMENT_STATUSES` itself, so a seventh status added without a word goes red
here rather than reaching a customer as a borrowed one.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from apps.payments import models as payment_models
from apps.portal import selectors
from apps.portal.seams import payments_seam
from core.tenancy import tenant_context
from tests.test_us_cwp_005_receipt import POSTCODE, _a_recorded_payment, _track
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import elm_street_account, switch_on

OCT_20 = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)
OCT_21 = datetime(2026, 10, 21, 9, 0, tzinfo=UTC)

#: The table the defect asked for, written out so a reader sees it whole.
EXPECTED_GUEST_WORDS = {
    "posted": "received",
    "cleared": "received",
    "processing": "processing",
    "failed": "failed",
    "reversed": "failed",
    "cancelled": "cancelled",
}


def test_every_payment_status_has_an_explicit_guest_word():
    """No real status may reach the fallback."""
    assert set(payment_models.PAYMENT_STATUSES) == set(selectors.PAYMENT_PROGRESS_WORDS)
    for status in payment_models.PAYMENT_STATUSES:
        assert selectors.payment_progress_status(status) == EXPECTED_GUEST_WORDS[status], status


def test_posted_and_cleared_read_the_same_to_a_customer():
    assert selectors.payment_progress_status("posted") == selectors.payment_progress_status("cleared")


def test_an_unknown_status_reads_unknown_and_never_a_real_word():
    for odd in ("something_new", "", None):
        word = selectors.payment_progress_status(odd)
        assert word == selectors.PAYMENT_PROGRESS_UNKNOWN == "unknown"
        assert word not in selectors.PAYMENT_PROGRESS_WORDS.values()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("status", "word"),
    [("posted", "received"), ("cancelled", "cancelled"), ("processing", "processing")],
)
def test_track_anything_reads_the_customer_word(pine_hill, sarah, status, word):
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    _a_recorded_payment(pine_hill, account, status=status, cleared=None)

    body = _track(pine_hill, "PAY-26-08841", POSTCODE).data

    assert body["status"] == word


# ── the signed-in money list (CWP-041) ─────────────────────


def _payment(tenant, account, *, status, number, amount="129.0200", reverses=None, at=OCT_20):
    return payment_models.Payment.objects.create(
        tenant=tenant,
        account=account,
        payment_no=number,
        amount=Decimal(amount),
        currency="USD",
        status=status,
        posted_at=at,
        cleared_at=at if status == payment_models.PAYMENT_CLEARED else None,
        reverses_payment=reverses,
    )


def _read(tenant, account):
    with tenant_context(tenant.id):
        return payments_seam.money_list([account.pk])


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("status", "state"),
    [
        (payment_models.PAYMENT_POSTED, payments_seam.STATE_RECEIVED),
        (payment_models.PAYMENT_CLEARED, payments_seam.STATE_RECEIVED),
        (payment_models.PAYMENT_PROCESSING, payments_seam.STATE_PROCESSING),
        (payment_models.PAYMENT_FAILED, payments_seam.STATE_FAILED),
        (payment_models.PAYMENT_CANCELLED, payments_seam.STATE_CANCELLED),
    ],
)
def test_a_single_payment_reads_its_own_state(pine_hill, sarah, status, state):
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        _payment(pine_hill, account, status=status, number="PMT-26-10001")

    (row,) = _read(pine_hill, account)
    assert row["state"] == state
    assert row["returned_by_the_bank"] is False


@pytest.mark.django_db
def test_a_cancel_is_two_CANCELLED_rows_and_neither_says_the_bank_returned_it(pine_hill, sarah):
    """The shape `payments/cancel.py` writes: the original moved to `cancelled`
    and a negative reversing row, also `cancelled`, pointing at it."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        original = _payment(
            pine_hill, account, status=payment_models.PAYMENT_CANCELLED, number="PMT-26-10001"
        )
        _payment(
            pine_hill,
            account,
            status=payment_models.PAYMENT_CANCELLED,
            number="PMT-26-10002",
            amount="-129.0200",
            reverses=original,
            at=OCT_21,
        )

    rows = _read(pine_hill, account)
    assert [row["state"] for row in rows] == [
        payments_seam.STATE_CANCELLED,
        payments_seam.STATE_CANCELLED,
    ]
    assert [row["returned_by_the_bank"] for row in rows] == [False, False]
    assert payments_seam.STATE_BOUNCED not in {row["state"] for row in rows}
    assert payments_seam.STATE_REVERSED not in {row["state"] for row in rows}


@pytest.mark.django_db
def test_a_bounce_still_reads_bounced_over_reversed(pine_hill, sarah):
    """The bank-return pair is unchanged by the cancel branch."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        original = _payment(
            pine_hill, account, status=payment_models.PAYMENT_CLEARED, number="PMT-26-10001"
        )
        _payment(
            pine_hill,
            account,
            status=payment_models.PAYMENT_REVERSED,
            number="PMT-26-10002",
            amount="-129.0200",
            reverses=original,
            at=OCT_21,
        )

    rows = _read(pine_hill, account)
    assert [row["state"] for row in rows] == [
        payments_seam.STATE_BOUNCED,
        payments_seam.STATE_REVERSED,
    ]
    assert [row["returned_by_the_bank"] for row in rows] == [True, False]


def test_an_unknown_status_on_the_money_list_reads_unknown():
    class Row:
        status = "something_new"
        type = payment_models.PAYMENT_TYPE_PAYMENT

    state = payments_seam._payment_state(Row(), is_reversal=False, was_reversed=False)
    assert state == payments_seam.STATE_UNKNOWN == "unknown"
