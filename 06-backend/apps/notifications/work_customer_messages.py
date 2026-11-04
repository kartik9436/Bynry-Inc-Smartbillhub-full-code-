# ── Trace ──────────────────────────────────────────────
# Change:   CR-168-BRC10 round 6, lane SRV-5 — P6.1 (tell the consumer: booked,
#           moved, on the way, done), P6.4/P6.7 (the tenant chooses per event —
#           on Settings → Notifications, the ONE home, never a Work table),
#           P6.5 (four consumer kinds in the catalogue), P6.6 (no message
#           without a rule). Ruling 3 (23 Sep): *"Notification reaches the
#           consumer and the back office, and work orders print"*.
# Rules:    BR-NOT-017 (one home: every message is a catalogue row with the
#           utility's own switch) · BR-NOT-005 (queue only; the do-not-send
#           list HOLDS a row, `DEF-NOT-5632`) · BR-NOT-006 (the pin's language
#           is the UTILITY's default) · OQ-WRK-1495 (the kind is `appointment`,
#           never `notice`) · CLAUDE.md hard rule 8 (the address is the
#           PREMISES', walked by the caller) · rule 6 (idempotent) · hard-won
#           law 14 (the savepoint)
# Tests:    06-backend/tests/test_cr168_srv5_messages.py
# Impacts:  rule_catalog.py (the four customer events) · catalogs.py +
#           seed_templates.py (four new classes) · apps/work/visit_notices.py
#           (the one caller, through apps/work/seams/notifications_seam.py)
# ───────────────────────────────────────────────────────
"""The customer told about a visit — booked, moved, on the way, done.

WHICH CHANNEL, AND WHO DECIDES
────────────────────────────────────────────────────────────────────────────
Three answers intersect, in this order, and each can only REMOVE:

1. **The event offers a channel** (`rule_catalog`): booked and moved by email
   and SMS, on the way by SMS, done by email.
2. **The customer can be reached on it, the way a bill decides** — EMAIL
   whenever an email is on file (or the customer chose paperless), SMS only
   with the customer's SMS consent (`accounts.sms_reminders`). One read for
   both: `customers.selectors.delivery_channel_election_for_account`, the
   bill's own election (`DEF-BIL-10535`).
   ⚠ **AMENDED 2026-10-29 (`DEF-WRK-10663`, PO ruling B1 A, verbatim *"B1
   A"* on the question *visit messages go by email whenever the account has
   an address, as bills do?*).** Until then this read
   `channel_preference_for_account` — the customer's paperless tick — on the
   reasoning *"a visit message is not a bill, so it keeps the preference"*.
   Both default OFF on a new account, so Rosa, with an email on file and no
   paperless tick, was never told her visit was booked (`WO-0085`). The
   portal's *Paperless* switch still reads the preference; only these five
   visit events moved. A customer with no email on file and no SMS consent
   gets NO visit message and the answer says so
   (`visit_message_no_channel_elected`); the `appointment` kind has no print
   floor (an appointment change is not a document, and a posted one arrives
   after the visit it warned about — `models.SOURCE_TYPES`' own reasoning).
3. **The utility's switch** for that event and channel (`event_key`, read by
   `services.channel_decision`). Off means nothing is written — P6.6.

The do-not-send list is the queue's, not ours: an address on it gets its row
written and HELD, so *did we tell them?* always has an answer.

ONE CALL PER CHANNEL, BECAUSE A PIN IS ONE PIN
────────────────────────────────────────────────────────────────────────────
`queue_document` writes every channel of one call from ONE template pin, and an
email body in an SMS is the wrong message. So each elected channel is its own
call with its own class; the queue's key `(source_type, source_id, channel,
copy_no)` keeps them apart and makes a replay write nothing.

THE KEY: (job, kind, occasion)
────────────────────────────────────────────────────────────────────────────
`source_id` is a uuid5 of the job, the kind and a discriminator the caller
names: booked and done once per job; moved per NEW window (a dispatcher who
moves it to the same window twice tells the customer once); on the way per
departure row. Rule 6 is the database's unique key, not a caller remembering.

IT NEVER RAISES. A message that could not be queued never fails the job act
that caused it; every path answers an outcome row.
"""

from __future__ import annotations

import uuid
from importlib import import_module
from typing import Any

from django.db import transaction

from apps.notifications import models, rule_catalog, services

SOURCE_APPOINTMENT = "appointment"

#: Ruling 3's four words (and `DEF-WRK-10652`'s fifth, *logged*, PO 2026-10-29
#: ruling 1A) → the catalogue event each is governed by.
EVENT_BY_KIND: dict[str, str] = {
    "logged": "work_order_logged",
    "booked": "appointment_window",
    "moved": "visit_moved",
    "on_the_way": "technician_on_the_way",
    "done": "completion_receipt",
}

QUEUED = "visit_message_queued"
ALREADY_QUEUED = "visit_message_already_queued"
NO_CUSTOMER = "visit_message_no_customer"
NO_CHANNEL_ELECTED = "visit_message_no_channel_elected"
SWITCHED_OFF = "visit_message_switched_off"
REFUSED = "visit_message_refused"
ERROR = "visit_message_error"

BR_REF = "BR-NOT-017"

