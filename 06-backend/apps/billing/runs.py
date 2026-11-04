# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-001 (S31.1 — scope a run) · US-BIL-002 (S31.2 — "check what
#           we found", the prepare pass) · US-BIL-003 (S31.3 — decide the
#           exceptions)   Screens: S31.1 · S31.2 · S31.3
# Rules:    BR-BIL-039 (stages 1–5 are PURE, so the run gathers first) ·
#           BR-BIL-015 (a missing input is an EXCEPTION a human decides, never
#           a silent skip) · BR-BIL-005 (a run is idempotent on its key) ·
#           BR-CUS-055 (behaviour classes decide who is billed at all) ·
#           BR-MET-033 (cycle membership follows the route) · BR-RAT-007
#           (price on the SERVICE date) · BR-BIL-070 (the bill date a clerk
#           types is STORED and USED, and it IS the run's service date — PO
#           2026-08-11, OQ-122 option A) · BR-MET-024 (a read with an uncleared
#           DISPUTE marker HOLDS its account out of the run until a System Admin
#           clears it — OQ-043 closure, PO R6) · BR-TEN-043 (event time is an
#           argument; a typed date is one, a clock is not) · CLAUDE.md rule 3
#           (a quantity carries its unit)
# Tests:    06-backend/tests/test_us_bil_001_prepare.py
# Impacts:  apps/billing/stages/** (consume what this gathers) · S31.2's
#           findings tabs and S31.3's exception list render exactly this
# ───────────────────────────────────────────────────────
"""Phases 1 and 2 of the run the PO described: build the data, then bill it.

The PO stated the whole shape on 2026-08-11, and the ordering is the design:

    *"we build the data first for billing show all that data on screen for
    user so that all the decisions are made on screen and recorded, in case
    any data should be changed, he is able to do it; once all billing data
    exceptions, decisions are made, then run the billing in batch process in
    the background …"*

`prepare_run` is the first clause and `calculate_account` is the second. The
first resolves WHO the run covers, gathers everything needed to bill each of
them, and returns both halves — the accounts that are ready and the ones that
are not, each with a reason a human can act on. **It writes nothing.** Not a
draft, not an exclusion row, not a status change. A prepare pass that wrote
would make "let me look at this first" a committing action, and the PO's
sentence is explicitly about looking first.

The second runs stages 1 → 2 → 3-5 → 6 for ONE account and leaves a DRAFT
bill. One account is the unit of atomicity on purpose: a run of 500 where
number 7 fails must leave 499 drafts and one named break, never a rollback of
the morning's work.

Phases 3, 4 and 5 — the break list, the summary, the release gate — are not
here. `BillRunRelease` is their record and exists; the code that fills it does
not.

WHY "READY" AND "BLOCKED" COME BACK TOGETHER
--------------------------------------------
The tempting shape is to raise on the first account that cannot be gathered.
That would be wrong twice over: a run of 500 accounts where account 7 has no
meter would show the clerk nothing about the other 493, and the one number
they most need — *how many are ready* — would not exist. So every account is
attempted, every failure is caught with its reason code, and the result
carries both lists. One bad account never hides the run.

WHAT THIS DELIBERATELY DOES NOT DECIDE
---------------------------------------
Three things arrive here as facts and leave as facts, because each is the
staff's call and the PO said so:

  * **Base-only accounts** (vacation hold, suspended). BR-CUS-055 says they
    bill base charges; the PO's refinement is *"this is decision user make
    hence during pre billing process, you have to give option to user to opt
    in or opt out"*. They are gathered and FLAGGED, never filtered.
  * **Missing reads.** BR-BIL-015 makes these a decision — estimate, hold, or
    bill without the service. The account is gathered with the absence
    carried on it, and stays in the run until a human says otherwise.
  * **Zero usage.** A real zero is a real bill. This module does not conflate
    it with a missing read, which is the single most common way a utility
    bills a customer for nothing (or fails to bill them at all).

Everything cross-module goes through the owning module's selector by name
(B1). A module that has not published one produces a NAMED problem on the
account, never a default and never a crash.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING (2026-09-14, `DEF-BIL-5270` + `DEF-BIL-5271`) — three
NEW things in this file decide money and each has a row in
`12-governance/09-human-review-ledger.md`:

  * **the billed-through anchor** (`billed_positions`, `_anchor_quantity`) —
    it decides the register a period OPENS at, and therefore how much of a
    customer's real consumption is billed at all. PO ruling 2026-09-14: the
    period opens at the last ISSUED bill's closing read, with no clerk choice,
    because *"we cannot create wrong conusmption that is loss"*. Its four
    refusals (`ANCHOR_*`) are the other half — anchoring across a meter
    exchange or a register wrap would bill a FICTION, which is the mirror of
    the loss the rule prevents;
  * **the calendar anchor** (`period_anchor`, `_continuity_decisions`) — the
    one half that IS a decision, because a gap in the DATES can be lawful;
  * **the phase-4 gate** (`stale_drafts`, `refuse_stale_drafts`) — it decides
    whether a run may be authorised;
  * **the scoped re-price** (`reprice_accounts`, `calculate_run`'s
    `only_accounts`) — it decides which drafts a decision replaces;
  * **(2026-09-30, bulk Check engine) the answers a pass may use**
    (`_ANSWERS`, `_rollover_suggestion`, the ×1 branch of `_anchor_quantity`,
    `_UNIT_FROM_METER`) and **`price_date`** (BR-BIL-1055) — ledger section
    *"BULK CHECK ENGINE — PRICE AT PERIOD END, THE CHECK STORE, THE ANSWERS A
    PASS MAY USE"*.

⚠ **THE ANCHOR NOW MOVES A QUANTITY, AND THAT IS NEW SINCE THE FIRST VERSION OF
THIS NOTE.** It was true that nothing here computed a figure while the register
case was a DECISION; under the ruling it is not. `_anchor_quantity` recomputes
one number — `(current − anchor) × multiplier`, on the anchored period only —
and the worked case is `14,212 − 13,500 = 712` where metering stored 412.
**No B4/B5 rule is touched even so**: the subtraction is BR-MET-019's own, the
multiplier is the factor metering published as USED (BR-MET-500), no rounding
decision is taken and no price is read. The gate still only COMPARES two stored
timestamps and the re-price still calls the same engine a full run calls. Stated
plainly so a reviewer looks in the right place: the money math is one
subtraction, and its inputs are all stored facts.
"""

from __future__ import annotations

import logging
from calendar import monthrange
from contextvars import ContextVar
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import Count, Max, Q

from apps.billing import (
    bill_warnings,
    counted_service_line,
    gather,
    midperiod,
    models,
    rating_seam,
    seam_batch,
)
from apps.billing.contracts import AccountBillingData, ServiceReading
from apps.billing.exceptions import BillingRuleError
from apps.billing.gather import GatherProblem
from apps.billing.rating_seam import Quantity, WindowQuantity
from apps.billing.stages import measure_consumption as measure_consumption_stage
from apps.billing.stages.assemble_document import assemble_document
from apps.billing.stages.measure_consumption import measure_consumption
from apps.billing.stages.resolve_subscription import resolve_subscription
from core import audit, idempotency
from core import batch_reads
from core import jobs as core_jobs
from core import numbering as core_numbering
from core import errors as core_errors
from core import tenancy as core_tenancy

logger = logging.getLogger("smartbillhub.billing")

#: Problems the run itself finds, distinct from the GATHER_* reason codes that
#: describe one account's own data. These are about the RUN's shape.
RUN_NO_SCOPE = "cycle_has_no_service_points"
RUN_UNIT_HAS_NO_ACCOUNT = "unit_has_no_billable_account"
RUN_READS_UNAVAILABLE = "metering_has_not_published_reads"
#: One day. `DEF-BIL-5270`'s boundaries are INCLUSIVE at both ends, the same
#: `BR-CUS-103` boundary `cut_bill.ONE_DAY` steps — the first unbilled day is
#: the day AFTER the last issued period end — so this module steps by a day
#: rather than writing the literal into an expression. Declared here rather
#: than imported from `cut_bill`, which imports THIS module.
ONE_DAY = timedelta(days=1)

#: ── `DEF-BIL-5270` · WHEN THE ANCHOR CANNOT BE TRUSTED (PO 2026-09-14) ────
#: The ruling makes the period OPEN at the last issued bill's closing read, with
#: no clerk choice — *"we cannot create wrong conusmption that is loss"*. These
#: four are its other half: the cases where anchoring blindly would bill a
#: FICTION, which is the exact mirror of the loss the rule prevents. Each is a
#: BLOCK and not a decision, for the same reason the anchor is not a decision:
#: there is no defensible second outcome, and the repair is in Meter Reads
#: rather than on this screen.
ANCHOR_METER_EXCHANGED = "anchor_meter_exchanged"
ANCHOR_REGISTER_WENT_BACKWARDS = "anchor_register_went_backwards"
ANCHOR_MULTIPLIER_UNSTATED = "anchor_multiplier_unstated"
ANCHOR_TOU_UNANCHORABLE = "anchor_tou_windows_unanchorable"

#: `BR-BIL-1025` — an account the run EXAMINED and found nothing to charge for.
#: **This is not a problem and never reaches the exceptions screen.** PO ruling
#: 2026-08-31 (`CR-056` ruling 1), consequence 1: *"A silent Master Account must
#: NEVER reach the exceptions screen. That screen exists to catch a metered
#: service point with nobody to bill. This is the opposite: the correct state,
#: for most master accounts most months. Leave it firing and every owner-occupier
#: in the book is a false alarm every month."* It is a REASON rather than a bare
#: count so the screen can say WHICH accounts were quiet, in words.
RUN_NOTHING_TO_BILL = "account_has_nothing_to_bill"
#: Phase 2. An account that reached calculate still carrying a decision
#: nobody took — the run breaks it rather than choosing for the clerk.
CALC_UNRESOLVED_READ = "missing_read_undecided_at_calculate"
#: **BR-RAT-090 (DEF-1813)** — an UNMETERED service is billed by a count of its
#: assets on the unit and no count could be determined. Its own reason rather
#: than `CALC_UNRESOLVED_READ`, because the two send a clerk to two different
#: places: a missing read is estimated on the Reads tab, and a missing count is
#: fixed by going and counting the carts on the unit. Deliberately NOT retryable
#: from the run screen for that reason.
CALC_ASSET_COUNT_UNAVAILABLE = "unmetered_asset_count_undetermined"
#: **CR-062 D1/H2** — a service billed on the SUM of its installed capacity has
#: equipment on the unit that does not say how much capacity it is, so the total
#: cannot be stated. Its own reason rather than `CALC_ASSET_COUNT_UNAVAILABLE`
#: for that constant's own reason, one step further on: the count IS known here
#: — three panels stand on the unit — and counting them again fixes nothing. The
#: work is to record each panel's size class, which is a different screen and a
#: different person. Deliberately NOT retryable from the run screen.
CALC_INSTALLED_CAPACITY_UNRESOLVED = "installed_capacity_undetermined"
#: Phase 2. Rating looked at this account and refused (DEF-047). Its own reason
#: rides on the break's detail; the code is one group on the phase-3 screen
#: because the fix for all of them is in Plans & Rates rather than in the run.
PRICING_REFUSED = "rating_refused_to_price"
#: Phase 1. One of this unit's readings is DISPUTED and nobody has cleared it.
#: OQ-043's closure (PO R6), verbatim: *"record+flag, hold account from run
#: until SysAdmin clears"*; BR-MET-024 says the same. So the account leaves the
#: run — it is not a decision a clerk takes on S31.3, it is a hold only a System
#: Admin lifts, and it is grouped separately from a missing read for exactly
#: that reason: the fix is in Reads, by a different person, on a different
#: screen. Added 2026-08-16 with metering's dispute writer; before it, a
#: disputed read billed as if it had been agreed, which is DEF-046's real cost.
RUN_ACCOUNT_HELD_BY_DISPUTE = "account_held_by_disputed_read"
#: Phase 1. A reading arrived with a quantity and NO UNIT (CLAUDE.md rule 3).
#: ⚠ **IT WAS A PLAIN `BillingRuleError` UNTIL 2026-09-30 AND IT ENDED THE WHOLE
#: PASS** (`DEF-BIL-8207`): one unitless read on one account refused every
#: other account in the cycle. It is a `GatherProblem` now — a subclass of
#: `BillingRuleError`, so every caller that caught the old refusal still does —
#: and a bill run records it against THAT account (BR-BIL-1052).
READ_HAS_NO_UNIT = "reading_and_meter_have_no_unit"

#: ── PO ruling 2026-09-30 (decision log *"A PROBLEM NEVER STOPS THE
#: CHECKING"*, item 2) — A READING STORED WITHOUT A UNIT TAKES THE UNIT
#: RECORDED ON ITS METER, WITH A WARNING. PO verbatim: *"take correct unit as
#: default and put them in"*. Not an assumption under rule 3: the meter's unit
#: of measure is an explicit recorded fact (`assets.unit`), which metering
#: publishes on the reads row as `meter_unit` only when the read itself carries
#: none. **Applied ONLY while a Check has opened this collector** (the bulk
#: run's per-account pass, `check_engine`): every other caller of the reads
#: seam — single bill, back-bill, one-time — keeps the refusal, because the
#: ruling was made for the Check and a silent fallback on a path with nobody
#: to see the warning would be exactly the silent default rule 3 forbids.
#: Where the meter records no unit either, the service is refused as before.
_UNIT_FROM_METER: ContextVar[list | None] = ContextVar("billing_unit_from_meter", default=None)


def open_unit_from_meter() -> Any:
    """Open the Check's unit-from-meter collector; returns the reset token."""
    return _UNIT_FROM_METER.set([])


def taken_units() -> tuple[dict[str, Any], ...]:
    """What the open collector recorded — `{service_code, unit, unit_id}` each."""
    return tuple(_UNIT_FROM_METER.get() or ())


def close_unit_from_meter(token: Any) -> None:
    _UNIT_FROM_METER.reset(token)


#: ── PO rulings 2026-09-30 (changes rows 44–46) · A CLERK'S ANSWER FEEDS THE
#: NEXT PASS ─────────────────────────────────────────────────────────────────
#: *"this should be decision by clark - we point it out and suggest but dont
#: make it auto"*. Two anchor refusals now carry a SUGGESTED quantity — a
#: register wrap the meter's own digits prove (`possible_rollover`, e.g.
#: 99,950 → 00,120 on a 5-digit dial = **170**), and the ×1 figure for a read
#: whose multiplier is unstated (`anchor_multiplier_unstated`, default HOLD) —
#: and **neither is ever used unless a clerk recorded the answer**. The answers
#: a pass may use are loaded here by `selectors.prepared_for` from the run's
#: recorded decisions (`decisions.anchor_answers_for`); on every other caller
#: the map is empty and the refusal is exactly what it was.
#: Keyed `(account_id, service_code, case) -> choice`.
_ANSWERS: ContextVar[dict | None] = ContextVar("billing_check_answers", default=None)
_ACCOUNT_IN_PLAY: ContextVar[str | None] = ContextVar("billing_account_in_play", default=None)

#: The choices that USE the suggestion (see `decisions.CHOICES_BY_CASE`).
ANSWER_ACCEPT = "accept_suggestion"
ANSWER_MULTIPLIER_ONE = "bill_with_multiplier_1"
POSSIBLE_ROLLOVER = "possible_rollover"
#: DEF-BIL-9077 — the clerk sentence for a rollover held with no last-bill
#: anchor (`_across_rollover`); the one-time screen shows its Accept control
#: beside it.
ROLLOVER_HELD_KEY = "billing.oneTime.err.rolloverHeld"
#: 🔒 `DEF-BIL-8244` (changes rows 44–46, PO 2026-09-30) — the meter was
#: exchanged inside the period and BOTH parts are recorded (the old meter's
#: final reading and the new meter's first). Suggested answer: bill both parts;
#: used only when a clerk accepted it (`_meter_swap`).
METER_SWAPPED = "meter_swapped"


def open_answers(answers: dict | None) -> Any:
    return _ANSWERS.set(dict(answers or {}))


def close_answers(token: Any) -> None:
    _ANSWERS.reset(token)


#: ── changes row 44 (PO 2026-09-30) · NO MULTIPLIER, ON THE RULED PATH ─────
#: *"no multiplier → Hold (default) / Bill with multiplier 1"*. A meter that
#: has never been read has no billable read for metering to answer a factor
#: from (`metering.billing_multiplier_for` answers from the latest head), and a
#: missing factor is never 1 (BR-MET-056). The ruled path's adapter
#: (`resolution_shadow.adapt`) refused it as *"ruled path refused"*, a BLOCK
#: with no answer — so the account could never reach the clerk's choice. Inside
#: a Check pass it is now THIS decision, in its own tag; a clerk's ×1 is the only
#: thing that ever puts a 1 into the adapter. Distinct from
#: `ANCHOR_MULTIPLIER_UNSTATED`, which is the anchored-period read's factor.
METER_HAS_NO_MULTIPLIER = "meter_has_no_multiplier"

#: True while `check_engine.check_account` runs an account's pass — the Check
#: and the Calculate pass, both `prepare_run`. The ONLY place a clerk can answer
#: the no-multiplier question, so the only place it is put as one; every other
#: caller (single, first, one-time, back-bill) keeps the adapter's refusal.
_CHECK_PASS: ContextVar[bool] = ContextVar("billing_check_pass", default=False)


def open_check_pass() -> Any:
    return _CHECK_PASS.set(True)


def close_check_pass(token: Any) -> None:
    _CHECK_PASS.reset(token)


def in_check_pass() -> bool:
    return _CHECK_PASS.get()


#: The services a clerk's *Bill with multiplier 1* was APPLIED to in this pass —
#: so the Check keeps the decision on the account, answered, instead of losing
#: it the moment the answer lets the gather through (changes row 44: *"Re-check
#: must not lose it"*). Opened by `check_engine` around the gather.
_MULTIPLIER_ONE_USED: ContextVar[set | None] = ContextVar(
    "billing_multiplier_one_used", default=None
)


def open_multiplier_one_used() -> Any:
    return _MULTIPLIER_ONE_USED.set(set())


def multiplier_one_used() -> tuple[str, ...]:
    return tuple(sorted(_MULTIPLIER_ONE_USED.get() or ()))


def close_multiplier_one_used(token: Any) -> None:
    _MULTIPLIER_ONE_USED.reset(token)


def note_multiplier_one(service_code: str) -> None:
    used = _MULTIPLIER_ONE_USED.get()
    if used is not None:
        used.add(str(service_code))


def clerk_answer(account_id: Any, service_code: Any, case: str) -> str | None:
    """The recorded answer for `case` on this account and service, or None —
    `_answered` with the account NAMED rather than read from the readings
    pass's context (the ruled path runs after that context is reset)."""
    token = _ACCOUNT_IN_PLAY.set(str(account_id) if account_id is not None else None)
    try:
        return _answered(service_code, case)
    finally:
        _ACCOUNT_IN_PLAY.reset(token)


def _answered(service_code: Any, case: str) -> str | None:
    answers = _ANSWERS.get() or {}
    account = _ACCOUNT_IN_PLAY.get()
    if not answers or account is None:
        return None
    # A per-account answer (for this service, then for the account) wins; the
    # tag's *Answer for all N* is keyed `("*", "", case)`.
    return (
        answers.get((str(account), str(service_code or ""), case))
        or answers.get((str(account), "", case))
        or answers.get(("*", "", case))
    )


def _register_digits_for(read_id: Any) -> int | None:
    reader = _resolve("metering", "register_digits_for_read")
    if reader is None or not read_id:
        return None
    try:
        digits = reader(read_id)
    except Exception:  # noqa: BLE001 — no span means no suggestion, never a guess
        return None
    return int(digits) if digits else None


#: B21 — the modules a utility-wide stop can name, as the clerk knows them.
MODULE_METER_READS = "meter_reads"
MODULE_CUSTOMERS = "customers"
MODULE_PAYMENTS = "payments"


class UtilityWideStop(BillingRuleError):
    """A fault that is not ANY one account's — a module not answering.

    Plan B21 / changes row 24: *"utility-wide stops say what and who;
    unexpected errors give a support reference; the run is always kept"*.
    `module` is WHAT (one of the `MODULE_*` names above), `who` is who can
    act on it, and `support_ref` is the reference a clerk reads out to
    support — the same string is in the log beside the traceback. It is a
    `BillingRuleError` so every caller that already turns a rule refusal into
    a catalogue refusal keeps doing so; nothing about it deletes the run.
    """

    def __init__(self, module: str, detail: str, *, who: str = "support") -> None:
        from apps.billing import check_engine

        super().__init__(detail)
        self.module = module
        self.who = who
        self.support_ref = check_engine.new_support_ref()
        logger.error(
            "bill run check stopped utility-wide: %s not answering (%s) — ref %s",
            module,
            detail,
            self.support_ref,
        )

    @classmethod
    def from_error(cls, module: str, error: BaseException) -> "UtilityWideStop":
        logger.exception("bill run check: %s raised", module, exc_info=error)
        return cls(module, f"{module} did not answer: {type(error).__name__}")

    def as_dict(self) -> dict[str, str]:
        return {
            "module": self.module,
            "who": self.who,
            "support_ref": self.support_ref,
            "message_key": "billing.check.stop.moduleDown",
        }


@dataclass(frozen=True)
class AccountProblem:
    """One account (or one unit) the run cannot bill, and why.

    `reason` is a code, never prose: S31.2 groups its findings tabs on it and
    S31.3 offers different actions per group, so the grouping key has to be
    stable. `detail` is the sentence a human reads underneath.

    `stage` is BR-BIL-040's other half — *"surfaced in the tab that owns that
    stage's inputs (Plans ← stage 1, Reads ← stage 2, …)"* — and it is DERIVED
    here from `STAGE_BY_REASON` rather than passed in at each construction
    site, for one reason worth stating: it was absent until 2026-08-11 and
    S31.2 therefore kept its own reason→tab table, a second copy of a map this
    module already owns, which would drift the day a reason moved stage. One
    map, one owner; the screen reads the answer instead of recomputing it.
    (`runs.Break` has carried its stage since it was written — this closes the
    asymmetry the S31 lane reported.)

    A stage of None is a real answer and not a gap: `cycle_has_no_service_points`
    and `unit_has_no_billable_account` are facts about the RUN's shape and
    `base_only_billing` is a scope decision about who is billed at all — none of
    them is a stage failure, so none is given a stage it does not have. The
    screen renders those where the epic puts them (the Consumers tab).
    """

    reason: str
    detail: str
    account_id: str | None = None
    account_no: str | None = None
    unit_id: str | None = None
    service_code: str | None = None
    #: One of the seven BR-BIL-037 stage names, or None when this problem is
    #: not a stage failure. Derived in __post_init__; an explicit value wins.
    stage: str | None = None
    #: ── `DEF-RAT-7991`, 2026-09-29 — WHOSE SENTENCE `detail` IS ────────────
    #: `detail` above is written for the record and nine of the rating chain's
    #: raise sites put a database uuid in it. `one_time._one_time_preview`
    #: serves this row's `detail` in a **200-response body**, where
    #: `BR-SHL-020 r2`'s stripper cannot see it, so a clerk read four uuids at
    #: once on the One-time bill screen. These three carry rating's own CLERK
    #: sentence — the catalogue key, its facts, the id-free English mirror —
    #: forward without this module composing a word of it. They are None on
    #: every problem this file writes itself, and a serialiser that finds them
    #: empty falls back to `detail`, exactly as it always did.
    message_key: str | None = None
    clerk_detail: str | None = None
    message_params: dict | None = None

    def __post_init__(self) -> None:
        if self.stage is None:
            # frozen dataclass: the ONE write, at construction, so no caller can
            # produce a problem whose stage disagrees with its reason.
            object.__setattr__(self, "stage", STAGE_BY_REASON.get(self.reason))


@dataclass(frozen=True)
class PreparedRun:
    """Phase 1's output — the screen's entire contents, and nothing written.

    `ready` and `blocked` are the two halves the S31.2 tabs render. `decisions`
    is the third: accounts that CAN be billed but that a human should look at
    before they are — a base-only account, a service with no read. They are in
    `ready` as well, because the run bills them once a decision is taken; they
    are listed separately because a screen that does not surface them makes the
    decision by default, which is precisely what the PO's flow forbids.
    """

    cycle_id: str
    period_start: date
    period_end: date
    service_date: date
    cycle_days: int
    scope_services: tuple[str, ...] | None
    ready: tuple[AccountBillingData, ...] = ()
    blocked: tuple[AccountProblem, ...] = ()
    decisions: tuple[AccountProblem, ...] = ()
    #: `BR-BIL-1025` — accounts the run examined and found NOTHING TO CHARGE
    #: for. A fourth list rather than a subset of `blocked`, because the two
    #: mean opposite things to a clerk: `blocked` is *a human must act* and this
    #: is *the correct state, and here is who was quiet*. Empty on every run
    #: that has no owner-occupier master account in scope, which is every run
    #: this product made before 2026-09-01.
    silent: tuple[AccountProblem, ...] = ()
    #: account_id → the units that account's ONE bill covers (BR-CUS-068),
    #: anchor first — the SAME map the prepare loop already resolves for its
    #: scope check, carried out instead of thrown away (CR-038 W8): the read
    #: ANALYSIS walks each ready account's covered units and cannot re-ask
    #: customers, because `covered_unit_ids` takes the Account row this
    #: dataclass deliberately does not hold. Empty for a run prepared by an
    #: older caller; consumers treat absence as "anchor unknown", never guess.
    coverage: dict[str, tuple[str, ...]] = field(default_factory=dict)
    #: ── BR-BIL-1052 (PO 2026-09-30) · EVERY PROBLEM, PER ACCOUNT ──────────
    #: account_id → every `check_engine.Finding` the Check recorded for it —
    #: blocking, decisions and warnings, each under its own tag. `blocked`
    #: above keeps its old meaning (ONE row per blocked account, the first
    #: blocking finding in check order) so every existing consumer reads what
    #: it always read; this is the full list the redrawn Check serves.
    findings: dict[str, tuple[Any, ...]] = field(default_factory=dict)
    #: Warnings on READY accounts (base `$0.00`, no agreements, a unit taken
    #: from the meter, payment warnings) — they bill anyway (`DEF-BIL-8210`).
    warnings: tuple[AccountProblem, ...] = ()
    #: 🔒 BR-BIL-1055 — the date the rate VERSION was chosen at: the period
    #: end on a bulk run, while `service_date` stays the bill date the
    #: documents carry. None on a caller that predates the rule (it priced at
    #: `service_date`, exactly as it always did).
    price_date: date | None = None
    #: The payment facts the payments module declares it cannot answer today
    #: (`apps.payments.bill_run_checks.UNAVAILABLE`), served beside the findings
    #: so a tag that is not checked never reads as *checked and clear*.
    unavailable: tuple[dict[str, str], ...] = ()
    #: PO ruling 2026-09-30 (fixed-charge case 2, *"Waive"*): accounts whose
    #: standing charges a clerk WAIVED for this run, with a reason. Not billed,
    #: NOT in the pending queue (nothing is carried forward) — written by
    #: `decisions.apply_decisions` only; each amount is on its decision row.
    waived: tuple[AccountProblem, ...] = ()

    @property
    def account_count(self) -> int:
        """Every account the run TOUCHED — the denominator on the screen.

        Ready plus blocked plus silent, deduplicated on the account: "480 of
        500" is only honest if the 500 counts the ones that failed. `decisions`
        are not added, because those accounts are already in `ready`.

        ⚠ **SILENT ACCOUNTS ARE COUNTED (`BR-BIL-1025`).** They produce no
        document and no exception row, but the run DID touch them, and an
        account that vanished from the denominator would be the same lie the
        `$0.00` bill was: a screen reading *"12 of 12"* on a cycle that examined
        fourteen accounts.
        """
        ids = {data.account_id for data in self.ready}
        ids |= {p.account_id for p in self.blocked if p.account_id}
        ids |= {p.account_id for p in self.silent if p.account_id}
        return len(ids)

    def blocked_by_reason(self) -> dict[str, tuple[AccountProblem, ...]]:
        """The S31.2 findings tabs: one group per reason, insertion-ordered."""
        groups: dict[str, list[AccountProblem]] = {}
        for problem in self.blocked:
            groups.setdefault(problem.reason, []).append(problem)
        return {reason: tuple(items) for reason, items in groups.items()}


def _resolve(module: str, attribute: str, kind: str = "selectors") -> Any:
    """The owning module's callable, or None while it has not published one."""
    return gather._resolve(module, attribute, kind)


def _measured(entry: Any, unit_id: Any, what: str) -> Quantity:
    """One channel's quantity from metering's row, unit ENFORCED (rule 3).

    The same refusal the main consumption gets, and for the same reason: a
    number with no unit cannot be billed against a tariff's assumed one, and the
    mistake is unfixable once it is on an issued document.
    """
    unit = entry.get("unit")
    if not unit:
        # `DEF-BIL-8207` — a GatherProblem (still a BillingRuleError), so a
        # bill run records it against this account instead of ending the pass.
        raise gather.GatherProblem(
            READ_HAS_NO_UNIT,
            f"unit {unit_id}: the {what} register returned a quantity with no unit "
            "(CLAUDE.md rule 3). The quantity is refused rather than billed against "
            "the tariff's assumed unit.",
            service_code=entry.get("service_code"),
        )
    return Quantity(amount=Decimal(str(entry["consumption"])), unit=unit)


def _chain_read_ids(row: dict[str, Any]) -> tuple[str, ...]:
    """`DEF-BIL-9075` — every reading the row's quantities were summed from.

    The main register's chain and each TOU window's, deduplicated in order.
    Empty on a row metering built without them (a keyed move-out read).
    """
    seen: dict[str, None] = {}
    for read_id in row.get("chain_read_ids") or ():
        seen.setdefault(str(read_id), None)
    for window in row.get("windows") or ():
        for read_id in window.get("chain_read_ids") or ():
            seen.setdefault(str(read_id), None)
    return tuple(seen)


