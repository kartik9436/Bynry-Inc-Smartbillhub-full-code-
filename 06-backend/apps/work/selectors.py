# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-004 (EP-WRK-01) — the Work shell's Orders tab, template W1:
#           every open order across every connection and every account.
#           US-WRK-001 — an order with no connection is in the list and its
#           CONNECTION cell is a dash. Screens: Work-007 (the head and the
#           table only; the KPI strip, the six filters and the bulk row are
#           wave G's — `WM-16`, `WM-17`)
# Rules:    BR-WRK-006 (four anchors; the premise comes from whichever one the
#           order has) · BR-WRK-002 (read through the seam, never the model) ·
#           BR-SHL-011 (q/page/per fall back or clamp, never error) ·
#           CLAUDE.md hard rule 1 (the tenant in context; RLS underneath)
# Tests:    06-backend/tests/test_us_wrk_004_orders_list.py
# Impacts:  apps/work/api.py (serves this) · 07-frontend/src/features/work/
#           workEndpoints.ts (types it) · OrdersPage.tsx (draws it)
# ───────────────────────────────────────────────────────
"""work read side — the Orders tab's list.

ONE READ, EVERY ANCHOR
----------------------
`open_orders()` pages the seam's open-order queryset and shapes one row per
order: ORDER · TYPE · PREMISE · SVC · STATE · OUTCOME · CONNECTION, plus the
ids a row action will need. The PREMISE is read from whichever anchor the
order has — the connection's premises, the order's own `premises_id`, or the
unit's premises — and the CONNECTION is `null` when there is none, which the
screen draws as a dash (US-WRK-001 TC-1 · Work-009's convention).

Sorted by order number, ascending, id as the tiebreak: the dispatcher's
columns (priority, due) arrive in wave G and the sort follows them then
(Work-007's footer: *"sorted by priority then due time"*). Until they exist a
sort by a column nobody can see would be a control onto nothing.

`q` matches the order number, the type, the premise address and the connection
number — the four things a clerk types (Work-007's box: *"Search WO #,
premise…"*). Applied in SQL BEFORE paging, for `DEF-1702`'s reason: a filter
over the page in hand is a subset of a subset.

THE SECOND READ — THE QUEUE THAT IS A NULL (CR-070 wave B)
----------------------------------------------------------
`awaiting_approval()` is `Work-009`: every order the field has FINISHED and
nobody has accepted, oldest first, with the days each has been waiting and the
footer's *oldest waiting* figure computed over the whole queue rather than the
page. `BR-WRK-007` — **no new table; the queue was always in the schema** and
had no screen. The two reads in this file are disjoint by construction: one
window is `planned · in_progress · blocked`, the other is `completed` with a
null `accepted_by`.
"""

from __future__ import annotations

import math
from typing import Any

from decimal import ROUND_HALF_UP, Decimal

from django.db.models import F, Q
from django.db.models.functions import Lower
from django.utils import timezone

from apps.work import models as work_models
from apps.work import packs as work_packs
from apps.work.seams import metering_seam
from core import errors
from core import tenancy as core_tenancy
from core.pagination import DEFAULT_PAGE_SIZE, clamp_page_size, filter_values


def _premises_row(order: Any) -> Any:
    """The premises ROW a job is at, walked from whichever anchor carries one —
    hard rule 8: the job declares no address, every anchor walks there.

    ⚠ **FIVE HOPS, AND THE LAST TWO WERE MISSING (`DEF-WRK-9622`).** A job
    raised from a move-out, a move-in, a transfer or a reconnect stands on an
    ACCOUNT (`BR-WRK-006`), and the walk stopped at the unit — so every one of
    them read *Premise —* on the Orders list. The account walks through its
    unit; a meter-only job walks asset → service point → unit.
    """
    if order.connection_id and order.connection.premises_id:
        return order.connection.premises
    if order.premises_id:
        return order.premises
    if order.unit_id and order.unit.premises_id:
        return order.unit.premises
    account = order.account if order.account_id else None
    unit = getattr(account, "unit", None) if account is not None else None
    if unit is not None and unit.premises_id:
        return unit.premises
    asset = order.asset if getattr(order, "asset_id", None) else None
    point = getattr(asset, "service_point", None) if asset is not None else None
    unit = getattr(point, "unit", None) if point is not None else None
    if unit is not None and unit.premises_id:
        return unit.premises
    return None


def _unit_row(order: Any) -> Any:
    """The unit a job stands on, or None — the order's own unit, the account's
    unit, the meter's unit, in `metering_seam._JOB_UNIT_CHAIN`'s order, so the
    phone's card and Nearby (`nearby_jobs_queryset`) agree about which unit's
    point a job reads."""
    if getattr(order, "unit_id", None):
        return order.unit
    account = order.account if getattr(order, "account_id", None) else None
    if account is not None and getattr(account, "unit_id", None):
        return account.unit
    asset = order.asset if getattr(order, "asset_id", None) else None
    point = getattr(asset, "service_point", None) if asset is not None else None
    return getattr(point, "unit", None) if point is not None else None


def _coord(value: Any) -> str | None:
    """A NUMERIC(9,6) coordinate as its stored string — never a float."""
    return None if value is None else str(Decimal(str(value)).quantize(Decimal("0.000001")))


def _position_of(order: Any, premises: Any) -> dict[str, Any]:
    """Where a job IS, as a point — `DEF-FLD-10582` (MQ-015: the phone's
    *Navigate* was greyed on every job because no point was on the wire).

    ⚠ **HARD RULE 8 AS NARROWED BY `BR-MET-1162`:** the UNIT's own point where
    it carries both halves, else its building's, and `position_source` says
    which (*"every screen showing a point says which of the two it is
    showing"*). A unit counts only when it refines THIS premises — a unit
    reached through another anchor never moves the pin to another building.
    Both `None` → no point recorded; nothing is invented.
    """
    unit = _unit_row(order)
    if (
        unit is not None
        and unit.premises_id == premises.id
        and unit.lat is not None
        and unit.lng is not None
    ):
        return {"lat": _coord(unit.lat), "lng": _coord(unit.lng), "position_source": "unit"}
    if premises.lat is not None and premises.lng is not None:
        return {
            "lat": _coord(premises.lat),
            "lng": _coord(premises.lng),
            "position_source": "premises",
        }
    return {"lat": None, "lng": None, "position_source": None}


def _premise_of(order: Any) -> dict[str, Any] | None:
    """The premise a job is at, from whichever anchor carries one — and its
    point (`_position_of`). Callers that read only `id`/`premise_no`/`address`
    are unchanged: the point is three extra keys."""
    row = _premises_row(order)
    if row is None:
        return None
    return {
        "id": str(row.id),
        "premise_no": row.premise_no,
        "address": row.address_line,
        **_position_of(order, row),
    }


def _stored_at(order: Any) -> str | None:
    """Where a job on NO premises is, in its asset's own words — `DEF-WRK-9671`.

    A meter in the warehouse has no service point and no installed unit, so the
    walk (`DEF-WRK-9660`) finds no premises and every *where* cell read a dash —
    even when the meter carries `assets.location_note` (*Warehouse bay 3*). That
    note is the answer for such a job, and ONLY for such a job: a job that
    stands on a premises names the premises (hard rule 8), never the note. Read
    at use, never copied onto the job. `None` → the screen draws its dash.

    Whether the certification rule should raise on a warehouse meter at all is
    the Product Owner's open question; this changes what the row SAYS, nothing
    about what is raised.
    """
    if not getattr(order, "asset_id", None) or _premises_row(order) is not None:
        return None
    note = (getattr(order.asset, "location_note", None) or "").strip()
    return note or None


def _row(order: Any) -> dict[str, Any]:
    return {
        "id": str(order.id),
        "order_no": order.order_no,
        "type": order.type,
        "premise": _premise_of(order),
        "stored_at": _stored_at(order),
        "service": order.service.code if order.service_id else None,
        "state": order.state,
        "outcome": order.outcome,
        "mode": order.mode,
        "is_gate": order.is_gate,
        # ⚠ **`home` IS WHERE THE CONNECTION CELL LINKS NOW (CR-070 wave O).**
        # The TEXT stays `CON-26-0117` — a number a clerk quotes down a phone,
        # not a database id — and the LINK moves to the build's home, because
        # `/connections/<uuid>` is no longer a place a person navigates to
        # (`CR-070 §W.11`). Computed from columns the row already carries, so
        # this costs no query: `owner_account_id` and `premises_id` are on the
        # connection itself.
        "connection": (
            {
                "id": str(order.connection_id),
                "connection_no": order.connection.connection_no,
                "home": metering_seam.home_of_connection(order.connection),
            }
            if order.connection_id
            else None
        ),
        "account": (
            {"id": str(order.account_id), "account_no": order.account.account_no}
            if order.account_id
            else None
        ),
        "raised_at": order.created_at.isoformat() if order.created_at else None,
    }


def _search(qs: Any, q: str | None) -> Any:
    text = (q or "").strip()
    if not text:
        return qs
    return qs.filter(
        Q(order_no__icontains=text)
        | Q(type__icontains=text)
        | Q(connection__connection_no__icontains=text)
        | Q(connection__premises__address_line__icontains=text)
        | Q(premises__address_line__icontains=text)
        | Q(unit__premises__address_line__icontains=text)
    )


