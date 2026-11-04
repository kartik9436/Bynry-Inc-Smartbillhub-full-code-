# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-004 (S19 Move-In) × US-CUS-005 (S20 Move-Out) ×
#           US-NOT-017 (SET-12 — the rule the queue reads)
#           Screens: S19 · S20 · S8 (Settings → Notifications)
# Rules:    BR-NOT-017 (ONE HOME for every notification rule — the queue reads
#           the utility's own switch on the way in) · BR-NOT-005 (queue only;
#           nothing here sends) · BR-NOT-024 (print is the floor on bills,
#           receipts, notices and plan letters — and on NOTHING ELSE, which is
#           why a move message can be switched off to nothing) ·
#           BR-NOT-006 (the template pin includes the language variant) ·
#           BR-CUS-150/151 (a move-in and a move-out are RECORDS of the JOB —
#           the id this message is keyed on) · BR-TEN-017 (the recipient is
#           snapshotted at queue time) · BR-TEN-043 (no wall clock) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 6 (idempotency)
# Change:   CR-048 wave B task B10 — *"the three real omissions"*: a customer
#           moving in is told nothing, a customer moving out is told nothing.
#           The wording for both has been seeded and unreachable since
#           2026-08-16.
# Tests:    06-backend/tests/test_cr048_b6_b10.py
# Impacts:  apps/customers/notifications_seam.py (the ONLY caller — customers
#           resolves this module BY NAME and never imports it) ·
#           apps/notifications/rule_catalog.py (owns the two event keys) ·
#           apps/notifications/seed_templates.py (owns the two bodies) ·
#           apps/notifications/models.py SOURCE_TYPES (`move`)
# ───────────────────────────────────────────────────────
"""The two messages an account's own life sends — moving in, and moving out.

╔══════════════════════════════════════════════════════════════════════════╗
║  WHAT THIS IS FOR, in the teardown's own words:                          ║
║  *"The module that owns moving in has no notification events at all.     ║
║   A customer moving in is told NOTHING."*                                ║
╚══════════════════════════════════════════════════════════════════════════╝

Both wordings already existed. `seed_templates` has planted `email_welcome`
(*"Welcome / account opened"*) and `email_move_out_final` (*"Move-out final
bill"*) on every tenant since 2026-08-16, and `catalogs.LISTINGS` said so out
loud on both — *"Not in use yet — a move-in does not send this."* This file is
the sentence that stops being true.

────────────────────────────────────────────────────────────────────────────
THE IDEMPOTENCY KEY IS THE MOVE RECORD, AND THE OBVIOUS CHOICE IS A TRAP
────────────────────────────────────────────────────────────────────────────
The queue's key is (tenant, source_type, source_id, channel, copy_no). The
obvious `source_id` for a message about an account is the ACCOUNT — and it is
wrong in a way that leaves no trace:

  * a customer moves in ⇒ welcome, keyed on account A;
  * eighteen months later the same customer moves out ⇒ final-bill letter,
    keyed on account A, same channel, same copy number;
  * the database refuses the second as a duplicate, `queue_document` reports
    `created=False`, the move-out completes normally, **and nobody is ever
    told their final bill is coming.**

Nothing about that looks like a failure. There is a row; it is just the wrong
message, written a year and a half earlier.

So `source_id` is the MOVE RECORD's id (`apps.customers.moves.MoveRecord`,
BR-CUS-150 — *one row per job*). A move-in and a move-out are different jobs and
therefore different ids by construction, and a replayed or resumed wizard finds
its own row and writes nothing, which is what rule 6 asks for.

────────────────────────────────────────────────────────────────────────────
NO PRINT FLOOR, AND THAT IS A RULING RATHER THAN AN OMISSION
────────────────────────────────────────────────────────────────────────────
BR-NOT-024 (PO 2026-08-29) makes print the floor on `invoice`, `payment`,
`notice` and `plan`. A move message is none of the four, so `models
.SOURCE_TYPES` gives `move` no entry in `CHANNEL_FLOOR_BY_SOURCE`. Adding one
would be this module writing a signed rule, which it may not do.

The consequence is deliberate and is CR-048's first acceptance case: **a utility
that switches *Move-in welcome* off gets no row at all, and the move-in still
completes.** The reason travels back on `MoveMessage.problems` so the wizard's
own result can say so, rather than the message quietly not existing.

────────────────────────────────────────────────────────────────────────────
NOTHING HERE READS A CLOCK, AND NOTHING HERE DECIDES A FACT
────────────────────────────────────────────────────────────────────────────
`effective_on` is the business date the CLERK entered (BR-TEN-043) and arrives
as an argument. Every merge value in the render context is a fact the CALLER
already holds — the move-in wizard knows the service start date, the move-out
wizard knows the closing read and its unit — and this file looks none of them
up. `template_service` refuses a token the class does not whitelist, so a
context is checked rather than trusted.
"""

from __future__ import annotations

import uuid

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from apps.notifications import catalogs, models, provider_seam, rendering, rule_catalog, services

#: The SOURCE KIND both messages ride. One row per move job per channel.
SOURCE_MOVE = "move"
#: CR-190-BRC10 — the click-to-accept agreement's outbound kind.
SOURCE_AGREEMENT = "agreement"

#: ⚠ THE KEYS ARE `rule_catalog`'s, and they are spelled here ONCE. Both were
#: checked against `rule_catalog.EVENT_KEYS` before being written down and a
#: test re-checks them, because `queue_document` REFUSES an event key this
#: platform cannot fire — and that refusal would land at the end of a committed
#: move-in, where the only honest thing left to do is report it.
EVENT_MOVE_IN = "move_in_welcome"
EVENT_MOVE_OUT = "move_out_final_bill"

#: The wording each one renders from. `seed_templates.SEEDABLE` owns the bodies;
#: `catalogs.CATALOGS` owns the token whitelist each is checked against.
TEMPLATE_MOVE_IN = "email_welcome"
TEMPLATE_MOVE_OUT = "email_move_out_final"


class MoveMessageRefused(Exception):
    """This message cannot be queued, and here is why — in a clerk's words.

    Not a `core.errors` catalog exception, for `bulk_summary.BulkSummaryRefused`'s
    reason: the CALLER is a wizard that has already committed a move, and the
    right handling of "the letter could not be addressed" is to record it against
    the job and let the job stand. A failed notification must never fail the work
    it describes.
    """


@dataclass(frozen=True)
class MoveMessage:
    """What one call left on the queue. One row, or none and the reason."""

    event_key: str
    move_record_id: str
    #: The queue row, or None when this utility's rule left no channel.
    message_id: str | None
    #: False when this call found the message already queued — a replayed
    #: wizard, a resumed job. The caller is never told it queued twice.
    created: bool
    channels: tuple[str, ...] = ()
    #: `services.QueueWrite.problems` verbatim — the rule join's own verdict, an
    #: absent email address, a template pin that could not resolve. Carried
    #: rather than swallowed, so a wizard can say why nothing went out.
    problems: tuple[dict[str, Any], ...] = ()
    #: `DEF-NOT-10649` — every row this call stands for, one per channel. A
    #: two-channel message (email + text) has two, and `message_id` is the first.
    message_ids: tuple[str, ...] = ()

    @property
    def suppressed_by_rule(self) -> bool:
        """True when the utility's own switch left no channel.

        A property over the two facts rather than `message_id is None`: a
        refused address also leaves no message and is a different thing.
        """
        return self.message_id is None and bool(self.problems)

    def as_wire(self) -> dict[str, Any]:
        return {
            "event_key": self.event_key,
            "move_record_id": self.move_record_id,
            "message_id": self.message_id,
            "created": self.created,
            "channels": list(self.channels),
            "suppressed_by_rule": self.suppressed_by_rule,
            "problems": [dict(problem) for problem in self.problems],
        }


def _queue_move_message(
    *,
    event_key: str | None,
    template_code: str,
    move_record_id: Any,
    account_id: Any,
    effective_on: date,
    context: dict[str, Any],
    actor: Any = None,
    job: str | None = None,
    language: str | None = None,
    channels: tuple[str, ...] = (models.CHANNEL_EMAIL,),
    source_id: Any = None,
) -> MoveMessage:
    """The one write every move entry point shares. EMAIL unless the caller
    names otherwise; the rule decides.

    `source_id` defaults to the move record's id. `DEF-CUS-9743` — the service
    agreement is a SECOND document of the same move-in, so it passes its own
    derived key (`service_agreement_source_id`) or it would dedupe into the
    welcome's row on the floor's print channel."""
    if catalogs.catalog_for(template_code) is None:  # pragma: no cover - defensive
        raise MoveMessageRefused(
            f"{template_code!r} has no template class, so this message has no token "
            "whitelist to render against and nothing is queued. A letter rendered "
            "against no whitelist is a letter nobody checked."
        )
    write = services.queue_document(
        source_type=SOURCE_MOVE,
        # BR-CUS-150 — the JOB's own id. See the module docstring for the
        # account-keyed version of this and why it loses the second message.
        source_id=source_id if source_id is not None else move_record_id,
        channels=tuple(channels),
        template=services.TemplatePin(code=template_code),
        account_id=account_id,
        render_context=context,
        actor=actor,
        job=job,
        language=language,
        # BR-TEN-043 — the clerk's date, for the template resolver's
        # effective-dated pick. Never a wall clock.
        on_date=effective_on,
        # CR-048 wave A's join. THIS is what makes the settings screen real for
        # these two messages: switch the event off and no row is written. The
        # service agreement passes None: it is no event, so no rule is read.
        event_key=event_key,
    )
    message = write.messages[0] if write.messages else None
    return MoveMessage(
        event_key=event_key or SERVICE_AGREEMENT_KEY,
        move_record_id=str(move_record_id),
        message_id=str(message.id) if message is not None else None,
        created=bool(message.created) if message is not None else False,
        channels=tuple(item.channel for item in write.messages),
        problems=tuple(write.problems),
    )


