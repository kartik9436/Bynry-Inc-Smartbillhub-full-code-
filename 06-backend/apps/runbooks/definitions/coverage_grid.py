# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-005 (EP-RBS-02) — CR-075 wave G tasks G2 and G3: runbook 24,
#           the Coverage grid. Screens: RBS-004-R24 (drawn, figure 44) ·
#           RBS-006-R24 (NOT drawn in the source — composed in task G1)
# Rules:    BR-RBS-002 (a Check is CONSTRUCTED with no ports) · BR-RBS-009 (the
#           scope is resolved ONCE and pinned) · BR-RBS-011 (a refusal names its
#           fix route) · BR-RBS-014 (a sample record is never picked) ·
#           BR-RBS-019 · BR-RBS-021 (twelve blocks — the grid is the Records
#           block's DISPLAY MODE and not a thirteenth) · BR-RBS-023 · BR-RBS-039
#           · CLAUDE.md hard rule 1 · hard rule 2 · hard-won law 7 (a check that
#           cannot cover its whole subject prints what it skipped) · hard-won
#           law 14 (a savepoint, not a bare except) · B14 rules 31, 32, 33
# Tests:    06-backend/tests/test_us_rbs_005_coverage_grid.py
# Impacts:  apps/runbooks/definitions/__init__.py (the one registration line) ·
#           apps/runbooks/seams/metering_seam.py (`unit_billing_axes`) ·
#           apps/runbooks/seams/rating_seam.py (`plan_names`) ·
#           apps/runbooks/seams/billing_seam.py (`estimated_services`)
# ───────────────────────────────────────────────────────
"""Runbook 24 — **Coverage grid**: the whole estate priced, as cells.

*"As an implementer at go-live, and as a salesperson before one, I want the
whole estate priced as a grid — so that a utility sees its own accounts produce
correct bills before it commits, and I know which plan is broken rather than
that something is."*

Three steps, all READ:

    1  pick one account per plan, service mix and cycle — a DETERMINISTIC pick
    2  price each one through the real engine — **runbook 23 on each cell**
    3  group by outcome: clean · estimated · refused, with the refusal sentence

It produces a grid of at most 25 cells reading **21 clean · 2 estimated ·
2 refused**, each cell opening that account's own test bill.

═════════════════════════════════════════════════════════════════════════════
STEP 2 IS *RUNBOOK 23*, NOT *WHAT RUNBOOK 23 DOES*
═════════════════════════════════════════════════════════════════════════════
The card's own words are **"Runbook 23 on each cell"**, and this file takes them
literally: each cell **opens, executes and closes a real run of `test_bill`**
through `services.open_run` → `executor.execute` → `services.close_run`, with
`parent_run` set to this run. Three consequences, and each is why it is built
this way rather than by calling the pricing seam directly:

* **The cell's refusal sentence IS runbook 23's.** It is lifted out of the
  child's own frozen `sentence` block, so the words on a red cell and the words
  on the screen that cell opens cannot differ. `TC-RBS-005.4`'s *"must first
  fail on"* column names the alternative by name — *a refusal composed by this
  module; it would not change when the rate did*.
* **The cell has somewhere to open.** `RecordGrid` cannot express a cell without
  a destination (hard-won law 2's 2026-09-05 mirror — the portal's two working
  doors out of eight), so *"each cell opens that account's test bill"* needs a
  test bill that EXISTS. A child run is one. A query string pointing at a setup
  screen that cannot start a run would be a door onto a dead button.
* **There is one implementation of pricing and this is not a second one.**
  Runbook 23 already calls `billing.runs.price_account` — stages 1–5 of the real
  bill run, extracted by wave F so a test bill and a real bill cannot disagree.
  Nothing here prices anything.

⚠ **THE COST, STATED: a grid of 25 writes 25 extra `runbook_runs` rows.** They
carry `parent_run`, which is the column that exists for exactly this and which
wave `I4` uses for `requires`. **Run history (`RBS-008`) does not yet filter on
it**, so a tenant that runs the grid daily sees 25 test-bill rows a day in that
list — recorded here, and filed, rather than left for a reader to discover.

═════════════════════════════════════════════════════════════════════════════
THE PICK, AND WHY IT IS THE WHOLE STORY
═════════════════════════════════════════════════════════════════════════════
`US-RBS-005`: *"If the 25 are re-picked at random, two runs cannot be compared
and 'the grid moved from 21 to 23' is not a measurement."*

So the pick is a **stated function** of three axes — the unit's rate plan, the
services it takes, and the cycles that read it — and of nothing else:

    group key   (plan_id, services, cycles)          — the cell
    group order (plan NAME, services, cycles)        — reading order, by words
    within it   the FIRST account by account number  — the representative

Every input is sorted before it is used and `account_anchors()` already arrives
ordered by `(account_no, id)`, so two runs over an unchanged estate produce the
same 25 accounts in the same order — which is what `runbook_runs
.scope_fingerprint` then digests (`TC-RBS-005.2`).

⚠ **A SAMPLE ACCOUNT IS NEVER PICKED** (`BR-RBS-014`, `TC-RBS-005.3`). The
exclusion is in the PICK, not in the act: this runbook has no act. `is_sample`
lives on the owning row (`BR-TEN-057`) and travels through
`customers_seam.sample_account_ids`, the same read runbook 8's guard uses.

⚠ **AND WHAT IT LEAVES OUT IS SAID OUT LOUD, WHICH IS `TC-RBS-005.5`.** A silent
`LIMIT 25` is hard-won law 7's fifth shape — *reporting zero over a scope it
silently excludes* — so the `sentence` block names, every time: how many cells
the estate has, how many were drawn, how many accounts were excluded as sample
data, and how many were skipped for having no unit to derive a plan from. **A
grid that covered nine cells of forty and said nothing would look exactly like a
grid that covered the whole estate.**

═════════════════════════════════════════════════════════════════════════════
THE JUDGMENTS THIS LANE MADE, WHICH THE DOCUMENTS DID NOT SETTLE
═════════════════════════════════════════════════════════════════════════════
Written where a reader of the CODE meets them, per the Product Owner's standing
instruction — *"if you have questions on Runbook you should ask instead of
assuming"*. Each is a decision, cheap to reverse, and none touches a signed
figure.

**J1 · A MASTER ACCOUNT IS NOT A CELL, AND IT IS COUNTED RATHER THAN DROPPED.**
`BR-CUS-1010` makes a Master Account the owner's account at an ADDRESS: it names
a premises and no unit at all, lawfully. The three axes are the UNIT's, so a
master account has no cell to sit in. It is excluded from the pick and the
sentence says how many were — the difference between an estate this runbook
covered and one it merely walked past.

**J2 · AN UNPLANNED UNIT IS ITS OWN CELL, NOT AN OMISSION.** `BR-MET-100` makes
a unit with no rate plan a state a utility can be in and *"must be COUNTED AND
FINDABLE"*. It groups under a plan of `None`, and the cell reads **refused** the
moment runbook 23 prices it — which is the finding a go-live grid exists to
surface.

**J3 · *ESTIMATED* IS THE GATHER'S OWN FLAG AND NOTHING ELSE.** A cell is amber
when the bill priced completely and at least one of the readings behind it
carries `ServiceReading.estimated` (`BR-MET-029`). ⚠ The card's phrase is
*"estimated or defaulted"* and **the *defaulted* half is not built**: nothing in
`billing.contracts` records that a quantity was DEFAULTED rather than read or
estimated, so a runbook claiming to detect one would be reporting a fact this
product does not hold. Said here rather than silently folded into *clean*.

**J4 · THE PERIOD DEFAULTS TO THE LAST WHOLE CALENDAR MONTH, NOT THE CARD'S
*NEXT CYCLE*.** `RB-124`'s scope row reads *Period: The next cycle*. A period
that has not happened has no reads, so a grid over it would be 25 refusals and
would prove nothing about a utility's data — the exact opposite of what the
go-live artefact is for. The default is therefore runbook 23's own (its judgment
J8), and it is a parameter a clerk can change. **The divergence from the card is
stamped in `08-screen-layouts.md` with this reason.**

**J5 · NO CHIPS.** `RecordsPayload` allows them and `RBS-006-R1` draws them for
runbook 1. On this screen they would be dead UI: `RunResultPage` holds the chip
in state and **nothing filters the frozen report's rows by it**, so pressing
*Refused 2* would change a highlight and no rows. Hard-won law 2 — a control
that does nothing is worse than an absent one.

**J6 · NO `downloads` BLOCK, FOR RUNBOOK 23'S OWN REASON (its J6).** The two
result files stream `runbook_run_records` and nothing writes a record row yet.

⚠ **WHAT WOULD MAKE THIS RUNBOOK PASS WRONGLY, ANSWERED IN WRITING** (hard-won
law 7's second habit). A grid drawn over three accounts of four hundred would
read *3 clean* and look perfect. So every count this file publishes is drawn
beside the estate it was taken from: the KPI strip carries **Cells** as well as
the three outcomes, and the sentence carries the four exclusion counts. An
estate with nothing in it and an estate that is entirely clean produce different
screens, and a reader can tell them apart.
"""

