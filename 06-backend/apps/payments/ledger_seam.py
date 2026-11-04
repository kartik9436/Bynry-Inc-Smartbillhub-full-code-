# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-001 (a recorded payment reaches the books) · US-LED-001
#           (source-event posting contracts — the "Payment cleared" row and the
#           "Bank-rec difference" row) · US-PAY-022 (the S40 difference posts
#           per reason + GL) · US-PAY-023 (the reconciled batch and the
#           Unreconcile that reverses it)
#           Screens: S33 · S56 · S39 · S40
# Rules:    CLAUDE.md rule 5 (balanced pairs; ONLY the ledger posting service
#           writes journal lines) · rule 2 (money NUMERIC(18,6) + CHAR(3)) ·
#           rule 6 (idempotency) · rule 7 (audit) · BR-PAY-012 (unapplied money
#           → account credit) · BR-PAY-019 (every rec difference carries a
#           reason AND a GL) · BR-PAY-021 (bank rec matches on CLEARING, which
#           is why the book date is the clearing date) · BR-PAY-025 (deposit
#           batches) · BR-LED-001 (every journal line carries source_type +
#           source_id) · BR-LED-003 (a correction is a NEW mirror entry) ·
#           BR-LED-015 (every finance action audits) · BR-TEN-043 (event time is
#           named by the caller, never read from a clock)
# Tests:    06-backend/tests/test_us_pay_001_record_payment.py ·
#           06-backend/tests/test_us_pay_020_023_bank_rec.py
# Impacts:  apps/payments/services.record_payment (the receipt half's only
#           caller) · apps/payments/reconciliation.py (the reconciliation half's
#           only caller) · apps/ledger/posting.post + reverse_entry (the owner,
#           resolved BY NAME) · apps/ledger/selectors (the GL designations,
#           resolved BY NAME)
# ───────────────────────────────────────────────────────
"""payments → ledger SEAM: *the payment reaches the books, or nothing happens.*

Until this file existed, `apps/ledger/posting.py` — 837 lines, the sole writer
of journal lines in the product — was called by **nothing**. Its own docstring
said so under the heading WHAT NOTHING CALLS YET, and named this module as one
of the three callers it was waiting on. This is that caller.

╔══════════════════════════════════════════════════════════════════════════╗
║  PAYMENTS POSTS NOTHING ITSELF. IT HANDS OVER A FULLY-SPECIFIED REQUEST. ║
╚══════════════════════════════════════════════════════════════════════════╝

CLAUDE.md rule 5 and the payments overview say the same sentence from the two
sides: *"Payments posts NOTHING itself (ledger posting service 🔒)"*. Nothing
here inserts a journal line, opens the ledger's write window, or knows the shape
of `journal_lines`. It composes a `PostingRequest` under a ratified DR/CR
contract, resolves the accounts BY DESIGNATION through the ledger's own reads,
and calls `post()`.

────────────────────────────────────────────────────────────────────────────
THE CONTRACT, AND WHERE EVERY LEG OF IT IS SIGNED
────────────────────────────────────────────────────────────────────────────
US-LED-001's contract table, row *"Payment cleared"*: **DR cash/undeposited ·
CR AR**, sourced to *payments §12 (PE-1)*. That literal fork — `cash/undeposited`
— was OQ-143, and **the Product Owner closed it on 2026-08-11**:

    "Cash is received but undeposted in such case payment will say csah but
     ledger will say undeposited - until bank record and reconcilaition
     confirm it it is not realised"

So **cash is not cash until the bank confirms it**, and the posting is TWO
steps, not one:

    on RECEIPT          DR undeposited_funds   CR accounts_receivable
    on RECONCILIATION   DR cash                CR undeposited_funds

This seam owns the FIRST step. The second belongs to the bank-rec lane
(`apps/payments/reconciliation.py`, BR-PAY-004/019) and is not written here.
Both designations are already in the ❄️ finance-signed chart — **1000 Cash ·
1010 Undeposited funds** (B5 line 74) — so nothing about this needs a re-sign,
which was the deciding constraint put to the PO.

    DR  undeposited_funds         the full amount the customer handed over
    CR  accounts_receivable       what actually met open bills
    CR  customer_credit_balance   the remainder, if any

**The third leg is the one the contract table does not spell out**, and it is
derived rather than invented — stated here plainly because a reader deserves to
know which legs are transcribed and which are reasoned:

  * BR-PAY-012 (CONFIRMED): *"unapplied → account credit"*. PE-4 works it —
    open 292.87, pay 350.00 → **credit 57.13**.
  * `customer_credit_balance` is one of the eleven GL designations the PO ruled
    on 2026-08-11 closing OQ-110, mapped to **2400 Customer credit balances**.
  * The contract table's *"Refund executed | DR customer credit | CR cash"* is
    that same account being DRAWN DOWN. A refund can only debit a credit the
    books already carry, so the credit has to have been credited when it arose.

Without the third leg the entry could not balance at all, and the only
alternatives are worse: refusing an overpayment makes PE-4 unrecordable, and
posting only the allocated part leaves the books short of the bank by exactly
the credit. REPORTED for confirmation, not silently taken.

**CORRECTED 2026-08-11 (hard-won law 1).** This section used to read *"`undeposited_funds`
(1010) is NOT used here … LE-1 posts a payment to CASH and this seam does what
the worked example does"*. The PO's OQ-143 ruling reverses it, and the sentence
is rewritten rather than left standing beside code that now contradicts it.

**LE-1 IS THE CASUALTY AND IT IS NAMED, NOT GLOSSED.** The ledger workbook's
month books customer payments straight to *"1000 Cash (150.00 + 292.87)
442.87"*, and after this ruling the receipt leg lands in **1010 Undeposited
funds** instead. Two facts keep that from being a frozen-figure change: LE-1 is
a MODULE worked example (04-docs/05-modules/09-ledger/08-worked-examples.md),
not one of B5's ❄️ GT-1..61, and the AMOUNT is identical — only the account
moves, and it moves to the one the same signed chart already names for exactly
this. **The ledger's own documents are NOT edited by this lane** (another lane
owns 09-ledger) — the discrepancy is REPORTED in the lane report and in
12-governance/02-decision-log.md so the ledger lane restates LE-1 rather than
discovering it as a broken test.

**WHY THE BOUNCE CARES.** A returned cheque must unwind the step that actually
happened. Money that was received and never banked is sitting in `1010`, and
reversing a `1000` leg it never had would credit real bank cash the utility
still holds. `reverse_payment_entry` below does not choose: it hands the ORIGINAL
entry to `posting.reverse_entry`, which mirrors whatever was posted, so the
bounce is correct by construction on either side of this ruling.

────────────────────────────────────────────────────────────────────────────
THE TWO DATES, AGAIN — AND THEY GO TO DIFFERENT PLACES
────────────────────────────────────────────────────────────────────────────
`PostingRequest` takes both a BOOK date and a wall-clock moment, and both are
inputs (PO ruling 2026-08-11 closing OQ-107: *"posting and actual dates can
differ; ask actual date to user"*). Payments has exactly two dates and they map
across without a guess:

    entry_date = the payment's CLEARING date.  Cash in the books must agree with
        cash at the bank on a given day, and BR-PAY-019/021 match bank
        statements on the CLEARING date. Booking cash on the posting date would
        put a July entry against an August bank line and BR-LED-007's tie-out
        would drift by construction.
    posted_at  = the payment's POSTING moment. BR-PAY-021 defines it as *"when
        the record is posted to the system"*, which is the ledger's `posted_at`
        word for word. Nothing here reads a clock (BR-TEN-043, gate G6).

────────────────────────────────────────────────────────────────────────────
IDEMPOTENCY IS THE LEDGER'S, AND IT IS KEYED ON THE EVENT (hard rule 6)
────────────────────────────────────────────────────────────────────────────
`posting.posting_key(source_type="payment", source_id=<payment id>,
event="cleared")` → `payment|<uuid>|cleared`. A replay returns the FIRST entry
with `created=False` and writes nothing — so a resumed batch, a retried request
and a double-submitted form all leave one journal entry. The NSF reversal of the
same payment is `payment|<uuid>|nsf_reversed`, a different string, so both
lawfully exist: a document is not the unit of identity, a document plus the
event that happened to it is.

────────────────────────────────────────────────────────────────────────────
THE REFUSAL IS TRANSLATED (DEF-047's lesson)
────────────────────────────────────────────────────────────────────────────
`PostingError` is the ledger's vocabulary. It is caught here and re-raised as
`PaymentRuleError`, so a caller that knows only payments' own type still catches
it — and a bulk import of forty rows records one break on the bad row instead of
losing the batch. A rating refusal once escaped billing's run loop for exactly
this reason and killed a run of five hundred bills.

────────────────────────────────────────────────────────────────────────────
WHAT THIS SEAM DOES NOT BUILD
────────────────────────────────────────────────────────────────────────────
**CORRECTED 2026-08-11 (hard-won law 1).** This section said of NSF, reversal,
refund, write-off and the bank-rec difference that *"None of them has a service
and none is stubbed here"*. Three of the five now do:

  * **NSF / reversal** (BR-PAY-013 / BR-PAY-011) — `reverse_payment_entry`,
    driven by `apps/payments/reversal.py`.
  * **Refund** (BR-PAY-014) — `post_refund_executed` and `reverse_refund_entry`,
    driven by `apps/payments/refunds.py`.
  * **The bank's OWN fee on a returned cheque** — `post_bank_fee`, DR **6800
    Bank fees** / CR cash. Already-decided, not chosen here: *"the bank's fee
    appears on your statement … and lands in the signed bank-fees account
    6800. This is not the customer's NSF fee — they are two different amounts"*
    (12-governance/12-payments-decision-batch.md).

**CORRECTED AGAIN 2026-08-11 (the bank-rec lane).** This paragraph read *"Still
somebody else's and still not stubbed here: write-off (BR-PAY-020) and the
bank-rec explained difference + the second posting step (BR-PAY-019,
`reconciliation.py`)"*. **The bank-rec half now exists here**:
`post_batch_reconciled` and `reverse_batch_reconciliation`, driven by
`apps/payments/reconciliation.py`. That is the SECOND STEP of the OQ-143 ruling —
the one that turns undeposited funds into cash — plus the explained difference of
BR-PAY-019, one line per reason, each to the GL account a human named.

Still somebody else's and still not stubbed here: **write-off** (BR-PAY-020). Its
posting shape is stated in the contract table and belongs to the lane that writes
its rows.

**AND ONE THAT IS THIS LANE'S AND STILL CANNOT BE POSTED: the customer's NSF
FEE.** BR-PAY-013 auto-adds the tenant's NSF charge code and BR-BIL-007 puts the
LINE WRITE in billing, priced from `rating.charges`. `apps/billing/penalty.
penalty_charge_line` refuses on exactly this today — *"rating publishes no
charge-code read"* — so there is no amount to post and none is invented. See
`apps/payments/reversal.py`, which carries the gap as a code on every result.

**THE DEPOSIT CONTRACT ROW IS NOW BUILT (US-PAY-002, 2026-08-15).** This
paragraph used to say it was not, and that `record_payment` refused
`purpose=deposit` outright. Both sentences are false now and are rewritten
rather than left to rot (hard-won law 1). `post_payment_cleared` takes a
`deposit_taken` leg and credits **2000 deposit liability**; the debit stays
UNDEPOSITED under BR-PAY-039 like every other receipt.

⚠ What is STILL owed is on the other side of the boundary and is named in
`apps/payments/purposes.py` rather than here, so one file owns each claim:
nothing calls the read that satisfies BR-BIL-012's first-bill deposit line
(billing's write), and the rate plan's deposit REQUIREMENT is unreadable, so
every deposit recording carries `deposit_requirement_not_checked`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from importlib import import_module
from typing import Any

from apps.payments import settings_seam
from apps.payments.exceptions import PaymentRuleError

#: The ledger's published surfaces, named once so the boundary is greppable
#: from both sides — the discipline `apps/billing/issue.GL_REVENUE_READ` uses.
LEDGER_MODULE = "ledger"
POSTING_MODULE = "posting"
POST_CALL = "post"
POSTING_KEY_CALL = "posting_key"
GL_DESIGNATION_READ = "gl_account_id_for_designation"

#: The designations this contract names. Strings, not an import of
#: `apps.ledger.chart`, for the same reason the seam resolves its callables by
#: name: payments carries no import edge into ledger. The ledger REFUSES an
#: unknown designation rather than answering None, so a typo here fails loudly
#: at the first call instead of silently reporting a mapping gap.
#:
#: All five are among the ELEVEN the PO ruled on 2026-08-11 closing OQ-110, and
#: each maps to an account the ❄️ finance-signed chart already carries: 1000
#: Cash · 1010 Undeposited funds · 1200 Accounts receivable · 2400 Customer
#: credit balances · 6800 Bank fees (B5 line 74).
GL_CASH = "cash"
GL_UNDEPOSITED = "undeposited_funds"
GL_ACCOUNTS_RECEIVABLE = "accounts_receivable"
GL_CUSTOMER_CREDIT = "customer_credit_balance"
GL_BANK_FEES = "bank_fees"
#: US-PAY-002 / BR-PAY-012 — the sixth, added 2026-08-15 with the purpose model.
#: The signed contract row is *"Cash deposit taken (payment purpose=deposit) |
#: cash | deposit liability"*, and the CASH half of it is superseded by
#: BR-PAY-039 exactly as every other receipt leg is: money in a drawer is not
#: realised until the bank confirms it, so the debit is UNDEPOSITED FUNDS and
#: reconciliation moves it. `deposit_liability` is one of the twelve
#: designations the PO ruled (OQ-110) and 2000 is in the ❄️ signed chart.
#:
#: ⚠ OQ-177 asks whether a deposit taken in CASH follows BR-PAY-039 at all, and
#: it is OPEN. This leg does not answer it: the DEBIT side is the same
#: undeposited/cash question every receipt has, and it is decided by
#: BR-PAY-039's existing implementation here, not by anything this constant
#: adds. What is new is only the CREDIT side, which the contract row signs.
GL_DEPOSIT_LIABILITY = "deposit_liability"
#: US-PAY-012 / BR-PAY-020 — the bad-debt account. One of the twelve ruled
#: designations (OQ-110); the seed chart pairs it with 6900. Never a NUMBER:
#: field-map P-17 records what happens when a screen names GL codes instead.
GL_WRITE_OFF = "write_off"
#: `CR-060` T15 (PO ruling 2026-09-03) — the ALLOWANCE, and the account a
#: write-off consumes instead of `write_off` while a tenant books one. The seed
#: chart pairs it with 1290 and, as ever, this is a designation and never a
#: number.
GL_ALLOWANCE_DOUBTFUL = "allowance_doubtful_accounts"

#: The ledger's own words for what happened, and the third part of the replay
#: key. A document is not the unit of identity — a document plus the event that
#: happened to it is — so one payment can lawfully carry a `cleared` entry, an
#: `nsf_reversed` mirror and a `bank_fee` entry, and replaying any of the three
#: writes nothing.
EVENT_CLEARED = "cleared"
#: CR-059 CS-35 — a manual credit or adjustment's own posting event. A distinct
#: string from `cleared`, so the two entries are different keys and one row can
#: never be posted under both (hard rule 6).
EVENT_CREDIT_ADJUSTMENT = "credit_adjustment"
#: CR-059 CS-8 — a customer's credit crossing from one of their accounts to
#: another. Its own string, so a transfer's entry and a receipt's entry can never
#: collide on one posting key even when the same payment row is the source of
#: both (hard rule 6, the same argument `credit_adjustment` makes above).
EVENT_ACCOUNT_TRANSFER = "account_transfer"
EVENT_NSF_REVERSED = "nsf_reversed"
#: CR-059 CS-33 — a PART of a payment came back. Keyed on the REVERSING row
#: rather than on the original, because a payment may now carry several partial
#: reversals and they would otherwise all compose the same posting key: the
#: second would replay the first and the money would never reach the books.
EVENT_PARTIAL_REVERSAL = "partial_reversal"
EVENT_BANK_FEE = "bank_fee"
EVENT_REFUND_ISSUED = "issued"
EVENT_REFUND_VOIDED = "voided"
#: The bank-rec pair (BR-PAY-004/019). A batch may be reconciled, unreconciled
#: and reconciled AGAIN with corrected figures, so both events carry the attempt
#: number: `deposit_batch|<id>|reconciled` then `…|unreconciled:1` then
#: `…|reconciled:1`. Without it the second reconcile would REPLAY the first key
#: and the corrected money would silently never reach the books.
EVENT_RECONCILED = "reconciled"
EVENT_UNRECONCILED = "unreconciled"
SOURCE_PAYMENT = "payment"
SOURCE_REFUND = "refund"
SOURCE_DEPOSIT_BATCH = "deposit_batch"
#: US-PAY-012 / BR-PAY-020 — the bad-debt entry. Its own source type, so the
#: ledger can be asked "what did we write off this year?" without joining
#: through payments (the same reason refunds and batches have their own).
SOURCE_WRITE_OFF = "write_off"
EVENT_WRITTEN_OFF = "written_off"
#: CR-059 CS-25 — the mirror of a write-off that should not have been approved.
#: A DIFFERENT event from `written_off` on the SAME source, exactly as a
#: bounce's `nsf_reversed` differs from its receipt's `cleared`, so both
#: lawfully exist against one write-off and replaying either writes nothing.
EVENT_WRITE_OFF_REVERSED = "write_off_reversed"

ZERO = Decimal("0")


@dataclass(frozen=True)
class PaymentPosting:
    """What one payment left in the books — and whether it left anything.

    `created=False` is the replay no-op, and it is a RESULT rather than an
    exception for the reason `apps/ledger/posting.PostingResult` gives: a
    resumed batch replaying yesterday's handoff is doing the right thing.

    `debits` / `credits` are echoed so a caller can tie out what it asked for
    against what landed (BR-LED-007's discipline, applied at the moment of
    posting rather than a month later on S36).
    """

    entry_id: str
    posting_key: str
    created: bool
    debits: Decimal
    credits: Decimal
    line_count: int


def _resolve(module: str, attribute: str, kind: str) -> Any:
    """The owning module's callable, or None while it has not published one."""
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - defensive
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


