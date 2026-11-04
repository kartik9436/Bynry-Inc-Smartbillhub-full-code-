# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-024 (the dispatch columns and the third axis) · US-WRK-025
#           (the append-only assignment history) · US-WRK-026 (six filters and
#           no seventh) · US-WRK-027 (bulk acts, one row per order) ·
#           US-WRK-011 (the Area filter is tenancy's own list)
#           Screens: Work-007 (the dispatcher), Work-008's audit tab (wave H)
# Rules:    BR-WRK-018 (a priority carries SLA hours; due_at = raise + SLA) ·
#           BR-WRK-022 (areas are tenancy.Area, never a copy) · BR-WRK-023 (the
#           third axis) · BR-WRK-025 (append-only) · BR-WRK-026 (exactly six
#           filters) · BR-WRK-027 (one row PER ORDER, never one for the batch) ·
#           BR-WRK-029 (only a matching skill is offered) · CLAUDE.md hard
#           rule 1 (tenant scoping) · hard rule 7 (every act writes audit_log)
# Tests:    06-backend/tests/test_us_wrk_024_027_dispatch.py ·
#           tests/test_us_wrk_025_dispatch_pg.py (the trigger, on PostgreSQL)
# Impacts:  apps/work/api.py (ten routes) · config/urls.py · 07-frontend/src/
#           features/work/OrdersPage.tsx · workEndpoints.ts
# ───────────────────────────────────────────────────────
"""The dispatcher — one place to see every open order and drive it.

WHAT A DISPATCHER ACTUALLY DOES, AND WHY THE SHAPES ARE WHAT THEY ARE
---------------------------------------------------------------------
Five tiles, six filters, one list sorted by promise, and three acts that move
many jobs at once. Three decisions in this file are worth reading before
changing anything in it:

**1 · THE HISTORY IS THE RECORD AND THE ORDER CARRIES A CACHE.** Every act
appends a `work_order_assignments` row FIRST and refreshes
`work_orders.assignee_*` SECOND, inside one transaction. A cache can be rebuilt
from a history; a history cannot be rebuilt from a cache. `work/0009`'s trigger
means the row cannot be edited afterwards even by a person at a psql prompt.

**2 · A BULK ACT IS A LOOP, NOT A STATEMENT.** `BR-WRK-027`, verbatim: *"Each
writes one assignment or audit row PER ORDER — never one row for the batch."*
So `bulk_act` runs the single-order service once per id and returns a result per
id. It would be one `.update()` if the rule allowed it, and the rule exists
because *"who was assigned WO-4823, and by whom"* must be answerable for one
order without knowing it happened to be ticked alongside seven others.

⚠ **AND EACH ORDER GETS ITS OWN SAVEPOINT (hard-won law 14).** One refused
order must not take the other seven down with it. On PostgreSQL a failed
statement poisons the whole transaction, so `try/except IntegrityError:
continue` inside one `atomic()` loses the entire batch at COMMIT — and **the
test suite runs on in-memory SQLite, which has no aborted-transaction state, so
the broken version passes everything and fails on the first refused row in
production.** The nested `transaction.atomic()` per order is the only option,
not the tidy one. `tests/test_us_wrk_025_dispatch_pg.py` proves it on real
PostgreSQL because the default suite cannot.

**3 · SIX FILTERS, AND A SEVENTH IS A `400`.** This is the one route in the
product that REFUSES an undeclared query parameter. `BR-SHL-011`'s house rule is
that an unknown param is ignored, and `BR-WRK-026` overrides it here on purpose:
a dispatcher who types a filter the server silently drops is looking at a list
they believe is narrower than it is, and acting on it in bulk. Ignoring is the
safe default for a list you read; it is the wrong default for a list you drive.
The allow-list is `FILTER_PARAMS` plus `page`/`per`, and it is checked at the
API boundary where the raw query string still exists.
"""

from __future__ import annotations

import logging
import math
import uuid
from datetime import datetime, time, timedelta
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.work import models as work_models
from apps.work import push, workforce
from apps.work.seams import metering_seam, tenancy_seam
from core import audit as core_audit
from core import errors
from core import jobs as core_jobs
from core import tenancy as core_tenancy
from core.pagination import DEFAULT_PAGE_SIZE, clamp_page_size

logger = logging.getLogger("smartbillhub.work.dispatch")

#: `BR-WRK-026` — *"The dispatcher list has exactly six filters — search, type,
#: status, priority, technician, area."* SIX, and the count is asserted by
#: `US-WRK-026` TC-1 reading this tuple rather than counting chips on a screen.
FILTER_PARAMS: tuple[str, ...] = ("q", "type", "status", "priority", "technician", "area")

#: The house pagination params, which are not filters and never were.
PAGE_PARAMS: tuple[str, ...] = ("page", "per")

#: Nor are these. The sort is FIXED on this list — priority rank, then due time
#: — so `parse_list_params` is called with no allowed sorts and both are ignored
#: (`BR-SHL-011`'s fallback law). They are named here so a pasted URL carrying
#: them is not read as a seventh filter and refused.
SORT_PARAMS: tuple[str, ...] = ("sort", "dir")

#: `BR-WRK-027` — the three acts a selection may be driven with.
BULK_ACTS: tuple[str, ...] = ("assign", "reschedule", "priority")


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


# ══════════════════════════════════════════════════════════════════════════
# READS
# ══════════════════════════════════════════════════════════════════════════


def check_filters(param_names: Any) -> None:
    """`BR-WRK-026` — refuse a SEVENTH filter, by name.

    ⚠ **THIS ROUTE AND `BR-SHL-011` DISAGREED, AND NEITHER SIGNED STATEMENT
    MOVES.** `07-endpoints.md` row 61 says *"exactly six filters; `400` on a
    seventh"*. `BR-SHL-011`'s house rule says an undeclared parameter is
    **ignored, never refused** — and wave O SHIPPED A TEST asserting exactly
    that on this route (`test_wave_o_br_wrk_026_did_not_move_the_dispatcher_
    still_takes_six`, which sends `f.premises_id` and expects a list back).
    A first draft of this function refused everything unknown and turned that
    test red.

    **The two rules govern two different name spaces, and reading them that way
    satisfies both:**

      * `f.<name>` is the SHARED TABLE FRAMEWORK's grammar for a filter a screen
        DECLARED in its `TableConfig`. This route declares none in it, so
        `BR-SHL-011` governs and an `f.` param is ignored — which is precisely
        what wave O's test is there to prove: no seventh filter EXISTS.
      * The six of row 61 are BARE query parameters, spelled `type=`, `status=`,
        `priority=`, `technician=`, `area=` beside `q=`. A seventh bare name is
        a seventh filter written the way the six are written, and THAT is what
        gets the `400`.

    **Why refuse at all, when the house rule is to ignore.** Ignoring is the
    right default for a list you READ: a stale bookmark should still show you
    something. It is the wrong default for a list you DRIVE. A dispatcher whose
    filter was silently dropped is looking at a wider list than they believe,
    and the next thing they do on this screen is tick rows and act on all of
    them at once. Recorded in the decision log 2026-09-05.
    """
    allowed = set(FILTER_PARAMS) | set(PAGE_PARAMS) | set(SORT_PARAMS)
    unknown = sorted(
        name
        for name in param_names
        if name not in allowed and not str(name).startswith("f.")
    )
    if unknown:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="work.dispatch.filter_unknown",
            br_ref="BR-WRK-026",
            params={"filter": unknown[0], "count": len(FILTER_PARAMS)},
        )


def _open_queryset() -> Any:
    """Every open order of the tenant in context, with the dispatcher's joins.

    Open is `state ∈ planned · in_progress · blocked` — wave A's window, reused
    rather than re-stated, so this list and the Orders tab cannot disagree about
    what *open* means. The dispatch axis narrows it further only when the STATUS
    filter is used.
    """
    return metering_seam.dispatch_queryset()


def _apply_filters(qs: Any, filters: dict[str, Any]) -> Any:
    """The five chips. Each is an id or a code the utility itself published —
    nothing here invents a vocabulary."""
    if filters.get("type"):
        # By catalogue id, or by the words a clerk typed before the catalogue
        # existed: `type_id` was NULL on every row until wave G started writing
        # it, so a filter that only matched the FK would silently hide every
        # order raised before this wave.
        #
        # ⚠ **AND BY ITS KINDS — `DEF-WRK-5106`, fixed 2026-09-12.** This
        # matched the heading ROW and nothing beneath it, which was correct
        # while `work_order_types` was flat and stopped being correct on
        # 2026-09-07 when `BR-WRK-058` made it two-level. **Every job a clerk
        # actually files is a SUB-TYPE** — *Billing Issues*, *Odour complaint*,
        # *Low Pressure*, *Missed collection* — so picking *Consumer Complaint*
        # in the chip returned an empty list on a utility full of complaints,
        # and an empty list is indistinguishable from having none.
        #
        # ⚠ **ONE LEVEL, NEVER A PREFIX MATCH.** `BR-WRK-058` allows exactly two
        # levels (`lookups.py` refuses a grandparent), so `type_ref__parent_id`
        # is the whole of it — and picking a KIND must still narrow to that kind
        # rather than to its siblings, which is the opposite defect and the one
        # a reader of this fix would not think to check.
        #
        # ⚠ **`BR-WRK-026` DOES NOT MOVE.** Still six filters and still a 422 on
        # a seventh; this widens what the SECOND of them matches.
        qs = qs.filter(
            Q(type_ref_id=filters["type"])
            | Q(type_ref__parent_id=filters["type"])
            | Q(type__iexact=str(filters["type"]))
        )
    if filters.get("status"):
        qs = qs.filter(dispatch_state=filters["status"])
    if filters.get("priority"):
        qs = qs.filter(priority_id=filters["priority"])
    if filters.get("technician"):
        # UNASSIGNED is a real answer to *which technician*, and the tile links
        # here — `technician=none` is how the strip's first tile narrows the
        # list to what it counted.
        if str(filters["technician"]).lower() == "none":
            qs = qs.filter(assignee_technician__isnull=True, assignee_crew__isnull=True)
        else:
            qs = qs.filter(
                Q(assignee_technician_id=filters["technician"])
                | Q(assignee_crew_id=filters["technician"])
            )
    if filters.get("area"):
        # `CR-168-BRC10` P2.17 — the job's area is its BUILDING's, walked from
        # the premises (ruling 24: the raise never asks). The chip filtered
        # `work_orders.area_id`, which nothing writes: on the demo 79 of 79
        # premises carry an area and 0 of 40 orders did, so every area chip
        # read an empty list. The column stays the first leg for a job raised
        # before this round that carried it.
        from apps.work import advice

        qs = qs.filter(advice._area_q(filters["area"]))
    return qs


def _holder(order: Any) -> dict[str, Any] | None:
    """WHO HAS IT — a person, a crew, or nobody.

    Returns `None` for an unassigned job, which is what `Work-007` draws as a
    RED pill reading *Unassigned* rather than as an empty cell. A blank cell
    reads as a bug; a red pill reads as the thing a dispatcher is there to fix.
    """
    if order.assignee_technician_id:
        user = order.assignee_technician.user
        return {
            "kind": "person",
            "name": user.full_name or user.email,
            "slug": workforce.technician_slug(order.assignee_technician),
        }
    if order.assignee_crew_id:
        return {
            "kind": order.assignee_crew.kind,
            "name": order.assignee_crew.name,
            "slug": workforce.crew_slug(order.assignee_crew),
        }
    return None


