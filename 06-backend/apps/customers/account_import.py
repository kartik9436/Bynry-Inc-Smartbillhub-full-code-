# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-019 (EP-CUS-07 — the PUBLISHED account template, the header
#           auto-detector, the row parser and the 🔒 file+tags idempotency key)
#           Screens: S17 (entry) · S68 (the wizard)
# Rules:    BR-CUS-046 (the template's column set — the PO's AC-1 enumeration,
#           verbatim) · BR-CUS-051 (import mechanics = the platform standard:
#           staged, per-row errors, skip-errors ON, "N created · N failed",
#           10,000-row cap) · BR-CUS-060 (there is NO bill-delivery-day column
#           — the preference is DROPPED, cycles decide bill dates) ·
#           BR-CUS-059 (autopay is an enrollment FLAG, capture-only) ·
#           BR-MET-032 (the platform import STANDARD this follows: one
#           published template, re-detected every upload, no mapping memory) ·
#           CLAUDE.md rule 2 (money is a decimal STRING here, never a float) ·
#           CLAUDE.md rule 6 / B2 DB-12 ("file+tags imports" idempotency)
# Tests:    06-backend/tests/test_us_cus_019_account_import.py
# Impacts:  apps/customers/services.py (stages what this parses) ·
#           apps/customers/api.py (the S68 template download + upload) ·
#           07-frontend/src/features/customers/ImportAccountsWizard.tsx
# ───────────────────────────────────────────────────────
"""Parsing half of the S68 account upload — the published template, the header
detector, the row parser and the 🔒 file+tags idempotency key.

HUMAN-OWNED (idempotency keys are a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-08-11 under the PO ruling of 2026-08-09 ("AI will do it; we
will review it later as human"). Row in
12-governance/09-human-review-ledger.md.

WHY THIS FILE LOOKS LIKE `apps/metering/read_import.py`
──────────────────────────────────────────────────────
Because it is meant to. BR-CUS-051 does not describe a new mechanism — it says
*"import mechanics = the standard"*, and names S52 assets and S28 reads as the
two places that standard already lives. Two import shapes in one product is two
things to be wrong, so the pieces are lifted rather than reinvented: the
`target → accepted aliases` table whose FIRST alias is the published header,
`template_csv()` writing exactly those headers so the file we hand out is the
file we parse best, the byte and row caps checked BEFORE anything is staged,
and parse errors that are kept VERBATIM beside the row rather than coerced into
something that fits.

**Validate then accept.** Nothing here makes a value fit. A date that will not
parse is an error carrying the original text; an unknown status code is an
error, never snapped to the nearest tenant status; a money column that is not a
number is an error, never zero. Every row that goes in comes out — accepted or
named — and no row is ever silently dropped.

WHAT THIS FILE DELIBERATELY DOES NOT DO
───────────────────────────────────────
· **It resolves nothing against the database.** Units, statuses, categories and
  customer refs are RESOLVED IN THE SERVICE, under the tenant's RLS context.
  This module is pure text→values, which is why it can be unit-tested without a
  tenant and why the same parse cannot accidentally read another tenant's rows.
· **It maps no legacy vocabulary.** BR-CUS-052's source→target value-mapping
  step is US-CUS-020 and is NOT built. Until it is, a legacy code that does not
  match one of the tenant's OWN reference-data rows is a ROW ERROR — which is
  exactly what BR-CUS-052 says happens to an unmapped value, so the behaviour
  is the rule's, not a placeholder for it.

🔒 THE IDEMPOTENCY KEY (CLAUDE.md rule 6, B2 DB-12)
───────────────────────────────────────────────────
DB-12 lists the product's four idempotency uniques and one of them is
**"file+tags imports"**. `apps/metering/models.ReadImportBatch` implements that
shape as UNIQUE (tenant, file_hash, tag_fingerprint) scoped to POSTED batches;
this module computes the same two halves for an account file:

    file_hash        SHA-256 of the uploaded bytes, computed SERVER-SIDE
    tag_fingerprint  SHA-256 over the batch-level TAGS

**What counts as a "tag" for an account import is a DERIVATION and is stated
here rather than assumed.** A read batch's tags are (period, cycle, route,
service, source) — the facts that decide what the file means. An account
cutover file has exactly one such batch-level fact in the story: the **cutover
as-of date** (US-CUS-021 §5, "Cutover as-of date · import wizard (batch
level)"). So the fingerprint is over the cutover date alone, and the same bytes
staged for the same cutover date can be COMMITTED once.

The residue is written down, not papered over: rows whose account # is BLANK
(US-CUS-019 TC-4 — 96 of them in the §4 fixture) carry no natural key of their
own, so a re-typed file with different bytes would re-create exactly those
rows. That is **OQ-165**, and the service refuses nothing on account of it —
it is a gap in the RULE, reported, not a gap in this code.
"""

