# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-027 (EP-RBS-05) — CR-075 wave R′, the payments half:
#           runbook 15, registered as an Action holding three payments ports,
#           DISABLED for live, guards evaluated BEFORE step 1.
# Rules:    BR-RBS-012 (guards are ABSOLUTE, before any step) · BR-RBS-014 (a
#           SAMPLE record is never acted on) · BR-RBS-018 (every money-bearing
#           action carries a second approval — OQ-RBS-1732 CLOSED 2026-09-06
#           with NO threshold) · BR-RBS-013 (a correction goes through the
#           owning module) · BR-RBS-010 (every record names the rule that
#           decided it, in words) · BR-RBS-035 (a count for the outcomes with
#           no row) · BR-RBS-003 (dry and live are one path) · BR-CUS-050 /
#           BR-CUS-057 (the deposit, its receipt date and its interest —
#           customers' law, READ and never copied) · BR-PAY-021 (on time is
#           `posted_at ≤ due date`) · CLAUDE.md hard rule 2 (money 4 stored, 2
#           displayed, never a float)
# Golden:   ❄️ GT-61 — $150 @ 2.0%, 89 months → **$22.25** (B5, FROZEN). This
#           file computes NONE of it: `customers_seam.deposit_interest_accrued`
#           reads `apps/customers/deposit_interest.py`, which asserts it.
# Tests:    06-backend/tests/test_us_rbs_027_deposit_review.py
# Impacts:  apps/runbooks/definitions/__init__.py (the one registration line) ·
#           apps/runbooks/seams/payments_seam.py · customers_seam.py ·
#           apps/payments/runbook_reads.py (the reads added with it)
# ───────────────────────────────────────────────────────
"""Runbook 15 — **Deposit review**. Money going the OTHER way, so the gate is heavier.

WHAT IT DOES, IN ONE SENTENCE
------------------------------
It finds deposits this utility has held past its own good-payment period, reads
the interest owed, and decides for each one whether it is a CREDIT to an open
account or a REFUND — and **a refund waits for a second person** (`BR-RBS-018`,
and `OQ-RBS-1732` closed on 2026-09-06 with every money-bearing action carrying
it and no threshold at all).

⚠ **NOTHING IS SETTLED BY THIS RUN.** `engine.acts.LIVE_ENABLED_RUNBOOKS` is
empty for the whole catalogue, so every port this file holds is handed to a step
without a writer and `acts.act()` records what it WOULD do on the identical code
path (`BR-RBS-003`). The result screen says `Planned`, never `Credited`.

❄️ THE INTEREST IS FROZEN LAW AND THIS FILE COMPUTES NONE OF IT
----------------------------------------------------------------
**`GT-61` — $150 @ 2.0%, 89 months → $22.25** — is finance-signed (B5, 2026-08-08)
and is implemented in `apps/customers/deposit_interest.py`, published as
`apps.customers.selectors.deposit_interest_accrued` and asserted against that
exact figure. This runbook READS it through `customers_seam` and multiplies
nothing.

⚠ **THAT WAS VERY NEARLY THE OTHER WAY ROUND, AND THE NEAR-MISS IS WORTH THE
PARAGRAPH.** This lane's first reading of the estate was *"`BR-CUS-057`'s accrual
is unbuilt — `customers` reports `deposit_interest_not_accrued`"*, which is a
true sentence about `move_out_settlement` and was a **false** conclusion about the
product: the arithmetic landed under `CR-059` CS-20 and lives in a module whose
name is not `selectors.py`. Reporting the figure as *not worked out* would have
put **$0.00 interest** on a regulator's own tile. It is the shape `CR-075`'s
dependency table already records once — *"the capability was reported absent
because this lane looked for it in the shape it expected"* — and the cure is the
same one: grep for the FIGURE (`GT-61`), not for the module you expected.

⚠ **AND `None` IS NOT ZERO, WHICH IS THE WHOLE OF WHY THIS RUNBOOK HAS A
`not_configured` OUTCOME.** The owning module is explicit: `None` means *we could
not find out* — no rate set, no receipt date stamped — and `0` means *this state
requires no interest*. On the seeded tenant the rate is **0.000000**, which is
the shipped default, so every accrual is a real zero and the tile says so with
the reason beside it rather than printing a bare `$0.00` that reads like an
answer.

WHAT THIS FILE DIVERGES FROM `RB-115` ON, AND WHY — RECORDED, NOT APPLIED SILENTLY
-----------------------------------------------------------------------------------
**1 · THE CARD SAYS *Steps 7 · five read, two write* AND THIS DECLARES SIX.**
Same arithmetic as runbook 8's divergence 1: the card's step 1 (*Gather deposits
held past the period*) is `resolve()`, which is ONE function and also answers
*"Matches 70 deposits · $17,890.00 held"* on the setup screen. A count computed a
second way is a count that can disagree with the run.

    card 1  Gather deposits past the period → `resolve()`
    card 2  Check twelve months on time     → step `on_time`   (set · read)
    card 3  Check nothing is past due today → step `past_due`  (set · read)
    card 4  Work out the interest owed      → step `interest`  (set · read)
    card 5  Decide credit or refund         → step `decide`    (set · read)
    card 6  Post the credit / raise refund  → step `settle`    (per record · writes)
    card 7  Queue the letter                → step `letter`    (per record · writes)

**2 · `Past due now` IS BOTH A GUARD AND A STEP, AND THAT IS THE CARD'S OWN
SHAPE RATHER THAN A DUPLICATE.** The card lists *Never include: Past due now* in
the scope AND writes step 3 as *"re-check that nothing is past due — the morning
of, not the month of"*. The guard is what excludes (absolute, before any step,
`BR-RBS-012`); the step is what a clerk READS, and it reports how many the guard
took and on which day. They share ONE memoised read, so the exclusion and the
sentence cannot disagree.

**3 · THE SUBJECT IS A `deposit` AND THE ROW IS AN ACCOUNT'S.** There is no
`deposits` table in this product: a deposit is `accounts.deposit_on_file` +
`accounts.deposit_received_on` (B2 r9 #5). `subject_type` is the DECLARED unit
and never the raw row (`BR-RBS-019`), so the runbook walks deposits and the seam
reads accounts.

**4 · `post_credit` IS HELD AND FIRES ONLY WHERE THERE IS AN OPEN BILL TO DRAW
IT AGAINST, WHICH IS NARROWER THAN THE CARD READS.** `RB-115`'s *"Settle by:
Credit to account"* sounds like a balance adjustment; the bound writer is
`apps.payments.credit.apply_credit_at_issue`, which draws a carried credit down
**against an open invoice** (`BR-PAY-010`). An open account with nothing
outstanding therefore has nowhere to put the credit today, and this runbook says
so on the row (`no_open_bill`) rather than inventing a second credit path.
**Widening that is payments' act and a reviewed interface change, not a lane's.**

⚠ WHAT WOULD MAKE THIS RUNBOOK DO THE WRONG THING QUIETLY (hard-won law 7)
---------------------------------------------------------------------------
* **Treating an account with NO bills as twelve months of good payment.** This
  is not hypothetical: two of the five deposits on the seeded tenant belong to
  accounts with **zero** issued bills, and a review that started every verdict at
  *on time* would have released both. → `payment_history_verdict` is
  three-valued and `None` means UNPROVEN; unproven is held, never released.
* **Reading a zero rate as an unreadable one, or the reverse.** One means *this
  state requires no interest* and the other means *we could not find out*, and
  paying the first as the second is a compliance failure in the direction a
  regulator notices. → Two different outcomes, two different sentences.
* **Rounding the interest here.** Money is stored to 4 decimals and displayed to
  2 (hard rule 2); a runbook that quantised to 2 before summing would report a
  total that does not foot against the rows under it. → Every figure travels at
  four places and the RENDERER shows two.
* **Letting a refund out on the batch approval.** The batch approval releases the
  RUN; `BR-RBS-018`'s second approval releases the money, and they are different
  people at different moments. → The Action block is drawn DISABLED with its
  reason, and the reason is on the screen.
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
    PARAM_MONEY,
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

RUNBOOK_KEY = "deposit_review"

STEP_ON_TIME = "on_time"
STEP_PAST_DUE = "past_due"
STEP_INTEREST = "interest"
STEP_DECIDE = "decide"
STEP_SETTLE = "settle"
STEP_LETTER = "letter"

STEP_LABELS = {
    STEP_ON_TIME: "Check twelve months of on-time payment",
    STEP_PAST_DUE: "Check nothing is past due today",
    STEP_INTEREST: "Work out the interest owed",
    STEP_DECIDE: "Decide credit or refund",
    STEP_SETTLE: "Post the credit, or raise the refund",
    STEP_LETTER: "Queue the letter",
}

#: Every outcome word a clerk reads on this result. `planned` is the ENGINE's and
#: is what a dry run produces; the rest are this runbook's own and each is a
#: sentence somebody can act on.
OUTCOME_CREDITED = "credited"
OUTCOME_REFUND_WAITING = "refund_waiting"
OUTCOME_NOT_ELIGIBLE = "not_eligible"
OUTCOME_NOT_CONFIGURED = "not_configured"
OUTCOME_NO_OPEN_BILL = "no_open_bill"
OUTCOME_ALREADY_DONE = "already_done"
OUTCOME_SKIPPED = "skipped"
OUTCOME_FAILED = "failed"
OUTCOME_HELD = "held"

#: Why a deposit is not settled this month, in a clerk's words and with no rule
#: id in any of them (B14 rule 32) and none longer than a sentence (rule 33's
#: spirit: a refusal is short).
NOT_ELIGIBLE_SENTENCES = {
    "too_recent": "this deposit has not been held long enough yet",
    "no_receipt_date": "nobody stamped the day this deposit was taken",
    "no_history": "this account has no bills, so on-time payment cannot be shown",
    "paid_late": "a bill in the last twelve months was paid after its due date",
    "no_due_date": "a bill in the last twelve months carries no due date",
}

#: Tenant-relative fix routes, prefixed with `/:tenant/` by the shell — every one
#: a path this product actually mounts (`App.tsx`, checked 2026-09-07). A fix
#: route that resolves to nothing is a dead button over a live finding, and
#: nothing in the backend suite can see one because a string is a string.
FIX_ACCOUNT = "customers"
FIX_SETTINGS_BILLING = "settings/billing"


# ── guards — ABSOLUTE, and evaluated before step 1 (BR-RBS-012) ───────────


def _memo(ctx: Any, key: str, build) -> Any:
    """One lazily-built answer per run, so a guard is not asked twice.

    Three guards over N deposits would otherwise read the sample set, the plan
    board and the payment history three times each. `ctx.set_results` is the
    executor's own per-run scratch space.
    """
    cached = ctx.set_results.get(key)
    if cached is None:
        cached = build()
        ctx.set_results[key] = cached
    return cached


def _as_of(ctx: Any) -> dt.date:
    """The business day this run is taken for. **An argument, never a clock.**

    `BR-TEN-043` and gate `G6`. Step 3's whole point is *the morning of, not the
    month of* — a rule you cannot express without a stated day, and cannot
    re-test at a boundary if the code reads a wall clock.
    """
    given = ctx.params.get("as_of")
    if isinstance(given, dt.date):
        return given
    if isinstance(given, str) and given:
        return dt.date.fromisoformat(given)
    raise ValueError(
        "runbook 15 needs the business day it is being run for. It is a parameter and never a "
        "clock read (BR-TEN-043): a deposit review re-taken for the 1st must give the 1st's "
        "answer, and interest accrued to a day nobody named is a figure nobody can check."
    )


def _deposits(ctx: Any) -> dict[str, Any]:
    """Every deposit and how long it has been held, read ONCE and memoised.

    `resolve()` pins the scope from it and three later steps read it, so reading
    it twice would let them disagree — an account could be closed between them,
    which is exactly what `BR-RBS-009`'s *"resolved ONCE and pinned"* prevents.
    """
    return _memo(
        ctx,
        "_deposits",
        lambda: payments_seam.deposits_held(
            as_of=_as_of(ctx), months=int(ctx.params.get("held_months") or 12)
        ),
    )


def _rows_by_account(ctx: Any) -> dict[str, Any]:
    return {str(row["account_id"]): row for row in _deposits(ctx).get("rows", [])}


def _history(ctx: Any) -> dict[str, Any]:
    """Twelve months of payment behaviour for the whole pinned set, in ONE read."""

    def build():
        rows = _deposits(ctx).get("rows", [])
        return payments_seam.payment_history_verdict(
            [row["account_id"] for row in rows],
            as_of=_as_of(ctx),
            months=int(ctx.params.get("good_payment_months") or 12),
        )

    return _memo(ctx, "_history", build)


def guard_sample(ctx: Any, subject: SubjectRef) -> bool:
    """`BR-RBS-014` — **a sample record is never acted on, in any tenant, ever.**

    Absolute, before any step, and it cannot be switched off. A demo account
    receiving a real refund cheque is the mirror of the demo account receiving a
    real disconnection notice, and it costs more.
    """
    return str(subject.subject_id) in _memo(
        ctx, "_sample_ids", customers_seam.sample_account_ids
    )


def guard_past_due_now(ctx: Any, subject: SubjectRef) -> bool:
    """`RB-115`'s *Never include: Past due now* — **the morning of, not the month of.**

    A deposit is security against non-payment. Handing it back to somebody who
    owes money this morning is giving away the only thing that covers the debt,
    and the card puts the re-check in the scope AND in step 3 for that reason.
    Held here as a guard so it happens before any step and survives any later
    rule; step 3 reports what it took.
    """
    verdict = _history(ctx).get("verdicts", {}).get(str(subject.subject_id), {})
    return bool(verdict.get("past_due_today"))


def guard_plan_voided(ctx: Any, subject: SubjectRef) -> bool:
    """`RB-115`'s *Never include: Plan voided in 12 months*.

    ⚠ **THIS GUARD IS DECLARED AND CANNOT FIRE ON THIS PRODUCT, AND SAYING SO IS
    THE POINT.** `payment_plans.status` has four values — `proposed`,
    `agreement_sent`, `active`, `closed` (`BR-PAY-016`) — and **there is no
    `voided` status**: runbook 25 in this same wave records the same absence from
    the other side, where voiding a plan has no port either. A plan that failed
    is `closed`, indistinguishable from one a customer paid off, so *voided in
    the last twelve months* is a question this product cannot answer.

    It returns `False` — nothing is excluded — and the run REPORTS the gap on its
    own result rather than implying the exclusion happened. A guard that silently
    never fires is worse than an absent one: the setup screen draws it, a clerk
    reads it as protection, and it is not there.
    """
    return False


# ── resolve — the pinned set, and the setup screen's own count ────────────


def resolve(ctx: Any):
    """Every deposit held past the policy period, pinned ONCE.

    This is also the function that answers *"Matches N deposits · $X held"* on
    `RBS-004-R15`, which is why it is one function and not two.

    ⚠ **A DEPOSIT WITH NO RECEIPT DATE IS IN SCOPE AND IS NOT ELIGIBLE.** It
    cannot be aged, so it can never mature — and dropping it from the scope would
    make it invisible for ever, on a screen whose whole job is finding money a
    utility owes back. It appears with `no_receipt_date` and a route to the
    account, which is where somebody fixes it.
    """
    subjects = []
    for row in _deposits(ctx).get("rows", []):
        if not row.get("eligible") and row.get("received_on") is not None:
            continue
        subjects.append(
            SubjectRef(
                subject_type="deposit",
                subject_id=str(row["account_id"]),
                # ⚠ THE ACCOUNT NUMBER, NEVER THE DATABASE ID (B14 rule 31).
                label=str(row.get("account_no") or ""),
            )
        )
    return subjects


# ── steps ─────────────────────────────────────────────────────────────────


def step_on_time(ctx: Any, subjects) -> dict[str, Any]:
    """2 · SET · read — twelve months of on-time payment, for the whole set at once.

    ONE read rather than one per deposit, for the ladder board's reason: written
    per record it would be a bill query per account on the morning of the 1st.

    ⚠ **`on_time` IS THREE-VALUED AND THE THIRD VALUE IS WHAT KEEPS THIS
    HONEST.** `None` means no bill was looked at — no history at all — and the
    decision step treats it as NOT eligible. On the seeded tenant both eligible
    deposits come back `None`, so the run plans nothing and says why; a build
    that read absence as good behaviour would have released $300.00 on evidence
    nobody has.
    """
    history = _history(ctx)
    wanted = {str(subject.subject_id) for subject in subjects}
    verdicts = {
        key: value for key, value in history.get("verdicts", {}).items() if key in wanted
    }
    proven = len([one for one in verdicts.values() if one.get("on_time") is True])
    unproven = len([one for one in verdicts.values() if one.get("on_time") is None])
    return {
        "verdicts": verdicts,
        "readable": bool(history.get("readable", True)),
        "why_not": history.get("why_not", ""),
        "from": history.get("from"),
        "to": history.get("to"),
        # Three numbers rather than one, so *nothing proven* cannot be read as
        # *nothing wrong* (hard-won law 7).
        "proven_on_time": proven,
        "no_history": unproven,
        "not_on_time": len(verdicts) - proven - unproven,
    }


def step_past_due(ctx: Any, subjects) -> dict[str, Any]:
    """3 · SET · read — **the morning of, not the month of** (`RB-115` step 3).

    The exclusion itself is `guard_past_due_now`, which ran before step 1; this
    is the step that puts it on the screen. Both read the SAME memoised verdict,
    so the number a clerk sees and the accounts the run skipped cannot differ.

    The day is stated in the result because that is the whole rule: a review
    computed on the 1st over a balance from the 20th would hand back a deposit
    against a debt that arrived in between.
    """
    history = _history(ctx)
    verdicts = history.get("verdicts", {})
    walked = {str(subject.subject_id) for subject in subjects}
    past_due = [
        key for key, value in verdicts.items() if value.get("past_due_today")
    ]
    return {
        "checked_on": _as_of(ctx).isoformat(),
        "past_due_today": len(past_due),
        "still_in_scope": len(walked),
        "note": (
            "Anything past due this morning is out, whatever last month's balance was."
        ),
    }


def step_interest(ctx: Any, subjects) -> dict[str, Any]:
    """4 · SET · read — ❄️ `GT-61`'s figure, READ from `customers` and never computed.

    `customers_seam.deposit_interest_accrued` is
    `apps/customers/deposit_interest.py`, which implements the FROZEN rule and
    asserts **$150 @ 2.0%, 89 months → $22.25** against it. This step calls it
    once per deposit and adds nothing but the total.

    ⚠ **THE RATE IS READ BESIDE THE FIGURE, AND IT ANSWERS A DIFFERENT
    QUESTION.** Every accrual on a utility whose rate is 0 comes back a real
    zero. Printing `$0.00 interest` alone would read as *we worked it out and it
    is nothing*; printing it beside *no interest rate is set for this utility*
    reads as what it is. `None` from the seam is a third answer again — *we could
    not find out* — and it is never collapsed into the other two.
    """
    as_of = _as_of(ctx)
    rate = customers_seam.deposit_interest_rate_annual()
    accruals: dict[str, str | None] = {}
    total = Decimal("0")
    unreadable = 0
    for subject in subjects:
        figure = customers_seam.deposit_interest_accrued(subject.subject_id, as_of=as_of)
        if figure is None:
            accruals[str(subject.subject_id)] = None
            unreadable += 1
            continue
        amount = Decimal(str(figure))
        accruals[str(subject.subject_id)] = _stored(amount)
        total += amount
    return {
        "accrued": accruals,
        # Four places stored, two displayed (hard rule 2). The renderer rounds.
        "total": _stored(total),
        "rate_percent": None if rate is None else f"{Decimal(str(rate)):f}",
        "rate_readable": rate is not None,
        "rate_configured": rate is not None and Decimal(str(rate)) > 0,
        "could_not_work_out": unreadable,
    }


def step_decide(ctx: Any, subjects) -> dict[str, Any]:
    """5 · SET · read — credit or refund, and **why**, in one of two sentences.

    `RB-115`'s design note is the specification for this step: *"Why a refund is
    always one of two sentences, so the approver is not reading policy — they are
    confirming a fact."* The two are **Account closed** and **Over the $X
    limit**; everything else is a credit.

    Nothing is written here. The decision is the plan a second person approves,
    and `BR-RBS-004` requires it to exist before anything is acted on.
    """
    rows = _rows_by_account(ctx)
    history = _history(ctx).get("verdicts", {})
    interest = ctx.set_results.get(STEP_INTEREST, {}).get("accrued", {})
    limit = _money(ctx.params.get("refund_over"), Decimal("250.0000"))
    plan: dict[str, dict[str, Any]] = {}
    for subject in subjects:
        key = str(subject.subject_id)
        row = rows.get(key, {})
        held = _money(row.get("held"), Decimal("0"))
        accrued = _money(interest.get(key), None)
        total = held + (accrued or Decimal("0"))
        decision: dict[str, Any] = {
            "account_no": row.get("account_no"),
            "held": _stored(held),
            "interest": None if accrued is None else _stored(accrued),
            "total": _stored(total),
            "currency": row.get("currency") or "USD",
            "received_on": row.get("received_on"),
            "closed": bool(row.get("closed")),
        }
        blocked = _why_not_eligible(row, history.get(key, {}))
        if blocked:
            decision.update(
                {
                    "outcome": OUTCOME_NOT_ELIGIBLE,
                    "settle_by": None,
                    "why": NOT_ELIGIBLE_SENTENCES.get(blocked, blocked),
                    "decided_by_rule": "The good-payment period",
                    "fix_route": FIX_ACCOUNT,
                }
            )
        elif accrued is None:
            decision.update(
                {
                    "outcome": OUTCOME_NOT_CONFIGURED,
                    "settle_by": None,
                    "why": "the interest owed on this deposit could not be worked out",
                    "decided_by_rule": "This utility's deposit interest is not set up",
                    "fix_route": FIX_SETTINGS_BILLING,
                }
            )
        elif row.get("closed"):
            decision.update(
                {
                    "outcome": OUTCOME_REFUND_WAITING,
                    "settle_by": "refund",
                    # ⚠ ONE OF EXACTLY TWO SENTENCES — the card's design note.
                    "why": "Account closed",
                    "decided_by_rule": "A closed account cannot be credited",
                    "fix_route": FIX_ACCOUNT,
                }
            )
        elif total > limit:
            decision.update(
                {
                    "outcome": OUTCOME_REFUND_WAITING,
                    "settle_by": "refund",
                    "why": f"Over the {_display(limit)} limit",
                    "decided_by_rule": "This utility's refund limit",
                    "fix_route": FIX_ACCOUNT,
                }
            )
        else:
            decision.update(
                {
                    "outcome": OUTCOME_CREDITED,
                    "settle_by": "credit",
                    "why": "Credited to the account",
                    "decided_by_rule": "An open account under the limit is credited",
                    "fix_route": FIX_ACCOUNT,
                }
            )
        plan[key] = decision
    return {
        "plan": plan,
        "refund_limit": _stored(limit),
        "to_credit": len([one for one in plan.values() if one["outcome"] == OUTCOME_CREDITED]),
        "to_refund": len(
            [one for one in plan.values() if one["outcome"] == OUTCOME_REFUND_WAITING]
        ),
        "not_eligible": len(
            [one for one in plan.values() if one["outcome"] == OUTCOME_NOT_ELIGIBLE]
        ),
    }


def _why_not_eligible(row: dict[str, Any], verdict: dict[str, Any]) -> str:
    """The ONE reason this deposit is not settled, or `""` — never a list.

    Ordered so the first true one is the one a clerk can act on: a missing
    receipt date is a data fix, a short tenure is a matter of waiting, and a late
    payment is the customer's own record. Returning several would put three
    sentences in a cell built for one.
    """
    if row.get("received_on") is None:
        return "no_receipt_date"
    if not row.get("eligible"):
        return "too_recent"
    on_time = verdict.get("on_time")
    if on_time is None:
        return "no_history"
    if not on_time:
        if verdict.get("bills_with_no_due_date"):
            return "no_due_date"
        return "paid_late"
    return ""


def step_settle(ctx: Any, subject: SubjectRef) -> dict[str, Any]:
    """6 · PER RECORD · **writes** — the credit, or the refund REQUEST.

    Four layers meet here and each does a different job:

      1. **The guards already ran** — sample, past due this morning — absolute
         and before any step (`BR-RBS-012`).
      2. **Step 5 decided** credit or refund, with its sentence.
      3. **The run-level check** says whether an earlier run of this same job
         already did this, or is still waiting for somebody (`OQ-RBS-1737`, PO
         2026-09-06) — a warning, never a silent skip.
      4. **The per-record key** carries the deposit's RECEIPT DATE as its
         discriminator, so one deposit is settled once and a deposit taken again
         next year is a different key. Drop the discriminator and an account that
         paid a second deposit after a move-in is never refunded it.

    ⚠ **NEITHER PORT CAN SETTLE ANYTHING TODAY** — no runbook is on
    `LIVE_ENABLED_RUNBOOKS` — so `acts.act()` records `planned` on the same
    statements a live run walks (`BR-RBS-003`). And `raise_refund` **could not
    pay one even then**: it writes a REQUEST, and `approve_refund` and
    `issue_refund` are deliberately bound to no port at all. A runbook may ask; a
    person decides.
    """
    decision = ctx.set_results.get(STEP_DECIDE, {}).get("plan", {}).get(
        str(subject.subject_id), {}
    )
    if not decision:
        return {
            "outcome": OUTCOME_SKIPPED,
            "decided_by_rule": "Only the pinned set is walked",
            "reason": "this deposit was not in the plan when the run pinned its scope.",
        }
    if decision["outcome"] in (OUTCOME_NOT_ELIGIBLE, OUTCOME_NOT_CONFIGURED):
        return {
            "outcome": decision["outcome"],
            "decided_by_rule": decision["decided_by_rule"],
            "reason": decision["why"],
            "fix_route": decision["fix_route"],
            "data": _record_data(decision),
        }

    verdict = _run_level(ctx)
    if verdict.is_duplicate:
        return {
            "outcome": OUTCOME_ALREADY_DONE,
            "decided_by_rule": "This job already ran and was approved",
            "reason": verdict.message,
            "data": _record_data(decision),
        }

    amount = _money(decision["total"], Decimal("0"))
    if decision["settle_by"] == "refund":
        result = acts.perform(
            ctx,
            acts.ActRequest(
                port="raise_refund",
                action_kind="raise_refund",
                subject=subject,
                planned_action=f"Refund {_display(amount)}",
                discriminator=str(decision.get("received_on") or ""),
                decided_by_rule=decision["decided_by_rule"],
                reason=decision["why"],
                amount=amount,
                currency=decision["currency"],
                payload={
                    "actor": acts.actor_for(ctx),
                    "account_id": subject.subject_id,
                    "amount": amount,
                    "method": str(ctx.params.get("refund_method") or "cheque"),
                    "requested_at": _as_of(ctx),
                    "reason": decision["why"],
                    "idempotency_key": acts.idempotency_key(
                        runbook_key=ctx.runbook_key,
                        action_kind="raise_refund",
                        subject=subject,
                        discriminator=str(decision.get("received_on") or ""),
                    ),
                },
            ),
        )
        return {
            # ⚠ **`planned` DOES NOT BECOME `refund_waiting` AND
            # `refund_waiting` DOES NOT BECOME `done`.** A refund that has been
            # REQUESTED is still waiting for its second approval, so the word a
            # clerk reads is the same in both cases and only the engine's own
            # outcome tells a dry run from a live one.
            "outcome": _outcome(result.outcome, OUTCOME_REFUND_WAITING),
            "decided_by_rule": decision["decided_by_rule"],
            "reason": decision["why"],
            "fix_route": decision["fix_route"],
            "data": _record_data(decision, key=result.idempotency_key),
        }

    # A credit needs an open bill to draw down against — see divergence 4.
    position = payments_seam.open_bill_position(subject.subject_id) or {}
    invoice = _first_open_invoice(position)
    if invoice is None:
        return {
            "outcome": OUTCOME_NO_OPEN_BILL,
            "decided_by_rule": "A credit is drawn against an open bill",
            "reason": "this account has nothing open for the deposit to come off.",
            "fix_route": FIX_ACCOUNT,
            "data": _record_data(decision),
        }
    result = acts.perform(
        ctx,
        acts.ActRequest(
            port="post_credit",
            action_kind="post_credit",
            subject=subject,
            planned_action=f"Credit {_display(amount)}",
            discriminator=str(decision.get("received_on") or ""),
            decided_by_rule=decision["decided_by_rule"],
            reason=decision["why"],
            amount=amount,
            currency=decision["currency"],
            payload={
                "actor": acts.actor_for(ctx),
                "account_id": subject.subject_id,
                "invoice_id": invoice["invoice_id"],
                "invoice_total": _money(invoice["total"], Decimal("0")),
                "occurred_on": _as_of(ctx),
            },
        ),
    )
    return {
        "outcome": _outcome(result.outcome, OUTCOME_CREDITED),
        "decided_by_rule": decision["decided_by_rule"],
        "reason": decision["why"],
        "fix_route": decision["fix_route"],
        "data": _record_data(decision, key=result.idempotency_key),
    }


def _first_open_invoice(position: dict[str, Any]) -> dict[str, Any] | None:
    """The oldest bill with something still on it, or `None`.

    Oldest first is `BR-PAY-010`'s allocation order and is payments' own; this
    reads the order that module already returned rather than sorting again.
    """
    for bill in position.get("bills", ()) or ():
        invoice_id = bill.get("invoice_id") or bill.get("id")
        total = bill.get("open") or bill.get("balance") or bill.get("total")
        if invoice_id and total not in (None, ""):
            return {"invoice_id": invoice_id, "total": total}
    return None


def step_letter(ctx: Any, subject: SubjectRef) -> dict[str, Any]:
    """7 · PER RECORD · **writes** — *"Your deposit of $250.00 has been returned."*

    ⚠ **THE WORD IS `Queued` AND NEVER `Sent`** (`RBR-07`, PO 17 August 2026):
    nothing leaves the building until a delivery provider is connected, and no
    runbook is live-enabled besides. A letter is WRITTEN here and the dispatcher
    is what sends (`BR-NOT-005`).

    Only a deposit this run actually settled gets a letter. A deposit that was
    not eligible has nothing to tell a customer about, and a letter saying so
    would be the product volunteering that it looked at their money and did
    nothing.
    """
    decision = ctx.set_results.get(STEP_DECIDE, {}).get("plan", {}).get(
        str(subject.subject_id), {}
    )
    if not decision or decision["outcome"] in (
        OUTCOME_NOT_ELIGIBLE,
        OUTCOME_NOT_CONFIGURED,
    ):
        return {
            "outcome": OUTCOME_SKIPPED,
            "decided_by_rule": "A letter follows a settlement",
            "reason": "nothing was settled on this deposit, so there is nothing to tell them.",
        }
    amount = _money(decision["total"], Decimal("0"))
    result = acts.perform(
        ctx,
        acts.ActRequest(
            port="queue_notice",
            action_kind="queue_notice",
            subject=subject,
            planned_action=f"Tell them about {_display(amount)}",
            discriminator=f"{decision.get('received_on') or ''}|{decision['settle_by']}",
            decided_by_rule="Every settlement is told to the customer",
            reason=decision["why"],
            amount=amount,
            currency=decision["currency"],
            payload={
                "runbook_key": ctx.runbook_key,
                "account_id": subject.subject_id,
                "subject_id": subject.subject_id,
                "discriminator": str(decision.get("received_on") or ""),
                "actor": acts.actor_for(ctx),
                "channels": tuple(_channels(ctx)),
            },
        ),
    )
    return {
        "outcome": _outcome(result.outcome, OUTCOME_CREDITED),
        "decided_by_rule": "Every settlement is told to the customer",
        "reason": decision["why"],
        "data": {"queued": True, "idempotency_key": result.idempotency_key},
    }


# ── the run-level duplicate check (OQ-RBS-1737, CLOSED 2026-09-06) ────────


def _run_level(ctx: Any):
    """Ask ONCE per run whether this job already ran — never once per deposit.

    It is a fact about the RUN, which is the whole shape of the Product Owner's
    ruling: an APPROVED earlier run has already written its rows, and an
    UNAPPROVED one is a third state that gets a WARNING rather than a silent
    skip. `engine/duplicates.py` carries the reading in full.
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
    """KPIs · Records · **Action** · Downloads — `RB-115`'s own four blocks.

    ⚠ **THE `Action` BLOCK IS DRAWN DISABLED WITH ITS REASON, ALWAYS, AND THAT
    IS `BR-RBS-018` WRITTEN AS A SCREEN.** *Approve N refunds* is the second
    approval, it belongs to a second admin, and no runbook may press it — so B14
    draws the control a user may not use **disabled with its reason**, never
    hidden (`DEF-SHL-4043` is what a grey button that says nothing costs). The
    payload validator refuses a disabled action carrying no `reason`, which is
    what keeps this honest.

    ⚠ **THE GUARDED DEPOSITS ARE IN THE COUNTS AND HAVE NO ROWS**
    (`BR-RBS-035`). `view.counts` is the engine's own count and already includes
    them; drawing the tiles from `len(records)` would lose every account the
    past-due guard took this morning — which is the number a supervisor most
    wants to see.
    """
    decide = dict(view.set_results.get(STEP_DECIDE, {}))
    interest = dict(view.set_results.get(STEP_INTEREST, {}))
    on_time = dict(view.set_results.get(STEP_ON_TIME, {}))
    past_due = dict(view.set_results.get(STEP_PAST_DUE, {}))
    plan = dict(decide.get("plan", {}))
    currency = _currency_of(plan)

    credited = [one for one in plan.values() if one["outcome"] == OUTCOME_CREDITED]
    refunds = [one for one in plan.values() if one["outcome"] == OUTCOME_REFUND_WAITING]
    credited_value = sum((_money(one["total"], Decimal("0")) for one in credited), Decimal("0"))
    refund_value = sum((_money(one["total"], Decimal("0")) for one in refunds), Decimal("0"))

    return [
        Block(
            block="kpis",
            payload={
                "tiles": [
                    {
                        "id": "credited",
                        "label": "To credit",
                        "value": {"kind": "text", "text": str(len(credited))},
                        "detail": "Planned — nothing is posted until this run is approved",
                    },
                    {
                        "id": "credited_value",
                        "label": "Credit value",
                        "value": {
                            "kind": "money",
                            "amount": _stored(credited_value),
                            "currency": currency,
                        },
                    },
                    {
                        "id": "refunds",
                        "label": "Refunds awaiting",
                        "value": {"kind": "text", "text": str(len(refunds))},
                        "detail": "Each one needs a second admin",
                    },
                    {
                        "id": "refund_value",
                        "label": "Refund value",
                        "value": {
                            "kind": "money",
                            "amount": _stored(refund_value),
                            "currency": currency,
                        },
                    },
                    {
                        # ⚠ **INTEREST IS ITS OWN TILE BECAUSE IT IS THE FIGURE A
                        # REGULATOR ASKS ABOUT** (`RB-115`'s design note), and it
                        # carries the reason when there is nothing to show, so a
                        # bare $0.00 cannot read as *worked out and nil*.
                        "id": "interest",
                        "label": "Interest paid",
                        "value": {
                            "kind": "money",
                            "amount": interest.get("total", "0.0000"),
                            "currency": currency,
                        },
                        "detail": _interest_detail(interest),
                    },
                ]
            },
        ),
        Block(
            block="records",
            payload={
                "columns": [
                    {"key": "account", "label": "Account"},
                    {"key": "deposit", "label": "Deposit"},
                    {"key": "interest", "label": "Interest"},
                    {"key": "total", "label": "Total"},
                    {"key": "why", "label": "Why"},
                    {"key": "fix", "label": "Fix"},
                ],
                "rows": [_record_row(record, plan, currency) for record in view.records],
                "total": len(view.records),
                "empty": {
                    "title": "No deposit is due back.",
                    "helper": (
                        "Nothing this utility holds has passed its good-payment period."
                    ),
                },
            },
        ),
        Block(
            block="action",
            payload={
                "label": f"Approve {len(refunds)} refunds",
                "tier": "primary",
                # ⚠ ALWAYS FALSE. See the docstring — this is the second
                # approval and it is a second admin's act, never an automation's.
                "enabled": False,
                # B14 rule 33 keeps a refusal to five or six words.
                "reason": "A second admin approves refunds",
            },
        ),
        Block(
            block="downloads",
            payload={
                "files": [
                    {"name": "Credited", "outcome": OUTCOME_CREDITED},
                    {"name": "Not due back", "outcome": OUTCOME_NOT_ELIGIBLE},
                ],
                # Reported rather than inferred away. Each of these is a fact
                # this run could not establish, with its number beside it.
                "stated_absences": _absences(on_time, interest, past_due),
            },
        ),
    ]