def _across_rollover(row: dict[str, Any], quantity: Quantity) -> dict[str, Any]:
    """🔒 `DEF-BIL-9076` · A METER THAT ROLLED OVER INSIDE THE PERIOD WAITS
    FOR A CLERK — the rule the PO set for the run on 2026-09-30 (changes rows
    45–46, *"Possible rollover"*), applied where there is no last-bill anchor
    to ask it.

    Metering's chain stops at a reading whose dial went backwards and names it
    (`row["rollover"]`, and per TOU window). Without this, a one-time bill had
    nothing to ask the question with and billed only from the rollover onward:
    a 5-digit dial opening at 99,800, wrapping to 240 on 1 Nov and read 700 on
    13 Nov charged **460 kWh** where **900** were used.

    * **Not accepted** → `possible_rollover`, by name: *the meter rolled over —
      accept the rollover first*. Nothing is billed.
    * **Accepted** (`_answered(…, POSSIBLE_ROLLOVER) == ANSWER_ACCEPT`) → the
      period is the chain walked ACROSS the wrap, each register's quantity is
      metering's own (the wrap's 440 is its stored arithmetic, BR-AST-015), and
      the bill opens and prints from the dial before the wrap.

    Returns the row (with the across-wrap figures written in when accepted)
    and, under `_quantity`, the quantity to price. A row with no rollover comes
    back untouched.
    """
    main = row.get("rollover")
    windows = {w.get("channel"): w.get("rollover") for w in row.get("windows") or ()}
    if not main and not any(windows.values()):
        return row
    service_code = row.get("service_code")
    first = main or next(entry for entry in windows.values() if entry)
    if _answered(service_code, POSSIBLE_ROLLOVER) != ANSWER_ACCEPT:
        raise gather.GatherProblem(
            POSSIBLE_ROLLOVER,
            f"service {service_code!r}: the meter rolled over partway through the period "
            f"({first.get('from')} → {first.get('to')} on {first.get('day')}) — accept the "
            "rollover first. Nothing is billed until a clerk does.",
            service_code=service_code,
            # DEF-BIL-9077 — the one-time screen's Accept-rollover control reads
            # these: the meter, the three dials and the usage they imply.
            message_key=ROLLOVER_HELD_KEY,
            clerk_detail="The meter rolled over. Accept it first.",
            message_params={
                "meter": first.get("meter"),
                "from": str(first.get("from")),
                "to": str(first.get("to")),
                "closing": str(first.get("closing")),
                "suggested_quantity": str(main.get("quantity") if main else first.get("quantity")),
                "unit": quantity.unit,
            },
        )
    across = dict(row)
    if main:
        across["prior_value"] = main.get("prior_value")
        across["measured_from"] = main.get("measured_from")
        across["chain_read_ids"] = list(main.get("read_ids") or ())
    across["windows"] = [
        (
            window
            if not window.get("rollover")
            else {
                **window,
                "consumption": window["rollover"]["quantity"],
                "chain_read_ids": list(window["rollover"].get("read_ids") or ()),
            }
        )
        for window in row.get("windows") or ()
    ]
    across["_quantity"] = replace(
        quantity,
        amount=Decimal(str(main["quantity"])) if main else quantity.amount,
        windows=tuple(
            replace(
                window,
                quantity=replace(
                    window.quantity, amount=Decimal(str(windows[window.channel]["quantity"]))
                ),
            )
            if windows.get(window.channel)
            else window
            for window in quantity.windows
        ),
    )
    return across


def _window_quantities(row: dict[str, Any], unit_id: Any) -> tuple[WindowQuantity, ...]:
    """Metering's per-window registers, keyed by CHANNEL (BR-RAT-021).

    Keyed by channel and not by the tenant's window label, deliberately: the
    label is display text a tenant renames, the channel is the register that was
    read. Rating owns the join between them and states its reasoning where it
    makes it (`apps.rating.selectors._window_channels`, OQ-236).
    """
    return tuple(
        WindowQuantity(
            channel=entry["channel"],
            quantity=_measured(entry, unit_id, f"{entry['channel']} window"),
        )
        for entry in row.get("windows") or ()
    )


def _demand_quantity(row: dict[str, Any], unit_id: Any) -> Quantity | None:
    """The period's peak-demand read (BR-RAT-014), in ITS OWN unit — kW, where
    the energy quantity beside it is kWh. None when nothing measured one, which
    rating turns into a named refusal rather than a $0.00 demand line."""
    entry = row.get("demand")
    return None if not entry else _measured(entry, unit_id, "peak-demand")


def _as_date(value: Any) -> date | None:
    """A seam's date as a `date` — metering may hand a `date` or its ISO text."""
    if value is None or isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def readings_for_account(
    account: Any,
    *,
    period_start: date,
    period_end: date,
    scope_services: tuple[str, ...] | None,
    anchor_to_last_billed: bool = False,
    account_id: Any = None,
    keyed_reads: Any = None,
) -> tuple[tuple[ServiceReading, ...], tuple[str, ...]]:
    """What THIS ACCOUNT measured over the period — every unit it covers.

    ⚠ **THE UNIT-SHAPED READ IS THE ONE DEF-571 WAS FILED FOR.** Every caller
    here used to hand `_readings_for` the account's `unit_id`, which is the
    whole truth for an ordinary account and the ANCHOR of a master account
    (BR-CUS-068: one row, `accounts.unit_id` holds exactly one unit per
    BR-CUS-017, the rest covered through open service agreements). So the
    owner of 1408 Elm was billed the hallway's electric and never the shared
    irrigation's water — **$41.20 of a $69.60 obligation**, on a document that
    footed.

    An ordinary account walks ONE unit and produces byte-identical readings to
    the call this replaces; `gather.covered_units` answers `(unit_id,)` for it.

    Duplicate service codes across covered units are DEDUPED anchor-first
    rather than merged: `gather_account` refuses that coverage by name (OQ-334
    — nothing signed says whether a second connection brings its own base
    charge), and inventing a merge here would answer the open question in the
    one place nobody would look for it.
    """
    readings: list[ServiceReading] = []
    # ⚠ **KEYED BY (SERVICE, METER) SINCE 2026-09-30.** PO: *"both meter should
    # be build in metered case also - as a speearte line"*. Metering publishes
    # one row per meter where a metered point carries two, each naming its
    # `asset_id`; keyed by the service code alone this loop kept the FIRST and
    # dropped the second (`$29.20` billed for two meters owing `$58.40`). A row
    # naming no meter keys as `(code, None)`, so every account with one meter
    # per service dedupes exactly as before.
    seen: set[tuple[str, str | None]] = set()
    # ── `DEF-BIL-5270` · WHERE DOES THIS PERIOD OPEN? (PO ruling 2026-09-14) ─
    # `anchor_to_last_billed` is FALSE by default and true on exactly one
    # caller, the cycle run. A BACK-BILL deliberately re-bills a past window and
    # a SINGLE bill names its own, so anchoring either to the account's LAST
    # issued bill would move a window its caller chose on purpose. Those two
    # paths are byte-identical to before; stated rather than implied, and
    # REPORTED as the question they are.
    anchor_window = (
        last_issued_window(account_id if account_id is not None else account.id)
        if anchor_to_last_billed
        else None
    )
    in_play = _ACCOUNT_IN_PLAY.set(str(account_id if account_id is not None else account.id))
    try:
        return _readings_for_account_units(
            account,
            anchor_window=anchor_window,
            account_id=account_id,
            period_start=period_start,
            period_end=period_end,
            scope_services=scope_services,
            keyed_reads=keyed_reads,
            readings=readings,
            seen=seen,
        )
    finally:
        _ACCOUNT_IN_PLAY.reset(in_play)


def _readings_for_account_units(
    account: Any,
    *,
    anchor_window: Any,
    account_id: Any,
    period_start: date,
    period_end: date,
    scope_services: tuple[str, ...] | None,
    keyed_reads: Any,
    readings: list,
    seen: set,
) -> tuple[tuple[ServiceReading, ...], tuple[str, ...]]:
    """`readings_for_account`'s walk over the covered units — split out so the
    account in play (`_ACCOUNT_IN_PLAY`) is set around it and reset after."""
    for unit_id in gather.covered_units(account):
        positions = (
            billed_positions(
                account_id if account_id is not None else account.id,
                unit_id,
                anchor_window=anchor_window,
                period_end=period_end,
                scope_services=scope_services,
            )
            if anchor_window is not None
            else {}
        )
        unit_readings, _unit_unmeasured = _readings_for(
            unit_id,
            period_start=period_start,
            period_end=period_end,
            scope_services=scope_services,
            positions=positions,
            keyed_reads=keyed_reads,
        )
        for reading in unit_readings:
            key = (reading.service_code, getattr(reading, "asset_id", None))
            if key in seen:
                continue
            seen.add(key)
            readings.append(reading)
    # Derived from the MERGED readings rather than unioned from each unit's
    # own list: a service the anchor could not measure and a covered area did
    # is measured for this bill, and two lists could disagree about that.
    unmeasured = tuple(
        reading.service_code
        for reading in readings
        if reading.consumption is None and reading.service_code
    )
    return tuple(readings), unmeasured


#: 🔒 `DEF-BIL-10067` — the two per-entry OPTIONS a `keyed_reads` entry may
#: carry into metering's overlay, spelled as metering spells them
#: (`apps.metering.selectors.KEYED_WINS_OVER_COMMITTED` / `KEYED_SAVED_ONLY`;
#: a test pins the two spellings together). Only the ONE-TIME BILL sets them
#: (`one_time.provisional_reads` / `one_time.saved_typed_reads`): its typed
#: reading beats a committed read in the period, and its draft prices only on
#: the reading step 2's Continue saved. The move-out wizard sets neither.
KEYED_WINS_OVER_COMMITTED = "wins_over_committed"
KEYED_SAVED_ONLY = "saved_reads_only"


def typed_reads_win(keyed_reads: Any) -> bool:
    """True when `keyed_reads` came from the one-time bill (`DEF-BIL-10067`)."""
    return any(
        isinstance(entry, dict) and entry.get(KEYED_WINS_OVER_COMMITTED)
        for entry in (keyed_reads or ())
    )


def _readings_for(
    unit_id: Any,
    *,
    period_start: date,
    period_end: date,
    scope_services: tuple[str, ...] | None,
    positions: "dict[str, BilledPosition] | None" = None,
    keyed_reads: Any = None,
) -> tuple[tuple[ServiceReading, ...], tuple[str, ...]]:
    """This unit's measured position, as the pipeline's contract.

    Returns the readings AND the service codes that came back unmeasured, so
    the caller can raise them as decisions without re-scanning. A missing read
    is not an error here: BR-BIL-015 makes it a choice, and the account stays
    in the run carrying the absence.

    NOTHING IS COERCED TO ZERO. A service with no read arrives with
    `consumption=None` and a reason, all the way to the screen. `Quantity(0)`
    would be a claim that the meter was read and showed no usage, which is a
    different and sometimes very expensive statement.
    """
    # ── `DEF-CUS-5931` · THE READS A CLERK HAS KEYED AND NOBODY HAS WRITTEN ──
    # PO ruling 2026-09-20, verbatim *"option b is correct"*: the move-out
    # wizard prices step 3 from what was keyed on step 2, and the reads commit
    # with the close at step 6 (Billing blueprint p111). `keyed_reads` is
    # `None` on the cycle run, the back-bill run and the test bill, so this
    # branch is not reached by any of them and no ❄️ B4/B5 figure moves.
    # ⚠ The ONE-TIME BILL passes them too — its preview since `DEF-BIL-8300`
    # and its draft since `DEF-BIL-10067` — with the per-entry options above
    # (`KEYED_WINS_OVER_COMMITTED`, `KEYED_SAVED_ONLY`); until 2026-10-12 this
    # comment listed it among the callers that pass none.
    #
    # ⚠ **METERING OVERLAYS IT, NOT THIS FUNCTION.** The factor, the prior
    # register, the rollover branch and BR-MET-052's negative-usage refusal are
    # metering's and are reached through `provisional_reads_for_unit`, which
    # returns the SAME row shape and writes nothing. Computing a quantity here
    # would be billing applying a meter multiplier, which the PO's ruling of
    # 2026-08-11 puts in metering and nowhere else.
    seam = "provisional_reads_for_unit" if keyed_reads else "billing_reads_for_unit"
    reads_for = _resolve("metering", seam)
    if reads_for is None:
        raise gather.GatherProblem(
            RUN_READS_UNAVAILABLE,
            f"metering has not published {seam}, so no "
            "consumption can be read. Nothing is estimated in its absence.",
        )
    extra = {"keyed_reads": keyed_reads} if keyed_reads else {}
    rows = reads_for(
        unit_id,
        period_start=period_start,
        period_end=period_end,
        service_codes=list(scope_services) if scope_services is not None else None,
        **extra,
    )
    readings: list[ServiceReading] = []
    unmeasured: list[str] = []
    for row in rows:
        amount = row.get("consumption")
        unit = row.get("unit")
        # BR-RAT-090 (DEF-1813) — an UNMETERED service's billable quantity is a
        # COUNT of its assets on the unit, and metering publishes that count on
        # this row (`asset_count`, observed at the service-period end date). It
        # is carried onto the reading UNPRICED and WITHOUT A UNIT: three carts
        # is three things, not three of any measure (BR-RAT-036's rule row draws
        # exactly this distinction), and the unit the price is quoted per
        # belongs to the tariff. `stages/measure_consumption.py` turns it into a
        # quantity, because that is the one place the tariff is in hand.
        asset_count = row.get("asset_count")
        anchored_from = None
        anchored_to = None
        meter_parts: tuple[dict[str, Any], ...] = ()
        quantity = None
        if amount is not None:
            collector = _UNIT_FROM_METER.get()
            if not unit and collector is not None and row.get("meter_unit"):
                # PO ruling 2026-09-30 — the METER's recorded unit, with a
                # warning the Check files under `unit_taken_from_meter`. See
                # `_UNIT_FROM_METER` for why only a Check reaches this branch.
                unit = row["meter_unit"]
                collector.append(
                    {
                        "service_code": row.get("service_code"),
                        "unit": unit,
                        "unit_id": str(unit_id),
                    }
                )
            if not unit:
                # CLAUDE.md rule 3. Metering stamps the unit from the asset and
                # never infers it; a number arriving without one means the seam
                # changed, and billing a unitless quantity is unfixable later.
                # `DEF-BIL-8207` — a GatherProblem (still a BillingRuleError):
                # a bill run records it against THIS account, never the run.
                raise gather.GatherProblem(
                    READ_HAS_NO_UNIT,
                    f"unit {unit_id}: service {row.get('service_code')!r} returned a "
                    "consumption with no unit (CLAUDE.md rule 3), and its meter records "
                    "no unit either. The quantity is refused rather than billed against "
                    "the tariff's assumed unit.",
                    service_code=row.get("service_code"),
                )
            quantity = Quantity(
                amount=Decimal(str(amount)),
                unit=unit,
                # The OTHER registers this service point holds (2026-08-16):
                # per-window TOU quantities (BR-RAT-021 — reads arrive PRE-SPLIT)
                # and the max-demand read (BR-RAT-014). Carried faithfully and
                # never invented: a channel metering did not report is absent
                # here, and rating REFUSES a tariff that prices it rather than
                # billing an unread register as zero.
                windows=_window_quantities(row, unit_id),
                demand=_demand_quantity(row, unit_id),
            )
            position = (positions or {}).get(row.get("service_code") or "")
            if (
                position is not None
                and row.get("asset_id")
                and position.asset_id is not None
                and str(position.asset_id) != str(row.get("asset_id"))
            ):
                # 2026-09-30 — a service split per meter. The position is the
                # SERVICE's, taken on ONE meter; anchoring another meter's
                # register to it would subtract two registers (the exchange
                # refusal's own arithmetic). It anchors only the meter it was
                # taken on. Per-meter positions are not built — stated, not
                # guessed.
                position = None
            # 🔒 DEF-BIL-8244 — a meter exchanged inside the period with BOTH
            # parts recorded is two parts on this one bill, not an anchor
            # across two registers. Anything short of both parts falls through
            # to `_anchor_quantity`, whose exchange refusal is the ruled
            # "Estimate the missing part / Hold" decision.
            # 🔒 DEF-BIL-9076 — a rollover INSIDE the period. With a last-bill
            # anchor the anchor already asks (`_anchor_quantity`); without one
            # (a one-time bill, a first bill) it is asked HERE, so the bill is
            # held rather than charged from the rollover onward.
            if position is None or position.closed_at is None:
                row = _across_rollover(row, quantity)
                quantity = row.pop("_quantity", quantity)
            swap = _meter_swap(quantity, row, position)
            if swap is not None:
                quantity, meter_parts = swap
            else:
                quantity, anchored_from, anchored_to = _anchor_quantity(quantity, row, position)
        else:
            unmeasured.append(row.get("service_code"))
        reading = (
            ServiceReading(
                service_code=row.get("service_code"),
                service_id=row.get("service_id"),
                consumption=quantity,
                estimated=bool(row.get("estimated")),
                absent_reason=row.get("absent_reason"),
                # `DEF-BIL-5270` — the register this period ACTUALLY opens
                # at. Where the anchor moved it, this is the anchor and not
                # metering's stored prior, because `BR-BIL-030` prints the
                # pair on the bill and 13,800 -> 14,212 charging 712 would
                # be a document that does not foot.
                # 🔒 DEF-BIL-8244 — on a swap the one pair would not foot
                # (0 → 85 charging 205), so the pair moves into `meter_parts`,
                # one prior/current per meter, and this pair is left empty.
                prior_read=(
                    None
                    if meter_parts
                    else row.get("prior_value") if anchored_from is None else anchored_to
                ),
                current_read=None if meter_parts else row.get("current_value"),
                meter_parts=meter_parts,
                # DEF-098: the row has ALWAYS carried this and billing has
                # always thrown it away. It is what issue hands to
                # `mark_read_billed`, and without it BR-MET-053's BILLED lock
                # is unreachable from the only module that can apply it.
                read_id=row.get("read_id"),
                # BR-RAT-090 — what a counted line was counted FROM, so a
                # quantity that was OBSERVED stays distinguishable from one that
                # was read or estimated all the way to the document.
                asset_count=asset_count,
                # CR-062 D1/H2 — the OTHER arithmetic a capacity service has.
                # Metering publishes HOW MUCH is installed beside HOW MANY, with
                # the unit the total is in; `stages/measure_consumption.py`
                # picks between them where the tariff is in hand. Carried
                # UNPRICED and never combined here: a 14 kW total and a count of
                # 3 describe the same three panels, and which one bills depends
                # on the unit the schedule quotes its price per.
                installed_capacity=row.get("installed_capacity"),
                capacity_uom=row.get("capacity_uom"),
                # DEF-RAT-10220 — the assets the total could not be stated over.
                capacity_unresolved_assets=tuple(row.get("capacity_unresolved_assets") or ()),
                # CR-063 C3/C5 — the COUNT SPLIT BY SIZE, for the pair of
                # capacity services whose price is picked by the size rather
                # than multiplied by a capacity (trash and fire). Carried
                # UNPRICED and never combined here, exactly as the count and the
                # capacity above are: which of the three a bill uses is decided
                # where the TARIFF is in hand.
                asset_size_counts=row.get("asset_size_counts"),
                # `DEF-BIL-5270` — what metering's own read counted up from,
                # kept ONLY where the anchor moved the period off it. `None`
                # everywhere else, which is every reading on a first bill and
                # every reading already continuous.
                unanchored_prior_read=anchored_from,
                # `DEF-CUS-5931` — keyed, not committed. False on every row
                # metering returns from a committed head, which is every row
                # every other caller here ever sees.
                provisional=bool(row.get("provisional")),
                # BR-MET-500's factor, carried at last (`DEF-098`'s shape one
                # field along). Read only on a provisional row — see the
                # contract's own note and `DEF-CUS-5935`.
                multiplier=row.get("multiplier"),
                # 2026-09-30 — the meter, where metering split a metered point
                # per meter (two meters = two lines). None everywhere else.
                asset_id=row.get("asset_id"),
                # DEF-BIL-8324 — the day the read measures from.
                measured_from=_as_date(row.get("measured_from")),
                # 🔒 DEF-MET-10163 — a later actual already covers this period;
                # `_decisions_for` raises no missing read for it and
                # `decisions._apply_to_account` defers its usage to the next
                # bill instead of estimating it.
                covered_by_read_id=row.get("covered_by_read_id"),
                # 🔒 DEF-BIL-9075 — every reading this quantity was summed from
                # (the closing one first), so issue locks them all.
                chain_read_ids=_chain_read_ids(row),
                # 🔒 DEF-RAT-8849 — every register reading in the period, for
                # `gather`'s season-change-day cut. Carried, never priced here.
                period_registers=tuple(row.get("period_registers") or ()),
            )
        )
        if meter_parts and quantity is not None:
            # 🔒 PO 2026-10-01, *"B · Price each meter separately"*
            # (BR-BIL-1062) — the swap's two parts become ONE READING PER METER,
            # each with its own register pair, quantity, read and meter, so
            # each is priced as its own meter and climbs the tiers from the
            # bottom (`gather._swapped_services` keeps the base on the first).
            # Worked: old 120 kWh + new 80 kWh on tiers 0–100 @ $0.10 / $0.15
            # → $13.00 + $8.00 = $21.00, not 200 priced once at $25.00.
            readings.extend(_one_reading_per_meter_part(reading, quantity, meter_parts))
        else:
            readings.append(reading)
    return tuple(readings), tuple(code for code in unmeasured if code)


def _one_reading_per_meter_part(
    reading: ServiceReading, quantity: Quantity, meter_parts: tuple[dict[str, Any], ...]
) -> list[ServiceReading]:
    """🔒 A swapped meter's reading, split into one reading per meter part.

    Each part keeps the service, the flags and the unit of the read being
    priced, and takes its OWN quantity, register pair (`from` → `to`, so each
    line foots), read id (so BR-MET-053's lock reaches both reads) and meter
    (`asset_id`, which `gather._meters_by_service` splits the tariff on).
    `meter_parts` on each holds that one part, which is how gather and the
    document know the split is a swap and not two in-service meters.
    """
    split: list[ServiceReading] = []
    for part in meter_parts:
        split.append(
            replace(
                reading,
                consumption=replace(
                    quantity, amount=Decimal(str(part["quantity"])), windows=(), demand=None
                ),
                prior_read=part.get("from"),
                current_read=part.get("to"),
                read_id=part.get("read_id"),
                asset_id=part.get("asset_id"),
                meter_parts=(dict(part),),
            )
        )
    return split


# ══════════════════════════════════════════════════════════════════════════
# `DEF-BIL-5270` · DOES THIS ACCOUNT'S CONSUMPTION START WHERE ITS LAST BILL
# STOPPED?
#
# **BILLING DOES NOT COMPUTE THE DELTA AND THAT IS THE WHOLE OF THE DEFECT.**
# `_readings_for` asks metering for a PERIOD and metering answers with a figure
# it stored when the read was taken — `(current − prior) × multiplier`,
# BR-MET-019 — where `prior` is **the previous READ on that meter**. Nothing
# anywhere asked whether that previous read is the one the account's last
# ISSUED bill closed on. A skipped read, a re-read inside the period, a meter
# exchange or a draft that was calculated and never issued all put the two out
# of step, and **the failure is money in BOTH directions**: consumption below
# the anchor was billed twice, consumption above it was billed to nobody.
#
# ⚠ **THE RUN-LEVEL CONTINUITY BAND ON THE SCOPE STEP IS A DIFFERENT CHECK AND
# PASSES RIGHT OVER THIS.** `billRunShared.periodContinuity` compares this
# run's PERIOD with the previous run's period ON THE SAME CYCLE. Both can be
# perfectly contiguous — 1–31 Aug then 1–30 Sep — while one account inside them
# is billed from a register position two reads adrift. One is a fact about the
# RUN's calendar; this is a fact about ONE ACCOUNT's meter, and neither can
# stand in for the other.
#
# **THE SHAPE IS `cut_bill`'s AND IT IS REUSED RATHER THAN REINVENTED.** That
# module already anchors the FINAL bill — *"the first unbilled day is the day
# AFTER the last issued period end"* (`BR-CUS-103`, and `cut_bill.ONE_DAY`
# steps it) — so the cycle path asks the SAME question of the SAME read
# (`selectors.last_issued_invoice_period_end`) and differs in exactly one
# place, named below: an account with no issued bill is NORMAL here and is a
# refusal there.
#
# **IT RAISES A DECISION, NEVER A BLOCK** — `BR-BIL-015`'s posture, because a
# gap is sometimes lawful (a mid-cycle plan change, a catch-up sub-run, an
# account that moved in mid-period) and a clerk is the one who can tell. What
# it may never do is bill silently, which is what it did until today.
# ══════════════════════════════════════════════════════════════════════════

#: The account's reads pick up exactly where its last issued bill left off.
CONTINUITY_ALIGNED = "aligned"
#: Nothing has ever been issued for this account, so there is no anchor to be
#: out of step with. **NOT a pass and not a finding** — it is the honest third
#: answer, and it is kept apart from `aligned` because "we checked and it ties"
#: and "there was nothing to check against" are different facts (the same
#: distinction `periodContinuity` draws with its own `unknown` state).
CONTINUITY_FIRST_BILL = "first_bill"
#: Days, or register units, that no issued bill has covered.
CONTINUITY_GAP = "gap"
#: Days, or register units, that an issued bill has already covered.
CONTINUITY_OVERLAP = "overlap"
#: ⚠ **`CONTINUITY_UNKNOWN` WAS HERE AND IS DELETED (PO ruling 2026-09-14).**
#: It was the REGISTER anchor's fifth state — *the anchor exists and could not
#: be read* — and the register anchor is no longer a state machine a clerk
#: reads: it either anchors or refuses by name (`ANCHOR_*` above). The CALENDAR
#: anchor never had an unknown: a missing issued bill is `first_bill`, which is
#: a different and entirely knowable fact. Removed rather than left unused,
#: because a state nothing can reach is a state the next reader will try to
#: handle.


@dataclass(frozen=True)
class PeriodAnchor:
    """Where this account's billed position sits against this run's period.

    `days` is 0 on every state but `gap` and `overlap`, and on those two it is
    the count of days, INCLUSIVE at both ends — the same inclusive boundary
    `BR-CUS-103` gives the cut bill, so *"2 days were never billed"* means two
    real days and not one-and-a-bit.
    """

    state: str
    billed_through: date | None = None
    days: int = 0
    from_day: date | None = None
    to_day: date | None = None


@dataclass(frozen=True)
class BilledPosition:
    """Where the last ISSUED bill left this service's register, and on which meter.

    `closed_at` is the reading that bill counted up TO — **the number the next
    period must count up FROM** (PO ruling 2026-09-14). `asset_id` is the meter
    it was taken on and `asset_by_read` names the meter behind every read in
    the span, which together make a METER EXCHANGE a published fact rather than
    a guess about two numbers.
    """

    service_code: str
    closed_at: Decimal | None = None
    asset_id: str | None = None
    read_id: str | None = None
    asset_by_read: dict[str, str] = field(default_factory=dict)
    #: 🔒 `DEF-BIL-8244` — every published head in the span, oldest first
    #: (metering's `read_analysis_for_unit` rows, unchanged). A meter exchange
    #: reads the old meter's FINAL reading and the new meter's FIRST from here;
    #: nothing else does. Empty where the position was built without them.
    reads: tuple[dict[str, Any], ...] = ()


def billed_positions(
    account_id: Any,
    unit_id: Any,
    *,
    anchor_window: tuple[date, date],
    period_end: date,
    scope_services: tuple[str, ...] | None,
) -> dict[str, BilledPosition]:
    """Per service: the read the account's last ISSUED bill closed on.

    **THE BILL NAMES ITS OWN READ, AND THAT IS THE PRIMARY SOURCE.** `DEF-098`
    stamps `bill_payload.services[].read_id` at assembly and `BR-BIL-030`
    freezes it at issue, so *which* read priced each service is a stored fact
    rather than something re-derived from a window. This finds that read among
    metering's published heads and takes two things off it: the register it
    reached, and the meter it was taken on.

    ⚠ **WHY `read_analysis_for_unit` AND NOT `billing_reads_for_unit`.** The
    pricing seam answers the single latest head and publishes no asset, so it
    can say what the register reached and can NEVER say whether the meter is
    still the same one. The judgment seam publishes EVERY committed head in a
    window with `asset_id` on each — metering's own words: *"each read names
    its asset, so the caller can see the old meter's final read and the new
    meter's start"*. `DEF-BIL-5269`'s lesson is exactly this: read what the
    owning module publishes about the asset instead of inferring a swap from
    the numbers, because a new meter whose first read happens to sit above the
    old one's last produces a plausible delta and a fiction.

    **ONE CALL PER UNIT, OVER THE WHOLE SPAN** from the anchor bill's period
    start to this period's end, because both facts come out of one list: the
    anchor read is in the first half and this period's read is in the second.
    It REPLACES the extra pricing-seam call the superseded `register_anchors`
    made rather than adding to it, so the cycle run's seam cost does not move.

    A service with no answer is simply ABSENT from the map — never a zero and
    never an assumed alignment. Its reading is then left exactly as metering
    gave it, which is the pre-ruling behaviour and the honest one when nothing
    can be anchored.
    """
    analysis_for = _resolve("metering", "read_analysis_for_unit")
    if analysis_for is None:
        # Metering has not published the judgment seam on this deployment, so
        # no position can be resolved. `{}` anchors nothing and refuses
        # nothing: "we could not look" is not "the meter changed".
        return {}
    try:
        rows = analysis_for(
            unit_id,
            period_start=anchor_window[0],
            period_end=period_end,
            service_codes=list(scope_services) if scope_services is not None else None,
        )
    except Exception as problem:  # noqa: BLE001 — see below
        # A JUDGMENT seam that fails must never take a bill run down: the
        # account still has a lawful bill to produce from what the PRICING seam
        # already returned. Reported as an absent position, which anchors
        # nothing — and logged, because silently un-anchoring is the loss this
        # whole rule exists to prevent and a reader must be able to see it.
        logger.warning(
            "read_analysis_for_unit refused for unit %s (%s: %s); no billed position "
            "resolved and no reading re-anchored",
            unit_id,
            type(problem).__name__,
            problem,
        )
        return {}

    named = _payload_read_ids(account_id)
    positions: dict[str, BilledPosition] = {}
    for row in rows or ():
        service_code = row.get("service_code")
        if not service_code:
            continue
        reads = list(row.get("reads") or ())
        asset_by_read = {
            str(read.get("read_id")): str(read.get("asset_id"))
            for read in reads
            if read.get("read_id") and read.get("asset_id")
        }
        chosen = None
        # 1 — THE READ THE BILL ITSELF NAMED. Authoritative, and it is the one
        #     the arithmetic must continue from even where a later head exists
        #     inside the same window.
        wanted = named.get(service_code)
        if wanted:
            chosen = next((r for r in reads if str(r.get("read_id")) == str(wanted)), None)
        # 2 — no payload, or a bill issued before `DEF-098` stamped one. The
        #     last BILLABLE head at or before the anchor window's end is what
        #     that bill would have priced, by the same latest-head rule the
        #     pricing seam applies. Second best, and stated as such.
        if chosen is None:
            in_window = [
                read
                for read in reads
                if read.get("billable")
                and _read_day(read) is not None
                and _read_day(read) <= anchor_window[1]
            ]
            chosen = in_window[-1] if in_window else None
        if chosen is None:
            continue
        closed_at = chosen.get("current_value")
        positions[service_code] = BilledPosition(
            service_code=service_code,
            closed_at=None if closed_at is None else Decimal(str(closed_at)),
            asset_id=None if chosen.get("asset_id") is None else str(chosen.get("asset_id")),
            read_id=None if chosen.get("read_id") is None else str(chosen.get("read_id")),
            asset_by_read=asset_by_read,
            reads=tuple(reads),
        )
    return positions


