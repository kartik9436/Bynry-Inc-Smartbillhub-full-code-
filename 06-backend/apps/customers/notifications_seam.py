# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-004 (S19 Move-In) × US-CUS-005 (S20 Move-Out) ×
#           US-NOT-017 (SET-12 — the rule the queue reads)
#           Screens: S19 · S20 · S8
# Rules:    BR-NOT-017 (the utility's own rule, read on the way to the queue) ·
#           BR-NOT-005 (queue only — nothing here sends) · BR-NOT-024 (print is
#           the floor on bills, receipts, notices and plan letters, and on
#           nothing else) · BR-CUS-150/151 (the move RECORD, whose id keys the
#           message) · BR-SHL-019 (one commit per wizard) · BR-TEN-043 (the
#           business date is an input) · CLAUDE.md rule 6 (idempotency) ·
#           hard-won law 2 (built is not wired) · hard-won law 14 (a failed
#           statement poisons the whole Postgres transaction)
# Change:   CR-048 wave B task B10 — *"the three real omissions"*, the two in
#           this module: **a customer moving in is told nothing**, and the same
#           silence on the way out.
# Tests:    06-backend/tests/test_cr048_b6_b10.py
# Impacts:  apps/customers/services.py `move_in` and `move_out` (their two
#           callers — the point each job completes) ·
#           apps/notifications/customer_events.py (resolved BY NAME, never
#           imported)
# ───────────────────────────────────────────────────────
"""customers → notifications SEAM: the two letters an account's own life sends.

╔══════════════════════════════════════════════════════════════════════════╗
║  WHAT THIS IS FOR, in one sentence a clerk would recognise:              ║
║  a new occupant moves in and receives *"Welcome — your service starts    ║
║  on 3 September"*; an occupant moves out and is told their final bill    ║
║  is coming.                                                              ║
╚══════════════════════════════════════════════════════════════════════════╝

Both wordings have been seeded on every tenant since 2026-08-16 and neither has
ever been sent. `catalogs.LISTINGS` said so in as many words — *"Not in use yet
— a move-in does not send this."*

────────────────────────────────────────────────────────────────────────────
NOTHING THIS FILE DOES MAY REACH THE MOVE — AND A `try` IS NOT ENOUGH
────────────────────────────────────────────────────────────────────────────
⚠ **CATCHING THE EXCEPTION IS NOT ENOUGH ON POSTGRESQL** (hard-won law 14). A
statement that errors inside a Postgres transaction ABORTS the whole
transaction: the `except` catches it, the move-in is already doomed, and the
COMMIT fails afterwards with *"current transaction is aborted"*. SQLite has no
such state, so a `try/except` alone passes the whole suite and loses a
customer's account, their opening reads and their move record the first time the
queue refuses a row in production.

**The savepoint is not the tidy option, it is the only one**, and it must not be
"simplified" away. `apps/payments/run_alert_seam.py` and `apps/payments/
receipts.py` record the same finding from the same day; the `@requires_postgres`
cases in this seam's test drive a REAL `SELECT 1/0` through it and then read the
account and the move record back in a NEW transaction, which is the only way to
prove the savepoint is doing the work rather than the `except`.

The `except` is broad for the reason `receipts.py` gives: the queue now reads a
tenant rule table before it writes, and a bug in that read must not take a
move-in down.

────────────────────────────────────────────────────────────────────────────
WHY A SEAM FILE AND NOT A CALL INSIDE `services.py`
────────────────────────────────────────────────────────────────────────────
Customers must not import notifications (B1 · B2 §2). The entry points are
resolved BY NAME at call time — the idiom `apps/payments/run_alert_seam.py`,
`receipts.py` and `notices.py` all use — so the whole contract between the two
modules reads in one file.

⚠ **THE EVENT KEY IS NOT SPELLED HERE.** `queue_move_in_welcome` names its own
event, so this seam resolves a SYMBOL rather than typing a string, and a
mistyped key cannot refuse at the end of a committed move.
"""

from __future__ import annotations

from datetime import date
from importlib import import_module
from typing import Any

from django.db import transaction

#: The notifications contract this module depends on, named once so it is
#: greppable from BOTH sides of the boundary (the `receipts.py` discipline).
MESSAGE_MODULE = "notifications"
MESSAGE_KIND = "customer_events"
WRITE_MOVE_IN = "queue_move_in_welcome"
#: `DEF-CUS-9743` — the second default a move-in sends (CR-171 P1.20).
WRITE_SERVICE_AGREEMENT = "queue_move_in_service_agreement"
WRITE_MOVE_OUT = "queue_move_out_final"
#: ⚠ ADDED 2026-08-30 · CR-048 wave B task B11. Two more moments this module
#: owns and had no letter for: closing an account for good, and moving an
#: account to a different RATE plan. (The third account-lifecycle letter, the
#: deposit confirmation, fires from PAYMENTS and reaches its entry point through
#: that module's own seam — the money arrives there, not here.)
WRITE_ACCOUNT_CLOSED = "queue_account_closed"
#: ⚠ ADDED 2026-09-12 · `CR-094-BRC01` wave K · `ACC-S16`. The fifth entry
#: point, and the first one a HUMAN triggers on purpose — see
#: `queue_account_message` below for why it does not go through `_guarded`.
WRITE_ACCOUNT_MESSAGE = "queue_account_message"
#: Two READS beside the four writes, both published by the same module so the
#: dialog and the dispatcher cannot disagree about what a channel does.
READ_MESSAGE_KINDS = "message_kinds"
READ_CHANNEL_REACHABILITY = "channel_reachability"

#: The utility's own published wording, so a clerk starts from an agreed
#: letter instead of a blank box (PO 2026-09-13).
READ_MESSAGE_TEMPLATES = "account_message_templates"
#: `DEF-CUS-6365` — what a move-in's save will queue, for its review step.
READ_MOVE_IN_MESSAGE_PLAN = "move_in_message_plan"
WRITE_RATE_PLAN_CHANGE = "queue_rate_plan_change"
#: `DEF-NOT-10649` (PO 2026-10-29, *"1 A, 2 A, 3 A, 4 A"*) — the cut and the
#: restoration tell the customer, by email and (where they chose it) by text.
WRITE_SERVICE_DISCONNECTED = "queue_service_disconnected"
WRITE_SERVICE_RESTORED = "queue_service_restored"
#: The owner's own refusal type, resolved the same way. A refusal is the queue
#: saying no for a reason a human can act on, and it is not a fault.
MESSAGE_REFUSAL = "MoveMessageRefused"

#: Outcome CODES, because S19/S20 and the move worklists group on them rather
#: than parsing prose. Every one ends up on the wizard's own response.
MOVE_MESSAGE_QUEUED = "move_message_queued"
MOVE_MESSAGE_ALREADY_QUEUED = "move_message_already_queued"
MOVE_MESSAGE_SUPPRESSED = "move_message_suppressed_by_rule"
MOVE_MESSAGE_UNAVAILABLE = "move_message_unavailable"
MOVE_MESSAGE_REFUSED = "move_message_refused"
MOVE_MESSAGE_ERROR = "move_message_error"

BR_REF = "BR-NOT-017"


