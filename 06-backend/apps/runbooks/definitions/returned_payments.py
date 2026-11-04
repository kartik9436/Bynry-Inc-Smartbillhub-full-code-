# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-036 (EP-RBS-05) — CR-075 wave R′, the payments half:
#           runbook 26, registered as an Action holding three ports, DISABLED
#           for live, guards evaluated BEFORE step 1.
# Rules:    BR-RBS-013 (no UPDATE or DELETE on a payment; a correction is a NEW
#           row through the OWNING module — CLAUDE.md hard rule 4) ·
#           BR-RBS-018 (a money-bearing action carries a second approval —
#           OQ-RBS-1732 CLOSED 2026-09-06 with NO threshold) · BR-RBS-027 (a
#           step that could not run reads Never reached) · BR-RBS-012 (guards
#           are absolute) · BR-RBS-014 (a SAMPLE record is never acted on) ·
#           BR-RBS-010 (every record names its rule, in words) · BR-RBS-003
#           (dry and live are one path) · BR-PAY-013 (N returns → the cash-only
#           / no-autopay privilege) · BR-PAY-002 (a reversal is a NEW row) ·
#           BR-PAY-1070 (reversing a payment is Admin-only, and the gate is on
#           the SERVICE) · BR-BIL-007 (the returned-payment fee is the tenant's
#           charge code, never typed) · PO ruling 2026-09-06 (*"in absence of
#           API conenctions you will not find anything and you can stop the job
#           saying APi or conenct not available; that is a valid case and state
#           for us"*)
# Tests:    06-backend/tests/test_us_rbs_036_returned_payments.py
# Impacts:  apps/runbooks/definitions/__init__.py (the one registration line) ·
#           apps/runbooks/seams/payments_seam.py ·
#           apps/payments/runbook_reads.py (the reads added with it)
# ───────────────────────────────────────────────────────
"""Runbook 26 — **Returned payments**. It STOPS, and the stop is the deliverable.

WHAT IT WOULD DO, IN ONE SENTENCE
-----------------------------------
It takes each payment the bank returned, plans the reversal, applies the return
fee behind a second approval, tells the customer, and removes the payment
privilege once an account has returned enough items.

⚠⚠ AMENDED 2026-10-07 (`CR-175-BRC10`, `DEF-PAY-10010`) — IT NO LONGER STOPS
------------------------------------------------------------------------------
**The section below describes the world before 2026-10-07 and is kept as the
record of it.** Its absence 2 — *no column holds a bank return code* — went
false when `CR-174-BRC10` added `payments.return_code`, and the read was never
asked again, so a US Payments return reached this runbook only as a count and
no fee or notice followed. `payments.runbook_reads.returned_items_landed` now
answers with every reversing row that carries a bank code — US Payments'
returns and a billing clerk's *Mark returned* on an ACH payment alike (PO
2026-10-07: *"The same effect follows: balance restored, fee and notice."*).
Those are ALREADY reversed (the PO's reading (A)), so step 4 reports
*Already reversed* and step 5 drafts the fee and handles the notice; an `nsf`
return's letter went with its reversal and is not queued twice. Absence 3 —
no port reverses a payment — still holds for any item the feed cannot show as
reversed.

⚠ WHAT ACTUALLY HAPPENED ON EVERY DEPLOYMENT UNTIL 2026-10-07: **IT STOPPED AT STEP 1**
--------------------------------------------------------------------------
There is no returns feed, and the run says so on a designed screen rather than
reporting a clean morning. The Product Owner ruled on 2026-09-06, verbatim:
*"in absence of API conenctions you will not find anything and you can stop the
job saying APi or conenct not available; that is a valid case and state for
us"*. Wave `P`'s cash application is the shape this follows — a **WHAT TO DO**
box, later steps reading **Never reached** (`BR-RBS-027`), **no KPI strip** over
a run that examined nothing, and the word *failed* nowhere on the page.

**THREE THINGS ARE MISSING AND EACH IS A DIFFERENT ABSENCE. They are stated
here once, because a lane that fixed only one would still have a runbook that
cannot run.**

1. **NO RETURNS OPERATION ON ANY CONNECTION.** `integrations` connects, holds
   keys and owns the lifecycle of a connection (`BR-INT-054` as amended
   2026-09-06); no manifest declares a returns or NSF-advice operation, and
   `batch.landed` is emitted by nothing at all — verified 2026-09-06 by wave `Q′`
   and again for this wave.
2. **NO COLUMN ANYWHERE HOLDS A BANK RETURN CODE OR ITS REASON.** `BankLine` is
   `posted_on`, `reference`, `amount` and its statement, and nothing links a
   returned item back to the payment it reverses. So a statement carrying returns
   could not be READ as returns, and `RB-126`'s sibling promise — *the bank's
   reason in words* — has no source. Runbook 17 in this same wave records the
   same absence from the other end.
3. **THE REVERSAL ITSELF HAS NO PORT.** `apps.payments.reversal.reverse_payment`
   exists, is complete, and is **Admin-only on the SERVICE** (`BR-PAY-1070`,
   `CR-059` CS-5) — and `apps/payments/runbook_ports.py` deliberately binds it to
   nothing: *"approve_refund, issue_refund, reconcile_batch and the
   correct-reference path are deliberately NOT bound to any port."* `US-RBS-036`
   §5's own port list agrees — `apply_fee`, `queue_notice`, `flag_account` and no
   reversal. **So even with a feed, this runbook could plan a reversal and never
   perform one**, and the reversal service's own docstring already names the
   collision: *"a gateway returns feed has no user and therefore no role … that
   is a decision CS-1 must make when the rails land."*

**`OQ-RBS-1741` carries all three** and is OPEN. Nothing here is stubbed and no
`NotImplementedError` is raised: what ships is a runbook that stops with a
sentence a clerk can act on, which is the shipped behaviour the ruling asks for
and not a gap awaiting an answer (`boundary.py` takes the same posture and says
so in the same words).

⚠ **WHAT IS BUILT AND IS NOT WAITING FOR ANY OF THAT.** Steps 2 to 6 are written
against the seam and are proved in `test_us_rbs_036_returned_payments.py` with a
returns feed supplied — the match, the prior-return count against `BR-PAY-013`'s
limit, the fee behind the second approval, the notice, and the privilege. **The
day the feed lands, this runbook works without a line changing here**, and that
is the point of building it now rather than when the feed arrives.

⚠ **A REVERSAL IS A NEW ROW, NEVER AN EDIT** (hard rule 4, `BR-PAY-002`,
`TC-RBS-036.1`). Nothing in this file updates a payment, and nothing in it may
ever be widened towards the one narrow exception hard rule 4 carries — a runbook
that could rewrite a cheque number is a runbook that can rewrite the evidence.

WHAT THIS FILE DIVERGES FROM `RB-126` ON, AND WHY — RECORDED, NOT APPLIED SILENTLY
-----------------------------------------------------------------------------------
**1 · THE CARD IS RESERVED AND ITS RESULT SCREEN IS NOT DRAWN.** `RB-126` says so
in its own opening lines. So the report below is composed from the twelve blocks
that already exist (`BR-RBS-021`) and **invents no screen** — which is phase 5's
own rule: *if one of these seems to need a new block or a new screen, the
contract failed*. It did not.

**2 · THE CARD SAYS *Steps 6 · 3 read, 3 write* AND THIS DECLARES SIX**, because
here the card's step 1 is a real step and not `resolve()`. A returns feed decides
whether the run happens at all, so it is a step that can STOP; `resolve()` then
pins whatever step 1 found.

**3 · THE PRIVILEGE COUNT IS READ FROM THE REVERSING ROWS, NOT FROM
`accounts.nsf_count`.** `BR-PAY-013`'s `nsf_count++` is customers' write and
`apps/payments/reversal.py` records that **it does not happen** — every reversal
carries `nsf_count_not_incremented` because there is no service on the far side
(`DEF-069`). A limit read off a counter nothing increments would never be reached
on any account, ever, which is the quietest possible failure for a rule whose job
is to stop somebody paying by cheque.
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
    Block,
    Guard,
    Parameter,
    RunbookDefinition,
    Step,
    SubjectRef,
)
from apps.runbooks.engine import acts, duplicates
from apps.runbooks.seams import customers_seam, payments_seam

RUNBOOK_KEY = "returned_payments"

STEP_GATHER = "gather"
STEP_MATCH = "match"
STEP_PRIOR = "prior_returns"
STEP_REVERSE = "reverse"
STEP_FEE = "fee_and_notice"
STEP_PRIVILEGE = "privilege"

STEP_LABELS = {
    STEP_GATHER: "Gather the returned items",
    STEP_MATCH: "Match each to its payment",
    STEP_PRIOR: "Count prior returns",
    STEP_REVERSE: "Reverse the payment",
    STEP_FEE: "Apply the fee and queue the notice",
    STEP_PRIVILEGE: "Remove the privilege after N",
}

#: Every outcome word a clerk reads. `planned` is the ENGINE's.
OUTCOME_TO_REVERSE = "to_reverse"
OUTCOME_NO_MATCH = "no_match"
OUTCOME_ALREADY_REVERSED = "already_reversed"
OUTCOME_PRIVILEGE_REMOVED = "privilege_removed"
OUTCOME_SKIPPED = "skipped"
OUTCOME_FAILED = "failed"
OUTCOME_HELD = "held"

#: CR-175-BRC10 — the notice a `nsf` return's REVERSAL already queued, so this
#: runbook queues none. A word for the record's data, never a clerk's sentence.
NOTICE_QUEUED_BY_REVERSAL = "queued_by_reversal"

#: Tenant-relative fix routes, prefixed with `/:tenant/` by the shell. Each is a
#: path this product actually mounts (`App.tsx`, checked 2026-09-07).
FIX_PAYMENTS = "payments"
FIX_ACCOUNT = "customers"
FIX_INTEGRATIONS = "settings/integrations"


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

    `BR-TEN-043`, gate `G6`. A returns run re-taken for last Tuesday must take
    last Tuesday's items; a wall clock makes that impossible to express or test.
    """
    given = ctx.params.get("as_of")
    if isinstance(given, dt.date):
        return given
    if isinstance(given, str) and given:
        return dt.date.fromisoformat(given)
    raise ValueError(
        "runbook 26 needs the business day it is being run for. It is a parameter and never a "
        "clock read (BR-TEN-043): a returns run re-taken for last Tuesday must take last "
        "Tuesday's items, and a reversal is booked on the day the bank returned the item."
    )


