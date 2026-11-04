# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-010 · US-RBS-012 · US-RBS-014 (EP-RBS-04) — CR-075 wave L
#           task L6: runbook 8, registered as an Action with its ports declared
#           and DISABLED for live; guards evaluated BEFORE step 1.
# Rules:    BR-RBS-012 (guards are ABSOLUTE, before any step) · BR-RBS-014 (a
#           SAMPLE record is never acted on by an Action, in any tenant, at any
#           time) · BR-RBS-004 (a plan first, always) · BR-RBS-003 (dry and
#           live are one path) · BR-RBS-010 (every record names the rule that
#           decided it, in words) · BR-RBS-035 (a count for the outcomes with
#           no row) · BR-PAY-017 (the collection sequence — payments' law, read
#           and never copied) · BR-NOT-005 (a notice is WRITTEN; the dispatcher
#           sends) · OQ-RBS-1737 CLOSED (the run-level duplicate check)
# Tests:    06-backend/tests/test_us_rbs_010_dunning.py
# Impacts:  apps/runbooks/definitions/__init__.py (the one registration line) ·
#           apps/runbooks/seams/payments_seam.py · customers_seam.py ·
#           metering_seam.py (the reads added with it)
# ───────────────────────────────────────────────────────
"""Runbook 8 — **Collections ladder**. The first Action, and it cannot send.

On a card this is *Dunning and notices*; **on screen a clerk sees "Collections
ladder"**, which is the display name in the templates library and on every
wireframe (`RB-108`), and it is therefore the `name` below.

WHAT IT DOES, IN ONE SENTENCE
------------------------------
It walks accounts past due, works out which rung of the utility's own ladder
each is owed, and **queues** the notice — after a plan and a batch approval.
The word on every result is **Queued**, never *Sent*: nothing leaves the
building until a delivery provider is connected (`RBR-07`, PO ruling 17 August
2026), and in `CR-075` wave L no runbook is on
`engine.acts.LIVE_ENABLED_RUNBOOKS` at all, so even the queue write is not
reached — the run records what it WOULD do, on the same code path (`BR-RBS-003`).

⚠ **THE LADDER'S LAW IS PAYMENTS' AND NOT ONE LINE OF IT IS COPIED HERE.**
`BR-PAY-017` (CONFIRMED) is the sequence — due+3 reminder → late fee → 10-day →
5-day → 48-hour certified final — and `apps/payments/ladder.py::decide` is where
it is decided, PURE, with every figure arriving as an argument. The $25.00
balance floor (`OQ-137`/`OQ-157`), the plan pause (`BR-CUS-043`), the
partial-payment pause, the medical exclusion and hard rule 6's same-day guard
are all that function's. This module ASKS, through
`payments_seam.collections_ladder_board`, and renders the answer. A runbook that
re-derived any of it would be a second copy of a signed rule living where
payments' reviewers never look.

⚠ THE THIRTY-DAY PROBLEM, AND WHY THE RUNGS ARE THE ANSWER
------------------------------------------------------------
`OQ-RBS-1737` was closed on 2026-09-06 by the Product Owner moving the duplicate
check from the RECORD to the RUN. `engine/duplicates.py` implements that and
**names one case it does not cover**: a customer past due for thirty days under
a ladder that runs daily. The run-level check stops a 09:00 retry of the 07:00
run; the 24-hour bound stops a second run the same day; **neither stops thirty
letters on thirty consecutive days.** That case is this file's.

**It is answered by the RUNG being the per-record key's discriminator.** The
key `engine/acts.py` composes is
`runbook · action kind · subject type · subject id · discriminator`, and the
discriminator here is the rung. Worked, on account 4021 with a bill due 1
September and a daily ladder:

    day  4 · rung `friendly` due       → key ...|friendly       → **letter 1**
    day  5–13 · rung `friendly` sent   → payments' own board returns
                                          `runs=False, next_step_not_due`      → nothing
    day 14 · rung `first_10_day` due   → key ...|first_10_day   → **letter 2**
    day 15–23 · not due                                                        → nothing
    day 24 · rung `second_5_day` due   → key ...|second_5_day   → **letter 3**
    day 26 · rung `final_48_hour` due  → key ...|final_48_hour  → **letter 4**
    day 27–45 · ladder complete        → `ladder_complete`                     → nothing

**Four letters over forty-five days, not thirty over thirty** — and the second
protection is independent of the first: even with `account_collection_state`
somehow stale, the UNIQUE index refuses a second `friendly` letter to account
4021 for ever, because the key does not carry the run. Both halves are needed:
payments' board decides WHEN a rung falls due, and the key makes the write
happen ONCE per rung whatever the board says twice.

⚠ **THIS IS NOT PUT BACK TO THE PRODUCT OWNER** (hard-won law 13). It is ours to
design and to show them with a worked figure, and the figure is the table above.

WHAT THIS FILE DIVERGES FROM `RB-108` ON, AND WHY — RECORDED, NOT APPLIED SILENTLY
-----------------------------------------------------------------------------------
**1 · THE CARD SAYS *Steps 6 · four read, two write* AND THIS DECLARES FOUR.**
The two write steps are identical; the read half is grouped differently and the
reason is the plan's own instruction. `L6` says *"guards evaluated BEFORE step
1"*, which removes the card's step 2 (*Remove protected accounts*) from the step
list entirely — a guard is not a step, it is absolute and runs before any
(`BR-RBS-012`). The card's step 1 (*Find accounts past due*) is `resolve()`,
which is ONE function and also answers *"Matches 1,004 accounts today"* on the
setup screen. And the card's step 6 (*Record what was sent*) is an ENGINE act,
not a runbook's: `BR-RBS-022` puts the audit row in `engine/acts.py`, which is
the only thing that lets a Check leave a trail while holding no writer. So:

    card 1  Find accounts past due     → `resolve()`
    card 2  Remove protected accounts  → `guards`, before any step (L6)
    card 3  Work out the tier due      → step `tier_due`   (set · read)
    card 4  Check the address works    → step `deliverable` (set · read)
    card 5  Queue the notice           → step `queue_notice` (per record · writes)
    card 6  Record what was sent       → the ENGINE's audit row (BR-RBS-022)
                                       + step `late_fee`   (set · writes)

**2 · THE TWO READ STEPS ARE `set` AND NOT `per_record`, AND THAT IS A
MEASUREMENT RATHER THAN A PREFERENCE.** The ladder board is ONE read for the
whole pinned set; written per record it would be 1,004 reads for 1,004 accounts,
and `TC-RBS-17` exists because registering a set step as per-record is a real
mistake with a real cost. `12-the-contract.md` §3 draws exactly this shape for
runbooks 11 and 21 — compute over the set, then walk it — and it is why the mode
is per step rather than per runbook.

**3 · `apply_fee` IS HELD AND FIRES ONLY WHEN A TENANT NAMES THE CHARGE CODE.**
`RB-108`'s own run shows **Fees charged: $0.00**, and that is not an accident of
the fixture: `BR-PAY-017`'s late-fee step is **billing's** (`BR-BIL-001`/`008`),
and `apps/payments/ladder.py` says so in its own words — *"This engine CITES the
step and applies nothing: payments never writes a charge line."* This runbook
holds the port because the card says it does, and it applies a fee only when
`late_fee_charge_code` is set, which it is not by default. **A runbook must not
decide that a customer owes a fee**; it can only carry out a charge code a
utility has already named. `BR-RBS-018`'s second approval sits on top of that,
and `OQ-RBS-1732` closed on 2026-09-06 with **every** money-bearing action
carrying it and no threshold.

⚠ WHAT WOULD MAKE THIS RUNBOOK DO THE WRONG THING QUIETLY (hard-won law 7)
---------------------------------------------------------------------------
* **A guard that fails open.** A medical read that errored and was caught would
  chase a customer on a certificate. → No guard here catches anything: an
  ImportError or a database error propagates and the run fails loudly, because
  a collections run that half-ran its guards is worse than one that did not run.
* **Walking accounts the board could not decide.** `ladder_board` returns
  `next_step_available: false` when this deployment has no thresholds set, and a
  build that read `next_rung: None` as *"no notice due"* would report a clean
  run over a utility whose ladder is simply unconfigured. → That case is its own
  outcome word, `not_configured`, counted and named on the result.
* **Counting guarded accounts twice.** They have no record row at all — no step
  sees them — so they would vanish from every total if the counts came from the
  rows (`BR-RBS-035`). → The engine's `_count` adds them; this file's report
  reads that, not `len(records)`.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from apps.runbooks import models
from apps.runbooks.contract import (
    DOMAIN_SERVICE,
    MODE_PER_RECORD,
    MODE_SET,
    PARAM_ALL,
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
from apps.runbooks.seams import customers_seam, metering_seam, payments_seam

RUNBOOK_KEY = "collections_ladder"

STEP_TIER = "tier_due"
STEP_DELIVERABLE = "deliverable"
STEP_QUEUE = "queue_notice"
STEP_FEE = "late_fee"

STEP_LABELS = {
    STEP_TIER: "Work out the tier due",
    STEP_DELIVERABLE: "Check the address works",
    STEP_QUEUE: "Queue the notice",
    STEP_FEE: "Apply the late fee",
}

#: The outcome words this runbook uses. They are the ENGINE's where the engine
#: has one (`queued` is `acts.OUTCOME_DONE` renamed nowhere — see `_outcome`),
#: and its own where no rule decided. Every one of them is a word a clerk reads.
OUTCOME_QUEUED = "queued"
OUTCOME_ALREADY_SENT = "already_sent"
OUTCOME_SKIPPED = "skipped"
OUTCOME_UNDELIVERABLE = "undeliverable"
OUTCOME_NOT_CONFIGURED = "not_configured"
OUTCOME_FAILED = "failed"
OUTCOME_HELD = "held"

#: `payments`' own skip reasons, translated into the sentence a clerk reads.
#: ⚠ **THE TRANSLATION IS HERE AND THE DECISION IS NOT.** Every one of these
#: words is decided by `apps/payments/ladder.py::decide`; this map only says it
#: in English, with no rule id in it (B14 rule 32). A reason not on this map is
#: rendered as payments' own word rather than as a blank, because a skip a clerk
#: cannot read is the one thing a collections trail may not contain.
SKIP_SENTENCES = {
    "below_ladder_floor": "the balance is under this utility's collection floor",
    "medical_hold": "this account is on a medical hold",
    "payment_plan_pause": "there is a payment plan in good standing",
    "partial_payment_pause": "a part payment has paused the ladder",
    "nothing_overdue": "this account owes nothing",
    "next_step_not_due": "the next step is not due yet",
    "ladder_complete": "every step of the ladder has already been taken",
    # ⚠ THE LAST THREE ARE PAYMENTS' REFUSALS AT THE PORT, not the board's.
    # `step_ladder` can refuse a step the board approved minutes earlier — a
    # plan taken out since the plan was drawn, a tier a clerk sent by hand from
    # `S35` — and a refusal with no sentence would reach a clerk as the raw
    # code (`BR-RBS-010`: every record names the rule that decided it, in
    # words).
    "tier_already_sent": "somebody already sent this notice to this account",
    "collections_paused_by_active_plan": "there is a payment plan in good standing",
    "medical_hold": "this account is on a medical hold",
}


# ── guards — ABSOLUTE, and evaluated before step 1 (BR-RBS-012, L6) ───────


def _memo(ctx: Any, key: str, build) -> Any:
    """One lazily-built answer per run, so a guard is not asked twice.

    Guards are evaluated per subject and there are three of them; without this,
    a run over 1,004 accounts would read the sample set three thousand times.
    `ctx.set_results` is per run and is the executor's own scratch space.
    """
    cached = ctx.set_results.get(key)
    if cached is None:
        cached = build()
        ctx.set_results[key] = cached
    return cached


def _as_of(ctx: Any) -> dt.date:
    """The business day this run is taken for. **An argument, never a clock.**

    `BR-TEN-043` and gate `G6`. A run re-taken for last Tuesday must take last
    Tuesday's answer — payments' `decide` says the same thing about its own
    `as_of` and compares `>=` rather than `==` for exactly this reason.
    """
    given = ctx.params.get("as_of")
    if isinstance(given, dt.date):
        return given
    if isinstance(given, str) and given:
        return dt.date.fromisoformat(given)
    raise ValueError(
        "runbook 8 needs the business day it is being run for. It is a parameter and never a "
        "clock read (BR-TEN-043): a ladder re-taken for last Tuesday must take last Tuesday's "
        "decision, and a wall clock makes that impossible to express or to test."
    )


def guard_sample(ctx: Any, subject: SubjectRef) -> bool:
    """`BR-RBS-014` — **a sample record is never acted on, in any tenant, ever.**

    An absolute skip, evaluated before any step, and it cannot be switched off.
    A demo account that received a real disconnection notice would be the single
    most embarrassing failure this product has, and it is the one guard that has
    no legitimate exception anywhere.
    """
    return str(subject.subject_id) in _memo(
        ctx, "_sample_ids", customers_seam.sample_account_ids
    )


def guard_medical(ctx: Any, subject: SubjectRef) -> bool:
    """A15 via `BR-CUS-039` — an account on a medical certificate is excluded.

    ⚠ **THIS IS A GUARD AND NOT A SKIP REASON, AND THE DIFFERENCE MATTERS.**
    `apps/payments/ladder.py` also refuses a medical hold, as one of
    `BR-PAY-017`'s five stop conditions — but it only refuses it if it is TOLD,
    because payments publishes no medical-hold selector and *a clinical fact does
    not belong in that module*. Held here as a guard, the exclusion happens
    before any step and survives any later rule; passed to payments as an
    argument, it also appears on the board. Two layers over the same fact, and
    the outer one is the one that cannot be reasoned away.
    """
    cache: dict[str, bool] = _memo(ctx, "_medical", dict)
    key = str(subject.subject_id)
    if key not in cache:
        cache[key] = customers_seam.medical_hold(subject.subject_id, as_of=_as_of(ctx))
    return cache[key]


def guard_dispute(ctx: Any, subject: SubjectRef) -> bool:
    """A disputed account is not chased while the dispute is open.

    The dispute is a fact about a UNIT (`BR-MET-133` clause 4) and this walks
    accounts, so it goes account → unit through the anchors `customers` already
    publishes. `BR-CUS-068`'s multi-unit account can carry several and **any**
    open hold guards the account — the reading `dispute_ageing.
    open_dispute_for_account` already takes.

    A master account names a premises and no unit at all (`BR-CUS-1010`), which
    is lawful; it simply has no unit to carry a dispute, so it is not guarded
    here.
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
    """Every account past due by more than the threshold, pinned ONCE.

    `BR-RBS-009`: an account that becomes past due mid-run is not in the review
    list and is not acted on. This is also the function that answers *"Matches
    1,004 accounts today"* on `RBS-004-R8`, which is why it is one function and
    not two — a count computed a second way is a count that can disagree with
    the run.

    The set is payments' outstanding positions, read through the ladder board.
    `past_due_more_than` filters on the BALANCE and is the runbook's own
    parameter; the $25.00 ladder FLOOR is a different thing entirely — it is
    payments' per-utility setting and it stops the ladder rather than the scope,
    so an account under it appears in the plan with its reason rather than
    vanishing from it (`J4` step 2: every send AND skip is recorded, because a
    silent exclusion is the one thing a collections trail may not contain).

    ⚠ **AND `services` IS THE SECOND FILTER, ADDED IN WAVE `T` (`BR-RBS-042`).**
    It narrows WHICH DEBTORS the ladder walks — *"the process runs identically
    at every utility and the OUTPUT is filtered by what was chosen"* — and its
    default is the word *all*, so a utility that has never touched it chases
    every service it currently sells, including one enabled this morning. See
    `_only_these_services`, and note that the value reaching here is already the
    expanded set: the word never gets this far.
    """
    board = _board(ctx)
    threshold = _money(ctx.params.get("past_due_more_than"), Decimal("5.0000"))
    rows = [
        row
        for row in board.get("rows", [])
        if Decimal(str(row.get("balance", "0"))) > threshold
    ]
    rows = _only_these_services(ctx, rows)
    subjects = []
    for row in rows:
        subjects.append(
            SubjectRef(
                subject_type="account",
                subject_id=str(row["account_id"]),
                # ⚠ THE ACCOUNT NUMBER, NEVER THE DATABASE ID (B14 rule 31).
                # `ladder_board` already answers four words when there is none.
                label=str(row.get("account_no") or ""),
            )
        )
    return subjects