def _gl(designation: str) -> Any:
    """The tenant's live account for one designation, or a named refusal.

    Resolved BY DESIGNATION and never by CODE — `apps/ledger/chart.py`'s whole
    reason for existing: a utility may renumber accounts receivable from 1200 to
    1150 and any Python that said `code == "1200"` would be a latent misposting.

    A missing designation is REFUSED, not substituted. The alternative is
    posting a customer's money into a bucket nobody mapped, and unlike an
    unissued bill there is no draft state to repair it from — the entry is
    immutable the moment it lands.
    """
    read = _resolve(LEDGER_MODULE, GL_DESIGNATION_READ, "selectors")
    if read is None:  # pragma: no cover - defensive
        raise PaymentRuleError(
            f"apps.{LEDGER_MODULE}.selectors.{GL_DESIGNATION_READ} is not published, so this "
            "payment cannot find the accounts it must post to. Payments may not pick a GL "
            "account itself (CLAUDE.md rule 5) and money recorded without reaching the books "
            "is money the trial balance will never show.",
            br_ref="BR-LED-001",
        )
    account_id = read(designation)
    if account_id is None:
        raise PaymentRuleError(
            f"no live ledger account carries the {designation!r} designation for this tenant, "
            "so the payment cannot be posted (US-LED-001's 'Payment cleared' contract: DR cash "
            "/ CR accounts receivable). The chart is seeded at provisioning and the designation "
            "is one of the eleven the Product Owner ruled on 2026-08-11 (OQ-110) — a gap here "
            "is a chart to fix on the GL mapping page, never a different bucket to guess.",
            br_ref="BR-BIL-010",
        )
    return account_id


def tender_clearing_account_id(payment: Any) -> Any:
    """The payment method's OWN cash/clearing account, or None for undeposited.

    **CR-008 B-10 (OQ-264 CLOSED 2026-08-17, PO: "10 - A inside CR-008 now").**
    `payment_methods.clearing_gl_account_id` — the column CR-008's second set
    shipped as configuration — now decides which HOLDING account the receipt
    debits. `Payment.method` is the reviewed cross-module FK to tenancy's
    method lookup (B2 §2 / r5 #20), which is how the row is reached without a
    new read surface.

    Three answers, each a different fact:

      * **None** — no method on the payment, or a method with no mapping.
        NULL is unmapped and unmapped is TODAY'S behaviour: the caller debits
        the `undeposited_funds` designation exactly as it has since OQ-143.
      * **the account id** — the mapping exists AND the account is a LIVE row
        of this tenant's own chart, re-checked here through the ledger's
        `account_is_live` because the pick-time validation (CR-008 ruling 3)
        cannot see a deactivation that happened after the pick.
      * **a refusal, BY NAME** — the mapping points at a dead or foreign
        account. Falling back to undeposited would silently move money to an
        account the tenant told us not to use, and posting to the dead row
        would put cash in an account the trial balance treats as retired.
        Neither is a thing to let happen quietly; the fix is the GL mapping
        page and the refusal says so.
    """
    method = getattr(payment, "method", None)
    if method is None:
        return None
    account_id = getattr(method, "clearing_gl_account_id", None)
    if account_id is None:
        return None
    is_live = _resolve(LEDGER_MODULE, "account_is_live", "selectors")
    if not callable(is_live) or not is_live(account_id):
        raise PaymentRuleError(
            f"the {method.code!r} tender points at clearing account {account_id}, which is not "
            "a LIVE account of this tenant's own chart — it was deactivated (or never existed) "
            "after it was picked. The payment is refused whole rather than posted to a retired "
            "account or silently re-routed to undeposited funds; the fix is Settings → "
            "Accounting → GL mapping, section 3 (CR-008 B-10 / OQ-264).",
            br_ref="BR-BIL-010",
        )
    return account_id


#: CR-059 CS-35 — the tenancy read that turns a reason code into the GL account
#: a manual credit or adjustment debits. Named here so the contract is greppable
#: from BOTH sides of the boundary, exactly as `GL_DESIGNATION_READ` is.
TENANCY_MODULE = "tenancy"
REASON_CODE_READ = "reason_code_gl_account"
#: DEF-PAY-5128 / DEF-CUS-5126 — the same list, for the PICKER rather than for
#: the posting. `apps.tenancy.selectors.active_reason_codes` was written by
#: CS-35 for exactly this control and had **no caller at all** until
#: 2026-09-13: the type select shipped, the reason picker beside it did not,
#: and `services._reason_code` refuses a credit or an adjustment with no
#: reason BY NAME — so both non-default options of a live control could only
#: ever fail. Hard-won law 2, in the module that decides where money goes.
REASON_CODE_LIST = "active_reason_codes"


def active_reason_codes() -> list[dict[str, str]]:
    """This tenant's live credit/adjustment reasons, for a clerk's picker.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  THE PICKER AND THE RECORDER READ THE SAME ROWS, ON PURPOSE.         ║
    ╚══════════════════════════════════════════════════════════════════════╝
    `active_reason_codes` selects the SAME `active=True` rows that
    `reason_code_gl_account` — resolved two functions down — validates a
    submitted reason against. That is the whole reason this read goes through
    tenancy rather than being assembled from a seed list here: a picker built
    on its own copy would eventually offer a reason the recorder refuses, and
    the clerk would meet a server error on a value the screen had just given
    them.

    **IT IS NOT `GET /lookups/reason_codes`, AND THAT IS NOT A DUPLICATE
    READ.** The Settings route for this list is gated on
    `SettingsReadAnyWriteSystemAdmin`, and A4 gives the **Billing Clerk no
    `settings_lookups` cell at all** — so the one role A4 lets *Request* an
    adjustment (`adjustment_approval`: billing_clerk = Request) cannot read the
    reasons through Settings. This is the clerk-facing read of the same rows,
    on the surface that role can already reach.

    Returns `[]` — never a seeded five — when a tenant has deactivated every
    reason. Offering the seeds back would offer codes the recorder refuses,
    which is the same posture `usePaymentMethods` takes on the S22 form.
    """
    read = _resolve(TENANCY_MODULE, REASON_CODE_LIST, "selectors")
    if read is None:  # pragma: no cover - tenancy publishes it
        raise PaymentRuleError(
            f"apps.{TENANCY_MODULE}.selectors.{REASON_CODE_LIST} is not published, so this "
            "utility's own reasons cannot be listed. A picker filled from anywhere else "
            "would offer a reason the recording path then refuses by name.",
            br_ref="BR-TEN-036",
        )
    return [{"code": str(row["code"]), "name": str(row["name"])} for row in read()]


def credit_adjustment_debit_account_id(reason_code: str) -> tuple[Any, str]:
    """The account a manual CREDIT or ADJUSTMENT debits: `(account_id, source)`.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  IT IS NEVER UNDEPOSITED FUNDS AND NEVER A TENDER'S CLEARING         ║
    ║  ACCOUNT. NO CASH ARRIVED.                                           ║
    ╚══════════════════════════════════════════════════════════════════════╝
    CR-059 CS-35, verbatim: a credit or adjustment *"posts to its own ledger
    account, not to undeposited funds"*. Debiting a holding account would put
    money the utility never received into the balance the bank reconciliation
    then has to explain, and there is no bank line coming to explain it with —
    which is the same reason CS-35 keeps these rows out of the deposit batch.

    **NEITHER SIDE OF THIS IS INVENTED HERE. BOTH ARE RULED.**

      * **The reason's own account, when the tenant mapped one.** CR-008 ruling
        9 (PO 2026-08-17, *"make it separate"*) put `default_gl_account_id` on
        `reason_codes` so *"a billing error credit and a goodwill credit can
        post to different accounts"*. That column has existed since 2026-08-17
        and had never had a query run against it; this is the query.
      * **The `write_off` designation, when they did not.** PO 2026-08-12
        (OQ-105 / OQ-168), verbatim *"a separate write-off account"* — the same
        answer `apps.billing.corrections.credit_only_gl_accounts` gives a
        goodwill concession, and the `reason_codes` model docstring already
        says an unmapped reason *"posts to the designation the correction path
        already resolves"*. So the two paths cannot drift apart by default.

    Refuses BY NAME when the code is not one of this tenant's ACTIVE reasons.
    Falling back to write-off for an unrecognised reason would file a credit
    under a policy nobody chose and leave *"how much did we give away last year,
    and why"* with an answer that is quietly wrong.
    """
    read = _resolve(TENANCY_MODULE, REASON_CODE_READ, "selectors")
    if read is None:  # pragma: no cover - tenancy publishes it
        raise PaymentRuleError(
            f"apps.{TENANCY_MODULE}.selectors.{REASON_CODE_READ} is not published, so the "
            "ledger account this credit belongs in cannot be read. Payments may not pick a GL "
            "account itself (CLAUDE.md rule 5) and a credit recorded without reaching the "
            "books is money given away that the trial balance will never show.",
            br_ref="BR-LED-001",
        )
    row = read(reason_code)
    if row is None:
        raise PaymentRuleError(
            # CR-059 CS-35, in the comment rather than the sentence (G28).
            f"{reason_code!r} is not one of this utility's active reasons. A credit or "
            "adjustment carries a reason from the tenant's own list — the list on Settings → "
            "Configure → Reason codes — so that 'how much did we give away last year, and "
            "why' has an answer. It is refused rather than filed under a default: a credit "
            "posted under a reason nobody recognises is worse than one not recorded.",
            br_ref="BR-TEN-036",
        )
    mapped = row.get("gl_account_id")
    if mapped is None:
        # A real state, not a gap (the `reason_codes` model docstring says so in
        # as many words). The ruled fallback is the concession's own account.
        return _gl(GL_WRITE_OFF), "write_off_designation"
    is_live = _resolve(LEDGER_MODULE, "account_is_live", "selectors")
    if not callable(is_live) or not is_live(mapped):
        raise PaymentRuleError(
            f"the {reason_code!r} reason points at ledger account {mapped}, which is not a LIVE "
            "account of this tenant's own chart — it was deactivated (or never existed) after "
            "it was mapped. The credit is refused whole rather than posted to a retired "
            # The mapping is CR-008 ruling 9's column — in the comment rather
            # than the sentence (G28); the clerk needs the screen, not the id.
            "account or silently re-routed to write-off; the fix is Settings → Accounting → GL "
            "mapping.",
            br_ref="BR-BIL-010",
        )
    return mapped, "reason_code_mapping"


def post_credit_adjustment(
    *,
    payment: Any,
    reason_code: str,
    applied_to_bills: Decimal,
    credit_carried: Decimal,
    entry_date: date,
    posted_at: datetime,
    actor: Any = None,
) -> PaymentPosting:
    """A manual credit or adjustment reaching the books (CR-059 CS-35).

        DR  the reason's own account (or write-off)      amount
        CR  accounts receivable                          what met bills
        CR  customer credit balance                      what carried

    **THE DEBIT LEG IS THE WHOLE DIFFERENCE FROM `post_payment_cleared`.** The
    credit legs are identical and deliberately so: a credit meets open bills
    exactly as a payment does (CS-35: *"the allocation engine needs no
    change"*), so what it settles is receivables and what it does not settle is
    a credit the customer holds. What changed is that nothing arrived at a bank,
    so nothing debits cash, undeposited funds or a tender's clearing account.

    Payments composes the request and writes no journal line; the ledger posting
    service is the sole writer (CLAUDE.md rule 5) and composes the idempotency
    key itself (rule 6). The event is `credit_adjustment`, so this entry and a
    receipt's `cleared` entry are different strings and a row can never be
    posted under both.

    ⚠ **A CONCESSION RECORDED FOR BILLING DOES NOT COME THROUGH HERE.** CR-059
    CS-38's one-posting ruling is that billing's `execute_credit_only` has
    already emitted the single balanced entry for a goodwill concession, so
    `services.record_payment` skips this call entirely for such a row and says
    so on `problems`. See that function's docstring — this is the branch that
    would otherwise invent 25.00.
    """
    amount = payment.amount
    if not isinstance(amount, Decimal):  # pragma: no cover - the model gives a Decimal
        raise PaymentRuleError(
            f"credit amount {amount!r} is not a Decimal — money is NUMERIC(18,6) and never a "
            "float (CLAUDE.md rule 2). Refused rather than converted.",
            br_ref="BR-PAY-002",
        )
    if applied_to_bills + credit_carried != amount:
        raise PaymentRuleError(
            f"credit {payment.payment_no or payment.pk} is {amount} but the allocation reports "
            f"{applied_to_bills} against bills and {credit_carried} carried "
            f"({applied_to_bills + credit_carried}). Every cent of a credit is on a bill or in "
            "the customer's credit balance; an entry built from these figures would put the "
            "books out by the difference.",
            br_ref="BR-PAY-012",
        )

    debit_account_id, debit_source = credit_adjustment_debit_account_id(reason_code)
    posting = import_module(f"apps.{LEDGER_MODULE}.{POSTING_MODULE}")
    compose_key = _resolve(LEDGER_MODULE, POSTING_KEY_CALL, POSTING_MODULE)
    write = _resolve(LEDGER_MODULE, POST_CALL, POSTING_MODULE)
    if compose_key is None or write is None:  # pragma: no cover - defensive
        raise PaymentRuleError(
            f"apps.{LEDGER_MODULE}.{POSTING_MODULE} publishes neither {POST_CALL} nor "
            f"{POSTING_KEY_CALL}, so this credit cannot reach the books. Payments may not "
            "write journal lines itself — that service is the sole writer (CLAUDE.md rule 5).",
            br_ref="BR-LED-001",
        )

    dimensions = {
        "source_type": SOURCE_PAYMENT,
        "source_id": payment.pk,
        "account_id": payment.account_id,
    }
    lines = [
        posting.PostingLine(
            ledger_account_id=debit_account_id, side="debit", amount=amount, **dimensions
        )
    ]
    # Only legs that MOVED money get a line, the same rule every other posting
    # in this seam applies. A 0.00 leg is a line nobody can explain.
    if applied_to_bills > ZERO:
        lines.append(
            posting.PostingLine(
                ledger_account_id=_gl(GL_ACCOUNTS_RECEIVABLE),
                side="credit",
                amount=applied_to_bills,
                **dimensions,
            )
        )
    if credit_carried > ZERO:
        lines.append(
            posting.PostingLine(
                ledger_account_id=_gl(GL_CUSTOMER_CREDIT),
                side="credit",
                amount=credit_carried,
                **dimensions,
            )
        )

    request = posting.PostingRequest(
        posting_key=compose_key(
            source_type=SOURCE_PAYMENT, source_id=payment.pk, event=EVENT_CREDIT_ADJUSTMENT
        ),
        entry_date=entry_date,
        posted_at=posted_at,
        currency=payment.currency,
        lines=tuple(lines),
        source_type=SOURCE_PAYMENT,
        source_id=payment.pk,
        memo=f"{payment.type.replace('_', ' ').capitalize()} {payment.payment_no or payment.pk}",
        audit_context={
            "payment_no": payment.payment_no,
            "type": payment.type,
            "reason_code": reason_code,
            "debit_account_source": debit_source,
            "applied_to_bills": str(applied_to_bills),
            "credit_carried": str(credit_carried),
        },
    )
    try:
        result = write(request, actor=actor)
    except posting.PostingError as refusal:  # the ledger's vocabulary → payments'
        raise PaymentRuleError(
            f"credit {payment.payment_no or payment.pk} could not be posted to the books: "
            f"{refusal}",
            br_ref="BR-LED-001",
        ) from refusal
    return PaymentPosting(
        entry_id=result.entry_id,
        posting_key=result.posting_key,
        created=result.created,
        debits=result.debits,
        credits=result.credits,
        line_count=result.line_count,
    )


