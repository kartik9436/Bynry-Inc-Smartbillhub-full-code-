# ── Trace ──────────────────────────────────────────────
# Story:    The Invoice Cloud *Make Payment* API, confirmed by the Product
#           Owner before a line was written (decision log 2026-09-24, *"THE
#           INVOICE CLOUD *MAKE PAYMENT* API, CONFIRMED BEFORE A LINE IS
#           WRITTEN"*). Steps 9–20 of that row live here; steps 1–8 are
#           `partner_api._admit` and are not repeated.
# Rules:    BR-INT-083 (the partner door's one write) · BR-PAY-1197 (an
#           Invoice Cloud payment carries no till) · BR-PAY-1150 (a partner
#           may not waive our late fee) · BR-PAY-003 / BR-PAY-028 (inbound
#           payment idempotency) · BR-PAY-021 (posting date vs clearing date) ·
#           BR-TEN-081 / OQ-153 (a typed date is midnight in the UTILITY's
#           own timezone) · BR-INT-044 (one refusal, one body) ·
#           CLAUDE.md hard rule 1 (tenant scoping) · hard rule 2 (money is a
#           Decimal to four places, never a float) · hard rule 4 (financial
#           immutability — a correction is a new row) · hard rule 5 (only the
#           ledger posting service writes journal lines) · hard rule 6
#           (idempotency on inbound payments) · hard rule 7 (every money
#           action writes `audit_log`)
# Tests:    06-backend/tests/test_invoice_cloud_make_payment.py ·
#           06-backend/tests/test_invoice_cloud_make_payment_pg.py (law 14 —
#           the duplicate race cannot be shown on SQLite)
# Impacts:  apps/integrations/partner_api.partner_make_payment (the thin view) ·
#           apps/integrations/partner_urls.py (the address) ·
#           apps/integrations/manifests/pay_invoicecloud_partner.py (the
#           operation, which is the WRITE SCOPE) ·
#           apps/integrations/seams/payments.record_partner_payment
# ───────────────────────────────────────────────────────
"""`POST /api/partner/v1/make-payment/` — the FIRST WRITE on a read-only door.

HUMAN-OWNED (CLAUDE.md 🔒 "idempotency keys"). HUMAN-REVIEW-PENDING — AI-authored
2026-09-24 under the PO ruling of 2026-08-09 (*"AI will do it; we will review it
later as human"*), with a row in `12-governance/09-human-review-ledger.md`. It may
never reach lifecycle RATIFIED without a recorded human sign-off.

⚠ **WHY A FILE IN `integrations/` IS ON THAT LIST.** It composes the rule-6
idempotency key for money a partner posts us — `webhook|invoice_cloud:<their
reference>`, which is the exact string `settlements._payment_for` re-composes to
find a payout's members — and it decides which bill statuses money may be taken
against and which tenders this door refuses. `apps/payments/services.py` is on
the list because it shipped UNGUARDED and a disabled hard-rule-6 guard was
committed inside that window while G7 reported conform on everything else
(`DEF-058`). **A new caller that composes the key is the same exposure one file
along**, and a guard reporting conform over a path it cannot see is hard-won law
7's fifth shape. The RULE it implements stays human-signed (`BR-INT-083`,
`BR-PAY-1197`); this file implements it and invents none of it.

    THEY SEND                          WE ANSWER
    consumer_id      A-10650           payment_no   PMT-2609-000118
    bill_id          INV-2026-00412    status       posted
    payment_reference TID161007        amount       "142.18"
    paymentDate      20-06-2026        currency     USD
    amount           142.18            payment_reference  TID161007 (echoed)
    currency         USD               duplicate    false
    payment_method   card              deposit_batch_id / deposit_batch_code
                                                    (the day's Invoice Cloud
                                                    batch, when payments
                                                    stamped one)

WHAT THIS FILE IS AND IS NOT
-----------------------------
It is steps **9 to 20** of the confirmed plan: read the payload, refuse a
duplicate before any work, resolve the account and the bill by NUMBER inside
this tenant, map the tender to a tender the tenant actually configured, and
then hand the whole thing to `payments.services.record_payment` in ONE
transaction.

**It writes no payment row, no allocation row and no journal line itself.**
`record_payment` does creation → allocation → ledger → audit inside one
`atomic()` and it is the only thing that may (hard rules 4, 5 and 7, and B2 §2
— integrations does not write another module's tables). This module composes
arguments and refuses bad ones; that is all it does.

**Steps 1 to 8 are not here either.** `partner_api._admit` is the door for
every partner address and there is exactly one of those functions. A second
authorisation path on the one route that creates money would be the worst
possible place for this surface to have two answers to *may this caller act*.

THE WRITE SCOPE — WHY A NEW OPERATION AND NOT A FLAG
-----------------------------------------------------
⚠ **EVERY PARTNER KEY IN THIS PRODUCT WAS READ-ONLY UNTIL THIS ADDRESS
EXISTED, AND A READ KEY MUST NEVER CREATE MONEY.** The manifest declares
`record_payment` as its own operation, so a key's `scope` list has to NAME it
— `serve._scopes` reads the CREDENTIAL and `scope_permits` is check 5. That
means:

  * a key issued before this address existed cannot call it, because its scope
    was drawn from the operations that existed when it was minted;
  * a key granted the four reads and not this one is refused **through check
    5**, which shares the one indistinguishable `404`, the one body and the
    padded floor with an unknown key — so a partner probing for a write door
    learns nothing about whether it exists;
  * granting it is a clerk ticking a row that says *Take a payment* beside four
    that say *Read*. `machine_auth.issue_key` refuses an empty scope and gives
    no default, so nothing acquires this by omission (hard-won law 3 — the
    unsafe option is the one you type).

A boolean on the connection would have been the obvious cheaper shape and it is
the thing the blueprint classes as a security defect in as many words (p017,
`CR-4`): a scope on the RELATIONSHIP is not a scope on the KEY a partner
actually holds.

THE IDEMPOTENCY KEY IS `webhook|invoice_cloud:<payment_reference>` — READ THIS
------------------------------------------------------------------------------
⚠ **AND IT IS NOT A NEW `invoice_cloud` SOURCE, WHICH IS WHAT THE CONFIRMED
PLAN FIRST RECOMMENDED.** Decision log 2026-09-24, mismatch 3: *"Adding
`invoice_cloud` is a deliberate act, recommended over reusing `import`"*. That
recommendation is **superseded**, and the reason is load-bearing rather than
stylistic:

`payments.settlements._payment_for` finds a payout's members by **re-composing
the string `webhook|<provider>:<reference>` literally** — the prefix is typed
into that function, not derived. So a payment recorded under
`invoice_cloud|TID161007` would be invisible to the settlement that later names
it: `ingest_payout` would file it under `MEMBER_PAYMENT_NOT_FOUND`, the payout
would still be written, and a real bank credit would sit against a payment this
product holds and cannot find. Nothing would raise. `OQ-PAY-12625`'s own row
states the same join from the other side.

So the SOURCE is `webhook` (the namespace for *a payment rail's own event id*,
which is exactly what Invoice Cloud is sending) and the PROVIDER travels in the
reference, giving one string that both halves of this integration compose the
same way:

    idempotency.inbound_payment_key(source="webhook", reference="invoice_cloud:TID161007")
        →  "webhook|invoice_cloud:TID161007"

⚠ **`payments.webhooks._record` COMPOSES THE IDENTICAL STRING FOR A CALLBACK
FROM THE SAME PROVIDER**, so if Invoice Cloud ever both POSTs a payment here
and re-delivers it through the signed webhook door, the second one is
recognised as the replay it is instead of taking the money twice. That is a
property of choosing the shared namespace and it would have been lost by a
private one.

STATUS IS `posted`, AND THE PAYMENT MEETS ITS BILL THE MOMENT IT IS POSTED
-------------------------------------------------------------------------
**Amended 2026-10-21 (`CR-186-BRC10`).** Until that date this section read
*"STATUS IS `processing`"*: `OQ-PAY-12627` was open, no clearing date was
passed, and a `processing` payment met no bill. **The PO answered it with
neither `processing` nor `cleared` — `posted`** — decision log 2026-10-21,
*"we cannot mark payment clear yet"* and *"we have to return posted and
internal status also should be posted or processing"*, and then for every
method: *"first they will pot the payment - so we crete the record and add
posting date; then later money is recieved in the bank account ; uitlity will
reconcile it bank statement that time it is cleared with clearing date"*.

So an Invoice Cloud payment is recorded **`posted`** by
`payments.services.record_payment` — which writes `posted` at entry for every
method — and is **applied to the bill it names at posting**, with its journal
entry written then. It becomes `cleared` only when the utility reconciles the
day's Invoice Cloud deposit batch against the bank statement. **No clearing
date is passed from here, and none may be**: that would be this door claiming
the bank agreed, which is the one thing the PO ruled it cannot say. The
partner's own request — *"save as cleared … show cleared as posted"* — is
superseded by the same ruling: we store and we answer one word, `posted`.

The bill is still resolved and passed as the allocation target, so it is
applied **specific-bill** (decision log 2026-10-21, *"Payment application and
its accounting entry … confirmed unchanged"*): up to what that bill owes, and
anything above it carried as account credit.

See `_UNAVAILABLE` below for the one sentence that travels on every successful
response. It is for a machine, not a clerk: this surface has no catalogue line
and B14 rule 33 is not in play, because nothing here is drawn on a screen.

WHAT IS ACCEPTED, IGNORED AND RECORDED
---------------------------------------
`tenant_id` and `company_id` are read, put on the run row's window text, and
compared against nothing — PO ruling 2026-09-17, verbatim: *"you will ahve to
remove company ID filter from all Apis - we cannot tell tenant ID outside our
system"*. Refusing a mismatch would contradict that ruling and would break a
live partner on the day we told them to stop sending it.

`late_fee_waived` is **read and not honoured** (`BR-PAY-1150`, PO 2026-09-17:
*"Can a partner waive a late fee? - no"*). It is RECORDED on the run row so a
manager can see the partner claimed it, because a silently half-honoured row is
a discrepancy the partner finds before we do — which is the judgment the
decision log of 2026-09-17 already recorded for the feed.

`create_credit_note` is read and recorded on the run row. The PO honoured it
on 2026-09-17 (*"yes"*) for an OVERPAYMENT, and an overpayment is decided by
the ALLOCATOR at posting: whatever the named bill cannot absorb is carried as
account credit (`BR-PAY-010`), which is what the flag asks for. This module
decides no amount of its own — that would be computing rather than
recording.

WHAT WOULD MAKE THE CHECKS ON THIS FILE PASS WRONGLY — asked first (law 7)
---------------------------------------------------------------------------
**1 · The duplicate check.** A test that posts twice and asserts one payment
passes just as happily if the pre-check is removed, because the unique index
catches it one layer down — which is exactly how `DEF-058` shipped a disabled
guard. So both layers are asserted separately, and the second one is asserted
on **PostgreSQL only**, by committing the first copy in another connection.

**2 · The refusal indistinguishability.** A per-case `assert 404` proves
nothing, because a route that does not exist is also a 404. The case compares
the **whole response body byte for byte** across seven causes including the
missing write scope, and holds each to `REFUSAL_FLOOR_S`.

**3 · The read-only key.** Asserting that a key with the write scope succeeds
says nothing about a key without it. The case is the negative one: the same
request, the same partner, the same body, a key scoped to the four reads →
the stranger's bytes.

**4 · `counter_session_id` being NULL.** It is NULL by default, so asserting
`is None` passes on a build that never looked at tills at all. Since
`CR-186-BRC10` the payment DOES carry a deposit batch — the day's Invoice Cloud
batch, stamped at posting by payments — so the case asserts the till is NULL
and, separately, that whatever batch the reply names is the one on the row.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any

from apps.integrations import shapes

# ═══════════════════════════════════════════════════════════════════════════
# What their document sends — the field names, and why there are so few aliases
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **THE PARTNER'S SPECIFICATION IS NOT IN THIS REPOSITORY.** Every field name
# below is one the decision log of 2026-09-24 quotes from *Smart360 Next ↔
# Invoice Cloud, Make Payment API Specification v1.0* — `consumer_id: 69843`,
# `bill_id: 452615`, `paymentDate "20-06-2026"`, `tenant_id`, `company_id`,
# `late_fee_waived`, `create_credit_note`, `amount`, `currency`. Nothing here is
# a name this lane invented, and a name the record does not carry is not
# accepted on a guess (hard-won law 3).
#
# ⚠ **THE TENDER IS THE ONE FIELD THE RECORD DOES NOT NAME, AND IT IS
# `OQ-PAY-12632`, OPEN.** It is not a cosmetic gap: the tender decides which
# clearing account the money posts to, so defaulting it would put real money in
# the wrong place quietly. Two spellings are accepted — `payment_method`, and
# `tenderType`, which is the word THIS PRODUCT ALREADY USES TOWARD THIS PARTNER
# for this exact value (`shapes.INVOICE_CLOUD.resources["payments"].rename`) —
# and an absent or unknown one is REFUSED by name rather than defaulted.

#: Our account number. Their document's integer `consumer_id` is the field; what
#: travels in it is our text, because PO 2026-09-17 settled how our ids move:
#: *"a) they store our text exactly as we send it"*. `/partner/v1/accounts`
#: already hands them `A-10650`, so there is nothing to convert and no second
#: identity to keep (B14 rule 31 — no database id is ever the visible value).
FIELD_ACCOUNT = "consumer_id"
#: Our invoice number, the same way. `/partner/v1/bills` serves it as
#: `invoiceNo` under the Invoice Cloud dialect and `id` natively; both are the
#: same string, `INV-2026-00412`.
FIELD_BILL = "bill_id"
#: THEIR immutable payment identifier, whichever column they confirm it is.
#: ⚠ **NOT ALIASED TO `id` OR `FeeEntryId`, DELIBERATELY** — `OQ-PAY-12626` is
#: OPEN precisely because their own specification (§32) does not yet say which
#: of those two is immutable, and accepting either here would let the answer
#: change under us without anything going red. Their integration maps whichever
#: they confirm INTO this field; that is the open question's own reading.
FIELD_REFERENCE = "payment_reference"
#: `DD-MM-YYYY` in their document. `YYYY-MM-DD` is accepted too and is not an
#: invented spelling: it is what every other surface of this product sends and
#: receives, and `_read_date` tells the two apart without guessing.
FIELD_DATE = "paymentDate"
FIELD_AMOUNT = "amount"
FIELD_CURRENCY = "currency"
#: See the block above. `OQ-PAY-12632`.
FIELD_METHOD = "payment_method"
FIELD_METHOD_ALIAS = "tenderType"
#: Accepted, ignored, RECORDED (PO ruling 2026-09-17).
FIELD_TENANT = "tenant_id"
FIELD_COMPANY = "company_id"
#: Read, not honoured, recorded (`BR-PAY-1150`).
FIELD_LATE_FEE_WAIVED = "late_fee_waived"
#: Read and recorded; the allocator decides any overpayment at posting.
FIELD_CREDIT_NOTE = "create_credit_note"
#: Free text a partner may send with the payment; it lands on `payments.memo`.
FIELD_MEMO = "memo"

#: How long a value from an outside caller may be before it is cut. The same
#: reasoning `partner_api._company_named` records: these strings reach a run
#: row's summary, which a manager reads on S142, and an untrimmed field is a
#: place to put a megabyte or a forged second log line.
MAX_TEXT = 64


class PayloadRefused(Exception):
    """The body could not be read, or names something this utility does not have.

    ⚠ **THIS IS NOT THE DOOR'S REFUSAL AND MUST NEVER BECOME IT.** It is
    reachable only past all eight checks, so the caller already holds a live
    key for a live utility with the write scope on it — telling them *amount
    must be greater than zero* says nothing they could not work out from their
    own request body, and answering them the door's five words instead would
    send their engineer to look at their credentials for a bug in their JSON.

    ⚠ **AND THE ONE EXCEPTION IS THE BILL, WHICH IS WHY `bill_not_found` SAYS
    SO LITTLE.** *No such bill* and *not this utility's bill* must be one
    answer, or a partner could walk our invoice numbers and learn which exist —
    an enumeration oracle on a money document, the same one
    `partner_bill_download` closes structurally. The lookup here is narrowed to
    the account FIRST, so all three cases leave through one `.first()` that
    returned `None` and there is no branch that knows which it was.
    """

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


# ── the codes a partner branches on ────────────────────────────────────────
#
# One per thing a partner can actually fix at their end. They are stable
# strings, not sentences: the sentence is for a human reading a support ticket
# and the code is what their integration switches on (`BR-INT-044` bounds what
# a REFUSAL may say; these are not refusals of the door).
CODE_FIELD_REQUIRED = "FIELD_REQUIRED"
CODE_BAD_AMOUNT = "BAD_AMOUNT"
CODE_BAD_DATE = "BAD_DATE"
CODE_BAD_CURRENCY = "BAD_CURRENCY"
CODE_ACCOUNT_NOT_FOUND = "ACCOUNT_NOT_FOUND"
CODE_BILL_NOT_FOUND = "BILL_NOT_FOUND"
CODE_METHOD_NOT_CONFIGURED = "METHOD_NOT_CONFIGURED"
CODE_METHOD_NEEDS_A_TILL = "METHOD_NEEDS_A_TILL"
CODE_PAYMENT_REFUSED = "PAYMENT_REFUSED"

#: `PAYMENT_ALREADY_EXISTS` is a **200 and not an error** — decision log
#: 2026-09-24, *"A replay returns `RecordedPayment(created=False)` — never an
#: exception — and the response says `duplicate: true`"*. It is named here
#: beside the refusals so a reader meets the distinction in one place: a
#: partner retrying after a timeout did the right thing, and telling them their
#: request failed is how a retry becomes a second payment.
CODE_ALREADY_EXISTS = "PAYMENT_ALREADY_EXISTS"


@dataclass(frozen=True)
class MakePaymentRequest:
    """One Invoice Cloud payment, read and type-checked, nothing resolved yet.

    Frozen because every field is a fact the caller stated: a later step that
    "corrected" one would be changing what the partner said, and the run row
    and the audit row would then disagree with their own system.
    """

    account_no: str
    bill_no: str
    reference: str
    paid_on: date
    amount: Decimal
    currency: str | None
    method_code: str
    memo: str | None
    #: Accepted, ignored, recorded.
    named_tenant: str
    named_company: str
    #: Read, not honoured.
    late_fee_waived: bool
    create_credit_note: bool

    @property
    def idempotency_reference(self) -> str:
        """`invoice_cloud:TID161007` — the half that travels INSIDE the key.

        The provider stem is `PROVIDER` below and not the connector's
        `provider_key`, for the reason that constant records.
        """
        return f"{PROVIDER}:{self.reference}"


#: The provider stem inside the idempotency key.
#:
#: ⚠ **IT IS THE VENDOR AND NOT THE CONNECTOR KEY, AND THE DIFFERENCE MATTERS
#: EXACTLY ONCE.** `pay_invoicecloud_partner` is the row a clerk sees and is an
#: accommodation of a product limitation (`BR-INT-077`: one bidirectional
#: connector is what is owed, two rows is what unblocks a customer today). The
#: day those two rows become one, the connector key changes and **every
#: idempotency key already written would stop matching the settlement that
#: names it** — money silently unfindable, with nothing red. The VENDOR does
#: not change when our modelling of them does, so the vendor is what goes in
#: the key.
#:
#: ⚠ **IT IS A CONSTANT IN THIS FILE AND NOT A `provider_key` COMPARISON.**
#: `G77` fails a gate on branching by `provider_key` outside `adapters/` and
#: `manifests/` (`BR-INT-037`), and nothing here branches: this module IS the
#: Invoice Cloud dialect, the way `shapes.INVOICE_CLOUD` is, and a second
#: vendor posting payments gets its own module and its own stem rather than an
#: `if` added to this one.
PROVIDER = "invoice_cloud"


def _text(body: Any, name: str, *, required: bool = True) -> str:
    """One string field, trimmed, bounded, and refused when it is missing.

    An empty string is the same as absent. A field a partner sent as `""` is a
    field they have not filled in, and treating it as a value is how
    `"webhook|invoice_cloud:"` — one key for every payment they ever send —
    gets composed (`idempotency.PaymentKeyError` says the same from the other
    end).
    """
    raw = body.get(name)
    value = "" if raw is None else str(raw).strip()
    value = value[:MAX_TEXT].replace("\n", " ").replace("\r", " ")
    if not value and required:
        raise PayloadRefused(
            CODE_FIELD_REQUIRED,
            f"{name} is required and was not sent.",
        )
    return value


def _read_amount(body: Any) -> Decimal:
    """The amount as a **Decimal**, never a float (CLAUDE.md hard rule 2).

    ⚠ **`Decimal(str(value))` AND NEVER `Decimal(value)` ON A FLOAT.** JSON has
    one number type and a permissive reader hands this a `float`; `Decimal(142.18)`
    is `142.1800000000000352429...`, which is stored to four places as
    `142.1800` and looks right in every test written against it — until a
    figure lands on a boundary and the utility's books are a cent out with
    nothing to point at. Going through `str` keeps the digits the partner
    actually sent.

    Greater than zero, which is step 14 and is also `_amount`'s own rule in
    `payments.services`: this is a receipt, and a reversal is a new reversing
    row (BR-PAY-002 / hard rule 4), never a negative one.
    """
    raw = body.get(FIELD_AMOUNT)
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        raise PayloadRefused(CODE_FIELD_REQUIRED, f"{FIELD_AMOUNT} is required and was not sent.")
    try:
        amount = Decimal(str(raw).strip())
    except (InvalidOperation, ValueError, ArithmeticError):
        raise PayloadRefused(
            CODE_BAD_AMOUNT, f"{FIELD_AMOUNT} is not a number this product can read."
        ) from None
    if not amount.is_finite():
        raise PayloadRefused(CODE_BAD_AMOUNT, f"{FIELD_AMOUNT} is not a finite number.")
    if amount <= Decimal("0"):
        raise PayloadRefused(
            CODE_BAD_AMOUNT,
            f"{FIELD_AMOUNT} must be greater than zero. A refund or a reversal is its own "
            "record and never a negative payment.",
        )
    return amount


def _read_date(body: Any) -> date:
    """`20-06-2026` → 20 June 2026, and `2026-06-20` → the same day.

    ⚠ **THE TWO SPELLINGS ARE TOLD APART BY WHERE THE FOUR-DIGIT YEAR IS, NOT
    BY TRYING ONE AND CATCHING THE OTHER.** `10-06-2026` and `2026-06-10` are
    both unambiguous; what would be ambiguous is `06-10-2026` against
    `10-06-2026`, and neither of those is offered — this reads day-month-year
    because that is what their document writes, and month-day-year is not
    accepted in any form. A reader that guessed would put a payment five months
    out on a bill's ageing without anything looking wrong.

    `shapes._to_iso` is the inverse of the reformatter that serves THEM their
    dates, and it is reused rather than re-spelled so the two directions cannot
    drift apart into two spellings of one rule (`DEF-014`).
    """
    raw = body.get(FIELD_DATE)
    text = "" if raw is None else str(raw).strip()
    if not text:
        raise PayloadRefused(CODE_FIELD_REQUIRED, f"{FIELD_DATE} is required and was not sent.")
    text = text[:MAX_TEXT]
    # An ISO instant would carry a time and a zone, and a partner's clock is not
    # what decides which DAY a utility's money posted. Only the date part is
    # read, and it is anchored below in the utility's own zone (OQ-153).
    head = text.split("T")[0].split(" ")[0]
    parts = head.split("-")
    if len(parts) == 3 and len(parts[0]) == 2 and len(parts[2]) == 4:
        head = shapes._to_iso(head)
    try:
        return date.fromisoformat(head)
    except ValueError:
        raise PayloadRefused(
            CODE_BAD_DATE,
            f"{FIELD_DATE} must be DD-MM-YYYY (their document's spelling) or YYYY-MM-DD.",
        ) from None


def _read_currency(body: Any) -> str | None:
    """`CHAR(3)` or nothing. The AUTHORITY is the account, not this check.

    Absent means *the account's own*, which `payments.services._currency`
    resolves and which is the only correct default: a currency guessed here
    would be how a CAD tenant's books quietly become USD (hard rule 2).

    ⚠ **THREE LETTERS IS ALL THAT IS CHECKED HERE, AND THAT IS DELIBERATELY
    THIN.** There is no currency table in this product yet — Finance P0.6 is
    building one — so the real check is `_currency`'s, which refuses a code the
    ACCOUNT does not hold and holds no exchange rate. That refusal is the one
    that means something; this one only keeps a nine-character string out of a
    `CHAR(3)` column.
    """
    raw = body.get(FIELD_CURRENCY)
    text = "" if raw is None else str(raw).strip().upper()
    if not text:
        return None
    if len(text) != 3 or not text.isalpha():
        raise PayloadRefused(
            CODE_BAD_CURRENCY, f"{FIELD_CURRENCY} must be a three-letter code, such as USD."
        )
    return text


def _read_flag(body: Any, name: str) -> bool:
    """A partner's boolean, read the way JSON and form encodings both send it."""
    raw = body.get(name)
    if isinstance(raw, bool):
        return raw
    return str(raw or "").strip().lower() in ("true", "1", "yes")