def _priority_of(order: Any) -> dict[str, Any] | None:
    if order.priority_id is None:
        return None
    return {
        "id": str(order.priority_id),
        "code": order.priority.code,
        "name": order.priority.name,
        "colour": order.priority.colour,
        "rank": order.priority.rank,
    }


def _dispatch_row(order: Any, default_hours: Any = None) -> dict[str, Any]:
    """One row of `Work-007` at template W2 — **wave A's seven columns PLUS the
    dispatch ones**, never instead of them.

    ⚠ **THIS IS THE ONE `GET /work-orders` AND IT HAS TWO READERS.** The Orders
    tab drew ORDER · TYPE · PREMISE · SVC · STATE · OUTCOME · CONNECTION from
    wave A; the dispatcher draws PRIORITY · TECHNICIAN · DUE · STATUS · RAISED
    BY. They are ONE list with one route, so the row is the UNION and the
    **Columns ▾** chooser decides which of them a given dispatcher sees — which
    is precisely what the drawing puts that control there for.

    The first draft of this function returned only the dispatch half, and
    `test_us_wrk_004` went red on `KeyError: 'connection'`. Worth recording:
    nothing else would have caught it. `tsc` is happy with a narrower object,
    the screen renders an empty cell, and a CONNECTION column that silently
    stopped having a value looks exactly like a build that has none.

    ⚠ **NO PROSE AND NO IDS IN A CELL** (B14 rules 31 and 32). Every value here
    is a value — a number, a name, or a token the screen translates from its own
    catalogue. A uuid appears only where a link is built from it.
    """
    from apps.work import selectors as work_selectors

    return {
        **work_selectors._row(order),
        # ── the dispatcher's five, `03-field-map.md` §3 rows 6–15 ────────────
        "type": _job_name(order),
        "priority": _priority_of(order),
        "technician": _holder(order),
        "due_at": order.due_at.isoformat() if order.due_at else None,
        "window_start": order.window_start.isoformat() if order.window_start else None,
        "window_end": order.window_end.isoformat() if order.window_end else None,
        "dispatch_state": order.dispatch_state,
        # When the field closed it — image 32's CLOSED column (the gap lane
        # CREWS reported, CR §19; lane SRV-4). NULL on a job still out.
        "completed_at": order.completed_at.isoformat() if order.completed_at else None,
        # BR-WRK-024 — RAISED BY. One of the fourteen tokens wave P closed; NULL
        # on an order raised before a door stamped one, and the screen draws a
        # dash rather than inventing a reason.
        "source": order.source,
        "source_ref": order.source_ref,
        # ⚠ **WALKED FROM THE PREMISES** (`CR-168-BRC10` §7.3, P2.17's
        # finding): 79 of 79 demo premises carry an area and 0 of 40 orders
        # do, so the order's own column drew a dash on every row. The order's
        # column wins only where a dispatcher set one on purpose.
        "area": _area_of(order),
        # ── CR-168-BRC10 §7.3 · the four facts the redrawn list adds ─────────
        "technician_acceptance": _technician_acceptance(order),
        "hold": _hold_of(order),
        "accepted": (
            {
                "by": {"name": order.accepted_by.full_name or order.accepted_by.email}
                if order.accepted_by_id
                else None,
                "at": order.accepted_at.isoformat(),
            }
            if order.accepted_at
            else None
        ),
        "sla": _sla_of(order, default_hours),
    }


#: The placeholder `create_work_order` stored before `DEF-WRK-9638` for a raise
#: that sent no free-text name. Rows written then still carry it; it is READ as
#: absent so the page derives the name rather than printing a placeholder.
LEGACY_PLACEHOLDER_TYPE = "unspecified"


def _job_name(order: Any) -> str | None:
    """What the job is called: its job type, else the name it was raised with,
    else its template's — `DEF-WRK-9638` (*"WO-0043 · unspecified"*)."""
    if order.type_ref_id:
        return order.type_ref.name
    typed = (order.type or "").strip()
    if typed and typed != LEGACY_PLACEHOLDER_TYPE:
        return typed
    template = order.template if getattr(order, "template_id", None) else None
    return template.name if template is not None else None


def _area_of(order: Any) -> dict[str, Any] | None:
    area = order.area if order.area_id else None
    if area is None:
        premises = _premises_row_of(order)
        area = premises.area if premises is not None and premises.area_id else None
    if area is None:
        return None
    return {"id": str(area.id), "code": area.code, "name": area.name}


def _technician_acceptance(order: Any) -> dict[str, Any] | None:
    """The person given the job: did they take it (P0.2/P4.1)? None when nobody
    holds it; `pending` until the phone answers (the field app, P4.7)."""
    if order.declined_at is not None:
        return {
            "state": "declined",
            "at": order.declined_at.isoformat(),
            "reason": order.declined_reason,
        }
    if order.accepted_at_technician is not None:
        return {"state": "accepted", "at": order.accepted_at_technician.isoformat(), "reason": None}
    if order.assignee_technician_id or order.assignee_crew_id:
        return {"state": "pending", "at": None, "reason": None}
    return None


def _sla_of(order: Any, default_hours: Any) -> dict[str, Any]:
    """`{due_at, target, at_risk}` — what this job is measured against.

    `target` is `priority` when the job carries its own `due_at` (stamped from
    its priority at the raise, `BR-WRK-018`) and `default` when it carries none:
    PO answer (1) of 2026-10-04 measures it from the raise against the default
    target's hours (judgment J7). Held time is added back (P5.2): a job on hold
    for a day is due a day later.

    ⚠ **`at_risk` MEANS PAST ITS TARGET, FOR NOW.** The contract names a
    tenant's warning window and no such setting exists yet — it is SRV-4's, with
    the at-risk board (P5.3). Until then this is true only for an open job whose
    target has passed; never a window this lane invented.
    """
    held = timedelta(seconds=int(order.held_seconds or 0))
    if order.held_at is not None:
        held += timezone.now() - order.held_at
    if order.due_at is not None:
        due, target = order.due_at + held, "priority"
    elif default_hours and order.created_at is not None:
        due, target = order.created_at + timedelta(hours=int(default_hours)) + held, "default"
    else:
        return {"due_at": None, "target": None, "at_risk": False}
    finished = order.state == "completed" or order.dispatch_state == "cancelled"
    return {
        "due_at": due.isoformat(),
        "target": target,
        "at_risk": (not finished) and timezone.now() > due,
    }


def _premise_of(order: Any) -> dict[str, Any] | None:
    """The address, from whichever anchor carries one — the selector's own walk,
    reused so the two lists cannot disagree about where a job is."""
    from apps.work import selectors as work_selectors

    return work_selectors._premise_of(order)


def _search(qs: Any, q: str | None) -> Any:
    """`Search WO #, premise…` — what the box on the drawing says it matches.

    B14 rule 19: a box that names a field it does not match is worse than no box.
    Applied in SQL before paging (`DEF-1702`).
    """
    text = (q or "").strip()
    if not text:
        return qs
    return qs.filter(
        Q(order_no__icontains=text)
        | Q(type__icontains=text)
        | Q(type_ref__name__icontains=text)
        # ⚠ THE CONNECTION NUMBER IS A SEARCH LEG AND WAVE A'S TEST ASSERTS IT.
        # This rewrite dropped it once: the drawing's box reads *Search WO #,
        # premise…* and the fourth leg is invisible in that prompt, so it looks
        # like something the dispatcher does not need. It is `CON-26-0117` — a
        # number a clerk reads off a phone call — and narrowing a search is the
        # kind of regression nothing but its own test can see.
        | Q(connection__connection_no__icontains=text)
        | Q(connection__premises__address_line__icontains=text)
        | Q(premises__address_line__icontains=text)
        | Q(unit__premises__address_line__icontains=text)
    )


#: `CR-168-BRC10` §7.3 — the list's DECLARED sorts (`BR-SHL-011`: a sort that
#: is not declared is ignored, never refused). Each ends in a unique column so a
#: page boundary can never show one order twice (`DEF-MET-6881`'s lesson).
SORTS: dict[str, tuple[str, ...]] = {
    "priority": ("priority__rank", "due_at"),
    "due_at": ("due_at",),
    "raised": ("created_at",),
    "order_no": ("order_no",),
}


def _ordering(sort: str | None, direction: str | None, *, finished: bool) -> list[Any]:
    """The ORDER BY for the list. No declared sort → the dispatcher's own order:
    priority rank, then due time (`BR-WRK-018`) — or, for finished jobs, the
    newest close first, which is what *where did yesterday's work go* asks."""
    from django.db.models import F

    if sort not in SORTS:
        if finished:
            return [F("completed_at").desc(nulls_last=True), "-id"]
        return [models_f_nulls_last("priority__rank"), models_f_nulls_last("due_at"), "order_no", "id"]
    descending = str(direction or "").lower() == "desc"
    out: list[Any] = []
    for column in SORTS[sort]:
        expr = F(column)
        out.append(expr.desc(nulls_last=True) if descending else expr.asc(nulls_last=True))
    out.append("-id" if descending else "id")
    return out


def dispatch_page(
    *,
    q: str | None = None,
    filters: dict[str, Any] | None = None,
    page: Any = 1,
    per: Any = DEFAULT_PAGE_SIZE,
    sort: str | None = None,
    direction: str | None = None,
) -> dict[str, Any]:
    """`GET /work-orders` at wave G — the dispatcher's list.

    **SORTED BY PRIORITY RANK, THEN DUE TIME** (`BR-WRK-018`'s second sentence),
    and the footer says so in those words. Rank 1 is Urgent; an order with NO
    priority sorts last rather than first, because a job nobody set a priority on
    is not more urgent than one somebody marked Urgent — `F("priority__rank")`
    with `nulls_last` is what says that in SQL.

    The footer's `total` counts the FILTERED list and `open_total` the whole open
    window, so *Showing 8 of 10 open orders* is two facts and not one number
    presented twice (the `crews_page` posture — a count over the utility, never
    over the page).
    """
    filters = dict(filters or {})
    complete = metering_seam.dispatch_tokens().COMPLETE
    finished = filters.get("status") == complete
    if finished:
        # ⚠ **`status=complete` READS THE FINISHED JOBS, ACCEPTED OR NOT**
        # (`CR-168-BRC10` P1.6, judgment J3). The open window below holds no
        # finished job by definition, so this filter answered an empty list and
        # 23 finished demo jobs were reachable only by typing their number. It
        # is the existing STATUS filter, not a seventh (`BR-WRK-026` keeps six).
        base = metering_seam.completed_dispatch_queryset()
        filters.pop("status")
    else:
        base = _open_queryset()
    qs = _apply_filters(_search(base, q), filters)
    qs = qs.order_by(*_ordering(sort, direction, finished=finished))
    total = qs.count()
    size = clamp_page_size(per)
    last = max(1, math.ceil(total / size))
    number = max(1, min(int(page or 1), last))
    start = (number - 1) * size
    target = workforce.default_target()
    default_hours = target["hours"] if target else None
    rows = [_dispatch_row(row, default_hours) for row in qs[start : start + size]]
    # ⚠ **`open_total` IS NOT IN THE ANSWER, AND THAT IS A SIGNED CONTRACT.**
    # A11 gives this product ONE list envelope — `count`/`next`/`previous`/
    # `results` — and `apps/metering/api.py` records why a second shape is not
    # allowed. `Work-007`'s footer needs *8 of 10*, and the 10 is an AGGREGATE,
    # so it is served by `GET /work/kpis` beside the five tiles rather than
    # smuggled into the envelope. `test_us_wrk_004` asserts the envelope's exact
    # key set and caught this the first time it was written the other way.
    return {"rows": rows, "page": number, "per": size, "total": total}