def _page_number(raw: Any, last: int) -> int:
    try:
        number = int(str(raw))
    except (TypeError, ValueError):
        return 1
    return min(max(number, 1), last)


def open_orders(
    *, q: str | None = None, page: Any = 1, per: Any = DEFAULT_PAGE_SIZE
) -> dict[str, Any]:
    """The Orders tab's page: `{"rows", "page", "per", "total"}`.

    `page`/`per` come back as the values USED after clamping (BR-SHL-011).
    """
    qs = _search(metering_seam.open_work_orders_queryset(), q).order_by("order_no", "id")
    total = qs.count()
    size = clamp_page_size(per)
    last = max(1, math.ceil(total / size))
    number = _page_number(page, last)
    start = (number - 1) * size
    rows = list(qs[start : start + size])
    return {"rows": [_row(row) for row in rows], "page": number, "per": size, "total": total}


def open_work_order_count_for_unit(unit_id: Any) -> int:
    """`CR-089` wave F `F3` — **how many jobs are still running on ONE unit.**

    The unit page's fourth tile (*Open work*), resolved by
    `apps.metering.seams.open_work_order_count_for_unit` BY NAME rather than by
    metering filtering the table itself. Metering hosts the six Work tables
    today (`CLAUDE.md`'s module map) and could have written this filter in three
    lines; what it cannot own is the word **OPEN**, which is
    `metering_seam.OPEN_WORK_ORDER_STATES` — `planned · in_progress · blocked`,
    the set the dispatcher's own queue carves out. One definition, asked for.

    ⚠ **THE ANCHOR IS THE UNIT AND NOTHING ELSE, WHICH IS NARROWER THAN
    `orders_at_premises_queryset` AND IS THE RIGHT ANSWER FOR A TILE.** That
    function answers *what work stands at this ADDRESS* and reaches five
    anchors, a unit's siblings among them — correct for a building's tab and
    wrong over a flat, where a job on the flat upstairs would be counted as
    this flat's. `BR-WRK-006`'s unit anchor is the one that means *this unit*.

    ⚠ **A JOB ON AN ASSET OF THIS UNIT IS NOT COUNTED, AND THAT IS A DECISION
    RATHER THAN AN OVERSIGHT.** `orders_at_premises_queryset` walks asset →
    service point → unit → premises for exactly that case, so the reach exists
    and is deliberately not taken: **a tile reading 3 over a list showing 2 is
    worse than a tile that is narrow and says so**, and the wave that draws the
    unit's work-orders LIST is the one that can make a tile and a list count the
    same rows. Recorded in the decision log of 2026-09-09 (CR-089 wave F) rather
    than minted as a question — `CLAUDE.md` law 13: *"a judgment call recorded
    in the decision log with its reasoning is the deliverable; a question is the
    failure to make one."*

    A READ: it counts and writes nothing (`G78`), and the queryset is built in
    `metering_seam` beside every other reach into that table rather than here.
    """
    return int(metering_seam.open_orders_at_unit_queryset(unit_id).count())


def open_work_at_premises(premises_id: Any) -> dict[str, Any]:
    """`CR-089` `F3` / `DEF-MET-4733` — **how many jobs are still running at
    this ADDRESS, and what the next one is.**

    The property page's fourth tile. `{"count": int, "next": {...} | None}`.

    ⚠ **THE COUNT AND THE PROPERTY'S WORK-ORDERS TAB READ ONE QUERYSET.**
    `metering_seam.open_orders_at_premises_queryset` is
    `orders_at_premises_queryset` — the tab's own rows — narrowed to
    `OPEN_WORK_ORDER_STATES`. Wave F had to make the unit's tile NARROWER than
    its list and recorded why; at a property the two agree by construction, so
    a clerk cannot read a tile that disagrees with the table under it.

    ⚠ **`next` IS THE APPOINTMENT A CUSTOMER WAS PROMISED, NOT AN SLA
    DEADLINE.** `window_start` is *Thursday, 08:00–12:00*; `due_at` is
    `BR-WRK-018`'s internal deadline. `_scoped_row` keeps them apart for the
    reason reused here: printing a deadline as *when somebody is coming* tells a
    customer a time the utility never said to them. So `next` is the soonest
    open order that HAS a promised window, and it is `None` when none of them
    does — a true *"nothing is booked"* rather than a guessed date.

    `type` is the job's own words (`work_orders.type`), so the tile's detail
    line reads *meter change* because somebody typed that, never a code this
    function maps.

    A READ: it counts and writes nothing (`G78`).
    """
    qs = metering_seam.open_orders_at_premises_queryset(premises_id)
    count = int(qs.count())
    soonest = (
        qs.filter(window_start__isnull=False).order_by("window_start", "id").first()
        if count
        else None
    )
    return {
        "count": count,
        "next": (
            None
            if soonest is None
            else {
                "id": str(soonest.id),
                "order_no": soonest.order_no,
                "type": soonest.type,
                "window_start": soonest.window_start.isoformat(),
            }
        ),
    }


def _waiting_days(completed_at: Any, now: Any) -> int | None:
    """`Work-009`'s WAITING column, **in whole days and never a raw timestamp**
    (`US-WRK-003` §5: *"in words, never a raw timestamp"*).

    Whole days elapsed since the field finished, floored: an order completed six
    days and twenty-three hours ago has been waiting **6 days**, not seven. A
    figure that rounded up would say *1 day* about a job finished an hour ago.

    `None` when `completed_at` is null, which cannot happen for a row this queue
    returns — the state says the field has reported — but is answered rather than
    assumed, because a `TypeError` on a screen is worse than a dash.
    """
    if completed_at is None:
        return None
    return max((now - completed_at).days, 0)


def _approval_row(order: Any, now: Any, closers: dict[str, Any] | None = None) -> dict[str, Any]:
    """One `Work-009` row: ORDER · CONNECTION · PREMISE · SERVICE · OUTCOME ·
    COMPLETED · WAITING, plus the id the eye icon opens the drawer with.

    `closed_by` (`DEF-WRK-9679`) is image 22's *closed by D. Ortiz* — the name
    of whoever wrote the close, read for the whole page at once by
    `_closers_of`; `None` where no close was recorded, never a guess."""
    closer = (closers or {}).get(str(order.id))
    return {
        "closed_by": {"name": closer} if closer else None,
        "id": str(order.id),
        "order_no": order.order_no,
        "type": order.type,
        "premise": _premise_of(order),
        "stored_at": _stored_at(order),
        "service": order.service.code if order.service_id else None,
        "outcome": order.outcome,
        "completed_at": order.completed_at.isoformat() if order.completed_at else None,
        "waiting_days": _waiting_days(order.completed_at, now),
        # A DASH on the screen, never a blank: an order raised on a premises, an
        # account or an asset alone has no build (US-WRK-003 TC-7).
        "connection": (
            {
                "id": str(order.connection_id),
                "connection_no": order.connection.connection_no,
                # The queue's CONNECTION cell links HERE now, not to a retired
                # screen (`CR-070 §W.11`, wave O task O5).
                "home": metering_seam.home_of_connection(order.connection),
            }
            if order.connection_id
            else None
        ),
    }


def _closers_of(orders: list[Any]) -> dict[str, Any]:
    """`{order_id: name}` for a page of finished jobs — two queries for the
    page whatever its length (the close's audit row, then the names)."""
    from apps.work.seams import audit_seam, identity_seam

    actors = audit_seam.latest_actor_per_order([o.id for o in orders], "work_order.field_result")
    names = identity_seam.user_names([a for a in actors.values() if a])
    return {order_id: names.get(str(actor)) for order_id, actor in actors.items() if actor}


def awaiting_approval(*, page: Any = 1, per: Any = DEFAULT_PAGE_SIZE) -> dict[str, Any]:
    """**`BR-WRK-007` — every finished order nobody has accepted, oldest first.**

    `{"rows", "page", "per", "total", "oldest_waiting_days"}`. The last figure is
    the footer's second half — *"3 orders · oldest waiting 6 days"* — and it is
    computed over the WHOLE queue, not over the page in hand: a footer that said
    *oldest waiting 1 day* because the six-day row was on page two would be a
    true sentence about the wrong set (`DEF-1702`'s argument, applied to a
    count rather than to a filter). `None` when the queue is empty, because a
    zero there reads as *"something has been waiting no time at all"*.

    ⚠ **SORTED OLDEST FIRST, WHICH IS `completed_at` ASCENDING** — `US-WRK-003`
    TC-1. Nulls last and the id as the tiebreak, so the order is total and two
    runs of the same query cannot disagree.

    ⚠ **NO `q`.** `Work-009` draws no search box, and a control the drawing does
    not carry is not added on the way past (B14; the Orders tab has one because
    `Work-007` draws one). `page`/`per` come back as the values USED after
    clamping (`BR-SHL-011`).
    """
    now = timezone.now()
    qs = metering_seam.awaiting_approval_queryset().order_by(
        F("completed_at").asc(nulls_last=True), "id"
    )
    total = qs.count()
    size = clamp_page_size(per)
    last = max(1, math.ceil(total / size))
    number = _page_number(page, last)
    start = (number - 1) * size
    rows = list(qs[start : start + size])
    oldest = qs.values_list("completed_at", flat=True).first() if total else None
    closers = _closers_of(rows)
    return {
        "rows": [_approval_row(row, now, closers) for row in rows],
        "page": number,
        "per": size,
        "total": total,
        "oldest_waiting_days": _waiting_days(oldest, now),
    }


