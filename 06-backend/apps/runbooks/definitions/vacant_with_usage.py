# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-030 (EP-RBS-05) — CR-075 wave S: runbook 18, *Vacant premises
#           with usage* — six read steps over every premises with a meter, and
#           the only runbook in this wave whose output is a dollar figure.
# Rules:    BR-RBS-002 · BR-RBS-009 · BR-RBS-010 · BR-RBS-011 · BR-RBS-012 (the
#           sample guard is absolute) · BR-RBS-019 · BR-RBS-020 · BR-RBS-021 ·
#           BR-RBS-022 (a work item is the ENGINE's act) · BR-RBS-023 ·
#           BR-RBS-035 · BR-RBS-039 · BR-CUS-070 (the address as given is never
#           overwritten; only the resolved ids join) · CLAUDE.md hard rule 2 ·
#           hard rule 3 · hard rule 8 (an address lives on `premises`) ·
#           B14 rules 31, 32, 33
# Tests:    06-backend/tests/test_us_rbs_030_vacant_with_usage.py ·
#           06-backend/tests/test_rbs_check_runbooks_pg.py (PostgreSQL only)
# Impacts:  apps/runbooks/definitions/__init__.py · apps/runbooks/seams/
#           metering_seam.py · apps/runbooks/seams/customers_seam.py ·
#           apps/runbooks/seams/billing_seam.py ·
#           04-docs/05-modules/17-runbooks/11-catalogue/RB-118-vacant-premises-with-usage.md
# ───────────────────────────────────────────────────────
"""Runbook 18 — **Vacant premises with usage**.

*Where is water being used with nobody billed for it — and where is an account
being billed on a meter that never moves?* `RB-118`'s own sentence: **this is
revenue, not hours.**

⚠ **THE ONLY RUNBOOK IN THIS WAVE WHOSE OUTPUT IS A DOLLAR FIGURE**, and the
card marks it with a tilde for a reason: *"The revenue figure is an estimate at a
named plan (Residential base + tier 1), and the screen says ~."* Every number
here that is an estimate is drawn as one.

THE TWO HALVES ARE MIRRORS AND BOTH ARE REVENUE
-------------------------------------------------
`RB-118`'s design note: *"A vacant premise using 9,000 gallons is either an
unbilled occupant, a builder, or a leak, and all three are worth a visit. The
stopped-meter half is the mirror: revenue being lost on an account that looks
fine."* So the runbook walks every premises with a meter and finds both.

WHAT THE LIKELY CAUSE IS BUILT FROM, BECAUSE THE CARD FIXES FOUR WORDS
-----------------------------------------------------------------------
The card allows exactly four: **Occupant unbilled · Construction · Possible leak
· Stopped meter**. Nothing in this product knows which of the first three is
true, so the cause is a JUDGMENT and its evidence is stated on the row:

* **never had an account at all** → *Construction*. A premises the utility has
  never billed anyone at, with water moving through it, is a site.
* **had one, and is now using at least half what it used when it was occupied**
  → *Occupant unbilled*. Somebody is living the way the last customer did.
* **had one, and is using far less than that** → *Possible leak*. A trickle
  nobody is home for.
* an active account whose meter has not moved → *Stopped meter*.

⚠ **THE COMPARISON IS THE PREMISES' OWN HISTORY AND NEVER A FLEET AVERAGE**,
which is `RBR-09`'s reasoning one object up: a farm and a flat are both normal at
wildly different volumes. ⚠ **AND WHERE THERE IS NO OCCUPIED HISTORY TO COMPARE
AGAINST, THE ROW SAYS SO** — it reads *Occupant unbilled* with *"no earlier
usage to compare"* beside it, and the count of such rows is reported, because a
guess presented as a measurement is worse than a guess that says what it is.

WHAT THIS RUNBOOK CANNOT SEE, EACH WITH ITS NUMBER
----------------------------------------------------
1. **An application nobody has resolved to a premises cannot be matched.**
   `BR-CUS-070` keeps the address as the applicant typed it and never overwrites
   it; only the RESOLVED ids join to anything. Step 4 reports how many
   applications it could not place rather than treating them as absent.
2. **A premises with no reads at all is not vacant-with-usage and is not
   evidence of anything.** It is counted as *not measured* rather than folded
   into either half.
3. **The estimate is priced at what the LAST occupant of that premises actually
   paid per unit** — the usage lines' amount over their quantity on their most
   recent issued bill — and a premises whose last account never billed cannot be
   priced at all. Its row reads `—` and never `$0.00`, and the tile says how
   many could not be priced. The card's *Estimate revenue at: Residential base +
   tier 1* is a rate CARD this Check may not read: pricing a plan is rating's
   act, and a Check holds no writer and no engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from apps.runbooks import models
from apps.runbooks.contract import (
    MODE_PER_RECORD,
    MODE_SET,
    PARAM_ENUM,
    PARAM_INTEGER,
    PARAM_REF_SETTING,
    PARAM_TOGGLE,
    PARAM_WINDOW,
    Block,
    Guard,
    Parameter,
    RunbookDefinition,
    Step,
    SubjectRef,
)
from apps.runbooks.seams import billing_seam, customers_seam, metering_seam, tenancy_seam

KEY = "vacant_with_usage"

ZERO = Decimal("0")

# ── the six steps, in the card's own order ────────────────────────────────

STEP_VACANT = "find_vacant_premises_with_a_meter"
STEP_USAGE = "find_usage_on_them"
STEP_STOPPED = "find_active_accounts_whose_meter_stopped"
STEP_PENDING = "check_for_a_move_in_already_pending"
STEP_ESTIMATE = "estimate_what_is_going_unbilled"
STEP_CAUSE = "group_by_likely_cause"

STEP_LABELS = {
    STEP_VACANT: "Find vacant premises with a meter",
    STEP_USAGE: "Find usage on them",
    STEP_STOPPED: "Find active accounts whose meter stopped",
    STEP_PENDING: "Check for a move-in already pending",
    STEP_ESTIMATE: "Estimate what is going unbilled",
    STEP_CAUSE: "Group by likely cause",
}

# ── the four causes the card allows, and nothing else ─────────────────────

CAUSE_OCCUPANT = "occupant_unbilled"
CAUSE_CONSTRUCTION = "construction"
CAUSE_LEAK = "possible_leak"
CAUSE_STOPPED = "stopped_meter"
CAUSE_PENDING = "move_in_pending"
CAUSE_NOTHING = "nothing_to_report"

CAUSE_LABELS = {
    CAUSE_OCCUPANT: "Occupant unbilled",
    CAUSE_CONSTRUCTION: "Construction",
    CAUSE_LEAK: "Possible leak",
    CAUSE_STOPPED: "Stopped meter",
    CAUSE_PENDING: "Move-in pending",
    CAUSE_NOTHING: "Nothing to report",
}

#: The fix beside each — `BR-RBS-011`, and every route is one this product
#: mounts (verified against `07-frontend/src/routing/`, 2026-09-07).
FIX_ACCOUNTS = "accounts"
FIX_PREMISES = "premises"
FIX_ASSETS = "assets"
FIX_REQUESTS = "requests"

FIX_FOR_CAUSE = {
    CAUSE_OCCUPANT: (FIX_ACCOUNTS, "Start account →"),
    CAUSE_CONSTRUCTION: (FIX_ACCOUNTS, "Bill the builder →"),
    CAUSE_LEAK: (FIX_PREMISES, "Inspect →"),
    CAUSE_STOPPED: (FIX_ASSETS, "Order a test →"),
    CAUSE_PENDING: (FIX_REQUESTS, "Open the application →"),
    CAUSE_NOTHING: (FIX_PREMISES, "Open the premises →"),
}

#: A premises using at least this share of its OWN last-occupied usage reads as
#: an occupant rather than as a leak. ⚠ **A JUDGMENT, RECORDED IN THE DECISION
#: LOG** — the card fixes four words and names no rule for choosing between
#: them, and half is the point at which *"somebody is living here"* stops being
#: the simpler explanation. It is not a parameter because a tenant asked for no
#: such knob; if one ever does, this is the number it sets.
OCCUPANT_SHARE = Decimal("0.5")


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
    return str(amount.quantize(Decimal("0.0001")))


def _window_start(ctx):
    """The first day of the window — from the tenant's OWN today (`BR-TEN-043`)."""
    return tenancy_seam.today() - timedelta(days=int(ctx.params.get("window_days") or 90))


