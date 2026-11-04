# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-009 (EP-RBS-03) — CR-075 wave K task K1, runbook 9,
#           *Month-end completion*, on screen **Books tie-out**. Wave K CLOSES
#           phase 4.
# Rules:    BR-RBS-002 (a Check is CONSTRUCTED with no ports) · BR-RBS-010
#           (every record states the rule that decided it, in words) ·
#           BR-RBS-011 (a failure names its fix route) · BR-RBS-019 (the
#           declared unit of work) · BR-RBS-020 (the report is frozen at close) ·
#           BR-RBS-021 (twelve blocks) · BR-RBS-023 (a step declares its mode —
#           this is the phase's SET-MODE story) · BR-RBS-024 (one category) ·
#           BR-RBS-029 (the month-end tie-out tolerance for TAX is $0.00 and
#           CANNOT be raised) · BR-RBS-030 (closing the period is a named
#           person's act, never a step — CONFIRMED 2026-09-06, PO verbatim
#           *"1736 - always a person"*) · BR-RBS-039 (every foreign read
#           through a seam) · BR-LED-007 (the control-vs-register tie-outs) ·
#           BR-LED-006 (checklist items computed from live register states,
#           never checkboxes typed by hand) · BR-LED-018 (no hard lockout) ·
#           CLAUDE.md hard rule 2 (money 4 stored / 2 displayed, CHAR(3)) ·
#           hard rule 5 (balanced pairs; only the ledger posting service writes
#           journal lines — this writes none) · B14 rules 6 · 31 · 32 · 33 · 34
# Tests:    06-backend/tests/test_us_rbs_009_month_end.py
# Impacts:  apps/runbooks/definitions/__init__.py (the one line registering it) ·
#           apps/runbooks/seams/{ledger,billing,payments}_seam.py ·
#           apps/billing/selectors.unissued_run_count (published for this and
#           for the ledger's own close checklist, which had asked for it by
#           exact signature since US-LED-006 and never got it)
# ───────────────────────────────────────────────────────
"""Runbook 9 — **Books tie-out**. *Can this period be closed?*

Nine steps over one accounting period, **mostly SET mode**, and the output is
either *Balanced* or the exact list of what is not, each item linking to the
screen that settles it. **Closing the period itself stays a human act on the
last line.**

════════════════════════════════════════════════════════════════════════════
THIS RUNBOOK SUBTRACTS NOTHING. THAT IS ITS WHOLE DESIGN.
════════════════════════════════════════════════════════════════════════════
Every figure below crosses a seam already decided by the module that owns it:

* the four control-vs-register comparisons are `ledger.tie_out.tie_outs`, which
  applies `BR-LED-007` and is **the only place in the product that applies it**
  — `_verdict`'s own words are *"one implementation so that the API, the screen
  and the audit row cannot disagree about whether a book is drifting, which
  would be this check developing the very fault it exists to detect"*;
* the seven month-end tasks are `ledger.close.close_checklist`, which
  `BR-LED-006` requires to be *"computed from live register states, never
  checkboxes typed by hand"*;
* unfinished bill runs are `billing.selectors.unfinished_runs`;
* unapplied cash is `payments.selectors.unapplied_cash`.

**A month-end tie-out that computed its own `gl − register` would be a second
answer to *do the books agree*, and it would be the one on the finance user's
desk on the day they disagreed.** The only arithmetic in this file is counting
findings.

════════════════════════════════════════════════════════════════════════════
⚠ THE TAX TOLERANCE IS `$0.0000` AND THIS FILE REFUSES ANY OTHER VALUE
════════════════════════════════════════════════════════════════════════════
`BR-RBS-029`, and `RB-109`'s own card: *"Tolerance defaults to zero, and the tax
line has none at all. Tax is remitted to an authority; there is no 'we'll fix it
next month'."*

It is refused at CONSTRUCTION — `_refuse_a_tax_tolerance` runs during the import
`AppConfig.ready()` performs — rather than at run time, for the reason
`contract.py` gives for every other refusal it makes: a version of this rule that
checked at run time would mean a runbook with a raised tax tolerance existing in
memory on a live schedule, and a finance user closing a month over an unremitted
difference. **A parameter that cannot be edited to a wrong value cannot be
edited to a wrong value by a tenant either**, which is what `BR-RBS-029` means
by *cannot be raised*.

════════════════════════════════════════════════════════════════════════════
⚠ **CLOSE PERIOD ✓** IS DRAWN **DISABLED WITH ITS REASON**, NOT ABSENT
════════════════════════════════════════════════════════════════════════════
Five sources say disabled and two say absent, and the two are prose summaries
of the five. **Disabled with its reason** is what `RBS-006-R9`'s build sheet
says in its own words (*"danger · default · 14px · DISABLED — reason on the
button title"*), what `RB-109` says (*"Close period ✓ disabled carrying its
reason, '3 items open'"*), what `RB-109`'s own *Open questions and stated
absences* section CLOSED the question as (*"the button carries its reason in
words rather than being hidden, which is the platform's own rule for a control
a user may not yet use"* — `RBR-06`, B14), what `contract.PAYLOAD_FIELDS` makes
structurally required (`enabled: false` REQUIRES `reason`), and what
`ActionBlock.tsx` and `blocks/types.ts` already render — the union is
discriminated, so `tsc` refuses a disabled control with no explanation.

`10-execution-plan.md`'s `K2` row and `EP-RBS-03` line 281 say *absent*. Both
are filed as `DEF-RBS-4360` and amended rather than followed. **The distinction
that makes them wrong is worth stating: a control is ABSENT when the CAPABILITY
does not exist** — wave `L7`'s *"the Approve control is absent in the dry half,
not greyed"*, because nothing can send — **and DISABLED when a PRECONDITION is
not met.** Closing a period is a capability this product has; three items are
open. Hiding it would leave a finance user hunting for a button nobody told them
about.

⚠ **AND THE BUTTON IS THE LEDGER'S ACT, NOT THIS RUNBOOK'S.** `BR-RBS-030` —
CONFIRMED 2026-09-06, PO verbatim *"1736 - always a person"* — and this runbook
holds no port for it and never will while that rule stands. The `action` block
declares the button; `apps.ledger.close.close_period` performs it, with a
person's name on it and its own reason recorded.

════════════════════════════════════════════════════════════════════════════
⚠ THE TAX ROW IS KNOWN TO BE WRONG FROM THE SECOND POSTED PERIOD ONWARD
════════════════════════════════════════════════════════════════════════════
`DEF-LED-4356`, found by THIS runbook on 2026-09-07 and filed rather than
smoothed. `ledger.tie_out._tax_row` takes the GL side cumulative to `period_end`
and the register side for `period_start..period_end`, so from month two the
drift contains every earlier month's tax **on a correct book** — which is the
exact sentence `tie_outs`' own docstring says would be wrong, hard-won law 1 in
one file.

Measured on the seeded utility: **July GL $816.45 against $818.75 outstanding,
drift −$2.30** — the one real discrepancy, Bexar County local tax at $375.48
booked against $377.78 billed — and **August GL $1,657.64 against $841.19, drift
+$816.45**, which is exactly July's cumulative GL. The honest cumulative
comparison at 31 August is $1,657.64 against $1,659.94, drift −$2.30, the same
single discrepancy carried forward.

**Step 5 names the defect on the row rather than correcting it.** Correcting
another module's signed money comparison from here would be the second answer
this file spent its first paragraph refusing to be, and it would be one nobody
could find.

════════════════════════════════════════════════════════════════════════════
THIS IS THE PHASE'S SET-MODE STORY (`BR-RBS-023`, `TC-RBS-17`)
════════════════════════════════════════════════════════════════════════════
Eight of the nine steps are SET: they run **once** over the whole pinned set
whatever its size. A tie-out over 1,410 bills executes its set step once, not
1,410 times, and over 1.2M journal lines the difference is the runbook being
usable at all. Step 2 is PER-RECORD because it is the one that genuinely walks
each period, in its own SAVEPOINT — which is also what gives `TC-RBS-17` a
per-record step to count against the set ones.

FOUR JUDGMENTS RECORDED RATHER THAN ASKED (law 13)
----------------------------------------------------
1. **`unknown` IS DRAWN DIFFERENTLY FROM `incomplete`.** The ledger's checklist
   has three states and `unknown` means *the register could not be read*.
   *"We looked and it is not done"* and *"we could not look"* are different
   sentences to a finance user and only one names a fix they can perform. Both
   block the close, because a green tick nobody computed is hard-won law 1.
2. **A `failed` BILL RUN COUNTS AS UNFINISHED.** `RB-109` step 1 says *"issued
   or cancelled — nothing half-done"*, so the settled set is those two and
   nothing else. A month closed over a failed run is a month whose bills nobody
   can account for. The set lives in `billing.selectors`, beside the column it
   filters.
3. **THE DEPOSIT ROW IS READ FROM THE TIE-OUT AND NOT FROM `accounts.
   deposit_on_file`.** That column was unwritten for weeks (`DEF-177`) and the
   ledger's own row carries the reasoning; reading it here would be a second
   answer with an older bug in it.
4. **AN OPEN PERIOD IS NOT A FINDING.** `close_checklist` reports `closed`, and
   a period that is still open is the ordinary state of the month being tied
   out. It is drawn as a fact, never as something to settle.

⚠ **WHAT WOULD MAKE THIS RUNBOOK PASS WRONGLY, ANSWERED IN WRITING** (law 7's
second habit). The dangerous shape is **a period with nothing in it reading as a
balanced month**: no runs, no payments, no journal lines, nine green steps and
*Close period ✓* enabled over an empty book. So every step returns a `checked`
mapping saying what it looked at, the KPI strip draws the figures beside the
counts, and a period the ledger has never posted into is reported as *nothing is
posted in this period* in words rather than as a balanced zero.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from apps.runbooks import models
from apps.runbooks.contract import (
    DOMAIN_PERIOD,
    MODE_PER_RECORD,
    MODE_SET,
    PARAM_MONEY,
    PARAM_TOGGLE,
    PARAM_WINDOW,
    Block,
    Parameter,
    RunbookContractError,
    RunbookDefinition,
    Step,
    SubjectRef,
)
from apps.runbooks.seams import billing_seam, ledger_seam, payments_seam, tenancy_seam

_FOUR_PLACES = Decimal("0.0001")
_TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0")

#: `BR-RBS-029` — **the month-end tie-out tolerance for tax is `$0.0000` and it
#: cannot be raised.** It is a `Decimal` and not a float, and it is a constant
#: and not a default, because a default is something a tenant edits on Settings
#: and this is not editable by anybody.
TAX_TOLERANCE = Decimal("0.0000")

def money4(value: Any) -> Decimal:
    """FOUR decimals — hard rule 2's storage precision, never a float."""
    if isinstance(value, Decimal):
        return value.quantize(_FOUR_PLACES, rounding=ROUND_HALF_UP)
    return Decimal(str(value or 0)).quantize(_FOUR_PLACES, rounding=ROUND_HALF_UP)


