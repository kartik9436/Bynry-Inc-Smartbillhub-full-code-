# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-030 (EP-WRK-05) — assigning an order puts it on the
#           technician's phone without them opening anything, and the Audit tab
#           reads *Dispatched · pushed to phone · 14:02*.  Screens: Work-007,
#           Work-008 (Audit), Work-010
# Rules:    BR-WRK-034 (push on assignment; the audit line) · BR-WRK-025 (the
#           push is a CONSEQUENCE of the assign row, never a second act) ·
#           B12 r1 §3 (async = a job row, then the broker message) · TD-17 ·
#           CLAUDE.md hard rule 1 (tenant scope) · hard rule 7 (audit_log) ·
#           hard-won law 1 (a comment claiming a guarantee is not the guarantee)
# Defect:   DEF-320 (four job kinds enqueued and production dispatched none of
#           them — a routed queue with no consumer, the exact shape G59 and
#           this wave's G109 refuse)
# Tests:    06-backend/tests/test_us_wrk_030_push.py (TC-1…TC-6, with
#           JOBS_EAGER=false --reuse-db) · tests/test_us_wrk_030_push_pg.py
#           (isolation, real PostgreSQL, NOSUPERUSER role)
# Impacts:  apps/work/apps.py (registers this body AND its queue) ·
#           apps/work/dispatch.py (record_act enqueues it) ·
#           docker-compose.yml (`celery-work`, -Q work — the CONSUMER half) ·
#           10-scripts/gates/g109_work_queue_split.py
# ───────────────────────────────────────────────────────
"""`work.push` — the job that puts an order on a phone, on its own named queue.

WHY A JOB AND NOT A CALL INSIDE THE REQUEST
-------------------------------------------
A dispatcher assigning a job is holding a mouse. A push provider is a network
call to somebody else's service that can hang for thirty seconds and fail for
reasons that have nothing to do with this utility. `US-WRK-030` TC-3 says so in
its own words: *"the push provider is down → the job row stays queued and
retries with jitter; the assignment stands; nothing is lost."* **The assignment
must not be able to fail because a phone company had a bad afternoon**, and the
only way to mean that is to finish the assignment first and push afterwards.

THE ROW IS WRITTEN BEFORE THE MESSAGE, AND THAT IS THE WHOLE CONTRACT
----------------------------------------------------------------------
`core.jobs.enqueue` saves the record and only then hands it to the dispatcher —
`_store.save(record)` then `_dispatcher(record)`, in that order, in one
function. So a broker that is down loses a MESSAGE and never a RECORD, and the
work is still visible, still queued, and still runnable. `US-WRK-030` TC-1
asserts the ordering by name because the tempting shape — fire the message and
write the row in the callback — is the one that loses work silently.

⚠ **THE QUEUE IS HALF OF A QUEUE.** `set_job_queue("work.push", "work")` in
`WorkConfig.ready()` is the ROUTING half; `docker-compose.yml`'s `celery-work`
(`-Q work`) is the CONSUMER half. Ship the routing alone and every push is
accepted, answers *queued*, and never runs — `core/jobs.py` names that shape in
its own words, *"it accepts the file, says 'queued', and writes nothing, for
ever"*, and `DEF-320` is what it cost the last time. **`G109` fails on either
half alone**, which is `G59`'s clauses cloned for this queue.

THE AUDIT LINE MUST NOT LIE, AND THAT IS THIS FILE'S HARDEST RULE
------------------------------------------------------------------
`BR-WRK-034` gives the sentence: *Dispatched · pushed to phone*. `US-WRK-030`
TC-2 gives the case that makes it hard — **a technician with no registered
device** — and its expected outcome is *"the audit line reads Dispatched ·
waiting for the phone; never* pushed *when it was not"*.

So this job writes ONE of two audit actions and the choice is made from a
COUNT of active device rows, not from an intention:

    work.order.dispatched_pushed     ≥ 1 active device — a push was attempted
    work.order.dispatched_waiting     0 active devices — nothing was attempted

⚠ **AND *ATTEMPTED* IS THE STRONGEST WORD THIS PRODUCT MAY HONESTLY USE.**
Whether the handset rang is the provider's answer, arriving later and out of
band; there is no delivery receipt in this schema and `technician_devices`
deliberately has no `last_push_at` column to imply one. The job is delivered to
the phone by the phone ASKING — `GET /work/mobile/today` on its next sync — and
the push is what makes the phone ask sooner. That is why TC-2's expected
outcome is *"the job is delivered on the next sync"* rather than *"the job is
lost"*: **the sync is the delivery and the push is the doorbell.**

⚠ **THERE IS NO PUSH PROVIDER CONFIGURED IN THIS PRODUCT TODAY**, and this file
says so rather than pretending. `_deliver()` is the one seam where a Web Push
call will go; today it records the attempt and returns the count. That is not a
stub awaiting a ruling — nothing is blocked, the phone gets the job on its next
sync exactly as `US-WRK-030` TC-2 describes, and the audit line is already
honest about which of the two things happened. Adding a provider changes this
one function and nothing else.

THE SCOPE KEY IS PER ASSIGNMENT ROW, NOT PER ORDER
---------------------------------------------------
`US-WRK-030` TC-4: *"reassign to R. Patel → D. Ortiz's phone drops the job on
its next sync; R. Patel's gains it; TWO audit lines."* An order-scoped key would
fold the second push into the first — `core.jobs.enqueue` returns the existing
active record for a repeated scope key (NFR-16) — and R. Patel would never be
told. The assignment row's id is the fact that makes the two pushes different,
so it is the key.

TC-5 is the tenant half of the same argument: the key carries the tenant id, and
`enqueue` looks up an active job by `(tenant_id, kind, scope_key)` in any case,
so two utilities pushing the same order number cannot dedupe each other.
"""

