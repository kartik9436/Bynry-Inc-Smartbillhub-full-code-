# ── Trace ──────────────────────────────────────────────
# Change:   CR-171-BRC10 (move-in redesign) · lane MVI-FLOW · P1.20 · P1.21
# Rules:    images 45, 46 (the Messaging table: two defaults that cannot be
#           removed, extra rows to customer / co-owner / unit owner by email,
#           text, letter, portal, at four moments) · image 48 (*What happened*)
#           · BR-NOT-013 (a queued message is never called sent) · CLAUDE.md
#           hard rules 6 (the queue is keyed on the extra-message row) · 7
# Defects:  DEF-CUS-9702 (two stale absences served on every move-in)
# Tests:    06-backend/tests/test_cr171_p1_20_21_complete.py
# ───────────────────────────────────────────────────────
"""What Complete does with the *Messaging* table, and what it says it did.

════════════════════════════════════════════════════════════════════════════
P1.20 · THE EXTRA MESSAGES
════════════════════════════════════════════════════════════════════════════
`extra_messages` on the move-in payload is the table's ADDED rows:
`[{template_key, recipient, co_owner_name?, channel, send_when}]`. The two
defaults (`move_in_welcome`, `service_agreement`) are NOT rows; a payload
naming one as an extra is refused. Each has its writer, called by
`services._move_in` after the account is written: `queue_move_in_welcome` and,
since `DEF-CUS-9743` (2026-10-05), `queue_move_in_service_agreement` — on paper,
held at dispatch while the utility has published no contract version.

* Validated by `pop` BEFORE the transaction — a bad row writes nothing.
* Written as `move_extra_messages` rows inside Complete's transaction, after
  the co-owners (P1.10) so a `co_owner` row can name its person.
* Queued AFTER the commit, and only what can honestly be queued today:
  **`on_complete` to the `customer`** — through notifications' own account
  message door, with the template's published wording, keyed on the ROW's id
  (idempotent, rule 6). Every other row stays PLANNED with
  `notification_id = NULL` and the answer says why per row (`not_queued`
  reasons below) — a scheduled send needs a scheduler and a co-owner / unit
  owner needs an address book entry, and neither is notifications' today. A
  row is never reported *sent* (BR-NOT-013).

════════════════════════════════════════════════════════════════════════════
P1.21 · WHAT HAPPENED (image 48)
════════════════════════════════════════════════════════════════════════════
`what_happened(result)` composes the ticked list from what Complete RETURNED —
it reads no table and asserts nothing the commit did not report: customer
created or linked, account, services and date, opening reads, unit Vacant →
Occupied, co-owners, documents, work orders, fees, payment, messages, and the
`MVI-` / `SR-` numbers. A section the commit did not report is absent, never
rendered as zero.

`DEF-CUS-9702` — two sentences on the completed screen were false. ONE is a
false FACT and stops being served on a move-in: `plan_snapshot_not_recorded`
(BR-CUS-029 was superseded 2026-08-11 — the plan lives on the unit by design,
so *"this account is not tied to a plan version"* is untrue). The OTHER,
`deposit_carry_forward_unavailable`, is a true fact with a false REASON:
nothing carries a deposit at move-in yet (a returning tenant's $153.50 is still
not moved — `test_w5_move_in_out_cases` TC-MVI-2), but *"with no customer
record"* stopped being why on 2026-08-11. So the code stays and its sentence is
cut to the fact (B14 rule 33: rationale is zero words on screen).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from core import errors

from apps.customers import models, notifications_seam
from apps.customers.move_in_extras import (
    CHANNELS,
    RECIPIENT_CO_OWNER,
    RECIPIENT_CUSTOMER,
    RECIPIENTS,
    SEND_WHEN,
    MoveExtraMessage,
)

FIELD = "extra_messages"
DEFAULT_TEMPLATES: tuple[str, ...] = ("move_in_welcome", "service_agreement")

#: Why a planned row was not queued at Complete. Codes; the words are the
#: screen's.
NOT_QUEUED_SCHEDULED = "scheduled_send_not_queued_at_complete"
NOT_QUEUED_RECIPIENT = "recipient_has_no_message_door"
NOT_QUEUED_TEMPLATE = "template_wording_not_published"
NOT_QUEUED_REFUSED = "notifications_refused"

#: `DEF-CUS-9702` — see the module docstring.
STALE_ALWAYS = ("plan_snapshot_not_recorded",)

#: The table's channel → the account door's (`communication_api.OFFERED_CHANNELS`):
#: *text* is `sms`, *letter* is `pdf_print`.
_DOOR_CHANNEL = {"email": "email", "text": "sms", "letter": "pdf_print", "portal": "portal"}


def _bad(index: int, field: str, key: str) -> errors.ValidationError:
    return errors.ValidationError(
        errors.VAL_FORMAT,
        message_key=key,
        field_errors=[
            {
                "field": f"{FIELD}[{index}].{field}",
                "code": errors.VAL_FORMAT,
                "message_key": key,
            }
        ],
        params={"row": index},
    )


def pop(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Take `extra_messages` off the payload and validate every row. Absent or
    empty is no extra message, which is the ordinary case."""
    raw = data.pop(FIELD, None)
    if raw in (None, []):
        return []
    if not isinstance(raw, list):
        raise _bad(0, "rows", "customers.moveIn.messages.notAList")
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        row = item if isinstance(item, dict) else {}
        template = str(row.get("template_key") or "").strip()
        if not template:
            raise _bad(index, "template_key", "customers.moveIn.messages.templateRequired")
        if template in DEFAULT_TEMPLATES:
            raise _bad(index, "template_key", "customers.moveIn.messages.defaultTwice")
        recipient = str(row.get("recipient") or RECIPIENT_CUSTOMER)
        if recipient not in RECIPIENTS:
            raise _bad(index, "recipient", "customers.moveIn.messages.recipientUnknown")
        co_owner_name = str(row.get("co_owner_name") or "").strip() or None
        if recipient == RECIPIENT_CO_OWNER and not co_owner_name:
            raise _bad(index, "co_owner_name", "customers.moveIn.messages.coOwnerRequired")
        channel = str(row.get("channel") or "")
        if channel not in CHANNELS:
            raise _bad(index, "channel", "customers.moveIn.messages.channelUnknown")
        when = str(row.get("send_when") or "on_complete")
        if when not in SEND_WHEN:
            raise _bad(index, "send_when", "customers.moveIn.messages.whenUnknown")
        rows.append(
            {
                "template_key": template,
                "recipient": recipient,
                "co_owner_name": co_owner_name if recipient == RECIPIENT_CO_OWNER else None,
                "channel": channel,
                "send_when": when,
            }
        )
    return rows