# ── the two reads every step shares ───────────────────────────────────────


def _census(ctx) -> dict[str, Any]:
    cached = ctx.set_results.get("_census")
    if cached is None:
        cached = metering_seam.premises_meter_census(include_sample=True)
        ctx.set_results["_census"] = cached
    return cached


def _history(ctx) -> dict[str, list[dict[str, Any]]]:
    """Every meter's reads inside the window, keyed by PREMISES.

    ⚠ **ONE READ FOR THE ESTATE.** `NFR-3`: a per-premises walk is correct at
    3,000 accounts and 13× short at 40,000 (`DEF-PAY-4221`'s shape).
    """
    cached = ctx.set_results.get("_history")
    if cached is None:
        rows = metering_seam.meter_read_history(
            service_code=str(ctx.params.get("service") or "") or None,
            since=_window_start(ctx),
            limit_per_meter=24,
        )
        grouped: dict[str, list[dict[str, Any]]] = {}
        for meter in rows:
            grouped.setdefault(str(meter.get("premises_id") or ""), []).append(meter)
        cached = grouped
        ctx.set_results["_history"] = cached
    return cached


def _used(meters: list[dict[str, Any]]) -> tuple[Decimal, str, int]:
    """What these meters measured in the window, WITH the unit (hard rule 3).

    ⚠ **A `None` CONSUMPTION IS NOT A ZERO** — it is a read with no prior, or an
    estimate, and adding it in as nought would make an occupied house look
    vacant. The count of unmeasured periods travels so *"used nothing"* and
    *"nobody measured"* can be told apart.
    """
    total = ZERO
    unit = ""
    unmeasured = 0
    for meter in meters:
        for read in meter.get("reads") or []:
            quantity = _decimal(read.get("consumption"))
            if quantity is None:
                unmeasured += 1
                continue
            unit = unit or str(read.get("unit") or "")
            total += quantity
    return total, unit, unmeasured