def _absences(on_time: dict, interest: dict, past_due: dict) -> list[str]:
    """What this run could NOT look at, each with its figure (hard-won law 7).

    A blind spot with no number attached cannot be told from an empty one, and
    every sentence here is one a clerk could act on.
    """
    out: list[str] = []
    if on_time.get("no_history"):
        out.append(
            f"{on_time['no_history']} of these accounts have no bills at all, so twelve "
            "months of on-time payment cannot be shown for them and nothing is settled."
        )
    if not interest.get("rate_readable", True):
        out.append(
            "this utility's deposit interest rate could not be read, so no interest was "
            "worked out. It is not being treated as nil."
        )
    elif not interest.get("rate_configured", False):
        out.append(
            "no deposit interest rate is set for this utility, so every deposit comes back "
            "with no interest on it."
        )
    if interest.get("could_not_work_out"):
        out.append(
            f"{interest['could_not_work_out']} deposits carry no receipt date, so the "
            "interest clock has no start and none was worked out."
        )
    # ⚠ THE GUARD THAT CANNOT FIRE, SAID OUT LOUD — see `guard_plan_voided`.
    out.append(
        "a plan voided in the last twelve months is not excluded, because this product "
        "records a failed plan and a finished one the same way."
    )
    return out


def _record_row(record, plan: dict[str, Any], currency: str) -> dict[str, Any]:
    """One `{id, cells}` row — `RecordsBlock` reads nothing else (`DEF-RBS-4352`).

    `decided_by_rule` travels in `meta`, which no block draws: B14 rule 32 keeps
    a rule id out of what a clerk reads and the findings file still needs it.
    """
    decision = plan.get(str(record.subject.subject_id), {})
    return {
        "id": str(record.subject.subject_id),
        "cells": {
            # The account NUMBER, never the id (B14 rule 31).
            "account": {"kind": "text", "text": record.subject.label},
            "deposit": {
                "kind": "money",
                "amount": decision.get("held", "0.0000"),
                "currency": decision.get("currency") or currency,
            },
            "interest": (
                {
                    "kind": "money",
                    "amount": decision["interest"],
                    "currency": decision.get("currency") or currency,
                }
                if decision.get("interest") is not None
                else {"kind": "text", "text": "Not worked out"}
            ),
            "total": {
                "kind": "money",
                "amount": decision.get("total", "0.0000"),
                "currency": decision.get("currency") or currency,
            },
            "why": {"kind": "text", "text": record.reason},
            "fix": (
                {"kind": "link", "label": "Open account", "to": record.fix_route}
                if record.fix_route
                else {"kind": "text", "text": ""}
            ),
        },
        "meta": {"decided_by_rule": record.decided_by_rule, "outcome": record.outcome},
    }


