# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-PAY-10651 — the automatic past-due reminder queued nothing a
#           customer could receive and the notice history said Sent anyway
# Ruling:   PO 2026-10-29, *"1A 2A 3A 4B, start"* (decision log entry of that
#           date, and our six judgments under it)
# Rules:    BR-PAY-017 (the ladder's rung 1, due + 3) · BR-NOT-005 (queue only)
#           · BR-NOT-009 (SMS quiet hours — the dispatcher's, not this file's) ·
#           BR-NOT-024 (narrowed for the friendly reminder — see judgment 2) ·
#           BR-TEN-017 (the recipient read is customers') · B1 (no cross-module
#           ORM) · CLAUDE.md rule 6 (the caller's source id is the key)
# Tests:    06-backend/tests/test_def_pay_10651_past_due_reminder.py
# ───────────────────────────────────────────────────────
"""WHICH channels a past-due reminder goes out on, and the queue write that does it.

ONE place answers it, for both doors: the nightly ladder
(`payments.collections_schedule` → `ladder.run_ladder`) and the clerk's S35
*Send reminder* (`notices_by_hand` → `ladder.step_one`). Both reach
`payments.notices.send_reminders`, which resolves `queue_past_due_reminder`
here BY NAME (B1) — payments never decides a channel for a reminder again.

THE ORDER, AND EVERY STEP IS THE PO'S (2026-10-29):

  1. **The utility's rule** `past_due_reminder` (Settings › Notifications).
     Switched OFF ⇒ nothing at all, reason `rule_off` (ruling 1A).
  2. **Email and SMS, where the rule has them on, and where the customer can
     be reached** — an email address on the primary contact; SMS only with SMS
     consent (`accounts.sms_reminders`) AND a number. Asked through customers'
     own published read (`delivery_recipients_for_account`), the one every
     other queue write uses, so this file reads no customer table.
  3. **A digital channel whose wording nobody published is not a channel.** The
     template is resolved BEFORE the row is written; a row that can never
     render is exactly the defect being fixed, so it is not queued and the
     reason is `template_missing`.
  4. **The printed letter (`dunning`) ONLY when nothing digital is left**
     (ruling 2A) — and only where the rule's Print toggle is on and the account
     has a postal address.

What the caller gets back is per CHANNEL: the message ids actually WRITTEN by
this call, and for every other channel the rule had on, a reason code. The
caller records `Sent` only for the first kind — the rule this file exists for.

⚠ **THE MESSAGE KIND IS `reminder`, NOT `notice`, AND THAT IS JUDGMENT 2.**
`notice` carries BR-NOT-024's print floor, which survives even the rule's
master switch — so under it ruling 1A (*off means off*) and ruling 2A (*paper
only for a customer we cannot otherwise reach*) could not both be true. The
disconnection notices stay on `notice` and keep the floor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from apps.notifications import models

EVENT_KEY = "past_due_reminder"
SOURCE_TYPE = "reminder"

#: The printed letter's class. The EXISTING `dunning` class — *"Past-due
#: reminder · Print"* on Settings › Templates, the class BR-NOT-008 already
#: names for the friendly step — not a second one beside it (judgment 1).
LETTER_CLASS = "dunning"

#: Why a channel the rule had on did not go. CODES — the account's notice
#: history and the S34 column group on them, and each has catalogue words
#: under `payments.skip.<code>` in all eleven languages.
REASON_RULE_OFF = "rule_off"
REASON_NO_CONTACT = "no_contact"
REASON_NO_SMS_CONSENT = "no_sms_consent"
REASON_TEMPLATE_MISSING = "template_missing"
REASON_QUEUE_PROBLEM = "queue_problem"
REASONS = (
    REASON_RULE_OFF,
    REASON_NO_CONTACT,
    REASON_NO_SMS_CONSENT,
    REASON_TEMPLATE_MISSING,
    REASON_QUEUE_PROBLEM,
)

_DIGITAL = (models.CHANNEL_EMAIL, models.CHANNEL_SMS)

#: customers' recipient answers → this file's reasons. A consent refusal is its
#: own fact; every other absence is "nothing on file to reach them by".
_UNAVAILABLE_TO_REASON = {
    "no_sms_opt_in": REASON_NO_SMS_CONSENT,
}


@dataclass(frozen=True)
class ReminderWrite:
    """The answer for ONE account."""

    #: channel → ids of the rows THIS call created. A row that already existed
    #: (the same reminder, the same day) is NOT here — it was sent before.
    queued: dict[str, tuple[str, ...]] = field(default_factory=dict)
    #: channel → reason, for every channel the rule had on that did not go.
    #: `None` as the key means the whole reminder (the rule switched off).
    not_sent: dict[str | None, str] = field(default_factory=dict)
    #: channels whose row already existed for this occasion.
    already: tuple[str, ...] = ()
    problems: tuple[dict[str, Any], ...] = ()


def _template_ready(code: str, *, language: str | None) -> bool:
    from apps.notifications import template_service

    try:
        template_service.resolve(code=code, language=language)
    except template_service.TemplateRefused:
        return False
    return True


def plan(
    account_id: Any, *, language: str | None = None
) -> tuple[dict[str, str], dict[str | None, str]]:
    """`(channel → template class, channel → reason)` for one account. No writes."""
    from apps.notifications import rule_catalog, rule_service, services

    switches = rule_service.channel_switches(EVENT_KEY)
    if not switches.event_enabled:
        return {}, {None: REASON_RULE_OFF}
    classes = rule_catalog.event(EVENT_KEY).template_classes
    digital = tuple(c for c in _DIGITAL if switches.permits(c))
    print_on = switches.permits(models.CHANNEL_PRINT) is not False

    read = services._resolve(services.RECIPIENT_MODULE, services.RECIPIENT_READ)
    asked = digital + ((models.CHANNEL_PRINT,) if print_on else ())
    answers = dict(read(account_id, channels=asked) or {}) if read is not None else {}

    chosen: dict[str, str] = {}
    reasons: dict[str | None, str] = {}
    for channel in digital:
        entry = answers.get(channel) or {}
        if not entry.get("address"):
            reasons[channel] = _UNAVAILABLE_TO_REASON.get(
                str(entry.get("unavailable_reason") or ""), REASON_NO_CONTACT
            )
            continue
        code = classes.get(channel)
        if not code or not _template_ready(code, language=language):
            reasons[channel] = REASON_TEMPLATE_MISSING
            continue
        chosen[channel] = code

    if not chosen:
        letter = answers.get(models.CHANNEL_PRINT) or {}
        if not print_on:
            reasons.setdefault(None, REASON_RULE_OFF)
        elif not letter.get("address"):
            reasons[models.CHANNEL_PRINT] = REASON_NO_CONTACT
        elif not _template_ready(LETTER_CLASS, language=language):
            reasons[models.CHANNEL_PRINT] = REASON_TEMPLATE_MISSING
        else:
            chosen[models.CHANNEL_PRINT] = LETTER_CLASS
    return chosen, reasons


def queue_past_due_reminder(
    *,
    account_id: Any,
    source_id: Any,
    render_context: dict[str, Any] | None = None,
    actor: Any = None,
    on_date: Any = None,
) -> ReminderWrite:
    """Queue ONE account's past-due reminder on the channels `plan` chose.

    `source_id` is the CALLER's occasion key (payments' `ladder_notice_source_id`
    with the business date) and the idempotency tuple is the queue's own
    `(tenant, source_type, source_id, channel, copy_no)` — so the same reminder
    on the same day finds its rows and writes nothing (CLAUDE.md rule 6).
    """
    from apps.notifications import services, tenancy_seam

    language = tenancy_seam.tenant_default_language()
    chosen, reasons = plan(account_id, language=language)
    if not chosen:
        return ReminderWrite(not_sent=reasons)

    channels = tuple(chosen)
    # The document pin is the first chosen channel's class; every other channel
    # takes its own (`channel_templates`, DEF-BIL-10530's mechanism).
    first = channels[0]
    written = services.queue_document(
        source_type=SOURCE_TYPE,
        source_id=source_id,
        channels=channels,
        template=services.TemplatePin(code=chosen[first]),
        channel_templates={
            channel: services.TemplatePin(code=code)
            for channel, code in chosen.items()
            if channel != first
        },
        account_id=account_id,
        actor=actor,
        language=language,
        on_date=on_date,
        event_key=EVENT_KEY,
        render_context=render_context,
    )
    held = {
        problem.get("channel")
        for problem in written.problems
        if problem.get("code") == services.QUEUE_ADDRESS_SUPPRESSED
    }
    queued: dict[str, tuple[str, ...]] = {}
    already: list[str] = []
    for message in written.messages:
        if message.channel in held:
            reasons[message.channel] = REASON_QUEUE_PROBLEM
        elif message.created:
            queued[message.channel] = queued.get(message.channel, ()) + (message.id,)
        else:
            already.append(message.channel)
    for channel in channels:
        if channel not in queued and channel not in already and channel not in reasons:
            # Asked for, and no row came back — the rule join or the queue said
            # why in `problems`; it is not a send.
            reasons[channel] = REASON_QUEUE_PROBLEM
    return ReminderWrite(
        queued=queued,
        not_sent=reasons,
        already=tuple(already),
        problems=tuple(written.problems),
    )


__all__ = [
    "EVENT_KEY",
    "LETTER_CLASS",
    "REASONS",
    "ReminderWrite",
    "SOURCE_TYPE",
    "plan",
    "queue_past_due_reminder",
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-PAY-10651 · PO 2026-10-29 "1A 2A 3A 4B, start" · BR-PAY-017 ·
#         BR-NOT-005/009/024 · apps/notifications/services.queue_document ·
#         apps/customers/selectors.delivery_recipients_for_account
# generated: 2026-10-29 by the past-due reminder lane
# gates: pytest tests/test_def_pay_10651_past_due_reminder.py (RED on the old
#        path first — the lane report quotes it)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
