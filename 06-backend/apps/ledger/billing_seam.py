# ── Trace ──────────────────────────────────────────────
# Epics:    EP-LED-06 (cost-of-service capture — the BILLED half of the
#           bought-vs-billed reconciliation)
#           Screens: S74
#           NOTE: no US-ID is cited here ON PURPOSE — G10 reads a Trace-header
#           US-ID as "this file ships that story's TCs", and this file ships
#           one cross-module READ, not a story. Same precedent as
#           apps/ledger/tenancy_seam.py, apps/payments/billing_seam.py and
#           apps/billing/rating_seam.py.
# Rules:    BR-TEN-013 (a module NEVER touches another module's ORM; a
#           cross-module read resolves the owner's published callable) ·
#           BR-LED-032 (the unaccounted-for figure is a VOLUME ratio, both
#           sides in the same unit) · BR-LED-033 (units must match or the
#           figure is ABSENT by name) · BR-REP-002 (a report never recomputes
#           money) · CLAUDE.md rule 1 (tenant scoping — inherited from
#           billing's own tenant-scoped read, never re-implemented here) ·
#           rule 3 (a quantity travels with its unit)
# Tests:    06-backend/tests/test_us_led_020_reconciliation.py
# Impacts:  apps/ledger/cost_reconciliation.py (its only caller)
# ───────────────────────────────────────────────────────
"""ledger → billing SEAM: **how much did we actually BILL for this service?**

HUMAN-OWNED · HUMAN-REVIEW-PENDING — a wrong answer here is a wrong loss
percentage on the headline figure of this feature. AI-authored 2026-08-15 under
the PO ruling of 2026-08-09. **A row in 12-governance/09-human-review-ledger.md
is OWED** — that directory is the Product Owner's to write, so the lane report
names this file and the row it needs.

════════════════════════════════════════════════════════════════════════════
WHY THIS FILE EXISTS AT ALL, AND WHY IT IS NOT AN IMPORT
════════════════════════════════════════════════════════════════════════════
`04-docs/05-modules/09-ledger/01-overview.md` v5.1 records a law about the
ledger's read model: *"a report never recomputes money: no import of billing,
payments or customers exists in either file, and a test asserts that on the
source."* The billed VOLUME is not money — but the assertion is on the IMPORT,
not on the value, and the ledger field map's D-13 routes this read accordingly:
*"a published billing SELECTOR SEAM (the `apps/billing/selectors` shape G20
harvests), never a new import."*

So this module resolves billing's published callables **by name, at call time**.
**No cross-module MODEL import exists here**, and none exists in
`cost_reconciliation.py` either — G6 rule 4 would fail the merge if one did, and
`tests/test_us_led_020_reconciliation.py` asserts the absence on the parsed
source of both files as well.

⚠ That sentence is deliberately phrased WITHOUT the literal import statement it
forbids. Written the obvious way — quoting the banned line inside the prose that
bans it — this docstring FAILED G6 on its first run: the gate's grep is a
line-by-line scan that skips `#` comments and does not know a docstring from
code, so the file was reported as importing billing while importing nothing at
all. A false positive on a boundary gate is not a nuisance to be silenced; it is
a lane learning to widen the gate. The prose moved instead. (Measured, not
reasoned: `G6 forbidden FAIL — apps/ledger/billing_seam.py:41: imports
apps.billing.models from apps/ledger/`.)

════════════════════════════════════════════════════════════════════════════
THE PREFERRED READ, AND THE FALLBACK THAT KEEPS THE LOOP CLOSED
════════════════════════════════════════════════════════════════════════════
The contract this seam asks billing for is stated once, below, as
`BILLED_VOLUME_READ`. **Billing does not publish it today.** Rather than leave
the whole reconciliation dark — hard-won law 2, *built is not wired* — the seam
falls back to billing's OWN published tenant-scoped `invoice_queryset()` and
aggregates `invoice_lines.quantity` / `.unit` along it. That is the exact shape
`apps/payments/billing_seam.py` already uses and the exact reason it gives:
a documented preferred read, a published fallback, no model import, and **no
billing file edited** — another lane may be in `apps/billing` right now.

The gap is PARKED in `10-scripts/gates/seam_known_gaps.txt` so G20 says out
loud on every run that the preferred read is unbuilt, and so the row goes RED
the day billing publishes it (at which point this seam picks it up with no
edit here).

════════════════════════════════════════════════════════════════════════════
⚠ THE PERIOD BASIS IS **OQ-202, OPEN**, AND IT IS WORTH 2.55 POINTS
════════════════════════════════════════════════════════════════════════════
*"Which bills form the BILLED denominator — those ISSUED in the period, or those
whose SERVICE PERIOD falls in it?"*

Bills issue in arrears: Brazos Bend issues July's bills on **3 August** for the
July service period. Count the bills **issued in July** and the denominator is
**JUNE's** deliveries — **884,500 gal** — so July's 1,000,000 gallons of
purchases are compared against a different month's water and the figure reads
`(1,000,000 − 884,500) ÷ 1,000,000 = **11.55%**` instead of **9.00%**. A
2.55-point swing on the headline loss number of this feature, caused entirely by
a basis nobody labelled.

**Nothing here chooses.** `billed_volume_by_service` takes the basis as an
argument, both bases are computable, and **every answer carries its basis label
plus the problem code `billed_volume_period_basis_is_not_ruled`** so no figure
ever leaves this module unlabelled (BR-REP-001, one level out). The default is
`service_period` because that is the basis under which the PO's own ruled
figure — *bought 1,000,000 gallons, billed 910,000 → 9% unaccounted for* — is
the 9.00% they were shown; it is a REPRODUCTION of a ruled figure, not a
resolution of the question, and the problem code says so on every row it
produces.

════════════════════════════════════════════════════════════════════════════
WHAT IS **NOT** SUMMED, AND WHY EACH EXCLUSION IS A RULE
════════════════════════════════════════════════════════════════════════════
  * **Only `kind='usage'` lines.** A base charge, a fee, a tax and a minimum
    adjustment are money with no delivered quantity behind them; several carry
    `quantity = NULL` and one (`minimum_adjustment`) would add a quantity that
    was never delivered. Summing them would put units of nothing into a
    denominator of gallons.
  * **Only ISSUED bills** (`issued`/`paid`). A DRAFT bill has not been sent and
    can still change; `void` was withdrawn and `corrected` has been replaced by
    a rebill (BR-BIL-014), so counting either double-counts the water once the
    replacement is counted too.
  * **Lines with no unit are EXCLUDED and COUNTED**, never treated as zero. The
    count comes back on the result so the caller can report it — the same
    all-or-nothing discipline BR-LED-031 applies to the bought side. A silently
    dropped line understates the billed volume, which OVERSTATES the loss.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from importlib import import_module
from typing import Any

# Django's own aggregate, NOT a billing model. The no-import law this module
# states above is about `apps.billing.**`; `Max` is the ORM itself and is used
# only to make billing's OWN published queryset answer "the last period end"
# in the database rather than by walking every issued bill into memory.
from django.db.models import Max

#: Billing's published read layer, named once so the contract is greppable from
#: BOTH sides of the boundary — the discipline `apps/payments/billing_seam.py`
#: and `apps/billing/issue.GL_REVENUE_READ` both follow.
BILLING_MODULE = "billing"

#: THE PREFERRED READ, and the contract for the lane that publishes it:
#:
#:     apps.billing.selectors.billed_volume_by_service(
#:         period_start, period_end, *, basis="service_period" | "issued"
#:     ) -> Mapping[str, tuple[Decimal, str | None]]
#:         service code -> (summed usage quantity, its single unit or None when
#:                          the period's lines disagree about the unit)
#:
#: Billing does not publish it today, so the fallback below reads billing's own
#: published tenant-scoped queryset. PARKED in
#: 10-scripts/gates/seam_known_gaps.txt with `alt=apps.billing.selectors.
#: invoice_queryset`, so G20 names the gap on every run and goes RED the day the
#: preferred read appears.
BILLED_VOLUME_READ = "billed_volume_by_service"

#: The published fallback — billing's own tenant-scoped bill queryset. It is
#: what `apps/payments/billing_seam.py` falls back to for the same reason.
INVOICE_QUERYSET_READ = "invoice_queryset"

#: OQ-202's two readings. **RULED 2026-08-16: the SERVICE PERIOD.** PO verbatim:
#: *"(b). You're measuring physical water loss, so match the physical period."*
#: Both remain computable — the issued basis is still what an accountant would
#: ask for on a REVENUE question — but the unaccounted-for denominator is the
#: service period and the reason generalises: a metric about PHYSICAL water is
#: bounded by the period the water physically moved, never by the month an
#: invoice happened to be printed.
BASIS_SERVICE_PERIOD = "service_period"
BASIS_ISSUED = "issued"
PERIOD_BASES: tuple[str, ...] = (BASIS_SERVICE_PERIOD, BASIS_ISSUED)

#: ⚠ SUPERSEDED 2026-08-16 by the ruling above. Kept as a name so an older
#: payload or test can still be read, and emitted by nothing.
BASIS_NOT_RULED = "billed_volume_period_basis_is_not_ruled"

#: What a NON-ruled basis carries instead. The issued basis stays available and
#: is no longer silently equivalent: a caller that asks for it is asking for a
#: figure the PO did not rule, and the answer says so rather than wearing the
#: ruled basis's label. (BR-REP-001: no unlabelled figure, one level out.)
BASIS_NOT_THE_RULED_ONE = "billed_volume_basis_is_not_the_ruled_service_period"


def _basis_problem_tuple(basis: str) -> tuple[str, ...]:
    """`()` for the RULED basis, the named problem for the other one.

    Until 2026-08-16 every answer carried `BASIS_NOT_RULED` because neither
    reading had been chosen. It has been: the PO ruled the SERVICE PERIOD, so an
    answer computed on it is a plain answer and must stop apologising — a report
    still calling a ruled question open reads to a finance officer as *"this
    number may be about to change"*, which it is not, and that is the stale
    claim hard-won law 1 is about.

    The issued basis is still computable and still honest, and it now says what
    it is: not the ruled one.
    """
    return () if basis == BASIS_SERVICE_PERIOD else (BASIS_NOT_THE_RULED_ONE,)

#: Reported when billing publishes nothing this seam can read. US-LED-020 TC-9:
#: the row reports ABSENT with the reason and **never falls back to zero** — a
#: zero billed volume would read as **100.00% unaccounted for** on a healthy
#: month, which is the most alarming possible way to be wrong.
BILLED_READ_UNAVAILABLE = "billed_volume_read_is_unavailable"

#: Reported when a service's issued usage lines disagree about their unit. Not
#: an error and not a zero: the caller suppresses that service's figure by name
#: (BR-LED-033's shape applied to the billed side).
BILLED_UNIT_IS_MIXED = "billed_volume_unit_is_mixed"

#: Reported with a COUNT when usage lines carry a quantity and no unit. Rule 3
#: says a quantity without its unit is not a quantity, so those lines are
#: excluded — and the exclusion is named, because dropping them silently
#: understates the billed volume and therefore OVERSTATES the loss.
BILLED_LINES_WITHOUT_UNIT = "billed_lines_without_unit"

#: The bill states whose lines count. See the module docstring.
COUNTED_INVOICE_STATUSES: tuple[str, ...] = ("issued", "paid")

#: The one line kind that carries a delivered quantity. See the module
#: docstring for why the other four are excluded.
USAGE_LINE_KIND = "usage"

ZERO = Decimal("0")


@dataclass(frozen=True)
class BilledVolume:
    """What one service was BILLED over one period, or why that is unanswerable.

    `quantity is None` means **unanswerable**, and it is never conflated with a
    quantity of zero — US-LED-020 TC-9 exists because those two render as
    `ABSENT` and `100.00% unaccounted for` respectively, and only one of them is
    ever true of a healthy month.

    `problems` carries codes a screen can group on, never prose it would have to
    parse — the shape `apps/billing/delivery_seam.BillDelivery` established.
    """

    service: str
    quantity: Decimal | None
    unit: str | None
    basis: str
    line_count: int = 0
    problems: tuple[str, ...] = field(default=())


def _resolve(attribute: str, kind: str = "selectors") -> Any:
    """Billing's callable, or None while it has not published one."""
    try:
        target = import_module(f"apps.{BILLING_MODULE}.{kind}")
    except ImportError:  # pragma: no cover — defensive
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