def read_request(body: Any) -> MakePaymentRequest:
    """Step 9 — the payload, with nothing resolved and nothing written.

    Pure: same body, same answer, no database, no clock. That is what lets the
    duplicate check in step 10 run before any work is spent, and it is why
    every refusal in this function is about the REQUEST and never about this
    utility's data.
    """
    if not isinstance(body, dict):
        raise PayloadRefused(
            CODE_FIELD_REQUIRED, "the request body must be a JSON object of fields."
        )
    method = _text(body, FIELD_METHOD, required=False) or _text(
        body, FIELD_METHOD_ALIAS, required=False
    )
    if not method:
        raise PayloadRefused(
            CODE_FIELD_REQUIRED,
            f"{FIELD_METHOD} is required and was not sent. The tender decides which account "
            "the money clears through, so there is no default it would be safe to assume.",
        )
    return MakePaymentRequest(
        account_no=_text(body, FIELD_ACCOUNT),
        bill_no=_text(body, FIELD_BILL),
        reference=_text(body, FIELD_REFERENCE),
        paid_on=_read_date(body),
        amount=_read_amount(body),
        currency=_read_currency(body),
        method_code=method.lower(),
        memo=_text(body, FIELD_MEMO, required=False) or None,
        named_tenant=_text(body, FIELD_TENANT, required=False),
        named_company=_text(body, FIELD_COMPANY, required=False),
        late_fee_waived=_read_flag(body, FIELD_LATE_FEE_WAIVED),
        create_credit_note=_read_flag(body, FIELD_CREDIT_NOTE),
    )