def money2(value: Any) -> str:
    """The string a finance user reads — TWO decimals, always."""
    return str(money4(value).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP))


def money_words(value: Any) -> str:
    """`USD 1657.64` — a money figure with its CHAR(3) beside it.

    ⚠ **THE VERDICT LINE IS A PLAIN STRING, SO THE CURRENCY CANNOT RIDE ON A
    `MoneyCell`.** Every tabular figure in this report is a `{"kind": "money",
    "amount", "currency"}` value and the renderer puts the symbol on; the
    verdict's `detail` is one sentence and has no cell to carry it. Hard rule 2
    wants the code beside the amount wherever a person reads one, so it is put
    there here rather than left off because the block has no field for it.

    ⚠ **THE CODE AND NOT A SYMBOL.** `$` is four different currencies in North
    America alone, and `bankrec_read` already records the reason in its own
    words — *"a wrong symbol on a Canadian utility's banking is a money defect
    wearing a formatting costume."*

    It counts as ONE word for B14 rule 33: *"Tax off by USD 1657.64"* is five.
    """
    return f"{tenancy_seam.currency()} {money2(value)}"


# ── what has to be settled ────────────────────────────────────────────────

BLOCKER = "blocker"
WARNING = "warning"

#: Tenant-relative, exactly as `tenancy.selectors.CHECKLIST_TARGETS` — the shell
#: prefixes `/:tenant/`. `DEF-RBS-4329` is what an absolute-looking relative
#: route cost: every Fix link on every runbook landed on *"not built yet"*.
FIX_BILLING_RUNS = "billing/runs"
FIX_PAYMENTS = "payments"
FIX_FINANCE = "finance"
FIX_FINANCE_REMITTANCE = "finance/remittance"
FIX_FINANCE_EXPORT = "finance/export"
FIX_BANK_REC = "payments/bank-reconciliation"


@dataclass(frozen=True)
class Settle:
    """One thing to settle before this period can close, with its fix route.

    ⚠ **`fix_route` IS REQUIRED** (`BR-RBS-011`) and **`decided_by_rule` IS A
    SENTENCE, NEVER A RULE ID** (`BR-RBS-010`, B14 rule 32).
    """

    key: str
    item: str
    detail: str
    weight: str
    fix_route: str
    fix_label: str
    decided_by_rule: str
    #: The VERDICT's own clause — *"Tax off by $14.25"*, *"$312.00 unapplied"*.
    #:
    #: ⚠ **IT IS A SEPARATE FIELD BECAUSE B14 RULE 33 CAPS BY WHAT THE TEXT IS
    #: FOR, AND THESE TWO ARE FOR DIFFERENT THINGS.** `detail` is a table CELL
    #: with a whole column to itself; the verdict line puts three of these side
    #: by side under one banner, so each has to survive being read at a glance.
    #: Rule 33: *"two sentences of six beat one sentence of twelve"*, and the
    #: cap is PER CLAUSE. Deriving it from `detail` would give
    #: *"Tax 1657.64 between the books and what was billed"* — eight words, and
    #: a bare number with no currency in front of it.
    #:
    #: Empty means *this row does not belong on the banner*, which is the
    #: honest answer for a row whose whole meaning is in its table cell.
    headline: str = ""

    def __post_init__(self) -> None:
        if not self.item.strip():
            raise ValueError("a settle row with no item says nothing to anybody")
        if not self.fix_route.strip():
            raise ValueError(
                f"settle row {self.item!r} names no fix route. BR-RBS-011: a failure names its "
                "fix route, and one without a route is a defect in the runbook."
            )
        if self.weight not in (BLOCKER, WARNING):
            raise ValueError(f"settle row {self.item!r} carries weight {self.weight!r}")

    def as_row(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "item": self.item,
            "detail": self.detail,
            "weight": self.weight,
            "fix_route": self.fix_route,
            "fix_label": self.fix_label,
            "decided_by_rule": self.decided_by_rule,
            "headline": self.headline,
        }