def _as_decimal(value: Any) -> Decimal:
    """A quantity arrives as a Decimal or not at all.

    Refused rather than coerced, for the reason `apps/payments/billing_seam.
    _as_decimal` gives about money: a float that reached here would be a defect
    upstream, and converting it would hide the place where the quantity became a
    binary fraction. 1,000,000 gallons that becomes 999,999.99999 turns a clean
    9.00% into a figure with a tail nobody can explain.
    """
    if isinstance(value, Decimal):
        return value
    raise TypeError(
        f"a billed quantity must be a Decimal — quantities are NUMERIC(18,6) beside the money "
        f"they price (CLAUDE.md rule 2's reasoning, rule 3's unit); got {type(value).__name__}"
    )


#: `CR-142-BRC07` `P6.11` wave 3 — billing's own read of *which bills went out
#: in this window*, resolved rather than re-composed here (hard-won law 5).
INVOICES_ISSUED_BETWEEN_READ = "invoices_issued_between"

#: `invoices.bill_type` for a correction re-issued to the customer
#: (`billing.models.BILL_TYPES`). Named rather than typed at the call site so a
#: vocabulary change fails in one place.
REBILL_BILL_TYPE = "rebill"

#: Reported when billing publishes no issued-bills read. The column then stays
#: NULL **with this reason** and never 0 — a period in which nothing was rebilled
#: and a period we cannot ask about are different facts, and only the first is a
#: zero (`BR-REP-024`).
REBILLS_UNAVAILABLE = "billing_issued_invoices_read_is_unavailable"


