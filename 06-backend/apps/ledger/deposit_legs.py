# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-001 (source-event posting contracts — the two FINAL-BILL
#           deposit rows of the DR/CR table, and TC-1's LE-1 month)
#           Screens: S56 (the entries) · S36 (the deposit tie-out that reports
#           their absence today — US-LED-004's second row)
# Rules:    BR-BIL-013 (final bill: the deposit + its interest apply FIRST,
#           then exactly ONE settlement path) · BR-CUS-050 / BR-CUS-057
#           (deposit interest = tenant simple annual rate from the original
#           receipt date) · BR-PAY-012 (a deposit is a LIABILITY, never
#           revenue) · BR-LED-001 (every line carries source_type + source_id) ·
#           BR-LED-007 (the deposit subledger tie-out) · BR-TEN-043 (event time
#           is named by the caller, never read from a clock) · CLAUDE.md rule 2
#           (money NUMERIC(18,6) + CHAR(3), never float) · rule 4 (financial
#           immutability) · rule 5 (balanced pairs; posting is the sole writer) ·
#           rule 6 (idempotency) · rule 7 (audit)
# Golden:   GT-23 / WE-7 ❄️ B5 FROZEN, finance-signed 2026-08-08 — a $150.00
#           deposit held 14 months at 2% simple earns **3.50**, so **153.50**
#           applies before any settlement path is chosen; Case B's charges
#           289.40 leave **135.90** due. LE-1 §7 ties the month: deposit
#           liability CR **0.00** = 150.00 + 3.50 - 153.50, deposit interest
#           expense DR **3.50**, totals **598.69 = 598.69**.
# Tests:    06-backend/tests/test_us_led_001_deposit_legs.py ·
#           06-backend/tests/ledger_le_fixtures.py (LE-1's month now posts its
#           two deposit entries THROUGH this module)
# Impacts:  apps/ledger/posting.py 🔒 (the sole writer this composes for) ·
#           apps/billing/posting_seam.py (the caller — a final bill's issue
#           emits both legs inside its own transaction) ·
#           apps/billing/final_bill.py (computes the credit; books nothing) ·
#           apps/ledger/tie_out.py (the panel that reports the absence these
#           two functions close) · apps/ledger/reporting.revenue_and_ar (it
#           identifies an applied deposit by its deposit-liability DEBIT leg,
#           so the shape below is load-bearing for BR-REP-009)
# ───────────────────────────────────────────────────────
"""The two FINAL-BILL deposit postings: interest accrued, and deposit applied.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this composes money-bearing journal
entries under CLAUDE.md's 🔒 *ledger posting*. AI-authored 2026-08-16 under the
PO ruling of 2026-08-09 (*"AI will do it; we will review it later as human"*).
Row in `12-governance/09-human-review-ledger.md`; it may never reach lifecycle
RATIFIED without a recorded human sign-off.

════════════════════════════════════════════════════════════════════════════
WHAT WAS WRONG, IN ONE SENTENCE AND ONE FIGURE
════════════════════════════════════════════════════════════════════════════
A utility that took a **$150.00** deposit had that money in the customer's
record and **nothing in its books** on the way back out. The trial balance
still footed — because the entry was never made at all, on either side.

The measurement behind that, taken on 2026-08-16 by the US-LED-002/004 lane and
recorded in `apps/ledger/posting.py`'s own docstring: US-LED-001's contract
table has **seventeen** source events, **thirteen post** and **four do not**.
Three of the four are deposit rows:

  * *"Deposit interest accrual (final bill) | deposit interest expense |
    deposit liability | LE-1 (3.50) · BR-CUS-050/057"*
  * *"Deposit application at final bill | deposit liability | AR | LE-1
    (153.50) · BR-BIL-013"*
  * *"First-bill deposit line | (within issue entry) | deposit liability —
    never revenue | BR-BIL-012 (WE-6)"* — which is a GL-STAMP problem rather
    than a posting one and is closed in `apps/billing/issue.py`, not here.

`apps/billing/final_bill.py` computes the first two — `deposit_credit_for`
returns principal and interest, `settle` applies them before any settlement
path is chosen — and **books neither**. This module is the missing writer.

**WHY THE COMPOSITION IS HERE AND NOT IN BILLING'S SEAM.** Every other posting
contract in the product is composed by the module that owns the source document
(`apps/billing/posting_seam.py`, `apps/payments/ledger_seam.py`), and that is
right for them: an issue entry's credit buckets come from billing's own stamped
invoice lines, so billing is the only module that can build them. **These two
entries name no billing account at all.** Both sides of both are LEDGER
designations — `deposit_liability`, `deposit_interest_expense`,
`accounts_receivable` — so composing them in billing would put three
designation lookups and a signed DR/CR contract in a module that contributes
nothing to either. The caller supplies four figures and two dates; the books
decide the accounts and the sides, which is exactly the split US-LED-001 §1
describes.

════════════════════════════════════════════════════════════════════════════
THE TWO ENTRIES, WORKED ON ❄️ WE-7 / GT-23's FROZEN FIGURES
════════════════════════════════════════════════════════════════════════════
A customer paid a **$150.00** deposit 14 months ago. The tenant's rate is 2%
simple (BR-CUS-057), so **$3.50** has accrued. They move out; their final bill's
closing position is **$289.40** (WE-7 Case B).

    1. INTEREST ACCRUED
       DR  6950 deposit interest expense    3.50   ← the utility's cost
       CR  2300 customer deposit liability   3.50   ← now owed back to them

    2. DEPOSIT APPLIED
       DR  2300 customer deposit liability 153.50   ← the liability closes
       CR  1200 accounts receivable        153.50   ← the customer's bill falls

Afterwards: the deposit liability is **$0.00** (150.00 + 3.50 − 153.50), the
deposit interest expense holds **$3.50**, and **$135.90** stands in AR — which
is LE-1 §7 verbatim and the reason the month foots at **598.69 = 598.69**.

**NOTHING IN THIS FILE COMPUTES A FIGURE.** The 3.50 is BR-CUS-057's accrual,
owned by customers (US-CUS-023 §7); the 153.50 is `final_bill.DepositCredit.
total`, which is principal + interest and no other arithmetic. This module
asserts them. It does not round — B4 ❄️ rounds once, at finalization — and the
posting service refuses anything carrying more than two decimals anyway
(BR-LED-025, PO 2026-08-12: *"Refuse and make the caller round"*).

**A DEPOSIT IS THE CUSTOMER'S MONEY HELD BY THE UTILITY — A LIABILITY, NEVER
REVENUE.** BR-PAY-012, and `apps/payments/ledger_seam.py` says the same thing
where it credits 2300 on the way in. Both legs above keep it a liability the
whole way through: the interest INCREASES what is owed back, and the
application is the only thing that discharges it.

════════════════════════════════════════════════════════════════════════════
THE LEFTOVER DEPOSIT — OQ-248, CLOSED 2026-09-30 (PO, option A)
════════════════════════════════════════════════════════════════════════════
⚠ **RULED: *"A for deposit refund"*.** The part left over after what is owed is
REFUNDED: it moves to 2400 customer credit (money owed back to the customer) in
the SAME entry, and leaves the books when the refund is paid. Case A below now
posts DR 2300 153.50 / CR AR 142.30 / CR 2400 11.20; J70's figure is 150.00
against 103.67 → 46.33 owed back. `tests/test_oq_248_leftover_deposit_is_
refunded.py` asserts both. The paragraphs below are the question as it was put,
kept because they are why the entry has this shape.

WE-7 **Case A** is the same customer with charges of **$142.30** instead of
$289.40. The signed contract row says CR **AR**, so applying the whole $153.50
would leave that customer's AR at **−$11.20** — the books saying the utility is
owed minus eleven dollars and twenty cents.

And nothing could then pay it out. The refund row one line down the same signed
table reads *"Refund executed | customer credit | cash"* — a refund DEBITS
**2400 customer credit balances**, where this customer has **$0.00**. **No
signed statement moves the $11.20 across.**

So `post_deposit_applied` REFUSED (until 2026-09-30) when the deposit exceeded
the closing position, quoting both figures, and named **OQ-248**. It was not stubbed with
`NotImplementedError` because the OTHER case — the signed one — must keep
working inside a bill run (a stub would kill the batch where a named refusal
records one break, which is DEF-047's lesson and BR-BIL-055's rule).

A wrong entry is worse than a missing one, because a missing one is visible: the
deposit tie-out on S36 (US-LED-004, BR-LED-007) compares the books' deposit
liability against the customer register and shows the difference in red with no
dismiss control. A $11.20 negative receivable, by contrast, looks like an
ordinary credit balance on every report the product prints.

════════════════════════════════════════════════════════════════════════════
IDEMPOTENCY: TWO EVENTS ON ONE DOCUMENT, TWO KEYS
════════════════════════════════════════════════════════════════════════════
Hard rule 6. `posting.posting_key` is composed by the OWNER's function, never as
an f-string here, and the events are distinct strings on the same source
document:

    invoice|<final invoice id>|deposit_interest_accrued
    invoice|<final invoice id>|deposit_applied

Both differ from that bill's own `invoice|<id>|issued`, so all three lawfully
exist — *a document is not the unit of identity; a document plus the event that
happened to it is* (`apps/ledger/posting.py`). A re-issued or resumed run
replays all three and writes none of them twice.

`source_type` and `source_id` are the CALLER's, not hardcoded to `invoice`: LE-1
keys its interest accrual on the deposit payment (`deposit|DEP-1042|
interest_accrued`) because in that fixture the accrual is a month-end event
rather than a move-out one, and a module that forced one shape would make the
signed worked example unrepresentable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from apps.ledger import chart, models, posting, selectors

ZERO = Decimal("0")

#: The two events, named once so a caller cannot mistype one into a key that
#: silently never collides with anything (which is a replay guard that guards
#: nothing — the failure mode hard rule 6 exists for).
EVENT_INTEREST_ACCRUED = "deposit_interest_accrued"
EVENT_DEPOSIT_APPLIED = "deposit_applied"

#: What these postings CANNOT say, carried on every result — the discipline
#: `apps/billing/posting_seam.POSTING_UNAVAILABLE` uses, so an absence is on the
#: payload rather than only in this docstring (hard-won law 1).
DEPOSIT_LEG_UNAVAILABLE: tuple[dict[str, Any], ...] = (
    {
        "code": "deposit_interest_is_read_never_computed",
        "br_ref": "BR-CUS-057 · US-CUS-023 §7 · GT-61",
        "detail": "the accrual engine is customers' and is NOT BUILT — "
        "`apps.customers.selectors.deposit_interest_accrued` is published by nothing, so "
        "`apps/billing/final_bill.deposit_credit_for` refuses any account that HOLDS a "
        "deposit. Until it lands, these two entries can only be driven with an interest "
        "figure a caller states. GT-61 freezes the arithmetic ($150 at 2.0% over 89 months "
        "= $22.25) and nothing implements it.",
    },
    {
        "code": "the_refund_is_raised_not_paid_here",
        "br_ref": "OQ-248 (CLOSED 2026-09-30, A) · BR-BIL-013 · OQ-195",
        "detail": "when the deposit is worth MORE than the closing position (WE-7 Case A: "
        "153.50 against 142.30) the excess, 11.20, is credited to 2400 customer credit "
        "balances — money owed back to the customer. Paying it out is the signed refund row "
        "(DR customer credit / CR cash), owned by payments; this entry does not pay it.",
    },
    {
        "code": "no_final_settlements_table_records_the_path",
        "br_ref": "US-BIL-011 §5 · B2 Addendum r10 #10/#11",
        "detail": "`apps/billing/final_bill.py` reports it from its own side: there is no "
        "`final_settlements` table, so the settlement PATH (refund / collect / transfer / "
        "payment plan / write-off) is computed and never stored. These two entries are the "
        "part of a closure that IS recorded — the deposit's discharge — and the path that "
        "follows it is a different story's row.",
    },
)


class DepositPostingError(posting.PostingError):
    """A deposit leg the books refuse, in the ledger's own vocabulary.

    A subclass of `PostingError` so a caller that already translates the
    posting service's refusals into its own vocabulary (billing's
    `PostingRefused`, payments' `PaymentRuleError`) catches these unchanged —
    which is what keeps ONE unpostable final bill a single named break in a run
    of five hundred rather than an exception that takes the batch down
    (BR-BIL-055 · DEF-047).
    """


@dataclass(frozen=True)
class DepositLegPosting:
    """What one deposit leg left in the books, and what it could not say.

    `created=False` is the replay (hard rule 6) — a resumed issue re-emits the
    leg and writes nothing, which is the correct outcome rather than an error.
    `amount` is echoed so a caller can tie out what it asked for against what
    landed, at the moment of posting rather than a month later on S36.
    """

    entry_id: str
    posting_key: str
    created: bool
    amount: Decimal
    debit_designation: str
    credit_designation: str
    unavailable: tuple[dict[str, Any], ...] = field(default=DEPOSIT_LEG_UNAVAILABLE)
    #: OQ-248 (A, 2026-09-30): the part of the deposit left over after what is
    #: owed, credited to 2400 customer credit balances — money owed back.
    refunded: Decimal = ZERO


def _designated(designation: str, *, what: str, br_ref: str) -> str:
    """A tenant's account for one designation — BY DESIGNATION, or REFUSE.

    Never the numbers 2300, 6950 or 1200. `apps/ledger/chart.py` states the law
    in the PO's own words — *"the code reads the DESIGNATION and never the
    number"* — and OQ-106 was raised precisely because a posting path had no way
    to find "the AR account" without writing a code into Python.

    All three designations this module needs are among the twelve and all three
    are seeded from B5 line 74 ❄️ (2300 Customer deposit liability, 6950 Deposit
    interest expense, 1200 Accounts receivable), so a tenant reaching this
    refusal has deactivated or un-designated one on purpose. It is one edit on
    the GL mapping page and it blocks exactly one thing until somebody makes it.
    """
    account_id = selectors.gl_account_id_for_designation(designation)
    if not account_id:
        raise DepositPostingError(
            f"no live ledger account carries the {designation!r} designation, so a deposit "
            f"{what} has no home ({br_ref}). A deposit is the CUSTOMER'S money held by the "
            "utility — a liability, never revenue — and nothing here substitutes another "
            "account for it: posting it to revenue would recognise somebody else's money as "
            "income, on an entry that can never be edited (hard rule 4). A human designates "
            "an account on the GL mapping page."
        )
    return str(account_id)


def _checked_amount(value: Any, what: str) -> Decimal:
    """A money figure, or a refusal naming which figure and why (rule 2).

    Refused rather than coerced: a coercion hides the place where a customer's
    deposit became binary, and the entry it produces is immutable.
    """
    if not isinstance(value, Decimal):
        raise DepositPostingError(
            f"{what} arrived as {value!r} ({type(value).__name__}), not a Decimal. Money is "
            "NUMERIC(18,6) and never a float (CLAUDE.md rule 2). Refused rather than "
            "converted — the conversion is exactly the place a cent goes missing, and a "
            "posted entry cannot be corrected by editing it."
        )
    if value < ZERO:
        raise DepositPostingError(
            f"{what} is {value}, a negative amount. `journal_lines` is `CHECK (amount >= 0)` "
            "and direction is carried by the SIDE, so a negative figure here means the "
            "caller has the two legs the wrong way round — which would move a customer's "
            "deposit in the direction that takes their money rather than returning it."
        )
    return value


def post_deposit_interest_accrued(
    *,
    account_id: Any,
    source_type: str,
    source_id: Any,
    interest: Decimal,
    entry_date: date,
    posted_at: datetime,
    currency: str,
    actor: Any = None,
    memo: str | None = None,
) -> DepositLegPosting | None:
    """US-LED-001's *"Deposit interest accrual (final bill)"* — DR 6950 / CR 2300.

    ❄️ Worked, WE-7 / GT-23 and LE-1: a **$150.00** deposit held 14 months at 2%
    simple has earned **$3.50**, so this posts DR 6950 deposit interest expense
    **3.50** / CR 2300 customer deposit liability **3.50**. The customer is owed
    **$153.50** back from that moment, and the utility has recognised the $3.50
    as what it is — a cost of holding somebody else's money, not a reduction of
    revenue.

    **RETURNS `None` FOR ZERO INTEREST, AND THAT IS NOT THE SAME AS AN ERROR.**
    A deposit taken last week has accrued nothing. An entry of 0.00 against 0.00
    would be a journal entry for money that did not move, and every closing
    account in the product would file one — 0.00 rows a bookkeeper has to read
    past for ever. The caller distinguishes *"nothing accrued"* from *"we could
    not ask"* upstream, where the difference is knowable (`final_bill.
    deposit_credit_for` REFUSES an unreadable accrual rather than returning a
    zero, for exactly this reason).

    **BOTH DATES ARE INPUTS** (PO ruling 2026-08-11 closing OQ-107, BR-TEN-043).
    Nothing in this module reads a clock, which gate G6 greps every money path
    for; a resumed run stamps the moment of the run it resumed.
    """
    interest = _checked_amount(interest, "the accrued deposit interest")
    if interest == ZERO:
        return None

    expense = _designated(
        chart.DEPOSIT_INTEREST_EXPENSE, what="interest accrual", br_ref="BR-CUS-050/057"
    )
    liability = _designated(
        chart.DEPOSIT_LIABILITY, what="interest accrual", br_ref="BR-PAY-012 · BR-CUS-057"
    )
    dimensions = {
        "source_type": source_type,
        "source_id": source_id,
        # BR-LED-001 — without the account dimension this expense sits in the
        # trial balance and in nobody's deposit position, so US-LED-004's
        # deposit tie-out could see the total and never the customer.
        "account_id": account_id,
    }
    result = posting.post(
        posting.PostingRequest(
            posting_key=posting.posting_key(
                source_type=source_type, source_id=source_id, event=EVENT_INTEREST_ACCRUED
            ),
            entry_date=entry_date,
            posted_at=posted_at,
            currency=str(currency),
            source_type=source_type,
            source_id=source_id,
            memo=memo or "Deposit interest accrued",
            lines=(
                posting.PostingLine(
                    ledger_account_id=expense,
                    side=models.SIDE_DEBIT,
                    amount=interest,
                    **dimensions,
                ),
                posting.PostingLine(
                    ledger_account_id=liability,
                    side=models.SIDE_CREDIT,
                    amount=interest,
                    **dimensions,
                ),
            ),
            audit_context={"deposit_interest": str(interest), "br_ref": "BR-CUS-057"},
        ),
        actor=actor,
    )
    return DepositLegPosting(
        entry_id=result.entry_id,
        posting_key=result.posting_key,
        created=result.created,
        amount=interest,
        debit_designation=chart.DEPOSIT_INTEREST_EXPENSE,
        credit_designation=chart.DEPOSIT_LIABILITY,
    )


def post_deposit_applied(
    *,
    account_id: Any,
    source_type: str,
    source_id: Any,
    credit: Decimal,
    closing_position: Decimal,
    entry_date: date,
    posted_at: datetime,
    currency: str,
    actor: Any = None,
    memo: str | None = None,
) -> DepositLegPosting | None:
    """US-LED-001's *"Deposit application at final bill"* — DR 2300 / CR 1200 AR.

    ❄️ Worked, WE-7 Case B / LE-1: a **$153.50** credit (150.00 principal + 3.50
    interest) against a closing position of **$289.40** posts DR 2300 customer
    deposit liability **153.50** / CR 1200 accounts receivable **153.50**. The
    deposit liability closes to **$0.00**, and **$135.90** stands in AR as the
    remainder BR-BIL-013's settlement path then resolves.

    `credit` is `final_bill.DepositCredit.total` — principal plus interest and
    no other arithmetic. It is the caller's figure and is asserted, never
    recomputed (US-LED-001 §1).

    `closing_position` is what the customer owes AFTER the final bill has
    posted: BR-BIL-013 settles *"the remainder"* and the PO closed OQ-158 on
    2026-08-12 with *"everything outstanding"*, so it is the whole receivable
    and not this bill alone. It is REQUIRED rather than optional because it is
    the only input that can tell the signed case from OQ-248's — see below.

    **WHEN THE DEPOSIT EXCEEDS THE POSITION, THE EXCESS IS REFUNDED — OQ-248,
    CLOSED 2026-09-30 (PO, option A: *"A for deposit refund"*).** WE-7 Case A's
    charges are **$142.30**; the $153.50 credit settles them and the **$11.20**
    left over is credited to 2400 customer credit balances in the same entry,
    which is where the signed refund row pays from. AR never goes negative.
    This refused by name until the ruling.

    **RETURNS `None` WHEN THERE IS NO DEPOSIT.** An account that never paid one
    has nothing to discharge, and a 0.00 / 0.00 entry on every closure in the
    product is noise in the one ledger a bookkeeper reads line by line.
    """
    credit = _checked_amount(credit, "the deposit credit being applied")
    if credit == ZERO:
        return None
    if not isinstance(closing_position, Decimal):
        # rule 2 — the same refusal `_checked_amount` gives, without its sign
        # check: a closing position BELOW zero is a real fact (the customer is
        # already in credit) and means only that nothing is owed.
        _checked_amount(closing_position, "the account's closing position at the final bill")

    # ⚠ **OQ-248 CLOSED 2026-09-30 — PO, option A, verbatim: *"A for deposit
    # refund"* (BR-BIL-013).** This REFUSED the over-credit case until then.
    # The deposit settles what is owed; the part LEFT OVER is refunded — it
    # moves to CUSTOMER CREDIT (money owed back to the customer) and leaves the
    # books when the refund is paid, through the refund row already signed
    # beside this one (*"Refund executed | customer credit | cash"*).
    #
    # ONE balanced entry on the SAME `deposit_applied` key, so a replay still
    # writes nothing twice (hard rule 6) and AR never goes negative:
    #
    #     DR 2300 deposit liability   credit      e.g. 150.00
    #     CR 1200 AR                  owed           103.67
    #     CR 2400 customer credit     the excess      46.33
    #
    # `owed` is never below zero: a customer already in credit owes nothing, and
    # the whole deposit is theirs to have back. A zero AR line is not written
    # (`journal_lines` would carry a 0.00 row a bookkeeper has to read past).
    owed = max(min(credit, closing_position), ZERO)
    refunded = credit - owed

    liability = _designated(
        chart.DEPOSIT_LIABILITY, what="application", br_ref="BR-BIL-013 · BR-PAY-012"
    )
    receivable = _designated(chart.AR, what="application", br_ref="BR-BIL-013") if owed else None
    customer_credit = (
        _designated(chart.CUSTOMER_CREDIT_BALANCE, what="refund", br_ref="BR-BIL-013 · OQ-248")
        if refunded
        else None
    )
    dimensions = {
        "source_type": source_type,
        "source_id": source_id,
        # BR-LED-001, and load-bearing twice over: `reporting.revenue_and_ar`
        # identifies an APPLIED deposit by its deposit-liability DEBIT leg
        # (BR-REP-009 — *applied deposits count as collected*), and
        # `reporting.ar_positions` needs the account to take the credit off the
        # right customer's row.
        "account_id": account_id,
    }
    result = posting.post(
        posting.PostingRequest(
            posting_key=posting.posting_key(
                source_type=source_type, source_id=source_id, event=EVENT_DEPOSIT_APPLIED
            ),
            entry_date=entry_date,
            posted_at=posted_at,
            currency=str(currency),
            source_type=source_type,
            source_id=source_id,
            memo=memo or "Deposit applied at final bill",
            lines=tuple(
                line
                for line in (
                    posting.PostingLine(
                        ledger_account_id=liability,
                        side=models.SIDE_DEBIT,
                        amount=credit,
                        **dimensions,
                    ),
                    (
                        posting.PostingLine(
                            ledger_account_id=receivable,
                            side=models.SIDE_CREDIT,
                            amount=owed,
                            **dimensions,
                        )
                        if owed
                        else None
                    ),
                    (
                        posting.PostingLine(
                            ledger_account_id=customer_credit,
                            side=models.SIDE_CREDIT,
                            amount=refunded,
                            **dimensions,
                        )
                        if refunded
                        else None
                    ),
                )
                if line is not None
            ),
            audit_context={
                "deposit_applied": str(credit),
                "closing_position": str(closing_position),
                "applied_to_receivable": str(owed),
                "refunded_to_customer_credit": str(refunded),
                "br_ref": "BR-BIL-013 · OQ-248 (A)",
            },
        ),
        actor=actor,
    )
    return DepositLegPosting(
        entry_id=result.entry_id,
        posting_key=result.posting_key,
        created=result.created,
        amount=credit,
        debit_designation=chart.DEPOSIT_LIABILITY,
        credit_designation=chart.AR if owed else chart.CUSTOMER_CREDIT_BALANCE,
        refunded=refunded,
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-001@5e6b5d8 (sha1[:7] of the sources this slice was authored from, concatenated in order: 04-docs/05-modules/09-ledger/06-epics/EP-LED-01-posting-consumption.md — US-LED-001 §1's two final-bill deposit rows + §7's LE-1 tie-out — · 04-docs/02-decisions/05-golden-tests.md — GT-23/WE-7 ❄️ — · 04-docs/05-modules/07-billing/02-business-rules.md — BR-BIL-013 — · 04-docs/05-modules/03-customers/02-business-rules.md — BR-CUS-050/057 —; co-cited BR-PAY-012, BR-LED-007)
# generated: 2026-08-16 by story-coder (US-LED-001 four-unposted-events lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — a service-layer posting contract reached through billing's stage 7; its RESULT is served by GET /finance/tie-outs and the S56 journal reads) E=deferred(no-frontend-half — S56 renders the entries and S36's deposit tie-out row is the screen that has been REPORTING their absence; these two events have no screen of their own and never will) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · tests/test_us_led_001_deposit_legs.py — every guard driven
#         RED before it was trusted, failures quoted in
#         12-governance/09-human-review-ledger.md
# exceptions: (1) THE OVER-CREDIT CASE IS REFUSED, NAMING **OQ-248**. WE-7 Case A
#         (153.50 against 142.30) would put -11.20 into AR and the signed refund
#         row debits 2400, which holds 0.00. Refused rather than chosen (prime
#         directive), and refused rather than stubbed with NotImplementedError so
#         one unpostable closure is one named break in a run (BR-BIL-055/DEF-047).
#         (2) THE INTEREST IS READ, NEVER COMPUTED. BR-CUS-057's accrual engine
#         is US-CUS-023 §7 and is unbuilt, so `final_bill.deposit_credit_for`
#         refuses any account that HOLDS a deposit and these legs cannot fire on a
#         real closure until customers publishes `deposit_interest_accrued`.
#         Carried on every result as `deposit_interest_is_read_never_computed`.
#         (3) ZERO POSTS NOTHING and returns None — not an error and not a 0.00
#         entry. A deposit taken last week has accrued nothing; an account that
#         never paid one has nothing to discharge.
#         (4) `source_type`/`source_id` ARE THE CALLER'S. Billing keys both legs
#         on the final invoice; LE-1 keys its accrual on the deposit payment
#         because there it is a month-end event. Forcing one shape would make the
#         signed worked example unrepresentable.
#         (5) THE COMPOSITION IS IN THE LEDGER, against the house pattern where
#         the source module composes. Both sides of both entries are ledger
#         DESIGNATIONS and neither names a billing account, so composing them in
#         billing would put a signed DR/CR contract in a module that contributes
#         nothing to it. Argued in the module docstring rather than left as a
#         surprise to the next reader.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
