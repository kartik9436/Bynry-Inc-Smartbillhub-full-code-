# ── Trace ──────────────────────────────────────────────
# Change:  CR-132-BRC07 (2026-09-22) — New World / Logos reads our receipts.
#          PO ruling of that date, "NEW WORLD / LOGOS: A SEPARATE ENDPOINT FOR
#          THE RECEIPT, THE LEDGER REUSED UNCHANGED": *"i think we shoudl create
#          seperate enpoint - you can se the same components that you use, dont
#          write completely new code - what way we can keep it sepearet"*.
# Rules:   CLAUDE.md hard rule 1 (the tenant is on the session; no tenant
#          argument exists here) · hard rule 2 (money stored to 4 decimals and
#          DISPLAYED to 2 — their fields are `9,2`, so the rounding happens once,
#          at emission, and the sum is measured AFTER it) · hard rule 4 (this is
#          a READ; nothing here updates an issued payment or a journal line) ·
#          hard rule 5 (balanced pairs — the distributions ARE our credit legs,
#          so their balance is our balance and no second arithmetic exists) ·
#          BR-INT-054 (integrations lands and hands over; the GL is resolved by
#          the seam Aclarian already resolves against, never re-derived here)
# Tests:   06-backend/tests/test_cr132_newworld_receipts.py
# Impacts: apps/integrations/partner_api.py (`partner_receipts`) ·
#          apps/integrations/partner_urls.py (the address) ·
#          apps/integrations/mappings.py (the two vocabularies, as CONFIG) ·
#          apps/integrations/manifests/erp_newworld.py
# ───────────────────────────────────────────────────────
"""integrations → New World / Logos: one payment, as their four-level Receipt.

WHY THIS FILE EXISTS AND `seams/payments.py` DID NOT SUFFICE
------------------------------------------------------------
XML is already a supported codec and `codecs.py`'s own docstring names this
exact case — *"a payment as JSON to one finance system and as XML to another"*.
**What makes parameterising `/api/partner/v1/payments` insufficient is the
SHAPE, not the format.** Our Payment is one row with one tender. Their Receipt
is four levels:

    ReceiptHeaderLevel                     one per receipt
      ReceiptTransactionLevel              1..n
        ReceiptTransactionGLDistribution   1..n per transaction
      ReceiptPaymentLevel                  up to FOUR per receipt

— with a BALANCING RULE across two of those levels that our flat payload has
no place to express. Bending the existing address into it would change a
contract four other ERP manifests already consume, which is why the PO ruled a
separate endpoint rather than a parameter.

WHAT IS REUSED, WHICH IS ALMOST EVERYTHING
-------------------------------------------
* the **GL accounts** — `seams/ledger.account_code`, the same resolution
  Aclarian's ledger rows go through. **Nothing here reads `ledger_accounts`
  itself.** A GL rule therefore changes in one place; the moment this file
  grew its own lookup there would be two things that can disagree, and the
  disagreement would present as a City's books being short.
* the **facts about a payment** — `seams/payments` for the amount, the tender,
  the account number and the payer's name, including its page-at-a-time
  reads, because the PO set a partner page at 1,000 rows.
* the **door** — key auth, tenant-from-key, the access log and the rate window
  are `partner_api._admit`'s and not one line of them is written again.
* the **XML** — `codecs`' own ElementTree conventions and its fixture
  discipline (`fixtures/newworld/`), so *supported* means the same thing on
  this codec as on the other four.

⚠ **THE DOCUMENT SHAPE — ATTRIBUTES ON A `<ROOT>` DOCUMENT (2026-10-21).**
---------------------------------------------------------------------------
**Every field is an ATTRIBUTE on its element and the root is `<ROOT>`.** Until
2026-10-21 this file wrote one CHILD ELEMENT per field under `<Receipts>`,
`VoidedFlag` as `false`, ISO dates, and three empty `ProjectCode1/2/3`
children at transaction level — and its tests passed, because they compared
the output with a fixture recorded from this same code (`DEF-INT-10304`). The
PO reported it against New World's own template and an accepted file from
another vendor; decision log 2026-10-21, *"New World / Logos receipt XML:
attributes on a `<ROOT>` document; five answers"*. Since then:

  * every attribute in the template is ALWAYS present, `""` when empty, in the
    template's order (`HEADER_ATTRIBUTES` … `CARD_ATTRIBUTES` below);
  * `VoidedFlag` is `"0"` / `"1"`; the three dates are MM/DD/YYYY;
  * project codes appear only on the distribution level;
  * **`validate` checks every file against the template before it is written
    to the City's folder or served by the API**, and a file that fails is
    neither. No XSD is used — PO: *"this was only as exmaple; not required"*.

Field mapping, GL mapping, tender mapping, widths, rounding and the balancing
rule did not change.

⚠ **THE CARD ATTRIBUTES ARE PRESENT AND ALWAYS EMPTY — CARD DATA IS NOT BUILT.**
--------------------------------------------------------------------------------
Their template carries `ReceiptPaymentCreditCardNumber`,
`ReceiptPaymentCreditCardType`, `ReceiptPaymentCreditCardExpirationDate` and
`ReceiptPaymentCreditCardValidationNumber`. **Populating any one of them pulls
cardholder data into a file and destroys the PCI scoping that keeps card data
out of this product entirely.**

⚠ **SUPERSEDED IN PART 2026-10-21 — FOR THE NAMES ONLY.** From CR-132
(2026-09-22) until then the four names never appeared at all. PO, 2026-10-21,
option A: *"Always write all four as `""`"*. So the four attributes are now
written on every payment node with the literal value `""`, by one loop over
`CARD_ATTRIBUTES`, and nothing else. A card payment still leaves as
`ReceiptPaymentType = 2` (Charge) **with no card number**: there is no
setting, flag, mapping entry or branch that could give one of them a value.
`G130` now fails any code or file that could assign them a value, and
`validate` refuses a file in which one is not empty.

⚠ **THE BALANCING RULE — AND IT WAS REVERSED ON THE DAY IT WAS BUILT.**
------------------------------------------------------------------------
Their platform requires that `DistributionAmount` sum EXACTLY to
`ReceiptTransactionAmount`. The first instruction this lane carried was to
REFUSE to emit a receipt that does not balance. **The PO reversed it**, verbatim:
*"please send receipt even if it is not balance"*.

**Their reasoning is better than the rule it replaced, so it is written out
rather than merely obeyed:** a refused receipt is money that silently never
reaches the City's books — invisible on both sides, and nobody is looking for a
receipt they do not know was withheld. An unbalanced one is money that arrives
wrong and **can be found and fixed**. It is the same principle this repo already
applies when a refused import row goes to the exception list rather than being
silently forgiven, and when a seam that cannot answer REPORTS rather than
answering zero.

**So: SEND IT — but never silently, and never plugged.**

  * **SEND IT.** No refusal and no exception blocks emission.
  * **NEVER SILENTLY.** `Receipt.balanced` is False, `Receipt.difference`
    states the figure, and `Emission.short_count` / `.short_total` report how
    many receipts were short and by how much, on the page and on the run row.
  * **NEVER PLUG IT.** No balancing line is added, no distribution is invented
    and no real one is adjusted to make the arithmetic work. **What is emitted
    is what is true.**
  * **THEIR IMPORTER ENFORCES THEIR RULE AND WE LET IT.** A rejection we can
    see beats a receipt we never sent; pre-empting their control with ours is
    what hid the money in the first place.

⚠ **WHERE AN IMBALANCE COMES FROM, AND WHY IT IS MEASURED RATHER THAN FIXED.**
We store money to four decimals (hard rule 2) and their field is `9,2`, so a
transaction of `100.0000` credited across three legs emits `33.33 × 3 = 99.99`
— a **one-cent rounding residue**, not a mis-mapping. The two have the same
symptom and completely different fixes: a residue has a standard answer
(assign the remainder to the largest distribution, which PLACES a real cent
rather than inventing one) and a mis-mapping does not. **Neither is implemented
here.** `measure_residues()` counts which is which so the choice can be put to
the PO with a figure; today's ruling is *send it*, and that is what this builds.

⚠ **WHAT THIS FEED ACTUALLY CARRIES, WHICH IS NARROWER THAN THE TENDER TABLE
SUGGESTS.** The New World payment feed is `origin = webhook` only — the
customer's own requirement, ruled 2026-09-22 — so **cash, cheque, money order
and lockbox cannot appear in it at all**: those are counter and post work and
they are `entry` or `import` origin. In practice this feed is **ACH and Card**,
which is why ACH having no value in their five-type list was the row that
mattered. The others are mapped for completeness and because a tender mapping
that is only half true is worse than none.

WHAT A RECEIPT IS MADE OF, AND WHY EACH LEVEL MAPS THE WAY IT DOES
-------------------------------------------------------------------
**ONE PAYMENT IS ONE RECEIPT WITH ONE TRANSACTION.** Their model allows several
transactions per receipt; our payment is one row with one tender and one
purpose, so inventing a second transaction would mean inventing the split
between them. A payment allocated across three bills is still one transaction
(see `_bill_number`).

**THE DISTRIBUTIONS ARE OUR JOURNAL ENTRY'S CREDIT LEGS, AND THAT IS
ARITHMETIC RATHER THAN A JUDGMENT.** `payments/ledger_seam.post_payment_cleared`
writes exactly one debit — the tender's clearing account, or undeposited funds
— and one to three credits: accounts receivable for what went against bills,
customer credit for what was carried, deposit liability for what is held. The
debit IS the payment amount, so by hard rule 5 the credits sum to it too.

Their `ReceiptPaymentLevel` already carries the cash side (the tender and the
amount), and their `GLAccountNumber` is documented as derivable from the
payment-code mapping — **the cash leg is the one thing they do not need from
us.** So emitting both sides would double the total and fail their own rule by
construction. The distributions are the OTHER side, and `DistributionType` is
`2` (Credit) on every one of them for an ordinary receipt.

⚠ **A REVERSAL IS A NEW RECEIPT, NEVER AN EDIT.** Their platform rule is that a
voided receipt cannot be altered; our hard rule 4 is that an issued payment is
never updated and a correction is a new row. **These agree, so there is one
mechanism and not two** — a bounced payment is a second payment row with a
negative amount and it becomes its own receipt. `VoidedFlag` is therefore
always `"0"` (it read `false` until 2026-10-21): we have never voided a
receipt we sent, because we have no way to alter one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from xml.etree import ElementTree as ET

from core.tenancy import current_tenant_id

ZERO = Decimal("0.00")

#: Their `ReceiptPaymentType` vocabulary, from the specification (v2023.1.11).
#: Held in `mappings.py` as CONFIG — see `mappings.NEWWORLD_PAYMENT_TYPES` —
#: because the PO's ruling was *"dont write completely new code"* and a
#: vocabulary is data. Imported lazily below for the same reason every other
#: cross-file read here is lazy.

#: `ReceiptCashier` (32) defaults to the IMPORTING USER on their side, which
#: would make every online receipt look as though a named person at the City
#: had taken it at a counter. Set explicitly to the system that did take it.
#: ⚠ 32 characters is their ceiling and this is 13.
#:
#: **RENAMED 2026-10-02 (`CR-088` R.2 item 3), from `"SMARTBILLHUB"`.** PO,
#: answering *"should the cashier name NewWorld receives become SMART360 NEXT?"*:
#: *"yes"*. Still 13 characters. The space is the only new character, and
#: their specification gives this field a width and no character set; it is an
#: XML text node, so a space needs no escaping. Receipts already sent keep the
#: old name on their side — this changes only what is sent from here on.
RECEIPT_CASHIER = "SMART360 NEXT"

#: `ReceiptNumber` is 13 characters and OPTIONAL — *they assign one if it is
#: blank*. Our own receipt number is `PMT-2608-000412`, which is **15**, so it
#: does not fit and truncating it would hand their books a reference that
#: matches no payment of ours and cannot be looked up by either side.
#:
#: ⚠ **SO IT IS LEFT BLANK AND OUR NUMBER TRAVELS IN `ReceiptDescription`
#: (256), WHICH IS NOT A CONSOLATION.** A receipt nobody can trace back is the
#: thing that makes a reconciliation impossible, and a wrong 13-character
#: number is worse than an absent one because it looks like an answer.
RECEIPT_NUMBER_BLANK = ""

#: Their field widths, named once so a truncation is a decision and not a
#: surprise. Every value written through `_fit` is cut to these.
WIDTH_RECEIVED_FROM = 64
WIDTH_DESCRIPTION = 256
WIDTH_CASHIER = 32
WIDTH_TRANSACTION_TYPE = 64
WIDTH_AR_CUSTOMER_NUMBER = 16
WIDTH_AR_BILL_TYPE = 32
WIDTH_AR_BILL_NUMBER = 16
WIDTH_GL_ACCOUNT = 64
WIDTH_CHECK_NUMBER = 32

#: `DistributionType` — their two values. `1` is Debit and `2` is Credit.
DISTRIBUTION_DEBIT = "1"
DISTRIBUTION_CREDIT = "2"

#: ── THE CONFIRMED TEMPLATE (PO 2026-10-21, DEF-INT-10304) ──────────────────
#: The document is `<ROOT>`, and every field is an ATTRIBUTE on its element, in
#: the order the PO's pasted template lists them. These tuples ARE that
#: template: the builder writes exactly these names in this order (`_write`),
#: and `validate` checks every file against them before it is sent or served.
#: No XSD is committed — PO: *"this was only as exmaple; not required"*.
ROOT_ELEMENT = "ROOT"
HEADER_ELEMENT = "ReceiptHeaderLevel"
TRANSACTION_ELEMENT = "ReceiptTransactionLevel"
DISTRIBUTION_ELEMENT = "ReceiptTransactionGLDistributionLevel"
PAYMENT_ELEMENT = "ReceiptPaymentLevel"

HEADER_ATTRIBUTES = (
    "ReceiptNumber",
    "VoidedFlag",
    "PaymentEnteredDate",
    "PaymentRecordedDate",
    "PaymentGLDate",
    "ReceivedFromName",
    "ReceiptDescription",
    "ReceiptCashier",
)
TRANSACTION_ATTRIBUTES = (
    "ReceiptTransactionType",
    "ReceiptTransactionAmount",
    "ReceiptTransactionDescription",
    "ReceiptTransactionARCustomerNumber",
    "ReceiptTransactionARBillType",
    "ReceiptTransactionARBillNumber",
)
DISTRIBUTION_ATTRIBUTES = (
    "GLAccountNumber",
    "DueToDueFromFund",
    "ProjectCode1",
    "ProjectCode2",
    "ProjectCode3",
    "DistributionAmount",
    "DistributionType",
)
#: The payment node's attributes either side of the four card attributes.
PAYMENT_ATTRIBUTES_BEFORE_CARD = (
    "ReceiptPaymentType",
    "ReceiptPaymentAmount",
    "ReceiptPaymentCheckNumber",
)
PAYMENT_ATTRIBUTES_AFTER_CARD = ("ReceiptPaymentOtherType",)

#: ⚠ **ALWAYS PRESENT, ALWAYS `""` — PO 2026-10-21, option A: *"Always write
#: all four as `""`"*.** This tuple is the ONLY place in the product the four
#: names are written as strings, and the builder's one loop over it writes the
#: literal `""`. `G130` fails any code that could give one of them a value.
#: Card data stays out of the product; only the empty NAMES travel.
CARD_ATTRIBUTES = (
    "ReceiptPaymentCreditCardNumber",
    "ReceiptPaymentCreditCardType",
    "ReceiptPaymentCreditCardExpirationDate",
    "ReceiptPaymentCreditCardValidationNumber",
)

#: Their `xs:double` attributes, which we write as `9,2` and which must never
#: be empty in a real file (the template's `""` is a placeholder).
AMOUNT_ATTRIBUTES = (
    "ReceiptTransactionAmount",
    "DistributionAmount",
    "ReceiptPaymentAmount",
)
DATE_ATTRIBUTES = ("PaymentEnteredDate", "PaymentRecordedDate", "PaymentGLDate")

#: The journal sides, named here so this module does not import ledger's
#: models at module scope (G6 forbids it and the module graph must stay a DAG).
SIDE_DEBIT = "debit"
SIDE_CREDIT = "credit"


@dataclass(frozen=True)
class Distribution:
    """One `ReceiptTransactionGLDistributionLevel` node.

    ⚠ **`DueToDueFromFund` AND `ProjectCode1/2/3` ARE WRITTEN EMPTY — RULED,
    NOT OMITTED AND NOT ZERO (PO 2026-09-22).**

    * **`DueToDueFromFund` — empty, never `0`.** The PO offered *"you can pick
      it up or say zero"* and instructed neither; the field is OPTIONAL and 64
      alphanumeric, so an empty one cannot corrupt their posting while **`0` is
      an invented fund identifier** their importer is free to read as fund
      zero. Because a GL account always travels, New World derives the fund
      from it exactly as most municipal charts intend.
    * **`ProjectCode1/2/3` — empty.** At THIS level they are an extra reporting
      dimension sitting alongside a GL breakdown — a City tracking revenue
      against a grant would use them — and **we hold no such dimension**.
      Deferred on the PO's own terms: *"if it changes we will figure it out"*.

    **An empty optional field is a fact; a plausible value is a lie that
    reconciles.** That sentence is the decision log's, from the day all three
    of these were answered, and it is why none of them is filled.
    """

    account: str | None
    amount: Decimal
    type: str

    @property
    def resolved(self) -> bool:
        """Whether we could name a GL account for this leg.

        ⚠ **A GL ACCOUNT IS ALWAYS SENT — PO 2026-09-22, *"we are mapping gL
        code to various utility services and all cahrge codes so we will ahve a
        gl code"* — so their spec's conditional is closed in our favour and an
        UNRESOLVED one is an exception rather than a shape.** When a tenant has
        not finished its mapping the element goes out EMPTY and the receipt is
        FLAGGED: *send it, never silently, never plug it*. A zero GL account
        and a plug distribution line are the same act.
        """
        return bool(self.account)

    def as_element(self, parent: Any) -> Any:
        node = ET.SubElement(parent, "ReceiptTransactionGLDistributionLevel")
        _write(
            node,
            DISTRIBUTION_ATTRIBUTES,
            {
                "GLAccountNumber": _fit(self.account, WIDTH_GL_ACCOUNT),
                # Empty, never `0` — see this class's docstring.
                "DueToDueFromFund": "",
                "ProjectCode1": "",
                "ProjectCode2": "",
                "ProjectCode3": "",
                "DistributionAmount": _money(self.amount),
                "DistributionType": self.type,
            },
        )
        return node


@dataclass(frozen=True)
class Transaction:
    """One `ReceiptTransactionLevel` node and the distributions beneath it."""

    type: str
    amount: Decimal
    description: str
    ar_customer_number: str
    ar_bill_type: str
    ar_bill_number: str
    distributions: tuple[Distribution, ...]

    @property
    def distributed(self) -> Decimal:
        """Σ `DistributionAmount`, **after** each has been rounded to their two
        decimals. Hard rule 2 rounds once, at display; their field is `9,2`, so
        THIS is the sum their importer will compute and it is the only sum
        worth comparing against."""
        return sum((_rounded(one.amount) for one in self.distributions), ZERO)

    @property
    def difference(self) -> Decimal:
        """Transaction amount − Σ distributions. **Positive means the
        distributions are SHORT**, which is the ordinary rounding residue; a
        negative one means they overshoot and is the rarer, more interesting
        case."""
        return _rounded(self.amount) - self.distributed

    @property
    def balanced(self) -> bool:
        return self.difference == ZERO

    def as_element(self, parent: Any) -> Any:
        node = ET.SubElement(parent, "ReceiptTransactionLevel")
        _write(
            node,
            TRANSACTION_ATTRIBUTES,
            {
                "ReceiptTransactionType": _fit(self.type, WIDTH_TRANSACTION_TYPE),
                "ReceiptTransactionAmount": _money(self.amount),
                "ReceiptTransactionDescription": _fit(self.description, WIDTH_DESCRIPTION),
                "ReceiptTransactionARCustomerNumber": _fit(
                    self.ar_customer_number, WIDTH_AR_CUSTOMER_NUMBER
                ),
                "ReceiptTransactionARBillType": _fit(self.ar_bill_type, WIDTH_AR_BILL_TYPE),
                "ReceiptTransactionARBillNumber": _fit(
                    self.ar_bill_number, WIDTH_AR_BILL_NUMBER
                ),
            },
        )
        # ⚠ **THE LICENCE ATTRIBUTES ARE NOT WRITTEN.** Their specification
        # carries them (optional) for licence receipting; they are *not
        # applicable to utility billing* and they are not in the template the
        # PO confirmed on 2026-10-21.
        #
        # ⚠ **NO PROJECT CODES AT THIS LEVEL — REMOVED 2026-10-21
        # (DEF-INT-10304).** Until that day this node carried three empty
        # `ProjectCode1/2/3` CHILDREN, ruled empty on 2026-09-22. The template
        # the PO confirmed on 2026-10-21 carries project codes only on the
        # distribution level, and their schema's optional transaction-level
        # names are `ReceiptTransactionProjectCodeN` — so `ProjectCodeN` here
        # matched no name of theirs at all. Removed by our judgment under law
        # 13, recorded in the decision log that day.
        for distribution in self.distributions:
            distribution.as_element(node)
        return node


@dataclass(frozen=True)
class PaymentNode:
    """One `ReceiptPaymentLevel` node — the tender the money arrived as.

    ⚠ **UP TO FOUR PER RECEIPT IS THEIR CEILING AND WE EMIT EXACTLY ONE.** Our
    payment row carries ONE tender (`payments.method`), so a second node would
    be a split we do not hold. `build_receipt` asserts the ceiling rather than
    trusting it, because a silent fifth node is a file their importer rejects
    with no reason we could reproduce.

    ⚠ **THERE IS NO CARD NUMBER ON THIS NODE AND THERE IS NO BRANCH THAT
    COULD PUT ONE THERE.** See the module docstring. A card payment is
    `ReceiptPaymentType = 2` and nothing else. Since 2026-10-21 the four card
    ATTRIBUTES are written on this node, present and always `""` (PO, option
    A) — this dataclass has no field that could carry a value for them.
    """

    type: str
    amount: Decimal
    check_number: str
    other_type: str

    def as_element(self, parent: Any) -> Any:
        node = ET.SubElement(parent, "ReceiptPaymentLevel")
        _write(
            node,
            PAYMENT_ATTRIBUTES_BEFORE_CARD,
            {
                "ReceiptPaymentType": self.type,
                "ReceiptPaymentAmount": _money(self.amount),
                # Their spec: only when the type is Check. Written empty
                # otherwise rather than omitted, because a cheque number IS how
                # a City matches a bank line and its absence must be visible.
                "ReceiptPaymentCheckNumber": _fit(self.check_number, WIDTH_CHECK_NUMBER),
            },
        )
        # ⚠ **PRESENT AND EMPTY, ALWAYS — AND THIS LOOP IS THE ONLY CODE THAT
        # WRITES THEM.** PO 2026-10-21, option A: *"Always write all four as
        # `""`"*. The value is the literal `""`, not a variable, so there is
        # nothing a card number could travel through; G130 fails any other
        # write of these names.
        for name in CARD_ATTRIBUTES:
            node.set(name, "")
        # Always present since 2026-10-21, "" when the tender maps to one of
        # their named types. Until then the attribute was omitted when empty.
        _write(node, PAYMENT_ATTRIBUTES_AFTER_CARD,
               {"ReceiptPaymentOtherType": self.other_type})
        return node


@dataclass(frozen=True)
class Receipt:
    """One whole receipt — header, its transactions and its payment nodes."""

    number: str
    voided: bool
    entered_date: date | None
    recorded_date: date | None
    gl_date: date | None
    received_from: str
    description: str
    cashier: str
    transactions: tuple[Transaction, ...]
    payments: tuple[PaymentNode, ...]
    #: Our own receipt number, for OUR run row and OUR exception list. It is
    #: not a field of theirs — see `RECEIPT_NUMBER_BLANK`.
    our_number: str = ""
    #: The tender code we had to send as *Other* under our own name for it,
    #: or "". Not a field of theirs either — it is how a clerk finds out a
    #: mapping row is missing without reading the file (see `Emission`).
    unmapped_tender: str = ""

    @property
    def unresolved_accounts(self) -> int:
        """How many distributions went out with no GL account — an exception
        this feed states, because the PO ruled a GL account ALWAYS travels."""
        return sum(
            1
            for transaction in self.transactions
            for one in transaction.distributions
            if not one.resolved
        )

    @property
    def difference(self) -> Decimal:
        """Σ over transactions of (amount − Σ distributions). **Stated as a
        figure, never hidden**, and it is what the PO's *send it even if it is
        not balance* makes visible on our side."""
        return sum((one.difference for one in self.transactions), ZERO)

    @property
    def balanced(self) -> bool:
        return self.difference == ZERO

    def as_element(self, parent: Any) -> Any:
        node = ET.SubElement(parent, "ReceiptHeaderLevel")
        _write(
            node,
            HEADER_ATTRIBUTES,
            {
                "ReceiptNumber": self.number,
                # "0" / "1" since 2026-10-21 (DEF-INT-10304); it read
                # "false" / "true" until then. Their schema types it
                # xs:unsignedByte.
                "VoidedFlag": "1" if self.voided else "0",
                "PaymentEnteredDate": _day(self.entered_date),
                "PaymentRecordedDate": _day(self.recorded_date),
                "PaymentGLDate": _day(self.gl_date),
                "ReceivedFromName": _fit(self.received_from, WIDTH_RECEIVED_FROM),
                "ReceiptDescription": _fit(self.description, WIDTH_DESCRIPTION),
                "ReceiptCashier": _fit(self.cashier, WIDTH_CASHIER),
            },
        )
        # Transactions first, then payment nodes — the template's order.
        for transaction in self.transactions:
            transaction.as_element(node)
        for payment in self.payments:
            payment.as_element(node)
        return node


@dataclass(frozen=True)
class Emission:
    """A page of receipts as bytes, **with what was wrong with it stated.**

    ⚠ **`short_count` AND `short_total` ARE THE HALF THE PO'S RULING TURNS ON.**
    *Send it even if it is not balance* is only safe while the imbalance is
    visible on our side; without these two numbers it is the silent version of
    exactly the failure the ruling was protecting against, one step further
    along. They go on the run row and into the envelope.
    """

    body: bytes
    receipts: tuple[Receipt, ...]

    @property
    def short_count(self) -> int:
        """How many receipts on this page do not balance."""
        return sum(1 for one in self.receipts if not one.balanced)

    @property
    def short_total(self) -> Decimal:
        """By how much, summed — signed, so a short page and an overshooting
        one cannot cancel out into a reassuring zero."""
        return sum((one.difference for one in self.receipts if not one.balanced), ZERO)

    @property
    def unresolved_gl_count(self) -> int:
        """Distributions across this page that carry no GL account.

        ⚠ **THE PO RULED A GL ACCOUNT ALWAYS TRAVELS**, so anything above zero
        here is a tenant whose accounting settings are unfinished — sent and
        flagged, exactly as an unbalanced receipt is, and for the same reason.
        """
        return sum(one.unresolved_accounts for one in self.receipts)

    def unmapped_tenders(self) -> list[str]:
        """Tender codes that went out as *Other* under our own word for them,
        so a clerk can add the mapping row rather than discovering it in a
        rejection from New World."""
        return sorted({one.unmapped_tender for one in self.receipts if one.unmapped_tender})

    def unbalanced(self) -> list[dict[str, str]]:
        """`[{receipt, difference}]` — which ones, by OUR receipt number, so a
        clerk or a support call can find the payment rather than being told a
        count and left to look."""
        return [
            {"receipt": one.our_number, "difference": str(one.difference)}
            for one in self.receipts
            if not one.balanced
        ]


# ── the small, total helpers ────────────────────────────────────────────────


def _rounded(value: Any) -> Decimal:
    """Four stored decimals → their two, half-up. Hard rule 2 and B4: **the
    rounding happens ONCE and it happens here**, at emission, which is why
    every sum in this file is computed on the output of this function and never
    on the stored figure."""
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _money(value: Any) -> str:
    """A `9,2` field's text. A string, never a float — hard rule 2 names the
    float by name, and a string keeps the exactness across every XML parser on
    the far end."""
    return str(_rounded(value))


def _day(value: date | None) -> str:
    """Their 10-character date, **MM/DD/YYYY** (PO 2026-10-21, DEF-INT-10304 —
    it was ISO `YYYY-MM-DD` until then). Empty when we hold none, because their
    fields say *default available* and a date we made up would date a posting."""
    return value.strftime("%m/%d/%Y") if value is not None else ""


def _write(node: Any, names: tuple[str, ...], values: dict[str, str]) -> None:
    """Every attribute in `names`, IN THAT ORDER, from `values` — **all present,
    `""` when empty** (PO 2026-10-21). A name missing from `values` is a
    `KeyError` here rather than an attribute silently left off, and a value for
    a name outside `names` is refused the same way, so the template is the only
    thing that decides the attribute set."""
    extra = set(values) - set(names)
    if extra:  # pragma: no cover - defensive; the template decides
        raise KeyError(f"not in the New World template: {sorted(extra)}")
    for name in names:
        node.set(name, values[name] or "")


def _fit(value: Any, width: int) -> str:
    """A value cut to their declared width, with newlines flattened.

    ⚠ **THE FLATTENING IS NOT TIDINESS.** A memo is clerk-typed free text and
    it lands in a municipality's finance system; a newline in an XML text node
    is legal, survives the parse, and is how one receipt's description becomes
    two lines in whatever report reads it downstream.
    """
    if value in (None, ""):
        return ""
    text = str(value).replace("\r", " ").replace("\n", " ").strip()
    return text[:width]


# ── the projection ──────────────────────────────────────────────────────────


def _config() -> Any:
    """`mappings`, imported inside the call. The two vocabularies are CONFIG
    there rather than code here — PO 2026-09-22, *"dont write completely new
    code"* — and a clerk's row on the connection overrides the default."""
    from apps.integrations import mappings

    return mappings