def rebills_issued_between(*, start: date, end: date) -> int | None:
    """How many REBILLS this tenant issued inside a window — a COUNT, in SQL.

    R43's REBILLS column. `None` means billing publishes no such read and is
    never conflated with `0`.

    ⚠ **THIS COLUMN IS DATED BY ISSUE WHILE R43's MONEY IS DATED BY POSTING,
    AND THAT IS DELIBERATE RATHER THAN AN OVERSIGHT.** `BR-REP-001` governs what
    basis a MONEY figure states, and this is a count of an ACT: *how many
    corrections did we send out in this period*. The act is the issue, and a
    rebill posted on the 2nd for a bill sent on the 30th belongs to the month it
    was sent in as far as anybody reading this column is concerned. The two
    bases are one day apart at most and the report states the difference rather
    than hiding it — `apps/ledger/trend_pack.py` publishes `rebills_basis`.

    ⚠ **`.count()` AND NEVER `len(list(...))`.** The answer is a number and the
    rows are never wanted, so forty thousand bills in a period cost one
    aggregate rather than forty thousand model instances.
    """
    read = _resolve(INVOICES_ISSUED_BETWEEN_READ)
    if read is None:
        return None
    return int(read(start=start, end=end, bill_type=REBILL_BILL_TYPE).count())


