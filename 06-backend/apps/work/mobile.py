# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-041 (today's jobs, `WM-32`) · US-WRK-042 (the job on the
#           phone, `WM-33`) · US-WRK-030 (the device that gets pushed to,
#           `WM-37`) · US-WRK-040 (the shell's identity).
#           Screens: Work-010, Work-011
# Rules:    BR-WRK-035 (ordered by appointment time, NEVER priority) ·
#           BR-WRK-036 (the offline marker with the last sync time) ·
#           BR-WRK-038 (help rides with the job and opens offline) ·
#           BR-WRK-008 (everything is the order's own copy) · BR-WRK-042
#           (the bundle is fetched at sync, never on tap) · hard rule 1
#           (tenant scope) · hard rule 3 (a quantity carries its unit) ·
#           B14 rule 31 (no database id is a visible value)
# Tests:    06-backend/tests/test_us_wrk_041_today.py ·
#           tests/test_us_wrk_042_bundle.py · tests/test_us_wrk_030_push.py ·
#           tests/test_cr187_sync_feed.py · tests/test_cr187_sync_feed_pg.py
#           (CR-187-BRC10 T-31/T-32: the feed's tombstones and cursor)
# Impacts:  apps/work/api.py (#88, #89, #91) · features/work/mobile/** (the
#           three screens that read these) · apps/work/push.py (the device)
# ───────────────────────────────────────────────────────
"""The phone's three server reads: the day, the job, and the device register.

`07-endpoints.md` §6 #88, #89 and #91. #90 — the sync that sends work BACK — is
wave L's and is deliberately absent: nothing here writes anything a technician
captured.

WHY THE DAY IS ORDERED BY TIME AND THE ORDERING IS NOT CONFIGURABLE
--------------------------------------------------------------------
`BR-WRK-035`, from `WM-32`: *"Sorted by appointment time, not priority — a
technician drives a route, and an Urgent job across town does not jump the one
they are standing outside. **Priority shows as a pill; it does not reorder.**"*

`US-WRK-041` TC-2 is the negative that makes it real: moving `WO-4822` to Urgent
**does not** move it above `WO-4824`. The pill changes, the order does not. So
the sort key here is the appointment and the priority is a returned VALUE — a
lane adding `priority__rank` to this `order_by` would break a rule while making
the list look more useful, which is why the reason is written at the site.

⚠ **THE SORT IS `window_start`, THEN `due_at`, THEN the order number**, and the
third leg is not decoration: two jobs with no window and the same due date would
otherwise come back in whatever order the database felt like, and a day list
that reshuffles itself between two syncs is a technician losing their place.

WHAT IS COMPUTED HERE AND WHAT IS NOT
--------------------------------------
The **offline marker** (`BR-WRK-036`, *◍ offline · synced 08:12*) is NOT here
and cannot be: it is the time the PHONE last reached the server, which only the
phone knows. The server would have to answer *"now"*, which is precisely the
lie the rule exists to prevent — a marker that always reads *just synced*
because the thing rendering it is the thing being asked. `US-WRK-041` TC-4
(*"the phone has never synced"* → *◍ offline · never synced*) is unanswerable
from this file. The client stores it; see `features/work/mobile/offlineStore.ts`.

⚠ **THE BUNDLE IS FETCHED AT SYNC, NEVER ON TAP** (`BR-WRK-042`, `US-WRK-042`
TC-1: *"zero network requests during the tap"*). That is a CLIENT obligation and
this file cannot enforce it; what this file does is make it possible — `bundle`
returns everything one job needs in ONE response, so the phone has nothing left
to go back for. A route that answered half a job would make the rule
unimplementable however careful the client was.

THE HELP DOCUMENTS ARE PRE-SIGNED LINKS, AND THEY EXPIRE
---------------------------------------------------------
`BR-WRK-038`: *"Help is carried with the job and available offline — the SOP,
the supervisor's number, the hotline."* A `work_order_help` row of kind
`document` carries a `stored_documents` id in `ref`; this issues
`document_store.download_url` for it, which is a **four-hour bearer token** (PO
ruling 2026-08-30). The phone downloads the bytes into its own store AT SYNC and
opens them from there — so the link expiring is exactly right and does not break
`US-WRK-042` TC-2 (*"the SOP opens from the offline store"*). A phone that kept
the URL instead of the bytes would have a working SOP for four hours and a
broken one in the meter pit, which is the failure this rule is about.

⚠ **A LINK IS ISSUED ONLY FOR A DOCUMENT THE CALLER COULD ALREADY FIND.**
`document_store.download_url` resolves the row under the caller's tenant context
first and mints the URL second, so a `ref` pointing at another utility's
document yields the same answer as one pointing at nothing.
"""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.work import checklist as work_checklist
from apps.work import models
from apps.work.seams import assets_seam, customers_seam, metering_seam
from core import audit as core_audit
from core import device_clock, errors
from core import permissions as core_permissions
from core import tenancy as core_tenancy

logger = logging.getLogger("smartbillhub.work.mobile")

#: How many days ahead the *Week* tab reaches. `US-WRK-040` TC-7: *"Week is
#: Today's list for the week ahead"* — seven days including today.
WEEK_DAYS = 7


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _actor_id(actor: Any) -> Any:
    return getattr(actor, "id", None) or getattr(actor, "pk", None)


def technician_of(actor: Any) -> Any | None:
    """The `technicians` row for this login, or None.

    ⚠ **NONE IS A NORMAL ANSWER AND NEVER AN ERROR** — `US-WRK-040` TC-3: a
    login with no technician profile gets *"No field work for this login"* (six
    words, B14 rule 33) over an EMPTY DAY, never an error page. A clerk who taps
    a link a colleague sent them is the common case, and an error page would
    read as a broken product rather than as *this is not your app*.
    """
    user_id = _actor_id(actor)
    if user_id is None:
        return None
    return models.Technician.objects.filter(tenant_id=_tenant_id(), user_id=user_id).first()


def _no_profile() -> dict[str, Any]:
    """The empty day. Six words and a reason token — never an error."""
    return {
        "technician": None,
        "jobs": [],
        "count": 0,
        "done": 0,
        # The screen renders its own catalogue's sentence from this token; the
        # words are not in the payload (B14 rule 32 — no internal code in
        # clerk-facing copy, and no English in a JSON body a catalogue will
        # translate).
        "empty_reason": "no_technician_profile",
    }


