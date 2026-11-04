# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-029 (EP-RBS-05) — CR-075 wave R′, the payments half:
#           runbook 17, registered as an Action holding three ports, DISABLED
#           for live, guards evaluated BEFORE step 1.
# Rules:    BR-RBS-031 (a debit that fails twice is not retried a third time;
#           the account goes to the ladder) · BR-RBS-016 (the schedule is the
#           tenant's own clock) · BR-RBS-012 (guards are absolute, before any
#           step) · BR-RBS-014 (a SAMPLE record is never acted on) · BR-RBS-010
#           (every record states the rule that decided it, in words) ·
#           BR-RBS-035 (a count for the outcomes with no row) · BR-RBS-003 (dry
#           and live are one path) · BR-PAY-015 (autopay v1 is capture-INTENT:
#           bill issue records an intent dated the due date, and NOTHING drafts
#           money — payments' law, READ and never copied) · BR-PAY-013 (the
#           cash-only / no-autopay privilege) · BR-NOT-005 (a notice is WRITTEN;
#           the dispatcher sends) · CLAUDE.md hard rule 2 (money 4 stored, 2
#           displayed, never a float)
# Tests:    06-backend/tests/test_us_rbs_029_autopay_prenotice.py
# Impacts:  apps/runbooks/definitions/__init__.py (the one registration line) ·
#           apps/runbooks/seams/payments_seam.py ·
#           apps/payments/runbook_reads.py (the reads added with it)
# ───────────────────────────────────────────────────────
"""Runbook 17 — **Autopay pre-notification**. Compliance disguised as convenience.

WHAT IT DOES, IN ONE SENTENCE
------------------------------
It tells every autopay customer **the amount before it is debited**, which a bank
rule requires whenever the amount varies, and it handles the debits that failed
— except that on this product **no debit is ever attempted, so none can fail**,
and the result says exactly that instead of printing a zero.

⚠ **THE AMOUNT IS THE BILL'S OWN AND IS QUOTED, NEVER RECOMPUTED**
(`US-RBS-029` §7: *"None of its own. The amount is the bill's, quoted."*).
`BR-PAY-015` stores `amount` and `scheduled_on` on the intent at issue
*"because what the customer was told would be drafted, and when, must survive a
later change to the bill"* — which is precisely a pre-notification. A runbook
that re-priced the bill would tell the customer a different number from the one
the debit will take.

⚠ THE SECOND HALF OF THIS CARD CANNOT RUN, AND THE REASON IS STRUCTURAL
------------------------------------------------------------------------
`RB-117`'s own run reads *"851 notices queued · 11 failed debits, $1,480.20 — 9
retrying, 2 need a person"*, and the story's headline is *"851 queued · 2 debits
need you"*, each failure **reading the bank's reason in words**. On this product:

* **`AutopayCaptureIntent.status` has exactly ONE value** — `awaiting_rails` —
  and **nothing consumes an intent.** `apps/payments/autopay.py` says so in its
  own words: *"no function here takes a method, an amount or a date to
  capture."* The customer portal's refusal code was renamed `no_automatic_charge`
  on 2026-09-05 for the same reason. **A debit that is never attempted cannot
  fail.**
* **No column anywhere holds a bank return code or its reason.** `BankLine` is
  `posted_on`, `reference`, `amount` and its statement. So *"Bank said:
  insufficient funds"* — the card's own design note, and the thing that makes
  the failed-debit table worth reading — has no source to read from.

So the failed-debit half reports **NOT REPORTED**, with both sentences on the
screen, and never `0`. That distinction is the whole of hard-won law 7's fifth
shape: *a declared blind spot with no NUMBER attached is indistinguishable from
an empty one*, and here the two readings are *every debit went through* versus
*this product cannot draft a debit at all*.

**`BR-RBS-031` IS IMPLEMENTED ANYWAY AND IS NOT WAITING FOR THE RAILS.** *A debit
that fails twice is not retried a third time; the account goes to the ladder* is
written into `step_retry_or_ladder` against the attempt count the seam returns,
and `test_us_rbs_029_autopay_prenotice.py` proves it with the seam replaced —
which is the only way it can be proved today, and is said out loud here rather
than left as a passing test over an empty set.

WHAT THIS FILE DIVERGES FROM `RB-117` ON, AND WHY — RECORDED, NOT APPLIED SILENTLY
-----------------------------------------------------------------------------------
**1 · THE CARD SAYS *Steps 6 · four read, two write* AND THIS DECLARES FIVE.**
Runbook 8's divergence 1, again: the card's step 1 is `resolve()`, which is ONE
function and also answers *"Matches 862 accounts · 11 failed debits yesterday"*
on the setup screen.

    card 1  Gather autopay accounts       → `resolve()`
    card 2  Work out the debit date/amount→ step `debit`   (set · read)
    card 3  Check the amount changed      → step `changed` (set · read)
    card 4  Check yesterday's failures    → step `failed`  (set · read)
    card 5  Queue the notices             → step `notify`  (per record · writes)
    card 6  Flag failures, schedule retry → step `retry`   (set · writes)

**2 · *ONLY WHEN THE AMOUNT CHANGED* IS ANSWERED FROM THE PREVIOUS INTENT, AND
NOTHING ELSE COULD ANSWER IT.** The card's rule is *"a fixed amount needs no
notice; a variable one does"*. The only record this product keeps of what a
customer was last told is the amount on their PREVIOUS intent, so *changed*
means *differs from the amount last promised*, and a first-ever debit is always
notified because the customer has been told nothing at all. Recorded as this
lane's reading rather than presented as the card's.

**3 · `flag_account` IS HELD, CALLED, AND REFUSES — THERE IS NO `if is_bound`
BRANCH.** `customers` has no column for a general-purpose account flag with a
reason (`DEF-RBS-4331`), and `BR-RBS-040` forbids the obvious substitute of
writing a note. The port is called and **its own refusal is recorded as the
outcome**, exactly as wave `Q′`'s runbook 22 does — `BR-RBS-003` makes dry and
live one code path, and a branch on `is_bound` would be a second path proving
nothing about the first.

⚠ WHAT WOULD MAKE THIS RUNBOOK DO THE WRONG THING QUIETLY (hard-won law 7)
---------------------------------------------------------------------------
* **Reading *no intent* as *nothing due*.** An autopay account with an open bill
  and no intent is not a customer with nothing to pay — it is a customer nothing
  will draft for. → Both numbers travel on every result: how many accounts are on
  autopay at all, and how many have a debit scheduled. *6 on autopay · 0
  scheduled* is a sentence; *0* alone is not.
* **Printing 0 failed debits.** See above; it is `reported: False` with its
  reason, and the KPI tile carries the sentence rather than a number.
* **Telling a cash-only account about a debit.** `BR-PAY-013`'s privilege
  sanction means the account cannot be drafted at all, so a pre-notification
  would promise a debit that will never happen. → A guard, absolute, before any
  step.
* **Retrying for ever.** `BR-RBS-031` bounds it at two attempts and the third is
  the ladder's. → The attempt count is the retry key's discriminator, so one
  retry per attempt per debit however often this runs.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from apps.runbooks import models
from apps.runbooks.boundary import PortNotBound
from apps.runbooks.contract import (
    MODE_PER_RECORD,
    MODE_SET,
    PARAM_ENUM,
    PARAM_INTEGER,
    PARAM_TEXT,
    PARAM_TOGGLE,
    Block,
    Guard,
    Parameter,
    RunbookDefinition,
    Step,
    SubjectRef,
)
from apps.runbooks.engine import acts, duplicates
from apps.runbooks.seams import customers_seam, payments_seam

RUNBOOK_KEY = "autopay_prenotice"

STEP_DEBIT = "debit"
STEP_CHANGED = "changed"
STEP_FAILED = "failed"
STEP_NOTIFY = "notify"
STEP_RETRY = "retry"

STEP_LABELS = {
    STEP_DEBIT: "Work out the debit date and amount",
    STEP_CHANGED: "Check whether the amount changed",
    STEP_FAILED: "Check yesterday's failed debits",
    STEP_NOTIFY: "Queue the notices",
    STEP_RETRY: "Flag failed debits and schedule the retry",
}

#: Every outcome word a clerk reads. `planned` is the ENGINE's.
OUTCOME_QUEUED = "queued"
OUTCOME_NO_NOTICE_NEEDED = "no_notice_needed"
OUTCOME_ALREADY_TOLD = "already_told"
OUTCOME_SKIPPED = "skipped"
OUTCOME_FAILED = "failed"
OUTCOME_HELD = "held"

#: What `RB-117`'s *Fix* column says on a failed debit, in a clerk's words.
#: `BR-RBS-031`: the third attempt does not exist — the account goes to the
#: ladder instead, and the row says so.
NEXT_RETRY = "retry"
NEXT_LADDER = "to_the_ladder"
NEXT_NEEDS_A_PERSON = "needs_a_person"

#: Tenant-relative fix routes, prefixed with `/:tenant/` by the shell — each a
#: path this product actually mounts (`App.tsx`, checked 2026-09-07).
FIX_ACCOUNT = "customers"
FIX_PAYMENTS = "payments"


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

    `BR-TEN-043`, gate `G6`, and `BR-RBS-016` — *the schedule is the tenant's own
    clock*. *"Debit due within 10 days"* is a window measured from a stated day;
    read a wall clock and the same run cannot be re-taken for yesterday.
    """
    given = ctx.params.get("as_of")
    if isinstance(given, dt.date):
        return given
    if isinstance(given, str) and given:
        return dt.date.fromisoformat(given)
    raise ValueError(
        "runbook 17 needs the business day it is being run for. It is a parameter and never a "
        "clock read (BR-TEN-043, BR-RBS-016): the notice window is measured from it, and a "
        "customer told the wrong date is told a wrong thing about their own money."
    )