def _payment_type_for(payment: Any, tenant_id: Any) -> tuple[str, str, str]:
    """Our tender → their `(ReceiptPaymentType, ReceiptPaymentOtherType)`, plus
    the tender code when we had to fall back to our own word for it.

    **The decision table is `mappings.newworld_payment_type` and there is no
    branch here** — PO 2026-09-22, *"dont write completely new code"*. All this
    does is read the clerk's mapping row, if there is one, and hand both to the
    table.

    ⚠ **IT CANNOT REFUSE, AND THAT IS THIS DAY'S RULING ONE FIELD OVER.** An
    earlier draft raised `NotImplementedError` naming an open question, because
    their five types hold no ACH. **The PO answered it** — ACH, money order and
    lockbox all go as `3` Other with a word — so there is nothing left to stub,
    and a tender nobody has mapped goes as Other carrying OUR name for it and
    is COUNTED (`Emission.unmapped_tenders`) rather than withheld.
    """
    mappings = _config()
    method = getattr(payment, "method", None)
    code = str(getattr(method, "code", "") or "").strip().lower()
    mapped = None
    if code and tenant_id is not None:
        mapped = mappings.external_for(
            tenant_id, mappings.NEWWORLD_TARGET_KEY, "tender", code
        )
    payment_type, other_type = mappings.newworld_payment_type(code, mapped)
    fell_back = bool(
        code and not mapped and code not in mappings.NEWWORLD_TENDER_DEFAULTS
    )
    return payment_type, other_type, (code if fell_back else "")


