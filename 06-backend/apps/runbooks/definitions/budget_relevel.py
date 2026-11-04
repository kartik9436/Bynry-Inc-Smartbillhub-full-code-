# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-044 (EP-RBS-05) — CR-075: runbook 33, *Budget billing
#           re-level*. The one template the design draws Unavailable.
# Rules:    BR-RBS-002 (an Action holds an allow-list drawn from the named
#           ports) · BR-RBS-003 (dry and live are ONE path) · BR-RBS-004 (an
#           Action always produces a PLAN first) · BR-RBS-005 (the approval
#           must match the plan as it stands) · BR-RBS-006 (a cap REFUSES the
#           run, never truncates it) · BR-RBS-010 (every record states the rule
#           that decided it) · BR-RBS-011 (a failure names its fix route,
#           tenant-relative) · BR-RBS-012 (a guard is absolute) · BR-RBS-015
#           (the runbook is the audit actor) · BR-RBS-018 (a money-bearing
#           action carries a SECOND approval — OQ-RBS-1732 CLOSED, PO
#           2026-09-06: *"every money action, no threshold"*) · BR-RBS-020 (the
#           report is composed at close and frozen) · BR-RBS-021 (twelve
#           blocks) · BR-RBS-022 (a write is a NAMED port; a fifteenth is a
#           reviewed interface) · BR-RBS-039 (every foreign read through a seam
#           this module owns) · BR-BIL-017 / OQ-068 (level = trailing-12-month
#           average, whole $; auto re-level at ±20% drift each 6 months;
#           per-account override bounded ±30% — every parameter a tenant
#           setting) · BR-BIL-021 (every budget parameter is tenant config,
#           read and never defaulted) · BR-REP-001 (no unlabelled money number)
#           · CLAUDE.md hard rule 2 (money stored to 4 decimals, shown to 2) ·
#           hard rule 6 (idempotency) · hard rule 7 (every money action writes
#           audit_log) · hard-won law 2's mirror (a hold needs the test that
#           fires when it expires) · law 7 · B14 rules 31, 32, 33
# Golden:   ❄️ GT-24 (B5 FROZEN 2026-08-08) — trailing-12 $2,904 ÷ 12 → level
#           **$242**. This runbook RE-USES that arithmetic through
#           `apps.billing.budget.compute_level` and re-implements none of it.
# Tests:    06-backend/tests/test_us_rbs_044_budget_relevel.py
# Impacts:  apps/runbooks/definitions/__init__.py (the one line that registers
#           it) · apps/runbooks/seams/billing_seam.py ·
#           apps/billing/selectors.py ·
#           04-docs/05-modules/17-runbooks/11-catalogue/
#           RB-133-budget-billing-re-level.md
# ───────────────────────────────────────────────────────
"""Runbook 33 — **Budget billing re-level**. An ACTION, and it cannot re-level.

`RB-133`'s whole commitment, and the card carries one sentence and no more:

> A clerk sees each budget-billing account's current level, the level the last
> twelve months support, and the change queued behind approval **with the
> customer told first**.

⚠ **THE CENTRAL ACT HAS NO PORT, AND THAT IS RECORDED RATHER THAN WORKED
AROUND.** `interfaces.PORTS` holds fourteen names and **not one of them moves a
budget level**; `billing`'s only port is `apply_fee`, which raises a draft fee
bill. A fifteenth port is a REVIEWED INTERFACE under `BR-RBS-022` — *"not a line
added on the way past"* — with its row in the schema brief, so this lane does
not add one. `apps.billing.budget_service.relevel` exists and is billing's own
act; reaching into it from here would be exactly the cross-module write
`BR-RBS-039` and `G115` exist to refuse.

So step 4 below **records the refusal by name** and the report says it in the
clerk's own words. That is `RB-125`'s posture on voiding a plan and `RB-122`'s
on suppressing a channel, and it is the honest shape: a run of this runbook
today produces the two numbers the card asks for and changes nothing.

⚠ **AND THEREFORE NOBODY IS TOLD EITHER, WHICH IS THE HALF THAT NEEDED A
DECISION.** The card's order is *told first, then changed*. That order is right
when a change can fail — a customer warned about a change that then fails is
recoverable; a payment that moves with no warning is not. **But when the change
is known impossible BEFORE the run starts** — and it is, statically, because
there is no port at all — queueing the notice would tell a customer their
payment is changing when nothing can change it. So step 3 asks whether the level
change is REACHABLE and holds the notice when it is not, with its reason on the
row. Nothing is sent about a change that cannot be made.

⚠ **THE HOLD CARRIES THE TEST THAT FIRES WHEN IT EXPIRES** (hard-won law 2's
mirror, `DEF-CWP-3925`). `test_us_rbs_044_budget_relevel.py` asserts that no
port in `interfaces.PORTS` applies a budget level, BY NAME. The day one is
added that case goes RED and names this file — which is the only thing that
stops a hold rotting quietly into a live screen behind a dead control.

WHAT IS COMPUTED HERE, AND WHAT IS DELIBERATELY NOT
----------------------------------------------------
**Nothing about the level's arithmetic is re-implemented.** The level is
`apps.billing.budget.compute_level` — ❄️ `GT-24`, finance-signed: $2,904 over
twelve months rounds half-up to a level of **$242**. The drift band, the cadence
and the averaging window are the tenant's own S69 settings, read through the
billing seam and **never defaulted** (`BR-BIL-021`: an unreachable
`relevel_drift_pct` is not twenty). A second copy of any of those figures here
would be free to drift from the one a tenant's Settings screen shows.

What this runbook does own is the QUESTION — *which accounts should move, and by
how much* — and the two decisions the card's sentence needs:

1. **A level with too little history is not computed at all.** `BR-BIL-017`'s
   eligibility window is the divisor, and an account with nine months of bills
   under a twelve-month window has no supportable level. Averaging what it has
   would set what a customer pays for a year off a number the tenant's own rule
   says is not enough. It is reported as *not enough history* with its
   fraction — *9/12 months* — which is `budget.eligibility`'s own sentence.
2. **An account carrying an OVERRIDE is walked, not guarded out, and its row
   says what actually moves.** A re-level moves `level`; what the customer pays
   is `effective_level`, which prefers the override. So on an overridden account
   the computed level moves and the payment does not — and the ±30% override
   bound is measured against the computed level, so leaving it stale would make
   the next override validated against a number a year out of date. Guarding
   them out would have been the tidier build and the wrong one.

WHAT THE CARD SAYS THIS RUNBOOK WAITS ON, AND WHAT THAT IS IN CODE
-------------------------------------------------------------------
*"Waits on: the budget billing capability switched on for the tenant."* The
Templates wireframe draws this card **Unavailable** — *"Budget billing is
switched off for you"* — with **+ Add** disabled carrying *"Needs budget
billing"*, and the source calls it *"the one card worth arguing about"*.

⚠ **THAT STATE IS NOT REACHABLE IN CODE TODAY AND THIS RUNBOOK DOES NOT MAKE IT
SO.** `selectors.templates()` serves `state` with two values and
`unavailable_reason: None` for every template, and says why in its own
docstring: *"a template is unavailable when it needs a switched-off capability
… which is a read of the tenant's settings through the tenancy seam that no
shipped runbook declares and no seam yet answers"*. This runbook is the first to
NEED it, so the absence stops being theoretical — it is `OQ-RBS-1759`, and until
it is answered a tenant with budget billing switched off sees this template as
*Not added* rather than as *Unavailable*. **Nothing is dangerous about that
today**: a run on such a tenant pins zero accounts and says so in words. It is
recorded so the next lane meets it as a written absence rather than as a
surprise.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from apps.runbooks import models
from apps.runbooks.contract import (
    MODE_PER_RECORD,
    MODE_SET,
    PARAM_ENUM,
    PARAM_INTEGER,
    PARAM_REF_SETTING,
    Block,
    Finding,
    Guard,
    Parameter,
    RunbookDefinition,
    Step,
    SubjectRef,
)
from apps.runbooks.definitions import _money_gate
from apps.runbooks.engine import acts, duplicates
from apps.runbooks.seams import billing_seam, customers_seam, tenancy_seam

KEY = "budget_relevel"

ZERO = Decimal("0")

# ── the four steps, in the card's own order ───────────────────────────────

STEP_PROGRAMME = "the_budget_programme"
STEP_SUPPORTED = "level_the_year_supports"
STEP_TELL = "tell_the_customer"
STEP_APPLY = "apply_the_new_level"

STEP_LABELS = {
    STEP_PROGRAMME: "The budget programme",
    STEP_SUPPORTED: "The level the last twelve months support",
    STEP_TELL: "Tell the customer",
    STEP_APPLY: "Apply the new level",
}

#: What a record's row says happened to this account.
OUTCOME_MOVES = "moves"
OUTCOME_INSIDE_BAND = "inside_band"
OUTCOME_NOT_AT_CADENCE = "not_at_cadence"
OUTCOME_TOO_LITTLE_HISTORY = "too_little_history"
OUTCOME_HELD = "held"
OUTCOME_QUEUED = "queued"
OUTCOME_NOT_APPLIED = "not_applied"
OUTCOME_ALREADY = "already"

#: Tenant-relative (`BR-RBS-011`) — the shell prefixes the tenant.
FIX_BUDGET = "billing"
FIX_SETTINGS_BUDGET = "settings/budget-billing"

#: ⚠ **THE PORT THAT DOES NOT EXIST, NAMED SO THE ABSENCE IS GREPPABLE.** No
#: entry in `interfaces.PORTS` moves `account_budget_status.level`. This
#: constant is what `test_us_rbs_044_budget_relevel.py` asserts is still absent,
#: so the day a fifteenth port arrives the suite goes red and names this file
#: rather than leaving the refusal below to rot into a lie (hard-won law 2's
#: mirror — a hold with no expiry test is a promise nobody is keeping).
PORT_THAT_WOULD_APPLY_A_LEVEL = "relevel_budget"

#: `work_items.weight` is an INTEGER and a screen turns it into a word (B14 rule
#: 32). A level that should have moved and did not is money a utility is not
#: collecting every month until somebody does it by hand — above routine, below
#: anything that stops a bill.
WEIGHT_MOVES = 45


@dataclass
class _StepResult:
    items: dict[str, dict[str, Any]] = field(default_factory=dict)
    checked: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"reached": True, "items": dict(self.items), "checked": dict(self.checked)}


def _set(ctx_or_view, step: str) -> dict[str, Any]:
    return dict(ctx_or_view.set_results.get(step) or {})


def _items(ctx_or_view, step: str) -> dict[str, dict[str, Any]]:
    return dict(_set(ctx_or_view, step).get("items") or {})


def _checked(ctx_or_view, step: str) -> dict[str, Any]:
    return dict(_set(ctx_or_view, step).get("checked") or {})


def _programme(ctx) -> dict[str, Any]:
    """The enrolled accounts and the tenant's S69 rules, read ONCE per run.

    `resolve()` and three steps all need it, and asking billing four times would
    be four reads that can disagree about who is on the programme inside a
    single run — `BR-RBS-009` pins the scope and this is the same discipline one
    layer down.
    """
    cached = ctx.set_results.get("_programme")
    if cached is None:
        cached = billing_seam.budget_programme()
        ctx.set_results["_programme"] = cached
    return cached


def _accounts(ctx) -> dict[str, dict[str, Any]]:
    return {str(one["account_id"]): one for one in (_programme(ctx).get("accounts") or [])}


def _settings(ctx) -> dict[str, Any]:
    return dict(_programme(ctx).get("settings") or {})


def _decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (ArithmeticError, ValueError):  # pragma: no cover — defensive
        return None


def _stored(value: Decimal) -> str:
    """4 decimals, the way every money field in this product is WRITTEN."""
    return str(value.quantize(Decimal("0.0001")))


def _display(value: Any) -> str:
    """2 decimals — what a person READS (hard rule 2: stored 4, displayed 2).

    ⚠ **A SENTENCE IS A DISPLAY AND THE RENDERER CANNOT ROUND IT.** A money CELL
    goes through `MoneyCell` and is shown at two; a money figure inside a
    sentence a clerk reads — *"$268.00 would become $282.00"* — is a string this
    module builds, so the rounding is this module's. The first draft of these
    rows read *"268.0000 would become 282.0000"*, which is the stored form on a
    screen and is the breach.
    """
    amount = _decimal(value)
    if amount is None:
        return "—"
    return str(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _as_of(ctx) -> dt.date:
    """This run's business date. **A clock is never read here** (`BR-TEN-043`,
    gate `G6`) — `tenancy_seam.today()` is the tenant's own date, so a re-level
    evaluated for last Tuesday takes last Tuesday's cadence answer."""
    return tenancy_seam.today()


