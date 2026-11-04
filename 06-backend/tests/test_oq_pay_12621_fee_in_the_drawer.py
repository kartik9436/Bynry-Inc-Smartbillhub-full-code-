# ── Trace ──────────────────────────────────────────────
# Question: OQ-PAY-12621 — CLOSED 2026-09-24, option (a). PO, verbatim:
#           *"p1 a"* — a cash application fee taken at a counter counts toward
#           that counter's EXPECTED cash, so the close balances and the fee is
#           booked ONCE, at collection.
# Defect:   DEF-PAY-6375 — measured by lane REQ-FEE on 2026-09-23 and built
#           against by nobody until this.
# Rules:    CLAUDE.md hard rule 2 (four decimals) · hard rule 4 (NO payment row
#           is invented and no allow list moves) · `NFR-3`/`NFR-5` (the drawer
#           figure is grouped in SQL, never folded in Python) · decision log
#           2026-09-19 option A2 · decision log 2026-09-23 *a drawer difference
#           reaches the books* · hard-won law 7 habit 2 (what would make this
#           check pass wrongly?)
# Screens:  the Close counter screen (`3·2`, `3·3b`) — the SYSTEM SAYS column
# Tests:    this file. `payments/0045` is the column it turns on.
# ───────────────────────────────────────────────────────
"""**A fee in the drawer is money the close has to expect.**

WHAT WAS WRONG, IN ONE PARAGRAPH
---------------------------------
Two rulings met and produced a wrong posting. A2 (2026-09-19) posts a service
request's application fee at collection and writes **no payment row**, so
`running_split` — which reads `payments` — could not see it. The ruling of
2026-09-23 then made a drawer difference at close **reach the books**. So the
cash sat in the drawer, the expected count did not include it, the close read
OVER by exactly the fee, and that over posted: **one fee booked twice.**

**Worked, and it is the ruling's own figure:** Dana opens her counter holding
**$400.00**, takes Sarah Miller's **$70.00** application fee in cash, and
counts **$470.00** at close. Before this, the till expected **$400.00** and the
close read **$70.00 over**. Now it expects **$470.00** and the difference is
**$0.00**.

⚠ **THE FALSE PASS THIS FILE IS BUILT AGAINST (hard-won law 7, habit 2).**
*Take a fee and assert the expected figure went up* passes just as happily when
EVERY receipt in the tenant is being added — a fee another clerk took at
another till, or a card fee, which is not countable money at all. So the
negatives are asserted here at the same strength: a fee taken with **no till
open** moves nothing, a fee taken at **another clerk's till** moves that clerk's
till and not this one, and a **card** fee attaches to no till, exactly as a card
PAYMENT does not.

⚠ **AND THE MONEY-PATH HALF IS ASSERTED, NOT ASSUMED.** The ruling says *the
books are unchanged*, so this file also asserts what must NOT have happened:
**no `payments` row exists for the fee**, and the receipt still carries the one
collection entry it always did.
"""

from __future__ import annotations

from datetime import datetime, timezone as dt_timezone
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.payments import counter_receipt_models as cr_models
from apps.payments import counter_receipts, counters
from apps.payments import models as payment_models
from apps.tenancy import published_content_models as content_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana · marcus
from tests.test_us_met_helpers import staff_actor, tenant_ctx  # noqa: F401

pytestmark = [pytest.mark.django_db]

#: The ruling's own figures, and this whole file turns on them.
FEE = Decimal("70.00")
FLOAT = Decimal("400.0000")
COUNTED = "470.00"
TAKEN_AT = datetime(2026, 5, 12, 10, 30, tzinfo=dt_timezone.utc)


@pytest.fixture()
def centre(brazos):
    """A walk-in counter for the till to be at."""
    with tenant_ctx(brazos):
        return content_models.ServiceCentre.objects.create(
            tenant=brazos,
            slug="fee-window",
            name="Main office",
            address="101 Bend Road, Brazos Bend, TX 77422",
        )


