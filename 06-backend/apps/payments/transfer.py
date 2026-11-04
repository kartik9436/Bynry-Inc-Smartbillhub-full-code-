# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 · CS-8 — "Move money between two accounts of one customer:
#           build it ONCE; four things land on it". The CR's own words: *"The
#           product computes both figures and moves nothing, so a refund is
#           refused rather than offset."* · CR-059 · CS-32 — "Move a payment to
#           the account it belonged to".
# Story:    US-PAY-011 (the refund path this unblocks) · US-PAY-010 (the staff
#           reversal CS-32's source leg is)
#           Screens: S21 (a Transfer action; both accounts showing the move AS a
#           move) · S58 (the offset-first step) · S35 (the Move modal)
# Rules:    BR-PAY-864 (NEW — a transfer between two accounts of one customer is
#           ONE balanced movement recorded on both, never a refund on one plus a
#           payment on the other) · BR-PAY-865 (a moved payment is a reversal
#           plus a linked new payment, sharing the original's dates) ·
#           BR-PAY-866 (the destination re-allocates under its own rules) ·
#           BR-PAY-867 (a move is refused while the batch is reconciled) ·
#           OQ-135 CLOSED 2026-08-12 (*"offset first"*) · BR-CUS-054 (the
#           CUSTOMER entity is what makes "another account" mean anything) ·
#           BR-PAY-021 (both dates, always) · BR-PAY-1070 (a reversal is
#           Admin-only and the gate is on the SERVICE) · CLAUDE.md hard rule 1
#           (tenant scoping) · rule 2 (money is a Decimal, 4 dp written) ·
#           rule 4 (a correction is NEW ROWS) · rule 5 (only the ledger posting
#           service writes journal lines) · rule 6 (idempotency) · rule 7
#           (every money action writes `audit_log`)
# Ruling:   PO 2026-08-12 (OQ-135) — *"offset first"*, and the decision-log row
#           of the same day: *"the refund REFUSES and the offset is applied as a
#           balance transfer — one reviewed writer"*. THIS IS THAT WRITER.
# Tests:    06-backend/tests/test_cr059_cs8_transfer.py ·
#           06-backend/tests/test_cr059_cs32_move_payment.py
# Impacts:  apps/payments/ledger_seam.post_account_transfer (NEW — the one new
#           balanced pair) · apps/payments/models.Payment.moved_from_payment
#           (payments/0017) · apps/payments/reversal.reverse_payment (CS-32's
#           source leg calls it; unchanged) · apps/payments/services.
#           record_payment (CS-32's destination leg calls it; unchanged)
# ───────────────────────────────────────────────────────
"""Money crossing two accounts — **the ONE writer, as CS-8 asks for it**.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this module moves money between two
financial records and hands the ledger a balanced pair, so it is enrolled under
the CLAUDE.md 🔒 sensitive-path protocol. AI-authored 2026-09-03 under the PO
ruling of 2026-08-09 (*"AI will do it; we will review it later as human"*).

════════════════════════════════════════════════════════════════════════════
WHY THIS IS ONE MODULE AND NOT TWO
════════════════════════════════════════════════════════════════════════════
CS-8 is flagged in CR-059 §0d.1 as **the keystone: four specs wait on it and it
has nothing today** — CS-20's closing excess, CS-22's deposit carry-forward,
CS-28's landlord residue and CS-32's payment move. CS-32 says the same thing
from its own side: *"It shares CS-8's transfer mechanics; build the two together
or the second will be a near-copy of the first."* So they are here together.

**THEY ARE NOT THE SAME MOVEMENT, AND THE DIFFERENCE IS THE WHOLE FILE.**

    transfer_credit_between_accounts   CS-8. The customer's own CREDIT moves
                                       from one of their accounts to another.
                                       Two NEW payment rows and ONE new balanced
                                       entry: DR customer credit (source) /
                                       CR receivables + credit (destination).

    carry_deposit_forward              CS-22. SECURITY THE UTILITY HOLDS moves
                                       from a closed account to the customer's
                                       new one. The SAME two rows and the SAME
                                       one entry — DR 2300 (source) / CR 2300
                                       (destination) — plus the customer deposit
                                       register moving with it. It meets no bill
                                       and becomes credit nowhere.

    move_payment_to_account            CS-32. A payment was recorded on the
                                       WRONG account. The source leg is a
                                       REVERSAL of the original and the
                                       destination leg is an ordinary recording
                                       — two entries the ledger already knows
                                       how to write, and this module writes
                                       neither of them itself.

════════════════════════════════════════════════════════════════════════════
CS-8 IS CUSTOMER-SCOPED · CS-32 IS NOT, AND THAT IS DELIBERATE
════════════════════════════════════════════════════════════════════════════
CS-8's rule names the boundary: *"A transfer between two accounts of the same
customer"*. OQ-135's own option (b) records why — *"moving money between
accounts unasked can be unlawful where the account holders differ"* — so this
function refuses two accounts it cannot prove belong to one customer.

**CS-32 has no such boundary and must not be given one.** Its case is *"Two
accounts named Patel, adjacent unit numbers, one cheque"*: the money was NEVER
the source account's, and the two Patels may be two entirely different people.
Requiring one customer would refuse the exact clerical error the change exists
to repair. What guards a move instead is what CS-32 asks for — a **required
reason**, an audit row on both legs, both accounts showing it AS a move, and the
reconciled-batch refusal. Recorded in `12-governance/02-decision-log.md`
2026-09-03 rather than left for a reader to infer from two signatures.

════════════════════════════════════════════════════════════════════════════
THE OFFSET IS NEVER AUTOMATIC — CS-8's ONE OPEN JUDGMENT, DECIDED HERE
════════════════════════════════════════════════════════════════════════════
CS-8: *"Needs a ruling — OURS to decide and write down, not to ask. Whether the
offset may apply automatically when a refund is raised, or always needs a person
to confirm it."*

**DECIDED: A TRANSFER IS ALWAYS AN EXPLICIT ACT.** `refunds.request_refund`
keeps refusing and naming the arrear; nothing in this module is called by it.
Three reasons, in the order they weighed:

  1. **OQ-135's own risk analysis says so.** The option the PO was shown as
     *"block and offset automatically"* carried the sentence *"moving money
     between accounts unasked can be unlawful where the account holders
     differ"*. The PO ruled *"offset first"* — which settles the ORDER (the
     debt is met before any cheque goes out), not that the product may move a
     joint holder's money with nobody looking.
  2. **The figure that triggers it is a CACHE.** `arrears_on_other_accounts`
     reads `accounts.balance` (BR-CUS-015), and the decision log of 2026-08-12
     already draws this line in these words: it is *"good enough to stop a
     payout, not good enough to subtract from one"*. An automatic transfer would
     subtract from it.
  3. **It is reversible only by another transfer.** Hard rule 4 makes both legs
     immutable the instant they commit, so an offset applied to the wrong
     sibling is repaired by a second movement and never by an undo.

Worked, on the repo fixture: **57.13** credit on `ACC-1042`, **948.20** overdue
91 days on a sibling with a final notice already sent. A clerk opens S58, sees
both figures, presses Transfer, and 57.13 meets the sibling's oldest bill — the
sibling stands at **891.07** and **no cheque goes out**. Nothing happens without
that press.

════════════════════════════════════════════════════════════════════════════
WHAT THE BOOKS SEE — RULE 5, AND THE ARITHMETIC STATED SO IT CAN BE CHECKED
════════════════════════════════════════════════════════════════════════════
`ledger_seam.post_account_transfer` composes the pair and `apps.ledger.posting`
writes it. **Nothing here writes a journal line** (CLAUDE.md rule 5).

    DR  2400 customer credit          57.13   dimension: SOURCE account
    CR  1200 accounts receivable      57.13   dimension: DESTINATION account

and when the destination cannot absorb it all, the remainder is the second
credit leg:

    DR  2400 customer credit         100.00   dimension: SOURCE account
    CR  1200 accounts receivable      57.13   dimension: DESTINATION account
    CR  2400 customer credit          42.87   dimension: DESTINATION account

**Receivables net to zero across the pair only when the destination absorbs the
whole transfer**, which is what `CS-32`'s proof asks for on the MOVE path and
what a *credit* transfer deliberately does not promise: a credit that meets no
bill has not touched receivables at all. Both are asserted in the tests rather
than described here.

════════════════════════════════════════════════════════════════════════════
WHAT THIS MODULE DOES **NOT** DO
════════════════════════════════════════════════════════════════════════════
* **It does not write `accounts.balance`.** That is customers' cached column and
  payments may not write another module's table (B1 / DB-16). Reported on every
  result, exactly as the refund path reports it.
* ⚠ **THIS BULLET SAID *"It does not carry a deposit across"* UNTIL 2026-09-03
  AND IT IS NOW FALSE — CORRECTED RATHER THAN LEFT TO ROT (hard-won law 1).**
  It read: *"A `deposit` purpose payment is money the utility HOLDS (US-PAY-002
  TC-1) and is not credit; CS-22's carry-forward is a different change that will
  call this writer with its own purpose."* **That is exactly what CS-22 then
  did.** `carry_deposit_forward` is the door, `_transfer_between_accounts` is
  the one writer both go through, and the deposit's legs are **DR 2300 (source)
  / CR 2300 (destination)** with the destination's receivables untouched. The
  sentence that mattered in the old bullet is still true and is the reason the
  two paths differ at all: **a deposit is not credit**, so it meets no bill,
  becomes credit nowhere, and moves the customer deposit register with it.
* **It does not decide the destination's allocation.** BR-PAY-866: *"the
  destination re-allocates under its own rules"*, so the money walks that
  account's own open bills in that tenant's own order — which may land it on
  entirely different bills, *"and that is correct and must be shown before
  confirming"*. `preview_credit_transfer` is what the screen shows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from importlib import import_module
from typing import Any

from django.db import transaction

from core import audit as core_audit
from core import errors
from core import numbering
from core import permissions
from core import tenancy as core_tenancy

from apps.payments import billing_seam, idempotency, ledger_seam, models
from apps.payments.allocation import AllocationClassNotConfigured, allocate_payment
from apps.payments.exceptions import PaymentRuleError

ZERO = Decimal("0")

#: The audit actions, in the `<entity>.<verb>` shape B12 §6a and every other
#: money path in this module use. Two codes rather than one, because a screen
#: filtering the trail for *"where did this account's credit go"* must not have
#: to read a payload to tell a credit transfer from a mis-keyed payment.
AUDIT_TRANSFERRED = "payment.transferred"
AUDIT_MOVED = "payment.moved"
#: CR-059 CS-22 — the deposit carry-forward's own action, for the same reason
#: the two above are two codes rather than one. A clerk asking *"where did this
#: customer's SECURITY go"* is asking a different question from *"where did
#: their credit go"*, and the answers must be separable without reading a
#: payload: one is money the utility owes back, the other is money it holds
#: against bills the customer has already had.
AUDIT_DEPOSIT_CARRIED = "payment.deposit_carried"

#: The three `TransferredMoney.kind` values, named once so a screen and a test
#: cannot disagree about the spelling.
KIND_CREDIT_TRANSFER = "credit_transfer"
KIND_DEPOSIT_CARRY_FORWARD = "deposit_carry_forward"
KIND_PAYMENT_MOVE = "payment_move"

#: The customers writer that keeps `accounts.deposit_on_file` in step with the
#: 2300 liability — resolved BY NAME at call time, never imported, because
#: `accounts` is CUSTOMERS' table and payments may not write another module's
#: (B1 / DB-16). The same seam `services._move_deposit_register` and
#: `reversal._release_deposit` already use, named here so the contract is
#: greppable from both sides of the boundary (BR-TEN-013).
DEPOSIT_REGISTER_WRITE = "record_deposit_movement"

#: The reversal reason a MOVE uses on its source leg. It is one of the four
#: `models.REVERSAL_REASONS` and it is the right one by name: a payment recorded
#: on the wrong account is a data-entry error, not a bounce. Choosing `nsf` here
#: would count an NSF against a customer who did nothing wrong and could move
#: them to cash-only — `reversal.py` draws that boundary in its own words and
#: this constant is what keeps a move on the correct side of it.
MOVE_REVERSAL_REASON = models.REVERSAL_REASON_DATA_ENTRY_ERROR

#: What EVERY cross-account movement leaves undone, carried on every result —
#: the discipline `services.RECORD_UNAVAILABLE` and `reversal.REVERSE_UNAVAILABLE`
#: already keep. A caller must not have to infer an absence.
TRANSFER_UNAVAILABLE: tuple[dict[str, Any], ...] = (
    {
        "code": "account_balance_cache_not_updated",
        "br_ref": "BR-CUS-015",
        "detail": "`accounts.balance` is customers' CACHED column and payments may not write "
        "another module's table (B1 / DB-16). Both accounts' cached balances are now behind "
        "the books by the amount moved until customers recomputes them; the LEDGER is right "
        "either way, and every figure this result states came from it.",
    },
)

#: CS-22's own version, because the sentence above would be FALSE on a carry and
#: a wrong absence is worse than none (hard-won law 1).
#:
#: `TRANSFER_UNAVAILABLE` states that both cached balances *"are now behind the
#: books by the amount moved"*. That is true of a CREDIT transfer, which settles
#: the destination's receivable. **A carried deposit settles nothing** — it meets
#: no bill and becomes credit nowhere — so nothing it did should move a
#: receivables cache at all, and telling a screen otherwise would send a clerk
#: looking for a discrepancy that does not exist.
#:
#: ⚠ **AND THE DEPOSIT REGISTER IS NOT AMONG THE THINGS THIS WARNS ABOUT.**
#: `accounts.deposit_on_file` **was** moved, on both accounts, through customers'
#: own published writer (`record_deposit_movement`) inside this transaction —
#: `source_deposit_after` and `destination_deposit_after` on the result are what
#: each now holds, and BR-LED-007's tie-out compares exactly those two figures
#: against the 2300 liability. Saying so here is what stops the next reader
#: assuming the register lagged the books the way DEF-177's did.
DEPOSIT_CARRY_UNAVAILABLE: tuple[dict[str, Any], ...] = (
    {
        "code": "account_balance_cache_not_recomputed",
        "br_ref": "BR-CUS-015 · BR-CUS-670",
        "detail": "`accounts.balance` is customers' CACHED receivables column and payments may "
        "not write another module's table (B1 / DB-16). A carried deposit meets no bill, so "
        "nothing this movement did should change it; it is named here only because this module "
        "cannot state what that cache holds, never because it is known to be wrong. The DEPOSIT "
        "REGISTER is a different column and it WAS moved on both accounts, through customers' "
        "own writer and inside this transaction — `source_deposit_after` and "
        "`destination_deposit_after` are what each account now holds, and BR-LED-007's tie-out "
        "compares those against the 2300 deposit liability.",
    },
)

#: The seam that answers *"do these two accounts belong to one customer?"*.
#: Resolved BY NAME at call time, never imported: `customer_accounts` is
#: customers' N:M link (BR-CUS-054) and payments carries no import edge into
#: that module — the same shape `refunds.offset_before_refund` uses for
#: `arrears_on_other_accounts` and `reversal._record_nsf` uses for `record_nsf`.
CUSTOMER_FOR_ACCOUNT_READ = "customer_for_account"
CUSTOMER_ACCOUNT_IDS_READ = "customer_account_ids"


@dataclass(frozen=True)
class TransferredMoney:
    """One cross-account movement — and, on `problems`, what it could not do.

    The same result shape for both paths on purpose: a screen that renders a
    credit transfer and a payment move differently is a screen with two ways to
    be wrong about one fact. `kind` is what tells them apart.
    """

    kind: str
    source_account_id: str
    destination_account_id: str
    #: The row that took the money OFF the source account. For a credit transfer
    #: this is a new negative payment; for a move it is the REVERSAL of the
    #: original, and `moved_payment_id` below names the original itself.
    source_payment_id: str
    source_payment_no: str | None
    destination_payment_id: str
    destination_payment_no: str | None
    amount: Decimal
    currency: str
    created: bool = True
    #: CS-32 only: the payment the customer was actually given a number for.
    moved_payment_id: str | None = None
    moved_payment_no: str | None = None
    #: What the money met on the DESTINATION, bill by bill, and what carried.
    applied: Decimal = ZERO
    credit_carried: Decimal = ZERO
    allocations: tuple[dict[str, Any], ...] = ()
    #: What re-opened on the SOURCE (CS-32 only — a credit transfer re-opens
    #: nothing, because credit met no bill).
    reopened: tuple[dict[str, Any], ...] = ()
    #: Signed, and either may be below zero — PO 2026-08-11, *"Yes, it's a real
    #: debt"*. Stated so a caller asserts rather than recomputes.
    source_credit_after: Decimal = ZERO
    destination_credit_after: Decimal = ZERO
    #: CS-22 only: what ARRIVED as held security rather than as spendable money.
    #: Zero on a credit transfer and on a move, and that is a fact rather than a
    #: default — those two movements hold nothing back.
    held: Decimal = ZERO
    #: CS-22 only: the deposit REGISTER on both accounts once the carry landed —
    #: the customers-side figure, not the ledger's. Stated on the result because
    #: BR-LED-007's tie-out compares exactly these two numbers against 2300, and
    #: a caller that had to go and read them again could read them at a moment
    #: when a sibling transaction had moved one.
    source_deposit_after: Decimal = ZERO
    destination_deposit_after: Decimal = ZERO
    journal_entry_id: str | None = None
    posting_key: str | None = None
    problems: tuple[dict[str, Any], ...] = field(default=TRANSFER_UNAVAILABLE)


# ══════════════════════════════════════════════════════════════════════════
# the small readers — every one of them refuses rather than assuming
# ══════════════════════════════════════════════════════════════════════════


def _tenant_id() -> Any:
    """CLAUDE.md rule 1 — nothing touches a tenant table without `app.tenant_id`."""
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _resolve(module: str, attribute: str, kind: str = "selectors") -> Any:
    """A published function of another module, BY NAME, or None."""
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - the app package always imports
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


def _amount(value: Any) -> Decimal:
    """A movement amount — a Decimal, above zero (CLAUDE.md rule 2)."""
    if isinstance(value, float):
        raise PaymentRuleError(
            f"the amount {value!r} is a float. Money is NUMERIC(18,6) and never binary "
            "(CLAUDE.md rule 2) — refused rather than converted, because a conversion hides "
            "the place where money stopped being exact.",
            br_ref="BR-PAY-002",
        )
    if not isinstance(value, Decimal):
        raise PaymentRuleError(f"the amount {value!r} is not a Decimal.", br_ref="BR-PAY-002")
    if value <= ZERO:
        raise PaymentRuleError(
            f"a transfer of {value} moves nothing. A movement has a positive amount and a "
            "DIRECTION — reversing the direction is a transfer the other way, never a negative "
            "one, or the same movement would have two spellings and the books two shapes.",
            br_ref="BR-PAY-002",
        )
    return value


def _account(tenant_id: Any, account_id: Any, *, side: str) -> Any:
    """This tenant's account, or a refusal naming which side of the move it is."""
    read = _resolve("customers", "account_queryset")
    if read is None:  # pragma: no cover - customers always publishes it
        raise PaymentRuleError(
            "apps.customers.selectors.account_queryset is not published, so this process "
            "cannot see accounts at all and cannot move money between two of them.",
            br_ref="BR-CUS-054",
        )
    account = read().filter(tenant_id=tenant_id, pk=account_id).first()
    if account is None:
        raise PaymentRuleError(
            f"the {side} account {account_id} is not this tenant's. Nothing was moved.",
            br_ref="BR-TEN-003",
        )
    return account


