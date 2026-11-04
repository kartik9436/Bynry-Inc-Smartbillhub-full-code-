# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-021 (EP-RBS-05) — CR-075 wave S: runbook 6, *Why did this
#           account not bill?* — seven read steps that STOP at the first
#           failure, for one account or for a whole break list.
# Rules:    BR-RBS-002 (a Check is CONSTRUCTED with no writer) · BR-RBS-009
#           (scope resolved ONCE and pinned) · BR-RBS-010 · BR-RBS-011 (a
#           failure names its fix route) · BR-RBS-019 · BR-RBS-020 · BR-RBS-021
#           · BR-RBS-022 (a work item is the ENGINE's act) · BR-RBS-023 ·
#           BR-RBS-027 (a stopped chain reads *Never reached*) · BR-RBS-035 ·
#           BR-RBS-039 · BR-BIL-037 / BR-BIL-040 (the pipeline's own stage
#           names, and a break carries one) · BR-BIL-053 (the break list) ·
#           BR-CUS-1010 (a master account names a premises and no unit) ·
#           B14 rules 31, 32, 33
# Tests:    06-backend/tests/test_us_rbs_021_why_not_billed.py ·
#           06-backend/tests/test_rbs_check_runbooks_pg.py (PostgreSQL only)
# Impacts:  apps/runbooks/definitions/__init__.py · apps/runbooks/seams/
#           billing_seam.py · apps/runbooks/seams/customers_seam.py ·
#           apps/runbooks/seams/metering_seam.py ·
#           04-docs/05-modules/17-runbooks/11-catalogue/RB-106-why-did-this-account-not-bill.md
# ───────────────────────────────────────────────────────
"""Runbook 6 — **Why did this account not bill?**

A bill run finished and this account produced nothing. `RB-106`'s own sentence
for what the clerk gets: *"Stopped at step 4 — no Sewer read between 18 Aug and
17 Sep. Last billed 20 Aug."*, with **Add a read →** beside it.

⚠ **IT STOPS AT THE FIRST FAILURE BECAUSE A CLERK NEEDS ONE ANSWER, NOT SEVEN.**
That is the card's own guard, and it is what makes the chain readable: one red
cell, the rest **Never reached** (`BR-RBS-027`). A runbook that reported every
problem at once would be correct and useless — the second problem is usually a
consequence of the first.

WHERE THE ANSWER COMES FROM, AND WHY IT IS NOT AN INFERENCE
------------------------------------------------------------
`RB-106`: *"This is runbook 3 run backwards, for one account, after the fact.
Same checks, opposite direction. **Re-price to confirm pushes the account
through the real engine so the sentence shown is the engine's refusal, not an
inference about it** — the same principle as the test bill."*

So there are two sources and they are used for different things:

* **What the RUN recorded** — `bill_run_breaks`, each carrying the pipeline's
  own stage (`resolve-subscription` · `measure-consumption` · `price-usage`,
  `BR-BIL-037`/`BR-BIL-040`). This is history and it is authoritative about what
  happened on the day.
* **What the engine says NOW** — `billing.single.prepare_single_bill` +
  `billing.runs.price_account` through the seam, which is the run's own code and
  not a copy of it (`US-RBS-004`'s whole point). This is the *Re-price to
  confirm* toggle, and it answers *is it still broken*.

⚠ **THE TWO CAN DISAGREE, AND THAT DISAGREEMENT IS A FINDING RATHER THAN A
BUG.** An account that broke on a missing read and has since had one prices
cleanly today; the run's break explains the past and the re-price says the fix
has landed. Both are reported, in those words, because a clerk who has just
added the read needs to know it took.

THE SEVEN STEPS AND THE THREE STAGES — A MAPPING, STATED
---------------------------------------------------------
The card names seven steps; `billing` records three stages. They are not the
same vocabulary and this module does not pretend they are:

    step 3 · A plan in force?          ← stage `resolve-subscription`
    step 4 · A read for every service? ← stage `measure-consumption`
    step 5 · Did pricing refuse?       ← stage `price-usage`

Steps 1, 2, 6 and 7 have no stage because they are not pipeline stages at all:
in scope, held on purpose, the write refused, and did it bill last time.

⚠ **STEP 6 IS THE ONE THIS PRODUCT CANNOT ANSWER, AND IT SAYS SO WITH A
NUMBER.** *"Did the write refuse — a duplicate, a constraint, a number series
exhausted"* asks about a failure INSIDE the drafting transaction. `bill_runs`
records breaks raised by the pipeline's own stages and an invoice that was never
written leaves no row anywhere; there is no `write_refused` reason in
`STAGE_BY_REASON` and no table of failed writes. So step 6 reports what it CAN
see — the account has no invoice on this run and no break naming a stage — and
names that state as *nothing recorded either way*, which is the honest answer
and is not *the write refused*. Hard-won law 7: a declared blind spot with no
number attached is indistinguishable from an empty one.

THE BREAK-LIST VARIANT
------------------------
`RB-106`'s scope panel is headed *Scope one account, or the whole break list*,
and its variant lists all 14 accounts a run left unbilled, grouped by the step
that stopped each. That is the SAME runbook with a wider scope: leave `account`
unset and every account the run broke on is pinned, one record each.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from apps.runbooks import models
from apps.runbooks.contract import (
    MODE_PER_RECORD,
    MODE_SET,
    PARAM_REF_OBJECT,
    PARAM_TOGGLE,
    Block,
    Parameter,
    RunbookDefinition,
    Step,
    SubjectRef,
)
from apps.runbooks.seams import billing_seam, customers_seam, metering_seam

KEY = "why_not_billed"

# ── the seven steps, in the card's own order ──────────────────────────────

STEP_SCOPE = "was_it_in_scope"
STEP_HELD = "was_it_held_on_purpose"
STEP_PLAN = "a_plan_in_force"
STEP_READ = "a_read_for_every_service"
STEP_PRICING = "did_pricing_refuse"
STEP_WRITE = "did_the_write_refuse"
STEP_LAST_TIME = "did_it_bill_last_time"

STEP_LABELS = {
    STEP_SCOPE: "In scope",
    STEP_HELD: "Not held",
    STEP_PLAN: "Plan in force",
    STEP_READ: "A read for every service",
    STEP_PRICING: "Pricing",
    STEP_WRITE: "Write",
    STEP_LAST_TIME: "Last time",
}

#: The pipeline's three stage names (`BR-BIL-037`), mapped onto the card's steps.
#: ⚠ **THE STAGE IS BILLING'S WORD AND THE STEP IS THE CARD'S; NEITHER IS
#: TRANSLATED INTO THE OTHER.** A break says `measure-consumption` because that
#: is the stage that raised it, and this runbook draws it as *step 4* because
#: that is where the card puts it. Writing billing's word on a clerk's screen
#: would be an internal code in clerk-facing copy (B14 rule 32).
STEP_BY_STAGE = {
    "resolve-subscription": STEP_PLAN,
    "measure-consumption": STEP_READ,
    "price-usage": STEP_PRICING,
}

STEP_POSITION = {key: index for index, key in enumerate(STEP_LABELS, start=1)}

# ── fix routes ────────────────────────────────────────────────────────────
#
# Verified against `07-frontend/src/routing/` on 2026-09-07; tenant-relative.
FIX_ACCOUNTS = "accounts"
FIX_READS = "reads"
FIX_PLANS = "plans-rates/plans"
FIX_BILLING = "billing"

#: What a clerk does about a stop at each step — `BR-RBS-011`: a failure names
#: its fix route, and one without a route is a defect in the runbook.
FIX_FOR_STEP = {
    STEP_SCOPE: (FIX_ACCOUNTS, "Open the account →"),
    STEP_HELD: (FIX_ACCOUNTS, "Open the account →"),
    STEP_PLAN: (FIX_PLANS, "Assign a plan →"),
    STEP_READ: (FIX_READS, "Add a read →"),
    STEP_PRICING: (FIX_PLANS, "Open Plans & Rates →"),
    STEP_WRITE: (FIX_BILLING, "Open the run →"),
    STEP_LAST_TIME: (FIX_BILLING, "Open billing →"),
}

#: BILLING'S REASON CODE → WHAT A CLERK READS. `{service}` is filled from the
#: engine's own refusal where the re-price supplied one.
#:
#: ⚠ **THIS MAP EXISTS BECAUSE THE OBVIOUS BUILD BREAKS B14 RULE 32, AND IT DID
#: SO ON THE FIRST REAL RUN.** Title-casing the code produces *"Missing read
#: undecided at calculate."* — the pipeline's internal word, on a clerk's
#: screen, in a sentence they are meant to read to a customer. The break's own
#: `detail` is worse: it is the engine's full sentence and it quotes `BR-BIL-015`
#: by name.
#:
#: ⚠ **AND AN UNMAPPED REASON DOES NOT FALL BACK TO THE CODE.** It falls back to
#: a plain sentence and is COUNTED, so *"3 reasons this runbook has no words
#: for"* is visible on the run rather than three internal codes being read out
#: to customers (hard-won law 7 — the number beside the blind spot).
REASON_WORDS: dict[str, str] = {
    "account_has_no_unit": "This account is not attached to a unit.",
    "unit_has_no_plan": "No plan is assigned to this unit.",
    "plan_not_published": "The plan is not published.",
    "plan_has_no_tariff_for_service": "The plan has no rate for {service}.",
    "tariff_has_no_version_in_force_at_service_date": (
        "No {service} rate is in force for these dates."
    ),
    "tenant_currency_unresolved": "The utility's currency is not set.",
    "no_charge_applies_to_this_customer_type": (
        "No base charge applies to this customer type."
    ),
    "connection_size_unresolved_for_sized_schedule": (
        "The connection size is not recorded, and the rate depends on it."
    ),
    "premises_jurisdiction_unstated": (
        "Nobody has recorded whether this premises is inside the city."
    ),
    "master_coverage_unresolved": "What this master account covers is unclear.",
    "master_coverage_spans_two_plans": "This account's units sit on two plans.",
    "master_coverage_repeats_a_service": "This account covers one service twice.",
    "cut_covers_some_services_and_not_others": (
        "The move-out covers some services and not others."
    ),
    "missing_read_undecided_at_calculate": (
        "No {service} read in this period, and nobody has decided what to do."
    ),
    "missing_read": "No {service} read in this period.",
    "unmetered_asset_count_undetermined": (
        "Nobody has counted the {service} items this bill charges for."
    ),
    "installed_capacity_undetermined": "The installed capacity is not recorded.",
    "metering_has_not_published_reads": "No readings have been published yet.",
    "account_held_by_disputed_read": "A reading on this account is disputed.",
    "unit_service_priced_nowhere": "One of this account's services is priced nowhere.",
    "master_unbilled_units_unpriceable": (
        "Some units under this account cannot be priced."
    ),
    "unbilled_unit_service_state_unreadable": (
        "One unit's services could not be read."
    ),
    "ruled_path_refused": "The rule that governs this account refused it.",
}

#: What an unmapped reason reads as. It says WHERE it stopped and nothing it
#: cannot support — never the code, and never a guess about the cause.
REASON_UNKNOWN = "The run needed something this account does not have."

#: THE CHAIN CELL'S NOTE, WHICH IS A DIFFERENT LENGTH OF SENTENCE.
#: ⚠ **B14 rule 33 caps a refusal at five or six words**, and `Chain.tsx` says so
#: at the `note` field itself. The full reason belongs in the Sentence block,
#: which is prose; a cell that carried it would wrap over three lines and stop
#: being scannable, which is the whole point of a chain.
SHORT_NOTE = {
    "was_it_held_on_purpose": "Held on purpose",
    "a_plan_in_force": "No plan in force",
    "a_read_for_every_service": "Read missing",
    "did_pricing_refuse": "Pricing refused",
    "did_the_write_refuse": "Nothing recorded",
}


OUTCOME_BILLED = "billed"
OUTCOME_STOPPED = "stopped"
OUTCOME_HELD = "held"
OUTCOME_UNEXPLAINED = "unexplained"
OUTCOME_SKIPPED = "skipped"


@dataclass
class _StepResult:
    reached: bool = True
    stop: dict[str, Any] | None = None
    found: dict[str, Any] = field(default_factory=dict)
    checked: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "reached": self.reached,
            "found": dict(self.found),
            "checked": dict(self.checked),
        }
        if self.stop is not None:
            out["stop"] = dict(self.stop)
        return out


def _outcome(ctx) -> dict[str, Any]:
    """The run's own record of what it did, read ONCE and cached.

    Every step reads it, and asking billing seven times would let one account's
    answer change between two questions inside a single run.
    """
    cached = ctx.set_results.get("_outcome")
    if cached is None:
        cached = billing_seam.bill_run_outcome(ctx.params.get("bill_run")) or {}
        ctx.set_results["_outcome"] = cached
    return dict(cached)


def _stopped(ctx) -> dict[str, Any] | None:
    first = ctx.set_results.get(STEP_SCOPE) or {}
    stop = first.get("stop")
    return dict(stop) if stop else None


def _never_reached(stop: dict[str, Any]) -> dict[str, Any]:
    return _StepResult(
        reached=False, checked={"never_reached_because": stop["headline"]}
    ).as_dict()


def _iso(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _window_words(outcome: dict[str, Any]) -> str:
    """*between 18 Aug and 17 Sep* — the card's own phrasing for the period."""
    start, end = _iso(outcome.get("period_start")), _iso(outcome.get("period_end"))
    if start is None or end is None:
        return "in this period"
    return f"between {start.strftime('%-d %b')} and {end.strftime('%-d %b')}"