def _feed(ctx: Any) -> dict[str, Any]:
    """The returns feed, asked ONCE. **It answers with an absence, not a list.**

    Read the module docstring before changing this. `payments_seam
    .returned_items_landed` reports `feed_available: False` with three named
    absences and the number of items a PERSON reversed by hand in the window —
    because a blind spot with no figure beside it cannot be told from an empty
    one (hard-won law 7).
    """
    return _memo(
        ctx,
        "_feed",
        lambda: payments_seam.returned_items_landed(
            as_of=_as_of(ctx), window_days=int(ctx.params.get("window_days") or 1)
        ),
    )


def _feed_items(ctx: Any) -> dict[str, Any]:
    """The feed's own rows, keyed by item — **readable BEFORE step 1 runs.**

    ⚠ **THIS EXISTS BECAUSE THE GUARDS CANNOT READ A STEP'S RESULTS, AND THE
    FIRST DRAFT OF THIS FILE TRIED TO.** `BR-RBS-012` evaluates a guard BEFORE
    any step, so `ctx.set_results[STEP_GATHER]` is empty when a guard is asked —
    both guards read `{}`, both returned `False`, and **a sample account would
    have been charged a returned-payment fee and stripped of its right to pay by
    cheque.** Nothing but the guard's own test could see it: the run looked
    perfect, every record carried its rule, and the two accounts that should have
    vanished were simply present.

    The feed is memoised, so asking it here and in `resolve()` is one read.
    """
    return {str(row["item_id"]): row for row in _feed(ctx).get("rows", ())}