def _months_between(start: dt.date | None, end: dt.date) -> int:
    """Whole calendar months, the same arithmetic `budget_service` uses.

    ⚠ **A `None` START IS NOT ZERO MONTHS.** An account with no
    `last_leveled_at` has never been re-levelled, and treating that as *levelled
    today* would hold every such account outside its cadence for ever. The
    caller falls back to `enrolled_on` and the step reports when neither is
    there — see `step_level_the_year_supports`.
    """
    if start is None:  # pragma: no cover — the caller checks first
        return 0
    return (end.year - start.year) * 12 + (end.month - start.month)


def _date(value: Any) -> dt.date | None:
    if not value:
        return None
    try:
        return dt.date.fromisoformat(str(value))
    except ValueError:  # pragma: no cover — defensive
        return None


# ── the guard, absolute and evaluated before step 1 (`BR-RBS-012`) ────────


def guard_sample(ctx: Any, subject: SubjectRef) -> bool:
    """`BR-TEN-056`'s seeded records are not this utility's own customers.

    A run that re-levelled them would put sample accounts on a plan a clerk is
    asked to approve. The flag is asked of `customers` rather than read off the
    budget row, because the budget table carries no `is_sample` of its own and a
    second source for one fact is a second answer.
    """
    cached = ctx.set_results.get("_sample_accounts")
    if cached is None:
        cached = customers_seam.sample_account_ids()
        ctx.set_results["_sample_accounts"] = cached
    return str(subject.subject_id) in cached


