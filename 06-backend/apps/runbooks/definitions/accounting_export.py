# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-042 (EP-RBS-01) — runbook 36, *Month-end journal file*: the
#           general-journal CSV a bookkeeper downloads and imports, and the
#           list of what could not go in it.
# Rules:    PO ruling 2026-09-06 (*"A plain general-journal CSV — date, account
#           code, description, debit, credit, reference"*) · decision log
#           2026-09-06 ×3 (the export is TWO things; the download half needs no
#           change request; the four decisions this file implements) ·
#           BR-RBS-002 (a Check is CONSTRUCTED with no ports) · BR-RBS-010
#           (every record states the rule that decided it, in words a clerk can
#           read) · BR-RBS-011 (a failure names its fix route) · BR-RBS-019 (the
#           declared unit of work) · BR-RBS-020 (the report is frozen at close) ·
#           BR-RBS-021 (twelve blocks) · BR-RBS-023 (a step declares its mode) ·
#           BR-RBS-024 (one category from the sixteen) · BR-RBS-039 (every
#           foreign read through a seam) · BR-RBS-042 (declared inputs; *all* is
#           the WORD, resolved at run start) · CLAUDE.md hard rule 2 (money 4
#           stored / 2 displayed, CHAR(3) currency, never a float) · hard rule 5
#           (balanced pairs; only the ledger posting service writes journal
#           lines — this writes none) · B14 rules 31 · 32 · 33
# Tests:    06-backend/tests/test_us_rbs_042_accounting_export.py
#           06-backend/tests/test_us_rbs_042_pg.py (PostgreSQL only)
# Impacts:  apps/runbooks/definitions/__init__.py (the one line that registers
#           it) · apps/runbooks/seams/ledger_seam.py · seams/tenancy_seam.py ·
#           apps/ledger/selectors.py (the two reads ledger adds for it)
# ───────────────────────────────────────────────────────
"""Runbook 36 — **Month-end journal file**.

What the utility does today: *the bookkeeper reads figures off a screen and
types them into QuickBooks by hand, every month.* What this produces: **a plain
general-journal CSV they download and import**, and — just as importantly — **a
list of what could not go in it and why.**

The file, ruled by the Product Owner on 2026-09-06, verbatim:

    "A plain general-journal CSV — date, account code, description, debit,
     credit, reference. Every accounting system on earth imports this, usually
     after a one-time column mapping. Safest default."

**Six columns, in that order.** Not QuickBooks' own import format, not Sage's.

THE FOUR DECISIONS THIS FILE IMPLEMENTS — recorded 2026-09-06, not re-opened
-----------------------------------------------------------------------------
1. **Debit and credit carry TWO decimals.** Hard rule 2 stores money to four and
   DISPLAYS two, and an importer expects two. **A file is a display surface.**
2. **One file is ONE currency**, `CHAR(3)`. Two currencies would be two files and
   a new question, so a second one REFUSES rather than adding a seventh column.
3. ⚠ **THE EXPORT NEVER INVENTS AN ACCOUNT CODE, AND THIS IS THE WHOLE DESIGN.**
   Export every line that maps; REPORT every one that does not, each naming its
   fix route. A file with a guessed account code is worse than no file: it
   imports cleanly, puts money in the wrong place, and nobody finds out until a
   reconciliation.
4. **AN UNBALANCED FILE IS REFUSED, NOT EXPORTED.** Hard rule 5 — journal
   entries are balanced pairs. Both sides are summed over what is about to be
   written and the whole file is refused if they differ, naming the difference.
   An accounting system rejects an unbalanced journal anyway; catching it here
   means a clerk reads a sentence instead of a stack trace from QuickBooks.

IT IS A CHECK, SO IT DECLARES NO PORTS AT ALL
----------------------------------------------
`BR-RBS-002`, and `RunbookDefinition` refuses a Check that declares one at
CONSTRUCTION. **Producing a download is not a write to a business record**
(decision log 2026-09-06) — nothing here needs the fourteenth port, which is
only for the day the product PUSHES the file to the accounting system itself.

⚠ **AND IT WRITES NO JOURNAL LINE, WHICH IS HARD RULE 5's OTHER HALF.** Only the
ledger posting service writes journal lines. This runbook can tell a bookkeeper
the books do not foot and it **cannot post the correction** — the same sentence
`seams/ledger_seam.py` opens with, and the reason `ledger` owns none of the
thirteen ports.

THIS RUNBOOK COMPUTES NO MONEY
-------------------------------
Every figure it hands over is `apps.ledger.exports.export_preview` for the
window — the same rows `S43` renders and the same rows the tie-out checks.
`apps/ledger/exports.py` says why in its own words: *"a second summation here
would be a second answer to what did July hold, and the day the two disagreed
the ERP would hold the wrong one."* A runbook that added its own `SUM(amount)`
would be exactly that second answer, and it would be **the one on the
bookkeeper's desk**. So the figures cross the seam and the arithmetic never
does; the only arithmetic in this file is `debit − credit` for the refusal
message, over numbers the ledger published.

FIVE JUDGMENTS THIS FILE MAKES AND RECORDS RATHER THAN ASKING (law 13)
-----------------------------------------------------------------------
1. **THE ROWS ARE ONE PER ACCOUNT PER MONTH, NOT ONE PER JOURNAL LINE.** The
   seeded utility's July holds **824 journal lines and 11 accounts with
   movement**. A bookkeeper importing 824 lines into QuickBooks gets 824 journal
   lines to reconcile; importing 11 gets the month-end journal they would have
   typed. It is also the shape `apps.ledger.exports` already publishes, so this
   runbook re-sums nothing. A line-level variant is a LATER ADDITION using the
   same six columns and the same reads — never a rework.
2. **AN OPEN MONTH IS A WARNING THAT STILL CARRIES ITS FILE, NOT A REFUSAL.**
   `BR-LED-017` requires a CLOSED period before the ledger's own recorded,
   idempotent handover — *"the ERP never receives numbers that can still move"*
   — and that rule governs `create_export_batch`, which writes an `ExportBatch`
   and asserts *this is what we sent for July, once*. **This runbook records
   nothing, asserts nothing and may be re-run any number of times**, and the
   Product Owner named exactly ONE refusal (unbalanced). Withholding the
   deliverable on a second refusal nobody ruled would make the runbook useless
   on every tenant until somebody presses Close — while the clerk goes on typing
   figures by hand, which is the problem it exists to solve. So the verdict SAYS
   the month is still open, in words, and the file is still there.
3. **ONE PARAMETER, AND NO `raise_work_items` TOGGLE.** Runbook 1 declares one;
   nothing reads it yet. A knob nothing reads is dead UI (hard-won law 2), and
   adding a second one here would be a second dead knob rather than consistency.
4. **THE `reference` COLUMN CARRIES THE MONTH** — `2026-07` — and not a batch
   number. `core.numbering.EXPORT_BATCH` exists and **no tenant has an
   `export_batch` row in `number_series`** (`exports.EXPORT_SERIES_NOT_SEEDED`),
   so a batch number here would be a number this product cannot mint. The month
   is what a bookkeeper searches on anyway.
5. **THE `description` COLUMN IS THE ACCOUNT'S OWN NAME.** B14 rule 32 keeps
   internal codes out of clerk-facing copy and rule 33 caps a fact at six words;
   *"Electric usage"* is what the bookkeeper's chart calls it and what they will
   map it to.

⚠ **WHAT WOULD MAKE THIS RUNBOOK PASS WRONGLY, ANSWERED IN WRITING** (hard-won
law 7's second habit). The dangerous shape is **an empty file that reads like a
clean month**: eleven header-only bytes and a green verdict. So every step
returns a `checked` mapping saying **how many things it looked at**, the KPI
strip draws the file's row count and its total beside the blocked count, and a
month with no posted activity is reported as *nothing to export* in words rather
than as a balanced zero. A tenant with no posted months at all is reported the
same way — `BR-RBS-042` clause 2: **an empty domain says so.**

⚠ **WHERE THE FILE CANNOT REACH A CLERK TODAY, STATED RATHER THAN IMPLIED.**
`journal_csv()` below composes the bytes and is tested against real books. The
only download addresses this module mounts are
`runbooks/runs/{id}/results/{done|not-done}.csv`, whose columns are the nine
RECORD columns of `result_files.COLUMNS` and whose third word is a deliberate
404 (`api.py`'s own `re_path`). **A general journal cannot be expressed in those
nine columns** — they carry no date and no account code — so a third file name
is owed. That is `DEF-RBS-4312`, filed rather than worked around, and the
`downloads` block below names the file the day the address exists.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from apps.runbooks import models
from apps.runbooks.contract import (
    DOMAIN_PERIOD,
    MODE_PER_RECORD,
    MODE_SET,
    PARAM_ALL,
    PARAM_WINDOW,
    Block,
    Parameter,
    RunbookDefinition,
    Step,
    SubjectRef,
)
from apps.runbooks.seams import ledger_seam, tenancy_seam

# ── the file ──────────────────────────────────────────────────────────────

#: The PO's six, in the PO's order. **Lower case and spaced, exactly as ruled** —
#: a bookkeeper maps these once, by hand, in their own package's import wizard,
#: and a column they have to guess at is a column they will map wrongly.
JOURNAL_COLUMNS = ("date", "account code", "description", "debit", "credit", "reference")

#: Hard rule 2 — money DISPLAYS at two decimals, and a file is a display
#: surface. `ROUND_HALF_UP` because that is what B4 rounds with everywhere else;
#: banker's rounding here would disagree with the invoice the figure came from,
#: by a cent, on some rows and not others.
_TWO_PLACES = Decimal("0.01")
_ZERO = Decimal("0")

#: The word a tenant stores when it wants every month — `BR-RBS-042` clause 1:
#: *"store the word; resolve it at run start, never expanded to a list at
#: configure time"*. A utility that exports *all* in September and posts into
#: October must get October on the next run with nothing to reconfigure.
#:
#: ⚠ **ONE SPELLING, SHARED — CHANGED IN WAVE `T`.** This was `"all"` written
#: out here, which was correct and was a SECOND definition of a word the whole
#: product now stores: `contract.PARAM_ALL` is the one this module validates
#: against, expands and refuses on a single-value input. Two spellings of one
#: rule is how a rename lands in one file and not the other, and the alias keeps
#: every existing use in this file reading exactly as it did.
ALL = PARAM_ALL


def _money(amount: Any) -> str:
    """A `Decimal` at two decimals. **Never a float, never cents, never blank.**

    A blank debit cell and a `0.00` debit cell are different things to an
    importer: blank is *no value on this side*, `0.00` is *this side is zero*.
    A general journal wants the number on both sides so the two columns foot, so
    this never returns an empty string and the caller never passes `None`.
    """
    return str(Decimal(amount or 0).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class JournalRow:
    """One line of the file, already in the reader's terms.

    ⚠ **NO FIELD HERE CARRIES A DATABASE ID** (B14 rule 31). `account_code` is
    the chart's own code — `1200`, `4100` — which is what a bookkeeper maps and
    what `A14 §Accounting exports` says a CSV addresses an account by. The
    account's uuid never leaves the seam.
    """

    when: date
    account_code: str
    description: str
    debit: Decimal
    credit: Decimal
    reference: str

    def as_cells(self) -> list[str]:
        return [
            self.when.isoformat(),
            self.account_code,
            self.description,
            _money(self.debit),
            _money(self.credit),
            self.reference,
        ]


def journal_csv(rows: list[JournalRow]) -> str:
    """The six columns and one line per row. The whole file, as text.

    ⚠ **THE `csv` WRITER HERE IS NOT LAW 11's FORBIDDEN ONE.** CLAUDE.md's rule
    is *never round-trip a shared REGISTER through a `csv` writer*, because
    re-serialising 1,900 rows is a whole-file write wearing the costume of an
    append. This composes a fresh download from figures in memory and reads no
    file at all — the same distinction `result_files.py` draws, stated again
    here because a reader grepping for `import csv` deserves it rather than a
    second's alarm.

    ⚠ **`\\r\\n` IS THE ROW TERMINATOR, WHICH IS `csv`'s DEFAULT AND IS LEFT
    ALONE.** Excel and every accounting importer on Windows read it; changing it
    to `\\n` to make a test string tidier would be a formatting decision made
    for the convenience of the test rather than of the reader.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(JOURNAL_COLUMNS)
    for row in rows:
        writer.writerow(row.as_cells())
    return buffer.getvalue()