@dataclass
class _StepResult:
    """What a step returns — what it found, and what it LOOKED AT.

    `checked` is not decoration: a step reporting nothing over an empty period
    and one reporting nothing over a correct month are the same sentence with
    very different meanings (hard-won law 7).
    """

    settle: list[Settle] = field(default_factory=list)
    checked: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "settle": [row.as_row() for row in self.settle],
            "checked": dict(self.checked),
        }


# ── the nine steps ────────────────────────────────────────────────────────

STEP_RUNS = "runs"
STEP_FIGURES = "figures"
STEP_UNAPPLIED = "unapplied"
STEP_RECEIVABLES = "receivables"
STEP_REVENUE_TAX = "revenue_tax"
STEP_BANK = "bank"
STEP_ADJUSTMENTS = "adjustments"
STEP_DEPOSITS = "deposits"
STEP_EXPORTS = "exports"

#: `RB-109`'s own nine, in its own order. B14 rule 33 caps a LABEL at three
#: words; every one of these obeys it, and the chain block draws them.
STEP_LABELS = {
    STEP_RUNS: "Runs finished",
    STEP_FIGURES: "Figures",
    STEP_UNAPPLIED: "Unapplied cash",
    STEP_RECEIVABLES: "Receivables",
    STEP_REVENUE_TAX: "Revenue and tax",
    STEP_BANK: "Bank reconciled",
    STEP_ADJUSTMENTS: "Adjustments",
    STEP_DEPOSITS: "Deposits",
    STEP_EXPORTS: "Exports ready",
}

#: `close_checklist`'s codes → the step that reports each. A checklist item with
#: no step here would be a month-end task the ledger requires and this runbook
#: never mentions, so the map is asserted complete by the test suite rather than
#: trusted.
CHECKLIST_STEP = {
    "runs_issued": STEP_RUNS,
    "batches_reconciled": STEP_BANK,
    "bank_rec_current": STEP_BANK,
    "accruals_posted": STEP_ADJUSTMENTS,
    "unbilled_accrual": STEP_ADJUSTMENTS,
    "unpaid_cost_accrual": STEP_ADJUSTMENTS,
    "remittance_recorded": STEP_REVENUE_TAX,
}

#: The words a finance user reads for each checklist code. B14 rule 31 keeps the
#: internal code off the screen; rule 33 caps a LABEL at three words.
CHECKLIST_WORDS = {
    "runs_issued": ("Bill runs", FIX_BILLING_RUNS, "Open runs"),
    "batches_reconciled": ("Deposit batches", FIX_BANK_REC, "Reconcile"),
    "bank_rec_current": ("Bank lines", FIX_BANK_REC, "Reconcile"),
    "accruals_posted": ("Accruals", FIX_FINANCE, "Open the books"),
    "unbilled_accrual": ("Unbilled revenue", FIX_FINANCE, "Post the accrual"),
    "unpaid_cost_accrual": ("Unpaid costs", FIX_FINANCE, "Post the accrual"),
    "remittance_recorded": ("Tax remittance", FIX_FINANCE_REMITTANCE, "Record it"),
}


def _window(subject: SubjectRef) -> tuple[date, date]:
    """The month a period subject stands for, from its own id.

    ⚠ **THE SUBJECT ID IS `2026-08-01:2026-08-31` AND NOT A DATABASE ID**
    (B14 rule 31). A period is not a row in this product — `fiscal_period_closes`
    holds only the months somebody has CLOSED — so there is no id to carry, and
    inventing one would be a row nobody wrote. Runbook 36 resolves a period the
    same way, three files away, for the same reason.
    """
    first, _, last = subject.subject_id.partition(":")
    return date.fromisoformat(first), date.fromisoformat(last)


def _period(ctx) -> tuple[date, date] | None:
    """The ONE period this run covers, from the pinned set. `None` if empty."""
    carried = (ctx.set_results.get(STEP_RUNS) or {}).get("checked", {}).get("period")
    if carried:
        return date.fromisoformat(carried[0]), date.fromisoformat(carried[1])
    return None


def _checklist(ctx) -> dict[str, Any]:
    """The ledger's checklist, read ONCE per run and carried (`BR-RBS-009`)."""
    return (ctx.set_results.get(STEP_FIGURES) or {}).get("checklist") or {}


def _tie_outs(ctx) -> dict[str, Any]:
    """The ledger's four tie-out rows, read ONCE per run and carried."""
    return (ctx.set_results.get(STEP_FIGURES) or {}).get("tie_outs") or {}


def _row(tie_outs: dict[str, Any], subledger: str) -> dict[str, Any] | None:
    return next(
        (row for row in tie_outs.get("rows") or () if row["subledger"] == subledger), None
    )


def _checklist_settle(ctx, code: str, weight: str = BLOCKER) -> list[Settle]:
    """One checklist item as a settle row — or none, when it is complete.

    ⚠ **THREE STATES, AND `unknown` IS DRAWN AS ITS OWN THING.** *We looked and
    it is not done* and *we could not look* are different sentences to a finance
    user and only one names a fix they can perform. Both block the close: an
    item nobody could compute is an item nobody proved, and `BR-LED-006` puts
    `unknown` in the incomplete pile for exactly that reason.
    """
    checklist = _checklist(ctx)
    item = next(
        (one for one in checklist.get("items") or () if one["code"] == code), None
    )
    if item is None or item["state"] == "complete":
        return []
    words, route, label = CHECKLIST_WORDS[code]
    unknown = item["state"] == "unknown"
    outstanding = item.get("outstanding")
    return [
        Settle(
            key=code,
            item=words,
            detail=(
                "We could not read this register."
                if unknown
                else (f"{outstanding} outstanding." if outstanding else "Not done yet.")
            ),
            headline=(
                f"{words} unreadable" if unknown else f"{words} not done"
            ),
            weight=WARNING if unknown else weight,
            fix_route=route,
            fix_label=label,
            decided_by_rule=(
                "A month cannot close on a check nobody could run."
                if unknown
                else "The ledger requires this before a period closes."
            ),
        )
    ]


def step_runs(ctx, subjects) -> dict[str, Any]:
    """1 · Is every bill run finished — issued or cancelled, nothing half-done?

    ⚠ **THE READ THIS STEP USES IS THE ONE THE LEDGER HAD BEEN ASKING FOR SINCE
    `US-LED-006` AND NEVER GOT.** `close.py`'s `WANTED_READS` names
    `apps.billing.selectors.unissued_run_count(start, end) -> int` by exact
    signature; nothing published it, so the checklist's *every run finished* item
    reported UNKNOWN on every tenant for ever and no utility could reach a green
    close. It is published now, and this is its first reader.
    """
    result = _StepResult()
    if not subjects:
        result.checked = {"period": None, "unfinished": 0, "runs": []}
        result.settle.append(
            Settle(
                key="no_period",
                item="This period",
                detail="Nothing is posted in this period.",
                weight=WARNING,
                fix_route=FIX_FINANCE,
                fix_label="Open the books",
                decided_by_rule="A month with no entries has nothing to tie out.",
            )
        )
        return result.as_dict()

    first, last = _window(subjects[0])
    runs = billing_seam.unfinished_runs(first, last)
    result.checked = {
        "period": [first.isoformat(), last.isoformat()],
        "unfinished": len(runs),
        "runs": [
            {
                # B14 rule 31 — the human number, and the PERIOD where a run
                # predates the series and has none.
                "run": row["run_no"] or f"{row['period_start']} – {row['period_end']}",
                "status": row["status"],
            }
            for row in runs
        ],
    }
    if runs:
        result.settle.append(
            Settle(
                key="runs_unfinished",
                item="Bill runs",
                detail=f"{len(runs)} not finished.",
                headline=f"{len(runs)} bill runs unfinished",
                weight=BLOCKER,
                fix_route=FIX_BILLING_RUNS,
                fix_label="Open runs",
                decided_by_rule="Every run must be issued or cancelled, never half-done.",
            )
        )
    return result.as_dict()


