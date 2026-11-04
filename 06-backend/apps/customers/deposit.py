# ── Trace ──────────────────────────────────────────────
# Change:   CR-094-BRC01 step 2 wave H — the ONE deposit capability.
#           PO ruling 2026-09-12, verbatim: *"(a) It is one concept — money
#           held against an account — and building it four times would give
#           four behaviours."*, answering how many deposit surfaces to build;
#           and *"if there are deposits, then there should be a proper flow to
#           accept those deposit also … you figure it out where … but it should
#           be in the same flow"*.
# Story:    US-CUS-007 (the deposit on the starting-service flows) ·
#           US-PAY-002 (payment purpose `deposit`) · US-LED-004 (the tie-out
#           this closes one side of)
#           Screens: S18 step 4 (New account · Deposit) · S19 step 5
#           (Move-in · Deposit) — blueprint pages 63-64 and 70-71
# Rules:    **BR-CUS-025** (a deposit is a LIABILITY, never revenue — ruled
#           2026-08-12, `deposit_liability` 2300) · **BR-CUS-037** (a customers
#           money surface is an ENTRY POINT: validate → confirm → the owning
#           module's service; customers writes no financial table) ·
#           BR-PAY-012 (every payment carries a purpose; a deposit meets no
#           bill and becomes no credit) · BR-PAY-021 (both dates, always) ·
#           BR-RAT-020/023 (`plan_deposit_rules` is where the standard figure
#           lives) · BR-TEN-013 (a module never touches another module's ORM) ·
#           BR-TEN-043 (the event date is an argument, never a wall clock) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 2 (money to 4 decimals,
#           never float) · rule 4 (financial immutability) · rule 5 (only the
#           ledger posting service writes journal lines) · rule 7 (audit)
# Tests:    06-backend/tests/test_cr094_wh_deposit.py
# Impacts:  apps/customers/services.py (`CREATE_FIELDS` gains `deposit`, so
#           `MOVE_IN_FIELDS` gains it too; `_open_account` takes it INSIDE its
#           own transaction) · apps/customers/seams.py (the two resolves) ·
#           apps/payments/services.record_payment (the owning service) ·
#           apps/payments/ledger_seam (DR undeposited funds / CR 2300) ·
#           07-frontend/src/features/customers/depositCapability.tsx (the one
#           step, mounted by both wizards)
# ───────────────────────────────────────────────────────
"""**ONE deposit capability.** Taken at the counter, held as a liability.

════════════════════════════════════════════════════════════════════════════
WHY THIS FILE EXISTS, IN ONE SENTENCE
════════════════════════════════════════════════════════════════════════════
A clerk could not take a deposit anywhere in this product. Four wizards drew a
deposit and every one of them refused it by name, so a utility that asks for
$150.00 before turning the water on had nowhere to record that it had been
asked for, let alone paid.

**The PO ruled the SHAPE before the behaviour**: *"It is one concept — money
held against an account — and building it four times would give four
behaviours."* So this module is the whole of it on the customers side, and
every wizard that needs a deposit calls THIS.

════════════════════════════════════════════════════════════════════════════
THE ACCOUNTING WAS ALREADY RULED — THIS MODULE DECIDES NOTHING ABOUT IT
════════════════════════════════════════════════════════════════════════════
`BR-CUS-025`, ruled 2026-08-12: **a deposit is a LIABILITY, never revenue.**
The chart of accounts has carried `deposit_liability` **2300** since the PO
named the eleven designations account by account, and
`apps/payments/ledger_seam` already credits it on a posted deposit-purpose
payment. **Nothing here books anything** — hard rule 5 keeps the ledger posting
service the sole writer of journal lines, and `record_payment` is what reaches
it.

════════════════════════════════════════════════════════════════════════════
WHAT A DEPOSIT IS, AS THREE ANSWERS AND NOT TWO
════════════════════════════════════════════════════════════════════════════
The blueprint draws one select with three options, and the difference between
the second and the third is the whole reason it is not a checkbox:

    required      this account owes a deposit, of `amount`
    not_required  this account owes none — nothing was assessed
    waived        one WAS assessed and somebody decided not to collect it

**`not_required` and `waived` are different facts and must never collapse.** A
waived deposit is a decision with a person behind it; a deposit never assessed
is the absence of one. `rating.selectors.deposit_rule_for` takes the same care
one layer down — *"`None` is 'this plan asks no deposit of this category' … A
zero-valued line on a customer's first bill states that a deposit was assessed
and waived, which is a different fact from never having been assessed."*

════════════════════════════════════════════════════════════════════════════
WHERE THE AMOUNT COMES FROM — THE PLAN, FOR THE CATEGORY, WITH NO OVERRIDE
════════════════════════════════════════════════════════════════════════════
⛔ **RULED 2026-09-23, AND IT SUPERSEDES THIS MODULE'S FIRST DESIGN
(`DEF-CUS-6369`).** PO, verbatim: *"you need to take deposit amount as per
plan ; plan will have deposite chanrge code as per customer categoris ;so that
value should be atken as by default no override is required"*. Until that day
the clerk TYPED the amount (the blueprint's *"Typed by hand today."*) and the
plan's figure was only REPORTED beside it. The signed rules had always agreed
with the PO — `BR-RAT-020` (*"fixed $ amounts per consumer category"*) and
`BR-RAT-023` (*"Deposit schedule is PLAN-level"*) — so this collides with
nothing signed; it makes the signed figure the one the account is asked for.

The figure: account → `unit_id` → `units.rate_plan_id` →
`rating.selectors.deposit_rule_for(plan, account_type)` →
`rating.plan_deposit_rules` (**rate_plan × account_type → one fixed amount**,
tenant-editable on Plans & Rates). `plan_standard_for` walks it; the screen
reads the same walk before the account exists
(`standard_for_unit`, `GET /accounts/deposit-standard`), so
the figure a clerk is shown and the figure the commit takes cannot come from
two derivations.

⚠ **THE SERVER TAKES THE FIGURE FROM THE PLAN AND REFUSES A DIFFERENT ONE BY
NAME — IT DOES NOT SILENTLY SUBSTITUTE, AND THE CHOICE IS DELIBERATE.** The
block may omit `amount` altogether and the plan's figure is used. If it SENDS
one, that is the figure the screen showed the clerk and the clerk quoted to the
customer — and if the plan was edited in between, taking the new figure
silently would charge somebody an amount nobody at the counter ever saw. So a
sent amount that is not the plan's is refused
(`customers.deposit.amount_not_plan`), the clerk goes back a step and reads
the new figure, and a hand-built request cannot override the plan either way.

⚠ **AND THE PLAN DECIDES WHICH ANSWERS EXIST — `OQ-CUS-12620`, RULED (a).**
PO, verbatim: *"no, we ahve to take depsoite if plans asked clark can waive it
off - (a) When the plan asks a deposit: take it or waive it (supervisor). "No"
only when the plan asks none."* So:

    plan asks a figure  → `required` (today, or on the first bill) or `waived`
                          (a Billing Clerk or a System Admin since 2026-09-24 —
                          `OQ-CUS-12623` — with a reason). `not_required` — and a
                          door that sends NO block at all — is REFUSED.
    plan asks none      → `not_required` is the only answer; `required` and
                          `waived` are refused, because there is no figure to
                          take or to forgive and inventing one is the override
                          the PO ruled out.

**`plan_asks_deposit()` below is that one condition, and `take()` is where it
is enforced.** A plan rule of `0.00` is
read as asking none: a zero deposit is not money anybody can take
(`record_deposit_movement` refuses a movement of zero) or forgive.

*"Why this amount"* (`reason`) is gone from the screen with the typed figure —
its four reasons justified a typed judgement and a fixed figure has none. The
server stays TOLERANT of it: an absent `reason` has always been accepted, and a
parked draft written before 2026-09-23 may still carry one.

════════════════════════════════════════════════════════════════════════════
⚠ NOTHING HERE WRITES THE REGISTER, THE BOOKS OR THE RECEIPT — ALL THREE EXIST
════════════════════════════════════════════════════════════════════════════
**The first draft of this module wrote `accounts.deposit_on_file` itself, and
that was wrong.** The whole accept path has been built since 2026-08-27 and was
found by grepping for it rather than by reading a plan. One call does all of
it:

    payments.services.record_payment(purpose="deposit")     posted at entry
      → ledger_seam (via _hold_and_post)     DR undeposited / CR 2300
      → customers.services.record_deposit_movement   `BR-CUS-670`, the REGISTER
      → notifications                        the deposit receipt

`record_deposit_movement` is itself a **customers** function, published for
payments and resolved there by name, and it already does every hard part: it
`select_for_update`s the account, refuses a movement of zero, refuses a release
that would take the register below zero rather than clamping it, stamps
`deposit_received_on` **only when the account has none** (`BR-CUS-050`, so a
second deposit cannot restart `BR-CUS-057`'s interest clock), and writes its own
`deposit.received` audit row.

**So `DEF-177` — *"nothing writes `accounts.deposit_on_file`"* — is CLOSED, and
this module must not re-open it by becoming a second writer.** Two paths to one
money column is the shape of `DEF-154` (two base-charge columns) and `OQ-238`
(two figures for one fact); the figure is read back off the payment's own
`deposit_held_after` and nothing here writes it.

⚠ **WHAT WAS ACTUALLY MISSING IS ONLY THE ENTRY POINT.** Measured on 2.239.4:
`POST /accounts/{id}/payments` accepts `purpose="deposit"` and works end to
end, and **no screen in the product ever sent it.** Four wizards drew a deposit
and all four refused it. That is hard-won law 2 at feature scale — a finished
engine behind no door — and it is what this wave builds.

⚠ **NO CLEARING DATE IS ASKED HERE — `CR-186-BRC10`, PO 2026-10-21
(`DEF-CUS-10324`).** *"first they will pot the payment - so we crete the record
and add posting date; then later money is recieved in the bank account ;
uitlity will reconcile it bank statement that time it is cleared with clearing
date"*. So a deposit taken at the counter is recorded `posted` like every
payment: the 2300 liability is booked and the register moves AT POSTING
(`record_payment` → `_hold_and_post`), and `cleared` is written only by bank
reconciliation. The blueprint's *"Leave the clearing date blank … the new
account will read a deposit of $0.00 while the cash is in the drawer"* was true
before that ruling and is false after it, so the field and its sentence are
gone. **`cleared_at` is no longer an accepted key** — it is refused by name as
an unknown field, because a key accepted and silently ignored is a clearing
date the clerk believes they recorded.

⚠ **`accounts.deposit_on_file` STAYS A REFUSED FIELD** (`services.
REFUSED_FIELDS`, `BR-CUS-023`) and this module does not widen that. It is
written as the EFFECT of money that reached the books, never as an input —
which is the distinction `record_deposit_movement`'s own note draws.

⚠ **`DEF-1713` IS A DIFFERENT DOOR AND IS NOT CLOSED BY ANY OF THIS.** That is
the same column in the opposite direction: a MIGRATED deposit written by the
importer with no posting behind it. Nothing on this path touches it, so the S36
tie-out's `deposit_liability` row stays DRIFTING for an estate seeded that way.

════════════════════════════════════════════════════════════════════════════
ONE TRANSACTION, AND WHY NOTHING HERE CATCHES A DATABASE ERROR
════════════════════════════════════════════════════════════════════════════
The blueprint's own review panel states the order: *"the account, then the
reads, then the payment. One transaction."* `take()` runs INSIDE
`_open_account`'s `transaction.atomic()`, so a refused payment rolls the
account back and the clerk fixes the field with everything still on screen —
`BR-SHL-019`, and the same posture a refused opening reading already takes.

⚠ **NOTHING HERE CATCHES `IntegrityError` AND CONTINUES, DELIBERATELY —
hard-won law 14.** On PostgreSQL a failed statement aborts the whole
transaction, and the suite runs on SQLite, which does not — so the naive
`except IntegrityError: continue` passes every test and loses the account in
production. The way not to need a SAVEPOINT is not to swallow the error: a
payment that cannot be recorded refuses the whole commit, loudly.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any

from django.utils import timezone as dj_timezone

from core import errors
from core import tenancy as core_tenancy
from core.permissions import BILLING_CLERK, SYSTEM_ADMIN

#: The three answers to *"Does this account need a deposit?"*, in the order the
#: blueprint draws them. `waived` and `not_required` are different facts — see
#: the module docstring.
DECISION_REQUIRED = "required"
DECISION_NOT_REQUIRED = "not_required"
DECISION_WAIVED = "waived"
DECISIONS: tuple[str, ...] = (DECISION_REQUIRED, DECISION_NOT_REQUIRED, DECISION_WAIVED)

#: *"Why this amount"* — the blueprint's four, verbatim and in its own order.
#: A REASON, never a rule: none of these four changes a figure.
#:
#: ⚠ **NO LONGER ASKED ON ANY SCREEN (2026-09-23, `DEF-CUS-6369`)** — the figure
#: is the plan's, so there is no judgement left to give a ground for. KEPT here
#: so the server stays tolerant of a block that still carries one (a draft parked
#: before that day), and still refuses a value outside these four by name.
REASONS: tuple[str, ...] = (
    "standard",
    "no_credit_history",
    "previous_arrears",
    "returning_customer",
)

#: The payload this module accepts. Anything else is refused by name, because a
#: dropped key is a deposit the clerk believes they collected.
DEPOSIT_FIELDS: frozenset[str] = frozenset(
    {
        "decision",
        "amount",
        "reason",
        "waive_reason",
        "due_on",
        "take_now",
        "method_code",
        "confirmation",
        "amount_taken",
        "posted_at",
        # ⛔ NO `cleared_at` — `DEF-CUS-10324` (CR-186-BRC10): a deposit is
        # recorded `posted`; only bank reconciliation clears it. Sent, it is
        # refused by name below rather than accepted and ignored.
        "idempotency_reference",
        # `DEF-CUS-9521` — the size the clerk picked because no meter is fitted.
        "size_class",
    }
)

#: Money is stored to 4 decimals (CLAUDE.md rule 2, PO re-sign 2026-08-22).
MONEY_PLACES = Decimal("0.0001")

#: ⛔ `AMOUNT_DIFFERS_FROM_PLAN` and `NO_PLAN_STANDARD` are DELETED, not kept
#: (2026-09-23, `DEF-CUS-6369`). The first reported a typed figure that
#: disagreed with the plan, and a figure can no longer disagree — it is refused
#: (`AMOUNT_NOT_PLAN` below). The second reported a plan asking nothing beside a
#: typed figure, and a plan asking nothing now means no deposit at all. A note
#: whose condition cannot occur is a sentence nobody can make true (law 1).

#: The four refusals the plan's figure makes possible. Each must RESOLVE in all
#: eleven catalogues — an unresolved key reaches a clerk as silence.
#: The plan asks a deposit of this category, and the answer was *No* — or no
#: answer was sent at all. `OQ-CUS-12620` (a).
PLAN_ASKS_DEPOSIT = "customers.deposit.planAsksDeposit"
#: The plan asks nothing of this category, and the answer was take or waive.
PLAN_ASKS_NONE = "customers.deposit.planAsksNone"
#: The block sent a figure that is not the plan's. See the module docstring for
#: why this refuses rather than silently substituting.
AMOUNT_NOT_PLAN = "customers.deposit.amountNotPlan"
#: `OQ-RAT-12786` (CLOSED 2026-10-03) — the plan's deposit code is priced by
#: METER SIZE and states no amount for this connection's size (or no size is
#: recorded on it). The plan DOES ask a deposit, so this is never read as
#: "asks none"; the clerk is stopped by name until the utility prices the size
#: or records it.
SIZE_NOT_PRICED = "customers.deposit.sizeNotPriced"
#: `DEF-CUS-9521` — PO 2026-10-04, verbatim: *"(c) Let the clerk pick the size
#: on the Deposit step."* The plan prices the deposit by meter size, no size
#: is recorded on the connection (no meter fitted, or no connection for the
#: code's service) and no size was picked. The step OFFERS the plan's priced
#: sizes; this is the refusal a request that picked none meets — never "asks
#: none", which would connect the customer with no deposit taken.
SIZE_REQUIRED = "customers.deposit.sizeRequired"
#: rating's refusal name for *no size recorded* (`charge_prices.SIZE_NOT_RECORDED`).
SIZE_NOT_RECORDED = "size_not_recorded"
#: The audit action and its reason when the clerk picks the size
#: (`DEF-CUS-9521`; CLAUDE.md rule 7 — a deposit is a money action).
SIZE_PICKED_ACTION = "deposit.size_picked"
SIZE_PICKED_REASON = "no_meter_fitted"
#: A waive with no reason. Kept on the account, so it must say why.
WAIVE_REASON_REQUIRED = "customers.deposit.waiveReasonRequired"
#: A waive reason is ONE short sentence (`accounts.deposit_waive_reason`).
WAIVE_REASON_LIMIT = 200
#: A deposit was assessed and somebody decided not to collect it. Recorded so
#: the confirmation can say so; `waived` never takes a payment.
WAIVED = "deposit_waived"
#: The deposit is owed and is NOT being taken today — it goes out with the
#: first bill. Nothing is recorded against the account until money arrives.
DEFERRED_TO_FIRST_BILL = "deposit_deferred_to_first_bill"
#: Payments has published no `record_payment`. A seam that cannot answer SAYS
#: so — it never answers "recorded" (the G20 rule).
PAYMENTS_UNWIRED = "deposit_payment_path_unwired"

#: **WHO MAY WAIVE — `BR-CUS-1050` AS AMENDED 2026-09-24: A BILLING CLERK OR A
#: SYSTEM ADMIN (`OQ-CUS-12623`, `DEF-CUS-6372`).** PO, verbatim: *"p3 - clark
#: and sysem admin can do it"*. Worked: a Billing Clerk waives Rosa's
#: **$150.00** for *Hardship* and the account reads *Waived · $150.00*. The
#: reason is still required (`clean`) and the waive is still kept on the
#: account (`deposit_waived_*`, `DEF-CUS-6370`).
#:
#: ⛔ **SUPERSEDED 2026-09-24 — EVERYTHING BELOW THIS LINE ABOUT A SUPERVISOR.**
#: The set read `{SYSTEM_ADMIN, EXECUTIVE}` on the 2026-09-20 amendment and the
#: reasoning that follows. An Executive is OUT of the set — the signed grid
#: gives them View on Accounts, so they never reached this step anyway
#: (`DEF-CUS-6372`) — and a Billing Clerk is IN it, which reverses p073's
#: *"(needs a supervisor)"* parenthesis for this control by the PO's later
#: word. The history is kept so a reader who meets the old parenthesis in the
#: blueprint finds out why the code no longer enforces it.
#:
#: **WAS — `BR-CUS-1050` as amended 2026-09-20, `DEF-CUS-5908`.**
#:
#: ⚠ **THE AUTHORITY IS DRAWN IN THE CONTROL'S OWN LABEL.** Blueprint p073 draws
#: the deposit dropdown's help line as *"Yes — take one · No · Waive it (needs a
#: supervisor)"*, over a screen whose actor block reads `Sam Ortiz · Billing
#: Clerk`. The parenthesis is a REQUIREMENT, not a caption, and until this
#: landed `take()` returned the waived note for any actor at all: a billing
#: clerk waived `$150.00` and the whole move-in committed (`DEF-CUS-5908`).
#:
#: ⚠ **THIS PRODUCT HAS NO ROLE CALLED `supervisor`, AND THAT IS NOT A GAP HERE
#: — IT IS ALREADY ANSWERED TWICE, SO IT WAS NOT PUT TO THE PO AGAIN (hard-won
#: law 13).** `core.permissions.ROLES` is exactly `system_admin`,
#: `billing_clerk`, `executive`. Who counts as a supervisor is settled by:
#:
#:   * **`OQ-042`'s closure**, PO verbatim — *"optional toggle default ON;
#:     **supervisor = SysAdmin/Executive**; blocks when enabled (PO R6)"*, which
#:     `metering.services.cosign_read_batch` has been built on since `CR-038` W7;
#:   * **A4's signed grid** (`identity.models.A4_MATRIX`, `BR-IDN-014`), row
#:     `adjustment_approval` — System Admin **Approve** · Executive **Approve** ·
#:     Billing Clerk **Request**.
#:
#: So this is `BR-CUS-1047`'s reading applied to a second control, not a lane's
#: guess: `apps/customers/unit_correction.py` already refuses a Billing Clerk
#: with `@require_role(SYSTEM_ADMIN, EXECUTIVE)` for *"a supervisor's approval"*.
#:
#: ⚠ **AND IT IS A PER-DECISION GATE RATHER THAN `@require_role` ON `take()`.**
#: Only the THIRD answer names an authority; a whole-function decorator would
#: refuse a billing clerk TAKING an ordinary deposit, which is their daily work
#: and which p073 draws them doing.
WAIVE_ROLES: frozenset[str] = frozenset({BILLING_CLERK, SYSTEM_ADMIN})
#: The sentence a refused role reads — *"Your role cannot waive a deposit. Ask
#: a Billing Clerk."* It must RESOLVE — an unresolved key reaches them as
#: silence, not as an ugly string (`core/refusal_catalogue`). Renamed from
#: `waiveNeedsSupervisor` on 2026-09-24: a key naming a supervisor for a set
#: that holds a clerk is the rot a renamed key avoids.
WAIVE_NOT_YOUR_ROLE = "customers.deposit.waiveNotYourRole"


@dataclass(frozen=True)
class DepositInstruction:
    """What the clerk decided, validated, before a single row is written.

    Frozen and built BEFORE the account exists, so an instruction that cannot
    be honoured refuses at the door rather than leaving a half-taken deposit
    behind — the posture `payments.purposes.PurposeLinkage` takes for exactly
    the same reason.
    """

    decision: str
    #: What the block SENT, if anything. `take()` replaces it with the plan's
    #: figure — or refuses when the two differ. Never the authority.
    amount: Decimal | None = None
    reason: str | None = None
    #: Required when `decision == waived`; kept on the account.
    waive_reason: str | None = None
    due_on: date | None = None
    take_now: bool = False
    method_code: str | None = None
    confirmation: str | None = None
    amount_taken: Decimal | None = None
    posted_at: date | None = None
    idempotency_reference: str | None = None
    #: `DEF-CUS-9521` — the meter size the clerk picked because no meter is
    #: fitted (a `service_size_classes` code). Ignored where a size IS recorded.
    size_class: str | None = None

    @property
    def collects(self) -> bool:
        """Is there a payment to record at all?

        `waived` never collects — that is what waiving IS — and neither does
        `not_required`. Only a REQUIRED deposit the clerk is taking today.
        """
        return self.decision == DECISION_REQUIRED and self.take_now


def _fe(field: str, code: str, message_key: str, **params: Any) -> dict[str, Any]:
    return {"field": field, "code": code, "message_key": message_key, "params": params}


def _money(value: Any, field: str, fe: list[dict[str, Any]]) -> Decimal | None:
    """A money figure, quantized to 4 decimals. Never a float (rule 2)."""
    if value is None or value == "":
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, ArithmeticError):
        fe.append(_fe(field, errors.VAL_FORMAT, "customers.account.amount_invalid"))
        return None
    if amount.is_nan() or amount.is_infinite():
        fe.append(_fe(field, errors.VAL_FORMAT, "customers.account.amount_invalid"))
        return None
    if amount < 0:
        fe.append(_fe(field, errors.VAL_RANGE, "customers.account.amount_negative"))
        return None
    return amount.quantize(MONEY_PLACES)


def _day(value: Any, field: str, fe: list[dict[str, Any]]) -> date | None:
    if value is None or value == "":
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        fe.append(_fe(field, errors.VAL_FORMAT, "customers.account.date_invalid"))
        return None


def _text(value: Any, limit: int = 120) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned[:limit] if cleaned else None


def clean(raw: Any) -> DepositInstruction | None:
    """Validate the wizard's `deposit` block. `None` when it sent none.

    **Every refusal names ITS OWN FIELD**, because `DEF-CUS-5082` is the defect
    of a form that refuses on one field and marks another: a clerk told *"Fill
    in what's marked above"* over a screen with the wrong mark gives up.

    ⚠ **FIVE OF THE MESSAGE KEYS BELOW ARE NOT THIS MODULE'S, AND THAT IS
    DELIBERATE.** *"That is not an amount we can read"*, *"a deposit is money
    you are holding, so it cannot be negative"*, *"enter that date as a real
    calendar date"*, the unknown-field sentence and the malformed-payload one
    are already written in all eleven catalogues under `customers.account.*`
    and `customers.*`, and one of them is ABOUT A DEPOSIT in so many words. A
    `customers.deposit.*` twin would be the same sentence in two places, free
    to drift in ten languages at once — which is `DEF-154`'s shape in prose.
    Only the seven sentences nothing else says are new.
    """
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key="customers.payload_not_object")

    fe: list[dict[str, Any]] = []
    unknown = sorted(set(raw) - DEPOSIT_FIELDS)
    for key in unknown:
        fe.append(_fe(key, errors.VAL_FORMAT, "customers.account.unknown_field"))

    decision = _text(raw.get("decision")) or DECISION_NOT_REQUIRED
    if decision not in DECISIONS:
        fe.append(_fe("decision", errors.VAL_FORMAT, "customers.deposit.decision_unknown"))
        decision = DECISION_NOT_REQUIRED

    amount = _money(raw.get("amount"), "amount", fe)
    amount_taken = _money(raw.get("amount_taken"), "amount_taken", fe)
    reason = _text(raw.get("reason"))
    if reason is not None and reason not in REASONS:
        fe.append(_fe("reason", errors.VAL_FORMAT, "customers.deposit.reason_unknown"))
        reason = None

    due_on = _day(raw.get("due_on"), "due_on", fe)
    posted_at = _day(raw.get("posted_at"), "posted_at", fe)
    take_now = bool(raw.get("take_now"))

    # ⛔ **NO "AMOUNT REQUIRED" CHECK HERE ANY MORE (2026-09-23,
    # `DEF-CUS-6369`).** The figure is the PLAN's and the plan is only readable
    # once the account names its unit and category, which is inside the
    # creating transaction — so `take()` resolves it and refuses there. A block
    # may omit `amount`; one that sends `0` is refused in `take()` as not the
    # plan's figure, with everything rolled back (`BR-SHL-019`).

    # A waive is a money decision with a person behind it, kept on the account
    # (`DEF-CUS-6370`), so it carries its reason — one short sentence.
    waive_reason = _text(raw.get("waive_reason"), WAIVE_REASON_LIMIT)
    if decision == DECISION_WAIVED and waive_reason is None:
        fe.append(_fe("waive_reason", errors.VAL_REQUIRED, WAIVE_REASON_REQUIRED))

    if decision != DECISION_REQUIRED and take_now:
        # Taking money for a deposit this account does not owe would be a
        # payment with no purpose behind it. Refuse rather than silently drop
        # the tick — a dropped tick is money the clerk believes they took.
        fe.append(_fe("take_now", errors.VAL_RANGE, "customers.deposit.take_without_deposit"))

    if decision == DECISION_REQUIRED and take_now:
        if _text(raw.get("method_code")) is None:
            fe.append(_fe("method_code", errors.VAL_REQUIRED, "customers.deposit.method_required"))
        if posted_at is None:
            fe.append(_fe("posted_at", errors.VAL_REQUIRED, "customers.deposit.posted_required"))

    if fe:
        raise errors.ValidationError(
            fe[0]["code"],
            message_key=fe[0]["message_key"],
            params=fe[0]["params"],
            field_errors=fe,
        )

    return DepositInstruction(
        decision=decision,
        amount=amount,
        reason=reason,
        waive_reason=waive_reason if decision == DECISION_WAIVED else None,
        due_on=due_on,
        take_now=take_now,
        method_code=_text(raw.get("method_code"), 40),
        confirmation=_text(raw.get("confirmation"), 120),
        # *"Defaults to the deposit."* — the blueprint's own helper under
        # *Amount taken*. Resolved on the SERVER rather than on the screen, so a
        # clerk who never touches the box and one who retypes the same figure
        # reach it with the same instruction. `None` here when the block sent
        # no figure at all: `take()` fills it with the PLAN's, once it is known.
        amount_taken=amount_taken if amount_taken is not None else amount,
        posted_at=posted_at,
        idempotency_reference=_text(raw.get("idempotency_reference"), 120),
        size_class=_text(raw.get("size_class"), 40),
    )


def plan_standard_for(account: Any, size_class: str | None = None) -> dict[str, Any] | None:
    """The figure `plan_deposit_rules` states for this account, or None.

    account → `unit_id` → `units.rate_plan_id` → `deposit_rule_for(plan,
    account_type)`. Three links, each one a read the product already publishes,
    and **None at any of them means None here** — a master account names no
    unit (`BR-CUS-1010`), a unit may stand on no plan, and a plan may ask no
    deposit of this category. All three are ordinary states.

    `size_class` — the size the clerk picked (`DEF-CUS-9521`); absent, the one
    the account already keeps (`deposit_size_class`) is used, so the move
    record reads the figure the counter took.
    """
    from apps.customers import seams

    return seams.deposit_rule_for_account(
        unit_id=getattr(account, "unit_id", None),
        account_type_id=getattr(account, "account_type_id", None),
        size_class=size_class or getattr(account, "deposit_size_class", None),
    )


def plan_asks_deposit(standard: dict[str, Any] | None) -> Decimal | None:
    """**THE ONE CONDITION `OQ-CUS-12620` MOVES** — the plan's figure, or None.

    Returns the figure `plan_deposit_rules` states for this plan × category,
    quantized to four decimals (hard rule 2), when the plan ASKS a deposit —
    and `None` when it asks none. Every answer the step offers and every
    refusal `take()` makes hangs off this one value:

        figure  → the answers are `required` or `waived`; `not_required` refused
        None    → `not_required` is the only answer; the other two refused

    That is the PO's option (a), ruled 2026-09-23. **Had option (b) been ruled
    — keep *No* available always — the change would be ONE line in `take()`:
    the `not_required` refusal under `if figure is not None`.** Nothing else
    reads this for that purpose, deliberately, so a future ruling moves one
    condition and not a scatter of them.

    ⚠ **A RULE OF `0.00` IS "ASKS NONE", NOT "ASKS ZERO".** rating's own
    warning is that `None` and a zero line are different facts on a BILL; here
    there is no line to print, and a zero deposit is not money anybody can take
    (`record_deposit_movement` refuses a movement of zero) or forgive.
    """
    if (
        standard is not None
        and standard.get("refusal") == SIZE_NOT_RECORDED
        and standard.get("sizes")
    ):
        # `DEF-CUS-9521` — no meter fitted and the plan prices sizes the clerk
        # can pick: the answer is a PICK, so the refusal names that field.
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key=SIZE_REQUIRED,
            params={"charge": standard.get("code")},
            field_errors=[
                _fe("deposit.size_class", errors.VAL_REQUIRED, SIZE_REQUIRED, charge=standard.get("code"))
            ],
        )
    if standard is not None and standard.get("refusal"):
        # `OQ-RAT-12786` — a deposit priced by size this connection's size does
        # not price. Refused BY NAME rather than read as "asks none", which
        # would connect the customer with no deposit taken.
        size = standard.get("size_class")
        raise errors.ValidationError(
            errors.VAL_RANGE,
            message_key=SIZE_NOT_PRICED,
            params={"charge": standard.get("code"), "size": size},
            field_errors=[
                _fe("deposit.amount", errors.VAL_RANGE, SIZE_NOT_PRICED, charge=standard.get("code"), size=size)
            ],
        )
    if standard is None or standard.get("amount") is None:
        return None
    figure = Decimal(str(standard["amount"])).quantize(MONEY_PLACES)
    return figure if figure > 0 else None


def standard_for_unit(
    unit_id: Any, account_type: Any, size_class: Any = None
) -> dict[str, Any]:
    """`GET /accounts/deposit-standard` — what the Deposit step SHOWS.

    The step renders before the account exists, so it cannot ask
    `plan_standard_for(account)`. This is the SAME walk from the two facts the
    wizard already holds — the unit (step 1 of the move-in, step 2 of a new
    account) and the category (the Customer step) — through the same seam, so
    the figure on screen and the figure the commit takes cannot come from two
    derivations. The category arrives as the CODE the screen holds and is
    resolved to its row exactly as the commit resolves it.

    Answers `{asks, amount, currency}`. `asks: false` with `amount: null` is
    *this plan asks no deposit of this category* — including a unit on no plan
    and a category this tenant does not hold, which the commit reads the same
    way — and the screen says so and offers nothing to type.

    ⚠ **NO METER FITTED — THE CLERK PICKS THE SIZE (`DEF-CUS-9521`).** PO
    2026-10-04, verbatim: *"(c) Let the clerk pick the size on the Deposit
    step."* Where the plan prices the deposit by meter size and the
    connection records none, the answer is `asks: true`, `pick_size: true`
    and `sizes` — `{size_class, label, amount}` per size the plan prices for
    this category, each amount the TOTAL the commit would take — with
    `amount: null` until a size is picked (`size_class=`), then that size's
    figure. A RECORDED size answers exactly as before, with no `sizes`.
    """
    from apps.customers import models, seams

    fe: list[dict[str, Any]] = []
    if unit_id in (None, ""):
        fe.append(_fe("unit_id", errors.VAL_REQUIRED, "customers.deposit.standardNeedsUnit"))
    code = _text(account_type, 60)
    if code is None:
        fe.append(_fe("account_type", errors.VAL_REQUIRED, "customers.deposit.standardNeedsCategory"))
    if fe:
        raise errors.ValidationError(
            fe[0]["code"], message_key=fe[0]["message_key"], field_errors=fe
        )
    # Tenant-scoped like `services._resolve_account_type` (PO 2026-09-17: two
    # tenants may hold one code for different things), and ACTIVE only — a
    # retired category is not one a clerk can pick on the Customer step.
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    row = (
        models.AccountType.objects.filter(tenant_id=tenant_id, active=True, code__iexact=code)
        .values_list("id", flat=True)
        .first()
    )
    picked = _text(size_class, 40)

    def rule(size: str | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return seams.deposit_rule_for_account(
            unit_id=unit_id, account_type_id=row, size_class=size
        )

    standard = rule(picked)
    head = {"unit_id": str(unit_id), "account_type": code}
    if picked is None:
        choices = _size_choices(standard)
        if choices is not None:
            # No meter fitted: the plan asks a deposit and the clerk picks.
            return {
                **head,
                "asks": True,
                "amount": None,
                "currency": choices[0]["currency"],
                "pick_size": True,
                "sizes": choices,
            }
    figure = plan_asks_deposit(standard)
    out: dict[str, Any] = {
        **head,
        "asks": figure is not None,
        "amount": str(figure) if figure is not None else None,
        "currency": standard.get("currency") if figure is not None and standard else None,
    }
    if standard is not None and standard.get("size_picked"):
        out.update(
            pick_size=True,
            sizes=_size_choices(rule(None)) or [],
            size_class=standard.get("size_class"),
            size_label=standard.get("size_label"),
        )
    return out


def _size_choices(standard: dict[str, Any] | None) -> list[dict[str, Any]] | None:
    """The sizes rating offers when no meter is fitted (`DEF-CUS-9521`), as
    the screen reads them — money as a 4-place STRING (hard rule 2) — or
    None when the plan's deposit is not waiting on a pick."""
    if standard is None or standard.get("refusal") != SIZE_NOT_RECORDED:
        return None
    sizes = standard.get("sizes") or []
    if not sizes:
        return None
    return [
        {
            "size_class": str(one["size_class"]),
            "label": str(one.get("label") or one["size_class"]),
            "amount": str(Decimal(str(one["amount"])).quantize(MONEY_PLACES)),
            "currency": one.get("currency"),
        }
        for one in sizes
    ]