from __future__ import annotations

import calendar
from datetime import date
from typing import Any

from django.db import DatabaseError, transaction

from apps.runbooks import models
from apps.runbooks.contract import (
    MODE_PER_RECORD,
    MODE_SET,
    Finding,
    PARAM_ENUM,
    PARAM_INTEGER,
    PARAM_WINDOW,
    Block,
    Parameter,
    RunbookDefinition,
    Step,
    SubjectRef,
)
from apps.runbooks.contract import RunbookContractError
from apps.runbooks.seams import customers_seam, metering_seam, rating_seam
from core import errors

#: The runbook each cell runs. Named once, here, because it is the only thing
#: this file knows about pricing at all.
CELL_RUNBOOK = "test_bill"

# ── the three steps, by key, and the labels the setup sheet draws ─────────
#
# `RBS-004-R24` region 3 draws these three rows with this copy. The build sheet
# is the acceptance check and these strings are its words, not a paraphrase.
STEP_PICK = "pick"
STEP_PRICE = "price"
STEP_GROUP = "group"

STEP_LABELS: dict[str, str] = {
    STEP_PICK: "Pick one account per plan, service mix and cycle",
    STEP_PRICE: "Price each one through the real engine",
    STEP_GROUP: "Group by outcome",
}

#: The three outcomes, and they are the coverage grid's own words — `RecordGrid`
#: types exactly these three and colours the cell from them. They are an
#: OUTCOME rather than a severity: an estimated bill is not a lesser failure, it
#: is a different fact.
OUTCOME_CLEAN = "clean"
OUTCOME_ESTIMATED = "estimated"
OUTCOME_REFUSED = "refused"
OUTCOMES = (OUTCOME_CLEAN, OUTCOME_ESTIMATED, OUTCOME_REFUSED)

