# ── Trace ──────────────────────────────────────────────
# Epics:    EP-LED-04 (the accrual and its day-1 reversal — CR-060 C2 / task T7)
#           Screens: S42 (the close checklist the accrual completes)
#           NOTE: no US-ID is cited here ON PURPOSE. G10 reads a Trace-header
#           US-ID as "this file ships that story's TCs"; this file ships one
#           cross-module READ, not a story. Same precedent as
#           apps/ledger/billing_seam.py, apps/ledger/tenancy_seam.py and
#           apps/billing/metering_seam.py.
# Rules:    BR-TEN-013 (a module NEVER touches another module's ORM; a
#           cross-module read resolves the owner's published callable) ·
#           BR-MET-053 (the read lifecycle: committed → BILLED, and the BILLED
#           lock is what makes "unbilled" a fact rather than a guess) ·
#           BR-MET-016 (lineage heads only — a superseded read is represented by
#           its correction) · CLAUDE.md rule 1 (tenant scoping, inherited from
#           metering's own scoped read and never re-implemented here) · rule 3
#           (a quantity travels with its unit, always)
# Tests:    06-backend/tests/test_cr060_t7_unbilled_accrual.py
# Impacts:  apps/ledger/unbilled_accrual.py (its only caller)
# ───────────────────────────────────────────────────────
"""ledger → metering SEAM: **which reads are recorded and not yet billed?**

HUMAN-OWNED · HUMAN-REVIEW-PENDING — a wrong answer here is a wrong figure in
the trial balance. AI-authored 2026-09-02 under the PO ruling of 2026-08-09
("AI will do it; we will review it later as human"); the row is owed in
`12-governance/09-human-review-ledger.md` and CR-060 task T19 is where it is
written.

════════════════════════════════════════════════════════════════════════════
WHAT "UNBILLED" MEANS HERE, AND WHY IT IS A FACT RATHER THAN AN ESTIMATE
════════════════════════════════════════════════════════════════════════════
`meter_reads.lifecycle` is BR-MET-053's two-state column — `committed`, then
`billed` when a bill prices it. **The BILLED lock is WIRED**: `apps/billing/
issue.py` calls `metering_seam.mark_reads_billed` inside the issue transaction
(DEF-098), for every read named on the bill's own frozen snapshot.

⚠ **`apps/metering/services.mark_read_billed`'s own docstring still says
*"NOTHING CALLS THIS YET"*, and that sentence went stale when DEF-098 landed.**
It is reported rather than edited from here (metering is another module's file);
what matters for this seam is that the column is maintained, so a `committed`
head really is a read no bill has priced.

**AND THE DATE FILTER IS BELT AND BRACES, NOT BELT ALONE.** A read taken before
the lock was wired can still read `committed` although its bill went out months
ago. So a read counts as unbilled only when BOTH are true: its lifecycle is
`committed`, **and** it falls after the last issued bill's service period for
its own account (`apps/ledger/unbilled_accrual.py` applies the second half,
using billing's published dates). Requiring both is deliberately CONSERVATIVE —
it can only ever UNDER-accrue — and under-accruing an entry that reverses on day
one is the safe direction to be wrong in.

════════════════════════════════════════════════════════════════════════════
THE PREFERRED READ, AND THE FALLBACK THAT KEEPS THE FIGURE HONEST
════════════════════════════════════════════════════════════════════════════
The contract this seam wants from metering is `UNBILLED_READS_READ` below.
**Metering does not publish it today** — `10-scripts/gates/seam_known_gaps.txt`
already carries a sibling row saying metering *"publishes a paginated LIST for
S25, not a count of committed-but-unbilled reads"*. Rather than leave the
accrual dark (hard-won law 2, *built is not wired*), this seam falls back to
metering's OWN published, tenant-scoped `read_list()` queryset and reads the
heads along it. That is the exact shape `apps/ledger/billing_seam.py` uses and
for the same reasons: a documented preferred read, a published fallback, **no
metering model import**, and no metering file edited.

⚠ **THE FALLBACK CARRIES METERING'S HOT WINDOW AND SAYS SO.** `read_list()`
applies BR-MET-055's 730-day window unless `include_archive=True`, so a period
older than two years cannot be accrued through this path. Every answer carries
`READS_LIMITED_TO_HOT_WINDOW` rather than reporting a smaller figure silently —
BR-REP-001, one level out.

════════════════════════════════════════════════════════════════════════════
WHAT IS EXCLUDED, AND WHY EVERY EXCLUSION IS COUNTED
════════════════════════════════════════════════════════════════════════════
  * **A head with no `consumption`** — an estimate that recorded no figure has
    nothing to accrue. Excluded and COUNTED, never treated as zero.
  * **A head with no `unit`** — CLAUDE.md rule 3: a quantity with no unit is not
    a quantity. Excluded and counted.
  * **A head naming no customer account** — the price basis is the account's own
    last bill, so a read nobody is billed for has no price. Excluded and counted.
  * **A head whose service point resolves to no service** — nothing to credit.
    Excluded and counted.
  * **AN ESTIMATED READ IS NOT EXCLUDED.** It is counted separately and
    reported. An accrual IS an estimate of revenue; dropping the estimated reads
    would systematically UNDER-state it, and the product already bills from
    those same figures (BR-MET-026). The count travels so a reviewer can see how
    much of the accrual rests on estimates.

A silently dropped read understates the accrual, which overstates income by
omission. Nothing here is dropped without a name and a number.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from importlib import import_module
from typing import Any

#: Metering's published read layer, named once so the contract is greppable from
#: BOTH sides of the boundary.
METERING_MODULE = "metering"

#: THE PREFERRED READ, and the contract for the lane that publishes it:
#:
#:     apps.metering.selectors.unbilled_reads(
#:         *, as_of: date, service_codes: tuple[str, ...]
#:     ) -> Iterable[Mapping]
#:         each mapping carrying read_id · account_id · service_code ·
#:         consumption (Decimal | None) · unit (str | None) · read_on (date) ·
#:         estimated (bool)
#:
#: Metering does not publish it today, so the fallback below reads metering's own
#: published tenant-scoped queryset. PARKED in
#: 10-scripts/gates/seam_known_gaps.txt with `alt=apps.metering.selectors.
#: read_list`, so G20 names the gap on every run and goes RED the day the
#: preferred read appears.
UNBILLED_READS_READ = "unbilled_reads"

#: The published fallback — metering's own tenant-scoped, hot-windowed queryset.
READ_LIST_READ = "read_list"

#: BR-MET-053's two lifecycle words. `committed` is "no bill has priced this".
LIFECYCLE_COMMITTED = "committed"

#: Reported when metering publishes NEITHER read. The accrual then refuses
#: rather than accruing zero: a zero accrual reads as *"there is no unbilled
#: revenue"*, which is a claim, over books that may hold a month of it.
READS_UNAVAILABLE = "unbilled_reads_read_is_unavailable"

#: Always reported on the fallback path. See the docstring — BR-MET-055's hot
#: window is metering's own and is not defeated from here.
READS_LIMITED_TO_HOT_WINDOW = "unbilled_reads_limited_to_metering_hot_window"

#: The four named exclusions, each carrying a COUNT on the outcome.
READ_HAS_NO_CONSUMPTION = "read_has_no_consumption"
READ_HAS_NO_UNIT = "read_has_no_unit"
READ_HAS_NO_ACCOUNT = "read_has_no_account"
READ_HAS_NO_SERVICE = "read_has_no_service"

#: Not an exclusion — a disclosure. See the docstring.
READS_INCLUDE_ESTIMATES = "unbilled_reads_include_estimated_reads"


@dataclass(frozen=True)
class UnbilledRead:
    """One committed head that no bill has priced, as the accrual will use it."""

    read_id: str
    account_id: str
    service_code: str
    consumption: Decimal
    unit: str
    read_on: date
    estimated: bool = False


@dataclass(frozen=True)
class UnbilledReadOutcome:
    """The unbilled heads, and everything that was left out of them, by name.

    `reads is None` means **unanswerable** and is never conflated with an empty
    tuple: *"metering publishes nothing this seam can read"* and *"there is
    nothing unbilled"* are different facts, and only one of them may be accrued
    at zero.
    """

    reads: tuple[UnbilledRead, ...] | None
    problems: tuple[str, ...] = field(default=())
    excluded: dict[str, int] = field(default_factory=dict)
    estimated_count: int = 0
    considered: int = 0


def _resolve(attribute: str, kind: str = "selectors") -> Any:
    """Metering's callable, or None while it has not published one."""
    try:
        target = import_module(f"apps.{METERING_MODULE}.{kind}")
    except ImportError:  # pragma: no cover — defensive
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