def _as_datetime(day: date) -> datetime:
    """A date the clerk chose, as the instant payments wants.

    **`BR-TEN-043` — no wall clock.** Midnight of the day the clerk named,
    never `now()`: a deposit posted on the 2nd must read as the 2nd whatever
    hour the commit happened to run at.

    ⚠ **MIDNIGHT IN THE UTILITY'S OWN TIMEZONE — `OQ-153`, CLOSED BY THE PO ON
    2026-08-12 (`DEF-CUS-9754`).** This was midnight UTC, and the move-in
    matrix's M1 measured it: on a utility on America/Chicago a check typed
    **10/10/2026** was stored `2026-10-10T00:00Z` — 19:00 on 9 October in
    Chicago — and the move's Billing tab showed **10/09/2026**, because every
    screen reads the instant back in the utility's zone. `DEF-MET-9213` fixed
    the same fault in New Connection (`connections._moment_of`) and this is
    that fix, ported. The zone is a stored setting, not the process clock, so
    a replay still produces the same instant.
    """
    from apps.customers import seams

    return datetime.combine(day, time.min, tzinfo=seams.tenant_timezone())


def _refuse_unless_may_waive(actor: Any) -> None:
    """**Only `WAIVE_ROLES` waive — a Billing Clerk or a System Admin
    (`BR-CUS-1050`, 2026-09-24).** Renamed from the supervisor gate that
    enforced p073's *"(needs a supervisor)"*; the PO's *"clark and sysem admin
    can do it"* moved the set, so the name moved with it.

    ⚠ **IT REFUSES BY NAME AND SAYS WHO CAN**, because a refusal that only says
    *no* leaves a clerk clicking the same option again. `BR-SHL-025`: the server
    is the enforcement, so this holds whichever screen, job or shell called it.

    ⚠ **`BizError` AND NOT `AuthError`, DELIBERATELY.** This is not *you may not
    use this door* — a billing clerk may take, defer and decline a deposit all
    day on this very step. It is *this ANSWER needs a second person*, which is
    what `BIZ-APPROVAL` names and is why `unit_correction`'s whole-door
    `@require_role` is the wrong shape here. It also keeps the refusal inside
    the set `move_in` and `create_account` already roll back as one commit
    (`BR-SHL-019`): the account, the reads and the payment all go, and the clerk
    fixes the one field with everything else still on screen.
    """
    if getattr(actor, "role", None) in WAIVE_ROLES:
        return
    raise errors.BizError(
        errors.BIZ_APPROVAL,
        # `BR-CUS-025` owns the deposit as a liability and is what the move-in
        # scenario suite cites; `BR-CUS-1050` owns the DOOR and carries the
        # supervisor clause amended in on 2026-09-20. Both, because citing only
        # the first would point a clerk at a rule that does not say this.
        br_ref="BR-CUS-025 · BR-CUS-1050",
        message_key=WAIVE_NOT_YOUR_ROLE,
        field_errors=[
            {
                "field": "deposit.decision",
                "code": errors.BIZ_APPROVAL,
                "message_key": WAIVE_NOT_YOUR_ROLE,
                "params": {},
            }
        ],
        params={
            "code": "deposit_waiver_role_refused",
            "reason": "waiving an assessed deposit needs a Billing Clerk or a System Admin",
            # ⚠ **NAMED `accepts` ON PURPOSE — A REFUSAL MUST CARRY A WAY OUT.**
            # The two roles that may waive (2026-09-24), so the person is told
            # who to ask instead of having to find out. The move-in
            # scenario suite's friction check reads exactly this key set
            # (`earliest_start` · `accepts` · `account_no` · `account_id`) and
            # reports a refusal that names nothing actionable.
            "accepts": sorted(WAIVE_ROLES),
        },
    )