# ── step 1 · the budget programme ─────────────────────────────────────────


def step_the_budget_programme(ctx, subjects) -> dict[str, Any]:
    """1 · SET — who is on the programme, and under which of the tenant's rules.

    ⚠ **THE SETTINGS ARE REPORTED, NOT COPIED.** `RBR-03`: policy lives in
    Settings and is never duplicated on a card. What travels here is what the
    run READ, so a clerk looking at a six-month-old report can see the band the
    decision was made under — which is `BR-RBS-038`'s pinning applied to the
    numbers rather than to the definition.

    ⚠ **AN EMPTY PROGRAMME IS AN ANSWER AND NOT A FAULT.** A utility that has
    not switched budget billing on has nobody enrolled, and the report says
    *"nobody is on budget billing yet"* rather than drawing a clean verdict over
    an empty set.
    """
    walked = {str(one.subject_id) for one in subjects}
    rows = _accounts(ctx)
    settings = _settings(ctx)
    overridden = sum(
        1 for key, row in rows.items() if key in walked and row.get("level_override") is not None
    )
    return _StepResult(
        items={},
        checked={
            "on_the_programme": len(rows),
            "walked": len(walked),
            "guarded_as_sample_records": len(rows) - len(walked),
            "carrying_an_override": overridden,
            # The tenant's own S69 figures, as READ (`BR-BIL-021`).
            "averaging_window_months": settings.get("eligibility_months"),
            "drift_band_pct": str(settings.get("relevel_drift_pct")),
            "cadence_months": settings.get("relevel_cadence_months"),
            "level_rounding": settings.get("level_rounding"),
        },
    ).as_dict()


# ── step 2 · the level the last twelve months support ─────────────────────


