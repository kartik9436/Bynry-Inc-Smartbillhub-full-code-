# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 · §11 tasks 57 (CS-30's screen, P7) and 40 (CS-32's screens)
#           — the payload half of two screens whose ENGINES landed 2026-09-03
#           and whose facts reached no caller.
# Story:    US-PAY-001   Screens: S21 · S22 · S33 · S35 · S37
# Rules:    BR-PAY-880 / 883 (the cheque's structured facts and its hold) ·
#           BR-PAY-865 (a move is a reversal + a linked new payment) ·
#           B14 rule 31 (no database id is the visible value of a field) ·
#           CLAUDE.md hard rule 4 (the INSERT is the only writer)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""Hard-won law 2, twice, at the layer between an engine and a screen.

WHAT WAS TRUE BEFORE THIS LANE
==============================
Two engines landed on 2026-09-03 with every rule tested and **no route out**:

  * **CS-30.** `payments/0017` added `cheque_date`, `drawer_bank` and
    `bankable_from`; `services.record_payment` took all three; `GET /cheques`
    served three lists. But `POST /payments` — the ONLY door a person can reach
    — never passed them, and `selectors.payment_row` never served them back. So
    a cheque could not be given a date through any screen, and the cheque list
    a bookkeeper opens returned rows in which no cheque fact appeared.
  * **CS-32.** `payments.moved_from_payment_id` linked a moved payment to the
    one it came from, and nothing read it. CS-32 asks that **both** accounts
    show the move *"rather than as an unexplained reversal on one screen and an
    unexplained payment on the other"*, and neither screen could: the link was
    not on the wire in either direction.

Both are the same shape as `installment_seq` before task 6 — an argument the
service accepted and the API layer did not send.

THE RED PROOF, RUN BEFORE ANY OF THIS WAS TRUSTED GREEN (hard-won law 7)
========================================================================
Each assertion below was first run against the tree as it stood at 6dc8b07e:

  * `test_p7__the_record_door_takes_the_three_cheque_facts` failed with
    `assert None == datetime.date(2026, 8, 8)` — the door dropped the argument.
  * `test_p7__a_payment_row_carries_the_cheque_facts` failed with
    `KeyError: 'cheque_date'` — the selector served no such key.
  * `test_cs32__the_source_row_says_where_the_money_went` and
    `test_cs32__the_destination_row_says_where_it_came_from` failed with
    `KeyError: 'moved_to_account_no'` / `KeyError: 'moved_from_account_no'`.
  * `test_p7__an_unreadable_cheque_date_is_refused` failed with
    `DID NOT RAISE` — an unparseable date became a silent `None`, which drops
    the hold the batch cut obeys and banks a cheque before the day it exists.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.payments import models, selectors, services, transfer
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_ten_helpers import api_call
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

DRAWER_DAY = date(2026, 8, 8)
POSTED_AT = datetime(2026, 8, 8, 10, 0, tzinfo=UTC)
NOTICED_ON = date(2026, 8, 12)
THE_CHEQUE = Decimal("292.87")
CHEQUE_NO = "8842"
FIRST_NATIONAL = "First National"


def _record(dana, brazos, account, **body):
    """`POST /accounts/{id}/payments` through the WIRED stack.

    `api_call` is the shared helper the tenancy suite already uses: an
    authenticated user, a server-attached role and BE-01's tenant context
    entered around the view, exactly as the middleware does in production. A
    hand-rolled request object cannot reach a DRF `@api_view`, and calling the
    service directly would prove nothing about the DOOR — which is the whole
    finding this file exists for.
    """
    from apps.payments import api

    # ⚠ `staff_actor` returns a `SimpleNamespace` with no `is_authenticated`,
    # and `core.permissions._role_of` reads that BEFORE it reads the role — so
    # a request carrying the right role answers 403 AUTH-002 without it. The
    # flag is set here rather than in the shared fixture: every other caller of
    # `dana` passes it to a SERVICE, where the attribute means nothing.
    dana.is_authenticated = True
    return api_call(
        api.account_payments,
        "post",
        path=f"/api/accounts/{account.pk}/payments",
        user=dana,
        role="system_admin",
        tenant=brazos,
        data={"idempotency_key": str(uuid.uuid4()), **body},
        account_id=str(account.pk),
    )


# ══ P7 · CS-30 — THE CHEQUE'S OWN STATE, THROUGH THE DOOR AND BACK ═════════