# ── CR-070 wave O · the two SCOPED reads, and no seventh filter ─────────────
#
# `CR-070 §W.11` retires `/connections/<uuid>` as a destination: the build's
# progress, its units, its work orders and its charges are reached from the
# PREMISES and from the ACCOUNT. These two reads are the *work orders* half of
# that, and `metering_seam.build_for_premises` / `build_for_account` are the
# *build* half.
#
# ⚠ **SCOPED BY PATH, NEVER BY A SEVENTH FILTER** (execution plan judgment 3).
# `BR-WRK-026` gives the dispatcher exactly six filters and a `400` on a
# seventh. `GET /premises/{id}/work-orders` and `GET /accounts/{id}/work-orders`
# are PATHS, so that rule does not move and no signed rule stands in the way of
# a screen.


def _stands_on(order: Any) -> str:
    """Which anchor this row is standing on, in one word the screen can print.

    `US-WRK-004` on the account tab: *"each row saying which"*. The order is the
    order `BR-WRK-006` writes the anchors in, and the FIRST anchor a row has
    wins — an order can name a build AND a unit, and what a clerk is being told
    is the most specific true thing rather than every true thing.

    ⚠ **NOT AN ADDRESS AND NOT AN ID** — the word is `account`, `asset`,
    `unit`, `build` or `premises`, and the screen turns it into a sentence in
    its own catalogue. B14 rule 31: no database id is the visible value of a
    field.
    """
    if order.account_id is not None:
        return "account"
    if order.asset_id is not None:
        return "asset"
    if order.unit_id is not None:
        return "unit"
    if order.connection_id is not None:
        return "build"
    if order.premises_id is not None:
        return "premises"
    # Unreachable while `ck_work_orders_has_anchor` holds — an order standing on
    # nothing is refused by `create_work_order` and again by the CHECK. Answered
    # rather than asserted, because a KeyError on a screen is worse than a word.
    return "premises"


def _scoped_row(order: Any) -> dict[str, Any]:
    """One row of a scoped list: the house row shape, plus which anchor it
    stands on, plus what the drawer opens with.

    ⚠ **THE DRAWER FIELDS ARE HERE AND NOT IN `_row`, DELIBERATELY.** `_row`
    serves the dispatcher's queue, which pages fifty orders and draws none of
    these; carrying `field_data` on every one of those rows would put a JSON
    document per row on a list that never reads it. A premises or an account
    holds a handful of jobs and the person on it opens them, so the two shapes
    differ by what each screen actually does.

    ⚠ **AND IT IS THE SAME SIX FIELDS `connection_reads._work_order_row`
    PUBLISHES, BY NAME**, because the drawer they feed is the SAME component
    the connection detail used before wave O retired it. Two shapes for one
    drawer would be the second, drifting copy this repo keeps learning about.
    `accepted_at` is served exactly as stored and never defaulted to the
    completion date: a null on a completed order is the ONLY thing in the
    product that says the field sent data and no person has accepted it, and
    that gap IS the review queue (`BR-MET-110`).
    """
    shaped = _row(order)
    shaped["stands_on"] = _stands_on(order)
    shaped["scope"] = order.scope
    shaped["unit_label"] = order.unit.label if order.unit_id else None
    shaped["external_ref"] = order.external_ref
    shaped["completed_at"] = order.completed_at.isoformat() if order.completed_at else None
    shaped["accepted_at"] = order.accepted_at.isoformat() if order.accepted_at else None
    # An empty name is served as null rather than as an empty string: a user
    # invited and not yet named has no name, and `""` renders as a blank cell
    # that looks like a bug.
    shaped["accepted_by"] = (
        (order.accepted_by.full_name or None) if order.accepted_by_id else None
    )
    shaped["field_data"] = order.field_data
    # ── CR-089 wave C `C6` (`PUJ-16`) · WHEN IS SOMEBODY COMING ────────────
    #
    # The premises tab drew Order · Service · Stands on · Mode · Outcome ·
    # State · Actions — **seven columns, and not one of them is a date or a
    # name**. A person standing on a property page asking *when is somebody
    # coming* got a state word. The two facts that answer it are on the order
    # already and were served only to the DISPATCHER's own list
    # (`dispatch._dispatch_row`), which this route is not.
    #
    # ⚠ **THE APPOINTMENT WINDOW LEADS AND THE SLA DEADLINE FOLLOWS, AND THE
    # SCREEN IS TOLD WHICH IT GOT.** `window_start` is what a customer was
    # PROMISED — *Thursday, 08:00–12:00* — and `due_at` is `BR-WRK-018`'s
    # internal deadline, the raise time plus the priority's SLA hours. They are
    # different promises to different people, so they are served as separate
    # keys rather than coalesced into one nullable `when`: a screen printing an
    # SLA deadline as *when somebody is coming* would be telling a customer a
    # number the utility never said to them.
    #
    # ⚠ **`technician` REUSES `dispatch._holder`, WHICH IS THE ONE DEFINITION
    # OF WHO HAS A JOB** — a person, a crew, or `None` for nobody. A second
    # shaping here would be two answers to one question, and `None` is a real
    # answer the screen draws as *Nobody assigned* rather than as a blank cell.
    from apps.work.dispatch import _holder

    shaped["technician"] = _holder(order)
    shaped["window_start"] = order.window_start.isoformat() if order.window_start else None
    shaped["window_end"] = order.window_end.isoformat() if order.window_end else None
    shaped["due_at"] = order.due_at.isoformat() if order.due_at else None
    # ── B14 rule 41 · `ACC-T08` draws PRIORITY and RAISED BY ───────────────
    #
    # ⚠ **BOTH COLUMNS EXISTED, WERE WRITTEN, AND REACHED ONLY THE
    # DISPATCHER.** `work_orders.priority_id` is stamped at the raise
    # (`BR-WRK-018`) and `work_orders.source` is the column whose own docstring
    # says *"`Work-007` draws it as RAISED BY"* — and `_row` above serves
    # neither, so the account's Work tab could draw five of the seven columns
    # its blueprint draws and no more. Serving them is a READ widening inside
    # the module that owns the table; nothing here writes anything.
    #
    # ⚠ **`_priority_of` IS REUSED RATHER THAN RESHAPED.** It is `dispatch`'s
    # one definition of what a priority looks like on the wire — id, code,
    # name, colour and rank — and a second shaping here would let the
    # dispatcher's queue and the account's tab describe one priority two ways.
    # `None` is a real answer: `BR-WRK-018` gives a typeless order no priority
    # and therefore no `due_at`, and the screen states that rather than
    # inventing a rank.
    from apps.work.dispatch import _priority_of

    shaped["priority"] = _priority_of(order)
    shaped["source"] = order.source
    return shaped


def _scoped_page(qs: Any, page: Any, per: Any) -> dict[str, Any]:
    """One page of a scoped order list, newest first.

    **Newest first, not by order number**, and that is the difference from
    `open_orders` above: the Orders tab is a worklist a dispatcher scans in a
    stable order, and these two are a HISTORY of one place — the question is
    *"what has been happening here"*, whose answer starts with what happened
    last. `created_at` descending with the id as the tiebreak, so the order is
    total and two runs of the same query cannot disagree.

    ⚠ **EVERY STATE, NOT JUST THE OPEN ONES.** `open_orders` draws the
    dispatcher's window (`planned · in_progress · blocked`); a person standing
    on a premises asking what work has been done here needs the completed and
    the cancelled ones too, or the tab would say *"no work"* about an address
    with twenty finished jobs on it.
    """
    # ⚠ **`DEF-MET-6881`** — this newest-first read is served by
    # `ix_work_orders_raised (tenant_id, created_at, id)`, laid by
    # `metering/0062` on 2026-09-27, SCANNED BACKWARD. Before it this was a
    # `Seq Scan` + `Sort` of every order the tenant has. The index declares no
    # direction on purpose, so an ascending toggle reads the same index
    # forward; a lane "tidying" it to `DESC` takes that half away.
    qs = qs.order_by("-created_at", "-id")
    total = qs.count()
    size = clamp_page_size(per)
    last = max(1, math.ceil(total / size))
    number = _page_number(page, last)
    start = (number - 1) * size
    rows = [_scoped_row(row) for row in qs[start : start + size]]
    return {"rows": rows, "page": number, "per": size, "total": total}


def orders_at_premises(premises_id: Any, *, page: Any = 1, per: Any = DEFAULT_PAGE_SIZE) -> dict[str, Any]:
    """`GET /premises/{id}/work-orders` — every job at this address.

    The row shape is `open_orders`' shape plus `stands_on`, deliberately: one
    row shape for every list of work orders in this product means the account
    tab, the premises tab and the dispatcher's queue cannot describe the same
    order three ways.
    """
    return _scoped_page(metering_seam.orders_at_premises_queryset(premises_id), page, per)


def orders_for_account(
    account_id: Any, premises_id: Any = None, *, page: Any = 1, per: Any = DEFAULT_PAGE_SIZE
) -> dict[str, Any]:
    """`GET /accounts/{id}/work-orders` — the jobs on this account AND at its address.

    `premises_id` is the account's own premises, reached by `BR-MET-1161`'s walk
    (account → unit → premises) and passed in by the route so this selector
    reads the customers table exactly once, through the seam. `None` when the
    account names no unit, in which case the answer is the account's own orders
    and nothing else — a true, smaller list rather than a guessed larger one.
    """
    return _scoped_page(
        metering_seam.orders_for_account_queryset(account_id, premises_id), page, per
    )