def _resolve(attribute: str) -> Any:
    """Notifications' published callable, or None while it publishes none."""
    try:
        target = import_module(f"apps.{MESSAGE_MODULE}.{MESSAGE_KIND}")
    except ImportError:  # pragma: no cover - notifications ships in this repo
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


def entry_points() -> dict[str, Any]:
    """The entry points, resolved by name. Published so a test can assert this
    seam reaches real functions rather than trusting a docstring (hard-won law
    1). ⚠ TWO UNTIL 2026-08-30; CR-048 B11 added two, and `CR-094-BRC01` wave K
    added the clerk's own message plus the two reads its dialog needs — the
    reads are here for the same reason the writes are: a name that stops
    resolving is a control that silently does nothing."""
    return {
        name: _resolve(name)
        for name in (
            WRITE_MOVE_IN,
            WRITE_SERVICE_AGREEMENT,
            WRITE_MOVE_OUT,
            WRITE_ACCOUNT_CLOSED,
            WRITE_RATE_PLAN_CHANGE,
            WRITE_SERVICE_DISCONNECTED,
            WRITE_SERVICE_RESTORED,
            WRITE_ACCOUNT_MESSAGE,
            READ_MESSAGE_KINDS,
            READ_CHANNEL_REACHABILITY,
            READ_MESSAGE_TEMPLATES,
            READ_MOVE_IN_MESSAGE_PLAN,
        )
    }


def _unavailable(write_name: str) -> tuple[dict[str, Any], ...]:
    return (
        {
            "code": MOVE_MESSAGE_UNAVAILABLE,
            "br_ref": BR_REF,
            "detail": f"apps.{MESSAGE_MODULE}.{MESSAGE_KIND}.{write_name} is not published, "
            "so no message could be queued for this move. The move itself completed; "
            "this is reported rather than swallowed.",
        },
    )


def _outcome(message: Any, *, what: str) -> tuple[dict[str, Any], ...]:
    problems = tuple(getattr(message, "problems", ()) or ())
    if getattr(message, "message_id", None) is None:
        # The rule left no channel. A move message has NO print floor
        # (BR-NOT-024 names four source kinds and a move is none of them), so a
        # utility that switched this event off really does get nothing — which
        # is what switching it off means. The reason travels so the wizard can
        # say so instead of the letter silently not existing.
        return (
            {
                "code": MOVE_MESSAGE_SUPPRESSED,
                "br_ref": BR_REF,
                "event_key": getattr(message, "event_key", None),
                "detail": f"no {what} was queued because this utility's own notification "
                "rule left no channel. The move completed normally.",
            },
            *problems,
        )
    created = bool(getattr(message, "created", False))
    return (
        {
            "code": MOVE_MESSAGE_QUEUED if created else MOVE_MESSAGE_ALREADY_QUEUED,
            "br_ref": BR_REF,
            "event_key": getattr(message, "event_key", None),
            "message_id": str(message.message_id),
            # `DEF-CUS-9757` — one welcome is a row PER CHANNEL (email and the
            # printed letter), so *Move-in completed* counts the channels.
            "channels": list(getattr(message, "channels", ()) or ()),
            # `DEF-NOT-10537` (2026-10-22): the sentence said email *"will not
            # leave the building until an adapter is plugged in"* — false once
            # the Custom SMTP adapter went live. Only the true half stays.
            "detail": (
                f"the {what} is on the outbound queue — the row, its recipient and "
                "its wording are all real."
                if created
                else f"this move's {what} was already queued, so nothing was written. A "
                "replayed wizard says it once (CLAUDE.md rule 6)."
            ),
        },
        *problems,
    )


def _guarded(
    write: Any, *, what: str, write_name: str, **kwargs: Any
) -> tuple[dict[str, Any], ...]:
    """One call, inside its OWN savepoint. Raises nothing, ever."""
    try:
        # ⚠ THE SAVEPOINT IS THE POINT. See the module docstring: on PostgreSQL
        # a `try` alone loses the whole move at COMMIT. Do not "simplify" this.
        with transaction.atomic():
            message = write(**kwargs)
    except Exception as failure:  # noqa: BLE001 — the one boundary where broad is right
        refusal = _resolve(MESSAGE_REFUSAL)
        refused = refusal is not None and isinstance(failure, refusal)
        return (
            {
                "code": MOVE_MESSAGE_REFUSED if refused else MOVE_MESSAGE_ERROR,
                "br_ref": BR_REF,
                "detail": f"the {what} could not be queued: {failure} The move stands — a "
                "failed notification must never fail the work it describes.",
            },
        )
    return _outcome(message, what=what)


def move_in_default_channels(key: str) -> tuple[str, ...]:
    """`CR-190-BRC10` — the channels a clerk may pick for one move-in default
    (`customer_events.default_allowed_channels`). `()` for a key that is not
    editable, or while notifications publishes no answer — then any choice is
    refused rather than trusted."""
    read = _resolve("default_allowed_channels")
    return tuple(read(key) or ()) if read is not None else ()


def move_in_message_plan(
    *, category: str | None, deposit_taken: bool, deposit_cleared: bool = False
) -> tuple[dict[str, Any], ...] | None:
    """`DEF-CUS-6365` — the messages completing a move-in will queue, or None
    when notifications publishes no answer (the review then draws nothing
    rather than a guess). A READ: nothing is written."""
    read = _resolve(READ_MOVE_IN_MESSAGE_PLAN)
    if read is None:  # pragma: no cover - defensive
        return None
    return tuple(
        read(category=category, deposit_taken=deposit_taken, deposit_cleared=deposit_cleared)
    )


def queue_move_in_welcome(
    *,
    move_record_id: Any,
    account_id: Any,
    effective_on: date,
    channels: tuple[str, ...] | None = None,
    actor: Any = None,
) -> tuple[dict[str, Any], ...]:
    """The welcome letter for one completed move-in. Outcome rows only.

    `move_record_id` is the MOVE RECORD's id and is what makes a replayed wizard
    find its own message and write nothing — never the account's, which the
    move-out letter would later collide with (the whole argument is in
    `apps/notifications/customer_events.py`'s docstring).

    `effective_on` is the business date the account actually holds, read back
    off the written row (BR-TEN-043).

    **This function raises nothing.** Queued, already queued, suppressed by the
    utility's own switch, refused, or broken outright — each comes back as a row
    the caller carries on its result.
    """
    write = _resolve(WRITE_MOVE_IN)
    if write is None:  # pragma: no cover - defensive
        return _unavailable(WRITE_MOVE_IN)
    return _guarded(
        write,
        what="welcome message",
        write_name=WRITE_MOVE_IN,
        move_record_id=move_record_id,
        account_id=account_id,
        effective_on=effective_on,
        # CR-190-BRC10 — the clerk's Step 4 channel, already validated.
        channels=channels,
        actor=actor,
        job=None if actor is not None else "customers.move_in",
    )