def _job_card(order: Any, detail: Any | None) -> dict[str, Any]:
    """One card of `Work-010` — `WO-4822 · Meter exchange · 221 Oak Ave ·
    15:30 · 45 min · ⚠ Access: dog in rear yard · gate code 4417`.

    ⚠ **THE ACCESS NOTES AND THE GATE CODE COME FROM THE ORDER'S OWN COPY**
    (`work_order_details`, `BR-WRK-008`), not from the template and not from a
    live read of the premises. `US-WRK-041` TC-5 asserts them on the card, and
    the reason they are copied is `US-WRK-042` TC-3: a template edited after the
    job synced must not change what the technician was told to expect behind a
    gate.

    ⚠ **`priority` IS RETURNED AND DOES NOT ORDER ANYTHING** — `BR-WRK-035`.
    """
    from apps.work import dispatch as work_dispatch

    return {
        # B14 rule 31 — the visible reference is the human one. The uuid is
        # here only because the phone builds a route from it.
        "id": str(order.id),
        "order_no": order.order_no,
        "type": (order.type_ref.name if order.type_ref_id else order.type),
        "premise": work_dispatch._premise_of(order),
        "window_start": order.window_start.isoformat() if order.window_start else None,
        "window_end": order.window_end.isoformat() if order.window_end else None,
        "due_at": order.due_at.isoformat() if order.due_at else None,
        # `DEF-WRK-9688` — `{date, start, end, time_zone}` in the UTILITY's
        # zone, the same answer the edit page and the customer's message read
        # (`edit._appointment`). The card drew `window_start` in the PHONE's
        # zone, which is one more clock for one promise.
        "appointment": _appointment_of(order),
        # `DEF-WRK-9693` — no visit booked: the phone groups these last, under
        # *Unscheduled*, rather than drawing them as if they had a time.
        "unscheduled": order.window_start is None,
        # `45 min` on the card. `est_duration` is a DurationField, so the
        # MINUTES are derived here rather than in the front end: a duration
        # rendered by a browser is eleven catalogues' worth of *45 minutes* /
        # *45 min* / *45 Min.* and one of them will get it wrong.
        "est_minutes": (
            int(order.est_duration.total_seconds() // 60) if order.est_duration else None
        ),
        # A PILL. Not a sort key. See the module docstring.
        "priority": work_dispatch._priority_of(order),
        "state": order.state,
        "dispatch_state": order.dispatch_state,
        "access_notes": (detail.access_notes if detail else ""),
        "hazards": (detail.hazards if detail else ""),
        "gate_code": (detail.gate_code if detail else ""),
        # `DEF-FLD-10582` (MQ-015) — the meter, so FF-15's Asset card is not
        # *No asset* on a job that has one. Read through the seams at use.
        "meter": _meter_of(order),
        # `DEF-FLD-10579` — has the technician taken it, declined it, or
        # neither yet? The phone shows *Decline* only before it is taken and
        # *Declined* after a decline; read from the order's own columns, no
        # query (`dispatch._technician_acceptance`, the board's own reading).
        "technician_acceptance": work_dispatch._technician_acceptance(order),
        # FB-030 (PO 2026-10-31) — a job closed on the web or another phone
        # shows in FF-35 with its outcome and time, and whether the office has
        # accepted it (`accepted_at`, the office's review, BR-MET-110). Read
        # from the order's own columns, no query.
        "completed_at": order.completed_at.isoformat() if order.completed_at else None,
        "outcome": order.outcome,
        "accepted_at": order.accepted_at.isoformat() if order.accepted_at else None,
    }


def _meter_of(order: Any) -> dict[str, Any] | None:
    """The meter this job is about — `{id, asset_no, serial_no, model,
    size_class, service}` or None (`DEF-FLD-10582`, MQ-015).

    The order's own ASSET anchor first (`BR-WRK-006`). A job raised on a UNIT
    or an ACCOUNT names no asset, so its meter is the one IN-SERVICE meter on
    that unit's points for the job's service — and only when there is exactly
    one: two candidates is a question for the technician on site, never a
    guess on the card.

    ⚠ **READ THROUGH `assets_seam` AND `metering_seam`, NEVER COPIED ONTO THE
    ORDER** — a meter exchanged since the job synced is the NEW meter on the
    next sync (the phone's server-wins upsert). The badge is not served:
    `assets_seam.job_meter` says why.
    """
    from apps.work import selectors as work_selectors

    asset_id = getattr(order, "asset_id", None)
    if not asset_id:
        unit = work_selectors._unit_row(order)
        if unit is None:
            return None
        service_code = order.service.code if getattr(order, "service_id", None) else None
        points = metering_seam.service_point_ids_on_unit(unit.id, service_code)
        meters = assets_seam.in_service_meters_on_points(points)
        if len(meters) != 1:
            return None
        asset_id = meters[0]["id"]
    meter = assets_seam.job_meter(asset_id)
    if meter is None:
        return None
    point_id = meter.pop("service_point_id")
    anchor = metering_seam.service_point_anchor(point_id) if point_id else None
    return {**meter, "service": (anchor or {}).get("service_code")}


def _appointment_of(order: Any) -> dict[str, Any] | None:
    from apps.work import edit

    return edit._appointment(order)


def today(actor: Any, *, days: int = 1) -> dict[str, Any]:
    """`GET /work/mobile/today` — this technician's day, in appointment order.

    `days=7` is the *Week* tab (`US-WRK-040` TC-7); the shape is identical,
    which is the point — Week is Today's list over a longer window and not a
    second screen with a second sort.

    ⚠ **ONE TECHNICIAN: THE CALLER'S OWN.** There is no `technician_id`
    parameter and there deliberately never will be one on this route.
    `US-WRK-041` TC-6 says *"a query for another technician's day is 403"*; a
    route with no such parameter cannot be asked the question at all, which is
    stronger than a route that asks and refuses. A supervisor wanting to see
    somebody else's day has `Work-007`, the dispatcher, on the web.
    """
    technician = technician_of(actor)
    if technician is None:
        return _no_profile()

    tenant_id = _tenant_id()
    # T-32 (`CR-187-BRC10`) — the watermark is taken BEFORE the read, so a job
    # that changes while the list is being built is re-sent by the first
    # refresh rather than missed by it.
    cursor = day_cursor()
    start = timezone.now()
    horizon = start + timezone.timedelta(days=max(1, int(days)))

    # Built on the dispatcher's own joined queryset so the phone and the office
    # cannot disagree about what an order IS. The window is the day (or week)
    # ahead; an order whose window opened earlier and is still open stays on the
    # list, because a technician running late has not lost the job.
    qs = (
        metering_seam.dispatch_queryset()
        .filter(assignee_technician_id=technician.id)
        # ⚠ **A JOB WITH NO VISIT BOOKED IS ALWAYS ON THE LIST (`DEF-WRK-9693`).**
        # This kept an unbooked job only when its DEADLINE fell inside the day
        # (or the week), so a Normal job — 72 hours — given out this morning
        # was on nobody's phone: assigned, and never seen. It now rides at the
        # END (the sort's NULLs-last leg) under the phone's *Unscheduled*
        # heading, whatever its deadline.
        .filter(Q(window_start__lt=horizon) | Q(window_start__isnull=True))
        # ⚠ **A CANCELLED JOB IS NOT ON THE DAY (`CR-187-BRC10` T-31).** The
        # dispatcher's cancel moves `dispatch_state` and leaves the assignee
        # and the open `state` alone, so this list went on showing it — and
        # the change feed now TOMBSTONES it, so a day read that still carried
        # it would put back on the handset what the delta had just taken off.
        .exclude(dispatch_state=metering_seam.dispatch_tokens().CANCELLED)
    )

    # ── THE SORT. `BR-WRK-035`. Do not add a priority leg. ───────────────────
    #
    # `window_start` first (the appointment), `due_at` second (the promise when
    # there is no appointment), `order_no` third — the tie-break that stops a
    # day list reshuffling itself between two syncs. NULLs last on both time
    # legs: a job with no time is not a job at midnight.
    orders = list(
        qs.order_by(
            work_dispatch_nulls_last("window_start"),
            work_dispatch_nulls_last("due_at"),
            "order_no",
        )
    )

    details = {
        row.work_order_id: row
        for row in models.WorkOrderDetail.objects.filter(
            tenant_id=tenant_id, work_order_id__in=[o.id for o in orders]
        )
    }
    tokens = metering_seam.dispatch_tokens()
    cards = [_job_card(order, details.get(order.id)) for order in orders]
    return {
        "technician": {
            # `US-WRK-040` TC-2 — *Today reads D. Ortiz*. A NAME, never an id.
            "name": _technician_name(technician),
            "van": technician.van,
            "status": technician.status,
            # FB-033 — when it took that value (the phone reads it back
            # through `GET work/mobile/availability`, `availability.current`).
            "status_since": technician.status_since.isoformat() if technician.status_since else None,
            # FB-023 F3 — `employee` | `contractor`, by the money read's own test.
            "employment": _employment(technician),
        },
        "jobs": cards,
        "count": len(cards),
        # `4 jobs · 2 done` — the header `WM-32` draws. Counted here because a
        # count built in the front end is a plural nobody can translate.
        "done": len([c for c in cards if c["dispatch_state"] == tokens.COMPLETE]),
        "empty_reason": None if cards else "no_jobs_today",
        # T-32 — hand this to `GET /work/mobile/changes?cursor=` and the next
        # refresh is a DELTA (R56). Opaque; stored per technician on the phone.
        "cursor": cursor,
    }


def _employment(technician: Any) -> str:
    """FB-023 F3 — what the phone stores to decide whether money is shown: the
    SAME test `money.money_read` withholds by (`money.employment_of`), so the
    handset and the server cannot disagree about who sees a balance."""
    from apps.work import money as work_money

    return work_money.employment_of(technician)


def _field_raise_details(order: Any, technician: Any) -> dict[str, Any]:
    """FB-028 — `raised_on_site` and `skill_advice` for the job's details."""
    from apps.work import advice
    from apps.work.field_order_models import WorkFieldRaise

    raised = WorkFieldRaise.objects.filter(tenant_id=_tenant_id(), work_order_id=order.id).exists()
    skill_id = order.template.skill_id if order.template_id else None
    seen = (
        advice.advice_for(technician=technician, skill_id=skill_id, on=advice.order_day(order))
        if technician is not None and skill_id
        else None
    )
    return {
        "raised_on_site": raised,
        # FB-028 — the job's unit, so a raise carried from this job can name it.
        "unit_id": str(order.unit_id) if getattr(order, "unit_id", None) else None,
        "skill_advice": (
            {"skill": seen["skill"], "has_skill": bool(seen["has_skill"])} if seen else None
        ),
    }


def _technician_name(technician: Any) -> str:
    """*D. Ortiz* — the display name off the login, never the uuid."""
    user = getattr(technician, "user", None)
    for attribute in ("display_name", "full_name", "name", "email"):
        value = getattr(user, attribute, None)
        if value:
            return str(value)
    return ""


def work_dispatch_nulls_last(field: str) -> Any:
    """`F(field).asc(nulls_last=True)` through the dispatcher's own helper, so
    the phone and `Work-007` sort NULLs the same way."""
    from apps.work import dispatch as work_dispatch

    return work_dispatch.models_f_nulls_last(field)


#: FB-030 (PO 2026-10-31, decision log *"a technician's history is the last
#: 14 days, kept on the phone"*): how far back a technician's own closed work
#: reaches — the first sync's refill and the closed-job reads below. There is
#: no server history beyond it.
HISTORY_DAYS = 14


def history_since(now: Any = None) -> Any:
    """The start of the 14-day history window."""
    return (now or timezone.now()) - timezone.timedelta(days=HISTORY_DAYS)


def _history_q(technician: Any, since: Any) -> Q:
    """FB-030 — a CLOSED job this technician owns: they held it at the close
    (the assignee; the close admits only the lead) or they logged crew time on
    it (`work_order_labour`, R8). Completed inside the window, nothing older."""
    from apps.work.connection_models import WO_COMPLETED
    from apps.work.field_order_models import WorkOrderLabour

    helped = WorkOrderLabour.objects.filter(
        tenant_id=_tenant_id(), technician_id=technician.id
    ).values("work_order_id")
    return Q(state=WO_COMPLETED, completed_at__gte=since) & (
        Q(assignee_technician_id=technician.id) | Q(id__in=helped)
    )


def _own_record_or_404(actor: Any, order_id: Any) -> Any:
    """FB-030 — the order, if it is this technician's job NOW or their CLOSED
    job of the last 14 days (`_history_q`); else the same 404 (HR-1). For the
    READS of a record only — every write keeps `_own_job_or_404`, so a helper
    reading their history can never close or change the job."""
    technician = technician_of(actor)
    if technician is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    order = metering_seam.work_order_row(order_id)
    if order is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    if order.assignee_technician_id == technician.id:
        return order
    from apps.work.connection_models import WorkOrder

    owned = WorkOrder.objects.filter(
        Q(pk=order.pk) & _history_q(technician, history_since()), tenant_id=_tenant_id()
    ).exists()
    if not owned:
        raise errors.deny_as_not_found("BR-TEN-003")
    return order


def require_own_record(actor: Any, order_id: Any) -> None:
    """`require_own_job` for the READ routes of a job's evidence: a field
    technician is admitted to their own job, or their own closed job of the
    last 14 days (FB-030). An office role is not narrowed."""
    if getattr(actor, "role", None) == core_permissions.FIELD_TECHNICIAN:
        _own_record_or_404(actor, order_id)


def _own_job_or_404(actor: Any, order_id: Any) -> Any:
    """The order, if it is THIS login's technician's job — else a 404 (HR-1)."""
    technician = technician_of(actor)
    if technician is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    order = metering_seam.work_order_row(order_id)
    if order is None or order.assignee_technician_id != technician.id:
        raise errors.deny_as_not_found("BR-TEN-003")
    return order


def require_own_job(actor: Any, order_id: Any) -> None:
    """`DEF-WRK-9593` — a field technician reaches a job's evidence routes for
    THEIR OWN job only; an office role is not narrowed here.

    Those routes (`/work-orders/{id}/readings…`, `…/attachments…`,
    `…/signature`, `…/close-readiness`) are shared with the office's Checklist
    tab, and they scope by TENANT. Admitting the technician to them
    (`core.permissions.FieldAppRole`) without this would let one technician
    read every colleague's photographs by probing ids — the second boundary
    `bundle` already draws, drawn the same way: a 404, never a 403.
    """
    if getattr(actor, "role", None) == core_permissions.FIELD_TECHNICIAN:
        _own_job_or_404(actor, order_id)


def bundle(actor: Any, order_id: Any) -> dict[str, Any]:
    """`GET /work/mobile/jobs/{id}` — everything one job needs, in ONE response.

    The order's six copies (through `checklist.checklist`, the same function the
    staff screen reads — `BR-WRK-008` and one evaluator), the customer's contact
    for a tap-to-call, and the help documents as pre-signed links the phone
    downloads at sync.

    ⚠ **IT IS THE ASSIGNEE'S JOB OR IT IS A 404.** `US-WRK-042` TC-6 asks for a
    404 on another tenant's bundle, which the tenant filter already gives; this
    adds the second boundary — another TECHNICIAN's job in the same tenant. A
    404 rather than a 403 for both, because a 403 confirms the order exists
    (HR-1), and a technician has no business learning which jobs their colleague
    is carrying by probing ids.
    """
    # FB-030 — the record of a closed job of the last 14 days is the
    # technician's too (a helper's, or a job refilled onto a new phone).
    order = _own_record_or_404(actor, order_id)

    # The SAME function the staff Checklist tab reads. Not a second assembly of
    # the same six tables: two readers of one checklist that could disagree is
    # exactly what `BR-WRK-037`'s one-evaluator rule is about, one level up.
    pack = work_checklist.checklist(order.id)
    pack["help"] = [_help_row(row, order.id) for row in pack["help"]]
    pack["customer"] = _customer_contact(order)
    # FB-023 — the account the job's money is read for (the job's own, else
    # the one in force on its unit; `money.account_id_of`). The phone keeps it
    # beside the job; the money itself is still read PER JOB, never by this id.
    from apps.work import money as work_money

    pack["account_id"] = work_money.account_id_of(order)
    # FB-028 (PO 2026-10-31) — a job RAISED ON SITE gates its own reconnect and
    # disconnect steps on the phone, and W3 = C: the phone warns before Start
    # when the technician lacks the template's skill. Both ride in `details`,
    # which the handset already keeps whole on the job (`setDetails`).
    if pack.get("details") is not None:
        pack["details"] = {**pack["details"], **_field_raise_details(order, technician_of(actor))}
    pack["card"] = _job_card(
        order,
        models.WorkOrderDetail.objects.filter(
            tenant_id=_tenant_id(), work_order_id=order.id
        ).first(),
    )
    # CR-168-BRC10 §F (lane FIELD-2) — whether THIS technician has accepted the
    # job. The phone needs it to offer *Accept job*: an item captured before
    # acceptance is HELD for review (`BR-WRK-059`), so a screen that could not
    # see the answer would quietly send a day's work to the office's review list.
    from apps.work import dispatch as work_dispatch

    pack["technician_acceptance"] = work_dispatch._technician_acceptance(order)
    # `DEF-MET-10609` (decision log 2026-10-26) — the ONE can't-read list, so
    # *Unable to read* on a job reading offers the same reasons as a route
    # reading, offline. The phone keeps it where RW-17 already reads it.
    from apps.work.seams import metering_seam

    pack["cant_read_reasons"] = metering_seam.active_cant_read_reasons()
    # FB-030 — a CLOSED job carries its record, so a refilled phone shows the
    # debrief, the signer and the photographs (loaded on tap, never stored).
    pack["record"] = _closed_record(order)
    return pack


def _closed_record(order: Any) -> dict[str, Any] | None:
    """FB-030 — what FF-35's record shows beyond the checklist: the debrief the
    close carried (`field_data`), who signed or refused and when, and the job's
    photographs by the phone's own id. None for an open job.

    ⚠ NO MONEY AND NO SPEED FIGURES (PO 2026-10-31, coordinator judgment (5)):
    no balance, no labour minutes, no cost — the record is what was done."""
    from apps.work.connection_models import WO_COMPLETED
    from apps.work.evidence_models import WorkOrderSignature, WorkPhotoLink

    if order.state != WO_COMPLETED:
        return None
    data = order.field_data if isinstance(order.field_data, dict) else {}
    sig = WorkOrderSignature.objects.filter(tenant_id=_tenant_id(), work_order_id=order.id).first()
    photos = WorkPhotoLink.objects.filter(tenant_id=_tenant_id(), work_order_id=order.id).order_by(
        "taken_at", "created_at", "id"
    )
    return {
        "completed_at": order.completed_at.isoformat() if order.completed_at else None,
        "outcome": order.outcome,
        "problem": str(data.get("problem_found") or ""),
        "done": str(data.get("what_i_did") or ""),
        "signature": (
            {
                "kind": "refused" if sig.refused else "signed",
                "name": sig.printed_name or "",
                "reason": sig.decline_reason or "",
                "at": sig.signed_at.isoformat() if sig.signed_at else None,
            }
            if sig is not None
            else None
        ),
        "photos": [
            {
                "photo_id": str(p.photo_id),
                "task_id": str(p.task_id) if p.task_id else None,
                "reading_id": str(p.reading_id) if p.reading_id else None,
                "taken_at": p.taken_at.isoformat() if p.taken_at else None,
            }
            for p in photos
        ],
    }


def photo_content(actor: Any, photo_id: Any) -> tuple[bytes, str]:
    """`GET work/mobile/photos/{photo_id}/content` — FB-030: a job photograph's
    bytes, for a record whose file has left the phone (3 days after the close).

    OWN WORK ONLY: the photo's job must be this technician's job or their
    closed job of the last 14 days (`_own_record_or_404`) — another
    technician's photo is the same 404 as one that does not exist (HR-1).
    Served through the API with the caller's credential, `private, no-store`:
    nothing that outlives the request leaves the server, and the phone shows
    it without keeping it."""
    from apps.tenancy import document_store
    from apps.work.evidence_models import WorkOrderAttachment, WorkPhotoLink

    link = WorkPhotoLink.objects.filter(tenant_id=_tenant_id(), photo_id=photo_id).first()
    if link is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    require_own_record(actor, link.work_order_id)
    if link.attachment_id:
        attachment = WorkOrderAttachment.objects.filter(
            tenant_id=_tenant_id(), id=link.attachment_id
        ).first()
        if attachment is not None:
            ref = document_store.reference(attachment.document_id)
            return document_store.fetch(attachment.document_id), ref.content_type
    if link.staged:
        return bytes(link.staged), link.content_type or "image/jpeg"
    raise errors.deny_as_not_found("BR-TEN-003")


def _help_document(ref: Any) -> Any | None:
    """FB-031 — the stored help FILE a document row's `ref` names, or None.

    Only a `work_template_help` document resolves: a label typed before uploads
    existed (*SOP-W-12*), an empty row (the starter pack's), another kind of
    document and another tenant's id all read as no file (hard rule 1)."""
    from apps.tenancy import document_models, document_store

    if not ref:
        return None
    try:
        found = document_store.reference(str(ref))
    except Exception:  # noqa: BLE001 — not a stored id at all reads as no file
        return None
    if found.kind != document_models.KIND_WORK_TEMPLATE_HELP:
        return None
    return found


def help_content_path(order_id: Any, help_id: Any) -> str:
    """FB-031 — where the phone fetches a help document's bytes: our own API,
    with the technician's credential, own job only. Never expires, unlike the
    four-hour storage link `url` still carries for older phones."""
    return f"/work/mobile/jobs/{order_id}/help/{help_id}/content"


def _help_row(row: dict[str, Any], order_id: Any = None) -> dict[str, Any]:
    """One help entry, with a link where it is a document.

    ⚠ **A DOCUMENT THAT CANNOT BE RESOLVED IS LISTED WITHOUT A LINK, NEVER
    DROPPED** — `US-WRK-042` TC-4's shape: *"the job still opens; nothing
    silently dropped"*. A missing SOP the technician can SEE is missing is a
    phone call to the supervisor; an SOP that quietly is not on the list is a
    technician improvising in a basement.

    FB-031 (`DEF-FLD-10805`, decision log 2026-10-31): a document row also says
    whether there IS a file — `has_file`, with its `file_name`, `file_bytes`
    and `content_type` — and where the phone fetches it (`content_path`, our
    own route). `has_file: false` is *No file attached.* on the phone, never
    *Downloads at next sync*. `url` stays the four-hour storage link so a phone
    built before this keeps working.
    """
    if row.get("kind") == "link" and row.get("ref"):
        # Ruling 6 (24 Sep, `CR-168-BRC10` P3.25) — a video or web link is its
        # own `https` address; it needs a signal and the phone says so.
        return {**row, "url": row["ref"]}
    if row.get("kind") != "document":
        return {**row, "url": None}
    found = _help_document(row.get("ref"))
    if found is None:
        return {**row, "url": None, "has_file": False, "content_path": None}
    from apps.tenancy import document_store

    out = {
        **row,
        "has_file": True,
        "file_name": found.display_name,
        "file_bytes": found.byte_length,
        "content_type": found.content_type,
        "content_path": help_content_path(order_id, row["id"]) if order_id and row.get("id") else None,
    }
    try:
        return {**out, "url": document_store.download_url(row["ref"])}
    except Exception as exc:  # noqa: BLE001 — the row survives; see the docstring
        logger.warning("work.mobile: help document %s has no link: %r", row.get("ref"), exc)
        return {**out, "url": None}


def help_content(actor: Any, order_id: Any, help_id: Any) -> tuple[bytes, str, str]:
    """`GET /work/mobile/jobs/{id}/help/{help_id}/content` — FB-031.

    The bytes of ONE help document on the caller's OWN job: another
    technician's job, another tenant's, a help row that is not a document and
    a document row with no stored file are all the same 404 as the bundle's
    (HR-1)."""
    from apps.tenancy import document_store

    order = _own_job_or_404(actor, order_id)
    row = models.WorkOrderHelp.objects.filter(
        tenant_id=_tenant_id(), work_order_id=order.id, id=help_id,
        kind=models.HELP_KIND_DOCUMENT,
    ).first()
    found = _help_document(row.ref) if row is not None else None
    if found is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return document_store.fetch(found.id), found.content_type, found.display_name


def _unit_id_of(order: Any) -> Any:
    """The unit a job stands on, or None. The asset → unit walk is P2.20's
    (SRV-2, round 3); until it lands an asset-only job names no customer."""
    return getattr(order, "unit_id", None)


def _customer_contact(order: Any) -> dict[str, Any] | None:
    """*Miller, Sarah · (512) 555-0114* — `US-WRK-042` TC-5.

    ⚠ **READ THROUGH THE SEAM, NEVER COPIED ONTO THE ORDER.** The story says so
    in its own words — *"the number is the account's contact via
    `customers_seam`, never typed onto the order"* — and the reason is that a
    phone number is the one thing on this screen that must be CURRENT. The six
    copy tables freeze what the job involves (`BR-WRK-008`); who to ring is not
    part of that and would be a stale number in a customer's driveway.
    """
    # `CR-168-BRC10` P1.15: the job's own account, else the account in force
    # on its unit (a job raised on the unit or the premises names none).
    account = customers_seam.account(order.account_id) if order.account_id else None
    if account is None:
        account = customers_seam.current_account_for_unit(_unit_id_of(order))
    if account is None:
        return None
    return {
        "name": account.get("name") or account.get("display_name"),
        "phone": account.get("phone"),
        "account_no": account.get("account_no"),
        "customer_no": account.get("customer_no"),
    }


def register_device(
    actor: Any, payload: dict[str, Any], *, credential_device_uid: str | None = None
) -> dict[str, Any]:
    """`POST /work/mobile/devices` — the phone says where to push to.

    ⚠ **TWO SHAPES FROM 2026-10-21 (`CR-187-BRC10`), THE FIRST UNCHANGED.**
    Without a device id this is exactly the web field app's push-token
    registration below. With one — from the native app's bearer credential, or
    `device_id` in the body — it registers the HANDSET by name, push token
    optional (`_register_handset`).

    ⚠ **RE-REGISTERING THE SAME TOKEN UPDATES THE ROW; IT DOES NOT ADD ONE.**
    The unique index `(tenant_id, token)` is the guarantee, and this is the
    friendly path to it: a service worker re-subscribes on every install, on
    every browser update and whenever a push subscription rotates, so *register*
    is a thing that happens dozens of times per handset. Two rows for one phone
    would push the same job twice.

    ⚠ **THE TOKEN IS NEVER RETURNED.** The answer carries the device id and the
    last four characters, which is enough for a technician to recognise their
    own phone in a list and useless to anybody who intercepts it. See the
    model's docstring.

    ⚠ **A LOGIN WITH NO TECHNICIAN PROFILE IS REFUSED, NOT SILENTLY IGNORED.**
    This is a WRITE, unlike `today`: a clerk's browser registering a device
    would create a row nothing can ever push to and that nobody would find. The
    refusal is a 404 on the profile, the same answer as any other absent thing.
    """
    technician = technician_of(actor)
    if technician is None:
        raise errors.deny_as_not_found("BR-TEN-003")

    # `CR-187-BRC10` — the native app registers a HANDSET (by its own id and a
    # name), with or without a push token. The id comes from the bearer
    # credential when there is one (`R127`: never from the body when the
    # credential can say it); a cookie caller may name it in the body.
    device_uid = str(credential_device_uid or payload.get("device_id") or "").strip()
    if device_uid:
        return _register_handset(actor, technician, device_uid, payload)

    token = str(payload.get("token") or "").strip()
    if not token:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="work.mobile.device_token_required",
            br_ref="BR-WRK-034",
            params={"field": "token"},
        )
    platform = str(payload.get("platform") or models.TechnicianDevice.PLATFORM_WEB).strip()
    if platform not in models.TechnicianDevice.PLATFORMS:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="work.mobile.device_platform_unknown",
            br_ref="BR-WRK-034",
            params={"platform": platform or "—"},
        )

    with transaction.atomic():
        device, created = models.TechnicianDevice.objects.update_or_create(
            tenant_id=_tenant_id(),
            token=token,
            defaults={
                "technician_id": technician.id,
                "platform": platform,
                "label": str(payload.get("label") or "").strip(),
                "active": True,
                "last_seen_at": timezone.now(),
            },
        )
        # Hard rule 7 — a device is how a customer's address reaches a handset,
        # so registering one is an act worth a row. The token is NOT in it.
        core_audit.write_row(
            action="work.device_registered" if created else "work.device_refreshed",
            entity_type="technician",
            entity_id=technician.id,
            actor_user_id=_actor_id(actor),
            after={"device_id": str(device.id), "platform": platform, "last_four": token[-4:]},
        )
    return {
        "device_id": str(device.id),
        "platform": device.platform,
        "label": device.label,
        "active": device.active,
        # NEVER the token. Four characters so a technician can tell two of their
        # own handsets apart, and nothing more.
        "last_four": token[-4:],
        "created": created,
    }