def _interest_detail(interest: dict[str, Any]) -> str:
    """The sentence under the interest tile. **Never blank over a zero.**"""
    if not interest.get("rate_readable", True):
        return "The rate could not be read"
    if not interest.get("rate_configured", False):
        return "No interest rate is set for this utility"
    return f"At {interest.get('rate_percent')}% a year"


# ── small helpers ─────────────────────────────────────────────────────────


def _record_data(decision: dict[str, Any], *, key: str | None = None) -> dict[str, Any]:
    data = {
        "held": decision.get("held"),
        "interest": decision.get("interest"),
        "total": decision.get("total"),
        "settle_by": decision.get("settle_by"),
    }
    if key:
        data["idempotency_key"] = key
    return data


def _currency_of(plan: dict[str, Any]) -> str:
    """The tenant's ONE currency (`BR-TEN-042`), taken off the plan's own rows."""
    for row in plan.values():
        if row.get("currency"):
            return str(row["currency"])
    return "USD"


def _channels(ctx: Any) -> tuple[str, ...]:
    """`RB-115`'s letter, as a parameter. Post by default: a deposit letter is
    a document a customer keeps."""
    raw = str(ctx.params.get("channels") or "email_then_post")
    return ("email", "pdf_print") if raw == "email_then_post" else (raw,)


