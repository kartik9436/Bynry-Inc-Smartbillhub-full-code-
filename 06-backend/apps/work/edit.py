# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-031 (the work-order edit screen — assign, reschedule,
#           re-prioritise, re-area, cancel, behind a Change effects box)
#           Screens: Work-021 (`/{tenant}/work/orders/{order_no}/edit`)
# Rules:    BR-WRK-031 (a moved date or window notifies the customer on the
#           `appointment` kind; EVERY field change is audited with who and
#           when) · BR-WRK-032 (Cancel is danger tier; Save follows a Change
#           effects box) · BR-WRK-025 (assignment changes are new history rows,
#           never an edit) · BR-WRK-018 (a priority is a promise; due_at moves
#           with it) · BR-WRK-023 (dispatch state is the third axis) ·
#           CLAUDE.md hard rule 1 (tenant scoping) · hard rule 4 (financial
#           immutability — see WHAT THIS DELIBERATELY CANNOT TOUCH) · hard
#           rule 7 (every act writes audit_log) · hard rule 8 (an address is
#           the premises' — this screen has no address field at all)
# Tests:    06-backend/tests/test_us_wrk_031_edit.py (TC-1…TC-7) ·
#           tests/test_us_wrk_031_034_edit_pg.py (RLS + the FK, on PostgreSQL)
# Impacts:  apps/work/api.py (`PATCH /work-orders/{id}`) ·
#           07-frontend/src/features/work/OrderEditPage.tsx
# ───────────────────────────────────────────────────────
"""Everything a dispatcher changes AFTER an order exists.

WHAT MAKES THIS SCREEN DIFFERENT FROM EVERY OTHER ONE IN CR-070
---------------------------------------------------------------
Every other wave in this change request CREATES something. This one changes
something that already exists **and that somebody may already be acting on** —
a technician may be driving to it right now. Three consequences follow, and
they are the whole design:

**1 · WORK ALREADY DONE DOES NOT UN-HAPPEN.** Nothing here rewrites history.
`work_order_assignments` is append-only at the DATABASE (`work/0009`'s
trigger), so moving a job from D. Ortiz to R. Patel writes an `unassign` and an
`assign` and **leaves D. Ortiz's row exactly where it was**. A safety row or a
task a crew ticked against the order is `work_order_tasks`/`_safety` (wave H's
copies) and this file does not touch them: a step completed at 09:40 stays
completed at 09:40 even though the window it was completed in has since moved.
The order carries a NEW promise; it does not acquire a new past.

**2 · SOMEBODY HAS TO BE TOLD, AND WHICH SOMEBODY DEPENDS ON WHAT MOVED.**
Three audiences, three different triggers, and they are deliberately not the
same condition:

  * the CUSTOMER — only when the **date or the window** moved. They do not care
    that the area code changed or that the dispatcher added a note about a dog.
    `BR-WRK-031`, and the kind is `appointment` (`OQ-WRK-1495`, closed
    2026-09-04, option (a)).
  * the TECHNICIAN — on **any** change to a job they hold, because they are
    working from a copy on a phone. That is wave J's push and this file leaves
    it to `BR-WRK-034`'s trigger rather than inventing a second one.
  * the AUDIT — on **every** field, always. `BR-WRK-031`'s confirmed half.

**3 · THE BOX BEFORE SAVE SAYS WHAT SAVE DOES.** B14 rule 11, and this wave is
the case that rule was written for. The frontend renders it; the reason it is
mentioned in a backend docstring is that the box makes THREE promises and this
file is what has to keep them. A box that said *"this will change the order"*
would be worthless — it names the customer send, the phone update and the audit
because those are the three things a dispatcher cannot undo by pressing Cancel.

WHAT THIS DELIBERATELY CANNOT TOUCH — HARD RULE 4
--------------------------------------------------
⚠ **NOTHING ON THIS SCREEN IS FINANCIAL, AND THAT WAS CHECKED BEFORE THE EDIT
PATH WAS DESIGNED RATHER THAN AFTER.** The fields are priority, due date,
appointment window, area, technician notes, dispatch state and the assignee.
None of them is an issued invoice, an invoice line, a payment or a journal
entry, and none of them is an input to one:

  * a job's COST lines are `EP-WRK-10`'s and are posted when the work is
    accepted, not when it is scheduled;
  * a rescheduled visit does not move a bill — the customer's charge for a
    disconnection visit is raised by the acceptance, and this screen cannot
    reach it.

**So no correction row is needed and none is written.** If a later wave puts a
chargeable field on this form, that field does NOT join this UPDATE path: it
becomes a new row, and this paragraph is where the next lane should find that
out. `EP-WRK-10`'s costing is where the boundary actually sits.

⚠ **AND THE ONE PLACE HARD RULE 4 WAS NARROWED IS NOT THIS ONE.** The PO ruling
of 2026-09-02 widened exactly three columns on `payments` and nothing else. A
lane reading this file for a precedent is reading the wrong file.

WHY THE AUDIT IS PER FIELD AND THE HISTORY IS PER ACT
------------------------------------------------------
`US-WRK-031` TC-1 changes the technician AND the window and expects
`unassign` + `assign` rows and **two** audit rows. `J62` step 3 assigns and
schedules and expects one `assign` row, one `schedule` row and **two** audit
rows. Both are satisfied by one rule and only by one rule:

  **one `audit_log` row per FIELD the dispatcher changed; the assignment
  history takes as many rows as the acts require.**

Reassigning is two history rows (somebody LOST the job — recording only the
gain loses that) and one field. That is why this file calls
`dispatch.append_act`, which appends and refreshes the cache and writes NO
audit row, instead of `dispatch.record_act`, which audits per act.
"""