# ═══════════════════════════════════════════════════════════════════════════
# What the run row says — the record half of *accepted, ignored and recorded*
# ═══════════════════════════════════════════════════════════════════════════


def window_text(request: MakePaymentRequest | None, *, outcome: str) -> str:
    """The sentence a manager reads on S142 for this call.

    *"Make payment, A-10650 INV-2026-00412 142.18 · recorded PMT-2609-000118 ·
    they named 393 · they claimed a late-fee waiver"*.

    ⚠ **THIS IS WHERE `tenant_id`, `company_id` AND `late_fee_waived` GO, AND
    IT IS THE HALF THAT IS EASY TO DROP.** All three are accepted and none
    changes what we do. A partner configured against the wrong utility, or one
    whose system believes it cancelled our late fee, used to find that out with
    a refusal; it now finds out never. Putting what they claimed on the row a
    manager already reads keeps the one genuine benefit of the old check — a
    misconfigured partner being VISIBLE — at zero cost and with nothing
    exposed, which is exactly the reasoning `partner_api._named_suffix` records
    for `company_id`.
    """
    if request is None:
        return f"Make payment, {outcome}"
    head = f"Make payment, {request.account_no} {request.bill_no} {request.amount}"
    parts = [f"{head} · {outcome}"]
    named = request.named_company or request.named_tenant
    if named:
        parts.append(f"they named {named}")
    if request.late_fee_waived:
        # ⚠ NOT HONOURED (`BR-PAY-1150`). Recorded so the discrepancy is OURS
        # to see first rather than the partner's to report.
        parts.append("they claimed a late-fee waiver")
    if request.create_credit_note:
        parts.append("they asked for a credit note")
    return " · ".join(parts)