def _debits(ctx: Any) -> dict[str, Any]:
    """Every promised debit inside the window, read ONCE and memoised.

    `resolve()` pins the scope from it and two steps read it. Reading it twice
    would let the pinned set and the per-record pass disagree — a bill could be
    issued between them, which is what `BR-RBS-009` prevents.
    """
    return _memo(
        ctx,
        "_debits",
        lambda: payments_seam.autopay_debits_due(
            as_of=_as_of(ctx), within_days=int(ctx.params.get("within_days") or 10)
        ),
    )


def _by_account(ctx: Any) -> dict[str, Any]:
    return {str(row["account_id"]): row for row in _debits(ctx).get("rows", [])}


def guard_sample(ctx: Any, subject: SubjectRef) -> bool:
    """`BR-RBS-014` — **a sample record is never acted on, in any tenant, ever.**"""
    return str(subject.subject_id) in _memo(
        ctx, "_sample_ids", customers_seam.sample_account_ids
    )


def guard_autopay_paused(ctx: Any, subject: SubjectRef) -> bool:
    """`RB-117`'s *Never include: Autopay paused* — `BR-PAY-013`'s privilege flag.

    An account carrying `cash_only_no_autopay` cannot be drafted at all, so a
    pre-notification would promise a debit that will never be taken — worse than
    silence, because the customer would stop watching for the bill.

    ⚠ **THE FLAG IS READ AND NEVER CLEARED.** `BR-PAY-013`'s own rule is that
    nothing auto-clears it; a person restores the privilege. This guard reads it
    and no step in this runbook writes it.
    """
    row = _by_account(ctx).get(str(subject.subject_id))
    return bool(row and row.get("cash_only"))


