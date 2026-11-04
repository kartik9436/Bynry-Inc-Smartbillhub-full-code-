# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-031 (the edit screen tells the customer the visit moved)
#           Screens: Work-021
# Rules:    BR-WRK-031 (a reschedule notifies, on the `appointment` kind) ·
#           BR-WRK-002 (one seam file per module; work writes nobody else's
#           table) · B2 r16 #7 (`outbound_messages` is the ONE table open to a
#           cross-module write, through this named service and no other path) ·
#           OQ-WRK-1495 CLOSED 2026-09-04, option (a)
# Tests:    06-backend/tests/test_us_wrk_031_edit.py (TC-5, the kind by name)
# Impacts:  apps/work/edit.py (its only caller)
# ───────────────────────────────────────────────────────
"""work → notifications: the one door that queues a message.

WHY THIS FILE EXISTS WHEN EVERY OTHER SEAM HERE IS READ-ONLY
------------------------------------------------------------
The package docstring says every file in `apps/work/seams/` is a READ-ONLY
seam, and that is true of the other five. This one causes a WRITE, and it is
the sanctioned exception rather than a hole in the rule:

* `outbound_messages` is **the one table B1 opens to cross-module writes**
  (B2 r16 #7). Billing writes it at issue, payments for receipts, metering for
  `BR-MET-115`'s service-live letter. `apps/metering/seams.py` and
  `apps/customers/seams.py` each publish exactly this callable for exactly
  this reason, and this file is the third copy of one pattern, not a new one.
* It calls **`notifications.queue_document` BY NAME**. It does not touch the
  ORM. The owning module resolves the recipient, honours the idempotency rule
  and audits — all of which a caller reaching for `OutboundMessage.objects`
  would skip, which is the whole content of `BR-WRK-002`.
* `G78` fails a foreign ORM write from `apps/work/**`. Nothing here is one.

The naming rule `US-WRK-005` TC-6 asserts — no public name starting `create_`,
`set_`, `update_`, `delete_` or `post_` — is met: `queue_document` starts with
neither.

⚠ **UNWIRED ⇒ None ⇒ THE CALLER REPORTS THAT NOTHING WAS QUEUED.** It never
reports a notification it did not queue. That is hard-won law 1 applied to a
send: a toast reading *customer notified* over a missing row is worse than a
visible failure, because the dispatcher stops watching for it.
"""

from __future__ import annotations

from typing import Any

from apps.work.seams.metering_seam import resolve

#: `notifications.models.SOURCE_TYPES` — the kind a rescheduled visit is filed
#: under. Named as a constant HERE rather than typed as a literal at the call
#: site, so the one string the `OQ-WRK-1495` ruling turns on appears once and a
#: test can assert it by name.
#:
#: ⛔ **IT IS NOT `notice`, AND THAT IS THE WHOLE RULING.** PO 2026-09-04:
#: *"filing an appointment change beside disconnection notices distorts every
#: monthly report"*. The customer reads the right words either way — the cost of
#: getting this wrong lands on a monthly count of notices, where nothing would
#: ever show it.
SOURCE_APPOINTMENT = "appointment"


def queue_document(**message: Any) -> Any:
    """`notifications.queue_document` — the only door into `outbound_messages`.

    Returns `None` when notifications is not wired, which the caller reports as
    *not queued* rather than swallowing.
    """
    fn = resolve("notifications", "queue_document")
    return fn(**message) if fn is not None else None


def queue_refusals() -> tuple[type[BaseException], ...]:
    """`notifications.QueueWriteRefused` — what the queue raises when a caller
    asks for something the platform has no writer for.

    Resolved by name for the same reason the callable is: half a published
    interface is not an interface. An empty tuple when unwired means
    `except tuple(...)` catches nothing, which is correct — there is no queue
    there to refuse anything.
    """
    refused = resolve("notifications", "QueueWriteRefused", kind="services")
    return (refused,) if isinstance(refused, type) else ()