def guard_sample(ctx: Any, subject: SubjectRef) -> bool:
    """`BR-RBS-014` — **a sample record is never acted on, in any tenant, ever.**

    A demo account charged a returned-payment fee and stripped of its right to
    pay by cheque is the same failure as a demo account receiving a disconnection
    notice, and it costs money as well as embarrassment.
    """
    row = _feed_items(ctx).get(str(subject.subject_id), {})
    account_id = str(row.get("account_id") or "")
    return bool(account_id) and account_id in _memo(
        ctx, "_sample_ids", customers_seam.sample_account_ids
    )


def guard_already_reversed(ctx: Any, subject: SubjectRef) -> bool:
    """`RB-126`'s *Never include: Already reversed* — the card's own guard.

    A payment a person already reversed on `S35` has had its ladder restarted,
    its letter queued and its privilege counted by `reverse_payment` itself. A
    runbook that reversed it again would double the fee and double the letter,
    and hard rule 4 means neither could be taken back.

    ⚠ **A RETURN THAT WAS REVERSED WHEN IT WAS RECORDED IS NOT EXCLUDED
    (`CR-175-BRC10`, 2026-10-07).** Since that day the feed IS the reversing
    rows that carry a bank code — US Payments' returns and a clerk's ACH returns
    — so every one of them is already reversed, by the act that recorded it,
    and its fee and notice are exactly what this runbook is FOR. Such a row
    names its reversal (`reversal_no`); the engine's idempotency key on the item
    keeps a second run from drafting a second fee. What this guard still keeps
    out is an item the feed matched to a payment somebody reversed by some OTHER
    path, which no row names.
    """
    row = _feed_items(ctx).get(str(subject.subject_id), {})
    return bool(row.get("already_reversed")) and not row.get("reversal_no")


# ── resolve — the pinned set ──────────────────────────────────────────────


def _items(ctx: Any) -> dict[str, Any]:
    """The returned items step 1 found, keyed by item — `{}` when it stopped."""
    gathered = ctx.set_results.get(STEP_GATHER) or {}
    if gathered.get("stop"):
        return {}
    return {str(one["item_id"]): one for one in gathered.get("items", ())}


def resolve(ctx: Any):
    """Every returned item this run will work, pinned ONCE.

    ⚠ **THIS RESOLVES TO NOTHING WHEN THE FEED IS SHUT, AND THE RUN STILL
    PRODUCES A SCREEN.** An empty scope with a stop behind it is a designed
    state, not a failure: the report draws the chain with step 1 red and every
    later step **Never reached** (`BR-RBS-027`) and no KPI strip at all.

    The scope is the feed's own list — this module never matches, ages or
    interprets a bank item; `payments` owns all of that and the seam is where it
    is asked.
    """
    return [
        SubjectRef(
            subject_type="payment",
            subject_id=str(row["item_id"]),
            # ⚠ THE PAYMENT'S OWN NUMBER, NEVER A DATABASE ID (B14 rule 31).
            label=str(row.get("label") or row.get("reference") or ""),
        )
        for row in _feed(ctx).get("rows", ())
    ]


# ── steps ─────────────────────────────────────────────────────────────────


def step_gather(ctx: Any, subjects) -> dict[str, Any]:
    """1 · SET · read — **and the run STOPS here on every deployment today.**

    ⚠ **THE STOP IS A RESULT AND IT IS WRITTEN AS ONE.** `RUN_STATUS_STOPPED`
    already exists beside `done` and `failed`; nothing here raises, nothing
    crashes, and every later step reads *Never reached* (`BR-RBS-027`). The
    headline is one sentence a clerk can act on, and the detail names what is
    missing — because *"no connection"* alone sends somebody to Settings when
    what they actually needed to know is that this product has nowhere to record
    a bank's return code.

    ⚠ **THE NUMBER GOES BESIDE THE ABSENCE.** *"4 returned items were reversed by
    hand in this window"* is the only figure on this deployment that would move
    if the feed arrived, and printing the stop without it would leave a cashier
    unable to tell *nothing bounced* from *nothing can tell us*.
    """
    feed = _feed(ctx)
    checked = {
        "returns_feed_available": bool(feed.get("feed_available")),
        "window_from": feed.get("from"),
        "window_to": feed.get("to"),
        "items_found": len(feed.get("rows", ())),
        "already_reversed_by_hand": feed.get("already_reversed_by_hand", 0),
        "missing": list(feed.get("missing", ())),
    }
    if not feed.get("feed_available"):
        by_hand = int(feed.get("already_reversed_by_hand") or 0)
        return {
            "reached": True,
            "items": [],
            "checked": checked,
            "stop": {
                # B14 rule 33 — short, and it is a state rather than a failure.
                "headline": "No returns have landed.",
                "detail": (
                    "No bank returns feed is connected, and nothing in this product records "
                    "the code a bank sends back with a returned item — so returned payments "
                    "cannot be found automatically. "
                    + (
                        f"{by_hand} were reversed by hand in this window."
                        if by_hand
                        else "None was reversed by hand in this window either."
                    )
                    + " Connect a payment provider, or reverse a returned item on the payment."
                ),
                "fix_route": FIX_INTEGRATIONS,
                "fix_label": "Connect a provider",
            },
        }
    return {"reached": True, "items": list(feed.get("rows", ())), "checked": checked}