def step_level_the_year_supports(ctx, subjects) -> dict[str, Any]:
    """2 · SET — recompute every walked account's level, and decide if it moves.

    ⚠ **THE ARITHMETIC IS `apps.billing.budget.compute_level` AND IS NOT
    RE-IMPLEMENTED HERE.** ❄️ `GT-24` is finance-signed — $2,904 over twelve
    months is a level of **$242** — and a second implementation of a frozen
    figure is exactly what `B5`'s freeze exists to prevent. The seam hands over
    the same trailing actuals `budget_service.relevel` reads, so the number this
    runbook shows a clerk and the number billing would write cannot differ.

    ⚠ **BOTH GATES ARE THE TENANT'S AND BOTH ARE REPORTED.** `BR-BIL-017` moves
    a level only AT CADENCE and only on a drift BREACH, and `relevel_due`
    applies them in that order. An account inside the band and an account inside
    the cadence are two different answers with two different next steps, so they
    are two outcomes and never one *no change*.

    ⚠ **NOT ENOUGH HISTORY IS THE THIRD ANSWER AND IT IS NOT A FAILURE.** An
    account with nine months of bills under a twelve-month window has no
    supportable level; averaging nine would set a year of payments off a number
    the tenant's own eligibility rule calls insufficient.
    ⚠ **THE ARITHMETIC IS ASKED THROUGH THE SEAM AND IS NOT IMPORTED HERE, AND
    `G115` IS WHAT MADE THAT TRUE.** The first build of this step did
    `from apps.billing import budget` and called `compute_level`,
    `drift_fraction` and `relevel_due` itself — a foreign import outside the two
    lawful doors, refused by file and by line before it could merge
    (`BR-RBS-039`). The fix was not to move the import: it was to move the
    QUESTION. `billing_seam.budget_level_decision` asks *what level do these
    actuals support and does it move*, and billing applies its own two gates in
    its own order, so a lane here cannot reorder `BR-BIL-017` by accident.
    """
    walked = [str(one.subject_id) for one in subjects]
    rows = _accounts(ctx)
    settings = _settings(ctx)
    as_of = _as_of(ctx)

    months = int(settings.get("eligibility_months") or 0)
    drift_pct = _decimal(settings.get("relevel_drift_pct")) or ZERO
    cadence = int(settings.get("relevel_cadence_months") or 0)
    rounding = str(settings.get("level_rounding") or "")

    items: dict[str, dict[str, Any]] = {}
    moves = inside_band = not_at_cadence = short_history = 0
    for account_id in walked:
        row = rows.get(account_id) or {}
        history = billing_seam.budget_trailing_actuals(account_id, months=months)
        actuals = [Decimal(one) for one in (history.get("actuals") or [])]
        held = int(history.get("months_of_history") or 0)
        current = _decimal(row.get("level")) or ZERO
        effective = _decimal(row.get("effective_level")) or current

        record: dict[str, Any] = {
            "account_no": row.get("account_no"),
            "current_level": _stored(current),
            "effective_level": _stored(effective),
            "override": row.get("level_override"),
            "currency": row.get("currency") or history.get("currency"),
            "months_of_history": held,
            "months_required": months,
            "variance_balance": row.get("variance_balance"),
        }

        if held < months or not actuals:
            record.update(
                {
                    "outcome": OUTCOME_TOO_LITTLE_HISTORY,
                    "supported_level": None,
                    "reason": f"{held}/{months} months of bills — not enough to average.",
                }
            )
            short_history += 1
            items[account_id] = record
            continue

        # A NULL `last_leveled_at` means never re-levelled, which is not age
        # zero — fall back to the enrolment date, and say which was used.
        since = _date(row.get("last_leveled_at"))
        since_field = "last_leveled_at"
        if since is None:
            since = _date(row.get("enrolled_on"))
            since_field = "enrolled_on"
        months_since = _months_between(since, as_of) if since else cadence

        decision = billing_seam.budget_level_decision(
            actuals=actuals,
            months=months,
            rounding=rounding,
            current_level=current,
            drift_pct=drift_pct,
            months_since_last_level=months_since,
            cadence_months=cadence,
        )
        # ⚠ **BILLING'S TWO REFUSALS COME BACK AS ANSWERS, NOT AS EXCEPTIONS.**
        # A zero current level cannot be a denominator and an unknown rounding
        # mode stops an enrolment; either raised inside this loop would fail the
        # whole record in its savepoint and read on screen as *this account
        # errored*, when the truth is *this account has no level to measure a
        # change against*. The sentence billing gives is the one the row shows.
        if decision.get("refused"):
            record.update(
                {
                    "outcome": OUTCOME_TOO_LITTLE_HISTORY,
                    "supported_level": decision.get("supported_level"),
                    "reason": "this account has no level to measure a change against.",
                }
            )
            short_history += 1
            items[account_id] = record
            continue

        supported = _decimal(decision.get("supported_level")) or ZERO
        drift = _decimal(decision.get("drift_fraction")) or ZERO
        record.update(
            {
                "supported_level": _stored(supported),
                "movement": _stored(supported - current),
                "drift_pct": str(
                    (drift * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                ),
                "months_since_last_level": months_since,
                "months_since_measured_from": since_field,
                "trailing_total": _stored(sum(actuals, ZERO)),
            }
        )
        if months_since < cadence:
            record["outcome"] = OUTCOME_NOT_AT_CADENCE
            record["reason"] = (
                f"levelled {months_since} month{'s' if months_since != 1 else ''} ago; "
                f"the utility re-levels every {cadence}."
            )
            not_at_cadence += 1
        elif decision.get("moves"):
            record["outcome"] = OUTCOME_MOVES
            record["reason"] = (
                f"{record['drift_pct']}% away from what the last {months} months support."
            )
            moves += 1
        else:
            record["outcome"] = OUTCOME_INSIDE_BAND
            record["reason"] = (
                f"{record['drift_pct']}% away, inside the utility's {drift_pct}% band."
            )
            inside_band += 1
        items[account_id] = record

    return _StepResult(
        items=items,
        checked={
            "accounts_measured": len(walked),
            "levels_that_move": moves,
            "inside_the_band": inside_band,
            "not_at_cadence": not_at_cadence,
            "too_little_history": short_history,
            # Hard-won law 7 — the reads this step made, so a slow run has a
            # number rather than a feeling. One per walked account, by design.
            "trailing_reads": len(walked),
        },
    ).as_dict()


# ── step 3 · tell the customer ────────────────────────────────────────────


def _can_apply(ctx) -> bool:
    """Is there a port that could move a budget level? **No, and see the docstring.**

    Asked of the run's own context rather than of a constant, so the answer is
    about the ports this runbook was actually handed. When a fifteenth port is
    reviewed and this runbook declares it, this returns True and steps 3 and 4
    both change behaviour without either being rewritten.
    """
    return PORT_THAT_WOULD_APPLY_A_LEVEL in getattr(ctx, "ports", {})


def _run_level(ctx):
    """Has an earlier run of THIS job already done this today? (`OQ-RBS-1737`.)

    The PO moved this check from the record to the run on 2026-09-06, and an
    unapproved earlier run is a WARNING rather than a skip — a plan still
    sitting on somebody's screen is not a duplicate.
    """
    cached = ctx.set_results.get("_duplicate")
    if cached is None:
        # ⚠ **THE RUN ROW IS WHERE THE RUNBOOK ID AND THE START TIME LIVE, AND
        # `now` IS ITS `started_at` RATHER THAN A CLOCK** (`BR-TEN-043`, gate
        # `G6`): a re-run for last Tuesday must take last Tuesday's answer, and
        # a check reading the wall clock could not be tested at the window's
        # edge at all. `RB-108`'s `_run_level` is the same shape.
        run = models.RunbookRun.objects.filter(pk=ctx.run_id).first()
        if run is None or run.started_at is None:
            cached = duplicates.DuplicateVerdict(verdict=duplicates.VERDICT_NONE)
        else:
            cached = duplicates.check(
                tenant_id=run.tenant_id,
                runbook_id=run.runbook_id,
                now=run.started_at,
                this_run_id=run.pk,
                frequency_hours=int(
                    ctx.params.get("frequency_hours") or duplicates.DEFAULT_FREQUENCY_HOURS
                ),
            )
        ctx.set_results["_duplicate"] = cached
    return cached


def _channels(ctx) -> tuple[str, ...]:
    raw = str(ctx.params.get("channels") or "email_then_post")
    return ("email", "post") if raw == "email_then_post" else (raw,)


def _discriminator(record: dict[str, Any], as_of: dt.date) -> str:
    """This runbook's OWN repeat boundary — **the level being moved to, and the
    month it was decided in.**

    `engine/acts.py` says the composition of this is each runbook's question,
    asked with the real thing in front of it, and this is that answer written
    down rather than inherited.

    Worked: an account moving to **$268** is told once, however many times the
    run is repeated this month — two runs on the same Monday queue **one**
    letter, not two. The same account moving to **$291** at the next cadence six
    months later has a different key and is told again, which is the mirror the
    ladder's `rung` exists for. Drop the level and a customer re-levelled in
    March is never told about the change in September; drop the month and an
    account that goes 242 → 268 → 242 over a year is silent on the third move.
    **The RUN is deliberately not in it** — with the run in the key a retry
    mints a fresh key for every account and everyone is told twice in one
    morning.
    """
    return f"{record.get('supported_level')}@{as_of.isoformat()[:7]}"


def step_tell_the_customer(ctx, subject) -> dict[str, Any]:
    """3 · PER RECORD · **writes** — the card's *with the customer told first*.

    ⚠ **NOBODY IS TOLD ABOUT A CHANGE THAT CANNOT BE MADE.** The card's order is
    told-then-changed and that order is right when a change can fail. It is
    WRONG when the change is known impossible before the run starts, which it is
    today: no port moves a budget level, so a notice here would tell a customer
    their monthly payment is changing when nothing in this product can change
    it. The check is `_can_apply`, and the day a fifteenth port is reviewed this
    branch stops being taken without a line of it being rewritten.

    The engine performs the act when it is reachable: it writes the plan first
    (`BR-RBS-004`), calls the port only if a writer is bound (`BR-RBS-003` —
    `LIVE_ENABLED_RUNBOOKS` is empty for the whole catalogue), and writes the
    audit row naming this runbook and its version (`BR-RBS-015`).
    """
    account_id = str(subject.subject_id)
    record = _items(ctx, STEP_SUPPORTED).get(account_id) or {}
    outcome = str(record.get("outcome") or "")

    if outcome != OUTCOME_MOVES:
        return {
            "outcome": OUTCOME_HELD,
            "decided_by_rule": "Only a level that moves is worth a letter",
            "reason": str(record.get("reason") or "this level is not changing."),
        }

    if not _can_apply(ctx):
        return {
            "outcome": OUTCOME_HELD,
            "decided_by_rule": "Nobody is told about a change that cannot be made",
            "reason": (
                "this product cannot move a budget level yet, so telling this customer "
                "their payment is changing would not be true."
            ),
            "fix_route": FIX_BUDGET,
            "data": {"port_that_is_missing": PORT_THAT_WOULD_APPLY_A_LEVEL},
        }

    verdict = _run_level(ctx)
    if verdict.is_duplicate:  # pragma: no cover — unreachable while the hold stands
        return {
            "outcome": OUTCOME_ALREADY,
            "decided_by_rule": "This job already ran and was approved",
            "reason": verdict.message,
        }

    as_of = _as_of(ctx)
    discriminator = _discriminator(record, as_of)
    supported = _decimal(record.get("supported_level")) or ZERO
    result = acts.perform(  # pragma: no cover — unreachable while the hold stands
        ctx,
        acts.ActRequest(
            port="queue_notice",
            action_kind="queue_notice",
            subject=subject,
            planned_action=(
                f"Tell them the level becomes {_display(record.get('supported_level'))}"
            ),
            discriminator=discriminator,
            decided_by_rule="A budget level changes only after the customer is told",
            reason=str(record.get("reason") or ""),
            amount=supported,
            currency=record.get("currency"),
            payload={
                "runbook_key": ctx.runbook_key,
                "account_id": subject.subject_id,
                "subject_id": subject.subject_id,
                "discriminator": discriminator,
                "actor": acts.actor_for(ctx),
                "channels": tuple(_channels(ctx)),
            },
        ),
    )
    return {  # pragma: no cover — unreachable while the hold stands
        "outcome": OUTCOME_QUEUED,
        "decided_by_rule": "A budget level changes only after the customer is told",
        "reason": str(record.get("reason") or ""),
        "data": {"idempotency_key": result.idempotency_key},
    }


# ── step 4 · apply the new level ──────────────────────────────────────────


def step_apply_the_new_level(ctx, subject) -> dict[str, Any]:
    """4 · PER RECORD — **and it applies nothing, by name.**

    ⚠ **THE REFUSAL IS THE DELIVERABLE.** No entry in `interfaces.PORTS` moves
    `account_budget_status.level`; `billing`'s single port raises a draft fee.
    Adding a fifteenth is a reviewed interface (`BR-RBS-022`), not a line this
    lane writes on the way past, and calling `budget_service.relevel` from here
    would be the cross-module write `G115` refuses. So the row says what would
    have happened, in the clerk's words, and the level does not move.

    ⚠ **THE SECOND APPROVAL IS READ AND REPORTED EVEN THOUGH NOTHING IS
    APPLIED.** `BR-RBS-018` as `OQ-RBS-1732` closed it — *"every money action,
    no threshold"* — and a level is what a customer pays every month for a year.
    Reading it here keeps the shape correct rather than leaving a gate to be
    remembered on the day the port lands, and it puts *waiting for a second
    person* on the screen where a clerk can see it.

    `writes=False` on the step declaration is the truth about this build: there
    is nothing to write with. It is not a Check — the runbook holds
    `queue_notice` and the capability is real — it is an Action whose central
    act has no door yet.
    """
    account_id = str(subject.subject_id)
    record = _items(ctx, STEP_SUPPORTED).get(account_id) or {}
    outcome = str(record.get("outcome") or "")

    if outcome != OUTCOME_MOVES:
        return {
            "outcome": outcome or OUTCOME_INSIDE_BAND,
            "decided_by_rule": "The utility's own drift band and cadence",
            "reason": str(record.get("reason") or ""),
            "data": _row_data(record),
        }

    planned = int(_checked(ctx, STEP_SUPPORTED).get("levels_that_move") or 0)
    approval = _money_gate.second_approval(ctx, planned=planned)

    # ⚠ **THE MISSING DOOR IS SAID FIRST, BEFORE THE MISSING APPROVAL, AND THE
    # ORDER WAS WRONG IN THE FIRST DRAFT.** Both sentences are true on every row
    # today, and a row reading *"waiting for a second person to approve this
    # run"* tells a clerk that approving it is what unblocks the change. It is
    # not: approval would change nothing, because there is no port. Saying the
    # blocking fact first is `BR-RBS-010` — the record states the rule that
    # decided it — and the approval still TRAVELS, in `data`, so the shape is
    # visible on the day the port lands.
    if not _can_apply(ctx):
        return {
            "outcome": OUTCOME_NOT_APPLIED,
            "decided_by_rule": "Nothing in this product moves a budget level yet",
            "reason": (
                f"{_display(record.get('current_level'))} would become "
                f"{_display(record.get('supported_level'))}. "
                "This one has to be changed by hand."
            ),
            "fix_route": FIX_BUDGET,
            "data": {
                **_row_data(record),
                "port_that_is_missing": PORT_THAT_WOULD_APPLY_A_LEVEL,
                "second_approval": bool(approval.get("approved")),
                "second_approval_reason": str(approval.get("reason") or ""),
            },
        }

    if not approval.get("approved"):  # pragma: no cover — unreachable while the hold stands
        return {
            "outcome": OUTCOME_NOT_APPLIED,
            "decided_by_rule": "A change to what a customer pays needs a second person",
            "reason": str(approval.get("reason") or ""),
            "fix_route": FIX_BUDGET,
            "data": _row_data(record),
        }

    # ⚠ **UNREACHABLE, AND THE `raise` IS DELIBERATE.** If a fifteenth port is
    # ever declared on this runbook without this branch being written, the run
    # must STOP rather than report a level moved that nothing moved. A silent
    # `pass` here is exactly the shape of a check that cannot fail.
    raise NotImplementedError(  # pragma: no cover — no port applies a level
        "OQ-RBS-1760: a port that applies a budget level has been declared and this "
        "step has not been written to call it. Refusing rather than reporting a "
        "change nothing made."
    )


def _row_data(record: dict[str, Any]) -> dict[str, Any]:
    """What the Records table draws for this account. **No database id** (B14
    rule 31) — the account NUMBER is what a clerk reads, and the row states its
    absence rather than falling back to the id when a number is missing."""
    return {
        "account_no": record.get("account_no"),
        "current_level": record.get("current_level"),
        "supported_level": record.get("supported_level"),
        "effective_level": record.get("effective_level"),
        "movement": record.get("movement"),
        "drift_pct": record.get("drift_pct"),
        "currency": record.get("currency"),
        "override": record.get("override"),
        "months_of_history": record.get("months_of_history"),
        "months_required": record.get("months_required"),
        "variance_balance": record.get("variance_balance"),
    }


# ── the report, composed at close and frozen (`BR-RBS-020`) ───────────────


def _tile(tile_id: str, label: str, value: dict[str, Any], detail: str | None = None):
    tile: dict[str, Any] = {"id": tile_id, "label": label, "value": value}
    if detail:
        tile["detail"] = detail
    return tile


def _text(text: str) -> dict[str, Any]:
    return {"kind": "text", "text": text}


def _money_value(amount: Decimal, currency: str | None) -> dict[str, Any]:
    """A money value that DECLARES ITS BASIS (`BR-REP-001`, `DEF-RBS-4350`).

    `priced`: a budget level is **computed and never posted**. `BR-BIL-011` is
    explicit — the monthly posting is the ACTUALS posting and the level never
    reaches the ledger as a price — so a tile labelled *Posting date*, which is
    what the renderer falls back to, would put this figure under a heading it
    does not belong to. That is `DEF-RBS-4350` exactly, one runbook along.
    """
    return {
        "kind": "money",
        "amount": _stored(amount),
        "currency": currency or "",
        "basis": "priced",
    }


def _moving(view) -> list[Any]:
    """The accounts whose level moves, biggest change first — the card's own
    list. Sorted here because a per-record step sees one account and cannot rank
    a set (`BR-RBS-020`: the report is composed at close)."""
    rows = [
        one
        for one in view.records
        if one.step_key == STEP_APPLY
        and (one.data or {}).get("movement") is not None
        and str(one.outcome) in (OUTCOME_NOT_APPLIED,)
    ]

    def key(record):
        movement = _decimal((record.data or {}).get("movement")) or ZERO
        return (-abs(movement), str((record.data or {}).get("account_no") or ""))

    return sorted(rows, key=key)


def report(view) -> list[Block]:
    """Composed at CLOSE from what the steps counted, then frozen (`BR-RBS-020`).

    **Verdict · KPIs · Records · Action · Downloads.** The Records block is the
    card's own sentence — *each budget-billing account's current level, the
    level the last twelve months support, and the change* — so those three
    columns are the point of it and the fourth says what happened.
    """
    programme = _checked(view, STEP_PROGRAMME)
    supported = _checked(view, STEP_SUPPORTED)
    moving = _moving(view)

    on_programme = int(programme.get("on_the_programme") or 0)
    measured = int(supported.get("accounts_measured") or 0)
    moves = int(supported.get("levels_that_move") or 0)
    inside = int(supported.get("inside_the_band") or 0)
    early = int(supported.get("not_at_cadence") or 0)
    short = int(supported.get("too_little_history") or 0)
    overridden = int(programme.get("carrying_an_override") or 0)

    movement = ZERO
    currency = None
    for record in moving:
        movement += _decimal((record.data or {}).get("movement")) or ZERO
        currency = currency or (record.data or {}).get("currency")

    detail: list[str] = []
    if not on_programme:
        detail.append("Nobody is on budget billing yet.")
    if overridden:
        detail.append(
            f"{overridden} carr{'y' if overridden == 1 else 'y'} a level somebody set by hand — "
            "the computed level moves and what they pay does not."
        )
    if short:
        detail.append(f"{short} have too little billing history to average.")
    detail.append("Nothing was changed and nobody was told.")

    return [
        Block(
            block="verdict",
            payload={
                # ⚠ NEVER `Done`. A run of this runbook changes nothing today,
                # and a success word over a run that moved no money is hard-won
                # law 1 — a claim the code does not make.
                "word": "To do" if moves else ("Nothing to do" if measured else "Nobody yet"),
                "tone": "warning" if moves else "neutral",
                "count": (
                    f"{moves} of {measured} level{'s' if measured != 1 else ''} should move."
                    if measured
                    else "No budget-billing accounts."
                ),
                "detail": " ".join(detail),
            },
        ),
        Block(
            block="kpis",
            payload={
                "tiles": [
                    _tile(
                        "on_the_programme",
                        "On budget billing",
                        _text(str(on_programme)),
                        "Enrolled accounts",
                    ),
                    _tile(
                        "moves",
                        "Levels that should move",
                        _text(str(moves)),
                        "Past the drift band, and at cadence",
                    ),
                    _tile(
                        "movement",
                        "Change a month",
                        _money_value(movement, currency) if moving else _text("—"),
                        (
                            "Added up across the accounts that move"
                            if moving
                            else "No level moves this run"
                        ),
                    ),
                    _tile(
                        "inside_the_band",
                        "Inside the band",
                        _text(str(inside)),
                        "Close enough to leave alone",
                    ),
                    _tile(
                        "not_yet_due",
                        "Not yet due",
                        _text(f"{early} early · {short} short"),
                        "Inside the cadence, or too little history",
                    ),
                ]
            },
        ),
        Block(
            block="records",
            payload={
                "columns": [
                    {"key": "account", "label": "Account"},
                    {"key": "now", "label": "Level now", "numeric": True},
                    {"key": "supported", "label": "The year supports", "numeric": True},
                    {"key": "change", "label": "Change", "numeric": True},
                    {"key": "what_happened", "label": "What happened"},
                ],
                "rows": [
                    {
                        "id": str(record.subject.subject_id),
                        "cells": {
                            # B14 rule 31 — the account NUMBER, never its id, and
                            # a stated absence rather than a fallback to one.
                            "account": _text(
                                str(
                                    (record.data or {}).get("account_no")
                                    or "No account number on file"
                                )
                            ),
                            "now": _money_value(
                                _decimal((record.data or {}).get("current_level")) or ZERO,
                                (record.data or {}).get("currency"),
                            ),
                            "supported": _money_value(
                                _decimal((record.data or {}).get("supported_level")) or ZERO,
                                (record.data or {}).get("currency"),
                            ),
                            "change": _money_value(
                                _decimal((record.data or {}).get("movement")) or ZERO,
                                (record.data or {}).get("currency"),
                            ),
                            "what_happened": _text(record.reason),
                        },
                    }
                    for record in moving
                ],
                "total": len(moving),
                # ⚠ **`empty` IS `{title, helper}` AND NOT A STRING** — see
                # `meter_change_out.report` for the whole reasoning and
                # `DEF-RBS-4406` for the guard gap. This is the screen that
                # showed it: on the seeded utility this table is EMPTY, and a
                # string here drew a blank area where the sentence belongs.
                "empty": (
                    {
                        "title": "Every level is where it should be.",
                        "helper": (
                            "No level is far enough from what the last twelve months "
                            "support to be worth moving."
                        ),
                    }
                    if measured
                    else {
                        "title": "Nobody is on budget billing yet.",
                        "helper": "No account on this utility is enrolled on the programme.",
                    }
                ),
            },
        ),
        Block(
            block="action",
            payload={
                "label": "Apply the new levels",
                # B14 rule 6 — a destructive commit carries the danger tier, and
                # this changes what customers pay.
                "tier": "danger",
                "enabled": False,
                # ⚠ B14 rule 33 — a refusal caps at five or six words. The whole
                # reason is in the module docstring, where it belongs.
                "reason": "No door moves a budget level",
            },
        ),
        Block(
            block="downloads",
            payload={
                "files": [
                    {"id": "levels_that_move", "label": "Levels that move", "format": "csv"},
                    {"id": "the_whole_programme", "label": "The whole programme", "format": "csv"},
                ]
            },
        ),
    ]


# ── what the run leaves on somebody's desk (`BR-RBS-022`) ─────────────────


def findings(view) -> list[Finding]:
    """One item per level that should move — and **the ENGINE writes the rows**.

    Every one of these is a change somebody now has to make by hand on `S30`,
    which is exactly what the work list is for. Without them a run of this
    runbook would produce a screen a clerk reads once and a list nobody keeps.

    ⚠ **THE FINGERPRINT IS THE KIND PLUS THE ACCOUNT AND NEVER THE RUN**
    (`BR-RBS-017`). This runbook reports the same account every month until the
    level is changed; with the run in it each month would mint a new row and
    *"waiting since March"* would read as *today* for ever.
    """
    out: list[Finding] = []
    for record in _moving(view):
        data = record.data or {}
        out.append(
            Finding(
                kind="budget_level_should_move",
                title=(
                    f"{data.get('account_no') or 'Account'} — level "
                    f"{_display(data.get('current_level'))} should become "
                    f"{_display(data.get('supported_level'))}"
                ),
                fix_route=record.fix_route or FIX_BUDGET,
                weight=WEIGHT_MOVES,
                subject_ref=str(data.get("account_no") or record.subject.label),
                subject_type=record.subject.subject_type,
                subject_id=str(record.subject.subject_id),
            )
        )
    return out


# ── the pinned scope (`BR-RBS-009`, `BR-RBS-019`) ─────────────────────────


def resolve(ctx):
    """The pinned set: **every account enrolled on budget billing**.

    ⚠ **`off_budget` IS NOT IN THE SET.** `budget.STATUS_OFF_BUDGET` is reachable
    only by an explicit staff act on `S30` — the PO's ruling of 2026-08-11
    removed every automatic drop-off — and re-levelling somebody a person took
    off the programme would undo that act by arithmetic. The seam filters on
    `enrolled` for that reason.

    ⚠ **THE LABEL IS THE ACCOUNT NUMBER, NEVER ITS DATABASE ID** (B14 rule 31,
    and `DEF-3158` is what happens when it is not: `S30`'s own Budget Bills tab
    printed a truncated account id in its first column with no fallback). An
    account with no number on file states the absence.
    """
    return [
        SubjectRef(
            subject_type="account",
            subject_id=str(row["account_id"]),
            label=str(row.get("account_no") or "No account number on file"),
        )
        for row in (_programme(ctx).get("accounts") or [])
    ]


RUNBOOK = RunbookDefinition(
    key=KEY,
    name="Budget billing re-level",
    # ⚠ **AN ACTION, STATED ON THE CARD** — read off the Templates wireframe
    # (`RBS-002` region 9: *pills: Action (danger), Unavailable (neutral) ·
    # Action Billing*), which is the only place either its kind or its category
    # is written down. `BR-RBS-001`: a kind never changes afterwards.
    kind=models.KIND_ACTION,
    category="billing",
    subject_type="account",
    unit_of_work="a budget-billing account",
    # ⚠ **MANUAL ONLY, WHICH IS THE NARROWEST DECLARATION THE CARD SUPPORTS.**
    # `RB-133`'s Trigger row reads *Not yet defined* and its commitment opens
    # *"A clerk sees…"*. A schedule is the obvious guess — the cadence is six
    # months — and a guess is a wider declaration than the card makes, which is
    # a change request rather than a lane's decision (`13-change-process.md`).
    triggers=(models.TRIGGER_MANUAL,),
    tags=(),
    # ⚠ **ONE PORT, AND IT IS NOT THE ONE THIS RUNBOOK IS NAMED AFTER.**
    # `queue_notice` is the card's *"with the customer told first"*. Nothing in
    # `interfaces.PORTS` moves a budget level, and a fifteenth port is a
    # reviewed interface (`BR-RBS-022`) rather than a line added here — so step
    # 4 records the refusal and the module docstring says what it costs.
    ports=("queue_notice",),
    parameters=(
        Parameter(
            name="averaging_window",
            type=PARAM_REF_SETTING,
            label="Averaging window",
            # `RBR-03` — read from Settings (S69), never duplicated on a card.
            # `BR-BIL-017`'s twelve months, and `BR-BIL-021` makes it config.
            setting_key="billing.eligibility_months",
        ),
        Parameter(
            name="drift",
            type=PARAM_REF_SETTING,
            label="Re-level above drift of",
            setting_key="billing.relevel_drift_pct",
        ),
        Parameter(
            name="cadence",
            type=PARAM_REF_SETTING,
            label="Re-level no more often than",
            setting_key="billing.relevel_cadence_months",
        ),
        Parameter(
            name="channels",
            type=PARAM_ENUM,
            label="Channels",
            required=True,
            default="email_then_post",
            choices=("email_then_post", "email", "pdf_print"),
        ),
        Parameter(
            name="most_per_run",
            type=PARAM_INTEGER,
            label="Most per run",
            required=True,
            # ⚠ **100, AND IT IS THE PRODUCT OWNER'S OWN FIGURE.**
            # `OQ-RBS-1731` CLOSED 2026-09-06, verbatim: *"1731 … (b) ship
            # 100"*. A mistake at 100 is 100 customers told the wrong amount
            # rather than 3,000. `BR-RBS-006`: the cap REFUSES the run and never
            # truncates it.
            default=100,
        ),
        Parameter(
            name="frequency_hours",
            type=PARAM_INTEGER,
            label="Treat runs within",
            required=True,
            # The Product Owner's own figure as the default of a parameter —
            # `OQ-RBS-1737`, and see `engine/duplicates.py` for the reading.
            default=24,
        ),
    ),
    guards=(
        # ⚠ ONE GUARD, AND THE ONE THAT IS DELIBERATELY ABSENT MATTERS MORE. An
        # account carrying a level OVERRIDE is NOT guarded out: a re-level moves
        # `level` while `effective_level` keeps the override, so what the
        # customer pays does not change — and the ±30% override bound is
        # measured against the computed level, so leaving it stale would make
        # the next override validated against a year-old number. It is reported
        # on the row instead. See the module docstring, decision 2.
        Guard(key="sample", label="Never include: Sample", applies=guard_sample),
    ),
    resolve=resolve,
    report=report,
    findings=findings,
    steps=(
        Step(
            key=STEP_PROGRAMME,
            label=STEP_LABELS[STEP_PROGRAMME],
            mode=MODE_SET,
            run=step_the_budget_programme,
        ),
        Step(
            key=STEP_SUPPORTED,
            label=STEP_LABELS[STEP_SUPPORTED],
            mode=MODE_SET,
            run=step_level_the_year_supports,
        ),
        Step(
            key=STEP_TELL,
            label=STEP_LABELS[STEP_TELL],
            mode=MODE_PER_RECORD,
            run=step_tell_the_customer,
            # It holds `queue_notice` and would call it — the hold in the step
            # is about the ORDER of two acts, not about the capability.
            writes=True,
        ),
        Step(
            key=STEP_APPLY,
            label=STEP_LABELS[STEP_APPLY],
            mode=MODE_PER_RECORD,
            run=step_apply_the_new_level,
            # ⚠ **`False`, AND IT IS THE TRUTH ABOUT THIS BUILD.** There is no
            # port that moves a budget level, so this step has nothing to write
            # with. Declaring `True` would be a claim the code does not make
            # (hard-won law 1) and would say the capability exists.
            writes=False,
        ),
    ),
)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-044 (EP-RBS-01; CR-075, runbook 33 — RB-133)
# generated: 2026-09-07 by the CR-075 runbooks 28+33 lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint — a runbook needs none) E=n/a(no screen — RBS-004 and RBS-006 are renderers over the definition and the report) F✔ G✔ H=n/a(no 🔒 path — the level arithmetic is apps/billing/budget.py's and is called, never re-implemented; the idempotency DISCRIMINATOR is chosen here and its reasoning is in `_discriminator`)
# exceptions: (1) THE CENTRAL ACT HAS NO PORT. No entry in interfaces.PORTS moves a budget level; a fifteenth is a reviewed interface (BR-RBS-022) and is OQ-RBS-1760, OPEN. Step 4 records the refusal. (2) AND THEREFORE NOBODY IS TOLD EITHER — step 3 holds the notice rather than telling a customer about a change that cannot be made; the hold-expiry test is in the story's test file. (3) An account carrying a level OVERRIDE is walked rather than guarded out, and its row says the computed level moves while the payment does not. (4) The Templates library cannot draw this card Unavailable — no capability read exists (OQ-RBS-1759, OPEN); a run on a tenant with budget billing off pins zero accounts and says so.
# gates: MEASURED 2026-09-07, not claimed — `pytest tests/test_us_rbs_043_meter_change_out.py tests/test_us_rbs_044_budget_relevel.py` **51 passed**, with ELEVEN cases first shown RED on the specific wrong build each docstring names · `G115` (the module's boundary census) names neither of this lane's files; its two failures are `leak_alert.py:838` (landed 7f5c2892, 2026-09-07) and the port count still reading thirteen against fourteen (the port landed dff6b379, the constant was written 815777f0) — both DATED with `git log -S`, both filed as `DEF-RBS-4379` · `G2` code-trace names only `accounting_export.py`'s `US-RBS-042` · `G23` surface-debt **PASS** · `ruff` **All checks passed** · `black --line-length 100` clean · the browser walkthrough `10-scripts/render-checks/rbs-2833-runbooks.mjs` **28 checks, all green in Chromium** · full `run_gates` **89 PASS / 30 FAIL / 2 SKIP**, against a lane-start baseline of **82 / 37 / 2** — seven fewer failures than when this lane started and not one of the thirty names anything it wrote. Three of those thirty were PROVED pre-existing by running them in a worktree at the commit before this lane's first: `test_us_rbs_015_conformance` money-basis (seven tiles in five OTHER runbooks), `test_us_rbs_038` `z_cutover`, and the `RBS-004` setup fixture (wave T's `domain`/`multi` fields, fixture not regenerated).
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