def billed_volume_by_service(
    *,
    period_start: date,
    period_end: date,
    services: tuple[str, ...],
    basis: str = BASIS_SERVICE_PERIOD,
) -> dict[str, BilledVolume]:
    """The billed usage volume per service over one period, with its basis.

    One entry per requested service, always — a service with no billed lines
    comes back with `quantity = ZERO` and `unit = None`, which is a real answer
    (*"we billed nobody for water this month"*) and different from the
    unanswerable case, which comes back with `quantity = None` and a problem
    code. The caller must keep them apart; `cost_reconciliation.py` does.

    ⚠ **EVERY ENTRY CARRIES `billed_volume_period_basis_is_not_ruled`** until
    OQ-202 is ruled. See the module docstring for the 11.55%-vs-9.00% swing that
    makes the basis a finance question rather than an implementation detail.
    """
    if basis not in PERIOD_BASES:
        raise ValueError(
            f"{basis!r} is not one of {PERIOD_BASES}. OQ-202 asks which of the two the billed "
            "denominator uses and is OPEN; this seam computes either and chooses neither."
        )

    # The preferred read, if the lane that owns it has published it since.
    preferred = _resolve(BILLED_VOLUME_READ)
    if preferred is not None:  # pragma: no cover — billing publishes nothing today
        answered = preferred(period_start, period_end, basis=basis) or {}
        return {
            service: BilledVolume(
                service=service,
                quantity=(
                    _as_decimal(answered[service][0]) if service in answered else ZERO
                ),
                unit=answered[service][1] if service in answered else None,
                basis=basis,
                problems=_basis_problem_tuple(basis),
            )
            for service in services
        }

    queryset_read = _resolve(INVOICE_QUERYSET_READ)
    if queryset_read is None:
        # Billing publishes NEITHER read. Every service is unanswerable and says
        # so — never zero (TC-9).
        return {
            service: BilledVolume(
                service=service,
                quantity=None,
                unit=None,
                basis=basis,
                problems=(BILLED_READ_UNAVAILABLE, *_basis_problem_tuple(basis)),
            )
            for service in services
        }

    bills = queryset_read().filter(status__in=COUNTED_INVOICE_STATUSES)
    if basis == BASIS_SERVICE_PERIOD:
        # The bills whose SERVICE PERIOD lies in the window — the physics
        # reading. July's water is the water delivered in July, whenever the
        # bill for it went out.
        bills = bills.filter(period_start__gte=period_start, period_end__lte=period_end)
    else:
        # The bills ISSUED in the window — the posting reading. For Brazos Bend
        # this is JUNE's deliveries, billed on 3 August, and it is what makes
        # the figure read 11.55% instead of 9.00%.
        bills = bills.filter(issued_at__date__gte=period_start, issued_at__date__lte=period_end)

    # Traversed along the reviewed cross-module edge (`invoices` → its own
    # `lines` reverse relation) rather than by importing `billing.InvoiceLine`.
    # `service__code` reaches the PLATFORM service catalog, which is tenancy's
    # RLS-exempt table (B2 §3) and the same vocabulary this module's own
    # `tenancy_seam.enabled_service_codes` speaks.
    rows = (
        bills.filter(lines__kind=USAGE_LINE_KIND, lines__service__code__in=services)
        .values("lines__service__code", "lines__unit", "lines__quantity")
    )

    totals: dict[str, Decimal] = {}
    units: dict[str, set[str]] = {}
    counts: dict[str, int] = {}
    unitless: dict[str, int] = {}
    for row in rows:
        service = row["lines__service__code"]
        quantity = row["lines__quantity"]
        unit = row["lines__unit"]
        if quantity is None:
            continue  # a usage line with no quantity delivered nothing to count
        if not unit:
            unitless[service] = unitless.get(service, 0) + 1
            continue  # rule 3: a quantity with no unit is not a quantity
        totals[service] = totals.get(service, ZERO) + _as_decimal(quantity)
        units.setdefault(service, set()).add(unit)
        counts[service] = counts.get(service, 0) + 1

    answer: dict[str, BilledVolume] = {}
    for service in services:
        problems: list[str] = list(_basis_problem_tuple(basis))
        service_units = units.get(service, set())
        if unitless.get(service):
            problems.append(BILLED_LINES_WITHOUT_UNIT)
        if len(service_units) > 1:
            # Two units in one service's own bills. Suppressed by name rather
            # than summed — adding gallons to litres is the failure BR-LED-033
            # forbids on the purchase side, and it is no better here.
            answer[service] = BilledVolume(
                service=service,
                quantity=None,
                unit=None,
                basis=basis,
                line_count=counts.get(service, 0),
                problems=tuple(problems + [BILLED_UNIT_IS_MIXED]),
            )
            continue
        answer[service] = BilledVolume(
            service=service,
            quantity=totals.get(service, ZERO),
            unit=next(iter(service_units)) if service_units else None,
            basis=basis,
            line_count=counts.get(service, 0),
            problems=tuple(problems),
        )
    return answer




