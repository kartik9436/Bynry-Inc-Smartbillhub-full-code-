# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-025 (EP-INT-07) TC-2 — *"queue rows rest `queued` with the
#           config-missing marker; no shared-sender fallback"*. US-INT-003 —
#           the consequence copy needs the NUMBER of rows that will wait.
#           US-INT-026 TC-5 — the dispatcher resolves the credential INSIDE
#           the seam at use time. Screens: S8 (the confirm) · S141
# Rules:    BR-INT-016 (disconnect destroys the secret; nothing queued or
#           recorded is lost) · BR-NOT-005 (rows rest `queued` when the
#           channel's provider config is missing; the queue is the only send
#           path) · BR-INT-008 (integrations sends nothing — the dispatcher
#           stays the only sender) · BR-TEN-013 (cross-module work goes
#           through the owner's published callable, never its ORM) ·
#           A15 addendum (the utility's OWN address, never a shared sender)
# Tests:    06-backend/tests/test_us_int_025_disconnect.py
# Impacts:  apps/integrations/services.py (`disconnect` reads this) ·
#           apps/notifications/delivery_ops.py (`deferred_backlog`, the
#           published callable this reads) · apps/notifications/provider_seam.py
#           (the OTHER direction of the same boundary — it resolves ours)
# ───────────────────────────────────────────────────────
"""integrations → notifications: what is waiting, and what disconnect does to it.

TWO DIRECTIONS, ONE BOUNDARY, AND THIS IS THE QUIET HALF
---------------------------------------------------------
`apps/notifications/provider_seam.py` is the loud half: the dispatcher asking
integrations whether a channel may be dispatched and handing it a batch. This
file is the other way round — integrations asking notifications *how many
messages are resting on this channel right now*, because a confirm dialog that
says **"12 queued bills will wait"** is a different dialog from one that says
"queued work will wait", and only one of them is checkable.

⚠ **IT READS. IT NEVER WRITES, AND THE NOT-WRITING IS THE RULE (BR-INT-016).**
Disconnect does nothing at all to the queue: no cancel, no fail, no re-route,
no shared-sender fallback. The rows stay exactly `queued` and the dispatch home
already surfaces them as config-missing through `provider_seam.channel_route`,
which will now answer `provider_not_connected` because the connection is `off`.
That is the whole mechanism, and it works because NOTHING here touches it —
which is why this file has one read and no writer to reach for.

WHY A COUNT AND NOT A LIST
--------------------------
The confirm needs a figure, not the rows. A tenant mid-cycle can hold tens of
thousands of queued messages and the dialog shows one number; pulling the rows
to count them would be the same defect `US-INT-020` avoided by storing only the
items a run could NOT do.

`None` IS NOT ZERO — the distinction this repo keeps making
------------------------------------------------------------
`queued_on_channel` answers `None` when notifications cannot answer at all
(not installed, no published callable, a read that raised). `0` means it
answered and there is nothing waiting. A screen that renders those the same
tells a utility nothing is waiting when the truth is that nobody looked —
`apps/billing/release.py`'s own rule: *"'0 of 1,122 hold an address' and 'we
could not count' must never render the same."*
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

from core.tenancy import current_tenant_id

#: The neighbour's published read, named once so it is greppable from BOTH
#: sides of the boundary (G20 harvests these).
NOTIFICATIONS_MODULE = "notifications"
BACKLOG_READ = "deferred_backlog"

#: Manifest category → the notifications channel its connection feeds. A
#: category with no channel simply has no queue behind it, which is most of
#: them; the map is data so a new category is a row and never a branch (G77).
CATEGORY_CHANNEL: dict[str, str] = {
    "email": "email",
    "messaging": "sms",
    "print": "pdf_print",
}


def _resolve(attribute: str, kind: str = "delivery_ops") -> Any:
    """The owner's callable, or None while it has not published one."""
    try:
        target = import_module(f"apps.{NOTIFICATIONS_MODULE}.{kind}")
    except ImportError:  # pragma: no cover — defensive
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


#: `CR-174-BRC10` — the one staff alert the payment-agent door raises.
STAFF_ALERT_WRITE = "queue_staff_alert"