def queue_move_in_welcome(
    *,
    move_record_id: Any,
    account_id: Any,
    effective_on: date,
    first_bill_date: date | None = None,
    channels: tuple[str, ...] | None = None,
    actor: Any = None,
    job: str | None = None,
    language: str | None = None,
) -> MoveMessage:
    """ONE welcome email when a move-in completes. SET-12 `move_in_welcome`.

    `channels` — `CR-190-BRC10`: the ONE channel a clerk chose for this move-in
    on Step 4 (PO: *"allow untick and channel change per move-in"*), already
    checked against `default_allowed_channels` by the caller. None is the
    default ask (email). The utility's rule and the floor still decide after it.

    `effective_on` is the new tenancy's start — the date the account actually
    holds, read back off the written row by the caller, not off the payload.

    ⚠ **AMENDED 2026-10-22 — `CR-190-BRC10`, DEF-NOT-10440.** This passed only
    `{service_start_date}`, so a new customer's first email read *"Welcome, ——."*
    at *"——"* with account number *"——"*. The customer's name, account number
    and service address now come from `customer_context` — the ONE builder every
    customer letter shares — and the first bill date from the account's own
    cycle (`customer_context.first_bill_date`, OQ-344's default bill day for the
    period the customer moved in during). PO: *"give the activation date , first
    bill date and no due date required"*.

    `first_bill_date` passed by a caller still WINS (a caller that holds one is
    more current than a derivation). Where neither exists the key is passed with
    NO value: `catalogs` marks it optional, so the renderer leaves its paragraph
    out rather than dashing it, and the queue's context-gap guard is told the
    absence is deliberate rather than forgotten.
    """
    from apps.notifications import customer_context

    context: dict[str, Any] = {
        **customer_context.customer_context(account_id),
        "service_start_date": effective_on,
        "first_bill_date": (
            first_bill_date
            if first_bill_date is not None
            else customer_context.first_bill_date(account_id, effective_on)
        ),
    }
    return _queue_move_message(
        event_key=EVENT_MOVE_IN,
        template_code=TEMPLATE_MOVE_IN,
        move_record_id=move_record_id,
        account_id=account_id,
        effective_on=effective_on,
        context=context,
        actor=actor,
        job=job or "customers.move_in",
        language=language,
        channels=tuple(channels) if channels else (models.CHANNEL_EMAIL,),
    )


def _reading_text(value: Any) -> str | None:
    """A stored reading as a person reads it: `2645.000000` → `2645`.

    No thousands mark, deliberately (decision log 2026-10-22, MOVEOUT-EMAIL
    point 3): the line is composed at QUEUE time and the message's language is
    chosen at render, so a grouping mark here could be the wrong one; a bare
    figure is unambiguous in every language."""
    if value in (None, ""):
        return None
    try:
        figure = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    text = format(figure.normalize(), "f")
    return text[:-2] if text.endswith(".0") else text


def closing_read_lines(reads: Any, moved_out_on: date) -> list[tuple[str, str]]:
    """`DEF-NOT-10536` — one `(line, unit)` per meter register read ON OR AFTER
    the move-out date, from metering's `reads_for_unit` answer.

    The line is `<meter number>: <reading> <unit>` — `W-5043: 2645 kgal`. The
    unit is ALWAYS in the line (CLAUDE.md hard rule 3): a register whose read
    carries no unit is left out rather than printed as a bare number. An
    estimated register has no dial reading (`current_value` is None,
    `BR-MET-028`) and is left out too.
    """
    lines: list[tuple[str, str]] = []
    threshold = moved_out_on.isoformat()
    for meter in (reads or {}).get("meters") or ():
        number = (meter.get("asset_no") or "").strip()
        for register in meter.get("registers") or ():
            read_at = str(register.get("read_at") or "")[:10]
            unit = (register.get("unit") or "").strip()
            reading = _reading_text(register.get("current_value"))
            if not read_at or read_at < threshold or not unit or reading is None:
                continue
            head = f"{number}: " if number else ""
            lines.append((f"{head}{reading} {unit}", unit))
    return lines


def queue_move_out_final(
    *,
    move_record_id: Any,
    account_id: Any,
    effective_on: date,
    closing_reads: Any = None,
    final_bill: dict[str, Any] | None = None,
    final_bill_document: dict[str, Any] | None = None,
    final_read: str | None = None,
    unit: str | None = None,
    total_due: Any = None,
    due_date: date | None = None,
    actor: Any = None,
    job: str | None = None,
    language: str | None = None,
) -> MoveMessage:
    """ONE final-bill email when a move-out COMPLETES. `move_out_final_bill`.

    ⚠ **AMENDED 2026-10-22 — `DEF-NOT-10536`.** PO, verbatim: *"B: send at
    move-out completion with the draft figures"*, and *"These are normal email
    these are not instant email this will go on normal priority"*. This passed
    only the end date, so the email greeted `——` at `——` with closing read
    `——`, total `——` and no PDF. Since `DEF-CUS-10093` (2026-10-13) the
    move-out's Complete DRAFTS the final bill, so the figures exist; the old
    paragraph here saying *"a move-out issues no invoice"* stopped being true
    that day and nobody re-read this letter.

    Now, at completion and once (keyed on the move record, rule 6):

      * `first_name`, `customer_name`, `account_no`, `service_address` —
        `customer_context`, the ONE builder every customer letter shares;
      * `final_read` — `closing_read_lines(closing_reads)`, one line per
        meter register, each WITH its unit (hard rule 3); `{unit}` is filled
        only when every line shares one unit (decision log point 5);
      * `total_due` — the drafted bill's TOTAL DUE as its page prints it
        (previous balance + this bill; 0.00 for a customer in credit), as
        `rendering.Money` with its currency, so the renderer writes it in the
        utility's region;
      * `due_date` — the date issue will stamp (bill date + the cycle's due
        days), from billing's `final_bill_email_document`;
      * the PDF — that same answer's page, stored write-once under this email
        row and named on it (`attachments.attach_documents`).

    **Normal priority.** Nothing here calls `services.send_now`: the ruling
    keeps instant sending for the account-access emails alone.

    No draft (`nothing_to_bill`): the email still goes, without the figures
    and without an attachment — the body's paragraph that carries them is
    optional and is left out. A draft whose page cannot be produced REFUSES:
    an email saying the bill is attached with nothing attached is a wrong
    email (decision log point 4); the move-out stands either way.

    The legacy keyword arguments (`final_read`, `unit`, `total_due`,
    `due_date`) are kept for an old caller and win where given.
    """
    from apps.notifications import attachments, customer_context

    drafted = bool(final_bill) and final_bill.get("outcome") == "drafted"
    document = final_bill_document if drafted else None
    if drafted and (not document or document.get("outcome") != "rendered"):
        reason = (document or {}).get("detail") or "billing published no page for it"
        raise MoveMessageRefused(
            "the final bill was drafted but its PDF could not be produced, so the "
            f"final-bill email was not queued ({reason})."
        )

    lines = closing_read_lines(closing_reads, effective_on)
    units = {line_unit for _text, line_unit in lines}
    total = None
    if drafted:
        # The TOTAL DUE the attached page prints (arrears included), never the
        # draft's current charges — `final_bill_email`'s own comment has the
        # walk that caught the two disagreeing.
        figure = document.get("total_due")
        if figure not in (None, ""):
            total = rendering.Money(
                Decimal(str(figure)), document.get("currency") or final_bill.get("currency")
            )
    context: dict[str, Any] = {
        **customer_context.customer_context(account_id),
        "service_end_date": effective_on,
        # Passed WITH a None value where absent: the catalogue marks all three
        # optional, so the renderer leaves their paragraph out rather than
        # dashing it, and the context-gap guard knows the absence is meant.
        "final_read": (
            final_read if final_read is not None else ("\n".join(t for t, _u in lines) or None)
        ),
        "unit": unit if unit is not None else (next(iter(units)) if len(units) == 1 else None),
        "total_due": total_due if total_due is not None else total,
        "due_date": due_date if due_date is not None else (document or {}).get("due_date"),
    }
    message = _queue_move_message(
        event_key=EVENT_MOVE_OUT,
        template_code=TEMPLATE_MOVE_OUT,
        move_record_id=move_record_id,
        account_id=account_id,
        effective_on=effective_on,
        context=context,
        actor=actor,
        job=job or "customers.move_out",
        language=language,
    )
    if document and message.message_id is not None:
        _attach_final_bill(message, document, actor=actor, job=job, attachments=attachments)
    return message