# ════════════════════════════════════════════════════════════════════════════
# CR-190-BRC10 · THE TWO DEFAULTS, PER MOVE-IN — untick, or another channel
# ════════════════════════════════════════════════════════════════════════════
#: PO 2026-10-22, verbatim: *"A: allow untick and channel change per move-in"*.
#: `default_messages` on the payload is `[{key, send, channel?}]` for the two
#: defaults a move-in itself writes. Settings still supply the defaults; a key
#: the clerk did not send keeps its Settings answer.
DEFAULTS_FIELD = "default_messages"
#: The audit action for a default the clerk switched off for this move-in.
AUDIT_DEFAULT_CHANGED = "move_in.default_message_changed"
#: The outcome code a default the clerk unticked carries on Complete's answer.
UNTICKED = "move_message_unticked_by_clerk"


def _bad_default(index: int, field: str, key: str) -> errors.ValidationError:
    return errors.ValidationError(
        errors.VAL_FORMAT,
        message_key=key,
        field_errors=[
            {
                "field": f"{DEFAULTS_FIELD}[{index}].{field}",
                "code": errors.VAL_FORMAT,
                "message_key": key,
            }
        ],
        params={"row": index},
    )


def pop_defaults(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Take `default_messages` off the payload and validate it SERVER-SIDE.

    Returns `{key: {"send": bool, "channel": str | None}}`. Refused by name: a
    key that is not one of the two defaults (`defaultUnknown`), a key twice
    (`defaultTwice`), and a channel the template class does not allow for that
    default (`channelNotAllowed`) — the allowed set is notifications' own
    derivation, never this module's list, so a screen cannot send a channel the
    class has no form for. Absent or empty is *the Settings answer*.
    """
    raw = data.pop(DEFAULTS_FIELD, None)
    if raw in (None, []):
        return {}
    if not isinstance(raw, list):
        raise _bad_default(0, "rows", "customers.moveIn.messages.notAList")
    choices: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(raw):
        row = item if isinstance(item, dict) else {}
        key = str(row.get("key") or "").strip()
        if key not in DEFAULT_TEMPLATES:
            raise _bad_default(index, "key", "customers.moveIn.messages.defaultUnknown")
        if key in choices:
            raise _bad_default(index, "key", "customers.moveIn.messages.defaultTwice")
        send = row.get("send", True)
        if not isinstance(send, bool):
            raise _bad_default(index, "send", "customers.moveIn.messages.sendNotABoolean")
        channel = row.get("channel")
        channel = str(channel).strip() if channel not in (None, "") else None
        if channel is not None and channel not in notifications_seam.move_in_default_channels(key):
            raise _bad_default(index, "channel", "customers.moveIn.messages.channelNotAllowed")
        choices[key] = {"send": send, "channel": channel}
    return choices


def default_outcome(key: str, choice: dict[str, Any] | None) -> tuple[bool, tuple[str, ...] | None]:
    """`(send, channels)` for one default — `(True, None)` is the Settings answer."""
    if not choice:
        return True, None
    channel = choice.get("channel")
    return bool(choice.get("send", True)), ((channel,) if channel else None)


def audit_default_choices(
    actor: Any, *, account_id: Any, move_record_id: Any, choices: dict[str, dict[str, Any]]
) -> None:
    """Hard rule 7's shape for a clerk's per-move-in change: WHAT was unticked or
    re-channelled, by whom, on which move-in. One row, only when something
    changed; no customer data (BR-AUD-006)."""
    if not choices:
        return
    from core import audit

    audit.money_action(
        actor,
        AUDIT_DEFAULT_CHANGED,
        "move_record",
        str(move_record_id),
        before=None,
        after={
            "account_id": str(account_id),
            "unticked": sorted(key for key, one in choices.items() if not one.get("send", True)),
            "channels": {
                key: one["channel"]
                for key, one in sorted(choices.items())
                if one.get("send", True) and one.get("channel")
            },
        },
    )


def template_choices(*, search: str | None = None) -> dict[str, Any]:
    """`GET /move-ins/message-templates` — what *+ Add message* may pick (P2.33,
    image 46). READS ONLY.

    The rows are `notifications_seam.message_templates()` — the SAME call
    `queue` reads the wording through at Complete — minus the two defaults,
    which `pop` refuses as an extra row (`defaultTwice`). The code is the value
    a row sends; the name a person gave it is what the screen shows (B14 rule
    31). `served` is false when notifications published no answer at all, so
    the screen can say so instead of offering an empty list as *nothing to
    pick*.
    """
    published = notifications_seam.message_templates()
    typed = (search or "").strip().lower()
    results = [
        {"code": str(row.get("code")), "name": str(row.get("name") or row.get("code"))}
        for row in published
        if row.get("code") and row.get("code") not in DEFAULT_TEMPLATES
    ]
    if typed:
        results = [row for row in results if typed in row["name"].lower()]
    return {"served": len(published) > 0, "results": results}


def write(*, move_record_id: Any, account_id: Any, rows: list[dict[str, Any]]) -> list[MoveExtraMessage]:
    """Inside Complete's transaction, after the co-owners are written."""
    from apps.customers.co_owner_models import AccountCoOwner

    record_tenant = models.Account.objects.only("tenant_id").get(pk=account_id).tenant_id
    written: list[MoveExtraMessage] = []
    for seq, row in enumerate(rows, start=1):
        co_owner = None
        if row["recipient"] == RECIPIENT_CO_OWNER:
            co_owner = (
                AccountCoOwner.objects.filter(account_id=account_id, full_name__iexact=row["co_owner_name"])
                .order_by("created_at")
                .first()
            )
            if co_owner is None:
                raise _bad(seq - 1, "co_owner_name", "customers.moveIn.messages.coOwnerUnknown")
        written.append(
            MoveExtraMessage.objects.create(
                tenant_id=record_tenant,
                move_record_id=move_record_id,
                seq=seq,
                template_key=row["template_key"],
                recipient=row["recipient"],
                co_owner=co_owner,
                channel=row["channel"],
                send_when=row["send_when"],
            )
        )
    return written


def _wording(template_key: str) -> dict[str, Any] | None:
    for row in notifications_seam.message_templates():
        if row.get("code") == template_key:
            return row
    return None


def queue(actor: Any, *, account_id: Any, on_date: date, written: list[MoveExtraMessage]) -> list[dict[str, Any]]:
    """AFTER the commit. One outcome row per extra message, in table order."""
    signed_by = (
        (getattr(getattr(actor, "user", None), "full_name", "") or "").strip()
        or (getattr(actor, "full_name", "") or "").strip()
        or "—"
    )
    out: list[dict[str, Any]] = []
    for row in written:
        outcome: dict[str, Any] = {
            "seq": row.seq,
            "template_key": row.template_key,
            "recipient": row.recipient,
            "channel": row.channel,
            "send_when": row.send_when,
            "state": "planned",
            "not_queued": None,
        }
        door = _DOOR_CHANNEL.get(row.channel)
        if row.send_when != "on_complete":
            outcome["not_queued"] = NOT_QUEUED_SCHEDULED
        elif row.recipient != RECIPIENT_CUSTOMER or door is None:
            outcome["not_queued"] = NOT_QUEUED_RECIPIENT
        else:
            wording = _wording(row.template_key)
            if wording is None or not str(wording.get("body") or "").strip():
                outcome["not_queued"] = NOT_QUEUED_TEMPLATE
            else:
                answer = notifications_seam.queue_account_message(
                    message_id=row.id,
                    account_id=account_id,
                    channels=(door,),
                    subject=str(wording.get("subject") or wording.get("name") or ""),
                    body=str(wording.get("body")),
                    signed_by=signed_by,
                    on_date=on_date,
                    kind="courtesy",
                    actor=actor,
                )
                if answer.get("refused"):
                    outcome["not_queued"] = NOT_QUEUED_REFUSED
                else:
                    outcome["state"] = "queued"  # never "sent" (BR-NOT-013)
                    # The outbound rows are keyed on this id as their SOURCE
                    # (rule 6); it is what `notification_id` points at.
                    message_id = answer.get("message_id")
                    if message_id:
                        MoveExtraMessage.objects.filter(pk=row.pk).update(notification_id=message_id)
        out.append(outcome)
    return out


def drop_stale_absences(warnings: list[dict[str, Any]], *, customer_outcome: Any) -> None:
    """`DEF-CUS-9702` — in place, like the `customer_not_linked` filter beside
    the call."""

    del customer_outcome  # kept in the signature for the call site's symmetry
    stale = set(STALE_ALWAYS)
    warnings[:] = [w for w in warnings if w.get("code") not in stale]


def what_happened(result: dict[str, Any]) -> dict[str, Any]:
    """Image 48 — the ticked list, from what the commit RETURNED."""
    items: list[dict[str, Any]] = []

    def add(key: str, **facts: Any) -> None:
        items.append({"key": key, **facts})

    outcome = result.get("customer_outcome")
    if outcome:
        add("customer", outcome=outcome, customer_no=result.get("customer_no"))
    add(
        "account",
        account_no=result.get("account_no"),
        status=result.get("status"),
        opened_at=result.get("opened_at"),
    )
    agreements = result.get("service_agreements") or result.get("agreements")
    if agreements is not None:
        add("services", count=len(agreements), starts_on=result.get("opened_at"))
    reads = result.get("event_reads")
    if reads is not None:
        add("opening_reads", posted=int(reads.get("posted_reads") or 0))
    # `DEF-CUS-9730` — ALWAYS vacant before: a move-in only takes a vacant unit
    # (BR-CUS-020; BR-CUS-017 refuses one an account still holds). Following a
    # finished tenancy does not make the unit occupied — that tenancy has ended.
    add("unit", now="occupied", was="vacant")
    people = result.get("people")
    if people:
        add("co_owners", count=int(people.get("co_owners") or 0))
        add("documents", count=int(people.get("documents_carried") or 0))
    orders = result.get("work_orders")
    if orders is not None:
        add(
            "work_orders",
            count=len(orders),
            declined=bool(result.get("field_visit_declined")),
            orders=[
                {"order_no": o.get("order_no"), "assignee": o.get("assignee") or o.get("holder")}
                for o in orders
            ],
        )
    for key in ("fees", "payment", "deposit"):
        if result.get(key) is not None:
            add(key, detail=result.get(key))
    # `DEF-CUS-9759` — the welcome's outcome rows carry a `code`, never a
    # `state`; an extra row carries a `state`. Both are counted, a suppressed
    # welcome is not. `DEF-CUS-9757` — one welcome is one queued row PER
    # CHANNEL (email + printed letter), so it counts its channels (1 when the
    # outcome names none). `DEF-CUS-9743` — the service agreement's outcome
    # rows have the same shape and are counted the same way.
    welcome_queued = sum(
        len(m.get("channels") or ()) or 1
        for m in [*(result.get("move_message") or []), *(result.get("service_agreement_message") or [])]
        if m.get("code")
        in (notifications_seam.MOVE_MESSAGE_QUEUED, notifications_seam.MOVE_MESSAGE_ALREADY_QUEUED)
    )
    add(
        "messages",
        queued=welcome_queued
        + sum(1 for m in (result.get("extra_messages") or []) if m.get("state") == "queued"),
        planned=sum(1 for m in (result.get("extra_messages") or []) if m.get("state") == "planned"),
    )
    return {
        "move_no": result.get("move_no"),
        "request_no": result.get("request_no"),
        "items": items,
    }