def queue_staff_alert(**alert: Any) -> dict[str, Any] | None:
    """ONE in-app alert to the utility's System Admins, or `None` while unwired.

    `CR-174-BRC10`: a payment agent's message that could not be posted (an
    account we cannot find — D2's residue — or a return that keeps arriving
    before its payment) is a clerk's to look at, and the coordinator's brief
    names who is told: the System Admin. `notifications.services.
    queue_staff_alert` addresses the ruled staff audience when no person is
    the actor (BR-NOT-021), opens its own savepoint and **never raises**, so a
    failed alert can never fail the money message it describes.
    """
    read = _resolve(STAFF_ALERT_WRITE, kind="services")
    if read is None:  # pragma: no cover — notifications publishes it
        return None
    return read(**alert)


def channel_for(category: str) -> str | None:
    """Which notifications channel a provider of this category feeds, if any."""
    return CATEGORY_CHANNEL.get(category)


def queued_on_channel(channel: str | None) -> int | None:
    """How many messages rest `queued` on this channel for the current tenant.

    `None` when there is no channel behind this category, or when
    notifications cannot answer — never a zero standing in for silence.
    """
    if channel is None:
        return None
    read = _resolve(BACKLOG_READ)
    if read is None:
        return None
    try:
        backlog = read()
    except Exception:  # noqa: BLE001 — a read that fails must not break a disconnect
        return None
    if not isinstance(backlog, dict):  # pragma: no cover — contract drift
        return None
    return int(backlog.get(channel, 0))


def waiting_for_category(category: str) -> tuple[str | None, int | None]:
    """`(channel, queued)` for a provider category — what the confirm shows."""
    channel = channel_for(category)
    return channel, queued_on_channel(channel)


#: Where the KINDS OF MESSAGE live. `apps.notifications.catalogs.CR_CATEGORIES`
#: is `CR-007`'s own list in the PO's own order — *Billing · Collections ·
#: Payments · Service & field · Account lifecycle* — and it is the axis a
#: SENDER can resolve: an `OutboundMessage` carries `template_code`, and
#: `catalogs.listing_for(code).category` turns that into one of these five.
NOTIFICATION_CLASS_MODULE = "catalogs"
NOTIFICATION_CLASS_LIST = "CR_CATEGORIES"


def notification_classes() -> tuple[str, ...]:
    """The kinds of message this product sends — notifications' own list.

    Read here rather than copied, because a connector setting that varies by
    the kind of message (`registry.Field.per_class`) has to be validated
    against the SAME list the sender will resolve against. Two copies is
    hard-won law 1: the manifest would go on accepting a class that no longer
    exists, and nothing would go red.

    ⚠ **`()` MEANS *WE COULD NOT ASK*, AND IT IS NOT AN EMPTY LIST OF
    CLASSES.** `registry._validate_per_class` refuses a manifest by name when
    this comes back empty, which is the fail-closed direction: the alternative
    is a per-class setting whose keys are unchecked. This module's own rule —
    *"`None` IS NOT ZERO"* — is the same distinction one column over.

    ⚠ **THE OTHER AXIS IS NOT THIS ONE, AND THE CHOICE IS RECORDED RATHER THAN
    LEFT TO BE INFERRED.** `rule_catalog.CATEGORIES` has six values and answers
    *what part of the business SCHEDULES a message*; a message in flight does
    not carry the rule that scheduled it, so a sender could not resolve it.
    """
    try:
        catalogs = import_module(f"apps.{NOTIFICATIONS_MODULE}.{NOTIFICATION_CLASS_MODULE}")
    except ImportError:  # pragma: no cover — defensive
        return ()
    found = getattr(catalogs, NOTIFICATION_CLASS_LIST, ())
    if not isinstance(found, (list, tuple)):  # pragma: no cover — contract drift
        return ()
    return tuple(str(one) for one in found)


# ═════════════════════════════════════════════════════════════════════════
# THE OTHER DIRECTION — what notifications asks US (US-INT-026 TC-5)
# ═════════════════════════════════════════════════════════════════════════
#
# `apps/notifications/provider_seam.py` resolves these two by name at CALL
# time, on `apps.integrations.services`. They are DEFINED here, beside the
# read above, because they are two halves of one boundary and splitting a
# boundary across two files is how the halves drift; `services.py` re-exports
# them so the address the neighbour looks at is the address it has always
# looked at, and `provider_seam.py` needed no edit for either to start
# working (hard-won law 2's opposite: a seam that was wired before it was
# built, and became live the moment something was behind it).
#
# ⚠ THE CREDENTIAL IS RESOLVED INSIDE THIS FILE, AT USE TIME, AND THE
# DISPATCHER NEVER HOLDS IT. `US-INT-026` TC-5 states the guarantee in those
# words. The plaintext exists for the length of `adapter.execute(...)` and is
# dropped in a `finally`; it is not on the returned dict, not on the queue
# row, and not in this module's namespace afterwards.
#
# ⚠ AND SENDING IS STILL THE DISPATCHER'S (BR-INT-008). Nothing here is
# reachable except through `provider_seam.channel_route`, which refuses every
# channel a tenant has not switched on — email is off until W6 (BR-INT-007:
# *the connection may be made from day one; SENDING activates W6*). Wiring the
# adapter did not switch anything on, and a test asserts that.


