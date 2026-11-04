# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-024 (EP-RBS-05) — CR-075 wave S: runbook 12, *Disconnect
#           eligibility* — eight read steps over the accounts at the last tier,
#           and the most expensive error a utility makes is the one it exists
#           to prevent.
# Rules:    BR-RBS-002 (a Check is CONSTRUCTED with no writer) · BR-RBS-011 (a
#           failure names its fix route, tenant-relative) · BR-RBS-012 (the
#           sample guard is absolute) · BR-RBS-019 · BR-RBS-020 · BR-RBS-021 ·
#           BR-RBS-023 · BR-RBS-032 (a returned letter is not a served notice;
#           the list re-checks delivery on the morning) · BR-RBS-039 ·
#           BR-CUS-100 (proof of service is a record a PERSON enters) ·
#           BR-CUS-039 (a protection freezes the ladder) · BR-CUS-082 (a closed
#           account cannot be escalated to disconnection) · BR-PAY-017 (the
#           48-hour certified final) · BR-TEN-043 (a business date is an
#           argument) · CLAUDE.md hard rule 2 · hard rule 8 (an address lives on
#           `premises`) · B14 rules 31, 32, 33
# Questions:OQ-RBS-1757 (the AREA-WIDE weather moratorium — the card's
#           temperature rule against this product's per-account date window)
# Tests:    06-backend/tests/test_us_rbs_024_disconnect_eligibility.py
# Impacts:  apps/runbooks/definitions/__init__.py · apps/customers/
#           runbook_reads.py · apps/runbooks/seams/customers_seam.py ·
#           apps/runbooks/seams/payments_seam.py ·
#           04-docs/05-modules/17-runbooks/11-catalogue/RB-112-disconnect-eligibility.md
# ───────────────────────────────────────────────────────
"""Runbook 12 — **Disconnect eligibility**.

*Who is actually eligible for disconnection today — and who must not be on the
list.* `RB-112`'s own sentence: **this is a Check; it produces a field list a
person signs. Nothing here disconnects anyone.**

⚠ **THE WHOLE RUNBOOK IS ONE IDEA: A LIST ASSEMBLED WHEN THE LETTERS WENT OUT IS
A LIST OF WHO WAS ELIGIBLE *THEN*.** `RB-112`'s design note — *"the most
expensive error a utility makes is a wrongful disconnect, and this runbook exists
to make it impossible by accident"* — is why every reason an account should not
be on the list is checked AGAIN on the morning, and why the removed rows are
drawn beside the eligible ones: the person signing wants to see who was taken
off, **because that is the list that would have been wrong.**

WHY THE REMOVED ROWS ARE RECORDS AND NOT GUARDS
------------------------------------------------
`RB-112`'s scope says *"Never include: Medical · Dispute · Plan in good standing
· Sample"*, and `BR-RBS-012` makes a guard ABSOLUTE — evaluated before any step,
the record skipped whatever the checks conclude. **Only `Sample` is built as a
guard here, and that is a deliberate reading of the card rather than a shortcut.**

The card's own result draws *Pace, J. · Removed · Medical protection added 3
Sep* as a ROW, its chip row counts *Removed 9*, and its verdict says *3
protected*. A guarded subject is skipped and counted and carries no reason —
so building medical, dispute and plan as guards would delete the nine rows this
runbook exists to show. They are therefore excluded by step 5 and DRAWN, which
is the same exclusion with the evidence attached. `Sample` stays a guard because
`BR-TEN-057`'s demo rows are not a household anybody would visit.

THE TWO LADDERS, AND WHY THE LIST IS BUILT FROM THE ONE WITH THE LETTER ON IT
------------------------------------------------------------------------------
This product holds two overlapping ladders — payments' `account_collection_state`
(reminder · 10-day · 5-day · certified final) and customers'
`disconnect_cases.tier` (TIER 1 · 2 · 3) — and `disconnects.py`'s own lifecycle
block records the overlap as UNRULED (`DEF-675`). Only one of them records a
**certified letter and its proof of service**, and `BR-CUS-100` makes exactly
that the thing which authorises a cut. So the scope is the tier-3 cases, and
step 1 reports how many of them payments' ladder ALSO shows at its final rung —
so `DEF-675`'s disagreement arrives as a number on the screen rather than as a
silence.

THREE THINGS THIS RUNBOOK CANNOT SEE, EACH WITH ITS NUMBER
------------------------------------------------------------
1. **WHETHER A LETTER WAS *DELIVERED*.** `delivered` and `bounced` are provider
   facts and no provider adapter exists on any channel, print included. What is
   readable is `BR-CUS-100`'s proof of service — a person's attestation with the
   channel, the reference and the date — and that is the STRONGER fact, because
   it is what a regulator asks to see. Step 2 counts what has it and what does
   not, and never reports a clean delivery.
2. **WHETHER AN AMOUNT IS IN DISPUTE.** Nothing in this product stores a
   disputed amount, so `protection_check`'s fourth row answers `unavailable`
   rather than `pass`, in its own words: *"a green clearance derived from a
   table that does not exist would authorise a cut."* Step 5 carries that
   verdict through and prints the count.
3. **WHETHER TODAY IS INSIDE AN AREA-WIDE WEATHER MORATORIUM.** `OQ-RBS-1757`,
   OPEN. The card's parameter is a TEMPERATURE rule — *below 32°F · above
   100°F* — and this product holds a per-ACCOUNT date window a person records
   (`weather_moratorium`, B18 §5.8.3). The per-account window IS checked and
   DOES remove; the area-wide half reports **Not checked**, never the card's
   green *No*, because *we looked at the weather and it is fine* and *nobody
   looked* send a crew to opposite places (hard-won law 7).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from apps.runbooks import models
from apps.runbooks.contract import (
    DOMAIN_SERVICE,
    MODE_PER_RECORD,
    MODE_SET,
    PARAM_ENUM,
    PARAM_MONEY,
    PARAM_REF_SETTING,
    PARAM_TEXT,
    PARAM_TOGGLE,
    Block,
    Guard,
    Parameter,
    RunbookDefinition,
    Step,
    SubjectRef,
)
from apps.runbooks.seams import (
    customers_seam,
    metering_seam,
    payments_seam,
    tenancy_seam,
)

KEY = "disconnect_eligibility"

ZERO = Decimal("0")

# ── the eight steps, in the card's own order ──────────────────────────────

STEP_GATHER = "gather_accounts_at_the_last_tier"
STEP_LETTER = "confirm_the_letter_was_sent_and_delivered"
STEP_NOTICE = "confirm_the_notice_period_has_passed"
STEP_PAYMENT = "check_for_a_payment_overnight"
STEP_PROTECTIONS = "check_protections_and_disputes_again"
#: The three temperature bands a clerk picks from before the run walks anybody.
#:
#: ⚠ **PO RULING 2026-09-07 (`OQ-RBS-1757`), verbatim:** *"when you run this
#: runbook, ask user to check temp range from ddropdown and use that details in
#: logic"*. The THRESHOLDS are `RB-112`'s own — below 32°F, above 100°F — and
#: what the ruling settles is only who supplies today's reading: the person
#: pressing Run, not a weather feed this product does not have.
WEATHER_BAND_BELOW_FREEZING = "below_32f"
WEATHER_BAND_MILD = "between_32f_and_100f"
WEATHER_BAND_ABOVE_100 = "above_100f"

WEATHER_BANDS: tuple[str, ...] = (
    WEATHER_BAND_BELOW_FREEZING,
    WEATHER_BAND_MILD,
    WEATHER_BAND_ABOVE_100,
)

#: The two bands that stop the run. Named as a set rather than tested inline, so
#: adding a fourth band is one edit and cannot leave a step reading the old two.
#: What the clerk's own answer reads as on the row. Their words back to them,
#: not a code — `DEF-RBS-4383` is what a raw refusal word costs when 720 rows
#: carry it.
_WEATHER_BAND_SENTENCE: dict[str, str] = {
    WEATHER_BAND_BELOW_FREEZING: "Reported below 32\u00b0F today.",
    WEATHER_BAND_ABOVE_100: "Reported above 100\u00b0F today.",
}

WEATHER_BANDS_THAT_HOLD: frozenset[str] = frozenset(
    {WEATHER_BAND_BELOW_FREEZING, WEATHER_BAND_ABOVE_100}
)

STEP_WEATHER = "check_the_weather_moratorium"
STEP_WORKING_DAY = "check_it_is_a_working_day"
STEP_FIELD_LIST = "build_the_field_list"

STEP_LABELS = {
    STEP_GATHER: "Gather accounts at the last tier",
    STEP_LETTER: "Confirm the letter was sent and delivered",
    STEP_NOTICE: "Confirm the notice period has passed",
    STEP_PAYMENT: "Check for a payment overnight",
    STEP_PROTECTIONS: "Check protections and disputes again",
    STEP_WEATHER: "Check the weather moratorium",
    STEP_WORKING_DAY: "Check it is a working day",
    STEP_FIELD_LIST: "Build the field list",
}

# ── the two outcomes, and the reasons one of them has ─────────────────────

OUTCOME_ELIGIBLE = "eligible"
OUTCOME_REMOVED = "removed"

#: Why an account came off the list. ⚠ **THE ORDER IS THE ORDER THEY ARE
#: TESTED IN, AND IT IS DELIBERATE:** a protection wins over a payment, a
#: payment wins over an unserved letter, and the balance floor is last — so the
#: sentence on the row is the reason a supervisor would give, not merely the
#: first one a loop happened to reach. Nothing here is ambiguous in the other
#: direction: every one of these removes.
WHY_NOT_SERVED = "letter_not_served"
WHY_NOTICE_NOT_PASSED = "notice_period_not_passed"
WHY_PROTECTED_MEDICAL = "medical_protection"
WHY_PROTECTED_MORATORIUM = "weather_moratorium"
WHY_PROTECTED_PLAN = "plan_in_good_standing"
WHY_PAID = "paid_since_the_letter"
WHY_UNDER_MINIMUM = "under_the_minimum_balance"
WHY_CUT_NOT_REACHABLE = "cut_not_reachable"
WHY_NOT_A_WORKING_DAY = "not_a_working_day"

WHY_LABELS = {
    WHY_NOT_SERVED: "Letter not served",
    WHY_NOTICE_NOT_PASSED: "Notice period has not passed",
    WHY_PROTECTED_MEDICAL: "Medical protection",
    WHY_PROTECTED_MORATORIUM: "Weather moratorium",
    WHY_PROTECTED_PLAN: "Plan in good standing",
    WHY_PAID: "Paid since the letter",
    WHY_UNDER_MINIMUM: "Under the minimum",
    WHY_CUT_NOT_REACHABLE: "No service to disconnect",
    WHY_NOT_A_WORKING_DAY: "Not a working day",
}

#: The three reasons the card's verdict band counts by name — *4 paid overnight
#: · 3 protected · 2 under minimum*.
PROTECTION_REASONS = (WHY_PROTECTED_MEDICAL, WHY_PROTECTED_MORATORIUM, WHY_PROTECTED_PLAN)

#: The fix beside each — `BR-RBS-011`, tenant-relative (the shell prefixes the
#: utility), and every route is one this product mounts: `/accounts` and
#: `/payments` are in `SIDEBAR_DESTINATIONS`, and `settings/collections` is a
#: settings rule page (`settingsRulePages.ts` slug `collections`). Verified
#: 2026-09-07. ⚠ **A ROUTE THAT OPENS ONTO *not built yet* IS `DEF-RBS-4329`
#: AGAIN**, which is why the proof-of-service fix points at the ACCOUNT rather
#: than at `S90`, the disconnect worklist screen that does not exist.
FIX_ACCOUNTS = "accounts"
FIX_PAYMENTS = "payments"
FIX_SETTINGS = "settings/collections"

FIX_FOR_WHY = {
    WHY_NOT_SERVED: (FIX_ACCOUNTS, "Record how it was served →"),
    WHY_NOTICE_NOT_PASSED: (FIX_ACCOUNTS, "Open the account →"),
    WHY_PROTECTED_MEDICAL: (FIX_ACCOUNTS, "Open the protection →"),
    WHY_PROTECTED_MORATORIUM: (FIX_ACCOUNTS, "Open the protection →"),
    WHY_PROTECTED_PLAN: (FIX_ACCOUNTS, "Open the plan →"),
    WHY_PAID: (FIX_PAYMENTS, "Open the payment →"),
    WHY_UNDER_MINIMUM: (FIX_SETTINGS, "Open the minimum →"),
    WHY_CUT_NOT_REACHABLE: (FIX_ACCOUNTS, "Open the account →"),
    WHY_NOT_A_WORKING_DAY: (FIX_SETTINGS, "Open the calendar →"),
}


@dataclass
class _StepResult:
    found: dict[str, Any] = field(default_factory=dict)
    checked: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"reached": True, "found": dict(self.found), "checked": dict(self.checked)}


def _decimal(raw: Any) -> Decimal | None:
    if raw in (None, ""):
        return None
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return None


def _stored(amount: Decimal) -> str:
    """The four-place string a report carries. Display rounds; storage does not."""
    return f"{amount.quantize(Decimal('0.0001')):f}"


def _date(raw: Any) -> dt.date | None:
    if not raw:
        return None
    if isinstance(raw, dt.date):
        return raw
    try:
        return dt.date.fromisoformat(str(raw)[:10])
    except (TypeError, ValueError):
        return None


def _board(ctx) -> dict[str, Any]:
    """The tier-3 cases, read ONCE per run in `resolve` and cached here."""
    return ctx.set_results.get("_board") or {"rows": [], "cases_at_this_tier": 0}


def _walked(ctx, subjects) -> list[dict[str, Any]]:
    """The board's rows for the subjects a GUARD did not take out.

    ⚠ **`BR-RBS-012`: A GUARD IS EVALUATED BEFORE ANY STEP AND A GUARDED RECORD
    IS SEEN BY NONE OF THEM — AND THIS FUNCTION EXISTS BECAUSE THE FIRST BUILD
    BROKE THAT AND NOTHING IN THE SUITE COULD SEE IT** (`DEF-RBS-4395`, found by
    running the thing on a real utility). Steps 2, 3 and 4 walked
    `_board()["rows"]` — every case at the last tier, guarded or not — while step
    5 onward walked the SUBJECTS the executor hands in. So on the seeded utility
    the run reported *"2 letters served, notice period passed on both"* over two
    SAMPLE accounts it had correctly refused to look at, and drew a table with
    nothing in it. Both halves were internally consistent, which is why every
    mocked test passed: the fixtures had no guarded row in them.

    Reading the subjects the executor hands each set step is the fix, and it is
    the only reading that cannot drift — the executor decides who was walked, so
    no step gets to decide it a second time.
    """
    wanted = {str(one.subject_id) for one in subjects}
    return [row for row in (_board(ctx).get("rows") or []) if str(row["account_id"]) in wanted]


def _rows(ctx) -> dict[str, dict[str, Any]]:
    return ctx.set_results.get("_rows") or {}


# ── step 1 · the ladder's end ─────────────────────────────────────────────


def step_gather_accounts_at_the_last_tier(ctx, subjects) -> dict[str, Any]:
    """1 · The ladder's end, and what each of these accounts owes.

    ⚠ **ONE READ FOR THE WHOLE LIST** (`NFR-3`). `collections_ladder_board` is
    narrowed to the pinned accounts, so `ladder.decide` runs once per subject
    rather than once per debtor in the utility — correct at 3,000 accounts and
    13× short at 40,000 is `DEF-PAY-4221`'s shape, and this list is small only
    because the ladder in front of it is doing its job.

    ⚠ **THE BALANCE IS PAYMENTS' AND IS NOT RE-DERIVED HERE.** A disconnect list
    that computed its own arrears would be a second answer to *what does this
    household owe*, on the one screen where being wrong costs a household its
    water.
    """
    board = _board(ctx)
    account_ids = [str(one.subject_id) for one in subjects]
    ladder: dict[str, Any] = {}
    problems: list[str] = []
    if account_ids:
        answer = payments_seam.collections_ladder_board(
            as_of=ctx.set_results.get("_as_of"),
            account_ids=account_ids,
            medical_hold_account_ids=(),
        )
        ladder = {str(row["account_id"]): row for row in (answer.get("rows") or [])}
        problems = [str(one.get("code") or "") for one in (answer.get("problems") or [])]
    ctx.set_results["_ladder"] = ladder

    unreadable = [one for one in account_ids if one not in ladder]
    at_final_rung = sum(
        1
        for row in ladder.values()
        if str(row.get("current_tier") or "") == _final_rung()
    )
    return _StepResult(
        found={"ladder": ladder},
        checked={
            "cases_at_the_last_tier": board.get("cases_at_this_tier", 0),
            # ⚠ **THE GUARDED ONES ARE COUNTED AND NOT LOOKED AT** (`BR-RBS-012`,
            # `DEF-RBS-4395`). A screen that showed the shorter list with no
            # number beside it could not tell a small morning from an excluded
            # one.
            "of_those_a_guard_took_out": board.get("cases_at_this_tier", 0) - len(subjects),
            "checked_after_the_guards": len(subjects),
            "tier": board.get("tier"),
            # ⚠ `DEF-675` AS A NUMBER RATHER THAN AS A SILENCE — the two ladders
            # overlap and the overlap is unruled, so the disagreement is
            # printed. On a utility whose collections ladder has never run this
            # is 0 beside a non-zero case count, which is the honest picture.
            "of_those_also_at_payments_final_rung": at_final_rung,
            "balances_that_could_not_be_read": len(unreadable),
            "ladder_problems": problems,
            # ⚠ **THE SERVICE PARAMETER NARROWS NOTHING TODAY, AND THAT IS
            # STATED RATHER THAN HIDDEN.** A disconnect case is per ACCOUNT;
            # `disconnect_cases.services_cut` is written when a cut is
            # SCHEDULED and is empty before then, so there is no service on a
            # case at the last tier to filter by. The card declares the
            # dropdown and this says what it does.
            "narrowed_by_service": False,
            "service_asked_for": str(ctx.params.get("service") or ""),
        },
    ).as_dict()


def _final_rung() -> str:
    """Payments' last rung, read from payments rather than typed.

    One vocabulary across both ladders is the only thing that makes the
    comparison in step 1 mean anything; a word written here would compare this
    module's spelling with payments'.
    """
    rungs = payments_seam.ladder_rungs()
    return str(rungs[-1]) if rungs else ""


# ── step 2 · was it served ────────────────────────────────────────────────


def step_confirm_the_letter_was_sent_and_delivered(ctx, subjects) -> dict[str, Any]:
    """2 · **A returned letter is not a served notice** (`BR-RBS-032`).

    ⚠ **THIS PRODUCT CANNOT SAY A LETTER WAS DELIVERED AND THIS STEP DOES NOT
    PRETEND TO.** `delivered` and `bounced` are PROVIDER facts and no provider
    adapter exists on any channel, print included, so a check built on them
    would report a clean morning over a channel nobody is listening to. What is
    recorded is `BR-CUS-100`'s **proof of service** — the channel, the
    reference, and the date it was served, entered by a person — and that is
    both the stronger fact and the one `assert_service_proved` already gates a
    real cut on. So the list a supervisor signs and the cut the product would
    refuse cannot disagree.

    Three distinct absences, kept apart because a regulator asks about each:
    **no notice at this tier** · **raised and nobody has said how it went out**
    · **served by a channel that is not certified mail**, which `DSC-02.3`
    marks *"Required at tier 3 — proof of service"*.
    """
    board = _board(ctx)
    served: dict[str, dict[str, Any]] = {}
    absent: dict[str, str] = {}
    wrong_channel = 0
    required = str(board.get("proof_channel_required") or "")
    for row in _walked(ctx, subjects):
        account_id = str(row["account_id"])
        proof = dict(row.get("proof") or {})
        if not proof.get("recorded"):
            absent[account_id] = str(proof.get("absence") or "awaiting_proof_of_service")
            continue
        if required and str(proof.get("channel") or "") != required:
            absent[account_id] = "proof_not_certified"
            wrong_channel += 1
            continue
        served[account_id] = proof
    ctx.set_results["_served"] = served
    ctx.set_results["_not_served"] = absent
    return _StepResult(
        found={"served": served, "not_served": absent},
        checked={
            "served_with_recorded_proof": len(served),
            "awaiting_proof_of_service": sum(
                1 for one in absent.values() if one == "awaiting_proof_of_service"
            ),
            "no_notice_at_this_tier": sum(
                1 for one in absent.values() if one == "no_notice_at_this_tier"
            ),
            "served_by_another_channel": wrong_channel,
            "proof_channel_required": required,
            # ⚠ **A DECLARED BLIND SPOT WITH A NUMBER BESIDE IT** (hard-won law
            # 7). `False` here is not *nothing bounced*; it is *no channel on
            # this deployment reports delivery at all*.
            "delivery_reported_by_any_channel": bool(board.get("delivery_reported")),
            "delivery_not_reported_because": board.get("delivery_not_reported_because"),
            "signed_for_back": sum(1 for one in served.values() if one.get("signed_for_on")),
            # ⚠ **WHETHER AN UNCLAIMED CERTIFIED LETTER STOPS A DISCONNECTION IS
            # UNWRITTEN AND IS NOT DECIDED HERE.** `assert_service_proved`'s own
            # docstring records it as owed: `BR-CUS-100`, `DSC-02.3` and
            # `BR-CUS-039` are all silent, and *"choosing either reading here
            # would decide, for real households, whether an unclaimed letter
            # stops a disconnection."* This runbook reads the same fact the cut
            # guard reads and counts the signatures beside it.
            "signature_back_is_not_required_because": (
                "no signed document says whether a tier-3 disconnection needs the signature "
                "back or only that certified mail was sent"
            ),
        },
    ).as_dict()


# ── step 3 · has the clock run out ────────────────────────────────────────


def step_confirm_the_notice_period_has_passed(ctx, subjects) -> dict[str, Any]:
    """3 · `BR-PAY-017`'s *48h certified final*, read from Settings.

    ⚠ **THE NUMBER IS THE TENANT'S AND IS NEVER A CONSTANT HERE** (`RBR-03`,
    `RB-021`: policy lives in Settings and is never duplicated on a card). An
    unreadable setting stops every account rather than falling back to 48 —
    computing a notice period from another utility's policy would clear a
    household for disconnection two days early, and `payments`' own posture for
    this class of read is the same one: *"every step it takes reaches a real
    customer."*

    ⚠ **THE PERIOD RUNS FROM `served_on`, NOT FROM `issued_on`.** The letter
    being raised in this product is not the letter reaching a house;
    `BR-CUS-100` separates the two on purpose, and the clock a regulator counts
    starts when it was served. `served_on` is a DATE, so the arithmetic is in
    whole days and says so: 48 hours is two days here, and an hour figure that
    is not a whole number of days is rounded UP to the next whole day, which is
    the direction that never disconnects anybody early.
    """
    setting = payments_seam.final_notice_hours()
    as_of = ctx.set_results.get("_as_of")
    hours = setting.get("hours") if setting.get("readable") else None
    days = None if hours is None else -(-int(hours) // 24)
    served = ctx.set_results.get("_served") or {}
    passed: dict[str, str] = {}
    not_yet: dict[str, str] = {}
    for account_id, proof in served.items():
        served_on = _date(proof.get("served_on"))
        if served_on is None or days is None:
            not_yet[account_id] = "the notice period could not be computed"
            continue
        ready_on = served_on + dt.timedelta(days=days)
        if as_of >= ready_on:
            passed[account_id] = ready_on.isoformat()
        else:
            not_yet[account_id] = ready_on.isoformat()
    ctx.set_results["_notice_passed"] = passed
    ctx.set_results["_notice_not_yet"] = not_yet
    return _StepResult(
        found={"passed": passed, "not_yet": not_yet},
        checked={
            "notice_period_readable": bool(setting.get("readable")),
            "notice_period_hours": hours,
            "notice_period_whole_days": days,
            "notice_period_passed": len(passed),
            "notice_period_not_yet": len(not_yet),
            "counted_from": "the date a person recorded the letter as served",
            "unreadable_setting_detail": setting.get("detail"),
        },
    ).as_dict()


# ── step 4 · anything landed overnight ────────────────────────────────────


def step_check_for_a_payment_overnight(ctx, subjects) -> dict[str, Any]:
    """4 · **Anything landed since the letter, applied or not.**

    ⚠ **SINCE THE LETTER, NEVER SINCE MIDNIGHT.** The card's parameter is
    *Check payments to: 06:00 today* — the END of the window — and its start is
    the day the certified letter was served, per account. A window that began at
    midnight would miss the customer who paid the evening the letter arrived,
    which is the single most likely way this list is wrong.

    ⚠ **`applied or not` IS THE CARD'S OWN PHRASE AND IT IS WHY NO STATUS IS
    FILTERED.** Money received and not yet placed against a bill is still money
    the household paid; a crew sent to it is the mistake this step exists to
    stop. `payments_recorded_between` windows on `posted_at`, which is when the
    customer paid rather than when a clerk typed it in.
    """
    served = ctx.set_results.get("_served") or {}
    as_of = ctx.set_results.get("_as_of")
    account_ids = list(served)
    earliest = min(
        (_date(proof.get("served_on")) for proof in served.values() if proof.get("served_on")),
        default=as_of,
    )
    rows = (
        payments_seam.payments_recorded_between(account_ids, earliest, as_of)
        if account_ids
        else []
    )
    paid: dict[str, dict[str, Any]] = {}
    for row in rows:
        account_id = str(row.get("account_id") or "")
        proof = served.get(account_id) or {}
        since = _date(proof.get("served_on")) or earliest
        posted_on = _date(row.get("posted_on"))
        if posted_on is None or posted_on < since:
            continue
        amount = _decimal(row.get("amount")) or ZERO
        held = paid.setdefault(
            account_id,
            {"total": ZERO, "count": 0, "latest_on": None, "currency": row.get("currency") or ""},
        )
        held["total"] = held["total"] + amount
        held["count"] = int(held["count"]) + 1
        if held["latest_on"] is None or posted_on.isoformat() > str(held["latest_on"]):
            held["latest_on"] = posted_on.isoformat()
    for row in paid.values():
        row["total"] = _stored(row["total"])
    ctx.set_results["_paid"] = paid
    return _StepResult(
        found={"paid": paid},
        checked={
            "accounts_with_a_payment_since_the_letter": len(paid),
            "window_opened_on": earliest.isoformat() if earliest else None,
            "window_closed_on": as_of.isoformat() if as_of else None,
            # The card's *Check payments to: 06:00 today*. The read windows on
            # a DATE, so the time of day narrows nothing and is carried rather
            # than quietly applied — a parameter that looks applied and is not
            # is worse than one that says so.
            "cutoff_time_declared": str(ctx.params.get("check_payments_to") or ""),
            "cutoff_time_applied": False,
            "cutoff_time_not_applied_because": (
                "payments are windowed by the date they were posted; this product records no "
                "time of day a clerk could compare against"
            ),
        },
    ).as_dict()


# ── step 5 · today, not when the letter went ──────────────────────────────


def step_check_protections_and_disputes_again(ctx, subjects) -> dict[str, Any]:
    """5 · **Today, not when the letter went** — the card's own words.

    ⚠ **THIS IS THE STEP THE RUNBOOK EXISTS FOR.** A protection recorded after
    the certified letter went out is exactly the row a stale list would have
    disconnected wrongly, and `RB-112`'s own example is *Pace, J. · Removed ·
    Medical protection added 3 Sep* — a letter dated 1 September.

    ⚠ **THE DISPUTE ROW IS `unavailable`, NEVER `pass`, AND THE COUNT TRAVELS.**
    `protection_check`'s own sentence: nothing in this repository stores a
    disputed AMOUNT, so *"a green clearance derived from a table that does not
    exist would authorise a cut."* This step prints how many accounts it could
    not check rather than reporting nought disputes.
    """
    account_ids = [str(one.subject_id) for one in subjects]
    board = customers_seam.protection_board(account_ids, as_of=ctx.set_results.get("_as_of"))
    ctx.set_results["_protections"] = board.get("accounts") or {}
    counts = dict(board.get("counts") or {})
    return _StepResult(
        found={"protections": board.get("accounts") or {}},
        checked={
            "accounts_checked": board.get("accounts_checked", 0),
            "medical_protection_in_force": counts.get("medical_certificate", 0),
            "payment_plan_in_good_standing": counts.get("payment_plan", 0),
            "weather_moratorium_in_force": counts.get("weather_moratorium", 0),
            "re_checked_on": board.get("as_of"),
            "disputes_that_could_not_be_checked": board.get("dispute_not_checked", 0),
            "disputes_not_checked_because": board.get("dispute_not_checked_because"),
        },
    ).as_dict()


# ── step 6 · the weather ──────────────────────────────────────────────────


def step_check_the_weather_moratorium(ctx, subjects) -> dict[str, Any]:
    """6 · Two different objects wear this name, and BOTH of them now run.

    ⚠ **THE AREA-WIDE HALF IS ANSWERED BY THE PERSON PRESSING RUN — PO ruling
    2026-09-07, `OQ-RBS-1757` CLOSED.** Verbatim: *"when you run this runbook,
    ask user to check temp range from ddropdown and use that details in logic"*.

    `RB-112`'s card asks for *"the forecast for the service area today"* against
    **below 32°F · above 100°F**, and nothing in this product holds a forecast,
    a temperature or a regulator's cold-weather calendar. Rather than build a
    weather feed or leave the check dark, the clerk states the band. It needs no
    integration, it puts the judgment where the accountability already is — a
    named person presses Run and signs the list — and it is auditable, because
    the band is stored on the run with everything else, so *why was nobody
    disconnected on 7 September* is answerable from the run alone.

    ⚠ **THE OTHER HALF IS UNCHANGED AND STILL REMOVES.**
    `customers.AccountProtection` kind `weather_moratorium` is a date window a
    person enters PER ACCOUNT (`apps/customers/disconnects.py`, B18 §5.8.3). It
    is gathered in step 5 and read here; the clerk's band does not replace it,
    because a regulator's order on one account outlives today's temperature.

    ⚠ **THE TILE CAN NOW SAY A TRUE `No`, AND ONLY BECAUSE SOMEBODY LOOKED.**
    Until today it read *Not checked* and never the card's green *No*, because
    *we looked at the weather and it is fine* and *nobody looked* read
    identically on a screen and send a crew to opposite places. That distinction
    survives: the band is REQUIRED, so a run that reached this step has an
    answer from a person, and `held` below is a judgment rather than a silence.
    """
    protections = ctx.set_results.get("_protections") or {}
    held = sorted(
        account_id
        for account_id, row in protections.items()
        if row.get("weather_moratorium")
    )
    band = (ctx.params or {}).get("weather_today")
    # A required enum cannot arrive absent through `run_parameters`, and this
    # step still refuses to GUESS if it somehow does: an unknown band holds the
    # run rather than clearing it, because the failure that matters here is
    # disconnecting somebody in a heatwave, never declining to.
    area_wide_holds = band not in WEATHER_BANDS or band in WEATHER_BANDS_THAT_HOLD
    # Recorded on the SET exactly as step 7 records `_not_a_working_day`, and
    # read by the per-record verdict below. A set-level stop that only appeared
    # in this step's own `checked` block would be a finding nobody acts on.
    ctx.set_results["_weather_holds"] = area_wide_holds
    return _StepResult(
        found={"held_by_a_moratorium": held},
        checked={
            "accounts_held_by_a_recorded_moratorium": len(held),
            # ⚠ TRUE NOW, AND IT IS THE WHOLE POINT OF THE RULING: a person
            # answered, so this is a judgment and not a silence.
            "area_wide_forecast_checked": True,
            "weather_band_the_clerk_reported": band,
            "area_wide_moratorium_in_force": area_wide_holds,
            "area_wide_holds_the_run_because": (
                "the clerk reported a band inside the card's own thresholds "
                "(below 32°F or above 100°F)"
                if area_wide_holds and band in WEATHER_BANDS
                else "no band was supplied, and an unknown band holds rather than clears"
                if area_wide_holds
                else None
            ),
        },
    ).as_dict()


# ── step 7 · no disconnect into a weekend ─────────────────────────────────


def step_check_it_is_a_working_day(ctx, subjects) -> dict[str, Any]:
    """7 · **No disconnect into a weekend or holiday.**

    ⚠ **COMPOSED FROM `holidays()` RATHER THAN ASKING FOR A SELECTOR NOBODY HAS
    — `13-selector-inventory.md` N-2 LEFT THAT CHOICE TO THIS WAVE.** The
    calendar is real and `G24` guards its horizon; *is this date a working day
    for this tenant* is one line over it, and a selector for it would be a new
    cross-module read for an expression this short.

    ⚠ **AN EMPTY CALENDAR IS A WARNING AND NEVER A CLEARANCE.** A utility that
    has not entered its holidays still has them; the count of holidays known
    travels so *"today is a working day"* over an empty calendar can be read for
    what it is.

    ⚠ **IT STOPS THE WHOLE LIST, WHICH IS THE CARD'S OWN RULE** — *"The weather
    moratorium and the working-day check both stop the list."* Every account is
    removed with the same reason rather than the run being refused, because a
    supervisor arriving on a Saturday needs to see the list they would have
    signed on Monday.
    """
    as_of: dt.date = ctx.set_results.get("_as_of")
    calendar = tenancy_seam.holiday_calendar()
    holidays = {
        str(_date(row.get("on") or row.get("date") or row.get("holiday_on")))
        for row in calendar
    }
    holidays.discard("None")
    weekend = as_of.weekday() >= 5
    holiday = as_of.isoformat() in holidays
    only = bool(ctx.params.get("working_days_only", True))
    stops = only and (weekend or holiday)
    ctx.set_results["_not_a_working_day"] = stops
    return _StepResult(
        found={"stops_the_list": stops},
        checked={
            "is_a_working_day": not (weekend or holiday),
            "is_a_weekend": weekend,
            "is_a_holiday": holiday,
            "holidays_this_tenant_has_entered": len(holidays),
            "working_days_only": only,
        },
    ).as_dict()


# ── step 8 · the field list, per account ──────────────────────────────────


def step_build_the_field_list(ctx, subject) -> dict[str, Any]:
    """8 · **Address, meter, balance, crew notes** — one account, one row.

    ⚠ **THE ONLY PER-RECORD STEP** — one account, one savepoint (hard-won law
    14), one row on the list a person signs.

    ⚠ **THE ADDRESS IS WALKED TO ON `premises` AND IS COPIED FROM NOWHERE**
    (hard rule 8, `BR-MET-1161`): the account names a unit, the unit names a
    premises, and the premises holds the address. An account has no address
    column and this step does not invent one.

    The order the reasons are tested in is the order a supervisor would give
    them, and every one of them REMOVES — see `WHY_LABELS`.
    """
    account_id = str(subject.subject_id)
    facts = (ctx.set_results.get("_rows") or {}).get(account_id) or {}
    ladder = (ctx.set_results.get("_ladder") or {}).get(account_id) or {}
    protections = (ctx.set_results.get("_protections") or {}).get(account_id) or {}
    paid = (ctx.set_results.get("_paid") or {}).get(account_id)
    minimum = _decimal(ctx.set_results.get("_minimum")) or ZERO
    balance = _decimal(ladder.get("balance"))

    why = ""
    detail = ""
    if not facts.get("cut_reachable", True):
        why = WHY_CUT_NOT_REACHABLE
        detail = "This account has no live service to disconnect."
    elif ctx.set_results.get("_not_a_working_day"):
        why = WHY_NOT_A_WORKING_DAY
        detail = "No disconnect into a weekend or a holiday."
    elif ctx.set_results.get("_weather_holds"):
        # ⚠ ABOVE the per-account protections ON PURPOSE. This is a fact about
        # the DAY, like the weekend above it: when it is 104°F nobody is
        # eligible, and a row saying "medical protection" would suggest the
        # others could have gone out. The clerk's own words come back to them.
        why = WHY_PROTECTED_MORATORIUM
        detail = _WEATHER_BAND_SENTENCE.get(
            ctx.params.get("weather_today"), "No weather was reported for today."
        )
    elif protections.get("medical"):
        why = WHY_PROTECTED_MEDICAL
        detail = _since("Medical protection", protections)
    elif protections.get("weather_moratorium"):
        why = WHY_PROTECTED_MORATORIUM
        detail = _since("Weather moratorium", protections)
    elif protections.get("plan_in_good_standing"):
        why = WHY_PROTECTED_PLAN
        detail = _since("Payment plan", protections)
    elif paid:
        why = WHY_PAID
        detail = f"Paid {_shown(paid.get('total'))} on {paid.get('latest_on')}."
    elif account_id in (ctx.set_results.get("_not_served") or {}):
        why = WHY_NOT_SERVED
        detail = _absence_sentence((ctx.set_results.get("_not_served") or {})[account_id])
    elif account_id in (ctx.set_results.get("_notice_not_yet") or {}):
        why = WHY_NOTICE_NOT_PASSED
        ready = (ctx.set_results.get("_notice_not_yet") or {})[account_id]
        detail = f"Not before {ready}." if ready.count("-") == 2 else f"{ready}."
    elif balance is None:
        why = WHY_UNDER_MINIMUM
        detail = "What this account owes could not be read."
    elif balance < minimum:
        why = WHY_UNDER_MINIMUM
        detail = f"Balance is under the {_shown(_stored(minimum))} minimum."

    outcome = OUTCOME_REMOVED if why else OUTCOME_ELIGIBLE
    route, label = FIX_FOR_WHY.get(why, (FIX_ACCOUNTS, "Open the account →"))
    proof = (ctx.set_results.get("_served") or {}).get(account_id) or {}
    return {
        "outcome": outcome,
        "reason": (
            f"{WHY_LABELS[why]}. {detail}".strip()
            if why
            else "Notice period passed · no payment"
        ),
        "decided_by_rule": (
            "Every reason an account should not be on the list is re-checked on the morning"
        ),
        "fix_route": route,
        "data": {
            # B14 rule 31 — the customer's name or the account number, never the id.
            "label": facts.get("label") or facts.get("account_no") or "",
            "account_no": facts.get("account_no"),
            # hard rule 8 — walked to on `premises`, never a column of its own.
            "address": facts.get("address") or "",
            "meter": facts.get("meter") or "",
            "balance": ladder.get("balance"),
            "currency": ladder.get("currency") or "",
            "letter_served_on": proof.get("served_on"),
            "signed_for_on": proof.get("signed_for_on"),
            "case_no": facts.get("case_no"),
            "why": why,
            "fix_label": label,
        },
    }


def _since(what: str, protections: dict[str, Any]) -> str:
    """*Medical protection added 3 Sep* — the card's own sentence shape."""
    kinds = {
        "Medical protection": "medical_certificate",
        "Weather moratorium": "weather_moratorium",
        "Payment plan": "payment_plan",
    }
    on = (protections.get("since") or {}).get(kinds.get(what, ""))
    return f"In force from {on}." if on else "In force today."