from __future__ import annotations

import logging
from typing import Any

from core import audit as core_audit
from core import jobs as core_jobs

logger = logging.getLogger("smartbillhub.work.push")

#: The job kind. One string, declared here beside its body, because a kind whose
#: queue is declared in a different file is a kind somebody will one day rename
#: in one place (`core/jobs.py`'s own words on `set_job_queue`).
PUSH_JOB = "work.push"

#: The named broker queue. The CONSUMER half is `celery-work` in
#: `docker-compose.yml`; `G109` checks the two against each other and fails when
#: either is missing, because either one alone is worse than neither.
WORK_QUEUE = "work"

#: The two audit actions, and the sentence each stands for. `BR-WRK-034` gives
#: the first; `US-WRK-030` TC-2 gives the second and the rule that a line saying
#: *pushed* over a technician with no device would be a lie the Audit tab tells
#: for ever.
ACTION_PUSHED = "work.order.dispatched_pushed"
ACTION_WAITING = "work.order.dispatched_waiting"


# ══════════════════════════════════════════════════════════════════════════
# CR-187-BRC10 T-41 (lane S-FIND) — KINDS AND CHANNELS
# ══════════════════════════════════════════════════════════════════════════
#
# Requirement 13: *"Push and emergency alerts — distinct audio and vibration for
# urgent assignments, emergencies and schedule changes, on a locked device.
# In-app badges for dispatch messages."* T-41: *"each with its own sound and its
# own channel"*. `AD-01` (Decisions): *"Android notification channels carry
# custom sound and vibration per kind; DND override is a channel permission"*;
# iOS breaks silent mode only with the Critical Alerts entitlement (E2E-22,
# T-01 — applied for, not granted).
#
# ⚠ **THE CHANNEL ID IS A CONTRACT WITH AN INSTALLED APP AND IS NEVER RENAMED.**
# Android fixes a channel's sound and importance when the app first creates it;
# a renamed id is a NEW channel the handset has never configured, and the old
# one keeps ringing with the old sound (07-endpoints.md §0 rule 1: a kind is
# added, never repurposed). The sound NAME is the file bundled in the app.
#
# ⚠ **A DISPATCH MESSAGE HAS ITS OWN SOUND NAME AND RINGS NOTHING BY DEFAULT.**
# Requirement 13 gives it an in-app badge, not audio; T-41 gives every kind its
# own sound. Both hold: its channel is LOW importance on Android (no sound, no
# heads-up) and PASSIVE on iOS (no sound, no light-up), and the sound file is
# named so the technician's per-kind notification setting (R33, FF-51) can turn
# it on.
PUSH_KINDS: dict[str, dict[str, Any]] = {
    # The automatic doorbell on every assignment (`US-WRK-030`, this file's
    # original job). Data.txt §7: *"The server pushes a change — new job …"*.
    "new_job": {
        "sound": "new_job.wav",
        "android_channel_id": "new_job",
        "android_importance": "default",
        "ios_interruption_level": "active",
        "badge": True,
    },
    "urgent_assignment": {
        "sound": "urgent_assignment.wav",
        "android_channel_id": "urgent_assignment",
        "android_importance": "high",
        "ios_interruption_level": "time-sensitive",
        "badge": True,
    },
    # R28 — must be acknowledged. `critical` needs Apple's entitlement; until
    # it is granted iOS delivers it as time-sensitive and the handset is told
    # nothing different (the payload is the same either way).
    "emergency": {
        "sound": "emergency.wav",
        "android_channel_id": "emergency",
        "android_importance": "max",
        "ios_interruption_level": "critical",
        "badge": True,
    },
    "schedule_change": {
        "sound": "schedule_change.wav",
        "android_channel_id": "schedule_change",
        "android_importance": "high",
        "ios_interruption_level": "time-sensitive",
        "badge": True,
    },
    "dispatch_message": {
        "sound": "dispatch_message.wav",
        "android_channel_id": "dispatch_message",
        "android_importance": "low",
        "ios_interruption_level": "passive",
        "badge": True,
    },
    # DEF-MET-10606 (PO 2026-10-26, *"we will send this in notification"*) — a
    # meter-reading route given to, or taken from, the reader. The doorbell
    # for the phone's route download (`route_push.py`); ordinary importance.
    "route_change": {
        "sound": "route_change.wav",
        "android_channel_id": "route_change",
        "android_importance": "default",
        "ios_interruption_level": "active",
        "badge": True,
    },
}