def _bill_number(payment: Any) -> str:
    """`ReceiptTransactionARBillNumber` — the bill this receipt settled, or "".

    ⚠ **BLANK WHENEVER IT IS NOT EXACTLY ONE BILL, AND THE BLANK IS THE HONEST
    ANSWER.** A payment may be allocated across several invoices, and their
    field holds ONE number. Naming the first of three would tell a City's books
    that a $300 receipt paid one $100 bill; splitting the receipt into three
    transactions would mean splitting the GL credit across them, which is an
    ALLOCATION RULE nobody has agreed — the same thing `seams/ledger.as_record`
    refuses to invent when it meets three debits against four credits.

    A blank field is a partner looking the payment up by customer number; a
    wrong one is a partner reconciling against a bill that was never paid.
    """
    allocations = getattr(payment, "allocations", None)
    if allocations is None:
        return ""
    rows = list(allocations.all()[:2])
    if len(rows) != 1:
        return ""
    invoice = getattr(rows[0], "invoice", None)
    return str(getattr(invoice, "invoice_no", "") or "")


def _credit_legs(entry: Any) -> list[Any]:
    """The journal entry's CREDIT lines — the distributions, in line order.

    See the module docstring for why it is the credit side: their payment node
    already carries the cash, and their `GLAccountNumber` is derivable from
    the payment code, so the cash leg is the one thing they do not need from
    us. Emitting both sides would double the total and fail their own balancing
    rule by construction.
    """
    if entry is None:
        return []
    return [line for line in entry.lines.all() if str(getattr(line, "side", "")) == SIDE_CREDIT]


