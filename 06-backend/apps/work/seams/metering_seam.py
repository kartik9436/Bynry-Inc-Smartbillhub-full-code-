# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-005 (the seam set) · US-WRK-001 (the raise that accepts an
#           order with no connection) · US-WRK-004 (the Orders tab's read)
# Rules:    BR-WRK-002 (read-only seam; a direct write to another module's
#           table fails a gate) · BR-WRK-006 (an order may exist without a
#           connection; at least one anchor) · CLAUDE.md hard rule 1 (every
#           read filtered by the tenant in context; RLS FORCE underneath)
# Tests:    06-backend/tests/test_us_wrk_005_module.py (TC-6 names, TC-7
#           no-context reads) · tests/test_us_wrk_001_anchors.py
# Impacts:  apps/work/selectors.py (reads through here) ·
#           apps/work/services.py (raises through here)
# ───────────────────────────────────────────────────────
"""work → metering: connections, premises and the six Work tables that still
live in `apps/metering/connections.py`.

READS, and the ONE DOOR THAT WRITES
-----------------------------------
* `connection(id)`, `premises(id)` — one row each, as a dict, or None.
* `open_work_orders_queryset()` — every OPEN order of the tenant in context,
  across every anchor, with the joins the Orders tab needs. Handed to
  `apps/work/selectors.py`, which pages and shapes it and never writes.
* `awaiting_approval_queryset()` — the other side of the same coin (CR-070 wave
  B, `BR-WRK-007`): every order the field has FINISHED and nobody has accepted.
  The two state sets are disjoint by construction and must stay that way.
* `raise_work_order(actor, payload)` — **the one call in this package that
  causes a write, and it is metering's own `create_work_order`**, called by
  name. That is the pattern BR-WRK-002 sanctions (the same way a field reading
  will reach `meter_reads` through metering's set-read door in wave L): the
  owning module's service applies its numbering, its audit row and its
  refusals; this file adds nothing and bypasses nothing. It is named
  `raise_…` because it RAISES an order (the product's own verb, B14 rule 15's
  ⚡ *raise work*), and TC-6's forbidden prefixes name ORM verbs, not this one.

`work_orders` is metering's table today (03-field-map.md §4 — PENDING §16).
This file is what makes the eventual move safe: every read and the one write
already go through it, so relocating the models changes this file and nothing
that calls it.
"""

from __future__ import annotations

from collections.abc import Callable
from importlib import import_module
from typing import Any

from django.core.exceptions import FieldError
from django.db.models import Q

from core import errors
from core import tenancy as core_tenancy


def resolve(module: str, attribute: str, kind: str = "services") -> Callable[..., Any] | None:
    """The owning module's callable, or None while its lane has not landed."""
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - defensive
        return None
    fn = getattr(target, attribute, None)
    return fn if callable(fn) else None


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


#: The states an order is OPEN in — the Orders tab's window (Work-007: *"Everything
#: open, across every connection and every account"*). A `completed` order that
#: nobody has accepted is not open work; it is the approval queue (BR-WRK-007,
#: Work-009, wave B), and an accepted or cancelled one is closed.
OPEN_WORK_ORDER_STATES: tuple[str, ...] = ("planned", "in_progress", "blocked")


def cant_read_reason_index() -> dict[str, dict[str, Any]]:
    """DEF-MET-10609 — the ONE can't-read reason list (decision log
    2026-10-26: one list for route readings AND job readings), as metering
    owns it: casefolded code → `{code, name, active}`, switched-off reasons
    included. Read-only; Work never touches `cant_read_reasons`."""
    fn = resolve("metering", "cant_read_reason_index", "field_reads")
    return fn() if fn is not None else {}


def active_cant_read_reasons() -> list[dict[str, str]]:
    """The switched-on reasons in the phone's order, `[{code, name}]` — what a
    job's bundle carries so *Unable to read* works offline."""
    return [
        {"code": row["code"], "name": row["name"]}
        for row in cant_read_reason_index().values()
        if row["active"]
    ]


def connection(connection_id: Any) -> dict[str, Any] | None:
    """One connection of the tenant in context, or None."""
    from apps.work import connection_models as work_tables

    row = (
        work_tables.Connection.objects.filter(tenant_id=_tenant_id(), pk=connection_id)
        .select_related("premises")
        .first()
    )
    if row is None:
        return None
    return {
        "id": str(row.id),
        "connection_no": row.connection_no,
        "state": row.state,
        "premises_id": str(row.premises_id) if row.premises_id else None,
        "address": row.premises.address_line if row.premises_id else None,
    }


def premises(premises_id: Any) -> dict[str, Any] | None:
    """One premises with its coordinates — the map (wave I) READS these and
    never writes them; `geocode_premises` is metering's."""
    from apps.metering import models as metering_models

    row = metering_models.Premises.objects.filter(tenant_id=_tenant_id(), pk=premises_id).first()
    if row is None:
        return None
    return {
        "id": str(row.id),
        "premise_no": row.premise_no,
        "address": row.address_line,
        "city": row.city,
        "lat": None if row.lat is None else str(row.lat),
        "lng": None if row.lng is None else str(row.lng),
    }


def work_order(order_id: Any) -> dict[str, Any] | None:
    """ONE order of the tenant in context, or None — `CR-070` wave H.

    The single-order read `apps/work/checklist.py` needs. A cross-tenant id
    reads as ABSENT rather than as forbidden, which is HR-1 and needs no code
    here: the filter is the tenant in context and RLS `FORCE` sits under it
    (`US-WRK-032` TC-5, `US-WRK-033` TC-6 — both expect `404`).

    `template_id` and `template_version` travel together because together they
    are the ONLY reference `BR-WRK-008` allows an order to keep to the thing it
    was made from — where this job's checklist came from, stated in a way that
    cannot move when the template does.
    """
    from apps.work import connection_models as work_tables

    row = (
        work_tables.WorkOrder.objects.filter(tenant_id=_tenant_id(), pk=order_id)
        .select_related("connection__premises", "premises", "unit__premises", "account")
        .first()
    )
    if row is None:
        return None
    return {
        "id": row.id,
        # B14 rule 31 — the human reference is what a screen shows.
        "order_no": row.order_no,
        "type": row.type,
        "state": row.state,
        "dispatch_state": row.dispatch_state,
        "template_id": row.template_id,
        "template_version": row.template_version,
        "account_id": row.account_id,
        "premises_id": row.premises_id,
    }


def open_work_orders_queryset() -> Any:
    """Every OPEN order of the tenant in context, across every anchor.

    Joined to the four places a premise can come from — the connection's
    premises, the order's own `premises_id` (BR-WRK-006), the unit's premises
    — and to the service and the account, so the Orders tab pages this ONCE
    and reads no more. A READ: the selector orders, searches and slices it and
    writes nothing (G78 fails a write on it outside this package).
    """
    from apps.work import connection_models as work_tables

    return work_tables.WorkOrder.objects.filter(
        tenant_id=_tenant_id(), state__in=OPEN_WORK_ORDER_STATES
    ).select_related("connection__premises", "premises", "unit__premises", "service", "account")


def open_orders_at_unit_queryset(unit_id: Any) -> Any:
    """`CR-089` wave F `F3` — the OPEN orders anchored on ONE unit.

    `BR-WRK-006`'s unit anchor, and only that anchor. It is deliberately NOT
    `orders_at_premises_queryset` narrowed: that function answers *what work
    stands at this ADDRESS* through five anchors, so over a flat it would count
    the job on the flat upstairs. A tile on a unit page must count this unit's
    work or it is worse than no tile.

    The state set is `OPEN_WORK_ORDER_STATES` — the same three words the
    dispatcher's own queue carves out, read from the constant rather than
    restated, so *open* cannot come to mean two things in one product.

    No `select_related`: the one caller COUNTS, and joining four tables to
    throw them away is the shape `service_codes_for_points` warns about one
    module over. A caller that wants rows should add its own.
    """
    from apps.work import connection_models as work_tables

    return work_tables.WorkOrder.objects.filter(
        tenant_id=_tenant_id(), unit_id=unit_id, state__in=OPEN_WORK_ORDER_STATES
    )


def search_work_orders_queryset() -> Any:
    """Every work order of the tenant in context — for `GET /search` ONLY.

    ⚠ **DELIBERATELY UNFILTERED BY STATE, WHICH IS THE OPPOSITE OF EVERY OTHER
    DOOR IN THIS FILE.** `open_work_orders_queryset` and
    `awaiting_approval_queryset` each carve out a work QUEUE, and their two
    state sets are disjoint on purpose. Universal search is not a queue: a
    clerk holding a piece of paper that says `WO-0011` is asking *where is this
    job*, and answering *"no results"* because the job was completed last
    Tuesday would be a worse lie than showing it. `CR-073` §2a.

    Joined to the three places a premise can come from, plus the job-type
    catalogue, so the source builds its context line without a second query per
    row (`selectors._premise_of` does the walk — BR-MET-1161's *derive it by
    walking to the premises*, never a second address column).

    A READ. `G78` fails a write on it anywhere outside this package.
    """
    from apps.work import connection_models as work_tables

    return work_tables.WorkOrder.objects.filter(tenant_id=_tenant_id()).select_related(
        "connection__premises", "premises", "unit__premises", "type_ref"
    )


def search_work_order_templates_queryset() -> Any:
    """Every work-order template of the tenant in context — `GET /search` ONLY.

    Includes DRAFTS and DEACTIVATED templates, for the same reason the orders
    door includes closed orders: a supervisor searching for *Meter set* is
    looking for the template, and the one they cannot find is the one they were
    about to publish. `BR-WRK-012` keeps a deactivated template readable by
    design, and the row's own screen states its state.

    Joined to the service, which is what tells four templates all called
    *Meter set* apart (`BR-WRK-010` keys them on `(tenant, service, name,
    version)` precisely because that name repeats).

    A READ.
    """
    from apps.work import connection_models as work_tables

    return work_tables.WorkOrderTemplate.objects.filter(tenant_id=_tenant_id()).select_related("service")


def awaiting_approval_queryset() -> Any:
    """**`BR-WRK-007` — the queue is a NULL, not a table.** CR-070 wave B.

    Every order of the tenant in context that the field has finished and nobody
    has accepted: `state = completed AND accepted_by IS NULL`, across every
    connection and every anchor. **No new table and no new column** — the queue
    was already in the schema the day `accepted_by` was made nullable, with no
    screen on it, which is what `WM-03` means by *"one query, no new table"*.

    ⚠ **BOTH HALVES ARE LOAD-BEARING AND THE NULL ALONE IS NOT ENOUGH.** A
    `planned` order also has no `accepted_by`; it is not awaiting anyone's
    approval, it is waiting for a technician (`US-WRK-003` TC-3). `state =
    completed` is what says the field has sent something back.

    ⚠ **AND `completed` IS EXACTLY THE STATE `OPEN_WORK_ORDER_STATES` LEAVES
    OUT**, which is why the Orders tab and this queue never show the same row:
    one is *open work*, the other is *finished work nobody has signed off*.
    Change one of these two sets without the other and an order falls into both
    lists or into neither.

    Joined to the same four places a premise can come from as the open list, so
    the queue pages ONCE (`selectors.awaiting_approval` shapes it and writes
    nothing).
    """
    from apps.work import connection_models as work_tables

    return work_tables.WorkOrder.objects.filter(
        tenant_id=_tenant_id(), state=work_tables.WO_COMPLETED, accepted_by__isnull=True
    ).select_related("connection__premises", "premises", "unit__premises", "service", "account")