# ── resolve — the pinned set, and the setup screen's own count ────────────


def resolve(ctx: Any):
    """Every autopay account with a debit due inside the notice window, pinned ONCE.

    Also the function that answers *"Matches N accounts"* on `RBS-004-R17`.

    ⚠ **THE SCOPE IS THE PROMISED DEBIT AND NOT THE OPEN BILL.** `BR-PAY-015`
    makes the `AutopayCaptureIntent` row the record of what the customer was told
    would be drafted and when. An autopay account with an open bill and no intent
    is not in scope: nothing will draft it, and a pre-notification is a promise
    this product would not keep.
    """
    return [
        SubjectRef(
            subject_type="account",
            subject_id=str(row["account_id"]),
            # ⚠ THE ACCOUNT NUMBER, NEVER THE DATABASE ID (B14 rule 31).
            label=str(row.get("account_no") or ""),
        )
        for row in _debits(ctx).get("rows", [])
    ]


# ── steps ─────────────────────────────────────────────────────────────────


def step_debit(ctx: Any, subjects) -> dict[str, Any]:
    """2 · SET · read — the debit date and amount, as PAYMENTS recorded them.

    ONE read over the whole pinned set. Nothing is computed: `amount` and
    `scheduled_on` are stored on the intent at bill issue for exactly this
    purpose, and the number the customer is told must be the number the debit
    will take.

    ⚠ **BOTH FIGURES TRAVEL, AND THAT IS THE HONEST PART OF THIS STEP.**
    `autopay_accounts` is how many accounts are on autopay at all;
    `scheduled_in_window` is how many have a debit promised. On the seeded tenant
    those are **6 and 0** — six customers enrolled and nothing scheduled — and a
    screen that could only say the second would report a quiet morning over a
    feature nothing has ever drafted for.
    """
    debits = _debits(ctx)
    wanted = {str(subject.subject_id) for subject in subjects}
    rows = {
        str(one["account_id"]): one
        for one in debits.get("rows", [])
        if str(one["account_id"]) in wanted
    }
    total = sum((_money(one["amount"], Decimal("0")) for one in rows.values()), Decimal("0"))
    return {
        "debits": rows,
        "from": debits.get("from"),
        "to": debits.get("to"),
        "autopay_accounts": debits.get("autopay_accounts"),
        "intents_in_total": debits.get("intents_in_total"),
        "scheduled_in_window": len(rows),
        "value": _stored(total),
        "currency": _currency_of(rows),
    }


