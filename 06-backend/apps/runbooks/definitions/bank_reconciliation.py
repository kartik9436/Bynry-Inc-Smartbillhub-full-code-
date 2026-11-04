# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-026 (EP-RBS-05) — CR-075 wave P: runbook 14, *Bank
#           reconciliation* — six steps over the statement a person imported,
#           four read and one write, and the sixth is the ENGINE's.
# Rules:    BR-RBS-004 (an Action always produces a PLAN first) · BR-RBS-002 (a
#           Check is constructed with no writer — this is an Action and holds
#           ONE named port) · BR-RBS-005 / BR-RBS-018 (a money-bearing action
#           carries a SECOND approval, matching the plan as it stands) ·
#           BR-RBS-009 (scope resolved ONCE and pinned) · BR-RBS-010 (every
#           record states the rule that decided it, in words a clerk can read) ·
#           BR-RBS-011 (a failure names its fix route) · BR-RBS-019 (the
#           declared unit of work) · BR-RBS-020 (the report is composed at close
#           and frozen) · BR-RBS-021 (twelve blocks) · BR-RBS-022 (a write is a
#           named port; work items are the ENGINE's) · BR-RBS-023 (a step
#           declares its mode) · BR-RBS-027 (a stopped run reads *Never reached*
#           on every later step) · BR-RBS-039 (every foreign read through a seam
#           this module owns) · BR-PAY-019 (the tenant's own match tolerance,
#           read from Settings and never a constant) · CLAUDE.md hard rule 2 ·
#           hard rule 5 (only the ledger posting service writes journal lines) ·
#           hard-won law 14 · B14 rules 31, 32 and 34
# Tests:    06-backend/tests/test_us_rbs_026_bank_reconciliation.py ·
#           06-backend/tests/test_rbs_money_runbooks_pg.py (PostgreSQL only)
# Impacts:  apps/runbooks/definitions/__init__.py (the one line that registers
#           it) · apps/runbooks/seams/payments_seam.py ·
#           apps/runbooks/seams/integrations_seam.py ·
#           04-docs/05-modules/17-runbooks/11-catalogue/RB-114-bank-reconciliation.md
# ───────────────────────────────────────────────────────
"""Runbook 14 — **Bank reconciliation**.

Runbook 10's twin, one step further from the customer. Cash application matches
payments to accounts; **this matches the bank to our own deposit batches**, and
lists the lines it cannot place **beside the batch they are nearest to and the
difference between them** — the two columns that turn an hour of squinting into
a decision.

⚠ **IT IS AN ACTION AND IT HOLDS ONE PORT, WHICH IS A JUDGMENT THIS LANE MADE
AND WOULD RATHER BE CORRECTED ON THAN LEAVE UNSAID.** The lane's briefing
described runbook 14 as a **Check** — *"it produces a tie-out; do not give it a
writer"* — and four places in this repository say otherwise: `RB-114`'s own card
(*Kind: Action*, *Ports it holds: `record_match`*), `12-the-contract.md` §8's
coverage table, `boundary.py` (*"`record_match` is drawn on runbook 14"*), and
`10-execution-plan.md` §1.1, which verified card by card on 2026-09-06 that all
four phase-3 runbooks read `Kind: Action` and moved the whole acting half into
the foundation because of it. **The card is the acceptance check, so the card
wins and the disagreement is written here** rather than resolved silently.
**It is one line to reverse** (`kind=` and `ports=`), and nothing is written
either way while `record_match` has no writer bound.

WHAT THE PORT IS ACTUALLY FOR, WHICH IS NOT WHAT IT FIRST LOOKS LIKE
---------------------------------------------------------------------
`payments.reconciliation.import_bank_statement` already auto-matches on import,
and it is deliberately strict: *"one-to-one and unambiguous or nothing"*, inside
the tenant's own amount tolerance (default **0.00**) and date tolerance. So most
lines are linked before this runbook ever sees them.

**What is left is exactly what this runbook is for.** Its own date window is a
parameter (the card's ± 2 days) and can be wider than the tenant's auto-match
setting, so it finds pairings the strict rule left alone — and where it finds
**exactly one** candidate it plans a match and a second person approves it. A
line with two candidates is left for a human, for `auto_match`'s own reason.

WHO STARTS IT, AND "NO CONNECTION" AS AN ANSWER
------------------------------------------------
`RB-114`'s trigger row reads ⚡ `batch.landed`. **A person imports the statement**
— PO ruling 2026-09-06 — and `batch.landed` is emitted by nothing (`CR-069`), so
this declares **manual and schedule**, both of which wait on nothing.

Step 1 asks where the work comes from, and there are two doors: an **accounting**
connection, and a statement somebody imported. When both are shut the run
**STOPS** (`RUN_STATUS_STOPPED`) — PO ruling the same day, verbatim: *"in absence
of API conenctions you will not find anything and you can stop the job saying APi
or conenct not available; that is a valid case and state for us"*. One red chain
cell names what is missing and five cells honestly read *Never reached*
(`BR-RBS-027`).

THE FOUR PLACES THIS DIVERGES FROM `RB-114` AND ITS FRAME, EACH STAMPED
------------------------------------------------------------------------
1. **Step 6 does not write, and the card marks it `writes`.** *"Raise the rest
   as work items"* is an **ENGINE act** (`BR-RBS-022`); `raise_work_item` is
   refused BY NAME as a port precisely so a Check can populate the work list
   while holding no writer. The runbook returns the findings and the engine
   upserts them by fingerprint when the run closes, so thirty daily sweeps over
   one unexplained line are one item ageing rather than thirty rows. **The
   engine's upsert is `CR-075` wave C's and is not built yet**, so today those
   findings reach a person on this screen and nowhere else — said out loud
   rather than left to be discovered.
2. **The bank-fee tile carries its money in `detail`, not folded into the
   label.** The frame draws *1 — Bank fee · $12.00*. `KpiTile` has a `detail`
   slot and a money value typed into a LABEL is a string: it loses its CHAR(3)
   currency and its two-decimal rule (hard rule 2), which is a money defect
   wearing a formatting costume.
3. **The chain is drawn only when the run STOPPED.** The frame has three regions
   and no chain, because it draws a run that finished. A stopped run is a state
   the frame does not cover, and the chain is the only block that can say *this
   step never ran*.
4. **The KPI strip and the table say *To record* while nothing is recorded.** A
   tile reading **15 Matched** over a run that recorded nothing is the most
   dangerous sentence this screen could print. `KpisPayload.tiles[].label` is
   server-supplied, so the honest word costs nothing and the frame's word
   returns the moment a writer is bound and a second person approves.

WHAT COUNTS AS A FEE, WHICH THE CARD ASSERTS AND NEVER DEFINES
----------------------------------------------------------------
*"A bank charge is not an unmatched deposit"* — `RB-114`'s guard, with no rule
under it. **This lane's rule, recorded so a wrong one is cheap to reverse: a
statement line whose amount is NEGATIVE is money leaving the account and is a fee
or an adjustment, never an unmatched deposit; and a line a person has already
explained under a fee reason (`bank_fee`, `processor_fee`) is one too, whatever
its sign.** Both go to the tile and neither goes to the unmatched table. The
reason codes are `payments`' own seeded vocabulary and are read as VALUES across
the seam.

WHAT WOULD MAKE THIS RUNBOOK REPORT WRONGLY, ANSWERED IN WRITING
-----------------------------------------------------------------
A tie-out that cannot tell *nothing to reconcile* from *everything reconciles*
is worse than no tie-out. So every step reports what it LOOKED AT beside what it
found, the KPI strip carries the line count the statement actually held, and a
statement with no lines produces an empty-state sentence rather than five green
zeroes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from apps.runbooks import models
from apps.runbooks.boundary import PortNotBound
from apps.runbooks.contract import (
    MODE_PER_RECORD,
    MODE_SET,
    PARAM_DAYS,
    PARAM_ENUM,
    PARAM_REF_OBJECT,
    PARAM_REF_SETTING,
    PARAM_TOGGLE,
    Block,
    Parameter,
    RunbookDefinition,
    Step,
    SubjectRef,
)
from apps.runbooks.definitions import _money_gate
from apps.runbooks.seams import integrations_seam, payments_seam

KEY = "bank_reconciliation"

#: The two accounting manifests, verified against
#: `06-backend/apps/integrations/manifests/` on 2026-09-06 and named as VALUES:
#: a manifest key crossing the seam is data, and importing
#: `apps.integrations.manifests` is what `G115` refuses (`BR-RBS-039`).
# ⚠ `gl_partner` BECAME FIVE NAMED ERPs in `CR-110-BRC04` (blueprint p162:
# *"Replaced by five named ERPs"*), so the one key it contributed here is
# now five. Nothing about what this runbook DOES changed — a finance system
# reading from us is the same relationship under a vendor's own name.
ACCOUNTING_PROVIDER_KEYS = (
    "accounting_file",
    "erp_aclarian",
    "erp_workday",
    "erp_sap",
    "erp_infor",
    "erp_msgp",
)

#: `payments`' own seeded difference reasons that mean *the bank was paid*.
#: Values, not an import — `SEED_DIFFERENCE_REASONS` is another module's
#: constant and the VALUE crosses the seam, never the name.
FEE_REASON_CODES = ("bank_fee", "processor_fee")

#: What `bankrec_read.statement_review` calls each line's state. Read as values
#: for the same reason; the vocabulary is `payments`' and is documented in its
#: own docstring — `auto` · `matched_off_by` · `needs_a_look` ·
#: `not_in_our_system` · `set_matched` · `explained`.
STATE_AUTO = "auto"
STATE_MATCHED_OFF_BY = "matched_off_by"
STATE_NEEDS_A_LOOK = "needs_a_look"
STATE_NOT_IN_OUR_SYSTEM = "not_in_our_system"
STATE_SET_MATCHED = "set_matched"
STATE_EXPLAINED = "explained"

# ── the outcomes one bank line can reach ──────────────────────────────────

OUTCOME_ALREADY_MATCHED = "already_matched"
OUTCOME_RECORDED = "recorded"
OUTCOME_PLANNED = "planned"
OUTCOME_NEEDS_A_PERSON = "needs_a_person"
OUTCOME_FEE = "fee"
OUTCOME_SKIPPED = "skipped"

# ── the steps, in the card's own order ────────────────────────────────────

STEP_SOURCE = "gather_statement_lines"
STEP_BATCHES = "gather_open_deposit_batches"
STEP_MATCH = "match_by_amount_and_reference"
STEP_FEES = "separate_fees_and_adjustments"
STEP_RECORD = "record_the_matches"
STEP_REST = "raise_the_rest"

STEP_LABELS = {
    STEP_SOURCE: "Gather statement lines",
    STEP_BATCHES: "Gather open deposit batches",
    STEP_MATCH: "Match by amount and reference",
    STEP_FEES: "Separate fees and adjustments",
    STEP_RECORD: "Record the matches",
    STEP_REST: "Raise the rest",
}

# ── fix routes ────────────────────────────────────────────────────────────
#
# ⚠ **EVERY ONE IS A PATH THIS PRODUCT ACTUALLY MOUNTS, VERIFIED AGAINST
# `07-frontend/src/App.tsx` ON 2026-09-06** — `finance/deposits` is `S37`,
# `finance/deposits/import` is `S38` and `finance/deposits/statement` is the
# reconciliation statement. A fix route that resolves to nothing is a dead
# button over a live finding, and nothing in the backend suite can see it.
FIX_DEPOSITS = "finance/deposits"
FIX_STATEMENT_IMPORT = "finance/deposits/import"
FIX_STATEMENT = "finance/deposits/statement"

ZERO = Decimal("0")


@dataclass(frozen=True)
class Line:
    """One statement line and what this run decided about it.

    ⚠ **NO FIELD HERE CARRIES A DATABASE ID AS A VISIBLE VALUE** (B14 rule 31).
    `line_id` and `batch_id` are handles the engine and the port need; what a
    clerk reads is the bank's own reference and the batch's CODE.
    """

    line_id: str
    posted_on: str | None
    reference: str | None
    amount: Decimal | None
    currency: str
    batch_id: str | None
    batch_label: str
    batch_amount: Decimal | None
    difference: Decimal | None
    outcome: str
    cause: str
    decided_by_rule: str
    fix_route: str
    fix_label: str

    def __post_init__(self) -> None:
        if not self.cause.strip():
            raise ValueError("a bank line with no likely cause tells a clerk nothing")
        if not self.fix_route.strip():
            raise ValueError(
                f"bank line {self.reference!r} names no fix route. BR-RBS-011: a failure names "
                "its fix route, and a failure with no route is a defect in the runbook."
            )

    def as_row(self) -> dict[str, Any]:
        return {
            "line_id": self.line_id,
            "posted_on": self.posted_on,
            "reference": self.reference,
            "amount": None if self.amount is None else str(self.amount),
            "currency": self.currency,
            "batch_id": self.batch_id,
            "batch_label": self.batch_label,
            "batch_amount": None if self.batch_amount is None else str(self.batch_amount),
            "difference": None if self.difference is None else str(self.difference),
            "outcome": self.outcome,
            "cause": self.cause,
            "decided_by_rule": self.decided_by_rule,
            "fix_route": self.fix_route,
            "fix_label": self.fix_label,
        }


@dataclass
class _StepResult:
    reached: bool = True
    stop: dict[str, Any] | None = None
    plan: list[dict[str, Any]] = field(default_factory=list)
    checked: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "reached": self.reached,
            "plan": list(self.plan),
            "checked": dict(self.checked),
        }
        if self.stop is not None:
            out["stop"] = dict(self.stop)
        return out


# ── helpers ───────────────────────────────────────────────────────────────


def _money(raw: Any) -> Decimal | None:
    """A stored money string as a `Decimal`, or `None`. **Never `float(...)`.**"""
    if raw in (None, ""):
        return None
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return None


def _day(raw: Any) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(str(raw))
    except ValueError:
        return None


def _stopped(ctx) -> dict[str, Any] | None:
    first = ctx.set_results.get(STEP_SOURCE) or {}
    stop = first.get("stop")
    return dict(stop) if stop else None


def _never_reached(stop: dict[str, Any]) -> dict[str, Any]:
    return _StepResult(reached=False, checked={"never_reached_because": stop["headline"]}).as_dict()


def _statement(ctx) -> dict[str, Any] | None:
    """The statement this run is about — the declared one, or the most recent.

    ⚠ **READ ONCE PER STEP AND NEVER CACHED ACROSS STEPS BY IDENTITY.**
    `statement_review` is recomputed from the PERSISTED link every time, so two
    reads inside one run can legitimately differ if a clerk ties a line by hand
    mid-run. `BR-RBS-009` pins the SCOPE — which lines this run is about — and
    the executor's fingerprint is what proves that set did not move; it does not
    freeze the world the lines live in, and pretending otherwise would be a
    guarantee this code cannot keep (hard-won law 1).
    """
    chosen = ctx.params.get("statement")
    if chosen:
        return payments_seam.statement_review(chosen)
    recent = payments_seam.statement_imports(limit=1)
    if not recent:
        return None
    return payments_seam.statement_review(recent[0].get("id"))


def _plan(ctx) -> list[dict[str, Any]]:
    for key in (STEP_FEES, STEP_MATCH):
        result = ctx.set_results.get(key) or {}
        if result.get("reached") and result.get("plan"):
            return list(result["plan"])
    return []


# ── step 1 · the statement, or the reason there is none ───────────────────


def step_gather_statement_lines(ctx, subjects) -> dict[str, Any]:
    """1 · From the bank connection; **this only reads them** (the card's words).

    Two doors, exactly as runbook 10 has: an accounting connection, and a
    statement a person imported. When both are shut the run stops with a
    sentence naming both absences — *"no connection"* alone would send a
    bookkeeper to Settings when what they needed was to import the file.
    """
    connections = integrations_seam.live_connections(ACCOUNTING_PROVIDER_KEYS)
    working = [one for one in connections if one.get("enabled") and one.get("status") == "working"]
    statement = _statement(ctx)
    rows = list((statement or {}).get("rows") or [])
    head = (statement or {}).get("statement") or {}

    checked: dict[str, Any] = {
        "accounting_connections_looked_for": len(ACCOUNTING_PROVIDER_KEYS),
        "accounting_connections_found": len(connections),
        "accounting_connections_working": len(working),
        "connection_names": [one.get("display_name") or one.get("key") for one in working],
        "statement_imported": statement is not None,
        "bank_account": head.get("bank_account_name"),
        "period_start": head.get("period_start"),
        "period_end": head.get("period_end"),
        "lines_on_the_statement": len(rows),
    }

    if statement is None and not working:
        offline = [one for one in connections if not one.get("enabled")]
        detail = (
            "An accounting connection is set up and switched off."
            if offline
            else "No accounting connection is set up."
        )
        return _StepResult(
            stop={
                "headline": "Nothing to reconcile.",
                "detail": (
                    f"{detail} No bank statement has been imported either, so there are no "
                    "lines to tie out. Import the statement, or connect an accounting system."
                ),
                "fix_route": FIX_STATEMENT_IMPORT,
                "fix_label": "Import a statement",
            },
            checked=checked,
        ).as_dict()

    if statement is None:
        return _StepResult(
            stop={
                "headline": "No statement has been imported yet.",
                "detail": (
                    f"{', '.join(str(one) for one in checked['connection_names'])} is connected "
                    "and no bank statement has been imported for this run. Import the "
                    "statement, or start this again when one arrives."
                ),
                "fix_route": FIX_STATEMENT_IMPORT,
                "fix_label": "Import a statement",
            },
            checked=checked,
        ).as_dict()

    return _StepResult(checked=checked).as_dict()


# ── step 2 · our own open batches ─────────────────────────────────────────


def step_gather_open_deposit_batches(ctx, subjects) -> dict[str, Any]:
    """2 · Ours, not yet matched.

    `statement_review` already serves them — the candidate batches a human picks
    from when the exact rule could not make the pairing — so this step counts
    and reports rather than asking `payments` a second question. **An empty list
    is an honest answer and it is named**: a statement with lines and no open
    batches of ours is a real state, and it is a very different sentence from
    *"everything ties"*.
    """
    stop = _stopped(ctx)
    if stop:
        return _never_reached(stop)
    statement = _statement(ctx) or {}
    batches = list(statement.get("open_batches") or [])
    total = sum((_money(one.get("recorded_total")) or ZERO for one in batches), ZERO)
    return _StepResult(
        checked={
            "open_batches": len(batches),
            "open_batch_value": str(total),
            "batch_codes": [one.get("code") for one in batches],
        }
    ).as_dict()


# ── step 3 · the match ────────────────────────────────────────────────────


def _nearest(line_amount: Decimal | None, posted_on: date | None, batches, window: int):
    """The open batch this line is NEAREST to — by money first, then by days.

    ⚠ **NEAREST IS NOT MATCHED, AND THE TWO WORDS MUST NEVER BLUR.** This is the
    column that turns an hour of squinting into a decision: *a $35.95 gap against
    a lockbox batch is almost always a late item*, and the row says so. It is
    offered to a person, never acted on — a candidate outside the tenant's own
    auto-match tolerance is exactly the exception `BR-PAY-019` leaves to a human.

    Money first because a bank posts a batch on the day it feels like and never
    changes the amount, so the amount is the stronger signal. Ties broken by the
    smaller date gap, then by the batch code, so the answer is stable across two
    runs over the same data.
    """
    if line_amount is None:
        return None
    scored = []
    for batch in batches:
        amount = _money(batch.get("recorded_total"))
        deposited = _day(batch.get("deposited_on"))
        if amount is None:
            continue
        days = (
            abs((posted_on - deposited).days)
            if posted_on is not None and deposited is not None
            else None
        )
        if days is not None and days > window:
            continue
        scored.append((abs(line_amount - amount), days if days is not None else 10**6,
                       str(batch.get("code") or ""), batch))
    if not scored:
        return None
    scored.sort(key=lambda row: (row[0], row[1], row[2]))
    return scored[0][3]


def _cause(difference: Decimal | None, batch: dict[str, Any] | None) -> tuple[str, str]:
    """The sentence a clerk reads, and the rule that produced it.

    ⚠ **THE SENTENCES ARE THIS LANE's AND THE CARD ASSERTS THEM WITHOUT A
    RULE.** `RBS-006-R14` draws *"Bank added a late item"*, *"No batch — a
    direct deposit?"* and *"Half of a kiosk batch"*, which are three examples
    rather than a vocabulary. The rules under them are recorded here so a wrong
    one is cheap to reverse: **more money at the bank than in the batch means
    the bank added something; less means the batch was split or is short; no
    candidate at all means it is probably not ours.** Every one ends in a
    question or a hedge where it is a guess, because it is.
    """
    if batch is None:
        return (
            "No batch — a direct deposit?",
            "A line with no candidate batch is not ours until somebody says it is",
        )
    if difference is None:
        return ("A batch of ours is close.", "Nearest is offered to a person, never acted on")
    if difference > ZERO:
        return (
            "The bank added a late item.",
            "More at the bank than in the batch means something arrived after the cut",
        )
    if difference < ZERO:
        return (
            "Part of a batch — was it split?",
            "Less at the bank than in the batch means the deposit was split or is short",
        )
    return ("Ties exactly.", "An exact tie inside the window is a match a person approves")


def step_match_by_amount_and_reference(ctx, subjects) -> dict[str, Any]:
    """3 · Inside tolerance and the date window.

    The whole plan is built here. Lines `payments` has already linked keep their
    link and are counted as matched; the rest are offered their nearest batch,
    and where **exactly one** candidate ties EXACTLY inside the window the line
    is planned for recording.

    ⚠ **A BATCH IS CLAIMED ONCE.** A batch two lines could both claim is
    ambiguous and both are left for a human — `auto_match`'s own rule, applied
    to this runbook's wider window rather than reinvented with a different
    answer.
    """
    stop = _stopped(ctx)
    if stop:
        return _never_reached(stop)
    statement = _statement(ctx) or {}
    rows = list(statement.get("rows") or [])
    batches = list(statement.get("open_batches") or [])
    window = int(ctx.params.get("date_window") or 2)
    currency = str(statement.get("currency") or "")

    # Which batches could be claimed by more than one line — computed BEFORE
    # anything is planned, because a claim made in row order would give the
    # batch to whichever line the bank happened to print first.
    claims: dict[str, int] = {}
    nearest_by_line: dict[str, dict[str, Any] | None] = {}
    for row in rows:
        if row.get("state") not in (STATE_NEEDS_A_LOOK, STATE_NOT_IN_OUR_SYSTEM):
            continue
        near = _nearest(_money(row.get("amount")), _day(row.get("posted_on")), batches, window)
        nearest_by_line[str(row.get("bank_line_id"))] = near
        if near is not None:
            claims[str(near.get("id"))] = claims.get(str(near.get("id")), 0) + 1

    plan: list[Line] = []
    for row in rows:
        state = str(row.get("state") or "")
        line_id = str(row.get("bank_line_id"))
        amount = _money(row.get("amount"))
        posted_on = row.get("posted_on")
        reference = row.get("reference")

        if state in (STATE_AUTO, STATE_SET_MATCHED):
            plan.append(
                Line(
                    line_id=line_id,
                    posted_on=posted_on,
                    reference=reference,
                    amount=amount,
                    currency=currency,
                    batch_id=row.get("batch_id"),
                    batch_label=str(row.get("batch_code") or "A set of batches"),
                    batch_amount=_money(row.get("recorded_total")),
                    difference=ZERO,
                    outcome=OUTCOME_ALREADY_MATCHED,
                    cause="Ties exactly.",
                    decided_by_rule="Already tied by the exact rule when the statement landed",
                    fix_route=FIX_DEPOSITS,
                    fix_label="Open deposits →",
                )
            )
            continue

        if state == STATE_MATCHED_OFF_BY:
            difference = _money(row.get("difference"))
            cause, rule = _cause(difference, {"id": row.get("batch_id")})
            plan.append(
                Line(
                    line_id=line_id,
                    posted_on=posted_on,
                    reference=reference,
                    amount=amount,
                    currency=currency,
                    batch_id=row.get("batch_id"),
                    batch_label=str(row.get("batch_code") or "—"),
                    batch_amount=_money(row.get("recorded_total")),
                    difference=difference,
                    outcome=OUTCOME_NEEDS_A_PERSON,
                    cause=cause,
                    decided_by_rule=rule,
                    fix_route=FIX_DEPOSITS,
                    fix_label="Split and match →",
                )
            )
            continue

        near = nearest_by_line.get(line_id)
        batch_amount = None if near is None else _money(near.get("recorded_total"))
        difference = (
            amount
            if (near is None and amount is not None)
            else (
                None
                if (amount is None or batch_amount is None)
                else amount - batch_amount
            )
        )
        contested = near is not None and claims.get(str(near.get("id")), 0) > 1
        ties = difference == ZERO and near is not None and not contested

        if ties:
            outcome, cause, rule, label = (
                OUTCOME_PLANNED,
                "Ties exactly.",
                "An exact tie inside the window is a match a person approves",
                "Open deposits →",
            )
        elif contested:
            outcome, cause, rule, label = (
                OUTCOME_NEEDS_A_PERSON,
                "Two batches could be this line.",
                "A batch two lines could claim is left for a person",
                "Split and match →",
            )
        else:
            cause, rule = _cause(difference if near is not None else None, near)
            outcome = OUTCOME_NEEDS_A_PERSON
            label = "Record deposit →" if near is None else "Investigate →"

        plan.append(
            Line(
                line_id=line_id,
                posted_on=posted_on,
                reference=reference,
                amount=amount,
                currency=currency,
                batch_id=None if near is None else str(near.get("id")),
                batch_label="—" if near is None else str(near.get("code") or "—"),
                batch_amount=batch_amount,
                difference=difference,
                outcome=outcome,
                cause=cause,
                decided_by_rule=rule,
                fix_route=FIX_DEPOSITS if near is not None else FIX_STATEMENT,
                fix_label=label,
            )
        )

    return _StepResult(
        plan=[one.as_row() for one in plan],
        checked={
            "lines_examined": len(rows),
            "already_tied": len([one for one in plan if one.outcome == OUTCOME_ALREADY_MATCHED]),
            "planned_to_record": len([one for one in plan if one.outcome == OUTCOME_PLANNED]),
            "left_for_a_person": len([one for one in plan if one.outcome == OUTCOME_NEEDS_A_PERSON]),
            "date_window_days": window,
        },
    ).as_dict()


# ── step 4 · fees and adjustments ─────────────────────────────────────────


def step_separate_fees_and_adjustments(ctx, subjects) -> dict[str, Any]:
    """4 · **A bank charge is not an unmatched deposit** — it is the bank being paid.

    The rule this lane wrote for the card's assertion is in the module docstring
    and is repeated in one line here because it is the thing a reader will want:
    **a negative line is money leaving, and a line already explained under a fee
    reason is a fee whatever its sign.** Both leave the unmatched table and land
    on a tile.
    """
    stop = _stopped(ctx)
    if stop:
        return _never_reached(stop)
    statement = _statement(ctx) or {}
    explained = {
        str(row.get("bank_line_id")): str(row.get("reason_code") or "")
        for row in (statement.get("rows") or [])
        if row.get("state") == STATE_EXPLAINED
    }

    fees = ZERO
    count = 0
    out: list[dict[str, Any]] = []
    for row in _plan(ctx):
        amount = _money(row.get("amount"))
        reason = explained.get(row["line_id"], "")
        is_fee = (amount is not None and amount < ZERO) or reason in FEE_REASON_CODES
        if not is_fee:
            out.append(row)
            continue
        count += 1
        if amount is not None:
            fees += amount
        row = dict(row)
        row["outcome"] = OUTCOME_FEE
        row["cause"] = "The bank being paid, not an unmatched deposit."
        row["decided_by_rule"] = "A charge is separated from the unmatched deposits"
        out.append(row)

    return _StepResult(
        plan=out,
        checked={
            "fees_and_adjustments": count,
            # ⚠ THE SIGN IS KEPT. `difference_report` records the same posture:
            # *"a report that added a −147.50 fee to a +12.00 interest credit as
            # 159.50 would describe a difference nobody had."* The tile shows
            # the magnitude; the stored figure keeps its sign.
            "fee_value": str(fees),
            "explained_lines": len(explained),
        },
    ).as_dict()


# ── step 5 · record the matches ───────────────────────────────────────────


def step_record_the_matches(ctx, subject) -> dict[str, Any]:
    """5 · Through the payments service, one per line (`BR-RBS-022`).

    ⚠ **THE RUNBOOK WRITES NO `bank_lines` ROW AND POSTS NO JOURNAL LINE.**
    `record_match` is a named port into `payments`' own
    `reconciliation.match_bank_line`, and hard rule 5 keeps journal lines with
    the ledger posting service whatever happens here.

    ⚠ **PER-RECORD, SO EACH LINE RUNS INSIDE ITS OWN SAVEPOINT** — the executor
    opens a nested `transaction.atomic()`. On PostgreSQL that is the ONLY thing
    that lets the run continue after one refused row, and the in-memory SQLite
    suite cannot see the difference (hard-won law 14).
    """
    if _stopped(ctx):
        return {
            "outcome": OUTCOME_SKIPPED,
            "reason": "The run stopped before this step.",
            "decided_by_rule": "A required step failing makes every later step Never reached",
        }
    by_id = {one["line_id"]: one for one in _plan(ctx)}
    row = by_id.get(str(subject.subject_id))
    if row is None:
        return {"outcome": OUTCOME_SKIPPED, "reason": "This line is not in the plan."}
    if row["outcome"] != OUTCOME_PLANNED:
        return {
            "outcome": row["outcome"],
            "reason": row["cause"],
            "decided_by_rule": row["decided_by_rule"],
            "fix_route": row["fix_route"],
            "data": {"batch": row["batch_label"], "amount": row["amount"]},
        }

    planned = len([one for one in by_id.values() if one["outcome"] == OUTCOME_PLANNED])
    approval = _money_gate.second_approval(ctx, planned=planned)
    if not approval["approved"]:
        return {
            "outcome": OUTCOME_PLANNED,
            "reason": approval["reason"],
            "decided_by_rule": "A money-bearing action carries a second approval",
            "fix_route": FIX_DEPOSITS,
            "data": {"batch": row["batch_label"], "amount": row["amount"]},
        }

    try:
        ctx.port("record_match").call(
            bank_line_id=row["line_id"],
            batch_id=row["batch_id"],
            amount=row["amount"],
            currency=row["currency"],
        )
    except PortNotBound as refusal:
        # The port is ALWAYS called and its own refusal is the outcome — see
        # `cash_application`'s matching comment and `BR-RBS-003`. Raised before
        # any SQL, so no transaction is poisoned.
        return {
            "outcome": OUTCOME_PLANNED,
            "reason": "Ready to record. Nothing is written yet.",
            "decided_by_rule": str(refusal),
            "fix_route": FIX_DEPOSITS,
            "data": {"batch": row["batch_label"], "amount": row["amount"]},
        }
    return {
        "outcome": OUTCOME_RECORDED,
        "reason": "Matched to the batch and recorded.",
        "decided_by_rule": "An exact tie inside the window is a match a person approves",
        "fix_route": FIX_DEPOSITS,
        "data": {"batch": row["batch_label"], "amount": row["amount"]},
    }


def step_raise_the_rest(ctx, subjects) -> dict[str, Any]:
    """6 · With the nearest batch and the difference — **and it writes nothing**.

    The card marks this step `writes`. Raising a work item is an **ENGINE act**
    (`BR-RBS-022`); `raise_work_item` is refused BY NAME as a port, which is the
    only thing that lets a runbook populate the work list while holding no
    writer for it. This step returns the findings and the engine upserts them by
    fingerprint at close, so thirty daily sweeps over one unexplained line are
    one item ageing rather than thirty rows (`BR-RBS-017`).

    ⚠ **THE ENGINE'S UPSERT IS `CR-075` WAVE C's AND IS NOT BUILT.** So today
    these findings reach a person on this screen and NOWHERE ELSE. Said out loud
    here, in the report's own `checked` block and in the catalogue card, because
    a runbook that claims to raise work items and does not is hard-won law 1
    exactly.
    """
    stop = _stopped(ctx)
    if stop:
        return _never_reached(stop)
    plan = _plan(ctx)
    rest = [one for one in plan if one["outcome"] == OUTCOME_NEEDS_A_PERSON]
    return _StepResult(
        plan=plan,
        checked={
            "left_for_a_person": len(rest),
            "work_items_raised": 0,
            "work_item_queue_state": (
                "The engine's work-item upsert is not built yet (CR-075 wave C), so these "
                "reach a person on this screen only."
            ),
        },
    ).as_dict()


# ── the report ────────────────────────────────────────────────────────────


def _plan_from_view(view) -> list[dict[str, Any]]:
    for key in (STEP_REST, STEP_FEES, STEP_MATCH):
        result = view.set_results.get(key) or {}
        if result.get("reached") and result.get("plan"):
            return list(result["plan"])
    return []


def _chain(stop: dict[str, Any]) -> Block:
    cells = []
    for index, key in enumerate(STEP_LABELS, start=1):
        first = index == 1
        cells.append(
            {
                "id": key,
                "position": index,
                "label": STEP_LABELS[key],
                "state": "bad" if first else "notReached",
                "note": stop["headline"] if first else "Never reached",
            }
        )
    return Block(block="chain", payload={"label": "The run stopped at step 1.", "cells": cells})


def _line_row(index: int, row: dict[str, Any]) -> dict[str, Any]:
    posted_on = row.get("posted_on") or ""
    reference = row.get("reference")
    currency = row.get("currency") or "USD"
    label = f"{posted_on} · {reference}" if reference else (posted_on or f"Line {index}")

    def money(value):
        return (
            {"kind": "money", "amount": str(value), "currency": currency}
            if value is not None
            else {"kind": "text", "text": "—"}
        )

    return {
        "id": f"line-{index}",
        "cells": {
            "line": {"kind": "text", "text": label},
            "bank_amount": money(row.get("amount")),
            "batch": {"kind": "text", "text": row.get("batch_label") or "—"},
            "batch_amount": money(row.get("batch_amount")),
            "difference": money(row.get("difference")),
            "cause": {"kind": "text", "text": row["cause"]},
            "fix": {"kind": "link", "label": row["fix_label"], "to": row["fix_route"]},
        },
        # Carried, never drawn — the renderer walks `columns`. B14 rule 32 keeps
        # a rule out of clerk-facing copy and the result file needs it.
        "meta": {"decided_by_rule": row["decided_by_rule"], "outcome": row["outcome"]},
    }


def report(view) -> list[Block]:
    """Composed from records and counts at CLOSE, then frozen (`BR-RBS-020`).

    * **stopped** — `Verdict` · `Sentence` · `Chain` · `Records` (empty). No KPI
      strip: five tiles of zero over a run that examined nothing reads exactly
      like a clean month, which is the failure hard-won law 7 is about.
    * **finished** — `Verdict` · `KPIs` · `Records` · `Downloads`, which is
      `RB-114`'s own block list plus the verdict the header consumes.
    """
    stop = (view.set_results.get(STEP_SOURCE) or {}).get("stop")
    if stop:
        return [
            Block(
                block="verdict",
                payload={
                    "word": "Stopped",
                    "tone": "warning",
                    "count": stop["headline"],
                    "detail": stop["detail"],
                },
            ),
            Block(
                block="sentence",
                payload={"tone": "muted", "label": "What to do", "text": stop["detail"]},
            ),
            _chain(stop),
            Block(
                block="records",
                payload={
                    "columns": _records_columns(),
                    "rows": [],
                    "total": 0,
                    "empty": {"title": stop["headline"], "helper": stop["detail"]},
                },
            ),
        ]

    plan = _plan_from_view(view)
    currency = next((str(one["currency"]) for one in plan if one.get("currency")), "USD")
    recorded = [one for one in plan if one["outcome"] == OUTCOME_RECORDED]
    already = [one for one in plan if one["outcome"] == OUTCOME_ALREADY_MATCHED]
    planned = [one for one in plan if one["outcome"] == OUTCOME_PLANNED]
    unmatched = [one for one in plan if one["outcome"] == OUTCOME_NEEDS_A_PERSON]
    fees = [one for one in plan if one["outcome"] == OUTCOME_FEE]

    acted = bool(recorded)
    matched = already + (recorded if acted else planned)
    word = "Matched" if acted or not planned else "To record"
    matched_value = sum((_money(one.get("amount")) or ZERO for one in matched), ZERO)
    unmatched_value = sum((_money(one.get("amount")) or ZERO for one in unmatched), ZERO)
    fee_value = sum((_money(one.get("amount")) or ZERO for one in fees), ZERO)

    return [
        Block(
            block="verdict",
            payload={
                "word": word,
                "tone": "success" if not unmatched else "warning",
                "count": f"{len(matched)} matched. {len(unmatched)} need you.",
                "detail": (
                    f"{len(plan)} lines on the statement."
                    if acted or not planned
                    else f"{len(planned)} are ready to record and wait for a second approval."
                ),
            },
        ),
        Block(
            block="kpis",
            payload={
                "tiles": [
                    {
                        "id": "matched",
                        "label": word,
                        "value": {"kind": "text", "text": str(len(matched))},
                        "detail": None if acted or not planned else "Waiting for a second approval",
                    },
                    {
                        "id": "matched_value",
                        "label": f"{word} value",
                        "value": {
                            "kind": "money",
                            "amount": str(matched_value),
                            "currency": currency,
                        },
                        # `BR-REP-001`: a cash-side figure reads the CLEARING
                        # date, and this is money that arrived at the bank.
                        # Stated rather than left to the renderer's fallback,
                        # which was a hardcoded "posting" for every money tile
                        # in the product (`DEF-RBS-4350`) — wrong here in the
                        # other direction from the test bill.
                        "basis": "clearing",
                    },
                    {
                        "id": "unmatched",
                        "label": "Unmatched",
                        "value": {"kind": "text", "text": str(len(unmatched))},
                    },
                    {
                        "id": "unmatched_value",
                        "label": "Unmatched value",
                        "value": {
                            "kind": "money",
                            "amount": str(unmatched_value),
                            "currency": currency,
                        },
                        # `BR-REP-001`: a cash-side figure reads the CLEARING
                        # date, and this is money that arrived at the bank.
                        # Stated rather than left to the renderer's fallback,
                        # which was a hardcoded "posting" for every money tile
                        # in the product (`DEF-RBS-4350`) — wrong here in the
                        # other direction from the test bill.
                        "basis": "clearing",
                    },
                    {
                        "id": "fees",
                        "label": "Bank fee",
                        "value": {"kind": "text", "text": str(len(fees))},
                        # The money is the DETAIL, not the label — see divergence 2.
                        "detail": f"{fee_value} {currency}",
                    },
                ]
            },
        ),
        Block(
            block="records",
            payload={
                "columns": _records_columns(),
                "rows": [_line_row(index, row) for index, row in enumerate(unmatched, start=1)],
                "total": len(unmatched),
                "chips": [
                    {"id": "all", "label": "All", "count": len(unmatched)},
                    {"id": "fees", "label": "Fees and adjustments", "count": len(fees)},
                ],
                "empty": {
                    "title": "Every line ties.",
                    "helper": (
                        f"All {len(plan)} statement lines are accounted for. "
                        "Nothing is waiting for you."
                    ),
                },
            },
        ),
        Block(
            block="downloads",
            payload={
                "files": [
                    {"id": "matched", "label": word, "format": "csv"},
                    {"id": "unmatched", "label": "Unmatched", "format": "csv"},
                ]
            },
        ),
    ]


def _records_columns() -> list[dict[str, Any]]:
    """`RBS-006-R14` region 3, in THIS order — the sheet's own seven columns."""
    return [
        {"key": "line", "label": "Bank line"},
        {"key": "bank_amount", "label": "Bank amount", "numeric": True},
        {"key": "batch", "label": "Nearest batch"},
        {"key": "batch_amount", "label": "Batch amount", "numeric": True},
        {"key": "difference", "label": "Difference", "numeric": True},
        {"key": "cause", "label": "Likely cause"},
        {"key": "fix", "label": "Fix"},
    ]


# ── the pinned scope ──────────────────────────────────────────────────────


def resolve(ctx):
    """The pinned set: **one subject per statement line** (`BR-RBS-019`).

    ⚠ **AN EMPTY SET IS THE CORRECT ANSWER WHEN THE RUN IS ABOUT TO STOP.** Step
    1 says why in one sentence; a `resolve()` that raised would turn a designed
    outcome into a stack trace.
    """
    statement = _statement(ctx)
    rows = list((statement or {}).get("rows") or [])
    return [
        SubjectRef(
            subject_type="bank_line",
            subject_id=str(row.get("bank_line_id")),
            label=str(row.get("reference") or row.get("posted_on") or "Bank line"),
        )
        for row in rows
    ]


RUNBOOK = RunbookDefinition(
    key=KEY,
    name="Bank reconciliation",
    kind=models.KIND_ACTION,
    category="finance",
    subject_type="bank_line",
    unit_of_work="a bank statement line",
    # MANUAL AND SCHEDULE, not `batch.landed` — a person imports the statement
    # (PO 2026-09-06) and nothing emits the event yet.
    triggers=(models.TRIGGER_MANUAL, models.TRIGGER_SCHEDULE),
    tags=("Payments", "Finance"),
    parameters=(
        Parameter(
            name="statement",
            type=PARAM_REF_OBJECT,
            label="The statement you imported",
        ),
        Parameter(
            name="auto_match_tolerance",
            type=PARAM_REF_SETTING,
            label="Auto-match tolerance",
            # ⚠ READ FROM SETTINGS AND NEVER DUPLICATED (`RBR-03`). `payments`
            # owns this number, its default is 0.00, and a tenant who raises it
            # LOCKS batches (`BR-PAY-004`) — which is why the decision is
            # theirs, made once, on their own screen, with an audit row.
            setting_key="payments.match_amount_tolerance",
        ),
        Parameter(
            name="date_window",
            type=PARAM_DAYS,
            label="Date window",
            default=2,
        ),
        Parameter(
            name="match_on",
            type=PARAM_ENUM,
            label="Match on",
            required=True,
            default="amount_then_batch_reference",
            choices=("amount_then_batch_reference",),
        ),
        Parameter(
            name="record_matches_automatically",
            type=PARAM_TOGGLE,
            label="Record matches automatically",
            default=True,
        ),
        Parameter(
            name="rerun_window",
            type=PARAM_DAYS,
            label="Run the same job again after",
            default=1,
        ),
    ),
    resolve=resolve,
    report=report,
    steps=(
        Step(
            key=STEP_SOURCE,
            label=STEP_LABELS[STEP_SOURCE],
            mode=MODE_SET,
            run=step_gather_statement_lines,
        ),
        Step(
            key=STEP_BATCHES,
            label=STEP_LABELS[STEP_BATCHES],
            mode=MODE_SET,
            run=step_gather_open_deposit_batches,
        ),
        Step(
            key=STEP_MATCH,
            label=STEP_LABELS[STEP_MATCH],
            mode=MODE_SET,
            run=step_match_by_amount_and_reference,
        ),
        Step(
            key=STEP_FEES,
            label=STEP_LABELS[STEP_FEES],
            mode=MODE_SET,
            run=step_separate_fees_and_adjustments,
        ),
        # The ONLY per-record step and the only one that writes: one line, one
        # savepoint, one record row carrying the plan and the outcome together.
        Step(
            key=STEP_RECORD,
            label=STEP_LABELS[STEP_RECORD],
            mode=MODE_PER_RECORD,
            run=step_record_the_matches,
            writes=True,
        ),
        # ⚠ `writes=False`, AND THE CARD MARKS IT `writes`. Raising a work item
        # is an ENGINE act (`BR-RBS-022`) — see the step's own docstring.
        Step(
            key=STEP_REST,
            label=STEP_LABELS[STEP_REST],
            mode=MODE_SET,
            run=step_raise_the_rest,
        ),
    ),
    ports=("record_match",),
)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-026 (EP-RBS-05; CR-075 wave P)
# generated: 2026-09-06 by the CR-075 wave P money-runbooks lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint — every runbooks route is a GET and POST /runbooks/{key}/runs is wave L) E=n/a(no screen — RBS-004 and RBS-006 render any runbook; RB-020) F✔ G✔ H=n/a(no 🔒 path: this composes no idempotency key, touches no rating math and posts no ledger line)
# gates: pytest tests/test_us_rbs_026_bank_reconciliation.py · pytest tests/test_rbs_money_runbooks_pg.py (PostgreSQL) · pytest tests/test_us_rbs_015_conformance.py · G115 · G20
# exceptions: nothing is recorded — `record_match` has no writer until CR-075 task L2, and every run needs a second approval no endpoint can yet grant; step 6 raises no work item because the engine's upsert is wave C's and is not built; the KIND is Action per RB-114's card against a briefing that called it a Check, and the disagreement is written into the module docstring and the card
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
