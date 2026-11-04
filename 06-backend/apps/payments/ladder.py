# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-014 (the collection sequence engine: due+3 → late fee →
#           10-day → 5-day → 48h certified final)
#           Screens: S32 · S34 (the tier and next-step columns) · S70
# Rules:    BR-PAY-017 (the tenant-config ladder; paper v1; medical hold
#           excluded; every step a queue-write) · BR-NOT-005 (a notice is
#           WRITTEN to the outbound table; only the dispatcher sends) ·
#           BR-PAY-021 (evaluation reads the POSTING date) · BR-PAY-032 (days
#           late = today − the OLDEST UNPAID invoice's due date) · BR-PAY-016 as
#           amended 2026-08-12 (a partial payment pauses the ladder only above a
#           TENANT-SET percentage — OQ-136; a missed instalment lifts the plan
#           pause the next day — OQ-170; after a BOUNCE the ladder restarts at
#           rung 1 — OQ-133) · BR-BIL-001 as amended (the $25.00 balance floor
#           governs the WHOLE ladder — OQ-137 — and is PER-UTILITY with $25.00
#           seeded — OQ-157) · BR-CUS-043 (an active + current plan pauses it) ·
#           BR-CUS-039 / A19 rule 3 (certified mail REQUIRED on the final tier)
#           · CLAUDE.md rule 1 (tenant scoping) · rule 2 (money) · rule 7
# Tests:    06-backend/tests/test_us_pay_014_ladder.py
# Impacts:  apps/payments/notices.py (every step is one of its two bulk sends) ·
#           apps/payments/dunning.py (the plan pause) ·
#           apps/payments/collections_models.AccountCollectionState (the tier
#           this engine advances) · apps/payments/settings_seam.py (the
#           intervals, the floor and the pause percentage) ·
#           apps/payments/reversal.py (`reverse_payment` calls
#           `restart_after_bounce` when its caller passes
#           `resume_collections=True` — wired 2026-09-01, CR-059 CS-5; this line
#           named it as a caller for three weeks while nothing called it) ·
#           apps/payments/outstandings.py (renders the tier it sets)
# ───────────────────────────────────────────────────────
"""The collection ladder — when it runs, when it does not, and where it resumes.

BR-PAY-017, CONFIRMED: *"Collection sequence (tenant-config): due+3 reminder →
late fee → 10-day → 5-day → 48h certified final (paper v1, medical-hold
excluded)"*.

    rung 0   due + `reminder_days_after_due`   friendly reminder
    ——       due + grace                       THE LATE FEE — billing's
                                               (BR-BIL-001/008). This engine
                                               CITES the step and applies
                                               nothing: payments never writes a
                                               charge line.
    rung 1   reminder + tier days[0]           10-day disconnect notice
    rung 2   cut − tier days[1]                5-day disconnect notice
    rung 3   cut − `final_notice_hours`        48-hour CERTIFIED final (see
                                               `rung_due_on` for the derivation)

Every step is a QUEUE-WRITE through `notices.py` (BR-NOT-005) and every send AND
skip appends `notice_history` (J4 step 2). Nothing here sends anything itself.

════════════════════════════════════════════════════════════════════════════
FIVE THINGS STOP THIS LADDER, AND ALL FIVE ARE RECORDED — NEVER SILENT
════════════════════════════════════════════════════════════════════════════
1. **THE BALANCE FLOOR, ON THE WHOLE LADDER** (PO 2026-08-12, OQ-137). An
   account leaving **$2.40** unpaid gets no reminder, no notice and above all no
   **$8.00** certified letter: chasing $2.40 spends more than it recovers. The
   floor is **$25.00** as a SEEDED DEFAULT and is **per-utility** (OQ-157,
   *"per utility - uyiliyy can define it using settings"*) — a submetered block
   averaging $38 a bill and a municipal water utility averaging $180 cannot
   share one. It is strict: a balance of exactly $25.00 IS chased, the same
   reading BR-BIL-001's fee half already ships.
2. **MEDICAL HOLD** (A15 via BR-CUS-039). Excluded from every step, with the
   skip in `notice_history`. The hold is a customers-owned clinical fact and is
   passed IN, never inferred here — the posture `notices.py` already takes.
3. **AN ACTIVE AND CURRENT PAYMENT PLAN** (BR-CUS-043), through
   `dunning.collections_pause_for`. It pauses the ladder over *the arrears the
   plan spreads* and NOT over the current month's bill (BR-BIL-073), and a
   MISSED instalment lifts it the very next day with no grace (OQ-170,
   *"Immediate"* — PE-13's $36.22 unpaid 1 Oct resumes chasing 2 Oct) while the
   plan stays ACTIVE, because nobody is dropped.
4. **A PARTIAL PAYMENT AT OR ABOVE THE TENANT'S PERCENTAGE** (PO 2026-08-12,
   OQ-136). Worked on the S34 fixture: an account owing **$948** pays **$150**
   — **15.8%**, under either figure the PO named, so **the ladder continues**.
   At 25% it would need **$237.00**; at 50%, **$474.00**. The percentage is a
   TENANT SETTING and the PO named 25 and 50 *as examples, not as the value*, so
   nothing here seeds one.
5. **MONEY POSTED BY THE DUE DATE** (BR-PAY-021) — which simply leaves no
   overdue balance to chase, and needs no special case.

════════════════════════════════════════════════════════════════════════════
AND ONE THING RESTARTS IT: A BOUNCE (PO 2026-08-12, OQ-133)
════════════════════════════════════════════════════════════════════════════
Verbatim: *"Restart from the beginning"*. A **$1,842.10** bill due **6 Jul**
paid by a cheque posted **5 Jul** stopped the chase; the cheque bounces three
weeks later. The customer gets **the full ladder again, first notice onward** —
not the rung it had reached — **because the payment that stopped it never
existed**. `restart_after_bounce` is that reset.

**WHO CALLS IT, PRECISELY — because this paragraph was WRONG for three weeks
(CR-059 CS-5, 2026-09-01).** It read *"`restart_after_bounce` is that reset and
`reversal.py` calls it"*, and `reversal.py` did not: `reverse_payment` declared
a `resume_collections` argument, documented it in eleven lines and **read it
nowhere**, so this function had no caller outside its own test and a bounced
customer stayed on whatever rung their AGE selected — the exact outcome the
ruling above replaced. It is stated here rather than quietly corrected because
it is hard-won law 1: *a comment claiming a guarantee is not the guarantee*, and
nothing in this repo reads prose for truth.

`reversal.reverse_payment` calls it now, inside the bounce's own transaction,
**when its caller passes `resume_collections=True`** — which is the S35 Reverse
modal's resume-collections choice. **The default is False and that is the other
half of the ruling:** a bounce PAUSES the ladder and a PERSON resumes it; the PO
settled WHERE it re-enters, not that it should re-enter with nobody asking. The
bounce reports which of the two happened on its own result
(`collection_ladder_paused`, `collection_ladder_restarted`, or
`collection_ladder_not_restarted` when this module publishes no reset), and
`tests/test_cr059_cs5_ladder_restart.py` fails if this sentence and that call
ever part company again.

════════════════════════════════════════════════════════════════════════════
THE TWO FIGURES THIS ENGINE CANNOT READ YET, AND WHY THEY ARE ARGUMENTS
════════════════════════════════════════════════════════════════════════════
`balance_floor` and `partial_pause_percent` are ARGUMENTS defaulting to None,
where None means *read the tenant's setting*. Both settings were RULED on
2026-08-12 and neither has storage: `apps.tenancy.settings_families.COLLECTIONS`
carries no `ladder_balance_floor_amount` and no `partial_payment_pause_percent`,
that file belongs to another lane this session, and the two `Param(...)` lines
are REPORTED rather than written. So `settings_seam` REFUSES, loudly, naming the
gap — and the ruled behaviour is nonetheless built, argued and asserted at
$25.00 / 25% / 50% with the PO's own worked figures.

This is BR-BIL-001's own precedent, not a new posture: OQ-157's registry row
records the same shape for the same $25.00 — *"the figure is the DEFAULT of
`late_fee.assess_late_fee(balance_floor=...)` rather than an inlined literal, so
making it a tenant setting later is a caller change and not a rewrite"*.

**WHAT THIS ENGINE STILL HAS NO CALLER FOR.** BR-PAY-017's ladder is evaluated
by a scheduled job and this repo's job runner (BE-07) registers no collections
job. `run_ladder` is published, tenant-scoped and tested, and the S34 screen can
drive it over a selection; the nightly caller is REPORTED, not implied.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.db import transaction

from core import audit as core_audit
from core import tenancy as core_tenancy

from apps.payments import billing_seam, dunning, notices, settings_seam
from apps.payments.collections_models import (
    TIER_FINAL_48_HOUR,
    TIER_FIRST_10_DAY,
    TIER_FRIENDLY,
    TIER_SECOND_5_DAY,
    AccountCollectionState,
)
from apps.payments.exceptions import PaymentRuleError

ZERO = Decimal("0")
HUNDRED = Decimal("100")

#: The rungs, in the order BR-PAY-017 names them. `TIER_FRIENDLY` is the due+3
#: reminder; the other three are the disconnect tiers `notices.py` already
#: writes. ONE vocabulary across the automatic engine and the manual S35 modals,
#: which is what makes US-PAY-015 TC-4's "no double-send" possible at all.
LADDER_RUNGS: tuple[str, ...] = (
    TIER_FRIENDLY,
    TIER_FIRST_10_DAY,
    TIER_SECOND_5_DAY,
    TIER_FINAL_48_HOUR,
)

#: Why a step did not happen. Each becomes a `notice_history` skip row — J4 step
#: 2 requires every send AND skip to be recorded, because a silent exclusion is
#: the one thing a collections trail may not contain.
SKIP_BELOW_FLOOR = "below_ladder_floor"
SKIP_MEDICAL_HOLD = notices.SKIP_MEDICAL_HOLD
SKIP_PLAN_PAUSED = "payment_plan_pause"
SKIP_PARTIAL_PAYMENT = "partial_payment_pause"
SKIP_NOTHING_OVERDUE = "nothing_overdue"
SKIP_NOT_DUE_YET = "next_step_not_due"
SKIP_LADDER_COMPLETE = "ladder_complete"

#: ⚠ **THE SAME-DAY GUARD — CLAUDE.md hard rule 6, added 2026-09-02 (CR-059
#: CS-10, `DEF-3150`).** This module's own exception (4) has read *"ONE STEP PER
#: ACCOUNT PER PASS"* since it shipped, and the CR that asked for a scheduled
#: caller repeated it as *"the idempotence it needs already holds"*. **PER PASS
#: IS NOT PER DAY, and the difference is four letters in one afternoon.** Every
#: rung's due date is derived from `oldest_due_on` ALONE (see `rung_due_on`), so
#: on an account 62 days overdue the reminder, the 10-day, the 5-day and the
#: certified final are ALL past due at once: four consecutive passes on the same
#: `as_of` step it four times, each one lawfully, and the last posts an $8.00
#: certified disconnection letter. That is exactly what exception (4) says must
#: not happen, and nothing enforced it.
#:
#: It was reachable before any scheduler existed — `POST /collections/run`
#: pressed twice is two passes — and a scheduler makes it routine, because
#: `CELERY_TASK_ACKS_LATE` is on and a re-delivered message is a second pass by
#: design.
SKIP_ALREADY_NOTICED_TODAY = "already_noticed_today"

#: hard rule 7 — a ladder step reaches a real customer with a real cut-off date.
AUDIT_LADDER_STEP = "collection.step"
AUDIT_LADDER_RESTART = "collection.restarted"

#: US-PAY-014 §1. Carried on every result rather than stated only here.
LADDER_UNAVAILABLE: tuple[dict[str, Any], ...] = (
    {
        "code": "no_scheduled_caller",
        "br_ref": "BR-PAY-017",
        "detail": "BR-PAY-017's ladder is evaluated on a schedule and this repo's job runner "
        "registers no collections job. `run_ladder` is published and can be driven from S34 "
        "over a selection; nothing runs it nightly. Until it does, the ladder advances only "
        "when a human asks it to.",
    },
    {
        "code": "late_fee_step_is_billings",
        "br_ref": "BR-BIL-001",
        "detail": "the ladder's second rung is the LATE FEE and this engine does not apply it. "
        "BR-BIL-001/008 own the computation and `apps/billing/late_fee.py` is the implementation; "
        "payments never writes a charge line (BR-BIL-007). The step is CITED so the sequence "
        "reads correctly and nothing here moves that money.",
    },
)


def ladder_problems() -> tuple[dict[str, Any], ...]:
    """`LADDER_UNAVAILABLE`, minus anything that has stopped being true.

    ⚠ **THE CONSTANT ABOVE IS STILL THE ANSWER FOR ALMOST EVERY DEPLOYMENT AND
    THAT IS WHY IT IS STILL A CONSTANT.** CR-059 CS-10 registered a scheduled
    caller (`apps/payments/collections_schedule.py`), so `no_scheduled_caller`
    — *"nothing runs it nightly"*, printed to a clerk on S34 as **"Nothing runs
    the collection sequence overnight"** — became capable of being FALSE. It is
    false only where BOTH halves hold: the beat entry is registered on a live
    celery app, and THIS utility has switched the schedule on. Neither implies
    the other, and on a deployment with no beat, or a utility that has not
    turned it on, the sentence is exactly as true as it was.

    So the entry is dropped only when the schedule is demonstrably live, and
    kept in every other case. Stating an absence that no longer exists misleads
    a clerk; withdrawing one that still does is hard-won law 1 with the sign
    flipped — a claimed guarantee, printed on a screen.

    Callers pass the result where they used to pass the constant. The constant
    keeps its name and its content, because it is what `LADDER_UNAVAILABLE`
    still means: what this engine cannot do unaided.
    """
    live = False
    try:
        from apps.payments import collections_schedule

        live = collections_schedule.is_live()
    except Exception:  # noqa: BLE001 — an unanswerable question is not a live schedule
        live = False
    if not live:
        return LADDER_UNAVAILABLE
    return tuple(
        problem for problem in LADDER_UNAVAILABLE if problem["code"] != "no_scheduled_caller"
    )


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


@dataclass(frozen=True)
class LadderDecision:
    """What the ladder does for ONE account today, and why.

    `runs` False with a `skip_reason` is a decision, not an absence — every one
    of them is written to `notice_history` by the caller, so *"why did this
    customer never hear from us?"* has an answer on the account.

    `days_late` is BR-PAY-032's figure: today − the oldest unpaid invoice's due
    date. It is None when no unpaid bill carries a due date, and None is NOT
    zero: a bill nobody can place in time cannot be chased on a schedule
    anchored to time.
    """

    account_id: str
    runs: bool
    rung: str | None = None
    skip_reason: str | None = None
    balance: Decimal = ZERO
    days_late: int | None = None
    next_step_on: Any = None
    detail: str = ""


@dataclass(frozen=True)
class LadderRun:
    """What one pass over a selection did (US-PAY-014 TC-1)."""

    as_of: date
    decisions: tuple[LadderDecision, ...] = ()
    problems: tuple[dict[str, Any], ...] = field(default=LADDER_UNAVAILABLE)

    @property
    def stepped(self) -> tuple[LadderDecision, ...]:
        return tuple(decision for decision in self.decisions if decision.runs)

    @property
    def skipped(self) -> tuple[LadderDecision, ...]:
        return tuple(decision for decision in self.decisions if not decision.runs)


def rung_due_on(
    rung: str, *, due_on: date, reminder_days: int, tier_days: tuple[int, ...], final_hours: int
) -> date:
    """The day one rung falls due, derived from the tenant's OWN intervals.

    ════════════════════════════════════════════════════════════════════════
    THE DERIVATION, STATED BECAUSE IT IS A DERIVATION AND NOT A RULE
    ════════════════════════════════════════════════════════════════════════
    BR-PAY-017 ratifies the SEQUENCE — *"due+3 reminder → late fee → 10-day →
    5-day → 48h certified final"* — and the tenant settings ratify the NUMBERS
    (`reminder_days_after_due` 3, `notice_tier_days` [10, 5],
    `final_notice_hours` 48). What no ratified document states is the gap
    between the reminder and the FIRST disconnect notice.

    Everything else follows mechanically once one thing is seen: **the tier
    names are notice PERIODS, not offsets.** A "10-day notice" is a notice
    saying *service stops in 10 days*, a "5-day notice" says *in 5 days*, and
    the "48-hour certified final" says *in 2 days* — so all three must name the
    SAME service-cut date or the utility has told one customer three different
    deadlines. That fixes every gap except the first:

        reminder    due + 3                     → day  3
        1st notice  reminder + tier_days[0]      → day 13   (the one convention)
        cut date    1st notice + tier_days[0]    → day 23
        2nd notice  cut − tier_days[1]           → day 18
        final       cut − final_hours/24         → day 21

    The single convention is the second line: the first disconnect notice
    follows the reminder by its own notice period. It is recorded here, and in
    the lane report, as a DERIVATION rather than presented as ratified law —
    the same posture the field map takes with its P-numbered discrepancies. A
    tenant that wants a different gap changes `reminder_days_after_due`, and a
    ruling that fixes it changes one line.
    """
    if rung not in LADDER_RUNGS:
        raise PaymentRuleError(
            f"{rung!r} is not one of BR-PAY-017's rungs ({list(LADDER_RUNGS)}). A step nothing "
            "recognises is a notice no screen will show and no history row will group.",
            br_ref="BR-PAY-017",
        )
    reminder_on = due_on + timedelta(days=reminder_days)
    if rung == TIER_FRIENDLY:
        return reminder_on
    first_on = reminder_on + timedelta(days=tier_days[0])
    if rung == TIER_FIRST_10_DAY:
        return first_on
    cut_on = first_on + timedelta(days=tier_days[0])
    if rung == TIER_SECOND_5_DAY:
        # The second tier's own period before the SAME cut date. A tenant who
        # configured only one tier has no second notice, so the ladder steps
        # straight from the first to the certified final rather than inventing
        # a period the tenant never set.
        if len(tier_days) < 2:
            return cut_on - timedelta(days=_final_days(final_hours))
        return cut_on - timedelta(days=tier_days[1])
    return cut_on - timedelta(days=_final_days(final_hours))


def _final_days(final_hours: int) -> int:
    """BR-PAY-017's *"48h"* in whole days, rounded UP.

    Up, not down: 48 hours before a cut is 2 days, and rounding a 36-hour
    setting DOWN to one day would post the certified letter later than the
    tenant's own policy allows. The unsafe direction is the one that has to be
    typed (hard-won law 3).
    """
    return max(1, -(-final_hours // 24))


def next_rung(current: str | None) -> str | None:
    """The rung after `current`, or None at the end of the ladder.

    The end of the ladder is NOT a drop-off. BR-PAY-016 as amended (PO
    2026-08-11, *"nodrop we chase for payments until write off"*) means an
    account that has had the certified final notice is still chased — by a
    human, through a write-off decision (US-PAY-012), which is the one act with
    a person on it. This function returning None says *the automatic sequence is
    exhausted*, never *stop chasing*.
    """
    if current is None:
        return LADDER_RUNGS[0]
    index = LADDER_RUNGS.index(current)
    if index + 1 >= len(LADDER_RUNGS):
        return None
    return LADDER_RUNGS[index + 1]


def decide(
    *,
    account_id: Any,
    as_of: date,
    balance: Decimal,
    oldest_due_on: date | None,
    balance_floor: Decimal,
    partial_pause_percent: Decimal | None,
    paid_recently: Decimal = ZERO,
    medical_hold: bool = False,
    current_rung: str | None = None,
    last_notice_on: date | None = None,
    reminder_days: int = 3,
    tier_days: tuple[int, ...] = (10, 5),
    final_hours: int = 48,
) -> LadderDecision:
    """PURE. Which rung this account is due, or which rule stopped it.

    Nothing here reads a database, a clock or a setting — every figure arrives
    as an argument, so the same decision can be previewed on a screen and taken
    by a job and the two can never disagree (the discipline `allocation.py`
    uses for the same reason).

    The order of the tests is the order of the rulings' own priority and it is
    not arbitrary: the FLOOR comes first because a $2.40 debt must not even be
    evaluated against a plan or a hold, and the plan pause comes before the
    partial-payment test because a customer on a current plan is not "partially
    paying" — they are paying exactly what they agreed.

    ⚠ **`last_notice_on` IS TESTED LAST, DELIBERATELY, AND IT IS NOT ONE OF THE
    FIVE (`SKIP_ALREADY_NOTICED_TODAY`).** BR-PAY-017's five ruled stop
    conditions are facts about the CUSTOMER — what they owe, what they agreed,
    what their doctor said — and their order is the rulings' own. The same-day
    guard is a fact about the PASS, so it is tested after all five and never
    masks a ruled reason: an account that is both below the floor and already
    written to today still reports `below_ladder_floor`, which is the durable
    answer a clerk needs.

    **THE COMPARISON IS `>=`, NOT `==`, and that is load-bearing.** `as_of` may
    be BACKDATED — the docstring on `run_ladder` promises *"a job re-run for
    last Tuesday must take last Tuesday's decision"* — and a backdated pass
    against an account that has since climbed a rung would both post a letter to
    a customer who has moved on AND write last Tuesday's date over a newer
    `tier_sent_on` in `_advance`. So any notice dated ON OR AFTER `as_of` stops
    this pass.
    """
    common = {"account_id": str(account_id), "balance": balance}

    if balance <= ZERO:
        return LadderDecision(
            runs=False,
            skip_reason=SKIP_NOTHING_OVERDUE,
            detail="this account owes nothing, so there is nothing to chase. Money POSTED by "
            "the due date settles a bill even if it clears later (BR-PAY-021).",
            **common,
        )

    # 1 · the floor — PO 2026-08-12, OQ-137/OQ-157. STRICT: exactly $25.00 IS
    # chased, the same reading BR-BIL-001's fee half ships.
    if balance < balance_floor:
        return LadderDecision(
            runs=False,
            skip_reason=SKIP_BELOW_FLOOR,
            detail=f"the balance of {balance} is under this utility's collection floor of "
            f"{balance_floor}, so NO rung of the ladder runs — not the reminder, not the "
            "notices, and above all not the certified final letter, which costs about $8.00 to "
            "send. The PO ruled the floor onto the WHOLE ladder on 2026-08-12 (OQ-137) and made "
            "it per-utility on the same day (OQ-157).",
            **common,
        )

    if medical_hold:
        return LadderDecision(
            runs=False,
            skip_reason=SKIP_MEDICAL_HOLD,
            detail="this account is on a medical hold and is excluded from every ladder step "
            "(A15 via BR-CUS-039). The skip is recorded rather than silent.",
            **common,
        )

    if oldest_due_on is None:
        return LadderDecision(
            runs=False,
            skip_reason=SKIP_NOTHING_OVERDUE,
            detail="no unpaid bill on this account carries a due date, so BR-PAY-032's anchor "
            '("today − the oldest unpaid invoice\'s due date") cannot place it. The balance is '
            "real and is reported; the ladder is not run against a date nobody can compute.",
            **common,
        )

    days_late = (as_of - oldest_due_on).days
    common["days_late"] = days_late

    # 4 · the partial payment — PO 2026-08-12, OQ-136.
    if paid_recently > ZERO:
        if partial_pause_percent is None:
            raise PaymentRuleError(
                f"this account paid {paid_recently} against {balance} outstanding, and whether "
                "that pauses the ladder depends on a percentage the Product Owner ruled on "
                "2026-08-12 to be a TENANT SETTING (OQ-136). No percentage was supplied and none "
                "is stored. The PO named 25% and 50% as EXAMPLES, not as the value, so choosing "
                "one here would answer a question they deliberately handed to each utility.",
                br_ref="BR-PAY-016",
            )
        outstanding_before = balance + paid_recently
        share = (paid_recently / outstanding_before) * HUNDRED
        if share >= partial_pause_percent:
            return LadderDecision(
                runs=False,
                skip_reason=SKIP_PARTIAL_PAYMENT,
                detail=f"a partial payment of {paid_recently} against {outstanding_before} "
                f"outstanding is {share.quantize(Decimal('0.1'))}%, at or above this utility's "
                f"{partial_pause_percent}% threshold, so the ladder pauses (PO 2026-08-12, "
                "OQ-136).",
                **common,
            )

    # ── the SAME-DAY guard (hard rule 6) ──────────────────────────────────
    # `last_notice_on` is written by BOTH senders — `ladder._advance` and
    # `notices._advance_tier`, the S35 manual modal's — so this is one letter
    # per account per BUSINESS DAY across the automatic engine and the clerk,
    # which is the property US-PAY-015 TC-4 already asks for per TIER and
    # exception (4) asks for per afternoon.
    if last_notice_on is not None and last_notice_on >= as_of:
        return LadderDecision(
            runs=False,
            skip_reason=SKIP_ALREADY_NOTICED_TODAY,
            detail=f"this account was already written to on {last_notice_on}, so no further "
            f"step is taken on {as_of}. ONE step per account per business day (BR-PAY-017 "
            "as this engine has always described itself, and CLAUDE.md hard rule 6): every "
            "rung's due date is derived from the oldest unpaid bill alone, so an account "
            "long overdue has FOUR rungs past due at once and a second pass would post the "
            "next letter the same afternoon as the last one.",
            **common,
        )

    rung = next_rung(current_rung)
    if rung is None:
        return LadderDecision(
            runs=False,
            skip_reason=SKIP_LADDER_COMPLETE,
            detail="this account has already had the 48-hour certified final notice, so the "
            "automatic sequence is exhausted. That is NOT a drop-off: nobody is dropped (PO "
            "2026-08-11, 'nodrop we chase for payments until write off') and the next act is a "
            "human's — a payment plan, or a write-off with a person's name on it (US-PAY-012).",
            **common,
        )

    due = rung_due_on(
        rung,
        due_on=oldest_due_on,
        reminder_days=reminder_days,
        tier_days=tier_days,
        final_hours=final_hours,
    )
    if as_of < due:
        return LadderDecision(
            runs=False,
            rung=rung,
            skip_reason=SKIP_NOT_DUE_YET,
            next_step_on=due,
            detail=f"the next step ({rung}) falls due on {due} under this tenant's own "
            "intervals; today is earlier. Nothing is sent early.",
            **common,
        )

    return LadderDecision(
        runs=True,
        rung=rung,
        next_step_on=due,
        detail=f"{rung} is due (oldest unpaid bill fell due {oldest_due_on}, {days_late} days "
        "ago) and no rule stops it.",
        **common,
    )


@transaction.atomic
def run_ladder(
    *,
    account_ids: tuple[Any, ...],
    as_of: date,
    actor: Any = None,
    balance_floor: Decimal | None = None,
    partial_pause_percent: Decimal | None = None,
    medical_hold_account_ids: tuple[Any, ...] = (),
    recent_payments: dict[Any, Decimal] | None = None,
    channels: tuple[str, ...] = ("pdf_print",),
    cut_date: date | None = None,
) -> LadderRun:
    """Evaluate the ladder for a selection and take at most ONE step each.

    ONE step per account per pass, deliberately: an account 58 days overdue must
    not receive the reminder, both notices and the certified final letter in one
    afternoon. That is also what makes OQ-133's restart meaningful — a bounced
    cheque puts the customer back at rung 1 and they walk the ladder again, one
    rung at a time, rather than arriving instantly at the certified letter they
    would reach by AGE.

    `as_of` is an argument and never a clock (BR-TEN-043): a job re-run for last
    Tuesday must take last Tuesday's decision.
    """
    floor = settings_seam.ladder_balance_floor() if balance_floor is None else balance_floor
    percent = partial_pause_percent
    reminder_days = settings_seam.reminder_days_after_due()
    tier_days = settings_seam.notice_tier_days()
    final_hours = settings_seam.final_notice_hours()

    positions, problems = billing_seam.outstanding_positions(account_ids=account_ids)
    by_account = {str(position.account_id): position for position in positions}
    held = {str(account_id) for account_id in medical_hold_account_ids}
    paid = {str(key): value for key, value in (recent_payments or {}).items()}

    decisions: list[LadderDecision] = []
    for account_id in account_ids:
        key = str(account_id)
        position = by_account.get(key)
        state = AccountCollectionState.objects.filter(
            tenant_id=_tenant_id(), account_id=account_id
        ).first()

        pause = dunning.collections_pause_for(account_id, as_of=as_of)
        if pause.paused:
            decision = LadderDecision(
                account_id=key,
                runs=False,
                skip_reason=SKIP_PLAN_PAUSED,
                balance=position.balance if position else ZERO,
                detail=pause.detail,
            )
        else:
            decision = decide(
                account_id=account_id,
                as_of=as_of,
                balance=position.balance if position else ZERO,
                oldest_due_on=position.oldest_due_on if position else None,
                balance_floor=floor,
                partial_pause_percent=percent,
                paid_recently=paid.get(key, ZERO),
                medical_hold=key in held,
                current_rung=state.tier if state else None,
                # hard rule 6 — the same-day guard. Read from the SAME state row
                # `_advance` writes below, so a second pass over the same
                # selection on the same `as_of` steps nobody.
                last_notice_on=state.last_notice_on if state else None,
                reminder_days=reminder_days,
                tier_days=tier_days,
                final_hours=final_hours,
            )

        if decision.runs:
            not_taken = _send(
                decision=decision,
                as_of=as_of,
                actor=actor,
                channels=channels,
                cut_date=cut_date,
                account_id=account_id,
            )
            if not_taken is None:
                _advance(account_id, rung=decision.rung, on_date=as_of)
            elif decision.rung == TIER_FRIENDLY and not_taken == notices.SKIP_REMINDER_RULE_OFF:
                # ⚠ `DEF-PAY-10664` — PO 2026-10-29 B4 A, reversing `DEF-PAY-
                # 10651` judgment 4: the utility switched the past-due reminder
                # OFF, so the reminder is SKIPPED and the ladder CARRIES ON. The
                # sender already wrote *Not sent · rule off* to `notice_history`;
                # the account moves to rung 1 WITHOUT a last-notice date (nobody
                # was written to), and the 10-day notice falls due on its own
                # day — `rung_due_on` counts from the due date, never from here.
                # ONLY the deliberate switch-off continues: a reminder that could
                # not go (no contact, no wording, the queue refused) is still not
                # a step taken, and the next run tries again.
                _advance(account_id, rung=decision.rung, on_date=as_of, noticed=False)
                decision = replace(decision, runs=False, skip_reason=not_taken)
            else:
                # ⚠ `DEF-PAY-10651` — NOTHING WAS SENT, SO THE RUNG WAS NOT
                # TAKEN. `_advance` ran here unconditionally, so a reminder that
                # queued nothing (rule off, nobody reachable, no wording) still
                # moved the account on, and the next pass sent the 10-day notice
                # to a customer who had never been reminded. The sender already
                # wrote the reason to `notice_history`; the run reports it as a
                # skip, and the next pass asks again.
                decision = replace(decision, runs=False, skip_reason=not_taken)
        else:
            notices.record_notice(
                account_id=account_id,
                notice_type=(
                    notices.NOTICE_DISCONNECT
                    if decision.rung in (TIER_FIRST_10_DAY, TIER_SECOND_5_DAY, TIER_FINAL_48_HOUR)
                    else notices.NOTICE_REMINDER
                ),
                outcome=notices.OUTCOME_SKIPPED,
                skip_reason=decision.skip_reason,
                on_date=as_of,
                tier=decision.rung,
                detail={"balance": str(decision.balance), "why": decision.detail},
                actor=actor,
            )
        decisions.append(decision)

    core_audit.money_action(
        actor,
        AUDIT_LADDER_STEP,
        "collection_run",
        # NOT `str(as_of)`. `audit_log.entity_id` is a UUIDField, and a date
        # string reaching it raises `ValueError: badly formed hexadecimal UUID
        # string` — so this audit write, the one hard rule 7 demands, CRASHED
        # the whole request with a 500 AFTER the ladder had already stepped the
        # accounts. Found by an end-to-end journey on 2026-08-15; invisible to
        # 2,400 unit tests because only a real Postgres UUIDField refuses it.
        #
        # A collection RUN is not a persisted entity and has no id of its own —
        # it is a sweep over many accounts — so the column is left NULL, which
        # is what it is nullable FOR. The date is not lost: it travels in
        # `after["as_of"]` below, where a date belongs.
        None,
        after={
            "as_of": as_of.isoformat(),
            "accounts": len(account_ids),
            "stepped": [{"account_id": d.account_id, "rung": d.rung} for d in decisions if d.runs],
            "skipped": [
                {"account_id": d.account_id, "reason": d.skip_reason}
                for d in decisions
                if not d.runs
            ],
            "balance_floor": str(floor),
            "job": None if actor is not None else "payments.ladder.run",
        },
    )
    return LadderRun(
        as_of=as_of,
        decisions=tuple(decisions),
        problems=ladder_problems() + tuple(problems),
    )


@dataclass(frozen=True)
class LadderStep:
    """What ONE ladder step did for ONE account — the answer `step_one` returns."""

    account_id: str
    rung: str
    #: True when this call sent the notice and moved the account. False means
    #: payments itself refused, and `skip_reason` says which of its own rules
    #: did — never *nothing happened*.
    stepped: bool
    skip_reason: str | None = None
    tier_from: str | None = None
    tier_to: str | None = None
    queued_message_ids: tuple[str, ...] = ()
    problems: tuple[dict[str, Any], ...] = ()


def step_one(
    *,
    account_id: Any,
    rung: str,
    as_of: date,
    actor: Any = None,
    channels: tuple[str, ...] = ("pdf_print",),
    cut_date: date | None = None,
) -> LadderStep:
    """ONE rung, ONE account: the notice, its history row, and the tier — TOGETHER.

    ⚠⚠ **THIS FUNCTION EXISTS BECAUSE THE LADDER DID NOT CLIMB, AND *WHOSE ACT
    THE TIER ADVANCE IS* IS THE QUESTION IT ANSWERS** (`DEF-RBS-4347`, ruled by
    the `CR-075` wave `N` build lane on 2026-09-07 under CLAUDE.md hard-won law
    13 — ours to decide and write down, not the Product Owner's; the reasoning
    is in `12-governance/02-decision-log.md`).

    **A ladder step is THREE writes and it is ONE act.** The queue row that will
    become the letter, the `notice_history` row that is the regulator's record,
    and the `account_collection_state` row that says which rung this customer is
    on. Runbook 8 was doing only the first — it called `notifications.
    queue_notice` and nothing else — so on wave `M`'s month-long cycle
    `account_collection_state` held **512 rows before and 512 after** and
    `notice_history` held **0 and 0**. Every customer would have received the
    first reminder and then, for ever, nothing: the board never sees them climb,
    and the runbook's own per-record key (which carries the rung) guarantees the
    reminder is never sent twice either. **The ladder would have had exactly one
    rung.**

    **THE RULING: the advance is PAYMENTS', and it happens in the same call and
    the same transaction as the send.** A runbook that wrote
    `account_collection_state` itself would be a second writer of `BR-PAY-017`'s
    own state, living in a module payments' reviewers never read — and the
    manual S35 modals and the automatic engine deliberately share ONE state row
    so *"no double-send"* is possible at all (`US-PAY-015` TC-4). A third writer
    breaks that by arithmetic, not by accident. So the runbook decides **WHO**
    and **WHEN**; payments decides **WHETHER**, and does the whole act.

    ⚠ **PAYMENTS KEEPS ITS VETO AND THAT IS THE POINT OF THE SHAPE.** The rung
    arrives as an argument — it is payments' own board's answer, read back
    through `collections_read.ladder_board` — but this re-asks payments' two
    conditions that can have changed since the plan was drawn: an active,
    current payment plan (`BR-CUS-043`) and *this tier has already been sent*
    (`US-PAY-015` TC-4). A caller cannot talk payments into a step payments
    refuses; it can only ask.

    ⚠ **NOT A SECOND SENDING PATH.** It calls `notices.send_reminders` /
    `notices.send_disconnect_notices` — the same two functions the S35 modals
    and `run_ladder` use — for exactly the reason `_send` below already gives:
    two senders would be two places for the certified-mail rule to be applied,
    or forgotten. `_advance` is likewise the one `run_ladder` calls.

    ⚠ **ONE TRANSACTION, so a notice can never be queued without its history row
    or without the tier moving.** The three writes are the act; two of them
    landing is a customer who was written to and whom the board will write to
    again tomorrow.

    `as_of` is an ARGUMENT and never a clock (`BR-TEN-043`, gate `G6`).
    """
    if rung not in LADDER_RUNGS:
        raise PaymentRuleError(
            f"unknown ladder rung {rung!r}; BR-PAY-017 names {', '.join(LADDER_RUNGS)}. "
            "A rung this module does not recognise would advance the account to a state "
            "`decide` can never step out of.",
            br_ref="BR-PAY-017",
        )
    before = AccountCollectionState.objects.filter(
        tenant_id=_tenant_id(), account_id=account_id
    ).first()
    tier_from = before.tier if before else None
    with transaction.atomic():
        if rung == TIER_FRIENDLY:
            # `DEF-PAY-10651` — the reminder's channels are the Settings rule's
            # and the customer's, never `channels` (see `send_reminders`).
            result = notices.send_reminders(
                account_ids=(account_id,),
                on_date=as_of,
                actor=actor,
            )
        else:
            result = notices.send_disconnect_notices(
                account_ids=(account_id,),
                tier=rung,
                cut_date=cut_date or (as_of + timedelta(days=10)),
                on_date=as_of,
                channels=channels,
                actor=actor,
            )
        if result.skipped:
            # Payments refused its own step. Nothing is advanced — the account
            # stays where it is, and `notice_history` already carries the skip
            # row `send_*` wrote, so the refusal is on the account rather than
            # only in this return value.
            return LadderStep(
                account_id=str(account_id),
                rung=rung,
                stepped=False,
                skip_reason=result.skipped[0].skip_reason,
                tier_from=tier_from,
                tier_to=tier_from,
                problems=tuple(result.problems),
            )
        # ⚠ `send_disconnect_notices` advances the tier itself and
        # `send_reminders` does not, which is why `run_ladder` calls `_advance`
        # after BOTH. `_advance` is an `update_or_create` on the one state row,
        # so calling it after a sender that already moved the tier writes the
        # same values again rather than a second row.
        _advance(account_id, rung=rung, on_date=as_of)
    return LadderStep(
        account_id=str(account_id),
        rung=rung,
        stepped=True,
        tier_from=tier_from,
        tier_to=rung,
        queued_message_ids=tuple(
            message_id for outcome in result.sent for message_id in outcome.queued_message_ids
        ),
        problems=tuple(result.problems),
    )


def _send(
    *,
    decision: LadderDecision,
    as_of: date,
    actor: Any,
    channels: tuple[str, ...],
    cut_date: date | None,
    account_id: Any,
) -> str | None:
    """One rung, through the SAME bulk senders the S35 modals use.

    Not a second sending path, deliberately: US-PAY-015 TC-4 dedupes a tier
    across the manual modal and this engine, and two senders would be two places
    for the certified-mail rule (A19 rule 3) to be applied — or forgotten.

    ⚠ **RETURNS WHY THE RUNG WAS NOT TAKEN, OR None WHEN IT WAS
    (`DEF-PAY-10651`).** It returned nothing and `run_ladder` advanced the
    account whatever happened. A sender that sent nothing reports the account
    in `skipped`, with the reason it already wrote to `notice_history`; that
    reason comes back here so the account stays on its rung — the same reading
    `step_one` has always made of `result.skipped`.

    ⚠ **EXCEPT `rule_off` ON THE REMINDER (`DEF-PAY-10664`, PO 2026-10-29 B4
    A)** — `run_ladder` reads that one as *skip the reminder and carry on*.
    `step_one` (a clerk's own *Send reminder*) still reports it as not sent.
    """
    if decision.rung == TIER_FRIENDLY:
        # The reminder's channels are the Settings rule's and the customer's
        # (`send_reminders`), so `channels` is not passed.
        result = notices.send_reminders(
            account_ids=(account_id,),
            on_date=as_of,
            actor=actor,
        )
        return result.skipped[0].skip_reason if result.skipped else None
    result = notices.send_disconnect_notices(
        account_ids=(account_id,),
        tier=decision.rung,
        cut_date=cut_date or (as_of + timedelta(days=10)),
        on_date=as_of,
        channels=channels,
        actor=actor,
    )
    return result.skipped[0].skip_reason if result.skipped else None


def _advance(account_id: Any, *, rung: str, on_date: date, noticed: bool = True) -> None:
    """Move the account's collection state to the rung just sent.

    ONE state row per account (r12 #7) shared with the manual modals, which is
    what makes US-PAY-015 TC-4's *"no double-send"* possible: two states — one
    for staff, one for the job — would send the 5-day notice twice to the
    customer who complained about the first one.

    `noticed=False` is the ONE rung passed without writing to anybody — the
    past-due reminder with its rule switched off (`DEF-PAY-10664`). The tier
    moves; `last_notice_on` does not, because the account screen prints it as
    the day the customer was last written to, and nobody was.
    """
    defaults = {
        "tier": rung,
        "tier_sent_on": on_date,
        "paused_reason": None,
    }
    if noticed:
        defaults["last_notice_on"] = on_date
    AccountCollectionState.objects.update_or_create(
        tenant_id=_tenant_id(),
        account_id=account_id,
        defaults=defaults,
    )


def restart_after_bounce(account_id: Any, *, on_date: date, actor: Any = None) -> None:
    """**RESTART FROM THE BEGINNING** — PO 2026-08-12, closing OQ-133.

    Verbatim: *"Restart from the beginning"*. Worked: a **$1,842.10** bill due
    **6 Jul** was paid by a cheque posted **5 Jul**, so the ladder never ran; the
    cheque bounces three weeks later. The customer gets the **full ladder again,
    first notice onward** — *because the payment that stopped it never existed*.

    Evaluated by AGE instead, that account sits 58 days overdue and its first
    contact after the bounce would be a certified disconnection notice. That is
    the outcome the ruling replaced, and the reason this is a reset rather than
    a recalculation.

    The state row is cleared, never deleted: `notice_history` keeps every notice
    that was already sent, so the trail shows the first walk of the ladder and
    the second one, in order.

    **ITS CALLER, STATED AND TESTED (CR-059 CS-5, 2026-09-01).**
    `reversal.reverse_payment` calls this inside the bounce's own transaction
    when its caller passes `resume_collections=True`. It had NO caller at all
    until that date while two docstrings said it did — see the module docstring
    above, which carries the whole story, and
    `tests/test_cr059_cs5_ladder_restart.py`, which fails when the claim and the
    call part company. The audit row below is therefore written inside the
    reversal's transaction: a reset recorded for a bounce that then rolled back
    would put a customer back on rung 1 for money that never came back.
    """
    AccountCollectionState.objects.update_or_create(
        tenant_id=_tenant_id(),
        account_id=account_id,
        defaults={
            "tier": None,
            "tier_sent_on": None,
            "next_step_due": None,
            "paused_reason": None,
        },
    )
    core_audit.money_action(
        actor,
        AUDIT_LADDER_RESTART,
        "account",
        str(account_id),
        after={
            "on_date": on_date.isoformat(),
            "tier": None,
            # The PO ruled this on 2026-08-12 (OQ-133); the ruling belongs in
            # this comment and not in a sentence S61 shows a clerk (DEF-2377).
            "why": "the payment that stopped the ladder was reversed, so the ladder "
            "restarts at rung 1.",
            "job": None if actor is not None else "payments.ladder.restart_after_bounce",
        },
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-014@3c9f5a1 (sha1[:7] of the sources this slice was authored from, concatenated in order: 04-docs/05-modules/08-payments/06-epics/EP-PAY-04-outstandings-collections.md US-PAY-014 · 04-docs/05-modules/08-payments/02-business-rules.md BR-PAY-016/017/032 · 04-docs/05-modules/08-payments/04-flows.md §7 · 04-docs/05-modules/08-payments/07-pre-session-model.md PE-15 · 08-qa/01-e2e/journeys/J4-collections.md)
# generated: 2026-08-15 by story-coder (payments visible-half lane)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_us_pay_014_ladder.py (the $25.00 floor, the 15.8% partial and the bounce restart were each driven RED before being trusted green — verbatim transcripts in the lane report) · pytest tests -m isolation✔
# exceptions: (1) TWO TENANT SETTINGS THIS ENGINE READS DO NOT EXIST. `ladder_balance_floor_amount` (OQ-137/OQ-157) and `partial_payment_pause_percent` (OQ-136) were both RULED on 2026-08-12 and `apps/tenancy/settings_families.COLLECTIONS` carries neither `Param`; that file belongs to another lane this session, so the two lines are REPORTED verbatim rather than written. `settings_seam` REFUSES by name; both figures are ARGUMENTS here so the ruled behaviour is built and asserted meanwhile — BR-BIL-001's own precedent for the same $25.00 (OQ-157's registry row)
#         (2) NOTHING RUNS THIS NIGHTLY. BE-07's job runner registers no collections job; every result carries `no_scheduled_caller`. The S34 screen can drive it over a selection (hard-won law 2 — the absence is on the wire, not only in a docstring)
#         (3) THE LATE-FEE RUNG APPLIES NO FEE. BR-BIL-001/008 own it and payments never writes a charge line (BR-BIL-007); the step is CITED so the sequence reads correctly. Carried as `late_fee_step_is_billings` on every result
#         (4) ONE STEP PER ACCOUNT PER PASS. An account 58 days overdue must not receive four notices in one afternoon, and it is what makes OQ-133's restart mean anything
#         (5) MEDICAL HOLD IS PASSED IN, never inferred — `apps/customers` publishes no medical-hold selector and a clinical fact does not belong in this module (the posture `notices.py` already takes)
#         (6) A PARTIAL PAYMENT WITH NO THRESHOLD SUPPLIED RAISES rather than defaulting to 25% or 50%. The PO named both as EXAMPLES; picking one would answer a question they handed to each utility
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
