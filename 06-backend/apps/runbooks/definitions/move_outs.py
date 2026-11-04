# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-037 (EP-RBS-05) — CR-075 wave R′: runbook 27, *Move-outs and
#           final bills* — six steps over the closing accounts, three read and
#           three write.
# Rules:    BR-RBS-002 · BR-RBS-003 (dry and live are ONE code path) ·
#           BR-RBS-004 (an Action always produces a PLAN first) · BR-RBS-006
#           (a cap REFUSES the run; it never truncates) · BR-RBS-009 (scope
#           resolved ONCE and pinned) · BR-RBS-010 · BR-RBS-011 · BR-RBS-012 ·
#           BR-RBS-015 (the runbook is the audit actor — never a person) ·
#           BR-RBS-018 (a money-bearing action carries a SECOND approval, with
#           NO threshold — `OQ-RBS-1732` CLOSED 2026-09-06) · BR-RBS-019 ·
#           BR-RBS-020 · BR-RBS-021 · BR-RBS-022 · BR-RBS-023 · BR-RBS-027 ·
#           BR-RBS-035 · BR-RBS-039 · BR-CUS-025 / BR-CUS-081 / BR-CUS-082 /
#           BR-CUS-096 (the five money landings — 🔒 human-owned, READ here and
#           never re-derived) · BR-CUS-031 (the final-bill hand-off) ·
#           BR-NOT-005 (a notice is QUEUED; the dispatcher sends) ·
#           BR-NOT-029 (a) (an address is discrete columns, never assembled) ·
#           CLAUDE.md hard rule 2 (money 4 stored / 2 shown, never a float) ·
#           hard rule 4 (issued invoices are append-only) · hard rule 7 (every
#           money action writes `audit_log`) · hard rule 8 (an address lives on
#           `premises`; `kind='mailing'` is the FIRST stated exception) ·
#           hard-won law 2 · law 7 · law 14 · B14 rules 31, 32, 33
# Tests:    06-backend/tests/test_us_rbs_037_move_outs.py ·
#           06-backend/tests/test_rbs_reads_runbooks_pg.py (PostgreSQL only)
# Impacts:  apps/runbooks/definitions/__init__.py (the one line that registers
#           it) · apps/runbooks/seams/customers_seam.py ·
#           apps/runbooks/seams/billing_seam.py ·
#           apps/customers/selectors.py (closing_accounts)
#           · 04-docs/05-modules/17-runbooks/11-catalogue/RB-127-move-outs-and-final-bills.md
# ───────────────────────────────────────────────────────
"""Runbook 27 — **Move-outs**.

Walks every closing account: the closing read due, the final bill issued, the
deposit refunded or carried, the forwarding address captured. *The gap E.ON Next
paid £14.5 million for* — `RB-127`'s own sentence, and the reason a runbook that
finds nothing is still worth running every morning.

⚠ **THE CARD IS RESERVED AND SAYS SO IN ITS OWN WORDS: *"the result screen is
not drawn … until it is drawn, nothing here is a finished definition"*.** So
this file builds the SCOPE, the STEPS and the PARAMETERS the card DOES declare,
composes its result out of the twelve blocks every other runbook uses, and
**invents no screen**. Where the card is silent — its trigger row, its unit of
work, its block list and its port list are all *"Not declared on the contract
coverage table"* — the choice is made here, stated here, and recorded in
`12-governance/02-decision-log.md` rather than left for a reader to infer.

WHO STARTS IT
---------------
The card's `Runs` parameter reads **Daily 07:00** and its trigger row is not
declared at all. This declares **manual and schedule**, which covers the clock
exactly and waits on nothing.

THE ONE THING THIS RUNBOOK MAY NOT DO, AND IT IS THE CARD'S STEP 4
--------------------------------------------------------------------
`RB-127` step 4 reads *"Issue the final bill — through the billing service · the
ordinary bill run path"*. **There is no port that issues a bill, and there will
not be one.** `apps/runbooks/ports/billing_ports.py` says so in as many words:

    ⚠ **THERE IS NO PORT THAT ISSUES A BILL, AND THERE WILL NOT BE.** A runbook
    says what would stop a bill run and hands billing a scope at most; the bill
    run is billing's own act. … it is hard rule 4 read forward, since an issued
    invoice is append-only and a module that could re-run one would be writing
    corrections nobody asked for.

**So step 4 PLANS and hands billing a scope**, exactly as that rule prescribes:
it says which closing accounts are ready to bill, which are held and why, and it
consumes no bill number. That is a divergence from the card's own wording and it
is the safest possible reading of it — *"through the billing service · the
ordinary bill run path"* is satisfied by pointing the ordinary bill run at the
scope, and is NOT satisfied by a second implementation of issuing.

⚠ **AND IT IS NOT A GAP TO BE FILLED LATER BY A FOURTEENTH PORT.** A port that
issued a bill would make hard rule 4 depend on a runbook's good behaviour rather
than on the absence of the capability, which is the whole reason `BR-RBS-002`
removes capabilities instead of forbidding their use.

THE MONEY, AND WHY NONE OF IT IS COMPUTED HERE
------------------------------------------------
`BR-CUS-025` and the four rules around it — `BR-CUS-081` (an excess is
refunded), `BR-CUS-082` (a debt surviving closure is still chased),
`BR-CUS-096` (an open dispute HOLDS the excess), `BR-MET-107` (an unbanked
export credit comes off the final bill first) — are settled, worked and
🔒 human-owned in `apps/customers/move_out_settlement.py`. **This runbook reads
that arithmetic through the seam and re-derives none of it.** A second
implementation of a money decision is two answers that eventually disagree about
one customer, and the one in `customers` is the one a clerk already sees on the
move-out wizard.

⚠ **EVERY FIGURE CROSSES AS A `{stored, display}` PAIR OF STRINGS** — 4 decimals
stored, 2 displayed, never a float (hard rule 2, re-signed 2026-08-22). Nothing
here re-rounds one: rounding happens once, at finalisation, and a second
rounding on a money path is what B4 forbids.

⚠ **AND A SETTLEMENT WITH A GAP STATES NO LANDING.** Billing publishes no
per-account final-bill total, so a run that cannot state one gets
`final_bill_not_stated` and the account is HELD rather than settled against a
bill nobody read. That is `DEF-127`'s fail-closed shape on an account nobody
will look at again: a zero there would refund a customer who still owes.

THE SECOND APPROVAL, WHICH IS NOT OPTIONAL AND HAS NO THRESHOLD
-----------------------------------------------------------------
`BR-RBS-018`, as closed by `OQ-RBS-1732` on 2026-09-06 — PO verbatim, *"every
money action, no threshold"*. `RB-127`'s own guard says *"a refund sits behind
the second approval; a carry-forward does not"*, and both are honoured: the
refund asks `_money_gate.second_approval`, the carry-forward does not, and there
is **no amount anywhere in this file**. The register's own words: *a threshold
parameter is not to be added later without a new ruling.*

EVERY MONEY ACTION WRITES `audit_log`, AND THE ACTOR IS THE RUNBOOK
--------------------------------------------------------------------
Hard rule 7 and `BR-RBS-015`. The two money steps go through
`engine.acts.perform`, which writes the `runbook_run_records` row from the PLAN
before the port is reached and the `audit_log` row afterwards — **including when
the outcome is `planned`**, because *the automation decided to refund this
customer and was held* is exactly the fact a disputing customer asks about six
weeks later. The actor is *"Move-outs, version 1"* and **never a person**: a
runbook borrowing a staff login would make a clerk appear to have personally
refunded 48 deposits at 07:00 on a Monday.

WHAT IT ACTUALLY DOES TODAY
-----------------------------
**Nothing is written.** `raise_refund`, `post_credit` and `queue_notice` are all
BOUND (`CR-075` task `L2`) and `engine.acts.LIVE_ENABLED_RUNBOOKS` is an empty
frozenset for the whole catalogue, so every runbook is handed a writer-less copy
of its ports and each port refuses by name. That is phase 2's dry half — the
risky code runs against real accounts, in production, unable to do anything —
and wave `N` turns the first runbook on.

⚠ **THE PORTS ARE CALLED ANYWAY.** No `if is_bound` branch: `BR-RBS-003` makes
dry and live ONE code path, and a branch would be a second path proving nothing
about the first. So the KPI strip says **To refund** and **To credit** rather
than *Refunded* and *Credited*.

THE ADDRESSES — TWO OF THEM, AND THEY ARE DIFFERENT FACTS
------------------------------------------------------------
CLAUDE.md hard rule 8. The property being left has its address on **`premises`**
and nowhere else, walked to through metering. Where the final bill GOES is
`customers.addresses` at **`kind='mailing'`** — the rule's FIRST stated
exception, *where the BILL goes, which for a landlord is another building* — and
for somebody who has just moved out it is the entire point of asking.

⚠ **`kind='service'` IS RETIRED AND NOTHING HERE ASKS FOR IT.** The selector
reads the mailing kind only and returns `missing` naming the parts it cannot
supply, so *"no forwarding address"* is a finding this runbook REPORTS rather
than a null it swallows — `DEF-CUS-3653` is what an absence costs when nothing
names it, and that one would have returned null on every account forever with
`tsc` and every test green.

⚠ **AND NOTHING HERE ASSEMBLES OR SPLITS AN ADDRESS** (`BR-NOT-029` (a)):
*splitting an address is guessing, and a guessed address is mail delivered to
the wrong house.* The runbook counts which discrete parts are missing and says
so; it never composes one out of what it has.

WHAT WOULD MAKE THIS RUNBOOK REPORT WRONGLY, ANSWERED IN WRITING
-----------------------------------------------------------------
Hard-won law 7's second habit:

* **A run that examined nothing and a run that found every account settled must
  not read the same.** The strip carries the accounts examined; a stopped run
  has no strip at all.
* **A settlement that could not be computed is not a settlement of zero.** Every
  gap the owning module names travels to the screen with its own count in
  `held_by_a_gap`, and the account is HELD.
* **A closed account with no final bill is the point of the backwards window.**
  `already_closed_with_no_bill` is its own figure, because an empty one means
  *the utility is up to date* and its absence would mean nothing at all.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from apps.runbooks import models
from apps.runbooks.boundary import PortNotBound
from apps.runbooks.contract import (
    MODE_PER_RECORD,
    MODE_SET,
    PARAM_ENUM,
    PARAM_REF_SETTING,
    Block,
    Guard,
    Parameter,
    RunbookDefinition,
    Step,
    SubjectRef,
)
from apps.runbooks.definitions import _money_gate
from apps.runbooks.engine import acts
from apps.runbooks.seams import billing_seam, customers_seam, metering_seam

KEY = "move_outs"

# ── what one closing account can turn out to be ───────────────────────────

OUTCOME_SETTLED = "settled"
OUTCOME_TO_REFUND = "to_refund"
OUTCOME_REFUNDED = "refunded"
OUTCOME_TO_CARRY = "to_carry"
OUTCOME_CARRIED = "carried"
OUTCOME_STILL_OWES = "still_owes"
OUTCOME_HELD = "held"
OUTCOME_NOT_READY = "not_ready"

# ── why an account is not ready ───────────────────────────────────────────

ISSUE_NO_CLOSING_READ = "no_closing_read"
ISSUE_ESTIMATED_READ = "estimated_read"
ISSUE_NO_FORWARDING_ADDRESS = "no_forwarding_address"
ISSUE_NO_FINAL_BILL = "no_final_bill"
ISSUE_SETTLEMENT_INCOMPLETE = "settlement_incomplete"
ISSUE_AWAITING_APPROVAL = "awaiting_approval"

#: What a clerk calls each. ⚠ A refusal caps at five or six words (B14 rule 33)
#: and carries no rule id and no database id (rules 31, 32).
ISSUE_LABELS = {
    ISSUE_NO_CLOSING_READ: "No closing read",
    ISSUE_ESTIMATED_READ: "Closing read estimated",
    ISSUE_NO_FORWARDING_ADDRESS: "No forwarding address",
    ISSUE_NO_FINAL_BILL: "Final bill not issued",
    ISSUE_SETTLEMENT_INCOMPLETE: "Deposit cannot be settled",
    ISSUE_AWAITING_APPROVAL: "Waiting for approval",
}

#: `Account.final_read_state`, the three words `CR-038` W9 gave it. `None` is a
#: fourth fact and NOT a fourth value: the close predates the column, or the
#: seam could not answer, or the unit held no meters.
READ_TAKEN = "taken"
READ_DUE = "due"
READ_ESTIMATED = "estimated"

# ── the steps, in the card's own order ────────────────────────────────────

STEP_GATHER = "gather_closing_accounts"
STEP_READ = "check_the_closing_read"
STEP_ADDRESS = "check_the_forwarding_address"
STEP_BILL = "issue_the_final_bill"
STEP_DEPOSIT = "settle_the_deposit"
STEP_NOTICE = "queue_the_final_notice"

STEP_LABELS = {
    STEP_GATHER: "Gather closing accounts",
    STEP_READ: "Check the closing read",
    STEP_ADDRESS: "Check the forwarding address",
    STEP_BILL: "Issue the final bill",
    STEP_DEPOSIT: "Settle the deposit",
    STEP_NOTICE: "Queue the final notice",
}

# ── fix routes ────────────────────────────────────────────────────────────
#
# ⚠ **EVERY ONE IS A PATH THIS PRODUCT ACTUALLY MOUNTS, VERIFIED AGAINST
# `07-frontend/src/App.tsx` ON 2026-09-07.** A fix route resolving to nothing is
# a dead button over a live finding — hard-won law 2's mirror. Tenant-relative:
# the shell prefixes `/:tenant/`.
FIX_ACCOUNTS = "accounts"
FIX_READS = "reads"
FIX_BILLING = "billing"


def _decimal(raw: Any) -> Decimal | None:
    """A money figure as a `Decimal`, or `None`. **Never a float** (hard rule 2).

    The seam hands money across as canonical STRINGS for exactly this reason,
    and `float("296.40")` is where a utility's refunds stop tying out.
    """
    if raw is None or raw == "":
        return None
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError):  # pragma: no cover — the seam quantizes
        return None


def _stored(pair: Any) -> Decimal | None:
    """The 4-decimal half of a `{stored, display}` pair — what arithmetic uses."""
    if not isinstance(pair, dict):
        return _decimal(pair)
    return _decimal(pair.get("stored"))


def _shown(pair: Any) -> str | None:
    """The 2-decimal half — what a screen draws, ROUNDED ONCE by the owner.

    ⚠ **THIS RUNBOOK NEVER ROUNDS.** B4: round only at finalisation and at
    display, and the module that owns the arithmetic has already done both. A
    second rounding here is a second answer.
    """
    if not isinstance(pair, dict):
        return None if pair is None else str(pair)
    return pair.get("display")


@dataclass(frozen=True)
class Closing:
    """One closing account, and what this run decided about it.

    ⚠ **NO FIELD HERE CARRIES A DATABASE ID AS A VISIBLE VALUE** (B14 rule 31).
    `account_id` is the handle the ports need; `account_no`, `customer_name` and
    the walked address are what a clerk reads.

    ⚠ **`amount` IS A DISPLAY STRING AND `amount_stored` IS THE 4-DECIMAL ONE**
    (hard rule 2). Keeping both, named, is what stops a screen drawing the
    stored value or a port being handed the rounded one.
    """

    account_id: str
    account_no: str
    customer_name: str | None
    closed_at: str
    address: str | None
    forwarding_missing: tuple[str, ...]
    read_state: str | None
    landing: str | None
    currency: str
    amount_stored: Decimal | None
    amount: str | None
    outcome: str
    issue: str | None
    reason: str
    decided_by_rule: str
    fix_route: str
    fix_label: str

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("a closing account with no reason says nothing to anybody")
        if self.amount_stored is not None and not self.currency:
            raise ValueError(
                f"account {self.account_no!r} carries an amount and no currency. "
                "CLAUDE.md hard rule 2: money is CHAR(3) currency, always — a figure with no "
                "currency is a number nobody can pay."
            )
        if not self.fix_route.strip():
            raise ValueError(
                f"account {self.account_no!r} names no fix route. BR-RBS-011: a failure names "
                "its fix route, and a failure with no route is a defect in the runbook."
            )

    @property
    def amount_text(self) -> str:
        """The figure a clerk reads — two decimals, with its currency."""
        if self.amount is None:
            return "—"
        return f"{self.amount} {self.currency}"

    def as_row(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "account_no": self.account_no,
            "customer_name": self.customer_name,
            "closed_at": self.closed_at,
            "address": self.address,
            "forwarding_missing": list(self.forwarding_missing),
            "read_state": self.read_state,
            "landing": self.landing,
            "currency": self.currency,
            "amount": self.amount,
            "amount_stored": None if self.amount_stored is None else str(self.amount_stored),
            "outcome": self.outcome,
            "issue": self.issue,
            "reason": self.reason,
            "decided_by_rule": self.decided_by_rule,
            "fix_route": self.fix_route,
            "fix_label": self.fix_label,
        }


@dataclass
class _StepResult:
    """What every set step returns — what it decided, and what it looked at.

    `checked` is not decoration: a step reporting nothing over an empty window
    and a step reporting nothing over a utility with no move-outs are the same
    sentence with very different meanings (hard-won law 7).
    """

    reached: bool = True
    stop: dict[str, Any] | None = None
    plan: list[dict[str, Any]] = field(default_factory=list)
    checked: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "reached": self.reached,
            "plan": list(self.plan),
            "checked": dict(self.checked),
        }
        if self.stop is not None:
            out["stop"] = dict(self.stop)
        return out


# ── reading the run's own context ─────────────────────────────────────────


def _as_of(ctx) -> date:
    """The day this run is FOR — STATED, never read from a clock.

    `BR-TEN-043` and gate `G6`, and here it is load-bearing twice over: the
    window is measured from it AND `BR-CUS-057`'s deposit interest accrues TO
    it. A money path that read `today` would give two answers for one pinned
    scope and two different refunds for one customer.
    """
    stated = ctx.params.get("as_of")
    if isinstance(stated, datetime):
        return stated.date()
    if isinstance(stated, date):
        return stated
    if isinstance(stated, str) and stated:
        try:
            return date.fromisoformat(stated[:10])
        except ValueError:  # pragma: no cover — the validator refuses it first
            pass
    return date(1970, 1, 1)


def _window_days(ctx) -> int:
    return int(ctx.params.get("window_days") or 14)


def _accounts(ctx) -> list[dict[str, Any]]:
    return customers_seam.closing_accounts(as_of=_as_of(ctx), window_days=_window_days(ctx))


def _stopped(ctx) -> dict[str, Any] | None:
    for key in (STEP_GATHER, STEP_BILL):
        result = ctx.set_results.get(key) or {}
        stop = result.get("stop")
        if stop:
            return dict(stop)
    return None


def _never_reached(stop: dict[str, Any]) -> dict[str, Any]:
    return _StepResult(reached=False, checked={"never_reached_because": stop["headline"]}).as_dict()


def _plan(ctx) -> list[dict[str, Any]]:
    """The plan as the LAST step that touched it left it.

    Steps 1 to 4 each rewrite the whole plan rather than annotating rows in
    place, so the plan a later step reads is one object with one author.
    """
    for key in (STEP_BILL, STEP_ADDRESS, STEP_READ, STEP_GATHER):
        result = ctx.set_results.get(key) or {}
        if result.get("reached") and result.get("plan") is not None:
            return list(result["plan"])
    return []


def _cap(ctx) -> int | None:
    """The tenant's own limit, from the runbook row (`RBR-03`)."""
    if ctx.run_id is None:
        return None
    return (
        models.RunbookRun.objects.filter(pk=ctx.run_id)
        .values_list("runbook__cap", flat=True)
        .first()
    )