def entry_date_for_posting(posted_on: date) -> tuple[date, dict[str, Any] | None]:
    """The date a payment's entry is booked on — its POSTING date, forwarded
    out of a closed period (`CR-186-BRC10`, PO 2026-10-21 ruling 3, *"Option
    B - accept it"*).

    Since 2026-10-21 a payment is applied and journalled AT POSTING, so the
    entry is dated the posting date. When that falls in a CLOSED accounting
    period the ledger's own BR-TEN-038 auto-forward moves it to the first open
    period — `apps.ledger.close.resolve_entry_date`, the ONE implementation,
    which `ledger/posting._refuse_if_period_closed` names as the caller's job
    for *"a payment that genuinely arrived late"*. The closed period is
    untouched, and the PAYMENT keeps its own posting date, which is still the
    date late fees read (BR-PAY-021).

    Returns `(entry_date, note)`; `note` is None unless the date moved, and
    then it is the ledger's `period_closed_auto_forwarded` row, which the
    caller carries on its result.
    """
    resolve = _resolve(LEDGER_MODULE, "resolve_entry_date", "close")
    if resolve is None:  # pragma: no cover - defensive
        return posted_on, None
    close = import_module(f"apps.{LEDGER_MODULE}.close")
    try:
        return resolve(posted_on)
    except close.CloseError as refusal:
        raise PaymentRuleError(
            f"this payment's posting date {posted_on.isoformat()} falls in a closed period and "
            f"no open period follows it to forward the entry into: {refusal}",
            br_ref="BR-TEN-038",
        ) from refusal


def post_payment_cleared(
    *,
    payment: Any,
    applied_to_bills: Decimal,
    credit_carried: Decimal,
    entry_date: date,
    posted_at: datetime,
    actor: Any = None,
    deposit_taken: Decimal | None = None,
    clearing_account_id: Any = None,
) -> PaymentPosting:
    """US-LED-001's *"Payment cleared"* — DR the tender's holding account / CR AR.

    ⚠ **AMENDED 2026-08-18 (CR-008 B-10).** The debit leg used to be
    `undeposited_funds` for every tender; it is now `clearing_account_id` when
    the caller resolved one (`tender_clearing_account_id` above) and
    undeposited otherwise. OQ-143's law is UNTOUCHED — money is still not
    realised until the bank confirms it; only WHICH holding account holds the
    unconfirmed money is the tender's choice. The matching reconciliation leg
    moved in this same change (`post_batch_reconciled`'s `undeposited_credits`),
    because the two moving apart is the trial-balance fault the decision log
    of 2026-08-17 measured in advance.

    Called from INSIDE `record_payment`'s transaction, so a payment and its
    journal entry are one atomic fact. The alternative — post afterwards,
    outside — produces the state nothing can repair: an immutable payment row
    with no entry in the books and no code path left that would ever write one.

    Every figure is the caller's. This function computes no money: it splits the
    amount across the two credit legs exactly as the allocator reported them,
    and refuses the request if they do not foot to the payment (below). The
    ledger then refuses it a second time if debits ≠ credits — two independent
    checks on the one arithmetic fact this seam touches, because a posting that
    is wrong here is wrong in the trial balance forever.

    Raises `PaymentRuleError` for everything a human can act on, including the
    ledger's own `PostingError` translated into this module's vocabulary.
    """
    amount = payment.amount
    if not isinstance(amount, Decimal):  # pragma: no cover - the model gives a Decimal
        raise PaymentRuleError(
            f"payment amount {amount!r} is not a Decimal — money is NUMERIC(18,6) and never a "
            "float (CLAUDE.md rule 2). Refused rather than converted: a conversion would hide "
            "the place where money became binary.",
            br_ref="BR-PAY-002",
        )
    held = ZERO if deposit_taken is None else deposit_taken
    if applied_to_bills + credit_carried + held != amount:
        raise PaymentRuleError(
            f"payment {payment.payment_no or payment.pk} is {amount} but the allocation reports "
            f"{applied_to_bills} against bills, {credit_carried} carried as credit and {held} "
            f"held as a deposit ({applied_to_bills + credit_carried + held}). Every cent a "
            "customer handed over is on a bill, in their credit balance, or held as a deposit "
            "(BR-PAY-010 / BR-PAY-012); an entry built from these figures would put the books "
            "out against the bank by the difference.",
            br_ref="BR-PAY-012",
        )

    posting = import_module(f"apps.{LEDGER_MODULE}.{POSTING_MODULE}")
    compose_key = _resolve(LEDGER_MODULE, POSTING_KEY_CALL, POSTING_MODULE)
    write = _resolve(LEDGER_MODULE, POST_CALL, POSTING_MODULE)
    if compose_key is None or write is None:  # pragma: no cover - defensive
        raise PaymentRuleError(
            f"apps.{LEDGER_MODULE}.{POSTING_MODULE} publishes neither {POST_CALL} nor "
            f"{POSTING_KEY_CALL}, so this payment cannot reach the books. Payments may not "
            "write journal lines itself — that service is the sole writer (CLAUDE.md rule 5).",
            br_ref="BR-LED-001",
        )

    dimensions = {
        "source_type": SOURCE_PAYMENT,
        "source_id": payment.pk,
        "account_id": payment.account_id,
    }
    lines = [
        # PO ruling 2026-08-11 (OQ-143 CLOSED): the RECEIPT leg debits a
        # HOLDING account, never cash. *"until bank record and reconcilaition
        # confirm it it is not realised"*. Reconciliation moves it to 1000 Cash
        # in a second entry that belongs to the bank-rec lane. Since CR-008
        # B-10 (2026-08-18) the holding account is the tender's own clearing
        # account when one is mapped, and 1010 Undeposited funds otherwise.
        posting.PostingLine(
            ledger_account_id=(
                clearing_account_id if clearing_account_id is not None else _gl(GL_UNDEPOSITED)
            ),
            side="debit",
            amount=amount,
            **dimensions,
        )
    ]
    # Only legs that MOVED money get a line — the same rule the allocator
    # applies to its rows. A 0.00 credit leg would be a journal line for money
    # that did not move, and every one of them would have to be explained to
    # whoever reads the entry.
    if applied_to_bills > ZERO:
        lines.append(
            posting.PostingLine(
                ledger_account_id=_gl(GL_ACCOUNTS_RECEIVABLE),
                side="credit",
                amount=applied_to_bills,
                **dimensions,
            )
        )
    if credit_carried > ZERO:
        lines.append(
            posting.PostingLine(
                ledger_account_id=_gl(GL_CUSTOMER_CREDIT),
                side="credit",
                amount=credit_carried,
                **dimensions,
            )
        )
    if held > ZERO:
        # BR-PAY-012 / US-PAY-002 TC-1: a deposit is a LIABILITY, never revenue
        # and never a credit on account. The distinction is the whole reason the
        # purpose exists — a deposit credited to 2400 would auto-apply to the
        # next bill (BR-PAY-010) and the utility would spend money it is holding.
        lines.append(
            posting.PostingLine(
                ledger_account_id=_gl(GL_DEPOSIT_LIABILITY),
                side="credit",
                amount=held,
                **dimensions,
            )
        )

    key = compose_key(source_type=SOURCE_PAYMENT, source_id=payment.pk, event=EVENT_CLEARED)
    request = posting.PostingRequest(
        posting_key=key,
        entry_date=entry_date,
        posted_at=posted_at,
        currency=payment.currency,
        lines=tuple(lines),
        source_type=SOURCE_PAYMENT,
        source_id=payment.pk,
        memo=f"Payment {payment.payment_no or payment.pk}",
        audit_context={
            "payment_no": payment.payment_no,
            "applied_to_bills": str(applied_to_bills),
            "credit_carried": str(credit_carried),
            "deposit_held": str(held),
        },
    )
    try:
        result = write(request, actor=actor)
    except posting.PostingError as refusal:  # the ledger's vocabulary → payments'
        raise PaymentRuleError(
            f"payment {payment.payment_no or payment.pk} could not be posted to the books: "
            f"{refusal}",
            br_ref="BR-LED-001",
        ) from refusal
    return PaymentPosting(
        entry_id=result.entry_id,
        posting_key=result.posting_key,
        created=result.created,
        debits=result.debits,
        credits=result.credits,
        line_count=result.line_count,
    )


def _write_off_memo_subject(write_off: Any) -> str:
    """THE WRITE-OFF'S NAME IN A CLERK'S WORDS, NEVER ITS DATABASE ID (`DEF-LED-6661`).

    This memo is stored on the journal entry and rendered VERBATIM in the MEMO
    column of Finance > General ledger > Journal and of the entries list under
    the trial balance. It read `Write-off 01a0d522-edd3-710f-84f7-16035e9aec91`
    on the live demo tenant on 2026-09-24 — a uuid7 primary key on a clerk's
    screen, which **B14 rule 31** forbids in terms: *"no Databse ID on screen -
    that is a rule"*.

    **A write-off has no number of its own**, and inventing one would be a
    schema change dressed up as a copy fix. What it does have is the ACCOUNT the
    debt sat on, and `accounts.account_no` (`A-10432`, allocated from the
    tenancy series, BR-TEN-035) is the string a clerk and a customer both say
    out loud. Every other memo in this seam already names its subject that way —
    `Payment {payment_no}`, `Bill {invoice_no} issued`, `Deposit batch {code}
    reconciled` — each with a `or pk` fallback this one had without the human
    half in front of it.

    **THE PROVENANCE IS NOT DELETED, IT LEAVES THE SENTENCE.** The entry still
    carries `source_type='write_off'` and `source_id=<the pk>` on every line's
    dimensions, and the posting key still composes from the pk, so the drill
    from an entry back to the row is untouched. Only what the clerk READS
    changes — which is exactly the split rule 31's own worked cases take.

    Returns the empty string when the account cannot be named, and the callers
    then write a memo with no subject at all rather than fall back to the pk:
    `account_no` is blank on an account migrated under the 2026-08-27 ruling,
    and a blank there must not reopen the defect by the back door.
    """
    account = getattr(write_off, "account", None)
    return str(getattr(account, "account_no", "") or "").strip()


def _write_off_memo(write_off: Any, *, prefix: str) -> str:
    """`Write-off — account A-10432`, or `Write-off` when the account is unnamed."""
    subject = _write_off_memo_subject(write_off)
    return f"{prefix} — account {subject}" if subject else prefix


@dataclass(frozen=True)
class WriteOffPosting(PaymentPosting):
    """A `PaymentPosting` that also names the GL account it debited.

    The write-off row stores `gl_account_id` (r12 #11: *"bad-debt GL"*) and the
    account is resolved BY DESIGNATION here, so the row records WHICH account
    this tenant's chart designates rather than a number a screen typed. Field-map
    P-17 is the defect that follows from the other approach — the prototype
    names three GL codes that appear in no signed chart, and one of them means
    the OPPOSITE of its label.
    """

    gl_account_id: Any = None


def _write_off_debit_designation() -> str:
    """Which account a write-off CHARGES — and it is a tenant policy question.

    **`CR-060` T15, PO ruling 2026-09-03.** Two lawful accounting policies, and
    a utility picks one:

      * **DIRECT (the default, and BR-PAY-020 as signed).** Nothing was provided
        for in advance, so giving the debt up is when the expense is taken:
        `DR 6900 Bad debt / CR 1200 AR`.
      * **ALLOWANCE.** The expense was ALREADY taken, at the month-end estimate
        (`DR 6900 / CR 1290`). Giving the debt up therefore CONSUMES what was
        provided: `DR 1290 / CR 1200`.

    ⚠ **IF BOTH HAPPEN, BAD DEBT IS EXPENSED TWICE**, and it is the exact shape
    of `DEF-3380` — a settled supplier bill counted in the balanced section AND
    summed again in the register section, handing an ERP **$4,340.00** against
    **$3,100.00** actually bought. There is ONE switch and it is here.

    ⚠ **THE SETTING DECIDES, NOT THE PRESENCE OF AN ACCOUNT.** `1290` can appear
    on a chart because somebody was exploring the GL mapping page; a policy is
    something a utility chose. Reading the account's existence instead would
    move a money path on a UI accident, and hard rule 4 leaves no way to correct
    the entry afterwards.

    **The refusal when the seam cannot be read is `settings_seam`'s own**, and it
    is deliberate rather than a defaulted `False`: an unreachable setting is not
    a setting, and reading the policy as OFF would charge `6900` for a utility
    that has already provided for this debt.
    """
    return (
        GL_ALLOWANCE_DOUBTFUL
        if settings_seam.allowance_for_doubtful_accounts_enabled()
        else GL_WRITE_OFF
    )


def post_write_off(
    *,
    write_off: Any,
    entry_date: date,
    posted_at: datetime,
    actor: Any = None,
) -> WriteOffPosting:
    """**DR write-off / CR accounts receivable** (BR-PAY-020, US-PAY-012 TC-2).

    ⚠ **NARROWED 2026-09-03 (`CR-060` T15), NOT SUPERSEDED.** The line above is
    still exactly what happens for every tenant that does not book an allowance
    — which is the default and, on the day this landed, all of them. A tenant
    who HAS switched the allowance on debits `1290` instead, because the expense
    was already taken at the estimate. See `_write_off_debit_designation`.

    Worked, on TC-2's own figures: DR write-off **948.20** / CR accounts
    receivable **948.20** — balanced, and the account's outstanding AR falls by
    exactly what a human approved.

    `write_off` is the designation the PO ruled on 2026-08-11 (OQ-110's eleven);
    the seed chart pairs it with **6900**, and this seam never names a NUMBER —
    a tenant whose chart designates a different account gets their own.

    Called ONLY from `writeoffs.approve_write_off`, inside its transaction: a
    write-off row that committed without its entry would be receivables reduced
    in the product and not in the books.
    """
    amount = write_off.amount
    if not isinstance(amount, Decimal):  # pragma: no cover - the model gives a Decimal
        raise PaymentRuleError(
            f"write-off amount {amount!r} is not a Decimal — money is NUMERIC(18,6) and never a "
            "float (CLAUDE.md rule 2).",
            br_ref="BR-PAY-020",
        )
    if amount <= ZERO:
        raise PaymentRuleError(
            "a write-off posts DR write-off / CR AR of a POSITIVE amount; its direction is the "
            "posting's, never the figure's sign (BR-PAY-020).",
            br_ref="BR-PAY-020",
        )

    posting = import_module(f"apps.{LEDGER_MODULE}.{POSTING_MODULE}")
    compose_key = _resolve(LEDGER_MODULE, POSTING_KEY_CALL, POSTING_MODULE)
    if compose_key is None:  # pragma: no cover - defensive
        raise PaymentRuleError(
            f"apps.{LEDGER_MODULE}.{POSTING_MODULE} publishes no {POSTING_KEY_CALL}, so this "
            "write-off cannot reach the books. Payments may not write journal lines itself "
            "(CLAUDE.md rule 5).",
            br_ref="BR-LED-001",
        )
    # CR-060 T15 — `write_off` (6900 Bad debt) or `allowance_doubtful_accounts`
    # (1290), decided by the tenant's own policy and by nothing else. The
    # variable keeps its name because everything downstream of it — the request,
    # the result, the reversal's mirror — is about the DEBIT side of a write-off
    # and does not care which account carries it.
    gl_write_off = _gl(_write_off_debit_designation())
    dimensions = {
        "source_type": SOURCE_WRITE_OFF,
        "source_id": write_off.pk,
        "account_id": write_off.account_id,
    }
    request = posting.PostingRequest(
        posting_key=compose_key(
            source_type=SOURCE_WRITE_OFF, source_id=write_off.pk, event=EVENT_WRITTEN_OFF
        ),
        entry_date=entry_date,
        posted_at=posted_at,
        currency=write_off.currency,
        lines=(
            posting.PostingLine(
                ledger_account_id=gl_write_off, side="debit", amount=amount, **dimensions
            ),
            posting.PostingLine(
                ledger_account_id=_gl(GL_ACCOUNTS_RECEIVABLE),
                side="credit",
                amount=amount,
                **dimensions,
            ),
        ),
        source_type=SOURCE_WRITE_OFF,
        source_id=write_off.pk,
        memo=_write_off_memo(write_off, prefix="Write-off"),
        audit_context={"reason": write_off.reason, "amount": str(amount)},
    )
    result = _write(posting, request, actor=actor, subject=f"write-off {write_off.pk}")
    return WriteOffPosting(
        entry_id=result.entry_id,
        posting_key=result.posting_key,
        created=result.created,
        debits=result.debits,
        credits=result.credits,
        line_count=result.line_count,
        gl_account_id=gl_write_off,
    )