def journal_entry_for(payment: Any) -> Any:
    """The posted journal entry behind one payment, or `None`.

    ⚠ **`None` MEANS *WE CANNOT ANSWER*, NEVER *THERE IS NOTHING* (DEF-075).**
    A payment still processing has no entry yet and a deployment with no ledger
    has none at all; both come back with no distributions and a receipt that
    does not balance by its whole amount — which is exactly the case the PO's
    ruling wants VISIBLE rather than withheld.
    """
    try:
        from apps.ledger import models as ledger_models
    except ImportError:  # pragma: no cover - a deployment with no ledger
        # ⚠ **`ImportError` AND NOT `Exception`.** A bare `except Exception`
        # here would swallow a real fault inside `apps.ledger` and answer
        # `None` — and `None` means *no entry*, so every receipt would go out
        # with NO GL distributions and an imbalance of its whole amount,
        # flagged but unexplained. The only thing this branch is for is a
        # deployment that has no ledger module at all.
        return None
    tenant_id = current_tenant_id()
    if tenant_id is None:
        return None
    return (
        ledger_models.JournalEntry.objects.filter(
            tenant_id=tenant_id,
            source_type="payment",
            source_id=payment.pk,
            status=ledger_models.JE_POSTED,
        )
        .prefetch_related("lines__ledger_account")
        .order_by("entry_date", "id")
        .first()
    )