def _refuse_same_account(source: Any, destination: Any) -> None:
    if str(source.pk) == str(destination.pk):
        raise PaymentRuleError(
            "the source and the destination are the same account. A transfer to itself would "
            "write two rows that cancel, an entry that moves nothing, and a history a clerk "
            "would have to explain; re-allocating money WITHIN one account is a reapply "
            "(BR-PAY-031), which is a different door.",
            br_ref="BR-PAY-864",
        )


def _refuse_unless_one_customer(source: Any, destination: Any) -> None:
    """CS-8's boundary — BR-CUS-054's customer entity, or a REFUSAL.

    ⚠ **AN UNWIRED SEAM REFUSES; IT NEVER ANSWERS "yes".** A module that cannot
    see who holds an account cannot prove two accounts share a holder, and
    moving money on that basis is precisely what OQ-135's option (b) warns
    against. So a missing read is a refusal that names the read.

    **IT IS ASKED FROM BOTH SIDES, AND THAT IS NOT BELT-AND-BRACES.**
    `customer_for_account` answers the EARLIEST link by `created_at` — its own
    docstring says so — and BR-CUS-054's link is N:M, so a jointly-held account
    has holders it does not name. Two accounts sharing a holder who happens to
    be first on neither would be refused by a one-sided check. Asking from both
    ends catches every case where the shared holder is first on EITHER account,
    which is every joint holding this product can currently produce.

    ⚠ **WHAT IS STILL NOT COVERED, SAID PLAINLY (hard-won law 1):** two accounts
    whose only shared holder is first on neither. That needs a customers-side
    read of the form `sibling_account_ids(account_id)` — the same walk
    `selectors.arrears_on_other_accounts` and `move_out_settlement.
    _sibling_positions` already do privately, twice, published neither time.
    This lane may not add it (customers is another module's table and another
    lane's scope), so it is REPORTED here and in the lane's decision-log row.
    The failure mode is a lawful transfer REFUSED, never an unlawful one
    allowed, which is the safe direction of the unknown.
    """
    holder = _resolve("customers", CUSTOMER_FOR_ACCOUNT_READ)
    accounts_of = _resolve("customers", CUSTOMER_ACCOUNT_IDS_READ, "service_request_service")
    if holder is None or accounts_of is None:
        raise PaymentRuleError(
            "a transfer moves money between two accounts of ONE customer (CS-8), and "
            f"`apps.customers.selectors.{CUSTOMER_FOR_ACCOUNT_READ}` or "
            f"`apps.customers.service_request_service.{CUSTOMER_ACCOUNT_IDS_READ}` is not "
            "published on this deployment — so this process cannot tell whether these two "
            "accounts share a holder. Refused rather than assumed: the PO was shown, and "
            "declined, an automatic offset precisely because moving money between accounts "
            "with different holders can be unlawful (OQ-135).",
            br_ref="BR-CUS-054",
        )
    for one, other in ((source, destination), (destination, source)):
        customer = holder(one.pk)
        if not customer:
            continue
        if str(other.pk) in set(accounts_of(customer.get("id"))):
            return
    raise PaymentRuleError(
        f"accounts {getattr(source, 'account_no', source.pk)} and "
        f"{getattr(destination, 'account_no', destination.pk)} are not held by one customer, so "
        "money may not be transferred between them. A shared surname or address counts for "
        "nothing here (BR-CUS-054): offsetting across those would move money between strangers. "
        "Money genuinely owed to the other account is REFUNDED to whoever paid it, and a "
        "payment recorded against the wrong account is MOVED (CS-32), which is a different "
        "door and needs no customer link.",
        br_ref="BR-CUS-054",
    )