def _as_decimal(value: Any) -> Decimal | None:
    """A consumption arrives as a Decimal or not at all.

    Refused rather than coerced, for the reason `apps/ledger/billing_seam.
    _as_decimal` gives: a float that reached here would be a defect upstream,
    and converting it would hide the place where the quantity became a binary
    fraction — in a figure that is about to be multiplied by a price and posted.
    """
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    raise TypeError(
        "a meter read's consumption must be a Decimal — quantities are "
        "NUMERIC(18,6) beside the money they price (CLAUDE.md rule 2's "
        f"reasoning, rule 3's unit); got {type(value).__name__}"
    )


def _read_on(value: Any) -> date | None:
    """`read_at` is a datetime stamped at 00:00Z of the read DATE. Take the date."""
    if value is None:
        return None
    return value.date() if hasattr(value, "date") else value


def unbilled_reads(
    *,
    as_of: date,
    service_codes: tuple[str, ...],
) -> UnbilledReadOutcome:
    """Every committed head on or before `as_of` that no bill has priced.

    `service_codes` is the tenant's own enabled set, resolved by the caller
    through `tenancy_seam.enabled_service_codes` — a service the tenant does not
    sell has no revenue account to credit, so asking for it would be asking for
    a line nothing could post.
    """
    preferred = _resolve(UNBILLED_READS_READ)
    if preferred is not None:  # pragma: no cover — metering publishes nothing today
        rows = preferred(as_of=as_of, service_codes=service_codes) or ()
        return _collect(
            (
                {
                    "id": row.get("read_id"),
                    "account_id": row.get("account_id"),
                    "service": row.get("service_code"),
                    "consumption": row.get("consumption"),
                    "unit": row.get("unit"),
                    "read_at": row.get("read_on"),
                    "estimated": bool(row.get("estimated")),
                }
                for row in rows
            ),
            problems=(),
        )

    read_list = _resolve(READ_LIST_READ)
    if read_list is None:
        # Metering publishes NEITHER read. The figure is unanswerable and says
        # so — never zero.
        return UnbilledReadOutcome(reads=None, problems=(READS_UNAVAILABLE,))

    # Traversed along metering's OWN published, tenant-scoped queryset
    # (`read_list` applies CLAUDE.md rule 1 and BR-MET-016's lineage-head filter
    # itself) rather than by importing `metering.MeterRead`. `.values()` keeps
    # the model instances out of memory entirely; `.iterator()` keeps the result
    # cache out of it too, which is the same discipline CR-060 task T14 applies
    # to the bill run's gather loop and matters here for the same reason.
    queryset = (
        read_list()
        .filter(
            lifecycle=LIFECYCLE_COMMITTED,
            read_at__date__lte=as_of,
            asset__service_point__service__code__in=list(service_codes),
        )
        .values(
            "id",
            "account_id",
            "consumption",
            "unit",
            "read_at",
            "status",
            "asset__service_point__service__code",
        )
    )
    return _collect(
        (
            {
                "id": row["id"],
                "account_id": row["account_id"],
                "service": row["asset__service_point__service__code"],
                "consumption": row["consumption"],
                "unit": row["unit"],
                "read_at": row["read_at"],
                "estimated": row.get("status") == "estimated",
            }
            for row in queryset.iterator(chunk_size=500)
        ),
        problems=(READS_LIMITED_TO_HOT_WINDOW,),
    )