def queue_move_in_service_agreement(
    *,
    move_record_id: Any,
    account_id: Any,
    effective_on: date,
    channels: tuple[str, ...] | None = None,
    actor: Any = None,
) -> tuple[dict[str, Any], ...]:
    """The service agreement for one completed move-in. Outcome rows only.

    `DEF-CUS-9743` — CR-171 P1.20's second default, listed on Review and,
    until this, queued by nothing. Keyed by notifications on a key DERIVED
    from the move record, so it never dedupes into the welcome and a replayed
    wizard writes it once. Raises nothing, for `queue_move_in_welcome`'s
    reason: a letter that cannot be queued never fails the move it describes.
    """
    # `CR-190-BRC10` (PO 2026-10-22, answer 1 — *"email it as a PDF attachment
    # (plus a letter if the customer wants paper)"*): the agreement now goes as
    # a click-to-accept REQUEST — `agreements.issue`, its own savepoint, keyed
    # on the move record. A utility that has published no version of the
    # agreement (`BR-NOT-002` seeds none) falls through to the old write below,
    # which holds at dispatch saying what it waits for.
    issued = _issue_agreement(
        move_record_id=move_record_id, account_id=account_id, actor=actor, channels=channels
    )
    if issued is not None:
        return issued
    write = _resolve(WRITE_SERVICE_AGREEMENT)
    if write is None:  # pragma: no cover - defensive
        return _unavailable(WRITE_SERVICE_AGREEMENT)
    return _guarded(
        write,
        what="service agreement",
        write_name=WRITE_SERVICE_AGREEMENT,
        move_record_id=move_record_id,
        account_id=account_id,
        effective_on=effective_on,
        # CR-190-BRC10 — the clerk's Step 4 channel, already validated.
        channels=channels,
        actor=actor,
        job=None if actor is not None else "customers.move_in",
    )


def _issue_agreement(
    *,
    move_record_id: Any,
    account_id: Any,
    actor: Any,
    channels: tuple[str, ...] | None = None,
) -> tuple[dict[str, Any], ...] | None:
    """The move-in's agreement as a click-to-accept request, or None when the
    utility has published no version of it (the caller then queues the held
    letter, as before). Raises nothing — a failed agreement never fails the
    move it belongs to."""
    from apps.customers import agreements
    from apps.customers.agreement_models import ORIGIN_MOVE_IN

    code = getattr(
        import_module(f"apps.{MESSAGE_MODULE}.{MESSAGE_KIND}"), "TEMPLATE_SERVICE_AGREEMENT"
    )
    try:
        with transaction.atomic():  # law 14 — the move survives any failure here
            result = agreements.issue(
                actor,
                account_id,
                code,
                origin=ORIGIN_MOVE_IN,
                origin_id=move_record_id,
                job=None if actor is not None else "customers.move_in",
                # CR-190-BRC10 — the clerk's Step 4 channel, already validated.
                channels=channels,
            )
    except agreements.AgreementRefused as refused:
        if refused.code == "agreement_not_published":
            return None
        return ({"code": MOVE_MESSAGE_REFUSED, "br_ref": BR_REF, "detail": refused.code},)
    except Exception as failure:  # noqa: BLE001 — the one boundary where broad is right
        return (
            {
                "code": MOVE_MESSAGE_ERROR,
                "br_ref": BR_REF,
                "detail": f"the service agreement could not be sent: {failure} The move stands.",
            },
        )
    delivery = result.get("delivery") or {}
    channels = [
        channel
        for channel, key in (("email", "email"), ("pdf_print", "letter"))
        if delivery.get(key)
    ]
    first = (delivery.get("email") or delivery.get("letter") or {}).get("id")
    return (
        {
            # The welcome's own codes, so *Move-in completed* counts it as it
            # counts every queued move message (`move_in_complete.what_happened`).
            "code": MOVE_MESSAGE_QUEUED if result.get("created") else MOVE_MESSAGE_ALREADY_QUEUED,
            "br_ref": "CR-190-BRC10",
            "event_key": None,
            "message_id": first,
            "channels": channels,
            "agreement": result["request"],
            "detail": "the service agreement is on the outbound queue with its acceptance link.",
        },
        *tuple(delivery.get("problems") or ()),
    )


def queue_move_out_final(
    *,
    move_record_id: Any,
    account_id: Any,
    effective_on: date,
    closing_reads: Any = None,
    final_bill: dict[str, Any] | None = None,
    actor: Any = None,
) -> tuple[dict[str, Any], ...]:
    """The final-bill email for one completed move-out. Outcome rows only.

    ⚠ **AMENDED 2026-10-22 — `DEF-NOT-10536`.** This said *"the closing read,
    the total and the due date are not passed … a move-out issues no
    invoice"*. Since `DEF-CUS-10093` (2026-10-13) Complete DRAFTS the final
    bill, and the PO ruled the email carries that draft's figures and its PDF
    (*"B: send at move-out completion with the draft figures"*). So:

      * `closing_reads` is metering's `reads_for_unit` answer the move-out
        already swept after committing its reads — each reading WITH its unit
        (hard rule 3), never a count;
      * `final_bill` is billing's draft answer (`outcome`, `invoice_id`,
        `total`, `currency`); when it is `drafted`, billing is asked here for
        the page issue would keep and the due date it would stamp
        (`seams.final_bill_email_document`).

    Both are asked INSIDE `_guarded`'s savepoint, so a page that cannot be
    produced costs the email and never the move-out.
    """
    write = _resolve(WRITE_MOVE_OUT)
    if write is None:  # pragma: no cover - defensive
        return _unavailable(WRITE_MOVE_OUT)

    def _write(**kwargs: Any) -> Any:
        document = None
        if final_bill and final_bill.get("outcome") == "drafted":
            from apps.customers import seams

            document = seams.final_bill_email_document(final_bill.get("invoice_id"))
        return write(final_bill_document=document, **kwargs)

    return _guarded(
        _write,
        what="final-bill message",
        write_name=WRITE_MOVE_OUT,
        move_record_id=move_record_id,
        account_id=account_id,
        effective_on=effective_on,
        closing_reads=closing_reads,
        final_bill=final_bill,
        actor=actor,
        job=None if actor is not None else "customers.move_out",
    )


def queue_account_closed(
    *,
    case_id: Any,
    account_id: Any,
    closed_on: date,
    closing_balance: str | None = None,
    actor: Any = None,
) -> tuple[dict[str, Any], ...]:
    """The confirmation for one closed-out account. Outcome rows only.

    ⚠ ADDED 2026-08-30 · CR-048 wave B task B11. `catalogs.LISTINGS` has read
    *"Not in use yet — closing an account does not send this."* since
    2026-08-16; this is where that stops being true.

    `case_id` is the DISCONNECT CASE the close-out closed, and it — not the
    account — is what keys the letter. The whole argument, including why an
    account that is moved out of and later closed must get two letters rather
    than one, is in `apps/notifications/customer_events.py`.

    `closing_balance` is a STRING or `None`, and **`None` is not zero**: the AR
    read can fail, and BR-CUS-015 is emphatic that a failed read must never
    become a $0.00 on a customer's own letter.

    **This function raises nothing** — the savepoint and the broad `except` in
    `_guarded` are the module docstring's subject and hard-won law 14's.
    """
    write = _resolve(WRITE_ACCOUNT_CLOSED)
    if write is None:  # pragma: no cover - defensive
        return _unavailable(WRITE_ACCOUNT_CLOSED)
    return _guarded(
        write,
        what="account-closed confirmation",
        write_name=WRITE_ACCOUNT_CLOSED,
        case_id=case_id,
        account_id=account_id,
        closed_on=closed_on,
        closing_balance=closing_balance,
        actor=actor,
        job=None if actor is not None else "customers.close_out",
    )