def step_match(ctx: Any, subjects) -> dict[str, Any]:
    """2 · SET · read — each returned item to its payment, by reference and amount.

    **PAYMENTS DOES THE MATCHING AND THIS READS THE ANSWER.** The card's *"By
    reference, amount and date"* is the same ladder `payment_import._match_row`
    already walks for money coming IN, and a second implementation of it here
    would be how a screen and a runbook end up disagreeing about whose money it
    is (`RBR-03`'s shape, one level down).

    An item that matches nothing is `no_match` with a route to the payments
    screen — never dropped. A returned item nobody can place is exactly the row a
    cashier must see.
    """
    if _stopped(ctx):
        return _never_reached(ctx)
    items = _items(ctx)
    matched = {
        key: row for key, row in items.items() if row.get("payment_id")
    }
    return {
        "reached": True,
        "matched": matched,
        "unmatched": [key for key in items if key not in matched],
        "items_looked_at": len(items),
        "matched_count": len(matched),
    }


def step_prior_returns(ctx: Any, subjects) -> dict[str, Any]:
    """3 · SET · read — how many items each account has returned, against the limit.

    `BR-PAY-013`: after N returns the account loses its payment privilege, and N
    is `nsf_privilege_n` in Settings (`RBR-03` — read, never duplicated onto a
    card).

    ⚠ **COUNTED FROM THE REVERSING ROWS AND NOT FROM `accounts.nsf_count`** —
    divergence 3 in the module docstring. `nsf_count` is never incremented on
    this product, so a limit read off it would never be reached on any account.
    """
    if _stopped(ctx):
        return _never_reached(ctx)
    items = _items(ctx)
    account_ids = {str(row.get("account_id")) for row in items.values() if row.get("account_id")}
    settings = payments_seam.plan_notice_settings()
    limit = settings.get("returns_before_privilege_lost")
    counts = payments_seam.returned_payment_counts(sorted(account_ids)) if account_ids else {}
    return {
        "reached": True,
        "prior": counts,
        "limit": limit,
        "settings_readable": bool(settings.get("readable")) and limit is not None,
        "why_not": settings.get("why_not", ""),
        "at_the_limit": len(
            [
                account
                for account, one in counts.items()
                if limit is not None and one + _new_here(items, account) >= int(limit)
            ]
        ),
    }


def step_reverse(ctx: Any, subject: SubjectRef) -> dict[str, Any]:
    """4 · PER RECORD · **writes** — the reversal, PLANNED. It cannot be performed.

    ⚠ **READ THE MODULE DOCSTRING BEFORE CHANGING THIS.** There is no port that
    reverses a payment: `reverse_payment` is Admin-only on the SERVICE
    (`BR-PAY-1070`) and is bound to nothing, deliberately. `US-RBS-036` §5's own
    port list agrees. So this step states what must happen, with the amount and
    the rule, and routes to the payment — where a named Admin performs it.

    ⚠ **IT IS DECLARED `writes=True` THOUGH IT WRITES NOTHING.** The declaration
    is what the setup screen draws and what the contract refuses on a Check, and
    the day the port exists this becomes an `acts.perform` call with no other
    change. Declaring it `read` would hide the absence on every screen that lists
    what this runbook can do — hard-won law 2's mirror.

    ⚠ **A REVERSAL IS A NEW ROW, NEVER AN EDIT** (`TC-RBS-036.1`, hard rule 4).
    Nothing here touches the original payment, and when the port lands it must
    delegate to `payments`' own service rather than composing a row: the reversing
    payment, its reversing allocations, the ledger's mirror and the audit row
    commit together or none of them does.
    """
    if _stopped(ctx):
        return {
            "outcome": OUTCOME_SKIPPED,
            "decided_by_rule": "The run stopped before this step",
            "reason": "no returned items landed, so there was nothing to reverse.",
            "fix_route": FIX_INTEGRATIONS,
        }
    row = _items(ctx).get(str(subject.subject_id))
    if row is None:
        return {
            "outcome": OUTCOME_SKIPPED,
            "decided_by_rule": "Only the pinned set is walked",
            "reason": "this item was not in the set when the run pinned its scope.",
        }
    if not row.get("payment_id"):
        return {
            "outcome": OUTCOME_NO_MATCH,
            "decided_by_rule": "A returned item is matched by reference, amount and date",
            "reason": "this returned item matches no payment we recorded.",
            "fix_route": FIX_PAYMENTS,
            "data": _record_data(row),
        }
    amount = _money(row.get("amount"), Decimal("0"))
    if row.get("reversal_no"):
        # CR-175-BRC10 — the return was reversed when it was RECORDED (US
        # Payments' return notification, or a clerk's Mark returned): the PO's
        # reading (A). This step reports that fact; it never writes a second
        # reversal, and the fee and notice in step 5 are what is left to do.
        return {
            "outcome": OUTCOME_ALREADY_REVERSED,
            "decided_by_rule": "A return is reversed when it is recorded",
            "reason": (
                f"{_display(amount)} came back: {row.get('bank_said') or 'the bank returned it'}. "
                f"Reversed as {row['reversal_no']}."
            ),
            "fix_route": FIX_PAYMENTS,
            "data": _record_data(row, reversal_no=row["reversal_no"]),
        }
    return {
        "outcome": OUTCOME_TO_REVERSE,
        "decided_by_rule": "A returned item reverses the payment it came from",
        # The sentence says what is true — a person performs it — rather than
        # implying the money has already moved back.
        "reason": (
            f"{_display(amount)} came back: {row.get('bank_said') or 'the bank returned it'}. "
            "Reverse this payment; only an administrator can."
        ),
        "fix_route": FIX_PAYMENTS,
        "data": _record_data(row, reversal_needs_an_admin=True),
    }