# ── step 1 · the closing accounts, and the backwards window ───────────────


def step_gather_closing_accounts(ctx, subjects) -> dict[str, Any]:
    """1 · *"And any closed account with no final bill, however old."*

    ⚠ **THE BACKWARDS HALF IS THE POINT OF THE RUNBOOK.** A move-out somebody
    processed in March and never billed is invisible on every screen this
    product has — the account is closed, so it is off the ageing, off the bill
    run and off the ladder — and it is exactly the gap `RB-127` is named after.
    Its count is its own figure on the strip, because an EMPTY one means *the
    utility is up to date* and its absence would mean nothing at all.

    ⚠ **THIS RUNBOOK CANNOT STOP FOR WANT OF A CONNECTION** — it reads the
    utility's own accounts and nothing else — so the only stop it has is the cap
    in step 4. An empty window is a RESULT and not a stop: *no move-outs this
    fortnight* is a good morning, drawn as an empty state with what was examined
    beside it.
    """
    accounts = _accounts(ctx)
    issued = billing_seam.last_issued_bill_dates([one["account_id"] for one in accounts])
    as_of = _as_of(ctx)

    plan: list[dict[str, Any]] = []
    already_closed_no_bill = 0
    for row in accounts:
        closed = date.fromisoformat(row["closed_at"])
        last_bill = issued.get(row["account_id"])
        # A final bill is one issued ON OR AFTER the move-out date. A bill from
        # two months before the close is an ordinary cycle bill and settles
        # nothing — reading it as *the final bill* is how an account closes
        # owing a fortnight nobody billed.
        has_final = last_bill is not None and last_bill >= closed
        backwards = row["already_closed"] and not has_final
        if backwards:
            already_closed_no_bill += 1
        plan.append(
            {
                **row,
                "last_bill_on": None if last_bill is None else last_bill.isoformat(),
                "has_final_bill": has_final,
                "already_closed_with_no_bill": backwards,
                "days_to_move_out": (closed - as_of).days,
            }
        )

    return _StepResult(
        plan=plan,
        checked={
            "closing_accounts": len(plan),
            "window_days": _window_days(ctx),
            "as_of": as_of.isoformat(),
            "closing_ahead": len([one for one in plan if one["days_to_move_out"] >= 0]),
            "already_closed_with_no_bill": already_closed_no_bill,
            "final_bill_already_issued": len([one for one in plan if one["has_final_bill"]]),
            "sample_accounts_guarded": len([one for one in plan if one.get("is_sample")]),
        },
    ).as_dict()