# ══════════════════════════════════════════════════════════════════════════
# CR-187-BRC10 · THE NATIVE APP'S HANDSET REGISTRY (Security §4, R115)
# HUMAN-REVIEW-PENDING — 🔒 auth, AI-authored 2026-10-21; ledger row owed by
# the coordinator.
# ══════════════════════════════════════════════════════════════════════════
DEVICE_NAME_CHARS = 80


def _device_row(device: Any) -> dict[str, Any]:
    """One registration as a list row. NEVER the push token — four characters
    of it at most, so a technician can tell two handsets apart."""
    return {
        "device_id": str(device.id),
        "device_uid": device.device_uid,
        "name": device.label,
        "platform": device.platform,
        "active": device.active,
        "signed_out": device.signed_out_at is not None,
        "signed_out_at": device.signed_out_at.isoformat() if device.signed_out_at else None,
        "push_registered": bool(device.token),
        "last_four": device.token[-4:] if device.token else None,
        "registered_at": device.registered_at.isoformat() if device.registered_at else None,
        "last_seen_at": device.last_seen_at.isoformat() if device.last_seen_at else None,
    }


def _register_handset(
    actor: Any, technician: Any, device_uid: str, payload: dict[str, Any]
) -> dict[str, Any]:
    """Register THIS technician on THIS handset, by name, push token optional.

    ⚠ **ONE ROW PER (HANDSET, TECHNICIAN).** Marco signing in on the tablet Dana
    used adds HIS row and leaves hers, so the capture credential bound to her
    row still verifies when her unsent items go up (`BR-WRK-060`, `R132`).

    ⚠ **A PUSH TOKEN FOLLOWS THE SIGNED-IN TECHNICIAN** (`BR-WRK-059`): giving
    it here takes it off every other row in the utility, so the tablet rings
    for Marco's jobs and no longer for Dana's.

    ⚠ **REGISTERING AGAIN AFTER A REMOTE SIGN-OUT CLEARS THE SIGN-OUT, AND
    ONLY THAT.** The person has just signed in with a password to get here.
    `capture_epoch` is NOT reset, so a capture credential minted before the
    sign-out still names the old epoch and its items are still held."""
    if len(device_uid) > 200:
        raise errors.ValidationError(
            errors.VAL_RANGE,
            field_errors=[{"field": "device_id", "code": errors.VAL_RANGE, "params": {}}],
        )
    name = str(payload.get("name") or payload.get("label") or "").strip()[:DEVICE_NAME_CHARS]
    push = str(payload.get("push_token") or payload.get("token") or "").strip() or None
    platform = str(payload.get("platform") or models.TechnicianDevice.PLATFORM_WEB).strip()
    if platform not in models.TechnicianDevice.PLATFORMS:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="work.mobile.device_platform_unknown",
            br_ref="BR-WRK-034",
            params={"platform": platform or "—"},
        )
    now = timezone.now()
    tenant_id = _tenant_id()
    with transaction.atomic():
        row = models.TechnicianDevice.objects.filter(
            tenant_id=tenant_id, device_uid=device_uid, technician_id=technician.id
        ).first()
        if push:
            released = models.TechnicianDevice.objects.filter(tenant_id=tenant_id, token=push)
            if row is not None:
                released = released.exclude(pk=row.pk)
            released.update(token=None)
        created = row is None
        if created:
            row = models.TechnicianDevice.objects.create(
                tenant_id=tenant_id,
                technician_id=technician.id,
                device_uid=device_uid,
                token=push,
                platform=platform,
                label=name,
                active=True,
                last_seen_at=now,
            )
        else:
            row.platform = platform
            if name:
                row.label = name
            if push:
                row.token = push
            row.active = True
            row.signed_out_at = None
            row.signed_out_by = None
            row.last_seen_at = now
            row.save(
                update_fields=[
                    "platform",
                    "label",
                    "token",
                    "active",
                    "signed_out_at",
                    "signed_out_by",
                    "last_seen_at",
                    "updated_at",
                ]
            )
        core_audit.write_row(
            action="work.device_registered" if created else "work.device_refreshed",
            entity_type="technician",
            entity_id=technician.id,
            actor_user_id=_actor_id(actor),
            after={
                "device_id": str(row.id),
                "device": device_uid[-6:],
                "name": row.label,
                "push": bool(row.token),
            },
        )
    return {**_device_row(row), "created": created}