# ══════════════════════════════════════════════════════════════════════════
# DEF-NOT-10649 — THE CUT AND THE RESTORATION TELL THE CUSTOMER
# ══════════════════════════════════════════════════════════════════════════
# PO 2026-10-29, *"1 A, 2 A, 3 A, 4 A"*. Called by `disconnects.commit_cut`
# and `disconnects.restore_service` INSIDE their transactions, after the act is
# written, so a refused or rolled-back act queues nothing. Each call opens its
# OWN savepoint (hard-won law 14 — on PostgreSQL a caught exception aborts the
# whole transaction otherwise) and RAISES NOTHING: a message that could not be
# queued never fails the cut or the restoration it describes.
NOTICE_QUEUED = "service_notice_queued"
NOTICE_ALREADY_QUEUED = "service_notice_already_queued"
NOTICE_SWITCHED_OFF = "service_notice_switched_off"
NOTICE_NOT_QUEUED = "service_notice_not_queued"


def _service_notice(write_name: str, **kwargs: Any) -> dict[str, Any]:
    """One savepointed call → the `notification_queued` block on the act's answer."""
    write = _resolve(write_name)
    if write is None:  # pragma: no cover - notifications ships in this repo
        return {
            "code": NOTICE_NOT_QUEUED,
            "message_ids": [],
            "channels": [],
            "created": False,
            "problems": list(_unavailable(write_name)),
        }
    try:
        with transaction.atomic():  # the savepoint — law 14; do not "simplify"
            message = write(**kwargs)
    except Exception as failure:  # noqa: BLE001 — the one boundary where broad is right
        return {
            "code": NOTICE_NOT_QUEUED,
            "message_ids": [],
            "channels": [],
            "created": False,
            "problems": [{"code": MOVE_MESSAGE_ERROR, "br_ref": BR_REF, "detail": str(failure)}],
        }
    ids = list(getattr(message, "message_ids", ()) or ())
    created = bool(getattr(message, "created", False))
    return {
        "code": (
            NOTICE_SWITCHED_OFF
            if not ids
            else NOTICE_QUEUED
            if created
            else NOTICE_ALREADY_QUEUED
        ),
        "event_key": getattr(message, "event_key", None),
        "message_ids": ids,
        "channels": list(getattr(message, "channels", ()) or ()),
        "created": created,
        "problems": [dict(problem) for problem in getattr(message, "problems", ()) or ()],
    }


def queue_service_disconnected(
    *,
    case_id: Any,
    account_id: Any,
    cut_on: date,
    terms: dict[str, Any] | None = None,
    closing_reads: Any = None,
    currency: str | None = None,
    actor: Any = None,
) -> dict[str, Any]:
    """*Service disconnected*, by email and text. Never raises.

    `terms` is `disconnects.reconnection_terms` read AFTER the cut (the fee is
    then inside the position); `closing_reads` is metering's `reads_for_unit`
    answer after the cut posted its reading. When either is not given it is
    read here, through this module's own doors, so a replay from anywhere
    states the same figures.
    """
    if terms is None:
        from apps.customers import disconnects

        terms = disconnects.reconnection_terms(account_id)
    return _service_notice(
        WRITE_SERVICE_DISCONNECTED,
        case_id=case_id,
        account_id=account_id,
        cut_on=cut_on,
        terms=terms,
        closing_reads=closing_reads,
        currency=currency,
        actor=actor,
        job=None if actor is not None else "customers.disconnects.commit_cut",
    )


def queue_service_restored(
    *, case_id: Any, account_id: Any, restored_on: date, actor: Any = None
) -> dict[str, Any]:
    """*Service restored*, by email and text. Never raises."""
    return _service_notice(
        WRITE_SERVICE_RESTORED,
        case_id=case_id,
        account_id=account_id,
        restored_on=restored_on,
        actor=actor,
        job=None if actor is not None else "customers.disconnects.restore_service",
    )


def message_kinds() -> tuple[dict[str, Any], ...]:
    """What the Communication dialog may offer, and which kinds are refused."""
    read = _resolve(READ_MESSAGE_KINDS)
    return tuple(read()) if read is not None else ()


def message_templates(
    *,
    language: str | None = None,
    channels: tuple[str, ...] = (),
    preferred_language: str | None = None,
) -> tuple[dict[str, Any], ...]:
    """The published wording the Communication dialog may start a clerk from.

    An empty tuple means notifications published no answer, which the dialog
    renders as *no ready-made messages* rather than as a broken picker — the
    same honest absence `channel_reachability` returns for an unknown route.
    """
    read = _resolve(READ_MESSAGE_TEMPLATES)
    if read is None:
        return ()
    return tuple(
        read(
            language=language,
            channels=tuple(channels),
            preferred_language=preferred_language,
        )
    )


def channel_reachability(channels: tuple[str, ...] = ()) -> tuple[dict[str, Any], ...]:
    """Per channel, whether a queued row will actually leave this deployment.

    `BR-NOT-013` — delivery is out of this release on post, email and SMS alike
    — is the reason the dialog asks at all. An empty tuple means notifications
    published no answer, which a screen must render as *unknown* rather than as
    *yes*.
    """
    read = _resolve(READ_CHANNEL_REACHABILITY)
    return tuple(read(tuple(channels))) if read is not None else ()


def queue_account_message(
    *,
    message_id: Any,
    account_id: Any,
    channels: tuple[str, ...],
    subject: str,
    body: str,
    signed_by: str,
    on_date: date,
    kind: str,
    actor: Any = None,
    language: str | None = None,
) -> dict[str, Any]:
    """The message a clerk typed, queued on every channel they ticked.

    ⚠ **THIS IS THE ONE WRITE IN THIS FILE THAT MUST NOT SWALLOW ITS REFUSAL,
    AND IT IS THE OPPOSITE OF WHAT `_guarded` IS FOR.** Every other entry point
    here rides along with a job — a move-in, a close-out — and the module
    docstring's rule is that *"a failed notification must never fail the work it
    describes"*. Here the notification **is** the work: a clerk pressed *Queue
    the message* and nothing else happened on that request. Reporting a refusal
    as an outcome row on a 200 would put *"Queued"* on the screen over a message
    that was never written — which is the exact failure `ACC-S16` exists to
    prevent, one layer down.

    So this returns a dict with `refused` set, and the endpoint turns that into
    a refusal the clerk reads. The savepoint stays, because hard-won law 14 is
    about PostgreSQL's aborted-transaction state and not about who reports the
    error.
    """
    write = _resolve(WRITE_ACCOUNT_MESSAGE)
    if write is None:  # pragma: no cover - notifications ships in this repo
        return {
            "refused": True,
            "code": MOVE_MESSAGE_UNAVAILABLE,
            "detail": _unavailable(WRITE_ACCOUNT_MESSAGE)[0]["detail"],
            "message_id": None,
            "channels": (),
            "problems": (),
        }
    try:
        with transaction.atomic():
            message = write(
                message_id=message_id,
                account_id=account_id,
                channels=tuple(channels),
                subject=subject,
                body=body,
                signed_by=signed_by,
                on_date=on_date,
                kind=kind,
                actor=actor,
                language=language,
                job=None if actor is not None else "customers.account_message",
            )
    except Exception as failure:  # noqa: BLE001 — reported, never swallowed
        refusal = _resolve(MESSAGE_REFUSAL)
        refused = refusal is not None and isinstance(failure, refusal)
        return {
            "refused": True,
            "code": MOVE_MESSAGE_REFUSED if refused else MOVE_MESSAGE_ERROR,
            "detail": str(failure),
            "message_id": None,
            "channels": (),
            "problems": (),
        }
    return {
        "refused": False,
        "code": MOVE_MESSAGE_QUEUED if message.created else MOVE_MESSAGE_ALREADY_QUEUED,
        "detail": None,
        "message_id": message.message_id,
        "channels": tuple(message.channels),
        "problems": tuple(message.problems),
    }