#: The clerk's word for each. No internal code reaches a screen (B14 rule 32).
OUTCOME_WORDS: dict[str, str] = {
    OUTCOME_CLEAN: "Clean",
    OUTCOME_ESTIMATED: "Estimated",
    OUTCOME_REFUSED: "Refused",
}

#: `StatusPill` tones. `good` · `warning` · `bad` are the renderer's vocabulary.
OUTCOME_TONES: dict[str, str] = {
    OUTCOME_CLEAN: "good",
    OUTCOME_ESTIMATED: "warning",
    OUTCOME_REFUSED: "bad",
}

#: Where a clerk goes when the grid itself cannot run. `BR-RBS-011` — a failure
#: names its fix route, and a refusal with nowhere to go is a defect in the
#: runbook. Tenant-relative, resolved by the screen (`DEF-RBS-4329`).
FIX_ADD_THE_TEST_BILL = "runbooks/templates"

#: The default number of cells. `RB-124`'s scope row: *Accounts: 25*.
DEFAULT_CELLS = 25


# ── the pick ──────────────────────────────────────────────────────────────


def _estate(ctx) -> dict[str, Any]:
    """The three axes, read once: accounts, their units' axes, the plan names.

    ⚠ **THIS IS READ TWICE PER RUN — ONCE BY `resolve()` AND ONCE BY STEP 1 —
    AND THAT IS DELIBERATE RATHER THAN AN OVERSIGHT.** `resolve()` must return
    the pinned subjects and cannot hand a census forward; step 1 must publish
    what the pick LEFT OUT and cannot see inside `resolve()`. The alternative
    was a second grouping implementation, which is the one thing worth avoiding
    here. Both calls go through `_plan()` below, which is pure, so the two
    answers can only differ if the estate itself moved between them — and step 1
    says so when it does.
    """
    return {
        "accounts": customers_seam.account_anchors(),
        "samples": customers_seam.sample_account_ids(),
        "axes": metering_seam.unit_billing_axes(),
        "plans": rating_seam.plan_names(),
    }


def _plan(estate: dict[str, Any], *, cells: int) -> dict[str, Any]:
    """The deterministic pick — **pure**, so two calls over one estate agree.

    Returns the chosen representatives in reading order and the census of what
    it left out. Nothing in here reads a clock, a database or a random source.
    """
    samples = estate["samples"]
    axes = estate["axes"]
    plans = estate["plans"]

    groups: dict[tuple, dict[str, Any]] = {}
    excluded_sample = 0
    excluded_no_unit = 0
    excluded_unknown_unit = 0

    for account in estate["accounts"]:
        if str(account["id"]) in samples:
            # `BR-RBS-014` — in the PICK, because this runbook has no act.
            excluded_sample += 1
            continue
        unit_id = account.get("unit_id")
        if not unit_id:
            # Judgment J1 — a master account is anchored to an address and has
            # no unit, so it has no plan, no service mix and no cycle.
            excluded_no_unit += 1
            continue
        unit = axes.get(str(unit_id))
        if unit is None:
            # A unit this tenant cannot see. `resolve_anchors`' own boundary
            # expressed as absence — counted rather than silently dropped.
            excluded_unknown_unit += 1
            continue

        plan_id = unit.get("rate_plan_id")
        services = tuple(unit.get("services") or ())
        cycles = tuple(unit.get("cycles") or ())
        key = (plan_id or "", services, cycles)
        if key in groups:
            continue
        groups[key] = {
            "key": key,
            "plan_id": plan_id,
            "plan_name": plans.get(str(plan_id)) if plan_id else None,
            "services": list(services),
            "cycles": list(cycles),
            "account_id": str(account["id"]),
            "account_no": account.get("account_no") or "",
        }

    ordered = sorted(
        groups.values(),
        # ⚠ **BY WORDS, NOT BY ID.** A uuid order is stable and meaningless; a
        # reader who asks *why is that cell first* deserves an answer, and the
        # plan's NAME is one. A plan with no name sorts last under the empty
        # string, which puts the unplanned cell at the end rather than at the
        # front of a go-live screen.
        key=lambda group: (
            group["plan_name"] or "￿",
            group["services"],
            group["cycles"],
            group["account_no"],
        ),
    )
    drawn = ordered[:cells] if cells > 0 else []
    return {
        "cells": drawn,
        "groups_found": len(ordered),
        "cells_drawn": len(drawn),
        "cells_left_out": max(0, len(ordered) - len(drawn)),
        "excluded_sample": excluded_sample,
        "excluded_no_unit": excluded_no_unit,
        "excluded_unknown_unit": excluded_unknown_unit,
        "accounts_seen": len(estate["accounts"]),
    }


def _cell_limit(ctx) -> int:
    raw = ctx.params.get("accounts", DEFAULT_CELLS)
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return DEFAULT_CELLS


def resolve(ctx):
    """The pinned set: one account per cell, in reading order (`BR-RBS-009`).

    ⚠ **THE SET IS EMPTY WHEN THE TEST BILL IS NOT IN *MY RUNBOOKS*, AND THE
    REPORT SAYS SO IN WORDS.** Every cell of this grid IS a run of runbook 23,
    so without runbook 23 there is nothing to pick a representative FOR. An
    empty scope is a lawful answer (`BR-RBS-042` clause 2 — *an empty domain
    says so*) and the `sentence` block carries the reason and the route.
    """
    if _cell_runbook(ctx) is None:
        return []
    picked = _plan(_estate(ctx), cells=_cell_limit(ctx))
    return [
        SubjectRef(
            subject_type="account",
            subject_id=cell["account_id"],
            # ⚠ B14 rule 31 — the LABEL is what a reader sees and it is never
            # the id. The account NUMBER is the utility's own and is on every
            # screen in the product; it is not a database id.
            label=cell["account_no"],
        )
        for cell in picked["cells"]
    ]


