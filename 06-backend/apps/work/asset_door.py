# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-038 (EP-WRK-07) — the Assets door: one form, four ways in.
#           Screens: Work-028 (`RaiseWorkOrderPage`), Work-020, and the
#           Maintenance history panel on `AssetDetailPage` (S53 · AST-07).
# Rules:    BR-WRK-056 (the door is ONE form at
#           `/{tenant}/assets/{assetId}/work-orders/new`; it writes
#           `work_orders.asset_id`; templates are filtered by *applies to asset
#           types*) · BR-WRK-002 (Work writes no other module's tables) ·
#           BR-WRK-006 (an asset is an anchor) · CLAUDE.md hard rule 1
# Tests:    06-backend/tests/test_us_wrk_038_asset_door.py (TC-1…TC-7,
#           including the grep case: `apps/assets/**` writes nothing to
#           `work_orders`)
# Impacts:  apps/work/api.py (two routes) · apps/work/seams/metering_seam.py
#           (`orders_for_asset_queryset`, `template_asset_type_ids`) ·
#           07-frontend/src/features/assets/RaiseWorkOrderPage.tsx
# ───────────────────────────────────────────────────────
"""The Assets door — Work serves it, and `apps/assets` writes nothing.

WHICH WAY ROUND THE DEPENDENCY GOES, AND WHY IT IS THE WHOLE TASK
────────────────────────────────────────────────────────────────────────────
A clerk standing on an asset wants to raise a job. The three-line way to build
that is a POST in `apps/assets/` that inserts a `work_orders` row, and it is
forbidden: `work_orders` is not the assets module's table, `A7` is the gate that
says so, and `BR-WRK-056` states the rule in its own words. **So the door is
served from HERE**, on asset-shaped addresses, exactly as
`GET /premises/{id}/work-orders` and `GET /accounts/{id}/work-orders` already
are. `apps/assets/**` gains no line of code at all — which is a stronger
statement than "assets writes nothing to work_orders", and it is the one a grep
test can prove.

AND THE MAINTENANCE HISTORY'S WORK-ORDER COLUMN IS A **READ**, NOT A COLUMN
────────────────────────────────────────────────────────────────────────────
`BR-WRK-056`: *"no column is added to `AssetMaintenance`"*. `asset_maintenance`
carries `cost` and nothing about a job (CR-028 D3), and r10 draws the history
with a DIFFERENT work order on each row and a dash on the third — so the picture
needs a per-ROW link that the schema does not have and may not grow.

⚠ **THE LINK IS THEREFORE BY DATE, AND THAT IS A JUDGMENT WORTH STATING RATHER
THAN BURYING.** `maintenance_order_index` returns *this asset's orders, keyed by
the DATE each one belongs to*, and the screen stamps a maintenance row with the
order sharing its date. A row with no order on its date keeps the dash — which
is precisely r10's third row (*Mar 12, 2024 · Commissioning accuracy test* ·
`—`), a test done before any work-order system existed.

The alternative shapes were both worse:
  * **a column on `asset_maintenance`** — forbidden by the rule, and it would
    have to be back-filled by guessing for every row already written;
  * **the same order on every row** — the only thing a per-ASSET read can
    honestly say, and on screen it reads as *this repair came from that job*
    for every repair at once, which is a per-row claim the data cannot support.

**A date match can be wrong and a dash cannot lie**, so where two orders share
one date the index keeps the FIRST and the screen shows one order rather than
inventing a list; where none matches, the cell stays as it is today. The
decision and this reasoning are in `12-governance/02-decision-log.md`.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from apps.work import selectors
from apps.work.seams import assets_seam, metering_seam

# Hard rule 2: money is STORED to 4 decimals and DISPLAYED to 2. `_CENT` is the
# rounding a DISPLAYED line takes (BR-WRK-051's "rounded displayed lines");
# `_MONEY` is the precision the wire carries.
_CENT = Decimal("0.01")
_MONEY = Decimal("0.0001")


def orders_for_asset(asset_id: Any, *, page: Any = 1, per: Any = 50) -> dict[str, Any]:
    """`GET /assets/{id}/work-orders` — every job raised against this asset.

    The row shape is the one every other list of work orders in this product
    uses, so the account tab, the premises tab, the dispatcher's queue and this
    one cannot describe the same order four ways.

    A cross-tenant id yields an EMPTY PAGE rather than a 404, and that is the
    same sentence as *"nothing has been raised for this asset"*: the seam filters
    by the tenant in context with RLS `FORCE` underneath, so Lone Star Ridge
    cannot learn that one of Brazos Bend's assets exists (hard rule 1).
    """
    # `_scoped_page` is `selectors`' own paging helper and is private by name
    # only — reusing it is what keeps this list's shape identical to the other
    # three. Copying it here would be the second shape this docstring warns
    # about, arriving by the back door.
    return selectors._scoped_page(
        metering_seam.orders_for_asset_queryset(asset_id), page, per
    )


def maintenance_order_index(asset_id: Any) -> dict[str, str]:
    """`{date: order_no}` for this asset — the Maintenance history's column.

    See the module docstring for why the key is a DATE. The value is the
    HUMAN-FACING order number (`WO-4908`) and never the row's uuid: B14 rule 31
    forbids a database id being the visible value of a field, and this map is
    consumed by a screen.
    """
    index: dict[str, str] = {}
    for row in metering_seam.orders_for_asset_queryset(asset_id):
        # An order belongs to the day it was COMPLETED where it has one, and
        # otherwise to the day it was raised. A newly raised job has no
        # completion date and must still appear — that is the demo's own step
        # 5, where `WO-4908` shows up in the history the moment it is raised.
        moment = getattr(row, "completed_at", None) or row.created_at
        if moment is None:
            continue
        key = moment.date().isoformat()
        # FIRST WINS, and the queryset is newest-first, so where two orders
        # share a date the more recent one is shown. One order, never a list —
        # a cell that sometimes holds two numbers is a cell nobody can read.
        index.setdefault(key, row.order_no)
    return index


def cost_rollup_for_asset(asset_id: Any) -> dict[str, Any]:
    """`AST-B-21` — what the JOBS on this asset have cost, and how many are open.

    ⚠ **THIS IS A READ PUBLISHED BY WORK, NOT ARITHMETIC DONE BY ASSETS.**
    `BR-WRK-051` names `costing.work_order_cost_lines` as *"the ONE place the
    arithmetic lives"*, so this function calls it once per order and adds the
    per-order totals it hands back. It computes no line and prices nothing.
    `apps/assets` reaches it through its own seam, exactly as it reaches
    metering for a read count — the module that owns `work_orders` answers for
    them.

    ⚠ **ROUND-THEN-SUM, AND THE REASON IS ON SCREEN RATHER THAN IN A LEDGER.**
    `BR-WRK-051` says *"the total is the sum of the ROUNDED displayed lines"*,
    and the asset's own `maintenance_lifetime_cost()` sums at 4 dp and
    quantizes once (sum-then-round). A single combined figure cannot obey both.
    It obeys `BR-WRK-051`, because the figure sits **above two named halves on
    the same panel** and a clerk who adds the two numbers they can see must get
    the number they are shown. Worked: repairs `84.0060` + jobs `138.4160`
    displays `$84.01 + $138.42 = $222.43`, where sum-then-round gives
    `222.4220` and displays `$222.42` over those same two lines. **That one
    cent is the whole reason this is written down** — and the first worked pair
    tried here (`84.0000` / `138.4150`) reads `$222.42` BOTH ways, so it proved
    nothing and was replaced.

    ⚠ **AN OPEN JOB HAS NO COST, AND THAT IS NOT A GAP.** `WorkOrderCostLine`
    rows are persisted at ACCEPTANCE, so `jobs_costed` counts accepted work and
    `open_orders` counts `OPEN_WORK_ORDER_STATES`. The two never overlap, and
    the screen names the first half *Work orders* rather than *Jobs*, so
    nobody reads the money as covering the open ones.

    `cost` is None — never `"0.0000"` — when no order on this asset carries a
    cost line at all: *nobody has spent anything here* and *we spent zero* are
    different facts, and the asset's own maintenance sum already draws that
    distinction (`selectors.maintenance_lifetime_cost`).
    """
    from apps.work import costing

    orders = list(metering_seam.orders_for_asset_queryset(asset_id))
    total = Decimal("0")
    costed = 0
    for order in orders:
        _lines, amount = costing.work_order_cost_lines(order)
        if amount is None:
            continue
        rounded = Decimal(amount).quantize(_CENT)
        if rounded == 0:
            continue
        total += rounded
        costed += 1
    open_orders = sum(
        1 for order in orders if getattr(order, "state", None) in metering_seam.OPEN_WORK_ORDER_STATES
    )
    return {
        # 4 dp on the wire (hard rule 2), displayed at 2 — and the value is
        # already a whole number of cents, because it is a sum of cents.
        "cost": None if costed == 0 else str(total.quantize(_MONEY)),
        "jobs_costed": costed,
        "open_orders": open_orders,
    }


def templates_for_asset(asset_id: Any) -> dict[str, Any]:
    """The templates a clerk may raise FOR THIS ASSET — `BR-WRK-056`.

    ⚠ **FILTERED BY `wot_asset_types`, AND AN UNRESTRICTED TEMPLATE APPLIES TO
    EVERYTHING.** A template that names NO asset types is not a template that
    applies to none — it is one nobody has restricted, and hiding it would make
    the door useless on the day a utility first opens it, before anybody has
    filled in the asset-types tab. So the filter reads: *this template names
    this asset's type, or it names no types at all.*

    A template that IS restricted and does not name this asset's type is
    excluded, which is the demo's step 4 — *only templates for this kind of
    meter are offered*.
    """
    asset = assets_seam.asset(asset_id)
    if asset is None:
        # A cross-tenant or unknown asset offers nothing, and says so as an
        # empty list rather than as a 404 — the same posture as the list above.
        return {"asset": None, "rows": []}

    # `assets_seam.asset` does not carry the type id, so it is read here through
    # the same seam rather than by reaching into the assets models.
    asset_type_id = assets_seam.asset_type_id(asset_id)

    rows: list[dict[str, Any]] = []
    for template in metering_seam.templates_queryset():
        if not getattr(template, "active", False) or int(getattr(template, "version", 0) or 0) < 1:
            # `BR-WRK-012`/`BR-WRK-016` — a deactivated or draft template is not
            # offered. The same refusal `from_flows` gives, so a clerk meets one
            # rule and not two.
            continue
        named = metering_seam.template_asset_type_ids(template.id)
        if named and (asset_type_id is None or str(asset_type_id) not in named):
            continue
        rows.append(
            {
                "id": str(template.id),
                "name": template.name,
                "scope": template.scope,
                "restricted": bool(named),
            }
        )
    rows.sort(key=lambda row: row["name"] or "")
    return {
        "asset": {
            "id": asset["id"],
            "asset_no": asset["asset_no"],
            "asset_type_id": str(asset_type_id) if asset_type_id else None,
        },
        "rows": rows,
    }


__all__ = ["maintenance_order_index", "orders_for_asset", "templates_for_asset"]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-038@5e48ae29 (EP-WRK-07) · 10-execution-plan.md wave M task M2
# generated: 2026-09-05 by the CR-070 wave M build lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a(no 🔒 path — the migration is wave M's M1)
# gates: pytest tests/test_us_wrk_038_asset_door.py · G78 · A7 (apps/assets writes no work_orders row)
# exceptions: the maintenance column's per-row link is BY DATE and is a judgment, not a stored fact — stated in the module docstring and recorded in the decision log, because the schema has no per-row link and BR-WRK-056 forbids adding one
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