def _channel_category(channel: str) -> str | None:
    for category, mapped in CATEGORY_CHANNEL.items():
        if mapped == channel:
            return category
    return None


def _connection_for_channel(channel: str):
    """The tenant's live connection for this channel, or None.

    Enabled, production, with an adapter bound and an active credential —
    every one of those is a reason a batch could not go, and answering None
    here means the dispatcher records `provider_not_connected` and the rows
    rest `queued`. It never means a message was lost.

    ⚠ **THE TENANT IS STATED IN THE QUERY, NOT LEFT TO RLS (`DEF-INT-5568`).**
    `provider_key__in`, `enabled` and `environment` are true of every utility
    that has switched a mailbox on, so with no tenant named this returned *the
    oldest enabled production mail connection on the platform* — and what leaks
    here is not a number on a screen: it is one utility's bills leaving through
    another utility's mail server, under that utility's sender address and
    against its sending allowance. RLS `FORCE` stopped it on PostgreSQL; the
    suite runs on SQLite, which has no RLS at all, so it passed every test in
    this repository (hard-won law 14). `runners/serve.py::_connection_for`
    argues the same point at length and is the house style this now matches.

    **No context means NO connection, never everybody's** (hard-won law 3) —
    the dispatcher then records `provider_not_connected` and nothing is lost,
    which is the same honest answer a utility with no mailbox gets.
    """
    from apps.integrations import models as integration_models
    from apps.integrations.registry import REGISTRY

    tenant_id = current_tenant_id()
    if tenant_id is None:
        return None
    category = _channel_category(channel)
    if category is None:
        return None
    keys = [one.key for one in REGISTRY.all() if one.category == category]
    rows = list(
        integration_models.IntegrationConnection.objects.filter(
            tenant_id=tenant_id,
            provider_key__in=keys,
            enabled=True,
            environment=integration_models.ENVIRONMENT_PRODUCTION,
        ).order_by("connected_at")
    )
    for row in rows:
        if REGISTRY.adapter_for(row.provider_key) is None:
            continue
        if not integration_models.IntegrationCredential.objects.filter(
            connection=row, is_active=True
        ).exists():
            continue
        return row
    return None


def reports_feedback(connection) -> bool:
    """Does this connection's provider have a way to tell us what BOUNCED?

    ⚠ **THIS IS A FACT ABOUT THE PROVIDER, NOT ABOUT OUR PROGRESS**, and the
    difference is `BR-INT-027`'s whole point. A bulk email service declares a
    `receive_feedback` operation (`manifests/sendgrid.py`,
    `manifests/postmark.py` — one file named `email_bulk.py` until
    `CR-115-BRC05`) and will call us
    back. **A mailbox never will** — SMTP hands a message to a server and the
    bounce, if there is one, arrives hours later as a new email to a human. So
    for a mailbox this answers `False` **for ever**, not *not yet*, and the
    delivery dashboard must go on saying *not reported* rather than settling
    into a zero once the connection looks healthy.
    """
    from apps.integrations.registry import REGISTRY

    manifest = REGISTRY.get(getattr(connection, "provider_key", None) or "")
    if manifest is None:
        return False
    return any(
        (one.direction, one.initiative) == ("in", "them")
        for one in manifest.operations
    )


def _category_is_connectable(category: str) -> bool:
    """Whether ANY provider of this category can be connected on this platform.

    Read from the same place a connect is refused from — a manifest whose key
    has no adapter in the registry answers *Cannot be connected yet.* — so the
    two can never disagree about what a utility is able to do.
    """
    from apps.integrations.registry import REGISTRY

    return any(
        REGISTRY.adapter_for(manifest.key) is not None
        for manifest in REGISTRY.all()
        if manifest.category == category
    )