def build_receipt(payment: Any, *, context: Any = None, entry: Any = None) -> Receipt:
    """ONE payment → ONE `Receipt`. **It never refuses over an imbalance.**

    `context` is `seams/payments.PageContext` — the payer names and the tender
    clearing codes, read ONCE for a page of up to 1,000 rather than per row.
    `entry` is the payment's posted journal entry; passing it in is what lets a
    page read the entries in one query instead of one per receipt.
    """
    from apps.integrations.seams import ledger as ledger_seam
    from apps.integrations.seams import payments as payments_seam

    mappings = _config()

    if context is None:
        context = payments_seam.page_context([payment])
    if entry is None:
        entry = journal_entry_for(payment)

    tenant_id = current_tenant_id()
    payment_type, other_type, unmapped_tender = _payment_type_for(payment, tenant_id)

    distributions = tuple(
        Distribution(
            # ⚠ **THE GL CODE IS THE LEDGER SEAM'S, NOT A LOOKUP OF OUR OWN.**
            # `account_code` is what `/partner/v1/ledger` resolves Aclarian's
            # rows through. One place, so a GL rule changes once; the moment
            # this file read `ledger_accounts` itself there would be two
            # answers and the difference would present as a City being short.
            account=ledger_seam.account_code(line),
            amount=getattr(line, "amount", ZERO),
            type=DISTRIBUTION_CREDIT,
        )
        for line in _credit_legs(entry)
    )

    purpose = str(getattr(payment, "purpose", "") or "")
    our_number = str(getattr(payment, "payment_no", "") or "")
    memo = str(getattr(payment, "memo", "") or "")
    account = getattr(payment, "account", None)

    transaction = Transaction(
        type=mappings.newworld_transaction_type(purpose),
        amount=getattr(payment, "amount", ZERO),
        # Our receipt number travels here because theirs is 13 and ours is 15
        # — see `RECEIPT_NUMBER_BLANK`. The clerk's own memo follows it.
        description=" · ".join(one for one in (our_number, memo) if one),
        ar_customer_number=str(getattr(account, "account_no", "") or ""),
        ar_bill_type=mappings.newworld_bill_type(purpose),
        ar_bill_number=_bill_number(payment),
        distributions=distributions,
    )

    method = getattr(payment, "method", None)
    method_code = str(getattr(method, "code", "") or "").lower()
    node = PaymentNode(
        type=payment_type,
        amount=getattr(payment, "amount", ZERO),
        # Their rule: a check number only when the type is Check. Ours is
        # `payments.confirmation`, one of the exactly three columns the PO
        # opened to correction on 2026-09-02 (hard rule 4, `payments/0014`).
        check_number=(
            str(getattr(payment, "confirmation", "") or "")
            if payment_type == mappings.NEWWORLD_PAYMENT_CHECK
            else ""
        ),
        other_type=other_type,
    )

    posted = getattr(payment, "posted_at", None)
    posted_day = posted.date() if posted is not None else None
    return Receipt(
        number=RECEIPT_NUMBER_BLANK,
        # Always false — a correction is a new payment row (hard rule 4) and
        # their platform forbids altering a voided receipt, so the two rules
        # agree and there is ONE mechanism. See the module docstring.
        voided=False,
        entered_date=posted_day,
        recorded_date=posted_day,
        # ⚠ **THE BOOK DATE, NOT THE POSTING DATE.** `journal_entries.
        # entry_date` is the date the books took it, which is what a GL date
        # means; a payment entered in September into an August period posts
        # into August and their GL must agree with ours about which month it
        # is in. Falls back to the posting day when there is no entry.
        gl_date=getattr(entry, "entry_date", None) or posted_day,
        received_from=context.names.get(str(getattr(payment, "account_id", ""))) or "",
        description=" · ".join(one for one in (our_number, memo) if one),
        cashier=RECEIPT_CASHIER,
        transactions=(transaction,),
        payments=(node,),
        our_number=our_number,
        unmapped_tender=unmapped_tender,
    )