def completed_work_orders_queryset() -> Any:
    """Every COMPLETED order of the tenant in context — the performance tab's
    denominator (`US-WRK-054`).

    ⚠ **THIS READ WAS INLINE IN `apps/work/selectors.py` UNTIL 2026-09-05 AND
    IT WAS THE ONE REAL FINDING G78 WAS MAKING (`DEF-WRK-4032`).** That file
    imported `apps.metering.connections` directly, which is the line
    `BR-WRK-002` forbids and the line G78 exists to catch: a seam is where
    another module's models are named, and nowhere else.

    A READ. The selector filters it by period, counts it and shapes it, and
    writes nothing — G78 fails a write on it outside this package.

    ⚠ **`completed` HERE MEANS THE SAME STATE `awaiting_approval_queryset`
    USES AND `OPEN_WORK_ORDER_STATES` LEAVES OUT.** One word, one state, read
    from `work_tables.WO_COMPLETED` rather than spelled again, so the performance tab
    and the approval queue can never come to disagree about what finished
    means.
    """
    from apps.work import connection_models as work_tables

    return work_tables.WorkOrder.objects.filter(tenant_id=_tenant_id(), state=work_tables.WO_COMPLETED)


def followed_order_ids() -> set[Any]:
    """The ids of orders that some LATER order names as the one it follows.

    First-time fix is *nothing points AT this job* (`US-WRK-054` TC-5), so the
    direction matters and is easy to invert: the follow-up carries
    `follows_order_id`, which makes the RE-DONE job the target and not the row
    holding a value. Reading it here, once, keeps that sentence in one place.

    Returns a set so the caller tests membership per order without a second
    query. A READ.
    """
    from apps.work import connection_models as work_tables

    return set(
        work_tables.WorkOrder.objects.filter(
            tenant_id=_tenant_id(), follows_order__isnull=False
        ).values_list("follows_order_id", flat=True)
    )


# ── CR-070 wave O · one destination (§W.11) ─────────────────────────────────
#
# `/connections/<uuid>` stops being a place a person navigates to, so the build
# has to be reachable FROM the two records that always exist at an address: the
# premises, and the account. These four readers are that walk, and every one of
# them is a READ — nothing here writes, and G78 fails a foreign write anywhere
# in `apps/work`.
#
# ⚠ **THE PREMISES IS THE HOST THAT ALWAYS EXISTS AND THE ACCOUNT IS NOT.**
# `connections.owner_account_id` is NULLABLE, and that on its own is the whole
# argument: a build carries no owner account until one is asked for, and
# `BR-MET-116` refuses one outright on a build with no common area. An
# account-only host would render an empty screen on any such build (execution
# plan judgment 1).
#
# ⚠ **THIS NOTE SAID `create_owner_account()` RAISES
# `NotImplementedError("OQ-373")` UNTIL 2026-09-12 (`DEF-MET-5081`).** It does
# not; `OQ-373` closed 2026-08-25 → `BR-MET-116` and the writer has existed
# since. The judgment did not depend on that sentence and is unchanged; only its
# proof is. Measured with `app.tenant_id` set on 2026-09-12: **8 `brazosbend`
# connections, 0 with an owner account** — this fixture seeds connection rows
# directly rather than through `commit_connection` step 4.


def followed_by_queryset() -> Any:
    """The orders that FOLLOW the outer order (`follows_order_id = OuterRef(pk)`)
    — for an `Exists(...)` annotation, so Performance's first-time fix is
    counted in SQL rather than over a Python set of every followed id
    (`CR-168-BRC10` P5.6). A READ."""
    from django.db.models import OuterRef

    from apps.work import connection_models as work_tables

    return work_tables.WorkOrder.objects.filter(tenant_id=_tenant_id(), follows_order_id=OuterRef("pk"))


def premises_id_of_unit(unit_id: Any) -> Any | None:
    """The premises a unit refines — `BR-MET-1161`'s walk, one hop.

    An address is stored on `premises` and NOWHERE else, and *"a unit refines a
    premises by LABEL, not by address"*. So every caller that wants to know
    where an account's work is walks account → unit → premises through here
    rather than reading an address column of its own; there is no such column
    to read, and `G85` fails a model that declares one.
    """
    from apps.metering import models as metering_models

    row = (
        metering_models.Unit.objects.filter(tenant_id=_tenant_id(), pk=unit_id)
        .values_list("premises_id", flat=True)
        .first()
    )
    return row


def service_point_ids_on_unit(unit_id: Any, service_code: str | None = None) -> list[str]:
    """The service points of a unit, narrowed to one service when a code is
    given. READ ONLY (`DEF-WRK-9620`).

    ⚠ **THE UNIT, NOT THE ACCOUNT'S AGREEMENTS.** A move-out ENDS its
    agreements before it raises its visit, so a walk through them finds nothing
    on exactly the flow that needs a final read. The meter stands on the unit's
    point whoever holds the account, which is what a crew is sent to.
    """
    from apps.metering import models as metering_models

    if not unit_id:
        return []
    rows = metering_models.ServicePoint.objects.filter(tenant_id=_tenant_id(), unit_id=unit_id)
    if service_code:
        rows = rows.filter(service__code=service_code)
    return sorted(str(pid) for pid in rows.values_list("id", flat=True))


def service_codes_on_unit(unit_id: Any) -> list[str]:
    """The services a UNIT is fitted for — the codes of its live service points,
    ordered. READ ONLY (`DEF-WRK-9645`).

    A move-in asks what field work it may raise about the OUTGOING account, and
    a move-out has already ended that account's agreements, so the account's
    services in force are none — the normal case, not an edge. The unit's
    points are what a crew is sent to whoever holds the account, the same walk
    `service_point_ids_on_unit` makes for `DEF-WRK-9620`.
    """
    from apps.metering import models as metering_models

    if not unit_id:
        return []
    codes = (
        metering_models.ServicePoint.objects.filter(
            tenant_id=_tenant_id(), unit_id=unit_id, deleted_at__isnull=True
        )
        .values_list("service__code", flat=True)
        .distinct()
        .order_by("service__code")
    )
    return [str(code) for code in codes if code]


def service_point_anchor(service_point_id: Any) -> dict[str, Any] | None:
    """Where a meter STANDS — the second hop of the Reads→Work door's walk
    (PO ruling 2026-09-14). READ ONLY.

    `assets_seam.meter` answers which service point a meter is on; this answers
    what that point is, which is metering's to say: the unit it refines, the
    PREMISES that unit refines, and the service the point runs.

    ⚠ **THE PREMISES IS WALKED, NEVER READ OFF THE POINT.** Hard rule 8 —
    `BR-MET-1161`: an address is stored on `premises` and nowhere else, and a
    unit refines a premises by LABEL rather than by address. So a field visit
    raised from a reading is anchored on the premises this returns, and there is
    no address column anywhere on this path to take a short cut through (`G85`
    fails a model that declares one).

    ⚠ **A POINT WITH NO PREMISES ANSWERS `None` FOR IT RATHER THAN RAISING**, and
    the caller turns that into judgment 8's refusal — *a job raised from this
    would stand on nothing*. That refusal belongs on the screen a clerk is
    standing on, not in a seam.
    """
    from apps.metering import models as metering_models

    row = (
        metering_models.ServicePoint.objects.filter(
            tenant_id=_tenant_id(), pk=service_point_id
        )
        .select_related("unit", "service")
        .first()
    )
    if row is None:
        return None
    unit = getattr(row, "unit", None)
    return {
        "unit_id": str(row.unit_id) if row.unit_id else None,
        "premises_id": (
            str(unit.premises_id) if unit is not None and unit.premises_id else None
        ),
        "service_code": getattr(getattr(row, "service", None), "code", None),
    }


def _build_row(row: Any) -> dict[str, Any]:
    """One build's own facts, for the Build tab on either host.

    Every figure is metering's own derivation, called by name: `connection_
    state` (never the cached column — a drifted cache must not put the wrong
    badge on a screen), `connection_mode` (which answers `None` when the orders
    disagree, and §8.3 calls mixed *"the normal case"*), `order_progress` and
    `outstanding_work`. **Nothing is computed here.** A figure derived in a seam
    would be a second, drifting copy of a rule that is already signed and
    tested, which is the fault `connection_detail`'s own docstring names.

    `quote_total` travels as the FOUR-decimal string that is stored beside the
    TWO-decimal string the SERVER rounded (CLAUDE.md hard rule 2); a client that
    re-rounded the stored value would be the second rounding path DEF-088
    removed. `connection_reads._pair` is that one shape, reused rather than
    re-written.
    """
    from apps.metering import connection_reads, connections as w6
    from apps.work import connection_models as work_tables

    done, total = w6.order_progress(row)
    return {
        "id": str(row.id),
        "connection_no": row.connection_no,
        "state": w6.connection_state(row),
        "mode": w6.connection_mode(row),
        "target_activation": (
            row.target_activation.isoformat() if row.target_activation else None
        ),
        "quote_total": connection_reads._pair(row.quote_total),
        "waiting_on": row.waiting_on,
        # `NCT-01`'s UNITS figure, and it is the BUILD's units rather than the
        # premises': a build's units are the ones its SERVICES name, so a later
        # connection on an existing block does not report the whole block. A
        # per-premise service (`unit_id` NULL — the main tap, the building's
        # trash) belongs to the build and to no unit and is not counted as one.
        "units": work_tables.ConnectionService.objects.filter(
            tenant_id=_tenant_id(), connection_id=row.id, unit__isnull=False
        )
        .values("unit_id")
        .distinct()
        .count(),
        "orders": {"done": done, "total": total},
        "outstanding": w6.outstanding_work(row.id),
        # WHERE this build's home is, so the two hosts and the redirect agree.
        "home": home_of_connection(row),
        "premises_id": str(row.premises_id) if row.premises_id else None,
    }


def home_of_connection(row: Any) -> dict[str, str] | None:
    """The one place a person goes to see this build — **metering's own
    `connection_home()`, called by name.**

    Not re-implemented here, and that is the point: this exact answer is drawn
    by metering's worklist row, by both of Work's scoped order lists and by the
    bookmark redirect, and four copies of one routing rule is how a product ends
    up with two of its screens disagreeing about where a thing lives. The same
    posture `raise_work_order` below takes — the owning module's function does
    the work and this file adds nothing.
    """
    from apps.metering import connections as w6

    return w6.connection_home(row)


def build_for_premises(premises_id: Any) -> dict[str, Any] | None:
    """The build at this premises, or None when there is not one.

    Newest first, because a premises can be built on twice — a 1970s connection
    and a 2026 rebuild are two rows — and the one a clerk is asking about is the
    current one. **None is the ordinary answer**, not an error: most premises in
    a utility's book were connected before this product existed, and the screen
    says so in a sentence rather than drawing an empty panel.
    """
    from apps.work import connection_models as work_tables

    row = (
        work_tables.Connection.objects.filter(tenant_id=_tenant_id(), premises_id=premises_id)
        .order_by("-created_at", "-id")
        .first()
    )
    return None if row is None else _build_row(row)


def unit_awaiting_activation(unit_id: Any) -> dict[str, Any] | None:
    """`CR-162-BRC10` — the New Connection this unit still waits on, or
    `None`. A READ through metering's own answer
    (`premises_capacity.unit_not_yet_active`); the account page says
    *"Billing starts when the unit is activated"* and links to the build."""
    from apps.metering import premises_capacity

    return premises_capacity.unit_not_yet_active(unit_id) if unit_id else None