def _attach_final_bill(
    message: MoveMessage, document: dict[str, Any], *, actor: Any, job: str | None, attachments: Any
) -> None:
    """Store the drafted final bill's page under the EMAIL row and name it there.

    Only the email carries it: the print row the floor adds is the letter
    itself. Idempotent — a replayed move-out finds its own stored page.
    """
    from apps.notifications import models as notification_models
    from apps.tenancy import document_models, document_store

    from core import tenancy as core_tenancy

    email = notification_models.OutboundMessage.objects.filter(
        tenant_id=core_tenancy.current_tenant_id(),
        source_type=SOURCE_MOVE,
        source_id=message.move_record_id,
        channel=models.CHANNEL_EMAIL,
        template_code=TEMPLATE_MOVE_OUT,
    ).first()
    if email is None:
        return
    found = document_store.for_source(
        source_type=document_models.SOURCE_OUTBOUND_MESSAGE,
        source_id=email.pk,
        content_type=document.get("content_type") or "application/pdf",
    )
    ref = getattr(found, "document", None)
    if ref is None:
        actor_id = getattr(actor, "id", None)
        ref = document_store.store(
            kind=document_models.KIND_MOVE_OUT_FINAL_BILL,
            source_type=document_models.SOURCE_OUTBOUND_MESSAGE,
            source_id=email.pk,
            content_type=document.get("content_type") or "application/pdf",
            display_name=f"move-out/{document['filename']}",
            payload=document["pdf"],
            actor_user_id=actor_id,
            process=None if actor_id else (job or "customers.move_out"),
        )
    attachments.attach_documents(
        email.pk,
        [
            {
                "document_id": str(ref.id),
                "filename": document["filename"],
                "content_type": document.get("content_type") or "application/pdf",
            }
        ],
    )


# ══════════════════════════════════════════════════════════════════════════
# CR-048 WAVE B TASK B11 — THE OTHER THREE THINGS AN ACCOUNT'S LIFE SENDS
# ══════════════════════════════════════════════════════════════════════════
# Closing the account, taking a deposit, and moving the account to a different
# rate plan. All three are `CAT_ACCOUNT_LIFECYCLE` in `catalogs.LISTINGS`, all
# three have had a body seeded on every tenant since 2026-08-16, and until this
# commit none of them could ever be sent.
#
# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  THE SOURCE KIND IS `account`, AND `source_id` IS NEVER THE ACCOUNT.     ║
# ╚══════════════════════════════════════════════════════════════════════════╝
# The move messages above spell out why the obvious key loses the second
# message, and these three are the same trap three more times over — worse, in
# fact, because they SHARE a source kind with each other:
#
#   * an account is closed once, but the same account can be given TWO deposits
#     and moved between plans FOUR times;
#   * all three ride `account`, so keying any of them on the account would make
#     the deposit letter, the plan-change letter and the closing confirmation
#     ONE row — the first one written, and the rest silently `created=False`.
#
# So each names the row for its OWN occasion: the disconnect CASE that was
# closed out, the PAYMENT that cleared as a deposit, and the
# `unit_plan_assignments` row the rate change wrote. Every one of those is a
# row per act by construction, so a replayed call finds its own message and a
# second act writes a second letter.
#
# ⚠ **NO PRINT FLOOR ON ANY OF THE THREE**, for the reason the move messages
# give: BR-NOT-024 (PO 2026-08-29) names `invoice`, `payment`, `notice` and
# `plan`, and `account` is none of them. Adding a fifth would be this module
# writing a signed rule. So a utility that switches *Account closed* off gets
# no row at all, and the reason travels back on `problems` so the caller can
# say so.
SOURCE_ACCOUNT = "account"

EVENT_ACCOUNT_CLOSED = "account_closed"
EVENT_DEPOSIT_RECEIVED = "deposit_received"
EVENT_RATE_PLAN_CHANGED = "rate_plan_changed"

TEMPLATE_ACCOUNT_CLOSED = "email_account_closed"
TEMPLATE_DEPOSIT = "email_deposit"
TEMPLATE_RATE_PLAN_CHANGE = "email_plan_change"


def _queue_account_message(
    *,
    event_key: str,
    template_code: str,
    occasion_id: Any,
    account_id: Any,
    on_date: date,
    context: dict[str, Any],
    actor: Any = None,
    job: str | None = None,
    language: str | None = None,
    channels: tuple[str, ...] = (models.CHANNEL_EMAIL,),
    channel_templates: dict[str, str] | None = None,
    source_type: str = SOURCE_ACCOUNT,
) -> MoveMessage:
    """The one write every account letter shares. EMAIL unless the caller
    names otherwise; the utility's rule decides what survives.

    ⚠ **`channels` AND `channel_templates` JOINED 2026-10-29 (`DEF-NOT-10649`,
    PO: *"1 A, 2 A, 3 A, 4 A"*).** The post-cut and restored messages go by
    email AND text, and the PO accepted extending THIS helper rather than a
    second path. A text is the same occasion on another channel with its own
    wording class, so `channel_templates` maps a channel to its own class code
    (`queue_document`'s `channel_templates`, `DEF-BIL-10530`); the queue key
    `(source, occasion, channel, copy)` keeps the two rows apart and a replay
    finds both. The defaults are the old behaviour exactly — every existing
    letter still goes by email only, under `account` (which carries the
    BR-NOT-024 print floor). `source_type` lets the two service-state messages
    ride their own floorless kind (`models.SOURCE_TYPES`' `service_state`).

    `occasion_id` is the row this letter is ABOUT — not the account. See the
    block above for the three occasions and why the account is the wrong key.

    Returns a `MoveMessage` rather than a third result shape: the caller needs
    exactly the same four facts (a row or none, whether this call created it,
    the channels, and why nothing was written), and a second dataclass saying
    the same thing in different words is a second thing to keep in step.
    """
    if catalogs.catalog_for(template_code) is None:  # pragma: no cover - defensive
        raise MoveMessageRefused(
            f"{template_code!r} has no template class, so this message has no token "
            "whitelist to render against and nothing is queued. A letter rendered "
            "against no whitelist is a letter nobody checked."
        )
    pins = {
        channel: services.TemplatePin(code=code)
        for channel, code in (channel_templates or {}).items()
        if channel in channels
    }
    write = services.queue_document(
        source_type=source_type,
        source_id=occasion_id,
        channels=tuple(channels),
        template=services.TemplatePin(code=template_code),
        channel_templates=pins or None,
        account_id=account_id,
        render_context=context,
        actor=actor,
        job=job,
        language=language,
        # BR-TEN-043 — the business date the caller holds, for the template
        # resolver's effective-dated pick. Never a wall clock.
        on_date=on_date,
        # CR-048 wave A's join: switch the event off on SET-12 and no row is
        # written, and `account` has no floor to keep one.
        event_key=event_key,
    )
    message = write.messages[0] if write.messages else None
    return MoveMessage(
        event_key=event_key,
        move_record_id=str(occasion_id),
        message_id=str(message.id) if message is not None else None,
        created=any(bool(item.created) for item in write.messages),
        channels=tuple(item.channel for item in write.messages),
        problems=tuple(write.problems),
        message_ids=tuple(str(item.id) for item in write.messages),
    )


def queue_account_closed(
    *,
    case_id: Any,
    account_id: Any,
    closed_on: date,
    closing_balance: str | None = None,
    actor: Any = None,
    job: str | None = None,
    language: str | None = None,
) -> MoveMessage:
    """ONE confirmation when an account is closed out. SET-12 `account_closed`.

    ⚠ **THIS IS A DIFFERENT MOMENT FROM A MOVE-OUT, which is why B10 refused to
    take it and left it in writing.** A move-out ends one occupant's tenancy and
    the account survives to be billed a final time; a CLOSE-OUT is the act after
    the service was cut, making the account TERMINAL for good
    (`customers.close_out`, BR-CUS-430/431). Two acts, two letters, and an
    account that is moved out of and later closed gets both — which is only
    true because they key on different rows.

    `case_id` is the DISCONNECT CASE this close-out closed (BR-CUS-430: one case
    per terminal event, `case_no` allocated inside its own transaction). It is
    the id of the JOB, exactly as the move record is for a move.

    `closing_balance` is OPTIONAL and arrives as a STRING already finalised by
    the caller (CLAUDE.md rule 2 — never a float, never a figure this module
    rounded). ⚠ **ABSENT IS A REAL CASE AND IT IS NOT ZERO:** `close_out` reads
    the balance through the AR seam and `None` means the READ FAILED, which
    BR-CUS-015 is emphatic must never become a $0.00. So an unreadable balance
    is passed as `None` and `rendering` prints a NAMED ABSENCE, rather than
    telling a departing customer they owe nothing when nobody could find out.
    """
    context: dict[str, Any] = {"service_end_date": closed_on}
    if closing_balance is not None:
        context["closing_balance"] = closing_balance
    return _queue_account_message(
        event_key=EVENT_ACCOUNT_CLOSED,
        template_code=TEMPLATE_ACCOUNT_CLOSED,
        occasion_id=case_id,
        account_id=account_id,
        on_date=closed_on,
        context=context,
        actor=actor,
        job=job or "customers.close_out",
        language=language,
    )