def _premises_row_of(order: Any) -> Any:
    """The premises MODEL ROW a job is at, by the walk hard rule 8 mandates.

    ⚠ **THE COORDINATE IS THE PREMISES', LIKE THE ADDRESS, AND FOR THE SAME
    REASON.** `BR-MET-1161`: *"they will also draw addresses from same place
    that we can maintain the integrtiy"*. A work order declares no `lat`/`lng`
    of its own and never will, so a pin on this map and an envelope printed for
    the same job cannot point at different buildings.

    `selectors._premise_of` walks the identical anchors and shapes a dict for a
    list cell; this returns the ROW so the map can read two more columns off it.
    Two shapings of ONE walk, not two walks.
    """
    from apps.work import selectors as work_selectors

    return work_selectors._premises_row(order)


def map_pins(*, q: str | None = None, filters: dict[str, Any] | None = None) -> dict[str, Any]:
    """`GET /work-orders/map` — the day's work placed on the ground
    (`US-WRK-029`, `WM-23`, a sub-screen of `Work-007`).

    **THE SAME LIST, DRAWN DIFFERENTLY — which is why it lives in this file.**
    It reuses `_open_queryset`, `_search` and `_apply_filters` unchanged, so
    `US-WRK-029` TC-6 (*"the same six filters apply; Area = North leaves four
    pins"*) is true by CONSTRUCTION rather than by a second implementation
    agreeing with the first. A map that could disagree with the list under it
    about which jobs are open would be worse than no map.

    ⚠ **NOTHING IS PAGED.** A map of page 1 of 3 is a map of the wrong day.

    ⚠ **AN ORDER WITH NO COORDINATE IS RETURNED, NOT DROPPED** (`US-WRK-029`
    TC-3). `WO-4828` is a network job at *Elm St & 3rd* with no premises at all;
    silently omitting it would let a dispatcher believe the map is the day. So
    the answer has two lists and the screen draws the second as the *not on the
    map* strip — the posture `BR-BIL-055` takes on a bill run, where a named
    break per row beats a shorter list nobody can audit.

    **The pin's own vocabulary** (`BR-WRK-023`): `dispatch_state` gives the
    COLOUR, the priority gives the WEIGHT, and `hollow` is `True` when nobody is
    going — a fact about the ASSIGNMENT rather than about either of the other
    two, and the one a dispatcher is scanning for.
    """
    qs = _apply_filters(_search(_open_queryset(), q), dict(filters or {}))
    qs = qs.order_by(models_f_nulls_last("priority__rank"), "order_no")
    pins: list[dict[str, Any]] = []
    unplaced: list[dict[str, Any]] = []
    for order in qs:
        holder = _holder(order)
        card = {
            # `Work-008`, the job card the pin opens. The ORDER NUMBER is what a
            # person reads and quotes (B14 rule 31 — no database id on screen);
            # the uuid is here only because a link is built from it.
            "id": str(order.id),
            "order_no": order.order_no,
            "type": _job_name(order),
            "priority": _priority_of(order),
            "technician": holder,
            "dispatch_state": order.dispatch_state,
            "due_at": order.due_at.isoformat() if order.due_at else None,
        }
        premises = _premises_row_of(order)
        if premises is not None and premises.lat is not None and premises.lng is not None:
            pins.append(
                {
                    **card,
                    "lat": float(premises.lat),
                    "lng": float(premises.lng),
                    "address": premises.address_line,
                    # `WM-23` — *"hollow when unassigned"*. Computed here rather
                    # than left to the screen, so the map, the list's red
                    # *Unassigned* pill and the UNASSIGNED tile all answer one
                    # question from one place.
                    "hollow": holder is None,
                }
            )
        else:
            unplaced.append(
                {
                    **card,
                    # WHY it is not on the map, in the two cases that differ: a
                    # job at a premises nobody geocoded, and a job with no
                    # premises at all. A dispatcher can fix the first.
                    "address": premises.address_line if premises is not None else None,
                    "reason": "premises_not_geocoded" if premises is not None else "no_premises",
                }
            )
    return {"pins": pins, "unplaced": unplaced, "total": len(pins) + len(unplaced)}


def models_f_nulls_last(field: str) -> Any:
    """`ORDER BY <field> ASC NULLS LAST`, spelled once.

    Written out rather than inlined three times because the two databases
    disagree by default: PostgreSQL sorts NULLs LAST ascending, SQLite sorts
    them FIRST. A list whose top row differs between the test suite and
    production is the shape of bug that gets found by a person looking at a
    screen — Django's explicit `nulls_last` makes both say the same thing.
    """
    from django.db.models import F

    return F(field).asc(nulls_last=True)


def kpis(*, now: Any = None) -> dict[str, Any]:
    """`GET /work/kpis` — the five tiles, each with the sub-line the drawing
    gives it.

    ⚠ **EVERY FIGURE IS COUNTED OVER THE WHOLE OPEN WINDOW, NEVER OVER THE PAGE
    OR OVER THE FILTERED LIST.** A tile reading *4 unassigned* is a fact about
    the utility; a tile that changed when a dispatcher typed in the search box
    would be a fact about the search box, and nobody would trust it twice. The
    `crews_page` footer already takes this posture and this is the same call.

    ⚠ **AND THE SUB-LINES ARE FIGURES, NOT SENTENCES.** *2 of them urgent* and
    *WO-4823 · 2 days* are computed here and handed over as `urgent` and
    `worst`; the screen composes the words from its own catalogue in its own
    language (B14 rule 35 — a catalogue is written in its own language, not
    translated from English). A sentence assembled here would ship English to
    every tenant.
    """
    now = now or timezone.now()
    # `DEF-WRK-9688` — *today* is the UTILITY's day, cut as two instants. The
    # server's `localtime` and `__date` both read UTC, so from 19:00 in Brazos
    # Bend the tile counted tomorrow's jobs as today's.
    zone = tenancy_seam.tenant_timezone()
    today = now.astimezone(zone).date()
    day_start = datetime.combine(today, time.min, tzinfo=zone)
    base = _open_queryset()

    unassigned = base.filter(assignee_technician__isnull=True, assignee_crew__isnull=True)
    due_today = base.filter(due_at__gte=day_start, due_at__lt=day_start + timedelta(days=1))
    in_field = base.filter(dispatch_state__in=metering_seam.dispatch_tokens().IN_FIELD)
    overdue = base.filter(due_at__lt=now)

    # AWAITING APPROVAL is the OTHER window — `state = completed AND accepted_by
    # IS NULL` — and it is deliberately not in `base`. `BR-WRK-007`: the queue is
    # a NULL, not a table, and wave B already owns the query.
    awaiting = metering_seam.awaiting_approval_queryset()

    worst = overdue.order_by(models_f_nulls_last("due_at"), "order_no").first()
    return {
        # `Work-007`'s footer — *Showing 8 of 10 open orders* — needs the 10,
        # and it is an aggregate over the utility, which is what this endpoint
        # is for. It does NOT go in the list envelope (A11: one shape).
        "open_total": base.count(),
        "unassigned": {"count": unassigned.count()},
        "due_today": {
            "count": due_today.count(),
            # *2 of them urgent* — rank 1 is the top priority the utility
            # published, whatever it chose to call it. Reading the RANK rather
            # than the code `URGENT` means a tenant that renamed it still gets a
            # true sub-line (the `BR-AST-031` behaviour-class posture).
            "urgent": due_today.filter(priority__rank=1).count(),
        },
        "in_field": {"count": in_field.count()},
        "awaiting_approval": {"count": awaiting.count()},
        "overdue": {
            "count": overdue.count(),
            # *WO-4823 · 2 days* — the worst one, named, so the tile points at
            # something a person can act on rather than at a number.
            "worst": (
                {
                    "order_no": worst.order_no,
                    "days": max(0, (now - worst.due_at).days),
                }
                if worst is not None and worst.due_at is not None
                else None
            ),
        },
    }


def area_options() -> list[dict[str, Any]]:
    """`US-WRK-011` — the Area chip's options, **from `tenancy.Area` through the
    seam and from nowhere else**.

    `BR-WRK-022`, verbatim: *"Areas are `tenancy.Area`. Work references the
    existing lookup for the dispatcher's Area filter and the order's area ·
    sub-area; **it never duplicates it**."* This function is four lines because
    the rule is that there is nothing to build — and `US-WRK-011` TC-1's whole
    content is that a tenant adding an area in Settings sees it here with no
    Work-side write of any kind.
    """
    return tenancy_seam.areas()