def step_fee_and_notice(ctx: Any, subject: SubjectRef) -> dict[str, Any]:
    """5 · PER RECORD · **writes** — the fee behind the second approval, then the notice.

    ⚠ **THE FEE FIRES ONLY WHERE A TENANT NAMED THE CHARGE CODE**, which is
    runbook 8's divergence 3 and the same rule: `BR-BIL-007` makes the
    returned-payment fee the tenant's own charge code, *never typed*, and whether
    a customer owes a fee is BILLING's (`BR-BIL-001`/`008`). **A runbook must not
    decide that a customer owes a fee**; it can only carry out a code a utility
    has already named. `apply_fee` DRAFTS the bill and
    `billing.fee_bill.issue_charge_fee` — which is bound to no port at all — is
    what a person issues.

    ⚠ **THAT IS `BR-RBS-018`'s SECOND APPROVAL WRITTEN INTO THE SHAPE OF THE
    CODE**, and `OQ-RBS-1732` closed on 2026-09-06 with **every** money-bearing
    action carrying it and no threshold at all. There is deliberately no
    threshold parameter here and adding one would be a new ruling.

    ⚠ **THE NOTICE GOES AFTER THE BATCH APPROVAL AND THE FEE AFTER THE SECOND
    ONE** — two approvals, two moments, and the card says so. The word is
    `Queued`, never `Sent` (`RBR-07`).
    """
    if _stopped(ctx):
        return {
            "outcome": OUTCOME_SKIPPED,
            "decided_by_rule": "The run stopped before this step",
            "reason": "no returned items landed, so nobody is owed a fee or a letter.",
            "fix_route": FIX_INTEGRATIONS,
        }
    row = _items(ctx).get(str(subject.subject_id))
    if row is None or not row.get("payment_id"):
        return {
            "outcome": OUTCOME_SKIPPED,
            "decided_by_rule": "A fee follows a matched item",
            "reason": "nothing was matched, so there is no account to charge or tell.",
        }
    verdict = _run_level(ctx)
    if verdict.is_duplicate:
        return {
            "outcome": OUTCOME_ALREADY_REVERSED,
            "decided_by_rule": "This job already ran and was approved",
            "reason": verdict.message,
            "data": _record_data(row),
        }

    code = str(ctx.params.get("returned_payment_charge_code") or "").strip()
    account = SubjectRef(
        subject_type="account",
        subject_id=str(row["account_id"]),
        label=str(row.get("account_no") or ""),
    )
    fee_outcome = "no_charge_code"
    if code:
        fee = acts.perform(
            ctx,
            acts.ActRequest(
                port="apply_fee",
                action_kind="apply_fee",
                subject=account,
                planned_action=f"Draft the {code} fee",
                # One fee per returned ITEM, so a second return next month is a
                # different key and is charged again.
                discriminator=f"{row['item_id']}|{code}",
                decided_by_rule="This utility's returned-payment charge code",
                reason="a payment on this account came back",
                payload={
                    "actor": acts.actor_for(ctx),
                    "account_id": account.subject_id,
                    "charge_code": code,
                    "on_date": _as_of(ctx),
                    "due_days": int(ctx.params.get("fee_due_days") or 0),
                },
            ),
        )
        fee_outcome = fee.outcome

    amount = _money(row.get("amount"), Decimal("0"))
    if row.get("letter_queued_by_reversal"):
        # CR-175-BRC10 — an `nsf` return's reversal already queued the
        # customer's *payment failed* letter (`receipts.queue_failed_payment_
        # notice`, switchable on Settings → Notifications). A second letter
        # from here would tell the customer twice; the outcome says where the
        # notice went instead of pretending this step sent it.
        return {
            "outcome": _outcome(fee_outcome, OUTCOME_TO_REVERSE)
            if code
            else OUTCOME_ALREADY_REVERSED,
            "decided_by_rule": "A customer is told when a payment comes back",
            "reason": (
                f"{_display(amount)} came back. The letter went with the reversal. "
                + (
                    "The fee waits for a second person."
                    if code
                    else "No returned-payment charge code is set, so no fee is applied."
                )
            ),
            "fix_route": FIX_ACCOUNT,
            "data": _record_data(row, fee=fee_outcome, notice=NOTICE_QUEUED_BY_REVERSAL),
        }
    notice = acts.perform(
        ctx,
        acts.ActRequest(
            port="queue_notice",
            action_kind="queue_notice",
            subject=account,
            planned_action="Tell them the payment came back",
            discriminator=str(row["item_id"]),
            decided_by_rule="A customer is told when a payment comes back",
            reason=str(row.get("bank_said") or "the bank returned the payment"),
            amount=amount,
            currency=row.get("currency"),
            payload={
                "runbook_key": ctx.runbook_key,
                "account_id": account.subject_id,
                "subject_id": account.subject_id,
                "discriminator": str(row["item_id"]),
                "actor": acts.actor_for(ctx),
                "channels": tuple(_channels(ctx)),
            },
        ),
    )
    return {
        "outcome": _outcome(notice.outcome, OUTCOME_TO_REVERSE),
        "decided_by_rule": "A customer is told when a payment comes back",
        "reason": (
            f"{_display(amount)} came back. "
            + (
                "The fee waits for a second person."
                if code
                else "No returned-payment charge code is set, so no fee is applied."
            )
        ),
        "fix_route": FIX_ACCOUNT,
        "data": _record_data(row, fee=fee_outcome, notice=notice.outcome),
    }