def release_push_on_sign_out(*, tenant_id: Any, user_id: Any, device_uid: str) -> int:
    """`DEF-WRK-10352` — a technician signed out of the native app on THIS
    handset: take the push token off their registration of it, so the phone
    stops ringing for this utility's jobs — for them (signed into another
    utility now) and for whoever picks the handset up next.

    Called by identity's `native.sign_out_native` through
    `identity/seams/work_seam.py` — a SERVICE call into work, the door
    `BR-WRK-002` sanctions (the mirror of `identity_seam.revoke_device_tokens`).
    Identity never writes this table.

    ⚠ **ONLY `token` IS CLEARED. THE ROW, `active`, `device_uid` AND
    `capture_epoch` STAY**, because the capture credential is bound to this
    row and unsent work captured under it must still verify when it goes up
    (`BR-WRK-060`, `R132`). Registering again after the next sign-in puts a
    token back (`_register_handset`). Only this login's row of this handset in
    this utility moves: another technician's row on a shared tablet, and any
    other utility's rows, are untouched (RLS FORCE underneath the filter).
    Answers the number of rows cleared; audited when it is not zero."""
    uid = str(device_uid or "").strip()
    if not uid:
        return 0
    with transaction.atomic():
        rows = list(
            models.TechnicianDevice.objects.filter(
                tenant_id=tenant_id,
                device_uid=uid,
                technician__user_id=user_id,
                token__isnull=False,
            ).values_list("id", "technician_id")
        )
        if not rows:
            return 0
        cleared = models.TechnicianDevice.objects.filter(pk__in=[r[0] for r in rows]).update(
            token=None
        )
        for row_id, technician_id in rows:
            core_audit.write_row(
                action="work.device_push_released",
                entity_type="technician",
                entity_id=technician_id,
                actor_user_id=user_id,
                after={"device_id": str(row_id), "device": uid[-6:], "reason": "signed_out"},
            )
    return cleared


def devices_page(technician_id: Any, *, page: int, per: int) -> tuple[list[dict[str, Any]], int]:
    """A technician's registrations, newest first, paged (`NFR-3`). The office
    sees every handset a technician uses (Security §4)."""
    qs = models.TechnicianDevice.objects.filter(
        tenant_id=_tenant_id(), technician_id=technician_id
    ).order_by("-registered_at", "-id")
    total = qs.count()
    start = (max(page, 1) - 1) * per
    return [_device_row(d) for d in qs[start : start + per]], total


def remote_sign_out(actor: Any, technician_id: Any, device_row_id: Any) -> dict[str, Any]:
    """The office signs a handset out (`R115`, Security §4).

    ⚠ **IT SIGNS OUT THE HANDSET, NOT ONE PERSON ON IT.** A lost tablet is lost
    for everybody who used it, so every registration of the same `device_uid`
    is marked, its `capture_epoch` bumped, and identity revokes every live
    token of that handset with reason `device_signed_out` — which is what the
    phone is told on its next contact (401, `params.reason`).

    ⚠ **NOTHING CAPTURED IS THROWN AWAY.** Items stamped with a capture
    credential from before the sign-out are HELD for the office's review when
    they arrive, never refused and never dropped (`R113`: *"there is no state in
    which captured work is thrown away to resolve an auth problem"*).

    A registration of another technician, or another tenant, is a 404."""
    from apps.work.seams import identity_seam

    row = models.TechnicianDevice.objects.filter(
        tenant_id=_tenant_id(), technician_id=technician_id, pk=device_row_id
    ).first()
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    now = timezone.now()
    actor_id = _actor_id(actor)
    with transaction.atomic():
        if row.device_uid:
            siblings = models.TechnicianDevice.objects.filter(
                tenant_id=_tenant_id(), device_uid=row.device_uid
            )
        else:
            siblings = models.TechnicianDevice.objects.filter(pk=row.pk)
        affected = 0
        for device in siblings.select_for_update():
            device.signed_out_at = now
            device.signed_out_by = actor_id
            device.active = False
            device.capture_epoch = device.capture_epoch + 1
            device.save(
                update_fields=[
                    "signed_out_at",
                    "signed_out_by",
                    "active",
                    "capture_epoch",
                    "updated_at",
                ]
            )
            affected += 1
        revoked = (
            identity_seam.revoke_device_tokens(row.device_uid, actor_id) if row.device_uid else 0
        )
        core_audit.write_row(
            action="work.device_signed_out",
            entity_type="technician",
            entity_id=technician_id,
            actor_user_id=actor_id,
            after={
                "device_id": str(row.id),
                "device": (row.device_uid or "")[-6:],
                "registrations": affected,
                "tokens_revoked": revoked,
            },
        )
    row.refresh_from_db()
    return {**_device_row(row), "registrations_signed_out": affected, "tokens_revoked": revoked}


def device_for_capture(technician: Any, device_uid: str) -> Any | None:
    """This technician's live registration of this handset, or None."""
    return models.TechnicianDevice.objects.filter(
        tenant_id=_tenant_id(),
        technician_id=technician.id,
        device_uid=device_uid,
        signed_out_at__isnull=True,
    ).first()


__all__ = [
    "WEEK_DAYS",
    "bundle",
    "devices_page",
    "register_device",
    "remote_sign_out",
    "technician_of",
    "today",
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-041@386432ab — US-WRK-040/041/042 (EP-WRK-08) + US-WRK-030 (EP-WRK-05) · 07-endpoints.md §6 #88/#89/#91 · 10-execution-plan.md wave J task J1
# ⚠ AMENDED 2026-10-21 (CR-187-BRC10 lane S-SYNC, T-31/T-32): the change feed's tombstones and its per-table cursor, the day read's cursor and its cancelled exclusion — tests/test_cr187_sync_feed.py (SQLite) · tests/test_cr187_sync_feed_pg.py (PostgreSQL). The packet line above lacked its `@<hash>` (G1) until this amendment; the hash is `05-user-stories.md` at the amending commit's parent.
# generated: 2026-09-05 by the CR-070 wave J build lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a(no 🔒 path — the migrations are, and carry their own markers)
# gates: pytest tests/test_us_wrk_04{1,2}*.py tests/test_us_wrk_030_push.py · G78 (Work writes nothing foreign)
# exceptions: the offline marker is NOT computed here and cannot be — it is the time the PHONE last reached the server; see the module docstring
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────


# ══════════════════════════════════════════════════════════════════════════
# CR-168-BRC10 §F — THE TECHNICIAN API's THREE MISSING ACTS (PO 2026-10-04:
# *"you should create apis for techncian app and use those apis wth payload to
# complete the jobs"*). Accept, decline, and on the way / on site. Everything
# else a technician does already had a route (`04-docs/03-contracts/
# technician-api.md` lists them); these three were the gaps.
# ══════════════════════════════════════════════════════════════════════════
#: The two dispatch acts the person holding the job may record themselves.
#: Assign, unassign and schedule are the DISPATCHER's (`BR-WRK-025`) and are
#: refused here by name.
FIELD_ACTS: tuple[str, ...] = ("depart", "arrive")


def _refuse_if_finished(order: Any) -> None:
    if order.state == "completed" or order.dispatch_state == "cancelled":
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-MET-110",
            message_key="work.mobile.job_finished",
            params={"order_no": order.order_no or ""},
        )