def step_changed(ctx: Any, subjects) -> dict[str, Any]:
    """3 · SET · read — has the amount moved since the last one we told them?

    The bank rule the card cites applies to a VARIABLE amount: a fixed debit
    needs no notice, a varying one does. The only record this product keeps of
    what a customer was last told is the amount on their PREVIOUS intent
    (divergence 2), so *changed* means *differs from the amount last promised*.

    ⚠ **A FIRST-EVER DEBIT IS ALWAYS NOTIFIED.** There is no previous amount, so
    there is nothing the customer has already been told, and the safe direction
    is to tell them. Reading *no history* as *unchanged* would silence the very
    first notice a customer ever gets.
    """
    debits = ctx.set_results.get(STEP_DEBIT, {}).get("debits", {})
    only_when_changed = bool(ctx.params.get("only_when_amount_changed", True))
    changed: dict[str, bool] = {}
    firsts = 0
    for key, row in debits.items():
        if row.get("previous_amount") is None:
            firsts += 1
            changed[key] = True
            continue
        changed[key] = bool(row.get("amount_changed"))
    return {
        "changed": changed,
        "only_when_changed": only_when_changed,
        "first_debits": firsts,
        "amount_changed": len([one for one in changed.values() if one]),
        "amount_unchanged": len([one for one in changed.values() if not one]),
    }


def step_failed(ctx: Any, subjects) -> dict[str, Any]:
    """4 · SET · read — yesterday's failed debits. **NOT REPORTED, never zero.**

    ⚠ **READ THE MODULE DOCSTRING BEFORE CHANGING THIS.** Nothing on this product
    drafts an autopay payment, so no debit is ever attempted and none can fail —
    and no column anywhere holds the bank's return code, so even a failure that
    happened could not be read *in words*. The seam answers `reported: False`
    with the reason, and this step carries both onto the result.

    A tile reading **0 failed debits** would be indistinguishable from a morning
    when every debit went through, which is the exact confusion this whole
    posture exists to prevent.
    """
    answer = payments_seam.failed_debits(as_of=_as_of(ctx))
    rows = list(answer.get("rows", ()))
    return {
        "rows": rows,
        "reported": bool(answer.get("reported")),
        "why_not": answer.get("why_not", ""),
        "failed_count": len(rows),
        "failed_value": _stored(
            sum((_money(one.get("amount"), Decimal("0")) for one in rows), Decimal("0"))
        ),
        "retrying": len([one for one in rows if one.get("next") == NEXT_RETRY]),
        "need_a_person": len(
            [one for one in rows if one.get("next") in (NEXT_NEEDS_A_PERSON, NEXT_LADDER)]
        ),
    }


def step_notify(ctx: Any, subject: SubjectRef) -> dict[str, Any]:
    """5 · PER RECORD · **writes** — one notice, one account, one bill, once.

    ⚠ **THE DISCRIMINATOR IS THE INVOICE, NOT THE RUN.** One pre-notification per
    account per bill, which is `RB-117`'s own step 5 in as many words. The key
    carries no run, so a second run of the morning writes nothing; the next
    bill's intent is a different invoice and is a different key, so next month's
    customer is told again. Drop the discriminator and a customer is notified
    once and never again.

    ⚠ **THE WORD IS `Queued`, NEVER `Sent`** (`RBR-07`, PO 17 August 2026), and
    no runbook is on `LIVE_ENABLED_RUNBOOKS` besides — so this reaches a
    writer-less port and records what it WOULD do on the identical statements a
    live run walks (`BR-RBS-003`).
    """
    key = str(subject.subject_id)
    debit = ctx.set_results.get(STEP_DEBIT, {}).get("debits", {}).get(key, {})
    changed = ctx.set_results.get(STEP_CHANGED, {})
    if not debit:
        return {
            "outcome": OUTCOME_SKIPPED,
            "decided_by_rule": "Only the pinned set is walked",
            "reason": "this account had no debit due when the run pinned its scope.",
        }
    if changed.get("only_when_changed", True) and not changed.get("changed", {}).get(key, True):
        return {
            "outcome": OUTCOME_NO_NOTICE_NEEDED,
            "decided_by_rule": "A fixed amount needs no notice",
            "reason": "the amount has not moved since the last one they were told about.",
            "data": _record_data(debit),
        }

    verdict = _run_level(ctx)
    if verdict.is_duplicate:
        return {
            "outcome": OUTCOME_ALREADY_TOLD,
            "decided_by_rule": "This job already ran and was approved",
            "reason": verdict.message,
            "data": _record_data(debit),
        }

    amount = _money(debit.get("amount"), Decimal("0"))
    result = acts.perform(
        ctx,
        acts.ActRequest(
            port="queue_notice",
            action_kind="queue_notice",
            subject=subject,
            planned_action=f"Tell them {_display(amount)} on {debit.get('scheduled_on')}",
            # ⚠ ONE NOTICE PER ACCOUNT PER BILL. See the docstring.
            discriminator=str(debit.get("invoice_id") or ""),
            decided_by_rule="A varying amount is told before it is taken",
            reason=(
                f"{_display(amount)} is due to be taken on {debit.get('scheduled_on')}."
            ),
            amount=amount,
            currency=debit.get("currency"),
            payload={
                "runbook_key": ctx.runbook_key,
                "account_id": subject.subject_id,
                "subject_id": subject.subject_id,
                "discriminator": str(debit.get("invoice_id") or ""),
                "actor": acts.actor_for(ctx),
                "channels": tuple(_channels(ctx)),
            },
        ),
    )
    return {
        "outcome": _outcome(result.outcome),
        "decided_by_rule": "A varying amount is told before it is taken",
        "reason": f"{_display(amount)} on {debit.get('scheduled_on')}",
        "data": _record_data(debit, key=result.idempotency_key),
    }