def _open(actor, centre, *, float_amount=FLOAT):
    return counters.open_counter(
        actor,
        service_centre_id=centre.pk,
        opening_float=Decimal(float_amount),
        opened_at=timezone.now(),
    )


def _take_a_fee(actor, *, source_id, method_code="cash", receipt="RCP-26-4471", amount=FEE):
    """A fee through the REAL write path — nothing is stamped by hand here."""
    import uuid as _uuid

    return counter_receipts.record_counter_receipt(
        source_type=cr_models.SOURCE_SERVICE_REQUEST,
        source_id=source_id or _uuid.uuid4(),
        source_ref="SR-26-0048",
        receipt_no=receipt,
        amount=amount,
        currency="USD",
        method_code=method_code,
        taken_at=TAKEN_AT,
        actor=actor,
    )


def _cash_row(split):
    return next(row for row in split["by_method"] if row["method_code"] == "cash")


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE RULING'S OWN FIGURE — $400.00 + $70.00 = $470.00, AND IT BALANCES
# ══════════════════════════════════════════════════════════════════════════
def test_oq_pay_12621__the_fee_joins_the_expected_cash_and_the_close_balances(
    brazos, dana, centre
):
    """**$70.00 in the drawer is $70.00 the close expects.** PO: *"p1 a"*.

    Before this, `countable_expected` read **$400.00** while the drawer held
    **$470.00**, so the close reported **$70.00 over** — and since 2026-09-23
    an over POSTS, which booked the one fee a second time.
    """
    with tenant_ctx(brazos):
        opened = _open(dana, centre)
        before = counters.running_split(opened.session)
        assert before["countable_expected"] == "400.0000"

        _take_a_fee(dana, source_id=None)

        after = counters.running_split(opened.session)
        assert after["countable_expected"] == "470.0000", (
            "the fee is in the drawer and the close must expect it — OQ-PAY-12621 (a). "
            "A figure of 400.0000 here is DEF-PAY-6375 back: the close reads $70.00 over "
            "and, since 2026-09-23, posts it."
        )
        assert _cash_row(after)["system_total"] == "470.0000"

        sealed = counters.close_counter(
            dana,
            session_id=opened.session.pk,
            counted_totals={str(_cash_row(after)["method_id"]): COUNTED},
            closed_at=timezone.now(),
        )
        assert Decimal(str(sealed.session.difference)) == Decimal("0.0000"), (
            "a clerk who counts exactly what is in the drawer must be square. A non-zero "
            "difference here is the double booking the ruling exists to remove."
        )


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE BOOKS ARE UNCHANGED — THE OTHER HALF OF THE RULING
# ══════════════════════════════════════════════════════════════════════════
def test_oq_pay_12621__no_payment_row_is_invented_for_the_fee(brazos, dana, centre):
    """*"A2's posting unchanged; no payment row invented"* — asserted.

    ⚠ **THIS IS THE CASE THAT STOPS THE OBVIOUS WRONG FIX.** Writing a
    `payments` row for the fee would make the drawer balance too, and it would
    book the fee twice in the LEDGER instead of once — the same defect moved
    one table along, and invisible to case 1.
    """
    with tenant_ctx(brazos):
        opened = _open(dana, centre)
        rows_before = payment_models.Payment.objects.count()
        result = _take_a_fee(dana, source_id=None)

        assert payment_models.Payment.objects.count() == rows_before, (
            "record_counter_receipt must write NO payments row (decision log 2026-09-19, "
            "option A2). The drawer is made to balance by READING the receipt, never by "
            "inventing a payment."
        )
        receipt = cr_models.CounterReceipt.objects.get(pk=result["id"])
        assert receipt.collection_entry_id is not None, "the collection still posts"
        assert receipt.counter_session_id == opened.session.pk
        assert counters.running_split(opened.session)["countable_expected"] == "470.0000"