def reverse_write_off_entry(
    *,
    write_off: Any,
    entry_date: date,
    posted_at: datetime,
    memo: str | None = None,
    actor: Any = None,
) -> WriteOffPosting:
    """Unwind a bad-debt entry with the LEDGER'S OWN MIRROR (CR-059 CS-25).

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  THIS FUNCTION COMPOSES NO LINES. CS-25 ASKS FOR THAT IN TERMS.       ║
    ╚══════════════════════════════════════════════════════════════════════╝
    CS-25's Backend line, verbatim: *"a `reverse_write_off` service **asking the
    ledger for its own mirror — never composing a compensating entry**."* So
    this hands `apps.ledger.posting.reverse_entry` the original entry id and it
    copies it with the sides swapped — *"same GLs, sides swapped"*, US-LED-003
    §5's own signed words.

    Worked, on US-PAY-012 TC-2's own figures. The approval posted
    **DR write-off 948.20 / CR accounts receivable 948.20**; this mirror posts
    **DR accounts receivable 948.20 / CR write-off 948.20**, so bad debt for the
    period nets to **0.00** and the receivable is back on the books at the full
    948.20. Nothing is netted and nothing is dropped: all three rows — request,
    approval entry, mirror — survive forever, which is what makes *"we wrote it
    off in August and put it back in September"* an answerable question.

    **Why not compose DR AR / CR write-off here.** The tenant's `write_off`
    designation can be re-pointed at a different chart account between the
    approval and the correction. A compensating entry composed today would
    credit TODAY's designated account while the original debited YESTERDAY's,
    and the two would never net — the same argument `reconciliation` makes for
    reading each member receipt's own legs rather than today's tender mapping.
    The mirror copies what was posted, and the original is immutable, so what is
    copied is what was posted.

    **The reversal is linked, not netted** — `reverse_entry` sets `reversal_of`
    on the mirror, so both halves render forever and neither can be mistaken for
    an independent adjustment.

    Raises `PaymentRuleError` when the write-off never reached the books. A row
    with no `journal_entry_id` was never approved (or predates the stamp), and
    reversing "nothing" silently is how a correction comes to leave the books
    unchanged while the product says the debt is back.
    """
    entry_id = getattr(write_off, "journal_entry_id", None)
    if entry_id is None:
        # The stamp this relies on is US-PAY-012 TC-2's, and it is named HERE
        # rather than in the sentence: refusal prose reaches the audit row and
        # the server log, and G28 ratchets internal references in it downwards.
        # `br_ref` below is the machine-readable half.
        raise PaymentRuleError(
            f"write-off {write_off.pk} names no journal entry, so there is nothing in the books "
            "to unwind. An approved write-off is stamped with its entry id in the same "
            "transaction that posts it; a row without one was never approved, and reversing it "
            "would announce a correction the books never received.",
            br_ref="BR-PAY-020",
        )
    posting = import_module(f"apps.{LEDGER_MODULE}.{POSTING_MODULE}")
    compose_key = _resolve(LEDGER_MODULE, POSTING_KEY_CALL, POSTING_MODULE)
    mirror = _resolve(LEDGER_MODULE, "reverse_entry", POSTING_MODULE)
    if compose_key is None or mirror is None:  # pragma: no cover - defensive
        raise PaymentRuleError(
            f"apps.{LEDGER_MODULE}.{POSTING_MODULE} publishes no reverse_entry, so this "
            "write-off cannot be unwound. Payments may not write journal lines itself "
            "(CLAUDE.md rule 5), and it may not hand-compose a compensating entry either.",
            br_ref="BR-LED-003",
        )
    key = compose_key(
        source_type=SOURCE_WRITE_OFF,
        source_id=write_off.pk,
        event=EVENT_WRITE_OFF_REVERSED,
    )
    try:
        result = mirror(
            entry_id,
            posting_key=key,
            entry_date=entry_date,
            posted_at=posted_at,
            memo=memo or _write_off_memo(write_off, prefix="Reversal of write-off"),
            actor=actor,
        )
    except posting.PostingError as refusal:
        raise PaymentRuleError(
            f"write-off {write_off.pk} could not be unwound in the books: {refusal}",
            br_ref="BR-LED-003",
        ) from refusal
    return WriteOffPosting(
        entry_id=result.entry_id,
        posting_key=result.posting_key,
        created=result.created,
        debits=result.debits,
        credits=result.credits,
        line_count=result.line_count,
        # The SAME designated account the approval debited, carried onto the
        # reversing row so the pair reads as one correction. Read from the
        # original row rather than re-resolved, for the reason above.
        gl_account_id=getattr(write_off, "gl_account_id", None),
    )


def _write(posting: Any, request: Any, *, actor: Any, subject: str) -> PaymentPosting:
    """Hand one composed request to the ledger and translate its refusal.

    Every posting in this module funnels through here so the DEF-047 lesson —
    the callee's REFUSAL is as much a part of the contract as its result — is
    applied once rather than copied five times.
    """
    write = _resolve(LEDGER_MODULE, POST_CALL, POSTING_MODULE)
    if write is None:  # pragma: no cover - defensive
        raise PaymentRuleError(
            f"apps.{LEDGER_MODULE}.{POSTING_MODULE} publishes no {POST_CALL}, so {subject} "
            "cannot reach the books. Payments may not write journal lines itself — that "
            "service is the sole writer (CLAUDE.md rule 5).",
            br_ref="BR-LED-001",
        )
    try:
        result = write(request, actor=actor)
    except posting.PostingError as refusal:  # the ledger's vocabulary → payments'
        raise PaymentRuleError(
            f"{subject} could not be posted to the books: {refusal}", br_ref="BR-LED-001"
        ) from refusal
    return PaymentPosting(
        entry_id=result.entry_id,
        posting_key=result.posting_key,
        created=result.created,
        debits=result.debits,
        credits=result.credits,
        line_count=result.line_count,
    )


def post_account_transfer(
    *,
    source_payment: Any,
    destination_payment: Any,
    applied_to_bills: Decimal,
    credit_carried: Decimal,
    entry_date: date,
    posted_at: datetime,
    actor: Any = None,
    held: Decimal = ZERO,
) -> PaymentPosting:
    """CR-059 CS-8 — one balanced movement recorded on BOTH accounts.

    CS-8's one new rule, verbatim: *"A transfer between two accounts of the same
    customer is one balanced movement recorded on both, never a refund on one
    plus a payment on the other."* That sentence is a statement about the BOOKS
    before it is one about the screens, and this is where it is honoured: ONE
    entry, whose debit carries the source account's dimension and whose credits
    carry the destination's.

        DR  2400 customer credit balance    57.13   account = SOURCE
        CR  1200 accounts receivable        57.13   account = DESTINATION

    and, when the destination cannot absorb it all, the remainder is a second
    credit leg on 2400 under the DESTINATION's dimension:

        DR  2400 customer credit balance   100.00   account = SOURCE
        CR  1200 accounts receivable        57.13   account = DESTINATION
        CR  2400 customer credit balance    42.87   account = DESTINATION

    **WHY THE DEBIT IS 2400 AND NOT CASH, UNDEPOSITED FUNDS OR A CLEARING
    ACCOUNT.** No money arrived and none left the building. What moved is the
    utility's OBLIGATION: it held 57.13 for the customer against one account and
    now holds it against another, or has used it to settle that account's
    receivable. Debiting a cash account would state that the utility's bank
    balance fell, which is the one thing that certainly did not happen, and the
    trial balance would disagree with the statement by the amount of every
    transfer ever made.

    **THE REFUND ALTERNATIVE IS WHAT THIS RULE FORBIDS, AND THE DIFFERENCE IS
    REAL.** A refund on the source plus a payment on the destination would post
    DR 2400 / CR 1000 cash and then DR 1010 / CR 1200 — two entries, a cheque
    that was never written, and a bank reconciliation carrying an outgoing item
    nobody can find on a statement.

    ════════════════════════════════════════════════════════════════════════
    CR-059 CS-22 — THE DEPOSIT CARRY-FORWARD IS **2300 → 2300**, AND IT IS A
    DIFFERENT ENTRY FROM THE ONE ABOVE ON PURPOSE
    ════════════════════════════════════════════════════════════════════════
    PO ruling 2026-09-01 (CR-059 §6 Q2, option (b) CHOSEN): a customer who
    closes one account and opens another is **not asked for a second deposit** —
    *"offer it forward: the move-in screen says the deposit is held on the old
    account and the clerk accepts it"*. The cost the PO was shown alongside it:
    *"money has to move between two accounts, which nothing in the product does
    today"*. This is where that movement reaches the books.

        DR  2300 customer deposit liability  150.00   account = SOURCE
        CR  2300 customer deposit liability  150.00   account = DESTINATION

    **WHY IT IS NOT THE ENTRY ABOVE, AND THIS IS THE WHOLE OF CS-22.** A CREDIT
    is the customer's money sitting against their own bills, so settling the
    destination's receivable with it (CR 1200) is exactly right. A **DEPOSIT is
    security the utility HOLDS and owes back** (BR-PAY-012 / US-PAY-002 TC-1):
    it lives on 2300, and it must NOT meet a bill on arrival. Carrying it
    through the credit legs above would have credited 1200 receivables and
    **silently converted returnable customer security into revenue** — on a
    perfectly balanced entry, with every test green, and the customer would then
    be asked for a fresh deposit later. That is the failure this branch exists
    to make impossible, and the two guards below are what make it impossible
    rather than merely unlikely.

    **NOTHING IS REALISED AND NOTHING IS DISCHARGED.** The utility held 150.00
    of this customer's money before the entry and holds 150.00 after it; only
    the account dimension moved. The 2300 balance for the tenant is unchanged,
    which is what keeps BR-LED-007's deposit tie-out equal across a carry —
    the customer REGISTER moves by the same 150.00 in `apps/payments/transfer.py`
    and neither side of that tie-out can drift.

    Every figure is the caller's and this function computes no money: it refuses
    the request if the legs do not foot to the amount moved (below), and the
    ledger refuses it a second time if debits ≠ credits — two independent checks
    on the one arithmetic fact this seam touches.

    The posting is keyed on the DESTINATION payment, because that is the row that
    carries the money afterwards and the row whose `journal_entry_id` is stamped.
    `EVENT_ACCOUNT_TRANSFER` is its own event, so a transfer and a receipt can
    never collide on one key (hard rule 6).

    Raises `PaymentRuleError` for everything a human can act on.
    """
    amount = destination_payment.amount
    if not isinstance(amount, Decimal):  # pragma: no cover - the model gives a Decimal
        raise PaymentRuleError(
            f"transfer amount {amount!r} is not a Decimal — money is NUMERIC(18,6) and never a "
            "float (CLAUDE.md rule 2).",
            br_ref="BR-PAY-002",
        )
    if applied_to_bills + credit_carried + held != amount:
        raise PaymentRuleError(
            f"the transfer moves {amount} and the destination reports {applied_to_bills} against "
            f"bills, {credit_carried} carried as credit and {held} held as a deposit "
            f"({applied_to_bills + credit_carried + held}). Every cent that leaves one account "
            "arrives on the other — on a bill, in the credit balance, or in the deposit the "
            "utility holds; an entry built from these figures would put the books out by the "
            "difference.",
            br_ref="BR-PAY-864",
        )
    # ── CS-22's TWO GUARDS, AND THEY ARE THE POINT OF THIS FUNCTION ─────────
    # A movement is EITHER a credit transfer or a deposit carry-forward. Reading
    # the verdict off the ROWS rather than off a caller's flag is deliberate: a
    # caller that passed the wrong flag would compose the wrong entry, and the
    # wrong entry here is the one that turns a customer's returnable security
    # into revenue. The rows carry the purpose the writer actually wrote.
    from apps.payments.models import PURPOSE_DEPOSIT

    carries_a_deposit = getattr(source_payment, "purpose", None) == PURPOSE_DEPOSIT
    if carries_a_deposit != (getattr(destination_payment, "purpose", None) == PURPOSE_DEPOSIT):
        raise PaymentRuleError(
            f"the source leg is purpose {getattr(source_payment, 'purpose', None)!r} and the "
            f"destination leg {getattr(destination_payment, 'purpose', None)!r}. ONE movement "
            "has ONE purpose on both legs: a deposit that arrived as a credit would be the "
            "utility's security to spend, and a credit that arrived as a deposit would be the "
            "customer's own money locked up until they move out.",
            br_ref="BR-PAY-012",
        )
    if carries_a_deposit and (applied_to_bills > ZERO or credit_carried > ZERO):
        raise PaymentRuleError(
            f"this movement carries a DEPOSIT of {amount} and reports {applied_to_bills} met "
            f"against bills and {credit_carried} carried as credit. A deposit is money the "
            "utility HOLDS and owes back (BR-PAY-012 / US-PAY-002 TC-1) — settling a bill with "
            "it would credit 1200 receivables and turn returnable customer security into "
            "revenue on a perfectly balanced entry, and the customer would be asked for a fresh "
            "deposit later. A carried deposit lands on 2300 and meets nothing.",
            br_ref="BR-PAY-012",
        )
    if held > ZERO and not carries_a_deposit:
        raise PaymentRuleError(
            f"{held} was reported as HELD on a movement whose legs are not deposit-purpose "
            "rows. Money held for a customer is a deposit, and a deposit says so on its own "
            "row; crediting 2300 from a credit transfer would build a liability the deposit "
            "register knows nothing about, which is DEF-177 in a new place.",
            br_ref="BR-PAY-012",
        )
    if source_payment.amount != -amount:
        raise PaymentRuleError(
            f"the source leg carries {source_payment.amount} and the destination leg {amount}. "
            "A transfer is ONE movement with two legs of equal size and opposite sign; two "
            "different figures are two movements and the books would carry the difference "
            "forever.",
            br_ref="BR-PAY-864",
        )

    posting = import_module(f"apps.{LEDGER_MODULE}.{POSTING_MODULE}")
    compose_key = _resolve(LEDGER_MODULE, POSTING_KEY_CALL, POSTING_MODULE)
    if compose_key is None:  # pragma: no cover - defensive
        raise PaymentRuleError(
            f"apps.{LEDGER_MODULE}.{POSTING_MODULE} publishes no {POSTING_KEY_CALL}, so this "
            "transfer cannot reach the books (CLAUDE.md rule 5).",
            br_ref="BR-LED-001",
        )
    source_dimensions = {
        "source_type": SOURCE_PAYMENT,
        "source_id": destination_payment.pk,
        "account_id": source_payment.account_id,
    }
    destination_dimensions = {
        "source_type": SOURCE_PAYMENT,
        "source_id": destination_payment.pk,
        "account_id": destination_payment.account_id,
    }
    lines = [
        # The DEBIT is what the utility stops owing on the SOURCE account, and
        # which obligation that is depends on which kind of money moved — 2300
        # for security held, 2400 for the customer's own credit. Debiting 2400
        # for a deposit would discharge a credit balance the customer never had
        # and leave the 2300 liability standing on a closed account forever.
        posting.PostingLine(
            ledger_account_id=_gl(
                GL_DEPOSIT_LIABILITY if carries_a_deposit else GL_CUSTOMER_CREDIT
            ),
            side="debit",
            amount=amount,
            **source_dimensions,
        )
    ]
    # Only legs that MOVED money get a line — `post_payment_cleared`'s own rule,
    # for its own reason: a 0.00 line is a journal line for money that did not
    # move and somebody has to explain it to whoever reads the entry.
    if applied_to_bills > ZERO:
        lines.append(
            posting.PostingLine(
                ledger_account_id=_gl(GL_ACCOUNTS_RECEIVABLE),
                side="credit",
                amount=applied_to_bills,
                **destination_dimensions,
            )
        )
    if credit_carried > ZERO:
        lines.append(
            posting.PostingLine(
                ledger_account_id=_gl(GL_CUSTOMER_CREDIT),
                side="credit",
                amount=credit_carried,
                **destination_dimensions,
            )
        )
    if held > ZERO:
        # CS-22 — the deposit ARRIVES as a deposit. Same designation, same
        # amount, the DESTINATION's dimension: the utility owes the same money
        # back to the same person and only the account it is held against moved.
        lines.append(
            posting.PostingLine(
                ledger_account_id=_gl(GL_DEPOSIT_LIABILITY),
                side="credit",
                amount=held,
                **destination_dimensions,
            )
        )
    key = compose_key(
        source_type=SOURCE_PAYMENT,
        source_id=destination_payment.pk,
        event=EVENT_ACCOUNT_TRANSFER,
    )
    request = posting.PostingRequest(
        posting_key=key,
        entry_date=entry_date,
        posted_at=posted_at,
        currency=destination_payment.currency,
        lines=tuple(lines),
        source_type=SOURCE_PAYMENT,
        source_id=destination_payment.pk,
        memo=(
            f"Transfer {source_payment.payment_no or source_payment.pk} → "
            f"{destination_payment.payment_no or destination_payment.pk}"
        ),
        audit_context={
            "source_payment_no": source_payment.payment_no,
            "destination_payment_no": destination_payment.payment_no,
            "applied_to_bills": str(applied_to_bills),
            "credit_carried": str(credit_carried),
            "deposit_held": str(held),
        },
    )
    return _write(
        posting,
        request,
        actor=actor,
        subject=(
            f"the transfer from {source_payment.payment_no or source_payment.pk} to "
            f"{destination_payment.payment_no or destination_payment.pk}"
        ),
    )