# ── step 2 · the closing read ─────────────────────────────────────────────


def step_check_the_closing_read(ctx, subjects) -> dict[str, Any]:
    """2 · Present, inside the window, or estimated by policy.

    `Account.final_read_state` is the fact `CR-038` W9 added for exactly this:
    `taken` · `due` · `estimated`, derived ONCE at move-out commit from the
    metering read seam and stored beside `closed_at`.

    ⚠ **`None` IS A FOURTH FACT AND NOT A FOURTH VALUE.** It means the close
    predates the column, or the seam could not answer, or the unit held no
    meters — three honest absences, and the column's own docstring refuses to
    invent a fourth value to cover them. This runbook treats `None` the same way
    it treats `due`: **not ready**, because a final bill on an unread meter is a
    bill the customer will dispute.

    ⚠ **AN ESTIMATED READ IS NOT A REFUSAL, IT IS A FLAG.** `B18` §5.6.2 draws
    it amber; the utility's own policy allows it, and holding every estimated
    close would stop a runbook whose whole job is to find the ones nobody
    finished. It is carried on the row and counted.
    """
    stop = _stopped(ctx)
    if stop:
        return _never_reached(stop)

    in_scope = {str(one.subject_id) for one in subjects}
    plan = [one for one in _plan(ctx) if str(one["account_id"]) in in_scope]
    taken = due = estimated = unknown = 0
    out: list[dict[str, Any]] = []
    for row in plan:
        state = row.get("final_read_state")
        if state == READ_TAKEN:
            taken += 1
            issue = None
        elif state == READ_ESTIMATED:
            estimated += 1
            issue = ISSUE_ESTIMATED_READ
        elif state == READ_DUE:
            due += 1
            issue = ISSUE_NO_CLOSING_READ
        else:
            unknown += 1
            issue = ISSUE_NO_CLOSING_READ
        out.append({**row, "read_issue": issue})

    return _StepResult(
        plan=out,
        checked={
            "closing_read_taken": taken,
            "closing_read_due": due,
            "closing_read_estimated": estimated,
            # ⚠ A DECLARED BLIND SPOT WITH A NUMBER ATTACHED (law 7). These are
            # the closes that predate the column or whose unit held no meters,
            # and they are NOT counted as *due* — they are a different fact.
            "closing_read_not_stated": unknown,
        },
    ).as_dict()