def provider_connection_status(channel: str) -> dict[str, Any] | None:
    """`US-NOT-004` §5's readout — read-only, and never a secret.

    `None` is not *not connected*: it means this module cannot answer, and
    `provider_seam.provider_status` already refuses to render the two the
    same. We CAN answer for every channel we know a category for, so the only
    `None` here is a channel with no integrations category behind it.
    """
    from apps.integrations import selectors
    from apps.integrations.registry import REGISTRY

    category = _channel_category(channel)
    if category is None:
        return None
    platform = _platform_manifest(category)
    if platform is not None:
        return _platform_status(channel, platform)
    row = _connection_for_channel(channel)
    if row is None:
        return {
            "channel": channel,
            "connected": False,
            "provider_key": None,
            "describe": None,
            # Nothing is connected, so nothing can report. Stated rather than
            # left absent: a caller that has to guess will guess zero.
            "reports_feedback": False,
            # `DEF-NOT-8451` — could this utility connect one if it tried? A
            # category whose manifests have NO adapter bound (print and SMS
            # today) answers every connect with *Cannot be connected yet.*, so
            # "not connected" there is the PLATFORM's gap and not the tenant's,
            # and the dispatcher must not send a clerk to Settings to fix it.
            "connectable": _category_is_connectable(category),
        }
    return {
        "channel": channel,
        "connected": True,
        "provider_key": row.provider_key,
        "status": row.status,
        "describe": selectors.describe_line(REGISTRY.require(row.provider_key), row, REGISTRY),
        # `BR-INT-027` — the delivery dashboard reads this to choose WHICH
        # *not reported* sentence is true, and the two are not interchangeable:
        # *nothing is connected* stopped being true the day a utility connected
        # its mailbox, and a sentence that has quietly become false is
        # hard-won law 1 rather than a wording preference.
        "reports_feedback": reports_feedback(row),
        # Lane SETTINGS-MOVE (2026-10-22) — the provider's NAME, so a channel's
        # one line can say *"Sending through Custom SMTP"* rather than a key.
        "provider_name": REGISTRY.require(row.provider_key).display_name,
    }


#: The provider a utility's own mail server is connected through.
SMTP_PROVIDER_KEY = "email_smtp"
#: The channel a mail server carries (`notifications.models.CHANNEL_EMAIL`).
EMAIL_CHANNEL = "email"


def email_sender_status() -> dict[str, Any]:
    """The mail server this utility sends through, read-only and never a secret.

    PO 2026-10-22 (`DEF-NOT-10534`): *"We have to move everything in connector
    not any other place"*. Settings → Configure → Notifications shows THIS, not
    a form: *Active: Custom SMTP (smtp.office365.com)*, the sender address and
    the connector's state, with a link to Connectors.

    `active` is the dispatcher's own test (`_connection_for_channel`: switched
    on, production, adapter bound, a password held) — so the word *Active* on
    the screen can never disagree with whether an email can actually leave.
    Where nothing can send, the Custom SMTP connection is read anyway (any
    environment, production first), so a mail server typed in without its
    password still shows its host and *Not set up* instead of vanishing.

    No tenant in context answers *nothing connected* (hard-won law 3), the same
    honest answer `_connection_for_channel` gives.
    """
    from apps.integrations import models as integration_models
    from apps.integrations.registry import REGISTRY

    live = _connection_for_channel(EMAIL_CHANNEL)
    row = live
    tenant_id = current_tenant_id()
    if row is None and tenant_id is not None:
        rows = list(
            integration_models.IntegrationConnection.objects.filter(
                tenant_id=tenant_id, provider_key=SMTP_PROVIDER_KEY
            )
        )
        rows.sort(
            key=lambda one: 0 if one.environment == integration_models.ENVIRONMENT_PRODUCTION else 1
        )
        row = rows[0] if rows else None
    if row is None:
        return {
            "connected": False,
            "active": False,
            "provider_key": None,
            "provider_name": None,
            "host": None,
            "send_from": None,
            "status": None,
        }
    manifest = REGISTRY.get(row.provider_key)
    config = dict(row.config or {})
    return {
        "connected": True,
        "active": live is not None,
        "provider_key": row.provider_key,
        "provider_name": manifest.display_name if manifest is not None else row.provider_key,
        # A bulk email service has no host; only a mail server does.
        "host": (str(config.get("host") or "").strip() or None),
        "send_from": (
            str(config.get("send_from") or config.get("username") or "").strip() or None
        ),
        "status": row.status,
    }