def step_figures(ctx, subject) -> dict[str, Any]:
    """2 · One period's books, PER RECORD, as the ledger publishes them.

    ⚠ **PER-RECORD, AND THE UNIT IS THE ACCOUNTING PERIOD** (`BR-RBS-019`,
    `BR-RBS-023`). One period is one savepoint and one record row, which is what
    hard-won law 14's savepoint is for on PostgreSQL: a period whose read fails
    does not take the run down with it. It is also the ONE per-record step in
    this runbook, so `TC-RBS-17` has something to count the eight set steps
    against.

    ⚠ **THE RESULTS ARE WRITTEN ONTO `set_results` BY THIS STEP AND NOT BY THE
    ENGINE.** The executor fills `set_results` for SET steps only; a per-record
    step that wants to hand something to a later step writes its own key. Every
    later step reads THESE figures rather than calling the ledger again — one
    answer to *what did August hold*, which is the promise this file's first
    paragraph makes.
    """
    first, last = _window(subject)
    tie_outs = ledger_seam.tie_out_rows(first, last)
    checklist = ledger_seam.close_checklist(first, last)
    figures = ledger_seam.period_figures(first, last)
    ctx.set_results.setdefault(STEP_FIGURES, {})
    ctx.set_results[STEP_FIGURES].update(
        {"tie_outs": tie_outs, "checklist": checklist, "figures": figures}
    )
    return {
        "outcome": "read",
        "reason": (
            f"{len(figures['rows'])} accounts moved · "
            f"{money2(figures['total_debits'])} posted"
        ),
        "decided_by_rule": "A period is read from the books, never re-summed.",
        "data": {
            "period": f"{first.isoformat()}:{last.isoformat()}",
            "accounts_with_movement": len(figures["rows"]),
            "debits": str(figures["total_debits"]),
            "credits": str(figures["total_credits"]),
            "balanced": figures["balanced"],
            "closed": figures["period_closed"],
        },
    }


def step_unapplied(ctx, subjects) -> dict[str, Any]:
    """3 · Unapplied cash — listed, and within the amount allowed.

    The allowance defaults to `$0.00` (`RB-109`'s own card), so on most tenants
    any figure here is a finding. It is a MONEY parameter and therefore a string
    default, never a float: the value lives in `runbook_versions.definition`,
    which is `jsonb`, where no column type could catch one (hard rule 2).
    """
    result = _StepResult()
    period = _period(ctx)
    if period is None:
        result.checked = {"total": "0.00", "payments": 0}
        return result.as_dict()
    first, last = period
    allowed = money4((ctx.params or {}).get("unapplied_allowed", "0.00"))
    answer = payments_seam.unapplied_cash(first, last)
    total = money4(answer["total"])
    result.checked = {
        "total": str(total),
        "allowed": str(allowed),
        "payments": answer["payment_count"],
        "currency": answer["currency"],
        "rows": [
            {
                "payment": row["payment_no"],
                "unapplied": str(row["unapplied"]),
                "posted_on": row["posted_on"].isoformat(),
            }
            for row in answer["payments"]
        ],
    }
    if total > allowed:
        result.settle.append(
            Settle(
                key="unapplied_cash",
                item="Unapplied cash",
                # ⚠ **THE CURRENCY IS HERE BECAUSE THE BROWSER SHOWED IT
                # MISSING (2026-09-07).** The KPI tile beside this row draws
                # `$1,195.05` through `MoneyCell`; this cell is a `text` value,
                # so nothing downstream can add a symbol — and it drew a bare
                # `1195.05`. One screen stated the same figure twice with a
                # currency on one of them. Hard rule 2 wants the code beside
                # every amount a person reads, and only a walkthrough saw it.
                detail=(
                    f"{money_words(total)} across {answer['payment_count']} payments."
                ),
                headline=f"{money_words(total)} unapplied",
                weight=BLOCKER,
                fix_route=FIX_PAYMENTS,
                fix_label="Allocate",
                decided_by_rule="Money we hold has to be pointed at a bill.",
            )
        )
    return result.as_dict()


def step_receivables(ctx, subjects) -> dict[str, Any]:
    """4 · Do receivables tie — sub-ledger to control account, TO THE CENT?

    `BR-LED-007`'s first row, read from `ledger.tie_out`. The tolerance is zero
    and there is no parameter for it: *to the cent* is the rule's own words and
    a receivables tolerance would be a knob for hiding a real difference.
    """
    result = _StepResult()
    row = _row(_tie_outs(ctx), "accounts_receivable")
    result.checked = _tie_out_checked(row)
    result.settle.extend(
        _tie_out_settle(
            row,
            key="receivables",
            item="Receivables",
            fix_route=FIX_FINANCE,
            fix_label="Open the books",
            rule="The sub-ledger and the control account must agree to the cent.",
        )
    )
    return result.as_dict()


def step_revenue_tax(ctx, subjects) -> dict[str, Any]:
    """5 · Do revenue and tax tie — billed totals to posted totals?

    ⚠ **THE TAX TOLERANCE IS `$0.0000` AND CANNOT BE RAISED** (`BR-RBS-029`).
    There is no parameter for it and `_refuse_a_tax_tolerance` refuses one at
    construction. Tax is remitted to an authority; there is no *we'll fix it next
    month*.

    ⚠ **AND THE ROW THIS STEP READS IS KNOWN TO BE WRONG FROM THE SECOND POSTED
    PERIOD ONWARD — `DEF-LED-4356`, named on the finding rather than corrected.**
    See this module's docstring for the worked figures. A finance user meeting a
    tax difference here needs to know that the comparison itself is under
    repair, or they will spend a day looking for money that is not missing.
    """
    result = _StepResult()
    tie_outs = _tie_outs(ctx)
    tax = _row(tie_outs, "tax_payable")
    figures = (ctx.set_results.get(STEP_FIGURES) or {}).get("figures") or {}
    result.checked = {
        **_tie_out_checked(tax),
        "tax_tolerance": str(TAX_TOLERANCE),
        "revenue_balanced": bool(figures.get("balanced")),
        "revenue_debits": str(figures.get("total_debits") or 0),
        "revenue_credits": str(figures.get("total_credits") or 0),
    }

    # Revenue: the period's own posted totals, as the ledger publishes them.
    # Hard rule 5 — balanced pairs. An unbalanced period is a broken book, not a
    # tolerance question, so it has no tolerance either.
    if figures and not figures.get("balanced"):
        result.settle.append(
            Settle(
                key="revenue_unbalanced",
                item="Revenue",
                detail=(
                    f"{money_words(figures.get('total_debits'))} debits · "
                    f"{money_words(figures.get('total_credits'))} credits."
                ),
                headline="Revenue does not balance",
                weight=BLOCKER,
                fix_route=FIX_FINANCE,
                fix_label="Open the books",
                decided_by_rule="Every entry is a balanced pair.",
            )
        )

    if tax is not None and tax["state"] != "agreed":
        drift = tax["drift"]
        result.settle.append(
            Settle(
                key="tax_does_not_tie",
                item="Tax",
                detail=(
                    "The tax comparison is under repair."
                    if drift is None
                    else f"{money_words(drift)} between the books and what was billed."
                ),
                headline=(
                    "Tax comparison under repair"
                    if drift is None
                    else f"Tax off by {money_words(drift)}"
                ),
                weight=BLOCKER,
                fix_route=FIX_FINANCE_REMITTANCE,
                fix_label="Open remittance",
                # ⚠ B14 rule 32 — no defect id in clerk-facing copy. The id is
                # in this file's docstring, where an engineer reads it.
                decided_by_rule="Tax goes to an authority, so it has no tolerance at all.",
            )
        )
    result.settle.extend(_checklist_settle(ctx, "remittance_recorded"))
    return result.as_dict()