def accept_job(actor: Any, order_id: Any) -> dict[str, Any]:
    """`POST /work/mobile/jobs/{id}/accept` — *I'll take it* (P0.2, P4.7).

    Stamps `accepted_by_technician` and `accepted_at_technician`, which the
    dispatcher's board already reads (`dispatch._technician_acceptance`) and
    nothing wrote. **Idempotent**: a second accept answers the first stamp
    unchanged. A job already DECLINED is refused — the dispatcher has been told
    *no* and may already be giving it to someone else; taking it back is a
    conversation, not a tap. Hard rule 7: audited as
    `work.order.technician_accepted` (the Audit tab's `accepted_by_technician`).
    """
    order = _own_job_or_404(actor, order_id)
    technician = technician_of(actor)
    _refuse_if_finished(order)
    if order.declined_at is not None:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-WRK-025",
            message_key="work.mobile.job_already_declined",
            params={"order_no": order.order_no or ""},
        )
    if order.accepted_at_technician is None:
        with transaction.atomic():
            order.accepted_by_technician_id = technician.id
            order.accepted_at_technician = timezone.now()
            metering_seam.save_order_fields(
                order, ["accepted_by_technician", "accepted_at_technician"]
            )
            core_audit.write_row(
                action="work.order.technician_accepted",
                entity_type="work_order",
                entity_id=order.id,
                actor_user_id=_actor_id(actor),
                before={"accepted_at_technician": None},
                after={
                    "order_no": order.order_no,
                    "accepted_at_technician": order.accepted_at_technician.isoformat(),
                },
            )
    return _acceptance_answer(order)


def decline_job(actor: Any, order_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`POST /work/mobile/jobs/{id}/decline` — *I can't take it*, WITH A REASON.

    `{reason}` is required: a dispatcher told *no* without a why cannot decide
    whether to wait or reassign. The job STAYS with the technician — moving it
    is the dispatcher's act (`BR-WRK-025`), and the board shows *declined*
    beside the name. A job already accepted cannot be declined here; that is a
    send-back, which is the office's (P4.14).
    """
    order = _own_job_or_404(actor, order_id)
    _refuse_if_finished(order)
    reason = str((payload or {}).get("reason") or "").strip()
    if not reason:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            br_ref="BR-WRK-025",
            message_key="work.mobile.decline_reason_required",
        )
    # `DEF-FLD-10579` — the phone's *Other* carries a note; stored with the
    # reason exactly as hand-back stores its (`field_dispatch.hand_back`:
    # *reason — note*), so the board reads one line either way.
    note = str((payload or {}).get("note") or "").strip() or None
    if note is not None:
        reason = f"{reason} — {note}"
    if order.accepted_at_technician is not None:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-WRK-025",
            message_key="work.mobile.job_already_accepted",
            params={"order_no": order.order_no or ""},
        )
    if order.declined_at is None:
        with transaction.atomic():
            order.declined_at = timezone.now()
            order.declined_reason = reason
            metering_seam.save_order_fields(order, ["declined_at", "declined_reason"])
            core_audit.write_row(
                action="work.order.technician_declined",
                entity_type="work_order",
                entity_id=order.id,
                actor_user_id=_actor_id(actor),
                before={"declined_at": None},
                after={"order_no": order.order_no, "reason": reason},
            )
        # P6.2 (lane SRV-5) — the office is told, once, after the commit.
        from apps.work import visit_notices

        visit_notices.tell_office(order, "declined", discriminator=order.declined_at.isoformat())
    return _acceptance_answer(order)


def _acceptance_answer(order: Any) -> dict[str, Any]:
    from apps.work import dispatch as work_dispatch

    return {
        "order_id": str(order.id),
        "order_no": order.order_no,
        "technician_acceptance": work_dispatch._technician_acceptance(order),
    }


def field_act(actor: Any, order_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`POST /work/mobile/jobs/{id}/acts` — `{act: depart | arrive, key?}`: on
    the way, on site. The SAME append-only row the dispatcher's door writes
    (`dispatch.record_act`, `BR-WRK-025`), recorded by the person doing it.

    `arrive` matters beyond the board: the labour minutes are the close minus
    the LAST arrival (`BR-WRK-020`), so a job with no arrival carries no labour
    line at all. A declined or finished job is refused; any other act word is
    refused by name, because assigning and scheduling are the dispatcher's.
    """
    from django.db import IntegrityError

    from apps.work import dispatch as work_dispatch

    # ── `CR-187-BRC10` (lane S-GAPS) · IDEMPOTENT ON THE OUTBOX KEY ─────────
    # `07-endpoints.md` §0 rule 7. A resend after a lost answer finds the row
    # its first send appended and answers *duplicate* — BEFORE any state
    # check, because the job may have moved on since (arrived, closed, handed
    # back) and the act it asks for is already recorded. The key is the
    # caller's own: one recorded by somebody else, or on another job, is the
    # not-found an absent job gets (HR-1), never a hint that it exists.
    key = str((payload or {}).get("key") or "").strip() or None
    if key is not None:
        seen = assignment_by_key(key)
        if seen is not None:
            return _act_duplicate(actor, order_id, seen)

    order = _own_job_or_404(actor, order_id)
    _refuse_if_finished(order)
    act = str((payload or {}).get("act") or "").strip()
    if act not in FIELD_ACTS:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            br_ref="BR-WRK-025",
            message_key="work.mobile.act_not_a_field_act",
            params={"act": act or "—", "allowed": ", ".join(FIELD_ACTS)},
        )
    if order.declined_at is not None:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-WRK-025",
            message_key="work.mobile.job_already_declined",
            params={"order_no": order.order_no or ""},
        )
    try:
        # `record_act` writes the row inside its own `atomic()`, so a lost race
        # on `uq_work_order_assignments_key` rolls back that whole act — row,
        # cache and audit — and is caught HERE, outside it (hard-won law 14).
        answer = work_dispatch.record_act(actor, order.id, {"act": act}, key=key)
    except IntegrityError:
        seen = assignment_by_key(key) if key is not None else None
        if seen is None:
            raise
        return _act_duplicate(actor, order_id, seen)
    return {**answer, "duplicate": False}


def assignment_by_key(key: str) -> Any:
    """The assignment-history row a handset key already wrote, or None."""
    return models.WorkOrderAssignment.objects.filter(tenant_id=_tenant_id(), key=key).first()


def _act_duplicate(actor: Any, order_id: Any, seen: Any) -> dict[str, Any]:
    """*Duplicate* for a replayed act — or the not-found, when the key is not
    this caller's on this job (`07-endpoints.md` §0 rule 10)."""
    if str(seen.work_order_id) != str(order_id) or str(seen.actor_id) != str(_actor_id(actor)):
        raise errors.deny_as_not_found("BR-TEN-003")
    order = metering_seam.work_order_row(order_id)
    return {
        "assignment_id": str(seen.id),
        "order_no": getattr(order, "order_no", None),
        "act": seen.act,
        "dispatch_state": getattr(order, "dispatch_state", None),
        "at": seen.at.isoformat() if seen.at else None,
        "duplicate": True,
    }


def door_actor(session_actor: Any, payload: Any) -> Any:
    """**Who an own-door act is written as — `CR-187-BRC10` (lane S-GAPS).**

    The handset's crew-time, raise and hand-back items go through their own
    routes, not the job's sync batch, and until now those routes read no
    capture token: an item was answered as whoever was signed in, so the
    handset sent one only while its captor WAS the one signed in (Security
    §3). With `capture_token` in the body the act is the CAPTOR's, verified
    exactly as `sync._one_item` verifies an item (`captor_from_token`, the
    strict read): the session is only the courier (`BR-WRK-059`, PO
    2026-10-04 *"we are sending details as per login"*). Without one, the
    session — unchanged for every caller that sends none.

    ⚠ **AN EXPIRED OR SIGNED-OUT TOKEN IS REFUSED, NOT DOWNGRADED TO THE
    SESSION** (`work.mobile.capture_token_expired`, 403). Falling back would
    write the captor's act as the courier — the one thing the token exists
    to stop. The handset keeps the item and sends it once the captor has
    signed in again; its key then makes a repeat a duplicate.
    """
    token = (payload or {}).get("capture_token") if isinstance(payload, dict) else None
    if not token:
        return session_actor
    actor, _technician = captor_from_token(str(token))
    return actor


def without_capture_token(payload: Any) -> dict[str, Any]:
    """The body a service reads — the token is the door's, never the act's."""
    return {k: v for k, v in (payload or {}).items() if k != "capture_token"}


# ══════════════════════════════════════════════════════════════════════════
# BR-WRK-059 · ONE DEVICE, SEVERAL TECHNICIANS IN TURN — the CAPTURE TOKEN.
# PO 2026-10-04: *"same device first X tenchnican can login ; then he will log
# out ; then y technican can login … so we need to ensure we are sending
# details as per login and appoavel"*.
# ══════════════════════════════════════════════════════════════════════════
#: The signer's salt. A capture token is signed with the server's SECRET_KEY
#: and this salt, so a token minted for any other purpose cannot be replayed
#: here, and the handset cannot forge or edit one.
CAPTURE_TOKEN_SALT = "work.mobile.capture-token.v1"
#: The SEEDED life — 7 days, `BR-WRK-060`'s signed figure — kept as a name
#: because tests and docs quote it. **It is not the life a handset is given.**
#:
#: ⚠ **FROM 2026-10-21 THE LIFE IS THE UTILITY'S OWN SETTING** (PO, verbatim,
#: *"this should come from settings"* — decision log *"Field app: the PO
#: corrects four of the ten answers"* item 2). Settings → Security holds
#: `field_capture_hours` (seeded 168, choices 1 hour to 30 days,
#: `apps/identity/services.FIELD_CAPTURE_HOURS_CHOICES` says why those bounds),
#: and `capture_token_max_age_s()` reads it through the identity seam. It
#: replaced the process setting `WORK_CAPTURE_TOKEN_MAX_AGE_S`, which is GONE
#: rather than kept as an override: two sources for one life is how the admin's
#: screen and the handset come to disagree. The native refresh token reads the
#: same setting (`identity/native.refresh_token_max_age_s`).
#:
#: ⚠ **A TOKEN IS CHECKED AGAINST THE SETTING AS IT STANDS WHEN THE ITEM
#: ARRIVES, not as it stood when the token was minted.** So shortening the life
#: shortens tokens already on handsets (the safe direction, hard-won law 3) and
#: lengthening it lengthens them; `expires_at` in the mint's answer is the
#: phone's best figure at the time, and an item refused as expired is kept on
#: the phone and resent after a sign-in (`BR-WRK-063` as superseded 2026-10-21).
CAPTURE_TOKEN_MAX_AGE_S = 7 * 24 * 3600


def capture_token_max_age_s() -> int:
    """The capture credential's life in seconds — the utility's setting."""
    from apps.work.seams import identity_seam

    return identity_seam.field_capture_seconds()


