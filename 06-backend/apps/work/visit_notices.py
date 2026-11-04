# ── Trace ──────────────────────────────────────────────
# Change:   CR-168-BRC10 round 6, lane SRV-5 — P6.1 (tell the consumer: booked,
#           moved, on the way, done) and P6.2 (tell the back office: at risk,
#           declined, blocked). Ruling 3 (23 Sep): *"Notification reaches the
#           consumer and the back office, and work orders print"*.
# Rules:    BR-NOT-017 (one home — the words, the switches and the rows are
#           Notifications'; Work only says WHICH occasion happened) ·
#           BR-NOT-021 (who in the office is told) · BR-WRK-002 (Work writes no
#           other module's table — the seam calls by name) · CLAUDE.md hard
#           rule 8 (the address is the PREMISES', walked) · B14 rule 31 (no
#           database id in anything a person reads)
# Tests:    06-backend/tests/test_cr168_srv5_messages.py
# Impacts:  apps/work/dispatch.py (record_act, hold) · apps/work/mobile.py
#           (decline_job) · apps/work/edit.py (notify_reschedule) ·
#           apps/work/escalations.py (the at-risk pass of the hourly sweep) ·
#           apps/metering/connections.py (accept_field_result → done)
# ───────────────────────────────────────────────────────
"""Work's half of telling people: WHICH occasion happened, on WHICH job.

THE SEVEN OCCASIONS AND WHERE EACH IS NOTICED
────────────────────────────────────────────────────────────────────────────
Customer (P6.1):
  * **logged** — `DEF-WRK-10652` (PO 2026-10-29, ruling 1A): a job WITH A
    CUSTOMER raised WITHOUT a visit window (`raise_svc`, after the raise
    commits). *We'll confirm a date.* Once per job, and never beside a
    *booked* for the same raise: a raise that books is told *booked* only.
  * **booked** — the first `assign` or `schedule` act that leaves a job WITH A
    CUSTOMER holding a date (`record_act`). Once per job.
  * **moved** — a later `assign`/`schedule` (or the edit page's Save) that
    changes the date or window. Once per new window.
  * **on the way** — a `depart` act (the phone's *On my way*, or the
    dispatcher's). Once per departure.
  * **done** — the office ACCEPTS a job whose outcome passed
    (`metering.connections.accept_field_result`). Never at the field close:
    until a person accepts it nothing is final (`WM-47`), and a failed job is
    not *done* to the person waiting for it.

Back office (P6.2), every one a failure in `BR-NOT-021`'s sense:
  * **declined** — a technician declines (`mobile.decline_job`).
  * **blocked** — the job is put on hold (`dispatch.hold`): it cannot go ahead,
    and the hold reason the office chose says why.
  * **at risk** — the hourly sweep finds an open job inside the at-risk window
    of its promise (`promise.at_risk_window_hours`), not yet past due.

⚠ **THE TEMPLATE DECIDES WHETHER THE CUSTOMER IS TOLD AT ALL** (`DEF-WRK-10652`,
ruling 4A): the job's copy of `send_customer_visit_messages` OFF — the seeded
disconnect and reconnect templates — and no customer message is queued, for any
of the five kinds. Never decided by a type name; the disconnect notices speak
for those visits. The office's three notices are not gated.

⚠ **NOTHING HERE MAY FAIL THE ACT.** Each call runs AFTER the act's own
transaction has committed, the seam never raises, and a broad catch here as
well: an assignment must not answer 500 because a letter could not be queued.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from django.utils import timezone

from apps.work.seams import notifications_seam, tenancy_seam

log = logging.getLogger(__name__)

#: `DEF-WRK-10652` — the answer when the job's template sends no visit message.
TEMPLATE_SWITCHED_OFF = "visit_message_template_off"

#: The acts that can BOOK or MOVE a visit — the two that give a job its time.
DATING_ACTS: tuple[str, ...] = ("assign", "schedule")


# ── the facts a customer's message carries ──────────────────────────────────


def _account_id(order: Any) -> Any:
    """The job's own account, else the account in force on its unit — the walk
    the order page's *Customer* uses (P1.15), so the two cannot disagree."""
    from apps.work.seams import customers_seam

    if getattr(order, "account_id", None):
        return order.account_id
    unit_id = getattr(order, "unit_id", None)
    account = customers_seam.current_account_for_unit(unit_id) if unit_id else None
    return account.get("id") if account else None


