# ── Trace ──────────────────────────────────────────────
# Epics:    EP-LED-04 (the month-end postings — CR-060 C20 / task T7f)
#           Screens: S49 (the asset registry the figures come from)
#           NOTE: no US-ID is cited here ON PURPOSE. G10 reads a Trace-header
#           US-ID as "this file ships that story's TCs"; this file ships one
#           cross-module READ, not a story. Same precedent as
#           apps/ledger/metering_seam.py, billing_seam.py and tenancy_seam.py.
# Rules:    BR-TEN-013 (a module NEVER touches another module's ORM; a
#           cross-module read resolves the owner's published callable) ·
#           BR-AST-047 (straight-line book value: cost, method, expected life —
#           the ONE computation, and it lives in assets) · BR-REP-002 (a report
#           never recomputes money) · CLAUDE.md rule 1 (tenant scoping, inherited
#           from assets' own scoped read and never re-implemented here) · rule 2
# Tests:    06-backend/tests/test_cr060_t7f_depreciation.py
# Impacts:  apps/ledger/depreciation.py (its only caller)
# ───────────────────────────────────────────────────────
"""ledger → assets SEAM: **how much did the plant depreciate in this period?**

HUMAN-OWNED · HUMAN-REVIEW-PENDING — a wrong answer here is a wrong figure in
the trial balance. AI-authored 2026-09-02 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*); the row is in
`12-governance/09-human-review-ledger.md` under CR-060 task T19.

════════════════════════════════════════════════════════════════════════════
THIS SEAM COMPUTES NO DEPRECIATION. IT SUBTRACTS TWO FIGURES ASSETS PRODUCES.
════════════════════════════════════════════════════════════════════════════
CR-060 C20 is explicit that the number already exists: *"The assets module
already computes accumulated depreciation and book value from the purchase cost,
method and expected life, and shows them on screen. Nothing posts them."* T7f's
own row says the same in the other direction — *"this is a posting path and a
period trigger, not a calculation"*.

So the period's charge is **a difference of two of assets' own answers**:

    charge(period) = accumulated(period_end) − accumulated(day before period_start)

Both terms come from `apps.assets.selectors.asset_book_value`, which is
BR-AST-047's single implementation and carries its own ratified-figure verdict
($19.8167 against r10's $19.83 — *"the formula is not bent to meet a figure no
month arithmetic produces"*). **Nothing in this file multiplies a cost by a
life.** A second implementation of that arithmetic is exactly what BR-REP-002
and CR-060 §13 forbid, and it is how the screen and the books would come to
disagree about the same truck.

⚠ **AND A DIFFERENCE IS WHY RE-RUNNING IS SAFE.** Each period posts only its own
movement, so an asset bought two years ago does not re-post two years of charge
the first time a utility presses the button — it posts this month's slice, and
the months before it stay unposted rather than arriving in a lump nobody asked
for. What that leaves behind is stated on the caller (`depreciation.py`) and
carried on every answer.

════════════════════════════════════════════════════════════════════════════
THE PREFERRED READ, AND THE FALLBACK THAT KEEPS THE FIGURE HONEST
════════════════════════════════════════════════════════════════════════════
The contract this seam wants from assets is `DEPRECIATION_MOVEMENT_READ` below:
one call, one answer, computed inside the module that owns the arithmetic.
**Assets does not publish it today.** Rather than leave the posting dark
(hard-won law 2, *built is not wired*), this seam falls back to assets' OWN two
published callables — the tenant-scoped `asset_list()` queryset and
`asset_book_value()`, called twice per asset — which is the exact shape
`apps/ledger/metering_seam.py` and `billing_seam.py` use, and for the same
reasons: a documented preferred read, a published fallback, **no assets model
import**, and no assets file edited. The gap is PARKED in
`10-scripts/gates/seam_known_gaps.txt` so G20 names it on every run and goes RED
the day the preferred read appears.

════════════════════════════════════════════════════════════════════════════
WHAT IS EXCLUDED, AND WHY EVERY EXCLUSION IS COUNTED
════════════════════════════════════════════════════════════════════════════
  * **AN ASSET WITH NO PURCHASE COST OR NO EXPECTED LIFE.** `asset_book_value`
    answers `None` for it — the honest *"no purchase cost recorded"* state it
    documents, *"never a fabricated $0.00"*. Excluded and COUNTED, never
    depreciated at zero, because a utility with fifty unpriced meters should see
    fifty in that count rather than a small charge that looks finished.
  * **A RETIRED OR DISPOSED ASSET.** `asset_list`'s default status filter
    excludes the terminal stage (BR-AST-005) and this seam takes that default
    deliberately. `asset_book_value` knows an asset's LIFE and not its
    retirement, so including them would keep charging depreciation on plant that
    has left the utility. The cost is that an asset retired MID-period loses the
    part-month it was still in service: the charge is understated, never
    overstated, and understating is the direction to be wrong in when the entry
    is immutable. Counted as `retired_assets_are_not_depreciated`, with the
    number, on every answer.
  * **AN ASSET WHOSE MOVEMENT IS ZERO** — fully depreciated, or bought after the
    period ended. Not an exclusion and not a line: it simply contributes 0.00.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from importlib import import_module
from typing import Any

#: Assets' published read layer, named once so the contract is greppable from
#: BOTH sides of the boundary.
ASSETS_MODULE = "assets"

#: THE PREFERRED READ, and the contract for the lane that publishes it:
#:
#:     apps.assets.selectors.depreciation_movement(
#:         *, period_start: date, period_end: date
#:     ) -> Iterable[Mapping]
#:         each mapping carrying asset_id · asset_no · charge (Decimal) ·
#:         accumulated_at_end (Decimal) · purchase_cost (Decimal)
#:
#: Assets does not publish it today, so the fallback below calls assets' own
#: `asset_list` and `asset_book_value`. PARKED in
#: 10-scripts/gates/seam_known_gaps.txt with
#: `alt=apps.assets.selectors.asset_book_value`, so G20 names the gap on every
#: run and goes RED the day the preferred read appears.
DEPRECIATION_MOVEMENT_READ = "depreciation_movement"

#: The two published fallbacks — assets' own tenant-scoped registry queryset and
#: BR-AST-047's single book-value computation.
ASSET_LIST_READ = "asset_list"
ASSET_BOOK_VALUE_READ = "asset_book_value"

#: Reported when assets publishes NEITHER path. The posting then refuses rather
#: than charging zero: a zero depreciation entry reads as *"the plant did not
#: depreciate"*, which is a claim about a balance sheet.
MOVEMENT_UNAVAILABLE = "depreciation_movement_read_is_unavailable"

#: The named exclusions, each carrying a COUNT on the outcome.
ASSET_HAS_NO_COST_OR_LIFE = "asset_has_no_purchase_cost_or_expected_life"
RETIRED_NOT_DEPRECIATED = "retired_assets_are_not_depreciated"

ZERO = Decimal("0")


@dataclass(frozen=True)
class AssetCharge:
    """One asset's depreciation for the period, as the posting will use it."""

    asset_id: str
    asset_no: str
    charge: Decimal
    accumulated_at_end: Decimal
    purchase_cost: Decimal