import csv
import hashlib
import io
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

# US-CUS-019 §5 / BR-CUS-051: ≤10,000 rows, rejected AT UPLOAD. The byte cap
# mirrors the S28 reads importer — a 10 MB CSV is already far past 10,000
# account rows, so it bites only on a file that was never a template at all.
ROW_CAP = 10_000
BYTE_CAP = 10 * 1024 * 1024

# ── the PUBLISHED template (BR-CUS-046, the PO's AC-1 enumeration) ──────────
# target → accepted header aliases (lower-cased, trimmed). The FIRST alias of
# every target is the published header itself; `template_csv()` writes exactly
# those, so the file the wizard hands out is the file this parser reads best.
#
# The order is the AC-1 reading order: who the customer is, which account,
# which unit, what kind, what state, what money came with them, since when.
TEMPLATE_COLUMNS: dict[str, tuple[str, ...]] = {
    # BR-CUS-054 — the column that makes one customer own many accounts.
    "customer_ref": ("customer_ref", "customer ref", "customer id", "customer #", "cust ref"),
    "customer_kind": ("customer_kind", "customer type", "customer kind", "type"),
    "customer_name": ("customer_name", "customer name", "name", "customer"),
    "email": ("email", "e-mail", "email address"),
    "phone": ("phone", "telephone", "phone number"),
    "mailing_address": ("mailing_address", "mailing address", "mail to", "billing address"),
    # BR-CUS-046 "account # auto-option" — blank allocates from the series.
    "account_no": ("account_no", "account #", "account no", "account number", "account"),
    # BR-CUS-046/047 — REQUIRED, and it must already exist.
    "unit_ref": ("unit_ref", "premises/unit ref", "unit ref", "premise/unit", "unit", "premises"),
    "category": ("category", "account category", "consumer category", "class"),
    "subtype": ("subtype", "sub-type", "sub type", "account subtype"),
    "plan_override": ("plan_override", "plan override", "plan", "rate plan"),
    "status": ("status", "account status", "state"),
    "deposit_amount": ("deposit_amount", "deposit", "deposit $", "deposit amount"),
    "deposit_received_on": ("deposit_received_on", "deposit date", "deposit received"),
    "tax_exempt": ("tax_exempt", "tax exempt", "tax-exempt", "exempt"),
    "autopay": ("autopay", "autopay enrollment", "auto pay", "enrolled in autopay"),
    # BR-CUS-048 — four AGED buckets, never a lump sum.
    "ob_current": ("ob_current", "opening balance current", "current", "balance current"),
    "ob_31_60": ("ob_31_60", "opening balance 31-60", "31-60", "31_60"),
    "ob_61_90": ("ob_61_90", "opening balance 61-90", "61-90", "61_90"),
    "ob_90_plus": ("ob_90_plus", "ob_90+", "opening balance 90+", "90+", "90_plus"),
    "since": ("since", "since date", "service start", "opened", "start date"),
}
PUBLISHED_HEADERS: tuple[str, ...] = tuple(aliases[0] for aliases in TEMPLATE_COLUMNS.values())