# ── step 3 · the forwarding address ───────────────────────────────────────


def step_check_the_forwarding_address(ctx, subjects) -> dict[str, Any]:
    """3 · Captured, standardised — and it is the MAILING address, not a copy.

    ⚠ **HARD RULE 8'S FIRST STATED EXCEPTION.** An address lives on `premises`
    and nowhere else; `customers.addresses` at `kind='mailing'` is not a second
    copy of it but a DIFFERENT FACT — *where the BILL goes* — which for somebody
    who has just moved out is the entire question. The property they left is
    walked to through the premises and drawn beside them.

    ⚠ **`kind='service'` IS RETIRED AND NOTHING HERE ASKS FOR IT.** The owning
    selector reads the mailing kind only and returns `missing` naming the
    discrete parts it cannot supply, and this counts them — so *"no forwarding
    address"* is a finding rather than a null nobody sees (`DEF-CUS-3653`).

    ⚠ **AND NOTHING HERE COMPOSES ONE** (`BR-NOT-029` (a)): *splitting an
    address is guessing, and a guessed address is mail delivered to the wrong
    house.*
    """
    stop = _stopped(ctx)
    if stop:
        return _never_reached(stop)

    plan = _plan(ctx)
    # ⚠ ONE READ FOR THE WHOLE ESTATE'S SERVICE ADDRESSES — the premises is the
    # product's one address home and this is metering's own bulk read of it.
    premises = {
        str(one["premises_id"]): one.get("address_line")
        for one in metering_seam.premises_for_reconciliation(include_sample=True)
    }

    out: list[dict[str, Any]] = []
    captured = missing = 0
    for row in plan:
        forwarding = customers_seam.mailing_address_for_account(row["account_id"]) or {}
        gaps = tuple(str(one) for one in (forwarding.get("missing") or []))
        if gaps:
            missing += 1
        else:
            captured += 1
        out.append(
            {
                **row,
                "address": premises.get(str(row.get("premises_id"))),
                "forwarding_missing": list(gaps),
                "address_issue": ISSUE_NO_FORWARDING_ADDRESS if gaps else None,
            }
        )

    return _StepResult(
        plan=out,
        checked={
            "forwarding_address_captured": captured,
            "forwarding_address_missing": missing,
            "service_addresses_walked": len(
                [one for one in out if one.get("address")]
            ),
            # A property whose premises has no address line at all is a
            # different problem from a customer who gave no forwarding address,
            # and one number cannot say both.
            "no_service_address_on_the_premises": len(
                [one for one in out if not one.get("address")]
            ),
        },
    ).as_dict()


# ── step 4 · the bill this runbook may not issue ──────────────────────────


def step_issue_the_final_bill(ctx, subjects) -> dict[str, Any]:
    """4 · **Hands billing a SCOPE. It does not issue, and it never will.**

    `apps/runbooks/ports/billing_ports.py`, verbatim: *"THERE IS NO PORT THAT
    ISSUES A BILL, AND THERE WILL NOT BE. A runbook says what would stop a bill
    run and hands billing a scope at most; the bill run is billing's own act."*
    That is hard rule 4 read forward — an issued invoice is append-only, and a
    module that could re-run one would be writing corrections nobody asked for.

    So this step says which closing accounts are READY to bill and which are
    held and why, and consumes no bill number. `RB-127`'s own step 4 —
    *"through the billing service · the ordinary bill run path"* — is satisfied
    by pointing the ordinary bill run at that scope, and would NOT be satisfied
    by a second implementation of issuing.

    ⚠ **THE CAP REFUSES THE RUN; IT NEVER TRUNCATES** (`BR-RBS-006`). A run over
    the limit STOPS and says both numbers, because settling the first N deposits
    and dropping the rest is the failure that looks like success.
    """
    stop = _stopped(ctx)
    if stop:
        return _never_reached(stop)

    plan = _plan(ctx)
    out: list[dict[str, Any]] = []
    ready = held = already = 0
    for row in plan:
        blocked = row.get("read_issue") in (ISSUE_NO_CLOSING_READ,)
        if row.get("has_final_bill"):
            already += 1
            state = "already_issued"
        elif blocked:
            held += 1
            state = "held"
        else:
            ready += 1
            state = "ready"
        out.append({**row, "bill_state": state})

    cap = _cap(ctx)
    checked = {
        "ready_to_bill": ready,
        "held_for_a_read": held,
        "final_bill_already_issued": already,
        "bills_issued_by_this_runbook": 0,
        "why_not": (
            "A runbook hands billing a scope; the bill run is billing's own act."
        ),
        "cap": cap,
    }
    if cap is not None and ready > int(cap):
        return _StepResult(
            plan=out,
            stop={
                "headline": "Too many move-outs for one run.",
                "detail": (
                    f"{ready} accounts are ready to bill and the limit is {cap}. "
                    "Nothing has been settled. Raise the limit, or work through the list "
                    "and run this again."
                ),
                "fix_route": FIX_ACCOUNTS,
                "fix_label": "Open accounts",
            },
            checked=checked,
        ).as_dict()
    return _StepResult(plan=out, checked=checked).as_dict()


# ── step 5 · the deposit, which is the money ──────────────────────────────


def _settlement(ctx, row: dict[str, Any]) -> dict[str, Any]:
    """The five landings, READ from the module that owns them. Never re-derived.

    `BR-CUS-025` and the four rules around it are 🔒 human-owned in
    `apps/customers/move_out_settlement.py`, and a second implementation of a
    money decision is two answers that eventually disagree about one customer.
    """
    return customers_seam.move_out_settlement(
        row["account_id"], as_of=_as_of(ctx), final_bill=row.get("final_bill_total")
    )


def _closing(row: dict[str, Any], settlement: dict[str, Any] | None) -> Closing:
    """One plan row as the object that refuses an amount with no currency."""
    verdict = (settlement or {}).get("verdict") or {}
    landing = (settlement or {}).get("landing")
    gaps = list((settlement or {}).get("gaps") or [])
    currency = str((settlement or {}).get("currency") or "USD")
    refund = verdict.get("refund_amount")
    outcome, issue = _decide(row, landing, gaps)
    amount_pair = refund if outcome in (OUTCOME_TO_REFUND, OUTCOME_REFUNDED) else verdict.get("net")
    reason, rule, fix_route, fix_label = _sentence(row, outcome, issue, landing, gaps)
    return Closing(
        account_id=str(row["account_id"]),
        account_no=str(row.get("account_no") or "—"),
        customer_name=row.get("customer_name"),
        closed_at=str(row["closed_at"]),
        address=row.get("address"),
        forwarding_missing=tuple(row.get("forwarding_missing") or ()),
        read_state=row.get("final_read_state"),
        landing=landing,
        currency=currency,
        amount_stored=_stored(amount_pair),
        amount=_shown(amount_pair),
        outcome=outcome,
        issue=issue,
        reason=reason,
        decided_by_rule=rule,
        fix_route=fix_route,
        fix_label=fix_label,
    )