# ── step 1 · vacant premises with a meter ─────────────────────────────────


def step_find_vacant_premises_with_a_meter(ctx, subjects) -> dict[str, Any]:
    """1 · No active account against the unit.

    ⚠ **VACANT IS *NO ACTIVE ACCOUNT*, WHICH IS THE CARD'S OWN SETTINGS-OWNED
    DEFINITION**, and `customers` decides what *active* means: `accounts_for_units`
    answers with the OCCUPYING behaviour classes (`BR-CUS-055`), so a vacation
    hold still counts as occupied and a closed account does not. A runbook that
    re-derived that boundary would be a second copy of a rule whose owner is one
    module away.
    """
    census = _census(ctx)
    by_id = {str(one["premises_id"]): one for one in (census.get("premises") or [])}
    unit_ids = [
        unit_id
        for subject in subjects
        for unit_id in (by_id.get(str(subject.subject_id), {}).get("unit_ids") or [])
    ]
    occupied_units = customers_seam.accounts_for_units(unit_ids)
    vacant: dict[str, dict[str, Any]] = {}
    occupied: dict[str, dict[str, Any]] = {}
    no_meter = 0
    for subject in subjects:
        premises = by_id.get(str(subject.subject_id)) or {}
        if not premises.get("meters"):
            no_meter += 1
            continue
        holders = [
            occupied_units[str(unit_id)]
            for unit_id in premises.get("unit_ids") or []
            if str(unit_id) in occupied_units
        ]
        if holders:
            occupied[str(subject.subject_id)] = {"accounts": holders}
        else:
            vacant[str(subject.subject_id)] = {"units": premises.get("unit_ids") or []}
    return _StepResult(
        found={"vacant": vacant, "occupied": occupied},
        checked={
            "premises_checked": len(subjects),
            "premises_with_no_meter": no_meter,
            "vacant_with_a_meter": len(vacant),
            "occupied_with_a_meter": len(occupied),
            "vacant_means": "no account of an occupying status against any of its units",
        },
    ).as_dict()


# ── step 2 · usage on them ────────────────────────────────────────────────


def _days_between(first: str, last: str) -> int:
    from datetime import date as _date

    try:
        return (_date.fromisoformat(last[:10]) - _date.fromisoformat(first[:10])).days
    except (TypeError, ValueError):
        return 0


def _occupied_normal(ctx) -> dict[str, Decimal]:
    """WHAT EACH PREMISES USED WHILE IT WAS OCCUPIED, over a window's length.

    ⚠ **THE COMPARISON IS THE PREMISES' OWN HISTORY AND NEVER A FLEET AVERAGE**
    — `RBR-09`'s reasoning one object up: a farm and a flat are both normal at
    wildly different volumes, so *"is somebody living here"* can only be asked
    against what living here looked like.

    It reads the meters' WHOLE history rather than the window's, because the
    occupied months are by definition before the account closed. That is a
    second estate-wide read, made ONCE per run in step 2 and stated rather than
    hidden.

    A premises is absent from the map where there are fewer than two reads
    before the closure — one read is a register value, not a period — and the
    row that has no entry says *"no earlier usage to compare"* rather than
    guessing.
    """
    cached = ctx.set_results.get("_occupied_normal")
    if cached is not None:
        return {key: Decimal(value) for key, value in cached.items()}

    facts = ctx.set_results.get("_last_account_facts") or {}
    window = Decimal(int(ctx.params.get("window_days") or 90))
    everything = metering_seam.meter_read_history(
        service_code=str(ctx.params.get("service") or "") or None,
        since=None,
        limit_per_meter=36,
    )
    by_premises: dict[str, list[dict[str, Any]]] = {}
    for meter in everything:
        by_premises.setdefault(str(meter.get("premises_id") or ""), []).append(meter)

    out: dict[str, str] = {}
    for premises_id, who in facts.items():
        closed_on = str(who.get("closed_on") or "")
        if not closed_on:
            continue
        total = ZERO
        days = 0
        for meter in by_premises.get(premises_id) or []:
            measured = [
                one
                for one in (meter.get("reads") or [])
                if str(one.get("on") or "")
                and str(one["on"]) <= closed_on
                and _decimal(one.get("consumption")) is not None
            ]
            if len(measured) < 2:
                continue
            total += sum((_decimal(one["consumption"]) or ZERO) for one in measured)
            days = max(days, _days_between(str(measured[0]["on"]), str(measured[-1]["on"])))
        if days > 0 and total > ZERO:
            out[premises_id] = str((total / Decimal(days) * window).quantize(Decimal("0.0001")))
    ctx.set_results["_occupied_normal"] = out
    return {key: Decimal(value) for key, value in out.items()}