#: The one REQUIRED column (BR-CUS-046/047). Everything else has a defined
#: meaning when blank; a unit ref does not — a row that names no unit names no
#: account, because `accounts.unit_id` is NOT NULL.
REQUIRED_TARGETS: tuple[str, ...] = ("unit_ref",)

#: BR-CUS-060: the bill-delivery-day preference was DROPPED. Named here so a
#: future "helpful" addition has to argue with the ruling first.
DROPPED_COLUMNS: tuple[str, ...] = ("bill_delivery_day",)

#: A commented header block written above the template's header row. The
#: published template IS the specification of the columns (BR-CUS-046) — a
#: README sentence is not an artifact an operator can open in a spreadsheet.
TEMPLATE_NOTES: tuple[str, ...] = (
    "SMART360 Next — account import template (BR-CUS-046).",
    "Import order (BR-CUS-047): premises -> units+plans -> assets -> ACCOUNTS -> opening reads.",
    "A row naming a unit that does not exist is an ERROR. Units are never auto-created.",
    "customer_ref groups rows: one distinct ref = one customer, many accounts (BR-CUS-054).",
    "account_no may be blank - a number is allocated from your account series (BR-TEN-035).",
    "Money columns are plain decimals, no currency symbol and no thousands separator.",
    "Dates are YYYY-MM-DD. Maximum 10,000 rows per file (BR-CUS-051).",
)

# Accepted date shapes: ISO first (the template's own), then the two a US
# legacy export realistically emits. Anything else is a PARSE ERROR — a value
# is never guessed into a date.
_DATE_FORMATS: tuple[str, ...] = ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d-%b-%Y")

_TRUE = frozenset({"y", "yes", "true", "t", "1", "on"})
_FALSE = frozenset({"n", "no", "false", "f", "0", "off", ""})

# ── error codes (they surface verbatim next to the row, and in the UI) ──────
ERR_ENCODING = "file_not_utf8"
ERR_TOO_LARGE = "file_too_large"
ERR_NO_HEADER = "file_has_no_header_row"
ERR_UNMAPPED_COLUMN = "required_column_not_mapped"
ERR_ROW_CAP = "row_cap_exceeded"
ERR_UNIT_REF_MISSING = "unit_ref_missing"
ERR_DATE_UNPARSEABLE = "date_unparseable"
ERR_NOT_A_NUMBER = "not_a_number"
ERR_NEGATIVE = "must_not_be_negative"
ERR_BOOL_UNPARSEABLE = "not_a_yes_no_value"
ERR_KIND_UNKNOWN = "customer_kind_unknown"

#: B2 r9 #1: `customers (kind person|company, …)`. Two values, closed set.
CUSTOMER_KINDS: tuple[str, ...] = ("person", "company")
_KIND_ALIASES: dict[str, str] = {
    "person": "person",
    "individual": "person",
    "residential": "person",
    "p": "person",
    "i": "person",
    "company": "company",
    "business": "company",
    "commercial": "company",
    "organisation": "company",
    "organization": "company",
    "c": "company",
    "b": "company",
}


@dataclass
class ParsedRow:
    """One template row, parsed but NOT resolved. `raw` keeps the file's own
    cells so the wizard can show an operator what they actually uploaded."""

    row_no: int
    raw: dict[str, str]
    values: dict[str, Any] = field(default_factory=dict)
    errors: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ParsedFile:
    rows: list[ParsedRow] = field(default_factory=list)
    mapping: dict[str, str] = field(default_factory=dict)
    file_hash: str = ""


def template_csv() -> str:
    """The PUBLISHED template (BR-CUS-046) — the downloadable artifact, not a
    description of one.

    A comment block first (spreadsheets keep it; the parser skips it), then the
    header row, then ONE example row so the shapes are unambiguous. The example
    is deliberately obvious junk (`CUST-0001`, `REPLACE ME`) — a realistic
    sample row is a row somebody imports by accident.
    """
    lines = [f"# {note}" for note in TEMPLATE_NOTES]
    lines.append(",".join(PUBLISHED_HEADERS))
    lines.append(
        ",".join(
            (
                "CUST-0001",
                "person",
                "REPLACE ME",
                "name@example.com",
                "+1 555 0100",
                "same-as-service",
                "",
                "1408 Elm Street · Unit A",
                "residential",
                "",
                "",
                "active",
                "0.00",
                "",
                "N",
                "N",
                "0.00",
                "0.00",
                "0.00",
                "0.00",
                "2026-01-01",
            )
        )
    )
    return "\n".join(lines) + "\n"