from __future__ import annotations

import uuid
from typing import Any

from django.db import transaction

from apps.work import dispatch
from apps.work import models as work_models
from apps.work.seams import metering_seam, notifications_seam, tenancy_seam
from core import audit as core_audit
from core import errors
from core import tenancy as core_tenancy

#: The fields `Work-021` puts on the form, in the order the screen draws them
#: (`WS-21`). Named as a tuple so the API's allow-list, the audit's field names
#: and the test's coverage check all read ONE list — a field added to the screen
#: and forgotten in one of the three is the shape of `DEF-CUS-3653`.
EDITABLE_FIELDS: tuple[str, ...] = (
    "dispatch_state",
    "priority_id",
    "due_at",
    "window_start",
    "window_end",
    "area_id",
    "technician_notes",
    "technician_id",
    "crew_id",
    # CR-161-BRC10 W4 — the utility's own fields (PO 2026-10-02, Part 2 row
    # 10: *"Edit work order"*). Validated and MERGED by tenancy's one
    # validator through `tenancy_seam`; audited as ONE field, like the notes.
    "custom_data",
    # `CR-168-BRC10` P4.4 (lane ASSIGN, image 13) — WHY the job moves off its
    # holder. Not a field of the order: it rides the two history rows a
    # reassign writes, and a move off somebody without it is refused.
    "reason",
)

#: CR-161-BRC10 W4 — Work-021's slot key in `apps/tenancy/custom_fields.SLOTS`.
CUSTOM_SCREEN = "WORK_EDIT"

#: ⚠ **THE TWO THAT TELL THE CUSTOMER.** `BR-WRK-031`, verbatim: *"Changing an
#: order's date or appointment WINDOW notifies the customer."* Not the area, not
#: the notes, not the priority — a customer waiting in on Tuesday morning cares
#: that the morning became the afternoon and not that the job moved from High to
#: Urgent. `US-WRK-031` TC-6 is the negative and it is a real case: a dispatcher
#: adding *"dog on property"* must not send anybody a letter.
NOTIFYING_FIELDS: frozenset[str] = frozenset({"due_at", "window_start", "window_end"})


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _order_or_404(order_id: Any) -> Any:
    """The order, scoped to the tenant in context — hard rule 1.

    `US-WRK-031` TC-7: Lone Star Ridge opening Brazos Bend's `WO-4821` gets a
    **404 and not a 403**, because a 403 confirms the order exists.
    """
    return dispatch._order_or_404(order_id)


def _window_label(order: Any) -> str | None:
    """*08:00–12:00* — what the customer was promised, in the customer's terms.

    Returns None when there is no window, which the message template renders as
    the date alone. A half-window (`start` with no `end`) is an EXACT
    APPOINTMENT on this screen's own vocabulary, so it renders as the one time.
    """
    if order.window_start is None:
        return None
    # `DEF-WRK-9688` — in the UTILITY's zone. `strftime` on a stored instant
    # printed UTC, so the history line said *13:00–17:00* over a Central
    # 08:00–12:00 the order page drew correctly.
    zone = tenancy_seam.tenant_timezone()
    start = order.window_start.astimezone(zone).strftime("%H:%M")
    if order.window_end is None:
        return start
    return f"{start}–{order.window_end.astimezone(zone).strftime('%H:%M')}"