#: Their ceiling on `ReceiptPaymentLevel` nodes. Asserted rather than trusted.
MAX_PAYMENT_NODES = 4


def emit(payments: list[Any]) -> Emission:
    """A page of payments → their XML, **and what is wrong with it.**

    ⚠ **NOTHING HERE CAN REFUSE OVER AN IMBALANCE**, by construction rather
    than by discipline: there is no branch in this function that inspects
    `Receipt.balanced` before writing, and `Emission` reports the count
    afterwards. PO 2026-09-22: *"please send receipt even if it is not
    balance"*.
    """
    rows = list(payments)
    receipts: list[Receipt] = []
    if rows:
        from apps.integrations.seams import payments as payments_seam

        context = payments_seam.page_context(rows)
        entries = _entries_for(rows)
        for one in rows:
            receipts.append(
                build_receipt(one, context=context, entry=entries.get(str(one.pk)))
            )

    return Emission(body=render(receipts), receipts=tuple(receipts))


def render(receipts: list[Receipt] | tuple[Receipt, ...]) -> bytes:
    """A list of receipts → their XML bytes. **The whole serialisation, in one
    place that a test can call without a database.**

    ⚠ **IT IS SPLIT OUT OF `emit` BECAUSE A TEST HELPER THAT REBUILDS THIS
    LOOP IS A SECOND THING THAT CAN DISAGREE — AND MINE DID.** The first draft
    of `tests/test_cr132_newworld_receipts.py` had its own `_bytes()` copy of
    these six lines, so every balance case was proved against the copy and
    **the path the endpoint actually calls had no test at all**. The red proof
    found it: a refusal inserted into `emit` — the exact rule the PO reversed —
    was reinstated and **all seventeen cases stayed green** (CLAUDE.md law 7,
    *structurally incapable of failing*).

    ⚠ **NOTHING HERE INSPECTS `Receipt.balanced`, BY CONSTRUCTION RATHER THAN
    BY DISCIPLINE.** There is no branch in this function that could withhold a
    receipt. PO 2026-09-22: *"please send receipt even if it is not balance"*.
    """
    root = ET.Element(ROOT_ELEMENT)
    for receipt in receipts:
        if len(receipt.payments) > MAX_PAYMENT_NODES:  # pragma: no cover - defensive
            raise ValueError(
                f"receipt {receipt.our_number} carries {len(receipt.payments)} payment nodes "
                f"and New World allows {MAX_PAYMENT_NODES}. Refused at composition rather "
                "than sent: their importer would reject the whole file with a reason we "
                "could not reproduce from our side. ⚠ This is NOT the balance rule — an "
                "unbalanced receipt is always sent; this is a file their importer cannot "
                "parse at all."
            )
        receipt.as_element(root)
    ET.indent(root, space="  ")
    body = ET.tostring(root, encoding="unicode")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n' + body + "\n").encode("utf-8")