def _cell_runbook(ctx):
    """This tenant's row for runbook 23, or `None`.

    In-module read: `runbooks` owns this table, so there is no seam and no
    foreign import (`BR-RBS-039`, `G115`).
    """
    from apps.runbooks import selectors

    if ctx.tenant_id is None:
        return None
    return selectors.runbook_by_key(ctx.tenant_id, CELL_RUNBOOK)


# ── the three steps ───────────────────────────────────────────────────────


def step_pick(ctx, subjects) -> dict[str, Any]:
    """1 · The pick, and **what it left out** (`TC-RBS-005.5`).

    It re-runs the same pure planner `resolve()` used and publishes the census
    beside it. Where the two disagree — an account created between the two reads
    — `moved` says so rather than leaving a reader to notice that 25 cells were
    pinned and 26 exist.
    """
    picked = _plan(_estate(ctx), cells=_cell_limit(ctx))
    pinned = [subject.subject_id for subject in subjects]
    return {
        **picked,
        "pinned": pinned,
        "moved": [cell["account_id"] for cell in picked["cells"]] != pinned,
        "have_test_bill": _cell_runbook(ctx) is not None,
    }


def step_price(ctx, subjects) -> dict[str, Any]:
    """2 · **Runbook 23 on this cell** — a real child run, its own savepoint.

    ⚠⚠ **THE SAVEPOINT IS NOT THE TIDY OPTION** (hard-won law 14). Each cell
    opens and closes a run, so each cell issues statements; on PostgreSQL one
    refused statement aborts the WHOLE transaction and every later cell is lost
    at COMMIT however carefully the exception is caught. The engine already
    wraps every per-record step in a savepoint (`executor._run_one_record`), and
    this step is per-record for exactly that reason — **registering it as `set`
    would put all 25 cells in one transaction and one bad account would take the
    grid with it.** `config/settings/test.py` is in-memory SQLite, which has no
    aborted-transaction state at all, so the wrong build passes the whole suite
    green.

    ⚠ **IT ACCUMULATES INTO `ctx.set_results` UNDER ITS OWN KEY, WHICH IS HOW
    STEP 3 SEES IT.** The executor writes `ctx.set_results[step.key]` for `set`
    steps only, so a per-record step's key is never overwritten and nothing
    collides. It is the run-scoped channel the context exists to be, used in the
    direction the docstring there does not name — recorded rather than left for
    a reader to work out.
    """
    from apps.runbooks import services
    from apps.runbooks.engine import executor
    from apps.runbooks.registry import registry

    cells = ctx.set_results.setdefault(STEP_PRICE, {"cells": []})["cells"]
    runbook = _cell_runbook(ctx)
    if runbook is None:  # pragma: no cover — resolve() returns nothing first
        return {"outcome": OUTCOME_REFUSED, "reason": "The test bill is not added."}

    definition = registry.get(CELL_RUNBOOK)
    parent = None
    if ctx.run_id is not None:
        parent = models.RunbookRun.objects.filter(pk=ctx.run_id).first()

    params: dict[str, Any] = {
        "account": subjects.subject_id,
        "compare_with": "nothing",
        "show": "every_line_explained",
    }
    window = ctx.params.get("period")
    params["period"] = window if window else _default_period()

    # ⚠ **`open_run` → `execute` → `close_run` RATHER THAN
    # `services.run_to_completion`, FOR ONE REASON: `parent_run`.** That helper
    # takes no parent, and a child run with no link to the run that started it
    # is provenance thrown away — `runbook_runs.parent_run_id` exists for
    # exactly this and wave `I4` uses the same three calls for `requires`.
    #
    # ⚠⚠ **THE REFUSAL IS CAUGHT PER CELL, AND `DEF-RBS-4363` IS WHAT IT COSTS
    # WHEN IT IS NOT.** `open_run` carries two deliberate refusals of its own —
    # a pending template update on runbook 23, and the trust ratchet — and
    # neither is a database error, so the executor's savepoint does not net
    # them. The first real run of this runbook met one on cell 1 and **the
    # whole grid reported nothing at all** rather than 24 cells and one
    # refusal. A Check that cannot survive one bad cell is not a Check over an
    # estate; it is a Check over the first account in it.
    try:
        child = services.open_run(runbook, definition)
        with transaction.atomic():
            result = executor.execute(
                definition, tenant_id=ctx.tenant_id, run_id=child.pk, params=params
            )
        if parent is not None:
            models.RunbookRun.objects.filter(pk=child.pk).update(parent_run=parent)
        services.close_run(child, result)
    except (errors.BizError, errors.ValidationError, RunbookContractError) as refused:
        cell = _the_test_bill_would_not_run(refused, subject=subjects)
        cells.append(cell)
        return {
            "outcome": cell["outcome"],
            "reason": cell["reason"],
            "decided_by_rule": cell["decided_by_rule"],
            "fix_route": cell["fix_route"],
            "data": {"account_no": subjects.label},
        }

    cell = _read_the_child(child, result, subject=subjects)
    cells.append(cell)
    return {
        "outcome": cell["outcome"],
        "reason": cell["reason"],
        "decided_by_rule": cell["decided_by_rule"],
        "fix_route": cell["fix_route"],
        "data": {"run_id": str(child.pk), "account_no": subjects.label},
    }