def file_name(months: list[str], currency: str) -> str:
    """`journal-2026-07-USD.csv`, or `journal-2026-07-to-2026-09-USD.csv`.

    ⚠ **THE CURRENCY IS IN THE NAME BECAUSE ONE FILE IS ONE CURRENCY** (decision
    2 above). A bookkeeper with two sets of books downloads two files on the same
    day into one folder, and a name that did not say which is which is how the
    wrong one gets imported.

    No id appears here, so rule 31 is not even in question: the months are the
    file's natural key and two runs over the same months are the same file.
    """
    if not months:
        return f"journal-{currency}.csv"
    if len(months) == 1:
        return f"journal-{months[0]}-{currency}.csv"
    return f"journal-{months[0]}-to-{months[-1]}-{currency}.csv"


# ── what could not be exported ────────────────────────────────────────────

BLOCKER = "blocker"
WARNING = "warning"

#: Every fix route is a path this product actually mounts, verified against
#: `07-frontend/src/App.tsx`. They are TENANT-RELATIVE, exactly like
#: `tenancy.selectors.CHECKLIST_TARGETS` and runbook 1's — the shell prefixes
#: `/:tenant/`. A fix route that resolves to nothing is a dead button over a live
#: finding, which is hard-won law 2's mirror and which no backend test can see.
FIX_FINANCE = "finance"
FIX_FINANCE_EXPORT = "finance/export"
FIX_SETTINGS_REGIONAL = "settings/regional"