# ── Work-025 · the parts register (wave C) ──────────────────────────────────
#: The keys `GET /work/parts` publishes. **A frozen tuple rather than a shape
#: built inline**, because `US-WRK-010` TC-5 asserts the register's payload BY
#: NAME — *no `on_hand`, no `reorder_at`, no `location`* — and an assertion
#: about a dict literal buried in a function is an assertion nobody re-reads.
#: `OQ-WRK-1490` is what stands between this tuple and a longer one.
PART_ROW_KEYS: tuple[str, ...] = (
    "id",
    "part_no",
    "name",
    "category",
    "unit_of_measure",
    "unit_cost",
    "active",
)


def _part_row(row: Any) -> dict[str, Any]:
    """One row of the register — Work-025's six columns and the id behind them.

    `unit_cost` travels as a STRING at four decimals (`"92.4000"`), which is
    what the column stores; the screen displays two (`$92.40`) through
    `MoneyCell`. CLAUDE.md hard rule 2 — and a float here would be the exact
    thing that rule forbids, one JSON serialization away from `92.39999`.
    """
    return {
        "id": str(row.id),
        "part_no": row.part_no,
        "name": row.name,
        "category": (
            None
            if row.category_id is None
            else {"id": str(row.category_id), "name": row.category.name}
        ),
        "unit_of_measure": row.unit_of_measure,
        "unit_cost": f"{row.unit_cost:.4f}",
        "active": row.active,
    }


def _parts_queryset() -> Any:
    from apps.work import models as work_models

    return work_models.Part.objects.filter(
        tenant_id=core_tenancy.current_tenant_id()
    ).select_related("category")