def build_for_account(account_id: Any, unit_id: Any = None) -> dict[str, Any] | None:
    """The build this account is the owner of, or the build at its address.

    ⚠ **TWO READINGS, IN ORDER, AND THE ORDER IS THE JUDGMENT.** An account is
    the owner of a build when `owner_account_id` names it — the direct fact,
    **live since `OQ-373` closed on 2026-08-25 → `BR-MET-116`; this line said
    *"will start being true when `OQ-373` is ruled"* until 2026-09-12
    (`DEF-MET-5081`)**. Failing that, the build AT the account's address is the
    one a clerk means — and that fallback is not a stand-in for an unbuilt first
    reading: a build whose owner was never named has no `owner_account_id` to
    match and its address still does. It is reached by
    `BR-MET-1161`'s walk (account → unit → premises → build) and never by an
    address column, because accounts have none.

    `unit_id` is passed in by the caller that already read the account, so this
    does not read the customers table a second time (`customers_seam.account`
    is the ONE place `apps/work` touches an account row).
    """
    from apps.work import connection_models as work_tables

    row = (
        work_tables.Connection.objects.filter(tenant_id=_tenant_id(), owner_account_id=account_id)
        .order_by("-created_at", "-id")
        .first()
    )
    if row is not None:
        return _build_row(row)
    if unit_id is None:
        return None
    premises_id = premises_id_of_unit(unit_id)
    return None if premises_id is None else build_for_premises(premises_id)


def build_home(connection_id: Any) -> dict[str, str] | None:
    """Where a bookmarked `/connections/<uuid>` link should land.

    ⚠ **A REDIRECT, NEVER A 404** (execution plan judgment 5). The New Connect
    wizard's completion, the *New connects* tab and every bookmark point at that
    path today; answering 404 would break a working link in order to punish a
    screen. An id that is not this tenant's, or is not a build at all, answers
    None here and 404 at the route — identical to an id that does not exist,
    because anything else is an existence oracle across the tenant boundary
    (hard rule 1).
    """
    from apps.work import connection_models as work_tables

    row = (
        work_tables.Connection.objects.filter(tenant_id=_tenant_id(), pk=connection_id)
        .only("id", "owner_account_id", "premises_id")
        .first()
    )
    return None if row is None else home_of_connection(row)


def orders_at_premises_queryset(premises_id: Any) -> Any:
    """Every order standing at this premises, by whichever anchor it has.

    An order is AT a premises when it names the premises itself, or a unit of
    it, or an asset on one of its units, or the build on it, or an account of
    one of its units. All five are `BR-WRK-006`'s four anchors read from the
    place's side, and every one of them is a WALK to the premises rather than a
    stored address — which is `BR-MET-1161` exactly: *"every other entity
    derives it by walking to the premises and declares no address column of its
    own"*. An asset takes the longest walk of the five, asset → service point →
    unit → premises, because `assets.Asset` has no premises column and must
    not grow one (`G85` fails a fourth address home).

    ⚠ **THIS IS A PATH, NOT A FILTER** (execution plan judgment 3).
    `BR-WRK-026` says the dispatcher takes exactly six filters and answers 400
    on a seventh; adding *premises* and *account* as filters would have made it
    eight and put a signed rule in the way of a screen.
    """
    from apps.work import connection_models as work_tables

    return (
        work_tables.WorkOrder.objects.filter(tenant_id=_tenant_id())
        .filter(
            Q(premises_id=premises_id)
            | Q(unit__premises_id=premises_id)
            | Q(asset__service_point__unit__premises_id=premises_id)
            | Q(connection__premises_id=premises_id)
            | Q(account__unit__premises_id=premises_id)
        )
        .select_related(
            "connection__premises",
            "premises",
            "unit__premises",
            "service",
            "account",
            "accepted_by",
            # Joined for the same reason as on the account list: `_scoped_row`
            # serves the priority's NAME and a per-row lookup would be one
            # query per job.
            "priority",
        )
    )


def open_orders_at_premises_queryset(premises_id: Any) -> Any:
    """`CR-089` `F3` / `DEF-MET-4733` — the OPEN orders standing at a PROPERTY.

    ⚠ **THIS IS THE FUNCTION ABOVE NARROWED, AND THAT REUSE IS THE POINT —
    UNLIKE ON A UNIT.** The unit's tile could NOT be the premises walk narrowed,
    because over a flat those five anchors reach the flat upstairs
    (`open_orders_at_unit_queryset` says so in its own docstring). On a PROPERTY
    they are exactly right: `BR-WRK-006`'s five anchors read from the place's
    side ARE what *at this address* means, and they are the same rows the
    property's Work orders tab pages through. **So the tile and the list beneath
    it count one queryset**, and the *"a tile reading 3 over a list showing 2"*
    problem wave F recorded on the unit cannot arise here.

    The state set is `OPEN_WORK_ORDER_STATES`, read from the constant rather
    than restated — *open* has one owner and one definition (`DEF-127`).
    """
    return orders_at_premises_queryset(premises_id).filter(state__in=OPEN_WORK_ORDER_STATES)


def orders_for_account_queryset(account_id: Any, premises_id: Any = None) -> Any:
    """Every order standing on this account, and every order at its address.

    Both, in one list, because a person on an account asks *"what work is
    happening here"* and the answer is rarely all on one anchor: the move-out's
    final read stands on the ACCOUNT, the meter exchange next to it stands on
    the ASSET, and the build's install jobs stand on the CONNECTION. The row
    says which (`selectors._stands_on`), so nothing is claimed that is not true.
    """
    from apps.work import connection_models as work_tables

    where = Q(account_id=account_id)
    if premises_id is not None:
        where = where | Q(premises_id=premises_id) | Q(unit__premises_id=premises_id)
        where = where | Q(asset__service_point__unit__premises_id=premises_id)
        where = where | Q(connection__premises_id=premises_id)
    return (
        work_tables.WorkOrder.objects.filter(tenant_id=_tenant_id())
        .filter(where)
        .select_related(
            "connection__premises",
            "premises",
            "unit__premises",
            "service",
            "account",
            "accepted_by",
            # `_scoped_row` prints the priority's NAME on the account's Work
            # tab (`ACC-T08` draws a PRIORITY column), so it is joined here
            # rather than asked for once per row.
            "priority",
        )
    )


def count_work_orders_of_type(type_id: Any) -> int:
    """How many of this tenant's orders name this job type (`BR-TEN-029`).

    The live used-by count behind the *Work order types* card: it is what
    freezes a code once used (`BR-TEN-030`) and what locks a delete
    (`BR-TEN-034`), so a wrong one is worse than none. `work_orders.type_id`
    is the column `metering/0045` adds beside the free-text `type`; on a
    database where that migration has not run the column does not exist and
    the honest answer is 0 rather than an exception in a Settings screen.
    """
    from django.db.utils import ProgrammingError

    from apps.work import connection_models as work_tables

    try:
        return work_tables.WorkOrder.objects.filter(tenant_id=_tenant_id(), type_ref_id=type_id).count()
    except (FieldError, ProgrammingError):  # pragma: no cover - pre-0045 databases
        return 0


def orders_from_flow_queryset(source: str, source_ref: Any) -> Any:
    """Every order one flow record raised — `BR-WRK-024`'s two columns, read.

    Tenant-scoped like every read in this file, so one utility's move-out can
    never see another's jobs even if two of them allocated the same `MVO-`
    number, which they will: the series is per tenant.
    """
    from apps.work import connection_models as work_tables

    return work_tables.WorkOrder.objects.filter(
        tenant_id=_tenant_id(), source=source, source_ref=source_ref
    )


def orders_from_flow_tally(source: str, source_ref: Any) -> dict[str, int]:
    """How many jobs one flow record raised, and how many have been ACCEPTED.

    ⚠ **THE CANCELLED EXCLUSION LIVES HERE AND NOT IN THE CALLER, BECAUSE
    `WO_CANCELLED` IS METERING'S CONSTANT.** `apps/work/from_flows.py` may not
    import `apps.metering.connections` — that is `BR-WRK-002` and `G78` names
    that module by name — so the count that needs metering's vocabulary is
    computed on this side of the seam and only two integers cross it.

    Cancelled orders are out of BOTH figures: a job somebody called off is not
    work outstanding, and leaving it in the total would hold a service request
    open for ever on a job nobody is going to do.
    """
    from apps.work import connection_models as work_tables

    rows = orders_from_flow_queryset(source, source_ref).exclude(state=work_tables.WO_CANCELLED)
    return {"total": rows.count(), "accepted": rows.filter(accepted_at__isnull=False).count()}


def orders_from_flow_rows(source: str, source_ref: Any) -> list[dict[str, Any]]:
    """The jobs one flow record raised, one small dict each — `CR-168-BRC10` §F.

    `orders_from_flow_tally` answers two integers, which is enough to CLOSE a
    request and not enough for a clerk to SEE the visit: the move record, the
    transfer and the reconnect page each need the number to link and whether
    the field has finished (`DEF-CUS-9628`, `9629`, `9630`). Cancelled orders are
    out, for the tally's reason. Values only — no id is shown as a value
    (B14 rule 31); `order_no` is what the link carries and the clerk reads.
    """
    from apps.work import connection_models as work_tables

    rows = (
        orders_from_flow_queryset(source, source_ref)
        .exclude(state=work_tables.WO_CANCELLED)
        .select_related("service", "assignee_technician__user", "assignee_crew")
        .order_by("order_no", "id")
    )
    answer: list[dict[str, Any]] = []
    for row in rows:
        holder = None
        if row.assignee_crew_id:
            holder = row.assignee_crew.name
        elif row.assignee_technician_id:
            user = getattr(row.assignee_technician, "user", None)
            holder = (getattr(user, "full_name", "") or "").strip() or None
        answer.append(
            {
                "order_no": row.order_no,
                "service": row.service.code if row.service_id else None,
                "state": row.state,
                "done": row.state == work_tables.WO_COMPLETED,
                "accepted": row.accepted_at is not None,
                "assignee": holder,
            }
        )
    return answer


def raise_work_order(actor: Any, payload: Any) -> dict[str, Any]:
    """THE ONE DOOR — metering's own `create_work_order`, by name.

    The payload carries the anchor set (`connection_id` · `premises_id` ·
    `account_id` · `asset_id`, at least one — BR-WRK-006) and the order's own
    fields (`type`, `service`, `scope`, `unit_id`, `mode`, `template_id`,
    `is_gate`, `blocked_by`). Metering allocates the `WO-` number from the
    tenant's series, writes the audit row and refuses an order with no anchor
    BEFORE the database's CHECK gets to (US-WRK-001 TC-3: the CHECK is the
    backstop, proved on PostgreSQL).
    """
    from apps.metering import connections as w6

    data = dict(payload or {})
    return w6.create_work_order(actor, data.pop("connection_id", None), data)



# ── CR-070 wave D · the template header (US-WRK-013/015/018) ────────────────
#
# ⚠ **FOUR MORE DOORS, ALL OF THE SAME KIND AS `raise_work_order`.** The header
# row of a template lives in `work_order_templates`, which is metering's table
# (`03-field-map.md` §4). Work owns the CONCEPT — the seven child collections,
# the version log, the rules about publishing — and writes those itself; the
# header row is written by metering's own service, called BY NAME. Nothing in
# this file touches `WorkOrderTemplate.objects` with a write verb, which is
# what `BR-WRK-002` asks and `G78` enforces.