def order_row(order_id: Any) -> dict[str, Any]:
    """`GET /work-orders/{id}` — one order in the dispatcher's own row shape.

    ⚠ **THE SAME SHAPE AS A LIST ROW, DELIBERATELY.** Wave H's `Work-008` opens
    from a row on this list, and a detail endpoint whose fields were spelled
    differently would make the screen re-map every value at the boundary — which
    is where a *Scheduled* becomes a *scheduled* and a dispatcher stops trusting
    the two screens to agree. H adds what the DETAIL needs on top; it does not
    restate what the row already says.
    """
    order = metering_seam.work_order_with_joins(order_id)
    if order is None:
        raise errors.NotFoundError()
    target = workforce.default_target()
    completed = order.state == "completed"
    return {
        **_dispatch_row(order, target["hours"] if target else None),
        # ── CR-168-BRC10 §7.3 · the redrawn order page (images 03–09) ────────
        # Ruling 15/17: two shapes. `completed` once the field has closed it —
        # the page then shows what was DONE; `open` shows the plan.
        "shape": "completed" if completed else "open",
        # P1.15 (`DEF-WRK-9529`): the job's account, else the account in force
        # on its unit — walked like the address, never typed onto the job.
        "customer": _customer_of(order),
        "location": _location_of(order),
        # P1.23: only on a completed job — before the close there is nothing
        # the customer signed for.
        "signature": _signature_of(order.id) if completed else None,
        # Image 04's *Closed by* (appended to §7.3 by lane ORDER-PAGE): who said
        # it was done in the field, and when — read from the close's own audit
        # row, the only record that names the closer.
        "closed": _closed_of(order) if completed else None,
        # PO 2026-10-04, (a) — REQUIRED photos still uploading; Accept waits.
        "photos_uploading": _photos_uploading(order.id),
        "timeline": _timeline_of(order),
        # The two axes the row does not carry, because the LIST draws only the
        # dispatch one (Work-007's STATUS column) and the detail draws both.
        "state": order.state,
        "outcome": order.outcome,
        "est_duration_minutes": (
            int(order.est_duration.total_seconds() // 60)
            if order.est_duration is not None
            else None
        ),
        # CR-161-BRC10 W4 — the utility's own answers, shown read-only on
        # Work-008 (`WORK_DETAIL`). On the DETAIL only, not the list row: no
        # dispatcher column reads them and a page of rows need not carry them.
        "custom_data": dict(order.custom_data or {}),
        # `DEF-WRK-9624` — the failed-outcome chain, both ways (`BR-WRK-054`):
        # the job this one exists BECAUSE OF, and the follow-ups raised when
        # this one failed. Numbers only (B14 rule 31); the page links them.
        "follows": (
            {"order_no": order.follows_order.order_no} if order.follows_order_id else None
        ),
        "follow_ups": [
            {"order_no": number}
            for number in order.follow_ups.order_by("order_no").values_list("order_no", flat=True)
        ],
    }


def _customer_of(order: Any) -> dict[str, Any] | None:
    from apps.work import mobile

    contact = mobile._customer_contact(order)
    if contact is None:
        return None
    return {
        "name": contact["name"],
        "phone": contact["phone"],
        "account_no": contact["account_no"],
        # `DEF-WRK-9678` — images 03/04 draw *Ana Alvarez · C-00001*.
        "customer_no": contact.get("customer_no"),
    }


def _location_of(order: Any) -> dict[str, Any]:
    """Where the job is: the premises, the unit, the asset and the ONE address
    (hard rule 8 — walked to the premises, declared nowhere on the job)."""
    premises = _premises_row_of(order)
    unit = order.unit if order.unit_id else None
    asset = order.asset if order.asset_id else None
    return {
        "premises": (
            {"id": str(premises.id), "premise_no": premises.premise_no}
            if premises is not None
            else None
        ),
        "unit": {"id": str(unit.id), "label": unit.label} if unit is not None else None,
        "asset": (
            {"id": str(asset.id), "asset_no": asset.asset_no, "serial": asset.serial_no}
            if asset is not None
            else None
        ),
        "address": premises.address_line if premises is not None else None,
    }


def _photos_uploading(order_id: Any) -> int:
    from apps.work import photo_links

    return photo_links.pending_required(order_id)


def _closed_of(order: Any) -> dict[str, Any]:
    from apps.work.seams import audit_seam, identity_seam

    row = (
        audit_seam.order_trail_queryset(order.id, ("work_order.field_result",))
        .order_by("-created_at")
        .values("actor_user_id", "created_at")
        .first()
    )
    by = None
    if row is not None and row["actor_user_id"]:
        name = identity_seam.user_names([row["actor_user_id"]]).get(str(row["actor_user_id"]))
        by = {"name": name} if name else None
    at = order.completed_at or (row["created_at"] if row else None)
    # `BR-WRK-061` — where the close was made, with the fix's accuracy, and
    # whether it reached the tenant's precision. `precise: false` is what the
    # office sees as *Location not precise* where it accepts (PO 2026-10-04).
    # None for a close made before the technician API carried a location.
    data = order.field_data if isinstance(order.field_data, dict) else {}
    location = data.get("close_location") if isinstance(data.get("close_location"), dict) else None
    # `DEF-WRK-4127` — the technician's *Arrived* and *Finished*, which price the
    # labour, shown where the office accepts or sends the job back. None for a
    # close that carried no times (an older phone, or the arrival row priced it).
    labour_time = data.get("labour_time") if isinstance(data.get("labour_time"), dict) else None
    # FB-014 (PO 2026-10-28) — how far the phone's clock was off when it sent
    # the close; every time above was shifted by it. The office shows *"Phone
    # clock was N min fast"* past 5 minutes. None for a close with no reading.
    clock = data.get("device_clock") if isinstance(data.get("device_clock"), dict) else None
    return {
        "by": by,
        "at": at.isoformat() if at else None,
        "location": location,
        "labour_time": labour_time,
        "device_clock": (
            {"offset_s": clock.get("offset_s"), "device_time": clock.get("device_time")}
            if clock is not None
            else None
        ),
    }


def _signature_of(order_id: Any) -> dict[str, Any] | None:
    from apps.work import evidence

    return evidence.signature_for_order(order_id)


def _timeline_of(order: Any) -> list[dict[str, Any]]:
    """`Raised → Assigned → En route → On site → Completed → Accepted` (P4.2),
    each a moment the job actually reached — a step not reached is absent, never
    a dash with a date. At most six rows, read from columns and the latest
    depart/arrive acts, so it needs no paging (the full story is the Audit tab).
    """
    def person(user: Any) -> dict[str, Any] | None:
        return {"name": user.full_name or user.email} if user is not None else None

    steps: list[dict[str, Any]] = []
    if order.created_at:
        steps.append({"kind": "raised", "at": order.created_at.isoformat(), "by": None,
                      "detail": order.source})
    if order.assigned_at:
        holder = _holder(order)
        steps.append({"kind": "assigned", "at": order.assigned_at.isoformat(),
                      "by": person(order.assigned_by) if order.assigned_by_id else None,
                      "detail": holder["name"] if holder else None})
    for act, kind in (("depart", "en_route"), ("arrive", "on_site")):
        row = (
            work_models.WorkOrderAssignment.objects.filter(
                tenant_id=_tenant_id(), work_order_id=order.id, act=act
            )
            .select_related("actor")
            .order_by("-at", "-id")
            .first()
        )
        if row is not None:
            steps.append({"kind": kind, "at": row.at.isoformat(),
                          "by": person(row.actor) if row.actor_id else None, "detail": None})
    if order.completed_at and order.state == "completed":
        steps.append({"kind": "completed", "at": order.completed_at.isoformat(), "by": None,
                      "detail": order.outcome})
    if order.accepted_at:
        steps.append({"kind": "accepted", "at": order.accepted_at.isoformat(),
                      "by": person(order.accepted_by) if order.accepted_by_id else None,
                      "detail": None})
    return sorted(steps, key=lambda step: step["at"])


def order_row_by_number(order_no: str) -> dict[str, Any]:
    """`GET /work-orders/by-number/{order_no}` — the SAME row, found by the
    reference a person can actually read.

    ⚠ **ONE ASSEMBLER, TWO DOORS (`DEF-WRK-4518`).** This resolves the number to
    an id and then calls `order_row` — it does not build a row of its own. A
    second assembler would be a second place for a field to be added, and the
    two doors would answer differently within a week (hard-won law 5).

    ⚠ **AN UNKNOWN NUMBER IS A PLAIN 404, IDENTICAL TO AN UNKNOWN ID.** The
    lookup is already filtered by the tenant in context, so *no such order* and
    *another utility's order* collapse into one answer here exactly as they do
    for a uuid. A by-number door that distinguished them would be a way to ask
    whether a neighbouring utility holds `WO-0016`.
    """
    order_id = metering_seam.work_order_id_by_number(order_no)
    if order_id is None:
        raise errors.NotFoundError()
    return order_row(order_id)


#: `CR-168-BRC10` P4.11 — the `audit_log` actions that belong on an order's
#: own history, and the act word each is shown as. **Names and words, never
#: ids** (B14 rule 31). The assignment acts are NOT here: they come from
#: `work_order_assignments`, the record, and their `audit_log` twins
#: (`work.order.assign` …) would show every assignment twice.
AUDIT_ACTS: dict[str, str] = {
    "work.order.held": "hold",
    "work.order.resumed": "resume",
    "work.order.cancelled": "cancel",
    "work.order.state_changed": "status",
    "work.order.priority_changed": "priority",
    "work_order.field_result": "completed",
    "work_order.accepted": "accepted",
    # Written by later rounds (send back P4.14 · the phone's acceptance P4.7);
    # mapped now so the day they write, the history shows them.
    "work.order.sent_back": "sent_back",
    "work.order.technician_accepted": "accepted_by_technician",
    "work.order.technician_declined": "declined_by_technician",
}

#: The edit page's Status list writes `work.order.state_changed`; on the
#: history that is a hold, a cancel or a plain status move, by its new value.
_STATE_CHANGED_AS = {"on_hold": "hold", "cancelled": "cancel"}


def order_audit(order_id: Any, *, page: Any = 1, per: Any = DEFAULT_PAGE_SIZE) -> dict[str, Any]:
    """`GET /work-orders/{id}/audit` — the order's WHOLE history, oldest first,
    paged (`CR-168-BRC10` P4.11, `DEF-WRK-9532`).

    ⚠ **TWO SOURCES, ONE LIST, PAGED IN SQL.** The assignment acts live in
    `work_order_assignments` (the append-only record, `BR-WRK-025`); hold,
    resume, cancel, priority, the field's close and the office's acceptance
    live in `audit_log`, written by the service that did each (hard rule 7).
    Until this, the tab read the first table only, so a hold never appeared on
    the one screen a supervisor opens to ask what happened. The two are a SQL
    `UNION` of `(source, id, moment)`, ordered and sliced in the database, and
    only the page's rows are then read whole — NFR-3, never a Python merge.

    ⚠ **A REASSIGN IS ONE LINE** (judgment J2). It is written as an `unassign`
    and an `assign` sharing an `act_group`; the `unassign` half is left out of
    the union and the `assign` half reads `reassign`, with the reason both
    carry. **THIS IS STILL WHAT PROVES `BR-WRK-027`**: a bulk assign of three
    orders leaves three rows, one on each order's history.
    """
    from django.db.models import F, Value
    from django.db.models import CharField

    from apps.work.seams import audit_seam, identity_seam

    order = _order_or_404(order_id)
    tenant_id = _tenant_id()
    assignments = (
        work_models.WorkOrderAssignment.objects.filter(tenant_id=tenant_id, work_order_id=order.id)
        .exclude(act="unassign", act_group__isnull=False)
        .annotate(src=Value("a", output_field=CharField()), moment=F("at"))
        .values("src", "id", "moment")
    )
    trail = (
        audit_seam.order_trail_queryset(order.id, tuple(AUDIT_ACTS))
        .annotate(src=Value("l", output_field=CharField()), moment=F("created_at"))
        .values("src", "id", "moment")
    )
    union = assignments.union(trail, all=True)
    total = union.count()
    size = clamp_page_size(per)
    last = max(1, math.ceil(total / size))
    number = max(1, min(int(page or 1), last))
    start = (number - 1) * size
    keys = list(union.order_by("moment", "id")[start : start + size])

    a_ids = [k["id"] for k in keys if k["src"] == "a"]
    l_ids = [k["id"] for k in keys if k["src"] == "l"]
    a_rows = {
        row.id: row
        for row in work_models.WorkOrderAssignment.objects.filter(
            tenant_id=tenant_id, id__in=a_ids
        ).select_related("technician__user", "crew", "actor")
    }
    l_rows = {row.id: row for row in audit_seam.trail_rows(l_ids)}
    names = identity_seam.user_names([row.actor_user_id for row in l_rows.values()])
    priority_names = {
        (code or "").upper(): name
        for code, name in work_models.WorkPriority.objects.filter(tenant_id=tenant_id).values_list(
            "code", "name"
        )
    }

    # P4.6 — which of the page's assignment lines were made against the advice:
    # the override's own audit row names its assignment (never a line of its
    # own on the history; it MARKS one).
    overridden = {
        str((row.after or {}).get("assignment_id"))
        for row in audit_seam.order_trail_queryset(order.id, (AGAINST_ADVICE,))
        if isinstance(row.after, dict)
    } if a_ids else set()
    rows: list[dict[str, Any]] = []
    for key in keys:
        if key["src"] == "a" and key["id"] in a_rows:
            rows.append(_assignment_audit_row(a_rows[key["id"]], overridden))
        elif key["src"] == "l" and key["id"] in l_rows:
            rows.append(_trail_audit_row(l_rows[key["id"]], names, priority_names))
    return {"order_no": order.order_no, "rows": rows, "page": number, "per": size, "total": total}


def _assignment_audit_row(row: Any, overridden: set[str] | frozenset[str] = frozenset()) -> dict[str, Any]:
    who = (
        {"kind": "person", "name": row.technician.user.full_name or row.technician.user.email}
        if row.technician_id
        else ({"kind": row.crew.kind, "name": row.crew.name} if row.crew_id else None)
    )
    act = "reassign" if (row.act == "assign" and row.act_group is not None) else row.act
    return {
        "act": act,
        "at": row.at.isoformat() if row.at else None,
        "who": who,
        "by": {"name": (row.actor.full_name or row.actor.email)} if row.actor_id else None,
        "reason": row.reason,
        "before_display": None,
        "after_display": who["name"] if who else None,
        "scheduled_for": row.scheduled_for.isoformat() if row.scheduled_for else None,
        "window_start": row.window_start.isoformat() if row.window_start else None,
        "window_end": row.window_end.isoformat() if row.window_end else None,
        # P4.6 — marked from `work.order.assigned_against_advice`.
        "against_advice": str(row.id) in overridden,
    }


def _trail_audit_row(
    row: Any, names: dict[str, str], priority_names: dict[str, str]
) -> dict[str, Any]:
    before = row.before if isinstance(row.before, dict) else {}
    after = row.after if isinstance(row.after, dict) else {}
    act = AUDIT_ACTS.get(row.action, row.action)
    if row.action == "work.order.state_changed":
        act = _STATE_CHANGED_AS.get(str(after.get("dispatch_state")), "status")
    before_display = after_display = None
    if act in ("hold",):
        after_display = after.get("reason")
    elif act in ("status", "cancel", "resume"):
        before_display = before.get("dispatch_state")
        after_display = after.get("dispatch_state")
    elif act == "priority":
        # Stored as the CODE (`URGENT`); shown as the tenant's own name.
        before_display = priority_names.get(str(before.get("priority") or "").upper())
        after_display = priority_names.get(str(after.get("priority") or "").upper())
    elif act == "completed":
        after_display = after.get("outcome")
    by_name = names.get(str(row.actor_user_id)) if row.actor_user_id else None
    if by_name is None and getattr(row, "actor_label", None):
        by_name = row.actor_label
    return {
        "act": act,
        "at": row.created_at.isoformat() if row.created_at else None,
        "who": None,
        "by": {"name": by_name} if by_name else None,
        "reason": after.get("note") if act == "hold" else after.get("reason"),
        "before_display": before_display,
        "after_display": after_display,
        "scheduled_for": None,
        "window_start": None,
        "window_end": None,
        "against_advice": False,
    }


def assign_candidates(
    order_id: Any, *, q: str | None = None, page: Any = 1, per: Any = DEFAULT_PAGE_SIZE
) -> dict[str, Any]:
    """Who could take THIS job, and what the dispatcher should know about each —
    **every technician, crew and contractor, paged and uncapped**
    (`CR-168-BRC10` P4.5, P4.12; `DEF-WRK-9531`, `DEF-WRK-9533`).

    ⚠ **`BR-WRK-029` IS SUPERSEDED — RULING 2 (2026-09-23), *"a guideline,
    never a block"*.** This used to return only the people holding the
    template's skill, and the write refused anybody else. Now every holder is a
    row with ADVICE beside it (`apps/work/advice.py`), and nothing is refused.
    `BR-WRK-030` went the same way on 2026-10-04 (PO answer 2, *"(a) Warn only,
    the same as skills"*): there is no policy to answer.

    ⚠ **NO MAXIMUM (NFR-5).** The no-skill path read ONE page of 200 from
    `workforce.crews_page` and called it everybody; the 201st holder was never
    offered. Paged in SQL now, and `count` is the whole workforce.

    `skill` and `on` ride beside the page. The one-round `policy` and
    `candidates` twins were retired by lane SRV-3 (2026-10-04) after lane ASSIGN
    moved to `results` and `advice` (2.501.1).
    """
    from apps.work import advice

    order = _order_or_404(order_id)
    skill_id = order.template.skill_id if order.template_id else None
    on = advice.order_day(order)
    result = advice.candidates_page(
        skill_id=skill_id,
        area_id=advice.order_area_id(order),
        on=on,
        q=q,
        page=page,
        per=per,
    )
    # SRV-2's one-round `policy` and `candidates` twins are RETIRED (lane SRV-3,
    # 2026-10-04): lane ASSIGN reads only the paged `results` from 2.501.1.
    return result


# ══════════════════════════════════════════════════════════════════════════
# WRITES
# ══════════════════════════════════════════════════════════════════════════


def _actor_id(actor: Any) -> Any:
    return getattr(actor, "id", None)


def _order_or_404(order_id: Any) -> Any:
    """One order of the tenant in context, or a 404.

    ⚠ **CROSS-TENANT IS INDISTINGUISHABLE FROM ABSENT** (hard rule 1, HR-1). A
    403 on another utility's order number would confirm that the number exists,
    which is exactly the leak the rule forbids.
    """
    order = metering_seam.work_order_row(order_id)
    if order is None:
        raise errors.NotFoundError()
    return order


def _candidate_or_refuse(order: Any, payload: dict[str, Any]) -> tuple[Any, Any]:
    """The technician or crew named in the payload — `(technician, crew)`, at
    most one set. Refuses only a holder that does not exist (404) or a payload
    naming nobody; **never a skill or a certification** (ruling 2, PO answer 2).
    The name is kept because `edit.save_order_edit` calls it.
    """
    tenant_id = _tenant_id()
    technician = crew = None
    if payload.get("technician_id"):
        technician = work_models.Technician.objects.filter(
            tenant_id=tenant_id, pk=payload["technician_id"]
        ).first()
        if technician is None:
            raise errors.NotFoundError()
    elif payload.get("crew_id"):
        crew = work_models.Crew.objects.filter(
            tenant_id=tenant_id, pk=payload["crew_id"]
        ).first()
        if crew is None:
            raise errors.NotFoundError()
    else:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="work.dispatch.holder_required",
            br_ref="BR-WRK-025",
        )
    # ⚠ NO SKILL OR CERTIFICATION REFUSAL HERE ANY MORE (`CR-168-BRC10` P4.5,
    # `DEF-WRK-9533`). Ruling 2 (2026-09-23) SUPERSEDES `BR-WRK-029` — *"a
    # guideline, never a block"* — and PO answer 2 (2026-10-04) SUPERSEDES
    # `BR-WRK-030`'s block. The advice is read by `_audit_against_advice` after
    # the row is written, and an assignment against it is RECORDED, not refused.
    return technician, crew


