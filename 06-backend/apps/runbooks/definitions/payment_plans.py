# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-035 (EP-RBS-05) — CR-075 wave R′, the payments half:
#           runbook 25, registered as an Action holding `queue_notice`,
#           DISABLED for live, guards evaluated BEFORE step 1.
# Rules:    BR-RBS-010 (every record states the rule that decided it, in words)
#           · BR-RBS-013 (a correction goes through the OWNING module) ·
#           BR-RBS-012 (guards are absolute, before any step) · BR-RBS-014 (a
#           SAMPLE record is never acted on) · BR-RBS-022 (a write is a named
#           port; the audit row is the ENGINE's) · BR-RBS-035 (a count for the
#           outcomes with no row) · BR-RBS-003 (dry and live are one path) ·
#           BR-PAY-016 (plan notices: reminder 3 days before, missed-notice
#           day+1, 2nd miss VOIDS the plan — payments' law, READ and never
#           copied) · BR-CUS-043 (the schedule's arithmetic, frozen as GT-47) ·
#           BR-PAY-021 (on time is `posted_at ≤ due date`) · CLAUDE.md hard
#           rule 2 (money 4 stored, 2 displayed) · hard rule 4 (a correction is
#           a new row)
# Tests:    06-backend/tests/test_us_rbs_035_payment_plans.py
# Impacts:  apps/runbooks/definitions/__init__.py (the one registration line) ·
#           apps/runbooks/seams/payments_seam.py ·
#           apps/payments/runbook_reads.py (the reads added with it)
# ───────────────────────────────────────────────────────
"""Runbook 25 — **Payment plans**. It warns, and it CANNOT void.

WHAT IT DOES, IN ONE SENTENCE
------------------------------
It walks every plan still in flight, finds the instalments missed this cycle,
counts the misses against the tenant's own limit, queues a warning, and — for a
plan past the limit — **records that the plan is due to be voided and names who
must do it**, because voiding a plan is a write this module has no port for.

⚠ **THE VOID HAS NO PORT, AND THAT IS THE FINDING THIS RUNBOOK CARRIES**
--------------------------------------------------------------------------
`RB-125` step 5 reads *"Void the plan · after the configured misses · through
the payments service · the balance returns to the ladder."* **There is no port
that can.** `US-RBS-035`'s own §5 says so in one line — *"**Port:**
`queue_notice`. Plan status is payments'"* — and the port list is closed:
fourteen declarations, five of them payments', and not one of them touches
`payment_plans.status`. A fifteenth is a **reviewed interface change**
(`BR-RBS-022`), which is a ruling and not a lane's decision — `CR-075` added its
first-ever new port on 2026-09-07 (`step_ladder`) and did it through a recorded
ruling, which is the bar.

So this runbook does what the shape of the module allows and says so out loud:
the plan reaches `to_void` with the rule that decided it and a route to the
screen where a person voids it. **The alternative — `PaymentPlan.objects.update
(status=…)` — is a cross-module write, is four lines shorter, and is exactly
what `G115`'s census exists to catch.**

⚠ **AND THERE IS NO `voided` STATUS TO WRITE EVEN IF THERE WERE A PORT.**
`PLAN_STATUSES` is four values — `proposed`, `agreement_sent`, `active`,
`closed` — and `collections_models.py` states in its own docstring that they are
four. A plan that failed is `closed`, indistinguishable from one a customer paid
off. That is why runbook 15 in this same wave cannot honour its *"Never include:
Plan voided in 12 months"* guard either: the two runbooks record the same absence
from opposite ends, and neither invents a fifth status.

**`OQ-RBS-1740` carries both halves** — the port and the status — and is OPEN.
Nothing here is stubbed: what ships is that it does not void, stated on the
result screen in a clerk's own words, which is the posture `OQ-RBS-1734` already
set for this module (*"Built meanwhile: it does not"*).

WHAT THIS FILE DIVERGES FROM `RB-125` ON, AND WHY — RECORDED, NOT APPLIED SILENTLY
-----------------------------------------------------------------------------------
**1 · THE CARD SAYS *Steps 6 · 3 read, 3 write* AND THIS DECLARES FOUR.** Same
arithmetic as runbook 8's divergence 1, plus the card's own step 6:

    card 1  Gather plans in flight   → `resolve()`
    card 2  Find missed instalments  → step `missed`   (set · read)
    card 3  Count the misses         → step `count`    (set · read)
    card 4  Queue the warning        → step `warn`     (per record · writes)
    card 5  Void the plan            → step `void`     (per record · writes)
    card 6  Record it                → the ENGINE's audit row (`BR-RBS-022`)

Card step 6 (*"Audit row names this runbook"*) is not a runbook's step at all —
`engine/acts.py` writes it, which is the only thing that lets a Check leave a
trail while holding no writer, and every outcome writes one including `planned`.

**2 · THE SUBJECT IS AN `account`, NOT A PLAN.** `SUBJECT_TYPES` has twelve
values and `payment_plan` is not among them; a thirteenth is a schema change and
a reviewed one. It costs nothing here: `uq_one_live_plan_per_account` makes one
live plan per account a DATABASE guarantee, so *the account* and *the plan in
flight* are the same set, and the account NUMBER is what a clerk reads anyway
(B14 rule 31).

**3 · *A plan in good standing* IS NOT COUNTED AS SKIPPED**, which is
`TC-RBS-035.2` in as many words. A plan whose instalments are all met is walked,
gets a record row saying `current`, and is a distinct outcome — not swept into
the same tally as a plan the run refused to touch. Two different facts must not
share one number.

⚠ WHAT WOULD MAKE THIS RUNBOOK DO THE WRONG THING QUIETLY (hard-won law 7)
---------------------------------------------------------------------------
* **Counting a paid instalment as missed because the payment CLEARED late.**
  `BR-PAY-021`: on time is `posted_at ≤ due date`, and a cheque posted on the due
  date that clears three days later is ON TIME. → `paid_posted_on` is the column
  read, and clearing dates never touch that table.
* **Warning a plan twice in one week.** The per-record key's discriminator is the
  MISS COUNT, so a plan at two misses is warned once however often the run
  fires, and a plan that misses a third instalment is a different key and is
  warned again. Drop the discriminator and a customer who falls further behind is
  never told; put the RUN in it and they are told every Monday.
* **Voiding on a limit nobody set.** `settings_seam.collections` REFUSES rather
  than falling back to `BR-PAY-016`'s defaults, and its reason holds word for
  word — *"every step it takes reaches a real customer"*. → An unreadable setting
  is `not_configured`, a named outcome with a route to Settings, and no plan is
  voided against a number this module chose.
* **Re-deriving the schedule.** `apps.customers.payment_plan.build_schedule` owns
  it and it is frozen as `GT-47` (267.30 − 50 down over 6 → 5 × 36.22 + 36.20).
  → Nothing here computes an instalment amount; the rows are read.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from apps.runbooks import models
from apps.runbooks.contract import (
    MODE_PER_RECORD,
    MODE_SET,
    PARAM_ENUM,
    PARAM_INTEGER,
    PARAM_TEXT,
    Block,
    Guard,
    Parameter,
    RunbookDefinition,
    Step,
    SubjectRef,
)
from apps.runbooks.engine import acts, duplicates
from apps.runbooks.seams import customers_seam, metering_seam, payments_seam

RUNBOOK_KEY = "payment_plans"

STEP_MISSED = "missed"
STEP_COUNT = "count"
STEP_WARN = "warn"
STEP_VOID = "void"

STEP_LABELS = {
    STEP_MISSED: "Find missed instalments",
    STEP_COUNT: "Count the misses",
    STEP_WARN: "Queue the warning",
    STEP_VOID: "Void the plan",
}

#: Every outcome word a clerk reads. `planned` is the ENGINE's and is what a dry
#: run produces for a write that reached a writer-less port.
OUTCOME_CURRENT = "current"
OUTCOME_WARNED = "warned"
OUTCOME_TO_VOID = "to_void"
OUTCOME_NOT_CONFIGURED = "not_configured"
OUTCOME_ALREADY_WARNED = "already_warned"
OUTCOME_SKIPPED = "skipped"
OUTCOME_FAILED = "failed"
OUTCOME_HELD = "held"

#: Tenant-relative fix routes, prefixed with `/:tenant/` by the shell. Both are
#: paths this product actually mounts (`App.tsx`, checked 2026-09-07): a fix
#: route resolving to nothing is a dead button over a live finding and no
#: backend test can see one, because a string is a string.
FIX_ACCOUNT = "customers"
FIX_SETTINGS_COLLECTIONS = "settings/collections"


# ── guards — ABSOLUTE, and evaluated before step 1 (BR-RBS-012) ───────────


def _memo(ctx: Any, key: str, build) -> Any:
    """One lazily-built answer per run, so a guard is not asked twice."""
    cached = ctx.set_results.get(key)
    if cached is None:
        cached = build()
        ctx.set_results[key] = cached
    return cached


def _as_of(ctx: Any) -> dt.date:
    """The business day this run is taken for. **An argument, never a clock.**

    `BR-TEN-043`, gate `G6`. *"Due date passed, no payment inside the grace
    days"* is a statement about a DAY; a wall clock makes it impossible to
    re-take last Monday's run and get last Monday's answer.
    """
    given = ctx.params.get("as_of")
    if isinstance(given, dt.date):
        return given
    if isinstance(given, str) and given:
        return dt.date.fromisoformat(given)
    raise ValueError(
        "runbook 25 needs the business day it is being run for. It is a parameter and never a "
        "clock read (BR-TEN-043): a plan re-checked for last Monday must give last Monday's "
        "answer, and a void is not a decision to take against an unnamed day."
    )


def _settings(ctx: Any) -> dict[str, Any]:
    """`BR-PAY-016`'s grace days and miss limit, read ONCE from Settings.

    `RBR-03`: policy lives in Settings and is never duplicated onto a card. The
    read REFUSES rather than defaulting, which is `settings_seam.collections`'
    own posture and its own reason.
    """
    return _memo(ctx, "_settings", payments_seam.plan_notice_settings)


def _plans(ctx: Any) -> dict[str, Any]:
    """Every plan in flight with its misses, read ONCE and memoised.

    `resolve()` pins the scope from it and both read steps use it, so reading it
    twice would let the pinned set and the per-record pass disagree — an
    instalment could be paid between them, which is what `BR-RBS-009`'s
    *"resolved ONCE and pinned"* exists to prevent.
    """

    def build():
        settings = _settings(ctx)
        grace = settings.get("missed_notice_days_after")
        return payments_seam.plans_in_flight(
            as_of=_as_of(ctx), grace_days=int(grace or 0)
        )

    return _memo(ctx, "_plans", build)


def _by_account(ctx: Any) -> dict[str, Any]:
    return {str(row["account_id"]): row for row in _plans(ctx).get("rows", [])}


def guard_sample(ctx: Any, subject: SubjectRef) -> bool:
    """`BR-RBS-014` — **a sample record is never acted on, in any tenant, ever.**

    Absolute, evaluated before any step, and it cannot be switched off. A demo
    customer told their payment plan is about to be cancelled is the same class
    of failure as a demo account receiving a disconnection notice.
    """
    return str(subject.subject_id) in _memo(
        ctx, "_sample_ids", customers_seam.sample_account_ids
    )


def guard_dispute(ctx: Any, subject: SubjectRef) -> bool:
    """`RB-125`'s *Never include: Dispute* — an open dispute stops the chase.

    A dispute is a fact about a UNIT (`BR-MET-133` clause 4) and this walks
    accounts, so it goes account → unit through the anchors `customers` already
    publishes — the same walk runbook 8's own dispute guard takes, deliberately,
    so the two runbooks cannot disagree about which accounts are protected.

    A master account names a premises and no unit at all (`BR-CUS-1010`), which
    is lawful; it has no unit to carry a dispute and is not guarded here.
    """
    anchors: dict[str, Any] = _memo(
        ctx,
        "_anchors",
        lambda: {row["id"]: row for row in customers_seam.account_anchors()},
    )
    anchor = anchors.get(str(subject.subject_id))
    unit_id = anchor.get("unit_id") if anchor else None
    if not unit_id:
        return False
    cache: dict[str, bool] = _memo(ctx, "_disputes", dict)
    if unit_id not in cache:
        cache[unit_id] = metering_seam.unit_has_dispute_hold(unit_id)
    return cache[unit_id]


# ── resolve — the pinned set, and the setup screen's own count ────────────


def resolve(ctx: Any):
    """Every plan still in flight, pinned ONCE.

    Also the function that answers *"Matches N plans"* on `RBS-004-R25` — one
    function, because a count computed a second way is a count that can disagree
    with the run.

    ⚠ **EVERY plan in flight is walked, including the ones in good standing.**
    `TC-RBS-035.2` requires a current plan to be *"untouched, and NOT counted as
    skipped"*, which is only expressible if it is walked and given its own
    outcome. A scope that filtered to plans with misses would make *current* and
    *not looked at* the same number.
    """
    return [
        SubjectRef(
            subject_type="account",
            subject_id=str(row["account_id"]),
            # ⚠ THE ACCOUNT NUMBER, NEVER THE DATABASE ID (B14 rule 31).
            label=str(row.get("account_no") or ""),
        )
        for row in _plans(ctx).get("rows", [])
    ]


# ── steps ─────────────────────────────────────────────────────────────────


def step_missed(ctx: Any, subjects) -> dict[str, Any]:
    """2 · SET · read — which instalments were missed, for the whole set at once.

    ONE read for every plan rather than one per plan, for the ladder board's
    reason. A miss is a due date passed with no payment inside the grace days,
    and the payment's own POSTING date is what counts (`BR-PAY-021`) — a cheque
    posted on the due date and cleared three days later is on time.

    Nothing here re-derives the schedule: `apps.customers.payment_plan.
    build_schedule` owns that arithmetic and it is frozen as `GT-47`.
    """
    plans = _plans(ctx)
    wanted = {str(subject.subject_id) for subject in subjects}
    rows = [one for one in plans.get("rows", []) if str(one["account_id"]) in wanted]
    with_misses = [one for one in rows if one["misses"] > 0]
    return {
        "plans": {str(one["account_id"]): one for one in rows},
        "grace_days": plans.get("grace_days"),
        "as_of": plans.get("as_of"),
        # Three numbers rather than one: *0 behind* over 43 plans is a good
        # morning, and *0 behind* over 0 plans is a feature nobody is using.
        "plans_walked": len(rows),
        "plans_behind": len(with_misses),
        "instalments_missed": sum(one["misses"] for one in rows),
        "missed_value": _stored(
            sum((_money(one["missed_value"], Decimal("0")) for one in rows), Decimal("0"))
        ),
    }


def step_count(ctx: Any, subjects) -> dict[str, Any]:
    """3 · SET · read — the misses against the tenant's own limit, and the verdict.

    `BR-PAY-016`'s *"2nd miss VOIDS the plan"* is a **default**, not a constant:
    the number lives in Settings as `plan_void_after_misses` and this reads it.
    A runbook that carried its own copy would give a utility two answers to one
    question and no way to tell which one cancelled a customer's plan.

    ⚠ **AN UNREADABLE SETTING IS NOT A DEFAULT.** Where Settings cannot be read
    the verdict for every plan is `not_configured` with a route to the page, and
    nothing is warned or voided. That is the same refusal `settings_seam` already
    makes and it is made for the same reason.
    """
    settings = _settings(ctx)
    missed = ctx.set_results.get(STEP_MISSED, {}).get("plans", {})
    limit = settings.get("void_after_misses")
    readable = bool(settings.get("readable")) and limit is not None
    verdicts: dict[str, dict[str, Any]] = {}
    for key, row in missed.items():
        if not readable:
            verdicts[key] = {
                "verdict": OUTCOME_NOT_CONFIGURED,
                "why": "nobody has set how many missed instalments end a plan",
                "decided_by_rule": "This utility's plan rules are not set up",
                "fix_route": FIX_SETTINGS_COLLECTIONS,
            }
            continue
        misses = int(row["misses"])
        if misses == 0:
            verdicts[key] = {
                "verdict": OUTCOME_CURRENT,
                "why": "every instalment so far has been paid",
                "decided_by_rule": "A plan in good standing is left alone",
                "fix_route": FIX_ACCOUNT,
            }
        elif misses >= int(limit):
            verdicts[key] = {
                "verdict": OUTCOME_TO_VOID,
                "why": _plural(misses, "instalment") + " missed",
                "decided_by_rule": f"This utility ends a plan after {limit} missed instalments",
                "fix_route": FIX_ACCOUNT,
            }
        else:
            verdicts[key] = {
                "verdict": OUTCOME_WARNED,
                "why": _plural(misses, "instalment") + " missed",
                "decided_by_rule": "A missed instalment is warned before the plan ends",
                "fix_route": FIX_ACCOUNT,
            }
    return {
        "verdicts": verdicts,
        "void_after_misses": limit,
        "settings_readable": readable,
        "why_not": settings.get("why_not", ""),
        "to_warn": len(
            [one for one in verdicts.values() if one["verdict"] == OUTCOME_WARNED]
        ),
        "to_void": len(
            [one for one in verdicts.values() if one["verdict"] == OUTCOME_TO_VOID]
        ),
        "current": len(
            [one for one in verdicts.values() if one["verdict"] == OUTCOME_CURRENT]
        ),
    }


def step_warn(ctx: Any, subject: SubjectRef) -> dict[str, Any]:
    """4 · PER RECORD · **writes** — one warning, one plan, one miss count, once.

    ⚠ **THE DISCRIMINATOR IS THE MISS COUNT, AND THAT IS THE WHOLE REPEAT
    RULE.** The key `engine/acts.py` composes carries no run, so a plan at two
    misses is warned ONCE however often this runs — and a plan that misses a
    third instalment computes a different key and is warned again. Worked, on a
    weekly run over one plan:

        Mon 1 · 1 miss  → key …|1  → **warning 1**
        Mon 2 · 1 miss  → key …|1  → already written, nothing sent
        Mon 3 · 2 misses→ key …|2  → **warning 2**, and the plan is due to end

    ⚠ **THE WORD IS `Queued`, NEVER `Sent`** (`RBR-07`, PO 17 August 2026):
    nothing leaves the building until a delivery provider is connected, and no
    runbook is on `LIVE_ENABLED_RUNBOOKS` besides — so this reaches a writer-less
    port and records what it WOULD do, on the identical statements a live run
    walks (`BR-RBS-003`).
    """
    verdict = ctx.set_results.get(STEP_COUNT, {}).get("verdicts", {}).get(
        str(subject.subject_id), {}
    )
    plan = ctx.set_results.get(STEP_MISSED, {}).get("plans", {}).get(
        str(subject.subject_id), {}
    )
    if not verdict or not plan:
        return {
            "outcome": OUTCOME_SKIPPED,
            "decided_by_rule": "Only the pinned set is walked",
            "reason": "this plan was not in the set when the run pinned its scope.",
        }
    if verdict["verdict"] in (OUTCOME_CURRENT, OUTCOME_NOT_CONFIGURED):
        # A plan in good standing is walked and reported — never counted as
        # skipped (`TC-RBS-035.2`) — and nothing is written about it.
        return {
            "outcome": verdict["verdict"],
            "decided_by_rule": verdict["decided_by_rule"],
            "reason": verdict["why"],
            "fix_route": verdict["fix_route"],
            "data": _record_data(plan),
        }

    run_level = _run_level(ctx)
    if run_level.is_duplicate:
        return {
            "outcome": OUTCOME_ALREADY_WARNED,
            "decided_by_rule": "This job already ran and was approved",
            "reason": run_level.message,
            "data": _record_data(plan),
        }

    misses = int(plan["misses"])
    result = acts.perform(
        ctx,
        acts.ActRequest(
            port="queue_notice",
            action_kind="queue_notice",
            subject=subject,
            planned_action=(
                "Tell them the plan is ending"
                if verdict["verdict"] == OUTCOME_TO_VOID
                else "Warn about the missed instalment"
            ),
            # ⚠ THE MISS COUNT. Read the docstring before changing it.
            discriminator=str(misses),
            decided_by_rule=verdict["decided_by_rule"],
            reason=verdict["why"],
            amount=_money(plan.get("missed_value"), None),
            currency=plan.get("currency"),
            payload={
                "runbook_key": ctx.runbook_key,
                "account_id": subject.subject_id,
                "subject_id": subject.subject_id,
                "discriminator": str(misses),
                "actor": acts.actor_for(ctx),
                "channels": tuple(_channels(ctx)),
            },
        ),
    )
    return {
        "outcome": _outcome(result.outcome, OUTCOME_WARNED),
        "decided_by_rule": verdict["decided_by_rule"],
        "reason": verdict["why"],
        "fix_route": verdict["fix_route"],
        "data": _record_data(plan, key=result.idempotency_key),
    }


def step_void(ctx: Any, subject: SubjectRef) -> dict[str, Any]:
    """5 · PER RECORD · **writes** — and **it cannot void anything.**

    ⚠ **READ THE MODULE DOCSTRING BEFORE CHANGING THIS.** There is no port that
    writes `payment_plans.status` and there is no `voided` status to write. This
    step therefore does the only lawful thing: it names the plan, states the rule
    that ended it in a clerk's words, and points at the screen where a person
    performs the act. `OQ-RBS-1740` is OPEN and carries both halves.

    ⚠ **IT IS DECLARED `writes=True` DELIBERATELY, EVEN THOUGH IT WRITES
    NOTHING.** The declaration is what the setup screen draws, what the chain
    labels, and what the contract refuses on a Check — and the day the port
    exists, this step becomes an `acts.perform` call with no other change to the
    runbook. Declaring it `read` would make the absence invisible on every screen
    that lists what this runbook can do, which is the shape hard-won law 2's
    mirror is about.

    Nothing is stubbed and no `NotImplementedError` is raised: a run that died
    here would lose the warnings step 4 just planned, and `G8` reads a
    `NotImplementedError` as a blocked story when this one is shipped behaviour.
    """
    verdict = ctx.set_results.get(STEP_COUNT, {}).get("verdicts", {}).get(
        str(subject.subject_id), {}
    )
    plan = ctx.set_results.get(STEP_MISSED, {}).get("plans", {}).get(
        str(subject.subject_id), {}
    )
    if not verdict or verdict["verdict"] != OUTCOME_TO_VOID:
        return {
            "outcome": OUTCOME_SKIPPED,
            "decided_by_rule": "Only a plan past the limit ends",
            "reason": "this plan has not missed enough instalments to end.",
            "data": _record_data(plan),
        }
    limit = ctx.set_results.get(STEP_COUNT, {}).get("void_after_misses")
    return {
        "outcome": OUTCOME_TO_VOID,
        "decided_by_rule": f"This utility ends a plan after {limit} missed instalments",
        # The sentence a clerk reads. It says what is true — the runbook has
        # decided, and a person performs — rather than implying the plan is gone.
        "reason": (
            f"{_plural(int(plan.get('misses') or 0), 'instalment')} missed. "
            "End this plan on the account; the balance goes back to collections."
        ),
        "fix_route": FIX_ACCOUNT,
        "data": _record_data(plan, void_needs_a_person=True),
    }


# ── the run-level duplicate check (OQ-RBS-1737, CLOSED 2026-09-06) ────────


def _run_level(ctx: Any):
    """Ask ONCE per run whether this job already ran — never once per plan.

    A fact about the RUN, which is the shape of the Product Owner's own ruling:
    an APPROVED earlier run has written its rows, and an UNAPPROVED one is a
    third state that gets a warning rather than a silent skip.
    """

    def build():
        run = models.RunbookRun.objects.filter(pk=ctx.run_id).first()
        if run is None or run.started_at is None:
            return duplicates.DuplicateVerdict(verdict=duplicates.VERDICT_NONE)
        return duplicates.check(
            tenant_id=run.tenant_id,
            runbook_id=run.runbook_id,
            now=run.started_at,
            this_run_id=run.pk,
            frequency_hours=int(
                ctx.params.get("frequency_hours") or duplicates.DEFAULT_FREQUENCY_HOURS
            ),
        )

    return _memo(ctx, "_run_level", build)


# ── the report ────────────────────────────────────────────────────────────


def report(view) -> list[Block]:
    """KPIs · Breakdown · Records · Downloads.

    ⚠ **`Plans to end` IS ITS OWN TILE AND ITS DETAIL LINE SAYS WHO ENDS
    THEM.** A tile reading *2 to end* over a runbook that cannot end one is the
    mirror of hard-won law 2 — a live-looking number behind a door that does not
    open — so the number carries the sentence.

    ⚠ **THE GUARDED PLANS ARE IN THE COUNTS AND HAVE NO ROWS** (`BR-RBS-035`).
    `view.counts` is the engine's own and already includes them; tiles drawn
    from `len(records)` would lose every disputed account.
    """
    missed = dict(view.set_results.get(STEP_MISSED, {}))
    count = dict(view.set_results.get(STEP_COUNT, {}))
    currency = _currency_of(missed.get("plans", {}))

    return [
        Block(
            block="kpis",
            payload={
                "tiles": [
                    {
                        "id": "in_flight",
                        "label": "Plans in flight",
                        "value": {"kind": "text", "text": str(missed.get("plans_walked", 0))},
                    },
                    {
                        "id": "behind",
                        "label": "Behind",
                        "value": {"kind": "text", "text": str(missed.get("plans_behind", 0))},
                        "detail": f"{missed.get('instalments_missed', 0)} instalments missed",
                    },
                    {
                        "id": "missed_value",
                        "label": "Missed value",
                        "value": {
                            "kind": "money",
                            "amount": missed.get("missed_value", "0.0000"),
                            "currency": currency,
                        },
                    },
                    {
                        "id": "warn",
                        "label": "To warn",
                        "value": {"kind": "text", "text": str(count.get("to_warn", 0))},
                        "detail": "Planned — nothing is sent until this run is approved",
                    },
                    {
                        "id": "void",
                        "label": "Plans to end",
                        "value": {"kind": "text", "text": str(count.get("to_void", 0))},
                        # ⚠ THE SENTENCE THAT KEEPS THE NUMBER HONEST.
                        "detail": "A person ends a plan on the account",
                    },
                ]
            },
        ),
        Block(
            block="breakdown",
            payload={
                "heading": "By standing",
                "columns": [
                    {"key": "standing", "label": "Standing"},
                    {"key": "plans", "label": "Plans"},
                    {"key": "instalments", "label": "Instalments missed"},
                ],
                "rows": _by_standing(view, count),
            },
        ),
        Block(
            block="records",
            payload={
                "columns": [
                    {"key": "account", "label": "Account"},
                    {"key": "missed", "label": "Missed"},
                    {"key": "value", "label": "Value"},
                    {"key": "outcome", "label": "Outcome"},
                    {"key": "why", "label": "Why"},
                    {"key": "fix", "label": "Fix"},
                ],
                "rows": [
                    _record_row(record, missed.get("plans", {}), currency)
                    for record in view.records
                ],
                "total": len(view.records),
                "empty": {
                    "title": "No plan is in flight.",
                    "helper": "Nobody on this utility is paying arrears by instalments.",
                },
            },
        ),
        Block(
            block="downloads",
            payload={
                "files": [
                    {"name": "Warned", "outcome": OUTCOME_WARNED},
                    {"name": "Plans to end", "outcome": OUTCOME_TO_VOID},
                ],
                "stated_absences": _absences(count),
            },
        ),
    ]


def _absences(count: dict[str, Any]) -> list[str]:
    """What this run could NOT do, each with its figure (hard-won law 7).

    The first sentence is the one that matters and it is unconditional: this
    runbook has no way to end a plan, and a result that did not say so would let
    a clerk believe the plans were ended.
    """
    out = [
        "this run cannot end a plan. It works out which plans are due to end and a person "
        "ends each one on the account.",
    ]
    if not count.get("settings_readable", True):
        out.append(
            "this utility's plan rules could not be read, so nothing was warned or ended. "
            "It is not being treated as nothing to do."
        )
    return out


def _by_standing(view, count: dict[str, Any]) -> list[dict[str, Any]]:
    """`{id, cells}` rows — `BreakdownBlock` reads `columns` and nothing else.

    Kept separate from the counting so the sum stays testable on its own: the
    figure is what a person checks, and wrapping it in cell objects would make
    every assertion about it an assertion about markup (`DEF-RBS-4352`).
    """
    tally: dict[str, dict[str, int]] = {}
    for record in view.records:
        if record.step_key != STEP_WARN:
            continue
        word = _standing_word(record.outcome)
        row = tally.setdefault(word, {"plans": 0, "instalments": 0})
        row["plans"] += 1
        row["instalments"] += int(dict(record.data or {}).get("misses") or 0)
    return [
        {
            "id": word,
            "cells": {
                "standing": {"kind": "text", "text": word},
                "plans": {"kind": "text", "text": str(row["plans"])},
                "instalments": {"kind": "text", "text": str(row["instalments"])},
            },
        }
        for word, row in sorted(tally.items())
    ]


def _standing_word(outcome: str) -> str:
    """The outcome as a word for a table heading. No rule id (B14 rule 32)."""
    return {
        OUTCOME_CURRENT: "In good standing",
        OUTCOME_WARNED: "Behind — warned",
        acts.OUTCOME_PLANNED: "Behind — warning planned",
        OUTCOME_TO_VOID: "Due to end",
        OUTCOME_ALREADY_WARNED: "Already warned",
        OUTCOME_NOT_CONFIGURED: "Not set up",
        OUTCOME_SKIPPED: "Not looked at",
    }.get(outcome, outcome.replace("_", " "))


def _record_row(record, plans: dict[str, Any], currency: str) -> dict[str, Any]:
    """One `{id, cells}` row. `decided_by_rule` travels in `meta` (B14 rule 32)."""
    plan = plans.get(str(record.subject.subject_id), {})
    return {
        "id": f"{record.subject.subject_id}:{record.step_key}",
        "cells": {
            # The account NUMBER, never the id (B14 rule 31).
            "account": {"kind": "text", "text": record.subject.label},
            "missed": {"kind": "text", "text": str(plan.get("misses", 0))},
            "value": {
                "kind": "money",
                "amount": plan.get("missed_value", "0.0000"),
                "currency": plan.get("currency") or currency,
            },
            "outcome": {"kind": "text", "text": _standing_word(record.outcome)},
            "why": {"kind": "text", "text": record.reason},
            "fix": (
                {"kind": "link", "label": "Open account", "to": record.fix_route}
                if record.fix_route
                else {"kind": "text", "text": ""}
            ),
        },
        "meta": {"decided_by_rule": record.decided_by_rule, "step": record.step_key},
    }


# ── small helpers ─────────────────────────────────────────────────────────


def _record_data(plan: dict[str, Any], *, key: str | None = None, **extra) -> dict[str, Any]:
    data = {
        "misses": plan.get("misses"),
        "missed_value": plan.get("missed_value"),
        "earliest_missed_on": plan.get("earliest_missed_on"),
        "next_due_on": plan.get("next_due_on"),
    }
    if key:
        data["idempotency_key"] = key
    data.update(extra)
    return data


def _plural(count: int, word: str) -> str:
    """*1 instalment* · *2 instalments* — a sentence, not a template with an (s)."""
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def _currency_of(plans: dict[str, Any]) -> str:
    """The tenant's ONE currency (`BR-TEN-042`), off the plans' own rows."""
    for row in plans.values():
        if row.get("currency"):
            return str(row["currency"])
    return "USD"


def _channels(ctx: Any) -> tuple[str, ...]:
    """`RB-125`'s *Channel: Email, then post*, as a parameter."""
    raw = str(ctx.params.get("channels") or "email_then_post")
    return ("email", "pdf_print") if raw == "email_then_post" else (raw,)


