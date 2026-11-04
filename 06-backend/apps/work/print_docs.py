# ── Trace ──────────────────────────────────────────────
# Change:   CR-168-BRC10 round 6, lane SRV-5 — P6.3 *"Print a work order"* and
#           ruling 3's *"a day's pack prints"*. The blueprint's own reason:
#           *"A technician with no phone, a depot with no signal, a customer
#           wanting a copy, a contractor who is not a user."*
# Rules:    B14 rule 31 (no database id on paper — numbers and names only) ·
#           CLAUDE.md hard rule 8 (the address is the PREMISES', walked) ·
#           rule 3 (a reading carries its unit) · BR-WRK-008 (the order's OWN
#           copies — the checklist read, never the template) · B14 rule 43 (the
#           product's one PDF writer, `apps/billing/page_print.py`, reused)
# Tests:    06-backend/tests/test_cr168_srv5_print.py
# Impacts:  apps/work/api.py (`GET /work-orders/{id}/print`,
#           `GET /work/print/day-pack`) · apps/work/seams/billing_seam.py
# ───────────────────────────────────────────────────────
"""A work order on paper, and a technician's (or a crew's) day on paper.

WHAT A SHEET CARRIES, AND FROM WHERE
────────────────────────────────────────────────────────────────────────────
Every fact is one the order page already shows, read through the SAME reads
(`dispatch.order_row`, `checklist.checklist`) so paper and screen cannot
disagree: the job, its priority and status; WHERE — the premises' address
walked (hard rule 8), its number, the unit's label, the meter's number; the
CUSTOMER — name, phone, account number (read live, never typed onto the job);
WHEN — the date and window in the utility's own zone; who holds it; access
notes and hazards; then the order's own copies as boxes to tick and blanks to
fill — safety, tasks, readings with their units, parts. A sign-off block ends
the sheet. **No id is printed** (B14 rule 31) — a uuid on a clipboard is
nothing a person can say on the phone.

ON DEMAND, NOT STORED
────────────────────────────────────────────────────────────────────────────
§7.3 sketched these as *"rendered through the tenancy document store"*. They
are rendered on demand instead, and that is our judgment (decision log
*"CR-168 ROUND 6 · SRV-5"*): an OPEN job's sheet changes every time it is
moved or reassigned, so a stored copy is stale by the next dispatch, and the
document that IS final — the accepted job's report — already has its own home
(`WorkOrderReport`, `BR-WRK-050`). The render is deterministic (the billing
engine's: no clock, a content-hash `/ID`), so the same job printed twice is
the same bytes.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from core import errors
from core import tenancy as core_tenancy

from apps.work.seams import billing_seam, tenancy_seam

#: The dispatch and state tokens, in the words a technician reads on paper.
#: English, like every printed document in the product (the bill included).
STATUS_WORDS: dict[str, str] = {
    "queued": "Queued",
    "scheduled": "Scheduled",
    "en_route": "En route",
    "on_site": "On site",
    "on_hold": "On hold",
    "complete": "Completed",
    "cancelled": "Cancelled",
    "planned": "Planned",
    "in_progress": "In progress",
    "blocked": "Blocked",
    "completed": "Completed",
}


def _pp() -> Any:
    return billing_seam.page_engine()


def _dash(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    return text or _pp().ABSENT_MARK


def _local(iso: str | None) -> datetime | None:
    if not iso:
        return None
    return datetime.fromisoformat(iso).astimezone(tenancy_seam.tenant_timezone())


def _day_words(day: date) -> str:
    return f"{day.strftime('%a')} {day.strftime('%b')} {day.day}, {day.year}"


def when_text(row: dict[str, Any]) -> str:
    """*Tue Oct 6, 2026 · 08:00–12:00* — the promise in the utility's zone."""
    start = _local(row.get("window_start"))
    end = _local(row.get("window_end"))
    if start is not None:
        window = f"{start:%H:%M}–{end:%H:%M}" if end is not None else f"{start:%H:%M}"
        return f"{_day_words(start.date())} · {window}"
    due = _local(row.get("due_at"))
    return f"{_day_words(due.date())} · any time" if due is not None else _pp().ABSENT_MARK


# ── the row builders ────────────────────────────────────────────────────────


def _heading(text: str) -> list[Any]:
    pp = _pp()
    return [
        pp.PageRow(pp.LEAD_SECTION),
        pp.PageRow(
            pp.LEAD_BODY,
            (pp.PageCell(text.upper(), pp.PAGE_MARGIN, pp.FONT_BOLD, pp.SIZE_SECTION, pp.MUTED,
                         tracking=0.6),),
            (pp.PageRule(dy=4.0),),
            keep_with_next=1,
        ),
        pp.PageRow(pp.LEAD_GAP),
    ]