@dataclass(frozen=True)
class Blocked:
    """One thing that could not be exported, in words, with the screen that fixes it.

    ⚠ **`fix_route` IS REQUIRED** (`BR-RBS-011`): a failure with no route is a
    defect in the runbook, because a finding a clerk cannot act on is a finding
    we should not have shown them.

    ⚠ **`decided_by_rule` IS A SENTENCE AND NEVER A RULE ID** (`BR-RBS-010`,
    B14 rule 32). The id belongs in this file's docstrings, where an engineer
    reads it.
    """

    key: str
    reason: str
    affects: str
    weight: str
    fix_route: str
    fix_label: str
    decided_by_rule: str

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("a blocked row with no reason says nothing to anybody")
        if not self.fix_route.strip():
            raise ValueError(
                f"blocked row {self.reason!r} names no fix route. BR-RBS-011: a failure names "
                "its fix route, and one without a route is a defect in the runbook."
            )
        if not self.fix_label.strip():
            raise ValueError(f"blocked row {self.reason!r} has a route and no words on the button")
        if self.weight not in (BLOCKER, WARNING):
            raise ValueError(f"blocked row {self.reason!r} carries weight {self.weight!r}")

    def as_row(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "reason": self.reason,
            "affects": self.affects,
            "weight": self.weight,
            "fix_route": self.fix_route,
            "fix_label": self.fix_label,
            "decided_by_rule": self.decided_by_rule,
        }