def _the_test_bill_would_not_run(refused: Exception, *, subject) -> dict[str, Any]:
    """A cell whose CHILD RUN was refused before it could price — `DEF-RBS-4363`.

    ⚠ **IT HAS NO RUN, SO IT HAS NO DOOR, AND `RecordGrid` CANNOT DRAW A CELL
    WITHOUT ONE.** `report()` therefore leaves this cell OUT of the grid and the
    sentence counts it — a cell that opened onto nothing would be the dead door
    this runbook was built to avoid, and a silent omission would be the silent
    truncation `TC-RBS-005.5` forbids. The record row still carries it, so the
    run's own counts say four refused where the grid draws three.

    ⚠ **THE WORDS ARE THE PRODUCT'S, NOT AN EXCEPTION'S `str()`.** `open_run`'s
    refusals are `BizError`s carrying a `message_key`; their English lives in
    eleven catalogues and a `str(exc)` would put `BIZ-STATE` on a screen (B14
    rule 32). So the sentence here says what a clerk can act on and the fix
    route sends them to the runbook that would not start.
    """
    return {
        "account_id": subject.subject_id,
        "account_no": subject.label,
        # No child run: this cell is not drawn on the grid. See the docstring.
        "run_id": "",
        "period_start": None,
        "period_end": None,
        "outcome": OUTCOME_REFUSED,
        "reason": "The test bill would not start.",
        "decided_by_rule": "This account was never priced.",
        "fix_route": f"runbooks/{CELL_RUNBOOK}",
        "fix_label": "Open the Test bill",
    }


def _read_the_child(child, result, *, subject) -> dict[str, Any]:
    """One cell, read out of runbook 23's OWN result — never recomposed.

    The refusal sentence is lifted from the child's frozen `sentence` block, so
    the words on a red cell are byte-for-byte the words on the screen that cell
    opens. That is `TC-RBS-005.4`'s point: *a refusal composed by this module
    would not change when the rate did*.
    """
    from apps.runbooks.definitions import test_bill

    priced_step = result.set_results.get("price") or {}
    priced = priced_step.get("priced")
    refusal = priced_step.get("refusal")
    loaded = result.set_results.get("load") or {}

    row: dict[str, Any] = {
        "account_id": subject.subject_id,
        "account_no": subject.label,
        "run_id": str(child.pk),
        "period_start": loaded.get("period_start"),
        "period_end": loaded.get("period_end"),
        "decided_by_rule": "",
        "fix_route": "",
    }
    if priced is None:
        label, route = test_bill.fix_route(refusal or {})
        row.update(
            {
                "outcome": OUTCOME_REFUSED,
                # The child's own sentence, as a clerk reads it there.
                "reason": _sentence_of(child) or "This account could not be priced.",
                "decided_by_rule": "The bill run refused this account.",
                "fix_route": route,
                "fix_label": label,
            }
        )
        return row

    estimated = list(priced.get("estimated_services") or ())
    if estimated:
        row.update(
            {
                "outcome": OUTCOME_ESTIMATED,
                "reason": _estimated_sentence(estimated),
                "decided_by_rule": "At least one read on this bill is an estimate.",
                # `BR-RBS-011` — an amber cell is a finding too, and a finding
                # a clerk cannot act on is one we should not have shown them.
                "fix_route": "meter-reads",
                "fix_label": "Open Meter Reads",
            }
        )
        return row

    row.update(
        {
            "outcome": OUTCOME_CLEAN,
            "reason": "",
            "decided_by_rule": "Every line priced from a real read.",
            # A clean cell has nothing to fix, so it names no route — which is
            # `BR-RBS-011` honoured rather than breached: the rule is about a
            # FAILURE naming its route.
            "fix_route": "",
            "fix_label": "",
        }
    )
    return row


def step_group(ctx, subjects) -> dict[str, Any]:
    """3 · Group by outcome — clean · estimated · refused, in that order.

    ⚠ **IT GROUPS; IT DOES NOT COUNT A SECOND TIME.** The totals the report
    draws come from `RunResult.counts`, which the ENGINE derives from the record
    rows step 2 produced (`executor._count`). A step that summed its own list
    would be a second answer to *how many cells were clean*, and the two would
    eventually disagree on a run where a cell raised.
    """
    cells = (ctx.set_results.get(STEP_PRICE) or {}).get("cells") or []
    grouped: dict[str, list[dict[str, Any]]] = {outcome: [] for outcome in OUTCOMES}
    for cell in cells:
        grouped.setdefault(cell["outcome"], []).append(cell)
    return {
        "order": list(OUTCOMES),
        "grouped": grouped,
        "words": dict(OUTCOME_WORDS),
    }


# ── the sentences ─────────────────────────────────────────────────────────


def _sentence_of(run) -> str:
    """Runbook 23's own refusal sentence, out of its frozen report."""
    for block in run.report or []:
        if block.get("block") == "sentence":
            return str((block.get("payload") or {}).get("text") or "")
    return ""