# ═══════════════════════════════════════════════════════════════════════════
# Steps 11–18 — resolve, then hand over
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class MadePayment:
    """What one call did. `duplicate=True` is a `200`, never an error."""

    payment_id: str
    payment_no: str | None
    status: str
    amount: Decimal
    currency: str
    duplicate: bool
    reference: str
    unavailable: tuple[dict[str, str], ...] = field(default_factory=tuple)
    #: `CR-186-BRC10` — the deposit batch payments stamped at posting (one per
    #: provider per day, PO 2026-10-21) and its human code. None when payments
    #: stamped none, never a guess.
    deposit_batch_id: str | None = None
    deposit_batch_code: str | None = None


def _account_for(request: MakePaymentRequest) -> Any:
    """Step 11 — the account, BY NUMBER, inside this tenant.

    ⚠ **`customers_seam.collectable()` AND NOT A MODEL QUERY**, so the tenant
    filter is the seam's (stated twice — RLS on PostgreSQL and an explicit
    `tenant_id` because the suite runs on SQLite, where RLS does not exist and
    a cross-tenant read would pass the whole suite). There is no tenant
    argument anywhere on this path that could be pointed elsewhere.

    The number is the one `/partner/v1/accounts` already hands them, which is
    mismatch 2 of the confirmed plan: their document's `consumer_id: 69843` is
    an integer of their numbering and ours is `A-10650`, so what goes in the
    field is whatever we gave them.
    """
    from apps.integrations.seams import customers as customers_seam

    account = customers_seam.collectable().filter(account_no=request.account_no).first()
    if account is None:
        # ⚠ **THE NUMBER THEY SENT IS NOT ECHOED, AND THAT IS NOT TIDINESS.**
        # With the value in the sentence, *an account of another utility* and
        # *an account that does not exist* would answer bytes that differ —
        # by the caller's own input, admittedly, but the difference makes the
        # PROPERTY unassertable, and a property you can only reason about is
        # one that rots. With no value in it the two answers are byte-identical
        # and `test_another_utilitys_bill_is_the_same_answer_as_no_such_bill`
        # can say so in one comparison. The caller already knows what it sent.
        raise PayloadRefused(
            CODE_ACCOUNT_NOT_FOUND,
            f"That {FIELD_ACCOUNT} is not an account of this utility. Send the account "
            "number exactly as /partner/v1/accounts returned it.",
        )
    return account