# ── step 1 · was it in scope? ─────────────────────────────────────────────


def step_was_it_in_scope(ctx, subjects) -> dict[str, Any]:
    """1 · Status, cycle, service dates inside the period.

    ⚠ **THE RUN IS THE SCOPE, AND THIS STEP STOPS THE WHOLE RUNBOOK WHEN THERE
    IS NO RUN TO EXPLAIN.** *"Which run?"* is not a failure of the account; it
    is a run nobody picked, and it reads as a designed stop with a sentence
    rather than as an empty screen (PO ruling 2026-09-06).

    ⚠ **AN ACCOUNT THAT DID BILL IS AN ANSWER TOO.** A clerk who picked the
    wrong account, or the wrong run, must be told *this one billed* rather than
    shown a chain of green cells that quietly explains nothing.
    """
    outcome = _outcome(ctx)
    if not outcome:
        return _StepResult(
            stop={
                "headline": "No bill run to explain.",
                "detail": (
                    "Pick a run from the billing screen — this runbook explains what one "
                    "run did to one account."
                ),
                "fix_route": FIX_BILLING,
                "fix_label": "Open billing",
            },
            checked={"bill_run": None},
        ).as_dict()

    billed = set(outcome.get("billed_account_ids") or [])
    breaks = list(outcome.get("breaks") or [])
    return _StepResult(
        found={"run": outcome},
        checked={
            "run_no": outcome.get("run_no"),
            "run_status": outcome.get("status"),
            "period": f"{outcome.get('period_start')} → {outcome.get('period_end')}",
            "accounts_billed": len(billed),
            "accounts_broken": len({str(one.get("account_id")) for one in breaks}),
            "accounts_excluded": len(outcome.get("exclusions") or []),
            "subjects_pinned": len(subjects),
        },
    ).as_dict()


