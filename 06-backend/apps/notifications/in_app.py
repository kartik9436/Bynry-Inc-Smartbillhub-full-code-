# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-018 (CR-009 — the in-app channel: the PLATFORM's own delivery
#           adapter behind the one provider seam, and the inbox it fills)
#           Screens: shell-chrome (the bell + its popover inbox) · S8
# Rules:    BR-NOT-019 (in-app is a real delivery channel and the PLATFORM is its
#           provider — no integration, no credentials, no vendor) ·
#           BR-NOT-005 (queue only: nothing here is reachable from a request that
#           wants to SEND; delivery happens when the dispatcher drains the queue)
#           · BR-TEN-017 (the delivered artifact is a snapshot — a mailbox row is
#           never re-rendered) · CLAUDE.md rule 1 (tenant scoping) · rule 6
#           (idempotency: one delivery per message per inbox)
# Tests:    06-backend/tests/test_cr_009_in_app_channel.py ·
#           06-backend/tests/test_cr_009_in_app_isolation.py
# Impacts:  apps/notifications/provider_seam.py (resolves this module as the
#           adapter for `in_app`, the same way it resolves integrations for the
#           other three) · apps/notifications/dispatcher.py (hands it the batch)
# ───────────────────────────────────────────────────────
"""notifications → IN-APP delivery: the one channel that needs nobody.

╔══════════════════════════════════════════════════════════════════════════╗
║  THIS IS A PROVIDER ADAPTER. IT IS NOT A SECOND SEND PATH.               ║
╚══════════════════════════════════════════════════════════════════════════╝

BR-NOT-005 says every message from every module is written to the outbound queue
first and *"never sent inline"*, and A11 Addendum r2 §4 makes a synchronous send
endpoint a gate failure. Nothing in this file is reachable from an HTTP route
that wants to deliver something. `deliver_batch` has exactly one caller —
`provider_seam.dispatch_batch`, invoked by the dispatcher after it has claimed a
batch, rendered it and stamped a batch id — which is the same door a real ESP
would come through. If email is ever plugged in, the only difference between it
and this module is which side of the boundary the code runs on.

WHY THAT MATTERS MORE THAN IT SOUNDS. The PO's ruling of 2026-08-17 is that a
message arriving in an in-app inbox is *"proof that notification is working"*.
It is only proof if the message travelled the REAL path. An in-app notification
written directly by the caller that raised the event would prove that a row can
be inserted into a table, which nobody doubted.

────────────────────────────────────────────────────────────────────────────
WHAT "DELIVERY" MEANS HERE, AND WHY THIS CHANNEL IS `dispatchable: True`
────────────────────────────────────────────────────────────────────────────
`provider_seam` documents three states a channel can be in — DEFERRED (the
platform has not built it), NO PROVIDER (the tenant has not connected one), and
READY. Print, email and SMS are all stuck at one of the first two and BR-NOT-013
records why: *"no provider adapter exists or is coming on ANY channel, print
included"*.

In-app is READY, and it is the first channel that ever has been, because the
three things the other channels are waiting for do not apply to it:

  * **No vendor decision.** There is no SMTP-vs-ESP fork, no Twilio contract, no
    print fulfilment house. The recipient's mailbox is `in_app_messages`.
  * **No per-tenant configuration.** Nothing to connect on Settings →
    Integrations, no credentials to hold, no SPF/DKIM, no sender identity. A
    tenant provisioned five minutes ago can receive one.
  * **No cost and no outside party.** Which is exactly why the PO chose it as
    the proof: it isolates the pipeline from the one unknown.

So `deliver_batch` returns `{"status": "sent"}` per message and the queue row
reaches `sent` — a status this platform has never been able to write before. It
does NOT return `delivered`: BR-NOT-013 is unchanged and `delivered` remains a
provider CONFIRMATION nothing in this repo can produce. The honest reading is
that the platform accepted the message into the recipient's inbox, which is
`sent`. Whether a person has actually looked at it is `read_at` on the mailbox
row, and that is a different fact recorded in a different column.

────────────────────────────────────────────────────────────────────────────
THE ADDRESS OF AN IN-APP MESSAGE IS A USER ID
────────────────────────────────────────────────────────────────────────────
Every other channel's `recipient_address` is an email address, an E.164 number
or a postal address. This one's is the recipient's `identity.users.id`, as text.
That keeps the queue row's own CHECK constraint meaningful — a row either
carries the address it will be delivered to or states why it has none — without
adding a column that three of the four channels would leave NULL.

`recipient_snapshot` carries the human-readable half (`display_name`, `email`)
so a delivery record a year from now can still say who it went to when the user
has been renamed or removed. BR-TEN-017: the recipient is snapshotted at queue
time and never re-resolved.

────────────────────────────────────────────────────────────────────────────
WHOSE INBOX A READ CAN TOUCH — THE SECOND ISOLATION, AND IT IS IN CODE
────────────────────────────────────────────────────────────────────────────
RLS scopes these rows to a TENANT (migration 0012). It does not and cannot scope
them to a USER, so that guarantee lives here instead: **not one function in this
module accepts a user id from a caller.** `inbox`, `unread_count`, `mark_read`
and `mark_all_read` each take the ACTOR and derive the user from them, so there
is no shape of API request that can ask for somebody else's mail. `mark_read`
filters on `user_id` in the same query that finds the row, so a guessed message
id from another clerk's inbox matches nothing rather than being found and then
checked.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.notifications import models
from core import errors
from core import tenancy as core_tenancy

#: What the bell asks for. The popover is a glance, not an archive — the inbox
#: read is capped so a clerk with two years of run summaries still gets a
#: response, and the cap is stated on the wire so the screen can say "showing
#: the latest 20" rather than implying that is all there is.
INBOX_PAGE_SIZE = 20

#: Hard rule 7 · the dotted `entity.action` grammar `core.audit` documents.
#: ⚠ NOT WRITTEN BY THIS MODULE, and the absence is deliberate rather than
#: forgotten: reading your own notification is not a money action and not a
#: change to tenant data. The DELIVERY is audited where every other delivery is
#: — `dispatcher._audit_batch`, one row per batch — and the queue row is the
#: permanent record of what was sent. An audit row per bell-open would bury the
#: money actions hard rule 7 exists to protect.
AUDIT_NOTE = "in-app reads are not audited; the delivery is (dispatcher batch audit)"


class InboxRefused(Exception):
    """This inbox operation cannot be performed, and here is why — in a clerk's
    words. Not a `core.errors` catalog exception: `deliver_batch` runs inside a
    dispatch cycle over a whole batch, where the right handling is to record the
    break against the one message and carry on, exactly as
    `services.QueueWriteRefused` reasons."""


def _tenant_id() -> Any:
    """Hard rule 1: no tenant table is touched without `app.tenant_id` set.

    Refuse loudly rather than run an unscoped query and leave RLS as the only
    thing between one utility's inbox and another's. Same guard, same error, as
    `apps/notifications/services.py` and `dispatch_config.py`.
    """
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def user_id_of(actor: Any) -> Any:
    """The signed-in user's id, from either actor shape this codebase uses.

    The actor arrives as the raw session user or as the B12 §6a
    `SimpleNamespace(id, role, user)` the API layer builds. `rule_service.
    _test_recipient` records the same hazard and the same fix: reading `.id` off
    the namespace would return the MEMBERSHIP's id on one path and the USER's on
    the other, and a mailbox keyed on the wrong one of those is an inbox that is
    silently always empty.
    """
    user = getattr(actor, "user", None) or actor
    found = getattr(user, "id", None)
    if found is None:
        raise InboxRefused(
            "there is no signed-in user on this request, so there is no inbox to read. "
            "An in-app message belongs to a person; it is not tenant-wide mail."
        )
    return found


def address_for(actor: Any) -> str:
    """The in-app ADDRESS of a user — their id as text.

    Published so the queue writers (`rule_service.queue_test`,
    `bulk_summary.queue_bulk_summary`) and this adapter spell the address the
    same way. Two spellings of an address is how a message gets queued to an
    inbox that is never read.
    """
    return str(user_id_of(actor))


# ── The adapter — the ONLY thing the dispatcher calls ──────────────────────


def deliver_batch(channel: str, messages: tuple[dict[str, Any], ...]) -> dict[str, dict[str, Any]]:
    """Deliver ONE batch into recipients' inboxes. The provider-seam contract.

    Signature is `provider_seam`'s published adapter contract, verbatim:
    `(channel, messages) -> {message_id: answer}`, one call per hand-off and
    never one per message. It is matched exactly so that this module is
    substitutable with `apps.integrations.services.dispatch_outbound_batch` — if
    the two contracts drifted, the in-app channel would be proving a pipeline
    that no other channel will ever travel.

    Each `messages` entry is `{"id", "channel", "address", "snapshot",
    "artifact"}`. `address` is the recipient's user id (see the module
    docstring). An entry this adapter cannot deliver gets a `failed` answer with
    `retryable: False` — a message addressed to nobody will not become
    deliverable by waiting, and burning three retry attempts on it would hide it
    behind a counter instead of putting it on the dispatch home.
    """
    if channel != models.CHANNEL_IN_APP:
        raise InboxRefused(
            f"the in-app adapter was handed a {channel!r} batch. It delivers exactly one "
            f"channel ({models.CHANNEL_IN_APP}); the other three go to "
            "apps.integrations.services.dispatch_outbound_batch, and a platform module "
            "quietly answering for a provider channel would report messages as sent that "
            "nobody sent."
        )

    tenant_id = _tenant_id()
    answers: dict[str, dict[str, Any]] = {}
    now = timezone.now()

    for message in messages:
        message_id = str(message.get("id"))
        address = message.get("address")
        artifact = message.get("artifact") or {}
        body = artifact.get("body")

        if not address:
            answers[message_id] = {
                "status": models.STATUS_FAILED,
                "error": (
                    "this in-app message carries no recipient — an in-app address is the "
                    "signed-in user's id and this row has none. Not retryable: it will "
                    "not acquire a recipient by waiting."
                ),
                "retryable": False,
                "response": {"adapter": "platform.in_app", "reason": "no_recipient_user"},
            }
            continue
        if not body:
            answers[message_id] = {
                "status": models.STATUS_FAILED,
                "error": (
                    "this in-app message rendered to an empty body. Delivering it would "
                    "put a blank line in a clerk's inbox that they cannot act on or "
                    "explain. Not retryable: the template is what must change."
                ),
                "retryable": False,
                "response": {"adapter": "platform.in_app", "reason": "empty_body"},
            }
            continue

        # ── BR-NOT-021 (OQ-261 CLOSED 2026-08-17): ONE message, MANY mailboxes.
        # The snapshot's `recipients` list is the ruled audience, snapshotted at
        # queue time (`staff_recipients.py`); a row queued before the ruling —
        # or by a writer that addresses exactly one person, like `queue_test` —
        # carries no list and delivers to its own `address`, unchanged.
        snapshot = message.get("snapshot") or {}
        listed = snapshot.get("recipients") if isinstance(snapshot, dict) else None
        mailbox_user_ids: list[str] = []
        if isinstance(listed, (list, tuple)) and listed:
            for entry in listed:
                user_id = str((entry or {}).get("user_id") or "")
                if user_id and user_id not in mailbox_user_ids:
                    mailbox_user_ids.append(user_id)
        if str(address) not in mailbox_user_ids:
            # The queue row's own address is ALWAYS a mailbox — a snapshot that
            # somehow dropped it must not un-address the primary recipient.
            mailbox_user_ids.insert(0, str(address))

        delivered_ids: list[str | None] = []
        duplicates = 0
        for user_id in mailbox_user_ids:
            try:
                with transaction.atomic():
                    row = models.InAppMessage.objects.create(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        outbound_message_id=message_id,
                        subject=artifact.get("subject") or None,
                        body=body,
                    )
                delivered_ids.append(str(row.pk))
            except IntegrityError:
                # Hard rule 6 at the delivery end. `uq_in_app_msgs_message_user`
                # refused a SECOND copy of this message into this inbox, which is
                # the correct outcome of a re-run over a row that was claimed and
                # not marked. It is reported as `sent`, not as a failure: the
                # message IS in the recipient's inbox, which is what the queue
                # row was asking for. Answering `failed` here would retry forever
                # against a constraint that will refuse it every time.
                existing = models.InAppMessage.objects.filter(
                    tenant_id=tenant_id, outbound_message_id=message_id, user_id=user_id
                ).first()
                delivered_ids.append(str(existing.pk) if existing is not None else None)
                duplicates += 1

        answers[message_id] = {
            "status": models.STATUS_SENT,
            "provider_reference": delivered_ids[0],
            "response": {
                "adapter": "platform.in_app",
                "delivered_at": now.isoformat(),
                "in_app_message_id": delivered_ids[0],
                # BR-NOT-021 — every mailbox this one message landed in, so the
                # dispatch home can show "1 message · 3 inboxes" as a fact.
                "in_app_message_ids": delivered_ids,
                "mailboxes": len(mailbox_user_ids),
                # Reported rather than hidden: a dispatch that re-delivered
                # nothing is a fact the dispatch home should be able to show.
                "already_delivered": duplicates == len(mailbox_user_ids),
            },
        }

    return answers


# ── The inbox — the reads and the two writes a recipient may make ──────────


@dataclass(frozen=True)
class InboxItem:
    """One message as the bell renders it."""

    id: str
    subject: str | None
    body: str
    read: bool
    created_at: Any
    #: The queue row it was delivered from, so a support question ("did this
    #: actually go out?") can be answered from the dispatch home without a join
    #: the screen has to know how to make.
    outbound_message_id: str
    #: CR-168-BRC10 §F (FIELD-2) — a PRODUCT event (a field job closed) carries
    #: a catalogue key and its params so the bell says it in the clerk's own
    #: language; the stored `body` (the utility's template) is the fallback.
    #: Derived from the queue row's frozen `render_context`, never stored twice.
    message_key: str | None = None
    params: dict[str, Any] | None = None

    def as_wire(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "subject": self.subject,
            "body": self.body,
            "read": self.read,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "outbound_message_id": self.outbound_message_id,
            "message_key": self.message_key,
            "params": self.params or {},
        }


def _bell_key(row: Any) -> tuple[str | None, dict[str, Any] | None]:
    """The catalogue key for a mailbox row whose message is a product event."""
    outbound = getattr(row, "outbound_message", None)
    if outbound is None or outbound.source_type != "field_work":
        return None, None
    from apps.notifications import field_work_events

    return field_work_events.bell_key_for(outbound.render_context)


def _mine(actor: Any):
    """This user's mailbox, in this tenant. The ONE queryset every read starts
    from — see the module docstring's second-isolation note."""
    return models.InAppMessage.objects.filter(tenant_id=_tenant_id(), user_id=user_id_of(actor))