def _bill_for(request: MakePaymentRequest, account: Any) -> Any:
    """Step 12 — the bill: exists, this tenant's, this account's, open to payment.

    ⚠ **ALL FOUR ARE ONE QUERY AND THERE IS NO BRANCH THAT KNOWS WHICH FAILED.**
    That is the same structural non-answer `partner_bill_download` relies on and
    it is the reason this refusal says so little: if *no such bill*, *another
    utility's bill*, *another account's bill* and *a void bill* answered
    differently, a partner could walk our invoice numbers and learn which exist
    and who owns them.

    ⚠ **`OPEN_TO_PAYMENT` IS NARROWER THAN THE SEAM'S `COLLECTABLE_STATUSES`,
    AND THE TWO EXTRA VALUES ARE WHY.** That tuple is what a partner may READ
    and it carries `void` and `corrected` on purpose — a finance system that
    posted the original needs to know it was voided. Neither is a thing money
    may be taken against: allocating a payment to a cancelled document is money
    against a bill the utility has withdrawn. `paid` stays in, because a bill
    settled a minute ago and paid again by a customer who had already sent the
    money is a real overpayment, and `BR-PAY-010` already says what happens to
    one (it carries as account credit).
    """
    from apps.integrations.seams import billing as billing_seam

    invoice = (
        billing_seam.collectable()
        .filter(account_id=account.pk, invoice_no=request.bill_no, status__in=OPEN_TO_PAYMENT)
        .first()
    )
    if invoice is None:
        # ⚠ **NO NUMBER IN THE SENTENCE — SEE `_account_for`.** Here it matters
        # most: a bill number is a money document's name, and four different
        # facts (no such bill · another utility's · another account's · void)
        # have to be ONE answer or the numbers can be walked. With the value
        # echoed the bytes differ and the property cannot be asserted at all.
        raise PayloadRefused(
            CODE_BILL_NOT_FOUND,
            f"That {FIELD_BILL} is not a bill of this account that is open to payment.",
        )
    return invoice