def _credit_position(account_id: Any) -> Decimal:
    """The signed credit position. Imported late to avoid an import cycle."""
    from apps.payments import selectors

    return selectors.account_credit_position(account_id)


def _refuse_unless_the_credit_is_there(account: Any, *, amount: Decimal) -> Decimal:
    """A transfer moves money the account HOLDS — never money it might hold.

    Worked: an account **57.13** in credit cannot transfer **100.00**. Allowing
    it would drive the source's credit position to **−42.87**, which this product
    already means something specific by — *"a real debt"*, PO 2026-08-11,
    OQ-132 — and would invent a receivable from a clerk's typo.
    """
    position = _credit_position(account.pk)
    if position < amount:
        raise PaymentRuleError(
            f"account {getattr(account, 'account_no', account.pk)} holds {position} in credit and "
            f"{amount} was asked for. A transfer moves money the utility is already holding for "
            "this customer; moving more would drive the credit position below zero, which this "
            "product reads as a REAL DEBT (PO 2026-08-11) and would be a receivable invented by "
            "a typo. Nothing was moved.",
            br_ref="BR-PAY-864",
        )
    return position


def _deposit_position(account_id: Any) -> dict[str, Any]:
    """What the utility HOLDS for this account — customers' figure, never ours.

    `purposes.deposit_position` REFUSES when customers publishes no
    `account_detail` rather than answering zero, and that posture is exactly
    what a carry-forward needs: an unreadable deposit position is not an empty
    one, and carrying nothing because nothing could be read would tell a
    returning customer they have no deposit and ask them for a second one.
    """
    from apps.payments import purposes

    return purposes.deposit_position(account_id)


def _refuse_unless_the_deposit_is_there(account: Any, *, expected: Decimal | None) -> Decimal:
    """CS-22 moves the deposit the account HOLDS, and nothing else.

    ⚠ **THE WHOLE PRINCIPAL MOVES AND THE CALLER DOES NOT CHOOSE THE FIGURE.**
    The PO ruled the offer, not a slider: *"the move-in screen says the deposit
    is held on the old account and the clerk accepts it"* (2026-09-01, CR-059
    §6 Q2 (b)). A partial carry is described by no rule, would leave a stub
    liability on a closed account nobody looks at again — which is the very
    thing Q3's option (b) was declined for — and would need a second rule
    saying what happens to the remainder.

    ⚠ **`expected` IS A CONFIRMATION, NOT AN INSTRUCTION, AND IT EXISTS FOR ONE
    REAL CASE.** `customers.discounts.carry_forward_offer` offers the customer's
    POSITION — principal **plus** BR-CUS-057's accrued interest, `$153.50` on
    the repo's own fixture — while what the register and the 2300 liability
    actually hold is the **$150.00** principal. A screen echoing the offered
    figure back at this door must meet a refusal that says so in figures, never
    a silent 150.00 where 153.50 was asked for. **The interest is not lost by
    moving 150.00**: it is a pure function of principal, rate and the ORIGINAL
    receipt date, and the carry moves all three (see `_carry_deposit_register`),
    so the same $3.50 stands on the destination the moment it lands.
    """
    held = _amount_held(account)
    if held <= ZERO:
        raise PaymentRuleError(
            f"account {getattr(account, 'account_no', account.pk)} holds no deposit, so there is "
            "nothing to carry forward. A carry-forward moves security the utility is already "
            "holding; where none is held the move-in collects one under the plan's own deposit "
            "schedule (BR-CUS-023), which is a different door.",
            br_ref="BR-CUS-024",
        )
    if expected is not None and expected != held:
        raise PaymentRuleError(
            f"account {getattr(account, 'account_no', account.pk)} holds {held} and {expected} "
            "was confirmed. The two differ by the deposit INTEREST BR-CUS-057 has accrued: the "
            "offer states the customer's POSITION (principal plus interest) and this movement "
            "carries the PRINCIPAL, which is what the register and the deposit-liability account "
            "actually hold. The interest is carried with it — the original receipt date moves to "
            "the new account, so the same accrual stands there from the day it lands — but it is "
            "not money that can be transferred, because it has never been booked. Confirm the "
            "principal, or carry nothing.",
            br_ref="BR-CUS-057",
        )
    return held


def _amount_held(account: Any) -> Decimal:
    position = _deposit_position(account.pk)
    value = position.get("on_file")
    return value if isinstance(value, Decimal) else Decimal(str(value or "0"))


def _deposit_register_writer() -> Any:
    """`apps.customers.services.record_deposit_movement`, or a REFUSAL.

    ⚠ **AN UNWIRED SEAM REFUSES HERE, AND IT REPORTS EVERYWHERE ELSE.** Both
    postures are right and the difference is what the caller was trying to do.
    `services._move_deposit_register` carries `deposit_register_not_moved` as a
    PROBLEM because the payment it belongs to is real either way — the customer
    handed over money and the books must say so. **A carry-forward has no such
    residue.** Its entire content is *"stop holding this against the old account
    and start holding it against the new one"*, and the register is half of
    where that is recorded. Landing the ledger half alone would leave the closed
    account's register still claiming money the books moved and the new
    account's claiming none — so the returning customer is asked for a second
    deposit, which is the exact thing CS-22 exists to stop, and BR-LED-007's
    tie-out shows two errors that cancel.
    """
    try:
        customers_services = import_module("apps.customers.services")
    except ImportError:  # pragma: no cover — the app package always imports
        customers_services = None
    writer = getattr(customers_services, DEPOSIT_REGISTER_WRITE, None) if customers_services else None
    if not callable(writer):
        raise PaymentRuleError(
            f"`apps.customers.services.{DEPOSIT_REGISTER_WRITE}` is not published on this "
            "deployment, so the customer deposit register cannot be moved and the carry-forward "
            "is REFUSED rather than half-made. `accounts` is customers' table and payments may "
            "not write another module's (B1 / DB-16). Posting the books alone would leave the "
            "closed account's register still claiming money the books have moved and the new "
            "account's claiming none — the returning customer would be asked for a second "
            "deposit, which is the whole of what this change prevents (DEF-177's shape, in a "
            "new place). Nothing was moved.",
            br_ref="BR-CUS-670",
        )
    return writer


def _carry_deposit_register(
    *, source: Any, destination: Any, amount: Decimal, received_on: Any, actor: Any
) -> tuple[Decimal, Decimal]:
    """Release on the old account, receive on the new one — and CARRY THE CLOCK.

    Two calls to ONE published writer, inside the caller's transaction. A
    refusal from customers PROPAGATES and takes the whole carry with it
    (DEF-047): a deposit released from one register and never received on the
    other is money the customer holds nowhere.

    ⚠ **`received_on` IS THE ORIGINAL RECEIPT DATE AND THAT IS THE MOST
    IMPORTANT ARGUMENT IN THIS FILE FOR THE CUSTOMER'S POCKET.** BR-CUS-050
    stamps the date only when the destination has none, and BR-CUS-057 accrues
    interest FROM it. Passing today's date — or passing nothing — would restart
    the interest clock on a customer who has been with the utility for years,
    which `record_deposit_movement`'s own docstring names as *"quietly
    under-paying the customer who has been with the utility longest"*. Worked:
    $150.00 received 14 months ago at 2% has accrued **$3.50**; carried with its
    date, the new account reads **$3.50** on the day it lands and goes on
    accruing. Carried without it, the customer's $3.50 is gone and no report
    anywhere shows a difference.

    ⚠ **THE ORDER IS RELEASE THEN RECEIVE, AND IT IS NOT ARBITRARY.**
    `record_deposit_movement` takes `select_for_update()` on each account and
    REFUSES a release larger than what is held. Releasing first means the guard
    that protects the customer's money runs before anything is credited: a
    concurrent release that emptied the source is met by a refusal rather than
    by a second deposit appearing on the destination.
    """
    writer = _deposit_register_writer()
    out = writer(source.pk, amount, actor=actor, released=True)
    into = writer(destination.pk, amount, actor=actor, received_on=received_on)
    return (
        _as_decimal(getattr(out, "held_after", ZERO)),
        _as_decimal(getattr(into, "held_after", ZERO)),
    )