def step_retry_or_ladder(ctx: Any, subjects) -> dict[str, Any]:
    """6 · SET · **writes** — `BR-RBS-031`, and it is bounded at two attempts.

    *A debit that fails twice is not retried a third time; the account goes to
    the ladder.* Endless retries are how a bank relationship is damaged and how
    one problem becomes three return fees on one customer.

    Three things happen per failed debit and each is a different act:

      1. **First failure** → `schedule_retry`, dated. The writer is
         `apps.payments.autopay.record_intent_at_issue`, which is IDEMPOTENT ON
         THE INVOICE (`UNIQUE (tenant, invoice_id)`), so a retry promised twice
         is one draft and not two — the guarantee is the index rather than a
         `SELECT`-then-`INSERT` two workers would both win.
      2. **Second failure** → **no third retry.** The account is handed to the
         collections ladder, which is runbook 8's, and the row says so.
      3. **Either way** → `flag_account`, so a person can see it. **That port
         binds no writer** (`DEF-RBS-4331`): `customers` has no column for a flag
         with a reason and `BR-RBS-040` forbids the substitute of writing a note.
         It is called anyway and **its own refusal is recorded**, because
         `BR-RBS-003` makes dry and live one code path and an `if is_bound`
         branch would be a second path proving nothing about the first.

    ⚠ **THIS STEP WALKS AN EMPTY LIST ON EVERY DEPLOYMENT TODAY** and says so on
    the result. See the module docstring: nothing drafts a debit, so nothing
    fails. The logic is proved in the test with the seam replaced, which is the
    only way it can be proved, and that is stated rather than left as a green
    test over an empty set.
    """
    failed = ctx.set_results.get(STEP_FAILED, {})
    rows = list(failed.get("rows", ()))
    if not rows:
        return {
            "retried": 0,
            "to_the_ladder": 0,
            "flagged": 0,
            "flag_refused": "",
            "reported": bool(failed.get("reported")),
            "why_not": failed.get("why_not", ""),
        }
    limit = int(ctx.params.get("retry_attempts") or 2)
    retried: list[str] = []
    ladder: list[str] = []
    flagged: list[str] = []
    refused = ""
    for row in rows:
        subject = SubjectRef(
            subject_type="account",
            subject_id=str(row["account_id"]),
            label=str(row.get("account_no") or ""),
        )
        attempt = int(row.get("attempt") or 1)
        amount = _money(row.get("amount"), Decimal("0"))
        if attempt < limit:
            result = acts.perform(
                ctx,
                acts.ActRequest(
                    port="schedule_retry",
                    action_kind="schedule_retry",
                    subject=subject,
                    planned_action=f"Try {_display(amount)} again",
                    # ⚠ THE ATTEMPT NUMBER. One retry per attempt per debit,
                    # however often this runs — and the third never has a key.
                    discriminator=f"{row.get('invoice_id')}|{attempt}",
                    decided_by_rule="A failed debit is tried once more",
                    reason=str(row.get("bank_said") or ""),
                    amount=amount,
                    currency=row.get("currency"),
                    payload={
                        "actor": acts.actor_for(ctx),
                        "account_id": subject.subject_id,
                        "invoice_id": row.get("invoice_id"),
                        "amount": amount,
                        "due_date": _retry_on(ctx, row),
                        "currency": str(row.get("currency") or "USD"),
                    },
                ),
            )
            if result.outcome in (acts.OUTCOME_DONE, acts.OUTCOME_PLANNED):
                retried.append(subject.subject_id)
        else:
            # ⚠ `BR-RBS-031`. NO third attempt is scheduled: the account is the
            # collections ladder's now, and runbook 8 picks it up on its own
            # schedule. Nothing here writes a ladder state — that is payments'
            # own table and runbook 8's port.
            ladder.append(subject.subject_id)
        try:
            ctx.port("flag_account").call(
                account_id=subject.subject_id,
                reason=f"An autopay debit failed: {row.get('bank_said')}",
            )
        except PortNotBound as refusal:
            refused = str(refusal)
        else:
            flagged.append(subject.subject_id)
    return {
        "retried": len(retried),
        "to_the_ladder": len(ladder),
        "flagged": len(flagged),
        # The port's OWN refusal, recorded rather than papered over.
        "flag_refused": refused,
        "reported": True,
        "why_not": "",
    }