def step_privilege(ctx: Any, subjects) -> dict[str, Any]:
    """6 · SET · **writes** — `BR-PAY-013`'s privilege, and the port REFUSES.

    After N returns an account loses the right to pay by cheque or by autopay.
    The port is `flag_account`, it **binds no writer** (`DEF-RBS-4331`) —
    `customers` carries only `cash_only` and its own rule is that nothing
    auto-clears it — and `BR-RBS-040` forbids the obvious substitute of writing a
    note.

    So the port is **called anyway and its own refusal is recorded**, which is
    wave `Q′`'s model and `BR-RBS-003`'s requirement: dry and live are one code
    path, and an `if is_bound` branch would be a second path proving nothing
    about the first.

    ⚠ **`TC-RBS-036.3` — THE REMOVAL NAMES ITS RULE.** A privilege that vanished
    silently is the one thing a customer will ring about and nobody will be able
    to explain, so the sentence and the count travel together whether the write
    lands or not.
    """
    if _stopped(ctx):
        return _never_reached(ctx)
    prior = ctx.set_results.get(STEP_PRIOR, {})
    limit = prior.get("limit")
    if not prior.get("settings_readable"):
        return {
            "reached": True,
            "removed": 0,
            "refused": "",
            "reason": (
                "nobody has set how many returned payments cost an account its payment "
                "privilege, so none was removed."
            ),
        }
    items = _items(ctx)
    counts = dict(prior.get("prior", {}))
    removed: list[str] = []
    refused = ""
    for row in items.values():
        account_id = str(row.get("account_id") or "")
        if not account_id:
            continue
        # This return plus the ones already recorded.
        # This return plus the ones already recorded — and a return that was
        # reversed when it was RECORDED is already one of those rows, so it is
        # not counted twice (`CR-175-BRC10`).
        total = int(counts.get(account_id, 0)) + (0 if row.get("reversal_no") else 1)
        if total < int(limit):
            continue
        try:
            ctx.port("flag_account").call(
                account_id=account_id,
                reason=(
                    f"{total} payments have come back, so this account pays by cash only"
                ),
            )
        except PortNotBound as refusal:
            refused = str(refusal)
        else:
            removed.append(account_id)
    return {
        "reached": True,
        "removed": len(removed),
        "at_the_limit": prior.get("at_the_limit", 0),
        # The port's OWN refusal, in its own words, recorded rather than hidden.
        "refused": refused,
        "limit": limit,
        "reason": f"An account loses the privilege after {limit} returned payments.",
    }


# ── stop plumbing (the shape wave P's cash application set) ───────────────


def _new_here(items: dict[str, Any], account_id: str) -> int:
    """Returns in this run on this account that are NOT yet a reversing row.

    A return reversed when it was recorded is already counted by
    `returned_payment_counts`; adding one for it would trip the privilege a
    return early (`CR-175-BRC10`).
    """
    mine = [row for row in items.values() if str(row.get("account_id") or "") == account_id]
    return 0 if mine and all(row.get("reversal_no") for row in mine) else 1


def _stopped(ctx: Any) -> bool:
    """Did step 1 stop the run? Every later step asks before doing anything."""
    return bool((ctx.set_results.get(STEP_GATHER) or {}).get("stop"))


def _never_reached(ctx: Any) -> dict[str, Any]:
    """`BR-RBS-027` — a step that did not run says so, rather than sitting blank.

    A blank cell reads as *nothing wrong*; **Never reached** reads as *it never
    ran, because something earlier stopped the run*. They are opposite sentences
    and only one of them is true.
    """
    stop = (ctx.set_results.get(STEP_GATHER) or {}).get("stop") or {}
    return {"reached": False, "never_reached_because": stop.get("headline", "")}


# ── the run-level duplicate check (OQ-RBS-1737, CLOSED 2026-09-06) ────────


def _run_level(ctx: Any):
    """Ask ONCE per run whether this job already ran — never once per item."""

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
    """TWO compositions, because a stopped run and a finished one are two states.

    * **stopped** — `Verdict` · `Sentence` · `Chain` · `Records` (empty). The
      chain draws step 1 red and the five later steps **Never reached**, and the
      **KPI strip is deliberately ABSENT**: a strip reading *0 reversed · $0.00 ·
      0 need a person* over a run that examined nothing is indistinguishable from
      a clean morning, which is precisely the failure hard-won law 7 is about.
      The word *failed* appears nowhere — the Product Owner ruled this a valid
      state, and a screen that called it a failure would be arguing with them.
    * **finished** — `Verdict` · `KPIs` · `Breakdown` · `Records` · `Downloads`,
      which is `US-RBS-036`'s own block list plus the verdict the header consumes.

    Every name is one of the twelve (`BR-RBS-021`); no thirteenth is minted, and
    `RB-126`'s undrawn result screen needed none.
    """
    gathered = dict(view.set_results.get(STEP_GATHER, {}))
    stop = gathered.get("stop")
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
            _chain(view, stop),
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

    counts = dict(view.counts)
    match = dict(view.set_results.get(STEP_MATCH, {}))
    prior = dict(view.set_results.get(STEP_PRIOR, {}))
    privilege = dict(view.set_results.get(STEP_PRIVILEGE, {}))
    items = {str(one["item_id"]): one for one in gathered.get("items", ())}
    currency = _currency_of(items)
    value = sum((_money(one.get("amount"), Decimal("0")) for one in items.values()), Decimal("0"))

    return [
        Block(
            block="verdict",
            payload={
                "word": "To reverse",
                "tone": "warning" if items else "success",
                "count": (
                    f"{counts.get(OUTCOME_TO_REVERSE, 0)} to reverse. "
                    f"{counts.get(OUTCOME_NO_MATCH, 0)} match no payment."
                ),
                "detail": (
                    f"{counts.get(OUTCOME_ALREADY_REVERSED, 0)} reversed when recorded. "
                    "An administrator reverses the rest."
                ),
            },
        ),
        Block(
            block="kpis",
            payload={
                "tiles": [
                    {
                        "id": "items",
                        "label": "Came back",
                        "value": {"kind": "text", "text": str(len(items))},
                    },
                    {
                        "id": "value",
                        "label": "Returned value",
                        "value": {
                            "kind": "money",
                            "amount": _stored(value),
                            "currency": currency,
                        },
                    },
                    {
                        "id": "unmatched",
                        "label": "Match no payment",
                        "value": {
                            "kind": "text",
                            "text": str(len(match.get("unmatched", ()))),
                        },
                        "detail": "Somebody has to place these",
                    },
                    {
                        "id": "privilege",
                        "label": "Privilege to remove",
                        "value": {
                            "kind": "text",
                            "text": str(privilege.get("at_the_limit", 0)),
                        },
                        "detail": privilege.get("reason", ""),
                    },
                ]
            },
        ),
        Block(
            block="breakdown",
            payload={
                "heading": "By reason",
                "columns": [
                    {"key": "reason", "label": "Bank said"},
                    {"key": "items", "label": "Items"},
                    {"key": "value", "label": "Value"},
                ],
                "rows": _by_reason(items, currency),
            },
        ),
        Block(
            block="records",
            payload={
                "columns": _records_columns(),
                "rows": [_record_row(record, items, currency) for record in view.records],
                "total": len(view.records),
                "empty": {
                    "title": "Nothing came back.",
                    "helper": "No payment was returned in this window.",
                },
            },
        ),
        Block(
            block="downloads",
            payload={
                "files": [
                    {"name": "To reverse", "outcome": OUTCOME_TO_REVERSE},
                    {"name": "Match no payment", "outcome": OUTCOME_NO_MATCH},
                ],
                "stated_absences": _absences(prior, privilege),
            },
        ),
    ]