def _sending_operation(connection):
    """The operation a dispatched batch runs as — the connection's first
    `out · us` one, which is what a mailbox declares for sending.

    It exists so the guard can read THIS operation's timeout and cap rather
    than the manifest's first, which for a mailbox is whatever happens to be
    listed first and may carry a different deadline.
    """
    from apps.integrations.registry import REGISTRY

    manifest = REGISTRY.get(connection.provider_key)
    if manifest is None:
        return None
    for one in manifest.operations:
        if (one.direction, one.initiative) == ("out", "us"):
            return one
    return manifest.operations[0] if manifest.operations else None


#: The channel whose messages carry a subject line. A text message and a printed
#: letter have none, so only this channel refuses a message without one.
SUBJECT_CHANNEL = "email"

#: `response.reason` on a message refused before any provider was dialled.
#: Not retryable: waiting does not give a render a subject or a body.
REFUSED_NOT_A_RENDER = "artifact_not_a_render"
REFUSED_NO_SUBJECT = "email_has_no_subject"
REFUSED_NO_BODY = "message_has_no_body"

#: `DEF-NOT-10460` — the neighbour's published read of a row's attachments
#: (`apps.notifications.attachments.for_handoff`), named once (G20).
ATTACHMENTS_KIND = "attachments"
ATTACHMENTS_READ = "for_handoff"
#: `response.reason` when a named attachment could not be fetched. RETRYABLE:
#: the store may answer next time, and the email waits rather than going out
#: without the file it promises.
ATTACHMENT_UNAVAILABLE = "attachment_not_fetched"


def _attachments(one: dict) -> list[dict[str, Any]]:
    """The stored files this message encloses, as `[{filename, content_type,
    content: bytes}]` — `[]` when it names none. RAISES when one cannot be
    fetched (the caller answers that as a retryable failure)."""
    read = _resolve(ATTACHMENTS_READ, kind=ATTACHMENTS_KIND)
    if read is None:  # pragma: no cover — notifications publishes it
        return []
    return list(read(one.get("snapshot")) or ())


def _refused(reason: str, error: str) -> dict[str, Any]:
    return {
        "status": "failed",
        "error": error,
        "retryable": False,
        "response": {"adapter": "integrations.seam", "reason": reason},
    }


def _work_item(channel: str, one: dict) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """One dispatcher message → one adapter work item, or a refusal.

    ⚠ **THE SUBJECT AND THE BODY ARE THE RENDER'S, READ FROM `artifact`
    (`DEF-NOT-10420`).** The dispatcher's payload (`dispatcher._payload`) puts the
    rendered `RenderedArtifact` under `artifact` as `{subject, body,
    template_code, template_version, language}`; `snapshot` is the RECIPIENT as
    it stood at queue time and has never held a subject. Until 2026-10-22 this
    read the subject from the snapshot (always `None`) and handed the WHOLE
    artifact dict over as the body, every adapter `str()`-ed it, and every email
    the product sent read `{'subject': …, 'body': 'Hi ——,\\n\\n…'}` under an
    adapter's made-up subject. `apps/notifications/in_app.py` reads it the right
    way and is the shape this now matches.

    ⚠ **A NON-RENDER IS REFUSED, NEVER STRINGIFIED, AND NOTHING IS INVENTED.** An
    `artifact` that is not a mapping (an older caller, a bare string), a body
    that is empty, or an EMAIL with no subject is answered here as a
    non-retryable failure naming the reason, and no provider is dialled for it:
    a customer is never sent a placeholder, and a default subject would be
    hardcoded words in a utility's name (PO 2026-10-22, *"don't do any
    hardcoding"*). The row's `last_error` carries the sentence, so the delivery
    dashboard shows a failed message rather than a sent one that said nothing.
    """
    ref = str(one.get("id"))
    artifact = one.get("artifact")
    if not isinstance(artifact, dict):
        return None, _refused(
            REFUSED_NOT_A_RENDER,
            "This message was not rendered from a template.",
        )
    subject = artifact.get("subject")
    body = artifact.get("body")
    if not isinstance(body, str) or not body.strip():
        return None, _refused(REFUSED_NO_BODY, "The message has no body.")
    if channel == SUBJECT_CHANNEL and (not isinstance(subject, str) or not subject.strip()):
        return None, _refused(REFUSED_NO_SUBJECT, "The message has no subject.")
    # `DEF-NOT-10460` — the files the row names (an agreement's PDF), fetched
    # under this tenant now, so every adapter receives bytes and none of them
    # reads the document store. Email only: a letter IS its document.
    files: list[dict[str, Any]] = []
    if channel == SUBJECT_CHANNEL:
        try:
            files = _attachments(one)
        except Exception as missing:  # noqa: BLE001 — any store failure; the row waits
            return None, {
                "status": "failed",
                "error": f"An attached file could not be read: {missing}",
                "retryable": True,
                "response": {"adapter": "integrations.seam", "reason": ATTACHMENT_UNAVAILABLE},
            }
    return (
        {
            "ref": ref,
            "address": one.get("address"),
            "subject": subject if isinstance(subject, str) else None,
            "body": body,
            # `CR-199-BRC10` S6 — the render's own branded HTML (email only);
            # `email_format.compose` sends it as the HTML alternative of `body`.
            "html": artifact.get("html") if isinstance(artifact.get("html"), str) else None,
            "attachments": files,
            # `DEF-NOT-10571` (WCAG 3.1.1) — the language the email's HTML
            # wrapper declares: the template variant it was rendered from, or
            # for a `default` variant the utility's own language, which is the
            # one `rendering` already writes its money in.
            "language": _message_language(artifact.get("language")),
        },
        None,
    )