def step_find_usage_on_them(ctx, subjects) -> dict[str, Any]:
    """2 · Over the threshold inside the window."""
    over = _decimal(ctx.params.get("usage_means_more_than")) or Decimal("500")
    history = _history(ctx)
    vacant = ((ctx.set_results.get(STEP_VACANT) or {}).get("found") or {}).get("vacant") or {}
    found: dict[str, dict[str, Any]] = {}
    unmeasured_premises = 0
    for premises_id in vacant:
        meters = history.get(premises_id) or []
        if not meters:
            unmeasured_premises += 1
            continue
        total, unit, unmeasured = _used(meters)
        if total > over:
            found[premises_id] = {
                "used": str(total),
                "unit": unit,
                "periods_with_no_reading": unmeasured,
            }
    return _StepResult(
        found={"using": found},
        checked={
            "usage_means_more_than": str(over),
            "vacant_and_using": len(found),
            "vacant_with_no_reads_at_all": unmeasured_premises,
            # Computed here, ONCE, so the per-record step never makes an
            # estate-wide read per premises.
            "premises_with_an_occupied_history_to_compare": len(_occupied_normal(ctx)),
        },
    ).as_dict()


# ── step 3 · the mirror ───────────────────────────────────────────────────


def step_find_active_accounts_whose_meter_stopped(ctx, subjects) -> dict[str, Any]:
    """3 · Zero for three consecutive reads, on an OCCUPIED premises.

    ⚠ **THE MIRROR OF STEP 2, AND IT IS WHERE THE MONEY QUIETLY GOES.** An
    account that looks fine, bills every month, and is being charged base only
    because its meter has not moved. `RB-118`'s own example row is
    *31 Bell Ave · Active · Nunes, R. · 0 · — · Stopped meter · billed base
    only*.
    """
    needed = int(ctx.params.get("stopped_means") or 3)
    history = _history(ctx)
    occupied = ((ctx.set_results.get(STEP_VACANT) or {}).get("found") or {}).get("occupied") or {}
    found: dict[str, dict[str, Any]] = {}
    for premises_id in occupied:
        for meter in history.get(premises_id) or []:
            run = 0
            for read in meter.get("reads") or []:
                quantity = _decimal(read.get("consumption"))
                if quantity is not None and quantity == ZERO:
                    run += 1
                elif quantity is not None:
                    run = 0
            if run >= needed:
                found[premises_id] = {
                    "asset_no": meter.get("asset_no"),
                    "zero_reads": run,
                }
                break
    return _StepResult(
        found={"stopped": found},
        checked={"stopped_means_zero_reads": needed, "meters_stopped": len(found)},
    ).as_dict()


# ── step 4 · already somebody's job ───────────────────────────────────────


def step_check_for_a_move_in_already_pending(ctx, subjects) -> dict[str, Any]:
    """4 · Someone applied; this is not a finding.

    ⚠ **COUNTED BUT NOT LISTED**, which the card closed OUT OF SCOPE in those
    words: *"they are already somebody's job."* Listing them would put the same
    work on two desks and teach a clerk that this list contains things they do
    not need to do.
    """
    pending = customers_seam.pending_move_ins()
    unresolved = 0
    for one in pending.pop("_applications_not_resolved_to_a_premises", []) or []:
        unresolved = int(one.get("count") or 0)
    using = ((ctx.set_results.get(STEP_USAGE) or {}).get("found") or {}).get("using") or {}
    overlapping = sorted(set(pending) & set(using))
    return _StepResult(
        found={"pending": {one: pending[one] for one in overlapping}},
        checked={
            "applications_in_flight": len(pending),
            "of_those_on_a_premises_this_run_found": len(overlapping),
            # Hard-won law 7 — `BR-CUS-070` keeps the typed address and only the
            # RESOLVED ids join, so an unresolved application cannot be matched.
            "applications_not_resolved_to_a_premises": unresolved,
        },
    ).as_dict()


# ── step 5 · the money ────────────────────────────────────────────────────


def _price_per_unit(account_id: Any, service: str) -> Decimal | None:
    """What that account last PAID per unit — the same method runbook 5 uses.

    `None` where the account never billed, where no usage line names the
    service, or where the quantity is zero. **Never `0.0000`**: an unknown price
    is not a free one.
    """
    if not account_id:
        return None
    bills = billing_seam.issued_bills_for_account(account_id, limit=1)
    if not bills:
        return None
    amount = quantity = ZERO
    for line in bills[0].get("lines") or []:
        if str(line.get("kind")) != "usage":
            continue
        if service and str(line.get("service") or "") != service:
            continue
        this = _decimal(line.get("quantity"))
        if this is None or this <= ZERO:
            continue
        amount += _decimal(line.get("amount")) or ZERO
        quantity += this
    if quantity <= ZERO:
        return None
    return amount / quantity