def _decide(row: dict[str, Any], landing: str | None, gaps: list[str]) -> tuple[str, str | None]:
    """What happens to this account, and why not when nothing does.

    The order matters and it is fail-closed: a missing read stops a bill, a
    missing settlement stops the money, and only an account that is complete
    end to end reaches a refund.
    """
    if row.get("read_issue") == ISSUE_NO_CLOSING_READ:
        return OUTCOME_NOT_READY, ISSUE_NO_CLOSING_READ
    if gaps or landing is None:
        # ⚠ **A SETTLEMENT WITH A GAP STATES NO LANDING, AND A ZERO WOULD REFUND
        # A CUSTOMER WHO STILL OWES** (`DEF-127`'s shape). Held, named, counted.
        return OUTCOME_HELD, ISSUE_SETTLEMENT_INCOMPLETE
    if landing == "short":
        return OUTCOME_STILL_OWES, None
    if landing == "settled":
        return OUTCOME_SETTLED, None
    if landing == "refused_other_debt":
        return OUTCOME_TO_CARRY, None
    if landing == "refused_excess":
        return OUTCOME_HELD, ISSUE_SETTLEMENT_INCOMPLETE
    return OUTCOME_TO_REFUND, None


def _sentence(
    row: dict[str, Any], outcome: str, issue: str | None, landing: str | None, gaps: list[str]
) -> tuple[str, str, str, str]:
    """What this account says to a clerk, and the rule that decided it.

    ⚠ **NO RULE ID REACHES A SCREEN** (B14 rule 32) — the rule rides in
    `ReportRow.meta`, which no block draws — and a refusal caps at five or six
    words (rule 33) with the explanation in its own column.
    """
    if outcome == OUTCOME_NOT_READY:
        return (
            "No closing read, so the final bill cannot be raised.",
            "A final bill on an unread meter is a bill the customer will dispute",
            FIX_READS,
            "Take a read →",
        )
    if outcome == OUTCOME_HELD and landing == "refused_excess":
        return (
            "There is an open dispute, so the money is held.",
            "An open dispute holds the excess until it closes",
            FIX_ACCOUNTS,
            "Open account →",
        )
    if outcome == OUTCOME_HELD:
        return (
            "The deposit cannot be settled from what is on file.",
            "A settlement missing a term states no landing and settles nothing",
            FIX_BILLING,
            "Open billing →",
        )
    if outcome == OUTCOME_STILL_OWES:
        return (
            "The deposit did not cover what is owed.",
            "A debt surviving closure is still chased",
            FIX_ACCOUNTS,
            "Open account →",
        )
    if outcome == OUTCOME_TO_CARRY:
        return (
            "Carried to this customer's other account.",
            "An excess goes to a sibling debt before it goes back",
            FIX_ACCOUNTS,
            "Open account →",
        )
    if outcome in (OUTCOME_TO_REFUND, OUTCOME_REFUNDED):
        return (
            "The deposit more than covers the closing balance.",
            "A closing balance the deposit covers is settled and the difference refunded",
            FIX_ACCOUNTS,
            "Open account →",
        )
    return (
        "The deposit settled the closing balance exactly.",
        "The deposit and its interest settle everything outstanding",
        FIX_ACCOUNTS,
        "Open account →",
    )


def step_settle_the_deposit(ctx, subject) -> dict[str, Any]:
    """5 · Refund behind the second approval, or carry forward.

    ⚠ **ONE ACCOUNT, ONE SAVEPOINT** (hard-won law 14). The executor wraps this
    in a nested `transaction.atomic()`, so one refused row rolls back to its own
    savepoint and the rest of the run survives. On PostgreSQL that is the ONLY
    thing that works, and the suite — in-memory SQLite — cannot see the
    difference.

    ⚠ **EVERY MONEY ACTION GOES THROUGH `acts.perform`, WHICH IS WHAT WRITES THE
    AUDIT ROW** (hard rule 7, `BR-RBS-015`). The actor is *"Move-outs, version
    1"* and never a person, and the row is written **even when the outcome is
    `planned`** — *the automation decided to refund this customer and was held*
    is exactly the fact a disputing customer asks about six weeks later.

    ⚠ **THE REFUND CARRIES THE SECOND APPROVAL AND THE CARRY-FORWARD DOES NOT**
    (`RB-127`'s own guard, `BR-RBS-018`). There is **no amount** anywhere in
    this branch: `OQ-RBS-1732` closed on 2026-09-06 with *"every money action, no
    threshold"*, and the register says in as many words that a threshold is not
    to be added later without a new ruling.
    """
    if _stopped(ctx):
        return {
            "outcome": OUTCOME_NOT_READY,
            "reason": "The run stopped before this step.",
            "decided_by_rule": "A step that stops makes every later step Never reached",
            "fix_route": FIX_ACCOUNTS,
        }

    key = str(subject.subject_id)
    row = next((one for one in _plan(ctx) if str(one["account_id"]) == key), None)
    if row is None:
        return {
            "outcome": OUTCOME_NOT_READY,
            "reason": "This account was not in the plan.",
            "decided_by_rule": "The pinned set is resolved once and frozen",
            "fix_route": FIX_ACCOUNTS,
            "data": {},
        }

    settlement = None
    if row.get("read_issue") != ISSUE_NO_CLOSING_READ:
        try:
            settlement = _settlement(ctx, row)
        except Exception as refusal:  # the owning module's own refusal, in its words
            # ⚠ **A SETTLEMENT THE OWNER REFUSES IS A HELD ACCOUNT, NOT A ZERO.**
            # `DEF-047`'s family: a caller that adapts the owner's RESULT but not
            # its REFUSAL. The sentence the owner wrote is what a clerk reads.
            closing = _closing(row, None)
            return {
                "outcome": OUTCOME_HELD,
                "reason": closing.reason,
                "decided_by_rule": str(refusal),
                "fix_route": closing.fix_route,
                "data": closing.as_row(),
            }

    closing = _closing(row, settlement)
    if closing.outcome not in (OUTCOME_TO_REFUND, OUTCOME_TO_CARRY):
        return {
            "outcome": closing.outcome,
            "reason": closing.reason,
            "decided_by_rule": closing.decided_by_rule,
            "fix_route": closing.fix_route,
            "data": closing.as_row(),
        }

    if closing.outcome == OUTCOME_TO_REFUND:
        planned = len(
            [
                one
                for one in _plan(ctx)
                if _closing(one, None).outcome != OUTCOME_NOT_READY
            ]
        )
        approval = _money_gate.second_approval(ctx, planned=planned)
        if not approval["approved"]:
            return {
                "outcome": OUTCOME_HELD,
                "reason": approval["reason"],
                "decided_by_rule": "Every money-bearing action carries a second approval",
                "fix_route": FIX_ACCOUNTS,
                "data": {**closing.as_row(), "issue": ISSUE_AWAITING_APPROVAL},
            }

    port = "raise_refund" if closing.outcome == OUTCOME_TO_REFUND else "post_credit"
    try:
        result = acts.perform(
            ctx,
            acts.ActRequest(
                port=port,
                action_kind=port,
                subject=subject,
                planned_action=(
                    f"Refund {closing.amount_text}"
                    if port == "raise_refund"
                    else f"Carry {closing.amount_text} to the other account"
                ),
                # ⚠ THE MOVE-OUT DATE IS THE DISCRIMINATOR. Read `acts`' own
                # docstring before changing it: leave it out and one customer's
                # deposit can only ever be settled once, ever — including the
                # day they move back in; put the RUN in it and a second firing
                # on the same morning refunds the same deposit twice.
                discriminator=closing.closed_at,
                decided_by_rule=closing.decided_by_rule,
                reason=closing.reason,
                amount=closing.amount_stored,
                currency=closing.currency,
                fix_route=closing.fix_route,
                payload={
                    "actor": acts.actor_for(ctx),
                    "account_id": closing.account_id,
                    # ⚠ THE 4-DECIMAL FIGURE AS A STRING, NEVER THE DISPLAY ONE
                    # AND NEVER A FLOAT (hard rule 2).
                    "amount": None if closing.amount_stored is None else str(closing.amount_stored),
                    "currency": closing.currency,
                },
            ),
        )
    except PortNotBound as refusal:  # pragma: no cover — `acts.act` asks is_bound first
        return {
            "outcome": closing.outcome,
            "reason": closing.reason,
            "decided_by_rule": str(refusal),
            "fix_route": closing.fix_route,
            "data": closing.as_row(),
        }
    done = result.outcome == acts.OUTCOME_DONE
    return {
        "outcome": (
            (OUTCOME_REFUNDED if closing.outcome == OUTCOME_TO_REFUND else OUTCOME_CARRIED)
            if done
            else closing.outcome
        ),
        "reason": closing.reason if done else f"{closing.reason} Nothing has moved yet.",
        "decided_by_rule": closing.decided_by_rule,
        "fix_route": closing.fix_route,
        "data": closing.as_row(),
    }