def _message_language(variant: object) -> str | None:
    """The rendered variant's language, or the utility's own for `default`."""
    if isinstance(variant, str) and variant.strip() and variant.strip() != "default":
        return variant.strip()
    from apps.integrations.seams import tenancy as tenancy_seam

    return tenancy_seam.language()


def dispatch_outbound_batch(channel: str, messages: tuple) -> dict[str, dict]:
    """`BR-NOT-005`'s ONE hand-off: one call per batch, one entry per message.

    The contract is the neighbour's and is quoted in its docstring:
    `{"status": "sent"|"failed", …}` per message id. A message id we do not
    answer for is treated by the dispatcher as a retryable failure — silence
    is not success — so this returns an entry for every id it was given.

    Each message becomes `{ref, address, subject, body}` with the subject and
    body taken from the RENDER (`_work_item`); a message that cannot be one is
    answered as a non-retryable failure and the rest of the batch still goes.
    """
    from apps.integrations import services
    from apps.integrations.registry import REGISTRY
    from apps.integrations.runners.deliver import view_of

    rows = list(messages or ())
    if not rows:
        return {}
    category = _channel_category(channel)
    platform = _platform_manifest(category) if category is not None else None
    if platform is not None:
        return _dispatch_platform(channel, platform, rows)
    connection = _connection_for_channel(channel)
    if connection is None:
        return {
            str(one.get("id")): {
                "status": "failed",
                "error": "no provider is connected for this channel",
                "retryable": True,
                "response": {},
            }
            for one in rows
        }
    adapter_cls = REGISTRY.adapter_for(connection.provider_key)
    answer: dict[str, dict] = {}
    work: list[dict[str, Any]] = []
    for one in rows:
        item, refusal = _work_item(channel, one)
        if refusal is not None:
            answer[str(one.get("id"))] = refusal
        else:
            work.append(item)
    if not work:
        return answer
    operation = _sending_operation(connection)
    secrets = services.credential_secrets(connection)  # the ONE read (BR-INT-003)
    try:
        # ⚠ THIS IS THE CALL SITE THE WHOLE OF `BR-INT-041` IS ABOUT. The
        # dispatcher sweeps every tenant's queue in one worker pool; an
        # unguarded batch here is one utility's dead mail server holding a
        # worker that Silver Creek's 240 bills are waiting for.
        outcome = services.guarded_adapter_call(
            connection=connection,
            operation=operation,
            call=lambda _secrets=secrets: adapter_cls().execute(
                view_of(connection), _secrets, work
            ),
        )
    finally:
        del secrets
    if outcome.skipped or outcome.timed_out:
        # ⚠ RETRYABLE, AND THE ROWS STAY `queued`. Nothing was sent and nothing
        # is lost: the dispatcher's contract treats a failed entry as one to
        # come back to, which is exactly right for a provider we are declining
        # to dial. Marking these `sent` would lose a utility's bills; marking
        # them permanently failed would throw them away over an outage that
        # ends when the probe succeeds.
        for one in work:
            answer[one["ref"]] = {
                "status": "failed",
                "error": outcome.sentence,
                "retryable": True,
                "response": {},
            }
        return answer
    result = outcome.value
    by_ref = {one.ref: one for one in result.items}
    for one in work:
        ref = one["ref"]
        item = by_ref.get(ref)
        if item is None or item.outcome != "succeeded":
            answer[ref] = {
                "status": "failed",
                "error": (item.provider_text if item is not None else None) or "not answered for",
                "retryable": True,
                "response": {},
            }
        else:
            answer[ref] = {"status": "sent", "provider_reference": ref, "response": {}}
    return answer