def _records_columns() -> list[dict[str, str]]:
    return [
        {"key": "item", "label": "Item"},
        {"key": "account", "label": "Account"},
        {"key": "amount", "label": "Amount"},
        {"key": "bank_said", "label": "Bank said"},
        {"key": "outcome", "label": "Outcome"},
        {"key": "fix", "label": "Fix"},
    ]


def _chain(view, stop: dict[str, Any]) -> Block:
    """The six steps, one red and the rest **Never reached** (`BR-RBS-027`).

    Drawn only on a stopped run, and it is what makes the stop READ as a designed
    answer: a clerk sees which step could not run and that the five after it never
    started, rather than five blank cells that look like five clean checks.
    """
    cells = []
    for position, step in enumerate(RUNBOOK.steps, start=1):
        first = position == 1
        cells.append(
            {
                "id": step.key,
                "position": position,
                "label": step.label,
                "state": "bad" if first else "notReached",
                "note": stop["headline"] if first else "Never reached",
            }
        )
    return Block(block="chain", payload={"label": "Steps", "cells": cells})


def _by_reason(items: dict[str, Any], currency: str) -> list[dict[str, Any]]:
    """`RB-126`'s by-reason table — **the bank's words, never the return code.**

    B14 rule 32 keeps a code out of what a clerk reads, and the whole value of
    this table is that *Insufficient funds* and *Account closed* need different
    conversations with the customer.
    """
    tally: dict[str, dict[str, Any]] = {}
    for row in items.values():
        word = str(row.get("bank_said") or "Not stated")
        entry = tally.setdefault(word, {"items": 0, "value": Decimal("0")})
        entry["items"] += 1
        entry["value"] += _money(row.get("amount"), Decimal("0")) or Decimal("0")
    return [
        {
            "id": word,
            "cells": {
                "reason": {"kind": "text", "text": word},
                "items": {"kind": "text", "text": str(entry["items"])},
                "value": {
                    "kind": "money",
                    "amount": _stored(entry["value"]),
                    "currency": currency,
                },
            },
        }
        for word, entry in sorted(tally.items())
    ]


def _record_row(record, items: dict[str, Any], currency: str) -> dict[str, Any]:
    """One `{id, cells}` row. `decided_by_rule` travels in `meta` (B14 rule 32)."""
    row = items.get(str(record.subject.subject_id), {})
    return {
        "id": f"{record.subject.subject_id}:{record.step_key}",
        "cells": {
            "item": {"kind": "text", "text": record.subject.label},
            # The account NUMBER, never the id (B14 rule 31).
            "account": {"kind": "text", "text": str(row.get("account_no") or "")},
            "amount": {
                "kind": "money",
                "amount": str(row.get("amount") or "0.0000"),
                "currency": row.get("currency") or currency,
            },
            "bank_said": {"kind": "text", "text": str(row.get("bank_said") or "")},
            "outcome": {"kind": "text", "text": _outcome_word(record.outcome)},
            "fix": (
                {"kind": "link", "label": "Open payment", "to": record.fix_route}
                if record.fix_route
                else {"kind": "text", "text": ""}
            ),
        },
        "meta": {"decided_by_rule": record.decided_by_rule, "why": record.reason},
    }


def _outcome_word(outcome: str) -> str:
    """The outcome as a word for a table cell. No rule id (B14 rule 32)."""
    return {
        OUTCOME_TO_REVERSE: "To reverse",
        OUTCOME_NO_MATCH: "Matches no payment",
        OUTCOME_ALREADY_REVERSED: "Already reversed",
        OUTCOME_PRIVILEGE_REMOVED: "Privilege removed",
        acts.OUTCOME_PLANNED: "Planned",
        OUTCOME_SKIPPED: "Not looked at",
    }.get(outcome, outcome.replace("_", " "))


def _absences(prior: dict[str, Any], privilege: dict[str, Any]) -> list[str]:
    """What this run could NOT do, each with its figure (hard-won law 7)."""
    out = [
        "this run cannot reverse a payment. A return is reversed when it is recorded, by "
        "US Payments or on the payment, and an administrator reverses any other.",
    ]
    if privilege.get("refused"):
        out.append(
            "an account's payment privilege could not be removed automatically: "
            + str(privilege["refused"])
        )
    if not prior.get("settings_readable", True):
        out.append(
            "this utility has not set how many returned payments cost an account its "
            "payment privilege, so none was removed."
        )
    return out


# ── small helpers ─────────────────────────────────────────────────────────


def _record_data(row: dict[str, Any], **extra) -> dict[str, Any]:
    data = {
        "amount": row.get("amount"),
        "bank_said": row.get("bank_said"),
        "payment_id": row.get("payment_id"),
        "account_no": row.get("account_no"),
    }
    data.update(extra)
    return data