def step_estimate_what_is_going_unbilled(ctx, subjects) -> dict[str, Any]:
    """5 · Usage priced at what the premises' LAST occupant actually paid.

    ⚠ **THE CARD NAMES A PLAN AND THIS CHECK MAY NOT READ ONE.** *Estimate
    revenue at: Residential base + tier 1* is a rate card; pricing a plan is
    rating's act through billing's engine, and a Check holds no writer and no
    engine. What it CAN do is measure — the amount over the quantity on the last
    occupant's own most recent issued bill — so the figure is a price this
    customer was actually charged rather than a tariff this runbook interpreted.

    ⚠ **AND IT IS AN ESTIMATE, DRAWN AS ONE.** The card's tile reads `~$1,940`
    with a tilde and this one does too. A premises whose last account never
    billed reads `—`, never `$0.00`.
    """
    history = _history(ctx)
    using = ((ctx.set_results.get(STEP_USAGE) or {}).get("found") or {}).get("using") or {}
    window = int(ctx.params.get("window_days") or 90)
    service = str(ctx.params.get("service") or "")
    priced: dict[str, dict[str, Any]] = {}
    unpriced = 0
    for premises_id, usage in using.items():
        last = (ctx.set_results.get("_last_account") or {}).get(premises_id)
        price = _price_per_unit(last, service)
        if price is None:
            unpriced += 1
            priced[premises_id] = {"per_month": None, "price_per_unit": None}
            continue
        used = _decimal(usage.get("used")) or ZERO
        # Per MONTH, because the tile and the column both say *a month* and the
        # window is 90 days. 30 days is the month this arithmetic uses and it is
        # named rather than assumed.
        per_month = (used * price) / Decimal(window) * Decimal(30)
        priced[premises_id] = {
            "per_month": _stored(per_month),
            "price_per_unit": _stored(price),
        }
    return _StepResult(
        found={"estimate": priced},
        checked={
            "premises_priced": len(priced) - unpriced,
            "premises_that_could_not_be_priced": unpriced,
            "priced_at": "what the last occupant of that premises last paid per unit",
            "month_is_days": 30,
            "window_days": window,
        },
    ).as_dict()


# ── step 6 · the cause, per premises ──────────────────────────────────────


def step_group_by_likely_cause(ctx, subject) -> dict[str, Any]:
    """6 · Occupant unbilled · construction · leak · stuck meter.

    ⚠ **THE ONLY PER-RECORD STEP** — one premises, one savepoint (hard-won law
    14), one row on the screen.
    """
    premises_id = str(subject.subject_id)
    using = ((ctx.set_results.get(STEP_USAGE) or {}).get("found") or {}).get("using") or {}
    stopped = ((ctx.set_results.get(STEP_STOPPED) or {}).get("found") or {}).get("stopped") or {}
    pending = ((ctx.set_results.get(STEP_PENDING) or {}).get("found") or {}).get("pending") or {}
    estimate = ((ctx.set_results.get(STEP_ESTIMATE) or {}).get("found") or {}).get("estimate") or {}
    facts = (ctx.set_results.get("_premises") or {}).get(premises_id) or {}
    last = (ctx.set_results.get("_last_account_facts") or {}).get(premises_id) or {}

    cause = CAUSE_NOTHING
    detail = ""
    if premises_id in pending:
        cause = CAUSE_PENDING
        detail = "Somebody has already applied."
    elif premises_id in using:
        usage = using[premises_id]
        normal = _occupied_normal(ctx).get(premises_id)
        used = _decimal(usage.get("used")) or ZERO
        if not last:
            cause = CAUSE_CONSTRUCTION
            detail = "Nobody has ever had an account here."
        elif normal is None or normal <= ZERO:
            cause = CAUSE_OCCUPANT
            detail = "No earlier usage to compare."
        elif used >= normal * OCCUPANT_SHARE:
            cause = CAUSE_OCCUPANT
            detail = f"Using {_share(used, normal)} of what the last account used."
        else:
            cause = CAUSE_LEAK
            detail = f"Using {_share(used, normal)} of what the last account used."
    elif premises_id in stopped:
        cause = CAUSE_STOPPED
        detail = (
            f"{stopped[premises_id]['zero_reads']} zero reads on "
            f"{stopped[premises_id]['asset_no']} · billed base only."
        )

    route, label = FIX_FOR_CAUSE[cause]
    money = (estimate.get(premises_id) or {}).get("per_month")
    return {
        "outcome": cause,
        "reason": f"{CAUSE_LABELS[cause]}. {detail}".strip(),
        "decided_by_rule": (
            "A vacant premises is one with no occupying account against any of its units"
        ),
        "fix_route": route,
        "data": {
            # B14 rule 31 — the premises NUMBER or its address, never the id.
            "label": facts.get("label") or "",
            "fix_label": label,
            "cause": cause,
            "used": (using.get(premises_id) or {}).get("used"),
            "unit": (using.get(premises_id) or {}).get("unit"),
            "per_month": money,
            "last_account": last.get("label") or last.get("account_no"),
            "last_closed_on": last.get("closed_on"),
        },
    }