# ── step 6 · the letter ───────────────────────────────────────────────────


def step_queue_the_final_notice(ctx, subjects) -> dict[str, Any]:
    """6 · Bill and deposit letter · after approval — **queued, never sent**.

    `BR-NOT-005` and `RBR-07`: a notice is WRITTEN to the outbound table and the
    dispatcher sends it. No delivery provider is connected, so the word on every
    screen is **Queued** and never *Sent*.

    ⚠ **AN ACCOUNT WITH NO FORWARDING ADDRESS IS NOT QUEUED, AND THAT IS THE
    WHOLE VALUE OF STEP 3.** Posting a final bill to the property somebody has
    just left is the most reliable way to never be paid, and the address they
    left is the one this product holds most of.
    """
    stop = _stopped(ctx)
    if stop:
        return _never_reached(stop)

    plan = _plan(ctx)
    queued = 0
    no_address = 0
    refusal = ""
    for row in plan:
        closing = _closing(row, None)
        if closing.outcome == OUTCOME_NOT_READY:
            continue
        if row.get("forwarding_missing"):
            no_address += 1
            continue
        try:
            ctx.port("queue_notice").call(
                actor=acts.actor_for(ctx),
                runbook_key=KEY,
                account_id=closing.account_id,
                subject_id=closing.account_id,
                discriminator=f"final_notice|{closing.closed_at}",
                render_context={
                    "account_no": closing.account_no,
                    "closed_at": closing.closed_at,
                    "amount": closing.amount,
                    "currency": closing.currency,
                },
            )
            queued += 1
        except PortNotBound as caught:
            refusal = str(caught)
        except Exception as caught:  # pragma: no cover — a bound writer's own refusal
            refusal = str(caught)

    return _StepResult(
        plan=plan,
        checked={
            "notices_queued": queued,
            "notices_to_queue": len(
                [
                    one
                    for one in plan
                    if not one.get("forwarding_missing")
                    and one.get("read_issue") != ISSUE_NO_CLOSING_READ
                ]
            ),
            "held_for_no_forwarding_address": no_address,
            "why_not": refusal,
            "word_on_the_screen": "Queued — the dispatcher sends, and none is connected",
        },
    ).as_dict()


# ── the report ────────────────────────────────────────────────────────────


def _plan_from_view(view) -> list[dict[str, Any]]:
    for key in (STEP_NOTICE, STEP_BILL, STEP_ADDRESS, STEP_READ, STEP_GATHER):
        result = view.set_results.get(key) or {}
        if result.get("reached") and result.get("plan"):
            return list(result["plan"])
    return []


def _chain(view, stop: dict[str, Any]) -> Block:
    stopped_at = STEP_GATHER
    for key in (STEP_GATHER, STEP_BILL):
        if (view.set_results.get(key) or {}).get("stop"):
            stopped_at = key
            break
    cells = []
    seen_stop = False
    for index, key in enumerate(STEP_LABELS, start=1):
        if key == stopped_at:
            seen_stop = True
            state, note = "bad", stop["headline"]
        elif seen_stop:
            state, note = "notReached", "Never reached"
        else:
            state, note = "good", "Done"
        cells.append(
            {
                "id": key,
                "position": index,
                "label": STEP_LABELS[key],
                "state": state,
                "note": note,
            }
        )
    return Block(
        block="chain",
        payload={
            "label": f"The run stopped at step {[*STEP_LABELS].index(stopped_at) + 1}.",
            "cells": cells,
        },
    )


def _records_columns() -> list[dict[str, Any]]:
    """`RB-127`'s *done looks like*, as columns: every closing account with its
    closing read, its final bill, its deposit and its forwarding address."""
    return [
        {"key": "account", "label": "Account"},
        {"key": "move_out", "label": "Move-out"},
        {"key": "read", "label": "Closing read"},
        {"key": "bill", "label": "Final bill"},
        {"key": "deposit", "label": "Deposit"},
        {"key": "forwarding", "label": "Forwarding address"},
        {"key": "fix", "label": "Fix"},
    ]


def _record_row(index: int, row: dict[str, Any], outcomes: dict[str, str]) -> dict[str, Any]:
    closing = _closing(row, None)
    outcome = outcomes.get(closing.account_id, closing.outcome)
    read = {
        READ_TAKEN: "Taken",
        READ_ESTIMATED: "Estimated",
        READ_DUE: "Due",
    }.get(closing.read_state or "", "Not stated")
    bill = {
        "already_issued": "Issued",
        "ready": "Ready to bill",
        "held": "Waiting for a read",
    }.get(str(row.get("bill_state") or ""), "—")
    deposit = {
        OUTCOME_REFUNDED: f"Refunded {closing.amount_text}",
        OUTCOME_TO_REFUND: f"To refund {closing.amount_text}",
        OUTCOME_CARRIED: "Carried forward",
        OUTCOME_TO_CARRY: "To carry forward",
        OUTCOME_SETTLED: "Settled",
        OUTCOME_STILL_OWES: "Still owes",
        OUTCOME_HELD: "Held",
        OUTCOME_NOT_READY: "—",
    }.get(outcome, "—")
    return {
        "id": f"closing-{index}",
        "cells": {
            # ⚠ THE ACCOUNT NUMBER AND THE CUSTOMER, NEVER A DATABASE ID
            # (B14 rule 31). The service address is walked to from the premises
            # (hard rule 8) and drawn beside them.
            "account": {
                "kind": "text",
                "text": " · ".join(
                    part
                    for part in (closing.account_no, closing.customer_name, closing.address)
                    if part
                ),
            },
            "move_out": {"kind": "text", "text": closing.closed_at},
            "read": {"kind": "text", "text": read},
            "bill": {"kind": "text", "text": bill},
            "deposit": {"kind": "text", "text": deposit},
            "forwarding": {
                "kind": "text",
                "text": "Missing" if closing.forwarding_missing else "Captured",
            },
            "fix": {"kind": "link", "label": closing.fix_label, "to": closing.fix_route},
        },
        "meta": {
            "decided_by_rule": closing.decided_by_rule,
            "outcome": outcome,
            "reason": closing.reason,
            "landing": closing.landing,
        },
    }