def _outcome(engine_outcome: str, done_word: str) -> str:
    """The engine's word, in this runbook's vocabulary.

    ⚠ **`planned` STAYS `planned`.** A dry run and a live one must not read the
    same on the result screen — that difference is the single thing wave `M`'s
    month-long soak exists to look at.
    """
    return {
        acts.OUTCOME_DONE: done_word,
        acts.OUTCOME_ALREADY: OUTCOME_ALREADY_DONE,
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

    ⚠ **A STORED SIX- OR FOUR-PLACE VALUE MUST NEVER REACH CLERK COPY.**
    *"182.400000 more than this account owes"* is a real defect another lane
    fixed this week, and a sentence is exactly where it escapes — every cell
    goes through the renderer and every sentence goes through here.
    """
    return f"${value.quantize(Decimal('0.01')):f}"


RUNBOOK = RunbookDefinition(
    key=RUNBOOK_KEY,
    name="Deposit review",
    kind=models.KIND_ACTION,
    category="collections",
    # ⚠ THE DECLARED UNIT, NOT THE ROW (`BR-RBS-019`). There is no `deposits`
    # table — a deposit is two columns on `accounts` (B2 r9 #5) — and the unit a
    # clerk counts is still the deposit.
    subject_type="deposit",
    unit_of_work="deposit",
    triggers=(models.TRIGGER_SCHEDULE, models.TRIGGER_MANUAL),
    tags=("Finance", "Accounts"),
    parameters=(
        Parameter(name="as_of", type=PARAM_TEXT, label="Business day", required=True),
        Parameter(
            name="held_months",
            type=PARAM_INTEGER,
            label="Deposits held longer than (months)",
            required=True,
            default=12,
        ),
        Parameter(
            name="good_payment_months",
            type=PARAM_INTEGER,
            label="Good-payment months",
            required=True,
            default=12,
        ),
        Parameter(
            name="refund_over",
            type=PARAM_MONEY,
            label="Refund instead when over",
            required=True,
            # ⚠ A STRING, NOT A FLOAT. `Parameter` refuses a float on a money
            # type, and this value lives in jsonb where nothing else would.
            default="250.0000",
        ),
        Parameter(
            name="refunds_need_second_approval",
            type=PARAM_TOGGLE,
            label="Refunds need second approval",
            required=True,
            # ⚠ **ON, AND IT IS DRAWN READ-ONLY.** `OQ-RBS-1732` closed on
            # 2026-09-06: every money-bearing action carries the second approval
            # and there is NO threshold. The parameter exists because the card
            # draws it; nothing reads it to decide, because turning it off is not
            # a thing a tenant may do.
            default=True,
        ),
        Parameter(
            name="refund_method",
            type=PARAM_ENUM,
            label="Refund by",
            required=True,
            default="cheque",
            choices=("cheque", "card_reversal", "ach"),
        ),
        Parameter(
            name="most_per_run",
            type=PARAM_INTEGER,
            label="Most per run",
            required=True,
            default=100,
        ),
        Parameter(
            name="channels",
            type=PARAM_ENUM,
            label="Channel",
            required=True,
            default="email_then_post",
            choices=("email_then_post", "email", "pdf_print"),
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
    # each DISABLED with its reason rather than hiding it, because a guard a
    # clerk cannot see is a guard they will assume is absent.
    guards=(
        Guard(key="sample", label="Never include: Sample", applies=guard_sample),
        Guard(key="past_due", label="Never include: Past due now", applies=guard_past_due_now),
        Guard(
            key="plan_voided",
            label="Never include: Plan voided in 12 months",
            applies=guard_plan_voided,
        ),
    ),
    resolve=resolve,
    report=report,
    steps=(
        Step(key=STEP_ON_TIME, label=STEP_LABELS[STEP_ON_TIME], mode=MODE_SET, run=step_on_time),
        Step(
            key=STEP_PAST_DUE,
            label=STEP_LABELS[STEP_PAST_DUE],
            mode=MODE_SET,
            run=step_past_due,
        ),
        Step(
            key=STEP_INTEREST,
            label=STEP_LABELS[STEP_INTEREST],
            mode=MODE_SET,
            run=step_interest,
        ),
        Step(key=STEP_DECIDE, label=STEP_LABELS[STEP_DECIDE], mode=MODE_SET, run=step_decide),
        Step(
            key=STEP_SETTLE,
            label=STEP_LABELS[STEP_SETTLE],
            mode=MODE_PER_RECORD,
            run=step_settle,
            writes=True,
        ),
        Step(
            key=STEP_LETTER,
            label=STEP_LABELS[STEP_LETTER],
            mode=MODE_PER_RECORD,
            run=step_letter,
            writes=True,
        ),
    ),
    ports=("post_credit", "raise_refund", "queue_notice"),
)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-027 (EP-RBS-05; CR-075 wave R′, the payments half)
# generated: 2026-09-07 by the CR-075 wave R′ payments build lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint — the run/approve/stop routes are wave D's) E=n/a(no screen — phase 5 declares NO frontend code; the result is a composition of the twelve blocks) F✔ G✔ H=n/a(no 🔒 path in this file: the idempotency KEY is composed in engine/acts.py and ❄️ GT-61's arithmetic is customers')
# gates: pytest tests/test_us_rbs_027_deposit_review.py · pytest tests/test_us_rbs_015_conformance.py · G115 (the import census) · G6 (no clock read — as_of is a parameter)
# exceptions: DISABLED FOR LIVE — no runbook is on engine.acts.LIVE_ENABLED_RUNBOOKS · six steps rather than the card's seven (divergence 1) · `past_due` is a guard AND a step, which is the card's own shape (divergence 2) · `guard_plan_voided` CANNOT FIRE — `payment_plans` has no `voided` status — and the run says so on its own result rather than implying the exclusion happened · `post_credit` needs an open bill to draw against and reports `no_open_bill` where there is none (divergence 4) · NO INTEREST IS COMPUTED HERE: ❄️ GT-61 is customers', read through customers_seam
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