# ── the check every file passes before it leaves ────────────────────────────


#: `9,2` — up to seven digits before the point and exactly two after.
_AMOUNT = re.compile(r"^-?\d{1,7}\.\d{2}$")
_DATE = re.compile(r"^\d{2}/\d{2}/\d{4}$")

#: Which child elements each level may hold.
_CHILDREN = {
    ROOT_ELEMENT: (HEADER_ELEMENT,),
    HEADER_ELEMENT: (TRANSACTION_ELEMENT, PAYMENT_ELEMENT),
    TRANSACTION_ELEMENT: (DISTRIBUTION_ELEMENT,),
    DISTRIBUTION_ELEMENT: (),
    PAYMENT_ELEMENT: (),
}

#: Each element's exact attribute set, card attributes aside (they are checked
#: on their own, because their rule is stricter: present AND empty).
_ATTRIBUTES = {
    ROOT_ELEMENT: (),
    HEADER_ELEMENT: HEADER_ATTRIBUTES,
    TRANSACTION_ELEMENT: TRANSACTION_ATTRIBUTES,
    DISTRIBUTION_ELEMENT: DISTRIBUTION_ATTRIBUTES,
    PAYMENT_ELEMENT: PAYMENT_ATTRIBUTES_BEFORE_CARD + PAYMENT_ATTRIBUTES_AFTER_CARD,
}