def issue_capture_token(
    actor: Any,
    payload: dict[str, Any] | None = None,
    *,
    credential_device_uid: str | None = None,
) -> dict[str, Any]:
    """`POST /work/mobile/capture-token` — the signed identity a handset stamps
    on every item it captures while THIS technician is signed in.

    ⚠ **BOUND TO THE DEVICE REGISTRATION WHEN THERE IS ONE (`CR-187-BRC10`).**
    With a handset id — from the native app's bearer credential, or
    `device_id` in the body — the token also carries that technician's
    registration of that handset (`dv`) and its `capture_epoch` (`ep`), and
    `captor_from_token` checks both per item: an unknown registration is
    INVALID, a signed-out one is HELD (`R115`). A handset that is not
    registered is refused — register it first (`POST work/mobile/devices`).
    Without a handset id the token is exactly what the web field app has
    always had.

    ⚠ **WHY A TOKEN AND NOT THE SESSION.** The session is whoever is signed in
    when the batch is SENT. On a shared tablet X closes a job in a basement,
    signs out, and Y signs in upstairs where there is a signal — the batch
    then travels under Y's session. The item must still say X (`BR-WRK-059`),
    so the identity rides with the ITEM, minted while X was signed in.

    ⚠ **IT OUTLIVES SIGN-OUT ON PURPOSE — RULED 2026-10-04 (`BR-WRK-060`).**
    PO, verbatim: *"(a) Patel's work stays saved on the tablet under his name
    and uploads as soon as there's signal, even while Chen is signed in. Chen
    can't see or change it."* So the work stays bound to X, sends when online
    whoever is signed in, and Y can neither see nor change it (the token is
    signed against tampering). Sign-out is never blocked and never deletes.
    """
    technician = technician_of(actor)
    if technician is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    from django.core import signing

    device = str((payload or {}).get("device_label") or "").strip()[:80]
    claims = {
        "t": str(_tenant_id()),
        "u": str(_actor_id(actor)),
        "x": str(technician.id),
        "d": device,
    }
    device_uid = str(credential_device_uid or (payload or {}).get("device_id") or "").strip()
    registration = None
    if device_uid:
        registration = device_for_capture(technician, device_uid)
        if registration is None:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-WRK-059",
                message_key="work.mobile.device_token_required",
                params={"reason": "device_not_registered"},
            )
        claims["dv"] = str(registration.id)
        claims["ep"] = registration.capture_epoch
        claims["d"] = device or registration.label[:80]
    token = signing.dumps(claims, salt=CAPTURE_TOKEN_SALT)
    from datetime import timedelta

    from django.utils import timezone

    life = capture_token_max_age_s()
    answer = {
        "capture_token": token,
        "technician": {"name": _technician_name(technician)},
        # The utility's setting (PO 2026-10-21) — the phone renews before this
        # and shows the technician how long it may keep capturing offline.
        "max_age_seconds": life,
        "expires_at": (timezone.now() + timedelta(seconds=life)).isoformat(),
        "br_ref": "BR-WRK-059",
    }
    if registration is not None:
        answer["device"] = {"device_id": str(registration.id), "name": registration.label}
    return answer


def captor_from_token(token: str, *, allow_expired: bool = False) -> tuple[Any, Any]:
    """`(actor, technician)` for a capture token, or a refusal naming why.

    The actor is the CAPTOR's own login in the shape every service reads
    (`id`, `role`), so a tick, a photo or a close is written as X even when the
    request came in under Y's session.
    """
    from types import SimpleNamespace

    from django.core import signing

    try:
        data = signing.loads(
            str(token or ""),
            salt=CAPTURE_TOKEN_SALT,
            max_age=None if allow_expired else capture_token_max_age_s(),
        )
    except signing.SignatureExpired:
        raise errors.AuthError(
            errors.AUTH_PERMISSION_DENIED,
            br_ref="BR-WRK-059",
            message_key="work.mobile.capture_token_expired",
        ) from None
    except signing.BadSignature:
        raise errors.AuthError(
            errors.AUTH_PERMISSION_DENIED,
            br_ref="BR-WRK-059",
            message_key="work.mobile.capture_token_invalid",
        ) from None
    if str(data.get("t")) != str(_tenant_id()):
        # Another utility's token on this utility's path reads as invalid —
        # never as "belongs elsewhere" (HR-1).
        raise errors.AuthError(
            errors.AUTH_PERMISSION_DENIED,
            br_ref="BR-WRK-059",
            message_key="work.mobile.capture_token_invalid",
        )
    technician = models.Technician.objects.filter(
        tenant_id=_tenant_id(), pk=data.get("x"), user_id=data.get("u")
    ).first()
    if technician is None:
        raise errors.AuthError(
            errors.AUTH_PERMISSION_DENIED,
            br_ref="BR-WRK-059",
            message_key="work.mobile.capture_token_invalid",
        )
    if data.get("dv"):
        # ── `CR-187-BRC10` · the per-item check against the DEVICE ─────────
        # A registration that is not this technician's in this tenant is a
        # forgery-shaped answer: INVALID, refused. One the office has signed
        # out since the token was minted (`capture_epoch` moved) is treated
        # EXACTLY as an expired token: refused on the strict read, and on the
        # sync's second read (`allow_expired`) the captor is named and the item
        # is REFUSED BACK to the technician with `capture_token_expired` —
        # kept on the phone, never thrown away (`R113`, `R115`; PO 2026-10-21
        # *"back to the technician"*, which replaced *held for review*).
        registration = models.TechnicianDevice.objects.filter(
            tenant_id=_tenant_id(), pk=data.get("dv"), technician_id=technician.id
        ).first()
        if registration is None:
            raise errors.AuthError(
                errors.AUTH_PERMISSION_DENIED,
                br_ref="BR-WRK-059",
                message_key="work.mobile.capture_token_invalid",
            )
        signed_out = registration.signed_out_at is not None or registration.capture_epoch != data.get(
            "ep"
        )
        if signed_out and not allow_expired:
            raise errors.AuthError(
                errors.AUTH_PERMISSION_DENIED,
                br_ref="BR-WRK-059",
                message_key="work.mobile.capture_token_expired",
                params={"reason": "device_signed_out"},
            )
    return SimpleNamespace(id=technician.user_id, role=core_permissions.FIELD_TECHNICIAN), technician


def require_captor_holds_job(technician: Any, order_id: Any) -> Any:
    """`BR-WRK-059` — the captor must be the technician the job is ASSIGNED to
    AND who ACCEPTED it. Anyone else's item is refused, by name."""
    order = metering_seam.work_order_row(order_id)
    if order is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    if order.assignee_technician_id != technician.id:
        raise errors.AuthError(
            errors.AUTH_PERMISSION_DENIED,
            br_ref="BR-WRK-059",
            message_key="work.mobile.not_your_job",
            params={"order_no": order.order_no or ""},
        )
    if order.accepted_at_technician is None or order.accepted_by_technician_id != technician.id:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-WRK-059",
            message_key="work.mobile.accept_the_job_first",
            params={"order_no": order.order_no or ""},
        )
    return order


def capture_actor(session_actor: Any, order_id: Any, token: Any) -> Any:
    """The actor a multipart capture (a photograph, a signature) is written as.

    With a token: the captor, who must hold and have accepted the job — the
    session is only the courier. Without one: the session, scoped to its own
    job as before (`DEF-WRK-9593`).
    """
    if token:
        actor, technician = captor_from_token(token)
        require_captor_holds_job(technician, order_id)
        return actor
    require_own_job(session_actor, order_id)
    return session_actor


#: The phone's own cut: `MobileApp.tsx` labels a handset with
#: `navigator.userAgent.slice(0, 60)`, so the server's fallback is the same 60.
DEVICE_LABEL_CHARS = 60


def capture_device_label(token: Any, user_agent: Any = "") -> str:
    """**Which handset took this photograph — `DEF-WRK-4126`.**

    `work_order_attachments.device` was published, rendered and sent by no
    client, so it was always empty. The phone ALREADY names itself: it mints
    its capture token with `device_label` (`issue_capture_token`), and the
    token carried it as `d` — read by nothing. So, in order: the capture
    token's label (the CAPTOR's handset, `BR-WRK-059`, even when another login
    is the courier), then the request's own User-Agent cut to the phone's 60
    characters. Called only after `capture_actor` has verified the token, so a
    bad signature here just means no label. Never a key, never trusted — the
    column is free text a supervisor reads.
    """
    if token:
        from django.core import signing

        try:
            data = signing.loads(str(token), salt=CAPTURE_TOKEN_SALT, max_age=None)
        except signing.BadSignature:
            data = {}
        label = str((data or {}).get("d") or "").strip()
        if label:
            return label[:80]
    return str(user_agent or "").strip()[:DEVICE_LABEL_CHARS]


# ══════════════════════════════════════════════════════════════════════════
# BR-WRK-061 · LOCATION — lat, lng, accuracy_m, fix_at on an item.
# ══════════════════════════════════════════════════════════════════════════
def location_threshold_m() -> int:
    """The tenant's `work_settings.location_accuracy_m`, 50 m when no row."""
    row = models.WorkSettings.objects.filter(tenant_id=_tenant_id()).first()
    return int(row.location_accuracy_m) if row is not None else 50


def parse_location(raw: Any) -> dict[str, Any] | None:
    """A location block, validated, or None when the item carried none.

    `{lat, lng, accuracy_m, fix_at}` — all four, or the block is refused by
    name: a point with no accuracy cannot be judged precise or not, and a fix
    with no time cannot be told from a stale one.
    """
    from decimal import Decimal, InvalidOperation

    if raw in (None, "", {}):
        return None
    if not isinstance(raw, dict):
        raise errors.ValidationError(
            errors.VAL_FORMAT, br_ref="BR-WRK-061", message_key="work.mobile.location_malformed"
        )
    try:
        lat = Decimal(str(raw["lat"]))
        lng = Decimal(str(raw["lng"]))
        accuracy = Decimal(str(raw["accuracy_m"]))
        # FB-014 — the fix was timed by the phone's clock; onto the server's.
        fix_at = device_clock.correct(metering_seam.parse_moment(raw["fix_at"], field="location.fix_at"))
    except (KeyError, InvalidOperation, TypeError, ValueError):
        raise errors.ValidationError(
            errors.VAL_FORMAT, br_ref="BR-WRK-061", message_key="work.mobile.location_malformed"
        ) from None
    if not (-90 <= lat <= 90 and -180 <= lng <= 180) or accuracy < 0 or fix_at is None:
        raise errors.ValidationError(
            errors.VAL_RANGE, br_ref="BR-WRK-061", message_key="work.mobile.location_malformed"
        )
    return {
        "lat": lat.quantize(Decimal("0.000001")),
        "lng": lng.quantize(Decimal("0.000001")),
        "accuracy_m": accuracy.quantize(Decimal("0.1")),
        "fix_at": fix_at,
    }


def labour_time_record(arrived: Any, finished: Any) -> dict[str, Any] | None:
    """The two times the technician confirmed at the close — `DEF-WRK-4127`.

    PO 2026-10-05, verbatim: *"allow technicain to fill in time"*. The phone
    pre-fills *Arrived* and *Finished* from its own clock, the technician may
    correct either, and both travel on the close item in the offline batch.
    Labour is priced from finished − arrived (`services._minutes_on_site`), so
    an offline day no longer prices from the SYNC's clock.

    ⚠ **NEW DATA ON THE CLOSE, NEVER AN EDIT OF AN `arrive` ROW.**
    `work_order_assignments` is append-only (`BR-WRK-025`); the entered pair is
    stored with the close on the order's field data, server-written beside
    `close_location`, and the history keeps what it recorded.

    None when the close carries neither (an older phone: today's reading of the
    last arrival stands). Half a pair or a finish that is not after the arrival
    is REFUSED by name — the sync then holds the close for the office
    (TECHNICIAN SYNC DESIGN (2)) and no labour is priced from it.

    ⚠ **BOTH TIMES ARE SHIFTED ONTO THE SERVER'S CLOCK FIRST (FB-014, PO
    2026-10-28)** by the offset the request measured (`core/device_clock.py`):
    phone 12:07:30 against server 12:02:30 stores a 12:07 finish as 12:02, and
    the minutes do not move because both ends move together. This read *"a
    future time … is REFUSED"* until then; a future finish is now refused only
    on a send with no clock reading and more than 5 minutes ahead.
    """
    if arrived in (None, "") and finished in (None, ""):
        return None
    arrived_at = device_clock.correct(metering_seam.parse_moment(arrived, field="arrived_at"))
    finished_at = device_clock.correct(metering_seam.parse_moment(finished, field="finished_at"))
    if arrived_at is None or finished_at is None:
        raise errors.ValidationError(
            errors.VAL_REQUIRED, br_ref="BR-WRK-020", message_key="work.mobile.labour_time_incomplete"
        )
    if finished_at <= arrived_at or finished_at > timezone.now():
        raise errors.ValidationError(
            errors.VAL_RANGE, br_ref="BR-WRK-020", message_key="work.mobile.labour_time_out_of_order"
        )
    return {
        "arrived_at": arrived_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "minutes": int(round((finished_at - arrived_at).total_seconds() / 60)),
    }