@dataclass
class _StepResult:
    """What every set step returns — what it found, and what it looked at.

    `checked` is not decoration. A step that reports nothing over an empty set of
    books and a step that reports nothing over a correct one are the same
    sentence with very different meanings (hard-won law 7).
    """

    blocked: list[Blocked] = field(default_factory=list)
    checked: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "blocked": [row.as_row() for row in self.blocked],
            "checked": dict(self.checked),
        }


# ── the six steps ─────────────────────────────────────────────────────────

STEP_MONTHS = "months"
STEP_FIGURES = "figures"
STEP_CURRENCY = "currency"
STEP_BALANCE = "balance"
STEP_MAPPING = "mapping"
STEP_FILE = "file"

STEP_LABELS = {
    STEP_MONTHS: "Months",
    STEP_FIGURES: "Figures",
    STEP_CURRENCY: "Currency",
    STEP_BALANCE: "Balance",
    STEP_MAPPING: "Account codes",
    STEP_FILE: "The file",
}


def month_label(first: date) -> str:
    """`2026-07` — the month a row belongs to, and the file's `reference` cell."""
    return f"{first.year:04d}-{first.month:02d}"


def step_months(ctx, subjects) -> dict[str, Any]:
    """1 · What this run covers, and whether the tenant has anything to export.

    `BR-RBS-042` clause 2 — **an empty domain says so.** A utility that has
    posted nothing has no accounting month, and saying *nothing to export* is a
    different statement from handing over a balanced file of zeroes.
    """
    result = _StepResult()
    chosen = [subject.label for subject in subjects]
    result.checked = {
        "months": len(chosen),
        "labels": chosen,
        "asked_for": str((ctx.params or {}).get("period") or ALL),
    }
    if not chosen:
        result.blocked.append(
            Blocked(
                key="no_months",
                reason="Nothing is posted yet.",
                affects="Every month",
                weight=BLOCKER,
                fix_route=FIX_FINANCE,
                fix_label="Open the books",
                decided_by_rule="A month is exportable once something is posted in it.",
            )
        )
    return result.as_dict()


def step_figures(ctx, subject) -> dict[str, Any]:
    """2 · One month's books, per record, as the LEDGER publishes them.

    ⚠ **PER-RECORD, AND THE UNIT IS THE ACCOUNTING MONTH** (`BR-RBS-019`,
    `BR-RBS-023`). One month is one savepoint and one record row: a period whose
    read fails does not take the other months' figures with it, which is exactly
    what hard-won law 14's savepoint is for on PostgreSQL.

    The outcome word is a fact a clerk reads in the records table, so it is
    plain: **ready** or **off**.
    """
    first, last = _window(subject)
    figures = ledger_seam.period_figures(first, last)
    carried = ctx.set_results.setdefault(STEP_FIGURES, {"months": []})
    rows = [
        JournalRow(
            when=last,
            account_code=row["code"],
            description=row["name"],
            debit=row["debit"] or _ZERO,
            credit=row["credit"] or _ZERO,
            reference=month_label(first),
        )
        for row in figures["rows"]
    ]
    balanced = bool(figures["balanced"])
    month = {
        "label": subject.label,
        "month": month_label(first),
        "closed": bool(figures["period_closed"]),
        "balanced": balanced,
        "lines": len(rows),
        "debits": str(figures["total_debits"] or _ZERO),
        "credits": str(figures["total_credits"] or _ZERO),
        "missing_refs": list(figures["missing_refs"]),
        "rows": [
            {
                "when": row.when.isoformat(),
                "code": row.account_code,
                "name": row.description,
                "debit": str(row.debit),
                "credit": str(row.credit),
                "reference": row.reference,
            }
            for row in rows
        ],
    }
    # ⚠ **CARRIED FORWARD BY HAND, BECAUSE THE ENGINE CARRIES IT THE OTHER
    # WAY.** `ExecutionContext.set_results` is documented as *"set by the
    # executor before the per-record pass so a per-record step can read what a
    # set step computed"* — set → per-record. Nothing carries a per-record
    # outcome FORWARD to a later set step, and the balance, the mapping and the
    # file all need every month's figures at once. Writing them into the context
    # under this step's own key is the seam-free way to do it, and it is ONE
    # read of the ledger per month rather than three. Re-reading instead would
    # break `BR-RBS-009`'s pinning in the quietest way there is: a month whose
    # books moved between step 2 and step 6 would balance in one and not in the
    # other, and the file would be the disagreement.
    carried["months"].append(month)
    return {
        "outcome": "ready" if balanced else "off",
        "reason": (
            "Ready to export."
            if balanced
            else f"Off by {_money(abs(figures['total_debits'] - figures['total_credits']))}."
        ),
        "decided_by_rule": "Every month's debits equal its credits.",
        "fix_route": "" if balanced else FIX_FINANCE,
        # ⚠ **THE ROWS DO NOT TRAVEL IN THE RECORD.** A record row is what a
        # clerk reads about one month; the eleven account rows behind it are the
        # FILE's, and `runbook_run_records.data` is not where a file belongs.
        # What a reader needs in order to act is here — the month, whether it is
        # closed, its two totals and how many lines it contributes.
        "data": {
            "label": month["label"],
            "month": month["month"],
            "closed": month["closed"],
            "lines": month["lines"],
            "debits": month["debits"],
            "credits": month["credits"],
        },
    }


