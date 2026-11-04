# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-012 (S30 One-time bill tab · S31 in single-account mode —
#           the bulk wizard scoped to ONE account)
#           Screens: S30 · S31
# Rules:    BR-BIL-020 (ad-hoc single bill = the bulk wizard in single-account
#           mode: preview → exceptions → draft → issue; lines come ONLY from
#           rules and charge codes — free-typed amounts never exist on any
#           bill) · BR-BIL-023 (same draft powers, same never-edit-computed
#           rule) · BR-BIL-015 (a missing input is an EXCEPTION a human
#           decides) · BR-BIL-055 (a held account waits for a catch-up
#           sub-run — never a colliding parallel bill) · BR-CUS-055 (behaviour
#           classes decide who is billed at all) · BR-RAT-007 (price on the
#           SERVICE date) · BR-TEN-043 (event-time law — no clock here)
# Tests:    06-backend/tests/test_us_bil_012_single.py
# Impacts:  apps/billing/backbill.py + apps/billing/final_bill.py +
#           apps/billing/penalty.py (all three enter through THIS module's
#           account resolution — BR-BIL-018's "via the single-account flow") ·
#           S30's One-time bill tab, which renders exactly this
# ───────────────────────────────────────────────────────
"""Single-account mode: the SAME pipeline, scoped to one account.

🔒 **HUMAN-OWNED · HUMAN-REVIEW-PENDING (account resolution on a money path) — 2026-09-16,
lane C wave 1.** `billable_account` stopped refusing a premises-anchored master
account (`DEF-BIL-5457`) and `SingleScope.unit_id` became optional. What that
changes in one sentence: **a utility can now raise a one-off bill against an
owner's account for a whole address, which it could not do at all before** —
this is the door the New Connect wizard's Charges step bills a developer
through. The billable-CLASS test (`BR-CUS-055` — a pending or closed account
still refuses) is unchanged and is now read from `selectors.billable_accounts`,
the same filter `accounts_for_bill_run` applies. Row in
`12-governance/09-human-review-ledger.md`.

BR-BIL-020 is one sentence and it settles the whole design: *"Ad-hoc single
bill = the bulk wizard in single-account mode (preview → exceptions → draft →
issue)"*. So this module is an ENTRY POINT and not a pipeline. It resolves who
is being billed, gathers exactly what `prepare_run` gathers, and hands the
result to `runs.calculate_account` — the same seven stages, the same
per-account atomicity, the same draft replacement.

**A second pricing path would be a second thing to be wrong.** The reason that
is not a stylistic preference: every figure in B4/B5 is frozen once, and a
parallel "simple" path for one-off bills is how a tenant discovers that their
interim bills round differently from their cycle bills. There is one engine
call in this file and it is `runs.calculate_account`.

WHAT SINGLE MODE ADDS OVER `prepare_run`, and it is only two things:

  * **Scope by ACCOUNT rather than by cycle.** A cycle run asks metering which
    units are in the route and customers who occupies them; single mode names
    the account and asks customers the same billability question about it —
    through `accounts_for_bill_run`, deliberately, so "who can be billed" has
    ONE definition (BR-CUS-055). An account a cycle run would skip is an
    account this flow refuses, and it refuses by NAME.
  * **The held-period check** (BR-BIL-055, US-BIL-012 TC-5). An account sitting
    in the pending-billing queue for a period must not be billed in parallel
    for that same period: it belongs in the catch-up sub-run that will resolve
    its exclusion row. Two bills for one period is the one outcome a clerk
    cannot undo without a correction.

WHAT IT DELIBERATELY DOES NOT HAVE — and this is the prototype diff, stated in
both directions (hard-won law 6):

    05-prototype/UtilityBilling.html step 2 of the One-time bill wizard
    renders every line as an EDITABLE description input and an EDITABLE amount
    input, plus a "+ Add line" button.

That is superseded, in writing, by BR-BIL-020: *"free-typed amounts never exist
on any bill"* (US-BIL-012 TC-4). No function in this module takes an amount, a
description or a line — there is no parameter to pass one to, which is why the
test for TC-4 introspects the module's own signatures rather than asserting a
rejection message. A rejection can be removed; a missing parameter cannot be
passed by accident.

The prototype is RIGHT and this module is behind on two points, both reported
rather than invented:

  * Its step 1 offers a **bill date**. That field HAS a home as of 2026-08-11 —
    the PO closed OQ-122 with *"Store what they type and use it"* and
    `bill_runs.bill_date` + `runs.effective_bill_date` shipped in migration
    0011 — and this module does not accept one. A single-account bill therefore
    dates from the caller's `service_date` alone, which is correct but is less
    than the run path now offers. (Written this way deliberately: the sentence
    here first said the column did not exist, which was true when it was typed
    and false a few hours later. Hard-won law 1 cuts both ways.)
  * Its step 1 offers a fourth kind, **"Deposit invoice"**, which no story in
    EP-BIL-03 owns — hard-won law 8, every screen needs a story. Not built, and
    not invented.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from typing import Any

from apps.billing import gather, models, runs
from apps.billing.contracts import AccountBillingData
from apps.billing.exceptions import BillingRuleError
from core import tenancy as core_tenancy

#: Why single mode refuses to bill this account. VALUES, not prose: S30 groups
#: its findings the way S31.2 does and a grouping key has to be stable.
SINGLE_NOT_BILLABLE = "account_not_billable_in_this_mode"
SINGLE_HELD_PERIOD = "account_held_for_this_period"

#: The bill types that have their OWN entry point with their own rules. Naming
#: them here is what stops single mode becoming a back door: a clerk who picks
#: "Catch-up (missed cycles)" with a past period is running US-BIL-013's rules
#: (per-sub-period tariff versions, the window cap, the approval gate), and
#: producing that bill through this function would price the whole span on ONE
#: version — the silent-overcharge case US-BIL-013 exists to prevent.
ROUTED_ELSEWHERE: dict[str, str] = {
    "backbill": "apps.billing.backbill.prepare_back_bill (US-BIL-013 — per-sub-period "
    "tariff versions, the tenant window cap and the approval gate)",
    "penalty": "apps.billing.penalty.prepare_penalty_bill (US-BIL-014 — assessed reads "
    "priced by the engine plus charge-code penalties)",
    "final": "apps.billing.final_bill.prepare_final_bill (US-BIL-011 — billed through "
    "the move day, deposit applied first, exactly one settlement path)",
    # `first` is US-BIL-010: the run marks it automatically for accounts whose
    # move-in falls inside the period, from the move-in date. It is system-
    # derived (US-BIL-010 TC-6) and therefore not a kind a caller may request.
    "first": "US-BIL-010 — first-bill classification is system-derived from the "
    "move-in date and is never user-set",
}


@dataclass(frozen=True)
class SingleScope:
    """One account resolved for billing, with the row the pipeline needs.

    `account` is customers' own row, held rather than copied: `gather` reads it
    by attribute (`unit_id`, `status`, `opened_at`, `closed_at`, `tax_exempt`)
    and billing never imports the model (B1).
    """

    account_id: str
    account_no: str
    #: The unit this account anchors on, or **None for a premises-anchored
    #: master account** (`BR-CUS-1010`, `CR-056` W1, PO 2026-09-01 — *"the row
    #: now writes `premises_id` and leaves `unit_id` NULL"*).
    #:
    #: ⚠ **IT WAS TYPED `str` UNTIL 2026-09-16 AND THE TYPE WAS THE LEAST OF IT**
    #: — `billable_account` refused such a row outright (`DEF-BIL-5457`). The
    #: readers that matter already tolerate the absence: `gather_single` prices
    #: `covered_units` rather than the anchor, and the `AccountProblem` built
    #: below carries `BR-BIL-1025`'s own sentence about *"an owner's account at
    #: an address he occupies himself"*. The anchor was never the thing a bill
    #: is assembled from; it was only the thing the front door demanded.
    unit_id: str | None
    account: Any


def _unit_less_scope(row: Any, account_id: Any) -> SingleScope:
    """The scope for an account that anchors on an ADDRESS instead of a unit.

    ⚠ **THIS REPLACES A REFUSAL THAT COULD ONLY EVER FIRE ON THE ACCOUNTS A
    RULING HAD ALREADY MADE LAWFUL (`DEF-BIL-5457`).** Until 2026-09-16
    `billable_account` raised here:

        GatherProblem: account 'AC-2026-00001' has no unit, so it has no plan
        and no service points. BR-CUS-017 binds an account to exactly one unit.

    Three things are wrong with that, and the third is the one that decides it:

      1 · **The cited rule was superseded for exactly this row.**
          `BR-CUS-1010` (`CR-056` W1, PO 2026-09-01) moved a master account off
          the common-area unit and onto the premises — *"the row now writes
          `premises_id` and leaves `unit_id` NULL"*. The guard went on quoting
          `BR-CUS-017` at the shape its own supersession created.
      2 · **The intent was recorded and the guard was not amended.** The
          master-account bill-assembly ruling of 2026-08-22 says in terms:
          *"single/final/first/one-time/back-bill inherit all of it because they
          all gather through `single.gather_single`"*. They could not, because
          this function sits in front of `gather_single` and never let them
          reach it.
      3 · **The refusal was DEAD for the accounts it was written for.** The live
          schema carries `ck_accounts_regular_has_unit` —
          `NOT kind='regular' OR unit_id IS NOT NULL` — so an ordinary account
          ALWAYS has a unit and can never reach this branch. Every row that ever
          did was a master. A guard that cannot fire on its target and fires
          only on the exception is not protecting anything.

    **WHAT IS STILL CHECKED, BECAUSE IT IS THE PART THAT MATTERS.** Dropping the
    unit does NOT drop the billable-class test: `BR-CUS-055` says billability is
    a CLASS, and a pending-activation or closed account must refuse here exactly
    as it does for a unit-anchored one. `accounts_for_bill_run` cannot answer —
    it is that class filter PLUS a unit scope, and there is no unit — so this
    reads `billable_accounts()`, which is the same filter with nothing added.
    Two readers of one class set, not two copies of it, which is the reason
    `selectors` extracted it in the first place.

    **WHAT A FEE BILL NEEDS FROM A UNIT: NOTHING.** `fee_bill._fee_usage` builds
    *"a subscription to NOTHING"* — no plan, no service points, no readings —
    because a fee is a fact about the ACCOUNT. So the anchor was never an
    ingredient of the document; it was a precondition nobody had re-read.

    ⚠ **THIS IS NOT A LICENCE TO BILL AN UNPLANNED ACCOUNT FOR USAGE.** A
    METERED bill over such an account still resolves nothing to price and still
    refuses, one layer down, where the refusal is true: `gather_single` prices
    `covered_units`, and an owner's account covering none produces
    `BR-BIL-1025`'s *"covers no unit and its address holds no unoccupied unit to
    charge for"* — which this module already builds, a hundred lines below, and
    already treats as the correct state rather than an error.
    """
    billable = runs._resolve("customers", "billable_accounts")
    if billable is None:
        raise BillingRuleError(
            "customers has not published `billable_accounts`, so an address-anchored "
            "account's billability cannot be established without a unit to scope on. "
            "Nothing is assumed: BR-CUS-055 makes billability a class, and a bill for "
            "an account whose class nobody checked is a bill for a closed customer."
        )
    account = billable().filter(pk=account_id).first()
    if account is None:
        raise gather.GatherProblem(
            SINGLE_NOT_BILLABLE,
            f"account {getattr(row, 'account_no', account_id)!r} is not billable "
            "(BR-CUS-055). A pending-activation or closed account is correctly out of "
            "scope for an ordinary bill — a closed account's last bill is a FINAL bill "
            "(US-BIL-011) and goes through that flow, which settles the deposit.",
        )
    return SingleScope(
        account_id=str(account.id),
        account_no=account.account_no,
        unit_id=None,
        account=account,
    )


#: The ONE account status a New Connection fee may be billed to while it
#: waits (`DEF-MET-9217`). customers' own code for it
#: (`customers.services.PENDING_STATUS_CODE`), read off the row billing already
#: holds — never a class, because `disconnected` is `non_billable` too.
PENDING_NEW_CONNECTION_STATUS = "pending_activation"


def _pending_new_connection_scope(row: Any) -> SingleScope | None:
    """🔒 HUMAN-REVIEW-PENDING · `DEF-MET-9217` — the scope for a New Connection
    owner's account that is HELD PENDING until the build is approved, or None.

    `CR-162-BRC10` (PO 2026-10-02, Q1) opens the owner's account *"PENDING at
    Create, ACTIVE on approval"*, and `CR-163-BRC10` item 2 (*"Add fees after
    submission, until approval"*, then *"Yes. It creates real bills."*) adds
    fees to that same account in exactly that window. BR-CUS-055 keeps a
    pending account out of every ordinary bill, so the two rulings met here and
    every Add fee refused. The quote at Create never met it only because the
    commit bills BEFORE it holds the account (`connections.commit_connection`).

    **NARROW BY CONSTRUCTION:** only a caller that says so reaches this (the
    New Connection fee door, `metering.connection_fees`, which has already
    checked the build is not yet approved and that this is the build's own
    payer), and only an account whose status is exactly
    `pending_activation` — a closed, disconnected or any other non-billable
    account still refuses below, word for word as before.
    """
    status = getattr(row, "status", None)
    if getattr(status, "code", None) != PENDING_NEW_CONNECTION_STATUS:
        return None
    unit_id = getattr(row, "unit_id", None)
    return SingleScope(
        account_id=str(row.pk),
        account_no=row.account_no,
        unit_id=str(unit_id) if unit_id else None,
        account=row,
    )


def billable_account(account_id: Any, *, pending_new_connection_owner: bool = False) -> SingleScope:
    """THE account this bill is for — or a named refusal. No default, ever.

    `pending_new_connection_owner` (`DEF-MET-9217`, 🔒 HUMAN-REVIEW-PENDING) —
    passed ONLY by the New Connection fee door; see
    `_pending_new_connection_scope`. Every other caller is unchanged.

    Resolved through customers' `accounts_for_bill_run`, which is the same read
    a cycle run scopes on, so single mode inherits BR-CUS-055's classes rather
    than re-stating them. A `non_billable` (pending activation) or `terminal`
    (closed) account therefore refuses here — correctly: those are silently out
    of scope for a cycle run, and a one-off bill for a closed account is a
    final bill (US-BIL-011), not this.

    Unknown, malformed and ANOTHER TENANT'S account id are ONE answer — absent
    (HR-1) — because the read is tenant-scoped under RLS and a distinguishable
    "not yours" would let an id be probed.
    """
    account_or_404 = runs._resolve("customers", "account_or_404")
    accounts_for = runs._resolve("customers", "accounts_for_bill_run")
    if account_or_404 is None or accounts_for is None:
        raise BillingRuleError(
            "customers has not published account_or_404/accounts_for_bill_run, so "
            "single-account mode cannot resolve who is billed. Nothing is assumed: a "
            "bill for an account nobody could verify is a bill for nobody."
        )
    # Raises customers' own `deny_as_not_found` for an unknown, malformed or
    # cross-tenant id — one answer for all three, so no id can be probed.
    row = account_or_404(account_id)
    if pending_new_connection_owner:
        pending = _pending_new_connection_scope(row)
        if pending is not None:
            return pending
    unit_id = getattr(row, "unit_id", None)
    if not unit_id:
        return _unit_less_scope(row, account_id)
    for account in accounts_for([str(unit_id)]):
        if str(account.id) != str(account_id):
            continue
        return SingleScope(
            account_id=str(account.id),
            account_no=account.account_no,
            unit_id=str(account.unit_id),
            account=account,
        )
    raise gather.GatherProblem(
        SINGLE_NOT_BILLABLE,
        f"account {getattr(row, 'account_no', account_id)!r} is not in the billable set "
        "for its unit (BR-CUS-055). A pending-activation or closed account is correctly "
        "out of scope for an ordinary bill — a closed account's last bill is a FINAL "
        "bill (US-BIL-011) and goes through that flow, which settles the deposit.",
    )


def held_for_period(account_id: Any, *, period_start: date, period_end: date) -> Any:
    """The unresolved exclusion overlapping this period, or None (BR-BIL-055).

    US-BIL-012 TC-5. The pending-billing queue IS `bill_run_exclusions` with
    `resolved_at IS NULL` (r10 #7), and the period comes from the RUN the
    exclusion was written against — the row itself carries no dates, because an
    exclusion is always about one run's window.

    Overlap and not equality: a clerk billing Jul 15 – Aug 6 while the account
    is held for the July cycle would produce two bills covering July 15–31. The
    held period is the one the catch-up sub-run will bill (BR-BIL-055's "one
    pending queue, two doors"), so the overlap is the collision.
    """
    return (
        models.BillRunExclusion.objects.filter(
            tenant_id=core_tenancy.current_tenant_id(),
            account_id=account_id,
            resolved_at__isnull=True,
            bill_run__period_start__lte=period_end,
            bill_run__period_end__gte=period_start,
        )
        .select_related("bill_run")
        .order_by("created_at", "id")
        .first()
    )


def gather_single(
    scope: SingleScope,
    *,
    period_start: date,
    period_end: date,
    service_date: date,
    cycle_days: int | None = None,
    scope_services: tuple[str, ...] | None = None,
    keyed_reads: Any = None,
    reads_from: date | None = None,
) -> AccountBillingData:
    """One account's billing data, read exactly as a cycle run reads it.

    `reads_from` (`DEF-BIL-8563`) opens the READINGS window on a later day than
    the billed window, and only a first bill passes it: the reading taken ON
    the move-in day is the register the customer took the service on — the
    START reading — so the readings are asked for from the day after, while the
    move-in day itself is still a billed day (`period_start`, service days and
    proration are untouched). `None` everywhere else: byte-identical to before.

    The reads come through `runs._readings_for` rather than a second call to
    metering's seam. That is the point of reaching into a neighbour's private
    helper: the alternative is a second call site with its own idea of what a
    unitless quantity means (CLAUDE.md rule 3) and its own handling of an
    absent read (BR-BIL-015) — two copies of a rule that has exactly one
    correct implementation.

    `cycle_days` defaults to the period's own length. It is separable for the
    reason B4.3 makes it separable: proration divides service days by CYCLE
    days, and a short ad-hoc period must not shrink the denominator — that
    would charge a three-week interim bill a full month of base charges.
    """
    days = cycle_days if cycle_days is not None else (period_end - period_start).days + 1
    # EVERY unit this account covers (BR-CUS-068 / DEF-571), which for every
    # ordinary account is `scope.unit_id` and nothing else — `covered_units`
    # answers the anchor alone unless the row is `kind='master'`.
    readings, _unmeasured = runs.readings_for_account(
        scope.account,
        period_start=reads_from or period_start,
        period_end=period_end,
        scope_services=scope_services,
        # `DEF-CUS-5931` — the move-out wizard's step-2 capture, priced and not
        # written (PO 2026-09-20). `None` on every other caller.
        keyed_reads=keyed_reads,
    )
    return gather.gather_account(
        account=scope.account,
        service_date=service_date,
        period_start=period_start,
        period_end=period_end,
        cycle_days=days,
        readings=readings,
        scope_services=scope_services,
    )


def with_price_split(
    data: AccountBillingData,
    scope: SingleScope,
    *,
    period_start: date,
    period_end: date,
    cycle_days: int,
    cycle_days_for: Any,
    scope_services: tuple[str, ...] | None = None,
    keyed_reads: Any = None,
    reads_from: date | None = None,
) -> AccountBillingData:
    """🔒 HUMAN-REVIEW-PENDING · `DEF-BIL-8749` (CR-156-BRC10) — a FIRST or
    FINAL bill whose window crosses a charge-code price change is cut there.

    PO 2026-10-01: *"a period crossing a change is split by days"*, and *"each
    part is prorated over its own month"*. The catch-up, the interim and the
    cycle bill were cut by wave A; the first and final bills priced the WHOLE
    window at the row in force on their service date. This attaches the same
    `midperiod.gather_split` segments, **price cuts only** (`price_only=True`):
    a rate-version or plan boundary inside a first or final bill is NOT newly
    cut here — the 2026-08-22 ruling kept typed documents on their own rules,
    and this defect is about the charge code's dated price, nothing else.

    Each part is gathered on its own first day and divided by
    `cycle_days_for(part_start, part_end)` — the account's cycle length on the
    part's last day (B4.3 ❄️ unchanged: service days / cycle days, per part).
    Worked, the PO's case: first bill 10/16–11/15, BASE-S $9.00 → $10.00 from
    11/01 → 16/31 × 9.00 = **$4.65** + 15/30 × 10.00 = **$5.00** = **$9.65**.

    No price change inside the window → no segments → the data is returned
    untouched, so every bill without one (every frozen B5 figure among them)
    walks the path it walked before.
    """
    from apps.billing import midperiod

    segments = midperiod.gather_split(
        scope.account,
        period_start=period_start,
        period_end=period_end,
        cycle_days=cycle_days,
        scope_services=scope_services,
        price_only=True,
        cycle_days_for=cycle_days_for,
        reads_from=reads_from,
        keyed_reads=keyed_reads,
    )
    if not segments:
        return data
    return replace(data, split_segments=segments)


def prepare_single_bill(
    *,
    account_id: Any,
    period_start: date,
    period_end: date,
    service_date: date,
    cycle_days: int | None = None,
    scope_services: tuple[str, ...] | None = None,
    bill_type: str = "cycle",
    keyed_reads: Any = None,
    price_split_cycle_days: Any = None,
) -> runs.PreparedRun:
    """Phase 1 for ONE account. Writes nothing — the same promise `prepare_run` makes.

    ── `price_split_cycle_days` · AN INTERIM BILL CROSSING A CHANGE ─────────
    🔒 `CR-156-BRC10`. PO 2026-10-01, option A, ruled (4): *"a period crossing
    a change is split by days"*, worked on an INTERIM bill — 10/16–11/15 with
    BASE-S $9.00 → $10.00 from 11/01 is `16/31 × 9.00 + 15/30 × 10.00 = 4.65 +
    5.00 = $9.65`, *"each part is prorated over its own month"*. An interim
    bill is typed `cycle` (`one_time.BILL_TYPE_BY_KIND`), so it already takes
    `BR-RAT-114`'s split below — now cut at a base charge code's price change
    as well (`midperiod.split_boundaries`) — and this callable gives each part
    the account's cycle length on that part's last day
    (`one_time.interim_bill_cycle_days`, `BR-BIL-1066`) instead of the whole
    window's. Without it the October part divides by November's 30: `16/30 ×
    9.00 = 4.80`, the figure the PO's reply corrected. A window inside one
    cycle gets the same denominator either way; `None` (every other caller)
    keeps the caller's cycle for every part, exactly as before.

    Returns a `PreparedRun` and not a bespoke type, so S31.2's preview, its
    findings tabs and S31.3's exception list render single mode with no second
    implementation. `cycle_id` is empty because a one-off bill has no cycle:
    `bill_runs.cycle_id` is NOT NULL, which is why the run row (when the caller
    wants one) is the caller's to create — see `calculate_single_bill`.

    Every refusal here is a REFUSAL and not a blocked entry: single mode is one
    account and one clerk waiting on one screen, so there is no "the other 493"
    to protect. That is the one shape difference from `prepare_run`, and it is
    deliberate.
    """
    if period_end < period_start:
        raise BillingRuleError(
            f"period {period_start} → {period_end} ends before it begins. Every "
            "proration in B4.3 divides by this window, so the bill is refused rather "
            "than computed over a window that cannot be divided."
        )
    if bill_type in ROUTED_ELSEWHERE:
        raise BillingRuleError(
            f"a {bill_type!r} bill has its own rules and its own entry point: "
            f"{ROUTED_ELSEWHERE[bill_type]}. Producing one through the ordinary "
            "single-account flow would apply none of them — which is how a six-month "
            "catch-up gets priced at today's rates."
        )
    if bill_type not in models.BILL_TYPES:
        raise BillingRuleError(
            f"unknown bill type {bill_type!r}. B2 r10 #12 defines {models.BILL_TYPES}; "
            "a type the code does not implement stops the bill rather than defaulting "
            "to 'cycle', which would mistype a document that is kept for seven years."
        )

    scope = billable_account(account_id)
    holding = held_for_period(scope.account_id, period_start=period_start, period_end=period_end)
    if holding is not None:
        raise gather.GatherProblem(
            SINGLE_HELD_PERIOD,
            f"account {scope.account_no} is held for a period overlapping "
            f"{period_start} → {period_end} (exclusion {holding.pk}, reason "
            f"{holding.reason_code!r}). BR-BIL-055 settles it in a catch-up sub-run; a "
            "parallel single bill would bill the same days twice and only a correction "
            "could undo it.",
            service_code=None,
        )

    days = cycle_days if cycle_days is not None else (period_end - period_start).days + 1
    ready: list[AccountBillingData] = []
    blocked: list[runs.AccountProblem] = []
    decisions: list[runs.AccountProblem] = []
    silent: list[runs.AccountProblem] = []
    try:
        data = gather_single(
            scope,
            period_start=period_start,
            period_end=period_end,
            service_date=service_date,
            cycle_days=days,
            scope_services=scope_services,
            # `DEF-BIL-8300` — the one-time bill's step-2 values, priced as
            # provisional by the PREVIEW only (contract §2). `None` on every
            # other caller, the draft included.
            keyed_reads=keyed_reads,
        )
    except gather.GatherProblem as problem:
        # ── `BR-BIL-1025` · IS THIS A FAULT, OR IS IT SIMPLY QUIET? ──────────
        # The SAME classifier the cycle run uses (`gather.nothing_to_bill`), on
        # the same list name, because two vocabularies for one fact is how the
        # batch path and the single path come to disagree about who was billed.
        # An owner's account at an address he occupies himself covers nothing
        # and has no unoccupied unit, so the gather refuses it for want of a
        # unit — a refusal that is CORRECT for an account that ought to have had
        # something, and a wrong sentence for this one. The clerk who asked for
        # this bill by name still gets a refusal (see `calculate_single_bill`);
        # what changes is that the refusal says there was nothing to bill rather
        # than describing a configuration problem that does not exist.
        target = silent if gather.nothing_to_bill(scope.account) else blocked
        target.append(
            runs.AccountProblem(
                reason=(runs.RUN_NOTHING_TO_BILL if target is silent else problem.reason),
                detail=(
                    (
                        f"account {scope.account_no} covers no unit and its address holds "
                        "no unoccupied unit to charge for, so there is nothing to bill it "
                        "for this period. That is the correct state for an owner's account "
                        "at an address he occupies himself (BR-BIL-1025)."
                    )
                    if target is silent
                    else str(problem)
                ),
                account_id=scope.account_id,
                account_no=scope.account_no,
                unit_id=scope.unit_id,
                service_code=problem.service_code,
                # `DEF-BIL-8287` — rating's clerk sentence (`DEF-RAT-7991`)
                # rode on the problem and was dropped here, so the one-time
                # bill's blocked row fell back to a generic line. Copy only.
                message_key=None if target is silent else problem.message_key,
                clerk_detail=None if target is silent else problem.clerk_detail,
                message_params=None if target is silent else (problem.message_params or None),
            )
        )
    else:
        # BR-RAT-114 (PO 2026-08-22): the ordinary single bill splits at a
        # mid-period rate/plan boundary exactly as the cycle run does — same
        # helper, same refusal semantics (single mode refuses rather than
        # lists, per this function's own shape). CYCLE ONLY: interim and other
        # typed documents keep their own rules (decision log 2026-08-22,
        # judgment 4); back-bill/penalty/final never reach here (routed above).
        if bill_type == "cycle":
            from apps.billing import midperiod

            data = replace(
                data,
                split_segments=midperiod.gather_split(
                    scope.account,
                    period_start=period_start,
                    period_end=period_end,
                    cycle_days=days,
                    scope_services=scope_services,
                    # CR-156-BRC10 — an INTERIM bill (typed `cycle`) states
                    # each part over its own cycle; `None` everywhere else.
                    cycle_days_for=price_split_cycle_days,
                    # 🔒 `DEF-BIL-10067` (PO 2026-10-12) — the one-time bill's
                    # step-2 reading reaches the PARTS too. The whole-period
                    # gather above took it (`DEF-BIL-8300`) and the split did
                    # not, so a window crossing a rate change previewed on the
                    # saved reads alone and never moved as the clerk typed
                    # 4.6 over 2.9. `None` on every other caller — the draft
                    # included, which prices only on readings Meter Reads saved.
                    keyed_reads=keyed_reads,
                ),
            )
        ready.append(data)
        unmeasured = tuple(
            reading.service_code
            for reading in data.readings
            if reading.consumption is None and reading.service_code
        )
        decisions.extend(runs._decisions_for(data, unmeasured))

    return runs.PreparedRun(
        cycle_id="",
        period_start=period_start,
        period_end=period_end,
        service_date=service_date,
        cycle_days=days,
        scope_services=scope_services,
        ready=tuple(ready),
        blocked=tuple(blocked),
        decisions=tuple(decisions),
        silent=tuple(silent),
    )


def calculate_single_bill(
    prepared: runs.PreparedRun,
    *,
    bill_run: models.BillRun,
    bill_type: str = "cycle",
) -> models.Invoice:
    """Phase 2 for ONE account: stages 1 → 6, one DRAFT bill. Same code as a run.

    `bill_run` is REQUIRED, and that is a deliberate reversal of what looks
    convenient. Stage 6 replaces an existing draft for `(tenant, account,
    bill_run)` — which is exactly right per run, and wrong with `bill_run=None`:
    an interim bill for July and a back-bill for January–June would both key on
    NULL, so drafting the second would DELETE the first. The invoice column is
    nullable and the correct value is still a row.

    Reported rather than worked around: `bill_runs.cycle_id` is NOT NULL and
    `runs.create_run` takes no `bill_type`, so an ad-hoc run row is typed
    `cycle` while the invoice it produces is typed `final`/`backbill`/`penalty`,
    and r10 #7's single-account SCOPE has no column at all. Both belong to the
    lane that owns `models.py` / `runs.py`.
    """
    if not prepared.ready:
        # ⚠ **A SILENT ACCOUNT IS NAMED HERE (`BR-BIL-1025`), NOT REPORTED AS A
        # MISSING REASON.** Until 2026-09-01 an empty `ready` with an empty
        # `blocked` could only be a bug, so this said so. It can now be an
        # ordinary, correct state — an owner's account at an address he occupies
        # himself covers nothing and has nothing to charge — and the run files
        # it in `prepared.silent`. Reading only `blocked` would tell a clerk
        # *"no reason was recorded, which is itself a bug"* about a state the PO
        # ruled correct on 2026-08-31.
        problem = (prepared.blocked or prepared.silent or (None,))[0]
        raise BillingRuleError(
            "this account could not be gathered, so there is nothing to bill: "
            + (problem.detail if problem else "no reason was recorded, which is itself a bug.")
        )
    data = prepared.ready[0]
    invoice = runs.calculate_account(
        data,
        bill_run=bill_run,
        service_date=prepared.service_date,
        bill_type=bill_type,
    )
    if invoice is None:
        # ⚠ **IN SINGLE MODE, NOTHING TO BILL IS A REFUSAL AND NOT AN OUTCOME.**
        # `BR-BIL-1024` suppresses the DOCUMENT, and in a batch that is silence:
        # nobody asked for that account by name. Here somebody did — a clerk
        # pressed a button, and a rebill, a final bill and an interim bill all
        # arrive through this function — so answering `None` would hand the
        # caller a success it cannot render and would let `corrections` write a
        # credit note against a rebill that does not exist. Exception (5) below
        # already states the posture: single mode has one account and one
        # waiting clerk, and a refusal raises.
        raise BillingRuleError(
            f"account {data.account_no} priced no lines for "
            f"{prepared.period_start} to {prepared.period_end}, so there is no bill to "
            "produce. A bill with no lines is not a $0.00 document (BR-BIL-1024); in a "
            "cycle run this account is simply quiet, but a bill asked for by name has to "
            "say why nothing came back."
        )
    return invoice


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-012@f0a3c21 (the four billing sources — B2 §2 + Addendum r10 ·
#         EP-BIL-03-bill-types.md · 07-billing/02-business-rules.md ·
#         07-billing/08-worked-examples.md)
# generated: 2026-08-11 by story-coder (W3/W5 bill-types lane — US-BIL-011..014)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — S30's One-time tab is unbuilt; the endpoint belongs with it) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · tests/test_us_bil_012_single.py
# exceptions: (1) NO FREE-TYPED AMOUNTS ANYWHERE, and the enforcement is
#         STRUCTURAL rather than a validation: no function in this module takes
#         an amount, a description or a line, so there is nothing to reject.
#         BR-BIL-020 supersedes the prototype's editable line inputs and its
#         "+ Add line" button, in writing (US-BIL-012 TC-4). tc4 asserts it by
#         introspecting this module's signatures — a check that survives a
#         refactor, where a rejection message would not.
#         (2) `bill_run` is REQUIRED on calculate, not optional. Stage 6 keys
#         draft replacement on (tenant, account, bill_run); with None, two
#         different ad-hoc bills for one account collide and the second silently
#         deletes the first.
#         (3) Reaches `runs._readings_for` and `runs._decisions_for` — private
#         helpers of a module in the same package. Deliberate: a second call
#         site for metering's reads seam would be a second place to decide what
#         a missing read means (BR-BIL-015) and whether a unitless quantity may
#         be billed (rule 3). One implementation, one behaviour.
#         (4) THREE THINGS THE PROTOTYPE HAS AND THIS DOES NOT, each REPORTED
#         and none invented: the step-1 **bill date** (which DOES have a column
#         since migration 0011 / OQ-122 closed — this entry point simply does
#         not take one yet, and that is a gap rather than an absence), the
#         **"Deposit invoice"** kind (no story owns it — hard-won law 8), and
#         the run row's single-account **scope** (r10 #7 promises it; no column
#         carries it).
#         (5) A refusal here RAISES rather than joining a blocked list. Single
#         mode has one account and one waiting clerk; `prepare_run`'s both-halves
#         shape exists to stop one bad account hiding 493 others, and there are
#         no others here.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