def _read_day(row: dict[str, Any]) -> date | None:
    """A published read's own date, or None. Never a clock (BR-TEN-043)."""
    raw = row.get("read_at")
    if not raw:
        return None
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:  # pragma: no cover - defensive
        return None


@batch_reads.memoised(copy=True)
def _payload_read_ids(account_id: Any) -> dict[str, str]:
    """`{service_code: read_id}` off the account's last ISSUED bill.

    `BR-BIL-030` freezes `bill_payload` at issue and `DEF-098` puts the read's
    identity in it, so this is a stored statement about what was billed rather
    than a re-derivation of it. `{}` for a bill carrying no payload, which is
    every bill issued before that stamp existed — the fallback in
    `billed_positions` covers those.

    A fee bill is skipped, as in `last_issued_window` (`DEF-BIL-9254`): it
    names no read, and taking it as "the last bill" would drop the read the
    last SERVICE bill closed on.
    """
    from apps.billing.selectors import NON_SERVICE_BILL_TYPES, billed_position_q

    row = (
        models.Invoice.objects.filter(
            billed_position_q(),  # DEF-CUS-10154 — a live move-out final draft too
            tenant_id=core_tenancy.current_tenant_id(),
            account_id=account_id,
        )
        .exclude(bill_type__in=NON_SERVICE_BILL_TYPES)
        .order_by("-period_end", "-created_at")
        .values_list("bill_payload", flat=True)
        .first()
    )
    return _read_ids_in_payload(row)


def _read_ids_in_payload(row: Any) -> dict[str, str]:
    """`_payload_read_ids`' reading of one stored `bill_payload` — shared with
    the bulk Check's batch read of the same row (`batch_seams`, B27)."""
    if not isinstance(row, dict):
        return {}
    named: dict[str, str] = {}
    for entry in row.get("services") or ():
        code = entry.get("code")
        read_id = entry.get("read_id")
        if code and read_id:
            named[str(code)] = str(read_id)
    return named


def _meter_swap(
    quantity: Quantity,
    row: dict[str, Any],
    position: "BilledPosition | None",
) -> tuple[Quantity, tuple[dict[str, Any], ...]] | None:
    """🔒 `DEF-BIL-8244` · **METER SWAPPED → BILL BOTH PARTS** (PO 2026-09-30).

    The ratified table (changes row 44, *"these are correct"*): *"meter swapped
    → bill both parts when the old meter's final and the new meter's first
    reading are recorded"*; row 45 makes it a DECISION whose suggestion is
    pre-selected and used only once a clerk accepts it (*"we point it out and
    suggest but dont make it auto"*); row 46 names the tag *Meter swapped*.

    **Worked (the test's figures).** The May bill closed old meter M-5278 at
    **13,500**. On 10 June the old meter came out reading **13,620**; the new
    meter went in at **0** and reads **85** on 29 June. Both parts are recorded:

        old part  (13,620 − 13,500) × 1 = 120 kWh
        new part  (85 − 0) × 1          =  85 kWh
        the bill  one electric line of    205 kWh, both parts listed

    **ONE LINE, ONE LADDER, ONE BASE — A JUDGMENT, RECORDED IN THE DECISION
    LOG (2026-09-30, law 13).** A swap is one connection over one period: the
    customer's usage did not change because the utility changed the device. So
    the two parts are SUMMED and priced once — a tiered ladder is not restarted
    and no second base is charged — and the bill carries each meter's own
    prior and current (`meter_parts`), which is what *"two parts on the one
    bill"* shows the customer. Two IN-SERVICE meters on one point are the other
    ruling (each its own line and base, `billing_reads_for_unit`), and never
    reach here: metering splits those rows and names each meter.

    **RETURNS `None` — and `_anchor_quantity` then raises the ratified
    exchange decision (Estimate the missing part / Hold) — whenever a part is
    not RECORDED:** no final reading on the old meter after the one the last
    bill closed on; the new meter's first reading (its start register) not
    recorded; either reading estimated or unbillable; a factor not published
    (BR-MET-500 — never defaulted to 1); a unit that differs from the read's
    (rule 3 — never converted); the old register below where the last bill
    closed (a wrap is not guessed across an exchange); time-of-use windows
    (no per-window position). Nothing here invents a part.

    The arithmetic is the anchor's own — `(current − opening) × factor`, the
    factor being the one metering stored as USED on that read — and the
    readings come off metering's published heads (`read_analysis_for_unit`),
    never off a query of metering's tables.
    """
    if position is None or position.closed_at is None or position.asset_id is None:
        return None
    read_id = row.get("read_id")
    new_asset = position.asset_by_read.get(str(read_id)) if read_id else None
    if new_asset is None or new_asset == position.asset_id:
        return None  # not an exchange: `_anchor_quantity` owns it
    if row.get("current_value") is None or quantity.windows:
        return None
    reads = list(position.reads or ())
    anchor_at = next(
        (i for i, r in enumerate(reads) if str(r.get("read_id")) == str(position.read_id)), None
    )
    this_at = next((i for i, r in enumerate(reads) if str(r.get("read_id")) == str(read_id)), None)
    if anchor_at is None or this_at is None or this_at <= anchor_at:
        return None
    # Same register as the read being priced: the judgment seam also carries
    # a net meter's export and a device's generation rows (BR-MET-135), which
    # the pricing seam excludes and which are never consumption.
    channel = reads[this_at].get("channel")
    between = [r for r in reads[anchor_at + 1 : this_at + 1] if r.get("channel") == channel]

    def usable(read: dict[str, Any]) -> bool:
        return (
            bool(read.get("billable", True))
            and not read.get("estimated")
            and read.get("current_value") is not None
            and read.get("unit") == quantity.unit
        )

    old_reads = [r for r in between if str(r.get("asset_id")) == str(position.asset_id)]
    new_reads = [r for r in between if str(r.get("asset_id")) == str(new_asset)]
    if not old_reads or not new_reads:
        return None
    old_final = old_reads[-1]
    new_first = new_reads[0]
    if not usable(old_final) or not usable(new_reads[-1]):
        return None
    # The new meter's FIRST reading is its start register: the prior its first
    # read counted up from, or — where the install reading was recorded as a
    # read of its own, with no prior — that reading's own register.
    new_start = new_first.get("prior_value")
    if new_start is None and len(new_reads) >= 2 and usable(new_first):
        new_start = new_first.get("current_value")
    if new_start is None or old_final.get("multiplier") is None or row.get("multiplier") is None:
        return None
    old_to = Decimal(str(old_final["current_value"]))
    new_from = Decimal(str(new_start))
    new_to = Decimal(str(row["current_value"]))
    if old_to < position.closed_at or new_to < new_from:
        return None
    old_part = (old_to - position.closed_at) * Decimal(str(old_final["multiplier"]))
    new_part = (new_to - new_from) * Decimal(str(row["multiplier"]))
    total = old_part + new_part
    parts = (
        {
            "meter": old_final.get("meter"),
            "asset_id": str(position.asset_id),
            "read_id": str(old_final.get("read_id")),
            "from": str(position.closed_at),
            "to": str(old_to),
            "quantity": str(old_part),
            "unit": quantity.unit,
        },
        {
            "meter": new_first.get("meter"),
            "asset_id": str(new_asset),
            "read_id": str(read_id),
            "from": str(new_from),
            "to": str(new_to),
            "quantity": str(new_part),
            "unit": quantity.unit,
        },
    )
    service_code = row.get("service_code")
    if _answered(service_code, METER_SWAPPED) == ANSWER_ACCEPT:
        return replace(quantity, amount=total), parts
    raise gather.GatherProblem(
        METER_SWAPPED,
        f"service {service_code!r}: the meter was exchanged inside this period. The old "
        f"meter {parts[0]['meter']} ran {position.closed_at} → {old_to} ({old_part} "
        f"{quantity.unit}); the new meter {parts[1]['meter']} ran {new_from} → {new_to} "
        f"({new_part} {quantity.unit}). The suggestion is to bill both parts, {total} "
        f"{quantity.unit}; nothing is billed until a clerk accepts it.",
        service_code=service_code,
        message_params={
            "old_meter": parts[0]["meter"],
            "old_from": parts[0]["from"],
            "old_to": parts[0]["to"],
            "old_quantity": parts[0]["quantity"],
            "new_meter": parts[1]["meter"],
            "new_from": parts[1]["from"],
            "new_to": parts[1]["to"],
            "new_quantity": parts[1]["quantity"],
            "suggested_quantity": str(total),
            "unit": quantity.unit,
        },
    )


def _anchor_quantity(
    quantity: Quantity,
    row: dict[str, Any],
    position: "BilledPosition | None",
) -> tuple[Quantity, Decimal | None, Decimal | None]:
    """**THE PERIOD OPENS WHERE THE LAST ISSUED BILL CLOSED.** PO, 2026-09-14.

    Verbatim: *"there is no sign off issue - you ahve to raje start reading as
    13,500 - we cannot create wrong conusmption that is loss"*.

    Metering answers a PERIOD with a figure it stored when the read was taken,
    `(current − prior) × multiplier`, where the prior is **the previous READ on
    the meter**. Where that is not the read the last issued bill closed on, the
    difference is consumption a customer physically used that no bill will ever
    carry. May closes at **13,500** and June opens at **13,800**: opening at
    13,800 does not defer those 300 kWh, it bills them to nobody, for ever.

    ⚠ **THIS IS NOT A DECISION AND MUST NEVER BECOME ONE.** The ruling's own
    reasoning: a decision asks a clerk to choose between outcomes that are each
    defensible, and here one outcome is simply wrong — and a control that
    offers it will have it chosen, on a busy day, in bulk, by somebody clearing
    a work list. The CALENDAR anchor keeps its decision because a gap in the
    DATES genuinely can be lawful (a service off, an account closed and
    reopened, a cycle moved). A gap in the REGISTER cannot be.

    ⚠ **AND IT REFUSES RATHER THAN ANCHORING WHEREVER THE ARITHMETIC WOULD BE A
    FICTION — the exact mirror of the loss it prevents.** Four refusals, none
    of them inferred from how the numbers look:

      * **the meter was exchanged** — the anchor read and this period's read
        sit on different `asset_id`s, published by metering on each read. The
        old device left at 13,500 and a new one starts at its own number, so
        the subtraction spans two registers and means nothing. Pricing both
        segments is `decisions.CHOICE_PRORATE_BOTH_SEGMENTS`' named boundary;
      * **the register went backwards** — a 5-digit register passing 99,999
        returns to 0, and `240 − 99,800` is catastrophically negative. Whether
        that is a WRAP or a bad read is decided by the register's SPAN against
        the drop (`BR-AST-015`; `metering.validation.classify_register_delta`,
        whose ❄️ GT-4/GT-14 arithmetic makes 99,800 → 240 a lawful **440**),
        and metering publishes no span across this seam — so billing refuses
        rather than guessing a 5-, 6- or 9-digit register. **It does not
        compute a wrap and it does not call one a negative read**: it says
        which module owns the answer;
      * **no multiplier** — `BR-MET-500` publishes the factor USED and
        deliberately never defaults it to 1, because 1 is right for most meters
        and silently wrong for the rest;
      * **a time-of-use meter** — `BR-RAT-021` reads arrive PRE-SPLIT per
        window and there is no per-window position to move them to, so
        anchoring the total alone would leave the windows short and under-bill
        exactly the way this ruling forbids.

    **WHERE THERE IS NOTHING TO ANCHOR, NOTHING CHANGES.** No issued bill, no
    position for the service, no current read, or a position that already
    equals the read's own prior all return the quantity byte-identical — which
    is every account in every existing fixture, and is why no ❄️ B4/B5 figure
    can move.
    """
    if position is None or position.closed_at is None:
        return quantity, None, None
    current_raw = row.get("current_value")
    if current_raw is None:
        # An ESTIMATE carries a consumption and no register (BR-MET-028) —
        # nobody read the dial, so there is no position to anchor. The
        # estimated-read case already owns it and a second voice here would be
        # two questions about one fact.
        return quantity, None, None
    prior_raw = row.get("prior_value")
    prior = None if prior_raw is None else Decimal(str(prior_raw))
    if prior is not None and prior == position.closed_at:
        return quantity, None, None  # already continuous — the overwhelming majority

    service_code = row.get("service_code")
    read_id = row.get("read_id")
    this_asset = position.asset_by_read.get(str(read_id)) if read_id else None
    if this_asset is not None and position.asset_id is not None and this_asset != position.asset_id:
        raise gather.GatherProblem(
            ANCHOR_METER_EXCHANGED,
            f"service {service_code!r}: the last issued bill closed at "
            f"{position.closed_at} on meter {position.asset_id}, and this period's read is "
            f"on meter {this_asset}. Two registers cannot be subtracted from each other, "
            "so the exchange is priced as two segments rather than anchored across.",
            service_code=service_code,
        )
    current = Decimal(str(current_raw))
    if current < position.closed_at:
        # ── PO 2026-09-30 (changes rows 45–46) · A POSSIBLE ROLLOVER ─────
        # Where the METER'S OWN register span proves a wrap (BR-AST-015, the
        # ❄️ GT-4/GT-14 arithmetic in `metering.quantities`), the product
        # SUGGESTS the wrapped quantity — 99,950 → 00,120 on 5 digits = 170 —
        # and uses it ONLY when a clerk accepted it. Anything else stays the
        # ratified decision below (Estimate / Hold).
        suggested = _rollover_suggestion(position.closed_at, current, row, quantity)
        if suggested is not None:
            if _answered(service_code, POSSIBLE_ROLLOVER) == ANSWER_ACCEPT:
                return replace(quantity, amount=suggested), prior, position.closed_at
            raise gather.GatherProblem(
                POSSIBLE_ROLLOVER,
                f"service {service_code!r}: the last issued bill closed at "
                f"{position.closed_at} and this period reads {current}. The meter's "
                f"register wraps there, so the suggestion is {suggested} "
                f"{quantity.unit}; nothing is billed until a clerk accepts it.",
                service_code=service_code,
                message_params={
                    "from": str(position.closed_at),
                    "to": str(current),
                    "suggested_quantity": str(suggested),
                    "unit": quantity.unit,
                },
            )
        raise gather.GatherProblem(
            ANCHOR_REGISTER_WENT_BACKWARDS,
            f"service {service_code!r}: the last issued bill closed at "
            f"{position.closed_at} and this period reads {current}. That is a register "
            "wrap or a bad read, and which one it is depends on the register's span "
            "(BR-AST-015), which metering does not publish across this seam. Nothing is "
            "assumed: a wrap computed against a guessed span invents consumption, and "
            "calling a wrap a bad read loses a whole register of it.",
            service_code=service_code,
        )
    if quantity.windows:
        raise gather.GatherProblem(
            ANCHOR_TOU_UNANCHORABLE,
            f"service {service_code!r} opens at {prior} where the last issued bill closed "
            f"at {position.closed_at}, and its reads arrive PRE-SPLIT per time-of-use "
            "window (BR-RAT-021). There is no per-window position to move them to, so "
            "anchoring the total alone would leave the windows short.",
            service_code=service_code,
        )
    multiplier_raw = row.get("multiplier")
    if (
        multiplier_raw is None
        and _answered(service_code, ANCHOR_MULTIPLIER_UNSTATED) == ANSWER_MULTIPLIER_ONE
    ):
        # PO 2026-09-30 (ratified table): *"no multiplier → Hold (default) /
        # Bill with multiplier 1"* — ×1 ONLY because a clerk chose it for this
        # account; the default stays HOLD and nothing defaults the factor.
        multiplier_raw = "1"
    if multiplier_raw is None:
        raise gather.GatherProblem(
            ANCHOR_MULTIPLIER_UNSTATED,
            f"service {service_code!r} must open at {position.closed_at} rather than "
            f"{prior}, and the factor this read USED is not published (BR-MET-500). It is "
            "never defaulted to 1: that is right for most meters and silently wrong for "
            "the rest.",
            service_code=service_code,
            message_params={
                "from": str(position.closed_at),
                "to": str(current),
                "suggested_quantity": str(current - position.closed_at),
                "unit": quantity.unit,
            },
        )
    anchored = (current - position.closed_at) * Decimal(str(multiplier_raw))
    logger.info(
        "DEF-BIL-5270: %s opens at %s rather than %s (last issued bill's closing read); "
        "consumption %s -> %s %s",
        service_code,
        position.closed_at,
        prior,
        quantity.amount,
        anchored,
        quantity.unit,
    )
    return replace(quantity, amount=anchored), prior, position.closed_at


def _rollover_suggestion(
    closed_at: Decimal, current: Decimal, row: dict[str, Any], quantity: Quantity
) -> Decimal | None:
    """The wrapped quantity when the meter's register span PROVES a wrap, else
    None. The arithmetic is metering's (`quantities.consumption_from_registers`,
    ❄️ GT-4/GT-14) and so is the span; billing only asks."""
    digits = _register_digits_for(row.get("read_id"))
    multiplier = row.get("multiplier")
    if digits is None or multiplier is None:
        return None
    wrap = _resolve("metering", "consumption_from_registers", "quantities")
    if wrap is None:
        return None
    try:
        answer = wrap(
            prior_read=closed_at,
            current_read=current,
            multiplier=Decimal(str(multiplier)),
            register_digits=digits,
            unit=quantity.unit,
        )
    except (ValueError, TypeError):
        return None  # not a wrap: the ratified Estimate / Hold decision applies
    return Decimal(str(answer.amount))


@batch_reads.memoised
def last_issued_window(account_id: Any) -> tuple[date, date] | None:
    """The period the account's FURTHEST-BILLED issued bill covered, or None.

    Ordered on `period_end` and not on `issued_at`, exactly as
    `selectors.last_issued_invoice_period_end` is: a bill issued late for an
    early period does not move the account's billed position forwards, and a
    catch-up sub-run issues bills out of calendar order by design.

    `INVOICE_LOCKED_STATUSES` is the *issued* set — issued, paid, void and
    corrected — for the reason that file states: all four describe a document
    that LEFT THE BUILDING, and only `draft` never did. **A draft is
    deliberately not an anchor**: a draft that is discarded and re-run has
    covered nothing, and anchoring on one would make every re-run look
    continuous with itself.

    🔒 HUMAN-REVIEW-PENDING (the billed-through anchor; review-ledger row).

    ⚠ **A FEE BILL IS NOT AN ANCHOR EITHER (`DEF-BIL-9254`, 2026-10-03).** A
    New Connection's quote is issued at Create as a `fee` bill dated that day
    (BR-MET-1187), and until this exclusion the account's FIRST cycle run read
    it as *"billed through 2026-10-03"*: a continuity finding nobody could
    answer, and the account's period opened the day after the quote. A fee
    covers no service period — the rule `selectors.last_issued_service_period_
    end` already applies for the move-out cut (`DEF-CUS-6086`) — so the same
    `NON_SERVICE_BILL_TYPES` is skipped here, in `_payload_read_ids` and in
    `period_anchor`, and in the bulk Check's prime of all three
    (`batch_seams.prime_billing_history`). One rule, every read.

    ⚠ **ONE DRAFT IS AN ANCHOR: A MOVE-OUT'S FINAL BILL (`DEF-CUS-10154`).**
    It is not a run's re-runnable draft but the final bill of a tenancy that
    ended, and it may still be sent. When the account is reopened (CR-181) its
    next cycle bill starts the day after it — Viktor Valdez's October bill
    10/13–10/31 from the 10/12 final reads, not 10/01–10/31 a second time
    (`selectors.billed_position_q`, the same filter in all four reads).
    """
    from apps.billing.selectors import NON_SERVICE_BILL_TYPES, billed_position_q

    row = (
        models.Invoice.objects.filter(
            billed_position_q(),  # DEF-CUS-10154 — see the docstring
            tenant_id=core_tenancy.current_tenant_id(),
            account_id=account_id,
        )
        .exclude(bill_type__in=NON_SERVICE_BILL_TYPES)
        .order_by("-period_end", "-created_at")
        .values_list("period_start", "period_end")
        .first()
    )
    if row is None or row[0] is None or row[1] is None:
        return None
    return (row[0], row[1])


def held_in(account_id: Any, *, first_day: date, before: date) -> bool:
    """Was this account HELD — or left for a later cycle — by a run whose period
    opened inside `[first_day, before)`? (PO ruling 2026-09-30, fixed-charge
    case 3.)

    Read off billing's own pending queue, `bill_run_exclusions` — the ONE queue
    both a phase-1 hold and a phase-3 mark-for-later write (BR-BIL-055). A row
    answers *yes* whether or not it was later resolved: a catch-up run that
    billed the held period issued a bill, and then the account's last bill is
    that one and no gap remains to ask about.
    """
    return models.BillRunExclusion.objects.filter(
        tenant_id=core_tenancy.current_tenant_id(),
        account_id=account_id,
        bill_run__period_start__gte=first_day,
        bill_run__period_start__lt=before,
    ).exists()


def period_anchor(account_id: Any, *, period_start: date) -> PeriodAnchor:
    """`cut_bill.first_unbilled_day`'s question, asked of a CYCLE run.

    ⚠ **THE ONE DIFFERENCE FROM `cut_bill`, AND IT IS DELIBERATE.** That module
    REFUSES an account with no issued bill and no move-in date, because a final
    bill must open its window somewhere and a guess bills days that are not the
    customer's. Here the same account is the ordinary first-bill case — a cycle
    run bills the period it was scoped for — so *nothing has ever been issued*
    answers `first_bill` and raises no finding at all. Refusing here would put
    every new customer on the exceptions screen in their first month.

    ONE QUERY, through billing's own published read. The prepare loop does NOT
    call this — it holds the whole anchor window already and calls
    `anchor_from` below with the date in hand, so a run asks the database once
    per account rather than twice. This form exists for a caller that has only
    an account id, and it must go on agreeing with that one: both read the
    furthest-billed ISSUED invoice ordered on `period_end`.

    ⚠ **THE SERVICE read, not the any-document read (`DEF-BIL-9254`).** A fee
    bill — a New Connection quote, a reconnection fee — covers no service
    period, so it is no billed-through date: the read is
    `last_issued_service_period_end` (`DEF-CUS-6086`), which skips it.
    """
    from apps.billing import selectors as billing_selectors

    return anchor_from(
        billing_selectors.last_issued_service_period_end(account_id),
        period_start=period_start,
    )


def anchor_from(billed_through: Any, *, period_start: date) -> PeriodAnchor:
    """The same arithmetic with the date ALREADY IN HAND — no query at all.

    Split out so the prepare loop, which must read `last_issued_window` anyway
    to anchor the REGISTER, does not ask the database a second time for a date
    it is already holding. At the top of the ICP (T5, 40,000 accounts) the
    difference is 40,000 queries a run, which is the sort of thing `NFR-5` has
    in mind and which no test would ever have noticed.
    """
    if not billed_through:
        return PeriodAnchor(state=CONTINUITY_FIRST_BILL)
    through = (
        billed_through
        if isinstance(billed_through, date)
        else date.fromisoformat(str(billed_through))
    )
    expected = through + ONE_DAY
    if period_start == expected:
        return PeriodAnchor(state=CONTINUITY_ALIGNED, billed_through=through)
    if period_start > expected:
        return PeriodAnchor(
            state=CONTINUITY_GAP,
            billed_through=through,
            days=(period_start - expected).days,
            from_day=expected,
            to_day=period_start - ONE_DAY,
        )
    return PeriodAnchor(
        state=CONTINUITY_OVERLAP,
        billed_through=through,
        days=(through - period_start).days + 1,
        from_day=period_start,
        to_day=through,
    )


# ══════════════════════════════════════════════════════════════════════════
# BR-BIL-1045 — THE RUN STATUS MACHINE (`DEF-BIL-5352`, 2026-09-15)
#
# ⚠ **`bill_runs.status` HAD TWO WRITERS AND BOTH WERE AT CREATION.**
# `create_run` below wrote `"draft"` and `corrections.execute_correction` wrote
# `"issuing"` for a rebill run; NOTHING advanced either. Measured on the demo
# tenant on 2026-09-15: 2 rows `draft`, 1 `issuing`, and a run that had issued
# **1,251 bills still read Draft**. The blueprint's screen 27 (p146) draws a
# STATUS column and its notes name three words, so the column stopped being a
# defect nobody could see and became the thing a clerk reads.
#
# **NO SIGNED VOCABULARY EXISTED.** `04-docs/03-contracts` carries none, and the
# model's own comment points at `RUN_STATUSES (r10 #7)`, which is not a symbol
# in this repository. B14 rule 41 makes the drawing the agreement; the five
# words below and their transitions are `BR-BIL-1045`, decided and written down
# rather than put to the PO (law 13).
#
# **EVIDENCE, NEVER A CLOCK.** Every transition is computed from rows that
# exist — locked bills, remaining drafts, a correction that has issued — at the
# moment the work happens. `BR-TEN-043` and gate G6 forbid a wall clock in this
# app, and a status derived from one would be unreproducible anyway.
#
# ⚠ **TWO SELECTOR CONSTANTS NAMED WORDS NOTHING EVER WROTE, AND BOTH WERE
# LOAD-BEARING.** `selectors.SETTLED_RUN_STATUSES` was `{completed, cancelled}`,
# so `unissued_run_count` counted every run in the window as unfinished on every
# tenant, for ever — the ledger's month-end *"every run finished"* item could
# never go green. `selectors.RUN_STATUSES_THAT_CONSUME_A_PERIOD` was
# `{completed}`, so `BR-MET-132`'s chase-days chip never dropped a period a bill
# run had billed. Both now name the words this module writes; see their own
# comments in `selectors.py` for the reasoning behind each membership.
# ══════════════════════════════════════════════════════════════════════════

#: Created. Nothing has issued and the run may still be thrown away.
RUN_STATUS_DRAFT = "draft"
#: In flight — drafts exist and none has gone out yet, or a pass issued nothing
#: and left work behind (a break list to clear, then issue again).
RUN_STATUS_ISSUING = "issuing"
#: TERMINAL. At least one of this run's bills is locked, so money left the
#: building (`models.INVOICE_LOCKED_STATUSES`).
RUN_STATUS_ISSUED = "issued"
#: TERMINAL. A correction has restated one of this run's bills — the blueprint's
#: own words, *"a status the correction workflow sets"*.
RUN_STATUS_CORRECTED = "corrected"
#: TERMINAL. The run ended having issued nothing AND with nothing left to issue.
#: It stays a row: a run that vanished would leave a clerk unable to explain a
#: gap in the numbering to an auditor (blueprint p146).
RUN_STATUS_ABANDONED = "abandoned"

#: The whole vocabulary, in the order a run passes through it. There is no
#: database constraint behind this tuple and deliberately so — `bill_runs.status`
#: is a plain `TextField` and adding a CHECK would refuse the historical rows
#: this product has already written. The tuple is what the tests assert against.
RUN_STATUSES: tuple[str, ...] = (
    RUN_STATUS_DRAFT,
    RUN_STATUS_ISSUING,
    RUN_STATUS_ISSUED,
    RUN_STATUS_CORRECTED,
    RUN_STATUS_ABANDONED,
)

#: A word that never goes backwards. `corrected` outranks `issued` because a
#: clerk who watches a run go from Corrected back to Issued has been told the
#: restatement was undone, which is the one thing hard rule 4 says cannot
#: happen; `abandoned` is not in the set, because a run that issued nothing can
#: legitimately be issued later and must be free to say so.
RUN_STATUSES_THAT_NEVER_REGRESS: frozenset[str] = frozenset({RUN_STATUS_CORRECTED})


def run_status_from_evidence(*, issued: int, drafts: int) -> str:
    """Which of the three post-pass words this run's rows actually support.

    ⚠ **THE `abandoned` TEST IS *ZERO ISSUED AND ZERO DRAFTS LEFT*, AND THE
    OBVIOUS ALTERNATIVE IS A TRAP.** Reading it as *the issue pass ended with no
    bills* would mark a run whose accounts all broke as Abandoned — and then the
    clerk clears the breaks, runs issue again, and a TERMINAL word flips back to
    Issued. A terminal word that un-terminates is worse than no word. Nothing
    went out and nothing is waiting to go out is a state that cannot reverse
    itself without somebody deliberately drafting more bills.

    Worked, against the blueprint's own drawn rows: `BR-2609-0051` holds 1,251
    locked bills and 0 drafts → **issued**; `BR-2607-0030` holds 0 and 0 →
    **abandoned**; a run holding 0 locked and 18 drafts after a pass that broke
    on every one of them → **issuing**, and it says so until somebody acts.
    """
    if issued:
        return RUN_STATUS_ISSUED
    if drafts:
        return RUN_STATUS_ISSUING
    return RUN_STATUS_ABANDONED