def queue_deposit_received(
    *,
    payment_id: Any,
    account_id: Any,
    received_on: date,
    amount: Any,
    held_after: Any = None,
    balance: Any = None,
    currency: str | None = None,
    actor: Any = None,
    job: str | None = None,
    language: str | None = None,
) -> MoveMessage:
    """ONE letter when a customer's deposit clears. SET-12 `deposit_received`.

    ⚠ **AMENDED 2026-10-22 — `CR-190-BRC10`, DEF-NOT-10441.** The letter read
    *"Hi ——"*, *"service at ——"* and *"Deposit 45.0000"*: payments passed the
    amount as a string already written to four places, so the renderer's money
    path never ran, and no customer details at all. Now (PO, *"Callers pass money
    as a value plus currency, never a pre-formatted string"*):

      * `amount` and `balance` arrive as `Decimal` and are wrapped with
        `currency` as `rendering.Money`, so the renderer writes `$45.00` in the
        utility's region (a string is still accepted from an old caller and
        parsed, never printed raw);
      * `{balance}` is what the ACCOUNT OWES after the deposit — the body says
        *"Your account balance is still {balance}"* — and the deposit
        register's `held_after` is NOT that figure. `balance` wins; `held_after`
        is kept on the signature for an old caller and is no longer rendered as
        the account balance;
      * the four customer tokens come from `customer_context`.

    `payment_id` is the PAYMENT that cleared, and it is the occasion. A deposit
    is not an event on the account — it is money arriving, and a customer can be
    asked for a second deposit after a disconnection and reconnection. Keyed on
    the account, that second letter would dedupe into the first and the customer
    would never be told their money was received.

    ⚠ **THE FIGURES ARE THE ONES THAT MOVED THE REGISTER, and both arrive as
    STRINGS already finalised by the caller** (CLAUDE.md rule 2). `amount` is
    what CLEARED — never what the plan schedule required, which is a different
    number and a collections question (`customers.services.
    record_deposit_movement` holds that distinction in full). `held_after` is
    the register's position after the movement, so the letter and the S36
    tie-out cannot state different totals.

    ⚠ **IT SAYS NOTHING ABOUT WHEN THE DEPOSIT COMES BACK.** `catalogs.py` is
    explicit on this class: r10 draws *"refunded automatically after 12 months
    of on-time payments"* and no signed rule states a period, so the body says
    only that we will write when the deposit is applied or returned (OQ-260).
    Nothing here adds a date.
    """
    from apps.notifications import customer_context

    def money(value: Any) -> Any:
        if value is None or value == "":
            return None
        if isinstance(value, rendering.Money):
            return value
        try:
            figure = value if isinstance(value, Decimal) else Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return None
        return rendering.Money(figure, currency)

    context: dict[str, Any] = {
        **customer_context.customer_context(account_id),
        "amount": money(amount),
        "date": received_on,
        # Stated with no value where the books could not answer: a named absence
        # beats a register figure dressed up as what the account owes.
        "balance": money(balance),
    }
    return _queue_account_message(
        event_key=EVENT_DEPOSIT_RECEIVED,
        template_code=TEMPLATE_DEPOSIT,
        occasion_id=payment_id,
        account_id=account_id,
        on_date=received_on,
        context=context,
        actor=actor,
        job=job or "payments.record",
        language=language,
    )


def _plan_change_context(
    *,
    account_id: Any,
    effective_on: date,
    plan_name: str,
    from_plan_id: Any,
    to_plan_id: Any,
    customer_class: str | None,
    language: str | None,
) -> dict[str, Any]:
    """`email_plan_change`'s facts. `CR-190-BRC10` — see `queue_rate_plan_change`."""
    from datetime import timedelta

    from apps.notifications import customer_context, rate_summary

    frequency = customer_context.account_cycle(account_id, effective_on).get("frequency")
    day_before = effective_on - timedelta(days=1)
    return {
        **customer_context.customer_context(account_id),
        "effective_date": effective_on,
        "plan_name": plan_name,
        "old_rate": rate_summary.rate_line(
            from_plan_id,
            on_date=day_before,
            language=language,
            customer_class=customer_class,
            frequency=frequency,
        ),
        "new_rate": rate_summary.rate_line(
            to_plan_id,
            on_date=effective_on,
            language=language,
            customer_class=customer_class,
            frequency=frequency,
        ),
    }


def queue_rate_plan_change(
    *,
    assignment_id: Any,
    account_id: Any,
    effective_on: date,
    plan_name: str,
    from_plan_id: Any = None,
    to_plan_id: Any = None,
    customer_class: str | None = None,
    actor: Any = None,
    job: str | None = None,
    language: str | None = None,
) -> MoveMessage:
    """ONE letter when an account's RATE PLAN changes. SET-12 `rate_plan_changed`.

    ⚠ **AMENDED 2026-10-22 — `CR-190-BRC10`, DEF-NOT-10443.** The letter read
    *"Hi ——"*, *"account ——"*, *"Now ——"* and *"From 10/31/2026 ——"*. The PO
    then ruled what the two rates ARE (verbatim: *"B. Main charges, one line
    each — Now: Residential Standard: base $12.00 a month, energy $0.0425 per
    kWh · From 10/31/2026: Ayush_Plan: base $14.00 a month, energy $0.0390 per
    kWh"*), which supersedes the paragraph below that called the absence the
    honest answer: `{old_rate}` is the plan the account was on the DAY BEFORE
    `effective_on`, `{new_rate}` the new plan ON it, each composed by
    `rate_summary` from the plan's published rate schedule. The customer tokens
    come from `customer_context`. A caller passing no plan ids still queues —
    the two lines then print their named absence, as before.

    ⚠ **A RATE PLAN, NOT A PAYMENT PLAN.** Three of SET-12's events are about
    payment plans and this one is not; the event key says `rate_plan_changed`
    for exactly that reason, and a reader of the settings screen must never
    have to guess which "plan" a row means.

    `assignment_id` is the `unit_plan_assignments` row the change wrote
    (BR-CUS-013 — append-only, dated, one row per assignment). It is the right
    occasion for two reasons and the second is the interesting one:
      * an account can be moved between plans repeatedly, so the ACCOUNT would
        collide on the second change and the customer would never hear about
        it — DEF-2512's mechanism, and the shape this trigger shipped with from
        W6 until 2026-08-30;
      * `change_plan`'s own TC-5 says *"the same plan from the same date twice
        is ONE change"*, and rating enforces that on the history row's natural
        key by returning the SAME row. So a re-submitted identical change comes
        back with the same assignment id, finds its own message, and writes
        nothing — **the letter inherits the idempotency the change already
        has**, rather than keeping a second opinion about it.

    ⚠ **`{old_rate}` AND `{new_rate}` ARE NOT PASSED, AND THE ABSENCE IS THE
    HONEST ANSWER.** A plan in this product is a BUNDLE of tariffs across up to
    ten services (BR-RAT-024), so there is no single rate to put in either
    token; picking one service's base charge would print a figure that is true
    of one line of a bill and false of the bill. `rendering` marks an absent
    token as a NAMED ABSENCE, which says less and says nothing untrue.
    `catalogs.py` already refuses to state the proration for the same reason.
    """
    return _queue_account_message(
        event_key=EVENT_RATE_PLAN_CHANGED,
        template_code=TEMPLATE_RATE_PLAN_CHANGE,
        occasion_id=assignment_id,
        account_id=account_id,
        on_date=effective_on,
        context=_plan_change_context(
            account_id=account_id,
            effective_on=effective_on,
            plan_name=plan_name,
            from_plan_id=from_plan_id,
            to_plan_id=to_plan_id,
            customer_class=customer_class,
            language=language,
        ),
        actor=actor,
        job=job or "customers.change_plan",
        language=language,
    )


# ══════════════════════════════════════════════════════════════════════════
# DEF-NOT-10649 — THE TWO MOMENTS AFTER THE DISCONNECT LADDER
# ══════════════════════════════════════════════════════════════════════════
# PO 2026-10-29, verbatim *"1 A, 2 A, 3 A, 4 A"* then *"start"* (decision log
# *"A cut and a restoration TELL THE CUSTOMER"*): (1) send BOTH — *Service
# disconnected* when the cut is recorded and *Service restored* when service is
# restored; (2) email and SMS, each only where the customer has it and (SMS)
# consented; (3) automatic, on by default, switchable per utility on Settings;
# (4) a short default safety text each utility edits.
#
# **ONE PIPELINE.** Both ride `_queue_account_message` above — extended to take
# channels rather than a second path, as the PO accepted — so the rules
# catalogue, the template pin, the recipient read (no email → the row says
# `no_email_address`; no SMS opt-in → `no_sms_opt_in`, nothing addressed), the
# do-not-send list, the dispatcher and the account's timeline are the ones every
# other letter uses. New code here is ONLY the facts each message carries.
#
# **ITS OWN SOURCE KIND, `service_state`, AND NOT `account`.** `account`
# carries BR-NOT-024's print floor, so a cut notice queued there would ALSO
# post a letter the PO did not ask for (2A is email and SMS) and that no
# utility could switch off (3A). The walk of 2026-10-29 caught exactly that: a
# `pdf_print` row beside the email and the text on the first real cut.
#
# **THE KEY IS THE CASE PLUS THE ACT, NEVER THE BARE CASE.** A case is cut once
# and restored once, and both acts belong to the same case, so a bare case id
# would key both messages on one row; and `account_closed` keys on the bare
# case too. `uuid5(case, act)` is a row per act by construction, and a replayed
# call finds its own rows and writes nothing (rule 6).
SOURCE_SERVICE_STATE = "service_state"

EVENT_SERVICE_DISCONNECTED = "service_disconnected"
EVENT_SERVICE_RESTORED = "service_restored"