def _share(used: Decimal, normal: Decimal) -> str:
    """*38%* — a percentage a clerk reads, at two decimals' worth of meaning."""
    if normal <= ZERO:
        return "—"
    return f"{(used / normal * Decimal(100)).quantize(Decimal('1'))}%"


# ── the report ────────────────────────────────────────────────────────────


def report(view) -> list[Block]:
    """`RB-118`'s own blocks — **KPIs · Records · Action · Downloads** — plus the
    verdict the header consumes.

    ⚠ **DEFAULT SORT IS ESTIMATED REVENUE**, which is the card's own note: *"so
    the unbilled occupant is above the leak."* A premises that could not be
    priced sorts after every priced one rather than among the zeros.
    """
    currency = str(view.set_results.get("_currency") or "")
    findings = [
        record
        for record in view.records
        if record.outcome not in (CAUSE_NOTHING, CAUSE_PENDING)
    ]
    by_cause: dict[str, int] = {}
    for record in view.records:
        by_cause[record.outcome] = by_cause.get(record.outcome, 0) + 1

    vacant_using = [one for one in findings if one.outcome != CAUSE_STOPPED]
    total = sum(
        (Decimal(one.data["per_month"]) for one in findings if one.data.get("per_month")),
        ZERO,
    )
    unpriced = len([one for one in vacant_using if not one.data.get("per_month")])
    ranked = sorted(
        findings,
        key=lambda record: (
            Decimal(record.data["per_month"]) if record.data.get("per_month") else Decimal("-1")
        ),
        reverse=True,
    )

    return [
        Block(
            block="verdict",
            payload={
                "word": "Revenue at risk" if findings else "Nothing found",
                "tone": "warning" if findings else "success",
                "count": (
                    f"{len(vacant_using)} premises using water with nobody billed · "
                    f"{by_cause.get(CAUSE_STOPPED, 0)} stopped meters."
                ),
                "detail": (
                    f"{len(view.records)} premises checked · "
                    f"{by_cause.get(CAUSE_PENDING, 0)} already have an application in flight."
                ),
            },
        ),
        Block(
            block="kpis",
            payload={
                "tiles": [
                    {
                        "id": "vacant_with_usage",
                        "label": "Vacant with usage",
                        "value": {"kind": "text", "text": str(len(vacant_using))},
                    },
                    {
                        "id": "unbilled",
                        "label": "Unbilled per month",
                        # ⚠ **AN ESTIMATE, AND THE TILDE IS THE CARD'S** —
                        # `~$1,940`. Where nothing could be priced it reads `—`
                        # rather than `0.00`, because a money tile reading zero
                        # over a list nobody could price is hard-won law 7's
                        # *zero over a scope it silently excludes*.
                        "value": (
                            {
                                "kind": "money",
                                "amount": _stored(total),
                                "currency": currency,
                            }
                            if vacant_using and unpriced < len(vacant_using)
                            else {"kind": "text", "text": "—"}
                        ),
                        # `priced`, never `posting`: nothing here was posted.
                        "basis": "priced",
                        "detail": (
                            f"Estimated · {unpriced} could not be priced"
                            if unpriced
                            else "Estimated at what each last occupant paid"
                        ),
                    },
                    {
                        "id": "stopped",
                        "label": "Meter stopped",
                        "value": {
                            "kind": "text",
                            "text": str(by_cause.get(CAUSE_STOPPED, 0)),
                        },
                        "detail": "Billed base only",
                    },
                    {
                        "id": "pending",
                        "label": "Move-in pending",
                        "value": {
                            "kind": "text",
                            "text": str(by_cause.get(CAUSE_PENDING, 0)),
                        },
                        "detail": "Already somebody's job",
                    },
                ]
            },
        ),
        Block(
            block="records",
            payload={
                "columns": [
                    {"key": "premise", "label": "Premise"},
                    {"key": "last_account", "label": "Last account"},
                    {"key": "used", "label": "Used"},
                    {"key": "per_month", "label": "Est. / month", "numeric": True},
                    {"key": "cause", "label": "Likely cause"},
                    {"key": "fix", "label": "Fix"},
                ],
                "rows": [
                    {
                        "id": f"premises-{index}",
                        "cells": {
                            "premise": {
                                "kind": "text",
                                "text": str(record.data.get("label") or ""),
                            },
                            "last_account": {
                                "kind": "text",
                                "text": str(record.data.get("last_account") or "Never"),
                            },
                            "used": (
                                {
                                    "kind": "unit",
                                    "quantity": str(record.data["used"]),
                                    "unit": str(record.data.get("unit") or ""),
                                }
                                if record.data.get("used")
                                else {"kind": "text", "text": "0"}
                            ),
                            "per_month": (
                                {
                                    "kind": "money",
                                    "amount": record.data["per_month"],
                                    "currency": currency,
                                }
                                if record.data.get("per_month")
                                # ⚠ `—` ON A STOPPED METER IS THE CARD'S OWN
                                # NOTE: *"Est. / month reads — on a stopped
                                # meter."* Nothing was used, so nothing can be
                                # priced, and `$0.00` would read as *we checked
                                # and it is worth nothing*.
                                else {"kind": "text", "text": "—"}
                            ),
                            "cause": {
                                "kind": "text",
                                "text": CAUSE_LABELS.get(record.outcome, record.outcome),
                            },
                            "fix": {
                                "kind": "link",
                                "label": str(record.data.get("fix_label") or "Open →"),
                                "to": record.fix_route,
                            },
                        },
                        "meta": {
                            "decided_by_rule": record.decided_by_rule,
                            "why": record.reason,
                            "cause": record.outcome,
                        },
                    }
                    for index, record in enumerate(ranked, start=1)
                ],
                "total": len(ranked),
                "chips": [
                    {"id": "all", "label": "All", "count": len(findings)},
                ]
                + [
                    {"id": cause, "label": CAUSE_LABELS[cause], "count": by_cause[cause]}
                    for cause in (
                        CAUSE_OCCUPANT,
                        CAUSE_CONSTRUCTION,
                        CAUSE_LEAK,
                        CAUSE_STOPPED,
                    )
                    if by_cause.get(cause)
                ],
                "empty": {
                    "title": "Nothing is being used where nobody is billed.",
                    "helper": (
                        f"{len(view.records)} premises with a meter checked over "
                        f"{(view.set_results.get(STEP_ESTIMATE) or {}).get('checked', {}).get('window_days', 90)} days."
                    ),
                },
            },
        ),
        Block(
            block="action",
            payload={
                "label": "Raise work items",
                "tier": "secondary",
                "enabled": False,
                "reason": "The work list is not built yet",
            },
        ),
        Block(
            block="downloads",
            payload={
                "files": [
                    {"id": "all", "label": "All", "format": "csv"},
                    {"id": "vacant_with_usage", "label": "Vacant with usage", "format": "csv"},
                ]
            },
        ),
    ]