def _estimated_sentence(services: list[str]) -> str:
    """Six words or fewer (B14 rule 33), naming what was estimated.

    ⚠ **THE COLON FORM IS WHAT MAKES SIX WORDS REACHABLE**, exactly as runbook
    23 records: two of the eleven service codes are two words (`storm_water`,
    `thermal_heat`), so *"Storm water was estimated this period"* is seven and
    *"Storm water: estimated read."* is four.
    """
    if len(services) == 1:
        return f"{_service_word(services[0])}: estimated read."
    return f"{len(services)} services: estimated reads."


def _service_word(code: Any) -> str:
    """`storm_water` → *Storm water*. No internal code reaches a clerk (rule 32)."""
    text = str(code or "").replace("_", " ").strip()
    return text[:1].upper() + text[1:] if text else "This service"


def _coverage_sentence(picked: dict[str, Any]) -> str:
    """What the grid covered and **what it left out** — `TC-RBS-005.5`.

    One sentence per fact and no rule id (B14 rule 32). The exclusions are named
    only when they are non-zero, because a run over a tidy estate should not
    read like a list of things that went wrong.
    """
    drawn = picked.get("cells_drawn", 0)
    found = picked.get("groups_found", 0)
    parts = [
        f"{drawn} of {found} plan and cycle combinations were priced."
        if drawn != found
        else f"All {found} plan and cycle combinations were priced."
    ]
    left = picked.get("cells_left_out", 0)
    if left:
        parts.append(f"{left} more would not fit in this grid.")
    excluded = []
    if picked.get("excluded_sample"):
        excluded.append(f"{picked['excluded_sample']} sample")
    if picked.get("excluded_no_unit"):
        excluded.append(f"{picked['excluded_no_unit']} without a unit")
    if picked.get("excluded_unknown_unit"):
        excluded.append(f"{picked['excluded_unknown_unit']} on a unit nobody can see")
    if excluded:
        parts.append(f"Left out: {', '.join(excluded)}.")
    return " ".join(parts)


# ── what this run leaves on somebody's desk — CR-075 wave H, US-RBS-006 ───


def findings(view) -> list[Finding]:
    """One work item per cell that did not price cleanly — **per ACCOUNT**.

    ⚠ **PER ACCOUNT AND NOT ONE SUMMARY ROW, WHICH IS A DIVERGENCE FROM
    `RBS-007`'s SAMPLE DATA AND IS INSIDE THAT SHEET'S OWN ALLOWANCE.** The
    build sheet draws *"4 accounts refused pricing · Coverage grid"* as a single
    row; its acceptance line says *"Sample values are illustrative; the words
    around them are not."* A summary row cannot close itself when three of the
    four are fixed, and self-closing is the property `US-RBS-006` is written
    around — so the item is the account, and `J-RBS-2`'s step 7 (add the rate
    block, re-run, **21 → 23**) closes exactly two of them by itself.

    ⚠ **A CLEAN CELL RAISES NOTHING, AND THAT IS WHAT CLOSES YESTERDAY'S ITEM.**
    Absence is the signal: `engine.work_items` resolves every open item this
    runbook raised whose fingerprint this run did not raise.

    ⚠ **THE TITLE IS THE CHILD RUN'S OWN SENTENCE**, so the words on the work
    list, on the grid cell and on the test bill that cell opens are one string.
    """
    cells = (view.set_results.get(STEP_PRICE) or {}).get("cells") or []
    raised: list[Finding] = []
    for cell in cells:
        if cell["outcome"] == OUTCOME_CLEAN:
            continue
        raised.append(
            Finding(
                # The question, never the answer: *did this account price* is
                # one question whichever service refused it this month.
                kind=f"{cell['outcome']}:account",
                title=f"{cell['account_no']} — {cell['reason']}",
                fix_route=cell["fix_route"] or "plans",
                # A refusal stops billing; an estimate does not.
                weight=100 if cell["outcome"] == OUTCOME_REFUSED else 50,
                # B14 rule 31 — the account NUMBER, never its id.
                subject_ref=cell["account_no"],
                subject_type="account",
                subject_id=cell["account_id"],
            )
        )
    return raised


# ── the report — three of the twelve blocks, composed at close ────────────
#
# ⚠ **EVERY PAYLOAD HERE IS THE RENDERER'S SHAPE.** `contract.PAYLOAD_FIELDS`
# is transcribed from `07-frontend/src/features/runbooks/blocks/types.ts` and
# `validate_report` refuses a missing field at close — `DEF-RBS-4352`, where the
# collections ladder shipped a `breakdown` with no `columns` and `RBS-006` drew
# an error boundary instead of 835 notices, with every test on both sides green.


def report(view) -> list[Block]:
    """`kpis` · `records` (**grid mode**) · `sentence`. Three of the twelve.

    ⚠ **THE GRID IS A DISPLAY MODE OF `records` AND NOT A THIRTEENTH BLOCK**
    (`BR-RBS-021`). `RecordsPayload` already declares `display` and `grid`;
    phase 1 built both. *"That is the contract paying for itself: the highest-
    value screen in phase 2 costs a display mode on a component phase 1 already
    built"* — `US-RBS-005`'s own words.
    """
    picked = view.set_results.get(STEP_PICK) or {}
    cells = (view.set_results.get(STEP_PRICE) or {}).get("cells") or []
    grouped = (view.set_results.get(STEP_GROUP) or {}).get("grouped") or {}
    counts = dict(view.counts)

    if not cells:
        return _nothing_to_draw(picked)

    # ⚠ **A CELL WITH NO CHILD RUN HAS NO DOOR AND IS NOT DRAWN** — `DEF-RBS-4363`
    # and hard-won law 2's 2026-09-05 mirror: `RecordGrid` cannot express a cell
    # without a destination, and one pointing at nothing is a dead door on a live
    # screen. It is still COUNTED, by the engine, from its record row — so the
    # KPI strip and the sentence say four where the grid draws three, which is
    # visible rather than silent.
    ordered = [
        cell
        for outcome in OUTCOMES
        for cell in (grouped.get(outcome) or [])
        if cell.get("run_id")
    ]
    return [
        Block(block="kpis", payload={"tiles": _tiles(counts, len(cells))}),
        Block(block="records", payload=_grid(ordered, picked)),
        Block(
            block="sentence",
            payload={
                "tone": "bad" if counts.get(OUTCOME_REFUSED) else "good",
                "label": "Read this aloud",
                "text": _coverage_sentence(picked),
            },
        ),
    ]