TEMPLATE_SERVICE_DISCONNECTED = "service_disconnected_guide"
TEMPLATE_SERVICE_DISCONNECTED_SMS = "sms_service_disconnected"
TEMPLATE_SERVICE_RESTORED = "service_restored"
TEMPLATE_SERVICE_RESTORED_SMS = "sms_service_restored"

_SERVICE_STATE_NAMESPACE = uuid.UUID("3f6c2a91-7d4e-5b18-9c3a-e0b7d5f41a26")


def service_state_source_id(case_id: Any, act: str) -> uuid.UUID:
    """The occasion a cut or restored message is keyed on — see the block above."""
    return uuid.uuid5(_SERVICE_STATE_NAMESPACE, f"{case_id}|{act}")


def _figure(value: Any) -> Decimal | None:
    """A `{"stored", "display"}` pair, a Decimal or a string → its 4dp Decimal.

    The STORED leg is read, never the display one: the renderer rounds once, at
    2 places, in the utility's region (hard rule 2)."""
    if value in (None, ""):
        return None
    if isinstance(value, dict):
        value = value.get("stored")
        if value in (None, ""):
            return None
    try:
        figure = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return figure.quantize(Decimal("0.0001"))


def restoration_figures(terms: dict[str, Any] | None, currency: str | None) -> dict[str, Any]:
    """`{balance_owed, reconnect_fee, total_to_restore}` from the cut's own quote.

    `terms` is `customers.disconnects.reconnection_terms`, handed across the
    seam — ONE read, so the letter, the screen and the record cannot quote
    three different prices. Its `to_clear.basis.fee_in_arrears` says which
    question the total answered:

      * **after the cut** (the fee is an issued receivable): total to restore =
        the position read once; balance owed = that position less the fee;
      * **before it** (the fee is still a quote): balance owed = the position;
        total = position + fee.

    Worked, as put to the PO: owed $612.75, fee $75.00 issued at the cut → the
    position reads $687.75 → *balance owed $612.75 · fee $75.00 · total to
    restore $687.75*. An unreadable half is `None` and prints as a named
    absence — never $0.00, which is what a settled account reads (BR-CUS-015).
    """
    terms = terms or {}
    to_clear = terms.get("to_clear") or {}
    fee = _figure(terms.get("fee"))
    position = _figure(to_clear.get("arrears"))
    after_the_cut = bool((to_clear.get("basis") or {}).get("fee_in_arrears"))
    if after_the_cut:
        total = position
        balance = None if position is None or fee is None else position - fee
    else:
        balance = position
        total = None if position is None or fee is None else position + fee

    def money(figure: Decimal | None) -> Any:
        return None if figure is None else rendering.Money(figure, currency)

    return {
        "balance_owed": money(balance),
        "reconnect_fee": money(fee),
        "total_to_restore": money(total),
    }


def _ensure_service_state_wording(actor: Any) -> None:
    """The four classes on a utility provisioned before 2026-10-29 —
    insert-missing, so a queue write is never pinned to nothing."""
    from apps.notifications import seed_templates

    for code in (
        TEMPLATE_SERVICE_DISCONNECTED,
        TEMPLATE_SERVICE_DISCONNECTED_SMS,
        TEMPLATE_SERVICE_RESTORED,
        TEMPLATE_SERVICE_RESTORED_SMS,
    ):
        seed_templates.ensure_seeded(code, actor=actor)


def queue_service_disconnected(
    *,
    case_id: Any,
    account_id: Any,
    cut_on: date,
    terms: dict[str, Any] | None = None,
    closing_reads: Any = None,
    currency: str | None = None,
    actor: Any = None,
    job: str | None = None,
    language: str | None = None,
) -> MoveMessage:
    """*Service disconnected* — email and text, the moment the cut is recorded.

    Called INSIDE `commit_cut`'s transaction (through the customers seam, in
    its own savepoint), so a cut that rolls back takes the message with it and
    there is never a letter about a cut that did not happen.

    `closing_reads` is metering's `reads_for_unit` answer after the cut posted
    its reading: `{final_read}` is one line per meter register read ON the cut
    date or later, each WITH its unit (hard rule 3), and the paragraph is left
    out for a unit with no meter. `{service_address}` is the premises' address,
    walked by `customer_context` (hard rule 8).
    """
    from apps.notifications import customer_context, tenancy_seam

    _ensure_service_state_wording(actor)
    lines = closing_read_lines(closing_reads, cut_on)
    context: dict[str, Any] = {
        **customer_context.customer_context(account_id),
        "cut_date": cut_on,
        **restoration_figures(terms, currency),
        # Passed WITH a None value where absent: both are optional on the
        # class, so the renderer drops their paragraph rather than dashing it.
        "final_read": "\n".join(text for text, _unit in lines) or None,
        "restoration_link": tenancy_seam.portal_pay_link(),
    }
    return _queue_account_message(
        event_key=EVENT_SERVICE_DISCONNECTED,
        template_code=TEMPLATE_SERVICE_DISCONNECTED,
        channel_templates={models.CHANNEL_SMS: TEMPLATE_SERVICE_DISCONNECTED_SMS},
        channels=(models.CHANNEL_EMAIL, models.CHANNEL_SMS),
        occasion_id=service_state_source_id(case_id, "disconnected"),
        source_type=SOURCE_SERVICE_STATE,
        account_id=account_id,
        on_date=cut_on,
        context=context,
        actor=actor,
        job=job or "customers.disconnects.commit_cut",
        language=language,
    )


def queue_service_restored(
    *,
    case_id: Any,
    account_id: Any,
    restored_on: date,
    actor: Any = None,
    job: str | None = None,
    language: str | None = None,
) -> MoveMessage:
    """*Service restored* — email and text, when `restore_service` commits.

    Inside that transaction too, for the same reason. It states the date and
    the PO's safety text and nothing about money: under `BR-CUS-1097` a
    restored account may still owe, and the restoration is not the moment to
    restate a figure the customer was already sent at the cut.
    """
    from apps.notifications import customer_context

    _ensure_service_state_wording(actor)
    context: dict[str, Any] = {
        **customer_context.customer_context(account_id),
        "restored_at": restored_on,
    }
    return _queue_account_message(
        event_key=EVENT_SERVICE_RESTORED,
        template_code=TEMPLATE_SERVICE_RESTORED,
        channel_templates={models.CHANNEL_SMS: TEMPLATE_SERVICE_RESTORED_SMS},
        channels=(models.CHANNEL_EMAIL, models.CHANNEL_SMS),
        occasion_id=service_state_source_id(case_id, "restored"),
        source_type=SOURCE_SERVICE_STATE,
        account_id=account_id,
        on_date=restored_on,
        context=context,
        actor=actor,
        job=job or "customers.disconnects.restore_service",
        language=language,
    )


#: Published so a test can assert the keys are real without importing the
#: catalogue twice — the `run_alert_seam.entry_point` discipline (hard-won law 1:
#: a docstring claiming these keys are valid is not the check).
# ══════════════════════════════════════════════════════════════════════════
#  THE CLERK'S OWN MESSAGE — `CR-094-BRC01` wave K, `ACC-S16`
# ══════════════════════════════════════════════════════════════════════════
#
# `ACC-S16`, the blueprint's commitment card, verbatim: *"A clerk can write to
# the customer from the account, and see what has already been sent."*
#
# THE FOUR WAYS THIS IS UNLIKE EVERY OTHER WRITE IN THIS FILE, each of them a
# decision rather than an omission:
#
# **1 · Its source kind is `message` and not `account`.** `account` carries the
# PRINT floor (`BR-NOT-024`), so a clerk sending a one-line email would also
# have posted a letter. `models.SOURCE_TYPES` holds the whole argument beside
# the value.
#
# **2 · `source_id` is minted by the SCREEN.** There is no job row to key on —
# the occasion IS the composing — so the dialog mints a UUID and sends it with
# the submit, and a double-clicked *Queue the message* meets the unique key and
# writes one message. This is the only write in the module whose idempotency key
# comes from outside the server, which is why `queue_account_message` refuses an
# id already used on a DIFFERENT account rather than letting it dedupe silently.
#
# **3 · It passes NO `event_key`, and that is the point.** SET-12 lets a utility
# switch off a class of automatic message. A clerk pressing a button is not an
# automatic message: a rule that silently swallowed it would leave the clerk
# believing they had written to a customer when nothing was written at all.
#
# **4 · The channels are the CLERK's, one row each.** `queue_document` writes one
# row per channel, so *email and post* is two rows and the history view groups
# them back into one document, exactly as a posted-and-emailed bill is grouped.
SOURCE_MESSAGE = "message"
TEMPLATE_ACCOUNT_MESSAGE = "account_message"

#: The kinds the dialog offers. **Only the first is queued from here** — the
#: rest are REFUSED BY NAME with the rule that owns them, and the refusal is
#: served to the screen rather than hardcoded in it, so one list governs both
#: sides (`BR-SHL-025`'s shape applied across the boundary).
MESSAGE_KIND_COURTESY = "courtesy"