class ReceiptFileInvalid(ValueError):
    """A rendered document that failed `validate`. Carries the problems so the
    run row and the alert can say what was wrong."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems[:5]))
        self.problems = list(problems)


def validate(body: bytes) -> list[str]:
    """Every way `body` departs from New World's confirmed template, or `[]`.

    ⚠ **THE TEMPLATE IS THE ONE THE PO PASTED ON 2026-10-21, ENCODED ABOVE —
    NOT AN XSD.** PO: *"this was only as exmaple; not required"*, so nothing is
    committed or validated against a schema file and no dependency is added;
    this is stdlib ElementTree. It is called before a file is written to the
    City's SFTP folder (`receipt_push.send`) and before the partner API answers
    (`partner_api.partner_receipts`). **A file with a problem is never sent and
    never served.** It checks:

      * the root is `<ROOT>`, and each level holds only its own children:
        header ▸ transactions (at least one) then payment nodes (at most
        `MAX_PAYMENT_NODES`), transaction ▸ distributions, nothing below;
      * no element carries text — every field is an attribute;
      * each element carries EXACTLY its template attribute set, every one
        present (`""` when empty), nothing extra;
      * `VoidedFlag` is `0` or `1`;
      * the three dates are MM/DD/YYYY and real dates, or empty;
      * the three amounts are present and `9,2`;
      * the four card attributes are present and empty.

    ⚠ **AN EMPTY DAY IS `<ROOT />` AND PASSES.** PO 2026-10-07 Q3: *"send an
    empty file and alert"*. Their example schema draws the header as 1..n; the
    PO's ruling on empty days stands until they say otherwise.
    """
    problems: list[str] = []
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        return [f"not well-formed XML: {exc}"]
    if root.tag != ROOT_ELEMENT:
        return [f"the root is <{root.tag}>, not <{ROOT_ELEMENT}>"]
    _check(root, ROOT_ELEMENT, problems)
    return problems


def _check(node: Any, where: str, problems: list[str]) -> None:
    """One element and, recursively, everything under it."""
    tag = node.tag
    if (node.text or "").strip():
        problems.append(f"{where}: carries text; every field is an attribute")
    expected = _ATTRIBUTES[tag]
    for name in expected:
        if name not in node.attrib:
            problems.append(f"{where}: attribute {name} is missing")
    for name in node.attrib:
        if name not in expected and name not in CARD_ATTRIBUTES:
            problems.append(f"{where}: attribute {name} is not in the template")
    if tag == PAYMENT_ELEMENT:
        for name in CARD_ATTRIBUTES:
            if name not in node.attrib:
                problems.append(f"{where}: attribute {name} is missing")
            elif node.attrib[name] != "":
                problems.append(f"{where}: attribute {name} must be empty")
    elif any(name in CARD_ATTRIBUTES for name in node.attrib):
        problems.append(f"{where}: a card attribute outside {PAYMENT_ELEMENT}")
    if tag == HEADER_ELEMENT:
        flag = node.attrib.get("VoidedFlag")
        if flag is not None and flag not in ("0", "1"):
            problems.append(f"{where}: VoidedFlag is {flag!r}, not 0 or 1")
        for name in DATE_ATTRIBUTES:
            value = node.attrib.get(name, "")
            if value and not _is_day(value):
                problems.append(f"{where}: {name} is {value!r}, not a real MM/DD/YYYY date")
    for name in AMOUNT_ATTRIBUTES:
        if name in expected and name in node.attrib:
            value = node.attrib[name]
            if not _AMOUNT.match(value):
                problems.append(f"{where}: {name} is {value!r}, not a 9,2 amount")

    allowed = _CHILDREN[tag]
    counts: dict[str, int] = {}
    seen_payment = False
    for child in node:
        if (child.tail or "").strip():
            problems.append(f"{where}: carries text between elements")
        if child.tag not in allowed:
            problems.append(f"{where}: <{child.tag}> is not allowed here")
            if (child.text or "").strip():
                # The shape this file had until 2026-10-21: a field as an element.
                problems.append(f"{where}/{child.tag}: carries text; every field is an attribute")
            continue
        counts[child.tag] = counts.get(child.tag, 0) + 1
        if child.tag == PAYMENT_ELEMENT:
            seen_payment = True
        elif tag == HEADER_ELEMENT and seen_payment:
            problems.append(f"{where}: a transaction after a payment node")
        _check(child, f"{where}/{child.tag}[{counts[child.tag]}]", problems)
    if tag == HEADER_ELEMENT:
        if not counts.get(TRANSACTION_ELEMENT):
            problems.append(f"{where}: no {TRANSACTION_ELEMENT}")
        if counts.get(PAYMENT_ELEMENT, 0) > MAX_PAYMENT_NODES:
            problems.append(f"{where}: more than {MAX_PAYMENT_NODES} payment nodes")


def _is_day(value: str) -> bool:
    """MM/DD/YYYY and a date that exists — `02/30/2026` is refused."""
    if not _DATE.match(value):
        return False
    try:
        datetime.strptime(value, "%m/%d/%Y")
    except ValueError:
        return False
    return True


def checked(body: bytes) -> bytes:
    """`body`, or `ReceiptFileInvalid` naming every problem. The one call both
    exits make, so the SFTP file and the API answer are held to one check."""
    problems = validate(body)
    if problems:
        raise ReceiptFileInvalid(problems)
    return body


def _entries_for(payments: list[Any]) -> dict[str, Any]:
    """Every payment's posted journal entry, in ONE query for the page.

    ⚠ **ASKED ONCE FOR THE PAGE, NEVER PER ROW.** The PO set a partner page at
    1,000 (*"make this as 1000 per page"*), so a per-receipt entry lookup is a
    thousand round trips plus a thousand more for their lines.
    """
    try:
        from apps.ledger import models as ledger_models
    except ImportError:  # pragma: no cover - a deployment with no ledger
        # `ImportError` and not `Exception` — see `journal_entry_for`.
        return {}
    tenant_id = current_tenant_id()
    if tenant_id is None:
        return {}
    found: dict[str, Any] = {}
    rows = ledger_models.JournalEntry.objects.filter(
        tenant_id=tenant_id,
        source_type="payment",
        source_id__in=[one.pk for one in payments],
        status=ledger_models.JE_POSTED,
    ).prefetch_related("lines__ledger_account")
    for entry in rows:
        found.setdefault(str(entry.source_id), entry)
    return found


# ── the measurement the PO asked for, which decides nothing ─────────────────


def measure_residues(payments: list[Any]) -> dict[str, Any]:
    """**How often an imbalance is a one-cent rounding residue rather than a
    real error.** It changes nothing and it is not called by the endpoint.

    ⚠ **THIS EXISTS BECAUSE THE TWO CASES HAVE THE SAME SYMPTOM AND OPPOSITE
    FIXES.** We store money to four decimals and their field is `9,2`, so a
    transaction of `100.0000` credited across three legs emits `33.33 × 3 =
    99.99` — one cent short, and nothing is wrong. A mis-mapped GL account, a
    missing journal entry or a payment whose credits do not foot is short by a
    real amount, and no rounding rule would fix it.

    A systematic residue has a standard answer — assign the remainder to the
    LARGEST distribution, which places a real cent rather than inventing one —
    and it is **deliberately not implemented here**. Today's ruling is *send
    it*. This counts, so the choice can be put to the PO with a figure.

    `residue` counts receipts whose shortfall is smaller than the number of
    distributions it is spread over, in cents — the arithmetic bound on what
    rounding alone can cost. Anything larger is `material` and is a real
    question about a real payment.
    """
    counts = {"receipts": 0, "balanced": 0, "residue": 0, "material": 0}
    residue_total = ZERO
    material_total = ZERO
    worst = ZERO
    examples: list[dict[str, str]] = []
    for receipt in emit(payments).receipts:
        counts["receipts"] += 1
        if receipt.balanced:
            counts["balanced"] += 1
            continue
        legs = sum(len(one.distributions) for one in receipt.transactions)
        bound = Decimal(max(legs, 1)) * Decimal("0.01")
        gap = abs(receipt.difference)
        if gap > abs(worst):
            worst = receipt.difference
        if gap <= bound:
            counts["residue"] += 1
            residue_total += receipt.difference
        else:
            counts["material"] += 1
            material_total += receipt.difference
            if len(examples) < 5:
                examples.append(
                    {"receipt": receipt.our_number, "difference": str(receipt.difference)}
                )
    return {
        **counts,
        "residue_total": str(residue_total),
        "material_total": str(material_total),
        "largest_difference": str(worst),
        "material_examples": examples,
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-132-BRC07 · 12-governance/02-decision-log.md 2026-09-22 "NEW WORLD / LOGOS" · New World/Logos import specification v2023.1.11
# generated: 2026-09-22 by the CR-132-BRC07 New World lane
# checklist: A✔ B=n/a(no screen) C✔ D✔ E=n/a F✔ G✔ H=HUMAN-REVIEW-PENDING (🔒 money path — row in 12-governance/09-human-review-ledger.md)
# gates: pytest tests/test_cr132_newworld_receipts.py · 10-scripts/gates/g130_no_card_fields.py
# exceptions: (2026-10-21, DEF-INT-10304) every field is an attribute on a <ROOT> document, all template attributes always present, checked by validate() before the SFTP outbox or the API answer · card DATA is NOT BUILT — the four ReceiptPaymentCreditCard* attributes are written present and always "" (PO 2026-10-21 option A) and G130 fails any code that could give one a value · an unbalanced receipt is EMITTED, flagged and counted, never refused and never plugged (PO 2026-09-22, "please send receipt even if it is not balance") · a distribution with no resolvable GL account goes out EMPTY and flagged, never zero-filled — the same ruling one field over · DueToDueFromFund and the distribution-level ProjectCode1/2/3 are written EMPTY by PO ruling, never omitted and never zero (the transaction-level ProjectCode1/2/3 were removed 2026-10-21, DEF-INT-10304) · an unmapped tender goes as Other under OUR OWN word for it and is counted, never mapped onto one of their four named types
# status: HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────