def test_p7__the_record_door_takes_the_three_cheque_facts(brazos, dana):
    """`POST /payments` passes `cheque_date`, `drawer_bank` and `bankable_from`.

    The INSERT is the only thing that may write them (hard rule 4's trigger
    refuses a later column change on a row that is not `processing`), so a door
    that drops the argument is a fact NO screen can ever record.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        response = _record(
            dana,
            brazos,
            account,
            amount="100.00",
            posted_at=POSTED_AT.isoformat(),
            method="check",
            confirmation=CHEQUE_NO,
            cheque_date=DRAWER_DAY.isoformat(),
            drawer_bank=FIRST_NATIONAL,
            bankable_from="2026-08-29",
        )
        assert response.status_code == 201, response.data
        row = models.Payment.objects.get(pk=response.data["id"])
        assert row.cheque_date == DRAWER_DAY
        assert row.drawer_bank == FIRST_NATIONAL
        assert row.bankable_from == date(2026, 8, 29), (
            "the post-dated hold the deposit-batch cut obeys — CS-30's fourth rule, "
            "and the half that makes the hold safe"
        )


def test_p7__an_unreadable_cheque_date_is_refused(brazos, dana):
    """Absent and unreadable are different answers.

    A cheque dated `14/07/2026` that quietly became "no date" would drop the
    hold and the cheque would be banked before the day it is written.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        response = _record(
            dana,
            brazos,
            account,
            amount="100.00",
            posted_at=POSTED_AT.isoformat(),
            method="check",
            confirmation=CHEQUE_NO,
            cheque_date="14/07/2026",
            drawer_bank=FIRST_NATIONAL,
        )
        # The catalog refusal, rendered by the handler rather than raised past
        # it — a 422 the screen shows as a sentence beside the field.
        assert response.status_code == 422, response.data
        assert response.data["code"] == errors.VAL_FORMAT
        assert [entry["field"] for entry in response.data["field_errors"]] == ["cheque_date"]
        assert not models.Payment.objects.filter(account_id=account.pk).exists(), (
            "and no PMT- number is burnt out of the tenant's series behind a refusal"
        )


def test_p7__a_payment_row_carries_the_cheque_facts(brazos, dana):
    """`GET /cheques` is `payment_row`, so the facts must be ON `payment_row`.

    Before this lane the three lists came back with no cheque state in them at
    all: a screen could group the rows and could not say what any of them was.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        paid = services.record_payment(
            dana,
            account_id=account.pk,
            amount=Decimal("100.00"),
            posted_at=POSTED_AT,
            cleared_at=None,
            method_code="check",
            confirmation=CHEQUE_NO,
            cheque_date=DRAWER_DAY,
            drawer_bank=FIRST_NATIONAL,
            bankable_from=date(2026, 8, 29),
            idempotency_reference=uuid.uuid4(),
        )
        row = selectors.payment_row(models.Payment.objects.get(pk=paid.payment_id))
        assert row["cheque_date"] == "2026-08-08"
        assert row["drawer_bank"] == FIRST_NATIONAL
        assert row["bankable_from"] == "2026-08-29"


def test_p7__a_payment_that_is_not_a_cheque_states_the_absence(brazos, dana):
    """Null is a STATE, not a missing value — the same claim `cleared_at` makes."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        paid = services.record_payment(
            dana,
            account_id=account.pk,
            amount=Decimal("50.00"),
            posted_at=POSTED_AT,
            cleared_at=POSTED_AT,
            method_code="cash",
            idempotency_reference=uuid.uuid4(),
        )
        row = selectors.payment_row(models.Payment.objects.get(pk=paid.payment_id))
        assert row["cheque_date"] is None
        assert row["drawer_bank"] is None
        assert row["bankable_from"] is None


# ══ CS-32 · BOTH ACCOUNTS SHOWING THE MOVE, AS A MOVE ══════════════════════


def _two_accounts(actor, tenant):
    """The two Patels of CS-32's own case — adjacent units, one cheque."""
    from tests.test_cr059_cs8_cs32_transfer import two_accounts_of_one_customer

    return two_accounts_of_one_customer(actor, tenant)


def _a_moved_cheque(actor, tenant):
    wrong, right = _two_accounts(actor, tenant)
    paid = services.record_payment(
        actor,
        account_id=wrong.pk,
        amount=THE_CHEQUE,
        posted_at=POSTED_AT,
        cleared_at=POSTED_AT,
        method_code="check",
        confirmation=CHEQUE_NO,
        idempotency_reference=uuid.uuid4(),
    )
    moved = transfer.move_payment_to_account(
        actor,
        payment_id=paid.payment_id,
        destination_account_id=right.pk,
        reason="recorded against the wrong Patel",
        moved_on=NOTICED_ON,
        approval="approved by the office manager",
        idempotency_reference=uuid.uuid4(),
    )
    return wrong, right, paid, moved