# ── step 2 · was it held on purpose? ──────────────────────────────────────


def step_was_it_held_on_purpose(ctx, subjects) -> dict[str, Any]:
    """2 · A hold, a dispute, a deliberate exclusion.

    ⚠ **A DELIBERATE EXCLUSION IS NOT A FAULT AND MUST NOT READ AS ONE.**
    Somebody chose it, with a reason code and their name against it, and a
    runbook that reported *"stopped at step 3"* over an account a supervisor
    held would send a clerk to fix something nobody broke.

    A dispute is metering's fact about a UNIT (`BR-MET-133`) and a service-off
    window is customers' fact about an account; both are read through their own
    seams and neither is re-derived here.
    """
    stop = _stopped(ctx)
    if stop:
        return _never_reached(stop)

    outcome = _outcome(ctx)
    excluded = {
        str(one["account_id"]): one for one in (outcome.get("exclusions") or [])
    }
    holds: dict[str, dict[str, Any]] = {}
    disputes = 0
    for subject in subjects:
        account_id = str(subject.subject_id)
        facts = customers_seam.account_facts(account_id) or {}
        unit_id = facts.get("unit_id")
        held: list[str] = []
        if account_id in excluded:
            reason = excluded[account_id].get("reason_code") or "held by a person"
            held.append(f"Held on purpose · {str(reason).replace('_', ' ')}")
        if unit_id and metering_seam.unit_has_dispute_hold(unit_id):
            disputes += 1
            held.append("A reading on this unit is disputed")
        if held:
            holds[account_id] = {"reasons": held}
    return _StepResult(
        found={"holds": holds},
        checked={
            "accounts_looked_at": len(subjects),
            "held_on_purpose": len(excluded),
            "held_by_a_dispute": disputes,
        },
    ).as_dict()


# ── steps 3, 4 and 5 · what the run recorded, by stage ────────────────────