def post_partial_reversal(
    *,
    original: Any,
    reversal: Any,
    allocations_reversed: Decimal,
    credit_reversed: Decimal,
    entry_date: date,
    posted_at: datetime,
    actor: Any = None,
    clearing_account_id: Any = None,
) -> PaymentPosting:
    """CR-059 CS-33 — the books for a reversal of PART of a payment.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  ⚠ THIS COMPOSES LINES, AND `reverse_payment_entry` DELIBERATELY     ║
    ║  DOES NOT. THE REASON IS WRITTEN OUT HERE BECAUSE IT LOOKS LIKE A    ║
    ║  RULE BEING BROKEN AND IS NOT.                                       ║
    ╚══════════════════════════════════════════════════════════════════════╝
    `reverse_payment_entry` above hands the ledger the ORIGINAL entry and lets
    `posting.reverse_entry` copy it with the sides swapped — *"same GLs, sides
    swapped"*, US-LED-003 §5's signed words — and its docstring says a
    compensating entry composed here *"would have to re-derive the original's
    legs from figures this module still holds"*. That reasoning is right and it
    is why a FULL reversal still goes through the mirror, untouched.

    **A PARTIAL REVERSAL CANNOT USE THE MIRROR, AND NOT FOR CONVENIENCE:**

      * `reverse_entry` reverses the WHOLE entry. A 100.00 reversal of a 292.87
        payment would take all 292.87 out of the books while 192.87 of the money
        is still in the utility's hands.
      * the ledger's own `uq_journal_entries_reversal` **refuses a SECOND mirror
        of one entry** — which is a guarantee worth having, and which makes two
        partial reversals of one payment structurally unmirrorable.

    **AND THE OBJECTION THE MIRROR'S DOCSTRING RAISES DOES NOT APPLY HERE.** It
    warns against RE-DERIVING the original's legs. These legs are not re-derived
    from anything: `allocations_reversed` is the Σ of the negative allocation
    rows THIS reversal just wrote, and `credit_reversed` is what is left of the
    reversed amount after them. They are facts about rows that exist, handed in
    by the one writer that made them, and this function refuses the request if
    they do not foot to the reversing row (below).

    **REPORTED, NOT ASSUMED SETTLED:** whether `apps.ledger.posting` should grow
    a partial-reversal primitive of its own is a question for the ledger lane,
    and it is in this lane's decision-log row and its report. Composing here is
    the only lawful expression available today; it is not a claim that it is the
    permanent home.

    THE LEGS — the receipt's own, inverted, for the part that came back:

        DR  1200 accounts receivable      100.00   the bills that re-opened
        DR  2400 customer credit           57.13   credit taken back, if any
        CR  1010 undeposited funds        157.13   or the tender's clearing acct

    The credit leg may drive `2400` into DEBIT for this customer, and nothing
    floors it — PO 2026-08-11, `OQ-132`, *"Yes, it's a real debt"*.

    Raises `PaymentRuleError` for everything a human can act on.
    """
    reversed_total = -reversal.amount
    if not isinstance(reversed_total, Decimal):  # pragma: no cover - the model gives a Decimal
        raise PaymentRuleError(
            f"reversal amount {reversal.amount!r} is not a Decimal — money is NUMERIC(18,6) "
            "and never a float (CLAUDE.md rule 2).",
            br_ref="BR-PAY-002",
        )
    if allocations_reversed + credit_reversed != reversed_total:
        raise PaymentRuleError(
            f"this partial reversal takes back {reversed_total} and reports "
            f"{allocations_reversed} off bills and {credit_reversed} off credit "
            f"({allocations_reversed + credit_reversed}). Every cent that comes back leaves "
            "a bill or the customer's credit balance; an entry built from these figures would "
            "put the books out against the bank by the difference.",
            br_ref="BR-PAY-884",
        )

    posting = import_module(f"apps.{LEDGER_MODULE}.{POSTING_MODULE}")
    compose_key = _resolve(LEDGER_MODULE, POSTING_KEY_CALL, POSTING_MODULE)
    if compose_key is None:  # pragma: no cover - defensive
        raise PaymentRuleError(
            f"apps.{LEDGER_MODULE}.{POSTING_MODULE} publishes no {POSTING_KEY_CALL}, so this "
            "partial reversal cannot reach the books (CLAUDE.md rule 5).",
            br_ref="BR-LED-001",
        )
    dimensions = {
        "source_type": SOURCE_PAYMENT,
        "source_id": reversal.pk,
        "account_id": original.account_id,
    }
    lines = []
    if allocations_reversed > ZERO:
        lines.append(
            posting.PostingLine(
                ledger_account_id=_gl(GL_ACCOUNTS_RECEIVABLE),
                side="debit",
                amount=allocations_reversed,
                **dimensions,
            )
        )
    if credit_reversed > ZERO:
        lines.append(
            posting.PostingLine(
                ledger_account_id=_gl(GL_CUSTOMER_CREDIT),
                side="debit",
                amount=credit_reversed,
                **dimensions,
            )
        )
    # The holding account the receipt DEBITED. Credited back here, so a partial
    # bounce never touches bank cash the utility still holds — OQ-143's law,
    # applied to a part of a payment exactly as the mirror applies it to all.
    lines.append(
        posting.PostingLine(
            ledger_account_id=(
                clearing_account_id if clearing_account_id is not None else _gl(GL_UNDEPOSITED)
            ),
            side="credit",
            amount=reversed_total,
            **dimensions,
        )
    )
    key = compose_key(
        source_type=SOURCE_PAYMENT, source_id=reversal.pk, event=EVENT_PARTIAL_REVERSAL
    )
    request = posting.PostingRequest(
        posting_key=key,
        entry_date=entry_date,
        posted_at=posted_at,
        currency=original.currency,
        lines=tuple(lines),
        source_type=SOURCE_PAYMENT,
        source_id=reversal.pk,
        memo=(
            f"Partial reversal {reversal.payment_no or reversal.pk} of "
            f"{original.payment_no or original.pk}"
        ),
        audit_context={
            "original_payment_no": original.payment_no,
            "reversal_no": reversal.payment_no,
            "allocations_reversed": str(allocations_reversed),
            "credit_reversed": str(credit_reversed),
        },
    )
    return _write(
        posting,
        request,
        actor=actor,
        subject=(
            f"the partial reversal of {original.payment_no or original.pk} " f"({reversed_total})"
        ),
    )


def reverse_payment_entry(
    *,
    payment: Any,
    entry_date: date,
    posted_at: datetime,
    event: str = EVENT_NSF_REVERSED,
    memo: str | None = None,
    actor: Any = None,
) -> PaymentPosting:
    """Unwind a payment's entry with the LEDGER'S OWN MIRROR (BR-PAY-013).

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  THIS FUNCTION COMPOSES NO LINES. THAT IS THE WHOLE POINT.           ║
    ╚══════════════════════════════════════════════════════════════════════╝
    `apps.ledger.posting.reverse_entry` reads the original entry and copies it
    with the sides swapped — *"same GLs, sides swapped"*, US-LED-003 §5's own
    signed words. A compensating entry composed HERE would have to re-derive the
    original's legs from figures this module still holds, and the one thing a
    reversal may never do is disagree with the entry it claims to reverse.

    Three consequences follow for free, and each is asserted rather than assumed
    (tests/test_us_pay_009_nsf.py):

      * **The right STEP is unwound.** After the PO's OQ-143 ruling the receipt
        leg is `undeposited_funds`; the mirror credits whatever was debited, so
        a bounce never touches bank cash the utility still holds.
      * **THE ACCOUNT CREDIT GOES NEGATIVE, AND NOTHING FLOORS IT.** PO ruling
        2026-08-11, verbatim: *"Yes, it's a real debt"*. Worked, on J15's own
        chain: a **$350.00** cheque clears (CR AR 292.87 + CR customer-credit
        57.13), the **$57.13** change is refunded (DR customer-credit 57.13),
        and then the cheque bounces. The mirror DEBITS customer-credit 57.13
        again, leaving that account **57.13 in debit for this customer — a
        credit balance of −57.13**, which is a genuine receivable the utility
        pursues. A seam that "protected" the customer by dropping that leg
        would balance by losing 57.13 of the utility's money.
      * **The reversal is linked, not netted.** `reverse_entry` sets
        `reversal_of` on the mirror, so S56 renders both halves forever.

    `event` is the third part of the replay key, so the mirror of a bounce
    (`payment|<uuid>|nsf_reversed`) is a different string from the receipt
    (`payment|<uuid>|cleared`) and both lawfully exist. A replay writes nothing
    and returns the FIRST mirror with `created=False`; the ledger's own
    `uq_journal_entries_reversal` refuses a SECOND mirror of the same entry even
    under a fresh key, which is this flow's third idempotency guard.

    Raises `PaymentRuleError` when the payment never reached the books — a
    payment with no `journal_entry_id` has nothing to unwind, and reversing
    "nothing" silently is how a bounce comes to leave the books unchanged.
    """
    entry_id = getattr(payment, "journal_entry_id", None)
    if entry_id is None:
        raise PaymentRuleError(
            f"payment {payment.payment_no or payment.pk} names no journal entry, so there is "
            "nothing in the books to unwind. A cleared payment is stamped with its entry id in "
            "the same transaction that posts it (US-PAY-009); a row without one either never "
            "cleared or predates that stamp, and reversing it would leave the money in the "
            "trial balance while the customer's bills re-opened.",
            br_ref="BR-PAY-013",
        )
    posting = import_module(f"apps.{LEDGER_MODULE}.{POSTING_MODULE}")
    compose_key = _resolve(LEDGER_MODULE, POSTING_KEY_CALL, POSTING_MODULE)
    mirror = _resolve(LEDGER_MODULE, "reverse_entry", POSTING_MODULE)
    if compose_key is None or mirror is None:  # pragma: no cover - defensive
        raise PaymentRuleError(
            f"apps.{LEDGER_MODULE}.{POSTING_MODULE} publishes no reverse_entry, so this "
            "payment cannot be unwound. Payments may not write journal lines itself "
            "(CLAUDE.md rule 5), and it may not hand-compose a compensating entry either.",
            br_ref="BR-LED-003",
        )
    key = compose_key(source_type=SOURCE_PAYMENT, source_id=payment.pk, event=event)
    try:
        result = mirror(
            entry_id,
            posting_key=key,
            entry_date=entry_date,
            posted_at=posted_at,
            memo=memo or f"Reversal of payment {payment.payment_no or payment.pk}",
            actor=actor,
        )
    except posting.PostingError as refusal:
        raise PaymentRuleError(
            f"payment {payment.payment_no or payment.pk} could not be unwound in the books: "
            f"{refusal}",
            br_ref="BR-LED-003",
        ) from refusal
    return PaymentPosting(
        entry_id=result.entry_id,
        posting_key=result.posting_key,
        created=result.created,
        debits=result.debits,
        credits=result.credits,
        line_count=result.line_count,
    )


def post_bank_fee(
    *,
    payment: Any,
    amount: Decimal,
    entry_date: date,
    posted_at: datetime,
    actor: Any = None,
) -> PaymentPosting:
    """The BANK's own charge for handling the return — DR 6800 / CR cash.

    Already-decided and transcribed, never chosen here
    (12-governance/12-payments-decision-batch.md, "Who pays the bank's own
    charge"): **"You do."** It is the utility's expense, it lands in the signed
    **bank-fees** designation (6800), and *"This is not the customer's NSF fee —
    they are two different amounts"*.

    **The contra leg is CASH (1000), not undeposited funds, and the distinction
    is the OQ-143 ruling working correctly rather than an exception to it.** The
    PO's rule is about money coming IN — it is not realised until the bank
    confirms it. A bank fee is money the bank has ALREADY taken out of the
    utility's real account; it appears on the statement as a debit that has
    happened. Booking it against undeposited funds would say the bank charged a
    drawer of uncounted cheques.

    Recorded as a judgment call in 12-governance/02-decision-log.md, because the
    signed material names the EXPENSE account and does not spell the contra.
    """
    if not isinstance(amount, Decimal):
        raise PaymentRuleError(
            f"bank fee {amount!r} is not a Decimal — money is NUMERIC(18,6) and never a float "
            "(CLAUDE.md rule 2). Refused rather than converted.",
            br_ref="BR-PAY-002",
        )
    if amount <= ZERO:
        raise PaymentRuleError(
            f"bank fee {amount} must be greater than zero. A returned-item charge of nothing is "
            "not a charge, and a NEGATIVE one is a refund from the bank — which is its own "
            "event with its own reason, not this one wearing a minus sign.",
            br_ref="BR-PAY-019",
        )
    posting = import_module(f"apps.{LEDGER_MODULE}.{POSTING_MODULE}")
    compose_key = _resolve(LEDGER_MODULE, POSTING_KEY_CALL, POSTING_MODULE)
    if compose_key is None:  # pragma: no cover - defensive
        raise PaymentRuleError(
            f"apps.{LEDGER_MODULE}.{POSTING_MODULE} publishes no {POSTING_KEY_CALL}.",
            br_ref="BR-LED-001",
        )
    # NO `account_id` dimension. BR-LED-001's dimensions describe WHOSE money a
    # line is, and this expense is the utility's own — stamping the customer's
    # account on it would make the bank's charge show up in that customer's
    # ledger view as something they owe.
    dimensions = {"source_type": SOURCE_PAYMENT, "source_id": payment.pk}
    request = posting.PostingRequest(
        posting_key=compose_key(
            source_type=SOURCE_PAYMENT, source_id=payment.pk, event=EVENT_BANK_FEE
        ),
        entry_date=entry_date,
        posted_at=posted_at,
        currency=payment.currency,
        lines=(
            posting.PostingLine(
                ledger_account_id=_gl(GL_BANK_FEES), side="debit", amount=amount, **dimensions
            ),
            posting.PostingLine(
                ledger_account_id=_gl(GL_CASH), side="credit", amount=amount, **dimensions
            ),
        ),
        source_type=SOURCE_PAYMENT,
        source_id=payment.pk,
        memo=f"Bank fee on returned payment {payment.payment_no or payment.pk}",
        audit_context={"payment_no": payment.payment_no, "bank_fee": str(amount)},
    )
    return _write(
        posting,
        request,
        actor=actor,
        subject=f"the bank fee on payment {payment.payment_no or payment.pk}",
    )