LABEL_WIDTH = 110.0


def _fact(label: str, value: Any) -> list[Any]:
    """One label / value pair; a long value wraps under itself."""
    pp = _pp()
    x = pp.PAGE_MARGIN + LABEL_WIDTH
    lines = pp.wrap(_dash(value), pp.PAGE_RIGHT - x)
    rows = [
        pp.PageRow(
            pp.LEAD_BODY,
            (
                pp.PageCell(label, pp.PAGE_MARGIN, pp.FONT_REGULAR, pp.SIZE_BODY, pp.MUTED),
                pp.PageCell(lines[0], x),
            ),
        )
    ]
    rows.extend(pp.PageRow(pp.LEAD_BODY, (pp.PageCell(line, x),)) for line in lines[1:])
    return rows


def _line(text: str, *, indent: float = 0.0, bold: bool = False, muted: bool = False,
          size: float | None = None) -> list[Any]:
    pp = _pp()
    x = pp.PAGE_MARGIN + indent
    size = size or pp.SIZE_BODY
    lines = pp.wrap(text, pp.PAGE_RIGHT - x, bold=bold, size=size)
    return [
        pp.PageRow(
            pp.LEAD_BODY,
            (pp.PageCell(line, x, pp.FONT_BOLD if bold else pp.FONT_REGULAR, size,
                         pp.MUTED if muted else pp.INK),),
        )
        for line in lines
    ]


BOX = "[ ]"


def _tick_rows(items: list[tuple[str, str | None]]) -> list[Any]:
    """`[  ] 1. Title` with the instruction under it — boxes to tick by hand."""
    rows: list[Any] = []
    for title, note in items:
        rows.extend(_line(f"{BOX}  {title}"))
        if note:
            rows.extend(_line(note, indent=22.0, muted=True, size=_pp().SIZE_SMALL))
    return rows


def _range(reading: dict[str, Any]) -> str:
    low, high = reading.get("min_value"), reading.get("max_value")
    if low is None and high is None:
        return ""
    return f"  (expected {_trim(low) if low is not None else '…'}–{_trim(high) if high is not None else '…'})"


