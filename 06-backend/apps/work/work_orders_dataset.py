# ── Trace ──────────────────────────────────────────────
# Change:   CR-142-BRC07 · the `work_orders` DATASET QUERY (brief §7.1 —
#           "datasets are code, definitions are data"; §7.2 — one dataset
#           states ONE grain; §7.5 — the two read paths).
#           Drawings read as IMAGES (B14 rule 42): p065 (R33 Service Order
#           Activity, R34 Disconnect & Reconnect), p083–p086 (§7.2/§7.2.1/
#           §7.2.1B/§7.2.2 — the dimension model and additivity), p087 (§7.5).
# Story:    R33 `service_order_activity` — Operations › Field · work orders ·
#           Event date (`reports/migrations/0003_seed_catalogue.py` line 250).
# Rules:    CLAUDE.md hard rule 1 (tenant scoping — every read through the seam
#           filters on `current_tenant_id()`, RLS FORCE underneath) · hard rule
#           3 (every quantity carries its unit — `duration` is HOURS and says
#           so) · hard rule 8 (an address is walked to `premises`; a work order
#           declares none of its own) · **the module map — `work` READS assets,
#           connections, accounts, meter reads, areas and users through ONE
#           read-only seam file per module and WRITES NONE OF THEM; `G78` fails
#           a foreign write from this module's first commit. THIS FILE WRITES
#           NOTHING AT ALL** · NFR-3 (universal server pagination — limit /
#           offset / sort applied IN SQL) · NFR-5 (no hard caps anywhere) ·
#           BR-WRK-006 (four anchors) · BR-WRK-018 (`due_at` is STAMPED at the
#           raise, never derived on read) · BR-REP-002 (read models only) ·
#           BR-REP-024 (never a 0 where a figure could not be computed) ·
#           BR-TEN-043 (the business date is an argument, never a clock)
# Tests:    06-backend/tests/test_rep_work_orders_dataset.py
#           10-scripts/ds_work_orders_dataset_cost.py (the PostgreSQL
#           measurement — hard-won law 14: the suite runs on in-memory SQLite)
# Impacts:  apps/work/seams/metering_seam.py (`work_orders_dataset_queryset`) ·
#           apps/reports/datasets.py (`WORK_ORDERS.grain`, `.paginates`) ·
#           apps/reports/queries.py (REP-UNBLOCK registers the viewer) ·
#           apps/reports/report_seams.py (the intended cross-module caller)
# ───────────────────────────────────────────────────────
"""THE `work_orders` DATASET — **one row per WORK ORDER**, paged and sorted in SQL.

═══════════════════════════════════════════════════════════════════════════════
TWO REPORTS ARE SEEDED ON THIS DATASET AND ONLY ONE OF THEM IS A REPORT ABOUT
WORK ORDERS
═══════════════════════════════════════════════════════════════════════════════
`reports/migrations/0003_seed_catalogue.py` seeds exactly two definitions whose
`dataset` is `work_orders`:

    R33  service_order_activity   Service Order Activity
    R34  disconnect_reconnect     Disconnect & Reconnect

**R33 IS SERVED FROM HERE. R34 IS NOT, AND THE REFUSAL IS DELIBERATE.**

Read R34's drawing (p065, as an image) rather than its seed row. Its eyebrow is
*"Operations › Field · **work orders + accounts** · Event date"* — two sources —
and **every drawn row is an ACCOUNT**: `ACCOUNT · CUSTOMER · BALANCE · NOTICE ·
DISCONNECTED · PAID · RECONNECTED · STATUS`, with `100907 Okafor, D. 418.90`
carrying FIVE dates and amounts strung along one line. Its own warning says so
in as many words: *"The five states are columns, not a status filter, because a
supervisor reads this to answer one question: **where is each account in the
sequence**."*

One account in the middle of a cut-and-restore cycle has a disconnect order AND
a reconnect order. At this grain it is **two rows**, each holding half the
sequence, and `Σ BALANCE` down the list **double-counts the debt**. At R34's
real grain it is one row with two dates on it. §7.2 is explicit that a dataset
states ONE grain, and this one states *one work order*.

Serving R34 from here would produce real rows, a footing total and an answer to
a question nobody asked — invisible to every gate and to the clerk. So it is
refused BY NAME, in `PROBLEMS` below, carrying the grain and the two sources it
actually needs. `BR-REP-021` (PO RP-3, 2026-08-08, CONFIRMED) independently
routes R34 to the GENERIC viewer *because its column set is unratified*, so the
catalogue card's present sentence — *"Its columns have not been agreed and
nothing supplies the rows, so no columns are invented here"* — is **HALF true
and stays**: the drawing agrees a column set, the PRODUCT OWNER has not, and
`BR-REP-021` is the signed rule that says so. Nothing here invents one.

═══════════════════════════════════════════════════════════════════════════════
THE MODULE BOUNDARY, WHICH IS THE ONE THING THIS FILE COULD BREAK
═══════════════════════════════════════════════════════════════════════════════
R33's own drawn warning is the rule, verbatim: *"Work is the eleventh module and
owns these tables; this report reads them through a seam and writes nothing. The
premises column walks to premises like every other address in the product — the
work order declares no address of its own."*

So: **no model of another module is named in this file.** The single read is
`seams.metering_seam.work_orders_dataset_queryset()`, which is where
`apps.metering.connections.WorkOrder` is named and the only place it may be
(`BR-WRK-002`; `DEF-WRK-4032` is the defect from the day `selectors.py` imported
it directly). There is no INSERT, UPDATE, DELETE or `save()` below, on any table
of any module. `G78` is the gate.

`work_orders` is metering's TABLE today and work's by ownership
(`16-work/03-field-map.md` §4, pending the blueprint's §16). Reading it through
the seam is what makes that eventual move a one-file change.

═══════════════════════════════════════════════════════════════════════════════
IT PAGES AND SORTS IN SQL, AND THE EXPORT TAKES NO `page` AND NO `per`
═══════════════════════════════════════════════════════════════════════════════
Brief §7.5 (p087): *"Sync — viewing — page 1 — returns rows with limit/offset/
sort applied in SQL. Never the whole result."*

`per` cuts the page with `[offset:offset + limit]` on a QuerySet — one
`LIMIT`/`OFFSET` — and `sort` is `order_by(*order_terms(...))`. **Nothing is
sorted or sliced in Python anywhere in this file.**

⚠ **`work_orders_dataset_stream()` IS A SEPARATE FUNCTION WITH NO `page` AND NO
`per`.** That is not tidiness: when the billing register started paging, its
export silently inherited the screen's page and produced a valid-looking file of
50 rows from a 38,000-row report. A flag would have had the same bug; **a
missing parameter cannot.** `NFR-5` forbids a ceiling on that branch and there
is none — `STREAM_CHUNK` is a fetch buffer, not a cap.

⚠ **EVERY SORT TUPLE ENDS IN A UNIQUE COLUMN.** A page is a window over an
ORDER; if the order is not total, two rows that compare equal may swap between
page 1 and page 2 and a supervisor sees one order twice and another never.
`raised_on` alone is not total — a bill-run-raised batch stamps a hundred orders
in the same second.

═══════════════════════════════════════════════════════════════════════════════
TOTALS ARE A SQL AGGREGATE OVER THE WHOLE FILTERED SET, NEVER OVER THE PAGE
═══════════════════════════════════════════════════════════════════════════════
That is what makes R33's drawn tiles — `Raised 148 · Completed 132 · Open 16 ·
Average to close 2.4 days` — foot to the report whether a page is cut or not.
It is the premise `/outstandings`'s withdrawn docstring got backwards, and the
one `invoices`, `journal_lines` and `payments` already build on.

⚠ **`open` IS COMPUTED, NOT `raised − completed`.** An order CANCELLED inside
the window is neither completed nor open, and the drawn subtraction happens to
work only because the illustration has no cancellation in it (B14 rule 37 — a
figure drawn in a wireframe is an illustration, never a fact to build to). Each
of the three is its own aggregate over its own state set.

═══════════════════════════════════════════════════════════════════════════════
ADDITIVITY (brief §7.2.2, read as an image on p085)
═══════════════════════════════════════════════════════════════════════════════
`apps/reports/datasets.py` declares three measures on this dataset and this
query honours all three:

* `orders` (COUNT) — **fully additive.** Orders raised in July plus orders
  raised in August is orders raised in the two months; the same across crews,
  types and areas. Nothing here is a balance as at a date.
* `duration` (SUM, hours) — **fully additive**, and it carries its unit
  (hard rule 3). ⚠ **IT IS TIME ON SITE, NOT THE ESTIMATE.** `est_duration` is
  what a template PLANNED; `minutes_on_site` is what the job TOOK. Summing the
  plan and calling it the work done is a different report, so the estimate is
  not served here at all and the orders with no minutes recorded are counted
  and NAMED (`GAP_DURATION_NOT_RECORDED`) rather than folded in as zero, which
  would drag every average down silently. BR-REP-024.
* `on_time_pct` (RECOMPUTE) — **NON-ADDITIVE.** §7.2.2: *"must be recomputed
  from its components, never averaged. The average of four route DSOs is not the
  utility's DSO."* It is published beside its numerator and denominator for
  exactly that reason, so a caller grouping by crew recomputes rather than
  averaging four percentages.

⚠ **`average_days_to_close` IS NON-ADDITIVE TOO AND IS NOT A DECLARED MEASURE.**
R33's drawing puts `2.4 days` in a tile and `Total 2.4` in the footer, which is
the mean of the closed orders' days — a mean of means is not a mean. It travels
in `totals` beside `completed` (its denominator) and `days_to_close_sum` (its
numerator) so the footer refusal a sibling built can show an em-dash and its
reason wherever a lawful sum is not available. It is REPORTED as a missing
measure declaration rather than added to `datasets.py` from here — that file is
shared and P0.16's declaration is where a measure's additivity is stated once.

═══════════════════════════════════════════════════════════════════════════════
WHAT IT WILL NOT DO
═══════════════════════════════════════════════════════════════════════════════
**It writes nothing**, on any table, in any module (`G78`, `BR-WRK-002`).

**It never falls back to zero.** BR-REP-024: a figure that cannot be computed is
`None` beside a named reason in `problems`. A window with no orders has a count
of `0`, which is a real answer and a different thing from *not derivable*.

**It states no clock.** `start` and `end` are arguments (BR-TEN-043): the figure
a supervisor sees at 23:58 and the figure a scheduled run takes at 00:02 must be
explainable, and a function that read the system date could not be asked for
yesterday's.

**It serves no address column of its own.** `premises_no` and `premises_address`
are both WALKED, through whichever of `BR-WRK-006`'s four anchors the order
carries (hard rule 8).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from django.db.models import Count, DurationField, ExpressionWrapper, F, Q, Sum

from apps.work.seams import metering_seam
from core.pagination import order_terms

#: BR-REP-001 is about MONEY and this dataset serves none — no column here is a
#: currency amount, so there is no basis to name and none is invented. The
#: report's own DATE basis is the raise (`Event date`, the seeded row), which is
#: what `start`/`end` filter on and what `BASIS_DATE` records for a caller that
#: needs to label the window.
BASIS_DATE = "raised"

#: Hard rule 3 — a quantity carries its unit, always, and never by convention.
#: `minutes_on_site` is stored in MINUTES and served in HOURS because
#: `apps/reports/datasets.py` declares `Column(name="duration",
#: type=TYPE_QUANTITY, unit="hours")`. The conversion is stated ONCE, here.
DURATION_UNIT = "hours"
MINUTES_PER_HOUR = Decimal("60")

#: The one place this module spells the state words, read from the owning
#: module's own constants rather than typed again — two spellings of
#: `completed` is how the approval queue and a report come to disagree about
#: what finished means.
_OPEN_STATES: tuple[str, ...] = metering_seam.OPEN_WORK_ORDER_STATES

#: What a caller may order by. Six, because six are what R33's drawn table puts
#: a column head on — `ORDER · TYPE · PREMISES · RAISED · ASSIGNED · COMPLETED ·
#: DAYS · STATUS` — minus the two that are derived rather than stored (`DAYS` is
#: an expression over two columns and `PREMISES` is a walk through four
#: anchors, so neither has a stable SQL order at this grain; offering them would
#: be a live caret over a dead control, hard-won law 2's mirror).
#:
#: ⚠ **EVERY TUPLE ENDS IN `id`.** `core.pagination.order_terms` refuses to add
#: a tiebreak silently, precisely so this stays the caller's stated decision.
WORK_ORDER_SORTS: tuple[str, ...] = (
    "raised_on",
    "completed_on",
    "order_no",
    "order_type",
    "status",
    "crew",
)
WORK_ORDER_DEFAULT_SORT = "raised_on"
WORK_ORDER_SORT_COLUMNS: dict[str, tuple[str, ...]] = {
    # ⚠ **`DEF-MET-6881` — THIS TUPLE IS WHAT `ix_work_orders_raised` EXISTS
    # FOR, AND IT WAS UNINDEXED UNTIL `metering/0062` (2026-09-27).** Being the
    # DEFAULT sort, it is the one every reader of this report pays for: at
    # 40,025 orders in one tenant PostgreSQL 16 read the whole table and sorted
    # it — `Sort Method: external merge  Disk: 4288kB` on the deep pages — and
    # the page query measured 0.0655s. It is 0.0034s now, with no `Sort` node
    # in the plan at all. **A seventh sort on a new DATE column needs its own
    # index or it arrives with this defect**; `tests/test_def_met_6881_work_
    # order_raise_index.py` goes red on the day the default moves off a covered
    # tuple, which is the only reason that test asserts the SORT and not just
    # the index.
    "raised_on": ("created_at", "id"),
    "completed_on": ("completed_at", "created_at", "id"),
    # ⚠ The ORDER NUMBER, never the uuid — B14 rule 31, and a uuid7 sorts by
    # mint time, which is not an order anybody asked for.
    "order_no": ("order_no", "id"),
    "order_type": ("type", "created_at", "id"),
    "status": ("state", "created_at", "id"),
    "crew": ("assignee_crew__name", "created_at", "id"),
}

#: The filters this dataset accepts, named here so `apps/reports/datasets.py`
#: and this query cannot drift. A filter the dataset declares and the query
#: drops shows the WHOLE set under a chip that says otherwise.
#:
#: ⚠ **THIS IS THE DATASET'S DECLARED SET EXACTLY** — `WORK_ORDERS.filters` is
#: `("from", "to", "order_type", "status", "priority", "crew", "service")` and
#: every one of the seven is applied below. R33's drawn bar offers four of them
#: (`From · To · Type · Crew`); the other three are the dataset's to offer and
#: the definition's to use, which is §7.2.1B's *"filters come from the dataset,
#: not the report"*.
WORK_ORDER_FILTERS: tuple[str, ...] = (
    "from",
    "to",
    "order_type",
    "status",
    "priority",
    "crew",
    "service",
)


# ── BR-REP-024: named gaps, never a silent zero and never a plausible number ──

GAP_R34_IS_A_DIFFERENT_GRAIN = {
    "code": "disconnect_and_reconnect_is_one_account_not_one_work_order",
    "br_ref": "brief §7.2 · §7.2.1B · BR-REP-021",
    "detail": (
        "R34 Disconnect & Reconnect is seeded onto this dataset and this dataset cannot "
        "state its grain. Its drawing (p065) is dated 'work orders + accounts' and every "
        "drawn row is an ACCOUNT carrying the whole sequence — balance, notice date, "
        "disconnected date, amount paid, reconnected date — while this dataset states one "
        "WORK ORDER. An account cut and restored inside the window has two orders, so it "
        "would appear twice and the balance column would double-count the debt. Its own "
        "warning says a supervisor reads it to answer 'where is each account in the "
        "sequence', which is one row per account by construction. BR-REP-021 separately "
        "holds its column set unratified, so nothing is invented here either."
    ),
    "wanted_reads": (
        "a dataset at ACCOUNT grain joining the disconnect and reconnect orders to the "
        "account's balance and the tenant's eligibility rule (Settings)",
    ),
}

GAP_DURATION_NOT_RECORDED = {
    "code": "some_orders_recorded_no_time_on_site",
    "br_ref": "BR-REP-024 · hard rule 3",
    "detail": (
        "`minutes_on_site` is nullable and is written when the field records it. The "
        "orders without it are counted in `duration_missing` and are NOT folded in as "
        "zero: a zero would read as a job that took no time and would drag every average "
        "down silently. `est_duration` is deliberately not substituted — a template's "
        "plan is not the work done, and serving one where a reader expects the other is "
        "the wrong answer this dataset exists to refuse."
    ),
    "wanted_reads": (),
}

GAP_ON_TIME_NEEDS_A_PROMISE = {
    "code": "on_time_is_undefined_for_an_order_with_no_due_date",
    "br_ref": "BR-WRK-018 · BR-REP-024",
    "detail": (
        "On-time compares `completed_at` with `due_at`, and `due_at` is stamped at the "
        "raise from the priority's SLA hours (BR-WRK-018 — stamped, never derived on "
        "read, so moving Urgent from 4h to 2h does not move a job already in the field). "
        "An order raised without a priority carries no promise, so it is neither on time "
        "nor late: it is excluded from BOTH sides of the percentage and counted here. The "
        "percentage is served as null rather than 0.0 when nothing was promised."
    ),
    "wanted_reads": (),
}


@dataclass(frozen=True)
class WorkOrderFactRow:
    """One work order, in the dataset's own declared column names.

    ⚠ **`premises_no` AND `premises_address` ARE BOTH WALKED (hard rule 8).**
    A work order declares no address column of its own, and this row does not
    invent one: both values come from whichever of `BR-WRK-006`'s four anchors
    the order carries. An order anchored only on an account — a move-out's final
    read — reaches no premises at all and both cells are `None`, which the
    renderer draws as an em-dash. R31's drawn rule for a spare meter is the same
    one: *"blank reads as missing data; the dash reads as not applicable."*

    ⚠ **`assigned_to` IS A CREW OR A TECHNICIAN OR NEITHER, AND THE KIND
    TRAVELS.** R33's drawing shows `Crew A` beside `M. Okonkwo` in one column,
    which is two different facts rendered alike. `assigned_kind` says which,
    so a caller grouping by crew does not silently bucket a named technician
    under a crew that does not exist.

    ⚠ **`days_to_close` IS `None` ON AN OPEN ORDER, NEVER 0.** The drawn row
    `WO-2609-0488 … — … 3 … Open` shows a DAYS figure against an order with no
    completion date, which is days-so-far rather than days-to-close; two
    different measures in one column is the trap §7.2.2 opens with, so this row
    carries `days_to_close` (closed orders only) and `days_open` (open orders
    only) and never one column meaning both.
    """

    order_id: str
    order_no: str | None
    order_type: str | None
    priority: str | None
    status: str
    crew: str | None
    technician: str | None
    assigned_to: str | None
    assigned_kind: str | None
    raised_on: date | None
    completed_on: date | None
    account_no: str | None
    premises_no: str | None
    premises_address: str | None
    service_code: str | None
    duration: Decimal | None
    duration_unit: str
    days_to_close: int | None
    days_open: int | None


def _tenant_id() -> Any:
    from core.tenancy import current_tenant_id

    return current_tenant_id()


def _base(
    *,
    start: date | None = None,
    end: date | None = None,
    order_type: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    crew_id: Any = None,
    service: str | None = None,
) -> Any:
    """The filtered set, as a QuerySet — every criterion a `WHERE`.

    ⚠ **THE WINDOW IS ON THE RAISE, WHICH IS THE SEEDED BASIS.** R33 is seeded
    `EVENT · "Event date"` and its drawn tiles count what was RAISED in the
    window. Dating it by completion instead would make `Raised 148` impossible
    to compute and would silently drop every order still open, which is the
    figure a supervisor is reading the report for.

    Tenant scoping is the seam's (`hard rule 1`), which filters on
    `current_tenant_id()` before this function sees a row, with RLS FORCE
    underneath it. Nothing here widens that.
    """
    rows = metering_seam.work_orders_dataset_queryset()
    if start is not None:
        rows = rows.filter(created_at__date__gte=start)
    if end is not None:
        rows = rows.filter(created_at__date__lte=end)
    if order_type:
        # Both spellings, because `metering/0045` put a CATALOGUE beside the
        # free text rather than replacing it (`BR-WRK-017`, `US-WRK-007` TC-6:
        # an unmatched string stays a string). Filtering only on `type_ref`
        # would hide every order raised before the catalogue existed.
        rows = rows.filter(Q(type__iexact=order_type) | Q(type_ref__code__iexact=order_type))
    if status:
        rows = rows.filter(state=status)
    if priority:
        rows = rows.filter(priority__code__iexact=priority)
    if crew_id:
        rows = rows.filter(assignee_crew_id=crew_id)
    if service:
        rows = rows.filter(service__code__iexact=service)
    return rows


def _premises_of(order: Any) -> tuple[str | None, str | None]:
    """The premises a job is AT, walked through `BR-WRK-006`'s four anchors.

    Hard rule 8: the order declares no address of its own, and neither does an
    asset, a unit or a connection — every one of them walks here. The order of
    the four is the order `apps/work/selectors._premise_of` already established,
    with the asset chain added as the fourth (that function walks three, which
    leaves an order anchored only on a meter with an empty cell).

    Costs no query: every hop is `select_related` in the seam.
    """
    row = None
    if order.connection_id and order.connection.premises_id:
        row = order.connection.premises
    elif order.premises_id:
        row = order.premises
    elif order.unit_id and order.unit.premises_id:
        row = order.unit.premises
    elif order.asset_id:
        point = getattr(order.asset, "service_point", None)
        unit = getattr(point, "unit", None) if point is not None else None
        row = getattr(unit, "premises", None) if unit is not None else None
    if row is None:
        return None, None
    return row.premise_no, row.address_line


def _duration_hours(order: Any) -> Decimal | None:
    """Time on site, in HOURS — the unit `apps/reports/datasets.py` declares.

    `None` and never `0` when nothing was recorded: hard rule 3 wants a quantity
    WITH its unit, and BR-REP-024 wants an underivable figure absent rather than
    plausible. A zero here reads as a job that took no time.
    """
    minutes = order.minutes_on_site
    if minutes is None:
        return None
    return (Decimal(int(minutes)) / MINUTES_PER_HOUR).quantize(Decimal("0.0001"))


def _shape(order: Any) -> WorkOrderFactRow:
    """One stored order, in the dataset's declared column names. No query."""
    premises_no, premises_address = _premises_of(order)
    crew = order.assignee_crew.name if order.assignee_crew_id else None
    technician = None
    if order.assignee_technician_id:
        user = getattr(order.assignee_technician, "user", None)
        technician = (getattr(user, "full_name", "") or "").strip() or None
    if crew is not None:
        assigned_to, assigned_kind = crew, "crew"
    elif technician is not None:
        assigned_to, assigned_kind = technician, "technician"
    else:
        assigned_to, assigned_kind = None, None

    raised_on = order.created_at.date() if order.created_at else None
    completed_on = order.completed_at.date() if order.completed_at else None
    days_to_close = None
    if raised_on is not None and completed_on is not None:
        days_to_close = (completed_on - raised_on).days
    days_open = None
    if completed_on is None and raised_on is not None and order.state in _OPEN_STATES:
        # ⚠ Against the ORDER's own last-touched stamp, never `date.today()`.
        # BR-TEN-043: a read that consulted a clock could not be asked for
        # yesterday's figure and would give a scheduled run a different answer
        # from the screen it is supposed to reproduce.
        seen = order.updated_at.date() if order.updated_at else raised_on
        days_open = max(0, (seen - raised_on).days)

    type_ref = order.type_ref if order.type_ref_id else None
    return WorkOrderFactRow(
        order_id=str(order.id),
        # B14 rule 31 — the WO- series number, never the uuid. Nullable by
        # design (an import path that cannot reach the series), so the absence
        # travels as an absence and the renderer decides what to draw.
        order_no=order.order_no,
        order_type=(getattr(type_ref, "name", None) or order.type or None),
        priority=getattr(order.priority, "name", None) if order.priority_id else None,
        status=order.state,
        crew=crew,
        technician=technician,
        assigned_to=assigned_to,
        assigned_kind=assigned_kind,
        raised_on=raised_on,
        completed_on=completed_on,
        account_no=getattr(order.account, "account_no", None) if order.account_id else None,
        premises_no=premises_no,
        premises_address=premises_address,
        service_code=getattr(order.service, "code", None) if order.service_id else None,
        duration=_duration_hours(order),
        duration_unit=DURATION_UNIT,
        days_to_close=days_to_close,
        days_open=days_open,
    )