def _as_decimal(value: Any) -> Decimal:
    """Another module's money figure, never through `float` (CLAUDE.md rule 2)."""
    if isinstance(value, Decimal):
        return value
    return ZERO if value is None else Decimal(str(value))


def _a_date(value: Any) -> date | None:
    """The receipt date, as a `date`, whatever shape the seam handed over.

    ⚠ **`selectors.account_detail` SERIALISES IT — it returns `"2025-07-02"`,
    not a `date`** (`account_detail_dict`, which is a WIRE shape). Django would
    coerce the string on save and the stored value would be right either way,
    but the audit trail and this module's own comparisons would be carrying a
    string that only looks like a date. Converted once, here, so the value that
    crosses into `record_deposit_movement` is the type BR-CUS-050 is about.
    """
    if value is None or isinstance(value, date):
        return None if value is None else value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:  # pragma: no cover - the seam serialises ISO or nothing
        return None


def _refuse_if_batch_reconciled(payment: models.Payment) -> None:
    """BR-PAY-867 — a move is refused while the batch is RECONCILED.

    ⚠ **THIS IS THE OPPOSITE OF `reversal._refuse_if_batch_locked`, AND BOTH ARE
    RIGHT.** The PO closed OQ-134 on 2026-08-12 and a BOUNCE inside a reconciled
    batch is lawful: the batch total stands, the bounce is new rows, and the
    bank's own statement did not change. **A MOVE is not that event.** Nothing
    happened at the bank; we are choosing to say the money was somebody else's,
    and the payment would leave the set of rows the bank agreed a total for. The
    batch is unreconciled first, or the correction waits.

    Worked, on the same fixture the bounce rule uses: **DEP-260805-CHK**, 8
    cheques, **$2,840.00**, reconciled and locked. Cheque #4021's **$100.00** was
    recorded against the wrong Patel. Moving it now would leave the batch
    claiming eight cheques and holding seven — a tie-out that was true yesterday
    and is silently false today, on a record hard rule 4 forbids anyone to edit.

    A payment naming a batch that cannot be READ still refuses, for the reason
    the bounce path gives: an unknown lock state is not a safe one.
    """
    batch_id = getattr(payment, "deposit_batch_id", None)
    if batch_id is None:
        return
    from apps.payments import bankrec_models

    batch = bankrec_models.DepositBatch.objects.filter(
        tenant_id=payment.tenant_id, pk=batch_id
    ).first()
    if batch is None:
        raise PaymentRuleError(
            f"payment {payment.payment_no or payment.pk} names deposit batch {batch_id}, which "
            "does not exist for this tenant. A payment pointing at a missing batch is a broken "
            "reference, and moving it would leave the books referring to it too.",
            br_ref="BR-PAY-004",
        )
    if batch.status == bankrec_models.BATCH_RECONCILED:
        raise PaymentRuleError(
            f"payment {payment.payment_no or payment.pk} sits in deposit batch "
            f"{getattr(batch, 'batch_no', batch_id)}, which has been RECONCILED — the bank has "
            "already agreed that total. Moving the payment now would take it out of a set the "
            "bank tied out, leaving the batch claiming money it no longer holds. Unreconcile the "
            "batch first (S39) and then move it. This is NOT the bounce rule: a returned cheque "
            "inside a reconciled batch IS recorded (PO 2026-08-12, OQ-134), because a bounce is "
            "the bank's own event and a move is ours.",
            br_ref="BR-PAY-867",
        )


def _dates_of(payment: models.Payment) -> tuple[datetime, datetime | None]:
    """BR-PAY-865: *"sharing the original's posting and clearing dates. The dates
    must not be rewritten to today, or the customer becomes late on a bill they
    paid on time."*

    Worked: a cheque posted **5 Jul** against a bill due **6 Jul** is on time
    (BR-PAY-021 — billing reads the POSTING date). Discover the mis-keying on
    **2 Aug**, move it, and a re-dated destination payment makes that customer
    27 days late on a bill they paid a day early — with a late fee and a rung of
    the collection ladder behind it.
    """
    return payment.posted_at, payment.cleared_at


# ══════════════════════════════════════════════════════════════════════════
# CS-8 · the credit transfer — TWO NEW ROWS AND ONE BALANCED ENTRY
# ══════════════════════════════════════════════════════════════════════════


def preview_credit_transfer(
    *, source_account_id: Any, destination_account_id: Any, amount: Decimal
) -> dict[str, Any]:
    """What a transfer WOULD do — computed by the service, never by the screen.

    BR-PAY-866 asks that the destination's re-allocation be *"shown before
    confirming"*, and CS-31's own note says why the composition lives here:
    *"It must be computed by the service, not assembled on the screen, or the
    warning and the outcome can disagree."*

    A GET's worth of work and no writes: the same read may be taken twice by two
    clerks with no consequence.
    """
    tenant_id = _tenant_id()
    amount = _amount(amount)
    source = _account(tenant_id, source_account_id, side="source")
    destination = _account(tenant_id, destination_account_id, side="destination")
    _refuse_same_account(source, destination)
    _refuse_unless_one_customer(source, destination)
    held = _credit_position(source.pk)
    position = billing_seam.open_invoices_for_account(destination.pk)
    outcome = allocate_payment(
        payment_amount=amount,
        open_invoices=position.invoices,
        class_order=_class_order(None),
    )
    return {
        "source_account_id": str(source.pk),
        "destination_account_id": str(destination.pk),
        "amount": str(amount),
        "source_credit_held": str(held),
        "source_credit_after": str(held - amount),
        "transferable": held >= amount,
        "meets": [
            {
                "invoice_number": row.invoice_number,
                "amount": str(row.applied),
            }
            for row in outcome.allocations
        ],
        "credit_carried": str(outcome.credit_carried),
        "problems": [dict(problem) for problem in (TRANSFER_UNAVAILABLE + position.problems)],
    }