def _trim(value: Any) -> str:
    text = str(value)
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def order_rows(order_id: Any, *, masthead: dict[str, Any] | None = None) -> tuple[list[Any], str]:
    """One work order's sheet as page rows, and its number."""
    from apps.work import checklist, dispatch

    pp = _pp()
    row = dispatch.order_row(order_id)
    copies = checklist.checklist(order_id)
    masthead = masthead if masthead is not None else tenancy_seam.utility_masthead()
    order_no = row.get("order_no") or pp.ABSENT_MARK

    rows: list[Any] = [
        pp.PageRow(
            22.0,
            (
                pp.PageCell(f"Work order {order_no}", pp.PAGE_MARGIN, pp.FONT_BOLD, pp.SIZE_TITLE),
                pp.PageCell(_dash(masthead.get("name")), pp.PAGE_RIGHT, pp.FONT_BOLD,
                            pp.SIZE_BODY, right=True),
            ),
        ),
    ]
    status = STATUS_WORDS.get(row.get("dispatch_state") or "", None) or STATUS_WORDS.get(
        row.get("state") or "", _dash(row.get("state"))
    )
    priority = (row.get("priority") or {}).get("name")
    rows.extend(_line(" · ".join(part for part in (row.get("type"), priority, status) if part),
                      muted=True))
    rows.append(pp.PageRow(pp.LEAD_GAP, rules=(pp.PageRule(dy=4.0, weight=0.8),)))

    location = row.get("location") or {}
    rows += _heading("Where")
    rows += _fact("Address", location.get("address"))
    if row.get("stored_at"):
        # `DEF-WRK-9671` — a meter in the warehouse: where it is kept, in the
        # asset's own words, and never written as its address (hard rule 8).
        rows += _fact("Stored at", row.get("stored_at"))
    rows += _fact("Premise", (location.get("premises") or {}).get("premise_no"))
    rows += _fact("Unit", (location.get("unit") or {}).get("label"))
    asset = location.get("asset") or {}
    rows += _fact("Meter / asset", " · ".join(
        part for part in (asset.get("asset_no"), asset.get("serial")) if part) or None)

    customer = row.get("customer") or {}
    rows += _heading("Customer")
    rows += _fact("Name", customer.get("name"))
    rows += _fact("Phone", customer.get("phone"))
    rows += _fact("Account", customer.get("account_no"))

    rows += _heading("When")
    rows += _fact("Visit", when_text(row))
    due = _local(row.get("due_at"))
    rows += _fact("Due", f"{_day_words(due.date())} {due:%H:%M}" if due else None)
    minutes = row.get("est_duration_minutes") or copies.get("tasks_est_minutes") or None
    rows += _fact("Expected time", f"{minutes} min" if minutes else None)
    rows += _fact("Assigned to", (row.get("technician") or {}).get("name"))

    details = copies.get("details") or {}
    if any(details.get(key) for key in ("access_notes", "hazards", "gate_code")):
        rows += _heading("Access")
        if details.get("access_notes"):
            rows += _fact("Access notes", details.get("access_notes"))
        if details.get("hazards"):
            rows += _fact("Hazards", details.get("hazards"))
        if details.get("gate_code"):
            rows += _fact("Gate code", details.get("gate_code"))

    safety = copies.get("safety") or []
    if safety:
        rows += _heading("Safety — before you start")
        rows += _tick_rows([(item["text"], None) for item in safety])

    tasks = copies.get("tasks") or []
    if tasks:
        rows += _heading("Tasks")
        rows += _tick_rows(
            [
                (
                    f"{index}. {task['title']}"
                    + (f"  ({task['est_minutes']} min)" if task.get("est_minutes") else "")
                    + ("  · photo" if task.get("photo_required") else ""),
                    task.get("instruction"),
                )
                for index, task in enumerate(tasks, start=1)
            ]
        )

    readings = copies.get("readings") or []
    if readings:
        rows += _heading("Readings")
        for reading in readings:
            value = reading.get("value_text") or (
                _trim(reading["value"]) if reading.get("value") is not None else "__________"
            )
            unit = reading.get("unit_of_measure") or ""
            rows += _fact(reading.get("prompt") or "Reading",
                          f"{value} {unit}".strip() + _range(reading))

    materials = copies.get("materials") or []
    if materials:
        rows += _heading("Parts")
        for item in materials:
            used = _trim(item["used_qty"]) if item.get("used_qty") is not None else "____"
            rows += _fact(
                item.get("part_no") or "",
                f"{item.get('part_name') or ''} — planned {_trim(item.get('planned_qty'))} "
                f"{item.get('unit_of_measure') or ''}, used {used}",
            )

    rows += _heading("Sign-off")
    rows += _fact("Technician", "______________________________   Date ____________")
    rows += _fact("Customer", "______________________________   Date ____________")
    if masthead.get("support_phone"):
        rows.append(pp.PageRow(pp.LEAD_GAP))
        rows += _line(f"Questions about this visit: {masthead['support_phone']}", muted=True,
                      size=pp.SIZE_SMALL)
    return rows, str(order_no)


def order_pdf(order_id: Any) -> tuple[bytes, str]:
    """`GET /work-orders/{id}/print` — the bytes and the file name."""
    pp = _pp()
    rows, order_no = order_rows(order_id)
    printed = pp.render([rows], footer=f"Work order {order_no}")
    return printed.data, f"{order_no}.pdf"


# ── the day's pack ──────────────────────────────────────────────────────────


def _holder_by_slug(*, technician: str | None, crew: str | None) -> tuple[str, str, Any]:
    """`(kind, name, row)` for a technician or crew slug of THIS tenant, or 404
    — another utility's slug is not found, identical to one that never existed
    (hard rule 1)."""
    from apps.work import models as work_models
    from apps.work import workforce

    tenant_id = core_tenancy.current_tenant_id()
    if technician:
        for row in work_models.Technician.objects.filter(tenant_id=tenant_id).select_related("user"):
            if workforce.technician_slug(row) == technician:
                return "technician", row.user.full_name or row.user.email, row
    elif crew:
        for row in work_models.Crew.objects.filter(tenant_id=tenant_id):
            if workforce.crew_slug(row) == crew:
                return "crew", row.name, row
    else:
        raise errors.ValidationError(
            errors.VAL_REQUIRED, message_key="work.print.holder_required", br_ref="BR-WRK-025"
        )
    raise errors.NotFoundError()