def record_run_outcome(bill_run: Any, *, actor: Any = None) -> str:
    """Advance a run's status to what its rows say. Returns the status now held.

    **THE ONE WRITER.** `release.release_run` calls it the instant the issue
    pass returns, inside the same transaction that stamps `released_at`, so a
    crash cannot leave a run that claims to have gone out. `corrections` calls
    it for the rebill run it created. Every other caller that ever issues a bill
    should call this rather than writing the column itself — a second writer is
    a second vocabulary.

    **IT IS IDEMPOTENT AND IT NEVER REGRESSES.** Called twice it writes once;
    called on a `corrected` run it leaves it corrected (`RUN_STATUSES_THAT_
    NEVER_REGRESS`). `update_fields` is exactly `status` and `updated_at`, so
    nothing else on the row can move through this path.

    ⚠ **IT IS NOT AN `audit_log` MONEY ACTION AND THAT IS ON PURPOSE.** Hard
    rule 7 asks for an audit row on every money ACTION; this writes no money and
    moves no money — it records what a money action that has ALREADY been
    audited did. `release.release_run` writes `bill_run.released` with the issue
    counts in it, one line above the call, and a second row saying *the word
    changed* would double-count the same event in the register a clerk reads.

    ⚠ **TWO RUN CREATORS DO NOT CALL THIS YET AND THAT IS `DEF-BIL-5373`**:
    `cut_bill` and `fee_bill` each issue one bill through `issue.issue_invoice`
    rather than through `release_run`, so their runs stay `draft` after their
    bill has gone out. One call in each is the fix; the single writer that
    would cover all of them lives in 🔒 `issue.py`, which is a locked money
    file. ⚠ **CORRECTED 2026-09-30 (build plan B13): this named `one_time` as a
    third, and that was false.** ⚠ **AND THE CORRECTION ROTTED THE SAME DAY
    (`DEF-BIL-8091`, re-checked 2026-10-01):** it went on to say `one_time` *"has
    no send path"* and that this call belonged in build-plan task A6 *"when it
    lands"*. A6 landed (`0b466f991`): `one_time_send.send` issues through
    `release.authorise_release` + `release.release_run`, and `release_run`
    calls THIS function through `complete_release` — so a one-time run already leaves `draft` when its
    bill goes out, and needs no call of its own.
    """
    tenant_id = core_tenancy.current_tenant_id()
    counts = (
        models.Invoice.objects.filter(tenant_id=tenant_id, bill_run=bill_run)
        .values("bill_run_id")
        .annotate(
            issued=Count("id", filter=Q(status__in=models.INVOICE_LOCKED_STATUSES)),
            drafts=Count("id", filter=Q(status=models.INVOICE_DRAFT)),
        )
        # The group is one run, so ordering by the grouped column names the one
        # row without letting `Invoice.Meta.ordering` into a GROUP BY it was
        # never meant to be in — the same reason `selectors.run_detail_dict`
        # spells this out, where a bare `.first()` on an aggregate is refused.
        .order_by("bill_run_id")
        .first()
    ) or {}
    was = bill_run.status
    if was in RUN_STATUSES_THAT_NEVER_REGRESS:
        return was
    now = run_status_from_evidence(
        issued=counts.get("issued", 0), drafts=counts.get("drafts", 0)
    )
    if now == was:
        return was
    bill_run.status = now
    bill_run.save(update_fields=["status", "updated_at"])
    return now


def mark_run_corrected(bill_run: Any) -> str:
    """The blueprint's *"a status the correction workflow sets"*, written once.

    Set on the run that holds the bill a correction RESTATED — never on the
    rebill run, which is an ordinary run of one bill and reaches `issued` like
    any other. A clerk reading Corrected on run 08-B is being told *this whole
    run was redone*, which the blueprint calls the only place in the product
    that fact is visible.

    Only a run that has ISSUED can be corrected — there is nothing to restate
    otherwise — so a `draft` run is left alone rather than jumped forward, and
    the caller is not made to care.
    """
    if bill_run is None:
        return ""
    if bill_run.status not in (RUN_STATUS_ISSUED, RUN_STATUS_ISSUING):
        return bill_run.status
    bill_run.status = RUN_STATUS_CORRECTED
    bill_run.save(update_fields=["status", "updated_at"])
    return RUN_STATUS_CORRECTED


class DuplicateRun(BillingRuleError):
    """BR-BIL-005: this (tenant, cycle, period) has already been run.

    Carries the ORIGINAL row rather than a formatted sentence, because the rule
    names three things the refusal must show — *who ran the original, when, and
    a link* — and only the caller knows how to render a link. The API turns it
    into a 409 BIZ-IDEMPOTENT whose params carry the run id, the actor and the
    timestamp; a batch caller can read the same three off `.original`.
    """

    def __init__(self, original: Any) -> None:
        self.original = original
        super().__init__(
            f"a bill run over this cycle and period already exists ({original.pk}), so "
            "this one is refused rather than double-billing the cycle (BR-BIL-005). "
            "Stragglers go through a catch-up sub-run, never a colliding re-run."
        )


# ══════════════════════════════════════════════════════════════════════════
# DEF-BIL-9255 — DISCARD A DRAFT RUN (BR-BIL-1045's `abandoned`, by a clerk)
# ══════════════════════════════════════════════════════════════════════════

#: The refusal codes, each its own catalogue key (`billing.runDiscard.refused.*`,
#: mapped in `api._DISCARD_REFUSALS`).
DISCARD_REFUSED_NOT_DRAFT = "not_draft"
DISCARD_REFUSED_HAS_ISSUED = "has_issued_bills"
DISCARD_REFUSED_RELEASED = "released"
DISCARD_REFUSED_HAS_CHILD = "has_catch_up"