#: ⚠ **WHY FOUR OF THE DRAWING'S FIVE KINDS ARE REFUSED HERE.** Two of them are
#: the collections LADDER's acts: `BR-PAY-035` maps a reminder's tone onto a
#: dunning TIER template and says *"free-text tones do not exist"*, and
#: `BR-NOT-008` renders the disconnect class whatever tone was picked. A ladder
#: step composed on this dialog would carry no tier and write no
#: `NoticeHistory` row, so the regulatory trail would have a letter in it that
#: no ladder knows about — the exact opposite of *"what a customer was told has
#: to be provable later"*. The other two are DOCUMENTS that already have a
#: writer: a bill copy is billing's reprint and a balance statement is the
#: statement path. Each refusal names its owner so a clerk is sent somewhere
#: rather than stopped.
REFUSED_MESSAGE_KINDS: dict[str, str] = {
    "payment_reminder": "reminder_is_the_ladder",
    "disconnection_notice": "notice_is_the_ladder",
    "bill_copy": "bill_copy_is_a_reprint",
    "balance_proof": "balance_proof_is_a_statement",
}


def message_kinds() -> tuple[dict[str, Any], ...]:
    """Every kind the dialog may offer, and for each whether it may be queued.

    Served rather than hardcoded on the screen: a kind that stops being refused
    must stop being refused in ONE place, and a screen that kept its own copy is
    how a control goes on refusing after its reason expired (hard-won law 2's
    mirror).
    """
    return (
        {"kind": MESSAGE_KIND_COURTESY, "allowed": True, "refusal": None},
        *(
            {"kind": kind, "allowed": False, "refusal": reason}
            for kind, reason in REFUSED_MESSAGE_KINDS.items()
        ),
    )


#: The categories whose published templates the Communication dialog may OFFER
#: as a starting point. It is `REFUSED_MESSAGE_KINDS` one layer down, decided by
#: the SAME two reasons and derived from the catalogue rather than re-listed:
#: `CAT_COLLECTIONS` is the dunning LADDER (`BR-PAY-035`, `BR-NOT-008` — a step
#: composed here would carry no tier and write no `NoticeHistory` row) and
#: `CAT_BILLING` is the DOCUMENTS that already have a writer (a bill copy is
#: billing's reprint, a statement is the statement path). What is left is the
#: everyday correspondence a clerk legitimately sends by hand.
#:
#: ⚠ **A CATEGORY LIST, NOT A CODE LIST, ON PURPOSE.** A new class filed under
#: `payments` or `account_lifecycle` appears in the picker the day it is seeded;
#: a hand-kept list of codes is the shape `used_by` failed in — 23 sentences of
#: 38 true the day they were typed and wrong within weeks.
OFFERABLE_TEMPLATE_CATEGORIES: tuple[str, ...] = (
    catalogs.CAT_PAYMENTS,
    catalogs.CAT_SERVICE_FIELD,
    catalogs.CAT_ACCOUNT_LIFECYCLE,
)


#: What a token becomes when THIS screen cannot answer it. A blank a clerk types
#: over, never the token spelling: `{outage_start}` left literal is refused at
#: queue time (it is outside `account_message`'s whitelist), and a clerk would
#: read the refusal as the product being broken rather than as a line to fill.
TEMPLATE_BLANK = "____"


def account_message_templates(
    *,
    language: str | None = None,
    channels: tuple[str, ...] = (),
    preferred_language: str | None = None,
) -> tuple[dict[str, Any], ...]:
    """The ready-made wording a clerk may start from, resolved for this account.

    ⚠ **IN THE CUSTOMER'S LANGUAGE WHERE THE UTILITY PUBLISHED IT (PO option B,
    2026-10-29).** `language` is the utility's default and the fallback;
    `preferred_language` is the account's. Each class is asked for
    `message_language.language_for(...)`, the same answer `queue_document` pins
    with, so the wording offered and the wording sent cannot disagree.

    ⚠ **THE POINT IS THAT NOBODY RETYPES A LETTER THE UTILITY HAS ALREADY
    AGREED.** PO, 2026-09-13, on the Communication dialog: *"it should also have
    ready to use messages from our Notification rules - user will not write it
    every time"*. Thirty-four published versions already sit in this tenant's
    registry; the dialog could not see them, so every message was typed from
    nothing and every history row read *A message*.

    **Resolution is `template_service.resolve` + `load_pinned`, not a query of
    our own.** That is `BR-BIL-025`'s order — override, exact variant, language
    fallback, category fallback, the mandatory default — and it is the same call
    the dispatcher makes, so the wording a clerk starts from is the wording that
    class really carries. A class whose `resolve` refuses is SKIPPED rather than
    offered empty: the ratified hold is *"dispatch holds safely on missing
    published template; content never invented"*, and an entry that pasted a
    blank body into a clerk's message would be exactly that invention.

    ⚠ **THE TOKENS ARE TRANSLATED THROUGH `account_message`'s WHITELIST, AND
    THIS IS THE HALF THAT MAKES THE FEATURE HONEST RATHER THAN A TRAP.** What a
    clerk writes here is queued as ONE class — `account_message` — so their
    words are rendered against ITS palette and nothing else. A receipt's body
    carries `{amount}`, `{confirmation}`, `{balance_after}`: facts only the
    payment that caused it holds, which this screen cannot supply and
    `rendering.validate_body` refuses by name. So each token is sorted into one
    of two piles:

      * **inside the palette** (`{utility_name}`, `{first_name}`,
        `{account_no}`, `{service_address}` …) — LEFT AS A TOKEN, because
        dispatch fills it from the real account and a clerk should not be
        retyping a customer's own name either;
      * **outside it** — replaced with `TEMPLATE_BLANK`, a line the clerk types
        over before queueing.

    The result is a body that is personalised where the product knows the answer
    and visibly incomplete where only a person does — and, either way, one that
    will actually render. Nothing offered here can be queued into a refusal.
    """
    from apps.notifications import message_language, template_service

    palette = catalogs.catalog_for(TEMPLATE_ACCOUNT_MESSAGE)
    allowed = set(palette.tokens) if palette is not None else set()
    wanted = tuple(channels) if channels else models.CHANNELS
    out: list[dict[str, Any]] = []
    for code in catalogs.listable_codes():
        listing = catalogs.listing_for(code)
        if listing is None or listing.category not in OFFERABLE_TEMPLATE_CATEGORIES:
            continue
        if not catalogs.has_wording(code):
            continue
        # `class_serves_channel` answers None for a class with no opinion, which
        # is not the same as False and must not be read as one.
        if not any(catalogs.class_serves_channel(code, one) is not False for one in wanted):
            continue
        try:
            pin = template_service.resolve(
                code=code,
                language=message_language.language_for(
                    code, stated=preferred_language, utility=language
                ),
            )
            pinned = template_service.load_pinned(template_id=pin.template_id, version=pin.version)
        except Exception:  # noqa: BLE001 — a class that will not resolve is simply not offered
            continue
        out.append(
            {
                "code": code,
                #: The TENANT-facing name from the catalogue — *Planned outage
                #: notice* — never the code, which B14 rule 31 keeps off screen.
                "name": listing.name,
                "subject": _fillable(pinned.subject, allowed),
                "body": _fillable(pinned.body, allowed),
            }
        )
    return tuple(out)


def _fillable(text: str | None, allowed: set[str]) -> str:
    """A template's words with every token this screen cannot answer blanked."""
    if not text:
        return ""
    out = text
    for token in rendering.tokens_in(text):
        if token not in allowed:
            out = out.replace("{" + token + "}", TEMPLATE_BLANK)
    return out


def channel_reachability(channels: tuple[str, ...] = ()) -> tuple[dict[str, Any], ...]:
    """Per channel: will a row queued on it actually LEAVE this deployment?

    ⚠ **THE SCREEN EXISTS TO ANSWER THIS AND MUST NOT GUESS IT.** `BR-NOT-013`,
    CONFIRMED by the PO on 2026-08-15: *"DELIVERY IS OUT OF THIS RELEASE … no
    provider adapter exists or is coming on ANY channel, print included"*. So a
    dialog that said *the outbound queue delivers it* under an email tick would
    be telling a clerk something this product cannot do. `provider_seam` already
    computes the answer for the dispatcher; this publishes the same answer to
    the surface that needs it, so the two cannot disagree.
    """
    wanted = channels or models.CHANNELS
    out: list[dict[str, Any]] = []
    for channel in wanted:
        route = provider_seam.channel_route(channel, active=True)
        problem = route.problem or {}
        out.append(
            {
                "channel": channel,
                "delivers": bool(route.dispatchable),
                "reason": problem.get("code"),
            }
        )
    return tuple(out)


#: `DEF-CUS-6365` — the payment receipt's three writes, in `payments.receipts`
#: order, each with the template class it pins. Named here rather than imported
#: because notifications may not import payments (B1); `test_def_cus_6365`
#: asserts they equal `receipts.RECEIPT_TEMPLATE_CODE` and its two siblings, so
#: the two lists cannot drift apart silently.
RECEIPT_EVENT = "payment_received"
RECEIPT_CHANNEL_TEMPLATES: tuple[tuple[str, str], ...] = (
    (models.CHANNEL_PRINT, "receipt"),
    (models.CHANNEL_EMAIL, "email_payment_receipt"),
    (models.CHANNEL_SMS, "sms_payment_received"),
)