#: The owning module's word for *finished*, read through the seam rather than
#: spelled again here. `apps/work/seams/metering_seam.completed_work_orders_
#: queryset` already established that one word, one state, for exactly this
#: reason: the performance tab and the approval queue must not come to disagree
#: about what finished means, and nor may a report.
#: ⚠ Resolved LAZILY, inside the query. Reading it at import time would pull
#: `apps.metering.connections` in while the app registry is still loading, and
#: a module that cannot be imported during startup is a module nothing can
#: register.
def _completed_state() -> str:
    return metering_seam.completed_work_order_state()

#: Elapsed time as an INTERVAL, summed in SQL. ⚠ A date-minus-date expression
#: is not portable — it is an integer on PostgreSQL and something else on the
#: SQLite the suite runs on (hard-won law 14's shape for arithmetic rather than
#: for transactions). A `DurationField` difference of the two TIMESTAMPS is, so
#: the sum is struck in SQL over the whole filtered set and divided ONCE in
#: Python on the aggregate — never per row.
_ELAPSED = ExpressionWrapper(F("completed_at") - F("created_at"), output_field=DurationField())
_SECONDS_PER_DAY = Decimal("86400")


def work_orders_dataset(
    *,
    start: date | None = None,
    end: date | None = None,
    order_type: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    crew_id: Any = None,
    service: str | None = None,
    page: int = 1,
    per: int | None = None,
    sort: str | None = None,
    direction: str = "desc",
) -> dict[str, Any]:
    """THE dataset query. One row per work order, paged and sorted in SQL.

    `per=None` is the whole filtered set. `per` is an integer page size; the
    CALLER clamps it (`core.pagination.clamp_page_size`) and this function does
    not invent one, because a cap invented here is a cap nobody can see
    (`NFR-5`).

    ⚠ **FOR AN EXPORT, CALL `work_orders_dataset_stream()` INSTEAD** — it takes
    no `page` and no `per`, so an export has no argument through which to
    inherit a screen's fifty rows.

    **`totals` IS A SQL AGGREGATE OVER THE WHOLE FILTERED SET AND NEVER OVER THE
    PAGE**, so R33's tiles foot to the report whether a page is cut or not.
    """
    rows = _base(
        start=start,
        end=end,
        order_type=order_type,
        status=status,
        priority=priority,
        crew_id=crew_id,
        service=service,
    )

    completed_q = Q(state=_completed_state())
    open_q = Q(state__in=_OPEN_STATES)
    # ⚠ ONE aggregate call, so every figure is struck over the same snapshot of
    # the same rows. Two round trips could see two different worlds if an order
    # completed between them, and *"raised and completed were read a
    # millisecond apart"* is not a defect anybody would diagnose from a report
    # that does not foot.
    aggregated = rows.aggregate(
        raised=Count("id"),
        completed=Count("id", filter=completed_q),
        # ⚠ NOT `raised − completed`. A CANCELLED order is neither, and the
        # drawn subtraction works only because the illustration has none in it.
        open_now=Count("id", filter=open_q),
        duration_minutes=Sum("minutes_on_site"),
        duration_missing=Count("id", filter=Q(minutes_on_site__isnull=True)),
        elapsed=Sum(_ELAPSED, filter=completed_q),
        promised=Count("id", filter=completed_q & Q(due_at__isnull=False)),
        on_time=Count(
            "id", filter=completed_q & Q(due_at__isnull=False, completed_at__lte=F("due_at"))
        ),
    )

    raised = int(aggregated["raised"] or 0)
    completed = int(aggregated["completed"] or 0)
    promised = int(aggregated["promised"] or 0)
    duration_missing = int(aggregated["duration_missing"] or 0)

    problems: list[dict[str, Any]] = [dict(GAP_R34_IS_A_DIFFERENT_GRAIN)]
    if duration_missing:
        problems.append(dict(GAP_DURATION_NOT_RECORDED))
    if completed and not promised:
        problems.append(dict(GAP_ON_TIME_NEEDS_A_PROMISE))

    duration_minutes = aggregated["duration_minutes"]
    duration_hours = (
        None
        if duration_minutes is None
        else (Decimal(int(duration_minutes)) / MINUTES_PER_HOUR).quantize(Decimal("0.0001"))
    )

    elapsed = aggregated["elapsed"]
    days_sum = (
        None
        if elapsed is None
        else (Decimal(int(elapsed.total_seconds())) / _SECONDS_PER_DAY).quantize(Decimal("0.0001"))
    )
    # ⚠ NON-ADDITIVE (§7.2.2) — recomputed from its components, never averaged.
    # Both components travel beside it so a caller grouping by crew recomputes
    # rather than averaging four means, and so the footer refusal a sibling
    # built can print an em-dash and the reason where a sum is not lawful.
    average_days_to_close = (
        None
        if not completed or days_sum is None
        else (days_sum / Decimal(completed)).quantize(Decimal("0.1"))
    )
    # BR-REP-024 — null, never 0.0, when nothing was promised. A 0% on-time
    # rate and "nobody promised a date" are opposite facts.
    on_time_pct = (
        None
        if not promised
        else (Decimal(int(aggregated["on_time"] or 0)) * 100 / Decimal(promised)).quantize(
            Decimal("0.000001")
        )
    )

    # ── the page, cut in SQL ────────────────────────────────────────────────
    ordered = rows.order_by(
        *order_terms(
            sort,
            direction,
            columns=WORK_ORDER_SORT_COLUMNS,
            default=WORK_ORDER_DEFAULT_SORT,
        )
    )

    served_page = max(1, int(page or 1))
    if per is None:
        window = ordered
        pages = 1
    else:
        size = max(1, int(per))
        pages = max(1, -(-raised // size)) if raised else 1
        served_page = min(served_page, pages)
        offset = (served_page - 1) * size
        window = ordered[offset : offset + size]

    shaped = tuple(_shape(order) for order in window)

    return {
        "basis": BASIS_DATE,
        "grain": "one work order",
        "rows": shaped,
        "totals": {
            # Fully additive (§7.2.2) — sum freely, in any direction.
            "orders": raised,
            "raised": raised,
            "completed": completed,
            "open": int(aggregated["open_now"] or 0),
            "duration": duration_hours,
            "duration_unit": DURATION_UNIT,
            "duration_missing": duration_missing,
            # Non-additive — published WITH their components (§7.2.2).
            "average_days_to_close": average_days_to_close,
            "days_to_close_sum": days_sum,
            "on_time_pct": on_time_pct,
            "on_time": int(aggregated["on_time"] or 0),
            "promised": promised,
        },
        "additivity": {
            "orders": "full",
            "raised": "full",
            "completed": "full",
            "open": "semi",
            "duration": "full",
            "average_days_to_close": "non",
            "on_time_pct": "non",
        },
        "page": served_page,
        "per": per,
        "pages": pages,
        "total": raised,
        "problems": tuple(problems),
    }


#: How many rows one round trip of the export fetches. A BUFFER, not a cap
#: (`NFR-5`): the generator runs until the cursor is exhausted and there is no
#: number any row can be beyond. It exists so a 40,000-row file does not become
#: 40,000 dataclasses in memory at once.
STREAM_CHUNK = 2_000


def work_orders_dataset_stream(
    *,
    start: date | None = None,
    end: date | None = None,
    order_type: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    crew_id: Any = None,
    service: str | None = None,
    sort: str | None = None,
    direction: str = "desc",
) -> Iterator[WorkOrderFactRow]:
    """EVERY row of the filtered set, streamed — **no `page`, no `per`.**

    ⚠ **THE ABSENCE OF THOSE TWO PARAMETERS IS THE WHOLE DESIGN.** An export
    cannot inherit a screen's fifty rows because there is no argument through
    which to pass them. A flag would have had the same bug; a missing parameter
    cannot.

    ⚠ **`NFR-5` — NO CAP ANYWHERE ON THIS PATH.** `STREAM_CHUNK` is a fetch
    buffer; the loop runs until the cursor is exhausted.

    The order is applied IN SQL, through the same `order_terms` the page uses,
    so the file and the screen sort identically.
    """
    rows = _base(
        start=start,
        end=end,
        order_type=order_type,
        status=status,
        priority=priority,
        crew_id=crew_id,
        service=service,
    ).order_by(
        *order_terms(
            sort,
            direction,
            columns=WORK_ORDER_SORT_COLUMNS,
            default=WORK_ORDER_DEFAULT_SORT,
        )
    )
    for order in rows.iterator(chunk_size=STREAM_CHUNK):
        yield _shape(order)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 Phase 2 · lane DS-SMALL (the `work_orders` dataset query)
# screens: none of its own — 2·1 and 2·2 render every dataset
# generated: 2026-09-27 by lane DS-SMALL
# exceptions: (1) R34 `disconnect_reconnect` is seeded onto this dataset and is
#   REFUSED BY NAME rather than served — its drawn grain is one ACCOUNT and its
#   drawn source is `work orders + accounts` (p065, read as an image);
#   `GAP_R34_IS_A_DIFFERENT_GRAIN` carries the grain and the reads it needs ·
#   (2) `average_days_to_close` is served and is NOT a declared measure on
#   `WORK_ORDERS` — REPORTED for `datasets.py`, whose owner declares additivity
#   once · (3) `premises_address` and `days_to_close` are served and are not
#   declared columns either; both are drawn on R33 and both are derivations
#   rather than stored facts
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