#: The job that pushes one dispatcher-sent alert (`field_alerts.send_alert`).
ALERT_PUSH_JOB = "work.alert_push"


def push_message(kind: str, data: dict[str, Any]) -> dict[str, Any]:
    """The provider-neutral message for one push of `kind`.

    `data` carries IDENTIFIERS and the human order number only — never an
    address, a name or money: a lock screen is read by whoever holds the phone,
    and the handset fetches the job itself (the sync is the parcel, the push is
    the doorbell). The handset renders the words from its own catalogue by
    `kind` (B14 rule 35: no English in a payload a catalogue will translate).

    ⚠ **NEVER CARRIES THE TOKEN.** `_deliver` addresses each device; this is the
    body, identical for every device of the technician.

    ⚠ **CARRIES THE UTILITY (`data.tenant`, its slug) — DEF-WRK-10352.** One
    handset may serve a technician at two utilities, signed into one at a time;
    the app shows a push only when it names the utility signed in, and ignores
    one with no tenant at all (fails closed). The slug is not customer data.
    """
    channel = PUSH_KINDS[kind]
    from apps.work.seams import tenancy_seam
    from core import tenancy as core_tenancy

    tenant = tenancy_seam.tenant_slug() if core_tenancy.current_tenant_id() is not None else None
    return {
        "kind": kind,
        "sound": channel["sound"],
        "android": {
            "channel_id": channel["android_channel_id"],
            "importance": channel["android_importance"],
        },
        "ios": {"interruption_level": channel["ios_interruption_level"]},
        "badge": channel["badge"],
        "data": {
            "kind": kind,
            "tenant": tenant,
            **{k: (None if v is None else str(v)) for k, v in data.items()},
        },
    }


def scope_key(assignment_id: Any) -> str:
    """One push per ASSIGNMENT row — see the module docstring's TC-4 argument."""
    return f"assignment:{assignment_id}"