def step_currency(ctx, subjects) -> dict[str, Any]:
    """3 · One file is ONE currency (decision 2), and it travels as `CHAR(3)`.

    A mixed-currency journal has no meaning to an importer. If a tenant ever
    posts in two, that is two files and a new question — never a seventh column
    added quietly — so a second currency REFUSES the file rather than widening
    it.
    """
    result = _StepResult()
    currency = tenancy_seam.currency()
    result.checked = {"currency": currency}
    if len(currency) != 3:
        result.blocked.append(
            Blocked(
                key="currency_shape",
                reason="The currency is not set.",
                affects="Every row",
                weight=BLOCKER,
                fix_route=FIX_SETTINGS_REGIONAL,
                fix_label="Set the currency",
                decided_by_rule="Every amount carries a three-letter currency.",
            )
        )
    return result.as_dict()


def step_balance(ctx, subjects) -> dict[str, Any]:
    """4 · Sum both sides over the WHOLE file and refuse it if they differ.

    Decision 4 and hard rule 5. `apps.ledger.exports` refuses the recorded
    handover on the same fact with `SYS-DRIFT`, and its reason applies here word
    for word: unbalanced books mean a posting-service bypass happened, and *"no
    clean-looking handover over broken books"*.

    ⚠ **THE REFUSAL IS OVER THE FILE, AND THE REPORT ALSO NAMES THE MONTH.** The
    ruling says *sum both sides over what you are about to write*, so the file is
    refused whole; a clerk who is only told the file is off by `$14.25` and not
    WHICH month it is in has to find it by hand, which is the manual tally this
    runbook exists to remove.
    """
    result = _StepResult()
    debits = _ZERO
    credits = _ZERO
    off_months: list[str] = []
    for record in _month_records(ctx):
        debits += Decimal(record["debits"])
        credits += Decimal(record["credits"])
        if Decimal(record["debits"]) != Decimal(record["credits"]):
            off_months.append(record["month"])
    difference = debits - credits
    result.checked = {
        "debits": str(debits),
        "credits": str(credits),
        "difference": str(difference),
        "months_off": off_months,
    }
    if difference != _ZERO:
        result.blocked.append(
            Blocked(
                key="does_not_balance",
                # B14 rule 33 — a fact is six words, and two sentences of six
                # beat one of twelve. The figure goes in `affects`, where the
                # table draws it in its own column.
                reason="The file does not balance.",
                affects=f"Off by {_money(abs(difference))} · {', '.join(off_months) or 'across the file'}",
                weight=BLOCKER,
                fix_route=FIX_FINANCE,
                fix_label="Open the books",
                decided_by_rule="Debits equal credits in every set of books.",
            )
        )
    return result.as_dict()


def step_mapping(ctx, subjects) -> dict[str, Any]:
    """5 · What has no account code behind it — reported, never guessed.

    Decision 3, and the whole design. Three shapes, each a different fact:

    * **an account carrying movement with a blank code** — nothing to put in the
      *account code* column, so the row cannot be written at all;
    * **a place in the books with no account behind it** — money of that kind
      cannot post, so it never reaches the journal and cannot reach the file
      either. The seeded utility has three;
    * **an account missing the target's reference** — empty for a plain CSV by
      construction (`REF_FIELD_BY_TARGET` maps `csv` to `None`, because a CSV
      addresses an account by code and name), and still read and still reported,
      because the same list is what refuses on the day a tenant exports to
      QuickBooks or Xero.
    """
    result = _StepResult()
    codeless = ledger_seam.accounts_without_a_code()
    unmapped = ledger_seam.unmapped_designations()
    missing_refs: list[str] = []
    for record in _month_records(ctx):
        missing_refs.extend(record.get("missing_refs") or ())
    result.checked = {
        "accounts_without_a_code": len(codeless),
        "unmapped_designations": len(unmapped),
        "missing_refs": len(set(missing_refs)),
    }
    if codeless:
        result.blocked.append(
            Blocked(
                key="accounts_without_a_code",
                reason="Some accounts have no code.",
                affects=f"{len(codeless)} accounts · {', '.join(row['name'] for row in codeless)}",
                weight=BLOCKER,
                fix_route=FIX_FINANCE,
                fix_label="Give it a code",
                decided_by_rule="An import finds an account by its code.",
            )
        )
    if unmapped:
        result.blocked.append(
            Blocked(
                key="unmapped_designations",
                reason="Some postings have no account.",
                affects=f"{len(unmapped)} of the books · {', '.join(_words(name) for name in unmapped)}",
                weight=WARNING,
                fix_route=FIX_FINANCE,
                fix_label="Finish the mapping",
                decided_by_rule="Each kind of posting names its own account.",
            )
        )
    return result.as_dict()