# ═══════════════════════════════════════════════════════════════════════════
# CR-094-BRC01 · DEF-CUS-5389 — the three things a SERVICE REQUEST says to the
# person who raised it
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **A SECOND NOTIFICATIONS MODULE, RESOLVED THE SAME WAY, AND IT IS A SECOND
# MODULE RATHER THAN FOUR MORE FUNCTIONS IN `customer_events` FOR ONE REASON:
# THE RECIPIENT IS NOT A CUSTOMER.** Everything in `customer_events` addresses
# somebody with an account. An APPLICANT has none — no account, no customer row,
# no `contacts` entry — so the address travels IN from this module instead of
# being looked up, `account_id` stays NULL on the queue row, and the palette
# those letters render from has no `{account_no}` in it.
#
# ⚠ **AND THE FAILURE POSTURE IS `_guarded`'s AND NOT
# `queue_account_message`'s.** Directly above, the clerk's account message
# reports its refusal on the response because THE NOTIFICATION IS THE WORK: a
# clerk pressed *Queue the message* and nothing else happened. Here the work is
# refusing a request or asking for more, and it has already committed by the
# time the letter is attempted — so a queue failure must never take it down. The
# clerk is told on the response instead, through the outcome rows, which is what
# `_guarded` exists to produce.
MESSAGE_KIND_SERVICE_REQUEST = "service_request_events"
WRITE_REQUEST_ACKNOWLEDGEMENT = "queue_request_acknowledgement"
WRITE_REQUEST_REFUSED = "queue_request_refused"
WRITE_REQUEST_MORE_INFO = "queue_request_more_info"
#: ⚠ ADDED 2026-09-15 · `CR-094-BRC01` lane J. The fourth applicant write, and
#: the one the PO asked about: *"at the time of approval we are also linking
#: notification and templates to the modal - are you ensuring it will work?"*
#: Approving a request queued NOTHING before this — the drawn row five of
#: `What goes out to the applicant` fires `On approve or refuse`, and only the
#: refuse half of it existed.
WRITE_REQUEST_APPROVED = "queue_request_approved"
WRITE_REQUEST_EXTRA = "queue_request_extra_message"
#: The picker's READ, beside the four writes. Published by the module that owns
#: the template registry so the picker and the dispatcher cannot disagree about
#: which version is live or which row is a draft — the same reasoning
#: `channel_reachability` carries one section up.
READ_APPLICANT_TEMPLATES = "applicant_templates"
#: That module's own refusal type. Resolved SEPARATELY from `MESSAGE_REFUSAL`
#: above, because catching a move's refusal type on a service request's failure
#: path would report every real problem as `..._error` and lose the sentence a
#: human could have acted on.
SERVICE_REQUEST_REFUSAL = "ApplicantMessageRefused"

#: Outcome CODES for the applicant messages. Distinct from the `move_*` family
#: so a screen, a log line or a test can tell which kind of message it is
#: reading without parsing prose.
APPLICANT_MESSAGE_QUEUED = "applicant_message_queued"
APPLICANT_MESSAGE_ALREADY_QUEUED = "applicant_message_already_queued"
APPLICANT_MESSAGE_REFUSED = "applicant_message_refused"
APPLICANT_MESSAGE_ERROR = "applicant_message_error"
APPLICANT_MESSAGE_UNAVAILABLE = "applicant_message_unavailable"

SR_BR_REF = "BR-CUS-079"


def _resolve_service_request(attribute: str) -> Any:
    """The applicant-message module's published callable, or None."""
    try:
        target = import_module(f"apps.{MESSAGE_MODULE}.{MESSAGE_KIND_SERVICE_REQUEST}")
    except ImportError:  # pragma: no cover - notifications ships in this repo
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


def service_request_entry_points() -> dict[str, Any]:
    """The three entry points, resolved by name — published so a test can assert
    this seam reaches real functions rather than trusting a docstring (hard-won
    law 1). A name that stops resolving here is a letter that silently stops
    being written, which is the exact shape of the absence this wave closed."""
    return {
        name: _resolve_service_request(name)
        for name in (
            WRITE_REQUEST_ACKNOWLEDGEMENT,
            WRITE_REQUEST_REFUSED,
            WRITE_REQUEST_MORE_INFO,
            WRITE_REQUEST_APPROVED,
            WRITE_REQUEST_EXTRA,
            READ_APPLICANT_TEMPLATES,
        )
    }


def _applicant_outcome(message: Any, *, what: str) -> dict[str, Any]:
    """One row a caller can put on its response and store on its timeline."""
    created = bool(getattr(message, "created", False))
    return {
        "code": APPLICANT_MESSAGE_QUEUED if created else APPLICANT_MESSAGE_ALREADY_QUEUED,
        "br_ref": SR_BR_REF,
        "message_id": (str(message.message_id) if getattr(message, "message_id", None) else None),
        "template_code": getattr(message, "template_code", None),
        "channels": tuple(getattr(message, "channels", ()) or ()),
        #: WHERE a real deployment would send it. Carried because proving a row
        #: exists and proving it is addressed to the right person are two
        #: different claims, and only the second one is worth anything to a
        #: clerk looking at a request.
        "address": getattr(message, "address", None),
        # `DEF-NOT-10537`: the false *"no delivery adapter exists on any
        # channel yet"* clause is gone (2026-10-22); the true half stays.
        "detail": (
            f"the {what} is on the outbound queue, addressed to the applicant — the "
            "row, its recipient and its wording are all real."
            if created
            else f"this {what} was already queued, so nothing was written. A replayed "
            "action says it once."
        ),
        "problems": tuple(getattr(message, "problems", ()) or ()),
    }