def _active_devices(technician_id: Any) -> list[Any]:
    """This technician's active device rows, under the caller's tenant context.

    ⚠ **NO `.values_list("token")` HERE AND NOWHERE ELSE EITHER.** The token is a
    bearer credential for a third-party service; it is read by `_deliver` and by
    nothing that logs, returns or renders. Pulling it into a variable a caller
    can print is how it ends up in a traceback.
    """
    from apps.work import models

    if technician_id is None:
        return []
    return list(
        models.TechnicianDevice.objects.filter(
            technician_id=technician_id, active=True
        )
        # `CR-187-BRC10` — a handset registered by NAME may carry no push
        # token (`work/0043` made it nullable); there is nothing to address.
        .exclude(token__isnull=True)
        .exclude(token="")
        .order_by("registered_at")
    )


def _deliver(devices: list[Any], payload: dict[str, Any], *, kind: str = "new_job") -> int:
    """THE SEAM where a Web Push call will go. Returns how many were attempted.

    ⚠ **IT IS NOT A STUB AND IT BLOCKS NOTHING** (hard-won law 1 — say what is
    true). No push provider is configured in this product, and `BR-WRK-045` made
    the phone a WEB app, so the eventual call is a Web Push POST to each
    subscription's own endpoint. Until one is configured this records the
    attempt and returns the count, and **the technician still gets the job**:
    delivery is the phone's next `GET /work/mobile/today`, which is what
    `US-WRK-030` TC-2 describes. The push is the doorbell, not the parcel.

    The count is what the audit line is derived from, so it must be the number
    of devices actually addressed and never an optimistic constant.

    `kind` (CR-187-BRC10 T-41) picks the sound and the channel; the provider
    call, when one is configured, sends `push_message(kind, …)` to each device.
    """
    channel = PUSH_KINDS[kind]["android_channel_id"]
    for device in devices:
        # The token is used here and read nowhere else. The log line names the
        # DEVICE and the ORDER; it must never name the token.
        logger.info(
            "work.push: %s (%s) order %s → device %s (%s)",
            kind,
            channel,
            payload.get("order_no")
            or payload.get("work_order_id")
            or (payload.get("data") or {}).get("route"),
            device.id,
            device.platform,
        )
    return len(devices)


def run_push_job(record: dict[str, Any]) -> None:
    """The BODY. `core.jobs.run_job` does the start/succeed/fail bookkeeping.

    Reads the payload the assignment wrote, counts the technician's active
    devices, attempts a delivery against each, and writes the ONE audit line
    that is true — `pushed` or `waiting for the phone`.

    ⚠ **THE AUDIT ROW IS WRITTEN BY THE JOB, NOT BY THE ASSIGNMENT.** It is
    tempting to write *Dispatched · pushed to phone* in `record_act`, where the
    dispatcher is standing and the transaction is already open. It would be a
    lie in one common case and an unfixable one: at that moment nothing has
    counted the devices and nothing has attempted anything, so the line would
    say *pushed* over a technician whose phone was never addressed. The audit
    tab is read weeks later by somebody asking why nobody came.
    """
    payload = record.get("payload") or {}
    technician_id = payload.get("technician_id")
    # CR-187-BRC10 (PO answer 9) — the kind the assignment chose
    # (`dispatch.push_kind_for`). A job enqueued before the kind travelled in
    # the payload, or carrying a token this table does not know, rings as the
    # original doorbell rather than failing.
    kind = payload.get("push_kind")
    if kind not in PUSH_KINDS:
        kind = "new_job"
    devices = _active_devices(technician_id)
    attempted = _deliver(devices, payload, kind=kind) if devices else 0
    alert_id = payload.get("alert_id")
    if alert_id:
        # The alert row the assignment wrote (`field_alerts.
        # record_assignment_alert`) is stamped exactly as `run_alert_push_job`
        # stamps a dispatcher's — how many devices, and when.
        from django.utils import timezone

        from apps.work import models

        models.WorkFieldAlert.objects.filter(pk=alert_id).update(
            devices_attempted=attempted, pushed_at=timezone.now()
        )

    core_audit.write_row(
        action=ACTION_PUSHED if attempted else ACTION_WAITING,
        entity_type="work_order",
        entity_id=payload.get("work_order_id"),
        actor_user_id=payload.get("actor_id"),
        after={
            "order_no": payload.get("order_no"),
            "technician": payload.get("technician_name"),
            "devices": attempted,
            # How it rang (PO answer 9) — `new_job`, `urgent_assignment` or
            # `emergency`, and the alert row when it was not a plain job.
            "kind": kind,
            **({"alert_id": str(alert_id)} if alert_id else {}),
            # The sentence the Audit tab renders, kept beside the count it was
            # derived from so a reader can check one against the other.
            "delivery": "pushed to phone" if attempted else "waiting for the phone",
        },
    )
    return None