# ══════════════════════════════════════════════════════════════════════════
# 3 · THE NEGATIVES — each one is a way case 1 could pass wrongly
# ══════════════════════════════════════════════════════════════════════════
def test_oq_pay_12621__a_fee_taken_with_no_till_open_joins_no_drawer(brazos, dana, centre):
    """A receipt with no till is not a receipt belonging to every till.

    `till_refusal` is enforced at the ENDPOINT and not here, because the sample
    fixture seeds a counter collection for a utility with no clerks (`P2.23`),
    so this state is reachable and must mean *joins no drawer* — not *joins
    whichever drawer is asking*.
    """
    with tenant_ctx(brazos):
        result = _take_a_fee(dana, source_id=None)
        receipt = cr_models.CounterReceipt.objects.get(pk=result["id"])
        assert receipt.counter_session_id is None

        opened = _open(dana, centre)
        assert counters.running_split(opened.session)["countable_expected"] == "400.0000", (
            "a till opened AFTER a fee was taken must not inherit it. This is the check "
            "that fails if the drawer query drops its counter_session_id filter."
        )


def test_oq_pay_12621__another_clerks_fee_belongs_to_another_clerks_till(
    brazos, dana, centre
):
    """Two tills, two drawers. Marcus's fee is Marcus's to count."""
    marcus = staff_actor(brazos, "billing_clerk", "marcus.till@brazosbendutilities.test")
    with tenant_ctx(brazos):
        hers = _open(dana, centre)
        his = _open(marcus, centre)
        _take_a_fee(marcus, source_id=None, receipt="RCP-26-4472")

        assert counters.running_split(hers.session)["countable_expected"] == "400.0000", (
            "Dana must not be asked to count money Marcus took. A figure of 470.0000 here "
            "is the drawer query reading every receipt in the tenant."
        )
        assert counters.running_split(his.session)["countable_expected"] == "470.0000"


def test_oq_pay_12621__a_card_fee_attaches_to_no_till(brazos, dana, centre):
    """**You cannot count a card total in a drawer** (p056 ③), and
    `payments.counter_session_id` is left null for a card for the same reason.
    A receipt and a payment of one tender must not disagree about which till
    they belong to, on the same screen."""
    with tenant_ctx(brazos):
        opened = _open(dana, centre)
        result = _take_a_fee(dana, source_id=None, method_code="card")
        receipt = cr_models.CounterReceipt.objects.get(pk=result["id"])
        assert receipt.counter_session_id is None
        assert counters.running_split(opened.session)["countable_expected"] == "400.0000"


# ══════════════════════════════════════════════════════════════════════════
# 4 · THE NUMBER BESIDE THE FIGURE
# ══════════════════════════════════════════════════════════════════════════
def test_oq_pay_12621__the_count_beside_the_total_includes_the_receipt(
    brazos, dana, centre
):
    """`MyCounterPage` prints this count directly under the tender's total.

    A count that excluded a line the total includes is a number a clerk cannot
    reconcile with the one next to it — so the receipt moves both, together.
    """
    with tenant_ctx(brazos):
        opened = _open(dana, centre)
        assert _cash_row(counters.running_split(opened.session))["payment_count"] == 0
        _take_a_fee(dana, source_id=None)
        row = _cash_row(counters.running_split(opened.session))
        assert row["payment_count"] == 1
        assert row["system_total"] == "470.0000"


# ── Lifecycle ─────────────────────────────────────────────
# packet: OQ-PAY-12621 (CLOSED 2026-09-24, option (a)) · DEF-PAY-6375 ·
#   decision log 2026-09-19 (A2) · decision log 2026-09-23 (a drawer
#   difference reaches the books) · payments/0045
# generated: 2026-09-24 by LANE RULINGS-0924
# gates: proved RED against the tip's code before payments/0045 existed, and
#   run again on real PostgreSQL 16 (--ds=config.settings.pgtest)
# ──────────────────────────────────────────────────────────