def step_file(ctx, subjects) -> dict[str, Any]:
    """6 · Compose the file — or say why there is not one.

    ⚠ **THE ORDER OF THE STEPS IS THE GUARANTEE.** Steps run in DECLARATION
    ORDER (`executor.execute`), so by the time this runs the balance and the
    currency have both been decided and this step reads their verdicts rather
    than re-deciding them. A file composed before the balance check would exist
    for a moment, which is a moment in which something could serve it.

    ⚠ **A BLOCKER MEANS NO FILE AT ALL, NOT A SHORTER ONE.** Decision 4 is
    *refuse the whole file*: a file with the unbalanced month quietly dropped
    would import cleanly and be wrong, which is the same harm as a guessed
    account code one door along.
    """
    result = _StepResult()
    blockers = [row for row in _blocked_so_far(ctx) if row["weight"] == BLOCKER]
    rows: list[JournalRow] = []
    if not blockers:
        for record in _month_records(ctx):
            for row in record["rows"]:
                rows.append(
                    JournalRow(
                        when=date.fromisoformat(row["when"]),
                        account_code=row["code"],
                        description=row["name"],
                        debit=Decimal(row["debit"]),
                        credit=Decimal(row["credit"]),
                        reference=row["reference"],
                    )
                )
    months = [record["month"] for record in _month_records(ctx)]
    currency = str(((ctx.set_results.get(STEP_CURRENCY) or {}).get("checked") or {}).get(
        "currency", "USD"
    ))
    debits = sum((row.debit for row in rows), _ZERO)
    credits = sum((row.credit for row in rows), _ZERO)
    result.checked = {
        "lines": len(rows),
        "months": len(months),
        "currency": currency,
        "debits": _money(debits),
        "credits": _money(credits),
        "file_name": file_name(months, currency),
        "refused": bool(blockers),
        # The file's own bytes, composed once and carried so that the report,
        # the download and every test read the SAME string rather than three
        # renderings of one intention.
        "csv": journal_csv(rows) if rows else "",
    }
    return result.as_dict()


# ── the small helpers the steps share ─────────────────────────────────────


def _window(subject: SubjectRef) -> tuple[date, date]:
    """The month a period subject stands for, from its own id.

    ⚠ **THE SUBJECT ID IS `2026-07-01:2026-07-31` AND NOT A DATABASE ID**
    (B14 rule 31, and `SubjectRef.subject_id` is a string on purpose). A period
    is not a row in this product — `fiscal_period_closes` holds only the months
    somebody has CLOSED — so there is no id to carry, and inventing one would be
    a row nobody wrote.
    """
    first, _, last = subject.subject_id.partition(":")
    return date.fromisoformat(first), date.fromisoformat(last)


def _month_records(ctx) -> list[dict[str, Any]]:
    """Every month's figures, in run order, from step 2's per-record outcomes.

    ⚠ **STEP 2 PUT THEM THERE AND THE ENGINE DID NOT.** `set_results` is filled
    by the executor for SET steps only, and it carries set → per-record. Step 2
    is per-record and writes its own key — the note on `carried` in that step
    says why. A later step that re-read the ledger instead would be a second
    answer to *what did July hold* three lines after this file promised there
    would not be one, and it would break `BR-RBS-009`'s pinning at the same time.
    """
    return list((ctx.set_results.get(STEP_FIGURES) or {}).get("months") or [])


def _blocked_so_far(ctx) -> list[dict[str, Any]]:
    """Everything the earlier set steps refused, flattened, in step order."""
    rows: list[dict[str, Any]] = []
    for key in STEP_LABELS:
        result = ctx.set_results.get(key) or {}
        rows.extend(result.get("blocked") or [])
    return rows


def _words(name: str) -> str:
    """`allowance_doubtful_accounts` → `Allowance doubtful accounts`.

    B14 rule 32 — no internal code in clerk-facing copy. A designation is our
    word for a slot in the chart; a bookkeeper reads the words.
    """
    return name.replace("_", " ").capitalize()


# ── the report ────────────────────────────────────────────────────────────

_TONE = {"go": "success", "warn": "warning", "no_go": "danger"}