# ════════════════════════════════════════════════════════════════════════════
# LBX-05 · A STATEMENT LINE THAT IS NOT A DEPOSIT POSTS (G3 RULED 2026-10-30)
# ════════════════════════════════════════════════════════════════════════════
#: HUMAN-REVIEW-PENDING (🔒 ledger posting) — row in
#: 12-governance/09-human-review-ledger.md, "LBX-05".
SOURCE_BANK_LINE = "bank_line"
EVENT_RETURNED_ITEM = "returned_item"
EVENT_LINE_BANK_FEE = "bank_fee"


def post_bank_line_settlement(
    *,
    bank_line: Any,
    counter_account_id: Any,
    event: str,
    entry_date: date,
    posted_at: datetime,
    currency: str,
    memo: str,
    actor: Any = None,
    audit_context: dict[str, Any] | None = None,
) -> PaymentPosting:
    """ONE balanced pair for one bank line that LEFT the bank: DR counter / CR cash.

    PO 2026-10-30, verbatim: *"Q1. May a bank-statement line that isn't a
    deposit post to the books?-A"* — batch decision G3, RULED. Two callers, one
    shape, both worked on the tester's statement (decision log *"Lockbox audit:
    what is fixed, what is not, and three answers"*):

      * a RETURNED cheque matched to its reversal — the counter account is the
        HOLDING account the receipt debited (the reversal's mirror credited it
        back, and reconciling the batch credited it again): RET1029-01
        **−76.40** → DR holding 76.40 / CR cash 76.40;
      * the bank's own FEE — the counter account is `bank_fees` (6800, by
        DESIGNATION): FEE1031 **−24.00** → DR 6800 24.00 / CR cash 24.00.

    After both on the tester's day: books cash = bank **616.10**, holding
    **0.00**. Cash is the `cash` designation, never a number.

    The line's amount is NEGATIVE (money out); the posting carries its absolute
    value because `journal_lines` holds no sign (B2's `CHECK (amount >= 0)`).
    Keyed `bank_line|<id>|<event>` (hard rule 6): a replay writes nothing.
    """
    amount = getattr(bank_line, "amount", None)
    if not isinstance(amount, Decimal):
        raise PaymentRuleError(
            f"bank line amount {amount!r} is not a Decimal (CLAUDE.md rule 2).",
            br_ref="BR-PAY-019",
        )
    if amount >= ZERO:
        raise PaymentRuleError(
            f"bank line {bank_line.reference or bank_line.pk} is {amount}: money came IN. A "
            "returned item and a bank fee are money the bank took OUT, so this line is neither.",
            br_ref="BR-PAY-019",
        )
    if counter_account_id is None:
        raise PaymentRuleError(
            "no account to post the bank line against — refused rather than guessed.",
            br_ref="BR-PAY-019",
        )
    value = -amount
    posting = import_module(f"apps.{LEDGER_MODULE}.{POSTING_MODULE}")
    compose_key = _resolve(LEDGER_MODULE, POSTING_KEY_CALL, POSTING_MODULE)
    if compose_key is None:  # pragma: no cover - defensive
        raise PaymentRuleError(
            f"apps.{LEDGER_MODULE}.{POSTING_MODULE} publishes no {POSTING_KEY_CALL}.",
            br_ref="BR-LED-001",
        )
    dimensions = {"source_type": SOURCE_BANK_LINE, "source_id": bank_line.pk}
    request = posting.PostingRequest(
        posting_key=compose_key(source_type=SOURCE_BANK_LINE, source_id=bank_line.pk, event=event),
        entry_date=entry_date,
        posted_at=posted_at,
        currency=currency,
        lines=(
            posting.PostingLine(
                ledger_account_id=counter_account_id, side="debit", amount=value, **dimensions
            ),
            posting.PostingLine(
                ledger_account_id=_gl(GL_CASH), side="credit", amount=value, **dimensions
            ),
        ),
        source_type=SOURCE_BANK_LINE,
        source_id=bank_line.pk,
        memo=memo,
        audit_context={
            "bank_line_reference": bank_line.reference,
            "amount": str(value),
            **(audit_context or {}),
        },
    )
    return _write(
        posting,
        request,
        actor=actor,
        subject=f"bank line {bank_line.reference or bank_line.pk}",
    )


def bank_fee_posting_key(payment_id: Any) -> str | None:
    """The replay key `post_bank_fee` used for a payment's Reverse-time bank fee."""
    compose_key = _resolve(LEDGER_MODULE, POSTING_KEY_CALL, POSTING_MODULE)
    if compose_key is None:  # pragma: no cover - defensive
        return None
    return compose_key(source_type=SOURCE_PAYMENT, source_id=payment_id, event=EVENT_BANK_FEE)


#: CR-197-BRC10 · BR-LED-803 — the refund's own account role. Optional.
GL_REFUNDS_PAYABLE = "refunds_payable"


def _refund_credit_account() -> Any:
    """Where a refund's CREDIT lands: the `refunds_payable` account when the
    tenant has given one that role, else `cash` exactly as before.

    PO 2026-10-29, *"Refunds: A — their own row (refund account)"*. Worked:
    refund $57.13 — with no role set, DR 2400 / CR 1000 (unchanged); with 2450
    designated, DR 2400 / CR 2450. A void (`reverse_refund_entry`) mirrors the
    entry it was given, so it follows whichever account the refund posted to.

    ⚠ **ONLY THE OPTIONAL READ IS NEW.** Cash is still resolved through `_gl`,
    which refuses by name when nothing carries it — a refund with no cash
    account must not fall back to anything either.
    """
    read = _resolve(LEDGER_MODULE, GL_DESIGNATION_READ, "selectors")
    own = read(GL_REFUNDS_PAYABLE) if read is not None else None
    return own if own is not None else _gl(GL_CASH)


def post_refund_executed(
    *,
    refund: Any,
    account_id: Any,
    entry_date: date,
    posted_at: datetime,
    actor: Any = None,
) -> PaymentPosting:
    """US-LED-001's *"Refund executed"* — DR customer credit / CR cash.

    BR-PAY-014, CONFIRMED and quoted: *"DR customer-credit / CR cash"*. PE-9
    works it: refund **57.13** by cheque #10241 draws ACC-1042's credit to 0.00.

    ⚠ **AMENDED 2026-10-29 (`CR-197-BRC10`, BR-LED-803):** the credit is
    `refunds_payable` when the tenant has given an account that role, and cash
    otherwise — see `_refund_credit_account`. Everything below about cash is
    still exactly the behaviour of a tenant who has not.

    **CR CASH, not undeposited funds — and OQ-143 does not touch this row.** The
    PO's ruling is about money arriving: it is not realised until the bank
    confirms it. A refund cheque is money LEAVING the utility's real bank
    account. There is no such thing as an "undeposited payment out"; the
    contract table says cash and it stays cash.

    The DEBIT is the account-level credit position being drawn down, which is
    the same `customer_credit_balance` (2400) the overpayment credited when it
    arose — that symmetry is why the third leg of `post_payment_cleared` had to
    exist at all.
    """
    amount = refund.amount
    if not isinstance(amount, Decimal):  # pragma: no cover - the model gives a Decimal
        raise PaymentRuleError(
            f"refund amount {amount!r} is not a Decimal (CLAUDE.md rule 2).", br_ref="BR-PAY-002"
        )
    posting = import_module(f"apps.{LEDGER_MODULE}.{POSTING_MODULE}")
    compose_key = _resolve(LEDGER_MODULE, POSTING_KEY_CALL, POSTING_MODULE)
    if compose_key is None:  # pragma: no cover - defensive
        raise PaymentRuleError(
            f"apps.{LEDGER_MODULE}.{POSTING_MODULE} publishes no {POSTING_KEY_CALL}.",
            br_ref="BR-LED-001",
        )
    dimensions = {
        "source_type": SOURCE_REFUND,
        "source_id": refund.pk,
        "account_id": account_id,
    }
    request = posting.PostingRequest(
        posting_key=compose_key(
            source_type=SOURCE_REFUND, source_id=refund.pk, event=EVENT_REFUND_ISSUED
        ),
        entry_date=entry_date,
        posted_at=posted_at,
        currency=refund.currency,
        lines=(
            posting.PostingLine(
                ledger_account_id=_gl(GL_CUSTOMER_CREDIT),
                side="debit",
                amount=amount,
                **dimensions,
            ),
            posting.PostingLine(
                ledger_account_id=_refund_credit_account(), side="credit", amount=amount, **dimensions
            ),
        ),
        source_type=SOURCE_REFUND,
        source_id=refund.pk,
        memo=f"Refund {refund.reference or refund.pk}",
        audit_context={"refund_id": str(refund.pk), "amount": str(amount)},
    )
    return _write(posting, request, actor=actor, subject=f"refund {refund.reference or refund.pk}")


def reverse_refund_entry(
    *,
    refund: Any,
    entry_date: date,
    posted_at: datetime,
    actor: Any = None,
) -> PaymentPosting:
    """Void a refund by MIRRORING its entry (US-PAY-011 TC-4, hard rule 4).

    *"Void an issued-but-lost check → Status → Void with reversing posting
    (credit restored 57.13); new refund issuable; no row deleted."*

    Same discipline as `reverse_payment_entry`: the ledger reads its own entry
    and swaps the sides. Nothing here recomputes 57.13, so a voided refund
    restores exactly what it drew down even if this module's arithmetic changed
    in between.
    """
    entry_id = getattr(refund, "journal_entry_id", None)
    if entry_id is None:
        raise PaymentRuleError(
            f"refund {refund.reference or refund.pk} names no journal entry, so there is "
            "nothing to unwind. Only an ISSUED refund has posted, and only an issued refund "
            "can be voided (BR-PAY-014).",
            br_ref="BR-PAY-014",
        )
    posting = import_module(f"apps.{LEDGER_MODULE}.{POSTING_MODULE}")
    compose_key = _resolve(LEDGER_MODULE, POSTING_KEY_CALL, POSTING_MODULE)
    mirror = _resolve(LEDGER_MODULE, "reverse_entry", POSTING_MODULE)
    if compose_key is None or mirror is None:  # pragma: no cover - defensive
        raise PaymentRuleError(
            f"apps.{LEDGER_MODULE}.{POSTING_MODULE} publishes no reverse_entry.",
            br_ref="BR-LED-003",
        )
    key = compose_key(source_type=SOURCE_REFUND, source_id=refund.pk, event=EVENT_REFUND_VOIDED)
    try:
        result = mirror(
            entry_id,
            posting_key=key,
            entry_date=entry_date,
            posted_at=posted_at,
            memo=f"Void of refund {refund.reference or refund.pk}",
            actor=actor,
        )
    except posting.PostingError as refusal:
        raise PaymentRuleError(
            f"refund {refund.reference or refund.pk} could not be voided in the books: "
            f"{refusal}",
            br_ref="BR-LED-003",
        ) from refusal
    return PaymentPosting(
        entry_id=result.entry_id,
        posting_key=result.posting_key,
        created=result.created,
        debits=result.debits,
        credits=result.credits,
        line_count=result.line_count,
    )


# ── the bank-rec pair: step 2 of the OQ-143 ruling ──────────────────────────
def post_batch_reconciled(
    *,
    batch: Any,
    bank_total: Decimal,
    recorded_total: Decimal,
    resolutions: tuple[tuple[str, Any, Decimal], ...],
    entry_date: date,
    posted_at: datetime,
    attempt: int = 0,
    actor: Any = None,
    undeposited_credits: tuple[tuple[Any, Decimal], ...] | None = None,
) -> PaymentPosting:
    """**Reconciliation realises the cash** — DR cash + each fee line / CR what
    the receipts DEBITED.

    ⚠ **AMENDED 2026-08-18 (CR-008 B-10), the other half of the one change.**
    `undeposited_credits` is `((holding_account_id, amount), …)` — the batch's
    recorded total split across the accounts its member receipts actually
    debited, which the CALLER derives from the entries themselves
    (`reconciliation._member_credit_split`, over the ledger's published
    `entry_debit_totals`). `None` keeps the pre-B-10 single credit to 1010
    Undeposited funds — the correct shape for every batch whose members all
    debited it, and the compatibility shape for any caller not yet passing a
    split. **Σ of the split must foot to `recorded_total`** or the request is
    refused BY NAME before it reaches the posting service: this is the second
    independent check on the one arithmetic fact this seam owns (the ledger's
    debits-equals-credits refusal is the other).

    The second step of the PO's ruling of 2026-08-11 (OQ-143), verbatim: *"until
    bank record and reconcilaition confirm it it is not realised"*. Every payment
    in this batch debited **1010 Undeposited funds** on receipt; the bank has now
    confirmed the money, so it moves to **1000 Cash**.

    And the PO's other ruling of the same day (OQ-144), verbatim: *"Match net
    with a fee line"*. Worked, on the prototype's card day:

        DR 1000 Cash               4,972.90   ← what the bank actually credited
        DR 6800 Bank fees            147.50   ← the processor's fee, ITS OWN LINE
        CR 1010 Undeposited funds  5,120.40   ← what the customers handed over

    **Nothing here computes a money figure.** `bank_total` is what the statement
    said, `recorded_total` is Σ the batch's members, and every resolution is a
    `(reason, GL account, signed amount)` a HUMAN stated — the caller has already
    refused the batch unless Σ resolutions = bank − recorded (BR-PAY-019). This
    function turns the sign into a SIDE (`journal_lines` cannot carry a negative
    amount, B2 §2 `CHECK (amount >= 0)`) and hands the request over.

    A **negative** resolution is money we did not receive — the processor's fee,
    a cash shortage — so it DEBITS its account: an expense, or whatever bucket
    the tenant named. A **positive** one is money the bank gave us beyond the
    batch (interest) and CREDITS it. Both directions are BR-PAY-019's *"every
    difference carries a reason and an account"*; neither is netted into cash.

    `entry_date` is the caller's (the bank's posting date by default — the day
    the bank confirmed it). `attempt` distinguishes a re-reconcile after an
    Unreconcile, so corrected figures post rather than replaying the first key.
    """
    for name, value in (("bank_total", bank_total), ("recorded_total", recorded_total)):
        if not isinstance(value, Decimal):
            raise PaymentRuleError(
                f"{name} {value!r} is not a Decimal — money is NUMERIC(18,6) and never a float "
                "(CLAUDE.md rule 2). Refused rather than converted.",
                br_ref="BR-PAY-019",
            )
    explained = sum((amount for _reason, _account, amount in resolutions), ZERO)
    if bank_total - recorded_total != explained:
        raise PaymentRuleError(
            f"deposit batch {getattr(batch, 'code', batch)} does not tie: bank {bank_total} − "
            f"recorded {recorded_total} = {bank_total - recorded_total}, and the explanations sum "
            f"to {explained}. The entry is refused rather than plugged — a balancing line would "
            "make the books balance and be wrong (BR-PAY-019, and BR-PAY-035 keeps 'Force match "
            "anyway' permanently superseded).",
            br_ref="BR-PAY-019",
        )

    posting = import_module(f"apps.{LEDGER_MODULE}.{POSTING_MODULE}")
    compose_key = _resolve(LEDGER_MODULE, POSTING_KEY_CALL, POSTING_MODULE)
    if compose_key is None:  # pragma: no cover - defensive
        raise PaymentRuleError(
            f"apps.{LEDGER_MODULE}.{POSTING_MODULE} publishes no {POSTING_KEY_CALL}.",
            br_ref="BR-LED-001",
        )
    # BR-LED-001's two mandatory dimensions. NO `account_id`: a deposit batch is
    # many customers' money in one bag, so stamping one account on these lines
    # would put the whole day's cash in one customer's ledger view.
    dimensions = {"source_type": SOURCE_DEPOSIT_BATCH, "source_id": batch.pk}
    lines = []
    if bank_total > ZERO:
        lines.append(
            posting.PostingLine(
                ledger_account_id=_gl(GL_CASH), side="debit", amount=bank_total, **dimensions
            )
        )
    for reason, account_id, amount in resolutions:
        if not isinstance(amount, Decimal):
            raise PaymentRuleError(
                f"the {reason!r} explanation is {amount!r}, not a Decimal (rule 2).",
                br_ref="BR-PAY-019",
            )
        lines.append(
            posting.PostingLine(
                ledger_account_id=account_id,
                # A shortfall (negative) is money that did not arrive: DEBIT the
                # account the tenant named. A surplus CREDITS it.
                side="debit" if amount < ZERO else "credit",
                amount=abs(amount),
                **dimensions,
            )
        )
    if undeposited_credits is None:
        # Pre-B-10 shape: every member receipt debited undeposited funds, so
        # one credit line returns the lot.
        lines.append(
            posting.PostingLine(
                ledger_account_id=_gl(GL_UNDEPOSITED),
                side="credit",
                amount=recorded_total,
                **dimensions,
            )
        )
    else:
        split_total = ZERO
        for account_id, share in undeposited_credits:
            if not isinstance(share, Decimal):
                raise PaymentRuleError(
                    f"the credit split's share for account {account_id} is {share!r}, not a "
                    "Decimal — money is NUMERIC(18,6) and never a float (CLAUDE.md rule 2).",
                    br_ref="BR-PAY-019",
                )
            split_total += share
        if split_total != recorded_total:
            raise PaymentRuleError(
                f"deposit batch {getattr(batch, 'code', batch)}'s credit split does not foot: "
                f"the member receipts' debits sum to {split_total} and the batch recorded "
                f"{recorded_total}. Crediting either figure over the other would leave the "
                "difference stranded in a holding account forever, so nothing is posted — the "
                "batch's membership or its members' entries need a human's eyes (CR-008 B-10, "
                "the balanced-pair tie-out at the seam).",
                br_ref="BR-PAY-019",
            )
        for account_id, share in undeposited_credits:
            if share <= ZERO:
                continue  # only legs that moved money get a line
            lines.append(
                posting.PostingLine(
                    ledger_account_id=account_id, side="credit", amount=share, **dimensions
                )
            )
    event = EVENT_RECONCILED if not attempt else f"{EVENT_RECONCILED}:{attempt}"
    request = posting.PostingRequest(
        posting_key=compose_key(source_type=SOURCE_DEPOSIT_BATCH, source_id=batch.pk, event=event),
        entry_date=entry_date,
        posted_at=posted_at,
        # The batch has no currency column (B2 §2); its members do, and they are
        # one tenant's own money. `tenant_settings.currency` is locked once a
        # financial record exists (BR-TEN-042), so a batch cannot mix two.
        currency=_batch_currency(batch),
        lines=tuple(lines),
        source_type=SOURCE_DEPOSIT_BATCH,
        source_id=batch.pk,
        memo=f"Deposit batch {getattr(batch, 'code', batch)} reconciled",
        audit_context={
            "batch_code": getattr(batch, "code", None),
            "bank_total": str(bank_total),
            "recorded_total": str(recorded_total),
            "explanations": len(resolutions),
        },
    )
    return _write(
        posting,
        request,
        actor=actor,
        subject=f"deposit batch {getattr(batch, 'code', batch)}",
    )