def _currency_of(items: dict[str, Any]) -> str:
    """The tenant's ONE currency (`BR-TEN-042`), off the items' own rows."""
    for row in items.values():
        if row.get("currency"):
            return str(row["currency"])
    return "USD"


def _channels(ctx: Any) -> tuple[str, ...]:
    """`RB-126`'s *Channel: Email, then post*, as a parameter."""
    raw = str(ctx.params.get("channels") or "email_then_post")
    return ("email", "pdf_print") if raw == "email_then_post" else (raw,)


def _outcome(engine_outcome: str, done_word: str) -> str:
    """The engine's word, in this runbook's vocabulary. `planned` STAYS `planned`."""
    return {
        acts.OUTCOME_DONE: done_word,
        acts.OUTCOME_ALREADY: OUTCOME_ALREADY_REVERSED,
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

    ⚠ **A STORED FOUR-PLACE VALUE MUST NEVER REACH CLERK COPY** —
    *"182.400000 more than this account owes"* is a real defect another lane
    fixed this week, and a sentence is exactly where it escapes.
    """
    return f"${value.quantize(Decimal('0.01')):f}"


RUNBOOK = RunbookDefinition(
    key=RUNBOOK_KEY,
    name="Returned payments",
    kind=models.KIND_ACTION,
    category="payments",
    subject_type="payment",
    unit_of_work="returned item",
    # ⚠ MANUAL AND SCHEDULE ONLY. `RB-126`'s *Runs: When returns land · rolled up
    # 07:00* names an EVENT trigger, and the three event names are BLOCKED-BY the
    # integrations substrate (`CR-069`) — `batch.landed` is emitted by nothing.
    # A runbook whose only trigger is an event is not runnable at all, so
    # declaring one here would put a **Run ▶** on a screen that must refuse.
    triggers=(models.TRIGGER_SCHEDULE, models.TRIGGER_MANUAL),
    tags=("Payments", "notices"),
    parameters=(
        Parameter(name="as_of", type=PARAM_TEXT, label="Business day", required=True),
        Parameter(
            name="window_days",
            type=PARAM_INTEGER,
            label="Returns landed within (days)",
            required=True,
            default=1,
        ),
        Parameter(
            name="returned_payment_charge_code",
            type=PARAM_TEXT,
            label="Returned-payment charge code",
            # ⚠ NO DEFAULT, ON PURPOSE. `BR-BIL-007`: the fee is the tenant's own
            # charge code, never typed. A runbook may carry out a code a utility
            # named; it may not decide that a customer owes a fee.
            default=None,
        ),
        Parameter(
            name="fee_due_days",
            type=PARAM_INTEGER,
            label="Fee terms (days)",
            default=0,
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
            name="most_per_run",
            type=PARAM_INTEGER,
            label="Most per run",
            required=True,
            default=100,
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
            key="already_reversed",
            label="Never include: Already reversed",
            applies=guard_already_reversed,
        ),
    ),
    resolve=resolve,
    report=report,
    steps=(
        Step(key=STEP_GATHER, label=STEP_LABELS[STEP_GATHER], mode=MODE_SET, run=step_gather),
        Step(key=STEP_MATCH, label=STEP_LABELS[STEP_MATCH], mode=MODE_SET, run=step_match),
        Step(
            key=STEP_PRIOR,
            label=STEP_LABELS[STEP_PRIOR],
            mode=MODE_SET,
            run=step_prior_returns,
        ),
        Step(
            key=STEP_REVERSE,
            label=STEP_LABELS[STEP_REVERSE],
            mode=MODE_PER_RECORD,
            run=step_reverse,
            # ⚠ TRUE THOUGH IT WRITES NOTHING — see `step_reverse`'s docstring.
            writes=True,
        ),
        Step(
            key=STEP_FEE,
            label=STEP_LABELS[STEP_FEE],
            mode=MODE_PER_RECORD,
            run=step_fee_and_notice,
            writes=True,
        ),
        Step(
            key=STEP_PRIVILEGE,
            label=STEP_LABELS[STEP_PRIVILEGE],
            mode=MODE_SET,
            run=step_privilege,
            writes=True,
        ),
    ),
    ports=("apply_fee", "queue_notice", "flag_account"),
)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-036 (EP-RBS-05; CR-075 wave R′, the payments half)
# generated: 2026-09-07 by the CR-075 wave R′ payments build lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint — the run/approve/stop routes are wave D's) E=n/a(no screen — phase 5 declares NO frontend code, and RB-126's result screen is RESERVED and not drawn; the report is composed from the twelve blocks and invents none) F✔ G✔ H=n/a(no 🔒 path: the idempotency KEY is composed in engine/acts.py and the reversal's arithmetic is payments')
# gates: pytest tests/test_us_rbs_036_returned_payments.py · pytest tests/test_us_rbs_015_conformance.py · G115 · G6 (no clock read — as_of is a parameter)
# amended: 2026-10-07 CR-175-BRC10 / DEF-PAY-10010 — the read now returns every reversing row carrying a bank return code (US Payments' returns and a clerk's ACH Mark returned alike); step 4 reports them Already reversed and step 5 drafts the fee and handles the notice. The exception below is the pre-2026-10-07 record.
# exceptions: **IT STOPPED AT STEP 1 ON EVERY DEPLOYMENT UNTIL 2026-10-07** — no returns feed, no bank-return-code column, and no port that reverses a payment (`OQ-RBS-1741`, OPEN; the stop is a valid state by PO ruling 2026-09-06) · DISABLED FOR LIVE besides — no runbook is on engine.acts.LIVE_ENABLED_RUNBOOKS · the reversal is PLANNED and an Admin performs it (BR-PAY-1070) · `flag_account` binds no writer and its refusal is recorded (DEF-RBS-4331) · the privilege count is read from the reversing ROWS, not from `accounts.nsf_count`, which nothing increments (DEF-069) · the event trigger the card names is NOT declared: `batch.landed` is emitted by nothing (CR-069)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