def template(template_id: Any) -> dict[str, Any] | None:
    """One template header as a dict, or None. A cross-tenant id reads as
    absent, which is HR-1 and needs no code here: the filter is the tenant in
    context and RLS `FORCE` sits under it."""
    from apps.work import connection_models as work_tables

    row = (
        work_tables.WorkOrderTemplate.objects.filter(tenant_id=_tenant_id(), pk=template_id)
        .select_related("service", "type", "skill", "safety_kit")
        .first()
    )
    return None if row is None else _template_row(row)


def templates_queryset() -> Any:
    """Every template of the tenant in context, with the joins `Work-013`'s
    seven columns need. Handed to `apps/work/selectors.py`, which pages and
    shapes it and never writes."""
    from apps.work import connection_models as work_tables

    return (
        work_tables.WorkOrderTemplate.objects.filter(tenant_id=_tenant_id())
        .select_related("service", "type", "skill", "safety_kit")
        .order_by("service__code", "sequence", "name", "id")
    )


def _template_row(row: Any) -> dict[str, Any]:
    """The header, flattened, with the NAMES a screen shows rather than the ids
    it must not (B14 rule 31)."""
    service = getattr(row, "service", None)
    job_type = getattr(row, "type", None)
    skill = getattr(row, "skill", None)
    kit = getattr(row, "safety_kit", None)
    return {
        "id": str(row.id),
        "template_no": row.template_no,
        "name": row.name,
        "service": None
        if service is None
        else {"id": str(service.id), "code": service.code, "name": service.name},
        "scope": row.scope,
        "sequence": row.sequence,
        "job_type": None if job_type is None else {"id": str(job_type.id), "name": job_type.name},
        "skill": None if skill is None else {"id": str(skill.id), "name": skill.name},
        "safety_kit": None if kit is None else {"id": str(kit.id), "name": kit.name},
        "crew_size": row.crew_size,
        "est_duration": row.est_duration,
        "is_gate": row.is_gate,
        "no_gate_reason": row.no_gate_reason,
        "is_sample": row.is_sample,
        "active": row.active,
        "version": row.version,
        "updated_at": row.updated_at,
    }


def create_template(actor: Any, payload: Any) -> dict[str, Any]:
    """metering's `create_work_order_template`, by name — the write this
    product has owed since 2026-08-25 (`sample_data.py:2547`)."""
    from apps.metering import connections as w6

    return w6.create_work_order_template(actor, payload)


def update_template(actor: Any, template_id: Any, payload: Any) -> dict[str, Any]:
    from apps.metering import connections as w6

    return w6.update_work_order_template(actor, template_id, payload)


def publish_template(actor: Any, template_id: Any) -> dict[str, Any]:
    """The header half of THE ONE WRITE. The versions row is Work's and is
    written by `apps/work/templates_svc.publish` in the same transaction."""
    from apps.metering import connections as w6

    return w6.publish_work_order_template(actor, template_id)


def set_template_active(actor: Any, template_id: Any, active: bool) -> dict[str, Any]:
    from apps.metering import connections as w6

    return w6.set_work_order_template_active(actor, template_id, active=active)


def delete_template(actor: Any, template_id: Any) -> dict[str, Any]:
    from apps.metering import connections as w6

    return w6.delete_work_order_template(actor, template_id)


def touch_template(template_id: Any) -> None:
    """metering's own `touch_work_order_template`, by name — the header's
    timestamp moves when a Work-owned collection under it changes."""
    from apps.metering import connections as w6

    w6.touch_work_order_template(template_id)


def orders_raised_from(template_id: Any, version: Any = None) -> int:
    """How many orders this template has produced — counted from `work_orders`
    and cached nowhere (`US-WRK-018` TC-7)."""
    from apps.metering import connections as w6

    return w6.count_orders_from_template(template_id, version)


def orders_raised_by_version(template_id: Any) -> dict[int, int]:
    """`Work-022`'s Versions tab, one count per version, summing to the Usage
    total. One grouped query rather than one per version."""
    from django.db.models import Count

    from apps.work import connection_models as work_tables

    rows = (
        work_tables.WorkOrder.objects.filter(tenant_id=_tenant_id(), template_id=template_id)
        .values("template_version")
        .annotate(n=Count("id"))
    )
    return {int(row["template_version"] or 0): row["n"] for row in rows}


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-005@87b94265 · US-WRK-001@87b94265 (EP-WRK-01) · 03-field-map.md §4
# generated: 2026-09-03 by the CR-070 wave A build lane
# checklist: A✔ B✔ C✔ D✔(GET /work-orders reads through here) E✔(OrdersPage) F✔ G✔ H=n/a
# gates: G78 (no ORM write anywhere in apps/work; foreign model imports only under seams/) · pytest tests/test_us_wrk_005_module.py
# exceptions: `raise_work_order` is a write-causing call inside a read-only seam, stated above and in US-WRK-005 §5 ("the ONE call that writes, and it writes through metering's own service")
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────


# ══════════════════════════════════════════════════════════════════════════
# CR-070 WAVE G · THE DISPATCHER'S DOOR ONTO `work_orders`
# ══════════════════════════════════════════════════════════════════════════
#
# ⚠ **WHY THESE EXIST AT ALL, AND `G78` IS THE ANSWER.** `apps/work/dispatch.py`
# was first written with `from apps.metering import connections as w6` at the
# top of the file, which is a foreign models import outside `seams/` and exactly
# what `BR-WRK-002` forbids: **06-backend/apps/work/dispatch.py:69 imports
# apps.metering.connections outside seams/**. The gate is right and the fix is
# not cosmetic — one file per neighbour is what makes the day `03-field-map.md`
# §4 moves `work_orders` into `apps/work` a change to THIS file and to nothing
# that calls it.
#
# ⚠ **AND THE WRITES GO THROUGH HERE TOO.** A dispatcher assigning a job writes
# `work_orders`, which is metering's table until §16 says otherwise, so the
# write is named here — `raise_work_order` and `touch_template` above already
# take that shape. `apps/work` still writes no neighbour's row directly.


def dispatch_tokens() -> Any:
    """`BR-WRK-023`'s seven states, as metering declares them.

    Returned rather than re-declared, because a second copy of a vocabulary the
    database has a CHECK on is a copy that drifts — and the whole reason
    `ck_work_orders_source` exists one column along is a wave that narrowed a
    vocabulary it did not own (`DEF-WRK-3726`).
    """
    from types import SimpleNamespace

    from apps.work import connection_models as work_tables

    return SimpleNamespace(
        QUEUED=work_tables.DISPATCH_QUEUED,
        SCHEDULED=work_tables.DISPATCH_SCHEDULED,
        EN_ROUTE=work_tables.DISPATCH_EN_ROUTE,
        ON_SITE=work_tables.DISPATCH_ON_SITE,
        COMPLETE=work_tables.DISPATCH_COMPLETE,
        ON_HOLD=work_tables.DISPATCH_ON_HOLD,
        CANCELLED=work_tables.DISPATCH_CANCELLED,
        ALL=work_tables.DISPATCH_STATES,
        IN_FIELD=work_tables.DISPATCH_IN_FIELD_STATES,
    )


def work_order_row(order_id: Any) -> Any:
    """One order of the tenant in context as the MODEL ROW, or `None`.

    ⚠ **NAMED `work_order_row` BECAUSE WAVE H OWNS `work_order`, AND THE TWO
    SHAPES ARE THE WHOLE REASON THE NAMES DIFFER.** Wave H's returns a DICT —
    the read shape every other function in this file hands over. This one
    returns the model row, because the dispatcher's services write it back
    through `save_order_fields` below and a dict cannot be saved. Both landed in
    this file within the hour; the collision was caught by the push helper
    refusing the file, not by anything in the code.
    """
    from apps.work import connection_models as work_tables

    return work_tables.WorkOrder.objects.filter(tenant_id=_tenant_id(), pk=order_id).first()


def work_order_with_joins(order_id: Any) -> Any:
    """The same row with everything `Work-007`'s cells read, in one query."""
    from apps.work import connection_models as work_tables

    return (
        work_tables.WorkOrder.objects.filter(tenant_id=_tenant_id(), pk=order_id)
        .select_related(
            "connection__premises",
            "premises",
            "unit__premises",
            "service",
            "account",
            "asset",
            *DISPATCH_JOINS,
        )
        .first()
    )


def work_order_id_by_number(order_no: str) -> Any:
    """The id of the order a HUMAN can read — `WO-0016` → its uuid, or None.

    ⚠ **THIS EXISTS BECAUSE NOTHING COULD ANSWER THE QUESTION (`DEF-WRK-4518`).**
    Every route on the work-order family is `<uuid:order_id>`, and `order_no` is
    the only reference a person ever sees: it is the Orders table's first
    column, it is what a dispatcher reads down the phone, and it is what the
    detail route's own parameter is NAMED after (`:orderNo`). There was no door
    that took it. So an address built from the number a clerk was looking at
    404'd on every call the screen made, and the screen drew a dash for each.

    ⚠ **TENANT-SCOPED LIKE EVERY OTHER READ IN THIS FILE, AND THAT IS WHY IT
    RETURNS AN ID RATHER THAN TAKING ONE ON TRUST.** `order_no` is allocated per
    tenant (`platform_numbering`), so `WO-0016` exists in more than one utility
    and means a different job in each. The filter below is what makes the
    number safe to put in an address; without it this would be the one read in
    the module that could answer across a tenant boundary.

    Returns the id and not the row, deliberately: the caller then goes through
    `dispatch.order_row`, so the by-number door and the by-id door serve bytes
    from ONE assembler and cannot drift apart (hard-won law 5).
    """
    from apps.work import connection_models as work_tables

    return (
        work_tables.WorkOrder.objects.filter(tenant_id=_tenant_id(), order_no=order_no)
        .values_list("pk", flat=True)
        .first()
    )


def dispatch_queryset() -> Any:
    """The open window with the dispatcher's own joins added to wave A's.

    Built on `open_work_orders_queryset` rather than beside it, so this list and
    the Orders tab cannot disagree about what *open* means.
    """
    return open_work_orders_queryset().select_related(*DISPATCH_JOINS)


#: The dispatcher's joins, shared by the open window and the finished one so the
#: two lists build one row shape from one set of reads. `CR-168-BRC10` adds the
#: hold reason, the two acceptances and the premises' area (the area is WALKED
#: from the premises, never read off `work_orders.area_id` — P2.17's finding).
DISPATCH_JOINS: tuple[str, ...] = (
    "priority",
    "assignee_technician__user",
    "assignee_crew",
    "area",
    "type_ref",
    "hold_reason",
    "accepted_by",
    "accepted_by_technician__user",
    "connection__premises__area",
    "premises__area",
    "unit__premises__area",
    # `DEF-WRK-9622` — a flow's job stands on an account; its premises is
    # walked through the account's unit, in the same query.
    "account__unit__premises__area",
    # `DEF-WRK-9638` — a job raised with no name is named by its template.
    "template",
)


def orders_held_for(hold_reason_id: Any) -> int:
    """How many of this tenant's orders name this hold reason — the lookup
    card's *used by* (`CR-168-BRC10` P0.4). A READ."""
    from apps.work import connection_models as work_tables

    return work_tables.WorkOrder.objects.filter(
        tenant_id=_tenant_id(), hold_reason_id=hold_reason_id
    ).count()


