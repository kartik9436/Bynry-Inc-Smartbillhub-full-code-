# ── Trace ──────────────────────────────────────────────
# Story:    US-REP-015 (email delivery rides the outbound queue — rows written
#           now, dispatch W6) × US-REP-014 (scheduled execution)
#           Screens: 4·1 (Scheduled) · 5·1 (History) · S8 (SET-12's staff rows)
# Change:   CR-142-BRC07 — the Reports Build Brief, Phase 4 task `P4.10`
#           (*"Deliver the file · The outbound queue carries the link, not the
#           file · BR-NOT-005 · Recipients get a link that respects their
#           permissions"*). Drawing p15, read as an IMAGE per B14 rule 42.
# Rules:    BR-NOT-005 (queue only — nothing here sends) · BR-REP-007
#           (scheduled-report email rides the outbound queue) · BR-REP-017
#           CONFIRMED (email ships W6; v1 delivery is the download — the ROWS
#           are written now) · BR-REP-018 (the file is kept three days) ·
#           BR-REP-020 CONFIRMED (recipients are INTERNAL staff only) ·
#           BR-NOT-006 (the pin includes the language variant) · BR-TEN-017
#           (the recipient is snapshotted at queue time) · BR-TEN-043 (no wall
#           clock — every date arrives as an argument) · CLAUDE.md rule 1
#           (tenant scoping) · rule 6 (idempotency) · hard-won law 2
# Tests:    06-backend/tests/test_cr142_p4_10_delivery.py
# Impacts:  apps/reports/notifications_seam.py (the ONLY caller — reports
#           resolves this module BY NAME and never imports it) ·
#           apps/notifications/catalogs.py (`email_scheduled_report`) ·
#           apps/notifications/seed_templates.py (its body) ·
#           apps/notifications/rule_catalog.py (`scheduled_report_ready`)
# ───────────────────────────────────────────────────────
"""The one message a scheduled report sends: *it ran, here is the link*.

╔══════════════════════════════════════════════════════════════════════════╗
║  THE PHASE'S OWN DONE-WHEN SENTENCE, from the brief's p14:               ║
║  *"A schedule set on Friday produces a file on Monday, delivered to      ║
║   named internal staff."*                                                ║
║  Until this file, the product did everything up to the comma.            ║
╚══════════════════════════════════════════════════════════════════════════╝

`apps/reports/schedules.py` fires the run, the file appears on screen `5·1`,
and **nobody is told**. A schedule stores its recipients — `BR-REP-020` is
enforced at the picker and at the API — and after that nothing ever read the
list again. That is hard-won law 2's mirror on the server: not a control with
no screen behind it, but a stored list with no delivery behind it, and every
test green over it because each half is correct on its own.

────────────────────────────────────────────────────────────────────────────
THE LINK, NEVER THE FILE — AND IT IS ENFORCED RATHER THAN INTENDED
────────────────────────────────────────────────────────────────────────────
`P4.10`'s line is *"the outbound queue carries the link, not the file"* and its
outcome is *"recipients get a link that respects their permissions"*. A CSV on
an envelope respects nobody's permissions once it has left the building: it is
a page of a utility's debtors, addresses and balances, forwardable by anyone
who receives it, and `BR-REP-018` already keeps the artifact for three days
behind the same sign-in every screen is behind.

So the enforcement is in the TEMPLATE CLASS rather than here:
`catalogs.email_scheduled_report` declares `{report_link}` as **mandatory
content**, and `rendering.validate_body` refuses a saved body without it. A
utility — or a later lane — cannot edit this message down to *"Your report is
ready."* There is no token in the palette that could carry an attachment.

────────────────────────────────────────────────────────────────────────────
ONE ROW, MANY PEOPLE — THE PRECEDENT IS `staff_recipients.py`
────────────────────────────────────────────────────────────────────────────
The queue's key is `(tenant, source_type, source_id, channel, copy_no)`, so a
row PER RECIPIENT would need a different `source_id` or a `copy_no` per person
— and `models.OutboundMessage.copy_no`'s own docstring says *"automatic
writers never set it"*, because `> 0` means a human asked for an extra copy.

`apps/notifications/staff_recipients.py` already settled this shape for the
staff bell: **one queue row, whose `recipient_address` is the PRIMARY
recipient and whose `recipient_snapshot["recipients"]` carries the full list**,
snapshotted at queue time (BR-TEN-017). A schedule naming three people is one
row and three addresses on it, not three rows — and the dispatcher that ships
at W6 reads the snapshot, exactly as `in_app.deliver_batch` already does.

⚠ **`source_id` IS THE RUN, NEVER THE SCHEDULE.** `customer_events.py` records
in full what the obvious key costs: a monthly schedule keyed on its own id
would queue September's message, and **every month after that would be
`created=False`** — a duplicate the database refuses, a caller told nothing is
wrong, and a report that silently stops being delivered while it goes on being
produced. The run's job id is one row per firing by construction.

────────────────────────────────────────────────────────────────────────────
NOTHING HERE SENDS, AND NOTHING HERE LOOKS ANYTHING UP
────────────────────────────────────────────────────────────────────────────
`BR-NOT-005` is queue-only; `BR-REP-017` defers the dispatch to W6 with all
email. Every value on the row is a fact the CALLER already holds — the report's
name, when it ran, its link, when its file expires, and who the schedule names
— and this file reads no clock, no job store and no user table. A date this
module invented would be a second opinion about a fact `run_history` owns.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.notifications import catalogs, models, services

#: `models.SOURCE_TYPES`' existing kind. It has NO entry in
#: `services.CHANNEL_FLOOR_BY_SOURCE` and must not gain one: `BR-NOT-024` puts
#: the print floor on customer documents, and posting a clerk a letter about a
#: CSV they can open in a browser is not what that ruling says.
SOURCE_REPORT = "report"

#: The SET-12 event this message is. Passing it is what makes the utility's own
#: switch real: turn *Scheduled report ready — email* off on Settings →
#: Notifications and `queue_document` writes NO row and says why.
EVENT_SCHEDULED_REPORT = "scheduled_report_ready"

TEMPLATE_SCHEDULED_REPORT = "email_scheduled_report"


class ScheduledReportRefused(Exception):
    """This message cannot be queued, and here is why — in a clerk's words.

    A plain exception rather than a `core.errors` catalog type for
    `services.QueueWriteRefused`'s reason: this runs inside a sweep over every
    utility, where the right handling is to record the break and carry on, not
    to answer an HTTP request that nobody made.
    """


@dataclass(frozen=True)
class ScheduledReportMessage:
    """What one call left in the queue — and what it could not.

    `created` is the honest answer to *did this call queue anything*. `False`
    with a `message_id` means the row was already there: the sweep ran twice
    over one run, which is the ordinary case and not a fault.

    `problems` travels rather than being inferred, for `QueueWrite.problems`'
    own reason: an absence a caller has to deduce is an absence nobody counts.
    """

    run_id: str
    message_id: str | None = None
    created: bool = False
    recipients: tuple[str, ...] = ()
    problems: tuple[dict[str, Any], ...] = ()


def queue_scheduled_report(
    *,
    run_id: Any,
    report_name: str,
    ran_at: str,
    report_link: str,
    expires_on: str | None,
    recipients: tuple[tuple[str, str], ...],
    actor: Any = None,
    job: str | None = None,
    language: str | None = None,
) -> ScheduledReportMessage:
    """ONE email row for ONE finished scheduled run. SET-12 `scheduled_report_ready`.

    `recipients` is `(name, email)` pairs, IN THE ORDER THE SCHEDULE NAMES
    THEM, already resolved against this tenant's own staff by
    `reports.schedules.resolve_recipients` — this module does not re-check
    `BR-REP-020` and must not, because a second opinion about who is internal
    is a second place for that ruling to be wrong.

    ⚠ **AN EMPTY LIST IS REFUSED RATHER THAN QUEUED.** A row addressed to
    nobody is a message that will never be delivered and that counts as
    delivery on every dashboard that reads the queue. `resolve_recipients`
    refuses the same case at the other end of the wire, for the same reason.

    ⚠ **`ran_at` AND `expires_on` ARRIVE AS STRINGS THE CALLER HAS ALREADY
    FORMATTED.** BR-TEN-043 — no clock is read here — and B14's display rule
    belongs to whoever owns the tenant's regional format, which is not this
    module. `expires_on` may be `None`, and a named absence in the body is the
    honest render of *this run has no file any more*; inventing a date would
    be worse than the gap.
    """
    if catalogs.catalog_for(TEMPLATE_SCHEDULED_REPORT) is None:  # pragma: no cover - defensive
        raise ScheduledReportRefused(
            f"{TEMPLATE_SCHEDULED_REPORT!r} has no template class, so this message has no "
            "token whitelist to render against and nothing is queued. A letter rendered "
            "against no whitelist is a letter nobody checked."
        )
    people = tuple(
        (str(name or "").strip(), str(email or "").strip())
        for name, email in recipients
        if str(email or "").strip()
    )
    if not people:
        raise ScheduledReportRefused(
            "a scheduled report was queued with no reachable recipient. The schedule "
            "names its staff and every one of them must have an email address; a row "
            "addressed to nobody reads as delivery on every count that reads this queue."
        )
    primary_name, primary_email = people[0]
    context: dict[str, Any] = {
        "staff_name": primary_name or primary_email,
        "report_name": report_name,
        "ran_at": ran_at,
        "report_link": report_link,
    }
    if expires_on:
        context["expires_on"] = expires_on
    write = services.queue_document(
        source_type=SOURCE_REPORT,
        # ⚠ THE RUN, NEVER THE SCHEDULE — see the module docstring.
        source_id=run_id,
        channels=(models.CHANNEL_EMAIL,),
        template=services.TemplatePin(code=TEMPLATE_SCHEDULED_REPORT),
        # A staff message belongs to no customer account, and
        # `services._recipients_for`'s own docstring names this exact case.
        account_id=None,
        recipients=(
            services.Recipient(
                channel=models.CHANNEL_EMAIL,
                address=primary_email,
                # BR-TEN-017 — the WHOLE envelope as it stood at queue time.
                # `staff_recipients.py` is the precedent: one row, every
                # mailbox on it, and the dispatcher fans out at W6.
                snapshot={
                    "name": primary_name,
                    "recipients": [
                        {"name": name, "address": email} for name, email in people
                    ],
                },
            ),
        ),
        render_context=context,
        actor=actor,
        job=job or "reports.schedule",
        language=language,
        event_key=EVENT_SCHEDULED_REPORT,
    )
    message = write.messages[0] if write.messages else None
    return ScheduledReportMessage(
        run_id=str(run_id),
        message_id=str(message.id) if message is not None else None,
        created=bool(message.created) if message is not None else False,
        recipients=tuple(email for _, email in people),
        problems=tuple(write.problems),
    )


__all__ = [
    "EVENT_SCHEDULED_REPORT",
    "SOURCE_REPORT",
    "TEMPLATE_SCHEDULED_REPORT",
    "ScheduledReportMessage",
    "ScheduledReportRefused",
    "queue_scheduled_report",
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 P4.10 (05-prototype/09 Reports Build Brief.pdf p15, read as an image per B14 rule 42) · 04-docs/05-modules/12-reports/06-epics/EP-REP-04-scheduler.md US-REP-015 · 04-docs/05-modules/12-reports/02-business-rules.md BR-REP-017/018/020 · apps/notifications/services.py queue_document (the ONE write path) · apps/notifications/staff_recipients.py (the one-row-many-mailboxes precedent)
# screens: 4·1 · 5·1 · S8
# generated: 2026-09-27 by lane REP-P4-REST
# checklist: A✔ B=n/a(no screen half — delivery has no drawn surface in this brief) C✔ D=deferred(no new API surface) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — tests/test_cr142_p4_10_delivery.py was run before this file existed and reported `ModuleNotFoundError: No module named 'apps.notifications.report_events'`.
# exceptions: (1) THE WORDING IS LANE-AUTHORED. No signed document writes this body; `OQ-REP-12757` is where the PO settles it, and the seeded row says so in its own `source`. (2) EMAIL ONLY — no in-app row, because a schedule fires when nobody is at the screen and a bell in a session nobody is in is not delivery. Stated, not implied. (3) NOTHING IS DISPATCHED — BR-REP-017 CONFIRMED defers the send to W6; this writes the row and `QueueWrite.dispatched` is False, which a test asserts as a VALUE rather than reading this sentence.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