def _retry_on(ctx: Any, row: dict[str, Any]) -> dt.date:
    """`RB-117`'s *Retry once after 3 days*, measured from the stated day."""
    days = int(ctx.params.get("retry_after_days") or 3)
    return _as_of(ctx) + dt.timedelta(days=days)


# ── the run-level duplicate check (OQ-RBS-1737, CLOSED 2026-09-06) ────────


def _run_level(ctx: Any):
    """Ask ONCE per run whether this job already ran — never once per account."""

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
    """KPIs · Records · Downloads — `RB-117`'s own three blocks.

    ⚠ **THE AUTOPAY NOTICES ARE A DOWNLOAD AND NOT A TABLE**, closed OUT OF SCOPE
    on the card in the Product Owner's own words: *"851 rows a clerk will never
    read belong in a file."* So the Records table draws the **failed debits** —
    the rows that need a decision — and the notices are a file.

    ⚠ **THE FAILED-DEBIT TILE CARRIES A SENTENCE, NOT A ZERO.** On every
    deployment today nothing drafts a debit, so the tile reads *Not reported*
    with its reason; only where the seam reports does it carry a count.
    """
    debit = dict(view.set_results.get(STEP_DEBIT, {}))
    changed = dict(view.set_results.get(STEP_CHANGED, {}))
    failed = dict(view.set_results.get(STEP_FAILED, {}))
    retry = dict(view.set_results.get(STEP_RETRY, {}))
    counts = dict(view.counts)
    currency = debit.get("currency") or "USD"
    queued = counts.get(OUTCOME_QUEUED, 0) + counts.get(acts.OUTCOME_PLANNED, 0)
    reported = bool(failed.get("reported"))

    return [
        Block(
            block="kpis",
            payload={
                "tiles": [
                    {
                        "id": "queued",
                        "label": "Notices queued",
                        "value": {"kind": "text", "text": str(queued)},
                        "detail": "Queued — nothing is sent until a provider is connected",
                    },
                    {
                        "id": "value",
                        "label": "Debit value",
                        "value": {
                            "kind": "money",
                            "amount": debit.get("value", "0.0000"),
                            "currency": currency,
                        },
                        "detail": f"Due between {debit.get('from')} and {debit.get('to')}",
                    },
                    {
                        "id": "unchanged",
                        "label": "Amount unchanged",
                        "value": {
                            "kind": "text",
                            "text": str(changed.get("amount_unchanged", 0)),
                        },
                        "detail": "A fixed amount needs no notice",
                    },
                    {
                        "id": "failed",
                        "label": "Failed debits",
                        "value": (
                            {"kind": "text", "text": str(failed.get("failed_count", 0))}
                            if reported
                            # ⚠ NOT A ZERO. See the module docstring.
                            else {"kind": "text", "text": "Not reported"}
                        ),
                        "detail": (
                            f"{failed.get('need_a_person', 0)} need a person"
                            if reported
                            else failed.get("why_not", "")
                        ),
                    },
                    {
                        "id": "retrying",
                        "label": "Retrying",
                        "value": (
                            {"kind": "text", "text": str(retry.get("retried", 0))}
                            if reported
                            else {"kind": "text", "text": "Not reported"}
                        ),
                        "detail": (
                            f"{retry.get('to_the_ladder', 0)} to the ladder"
                            if reported
                            else "No debit is drafted, so none can be retried"
                        ),
                    },
                ]
            },
        ),
        Block(
            block="records",
            payload={
                "columns": [
                    {"key": "account", "label": "Account"},
                    {"key": "amount", "label": "Amount"},
                    {"key": "bank_said", "label": "Bank said"},
                    {"key": "attempt", "label": "Attempt"},
                    {"key": "next", "label": "Next"},
                    {"key": "fix", "label": "Fix"},
                ],
                "rows": _failed_rows(failed, currency),
                "total": len(failed.get("rows", ())),
                "empty": {
                    "title": (
                        "No debit failed."
                        if reported
                        else "Failed debits are not reported here yet."
                    ),
                    "helper": (
                        "Every debit due in the window went through."
                        if reported
                        else str(failed.get("why_not", ""))
                    ),
                },
            },
        ),
        Block(
            block="downloads",
            payload={
                "files": [
                    # ⚠ THE NOTICES ARE THE FILE — the card's own closed question.
                    {"name": "Notices", "outcome": OUTCOME_QUEUED},
                    {"name": "No notice needed", "outcome": OUTCOME_NO_NOTICE_NEEDED},
                ],
                "stated_absences": _absences(debit, failed, retry),
            },
        ),
    ]