def _guarded_applicant(write: Any, *, what: str, **kwargs: Any) -> dict[str, Any]:
    """One call, inside its OWN savepoint. Raises nothing, ever.

    ⚠ **THE SAVEPOINT IS THE POINT AND IT IS NOT TIDINESS** (hard-won law 14).
    On PostgreSQL a statement that errors inside a transaction ABORTS the whole
    transaction: a plain `try` catches the exception, the refusal that already
    happened is doomed, and the COMMIT fails afterwards with *"current
    transaction is aborted"*. SQLite has no such state, so the version without
    this passes the entire suite and loses a refusal the first time the queue
    says no in production. Do not "simplify" it away.
    """
    try:
        with transaction.atomic():
            message = write(**kwargs)
    except Exception as failure:  # noqa: BLE001 — the one boundary where broad is right
        refusal = _resolve_service_request(SERVICE_REQUEST_REFUSAL)
        refused = refusal is not None and isinstance(failure, refusal)
        return {
            "code": APPLICANT_MESSAGE_REFUSED if refused else APPLICANT_MESSAGE_ERROR,
            "br_ref": SR_BR_REF,
            "message_id": None,
            "template_code": None,
            "channels": (),
            "address": None,
            "detail": f"the {what} could not be queued: {failure} The decision stands — a "
            "failed message must never undo the act it describes.",
            "problems": (),
        }
    return _applicant_outcome(message, what=what)


def _applicant_unavailable(write_name: str, *, what: str) -> dict[str, Any]:
    return {
        "code": APPLICANT_MESSAGE_UNAVAILABLE,
        "br_ref": SR_BR_REF,
        "message_id": None,
        "template_code": None,
        "channels": (),
        "address": None,
        "detail": f"apps.{MESSAGE_MODULE}.{MESSAGE_KIND_SERVICE_REQUEST}.{write_name} is not "
        f"published, so no {what} could be queued. The decision itself completed; this is "
        "reported rather than swallowed.",
        "problems": (),
    }


def queue_request_acknowledgement(**fields: Any) -> dict[str, Any]:
    """`BR-CUS-079` — an applicant is told their request arrived.

    Keyed on the REQUEST, so a replayed submit finds its own row and writes
    nothing. Which of the two acknowledgement classes renders it is decided by
    whether a receipt number is passed — `BR-CUS-090` clause (3), made
    structural on the other side of this seam.
    """
    write = _resolve_service_request(WRITE_REQUEST_ACKNOWLEDGEMENT)
    if write is None:  # pragma: no cover - notifications ships in this repo
        return _applicant_unavailable(WRITE_REQUEST_ACKNOWLEDGEMENT, what="acknowledgement")
    return _guarded_applicant(write, what="acknowledgement", **fields)


def queue_request_refused(**fields: Any) -> dict[str, Any]:
    """The refusal letter the blueprint's Refuse dialog promises the applicant.

    Keyed on the `service_request_events` row recording the refusal, never on
    the request — a request refused, reopened and refused again must send two
    letters rather than dedupe the second into the first.
    """
    write = _resolve_service_request(WRITE_REQUEST_REFUSED)
    if write is None:  # pragma: no cover - notifications ships in this repo
        return _applicant_unavailable(WRITE_REQUEST_REFUSED, what="refusal letter")
    return _guarded_applicant(write, what="refusal letter", **fields)


def queue_request_more_info(**fields: Any) -> dict[str, Any]:
    """The message a clerk types when they ask an applicant for more.

    It replaces one fixed sentence sent to every request alike, and it is keyed
    on the ask's own timeline row, because a request can be asked twice.
    """
    write = _resolve_service_request(WRITE_REQUEST_MORE_INFO)
    if write is None:  # pragma: no cover - notifications ships in this repo
        return _applicant_unavailable(WRITE_REQUEST_MORE_INFO, what="message")
    return _guarded_applicant(write, what="message", **fields)


def queue_request_approved(**fields: Any) -> dict[str, Any]:
    """The letter an applicant gets when their request is APPROVED.

    ⚠ **THIS IS THE HALF THAT DID NOT EXIST**, and it is the PO's own question
    of 2026-09-15 about the approval modal. The drawn row five fires *"On
    approve or refuse"*; refusing has queued a letter since `BR-CUS-1075`, and
    approving queued nothing at all, so the one decision an applicant actually
    wants to hear about was the one this product never told them.

    Keyed on the REQUEST rather than on a timeline row, which is the opposite
    of the refusal letter beside it and is right for the opposite reason: a
    request is approved ONCE. `approve` refuses a request that is not
    approvable, so a second approval cannot reach here through the front door —
    but a retried call, a double-clicked button and a replayed job all can, and
    the key is what makes *"approving twice queues one, not two"* true rather
    than likely (CLAUDE.md rule 6).
    """
    write = _resolve_service_request(WRITE_REQUEST_APPROVED)
    if write is None:  # pragma: no cover - notifications ships in this repo
        return _applicant_unavailable(WRITE_REQUEST_APPROVED, what="approval letter")
    return _guarded_applicant(write, what="approval letter", **fields)


def queue_request_extra_message(**fields: Any) -> dict[str, Any]:
    """`DEF-CUS-10042` — a message a clerk added to a request, keyed on its row."""
    write = _resolve_service_request(WRITE_REQUEST_EXTRA)
    if write is None:  # pragma: no cover - notifications ships in this repo
        return _applicant_unavailable(WRITE_REQUEST_EXTRA, what="added message")
    return _guarded_applicant(write, what="added message", **fields)


def applicant_templates(
    *, codes: tuple[str, ...] = (), search: str | None = None
) -> tuple[dict[str, Any], ...]:
    """The rows the drawn `Choosing a template` picker lists, for given classes.

    Each row is one VARIANT of one class with its live version:
    `template_id · code · name · group · channel · category · language ·
    version · status · pickable · not_pickable_reason · is_writing`.

    ⚠ **A DRAFT IS LISTED AND IS NOT PICKABLE, WHICH IS THE POINT.** p081, read
    as an image: *"The draft version is listed and cannot be picked. Hiding it
    sends a clerk looking for something they can see exists; offering it would
    queue a letter nobody has approved."* So the filtering is NOT done here and
    must not be done by the screen either — the row travels with the reason it
    cannot be chosen.

    An empty tuple means notifications published no answer, which a picker
    renders as *no wording yet* rather than as a broken screen — the honest
    absence `message_templates` and `channel_reachability` already return.
    """
    read = _resolve_service_request(READ_APPLICANT_TEMPLATES)
    if read is None:  # pragma: no cover - notifications ships in this repo
        return ()
    return tuple(read(codes=tuple(codes), search=search))


#: ⊕ `CR-171-BRC10` P1.07 — the two READS behind a request's *Messages* tab
#: (image 22), published by notifications' own selectors module. The source
#: kind is notifications' (`service_request_events.SOURCE_SERVICE_REQUEST`) and
#: is resolved from there too, so the two sides cannot spell it differently.
READ_DELIVERIES_FOR_SOURCES = "deliveries_for_sources"
READ_SOURCE_DELIVERY_ROW = "source_delivery_row"