def report(view) -> list[Block]:
    """Composed from records and counts at CLOSE, then frozen (`BR-RBS-020`).

    ⚠ **`RB-127`'s RESULT SCREEN IS NOT DRAWN AND THIS INVENTS NONE.** The card
    says so in its own words. What is composed here is the twelve blocks every
    other runbook uses, arranged around the card's *done looks like* sentence —
    *"a clerk sees every closing account with its closing read due, its final
    bill issued or waiting, its deposit refunded or carried, and the forwarding
    address captured"* — which is a table with five facts per row, and that is
    what `Records` draws.

    Two compositions, because a stopped run and a finished one are two states.
    """
    stop = None
    for key in (STEP_GATHER, STEP_BILL):
        stop = (view.set_results.get(key) or {}).get("stop")
        if stop:
            break

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

    plan = _plan_from_view(view)
    gathered = (view.set_results.get(STEP_GATHER) or {}).get("checked") or {}
    reads = (view.set_results.get(STEP_READ) or {}).get("checked") or {}
    addresses = (view.set_results.get(STEP_ADDRESS) or {}).get("checked") or {}
    bills = (view.set_results.get(STEP_BILL) or {}).get("checked") or {}
    notices = (view.set_results.get(STEP_NOTICE) or {}).get("checked") or {}

    outcomes = {str(record.subject.subject_id): record.outcome for record in view.records}
    tally: dict[str, int] = {}
    for outcome in outcomes.values():
        tally[outcome] = tally.get(outcome, 0) + 1
    acted = bool(tally.get(OUTCOME_REFUNDED) or tally.get(OUTCOME_CARRIED))

    settled = tally.get(OUTCOME_SETTLED, 0)
    refunds = tally.get(OUTCOME_TO_REFUND, 0) + tally.get(OUTCOME_REFUNDED, 0)
    carried = tally.get(OUTCOME_TO_CARRY, 0) + tally.get(OUTCOME_CARRIED, 0)
    held = tally.get(OUTCOME_HELD, 0)
    not_ready = tally.get(OUTCOME_NOT_READY, 0)
    refund_word = "Refunds raised" if acted else "Refunds to approve"

    # ⚠ **THE TOTAL IS SUMMED FROM THE 4-DECIMAL HALF AND SHOWN AT 2** (hard
    # rule 2). Summing the display halves would round 48 times and then once
    # more, which is the double-rounding B4 forbids by name. A run whose
    # accounts do not share one currency shows NO total, because a sum across
    # two currencies is not an amount.
    #
    # ⚠ **BOTH READS BELOW WERE `_closing(one, None)` UNTIL 2026-09-24, SO THE
    # TILE READ `0.00 USD` ON EVERY RUN (`DEF-RBS-6467`).** A plan row carries
    # the ACCOUNT; the SETTLEMENT that prices it is fetched one step later and
    # is never written back onto the row. `_closing(row, None)` therefore fell
    # to its own empty-settlement defaults — currency `"USD"` whatever the
    # account is actually in, and no `refund_amount` at all — which made the sum
    # zero and made a run across two currencies look like a run in one. The
    # figures come from the RECORDS instead, where the settled closing was
    # already stored (`closing.as_row()`), so the tile and the table below
    # cannot disagree about one customer's deposit.
    money = [
        (record.data or {})
        for record in view.records
        if record.outcome in (OUTCOME_TO_REFUND, OUTCOME_REFUNDED)
    ]
    currencies = {str(row.get("currency")) for row in money if row.get("currency")}
    refund_total = None
    refund_currency = currencies.pop() if len(currencies) == 1 else None
    if refund_currency:
        refund_total = sum(
            (
                Decimal(str(row["amount_stored"]))
                for row in money
                if row.get("amount_stored") is not None
            ),
            Decimal("0"),
        )

    return [
        Block(
            block="verdict",
            payload={
                "word": refund_word,
                "tone": "warning" if (held or not_ready) else "success",
                "count": (
                    f"{settled} settled · {refunds} {'refunded' if acted else 'to refund'} · "
                    f"{not_ready + held} need you."
                ),
                "detail": (
                    f"{gathered.get('closing_accounts', 0)} closing accounts over "
                    f"{gathered.get('window_days', 14)} days."
                    if acted
                    else "Nothing has moved until a writer is bound for this runbook."
                ),
            },
        ),
        Block(
            block="kpis",
            payload={
                "tiles": [
                    {
                        "id": "settled",
                        "label": "Settled",
                        "value": {"kind": "text", "text": str(settled)},
                    },
                    {
                        "id": "refunds",
                        "label": refund_word,
                        "value": {"kind": "text", "text": str(refunds)},
                        "detail": None if acted else "Planned — nothing has moved yet",
                    },
                    {
                        "id": "carried",
                        "label": "Carried forward",
                        "value": {"kind": "text", "text": str(carried)},
                    },
                    {
                        "id": "refund_total",
                        "label": "Deposit money",
                        "value": {
                            "kind": "money",
                            # ⚠ TWO DECIMALS ON SCREEN, FOUR IN THE SUM, AND
                            # ITS CURRENCY BESIDE IT (hard rule 2).
                            "amount": (
                                None if refund_total is None else str(round(refund_total, 2))
                            ),
                            "currency": refund_currency,
                        },
                        "detail": (
                            None
                            if refund_total is not None
                            else "Not shown: these accounts are in more than one currency"
                        ),
                    },
                    {
                        "id": "not_ready",
                        "label": "Need you",
                        "value": {"kind": "text", "text": str(not_ready + held)},
                        "detail": (
                            f"{reads.get('closing_read_due', 0)} without a read · "
                            f"{addresses.get('forwarding_address_missing', 0)} without an address"
                        ),
                    },
                    # ⚠ **THE BACKWARDS WINDOW IS ITS OWN TILE** — it is the gap
                    # this runbook is named after, and an empty one means the
                    # utility is up to date rather than that nobody looked.
                    {
                        "id": "old",
                        "label": "Closed, never billed",
                        "value": {
                            "kind": "text",
                            "text": str(gathered.get("already_closed_with_no_bill", 0)),
                        },
                        "detail": "However old",
                    },
                ]
            },
        ),
        Block(
            block="breakdown",
            payload={
                "heading": "Where the money landed",
                "columns": [
                    {"key": "landing", "label": "Landing"},
                    {"key": "count", "label": "Count", "numeric": True},
                    {"key": "happened", "label": "What happened"},
                ],
                "rows": [
                    {
                        "id": f"landing-{name}",
                        "cells": {
                            "landing": {
                                "kind": "text",
                                "text": {
                                    OUTCOME_SETTLED: "Settled by the deposit",
                                    OUTCOME_TO_REFUND: "Refund due",
                                    OUTCOME_REFUNDED: "Refund raised",
                                    OUTCOME_TO_CARRY: "Carried to another account",
                                    OUTCOME_CARRIED: "Carried to another account",
                                    OUTCOME_STILL_OWES: "Still owes",
                                    OUTCOME_HELD: "Held",
                                    OUTCOME_NOT_READY: "Not ready",
                                }.get(name, name),
                            },
                            "count": {"kind": "text", "text": str(count)},
                            "happened": {
                                "kind": "text",
                                "text": (
                                    "Nothing has moved yet"
                                    if not acted
                                    else "Written by this run"
                                ),
                            },
                        },
                    }
                    for name, count in sorted(tally.items(), key=lambda pair: -pair[1])
                ],
            },
        ),
        Block(
            block="records",
            payload={
                "columns": _records_columns(),
                "rows": [
                    _record_row(index, row, outcomes)
                    for index, row in enumerate(plan, start=1)
                ],
                "total": len(plan),
                "chips": [
                    {"id": "all", "label": "All", "count": len(plan)},
                    {"id": "need_you", "label": "Need you", "count": not_ready + held},
                    {"id": "refunds", "label": refund_word, "count": refunds},
                    {"id": "settled", "label": "Settled", "count": settled},
                ],
                "empty": {
                    "title": "No move-outs to finish.",
                    "helper": (
                        f"{gathered.get('closing_accounts', 0)} closing accounts over the next "
                        f"{gathered.get('window_days', 14)} days, and none closed without a "
                        "final bill. Nothing is waiting for you."
                    ),
                },
            },
        ),
        Block(
            block="facts",
            payload={
                "heading": "What this run did not do",
                # ⚠ **THE TWO ABSENCES THAT WOULD OTHERWISE BE INVISIBLE**, each
                # with a number beside it (hard-won law 7). A reader must be able
                # to see that no bill was issued and no letter left the building
                # WITHOUT knowing this module's rules.
                "rows": [
                    {
                        "label": "Final bills issued by this run",
                        "value": {
                            "kind": "text",
                            "text": str(bills.get("bills_issued_by_this_runbook", 0)),
                        },
                        "detail": str(bills.get("why_not") or ""),
                    },
                    {
                        "label": "Notices queued",
                        "value": {
                            "kind": "text",
                            "text": str(notices.get("notices_queued", 0)),
                        },
                        "detail": str(notices.get("word_on_the_screen") or ""),
                    },
                ],
            },
        ),
        Block(
            block="downloads",
            payload={
                "files": [
                    {"id": "closing", "label": "Closing accounts", "format": "csv"},
                    {"id": "refunds", "label": "Refunds", "format": "csv"},
                ]
            },
        ),
    ]