def record_act(
    actor: Any,
    order_id: Any,
    payload: dict[str, Any],
    *,
    push: bool = True,
    pending: list[Any] | None = None,
    key: str | None = None,
) -> dict[str, Any]:
    """`POST /work-orders/{id}/assignments` — **one act, one appended row.**

    `BR-WRK-025`: assign · unassign · schedule · depart · arrive. The row is
    written FIRST and the order's cache columns SECOND, in one transaction, so
    the cache is never ahead of the record it caches.

    ⚠ **`dispatch_state` MOVES AND `state` DOES NOT** (`BR-WRK-023`,
    `US-WRK-024` TC-1). Assigning a job takes it from *queued* to *scheduled*;
    the job is still *planned*, because nobody has done any work yet. That
    separation is the whole reason the third axis exists, and a lane that
    "tidies" this by moving `state` too will make a dispatcher's morning
    unrepresentable.
    """
    if pending is None:
        pending = []
    order = _order_or_404(order_id)
    act = str(payload.get("act") or "").strip()
    if act not in (*work_models.WorkOrderAssignment.ACTS, REASSIGN):
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="work.dispatch.act_unknown",
            br_ref="BR-WRK-025",
            params={"act": act or "—"},
        )

    # CR-187-BRC10 (PO answer 9) — a dispatcher may still CHOOSE how this
    # assignment rings; absent, the job's priority decides (`push_kind_for`).
    chosen_kind = _chosen_push_kind(payload)

    technician = crew = None
    if act in ("assign", "schedule", REASSIGN):
        if act != "schedule" or payload.get("technician_id") or payload.get("crew_id"):
            technician, crew = _candidate_or_refuse(order, payload)

    # ── P4.4 · A REASSIGN IS ONE REQUEST, AND IT SAYS WHY (judgment J2) ─────
    # Two rows, `unassign` + `assign`, sharing a `reason` and an `act_group`, so
    # the Audit reads ONE act with one reason while the CHECK keeps its five
    # tokens and the append-only trigger (`work/0009`) is untouched. A plain
    # `assign` that takes the job OFF somebody is a reassign too, and must say
    # why — otherwise the reason is optional only for the dispatcher who
    # forgot it.
    reason = str(payload.get("reason") or "").strip() or None
    takes_off = bool(order.assignee_technician_id or order.assignee_crew_id) and act in (
        "assign",
        REASSIGN,
    )
    if takes_off and _holder_differs(order, technician, crew) and reason is None:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="work.dispatch.reason_required",
            br_ref="BR-WRK-025",
        )
    if act == REASSIGN and not takes_off:
        # Nobody holds it, so nothing moves AWAY from anybody: an assign.
        act = "assign"

    scheduled_for = metering_seam.parse_moment(payload.get("scheduled_for"), field="scheduled_for")
    window_start = metering_seam.parse_moment(payload.get("window_start"), field="window_start")
    window_end = metering_seam.parse_moment(payload.get("window_end"), field="window_end")
    if window_start is not None and window_end is not None and window_end <= window_start:
        raise errors.ValidationError(
            errors.VAL_RANGE, message_key="work.dispatch.window_backwards"
        )

    before = {
        "dispatch_state": order.dispatch_state,
        "technician": (_holder(order) or {}).get("name"),
    }
    # `CR-168-BRC10` P6.1 (lane SRV-5) — what the customer was promised BEFORE
    # this act, so the act can tell them it is booked or that it moved.
    from apps.work import visit_notices

    window_before = visit_notices.window_key(order)
    written_act = "assign" if act == REASSIGN else act
    advice_row: dict[str, Any] | None = None
    with transaction.atomic():
        group = None
        if takes_off and _holder_differs(order, technician, crew):
            group = uuid.uuid4()
            append_act(actor, order, "unassign", reason=reason, act_group=group)
            written_act = "assign"
            act = REASSIGN
        row = append_act(
            actor,
            order,
            written_act,
            technician=technician,
            crew=crew,
            scheduled_for=scheduled_for,
            window_start=window_start,
            window_end=window_end,
            reason=reason if group is not None else None,
            act_group=group,
            # `CR-187-BRC10` — only the field's own door passes one
            # (`mobile.field_act`), as an ARGUMENT: a `key` in an office
            # request's body is never read, so the office door is unchanged.
            key=key,
        )
        # Hard rule 7 — every act writes audit_log, naming who and what moved.
        core_audit.write_row(
            action=f"work.order.{act}",
            entity_type="work_order",
            entity_id=order.id,
            actor_user_id=_actor_id(actor),
            before=before,
            after={
                "dispatch_state": order.dispatch_state,
                "technician": (_holder(order) or {}).get("name"),
                "order_no": order.order_no,
                **({"reason": reason} if group is not None else {}),
            },
        )
        if written_act == "assign":
            advice_row = _audit_against_advice(actor, order, row, technician, crew)
    # ── THE PUSH (`BR-WRK-034`, `US-WRK-030`) ────────────────────────────────
    #
    # ⚠ **OUTSIDE THE `atomic()` BLOCK ABOVE, DELIBERATELY.** `core.jobs.enqueue`
    # writes the job row and then hands it to the dispatcher; inside the
    # transaction the broker could be handed a job id the database has not
    # committed yet, and an eager worker would look it up and find nothing.
    #
    # ⚠ **AND IT IS A CONSEQUENCE, NEVER A SECOND ACT** (`BR-WRK-025`). See
    # `apps/work/push.py`.
    push_job = (
        push_after_assign(row, order, written_act, technician, actor, kind=chosen_kind)
        if push
        else None
    )
    # ── THE CUSTOMER (P6.1): booked, moved, on the way — after the act, and
    # never able to fail it (`visit_notices` never raises). ────────────────
    customer_notice = visit_notices.after_act(
        order, written_act, window_before=window_before, row=row, actor=actor
    )
    if not push:
        # The caller holds an open transaction (`raise_svc` — a job assigned at
        # its raise): it pushes after ITS commit, from what is handed back here.
        pending.append((row, order, written_act, technician))
    return {
        # NAMED `assignment_id`, not `id`. `bulk_act` spreads this answer into a
        # per-order result and a bare `id` here silently became the order's.
        "assignment_id": str(row.id),
        "order_no": order.order_no,
        "act": act,
        "dispatch_state": order.dispatch_state,
        "technician": _holder(order),
        "reason": reason if act == REASSIGN else None,
        # P4.5 — the advice the dispatcher acted against, or None. Never a
        # refusal; the Audit tab marks the row `against_advice`.
        "against_advice": advice_row,
        "push_job_id": push_job,
        # P6.1 — what the customer was told by this act (`visit_message_*`), or
        # None when the act tells them nothing (an unassign, an arrive).
        "customer_notice": (customer_notice or {}).get("code"),
    }