def _absences(debit: dict, failed: dict, retry: dict) -> list[str]:
    """What this run could NOT look at, each with its figure (hard-won law 7)."""
    out: list[str] = []
    if not failed.get("reported", False):
        out.append(str(failed.get("why_not", "")))
        out.append(
            "and no column in this product holds the bank's reason for a returned debit, so "
            "'Bank said' could not be filled in even if one had failed."
        )
    scheduled = int(debit.get("scheduled_in_window") or 0)
    enrolled = debit.get("autopay_accounts")
    if enrolled is not None and scheduled == 0:
        # ⚠ BOTH NUMBERS. *0 scheduled* alone reads as a quiet morning.
        out.append(
            f"{enrolled} accounts are on autopay and none has a debit scheduled in this "
            "window, because a debit is only recorded when a bill is issued."
        )
    if retry.get("flag_refused"):
        out.append(
            "an account could not be flagged for a person to look at: "
            + str(retry["flag_refused"])
        )
    return [one for one in out if one]


def _failed_rows(failed: dict[str, Any], currency: str) -> list[dict[str, Any]]:
    """`RB-117`'s failed-debit table, as the `{id, cells}` rows a table draws."""
    return [
        {
            "id": str(row.get("account_id")),
            "cells": {
                # The account NUMBER, never the id (B14 rule 31).
                "account": {"kind": "text", "text": str(row.get("account_no") or "")},
                "amount": {
                    "kind": "money",
                    "amount": str(row.get("amount") or "0.0000"),
                    "currency": row.get("currency") or currency,
                },
                # ⚠ THE BANK'S REASON IN WORDS, NEVER THE RETURN CODE — the
                # card's own design note and B14 rule 32.
                "bank_said": {"kind": "text", "text": str(row.get("bank_said") or "")},
                "attempt": {
                    "kind": "text",
                    "text": f"{row.get('attempt')} of {row.get('attempts_allowed')}",
                },
                "next": {"kind": "text", "text": _next_words(row)},
                "fix": (
                    {"kind": "link", "label": "Open account", "to": FIX_ACCOUNT}
                    if row.get("next") != NEXT_RETRY
                    # ⚠ *Fix* READS `—` ON A DEBIT THAT IS SIMPLY RETRYING — the
                    # card says so, because there is nothing for a person to do.
                    else {"kind": "text", "text": "—"}
                ),
            },
            "meta": {"decided_by_rule": str(row.get("decided_by_rule") or "")},
        }
        for row in failed.get("rows", ())
    ]


def _next_words(row: dict[str, Any]) -> str:
    """*Retry 7 Sep* · *To the ladder* · *Needs a person* — no rule id (rule 32)."""
    nxt = str(row.get("next") or "")
    if nxt == NEXT_RETRY:
        return f"Retry {row.get('retry_on') or ''}".strip()
    if nxt == NEXT_LADDER:
        return "To the ladder"
    return "Needs a person"


# ── small helpers ─────────────────────────────────────────────────────────


def _record_data(debit: dict[str, Any], *, key: str | None = None) -> dict[str, Any]:
    data = {
        "amount": debit.get("amount"),
        "previous_amount": debit.get("previous_amount"),
        "scheduled_on": debit.get("scheduled_on"),
        "invoice_id": debit.get("invoice_id"),
    }
    if key:
        data["idempotency_key"] = key
    return data


def _currency_of(rows: dict[str, Any]) -> str:
    """The tenant's ONE currency (`BR-TEN-042`), off the debits' own rows."""
    for row in rows.values():
        if row.get("currency"):
            return str(row["currency"])
    return "USD"


def _channels(ctx: Any) -> tuple[str, ...]:
    """`RB-117`'s *Channel: Email, then text*, as a parameter."""
    raw = str(ctx.params.get("channels") or "email_then_text")
    return ("email", "sms") if raw == "email_then_text" else (raw,)