def test_cs32__the_source_row_says_where_the_money_went(brazos, dana):
    """*"moved to 2608-0155"* — the ORIGINAL row, on the source account's tab.

    Read backwards off the destination leg's own FK, so there is no second
    column and no second write for the two halves to disagree about.
    """
    with tenant_ctx(brazos):
        _wrong, right, paid, _moved = _a_moved_cheque(dana, brazos)
        row = selectors.payment_row(models.Payment.objects.get(pk=paid.payment_id))
        assert row["moved_to_account_no"] == right.account_no
        assert row["moved_to_payment_no"] is not None
        assert row["moved_from_account_no"] is None, "the source row came from nowhere"


def test_cs32__the_destination_row_says_where_it_came_from(brazos, dana):
    """*"moved from 2608-0141"* — the new payment, on the destination's tab.

    It names the ORIGINAL payment's number and not the reversing row's, because
    the number the customer holds is the original's: a customer quoting their
    receipt must be findable.
    """
    with tenant_ctx(brazos):
        wrong, _right, paid, moved = _a_moved_cheque(dana, brazos)
        landed = models.Payment.objects.get(pk=moved.destination_payment_id)
        row = selectors.payment_row(landed)
        assert row["moved_from_account_no"] == wrong.account_no
        original = models.Payment.objects.get(pk=paid.payment_id)
        assert row["moved_from_payment_no"] == original.payment_no
        assert row["moved_to_account_no"] is None, "the money stopped here"


def test_cs32__an_ordinary_payment_carries_no_move_marks(brazos, dana):
    """Four nulls, so a screen draws the mark only where there is one to draw."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        paid = services.record_payment(
            dana,
            account_id=account.pk,
            amount=Decimal("25.00"),
            posted_at=POSTED_AT,
            cleared_at=POSTED_AT,
            method_code="cash",
            idempotency_reference=uuid.uuid4(),
        )
        row = selectors.payment_row(models.Payment.objects.get(pk=paid.payment_id))
        assert row["moved_from_payment_no"] is None
        assert row["moved_from_account_no"] is None
        assert row["moved_to_payment_no"] is None
        assert row["moved_to_account_no"] is None


# ══ CS-33 · WHAT THE PAYMENT STILL STANDS FOR, BEFORE THE REVERSAL ═════════


def test_cs33__the_plan_says_what_the_payment_still_stands_for(brazos, dana):
    """The S35 amount field's remainder is measured off THIS, never off `amount`.

    `reversed_payment_dict` has served `still_stands` AFTER the act since task
    66, for the stated reason that a screen must not subtract two figures
    itself. The modal needs the same fact BEFORE it, because the clerk decides
    then — and after one partial reversal `payments.amount` is no longer what
    the payment stands for.
    """
    from apps.payments import reversal, reversal_rules

    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        paid = services.record_payment(
            dana,
            account_id=account.pk,
            amount=THE_CHEQUE,
            posted_at=POSTED_AT,
            cleared_at=POSTED_AT,
            method_code="check",
            confirmation=CHEQUE_NO,
            idempotency_reference=uuid.uuid4(),
        )
        original = models.Payment.objects.get(pk=paid.payment_id)
        plan = reversal_rules.reversal_plan(original, reason="nsf", on=NOTICED_ON)
        assert plan["already_reversed"] == "0.0000"
        assert plan["stands_for"] == "292.8700", "nothing has come back off it yet"

        # $100.00 off a $292.87 cheque leaves $192.87 — CS-33's worked figure.
        reversal.reverse_payment(
            dana,
            payment_id=paid.payment_id,
            returned_on=datetime(2026, 8, 12, 9, 0, tzinfo=UTC),
            reason="nsf",
            amount=Decimal("100.00"),
            idempotency_reference=uuid.uuid4(),
        )
        original.refresh_from_db()
        after = reversal_rules.reversal_plan(original, reason="nsf", on=NOTICED_ON)
        assert after["already_reversed"] == "100.0000"
        assert after["stands_for"] == "192.8700", (
            "and THIS is the base the next remainder is measured off — a screen "
            "subtracting from 292.87 would offer a figure the service refuses"
        )