#: `CR-168-BRC10` P4.4 — the request word for *take it off one holder and give
#: it to another*. NOT a sixth `act` token: it writes `unassign` + `assign`.
REASSIGN = "reassign"


def _holder_differs(order: Any, technician: Any, crew: Any) -> bool:
    return str(order.assignee_technician_id or "") != str(
        technician.id if technician is not None else ""
    ) or str(order.assignee_crew_id or "") != str(crew.id if crew is not None else "")


def _audit_against_advice(
    actor: Any, order: Any, row: Any, technician: Any, crew: Any
) -> dict[str, Any] | None:
    """🔒 HUMAN-REVIEW-PENDING (`CR-168-BRC10` P4.6) — an assignment the advice
    argued against is RECORDED, never refused.

    Ruling 2 (2026-09-23) and PO answer 2 (2026-10-04) turned two refusals into
    advice. What is left of them is accountability: *who gave a backflow test
    to somebody whose certificate lapsed on 30 September, and when*. So one
    `audit_log` row, `work.order.assigned_against_advice`, names the missing
    skill and every lapsed certification by NAME (a person reads this row in
    six weeks), and carries the assignment row's id so the order's Audit tab
    can mark that one line `against_advice`.

    Worked: WO-0042 needs *Meter I*; R. Patel holds Water I only and his
    *Backflow tester* certificate expired 2026-09-30; a dispatcher assigns him
    for 2026-10-03 → the assignment stands, and this row reads
    `{missing_skill: "Meter I", lapsed: [{name: "Backflow tester",
    expired_on: "2026-09-30"}]}`.

    Returns the recorded advice, or None when there was nothing to override.
    Written INSIDE the caller's transaction, so the override and the assignment
    commit or vanish together.
    """
    if technician is None and crew is None:
        return None
    from apps.work import advice

    skill_id = order.template.skill_id if order.template_id else None
    seen = advice.advice_for(
        technician=technician, crew=crew, skill_id=skill_id, on=advice.order_day(order)
    )
    missing = seen["skill"]["name"] if (seen["skill"] and not seen["has_skill"]) else None
    lapsed = seen["certifications_lapsed"]
    if missing is None and not lapsed:
        return None
    recorded = {"missing_skill": missing, "lapsed": lapsed}
    core_audit.write_row(
        action=AGAINST_ADVICE,
        entity_type="work_order",
        entity_id=order.id,
        actor_user_id=_actor_id(actor),
        before=None,
        after={
            **recorded,
            "order_no": order.order_no,
            "assignment_id": str(row.id),
            "holder": (_holder(order) or {}).get("name"),
        },
    )
    return recorded


#: The audit action an override writes (P4.6). Read by `order_audit` to mark the
#: assignment line; never a line of its own.
AGAINST_ADVICE = "work.order.assigned_against_advice"


def append_act(
    actor: Any,
    order: Any,
    act: str,
    *,
    technician: Any = None,
    crew: Any = None,
    scheduled_for: Any = None,
    window_start: Any = None,
    window_end: Any = None,
    reason: str | None = None,
    act_group: Any = None,
    key: str | None = None,
) -> Any:
    """**The history row and the cache refresh — ONE writer, two callers.**

    ⚠ **EXTRACTED FROM `record_act` BY CR-070 wave I, AND THE EXTRACTION IS THE
    POINT.** Wave I's edit screen (`Work-021`) saves several fields at once and
    must write **one audit row per FIELD a dispatcher changed**, not one per act
    — reassigning a job is `unassign` + `assign`, two history rows, but it is
    ONE thing the dispatcher did, and `US-WRK-031` TC-1 counts **two** audit
    rows for a Save that moved the technician and the window.

    So `edit.py` needs the append and the cache refresh WITHOUT `record_act`'s
    own audit row. The wrong way to get that is a second function that creates a
    `WorkOrderAssignment` — a parallel world, exactly what the PO ruled against
    on 2026-09-05 (*"work is not isolated module … buld the code while
    leveraging existing framwrok, code, tabels"*). So the shared half is lifted
    here and both callers use it: `record_act` = `append_act` + one audit row
    per act; `edit.save_order_edit` = `append_act` + one audit row per field.

    **The invariant `record_act`'s docstring states survives because it lives in
    this function:** the row is appended FIRST and the order's cache columns
    refreshed SECOND, inside the caller's transaction. A cache can be rebuilt
    from a history; a history cannot be rebuilt from a cache.

    ⚠ **IT WRITES NO `audit_log` ROW ON PURPOSE, WHICH IS A HAZARD WORTH
    NAMING.** Every act here writes one — but the row is written by the CALLER.
    A third caller that forgets is an unaudited act with nothing raising, so: if
    you call this, write the audit row. `tests/test_us_wrk_031_edit.py` asserts
    the count for both existing callers.

    ⚠ **AND SINCE WAVE J THERE IS A SECOND OBLIGATION: THE PUSH
    (`DEF-WRK-4041`).** An `assign` or `schedule` row that gave somebody work
    must be followed by `push_after_assign(...)`, **after the transaction
    commits**. It is not done here because this function runs INSIDE the
    caller's transaction and `core.jobs.enqueue` must not hand a broker a job id
    the database has not committed yet. It was missed exactly once and cost
    nothing visible: the edit screen reassigned without pushing under a Change
    effects box promising *"Technician phone — job updates immediately"*, and
    the technician got the job on the next sync, so nothing looked wrong.
    **So: if you call this with an `assign` or `schedule`, call
    `push_after_assign` too** — and `tests/test_us_wrk_030_push.py` asserts it
    for each door by name.
    """
    row = work_models.WorkOrderAssignment.objects.create(
        tenant_id=_tenant_id(),
        work_order=order,
        act=act,
        technician=technician,
        crew=crew,
        scheduled_for=scheduled_for,
        window_start=window_start,
        window_end=window_end,
        actor_id=_actor_id(actor),
        # `CR-168-BRC10` P4.4 (J2) — a reassign's two rows share both.
        reason=reason,
        act_group=act_group,
        # `CR-187-BRC10` (`work/0047`) — the handset's outbox key, when an act
        # came from one (`mobile.field_act`, `field_dispatch.hand_back`).
        key=key,
    )
    _refresh_cache(order, act, technician, crew, scheduled_for, window_start, window_end, actor)
    return row

#: Which acts put a job on a phone. `assign` and `schedule` — the two that leave
#: a technician holding work they did not have a moment ago. `unassign` is
#: deliberately absent and `US-WRK-030` TC-4 is why: D. Ortiz's phone **drops**
#: the job on its next sync because the day list stops containing it, which
#: needs no push at all; R. Patel's phone gains it, which does. `depart` and
#: `arrive` are the technician's own taps — pushing a job to the phone that
#: just reported leaving for it would be the product talking to itself.
PUSHING_ACTS: tuple[str, ...] = ("assign", "schedule")


def _chosen_push_kind(payload: dict[str, Any]) -> str | None:
    """A dispatcher's explicit `push_kind` on an assignment, or None.

    One of `work_models.PRIORITY_PUSH_KINDS`; anything else is refused BEFORE
    the act is written, so a typo never leaves an assignment that rang with a
    kind nobody chose.
    """
    raw = str(payload.get("push_kind") or "").strip().lower()
    if not raw:
        return None
    if raw not in work_models.PRIORITY_PUSH_KINDS:
        allowed = ", ".join(work_models.PRIORITY_PUSH_KINDS)
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="work.priorities.push_kind_unknown",
            br_ref="BR-WRK-034",
            params={"allowed": allowed},
            field_errors=[
                {
                    "field": "push_kind",
                    "code": errors.VAL_UNKNOWN_LOOKUP,
                    "message_key": "work.priorities.push_kind_unknown",
                    "params": {"allowed": allowed},
                }
            ],
        )
    return raw


def push_by_priority_on() -> bool:
    """The tenant's *push by priority* switch — OFF unless a row says ON."""
    row = work_models.WorkSettings.objects.filter(tenant_id=_tenant_id()).first()
    return bool(getattr(row, "push_by_priority", False)) if row is not None else False


def push_kind_for(order: Any, chosen: str | None = None) -> str:
    """How an assignment of `order` rings — PO answer 9 (2026-10-21).

    The dispatcher's explicit choice wins; otherwise, ONLY WHEN THE TENANT HAS
    TURNED *push by priority* ON (`work_settings.push_by_priority` — PO answer
    9 as corrected the same day: *an option*, seeded OFF), the order's
    PRIORITY says (`work_priorities.push_kind` — seeded most urgent
    `emergency`, next `urgent_assignment`, rest `new_job`). Switched off, or a
    job with no priority, rings as an ordinary `new_job`. Read LIVE at the
    assignment, not stamped at the raise: the setting is about how the phone
    rings NOW.
    """
    if chosen:
        return chosen
    if not push_by_priority_on():
        return "new_job"
    priority = order.priority if getattr(order, "priority_id", None) else None
    kind = getattr(priority, "push_kind", None)
    return kind if kind in work_models.PRIORITY_PUSH_KINDS else "new_job"