# ── the guard and the pinned scope ────────────────────────────────────────

SAMPLE_KEYS = "_sample_premises_ids"


def _is_sample(ctx, subject) -> bool:
    """`RB-118`'s *Never include: Sample* (`BR-TEN-057`, `BR-RBS-012`).

    A guarded premises is still PINNED and still COUNTED, so the screen can say
    how many were excluded rather than quietly showing a shorter list.
    """
    return str(subject.subject_id) in (ctx.set_results.get(SAMPLE_KEYS) or frozenset())


def resolve(ctx):
    """The pinned set: **every premises with a meter** (`BR-RBS-019`).

    ⚠ **THE COUNT ON THE SETUP SCREEN IS THIS FUNCTION'S ANSWER** — the card's
    *Checks 2,862 premises*.

    ⚠ **THE ADDRESS COMES FROM `premises` AND NOWHERE ELSE** (hard rule 8,
    `BR-MET-1161`): the label a clerk reads is the premises' own number or its
    address line, walked to rather than copied onto anything.
    """
    census = metering_seam.premises_meter_census(include_sample=True)
    ctx.set_results["_census"] = census
    rows = [one for one in (census.get("premises") or []) if one.get("meters")]
    ctx.set_results[SAMPLE_KEYS] = frozenset(
        str(one["premises_id"]) for one in rows if one.get("is_sample")
    )
    ctx.set_results["_premises"] = {str(one["premises_id"]): one for one in rows}
    ctx.set_results["_currency"] = tenancy_seam.currency()

    # WHO WAS HERE LAST, and what they used when they were — the comparison the
    # likely cause rests on. Both are read once for the whole estate.
    last_account: dict[str, str] = {}
    last_facts: dict[str, dict[str, Any]] = {}
    by_unit = customers_seam.last_closed_account_for_units(
        [unit_id for one in rows for unit_id in (one.get("unit_ids") or [])]
    )
    for one in rows:
        for unit_id in one.get("unit_ids") or []:
            closed = by_unit.get(str(unit_id))
            if closed:
                last_account[str(one["premises_id"])] = str(closed["id"])
                last_facts[str(one["premises_id"])] = closed
                break
    ctx.set_results["_last_account"] = last_account
    ctx.set_results["_last_account_facts"] = last_facts

    return [
        SubjectRef(
            subject_type="premise",
            subject_id=str(one["premises_id"]),
            label=str(one.get("label") or ""),
        )
        for one in rows
    ]