def _tiles(counts: dict[str, int], drawn: int) -> list[dict[str, Any]]:
    """Four tiles, and the fourth is the one that stops a false pass.

    Three outcome counts over an estate of three would read *3 clean* and look
    perfect. **Cells** is the denominator that makes the other three mean
    something (hard-won law 7).
    """
    return [
        _tile(OUTCOME_CLEAN, "Clean", counts.get(OUTCOME_CLEAN, 0)),
        _tile(OUTCOME_ESTIMATED, "Estimated", counts.get(OUTCOME_ESTIMATED, 0)),
        _tile(OUTCOME_REFUSED, "Refused", counts.get(OUTCOME_REFUSED, 0)),
        _tile("cells", "Cells", drawn),
    ]


def _tile(tile_id: str, label: str, count: int) -> dict[str, Any]:
    """One KPI tile — and **`value` IS A `ReportValue` OBJECT, NOT A STRING.**

    ⚠⚠ **`DEF-RBS-4375`: THIS STRIP DREW FOUR LABELS AND NO NUMBERS.**
    `KpisPayload.tiles[].value` is the same tagged union every report cell uses
    — `{kind: "text", text: …}` — and a bare `"3"` renders as nothing at all
    while `CLEAN`, `ESTIMATED`, `REFUSED` and `CELLS` sit above four empty
    boxes. **Two checks looked one step short of the number**: `PAYLOAD_FIELDS`
    validates TOP-LEVEL names only, so `tiles` being present is all
    `validate_report` can ask (`DEF-RBS-4352` one level down, a second time);
    and the browser check asserted the tile's LABEL was on the page and never
    its VALUE. **The screenshot is what said so** — read after the walkthrough
    had already reported every check passed.

    ⚠ **NO `basis` FIELD, DELIBERATELY.** `basis` labels a MONEY tile's date
    (`BR-REP-001`, `DEF-RBS-4350`) and every tile here is a COUNT. A count with
    a posting date on it would be the same wrong answer that defect names, in
    the other direction.
    """
    return {
        "id": tile_id,
        "label": label,
        "value": {"kind": "text", "text": str(count)},
    }


def _grid(cells: list[dict[str, Any]], picked: dict[str, Any]) -> dict[str, Any]:
    """The `records` payload in GRID mode — `RecordsPayload`, field for field."""
    rows = []
    state_by_row: dict[str, str] = {}
    for cell in cells:
        row_id = cell["account_id"]
        state_by_row[row_id] = cell["outcome"]
        rows.append(
            {
                "id": row_id,
                "cells": {
                    # B14 rule 31 — the account NUMBER, never the id.
                    "account": {"kind": "text", "text": cell["account_no"]},
                    "outcome": {
                        "kind": "pill",
                        "label": OUTCOME_WORDS.get(cell["outcome"], cell["outcome"]),
                        "tone": OUTCOME_TONES.get(cell["outcome"], "neutral"),
                    },
                    "reason": {"kind": "text", "text": cell["reason"]},
                    # ⚠ TENANT-RELATIVE, resolved by the screen (`DEF-RBS-4329`
                    # and `DEF-RBS-4354` — the same fault one display mode over).
                    "open": {
                        "kind": "link",
                        "label": "Open the test bill",
                        "to": f"runbooks/{CELL_RUNBOOK}/runs/{cell['run_id']}",
                    },
                },
            }
        )
    return {
        "display": "grid",
        "columns": [
            {"key": "account", "label": "Account"},
            {"key": "outcome", "label": "Outcome"},
            {"key": "reason", "label": "Why"},
            {"key": "open", "label": "Test bill"},
        ],
        "rows": rows,
        "total": len(rows),
        "grid": {
            "labelKey": "account",
            "stateByRowId": state_by_row,
            "linkKey": "open",
            "reasonKey": "reason",
        },
        "empty": {
            "title": "Nothing was priced.",
            "helper": "Add accounts with a plan, then run this again.",
        },
    }


def _nothing_to_draw(picked: dict[str, Any]) -> list[Block]:
    """An empty grid still has to say WHY, in words (`BR-RBS-042` clause 2).

    Two different silences reach here and they need different sentences: the
    tenant has not added the test bill, or the estate holds no account this grid
    can group. A single *"nothing to show"* over both is the shape hard-won law
    7 calls a declared blind spot with no number attached.
    """
    if not picked.get("have_test_bill", True):
        text = "Add the Test bill to My runbooks, then run this again."
        route = FIX_ADD_THE_TEST_BILL
        label = "Open the library"
    else:
        text = _coverage_sentence(picked) or "No account could be grouped by plan and cycle."
        route = "accounts"
        label = "Open Accounts"
    return [
        Block(
            block="sentence",
            payload={"tone": "neutral", "label": "Nothing was priced", "text": text},
        ),
        Block(
            block="records",
            payload={
                "columns": [],
                "rows": [],
                "total": 0,
                "empty": {"title": "Nothing was priced.", "helper": f"{label} → /{route}"},
            },
        ),
    ]