def completed_dispatch_queryset() -> Any:
    """Every FINISHED order of the tenant in context, accepted or not — the
    dispatcher's `status=complete` (`CR-168-BRC10` P1.6, judgment J3).

    By `state`, the truth axis, and not by `dispatch_state`: 22 of the demo's
    23 finished jobs read *queued* on the third axis until `DEF-WRK-9526`, and a
    finished job must be findable whatever its dispatch token says. A READ.
    """
    from apps.work import connection_models as work_tables

    return work_tables.WorkOrder.objects.filter(
        tenant_id=_tenant_id(), state=work_tables.WO_COMPLETED
    ).select_related(
        "connection__premises", "premises", "unit__premises", "service", "account",
        *DISPATCH_JOINS,
    )


def every_dispatch_queryset() -> Any:
    """Every order of the tenant in context, open or finished, with the
    dispatcher's joins — one technician's Jobs tab (`CR-168-BRC10` P3.45, image
    32: *All · Open · Done*). A READ; the two windows above stay the lists'."""
    from apps.work import connection_models as work_tables

    return work_tables.WorkOrder.objects.filter(tenant_id=_tenant_id()).select_related(
        "connection__premises", "premises", "unit__premises", "service", "account",
        *DISPATCH_JOINS,
    )


def save_order_fields(order: Any, fields: list[str]) -> None:
    """Write named columns back on one order — **the ONE write door.**

    Named columns rather than a bare `save()` on purpose: a full save would
    rewrite every column of a row two other waves are also writing, which is
    hard-won law 11's mechanism two in a single table.
    """
    order.save(update_fields=[*fields, "updated_at"])


def submit_field_result(actor: Any, order_id: Any, **fields: Any) -> dict[str, Any]:
    """metering's `submit_field_result`, called BY NAME — the close, and nothing
    more (`BR-WRK-041`, `BR-MET-110`).

    ⚠ **PUBLISHED HERE BECAUSE `BR-WRK-002` FORBIDS THE OBVIOUS IMPORT, AND
    `G78` IS WHAT SAYS SO OUT LOUD.** `apps/work/sync.py` wrote
    `from apps.metering import connections` and the gate failed it by file and
    line: *"imports apps.metering.connections outside seams/"*. The rule is not
    about the write — this call causes one and is meant to — it is about WHERE
    another module's names may appear, so that the whole surface Work depends on
    is readable in one folder instead of scattered through it.

    It is the same pattern as `raise_work_order` above: metering's own service
    applies its state machine, its safety refusal, its audit row and its
    `BR-MET-110` semantics. Work supplies the field data and the handset's
    completion time and decides nothing.
    """
    from apps.metering import connections as w6

    return w6.submit_field_result(actor, order_id, **fields)


def accept_field_result(actor: Any, order_id: Any) -> dict[str, Any]:
    """metering's `accept_field_result`, called BY NAME — BR-MET-110's HUMAN act.

    `DEF-WRK-9062`: the sample seed imported `apps.metering.connections` for
    this one call, and `G78` named the file and line from 2026-09-07. Same
    pattern as `submit_field_result` above: metering applies its own rule and
    writes its own rows; Work decides nothing.
    """
    from apps.metering import connections as w6

    return w6.accept_field_result(actor, order_id)


def send_back_field_result(
    actor: Any, order_id: Any, reason: Any, *, after_acceptance: bool = False
) -> dict[str, Any]:
    """metering's `send_back_field_result`, called BY NAME — `CR-168-BRC10`
    P4.14. Metering moves its own `state`; Work decides nothing (`G78`).
    `after_acceptance` (PO answer 11, 2026-10-21) is passed ONLY by the
    office's reopen (`field_reopen._office_reopen`)."""
    from apps.metering import connections as w6

    return w6.send_back_field_result(actor, order_id, reason, after_acceptance=after_acceptance)


def parse_moment(value: Any, *, field: str) -> Any:
    """metering's own ISO-8601 parser, by name — one answer to *what does 15:30
    mean* for `due_at`, `scheduled_for` and both ends of a window."""
    from apps.metering import connections as w6

    return w6.parse_moment(value, field=field)


# ══════════════════════════════════════════════════════════════════════════
# CR-070 wave L · `L2` · US-WRK-046 · BR-WRK-003 · BR-WRK-015 · hard rule 3
#
# 🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING
#
# AI-authored 2026-09-05 under the PO ruling of 2026-08-09 (*"AI will do it; we
# will review it later as human"*). Its row is in
# `12-governance/09-human-review-ledger.md` (task `L6`) and states in plain
# English exactly what was shown. NOT ratified without a recorded sign-off.
#
# ⚠ **WHY A READ-ONLY SEAM FILE CARRIES A WRITE DOOR, AND WHY THAT IS NOT A
# CONTRADICTION.** `BR-WRK-002` forbids Work from writing another module's
# TABLE; it does not forbid Work from calling the owning module's own SERVICE
# by name. That is the pattern `raise_work_order` above already follows, and
# this file's header says so in as many words: *"the same way a field reading
# will reach `meter_reads` through metering's set-read door in wave L"*. This
# is that door. `apps/work/**` still contains no `MeterRead.objects.create`
# and `G78` still fails one.
# ══════════════════════════════════════════════════════════════════════════


def post_set_reads(actor: Any, order: Any) -> dict[str, Any]:
    """Every reading marked *becomes a meter read*, posted through metering's
    own event-read door — **with its unit, dated to the order's completion**.

    `BR-WRK-003`, and `US-WRK-046`'s own sentence: *a field reading becomes
    billing data exactly once, through the one door billing already trusts.*

    THE THREE FACTS THIS FUNCTION IS ABOUT
    ────────────────────────────────────────────────────────────────────────
    1. **THE DOOR IS METERING'S.** `metering.services.commit_event_reads` —
       the same call the new-connection wizard makes, the same sixteen
       validation rules, the same `meter_reads` insert, the same audit. Work
       does not write the table and does not have a second pipeline for
       field-collected numbers. One validation, two sources
       (`US-WRK-046` TC-7).
    2. **THE DATE IS THE COMPLETION, NEVER THE ACCEPTANCE.** D. Ortiz reads
       1,204 kWh at 16:07 on 15 March; M. Torres accepts at 09:12 on 16 March;
       the meter's history must show **15 March**. `BR-TEN-043`: an event date,
       never a wall clock. Getting this wrong puts a read in the wrong billing
       period and nothing on any screen would show it.
    3. **THE UNIT IS EXPLICIT OR THE READ DOES NOT HAPPEN** (hard rule 3,
       `BR-WRK-015`). See the two paragraphs below — this is the part that is
       genuinely unfinished on the metering side, and it is REPORTED rather
       than worked around.

    ✅ **METERING'S DOOR READS `unit` SINCE 2026-10-05 (`DEF-WRK-4072`, fixed).**
    `_refuse_unit_not_the_registers` (`apps/metering/services.py`) refuses a
    row whose `unit` is not the register's, for every caller, before anything
    is staged — so a mismatch now stops at the door and the check below is a
    second line rather than the only one. The paragraph that follows is the
    history, kept because the check below was written against it: until then
    `_event_read_rows` built each staged row from `meter_no`, `read_at`,
    `reading`, `channel` and `note` and **silently dropped every other key** —
    `unit` included. The unit that lands on the committed
    read is the REGISTER's own (`register_units.register_unit`, `BR-MET-143`),
    which is the right source and is not in question. What is missing is the
    CHECK: metering never compares the unit the caller measured in against the
    unit the register is denominated in. `03-field-map.md` D-13 anticipated
    exactly this and ruled it *"metering's story, filed not worked around"* —
    filed as **`DEF-WRK-4072`**, and the platform behaviour is unchanged by
    this file.

    ⚠ **SO THIS DOOR CHECKS IT ON THE WAY BACK OUT, AND THAT IS NOT A
    WORK-AROUND — IT IS THE ONLY PLACE THE TWO UNITS ARE BOTH IN HAND.** The
    `unit` still travels in the payload (so metering needs no new argument the
    day it starts reading it), and after the post this function compares the
    unit metering STAMPED — `read_dict()["unit"]`, the register's — against the
    unit the technician measured in. A disagreement raises, the enclosing
    acceptance rolls back, and the order stays in the review queue with the
    refusal in words. `US-WRK-046` TC-4/TC-5 ask for precisely that outcome,
    and `BR-MET-143` is the rule underneath: *a mismatch of DIMENSION is never
    reconciled.* A wrong unit here is a wrong bill.

    ⚠ **WHICH METER A READING BELONGS TO IS NOT WRITTEN DOWN ANYWHERE —
    `OQ-WRK-1723`, OPEN, AND THIS FUNCTION REFUSES RATHER THAN GUESSES.**
    `work_order_readings` has six columns (`BR-WRK-015`) and **not one of them
    names a meter**. For every job with ONE meter — a meter set, a reconnect, a
    final read — the order's own `asset` anchor is the answer and there is
    nothing to decide. **A meter EXCHANGE has two**: `WO-4822` records
    `48,221 kWh` on the old meter `E1P-33107` and `1,204 kWh` on the new one
    `E1P-77412`, and the only thing distinguishing them is the wording of a
    prompt a tenant is free to edit. Posting both to the order's anchor would
    write a second read on the OLD meter — a wrong number on a billing path,
    from a guess. So a job carrying more than one posting reading is REFUSED by
    name, the acceptance rolls back, and the question goes to the PO.
    **Do not close this by picking a rule** (prime directive).

    Returns `{"posted": [...], "posted_reads": n, "skipped": [...]}`; posts
    nothing and returns zero when the order has no posting readings, which is
    the ordinary case for most job types.
    """
    from apps.metering import services as metering_services
    from apps.work import models as work_models

    tenant_id = _tenant_id()
    order_id = getattr(order, "id", None) or order
    completed_at = getattr(order, "completed_at", None)

    rows = list(
        work_models.WorkOrderReading.objects.filter(
            tenant_id=tenant_id, work_order_id=order_id, posts_as_meter_read=True
        ).order_by("seq")
    )
    # A reading nobody captured posts nothing. That is not a refusal: an
    # optional reading left blank is a real outcome and `close_readiness` has
    # already decided whether the job could close without it.
    posting = [row for row in rows if row.value is not None]
    skipped = [
        {"reading_id": str(row.id), "prompt": row.prompt, "reason": "no_value_captured"}
        for row in rows
        if row.value is None
    ]
    if not posting:
        return {"posted": [], "posted_reads": 0, "skipped": skipped, "br_ref": "BR-WRK-003"}

    # ── Hard rule 3, BEFORE anything reaches metering ────────────────────
    # *Consumption always with an explicit unit; never assume.* The column is
    # NOT NULL, so a blank here means somebody wrote `""` — and a bare number
    # on a billing path is the failure this rule exists to stop.
    bare = [row for row in posting if not (row.unit_of_measure or "").strip()]
    if bare:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            br_ref="BR-WRK-015",
            message_key="work.reading.unit_required_to_post",
            params={"prompts": [row.prompt for row in bare]},
        )

    meter_no = _posting_meter_no(order, posting)

    completed_day = completed_at.date().isoformat() if completed_at else None
    if not completed_day:
        # `BR-WRK-003` dates the read to the COMPLETION. With no completion
        # there is no date, and defaulting to today would silently move a
        # reading into whatever period the acceptance happened to fall in.
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-WRK-003",
            message_key="work.reading.no_completion_date",
            params={"count": len(posting)},
        )

    event = field_read_event(order)
    result = metering_services.commit_event_reads(
        actor,
        {
            # DEF-WRK-10184 — the JOB's own event, never a blanket `new_connect`.
            "event": event,
            "reads": [
                {
                    "meter_no": meter_no,
                    "value": str(row.value),
                    # Carried even though metering drops it today — see the
                    # docstring. The day metering reads it, nothing here moves.
                    "unit": row.unit_of_measure,
                    "read_at": completed_day,
                    "channel": FIELD_READ_CHANNEL,
                    "note": row.prompt,
                }
                for row in posting
            ],
            "context": {
                "work_order_id": str(order_id),
                "source": "work.field_reading",
                "flow": "field_result_accepted",
                "job_source": getattr(order, "source", None),
            },
        },
    )

    # ── The unit check, a second line since metering's door makes it too ──
    # (DEF-WRK-4072, fixed 2026-10-05 — the door refuses first, by row.)
    # `posted` carries the register's own unit. If it disagrees with what the
    # technician measured in, the two are talking about different physical
    # quantities and the read must not stand: raising here rolls the whole
    # acceptance back, which is `US-WRK-046` TC-4's expected outcome in as many
    # words — *"the acceptance rolls back; the order stays in the queue"*.
    measured = {(row.unit_of_measure or "").strip() for row in posting}
    for read in result.get("posted", []):
        stamped = (read.get("unit") or "").strip()
        if stamped and measured and stamped not in measured:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-MET-143",
                message_key="work.reading.unit_disagrees_with_register",
                params={
                    "meter": read.get("meter") or meter_no,
                    "register_unit": stamped,
                    "measured_unit": sorted(measured)[0],
                },
            )

    return {
        "posted": result.get("posted", []),
        "posted_reads": result.get("posted_reads", len(posting)),
        "warnings": result.get("warnings", []),
        # BR-MET-1189 (PO 2026-10-04, DEF-WRK-9642): a reading the office had
        # already recorded with this exact value that day is not stored twice.
        "already_recorded": result.get("already_recorded", []),
        "skipped": skipped,
        "br_ref": "BR-WRK-003",
    }