def step_bank(ctx, subjects) -> dict[str, Any]:
    """6 · Is the bank reconciled — no unmatched statement lines?

    Both halves come from the ledger's checklist, which resolves payments' own
    published reads. `bank_rec_current` answers `None` when no statement covers
    the window, and that is reported as *we could not read this register* rather
    than as a green tick: a plain `.count()` would answer 0 on a month the bank
    has never been asked about, which is `DEF-127` exactly.
    """
    result = _StepResult()
    checklist = _checklist(ctx)
    result.checked = {
        one["code"]: {"state": one["state"], "outstanding": one["outstanding"]}
        for one in checklist.get("items") or ()
        if one["code"] in ("bank_rec_current", "batches_reconciled")
    }
    result.settle.extend(_checklist_settle(ctx, "bank_rec_current"))
    result.settle.extend(_checklist_settle(ctx, "batches_reconciled"))
    return result.as_dict()


def step_adjustments(ctx, subjects) -> dict[str, Any]:
    """7 · Are the accruals posted and every adjustment accounted for?

    ⚠ **THE APPROVER HALF IS A STATED ABSENCE, NOT A PASS.** `RB-109` step 7 is
    *"every write-off and credit has its approver"*, and nothing in this product
    records an approver ON an adjustment — `payments.Payment` carries `type =
    'adjustment'` and no approval column, and `DEF-3121` already records that an
    approved write-off writes no payment row at all. Reporting this green would
    be a tick nobody computed (hard-won law 1). It is `OQ-RBS-1739`, minted with
    this wave, and until it is answered the step reports the three ACCRUAL items
    the ledger does compute and says plainly what it cannot see.
    """
    result = _StepResult()
    checklist = _checklist(ctx)
    result.checked = {
        one["code"]: {"state": one["state"], "detail": one["detail"]}
        for one in checklist.get("items") or ()
        if one["code"] in ("accruals_posted", "unbilled_accrual", "unpaid_cost_accrual")
    }
    result.checked["approver_recorded_anywhere"] = False
    for code in ("accruals_posted", "unbilled_accrual", "unpaid_cost_accrual"):
        result.settle.extend(_checklist_settle(ctx, code))
    result.settle.append(
        Settle(
            key="approvers_unknown",
            item="Adjustments",
            detail="We cannot tell who approved these.",
            weight=WARNING,
            fix_route=FIX_FINANCE,
            fix_label="Open the books",
            decided_by_rule="Nothing records an approver against an adjustment yet.",
        )
    )
    return result.as_dict()


def step_deposits(ctx, subjects) -> dict[str, Any]:
    """8 · Do held deposits reconcile, and are refunds cleared?

    `BR-LED-007`'s second row. ⚠ It is read from the tie-out and NOT from
    `accounts.deposit_on_file`: that column was unwritten for weeks
    (`DEF-177`), the ledger's own row carries the reasoning and the named cause,
    and reading the column here would be a second answer with an older bug in
    it.
    """
    result = _StepResult()
    row = _row(_tie_outs(ctx), "deposit_liability")
    result.checked = _tie_out_checked(row)
    result.settle.extend(
        _tie_out_settle(
            row,
            key="deposits",
            item="Deposits held",
            fix_route=FIX_FINANCE,
            fix_label="Open the books",
            rule="Deposits are the customer's money and must reconcile exactly.",
        )
    )
    return result.as_dict()


def step_exports(ctx, subjects) -> dict[str, Any]:
    """9 · Are the export files prepared — and NOT yet sent?

    ⚠ **THE GL EXPORT MAY ONLY BE CALLED ONCE CLOSE HAS BEEN PRESSED, AND THAT
    GUARD LIVES IN THE LEDGER RATHER THAN HERE.** `RB-109`'s card puts it in
    this runbook; `BR-LED-017` already puts it on `create_export_batch`, which
    is where it can actually refuse — *"the ERP never receives numbers that can
    still move"*. Stating it twice would be two rules that can disagree, so this
    step REPORTS readiness and refuses nothing.

    Runbook 36 (*Month-end journal file*) composes the file itself. This step
    says whether there is one to compose, which is a different question and the
    only one a tie-out has to answer.
    """
    result = _StepResult()
    figures = (ctx.set_results.get(STEP_FIGURES) or {}).get("figures") or {}
    result.checked = {
        "accounts_with_movement": len(figures.get("rows") or ()),
        "balanced": bool(figures.get("balanced")),
        "period_closed": bool(figures.get("period_closed")),
        "missing_refs": len(figures.get("missing_refs") or ()),
    }
    if figures and not figures.get("rows"):
        result.settle.append(
            Settle(
                key="nothing_to_export",
                item="Exports",
                detail="Nothing is posted in this period.",
                weight=WARNING,
                fix_route=FIX_FINANCE_EXPORT,
                fix_label="Open exports",
                decided_by_rule="A month with no entries has no file to prepare.",
            )
        )
    return result.as_dict()


# ── the small helpers the tie-out steps share ─────────────────────────────


def _tie_out_checked(row: dict[str, Any] | None) -> dict[str, Any]:
    """One tie-out row's figures, as strings a frozen report can hold.

    ⚠ **`None` AND `0.00` ARE KEPT APART.** `TieOutRow` returns `None` when a
    side is unreadable and never `0.00`, and the ledger's whole module docstring
    turns on that distinction. Coercing it here would fold *we could not read
    this* in with *this is zero*, which is how a release ships on a check that
    never ran.
    """
    if row is None:
        return {"state": "unverifiable", "gl": None, "register": None, "drift": None}
    return {
        "state": row["state"],
        "gl": None if row["gl"] is None else str(row["gl"]),
        "register": None if row["register"] is None else str(row["register"]),
        "drift": None if row["drift"] is None else str(row["drift"]),
        "currency": row["currency"],
        "causes": [cause.get("code") for cause in row["causes"]],
    }


def _tie_out_settle(
    row: dict[str, Any] | None, *, key: str, item: str, fix_route: str, fix_label: str, rule: str
) -> list[Settle]:
    """A drifting or unverifiable tie-out row as a settle row — or none."""
    if row is None:
        return [
            Settle(
                key=f"{key}_unreadable",
                item=item,
                detail="We could not read this comparison.",
                weight=WARNING,
                fix_route=fix_route,
                fix_label=fix_label,
                decided_by_rule="A book nobody could check has not been checked.",
            )
        ]
    if row["state"] == "agreed":
        return []
    drift = row["drift"]
    return [
        Settle(
            key=key,
            item=item,
            detail=(
                "We could not read this comparison."
                if drift is None
                else f"{money_words(drift)} between the books and what is recorded."
            ),
            headline=(
                f"{item} unreadable" if drift is None else f"{item} off by {money_words(drift)}"
            ),
            weight=BLOCKER if drift is not None else WARNING,
            fix_route=fix_route,
            fix_label=fix_label,
            decided_by_rule=rule,
        )
    ]


