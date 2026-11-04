# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-021 (S38 step 1 — "Upload statement": the bank file becomes
#           `bank_lines`, and the same file cannot be imported twice)
#           Screens: S38
# Rules:    BR-PAY-019 (bank reconciliation: statement import, then auto-match) ·
#           BR-PAY-028 🔒 (idempotency — the import batch keys on file+tags; key
#           mechanics Eng-Lead) · BR-PAY-023 (the staged-import pattern this
#           follows: file + SHA-256 stamp, per-row validation, never a silent
#           guess) · CLAUDE.md rule 2 (money is Decimal, never float) · rule 6
#           (idempotency)
# Tests:    06-backend/tests/test_us_pay_020_023_bank_rec.py
# Impacts:  apps/payments/reconciliation.import_bank_statement (its only caller)
#           · apps/payments/bankrec_models.BankStatementImport (file_hash +
#           tag_fingerprint live there) · apps/metering/read_import.py (the same
#           file+tags shape, deliberately mirrored — see below)
# ───────────────────────────────────────────────────────
"""Bank-file kernel: parse a statement into lines, stamp it, key it. Pure.

HUMAN-OWNED — idempotency keys are a CLAUDE.md 🔒 sensitive path.
HUMAN-REVIEW-PENDING — AI-authored 2026-08-11 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Row in
12-governance/09-human-review-ledger.md.

⚠ CORRECTED 2026-09-01 (DEF-2791) — THE PARAGRAPH BELOW IS HISTORY, NOT THE
CURRENT STATE. A glob DOES match this file: `human_owned.txt` carries
`06-backend/apps/payments/lockbox.py` ("Bank-file kernel — the hard-rule-6
file+tags idempotency key for imported money"), granted by the PO ruling of
2026-08-11 — verbatim *"Pls start 2 and 1 and then 3"*, answering a ranked list
whose item 2 was *"five money paths are unguarded"*, this file among the five.
**So G7 DOES read the two markers above.** The ask below was answered nearly
three weeks ago; it is kept because why a money path went unguarded is worth
knowing, and nothing below it describes today.

⚠ **THIS FILE MATCHES NO GLOB IN `10-scripts/gates/human_owned.txt`**, so G7 does
not read the HUMAN-OWNED / HUMAN-REVIEW-PENDING markers above — it reports
"conform" over a money path it is not looking at. Editing that guard list is a
process event (its own header says so), so the line is **REPORTED for the daily
PO batch rather than self-granted**, which is the posture `posting_seam.py` and
`delivery_seam.py` each took from this same position. Saying it here is the
point: a marker no gate reads is hard-won law 1, and the file that carries it is
the honest place to say so.

⚠ **THIS FILE'S PREVIOUS DOCSTRING IS FALSIFIED AND REPLACED, not annotated**
(hard-won law 1). It read, in full: *"Lockbox file parsers (BAI2, bank CSV) with
auto-match preview (S35 modal)."* Two of those claims were wrong and the third
was somebody else's story:

  * there was no parser of any kind — the file was one line;
  * **S35's lockbox modal is the PAYMENT REMITTANCE import (US-PAY-003,
    BR-PAY-023)**, which STAGES `payment_import_batches` / `payment_import_rows`
    and creates payments. That is a different direction of money and a different
    lane; neither table exists and nothing here creates a payment;
  * "auto-match preview" belongs to that story too — matching a remittance line
    to an ACCOUNT (by account #, invoice # or a flagged name+amount heuristic).

What this module actually is: the **bank-file half** — the S38 statement upload
(US-PAY-021). It turns the bytes a bank hands you into normalised lines, stamps
the file, and composes the tag half of the file+tags idempotency key. Both
families are bank files and both will live here; the remittance family arrives
with US-PAY-003 and is named so silence is not read as "done".

════════════════════════════════════════════════════════════════════════════
PURE. NOTHING HERE TOUCHES THE DATABASE, THE CLOCK OR A TENANT
════════════════════════════════════════════════════════════════════════════
Every function below is a function of its arguments. That is what lets
`reconciliation.py` compute a file's identity BEFORE opening a transaction, and
what lets a test drive twenty malformed files through the parser without a
database at all.

════════════════════════════════════════════════════════════════════════════
🔒 FILE+TAGS IDEMPOTENCY (BR-PAY-028 · OQ-044's closure model · DB-12)
════════════════════════════════════════════════════════════════════════════
The POLICY is signed and is not reinterpreted here: the key is **file + tags**,
and a collision BLOCKS the import naming who did it first, when, and linking to
it (US-PAY-021 TC-5; OQ-044's closure, option b, for the read-import family it
was ruled on). Only the MECHANICS are authored, under BR-PAY-028's own
delegation (*"key mechanics Eng-Lead 🔒"*).

The shape is **deliberately the one `apps/metering/read_import.py` already
uses**, because two idempotency shapes in one product is how one of them stops
being checked:

    file half  SHA-256 of the exact bytes uploaded — one changed row is a
               different file, so a corrected statement imports normally.
    tag half   SHA-256 of the canonical JSON of the step-1 tags, in a FIXED
               field order with explicit nulls, so key equality means tag
               equality and dict ordering cannot change a key.

**The tags are the bank account and the statement period** — S38 step 1's own
two fields (*"Bank account: Chase Operating ••4021"*, *"Statement period"*).
That choice is the one judgment call in this file and it cuts both ways, so it
is stated rather than buried: the same file uploaded against a DIFFERENT bank
account is a different key and imports, which is correct when a bookkeeper picks
the wrong account first and repeats the upload — and is also the one hole a
determined re-import could walk through. The structural half closes it as far as
a key can: `uq_bank_statement_imports_idempotency` is UNIQUE (tenant, file_hash,
tag_fingerprint), so a race cannot double-import either.

Worked, so the figure is concrete rather than a description. J14's Chase
statement for 1–6 Aug against bank account
`018f6f6a-0000-7000-8000-00000000b0a1` produces the tag document

    {"bank_account_id": "018f6f6a-0000-7000-8000-00000000b0a1",
     "period_end": "2026-08-06", "period_start": "2026-08-01"}

hashed to a stable hex digest, and the same upload a second time finds the same
(file_hash, tag_fingerprint) pair and is refused with the first import's id.

════════════════════════════════════════════════════════════════════════════
THE CSV DIALECT, AND WHY NOTHING IS GUESSED
════════════════════════════════════════════════════════════════════════════
S38 step 1 accepts **CSV · OFX · QBO · QFX** (prototype). This kernel ships the
CSV reader and REFUSES the other three by name rather than half-reading them:
OFX/QFX are SGML/XML dialects with per-bank variance, and a parser that
"mostly" reads a money file is worse than one that says it cannot. The refusal
names the format so the S38 upload can say what to export instead.

Within CSV, the header row is matched case-insensitively against a small set of
aliases per column, because banks disagree about capitalisation and spacing and
nothing here is allowed to positionally guess which column holds the money. A
file whose header cannot be resolved is REFUSED naming the columns it needs —
BR-PAY-023's *"never auto-guess silently"*, applied to a bank file.

**Money is `Decimal`, from the text, always.** No float touches a statement
amount: the binary double nearest 4972.90 is 4972.8999999999996, and a reconciliation that
compares that against a `Decimal` batch total finds a difference of
0.0000000000004 and reports it to a human as an exception to explain.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

#: The formats S38 step 1 offers. CSV is read; the other three are refused BY
#: NAME (see the module docstring) so a clerk is told what to export instead.
FORMAT_CSV = "csv"
UNSUPPORTED_FORMATS = ("ofx", "qbo", "qfx")

#: The three facts a statement line must carry to be reconcilable at all: when
#: the bank posted it, what it says, and how much. Each maps to a `bank_lines`
#: column (B2 §2: posted_on · reference · amount).
COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "posted_on": ("posted_on", "posting date", "post date", "date", "transaction date"),
    "reference": ("reference", "description", "memo", "details", "narrative"),
    "amount": ("amount", "credit", "deposit", "value"),
}

#: The tag fields of the 🔒 file+tags key, in a FIXED order with explicit nulls.
IDEMPOTENCY_TAG_FIELDS: tuple[str, ...] = ("bank_account_id", "period_start", "period_end")

#: **THE REMITTANCE HALF'S COLUMNS (CR-059 CS-2 · US-PAY-003 · BR-PAY-023).**
#:
#: A lockbox file is not a statement, and the difference is what it is FOR: a
#: statement says what the BANK did, a remittance says WHO PAID and against what.
#: So the columns are the ones a matcher needs — the three the epic names, in its
#: priority order (account # → invoice # → name+amount) — plus the money and the
#: dates BR-PAY-021 keeps apart.
#:
#: ⚠ **ONLY `amount` IS REQUIRED, and that is the judgement worth stating.** A
#: row with no amount is not a payment and there is nothing to stage. A row with
#: no account reference is the ORDINARY case this whole feature exists to work
#: through, and refusing it at parse time would delete the review queue the story
#: is about. Everything else is the MATCHER's to judge, on a row that exists.
REMITTANCE_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "account_ref": (
        "account_ref",
        "account ref",
        "account",
        "account no",
        "account number",
        "account #",
        "acct",
        "acct no",
        "customer account",
        "customer number",
    ),
    "invoice_ref": (
        "invoice_ref",
        "invoice ref",
        "invoice",
        "invoice no",
        "invoice number",
        "invoice #",
        "bill",
        "bill no",
        "bill number",
    ),
    "payer_name": (
        "payer_name",
        "payer name",
        "payer",
        "name",
        "customer",
        "customer name",
        "remitter",
    ),
    "amount": ("amount", "amount paid", "paid", "payment", "value", "remittance"),
    "paid_on": (
        "paid_on",
        "paid on",
        "date",
        "payment date",
        "received",
        "received date",
        "check date",
        "cheque date",
        "deposit date",
    ),
    "reference": (
        "reference",
        "ref",
        "check no",
        "check number",
        "check #",
        "cheque no",
        "cheque number",
        "confirmation",
        "document",
    ),
}

#: The remittance file's TAG half. Deliberately the same shape and the same
#: fixed-order-with-explicit-nulls discipline as the statement half above
#: (BR-PAY-028, *"key mechanics Eng-Lead 🔒"*), because two idempotency shapes in
#: one product is how one of them stops being checked.
#:
#: **The tags are the lockbox account and the day the file covers.** Same
#: judgement call as the statement half's, and it cuts the same way: the same
#: file lodged against a DIFFERENT bank account is a different key and imports,
#: which is right when a clerk picks the wrong lockbox first and repeats the
#: upload, and is also the one hole a determined re-import could walk through.
#: The structural half closes it as far as a key can — `payment_import_batches`
#: carries UNIQUE (tenant, file_hash, tag_fingerprint) over COMMITTED batches.
REMITTANCE_TAG_FIELDS: tuple[str, ...] = ("bank_account_id", "received_on")

#: ISO first, because that is what every bank export tool emits when asked, then
#: the two US shapes S38's own prototype figures use ("Aug 5" renders from a
#: date, it is never uploaded). A date this list cannot read is REFUSED, never
#: guessed at — 03/04/2026 is two different days in two countries.
DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%d-%b-%Y", "%Y/%m/%d")


class BankFileError(ValueError):
    """This file cannot become bank lines, and here is exactly why.

    A `ValueError` rather than `PaymentRuleError`: this module is pure and knows
    nothing about payments' rules or its transactions. `reconciliation.py`
    translates it at the boundary, the same way `ledger_seam` translates the
    ledger's refusals — DEF-047's lesson, applied before it bites.
    """


@dataclass(frozen=True)
class ParsedBankLine:
    """One statement line, normalised. `amount` is a `Decimal`, never a float."""

    line_no: int
    posted_on: date
    reference: str | None
    amount: Decimal


@dataclass(frozen=True)
class ParsedRemittanceLine:
    """One remittance row, normalised — **and a row that would not parse is
    still a row** (CR-059 CS-2).

    ⚠ **THIS IS THE ONE PLACE THE TWO HALVES OF THIS KERNEL DISAGREE, AND IT IS
    DELIBERATE.** `parse_bank_statement` refuses the WHOLE FILE on one bad row,
    and this module's own lifecycle block records why: *"a statement is not a
    list of independent rows: half of one reconciles to nothing."* A remittance
    file is the opposite — it IS a list of independent cheques, and BR-PAY-023
    says so in as many words: *"per-row errors skip with a report."* One
    unreadable date in a file of four hundred cheques must not stop the other
    three hundred and ninety-nine being banked.

    So the error travels ON the row instead of being raised. `error` is None for
    a row that parsed; when it is set, `amount` and `paid_on` may be None and the
    RAW text is kept exactly as the bank sent it, so a person can see what the
    file actually said rather than what we could make of it.
    """

    line_no: int
    account_ref: str | None
    invoice_ref: str | None
    payer_name: str | None
    amount: Decimal | None
    paid_on: date | None
    reference: str | None
    #: The cells exactly as they arrived, for the row a person has to work.
    raw: dict[str, str]
    #: Why this row could not be read, or None. Never a partial parse in silence.
    error: str | None = None


def file_sha256(payload: bytes) -> str:
    """The file half of the 🔒 key — computed SERVER-side, never accepted from
    a client. One changed row is a different file (US-MET-010 TC-6's shape)."""
    return hashlib.sha256(payload).hexdigest()


def statement_tag_fingerprint(tags: dict[str, Any]) -> str:
    """The TAG half of BR-PAY-028's file+tags key. Deterministic, order-independent.

    Explicit nulls: a tag that is absent and a tag that is None produce the SAME
    document, so "no period given" cannot silently be a different key from
    "period given as null" and let one upload past the other.
    """
    canonical = json.dumps(
        {name: _tag_value(tags.get(name)) for name in IDEMPOTENCY_TAG_FIELDS},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def remittance_tag_fingerprint(tags: dict[str, Any]) -> str:
    """The TAG half of the 🔒 file+tags key for a REMITTANCE file (BR-PAY-028).

    Same function as `statement_tag_fingerprint` over a different field list, and
    written out rather than parameterised so that neither family can be changed
    by accident while editing the other. The two must not share a key: the same
    bytes can legitimately be both a statement and a remittance to two different
    utilities, and a shared key would let one block the other's import.
    """
    canonical = json.dumps(
        {name: _tag_value(tags.get(name)) for name in REMITTANCE_TAG_FIELDS},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _tag_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def parse_bank_statement(payload: bytes, *, file_format: str = FORMAT_CSV) -> list[ParsedBankLine]:
    """Bytes → normalised statement lines. Pure; refuses rather than guesses.

    Refuses, and each refusal is a thing a money file may never be read past:

    * a format this kernel does not read (OFX/QBO/QFX) — named, so the S38
      upload can say what to export instead;
    * an empty file, or one with no header row;
    * a header whose date/amount columns cannot be resolved from the aliases —
      positional guessing is how a reference column becomes an amount;
    * a row whose date or amount cannot be parsed, naming the ROW NUMBER. One
      bad row refuses the file: a statement that half-imports leaves a
      reconciliation that ties to nothing and no way to tell which half is
      missing.
    """
    fmt = (file_format or "").strip().lower()
    if fmt in UNSUPPORTED_FORMATS:
        raise BankFileError(
            f"{fmt.upper()} statements are not read in this release — only CSV is. OFX, QBO and "
            "QFX are per-bank SGML/XML dialects, and a parser that MOSTLY reads a money file is "
            "worse than one that says it cannot (BR-PAY-023: never guess silently). Export the "
            "same statement period as CSV."
        )
    if fmt != FORMAT_CSV:
        raise BankFileError(
            f"{file_format!r} is not a bank-statement format this kernel reads. S38 step 1 offers "
            f"CSV, OFX, QBO and QFX; CSV is the one implemented (the others are refused by name)."
        )
    if not payload or not payload.strip():
        raise BankFileError("the uploaded statement is empty — there is nothing to reconcile.")

    text = payload.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:  # pragma: no cover - `payload.strip()` already caught it
        raise BankFileError("the uploaded statement has no header row.") from None

    index = _resolve_columns(header)
    lines: list[ParsedBankLine] = []
    for row_no, row in enumerate(reader, start=2):  # row 1 is the header
        if not any(cell.strip() for cell in row):
            continue  # a blank line between sections is not an error
        lines.append(
            ParsedBankLine(
                line_no=len(lines) + 1,
                posted_on=_parse_date(_cell(row, index["posted_on"]), row_no),
                reference=_cell(row, index.get("reference")) or None,
                amount=_parse_amount(_cell(row, index["amount"]), row_no),
            )
        )
    if not lines:
        raise BankFileError(
            "the uploaded statement has a header and no rows — an import that wrote nothing would "
            "still consume this file's idempotency key and block the real one (BR-PAY-028)."
        )
    return lines


def parse_remittance_file(
    payload: bytes, *, file_format: str = FORMAT_CSV
) -> list[ParsedRemittanceLine]:
    """Bytes → remittance rows. **File-level problems refuse; ROW-level ones do not.**

    CR-059 CS-2 · US-PAY-003 · BR-PAY-023, whose text is the contract this
    implements: *"batch → per-row validation → preview → commit … per-row errors
    skip with a report."*

    ════════════════════════════════════════════════════════════════════════
    WHY THE ERROR POSTURE IS THE OPPOSITE OF `parse_bank_statement`'S
    ════════════════════════════════════════════════════════════════════════
    The statement half refuses the whole file on one bad row, because a
    half-imported statement reconciles to nothing and there is no way to tell
    which half is missing. **A remittance file is a stack of independent
    cheques.** A utility on a lockbox gets one a day carrying hundreds of them,
    and today every one is typed by hand. If a single unreadable date threw the
    file out, the feature would be no better than the typing: the clerk would
    still have to key three hundred and ninety-nine good cheques by hand because
    the four hundredth had a smudged date.

    So a bad row becomes a row carrying its own reason, and the staged import
    puts it in front of a person. **Nothing is guessed on the way past** — an
    amount that will not parse stays None and the raw text is kept.

    What still refuses the FILE, because none of it is about one row:

    * a format this kernel does not read — OFX/QBO/QFX, named, so the S35 upload
      can say what to export instead;
    * an empty file, or one with no header row;
    * **a header with no amount column.** Every other column is optional and the
      matcher judges it; a file with no money in it is not a remittance file, and
      a positional guess at which column holds the money is exactly what
      BR-PAY-023 forbids;
    * a file whose only rows are blank.
    """
    fmt = (file_format or "").strip().lower()
    if fmt in UNSUPPORTED_FORMATS:
        raise BankFileError(
            # The rule is BR-PAY-023 ("never auto-guess silently") and it stays
            # in this comment: an id in the words a person reads is provenance,
            # not help (B14 rule 32, CR-016).
            f"{fmt.upper()} remittance files are not read in this release — only CSV is. OFX, QBO "
            "and QFX are per-bank SGML/XML dialects, and a parser that MOSTLY reads a money file "
            "is worse than one that says it cannot. Ask the bank for the same lockbox file as CSV."
        )
    if fmt != FORMAT_CSV:
        raise BankFileError(
            f"{file_format!r} is not a remittance format this kernel reads. CSV is the one "
            "implemented; the others are refused by name rather than half-read."
        )
    if not payload or not payload.strip():
        raise BankFileError("the uploaded remittance file is empty — there is nothing to import.")

    text = payload.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:  # pragma: no cover - `payload.strip()` already caught it
        raise BankFileError("the uploaded remittance file has no header row.") from None

    index = _resolve_remittance_columns(header)
    lines: list[ParsedRemittanceLine] = []
    for row_no, row in enumerate(reader, start=2):  # row 1 is the header
        if not any(cell.strip() for cell in row):
            continue  # a blank line between sections is not an error
        lines.append(_remittance_line(row, index, line_no=len(lines) + 1, row_no=row_no))
    if not lines:
        raise BankFileError(
            # BR-PAY-028's file+tags key is what would be consumed; the id is
            # here rather than in the sentence.
            "the uploaded remittance file has a header and no rows — an import that wrote "
            "nothing would still consume this file's identity and block the real one."
        )
    return lines


def _remittance_line(
    row: list[str], index: dict[str, int], *, line_no: int, row_no: int
) -> ParsedRemittanceLine:
    """One row, with its failure ATTACHED rather than raised.

    Both parse failures are collected before returning, so a row with an
    unreadable date AND an unreadable amount says both. A row that reports one
    problem, is corrected, and then reports a second is two trips to the bank for
    a person who could have had one.
    """
    raw = {name: _cell(row, index.get(name)) for name in REMITTANCE_COLUMN_ALIASES}
    problems: list[str] = []

    amount: Decimal | None = None
    if raw["amount"]:
        try:
            amount = _parse_amount(raw["amount"], row_no)
        except BankFileError as refusal:
            problems.append(str(refusal))
    else:
        problems.append(
            f"row {row_no}: the amount cell is empty, so there is no payment to record."
        )

    paid_on: date | None = None
    if raw["paid_on"]:
        try:
            paid_on = _parse_date(raw["paid_on"], row_no)
        except BankFileError as refusal:
            problems.append(str(refusal))
    # ⚠ A ROW WITH NO DATE AT ALL IS NOT AN ERROR — PO ruling 2026-08-12,
    # verbatim: *"a receipt with no arrival date falls back to its recorded
    # date"*, worked there as *"entered 20 Aug against a bill due 22 Aug → no
    # fee; entered 25 Aug → still overdue, so the fallback forgives nothing"*.
    # The fallback is the SERVICE's to apply, at the moment it records the
    # payment, because only it knows the recording moment. The parser's job is to
    # say truthfully that the file carried none.

    return ParsedRemittanceLine(
        line_no=line_no,
        account_ref=raw["account_ref"] or None,
        invoice_ref=raw["invoice_ref"] or None,
        payer_name=raw["payer_name"] or None,
        amount=amount,
        paid_on=paid_on,
        reference=raw["reference"] or None,
        raw=raw,
        error=" ".join(problems) or None,
    )


def _resolve_remittance_columns(header: list[str]) -> dict[str, int]:
    """Header names → positions for the remittance family. Amount is the only must.

    Nothing is read positionally, for BR-PAY-023's reason: a file whose columns
    cannot be NAMED is refused rather than half-understood, and the failure mode
    being avoided is a reference column silently becoming an amount.
    """
    normalised = {cell.strip().lower(): position for position, cell in enumerate(header)}
    index: dict[str, int] = {}
    for column, aliases in REMITTANCE_COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in normalised:
                index[column] = normalised[alias]
                break
    if "amount" not in index:
        raise BankFileError(
            "the remittance header names no amount column (read: "
            f"{', '.join(cell.strip() for cell in header) or '<empty>'}). Accepted names are "
            f"{', '.join(REMITTANCE_COLUMN_ALIASES['amount'])}. Every other column is optional "
            "and is judged per row; the money is not, and it is never read positionally."
        )
    return index


def _resolve_columns(header: list[str]) -> dict[str, int]:
    """Header names → column positions, by alias, case- and space-insensitively."""
    normalised = {cell.strip().lower(): position for position, cell in enumerate(header)}
    index: dict[str, int] = {}
    for column, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in normalised:
                index[column] = normalised[alias]
                break
    missing = [column for column in ("posted_on", "amount") if column not in index]
    if missing:
        raise BankFileError(
            f"the statement header names no {' and no '.join(missing)} column "
            f"(read: {', '.join(cell.strip() for cell in header) or '<empty>'}). Accepted names "
            f"are {COLUMN_ALIASES}. Nothing is read positionally: a file whose columns cannot be "
            "named is refused rather than half-understood (BR-PAY-023)."
        )
    return index


def _cell(row: list[str], position: int | None) -> str:
    if position is None or position >= len(row):
        return ""
    return row[position].strip()


def _parse_date(text: str, row_no: int) -> date:
    for shape in DATE_FORMATS:
        try:
            return datetime.strptime(text, shape).date()
        except ValueError:
            continue
    raise BankFileError(
        f"row {row_no}: {text!r} is not a date this kernel reads ({', '.join(DATE_FORMATS)}). "
        "It is refused rather than guessed — 03/04/2026 is 3 April in one country and 4 March in "
        "another, and the wrong one silently moves a line outside the match tolerance."
    )


def _parse_amount(text: str, row_no: int) -> Decimal:
    """Money from text, as a `Decimal` (hard rule 2). Never `float`.

    Tolerates the presentation a bank export leaves in: thousands separators,
    a currency symbol, and parentheses for a negative (a debit on the
    statement). Everything else refuses.
    """
    cleaned = text.replace(",", "").replace("$", "").strip()
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    if negative:
        cleaned = cleaned[1:-1].strip()
    if not cleaned:
        raise BankFileError(f"row {row_no}: the amount cell is empty.")
    try:
        amount = Decimal(cleaned)
    except InvalidOperation:
        raise BankFileError(
            f"row {row_no}: {text!r} is not an amount. Money is read as a Decimal from the text "
            "of the file and never through a float (CLAUDE.md rule 2) — the binary double "
            "nearest 4972.90 is "
            "4972.8999999999996, and a reconciliation comparing that to a batch total reports a "
            "difference of four ten-billionths of a cent to a human to explain."
        ) from None
    return -amount if negative else amount


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-021@b6e4c19 (the five EP-PAY-06 sources — 04-docs/02-decisions/02-database-design-brief.md §2 + Addenda r12 #10 + DB-12 · 04-docs/05-modules/08-payments/06-epics/EP-PAY-06-deposits-bank-rec.md US-PAY-021 · 08-payments/02-business-rules.md BR-PAY-019/023/028 · 08-payments/03-field-map.md §6 · 08-payments/07-pre-session-model.md §7 PE-11)
# generated: 2026-08-11 by Eng-Lead (W5 deposit-batch + bank-reconciliation lane)
# checklist: A✔ B✔ C✔ D=deferred(no API call — a pure kernel behind reconciliation.py) E=deferred(no UI; S38 is unbuilt and REPORTED) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_us_pay_020_023_bank_rec.py · PROVED RED: with the re-import guard removed, the same statement file imports twice and every bank line exists twice — quoted verbatim in 12-governance/09-human-review-ledger.md before the guard was trusted green (hard-won law 7)
# exceptions: (1) THE PREVIOUS DOCSTRING WAS FALSIFIED AND REPLACED (hard-won law
#         1): it claimed BAI2 + bank-CSV parsers and an S35 auto-match preview,
#         and the file was one line. S35's lockbox modal is the PAYMENT
#         REMITTANCE import (US-PAY-003, BR-PAY-023) — a different direction of
#         money, a different lane, and its two staging tables do not exist. This
#         module is the BANK-STATEMENT half (US-PAY-021)
#         (2) CSV only. OFX/QBO/QFX are refused BY NAME rather than
#         half-implemented — per-bank SGML/XML variance, and a money file read
#         "mostly" is worse than one refused
#         (3) the 🔒 file+tags key deliberately MIRRORS
#         apps/metering/read_import.py's shape (OQ-044's ruled model). The TAG
#         CHOICE — bank account + statement period — is this lane's, under
#         BR-PAY-028's "key mechanics Eng-Lead 🔒", and its one hole (the same
#         file under a different bank account imports) is named in the docstring
#         rather than hidden
#         (4) one bad row refuses the WHOLE file, which is stricter than the
#         payment-import pattern's skip-with-report (BR-PAY-023). A statement is
#         not a list of independent rows: half of one reconciles to nothing
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