#: **`DEF-WRK-10184` — WHICH EVENT A FIELD JOB'S READING IS SAVED UNDER.**
#:
#: PO ruling 2026-10-17 (decision log *"WHERE A USER ENTERS A METER READING"*,
#: gap 7): *"Work → mobile job readings — saved with the job's real event type,
#: not always `new_connect`"*. Until then every accepted reading posted as
#: `new_connect`, so a move-out visit's closing reading read in the meter's
#: history as a NEW CONNECTION — the event BR-MET-128 records so that a reading
#: says why it was taken.
#:
#: **THE KEY IS THE ORDER'S `source` — WHY THE JOB WAS RAISED (`BR-WRK-024`).**
#: It is this product's own closed vocabulary (`connections.WORK_ORDER_SOURCES`,
#: held by `ck_work_orders_source`), stamped by the flow that raised the job.
#: The TYPE is not used: `work_orders.type` is free text and `work_order_types`
#: is a catalogue each utility renames, so reading an event out of *"Meter
#: set"* would be guessing (`US-WRK-007` TC-6: nothing is guessed).
#:
#: | the job was raised by…                  | its readings post as |
#: |-----------------------------------------|----------------------|
#: | a move-out                              | `move_out`           |
#: | a move-in                               | `move_in`            |
#: | a transfer                              | `transfer`           |
#: | a disconnection, or the non-pay rule    | `disconnect`         |
#: | a reconnection                          | `reconnect`          |
#: | a new connection                        | `new_connect`        |
#: | a meter read (Reads → Work)             | `meter_read`         |
#: | Assets (a meter exchange), the age rule | `exchange`           |
#: | anything else — a dispatcher, a service | `meter_read`         |
#: | request, an alert, a failed outcome …   | (the neutral answer) |
#:
#: ⚠ **THE FALLBACK IS `meter_read` AND NEVER `new_connect`.** A job raised for
#: no lifecycle reason is a technician reading a meter; calling it a new
#: connection is the defect this table exists to end. `reconnect`,
#: `meter_read` and `exchange` were appended to `EVENT_CONTEXTS` for this
#: ruling (no database CHECK holds that list; nothing was renumbered).
#:
#: ⚠ The NEW-CONNECTION WIZARD's own typed set reads (`field_data.set_reads`,
#: posted by `connections.accept_field_result`) stay `new_connect` — those ARE
#: a new connection's.
FIELD_READ_EVENT_BY_SOURCE: dict[str, str] = {
    "move_out": "move_out",
    "move_in": "move_in",
    "transfer": "transfer",
    "disconnect": "disconnect",
    "dunning_auto": "disconnect",
    "reconnect": "reconnect",
    "new_connect": "new_connect",
    "meter_read": "meter_read",
    "assets": "exchange",
    "asset_age_rule": "exchange",
}
FIELD_READ_FALLBACK_EVENT = "meter_read"


def field_read_event(order: Any) -> str:
    """The event an accepted field reading posts under — see the table above."""
    source = (getattr(order, "source", None) or "").strip()
    return FIELD_READ_EVENT_BY_SOURCE.get(source, FIELD_READ_FALLBACK_EVENT)


#: The register a field-collected reading lands on: `total`, the flat meter's
#: single channel (`BR-MET-059`, `metering.models.CHANNEL_TOTAL`).
#:
#: ⚠ **`US-WRK-046` TC-1, `J61` AND `J64` SAID *channel `field`* UNTIL
#: 2026-10-05, AND THAT READS AS A SOURCE RATHER THAN A REGISTER — FILED AS
#: `DEF-WRK-4073`, NEVER FOLLOWED, AND THE DOCUMENTS NOW SAY `total`.**
#: A channel in this product names WHICH REGISTER of a meter was read — total,
#: peak, off-peak, export (`BR-MET-059`) — not who read it. Inventing a `field`
#: channel would put field readings in a register no tariff prices and no
#: consumption calculation walks, and `BR-MET-019`'s delta would compare a
#: field read against nothing. WHO read it is already recorded, twice: the
#: batch's `imported_by` is the accepting user (`BR-MET-128`) and this call's
#: `context` carries the work order's own id.
FIELD_READ_CHANNEL = "total"


def _posting_meter_no(order: Any, posting: list[Any]) -> str:
    """WHICH meter — the order's own, or a refusal naming `OQ-WRK-1723`.

    See `post_set_reads`' docstring for why this is a question and not a
    derivation. The two refusals below are deliberately different sentences: a
    job with no meter at all is a template/anchor mistake a clerk can fix, and a
    job with two meters is an unanswered question a clerk cannot.
    """
    asset = getattr(order, "asset", None)
    meter_no = (getattr(asset, "asset_no", None) or "").strip() if asset else ""
    if not meter_no:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-WRK-003",
            message_key="work.reading.no_meter_on_order",
            params={"prompts": [row.prompt for row in posting]},
        )
    if len(posting) > 1:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-WRK-003",
            message_key="work.reading.meter_ambiguous",
            params={
                "count": len(posting),
                "prompts": [row.prompt for row in posting],
                "meter": meter_no,
                "tracks": "OQ-WRK-1723",
            },
        )
    return meter_no


# ── CR-070 wave M · the READS trigger reader (US-WRK-037, BR-WRK-033) ─────────
def meters_in_continuous_flow(
    *,
    consecutive_reads: int = 3,
    minimum_consumption: str = "0",
    service_code: str | None = None,
    unit: str | None = None,
) -> list[dict[str, Any]]:
    """Meters whose flow never stopped — the leak signature. READ ONLY.

    The `high_usage_alert` process (`CR-168-BRC10` P3.33, `DEF-WRK-4097`).

    ⚠ **WHAT "CONTINUOUS FLOW" MEANS HERE, BECAUSE THERE IS NO COLUMN CALLED
    THAT AND INVENTING ONE WOULD HAVE BEEN THE EASY MISTAKE.** `meter_reads`
    carries `status` (BR-MET-021) and `rule_outcomes`, and neither records a
    leak. A continuous-flow alarm is a fact about a SEQUENCE of readings —
    consumption above the floor on every one of the last N — computed here
    from columns that already exist (`BR-WRK-002`: Work writes no metering
    table).

    ⚠ **A SERVICE AND A UNIT, OR NOTHING (`DEF-WRK-4097`, hard rule 3).** Until
    round 5 this took EVERY meter and compared a bare number against kWh and
    kgal alike, so an electric meter — which shows use every period — read as a
    leak: 98 of the demo's 128 meters, 51 of them electric. Now the meter must
    stand on a point of `service_code`, and a reading counts toward the run
    only when its `unit` IS `unit`: a reading in any other unit BREAKS the run.
    It is never converted, because a conversion is a rule nobody signed. With
    no service or no unit this answers NOTHING, and the rule's save refuses
    that shape first (`rules._clean_trigger`).

    ⚠ **THE FLOOR IS THE RULE'S OWN SETTING AND ITS DEFAULT IS ZERO.** A floor
    of zero is still the widest net inside one service and one unit, and that
    breadth is the rule's to narrow (the Review states tonight's count before
    anything is switched on, P3.39). This file guesses no figure.

    ⚠ **ESTIMATES ARE EXCLUDED.** `current_value` is NULL on an estimate
    (BR-MET-028); three estimates in a row are three guesses, and a crew is not
    sent on our own arithmetic.

    ⚠ **THE LAST N PER METER ARE CUT IN SQL** (a window, `ROW_NUMBER() OVER
    (PARTITION BY asset ORDER BY read_at DESC) <= N`), so the read is N rows per
    meter rather than a utility's whole reading history (NFR-3's spirit at
    40,000 accounts).
    """
    from decimal import Decimal

    from django.db.models import F, Window
    from django.db.models.functions import RowNumber

    from apps.metering import models as metering_models

    if not service_code or not unit:
        return []
    tenant_id = _tenant_id()
    want = max(1, int(consecutive_reads))
    floor = Decimal(str(minimum_consumption or "0"))

    rows = (
        metering_models.MeterRead.objects.filter(
            tenant_id=tenant_id,
            lifecycle__in=("committed", "billed"),
            current_value__isnull=False,
            asset__service_point__service__code=service_code,
        )
        .exclude(asset_id__isnull=True)
        .annotate(
            rn=Window(
                RowNumber(),
                partition_by=[F("asset_id")],
                order_by=[F("read_at").desc(), F("id").desc()],
            )
        )
        .filter(rn__lte=want)
        .order_by("asset_id", "rn")
        .values("asset_id", "read_at", "consumption", "unit")
    )

    per_meter: dict[str, list[Any]] = {}
    for row in rows:
        per_meter.setdefault(str(row["asset_id"]), []).append(row)

    out: list[dict[str, Any]] = []
    for asset_id, reads in per_meter.items():
        if len(reads) < want:
            # Not enough history to make the claim. A meter installed last month
            # is not in continuous flow; it is new.
            continue
        if any(
            read["unit"] != unit or read["consumption"] is None or read["consumption"] <= floor
            for read in reads
        ):
            continue
        out.append(
            {
                "asset_id": asset_id,
                "reads": want,
                "latest_read_at": reads[0]["read_at"].isoformat() if reads[0]["read_at"] else None,
                "latest_consumption": str(reads[0]["consumption"]),
                "unit": unit,
            }
        )
    out.sort(key=lambda item: item["asset_id"])
    return out


def estimate_limit() -> int | None:
    """Meter-read settings' own `est_max_consecutive` (`BR-MET-027`, seeded 2)
    — READ, never copied onto a rule (P3.32: two figures would let estimating
    stop at 2 while the rule waits for 3). None when the tenant has no settings
    row, which the reader answers with nothing rather than a guessed limit."""
    from apps.metering import models as metering_models

    row = metering_models.ReadValidationSettings.objects.filter(tenant_id=_tenant_id()).first()
    if row is None:
        return None
    return int(row.est_max_consecutive) if row.est_max_consecutive else None