def _breaks_by_account(outcome: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for one in outcome.get("breaks") or []:
        out.setdefault(str(one.get("account_id")), []).append(one)
    return out


def _stage_step(ctx, subjects, wanted_step: str) -> dict[str, Any]:
    """The shared body of steps 3, 4 and 5 — one stage each.

    ⚠ **THREE STEPS AND ONE FUNCTION, WHICH IS A DELIBERATE CHOICE AND NOT A
    SHORTCUT.** Each step asks the identical question of a different stage, and
    three copies of it would be three places for the stage mapping to drift.
    `14-step-library.md` measured this across the catalogue: 173 step instances
    reduce to 137 distinct steps, and the sharing that pays is exactly this
    shape. The STEPS stay separate — the chain draws three cells and the card
    names three questions — only the body is shared.
    """
    stop = _stopped(ctx)
    if stop:
        return _never_reached(stop)

    outcome = _outcome(ctx)
    by_account = _breaks_by_account(outcome)
    stages = [stage for stage, step in STEP_BY_STAGE.items() if step == wanted_step]
    found: dict[str, list[dict[str, Any]]] = {}
    for subject in subjects:
        account_id = str(subject.subject_id)
        mine = [
            one
            for one in by_account.get(account_id, [])
            if str(one.get("stage")) in stages
        ]
        if mine:
            found[account_id] = mine
    no_words = sorted(
        {
            str(one.get("reason"))
            for rows in found.values()
            for one in rows
            if str(one.get("reason")) not in REASON_WORDS
        }
    )
    return _StepResult(
        found={"breaks": found},
        checked={
            "stage": stages,
            "accounts_stopped_here": len(found),
            "accounts_looked_at": len(subjects),
            # Hard-won law 7 — what this runbook has no words for, by NAME and
            # with a count, so an unmapped reason is visible on the run instead
            # of quietly reading as a generic sentence for ever.
            "reasons_this_runbook_has_no_words_for": no_words,
        },
    ).as_dict()


def step_a_plan_in_force(ctx, subjects) -> dict[str, Any]:
    """3 · For every service, for the whole period — stage `resolve-subscription`."""
    return _stage_step(ctx, subjects, STEP_PLAN)


def step_a_read_for_every_service(ctx, subjects) -> dict[str, Any]:
    """4 · Actual or estimated, inside the window — stage `measure-consumption`."""
    return _stage_step(ctx, subjects, STEP_READ)


def step_did_pricing_refuse(ctx, subjects) -> dict[str, Any]:
    """5 · Which step, which sentence — stage `price-usage`, **and re-priced**.

    ⚠ **THIS IS WHERE *RE-PRICE TO CONFIRM* HAPPENS, AND IT IS THE CARD'S OWN
    DESIGN NOTE**: *"Re-price to confirm pushes the account through the real
    engine so the sentence shown is the engine's refusal, not an inference about
    it — the same principle as the test bill."* The seam calls
    `billing.single.prepare_single_bill` + `billing.runs.price_account`, which
    IS the bill run's code rather than a copy of it, and **writes nothing**: no
    draft, no bill number, no journal line.

    ⚠ **WHAT IT ANSWERS IS *IS IT STILL BROKEN*, NOT *WHAT HAPPENED*.** The run's
    break is the history and it is authoritative about the day; the re-price is
    today. Where they disagree — an account that broke on a missing read and now
    prices cleanly — BOTH are reported, because a clerk who has just added the
    read needs to know it took.

    ⚠ **ONE ENGINE CALL PER ACCOUNT, AND THE COST IS STATED RATHER THAN HIDDEN.**
    A break list of 14 accounts is 14 calls; a whole-run list at the top of the
    ICP would be far more, which is why the toggle exists and why it is read
    here rather than assumed on.
    """
    result = _stage_step(ctx, subjects, STEP_PRICING)
    if not result.get("reached"):
        return result

    if not bool(ctx.params.get("re_price_to_confirm", True)):
        result["checked"]["re_priced"] = 0
        result["checked"]["re_price_to_confirm"] = False
        return result

    outcome = _outcome(ctx)
    start, end = _iso(outcome.get("period_start")), _iso(outcome.get("period_end"))
    now: dict[str, Any] = {}
    priced = refused = unreadable = 0
    for subject in subjects:
        if start is None or end is None:
            unreadable += 1
            continue
        answer = billing_seam.price_account_as_the_run_would(
            account_id=subject.subject_id, period_start=start, period_end=end
        )
        refusal = answer.get("refusal")
        if refusal is None:
            priced += 1
            now[str(subject.subject_id)] = {"prices_now": True}
            continue
        refused += 1
        now[str(subject.subject_id)] = {
            "prices_now": False,
            # ⚠ THE ENGINE'S OWN REASON CODE, CARRIED AND NEVER DRAWN — its
            # `detail` quotes rule ids and B14 rule 32 keeps those off a screen.
            "reason": refusal.get("reason"),
            "service": refusal.get("service_code"),
            "silent": bool(refusal.get("silent")),
        }
    result["found"]["re_priced"] = now
    result["checked"].update(
        {
            "re_price_to_confirm": True,
            "re_priced": priced + refused,
            "prices_cleanly_now": priced,
            "still_refuses": refused,
            "period_unreadable": unreadable,
        }
    )
    return result


# ── step 6 · did the write refuse? ────────────────────────────────────────


def step_did_the_write_refuse(ctx, subjects) -> dict[str, Any]:
    """6 · A duplicate, a constraint, a number series exhausted.

    ⚠ **NOTHING IN THIS PRODUCT RECORDS A REFUSED WRITE, AND THIS STEP SAYS SO
    RATHER THAN REPORTING A CLEAN RESULT.** `bill_run_breaks` carries what the
    pipeline's three stages raised; a failure inside the drafting transaction
    leaves no row, because the transaction that would have written it is the one
    that rolled back. There is no `write_refused` reason in billing's own
    `STAGE_BY_REASON` — verified 2026-09-07 — and no table of failed writes.

    What this step CAN see is the state that would follow one: **no invoice on
    this run and no break naming a stage**. It reports that as *nothing was
    recorded either way*, which is an honest description of a gap and is not the
    same claim as *the write refused*.
    """
    stop = _stopped(ctx)
    if stop:
        return _never_reached(stop)

    outcome = _outcome(ctx)
    billed = set(outcome.get("billed_account_ids") or [])
    by_account = _breaks_by_account(outcome)
    unexplained = [
        str(subject.subject_id)
        for subject in subjects
        if str(subject.subject_id) not in billed and not by_account.get(str(subject.subject_id))
    ]
    return _StepResult(
        found={"unexplained": unexplained},
        checked={
            "accounts_with_no_bill_and_no_break": len(unexplained),
            # Hard-won law 7 — the number beside the blind spot, and here it is
            # zero BY CONSTRUCTION rather than by measurement.
            "refused_writes_recorded": 0,
            "nothing_records_a_refused_write": True,
        },
    ).as_dict()


# ── step 7 · did it bill last time? ───────────────────────────────────────


def step_did_it_bill_last_time(ctx, subjects) -> dict[str, Any]:
    """7 · What changed since the run that worked.

    `RB-106`'s design note calls this *"the row that usually explains
    everything"* — its own worked example is a sewer meter exchanged on 2 Sep,
    which is why the sewer read is missing.

    ⚠ **THE LAST BILL IS READ PER ACCOUNT AND THE COST IS STATED.** A break list
    of 14 accounts is 14 reads; at the top of the ICP a whole-run break list
    could be far larger, and a bulk form is `billing`'s to publish rather than
    this module's to assemble (`13-selector-inventory.md` §4's own last bullet
    names exactly this class of gap).
    """
    stop = _stopped(ctx)
    if stop:
        return _never_reached(stop)

    last: dict[str, dict[str, Any]] = {}
    for subject in subjects:
        account_id = str(subject.subject_id)
        bills = billing_seam.issued_bills_for_account(account_id, limit=1)
        if bills:
            last[account_id] = {
                "period_end": bills[0].get("period_end"),
                "total": bills[0].get("total"),
                "currency": bills[0].get("currency"),
            }
    return _StepResult(
        found={"last_bill": last},
        checked={
            "accounts_looked_at": len(subjects),
            "accounts_that_have_ever_billed": len(last),
            "accounts_that_never_billed": len(subjects) - len(last),
        },
    ).as_dict()


# ── the per-record verdict ────────────────────────────────────────────────


def _verdict_for(ctx_or_view, account_id: str) -> dict[str, Any]:
    """WHERE this account stopped, in the card's own vocabulary.

    The order is the steps' own, and the FIRST hit wins — the card's *stops at
    the first that fails*, applied to one account.
    """
    outcome = (ctx_or_view.set_results.get("_outcome") or {}) or {}
    billed = set(outcome.get("billed_account_ids") or [])
    if account_id in billed:
        return {
            "stopped_at": None,
            "outcome": OUTCOME_BILLED,
            "why": "This account billed on this run.",
        }
    holds = ((ctx_or_view.set_results.get(STEP_HELD) or {}).get("found") or {}).get("holds") or {}
    if account_id in holds:
        return {
            "stopped_at": STEP_HELD,
            "outcome": OUTCOME_HELD,
            "why": " · ".join(holds[account_id]["reasons"]),
        }
    for step in (STEP_PLAN, STEP_READ, STEP_PRICING):
        breaks = ((ctx_or_view.set_results.get(step) or {}).get("found") or {}).get("breaks") or {}
        mine = breaks.get(account_id) or []
        if mine:
            first = mine[0]
            code = str(first.get("reason") or "")
            re_priced = (
                (
                    ((ctx_or_view.set_results.get(STEP_PRICING) or {}).get("found") or {}).get(
                        "re_priced"
                    )
                    or {}
                ).get(account_id)
                or {}
            )
            service = str(re_priced.get("service") or "")
            words = REASON_WORDS.get(code)
            outcome = (ctx_or_view.set_results.get("_outcome") or {}) or {}
            return {
                "stopped_at": step,
                "outcome": OUTCOME_STOPPED,
                "words_found": words is not None,
                "prices_now": (
                    (
                        ((ctx_or_view.set_results.get(STEP_PRICING) or {}).get("found") or {}).get(
                            "re_priced"
                        )
                        or {}
                    )
                    .get(account_id, {})
                    .get("prices_now")
                ),
                # ⚠ THE BREAK'S OWN `detail` IS THE ENGINE'S SENTENCE AND IT
                # QUOTES RULE IDS BY NAME (the seeded one reads *"BR-BIL-015
                # makes that a choice"*), so the clerk-facing sentence comes from
                # `REASON_WORDS` and the detail travels in `meta`, drawn by
                # nothing (B14 rule 32).
                # ⚠ THE PERIOD IS NAMED, NOT ALLUDED TO. `RB-106`'s own
                # sentence is *"no Sewer read between 18 Aug and 17 Sep"*, and
                # *"in this period"* over a screen that shows two other dates is
                # the sentence a clerk has to translate before saying it.
                "why": (words or REASON_UNKNOWN)
                .replace("{service}", service or "one service")
                .replace("in this period", _window_words(outcome)),
                "detail": first.get("detail"),
                "reason_code": code,
            }
    return {
        "stopped_at": STEP_WRITE,
        "outcome": OUTCOME_UNEXPLAINED,
        "why": "No bill and nothing recorded either way.",
    }


def step_the_account(ctx, subject) -> dict[str, Any]:
    """The one per-record step — one account, one savepoint, one answer.

    ⚠ **PER RECORD, SO THE BREAK-LIST VARIANT COSTS ONE SAVEPOINT PER ACCOUNT**
    and one failing account never takes the other thirteen with it. On
    PostgreSQL the nested `transaction.atomic()` the executor opens is the ONLY
    thing that makes that true, and the suite's in-memory SQLite cannot see the
    difference (hard-won law 14).
    """
    if _stopped(ctx):
        return {
            "outcome": OUTCOME_SKIPPED,
            "reason": "The run stopped before this step.",
            "decided_by_rule": "A required step failing makes every later step Never reached",
            "fix_route": FIX_BILLING,
        }
    account_id = str(subject.subject_id)
    verdict = _verdict_for(ctx, account_id)
    step = verdict.get("stopped_at")
    route, label = FIX_FOR_STEP.get(step or STEP_LAST_TIME, (FIX_ACCOUNTS, "Open the account →"))
    last = (
        ((ctx.set_results.get(STEP_LAST_TIME) or {}).get("found") or {}).get("last_bill") or {}
    ).get(account_id)
    return {
        "outcome": verdict["outcome"],
        "reason": verdict["why"],
        "decided_by_rule": (
            "A run records the stage that stopped each account"
            if verdict["outcome"] == OUTCOME_STOPPED
            else "An account with no bill and no break has nothing recorded either way"
        ),
        "fix_route": route,
        "data": {
            "label": subject.label,
            "stopped_at": step,
            "position": STEP_POSITION.get(step or "", 0),
            "fix_label": label,
            "last_billed_on": (last or {}).get("period_end"),
            "detail": verdict.get("detail"),
            "reason_code": verdict.get("reason_code"),
            # ⚠ `None` MEANS NOT RE-PRICED, `False` MEANS STILL REFUSED, `True`
            # MEANS THE FIX HAS LANDED — three states, and collapsing the first
            # two would tell a clerk an account is still broken when nobody
            # asked the engine.
            "prices_now": verdict.get("prices_now"),
        },
    }


# ── the report ────────────────────────────────────────────────────────────


def _chain_for(view, account_id: str) -> Block:
    """Seven cells: green up to the stop, RED at it, *Never reached* after.

    `RB-106`'s own figure — *1 In scope · 2 Not held · 3 Plan in force · 4 Read
    missing · 5 Pricing Never reached · 6 Write Never reached · 7 Last time
    Billed 20 Aug*. The last cell is drawn even after a stop, because *when did
    it last work* is the fact the clerk uses to date the change.
    """
    verdict = _verdict_for(view, account_id)
    stopped = verdict.get("stopped_at")
    position = STEP_POSITION.get(stopped or "", len(STEP_LABELS) + 1)
    last = (
        ((view.set_results.get(STEP_LAST_TIME) or {}).get("found") or {}).get("last_bill") or {}
    ).get(account_id)
    cells = []
    for key, label in STEP_LABELS.items():
        index = STEP_POSITION[key]
        if key == STEP_LAST_TIME:
            # ⚠ `ChainCellState` is `ok | bad | notReached | pending` and there
            # is no `warn`. *Never billed* is not a failure of this run — it is
            # a fact nobody has established yet — which is what `pending` is
            # for, and what `notReached`'s own comment says about colouring a
            # cell red the run never found a blocker in.
            state = "ok" if last else "pending"
            note = (
                f"Billed {_iso(last['period_end']).strftime('%-d %b')}"
                if last and _iso(last.get("period_end"))
                else "Never billed"
            )
        elif index < position:
            state, note = "ok", ""
        elif index == position:
            # ⚠ THE SHORT FORM — B14 rule 33. The full sentence is the Sentence
            # block's, one region above.
            state, note = "bad", SHORT_NOTE.get(str(stopped), "Stopped here")
        else:
            state, note = "notReached", "Never reached"
        cells.append(
            {"id": key, "position": index, "label": label, "state": state, "note": note}
        )
    return Block(
        block="chain",
        payload={
            "label": (
                f"Stopped at step {position}."
                if stopped and verdict["outcome"] != OUTCOME_BILLED
                else "This account billed."
            ),
            "cells": cells,
        },
    )


def report(view) -> list[Block]:
    """`RB-106`'s own blocks — **Sentence · Chain · Facts · Records**.

    Two shapes, and the card asks for both:

    * **one account** — the sentence, the seven-cell chain and the facts,
      because that is what a clerk opened this to read.
    * **the break list** — the same sentence over the whole run, and the Records
      table grouped by the step that stopped each account, with chips.

    ⚠ **A STOPPED RUN DRAWS NEITHER**: no chain over a run nobody picked, and no
    empty records table pretending the run was clean.
    """
    stop = (view.set_results.get(STEP_SCOPE) or {}).get("stop")
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
            Block(
                block="records",
                payload={
                    "columns": _columns(),
                    "rows": [],
                    "total": 0,
                    "empty": {"title": stop["headline"], "helper": stop["detail"]},
                },
            ),
        ]

    outcome = view.set_results.get("_outcome") or {}
    records = list(view.records)
    single = len(records) == 1
    stopped = [one for one in records if one.outcome in (OUTCOME_STOPPED, OUTCOME_UNEXPLAINED)]
    held = [one for one in records if one.outcome == OUTCOME_HELD]
    billed = [one for one in records if one.outcome == OUTCOME_BILLED]

    by_step: dict[str, int] = {}
    for record in records:
        key = str(record.data.get("stopped_at") or "")
        if key:
            by_step[key] = by_step.get(key, 0) + 1

    blocks: list[Block] = [
        Block(
            block="verdict",
            payload={
                "word": ("Billed" if billed and single else "Stopped") if single else "Break list",
                "tone": "success" if (single and billed) else "warning",
                "count": (
                    records[0].reason
                    if single and records
                    else f"{len(stopped)} accounts did not bill · {len(held)} held on purpose"
                ),
                "detail": (
                    f"{_window_words(outcome)} · run {outcome.get('run_no') or ''}".strip()
                ),
            },
        ),
        Block(
            block="sentence",
            payload={
                # ⚠ `OutcomeTone` is `success | danger | muted` — NOT the
                # verdict's `success | warning | danger`. A fourth word draws
                # the card with no rail and no tint, silently, because the
                # renderer looks the class up in a `Record` and the backend
                # validator checks the FIELD and never its value.
                "tone": "danger" if stopped else "success",
                "label": "What stopped it",
                "text": _sentence(view, records, outcome),
            },
        ),
    ]
    if single and records:
        blocks.append(_chain_for(view, str(records[0].subject.subject_id)))
        blocks.append(_facts(view, records[0], outcome))

    blocks.append(
        Block(
            block="records",
            payload={
                "columns": _columns(),
                "rows": [
                    {
                        "id": f"row-{index}",
                        "cells": {
                            "account": {"kind": "text", "text": str(record.data.get("label") or "")},
                            "stopped_at": {
                                "kind": "text",
                                "text": str(record.data.get("position") or "—"),
                            },
                            "why": {"kind": "text", "text": record.reason},
                            "fix": {
                                "kind": "link",
                                "label": str(record.data.get("fix_label") or "Open →"),
                                "to": record.fix_route,
                            },
                        },
                        # Carried, never drawn — the engine's own sentence may
                        # quote a rule id (B14 rule 32).
                        "meta": {
                            "decided_by_rule": record.decided_by_rule,
                            "outcome": record.outcome,
                            "reason_code": record.data.get("reason_code"),
                            "detail": record.data.get("detail"),
                        },
                    }
                    for index, record in enumerate(stopped + held, start=1)
                ],
                "total": len(stopped) + len(held),
                "chips": [
                    {
                        "id": step,
                        "label": STEP_LABELS[step],
                        "count": count,
                    }
                    for step, count in sorted(by_step.items(), key=lambda one: STEP_POSITION.get(one[0], 0))
                    if step
                ],
                "empty": {
                    "title": "Every account in this run billed.",
                    "helper": f"{len(billed)} accounts, none stopped.",
                },
            },
        )
    )
    return blocks