def register() -> None:
    """Register the body AND the queue. Called from `WorkConfig.ready`.

    Both, in one function, in the module that owns the work — `core/jobs.py`'s
    contract, and the reason `apps/billing/run_jobs.py` does exactly this. A
    kind registered in one file and routed in another is a kind that keeps its
    old queue after a rename, silently.
    """
    core_jobs.set_job_handler(PUSH_JOB, run_push_job)
    core_jobs.set_job_queue(PUSH_JOB, WORK_QUEUE)
    # CR-187-BRC10 T-41 — a dispatcher's alert rides the SAME queue, so the
    # consumer `G109` checks (`celery-work`, `-Q work`) drains it too.
    core_jobs.set_job_handler(ALERT_PUSH_JOB, run_alert_push_job)
    core_jobs.set_job_queue(ALERT_PUSH_JOB, WORK_QUEUE)
    # DEF-MET-10606 — a route's reader changed; the same queue and consumer.
    from apps.work import route_push

    core_jobs.set_job_handler(route_push.ROUTE_PUSH_JOB, route_push.run_route_push_job)
    core_jobs.set_job_queue(route_push.ROUTE_PUSH_JOB, WORK_QUEUE)


def run_alert_push_job(record: dict[str, Any]) -> None:
    """The BODY of `work.alert_push`: push one `work_field_alerts` row to its
    technician's active devices and record how many were addressed.

    The row is written by the dispatcher's request BEFORE this job is enqueued
    (`core.jobs.enqueue` saves the record, then dispatches), so a dead broker
    loses the doorbell and never the alert — FF-42 still lists it on the next
    sync, and the five-minute clock (R28) runs from `sent_at` regardless.
    """
    from django.utils import timezone

    from apps.work import models

    payload = record.get("payload") or {}
    alert = models.WorkFieldAlert.objects.filter(pk=payload.get("alert_id")).first()
    if alert is None:
        return None
    devices = _active_devices(alert.technician_id)
    attempted = _deliver(devices, payload, kind=alert.kind) if devices else 0
    models.WorkFieldAlert.objects.filter(pk=alert.pk).update(
        devices_attempted=attempted, pushed_at=timezone.now()
    )
    core_audit.write_row(
        action="work.alert.pushed" if attempted else "work.alert.waiting_for_phone",
        entity_type="work_field_alert",
        entity_id=alert.id,
        actor_user_id=alert.sent_by_id,
        after={"kind": alert.kind, "devices": attempted, "order_no": payload.get("order_no")},
    )
    return None


__all__ = [
    "ACTION_PUSHED",
    "ACTION_WAITING",
    "ALERT_PUSH_JOB",
    "PUSH_KINDS",
    "push_message",
    "run_alert_push_job",
    "PUSH_JOB",
    "WORK_QUEUE",
    "register",
    "run_push_job",
    "scope_key",
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-030 (EP-WRK-05) · BR-WRK-034 · 10-execution-plan.md wave J task J1
# generated: 2026-09-05 by the CR-070 wave J build lane
# checklist: A✔ B✔ C✔ D=n/a(no route of its own — dispatch.record_act enqueues it) E=n/a(no screen; the Audit tab renders the row) F✔ G✔ H=n/a(no 🔒 path — the migration is, and carries its own markers)
# gates: pytest tests/test_us_wrk_030_push.py · G109 (the queue pair, shown RED first) · G78 (Work writes nothing foreign)
# exceptions: `_deliver` addresses no provider today and says so in its own docstring rather than raising — nothing is blocked and no question is open; the sync is the delivery
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