def meters_at_estimate_limit() -> list[dict[str, Any]]:
    """Meters whose LATEST readings are `est_max_consecutive` estimates in a
    row — `BR-MET-027` forces a visit there, and until round 5 nothing raised it
    (`CR-168-BRC10` P3.32, the `meter_read` process). READ ONLY.

    An estimate is a committed reading with no `current_value` (BR-MET-028).
    The run is counted newest-first and stops at the first actual reading. The
    subject's `run_ends` is the newest estimate's date, so the rule's memory is
    per RUN: a meter that reaches the limit again next year, after an actual
    reading in between, is a new subject.

    The last `limit` readings per meter are cut in SQL, as above.
    """
    from django.db.models import F, Window
    from django.db.models.functions import RowNumber

    from apps.metering import models as metering_models

    limit = estimate_limit()
    if not limit:
        return []
    rows = (
        metering_models.MeterRead.objects.filter(
            tenant_id=_tenant_id(), lifecycle__in=("committed", "billed")
        )
        .exclude(asset_id__isnull=True)
        .annotate(
            rn=Window(
                RowNumber(),
                partition_by=[F("asset_id")],
                order_by=[F("read_at").desc(), F("id").desc()],
            )
        )
        .filter(rn__lte=limit)
        .order_by("asset_id", "rn")
        .values("asset_id", "read_at", "current_value")
    )
    per_meter: dict[str, list[Any]] = {}
    for row in rows:
        per_meter.setdefault(str(row["asset_id"]), []).append(row)
    out: list[dict[str, Any]] = []
    for asset_id, reads in per_meter.items():
        if len(reads) < limit or any(read["current_value"] is not None for read in reads):
            continue
        out.append(
            {
                "asset_id": asset_id,
                "estimates": limit,
                "run_ends": reads[0]["read_at"].date().isoformat() if reads[0]["read_at"] else None,
            }
        )
    out.sort(key=lambda item: item["asset_id"])
    return out


def open_order_for_template(template_id: Any, anchor: dict[str, Any]) -> dict[str, Any] | None:
    """`CR-168-BRC10` P3.38 — the OPEN job this template already has on this
    subject, or None. READ ONLY.

    *One subject, one open job per template*, whoever raised the first — a
    rule, a screen or a clerk. The subject is the most specific anchor the
    raise carries (asset, then unit, then account, then premises, then build),
    so two triggers on one meter, or a screen and a rule on one move-in, find
    each other. A finished, cancelled or accepted job is not open: the next
    one is a new piece of work.
    """
    from apps.work import connection_models as work_tables

    if not template_id:
        return None
    qs = work_tables.WorkOrder.objects.filter(
        tenant_id=_tenant_id(), template_id=template_id, state__in=OPEN_WORK_ORDER_STATES
    ).exclude(dispatch_state="cancelled")
    for key in ("asset_id", "unit_id", "account_id", "premises_id", "connection_id"):
        value = anchor.get(key)
        if value:
            row = qs.filter(**{key: value}).order_by("created_at").first()
            if row is None:
                return None
            return {"id": str(row.id), "order_no": row.order_no}
    return None


def raise_refusal(template_id: Any, anchor: dict[str, Any]) -> str | None:
    """`DEF-WRK-9661` — the refusal metering's raise would answer for this
    template on this subject, or None. READ ONLY, and metering's own check
    (`connections.asset_raise_refusal`), never a copy: the rules preview and a
    rule's *Tonight* ask it so the count they promise is the count the sweep
    raises. Only an ASSET anchor can be refused by the template; an account
    anchor carries the template's own service and nothing to disagree with.
    """
    from apps.metering import connections as w6

    asset_id = (anchor or {}).get("asset_id")
    if not template_id or not asset_id:
        return None
    return w6.asset_raise_refusal(template_id, asset_id)


def orders_raised_by_rule_queryset(rule_id: Any) -> Any:
    """Every job one rule raised, newest first — the rule's Jobs tab (image 63)
    and its Last fired / Jobs raised. READ ONLY; the selector pages it."""
    from apps.work import connection_models as work_tables

    return (
        work_tables.WorkOrder.objects.filter(tenant_id=_tenant_id(), rule_id=rule_id)
        .select_related(*DISPATCH_JOINS, "connection__premises", "premises", "unit__premises")
        .order_by("-created_at", "-id")
    )


# ── CR-070 wave M · the Assets door (US-WRK-038, BR-WRK-056) ────────────────
def orders_for_asset_queryset(asset_id: Any) -> Any:
    """Every order raised against ONE asset. READ ONLY.

    `work_orders.asset_id` is the FK at `connections.py` that, until this wave,
    **nothing wrote** — the Assets door is what fills it. This is the read back
    out, and it is the whole of what `apps/assets` needs from Work: the
    maintenance history's Work-order column is served from here rather than from
    a column on `asset_maintenance`, which is `BR-WRK-056`'s *"no column is
    added to `AssetMaintenance`"*.

    Newest first, because the question a clerk standing on an asset asks is
    *what is happening to this meter now*.
    """
    from apps.work import connection_models as work_tables

    return (
        work_tables.WorkOrder.objects.filter(tenant_id=_tenant_id(), asset_id=asset_id)
        .select_related("service", "priority")
        .order_by("-created_at", "-id")
    )


def service_points_of_units(unit_ids: list[Any], service_code: str | None = None) -> dict[str, dict[str, Any]]:
    """`CR-168-BRC10` P2.16 — the service points on the units a clerk ticked,
    each with the unit's LABEL and its building's address (walked, hard rule 8)
    and the service it runs. Bounded by the ticked units, never the tenant.
    READ ONLY. `{point_id: {unit {id, label}, premises {id, address}, service {code, name}}}`.
    """
    from apps.metering import models as metering_models

    qs = metering_models.ServicePoint.objects.filter(
        tenant_id=_tenant_id(), unit_id__in=list(unit_ids), deleted_at__isnull=True
    ).select_related("unit__premises", "service")
    if service_code:
        qs = qs.filter(service__code=service_code)
    out: dict[str, dict[str, Any]] = {}
    for row in qs:
        unit = row.unit
        premises = unit.premises if unit is not None else None
        out[str(row.id)] = {
            "unit": {"id": str(unit.id), "label": unit.label} if unit is not None else None,
            "premises": None
            if premises is None
            else {"id": str(premises.id), "address": premises.address_line},
            "service": {"code": row.service.code, "name": row.service.name},
        }
    return out


def last_reads(asset_ids: list[Any]) -> dict[str, dict[str, Any]]:
    """`CR-168-BRC10` P2.16 (lane RAISE, image 15's LAST READ) — each asset's
    latest ACTUAL reading: `{asset_id: {reading, unit, on}}`. An estimate
    (no `current_value`) is not a reading of the meter and is skipped. Two
    queries for the whole page, never one per asset. The unit is the read's
    own, always explicit (hard rule 3). READ ONLY."""
    from django.db.models import Max

    from apps.metering import models as metering_models

    ids = [str(a) for a in asset_ids]
    if not ids:
        return {}
    actual = metering_models.MeterRead.objects.filter(
        tenant_id=_tenant_id(), asset_id__in=ids, current_value__isnull=False
    )
    latest = {
        str(row["asset_id"]): row["at"]
        for row in actual.values("asset_id").annotate(at=Max("read_at"))
    }
    if not latest:
        return {}
    match = Q()
    for asset_id, at in latest.items():
        match |= Q(asset_id=asset_id, read_at=at)
    out: dict[str, dict[str, Any]] = {}
    for row in actual.filter(match).order_by("asset_id", "-id"):
        key = str(row.asset_id)
        if key in out:
            continue
        out[key] = {
            "reading": str(row.current_value),
            "unit": row.unit,
            "on": row.read_at.date().isoformat(),
        }
    return out


def units_of_premises(premises_id: Any, unit_ids: list[Any]) -> dict[str, dict[str, Any]]:
    """Which of these unit ids stand on this premises — `{id: {label}}` — so a
    bulk raise can answer *Unit 205 is not on this building* per row before it
    raises anything (`DEF-WRK-9527`'s rule, P2.13). READ ONLY."""
    from apps.metering import models as metering_models

    return {
        str(row.id): {"label": row.label}
        for row in metering_models.Unit.objects.filter(
            tenant_id=_tenant_id(), premises_id=premises_id, pk__in=list(unit_ids)
        )
    }


def unit_labels(unit_ids: list[Any]) -> dict[str, str]:
    """`{unit id: label}` for a bulk raise's answer rows. READ ONLY."""
    from apps.metering import models as metering_models

    return {
        str(pk): label
        for pk, label in metering_models.Unit.objects.filter(
            tenant_id=_tenant_id(), pk__in=list(unit_ids)
        ).values_list("id", "label")
    }


def premises_area_id(premises_id: Any) -> Any | None:
    """A premises' area — the area a job raised there will stand in (ruling 24:
    never asked on the raise). READ ONLY."""
    from apps.metering import models as metering_models

    return (
        metering_models.Premises.objects.filter(tenant_id=_tenant_id(), pk=premises_id)
        .values_list("area_id", flat=True)
        .first()
    )


def template_asset_type_ids(template_id: Any) -> list[str]:
    """The asset types one template applies to — `wot_asset_types`. READ ONLY.

    ⚠ **`wot_asset_types` IS WORK'S OWN TABLE, NOT METERING'S**, so this
    function is a convenience that belongs beside the template reads rather than
    a cross-module read; it is here so a caller filtering templates has one
    import rather than two. The rows are read through Work's own model.
    """
    from apps.work import models as work_models

    return [
        str(row.asset_type_id)
        for row in work_models.WorkOrderTemplateAssetType.objects.filter(
            tenant_id=_tenant_id(), template_id=template_id
        )
    ]


def work_orders_dataset_queryset() -> Any:
    """EVERY order of the tenant in context — the `work_orders` DATASET's fact.

    ⚠ **DELIBERATELY NOT `open_work_orders_queryset()`, AND THAT IS THE WHOLE
    POINT OF A SECOND FUNCTION.** The Orders tab asks *what is outstanding* and
    filters to three states. R33 Service Order Activity asks *what happened in
    this window* and its own drawn tiles are `Raised 148 · Completed 132 ·
    Open 16` — a report that could not see a completed order would report 148
    raised and 0 completed, foot perfectly, and be wrong. So the state set is
    the caller's filter here and never this function's opinion.

    ⚠ **ALL FOUR ANCHORS ARE JOINED, INCLUDING `asset`.** `BR-WRK-006` gives an
    order four anchors and `apps/work/selectors._premise_of` walks three of
    them; the asset chain (asset → service point → unit → premises) is the
    fourth, and an order anchored only on a meter would otherwise show an empty
    PREMISES cell on a report whose own drawn warning is *"the premises column
    walks to premises like every other address in the product"*. Hard rule 8.

    A READ. `G78` fails a write on it outside this package, and the dataset
    query that consumes it performs none.
    """
    from apps.work import connection_models as work_tables

    return work_tables.WorkOrder.objects.filter(tenant_id=_tenant_id()).select_related(
        "connection__premises",
        "premises",
        "unit__premises",
        "asset__service_point__unit__premises",
        "service",
        "account",
        "priority",
        "type_ref",
        "assignee_crew",
        "assignee_technician__user",
    )