class DiscardRefused(BillingRuleError):
    """Why this run cannot be thrown away. `code` keys the clerk's sentence."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def discarded_key(key: str, run_id: Any) -> str:
    """The key a discarded run keeps: unique, still says what it was, and never a
    key `idempotency.bill_run_key` can produce."""
    return f"{key}|discarded|{run_id}"


def discard_run(bill_run: Any, *, actor: Any = None) -> dict[str, Any]:
    """🔒 HUMAN-REVIEW-PENDING (idempotency key · money action) — `DEF-BIL-9255`.

    **Nothing issued, nothing posted, nothing signed off — then a clerk may throw
    the run away.** Until this function a draft run made for the wrong period
    could not be removed (DELETE answered 405) and blocked every overlapping run
    on its cycle (`run_scope._check_continuity`'s `period_overlap`).

    It keeps its ROW: `abandoned` is BR-BIL-1045's terminal word for a run that
    issued nothing and has nothing left to issue, and the blueprint's reason is
    the auditor — *"a run that vanished would leave a clerk unable to explain a
    gap in the numbering"*. What goes is everything that never left the
    building: the run's DRAFT bills and their lines, which BR-BIL-023 already
    deletes on every re-price (`assemble_document`), and which `billing/0017`'s
    trigger permits for a draft and refuses for anything else.

    **Refused, by name, when ANY of these is true** (never a partial discard):

      * the status is not `draft`;
      * a bill of this run is LOCKED. ⚠ Not the same test as the status:
        `cut_bill` and `fee_bill` runs still read `draft` after their one bill
        has gone out (`DEF-BIL-5373`) — a New Connection quote's run is one;
      * the run carries a release — the clerk signed off its figures;
      * a catch-up child of this run exists that is not itself abandoned.

    **THE KEY IS FREED, AND THAT IS THE 🔒 PART.** `bill_runs.idempotency_key` is
    unique per tenant (BR-BIL-005), so an abandoned row that kept its key would
    refuse a correct run for the SAME cycle and period for ever. It is rewritten
    once to `discarded_key(...)`.

    **AUDITED (hard rule 7)** as `bill_run.discarded`, with the run's number,
    period, and how many drafts were removed and what they totalled.
    """
    from django.db.models import Sum

    tenant_id = core_tenancy.current_tenant_id()
    with transaction.atomic():
        run = models.BillRun.objects.select_for_update().get(tenant_id=tenant_id, pk=bill_run.pk)
        name = run.run_no or run.pk
        if run.status != RUN_STATUS_DRAFT:
            raise DiscardRefused(
                DISCARD_REFUSED_NOT_DRAFT,
                f"run {name} is {run.status}; only a draft run can be discarded.",
            )
        invoices = models.Invoice.objects.filter(tenant_id=tenant_id, bill_run=run)
        if invoices.filter(status__in=models.INVOICE_LOCKED_STATUSES).exists():
            raise DiscardRefused(
                DISCARD_REFUSED_HAS_ISSUED,
                f"run {name} has a bill that has gone out; it cannot be discarded.",
            )
        if models.BillRunRelease.objects.filter(tenant_id=tenant_id, bill_run=run).exists():
            raise DiscardRefused(
                DISCARD_REFUSED_RELEASED, f"run {name} was signed off; it cannot be discarded."
            )
        if (
            models.BillRun.objects.filter(tenant_id=tenant_id, parent_run=run)
            .exclude(status=RUN_STATUS_ABANDONED)
            .exists()
        ):
            raise DiscardRefused(
                DISCARD_REFUSED_HAS_CHILD, f"run {name} has a catch-up run; discard that first."
            )

        drafts = invoices.filter(status=models.INVOICE_DRAFT)
        removed = drafts.count()
        removed_total = drafts.aggregate(total=Sum("total"))["total"] or Decimal("0")
        # BR-BIL-023's own two lines (`assemble_document`): lines first, then the
        # drafts. The locked-bill refusal above already makes a non-draft
        # unreachable, and the database refuses one anyway (`billing/0017`).
        models.InvoiceLine.objects.filter(invoice__in=drafts).delete()
        drafts.delete()

        before = {"status": run.status, "idempotency_key": run.idempotency_key}
        run.status = RUN_STATUS_ABANDONED
        run.idempotency_key = discarded_key(run.idempotency_key, run.pk)
        run.save(update_fields=["status", "idempotency_key", "updated_at"])
        audit.money_action(
            actor,
            "bill_run.discarded",
            "bill_run",
            str(run.pk),
            before=before,
            after={
                "status": RUN_STATUS_ABANDONED,
                "idempotency_key": run.idempotency_key,
                "run_no": run.run_no,
                "period_start": run.period_start.isoformat(),
                "period_end": run.period_end.isoformat(),
                "drafts_removed": removed,
                "drafts_total_removed": str(removed_total.quantize(Decimal("0.0001"))),
            },
        )
    return {"id": str(run.pk), "status": RUN_STATUS_ABANDONED, "drafts_removed": removed}


def default_bill_date(cycle_bill_day: int | None, period_end: date | None) -> date | None:
    """OQ-344 — the bill date a run falls back to: **the cycle's bill day, in
    the month AFTER the period ends.** Pure.

    **PO ruling 2026-08-23, verbatim:** *"I'd say B - these are defualt - user
    can override"* — reading (B) of three that sat up to a month apart. On the
    figure they were shown: a cycle whose bill day is the **5th**, with **21**
    due-days, billing the period **1–31 August**, bills **5 September** and
    falls due **26 September**.

    **WHY THIS QUESTION EXISTED AT ALL.** D9 gave the cycle a bill DAY, and
    turning a day-of-month into one run's DATE means choosing a month. The two
    readings the PO rejected: **(A) the period's start month** bills 5 August,
    before the period it bills has finished — right for a cycle billed in
    advance, wrong for one billed in arrears; **(C) the month the run is taken
    in** bills whatever the clerk's calendar says, so a run caught up in October
    bills 5 October and the same period falls due on a different date depending
    on when somebody got round to it. Since the due date is bill date + due
    days, each reading started the late-fee clock (BR-BIL-001) on a different
    day.

    (C) is not merely unchosen here, it is UNREACHABLE: the period is the only
    input and this function reads no clock (BR-TEN-043 / gate G6). That is the
    property the ruling turns on — *"the only one that gives the same answer
    whether the run is taken on time or late"*.

    **A DAY THE MONTH DOES NOT HAVE CLAMPS TO ITS LAST DAY** — OQ-339, ruled the
    same day: *"there is no 31st feb so we have to manage either 28th or 29th of
    Feb."* A cycle billing on the 31st, for a period ending in January, bills 28
    February in a common year and **29 February in a leap one**.

    ⚠ The clamp is written HERE rather than imported from
    `apps.metering.schedule.clamp_day_to_month`, and that is the module boundary
    rather than an oversight: **billing does not import metering** (B1, gate G6,
    the posture `metering_seam.py` states in as many words). What the two share
    is the RULE — one PO sentence, quoted at both — and both are tested against
    the figures in it.

    `None` when either half is missing. A cycle with no bill day has no default,
    and the caller REFUSES (BR-BIL-024) rather than reaching for a clock: a
    guessed due date decides when a late fee starts.

    Takes two plain values rather than a run row, so it can be asserted without a
    database and so no caller can pass a row it forgot to refresh — the shape
    `effective_bill_date` and `effective_due_days` already have.
    """
    if cycle_bill_day is None or period_end is None:
        return None
    total = period_end.year * 12 + period_end.month  # = (year, month) + 1 month
    year, month = divmod(total, 12)
    month += 1
    day = min(max(int(cycle_bill_day), 1), monthrange(year, month)[1])
    return date(year, month, day)


def effective_bill_date(
    run_bill_date: date | None,
    cycle_bill_day: int | None,
    period_end: date | None,
) -> date | None:
    """The date this run bills on — BR-BIL-070 (PO 2026-08-11, OQ-122 option A).

    Verbatim: *"A Store what they type and use it"*. So the clerk's typed date
    WINS whenever there is one, and everything that hangs off "the bill date"
    hangs off this answer: the SERVICE date, which is BR-RAT-007's pricing
    pivot, and BR-BIL-024's due date.

    **Worked, and it is the case the PO was shown:** cycle 08-A is dated 1 Aug
    with 21 due-days, the clerk types 3 Aug. This returns 3 Aug, so the bill
    prices against the tariff version in force on 3 Aug and falls due 24 Aug.
    Before the ruling it priced at 1 Aug and fell due 22 Aug, and the typed
    value vanished with no warning.

    NONE FROM THE CLERK MEANS THE CYCLE'S DEFAULT, and that is a fallback rather
    than a guess: a run created with no typed date is a run where nobody
    expressed a preference.

    ⚠ **WHAT THE FALLBACK IS HAS CHANGED, BY RULING (OQ-344, PO 2026-08-23).**
    It used to be `cycles.bill_date`, a stored calendar DATE from the previous
    column generation. That column is gone (metering 0023) and the fallback is
    now DERIVED — `default_bill_date(cycle_bill_day, period_end)`, *"the bill
    day, in the month after the period ends"* — which is why this function takes
    a DAY and a PERIOD END where it used to take a date. PO verbatim: *"I'd say
    B - these are defualt - user can override"*.

    `None` from both is `None` — this function never invents a third date and
    never reads a clock (BR-TEN-043 / gate G6). The caller refuses; see
    `selectors.prepared_for`, which raises BIZ-COMPLETENESS naming BR-BIL-024
    rather than reaching for `date.today()`.

    Pure and takes two plain dates rather than a run row, so it can be asserted
    without a database and so no caller can pass a row it forgot to refresh.
    """
    if run_bill_date is not None:
        return run_bill_date
    return default_bill_date(cycle_bill_day, period_end)


def effective_due_days(run_due_days: int | None, cycle_due_days: int | None) -> int | None:
    """The terms this run falls due on — CR-029 D9 (PO ruling 2026-08-23).

    Verbatim: *"when we configure Cycle we are provideing default values; mostly
    it wil remain as it is but user can over ride them during billing"*. So the
    CYCLE carries the default and the RUN may override it, which is the exact
    precedence `effective_bill_date` above already expresses for the other half
    of the same sentence. Written as its own function, next to that one, so the
    two halves of one ruling cannot drift apart.

    ⚠ **D9 SUPERSEDES THE UPGRADED PROTOTYPE**, whose SET-07.3 / SET-07.4 /
    SET-07D footnotes say *"Bill and due dates belong to the run, not the
    cycle"*. Three screens carry that sentence and it is now wrong.

    ⚠ **`is None`, NEVER TRUTHINESS.** `due_days = 0` is a lawful arrangement —
    due on the bill date, and BR-MET-009 says only `due_days ≥ 0` — so a falsy
    test here would silently replace a typed 0 with the cycle's 21 and give
    every customer in that run three more weeks than the clerk chose.

    **Worked:** cycle 06-A defaults to 21 due-days and bills 1 Jul. A run that
    overrides nothing falls due **22 Jul**; a run whose clerk types 14 falls due
    **15 Jul**, and the cycle still says 21 for the next run.

    Pure and takes two plain integers rather than a run row, so it can be
    asserted without a database.
    """
    return run_due_days if run_due_days is not None else cycle_due_days


def _allocate_run_no(issue_date: date, warnings: list[dict[str, Any]]) -> str | None:
    """OQ-342 — the run's number, from the `bill_run` series. `None` if absent.

    PO ruling 2026-08-23, verbatim: *"A: a real series (RUN-0001, like RT-001)"*.
    Allocated through `core.numbering`, which is the ONE place BR-TEN-035's
    allocation law lives — in the caller's transaction, forward-only, gaps
    acceptable, a number never reused.

    **THE ISSUE DATE IS AN ARGUMENT, NEVER A CLOCK** (BR-TEN-043, gate G6).
    `core.numbering` needs a date for two things: the `{YYYY}/{YY}/{MM}/{DD}`
    tokens a tenant may put in the format, and CR-005's restart period. The
    caller passes the run's OWN business date — the bill date the clerk typed,
    or the period's end when they typed none — so the number is reproducible
    on a replay years later and a catch-up run for August numbers under August
    rather than under the day somebody got round to it. `RUN-{0000}`, the seeded
    default, carries no date token at all, so on an untouched tenant this
    changes nothing; it matters the moment an admin picks `RUN-{YYYY}-{0000}`.

    **A MISSING SERIES ROW IS REPORTED, NEVER FAKED.** A tenant provisioned
    before this series existed has no row for it (`_seed_number_series` is
    `get_or_create` and repairs one on the next reference-data seed). Such a run
    is created UNNUMBERED with a warning naming the series — the posture CR-005
    established after `JE-` shipped for weeks with no row and every manual
    journal entry went out unnumbered in silence (BR-LED-021 (i)). Refusing to
    create the run instead would stop a utility billing over a settings gap.
    """
    try:
        return core_numbering.next_number(core_numbering.BILL_RUN, issue_date)
    except core_numbering.NumberingError:
        warnings.append({"code": "numbering_series_missing", "series": core_numbering.BILL_RUN})
        return None


def resolve_case_defaults(chosen: dict[str, Any] | None) -> dict[str, str]:
    """BR-BIL-1040 — screen 16's DEFAULTS group, resolved into what the run STORES.

    🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — it decides whether an account with
    no reading is ESTIMATED onto a customer's bill or HELD out of the run, for
    every account the case touches. Its row is in
    `12-governance/09-human-review-ledger.md`.

    `DEF-BIL-5255`. The blueprint's screen 16 (`p047`) draws three controls —
    *When there is no reading*, *When a bill looks unusually large*, *Unusual
    days* — and calls the group *"the single biggest error-reducer in this
    redraw"*: three decisions a clerk makes ONCE instead of hundreds of times.

    TWO SOURCES, IN THIS ORDER, and there is deliberately no third:

      * what the clerk LEFT THE CONTROL AT, passed in by the caller;
      * otherwise the tenant's own setting for that control
        (`settings_seam.run_case_defaults`, S66 Billing defaults).

    **No literal appears anywhere in this function** — PO instruction
    2026-09-14, *"no hardcoding"*. A value this module invented would be a
    second copy of a figure the tenant's own Settings screen shows, and the two
    would disagree the day somebody moved one (`settings_families.py` records
    that exact failure beside `back_bill_cap_months`).

    THE VOCABULARY IS `decisions.CHOICES_BY_CASE` AND NOTHING ELSE. Both halves
    of every pair are validated against it: an unknown case kind and an unknown
    choice are each refused by name. Writing the words out here — or into a
    CHECK constraint — would be the second copy again, one layer down.

    ⚠ **A DEFAULT IS NOT A DECISION.** BR-BIL-015's no-pre-committed-default
    rule was reaffirmed by its author on 2026-08-26 (*"an auditor asking 'who
    chose to estimate M-4412?' gets a name"*), and it stands: nothing here
    writes a `bill_run_decisions` row, and the per-account trail is as
    append-only as it was. What this stores is the RUN's standing answer, and
    the name the auditor gets is the run's own `run_by` plus its
    `bill_run.created` audit row.
    """
    from apps.billing import decisions, settings_seam

    tenant_defaults = settings_seam.run_case_defaults()
    resolved: dict[str, str] = dict(tenant_defaults)
    for case_kind, choice in dict(chosen or {}).items():
        offered = decisions.CHOICES_BY_CASE.get(str(case_kind))
        if offered is None:
            raise BillingRuleError(
                f"{case_kind!r} is not a case this run can carry a standing answer for. "
                f"The case kinds are billing's own ({', '.join(sorted(decisions.CHOICES_BY_CASE))}) "
                "and a run default that named a case nobody raises would be a decision "
                "with nothing to apply it to.",
                br_ref="BR-BIL-1040",
            )
        if str(choice) not in offered:
            raise BillingRuleError(
                f"{choice!r} is not one of the choices {case_kind!r} offers "
                f"({', '.join(offered)}). A run default outside the case's own "
                "vocabulary would be recorded here and refused per account at prepare "
                "time, which is a decision a clerk made and the run silently dropped.",
                br_ref="BR-BIL-1040",
            )
        resolved[str(case_kind)] = str(choice)
    return resolved


def validated_template_pin(template_id: Any) -> Any:
    """`CR-105-BRC03` / BR-BIL-1041 — the template chosen at Scope, checked THERE.

    🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — it decides which layout is frozen
    onto every immutable bill in a run (hard rule 4, BR-BIL-026). Its row is in
    `12-governance/09-human-review-ledger.md`.

    PO ruling 2026-09-14, verbatim: *"in this step 1 scope - you will ahve to
    also decide on billing template"*.

    ⚠ **DECIDING IS NOT STAMPING.** This returns the TEMPLATE and no version
    number. `assemble_document` still stamps template AND version onto each
    invoice at ISSUE and freezes it there, so a template edited between Scope
    and Send cannot change a bill a clerk already approved. Pinning a version
    here would be stale by Send on any tenant that publishes in between.

    **WHAT IT IS FOR IS THE REFUSAL.** `issue.IssuedRun.template_problems`
    counts *"distinct reasons a bill could not resolve its own template, with
    the number of bills each affected"* — so a bill CAN fail to find one, and
    today that is discovered at ISSUE, after Scope, after Check, after the clerk
    signed off. The two ways it fails are checked here instead: a template that
    is not this tenant's, and a template with no PUBLISHED version (BR-BIL-026 —
    a draft is test-printable and never pinned).

    `None` in, `None` out, and that is the ordinary case: nobody pinned one and
    BR-BIL-025's per-account chain runs exactly as it does today.
    """
    if template_id is None:
        return None
    # Imported at CALL time: `templates_service` imports `template_models`,
    # which imports this module's `models` — the same closed loop
    # `issue._pin_for_account` names at its own import.
    from apps.billing import templates_service
    from apps.billing.template_models import BillTemplate

    tenant_id = core_tenancy.current_tenant_id()
    template = BillTemplate.objects.filter(tenant_id=tenant_id, pk=template_id).first()
    if template is None:
        # HR-1: unknown, malformed and cross-tenant are ONE answer, the same
        # posture the cycle check below this takes.
        raise core_errors.deny_as_not_found("BR-TEN-003")
    if templates_service.published_version(template) is None:
        raise BillingRuleError(
            f"template {template.name!r} has no PUBLISHED version, so it cannot be the "
            "run's pin (BR-BIL-026). A draft is test-printable but never pinned: a bill "
            "pinned to a draft could be edited after the customer received it. This is "
            "refused at Scope rather than at issue, which is the whole of CR-105-BRC03 — "
            "the clerk finds out before they sign off, not after.",
            br_ref="BR-BIL-1041",
        )
    return template.pk


def create_run(
    *,
    cycle_id: Any,
    period_start: date,
    period_end: date,
    bill_date: date | None = None,
    due_days: int | None = None,
    case_defaults: dict[str, Any] | None = None,
    label: str | None = None,
    template_id: Any = None,
    run_by: Any = None,
    actor: Any = None,
) -> models.BillRun:
    """US-BIL-001's exit: ONE `bill_runs` row in draft. Writes nothing else.

    🔒 HUMAN-REVIEW-PENDING (the run's idempotency key) — row in
    `12-governance/09-human-review-ledger.md`, bulk bill run plan B3.

    ⚠ **A RUN IS NO LONGER NARROWED TO SERVICES — `scope_services` IS GONE FROM
    THIS SIGNATURE (plan B3, PO 2026-09-30).** PO verbatim: *"why do we need it
    - any way you dont need this here - which servcies to be billed in unit
    /account is decied at run time -so this filter is of now use"*. So a NEW
    run is always the whole cycle, `bill_runs.scope_services` is written NULL,
    and its key is cycle + period with NO `|scope|` segment. **Existing rows keep
    the key they were stored with** — nothing rewrites a stored key — and a
    catch-up of an old scoped run still copies its parent's scope
    (`pending.create_catch_up_run`). A NEW run over a period an old scoped run
    already covered has a different key, so the unique index cannot see it; the
    Scope step's overlap refusal (`run_scope._check_continuity`) is what refuses
    it, which is why that check is not optional.

    No draft, no exclusion, no read of a meter. Phase 1 is *"we build the data
    first … so that all the decisions are made on screen"* and this is only the
    row every later phase hangs off — `prepare_run` is what looks, and it still
    writes nothing when it does.

    THE STATUS IS THE PHASE (BR-BIL-050). `draft` is not a placeholder here: it
    is the value a returning clerk's wizard reads to re-enter the run where they
    left it, which is why the run lives in the URL rather than in React state.

    **THE BILL DATE THE CLERK TYPED IS STORED** — `bill_runs.bill_date`, added
    by migration 0011 under BR-BIL-070 (PO ruling 2026-08-11 closing OQ-122,
    option A, verbatim *"A Store what they type and use it"*). It is the run's
    SERVICE date (BR-RAT-007's pricing pivot) and BR-BIL-024's due date derives
    from it. Passing `None` records that nobody typed one, and the run then
    uses the CYCLE's date exactly as every run did before the ruling —
    `effective_bill_date` is the one place that resolution lives.

    This paragraph used to read *"the bill date is not stored, and that is not
    an omission this function invented … routed to the PO as OQ-122"*. That was
    true when it was written and is false now; it is rewritten rather than left
    standing (hard-won law 1 — a stale absence-claim misleads exactly as much
    as a stale guarantee).

    THE CYCLE IS CHECKED THROUGH METERING'S OWN PUBLISHED READ (B1), and it has
    to be: a foreign key alone would NOT stop a run being pointed at another
    tenant's cycle, because PostgreSQL evaluates referential integrity outside
    row-level security. An unknown cycle, a malformed id and another tenant's
    cycle are therefore one answer — absent (HR-1).

    **THE RUN'S STANDING ANSWERS ARE STORED TOO** — `bill_runs.case_defaults`,
    BR-BIL-1040, `DEF-BIL-5255`, the blueprint's screen-16 DEFAULTS group. They
    are RESOLVED here and not later: `resolve_case_defaults` takes what the
    clerk left each control at and fills the rest from the tenant's own S66
    setting, so the row records what was in force at the moment the run was
    created. Reading the setting at prepare time instead would let a tenant who
    edits Settings between Scope and Check change what a run already in flight
    decided — the same hazard BR-BIL-026 freezes the template against.

    **AND THE TEMPLATE THE CLERK CHOSE** — `bill_runs.template_id`, BR-BIL-1041,
    `CR-105-BRC03`, PO 2026-09-14: *"in this step 1 scope - you will ahve to also
    decide on billing template"*. ⚠ **Deciding is not stamping.** The version is
    NOT pinned here; `assemble_document` stamps template + version at ISSUE and
    freezes it (BR-BIL-026), unchanged. What moves forward is the REFUSAL: a
    template that is not this tenant's, or has no published version, is refused
    at step 1 instead of surfacing in `issue`'s `template_problems` after the
    clerk has signed off.

    Raises `DuplicateRun` for BR-BIL-005 and `BillingRuleError` for a backwards
    period; neither leaves a row.
    """
    if period_end < period_start:
        raise BillingRuleError(
            f"period {period_start} → {period_end} ends before it begins. "
            "Every proration in B4.3 divides by this window, so the run is "
            "refused rather than created with a window that cannot be divided."
        )

    cycles_list = _resolve("metering", "cycles_list")
    if cycles_list is None:
        raise BillingRuleError(
            "metering has not published cycles_list, so the run's cycle cannot be "
            "verified as this tenant's. A run created against an unverified cycle "
            "id is a run over an unknown scope."
        )
    if not any(str(row.get("id")) == str(cycle_id) for row in cycles_list()):
        # HR-1: unknown, malformed and cross-tenant are ONE answer. The body is
        # identical either way, so existence cannot be probed.
        raise core_errors.deny_as_not_found("BR-TEN-003")

    tenant_id = core_tenancy.current_tenant_id()
    #: OQ-342 — anything the NUMBERING could only report rather than do. Today
    #: exactly one thing can land here: this tenant has no `bill_run` series row
    #: (provisioned before the series existed), so the run is created unnumbered.
    #: Carried back on the returned row rather than raised, because a settings
    #: gap must not stop a utility billing — and stated out loud rather than
    #: swallowed, because `JE-` shipped unnumbered in silence for weeks and
    #: nobody found out until a finance officer could not quote an entry.
    numbering_warnings: list[dict[str, Any]] = []
    # BR-BIL-1040 / BR-BIL-1041 — resolved and refused BEFORE the row exists, so
    # an unknown choice or an unpublished template leaves nothing behind, the
    # same posture the backwards-period and unknown-cycle refusals above take.
    stored_case_defaults = resolve_case_defaults(case_defaults)
    pinned_template_id = validated_template_pin(template_id)
    # A label is the clerk's own words and is never parsed; blank is nothing
    # typed, which is the column's NULL.
    stored_label = (label or "").strip() or None
    key = idempotency.bill_run_key(
        cycle_id=cycle_id,
        period_start=period_start,
        period_end=period_end,
        # Plan B3 (PO 2026-09-30): no services term. A new run is the whole
        # cycle, keyed byte-identically to every unnarrowed run already stored.
        # `DEF-BIL-5283`'s `|scope|` segment survives only on rows written
        # before the ruling.
    )
    existing = models.BillRun.objects.filter(tenant_id=tenant_id, idempotency_key=key).first()
    if existing is not None:
        raise DuplicateRun(existing)

    with transaction.atomic():
        # ⚠ **THE ALLOCATION IS INSIDE `atomic()` AND MUST STAY THERE.** Two
        # reasons, and the second was learned by defect. (1) BR-TEN-035 allocates
        # under a `SELECT … FOR UPDATE` on the tenant's `number_series` row, and
        # Django refuses that outside a transaction — `create_route` answered
        # HTTP 500 on every un-coded route until DEF-234 moved it inside. (2) It
        # is the only placement that makes the number and the row ONE fact: a
        # successful allocation followed by a refused create (a duplicate run,
        # BR-BIL-005) would burn a number, and a utility reconciling a sequence
        # has to explain every hole in it. Gaps are lawful; unnecessary ones are
        # still a lie about what has been issued.
        run_no = _allocate_run_no(
            bill_date if bill_date is not None else period_end, numbering_warnings
        )
        try:
            row = models.BillRun.objects.create(
                tenant_id=tenant_id,
                cycle_id=cycle_id,
                period_start=period_start,
                period_end=period_end,
                # BR-BIL-070 — what the clerk typed on S31 step 1, stored so a
                # run resumed tomorrow (BR-BIL-050) finds the same date. NOT
                # part of the idempotency key: BR-BIL-005 makes a run unique on
                # (tenant, cycle, period), and adding the bill date would let
                # the same cycle-period be billed twice by retyping one field.
                bill_date=bill_date,
                # CR-029 D9 — *"user can over ride them during billing"*. NOT
                # part of the idempotency key either, for BR-BIL-005's reason
                # above: adding it would let the same cycle-period be billed
                # twice by retyping one field. None = nobody overrode the terms.
                due_days=due_days,
                # OQ-342 (PO 2026-08-23, *"A: a real series (RUN-0001, like
                # RT-001)"*). None when this tenant has no `bill_run` series row
                # yet — reported in `warnings`, never faked.
                run_no=run_no,
                status="draft",
                idempotency_key=key,
                # Plan B3 (PO 2026-09-30): the services filter is removed, so a
                # new run records NO service scope. The column stays for the
                # rows written before the ruling and for their catch-ups.
                scope_services=None,
                # BR-BIL-1040 — the run's standing answers, complete and already
                # resolved. NOT part of the idempotency key, for BR-BIL-005's
                # reason above: adding them would let the same cycle-period be
                # billed twice by changing one dropdown.
                case_defaults=stored_case_defaults,
                # `DEF-BIL-5255` ④ — the clerk's own name for this run, so the
                # `ALREADY RUN FOR THIS CYCLE` table's LABEL column has something
                # to render and two runs over one period can be told apart.
                label=stored_label,
                # BR-BIL-1041 — the template CHOSEN at Scope. None is the
                # ordinary case: BR-BIL-025's per-account chain then runs at
                # issue exactly as it does today.
                template_id=pinned_template_id,
                # WHO started it, by id — BR-BIL-005's refusal names this user.
                # A caller holding the `users` row may pass it, an API layer
                # only the session user's id, a runbook an `AutomationActor`
                # and a system job nothing at all: `actor_user_id` is the one
                # place all five are answered (DEF-BIL-5090).
                run_by_id=audit.actor_user_id(run_by),
            )
        except IntegrityError as clash:
            # Lost the race to another request between the check above and this
            # insert. The unique index is the real guarantee (the check is only
            # so the common case gets the who/when/link message); re-read and
            # answer with the same refusal rather than a 500.
            winner = models.BillRun.objects.filter(tenant_id=tenant_id, idempotency_key=key).first()
            if winner is None:
                raise clash
            raise DuplicateRun(winner) from clash
        # US-BIL-001 §5: `audit_log bill_run.created`. Inside the transaction so
        # the run cannot stand without its trail row (core.audit fails loudly
        # rather than losing it). No PII: the row carries ids and dates only.
        audit.money_action(
            actor if actor is not None else run_by,
            "bill_run.created",
            "bill_run",
            str(row.pk),
            before=None,
            after={
                "cycle_id": str(cycle_id),
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                # OQ-342: the number a customer or an auditor may quote belongs
                # in the trail beside the dates that decide what they are
                # charged (CLAUDE.md rule 7). `null` records that this tenant
                # had no series row.
                "run_no": row.run_no,
                # BR-BIL-070: the typed date decides what every bill in this run
                # is priced at and when it falls due, so it belongs in the trail
                # (CLAUDE.md rule 7). `null` records that nobody typed one.
                "bill_date": bill_date.isoformat() if bill_date is not None else None,
                # CR-029 D9: the terms decide when a bill falls due, so an
                # override belongs in the trail beside the date (CLAUDE.md
                # rule 7). `null` records that the cycle's default was used.
                "due_days": due_days,
                "status": row.status,
                "scope_services": row.scope_services,
                # BR-BIL-1040: these decide whether an account with no reading
                # is estimated onto a bill or held out of the run, so they
                # belong in the trail (CLAUDE.md rule 7). This is also the row
                # that answers *"who chose to estimate M-4412?"* for every
                # account the standing answer touched.
                "case_defaults": row.case_defaults,
                "label": row.label,
                # BR-BIL-1041: which layout every bill in this run is headed
                # for. `null` records that nobody pinned one and each account
                # resolves its own chain (BR-BIL-025).
                "template_id": str(row.template_id) if row.template_id else None,
                "idempotency_key": key,
            },
        )
    # Attached rather than returned separately: every caller already holds the
    # row, and a second return value would have to be threaded through four
    # call sites that do not care. `getattr(run, "numbering_warnings", [])` is
    # the read.
    row.numbering_warnings = numbering_warnings
    return row


def _dispute_hold_for(
    dispute_holds: Any, account: Any, *, unit_ids: tuple[str, ...] | None = None
) -> AccountProblem | None:
    """BR-MET-024's hold, as a phase-1 block — or None when the account is free.

    THE RULE, QUOTED RATHER THAN SUMMARISED. BR-MET-024: *"**Dispute** records a
    dispute marker + reason on the read … v1 dispute flow per the OQ-043
    closure (PO R6): record + flag, and the account is **HELD from the bill run
    until a System Admin clears** the dispute."*

    So this refuses the ACCOUNT, at prepare, before anything is priced. Not a
    decision on S31.3 — a clerk cannot opt past it, because the closure gives
    the release to a System Admin clearing the marker and to nobody else.

    **AN UNPUBLISHED SEAM DOES NOT SILENTLY RELEASE THE HOLD.** If metering has
    not published `dispute_holds_for_unit` the run does not quietly bill every
    account as if no dispute existed — it blocks nothing and SAYS SO on the
    account it could not check, because "we could not tell" and "there is no
    dispute" are different facts and only one of them is safe to bill on. That
    is the same posture `_readings_for` takes when the reads seam is absent, and
    it is the posture DEF-046's chip-stuck-at-zero taught: a silent zero reads
    as good news.

    The detail names the meter, the reason and the disputed QUANTITY WITH ITS
    UNIT (CLAUDE.md rule 3) — a clerk reading the exception must see the number
    that is being argued about, not an id.
    """
    if dispute_holds is None:
        return AccountProblem(
            reason=RUN_ACCOUNT_HELD_BY_DISPUTE,
            detail=(
                "metering has not published dispute_holds_for_unit, so this run cannot tell "
                "whether any of this account's readings is disputed. BR-MET-024 holds an "
                "account with an uncleared dispute out of the run, and billing one that MIGHT "
                "be disputed as though it were agreed is the failure that rule exists to "
                "prevent — so the account is held until the seam answers."
            ),
            account_id=str(account.id),
            account_no=account.account_no,
            unit_id=(str(account.unit_id) if account.unit_id else None),  # CR-056 W1: nullable
        )
    # EVERY unit this account's bill covers (BR-CUS-068), not just the anchor:
    # a disputed read on the shared-irrigation meter must hold the owner's bill
    # exactly as one on the hallway meter does, because both are priced onto it.
    # `None` keeps the anchor-only read this function has always taken.
    holds = [
        hold
        # `CR-056` W1 — `(None,)` would ask metering for holds on no unit at
        # all. A master that names no unit has its covered units in `unit_ids`;
        # if it has neither, there is nothing to hold and nothing to ask about.
        for unit_id in (unit_ids or ((account.unit_id,) if account.unit_id else ()))
        for hold in dispute_holds(unit_id) or ()
    ]
    if not holds:
        return None
    first = holds[0]
    extra = (
        f" (and {len(holds) - 1} other disputed reading(s) on this account)"
        if len(holds) > 1
        else ""
    )
    return AccountProblem(
        reason=RUN_ACCOUNT_HELD_BY_DISPUTE,
        detail=(
            f"meter {first.get('meter') or '—'} — the reading of "
            f"{first.get('usage_display') or 'an unstated quantity'} taken "
            f"{first.get('read_at') or 'on an unstated date'} is DISPUTED: "
            f"\"{first.get('dispute_reason') or 'no reason recorded'}\"{extra}. "
            "BR-MET-024 / the OQ-043 closure hold this account out of the bill run until a "
            "System Admin clears the dispute — billing it now would charge the customer for a "
            "reading they have told you is wrong, as though they had agreed it. Clear or "
            "resolve the dispute on the read (Reads → the reading → Dispute) and re-prepare."
        ),
        account_id=str(account.id),
        account_no=account.account_no,
        unit_id=(str(account.unit_id) if account.unit_id else None),  # CR-056 W1: nullable
    )


#: CR-060 task T14 — how many accounts one server-side cursor fetch carries.
#: 500 rows of three-join `Account` is a few hundred kilobytes, and the whole
#: point of the change is that the number does not grow with the run.
ACCOUNT_CHUNK = 500


def _account_stream(accounts: Any) -> Any:
    """Walk the run's accounts WITHOUT materialising them (CR-060 task T14).

    CR-060 §6 names the old `for account in accounts` over a `list(...)` as
    *"the thing that breaks first above ~20,000 accounts"*: the queryset was
    materialised once and held for the whole of `prepare_run`, so a run's peak
    memory grew linearly with the book. `.iterator()` streams it through a
    server-side cursor instead, and the run's memory stops depending on the
    tenant's size.

    **IT IS A FUNCTION AND NOT A `.iterator()` AT EACH CALL SITE** for one
    reason: `prepare_run` walks the accounts THREE times and the empty-scope
    case is a plain tuple, which has no `.iterator()`. Written inline, the third
    loop would raise `AttributeError` on a run whose cycle has no service points
    — a run that is not an error and must still report why it billed nobody.

    ⚠ **THREE WALKS ARE THREE QUERIES NOW, AND THAT IS THE TRADE.** It is safe
    because `customers.selectors.accounts_for_bill_run` orders by
    `("account_no", "id")` at the source, so every walk sees the same accounts
    in the same order and a run still reads the same way twice. It is also why
    the chunk size is set rather than left to the driver: a run over 80,000
    accounts is 160 round trips per walk, not 80,000.
    """
    iterator = getattr(accounts, "iterator", None)
    if callable(iterator) and hasattr(accounts, "query"):
        return iterator(chunk_size=ACCOUNT_CHUNK)
    return accounts


def prepare_run(
    *,
    cycle_id: Any,
    period_start: date,
    period_end: date,
    service_date: date,
    cycle_days: int | None = None,
    scope_services: tuple[str, ...] | None = None,
    resume_skip: Callable[[Any, Any], bool] | None = None,
    price_date: date | None = None,
    only_accounts: Any = None,
    payment_window: tuple[date | None, date | None] | None = None,
    on_account: Callable[[Any], None] | None = None,
    check_categories: Any = None,
    quiet_account_ids: Any = None,
) -> PreparedRun:
    """Resolve the run's scope and gather every account in it. Writes nothing.

    `resume_skip(account_id, account_no) -> bool` is CR-051 task 11's
    checkpoint, and it is None everywhere except a re-delivered calculate job.
    An account it answers True for is not gathered and does not appear in
    `ready` — which is the whole point, because the gather is 88% of what a
    run costs (task 21's measurement) and a resumed worker has already paid it
    for that account. The POLICY lives in `apps/billing/run_resume.py`, never
    here: this function is told what to skip and does not decide it.

    ⚠ **THE SCOPE CHECK STILL SEES EVERY ACCOUNT.** The skip is applied inside
    the gather loop and never to the coverage map above it, so a resumed pass
    reports the same *"unit in this cycle with no billable account"* rows as a
    full one. Skipping earlier would turn every already-drafted account's unit
    into a phantom configuration problem on the exception tab.

    `service_date` is passed explicitly and never derived from a clock. It is
    the pricing pivot (BR-RAT-007): a June run re-executed in 2031 must reach
    June's tariff versions, and a function that read `date.today()` could not
    promise that. BR-BIL-039's "no clock" rule applies to the stages; this is
    the same discipline one layer out, where it is the difference between a
    reproducible bill and a plausible one.

    `cycle_days` defaults to the period's own length. It is separable because
    B4.3 prorates on service days ÷ CYCLE days, and a short first period must
    not shrink the denominator — that would charge a mid-month move-in the full
    base charge for half a month.

    ── CR-051 TASK 22 · ONE PASS, ONE CACHE ─────────────────────────────────
    The whole pass runs inside `seam_batch.pass_cache()`, so the eight run- and
    plan-scoped seam reads are made ONCE for the run rather than once per
    account. It is opened HERE rather than by the callers on purpose: every
    caller then gets it and no caller can forget it (hard-won law 2), and — the
    part that matters more — **the cache cannot outlive the pass**, which is
    what keeps `selectors.prepared_for`'s promise that *"a clerk who fixes a
    plan and reloads must see the fix"*.

    ── THE BULK RUN'S CHECK (2026-09-30, plan B7/B8/B12/B15/B16) ─────────────
    * `price_date` 🔒 — BR-BIL-1055: the rate VERSION is the one in force on
      this date (the PERIOD END on a bulk run); `service_date` stays the bill
      date the documents carry. None prices at `service_date`, byte for byte
      what every caller before the rule did.
    * `only_accounts` — B15, re-check NAMED accounts: the walk is narrowed to
      them and the RUN-SHAPE rows (no service points, a unit with nobody to
      bill) are not reported, because a partial pass cannot see the whole
      cycle and would report phantoms.
    * `payment_window` — `(bill_date, due_date)`: the payment checks
      (BR-BIL-1053) need the run's dates; None skips them rather than guessing
      a date (BR-TEN-043).
    * `on_account(AccountCheck)` — called after each account is checked; the
      background Check uses it for progress and for saving the results.
    * `check_categories` / `quiet_account_ids` — DEF-BIL-8286, a PARTIAL
      re-check: only those categories of the Check (and what is downstream of
      them) are re-run; an account in `quiet_ids` was saved quiet. None is the
      full pass every caller before 2026-09-30 made. A partial pass is for the
      saved store only — its `ready` list is not a billing answer.

    Each account is checked by `check_engine.check_account`: EVERY check runs,
    each in its own savepoint, and no problem ends the account's checks or the
    run (BR-BIL-1052). Only a UTILITY-WIDE fault — a module not answering —
    stops the pass, as `UtilityWideStop`, naming what and who.
    """
    with seam_batch.pass_cache():
        return _prepare_run(
            cycle_id=cycle_id,
            period_start=period_start,
            period_end=period_end,
            service_date=service_date,
            cycle_days=cycle_days,
            scope_services=scope_services,
            resume_skip=resume_skip,
            price_date=price_date,
            only_accounts=only_accounts,
            payment_window=payment_window,
            on_account=on_account,
            check_categories=check_categories,
            quiet_account_ids=quiet_account_ids,
        )


def _prepare_run(
    *,
    cycle_id: Any,
    period_start: date,
    period_end: date,
    service_date: date,
    cycle_days: int | None = None,
    scope_services: tuple[str, ...] | None = None,
    resume_skip: Callable[[Any, Any], bool] | None = None,
    price_date: date | None = None,
    only_accounts: Any = None,
    payment_window: tuple[date | None, date | None] | None = None,
    on_account: Callable[[Any], None] | None = None,
    check_categories: Any = None,
    quiet_account_ids: Any = None,
) -> PreparedRun:
    """`prepare_run`'s body, with the pass cache already open around it.

    Split out so the cache is opened in exactly one place and the body's
    indentation did not move — a sixty-line re-indent in a file five lanes
    touch is a diff nobody can read (CLAUDE.md law 11: you author hunks, and a
    commit is a statement about files).
    """
    if period_end < period_start:
        raise BillingRuleError(
            f"period {period_start} → {period_end} ends before it begins. "
            "Every proration in B4.3 divides by this window."
        )
    days = cycle_days if cycle_days is not None else (period_end - period_start).days + 1

    unit_ids, accounts = _run_scope(cycle_id, scope_services)
    # B15 — re-check NAMED accounts only. The run-shape rows below are skipped
    # on a partial pass (see the docstring).
    wanted = None if only_accounts is None else {str(one) for one in only_accounts}
    if wanted is not None and hasattr(accounts, "filter"):
        # B28 — a named pass (a batch is at most 500) is read ONCE into a list:
        # the three walks below would otherwise each re-run the scope query,
        # whose IN list is the whole cycle's units (40,000 on the J73 world).
        accounts = list(accounts.filter(pk__in=list(wanted)))
    elif wanted is not None:
        accounts = tuple(a for a in accounts if str(a.id) in wanted)

    ready: list[AccountBillingData] = []
    blocked: list[AccountProblem] = []
    decisions: list[AccountProblem] = []
    silent: list[AccountProblem] = []

    if not unit_ids and wanted is None:
        # An empty run is not an error, but it must not be silent either: a
        # cycle nobody attached a service point to produces zero bills and
        # looks exactly like a successful run of zero accounts.
        blocked.append(
            AccountProblem(
                reason=RUN_NO_SCOPE,
                detail=(
                    f"cycle {cycle_id} has no service points in scope, so the run "
                    "covers no accounts. Check the cycle's routes and the run's "
                    "service scope before reading this as 'nothing to bill'."
                ),
            )
        )

    # DEF-572 — WHICH UNITS THIS RUN'S ACCOUNTS COVER, not which units they
    # ANCHOR on. A master account (BR-CUS-068) anchors on the premises' first
    # common area and covers the rest through its service agreements, so the
    # anchor-shaped set reported every OTHER covered common area as *"in this
    # cycle but has no billable account"* — a false alarm on the exception tab
    # for a unit that is billed, beside the true ones a clerk must act on.
    #
    # Resolved here for the scope check and again inside `gather_account` and
    # `readings_for_account`, which is deliberate rather than sloppy: those two
    # are called from single-bill, back-bill and split paths that this loop
    # never runs, so the coverage cannot be an argument they trust a caller to
    # supply. It costs NOTHING on an ordinary account — customers answers
    # `[unit_id]` from the row already in hand, with no query — and a handful of
    # reads on the rare master account.
    coverage, unbilled = _coverage_and_unbilled(unit_ids if wanted is None else (), accounts)
    blocked.extend(unbilled)

    # ── BR-BIL-1052 (PO 2026-09-30) · EVERY CHECK ON EVERY ACCOUNT ─────────
    # PO verbatim: *"please start and ensure between step 1 and 2 for given
    # account you runs allc heck sand dont stop at first problem"*. The body
    # that lived here stopped an account at its FIRST problem — a dispute hold
    # or the first gather refusal ended its checks (`DEF-BIL-8205`) — and let a
    # plain `BillingRuleError` from one account end the whole pass
    # (`DEF-BIL-8206`/`8207`). It now lives in `check_engine.check_account`,
    # which runs every check, each in its own savepoint, and records every
    # problem. The legacy lists below keep their meaning exactly.
    from apps.billing import check_engine

    context = check_engine.CheckContext.for_pass(
        period_start=period_start,
        period_end=period_end,
        price_date=price_date or service_date,
        cycle_days=days,
        scope_services=scope_services,
        payment_window=payment_window,
    )
    findings: dict[str, tuple[Any, ...]] = {}
    warnings: list[AccountProblem] = []
    # DEF-BIL-8286 — a PARTIAL re-check asks payments nothing unless the
    # payments category is among what it re-runs.
    rerun = None if check_categories is None else check_engine.downstream(check_categories)
    asks_payments = rerun is None or check_engine.CATEGORY_PAYMENTS in rerun
    quiet_ids = {str(one) for one in (quiet_account_ids or ())}
    # B27 — each batch of 500 is READ ONCE (`CheckContext.batches`): its read
    # time is taken first (DEF-BIL-8491), then payments and the owning modules'
    # batch reads, inside a memo that closes with the batch.
    for chunk in context.batches(_account_stream(accounts), payments=asks_payments):
        for account in chunk:
            # CR-051 task 11 — this account was finished by an earlier attempt
            # of the SAME job; see `run_resume` for why the predicate needs both
            # a cursor and the write before it may answer True.
            if resume_skip is not None and resume_skip(account.id, account.account_no):
                continue
            checked = check_engine.check_account(
                account,
                context,
                covered_unit_ids=coverage.get(str(account.id)),
                categories=check_categories,
                was_quiet=str(account.id) in quiet_ids,
            )
            findings[checked.account_id] = tuple(checked.findings)
            if on_account is not None:
                on_account(checked)
            if checked.rerun is not None:
                # A partial answer is merged into the saved store by the caller;
                # it is not a whole account, so it joins none of the lists.
                continue
            if checked.status == check_engine.STATUS_BLOCKED:
                blocked.append(checked.first_blocking().as_problem())
            elif checked.status == check_engine.STATUS_QUIET:
                silent.append(checked.quiet_problem())
            else:
                ready.append(checked.data)
                decisions.extend(checked.decision_problems())
                warnings.extend(checked.warning_problems())

    return PreparedRun(
        cycle_id=str(cycle_id),
        period_start=period_start,
        period_end=period_end,
        service_date=service_date,
        cycle_days=days,
        scope_services=scope_services,
        ready=tuple(ready),
        blocked=tuple(blocked),
        decisions=tuple(decisions),
        silent=tuple(silent),
        # CR-038 W8 — the coverage the loop above already resolved, carried out
        # for the read analysis (see the field's own comment).
        coverage=coverage,
        findings=findings,
        warnings=tuple(warnings),
        price_date=price_date,
        unavailable=context.unavailable,
    )



#: B28 — the cycle's unit ids, resolved ONCE for one batch of the parallel
#: Check and reused by that batch's own `prepare_run` (`open_scope_units`).
#: Measured on the 40,000-account J73 world: `units_in_cycle` costs ~1 s, and a
#: batch asked it twice — a tenth of a 500-account batch's work. A memo inside
#: ONE computation, never a stored answer (the `seam_batch` ruling), keyed on
#: the cycle and the service scope so it can answer nothing else.
_SCOPE_UNITS: ContextVar[tuple | None] = ContextVar("billing_scope_units", default=None)


def open_scope_units(cycle_id: Any, scope_services: Any, unit_ids: Any) -> Any:
    key = (str(cycle_id), None if scope_services is None else tuple(scope_services))
    return _SCOPE_UNITS.set((key, list(unit_ids)))


def close_scope_units(token: Any) -> None:
    _SCOPE_UNITS.reset(token)


def _run_scope(cycle_id: Any, scope_services: tuple[str, ...] | None) -> tuple[Any, Any]:
    """WHO THIS RUN BILLS — `(unit_ids, accounts)`, the two seams `_prepare_run`
    opens with, every refusal a `UtilityWideStop` naming the module (B21).

    Moved out of `_prepare_run` VERBATIM for B28 (2026-10-01), because the
    batch planner and each batch of the parallel Check must resolve exactly the
    population the pass resolves — two places answering *who does this run
    bill* is how a batch comes to walk a different population from its plan
    (the same reason `scope_account_count` sits beside it). `accounts` is a
    QUERYSET ordered by `("account_no", "id")`, or `()` when the cycle covers
    no unit — never materialised here (CR-060 task T14).
    """
    units_in_cycle = _resolve("metering", "units_in_cycle")
    if units_in_cycle is None:
        raise UtilityWideStop(
            MODULE_METER_READS,
            "metering has not published units_in_cycle, so the run's scope "
            "cannot be resolved. A run over an unknown scope is not a run.",
        )
    known = _SCOPE_UNITS.get()
    key = (str(cycle_id), None if scope_services is None else tuple(scope_services))
    if known is not None and known[0] == key:
        unit_ids = list(known[1])
    else:
        try:
            unit_ids = units_in_cycle(
                cycle_id, service_codes=list(scope_services) if scope_services is not None else None
            )
        except BillingRuleError:
            raise
        except Exception as broken:  # noqa: BLE001 — B21: a module not answering
            core_jobs.reraise_if_time_limit(broken)
            raise UtilityWideStop.from_error(MODULE_METER_READS, broken) from broken

    accounts_for = _resolve("customers", "accounts_for_bill_run")
    if accounts_for is None:
        raise UtilityWideStop(
            MODULE_CUSTOMERS,
            "customers has not published accounts_for_bill_run, so the run "
            "cannot resolve who is billed.",
        )
    if _resolve("metering", "billing_reads_for_unit") is None:
        # Asked ONCE here rather than failing every account one by one: the
        # seam is a property of the deployment, and 40,000 identical blocked
        # rows would hide the one sentence that matters (B21).
        raise UtilityWideStop(
            MODULE_METER_READS,
            "metering has not published billing_reads_for_unit, so no consumption can be read.",
        )
    # ── CR-060 TASK T14 — THE QUERYSET IS NOT MATERIALISED ────────────────
    # This read `list(...)` until 2026-09-02, and CR-060 §6 names it as *"the
    # thing that breaks first above ~20,000 accounts"*: every `Account` row the
    # run covers, with three `select_related` joins each, held in memory for the
    # whole of `prepare_run` — memory nobody budgeted at the ceiling T1 settled
    # the product must not hard-limit.
    #
    # It is a QUERYSET now, and each of the three loops below walks it with
    # `.iterator()`. THREE walks means three server-side-cursor queries rather
    # than one query and one list, which is the trade this makes deliberately:
    # the rows are `order_by("account_no", "id")` at the source, so every walk
    # sees the same accounts in the same order and a run still reads the same
    # way twice. `accounts_for_bill_run` uses `select_related` only — no
    # `prefetch_related` — so `.iterator()` is lossless here.
    #
    # ⚠ **`_account_stream` EXISTS BECAUSE `()` HAS NO `.iterator()`.** The
    # empty-scope case below is a plain tuple and must stay one: turning it into
    # a queryset would mean a query for a run we already know covers nothing.
    try:
        accounts = accounts_for(unit_ids) if unit_ids else ()
    except BillingRuleError:
        raise
    except Exception as broken:  # noqa: BLE001 — B21: a module not answering
        core_jobs.reraise_if_time_limit(broken)
        raise UtilityWideStop.from_error(MODULE_CUSTOMERS, broken) from broken
    return unit_ids, accounts


def scope_accounts(cycle_id: Any, scope_services: tuple[str, ...] | None = None) -> Any:
    """B28 — the run's accounts as `_prepare_run` resolves them (`_run_scope`)."""
    return _run_scope(cycle_id, scope_services)[1]



def _coverage_and_unbilled(
    unit_ids: Any, accounts: Any
) -> tuple[dict[str, tuple[str, ...]], list[AccountProblem]]:
    """`(coverage, unbilled)` — which units each account covers, and a
    `RUN_UNIT_HAS_NO_ACCOUNT` row for every unit of `unit_ids` nobody bills.

    Moved out of `_prepare_run` VERBATIM for B28 (2026-10-01): a batch of the
    parallel Check walks 500 accounts and cannot see the cycle, so the run-
    shape rows are computed ONCE, after every batch, by `unbilled_unit_ids`
    over the whole scope — through this same function, so the batched Check
    and the one-pass prepare report the same units. Pass `unit_ids=()` to get
    the coverage only (a partial pass reports no run-shape rows).
    """
    unbilled: list[AccountProblem] = []
    coverage: dict[str, tuple[str, ...]] = {}
    for account in _account_stream(accounts):
        try:
            coverage[str(account.id)] = gather.covered_units(account)
        except gather.GatherProblem:
            # The account cannot be gathered at all; the loop below records the
            # named problem against it. Its anchor still counts as billed, so a
            # blocked account does not also raise a phantom no-account row.
            # `CR-056` W1 — a master that names no unit has no anchor to fall
            # back on. `()` is the honest answer: the account is blocked, and its
            # covered units go on being reported as unbilled by the loop below,
            # which is TRUE while it cannot be gathered.
            coverage[str(account.id)] = (str(account.unit_id),) if account.unit_id else ()
    # ⚠ **`DEF-2960` — THE BILLED SET IS BOTH HALVES OF WHAT A MASTER'S BILL
    # PRICES, AND IT USED TO BE ONE.** `coverage` above answers a master's
    # COMMON AREAS. `BR-CUS-170` puts a SECOND set of units on the same bill —
    # every unit on that premises with no occupying account, one base charge
    # each (PO 2026-08-31: six empty flats at `$30.50` bill `$183.00`) — and
    # `base_charge_only_coverage` builds it by EXCLUDING everything
    # `covered_unit_ids` already names, so the two sets are disjoint by
    # construction. The union below therefore missed every empty unit the owner
    # IS charged for, and each one was reported as *"in this cycle but has no
    # billable account"*: `DEF-572`'s false alarm arriving from the other end,
    # about a unit that IS billed, on the tab a clerk is meant to act on.
    #
    # ⚠ **AND IT IS THE HALF `CR-056` TASK 22 TURNS ON.** What must GO ON being
    # reported is an unoccupied unit that reaches NOBODY — no owner account
    # exists, so its standing charge has nowhere to post. *"No lines because
    # nothing falls to it"* and *"no lines although the premises HAS an
    # unoccupied unit"* are different facts and only one of them is good news
    # (PO 2026-08-31, consequence 3). Adding the first set is what leaves the
    # second one visible instead of buried among false alarms.
    #
    # **IT COSTS NOTHING ON AN ORDINARY ACCOUNT.** `base_charge_only_units`
    # short-circuits on `kind != master` before any query, so the loop is one
    # attribute read per ordinary account and a handful of reads per master.
    billed_units = {unit_id for units in coverage.values() for unit_id in units}
    for account in _account_stream(accounts):
        try:
            billed_units |= {
                str(entry.get("unit_id"))
                for entry in gather.base_charge_only_units(account)
                if entry.get("unit_id")
            }
        except gather.GatherProblem:
            # The seam could not answer for this account. It is reported as a
            # blocked account by the loop below and its units go on being
            # reported as unbilled, which is TRUE while nobody can say who pays.
            continue
    for unit_id in unit_ids:
        if unit_id not in billed_units:
            # A metered service point with nobody to bill. Unlike a closed
            # account (correctly out of scope), this is a real configuration
            # problem: usage is being recorded against no customer.
            unbilled.append(
                AccountProblem(
                    reason=RUN_UNIT_HAS_NO_ACCOUNT,
                    detail=(
                        f"unit {unit_id} is in this cycle but has no billable "
                        "account. Its meters are recording usage nobody is being "
                        "billed for."
                    ),
                    unit_id=unit_id,
                )
            )
    return coverage, unbilled


def unbilled_unit_ids(cycle_id: Any, scope_services: tuple[str, ...] | None = None) -> list[str]:
    """B28 — the units in this run's scope that NO account bills (the
    `RUN_UNIT_HAS_NO_ACCOUNT` rows a whole pass reports), over the whole scope.
    The batched Check asks this once, when every batch is done."""
    unit_ids, accounts = _run_scope(cycle_id, scope_services)
    _coverage, unbilled = _coverage_and_unbilled(unit_ids, accounts)
    return sorted({str(p.unit_id) for p in unbilled if p.unit_id})


def scope_account_count(
    *,
    cycle_id: Any,
    scope_services: tuple[str, ...] | None = None,
) -> int:
    """HOW MANY accounts this run would bill — the two seams above, and no more.

    CR-051 task 30 needs a size BEFORE the run starts, and `prepare_run` is not
    it: at the measured cost per account, asking `prepare_run` how big a run is
    means paying for the whole run to find out. This asks the SAME two
    questions `_prepare_run` opens with — *which units does this cycle cover*
    and *which accounts occupy them* — and counts the answer in the database.

    ⚠ **IT IS DELIBERATELY THE SAME TWO SEAMS, IN THE SAME ORDER, AND IT SITS
    HERE RATHER THAN IN A CALLER.** Two places that answer *who does this run
    bill* is how a ceiling comes to refuse a different population from the one
    the run would walk. If `_prepare_run`'s scope resolution ever changes, this
    is four lines away from it and the reader has both on one screen.

    It is a COUNT and never a filter: nothing here decides who is billed. An
    unpublished seam refuses by the same sentence `_prepare_run` uses, because
    a run over an unknown scope is not a run.
    """
    units_in_cycle = _resolve("metering", "units_in_cycle")
    if units_in_cycle is None:
        raise BillingRuleError(
            "metering has not published units_in_cycle, so the run's scope "
            "cannot be resolved. A run over an unknown scope is not a run."
        )
    unit_ids = units_in_cycle(
        cycle_id, service_codes=list(scope_services) if scope_services is not None else None
    )
    if not unit_ids:
        return 0
    accounts_for = _resolve("customers", "accounts_for_bill_run")
    if accounts_for is None:
        raise BillingRuleError(
            "customers has not published accounts_for_bill_run, so the run "
            "cannot resolve who is billed."
        )
    # `.count()` on the queryset, not `len(list(...))`: the point of this
    # function is that it does NOT load the population it is sizing.
    return int(accounts_for(unit_ids).count())


def calculate_account(
    data: AccountBillingData,
    *,
    bill_run: Any = None,
    service_date: date,
    bill_type: str = "cycle",
) -> Any:
    """Phase 2 for ONE account: stages 1 → 2 → 3-5 → 6. Writes a DRAFT bill,
    or answers **`None`** where the account priced no lines at all.

    ⚠ **`None` IS A REAL ANSWER AND IS NOT AN ERROR (`BR-BIL-1024`).** It means
    the run reached the end for this account and there was nothing to charge —
    the PO's *"no lines, no document"*, decided after pricing in
    `stages/assemble_document.py` rather than predicted here. Every caller must
    handle it; `_calculate_run` files the account as SILENT, which is neither a
    draft nor a break.

    The PO's second clause — *"then run the billing in batch process in the
    background"* — one account at a time, because one account is the unit of
    atomicity: a run of 500 where number 7 fails must leave 499 drafts and one
    named break, not a rollback of the morning's work.

    Stages 3–5 go through `price_bill`, not `price_period`. A plan is a bundle,
    so one account with electric and water is ONE call whose tax runs once over
    the combined base (BR-RAT-062 / GT-17). Calling per service and summing
    would put a different tax on the bill — see DEF-032.

    An account still carrying an UNRESOLVED missing read is refused here rather
    than billed without that service. BR-BIL-015 makes the choice a human's
    (estimate / hold / bill without it), and phase 1 is where it is taken; a
    calculate pass that quietly billed the remaining services would take the
    third option on the clerk's behalf and leave no record that it had.
    """
    priced_account = price_account(data)
    return assemble_document(
        usage=priced_account.usage,
        priced=priced_account.priced,
        tenant_id=core_tenancy.current_tenant_id(),
        account_id=data.account_id,
        bill_run=bill_run,
        period_start=data.period_start,
        period_end=data.period_end,
        service_date=service_date,
        bill_type=bill_type,
    )


@dataclass(frozen=True)
class PricedAccount:
    """Stages 1–5 for one account, with **nothing written** — CR-075 wave F.

    `usage` and `priced` are exactly the two arguments stage 6 consumes, held
    together so there is no way to obtain one without the other.
    """

    usage: Any
    priced: Any
    #: True when the period was CUT at a rate-version or plan boundary and
    #: `midperiod` priced each stretch on its own version (`BR-RAT-114`).
    split: bool
    #: PO ruling 2026-09-30 — the named warnings this account's bill carries
    #: (`AccountBillingData.warnings`, plus each split stretch's), in the
    #: `{"key", "params"}` shape `apps/billing/bill_warnings.py` owns. The
    #: same tuple is frozen into the draft's `bill_payload["warnings"]` by
    #: `price_account`, so the preview, the draft and the run read one list.
    warnings: tuple[dict, ...] = ()


def account_warnings(data: AccountBillingData) -> tuple[dict, ...]:
    """Every warning on this account's gathered data, each once — the parent's
    and, on a split account, every stretch's (each stretch is gathered at its
    own service date and can find a base the parent did not)."""
    segments = getattr(data, "split_segments", ()) or ()
    return bill_warnings.merged(
        getattr(data, "warnings", ()) or (),
        *(getattr(getattr(segment, "data", None), "warnings", ()) or () for segment in segments),
    )


def with_warnings_in_snapshot(usage: Any, warnings: tuple[dict, ...]) -> Any:
    """`usage` whose subscription snapshot also carries `warnings`.

    ⚠ **THIS IS HOW A BULK RUN'S DRAFT CARRIES THEM, AND IT WRITES NOTHING.**
    Stage 6 builds `bill_payload` from `usage.subscription.snapshot`
    (`assemble_document._snapshot_payload` copies it first), so a key put
    here reaches every draft this function's callers assemble — a run, a
    one-time bill, a final bill — without stage 6 learning anything new.
    **No warnings, no key**: an account nothing warns about keeps the payload
    it has always had, byte for byte.
    """
    if not warnings:
        return usage
    subscription = usage.subscription
    snapshot = dict(subscription.snapshot or {})
    snapshot["warnings"] = [dict(row) for row in warnings]
    return replace(usage, subscription=replace(subscription, snapshot=snapshot))


def price_account(data: AccountBillingData) -> PricedAccount:
    """Stages 1 → 5 for ONE account. **The five pure stages, and no write.**

    ⚠ **THIS FUNCTION EXISTS SO THAT A SECOND PRICING PATH CANNOT.** It was
    extracted from `calculate_account` by `CR-075` wave F, unchanged line for
    line, because runbook 23 — the *Test bill* — has to price an account
    exactly as a bill run does and **write nothing at all**: it is a Check, and
    a Check is CONSTRUCTED with no writer (`BR-RBS-002`). Before this, the only
    way to reach a priced line from an account was `calculate_account`, which
    ends in stage 6 — a draft invoice **and a consumed bill number**
    (`BR-BIL-063`). Wave F's `TC-RBS-004.3` requires the test bill and the run
    to produce an identical line set and identical amounts **to four
    decimals**, and the only way to make that true by CONSTRUCTION rather than
    by assertion is for both to be this one function.
    `assemble_document`'s own docstring already drew the line in the right
    place — *"Stages 1–5 are pure and produce numbers. This one is where those
    numbers become a row"* — and this is that sentence given a name.

    **DO NOT INLINE IT BACK.** A copy of these five stages anywhere else is how
    a utility discovers that the figure a clerk was shown before go-live is not
    the figure on the bill, and every ❄️ FROZEN B4/B5 figure is quoted once.

    Raises `GatherProblem` for every condition that stops this account being
    priced — unchanged, with the same reason codes and the same sentences, so
    the run's exception list and the test bill's refusal say the same thing.
    """
    # BR-RAT-114 (PO 2026-08-22): a period phase 1 CUT at a rate-version or
    # plan boundary prices per sub-period, each at the version in force THEN,
    # taxed once, on ONE bill. Empty on every unsplit account — which is every
    # account this function ever saw before 2026-08-22 — so the path below is
    # untouched and every ❄️ frozen figure reproduces byte for byte.
    warnings = account_warnings(data)
    if getattr(data, "split_segments", ()):
        usage, priced = midperiod.price_split_account(data)
        return PricedAccount(
            usage=with_warnings_in_snapshot(usage, warnings),
            priced=priced,
            split=True,
            warnings=warnings,
        )
    subscription = resolve_subscription(data)
    usage = measure_consumption(subscription, data)

    # ⚠ DEF-161: FOUR reasons are exempt and each is a different fact — they
    # are `measure_consumption.EXEMPT_FROM_MISSING_READ`, read below and
    # argued there. The two the defect was filed for: ABSENT_BASE_ONLY is an
    # ACCOUNT fact (BR-CUS-055 — this account bills base charges and no usage)
    # and ABSENT_NOT_USAGE_MEASURED is a TARIFF fact (BR-RAT-015 — this service
    # prices no consumption of its own, so no reading of its own can be
    # missing). Neither is an unresolved read, and before the second existed a
    # plan carrying a sewer service billed as a percentage of water could not
    # produce a single bill. ⚠ **This sentence said TWO until 2026-09-15**; the
    # list had grown to four beneath it, which is the small version of
    # `DEF-BIL-5326` — a count quoted beside a list that moved.
    # ── BR-RAT-090 (DEF-1813) · AN ABSENT COUNT REFUSES BY ITS OWN NAME ──────
    # An unmetered service bills a COUNT of its assets on the unit, and *"no
    # carts recorded"* and *"zero carts"* are different facts of which only one
    # is billable. This refusal is raised BEFORE the missing-read refusal below
    # and with a reason of its own, because the sentence a clerk reads decides
    # what they go and do: *"trash still has no usable read"* sends them to the
    # Reads tab to estimate a register that does not exist, and the work is
    # actually to go and count the carts on the unit.
    counted = tuple(
        service
        for service in usage.unmeasured
        if service.absent_reason
        in (
            measure_consumption_stage.ABSENT_ASSET_COUNT_UNAVAILABLE,
            measure_consumption_stage.ABSENT_ASSET_COUNT_UNIT_UNSTATED,
        )
    )
    if counted:
        names = ", ".join(service.service_code for service in counted)
        raise GatherProblem(
            CALC_ASSET_COUNT_UNAVAILABLE,
            f"account {data.account_no}: {names} is billed by a COUNT of its assets on "
            "the unit (BR-RAT-090) and no count could be determined. The bill "
            "refuses rather than billing zero — 'no carts recorded' and 'zero "
            "carts' are different facts, and a household with three carts billed "
            "for none is a document that looks entirely normal.",
            service_code=counted[0].service_code,
        )

    # ── CR-062 D1/H2 · AN UNSTATABLE CAPACITY REFUSES BY ITS OWN NAME ────────
    # A SUMMING service — one whose schedule prices per kW, per ERU or per Mbps
    # — has equipment on the unit that does not say how much capacity it is.
    # Raised BEFORE the missing-read refusal below and with a reason of its own,
    # for the reason the count's refusal above has one: the sentence a clerk
    # reads decides what they go and do. *"Solar still has no usable read"*
    # sends them to the Reads tab to estimate a register that does not exist;
    # the work is to open each panel and record which type it is.
    unstated_capacity = tuple(
        service
        for service in usage.unmeasured
        if service.absent_reason == measure_consumption_stage.ABSENT_INSTALLED_CAPACITY_UNRESOLVED
    )
    if unstated_capacity:
        names = ", ".join(service.service_code for service in unstated_capacity)
        # DEF-RAT-10220 (PO 2026-10-17: *"the bill run Check names the asset
        # whose size has no kW"*) — the asset NUMBERS metering published for
        # these services, so the clerk opens PV-00020 rather than the unit.
        unnamed = {service.service_code for service in unstated_capacity}
        assets = [
            asset_no
            for reading in data.readings
            if reading.service_code in unnamed
            for asset_no in (getattr(reading, "capacity_unresolved_assets", ()) or ())
        ]
        assets = list(dict.fromkeys(assets))
        named: dict[str, object] = {}
        if assets:
            listed = ", ".join(assets)
            named = {
                "message_key": "billing.check.capacityUnknownAssets",
                "clerk_detail": f"{listed}: size has no capacity.",
                "message_params": {"assets": listed, "service": unstated_capacity[0].service_code},
            }
        raise GatherProblem(
            CALC_INSTALLED_CAPACITY_UNRESOLVED,
            f"account {data.account_no}: {names} is priced per unit of INSTALLED "
            "CAPACITY (CR-062), and at least one piece of equipment on the unit does "
            "not record which size class it is — so the total cannot be stated. The "
            "bill refuses rather than totalling the equipment it does recognise: three "
            "panels of 2 kW, 4 kW and 8 kW are 14 kW, and a total assembled from the "
            "one panel that was recorded would bill a fraction of that on a document "
            "that foots. Record the size class on each of this unit's assets; the run "
            "continues for every other account."
            + (f" Assets: {', '.join(assets)}." if assets else ""),
            service_code=unstated_capacity[0].service_code,
            **named,  # type: ignore[arg-type]
        )

    # ⚠ **THE FOUR EXEMPT REASONS AND THE ARGUMENT FOR EACH ONE LIVE IN
    # `measure_consumption.EXEMPT_FROM_MISSING_READ`** — they were spelled out
    # here, in `midperiod` and (three reasons short) in `backbill` until
    # `DEF-BIL-5326` on 2026-09-15, when the sub-period path's stale copy was
    # found refusing a percent-of-service sewer that the list here has exempted
    # since DEF-161. Three literal copies of one money rule is how that
    # happened; read the tuple, and add a reason THERE or in none of them.
    unresolved = tuple(
        service
        for service in usage.unmeasured
        if service.absent_reason not in measure_consumption_stage.EXEMPT_FROM_MISSING_READ
    )
    if unresolved:
        names = ", ".join(service.service_code for service in unresolved)
        raise GatherProblem(
            CALC_UNRESOLVED_READ,
            f"account {data.account_no}: {names} still has no usable read and no "
            "decision. BR-BIL-015 makes that a choice — estimate it, hold the "
            "account, or bill without the service — and billing the rest would "
            "be taking the third one silently.",
            service_code=unresolved[0].service_code,
        )

    priced = rating_seam.price_bill(
        services=tuple((service.tariff, service.consumption) for service in usage.measured),
        # BR-BIL-028: on a hold the base charge continues and the usage line
        # stops. Passed apart so neither becomes the other.
        base_only_services=tuple(service.tariff for service in usage.unmeasured),
        period=subscription.period,
        account=rating_seam.AccountContext(
            currency=subscription.currency, tax_exempt=subscription.tax_exempt
        ),
        taxes=subscription.taxes,
        fees=subscription.fees,
        # DEF-502 — the account's granted discounts (enrolment ∩ plan binding,
        # resolved at gather). Applied once at bill level, between
        # apply-charges and compute-tax (BR-RAT-071); the seam omits the
        # argument entirely when the tuple is empty, so an undiscounted
        # account's call is byte-identical to before.
        discounts=getattr(subscription, "discounts", ()),
    )
    # DEF-BIL-8151 — PO 2026-09-30 ("SIX ANSWERS" (5), *"per service"*): a
    # counted service (trash, fire) prints as ONE line, its per-size usage lines
    # and its base joined. LAYOUT ONLY — the engine's finalized lines are summed
    # and no total, tax or rounding moves (2 carts × $18.00 = one $36.00 line;
    # fire's $60.00 + 2 × $12.00 = one $84.00 line). Here, and not in the 🔒
    # engine, because this is the one door the bill run and the one-time bill
    # both price through. The split-period branch above is not joined: its
    # lines each belong to one stretch.
    priced = counted_service_line.one_line_per_counted_service(
        priced,
        counted_service_line.counted_services(
            tuple(service.tariff for service in usage.measured)
            + tuple(service.tariff for service in usage.unmeasured)
        ),
    )
    return PricedAccount(
        usage=with_warnings_in_snapshot(usage, warnings),
        priced=priced,
        split=False,
        warnings=warnings,
    )


@dataclass(frozen=True)
class Break:
    """One account the CALCULATION could not draft, and where it stopped.

    BR-BIL-040 and BR-BIL-053: a break names the STAGE that failed, not just an
    error. "ACC-1201 failed" sends a clerk hunting; "ACC-1201 failed at
    measure-consumption: no usable read for gas" is something they can act on
    in a minute, which is the entire point of showing breaks before the totals.

    `retryable` is the difference between the two ways out the PO named. A
    missing read can be fixed and retried in place; an account whose plan does
    not exist cannot be fixed from this screen, and offering "retry now" on it
    would be offering a button that always fails.
    """

    account_id: str
    account_no: str
    stage: str
    reason: str
    detail: str
    retryable: bool = True


@dataclass(frozen=True)
class CalculatedRun:
    """Phase 2's output over a whole run — drafts, breaks, and nothing hidden.

    The PO's phase 3 is a screen over THIS: *"once billing is complete show
    immediately bills that are break and why; allow user to retry immediately
    by fixing the issue or mark for later"*. Both halves come back together for
    the same reason phase 1's do — a clerk needs the count that worked and the
    list that did not, in one place, and a function that raised on the first
    failure could give neither.
    """

    bill_run_id: str
    drafted: tuple[str, ...] = ()  # invoice ids, in the order they were written
    breaks: tuple[Break, ...] = ()
    #: `BR-BIL-1025` — accounts that priced NO LINES and therefore got no
    #: document. Neither a draft nor a break: the run did its whole job for
    #: them and the correct outcome was nothing. Carried so the screen can say
    #: *nothing to bill this period* in words instead of showing an account
    #: that simply is not there.
    silent: tuple[AccountProblem, ...] = ()

    @property
    def drafted_count(self) -> int:
        return len(self.drafted)

    @property
    def account_count(self) -> int:
        """Every account the calculation TOUCHED — the denominator on screen.

        "1,122 of 1,124" is only honest if the 1,124 counts the two that broke,
        and the silent ones for the same reason: the run examined them.
        """
        return len(self.drafted) + len(self.breaks) + len(self.silent)

    def breaks_by_stage(self) -> dict[str, tuple[Break, ...]]:
        """The phase-3 grouping: a clerk fixes all the missing reads at once."""
        groups: dict[str, list[Break]] = {}
        for item in self.breaks:
            groups.setdefault(item.stage, []).append(item)
        return {stage: tuple(items) for stage, items in groups.items()}


#: Which stage a failure came from. The pipeline's own names (BR-BIL-037), so a
#: break says the same word the stage does rather than a paraphrase that drifts.
STAGE_BY_REASON: dict[str, str] = {
    gather.GATHER_NO_UNIT: "resolve-subscription",
    gather.GATHER_NO_PLAN: "resolve-subscription",
    gather.GATHER_PLAN_UNPUBLISHED: "resolve-subscription",
    gather.GATHER_NO_TARIFF: "resolve-subscription",
    # `DEF-2381` — base charges exist for the service and none of them names
    # this account's customer type. The repair is on the charge code's
    # customer-type list in Plans & Rates, so BR-BIL-040 puts the finding on
    # the tab that owns stage 1's inputs — beside the plan and tariff findings
    # a clerk is already going there to fix, and never on Reads: not one
    # reading is wrong.
    gather.GATHER_NO_BASE_FOR_CUSTOMER_TYPE: "resolve-subscription",
    gather.GATHER_NO_VERSION: "price-usage",
    gather.GATHER_NO_CURRENCY: "resolve-subscription",
    # DEF-484 / DEF-514 — the schedule prices some connection sizes differently
    # and this connection's size cannot be stated. It is a PRICING input that is
    # missing, like a version that is not in force, so it sits with
    # GATHER_NO_VERSION on the same tab.
    gather.GATHER_SIZE_UNRESOLVED: "price-usage",
    # BR-RAT-101 / BR-RAT-102 — the plan surcharges outside the city and nobody
    # recorded which side of the line the PREMISES is on. The fix is on the
    # premises record, not in Plans & Rates, which is why this is
    # resolve-subscription and not price-usage: the tab a clerk lands on should
    # be the one nearest the record they have to go and edit.
    gather.GATHER_JURISDICTION_UNSTATED: "resolve-subscription",
    # BR-CUS-068's three coverage refusals. All resolve-subscription: each is a
    # fact about WHAT this account subscribes to — which units it covers, on
    # whose plan, taking which services — and the edit that clears any of them
    # is on the account's own coverage or on Plans & Rates, never on a read.
    # (Two of the three additionally need a PO ruling: OQ-334 and OQ-335.)
    gather.GATHER_COVERAGE_UNRESOLVED: "resolve-subscription",
    gather.GATHER_COVERAGE_MULTI_PLAN: "resolve-subscription",
    gather.GATHER_COVERAGE_SERVICE_TWICE: "resolve-subscription",
    CALC_UNRESOLVED_READ: "measure-consumption",
    # BR-RAT-090 — the quantity this service is priced on is missing, which is
    # measure-consumption's input, so it lands on the same tab as a missing read
    # (BR-BIL-040). The action differs and the message says so.
    CALC_ASSET_COUNT_UNAVAILABLE: "measure-consumption",
    RUN_READS_UNAVAILABLE: "measure-consumption",
    # A disputed reading is a measure-consumption input that a human has said is
    # wrong, so BR-BIL-040 puts it on the Reads tab beside the missing ones —
    # same tab, different action: a missing read is estimated, a disputed one is
    # cleared by a System Admin (OQ-043 closure).
    RUN_ACCOUNT_HELD_BY_DISPUTE: "measure-consumption",
    # The phase-1 DECISION form of the same fact, one phase earlier: a service
    # with no usable read that a human has not yet ruled on (BR-BIL-015). It is
    # measure-consumption's input that is missing, which is what puts it on the
    # Reads tab (BR-BIL-040). Added 2026-08-11 with `AccountProblem.stage`;
    # `_decisions_for` raises it and nothing else in this map is a decision.
    "missing_read": "measure-consumption",
    # `DEF-BIL-5270` — the account's reads do not pick up where its last ISSUED
    # bill left off. BR-BIL-040 puts it on the Reads tab because that is where
    # the input is: the anchor is a READ, and the repair is a read entered, a
    # re-read superseded or a meter exchange recorded. It is a DECISION, like
    # `missing_read` above and unlike everything else in this map.
    "billing_continuity": "measure-consumption",
    # `DEF-BIL-5270`'s anchor refusals. All measure-consumption, because all
    # four are about the READ the period opens at (BR-BIL-040 puts a finding on
    # the tab that owns the input), and all four are repaired in Meter Reads —
    # a segment priced, a read superseded, a multiplier recorded — never here.
    ANCHOR_METER_EXCHANGED: "measure-consumption",
    ANCHOR_REGISTER_WENT_BACKWARDS: "measure-consumption",
    ANCHOR_MULTIPLIER_UNSTATED: "measure-consumption",
    ANCHOR_TOU_UNANCHORABLE: "measure-consumption",
}

#: Breaks a clerk cannot fix from the phase-3 screen. Each needs a change
#: somewhere else — a plan published, a tariff version dated, a service
#: mapped — so "retry now" would be a button that always fails.
NOT_RETRYABLE_HERE = frozenset(
    {
        gather.GATHER_NO_PLAN,
        gather.GATHER_PLAN_UNPUBLISHED,
        gather.GATHER_NO_TARIFF,
        # `DEF-2381` — nothing on the phase-3 screen edits a charge code's
        # customer-type list, so "retry now" would be a button that always
        # fails. The edit is on Plans & Rates and the run is re-prepared after.
        gather.GATHER_NO_BASE_FOR_CUSTOMER_TYPE,
        gather.GATHER_NO_VERSION,
        gather.GATHER_NO_CURRENCY,
        # Both need an edit somewhere else — a size recorded against the meter,
        # a city-limits flag set on the premises — so "retry now" would be a
        # button that always fails.
        gather.GATHER_SIZE_UNRESOLVED,
        gather.GATHER_JURISDICTION_UNSTATED,
        # BR-CUS-068 — a coverage refusal is never cleared by pressing retry:
        # two of them wait on a PO ruling (OQ-334, OQ-335) and the third waits
        # on a deployment publishing a selector. A retry button on any of them
        # is a button that always fails.
        gather.GATHER_COVERAGE_UNRESOLVED,
        gather.GATHER_COVERAGE_MULTI_PLAN,
        gather.GATHER_COVERAGE_SERVICE_TWICE,
        # BR-RAT-090 (DEF-1813) — the carts have to be counted onto the unit, or
        # the service's billed UoM declared in Settings. Neither happens on this
        # screen, so "retry now" would be a button that always fails.
        CALC_ASSET_COUNT_UNAVAILABLE,
        # `DEF-BIL-5270` — nothing on the phase-3 screen exchanges a meter,
        # records a register span or prices two segments of a swap, so "retry
        # now" on any of these would be a button that always fails.
        ANCHOR_METER_EXCHANGED,
        ANCHOR_REGISTER_WENT_BACKWARDS,
        ANCHOR_MULTIPLIER_UNSTATED,
        ANCHOR_TOU_UNANCHORABLE,
    }
)


# ══════════════════════════════════════════════════════════════════════════
# CR-051 tasks 5 + 6 — THE BREAK LIST BECOMES A TABLE
#
# Until 2026-08-30 `CalculatedRun.breaks` was the ONLY place a break existed.
# `calculate_run` returned the tuple, the POST answered with it, and a clerk who
# navigated away lost the exception list and kept the drafts — the wrong half to
# lose, because the drafts are the ones nobody has to look at. `bill_run_breaks`
# (migration 0026) is the durable row, and these two functions are the only
# writers.
#
# ⚠ **WHY EACH WRITE IS ITS OWN SAVEPOINT — CLAUDE.md hard-won law 14.**
# Writing a break is the second half of handling a failed account, and the loop
# below CONTINUES afterwards. On PostgreSQL, once any statement errors inside a
# transaction the transaction is ABORTED: every later query raises
# `InFailedSqlTransaction` and the work is thrown away at COMMIT. So a break
# write that hits a constraint would not lose one break — it would lose every
# draft and every break after it. A nested `transaction.atomic()` is a SAVEPOINT
# and it is what makes the `except` below survivable; it is not the tidy option.
#
# ⚠ **AND HERE IS THE HONEST HALF, MEASURED RATHER THAN ASSUMED: TODAY THIS
# SAVEPOINT IS REDUNDANT, AND THAT IS EXACTLY WHY IT MUST STAY.** Removing it
# and re-running the PostgreSQL cases was tried, expecting red, **and they
# passed** — because `QuerySet.update_or_create` opens
# `transaction.atomic(using=self.db)` ITSELF (django/db/models/query.py, and
# `get_or_create` does the same around its create). So the protection below is
# currently Django's, not ours.
#
# **The moment the call shape changes, it is ours and only ours.** A lane that
# swaps `update_or_create` for a plain `create()`, adds a second statement
# inside this block, or reaches for `bulk_create` loses Django's wrapper
# silently — no test moves, no gate fires, and the loss shows up the first time
# a real row is refused in production. The claim in this comment is therefore
# *"this is defence in depth and the depth is one"*, never *"this is the line
# that saved us"* — and a check whose output cannot distinguish pass from fail
# is worse than no check, because it is trusted.
#
# **WHAT THE POSTGRESQL CASES DO PROVE**, and it is the property that matters:
# a break write REFUSED by the database costs one break and the pass survives
# it — `tests/test_cr051_run_jobs_and_breaks.py::tc12`, run under
# `DJANGO_SETTINGS_MODULE=config.settings.local`, because
# `config/settings/test.py` hardcodes in-memory SQLite and SQLite has no
# aborted-transaction state to observe.
# ══════════════════════════════════════════════════════════════════════════
def record_break(bill_run: Any, item: "Break", *, job_id: Any = None) -> Any:
    """Write (or refresh) THE break row for one account of one run.

    Returns the row, or None when the write itself failed — which never stops
    the run (BR-BIL-055: a break never blocks the run, and a break we could not
    FILE is not a reason to lose the 1,122 drafts either side of it).

    **IDEMPOTENT ON (run, account)** — `uq_bill_run_breaks_once`. A calculate
    that runs twice, a re-delivered Celery task and two clerks pressing the
    button at once all converge on ONE row; a second pass that broke at a
    different stage UPDATES the stage and the reason rather than appending a
    contradiction. That is hard rule 6 living in the write, which is the only
    place it cannot rot.

    ⚠ **WHAT THE SAVEPOINT COVERS, AND THE ONE THING IT CANNOT — MEASURED ON
    REAL POSTGRESQL, NOT REASONED ABOUT.** It catches every refusal that lands
    ON THE STATEMENT: NOT NULL, CHECK, UNIQUE, and an RLS `WITH CHECK`. It does
    NOT catch a FOREIGN KEY violation, because **Django declares every foreign
    key `DEFERRABLE INITIALLY DEFERRED` on PostgreSQL** — so a break naming an
    account that no longer exists inserts happily, this function returns a ROW,
    and the whole transaction fails at COMMIT with nothing here able to have
    seen it. A savepoint cannot roll back what has not happened yet.

    That is stated rather than papered over because the difference decides what
    a caller can rely on: an account deleted mid-run would take the pass down at
    the end. It has never been observed and there is no path in this product
    that deletes an account under a running calculate (`on_delete=PROTECT` on
    every reference), so no guard is built for a case nothing can produce — but
    a lane that later adds one must set the constraint `IMMEDIATE` or check the
    account first, not assume this `except` covers it.
    """
    tenant_id = core_tenancy.current_tenant_id()
    try:
        # SAVEPOINT — see the block above. Not tidiness; hard-won law 14.
        with transaction.atomic():
            row, _created = models.BillRunBreak.objects.update_or_create(
                tenant_id=tenant_id,
                bill_run=bill_run,
                account_id=item.account_id,
                defaults={
                    "account_no": item.account_no,
                    "stage": item.stage,
                    "reason": item.reason,
                    "detail": item.detail or None,
                    "retryable": item.retryable,
                    # A break raised again by a later pass is OUTSTANDING again.
                    "resolution": None,
                    "job_id": job_id,
                },
            )
        return row
    except (IntegrityError, DatabaseError) as problem:
        # The account itself is still reported in `CalculatedRun.breaks`, so the
        # caller of this pass loses nothing; what is lost is the DURABLE row, and
        # that is worth a log line naming the account rather than a silence.
        logger.warning(
            "BR-BIL-053: could not file the break row for account %s on run %s (%s: %s). "
            "The break is still in this pass's response; it will not survive a refresh.",
            item.account_no,
            getattr(bill_run, "pk", bill_run),
            type(problem).__name__,
            problem,
        )
        return None


def clear_break(
    bill_run: Any,
    account_id: Any,
    *,
    resolution: str = models.BREAK_RESOLUTION_DRAFTED,
) -> int:
    """Close this account's outstanding break — it left the clerk's work list.

    BR-BIL-053's own last clause is *"the run cannot enter phase 4 with an
    unresolved break row"*, so a break that has stopped being true must stop
    being outstanding or the gate would refuse a run that is ready. A clerk who
    fixed a missing read and re-calculated sees the row leave the list.

    It marks rather than deletes: *"we broke here and then it was fixed"* and
    *"this never broke"* are different mornings, and only the first explains why
    a run took two passes. Returns how many rows moved (0 or 1).

    ⚠ **`resolution` NAMES WHICH OF BR-BIL-053's TWO DOORS THE ACCOUNT LEFT BY,
    AND UNTIL 2026-08-31 THERE WAS ONLY ONE VALUE (CR-051 task 6).** `drafted`
    is *"allow user to retry immediately by fixing the issue"* — the account is
    billed on this run after all. `held` is the other door: the account waits
    for the catch-up sub-run and this run will not bill it. **Both close the
    row and they are not the same fact**: a supervisor reading `?f.resolved=all`
    afterwards is asking which accounts this run struggled with and what became
    of each, and one value for two outcomes cannot answer it.

    It is a DEFAULT rather than a required argument because `_calculate_run`'s
    call is the overwhelming majority and naming `drafted` there would be noise
    at the site where it is most obvious. Every other caller states its door.

    ⚠ **NOT AN IMMUTABILITY VIOLATION.** Hard rule 4 covers issued invoices,
    invoice lines, payments and journal entries. A break is a work item about a
    bill that does not exist; `bill_run_exclusions.resolved_at` is the precedent
    and this follows it rather than minting a second convention.
    """
    if resolution not in models.BREAK_RESOLUTIONS:
        # A typo here would write a resolution nothing can read back, and the
        # column takes any string (no CHECK — `resolution` is a TextField).
        # Refusing beats storing an unreadable state into a work list.
        raise BillingRuleError(
            f"{resolution!r} is not a break resolution (BR-BIL-053). The rule gives a "
            f"break two ways out and this table records exactly those: "
            f"{list(models.BREAK_RESOLUTIONS)}.",
            br_ref="BR-BIL-053",
        )
    try:
        # SAVEPOINT for the same reason `record_break` has one — hard-won law 14.
        with transaction.atomic():
            return models.BillRunBreak.objects.filter(
                tenant_id=core_tenancy.current_tenant_id(),
                bill_run=bill_run,
                account_id=account_id,
                resolution__isnull=True,
            ).update(resolution=resolution)
    except DatabaseError as problem:
        logger.warning(
            "BR-BIL-053: could not close the break row for account %s on run %s (%s: %s)",
            account_id,
            getattr(bill_run, "pk", bill_run),
            type(problem).__name__,
            problem,
        )
        return 0


# ══════════════════════════════════════════════════════════════════════════
# `DEF-BIL-5271`(b) · THE BR-BIL-053 GATE LEARNS A SECOND QUESTION
#
# BR-BIL-053's last clause is *"the run cannot enter phase 4 with an unresolved
# break row"*, and until today that was the whole gate: `_break_counts`
# produces `outstanding` and nothing else was asked. **A DECISION IS NOT A
# BREAK.** A clerk who bulk-decides 44 estimated accounts under one
# `bulk_action_id` resolves nothing and breaks nothing — there was never a
# break row for those accounts — so the gate's number stays 0 and 44 drafts
# keep the figure they had BEFORE the decision was taken. The clerk then signs
# off on money their own decision was supposed to move.
#
# ⚠ **THIS IS THE HALF THAT MAKES THE SCOPED RE-PRICE REAL.** A re-price that
# nothing checks for is a button, and a button is optional. With this clause a
# run whose drafts predate their decisions cannot be authorised at all, so the
# re-price is not a courtesy the clerk may forget — it is the only way past the
# gate.
#
# **THE COMPARISON IS TWO STORED TIMESTAMPS AND NEVER A CLOCK** (BR-TEN-043,
# and gate `G6` bans `timezone.now()` on a money path): `invoices.created_at`
# against `bill_run_decisions.created_at`. A re-run DELETES this run's draft
# for the account and writes a new row (BR-BIL-023, `stages/assemble_document`
# — *"the re-run still clears its own draft first"*), so `created_at` really is
# *when this draft was computed* and not when the account was first drafted.
#
# ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY, asked before trusting it (law 7):**
#   * **A decision on an account with no draft.** Held, excluded and silent
#     accounts all have decisions and no `invoices` row. There is no stale
#     money there, so they are OUT by construction — the query starts from the
#     DRAFTS, never from the decisions.
#   * **A decision recorded before the calculate pass.** Ordinary and correct:
#     the draft is newer, so it is not stale. The comparison is directional and
#     stays directional.
#   * **A superseded decision.** Its replacement is newer than it is, so the
#     MAX per account is always the live row's — reading every row rather than
#     only the current ones cannot move the answer, and it cannot be fooled by
#     a supersession chain either.
# ══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class StaleDraft:
    """One account whose draft is older than a decision taken about it."""

    account_id: str
    #: `invoices.created_at` — when this draft was computed.
    drafted_at: Any
    #: `bill_run_decisions.created_at` of the NEWEST decision on this account.
    decided_at: Any


def stale_drafts(bill_run: Any) -> tuple[StaleDraft, ...]:
    """Drafts on this run that predate a decision recorded against their account.

    TWO GROUPED QUERIES, never one per account: the same posture
    `selectors._break_counts` takes, and for the same reason — this is asked on
    the gate of a run that may hold 40,000 accounts (T5, the top of the ICP),
    and `NFR-5` forbids a shape that only works below some count.

    Only DRAFTS are considered. An ISSUED bill is money that has left the
    building and BR-BIL-004 makes its correction a new row, never a re-price;
    including one here would refuse a run for a state no re-price can clear.
    """
    tenant_id = core_tenancy.current_tenant_id()
    drafted = {
        str(row["account_id"]): row["drafted_at"]
        for row in models.Invoice.objects.filter(
            tenant_id=tenant_id, bill_run=bill_run, status=models.INVOICE_DRAFT
        )
        .values("account_id")
        .annotate(drafted_at=Max("created_at"))
        .order_by()
    }
    if not drafted:
        return ()
    decided = {
        str(row["account_id"]): row["decided_at"]
        for row in models.BillRunDecision.objects.filter(
            tenant_id=tenant_id, bill_run=bill_run, account_id__in=list(drafted)
        )
        .values("account_id")
        .annotate(decided_at=Max("created_at"))
        .order_by()
    }
    stale = [
        StaleDraft(account_id=account_id, drafted_at=drafted_at, decided_at=decided[account_id])
        for account_id, drafted_at in drafted.items()
        if account_id in decided and decided[account_id] > drafted_at
    ]
    stale.sort(key=lambda item: item.account_id)
    return tuple(stale)


def late_fee_drafts_paid_since(bill_run: Any) -> tuple[str, ...]:
    """🔒 HUMAN-REVIEW-PENDING · `DEF-BIL-10708` (tester L2-06, 2026-10-30) —
    the accounts whose DRAFT on this run carries a late fee and whose payments
    moved AFTER that draft was worked out.

    **THE CASE.** Xander Xanthos paid **$226.00** at Hy-Vee on **21 Oct**, a day
    before his due date. The store file was loaded after the run had drafted
    his bill, which carried a **$5.00** late fee worked out when no payment was
    on file. BR-BIL-071 judges lateness by WHEN THE MONEY ARRIVED, so that fee
    is no longer owed — but `stale_drafts` asks only whether a CLERK DECIDED
    something after the draft, and a payment is not a decision. Release would
    have issued the $5.00, and a hard-rule-4 bill cannot be taken back.

    **THE ANSWER IS A REFUSAL, NOT A SILENT RE-PRICE** (decision log
    2026-10-30, lane PAY-F): the release gate is the moment a person signs for
    the figures, and changing them inside the signature would sign for numbers
    nobody was shown. `reprice_accounts` (or the step's own *work out the
    bills* again) clears it, and the re-worked draft is newer than the payment.

    **ONLY A LATE-FEE DRAFT.** A payment after drafting does not change any
    other line of a cycle bill (the usage, base and taxes are not payment
    facts), so refusing every draft with a payment since would stop a run for
    nothing. A late-fee line is a `fee` line booked to the late-fee code the
    account's plan names (`decisions._late_fee_charge_id_for_plan`, the code
    the draft itself was given). Where the run saved no plan for the account,
    ANY charged `fee` line counts — that fails closed: a refusal costs a
    re-price, a missed one costs a customer a fee they did not owe.

    Three grouped reads plus one seam call, whatever the run's size (NFR-5):
    the drafted fee lines, the saved Check plans, and payments'
    `accounts_changed_since` asked once from the OLDEST draft.
    """
    from apps.billing import check_models, check_staleness, decisions

    tenant_id = core_tenancy.current_tenant_id()
    drafted: dict[str, Any] = {}
    fee_charges: dict[str, set[str]] = {}
    for account_id, charge_id, created_at in models.InvoiceLine.objects.filter(
        tenant_id=tenant_id,
        invoice__bill_run=bill_run,
        invoice__status=models.INVOICE_DRAFT,
        kind="fee",
        charge_id__isnull=False,
    ).values_list("invoice__account_id", "charge_id", "invoice__created_at"):
        key = str(account_id)
        fee_charges.setdefault(key, set()).add(str(charge_id))
        if key not in drafted or created_at > drafted[key]:
            drafted[key] = created_at
    if not drafted:
        return ()
    since = min(drafted.values())
    paid = check_staleness._ask(
        "payments", "accounts_changed_since", list(drafted), since, "bill_run_checks"
    )
    moved = [
        account_id
        for account_id, drafted_at in drafted.items()
        if paid.get(account_id) is not None and paid[account_id] > drafted_at
    ]
    if not moved:
        return ()
    plans = {
        str(account_id): plan_id
        for account_id, plan_id in check_models.BillRunAccountCheck.objects.filter(
            tenant_id=tenant_id, bill_run=bill_run, account_id__in=moved
        ).values_list("account_id", "plan_id")
    }
    late_code_by_plan: dict[str, str | None] = {}
    hit: list[str] = []
    for account_id in moved:
        plan_id = plans.get(account_id)
        if plan_id is None:
            hit.append(account_id)
            continue
        plan_key = str(plan_id)
        if plan_key not in late_code_by_plan:
            late_code_by_plan[plan_key] = decisions._late_fee_charge_id_for_plan(plan_key)
        code = late_code_by_plan[plan_key]
        if code is not None and code in fee_charges[account_id]:
            hit.append(account_id)
    hit.sort()
    return tuple(hit)


def refuse_stale_drafts(bill_run: Any) -> None:
    """BR-BIL-053's last clause, extended — raise rather than let a run through.

    Named and separate from `stale_drafts` so a READ (a panel, a count, a
    progress band) can ask the question without a refusal, and so the one place
    that refuses is greppable. `release.authorise_release` calls it; nothing
    else may enter phase 4.

    ⚠ **TWO QUESTIONS SINCE 2026-10-30 (`DEF-BIL-10708`)**: a draft older than a
    decision about its account, AND a draft carrying a late fee older than a
    payment on its account (`late_fee_drafts_paid_since`). Both are cleared the
    same way — re-price those accounts.
    """
    stale = stale_drafts(bill_run)
    if stale:
        raise BillingRuleError(
            f"release refused: {len(stale)} draft(s) on this run were calculated before a "
            "decision was recorded against their account, so they still carry the figure "
            "they had before anyone decided anything (BR-BIL-053). Re-price those accounts "
            "and try again. A decision that never reached a bill is a decision nobody took.",
            br_ref="BR-BIL-053",
        )
    paid = late_fee_drafts_paid_since(bill_run)
    if paid:
        raise BillingRuleError(
            f"release refused: re-check {len(paid)} account(s). A payment arrived after "
            "their bills were worked out, and those bills carry a late fee that may no "
            "longer be owed (BR-BIL-071 — lateness is judged by when the money arrived). "
            "Work those bills out again and try again.",
            br_ref="BR-BIL-071",
            # DEF-BIL-10773 — the count reaches the screen through its own key;
            # the generic `billing.run.refused` told the clerk to check the
            # cycle and dates, which were never the problem.
            message_key="billing.run.recheckLateFees",
            params={"count": len(paid)},
        )


def refuse_unresolvable_template(bill_run: Any) -> None:
    """`DEF-BIL-5302` — a run may not be signed off pinned to a template that
    can no longer be printed.

    🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING with the rest of this module's
    money-path checks — it decides whether a batch of immutable bills may start
    (hard rule 4, BR-BIL-026). Its row is in
    `12-governance/09-human-review-ledger.md`.

    ── WHAT THIS IS FOR, AND WHY IT IS NOT `template_problems` ───────────────
    `issue.IssuedRun.template_problems` already counts *"distinct reasons a bill
    could not resolve its own template, with the number of bills each
    affected"*. That is a REPORT and it is computed INSIDE the issue loop — so
    the fault is discovered after the batch has started, after Scope, after
    Check, after a clerk has signed. It is the right carrier for a per-account
    chain that fails on one bill and the wrong one for a RUN whose single pinned
    layout has gone: that is knowable before anything issues, and the whole
    point of deciding the template at Scope is that it is decided EARLY.

    PO ruling 2026-09-14, verbatim: *"in this step 1 scope - you will ahve to
    also decide on billing template"*. `validated_template_pin` checks the same
    two facts when the run is CREATED. **This is the re-check at sign-off**,
    because a template can be retired or unpublished in between — the gap
    between Scope and Send is exactly where a tenant edits their templates.

    ── THE TWO WAYS IT FAILS, and they are the two `validated_template_pin`
    names ─────────────────────────────────────────────────────────────────
      * the template is **gone** for this tenant — deleted, or never theirs;
      * the template has **no PUBLISHED version** — BR-BIL-026: a draft is
        test-printable and never pinned, because a bill pinned to a draft could
        be edited after the customer received it.

    ⚠ **A RUN THAT PINNED NOTHING IS NOT A FAULT AND MUST NOT BE REFUSED.**
    `bill_runs.template_id` is nullable and null is the ordinary case: nobody
    chose one at Scope, and BR-BIL-025's per-account chain runs exactly as it
    always has, with `template_problems` reporting whatever it finds. Refusing
    here would block every run in the product.

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY, asked before trusting it (law 7):**
    the pin is read as a DIRECT attribute and not through `getattr(..., None)`,
    because a defaulted read of a renamed or dropped column answers *nothing
    pinned* for every run in the product and this check would then be a no-op
    that no test could see. A missing column raises here instead, loudly.

    NO `message_key` IS INVENTED. `api._as_catalog_refusal` gives an unnamed
    `BillingRuleError` the catalogue's own `billing.run.refused`, which exists
    and resolves in all eleven languages; a key raised with no catalogue entry
    reaches a clerk as SILENCE (`G18`/`G32`, and two were shipped this week).
    """
    template_id = bill_run.template_id
    if template_id is None:
        return
    # Imported at CALL time: `templates_service` imports `template_models`,
    # which imports this module's `models` — the same closed loop
    # `validated_template_pin` names at its own import.
    from apps.billing import templates_service
    from apps.billing.template_models import BillTemplate

    template = BillTemplate.objects.filter(
        tenant_id=core_tenancy.current_tenant_id(), pk=template_id
    ).first()
    if template is None:
        raise BillingRuleError(
            "release refused: the bill template chosen when this run was scoped no longer "
            "exists, so there is no layout to print these bills on (BR-BIL-026). Choose a "
            "template and scope the run again. Nothing is resolved in its place: sending a "
            "run on a layout nobody picked is the decision at Scope not having happened.",
            br_ref="BR-BIL-026",
        )
    if templates_service.published_version(template) is None:
        raise BillingRuleError(
            f"release refused: the bill template chosen when this run was scoped "
            f"({template.name!r}) has no published version now, so it cannot be pinned "
            "(BR-BIL-026). A draft is test-printable and never pinned — a bill pinned to "
            "a draft could be edited after the customer received it. Publish that "
            "template, or scope the run to one that is published.",
            br_ref="BR-BIL-026",
        )


# ── 🔒 DEF-RAT-9367 · ONE BUDGET, SHARED ACROSS THE ACCOUNTS OF ONE RUN ────
#
# A programme's budget is a SUM over `discount_grants`, and a grant is written
# at ISSUE (`DEF-2430`) — after the whole run is priced. Every account was
# therefore priced against the SAME remaining budget: $5.00 left and two $10.00
# accounts gave $5.00 to BOTH, $50.00 against a $45.00 budget. So the run keeps
# its own tally of what it has already DRAFTED under each programme and prices
# each account on what is left after the accounts before it — the crossing
# account takes what is left and the ones after it take $0.00, and the bill
# still goes out (PO 2026-10-04, *"we cannot stop the billing"*). The tally is
# seeded from the run's own existing drafts, so a scoped re-price or a resumed
# pass counts the accounts it is not walking. A per-ACCOUNT cap needs none of
# this: one account has one bill in a run.


def run_discount_spend(bill_run: Any) -> dict[str, dict[str, Decimal]]:
    """What this run's DRAFT bills already give, per ACCOUNT and programme code.

    Per account so that re-pricing an account never counts its OWN earlier
    draft (which the re-price replaces) against the budget it is priced on."""
    spend: dict[str, dict[str, Decimal]] = {}
    if bill_run is None:
        return spend
    rows = models.InvoiceLine.objects.filter(
        tenant_id=core_tenancy.current_tenant_id(),
        invoice__bill_run=bill_run,
        invoice__status=models.INVOICE_DRAFT,
        kind="discount",
        discount_code__isnull=False,
    ).values_list("invoice__account_id", "discount_code", "amount")
    for account_id, code, amount in rows:
        mine = spend.setdefault(str(account_id), {})
        mine[code] = mine.get(code, Decimal("0")) - Decimal(amount)
    return spend


def _spend_by_others(spend: dict[str, dict[str, Decimal]], account_id: Any) -> dict[str, Decimal]:
    total: dict[str, Decimal] = {}
    for other, codes in spend.items():
        if other == str(account_id):
            continue
        for code, amount in codes.items():
            total[code] = total.get(code, Decimal("0")) + amount
    return total


def discounts_net_of_run_spend(
    discounts: tuple[Any, ...], spend: dict[str, Decimal]
) -> tuple[Any, ...]:
    """Each rule's `budget_remaining` less what this run has already drafted
    under its programme. A rule with no budget is untouched. No rounding: the
    budget and the drafted lines are both figures already finalized."""
    return tuple(
        (
            replace(rule, budget_remaining=Decimal(rule.budget_remaining) - spend[rule.code])
            if rule.budget_remaining is not None and spend.get(rule.code)
            else rule
        )
        for rule in discounts
    )


def _add_run_spend(spend: dict[str, dict[str, Decimal]], invoice: Any) -> None:
    mine: dict[str, Decimal] = {}
    for code, amount in models.InvoiceLine.objects.filter(
        tenant_id=core_tenancy.current_tenant_id(),
        invoice=invoice,
        kind="discount",
        discount_code__isnull=False,
    ).values_list("discount_code", "amount"):
        mine[code] = mine.get(code, Decimal("0")) - Decimal(amount)
    spend[str(invoice.account_id)] = mine


def calculate_run(
    prepared: PreparedRun,
    *,
    bill_run: Any,
    bill_type: str = "cycle",
    on_progress: Callable[[int, int, str], None] | None = None,
    job_id: Any = None,
    already_done: int = 0,
    only_accounts: frozenset[str] | None = None,
) -> CalculatedRun:
    """Phase 2 over the WHOLE run: draft every ready account, collect the breaks.

    ⚠ **`only_accounts` NARROWS IT TO A NAMED SET — `DEF-BIL-5271`(a), THE
    SCOPED RE-PRICE.** `None` is every ready account and is what every caller
    but one passes. A set re-prices exactly those accounts and touches no
    other draft, which is what makes a decision taken on 44 accounts cost 44
    accounts of work instead of the whole run.

    **THE BLUEPRINT MARKS IT NEW ON p052 ITEM 7 AND STATES WHY IT IS SAFE:**
    *"a scoped re-run of calculate, which replaces that account's draft rather
    than adding one — and it is safe because the engine already guarantees
    it"*. That guarantee is not new and is not this parameter's: stages 1–5 are
    pure (BR-BIL-039) and stage 6 REPLACES this run's draft for the account
    rather than adding a second (BR-BIL-023), which is the same property that
    already makes a killed worker resumable. All this argument does is stop the
    loop walking accounts whose answer cannot have changed.

    The PO's second clause — *"then run the billing in batch process in the
    background"* — as a loop with one property that matters more than the loop:
    **one account's failure never touches another's draft.**

    EACH ACCOUNT IS ITS OWN TRANSACTION. Not the run. A run of 1,124 that fell
    over on number 400 and rolled back would throw away 399 correct drafts and
    a morning's work, and BR-BIL-052 forbids exactly that — a killed batch
    resumes, "already-drafted accounts are not recomputed and never
    duplicated". A draft is not money (BR-BIL-004), so there is nothing to
    protect by grouping them.

    RESUMABLE BY CONSTRUCTION, not by a checkpoint. Stage 6 already REPLACES an
    account's draft for this run rather than adding a second (BR-BIL-023), and
    stages 1–5 are pure, so re-running the whole thing is safe and converges on
    the same drafts. Nothing tracks progress because nothing needs to: the
    idempotency is in the write, which is the only place it cannot rot.

    ⚠ **AND "SAFE" IS NOT "FREE" — CR-051 TASK 21 PRICED THE RE-WALK.** The
    paragraph above is still true and is still the guarantee; what it does not
    say is what a re-walk COSTS. Measured on real PostgreSQL: **137 ms per
    account**, of which the prepare pass is 88%, so a worker killed at account
    9,000 of 10,000 pays **22 minutes** again to redo work it had finished.
    CR-051 task 11 is the checkpoint that stops that, and it lives one layer
    out — `prepare_run(resume_skip=…)` does not hand this loop the accounts an
    earlier attempt of the same job already finished. `already_done` below is
    the only thing that reaches this function, and it moves no draft.

    ⚠ **THIS DOCSTRING SAID "IT RUNS INLINE. THERE IS NO JOB RUNNER IN THIS
    PROJECT" AND THAT HAS BEEN FALSE SINCE 2026-08-19 — corrected here rather
    than left standing (hard-won law 1).** The paragraph read: *"`celery` is a
    declared dependency with zero `tasks.py` and `JOBS_EAGER=true` (TD-17,
    open) — so 'in the background' is not yet true and this function does not
    pretend it is."* Every clause of it has expired. CR-017 landed the worker:
    `apps.tenancy` registers the job store and the Celery transport, a `celery`
    service runs in `docker-compose.yml`, `JOBS_EAGER=False` in production, and
    seven job kinds were already registered across four modules before billing
    registered its first. **`apps/billing/run_jobs.py` is billing's, and
    `run_calculate_job` calls THIS function** — so BR-BIL-051's background half
    is now true when the caller asks for it (CR-051 tasks 4 and 8).

    WHAT IS STILL TRUE, and it is the reason the signature grew rather than the
    body changing: this function is the WORK, not the transport. It is the same
    code inline and in a worker, which is what makes the worker safe to trust.

    `on_progress(done, total, account_no)` is called after EVERY account, worked
    or broken, so NFR-4's gauge counts the same denominator the screen shows —
    *"412 of 1,124"* is only honest if the 1,124 counts the ones that will
    break. It is optional and defaults to nothing: an inline caller answers
    before anyone could poll it, and a gauge nobody reads is a write for
    nothing. `job_id` is stamped on the break rows this pass files, so a clerk
    looking at a break can be told which pass raised it.

    **BREAKS ARE NOW WRITTEN, NOT ONLY RETURNED (CR-051 tasks 5/6).** Each break
    becomes a `bill_run_breaks` row as it happens rather than after the loop, so
    a killed worker keeps every break it had already found exactly as it keeps
    every draft. An account that drafts on a LATER pass has its outstanding
    break closed in the same step — BR-BIL-053's *"the run cannot enter phase 4
    with an unresolved break row"* would otherwise refuse a run a clerk had
    already fixed.
    """
    # ── CR-051 TASK 22 · ONE PASS, ONE CACHE — AND WHY THE WRITE HALF HAS ONE ─
    # The prepare pass opens one of these too. This half needs it for exactly
    # ONE read: stage 6 asks tenancy for the platform service catalogue once
    # per account to stamp `invoice_lines.service_id`, measured at 979 calls
    # over 979 accounts for an answer that never changes. Billing writes
    # nothing to that catalogue, so one answer serves the run.
    #
    # ⚠ **IT DOES NOT CACHE THE MONEY.** `seam_batch.BATCHABLE` is a named
    # list, nothing on it is reached from the pricing engine, and every draft
    # this loop writes is still computed by `calculate_account` from scratch.
    with seam_batch.pass_cache():
        calculated = _calculate_run(
            prepared,
            bill_run=bill_run,
            bill_type=bill_type,
            on_progress=on_progress,
            job_id=job_id,
            already_done=already_done,
            only_accounts=only_accounts,
        )
    # 🔒 HUMAN-REVIEW-PENDING · DEF-BIL-8696 — Sign off's whole-run summary is
    # built and saved HERE, at the end of every pass (a re-price included), so
    # Sign off opens on it instead of building it in the clerk's request
    # (~10 s at 40,000 bills). Outside the pass cache, after every draft is
    # written; it never raises, and the first read rebuilds whatever it could
    # not save (`signoff.refresh_sign_off_snapshot`).
    if getattr(bill_run, "pk", None) is not None:
        from apps.billing import signoff

        signoff.refresh_sign_off_snapshot(bill_run)
    return calculated


def _calculate_run(
    prepared: PreparedRun,
    *,
    bill_run: Any,
    bill_type: str = "cycle",
    on_progress: Callable[[int, int, str], None] | None = None,
    job_id: Any = None,
    already_done: int = 0,
    only_accounts: frozenset[str] | None = None,
) -> CalculatedRun:
    """`calculate_run`'s loop, with the pass cache already open around it.

    Split out for the reason `_prepare_run` is: the cache is opened in one
    place and the loop's indentation did not move.
    """
    ready = prepared.ready
    if only_accounts is not None:
        # `DEF-BIL-5271`(a). Narrowed HERE and not by the caller filtering
        # `PreparedRun` itself, so the gauge's denominator below counts what
        # this pass will actually walk — *"412 of 44"* on a scoped re-price
        # would read to an operator as the run having restarted.
        ready = tuple(data for data in ready if str(data.account_id) in only_accounts)
    drafted: list[str] = []
    breaks: list[Break] = []
    silent: list[AccountProblem] = []
    # CR-051 task 11 — `already_done` is what an EARLIER attempt of this same
    # job finished and `prepare_run` therefore did not hand back. It is 0 on
    # every other call. It exists only so NFR-4's gauge stays honest across a
    # resume: without it a worker killed at 9,000 of 10,000 comes back and
    # reports *"0 of 1,000"*, which reads to an operator as the work having
    # started over — the exact thing the checkpoint exists to stop being true.
    total = already_done + len(ready)
    done = already_done

    def _progress(account_no: str) -> None:
        """NFR-4's gauge. A reporter that raises must never kill the run: the
        drafts are the work and the gauge is a courtesy (BR-BIL-055's spirit —
        nothing peripheral takes the batch down)."""
        if on_progress is None:
            return
        try:
            on_progress(done, total, account_no)
        except Exception as broken:  # noqa: BLE001 — see the docstring
            # CR-051 task 30 — ONE EXCEPTION IS NOT A COURTESY AND MUST NOT BE
            # SWALLOWED. Celery's soft time limit raises `SoftTimeLimitExceeded`
            # (an ordinary `Exception`) EXACTLY ONCE, wherever the task happens
            # to be — and a per-account gauge write is somewhere it plausibly
            # is. Caught here it would be logged as *"progress reporting
            # failed"*, the run would carry on unbounded, and the hard limit
            # would kill the worker mid-write with nothing recorded. One line,
            # and it is the difference between the limit working and the limit
            # being decoration.
            core_jobs.reraise_if_time_limit(broken)
            logger.warning("progress reporting failed on run %s", getattr(bill_run, "pk", None))

    # 🔒 DEF-RAT-9367 — the run's own tally of what it has drafted per programme.
    run_spend = run_discount_spend(bill_run)
    for data in ready:
        if run_spend and getattr(data, "discounts", ()):
            data = replace(
                data,
                discounts=discounts_net_of_run_spend(
                    data.discounts, _spend_by_others(run_spend, data.account_id)
                ),
            )
        try:
            # One account, one transaction. `atomic` per iteration is the whole
            # guarantee: account 400 failing rolls back account 400 and nothing
            # else, and the 399 before it are already committed.
            with transaction.atomic():
                invoice = calculate_account(
                    data,
                    bill_run=bill_run,
                    service_date=prepared.service_date,
                    bill_type=bill_type,
                )
            # ── `BR-BIL-1024` · NO LINES, NO DOCUMENT ────────────────────────
            # `None` is stage 6 reporting that this account priced no lines, so
            # no `invoices` row was created. It is neither a draft nor a break:
            # the run did its whole job and the correct outcome was nothing (PO
            # 2026-08-31). The break row is cleared exactly as it is on the
            # drafting path — a break filed by an earlier pass is no longer
            # true, and leaving it would put the account on the exceptions
            # screen for a state that is not a fault (`BR-BIL-1025`).
            if invoice is None:
                clear_break(bill_run, data.account_id)
                silent.append(
                    AccountProblem(
                        reason=RUN_NOTHING_TO_BILL,
                        detail=(
                            f"account {data.account_no} priced no lines for this period, "
                            "so no document was produced (BR-BIL-1024). Nothing is wrong "
                            "with the account: there was nothing to charge it for."
                        ),
                        account_id=str(data.account_id),
                        account_no=data.account_no,
                    )
                )
                done += 1
                _progress(data.account_no)
                continue
            drafted.append(str(invoice.pk))
            if getattr(data, "discounts", ()):
                _add_run_spend(run_spend, invoice)
            # This account drafted. If a PREVIOUS pass filed a break for it, it
            # is no longer true — see `clear_break` and BR-BIL-053's last clause.
            clear_break(bill_run, data.account_id)
            done += 1
            _progress(data.account_no)
            continue
        except rating_seam.PricingRefused as problem:
            # Caught BEFORE BillingRuleError (its base class) so the break can
            # name the stage that actually failed. DEF-047: rating raises its
            # own hierarchy, nothing translated it, and until the seam did an
            # account rating would not price killed the entire run.
            breaks.append(
                Break(
                    account_id=data.account_id,
                    account_no=data.account_no,
                    stage="price-usage",
                    reason=PRICING_REFUSED,
                    detail=str(problem),
                    # Not fixable from the phase-3 screen: a UoM mismatch, an
                    # unpriceable tariff version or a plan that resolves to
                    # nothing all need a change in Plans & Rates. "Retry now"
                    # here would be a button that always fails.
                    retryable=False,
                )
            )
        except gather.GatherProblem as problem:
            breaks.append(
                Break(
                    account_id=data.account_id,
                    account_no=data.account_no,
                    stage=STAGE_BY_REASON.get(problem.reason, "unknown"),
                    reason=problem.reason,
                    detail=str(problem),
                    retryable=problem.reason not in NOT_RETRYABLE_HERE,
                )
            )
        except BillingRuleError as problem:
            # A rule refused this account — a currency mismatch, an unknown
            # behaviour class, a line kind the seam does not publish. Caught
            # with the same shape rather than escaping, because a rule refusal
            # IS a break: the clerk needs to see it on the phase-3 list, not
            # find the run dead.
            breaks.append(
                Break(
                    account_id=data.account_id,
                    account_no=data.account_no,
                    stage="assemble-document",
                    reason="rule_refused",
                    detail=str(problem),
                    retryable=False,
                )
            )
        # ⚠ ONE EXIT FOR EVERY BREAK, and it is deliberately outside the three
        # `except` blocks rather than repeated inside each: a fourth failure
        # shape added above must not be able to reach the end of the loop
        # without its row being filed, and a `finally` here would also fire on
        # the success path that has already `continue`d.
        breaks_written = record_break(bill_run, breaks[-1], job_id=job_id)
        if breaks_written is None:
            logger.warning(
                "run %s: account %s broke and its row could not be filed",
                getattr(bill_run, "pk", None),
                breaks[-1].account_no,
            )
        done += 1
        _progress(data.account_no)

    return CalculatedRun(
        bill_run_id=str(getattr(bill_run, "pk", "")),
        drafted=tuple(drafted),
        breaks=tuple(breaks),
        # `BR-BIL-1025` — the accounts that legitimately produced nothing,
        # carried out beside the drafts rather than dropped, so the screen can
        # say WHO was quiet. `prepare_run`'s own silent list is the OTHER half
        # (an account that could not even be gathered); both use one reason
        # code and one shape, because two vocabularies for one fact is how a
        # run starts disagreeing with itself about who was billed.
        silent=tuple(silent),
    )


def has_drafts_for(bill_run: Any, account_ids: Any) -> bool:
    """Does this run already hold a DRAFT for any of these accounts?

    The question `api.run_exception_resolve` asks before re-pricing, and it is
    a question about ORDER rather than about size: a decision taken on step 3
    before step 4 has nothing to replace, and re-pricing there would draft
    bills nobody has asked for yet — turning *looking* into *committing*,
    which is the one thing the PO's whole phase-1/phase-2 split exists to stop.

    Drafts only, for `stale_drafts`' reason: an issued bill is never re-priced
    (BR-BIL-004), so its presence is not a reason to run one.
    """
    ids = [str(account_id) for account_id in account_ids if account_id]
    if not ids:
        return False
    return models.Invoice.objects.filter(
        tenant_id=core_tenancy.current_tenant_id(),
        bill_run=bill_run,
        status=models.INVOICE_DRAFT,
        account_id__in=ids,
    ).exists()


def reprice_accounts(
    *,
    bill_run: Any,
    account_ids: Any,
    bill_type: str = "cycle",
    on_progress: Callable[[int, int, str], None] | None = None,
    job_id: Any = None,
) -> CalculatedRun:
    """`DEF-BIL-5271`(a) — re-run phases 1 and 2 for a NAMED SET of accounts.

    **THE DEFECT IN ONE SENTENCE: a decision recorded a choice and never
    re-priced anything.** `decisions.resolve_cases` writes rows; the one-account
    retry endpoint says in its own words that it *is not a re-price*; so a
    clerk could bulk-decide 44 estimated accounts and every one of their drafts
    kept its pre-decision figure, under a KPI strip whose drawn sub-line reads
    *"updates as you decide"*.

    **IT IS THE SAME WORK AS A WHOLE RUN, NARROWED — NOT A SECOND ENGINE.**
    `prepare_run` gathers, `decisions.apply_decisions` folds in the clerk's
    recorded answers, and `calculate_run` drafts. The only thing that differs
    from a full calculate is WHICH accounts are walked, which is exactly what
    the blueprint marks NEW on p052 item 7 and exactly what it says is safe:
    stages 1–5 are pure (BR-BIL-039) and stage 6 REPLACES this run's draft for
    the account rather than adding one (BR-BIL-023).

    ⚠ **THE NARROWING IS APPLIED TWICE AND BOTH ARE LOAD-BEARING.**
    `prepare_run`'s `resume_skip` predicate stops the GATHER for an account
    outside the set — that is where the 137 ms per account is spent (`CR-051`
    task 21), so a re-price of 44 accounts out of 40,000 costs 44 accounts of
    work rather than the run's. `calculate_run`'s `only_accounts` is the belt to
    that brace: `resume_skip` is a hint the prepare pass may legitimately
    ignore (it does not apply to a one-time or account-scoped run), and a
    re-price that quietly redrafted the other 39,956 accounts would be a whole
    run wearing a decision's name.

    ⚠ **A HELD ACCOUNT LEAVES BY ITSELF AND ITS DRAFT MUST GO WITH IT.**
    `apply_decisions` moves an account the clerk held out of `ready` and writes
    its `bill_run_exclusions` row, so this pass draws no new draft for it —
    and stage 6 never runs, so the draft that already exists is not replaced
    either. Discarding it is `BR-BIL-055`'s pending-queue half and belongs to
    `mark_for_later`, which `apply_decisions` already calls. REPORTED rather
    than reached into from here: a re-price deleting a bill is a different act
    from a re-price replacing one, and only one of them is what this function
    is named for.

    `on_progress` and `job_id` are the SAME channel a full calculate uses, so a
    scoped re-price is visible where a clerk is already looking rather than on
    a second gauge nobody watches.
    """
    from apps.billing import decisions as billing_decisions
    from apps.billing import selectors as billing_selectors

    scope = frozenset(str(account_id) for account_id in account_ids if account_id)
    if not scope:
        # A decision that touched nobody re-prices nobody. Answered rather than
        # refused: `resolve_cases` can legitimately record against an account
        # this run never drafted, and an empty set is not an error.
        return CalculatedRun(bill_run_id=str(getattr(bill_run, "pk", "")))
    prepared = billing_selectors.prepared_for(
        bill_run,
        # `resume_skip` answers True for an account this pass must NOT gather.
        # Its name is CR-051's checkpoint and its contract is exactly this
        # predicate, so reusing it beats a second narrowing argument that would
        # have to be threaded through the same three functions.
        resume_skip=lambda account_id, _account_no: str(account_id) not in scope,
    )
    prepared = billing_decisions.apply_decisions(prepared, bill_run=bill_run)
    return calculate_run(
        prepared,
        bill_run=bill_run,
        bill_type=bill_type,
        on_progress=on_progress,
        job_id=job_id,
        only_accounts=scope,
    )


def retry_account(
    prepared: PreparedRun,
    account_id: str,
    *,
    bill_run: Any,
    readings: tuple[ServiceReading, ...] | None = None,
    bill_type: str = "cycle",
) -> Any:
    """Phase 3's "fix and retry now" — re-run stages 1-6 for ONE account.

    BR-BIL-053 gives a broken account exactly two ways out, and this is the
    first: *"allow user to retry immediately by fixing the issue"*. It re-runs
    that account alone and, if it succeeds, the account joins the draft set —
    the other drafts are never touched.

    `readings` is how a fix reaches the pipeline. A clerk who entered the
    missing read supplies the corrected readings and the account re-runs on
    them; `gather.with_readings` swaps them onto the data already gathered
    rather than re-gathering, deliberately, so a customer name changed since
    the run does not silently reach a bill that was priced before it.

    Raises rather than returning a `Break`: this is one account, called from a
    button, and the caller wants the failure to hand back to the screen.

    ⚠ **A SUCCESSFUL RETRY CLOSES THE BREAK ROW, AND UNTIL 2026-08-31 IT DID
    NOT (CR-051 task 6).** This function IS BR-BIL-053's first way out —
    *"allow user to retry immediately by fixing the issue"* — so an account that
    drafts here has stopped being a break by the rule's own definition. The row
    is closed as `drafted`, the same value `_calculate_run` writes when a later
    whole-run pass drafts the account, because it is the same fact: the account
    is billed on this run. Leaving it open would put the clerk's own fix back on
    their work list and would hold the run out of phase 4 by BR-BIL-053's last
    clause.

    **The close is AFTER the draft commits, deliberately.** A retry that raises
    must leave the break exactly as it was — the account still cannot be billed
    and the clerk still has to see it.
    """
    for data in prepared.ready:
        if data.account_id != account_id:
            continue
        if readings is not None:
            data = gather.with_readings(data, readings)
        with transaction.atomic():
            invoice = calculate_account(
                data,
                bill_run=bill_run,
                service_date=prepared.service_date,
                bill_type=bill_type,
            )
        clear_break(bill_run, data.account_id)
        return invoice
    raise BillingRuleError(
        f"account {account_id} is not in this run's ready set, so there is "
        "nothing to retry. An account that was never prepared cannot be "
        "retried into the run — it belongs in a catch-up sub-run (BR-BIL-055)."
    )


def mark_for_later(
    *,
    bill_run: Any,
    account_id: str,
    reason_code: str,
    detail: str = "",
    excluded_by: Any = None,
) -> Any:
    """Phase 3's second way out — the account waits for a catch-up sub-run.

    BR-BIL-055: *"a partial run ISSUES the clean bills and HOLDS the rest"*.
    This writes the `bill_run_exclusions` row that IS the pending queue, and it
    is deliberately the SAME table a phase-1 hold writes to — the PO confirmed
    the product behaviour as one queue, and both doors leave through the same
    catch-up sub-run.

    `reason_code` records WHICH DOOR. "We never calculated this" and "we
    calculated it and it broke" are different facts about an account, and a
    queue that cannot tell them apart cannot tell a clerk whether to fix data
    or fix configuration.

    Idempotent on (run, account) — the table's own unique constraint — so a
    double-click marks once rather than raising at the user.

    ⚠ **IT ALSO CLOSES THE ACCOUNT'S BREAK ROW, AND UNTIL 2026-08-31 IT DID NOT
    (CR-051 task 6).** This IS BR-BIL-053's second way out, so an account that
    leaves through it has stopped being outstanding work — but its
    `bill_run_breaks` row went on saying it was. The live path is not the
    hypothetical one: an account that broke at calculate, was then given a
    HOLDING decision on S31.3, and was re-calculated goes through
    `decisions.apply_decisions` into here, leaves `ready`, and is therefore
    never reached by `_calculate_run`'s `clear_break`. Its break stayed
    OUTSTANDING for ever. The clerk's work list showed rows for accounts already
    dealt with, and BR-BIL-053's last clause — *"the run cannot enter phase 4
    with an unresolved break row"* — would refuse a run that was ready.

    **Closed as `held`, never as `drafted`:** this run does not bill the
    account. Recording it as drafted would tell a supervisor the opposite of
    what happened. A row is closed only if it was OUTSTANDING, so an account
    that broke, drafted on a later pass and was then held for an unrelated
    reason keeps the `drafted` history it earned.
    """
    row, _created = models.BillRunExclusion.objects.get_or_create(
        tenant_id=core_tenancy.current_tenant_id(),
        bill_run=bill_run,
        account_id=account_id,
        defaults={
            # ⚠ **`_id`, FOR THE REASON `release.authorise_release` ALREADY
            # RECORDS** (2026-08-31): an API caller holds the actor's UUID off
            # the session, a service caller holds the row, and
            # `excluded_by=<uuid>` raises `ValueError: Cannot assign … must be
            # a "User" instance`. The `_id` form accepts both, so the first HTTP
            # caller of this function (DEF-2856's break-hold route) did not have
            # to reach into `apps.identity` to look up a row it already had the
            # key to. ⚠ **The `getattr(…, "pk", …)` that used to sit here was
            # DEF-BIL-5090's SHAPE and not its occurrence** — every caller of
            # this function passes an id today, so nothing broke here; it would
            # have stored an ACTOR OBJECT the first time one arrived, which no
            # UUID column can hold. Fixed with the six that shared it.
            "reason_code": reason_code,
            "detail": detail or None,
            "excluded_by_id": audit.actor_user_id(excluded_by),
        },
    )
    clear_break(bill_run, account_id, resolution=models.BREAK_RESOLUTION_HELD)
    return row


def covered_by_later_read(readings: Any) -> set[str]:
    """🔒 DEF-MET-10163 — the service codes whose EVERY unread meter already
    has a later actual reading spanning the period's end (metering's
    `covered_by_read_id`). HUMAN-REVIEW-PENDING (money path).

    PO ruling 2026-10-15, verbatim *"go with 1 and 3"*; ruled clause 2: *"a bill
    run does not create an estimate for a period a later actual reading on that
    meter already covers; it uses the actual (or skips the estimate) instead"*.
    Worked: AC-2026-00049's September (last reading 09/24, the 10/06 actual
    measuring from 09/24) — no 560 kWh estimate; September bills its base and
    the next bill prices the 10/06 reading's 1,200 kWh from 09/24, so those
    days are billed once.

    It SKIPS the estimate through the ruled *"bill base, usage later"* path
    (PO 2026-09-30, fixed-charge case 1, option A) rather than pricing the later
    reading on this bill: a reading dated after the period's end is the next
    period's, and moving it here would be a new money rule nobody signed.

    A service with two meters is covered only when BOTH unread meters are — an
    uncovered one is still a missing read a clerk decides.
    """
    unread: dict[str, bool] = {}
    for reading in readings or ():
        if getattr(reading, "consumption", None) is not None:
            continue
        code = getattr(reading, "service_code", None)
        if not code:
            continue
        is_covered = bool(getattr(reading, "covered_by_read_id", None))
        unread[code] = unread.get(code, True) and is_covered
    return {code for code, all_covered in unread.items() if all_covered}


def _decisions_for(data: AccountBillingData, unmeasured: tuple[str, ...]) -> list[AccountProblem]:
    """What a human should look at before this account is billed.

    These accounts are BILLABLE — they are in `ready` and the run will bill
    them. They are listed because billing them without anyone looking is a
    decision taken by omission, and the PO's flow puts every decision on the
    screen. Each maps to a `BillRunDecision.case` so the choice, once made,
    lands in the trail with a name on it.
    """
    out: list[AccountProblem] = []
    # ── BR-BIL-301 · THE ACCOUNTS BILLING ZERO FOR A SERVICE THEY ARE SOLD ──
    # PO 2026-09-25, option (b) of three: *"Bill it at $0.00, and say so"*.
    # ⚠ PO 2026-09-30 took the `$0.00` LINE off the document (*"sane no line -
    # and use 0"*) and kept this list, since the reason for it — a silent zero
    # is how a missing connection survives for months — was not withdrawn. So
    # this row is now the ONLY place the gap is said, and it also carries the
    # services not in service because nothing stands on their point (no
    # asset, PO the same day) and a `%`-of-service following its basis.
    #
    # ⚠ **WHAT A CLERK CAN ACTUALLY DO FROM THIS ROW TODAY, SAID PLAINLY
    # RATHER THAN IMPLIED.** They can SEE it, and they fix it by connecting the
    # property — which today means the four existing paths and no other
    # (`BR-BIL-302`, PO ruling of the same day): creating the unit from its
    # ticked services, fitting a meter or asset, moving an asset, or IMPORT.
    # **There is deliberately no *connect a service* button**, and for fire,
    # trash, solar and battery there is no meter to fit either — so for those
    # the honest answer is *see it here, fix it by import*. A row offering an
    # action this product has not got would be worse than none.
    for service_code in getattr(data, "unconnected_services", ()) or ():
        out.append(
            AccountProblem(
                # DECISION_CASES "service_not_connected".
                reason="service_not_connected",
                detail=(
                    f"account {data.account_no}: the plan sells {service_code} "
                    "and this property has no connection for it. It bills "
                    "$0.00. Connect the property or bill it as it is."
                ),
                account_id=data.account_id,
                account_no=data.account_no,
                service_code=service_code,
            )
        )
    if data.behavior_class == "billable_base_only":
        out.append(
            AccountProblem(
                # DECISION_CASES "base_only_billing" — PO ruling 2026-08-11:
                # opt in or opt out, at prepare time, on screen.
                reason="base_only_billing",
                detail=(
                    f"account {data.account_no} is on a base-charges-only status. "
                    "It bills its standing charges and no usage; whether this run "
                    "bills it at all is your call."
                ),
                account_id=data.account_id,
                account_no=data.account_no,
            )
        )
    # ⚠ DEF-161: a service whose TARIFF prices no consumption of its own is not
    # a decision anybody has to take. Listing it would put 48 sewer rows on the
    # S31 exception screen every month, each offering three choices that are all
    # wrong — and the one a clerk would reach for, "bill without this service",
    # deletes a charge the customer owes.
    not_measured = {
        tariff.service
        for tariff in data.tariffs
        if measure_consumption_stage.prices_no_consumption(tariff)
    }
    # BR-RAT-090 (DEF-1813) — a service billed by a COUNT of its assets has a
    # quantity; it simply did not come from a register. Listing it as a missing
    # read would put work on the S31.3 screen that no clerk could ever clear,
    # beside the three carts the bill was just priced on.
    counted = {
        reading.service_code
        for reading in data.readings
        if getattr(reading, "asset_count", None) is not None
    }
    # 2026-09-30 — a service NOT IN SERVICE (no point, no asset) is on the
    # list above as `service_not_connected`; metering still reports its point
    # as `no_meter`, and listing it again as a missing read would offer a
    # clerk *estimate it* for a meter that does not exist. Two meters of one
    # service with no read list the service ONCE.
    not_in_service = set(getattr(data, "unconnected_services", ()) or ())
    # 🔒 DEF-MET-10163 (PO 2026-10-15, *"go with 1 and 3"*) — a service whose
    # every unread meter already has a LATER actual spanning this period's end
    # is not a missing read: there is nothing to estimate, and its usage waits
    # for the next bill, which that reading measures (`decisions._apply_to_account`).
    covered = covered_by_later_read(data.readings)
    listed: set[str] = set()
    for service_code in unmeasured:
        if service_code in not_measured or service_code in counted:
            continue
        if service_code in covered:
            continue
        if service_code in not_in_service or service_code in listed:
            continue
        listed.add(service_code)
        out.append(
            AccountProblem(
                # DECISION_CASES "missing_read" — BR-BIL-015: estimate, hold,
                # or bill without this service.
                reason="missing_read",
                detail=(
                    f"account {data.account_no}: no usable read for {service_code} "
                    "in this period. Estimate it, hold the account, or bill "
                    "without this service — nothing is assumed."
                ),
                account_id=data.account_id,
                account_no=data.account_no,
                service_code=service_code,
            )
        )
    out.extend(_continuity_decisions(data))
    return out


def _continuity_decisions(data: AccountBillingData) -> list[AccountProblem]:
    """`DEF-BIL-5270`'s CALENDAR half, as a decision row. The register half is
    not here and must not come back.

    ⚠ **THIS FUNCTION USED TO RAISE BOTH AND THE PO OVERRULED THE SECOND ONE
    (ruling 2026-09-14).** The register case — *May's bill closed the meter at
    13,500, June's read opens at 13,800, 300 kWh on no bill* — was built as a
    decision with two choices, on the reasoning that a gap is sometimes lawful.
    It is not: *"we cannot create wrong conusmption that is loss"*. It is now
    the anchor's own behaviour in `_anchor_quantity`, with no choice at all.

    **THE CALENDAR HALF SURVIVES BECAUSE IT IS GENUINELY AMBIGUOUS**, and the
    ruling says so in as many words: billed through 30 April with a run opening
    1 June can be a service switched off, an account closed and reopened, or a
    cycle that moved. A clerk is the one who can tell, so a clerk is asked.
    A meter that read 13,500 and now reads 13,800 recorded 300 units of real
    use and no circumstance makes billing them optional.

    An account whose last issued bill cannot be located answers `first_bill`
    and produces nothing at all — see `period_anchor`.
    """
    out: list[AccountProblem] = []
    anchor = period_anchor(data.account_id, period_start=data.period_start)
    if anchor.state in (CONTINUITY_GAP, CONTINUITY_OVERLAP):
        out.append(
            AccountProblem(
                # DECISION_CASES "billing_continuity" — DEF-BIL-5270. A literal
                # rather than the constant beside it because `G124` reads the
                # emitted case set out of THIS construction site.
                reason="billing_continuity",
                detail=(
                    f"account {data.account_no} was billed through "
                    f"{anchor.billed_through} and this period opens on "
                    f"{data.period_start}: {anchor.days} day(s) "
                    f"{anchor.from_day} to {anchor.to_day} "
                    + (
                        "no issued bill covers."
                        if anchor.state == CONTINUITY_GAP
                        else "an issued bill already covers."
                    )
                    + " Bill it as gathered, or hold the account and look."
                ),
                account_id=data.account_id,
                account_no=data.account_no,
                # DEF-BIL-8472 — the STATE travels as a fact, so the Check can
                # offer each row only the answers its state allows (an overlap
                # has no *Bill as it stands*, PO 2026-09-30 case 4) instead of
                # offering the tag's two and refusing one at the server.
                message_params={"state": anchor.state},
            )
        )
    return out


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-001@e9d5a48 (the four billing sources — B2 §2 + Addendum r10 ·
#         EP-BIL-01-bill-run.md · 07-billing/02-business-rules.md ·
#         07-billing/03-field-map.md)
# generated: 2026-08-11 by Eng-Lead (W3 bill-run lane — the PO's phases 1–2)
# checklist: A✔ B✔ C✔ D✔(the API half landed 2026-08-11 — `create_run` and `prepare_run` are served by POST /billing/runs and GET /billing/runs/{id}/findings; the trailer said 'no-API-half yet' and that claim is now false, hard-won law 1) E✔(S31 ships and calls both) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · tests/test_us_bil_001_prepare.py (11, real rows across
#         four modules)
# exceptions: (1) PHASES 1 AND 2 ONLY. Phase 3 (the break list), 4 (the summary)
#         and 5 (the release) are NOT here, and neither is the background job
#         runner — `calculate_account` bills ONE account and something has to
#         call it per account, which nothing yet does. There is no `tasks.py` in
#         this codebase, so "in the background" currently means "not built"
#         rather than "asynchronous". This module must not be read as though
#         the run works end to end.
#         (2) `prepare_run` WRITES NOTHING — no exclusion rows, no drafts, no
#         run status. Deliberate: the PO's flow looks before it commits, and a
#         prepare pass that wrote would make looking a committing action. The
#         consequence is that a prepare is not resumable — re-preparing re-reads
#         — which is correct for a read-only pass but is stated, not implied.
#         `calculate_account` DOES write, which is the phase boundary.
#         (4) `calculate_account` refuses an account whose missing read has no
#         decision, rather than billing the other services. That is the
#         "bill without this service" choice (BR-BIL-015) and it belongs to a
#         human; taking it here would leave no record that anyone had.
#         (5) CLOSED 2026-08-11 — decisions ARE applied. This entry used to read
#         "DECISIONS ARE NOT YET APPLIED … `gather.with_readings` is the seam for
#         it and has no caller", which was true when written and is now false:
#         `apps/billing/decisions.py` records a decision and `apply_decisions`
#         rewrites the prepared data from it, THROUGH `gather.with_readings`. An
#         estimate a clerk chose reaches the bill (test_us_bil_003 tc4 — 400 kWh
#         priced to 66.50). Rewritten rather than deleted: hard-won law 1 cuts
#         both ways, and a stale absence-claim is as misleading as a stale
#         guarantee.
#         (3) `_resolve` reaches into `gather._resolve` rather than duplicating
#         it. One resolver, so a change to how seams are found cannot apply to
#         half the run.
#         (6) `calculate_run` catches THREE hierarchies, not two — DEF-047.
#         `rating_seam.PricingRefused` is caught FIRST, before its own base
#         class, so the break names `price-usage`. Until 2026-08-11 rating's
#         `RatingError` was caught by nothing at all and one unpriceable account
#         ended the whole run; tc2 and tc3 both proved the no-rollback property
#         with billing's OWN exception types, so the loop looked robust while it
#         was robust to half of what can fail. If a fourth module ever raises
#         into this loop, it needs a clause here and a translation at its seam.
#         (7) [run-API lane 2026-08-11] `AccountProblem` GAINED `stage`, derived
#         in `__post_init__` from `STAGE_BY_REASON` so no construction site can
#         produce a problem whose stage disagrees with its reason. `Break` had
#         carried its stage since it was written; the asymmetry meant S31.2 kept
#         a SECOND copy of the reason→stage map (fourteen codes) to place its
#         findings, and that copy is now deleted. A stage of None is a real
#         answer — the run's own shape and the base-only opt-in are not stage
#         failures — and the screen puts those on Consumers where the epic does.
#         `STAGE_BY_REASON` gained ONE entry with it: `missing_read` →
#         measure-consumption, the phase-1 decision form of a fact the map
#         already held for phase 2.
#         (8) [run-API lane 2026-08-11] `create_run` writes the `bill_runs` row
#         US-BIL-001 exits with, and NOTHING else — no prepare, no draft, no
#         status change. Three things about it are stated rather than implied:
#         the cycle is verified through metering's PUBLISHED read because a
#         foreign key alone would NOT stop a run pointing at another tenant's
#         cycle (PostgreSQL evaluates referential integrity outside RLS); the
#         duplicate check exists only so the common case gets BR-BIL-005's
#         who/when/link message, and the UNIQUE index is the real guarantee (a
#         lost race is caught, re-read and answered with the same refusal); and
#         ~~the BILL DATE the clerk typed has no column here at all~~ CLOSED
#         2026-08-11 by the PO's OQ-122 ruling — see (9).
#         (9) [typed-bill-date lane 2026-08-11] `create_run` TAKES AND STORES
#         `bill_date`, and `effective_bill_date` is the single place that
#         resolves "what date does this run bill on" — the typed one, else the
#         cycle's, never a clock. BR-BIL-070, PO ruling closing OQ-122 option A
#         (*"A Store what they type and use it"*). Worked: cycle 1 Aug, clerk
#         types 3 Aug → the run prices at 3 Aug and falls due 24 Aug, where it
#         used to price at 1 Aug and fall due 22 Aug. **The bill date is
#         deliberately NOT in the idempotency key** (BR-BIL-005 keys on tenant +
#         cycle + period): keying on it would let one cycle-period be billed
#         twice by retyping one field. **REPORTED, and the reason it is not
#         fixed here:** the DUE-date half of the ruling needs
#         `issue._due_terms_for` to prefer `bill_runs.bill_date` over
#         `cycle__bill_date`, and `apps/billing/issue.py` is owned by another
#         lane in this session. Until that one-line read changes, a run with a
#         typed bill date PRICES at the typed date and DERIVES its due date from
#         the cycle's — stated here rather than papered over, because a comment
#         claiming the whole ruling shipped would be hard-won law 1 again.
#         RED PROOFS EXECUTED AND MEASURED (hard-won law 7), both reverted:
#         (i) THE TYPED DATE IGNORED. `effective_bill_date` reduced to
#         `return cycle_bill_date` — i.e. the pre-ruling behaviour exactly.
#         `pytest tests/test_oq122_run_bill_date.py -q` measured `4 failed,
#         5 passed in 30.32s`; the pricing case failed verbatim
#         `assert datetime.date(2026, 8, 1) == datetime.date(2026, 8, 3)` —
#         the run back on the CYCLE's 1 Aug where the clerk typed 3 Aug.
#         Reverted → `9 passed in 21.47s`.
#         (ii) BUILT BUT NOT WIRED (hard-won law 2). With
#         `bill_date=_optional_date_field(payload, "bill_date")` deleted from
#         `apps/billing/api.bill_runs` — the column, the model field, the
#         service argument and every unit assertion still perfectly in place —
#         the same suite measured `2 failed, 7 passed in 21.74s`, verbatim
#         `assert None == datetime.date(2026, 8, 3)` / `+ where None =
#         <BillRun ...>.bill_date`: the wizard POSTs the date, the server has a
#         column for it, and the clerk's entry still vanishes. Reverted →
#         `9 passed in 26.86s`.
# exceptions: [US-MET-013 dispute lane 2026-08-16] `prepare_run` now BLOCKS an
#         account whose unit carries an uncleared dispute (BR-MET-024 /
#         the OQ-043 closure). It is a BLOCK and not a DECISION on purpose: a
#         clerk cannot opt past it, because the closure gives the release to a
#         System Admin clearing the marker. An UNPUBLISHED
#         `dispute_holds_for_unit` seam HOLDS rather than releases — "we could
#         not tell" and "there is no dispute" are different facts and only one
#         is safe to bill on. RED-PROVED by deleting the call: the disputed
#         account billed, verbatim `AssertionError: assert ['A-10001',
#         'A-10002'] == ['A-10002']`
#         [master-account BILL-ASSEMBLY lane 2026-08-22 — 🔒 HUMAN-REVIEW-PENDING]
#         `readings_for_account` reads EVERY unit a BR-CUS-068 master account
#         covers, the billed-units set counts coverage rather than anchors
#         (DEF-572) and a dispute on ANY covered meter holds the bill. ⚠ ONE
#         RESIDUE, REPORTED AND NOT FIXED: coverage is answered per ACCOUNT and
#         a run is scoped per CYCLE, so a premises whose common areas sit in
#         DIFFERENT cycles still gets a false `unit_has_no_billable_account`
#         row in the OTHER cycle's run — the master is billed once, in its
#         ANCHOR's cycle, carrying every covered meter's usage, and the second
#         run cannot see that from `accounts.unit_id`. It is NOT fixed by
#         asking `master_account_covering_unit` here, deliberately: that would
#         also silence the case where a covering master is billed by NO run at
#         all (its anchor in no cycle), turning real unbilled usage into
#         silence — the false-green DEF-108 is about. A premises' common areas
#         sharing one cycle is the ordinary shape and bills correctly.
# exceptions: [DEF-1813 unmetered-count lane 2026-08-28, BR-BIL-710]
#         `_readings_for` carries metering's `asset_count` onto the reading
#         UNPRICED; `stages/measure_consumption._counted_quantity` makes it the
#         billable quantity with the TARIFF's own `billed_unit`, because that is
#         the one place the tariff is in hand and CLAUDE.md rule 3 forbids
#         borrowing a unit from anywhere else. **3 carts x $15.00 = $45.00;
#         remove one and the next bill is $30.00** (BR-RAT-090).
#         `CALC_ASSET_COUNT_UNAVAILABLE` refuses an ABSENT count BEFORE the
#         missing-read refusal and with its own wording, because the two send a
#         clerk to two different places — a missing read is estimated on the
#         Reads tab, a missing count is fixed by going and counting the carts —
#         and it is NOT retryable here for the same reason. A counted service
#         leaves `unmeasured` and `_decisions_for`, so it is never work no clerk
#         could clear beside the carts the bill was priced on.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