# ═════════════════════════════════════════════════════════════════════════
# A CHANNEL THE PLATFORM PROVIDES — `CR-198-BRC10` (PO 2026-10-29, ruling 4B)
# ═════════════════════════════════════════════════════════════════════════
#
# Text messages go through ONE shared platform Twilio account. There is no
# tenant connection to find — the credential is the SERVER's
# (`platform_sms.py`) — so a category whose live, adapter-bound manifest
# declares `auth.mode == platform_holds_ours` is answered here instead of from
# `integration_connection`. Read off the manifest's DATA (G77: no branch on a
# provider key), so a second platform-provided channel is a manifest, not code.


def _platform_manifest(category: str | None):
    """The live, adapter-bound platform-provided manifest of this category."""
    from apps.integrations.registry import MODE_PLATFORM_HOLDS_OURS, REGISTRY

    if category is None:
        return None
    for manifest in REGISTRY.all():
        if (
            manifest.category == category
            and manifest.auth.mode == MODE_PLATFORM_HOLDS_OURS
            and not manifest.disposition.coming_soon
            and REGISTRY.adapter_for(manifest.key) is not None
        ):
            return manifest
    return None


def _utility() -> str | None:
    """This tenant's subdomain — the sender map and the callback path key on it."""
    from apps.integrations.seams import tenancy as tenancy_seam

    return tenancy_seam.subdomain()


def _platform_status(channel: str, manifest) -> dict[str, Any]:
    """`connected` is TRUE exactly when the platform's credentials and a sender
    for THIS utility are configured — the dispatcher's own test. Unconfigured is
    the PLATFORM's gap (`connectable: False`), never a connection the utility
    should go and make."""
    from apps.integrations import platform_sms

    utility = _utility()
    ready = platform_sms.configured(utility)
    return {
        "channel": channel,
        "connected": ready,
        "provider_key": manifest.key,
        "status": "working" if ready else None,
        "describe": None,
        # Delivery can be reported only when a public callback address exists.
        "reports_feedback": ready and platform_sms.status_callback_url(utility) is not None,
        "connectable": False,
        "provided_by_platform": True,
        "provider_name": manifest.display_name,
    }


def sending_ceiling(channel: str) -> int | None:
    """How many messages ONE hand-off on this channel may carry — the sending
    operation's per-minute rate when the platform provides the channel, so one
    dispatch cycle never hands Twilio more than a minute's worth (`CR-198-BRC10`
    judgment 6). `None` = no ceiling beyond the dispatcher's own batch size."""
    manifest = _platform_manifest(_channel_category(channel))
    if manifest is None:
        return None
    for one in manifest.operations:
        if (one.direction, one.initiative) == ("out", "us") and one.rate_limit_per_minute:
            return int(one.rate_limit_per_minute)
    return None


def _dispatch_platform(channel: str, manifest, rows: list) -> dict[str, dict]:
    """One hand-off through the PLATFORM's account. The credential is read at
    use time and dropped in `finally`, exactly as the tenant path does."""
    from apps.identity.phones import normalise_phone
    from apps.integrations import platform_sms
    from apps.integrations.registry import REGISTRY

    utility = _utility()
    answer: dict[str, dict] = {}
    if not platform_sms.configured(utility):
        for one in rows:
            answer[str(one.get("id"))] = {
                "status": "failed",
                "error": "The platform's text service is not set up.",
                "retryable": True,
                "response": {"adapter": "integrations.platform", "reason": "not_configured"},
            }
        return answer
    work: list[dict[str, Any]] = []
    for one in rows:
        item, refusal = _work_item(channel, one)
        if refusal is not None:
            answer[str(one.get("id"))] = refusal
            continue
        number = normalise_phone(item.get("address"))
        if number is None:
            answer[item["ref"]] = _refused(
                "not_a_phone_number", "That phone number cannot get texts."
            )
            continue
        item["address"] = number
        work.append(item)
    if not work:
        return answer
    adapter_cls = REGISTRY.adapter_for(manifest.key)
    secrets = platform_sms.secrets()
    try:
        result = adapter_cls().execute(platform_sms.view(utility), secrets, work)
    except Exception as exc:  # noqa: BLE001 — an outage is a retry, never a loss
        for one in work:
            answer[one["ref"]] = {
                "status": "failed",
                "error": f"The text service could not be reached: {type(exc).__name__}",
                "retryable": True,
                "response": {},
            }
        return answer
    finally:
        del secrets
    by_ref = {one.ref: one for one in result.items}
    for one in work:
        ref = one["ref"]
        item = by_ref.get(ref)
        if item is not None and item.outcome == "succeeded" and item.provider_reference:
            answer[ref] = {
                "status": "sent",
                # Twilio's `SM…` sid — what a signed status callback names.
                "provider_reference": item.provider_reference,
                "response": {"provider": manifest.key},
            }
            continue
        if item is None:
            error = "not answered for"
        elif item.provider_text:
            error = f"{item.detail or ''} {item.provider_text}".strip()
        else:
            error = item.detail or "not answered for"
        answer[ref] = {
            "status": "failed",
            "error": error,
            "retryable": True if item is None or item.retryable is None else bool(item.retryable),
            "response": {
                "provider": manifest.key,
                "code": None if item is None else item.provider_code,
            },
        }
    return answer