RUNBOOK = RunbookDefinition(
    key=KEY,
    name="Vacant premises with usage",
    kind=models.KIND_CHECK,
    category="premises",
    subject_type="premise",
    unit_of_work="a premises over the window",
    # The card's trigger row reads *Schedule*, and its `Runs` parameter reads
    # *Monthly*. Widening it to manual would be a wider declaration than the
    # card makes, which is a change request rather than a lane's decision.
    triggers=(models.TRIGGER_SCHEDULE,),
    tags=("Reads", "Business"),
    parameters=(
        Parameter(
            name="vacant_means",
            type=PARAM_REF_SETTING,
            label="Vacant means",
            # ⚠ DECLARED, AND NO SETTINGS ROW HOLDS IT TODAY. The card marks it
            # read-only and Settings-owned; the definition step 1 applies is
            # `customers`' own occupying-status boundary (`BR-CUS-055`), stated
            # in that step rather than invented here.
            setting_key="customers.vacant_definition",
        ),
        Parameter(
            name="service",
            type=PARAM_ENUM,
            label="Service",
            # One choice until wave `T` attaches `BR-RBS-042`'s tenant-resolved
            # `service` domain — a hand-typed catalogue here is the second copy
            # that made an eleventh service invisible on the sign-up screen.
            choices=("water",),
            default="water",
        ),
        Parameter(name="window_days", type=PARAM_WINDOW, label="Window", default=90),
        Parameter(
            name="usage_means_more_than",
            type=PARAM_INTEGER,
            label="Usage means more than",
            # The card's *500 gal in 90 days*. The unit is the METER's own —
            # the eleven parameter types have no quantity type — so it is
            # compared in each premises' unit and the unit travels on the row.
            default=500,
        ),
        Parameter(
            name="stopped_means",
            type=PARAM_INTEGER,
            label="Stopped means zero reads",
            default=3,
        ),
        Parameter(
            name="estimate_revenue_at",
            type=PARAM_ENUM,
            label="Estimate revenue at",
            # ⚠ **DECLARED AND NOT READ, AND THAT IS STATED RATHER THAN
            # HIDDEN.** The card's value is *Residential base + tier 1*, which
            # is a rate card; pricing a plan is rating's act through billing's
            # engine and a Check holds neither. Step 5 prices at what the last
            # occupant actually paid and says so on the screen.
            choices=("what_the_last_occupant_paid",),
            default="what_the_last_occupant_paid",
        ),
        Parameter(
            name="raise_work_items",
            type=PARAM_TOGGLE,
            label="Raise work items",
            default=True,
        ),
        Parameter(name="runs", type=PARAM_ENUM, label="Runs", choices=("monthly",), default="monthly"),
    ),
    guards=(Guard(key="sample", label="Never include: Sample", applies=_is_sample),),
    resolve=resolve,
    report=report,
    steps=(
        Step(key=STEP_VACANT, label=STEP_LABELS[STEP_VACANT], mode=MODE_SET, run=step_find_vacant_premises_with_a_meter),
        Step(key=STEP_USAGE, label=STEP_LABELS[STEP_USAGE], mode=MODE_SET, run=step_find_usage_on_them),
        Step(key=STEP_STOPPED, label=STEP_LABELS[STEP_STOPPED], mode=MODE_SET, run=step_find_active_accounts_whose_meter_stopped),
        Step(key=STEP_PENDING, label=STEP_LABELS[STEP_PENDING], mode=MODE_SET, run=step_check_for_a_move_in_already_pending),
        Step(key=STEP_ESTIMATE, label=STEP_LABELS[STEP_ESTIMATE], mode=MODE_SET, run=step_estimate_what_is_going_unbilled),
        # ⚠ THE ONLY PER-RECORD STEP — one premises, one savepoint, one row.
        Step(key=STEP_CAUSE, label=STEP_LABELS[STEP_CAUSE], mode=MODE_PER_RECORD, run=step_group_by_likely_cause),
    ),
)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-030 (EP-RBS-05; CR-075 wave S)
# generated: 2026-09-07 by the CR-075 wave S build lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint — every runbooks route is a GET and POST /runbooks/{key}/runs is wave L) E=n/a(no screen — RBS-004 and RBS-006 render any runbook; RB-020) F✔ G✔ H=n/a(no 🔒 path: this composes no idempotency key, touches no rating math and posts no ledger line)
# gates: pytest tests/test_us_rbs_030_vacant_with_usage.py · pytest tests/test_us_rbs_015_conformance.py · G115 · G20
# exceptions: the *likely cause* is a JUDGMENT and its evidence is on the row — never an account → Construction; using at least half of what the premises used when it was occupied → Occupant unbilled; far less → Possible leak; and where there is no occupied history to compare, the row reads *Occupant unbilled · no earlier usage to compare* and the count travels · `estimate_revenue_at` is declared and NOT read: the card's *Residential base + tier 1* is a rate card and pricing a plan is rating's act, so step 5 prices at what the last occupant actually paid · an application nobody has resolved to a premises cannot be matched (`BR-CUS-070`) and is counted · `Est. / month` reads `—` on a stopped meter, which is the card's own note
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