def _transfer_between_accounts(
    actor: Any,
    *,
    purpose: str,
    source_account_id: Any,
    destination_account_id: Any,
    amount: Decimal | None,
    moved_on: datetime,
    reason: str,
    memo: str | None = None,
    order: str = "oldest_first",
    targets: tuple[Any, ...] = (),
    class_order: tuple[str, ...] | None = None,
    idempotency_source: str = idempotency.SOURCE_ENTRY,
    idempotency_reference: Any = None,
) -> TransferredMoney:
    """CS-8 — one balanced movement recorded on BOTH accounts. All of it or none.

    ════════════════════════════════════════════════════════════════════════
    ONE WRITER, TWO PURPOSES — CS-8's OWN RULE, AND CS-22 LANDING ON IT
    ════════════════════════════════════════════════════════════════════════
    CS-8 says *"build the transfer ONCE"* and names the four specs that were to
    land on it. **`purpose` is how CS-22 lands, and it is not a flag: it is what
    both payment rows are WRITTEN with**, so every consequence follows from the
    rows rather than from an argument that could be forgotten one layer down.

        `PURPOSE_BILL`      CS-8. The customer's own CREDIT. It meets the
                            destination's open bills under that account's own
                            rules and what it cannot meet becomes credit there.
                            DR 2400 (source) / CR 1200 + 2400 (destination).

        `PURPOSE_DEPOSIT`   CS-22. Security the utility HOLDS and owes back
                            (BR-PAY-012 / US-PAY-002 TC-1). It meets NOTHING,
                            it becomes credit NOWHERE, and the customer deposit
                            register moves with it.
                            DR 2300 (source) / CR 2300 (destination).

    ⚠ **THE ONE MISTAKE THIS SHAPE EXISTS TO PREVENT, WRITTEN OUT BECAUSE IT
    LOOKS LIKE CORRECT CODE.** Calling this writer for a deposit WITHOUT the
    deposit purpose allocates it against the new account's bills. The entry
    balances, the suites stay green, the tie-out foots — and the customer's
    returnable security has been turned into revenue, after which they will be
    asked for a fresh deposit they have already paid. `ledger_seam.
    post_account_transfer` refuses that combination by name as the second
    independent guard.


    One service function = one transaction boundary (B1). Both payment rows, the
    destination's allocations, the ledger entry and both audit rows commit
    together or none of them does. **A transfer that cannot reach the books does
    not happen**: money that left one account and never arrived at the other is
    the state nothing can repair, because both rows are immutable the instant
    they commit.

    `moved_on` is the caller's business day and this function reads no clock
    (BR-TEN-043, gate G6). It is BOTH dates on both new rows: a transfer enters
    the system and completes in the same act — there is no bank in it — so a
    clearing date that differed from the posting date would describe an event
    that never happened.

    `reason` is REQUIRED and free text. Hard rule 7's audit row carries it, and
    the row is the only durable record of WHY the customer's money moved between
    two of their accounts — a question that is asked months later, by a person
    who was not there.

    ⚠ **THE CREDIT IS NOT SPENDABLE TWICE, and the guard is the transaction
    rather than a lock.** `_refuse_unless_the_credit_is_there` reads the position
    INSIDE the atomic block, after the source row would be visible to any
    concurrent reader in the same transaction, so two clerks transferring the
    same 57.13 cannot both pass — the second sees the first's negative row. On
    PostgreSQL under READ COMMITTED the second transaction re-reads at statement
    time and finds it; the test that proves this runs on PostgreSQL and not on
    the SQLite suite, because SQLite serialises writers and cannot show it
    (CLAUDE.md hard-won law 14).

    Raises `PaymentRuleError` for everything a human can act on.
    """
    tenant_id = _tenant_id()
    carries_a_deposit = purpose == models.PURPOSE_DEPOSIT
    if purpose not in (models.PURPOSE_BILL, models.PURPOSE_DEPOSIT):
        raise PaymentRuleError(
            f"{purpose!r} is not a purpose money may cross accounts under. A CREDIT transfer "
            "(CS-8) and a DEPOSIT carry-forward (CS-22) are the two movements any rule "
            "describes; a prepayment or a plan down payment belongs to the account it was taken "
            "on and is not moved by this door.",
            br_ref="BR-PAY-012",
        )
    if not (reason or "").strip():
        raise PaymentRuleError(
            "a transfer needs a reason. Money moving between two of a customer's accounts is "
            "not self-explanatory six months later, and the audit row is the only place the "
            "answer will exist.",
            br_ref="BR-PAY-864",
        )
    # A CREDIT transfer's amount is the caller's and is validated HERE, where
    # CS-8 has always validated it — a float must be refused whatever else is
    # true of the request. A DEPOSIT's amount is a CONFIRMATION and may be
    # absent, so only its type is checked here; the figure itself is resolved
    # below, against what the source actually holds.
    if carries_a_deposit:
        if amount is not None:
            amount = _amount(amount)
    else:
        amount = _amount(amount)
    source = _account(tenant_id, source_account_id, side="source")
    destination = _account(tenant_id, destination_account_id, side="destination")
    _refuse_same_account(source, destination)
    _refuse_unless_one_customer(source, destination)
    currency = _shared_currency(source, destination)
    key = (
        idempotency.inbound_payment_key(source=idempotency_source, reference=idempotency_reference)
        if idempotency_reference is not None
        else None
    )
    replay = _existing_transfer(tenant_id, key)
    if replay is not None:
        return _replayed(replay)
    # ── WHAT MOVES, AND WHO CHOOSES IT ──────────────────────────────────────
    # A CREDIT transfer moves what the caller asked for, up to what is held.
    # A DEPOSIT carry-forward moves the WHOLE principal and the caller may only
    # CONFIRM the figure — see `_refuse_unless_the_deposit_is_there`.
    #
    # ⚠ **THIS SITS BELOW THE REPLAY CHECK AND THAT ORDER IS LOAD-BEARING
    # (found by `test_cs22__a_double_submit_carries_the_deposit_once`).** After
    # a carry has committed, the source holds NOTHING — so resolving the amount
    # first meets *"holds no deposit"* and a move-in wizard submitted twice gets
    # a refusal instead of the movement it already made. Hard rule 6 says the
    # second submit is a no-op, not an error, and a clerk who double-clicked
    # would otherwise be told the deposit had vanished. **A replay must be
    # answered before any check on state the first call already changed.**
    received_on: Any = None
    if carries_a_deposit:
        position = _deposit_position(source.pk)
        received_on = _a_date(position.get("received_on"))
        amount = _amount(_refuse_unless_the_deposit_is_there(source, expected=amount))

    with transaction.atomic():
        if carries_a_deposit:
            # Re-read INSIDE the atomic block for the reason the credit check
            # below is re-read here: two clerks carrying the same deposit
            # forward must not both pass. `record_deposit_movement` takes
            # `select_for_update()` on the source account moments later, so the
            # second transaction blocks there and then meets this refusal.
            #
            # ⚠ **ITS OWN SENTENCE, NOT THE `expected` ONE.** The confirmation
            # refusal above explains a difference of ACCRUED INTEREST, which is
            # the right explanation for a screen echoing `$153.50` back. Here
            # the figure moved for a different reason — a second carry, a
            # bounced deposit, a new one taken at the counter — and reusing
            # that sentence would tell the clerk the cause was interest when it
            # was not. A refusal that names the wrong cause is worse than one
            # that names none.
            still_held = _amount_held(source)
            if still_held != amount:
                raise PaymentRuleError(
                    f"account {getattr(source, 'account_no', source.pk)} held {amount} when this "
                    f"carry was prepared and holds {still_held} now — somebody moved this "
                    "customer's deposit while the form was open. Nothing was moved: re-read the "
                    "position and confirm the figure that is actually there.",
                    br_ref="BR-CUS-670",
                )
        else:
            _refuse_unless_the_credit_is_there(source, amount=amount)
        out_row = models.Payment.objects.create(
            tenant_id=tenant_id,
            account=source,
            payment_no=numbering.next_number(numbering.PAYMENT, moved_on.date()),
            # ⚠ `adjustment`, NOT `payment`. Two things turn on it and both are
            # rules somebody else already wrote: `selectors.payments_totals`
            # excludes non-cash rows from the day's takings — no cash left the
            # drawer here — and `reconciliation.cut_deposit_batches` never
            # sweeps one into a batch, so a transfer cannot make a deposit total
            # un-tieable (CS-35's branch 1, applied to a movement that is not a
            # receipt either).
            type=models.PAYMENT_TYPE_ADJUSTMENT,
            method=None,
            amount=-amount,
            currency=currency,
            status=models.PAYMENT_CLEARED,
            # CS-22: the purpose is WRITTEN, not inferred. `selectors.
            # account_credit_position` excludes deposit-purpose rows by name
            # (US-PAY-002 TC-1), so a carried deposit cannot be read as credit,
            # cannot be spent by `credit.apply_credit_at_issue` on the new
            # account's first bill, and cannot be refunded as though it were
            # the customer's own money to draw on.
            purpose=purpose,
            memo=memo,
            posted_at=moved_on,
            cleared_at=moved_on,
            webhook_key=key,
            # CR-132-BRC07 — a transfer is a CLERK'S act at a screen, so
            # both legs are `entry`. `idempotency_source` is the caller's and
            # defaults to `entry`; it is read rather than hardcoded so a
            # transfer raised by some future automation records as what it was.
            # WRITE-ONCE (hard rule 4), and OBSERVED, so never derived.
            origin=idempotency_source,
            origin_is_derived=False,
        )
        in_row = models.Payment.objects.create(
            tenant_id=tenant_id,
            account=destination,
            payment_no=numbering.next_number(numbering.PAYMENT, moved_on.date()),
            type=models.PAYMENT_TYPE_ADJUSTMENT,
            method=None,
            amount=amount,
            currency=currency,
            status=models.PAYMENT_CLEARED,
            purpose=purpose,
            memo=memo,
            posted_at=moved_on,
            cleared_at=moved_on,
            # CR-132-BRC07 — a transfer is a CLERK'S act at a screen, so
            # both legs are `entry`. `idempotency_source` is the caller's and
            # defaults to `entry`; it is read rather than hardcoded so a
            # transfer raised by some future automation records as what it was.
            # WRITE-ONCE (hard rule 4), and OBSERVED, so never derived.
            origin=idempotency_source,
            origin_is_derived=False,
            # The link CS-32's data note asks for, doing CS-8's job as well: the
            # pair is walkable from either end and no second column was minted.
            moved_from_payment=out_row,
        )
        # ── WHAT THE MONEY DOES WHEN IT ARRIVES ─────────────────────────────
        # BR-PAY-866 for a credit: the destination re-allocates under ITS OWN
        # rules. **A DEPOSIT ALLOCATES NOTHING**, and this branch is the single
        # most important line in the file: `purposes.resolve` already records
        # that a deposit is *"the only purpose for which both are False — the
        # money is held, and held money is neither applied nor credited"*, and
        # a carried deposit that walked the new account's open bills would meet
        # its first bill with the customer's own security.
        held = ZERO
        source_deposit_after = ZERO
        destination_deposit_after = ZERO
        if carries_a_deposit:
            applied, credit_carried, rows = ZERO, ZERO, []
            held = amount
            source_deposit_after, destination_deposit_after = _carry_deposit_register(
                source=source,
                destination=destination,
                amount=amount,
                received_on=received_on,
                actor=actor,
            )
        else:
            applied, credit_carried, rows = _allocate_destination(
                payment=in_row,
                account=destination,
                order=order,
                targets=targets,
                class_order=class_order,
            )
        # ── hard rule 7, INSIDE the transaction, ONCE PER ACCOUNT ───────────
        # Two rows because they are two facts about two entities, and a clerk
        # reading either account's trail must find the movement without knowing
        # to look at the other one. `core.audit` raises rather than losing a
        # row, which takes the transfer with it.
        kind = KIND_DEPOSIT_CARRY_FORWARD if carries_a_deposit else KIND_CREDIT_TRANSFER
        trail = {
            "kind": kind,
            "source_account_id": str(source.pk),
            "destination_account_id": str(destination.pk),
            "source_payment_no": out_row.payment_no,
            "destination_payment_no": in_row.payment_no,
            "amount": str(amount),
            "currency": currency,
            "reason": reason,
            "memo": memo,
            "moved_on": moved_on.isoformat(),
            "applied": str(applied),
            "credit_carried": str(credit_carried),
            # CS-22 — on the trail because the register is the thing an auditor
            # ties against 2300, and because the RECEIPT DATE moving is the
            # part a reader would otherwise have to infer from two accounts.
            "held": str(held),
            "deposit_received_on": (
                received_on.isoformat() if hasattr(received_on, "isoformat") else received_on
            ),
            "source_deposit_after": str(source_deposit_after),
            "destination_deposit_after": str(destination_deposit_after),
            "allocations": [{**row, "amount": str(row["amount"])} for row in rows],
            "idempotency_key": key,
            "job": None if actor is not None else "payments.transfer",
        }
        action = AUDIT_DEPOSIT_CARRIED if carries_a_deposit else AUDIT_TRANSFERRED
        core_audit.money_action(actor, action, "payment", str(out_row.pk), after=trail)
        core_audit.money_action(actor, action, "payment", str(in_row.pk), after=trail)

        posting = ledger_seam.post_account_transfer(
            source_payment=out_row,
            destination_payment=in_row,
            applied_to_bills=applied,
            credit_carried=credit_carried,
            held=held,
            entry_date=moved_on.date(),
            posted_at=moved_on,
            actor=actor,
        )
        # The write-once stamp goes on the DESTINATION row alone, and the source
        # row's stays NULL on purpose. `ledger_seam.reverse_payment_entry`
        # refuses a payment with no `journal_entry_id` by name, so the negative
        # transfer-out row cannot be "bounced" — which is right, because there is
        # no bank behind it and unwinding a transfer is a transfer back. The
        # source row reaches its entry through this pair's audit rows and
        # through `moved_from_payment` on the row that carries the stamp.
        in_row.journal_entry_id = posting.entry_id
        in_row.save(update_fields=["journal_entry_id", "updated_at"])

        return TransferredMoney(
            kind=kind,
            source_account_id=str(source.pk),
            destination_account_id=str(destination.pk),
            source_payment_id=str(out_row.pk),
            source_payment_no=out_row.payment_no,
            destination_payment_id=str(in_row.pk),
            destination_payment_no=in_row.payment_no,
            amount=amount,
            currency=currency,
            applied=applied,
            credit_carried=credit_carried,
            held=held,
            allocations=tuple(rows),
            # ⚠ **BOTH CREDIT POSITIONS ARE UNCHANGED BY A DEPOSIT CARRY, AND
            # THEY ARE STILL REPORTED.** A deposit is not credit and
            # `account_credit_position` excludes it, so these two figures read
            # exactly as they did before the carry. Reporting them anyway is
            # the point: a screen that saw them move would be reading a deposit
            # as spendable money.
            source_credit_after=_credit_position(source.pk),
            destination_credit_after=_credit_position(destination.pk),
            source_deposit_after=source_deposit_after,
            destination_deposit_after=destination_deposit_after,
            journal_entry_id=posting.entry_id,
            posting_key=posting.posting_key,
            problems=DEPOSIT_CARRY_UNAVAILABLE if carries_a_deposit else TRANSFER_UNAVAILABLE,
        )