def _columns() -> list[dict[str, Any]]:
    return [
        {"key": "account", "label": "Account"},
        {"key": "stopped_at", "label": "Stopped at", "numeric": True},
        {"key": "why", "label": "Why"},
        {"key": "fix", "label": "Fix"},
    ]


def _sentence(view, records, outcome: dict[str, Any]) -> str:
    """`RB-106`'s deliverable: *"Stopped at step 4 — no Sewer read between 18 Aug
    and 17 Sep. Last billed 20 Aug."*

    ⚠ **NO RULE ID AND NO STAGE NAME** (B14 rule 32): `measure-consumption` is
    billing's word for its own pipeline and means nothing to a clerk.
    """
    if not records:
        return "Nothing was pinned for this run."
    if len(records) > 1:
        stopped = [one for one in records if one.outcome != OUTCOME_BILLED]
        return (
            f"{len(stopped)} of {len(records)} accounts in this run did not bill. "
            "The table groups them by the step that stopped each one."
        )
    record = records[0]
    position = record.data.get("position")
    last = record.data.get("last_billed_on")
    parts = []
    if record.outcome == OUTCOME_BILLED:
        # ⚠ AND NOTHING ELSE. *"This account billed on this run. Last billed 30
        # Jun."* is two facts that argue with each other on the same line; the
        # run's own bill is the answer and the previous one is noise.
        return "This account billed on this run."
    parts.append(f"Stopped at step {position} — {record.reason}")
    if record.data.get("prices_now") is True and record.outcome != OUTCOME_BILLED:
        # The fix has landed since the run — the single most useful thing to
        # tell a clerk who has just added the read.
        parts.append("It prices cleanly now, so the next run will bill it.")
    if last:
        day = _iso(last)
        parts.append(f"Last billed {day.strftime('%-d %b')}." if day else "")
    else:
        parts.append("This account has never billed.")
    return " ".join(part for part in parts if part)