# ══════════════════════════════════════════════════════════════════════════
# CR-070 wave L · `L3` · US-WRK-035 · BR-WRK-057 · BR-MET-115 · law 13
# ══════════════════════════════════════════════════════════════════════════

#: The kind the *your service is live* letter needs, and **which the platform
#: does not have**. Named here so the one string `OQ-376` turns on appears once
#: and a test can assert its ABSENCE from `notifications.models.SOURCE_TYPES`
#: by name — an absence is invisible to every check this repo has, unless
#: something states it.
SOURCE_CONNECTION = "connection"


def give_connection_kind() -> str:
    """Add the `connection` source kind to the platform vocabulary — **OQ-376**.

    ⛔ **THIS RAISES, AND IT WILL GO ON RAISING UNTIL A PERSON RULES.**

    `BR-MET-115` is ruled and built: accepting a work order queues the *your
    service is live* letter, and `metering.connections.dispatch_communication`
    does exactly that today. The queue REFUSES it, because
    `notifications.queue_document` checks `source_type` against a CONSTANT and
    `connection` is not in it — in the queue's own words, *"a tenant cannot
    invent a source the platform has no writer for, and a row nothing
    recognises is a message nothing will ever send."*

    **THE TEMPTING FIX IS `notice`, AND IT WOULD BE WRONG IN A WAY NOBODY WOULD
    NOTICE FOR A MONTH.** The kind is what monthly reports group by and what the
    renderer dispatches on. A *your service is live* letter filed beside
    disconnection notices reaches the customer with the right words and makes
    every count of notices wrong, silently — which is the identical argument the
    PO used on 2026-09-04 to give a rescheduled appointment its own kind
    (`OQ-WRK-1495`, `SOURCE_APPOINTMENT` above). That precedent makes the shape
    of the answer likely; it does **not** make the answer ours to take
    (`OQ-WRK-1495`'s own closure says so: *"`OQ-376` is a DIFFERENT question and
    is not closed by this one"*).

    ⚠ **THREE THINGS THE NEXT LANE SHOULD KNOW BEFORE READING THE REGISTER
    ROW.** (1) A kind is not enough on its own — a connection message needs a
    TEMPLATE before anything can render it. (2) `SOURCE_TYPES` stood at eight
    when `OQ-376` was written, at ten when `DEF-WRK-3602` corrected the
    documents, and stands at **TWELVE** today (`portal` 2026-09-04, `appointment`
     2026-09-05) — the count is not what the question turns on, which is exactly
    why it keeps going stale; read the tuple, never a sentence about it.
    (3) Adding a kind carries an obligation the constant itself now names:
    `tests/test_cr048_print_floor.py` fails until the new kind is classified
    (`DEF-NOT-4032`, a guard that sat RED for a day because the wave that added
    `portal` had no reason to run it).

    **The letter is not lost meanwhile.** `dispatch_communication` catches the
    refusal and answers `queued: False` with the platform's own sentence and
    `tracks: "OQ-376"` — never a stamp on a send that did not happen, and never
    filed under another kind. `US-WRK-035` TC-1…TC-5 assert that shape.
    """
    raise NotImplementedError("OQ-376")


# ══════════════════════════════════════════════════════════════════════════
# CR-168-BRC10 §F · lane FIELD-2 · TECHNICIAN SYNC DESIGN (5)
# ══════════════════════════════════════════════════════════════════════════


def queue_field_work_event(**event: Any) -> Any:
    """`notifications.queue_field_work_event` — the office told about a field
    close, photos complete, or Needs review. Notifications owns the queue row,
    the recipients (BR-NOT-021) and the template; work only names the event.

    Returns `None` when notifications is not wired, which the caller records
    as *not told* rather than swallowing.
    """
    fn = resolve("notifications", "queue_field_work_event")
    return fn(**event) if fn is not None else None