@permissions.require_role(permissions.SYSTEM_ADMIN, permissions.BILLING_CLERK, br_ref="BR-PAY-864")
def transfer_credit_between_accounts(
    actor: Any,
    *,
    source_account_id: Any,
    destination_account_id: Any,
    amount: Decimal,
    moved_on: datetime,
    reason: str,
    memo: str | None = None,
    order: str = "oldest_first",
    targets: tuple[Any, ...] = (),
    class_order: tuple[str, ...] | None = None,
    idempotency_source: str = idempotency.SOURCE_ENTRY,
    idempotency_reference: Any = None,
) -> TransferredMoney:
    """CS-8 — the customer's own CREDIT crosses to another of their accounts.

    The signature and the behaviour are exactly what they were when CS-8 landed
    on 2026-09-03; the body moved into `_transfer_between_accounts` so CS-22
    could land on the SAME writer rather than mint a second one, which is CS-8's
    own rule (*"build the transfer once"*, and it names the four specs waiting).

    Everything this function's own contract promises is documented on the core:
    one transaction boundary, `moved_on` as both dates and no clock read, the
    required reason, and the credit re-read INSIDE the atomic block so the same
    57.13 cannot be spent twice.
    """
    return _transfer_between_accounts(
        actor,
        purpose=models.PURPOSE_BILL,
        source_account_id=source_account_id,
        destination_account_id=destination_account_id,
        amount=amount,
        moved_on=moved_on,
        reason=reason,
        memo=memo,
        order=order,
        targets=targets,
        class_order=class_order,
        idempotency_source=idempotency_source,
        idempotency_reference=idempotency_reference,
    )


@permissions.require_role(permissions.SYSTEM_ADMIN, permissions.BILLING_CLERK, br_ref="BR-CUS-024")
def carry_deposit_forward(
    actor: Any,
    *,
    source_account_id: Any,
    destination_account_id: Any,
    moved_on: datetime,
    reason: str,
    expected_amount: Decimal | None = None,
    memo: str | None = None,
    idempotency_source: str = idempotency.SOURCE_ENTRY,
    idempotency_reference: Any = None,
) -> TransferredMoney:
    """CS-22 — the deposit is OFFERED FORWARD, never refunded and re-collected.

    **THE RULING, PO 2026-09-01 (CR-059 §6 Q2, option (b) CHOSEN), verbatim:**
    *"offer it forward: the move-in screen says the deposit is held on the old
    account and the clerk accepts it"*. Option (a) — *"refund the old one,
    collect a new one"* — was DECLINED, and option (c) — carrying forward only
    within 60 days — was declined too, **so there is no time limit here and its
    absence is the ruling rather than an omission.** The cost the PO was shown
    with it: *"money has to move between two accounts, which nothing in the
    product does today."* This door is that movement.

    ════════════════════════════════════════════════════════════════════════
    WORKED, END TO END, ON THE FIXTURE THIS PRODUCT SHIPS
    ════════════════════════════════════════════════════════════════════════
    Rosa Alvarez closes an account holding **$150.00** of deposit, received 14
    months ago, and opens a new one. The clerk accepts the carry.

        register   old account 150.00 → 0.00      new account 0.00 → 150.00
        books      DR 2300 150.00 (old)           CR 2300 150.00 (new)
        the clock  the ORIGINAL receipt date moves with the money
        interest   BR-CUS-057 reads $3.50 on the NEW account the day it lands,
                   because principal, rate and receipt date all moved together

    The tenant's 2300 balance is **unchanged** and the deposit register's total
    is **unchanged** — nothing was realised, discharged or paid out. What moved
    is which account the utility holds the money against. **The customer is not
    asked for a second $150.00**, which is the entire content of CS-22.

    ⚠ **THE AMOUNT IS NOT AN ARGUMENT — `expected_amount` IS A CONFIRMATION.**
    The whole principal moves (see `_refuse_unless_the_deposit_is_there`, which
    also explains why the OFFER says $153.50 while the movement is $150.00, and
    why the customer loses nothing by that).

    ⚠ **WHAT THIS DOOR DOES NOT DO, AND IT IS DELIBERATE IN BOTH DIRECTIONS.**
    It does not check the identity match: BR-CUS-089 gates the OFFER on a stored
    `strong` tier and `customers.discounts.carry_forward_offer` is where that
    gate lives, because it is a customers judgment about a person. This door
    proves the two accounts share a HOLDER (BR-CUS-054, `_refuse_unless_one_
    customer`), which is the payments-side question. **A caller that skipped the
    offer would carry money on a link but not on an identity check**, and that
    is stated here rather than assumed: wiring the screen means calling the
    offer first. It is REPORTED in this lane's decision-log row.
    """
    return _transfer_between_accounts(
        actor,
        purpose=models.PURPOSE_DEPOSIT,
        source_account_id=source_account_id,
        destination_account_id=destination_account_id,
        amount=expected_amount,
        moved_on=moved_on,
        reason=reason,
        memo=memo,
        idempotency_source=idempotency_source,
        idempotency_reference=idempotency_reference,
    )


def preview_deposit_carry_forward(
    *, source_account_id: Any, destination_account_id: Any
) -> dict[str, Any]:
    """What a carry WOULD move — computed by the service, never by the screen.

    A GET's worth of work and no writes, exactly as `preview_credit_transfer`
    is: the same read may be taken twice by two clerks with no consequence.

    It answers the two figures a clerk is about to act on — what the old account
    HOLDS and what the new one holds already — and it runs the same customer
    check the write runs, so a screen learns that two accounts are unrelated
    before the clerk types a reason rather than after.

    ⚠ **IT STATES THE INTEREST AS A SEPARATE FIGURE AND NEVER FOLDS IT IN.**
    `principal` is what moves; `interest_carries_with_the_clock` says the
    accrual is preserved by the receipt date travelling with the money. A
    preview that added them into one *"amount to carry"* would put a number on
    screen that this door then refuses.
    """
    tenant_id = _tenant_id()
    source = _account(tenant_id, source_account_id, side="source")
    destination = _account(tenant_id, destination_account_id, side="destination")
    _refuse_same_account(source, destination)
    _refuse_unless_one_customer(source, destination)
    _shared_currency(source, destination)
    here = _deposit_position(source.pk)
    there = _deposit_position(destination.pk)
    principal = _as_decimal(here.get("on_file"))
    received_on = _a_date(here.get("received_on"))
    return {
        "source_account_id": str(source.pk),
        "destination_account_id": str(destination.pk),
        "principal": str(principal),
        "currency": getattr(source, "currency", None) or "USD",
        "carryable": principal > ZERO,
        "deposit_received_on": (
            received_on.isoformat() if hasattr(received_on, "isoformat") else received_on
        ),
        "destination_holds_already": str(_as_decimal(there.get("on_file"))),
        # BR-CUS-050: the destination keeps the EARLIEST receipt date it has, so
        # a new account that already holds a deposit does not have its own clock
        # rewritten by the carry. Said on the wire because it changes what the
        # customer earns and a screen cannot work it out.
        "destination_received_on": (
            None if _a_date(there.get("received_on")) is None
            else _a_date(there.get("received_on")).isoformat()
        ),
        "interest_carries_with_the_clock": True,
        "problems": [dict(problem) for problem in DEPOSIT_CARRY_UNAVAILABLE],
    }


# ══════════════════════════════════════════════════════════════════════════
# CS-32 · the payment move — A REVERSAL, A NEW PAYMENT, AND THE LINK
# ══════════════════════════════════════════════════════════════════════════


def preview_payment_move(*, payment_id: Any, destination_account_id: Any) -> dict[str, Any]:
    """CS-32's *"preview showing what re-opens on the source and what the money
    will meet on the destination"* — composed here, never on the screen.

    BR-PAY-866's clause is the reason it exists: the destination re-allocates
    under its OWN rules, *"which may land the money on entirely different bills
    — that is correct and must be shown before confirming"*.
    """
    tenant_id = _tenant_id()
    original = _movable_payment(tenant_id, payment_id)
    destination = _account(tenant_id, destination_account_id, side="destination")
    if str(original.account_id) == str(destination.pk):
        raise PaymentRuleError(
            "that payment is already on this account. Re-allocating it across the account's own "
            "bills is a reapply (BR-PAY-031), not a move.",
            br_ref="BR-PAY-865",
        )
    position = billing_seam.open_invoices_for_account(destination.pk)
    outcome = allocate_payment(
        payment_amount=original.amount,
        open_invoices=position.invoices,
        class_order=_class_order(None),
    )
    reopens = [
        {"invoice_id": str(row.invoice_id), "amount": str(row.amount)}
        for row in original.allocations.all().order_by("created_at", "id")
    ]
    # BR-PAY-011's approval clause, ANSWERED HERE so the modal can ask for the
    # acknowledgement before the clerk commits rather than after. The verdict is
    # `reversal_rules`' own — a second copy of that rule here would be a second
    # place for it to drift, which is the argument `reversal_api` already makes
    # for serving the reversal plan from the service.
    from apps.payments import reversal_rules

    verdict = reversal_rules.approval_verdict(original, on=_today_of(original))
    return {
        "approval_required": verdict["required"],
        "approval_reasons": list(verdict["reasons"]),
        "payment_id": str(original.pk),
        "payment_no": original.payment_no,
        "source_account_id": str(original.account_id),
        "destination_account_id": str(destination.pk),
        "amount": str(original.amount),
        "posted_at": original.posted_at.isoformat(),
        "cleared_at": original.cleared_at.isoformat() if original.cleared_at else None,
        "reopens_on_source": reopens,
        "meets_on_destination": [
            {"invoice_number": row.invoice_number, "amount": str(row.applied)}
            for row in outcome.allocations
        ],
        "credit_carried": str(outcome.credit_carried),
        "problems": [dict(problem) for problem in (TRANSFER_UNAVAILABLE + position.problems)],
    }