def file_hash(content: str) -> str:
    """🔒 Half one of the DB-12 file+tags key. SHA-256 of the file's UTF-8
    bytes, computed server-side — a client-supplied hash would be a client
    deciding whether its own upload is a replay."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def tag_fingerprint(*, cutover_date: Any) -> str:
    """🔒 Half two of the DB-12 file+tags key.

    The batch-level TAGS of an account import. Today that is one fact — the
    cutover as-of date (US-CUS-021 §5, batch level) — and it is hashed rather
    than stored raw so the column has one shape whatever joins it later.

    A batch with no cutover date fingerprints the empty tag set, which is still
    a stable value: two undated stagings of the same file are still the same
    import.
    """
    payload = "|".join(("cutover", str(cutover_date or "")))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def detect_columns(headers: list[str]) -> dict[str, str]:
    """BR-MET-032's standard, applied to this template: the mapping is
    re-detected on EVERY upload and never remembered between them."""
    mapping: dict[str, str] = {}
    lowered: dict[str, str] = {}
    for header in headers:
        key = str(header or "").strip().lower().replace("-", "_").replace("  ", " ")
        lowered.setdefault(key, header)
        lowered.setdefault(key.replace("_", " "), header)
    for target, aliases in TEMPLATE_COLUMNS.items():
        for alias in aliases:
            if alias in lowered:
                mapping[target] = lowered[alias]
                break
    return mapping


def parse(content: str) -> ParsedFile:
    """Text → `ParsedRow`s. Raises nothing for a BAD ROW (that is a row error);
    raises `ValueError` only for a file that is not a file — the caller turns
    those into the catalog refusals BR-CUS-051 requires."""
    if len(content.encode("utf-8")) > BYTE_CAP:
        raise ValueError(ERR_TOO_LARGE)
    # A template downloaded from this product carries its own comment block.
    body = "\n".join(line for line in content.splitlines() if not line.lstrip().startswith("#"))
    reader = csv.DictReader(io.StringIO(body))
    if not reader.fieldnames:
        raise ValueError(ERR_NO_HEADER)
    mapping = detect_columns(list(reader.fieldnames))
    missing = [target for target in REQUIRED_TARGETS if target not in mapping]
    if missing:
        raise ValueError(f"{ERR_UNMAPPED_COLUMN}:{','.join(missing)}")

    parsed = ParsedFile(mapping=mapping, file_hash=file_hash(content))
    for index, raw in enumerate(reader, start=1):
        if index > ROW_CAP:
            raise ValueError(ERR_ROW_CAP)
        cleaned = {
            str(key): ("" if value is None else str(value).strip())
            for key, value in raw.items()
            if key is not None
        }
        if not any(cleaned.values()):  # a trailing blank line is not a row
            continue
        parsed.rows.append(_parse_row(len(parsed.rows) + 1, cleaned, mapping))
    return parsed


def _parse_row(row_no: int, raw: dict[str, str], mapping: dict[str, str]) -> ParsedRow:
    row = ParsedRow(row_no=row_no, raw=raw)

    def cell(target: str) -> str:
        source = mapping.get(target)
        return raw.get(source, "").strip() if source else ""

    def fail(column: str, code: str, **params: Any) -> None:
        row.errors.append({"column": column, "code": code, **params})

    # ── identity (BR-CUS-054) ───────────────────────────────────────────────
    row.values["customer_ref"] = cell("customer_ref") or None
    kind_raw = cell("customer_kind").lower()
    if kind_raw:
        kind = _KIND_ALIASES.get(kind_raw)
        if kind is None:
            fail("customer_kind", ERR_KIND_UNKNOWN, value=cell("customer_kind"))
        else:
            row.values["customer_kind"] = kind
    row.values["customer_name"] = cell("customer_name") or None
    row.values["email"] = cell("email") or None
    row.values["phone"] = cell("phone") or None
    row.values["mailing_address"] = cell("mailing_address") or None

    # ── the account itself ──────────────────────────────────────────────────
    row.values["account_no"] = cell("account_no") or None
    unit_ref = cell("unit_ref")
    if not unit_ref:
        fail("unit_ref", ERR_UNIT_REF_MISSING)
    row.values["unit_ref"] = unit_ref or None
    for target in ("category", "subtype", "plan_override", "status"):
        row.values[target] = cell(target) or None

    # ── flags (BR-CUS-059 autopay is capture-only) ──────────────────────────
    for target in ("tax_exempt", "autopay"):
        text = cell(target).lower()
        if text in _TRUE:
            row.values[target] = True
        elif text in _FALSE:
            row.values[target] = False
        else:
            fail(target, ERR_BOOL_UNPARSEABLE, value=cell(target))

    # ── money, as DECIMAL STRINGS (CLAUDE.md rule 2 — never float) ──────────
    row.values["deposit_amount"] = _money(cell("deposit_amount"), "deposit_amount", fail)
    for target in ("ob_current", "ob_31_60", "ob_61_90", "ob_90_plus"):
        row.values[target] = _money(cell(target), target, fail)

    # ── dates ───────────────────────────────────────────────────────────────
    row.values["deposit_received_on"] = _date(
        cell("deposit_received_on"), "deposit_received_on", fail
    )
    row.values["since"] = _date(cell("since"), "since", fail)
    return row


def _money(text: str, column: str, fail: Any) -> str | None:
    """A money cell → the exact decimal STRING, or an error.

    Never a float and never cents (CLAUDE.md rule 2). A blank is None, which
    the caller reads as "not stated" — distinct from 0.00, which is a stated
    zero. A negative is refused here rather than in the service because the
    reason is the same wherever it is caught: no signed rule says what a
    negative opening bucket or a negative deposit MEANS (BR-CUS-048 buckets are
    debits; legacy credit balances are OQ-065, still OPEN).
    """
    if not text:
        return None
    stripped = text.replace(",", "").replace("$", "").strip()
    try:
        amount = Decimal(stripped)
    except (InvalidOperation, ValueError):
        fail(column, ERR_NOT_A_NUMBER, value=text)
        return None
    if amount < 0:
        # OQ-065 (OPEN) owns legacy CREDIT balances. Naming it in the row error
        # is the difference between "we refuse this" and "we guessed".
        fail(column, ERR_NEGATIVE, value=text, oq_ref="OQ-065")
        return None
    return str(amount)


def _date(text: str, column: str, fail: Any) -> date | None:
    if not text:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    fail(column, ERR_DATE_UNPARSEABLE, value=text)
    return None


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CUS-019@248ffac (EP-CUS-07 lead story, sha1 of the epic file; co-packet customers 02-business-rules@554f391)
# generated: 2026-08-11 by story-coder (W2 customers slice 4 — the brownfield account import)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 idempotency key, HUMAN-REVIEW-PENDING, ledger row appended)
# gates: see the lane report
# exceptions: the TAG half of the DB-12 file+tags key is DERIVED — an account import's only batch-level tag in any signed document is the cutover as-of date (US-CUS-021 §5), so the fingerprint covers that and nothing else; stated in the docstring rather than assumed · rows with a BLANK account # have no natural key of their own, so a RE-TYPED file (different bytes, same accounts) would re-create exactly those rows — minted as OQ-165, refused by nothing, reported loudly · US-CUS-020's value-mapping step is NOT built: an unmapped legacy code is a ROW ERROR, which is what BR-CUS-052 says happens to one · the `plan_override` column is PARSED but its DB target was SUPERSEDED on 2026-08-11 (no account-side plan table; the plan lives on the unit) — the service refuses rows carrying one, citing OQ-166
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