#: CR-060 C9 / task T4 — THE PREFERRED PER-BUILDING READ, and the contract for
#: the lane that publishes it:
#:
#:     apps.billing.selectors.billed_volume_by_service_and_premises(
#:         period_start, period_end, *, basis
#:     ) -> {(premises_id, service_code): (quantity, unit)}
#:
#: Billing publishes neither this nor `billed_volume_by_service`, so the read
#: below runs on the SAME published fallback the tenant-wide read already uses
#: (`invoice_queryset`) and resolves the building through
#: `dimension_seam.location_for_account`. PARKED in
#: 10-scripts/gates/seam_known_gaps.txt beside its tenant-wide twin.
BILLED_VOLUME_BY_PREMISES_READ = "billed_volume_by_service_and_premises"

#: A bill whose account cannot be resolved to a building. It is REPORTED on the
#: row it affects and never dropped: a member account whose unit was removed
#: still billed real water, and silently leaving its volume out of a building's
#: denominator would understate that building's loss.
BILLED_PREMISES_UNRESOLVED = "some_billed_accounts_resolve_to_no_premises"


def billed_volume_by_service_and_premises(
    *,
    period_start: date,
    period_end: date,
    services: tuple[str, ...],
    basis: str = BASIS_SERVICE_PERIOD,
) -> dict[tuple[str, str], BilledVolume]:
    """CR-060 C9 — the billed denominator at the (building, service) grain.

    **THE BUILDING IS RESOLVED THROUGH THE ONE CHAIN THAT ALREADY EXISTS**, and
    that is the whole reason this function is short. `invoices.account_id` is a
    REVIEWED cross-module edge (B2 §2) and is as far as billing's own data
    reaches; account → unit → premises is `dimension_seam.location_for_account`,
    which US-LED-002 built and which `apps/ledger/posting.py` stamps every
    journal line from. Walking `account__unit__premises_id` in this queryset
    would be a SECOND implementation of that chain — and BR-TEN-013 forbids one
    module touching another's ORM, which customers' and metering's tables are.
    A second implementation is also how the cost side and the receivable side
    would eventually attribute the same money to two different buildings.

    ⚠ **THE COST, STATED RATHER THAN DISCOVERED.** The chain is two queries per
    DISTINCT ACCOUNT (the seam's own docstring says so), memoised here for the
    length of one call. A sub-metering company with forty buildings and twenty
    members each is 800 accounts — 1,600 queries on a monthly report. That is
    acceptable at this product's stated size and is exactly what the preferred
    read above exists to replace; it is named here so the next lane sees a
    measured limit rather than rediscovering it.

    Keys are `(premises_id, service_code)`. An account that resolves to NO
    building contributes to no key and raises `BILLED_PREMISES_UNRESOLVED` on
    every service it billed, which the caller carries onto the affected rows.
    """
    if basis not in PERIOD_BASES:
        raise ValueError(
            f"{basis!r} is not one of {PERIOD_BASES}. OQ-202 asks which of the two the billed "
            "denominator uses and is OPEN; this seam computes either and chooses neither."
        )

    preferred = _resolve(BILLED_VOLUME_BY_PREMISES_READ)
    if preferred is not None:  # pragma: no cover — billing publishes nothing today
        answered = preferred(period_start, period_end, basis=basis) or {}
        return {
            (str(premises_id), service): BilledVolume(
                service=service,
                quantity=_as_decimal(value[0]),
                unit=value[1],
                basis=basis,
                problems=_basis_problem_tuple(basis),
            )
            for (premises_id, service), value in answered.items()
            if service in services
        }

    queryset_read = _resolve(INVOICE_QUERYSET_READ)
    if queryset_read is None:
        return {}

    bills = queryset_read().filter(status__in=COUNTED_INVOICE_STATUSES)
    if basis == BASIS_SERVICE_PERIOD:
        bills = bills.filter(period_start__gte=period_start, period_end__lte=period_end)
    else:
        bills = bills.filter(issued_at__date__gte=period_start, issued_at__date__lte=period_end)

    rows = bills.filter(lines__kind=USAGE_LINE_KIND, lines__service__code__in=services).values(
        "account_id", "lines__service__code", "lines__unit", "lines__quantity"
    )

    from apps.ledger import dimension_seam  # local: avoids an import cycle

    located: dict[str, str | None] = {}
    totals: dict[tuple[str, str], Decimal] = {}
    units: dict[tuple[str, str], set[str]] = {}
    counts: dict[tuple[str, str], int] = {}
    unitless: dict[tuple[str, str], int] = {}
    unresolved: set[str] = set()
    for row in rows:
        service = row["lines__service__code"]
        quantity = row["lines__quantity"]
        unit = row["lines__unit"]
        account_id = str(row["account_id"]) if row["account_id"] else None
        if quantity is None:
            continue
        if account_id is None:
            unresolved.add(service)
            continue
        if account_id not in located:
            location = dimension_seam.location_for_account(account_id)
            located[account_id] = location.premises_id if location.resolved else None
        premises_id = located[account_id]
        if premises_id is None:
            unresolved.add(service)
            continue
        key = (premises_id, service)
        if not unit:
            unitless[key] = unitless.get(key, 0) + 1
            continue  # rule 3: a quantity with no unit is not a quantity
        totals[key] = totals.get(key, ZERO) + _as_decimal(quantity)
        units.setdefault(key, set()).add(unit)
        counts[key] = counts.get(key, 0) + 1

    answer: dict[tuple[str, str], BilledVolume] = {}
    for key in set(totals) | set(unitless):
        premises_id, service = key
        problems: list[str] = list(_basis_problem_tuple(basis))
        if unitless.get(key):
            problems.append(BILLED_LINES_WITHOUT_UNIT)
        if service in unresolved:
            problems.append(BILLED_PREMISES_UNRESOLVED)
        key_units = units.get(key, set())
        if len(key_units) > 1:
            answer[key] = BilledVolume(
                service=service,
                quantity=None,
                unit=None,
                basis=basis,
                line_count=counts.get(key, 0),
                problems=tuple(problems + [BILLED_UNIT_IS_MIXED]),
            )
            continue
        answer[key] = BilledVolume(
            service=service,
            quantity=totals.get(key, ZERO),
            unit=next(iter(key_units)) if key_units else None,
            basis=basis,
            line_count=counts.get(key, 0),
            problems=tuple(problems),
        )
    return answer