#: The statuses money may be taken against. See `_bill_for` for why this is not
#: `billing_seam.COLLECTABLE_STATUSES`.
OPEN_TO_PAYMENT: tuple[str, ...] = ("issued", "paid")


def _method_for(request: MakePaymentRequest) -> str:
    """Step 13 — the tender, mapped to a method THIS TENANT CONFIGURED.

    ⚠ **NOTHING HERE CREATES A PAYMENT METHOD, AND NOTHING DEFAULTS ONE.**
    `BR-PAY-026` makes the tender list a seeded, tenant-extensible LOOKUP, and a
    tenant that deactivated a method has said stop using it. Minting *Invoice
    Cloud* as a method on first use would put a row on a tenant's Reference-data
    page that no clerk asked for, and defaulting to `card` would post real money
    through the wrong clearing account (`BR-PAY-150`: every tender clears
    through `1010 UNDEPOSITED FUNDS`, and which tender it was is what the bank
    reconciliation matches on).

    **The check that the code exists is `payments.services._method`'s**, which
    refuses an unknown or deactivated one by name; this function does not
    duplicate it, because two implementations of *is this a real tender* is two
    answers and a path that consults the wrong one.

    ⚠ **WHAT THIS FUNCTION DOES DECIDE IS THE HAND TENDERS, AND IT IS A
    JUDGMENT RATHER THAN A RULING.** `cash`, `check` and `money_order` are
    refused on this door. PO ruling 2026-09-23 §3.4: money that passes through a
    person's hands belongs to a till *"so that every cash dollar belongs to
    somebody"* — and a partner door has no clerk, no session and therefore no
    till to name. A partner `cash` payment recorded with `counter_session_id`
    NULL would bank under the day's system till as money *"nobody's hands
    touched"*, which is the exact outcome that ruling exists to prevent. The
    three codes are read from `counters.HAND_TENDERS` rather than re-spelled,
    so there is one list and not two.
    """
    from apps.payments import counters as counter_rules

    if request.method_code in counter_rules.HAND_TENDERS:
        raise PayloadRefused(
            CODE_METHOD_NEEDS_A_TILL,
            f"{FIELD_METHOD} {request.method_code!r} is money that passes through a person's "
            "hands, and it belongs to a counter till that gets counted at the end of a shift. "
            "A partner has no till. Send the tender the money actually arrived as.",
        )
    return request.method_code