def close_location_record(location: dict[str, Any] | None) -> dict[str, Any]:
    """What the close stores on the order's field data for the office.

    ⚠ **NOT PRECISE IS ACCEPTED AND FLAGGED, NEVER REFUSED — RULED 2026-10-04
    (`BR-WRK-061`).** PO, verbatim: *"(a) Allow the close, send the best fix
    with its accuracy, and show the office \"Location not precise\" when they
    accept."* The close carries its best fix and that fix's accuracy, with
    `precise: false` the office sees on the order it accepts. A close with NO
    fix at all is the same flag with `missing: true`.
    """
    threshold = location_threshold_m()
    if location is None:
        return {"missing": True, "precise": False, "threshold_m": threshold}
    return {
        "lat": str(location["lat"]),
        "lng": str(location["lng"]),
        "accuracy_m": str(location["accuracy_m"]),
        "fix_at": location["fix_at"].isoformat(),
        "precise": location["accuracy_m"] <= threshold,
        "threshold_m": threshold,
    }


def release_device(actor: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`DELETE /work/mobile/devices` — `{token}`: this technician is signing out
    of this handset, so pushes for them stop going to it (`BR-WRK-059`: *push
    follows the signed-in technician, not the device*). The next technician's
    `POST /work/mobile/devices` with the same token moves the row to them."""
    technician = technician_of(actor)
    token = str((payload or {}).get("token") or "").strip()
    if technician is None or not token:
        raise errors.ValidationError(
            errors.VAL_REQUIRED, br_ref="BR-WRK-059", message_key="work.mobile.device_token_required"
        )
    changed = models.TechnicianDevice.objects.filter(
        tenant_id=_tenant_id(), token=token, technician_id=technician.id, active=True
    ).update(active=False, last_seen_at=timezone.now())
    if changed:
        core_audit.write_row(
            action="work.device_released",
            entity_type="technician",
            entity_id=technician.id,
            actor_user_id=_actor_id(actor),
            after={"last_four": token[-4:]},
        )
    return {"released": bool(changed), "last_four": token[-4:]}


def state_reason_for(technician: Any, order_id: Any) -> str | None:
    """The `require_captor_holds_job` question answered as a REASON (a message
    key) rather than an exception, so the sync can answer it per item. Since
    2026-10-21 (PO, *"back to the technician"*) the sync REFUSES the item back
    with this reason; until then it stored and flagged it. None when the
    captor holds the job."""
    try:
        require_captor_holds_job(technician, order_id)
    except (errors.AuthError, errors.BizError) as exc:
        return getattr(exc, "message_key", None) or "work.mobile.not_your_job"
    return None


def order_state_reason(order_id: Any, kind: str) -> str | None:
    """The job moved on while the phone was offline — accepted by the office,
    cancelled, or already closed. A reason to send the item BACK to the
    technician (2026-10-21), never to drop it."""
    order = metering_seam.work_order_row(order_id)
    if order is None:
        return None
    if getattr(order, "accepted_by_id", None):
        return "work.sync.job_already_accepted"
    if order.dispatch_state == "cancelled":
        return "work.sync.job_cancelled"
    if order.state == "completed":
        return "work.sync.job_already_closed"
    return None

# TECHNICIAN SYNC DESIGN (3) — SERVER → PHONE BY CHANGE FEED, PAGED.
#
# ⚠ REWRITTEN BY `CR-187-BRC10` lane S-SYNC (T-31, T-32), AND THE REASON IS A
# TOMBSTONE THAT COULD NEVER FIRE. The feed read its removals as
# `WorkOrderAssignment(technician=me, act="unassign")` — and `append_act`
# writes every `unassign` row with `technician` NULL (the row says a job was
# taken OFF somebody, so it names no recipient; `models.WorkOrderAssignment`'s
# own field comment says so). The query matched NOTHING, ever: a reassigned job
# stayed on the old technician's handset for good, every test passed, and the
# screen looked right. Data.txt §6 names this exact bug — *"the single most
# common bug in offline sync and it is invisible in testing"* — and R57 is the
# rule. Two more ways out produced nothing either: a `schedule` act that names
# a different technician moves the job WITHOUT any `unassign` row, and a
# cancelled job (a dispatch-axis move, `set_dispatch_state`) never leaves the
# assignee column at all.
# ══════════════════════════════════════════════════════════════════════════

#: How far a watermark is wound BACK when the feed runs dry. A row's
#: `updated_at` / `at` is the moment Python stamped it, not the moment its
#: transaction COMMITTED, so a long transaction can make a row visible with a
#: timestamp older than a watermark already handed out — and a watermark that
#: has passed a row never sees it again. Rewinding the dry-feed watermark by
#: this much re-sends the last two minutes on the next refresh (an upsert and a
#: tombstone are both idempotent on the handset) and closes that hole for any
#: transaction shorter than it. A web worker is killed at sixty seconds
#: (`docker-entrypoint.sh`, `GUNICORN_TIMEOUT:-60`); twice that covers a
#: request transaction with room to spare.
FEED_SETTLE = timezone.timedelta(seconds=120)

#: The id half of a position wound back to a moment rather than to a row —
#: sorts before every real id at that instant.
_NIL_ID = "00000000-0000-0000-0000-000000000000"

#: The two tables the feed reads, each with its OWN watermark (T-32): one
#: merged position would make a row of one table skip a row of the other that
#: shared its timestamp.
_STREAM_ORDERS = "wo"
_STREAM_DEPARTURES = "as"


def _encode_cursor(at: Any, ident: str) -> str:
    """The LEGACY single-position cursor (`iso|id`). Kept so a cursor a
    client stored before `CR-187-BRC10` is still read; never minted now."""
    import base64

    raw = f"{at.isoformat()}|{ident}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _encode_feed_cursor(state: dict[str, Any]) -> str:
    """The per-table cursor: `{v: 2, wo: [iso, id] | null, as: [iso, id] |
    null, full: iso | null}`, base64url. OPAQUE to the phone — it stores it per
    technician (Data.txt `sync_state`) and sends it back unread."""
    import base64
    import json

    def pos(value: Any) -> Any:
        return None if value is None else [value[0].isoformat(), str(value[1])]

    body = {
        "v": 2,
        _STREAM_ORDERS: pos(state.get(_STREAM_ORDERS)),
        _STREAM_DEPARTURES: pos(state.get(_STREAM_DEPARTURES)),
        "full": state["full"].isoformat() if state.get("full") else None,
    }
    raw = json.dumps(body, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _cursor_malformed() -> errors.ValidationError:
    return errors.ValidationError(
        errors.VAL_FORMAT, br_ref="BR-WRK-063", message_key="work.mobile.cursor_malformed"
    )


def _decode_cursor(cursor: Any) -> dict[str, Any] | None:
    """Either cursor shape → `{wo, as, full}`, or None for no cursor.

    A LEGACY cursor (`iso|id`, one merged position) becomes the same position
    on BOTH tables, which is exactly what the old feed filtered on — so a
    client upgraded mid-week resumes where it was rather than re-downloading.
    """
    import base64
    import json
    from datetime import datetime
    from uuid import UUID

    if not cursor:
        return None
    try:
        text = str(cursor)
        raw = base64.urlsafe_b64decode(text + "=" * (-len(text) % 4)).decode()
        if raw.startswith("{"):
            body = json.loads(raw)
            if not isinstance(body, dict) or body.get("v") != 2:
                raise _cursor_malformed()

            def pos(value: Any) -> Any:
                if value is None:
                    return None
                at, ident = value
                return datetime.fromisoformat(at), str(UUID(str(ident)))

            full = body.get("full")
            return {
                _STREAM_ORDERS: pos(body.get(_STREAM_ORDERS)),
                _STREAM_DEPARTURES: pos(body.get(_STREAM_DEPARTURES)),
                "full": datetime.fromisoformat(full) if full else None,
            }
        at, ident = raw.split("|", 1)
        position = (datetime.fromisoformat(at), str(UUID(ident)))
        return {_STREAM_ORDERS: position, _STREAM_DEPARTURES: position, "full": None}
    except (ValueError, UnicodeDecodeError, TypeError, KeyError):
        raise _cursor_malformed() from None


def day_cursor() -> str:
    """The cursor a DAY READ hands out (T-32): both watermarks at *now* less
    the settle window, so the first refresh after `GET /work/mobile/today`
    answers only what changed since — the delta R56 asks for — and re-sends at
    most the last two minutes rather than missing a row still committing."""
    mark = (timezone.now() - FEED_SETTLE, _NIL_ID)
    return _encode_feed_cursor({_STREAM_ORDERS: mark, _STREAM_DEPARTURES: mark, "full": None})


def _after(qs: Any, at_field: str, position: Any) -> Any:
    """Rows strictly after `(at, id)` — the keyset half of the watermark."""
    if position is None:
        return qs
    at, ident = position
    return qs.filter(Q(**{f"{at_field}__gt": at}) | Q(**{at_field: at, "id__gt": ident}))


def _holder_of(row: Any) -> Any:
    """Who a holder-moving assignment row leaves the job with."""
    if row.act == models.WorkOrderAssignment.ACT_UNASSIGN:
        return None
    if row.technician_id is not None:
        return ("t", str(row.technician_id))
    if row.crew_id is not None:
        return ("c", str(row.crew_id))
    return None


#: The assignment rows that MOVE the holder — `_refresh_cache`'s own rule: an
#: `unassign` clears it, and any row naming a technician or a crew sets it
#: (that includes a `schedule` naming somebody new, which writes no `unassign`).
_MOVES_THE_HOLDER = (
    Q(act="unassign") | Q(technician__isnull=False) | Q(crew__isnull=False)
)


def _departures(technician: Any, rows: list[Any]) -> dict[str, str]:
    """Of these candidate rows, which took a job OFF this technician, and why.

    Answers `{row id: "reassigned" | "unassigned"}`. Decided by WALKING each
    order's holder history up to the row — the holder before it was this
    technician and the holder after it is not — because the row itself cannot
    say whose the job was: an `unassign` names nobody, and a `schedule` or an
    `assign` naming somebody else names only who GAINED it.
    """
    if not rows:
        return {}
    tenant_id = _tenant_id()
    me = ("t", str(technician.id))
    wanted = {str(row.id) for row in rows}
    last = max((row.at, str(row.id)) for row in rows)
    history = (
        models.WorkOrderAssignment.objects.filter(
            tenant_id=tenant_id, work_order_id__in={row.work_order_id for row in rows}
        )
        .filter(_MOVES_THE_HOLDER)
        .filter(Q(at__lt=last[0]) | Q(at=last[0], id__lte=last[1]))
    )
    # A reassign is ONE act written as TWO rows — `unassign` then `assign`,
    # sharing an `act_group` (`CR-168-BRC10` P4.4) — so the `unassign` half is
    # where the job leaves, and whether it went to somebody is answered by its
    # partner, which may fall on the next page.
    groups = {row.act_group for row in rows if row.act == "unassign" and row.act_group}
    paired = set(
        models.WorkOrderAssignment.objects.filter(tenant_id=tenant_id, act_group__in=groups)
        .exclude(act="unassign")
        .values_list("act_group", flat=True)
    ) if groups else set()
    holders: dict[Any, Any] = {}
    out: dict[str, str] = {}
    for row in history.order_by("at", "id"):
        before = holders.get(row.work_order_id)
        after = _holder_of(row)
        if str(row.id) in wanted and before == me and after != me:
            gone_to_somebody = after is not None or row.act_group in paired
            out[str(row.id)] = "reassigned" if gone_to_somebody else "unassigned"
        holders[row.work_order_id] = after
    return out


def _is_cancelled(order: Any) -> bool:
    tokens = metering_seam.dispatch_tokens()
    return order.dispatch_state == tokens.CANCELLED or order.state == "cancelled"


def changes(actor: Any, *, cursor: Any = None, per: Any = 50) -> dict[str, Any]:
    """`GET /work/mobile/changes?cursor=` — everything that changed for THIS
    technician since the cursor: jobs given or changed (`upsert`, with the
    card), and jobs taken AWAY (`removed`, a tombstone with no content and a
    `reason`).

    THE TOMBSTONES (T-31, R57) — every way a job leaves a technician:

    * **reassigned** — an `assign`, a reassign or a `schedule` naming somebody
      else; found by walking the order's holder history (`_departures`);
    * **unassigned** — taken off and given to nobody;
    * **cancelled** — the dispatcher cancelled it (`dispatch_state`), or the
      order itself was cancelled (`state`); the job keeps its assignee, so the
      order stream reports it;
    * **deleted** — cannot happen to a job anybody was given: every
      assignment row holds its order by `PROTECT`, and the rows themselves are
      append-only under `work/0009`'s trigger, so the delete is refused at the
      database. Proved in `tests/test_cr187_sync_feed_pg.py`, not assumed.

    A job CLOSED by the technician is not taken away: it arrives as an
    `upsert` whose card reads `completed`, so the handset keeps it for FF-35.

    THE CURSOR (T-32) carries a watermark PER TABLE — the orders and the
    assignment history — so neither can skip the other's rows, and it is
    opaque. With no cursor the feed is a FULL pass of the open, uncancelled
    jobs (nothing to tombstone on a handset that holds nothing); when that pass
    runs dry both watermarks drop to the moment it STARTED, so nothing that
    changed during a slow pass is lost. `GET /work/mobile/today` hands out a
    cursor too (`day_cursor`), so a refresh after the day read is a delta.

    The cursor is per technician by construction — the feed only ever reads
    the caller's own jobs — so a shared tablet never mixes logins. Paged
    (`count` of this page, `next_cursor`, `has_more`), no cap on how many pages
    (NFR-3, NFR-5); a push carries no data and only says *call this*, so a lost
    push loses nothing.
    """
    from core.pagination import clamp_page_size

    technician = technician_of(actor)
    size = clamp_page_size(per)
    state = _decode_cursor(cursor)
    if technician is None:
        return {"changes": [], "count": 0, "next_cursor": cursor, "has_more": False,
                "br_ref": "BR-WRK-063"}
    tenant_id = _tenant_id()
    now = timezone.now()
    if state is None:
        state = {_STREAM_ORDERS: None, _STREAM_DEPARTURES: None, "full": now}
    full = state.get("full")
    out: list[dict[str, Any]] = []
    # ⚠ A PASS THAT SCANNED ONLY HISTORY ROWS ABOUT OTHER PEOPLE answers
    # nothing — and the web field app stops paging on an EMPTY page
    # (`mobileEndpoints.syncChanges`). So keep scanning until the page holds a
    # change or the feed is dry; every pass still moves the watermarks.
    has_more = _scan(technician, tenant_id, state, size, out)
    while has_more and not out:
        has_more = _scan(technician, tenant_id, state, size, out)

    if not has_more:
        # The feed ran dry. Wind each watermark back by the settle window (or
        # to the moment a full pass started) — see `FEED_SETTLE`.
        floor = ((full or now) - FEED_SETTLE, _NIL_ID)
        for stream in (_STREAM_ORDERS, _STREAM_DEPARTURES):
            position = state.get(stream)
            state[stream] = floor if position is None or full is not None else min(position, floor)
        state["full"] = None
    return {
        "changes": out,
        "count": len(out),
        "next_cursor": _encode_feed_cursor(state),
        "has_more": has_more,
        # `full` while the first pass is still paging, `delta` after it.
        "mode": "full" if state.get("full") else "delta",
        # FB-023 F3 — the phone syncs through THIS feed, not `today`, so the
        # employment fact rides on every page (one attribute read, no query
        # beyond the crew the technician row already joins).
        "technician": {"employment": _employment(technician)},
        "br_ref": "BR-WRK-063",
    }


def _scan(technician: Any, tenant_id: Any, state: dict[str, Any], size: int,
          out: list[dict[str, Any]]) -> bool:
    """One keyset pass over both streams: appends this page's changes to
    `out`, moves `state`'s watermarks past every row it consumed, and answers
    whether rows remain."""
    full = state.get("full")

    # ── Stream 1 · the technician's own orders, by `updated_at` ─────────────
    # FB-030 (PO 2026-10-31) — and their CLOSED jobs of the last 14 days
    # (`_history_q`: held at the close, or crew time logged on it), so a new
    # phone, a reinstall or a remote sign-out is refilled with the reference
    # the technician keeps, and a helper sees the job the lead closed.
    history = _history_q(technician, history_since())
    if full is not None:
        # The full pass: the open window `today` reads, less what is
        # cancelled — what a handset that holds nothing should come to hold —
        # plus the 14-day history. Paged by the keyset below, no cap.
        open_ids = (
            metering_seam.dispatch_queryset()
            .filter(assignee_technician_id=technician.id)
            .values("id")
        )
        orders_qs = (
            metering_seam.every_dispatch_queryset()
            .filter(Q(id__in=open_ids) | history)
            .exclude(dispatch_state=metering_seam.dispatch_tokens().CANCELLED)
        )
    else:
        # A delta: every state, so a cancel or a close is SEEN.
        orders_qs = metering_seam.every_dispatch_queryset().filter(
            Q(assignee_technician_id=technician.id) | history
        )
    orders_qs = _after(orders_qs, "updated_at", state.get(_STREAM_ORDERS))
    order_rows = list(orders_qs.order_by("updated_at", "id")[: size + 1])

    # ── Stream 2 · the history rows that may have taken a job off them ──────
    departure_rows: list[Any] = []
    if full is None:
        ever_mine = models.WorkOrderAssignment.objects.filter(
            tenant_id=tenant_id, technician_id=technician.id
        ).values("work_order_id")
        departures_qs = _after(
            models.WorkOrderAssignment.objects.filter(
                tenant_id=tenant_id, work_order_id__in=ever_mine
            )
            .filter(_MOVES_THE_HOLDER)
            # A row GIVING me the job is never a departure — but an `unassign`
            # that names me is: a hand-back (FF-58) records who handed it back
            # (DEF-WRK-10351), so excluding every row naming me hid it.
            .exclude(Q(technician_id=technician.id) & ~Q(act="unassign")),
            "at",
            state.get(_STREAM_DEPARTURES),
        )
        departure_rows = list(departures_qs.order_by("at", "id")[: size + 1])

    merged: list[tuple[Any, str, str, Any]] = [
        (row.updated_at, str(row.id), _STREAM_ORDERS, row) for row in order_rows
    ] + [(row.at, str(row.id), _STREAM_DEPARTURES, row) for row in departure_rows]
    merged.sort(key=lambda item: (item[0], item[1]))
    page = merged[:size]

    why_gone = _departures(technician, [item[3] for item in page if item[2] == _STREAM_DEPARTURES])
    details = {
        row.work_order_id: row
        for row in models.WorkOrderDetail.objects.filter(
            tenant_id=tenant_id,
            work_order_id__in=[item[3].id for item in page if item[2] == _STREAM_ORDERS],
        )
    }
    for at, ident, stream, row in page:
        state[stream] = (at, ident)
        if stream == _STREAM_ORDERS:
            if _is_cancelled(row):
                out.append({"change": "removed", "order_id": str(row.id), "at": at.isoformat(),
                            "reason": "cancelled"})
            else:
                out.append({"change": "upsert", "order_id": str(row.id), "at": at.isoformat(),
                            "job": _job_card(row, details.get(row.id))})
        elif ident in why_gone:
            # A tombstone. If the job came BACK to this technician later, its
            # own upsert follows in the feed and the phone re-adds it.
            out.append({"change": "removed", "order_id": str(row.work_order_id),
                        "at": at.isoformat(), "reason": why_gone[ident]})
        # Any other history row (a reassign between two OTHER people after
        # this technician had already lost the job) answers nothing, and the
        # watermark still moves past it.
    return len(merged) > size


def readings_page(actor: Any, order_id: Any, *, page: Any = 1, per: Any = 50) -> dict[str, Any]:
    """`GET /work/mobile/jobs/{id}/readings?page=` — a job's readings, PAGED
    (PO 2026-10-04: *"use pagination to send and receive data"*). The bundle
    stays whole for an ordinary job; a job carrying hundreds of readings is
    read through this, never as one payload."""
    import math

    from core.pagination import clamp_page_size

    require_own_record(actor, order_id)  # FB-030 — a closed job's record too
    qs = models.WorkOrderReading.objects.filter(tenant_id=_tenant_id(), work_order_id=order_id).order_by("seq", "id")
    size = clamp_page_size(per)
    total = qs.count()
    last = max(1, math.ceil(total / size))
    number = max(1, min(int(page or 1), last))
    rows = qs[(number - 1) * size : number * size]
    return {
        "count": total,
        "page": number,
        "pages": last,
        "next": number + 1 if number < last else None,
        "previous": number - 1 if number > 1 else None,
        "results": [
            {
                "id": str(row.id),
                "seq": row.seq,
                "prompt": row.prompt,
                "unit_of_measure": row.unit_of_measure,
                "required": row.required,
                "photo_required": row.photo_required,
                "posts_as_meter_read": row.posts_as_meter_read,
                "kind": row.kind,
                "value": str(row.value) if row.value is not None else None,
                "value_text": row.value_text,
                "unable_to_read": row.unable_to_read,
                "unable_reason": row.unable_reason,
                "unable_note": row.unable_note,
                "photo_attachment_id": str(row.photo_attachment_id) if row.photo_attachment_id else None,
            }
            for row in rows
        ],
    }


def reconciliation(actor: Any) -> dict[str, Any]:
    """`GET /work/mobile/reconciliation` — what the server holds of THIS
    technician's captures: items stored (applied and held for review, by
    kind) and photographs declared vs landed. The phone compares it with
    what it captured, so a gap is a number on a screen rather than silence
    (TECHNICIAN SYNC DESIGN (6))."""
    from django.db.models import Count

    from apps.work.evidence_models import WorkPhotoLink
    from apps.work.sync_models import WorkSyncReceipt

    technician = technician_of(actor)
    if technician is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    tenant_id = _tenant_id()
    mine = WorkSyncReceipt.objects.filter(tenant_id=tenant_id).filter(
        Q(captured_by_technician_id=technician.id) | Q(accepted_by_id=technician.user_id)
    )
    by_kind = {
        row["kind"]: row["n"] for row in mine.values("kind").annotate(n=Count("id")).order_by("kind")
    }
    photos = WorkPhotoLink.objects.filter(tenant_id=tenant_id, captured_by_id=technician.user_id)
    return {
        "technician": {"name": _technician_name(technician)},
        "items_stored": mine.count(),
        "items_held_for_review": mine.exclude(needs_review__isnull=True).count(),
        "by_kind": by_kind,
        "photos_declared": photos.count(),
        "photos_landed": photos.filter(state=WorkPhotoLink.STATE_LANDED).count(),
        "br_ref": "BR-WRK-063",
    }