def _only_these_services(ctx: Any, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep the accounts that take at least one of the chosen services.

    `BR-RBS-042`: *"the process runs identically at every utility and the OUTPUT
    is filtered by what was chosen"* — this is that filter, and it is the whole
    of what an input does to this runbook. The six steps below do not change by
    one line between a utility that chases everything and one that chases water
    only.

    ⚠ **THE VALUE ARRIVES ALREADY EXPANDED, WHICH IS WHY THERE IS NO `"all"`
    BRANCH HERE.** `services.run_parameters` turned the word into this tenant's
    CURRENT service codes one statement before the run started, so a utility
    that enabled Trash last week is chasing Trash debtors today with nothing
    reconfigured. A branch on the word in this file would be the expansion
    happening in two places, and the second one is where it goes stale.

    ⚠ **AN ACCOUNT WITH NO SERVICE AGREEMENT AT ALL IS KEPT.** It owes money and
    a runbook that dropped it would stop chasing a real debt on the strength of
    a missing row — a silent exclusion, and `J4` step 2 is explicit that every
    send AND skip is recorded because a collections trail may not contain one.
    An account whose services are all outside the choice IS excluded, which is
    the choice a person made.

    ⚠ **ONE READ FOR THE WHOLE SET.** `customers_seam.service_codes_for_account_ids`
    resolves the page in a constant number of queries; asking per account would
    put `DEF-2723`'s six statements per row back, one module along.
    """
    chosen = ctx.params.get("services")
    if not isinstance(chosen, (list, tuple)):
        # Nothing declared, or a value this runbook cannot read as a set: the
        # ladder chases everything it was already chasing. A filter that guessed
        # would drop debtors on the strength of a misread parameter.
        return rows
    wanted = {str(one) for one in chosen}
    account_ids = [str(row["account_id"]) for row in rows]
    by_account = customers_seam.service_codes_for_account_ids(account_ids)
    kept = []
    for row in rows:
        codes = by_account.get(str(row["account_id"])) or []
        if not codes or wanted.intersection(codes):
            kept.append(row)
    return kept


def _board(ctx: Any) -> dict[str, Any]:
    """The ladder board for this run's business day, read ONCE and memoised.

    `resolve()` needs it to pin the scope and `step_tier_due` needs it to decide
    each rung. Reading it twice would let the two disagree — an account could
    climb a rung between them — which is exactly what `BR-RBS-009`'s *"resolved
    ONCE and pinned"* exists to prevent.
    """
    return _memo(
        ctx,
        "_board",
        lambda: payments_seam.collections_ladder_board(as_of=_as_of(ctx)),
    )


# ── steps ─────────────────────────────────────────────────────────────────


def step_tier_due(ctx: Any, subjects) -> dict[str, Any]:
    """SET · read — which rung each account is owed, from payments' own engine.

    ONE read for the whole pinned set (see divergence 2 in the module
    docstring). Nothing is decided here: `ladder.decide` decided it, and this
    turns its answer into the two things the per-record pass needs — the rung,
    and the sentence a clerk reads if there is no rung.
    """
    board = _board(ctx)
    wanted = {str(subject.subject_id) for subject in subjects}
    decisions: dict[str, dict[str, Any]] = {}
    for row in board.get("rows", []):
        key = str(row["account_id"])
        if key not in wanted:
            continue
        decisions[key] = {
            "runs": row.get("runs"),
            "rung": row.get("next_rung"),
            "skip_reason": row.get("skip_reason"),
            "detail_code": row.get("detail_code"),
            "balance": row.get("balance"),
            "currency": row.get("currency"),
            "days_late": row.get("days_late"),
            "current_tier": row.get("current_tier"),
        }
    return {
        "decisions": decisions,
        # Stated as a VALUE rather than only in prose (hard-won law 1): when a
        # utility has not set its thresholds, the board can decide NOTHING and
        # every account comes back `not_configured` rather than "no notice due".
        "next_step_available": bool(board.get("next_step_available")),
        "rungs": list(board.get("rungs", ())),
        "problems": list(board.get("problems", ())),
    }


def step_deliverable(ctx: Any, subjects) -> dict[str, Any]:
    """SET · read — a dead channel is skipped, never sent to.

    ⚠⚠ **THIS ASKED WHETHER THE ACCOUNT EXISTS UNTIL 2026-09-07, WHICH IS A
    DIFFERENT QUESTION AND ALWAYS TRUE** (`DEF-RBS-4348`). Every subject came
    from `resolve()`, which walks payments' board, which walks accounts — so
    `bool(anchors.get(id))` was `True` for every account that could ever reach
    this step, the `undeliverable` outcome was **unreachable by any input**, and
    wave `M` planned a letter for each of **23 accounts flagged `bad_address`**.
    A check that cannot fail is worse than no check, because it is trusted
    (hard-won law 7): the run reported *812 deliverable* and a clerk had nothing
    to look at.
    It now reads `accounts.bad_address` — `customers`' own column, set by
    returned-mail handling under `BR-PAY-018` and never by an edit — so *the
    post came back from this address* actually stops the next letter.

    ⚠ **AND IT STILL CANNOT ASK MORE THAN THAT.** `suppress_channel` — the port
    that would let a runbook record *this address bounced on the 4th* — has no
    writer and no column to write to (`DEF-RBS-4331`), so the product holds no
    per-CHANNEL statement that delivery stopped working: `bad_address` is one
    flag over the whole account and nothing records an email that hard-bounced.
    **That absence is reported on the result rather than inferred away**,
    because a run that silently treated *"we have never heard otherwise"* as
    *"this address works"* would post letters into the void.

    ⚠ **AND THE FLAG IS ABOUT THE POST, NOT ABOUT THE CUSTOMER — `DEF-PAY-6380`
    (2026-09-24).** Until then a flagged account was unreachable on EVERY
    channel, email included, so a customer whose letter came back and whose
    email works was told nothing at all. `bad_address` says *the postal address
    failed* (`BR-PAY-018`, and `35f3cf079` made it the one flag a returned
    letter raises); an email on file is untouched by it. So a flagged account
    loses the POST channel only, keeps every other channel the run asked for
    that is actually ON FILE (`customers.contact_channels_for`, asked once for
    the flagged accounts), and is undeliverable only when nothing is left.
    """
    anchors: dict[str, Any] = _memo(
        ctx,
        "_anchors",
        lambda: {row["id"]: row for row in customers_seam.account_anchors()},
    )
    subjects = list(subjects)
    asked = _channels(ctx)
    # ONE read for the flagged accounts only — what else is ON FILE for them.
    flagged = [
        str(subject.subject_id)
        for subject in subjects
        if (anchors.get(str(subject.subject_id)) or {}).get("bad_address")
    ]
    on_file = customers_seam.contact_channels_for(flagged) if flagged else {}
    reachable: dict[str, bool] = {}
    channels: dict[str, list[str]] = {}
    for subject in subjects:
        key = str(subject.subject_id)
        anchor = anchors.get(key)
        # An account with no anchor row at all is not reachable either — that is
        # the old question, kept, because it is a real (if unreachable) case and
        # removing it would trade one blind spot for another.
        if not anchor:
            usable: tuple[str, ...] = ()
        elif anchor.get("bad_address"):
            usable = tuple(
                one for one in asked if one != POST_CHANNEL and _on_file(one, on_file.get(key))
            )
        else:
            usable = asked
        channels[key] = list(usable)
        reachable[key] = bool(usable)
    return {
        "reachable": reachable,
        # `DEF-PAY-6380` — WHICH channels each account can still be sent on, so
        # the queue step asks payments for exactly those and no others.
        "channels": channels,
        "undeliverable": sorted(key for key, ok in reachable.items() if not ok),
        "bounce_history_available": False,
        "stated_absence": (
            "this run can see whether the post has come back from an account's address; it "
            "cannot see whether one CHANNEL has stopped working, because nothing in the "
            "product records a bounce against a single contact yet."
        ),
    }


def step_queue_notice(ctx: Any, subject: SubjectRef) -> dict[str, Any]:
    """PER RECORD · **writes** — one notice, one account, one rung, once.

    Everything dangerous in this module meets here, and each of the four layers
    is doing a different job:

      1. **The guards already ran** and this subject is not guarded — absolute,
         before any step (`BR-RBS-012`).
      2. **Payments' board decided the rung** and whether it falls due today.
      3. **The run-level check** (`OQ-RBS-1737`, PO 2026-09-06) says whether an
         earlier run of this same job already did this — or is still waiting for
         somebody, which is a WARNING and not a skip.
      4. **The per-record key** carries the RUNG, so the same letter cannot go
         twice however many times the ladder runs. That is the thirty-day answer
         worked out in the module docstring.

    The engine performs the act: it writes the plan first (`BR-RBS-004`), calls
    the port only if a writer is bound (`BR-RBS-003` — none is, in wave L), and
    writes the audit row naming this runbook and its version (`BR-RBS-015`).
    """
    tier = ctx.set_results.get(STEP_TIER, {})
    channel = ctx.set_results.get(STEP_DELIVERABLE, {})
    key = str(subject.subject_id)
    decision = tier.get("decisions", {}).get(key, {})

    if not tier.get("next_step_available", False):
        return {
            "outcome": OUTCOME_NOT_CONFIGURED,
            "decided_by_rule": "This utility's collection ladder is not set up yet",
            "reason": (
                "nobody has set this utility's collection floor and intervals, so there is no "
                "way to work out what would be due."
            ),
            "fix_route": "Settings → Collections",
        }
    if not decision:
        return {
            "outcome": OUTCOME_SKIPPED,
            "decided_by_rule": "Not on the ladder board",
            "reason": "this account had no outstanding position when the run pinned its scope.",
        }
    if not decision.get("runs") or not decision.get("rung"):
        reason = str(decision.get("skip_reason") or "")
        return {
            "outcome": OUTCOME_SKIPPED,
            "decided_by_rule": "The collection ladder",
            "reason": SKIP_SENTENCES.get(reason, reason or "nothing is due on this account."),
            "data": {"skip_reason": reason, "days_late": decision.get("days_late")},
        }
    if not channel.get("reachable", {}).get(key, False):
        return {
            "outcome": OUTCOME_UNDELIVERABLE,
            "decided_by_rule": "A dead channel is skipped, never sent to",
            "reason": "there is no address to send this to.",
            "fix_route": "Add a contact",
        }
    # `DEF-PAY-6380` — the channels THIS account can still take (a returned
    # letter removes the post and nothing else). Falls back to the run's own
    # ask only when the step predates the per-account answer.
    send_on = tuple(channel.get("channels", {}).get(key) or _channels(ctx))

    rung = str(decision["rung"])
    verdict = _run_level(ctx)
    if verdict.is_duplicate:
        return {
            "outcome": OUTCOME_ALREADY_SENT,
            "decided_by_rule": "This job already ran and was approved",
            "reason": verdict.message,
        }

    result = acts.perform(
        ctx,
        acts.ActRequest(
            # ⚠ **`step_ladder`, NOT `queue_notice` — `DEF-RBS-4347`.** A
            # collections step is THREE writes and one act: the queue row, the
            # `notice_history` row and the `account_collection_state` tier. The
            # last two are payments' own tables under `BR-PAY-017`, and
            # `queue_notice` — which is `notifications`' port — writes neither.
            # Wave `M` measured what that costs: **512 state rows before a month
            # of runs and 512 after, and no notice history at either end**, so
            # every customer would have had the first reminder and then silence
            # for ever. The tier advance is PAYMENTS' act; the reasoning is in
            # the decision log of 2026-09-07 and the port is the fourteenth.
            port="step_ladder",
            action_kind="step_ladder",
            subject=subject,
            planned_action=f"Queue the {_rung_words(rung)}",
            # ⚠ THE RUNG IS THE DISCRIMINATOR. Read the module docstring before
            # changing this: drop it and a customer chased in September is never
            # chased again; put the RUN in it and the same 248 customers get two
            # letters in one morning.
            discriminator=rung,
            decided_by_rule="The collection ladder",
            reason=f"{decision.get('days_late')} days past due",
            amount=_money(decision.get("balance"), None),
            currency=decision.get("currency"),
            # ⚠ **THESE ARE `step_ladder`'s KEYWORD ARGUMENTS AND NOTHING
            # ELSE** — `acts.act` calls `port.call(**payload)`, so a key with no
            # parameter behind it is a `TypeError` caught as `held`, which reads
            # on screen as *the owning module refused* rather than as a build
            # error. `cut_date` is deliberately absent: the day service would be
            # cut is payments' own figure (`ladder.step_one` derives it exactly
            # as `run_ladder` does), and a runbook parameter for it would put a
            # date on a legal notice that this module invented.
            payload={
                "actor": acts.actor_for(ctx),
                "account_id": subject.subject_id,
                "rung": rung,
                "as_of": _as_of(ctx),
                "channels": send_on,
            },
        ),
    )
    # ⚠ **PAYMENTS MAY HAVE REFUSED ITS OWN STEP AND THAT IS NOT `done`.** An
    # active payment plan or a tier already sent comes back from the port as
    # `stepped: false` with a reason — a normal return, not an exception — and
    # reporting it as *Queued* would tell a clerk a letter went to a customer
    # who was deliberately left alone. The engine's word is still `done` because
    # the CALL succeeded; the runbook's word is the one on screen.
    outcome = _outcome(result.outcome)
    refusal = _payments_refusal(result)
    if refusal:
        outcome = OUTCOME_SKIPPED
    return {
        "outcome": outcome,
        "decided_by_rule": "The collection ladder",
        "reason": (
            SKIP_SENTENCES.get(refusal, refusal.replace("_", " "))
            if refusal
            else f"{_rung_words(rung)} · {decision.get('days_late')} days past due"
        ),
        "data": {
            "rung": rung,
            "idempotency_key": result.idempotency_key,
            **({"skip_reason": refusal} if refusal else {}),
        },
    }


def _payments_refusal(result: Any) -> str:
    """Payments' own skip reason for this step, or `""`.

    The port's answer is stamped onto the record row by `acts._seal` under
    `result`, so it is read from the row rather than returned — which is the one
    awkward edge of `perform()` doing plan-and-act in one call. Reading it here
    keeps the awkwardness in one function instead of in the step.
    """
    if result.outcome != acts.OUTCOME_DONE or result.record_id is None:
        return ""
    row = models.RunbookRunRecord.objects.filter(pk=result.record_id).values_list(
        "data", flat=True
    ).first()
    answer = dict((row or {}).get("result") or {})
    if answer.get("stepped") is False:
        return str(answer.get("skip_reason") or "payments refused this step")
    return ""


def step_late_fee(ctx: Any, subjects) -> dict[str, Any]:
    """SET · **writes** — and it charges NOTHING unless a utility named the code.

    See divergence 3 in the module docstring. `RB-108`'s own run reads **Fees
    charged: $0.00**, and this is why: whether a late fee is owed is billing's
    (`BR-BIL-001`/`008`), and `apps/payments/ladder.py` says of the same step
    *"This engine CITES the step and applies nothing: payments never writes a
    charge line."* A runbook may carry out a charge code a utility has already
    named; it may not decide that a customer owes a fee.

    So this fires only when `late_fee_charge_code` is set — it is not, by
    default — and when it does, `apply_fee` DRAFTS the bill.
    `billing.fee_bill.issue_charge_fee` consumes the number and is bound to no
    port at all, so a person issues it. That is `BR-RBS-018`'s second approval
    written into the shape of the code, and `OQ-RBS-1732` (CLOSED 2026-09-06)
    is why there is no threshold beneath which it is skipped.
    """
    code = str(ctx.params.get("late_fee_charge_code") or "").strip()
    if not code:
        return {
            "applied": 0,
            "charge_code": None,
            "reason": "this utility has not named a late-fee charge code, so no fee is applied.",
        }
    due_days = int(ctx.params.get("late_fee_due_days") or 0)
    tier = ctx.set_results.get(STEP_TIER, {})
    applied: list[str] = []
    for subject in subjects:
        decision = tier.get("decisions", {}).get(str(subject.subject_id), {})
        if not decision.get("runs"):
            continue
        result = acts.perform(
            ctx,
            acts.ActRequest(
                port="apply_fee",
                action_kind="apply_fee",
                subject=subject,
                planned_action=f"Draft the {code} fee",
                # The rung again, for the same reason: one fee per rung, and a
                # second run of the ladder on the same day drafts nothing.
                discriminator=f"{decision.get('rung')}|{code}",
                decided_by_rule="This utility's late-fee charge code",
                payload={
                    "actor": acts.actor_for(ctx),
                    "account_id": subject.subject_id,
                    "charge_code": code,
                    "on_date": _as_of(ctx),
                    "due_days": due_days,
                },
            ),
        )
        if result.outcome in (acts.OUTCOME_DONE, acts.OUTCOME_PLANNED):
            applied.append(str(subject.subject_id))
    return {"applied": len(applied), "charge_code": code, "accounts": applied}


# ── the run-level duplicate check (OQ-RBS-1737, CLOSED 2026-09-06) ────────


def _run_level(ctx: Any):
    """Ask ONCE per run whether this job already ran, and carry the answer.

    Asked once rather than per record because it is a fact about the RUN — that
    is the whole shape of the Product Owner's ruling. `frequency_hours` is the
    parameter their *"keep 24 hours time limit on the same job or we can
    parameteise the frequency of the runs"* asks for, read as ONE control with
    24 as its default (the reading is recorded as ours in the decision log of
    2026-09-06, not attributed to them).
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
    """KPIs · Breakdown · Records · Downloads — the four blocks `RB-108` names.

    ⚠ **THE GUARDED ACCOUNTS ARE IN THE COUNTS AND HAVE NO ROWS** (`BR-RBS-035`).
    A guarded subject is never walked, so it has no record row and would vanish
    from every total if the tiles were drawn from `len(records)`. `view.counts`
    is the engine's own count and already includes them.
    """
    counts = dict(view.counts)
    tier = dict(view.set_results.get(STEP_TIER, {}))
    fee = dict(view.set_results.get(STEP_FEE, {}))
    channel = dict(view.set_results.get(STEP_DELIVERABLE, {}))
    queued = counts.get(OUTCOME_QUEUED, 0) + counts.get(acts.OUTCOME_PLANNED, 0)
    skipped = (
        counts.get(OUTCOME_SKIPPED, 0)
        + counts.get(OUTCOME_UNDELIVERABLE, 0)
        + counts.get(OUTCOME_ALREADY_SENT, 0)
    )
    blocks = [
        Block(
            block="kpis",
            payload={
                "tiles": [
                    {"label": "To send", "value": queued},
                    {"label": "Skipped", "value": skipped},
                    {"label": "Need a person", "value": counts.get(OUTCOME_FAILED, 0)},
                    {"label": "Not set up", "value": counts.get(OUTCOME_NOT_CONFIGURED, 0)},
                    # ⚠ A TILE EVEN WHEN ZERO. A clerk who approved a run wants
                    # to see this figure without hunting for it (`RB-108`).
                    {"label": "Fees drafted", "value": fee.get("applied", 0)},
                ],
                "nothing_was_sent": True,
            },
        ),
        Block(
            block="breakdown",
            # ⚠ **`heading` · `columns` · `rows`, WHICH IS WHAT THE RENDERER
            # READS — `DEF-RBS-4352`.** This block used to send
            # `{by, rows, rungs}`: `heading` and `columns` absent, and `by` and
            # `rungs` extra. `BreakdownBlock` reads `payload.columns` to build
            # its header row, so `RBS-006` threw and a clerk got an error
            # boundary instead of 835 planned notices. Every test on both sides
            # passed, because the backend checked the block's NAME and the
            # report crosses the wire as untyped JSON that never meets
            # `types.ts`. `contract.PAYLOAD_FIELDS` now refuses this at run
            # close, so the shape cannot drift again without naming itself.
            payload={
                "heading": "By rung",
                "columns": [
                    {"key": "rung", "label": "Rung"},
                    {"key": "planned", "label": "Planned"},
                    {"key": "queued", "label": "Queued"},
                    {"key": "failed", "label": "Failed"},
                ],
                "rows": _breakdown_rows(view),
            },
        ),
        Block(
            block="records",
            # ⚠ **`columns` · `rows` · `total` · `empty`, AND EVERY ROW IS
            # `{id, cells}` — `DEF-RBS-4352` again, in the same report.** The
            # rows used to be flat dicts, which `RecordsBlock` reads as rows
            # with no cells at all: the table drew a header and nothing under
            # it, on the runs where the screen got that far. `decided_by_rule`
            # travels in `meta`, where no block draws it — B14 rule 32 keeps a
            # rule id out of what a clerk reads, and the walkthrough asserts
            # that it never appears on screen.
            payload={
                "columns": [
                    {"key": "account", "label": "Account"},
                    {"key": "planned", "label": "Planned"},
                    {"key": "outcome", "label": "Outcome"},
                    {"key": "reason", "label": "Reason"},
                    {"key": "fix", "label": "Fix"},
                ],
                "rows": [
                    {
                        # The account NUMBER, never the id (B14 rule 31).
                        "id": str(record.subject.subject_id),
                        "cells": {
                            "account": {"kind": "text", "text": record.subject.label},
                            "planned": {"kind": "text", "text": record.step_key},
                            "outcome": {"kind": "text", "text": record.outcome},
                            "reason": {"kind": "text", "text": record.reason},
                            "fix": (
                                {"kind": "link", "label": "Open account", "to": record.fix_route}
                                if record.fix_route
                                else {"kind": "text", "text": ""}
                            ),
                        },
                        "meta": {"decided_by_rule": record.decided_by_rule},
                    }
                    for record in view.records
                ],
                "total": len(view.records),
                "empty": {
                    "headline": "Nobody is past due",
                    "body": "No account on this ladder owes anything today.",
                },
            },
        ),
        Block(
            block="downloads",
            payload={
                "files": [
                    {"name": "Queued", "outcome": OUTCOME_QUEUED},
                    {"name": "Not queued", "outcome": OUTCOME_SKIPPED},
                ],
                # Reported rather than inferred away — see `step_deliverable`.
                "stated_absences": [channel["stated_absence"]]
                if channel.get("stated_absence")
                else [],
            },
        ),
    ]
    return blocks


def _breakdown_rows(view) -> list[dict[str, Any]]:
    """`_by_rung`'s counts, as the `{id, cells}` rows a table draws.

    ⚠ Kept separate from `_by_rung` so the COUNTING stays testable on its own —
    the sum is the thing a person checks, and wrapping it in cell objects would
    make every assertion about it an assertion about markup.
    """
    return [
        {
            "id": row["rung"],
            "cells": {
                "rung": {"kind": "text", "text": row["rung"]},
                "planned": {"kind": "text", "text": str(row["planned"])},
                "queued": {"kind": "text", "text": str(row["queued"])},
                "failed": {"kind": "text", "text": str(row["failed"])},
            },
        }
        for row in _by_rung(view)
    ]


def _by_rung(view) -> list[dict[str, Any]]:
    """Planned · queued · failed side by side, per rung — `RB-108`'s own table.

    Three columns because the approval was of a PLAN and this is that plan
    reconciled against what happened — the same three-column honesty the cutover
    totals use.
    """
    rows: dict[str, dict[str, Any]] = {}
    for record in view.records:
        rung = str(dict(record.data or {}).get("rung") or "")
        if not rung:
            continue
        row = rows.setdefault(rung, {"rung": rung, "planned": 0, "queued": 0, "failed": 0})
        row["planned"] += 1
        if record.outcome in (OUTCOME_QUEUED, acts.OUTCOME_PLANNED):
            row["queued"] += 1
        elif record.outcome == OUTCOME_FAILED:
            row["failed"] += 1
    return [rows[key] for key in sorted(rows)]


# ── small helpers ─────────────────────────────────────────────────────────


#: The one channel a returned letter closes (`DEF-PAY-6380`).
POST_CHANNEL = "pdf_print"


def _channels(ctx: Any) -> tuple[str, ...]:
    """`RB-108`'s *Channels: Email, then post*, as a parameter."""
    raw = str(ctx.params.get("channels") or "email_then_post")
    return ("email", POST_CHANNEL) if raw == "email_then_post" else (raw,)


def _on_file(channel: str, entry: dict[str, Any] | None) -> bool:
    """Is there something ON FILE to send this channel to?

    `customers.contact_channels_for`'s own vocabulary: `email` and `text` are
    a contact's columns. *On file* is not *working* (that read says so), which
    is the same limit `stated_absence` reports for the whole step.
    """
    entry = entry or {}
    if channel == "email":
        return bool(entry.get("email"))
    if channel == "sms":
        return bool(entry.get("text"))
    return False


def _rung_words(rung: str) -> str:
    """Payments' rung word, in a clerk's language. No rule id (B14 rule 32)."""
    return {
        "friendly": "reminder",
        "first_10_day": "10-day notice",
        "second_5_day": "5-day notice",
        "final_48_hour": "final certified letter",
    }.get(rung, rung.replace("_", " "))


def _outcome(engine_outcome: str) -> str:
    """The engine's word, in this runbook's vocabulary.

    ⚠ **`planned` BECOMES `queued` NOWHERE.** A dry run says `planned` and a
    live one says `queued`, and collapsing them would make the dry cycle
    indistinguishable from the real one on the result screen — which is the
    single thing wave `M`'s month-long soak exists to look at.
    """
    return {
        acts.OUTCOME_DONE: OUTCOME_QUEUED,
        acts.OUTCOME_ALREADY: OUTCOME_ALREADY_SENT,
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


RUNBOOK = RunbookDefinition(
    key=RUNBOOK_KEY,
    # The screen name, not the card title — `RB-108`'s own first sentence.
    name="Collections ladder",
    kind=models.KIND_ACTION,
    category="collections",
    subject_type="account",
    unit_of_work="past due",
    triggers=(models.TRIGGER_SCHEDULE, models.TRIGGER_MANUAL),
    tags=("Payments", "notices"),
    parameters=(
        Parameter(
            name="as_of",
            type=PARAM_TEXT,
            label="Business day",
            required=True,
        ),
        Parameter(
            name="past_due_more_than",
            type=PARAM_MONEY,
            label="Past due more than",
            required=True,
            # ⚠ A STRING, NOT A FLOAT. `Parameter` refuses a float on a money
            # type and this value lives in jsonb, where nothing else would.
            default="5.0000",
        ),
        Parameter(
            name="most_per_run",
            type=PARAM_INTEGER,
            label="Most per run",
            required=True,
            default=400,
        ),
        Parameter(
            name="services",
            type=PARAM_ENUM,
            label="Services",
            required=True,
            # ⚠ **THE WORD, NEVER A LIST — `BR-RBS-042` CLAUSE 1.** A utility
            # that chases every service it sells stores `"all"` and gets its
            # CURRENT services on every run. Write `["water", "sewer"]` here at
            # setup and the day the utility enables Trash, every Trash-only
            # debtor is silently outside the ladder — no error, no screen
            # change, nothing on any screen to see. `services.run_parameters`
            # expands this when the run starts and `BR-RBS-009` pins it there.
            default=PARAM_ALL,
            multi=True,
            # Tenant-resolved (clause 2): a Water-and-Sewer utility is offered
            # two, not the platform's eleven.
            domain=DOMAIN_SERVICE,
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
            name="frequency_hours",
            type=PARAM_INTEGER,
            label="Treat runs within",
            required=True,
            # The Product Owner's own figure, as the DEFAULT of a parameter —
            # `OQ-RBS-1737`, and see `engine/duplicates.py` for the reading.
            default=24,
        ),
        Parameter(
            name="late_fee_charge_code",
            type=PARAM_TEXT,
            label="Late-fee charge code",
            # ⚠ NO DEFAULT, ON PURPOSE. Divergence 3: a runbook may carry out a
            # charge code a utility named; it may not decide a fee is owed.
            default=None,
        ),
        Parameter(
            name="late_fee_due_days",
            type=PARAM_INTEGER,
            label="Late-fee terms (days)",
            default=0,
        ),
    ),
    # ⚠ ABSOLUTE, AND EVALUATED BEFORE STEP 1 (`BR-RBS-012`, and task `L6` says
    # so in as many words). `RBS-004.4` draws each of these DISABLED with its
    # reason rather than hiding it, because a guard a clerk cannot see is a
    # guard they will assume is absent.
    guards=(
        Guard(key="sample", label="Never include: Sample", applies=guard_sample),
        Guard(key="medical", label="Never include: Medical", applies=guard_medical),
        Guard(key="dispute", label="Never include: Dispute", applies=guard_dispute),
    ),
    resolve=resolve,
    report=report,
    steps=(
        Step(key=STEP_TIER, label=STEP_LABELS[STEP_TIER], mode=MODE_SET, run=step_tier_due),
        Step(
            key=STEP_DELIVERABLE,
            label=STEP_LABELS[STEP_DELIVERABLE],
            mode=MODE_SET,
            run=step_deliverable,
        ),
        Step(
            key=STEP_QUEUE,
            label=STEP_LABELS[STEP_QUEUE],
            mode=MODE_PER_RECORD,
            run=step_queue_notice,
            writes=True,
        ),
        Step(
            key=STEP_FEE,
            label=STEP_LABELS[STEP_FEE],
            mode=MODE_SET,
            run=step_late_fee,
            writes=True,
        ),
    ),
    # ⚠ **`step_ladder`, NOT `queue_notice` — `DEF-RBS-4347`, 2026-09-07.**
    # `RB-108`'s port column and `12-the-contract.md` §8 row 8 both said
    # `queue_notice · apply_fee`; both are amended in the same commit as this
    # line. See `step_queue_notice` for why, and the decision log for the
    # ruling. A runbook that declares a port it does not hold cannot construct,
    # so this line and the `acts.ActRequest` above cannot drift apart.
    ports=("step_ladder", "apply_fee"),
)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-010 · US-RBS-012 · US-RBS-014 (EP-RBS-04; CR-075 wave L task L6)
# generated: 2026-09-06 by the CR-075 wave L build lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint — the run/approve/stop routes are wave D's and L3's, in a sibling's api.py) E=n/a(no screen — RBS-004-R8 and RBS-006-R8 are L7's and another lane's) F✔ G✔ H=n/a(no 🔒 path in this file: the idempotency KEY is composed in engine/acts.py and the ladder's math is payments')
# gates: pytest tests/test_us_rbs_010_dunning.py · pytest tests/test_us_rbs_015_conformance.py · G115 (the import census) · G6 (no clock read — as_of is a parameter)
# exceptions: DISABLED FOR LIVE — no runbook is on engine.acts.LIVE_ENABLED_RUNBOOKS, so this reaches writer-less ports in every mode and records what it WOULD do · four steps rather than the card's six (divergence 1) · apply_fee fires only when a tenant names the charge code (divergence 3) · a bounce history cannot be read and the result says so (step_deliverable)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