def completed_work_order_state() -> str:
    """The owning module's word for *finished* — `work_tables.WO_COMPLETED`.

    ⚠ **ONE WORD, ONE STATE, READ RATHER THAN SPELLED AGAIN.**
    `completed_work_orders_queryset` above already made that argument for the
    performance tab and the approval queue; a REPORT counting `Completed 132`
    against a string typed a second time is the third surface that can come to
    disagree about what finished means. This returns the constant so a caller
    building its own `Q(...)` — the `work_orders` dataset query does — reaches
    the same one.
    """
    from apps.work import connection_models as work_tables

    return work_tables.WO_COMPLETED


def passed_outcome() -> str:
    """The owning module's word for a job that PASSED — `work_tables.OUTCOME_PASSED`.

    B18 §8.3's five outcomes are metering's tokens. `DEF-WRK-9070`: the sample
    seed typed `"completed"` — a STATE, not an outcome — and
    `submit_field_result` stored it, because nothing validates the token. Read
    rather than spelled again, the way `completed_work_order_state` is.
    """
    from apps.work import connection_models as work_tables

    return work_tables.OUTCOME_PASSED


def premises_of_an_activated_build() -> Any | None:
    """The premises of the tenant's first ACTIVATED build, or None. A READ.

    `DEF-WRK-9071`: the sample seed's one costed job needs an order it may
    finish. Every planned order in the sample tenant belongs to one of B18
    §5.4.8's drawn builds, and finishing one moves a drawn `ORDERS` fraction.
    An activated build's premises already takes service, so a stand-alone job
    there (`BR-WRK-006`: a premises is an anchor on its own) moves no build.
    """
    from apps.work import connection_models as work_tables

    return (
        work_tables.Connection.objects.filter(tenant_id=_tenant_id(), state=work_tables.ACTIVATED)
        .exclude(premises_id=None)
        .order_by("connection_no")
        .values_list("premises_id", flat=True)
        .first()
    )


# ══════════════════════════════════════════════════════════════════════════
# CR-187-BRC10 · lane S-FIND · T-40 — where a job and a meter STAND, for the
# field app's Nearby list (FF-11) and its asset search (FF-41). READS.
# ══════════════════════════════════════════════════════════════════════════

#: The units a job may stand on, in the order `selectors._premises_row` walks
#: its anchors — the order's own unit, the account's unit, the meter's unit.
_JOB_UNIT_CHAIN: tuple[str, ...] = ("unit", "account__unit", "asset__service_point__unit")
#: The premises a job may stand on — `selectors._premises_row`'s five hops, in
#: its order, so Nearby and the Orders tab cannot disagree about where a job is.
_JOB_PREMISES_CHAIN: tuple[str, ...] = (
    "connection__premises",
    "premises",
    "unit__premises",
    "account__unit__premises",
    "asset__service_point__unit__premises",
)


def _first_of(chain: tuple[str, ...], column: str) -> Any:
    """`column` off the FIRST anchor in `chain` that is present — NULL when
    that anchor carries no value. It never falls through to a later anchor on
    a null value: the first anchor present IS where the job stands."""
    from django.db.models import Case, F, FloatField, When
    from django.db.models.functions import Cast

    return Case(
        *[
            When(**{f"{hop}__isnull": False}, then=Cast(F(f"{hop}__{column}"), FloatField()))
            for hop in chain
        ],
        default=None,
        output_field=FloatField(),
    )


def nearby_jobs_queryset() -> Any:
    """The OPEN orders of the tenant in context — `dispatch_queryset()`, so
    Nearby, Today and the dispatcher agree on what *open* means — each
    annotated with the POINT it stands on. READ ONLY; the caller filters,
    sorts and pages it in SQL (`NFR-3`).

    ⚠ **THE POINT IS THE PREMISES', AND A UNIT'S OWN POINT WINS WHERE IT HAS
    ONE** — hard rule 8 as narrowed by `BR-MET-1162` (PO 2026-09-08: *"GIS data
    for unit might change and hence we have to have parcel ID and GIs details
    on Unit also"*). A unit with no point of its own reads its building's, and
    `pt_source` says which of the two was used. A unit point is taken only when
    it has BOTH halves: half a coordinate is not a place.

    Annotations: `pt_lat`, `pt_lng` (floats, degrees) and `pt_source`
    (`unit` · `premises` · NULL when the job has no point at all).
    """
    from django.db.models import Case, CharField, F, FloatField, Value, When

    qs = dispatch_queryset().annotate(
        u_lat=_first_of(_JOB_UNIT_CHAIN, "lat"),
        u_lng=_first_of(_JOB_UNIT_CHAIN, "lng"),
        p_lat=_first_of(_JOB_PREMISES_CHAIN, "lat"),
        p_lng=_first_of(_JOB_PREMISES_CHAIN, "lng"),
    )
    unit_has_point = Q(u_lat__isnull=False, u_lng__isnull=False)
    premises_has_point = Q(p_lat__isnull=False, p_lng__isnull=False)
    return qs.annotate(
        pt_lat=Case(
            When(unit_has_point, then=F("u_lat")),
            When(premises_has_point, then=F("p_lat")),
            default=None,
            output_field=FloatField(),
        ),
        pt_lng=Case(
            When(unit_has_point, then=F("u_lng")),
            When(premises_has_point, then=F("p_lng")),
            default=None,
            output_field=FloatField(),
        ),
        pt_source=Case(
            When(unit_has_point, then=Value("unit")),
            When(premises_has_point, then=Value("premises")),
            default=None,
            output_field=CharField(),
        ),
    )


def service_point_ids_at_address(text: str) -> Any:
    """A SUBQUERY of the service points whose premises' address contains
    `text` — the *address* leg of the field asset search. READ ONLY."""
    from apps.metering import models as metering_models

    return metering_models.ServicePoint.objects.filter(
        tenant_id=_tenant_id(), unit__premises__address_line__icontains=text
    ).values("id")


def unit_ids_at_address(text: str) -> Any:
    """A SUBQUERY of the units whose premises' address contains `text` — for a
    device seated on a unit through `asset_assignments` rather than a point."""
    from apps.metering import models as metering_models

    return metering_models.Unit.objects.filter(
        tenant_id=_tenant_id(), premises__address_line__icontains=text
    ).values("id")


def service_point_ids_on_units(unit_ids: Any) -> Any:
    """A SUBQUERY of the service points standing on `unit_ids` (a list or a
    subquery) — so an account found by number reaches the meters on its unit."""
    from apps.metering import models as metering_models

    return metering_models.ServicePoint.objects.filter(
        tenant_id=_tenant_id(), unit_id__in=unit_ids
    ).values("id")


def places_of(service_point_ids: list[Any], unit_ids: list[Any]) -> dict[str, dict[str, Any]]:
    """Where each of a PAGE of meters stands — keyed `sp:<id>` and `unit:<id>`.

    `{unit_label, premises: {id, premise_no, address, city, state,
    postal_code}, lat, lng, point_source}`. The address is WALKED to the
    premises (hard rule 8); the point is the unit's own where it has both
    halves, else the premises' (`BR-MET-1162`). Two queries for the page,
    whatever its size — never one per row. READ ONLY.
    """
    from apps.metering import models as metering_models

    def place(unit: Any) -> dict[str, Any]:
        premises = unit.premises
        if unit.lat is not None and unit.lng is not None:
            lat, lng, source = unit.lat, unit.lng, "unit"
        elif premises.lat is not None and premises.lng is not None:
            lat, lng, source = premises.lat, premises.lng, "premises"
        else:
            lat, lng, source = None, None, None
        return {
            "unit_label": unit.label,
            "premises": {
                "id": str(premises.id),
                "premise_no": premises.premise_no,
                "address": premises.address_line,
                "city": premises.city,
                "state": premises.state,
                "postal_code": premises.postal_code,
            },
            "lat": None if lat is None else str(lat),
            "lng": None if lng is None else str(lng),
            "point_source": source,
        }

    out: dict[str, dict[str, Any]] = {}
    sp_ids = [i for i in service_point_ids if i]
    if sp_ids:
        for point in metering_models.ServicePoint.objects.filter(
            tenant_id=_tenant_id(), pk__in=sp_ids
        ).select_related("unit__premises"):
            out[f"sp:{point.id}"] = place(point.unit)
    u_ids = [i for i in unit_ids if i]
    if u_ids:
        for unit in metering_models.Unit.objects.filter(
            tenant_id=_tenant_id(), pk__in=u_ids
        ).select_related("premises"):
            out[f"unit:{unit.id}"] = place(unit)
    return out


# CR-187-BRC10 lane S-ORDER — the field app's order acts (T-36…T-39, T-42).
# Same discipline as every door above: metering's NAMES appear here and only
# here (`BR-WRK-002`, `G78`); the one write is `save_order_fields`.
# ══════════════════════════════════════════════════════════════════════════


def work_order_row_for_update(order_id: Any) -> Any:
    """The order row, LOCKED for the rest of the caller's transaction, or None.

    A claim (`field_claim.py`) is two technicians racing for one unassigned
    job; the second must see the first's assignment, not the same NULL. A READ
    that takes a row lock — it writes nothing.
    """
    from apps.work import connection_models as work_tables

    return (
        work_tables.WorkOrder.objects.select_for_update()
        .filter(tenant_id=_tenant_id(), pk=order_id)
        .first()
    )


def work_order_state_tokens() -> Any:
    """`state` and `outcome` tokens, from the module that owns them — read,
    never spelled again (the `completed_work_order_state` argument)."""
    from types import SimpleNamespace

    from apps.work import connection_models as work_tables

    return SimpleNamespace(
        PLANNED=work_tables.WO_PLANNED,
        IN_PROGRESS=work_tables.WO_IN_PROGRESS,
        COMPLETED=work_tables.WO_COMPLETED,
        CANCELLED=work_tables.WO_CANCELLED,
        OPEN=OPEN_WORK_ORDER_STATES,
        PASSED=work_tables.OUTCOME_PASSED,
        FAILED=work_tables.OUTCOME_FAILED,
        PARTIALLY_DONE=work_tables.OUTCOME_PARTIALLY_DONE,
        WAITING=work_tables.OUTCOME_WAITING,
        OUTCOMES=work_tables.WORK_ORDER_OUTCOMES,
    )


def refresh_build_state(order: Any) -> None:
    """metering's `refresh_connection_state`, called BY NAME — the one writer
    of `connections.state` — for an order standing on a build. A job reopened
    in the field is no longer done, and the build's state must say so, exactly
    as `send_back_field_result` already re-derives it."""
    if not getattr(order, "connection_id", None):
        return
    from apps.metering import connections as w6

    w6.refresh_connection_state(order.connection)


def finished_orders_queryset() -> Any:
    """Every COMPLETED order of the tenant, accepted or not, with the joins an
    acceptance-queue row reads. A READ (`field_outcomes.office_queue`)."""
    from apps.work import connection_models as work_tables

    return work_tables.WorkOrder.objects.filter(
        tenant_id=_tenant_id(), state=work_tables.WO_COMPLETED
    ).select_related(
        "connection__premises", "premises", "unit__premises", "service", "account",
        "assignee_technician__user", "priority",
    )


def orders_by_ids_queryset(order_ids: list[Any]) -> Any:
    """These orders of the tenant, with the joins a queue row reads. A READ."""
    from apps.work import connection_models as work_tables

    return work_tables.WorkOrder.objects.filter(
        tenant_id=_tenant_id(), pk__in=list(order_ids)
    ).select_related(
        "connection__premises", "premises", "unit__premises", "service", "account",
        "template", "priority", "asset",
    )