# ── the report ────────────────────────────────────────────────────────────

_TONE = {"balanced": "success", "warn": "warning", "not_balanced": "danger"}


def _settle_rows(set_results: dict[str, Any], key: str) -> list[dict[str, Any]]:
    return list((set_results.get(key) or {}).get("settle") or [])


def _all_settle(set_results: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in STEP_LABELS:
        rows.extend(_settle_rows(set_results, key))
    return rows


def report(view) -> list[Block]:
    """`RBS-006-R9`'s six blocks: Verdict · KPIs · Reconciled · Records · Action
    · Downloads.

    ⚠ **SIX OF THE TWELVE AND NO THIRTEENTH** (`BR-RBS-021`). The build sheet's
    ten REGIONS are not ten blocks: regions 4–8 are the two tables and their
    headings, and region 10 is the balanced VARIANT of region 2 rather than a
    second block.
    """
    set_results = dict(view.set_results)
    settle = _all_settle(set_results)
    blockers = [row for row in settle if row["weight"] == BLOCKER]
    warnings = [row for row in settle if row["weight"] == WARNING]
    figures = (set_results.get(STEP_FIGURES) or {}).get("figures") or {}
    currency = tenancy_seam.currency()
    tie_outs = (set_results.get(STEP_FIGURES) or {}).get("tie_outs") or {}

    clear = sum(
        1
        for key in STEP_LABELS
        if not any(row["weight"] == BLOCKER for row in _settle_rows(set_results, key))
    )
    total_steps = len(STEP_LABELS)

    if blockers:
        word, tone = "Not balanced", "not_balanced"
    elif warnings:
        word, tone = "Balanced, with notes", "warn"
    else:
        word, tone = "Balanced", "balanced"
    count = f"{clear} of {total_steps} steps clear"
    # B14 rule 33 — a FACT caps at six words PER CLAUSE, and the middle dot is
    # the join. Each clause is the row's OWN `headline`; a row with none is not
    # on the banner at all, which is better than a clause nobody can read at a
    # glance. Three, because `RBS-006-R9`'s band draws three and a fourth wraps.
    detail = " · ".join(
        row["headline"] for row in blockers[:3] if row.get("headline")
    )

    return [
        Block(
            block="verdict",
            payload={"word": word, "tone": _TONE[tone], "count": count, "detail": detail},
        ),
        Block(block="kpis", payload={"tiles": _tiles(set_results, currency)}),
        Block(block="reconciled", payload=_reconciled(tie_outs, currency)),
        Block(block="records", payload=_records(settle, blockers, warnings, set_results)),
        Block(block="action", payload=_action(blockers, warnings)),
        Block(
            block="downloads",
            payload={
                "files": (
                    [{"id": "tie_out", "label": "Tie-out", "format": "csv"}]
                    if figures.get("rows")
                    else []
                )
            },
        ),
    ]


def _action(blockers: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> dict[str, Any]:
    """**Close period ✓** — danger tier, DISABLED with its reason, ledger's act.

    ⚠ **THREE THINGS ARE TRUE AT ONCE HERE AND EACH IS A RULE:**

    * **`tier` IS `danger`** (B14 rule 6). Closing a period is an irreversible
      commit; reopening one is `System Admin` only and is a separate act.
    * **`enabled: false` CARRIES ITS REASON**, and `ActionPayload` is a
      discriminated union so `tsc` refuses a disabled control without one. The
      execution plan's `K2` row says ABSENT and is wrong — see this module's
      docstring, and `DEF-RBS-4360`.
    * **THIS RUNBOOK DOES NOT PERFORM IT** (`BR-RBS-030`, CONFIRMED 2026-09-06,
      PO verbatim *"1736 - always a person"*). The block declares a button;
      `apps.ledger.close.close_period` performs it, with a person's name on it.
      A Check holds no ports at all, so there is no path from here to that write
      even by mistake.

    ⚠ **A WARNING DOES NOT DISABLE IT.** A warning is something we could not
    check, not something we found wrong, and `BR-LED-018` forbids a hard
    lockout: the close still happens and demands a reason. Blocking on a warning
    would make an unreadable bank statement stop a month that balances.
    """
    if blockers:
        # ⚠ **IT COUNTS BLOCKERS AND IT USES THE TABLE'S OWN WORD FOR THEM.**
        # `RB-109`'s illustrative copy is *"3 items open"*, and in its example
        # all three settle rows are blockers so the two readings coincide. They
        # do not coincide on real books: the seeded utility's August has SIX
        # rows on the list and FOUR that actually stop a close, and a button
        # saying *"4 items open"* over a table of six is a mismatch a finance
        # user would stop and try to resolve. `Blocker` is the pill the table
        # already draws, so the button and the rows use one word.
        #
        # ⚠ **AND A WARNING MUST NOT DISABLE THIS, WHICH IS WHY THE COUNT IS
        # NOT `len(settle)`.** Two of the six are permanent stated absences —
        # nothing records an adjustment's approver (`OQ-RBS-1739`), and no bank
        # statement covers the window. Counting them would leave **Close period
        # ✓** disabled on every tenant for ever: a check incapable of passing,
        # which is hard-won law 7's third shape.
        #
        # B14 rule 33 — a FACT is six words. This is three.
        reason = f"{len(blockers)} blocker{'s' if len(blockers) != 1 else ''} open."
        return {
            "label": "Close period ✓",
            "tier": "danger",
            "enabled": False,
            "reason": reason,
        }
    return {"label": "Close period ✓", "tier": "danger", "enabled": True}


def _tiles(set_results: dict[str, Any], currency: str) -> list[dict[str, Any]]:
    """`RBS-006-R9` region 3 — four tiles, and a money tile carries its basis."""
    receivables = (set_results.get(STEP_RECEIVABLES) or {}).get("checked") or {}
    revenue_tax = (set_results.get(STEP_REVENUE_TAX) or {}).get("checked") or {}
    unapplied = (set_results.get(STEP_UNAPPLIED) or {}).get("checked") or {}

    def _money_tile(tile_id: str, label: str, amount: Any) -> dict[str, Any]:
        return {
            "id": tile_id,
            "label": label,
            "value": {
                "kind": "money",
                "amount": "—" if amount is None else money2(amount),
                "currency": currency,
            },
        }

    return [
        _money_tile("receivables", "Receivables difference", receivables.get("drift")),
        _money_tile(
            "revenue",
            "Revenue difference",
            # Hard rule 5 — an entry is a balanced pair, so the revenue
            # difference is debits less credits and is 0.00 on a sound book.
            money4(revenue_tax.get("revenue_debits") or 0)
            - money4(revenue_tax.get("revenue_credits") or 0),
        ),
        _money_tile("tax", "Tax difference", revenue_tax.get("drift")),
        _money_tile("unapplied", "Unapplied cash", unapplied.get("total")),
    ]


def _reconciled(tie_outs: dict[str, Any], currency: str) -> dict[str, Any]:
    """Region 5–6 — **Billed · In the books · Difference**, with a Ties mark.

    ⚠ **THE TWO COLUMN HEADINGS ARE B14 RULE 34's RATIFIED PAIR.** *"One pair of
    words for held here and in the books — **Recorded** and **In the books**,
    everywhere, in all eleven catalogues"* (`CR-060` C11, ratified 2026-09-02).
    `RBS-006-R9`'s build sheet writes *Billed* for the first column, which is
    the same idea in this table's own words and is what the sheet's acceptance
    check asks for; the rule's pair is what a translator sees, and both are
    carried so neither is lost.

    ⚠ **A TIE IS A MARK, NOT AN ABSENCE** — `tiesLabel` and a pill, never an
    empty difference cell, because a blank cell reads as *nobody checked*.
    """
    rows = []
    for row in tie_outs.get("rows") or ():
        drift = row["drift"]
        rows.append(
            {
                "id": row["subledger"],
                "cells": {
                    "what": {"kind": "text", "text": _words(row["subledger"])},
                    "billed": {
                        "kind": "money",
                        "amount": "—" if row["register"] is None else money2(row["register"]),
                        "currency": row["currency"] or currency,
                    },
                    "books": {
                        "kind": "money",
                        "amount": "—" if row["gl"] is None else money2(row["gl"]),
                        "currency": row["currency"] or currency,
                    },
                    "difference": (
                        {"kind": "pill", "label": "Ties", "tone": "success"}
                        if row["state"] == "agreed"
                        else {
                            "kind": "money",
                            "amount": "—" if drift is None else money2(drift),
                            "currency": row["currency"] or currency,
                        }
                    ),
                },
                "meta": {"state": row["state"]},
            }
        )
    return {
        "heading": "Tie-out",
        "columns": [
            {"key": "what", "label": ""},
            {"key": "billed", "label": "Recorded", "numeric": True},
            {"key": "books", "label": "In the books", "numeric": True},
            {"key": "difference", "label": "Difference", "numeric": True},
        ],
        "rows": rows,
        "tiesLabel": "Ties",
    }


def _words(subledger: str) -> str:
    """`accounts_receivable` → `Receivables`. B14 rules 31 and 32.

    A designation is our word for a slot in the chart; a finance user reads
    theirs. Rule 33 caps a LABEL at three words and every one of these is one.
    """
    return {
        "accounts_receivable": "Receivables",
        "deposit_liability": "Deposits held",
        "tax_payable": "Tax",
        "cost_of_service": "Supplier cost",
    }.get(subledger, subledger.replace("_", " ").capitalize())


def _records(
    settle: list[dict[str, Any]],
    blockers: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    set_results: dict[str, Any],
) -> dict[str, Any]:
    """Region 7–8 — **To settle**, each row linking to the screen that fixes it."""
    return {
        "columns": [
            {"key": "item", "label": "Item"},
            {"key": "detail", "label": "Detail"},
            {"key": "weight", "label": "Weight"},
            {"key": "fix", "label": "Fix"},
        ],
        "rows": [
            {
                "id": str(index),
                "cells": {
                    "item": {"kind": "text", "text": row["item"]},
                    "detail": {"kind": "text", "text": row["detail"]},
                    "weight": {
                        "kind": "pill",
                        "label": "Blocker" if row["weight"] == BLOCKER else "Warning",
                        "tone": "danger" if row["weight"] == BLOCKER else "warning",
                    },
                    "fix": {"kind": "link", "label": row["fix_label"], "to": row["fix_route"]},
                },
                "meta": {"decided_by_rule": row["decided_by_rule"], "step": row["key"]},
            }
            for index, row in enumerate(settle, start=1)
        ],
        "total": len(settle),
        "chips": [
            {"id": "all", "label": "All", "count": len(settle)},
            {"id": "blockers", "label": "Blockers", "count": len(blockers)},
            {"id": "warnings", "label": "Warnings", "count": len(warnings)},
        ],
        "empty": {
            "title": "The books balance.",
            "helper": "Nothing is waiting on anybody.",
        },
        # ⚠ CARRIED, NOT DRAWN — what each step LOOKED AT. An empty period and a
        # balanced one produce different numbers here (hard-won law 7).
        "checked": {
            key: (set_results.get(key) or {}).get("checked", {}) for key in STEP_LABELS
        },
    }


# ── the pinned set ────────────────────────────────────────────────────────


def resolve(ctx):
    """The period this run covers — the word `all`, resolved HERE at run start.

    `BR-RBS-042` clause 1 — store the word, resolve it at run start, never
    expand it to a list at configure time. A utility that saved *all* in
    September and posts into October gets October on its next run with nothing
    to reconfigure.

    ⚠ **THE LATEST POSTED MONTH IS THE DEFAULT, NOT EVERY MONTH.** `RB-109`'s
    scope row is *"Period · August 2026 · value, not editable on this screen"* —
    one period, and its output is *either balanced or the exact list of what is
    not*. Nine steps over twelve months would produce twelve verdicts and one
    screen with no way to say which month is being closed. Runbook 36 walks
    every month because a journal FILE legitimately spans them; a close does
    not.
    """
    months = ledger_seam.posted_months()
    if not months:
        return []
    asked = (ctx.params or {}).get("period")
    chosen = months[-1]
    if isinstance(asked, str) and asked.strip():
        chosen = next(
            (pair for pair in months if f"{pair[0].year:04d}-{pair[0].month:02d}" == asked.strip()),
            months[-1],
        )
    first, last = chosen
    return [
        SubjectRef(
            subject_type="period",
            subject_id=f"{first.isoformat()}:{last.isoformat()}",
            label=f"{first.year:04d}-{first.month:02d}",
        )
    ]


def _refuse_a_tax_tolerance(definition: RunbookDefinition) -> None:
    """`BR-RBS-029` — **the tax tolerance is `$0.00` and CANNOT be raised.**

    ⚠ **REFUSED AT CONSTRUCTION, WHICH IS THE ONLY PLACE IT CAN BE.** This runs
    during the import `AppConfig.ready()` performs, so a parameter added here
    stops the process from starting and names itself. A run-time check would
    mean a runbook with a raised tax tolerance existing in memory on a live
    schedule, and a finance user closing a month over an unremitted difference —
    which is the same shape as `BR-RBS-002`'s *constructed without a writer*
    rather than *refused at write time*, and refused here for the same reason.

    The message names what to do instead, because the next lane will meet it
    while trying to make a real tenant's month close.
    """
    for parameter in definition.parameters:
        if "tax" in parameter.name and "toler" in parameter.name:
            raise RunbookContractError(
                f"runbook {definition.key!r} declares parameter {parameter.name!r}. "
                "BR-RBS-029: the month-end tie-out tolerance for TAX is $0.0000 and cannot be "
                "raised — tax is remitted to an authority and there is no 'we'll fix it next "
                "month'. A tax difference is settled by posting the correction, never by "
                "widening the check that found it."
            )


RUNBOOK = RunbookDefinition(
    key="month_end",
    name="Books tie-out",
    kind=models.KIND_CHECK,
    category="finance",
    subject_type="period",
    unit_of_work="accounting period",
    triggers=(models.TRIGGER_MANUAL, models.TRIGGER_SCHEDULE),
    tags=("Billing", "Payments"),
    parameters=(
        Parameter(
            name="period",
            type=PARAM_WINDOW,
            label="Period",
            required=True,
            # ⚠ THE WORD, NEVER A LIST (`BR-RBS-042` clause 1). Its DOMAIN is
            # `ledger_seam.posted_months()` — tenant-resolved, clause 2 — and it
            # is read when the run starts, in `resolve()` above.
            # ⚠ **`multi` AND `domain` ADDED 2026-09-07 BY THE WAVE `R′` PAYMENTS
            # LANE — `DEF-4364`, AND IT IS A ONE-LINE UNBLOCK RATHER THAN A
            # DESIGN CHANGE.** Wave `T` landed `Parameter._check_domain` the same
            # day, and its fourth refusal is *the word `all` on an input that
            # takes one value*: `all` is a RULE and is only meaningful where
            # several values are (`BR-RBS-042` clause 1). This parameter defaulted
            # to `ALL` and declared neither, so the refusal fired at CONSTRUCTION
            # — during the import `AppConfig.ready()` performs — and **`django
            # .setup()` itself died on the branch tip**: every management command,
            # every test run and every `runserver`.
            #
            # **Why these two values and not a different repair.** This file's own
            # comment three lines up already says what it intends — *its DOMAIN is
            # `ledger_seam.posted_months()`, tenant-resolved, clause 2* — so
            # `domain=DOMAIN_PERIOD` writes down the declaration the prose already
            # made, and `multi=True` is exactly what wave `T`'s rule asks of an
            # input whose default is `all`. **Nothing about what this runbook DOES
            # changes**: `resolve()` above still reads `params["period"]`, still
            # treats any non-`all` string as one month, and still resolves `all`
            # at run start against `posted_months()`.
            #
            # ⚠ **IT IS RECORDED HERE RATHER THAN RAISED AS A QUESTION** (law 13:
            # a judgment recorded with its reasoning is the deliverable). It
            # reverses no signed statement, moves no ❄️ frozen figure and needs no
            # fact only the Product Owner holds — and the branch could not start
            # while it was open. If wave `K` meant a single month with no `all`
            # at all, the repair is to drop the default instead; that is a
            # smaller change than this one and `DEF-4364` names both.
            #
            # ⚠ **WAVE `K` HAS NOW ANSWERED THE QUESTION THAT COMMENT LEAVES
            # OPEN, AND IT TOOK THE SMALLER REPAIR THE COMMENT ITSELF NAMES:
            # this runbook means A SINGLE MONTH AND NO `all` AT ALL, so the
            # DEFAULT IS DROPPED and `multi` stays False.** `BR-RBS-042` clause 1
            # gives a tenant *one value, several, or ALL*; a close is answerable
            # for exactly one month. `RB-109`'s scope row is *"Period · August
            # 2026 · value, not editable on this screen"*, and its output is
            # *either balanced or the exact list of what is not* — nine steps
            # over twelve months would produce twelve verdicts under one banner
            # with no way to say which month is being closed. Runbook 36 walks
            # every month because a journal FILE legitimately spans them; a
            # close does not.
            #
            # **ABSENT MEANS THE LATEST POSTED MONTH, DECIDED IN `resolve()`.** A
            # default here would be a hardcoded month, which is the one thing
            # clause 2 forbids: the domain is tenant-resolved and read at run
            # start. `DEF-4364` named both repairs and left the choice to the
            # wave that owns the runbook; this is that choice.
            domain=DOMAIN_PERIOD,
        ),
        Parameter(
            name="unapplied_allowed",
            type=PARAM_MONEY,
            label="Unapplied cash allowed",
            # ⚠ A STRING, NEVER A FLOAT — this lives in `runbook_versions.
            # definition`, which is `jsonb`, and no column type would catch one
            # (hard rule 2). `Parameter.__post_init__` refuses a float.
            default="0.00",
        ),
        Parameter(
            name="bank_rec_must_be_complete",
            type=PARAM_TOGGLE,
            label="Bank rec must be complete",
            default=True,
        ),
        # ⚠ THERE IS NO TAX-TOLERANCE PARAMETER AND THERE CANNOT BE ONE —
        # `BR-RBS-029`, refused at construction by `_refuse_a_tax_tolerance`
        # below. The absence is deliberate and is asserted by the test suite, so
        # a lane adding one for a tenant that "just needs a cent" meets a RED
        # test that names the rule rather than a review comment.
    ),
    resolve=resolve,
    report=report,
    steps=(
        Step(key=STEP_RUNS, label=STEP_LABELS[STEP_RUNS], mode=MODE_SET, run=step_runs),
        # ⚠ THE ONE PER-RECORD STEP. One period is one savepoint and one record
        # row (hard-won law 14), and `TC-RBS-17` counts the eight set steps
        # against this one.
        Step(
            key=STEP_FIGURES,
            label=STEP_LABELS[STEP_FIGURES],
            mode=MODE_PER_RECORD,
            run=step_figures,
        ),
        Step(
            key=STEP_UNAPPLIED,
            label=STEP_LABELS[STEP_UNAPPLIED],
            mode=MODE_SET,
            run=step_unapplied,
        ),
        Step(
            key=STEP_RECEIVABLES,
            label=STEP_LABELS[STEP_RECEIVABLES],
            mode=MODE_SET,
            run=step_receivables,
        ),
        Step(
            key=STEP_REVENUE_TAX,
            label=STEP_LABELS[STEP_REVENUE_TAX],
            mode=MODE_SET,
            run=step_revenue_tax,
        ),
        Step(key=STEP_BANK, label=STEP_LABELS[STEP_BANK], mode=MODE_SET, run=step_bank),
        Step(
            key=STEP_ADJUSTMENTS,
            label=STEP_LABELS[STEP_ADJUSTMENTS],
            mode=MODE_SET,
            run=step_adjustments,
        ),
        Step(
            key=STEP_DEPOSITS, label=STEP_LABELS[STEP_DEPOSITS], mode=MODE_SET, run=step_deposits
        ),
        Step(
            key=STEP_EXPORTS, label=STEP_LABELS[STEP_EXPORTS], mode=MODE_SET, run=step_exports
        ),
    ),
)

# ⚠ RUN AT IMPORT, WHICH IS THE POINT. `AppConfig.ready()` imports this module,
# so a tax tolerance added to the declaration above stops the process from
# starting and names itself — see `_refuse_a_tax_tolerance`.
_refuse_a_tax_tolerance(RUNBOOK)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-009 (EP-RBS-03; RB-109; RBS-004-R9 / RBS-006-R9 build sheets; BR-RBS-029 · BR-RBS-030; OQ-RBS-1736 CLOSED 2026-09-06 — PO verbatim "1736 - always a person")
# generated: 2026-09-07 by the CR-075 wave K build lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint of its own — the run routes are wave D's; Close period is the LEDGER's POST /finance/periods/close) E=n/a(no screen: RBS-006 renders it from the twelve blocks, RB-020) F✔ G✔ H=n/a(no 🔒 path: this composes no idempotency key, touches no rating math and posts no ledger line — it READS)
# gates: pytest tests/test_us_rbs_009_month_end.py · tests/test_us_rbs_015_conformance.py · G115 (the import census) · G6 (no float on money)
# exceptions: (1) the TAX row this runbook reads is known wrong from the second posted period onward — `DEF-LED-4356`, filed with its figures and NAMED on the finding rather than corrected here · (2) step 7's approver half is a STATED ABSENCE: nothing records an approver against an adjustment (`OQ-RBS-1739`) · (3) **Close period ✓** is DISABLED WITH ITS REASON and not absent — the execution plan's K2 row and EP-RBS-03 line 281 say absent and are wrong, `DEF-RBS-4360` · (4) step 9 reports export readiness and refuses nothing: `BR-LED-017` already guards `create_export_batch`, and two rules that can disagree is worse than one
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