# ── small helpers ─────────────────────────────────────────────────────────


def _default_period() -> dict[str, str]:
    """The last WHOLE calendar month — runbook 23's own default (its J8).

    ⚠ It is computed here rather than left to the child, because the grid's own
    `sentence` names the period and a period the parent cannot see is a period
    the screen cannot say. `date.today()` is read ONCE, in one place, and the
    parameter overrides it — a clerk re-taking last quarter's grid passes the
    window (`BR-TEN-043`'s spirit: a run re-taken for last week takes last
    week's answer).
    """
    today = date.today()
    year, month = (today.year - 1, 12) if today.month == 1 else (today.year, today.month - 1)
    return {
        "start": date(year, month, 1).isoformat(),
        "end": date(year, month, calendar.monthrange(year, month)[1]).isoformat(),
    }


def _step(key: str, run, *, mode: str) -> Step:
    """One step, labelled from the table the setup sheet also draws.

    `mode` is passed explicitly on every call because `Step.mode` has no default
    (`BR-RBS-023`) and a helper that supplied one would move the default up one
    layer rather than remove it.
    """
    return Step(key=key, label=STEP_LABELS[key], mode=mode, run=run)


RUNBOOK = RunbookDefinition(
    key="coverage_grid",
    name="Coverage grid",
    kind=models.KIND_CHECK,
    category="billing",
    subject_type="account",
    unit_of_work="account-period",
    # ⚠ MANUAL AND NOTHING ELSE. `RB-124`'s catalogue row C3 says who runs it:
    # *implementation, before go-live*. A schedule over a go-live artefact would
    # be twenty-five test bills a night, for ever, that nobody reads.
    triggers=(models.TRIGGER_MANUAL,),
    tags=("Billing", "Plans & Rates"),
    parameters=(
        # ── region 1, the Scope panel of `RBS-004-R24` ───────────────────
        Parameter(
            name="accounts",
            type=PARAM_INTEGER,
            label="Accounts",
            required=True,
            default=DEFAULT_CELLS,
        ),
        Parameter(
            name="period",
            type=PARAM_WINDOW,
            label="Period",
            required=True,
        ),
        Parameter(
            name="never_include",
            type=PARAM_ENUM,
            label="Never include",
            required=True,
            default="sample",
            # ⚠ ONE CHOICE, AND IT IS A RULE RATHER THAN A PREFERENCE
            # (`BR-RBS-014`). It is drawn so the exclusion is VISIBLE — a guard
            # a clerk cannot see is a guard they will assume is absent.
            choices=("sample",),
        ),
        # ── region 2, the Parameters panel ────────────────────────────────
        Parameter(
            name="cells",
            type=PARAM_ENUM,
            label="Cells",
            required=True,
            default="one_per_plan_and_cycle",
            choices=("one_per_plan_and_cycle",),
        ),
        Parameter(
            name="refusals",
            type=PARAM_ENUM,
            label="Refusals",
            required=True,
            default="open_the_accounts_test_bill",
            choices=("open_the_accounts_test_bill",),
        ),
        Parameter(
            name="repick",
            type=PARAM_ENUM,
            label="Re-pick accounts",
            required=True,
            default="each_run",
            # Both halves are true and neither contradicts the other: the pick
            # is re-taken on every run, and the pick FUNCTION is deterministic,
            # so an unchanged estate produces the same 25 in the same order.
            choices=("each_run",),
        ),
    ),
    resolve=resolve,
    report=report,
    findings=findings,
    steps=(
        _step(STEP_PICK, step_pick, mode=MODE_SET),
        _step(STEP_PRICE, step_price, mode=MODE_PER_RECORD),
        _step(STEP_GROUP, step_group, mode=MODE_SET),
    ),
    # ⚠ **`ports` IS ABSENT AND THAT IS THE RULE, NOT AN OVERSIGHT**
    # (`BR-RBS-002`). A Check is CONSTRUCTED without action ports, so no cell can
    # write an invoice, consume a bill number or touch a ledger line — which is
    # what lets an implementer press Run on a whole estate.
)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-005 (EP-RBS-02; CR-075 wave G tasks G1–G4)
# generated: 2026-09-07 by the CR-075 wave G build lane
# checklist: A✔ B✔ C✔ D=n/a(no new endpoint — wave D's GET routes serve this runbook unchanged) E✔(the Records block's grid display mode, and DEF-RBS-4354's fix to it) F✔ G✔ H=n/a(no 🔒 path: it composes no idempotency key, invents no rating math and posts no ledger line — every cell CALLS runbook 23, which calls the engine)
# gates: pytest tests/test_us_rbs_005_coverage_grid.py · pytest tests/test_us_rbs_015_conformance.py · G115 (the import census) · 10-scripts/render-checks/rbs-g-coverage-grid.mjs
# exceptions: (1) the period defaults to the last whole calendar month where RB-124's scope row says "The next cycle" (judgment J4 — a future period has no reads and would be 25 refusals); (2) no chips, because nothing filters a frozen report by one (J5); (3) no `downloads` block, for runbook 23's own reason (J6); (4) a master account is not a cell and is COUNTED in the sentence (J1)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