def _outcome(engine_outcome: str, done_word: str) -> str:
    """The engine's word, in this runbook's vocabulary.

    ⚠ **`planned` STAYS `planned`.** Collapsing it into `warned` would make a dry
    run and a live one read identically on the result screen, which is the one
    thing wave `M`'s month-long soak exists to look at.
    """
    return {
        acts.OUTCOME_DONE: done_word,
        acts.OUTCOME_ALREADY: OUTCOME_ALREADY_WARNED,
        acts.OUTCOME_FAILED: OUTCOME_FAILED,
        acts.OUTCOME_HELD: OUTCOME_HELD,
    }.get(engine_outcome, engine_outcome)


def _money(value: Any, fallback: Decimal | None) -> Decimal | None:
    """A `Decimal` or nothing. **Never a float** (hard rule 2)."""
    if value is None or value == "":
        return fallback
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        raise TypeError(
            "money arrived as a float. Hard rule 2: stored to 4 decimals, displayed to 2, and "
            "never a float — and a runbook parameter lives in jsonb, where no column type will "
            "catch it."
        )
    return Decimal(str(value))


def _stored(value: Decimal) -> str:
    """Four decimals, which is what money IS stored at. The renderer shows two."""
    return f"{value.quantize(Decimal('0.0001')):f}"


