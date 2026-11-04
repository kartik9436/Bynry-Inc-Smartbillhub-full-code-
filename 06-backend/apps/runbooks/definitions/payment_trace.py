# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-025 (EP-RBS-05) — CR-075 wave S: runbook 13, *Payment trace*
#           — six read steps that STOP when the payment is found.
# Rules:    BR-RBS-002 (a Check is CONSTRUCTED with no writer) · BR-RBS-009 ·
#           BR-RBS-010 · BR-RBS-011 · BR-RBS-019 · BR-RBS-020 · BR-RBS-021 ·
#           BR-RBS-023 · BR-RBS-027 · RBR-16 (the Check itself writes nothing) ·
#           CLAUDE.md hard rule 2 (money 4 stored / 2 shown) · hard rule 4 (a
#           payment is append-only; moving one is payments' own act) ·
#           B14 rules 31, 32, 33
# Tests:    06-backend/tests/test_us_rbs_025_payment_trace.py ·
#           06-backend/tests/test_rbs_check_runbooks_pg.py (PostgreSQL only)
# Impacts:  apps/runbooks/definitions/__init__.py · apps/runbooks/seams/
#           payments_seam.py · apps/runbooks/seams/customers_seam.py ·
#           04-docs/05-modules/17-runbooks/11-catalogue/RB-113-payment-trace.md
# ───────────────────────────────────────────────────────
"""Runbook 13 — **Payment trace**.

*"I paid, and you say I didn't"* — where did that payment go? `RB-113` calls it
the second most common call a utility takes, after *why is my bill higher*, and
its own sentence for the answer is: **"Found: $182.40 on 12 Sep, applied to
account ending 4471 — Alvarez, not Okonkwo. Same last four."**

⚠ **IT FINDS; THE PERSON MOVES THE PAYMENT.** The card closes that OUT OF SCOPE
in as many words — *"moving a payment is a payments-module act with its own
approval and its own audit"* — and hard rule 4 is why: a payment is append-only,
and a correction is a new row made by the module that owns the books. This
runbook holds **no port at all** (`BR-RBS-002`) and the *Move payment →* button
is a link to payments' own screen.

THE CHAIN STOPS WHEN FOUND, AND THE LATER CELLS SAY *NOT NEEDED*
------------------------------------------------------------------
`RB-113`'s design note: *"The chain stops at step 2 and says so — steps 3 to 5
read Not needed, which is the same honesty as 'Never reached' in runbook 6."*
The two words are different on purpose and this module keeps them apart: **Never
reached** means the run stopped and nobody knows; **Not needed** means the
question was answered before we got there.

⚠ **AND THE THREE-STATE CELL IS WHY THE RENDERER'S VOCABULARY MATTERS.**
`ChainCellState` is `ok · bad · notReached · pending`; a *Not needed* cell is
`pending` with its own note, because it did not fail and it was not blocked.

WHAT IT SEARCHES, IN ORDER, AND WHY THE SECOND STEP IS THE WHOLE POINT
-----------------------------------------------------------------------
1. this account, in the window;
2. **the same amount and date on ANY account** — *"this is where mis-keyed
   payments hide"*, and the card's worked case is two accounts ending 4471;
3. reversed or returned items — a payment that came and went again;
4. unapplied cash — money the utility holds and has not placed;
5. today's landed batch — arrived, not yet applied: *"it is real, just early"*;
6. the trace itself.

WHAT THIS PRODUCT CANNOT DO FOR STEP 5, WITH ITS NUMBER
---------------------------------------------------------
⚠ **`payments` PUBLISHES NO LIST OF IMPORT BATCHES** — `payment_import_batch_dict`
answers for ONE batch by id and nothing enumerates them
(`13-selector-inventory.md` **S-15**, owned by `payments`). So a landed batch is
a declared INPUT here, exactly as runbook 10 takes it, and where a clerk names
none the step reports **not checked** rather than *nothing found*. The Product
Owner's own description of that flow is the same shape (2026-09-06: *"it is
human who will collect it and uplaod in system"*).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from apps.runbooks import models
from apps.runbooks.contract import (
    MODE_PER_RECORD,
    MODE_SET,
    PARAM_DAYS,
    PARAM_MONEY,
    PARAM_REF_OBJECT,
    PARAM_TEXT,
    PARAM_TOGGLE,
    Block,
    Parameter,
    RunbookDefinition,
    Step,
    SubjectRef,
)
from apps.runbooks.seams import customers_seam, payments_seam, tenancy_seam

KEY = "payment_trace"

ZERO = Decimal("0")

# ── the six steps, in the card's own order ────────────────────────────────

STEP_THIS_ACCOUNT = "payments_on_this_account"
STEP_ELSEWHERE = "same_amount_and_date_anywhere"
STEP_REVERSED = "reversed_or_returned_items"
STEP_UNAPPLIED = "unapplied_cash_matching"
STEP_BATCH = "todays_landed_batch"
STEP_TRACE = "build_the_trace"

STEP_LABELS = {
    STEP_THIS_ACCOUNT: "This account",
    STEP_ELSEWHERE: "Elsewhere",
    STEP_REVERSED: "Reversed",
    STEP_UNAPPLIED: "Unapplied",
    STEP_BATCH: "Today's batch",
    STEP_TRACE: "The trace",
}

STEP_POSITION = {key: index for index, key in enumerate(STEP_LABELS, start=1)}

#: The five searching steps, in the order the chain draws them.
SEARCH_STEPS = (STEP_THIS_ACCOUNT, STEP_ELSEWHERE, STEP_REVERSED, STEP_UNAPPLIED, STEP_BATCH)

# ── what the trace can conclude ───────────────────────────────────────────

FOUND_HERE = "found_on_this_account"
FOUND_ELSEWHERE = "found_on_another_account"
FOUND_REVERSED = "found_and_reversed"
FOUND_UNAPPLIED = "found_as_unapplied_cash"
FOUND_IN_BATCH = "found_in_a_landed_batch"
NOT_FOUND = "not_found"

# ── fix routes ────────────────────────────────────────────────────────────
#
# Verified against `07-frontend/src/routing/` on 2026-09-07; tenant-relative.
FIX_PAYMENTS = "payments"
FIX_ACCOUNTS = "accounts"


@dataclass
class _StepResult:
    reached: bool = True
    needed: bool = True
    found: dict[str, Any] = field(default_factory=dict)
    checked: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "reached": self.reached,
            "needed": self.needed,
            "found": dict(self.found),
            "checked": dict(self.checked),
        }


def _money(raw: Any) -> Decimal | None:
    if raw in (None, ""):
        return None
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return None


def _stored(amount: Decimal) -> str:
    """Money as this product STORES it — four decimals (hard rule 2).

    ⚠ **`payments.amount` IS A `NUMERIC(18,6)` CONTAINER**, which hard rule 2
    calls lawful for a column that already exists while governing what is
    WRITTEN — so a payment crosses the seam as `160.520000` and a money cell
    that carried it would put six places into the frozen report. The renderer
    shows two either way; what is stored is four, and a report is a stored
    artefact (`BR-RBS-020` freezes it).
    """
    return str(amount.quantize(Decimal("0.0001")))


def _shown(amount: Decimal, currency: str) -> str:
    """Money as a CLERK READS IT — two decimals with its `CHAR(3)` code.

    The same convention `cash_application._shown` records and for its reason: a
    currency symbol is a formatting decision the tenant's regional settings own
    and the renderer applies. `DEF-RBS-4373` carries the divergence with
    `test_bill._display`, which writes a `$`.
    """
    return f"{amount.quantize(Decimal('0.01'))} {currency}".strip()


def _around(ctx) -> date | None:
    raw = ctx.params.get("around")
    if isinstance(raw, date):
        return raw
    try:
        return date.fromisoformat(str(raw)[:10])
    except (TypeError, ValueError):
        return None


def _window(ctx) -> tuple[date, date]:
    """The look-back the card declares — *90 days*, from the tenant's own today.

    ⚠ `BR-TEN-043`: the business date is an input and never a clock a runbook
    reads, so a trace re-run for last quarter searches last quarter.
    """
    today = tenancy_seam.today()
    return today - timedelta(days=int(ctx.params.get("look_back") or 90)), today


def _already_found(ctx) -> dict[str, Any] | None:
    """The first hit, or `None`. **The chain stops when found** (the card's own
    step heading), and this is what makes every later step say *Not needed*."""
    for step in SEARCH_STEPS:
        result = ctx.set_results.get(step) or {}
        hit = (result.get("found") or {}).get("hit")
        if hit:
            return dict(hit)
    return None


def _not_needed(reason: str) -> dict[str, Any]:
    return _StepResult(needed=False, checked={"not_needed_because": reason}).as_dict()


def _hit(payment: dict[str, Any], where: str, why: str) -> dict[str, Any]:
    return {"payment": payment, "where": where, "why": why}


# ── step 1 · this account ─────────────────────────────────────────────────


def step_payments_on_this_account(ctx, subjects) -> dict[str, Any]:
    """1 · Applied, pending, reversed — on the account the caller named.

    ⚠ **A REVERSED PAYMENT IS STILL A PAYMENT AND IS SEARCHED HERE.** The card's
    parameter is *Include reversed and returned: on*, because *"I paid"* is true
    of a cheque that bounced — and the answer a customer needs is that it came
    and went, not that it never arrived.
    """
    account_id = ctx.params.get("account")
    start, end = _window(ctx)
    amount = _money(ctx.params.get("amount"))
    around = _around(ctx)
    include_reversed = bool(ctx.params.get("include_reversed_and_returned", True))

    if not account_id:
        # ⚠ **NOBODY NAMED AN ACCOUNT, SO THIS STEP DID NOT RUN — AND SAYING
        # *nothing found* WOULD BE A LIE.** The card's second scope is a search
        # by amount and date *"when the caller does not know which account it
        # landed on"*; step 2 does that work, and this cell reads **Not
        # checked** rather than green. A first build let this step search the
        # whole tenant and then reported the hit as *"It is on this account"* —
        # a sentence about an account nobody had named.
        return _StepResult(
            checked={
                "searched": False,
                "not_searched_because": "no account was named — this is a search by amount and date",
            }
        ).as_dict()

    rows = payments_seam.payments_matching(
        amount=amount,
        around=around,
        within_days=int(ctx.params.get("within_days") or 3),
        tolerance=str(ctx.params.get("amount_tolerance") or "0.01"),
        account_ids=[account_id],
        last_four=str(ctx.params.get("last_four") or "") or None,
    )
    if not include_reversed:
        rows = [one for one in rows if not one.get("reverses_payment_id")]
    inside = [
        one
        for one in rows
        if not one.get("posted_on")
        or start.isoformat() <= str(one["posted_on"]) <= end.isoformat()
    ]
    hit = inside[0] if inside else None
    return _StepResult(
        found={"payments": inside, "hit": _hit(hit, "this account", "It is on this account.") if hit else None},
        checked={
            "searched_account": bool(account_id),
            "payments_on_this_account": len(inside),
            "look_back_from": start.isoformat(),
            "amount": str(amount) if amount is not None else None,
            "around": around.isoformat() if around else None,
            "include_reversed_and_returned": include_reversed,
        },
    ).as_dict()


# ── step 2 · anywhere ─────────────────────────────────────────────────────


def step_same_amount_and_date_anywhere(ctx, subjects) -> dict[str, Any]:
    """2 · Every account in the tenant — **this is where mis-keyed payments hide**.

    ⚠ **THE LAST FOUR DIGITS ARE THE FINDING, NOT THE FILTER.** The card's
    worked case is a payment applied to Alvarez because both account numbers end
    4471, so this step compares the found account's number against the caller's
    and says so when they match — which is the sentence a clerk reads out.

    ⚠ **IT IS A TENANT-WIDE READ AND IT IS BOUNDED BY THE AMOUNT AND THE DATE.**
    Without one of those the step does not run at all: *"every payment in the
    utility"* is not a search, and at the top of the ICP it is a page nobody can
    read (`NFR-3`).
    """
    if not bool(ctx.params.get("search_other_accounts", True)):
        return _not_needed("searching other accounts is switched off")
    if _already_found(ctx):
        return _not_needed("the payment was found on this account")

    amount = _money(ctx.params.get("amount"))
    around = _around(ctx)
    if amount is None and around is None:
        return _StepResult(
            checked={
                "searched": False,
                "not_searched_because": "no amount and no date to search on",
            }
        ).as_dict()

    account_id = str(ctx.params.get("account") or "")
    facts = customers_seam.account_facts(account_id) if account_id else None
    mine = str((facts or {}).get("account_no") or "")
    # With no account named this step IS the search, and every row is
    # "elsewhere" in the only sense that matters: nobody has said where it
    # should have been.
    rows = payments_seam.payments_matching(
        amount=amount,
        around=around,
        within_days=int(ctx.params.get("within_days") or 3),
        tolerance=str(ctx.params.get("amount_tolerance") or "0.01"),
        last_four=str(ctx.params.get("last_four") or "") or None,
    )
    elsewhere = [one for one in rows if str(one.get("account_id")) != account_id]
    hit = None
    if elsewhere:
        first = elsewhere[0]
        theirs = str(first.get("account_no") or "")
        same_four = bool(mine) and bool(theirs) and mine[-4:] == theirs[-4:]
        hit = _hit(
            first,
            "another account" if account_id else "the search",
            (
                "The account it landed on ends in the same four digits as this one."
                if same_four
                else ("It is on another account." if account_id else "It is on this account.")
            ),
        )
        hit["same_last_four"] = same_four
    return _StepResult(
        found={"payments": elsewhere, "hit": hit},
        checked={
            "searched": True,
            "payments_on_other_accounts": len(elsewhere),
            "this_account_ends": mine[-4:] if mine else None,
        },
    ).as_dict()


# ── step 3 · reversed or returned ─────────────────────────────────────────


def step_reversed_or_returned_items(ctx, subjects) -> dict[str, Any]:
    """3 · A payment that came and went again.

    ⚠ **IT SEARCHES WHAT STEPS 1 AND 2 ALREADY READ RATHER THAN ASKING AGAIN.**
    A reversal is a payment with `reverses_payment_id` set — hard rule 4's
    *corrections are new rows* seen from the other end — so it is a property of
    rows this run already holds, and a third query could return a different set
    inside one run.
    """
    if _already_found(ctx):
        return _not_needed("the payment was already found")

    seen = [
        one
        for step in (STEP_THIS_ACCOUNT, STEP_ELSEWHERE)
        for one in (((ctx.set_results.get(step) or {}).get("found") or {}).get("payments") or [])
    ]
    reversed_rows = [
        one
        for one in seen
        if one.get("reverses_payment_id") or str(one.get("status") or "") in ("reversed", "returned")
    ]
    hit = (
        _hit(
            reversed_rows[0],
            "a reversal",
            "It arrived and was reversed — the money came and went again.",
        )
        if reversed_rows
        else None
    )
    return _StepResult(
        found={"payments": reversed_rows, "hit": hit},
        checked={"reversed_or_returned": len(reversed_rows), "rows_examined": len(seen)},
    ).as_dict()


# ── step 4 · unapplied cash ───────────────────────────────────────────────


def step_unapplied_cash_matching(ctx, subjects) -> dict[str, Any]:
    """4 · Money we hold and have not placed.

    ⚠ **A NEGATIVE CREDIT IS A REAL DEBT AND NOTHING HERE FLOORS IT** (PO ruling
    2026-08-11, `OQ-132`). A trace that clamped it at zero would tell a customer
    the utility holds nothing for them while it is owed money on the same
    account.
    """
    if _already_found(ctx):
        return _not_needed("the payment was already found")

    account_id = ctx.params.get("account")
    credit = _money(payments_seam.account_credit(account_id)) if account_id else None
    amount = _money(ctx.params.get("amount"))
    hit = None
    if credit is not None and credit > ZERO and (amount is None or credit >= amount):
        hit = _hit(
            {"amount": str(credit), "currency": "", "account_id": str(account_id)},
            "unapplied cash",
            "The utility is holding this money and has not placed it on a bill.",
        )
    return _StepResult(
        found={"credit": None if credit is None else str(credit), "hit": hit},
        checked={
            "credit_read": credit is not None,
            "credit": None if credit is None else str(credit),
            "credit_may_be_negative": True,
        },
    ).as_dict()


# ── step 5 · today's landed batch ─────────────────────────────────────────


def step_todays_landed_batch(ctx, subjects) -> dict[str, Any]:
    """5 · Arrived, not yet applied — *"it is real, just early"*.

    ⚠ **`payments` PUBLISHES NO LIST OF IMPORT BATCHES** (`S-15`), so the batch
    is a declared INPUT and a run with none reports **not checked** rather than
    *nothing found*. Those are different answers: one says the question was
    asked, the other says it was not, and hard-won law 7 is about exactly that
    difference.
    """
    if _already_found(ctx):
        return _not_needed("the payment was already found")
    if not bool(ctx.params.get("include_todays_batch", True)):
        return _not_needed("today's batch is switched off")

    batch_id = ctx.params.get("batch")
    if not batch_id:
        return _StepResult(
            checked={
                "checked": False,
                "not_checked_because": "no landed file was named on the setup screen",
                # The number beside the blind spot: nothing lists the batches,
                # so this runbook cannot go looking for one.
                "batches_this_module_can_enumerate": 0,
            }
        ).as_dict()

    batch = payments_seam.import_batch(batch_id)
    if batch is None:
        return _StepResult(
            checked={"checked": False, "not_checked_because": "no such file for this utility"}
        ).as_dict()

    amount = _money(ctx.params.get("amount"))
    rows = [
        one
        for one in (batch.get("rows") or [])
        if amount is None or _money(one.get("amount")) == amount
    ]
    hit = (
        _hit(
            {
                "amount": str(rows[0].get("amount") or ""),
                "currency": str(batch.get("currency") or ""),
                "account_no": rows[0].get("account_no"),
                "payment_no": None,
            },
            "today's file",
            "It arrived in a file that has not been applied yet.",
        )
        if rows
        else None
    )
    return _StepResult(
        found={"rows": rows, "hit": hit},
        checked={"checked": True, "rows_in_the_file": len(batch.get("rows") or []), "matching": len(rows)},
    ).as_dict()


# ── step 6 · the trace ────────────────────────────────────────────────────


def step_build_the_trace(ctx, subject) -> dict[str, Any]:
    """6 · One sentence, and the move if it is on the wrong account.

    ⚠ **THE ONLY PER-RECORD STEP** — the subject is the account (or the payment)
    a person asked about, so this runs once inside its own savepoint.
    """
    hit = _already_found(ctx)
    currency = str((hit or {}).get("payment", {}).get("currency") or "")
    amount = _money((hit or {}).get("payment", {}).get("amount"))
    if hit is None:
        return {
            "outcome": NOT_FOUND,
            "reason": "No payment matching that amount and date was found.",
            "decided_by_rule": "Every place a payment can be is searched in order",
            "fix_route": FIX_PAYMENTS,
            "data": {"label": subject.label, "where": None},
        }
    where = str(hit.get("where") or "")
    outcome = {
        "this account": FOUND_HERE,
        "the search": FOUND_HERE,
        "another account": FOUND_ELSEWHERE,
        "a reversal": FOUND_REVERSED,
        "unapplied cash": FOUND_UNAPPLIED,
        "today's file": FOUND_IN_BATCH,
    }.get(where, NOT_FOUND)
    return {
        "outcome": outcome,
        "reason": (
            f"Found {_shown(amount, currency)} on {hit['payment'].get('posted_on') or 'no date'}"
            f" — {hit['why']}"
            if amount is not None
            else f"Found it — {hit['why']}"
        ),
        "decided_by_rule": "A payment is searched for by amount and date, then by account",
        "fix_route": FIX_PAYMENTS if outcome == FOUND_ELSEWHERE else FIX_ACCOUNTS,
        "data": {
            "label": subject.label,
            "where": where,
            "same_last_four": bool(hit.get("same_last_four")),
            "payment_no": hit["payment"].get("payment_no"),
            "account_no": hit["payment"].get("account_no"),
            "amount": hit["payment"].get("amount"),
            "currency": currency,
            "posted_on": hit["payment"].get("posted_on"),
        },
    }


# ── the report ────────────────────────────────────────────────────────────


def _chain(view) -> Block:
    """Five cells: the one that found it, and the rest **Not needed**.

    ⚠ **`Not needed` IS NOT `Never reached` AND THE TWO CELLS ARE DIFFERENT
    FACTS.** Never reached means the run stopped and nobody knows; Not needed
    means the question was answered before we got there. The card draws the
    second and says so in its design note.
    """
    hit_at = None
    for step in SEARCH_STEPS:
        result = view.set_results.get(step) or {}
        if (result.get("found") or {}).get("hit"):
            hit_at = step
            break
    cells = []
    for step in SEARCH_STEPS:
        result = view.set_results.get(step) or {}
        checked = result.get("checked") or {}
        if step == hit_at:
            state, note = "bad", "Match"
        elif hit_at is not None and STEP_POSITION[step] > STEP_POSITION[hit_at]:
            state, note = "pending", "Not needed"
        elif result.get("needed") is False:
            state, note = "pending", "Not needed"
        elif checked.get("checked") is False or checked.get("searched") is False:
            # ⚠ NOT SEARCHED IS NOT NOTHING FOUND. A cell that read *Nothing*
            # over a question nobody asked is hard-won law 7's shape exactly.
            state, note = "pending", "Not checked"
        else:
            state, note = "ok", "Nothing"
        cells.append(
            {
                "id": step,
                "position": STEP_POSITION[step],
                "label": STEP_LABELS[step],
                "state": state,
                "note": note,
            }
        )
    return Block(
        block="chain",
        payload={
            "label": "Where it was looked for." if hit_at is None else "Found it.",
            "cells": cells,
        },
    )


def report(view) -> list[Block]:
    """`RB-113`'s own blocks — **Verdict · Chain · Facts · Action**.

    The Action block is *Move payment →*, and it is **enabled only when the
    payment is on another account**: a control a person may not use is drawn
    disabled WITH its reason (B14), and *move* means nothing when there is
    nothing to move.
    """
    records = list(view.records)
    record = records[0] if records else None
    found = bool(record and record.outcome != NOT_FOUND)
    data = dict(record.data) if record else {}
    currency = str(data.get("currency") or "")
    amount = _money(data.get("amount"))

    facts_rows: list[dict[str, Any]] = []
    if found:
        facts_rows = [
            {
                "id": "amount",
                "label": "Amount",
                "value": (
                    {"kind": "money", "amount": _stored(amount), "currency": currency}
                    if amount is not None
                    else {"kind": "text", "text": "—"}
                ),
            },
            {
                "id": "posted",
                "label": "Landed",
                "value": (
                    {"kind": "date", "value": str(data["posted_on"])}
                    if data.get("posted_on")
                    else {"kind": "text", "text": "No date recorded"}
                ),
            },
            {
                "id": "applied_to",
                "label": "Applied to",
                # B14 rule 31 — the account NUMBER a clerk reads, never the id.
                "value": {"kind": "text", "text": str(data.get("account_no") or "—")},
            },
            {
                "id": "reference",
                "label": "Reference",
                "value": {"kind": "text", "text": str(data.get("payment_no") or "—")},
            },
        ]
        if data.get("same_last_four"):
            facts_rows.append(
                {
                    "id": "likely_cause",
                    "label": "Likely cause",
                    "value": {
                        "kind": "text",
                        "text": "The remittance slip carried the wrong account number.",
                    },
                }
            )

    return [
        Block(
            block="verdict",
            payload={
                "word": "Found it" if found else "Not found",
                "tone": "success" if found else "warning",
                "count": record.reason if record else "Nothing was searched for.",
                "detail": (
                    "The person moves the payment; this runbook only finds it."
                    if found
                    else "Try a wider window, or search without the account."
                ),
            },
        ),
        _chain(view),
        Block(block="facts", payload={"heading": "What was found", "rows": facts_rows}),
        Block(
            block="action",
            payload=(
                {"label": "Move payment", "tier": "primary", "enabled": True}
                if data.get("where") == "another account"
                else {
                    "label": "Move payment",
                    "tier": "primary",
                    "enabled": False,
                    # B14 rule 33 — five or six words.
                    "reason": (
                        "It is already on this account"
                        if found
                        else "Nothing was found to move"
                    ),
                }
            ),
        ),
    ]


# ── the pinned scope ──────────────────────────────────────────────────────


def resolve(ctx):
    """The pinned set: **one account** — or the search itself when none is named.

    ⚠ **THE CARD'S SCOPE IS *one account, or a search by amount and date*.** A
    caller who does not know which account it landed on has no account to pin,
    and a `resolve()` that returned nothing would leave a run with no record and
    no sentence. So the subject is the account where there is one, and the
    SEARCH where there is not — `subject_type` stays `payment`, which is what is
    being traced either way (`BR-RBS-019`: the declared unit).
    """
    account_id = ctx.params.get("account")
    if account_id:
        facts = customers_seam.account_facts(account_id)
        if facts is None:
            return []
        return [
            SubjectRef(
                subject_type="payment",
                subject_id=str(account_id),
                label=str(facts.get("label") or facts.get("account_no") or ""),
            )
        ]
    amount = ctx.params.get("amount")
    around = ctx.params.get("around")
    if amount is None and around is None:
        return []
    return [
        SubjectRef(
            subject_type="payment",
            subject_id="search",
            # B14 rule 31 — what was searched for, in words.
            label=f"{amount or 'any amount'} around {around or 'any date'}",
        )
    ]


RUNBOOK = RunbookDefinition(
    key=KEY,
    name="Payment trace",
    kind=models.KIND_CHECK,
    category="payments",
    subject_type="payment",
    unit_of_work="one payment a customer is asking about",
    triggers=(models.TRIGGER_MANUAL,),
    tags=("Customer portal",),
    parameters=(
        Parameter(name="account", type=PARAM_REF_OBJECT, label="Account"),
        Parameter(name="amount", type=PARAM_MONEY, label="Or amount", default=None),
        Parameter(name="around", type=PARAM_TEXT, label="Around"),
        Parameter(name="within_days", type=PARAM_DAYS, label="Within", default=3),
        Parameter(
            name="last_four",
            type=PARAM_TEXT,
            label="Last four of cheque or card",
        ),
        Parameter(name="look_back", type=PARAM_DAYS, label="Look back", default=90),
        Parameter(
            name="amount_tolerance",
            type=PARAM_MONEY,
            label="Amount tolerance",
            # A STRING, never a float (hard rule 2 — this lives in `jsonb`).
            default="0.0100",
        ),
        Parameter(
            name="search_other_accounts",
            type=PARAM_TOGGLE,
            label="Search other accounts",
            default=True,
        ),
        Parameter(
            name="include_reversed_and_returned",
            type=PARAM_TOGGLE,
            label="Include reversed and returned",
            default=True,
        ),
        Parameter(
            name="include_todays_batch",
            type=PARAM_TOGGLE,
            label="Include today's unapplied batch",
            default=True,
        ),
        Parameter(
            name="batch",
            type=PARAM_REF_OBJECT,
            label="Today's landed file",
            # ⚠ DECLARED BECAUSE NOTHING LISTS THEM (`S-15`). A clerk names the
            # file; this runbook cannot go looking for one.
        ),
    ),
    resolve=resolve,
    report=report,
    steps=(
        Step(key=STEP_THIS_ACCOUNT, label=STEP_LABELS[STEP_THIS_ACCOUNT], mode=MODE_SET, run=step_payments_on_this_account),
        Step(key=STEP_ELSEWHERE, label=STEP_LABELS[STEP_ELSEWHERE], mode=MODE_SET, run=step_same_amount_and_date_anywhere),
        Step(key=STEP_REVERSED, label=STEP_LABELS[STEP_REVERSED], mode=MODE_SET, run=step_reversed_or_returned_items),
        Step(key=STEP_UNAPPLIED, label=STEP_LABELS[STEP_UNAPPLIED], mode=MODE_SET, run=step_unapplied_cash_matching),
        Step(key=STEP_BATCH, label=STEP_LABELS[STEP_BATCH], mode=MODE_SET, run=step_todays_landed_batch),
        # ⚠ THE ONLY PER-RECORD STEP — the card's own *per record (1)*.
        Step(key=STEP_TRACE, label=STEP_LABELS[STEP_TRACE], mode=MODE_PER_RECORD, run=step_build_the_trace),
    ),
)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-025 (EP-RBS-05; CR-075 wave S)
# generated: 2026-09-07 by the CR-075 wave S build lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint — every runbooks route is a GET and POST /runbooks/{key}/runs is wave L) E=n/a(no screen — RBS-004 and RBS-006 render any runbook; RB-020) F✔ G✔ H=n/a(no 🔒 path: this composes no idempotency key, moves no payment and posts no ledger line)
# gates: pytest tests/test_us_rbs_025_payment_trace.py · pytest tests/test_us_rbs_015_conformance.py · G115 · G20
# exceptions: step 5 takes the landed file as a declared INPUT because `payments` publishes no list of import batches (`13-selector-inventory.md` S-15), and a run with none reports NOT CHECKED rather than *nothing found* · *Not needed* and *Never reached* are different cells and this runbook keeps them apart · the *Move payment →* action is enabled ONLY where the payment is on another account, and carries its reason otherwise · a negative account credit is never floored (PO ruling 2026-08-11, `OQ-132`) · `account` and `batch` are `ref:object` with no tenant-resolved DOMAIN, which is wave `T`'s
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