#: `apps.billing.selectors.tax_by_authority_for_invoices(invoice_ids)` — the
#: per-authority tax subtotal over a NAMED SET of bills. Published by billing on
#: 2026-08-31 for the PO's ruling *"(a) Add a per-authority subtotal to the bill
#: and the finance screens"* (`OQ-1190`).
TAX_BY_AUTHORITY_READ = "tax_by_authority_for_invoices"

#: Reported on every authority row when billing has not published the read.
#: NEVER a zero and never the GL figure copied across: a bill-sourced column
#: silently filled from the books would agree with the books by construction and
#: could never disagree — a check that cannot fail, which this repo recorded six
#: of in one day.
TAX_BY_AUTHORITY_UNAVAILABLE = "per_authority_bill_subtotal_read_is_unavailable"


def tax_by_authority_for_invoices(invoice_ids: tuple[Any, ...]) -> dict[str, Any] | None:
    """What each tax authority was charged across a NAMED set of bills.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  THE BOOKS CHOOSE THE BILLS. BILLING SPLITS THEM. NEITHER GUESSES.   ║
    ╚══════════════════════════════════════════════════════════════════════╝
    PO ruling 2026-08-31 (`OQ-1190`): *"(a) Add a per-authority subtotal to the
    bill and the finance screens"*. The finance screen is S41, which reports a
    PERIOD — and a period read written inside billing would have had to decide
    on its own whether a VOID bill's tax and a CORRECTED bill's tax still belong
    on a return. **That is an unsigned money rule and the prime directive
    forbids a lane choosing a value for one.**

    So `remittance_by_authority` hands over the invoice ids it already selected
    — the invoice-sourced entries that credited each authority's 2200-nn account
    inside ITS window, on ITS posting basis, where a reversal is a debit that
    removes itself — and billing answers only *"of these bills, how much is each
    authority's?"*. No basis is invented on either side of the seam.

    **A published SELECTOR, never an import** (B1 / BR-TEN-013, gate G6): the
    read is resolved by name at call time, exactly as `billed_volume_by_service`
    resolves its own. `None` comes back while billing has not published it, and
    the caller states the absence rather than filling the column — see
    `TAX_BY_AUTHORITY_UNAVAILABLE`.
    """
    read = _resolve(TAX_BY_AUTHORITY_READ)
    if read is None:  # pragma: no cover — billing publishes it since 2026-08-31
        return None
    return read(tuple(invoice_ids))


# ═══════════════════════════════════════════════════════════════════════════
# CR-060 C2 / task T7 — THE PRICE BASIS FOR THE UNBILLED-REVENUE ACCRUAL
# ═══════════════════════════════════════════════════════════════════════════
#: THE PREFERRED READ, and the contract for the lane that publishes it:
#:
#:     apps.billing.selectors.last_priced_usage_by_account_service(
#:         account_ids, service_codes
#:     ) -> {(account_id, service_code): (unit_price, unit, invoice_id,
#:                                        issued_on, period_end)}
#:
#: Billing does not publish it, so the read below runs on the SAME published
#: fallback the two volume reads already use (`invoice_queryset`). PARKED in
#: 10-scripts/gates/seam_known_gaps.txt beside them.
LAST_PRICED_USAGE_READ = "last_priced_usage_by_account_service"

#: Reported when billing publishes nothing this read can use. The accrual then
#: REFUSES rather than accruing zero — a zero unbilled accrual is the claim
#: *"nothing is unbilled"*, made over books that may hold a month of it.
PRICE_BASIS_UNAVAILABLE = "usage_price_basis_read_is_unavailable"

#: Reported WITH A COUNT when an (account, service) pair has unbilled reads and
#: no issued usage line to take a price from — a first bill that has not gone
#: out yet, most often. Those reads are EXCLUDED and NAMED, never priced at
#: zero: a zero-priced read would put consumption into the accrual's quantity
#: and nothing into its money, so the entry would understate revenue while
#: looking complete.
NO_PRIOR_PRICED_USAGE_LINE = "account_service_has_no_prior_priced_usage_line"