def unread_count(*, actor: Any) -> int:
    """How many unread messages the signed-in user has. The bell's badge."""
    return _mine(actor).filter(read_at__isnull=True).count()


def inbox(*, actor: Any, limit: int = INBOX_PAGE_SIZE) -> tuple[InboxItem, ...]:
    """The signed-in user's messages, newest first (BR-SHL-007's order)."""
    rows = _mine(actor).select_related("outbound_message").order_by("-created_at")[: max(1, int(limit))]
    items = []
    for row in rows:
        key, params = _bell_key(row)
        items.append(
            InboxItem(
                id=str(row.pk),
                subject=row.subject,
                body=row.body,
                read=row.read_at is not None,
                created_at=row.created_at,
                outbound_message_id=str(row.outbound_message_id),
                message_key=key,
                params=params,
            )
        )
    return tuple(items)


def mark_read(*, actor: Any, message_id: Any) -> InboxItem:
    """Mark ONE of the signed-in user's messages read. Forward-only.

    Already-read is a no-op that returns the row rather than an error: a second
    click on the same item is not a mistake to report. There is no mark-unread,
    for BR-NOT-005's reason — a fact about a message being seen is not un-made.
    """
    row = _mine(actor).filter(pk=message_id).first()
    if row is None:
        # Deliberately the same answer for "no such message" and "somebody
        # else's message": distinguishing them would let a caller enumerate
        # other people's mailbox ids by watching which id gives which error.
        raise InboxRefused(
            "that message is not in your inbox. An in-app message belongs to one person, "
            "and there is no read of anybody else's mail on this surface."
        )
    if row.read_at is None:
        row.read_at = timezone.now()
        row.save(update_fields=["read_at", "updated_at"])
    return InboxItem(
        id=str(row.pk),
        subject=row.subject,
        body=row.body,
        read=True,
        created_at=row.created_at,
        outbound_message_id=str(row.outbound_message_id),
    )