def _when(order: Any) -> dict[str, Any] | None:
    from apps.work import edit

    return edit._appointment(order)


def _human_date(iso: str | None) -> str | None:
    if not iso:
        return None
    day = datetime.fromisoformat(iso).date()
    return f"{day.strftime('%A')}, {day.strftime('%B')} {day.day}, {day.year}"


def window_key(order: Any) -> str:
    """What the customer was promised, as one comparable string — the moved
    message's discriminator (the same window twice tells the customer once)."""
    when = _when(order)
    if when is None:
        return ""
    return f"{when['date']}|{when.get('start') or ''}|{when.get('end') or ''}"


def _job_detail(order: Any) -> Any:
    """The job's own copy of its template's details (`BR-WRK-008`), or None
    for a one-off job raised with no template."""
    from apps.work import models as work_models

    return (
        work_models.WorkOrderDetail.objects.filter(
            tenant_id=order.tenant_id, work_order_id=order.id
        )
        .order_by("created_at")
        .first()
    )


def sends_visit_messages(order: Any) -> bool:
    """Ruling 4A — the job's template switch; ON for a job with no copy."""
    detail = _job_detail(order)
    return True if detail is None else bool(detail.send_customer_visit_messages)


def prep_instructions(order: Any) -> str | None:
    """Ruling 3B — the job's own preparation text, else the utility's default
    (`work_settings.visit_prep_default`; NULL reads the PO's seeded sentence,
    an empty string is *no default*). None when there is nothing to say, so
    the message's optional paragraph is left out rather than drawn blank."""
    from apps.work import models as work_models

    detail = _job_detail(order)
    text = (getattr(detail, "prep_instructions", None) or "").strip() if detail else ""
    if text:
        return text
    settings_row = work_models.WorkSettings.objects.filter(tenant_id=order.tenant_id).first()
    default = getattr(settings_row, "visit_prep_default", None) if settings_row else None
    if default is None:
        default = work_models.VISIT_PREP_DEFAULT
    return default.strip() or None


def customer_context(order: Any) -> dict[str, Any]:
    """Every merge value the four classes name, from stored facts only.

    `service_address` is the PREMISES' address (hard rule 8); `work_type` is the
    job's name as the order page draws it; no id travels (B14 rule 31).
    """
    from apps.work import dispatch, mobile

    contact = mobile._customer_contact(order) or {}
    name = contact.get("name") or None
    premises = dispatch._premises_row_of(order)
    when = _when(order) or {}
    start, end = when.get("start"), when.get("end")
    holder = dispatch._holder(order)
    completed = getattr(order, "completed_at", None)
    return {
        "first_name": (name.split(",")[-1].strip().split(" ")[0] if name else None),
        "customer_name": name,
        "account_no": contact.get("account_no"),
        "service_address": getattr(premises, "address_line", None) if premises else None,
        "work_type": dispatch._job_name(order),
        "appointment_date": _human_date(when.get("date")),
        # `DEF-WRK-10652` — a job with no date has no window either: *any time
        # that day* beside a *logged* message named a day nobody was given.
        "appointment_window": (
            (f"{start}–{end}" if start and end else (start or "any time that day"))
            if when
            else None
        ),
        "technician_name": holder["name"] if holder else None,
        "completed_date": (
            # `DEF-WRK-9688` — the utility's day, never the server's.
            _human_date(completed.astimezone(tenancy_seam.tenant_timezone()).date().isoformat())
            if completed
            else None
        ),
        "order_no": order.order_no,
        # DEF-WRK-10652 (ruling 3B) — the logged, booked and moved messages.
        "prep_instructions": prep_instructions(order),
    }


# ── the two doors ───────────────────────────────────────────────────────────


def tell_customer(order: Any, kind: str, *, discriminator: str = "", actor: Any = None) -> Any:
    """Queue one of the five customer messages. Never raises."""
    try:
        if not sends_visit_messages(order):
            # Ruling 4A — the template says this job's customer is told by
            # other notices (a disconnect, a reconnect). Nothing is written.
            return {"code": TEMPLATE_SWITCHED_OFF, "messages": []}
        return notifications_seam.queue_visit_message(
            kind=kind,
            order_id=order.id,
            account_id=_account_id(order),
            discriminator=discriminator,
            render_context=customer_context(order),
            actor=actor,
        )
    except Exception as exc:  # noqa: BLE001 — a message never fails the act
        log.warning("visit message %s for %s not queued: %s", kind, order.order_no, exc)
        return None