_NAMESPACE = uuid.UUID("7a3e1c5d-9b2f-5e84-a6c1-2d4f8b0e3c91")


def source_id_for(order_id: Any, kind: str, discriminator: str = "") -> uuid.UUID:
    return uuid.uuid5(_NAMESPACE, f"{order_id}|{kind}|{discriminator}")


def _elected(account_id: Any) -> tuple[str, ...] | None:
    """The channels this customer can be reached on — the BILL's election
    (`DEF-WRK-10663`, PO B1 A): email when an address is on file, SMS with
    consent. Through customers' published read, by name."""
    try:
        read = getattr(
            import_module("apps.customers.selectors"), "delivery_channel_election_for_account", None
        )
    except ImportError:  # pragma: no cover - customers ships in this repo
        read = None
    return read(account_id) if callable(read) else None


def _ensure_seeded(template_code: str) -> None:
    """`DEF-WRK-10652` — plant a class a utility provisioned before it existed
    (`service_work_order_logged`, `sms_work_order_logged`) the first time it is
    needed, insert-missing, so a message is never queued pinned to nothing.
    The portal's precedent (`seed_templates.ensure_seeded`). In its own
    savepoint (law 14) and never able to fail the message."""
    from apps.notifications import seed_templates

    try:
        with transaction.atomic():
            seed_templates.ensure_seeded(template_code)
    except Exception:  # noqa: BLE001 — the queue reports a missing pin itself
        return


def visit_message_written(*, order_id: Any, kind: str, discriminator: str = "") -> bool:
    """Has this occasion's message been written on ANY channel? READ ONLY,
    tenant-scoped (hard rule 1) — Work asks before deciding booked or moved."""
    from core import tenancy as core_tenancy

    return models.OutboundMessage.objects.filter(
        tenant_id=core_tenancy.current_tenant_id(),
        source_type=SOURCE_APPOINTMENT,
        source_id=source_id_for(order_id, kind, discriminator),
    ).exists()


def queue_visit_message(
    *,
    kind: str,
    order_id: Any,
    account_id: Any,
    discriminator: str = "",
    render_context: dict[str, Any] | None = None,
    actor: Any = None,
) -> dict[str, Any]:
    """Queue ONE visit message, on each channel the customer elected and the
    utility left on. Returns one outcome row; never raises."""
    event_key = EVENT_BY_KIND.get(kind)
    if event_key is None:
        return {"code": REFUSED, "br_ref": BR_REF, "messages": [],
                "note": f"{kind!r} is not one of the five visit messages"}
    if account_id is None:
        # A network job at *Elm St & 3rd* has nobody to tell; inventing a
        # recipient from the premises would tell a neighbour about a stranger's
        # visit (`edit.notify_reschedule`'s reasoning, kept).
        return {"code": NO_CUSTOMER, "br_ref": BR_REF, "event_key": event_key, "messages": []}
    event = rule_catalog.event(event_key)
    elected = _elected(account_id) or ()
    channels = [channel for channel in event.channels if channel in elected]
    if not channels:
        return {"code": NO_CHANNEL_ELECTED, "br_ref": "BR-CWP-001", "event_key": event_key,
                "messages": [], "offered": list(event.channels)}
    messages: list[dict[str, Any]] = []
    problems: list[dict[str, Any]] = []
    for channel in channels:
        template_code = event.template_classes.get(channel)
        if template_code is None:  # pragma: no cover - every offered channel has a class
            continue
        _ensure_seeded(template_code)
        try:
            with transaction.atomic():  # the savepoint — law 14
                write = services.queue_document(
                    source_type=SOURCE_APPOINTMENT,
                    source_id=source_id_for(order_id, kind, discriminator),
                    channels=(channel,),
                    template=services.TemplatePin(code=template_code),
                    account_id=account_id,
                    render_context=dict(render_context or {}),
                    actor=actor,
                    job="work_visit_message",
                    event_key=event_key,
                )
        except Exception as failure:  # noqa: BLE001 — never fail the job act
            problems.append({"channel": channel, "code": ERROR, "detail": str(failure)})
            continue
        problems.extend(dict(problem) for problem in write.problems)
        for message in write.messages:
            messages.append({"id": message.id, "channel": message.channel,
                             "created": bool(message.created)})
    if not messages:
        off = (services.QUEUE_EVENT_SWITCHED_OFF, services.QUEUE_CHANNEL_SWITCHED_OFF)
        switched_off = any(problem.get("code") in off for problem in problems)
        return {"code": SWITCHED_OFF if switched_off else REFUSED,
                "br_ref": BR_REF, "event_key": event_key, "messages": [],
                "problems": problems}
    created = any(message["created"] for message in messages)
    return {
        "code": QUEUED if created else ALREADY_QUEUED,
        "br_ref": BR_REF,
        "event_key": event_key,
        "messages": messages,
        "problems": problems,
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-168-BRC10 §5.8 P6 · §7.1 P6.1–P6.7 · ruling 3 · BR-NOT-017
# generated: 2026-10-04 by CR-168 round 6 lane SRV-5
# checklist: A✔ B✔ C✔ D=n/a(no HTTP surface — Work calls it by name) E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_cr168_srv5_messages.py on SQLite and PostgreSQL 16
# status: AI-AUTHORED
# ──────────────────────────────────────────────────────────