def reverse_batch_reconciliation(
    *,
    batch: Any,
    entry_id: Any,
    posted_at: datetime,
    attempt: int,
    entry_date: date | None = None,
    actor: Any = None,
) -> PaymentPosting | None:
    """Unreconcile: take the cash back out, with the LEDGER'S OWN MIRROR (OQ-163).

    Composes no lines, for the reason `reverse_payment_entry` gives at length:
    `posting.reverse_entry` copies the original with the sides swapped, so the
    cash, the fee line and the undeposited credit all unwind exactly as they
    were posted — including a fee this module could no longer recompute.

    **Why it happens at all is a lane reading, raised as OQ-163.** BR-PAY-004
    ratifies Unreconcile as the only way back and says nothing about the books;
    but the PO's OQ-143 ruling says money is not cash until the bank confirms it,
    and unreconciling is the statement that the confirmation did not hold.
    Leaving the entry would show CASH for a batch the product itself calls
    unreconciled, and the next reconcile would realise the same money twice.

    `entry_id` is the entry the reconcile posted, and the CALLER supplies it —
    read off its own trail (`deposit_batch_events`, the `reconciled` event's
    detail), not looked up here. The ledger publishes no
    `entry_id_for_posting_key` read, and inventing one on this side of the
    boundary would mean payments querying the journal (B1: cross-module reads go
    through the owner's published callables, never its ORM).

    Returns None when the batch has no reconciliation entry to mirror — a batch
    reconciled before this posting existed, or one whose entry was never written.
    Silence there is better than a refusal: BR-PAY-004's Unreconcile is CONFIRMED
    and must not be blocked by a posting that is not there to unwind.
    """
    if entry_id is None:
        return None
    posting = import_module(f"apps.{LEDGER_MODULE}.{POSTING_MODULE}")
    compose_key = _resolve(LEDGER_MODULE, POSTING_KEY_CALL, POSTING_MODULE)
    mirror = _resolve(LEDGER_MODULE, "reverse_entry", POSTING_MODULE)
    if compose_key is None or mirror is None:  # pragma: no cover - defensive
        raise PaymentRuleError(
            f"apps.{LEDGER_MODULE}.{POSTING_MODULE} publishes no reverse_entry, so this batch "
            "cannot be unwound. Payments may not hand-compose a compensating entry "
            "(CLAUDE.md rule 5).",
            br_ref="BR-LED-003",
        )
    key = compose_key(
        source_type=SOURCE_DEPOSIT_BATCH,
        source_id=batch.pk,
        event=f"{EVENT_UNRECONCILED}:{attempt}",
    )
    try:
        result = mirror(
            entry_id,
            posting_key=key,
            entry_date=entry_date or posted_at.date(),
            posted_at=posted_at,
            memo=f"Unreconcile of deposit batch {getattr(batch, 'code', batch)}",
            actor=actor,
        )
    except posting.PostingError as refusal:
        raise PaymentRuleError(
            f"deposit batch {getattr(batch, 'code', batch)} could not be unwound in the books: "
            f"{refusal}",
            br_ref="BR-LED-003",
        ) from refusal
    return PaymentPosting(
        entry_id=result.entry_id,
        posting_key=result.posting_key,
        created=result.created,
        debits=result.debits,
        credits=result.credits,
        line_count=result.line_count,
    )


def _batch_currency(batch: Any) -> str:
    """The currency of the money in a batch — read off its members, never guessed.

    `deposit_batches` carries no currency column (B2 §2) and `PostingRequest`
    requires one with no default, deliberately: *"a defaulted currency is how a
    CAD tenant's books quietly become USD"*. So it is read from the batch's own
    payments, which all carry one (B2 §2 `payments.currency`), and a batch with
    no members has nothing to post anyway.
    """
    from apps.payments import models as payment_models

    currency = (
        payment_models.Payment.objects.filter(tenant_id=batch.tenant_id, deposit_batch_id=batch.pk)
        .values_list("currency", flat=True)
        .first()
    )
    if not currency:
        raise PaymentRuleError(
            f"deposit batch {getattr(batch, 'code', batch)} has no member payments, so the "
            "currency of its money cannot be read and nothing can be posted. A batch is Σ its "
            "members (BR-PAY-025); an empty one is not a deposit.",
            br_ref="BR-PAY-025",
        )
    return currency


# ═══════════════════════════════════════════════════════════════════════════
# THE COUNTER RECEIPT — CR-094-BRC01 lane H, PO ruling 2026-09-15
# ═══════════════════════════════════════════════════════════════════════════
# *"payemnt should show in payments, in ledge and in fiannce books"*. Until this
# lane the capture wizard's step 5 took cash and posted NOTHING — the blueprint
# said so in red on p079 and the PO has reversed it. These two functions are the
# whole of the ledger half.
#
# ⚠ **THE DEBIT IS NOT `1000 Cash`.** The ruling row of 2026-09-15 names 1000
# and is AMENDED on that one account by the decision-log row of the same day.
# The PO named no account; 1000 was our rendering of them, and it collides with
# their own OQ-143 ruling of 2026-08-11 — *"Cash is received but undeposted in
# such case payment will say csah but ledger will say undeposited"*. A counter
# is the paradigm case of received-and-not-banked, so the collection resolves
# its debit through `tender_clearing_account_id` exactly as every other receipt
# in this product does, and lands in `1010 Undeposited funds` when a tender is
# unmapped. The reconciliation leg that turns it into cash is the bank-rec
# lane's and is unchanged.

#: The counter receipt as a source document. A THIRD source_type rather than
#: `payment`, because the row is not a payment: it is money handed over by
#: somebody who has no account yet, and an auditor asking *"what is the 25.00?"*
#: must land on the slip the clerk wrote and not on a payment that did not exist
#: for another three weeks (LE-5's question, BR-LED-001's answer).
SOURCE_COUNTER_RECEIPT = "counter_receipt"

#: The two events. A document is not the unit of identity — a document plus the
#: event that happened to it is — so one receipt lawfully carries both
#: `counter_receipt|<id>|collected` and `counter_receipt|<id>|released`, and a
#: replay of either returns the FIRST entry and writes nothing (hard rule 6).
EVENT_COUNTER_COLLECTED = "collected"
EVENT_COUNTER_RELEASED = "released"


def post_counter_receipt_collected(
    *,
    receipt: Any,
    clearing_account_id: Any,
    entry_date: date,
    posted_at: datetime,
    actor: Any = None,
) -> PaymentPosting:
    """**DR the tender's holding account · CR `2400 Customer credit balances`.**

    Money taken at a counter is HELD, not earned: there is no account, no
    invoice and nothing yet delivered, so it is a liability to a person who is
    becoming a customer. `apps/ledger/chart.py`'s own external-mapping note says
    exactly that of this account at line 2095 — an incoming *"2340 Advance
    Customer Payment"* maps to our 2400 — which is why no new account, no new
    designation and no re-sign is needed for any of this.

    **Worked, and it is the PO's own figure:** $25.00 cash on 12 May against
    `RCP-26-4471` → `DR 1010 Undeposited funds 25.0000 · CR 2400 Customer credit
    balances 25.0000`. Two lines, one entry, debits equal credits.

    Every figure is the caller's. This function computes no money.
    """
    amount = receipt.amount
    if not isinstance(amount, Decimal):  # pragma: no cover - the model gives a Decimal
        raise PaymentRuleError(
            f"counter receipt amount {amount!r} is not a Decimal — money is NUMERIC(18,6) and "
            "never a float (CLAUDE.md hard rule 2). Refused rather than converted.",
            br_ref="BR-PAY-002",
        )
    if amount <= ZERO:
        raise PaymentRuleError(
            f"counter receipt {receipt.receipt_no} is {amount}. A journal entry for money that "
            "did not move is a line somebody has to explain; nothing is posted for a zero "
            "receipt.",
            br_ref="BR-LED-001",
        )

    posting = import_module(f"apps.{LEDGER_MODULE}.{POSTING_MODULE}")
    compose_key = _resolve(LEDGER_MODULE, POSTING_KEY_CALL, POSTING_MODULE)
    write = _resolve(LEDGER_MODULE, POST_CALL, POSTING_MODULE)
    if compose_key is None or write is None:  # pragma: no cover - defensive
        raise PaymentRuleError(
            f"apps.{LEDGER_MODULE}.{POSTING_MODULE} publishes neither {POST_CALL} nor "
            f"{POSTING_KEY_CALL}, so this counter receipt cannot reach the books. Payments may "
            "not write journal lines itself — that service is the sole writer (CLAUDE.md hard "
            "rule 5).",
            br_ref="BR-LED-001",
        )

    dimensions = {"source_type": SOURCE_COUNTER_RECEIPT, "source_id": receipt.pk}
    lines = (
        posting.PostingLine(
            ledger_account_id=(
                clearing_account_id if clearing_account_id is not None else _gl(GL_UNDEPOSITED)
            ),
            side="debit",
            amount=amount,
            **dimensions,
        ),
        posting.PostingLine(
            ledger_account_id=_gl(GL_CUSTOMER_CREDIT),
            side="credit",
            amount=amount,
            **dimensions,
        ),
    )
    request = posting.PostingRequest(
        posting_key=compose_key(
            source_type=SOURCE_COUNTER_RECEIPT,
            source_id=receipt.pk,
            event=EVENT_COUNTER_COLLECTED,
        ),
        entry_date=entry_date,
        posted_at=posted_at,
        currency=receipt.currency,
        lines=lines,
        source_type=SOURCE_COUNTER_RECEIPT,
        source_id=receipt.pk,
        memo=f"Counter receipt {receipt.receipt_no}",
        audit_context={
            "receipt_no": receipt.receipt_no,
            "source_ref": receipt.source_ref,
            "amount": str(amount),
        },
    )
    return _write(posting, request, actor=actor, subject=f"counter receipt {receipt.receipt_no}")


def post_counter_receipt_released(
    *,
    receipt: Any,
    targets: Any,
    entry_date: date,
    posted_at: datetime,
    actor: Any = None,
) -> PaymentPosting:
    """**DR `2400 Customer credit balances` · CR each charge code's own revenue.**

    The liability is released by the two TERMINAL outcomes and by nothing else.
    Approval APPLIES the held credit to the application fee; refusal EARNS it
    because the fee is non-refundable — *"if it is refuse then it is application
    fees non refundable - it stya in books"*. In double entry those are the same
    act, so they are the same entry.

    `targets` is `[{"ledger_account_id", "charge_code", "amount"}]`, resolved by
    the CALLER from `rating.charges.gl_account_id` — the tenant's own mapping.
    **This function picks no account**, exactly as `PostingLine`'s docstring
    requires: *"This service does not pick accounts."*

    **Worked:** one target, `CC-REQFEE` $25.0000 at the code's revenue account →
    `DR 2400 25.0000 · CR <that account> 25.0000`.

    The debit is the SUM of the targets and not the receipt's amount, which is
    the over-collection rule made arithmetic: $30.00 taken against a $25.00
    quote releases $25.0000 and leaves $5.0000 sitting in 2400 as the liability
    it still is.
    """
    rows = [dict(target) for target in (targets or [])]
    if not rows:
        raise PaymentRuleError(
            f"counter receipt {receipt.receipt_no} has no revenue target, so there is nothing "
            "to release the liability INTO. Nothing is posted and nothing is guessed — the "
            "money stays in customer credit balances, where it is visible.",
            br_ref="BR-BIL-010",
        )
    total = ZERO
    for row in rows:
        amount = row.get("amount")
        if not isinstance(amount, Decimal):
            raise PaymentRuleError(
                f"a revenue target of {amount!r} is not a Decimal — money is NUMERIC(18,6) and "
                "never a float (CLAUDE.md hard rule 2).",
                br_ref="BR-PAY-002",
            )
        if amount <= ZERO:
            raise PaymentRuleError(
                f"a revenue target of {amount} moves no money. A zero journal line is a line "
                "somebody has to explain; the caller drops them instead.",
                br_ref="BR-LED-001",
            )
        if not row.get("ledger_account_id"):
            raise PaymentRuleError(
                f"a revenue target for {row.get('charge_code')!r} names no ledger account. The "
                "account is the tenant's own charge-code mapping (BR-BIL-010) and this service "
                "never picks one.",
                br_ref="BR-BIL-010",
            )
        total += amount
    total = total.quantize(Decimal("0.0001"))
    if total > receipt.amount:
        raise PaymentRuleError(
            f"the revenue targets total {total} against a receipt of {receipt.amount} "
            f"{receipt.currency}. More cannot be earned than was handed over — an entry built "
            "from these figures would credit revenue the counter never took.",
            br_ref="BR-PAY-1140",
        )

    posting = import_module(f"apps.{LEDGER_MODULE}.{POSTING_MODULE}")
    compose_key = _resolve(LEDGER_MODULE, POSTING_KEY_CALL, POSTING_MODULE)
    write = _resolve(LEDGER_MODULE, POST_CALL, POSTING_MODULE)
    if compose_key is None or write is None:  # pragma: no cover - defensive
        raise PaymentRuleError(
            f"apps.{LEDGER_MODULE}.{POSTING_MODULE} publishes neither {POST_CALL} nor "
            f"{POSTING_KEY_CALL}, so this release cannot reach the books (CLAUDE.md hard rule 5).",
            br_ref="BR-LED-001",
        )

    dimensions = {"source_type": SOURCE_COUNTER_RECEIPT, "source_id": receipt.pk}
    lines = [
        posting.PostingLine(
            ledger_account_id=_gl(GL_CUSTOMER_CREDIT),
            side="debit",
            amount=total,
            **dimensions,
        )
    ]
    for row in rows:
        lines.append(
            posting.PostingLine(
                ledger_account_id=row["ledger_account_id"],
                side="credit",
                amount=row["amount"],
                **dimensions,
            )
        )
    request = posting.PostingRequest(
        posting_key=compose_key(
            source_type=SOURCE_COUNTER_RECEIPT,
            source_id=receipt.pk,
            event=EVENT_COUNTER_RELEASED,
        ),
        entry_date=entry_date,
        posted_at=posted_at,
        currency=receipt.currency,
        lines=tuple(lines),
        source_type=SOURCE_COUNTER_RECEIPT,
        source_id=receipt.pk,
        memo=f"Counter receipt {receipt.receipt_no} earned",
        audit_context={
            "receipt_no": receipt.receipt_no,
            "source_ref": receipt.source_ref,
            "earned": str(total),
            "held_remaining": str(receipt.amount - total),
        },
    )
    return _write(
        posting, request, actor=actor, subject=f"counter receipt {receipt.receipt_no} release"
    )