def _holder_with_id(order: Any) -> dict[str, Any] | None:
    holder = dispatch._holder(order)
    if holder is None:
        return None
    holder_id = order.assignee_technician_id or order.assignee_crew_id
    return {"id": str(holder_id), **holder}


def _appointment(order: Any) -> dict[str, Any] | None:
    """`{date, start, end}` in the UTILITY's own zone (P1.25's date/time half).

    A job's window is stored as two instants; a dispatcher in Texas edits a
    calendar day and two clock times. Served as instants, a 08:00 window opened
    on a UTC server as *13:00* — the same `DEF-CUS-6363` shape. With no window,
    the date is the due date's and both times are `None` (*Any time*).
    """
    zone = tenancy_seam.tenant_timezone()
    start = order.window_start or order.due_at
    if start is None:
        return None
    local_start = start.astimezone(zone)
    return {
        "date": local_start.date().isoformat(),
        "start": local_start.strftime("%H:%M") if order.window_start else None,
        "end": (
            order.window_end.astimezone(zone).strftime("%H:%M") if order.window_end else None
        ),
        "time_zone": str(zone),
    }


def _priorities() -> list[dict[str, Any]]:
    """The tenant's ACTIVE priorities by rank — the form's select, in one read."""
    return [
        {"id": str(row.id), "code": row.code, "name": row.name, "rank": row.rank,
         "sla_hours": row.sla_hours}
        for row in work_models.WorkPriority.objects.filter(
            tenant_id=dispatch._tenant_id(), active=True
        ).order_by("rank", "id")
    ]


def form_values(order_id: Any) -> dict[str, Any]:
    """What `Work-021` opens with — the current value of every field it edits.

    Separate from `dispatch.order_row` because the EDIT form needs the raw
    values (an id to select, an ISO moment to put in a picker) where the list
    needs display values. Returning the list's shaped row here would make the
    Area select show a NAME it cannot post back.
    """
    order = _order_or_404(order_id)
    return {
        "id": str(order.id),
        "order_no": order.order_no,
        "type": (order.type_ref.name if order.type_ref_id else order.type),
        "dispatch_state": order.dispatch_state,
        "state": order.state,
        "priority_id": str(order.priority_id) if order.priority_id else None,
        "due_at": order.due_at.isoformat() if order.due_at else None,
        "window_start": order.window_start.isoformat() if order.window_start else None,
        "window_end": order.window_end.isoformat() if order.window_end else None,
        "area_id": str(order.area_id) if order.area_id else None,
        "technician_notes": order.technician_notes,
        # CR-161-BRC10 W4 — the stored answers the form opens with.
        "custom_data": dict(order.custom_data or {}),
        # ⚠ **WITH ITS ID** (`CR-168-BRC10` P1.25, `DEF-WRK-9530`). The form
        # posts back `technician_id` / `crew_id`; served without an id, the
        # picker opened on *Nobody yet* and a Save that touched only the slot
        # could unassign the job. `kind` says which of the two ids to post.
        "technician": _holder_with_id(order),
        "appointment": _appointment(order),
        "priorities": _priorities(),
        "premise": dispatch._premise_of(order),
        # Read-only on the form (`WS-21` draws TEMPLATE as a fixed row): the
        # order's collections were copied at the raise and re-pointing them is
        # not an edit, it is a new order. Wave H owns the copies.
        "template_id": str(order.template_id) if order.template_id else None,
        # `BR-WRK-018` — a Complete order refuses a priority change, and the
        # screen needs to know that BEFORE the dispatcher presses Save so it can
        # disable the control rather than answer a 400 into a dialog.
        "priority_locked": order.dispatch_state == metering_seam.dispatch_tokens().COMPLETE,
    }