def push_after_assign(
    row: Any,
    order: Any,
    act: str,
    technician: Any,
    actor: Any,
    *,
    kind: str | None = None,
) -> str | None:
    """Enqueue `work.push` for an assignment that gave somebody work.

    Returns the job id, or None when this act pushes nothing.

    ⚠ **THE KIND (CR-187-BRC10, PO answer 9).** `push_kind_for` picks it — a
    dispatcher's explicit `kind`, else the order's priority setting. An
    `urgent_assignment` or `emergency` FIRST writes the same alert row a
    dispatcher's send writes (`field_alerts.record_assignment_alert`), so an
    automatic emergency starts R28's five-minute clock whether or not the
    broker is up, and the job then rings that alert's channel and stamps it.
    A `new_job` is this function's original doorbell, unchanged.

    ⚠ **PUBLIC, AND EVERY ASSIGNMENT DOOR MUST CALL IT — `DEF-WRK-4041`.**
    There are two doors: `record_act` (the dispatcher's row action) and
    `edit.save_order_edit` (`Work-021`, wave I). Both append through
    `append_act`; only the first called this, so a dispatcher reassigning a job
    on the EDIT screen got two assignment rows, two audit rows, a customer
    message and **no push** — under a Change effects box that says in its own
    words *"Technician phone — job updates immediately"*. Nothing looked wrong,
    because the technician still gets the job on the next ordinary sync.
    `test_us_wrk_030_push.py` now asserts the job row after a reassignment made
    through EACH door by name, so a third door that forgets goes red naming
    itself.

    ⚠ **CALL IT AFTER THE TRANSACTION COMMITS, NOT INSIDE IT.** See the note at
    the call site in `record_act`: `core.jobs.enqueue` writes the row and then
    hands it to the broker, and inside an open transaction an eager worker would
    look up a job id the database has not committed.

    ⚠ **A FAILURE HERE MUST NOT UNDO THE ASSIGNMENT** — `US-WRK-030` TC-3:
    *"the push provider is down → the job row stays queued and retries with
    jitter; the assignment stands; nothing is lost."* The assignment is
    committed by the time this runs, and the broadest reasonable catch is
    correct here for exactly that reason: a dispatcher must not see *could not
    assign* because a broker was restarting. The failure is LOGGED at warning
    with the order it belongs to, so it is findable, and the phone still
    receives the job on its next sync — the sync is the delivery and the push is
    the doorbell.
    """
    if act not in PUSHING_ACTS or technician is None:
        return None
    push_kind = push_kind_for(order, kind)
    alert_id = None
    if push_kind != "new_job":
        from apps.work import field_alerts

        try:
            alert_id = str(
                field_alerts.record_assignment_alert(
                    actor, order, technician, push_kind, assignment_id=row.id
                ).id
            )
        except Exception as exc:  # noqa: BLE001 — the assignment stands (TC-3)
            # The assignment is committed; an alert that could not be written
            # must not undo it. Rung as an ordinary job instead, and LOGGED, so
            # the phone is never told of an emergency nobody can acknowledge.
            logger.warning(
                "the %s alert for %s (assignment %s) could not be written: %r — "
                "pushed as a new job",
                push_kind,
                order.order_no,
                row.id,
                exc,
            )
            push_kind = "new_job"
    payload = {
        "work_order_id": str(order.id),
        "order_no": order.order_no,
        "assignment_id": str(row.id),
        "technician_id": str(technician.id),
        "push_kind": push_kind,
        "alert_id": alert_id,
        # For the audit line's `after` blob — a NAME, so a person reading the
        # Audit tab in six weeks does not have to resolve a uuid (B14 rule 31 is
        # about screens, and an audit blob a human reads is one).
        "technician_name": (_holder(order) or {}).get("name"),
        "actor_id": str(_actor_id(actor)) if _actor_id(actor) else None,
    }
    try:
        record = core_jobs.enqueue(
            push.PUSH_JOB, payload=payload, scope_key=push.scope_key(row.id)
        )
    except Exception as exc:  # noqa: BLE001 — see the docstring: the assignment stands
        logger.warning(
            "work.push could not be enqueued for %s (assignment %s): %r — the "
            "assignment stands and the phone gets the job on its next sync",
            order.order_no,
            row.id,
            exc,
        )
        return None
    return str(record["id"])


#: Which dispatch state each act leaves the order in. A table rather than a
#: chain of `if`s because `BR-WRK-023`'s axis has seven values and five acts, and
#: the mapping is a FACT that wave J's phone and wave M's rules both need to read
#: — a reader can check it against the rule in one glance.
def act_moves_to() -> dict[str, str]:
    """Which dispatch state each act leaves the order in.

    A function rather than a module constant only because the tokens come from
    metering through the seam (`G78`/`BR-WRK-002`) and a module-level call would
    import an app at import time. The MAPPING is the fact; a reader can check it
    against `BR-WRK-023` in one glance, which is why it is a table and not a
    chain of `if`s — wave J's phone and wave M's rules both read it.
    """
    s = metering_seam.dispatch_tokens()
    return {
        "assign": s.SCHEDULED,
        "unassign": s.QUEUED,
        "schedule": s.SCHEDULED,
        "depart": s.EN_ROUTE,
        "arrive": s.ON_SITE,
    }


def _refresh_cache(
    order: Any,
    act: str,
    technician: Any,
    crew: Any,
    scheduled_for: Any,
    window_start: Any,
    window_end: Any,
    actor: Any,
) -> None:
    """Bring `work_orders`' cache columns up to the row just appended.

    ⚠ **A HELD ORDER STAYS HELD.** *On hold* and *Cancelled* are states a person
    put the job into deliberately, and a `depart` arriving from a phone must not
    quietly take it off hold — that would be the product overruling the
    dispatcher. The act is still RECORDED (the row is already written when this
    runs); what it does not do is move the axis.
    """
    if act == "unassign":
        order.assignee_technician = None
        order.assignee_crew = None
        order.assigned_at = None
        order.assigned_by = None
    elif technician is not None or crew is not None:
        order.assignee_technician = technician
        order.assignee_crew = crew
        order.assigned_at = timezone.now()
        order.assigned_by_id = _actor_id(actor)
    if scheduled_for is not None:
        order.due_at = order.due_at or scheduled_for
    if window_start is not None:
        order.window_start = window_start
    if window_end is not None:
        order.window_end = window_end
    tokens = metering_seam.dispatch_tokens()
    if order.dispatch_state not in (tokens.ON_HOLD, tokens.CANCELLED):
        order.dispatch_state = act_moves_to()[act]
    metering_seam.save_order_fields(
        order,
        [
            "assignee_technician",
            "assignee_crew",
            "assigned_at",
            "assigned_by",
            "due_at",
            "window_start",
            "window_end",
            "dispatch_state",
        ],
    )


def set_dispatch_state(actor: Any, order_id: Any, state: str, action: str) -> dict[str, Any]:
    """`POST …/cancel` and the edit page's Status list — a move on the third
    axis without deleting anything.

    `07-endpoints.md` row 66: *"danger tier; **nothing deleted**"*. A cancelled
    order keeps its number, its history and its audit trail; what changes is one
    column. Hard rule 4's shape applied to a table it does not name.

    ⚠ **ENTERING OR LEAVING A HOLD KEEPS THE HOLD CLOCK HONEST** (`CR-168-BRC10`
    P0.3, P5.2/P5.8). Whatever door moves a job onto *On hold* stamps
    `held_at`; whatever door moves it off adds the held time to `held_seconds`
    and clears the reason. `hold()` below is the door WITH a reason; the edit
    page's Status list is the door without one, and it must not leave a clock
    running nobody can see.
    """
    order = _order_or_404(order_id)
    before = order.dispatch_state
    with transaction.atomic():
        fields = ["dispatch_state", *_hold_clock(order, before, state)]
        order.dispatch_state = state
        metering_seam.save_order_fields(order, fields)
        core_audit.write_row(
            action=action,
            entity_type="work_order",
            entity_id=order.id,
            actor_user_id=_actor_id(actor),
            before={"dispatch_state": before},
            after={"dispatch_state": state, "order_no": order.order_no},
        )
    return {"order_no": order.order_no, "dispatch_state": order.dispatch_state}


def _hold_clock(order: Any, before: str, after: str) -> list[str]:
    """Move the hold columns for a `before → after` change; the fields touched."""
    on_hold = metering_seam.dispatch_tokens().ON_HOLD
    now = timezone.now()
    if after == on_hold and before != on_hold:
        order.held_at = now
        return ["held_at"]
    if before == on_hold and after != on_hold:
        if order.held_at is not None:
            order.held_seconds = int(order.held_seconds or 0) + max(
                0, int((now - order.held_at).total_seconds())
            )
        order.held_at = None
        order.hold_reason = None
        order.hold_expected_return_on = None
        return ["held_at", "held_seconds", "hold_reason", "hold_expected_return_on"]
    return []


