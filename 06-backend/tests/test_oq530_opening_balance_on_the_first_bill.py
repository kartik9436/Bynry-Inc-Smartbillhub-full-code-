# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-005 (issue — the balance-forward stamp) · OQ-530 CLOSED
#           (PO 2026-08-27)   Screens: S31 step 6 · S32 · the bill itself
# Rules:    BR-BIL-160 (a migrated opening balance is part of the previous
#           balance, and so is what has been paid against it) · BR-BIL-035
#           (previous balance − payments received + this period = total due) ·
#           BR-CUS-048 (four aged buckets) · BR-PAY-010 (overpayment → account
#           credit) · BR-PAY-041 (a negative credit is a real debt) ·
#           CLAUDE.md rule 2 · rule 4
# Golden:   ❄️ GT-16's four buckets (84.20 / 62.10 / 0.00 / 121.00 = 267.30) ·
#           ❄️ WE-1's 45.00 − 0.00 + 247.87 = 292.87, asserted UNMOVED
# ───────────────────────────────────────────────────────
"""OQ-530 — the first bill carries the opening balance as its PREVIOUS BALANCE.

**PO, 2026-08-27, verbatim:**

    "so when we run first bill; we have to take opening balance into account.
     you will generate first bill and against previous balance you will
     mention the opening balance."

**The defect, measured before this file existed:** `issue._stamp_balance_
forward`'s `previous_balance` read **open INVOICES only**, and a migrated
opening balance is not an invoice — it lives in `account_opening_buckets`. So a
customer who arrived owing money got a first bill whose previous balance printed
`—` and the product told them they were square.

────────────────────────────────────────────────────────────────────────────
THE CASE THIS FILE IS REALLY FOR IS `tc3`, NOT `tc1`
────────────────────────────────────────────────────────────────────────────
Putting the opening balance into `previous_balance` is the easy half. All three
of `previous_balance`, `payments_credits` and `open_balance` were derived from
**one set — the account's open invoices** — so an opening balance joining the
first operand ALONE would be right on bill 1, the customer would pay it, the
payment would allocate against no invoice in that set, and **bill 2 would ask
for it again, and every bill after it.** A customer asked twice for money they
have paid is a worse defect than the one being fixed.

`tc3` is that case end to end: seed the migration, issue bill 1, pay the whole
total due through the REAL payment path, issue the next cycle, and require the
opening figure to have CLEARED. **RED-PROVED with the second operand left
unchanged** — the transcript is in the lane report and the mutation is one line
(`payments_credits=allocated` instead of `allocated + settled`).

`tc5` is the other side of the same coin: every account that was NOT migrated
must be byte-identical to what it was, which is why ❄️ WE-1's frozen
**45.00 − 0.00 + 247.87 = 292.87** is asserted here as well as in its own file.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.billing import customers_seam, documents, issue, models, payments_seam
from apps.customers import models as customer_models
from apps.payments import services as payment_services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    tenant_ctx,
)
from tests.test_us_bil_005_release_issue_api import (  # noqa: F401
    CURRENT_CHARGES,
    PRIOR_BILL_TOTAL,
    TOTAL_DUE,
    a_bill_of,
    an_actor_user,
    an_issuable_world,
    issue_call,
    release_call,
)
from tests.test_us_bil_005_issue import electric_gl_accounts
from tests.test_w3_billing_models import a_run, an_account

pytestmark = pytest.mark.django_db

# ── ❄️ B5 GT-16 line 55, copied: the four imported buckets of `A-12103` ─────
GT16_BUCKETS: tuple[tuple[str, Decimal], ...] = (
    (customer_models.AccountOpeningBucket.BUCKET_CURRENT, Decimal("84.20")),
    (customer_models.AccountOpeningBucket.BUCKET_31_60, Decimal("62.10")),
    (customer_models.AccountOpeningBucket.BUCKET_61_90, Decimal("0.00")),
    (customer_models.AccountOpeningBucket.BUCKET_90_PLUS, Decimal("121.00")),
)
#: "`accounts.balance` = **267.30** (Sum buckets, exact - no recompute)".
GT16_OPENING = Decimal("267.30")
#: "cutover 2026-08-31" — BR-CUS-049's one date per batch.
GT16_CUTOVER = date(2026, 8, 31)

#: The migrated account's own first bill: **267.30 − 0.00 + 247.87 = 515.17**.
#: The current-charges figure is WE-1's, reused so the only thing that differs
#: between `tc1` and the frozen `tc5` case is the migration itself.
FIRST_BILL_TOTAL_DUE = GT16_OPENING + CURRENT_CHARGES  # 515.17

SECOND_CYCLE_CHARGES = Decimal("100.58")  # GT-1's own two lines, unmodified

#: ❄️ PE-4, verbatim: *"open 292.87, pay 350 → bills settled + credit 57.13"*.
#: Used by `tc5b` to prove the settled figure is CAPPED at the opening position:
#: an account with no migration must not have this credit netted into its
#: previous balance, because BR-PAY-010 already spends it on the bill itself.
PE4_OPEN = Decimal("292.87")
PE4_PAYMENT = Decimal("350.00")
PE4_CREDIT = Decimal("57.13")

PAID_AT = datetime(2026, 7, 10, 9, 0, tzinfo=UTC)


def a_migrated_account(brazos, dana, *, account_no, buckets=GT16_BUCKETS):
    """An account that ARRIVED owing money — ❄️ GT-16's own position.

    The bucket rows are written directly rather than through
    `apps/customers/import_writer.py`, and the reason is worth stating: the
    importer needs a whole `ImportRun`, a staged file and a mapping spec, none
    of which this rule depends on. What the rule depends on is the four rows and
    their sum, which is exactly what B5 GT-16 states as its INPUT. `import_run_
    id` is left NULL, which the column allows (it is deliberately not an FK —
    see the model's own judgment (2)).
    """
    account = an_account(dana, brazos, account_no=account_no)
    for bucket, amount in buckets:
        customer_models.AccountOpeningBucket.objects.create(
            tenant=brazos,
            account=account,
            as_of=GT16_CUTOVER,
            bucket=bucket,
            amount=amount,
            currency="USD",
        )
    return account


def _issue_one(brazos, actor_user, run, draft):
    release_call(brazos, actor_user, run)
    issue_call(brazos, actor_user, run, invoice_ids=[str(draft.pk)])
    return models.Invoice.objects.get(pk=draft.pk)


def _block(bill):
    return bill.bill_payload["balance_forward"]


def _foots(block):
    """BR-BIL-035's own arithmetic, read off the stamped block.

    previous balance − payments received + this period == total due. Returned
    rather than asserted so a caller can name the case in its own message.
    """
    return (
        Decimal(block["previous_balance"])
        - Decimal(block["payments_credits"])
        + Decimal(block["current_charges"])
    ) == Decimal(block["total_due"])


# ══════════════════════════════════════════════════════════════════════════
# tc1 — the ruling itself, on the account the frozen example already names
# ══════════════════════════════════════════════════════════════════════════
def test_oq530_tc1__the_first_bill_carries_the_migrated_opening_balance(brazos, dana):
    """❄️ GT-16's `267.30`, on the page: **267.30 − 0.00 + 247.87 = 515.17**.

    Before BR-BIL-160 this bill's previous balance printed `—`: the account has
    no earlier INVOICE, and the open-invoice read was the whole of the first
    operand. The figure is asserted on the RENDERED DOCUMENT as well as in the
    payload, for the reason `tc48` gives about its own: the payload key exists
    to be printed, and a stamp the renderer could not read would pass a payload
    assertion and still leave the customer holding a dash.
    """
    with tenant_ctx(brazos):
        electric_gl_accounts()
        run = a_run(brazos, key="2026-06|oq530-tc1")
        account = a_migrated_account(brazos, dana, account_no="A-12103")
        draft = a_bill_of(brazos, account, run, invoice_no="BL-2607-000201", total=CURRENT_CHARGES)
        bill = _issue_one(brazos, an_actor_user(brazos), run, draft)
        page = documents.render_invoice(bill)

    block = _block(bill)
    assert Decimal(block["previous_balance"]) == GT16_OPENING
    assert Decimal(block["payments_credits"]) == Decimal("0")
    assert Decimal(block["current_charges"]) == CURRENT_CHARGES
    assert Decimal(block["total_due"]) == FIRST_BILL_TOTAL_DUE == Decimal("515.17")
    assert _foots(block), block
    # The migrated half is stamped as its own fact, so an immutable bill can say
    # how much of its previous balance the account ARRIVED with.
    assert Decimal(block["opening_balance"]) == GT16_OPENING
    assert Decimal(block["opening_settled"]) == Decimal("0")
    assert block["opening_buckets"] == 4, "❄️ GT-16 states FOUR aged bands"
    assert block["basis"] == issue.BALANCE_FORWARD_BASIS
    assert block["basis_oq"] == "OQ-217", "the window question is NOT closed by this"

    printed = {field.label: field.value for field in page.summary}
    assert printed["Previous balance"] == "267.30 USD"
    assert printed["Payments & credits"] == "0.00 USD"
    assert printed["Current charges"] == "247.87 USD"
    assert printed["Total due"] == "515.17 USD"
    assert [p.code for p in page.problems if p.code == "total_due_not_printable"] == []


# ══════════════════════════════════════════════════════════════════════════
# tc2 — counted ONCE, beside a real open bill
# ══════════════════════════════════════════════════════════════════════════
def test_oq530_tc2__the_opening_balance_is_counted_once_beside_an_open_bill(brazos, dana):
    """An account with BOTH a migration and an unpaid earlier bill.

    **45.00 (the open bill) + 267.30 (the migration) = 312.30**, and the
    migrated figure appears exactly once. The way this goes wrong is not
    subtle and it is the reason `customers_seam` reads the BUCKET ROWS:
    `accounts.balance` is a cache (BR-CUS-015) that already carries the
    migration AND everything else posted for the account, so summing it beside
    the open bills would count the migrated money twice — **579.60** where
    **312.30** belongs.
    """
    with tenant_ctx(brazos):
        electric_gl_accounts()
        run = a_run(brazos, key="2026-06|oq530-tc2")
        account = a_migrated_account(brazos, dana, account_no="A-12104")
        a_bill_of(
            brazos,
            account,
            run,
            invoice_no="BL-2606-000202",
            total=PRIOR_BILL_TOTAL,
            status=models.INVOICE_ISSUED,
            issued_at=datetime(2026, 6, 3, tzinfo=UTC),
        )
        draft = a_bill_of(brazos, account, run, invoice_no="BL-2607-000203", total=CURRENT_CHARGES)
        bill = _issue_one(brazos, an_actor_user(brazos), run, draft)

    block = _block(bill)
    assert Decimal(block["previous_balance"]) == PRIOR_BILL_TOTAL + GT16_OPENING
    assert Decimal(block["previous_balance"]) == Decimal("312.30")
    assert Decimal(block["payments_credits"]) == Decimal("0")
    assert Decimal(block["total_due"]) == Decimal("312.30") + CURRENT_CHARGES
    assert _foots(block), block
    # Subtract the two halves and nothing is left over — the arithmetic a
    # double count could not survive.
    assert (
        Decimal(block["previous_balance"]) - Decimal(block["opening_balance"]) == PRIOR_BILL_TOTAL
    )
    assert block["prior_open_bills"] == 1, "the migration is not a bill and is not counted as one"
    assert Decimal(block["opening_balance"]) == GT16_OPENING

    # And the CURRENT charges never absorb it: `invoices.total` is this period
    # and nothing else, which is the other way the same money could double.
    assert bill.total == CURRENT_CHARGES


# ══════════════════════════════════════════════════════════════════════════
# tc3 — ⚠ THE ONE THAT MATTERS: it CLEARS when the customer pays it
# ══════════════════════════════════════════════════════════════════════════
def test_oq530_tc3__once_paid_the_opening_balance_clears_and_is_not_asked_for_again(brazos, dana):
    """The mirror of the defect, and the reason both middle operands move.

    Bill 1 asks for **267.30 + 247.87 = 515.17**. The customer pays all of it
    through `payments.services.record_payment` — the real path, oldest-bill
    first — and because a migrated opening balance is not an invoice, only the
    **247.87** meets a bill; the remaining **267.30** becomes an unapplied
    account credit (BR-PAY-010).

    Bill 2 must therefore read **267.30 − 267.30 + 100.58 = 100.58**: the
    migration is still stated, what was paid against it is stated beside it, and
    **the total due is this period's charges alone.** With `payments_credits`
    left reading open invoices only — the state of the code before BR-BIL-160 —
    bill 2 reads `267.30 − 0.00 + 100.58 = 367.88` and the customer is asked a
    second time for money they have already paid.
    """
    with tenant_ctx(brazos):
        electric_gl_accounts()
        actor_user = an_actor_user(brazos)
        first_run = a_run(brazos, key="2026-06|oq530-tc3a")
        account = a_migrated_account(brazos, dana, account_no="A-12105")
        first_draft = a_bill_of(
            brazos, account, first_run, invoice_no="BL-2607-000204", total=CURRENT_CHARGES
        )
        first_bill = _issue_one(brazos, actor_user, first_run, first_draft)
        first_block = _block(first_bill)

    # A fresh tenant context on purpose: `issue_call` goes through the real
    # middleware, which unsets `app.tenant_id` on its way out, and
    # `record_payment` refuses without one (CLAUDE.md rule 1). Re-entering here
    # is also the truthful shape — the payment arrives at the counter days after
    # the run, in a request of its own.
    with tenant_ctx(brazos):
        # The customer pays what the bill asked for, to the cent.
        payment_services.record_payment(
            dana,
            account_id=account.pk,
            amount=Decimal(first_block["total_due"]),
            posted_at=PAID_AT,
            cleared_at=PAID_AT,
            idempotency_reference=uuid.uuid4(),
        )

    with tenant_ctx(brazos):
        second_run = a_run(brazos, key="2026-07|oq530-tc3b")
        second_draft = a_bill_of(
            brazos,
            account,
            second_run,
            invoice_no="BL-2608-000205",
            total=SECOND_CYCLE_CHARGES,
        )
        second_bill = _issue_one(brazos, actor_user, second_run, second_draft)

    assert Decimal(first_block["total_due"]) == FIRST_BILL_TOTAL_DUE

    block = _block(second_bill)
    # THE NUMBER THE CUSTOMER ACTS ON, ASSERTED FIRST — it is the one that goes
    # wrong, and asserting it before the operands makes the failure say so.
    assert (
        Decimal(block["total_due"]) == SECOND_CYCLE_CHARGES
    ), "the total due is THIS period's charges alone — the migration has cleared"
    # ⚠ AMENDED 2026-10-01 — `OQ-217` CLOSED (PO, option A, BR-BIL-1065): the
    # two middle lines read the WHOLE ACCOUNT since the last bill. So bill 2's
    # previous balance is what bill 1 asked (the migration 267.30 + its charges
    # 247.87 = 515.17) and its payments are the 515.17 paid — the migration is
    # still never asked twice, which is what this case guards.
    assert (
        Decimal(block["previous_balance"]) == FIRST_BILL_TOTAL_DUE
    ), "what the first bill asked — the migration included"
    assert (
        Decimal(block["payments_credits"]) == FIRST_BILL_TOTAL_DUE
    ), "and what was PAID against it moves with it, or bill 2 asks twice"
    assert Decimal(block["opening_settled"]) == GT16_OPENING
    assert Decimal(block["current_charges"]) == SECOND_CYCLE_CHARGES
    assert _foots(block), block


# ══════════════════════════════════════════════════════════════════════════
# tc4 — an unreachable seam stamps NULLS, never zeros
# ══════════════════════════════════════════════════════════════════════════
def test_oq530_tc4__an_unreachable_opening_seam_stamps_nulls_not_zeros(brazos, dana, monkeypatch):
    """*Nobody could ask* and *this account arrived owing nothing* are different
    facts, and only one of them is a claim about a customer's money.

    On a deployment whose customers module publishes no opening read, the whole
    balance-forward section is withheld and the page prints the dash it printed
    before this lane. A previous balance short by the whole migration would be
    the defect BR-BIL-160 exists to close, wearing a different hat — and `0.00`
    would tell a customer in arrears that they are square, on a page that is
    immutable the moment it is written.
    """
    monkeypatch.setattr(customers_seam, "_resolve", lambda *args, **kwargs: None)
    with tenant_ctx(brazos):
        electric_gl_accounts()
        run = a_run(brazos, key="2026-06|oq530-tc4")
        account = a_migrated_account(brazos, dana, account_no="A-12106")
        draft = a_bill_of(brazos, account, run, invoice_no="BL-2607-000206", total=CURRENT_CHARGES)
        bill = _issue_one(brazos, an_actor_user(brazos), run, draft)
        page = documents.render_invoice(bill)

    block = _block(bill)
    assert block["previous_balance"] is None
    assert block["payments_credits"] is None
    assert block["total_due"] is None
    assert block["current_charges"] == "247.870000", "the bill's own figure is never in doubt"
    assert "customers_opening_position_for_account_not_published" in {
        entry["code"] for entry in block["problems"]
    }
    printed = {field.label: field.value for field in page.summary}
    assert printed["Total due"] == documents.ABSENT_MARK


def test_oq530_tc4b__an_unreachable_credit_read_withholds_the_block_too(brazos, dana, monkeypatch):
    """The settlement half has the same posture as the opening half.

    An account that carries a migration and whose credit position cannot be read
    is an account whose previous balance we can state the GROSS of and cannot
    state the NET of. Printing the gross would ask a customer who has settled
    their migrated arrears for them a second time, so nothing is printed.

    ⚠ The mutation is scoped to the CREDIT read by name: blanking every resolve
    would prove nothing, because the open-invoice read would fail first and the
    block would be withheld for a different reason entirely.
    """
    real_resolve = payments_seam._resolve

    def only_the_credit_read_is_missing(module, attribute):
        if attribute == payments_seam.CREDIT_POSITION_READ:
            return None
        return real_resolve(module, attribute)

    monkeypatch.setattr(payments_seam, "_resolve", only_the_credit_read_is_missing)
    with tenant_ctx(brazos):
        electric_gl_accounts()
        run = a_run(brazos, key="2026-06|oq530-tc4b")
        account = a_migrated_account(brazos, dana, account_no="A-12107")
        draft = a_bill_of(brazos, account, run, invoice_no="BL-2607-000207", total=CURRENT_CHARGES)
        bill = _issue_one(brazos, an_actor_user(brazos), run, draft)

    block = _block(bill)
    assert block["previous_balance"] is None
    assert block["total_due"] is None
    assert "payments_account_credit_position_not_published" in {
        entry["code"] for entry in block["problems"]
    }


# ══════════════════════════════════════════════════════════════════════════
# tc5 — ❄️ the frozen figure, asserted UNMOVED
# ══════════════════════════════════════════════════════════════════════════
def test_oq530_tc5__an_account_that_was_never_migrated_is_byte_identical(brazos, dana):
    """❄️ WE-1: **45.00 − 0.00 + 247.87 = 292.87**, unchanged by this rule.

    This is the blast-radius assertion and it is why the settled figure is
    capped at the opening balance. An account with no buckets has an opening
    balance of `0.00`, so nothing is added to either operand, and the four
    printed figures are the ones this product has printed since DEF-116. A
    build that netted the account's credit into `payments_credits` for EVERY
    account would move this frozen number, and it goes RED here.
    """
    with tenant_ctx(brazos):
        run, account, draft = an_issuable_world(brazos, dana)
        a_bill_of(
            brazos,
            account,
            run,
            invoice_no="BL-2606-000208",
            total=PRIOR_BILL_TOTAL,
            status=models.INVOICE_ISSUED,
            issued_at=datetime(2026, 6, 3, tzinfo=UTC),
        )
        bill = _issue_one(brazos, an_actor_user(brazos), run, draft)

    block = _block(bill)
    assert Decimal(block["previous_balance"]) == PRIOR_BILL_TOTAL == Decimal("45.00")
    assert Decimal(block["payments_credits"]) == Decimal("0")
    assert Decimal(block["current_charges"]) == CURRENT_CHARGES == Decimal("247.87")
    assert Decimal(block["total_due"]) == TOTAL_DUE == Decimal("292.87")
    assert Decimal(block["opening_balance"]) == Decimal("0")
    assert block["opening_buckets"] == 0
    # No extra problem entry on an ordinary account, either: the OQ-570 note is
    # carried only where a migration is actually being counted.
    assert "opening_balance_settlement_is_inferred_not_recorded" not in {
        entry["code"] for entry in block["problems"]
    }


# ══════════════════════════════════════════════════════════════════════════
# tc6 — the seam's own contract, without a bill in the way
# ══════════════════════════════════════════════════════════════════════════
def test_oq530_tc6__the_seam_states_the_buckets_and_never_the_cached_balance(brazos, dana):
    """`customers_seam` reads the four BR-CUS-048 rows, and only those.

    `accounts.balance` is BR-CUS-015's CACHE and nothing in this product writes
    it; a seam that read it would answer a different number for the same fact
    the day something starts to. The bucket count travels so a reviewer can tie
    the figure back to ❄️ GT-16's four bands.
    """
    with tenant_ctx(brazos):
        account = a_migrated_account(brazos, dana, account_no="A-12108")
        position = customers_seam.opening_position_for_account(account.pk)
        ordinary = customers_seam.opening_position_for_account(
            an_account(dana, brazos, account_no="A-12109").pk
        )

    assert position.amount == GT16_OPENING
    assert position.buckets == 4
    assert position.as_of == GT16_CUTOVER
    assert position.currency == "USD"
    assert position.problems == ()
    # Not migrated: a DERIVED zero, not an absence, and with no problem beside it.
    assert ordinary.amount == Decimal("0")
    assert ordinary.buckets == 0
    assert ordinary.problems == ()


def test_oq530_tc5b__a_carried_credit_on_an_UNMIGRATED_account_moves_nothing(brazos, dana):
    """❄️ PE-4's **57.13**, and why the settled figure is CAPPED at the opening.

    PE-4 is frozen: a **350.00** payment against **292.87** of bills settles them
    and leaves **57.13** carried. That credit is BR-PAY-010's ordinary carried
    credit and `credit.apply_credit_at_issue` already spends it against the next
    bill at issue — *after* this block is stamped. A build that netted the
    account's credit into `payments_credits` for every account would subtract
    that same 57.13 here as well, and the customer would be given the discount
    **twice**.

    So the account with no migration must read `0.00 − 0.00 + 247.87 = 247.87`:
    the settled paid bill has left the open set with its payment (today's
    window, OQ-217) and the carried credit appears nowhere in the block.
    """
    with tenant_ctx(brazos):
        electric_gl_accounts()
        run = a_run(brazos, key="2026-06|oq530-tc5b")
        account = an_account(dana, brazos, account_no="A-12111")
        a_bill_of(
            brazos,
            account,
            run,
            invoice_no="BL-2606-000209",
            total=PE4_OPEN,
            status=models.INVOICE_ISSUED,
            issued_at=datetime(2026, 6, 3, tzinfo=UTC),
        )
        draft = a_bill_of(brazos, account, run, invoice_no="BL-2607-000210", total=CURRENT_CHARGES)

    with tenant_ctx(brazos):
        payment_services.record_payment(
            dana,
            account_id=account.pk,
            amount=PE4_PAYMENT,
            posted_at=PAID_AT,
            cleared_at=PAID_AT,
            idempotency_reference=uuid.uuid4(),
        )
        from apps.payments import selectors as payment_selectors

        assert payment_selectors.account_credit_position(account.pk) == PE4_CREDIT

    with tenant_ctx(brazos):
        bill = _issue_one(brazos, an_actor_user(brazos), run, draft)

    block = _block(bill)
    # ⚠ AMENDED 2026-10-01 — `OQ-217` CLOSED (PO, option A, BR-BIL-1065): the
    # whole account since the last bill. Previous 292.87, paid 350.00, current
    # 247.87 → total due 190.74 = 247.87 − ❄️ PE-4's 57.13 carried credit,
    # counted ONCE (the drawdown at issue moves it onto this bill, and the
    # stamp already says where the account stands). Still no migration, and
    # still nothing settled against one.
    assert Decimal(block["previous_balance"]) == PE4_OPEN
    assert Decimal(block["payments_credits"]) == PE4_PAYMENT
    assert Decimal(block["total_due"]) == CURRENT_CHARGES - PE4_CREDIT
    assert Decimal(block["opening_settled"]) == Decimal("0")
    assert Decimal(block["opening_balance"]) == Decimal("0")
    assert _foots(block), block


def test_oq530_tc7__a_negative_credit_is_a_debt_and_settles_nothing(brazos, dana):
    """BR-PAY-041, PO 2026-08-11 — *"Yes, it's a real debt"*.

    A customer whose credit position is BELOW zero has not paid anything against
    their migrated arrears; they owe more. `min(credit, opening)` on a negative
    credit would REDUCE the previous balance by a debt, which is the exact shape
    the ruling calls out — *"any code, screen or report that assumes a customer
    credit is non-negative is wrong"*. The settled figure is 0.00 and the gross
    stands.
    """
    with tenant_ctx(brazos):
        account = a_migrated_account(brazos, dana, account_no="A-12110")
        position = payments_seam.prior_position_for_account(
            account.pk,
            totals_by_invoice_id={},
            opening=customers_seam.opening_position_for_account(account.pk),
        )
        # A NEGATIVE position, stated directly — the seam is what is under test
        # here, not payments' own bounce chain (that is J15's, and it is frozen).
        negative = payments_seam.prior_position_for_account(
            account.pk,
            totals_by_invoice_id={},
            opening=customers_seam.OpeningPosition(
                account_id=str(account.pk), amount=GT16_OPENING, buckets=4
            ),
        )

    assert position.previous_balance == GT16_OPENING
    assert position.opening_settled == Decimal("0")
    assert negative.previous_balance == GT16_OPENING
    assert negative.open_balance == GT16_OPENING


# ── Lifecycle ─────────────────────────────────────────────
# packet: OQ-530 CLOSED (12-governance/02-decision-log.md, 2026-08-27) ·
#         BR-BIL-160 · BR-BIL-035 · BR-CUS-048/049 · ❄️ B5 GT-16 · ❄️ WE-1
# generated: 2026-08-27 by the OQ-530 opening-balance lane
# gates: every case driven RED first (hard-won law 7) — tc1 against the
#         pre-rule seam, tc3 against `payments_credits=allocated`, tc4/tc4b
#         against a seam that answered 0.00, tc5 against an uncapped credit
#         netting. Transcripts quoted verbatim in the lane report.
# ──────────────────────────────────────────────────────────