def _outcome(engine_outcome: str) -> str:
    """The engine's word, in this runbook's vocabulary.

    ⚠ **`planned` STAYS `planned`.** A dry run and a live one must not read the
    same on the result screen.
    """
    return {
        acts.OUTCOME_DONE: OUTCOME_QUEUED,
        acts.OUTCOME_ALREADY: OUTCOME_ALREADY_TOLD,
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


def _display(value: Decimal) -> str:
    """Two decimals, for a sentence a clerk reads (hard rule 2).

    ⚠ **A STORED FOUR- OR SIX-PLACE VALUE MUST NEVER REACH CLERK COPY.**
    *"182.400000 more than this account owes"* is a real defect another lane
    fixed this week, and a sentence is exactly where it escapes.
    """
    return f"${value.quantize(Decimal('0.01')):f}"


RUNBOOK = RunbookDefinition(
    key=RUNBOOK_KEY,
    name="Autopay pre-notification",
    kind=models.KIND_ACTION,
    category="payments",
    subject_type="account",
    unit_of_work="autopay",
    triggers=(models.TRIGGER_SCHEDULE, models.TRIGGER_MANUAL),
    tags=("Accounts", "notices"),
    parameters=(
        Parameter(name="as_of", type=PARAM_TEXT, label="Business day", required=True),
        Parameter(
            name="within_days",
            type=PARAM_INTEGER,
            label="Debit due within (days)",
            required=True,
            default=10,
        ),
        Parameter(
            name="only_when_amount_changed",
            type=PARAM_TOGGLE,
            label="Only when amount changed",
            required=True,
            default=True,
        ),
        Parameter(
            name="channels",
            type=PARAM_ENUM,
            label="Channel",
            required=True,
            default="email_then_text",
            choices=("email_then_text", "email", "sms"),
        ),
        Parameter(
            name="retry_attempts",
            type=PARAM_INTEGER,
            label="Attempts before the ladder",
            required=True,
            # ⚠ `BR-RBS-031` — two, and the third does not exist. Raising this
            # is a rule change and not a setting a lane may widen.
            default=2,
        ),
        Parameter(
            name="retry_after_days",
            type=PARAM_INTEGER,
            label="Retry after (days)",
            required=True,
            default=3,
        ),
        Parameter(
            name="frequency_hours",
            type=PARAM_INTEGER,
            label="Treat runs within",
            required=True,
            default=24,
        ),
    ),
    guards=(
        Guard(key="sample", label="Never include: Sample", applies=guard_sample),
        Guard(
            key="autopay_paused",
            label="Never include: Autopay paused",
            applies=guard_autopay_paused,
        ),
    ),
    resolve=resolve,
    report=report,
    steps=(
        Step(key=STEP_DEBIT, label=STEP_LABELS[STEP_DEBIT], mode=MODE_SET, run=step_debit),
        Step(key=STEP_CHANGED, label=STEP_LABELS[STEP_CHANGED], mode=MODE_SET, run=step_changed),
        Step(key=STEP_FAILED, label=STEP_LABELS[STEP_FAILED], mode=MODE_SET, run=step_failed),
        Step(
            key=STEP_NOTIFY,
            label=STEP_LABELS[STEP_NOTIFY],
            mode=MODE_PER_RECORD,
            run=step_notify,
            writes=True,
        ),
        Step(
            key=STEP_RETRY,
            label=STEP_LABELS[STEP_RETRY],
            mode=MODE_SET,
            run=step_retry_or_ladder,
            writes=True,
        ),
    ),
    ports=("queue_notice", "flag_account", "schedule_retry"),
)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-029 (EP-RBS-05; CR-075 wave R′, the payments half)
# generated: 2026-09-07 by the CR-075 wave R′ payments build lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint — the run/approve/stop routes are wave D's) E=n/a(no screen — phase 5 declares NO frontend code) F✔ G✔ H=n/a(no 🔒 path: the idempotency KEY is composed in engine/acts.py and the amount is the bill's own, quoted)
# gates: pytest tests/test_us_rbs_029_autopay_prenotice.py · pytest tests/test_us_rbs_015_conformance.py · G115 · G6 (no clock read — as_of is a parameter)
# exceptions: DISABLED FOR LIVE — no runbook is on engine.acts.LIVE_ENABLED_RUNBOOKS · five steps rather than the card's six (divergence 1) · **THE FAILED-DEBIT HALF IS NOT REPORTED AND IS NEVER ZERO**: nothing on this product drafts an autopay debit (BR-PAY-015 — one intent status, no consumer) and no column holds a bank return code, so `BR-RBS-031` is proved in the test with the seam replaced · `flag_account` binds no writer and its own refusal is recorded (DEF-RBS-4331) · *amount changed* is answered from the PREVIOUS intent, which is the only record this product keeps (divergence 2)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