#: What travels on every successful response. **Machine-readable codes, not
#: prose a partner would have to parse** — the same posture `RECORD_UNAVAILABLE`
#: takes inside payments.
#:
#: ⚠ **THIS IS AN HONEST ABSENCE AND NOT A DISCLAIMER.** Hard-won law 1: a
#: comment claiming a guarantee is not the guarantee, and its mirror is a
#: silence a reader fills in optimistically.
#:
#: ⚠ **`recorded_as_processing_not_cleared` WAS REMOVED ON 2026-10-21
#: (`CR-186-BRC10`)** — it said the payment met no bill, and from that date it
#: does: the payment is `posted` and applied at posting (`OQ-PAY-12627`
#: answered `posted`). Leaving it would have been a live false sentence on
#: every successful reply.
_UNAVAILABLE: tuple[dict[str, str], ...] = (
    {
        "code": "late_fee_waiver_is_not_honoured",
        "br_ref": "BR-PAY-1150",
        "detail": "a late fee this utility assessed stands whatever an outside system says "
        "about it. The claim is recorded against the call and a person decides.",
    },
)


def record(
    *,
    caller_label: str,
    request: MakePaymentRequest,
) -> MadePayment:
    """Steps 11–19: resolve, hand over, and answer a replay as a replay.

    ⚠ **STEP 10 — THE DUPLICATE CHECK — IS NOT HERE AND IS NOT MISSING.** It is
    `record_payment`'s own `_existing()` lookup, which runs BEFORE it opens a
    transaction and returns `RecordedPayment(created=False)` without writing
    anything, backed by `uq_payments_webhook_key` for the race it cannot win.
    Writing a second pre-check in this module would be a third place that
    answers *has this already been recorded?*, and a path that consults the
    wrong one lets money in twice — which is the whole argument
    `idempotency.py` gives for there being ONE column.

    ⚠ **THE ACTOR IS THE CONNECTOR AND NOT A USER.** `actor_user_id` is NULL
    and `actor_kind`/`actor_label` name the partner (`ACTOR_KIND_INTEGRATION`
    is defined as *"a partner system acting through a connector"*). A payment
    row carries no `created_by` by design — who did it lives in `audit_log`,
    every time (hard rule 7) — and the KEY that was used is already on the
    integration run row, so the two together answer *which partner, which key,
    which call*.
    """
    from core import audit as core_audit

    from apps.integrations.seams import payments as payments_seam

    account = _account_for(request)
    invoice = _bill_for(request, account)
    method_code = _method_for(request)

    actor = core_audit.AutomationActor(
        kind=core_audit.ACTOR_KIND_INTEGRATION,
        name=caller_label,
    )
    recorded = payments_seam.record_partner_payment(
        actor=actor,
        account_id=account.pk,
        amount=request.amount,
        posted_at=posted_moment(request.paid_on),
        currency=request.currency,
        method_code=method_code,
        confirmation=request.reference,
        memo=request.memo,
        invoice_no=invoice.invoice_no,
        idempotency_reference=request.idempotency_reference,
    )
    return MadePayment(
        payment_id=recorded.payment_id,
        payment_no=recorded.payment_no,
        status=recorded.status,
        amount=recorded.amount,
        currency=recorded.currency,
        # ⚠ **STEP 19 — A REPLAY IS `created=False`, WHICH IS THE ABSENCE OF AN
        # EXCEPTION AND NOT THE PRESENCE OF ONE.** `PAYMENT_ALREADY_EXISTS` is a
        # `200` carrying the ORIGINAL payment's number, so a partner retrying
        # after a timeout reconciles against the money that exists rather than
        # sending it again.
        duplicate=not recorded.created,
        reference=request.reference,
        unavailable=_UNAVAILABLE,
        # `CR-186-BRC10` — the day's Invoice Cloud batch, when payments
        # stamped one. Read defensively: the name is payments' to publish.
        deposit_batch_id=_text_or_none(getattr(recorded, "deposit_batch_id", None)),
        deposit_batch_code=_text_or_none(getattr(recorded, "deposit_batch_code", None)),
    )