#: Reported WITH A COUNT when the read's unit and the priced line's unit differ
#: — gallons read against a kgal price. Excluded rather than converted:
#: BR-LED-033's discipline on the purchase side, applied here, and rule 3's
#: reason. A silent conversion factor is how a figure becomes 1,000× wrong.
PRICED_UNIT_MISMATCH = "read_unit_differs_from_last_priced_unit"


@dataclass(frozen=True)
class PricedUsage:
    """What this account was LAST charged per unit for this service.

    Read off an issued invoice line the rating engine produced — **never
    recomputed here** (BR-REP-002, and CR-060 §13's third exclusion: the mapping
    and the maths are resolved once, upstream, and read downstream).
    """

    account_id: str
    service_code: str
    unit_price: Decimal
    unit: str | None
    invoice_id: str
    issued_on: date | None
    period_end: date | None


@dataclass(frozen=True)
class PriceBasisOutcome:
    """The price basis, plus the date each account was last billed to.

    `prices is None` means **unanswerable** — billing publishes no read at all —
    and is never conflated with an empty mapping, which means *"these accounts
    have never been billed"*. The accrual treats the two differently: it refuses
    on the first and reports named exclusions on the second.

    `last_billed_period_end` is the belt-and-braces half of what counts as
    unbilled (see `apps/ledger/metering_seam.py`): a read on or before the
    account's last issued service period has been billed however its lifecycle
    column reads.
    """

    prices: dict[tuple[str, str], PricedUsage] | None
    last_billed_period_end: dict[str, date]
    problems: tuple[str, ...] = field(default=())


def last_priced_usage(
    *,
    account_ids: tuple[str, ...],
    service_codes: tuple[str, ...],
) -> PriceBasisOutcome:
    """The last issued usage price per (account, service), and the last bill date.

    ONE pass over billing's own published queryset answers both, ordered newest
    first so `setdefault` keeps the LATEST issued line per pair. `.iterator()`
    keeps the result cache out of memory — the same reason CR-060 task T14 gives
    for the bill run's gather loop, and it matters here because an accrual over
    a large tenant walks every issued usage line the candidate accounts have.

    ⚠ **ONLY `kind='usage'` LINES OF ISSUED BILLS**, exactly as
    `billed_volume_by_service` above and for the same reasons: a base charge, a
    fee, a tax and a minimum adjustment are money with no delivered quantity
    behind them, so none of them carries a price PER UNIT that consumption could
    be multiplied by. **The accrual is therefore a USAGE accrual and says so** —
    the base charge of an unbilled period is not accrued, because it is not
    measured by a read and pricing it would mean re-deriving a tariff here.
    """
    queryset_read = _resolve(INVOICE_QUERYSET_READ)
    if queryset_read is None:
        return PriceBasisOutcome(
            prices=None, last_billed_period_end={}, problems=(PRICE_BASIS_UNAVAILABLE,)
        )
    if not account_ids:
        return PriceBasisOutcome(prices={}, last_billed_period_end={})

    accounts = [str(account_id) for account_id in account_ids]
    bills = queryset_read().filter(
        status__in=COUNTED_INVOICE_STATUSES, account_id__in=accounts
    )

    # (1) The last SERVICE PERIOD each account was billed to. Answered in the
    # database rather than by walking rows — it is one number per account and
    # every candidate account has one.
    last_billed: dict[str, date] = {}
    for row in bills.values("account_id").annotate(last_end=Max("period_end")):
        if row["last_end"] is not None:
            last_billed[str(row["account_id"])] = row["last_end"]

    # (2) The price basis. Newest issued bill first; the `key in prices` guard
    # therefore keeps the most recent line per (account, service) and every
    # older one is a dict lookup that changes nothing.
    prices: dict[tuple[str, str], PricedUsage] = {}
    rows = (
        bills.filter(lines__kind=USAGE_LINE_KIND, lines__service__code__in=list(service_codes))
        .values(
            "id",
            "account_id",
            "issued_at",
            "period_end",
            "lines__service__code",
            "lines__unit_price",
            "lines__unit",
        )
        .order_by("-issued_at", "-period_end", "-id")
    )
    for row in rows.iterator(chunk_size=500):
        unit_price = row["lines__unit_price"]
        if unit_price is None:
            # A usage line with no per-unit price — a flat or minimum-priced
            # line. It prices no quantity, so it is no basis for one.
            continue
        key = (str(row["account_id"]), str(row["lines__service__code"]))
        if key in prices:
            continue
        issued_at = row["issued_at"]
        prices[key] = PricedUsage(
            account_id=key[0],
            service_code=key[1],
            unit_price=_as_decimal(unit_price),
            unit=row["lines__unit"],
            invoice_id=str(row["id"]),
            issued_on=issued_at.date() if hasattr(issued_at, "date") else issued_at,
            period_end=row["period_end"],
        )
    return PriceBasisOutcome(prices=prices, last_billed_period_end=last_billed)