def _refuse(field: str, code: str, message_key: str, **params: Any) -> None:
    """One refusal about the deposit ANSWER, named on its own field.

    `deposit.<field>` — the same spelling `_refuse_unless_may_waive` uses —
    because these are raised from inside the creating transaction, after the
    account exists, and roll it back with everything else (`BR-SHL-019`).
    """
    raise errors.ValidationError(
        code,
        message_key=message_key,
        params=params,
        field_errors=[_fe(f"deposit.{field}", code, message_key, **params)],
    )


#: What a door that ASKS the deposit question records when the request carried
#: no `deposit` block at all. It is *No*, spelled out — so a hand-built request
#: that simply leaves the block off meets the same refusal a clerk's *No* does
#: on a plan that asks a deposit (`OQ-CUS-12620` (a)). Only a door that passes
#: it gets that check: `create_account` and `move_in`, which are where the step
#: is drawn. Every other creator (the S68 import, a transfer, a sample loader
#: calling `_open_account` directly) passes nothing and is unaffected.
NO_ANSWER = DepositInstruction(decision=DECISION_NOT_REQUIRED)


def take(
    actor: Any,
    account: Any,
    instruction: DepositInstruction | None,
    *,
    warnings: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Record the deposit against a freshly-created account. `None` for no deposit.

    ⚠ **CALLED INSIDE THE CREATING TRANSACTION.** See the module docstring: the
    order is the account, then the reads, then the payment, and a refusal rolls
    all three back.

    ⚠ **THE PLAN DECIDES, HERE (2026-09-23, `DEF-CUS-6369` / `DEF-CUS-6371`).**
    The account now names its unit and category, so the plan's figure is
    readable: `plan_asks_deposit` answers it, the answer is checked against it,
    and the figure the rest of this function uses is the PLAN's — a figure the
    block sent is only ever compared, never used.

    ⚠ **THE PAYMENT IS PAYMENTS' TO WRITE (`BR-CUS-037`).** This function
    validates, resolves and calls; it writes no financial table and composes no
    journal line, and it never writes the register (`deposit_on_file`) — that
    is read back off the payment. What it DOES write is customers' own record
    of the decision: `deposit_assessed` on a deposit that is owed, and the four
    `deposit_waived_*` columns on a waive.
    """
    if instruction is None:
        return None

    from apps.customers import seams

    standard = plan_standard_for(account, instruction.size_class)
    figure = plan_asks_deposit(standard)

    # ── the plan decides which answers exist — `OQ-CUS-12620` (a) ───────────
    if figure is None:
        if instruction.decision != DECISION_NOT_REQUIRED:
            # Nothing to take and nothing to forgive: inventing a figure is the
            # override the PO ruled out.
            _refuse("decision", errors.VAL_RANGE, PLAN_ASKS_NONE)
        return None
    if instruction.decision == DECISION_NOT_REQUIRED:
        # ⚠ THE ONE LINE `OQ-CUS-12620`'s option (b) would have deleted.
        _refuse("decision", errors.VAL_REQUIRED, PLAN_ASKS_DEPOSIT, amount=str(figure))

    # ── the waive's authority, before anything about the figure ────────────
    # A clerk who picked *Waive* is told who can, first — the figure is the
    # plan's either way and would only distract from the one thing they can
    # act on.
    if instruction.decision == DECISION_WAIVED:
        _refuse_unless_may_waive(actor)

    # ── the figure is the plan's; a different one is refused by NAME ────────
    # See the module docstring for why this refuses rather than substituting:
    # the figure the screen showed is the figure the customer was quoted.
    if instruction.amount is not None and instruction.amount != figure:
        _refuse("amount", errors.VAL_RANGE, AMOUNT_NOT_PLAN, amount=str(figure))
    instruction = replace(
        instruction,
        amount=figure,
        amount_taken=(
            instruction.amount_taken if instruction.amount_taken is not None else figure
        ),
    )

    if standard is not None and standard.get("size_picked"):
        _keep_size_pick(actor, account, standard)

    notes: list[str] = []
    out: dict[str, Any] = {
        "decision": instruction.decision,
        "amount": str(figure),
        "currency": standard.get("currency") if standard else None,
        "reason": instruction.reason,
        "due_on": instruction.due_on.isoformat() if instruction.due_on else None,
        "payment_id": None,
        "payment_no": None,
        "amount_taken": None,
        # `DEF-CUS-10324` — was `cleared`, which no longer describes a deposit
        # taken at the counter (it is `posted`; reconciliation clears it).
        # True when the register moved by this payment.
        "held": False,
        "notes": notes,
    }
    if standard is not None and standard.get("size_picked"):
        out["size_class"] = standard.get("size_class")
        out["size_label"] = standard.get("size_label")

    if instruction.decision == DECISION_WAIVED:
        # ── KEPT ON THE ACCOUNT — `DEF-CUS-6370` ─────────────────────────────
        # Four columns, set together, in this transaction. `audit_log` is pruned
        # with no row exempt (`OQ-1340`), so without these a year-old $150.00
        # waive reads exactly like a plan that asked nothing.
        #
        # `now()` is the instant the decision was RECORDED, not an event date
        # the clerk chose — the same reading `service_request_fees.waived_at`
        # takes — so `BR-TEN-043`'s no-wall-clock rule is not engaged.
        account.deposit_waived_amount = figure
        account.deposit_waived_at = dj_timezone.now()
        account.deposit_waived_by_id = getattr(actor, "id", None) or getattr(actor, "pk", None)
        account.deposit_waive_reason = instruction.waive_reason
        account.save(
            update_fields=[
                "deposit_waived_amount",
                "deposit_waived_at",
                "deposit_waived_by",
                "deposit_waive_reason",
                "updated_at",
            ]
        )
        out["waive_reason"] = instruction.waive_reason
        out["waived_at"] = account.deposit_waived_at.isoformat()
        notes.append(WAIVED)
        return out

    # ── what was ASSESSED, recorded before any money is asked for ──────────
    # ⚠ **THE OTHER SIDE OF `Still to collect` (`DEF-CUS-5909`).** `BR-CUS-670`
    # writes `deposit_on_file` when the payment CLEARS — what ARRIVED. Nothing
    # held what was ASKED FOR, so the move record computed its shortfall
    # against `plan_deposit_rules`, a figure this module REPORTS and never
    # enforces. A $150.00 deposit with $25.00 handed over read $95.00 against a
    # $120.00 plan standard where p075's review computes $125.00.
    #
    # ⚠ **WRITTEN HERE AND ON NO OTHER PATH, AND ONLY FOR `required`.**
    # `not_required` assessed nothing; a `waived` deposit was assessed and then
    # forgiven by a supervisor, so nothing is still to collect and a figure
    # would make the record demand money the utility chose not to take. Both
    # leave NULL — which this module already distinguishes from `0` everywhere.
    #
    # ⚠ **IT IS NOT A SECOND WRITER OF THE REGISTER.** `BR-CUS-1050` forbids a
    # second writer of `deposit_on_file`; this is a different column, owned by
    # customers, written once inside the creating transaction, and the register
    # is still only ever READ BACK from the payment below.
    if instruction.amount is not None and account.deposit_assessed != instruction.amount:
        account.deposit_assessed = instruction.amount
        account.save(update_fields=["deposit_assessed", "updated_at"])
    out["assessed"] = str(instruction.amount) if instruction.amount is not None else None

    if not instruction.take_now:
        notes.append(DEFERRED_TO_FIRST_BILL)
        return out

    # ── the money, through the module that owns it ──────────────────────────
    recorded = seams.record_deposit_payment(
        actor=actor,
        account_id=account.pk,
        amount=instruction.amount_taken,
        posted_at=_as_datetime(instruction.posted_at) if instruction.posted_at else None,
        method_code=instruction.method_code,
        confirmation=instruction.confirmation,
        idempotency_reference=instruction.idempotency_reference,
    )
    if recorded is None:
        # G20's rule: an unwired seam REPORTS that it could not answer. It
        # never answers "recorded" over a module that published nothing.
        notes.append(PAYMENTS_UNWIRED)
        if warnings is not None:
            warnings.append({"code": PAYMENTS_UNWIRED, "rule": "BR-CUS-037"})
        return out

    out["payment_id"] = recorded.get("payment_id")
    out["payment_no"] = recorded.get("payment_no")
    out["status"] = recorded.get("status")
    out["amount_taken"] = (
        str(instruction.amount_taken) if instruction.amount_taken is not None else None
    )
    # Every code payments reported, forwarded rather than summarised. A deposit
    # whose receipt could not be queued or whose register seam was unwired says
    # so on the confirmation in payments' own words.
    for problem in recorded.get("problems") or ():
        code = problem.get("code") if isinstance(problem, dict) else None
        if code:
            notes.append(code)

    # ⚠ **NO "NOT CLEARED YET" NOTE — `DEF-CUS-10324`.** The payment is
    # `posted` and the register moved at posting (CR-186-BRC10), so the
    # account reads the deposit now; a note saying $0.00 would be false.
    #
    # ⚠ **READ BACK, NOT WRITTEN.** `BR-CUS-670`'s register writer already
    # moved `accounts.deposit_on_file` inside `record_payment`'s transaction;
    # this is the figure it landed on. `held_after` of `None` means payments
    # could not reach the writer at all, and its `problems` above say so by
    # name — so the screen states an absence rather than a figure nobody wrote.
    held = recorded.get("held_after")
    out["held_after"] = str(held) if held is not None else None
    out["held"] = held is not None
    if held is None and warnings is not None:
        warnings.append({"code": "deposit_register_not_moved", "rule": "BR-CUS-670"})
    # The account row was written under a lock by the register writer, so this
    # process's copy is one version behind and the response snapshot is built
    # from it. Refreshed rather than re-read: the value is already correct in
    # the database and re-deriving it here would be the second writer again.
    account.refresh_from_db(fields=["deposit_on_file", "deposit_received_on"])
    return out


def _keep_size_pick(actor: Any, account: Any, standard: dict[str, Any]) -> None:
    """**THE SIZE THE CLERK PICKED, KEPT AND AUDITED — `DEF-CUS-9521`.**

    PO 2026-10-04, verbatim: *"(c) Let the clerk pick the size on the Deposit
    step."* Written only when rating priced the deposit at a PICKED size (no
    meter size recorded) — on a take, a first-bill deferral or a waive alike,
    because each of them assessed a figure from that size. Three columns set
    together inside the creating transaction (the first bill reads the size
    back), and one `audit_log` row naming who, which size and why — CLAUDE.md
    rule 7. Worked: Rosa, no meter, 2" picked → `W-2`, *Water 2"*, $600.00.
    """
    from core import audit as core_audit

    size = standard.get("size_class")
    account.deposit_size_class = size
    account.deposit_size_picked_at = dj_timezone.now()
    account.deposit_size_picked_by_id = getattr(actor, "id", None) or getattr(actor, "pk", None)
    account.save(
        update_fields=[
            "deposit_size_class",
            "deposit_size_picked_at",
            "deposit_size_picked_by",
            "updated_at",
        ]
    )
    core_audit.write_row(
        action=SIZE_PICKED_ACTION,
        entity_type="account",
        entity_id=account.pk,
        actor_user_id=account.deposit_size_picked_by_id,
        after={
            "size_class": size,
            "size": standard.get("size_label") or size,
            "amount": str(standard.get("amount")),
            "reason": SIZE_PICKED_REASON,
        },
    )