def _facts(view, record, outcome: dict[str, Any]) -> Block:
    last = record.data.get("last_billed_on")
    return Block(
        block="facts",
        payload={
            "heading": "What the run recorded",
            "rows": [
                {
                    "id": "run",
                    "label": "Run",
                    "value": {
                        "kind": "text",
                        "text": f"{outcome.get('run_no') or ''} · {_window_words(outcome)}".strip(
                            " ·"
                        ),
                    },
                },
                {
                    "id": "stopped",
                    "label": "Stopped at",
                    "value": {
                        "kind": "text",
                        "text": (
                            f"Step {record.data.get('position')} · "
                            f"{STEP_LABELS.get(str(record.data.get('stopped_at')), '—')}"
                            if record.data.get("stopped_at")
                            else "Nothing stopped it"
                        ),
                    },
                },
                {
                    "id": "last",
                    "label": "Last billed",
                    "value": {
                        "kind": "date" if last else "text",
                        **({"value": str(last)} if last else {"text": "Never"}),
                    },
                },
            ],
        },
    )


# ── the pinned scope ──────────────────────────────────────────────────────


def resolve(ctx):
    """One account, **or every account the run left unbilled** (`BR-RBS-009`).

    ⚠ **THE VARIANT IS THE SAME RUNBOOK WITH A WIDER SCOPE AND NOT A SECOND
    ONE.** `RB-106`'s panel is headed *Scope one account, or the whole break
    list*: leave `account` unset and every account the run broke on, held or
    left with nothing is pinned, one record each. Two runbooks would be two
    answers to one question.

    ⚠ **RESOLVED ONCE AND FROZEN.** An account that gets a catch-up bill while
    this run is going is not added to the set — the run explains what happened,
    and a set that moved underneath it would explain something else.
    """
    account_id = ctx.params.get("account")
    if account_id:
        facts = customers_seam.account_facts(account_id)
        if facts is None:
            return []
        return [
            SubjectRef(
                subject_type="account",
                subject_id=str(account_id),
                label=str(facts.get("label") or facts.get("account_no") or ""),
            )
        ]

    outcome = billing_seam.bill_run_outcome(ctx.params.get("bill_run")) or {}
    ctx.set_results["_outcome"] = outcome
    wanted: list[str] = []
    for one in outcome.get("breaks") or []:
        if str(one.get("account_id")) not in wanted:
            wanted.append(str(one.get("account_id")))
    for one in outcome.get("exclusions") or []:
        if str(one.get("account_id")) not in wanted:
            wanted.append(str(one.get("account_id")))
    subjects = []
    for account_id in wanted:
        facts = customers_seam.account_facts(account_id) or {}
        subjects.append(
            SubjectRef(
                subject_type="account",
                subject_id=account_id,
                # B14 rule 31 — the account NUMBER or the customer's name.
                label=str(facts.get("label") or facts.get("account_no") or ""),
            )
        )
    return subjects