@dataclass(frozen=True)
class DepreciationOutcome:
    """The period's charges, and everything left out of them, by name.

    `charges is None` means **unanswerable** and is never conflated with an
    empty tuple: *"assets publishes nothing this seam can read"* and *"nothing
    depreciated"* are different facts, and only one of them may be posted at
    zero — which is to say, neither.
    """

    charges: tuple[AssetCharge, ...] | None
    problems: tuple[str, ...] = field(default=())
    excluded: dict[str, int] = field(default_factory=dict)
    considered: int = 0


def _resolve(attribute: str, kind: str = "selectors") -> Any:
    """Assets' callable, or None while it has not published one."""
    try:
        target = import_module(f"apps.{ASSETS_MODULE}.{kind}")
    except ImportError:  # pragma: no cover — defensive
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


def _as_decimal(value: Any) -> Decimal | None:
    """A money figure arrives as a Decimal or as the string assets serialises.

    `asset_book_value` returns its figures as STRINGS (they are built for a
    payload), and a string is parsed here rather than in the caller so exactly
    one place knows that. A float is REFUSED rather than converted, for
    `billing_seam._as_decimal`'s reason: it would hide the place where the
    figure became a binary fraction, in a number about to be posted.
    """
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, str):
        return Decimal(value)
    raise TypeError(
        "a book-value figure must be a Decimal or the string assets serialises "
        f"(CLAUDE.md rule 2 — money is never a float); got {type(value).__name__}"
    )