# ═══════════════════════════════════════════════════════════════════════════
# Finance blueprint p018 `P5.8` — THE PRINTED DOCUMENT NUMBER
# ═══════════════════════════════════════════════════════════════════════════
#: THE READS, and unlike this module's two volume reads these ARE published —
#: `P5.8` is the task that published them:
#:
#:     apps.billing.selectors.invoice_numbers_for(ids)     -> {id: invoice_no}
#:     apps.billing.selectors.credit_note_numbers_for(ids) -> {id: credit_note_no}
#:
#: p018's OUTCOME column: *"The read exists, so the feed can carry it"*. The
#: feed carried it already — `apps/integrations/seams/ledger._document_numbers`
#: reads its OWN seam files, which is why `P5.3` was buildable there and not
#: here. This is the SCREEN half, and it is the half `P5.8` gates.
INVOICE_NUMBERS_READ = "invoice_numbers_for"
CREDIT_NOTE_NUMBERS_READ = "credit_note_numbers_for"

#: The journal `source_type` each read answers for. ⚠ **`credit_note` IS ON
#: THIS LIST BECAUSE THE WIRE ALREADY HAS IT.** `_DOCUMENT_SOURCES` in
#: `apps/integrations/seams/ledger.py` names all three kinds; a screen half
#: that resolved only two would print a uuid on exactly the row the feed can
#: name, over the same gap, with every test green (`DEF-LED-6653`).
BILLING_DOCUMENT_READS: dict[str, str] = {
    "invoice": INVOICE_NUMBERS_READ,
    "credit_note": CREDIT_NOTE_NUMBERS_READ,
}


def document_numbers_for(wanted: dict[str, set[str]]) -> dict[tuple[str, str], str]:
    """`{(source_type, source_id): printed_number}` for billing's document kinds.

    `wanted` is keyed by journal `source_type`, so a window holding no credit
    note costs no credit-note query and a window holding neither costs no query
    at all — the shape `integrations.seams.ledger.page_context` already uses,
    copied deliberately so the two halves of one gap cannot drift.

    ⚠ **AN UNRESOLVED ID IS SIMPLY ABSENT FROM THIS MAP.** The caller renders a
    stated absence for it; what it must NOT do is fall back to the source id,
    because that is the value this whole task exists to take off the screen
    (`B14` rule 31) and it would arrive wearing the name of its own replacement.

    ⚠ **A SOURCE TYPE BILLING DOES NOT OWN IS NOT AN ERROR HERE.** `payment` is
    answered by `apps/ledger/payments_seam.py` and `opening_balance` has no
    document to name; both are skipped silently, because this seam's job is to
    answer for billing's kinds and not to police the ledger's vocabulary.
    """
    resolved: dict[tuple[str, str], str] = {}
    for source_type, attribute in BILLING_DOCUMENT_READS.items():
        ids = wanted.get(source_type)
        if not ids:
            continue
        read = _resolve(attribute)
        if read is None:  # pragma: no cover — billing publishes both since P5.8
            continue
        for source_id, number in (read(tuple(sorted(ids))) or {}).items():
            if number:
                resolved[(source_type, str(source_id))] = str(number)
    return resolved


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-020@d744841 (co-sources: 04-docs/05-modules/09-ledger/06-epics/EP-LED-06-cost-of-service-capture.md US-LED-020 §5/§8 — the billing selector seam and OQ-202 · 04-docs/05-modules/09-ledger/03-field-map.md D-13 — "a published billing SELECTOR SEAM, never a new import" · 04-docs/05-modules/09-ledger/01-overview.md v5.1 — the no-import law · 12-governance/01-open-questions.md OQ-202)
# generated: 2026-08-15 by the ledger AP-capture lane
# checklist: A✔ B✔ C✔ D=deferred(a seam — it serves no route of its own; its callers do) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, ledger row OWED and named in the lane report)
# gates: PROVED RED BEFORE GREEN — the unit-mismatch suppression was driven by
#         billing water in `kgal` against a `gal` purchase with the check
#         removed (a 99.9% loss figure was produced from 910 vs 1,000,000) and
#         with it present (ABSENT by name); the draft-bill exclusion was driven
#         by issuing nothing and watching the denominator move. See
#         tests/test_us_led_020_reconciliation.py
# exceptions: (1) THE PREFERRED READ IS NOT PUBLISHED. `apps.billing.selectors.
#         billed_volume_by_service` is the contract stated above and billing
#         does not have it; the seam falls back to billing's own published
#         tenant-scoped `invoice_queryset` and aggregates along the reviewed
#         cross-module edge. No billing model is imported (G6 rule 4) and NO
#         billing file was edited — the lane instruction forbids it and another
#         lane may be in there now. PARKED in seam_known_gaps.txt so G20 names
#         it every run · (2) **THE PERIOD BASIS IS OQ-202, OPEN.** Both bases
#         are computed and neither is chosen; every answer carries
#         `billed_volume_period_basis_is_not_ruled` and its basis label. The
#         DEFAULT reproduces the PO's own ruled 9.00% (service-period), which is
#         a reproduction of a ruled figure and NOT a resolution — the problem
#         code says so on every row · (3) ONLY `kind='usage'` LINES OF ISSUED
#         BILLS ARE SUMMED, and lines carrying a quantity with no unit are
#         EXCLUDED AND COUNTED (`billed_lines_without_unit`) rather than
#         silently dropped: dropping them understates the billed volume, which
#         OVERSTATES the loss · (4) a service whose issued lines carry TWO units
#         is suppressed by name rather than summed
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