RUNBOOK = RunbookDefinition(
    key=KEY,
    name="Why did this account not bill?",
    kind=models.KIND_CHECK,
    category="billing",
    subject_type="account",
    unit_of_work="one account on one bill run, or the run's whole break list",
    # ⚠ **MANUAL AND `bill_run.completed`, WHICH IS THE CARD'S OWN TRIGGER ROW**
    # — *"Manual · and `bill_run.completed(run_id)` for the whole-break-list
    # variant"*. Unlike `batch.landed` and `feedback.landed`, this event name is
    # already in `models.EVENT_KINDS`; whether anything EMITS it is `CR-069`'s
    # question and the manual half waits on nothing.
    triggers=(models.TRIGGER_MANUAL, models.EVENT_BILL_RUN_COMPLETED),
    tags=("Accounts",),
    parameters=(
        Parameter(
            name="account",
            type=PARAM_REF_OBJECT,
            label="Account",
            # Unset means the whole break list — the card's own second scope.
        ),
        Parameter(
            name="bill_run",
            type=PARAM_REF_OBJECT,
            label="Bill run",
            required=True,
        ),
        Parameter(
            name="stop_at_first_cause",
            type=PARAM_TOGGLE,
            label="Stop at first cause",
            # ⚠ **ON, AND IT IS THE CARD'S GUARD RATHER THAN A PREFERENCE**: *"it
            # stops at the first failure because a clerk needs one answer, not
            # seven"*. Every step still RUNS — the chain has to draw seven cells
            # — and what stops is the ATTRIBUTION: the first hit wins.
            default=True,
        ),
        Parameter(
            name="re_price_to_confirm",
            type=PARAM_TOGGLE,
            label="Re-price to confirm",
            default=True,
        ),
        Parameter(
            name="raise_a_work_item",
            type=PARAM_TOGGLE,
            label="Raise a work item",
            # A work item is an ENGINE act (`BR-RBS-022`) and the upsert is
            # `CR-075` task `H1`, phase 4. Declared because the card declares it.
            default=True,
        ),
    ),
    resolve=resolve,
    report=report,
    steps=(
        Step(key=STEP_SCOPE, label=STEP_LABELS[STEP_SCOPE], mode=MODE_SET, run=step_was_it_in_scope),
        Step(key=STEP_HELD, label=STEP_LABELS[STEP_HELD], mode=MODE_SET, run=step_was_it_held_on_purpose),
        Step(key=STEP_PLAN, label=STEP_LABELS[STEP_PLAN], mode=MODE_SET, run=step_a_plan_in_force),
        Step(key=STEP_READ, label=STEP_LABELS[STEP_READ], mode=MODE_SET, run=step_a_read_for_every_service),
        Step(key=STEP_PRICING, label=STEP_LABELS[STEP_PRICING], mode=MODE_SET, run=step_did_pricing_refuse),
        Step(key=STEP_WRITE, label=STEP_LABELS[STEP_WRITE], mode=MODE_SET, run=step_did_the_write_refuse),
        Step(
            key=STEP_LAST_TIME,
            label=STEP_LABELS[STEP_LAST_TIME],
            mode=MODE_SET,
            run=step_did_it_bill_last_time,
        ),
        # ⚠ THE PER-RECORD STEP THE CARD ASKS FOR — *per record (1)* — and it is
        # the one that produces the row a clerk reads. It runs LAST because it
        # composes what the seven set steps found.
        Step(key="the_account", label="This account", mode=MODE_PER_RECORD, run=step_the_account),
    ),
)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-021 (EP-RBS-05; CR-075 wave S)
# generated: 2026-09-07 by the CR-075 wave S build lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint — every runbooks route is a GET and POST /runbooks/{key}/runs is wave L) E=n/a(no screen — RBS-004 and RBS-006 render any runbook; RB-020) F✔ G✔ H=n/a(no 🔒 path: this composes no idempotency key, prices nothing and posts no ledger line)
# gates: pytest tests/test_us_rbs_021_why_not_billed.py · pytest tests/test_us_rbs_015_conformance.py · G115 · G20
# exceptions: step 6 (*did the write refuse*) has nothing to read — no `write_refused` reason exists in billing's `STAGE_BY_REASON` and a rolled-back draft leaves no row, so it reports *no bill and nothing recorded either way* with the count beside it and never claims a refused write · the card's seven steps and billing's three pipeline stages are two vocabularies and the mapping is written out rather than assumed · `account` and `bill_run` are `ref:object` with no tenant-resolved DOMAIN, which is wave `T`'s (`BR-RBS-042`); the domains this runbook needs are `account` and a new `bill_run` one
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
