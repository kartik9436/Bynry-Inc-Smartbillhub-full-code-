# ── Trace ──────────────────────────────────────────────
# Story:    CR-052 wave W0 task 1 — *"raise the final metered bill for the
#           period start up to and including the cut day, settle, write the
#           status, and leave any remainder outstanding"*   Screens: S90
# Rule:     **PO ruling 2026-08-30 — THE DISCONNECT IS THE WHOLE EVENT.**
#           Verbatim: *"when we disconnect - we generate final bill at that time
#           itself - so later bill is not required ... entire workflow including
#           all settlement and status update is taken care at time of disconnect
#           or move out - so account status changes and outstanding is pending
#           on account if any"*. Closes `OQ-1170`.
# Rules:    BR-CUS-103 (PO 2026-08-25, OQ-380 — *"a service is billed base right
#           up to the moment it is cut, because until then it was available"*) ·
#           BR-CUS-107 (a cut account gets the sixth status, `Disconnected`,
#           class `non_billable`) · `DSC-02.4` (a cut *"leaves the account
#           open"* and is *"not a move-out"*) · BR-BIL-005 (idempotency —
#           cutting twice must not bill twice) · BR-BIL-004 (an issued bill is
#           immutable) · BR-BIL-024/CR-029 D8③ (a cycle-less bill takes its
#           terms from the caller) · BR-BIL-026 (the template pin at issue) ·
#           BR-TEN-043 / G6 (no clock on a money path) · B4.3 ❄️ (calendar-day
#           proration, `service_days / cycle_days`) · CLAUDE.md rule 2 (money
#           4dp) · rule 4 · rule 5 · rule 6 · rule 7
# Tests:    06-backend/tests/test_cr052_w0_disconnected_at_the_cut.py
# Impacts:  apps/billing/services (publishes `raise_and_issue_cut_bill`) ·
#           apps/customers/seams.raise_and_issue_cut_bill (the SEAM) ·
#           apps/customers/disconnects.commit_cut (the only caller)
# ───────────────────────────────────────────────────────
"""The bill a disconnection raises AT the cut. CR-052 W0 task 1's money half.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — AI-authored 2026-08-31 under the PO ruling
of 2026-08-09 (*"AI will do it; we will review it later as human"*). This is a
🔒 money path: it decides what a disconnected customer is billed for the days
they used before the supply went off. A row in
`12-governance/09-human-review-ledger.md` states in plain English what it does
and with which figures ($23.23 and $612.75). Not RATIFIED without a recorded
human sign-off.

⚠ CORRECTED 2026-08-31 — THE PARAGRAPH BELOW IS HISTORY, NOT THE CURRENT STATE.
A glob in 10-scripts/gates/human_owned.txt DOES match this file now: the PO
ruled on 2026-08-31, having been shown all 62 unguarded files in five groups,
that groups one to four go on the watched list — "56 files" in their own words
— and this file is one of them. G7 checks it from that commit. The paragraph is
kept because WHY it went unguarded is worth knowing (DEF-2790: the check
written to catch exactly this looked for the wrong marker for three days), and
nothing below it should be read as describing today.

⚠ **NO GLOB IN `10-scripts/gates/human_owned.txt` MATCHES THIS FILE**, so G7
reports conform over it. A lane may not add itself to that list — the file's own
header calls changing it a process event — so the glob is ASKED FOR in the
review-ledger row. This is the SIXTH time this escape has hit a money path;
`issue.py`, `decisions.py` and `read_analysis.py` each record one of the first
three in that file's own margins.

════════════════════════════════════════════════════════════════════════════
WHY THIS FILE EXISTS, AND WHY IT IS IN **BILLING** AND NOT IN **CUSTOMERS**
════════════════════════════════════════════════════════════════════════════
`apps/customers/disconnects.commit_cut` is the act. Raising a bill is billing's
and only billing's: customers may not write a financial table (BR-CUS-037), only
the ledger posting service writes journal lines (CLAUDE.md rule 5), and a
cross-module write is forbidden outright (B1 / B2 §2). So the cut ASKS, through
a published seam, exactly as it already asks for the $75.00 reconnection fee —
`apps/billing/fee_bill.py` is the precedent and this file is its twin for the
metered half.

════════════════════════════════════════════════════════════════════════════
IT IS PRICED BY THE SAME ENGINE AS EVERY OTHER BILL. THERE IS NO SECOND PATH.
════════════════════════════════════════════════════════════════════════════
**PO 2026-08-30:** *"when you build billing logic ensue you use r1 to r7 that we
build and wire it"*, and CR-051's second hard rule spells out what that forbids.
So this module contains **no arithmetic at all**. It calls
`single.prepare_single_bill` → `single.calculate_single_bill` — the same two
calls a cycle run makes, through `runs.calculate_account`, through stages 1→6 —
and then `issue.issue_invoice`. It adds no narrowing logic to `gather.py`, it
prices nothing from a `ShadowOutcome`, and it reads no ❄️ FROZEN figure, so
`10-scripts/03-golden-verify.py` is 33 PASS / 0 FAIL before and after.

The document is typed **`cycle`**, and that is `one_time.KIND_INTERIM`'s own
reasoning applied unchanged: *"an ordinary bill over an unusual window, so the
DOCUMENT is typed `cycle`: nothing about its lines differs, and typing it
otherwise would mislabel a document kept for seven years."*

⛔ **IT IS NOT TYPED `final`, AND THAT IS `DSC-02.4` AND NOT A PREFERENCE.** A
`final` bill is the bill of a tenancy ENDING: `final_bill.settle_final_bill`
refuses any other type by name and applies the deposit and its interest against
the whole closing position (BR-BIL-013). `DSC-02.4` forbids exactly that at a
cut — *"Close the account or settle the deposit — that is a move-out, not a
disconnect"* — and the PO's ruling of 2026-08-30 is explicit that the cut
*"leaves the account open"*. Typing this `final` would put a second `final` bill
on one tenancy and hand a cut customer's deposit to a settlement nobody asked
for.

════════════════════════════════════════════════════════════════════════════
THE WINDOW: WHERE IT STARTS, WHERE IT ENDS, AND WHAT DIVIDES THE BASE CHARGE
════════════════════════════════════════════════════════════════════════════
**It ENDS on `cut_on`, inclusive.** BR-CUS-103: *"the boundary is the cut date,
not the notice date — a service is billed base right up to the moment it is cut,
because until then it was available."* That is the same inclusive convention
`final_bill.prepare_final_bill` applies to the move day (BR-CUS-056).

**It STARTS at the first unbilled day**, which is derived and never supplied:
the day after the account's last ISSUED bill's period end, or — when no bill has
ever issued — the account's own `opened_at`. A caller-supplied start would be a
clerk deciding how many days a customer pays for.

**AND THE DENOMINATOR IS THE CYCLE'S LENGTH, NOT THE WINDOW'S.** B4.3 prorates
base by `service_days / cycle_days`, and a window that is short *because the
service was cut* must not shrink the denominator with it — that is
`final_bill.prepare_final_bill`'s own warning (*"defaulting the denominator to
12 would charge a full month's base charge for twelve days"*), and here it is
the difference the PO was shown: on a **$40.00** month, 18 days of 31 is
**$23.23**, and a window-length denominator would charge the whole **$40.00**.

`cycle_days` is therefore the CALLER's, exactly as `due_days` is on
`raise_and_issue_charge_fee`: billing chooses nothing. `commit_cut` reads it
through `apps.customers.seams.billing_period_for_unit`, and when metering cannot
answer that read the absence is REPORTED on the result
(`CUT_BILL_DENOMINATOR_ABSENT`) rather than invented — the same posture
`one_time.ONE_TIME_UNAVAILABLE`'s `partial_window_charges_a_full_base_charge`
already states for every other cycle-less bill (CR-029 D8④, PO 2026-08-23).

════════════════════════════════════════════════════════════════════════════
CUTTING TWICE MUST NOT BILL TWICE — CLAUDE.md HARD RULE 6
════════════════════════════════════════════════════════════════════════════
Two independent guards, and neither is a Python check that a race can lose:

  1. `commit_cut` refuses a case already in state `cut` (`already_cut`), so the
     ordinary replay never reaches this module.
  2. **THE DATABASE.** The run row is minted through
     `one_time.create_one_time_run`, whose `idempotency_key` is
     `core.idempotency.one_time_run_key(account, bill_type, period_start,
     period_end)` and is UNIQUE PER TENANT (`uq_bill_runs_idempotency`). A
     second cut over the same window loses the insert and this module answers
     `already_billed_at_the_cut`, carrying the winning run — **it does not bill
     again and it does not fail the cut**, because a bill that already exists is
     the outcome the caller wanted.

⚠ **AND THAT SECOND GUARD IS WHY EVERYTHING HERE RUNS INSIDE A SAVEPOINT —
CLAUDE.md HARD-WON LAW 14.** `create_one_time_run` catches `IntegrityError` and
re-raises `DuplicateRun`; catching that and CARRYING ON is the exact shape law
14 names. On PostgreSQL a failed statement aborts the whole transaction, so the
cut would then die at COMMIT with `InFailedSqlTransaction` **after** reporting
success — and the suite would never show it, because `config/settings/test.py`
hardcodes in-memory SQLite, which has no aborted-transaction state. The nested
`transaction.atomic()` in `raise_and_issue_cut_bill` is a SAVEPOINT and is the
only construct that makes the continuation lawful. Do not "simplify" it away.

════════════════════════════════════════════════════════════════════════════
IT RETURNS AN OUTCOME. IT DOES NOT DECIDE WHAT THE CUT DOES WITH IT.
════════════════════════════════════════════════════════════════════════════
Three things can truthfully happen, and the caller needs to tell them apart
because the account STATUS turns on which one it was:

  * **`raised`** — an issued bill exists for the days up to the cut.
  * **`nothing_to_bill`** — the last issued bill already covers the cut day.
    There is no money at risk and nothing to raise.
  * **`blocked`** — the engine refused this account (no tariff version in force
    at the service date, no plan, a held period, an unpinnable template …). The
    days are NOT billed.

`commit_cut` writes `Disconnected` on the first two and **refuses to write it on
the third**, because the status is what removes the account from
`customers.selectors.accounts_for_bill_run`. That single rule is the whole of
`OQ-1170`'s money and it is stated once, there, in the module that owns the
account row.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone as dt_timezone
from decimal import Decimal
from typing import Any

from django.db import transaction

from apps.billing import gather, issue, models, one_time, runs, single
from apps.billing.exceptions import BillingRuleError
from core import audit

#: The `invoices.bill_type` a cut bill carries. See the module docstring — an
#: ordinary bill over an unusual window is typed `cycle`, never `final`.
BILL_TYPE_CUT = "cycle"

#: One day. The BR-CUS-103 boundary is INCLUSIVE at both ends — the first
#: unbilled day is the day AFTER the last issued period end, and the last billed
#: day is the cut day itself — so this module steps by a day twice and never
#: writes the literal in an expression.
ONE_DAY = timedelta(days=1)

#: The three outcomes. VALUES, because `commit_cut`, the S90 payload and the
#: audit row all key on them and a fourth spelling would be a fourth behaviour.
CUT_BILL_RAISED = "raised"
CUT_BILL_NOTHING_TO_BILL = "nothing_to_bill"
CUT_BILL_BLOCKED = "blocked"
#: A replay: the run's BR-BIL-005 key was already taken, so the bill exists.
#: Reported distinctly from `raised` so an audit row can tell a first cut from a
#: second attempt, and treated as `raised` by every rule that reads it.
CUT_BILL_ALREADY_BILLED = "already_billed_at_the_cut"

#: The outcomes that mean *the days up to the cut are billed*. `commit_cut` may
#: write `Disconnected` on these and on nothing else.
CUT_BILL_SETTLED_OUTCOMES = (CUT_BILL_RAISED, CUT_BILL_NOTHING_TO_BILL, CUT_BILL_ALREADY_BILLED)

#: ⚠ **THE PRORATION DENOMINATOR THIS MODULE CANNOT READ FOR ITSELF.** B4.3
#: divides by the CYCLE's length and the cut bill's window is shorter than a
#: cycle by construction. `apps.metering.selectors.billing_period_for_unit` is
#: the read that answers it (the contract is written out in
#: `apps/customers/seams.billing_period_for_unit`, and
#: `apps/customers/services.PERIOD_UNAVAILABLE` reports the identical absence
#: for a mid-cycle plan change). Without it the window's own length is the
#: denominator, the factor is 1, and the customer is charged a FULL period's
#: base for a part period — which is `one_time.ONE_TIME_UNAVAILABLE`'s
#: `partial_window_charges_a_full_base_charge`, the behaviour the PO ruled on
#: (CR-029 D8④, 2026-08-23, *"this is not required"*).
#:
#: ✅ **THAT READ IS PUBLISHED SINCE 2026-08-31 AND `DEF-2708` IS CLOSED**, so
#: this now fires only when the CYCLE cannot answer rather than on every cut:
#: a unit on no cycle, a unit on two, or a cycle provisioned before CR-029 that
#: carries no frequency and no first run. `A-11488` cut 18 August on a $40.00
#: monthly base now reads its period as 1–31 August and is billed **$23.23**.
#:
#: **On the PO's own worked case the absence was worth $16.77 of one bill:**
#: `A-11488` owes **$23.23** of a **$40.00** monthly base (18 days of 31) and
#: was charged **$40.00**. Named here so a caller can put the sentence on a
#: screen rather than a customer discovering it on the paper.
CUT_BILL_DENOMINATOR_ABSENT: dict[str, Any] = {
    "code": "cut_bill_prorates_on_the_window_not_the_cycle",
    "br_ref": "B4.3 ❄️ · BR-CUS-103 · CR-029 D8④ (OQ-242 WITHDRAWN) · DEF-2708",
    "detail": "the customer's cycle length could not be read, so B4.3's "
    "`service_days / cycle_days` divides by the BILLED WINDOW and the factor is 1 — a "
    "part-period bill carries a FULL period's base charge. The read that answers it is "
    "`apps.metering.selectors.billing_period_for_unit(unit_id, as_of=…)`; it is published, "
    "so this account's CYCLE is what cannot answer — the unit is on no cycle, or on two, or "
    "its cycle carries no frequency and no first run. On `A-11488`, cut 18 August on a $40.00 "
    "monthly base, that is $40.00 charged where 18 days of 31 is $23.23 — $16.77 too "
    "much, on a bill that foots either way. Usage lines are unaffected: they are priced "
    "on what the meter measured, not on a ratio.",
}


@dataclass(frozen=True)
class CutBill:
    """What the cut learned by asking billing. A RESULT, never a decision.

    `outcome` is one of the four constants above. `invoice_id` and the money are
    present only when a bill exists; `reason`/`detail` only when one does not.
    Every money figure travels with its currency (CLAUDE.md rule 2) and every
    amount is the STORED 4dp value — this module rounds nothing, because it
    computes nothing.
    """

    outcome: str
    period_start: date | None = None
    period_end: date | None = None
    cycle_days: int | None = None
    service_days: int | None = None
    invoice_id: str | None = None
    invoice_no: str | None = None
    bill_run_id: str | None = None
    total: Decimal | None = None
    currency: str | None = None
    reason: str | None = None
    detail: str | None = None
    #: `CUT_BILL_DENOMINATOR_ABSENT` when B4.3's denominator had to fall back to
    #: the window's own length, else None. A stated absence, never a silence.
    unavailable: dict[str, Any] | None = None

    @property
    def billed(self) -> bool:
        """Are the days up to the cut billed — or provably not owed?

        The ONE question `commit_cut` asks of this object, so it is answered
        here rather than by a caller re-listing the outcomes and getting the
        list wrong on the day a fifth one is added.
        """
        return self.outcome in CUT_BILL_SETTLED_OUTCOMES

    def as_payload(self) -> dict[str, Any]:
        """The S90 / audit shape. Dates and money as strings, rule 2 throughout."""
        body: dict[str, Any] = {
            "outcome": self.outcome,
            "billed": self.billed,
            "period_start": None if self.period_start is None else str(self.period_start),
            "period_end": None if self.period_end is None else str(self.period_end),
            "cycle_days": self.cycle_days,
            "service_days": self.service_days,
            "invoice_id": self.invoice_id,
            "invoice_no": self.invoice_no,
            "bill_run_id": self.bill_run_id,
            "total": None if self.total is None else str(self.total),
            "currency": self.currency,
            "reason": self.reason,
            "detail": self.detail,
        }
        if self.unavailable is not None:
            body["unavailable"] = dict(self.unavailable)
        return body


def first_unbilled_day(account_id: Any) -> date:
    """The day the cut bill's window opens — DERIVED, never supplied.

    The day after the account's last ISSUED bill's period end (BR-BIL-004: an
    issued bill is never re-billed), or the account's own `opened_at` when
    nothing has ever issued. Both reads cross the boundary BY NAME through
    `gather._resolve`, which is the idiom every other billing→customers read in
    this app already uses.

    ⚠ **THERE IS NO FALLBACK TO A CLOCK OR TO A CALENDAR.** An account with
    neither an issued bill nor a move-in date is REFUSED: assuming the first of
    the month would bill a customer for days somebody else may already have been
    billed for, and assuming the cut date would bill them for nothing at all.

    ⚠ **A `fee` BILL IS NOT AN ISSUED BILL FOR THIS PURPOSE (`DEF-CUS-6086`,
    2026-09-20).** This read used `selectors.last_issued_invoice_period_end`,
    which counts EVERY issued document. `commit_cut` raises this bill first and
    the $75.00 reconnection fee second, so on a clean cut the fee is harmless —
    but on a cut whose bill was REFUSED the fee lands anyway, dated the cut day,
    and the window can never be opened again: the next attempt answers *"an
    issued bill already covers this account through 2026-09-20"* with
    `billed=True`, over days nobody has billed. On `A-11340` that would have
    written `Disconnected` across **2021-03-15 → 2026-09-20** on the strength of
    a $75.00 fee. `last_issued_service_period_end` asks the same question and
    skips the bill types that cover no service period.

    ⚠ **AND A MIGRATED ACCOUNT'S HISTORY WAS BILLED BY SOMEBODY ELSE
    (`DEF-BIL-6093`, 2026-09-20).** An account brought over at cutover has never
    had an issued bill IN THIS PRODUCT, so this read fell through to `opened_at`
    — the day service began, which on a real utility is years back — and the cut
    then asked the engine to bill every day from then to the cut. **Those days
    are already on the books**: BR-CUS-048/049 migrate them as an opening
    receivable with ONE `as_of` date, and BR-CUS-061's bands are the customer's
    whole position up to it. Billing them again is charging twice for the same
    service.
    ⚠ **IT DID NOT BILL TWICE ONLY BECAUSE THE ENGINE REFUSED FOR A DIFFERENT
    REASON** — *"service 'electric' has no tariff version in force across
    2021-03-15 → 2026-05-31"* — which is luck and not a guard: a tenant whose
    schedules DO cover their own history would have had the whole of it raised
    on top of the migrated arrears. Measured on `brazosbend`: `A-11340` carries
    **$8,240.00** in `d90_plus` `as_of` **2026-09-20** and `opened_at`
    **2021-03-15**; `A-11721` carries **$1,204.50** `as_of` the same day and
    opened **2024-09-20**.
    ⚠ **RULED 2026-09-21, AND THE ORDER OF PREFERENCE IS THE RULE.** This
    paragraph ended *"the LATEST of the two answers wins overall"* until that
    day, which **described something the code below does not do** — it returns
    on the first answer it gets, it takes no maximum — and was hard-won law 1's
    shape on a money path: a comment claiming a guarantee is not the guarantee.
    The PO settled it in their own words: *"you create the bill from last bill
    date - if last bill was generated in feb and data is 28 feb you start the
    bill from 1 mar - for arreras - it is previous balance - bill will anyway
    calculate previous balance and mention it on bill; hence we have accounted
    or all oustanding amount."*

    **SO IT IS PRECEDENCE, IN THE ORDER WRITTEN BELOW, AND NOT A MAXIMUM:**

      1. the day after the last ISSUED bill that covered SERVICE — the PO's
         *"from last bill date"*, and `DEF-CUS-6086` is why a `fee` bill is not
         one;
      2. failing that, the day after the migration's `as_of` — an account
         brought over at cutover has no bill of OURS, and everything before
         that date belongs to the system this one replaced (`DEF-BIL-6093`);
      3. failing that, the account's own move-in date.

    **The two do not contradict**: a migrated account with no bill of ours has
    nothing before the cutover to bill, so (2) is the fallback for exactly the
    case (1) cannot answer. `DEF-BIL-6093`'s fix is NARROWED to that rather than
    kept as *prefer the cutover*.

    ⚠ **AND ARREARS ARE NEVER RE-BILLED, WHICH IS WHAT MAKES (1) SAFE.** The
    outstanding before the window is not billable days — it is **previous
    balance**, stamped onto the bill at issue by
    `issue._stamp_balance_forward` under BR-BIL-160, which reads open prior
    bills **and the migrated opening balance**. So on `A-11340` the window
    covers no day anybody has billed and the **$8,240.00** appears as previous
    balance rather than as five and a half years of billable service. That is
    the PO's own reasoning: *"hence we have accounted or all oustanding
    amount."* `opening_position_for_account` is the owner's own published read —
    the one `issue.py` already prints that line from — so the two can never
    disagree about when the migration stopped.
    """
    from apps.billing import customers_seam
    from apps.billing import selectors as billing_selectors

    billed_through = billing_selectors.last_issued_service_period_end(account_id)
    if billed_through:
        through = (
            billed_through
            if isinstance(billed_through, date)
            else date.fromisoformat(str(billed_through))
        )
        return through + ONE_DAY

    opening = customers_seam.opening_position_for_account(account_id)
    # `buckets` and not `amount`: an account migrated at ZERO was still migrated,
    # and its history still belongs to the old system. A zero amount is a real
    # answer about money and says nothing about which days are covered.
    if opening.buckets and opening.as_of:
        covered_to = (
            opening.as_of
            if isinstance(opening.as_of, date)
            else date.fromisoformat(str(opening.as_of))
        )
        return covered_to + ONE_DAY

    detail = gather._resolve("customers", "account_detail")
    if detail is None:
        raise BillingRuleError(
            "customers has not published account_detail, so the first unbilled day of a "
            "cut account cannot be derived and no window can be opened for its final "
            "bill (CR-052 W0 task 1).",
            br_ref="BR-CUS-103",
        )
    raw = (detail(account_id) or {}).get("opened_at")
    if not raw:
        raise BillingRuleError(
            "this account has no issued bill and records no move-in date, so the first "
            "day its final bill should cover cannot be derived. Nothing is assumed: a "
            "guessed start bills a customer for days that are not theirs, and the cut "
            "date itself would bill them for none of the days they used.",
            br_ref="BR-CUS-103",
        )
    return raw if isinstance(raw, date) else date.fromisoformat(str(raw))


def issue_moment(on_date: date) -> datetime:
    """The cut's own date as an instant — DERIVED, never a clock read.

    `fee_bill.issue_moment`'s reasoning, unchanged and deliberately not imported
    across a module boundary that does not exist: BR-TEN-043 and gate G6 forbid
    a wall clock on a money path, so `issued_at` comes from the date the CALLER
    named for the event. A replay stamps the same moment rather than a new one.
    """
    return datetime.combine(on_date, time.min, tzinfo=dt_timezone.utc)


def raise_and_issue_cut_bill(
    actor: Any,
    *,
    account_id: Any,
    cut_on: date,
    due_days: int,
    cycle_days: int | None = None,
    issued_at: datetime | None = None,
) -> CutBill:
    """**THE DOOR `customers` CALLS AT THE CUT.** One bill, issued, or a reason.

    Everything happens inside ONE SAVEPOINT (see the module docstring, law 14):
    the run row, the draft and the issue either all exist or none of them do, so
    a refusal leaves no orphan run occupying the BR-BIL-005 key that a corrected
    second attempt needs — and, on PostgreSQL, so a caught `DuplicateRun` does
    not leave the CUT's own transaction aborted.

    `due_days` is REQUIRED and billing chooses nothing (CR-029 D8③: a cycle-less
    bill takes its terms from the caller). `cycle_days` is the caller's for the
    reason the module docstring gives; `None` means *nobody could read the
    cycle's length*, and the fallback is stated on the result rather than
    silently applied.

    ⚠ **A BLOCKED ACCOUNT IS AN ANSWER, NOT AN EXCEPTION.** The engine refuses
    an account with no tariff version in force at the service date, no plan, or
    a held period overlapping the window — and every one of those is a real
    configuration problem a human fixes, exactly as it would be on the phase-3
    exception list of a cycle run. Raising here would make the CUT fail on it,
    which would leave a household's supply on because its tariff has no version.
    So the refusal comes back as `blocked` with the engine's own sentence, and
    `commit_cut` declines to write the status — which is what keeps the account
    in the next run and keeps the days billable.
    """
    period_end = cut_on
    try:
        period_start = first_unbilled_day(account_id)
    except BillingRuleError as refusal:
        # ⚠ **A WINDOW THAT CANNOT BE DERIVED IS `blocked`, NOT AN EXCEPTION.**
        # An account with no issued bill and no recorded move-in date has no
        # first unbilled day, and `first_unbilled_day` refuses rather than
        # guessing one. Letting that refusal out of this function would make the
        # CUT itself fail — a household's supply left connected because nobody
        # typed a move-in date — so it comes back as the same `blocked` answer
        # the engine's own refusals do, and `commit_cut` declines to write the
        # status over it. The days stay billable by the ordinary run.
        return CutBill(
            outcome=CUT_BILL_BLOCKED,
            period_end=period_end,
            cycle_days=cycle_days,
            reason="cut_bill_window_not_derivable",
            detail=str(refusal),
        )
    if period_start > period_end:
        # Every day up to the cut is already billed. Nothing is at risk and
        # nothing is raised — BR-BIL-004 forbids re-billing them.
        #
        # ⚠ **TWO DIFFERENT FACTS REACH THIS BRANCH AND THEY GET TWO DIFFERENT
        # SENTENCES (`DEF-BIL-6093`).** It said *"an issued bill already covers
        # this account"* whatever the reason, and on a cutover account that is
        # FALSE: there is no issued bill anywhere, the days were billed by the
        # system this one replaced. A support person reading the first sentence
        # goes looking for a bill that does not exist.
        from apps.billing import customers_seam

        opening = customers_seam.opening_position_for_account(account_id)
        migrated = bool(opening.buckets and opening.as_of)
        if migrated:
            detail = (
                f"this account was migrated at cutover with its position as of "
                f"{period_start - ONE_DAY}, which is on or after the cut date {period_end}, so "
                "every day up to the cut is already on the books as an opening receivable "
                "(BR-CUS-048/049). No bill is raised: billing those days again would charge "
                "the customer twice for service the old system already charged for."
            )
            reason = "covered_by_the_opening_balance_at_cutover"
        else:
            detail = (
                f"an issued bill already covers this account through {period_start - ONE_DAY}, "
                f"which is on or after the cut date {period_end}. There are no unbilled days "
                "before the cut, so no bill is raised (BR-BIL-004 — an issued bill is never "
                "re-billed)."
            )
            reason = "already_billed_through_the_cut_day"
        return CutBill(
            outcome=CUT_BILL_NOTHING_TO_BILL,
            period_start=period_start,
            period_end=period_end,
            reason=reason,
            detail=detail,
        )

    unavailable = None if cycle_days is not None else dict(CUT_BILL_DENOMINATOR_ABSENT)

    try:
        with transaction.atomic():  # SAVEPOINT — CLAUDE.md hard-won law 14
            run = one_time.create_one_time_run(
                account_id=account_id,
                bill_type=BILL_TYPE_CUT,
                period_start=period_start,
                period_end=period_end,
                # BR-BIL-070 — the date the event happened is the bill's date.
                # Not a clock (BR-TEN-043 / G6): the CUT names it.
                bill_date=cut_on,
                due_days=due_days,
                run_by=actor,
                actor=actor,
            )
            prepared = single.prepare_single_bill(
                account_id=account_id,
                period_start=period_start,
                period_end=period_end,
                # BR-RAT-007 prices on the SERVICE date, and for this bill the
                # last day of service IS the cut day (BR-CUS-103).
                service_date=period_end,
                cycle_days=cycle_days,
                bill_type=BILL_TYPE_CUT,
            )
            invoice = single.calculate_single_bill(prepared, bill_run=run, bill_type=BILL_TYPE_CUT)
            data = prepared.ready[0]
            _issue(actor, invoice, issued_at=issued_at or issue_moment(cut_on))
    except runs.DuplicateRun as duplicate:
        # BR-BIL-005 — the window is already billed. The savepoint rolled back,
        # so the winning run below is a COMMITTED row from the earlier act and
        # nothing of this attempt survives.
        return _already_billed(duplicate.original, period_start, period_end)
    except (gather.GatherProblem, BillingRuleError) as refusal:
        return CutBill(
            outcome=CUT_BILL_BLOCKED,
            period_start=period_start,
            period_end=period_end,
            cycle_days=cycle_days,
            reason=str(getattr(refusal, "reason", None) or "cut_bill_refused"),
            detail=str(refusal),
            unavailable=unavailable,
        )

    invoice.refresh_from_db()
    # CLAUDE.md rule 7 — the act that put a figure for the days before the cut
    # against a named customer. Audited HERE as well as by `issue.issue_invoice`
    # because this is the act the PO's ruling created and the one a regulator
    # would ask about: why does this customer have a bill dated the day their
    # supply went off?
    audit.money_action(
        actor,
        "invoice.cut_bill.issued",
        "invoice",
        str(invoice.pk),
        before=None,
        after={
            "bill_run_id": str(run.pk),
            "bill_type": BILL_TYPE_CUT,
            "account_id": str(invoice.account_id),
            "cut_on": cut_on.isoformat(),
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "cycle_days": data.cycle_days,
            "service_days": data.service_days,
            "total": str(invoice.total),
            "currency": invoice.currency,
            "br_ref": "BR-CUS-103 · PO ruling 2026-08-30",
        },
    )
    return CutBill(
        outcome=CUT_BILL_RAISED,
        period_start=period_start,
        period_end=period_end,
        cycle_days=data.cycle_days,
        service_days=data.service_days,
        invoice_id=str(invoice.pk),
        invoice_no=invoice.invoice_no,
        bill_run_id=str(run.pk),
        total=invoice.total,
        currency=invoice.currency,
        unavailable=unavailable,
    )


# ── the two helpers, and no arithmetic below this line ──────────────────────


def _issue(actor: Any, invoice: models.Invoice, *, issued_at: datetime) -> models.Invoice:
    """Issue the drafted cut bill — the act that makes it a RECEIVABLE.

    A thin forwarder, exactly as `fee_bill.issue_charge_fee` is. Issue stamps
    every line's GL account (BR-BIL-010), freezes the document (rule 4) and
    hands the posting to the ledger (rule 5); none of that is re-implemented
    here, which is why this module writes no invoice line of its own.

    ⚠ **THE TEMPLATE PIN IS THE TENANT'S FALLBACK (BR-BIL-025/026), AND THE
    LIMIT IS STATED RATHER THAN HIDDEN.** Billing publishes no read for an
    account's consumer category, so this resolves `consumer_category=None` —
    identical to `fee_bill.issue_charge_fee` and to `api._template_pin_for` for
    a whole run, with the same consequence and the same owed fix (CR-052 task
    12, which resolves the template per account at issue for all of them at
    once).
    """
    from apps.billing import templates_service

    template, version = templates_service.resolve_for(consumer_category=None)
    return issue.issue_invoice(
        invoice,
        issued_at=issued_at,
        template_id=template.pk,
        template_version=version.version_no,
        actor=actor,
    )


def _already_billed(run: models.BillRun, period_start: date, period_end: date) -> CutBill:
    """BR-BIL-005's replay answer, carrying the bill the FIRST cut raised.

    The invoice is looked up rather than assumed: `raise_and_issue_cut_bill`
    mints the run, drafts and issues inside one savepoint, so a committed run
    implies a committed bill — but reporting an invoice id nobody read would be
    a claim, and hard-won law 1 is that a comment claiming a guarantee is not
    the guarantee.
    """
    invoice = models.Invoice.objects.filter(tenant_id=run.tenant_id, bill_run_id=run.pk).first()
    return CutBill(
        outcome=CUT_BILL_ALREADY_BILLED,
        period_start=period_start,
        period_end=period_end,
        invoice_id=None if invoice is None else str(invoice.pk),
        invoice_no=None if invoice is None else invoice.invoice_no,
        bill_run_id=str(run.pk),
        total=None if invoice is None else invoice.total,
        currency=None if invoice is None else invoice.currency,
        reason="already_billed_at_the_cut",
        detail=(
            f"a bill run over {period_start} → {period_end} already exists for this account "
            f"(run {run.pk}, created {run.created_at.isoformat()}). BR-BIL-005 keys a run on "
            "its scope and window, so cutting twice cannot bill twice — the bill the first "
            "cut raised is the bill, and no second one is drafted."
        ),
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-052 W0 task 1 · decision log 2026-08-30 "THE DISCONNECT IS THE
#         WHOLE EVENT" · OQ-1170 (CLOSED) · BR-CUS-103 · BR-CUS-107 · `DSC-02.4`
# generated: 2026-08-31 by the CR-052 W0 lane (claude)
# checklist: A✔ B✔ C✔ D=deferred(no API half — the door is a service, called by
#         customers' own cut endpoint, exactly as `fee_bill.py`'s is)
#         E✔(the cut payload carries the bill and every absence) F✔ G✔
#         H=deferred(PO 2026-08-09 — HUMAN-REVIEW-PENDING)
# gates: ruff✔ black✔ · tests/test_cr052_w0_disconnected_at_the_cut.py
#         PROVED RED: with the `single.calculate_single_bill` call removed,
#         `test_the_days_before_the_cut_are_billed_by_somebody` fails on
#         `outcome == 'blocked'` and the $23.23 base line does not exist —
#         the defect exactly.
# exceptions: (1) the BR-BIL-025 template pin resolves `consumer_category=None`,
#         which is `fee_bill.issue_charge_fee`'s stated limit and CR-052 task
#         12's owed fix, not a new one · (2) `cycle_days` is the CALLER's and a
#         `None` falls back to the window's own length with
#         `CUT_BILL_DENOMINATOR_ABSENT` on the result — the PO-ruled
#         `partial_window_charges_a_full_base_charge` behaviour (CR-029 D8④),
#         reported and not silently applied · (3) a BLOCKED account is an
#         ANSWER, not an exception: the engine's refusals come back as
#         `CutBill(outcome='blocked')` so a cut is never vetoed by a tariff that
#         is unconfigured, and `commit_cut` declines to write the status over it
# status: VERIFIED-UNRATIFIED · HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────