# The notifications writers the platform door lands into — named once (G20).
SMS_FEEDBACK_KIND = "sms_feedback"
TEXT_STATUS_WRITE = "record_status"
TEXT_STOP_WRITE = "record_stop"
TEXTED_READ = "has_texted"


def record_text_status(**status: Any) -> dict[str, Any] | None:
    write = _resolve(TEXT_STATUS_WRITE, kind=SMS_FEEDBACK_KIND)
    return None if write is None else dict(write(**status))


def record_text_stop(**reply: Any) -> dict[str, Any] | None:
    write = _resolve(TEXT_STOP_WRITE, kind=SMS_FEEDBACK_KIND)
    return None if write is None else dict(write(**reply))


def has_texted(number: str) -> bool:
    read = _resolve(TEXTED_READ, kind=SMS_FEEDBACK_KIND)
    return bool(read(number)) if read is not None else False


TEXT_ACTIVITY_READ = "text_activity"


def text_activity() -> dict[str, Any] | None:
    """When a text last left and the last failure — `None` = cannot answer."""
    read = _resolve(TEXT_ACTIVITY_READ, kind=SMS_FEEDBACK_KIND)
    return None if read is None else dict(read())


__all__ = [
    "BACKLOG_READ",
    "has_texted",
    "record_text_status",
    "record_text_stop",
    "sending_ceiling",
    "dispatch_outbound_batch",
    "provider_connection_status",
    "email_sender_status",
    "reports_feedback",
    "CATEGORY_CHANNEL",
    "NOTIFICATIONS_MODULE",
    "channel_for",
    "queued_on_channel",
    "waiting_for_category",
    "notification_classes",
    "NOTIFICATION_CLASS_MODULE",
    "NOTIFICATION_CLASS_LIST",
]


#: CR-173-BRC10 — the published staff-alert seam (`DEF-3422`): one in-app
#: message to the utility's System Admins (and the person who pressed the
#: button, when one did). PO 2026-10-07 (Q5): *"System admin of Utility/tenant"*.
STAFF_ALERT_WRITE = "queue_staff_alert"


def queue_staff_alert(**alert: Any) -> dict[str, Any]:
    """Raise one alert through notifications, or say why none was raised.

    Never raises — `bulk_summary.queue_staff_alert`'s own contract, kept on
    this side too: a failed notification must never fail the thing it reports.
    """
    published = _resolve(STAFF_ALERT_WRITE, kind="services")
    if published is None:
        return {
            "code": "not_published",
            "message_id": None,
            "note": "notifications publishes no staff alert",
        }
    try:
        return dict(published(**alert))
    except Exception as exc:  # noqa: BLE001 — see the docstring
        return {"code": "error", "message_id": None, "note": f"the alert could not be raised: {exc}"}


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-025@c05e4dd4 (EP-INT-07 story + BR-INT-016/042 snapshot; co-packet US-INT-003@c05e4dd4)
# generated: 2026-09-04 by the CR-069 wave E build lane
# checklist: A✔ B✔ C✔ D✔(the count rides on the card `provider_card().disconnect`) E✔(ConnectionDetailPage's Disconnect confirm renders it) F✔ G✔ H=n/a(no secret is read here — the credential seam is `services.credential_secrets`)
# gates: pytest tests/test_us_int_025_disconnect.py · G20 (the contract name is declared on both sides) · G78's rule kept by hand: this module writes nothing of notifications'
# exceptions: the category→channel map is DATA and covers three of the nine categories; the other six have no queue behind them and answer `None`
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