def _collect(rows: Any, *, problems: tuple[str, ...]) -> UnbilledReadOutcome:
    """Split the heads into what can be accrued and what cannot, with counts."""
    kept: list[UnbilledRead] = []
    excluded: dict[str, int] = {}
    estimated = 0
    considered = 0

    def drop(code: str) -> None:
        excluded[code] = excluded.get(code, 0) + 1

    for row in rows:
        considered += 1
        consumption = _as_decimal(row.get("consumption"))
        if consumption is None:
            drop(READ_HAS_NO_CONSUMPTION)
            continue
        unit = row.get("unit")
        if not unit:
            drop(READ_HAS_NO_UNIT)
            continue
        account_id = row.get("account_id")
        if not account_id:
            drop(READ_HAS_NO_ACCOUNT)
            continue
        service_code = row.get("service")
        if not service_code:
            drop(READ_HAS_NO_SERVICE)
            continue
        read_on = _read_on(row.get("read_at"))
        if read_on is None:
            drop(READ_HAS_NO_CONSUMPTION)
            continue
        is_estimated = bool(row.get("estimated"))
        if is_estimated:
            estimated += 1
        kept.append(
            UnbilledRead(
                read_id=str(row.get("id")),
                account_id=str(account_id),
                service_code=str(service_code),
                consumption=consumption,
                unit=str(unit),
                read_on=read_on,
                estimated=is_estimated,
            )
        )

    reported = list(problems)
    if estimated:
        reported.append(READS_INCLUDE_ESTIMATES)
    return UnbilledReadOutcome(
        reads=tuple(kept),
        problems=tuple(reported),
        excluded=excluded,
        estimated_count=estimated,
        considered=considered,
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-060 C2 / task T7 (12-governance/11-change-requests.md §7 · §12) ·
#         04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-006 ·
#         BR-MET-053 (the read lifecycle) · BR-TEN-013 (the seam rule) ·
#         CLAUDE.md rules 1 and 3
# generated: 2026-09-02 by the CR-060 T7 lane
# checklist: A✔ B=n/a(one cross-module read, no story) C✔ D=n/a E=n/a F✔ G✔
#         H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, ledger row written
#         under CR-060 T19)
# gates: see 06-backend/tests/test_cr060_t7_unbilled_accrual.py — the
#         unavailable-read refusal, each of the four exclusions and the
#         hot-window disclosure were each proved RED before being trusted green
# exceptions: metering publishes no `unbilled_reads`, so this seam runs on
#         `read_list` and PARKS the gap in 10-scripts/gates/seam_known_gaps.txt ·
#         `apps/metering/services.mark_read_billed`'s docstring still claims
#         nothing calls it, which DEF-098 made false — REPORTED, not edited
#         (another module's file) · the hot window is metering's and is disclosed
#         rather than defeated
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