def _changed(order: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """Which of the form's fields actually MOVED — not which were submitted.

    ⚠ **THE DIFFERENCE IS THE WHOLE OF `US-WRK-031` TC-6.** A browser posts the
    entire form, so every field arrives on every Save. Auditing what was POSTED
    would write seven rows for a dispatcher who changed one, and — far worse —
    would fire the customer notification on a Save that touched only the notes,
    because `window_start` was "submitted". The customer would be told their
    visit moved to the time it already was.
    """
    moved: dict[str, Any] = {}
    if "dispatch_state" in payload:
        value = str(payload["dispatch_state"] or "").strip()
        if value and value != order.dispatch_state:
            if value not in metering_seam.dispatch_tokens().ALL:
                raise errors.ValidationError(
                    errors.VAL_UNKNOWN_LOOKUP,
                    message_key="work.edit.dispatch_state_unknown",
                    br_ref="BR-WRK-023",
                    params={"state": value},
                )
            if value == metering_seam.dispatch_tokens().COMPLETE:
                # ⚠ RULING 18 (`CR-168-BRC10` P1.34, `DEF-WRK-9525`): the back
                # office never completes a job, it only accepts. This was the
                # second office door — the Status list's *Complete* — and the
                # server refuses it here as metering refuses the first.
                raise errors.ValidationError(
                    errors.VAL_RANGE,
                    message_key="work.order.closed_by_field_only",
                    br_ref="BR-MET-110",
                    params={"order_no": order.order_no or ""},
                )
            moved["dispatch_state"] = value
    if "priority_id" in payload:
        value = payload["priority_id"] or None
        if str(value or "") != str(order.priority_id or ""):
            moved["priority_id"] = value
    for field in ("due_at", "window_start", "window_end"):
        if field in payload:
            value = metering_seam.parse_moment(payload[field], field=field)
            if value != getattr(order, field):
                moved[field] = value
    if "area_id" in payload:
        value = payload["area_id"] or None
        if str(value or "") != str(order.area_id or ""):
            moved["area_id"] = value
    if "technician_notes" in payload:
        value = payload["technician_notes"]
        value = str(value).strip() if value is not None and str(value).strip() else None
        if value != order.technician_notes:
            moved["technician_notes"] = value
    if "custom_data" in payload:
        # Merged, never replaced: a field placed Input here and left untouched
        # keeps its stored answer, a blank clears it, and an answer typed on
        # New work order that this form does not draw is kept as it was.
        stored = dict(order.custom_data or {})
        merged = tenancy_seam.validate_custom_answers(
            "work_orders", payload["custom_data"] or {}, screen=CUSTOM_SCREEN, existing=stored
        )
        if merged != stored:
            moved["custom_data"] = merged
    if "technician_id" in payload or "crew_id" in payload:
        wanted_tech = str(payload.get("technician_id") or "")
        wanted_crew = str(payload.get("crew_id") or "")
        if wanted_tech != str(order.assignee_technician_id or "") or wanted_crew != str(
            order.assignee_crew_id or ""
        ):
            moved["assignee"] = {"technician_id": wanted_tech, "crew_id": wanted_crew}
    return moved


def _audit_field(actor: Any, order: Any, field: str, before: Any, after: Any) -> None:
    """One row per field, naming who and when — `BR-WRK-031`'s confirmed half.

    `when` is not passed: `audit_log` stamps its own moment, which is the only
    clock that cannot be handed a wrong value by a caller.
    """
    core_audit.write_row(
        action="work.order.field_changed",
        entity_type="work_order",
        entity_id=order.id,
        actor_user_id=dispatch._actor_id(actor),
        before={"field": field, "value": before},
        after={"field": field, "value": after, "order_no": order.order_no},
    )


def save_order_edit(actor: Any, order_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`PATCH /work-orders/{id}` — **ONE Save, one transaction, one box.**

    ⚠ **A REFUSAL ANYWHERE ROLLS THE WHOLE SAVE BACK, AND THAT IS A CHOICE.**
    The alternative — apply what is valid and report what is not — reads as
    helpful and is wrong here: a dispatcher who moved the window AND raised the
    priority, and whose priority change was refused because the job is
    Complete, would have sent the customer a message about a change that half
    happened. The Change effects box promised three things; a partial Save keeps
    one of them. So: one `atomic()`, and the customer send is INSIDE it.

    ⚠ **ORDER MATTERS AND IT IS NOT ALPHABETICAL.** The assignee moves first,
    because `_refresh_cache` writes `window_start`/`window_end` when they ride
    an act, and the schedule act must not then be re-writing values the
    assignment already moved. The customer send is LAST, after every column is
    final, so the message can quote what was actually saved rather than what was
    about to be.
    """
    order = _order_or_404(order_id)
    body = dict(payload or {})
    unknown = sorted(set(body) - set(EDITABLE_FIELDS))
    if unknown:
        # The same posture `BR-WRK-026` takes on the list's seventh filter: a
        # field silently dropped is a dispatcher believing they changed
        # something they did not.
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="work.edit.field_unknown",
            params={"field": unknown[0]},
        )

    reason = str(body.pop("reason", None) or "").strip() or None
    moved = _changed(order, body)
    if (
        "assignee" in moved
        and (order.assignee_technician_id or order.assignee_crew_id)
        and reason is None
    ):
        # P4.4 — the holder moves AWAY from somebody: say why. Refused before
        # the transaction, so nothing is written and no `WO-` state moves.
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="work.dispatch.reason_required",
            br_ref="BR-WRK-025",
        )
    if not moved:
        # Nothing changed: no audit row, no message, no history. A Save that
        # writes an audit row saying nothing moved makes the audit tab unusable
        # — it is the log a supervisor reads to find what happened.
        return {
            "order_no": order.order_no,
            "changed": [],
            "audit_rows": 0,
            "reschedule_notice": None,
            "br_ref": "BR-WRK-031",
        }

    before_window = _window_label(order)
    before_due = order.due_at
    changed_fields: list[str] = []
    audit_rows = 0
    notice: dict[str, Any] | None = None
    #: The assignment row this Save handed to somebody, or None. `DEF-WRK-4041`:
    #: the push is enqueued AFTER the transaction below commits, so it is
    #: carried out of the block rather than fired inside it.
    pending_push: tuple[Any, Any] | None = None

    with transaction.atomic():
        # ── 1 · WHO HOLDS IT — two history rows, ONE field ──────────────────
        if "assignee" in moved:
            was = (dispatch._holder(order) or {}).get("name")
            group = None
            if order.assignee_technician_id or order.assignee_crew_id:
                # `BR-WRK-025`: the history records that somebody LOST the job.
                # Recording only the gain would leave *"who had WO-4821 on
                # Tuesday morning"* unanswerable, which is the question the
                # append-only table exists to answer.
                #
                # `CR-168-BRC10` P4.4 (judgment J2): and it says WHY. The
                # `unassign` and the `assign` that follows share the reason and
                # one `act_group`, so the Audit reads ONE reassign. A move off
                # somebody without a reason is refused before anything is
                # written (checked above the transaction).
                group = uuid.uuid4()
                dispatch.append_act(actor, order, "unassign", reason=reason, act_group=group)
            wanted = moved["assignee"]
            if wanted["technician_id"] or wanted["crew_id"]:
                technician, crew = dispatch._candidate_or_refuse(
                    order,
                    {
                        "technician_id": wanted["technician_id"] or None,
                        "crew_id": wanted["crew_id"] or None,
                    },
                )
                assigned_row = dispatch.append_act(
                    actor,
                    order,
                    "assign",
                    technician=technician,
                    crew=crew,
                    scheduled_for=moved.get("due_at"),
                    window_start=moved.get("window_start"),
                    window_end=moved.get("window_end"),
                    reason=reason if group is not None else None,
                    act_group=group,
                )
                # P4.6 🔒 — an assignment against the advice is RECORDED, never
                # refused (ruling 2, PO answer 2). The same writer the row
                # action uses, so the two doors cannot disagree.
                dispatch._audit_against_advice(actor, order, assigned_row, technician, crew)
                # The PUSH is enqueued after this transaction commits — see
                # below. Held here only so it can name the assignment row.
                pending_push = (assigned_row, technician)
            _audit_field(actor, order, "technician", was, (dispatch._holder(order) or {}).get("name"))
            changed_fields.append("technician")
            audit_rows += 1

        # ── 2 · WHEN — one `schedule` act, ONE field ────────────────────────
        schedule_moved = [f for f in ("due_at", "window_start", "window_end") if f in moved]
        if schedule_moved and "assignee" not in moved:
            dispatch.append_act(
                actor,
                order,
                "schedule",
                technician=order.assignee_technician,
                crew=order.assignee_crew,
                scheduled_for=moved.get("due_at"),
                window_start=moved.get("window_start"),
                window_end=moved.get("window_end"),
            )
        if schedule_moved:
            # `_refresh_cache` only ever WRITES a value it was handed, so a
            # window CLEARED on the form (Any time) needs the explicit write.
            for field in schedule_moved:
                setattr(order, field, moved[field])
            metering_seam.save_order_fields(order, schedule_moved)
            _audit_field(
                actor,
                order,
                "schedule",
                {"due_at": before_due.isoformat() if before_due else None, "window": before_window},
                {
                    "due_at": order.due_at.isoformat() if order.due_at else None,
                    "window": _window_label(order),
                },
            )
            changed_fields.append("schedule")
            audit_rows += 1

        # ── 3 · THE PROMISE — delegated, because it re-dates ────────────────
        if "priority_id" in moved:
            # `dispatch.change_priority` refuses a Complete order, re-dates
            # `due_at` from the ORIGINAL raise (never from now — that would
            # silently forgive lateness every time a priority was corrected) and
            # writes its own audit row. Re-implementing any of that here is the
            # parallel world the PO ruled against on 2026-09-05.
            dispatch.change_priority(actor, order.id, {"priority_id": moved["priority_id"]})
            order.refresh_from_db()
            changed_fields.append("priority")
            audit_rows += 1

        # ── 4 · WHERE ON THE RUN — delegated for the same reason ────────────
        if "dispatch_state" in moved:
            dispatch.set_dispatch_state(
                actor, order.id, moved["dispatch_state"], "work.order.state_changed"
            )
            order.refresh_from_db()
            changed_fields.append("dispatch_state")
            audit_rows += 1

        # ── 5 · THE PLAIN COLUMNS ───────────────────────────────────────────
        if "area_id" in moved:
            was = order.area.name if order.area_id else None
            # `BR-WRK-022` — areas are `tenancy.Area` and this must never accept
            # an id from another utility's list. `tenancy_seam.areas()` is the
            # SAME tenant-scoped read the Area filter chip is built from, reused
            # rather than re-queried: a second reader is the drift the PO ruled
            # against on 2026-09-05. An id that is not in it is a 404, not a
            # silent write of a foreign area onto this tenant's order.
            if moved["area_id"]:
                known = {row["id"] for row in dispatch.tenancy_seam.areas()}
                if str(moved["area_id"]) not in known:
                    raise errors.NotFoundError()
            order.area_id = moved["area_id"] or None
            metering_seam.save_order_fields(order, ["area"])
            order.refresh_from_db()
            _audit_field(actor, order, "area", was, order.area.name if order.area_id else None)
            changed_fields.append("area")
            audit_rows += 1

        if "custom_data" in moved:
            was = dict(order.custom_data or {})
            order.custom_data = moved["custom_data"]
            metering_seam.save_order_fields(order, ["custom_data"])
            _audit_field(actor, order, "custom_data", was, order.custom_data)
            changed_fields.append("custom_data")
            audit_rows += 1

        if "technician_notes" in moved:
            was = order.technician_notes
            order.technician_notes = moved["technician_notes"]
            metering_seam.save_order_fields(order, ["technician_notes"])
            _audit_field(actor, order, "technician_notes", was, order.technician_notes)
            changed_fields.append("technician_notes")
            audit_rows += 1

        # ── 6 · THE CUSTOMER, LAST, AND ONLY IF THE PROMISE MOVED ───────────
        if NOTIFYING_FIELDS & set(moved):
            notice = notify_reschedule(actor, order, before_window=before_window)

    # ── 7 · THE TECHNICIAN'S PHONE — `DEF-WRK-4041`, `BR-WRK-034` ───────────
    #
    # ⚠ **OUTSIDE THE TRANSACTION, AND THIS CALL IS THE DEFECT'S WHOLE FIX.**
    # `Work-021`'s Change effects box tells the dispatcher *"Technician phone —
    # job updates immediately"*. It said so from the day this screen shipped and
    # nothing here pushed anything: `record_act` (the dispatcher list's row
    # action) was the only door that enqueued `work.push`, and this screen
    # reassigns through `append_act`, which appends the history row and the
    # cache and enqueues nothing. R. Patel still got the job on his next
    # ordinary sync, so nothing anywhere looked wrong — which is exactly why it
    # would have survived (hard-won law 2's mirror).
    #
    # It is AFTER the `atomic()` block for the reason written at the other call
    # site: `core.jobs.enqueue` writes the job row and then hands it to the
    # broker, and inside an open transaction an eager worker would look up a job
    # id the database has not committed yet.
    push_job = None
    if pending_push is not None:
        row, technician = pending_push
        push_job = dispatch.push_after_assign(row, order, "assign", technician, actor)

    return {
        "order_no": order.order_no,
        "changed": changed_fields,
        "audit_rows": audit_rows,
        "reschedule_notice": notice,
        # `US-WRK-030` TC-4 and `DEF-WRK-4041`: a caller (and the test) can see
        # that this door pushed, without reaching into the job store. None when
        # the Save moved no assignee.
        "push_job_id": push_job,
        "br_ref": "BR-WRK-031",
    }


def notify_reschedule(actor: Any, order: Any, *, before_window: str | None) -> dict[str, Any]:
    """**The customer is told the visit moved — `OQ-WRK-1495`, option (a).**

    ⚠ **THIS FUNCTION WAS SPECIFIED AS A STUB AND IT IS NOT ONE.** `CR-070`'s
    execution plan told wave I to write `raise
    NotImplementedError("OQ-WRK-1495")` here and put
    `reschedule_notice_kind_unruled` on the response. The question closed on
    2026-09-04 — one day before this wave started and one day after the plan row
    was written — and six documents still said OPEN when this lane ran r11 step
    0 (`DEF-WRK-4028`). **PO verbatim:** *"(a) — filing an appointment change
    beside disconnection notices distorts every monthly report"*.

    ⛔ **THE KIND IS `appointment` AND SENDING IT AS `notice` IS THE ONE WAY TO
    GET THIS WRONG.** `notice` is the nearest existing kind, the customer would
    read identical words either way, and the damage lands somewhere nobody
    looks: a monthly count of notices — the number that includes disconnection
    letters — quietly inflated by every appointment change. `US-WRK-031` TC-5
    asserts the kind BY NAME for exactly that reason.

    **`source_id` is the WORK ORDER's own id.** The queue's unique key is
    `(tenant, source_type, source_id, channel, copy_no)`, so this makes a second
    message about the SAME order dedupe into the first at `copy_no = 0`. That is
    the correct default and the same choice `move` made for its own reason: a
    dispatcher who nudges a window three times while a customer is on the phone
    should not put three letters in the post. A deliberate re-send is what
    `copy_no` is for.

    ⚠ **IT NEVER REPORTS A MESSAGE IT DID NOT QUEUE** (hard-won law 1). An
    unwired queue, a refusal, or an order with nobody to write to each come back
    as `queued: False` with the reason, and the screen says so rather than
    showing a tick.
    """
    # ⚠ **SINCE 2026-10-04 (`CR-168-BRC10` P6.1, lane SRV-5) THIS GOES THROUGH
    # THE ONE CUSTOMER PATH**, `visit_notices.tell_customer` → Notifications'
    # `visit_moved` event: the customer's own channels (email / SMS as they
    # elected), the utility's switch, the do-not-send list and a real template.
    # Until then it queued an `in_app` row with NO template for a CUSTOMER —
    # a channel the customer has no inbox on, rendered from nothing. The kind is
    # still `appointment` (`OQ-WRK-1495`). A job never told it was booked is
    # told it is BOOKED rather than that it moved from a time nobody gave them.
    from apps.work import visit_notices

    kind = "moved" if visit_notices._booked_before(order) else "booked"
    told = visit_notices.tell_customer(
        order,
        kind,
        discriminator=visit_notices.window_key(order) if kind == "moved" else "",
        actor=actor,
    )
    code = (told or {}).get("code")
    if code not in ("visit_message_queued", "visit_message_already_queued"):
        # It NEVER reports a message it did not queue (hard-won law 1).
        return {
            "queued": False,
            "reason": (
                "no_customer_on_this_order"
                if code == "visit_message_no_customer"
                else code or "notifications.queue_document is not wired"
            ),
            "source_type": notifications_seam.SOURCE_APPOINTMENT,
        }
    core_audit.write_row(
        action="work.order.customer_notified",
        entity_type="work_order",
        entity_id=order.id,
        actor_user_id=dispatch._actor_id(actor),
        after={
            "source_type": notifications_seam.SOURCE_APPOINTMENT,
            "window_now": _window_label(order),
            "order_no": order.order_no,
            "br_ref": "BR-WRK-031",
        },
    )
    return {
        "queued": True,
        "source_type": notifications_seam.SOURCE_APPOINTMENT,
        "window_now": _window_label(order),
    }