# ── the guard and the pinned scope ────────────────────────────────────────


SAMPLE_KEYS = "_sample_accounts"


def _is_sample(ctx, subject) -> bool:
    """`RB-127`'s *Never include: Sample* (`BR-TEN-057`, `BR-RBS-012`).

    ⚠ **A GUARD AND NOT A FILTER INSIDE A READ.** A guarded subject is still
    pinned and still counted (`BR-RBS-035`), and `RBS-004.4` draws the control
    disabled WITH its reason rather than hiding it. And on this runbook it is
    the guard that matters most: `BR-RBS-014` says a sample record is never
    acted on by an Action, and every act here moves money.
    """
    return str(subject.subject_id) in (ctx.set_results.get(SAMPLE_KEYS) or frozenset())


def resolve(ctx):
    """The pinned set: **one subject per closing ACCOUNT** (`BR-RBS-019`).

    ⚠ **RESOLVED ONCE AND FROZEN** (`BR-RBS-009`). An account that closes
    mid-run is not in the review list and is not acted on; the fingerprint the
    executor computes is how a later reader proves the set did not move — which
    on a runbook that refunds money is the difference between an audit and an
    assertion.
    """
    accounts = _accounts(ctx)
    ctx.set_results[SAMPLE_KEYS] = frozenset(
        str(one["account_id"]) for one in accounts if one.get("is_sample")
    )
    return [
        SubjectRef(
            subject_type="account",
            subject_id=str(one["account_id"]),
            label=str(one.get("account_no") or one["account_id"]),
        )
        for one in accounts
    ]


RUNBOOK = RunbookDefinition(
    key=KEY,
    #: `RB-127`: *"On screen a clerk sees 'Move-outs.'"* The definition title —
    #: *Move-outs and final bills* — is the name on its card.
    name="Move-outs",
    kind=models.KIND_ACTION,
    category="accounts",
    subject_type="account",
    unit_of_work="a closing account",
    # ⚠ The card declares no trigger; its `Runs` parameter reads *Daily 07:00*,
    # which is the schedule half, and manual waits on nothing.
    triggers=(models.TRIGGER_MANUAL, models.TRIGGER_SCHEDULE),
    tags=(),
    parameters=(
        Parameter(
            name="window_days",
            type=PARAM_ENUM,
            label="Window",
            required=True,
            default="14",
            choices=("7", "14", "30"),
        ),
        Parameter(
            name="closing_read_due",
            type=PARAM_REF_SETTING,
            label="Closing read due",
            setting_key="metering.read_validation",
        ),
        Parameter(
            name="deposit",
            type=PARAM_ENUM,
            label="Deposit",
            required=True,
            default="refund",
            # `RB-127`'s own two options. A third — *hold* — would be a rule this
            # product does not have: `BR-CUS-096` already holds an excess behind
            # an open dispute, and that is a FACT about the account rather than a
            # setting a tenant chooses.
            choices=("refund", "carry_to_the_new_account"),
        ),
        Parameter(
            name="channel",
            type=PARAM_ENUM,
            label="Channel",
            required=True,
            default="email_then_post",
            choices=("email_then_post",),
        ),
    ),
    guards=(
        Guard(key="sample", label="Never include: Sample", applies=_is_sample),
    ),
    resolve=resolve,
    report=report,
    steps=(
        Step(
            key=STEP_GATHER,
            label=STEP_LABELS[STEP_GATHER],
            mode=MODE_SET,
            run=step_gather_closing_accounts,
        ),
        Step(
            key=STEP_READ,
            label=STEP_LABELS[STEP_READ],
            mode=MODE_SET,
            run=step_check_the_closing_read,
        ),
        Step(
            key=STEP_ADDRESS,
            label=STEP_LABELS[STEP_ADDRESS],
            mode=MODE_SET,
            run=step_check_the_forwarding_address,
        ),
        # ⚠ **THIS STEP DECLARES `writes=False`, AND THE CARD MARKS IT A WRITE.**
        # That is the divergence in the module docstring, made mechanical: there
        # is no port that issues a bill and there will not be one, so a step
        # claiming to write would be a claim the capability contradicts.
        Step(
            key=STEP_BILL,
            label=STEP_LABELS[STEP_BILL],
            mode=MODE_SET,
            run=step_issue_the_final_bill,
        ),
        # ⚠ THE ONLY PER-RECORD STEP, AND THE ONLY MONEY. One account, one
        # savepoint (law 14), one audit row named after the runbook (rule 7).
        Step(
            key=STEP_DEPOSIT,
            label=STEP_LABELS[STEP_DEPOSIT],
            mode=MODE_PER_RECORD,
            run=step_settle_the_deposit,
            writes=True,
        ),
        Step(
            key=STEP_NOTICE,
            label=STEP_LABELS[STEP_NOTICE],
            mode=MODE_SET,
            run=step_queue_the_final_notice,
            writes=True,
        ),
    ),
    ports=("raise_refund", "post_credit", "queue_notice"),
)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-037 (EP-RBS-05; CR-075 wave R′)
# generated: 2026-09-07 by the CR-075 wave R′ metering-and-customers lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint — every runbooks route is a GET and POST /runbooks/{key}/runs is wave L) E=n/a(no screen — RBS-004 and RBS-006 render any runbook; RB-020 — and RB-127's result frame is RESERVED and NOT DRAWN, which this file does not invent) F✔ G✔ H=n/a(no 🔒 path: the settlement arithmetic is READ from apps/customers/move_out_settlement.py and re-derived nowhere; this composes no idempotency key of its own beyond acts', touches no rating math and posts no ledger line)
# gates: pytest tests/test_us_rbs_037_move_outs.py · pytest tests/test_rbs_reads_runbooks_pg.py (PostgreSQL) · pytest tests/test_us_rbs_015_conformance.py · G115 (the import census) · G20 (the seam implementers)
# exceptions: step 4 PLANS and hands billing a scope — there is no port that issues a bill and there will not be one (billing_ports.py), so the step declares writes=False where the card marks it a write; the card's result screen is RESERVED and NOT DRAWN and this composes the twelve blocks around its *done looks like* sentence instead of inventing one; the five money landings are READ from customers and re-derived nowhere; nothing has moved — LIVE_ENABLED_RUNBOOKS is empty, so the strip says "Refunds to approve"
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