def mark_all_read(*, actor: Any) -> int:
    """Mark every unread message of the signed-in user read; return how many.

    Returns the COUNT because the screen has to be able to say what it just did,
    and because "Mark all read" on an already-empty inbox and on a full one must
    not look the same to anyone reading the response.
    """
    return _mine(actor).filter(read_at__isnull=True).update(read_at=timezone.now())


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-018@cr009inapp (12-governance/11-change-requests.md → CR-009 "PO RULINGS 2026-08-17 (fourth set)" in full · 04-docs/05-modules/10-notifications/02-business-rules.md BR-NOT-019/BR-NOT-020 · apps/notifications/provider_seam.py (the adapter contract, quoted) · apps/notifications/dispatcher.py (the only caller))
# generated: 2026-08-17 by story-coder (CR-009 in-app channel lane)
# checklist: A✔ B✔ C✔ D=deferred(the HTTP half is in_app_api.py) E=deferred(the screen is AppShell.tsx's bell, wired in ShellWithSession.tsx) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_cr_009_in_app_channel.py · RED PROVED FIRST — see the test file's own trailer for the four guards broken before they were trusted
# exceptions: (1) `sent`, NEVER `delivered`. BR-NOT-013 keeps `delivered` a provider CONFIRMATION nothing in this repo can write, and this adapter does not become one by being local — it reports that the platform accepted the message into an inbox. Whether a human looked is `read_at`, a different column answering a different question. (2) NO AUDIT ROW PER READ — the DELIVERY is audited by the dispatcher's per-batch row and the queue row is the permanent record; a row per bell-open would bury the money actions hard rule 7 protects. (3) NO PER-USER RLS — tenant isolation is the policy's (0012) and per-user isolation is this module's, because not one function here takes a user id from a caller. Stated in the .sql file too. (4) NO MARK-UNREAD, by BR-NOT-005's forward-only discipline.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