#: `DEF-CUS-6365` — the CONTRACT the PO named in their own words (*"email,
#: contract, text , inapp message"*), drawn third on blueprint p077 as *The
#: service agreement*. It is the one plan row that is NOT an event: a move-in
#: WRITES `service_agreements` rows and queues no message for them, so it takes
#: no `event_key` and no channel decision is made for it. Its channel list is
#: therefore empty BY CONSTRUCTION rather than by a switch somebody could turn
#: on — `move_in_message_plan`'s docstring carries the whole reason.
SERVICE_AGREEMENT_KEY = "service_agreement"
TEMPLATE_SERVICE_AGREEMENT = "contract_service_agreement"
#: ⚠ **`DEF-CUS-9743` (2026-10-05) — THE AGREEMENT IS NOW QUEUED.** The block
#: above described the world before that fix: CR-171 P1.20 and images 45/46
#: make it one of the two defaults a move-in ALWAYS sends, and it was listed
#: on Review and never written. It still takes no `event_key` (it is no
#: event, so no utility switch reaches it) and it goes on the contract class's
#: own channel — PRINT, as every `GROUP_CONTRACT` class is and as New
#: Connection's contract occasion already is (`metering.connection_messages`).
#: Decision log 2026-10-05, *"THE SERVICE AGREEMENT GOES OUT ON PAPER"*.
#: ⚠ **`CR-190-BRC10` (2026-10-22) — SUPERSEDED BY THE PO: EMAIL.** *"A: email
#: it as a PDF attachment (plus a letter if the customer wants paper)"*. The
#: move-in now sends a click-to-accept request (`apps/customers/agreements.py`);
#: the letter is added there per the customer's paperless choice. Step 4 lists
#: the agreement on EMAIL. DEF-CUS-9743's print-only lane judgment is the thing
#: superseded.
SERVICE_AGREEMENT_CHANNELS: tuple[str, ...] = (models.CHANNEL_EMAIL,)
#: The HELD letter written when the utility has published no version of the
#: agreement (nothing to email, nothing to accept): the contract class's own
#: PRINT channel, as before CR-190 — it holds at dispatch naming what it waits for.
SERVICE_AGREEMENT_UNPUBLISHED_CHANNELS: tuple[str, ...] = (models.CHANNEL_PRINT,)


def service_agreement_source_id(move_record_id: Any) -> uuid.UUID:
    """The `outbound_messages.source_id` a move-in's agreement files under.

    `outbound_messages` is unique on (source, channel, copy). Keyed on the
    move record, the agreement's print row and the welcome's print floor row
    are ONE row and the second write silently becomes the first. Derived with
    `uuid5` — New Connection's `occasion_source_id` idiom — so a replayed
    Complete finds its own row again (CLAUDE.md hard rule 6).
    """
    return uuid.uuid5(uuid.UUID(str(move_record_id)), "move-in-message:service_agreement")


def queue_move_in_service_agreement(
    *,
    move_record_id: Any,
    account_id: Any,
    effective_on: date,
    channels: tuple[str, ...] | None = None,
    actor: Any = None,
    job: str | None = None,
    language: str | None = None,
) -> MoveMessage:
    """The service agreement, once, when a move-in completes. `DEF-CUS-9743`.

    **A utility that has published no contract version is the common case** —
    `BR-NOT-002` refuses to seed one — and it is handled exactly as a missing
    welcome template is: `queue_document` writes the row anyway, it HOLDS at
    dispatch with the missing-template reason, and that reason travels back
    as `template_pin_unresolved` (`services._pinned`). A letter that was never
    queued leaves no trace; a held one says what it waits for.
    """
    return _queue_move_message(
        event_key=None,
        template_code=TEMPLATE_SERVICE_AGREEMENT,
        move_record_id=move_record_id,
        account_id=account_id,
        effective_on=effective_on,
        context={"service_start_date": effective_on},
        actor=actor,
        job=job or "customers.move_in",
        language=language,
        # MERGE (MOVEIN-MSG x AGREEMENT): this write is reached only when the
        # utility has published NO version of the agreement — a published one
        # goes as a click-to-accept request (`customers.notifications_seam
        # ._issue_agreement`), which is where the clerk's Step 4 channel is
        # honoured. The held letter is the contract class's own PRINT form, the
        # only channel that class is a form for (`DEF-2473`), whatever the clerk
        # picked; an untick never reaches here at all.
        channels=SERVICE_AGREEMENT_UNPUBLISHED_CHANNELS,
        source_id=service_agreement_source_id(move_record_id),
    )


# ══════════════════════════════════════════════════════════════════════════
# CR-190-BRC10 · STEP 4 — A DEFAULT MAY BE UNTICKED OR RE-CHANNELLED PER MOVE-IN
# ══════════════════════════════════════════════════════════════════════════
#: PO 2026-10-22, verbatim: *"A: allow untick and channel change per move-in"*.
#: Settings still SUPPLY the defaults (`move_in_message_plan`); the clerk may
#: change one move-in's answer for the two messages a move-in itself writes.
#: The deposit receipt and the deposit letter are queued by the PAYMENT at
#: *Pay now* (payments' own money act), not by Complete, so they stay read-only
#: here — recorded as `DEF-CUS-10444` rather than half-wired.
EDITABLE_DEFAULTS: tuple[str, ...] = (EVENT_MOVE_IN, SERVICE_AGREEMENT_KEY)
_DEFAULT_TEMPLATE_BY_KEY = {
    EVENT_MOVE_IN: TEMPLATE_MOVE_IN,
    SERVICE_AGREEMENT_KEY: TEMPLATE_SERVICE_AGREEMENT,
}
#: The class a default actually TRAVELS in, where that is not the class itself.
#: The service agreement is a print form (`PDF + click-to-accept`) and, since
#: lane AGREEMENT (CR-190-BRC10), it reaches the customer as the click-to-accept
#: REQUEST email with the PDF attached — so its email channel is the request
#: class's, read from that class's own listing rather than typed here.
_DELIVERY_TEMPLATES_BY_KEY: dict[str, tuple[str, ...]] = {
    SERVICE_AGREEMENT_KEY: (catalogs.AGREEMENT_REQUEST_EMAIL,),
}


def default_allowed_channels(key: str) -> tuple[str, ...]:
    """The channels a clerk may choose for one move-in default — DERIVED.

    The template class's own channels (`catalogs.channels_for_kind` of its
    listing — an email class is `email`, a `PDF + email` contract is both) plus
    the print floor a move letter already carries (`services
    .CHANNEL_FLOOR_BY_SOURCE`, BR-NOT-024). Nothing is typed here, so when a
    contract class gains email (lane AGREEMENT) the choice grows on its own.
    `()` for a key that is not an editable default.
    """
    code = _DEFAULT_TEMPLATE_BY_KEY.get(key)
    if code is None:
        return ()
    own: list[str] = []
    for each in (*_DELIVERY_TEMPLATES_BY_KEY.get(key, ()), code):
        listing = catalogs.LISTINGS.get(each)
        if listing is not None:
            own.extend(catalogs.channels_for_kind(listing.kind))
    floor = services.CHANNEL_FLOOR_BY_SOURCE.get(SOURCE_MOVE, ())
    return tuple(dict.fromkeys((*own, *floor)))


def _plan_template(code: str, category: str | None) -> dict[str, Any] | None:
    """The template a queue row on this class would PIN today, or None.

    `template_service.resolve` — the dispatcher's own call, so the name and
    version shown are the ones the row will carry. `language` is left to the
    resolver's default because that is what the move-in's write passes
    (`OQ-CUS-12619` (a): messages go in the utility's language).
    """
    from apps.notifications import template_models as tm
    from apps.notifications import template_service

    try:
        pin = template_service.resolve(code=code, category=category)
    except template_service.TemplateRefused:
        return None
    row = tm.NotificationTemplate.objects.filter(pk=pin.template_id).only("name").first()
    listing = catalogs.LISTINGS.get(code)
    name = (row.name if row is not None else None) or (listing.name if listing else code)
    return {"code": code, "name": name, "version": pin.version}