def parts_page(
    *,
    q: str | None = None,
    category: str | None = None,
    unit: str | None = None,
    status: str | None = None,
    page: Any = 1,
    per: Any = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
    """`GET /work/parts` — Work-025's Stock register segment.

    Search matches the part number and the description, which are the two
    columns the box names (`Work-025`: *"Search part #, description…"*),
    applied in SQL BEFORE paging for `DEF-1702`'s reason: a filter over the
    page in hand is a subset of a subset.

    Ordered by part number: the register is a reference list a person scans,
    and `Work-025`'s own capability row gives it that default sort.
    """
    qs = _parts_queryset()
    if q and len(q.strip()) >= 2:
        term = q.strip()
        qs = qs.filter(Q(part_no__icontains=term) | Q(name__icontains=term))
    # ── CR-168 · `DEF-WRK-9580` (P3.10) — the register's three filters ───────
    # In SQL and BEFORE the count and the page (NFR-3; `DEF-1702`). A category
    # travels as its CODE (B14 rule 31: the screen shows the name, the URL
    # never carries an id); `none` is the uncategorised parts, which the
    # register draws as a dash. A unit is the register's own word, matched
    # without case. Status is `active` | `inactive`. Each takes several values
    # (`f.category=meters,fittings` — the shared filter panel's ticks, OQ-306),
    # OR within a filter and AND across them; an unknown status filters
    # nothing rather than everything.
    categories = [value.lower() for value in filter_values(category)]
    if categories:
        clauses = Q(pk__in=[])
        if "none" in categories:
            clauses |= Q(category__isnull=True)
        codes = [value for value in categories if value != "none"]
        if codes:
            clauses |= Q(_category_code__in=codes)
        qs = qs.annotate(_category_code=Lower("category__code")).filter(clauses)
    units = [value.lower() for value in filter_values(unit)]
    if units:
        qs = qs.annotate(_uom=Lower("unit_of_measure")).filter(_uom__in=units)
    statuses = {value for value in filter_values(status) if value in ("active", "inactive")}
    if len(statuses) == 1:
        qs = qs.filter(active=(statuses == {"active"}))
    qs = qs.order_by("part_no", "id")
    total = qs.count()
    size = clamp_page_size(per)
    last = max(1, math.ceil(total / size))
    number = _page_number(page, last)
    start = (number - 1) * size
    return {
        "rows": [_part_row(row) for row in qs[start : start + size]],
        "page": number,
        "per": size,
        "total": total,
    }


def part_units() -> list[str]:
    """The units the register actually counts in — the Unit filter's choices.

    A DISTINCT in SQL over this tenant's parts, sorted, uncapped (NFR-5): the
    choices are the register's own words, so a filter can never offer a unit
    no part has, nor hide one a part does."""
    seen: dict[str, str] = {}
    for value in (
        _parts_queryset()
        .order_by("unit_of_measure")
        .values_list("unit_of_measure", flat=True)
        .distinct()
    ):
        word = str(value or "").strip()
        if word and word.lower() not in seen:
            seen[word.lower()] = word
    return sorted(seen.values(), key=str.lower)


def part(part_id: Any) -> dict[str, Any] | None:
    """One register row, or None — a cross-tenant id is None here and a 404 at
    the route, identical to an id that does not exist (hard rule 1)."""
    row = _parts_queryset().filter(pk=part_id).first()
    return None if row is None else _part_row(row)


# ══════════════════════════════════════════════════════════════════════════
# CR-070 WAVE D · THE TEMPLATE BUNDLE'S READS (Work-013, Work-022)
# ══════════════════════════════════════════════════════════════════════════
#
# ⚠ **THE HEADER IS READ THROUGH THE SEAM AND THE BUNDLE IS READ DIRECTLY**,
# which is not an inconsistency but the boundary showing through: the header
# row is metering's table and the eight bundle tables are Work's own
# (`03-field-map.md` §2.2, §4). The day the header moves, `metering_seam`
# changes and this file does not.


#: `Work-013`'s CONTENTS column — the five bundle tables counted per template.
_CONTENT_MODELS = (
    ("tasks", "WorkOrderTemplateTask"),
    ("parts", "WorkOrderTemplateMaterial"),
    ("readings", "WorkOrderTemplateReading"),
    ("safety", "WorkOrderTemplateSafety"),
    ("help", "WorkOrderTemplateHelp"),
)


def _content_annotations() -> dict[str, Any]:
    """The five counts as correlated `COUNT(*)` subqueries, so a page of
    templates is ONE query (`CR-168-BRC10` P3.5) rather than five per row."""
    from django.db.models import Count, IntegerField, OuterRef, Subquery
    from django.db.models.functions import Coalesce

    out: dict[str, Any] = {}
    for key, model_name in _CONTENT_MODELS:
        model = getattr(work_models, model_name)
        counted = (
            model.objects.filter(template_id=OuterRef("pk"))
            .order_by()
            .values("template_id")
            .annotate(n=Count("id"))
            .values("n")
        )
        out[f"contents_{key}"] = Coalesce(Subquery(counted, output_field=IntegerField()), 0)
    return out


def _contents(template_id: Any) -> dict[str, int]:
    """`Work-013`'s CONTENTS column — *2 tasks · 0 parts · 1 reading*.

    ⚠ **NEVER BLANK, AND ZERO IS A NUMBER** (`US-WRK-013` TC-4). A seeded
    starter with nothing behind it reads *0 tasks · 0 parts · 0 readings*, not
    an empty cell: a blank reads as a bug and a zero reads as an answer.
    """
    tenant_id = core_tenancy.current_tenant_id()
    return {
        key: getattr(work_models, model_name)
        .objects.filter(tenant_id=tenant_id, template_id=template_id)
        .count()
        for key, model_name in _CONTENT_MODELS
    }


def template_status(row: dict[str, Any]) -> str:
    """The ONE word `Work-013`'s STATUS column shows, derived and never stored.

    Three states out of two columns: `version = 0` has never been published
    and is a **draft**; `active = false` is **inactive** whatever its version;
    everything else is **published**. A stored status column would be a fourth
    place for the same fact to be wrong (the 2026-09-05 ruling's *"two answers
    to one question is how a figure drifts"*).
    """
    if not row.get("active", True):
        return "inactive"
    return "published" if int(row.get("version") or 0) >= 1 else "draft"


def _template_list_row(row: dict[str, Any], contents: dict[str, int] | None = None) -> dict[str, Any]:
    return {
        **row,
        "est_duration_minutes": (
            None
            if row.get("est_duration") is None
            else int(row["est_duration"].total_seconds() // 60)
        ),
        "contents": contents if contents is not None else _contents(row["id"]),
        "status": template_status(row),
    }


def templates_page(
    *,
    q: str | None = None,
    service: str | None = None,
    page: Any = 1,
    per: Any = DEFAULT_PAGE_SIZE,
    job_type: str | None = None,
    asset_type: str | None = None,
    scope: str | None = None,
    raisable: bool = False,
) -> dict[str, Any]:
    """`GET /work/templates` — `Work-013`'s list, and its footer's four counts.

    `service` is the drawing's own *Filter by service ▾* and is the only
    filter this list declares. Search matches the template name and the job
    type, which is what the box names; applied in SQL BEFORE paging
    (`DEF-1702`).

    The four footer figures — *6 templates · 4 published · 1 draft · 1
    inactive* — are counted over the WHOLE list and not over the page, for the
    same reason `Work-009`'s *oldest waiting* is: a footer that described the
    page in hand would change as a person paged through it.
    """
    qs = metering_seam.templates_queryset()
    if services := filter_values(service):  # OQ-306 — ANY of the picked services
        qs = qs.filter(service__code__in=services)
    if q and len(q.strip()) >= 2:
        term = q.strip()
        qs = qs.filter(Q(name__icontains=term) | Q(type__name__icontains=term))
    # ── `CR-168-BRC10` P2.11 (lane SRV-2) — the three filters the RAISE needs ──
    # `f.job_type` — the job type picked on step 1 (a kind or its heading);
    # `f.asset_type` — a template naming this asset type, or naming none (an
    # unrestricted template applies to every type, `BR-WRK-056`); `f.scope`.
    if job_type:
        # ⚠ `DEF-WRK-9612` — a template naming NO job type applies to every
        # type, exactly as one naming no asset type applies to every asset
        # (below). Keeping only typed matches dropped all 6 of 6 demo templates
        # and the raise offered nothing.
        qs = qs.filter(Q(type_id=job_type) | Q(type__parent_id=job_type) | Q(type_id__isnull=True))
    if asset_type:
        from django.db.models import Exists, OuterRef

        named = work_models.WorkOrderTemplateAssetType.objects.filter(template_id=OuterRef("pk"))
        qs = qs.filter(~Exists(named) | Exists(named.filter(asset_type_id=asset_type)))
    if scope:
        qs = qs.filter(scope=scope)
    if raisable:
        # Only what a job can be raised from: active and published (`BR-WRK-008`).
        qs = qs.filter(active=True, version__gte=1)
    # ── `CR-168-BRC10` P3.5 (lane SRV-3) — PAGED AND COUNTED IN SQL ──────────
    # This materialised every template, counted the footer by walking them and
    # sliced the list in Python, with five more queries per row for CONTENTS.
    # Now: ONE aggregate for the footer (the status is derived from `active`
    # and `version` exactly as `template_status` derives it), ONE query for the
    # page with its contents as subqueries. NFR-3; no maximum (NFR-5).
    from django.db.models import Count

    tally = qs.order_by().aggregate(
        total=Count("id"),
        inactive=Count("id", filter=Q(active=False)),
        published=Count("id", filter=Q(active=True, version__gte=1)),
        draft=Count("id", filter=Q(active=True) & (Q(version__lt=1) | Q(version__isnull=True))),
    )
    total = int(tally["total"] or 0)
    counts = {
        "published": int(tally["published"] or 0),
        "draft": int(tally["draft"] or 0),
        "inactive": int(tally["inactive"] or 0),
    }
    size = clamp_page_size(per)
    last = max(1, math.ceil(total / size)) if total else 1
    number = _page_number(page, last)
    start = (number - 1) * size
    page_qs = qs.annotate(**_content_annotations()).order_by(
        "service__code", "sequence", "name", "id"
    )[start : start + size]
    rows = []
    for row in page_qs:
        contents = {key: int(getattr(row, f"contents_{key}") or 0) for key, _ in _CONTENT_MODELS}
        rows.append(_template_list_row(metering_seam._template_row(row), contents))
    return {
        "rows": rows,
        "page": number,
        "per": size,
        "total": total,
        "counts": counts,
    }


def _collection_rows(template_id: Any) -> dict[str, list[dict[str, Any]]]:
    """The seven collections, in `seq` order — which is DATA, not presentation
    (`BR-WRK-009`: the order is what the phone shows)."""
    tenant_id = core_tenancy.current_tenant_id()
    detail = work_models.WorkOrderTemplateDetail.objects.filter(
        tenant_id=tenant_id, template_id=template_id
    ).first()
    return {
        "details": None
        if detail is None
        else {
            "show_account_summary": detail.show_account_summary,
            "show_asset_card": detail.show_asset_card,
            "show_access_notes": detail.show_access_notes,
            "show_appointment": detail.show_appointment,
            # FB-023 F4 — Balance & payments.
            "show_balance_payments": detail.show_balance_payments,
            # FB-028 — the Reconnect limit, 4 places as stored (null = none).
            "reconnect_limit": (
                None if detail.reconnect_limit is None else f"{detail.reconnect_limit:.4f}"
            ),
            # CR-070 wave E · the builder's step 7 (`work/0005`). What the
            # template ASKS FOR; what the technician actually captured is
            # `work_order_signatures`, which is US-WRK-036's and phase 2's.
            "signature_required": detail.signature_required,
            "refusal_reason_required": detail.refusal_reason_required,
            "door_hanger_on_no_answer": detail.door_hanger_on_no_answer,
            # DEF-WRK-10652 (PO 2026-10-29, rulings 3B and 4A) — what the
            # customer is asked to prepare, and whether they are told at all.
            "prep_instructions": detail.prep_instructions,
            "send_customer_visit_messages": detail.send_customer_visit_messages,
        },
        "safety": [
            {"seq": r.seq, "text": r.text, "is_mandatory": r.is_mandatory}
            for r in work_models.WorkOrderTemplateSafety.objects.filter(
                tenant_id=tenant_id, template_id=template_id
            ).order_by("seq")
        ],
        "tasks": [
            {
                "seq": r.seq,
                "title": r.title,
                "est_minutes": r.est_minutes,
                "photo_required": r.photo_required,
                "is_mandatory": r.is_mandatory,
                # PO answer (3) — the task's instruction text, or None.
                "instruction": r.instruction or None,
                # CR-187-BRC10 T-35 — the step's money freshness bar and charge.
                "money_fresh_minutes": r.money_fresh_minutes,
                "money_charge_code": r.money_charge_code or None,
            }
            for r in work_models.WorkOrderTemplateTask.objects.filter(
                tenant_id=tenant_id, template_id=template_id
            ).order_by("seq")
        ],
        "materials": [
            {
                "part_id": str(r.part_id),
                "part_no": r.part.part_no,
                "name": r.part.name,
                # hard rule 2 — four decimals as a STRING; the screen rounds.
                "planned_qty": f"{r.planned_qty:.4f}",
                "unit_of_measure": r.unit_of_measure,
            }
            for r in work_models.WorkOrderTemplateMaterial.objects.filter(
                tenant_id=tenant_id, template_id=template_id
            ).select_related("part").order_by("part__part_no")
        ],
        "readings": [
            {
                "seq": r.seq,
                "prompt": r.prompt,
                # hard rule 3 — the unit is a COLUMN and it travels with the
                # figure, never glued into the prompt.
                "unit_of_measure": r.unit_of_measure,
                "min": None if r.min_value is None else f"{r.min_value:.4f}",
                "max": None if r.max_value is None else f"{r.max_value:.4f}",
                "required": r.required,
                "photo_required": r.photo_required,
                "posts_as_meter_read": r.posts_as_meter_read,
                # `CR-168-BRC10` P1.33 — `number` or `text`.
                "kind": r.kind,
            }
            for r in work_models.WorkOrderTemplateReading.objects.filter(
                tenant_id=tenant_id, template_id=template_id
            ).order_by("seq")
        ],
        "help": [
            _help_read_row(template_id, r)
            for r in work_models.WorkOrderTemplateHelp.objects.filter(
                tenant_id=tenant_id, template_id=template_id
            ).order_by("seq")
        ],
        "asset_types": [
            {"asset_type_id": str(r.asset_type_id)}
            for r in work_models.WorkOrderTemplateAssetType.objects.filter(
                tenant_id=tenant_id, template_id=template_id
            ).order_by("asset_type_id")
        ],
    }


def _help_read_row(template_id: Any, row: Any) -> dict[str, Any]:
    """One help row as `Work-022` and the builder draw it (`CR-168-BRC10` §7.3):
    `url` — a SAME-ORIGIN path to a stored document's bytes (the page policy
    refuses a storage host, `DEF-WRK-9594`'s reason), or None when the ref is
    not a document this template holds; `link` — a link's `https` address."""
    from apps.work import template_help

    out = {"seq": row.seq, "kind": row.kind, "label": row.label, "ref": row.ref, "url": None, "link": None}
    if row.kind == work_models.HELP_KIND_LINK:
        out["link"] = row.ref
    elif row.kind == work_models.HELP_KIND_DOCUMENT and row.ref:
        document = template_help.document_of(template_id, row.ref)
        if document is not None:
            out["url"] = template_help.content_path(template_id, document["id"])
            out["file"] = document
    return out


def template(template_id: Any) -> dict[str, Any] | None:
    """`GET /work/templates/{id}` — `Work-022`'s Overview: the header, the
    bundle, the counts and the derived status. A cross-tenant id reads as
    absent (HR-1)."""
    header = metering_seam.template(template_id)
    if header is None:
        return None
    return {
        **_template_list_row(header),
        "bundle": _collection_rows(header["id"]),
        "orders_raised": metering_seam.orders_raised_from(header["id"]),
    }


def template_versions(template_id: Any) -> dict[str, Any] | None:
    """`Work-022`'s Versions tab — newest first, each with the orders it
    produced, and the sentence underneath that says nothing was rewritten.

    ⚠ **`orders_raised` IS COUNTED FROM `work_orders`, NOT STORED HERE.** It
    is the whole demonstration of `BR-WRK-008`: publishing v2 leaves the four
    v1 orders reading v1, and a count that lived on the version row would have
    to be maintained by the raise to say so.
    """
    header = metering_seam.template(template_id)
    if header is None:
        return None
    by_version = metering_seam.orders_raised_by_version(header["id"])
    rows = list(
        work_models.WorkOrderTemplateVersion.objects.filter(
            tenant_id=core_tenancy.current_tenant_id(), template_id=header["id"]
        ).order_by("-version")
    )
    current = int(header.get("version") or 0)
    return {
        "template_no": header["template_no"],
        "name": header["name"],
        "versions": [
            {
                "version": row.version,
                "published_at": row.published_at.isoformat(),
                "published_by": None if row.published_by is None else str(row.published_by),
                "change_note": row.change_note,
                "orders_raised": by_version.get(row.version, 0),
                "status": "current" if row.version == current else "superseded",
            }
            for row in rows
        ],
        "orders_raised": sum(by_version.values()),
    }


def template_usage(template_id: Any) -> dict[str, Any] | None:
    """`Work-022`'s Usage tab — the total, and the per-version breakdown that
    sums to it (`US-WRK-018` TC-7). The sum is asserted rather than assumed:
    both figures come from the same grouped query."""
    header = metering_seam.template(template_id)
    if header is None:
        return None
    by_version = metering_seam.orders_raised_by_version(header["id"])
    return {
        "orders_raised": sum(by_version.values()),
        "by_version": [
            {"version": version, "orders_raised": count}
            for version, count in sorted(by_version.items(), reverse=True)
        ],
    }


#: `GET /work/template-packs` — the three starter packs step 1 of the builder
#: offers, as CONSTANTS. They are PLATFORM content, identical for every tenant
#: and editable by none, so they are not a table: a table would be eleven
#: copies of the same three rows with nothing to keep them equal.
#:
#: ⚠ **THE PACKS ARE NOT SEEDED TEMPLATES.** A pack PREFILLS the builder
#: (wave E, `US-WRK-016`); the 24 seeded starters are rows a tenant owns
#: (`BR-WRK-013`). Confusing the two would make a utility's edits vanish on
#: the next provisioning sweep.
#:
#: ⚠ **THE ROWS MOVED TO `apps/work/packs/` IN WAVE E AND THIS IS NOW AN
#: ALIAS.** Wave D shipped them here as counts alone, and the count for
#: *Inspection* said 3 tasks where three documents draw 4 — a number nothing
#: could contradict because there was nothing to count. `packs.summary()`
#: counts the rows; this name survives so an existing import keeps working.
TEMPLATE_PACKS: tuple[dict[str, Any], ...] = work_packs.PACKS


def template_packs() -> list[dict[str, Any]]:
    """The three platform packs, with the rows step 1 prefills from.

    Each answer carries the pack's identity, its counted `Work-014` summary,
    the total minutes its tasks come to, and the BUNDLE itself in the exact
    shape `PUT /work/templates/{id}/{collection}` takes — so the builder can
    post a pack's prefill back without translating it.

    ⚠ **MATERIALS ARE RESOLVED AGAINST THE TENANT'S OWN PARTS REGISTER, AND A
    PART THIS UTILITY HAS NOT ENTERED IS DROPPED AND NAMED.** A pack is
    platform data and a part is the utility's row, so the pack can only say
    *MTR-E1P*. Dropping silently would be an absence nobody can see, which is
    what `DEF-CUS-3653` cost; `unresolved_parts` says which numbers were not
    found so step 4 can tell a person what is missing and where to add it.

    A COPY per call, all the way down, so a caller that mutates what it is
    handed cannot edit the constant for the process.
    """
    tenant_id = core_tenancy.current_tenant_id()
    by_number = {
        row.part_no: row
        for row in work_models.Part.objects.filter(tenant_id=tenant_id, active=True)
    }
    answer: list[dict[str, Any]] = []
    for pack in work_packs.PACKS:
        bundle = pack["bundle"]
        materials: list[dict[str, Any]] = []
        missing: list[str] = []
        for row in bundle["materials"]:
            part = by_number.get(row["part_no"])
            if part is None:
                missing.append(row["part_no"])
                continue
            materials.append(
                {
                    "part_id": str(part.id),
                    "part_no": part.part_no,
                    "name": part.name,
                    "planned_qty": row["planned_qty"],
                    # hard rule 3 — the unit comes from the part, never typed
                    # again, so a template and its register cannot disagree.
                    "unit_of_measure": part.unit_of_measure,
                }
            )
        answer.append(
            {
                "code": pack["code"],
                "name": pack["name"],
                **work_packs.summary(pack),
                "est_duration_minutes": work_packs.est_minutes(pack),
                "bundle": {
                    "details": dict(bundle["details"]),
                    "safety": [dict(row) for row in bundle["safety"]],
                    "tasks": [dict(row) for row in bundle["tasks"]],
                    "materials": materials,
                    "readings": [dict(row) for row in bundle["readings"]],
                    "help": [dict(row) for row in bundle["help"]],
                },
                # The COUNT above is the pack's own (what `Work-014` promises);
                # this list is what this tenant will actually get.
                "unresolved_parts": missing,
            }
        )
    return answer


# ══════════════════════════════════════════════════════════════════════════
# CR-070 WAVE E · WHAT NEW CONNECT STEP 6 PROPOSES (US-WRK-017, BR-WRK-016)
# ══════════════════════════════════════════════════════════════════════════


def proposed_work_orders(service_codes: Any, *, in_sequence: bool = True) -> dict[str, Any]:
    """`GET /connections/proposed-work-orders?services=electric,water`.

    `BR-WRK-016`, verbatim: *"New Connect step 6 proposes work orders from the
    enabled services' PUBLISHED templates that hold a place in the service's
    connection sequence — `work_order_templates.sequence` >= 1, the column
    every seeded starter carries and an authored exchange, leak-investigation
    or backflow template does not — in sequence order; the clerk may remove
    any; nothing is written until step 9."*

    Four conditions and every one of them is IN THE QUERY, not in a comprehension
    afterwards (the `G88` shape: a filter that lives in a template is one
    refactor from a leak):

      * the tenant in context, which is the queryset the seam hands over and
        RLS `FORCE` underneath it;
      * the SERVICES the clerk ticked at step 5;
      * **published** — `active = true` AND `version >= 1`. A draft is not
        proposed (`US-WRK-017` TC-4) and neither is a deactivated template,
        because `BR-WRK-012` says deactivating stops NEW orders and this is
        where new orders come from;
      * **`sequence >= 1`** — the clause `DEF-WRK-3573` added. Without it,
        after `J60` publishes *Meter exchange — residential* Electric holds
        three published templates and step 6 would propose SIX where
        `US-WRK-017` TC-1 and `J60` step 11 both say **five**.

    ⚠ **THIS READS AND WRITES NOTHING, AND THAT IS THE STORY'S CENTRAL RULE**
    (`BR-MET-112`: the wizard writes nothing until step 9). Removing a proposed
    row is wizard state in a browser; the wizard carries what survives into its
    own commit.

    ⚠ **`in_sequence` IS A PARAMETER SINCE CR-070 WAVE P, AND IT IS ONE READER
    RATHER THAN TWO (P2: *"reusing E2's reader, never a second copy"*).** The
    sequence clause above splits every published template into two sets and the
    split is not arbitrary:

      * **`sequence >= 1` — the jobs that BUILD a service.** Meter set, service
        connection, pressure test and light-up. New Connect step 6 proposes
        these, and so does an approved service request, because a request IS an
        application to build something.
      * **`sequence` 0 or absent — the jobs you do to a service that ALREADY
        EXISTS.** A final read, a turn-on, a changeover read, a reconnect visit,
        a leak investigation, a meter exchange. A move-out, a move-in, a
        transfer and a reconnect all act on a live connection, so offering them
        *Meter set* would be offering to build the thing the customer already
        has.

    **Both clauses stay IN THE QUERY** (the `G88` shape) rather than becoming a
    comprehension afterwards; what changed is which of two predicates the query
    carries, not where the predicate lives.

    ⚠ **IT LIVES IN `apps/work` THOUGH ITS PATH BEGINS `connections/`.** The
    noun is metering's and the CONTENT is Work's — the same shape wave O used
    for `premises/{id}/work-orders`, and the reason `apps/customers` may read
    this over HTTP and must never reach into `work_order_templates` with an
    ORM query (`A7`, `G78`'s mirror).
    """
    wanted = [
        code.strip().lower()
        for code in (
            service_codes.split(",") if isinstance(service_codes, str) else list(service_codes or [])
        )
        if str(code).strip()
    ]
    if not wanted:
        # No services ticked is not an error: step 5 may simply not have been
        # answered yet, and an empty proposal is the truthful answer to it.
        return {"services": [], "proposed": [], "count": 0}
    rows = metering_seam.templates_queryset().filter(
        service__code__in=wanted, active=True, version__gte=1
    )
    rows = (
        rows.filter(sequence__gte=1)
        if in_sequence
        else rows.filter(Q(sequence__isnull=True) | Q(sequence__lt=1))
    )
    rows = rows.order_by("service__code", "sequence", "name")
    proposed = [_proposed_row(metering_seam._template_row(row)) for row in rows]
    return {"services": wanted, "proposed": proposed, "count": len(proposed)}


def _proposed_row(row: dict[str, Any]) -> dict[str, Any]:
    """One line of `Work-004`'s step 6 — the NAME a clerk reads and the flag
    that says which one completes the connection.

    `id` and `version` travel because step 9's commit has to stamp both on the
    order it raises (`BR-WRK-008` — copy, never link, and the version is what
    says which copy). `template_no` is the visible reference (B14 rule 31); the
    uuid is never drawn.
    """
    return {
        "template_id": row["id"],
        "template_no": row["template_no"],
        "name": row["name"],
        "service": row["service"],
        "scope": row["scope"],
        "sequence": row["sequence"],
        "job_type": row["job_type"],
        "is_gate": row["is_gate"],
        "version": row["version"],
        "est_duration_minutes": (
            None
            if row.get("est_duration") is None
            else int(row["est_duration"].total_seconds() // 60)
        ),
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-004@87b94265 · US-WRK-001@87b94265 (EP-WRK-01) · 08-screen-layouts.md Work-007 · 09-component-inventory.md W1
# generated: 2026-09-03 by the CR-070 wave A build lane
# checklist: A✔ B✔ C✔ D✔ E✔(OrdersPage.tsx) F✔ G✔ H=n/a
# gates: G78 · pytest tests/test_us_wrk_004_orders_list.py
# exceptions: the six filters, the KPI strip and the bulk row of Work-007 are wave G's (WM-16, WM-17) — stated so their absence is a plan and not a gap
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────


# ══════════════════════════════════════════════════════════════════════════
# CR-070 wave N · the read side — `Work-025` Issue log · `Work-027`
# Performance · `Work-030` Labour rates · `Work-032` the report
# ══════════════════════════════════════════════════════════════════════════


def _labour_rate_row(row: Any) -> dict[str, Any]:
    """`Work-030` — the ONE screen in the product that shows money at 4 dp.

    Every other screen displays two (hard rule 2), and this one is the
    exception because the stored value is what is being EDITED: a supervisor
    typing `48.5000` must see `48.5000` back, or the screen and the column
    disagree about what was saved. The report shows `48.50`.

    ⚠ **A CONTRACTOR'S OVERTIME IS `None`, WHICH THE SCREEN DRAWS AS A DASH**
    — `BR-WRK-020`, *"an agency invoices its own overtime… The dash is the
    honest value"*. It is not `0.0000`, which would read as free overtime.
    """
    return {
        "id": str(row.id),
        "role": row.role,
        "role_label": row.role_label or row.role.replace("_", " ").capitalize(),
        "hourly": f"{row.hourly:.4f}",
        "overtime_hourly": (
            f"{row.overtime_hourly:.4f}" if row.overtime_hourly is not None else None
        ),
        "overtime_after_hours": (
            f"{row.overtime_after_hours:g}" if row.overtime_after_hours is not None else None
        ),
        "effective_from": row.effective_from.isoformat(),
        "superseded_on": row.superseded_on.isoformat() if row.superseded_on else None,
        "current": row.superseded_on is None,
    }


def labour_rate(rate_id: Any) -> dict[str, Any]:
    from apps.work import models as work_models

    row = work_models.LabourRate.objects.filter(
        tenant_id=core_tenancy.current_tenant_id(), id=rate_id
    ).first()
    if row is None:
        raise errors.NotFoundError(message_key="work.labour_rate_not_found")
    return _labour_rate_row(row)


def labour_rates_page(*, page: Any = 1, per: Any = DEFAULT_PAGE_SIZE) -> dict[str, Any]:
    """`GET /work/labour-rates` — `Work-030`, current rows then superseded.

    Default sort *effective from desc* per the capability matrix, with the
    CURRENT rows first: the screen's job is *what does an hour cost today*,
    and a superseded row is history a reader scrolls to.
    """
    from apps.work import models as work_models

    qs = work_models.LabourRate.objects.filter(
        tenant_id=core_tenancy.current_tenant_id()
    ).order_by(F("superseded_on").asc(nulls_first=True), "-effective_from", "role", "id")
    #: ⚠ `nulls_first` ON THE COLUMN, not `superseded_on__isnull` — a lookup is
    #: not an expression and Django raises `FieldError` for it in `order_by`.
    #: A NULL `superseded_on` IS *current*, so nulls-first is the screen's own
    #: "what does an hour cost today, then the history" order.
    total = qs.count()
    size = clamp_page_size(per)
    last = max(1, math.ceil(total / size))
    number = _page_number(page, last)
    start = (number - 1) * size
    return {
        "rows": [_labour_rate_row(row) for row in qs[start : start + size]],
        "page": number,
        "per": size,
        "total": total,
        "last_page": last,
    }


def _part_issue_row(row: Any) -> dict[str, Any]:
    """One movement — *−1 · D. Ortiz · (ref WO-4822)*.

    ⚠ **NO RUNNING BALANCE, AND THAT IS `US-WRK-050` TC-4 BY NAME.** The
    Movements tab lists what happened and does not accumulate it, because a
    running balance IS an on-hand figure with extra steps and there is no
    stock (`OQ-WRK-1490`, closed to option (a)).
    """
    holder = row.issued_to_technician or row.issued_to_crew
    return {
        "id": str(row.id),
        "part_id": str(row.part_id),
        "part_no": row.part.part_no,
        "part_name": row.part.name,
        "qty": f"{row.qty:.4f}",
        "unit_of_measure": row.part.unit_of_measure,
        "issued_to": _holder_name(holder),
        "purpose": row.purpose,
        "order_ref": row.order_ref,
        "at": row.at.isoformat(),
        #: A POSITIVE quantity is a return (`+4 · Unused on job`), a negative
        #: one an issue. The screen segments on this rather than on a `kind`
        #: column, because the sign IS the fact and a second column could
        #: disagree with it.
        "direction": "return" if row.qty > 0 else "issue",
    }


def _holder_name(holder: Any) -> str:
    if holder is None:
        return ""
    user = getattr(holder, "user", None)
    if user is not None:
        return (getattr(user, "full_name", "") or getattr(user, "email", "") or "").strip()
    return getattr(holder, "name", "") or ""


def part_issue(issue_id: Any) -> dict[str, Any]:
    from apps.work import models as work_models

    row = (
        work_models.PartIssue.objects.select_related(
            "part", "issued_to_technician__user", "issued_to_crew"
        )
        .filter(tenant_id=core_tenancy.current_tenant_id(), id=issue_id)
        .first()
    )
    if row is None:
        raise errors.NotFoundError(message_key="work.part_issue_not_found")
    return _part_issue_row(row)


def part_issues_page(
    *,
    q: str | None = None,
    part_id: Any = None,
    purpose: str | None = None,
    page: Any = 1,
    per: Any = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
    """`GET /work/parts/issues` — `Work-025`'s Issue log, newest first.

    Search matches the part and who took it, filter on purpose — the
    capability matrix's own row. Applied in SQL BEFORE paging (`DEF-1702`: a
    filter over the page in hand is a subset of a subset).
    """
    from apps.work import models as work_models

    qs = work_models.PartIssue.objects.select_related(
        "part", "issued_to_technician__user", "issued_to_crew"
    ).filter(tenant_id=core_tenancy.current_tenant_id())
    if part_id:
        qs = qs.filter(part_id=part_id)
    if purpose and purpose.strip():
        qs = qs.filter(purpose__icontains=purpose.strip())
    if q and len(q.strip()) >= 2:
        term = q.strip()
        qs = qs.filter(
            Q(part__part_no__icontains=term)
            | Q(part__name__icontains=term)
            | Q(order_ref__icontains=term)
        )
    qs = qs.order_by("-at", "id")
    total = qs.count()
    size = clamp_page_size(per)
    last = max(1, math.ceil(total / size))
    number = _page_number(page, last)
    start = (number - 1) * size
    return {
        "rows": [_part_issue_row(row) for row in qs[start : start + size]],
        "page": number,
        "per": size,
        "total": total,
        "last_page": last,
    }


def work_order_reports(order_id: Any) -> list[dict[str, Any]]:
    """`GET /work-orders/{id}/reports` — the versions, newest first.

    `Work-008` lists them. A correction is `-v2` BESIDE `-v1`; neither is
    overwritten (`BR-WRK-050`), so this is a list and never a single row.
    """
    from apps.work import models as work_models

    rows = work_models.WorkOrderReport.objects.filter(
        tenant_id=core_tenancy.current_tenant_id(), work_order_id=order_id
    ).order_by("-version")
    return [
        {
            "id": str(row.id),
            "version": row.version,
            "generated_at": row.generated_at.isoformat(),
            "total": f"{row.total:.2f}",
            #: NULL until wave `K` adds the `work_order_report` document kind
            #: (`03-field-map.md` row 28). The figures are frozen regardless.
            "document_id": str(row.document_id) if row.document_id else None,
        }
        for row in rows
    ]


def work_order_cost_lines(order_id: Any) -> dict[str, Any]:
    """The report's COST section — the persisted lines and their total.

    ⚠ **READ, NEVER RECOMPUTED.** The lines were written at acceptance and are
    frozen by `work/0011`'s trigger; recomputing here would let an edited part
    price or a superseded rate change a report after it was signed. That is
    the whole reason `work_order_cost_lines` exists as a persisted table and
    not only as a function.

    ⚠ **NO TAX ROW, AND THE TOTAL IS THE SUM OF THE DISPLAYED AMOUNTS** —
    `138.42`, not the wireframe's `149.84` (`BR-WRK-052`, `BR-WRK-051`).
    """
    from apps.work import models as work_models

    tenant_id = core_tenancy.current_tenant_id()
    # PO answer 11 (2026-10-21) — an office reopen after acceptance makes the
    # next acceptance write `-v2` with its own lines beside `-v1`'s. The COST
    # section is the LATEST version's; the older lines stay frozen and are read
    # by nothing that adds them up (`work/0045`).
    latest = (
        work_models.WorkOrderCostLine.objects.filter(tenant_id=tenant_id, work_order_id=order_id)
        .order_by("-report_version")
        .values_list("report_version", flat=True)
        .first()
    )
    rows = work_models.WorkOrderCostLine.objects.filter(
        tenant_id=tenant_id, work_order_id=order_id, report_version=latest or 1
    ).order_by("sequence", "id")
    lines = [
        {
            "kind": row.kind,
            "description": row.description,
            "qty": f"{row.qty:g}",
            "unit": row.unit,
            "rate": f"{row.rate:.4f}",
            #: Four stored, TWO displayed (hard rule 2). Both are published
            #: because the total is the sum of the second.
            "amount": f"{row.amount:.4f}",
            "amount_display": f"{_display(row.amount):.2f}",
        }
        for row in rows
    ]
    total = sum((_display(row.amount) for row in rows), Decimal("0.00"))
    return {"lines": lines, "total": f"{total:.2f}"}


def _display(amount: Any) -> Decimal:
    return Decimal(amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


#: P5.6 — the by-job-type table's declared sorts. `volume` (most first) is the
#: default and the drawing's order (image 65).
PERFORMANCE_SORTS: tuple[str, ...] = ("volume", "job_type", "sla_met", "first_time_fix", "total_cost")


def performance(
    *,
    period: str | None = None,
    page: Any = 1,
    per: Any = None,
    sort: str | None = None,
    direction: str | None = None,
) -> dict[str, Any]:
    """`GET /work/performance` — `Work-027`, `US-WRK-054`, `BR-WRK-053`; image 65.

    Arithmetic over completed orders: volume, SLA against the promise,
    first-time fix, and cost from the persisted cost lines.

    ⚠ **EVERY TALLY IS SQL AND THE TABLE IS PAGED IN SQL** (`CR-168-BRC10` P5.6,
    lane SRV-4). Until round 5 the first-time-fix count and the by-type buckets
    looped over EVERY completed order in Python and the table was unpaged
    (NFR-3). Now each order is annotated once — its promise, whether a later
    order follows it, its cost as the sum of its ROUNDED lines (`BR-WRK-051`) —
    and the tiles and every row are aggregates over that one annotated set, so
    the headline and its rows cannot disagree (P5.1's server half).

    ⚠ **SLA MET COUNTS EVERY COMPLETED JOB THAT HAS A PROMISE** (P5.9, PO answer
    (1) of 2026-10-04: *"(b), so every job has a promise to measure against"*):
    its own `due_at`, else its raise plus the DEFAULT target's hours (Normal,
    72 h). Until round 5 an undated job was left out of the denominator, and on
    the demo — 3 of 40 dated — that printed *SLA met 100.0%* over rows of 0.0%.
    **Held time is excluded** (P5.2): a job on hold for two days of rain is due
    two days later. A job with no promise at all — no date, and a tenant with
    no default — is still left out, because a promise nobody made cannot have
    been kept.

    ⚠ **AND NOTHING ON THIS PAGE CARRIES THE TOTAL ANYWHERE.** r10 says the
    figure *"feeds the O&M / labour line in Finance → Cost & Margin"*. **That
    arrow is not built** — `BR-WRK-004`, `OQ-WRK-1491` closed 2026-09-04 to
    option (a), and `CR-028` D3 is the Product Owner removing exactly that
    sentence for asset maintenance. So this payload carries no route, no link
    and no account code, `US-WRK-054` TC-3 greps for *Finance*, *Cost &
    Margin*, *O&M* and `5300`, and `G111` keeps it that way.
    """
    import math

    from django.db.models import (
        Count,
        DecimalField,
        Exists,
        OuterRef,
        Q as DQ,
        Subquery,
        Sum,
        Value,
    )
    from django.db.models.functions import Coalesce, Round

    from apps.work import models as work_models
    from apps.work import promise
    from apps.work.seams import metering_seam

    tenant_id = core_tenancy.current_tenant_id()
    orders = metering_seam.completed_work_orders_queryset()
    start, end = _period_bounds(period)
    if start is not None:
        orders = orders.filter(completed_at__gte=start)
    if end is not None:
        orders = orders.filter(completed_at__lt=end)

    money = DecimalField(max_digits=18, decimal_places=4)
    # PO answer 11 — only the LATEST report version's lines count; a job the
    # office reopened after acceptance carries `-v1`'s frozen lines beside
    # `-v2`'s, and adding both would cost it twice.
    latest_version = (
        work_models.WorkOrderCostLine.objects.filter(
            tenant_id=tenant_id, work_order_id=OuterRef(OuterRef("pk"))
        )
        .order_by("-report_version")
        .values("report_version")[:1]
    )
    line_cost = (
        work_models.WorkOrderCostLine.objects.filter(
            tenant_id=tenant_id,
            work_order_id=OuterRef("pk"),
            report_version=Subquery(latest_version),
        )
        .order_by()
        .values("work_order_id")
        .annotate(total=Sum(Round("amount", 2)))
        .values("total")
    )
    annotated = orders.order_by().annotate(
        promise_due=promise.due_expr(promise.default_hours(), open_clock=False),
        followed=Exists(metering_seam.followed_by_queryset()),
        cost=Coalesce(Subquery(line_cost, output_field=money), Value(Decimal("0"), output_field=money)),
    )
    figures = dict(
        volume=Count("id"),
        measured=Count("id", filter=DQ(promise_due__isnull=False)),
        met=Count("id", filter=promise.on_time_q()),
        ftf=Count("id", filter=DQ(followed=False)),
        total_cost=Sum("cost"),
    )
    whole = annotated.aggregate(**figures)

    grouped = annotated.values("type").annotate(**figures)
    key = {
        "volume": "volume",
        "job_type": "type",
        "sla_met": "met",
        "first_time_fix": "ftf",
        "total_cost": "total_cost",
    }.get(sort or "volume", "volume")
    descending = (direction or ("asc" if key == "type" else "desc")).lower() == "desc"
    grouped = grouped.order_by(f"-{key}" if descending else key, "type")
    total = grouped.count()
    size = clamp_page_size(per)
    last = max(1, math.ceil(total / size))
    number = _page_number(page, last)
    first = (number - 1) * size

    rows = []
    for bucket in grouped[first : first + size]:
        volume = bucket["volume"]
        cost = _display(bucket["total_cost"] or 0)
        rows.append(
            {
                "job_type": bucket["type"] or "—",
                "volume": volume,
                "sla_measured": bucket["measured"],
                "sla_met": bucket["met"],
                "sla_met_pct": _pct(bucket["met"], bucket["measured"]),
                "first_time_fix_pct": _pct(bucket["ftf"], volume),
                "cost_per_job": f"{_display(cost / volume) if volume else Decimal('0.00'):.2f}",
                "total_cost": f"{cost:.2f}",
            }
        )
    total_volume = whole["volume"] or 0
    total_cost = _display(whole["total_cost"] or 0)
    return {
        "period": period or "",
        "tiles": {
            "sla_met_pct": _pct(whole["met"] or 0, whole["measured"] or 0),
            "sla_measured": whole["measured"] or 0,
            "sla_met": whole["met"] or 0,
            "first_time_fix_pct": _pct(whole["ftf"] or 0, total_volume),
            "cost_per_job": (
                f"{_display(total_cost / total_volume):.2f}" if total_volume else "0.00"
            ),
            "volume": total_volume,
        },
        "rows": rows,
        "page": number,
        "per": size,
        "total": total,
        "totals": {"volume": total_volume, "total_cost": f"{total_cost:.2f}"},
    }


def _pct(part: int, whole: int) -> str:
    """One decimal place, as `Work-027` draws it (`94.2%`).

    A zero denominator is `0.0` and is DRAWN as a zero (`US-WRK-054` TC-6 —
    *"zeros drawn as zeros"*), never hidden: a new utility with no completed
    work should see that it has none, not an empty page.
    """
    if not whole:
        return "0.0"
    return f"{(Decimal(part) * 100 / Decimal(whole)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)}"


def _period_bounds(period: str | None):
    """`period=2026-03` or `period=2026` — a month or a year, else everything."""
    from datetime import date, datetime, timezone as dt_timezone

    if not period:
        return None, None
    text = str(period).strip()
    try:
        if len(text) == 7:
            year, month = int(text[:4]), int(text[5:7])
            start = datetime(year, month, 1, tzinfo=dt_timezone.utc)
            end = datetime(year + (month == 12), (month % 12) + 1, 1, tzinfo=dt_timezone.utc)
            return start, end
        if len(text) == 4:
            year = int(text)
            return (
                datetime(year, 1, 1, tzinfo=dt_timezone.utc),
                datetime(year + 1, 1, 1, tzinfo=dt_timezone.utc),
            )
    except (ValueError, TypeError):
        return None, None
    return None, None