def move_payment_to_account(
    actor: Any,
    *,
    payment_id: Any,
    destination_account_id: Any,
    reason: str,
    moved_on: date,
    approval: str | None = None,
    order: str = "oldest_first",
    targets: tuple[Any, ...] = (),
    class_order: tuple[str, ...] | None = None,
    idempotency_reference: Any = None,
) -> TransferredMoney:
    """CS-32 — the money was never this account's. All of it, or none of it.

    **One service function inside ONE transaction**, which is CS-32's own words.
    The reversal on the source, the new payment on the destination and the link
    between them commit together; the two nested `transaction.atomic()` blocks
    inside `reverse_payment` and `record_payment` become SAVEPOINTS of this one
    rather than boundaries of their own.

    **NEITHER LEG WRITES A JOURNAL LINE AND THIS FUNCTION COMPOSES NO ENTRY.**
    CS-32: *"Both legs post through the ledger service; neither writes a journal
    line directly."* The reversal mirrors the original's entry through
    `posting.reverse_entry` and the new payment posts an ordinary receipt — two
    entries the product already knows how to write, which is why this path adds
    no ledger seam at all where CS-8 needed one. The books net out exactly:
    receivables rise on the source by what re-opened and fall on the destination
    by what the money meets, and the holding account is debited and credited the
    same amount on the same day.

    **THE DATES ARE THE ORIGINAL'S** (BR-PAY-865) — see `_dates_of`. `moved_on`
    is the day the CORRECTION is made and is used for the reversal's own return
    date and for nothing else, because the reversal is a fact of the day someone
    noticed.

    ⚠ **IT IS ADMIN-ONLY, BY CONSEQUENCE RATHER THAN BY A NEW RULE.** The source
    leg is `reversal.reverse_payment`, which has carried
    `@require_role(SYSTEM_ADMIN)` since BR-PAY-1070 was ruled on 2026-09-01. A
    move is a reversal plus a recording, so it cannot be wider than the reversal
    inside it; adding a second, wider gate here would promise a Billing Clerk a
    reach the service denies and hand them a 403 from a layer they cannot see.
    Stated rather than discovered: **the clerk who recorded the payment against
    the wrong Patel cannot be the one who corrects it.**

    ⚠ **A PAYMENT MOVES ONCE, AND THE GUARANTEE IS `uq_payments_reverses`.** The
    original can carry exactly one reversal, so a second move of the same payment
    is refused by the database as a replay of the first. **CS-33 removes that
    index**, and when it does this path keeps its own guard: `_movable_payment`
    refuses a payment that already names a `moved_to` row.

    ⚠ **A MOVE USUALLY NEEDS `approval`, AND THAT IS `BR-PAY-011` DOING ITS JOB
    RATHER THAN THIS PATH BEING AWKWARD.** The rule is CONFIRMED —
    *"paid/cross-period requires Admin/Executive approval"* — and a move
    genuinely re-opens a bill the customer has already been sent, on the source
    account. So `reversal_rules.approval_verdict` asks for one whenever the
    payment met an issued bill or the day falls in a closed period, and this
    function passes the caller's acknowledgement straight through.

    **It was measured rather than assumed:** the first draft of this path did
    not pass one and every move of a payment that had met a bill was refused
    with *"needs an approval and none was given
    (applied_to_an_issued_bill)"* — which is the correct refusal, from the rule
    that owns it. **Exempting a move would have been this lane widening a signed
    rule**, so instead the requirement is stated here, `POST /payments/{id}/move`
    accepts `approval`, and `GET /payments/{id}/move-preview` is where a screen
    learns it will be asked for before the clerk starts typing.
    """
    tenant_id = _tenant_id()
    if not (reason or "").strip():
        raise PaymentRuleError(
            "a move needs a reason. CS-32 makes it required because the destination account's "
            "history will show money it never took at the counter, and the audit row is where "
            "the explanation lives.",
            br_ref="BR-PAY-865",
        )
    original = _movable_payment(tenant_id, payment_id)
    destination = _account(tenant_id, destination_account_id, side="destination")
    if str(original.account_id) == str(destination.pk):
        raise PaymentRuleError(
            "that payment is already on this account. Re-allocating it across the account's own "
            "bills is a reapply (BR-PAY-031), not a move.",
            br_ref="BR-PAY-865",
        )
    _refuse_if_batch_reconciled(original)
    posted_at, cleared_at = _dates_of(original)

    from apps.payments import reversal as reversal_service
    from apps.payments import services as record_service

    with transaction.atomic():
        reversed_leg = reversal_service.reverse_payment(
            actor,
            payment_id=original.pk,
            returned_on=_moment(moved_on),
            reason=MOVE_REVERSAL_REASON,
            memo=f"moved to another account: {reason}",
            approval=approval,
            idempotency_reference=(
                None if idempotency_reference is None else f"move-out:{idempotency_reference}"
            ),
        )
        if not reversed_leg.created:
            raise PaymentRuleError(
                f"payment {original.payment_no or original.pk} has already been reversed "
                f"({reversed_leg.reversal_no}). A payment is reversed once, so it can be moved "
                "once; if this correction needs to be made again, it is a new payment on the "
                "account that should have had it.",
                br_ref="BR-PAY-865",
            )
        recorded = record_service.record_payment(
            actor,
            account_id=destination.pk,
            amount=original.amount,
            # BR-PAY-865, and it is the clause with the customer's money in it.
            posted_at=posted_at,
            cleared_at=cleared_at,
            currency=original.currency,
            method_code=_method_code_of(original),
            confirmation=original.confirmation,
            memo=f"moved from {getattr(original, 'payment_no', None) or original.pk}: {reason}",
            purpose=original.purpose,
            order=order,
            targets=targets,
            class_order=class_order,
            idempotency_reference=(
                None if idempotency_reference is None else f"move-in:{idempotency_reference}"
            ),
            # The link CS-32's data note asks for, pointing at the ORIGINAL
            # rather than at the reversing row: the number the customer holds is
            # the original's, so S21's *"moved from PMT-…"* must name it or a
            # customer quoting their receipt cannot be found.
            #
            # ⚠ **IT IS PASSED INTO THE INSERT AND NEVER SET AFTERWARDS.** Hard
            # rule 4's trigger refuses every column change on a row that is not
            # `processing`, and a cleared payment is not — so a link written one
            # statement later would be refused on nearly every move. That is why
            # `record_payment` takes the argument at all.
            moved_from_payment_id=original.pk,
        )
        in_row = models.Payment.objects.get(tenant_id=tenant_id, pk=recorded.payment_id)
        trail = {
            "kind": KIND_PAYMENT_MOVE,
            "source_account_id": str(original.account_id),
            "destination_account_id": str(destination.pk),
            "moved_payment_no": original.payment_no,
            "reversal_no": reversed_leg.reversal_no,
            "destination_payment_no": in_row.payment_no,
            "amount": str(original.amount),
            "currency": original.currency,
            "reason": reason,
            "approval": approval,
            "moved_on": moved_on.isoformat(),
            "posted_at": posted_at.isoformat(),
            "cleared_at": cleared_at.isoformat() if cleared_at is not None else None,
            "reopened": [{**row, "amount": str(row["amount"])} for row in reversed_leg.reopened],
            "applied": str(recorded.applied),
            "credit_carried": str(recorded.credit_carried),
            "job": None if actor is not None else "payments.move",
        }
        core_audit.money_action(actor, AUDIT_MOVED, "payment", str(original.pk), after=trail)
        core_audit.money_action(actor, AUDIT_MOVED, "payment", str(in_row.pk), after=trail)

        return TransferredMoney(
            kind=KIND_PAYMENT_MOVE,
            source_account_id=str(original.account_id),
            destination_account_id=str(destination.pk),
            source_payment_id=reversed_leg.reversal_id,
            source_payment_no=reversed_leg.reversal_no,
            destination_payment_id=str(in_row.pk),
            destination_payment_no=in_row.payment_no,
            amount=original.amount,
            currency=original.currency,
            moved_payment_id=str(original.pk),
            moved_payment_no=original.payment_no,
            applied=recorded.applied,
            credit_carried=recorded.credit_carried,
            allocations=recorded.allocations,
            reopened=reversed_leg.reopened,
            source_credit_after=_credit_position(original.account_id),
            destination_credit_after=_credit_position(destination.pk),
            journal_entry_id=recorded.journal_entry_id,
            posting_key=recorded.posting_key,
            problems=TRANSFER_UNAVAILABLE + reversed_leg.problems + recorded.problems,
        )


# ══════════════════════════════════════════════════════════════════════════
# the shared mechanics — the reason CS-8 and CS-32 are one module
# ══════════════════════════════════════════════════════════════════════════


def _movable_payment(tenant_id: Any, payment_id: Any) -> models.Payment:
    """The payment being moved — this tenant's, real money, not already moved."""
    payment = models.Payment.objects.filter(tenant_id=tenant_id, pk=payment_id).first()
    if payment is None:
        raise PaymentRuleError(
            f"payment {payment_id} is not this tenant's. Nothing was moved.",
            br_ref="BR-TEN-003",
        )
    if payment.reverses_payment_id is not None:
        raise PaymentRuleError(
            f"{payment.payment_no or payment.pk} is a REVERSING row, not a payment. Move the "
            "payment it reverses, or record the money on the account that should have had it.",
            br_ref="BR-PAY-865",
        )
    if payment.amount <= ZERO:
        raise PaymentRuleError(
            f"{payment.payment_no or payment.pk} carries {payment.amount} and a move takes money "
            "somewhere. A negative row is one half of a movement that has already happened.",
            br_ref="BR-PAY-865",
        )
    # CS-33 removes `uq_payments_reverses`, and this guard is what stands in for
    # it here rather than inheriting a database constraint that is going away.
    if payment.moved_to.exists():
        raise PaymentRuleError(
            f"payment {payment.payment_no or payment.pk} has already been moved. Moving it again "
            "would give one receipt two destinations; record a fresh payment on the account "
            "that should have had it.",
            br_ref="BR-PAY-865",
        )
    return payment


def _method_code_of(payment: models.Payment) -> str | None:
    """The tender's CODE, because `record_payment` takes a code and not a row."""
    method = getattr(payment, "method", None)
    return getattr(method, "code", None) if method is not None else None