def move_in_message_plan(
    *, category: str | None = None, deposit_taken: bool = False, deposit_cleared: bool = False
) -> tuple[dict[str, Any], ...]:
    """What completing a move-in will put on the outbound queue. READS ONLY.

    `DEF-CUS-6365` — the move-in's review step draws *what goes out to the
    customer* (Accounts blueprint p077). Every row here is a write the save
    really makes, decided by the SAME calls that write makes, so the review and
    the queue cannot disagree:

      * **the welcome** — `queue_move_in_welcome`: EMAIL only, through
        `services.channel_decision(SOURCE_MOVE, …, event_key=EVENT_MOVE_IN)`.
        A move has no print floor, so a utility that switched the event off
        gets no row, and this says so with `channels == []`.
      * **the deposit receipt**, only when the deposit is taken at the move-in
        — `payments.receipts.queue_receipt_for_recorded_payment`: gated on the
        utility's *receipt on record-payment* election (`BR-NOT-022`), then
        print, email and text through the same channel decision, which puts
        print's floor back last (`BR-BIL-036`);
      * **the deposit letter**, only when that deposit is also CLEARED at the
        move-in — `payments.services._hold_and_post` → `queue_deposit_received`:
        EMAIL only, `deposit_received`'s rule deciding.
      * **the service agreement** — ALWAYS listed, and since `DEF-CUS-9743`
        (2026-10-05) ALWAYS queued: `queue_move_in_service_agreement`, on the
        contract class's own PRINT channel, with no event key (no utility rule
        reaches it). Until that fix this row read `channels == []` *by
        construction* and Complete wrote nothing, while CR-171 P1.20 and
        images 45/46 promised it was sent. `template` is None on a utility
        that has published no contract version (`BR-NOT-002`); the row is then
        still written and holds at dispatch, as a missing welcome would.

    ⚠ **THE TWO ROWS p077 DRAWS AND THIS DOES NOT ARE A DELIBERATE DIVERGENCE,
    NOT AN OVERSIGHT.** *The readings this account opened on* and *That a meter
    still has to be read* are drawn UNTICKED, and neither names a template class
    this product has anywhere — no code in `catalogs.LISTINGS`, no event, no
    rule. Listing them would put two rows of pure `—` on a screen the PO asked
    to carry LESS text (`DEF-CUS-6365`, *"reduce this text"*). Decision log
    2026-09-24. **When either class is authored, it belongs here.**

    Nothing else is written by a move-in, so nothing else is listed. Whether a
    queued row then LEAVES the building is the dispatcher's answer and is not
    claimed here. Nothing is written and no clock is read.
    """
    rows: list[dict[str, Any]] = []
    welcome = services.channel_decision(
        SOURCE_MOVE, (models.CHANNEL_EMAIL,), event_key=EVENT_MOVE_IN
    )
    rows.append(
        {
            "key": EVENT_MOVE_IN,
            "channels": list(welcome.channels),
            "template": _plan_template(TEMPLATE_MOVE_IN, category),
            # CR-190-BRC10 — what the clerk may change for THIS move-in.
            "editable": True,
            "allowed_channels": list(default_allowed_channels(EVENT_MOVE_IN)),
        }
    )
    if deposit_taken:
        from apps.notifications import selectors

        channels: list[str] = []
        if selectors.receipt_on_record_payment_election():
            decided = services.channel_decision(
                "payment",
                tuple(channel for channel, _code in RECEIPT_CHANNEL_TEMPLATES),
                event_key=RECEIPT_EVENT,
            )
            channels = list(decided.channels)
        first = next(
            (code for channel, code in RECEIPT_CHANNEL_TEMPLATES if channel in channels), None
        )
        rows.append(
            {
                "key": RECEIPT_EVENT,
                "channels": channels,
                "template": _plan_template(first, category) if first else None,
            }
        )
        if deposit_cleared:
            letter = services.channel_decision(
                SOURCE_ACCOUNT, (models.CHANNEL_EMAIL,), event_key=EVENT_DEPOSIT_RECEIVED
            )
            rows.append(
                {
                    "key": EVENT_DEPOSIT_RECEIVED,
                    "channels": list(letter.channels),
                    "template": _plan_template(TEMPLATE_DEPOSIT, category),
                }
            )
    # LAST, so a move-in that takes a deposit without clearing it draws p077's
    # three rows in p077's order: welcome · deposit receipt · service agreement.
    # `DEF-CUS-9743` — the channels `queue_move_in_service_agreement` will
    # really write, decided by the same call (no event key, so no rule).
    # CR-190-BRC10 — decided under the `agreement` kind the request is queued
    # under (`apps/customers/agreements.py`), which carries no print floor: the
    # letter is the customer's paper choice, added per account at Complete.
    agreement = services.channel_decision(SOURCE_AGREEMENT, SERVICE_AGREEMENT_CHANNELS)
    rows.append(
        {
            "key": SERVICE_AGREEMENT_KEY,
            "channels": list(agreement.channels),
            "template": _plan_template(TEMPLATE_SERVICE_AGREEMENT, category),
            "editable": True,
            "allowed_channels": list(default_allowed_channels(SERVICE_AGREEMENT_KEY)),
        }
    )
    return tuple(rows)


def queue_account_message(
    *,
    message_id: Any,
    account_id: Any,
    channels: tuple[str, ...],
    subject: str,
    body: str,
    signed_by: str,
    on_date: date,
    kind: str = MESSAGE_KIND_COURTESY,
    actor: Any = None,
    job: str | None = None,
    language: str | None = None,
) -> MoveMessage:
    """ONE message a clerk wrote, on every channel they ticked.

    Raises `MoveMessageRefused` — the module's own refusal type, which the
    customers seam already catches — for the three things a human can act on: a
    kind this dialog may not queue, an empty message, and a message id already
    spent on a different account.
    """
    if kind != MESSAGE_KIND_COURTESY:
        owner = REFUSED_MESSAGE_KINDS.get(kind)
        raise MoveMessageRefused(
            f"{kind!r} is not composed from the account screen ({owner or 'unknown kind'}). "
            "BR-PAY-035 maps a reminder's tone to a dunning tier and BR-NOT-008 fixes the "
            "disconnect class, so a ladder step written here would carry no tier and leave "
            "no notice history; a bill copy and a balance statement each already have a "
            "writer. The dialog offers the kind and says who owns it."
        )
    if not (body or "").strip():
        raise MoveMessageRefused(
            "a message with no body is an envelope. The clerk's text IS the document for "
            "this class — `account_message`'s body is one token — so an empty one renders "
            "a blank page at a customer."
        )
    # ⚠ Read DIRECTLY rather than through `selectors.queued_source_ids`, which
    # answers *"has this id been queued"* and does not carry the account — and
    # the account is the whole question here. One row is enough: every row for
    # one message shares its account by construction.
    spent = (
        models.OutboundMessage.objects.filter(
            source_type=SOURCE_MESSAGE, source_id=message_id
        )
        .values_list("account_id", flat=True)
        .first()
    )
    if spent is not None and str(spent) != str(account_id):
        raise MoveMessageRefused(
            "this message id is already queued against another account. The id is the "
            "idempotency key (CLAUDE.md rule 6) and reusing one would dedupe the new "
            "message into the old one — the clerk would be told it was queued and nothing "
            "would have been written."
        )
    write = services.queue_document(
        source_type=SOURCE_MESSAGE,
        source_id=message_id,
        channels=tuple(channels),
        template=services.TemplatePin(code=TEMPLATE_ACCOUNT_MESSAGE),
        account_id=account_id,
        render_context={
            "message_subject": subject,
            "message_body": body,
            "signed_by": signed_by,
        },
        actor=actor,
        job=job or "customers.account_message",
        language=language,
        on_date=on_date,
        # NO `event_key`. See point 3 in the block above — a clerk pressing a
        # button is not a class of message a utility switches off.
    )
    message = write.messages[0] if write.messages else None
    return MoveMessage(
        event_key=SOURCE_MESSAGE,
        move_record_id=str(message_id),
        message_id=str(message.id) if message is not None else None,
        created=bool(message.created) if message is not None else False,
        channels=tuple(item.channel for item in write.messages),
        problems=tuple(write.problems),
    )


def declared_events() -> tuple[rule_catalog.EventClass, ...]:
    """The event rows this module fires (seven since DEF-NOT-10649). Raises `KeyError` if any key stops
    being a row on SET-12, which is the failure a mistyped key would otherwise
    show as a refusal at the end of a committed move, close-out or payment.

    ⚠ TWO UNTIL 2026-08-30; CR-048 wave B task B11 added three."""
    return (
        rule_catalog.event(EVENT_MOVE_IN),
        rule_catalog.event(EVENT_MOVE_OUT),
        rule_catalog.event(EVENT_ACCOUNT_CLOSED),
        rule_catalog.event(EVENT_DEPOSIT_RECEIVED),
        rule_catalog.event(EVENT_RATE_PLAN_CHANGED),
        # DEF-NOT-10649 (2026-10-29) — the cut and the restoration.
        rule_catalog.event(EVENT_SERVICE_DISCONNECTED),
        rule_catalog.event(EVENT_SERVICE_RESTORED),
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-048 wave B task B10 (12-governance/11-change-requests.md → CR-048 · apps/notifications/rule_catalog.py EVENTS `move_in_welcome` + `move_out_final_bill` · apps/notifications/seed_templates.py (EMAIL_WELCOME_BODY, EMAIL_MOVE_OUT_FINAL_BODY) · apps/notifications/catalogs.py CATALOGS (both palettes) · apps/notifications/services.py queue_document (the ONE write path) · apps/customers/services.py move_in / move_out (the two moments) · 04-docs/05-modules/10-notifications/02-business-rules.md BR-NOT-024)
# generated: 2026-08-30 by story-coder (CR-048 wave B tasks B6 + B10 lane)
# checklist: A✔ B=deferred(no frontend half — S19/S20 already draw their own results; the message rides `move_message` on each wizard response for a lane that renders it) C✔ D=deferred(no HTTP surface of its own — reached through the existing move-in and move-out endpoints) E=deferred(as B) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_cr048_b6_b10.py under PostgreSQL — RED PROVED FIRST: a completed move-in queued ZERO messages, quoted in the lane report; the account-keyed idempotency trap was proved by keying both messages on the account and watching the move-out letter dedupe into the welcome with `created=False` and no failure anywhere.
# exceptions: (1) NO PRINT ROW ON EITHER MESSAGE — BR-NOT-024 names four source kinds and a move is none of them; inventing a fifth floor here would be this module writing a signed rule. The consequence (a switched-off event queues nothing) is the ruled behaviour, not a gap. (2) `first_bill_date`, `total_due` and `due_date` ARE OPTIONAL AND USUALLY ABSENT — a move-out issues no invoice and a move-in knows no billing cycle. An absent token renders as a NAMED ABSENCE; a guessed date or total on a customer's own letter would be worse than the gap. (3) THE READ AND ITS UNIT ARE ALL-OR-NOTHING (hard rule 3). (4) NOTHING IS SENT AND NO CLOCK IS READ: one queue row, `dispatcher.dispatch_cycle` delivers, and every date is an argument.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