# ══════════════════════════════════════════════════════════════════════════
# CR-168-BRC10 round 5 · lane SRV-4 · P3.66 / P3.57 — the catalogue, READ
# ══════════════════════════════════════════════════════════════════════════


def event_keys() -> tuple[str, ...]:
    """The notification catalogue's event keys — what a rule's *Who hears*
    rows may name (P3.66: *a picker into the notification catalogue, never a
    text box*, `BR-NOT-017`). READ ONLY. An empty tuple when notifications is
    unwired, which the rule's save treats as *nothing may be named* rather than
    *anything may*."""
    from importlib import import_module

    try:
        catalog = import_module("apps.notifications.rule_catalog")
    except ImportError:  # pragma: no cover - notifications ships in this repo
        return ()
    return tuple(getattr(catalog, "EVENT_KEYS", ()) or ())


def escalation_events() -> dict[str, str]:
    """Which catalogue message each of the seven escalation kinds sends
    (`notifications.work_escalations.EVENT_BY_KIND`). READ ONLY. The rule form
    SHOWS it on each *When it stalls* row rather than offering a picker the
    sender would ignore (lane RULES, CR-168 round 5). Empty when notifications
    is unwired."""
    from importlib import import_module

    try:
        module = import_module("apps.notifications.work_escalations")
    except ImportError:  # pragma: no cover - notifications ships in this repo
        return {}
    return dict(getattr(module, "EVENT_BY_KIND", {}) or {})


def queue_work_escalation(**fields: Any) -> Any:
    """`notifications.work_escalations.queue_work_escalation` — a stalled job
    told to the people `BR-NOT-021` names, plus a rule's *Also tell*
    (PO 2026-10-04, `BR-NOT-021` NARROWED for Work escalations only).

    Resolved BY NAME, like `queue_document`: Work writes no notifications
    table. `None` when unwired, which the escalation sweep reports as *not
    told* rather than as told.
    """
    fn = resolve("notifications", "queue_work_escalation", kind="work_escalations")
    return fn(**fields) if fn is not None else None


def queue_work_reminder(**fields: Any) -> Any:
    """`notifications.work_escalations.queue_work_reminder` — P3.59's two
    reminders (a certificate running out, a technician's day), which
    Notifications owns since ruling 34. By name; `None` when unwired."""
    fn = resolve("notifications", "queue_work_reminder", kind="work_escalations")
    return fn(**fields) if fn is not None else None


# ══════════════════════════════════════════════════════════════════════════
# CR-168-BRC10 round 6 · lane SRV-5 · P6.1 / P6.2 — the customer and the office
# ══════════════════════════════════════════════════════════════════════════


def queue_visit_message(**fields: Any) -> Any:
    """`notifications.work_customer_messages.queue_visit_message` — ruling 3's
    four consumer kinds (booked, moved, on the way, done). Notifications owns
    the channels (the customer's election ∩ the utility's switch), the
    do-not-send list, the template and the row; Work names the occasion.
    By name; `None` when unwired, which the caller records as *not told*."""
    fn = resolve("notifications", "queue_visit_message", kind="work_customer_messages")
    return fn(**fields) if fn is not None else None


def queue_work_office_notice(**fields: Any) -> Any:
    """`notifications.work_escalations.queue_work_office_notice` — ruling 3's
    three back-office kinds (at risk, declined, blocked) and R28's unanswered
    emergency (`DEF-WRK-10350`). By name; `None` when unwired."""
    fn = resolve("notifications", "queue_work_office_notice", kind="work_escalations")
    return fn(**fields) if fn is not None else None


def visit_message_written(**fields: Any) -> bool:
    """`notifications.work_customer_messages.visit_message_written` — READ ONLY:
    was this occasion's customer message already written? False when unwired."""
    fn = resolve("notifications", "visit_message_written", kind="work_customer_messages")
    return bool(fn(**fields)) if fn is not None else False