RUNBOOK = RunbookDefinition(
    key=RUNBOOK_KEY,
    name="Payment plans",
    kind=models.KIND_ACTION,
    category="collections",
    # ⚠ `payment_plan` IS NOT ONE OF THE TWELVE SUBJECT TYPES — see divergence 2.
    # `uq_one_live_plan_per_account` makes the account and the live plan the same
    # set, so nothing is lost and no thirteenth type is minted.
    subject_type="account",
    unit_of_work="plan in flight",
    triggers=(models.TRIGGER_SCHEDULE, models.TRIGGER_MANUAL),
    tags=("Payments", "notices"),
    parameters=(
        Parameter(name="as_of", type=PARAM_TEXT, label="Business day", required=True),
        Parameter(
            name="channels",
            type=PARAM_ENUM,
            label="Channel",
            required=True,
            default="email_then_post",
            choices=("email_then_post", "email", "pdf_print"),
        ),
        Parameter(
            name="most_per_run",
            type=PARAM_INTEGER,
            label="Most per run",
            required=True,
            default=200,
        ),
        Parameter(
            name="frequency_hours",
            type=PARAM_INTEGER,
            label="Treat runs within",
            required=True,
            default=24,
        ),
    ),
    # ⚠ ABSOLUTE, AND EVALUATED BEFORE STEP 1 (`BR-RBS-012`). `RBS-004.4` draws
    # each DISABLED with its reason rather than hiding it.
    guards=(
        Guard(key="sample", label="Never include: Sample", applies=guard_sample),
        Guard(key="dispute", label="Never include: Dispute", applies=guard_dispute),
    ),
    resolve=resolve,
    report=report,
    steps=(
        Step(key=STEP_MISSED, label=STEP_LABELS[STEP_MISSED], mode=MODE_SET, run=step_missed),
        Step(key=STEP_COUNT, label=STEP_LABELS[STEP_COUNT], mode=MODE_SET, run=step_count),
        Step(
            key=STEP_WARN,
            label=STEP_LABELS[STEP_WARN],
            mode=MODE_PER_RECORD,
            run=step_warn,
            writes=True,
        ),
        Step(
            key=STEP_VOID,
            label=STEP_LABELS[STEP_VOID],
            mode=MODE_PER_RECORD,
            run=step_void,
            # ⚠ TRUE THOUGH IT WRITES NOTHING — see `step_void`'s docstring.
            writes=True,
        ),
    ),
    # ⚠ ONE PORT, WHICH IS `US-RBS-035` §5's OWN LIST. Voiding a plan is
    # payments' act and has no port; a fifteenth is a reviewed interface change.
    ports=("queue_notice",),
)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-035 (EP-RBS-05; CR-075 wave R′, the payments half)
# generated: 2026-09-07 by the CR-075 wave R′ payments build lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint — the run/approve/stop routes are wave D's) E=n/a(no screen — phase 5 declares NO frontend code) F✔ G✔ H=n/a(no 🔒 path: the idempotency KEY is composed in engine/acts.py and the schedule's arithmetic is customers', frozen as GT-47)
# gates: pytest tests/test_us_rbs_035_payment_plans.py · pytest tests/test_us_rbs_015_conformance.py · G115 · G6 (no clock read — as_of is a parameter)
# exceptions: DISABLED FOR LIVE — no runbook is on engine.acts.LIVE_ENABLED_RUNBOOKS · four steps rather than the card's six (divergence 1) · **THE VOID IS NOT PERFORMED**: no port writes `payment_plans.status` and there is no `voided` status to write (`OQ-RBS-1740`, OPEN) — the plan reaches `to_void` with its rule and a route, and the result says so in a clerk's words · the subject is an `account` because `payment_plan` is not one of the twelve subject types (divergence 2)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