def day_orders(kind: str, holder: Any, on: date) -> list[Any]:
    """The OPEN jobs this person or crew holds on `on`, in the order of the
    day — window first, else due time, then number (the phone's own order)."""
    from django.db.models import Q

    from apps.work.seams import metering_seam

    zone = tenancy_seam.tenant_timezone()
    start = datetime.combine(on, datetime.min.time()).replace(tzinfo=zone)
    end = start + timedelta(days=1)
    qs = metering_seam.open_work_orders_queryset().filter(
        Q(window_start__gte=start, window_start__lt=end)
        | Q(window_start__isnull=True, due_at__gte=start, due_at__lt=end)
    )
    qs = qs.filter(assignee_technician=holder) if kind == "technician" else qs.filter(
        assignee_crew=holder
    )
    return sorted(
        qs,
        key=lambda order: (order.window_start or order.due_at, order.order_no or ""),
    )


def _parse_day(value: Any) -> date:
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError:
        raise errors.ValidationError(
            errors.VAL_FORMAT, message_key="work.print.date_unreadable",
            params={"date": str(value or "")},
        ) from None


def day_pack_pdf(*, on: Any, technician: str | None = None, crew: str | None = None
                 ) -> tuple[bytes, str]:
    """`GET /work/print/day-pack?date=&technician=|crew=` — a cover list of the
    day, then each job on its own sheet. A day with no jobs prints the cover
    saying so, rather than refusing: *nothing today* is an answer."""
    from apps.work import dispatch

    pp = _pp()
    day = _parse_day(on)
    kind, name, holder = _holder_by_slug(technician=technician, crew=crew)
    orders = day_orders(kind, holder, day)
    masthead = tenancy_seam.utility_masthead()

    cover: list[Any] = [
        pp.PageRow(
            22.0,
            (
                pp.PageCell(f"Day pack · {name}", pp.PAGE_MARGIN, pp.FONT_BOLD, pp.SIZE_TITLE),
                pp.PageCell(_dash(masthead.get("name")), pp.PAGE_RIGHT, pp.FONT_BOLD,
                            pp.SIZE_BODY, right=True),
            ),
        ),
    ]
    cover += _line(f"{_day_words(day)} · {len(orders)} job{'s' if len(orders) != 1 else ''}",
                   muted=True)
    cover.append(pp.PageRow(pp.LEAD_GAP, rules=(pp.PageRule(dy=4.0, weight=0.8),)))
    cover += _heading("The day, in order")
    if not orders:
        cover += _line("No open jobs on this day.", muted=True)
    columns = (pp.PAGE_MARGIN, pp.PAGE_MARGIN + 22, pp.PAGE_MARGIN + 104,
               pp.PAGE_MARGIN + 170, pp.PAGE_MARGIN + 300)
    if orders:
        cover.append(
            pp.PageRow(
                pp.LEAD_BODY,
                tuple(
                    pp.PageCell(text, x, pp.FONT_BOLD, pp.SIZE_LABEL, pp.MUTED)
                    for text, x in zip(("#", "Time", "Order", "Job", "Address"), columns)
                ),
                (pp.PageRule(dy=4.0),),
            )
        )
    sheets: list[list[Any]] = []
    for index, order in enumerate(orders, start=1):
        row = dispatch.order_row(order.id)
        when = when_text(row).split(" · ")[-1]
        # `DEF-WRK-9671` — a job on no premises reads its asset's own note.
        address = (
            (row.get("location") or {}).get("address") or row.get("stored_at") or pp.ABSENT_MARK
        )
        job = row.get("type") or pp.ABSENT_MARK
        width = pp.PAGE_RIGHT - columns[4]
        cover.append(
            pp.PageRow(
                pp.LEAD_BODY + 2,
                (
                    pp.PageCell(str(index), columns[0]),
                    pp.PageCell(when, columns[1]),
                    pp.PageCell(row.get("order_no") or pp.ABSENT_MARK, columns[2], pp.FONT_BOLD),
                    pp.PageCell(pp.wrap(job, columns[4] - columns[3] - 6)[0], columns[3]),
                    pp.PageCell(pp.wrap(address, width)[0], columns[4]),
                ),
            )
        )
        sheet, _ = order_rows(order.id, masthead=masthead)
        sheets.append(sheet)
    footer = f"Day pack · {name} · {day.isoformat()}"
    printed = pp.render([cover, *sheets], footer=footer)
    slug = technician or crew or "day"
    return printed.data, f"day-pack-{slug}-{day.isoformat()}.pdf"


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-168-BRC10 §5.8 P6.3 · §7.3 · ruling 3
# generated: 2026-10-04 by CR-168 round 6 lane SRV-5
# checklist: A✔ B✔ C✔ D✔ E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_cr168_srv5_print.py on SQLite and PostgreSQL 16
# status: AI-AUTHORED
# ──────────────────────────────────────────────────────────