def hold(actor: Any, order_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`POST /work-orders/{id}/hold` — off the run, WITH A REASON (`CR-168-BRC10`
    P0.3/P4.3, drawn as image 10).

    `{reason_code, expected_return_on?, note?}`. The reason is one of the
    tenant's own `work_hold_reasons` (judgment J1), active, by code; a hold with
    no reason is refused (`work.hold.reason_required`), because *on hold* with
    no why is the question a customer rings to ask. `expected_return_on` is a
    calendar DATE in the utility's day. The audit row carries the reason's NAME
    and the note, which is what the order's history shows (P4.11).

    A job already on hold may be re-held to change its reason or return date;
    the hold clock keeps running from the FIRST hold, so a correction does not
    forgive the time already spent.
    """
    body = dict(payload or {})
    order = _order_or_404(order_id)
    code = str(body.get("reason_code") or "").strip()
    if not code:
        raise errors.ValidationError(
            errors.VAL_REQUIRED, message_key="work.hold.reason_required", br_ref="BR-WRK-023"
        )
    reason = work_models.WorkHoldReason.objects.filter(
        tenant_id=_tenant_id(), code__iexact=code, active=True
    ).first()
    if reason is None:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="work.hold.reason_unknown",
            br_ref="BR-WRK-023",
            params={"reason": code},
        )
    expected = _parse_day(body.get("expected_return_on"), field="expected_return_on")
    note = str(body.get("note") or "").strip() or None
    tokens = metering_seam.dispatch_tokens()
    before = order.dispatch_state
    with transaction.atomic():
        fields = ["dispatch_state", "hold_reason", "hold_expected_return_on"]
        fields += _hold_clock(order, before, tokens.ON_HOLD)
        order.dispatch_state = tokens.ON_HOLD
        order.hold_reason = reason
        order.hold_expected_return_on = expected
        metering_seam.save_order_fields(order, sorted(set(fields)))
        core_audit.write_row(
            action="work.order.held",
            entity_type="work_order",
            entity_id=order.id,
            actor_user_id=_actor_id(actor),
            before={"dispatch_state": before},
            after={
                "dispatch_state": tokens.ON_HOLD,
                "order_no": order.order_no,
                "reason_code": reason.code,
                "reason": reason.name,
                "expected_return_on": expected.isoformat() if expected else None,
                "note": note,
            },
        )
    # P6.2 (lane SRV-5) — the office is told the job is BLOCKED, once per hold
    # (a re-hold that only changes the reason keeps `held_at`, so it is the
    # same occasion and writes nothing).
    from apps.work import visit_notices

    visit_notices.tell_office(
        order, "blocked", discriminator=order.held_at.isoformat() if order.held_at else ""
    )
    return {
        "order_no": order.order_no,
        "dispatch_state": order.dispatch_state,
        "hold": _hold_of(order),
    }


def _parse_day(value: Any, *, field: str) -> Any:
    """A calendar DATE (`2026-10-09`), or None when blank; refused if unreadable."""
    from datetime import date

    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="work.hold.return_date_unreadable",
            br_ref="BR-WRK-023",
            params={field: str(value)},
        ) from None


def resume(actor: Any, order_id: Any) -> dict[str, Any]:
    """`POST /work-orders/{id}/resume` — back on the run (`CR-168-BRC10` P4.3).

    ⚠ **BACK TO WHERE THE HISTORY SAYS IT WAS**, not to a fixed token: the
    latest assignment act decides — assigned or scheduled → *Scheduled*, departed
    → *En route*, arrived → *On site*, nothing → *Queued* (`act_moves_to`, the
    same table every act reads). The held time is added to `held_seconds` (P5.2)
    and the reason cleared. A job that is not on hold is refused rather than
    silently "resumed" into a state it never left.
    """
    order = _order_or_404(order_id)
    tokens = metering_seam.dispatch_tokens()
    if order.dispatch_state != tokens.ON_HOLD:
        raise errors.ValidationError(
            errors.VAL_RANGE,
            message_key="work.hold.not_on_hold",
            br_ref="BR-WRK-023",
            params={"order_no": order.order_no or ""},
        )
    last = (
        work_models.WorkOrderAssignment.objects.filter(
            tenant_id=_tenant_id(), work_order_id=order.id
        )
        .order_by("-at", "-id")
        .values_list("act", flat=True)
        .first()
    )
    back_to = act_moves_to().get(last, tokens.QUEUED) if last else tokens.QUEUED
    with transaction.atomic():
        fields = ["dispatch_state", *_hold_clock(order, tokens.ON_HOLD, back_to)]
        order.dispatch_state = back_to
        metering_seam.save_order_fields(order, fields)
        core_audit.write_row(
            action="work.order.resumed",
            entity_type="work_order",
            entity_id=order.id,
            actor_user_id=_actor_id(actor),
            before={"dispatch_state": tokens.ON_HOLD},
            after={"dispatch_state": back_to, "order_no": order.order_no,
                   "held_seconds": order.held_seconds},
        )
    return {"order_no": order.order_no, "dispatch_state": order.dispatch_state, "hold": None}


def _hold_of(order: Any) -> dict[str, Any] | None:
    """`{reason {code, name}, expected_return_on, since}` while on hold, else None."""
    if order.dispatch_state != metering_seam.dispatch_tokens().ON_HOLD:
        return None
    reason = order.hold_reason if order.hold_reason_id else None
    return {
        "reason": {"code": reason.code, "name": reason.name} if reason is not None else None,
        "expected_return_on": (
            order.hold_expected_return_on.isoformat() if order.hold_expected_return_on else None
        ),
        "since": order.held_at.isoformat() if order.held_at else None,
    }


def hold_reasons() -> list[dict[str, Any]]:
    """`GET /work/hold-reasons` — the tenant's ACTIVE reasons, by rank (P0.4)."""
    return [
        # §7.3 `{code, name, active, rank}` — `active` is always true here (only
        # active reasons are offered) and is sent so a reader need not assume.
        {"code": row.code, "name": row.name, "active": True, "rank": row.rank}
        for row in work_models.WorkHoldReason.objects.filter(
            tenant_id=_tenant_id(), active=True
        ).order_by("rank", "name", "id")
    ]


def reschedule(actor: Any, order_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """Move the promise — a `schedule` row, which is an ordinary act of the
    history and not a special case."""
    body = dict(payload or {})
    body["act"] = "schedule"
    return record_act(actor, order_id, body)


def change_priority(actor: Any, order_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`Change priority…` — and **`due_at` MOVES WITH IT.**

    A priority in this product is not a colour, it is a PROMISE: `BR-WRK-018`
    makes `sla_hours` the whole content of it. Raising a job to Urgent and
    leaving it due next Tuesday would put the pill and the date in flat
    contradiction on one row of one table, and the pill is the one people act on.

    ⚠ **RE-DATED FROM THE ORIGINAL RAISE, NOT FROM NOW** — a job raised at 09:00
    and made Urgent at 15:00 is due at 13:00 and is therefore ALREADY overdue,
    which is the truth. Measuring the new SLA from the moment somebody noticed
    would quietly forgive six hours of lateness every time a priority was
    corrected, and the OVERDUE tile is the number that would silently improve.
    """
    order = _order_or_404(order_id)
    priority = work_models.WorkPriority.objects.filter(
        tenant_id=_tenant_id(), pk=payload.get("priority_id")
    ).first()
    if priority is None:
        raise errors.NotFoundError()
    if order.dispatch_state == metering_seam.dispatch_tokens().COMPLETE:
        # `07-endpoints.md` row 63 — *"refuses priority on Complete"*. A promise
        # about work that is finished is not a promise, it is a rewrite.
        raise errors.ValidationError(
            errors.VAL_RANGE,
            message_key="work.dispatch.priority_on_complete",
            br_ref="BR-WRK-018",
        )
    before = {
        "priority": order.priority.code if order.priority_id else None,
        "due_at": order.due_at.isoformat() if order.due_at else None,
    }
    with transaction.atomic():
        order.priority = priority
        # P5.10 (lane SRV-4): a job type with its OWN hours keeps its promise —
        # the priority moves the pill, the type's hours keep the date.
        type_hours = getattr(order.type_ref, "sla_hours", None) if order.type_ref_id else None
        if not type_hours and priority.sla_hours:
            order.due_at = order.created_at + timedelta(hours=int(priority.sla_hours))
        metering_seam.save_order_fields(order, ["priority", "due_at"])
        core_audit.write_row(
            action="work.order.priority_changed",
            entity_type="work_order",
            entity_id=order.id,
            actor_user_id=_actor_id(actor),
            before=before,
            after={
                "priority": priority.code,
                "due_at": order.due_at.isoformat() if order.due_at else None,
                "order_no": order.order_no,
            },
        )
    return {
        "order_no": order.order_no,
        "priority": _priority_of(order),
        "due_at": order.due_at.isoformat() if order.due_at else None,
    }


def bulk_act(actor: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`POST /work-orders/bulk` — `BR-WRK-027`, **one row PER ORDER.**

    Verbatim: *"Bulk actions on the selection are Assign, Reschedule and Change
    priority. Each writes one assignment or audit row PER ORDER — never one row
    for the batch."* So this is a LOOP over the single-order services above and
    not a queryset `.update()`, and the answer is **a result per id** — never a
    boolean (`07-endpoints.md` row 67, in those words).

    ⚠ **ONE SAVEPOINT PER ORDER, AND HARD-WON LAW 14 IS WHY.** Ticking eight
    orders where one is refused BY THE DATABASE must still assign the other
    seven. On PostgreSQL a failed STATEMENT aborts the whole transaction — every
    later query raises `InFailedSqlTransaction` and the batch is lost at COMMIT
    — so catching the error inside one `atomic()` and carrying on is not merely
    untidy, it silently loses the work. **The suite runs on in-memory SQLite,
    which has no aborted-transaction state, so the broken version passes every
    test on every machine.**

    ⚠ **THERE ARE TWO SAVEPOINTS PER ORDER AND ONLY THE PAIR WAS PROVED.**
    `record_act` and `change_priority` each open their own
    `transaction.atomic()`, so removing the LOOP's alone leaves the guarantee
    standing and the PostgreSQL case still passes — measured, not assumed. The
    loop's savepoint is what makes it hold for **any act added later that does
    not bring its own**, which is why it is here rather than left to each
    service. With BOTH removed, `tests/test_us_wrk_025_dispatch_pg.py` fails
    with `psycopg.errors.InFailedSqlTransaction` — law 14's own signature.

    ⚠ **AND THE REFUSAL HAS TO COME FROM THE DATABASE FOR ANY OF THIS TO
    MATTER.** A `NotFoundError` is a SELECT that found nothing: no failed
    statement, no aborted transaction, nothing for a savepoint to contain. The
    first version of the PostgreSQL case used exactly that and could not fail.

    ⚠ **`dispatch_batch` ALLOCATES NOTHING, AND THAT IS NOW RULED.**
    `BR-WRK-021` gives Work four number series and the fourth has no writer;
    `OQ-WRK-1497` asked whether a bulk act is itself a numbered thing and CLOSED
    on 2026-09-04 — *"three separate assignments"*. So per-order results and no
    batch identity is the answer, not a holding shape. (This paragraph read
    *"is OPEN"* until `CR-168-BRC10` round 3 — a stale body, §7.1 P2.12.)
    """
    act = str(payload.get("act") or "").strip()
    if act not in BULK_ACTS:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="work.dispatch.bulk_act_unknown",
            br_ref="BR-WRK-027",
            params={"act": act or "—"},
        )
    ids = payload.get("ids") or []
    if not isinstance(ids, list) or not ids:
        raise errors.ValidationError(
            errors.VAL_REQUIRED, message_key="work.dispatch.selection_empty", br_ref="BR-WRK-027"
        )

    results: list[dict[str, Any]] = []
    for order_id in ids:
        # ⚠ THE SAVEPOINT. See the paragraph above before touching this.
        try:
            with transaction.atomic():
                if act == "assign":
                    done = record_act(actor, order_id, {**payload, "act": "assign"})
                elif act == "reschedule":
                    done = reschedule(actor, order_id, payload)
                else:
                    done = change_priority(actor, order_id, payload)
        except errors.ValidationError as exc:
            results.append(
                {
                    "id": str(order_id),
                    "ok": False,
                    "reason": getattr(exc, "message_key", None) or "work.dispatch.refused",
                }
            )
        except errors.NotFoundError:
            results.append({"id": str(order_id), "ok": False, "reason": "work.dispatch.not_found"})
        except IntegrityError:
            # The database refused this one row. The savepoint is rolled back and
            # the loop carries on; without it, every later statement in this
            # request would raise on PostgreSQL.
            results.append({"id": str(order_id), "ok": False, "reason": "work.dispatch.refused"})
        else:
            # ⚠ **THE ORDER'S ID LAST, AND THIS WAS A REAL BUG.** Written as
            # `{"id": str(order_id), "ok": True, **done}`, the spread overwrote
            # `id` with the ASSIGNMENT ROW's id — `record_act` returns that as
            # its own `id` — so every per-order result named a row the screen
            # has never heard of, and a partial batch could not be matched back
            # to the orders that failed. `US-WRK-027` TC-2 caught it.
            results.append({**done, "id": str(order_id), "ok": True})
    return {
        "act": act,
        "results": results,
        "done": sum(1 for row in results if row["ok"]),
        "failed": sum(1 for row in results if not row["ok"]),
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-024/025/026/027/011 (EP-WRK-05) · 08-screen-layouts.md Work-007 · 07-endpoints.md §5 · 10-execution-plan.md wave G tasks G1–G2
# generated: 2026-09-05 by the CR-070 wave G build lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H✔(work/0009 is the 🔒 path; review-ledger row is G5)
# gates: RED PROVED FIRST — with the seventh-filter check removed, test_us_wrk_026_a_seventh_filter_is_refused fails; with the per-order savepoint removed, the PostgreSQL bulk test loses the whole batch. run_gates.py · pytest · G78 (Work writes nothing foreign)
# exceptions: `dispatch_batch` allocates nothing (BR-WRK-021, OQ-WRK-1497 OPEN) · the order detail and its row action are wave H
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