def report(view) -> list[Block]:
    """Four blocks: the verdict, the numbers, what is blocked, and the file.

    ⚠ **FOUR OF THE TWELVE, AND NO THIRTEENTH** (`BR-RBS-021`). There is no
    `chain` because six steps that all read the same books tell a clerk nothing
    a verdict does not, and no `breakdown` because the months are the records
    table's own rows. `RB-020`'s claim survives: this runbook is one Python
    module and no frontend code.
    """
    set_results = view.set_results
    file_state = (set_results.get(STEP_FILE) or {}).get("checked") or {}
    blocked = _report_blocked(set_results)
    blockers = [row for row in blocked if row["weight"] == BLOCKER]
    warnings = [row for row in blocked if row["weight"] == WARNING]
    open_months = [
        str((record.data or {}).get("month") or "")
        for record in view.records
        if not (record.data or {}).get("closed", True)
    ]

    if blockers:
        word, tone, count = "No file", "no_go", _headline(blockers)
    elif warnings or open_months:
        word, tone, count = "Ready, with notes", "warn", _headline(warnings, open_months)
    else:
        word, tone, count = "Ready to import", "go", f"{file_state.get('lines', 0)} lines."

    return [
        Block(
            block="verdict",
            payload={
                "word": word,
                "tone": _TONE[tone],
                "count": count,
                "detail": file_state.get("file_name", ""),
            },
        ),
        Block(
            block="kpis",
            payload={
                "tiles": [
                    {
                        "id": "lines",
                        "label": "Lines exported",
                        "value": {"kind": "text", "text": str(file_state.get("lines", 0))},
                    },
                    {
                        "id": "blocked",
                        "label": "Blocked",
                        "value": {"kind": "text", "text": str(len(blocked))},
                    },
                    {
                        "id": "total",
                        "label": "File total",
                        "value": {
                            "kind": "money",
                            "amount": str(file_state.get("debits", "0.00")),
                            "currency": str(file_state.get("currency", "USD")),
                        },
                        # `BR-REP-001`: a books figure reads the POSTING date, and
                        # the journal file IS the books. Stated on the tile rather
                        # than left to the renderer's fallback — `DEF-RBS-4350`,
                        # where a hardcoded "posting" was right here and wrong on
                        # the test bill, and nothing could tell the two apart.
                        "basis": "posting",
                    },
                ]
            },
        ),
        Block(
            block="records",
            payload={
                "columns": [
                    {"key": "finding", "label": "What"},
                    {"key": "affects", "label": "Affects"},
                    {"key": "weight", "label": "Weight"},
                    {"key": "fix", "label": "Fix"},
                ],
                "rows": [_blocked_row(index, row) for index, row in enumerate(blocked, start=1)],
                "total": len(blocked),
                "chips": [
                    {"id": "all", "label": "All", "count": len(blocked)},
                    {"id": "blockers", "label": "Blockers", "count": len(blockers)},
                    {"id": "warnings", "label": "Warnings", "count": len(warnings)},
                ],
                # B14 rule 17's shape. A Check that finds nothing is a good
                # outcome rather than a gap, so the empty state carries no call
                # to action — the file is the action.
                "empty": {
                    "title": "Everything reached the file.",
                    "helper": "No account code was missing.",
                },
                # ⚠ CARRIED, NOT DRAWN, AND REACHABLE — what each step actually
                # looked at. An empty set of books and a correct one produce
                # different numbers here, and a reader can tell them apart.
                "checked": {
                    key: (set_results.get(key) or {}).get("checked", {}) for key in STEP_LABELS
                },
            },
        ),
        Block(
            block="downloads",
            payload={
                "files": (
                    []
                    if file_state.get("refused") or not file_state.get("lines")
                    else [
                        {
                            "id": "journal",
                            "label": "Journal file",
                            "format": "csv",
                        }
                    ]
                )
            },
        ),
    ]


