# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 · CS-22 (task 33) — "Carry a deposit forward to a new
#           account". PO ruling 2026-09-01, §6 Q2 option (b) CHOSEN: *"offer it
#           forward: the move-in screen says the deposit is held on the old
#           account and the clerk accepts it"*. Option (a) — refund and
#           re-collect — DECLINED. Option (c) — only within 60 days — DECLINED.
# Story:    US-CUS-004 / US-CUS-007 (the move-in that offers it) · US-PAY-002
#           TC-1 (a deposit is HELD, never credit)
#           Screens: S19 step 4 (offering the prior deposit) · S21 (where the
#           carried deposit came from) — both are task 34 and NOT this lane.
# Rules:    BR-CUS-024 (carry-forward: linkage CONFIRMED, mechanics ruled
#           2026-09-01) · BR-CUS-054 (the customer entity is what makes
#           "another account" mean anything) · BR-CUS-050 (the ORIGINAL receipt
#           date) · BR-CUS-057 (interest accrues from it) · BR-CUS-670 (the
#           deposit register) · BR-PAY-012 / US-PAY-002 TC-1 (a deposit is a
#           LIABILITY, never revenue and never credit) · BR-PAY-864 (one
#           balanced movement recorded on both) · BR-LED-007 (the deposit
#           tie-out) · CLAUDE.md rule 1 · rule 2 · rule 5 · rule 7
# Tests:    this file · test_cr059_cs22_deposit_carry_pg.py (PostgreSQL only)
# ───────────────────────────────────────────────────────
"""CS-22 — the deposit moves as a LIABILITY, and never as a credit.

═══════════════════════════════════════════════════════════════════════════════
THE ONE MISTAKE THIS FILE EXISTS TO CATCH, AND IT LOOKS LIKE CORRECT CODE
═══════════════════════════════════════════════════════════════════════════════
CS-8 landed on 2026-09-03 and published `transfer_credit_between_accounts`,
which moves a customer's CREDIT: **DR 2400 customer credit (source) / CR 1200
receivables (destination)**. Wiring this carry-forward straight into that call
is the obvious thing to do and it is **wrong in a way nothing would report**:

  * the journal entry BALANCES;
  * the suites stay GREEN;
  * the deposit tie-out still FOOTS, because both halves moved;
  * and the customer's **returnable security has settled a bill** — it has been
    turned into revenue — after which they are asked for a fresh deposit they
    have already paid.

So the assertions here are mostly about what did **not** happen:
`test_cs22__the_carried_deposit_meets_no_bill_and_becomes_no_credit` is the one
that fails if anybody ever "simplifies" the deposit branch away.

═══════════════════════════════════════════════════════════════════════════════
THE FIGURES
═══════════════════════════════════════════════════════════════════════════════
    150.00 held on a closed account carries to the new one
    register  old 150.00 → 0.00        new 0.00 → 150.00
    books     DR 2300 150.00 (old)     CR 2300 150.00 (new)
    the tenant's 2300 balance is UNCHANGED — nothing was realised or discharged
    the destination's receivables are UNTOUCHED — a 948.20 bill stays 948.20
    the ORIGINAL receipt date moves, so BR-CUS-057 reads the same 3.50 after
    153.50 confirmed against a 150.00 principal is REFUSED, naming both figures

═══════════════════════════════════════════════════════════════════════════════
THE RED PROOF, RUN BEFORE ANY OF THIS WAS TRUSTED GREEN (hard-won law 7)
═══════════════════════════════════════════════════════════════════════════════
Each was made to fail first, and the failure is quoted in the lane's
review-ledger row:

  * With `carry_deposit_forward` delegating with `purpose=PURPOSE_BILL` — the
    exact trap above — `test_cs22__the_carried_deposit_meets_no_bill_and_
    becomes_no_credit` fails on `assert Decimal('150.00') == Decimal('0')`:
    the money met the destination's open bill.
  * With the same sabotage, `test_cs22__the_books_move_2300_to_2300` fails on
    the DEBIT designation, reading `customer_credit_balance` where
    `deposit_liability` is required — the accounting error stated as an account
    name rather than as a consequence.
  * With `_carry_deposit_register` not passing `received_on`,
    `test_cs22__the_interest_clock_carries_with_the_money` fails on
    `assert None is not None` and then on `3.50 == 0.00` — the customer's
    accrued interest silently gone.
  * With `_refuse_unless_the_deposit_is_there`'s `expected` check removed,
    `test_cs22__the_offered_figure_is_confirmed_against_the_principal` fails
    with `DID NOT RAISE` and 150.00 moves where 153.50 was confirmed.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.customers import deposit_interest
from apps.customers import models as customer_models
from apps.ledger import chart, models as ledger_models, selectors as ledger_selectors, tie_out
from apps.payments import ledger_seam, models, selectors, services, transfer
from apps.payments.exceptions import PaymentRuleError

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_001_record_payment import an_issued_bill
from tests.test_cr059_cs8_cs32_transfer import two_accounts_of_one_customer
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

ZERO = Decimal("0")

#: The repo's own deposit figure — DEF-177's, US-PAY-002 TC-1's, and the one
#: `discounts.carry_forward_offer` works its `carried $153.50` from.
THE_DEPOSIT = Decimal("150.00")

#: ❄️ WE-7's frozen accrual: 150.00 at 2% simple for 14 completed months. The
#: figure is NOT recomputed here — `deposit_interest.accrued` is the engine
#: CS-20 landed and this file asserts that carrying the money carries it too.
THE_INTEREST = Decimal("3.50")
THE_RATE = Decimal("2")
THE_POSITION = THE_DEPOSIT + THE_INTEREST  # 153.50 — what the OFFER shows

#: A bill on the DESTINATION account, so "it met no bill" is a claim about a
#: real open receivable rather than about an empty account.
THE_BILL = Decimal("948.20")

RECEIVED_AT = datetime(2025, 7, 2, 10, 0, tzinfo=UTC)
FOURTEEN_MONTHS_ON = date(2026, 9, 2)
CARRIED_AT = datetime(2026, 9, 3, 9, 0, tzinfo=UTC)

REASON = "closed 2608-0141 and moved in at 2608-0233; deposit accepted forward"


# ══ the fixtures ═══════════════════════════════════════════════════════════


def a_deposit_on(actor, account, amount=THE_DEPOSIT, when=RECEIVED_AT):
    """A cleared deposit-purpose payment — the register and 2300 both move."""
    return services.record_payment(
        actor,
        account_id=account.pk,
        amount=amount,
        posted_at=when,
        cleared_at=when,
        method_code="cash",
        purpose=models.PURPOSE_DEPOSIT,
        idempotency_reference=uuid.uuid4(),
    )


def a_customer_who_moved(actor, tenant):
    """Two accounts of one customer, the OLD one holding a $150.00 deposit."""
    old, new = two_accounts_of_one_customer(actor, tenant)
    a_deposit_on(actor, old)
    return old, new


def _register(account_id) -> Decimal:
    row = customer_models.Account.objects.filter(pk=account_id).values("deposit_on_file").first()
    return Decimal(row["deposit_on_file"] or ZERO)


def _received_on(account_id):
    return (
        customer_models.Account.objects.filter(pk=account_id)
        .values_list("deposit_received_on", flat=True)
        .first()
    )


def _gl_balance(designation: str) -> Decimal:
    """The tenant's posted balance on one DESIGNATION — debits less credits.

    By designation and never by code, exactly as every posting path resolves it
    (`chart.py`'s whole reason for existing): a utility that renumbers 2300 must
    not silently turn this assertion into one about a different account.
    """
    account_id = ledger_selectors.gl_account_id_for_designation(designation)
    total = ZERO
    for line in ledger_models.JournalLine.objects.filter(ledger_account_id=account_id).values(
        "side", "amount"
    ):
        total += line["amount"] if line["side"] == "debit" else -line["amount"]
    return total


def _legs_of(entry_id):
    """The posted lines of ONE entry, with their account dimension.

    Read out of `journal_lines` directly rather than through a reporting layer:
    what is asserted is what LANDED, and a report that was wrong in the same
    direction would agree with a broken posting.
    """
    return list(
        ledger_models.JournalLine.objects.filter(journal_entry_id=entry_id).order_by("side", "id")
    )


def _deposit_tie_out():
    """BR-LED-007's own row — books against register, as S36 draws it."""
    result = tie_out.tie_outs(period_start=date(2025, 1, 1), period_end=date(2027, 12, 31))
    return {row.subledger: row for row in result["rows"]}[tie_out.SUBLEDGER_DEPOSITS]


# ══ CS-22 · THE MOVEMENT ═══════════════════════════════════════════════════


def test_cs22__the_deposit_carries_and_the_customer_is_not_asked_twice(brazos, dana):
    """**$150.00 held on the closed account is $150.00 held on the new one.**

    The PO's own case, and the whole content of the change: *"A customer who
    closes one account and opens another should not be asked for a second
    deposit."* Both register figures are asserted because a carry that emptied
    one without filling the other is exactly the half-made state the writer
    refuses to commit.
    """
    with tenant_ctx(brazos):
        old, new = a_customer_who_moved(dana, brazos)
        assert _register(old.pk) == THE_DEPOSIT
        assert _register(new.pk) == ZERO

        carried = transfer.carry_deposit_forward(
            dana,
            source_account_id=old.pk,
            destination_account_id=new.pk,
            moved_on=CARRIED_AT,
            reason=REASON,
            idempotency_reference=uuid.uuid4(),
        )

        assert carried.kind == transfer.KIND_DEPOSIT_CARRY_FORWARD
        assert carried.created is True
        assert carried.amount == THE_DEPOSIT
        assert carried.held == THE_DEPOSIT
        # Stated ON THE RESULT so a caller asserts rather than re-reads at a
        # moment when a sibling transaction has moved one of them.
        assert carried.source_deposit_after == ZERO
        assert carried.destination_deposit_after == THE_DEPOSIT
        assert _register(old.pk) == ZERO
        assert _register(new.pk) == THE_DEPOSIT


def test_cs22__the_carried_deposit_meets_no_bill_and_becomes_no_credit(brazos, dana):
    """⚠ **THE TRAP. A deposit is SECURITY, and security settles nothing.**

    The destination carries a real, issued, open **948.20** bill. If the carry
    went through CS-8's credit legs it would meet that bill and the customer's
    returnable deposit would have become the utility's revenue — on a balanced
    entry, with every other assertion in this file still passing.

    Three independent statements of the same fact, because one of them alone
    could be true for the wrong reason:
      * the SERVICE reports nothing applied and nothing carried as credit;
      * NO allocation row exists against the arriving payment;
      * the account's CREDIT POSITION is untouched — `account_credit_position`
        excludes deposit-purpose rows by name (US-PAY-002 TC-1), so a carried
        deposit can never be spent by `credit.apply_credit_at_issue` on the new
        account's first bill.
    """
    with tenant_ctx(brazos):
        old, new = a_customer_who_moved(dana, brazos)
        bill = an_issued_bill(
            brazos,
            new,
            number="BL-2608-019001",
            total=THE_BILL,
            issued_on=date(2026, 8, 1),
        )
        receivable_before = _gl_balance(chart.AR)

        carried = transfer.carry_deposit_forward(
            dana,
            source_account_id=old.pk,
            destination_account_id=new.pk,
            moved_on=CARRIED_AT,
            reason=REASON,
            idempotency_reference=uuid.uuid4(),
        )

        assert carried.applied == ZERO, (
            f"the carried deposit met {carried.applied} of bills — a customer's returnable "
            "security has just been turned into revenue on a balanced entry"
        )
        assert carried.credit_carried == ZERO
        assert carried.allocations == ()
        assert (
            models.Allocation.objects.filter(payment_id=carried.destination_payment_id).count() == 0
        )
        assert selectors.account_credit_position(new.pk) == ZERO
        # The books say it too: receivables did not move at all.
        assert _gl_balance(chart.AR) == receivable_before
        assert bill is not None


def test_cs22__the_books_move_2300_to_2300(brazos, dana):
    """**DR 2300 (source) / CR 2300 (destination)** — and nothing else moves.

    CLAUDE.md rule 5: this is one balanced entry written by the ledger posting
    service. What makes it CS-22's entry rather than CS-8's is which obligation
    the debit discharges, so the designations are asserted by NAME.

    ⚠ The tenant's 2300 BALANCE is unchanged, and that is the accounting fact
    underneath the whole change: the utility held 150.00 of this customer's
    money before and holds 150.00 after. Only the account dimension moved.
    """
    with tenant_ctx(brazos):
        old, new = a_customer_who_moved(dana, brazos)
        liability_before = _gl_balance(chart.DEPOSIT_LIABILITY)
        assert liability_before == -THE_DEPOSIT  # a credit balance: money owed back

        carried = transfer.carry_deposit_forward(
            dana,
            source_account_id=old.pk,
            destination_account_id=new.pk,
            moved_on=CARRIED_AT,
            reason=REASON,
            idempotency_reference=uuid.uuid4(),
        )

        legs = _legs_of(carried.journal_entry_id)
        deposit_gl = ledger_selectors.gl_account_id_for_designation(chart.DEPOSIT_LIABILITY)
        assert len(legs) == 2, f"a carry is a two-legged entry; this one has {len(legs)}"
        debits = [leg for leg in legs if leg.side == "debit"]
        credits = [leg for leg in legs if leg.side == "credit"]
        assert len(debits) == len(credits) == 1
        assert str(debits[0].ledger_account_id) == str(deposit_gl), (
            "the DEBIT is not the deposit liability — a carry that debits customer credit "
            "discharges a balance the customer never had and strands the 2300 on a closed account"
        )
        assert str(credits[0].ledger_account_id) == str(deposit_gl)
        assert debits[0].amount == credits[0].amount == THE_DEPOSIT
        assert str(debits[0].account_id) == str(old.pk)
        assert str(credits[0].account_id) == str(new.pk)
        # NOTHING WAS REALISED. The liability is the same size, held elsewhere.
        assert _gl_balance(chart.DEPOSIT_LIABILITY) == liability_before


def test_cs22__the_register_and_the_books_still_agree(brazos, dana):
    """BR-LED-007's tie-out — the check a finance officer actually looks at.

    DEF-177 was *"books $150.00 / register $0.00"*, and a carry touching one
    side without the other would re-open it as two errors that cancel in the
    total. The panel is read through `tie_out.tie_outs` rather than by summing
    here, for that file's own reason: a test computing its own comparison can
    pass over a panel that still shows red.
    """
    with tenant_ctx(brazos):
        old, new = a_customer_who_moved(dana, brazos)
        before = _deposit_tie_out()
        assert before.gl == before.register == THE_DEPOSIT
        assert before.state == tie_out.STATE_AGREED

        transfer.carry_deposit_forward(
            dana,
            source_account_id=old.pk,
            destination_account_id=new.pk,
            moved_on=CARRIED_AT,
            reason=REASON,
            idempotency_reference=uuid.uuid4(),
        )

        after = _deposit_tie_out()
        assert after.gl == THE_DEPOSIT and after.register == THE_DEPOSIT
        assert after.drift == ZERO
        assert after.state == tie_out.STATE_AGREED
        # NON-VACUITY: agreeing about 0.00 would agree about nothing.
        assert after.gl != ZERO


def test_cs22__the_interest_clock_carries_with_the_money(brazos, dana):
    """**BR-CUS-050/057 — the ORIGINAL receipt date moves, so $3.50 survives.**

    This is why the movement is the **principal** and the customer still loses
    nothing. `discounts.carry_forward_offer` shows the POSITION — 153.50 — and
    what the register and the 2300 liability hold is the 150.00 principal;
    interest is not booked anywhere until a final bill accrues it. Carrying the
    principal WITH its receipt date means BR-CUS-057 recomputes the identical
    3.50 on the new account from the day it lands.

    Stamping today instead is the silent version of taking the customer's
    interest — `record_deposit_movement`'s own words: *"quietly under-pay the
    customer who has been with the utility longest."*
    """
    with tenant_ctx(brazos):
        old, new = a_customer_who_moved(dana, brazos)
        original_stamp = _received_on(old.pk)
        assert original_stamp == RECEIVED_AT.date()

        transfer.carry_deposit_forward(
            dana,
            source_account_id=old.pk,
            destination_account_id=new.pk,
            moved_on=CARRIED_AT,
            reason=REASON,
            idempotency_reference=uuid.uuid4(),
        )

        assert _received_on(new.pk) == original_stamp, (
            "the new account was stamped with the carry date, so BR-CUS-057's clock restarted "
            "and the customer's accrued interest is gone with no report showing a difference"
        )
        # ❄️ WE-7's frozen 3.50, recomputed by CS-20's engine from what the
        # DESTINATION now stores. Same principal, same rate, same start date.
        assert (
            deposit_interest.accrued(
                principal=_register(new.pk),
                annual_rate_percent=THE_RATE,
                received_on=_received_on(new.pk),
                as_of=FOURTEEN_MONTHS_ON,
            )
            == THE_INTEREST
        )


def test_cs22__the_offered_figure_is_confirmed_against_the_principal(brazos, dana):
    """**153.50 confirmed against a 150.00 principal is REFUSED, with both.**

    The move-in screen's DEPOSIT cell reads `carried $153.50` — the customer's
    position. A screen posting that figure back must not silently move 150.00,
    and must not move 153.50 either: 3.50 of it has never been booked, so
    `record_deposit_movement` would refuse the release for more than is held
    and the ledger would credit a liability nothing backs.

    The refusal names both figures and says where the difference went, because
    the clerk's next question is *"then where is the 3.50?"* and the answer —
    it travels as the receipt date — is not guessable.
    """
    with tenant_ctx(brazos):
        old, new = a_customer_who_moved(dana, brazos)
        with pytest.raises(PaymentRuleError) as refused:
            transfer.carry_deposit_forward(
                dana,
                source_account_id=old.pk,
                destination_account_id=new.pk,
                moved_on=CARRIED_AT,
                reason=REASON,
                expected_amount=THE_POSITION,
                idempotency_reference=uuid.uuid4(),
            )
        assert "150.00" in str(refused.value) and "153.50" in str(refused.value)
        # Nothing was moved, on either side.
        assert _register(old.pk) == THE_DEPOSIT
        assert _register(new.pk) == ZERO

        # …and the PRINCIPAL confirmed is accepted.
        carried = transfer.carry_deposit_forward(
            dana,
            source_account_id=old.pk,
            destination_account_id=new.pk,
            moved_on=CARRIED_AT,
            reason=REASON,
            expected_amount=THE_DEPOSIT,
            idempotency_reference=uuid.uuid4(),
        )
        assert carried.held == THE_DEPOSIT


def test_cs22__an_account_holding_no_deposit_is_refused(brazos, dana):
    """Nothing to carry is a REFUSAL, never a silent 0.00 movement.

    A zero-amount pair of payment rows and a zero-line journal entry would be a
    movement of nothing that a clerk would then have to explain, and the
    move-in would read as though the deposit had been carried when the new
    account still owes one under the plan's own schedule (BR-CUS-023).
    """
    with tenant_ctx(brazos):
        old, new = two_accounts_of_one_customer(dana, brazos)
        with pytest.raises(PaymentRuleError, match="holds no deposit"):
            transfer.carry_deposit_forward(
                dana,
                source_account_id=old.pk,
                destination_account_id=new.pk,
                moved_on=CARRIED_AT,
                reason=REASON,
                idempotency_reference=uuid.uuid4(),
            )


def test_cs22__two_strangers_accounts_are_refused(brazos, dana):
    """BR-CUS-054 — a carry crosses two accounts of ONE customer or none.

    The same boundary CS-8 draws, inherited rather than re-implemented: the
    carry-forward goes through the one writer, so the customer-link refusal it
    already carries applies unchanged. A deposit moved between two people is
    the unlawful movement OQ-135's declined option (b) warns about by name.
    """
    with tenant_ctx(brazos):
        old, _ = a_customer_who_moved(dana, brazos)
        stranger = an_account(dana, brazos, account_no="A-2608-0999")
        with pytest.raises(PaymentRuleError, match="not held by one customer"):
            transfer.carry_deposit_forward(
                dana,
                source_account_id=old.pk,
                destination_account_id=stranger.pk,
                moved_on=CARRIED_AT,
                reason=REASON,
                idempotency_reference=uuid.uuid4(),
            )
        assert _register(old.pk) == THE_DEPOSIT


def test_cs22__a_reason_is_required(brazos, dana):
    """Hard rule 7's audit row is the only place the WHY will ever exist."""
    with tenant_ctx(brazos):
        old, new = a_customer_who_moved(dana, brazos)
        with pytest.raises(PaymentRuleError, match="needs a reason"):
            transfer.carry_deposit_forward(
                dana,
                source_account_id=old.pk,
                destination_account_id=new.pk,
                moved_on=CARRIED_AT,
                reason="   ",
                idempotency_reference=uuid.uuid4(),
            )


def test_cs22__a_double_submit_carries_the_deposit_once(brazos, dana):
    """Hard rule 6 — a move-in wizard submitted twice carries it ONCE.

    ⚠ **AND THE REPLAY REPORTS ITSELF AS A DEPOSIT CARRY.** `_replayed` answered
    `credit_transfer` unconditionally until this change; a replay under that
    name would tell the move-in screen a CREDIT was transferred, so it would
    offer the deposit forward a second time and show the customer's security as
    spendable money.
    """
    with tenant_ctx(brazos):
        old, new = a_customer_who_moved(dana, brazos)
        token = uuid.uuid4()
        first = transfer.carry_deposit_forward(
            dana,
            source_account_id=old.pk,
            destination_account_id=new.pk,
            moved_on=CARRIED_AT,
            reason=REASON,
            idempotency_reference=token,
        )
        again = transfer.carry_deposit_forward(
            dana,
            source_account_id=old.pk,
            destination_account_id=new.pk,
            moved_on=CARRIED_AT,
            reason=REASON,
            idempotency_reference=token,
        )

        assert first.created is True and again.created is False
        assert again.kind == transfer.KIND_DEPOSIT_CARRY_FORWARD
        assert again.held == THE_DEPOSIT
        assert again.source_payment_id == first.source_payment_id
        # The register moved once, not twice.
        assert _register(old.pk) == ZERO
        assert _register(new.pk) == THE_DEPOSIT
        assert (
            models.Payment.objects.filter(
                account_id=new.pk, purpose=models.PURPOSE_DEPOSIT, amount=THE_DEPOSIT
            ).count()
            == 1
        )


def test_cs22__both_accounts_carry_an_audit_row(brazos, dana, audit_rows):
    """CLAUDE.md rule 7, and TWO rows because they are two facts.

    A clerk reading either account's trail must find the movement without
    knowing to look at the other one, and the action is its OWN code:
    *"where did this customer's SECURITY go"* is a different question from
    *"where did their credit go"* and must be answerable without reading a
    payload.

    Read through the `audit_rows` capture sink rather than off `AuditLog`: the
    trail is tenant-partitioned and `core.audit` hands every row to whatever
    sink is registered, so the sink is what this file can assert about without
    depending on which partition a test's `created_at` lands in.
    """
    with tenant_ctx(brazos):
        old, new_account = a_customer_who_moved(dana, brazos)
        carried = transfer.carry_deposit_forward(
            dana,
            source_account_id=old.pk,
            destination_account_id=new_account.pk,
            moved_on=CARRIED_AT,
            reason=REASON,
            idempotency_reference=uuid.uuid4(),
        )
    rows = [row for row in audit_rows if row["action"] == transfer.AUDIT_DEPOSIT_CARRIED]
    assert {str(row["entity_id"]) for row in rows} == {
        str(carried.source_payment_id),
        str(carried.destination_payment_id),
    }, "a clerk reading one account's trail cannot see where the deposit went"
    payload = rows[0]["after"]
    assert payload["kind"] == transfer.KIND_DEPOSIT_CARRY_FORWARD
    assert payload["reason"] == REASON
    # ⚠ **COMPARED AS DECIMALS, NOT AS STRINGS, AND THE REASON IS HARD RULE 2.**
    # The trail carries the STORED figure, and money is stored to more places
    # than it is displayed — this reads `150.000000`, not `150.00`. A string
    # assertion here would pin the trail to a DISPLAY form and go red the day
    # the column's scale changes, which is a test asserting the wrong thing
    # about a rule it does not own.
    assert Decimal(payload["held"]) == THE_DEPOSIT
    # The receipt date is on the trail because it is the term that carries the
    # customer's interest, and nothing else records that it travelled.
    assert payload["deposit_received_on"] == RECEIVED_AT.date().isoformat()
    # The register MOVE is on the trail too — customers writes its own
    # `deposit.released` / `deposit.received` rows, and these two are what let
    # a reader tie one movement to both of them without a join.
    assert Decimal(payload["source_deposit_after"]) == ZERO
    assert Decimal(payload["destination_deposit_after"]) == THE_DEPOSIT


# ══ THE LEDGER SEAM'S OWN GUARDS — the second, independent check ═══════════


def test_cs22__the_seam_refuses_a_deposit_that_met_a_bill(brazos, dana):
    """⚠ **The guard that makes the trap impossible rather than unlikely.**

    `post_account_transfer` reads the purpose off the ROWS, not off a caller's
    flag, and refuses a deposit movement that reports anything met against
    bills or carried as credit. A future caller that composed one — the exact
    "wire it into CS-8" mistake — meets a refusal naming the accounting, not a
    balanced entry nobody questions.
    """
    with tenant_ctx(brazos):
        old, new = a_customer_who_moved(dana, brazos)
        out_row = models.Payment.objects.filter(
            account_id=old.pk, purpose=models.PURPOSE_DEPOSIT
        ).first()
        in_row = models.Payment.objects.filter(
            account_id=old.pk, purpose=models.PURPOSE_DEPOSIT
        ).first()
        with pytest.raises(PaymentRuleError, match="turn returnable customer security"):
            ledger_seam.post_account_transfer(
                source_payment=_negated(out_row),
                destination_payment=in_row,
                applied_to_bills=THE_DEPOSIT,
                credit_carried=ZERO,
                held=ZERO,
                entry_date=CARRIED_AT.date(),
                posted_at=CARRIED_AT,
                actor=dana,
            )
        assert new is not None


def test_cs22__the_seam_refuses_two_legs_of_different_purposes(brazos, dana):
    """One movement has ONE purpose on both legs.

    A deposit that ARRIVED as a credit would be the utility's security to
    spend; a credit that arrived as a deposit would be the customer's own money
    locked up until they move out. Both are silent, and both are refused.
    """
    with tenant_ctx(brazos):
        old, new = a_customer_who_moved(dana, brazos)
        deposit_row = models.Payment.objects.filter(
            account_id=old.pk, purpose=models.PURPOSE_DEPOSIT
        ).first()
        credit_row = models.Payment.objects.create(
            tenant_id=deposit_row.tenant_id,
            account=new,
            payment_no="PMT-TEST-0001",
            type=models.PAYMENT_TYPE_ADJUSTMENT,
            amount=THE_DEPOSIT,
            currency=deposit_row.currency,
            status=models.PAYMENT_CLEARED,
            purpose=models.PURPOSE_BILL,
            posted_at=CARRIED_AT,
            cleared_at=CARRIED_AT,
        )
        with pytest.raises(PaymentRuleError, match="ONE movement"):
            ledger_seam.post_account_transfer(
                source_payment=_negated(deposit_row),
                destination_payment=credit_row,
                applied_to_bills=ZERO,
                credit_carried=THE_DEPOSIT,
                held=ZERO,
                entry_date=CARRIED_AT.date(),
                posted_at=CARRIED_AT,
                actor=dana,
            )


def test_cs22__the_seam_refuses_held_money_on_a_credit_transfer(brazos, dana):
    """Money HELD says so on its own row, or 2300 grows a liability the deposit
    register knows nothing about — DEF-177 in a new place."""
    with tenant_ctx(brazos):
        old, new = two_accounts_of_one_customer(dana, brazos)
        row = models.Payment.objects.create(
            tenant_id=old.tenant_id,
            account=new,
            payment_no="PMT-TEST-0002",
            type=models.PAYMENT_TYPE_ADJUSTMENT,
            amount=THE_DEPOSIT,
            currency=new.currency or "USD",
            status=models.PAYMENT_CLEARED,
            purpose=models.PURPOSE_BILL,
            posted_at=CARRIED_AT,
            cleared_at=CARRIED_AT,
        )
        with pytest.raises(PaymentRuleError, match="reported as HELD"):
            ledger_seam.post_account_transfer(
                source_payment=_negated(row),
                destination_payment=row,
                applied_to_bills=ZERO,
                credit_carried=ZERO,
                held=THE_DEPOSIT,
                entry_date=CARRIED_AT.date(),
                posted_at=CARRIED_AT,
                actor=dana,
            )


class _Negated:
    """A stand-in source leg carrying `-amount` and the row's own purpose.

    The seam's guards are what is under test, and building one through the real
    writer would be the writer testing itself. Nothing is written by this class.
    """

    def __init__(self, row):
        self.amount = -row.amount
        self.purpose = row.purpose
        self.payment_no = row.payment_no
        self.account_id = row.account_id
        self.pk = row.pk
        self.currency = row.currency


def _negated(row):
    return _Negated(row)


# ══ CS-8 IS UNCHANGED — the regression this refactor could have caused ═════


def test_cs22__a_credit_transfer_still_holds_nothing(brazos, dana):
    """CS-8's path through the shared writer reports `held 0.00` and allocates.

    The carry-forward landed by moving CS-8's body into a shared core. This
    asserts the credit side did not acquire deposit behaviour on the way — the
    mirror of the trap this file is mostly about.
    """
    with tenant_ctx(brazos):
        old, new = two_accounts_of_one_customer(dana, brazos)
        services.record_payment(
            dana,
            account_id=old.pk,
            amount=Decimal("57.13"),
            posted_at=CARRIED_AT,
            cleared_at=CARRIED_AT,
            method_code="cash",
            idempotency_reference=uuid.uuid4(),
        )
        moved = transfer.transfer_credit_between_accounts(
            dana,
            source_account_id=old.pk,
            destination_account_id=new.pk,
            amount=Decimal("57.13"),
            moved_on=CARRIED_AT,
            reason="offset first",
            idempotency_reference=uuid.uuid4(),
        )
        assert moved.kind == transfer.KIND_CREDIT_TRANSFER
        assert moved.held == ZERO
        assert moved.source_deposit_after == ZERO
        assert moved.destination_deposit_after == ZERO
        assert moved.credit_carried == Decimal("57.13")
        assert _register(old.pk) == ZERO and _register(new.pk) == ZERO


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-059 §8 CS-22 · §6 Q2 (PO 2026-09-01) · task 33 · CS-8 (task 31,
#         the writer this extends) · BR-CUS-024 · BR-CUS-050 · BR-CUS-054 ·
#         BR-CUS-057 · BR-CUS-670 · BR-PAY-012 · BR-PAY-864 · BR-LED-007 ·
#         DEF-177 · apps/payments/transfer.py · apps/payments/ledger_seam.py
# generated: 2026-09-03 by the CR-059 CS-22 deposit carry-forward lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — CR-059 task 34 owns
#            S19 step 4 and S21) F✔ G✔ H=deferred(PO 2026-08-09)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