def _absence_sentence(code: str) -> str:
    """Which of the three absences this is, in a clerk's words (B14 rule 32)."""
    return {
        "no_notice_at_this_tier": "No certified letter has been raised.",
        "awaiting_proof_of_service": "Nobody has recorded how it was served.",
        "proof_not_certified": "It was not served by certified mail.",
    }.get(code, "Nobody has recorded how it was served.")


def _shown(stored: Any) -> str:
    """Two decimals, for a sentence a clerk reads (hard rule 2)."""
    amount = _decimal(stored)
    return "—" if amount is None else f"{amount.quantize(Decimal('0.01')):f}"


# ── the report ────────────────────────────────────────────────────────────


def report(view) -> list[Block]:
    """`RB-112`'s own blocks — **Verdict · KPIs · Records · Action · Downloads**.

    ⚠ **THE REMOVED ROWS ARE DRAWN WITH THE ELIGIBLE ONES ON PURPOSE**, which is
    the card's own design note: *"the person signing wants to see who was taken
    off and why, because that is the list that would have been wrong."*

    ⚠ **THE MORATORIUM TILE READS *Not checked* AND NEVER *No*.** `RB-112`'s own
    figure is a green **No**; `OQ-RBS-1757` is why this one is not. Where a
    per-account window IS in force the tile carries that count instead, which is
    a measured fact.
    """
    currency = str(view.set_results.get("_currency") or "")
    eligible = [one for one in view.records if one.outcome == OUTCOME_ELIGIBLE]
    removed = [one for one in view.records if one.outcome == OUTCOME_REMOVED]
    by_why: dict[str, int] = {}
    for record in removed:
        by_why[str(record.data.get("why") or "")] = (
            by_why.get(str(record.data.get("why") or ""), 0) + 1
        )
    protected = sum(by_why.get(one, 0) for one in PROTECTION_REASONS)
    paid = by_why.get(WHY_PAID, 0)
    under = by_why.get(WHY_UNDER_MINIMUM, 0)
    moratorium = by_why.get(WHY_PROTECTED_MORATORIUM, 0)
    # ⚠ **THE REPORT VIEW CARRIES NO `params`** — `_ReportView` is records,
    # counts and set results by design (`BR-RBS-020`: composed from what the
    # run produced), so the tile's own label reads the figure the STEP used
    # rather than re-reading a knob that could have moved.
    minimum = _shown(view.set_results.get("_minimum"))

    return [
        Block(
            block="verdict",
            payload={
                "word": f"{len(eligible)} eligible",
                "tone": "warning" if eligible else "success",
                "count": f"{len(removed)} removed since the letter",
                "detail": (
                    f"{paid} paid overnight · {protected} protected · "
                    f"{under} under minimum · weather not checked here"
                ),
            },
        ),
        Block(
            block="kpis",
            payload={
                "tiles": [
                    {
                        "id": "eligible",
                        "label": "Eligible today",
                        "value": {"kind": "text", "text": str(len(eligible))},
                    },
                    {
                        "id": "paid",
                        "label": "Paid overnight",
                        "value": {"kind": "text", "text": str(paid)},
                        "detail": "Since the letter was served",
                    },
                    {
                        "id": "protected",
                        "label": "Protected",
                        "value": {"kind": "text", "text": str(protected)},
                        "detail": "Re-checked this morning",
                    },
                    {
                        "id": "under_minimum",
                        "label": "Under the minimum",
                        "value": {"kind": "text", "text": str(under)},
                        # ⚠ **THE FIGURE CARRIES ITS CURRENCY** (hard rule 2:
                        # money never travels without one). The first build read
                        # `Under 50.00` on screen — a money threshold with no
                        # currency on it, which a browser walkthrough found and
                        # no backend test could, because the label was exactly
                        # the string the test asserted.
                        "detail": f"{minimum} {currency}".strip(),
                    },
                    {
                        "id": "moratorium",
                        "label": "Moratorium",
                        # ⚠ **NEVER THE CARD'S GREEN `No` — `OQ-RBS-1757`.**
                        "value": {
                            "kind": "text",
                            "text": str(moratorium) if moratorium else "Not checked",
                        },
                        "detail": (
                            "Recorded on the account"
                            if moratorium
                            else "No forecast for the service area"
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
                    {"key": "address", "label": "Address"},
                    {"key": "balance", "label": "Balance", "numeric": True},
                    {"key": "served", "label": "Letter served"},
                    {"key": "today", "label": "Today"},
                    {"key": "why", "label": "Why"},
                ],
                "rows": [
                    {
                        "id": f"account-{index}",
                        "cells": {
                            "account": {
                                "kind": "text",
                                "text": str(record.data.get("label") or ""),
                            },
                            "address": {
                                "kind": "text",
                                "text": str(record.data.get("address") or "—"),
                            },
                            "balance": (
                                {
                                    "kind": "money",
                                    "amount": str(record.data["balance"]),
                                    "currency": str(record.data.get("currency") or currency),
                                }
                                if record.data.get("balance")
                                # ⚠ `—` AND NEVER `$0.00`: a balance nobody could
                                # read is not a balance of nothing, and on this
                                # screen the difference is a crew's morning.
                                else {"kind": "text", "text": "—"}
                            ),
                            "served": (
                                {"kind": "date", "value": str(record.data["letter_served_on"])}
                                if record.data.get("letter_served_on")
                                else {"kind": "text", "text": "Not recorded"}
                            ),
                            "today": {
                                "kind": "pill",
                                "label": (
                                    "Eligible"
                                    if record.outcome == OUTCOME_ELIGIBLE
                                    else "Removed"
                                ),
                                "tone": (
                                    "danger"
                                    if record.outcome == OUTCOME_ELIGIBLE
                                    else "success"
                                ),
                            },
                            "why": {"kind": "text", "text": record.reason},
                        },
                        "meta": {
                            "decided_by_rule": record.decided_by_rule,
                            "outcome": record.outcome,
                            "case_no": record.data.get("case_no"),
                        },
                    }
                    # Eligible first, then the removed rows — the card's own
                    # order, and the list a person signs is the top of it.
                    for index, record in enumerate(eligible + removed, start=1)
                ],
                "total": len(view.records),
                "chips": [
                    {"id": "all", "label": "All", "count": len(view.records)},
                    {"id": "eligible", "label": "Eligible", "count": len(eligible)},
                    {"id": "removed", "label": "Removed", "count": len(removed)},
                ],
                "empty": {
                    "title": "Nobody is at the last tier today.",
                    "helper": (
                        "A certified final notice with a recorded proof of service is what "
                        "puts an account on this list."
                    ),
                },
            },
        ),
        Block(
            block="action",
            payload={
                "label": "Approve field list",
                # ⚠ **THE DANGER TIER, AND IT APPROVES A LIST — NEVER A
                # DISCONNECTION** (`US-RBS-024` TC-3: *no disconnect port, and
                # there must be none*). B14 rule 6: a commit on the band is the
                # danger tier.
                "tier": "danger",
                "enabled": False,
                # B14 rule 33 — a refusal caps at five or six words.
                "reason": "Run approval is not built yet",
            },
        ),
        Block(
            block="downloads",
            payload={
                "files": [
                    {"id": "field_list", "label": "Field list", "format": "csv"},
                    {"id": "all", "label": "All", "format": "csv"},
                ]
            },
        ),
    ]


# ── the guard and the pinned scope ────────────────────────────────────────

SAMPLE_KEY = "_sample_account_ids"


def _is_sample(ctx, subject) -> bool:
    """`RB-112`'s *Never include: Sample* (`BR-TEN-057`, `BR-RBS-012`).

    ⚠ **THE ONLY GUARD ON THIS RUNBOOK, AND THE OTHER THREE EXCLUSIONS ARE
    DELIBERATELY NOT GUARDS** — see the module docstring. A guarded account is
    still PINNED and still COUNTED, so the screen can say how many were left out
    rather than quietly showing a shorter list.
    """
    return str(subject.subject_id) in (ctx.set_results.get(SAMPLE_KEY) or frozenset())


def resolve(ctx):
    """The pinned set: **every open case at the last tier** (`BR-RBS-019`).

    ⚠ **THE COUNT ON THE SETUP SCREEN IS THIS FUNCTION'S ANSWER** — the card's
    *Matches 23 accounts today*.

    ⚠ **THE ADDRESS AND THE METER ARE WALKED TO, NOT READ OFF THE ACCOUNT**
    (hard rule 8, `BR-MET-1161`). `resolve_anchors` carries `premise_address` on
    the unit row, which is the whole chain — account → unit → premises → address
    — answered without any other table holding an address column; the meter
    number comes from `metering`'s own read of the unit's meters.
    """
    as_of = tenancy_seam.today()
    board = customers_seam.final_notice_board(as_of=as_of)
    rows = list(board.get("rows") or [])

    ctx.set_results["_as_of"] = as_of
    ctx.set_results["_board"] = board
    # The figure the STEPS use, pinned once so the report's own tile label and
    # the comparison a row was decided by cannot come from two reads.
    ctx.set_results["_minimum"] = str(ctx.params.get("minimum_balance") or "0")
    ctx.set_results["_currency"] = tenancy_seam.currency()
    ctx.set_results[SAMPLE_KEY] = frozenset(
        str(row["account_id"]) for row in rows if row.get("is_sample")
    )

    # ONE read for the estate, twice: the addresses and the meters (`NFR-3`).
    unit_ids = [row["unit_id"] for row in rows if row.get("unit_id")]
    premises_ids = [row["premises_id"] for row in rows if row.get("premises_id")]
    anchors = (
        metering_seam.resolve_anchors(unit_ids, premises_ids)
        if (unit_ids or premises_ids)
        else {"units": {}, "premises": {}}
    )
    meters: dict[str, str] = {}
    if unit_ids:
        for meter in metering_seam.meter_read_history(unit_ids=unit_ids, limit_per_meter=1):
            key = str(meter.get("unit_id") or "")
            if key and key not in meters:
                meters[key] = str(meter.get("asset_no") or "")

    facts: dict[str, dict[str, Any]] = {}
    for row in rows:
        unit = (anchors.get("units") or {}).get(str(row.get("unit_id") or "")) or {}
        premise = (anchors.get("premises") or {}).get(str(row.get("premises_id") or "")) or {}
        facts[str(row["account_id"])] = {
            **row,
            "address": (
                unit.get("premise_address")
                or premise.get("address_line")
                or premise.get("label")
                or ""
            ),
            "meter": meters.get(str(row.get("unit_id") or ""), ""),
        }
    ctx.set_results["_rows"] = facts

    return [
        SubjectRef(
            subject_type="account",
            subject_id=str(row["account_id"]),
            label=str(row.get("label") or row.get("account_no") or ""),
        )
        for row in rows
    ]


RUNBOOK = RunbookDefinition(
    key=KEY,
    name="Disconnect eligibility",
    kind=models.KIND_CHECK,
    category="collections",
    subject_type="account",
    unit_of_work="an account at the last tier of the ladder",
    triggers=(models.TRIGGER_MANUAL,),
    tags=("Work",),
    parameters=(
        Parameter(
            name="accounts_at",
            type=PARAM_REF_SETTING,
            label="Accounts at",
            # ⚠ DECLARED, AND NO SETTINGS ROW HOLDS IT TODAY. The card marks it
            # read-only and Settings-owned; what step 1 actually applies is
            # `customers`' own last tier (`disconnects.TIER_3`), stated in that
            # step rather than invented here.
            setting_key="payments.collections_last_tier",
        ),
        Parameter(
            name="service",
            type=PARAM_ENUM,
            label="Service",
            default="water",
            # Tenant-resolved (`BR-RBS-042` clause 2) — a Water-and-Sewer
            # utility is offered two, never the platform's eleven. A hand-typed
            # catalogue here is the second copy that made an eleventh service
            # invisible on the sign-up screen.
            domain=DOMAIN_SERVICE,
        ),
        Parameter(
            name="never_include",
            type=PARAM_REF_SETTING,
            label="Never include",
            setting_key="payments.collections_exclusions",
        ),
        Parameter(
            name="notice_period",
            type=PARAM_REF_SETTING,
            label="Notice period",
            # `BR-PAY-017`'s *48h certified final*, READ in step 3 through
            # `payments_seam.final_notice_hours` and never copied here
            # (`RBR-03`).
            setting_key="collections.final_notice_hours",
        ),
        Parameter(
            name="weather_today",
            type=PARAM_ENUM,
            label="Weather today",
            # ⚠ **ASKED AT RUN TIME, FROM A DROPDOWN — PO RULING 2026-09-07,
            # `OQ-RBS-1757` CLOSED.** Verbatim: *"when you run this runbook, ask
            # user to check temp range from ddropdown and use that details in
            # logic"*. This replaced a `PARAM_REF_SETTING` that was declared and
            # read by nothing, because the card's value is a TEMPERATURE rule
            # over a service area and no setting, feed or table in this product
            # holds one.
            #
            # **`choices`, not a `domain`.** A domain is tenant-resolved (a
            # Water-and-Sewer utility is offered two services, never eleven);
            # these three bands are the runbook's own fixed vocabulary and are
            # the same in every utility, which is exactly what `choices` is for.
            # The thresholds are the CARD's — below 32°F, above 100°F — and are
            # not invented here.
            #
            # ⚠ **REQUIRED, WITH NO DEFAULT.** This runbook is manual-trigger
            # only, so there is always a person to ask, and a default would be a
            # plausible wrong answer — which is the defect, not the cure
            # (`DEF-SHL-3964`: an unset regional format silently became
            # `MM/DD/YYYY` across the whole product for weeks). A clerk who has
            # not looked out of the window must say so rather than have the run
            # assume a mild day on their behalf.
            required=True,
            choices=WEATHER_BANDS,
        ),
        Parameter(
            name="check_payments_to",
            type=PARAM_TEXT,
            label="Check payments to",
            default="06:00",
        ),
        Parameter(
            name="minimum_balance",
            type=PARAM_MONEY,
            label="Minimum balance",
            # The card's `$50.00`, as a stored four-decimal STRING — never a
            # float, which this parameter lives in `jsonb` and no column type
            # would catch (hard rule 2).
            default="50.0000",
        ),
        Parameter(
            name="working_days_only",
            type=PARAM_TOGGLE,
            label="Working days only",
            default=True,
        ),
        Parameter(
            name="produce_a_field_list",
            type=PARAM_TOGGLE,
            label="Produce a field list",
            default=True,
        ),
        Parameter(name="runs", type=PARAM_ENUM, label="Runs", choices=("manual",), default="manual"),
    ),
    guards=(Guard(key="sample", label="Never include: Sample", applies=_is_sample),),
    resolve=resolve,
    report=report,
    steps=(
        Step(key=STEP_GATHER, label=STEP_LABELS[STEP_GATHER], mode=MODE_SET, run=step_gather_accounts_at_the_last_tier),
        Step(key=STEP_LETTER, label=STEP_LABELS[STEP_LETTER], mode=MODE_SET, run=step_confirm_the_letter_was_sent_and_delivered),
        Step(key=STEP_NOTICE, label=STEP_LABELS[STEP_NOTICE], mode=MODE_SET, run=step_confirm_the_notice_period_has_passed),
        Step(key=STEP_PAYMENT, label=STEP_LABELS[STEP_PAYMENT], mode=MODE_SET, run=step_check_for_a_payment_overnight),
        Step(key=STEP_PROTECTIONS, label=STEP_LABELS[STEP_PROTECTIONS], mode=MODE_SET, run=step_check_protections_and_disputes_again),
        Step(key=STEP_WEATHER, label=STEP_LABELS[STEP_WEATHER], mode=MODE_SET, run=step_check_the_weather_moratorium),
        Step(key=STEP_WORKING_DAY, label=STEP_LABELS[STEP_WORKING_DAY], mode=MODE_SET, run=step_check_it_is_a_working_day),
        # ⚠ THE ONLY PER-RECORD STEP — one account, one savepoint, one row.
        Step(key=STEP_FIELD_LIST, label=STEP_LABELS[STEP_FIELD_LIST], mode=MODE_PER_RECORD, run=step_build_the_field_list),
    ),
    # ⚠ **EMPTY, AND THAT IS THE POINT** (`BR-RBS-002`, `US-RBS-024` TC-3). A
    # Check is CONSTRUCTED with no writer, so nothing here disconnects anyone —
    # the capability is absent rather than refused at runtime. There is no
    # disconnect port in the thirteen and there must not be one: a crew acts
    # through the Work module on a list a person signed.
    ports=(),
)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-024 (EP-RBS-05; CR-075 wave S)
# generated: 2026-09-07 by the CR-075 wave S build lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint — every runbooks route is a GET and POST /runbooks/{key}/runs is wave L) E=n/a(no screen — RBS-004 and RBS-006 render any runbook; RB-020) F✔ G✔ H=n/a(no 🔒 path: this composes no idempotency key, touches no rating math and posts no ledger line)
# gates: pytest tests/test_us_rbs_024_disconnect_eligibility.py · pytest tests/test_us_rbs_015_conformance.py · G115 · G20
# exceptions: medical, dispute and plan are RECORDS rather than GUARDS — the card draws each removal as a row with its reason and a guarded subject carries none, so building them as guards would delete the nine rows this runbook exists to show; only `Sample` is a guard · the scope reads `disconnect_cases` and not payments' `account_collection_state` (the overlap is unruled, `DEF-675`) because only one of the two records a certified letter and its proof of service, and step 1 prints the disagreement as a number · *delivered* is unreadable on every channel and step 2 reads `BR-CUS-100`'s proof of service instead, with the blind spot counted · the AREA-WIDE weather moratorium is `OQ-RBS-1757` and the tile reads *Not checked*, never the card's green `No` · the `service` parameter narrows nothing today and step 1 says so · `check_payments_to` is declared and the window is by DATE, which step 4 states
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
