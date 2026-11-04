# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-015 (the S35 reminder/disconnect position — which tier has
#           already gone, so a manual send never doubles one) · US-PAY-018 (the
#           plan-notice and missed-instalment position) · US-PAY-019 (the
#           dunning + disconnect PAUSE and why it is or is not running) ·
#           US-PAY-014 (the ladder this previews without stepping it)
#           Screens: S34 (the collections board) · S21 (the account's own
#           dunning position)
# Rules:    BR-PAY-017 (the ladder's rungs and the tenant intervals behind
#           them) · BR-PAY-016 as amended (dunning resumes day+1 of a missed
#           instalment; the plan stays active — PO 2026-08-12 OQ-170; the ladder
#           RESTARTS at rung 1 after a bounce — OQ-133; a partial payment pauses
#           only above a tenant-set % — OQ-136) · BR-CUS-043 (pause while active
#           AND current; the pause covers the ARREARS THE PLAN SPREADS, not this
#           month's bill) · BR-PAY-020 (a write-off is initiated in Payments and
#           approved in Finance) · BR-TEN-043 (the business day is an input,
#           never a clock) · CLAUDE.md rule 1 · rule 2
# Tests:    06-backend/tests/test_us_pay_015_019_collections_surface.py
# Impacts:  apps/payments/api.py (GET /collections/ladder · GET
#           /accounts/{id}/collections) · 07-frontend/src/features/payments/
#           CollectionsPage.tsx
# ───────────────────────────────────────────────────────
"""The collections POSITION — read-only, and it steps nothing.

WHY THIS FILE EXISTS. `apps/payments/ladder.py` decides which rung an account is
due and `POST /collections/run` TAKES that step over a selection. There was no
way to LOOK first. A clerk could send the next notice to nine accounts and could
not see, beforehand, which nine they were, which tier each had already had, or
which of them the rules would silently skip — and BR-PAY-017's ladder has five
stop conditions, every one of which is a customer nobody contacted.

So this module answers the two questions the engine could not be asked:

    "Who is at which tier, and what goes next?"   → `ladder_board`
    "Why is this account being chased, or not?"   → `account_position`

════════════════════════════════════════════════════════════════════════════
IT IS A PREVIEW. IT WRITES NOTHING, AND THAT IS LOAD-BEARING
════════════════════════════════════════════════════════════════════════════
`ladder.run_ladder` writes on every path: it sends the notice, advances the
tier, and records a `notice_history` row even for a SKIP (J4 step 2 — every send
AND skip on the trail). A screen that called it to find out what would happen
would have made it happen.

`ladder.decide` is PURE — *"nothing here reads a database, a clock or a
setting"* — so this module gathers the same inputs `run_ladder` gathers, calls
`decide`, and returns the decisions without acting on one. The preview and the
run therefore agree by construction rather than by two implementations of one
rule staying in step.

════════════════════════════════════════════════════════════════════════════
THE TWO FIGURES THE LADDER RUNS ON — READ, NEVER INVENTED
════════════════════════════════════════════════════════════════════════════
BR-PAY-017's ladder needs a **balance floor** (PO 2026-08-12, OQ-137/OQ-157 —
*"Same $25 floor on the whole ladder"*, and *"per utility - uyiliyy can define
it using settings"*) and a **partial-payment pause percentage** (OQ-136 — *"at
least 25% or 50% of outstanding … allow user to set this limit"*).

⚠ **CORRECTED 2026-08-16, hard-won law 1.** `apps/payments/ladder.py` and
EP-PAY-04 §9 both still say these two are *"stored by no tenant setting"* and
that `settings_seam` refuses them. **That stopped being true on 2026-08-15**,
when the DEF-097 lane added both `Param`s to
`apps.tenancy.settings_families.COLLECTIONS`: `ladder_balance_floor_amount`
seeded **25** and `partial_payment_pause_percent` seeded **25**. This module
was written against the stale sentence, and the correction is here rather than
in a report — a comment claiming a guarantee is not the guarantee, and it runs
in the other direction too. The two engine files that still carry the old
wording are REPORTED in the lane report; rewriting another module's docstrings
is not this lane's act.

So the normal path READS them through the seam. What survives, and why:

  · the caller MAY state either (the same door `POST /collections/run` opens),
    which is what a preview of *"what if we set the floor to $50?"* needs;
  · when neither the caller nor the tenant can supply a floor — a tenant whose
    settings are unreadable, which `settings_seam` still refuses by name — the
    board comes back `next_step_available: false` with the reason, and the
    accounts, their balances and the tier already sent all still render.

**AN HONEST "I CANNOT ANSWER THAT" BEATS A REAL-LOOKING NEXT STEP.** A board
that drew "1st notice · due Tue" from a guessed floor would send letters. That
branch is not dead code kept for tidiness: it is the difference between a
screen that degrades and a screen that lies, and it is asserted by its own test.

════════════════════════════════════════════════════════════════════════════
A ZERO IS NEVER "I DON'T KNOW" HERE EITHER
════════════════════════════════════════════════════════════════════════════
`days_late` is None — never 0 — when no unpaid bill carries a due date, which is
`ladder.LadderDecision`'s own rule: *"a bill nobody can place in time cannot be
chased on a schedule anchored to time."* `next_step_on` is None when the ladder
is exhausted, and that is NOT "nothing more happens": BR-PAY-016 as amended (PO
2026-08-11, *"nodrop we chase for payments until write off"*) means the account
is still chased — by a human, through a write-off decision, which is the one act
with a person on it. The board says so in its own field rather than leaving a
blank cell to be read as "done".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from core import errors
from core import tenancy as core_tenancy

from apps.payments import billing_seam, dunning, ladder, notices, plans, settings_seam
from apps.payments.collections_models import AccountCollectionState
from apps.payments.exceptions import PaymentRuleError

ZERO = Decimal("0")


@dataclass(frozen=True)
class _Thresholds:
    """The two figures the ladder cannot run without, and whether we have them.

    A dataclass rather than a tuple so the ABSENCE travels with the values: a
    caller cannot read `floor` without also being handed `available`, which is
    what stops a `floor or 0` appearing anywhere downstream.
    """

    floor: Decimal | None
    percent: Decimal | None
    available: bool
    problems: tuple[dict[str, Any], ...]


def _tenant_id() -> Any:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _thresholds(
    *, balance_floor: Decimal | None, partial_pause_percent: Decimal | None
) -> _Thresholds:
    """The caller's figures, or the tenant's, or an honest refusal.

    The refusal is CAUGHT rather than propagated because a board that 500s is a
    board a clerk cannot use to see who owes money — and the account rows, the
    balances and the tiers already sent are all perfectly answerable without
    either threshold. What is NOT answerable is the NEXT step, and that is the
    part that comes back absent with its reason.
    """
    problems: list[dict[str, Any]] = []
    floor = balance_floor
    if floor is None:
        try:
            floor = settings_seam.ladder_balance_floor()
        except PaymentRuleError as refusal:
            problems.append(
                {
                    "code": "ladder_balance_floor_unset",
                    "br_ref": "BR-PAY-017 · OQ-137 · OQ-157",
                    "detail": str(refusal),
                }
            )
    percent = partial_pause_percent
    if percent is None:
        try:
            percent = settings_seam.partial_pause_percent()
        except PaymentRuleError as refusal:
            problems.append(
                {
                    "code": "partial_pause_percent_unset",
                    "br_ref": "BR-PAY-016 · OQ-136",
                    "detail": str(refusal),
                }
            )
    # The FLOOR is what `decide` cannot run without; the PERCENT is optional on
    # its own signature (None means "no partial-payment pause is configured",
    # which `decide` already handles as its own case). So availability turns on
    # the floor alone, and the percent's absence is reported without blocking a
    # board that is otherwise answerable.
    return _Thresholds(
        floor=floor,
        percent=percent,
        available=floor is not None,
        problems=tuple(problems),
    )


def _accounts_by_id(ids: list[Any]) -> dict[Any, Any]:
    """Account rows through customers' OWN published queryset (B1/BR-TEN-013).

    `outstandings._accounts_by_id` and `reporting._accounts_by_id`'s twin, and
    deliberately the same shape: **no customers model is imported and no ORM of
    theirs is walked.** The read is RESOLVED BY NAME at call time, exactly as
    `billing_seam` resolves billing's invoice queryset — so this is payments
    asking customers a question customers published an answer to, not payments
    reaching into another module's tables. There is no join here and there is
    no cross-module write; B2 §2's interface set is unchanged by it.

    Tenant scoping is customers' own: `account_queryset()` filters on
    `app.tenant_id` itself and RLS FORCE is the second guarantee (hard rule 1),
    which is why this cannot be given a tenant to look at.

    Empty when customers publishes nothing — the board then says "No account
    number" in every row rather than 500ing, because a clerk who cannot see a
    reference can still see who owes what.
    """
    if not ids:
        return {}
    queryset = billing_seam._resolve("customers", "account_queryset")
    if queryset is None:  # pragma: no cover — customers publishes it
        return {}
    return {account.pk: account for account in queryset().filter(pk__in=ids)}


def _account_no(account: Any) -> str | None:
    """The account's HUMAN-FACING number, or None — never `""`, never the id.

    ⚠ **B14 rule 31 (RATIFIED 2026-08-30, PO: *"no Databse ID on screen - that
    is a rule"*).** Until CR-059 this board served only `account_id`, so
    `CollectionsPage` had nothing to print but a uuid and printed one:
    `01a046dd-d809-7e20-81a3-87b1eddc1b64` stood in the ACCOUNT column while the
    Outstandings tab one click away showed `AC-2026-00048` for the same
    customer. The screen could not fix that by itself — the number was not on
    the wire.

    ⚠ **AND BLANK IS NOT NULL.** `customers.Account.account_no` is a
    `TextField()`, so an account nobody has numbered holds `""` and not NULL —
    `customers/models.py` says so beside the CR-046 constraint: *"under the
    2026-08-27 ruling `account_no` is blank on every row"* for an imported book
    of accounts. `""` would slip past the screen's `?? "No account number"`
    fallback and draw an EMPTY CELL, which rule 31 forbids in the same sentence
    as the id — *"where neither exists, the field says so in words"*. So the
    normalisation is HERE, once, where every reader of the board gets it,
    rather than in each surface that renders one.
    """
    number = getattr(account, "account_no", None)
    if number is None:
        return None
    number = str(number).strip()
    return number or None


def _intervals() -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    """The tenant's own reminder/tier/final intervals, or the reason they are not.

    Read through the seam, never as constants: BR-PAY-017 ratifies the SEQUENCE
    and the tenant ratifies the NUMBERS, so a screen that hardcoded 3/10/5/48
    would show one utility another's policy.
    """
    try:
        return (
            {
                "reminder_days": settings_seam.reminder_days_after_due(),
                "tier_days": list(settings_seam.notice_tier_days()),
                "final_hours": settings_seam.final_notice_hours(),
            },
            (),
        )
    except PaymentRuleError as refusal:
        return (
            {},
            (
                {
                    "code": "ladder_intervals_unreadable",
                    "br_ref": "BR-PAY-017",
                    "detail": str(refusal),
                },
            ),
        )


def ladder_board(
    *,
    as_of: date,
    account_ids: tuple[Any, ...] | None = None,
    balance_floor: Decimal | None = None,
    partial_pause_percent: Decimal | None = None,
    medical_hold_account_ids: tuple[Any, ...] = (),
) -> dict[str, Any]:
    """WHO IS AT WHICH TIER, AND WHAT GOES NEXT — without stepping the ladder.

    The rows are every account with an outstanding position (billing's own
    read), each carrying:

      `current_tier`   the rung already sent, from `account_collection_state`
      `tier_sent_on`   when it went — US-PAY-015 TC-4's *"tier already sent
                       Jul 30"*, which is what stops a manual send doubling one
      `next_rung`      what the ladder would do next, from `ladder.decide`
      `next_step_on`   the day it falls due
      `runs`/`skip_reason`  whether it would actually happen today, and which of
                       BR-PAY-017's five stop conditions would prevent it

    `as_of` is REQUIRED and is the caller's business day (BR-TEN-043). Nothing
    here reads a clock, so the board a clerk previews on Monday for Tuesday is
    Tuesday's board.
    """
    tenant_id = _tenant_id()
    thresholds = _thresholds(
        balance_floor=balance_floor, partial_pause_percent=partial_pause_percent
    )
    intervals, interval_problems = _intervals()
    positions, seam_problems = billing_seam.outstanding_positions(account_ids=account_ids)
    held = {str(account_id) for account_id in medical_hold_account_ids}

    position_ids = [position.account_id for position in positions]
    states = {
        str(state.account_id): state
        for state in AccountCollectionState.objects.filter(
            tenant_id=tenant_id,
            account_id__in=position_ids,
        )
    }
    # B14 rule 31 — the board must serve a HUMAN-FACING reference, because a
    # screen can only print what it is given and this one was given a uuid.
    # ONE query for the page, through customers' published queryset; the
    # position list is already bounded by `outstanding_positions`.
    accounts = _accounts_by_id(position_ids)
    # ⛔ **TWO N+1s CLOSED HERE, AND `CLAUDE.md` NAMES NEITHER** (`CR-138-BRC07`
    # `P4.2`). This loop asked `collections_pause_for` once per debtor — one
    # query, two for an account on a plan — and `tenant_currency()` once per
    # ROW, which is three more reads of tenancy's settings each time. Both are
    # now read ONCE for the whole board. Measured on real PostgreSQL 16
    # (`10-scripts/cr138_p4_debtor_cost.py`, median of 3 after a discarded
    # warm-up, 2026-09-23):
    #
    #      2,046 debtors    before   14.503 s ·  12,395 statements
    #                       after     0.601 s ·      20 statements
    #     40,046 debtors    before  285.572 s · 244,195 statements
    #                       after    12.405 s ·      20 statements
    #
    # A web worker is given **sixty** seconds (`docker-entrypoint.sh`), so at
    # the top of the ICP this board took **four and three quarter minutes** —
    # nearly five worker timeouts — to draw one screen.
    #
    # ⚠ **THE BOARD IS STILL UNPAGED AND THAT IS `P4.9`, NOT THIS TASK.** 20
    # statements serve 40,030 rows, so the STATEMENT count no longer grows
    # with the tenant; the ROW count still does, and twelve seconds is the
    # cost of building forty thousand rows nobody asked for. `P4.2` closed
    # the N+1; the page is the screen task and it is HELD.
    #
    # ⚠ The currency is hoisted rather than cached: a per-call cache would be a
    # second place the answer lives, and BR-TEN-042 locks a tenant's currency
    # once a financial record exists — which is exactly what makes one read per
    # BODY correct. A body cannot span two currencies.
    #
    # ⚠ **AND BOTH READS ARE SKIPPED WHEN THERE ARE NO DEBTORS, WHICH IS NOT
    # AN OPTIMISATION.** `tenant_currency()` REFUSES rather than defaulting
    # when tenancy cannot answer (DEF-099), and inside the loop it was reached
    # only when there was a row to put a currency on. Hoisting it
    # unconditionally would turn an EMPTY board on a tenant with unreadable
    # regional settings from *"nobody owes anything"* into a refusal — a
    # behaviour change nobody asked for, hidden inside a performance fix.
    pauses = dunning.collections_pause_for_many(position_ids, as_of=as_of) if positions else {}
    currency = settings_seam.tenant_currency() if positions else None

    rows: list[dict[str, Any]] = []
    for position in positions:
        key = str(position.account_id)
        state = states.get(key)
        pause = pauses[position.account_id]
        row: dict[str, Any] = {
            # `account_id` stays on the wire and is NOT a visible value: it is
            # the row's React key and the account the S21 drill-down opens.
            # B14 rule 31 governs what a utility user can READ, and what they
            # read is `account_no` — or, when there is none, four words saying
            # so. See `_account_no`.
            "account_id": key,
            "account_no": _account_no(accounts.get(position.account_id)),
            "balance": f"{position.balance:.6f}",
            "currency": currency,
            "oldest_due_on": (
                position.oldest_due_on.isoformat() if position.oldest_due_on else None
            ),
            "current_tier": state.tier if state else None,
            "tier_sent_on": (
                state.tier_sent_on.isoformat() if state and state.tier_sent_on else None
            ),
            "last_notice_on": (
                state.last_notice_on.isoformat() if state and state.last_notice_on else None
            ),
            "plan_paused": pause.paused,
            "plan_pause_reason": pause.reason,
            "plan_id": pause.plan_id,
            "medical_hold": key in held,
        }
        if pause.paused:
            # The pause is decided BEFORE the rung, exactly as `run_ladder` does
            # it — a paused account has no "next step", and computing one would
            # print a date for a letter this product will not send.
            row.update(
                {
                    "runs": False,
                    "next_rung": None,
                    "next_step_on": None,
                    "skip_reason": ladder.SKIP_PLAN_PAUSED,
                    "days_late": None,
                    "detail_code": "plan_pause",
                }
            )
        elif not thresholds.available:
            # THE HONEST ABSENCE. The tier already sent is a FACT and is shown;
            # the next step is a computation this deployment cannot make, and it
            # comes back null with `next_step_available: false` rather than as a
            # plausible rung.
            row.update(
                {
                    "runs": None,
                    "next_rung": None,
                    "next_step_on": None,
                    "skip_reason": None,
                    "days_late": None,
                    "detail_code": "thresholds_unset",
                }
            )
        else:
            decision = ladder.decide(
                account_id=position.account_id,
                as_of=as_of,
                balance=position.balance,
                oldest_due_on=position.oldest_due_on,
                balance_floor=thresholds.floor,
                partial_pause_percent=thresholds.percent,
                medical_hold=key in held,
                current_rung=state.tier if state else None,
                # hard rule 6's same-day guard, passed here for the reason this
                # module's own docstring gives for using `decide` at all: the
                # PREVIEW and the SEND must not disagree. A board that offered
                # "next: 10-day notice" on an account already written to today
                # would invite a clerk to press a button that correctly does
                # nothing (CR-059 CS-10, `DEF-3150`).
                last_notice_on=state.last_notice_on if state else None,
                **_decide_intervals(intervals),
            )
            row.update(
                {
                    "runs": decision.runs,
                    "next_rung": decision.rung,
                    "next_step_on": (
                        decision.next_step_on.isoformat() if decision.next_step_on else None
                    ),
                    "skip_reason": decision.skip_reason,
                    "days_late": decision.days_late,
                    "detail_code": "decided",
                }
            )
        rows.append(row)

    # Balance high → low, which is BR-PAY-029's order for every collections list
    # in this product: the biggest debt is the one a clerk works first.
    rows.sort(key=lambda row: Decimal(row["balance"]), reverse=True)
    return {
        "as_of": as_of.isoformat(),
        "rows": rows,
        "rungs": list(ladder.LADDER_RUNGS),
        "next_step_available": thresholds.available,
        "intervals": intervals,
        "tiles": _board_tiles(rows),
        "problems": [
            dict(problem)
            for problem in (
                # CR-059 CS-10 — the `no_scheduled_caller` sentence is dropped
                # only where a scheduled caller is demonstrably live for THIS
                # utility; see `ladder.ladder_problems`.
                ladder.ladder_problems()
                + thresholds.problems
                + interval_problems
                + tuple(seam_problems)
            )
        ],
    }


def _decide_intervals(intervals: dict[str, Any]) -> dict[str, Any]:
    """The interval arguments `decide` takes, or none of them.

    An empty dict lets `decide` use its OWN signature defaults, which are
    BR-PAY-017's ratified 3 / (10, 5) / 48. That is not a guess: it is the rule's
    own numbers, and the branch is only reached when the tenant's settings are
    unreadable — in which case `ladder_intervals_unreadable` is already on the
    body saying so.
    """
    if not intervals:
        return {}
    return {
        "reminder_days": intervals["reminder_days"],
        "tier_days": tuple(intervals["tier_days"]),
        "final_hours": intervals["final_hours"],
    }


def _board_tiles(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """How many accounts sit at each rung — computed over the rows shown.

    A fold over the SAME rows, never a second query, for the reason
    `outstandings.OutstandingsView.ageing` gives: tiles that tie to the list are
    the only tiles worth drawing.
    """
    at_tier: dict[str, int] = {rung: 0 for rung in ladder.LADDER_RUNGS}
    not_started = 0
    for row in rows:
        tier = row["current_tier"]
        if tier in at_tier:
            at_tier[tier] += 1
        else:
            not_started += 1
    return {
        "accounts": len(rows),
        "at_tier": at_tier,
        "not_started": not_started,
        "paused": sum(1 for row in rows if row["plan_paused"]),
        "due_today": sum(1 for row in rows if row["runs"] is True),
    }


def account_position(*, account_id: Any, as_of: date) -> dict[str, Any]:
    """ONE account's dunning position — S21's header, and why it reads that way.

    Four facts a clerk on the phone needs in one place, and every one of them
    read from the surface that OWNS it (the seam pattern, resolved by name at
    call time — DEF-127's lesson):

      the PAUSE       `dunning.collections_pause_for` — including what the pause
                      covers and, just as importantly, what it does NOT (this
                      month's bill is chased normally, PO 2026-08-11)
      the PLAN        `plans.live_plan_for` + its outstanding instalments
      the LADDER      `account_collection_state` — the tier already sent
      the NOTICES     `notices.notice_history_for` — sends AND skips, because an
                      account excluded for a medical hold and one nobody ever
                      chased must never read the same

    Nothing is written and no notice is sent.
    """
    _tenant_id()
    pause = dunning.collections_pause_for(account_id, as_of=as_of)
    state = AccountCollectionState.objects.filter(
        tenant_id=_tenant_id(), account_id=account_id
    ).first()
    plan = plans.live_plan_for(account_id)
    blocked, blocked_detail = dunning.disconnect_blocked(account_id, as_of=as_of)
    return {
        "account_id": str(account_id),
        "as_of": as_of.isoformat(),
        "pause": pause.as_dict(),
        "disconnect_blocked": blocked,
        "disconnect_detail": blocked_detail,
        "late_fee_suspended": dunning.late_fee_suspended_for(account_id, as_of=as_of),
        "plan": _plan_row(plan, as_of=as_of),
        "state": {
            "tier": state.tier if state else None,
            "tier_sent_on": (
                state.tier_sent_on.isoformat() if state and state.tier_sent_on else None
            ),
            "last_notice_on": (
                state.last_notice_on.isoformat() if state and state.last_notice_on else None
            ),
            "next_step_due": (
                state.next_step_due.isoformat() if state and state.next_step_due else None
            ),
        },
        "notices": notices.notice_history_for(account_id=account_id, limit=100),
        "rungs": list(ladder.LADDER_RUNGS),
        "problems": [dict(problem) for problem in ladder.LADDER_UNAVAILABLE],
    }


def _plan_row(plan: Any, *, as_of: date) -> dict[str, Any] | None:
    """The live plan, or None — and None means *there is no plan*, not *unknown*.

    `missed` is the count of instalments due by `as_of` and unmet, which is the
    figure BR-PAY-016 as amended turns on: the day one is missed the pause lifts
    and chasing resumes, with **no grace** (PO 2026-08-12, OQ-170) and with the
    plan STILL ACTIVE — nobody is dropped. The header a screen draws from this is
    *"Active · 1 missed"* with the chase running, which is US-PAY-019 TC-3's own
    corrected wording.
    """
    if plan is None:
        return None
    missed = plans.outstanding_installments(plan, as_of=as_of)
    return {
        "id": str(plan.pk),
        "status": plan.status,
        "missed": len(missed),
        "suspend_late_fees": bool(getattr(plan, "suspend_late_fees", False)),
        "suspend_disconnect": bool(getattr(plan, "suspend_disconnect", False)),
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-019@9d41b60 (sha1[:7] of the sources this slice was authored from, concatenated in order: 04-docs/05-modules/08-payments/06-epics/EP-PAY-05-payment-plans.md — US-PAY-018 §1/§3/§5 + US-PAY-019 §1/§3/§5 — · 04-docs/05-modules/08-payments/06-epics/EP-PAY-04-outstandings-collections.md US-PAY-014/US-PAY-015 · 04-docs/05-modules/08-payments/02-business-rules.md BR-PAY-016/017/020 + BR-CUS-043 · 08-qa/01-e2e/journeys/J4-collections.md; co-packets US-PAY-015, US-PAY-018, same sources)
# generated: 2026-08-16 by story-coder (payments SURFACE lane — the position read a ladder that could only STEP had never had)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — tests/test_us_pay_015_019_collections_surface.py failed with ModuleNotFoundError: No module named 'apps.payments.collections_read' and Resolver404 on /collections/ladder before this file and the routes existed; verbatim in the lane report. ruff✔ black✔ · pytest tests -m isolation✔ · run_gates✔
# exceptions: (1) THIS MODULE WRITES NOTHING. `run_ladder` sends, advances the tier and records a skip row on every path, so a screen that called it to preview would have acted; `decide` is pure and is what this calls, so preview and run agree by construction · (2) the ladder BALANCE FLOOR (OQ-137/OQ-157) and PARTIAL-PAUSE PERCENT (OQ-136) are stored by no tenant setting; neither is invented here. The board serves `next_step_available:false` with both reasons and still shows every account, its balance and the tier already sent — an honest "I cannot say what happens next" over a real-looking rung · (3) `days_late` is null and never 0 when no unpaid bill carries a due date (`ladder.LadderDecision`'s own rule), and an exhausted ladder is reported as exhausted rather than as a blank cell — BR-PAY-016 as amended means the customer is STILL chased, by a human, through a write-off · (4) `_decide_intervals` falls back to `decide`'s signature defaults ONLY when the tenant's settings are unreadable, and the body then carries `ladder_intervals_unreadable` saying so — the defaults are BR-PAY-017's own ratified 3/(10,5)/48, not a guess
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