def request_messages(source_ids: Any) -> tuple[Any, Any] | None:
    """`(queryset, row)` for every letter queued under these source ids, newest
    first — the caller pages the queryset in SQL and serialises the page with
    `row`. `None` when notifications publishes neither, which a caller states
    rather than rendering an empty table as *nothing was sent*."""
    try:
        selectors = import_module(f"apps.{MESSAGE_MODULE}.selectors")
        events = import_module(f"apps.{MESSAGE_MODULE}.{MESSAGE_KIND_SERVICE_REQUEST}")
    except ImportError:  # pragma: no cover - notifications ships in this repo
        return None
    read = getattr(selectors, READ_DELIVERIES_FOR_SOURCES, None)
    row = getattr(selectors, READ_SOURCE_DELIVERY_ROW, None)
    source_type = getattr(events, "SOURCE_SERVICE_REQUEST", None)
    if not callable(read) or not callable(row) or not source_type:
        return None
    return read(source_type, source_ids), row


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
    language: str | None = None,
) -> tuple[dict[str, Any], ...]:
    """The rate-plan change confirmation. Outcome rows only.

    `CR-190-BRC10` — `from_plan_id` / `to_plan_id` / `customer_class` let
    notifications state each plan's main charges (`{old_rate}`/`{new_rate}`);
    the account type CODE is passed because the base charge narrows by it.

    ⚠ **THIS REPLACES A TRIGGER THAT ALREADY EXISTED AND HAD FOUR FAULTS.**
    `services._queue_plan_change_email` has queued a row on every elected plan
    change since W6, and every one of them was wrong in a way nothing reported:

      1 · it pinned the template code `plan_change`, which no row in
          `catalogs.LISTINGS` or `seed_templates.SEEDABLE` declares, so the
          letter rendered from wording that does not exist (DEF-2511 — the same
          fault, in a third module, found by this wave);
      2 · it keyed on the ACCOUNT, so a customer's SECOND rate change deduped
          into their first with `created=False` and nothing anywhere reporting
          a problem (DEF-2512);
      3 · it rode `source_type="plan"` — the PAYMENT-plan kind — so once
          BR-NOT-024 landed on 2026-08-29 the payment-plan print floor started
          putting a rate-plan email on paper;
      4 · it passed no `event_key`, so switching the row off on Settings →
          Notifications did nothing at all, which is CR-048's own headline.

    All four are closed here. `assignment_id` is the `unit_plan_assignments`
    row, which is also what makes this letter inherit `change_plan`'s own TC-5
    idempotency rather than keeping a second opinion about it.

    `language` is the UTILITY's default language (`OQ-CUS-12619`,
    `BR-NOT-006` amended 2026-09-23 — PO: *"(a) Portal only; emails in
    English."*). ⚠ It read *"the ACCOUNT's preferred language"* until that
    ruling, and the caller passed `accounts.preferred_language`; the account's
    language now drives the customer portal alone, and the caller reads the
    utility's through `seams.tenant_default_language`.
    """
    write = _resolve(WRITE_RATE_PLAN_CHANGE)
    if write is None:  # pragma: no cover - defensive
        return _unavailable(WRITE_RATE_PLAN_CHANGE)
    return _guarded(
        write,
        what="rate-plan change confirmation",
        write_name=WRITE_RATE_PLAN_CHANGE,
        assignment_id=assignment_id,
        account_id=account_id,
        effective_on=effective_on,
        plan_name=plan_name,
        from_plan_id=from_plan_id,
        to_plan_id=to_plan_id,
        customer_class=customer_class,
        actor=actor,
        language=language,
        job=None if actor is not None else "customers.change_plan",
    )


# ═══════════════════════════════════════════════════════════════════════════
# `DEF-CUS-5949` — the three things a PROPERTY SALE says, and to WHICH party
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **A THIRD NOTIFICATIONS MODULE, RESOLVED THE SAME WAY, AND IT IS A THIRD
# MODULE RATHER THAN THREE MORE FUNCTIONS IN `customer_events` FOR THE REASON
# THE APPLICANT BLOCK ABOVE GIVES, ONE STEP FURTHER ON: ONE OF THESE THREE
# MESSAGES IS NOT ADDRESSED TO THE ACCOUNT AT ALL.** Everything in
# `customer_events` addresses the person who holds an account. A property sale
# REASSIGNS the account (`BR-CUS-1030`) — the account stays, its CUSTOMER
# changes — so from the instant the commit lands, *the account* means *the
# buyer*, and the letter telling the SELLER they no longer hold it cannot be
# told apart from the buyer's by `account_id`. The seller's row therefore
# carries `account_id` NULL and names its party in `recipient_snapshot`, and
# `apps/notifications/transfer_events.py` holds the whole argument including
# why a `recipient_customer_id` column was weighed and rejected.
#
# ⚠ **THE FAILURE POSTURE IS `_guarded`'s.** The sale has already committed by
# the time any of these is attempted — the module docstring's rule is that *"a
# failed notification must never fail the work it describes"* — and a queue
# refusal that unwound a property sale would be this product telling somebody
# they may not sell their house. The clerk is told on the response instead,
# through the outcome rows.
#
# ⚠ **QUEUED IS NOT SENT AND NOTHING HERE SAYS OTHERWISE.** Measured on the
# beta on 2026-09-20: **373 messages are queued in this product and not one has
# ever been sent** (`sent_at` null on every row; `BR-NOT-013` — no provider
# adapter on email, SMS or print). These three join that number; they do not
# change it.
MESSAGE_KIND_TRANSFER = "transfer_events"
WRITE_TRANSFER_TO_BUYER = "queue_transfer_to_buyer"
WRITE_TRANSFER_TO_SELLER = "queue_transfer_to_seller"
WRITE_TRANSFER_FIELD_VISIT = "queue_transfer_field_visit"
#: That module's own refusal type, resolved SEPARATELY for the reason
#: `SERVICE_REQUEST_REFUSAL` is: catching a move's refusal type on a sale's
#: failure path would report every real problem as `..._error` and lose the
#: sentence a human could have acted on.
TRANSFER_REFUSAL = "TransferMessageRefused"

#: Outcome CODES for the sale's messages. Distinct from the `move_*` and
#: `applicant_*` families so a screen, a log line or a test can tell which kind
#: of message it is reading without parsing prose.
TRANSFER_MESSAGE_QUEUED = "transfer_message_queued"
TRANSFER_MESSAGE_ALREADY_QUEUED = "transfer_message_already_queued"
TRANSFER_MESSAGE_REFUSED = "transfer_message_refused"
TRANSFER_MESSAGE_ERROR = "transfer_message_error"
TRANSFER_MESSAGE_UNAVAILABLE = "transfer_message_unavailable"

TRANSFER_BR_REF = "BR-CUS-1030"


def _resolve_transfer(attribute: str) -> Any:
    """The sale-message module's published callable, or None."""
    try:
        target = import_module(f"apps.{MESSAGE_MODULE}.{MESSAGE_KIND_TRANSFER}")
    except ImportError:  # pragma: no cover - notifications ships in this repo
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


def transfer_entry_points() -> dict[str, Any]:
    """The three entry points, resolved by name — published so a test can
    assert this seam reaches real functions rather than trusting a docstring
    (hard-won law 1). A name that stops resolving here is a sale that silently
    stops telling anybody, which is the exact absence this wave closed."""
    return {
        name: _resolve_transfer(name)
        for name in (
            WRITE_TRANSFER_TO_BUYER,
            WRITE_TRANSFER_TO_SELLER,
            WRITE_TRANSFER_FIELD_VISIT,
        )
    }