def depreciation_movement(*, period_start: date, period_end: date) -> DepreciationOutcome:
    """Each asset's depreciation charge FOR THIS PERIOD, from assets' own figures.

    The preferred read if assets publishes it; otherwise
    `accumulated(period_end) − accumulated(period_start − 1 day)` per asset,
    using assets' single computation at both ends. See the module docstring.
    """
    preferred = _resolve(DEPRECIATION_MOVEMENT_READ)
    if preferred is not None:  # pragma: no cover — assets does not publish it yet
        rows = tuple(preferred(period_start=period_start, period_end=period_end))
        charges = tuple(
            AssetCharge(
                asset_id=str(row["asset_id"]),
                asset_no=str(row["asset_no"]),
                charge=_as_decimal(row["charge"]) or ZERO,
                accumulated_at_end=_as_decimal(row.get("accumulated_at_end")) or ZERO,
                purchase_cost=_as_decimal(row.get("purchase_cost")) or ZERO,
            )
            for row in rows
        )
        return DepreciationOutcome(charges=charges, considered=len(charges))

    listing = _resolve(ASSET_LIST_READ)
    book_value = _resolve(ASSET_BOOK_VALUE_READ)
    if listing is None or book_value is None:
        return DepreciationOutcome(charges=None, problems=(MOVEMENT_UNAVAILABLE,))

    # `asset_list`'s DEFAULT status filter excludes the terminal stage
    # (BR-AST-005) — taken deliberately, see the module docstring. The `all` tab
    # is read separately for the COUNT alone, so the exclusion is a number a
    # reviewer can see rather than a silence.
    live = list(listing())
    every = list(listing(filters={"status": "all"}))
    excluded: dict[str, int] = {}
    retired = len(every) - len(live)
    if retired > 0:
        excluded[RETIRED_NOT_DEPRECIATED] = retired

    opening_day = period_start - timedelta(days=1)
    charges: list[AssetCharge] = []
    for asset in live:
        closing = book_value(asset, as_of=period_end)
        if closing is None:
            excluded[ASSET_HAS_NO_COST_OR_LIFE] = excluded.get(ASSET_HAS_NO_COST_OR_LIFE, 0) + 1
            continue
        opening = book_value(asset, as_of=opening_day)
        accumulated_end = _as_decimal(closing["accumulated_depreciation"]) or ZERO
        accumulated_start = (
            _as_decimal(opening["accumulated_depreciation"]) if opening is not None else ZERO
        ) or ZERO
        charges.append(
            AssetCharge(
                asset_id=str(asset.pk),
                asset_no=str(getattr(asset, "asset_no", "")),
                charge=accumulated_end - accumulated_start,
                accumulated_at_end=accumulated_end,
                purchase_cost=_as_decimal(closing["purchase_cost"]) or ZERO,
            )
        )
    return DepreciationOutcome(
        charges=tuple(charges), excluded=excluded, considered=len(live)
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-060 C20 + task T7f (12-governance/11-change-requests.md §7 · §12 ·
#         §13) · 04-docs/05-modules/03-assets/02-business-rules.md BR-AST-047 ·
#         04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-793 ·
#         CLAUDE.md hard rules 1, 2, 5
# generated: 2026-09-02 by the CR-060 T7b/T7d/T7f lane
# checklist: A✔ B=deferred(a seam has no backend surface of its own) C✔
#         D=deferred E=deferred F✔ G✔ H=deferred(PO 2026-08-09 — 🔒
#         HUMAN-REVIEW-PENDING, row written under CR-060 T19)
# gates: see 06-backend/tests/test_cr060_t7f_depreciation.py — the seam is
#         driven through the posting service it feeds, and the exclusion counts
#         are asserted rather than described
# exceptions: (1) THE PREFERRED READ IS NOT PUBLISHED — parked in
#         10-scripts/gates/seam_known_gaps.txt with its alternative, so G20
#         names it every run · (2) RETIRED ASSETS ARE NOT DEPRECIATED and the
#         part-month a mid-period retirement loses is UNDER-stated rather than
#         over-stated, counted on every answer · (3) `depreciation_method` is
#         read as stored and only straight-line is computed — that is
#         BR-AST-047's own stated limit, in assets, and this seam does not
#         widen it
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