def _text_or_none(value: Any) -> str | None:
    """An id or a code as text, or None — never the string `"None"`."""
    return None if value in (None, "") else str(value)


def posted_moment(day: date) -> datetime:
    """A payment date as a moment — **midnight in the UTILITY's own clock**.

    `OQ-153`, closed by the PO on 2026-08-12, and `BR-TEN-081`. `DEF-094` is
    what happens when a write path anchors at UTC while the read path uses the
    tenant's zone: a Houston utility's *20 June* is stored as
    `2026-06-20T00:00:00Z` and every screen shows *19 June*.

    ⚠ **THERE IS NO CLOCK ON THIS PATH AND GATE `G6` BANS ONE.** The partner
    states the date; `posted_at` is user-entered and never `now()`
    (`BR-PAY-033`), because a defaulted posting date lets the moment a request
    happened to arrive decide whether a customer owes a late fee. The payment
    NUMBER is minted against this date too (`BR-TEN-035`), so a payment sent at
    01:00 on the 21st for the 20th numbers in the 20th's series.
    """
    from apps.payments import settings_seam

    return datetime.combine(day, time.min, tzinfo=settings_seam.tenant_timezone())


# ── Lifecycle ─────────────────────────────────────────────
# packet: the decision log of 2026-09-24 ("THE INVOICE CLOUD *MAKE PAYMENT*
#         API, CONFIRMED BEFORE A LINE IS WRITTEN") · OQ-PAY-12625 ·
#         OQ-PAY-12626 · OQ-PAY-12627 · BR-INT-083 · BR-PAY-1197 ·
#         BR-PAY-1150 · apps/payments/services.record_payment ·
#         apps/payments/idempotency.py · apps/payments/settlements._payment_for
# generated: 2026-09-24 by the INVOICE-CLOUD lane
# checklist: A✔ B=n/a(no screen — a partner's machine is the only caller)
#            C✔ D✔ E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: PROVED RED FIRST, each on the branch's own code and quoted in the lane
#        report: the duplicate pre-check removed (two payments, money doubled);
#        the write scope removed from the manifest (a read-only key creates a
#        payment); `OPEN_TO_PAYMENT` widened to the seam's COLLECTABLE_STATUSES
#        (a void bill takes money); the hand-tender refusal removed (a partner
#        `cash` payment banks under the system till); the DMY reader replaced
#        with a bare `fromisoformat` (20-06-2026 refused).
# amended: 2026-10-21 CR-186-BRC10 lane BAL-IC — `OQ-PAY-12627` answered
#          `posted`: no clearing date, applied at posting, the reply carries
#          the deposit batch, `recorded_as_processing_not_cleared` removed.
# exceptions:
#   E1 the idempotency SOURCE is `webhook` and not a new `invoice_cloud`
#      source, which SUPERSEDES mismatch 3 of the confirmed plan. The reason is
#      `settlements._payment_for`, which re-composes `webhook|<provider>:<ref>`
#      literally; see this module's docstring. Recorded in the decision log.
#   E2 `cash`, `check` and `money_order` are refused on this door. That is a
#      JUDGMENT from PO ruling 2026-09-23 §3.4 and not a ruling of its own;
#      recorded in the decision log with its worked case.
#   E3 the tender FIELD NAME is `OQ-PAY-12632`, OPEN — the partner's
#      specification is not in this repository and the decision log does not
#      quote it. Two spellings are accepted and an absent one is REFUSED; no
#      default is assumed.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