def _transfer_outcome(message: Any, *, what: str) -> dict[str, Any]:
    """One row a caller can put on its response and store on its timeline."""
    created = bool(getattr(message, "created", False))
    return {
        "code": TRANSFER_MESSAGE_QUEUED if created else TRANSFER_MESSAGE_ALREADY_QUEUED,
        "br_ref": TRANSFER_BR_REF,
        "message_id": (str(message.message_id) if getattr(message, "message_id", None) else None),
        "template_code": getattr(message, "template_code", None),
        #: ⛔ **WHICH PARTY, CARRIED ON THE OUTCOME ROW ITSELF.** A clerk
        #: reading a sale's result must be able to see that the seller was
        #: written to as well as the buyer, and `account_id` cannot tell them —
        #: that is the whole subject of this block.
        "party": getattr(message, "party", None),
        "channels": tuple(getattr(message, "channels", ()) or ()),
        #: WHERE a real deployment would send it. Proving a row exists and
        #: proving it is addressed to the right person are two claims, and only
        #: the second is worth anything on a sale.
        "address": getattr(message, "address", None),
        # `DEF-NOT-10537`: the false *"no delivery adapter exists on any
        # channel yet"* clause is gone (2026-10-22); the true half stays.
        "detail": (
            f"the {what} is on the outbound queue — the row, its recipient and its "
            "wording are all real."
            if created
            else f"this sale's {what} was already queued, so nothing was written. A "
            "replayed commit says it once (CLAUDE.md rule 6)."
        ),
        "problems": tuple(getattr(message, "problems", ()) or ()),
    }


def _transfer_unavailable(write_name: str, *, what: str) -> dict[str, Any]:
    return {
        "code": TRANSFER_MESSAGE_UNAVAILABLE,
        "br_ref": TRANSFER_BR_REF,
        "message_id": None,
        "template_code": None,
        "party": None,
        "channels": (),
        "address": None,
        "detail": f"apps.{MESSAGE_MODULE}.{MESSAGE_KIND_TRANSFER}.{write_name} is not "
        f"published, so no {what} could be queued. The sale itself completed; this is "
        "reported rather than swallowed.",
        "problems": (),
    }


def _guarded_transfer(write: Any, *, what: str, **kwargs: Any) -> dict[str, Any]:
    """One call, inside its OWN savepoint. Raises nothing, ever.

    ⚠ **THE SAVEPOINT IS THE POINT AND IT IS NOT TIDINESS** (hard-won law 14).
    On PostgreSQL a statement that errors inside a transaction ABORTS the whole
    transaction: a plain `try` catches the exception, the sale that already
    committed is doomed, and the COMMIT fails afterwards with *"current
    transaction is aborted"*. SQLite has no such state, so the version without
    this passes the entire suite and loses a property sale the first time the
    queue refuses a row in production. Do not "simplify" it away.
    """
    try:
        with transaction.atomic():
            message = write(**kwargs)
    except Exception as failure:  # noqa: BLE001 — the one boundary where broad is right
        refusal = _resolve_transfer(TRANSFER_REFUSAL)
        refused = refusal is not None and isinstance(failure, refusal)
        return {
            "code": TRANSFER_MESSAGE_REFUSED if refused else TRANSFER_MESSAGE_ERROR,
            "br_ref": TRANSFER_BR_REF,
            "message_id": None,
            "template_code": None,
            "party": None,
            "channels": (),
            "address": None,
            "detail": f"the {what} could not be queued: {failure} The sale stands — a "
            "failed notification must never fail the work it describes.",
            "problems": (),
        }
    return _transfer_outcome(message, what=what)


def queue_transfer_to_buyer(**fields: Any) -> dict[str, Any]:
    """*The account is yours from today* — the buyer's half of the commit.

    `account_id` IS passed: after the commit the account belongs to the buyer,
    so the column says something true and the account timeline finds the row.
    """
    write = _resolve_transfer(WRITE_TRANSFER_TO_BUYER)
    if write is None:  # pragma: no cover - notifications ships in this repo
        return _transfer_unavailable(WRITE_TRANSFER_TO_BUYER, what="buyer's letter")
    return _guarded_transfer(write, what="buyer's letter", **fields)


def queue_transfer_to_seller(**fields: Any) -> dict[str, Any]:
    """*The account is no longer yours* — the seller's half of the commit.

    ⚠ **THE CALLER MUST READ THE SELLER'S ADDRESS BEFORE IT CARRIES THE
    BUYER'S DETAILS ONTO THE ACCOUNT.** `contacts` is keyed to the ACCOUNT and
    `BR-CUS-1081` has the sale write the buyer's email onto exactly that row,
    so a caller that read it afterwards would address the seller's letter to
    the buyer — the same confusion this block exists to prevent, arriving
    through the back door.
    """
    write = _resolve_transfer(WRITE_TRANSFER_TO_SELLER)
    if write is None:  # pragma: no cover - notifications ships in this repo
        return _transfer_unavailable(WRITE_TRANSFER_TO_SELLER, what="seller's letter")
    return _guarded_transfer(write, what="seller's letter", **fields)


def queue_transfer_field_visit(**fields: Any) -> dict[str, Any]:
    """*Somebody is coming to read the meter* — the third drawn message, by SMS.

    To the BUYER: they are the one who has to let a technician in. It carries
    no appointment window, because the work order is raised AFTER the commit
    and is allowed to fail, so nothing here knows when anybody is coming.
    """
    write = _resolve_transfer(WRITE_TRANSFER_FIELD_VISIT)
    if write is None:  # pragma: no cover - notifications ships in this repo
        return _transfer_unavailable(WRITE_TRANSFER_FIELD_VISIT, what="meter-visit text")
    return _guarded_transfer(write, what="meter-visit text", **fields)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-048 wave B task B10 (12-governance/11-change-requests.md → CR-048 · apps/notifications/customer_events.py (the two entry points) · apps/notifications/rule_catalog.py EVENTS `move_in_welcome` + `move_out_final_bill` · apps/customers/services.py move_in / move_out · apps/customers/moves.py record_move (the id this message is keyed on) · CLAUDE.md hard-won law 14 · apps/payments/run_alert_seam.py (the seam shape this follows))
# generated: 2026-08-30 by story-coder (CR-048 wave B tasks B6 + B10 lane)
# checklist: A✔ B=deferred(no frontend half — S19/S20 render their own result; `move_message` rides both wizard responses for a lane that draws it) C✔ D=deferred(no HTTP surface of its own — reached through the existing move-in / move-out endpoints) E=deferred(as B) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_cr048_b6_b10.py under PostgreSQL — RED PROVED FIRST: a completed move-in queued ZERO messages before this file existed; the savepoint was proved by removing it and driving a real `SELECT 1/0` through the seam, which took the whole move-in with it at COMMIT on PostgreSQL and passed on SQLite. Both transcripts in the lane report.
# exceptions: (1) NOTHING SENDS — every message is a `queue_document` write (BR-NOT-005); there is no provider call in this module. (2) NO FINAL-BILL FIGURES ARE PASSED, because a move-out issues no invoice and this flow holds no reading value; the tokens render as named absences. (3) THE SAVEPOINT IS LOAD-BEARING (hard-won law 14) — a `try` alone loses the whole move on PostgreSQL and passes on SQLite. (4) THE EVENT KEYS ARE NOT SPELLED HERE: the named entry points own them, so a mistyped key cannot refuse at the end of a committed move.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