def _report_blocked(set_results: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in STEP_LABELS:
        result = set_results.get(key) or {}
        rows.extend(result.get("blocked") or [])
    return rows


def _headline(to_fix: list[dict[str, Any]], open_months: list[str] | None = None) -> str:
    """The verdict's count line — a FACT, so **six words** (B14 rule 33).

    ⚠ **IT IS TWO CLAUSES OF THREE, NOT ONE OF SIX, AND THE MIDDLE DOT IS THE
    JOIN.** Rule 33's own words are *"two sentences of six beat one sentence of
    twelve"*, so the cap is per clause: *"1 to fix"* · *"3 months open."* An
    earlier draft read *"3 months still open"*, which is four, and the word that
    had to go is the one carrying no information.
    """
    parts: list[str] = []
    if to_fix:
        parts.append(f"{len(to_fix)} to fix")
    if open_months:
        # ⚠ **THE SINGULAR IS NOT A NICETY AND ONLY A REAL RUN FOUND IT.** The
        # first draft read *"1 months open"* on every tenant with one open
        # month, which is the whole seeded utility on its first month. A verdict
        # line is the most-read sentence this runbook produces.
        word = "month" if len(open_months) == 1 else "months"
        parts.append(f"{len(open_months)} {word} open")
    return " · ".join(parts) + "." if parts else "Nothing to fix."


def _blocked_row(index: int, row: dict[str, Any]) -> dict[str, Any]:
    """One row of the records table. `id` is the position and never a row id."""
    return {
        "id": str(index),
        "cells": {
            "finding": {"kind": "text", "text": row["reason"]},
            "affects": {"kind": "text", "text": row["affects"]},
            "weight": {
                "kind": "pill",
                "label": "Blocker" if row["weight"] == BLOCKER else "Warning",
                "tone": "danger" if row["weight"] == BLOCKER else "warning",
            },
            "fix": {"kind": "link", "label": row["fix_label"], "to": row["fix_route"]},
        },
        "meta": {"decided_by_rule": row["decided_by_rule"], "step": row["key"]},
    }


# ── the pinned set ────────────────────────────────────────────────────────


def resolve(ctx):
    """The months this run covers — **`all` resolved HERE, at run start.**

    `BR-RBS-042` clause 1, verbatim: *"store the word; resolve it at run start,
    never expanded to a list at configure time. A utility that picks all
    services with Water and Sewer and later adds Trash must get three, not the
    two frozen at setup."* The same sentence with *months* for *services*: a
    tenant that saved *all* in September and then posts into October gets
    October on its next run, with nothing to reconfigure and nothing on any
    screen to notice.

    It composes with `BR-RBS-009` — resolved once and PINNED — so a journal
    entry posted into a new month **while the run is going** is not in this
    file, and the run says which months it covered.

    The parameter accepts the word `all`, one month label, or several.
    """
    asked = (ctx.params or {}).get("period") or ALL
    months = ledger_seam.posted_months()
    if isinstance(asked, str) and asked.strip().lower() == ALL:
        chosen = months
    else:
        wanted = {asked} if isinstance(asked, str) else {str(value) for value in asked}
        chosen = tuple(pair for pair in months if month_label(pair[0]) in wanted)
    return [
        SubjectRef(
            subject_type="period",
            subject_id=f"{first.isoformat()}:{last.isoformat()}",
            label=month_label(first),
        )
        for first, last in chosen
    ]


RUNBOOK = RunbookDefinition(
    key="accounting_export",
    name="Month-end journal file",
    kind=models.KIND_CHECK,
    category="finance",
    subject_type="period",
    unit_of_work="accounting month",
    triggers=(models.TRIGGER_MANUAL, models.TRIGGER_SCHEDULE),
    tags=("Finance", "Accounting"),
    parameters=(
        Parameter(
            name="period",
            type=PARAM_WINDOW,
            label="Months",
            required=True,
            # ⚠ THE WORD, NEVER A LIST (`BR-RBS-042` clause 1). Its DOMAIN is
            # `ledger_seam.posted_months()` — tenant-resolved, clause 2 — and it
            # is read when the run starts, in `resolve()` above.
            default=ALL,
            # ⚠ **DECLARED IN WAVE `T`, AND THE BEHAVIOUR IS UNCHANGED.** This
            # runbook implemented clause 1 by hand before the mechanism existed:
            # the word in `default`, the expansion in `resolve()`, the domain in
            # a seam. What these two lines add is that `contract.Parameter` can
            # now SEE it — a picker knows what to draw, `_validated_parameters`
            # can refuse a month this tenant has not posted into, and
            # `services.run_parameters` expands the word before `resolve()` is
            # ever called. `resolve()`'s own branch stays as the fallback for a
            # caller that reaches `executor.execute` directly.
            multi=True,
            domain=DOMAIN_PERIOD,
        ),
    ),
    resolve=resolve,
    report=report,
    steps=(
        Step(key=STEP_MONTHS, label=STEP_LABELS[STEP_MONTHS], mode=MODE_SET, run=step_months),
        Step(
            key=STEP_FIGURES,
            label=STEP_LABELS[STEP_FIGURES],
            mode=MODE_PER_RECORD,
            run=step_figures,
        ),
        Step(key=STEP_CURRENCY, label=STEP_LABELS[STEP_CURRENCY], mode=MODE_SET, run=step_currency),
        Step(key=STEP_BALANCE, label=STEP_LABELS[STEP_BALANCE], mode=MODE_SET, run=step_balance),
        Step(key=STEP_MAPPING, label=STEP_LABELS[STEP_MAPPING], mode=MODE_SET, run=step_mapping),
        Step(key=STEP_FILE, label=STEP_LABELS[STEP_FILE], mode=MODE_SET, run=step_file),
    ),
)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-042 (EP-RBS-01; PO ruling 2026-09-06 + the three decision-log rows of the same day, quoted verbatim above)
# generated: 2026-09-06 by the CR-075 accounting-export build lane
# checklist: A✔ B✔ C✔ D=blocked(no address serves a six-column file — DEF-RBS-4312) E=n/a(no screen: RBS-006 renders it from the twelve blocks, RB-020) F✔ G✔ H=n/a(no 🔒 path: this composes no idempotency key, touches no rating math and posts no ledger line)
# gates: pytest tests/test_us_rbs_042_accounting_export.py · pytest tests/test_us_rbs_042_pg.py (PostgreSQL) · pytest tests/test_us_rbs_015_conformance.py · G115 (the import census) · G6 (no float on money)
# exceptions: (1) an OPEN month WARNS and still carries its file — argued in the module docstring against BR-LED-017, which governs the RECORDED handover · (2) rows are one per account per month, not one per journal line — the shape the ledger already publishes · (3) the composed file has no download address yet (DEF-RBS-4312) and the downloads block names it for the day it does
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