def _shared_currency(source: Any, destination: Any) -> str:
    """Both accounts' CHAR(3), or a refusal. Never a conversion.

    Two accounts of one customer in two currencies is not a case this product
    has, and if it ever is, moving money between them is a foreign-exchange
    transaction with a rate, a date and a gain-or-loss account — none of which
    exist here. Refused rather than transferred at 1:1, which would silently
    invent or destroy money.
    """
    left = getattr(source, "currency", None) or "USD"
    right = getattr(destination, "currency", None) or "USD"
    if left != right:
        raise PaymentRuleError(
            f"account {getattr(source, 'account_no', source.pk)} is in {left} and "
            f"{getattr(destination, 'account_no', destination.pk)} is in {right}. Moving money "
            "between them is a foreign-exchange transaction — a rate, a date and a gain-or-loss "
            "account — and this product has none of those. Nothing was moved.",
            br_ref="BR-PAY-002",
        )
    return left


def _class_order(class_order: tuple[str, ...] | None) -> tuple[str, ...]:
    """The tenant's own within-bill sequence (BR-PAY-010), never the shipped one.

    `services.tenant_class_order` reads the S66 Billing-defaults page, whose
    seeded value IS the shipped order — so nobody's figure moves and a tenant
    who put tax first has somewhere to have said so. Resolved through the
    services module rather than re-read here, because two readers of one setting
    are two places for it to drift (hard-won law 5, in code).
    """
    if class_order is not None:
        return tuple(class_order)
    from apps.payments import services

    return services.tenant_class_order()


def _allocate_destination(
    *,
    payment: models.Payment,
    account: Any,
    order: str,
    targets: tuple[Any, ...],
    class_order: tuple[str, ...] | None,
) -> tuple[Decimal, Decimal, list[dict[str, Any]]]:
    """BR-PAY-866 — the destination meets ITS OWN open bills, under ITS OWN rules.

    ⚠ **WHY THIS IS NOT `services._allocate_and_post`.** That function allocates
    AND posts, and its posting debits undeposited funds or the tender's clearing
    account — which is right for a receipt and wrong here, because no cash
    arrived: the debit for a transfer is the SOURCE account's customer-credit
    balance. Widening a 🔒 money file's signature to take a posting strategy for
    one extra caller is a larger change to a more dangerous file than writing the
    allocation rows here, so the rows are written here and the posting is a
    single call in the caller. The ARITHMETIC is not duplicated: `allocate_payment`
    is the same pure function, called with the same arguments.
    """
    class_sequence = _class_order(class_order)
    position = billing_seam.open_invoices_for_account(account.pk)
    try:
        outcome = allocate_payment(
            payment_amount=payment.amount,
            open_invoices=position.invoices,
            order=order,
            targets=targets,
            class_order=class_sequence,
        )
    except AllocationClassNotConfigured as refusal:
        raise PaymentRuleError(str(refusal), br_ref="BR-PAY-038") from refusal
    except (ValueError, TypeError) as refusal:
        raise PaymentRuleError(str(refusal), br_ref="BR-PAY-010") from refusal

    by_number = {invoice.number: invoice for invoice in position.invoices}
    rows: list[dict[str, Any]] = []
    for allocation in outcome.allocations:
        invoice = by_number[allocation.invoice_number]
        row = models.Allocation.objects.create(
            tenant_id=payment.tenant_id,
            payment=payment,
            invoice_id=invoice.invoice_id,
            amount=allocation.applied,
        )
        # CR-060 C19 / T7d — the class breakdown is a STORED fact, and a
        # transferred credit meets tax exactly as a receipt does. Without these
        # rows the *collected* remittance basis would understate by every cent a
        # transfer met, which is a tax return filed short.
        models.AllocationClass.objects.bulk_create(
            [
                models.AllocationClass(
                    tenant_id=payment.tenant_id,
                    allocation=row,
                    line_class=entry.line_class,
                    amount=entry.applied,
                )
                for entry in allocation.by_class
            ]
        )
        rows.append(
            {
                "invoice_id": str(invoice.invoice_id),
                "invoice_number": allocation.invoice_number,
                "amount": allocation.applied,
                "by_class": {entry.line_class: str(entry.applied) for entry in allocation.by_class},
            }
        )
    applied = sum((row["amount"] for row in rows), ZERO)
    return applied, outcome.credit_carried, rows


def _existing_transfer(tenant_id: Any, key: str | None) -> models.Payment | None:
    """Hard rule 6 — the same transfer submitted twice writes ONE pair.

    Keyed on `payments.webhook_key`, whose UNIQUE index is the database half:
    the SOURCE leg carries the key, so a replay finds the negative row and
    reports the pair it belongs to. The destination row deliberately carries no
    key — one movement, one token, or the two legs would dedupe independently
    and a lost race could leave a transfer with one leg.
    """
    if key is None:
        return None
    return models.Payment.objects.filter(tenant_id=tenant_id, webhook_key=key).first()


def _replayed(out_row: models.Payment) -> TransferredMoney:
    """The no-op answer for a transfer this tenant has already made.

    ⚠ **`kind` IS READ OFF THE ROW, NEVER ASSUMED.** This function returned
    `credit_transfer` unconditionally while a credit transfer was the only
    movement it could replay. A deposit carry-forward replayed under that name
    would tell the move-in screen a CREDIT had been transferred — so it would
    offer the deposit forward a second time and, worse, show the customer's
    security as spendable credit. The purpose is on the row; it is the same
    purpose the ledger legs were composed from.
    """
    in_row = out_row.moved_to.first()
    carried_a_deposit = out_row.purpose == models.PURPOSE_DEPOSIT
    held = -out_row.amount if carried_a_deposit else ZERO
    return TransferredMoney(
        kind=KIND_DEPOSIT_CARRY_FORWARD if carried_a_deposit else KIND_CREDIT_TRANSFER,
        held=held,
        source_deposit_after=_as_decimal(_deposit_position(out_row.account_id).get("on_file"))
        if carried_a_deposit
        else ZERO,
        destination_deposit_after=(
            _as_decimal(_deposit_position(in_row.account_id).get("on_file"))
            if carried_a_deposit and in_row is not None
            else ZERO
        ),
        source_account_id=str(out_row.account_id),
        destination_account_id=str(in_row.account_id) if in_row is not None else "",
        source_payment_id=str(out_row.pk),
        source_payment_no=out_row.payment_no,
        destination_payment_id=str(in_row.pk) if in_row is not None else "",
        destination_payment_no=in_row.payment_no if in_row is not None else None,
        amount=-out_row.amount,
        currency=out_row.currency,
        created=False,
        source_credit_after=_credit_position(out_row.account_id),
        destination_credit_after=(
            _credit_position(in_row.account_id) if in_row is not None else ZERO
        ),
        journal_entry_id=(
            str(in_row.journal_entry_id)
            if in_row is not None and in_row.journal_entry_id is not None
            else None
        ),
        # The absence a REPLAY reports is the absence of the movement it is
        # replaying, not the generic one — a replayed carry must not tell a
        # screen a receivables cache went stale when no receivable was touched.
        problems=DEPOSIT_CARRY_UNAVAILABLE if carried_a_deposit else TRANSFER_UNAVAILABLE,
    )


def _today_of(payment: models.Payment) -> date:
    """The business day the approval verdict is judged on, from the ROW.

    ⚠ **NOT A CLOCK** (BR-TEN-043, gate G6). The preview is a GET with no body
    and no `on` parameter, and inventing one from `datetime.now()` would decide
    a closed-period question in the SERVER's timezone. The payment's own
    clearing day is a fact the row already carries and is the day the money
    actually moved, which is the day `approval_verdict`'s period test is about.
    """
    when = payment.cleared_at or payment.posted_at
    return when.date()


def _moment(on: date) -> datetime:
    """A calendar day as the instant the reversal path takes (BR-TEN-043).

    Midnight UTC, which is `services._moment`'s own convention and carries the
    same open question (OQ-153 — which instant a user-entered date becomes, in
    whose timezone). The DATE is what every rule downstream reads, and it is
    preserved either way.
    """
    from datetime import time, timezone

    return datetime.combine(on, time.min, tzinfo=timezone.utc)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-059 §8 CS-8 · CS-32 · §0d.1 (the keystone note) · OQ-135 (CLOSED
#         2026-08-12) · OQ-132 (CLOSED 2026-08-11) · OQ-134 (CLOSED
#         2026-08-12) · BR-PAY-864..867 · BR-CUS-054 · BR-PAY-021 ·
#         BR-PAY-1070 · apps/payments/reversal.py · apps/payments/services.py ·
#         apps/payments/refunds.offset_before_refund · apps/billing/final_bill.py
# generated: 2026-09-03 by the CR-059 payments cross-account lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — CR-059 tasks 32 and 40
#            own S21/S58's Transfer action and S35's Move modal) F✔ G✔
#            H=deferred(PO 2026-08-09)
# exceptions:
#   E1 CR-059 CS-8 says to EXTEND `apps/billing/final_bill.py`'s balance-transfer
#      path *"rather than minting a second writer"*. **There is no writer there
#      to extend.** `final_bill.PATH_TRANSFER` is a settlement OPTION and
#      `master_account_for` returns `(None, reason)` on every call in this
#      repository — the landlord-agreement link it needs has no table. The rules
#      that path states (a transfer target is RESOLVED and never caller-supplied;
#      a transfer is a BALANCED transaction, audited) are honoured here and cited
#      above. Recorded in 12-governance/02-decision-log.md 2026-09-03. REPORTED.
#   E2 customers publishes no `sibling_account_ids(account_id)`. The same walk
#      exists PRIVATELY twice in that module (`selectors.arrears_on_other_accounts`,
#      `move_out_settlement._sibling_positions`) and is published neither time,
#      so `_refuse_unless_one_customer` asks the two published reads from both
#      ends. Two accounts whose ONLY shared holder is first on neither are
#      refused. The failure direction is safe and it is REPORTED, not hidden.
#   E3 `apps/payments/models.py` is on `10-scripts/gates/human_owned.txt` and
#      this lane added one column (`moved_from_payment`) plus CS-30's three.
#      A row in 12-governance/09-human-review-ledger.md is OWED and this lane's
#      write scope does not include that file; the row's content is written into
#      the decision log verbatim so it can be transcribed. REPORTED.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