def tell_office(order: Any, kind: str, *, discriminator: str = "", hours: int = 0) -> Any:
    """Queue one of the three back-office notices. Never raises."""
    try:
        return notifications_seam.queue_work_office_notice(
            kind=kind,
            order_id=order.id,
            order_no=order.order_no,
            acted_user_id=getattr(order, "assigned_by_id", None),
            discriminator=discriminator,
            hours=hours,
            occurred_at=timezone.now(),
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("office notice %s for %s not queued: %s", kind, order.order_no, exc)
        return None


# ── when an act happened ────────────────────────────────────────────────────


def after_act(order: Any, act: str, *, window_before: str, row: Any = None, actor: Any = None) -> Any:
    """After `record_act` (or the edit page) committed one act on `order`.

    `window_before` is `window_key(order)` read BEFORE the act. Booked is the
    first time a dated act leaves the job with a time; moved is a later one
    that changed it. A depart is *on the way*, once per departure row.
    """
    if act in DATING_ACTS or act == "reassign":
        now = window_key(order)
        if not now:
            return None
        if not window_before or not _booked_before(order):
            return tell_customer(order, "booked", actor=actor)
        if now != window_before:
            return tell_customer(order, "moved", discriminator=now, actor=actor)
        return None
    if act == "depart":
        return tell_customer(
            order, "on_the_way", discriminator=str(getattr(row, "id", "") or ""), actor=actor
        )
    return None


def after_raise(order: Any, actor: Any = None) -> Any:
    """`DEF-WRK-10652` (ruling 1A) — after a raise COMMITTED: a job with no
    visit window, about which no *booked* was written, is told *logged*.

    A raise that gave the job a window told the customer *booked* through
    `record_act` already, so this writes nothing (never both). A due date
    alone is a deadline, not a visit: such a job is *logged* unless an
    assignment at the raise already booked it. The key is the job and the
    kind, so a repeated call writes nothing twice. Never raises."""
    try:
        if getattr(order, "window_start", None) is not None:
            return None
        if _booked_before(order):
            return None
    except Exception as exc:  # noqa: BLE001 — a message never fails the raise
        log.warning("logged message for %s not queued: %s", order.order_no, exc)
        return None
    return tell_customer(order, "logged", actor=actor)


def _booked_before(order: Any) -> bool:
    """Was a *booked* message already written for this job? Asked of the queue
    through the seam, never remembered — a job dated before this build has no
    booked row, and its first move books it rather than telling the customer
    their visit moved from a time they were never told."""
    return bool(notifications_seam.visit_message_written(order_id=order.id, kind="booked"))


def after_accept(order: Any, actor: Any = None) -> Any:
    """The office accepted the field result: a PASSED job is *done*."""
    if getattr(order, "outcome", None) != "passed":
        return None
    return tell_customer(order, "done", actor=actor)


def at_risk_sweep(*, now: datetime | None = None) -> dict[str, int]:
    """The at-risk pass of the hourly sweep: every OPEN job due within the
    tenant's at-risk window and not yet past due, told ONCE per promise (the
    due moment is the discriminator, so a job whose promise moves can be at
    risk again)."""
    from apps.work import promise
    from apps.work.seams import metering_seam

    window = promise.at_risk_window_hours()
    if not window:
        return {"at_risk": 0}
    moment = now or timezone.now()
    hours_default = promise.default_hours()
    qs = (
        metering_seam.open_work_orders_queryset()
        .annotate(promise_due=promise.due_expr(hours_default, open_clock=True))
        .filter(promise_due__gt=moment, promise_due__lte=moment + timedelta(hours=int(window)))
        .order_by("created_at", "id")
    )
    told = 0
    for order in qs:
        answer = tell_office(
            order, "at_risk", discriminator=order.promise_due.isoformat(), hours=int(window)
        )
        told += 1 if (answer or {}).get("code") == "escalation_queued" else 0
    return {"at_risk": told}


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-168-BRC10 §5.8 P6 · §7.1 · ruling 3
# generated: 2026-10-04 by CR-168 round 6 lane SRV-5
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_cr168_srv5_messages.py on SQLite and PostgreSQL 16
# status: AI-AUTHORED
# ──────────────────────────────────────────────────────────