# ════════════════════════════════════════════════════════════════════════════
# `CR-136-BRC07` `P2.22` — THE DRAWER DIFFERENCE. ⚠ THIS SUPERSEDES THE DRAWING
# ════════════════════════════════════════════════════════════════════════════
#: The counter SESSION as a source document — a FOURTH source type beside
#: `payment`, `deposit_batch` and `counter_receipt`. The document an auditor
#: lands on when they ask *"what is the 12.00?"* is the till that was counted,
#: not any payment in it: no single payment was wrong, the DRAWER was.
SOURCE_COUNTER_SESSION = "counter_session"

#: The event. One per session, and one only: a till is counted once — at close
#: if the clerk counted it, at declare if a supervisor sealed it first — so
#: `counter_session|<id>|drawer_counted` is the replay guard for BOTH paths
#: (hard rule 6). A retried close writes one entry, never two.
EVENT_DRAWER_COUNTED = "drawer_counted"

#: `6850 Cash over and short` — expense, operating expenses, seeded between
#: `6800 Bank fees` and `6900 Bad debt`. **RESOLVED BY DESIGNATION AND NEVER BY
#: CODE**, which is `apps/ledger/chart.py`'s whole reason for existing: a
#: utility may re-code it on Settings → Accounting and any Python that said
#: `code == "6850"` would be a latent misposting. The seeding is `P2.21`, a
#: parallel lane's task; until it lands `_gl()` refuses this BY NAME rather
#: than posting a drawer difference into a bucket nobody mapped.
GL_CASH_OVER_SHORT = "cash_over_short"


#: The ledger's own top-up for `6850`, resolved BY NAME like every other call
#: across this seam — payments carries no import edge into ledger (B2 §2).
CASH_OVER_SHORT_TOP_UP = "ensure_cash_over_short_account"


def _cash_over_short_account(actor: Any = None) -> Any:
    """`6850`'s id for this tenant, or a refusal a person can act on.

    ⚠ **IT TOPS THE CHART UP FIRST, AND THAT IS `P2.21`'s REQUIREMENT RATHER
    THAN THIS LANE'S IDEA.** `CR-136-BRC07` §9(b), written by the lane that
    seeded the account: *"Call `apps.ledger.services.
    ensure_cash_over_short_account(actor)` at the top of the posting, exactly
    as the allowance estimate calls its own top-up: a posting that refuses
    because a pointer is missing is a posting a clerk cannot fix from the
    screen they are on — and that screen is the one where they have just
    counted a bag of cash."* `6850` IS in the provisioning seed, so for a
    tenant created from today this call creates nothing and costs one indexed
    read; what it covers is a live beta tenant between a deploy and the
    post-migrate sweep, and a tenant whose sweep failed and carried on
    (BR-TEN-074).

    ⚠ **`None` IS A REAL STATE AND IT REFUSES. IT NEVER SUBSTITUTES.** §9(a):
    a utility that hand-added its own `6850` keeps it, and `cash_over_short`
    then resolves to nothing for them. Posting a drawer difference into
    whatever account came to hand would put somebody else's money in it, and
    **hard rule 4 leaves nobody a way to move a journal line afterwards** —
    there is no draft state to repair an entry from. So the refusal below is
    the whole of the behaviour for that tenant, and the fix is one row on
    Settings → Accounting.

    ⚠ **`_gl()` ALONE IS NOT ENOUGH HERE, AND THE MEASUREMENT IS WHY.** It
    handles *the designation exists and this tenant mapped nothing to it* and
    answers a sentence for it. It does **not** handle *the designation is not
    one the ledger knows*, which is `cash_over_short`'s state until `P2.21`
    seeds it: `apps/ledger/selectors.py` raises a bare `ValueError` — *"Nothing
    here invents a fourteenth — a posting with no home is an OQ row, not a new
    designation"* — and that exception would leave payments **untranslated**,
    straight past `PaymentRuleError`, past `api._as_catalog_refusal`, and reach
    a clerk as a 500 on a close that had already sealed their till.
    `DEF-047`'s lesson is exactly this shape: the callee's REFUSAL is as much
    part of the contract as its result, and the seam adapts both directions.

    Found by running the case rather than by reading the code — `_gl`'s own
    docstring says the ledger *"REFUSES an unknown designation rather than
    answering None"*, which is true and is the half that needed catching.
    """
    top_up = _resolve(LEDGER_MODULE, CASH_OVER_SHORT_TOP_UP, "services")
    if top_up is not None:
        try:
            top_up(actor)
        except Exception:  # noqa: BLE001 — a failed top-up is not a failed close
            # ⚠ **SWALLOWED ON PURPOSE, AND ONLY HERE.** The top-up is a
            # CONVENIENCE: its whole job is to spare a clerk a refusal they
            # cannot act on. If it fails, `_gl` below still decides — and it
            # either resolves the account, in which case the top-up was never
            # needed, or it REFUSES BY NAME, which is the outcome §9(a)
            # requires. Letting the top-up's own exception escape would turn a
            # named, actionable refusal into whatever the ledger happened to
            # raise, on the screen where somebody has just counted cash.
            pass
    try:
        return _gl(GL_CASH_OVER_SHORT)
    except PaymentRuleError:
        raise
    except Exception as unknown:  # the ledger does not carry this designation yet
        raise PaymentRuleError(
            f"this utility's chart has no {GL_CASH_OVER_SHORT!r} account, so a drawer "
            "difference cannot reach the books. The account is `6850 Cash over and short` "
            "and it is seeded at provisioning; a host provisioned before it existed repairs "
            "its chart from Settings → Accounting. Refused rather than posting the difference "
            "into a bucket nobody mapped — an entry is immutable the moment it lands, and "
            "there is no draft state to repair it from.",
            br_ref="BR-PAY-1185",
        ) from unknown


#: `DEF-LED-10073` — the currencies whose amounts a North American clerk reads
#: with a `$`. Any other code is written in front of the figure instead, so a
#: memo never shows a dollar sign on money that is not dollars.
_DOLLAR_CURRENCIES = ("USD", "CAD", "MXN")


def drawer_difference_memo(amount: Decimal, *, over: bool, currency: str | None) -> str:
    """The memo on a drawer-difference entry — `Counter drawer short $10.00`.

    ⚠ **`DEF-LED-10073` — IT READ `Counter drawer short 10.0000` UNTIL
    2026-10-12.** The memo is a sentence a clerk reads on the Journal, and it
    printed the STORED figure: hard rule 2 stores money at 4 decimals and
    DISPLAYS it at 2 (PO re-sign 2026-08-22, *"display both 2 decimal"*). The
    AMOUNT on the lines is untouched and stays exact; only the words change.

    ⚠ **AN ENTRY ALREADY POSTED KEEPS ITS OLD MEMO FOR EVER.** A posted journal
    entry is immutable (hard rule 4), so the memos written before this fix
    still read `10.0000` and no migration rewrites them. This changes what is
    written from now on.

    Half-up to the cent is the display rounding B4 already uses; a drawer is
    counted in cents, so nothing is actually rounded in practice.
    """
    shown = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    code = (currency or "").upper()
    figure = f"${shown}" if code in _DOLLAR_CURRENCIES or code == "" else f"{code} {shown}"
    return f"Counter drawer {'over' if over else 'short'} {figure}"


def post_counter_difference(
    *,
    session: Any,
    difference: Decimal,
    entry_date: date,
    posted_at: datetime,
    actor: Any = None,
) -> PaymentPosting:
    """A counted drawer that does not balance writes a balanced pair.

    **PO ruling 2026-09-23, verbatim:** *"(b) Post it. A short writes a
    balanced pair to a cash over/short account the day it is declared. Needs
    one new account added to the chart"*.

    ⚠ **THE BLUEPRINT SAYS THE OPPOSITE AND IS SUPERSEDED.** p059's acts table
    reads *"Close … The ledger: Nothing — counting is not a posting"*, and
    `P2.15` commits that sentence as a test. The ruling wins and that test
    flips for a non-zero difference.

        $12.0000 SHORT   DR 6850 Cash over and short 12.0000
                         CR 1010 Undeposited funds   12.0000
        $12.0000 OVER    DR 1010 Undeposited funds   12.0000
                         CR 6850 Cash over and short 12.0000

    **`difference` is COUNTED minus EXPECTED, so positive is OVER** — the sign
    convention `counter_sessions.difference` already documents. The amount on a
    line carries no sign (B2's `CHECK (amount >= 0)`); the DIRECTION is the
    side, which is why this function reads the sign once and never again.

    **AGAINST `1010`, NOT `1000`, AND THAT IS THE LOAD-BEARING CHOICE.** Taking
    a payment already debits `1010 Undeposited funds` (`post_payment_cleared`
    above). The bank receives only what was physically in the drawer, so a
    short has to LEAVE `1010` before the deposit clears it — otherwise
    reconciliation carries a `$12.00` stub in undeposited funds that no bank
    statement will ever match, for ever. `apps/ledger/reporting.py` documents
    the 1010 → 1000 move this depends on.

    **Every figure is the caller's. This function computes no money** — it
    reads a sign and takes an absolute value, and the ledger refuses the entry
    a second time if debits ≠ credits.

    Hard rule 5: payments does not write a journal line. This calls the ledger's
    posting service, exactly as every other leg in this file does.
    """
    if not isinstance(difference, Decimal):  # pragma: no cover - the caller quantizes
        raise PaymentRuleError(
            f"a drawer difference of {difference!r} is not a Decimal — money is never a float "
            "(CLAUDE.md hard rule 2). Refused rather than converted, because a conversion "
            "would hide the place where the money stopped being exact.",
            br_ref="BR-PAY-002",
        )
    if difference == ZERO:  # pragma: no cover - the caller returns before this
        raise PaymentRuleError(
            "a drawer that balanced posts nothing. A journal line for money that did not move "
            "is a line somebody has to explain.",
            br_ref="BR-LED-001",
        )

    posting = import_module(f"apps.{LEDGER_MODULE}.{POSTING_MODULE}")
    compose_key = _resolve(LEDGER_MODULE, POSTING_KEY_CALL, POSTING_MODULE)
    write = _resolve(LEDGER_MODULE, POST_CALL, POSTING_MODULE)
    if compose_key is None or write is None:  # pragma: no cover - defensive
        raise PaymentRuleError(
            f"apps.{LEDGER_MODULE}.{POSTING_MODULE} publishes neither {POST_CALL} nor "
            f"{POSTING_KEY_CALL}, so this drawer difference cannot reach the books. Payments "
            "may not write journal lines itself — that service is the sole writer (CLAUDE.md "
            "rule 5).",
            br_ref="BR-LED-001",
        )

    amount = abs(difference)
    over = difference > ZERO
    dimensions = {"source_type": SOURCE_COUNTER_SESSION, "source_id": session.pk}
    over_short = _cash_over_short_account(actor)
    undeposited = _gl(GL_UNDEPOSITED)
    lines = (
        posting.PostingLine(
            ledger_account_id=(undeposited if over else over_short),
            side="debit",
            amount=amount,
            **dimensions,
        ),
        posting.PostingLine(
            ledger_account_id=(over_short if over else undeposited),
            side="credit",
            amount=amount,
            **dimensions,
        ),
    )
    key = compose_key(
        source_type=SOURCE_COUNTER_SESSION, source_id=session.pk, event=EVENT_DRAWER_COUNTED
    )
    request = posting.PostingRequest(
        posting_key=key,
        entry_date=entry_date,
        posted_at=posted_at,
        currency=session.currency,
        lines=lines,
        source_type=SOURCE_COUNTER_SESSION,
        source_id=session.pk,
        memo=drawer_difference_memo(amount, over=over, currency=session.currency),
        audit_context={
            "difference": str(difference),
            "direction": "over" if over else "short",
            "close_kind": session.close_kind,
        },
    )
    try:
        result = write(request, actor=actor)
    except posting.PostingError as refusal:  # the ledger's vocabulary → payments'
        raise PaymentRuleError(
            f"the drawer difference of {difference} could not be posted to the books: "
            f"{refusal}",
            br_ref="BR-LED-001",
        ) from refusal
    return PaymentPosting(
        entry_id=result.entry_id,
        posting_key=result.posting_key,
        created=result.created,
        debits=result.debits,
        credits=result.credits,
        line_count=result.line_count,
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-001@f4d2b18 (the four payments sources — B2 §2 + Addenda r12/r14 · EP-PAY-01-record-payments.md · 08-payments/02-business-rules.md · 08-payments/03-field-map.md — plus the DR/CR contract table in 04-docs/05-modules/09-ledger/06-epics/EP-LED-01-posting-consumption.md and LE-1 in 09-ledger/08-worked-examples.md)
# generated: 2026-08-11 by Eng-Lead (W4 payments closed-loop lane) · AMENDED 2026-08-18 by the CR-008 ledger lane (B-10 / OQ-264 CLOSED, PO "10 - A inside CR-008 now": `tender_clearing_account_id` — the mapped tender's own holding account, dead mapping refused BY NAME; `post_payment_cleared(clearing_account_id=…)` debits it, NULL = undeposited unchanged; `post_batch_reconciled(undeposited_credits=…)` credits what the receipts debited, refusing a split that does not foot to recorded_total. BOTH legs in one change — the half-change is the trial-balance fault the 2026-08-17 decision-log row measured in advance. RED-first proofs quoted in tests/test_cr008_tender_gl_posting.py)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — a seam) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · PROVED RED: with this seam made a no-op, a payment is recorded and allocated with NOTHING in the books — the trial-balance assertion fails naming the missing cash and AR legs. Quoted in the lane report before it was trusted green (hard-won law 7)
# exceptions: (1) THE THIRD LEG IS DERIVED, NOT TRANSCRIBED. US-LED-001's
#         contract row names DR cash / CR AR; an overpayment cannot balance on
#         those two alone, so the remainder credits `customer_credit_balance`
#         (2400) under BR-PAY-012 ("unapplied → account credit"), PE-4's 57.13,
#         and the refund row's own DR of that same account. REPORTED for
#         confirmation rather than silently taken.
#         (2) `undeposited_funds` (1010) IS NOT USED. The contract reads
#         "cash/undeposited" and LE-1 posts a payment to CASH; the counter-receipt
#         fork belongs to the deposit-batch lane — OQ-130, raised.
#         ⚠ **STALE SINCE 2026-08-11 AND LEFT VISIBLE RATHER THAN DELETED
#         (stamped 2026-09-15, CR-094-BRC01 lane H).** Sentence (2) has been
#         untrue of this file since the PO closed OQ-143 the same week it was
#         written: `GL_UNDEPOSITED` is what EVERY receipt leg debits when a
#         tender maps to no clearing account, the body of the file says so at
#         length, and `post_counter_receipt_collected` below debits it too. The
#         file's prose was corrected then and this trailer line was not — which
#         is the pointer rot CLAUDE.md names, one trailer along.
#         (3) THE BOOK DATE IS THE CLEARING DATE, not the posting date, because
#         bank reconciliation matches on clearing (BR-PAY-019/021) and cash in
#         the books must agree with cash at the bank. A judgment call, recorded
#         in the decision log.
#         (4) FIVE further payments contract rows — NSF, reversal/void, refund,
#         write-off, bank-rec difference — are NOT stubbed here; each belongs to
#         the lane that writes its rows.
#         (5) THE DEPOSIT ROW IS SIGNED AND STILL NOT BUILT: `purpose=deposit` is
#         refused upstream because its linkage (BR-BIL-012's first-bill deposit
#         line) does not exist, and crediting a liability nothing will draw down
#         is worse than refusing the payment.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
