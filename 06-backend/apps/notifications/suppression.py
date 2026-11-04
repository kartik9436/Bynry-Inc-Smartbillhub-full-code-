# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-014 (bounces + returned mail)   Screens: S8 · S30
# Rules:    BR-NOT-005 (forward-only lifecycle; retry ×3 with backoff IS the
#           answer to a transient failure — so a SOFT bounce may never reach
#           this table) · BR-NOT-013 (provider facts; nothing here invents one)
#           · BR-NOT-024 (print is the floor, so suppressing email never costs
#           a consumer their bill) · BR-PAY-018 (the paper half of the same
#           idea, already built as `outbound_messages.held`) · BR-TEN-043 (a
#           business date is a PARAMETER, never a clock read — G6 greps for it)
#           · CLAUDE.md hard rule 1 (tenant scoping) · hard rule 6
#           (idempotency) · hard rule 7 (every money action writes `audit_log`)
#           · hard-won law 14 (a failed statement poisons a PostgreSQL
#           transaction; the suite is SQLite and cannot reproduce it)
# Change:   DEF-NOT-5632, 2026-09-17.
# Tests:    06-backend/tests/test_def_not_5632_suppression.py
# Impacts:  apps/notifications/dispatcher.py (`_selectable` ANDs the filter) ·
#           apps/notifications/services.py (`queue_document` holds a new row) ·
#           apps/notifications/api.py (the list and the Release door)
# ───────────────────────────────────────────────────────
"""The ONE writer of the do-not-send list, and the two doors in and out of it.

The table, the key, and why this is not a column on `customers.Contact`, are all
argued in `suppression_models.py`. This file is the behaviour, and it has four
jobs and refuses to have a fifth:

  `suppress()`              put an address on the list — idempotent, audited
  `release()`               take it off, keeping the row — audited
  `selectable_filter()`     the dispatcher's half of the guarantee
  `hold_queued_for()`       make what is already queued visible as held

╔══════════════════════════════════════════════════════════════════════════╗
║  A SOFT BOUNCE CAN NEVER PRODUCE A SUPPRESSION, AND THE REFUSAL LIVES    ║
║  HERE RATHER THAN IN EVERY CALLER.                                       ║
╚══════════════════════════════════════════════════════════════════════════╝
`models.py` already rules it, in its own words: a soft bounce is *"RETRIED and
NEVER suppresses"*, because it means a mailbox was full, a server was busy or a
message was greylisted — and `BR-NOT-005`'s retry ×3 with backoff is this
product's answer to a transient failure. **Treat one as a hard bounce and a
customer whose mailbox was full on Tuesday loses email delivery for ever.**

**Why the guard is at the WRITER and not left to callers.** There is exactly one
way into this table, so a refusal here is a refusal everywhere — including from
a provider adapter written a year from now by someone who has read neither this
file nor `models.py`. SendGrid reports `bounce` with a TYPE and Postmark reports
`Bounce` with a hard/soft `Type` on one event; an adapter that drops the type,
or defaults it, is one line of plausible code away from suppressing every
transient failure a utility has. `suppress()` refuses `bounced_soft` **by name**
and says why in a sentence, so that adapter meets an error message instead of a
silent success.

────────────────────────────────────────────────────────────────────────────
WHAT DECIDES A SUPPRESSION IS NOT IN THIS FILE, AND THAT IS DELIBERATE
────────────────────────────────────────────────────────────────────────────
⚠ **THERE IS NO THRESHOLD, COUNT OR WINDOW ANYWHERE BELOW. Do not add one.**
*Suppress after 2 hard bounces, or 1 returned letter* is runbook 22's card, is
tenant-tunable (`suppress_after_bounces`), and is implemented in
`apps/runbooks/definitions/undeliverable_contacts.py::
step_apply_the_suppression_rule`. That runbook's own report says what it has
been waiting for: *"No column records a suppression, so '31 suppressed' is what
this run WOULD suppress. The KPI tile says To suppress until a writer is
bound."* This is that writer. Counting here as well would give one question two
answers, free to disagree, on a path where disagreeing means a consumer either
keeps getting mail at a dead address or stops getting it at a live one.

A complaint and an unsubscribe are different in kind and are NOT threshold
questions — the runbook's `HARD_KINDS` does not contain either. A person
clicking *this is spam* or *unsubscribe* has given an instruction, and it is
honoured on the first one.

────────────────────────────────────────────────────────────────────────────
IS A SUPPRESSION A MONEY ACTION? YES — AND THE PRECEDENT IS TWO FILES OVER
────────────────────────────────────────────────────────────────────────────
Hard rule 7 audits money actions, and the question is fair: no balance moves
here. But `delivery_ops.hold_paper_for_accounts` and
`release_held_for_accounts` — the PAPER half of exactly this idea — both write
`audit.money_action`, under `delivery.held` and `delivery.released`. The act is
the same act: **stopping a bill from reaching the customer it is addressed to,
and letting it through again.** A utility asked *why did this customer never get
their March bill* needs a name and a timestamp, and a release is the more
sensitive of the two, because it is a person overriding a machine's refusal.

So both doors audit, under `delivery.suppressed` and
`delivery.suppression_released`, in the SAME transaction as the write — a
suppression that stands without its trail row is the failure hard rule 7 exists
to prevent, and `core.audit` fails loudly rather than quietly.

⚠ **`audit_log` IS PRUNED ON A RETENTION SCHEDULE**, which is why the released
ROW is kept rather than deleted (`suppression_models.py`). The trail says who;
the row says what and still says it in three years.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef, Q

from apps.notifications import models, suppression_models
from core import audit, errors
from core import tenancy as core_tenancy

#: Hard rule 7 — `entity.action`, the dotted grammar `core.audit` documents and
#: the same shape `delivery.held` / `delivery.released` already use one file
#: over. One row per ADDRESS, not per blocked message: the per-message evidence
#: is the queue row's own `held` / `held_reason`.
AUDIT_SUPPRESSED = "delivery.suppressed"
AUDIT_RELEASED = "delivery.suppression_released"
AUDIT_ENTITY = "suppressed_address"

#: Why a queue row is held BY THIS RULE, in `held_reason`'s own vocabulary.
#: A CODE, because the dashboard groups on it — and a DIFFERENT code from
#: `delivery_ops.HELD_BAD_ADDRESS`, deliberately: that one is paper held because
#: an ENVELOPE came back and the account is flagged, this one is a message held
#: because the ADDRESS is on the do-not-send list. A clerk seeing them grouped
#: together would be looking at two different problems with two different fixes.
HELD_SUPPRESSED = "address_suppressed"

#: The outcome vocabulary → the reason it is recorded under. Three of
#: `models.PROVIDER_OUTCOME_STATUSES`; the other three do not suppress and are
#: named below so that a reader can see the six are accounted for rather than
#: wonder whether three were forgotten.
#:
#:   `delivered`     nothing happened that needs recording
#:   `failed`        OUR side could not hand it over — a provider outage, a
#:                   missing connection. It says nothing about the mailbox, and
#:                   `BR-NOT-005`'s retry is its answer.
#:   `bounced_soft`  REFUSED BY NAME. See the module docstring.
SUPPRESSING_OUTCOMES = {
    models.STATUS_BOUNCED_HARD: suppression_models.REASON_HARD_BOUNCE,
    models.STATUS_COMPLAINED: suppression_models.REASON_COMPLAINT,
    models.STATUS_UNSUBSCRIBED: suppression_models.REASON_UNSUBSCRIBED,
}


class SuppressionRefused(Exception):
    """This address cannot be suppressed or released, and here is why.

    Deliberately NOT a catalog exception, for `DeliveryOpsRefused`'s stated
    reason: it is raised inside work that may run over a morning's whole
    feedback batch, where the right handling is to record the break and carry
    on. `apps/notifications/api.py` translates it at the one layer that knows
    what HTTP is.

    `message_key`, where set, is the clerk's sentence for THIS refusal (B14
    rule 33); the positional text stays the diagnostic. Only the channel
    refusals carry one so far — they are the ones a future Block button would
    put in front of a clerk.
    """

    def __init__(self, detail: str, *, message_key: str | None = None) -> None:
        super().__init__(detail)
        self.message_key = message_key


#: The clerk's words for the two channel refusals (PO 2026-10-02 — the list
#: holds email and text only). Both live in all eleven catalogues.
KEY_POSTAL_REFUSED = "notifications.suppression.postal_refused"
KEY_CHANNEL_REFUSED = "notifications.suppression.channel_refused"


@dataclass(frozen=True)
class SuppressionWrite:
    """What a `suppress()` call did — and whether it was THIS call that did it.

    `created` is stated as a VALUE rather than left to be inferred, the
    discipline `services.QueueWrite` and `CycleResult.dispatched` already
    follow: a caller must be able to ASSERT that a second webhook delivery
    changed nothing (hard rule 6) instead of reading a docstring about it.
    """

    id: str
    address: str
    channel: str
    reason: str
    created: bool
    held_message_ids: tuple[str, ...] = ()


def _tenant_id() -> Any:
    """Hard rule 1: no tenant table is touched without `app.tenant_id` set."""
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def normalise_address(channel: str, address: str) -> str:
    """The form an address is MATCHED in — which is a judgment, not a fact.

    ⚠ **THIS FUNCTION DOES NOT CHANGE WHAT IS SENT TO.** The queue row keeps its
    own `recipient_address` snapshot exactly as the writer captured it
    (`BR-TEN-017`), and nothing here rewrites it. This is the comparison key and
    only the comparison key.

    **Email is lower-cased, and that is a choice with a cost.** RFC 5321 makes
    the local part case-SENSITIVE, so `Bob@example.com` and `bob@example.com`
    are, strictly, two mailboxes. In practice every mail provider this product
    will ever meet treats them as one, and every ESP suppression list is
    case-insensitive. The cost of matching case-sensitively is the one that
    matters: a hard bounce recorded against `Bob@…` would not stop the next bill
    going to `bob@…`, and the address on a queue row comes from whatever a clerk
    typed into a form. **The failure is asymmetric** — matching too widely holds
    a message a clerk can release in one click, matching too narrowly posts to a
    dead mailbox for ever and burns the sending reputation every utility on this
    platform shares. Recorded in the decision log rather than left in a comment.

    Whitespace is stripped on every channel: a trailing space is a typo in a
    form, never a different mailbox.
    """
    cleaned = (address or "").strip()
    if channel == models.CHANNEL_EMAIL:
        return cleaned.lower()
    if channel == models.CHANNEL_SMS:
        # `CR-198-BRC10` — a phone number is matched in E.164 (`+14025551049`),
        # the form Twilio reports a STOP in, so `(402) 555-1049` typed on a form
        # and `+1 402 555 1049` from the carrier are one number. A value that is
        # not a phone number keeps its stripped form, exactly as before.
        from apps.identity.phones import normalise_phone

        return normalise_phone(cleaned) or cleaned
    return cleaned


def active(channel: str | None = None):
    """This tenant's ACTIVE suppressions — the base read every caller starts from.

    `released_at IS NULL` is the whole definition of active, and it is written
    here ONCE so that the dispatcher's filter, the API list and the queue-time
    hold cannot drift into three slightly different ideas of it.
    """
    rows = suppression_models.SuppressedAddress.objects.filter(
        tenant_id=_tenant_id(), released_at__isnull=True
    )
    return rows.filter(channel=channel) if channel else rows


#: The three answers `GET /suppressions`'s `f.state` takes. Named here rather
#: than spelled in the view, because *active* already means one thing in this
#: module (`released_at IS NULL`) and a second definition in a view is how a
#: list and its own filter come to disagree.
STATE_ACTIVE = "active"
STATE_RELEASED = "released"
STATE_ALL = "all"
STATES = (STATE_ACTIVE, STATE_RELEASED, STATE_ALL)


def listing(*, state: str = STATE_ACTIVE, channel: str | None = None, reason: str | None = None):
    """The blocked-addresses list, ordered and tenant-scoped. One queryset.

    ⚠ **RETURNS A QUERYSET AND NEVER A LIST** — the page is taken in the
    DATABASE (`NFR-3`, 11b G5) and only the rows on screen are serialized. This
    list grows for ever, because a released row is kept as history, so there is
    no tenant size at which materialising it would be correct.

    Active first, then newest first: a released address is history and belongs
    below the thing a clerk came here to act on. `released_at` ascending puts
    NULLs first on PostgreSQL's default ordering for ASC and on SQLite alike,
    which is the one ordering detail worth stating rather than discovering.

    An unknown `state` falls back to ACTIVE rather than raising: this is a
    filter on a list, and a screen that asked for a state this product does not
    have should show a clerk their work, not an error.

    ⚠ **`reason` FILTERS HERE AND NOT IN THE BROWSER — `DEF-NOT-5637`.** The
    screen offers the four reasons as a filter because they are not
    interchangeable (`suppression_models` says so: a hard bounce is a typo a
    clerk can fix, a complaint is a person who does not want the mail, an
    unsubscribe is a button we gave them). A front end that filtered the PAGE it
    was handed would answer *no complaints* over a tenant whose complaints are
    all on page two — hard-won law 7's *reporting zero over a scope it silently
    excludes*, in a list control. An unknown reason narrows to nothing rather
    than falling back, because unlike `state` this filter has no default to fall
    back TO and a silent widening would show a clerk rows they did not ask for.
    """
    tenant_id = _tenant_id()
    rows = suppression_models.SuppressedAddress.objects.filter(tenant_id=tenant_id)
    if state == STATE_RELEASED:
        rows = rows.filter(released_at__isnull=False)
    elif state != STATE_ALL:
        rows = rows.filter(released_at__isnull=True)
    if channel:
        rows = rows.filter(channel=channel)
    if reason:
        rows = rows.filter(reason=reason)
    return rows.order_by("released_at", "-suppressed_at", "id")


def is_suppressed(*, channel: str, address: str | None) -> bool:
    """Is this address on the list right now? The question `queue_document` asks."""
    if not address:
        # A row with no address has nowhere to go anyway, and
        # `unavailable_reason` already records why. Never suppressed, never
        # counted as suppressed — the two absences must stay distinguishable.
        return False
    return active(channel).filter(address=normalise_address(channel, address)).exists()


def selectable_filter() -> Q:
    """The suppression half of the dispatcher's selection predicate.

    Lives here rather than in `dispatcher.py` so the rule and its reason stay
    with the story that owns them — exactly as `delivery_ops.selectable_filter`
    does for `BR-PAY-018`'s holds, and the dispatcher ANDs both into
    `_selectable`.

    ⚠ **THIS IS THE THIRD LAYER AND IT SHOULD NEVER BE THE ONE THAT FIRES.**
    `queue_document` holds a new row addressed to a suppressed address, and
    `suppress()` holds the ones already queued, so by the time a cycle runs
    every such row is `held=True` and `delivery_ops.selectable_filter()` has
    already excluded it. This exists because those two are WRITERS and this is
    the READER: a writer that is added later and forgets, or a row written
    before this slice landed, would otherwise be handed to a provider. **A row
    excluded by this filter and NOT held is a bug**, and
    `test_def_not_5632_suppression.py` asserts the two agree rather than
    assuming it.

    It is a correlated `EXISTS` over the partial unique index
    `uq_suppressed_addrs_active`, which leads on exactly `(tenant, channel,
    address)` — so it is an index probe per candidate row and not a scan.

    ⚠ **IT MATCHES CASE-INSENSITIVELY, WHICH MEANS `LOWER()` ON THE QUEUE ROW,
    AND THAT IS NOT INDEXED.** Stated rather than discovered: the claim query is
    already bounded to one page of candidates by `_selectable`'s own partial
    index, so the comparison is evaluated over a handful of rows and never the
    table. If a tenant's queue ever makes this measurable, the fix is a stored
    normalised column on `outbound_messages`, not a widening of this predicate.

    `iexact` on EVERY channel rather than only email, and the asymmetry
    `normalise_address` describes is the reason: matching too widely holds a
    message a clerk releases in one click, matching too narrowly posts to a dead
    mailbox for ever. A phone number and a postal address have no meaningful
    case for it to be wrong about.
    """
    suppressed = suppression_models.SuppressedAddress.objects.filter(
        tenant_id=OuterRef("tenant_id"),
        channel=OuterRef("channel"),
        released_at__isnull=True,
        address__iexact=OuterRef("recipient_address"),
    )
    return ~Exists(suppressed)


def hold_queued_for(*, channel: str, address: str, reason: str = HELD_SUPPRESSED) -> tuple[str, ...]:
    """Mark what is ALREADY queued to this address held, so a clerk can see it.

    `BR-PAY-018`'s paper rule, applied to a rail it was not written for:
    *"written, marked held, never dispatched, never lost."* The row is not
    deleted and its status does not move — `BR-NOT-005` is forward-only, and
    `held` is orthogonal to status for exactly this reason
    (`OutboundMessage.held`'s own docstring: *"a queued row that is not
    currently selectable"*).

    ⚠ **ONLY `queued` ROWS, AND THAT IS THE WHOLE CARE HERE.** A message already
    `sent` cannot be un-sent, and holding it would rewrite history the account
    timeline is showing a clerk.

    Returns the ids it held, so the caller can report a number instead of
    implying one.
    """
    rows = models.OutboundMessage.objects.filter(
        tenant_id=_tenant_id(),
        channel=channel,
        status=models.STATUS_QUEUED,
        held=False,
    )
    if channel == models.CHANNEL_EMAIL:
        rows = rows.filter(recipient_address__iexact=address)
    elif channel == models.CHANNEL_SMS:
        # `CR-198-BRC10` — a queued text's address is whatever a clerk typed, so
        # it is matched by the last four digits in SQL (every spelling of a
        # number shares them) and confirmed in E.164 here.
        wanted = normalise_address(channel, address)
        candidates = rows.filter(recipient_address__endswith=wanted[-4:])
        ids = [
            one.pk
            for one in candidates
            if normalise_address(channel, one.recipient_address or "") == wanted
        ]
        rows = rows.filter(pk__in=ids)
    else:
        rows = rows.filter(recipient_address=address)
    held_ids = tuple(str(row.pk) for row in rows)
    if held_ids:
        rows.update(held=True, held_reason=reason)
    return held_ids


@transaction.atomic
def suppress(
    *,
    channel: str,
    address: str,
    reason: str,
    at: datetime,
    actor: Any = None,
    detail: str | None = None,
    source_message_id: Any = None,
    actor_user_id: Any = None,
) -> SuppressionWrite:
    """Put ONE address on the do-not-send list. Idempotent, audited, refusable.

    `at` is a PARAMETER and never a clock read (`BR-TEN-043`): the moment a
    provider says a mailbox is dead is the provider's timestamp, not the moment
    our job happened to process the webhook, and G6 greps this module for clock
    reads.

    **What it refuses, and both refusals are by NAME rather than by falling
    through a lookup:**

      * `bounced_soft` — the guard this slice exists around. See the module
        docstring. The sentence names the customer's cost because whoever reads
        it is about to decide whether to work around it.
      * any reason not in `suppression_models.REASONS` — a vocabulary a caller
        invented is a value no screen can render and no clerk can group on.

    **Idempotency (hard rule 6)** is the database's, not a pre-check's. A
    feedback webhook delivered twice, or two workers handling one batch, both
    reach the INSERT; the partial unique constraint refuses the second and this
    returns `created=False` for it. A `get_or_create`-style pre-check would race
    in exactly the window that matters.

    ⚠ **THE SAVEPOINT IS NOT TIDINESS — IT IS THE ONLY CORRECT FORM, AND THE
    TEST SUITE CANNOT SHOW YOU WHY (CLAUDE.md hard-won law 14).** On PostgreSQL
    a failed statement ABORTS the whole transaction: every query after the
    `IntegrityError` raises `InFailedSqlTransaction` and the work is lost at
    COMMIT anyway, so the `except` branch below could not read the existing row
    without one. `config/settings/test.py` hardcodes in-memory SQLite, which has
    no aborted-transaction state, so the version WITHOUT this nested
    `transaction.atomic()` passes the entire suite green on every machine and
    fails the first time a real duplicate arrives in production. **Do not
    "simplify" it away.** Proved against a real PostgreSQL 16 — see this
    module's trailer.
    """
    if reason == "soft_bounce" or reason == models.STATUS_BOUNCED_SOFT:
        raise SuppressionRefused(
            "a SOFT bounce never suppresses an address (BR-NOT-005). It means the mailbox "
            "was full, the server was busy or the message was greylisted — all temporary — "
            "and retry ×3 with backoff is this product's answer to a transient failure. "
            "Suppressing on one would take email away from a customer whose mailbox happened "
            "to be full on a Tuesday, and print is the only channel they would have left."
        )
    if reason not in suppression_models.REASONS:
        raise SuppressionRefused(
            f"{reason!r} is not a reason an address can be suppressed for. The four are "
            f"{', '.join(suppression_models.REASONS)}. A reason a caller invented is a value "
            "no screen can render and no clerk can group on."
        )
    # ══ EMAIL AND TEXT ONLY — PO 2026-10-02, *"A · Email and text only - this
    # correct"* (`DEF-NOT-8538`, hard rule 8). A postal address is refused BY
    # NAME, because a street on this list would be a fifth home for an address;
    # paper already has its own door, `BR-PAY-018`'s bad-address flag.
    if channel == models.CHANNEL_PRINT:
        raise SuppressionRefused(
            "a POSTAL address cannot go on the do-not-send list (PO 2026-10-02: email and "
            "text only). An address is stored on the premises and nowhere else (hard rule "
            "8); returned paper is handled by the account's bad-address flag (BR-PAY-018).",
            message_key=KEY_POSTAL_REFUSED,
        )
    if channel not in suppression_models.SUPPRESSIBLE_CHANNELS:
        raise SuppressionRefused(
            f"{channel!r} has no address a person could ask us to stop using; the "
            f"do-not-send list holds {' and '.join(suppression_models.SUPPRESSIBLE_CHANNELS)} "
            "only (PO 2026-10-02).",
            message_key=KEY_CHANNEL_REFUSED,
        )
    tenant_id = _tenant_id()
    normalised = normalise_address(channel, address)
    if not normalised:
        raise SuppressionRefused(
            "an empty address cannot be suppressed. A message with no address is already "
            "recorded as such on the queue row (`unavailable_reason`), and the two absences "
            "must stay distinguishable: one customer has no email address, the other has one "
            "that does not work."
        )

    created = True
    try:
        # THE SAVEPOINT. Read the docstring before touching this.
        with transaction.atomic():
            row = suppression_models.SuppressedAddress.objects.create(
                tenant_id=tenant_id,
                channel=channel,
                address=normalised,
                reason=reason,
                reason_detail=detail,
                source_message_id=source_message_id,
                suppressed_at=at,
                suppressed_by=actor_user_id or audit.actor_user_id(actor),
            )
    except IntegrityError:
        # Already on the list. The DATABASE told us, which is the only answer
        # that survives a race this code never saw.
        row = (
            suppression_models.SuppressedAddress.objects.filter(
                tenant_id=tenant_id,
                channel=channel,
                address=normalised,
                released_at__isnull=True,
            ).first()
        )
        if row is None:  # pragma: no cover - a different constraint failed
            raise
        created = False

    # Even on the second delivery: a row queued since the first one still needs
    # holding, and doing it only on `created` would leave it selectable.
    held = hold_queued_for(channel=channel, address=normalised)

    if created:
        # Hard rule 7, in the SAME transaction — a suppression cannot stand
        # without its trail row. `core.audit` fails loudly.
        audit.money_action(
            actor,
            AUDIT_SUPPRESSED,
            AUDIT_ENTITY,
            str(row.pk),
            after={
                "channel": channel,
                "address": normalised,
                "reason": reason,
                "detail": detail,
                "held_messages": len(held),
            },
        )
    return SuppressionWrite(
        id=str(row.pk),
        address=normalised,
        channel=channel,
        reason=reason,
        created=created,
        held_message_ids=held,
    )


def suppress_for_outcome(
    *,
    message: models.OutboundMessage,
    outcome: str,
    at: datetime,
    actor: Any = None,
    detail: str | None = None,
) -> SuppressionWrite | None:
    """THE CONTRACT A PROVIDER ADAPTER MAPS ONTO — one outcome in, one row or None.

    `models.PROVIDER_OUTCOME_STATUSES` is described in its own docstring as
    *"the CONTRACT an adapter maps onto"*; this is that contract's suppression
    half. An adapter normalises SendGrid's `bounce(+type) · spamreport ·
    unsubscribe` or Postmark's `Bounce(+Type) · SpamComplaint ·
    SubscriptionChange` into one of the six words, hands it here, and this
    decides nothing except which of those six earns a row.

    Returns `None` — never raises — for `delivered`, `failed` and
    **`bounced_soft`**, because on this path a soft bounce is an ordinary,
    expected outcome that the retry policy handles, and making the adapter catch
    an exception for the commonest transient event would be an invitation to
    wrap the call in a bare `except`. The REFUSAL in `suppress()` is still there
    for a caller that asks for a soft-bounce suppression EXPLICITLY, which is
    the mistake worth shouting about.

    ⚠ **NOTHING CALLS THIS TODAY AND THAT IS STATED RATHER THAN IMPLIED
    (hard-won law 2: built is not wired).** `BR-NOT-013` still holds — no
    provider adapter with a feedback door exists on any channel — so no
    `bounced_hard`, `complained` or `unsubscribed` is ever written on this
    deployment, and therefore nothing reaches this function. Its callers today
    are the tests. The READ half of the slice IS live from the same commit: the
    dispatcher consults the list on every cycle, so the day an adapter lands and
    calls this, the guarantee is already enforced rather than still to be wired.

    ⚠ **IT DOES NOT ADVANCE THE MESSAGE'S STATUS**, and that is a boundary and
    not an omission. The lifecycle is `dispatcher.forward_only`'s
    (`BR-NOT-005`), it has one guard and one set of allowed transitions, and a
    second writer of `status` in this module is how a forward-only rule stops
    being one. An adapter advances the row and then calls this.
    """
    reason = SUPPRESSING_OUTCOMES.get(outcome)
    if reason is None:
        return None
    return suppress(
        channel=message.channel,
        address=message.recipient_address or "",
        reason=reason,
        at=at,
        actor=actor,
        detail=detail,
        source_message_id=message.pk,
    )


@transaction.atomic
def release(
    *,
    suppression_id: Any,
    actor: Any,
    at: datetime,
    note: str | None = None,
    actor_user_id: Any = None,
) -> suppression_models.SuppressedAddress:
    """Let an address through again — the clerk's door, and the one that matters.

    ⚠ **THIS EXISTS BECAUSE A HARD BOUNCE IS OFTEN A TYPO.** The commonest way
    an address is dead is that somebody mistyped it at sign-up, which is
    `models.py`'s own first example. Without this door the product's answer to
    *we fixed the address* would be *that customer receives email again never*,
    and the harm would be the exact harm the soft-bounce guard exists to
    prevent, arriving one step later and permanently. The Product Owner asked
    for it by name — **Release**, on the blocked-addresses view.

    **Three things happen and all three are deliberate:**

      1. the row is stamped released and KEPT (`suppression_models.py` argues
         why: `audit_log` is pruned and the row is the durable answer to *why
         did this customer stop getting email in March*);
      2. every queue row held BY THIS RULE for that address becomes selectable
         again — the same rows, the same pins, the same recipient snapshots,
         nothing re-rendered and nothing re-created, which is
         `delivery_ops.release_held_for_accounts`' ratified shape;
      3. it is audited under `delivery.suppression_released` with the note, the
         name and the count, because a person overriding a machine's refusal is
         the more sensitive of this file's two doors.

    ⚠ **IT RELEASES ONLY ROWS HELD BY `HELD_SUPPRESSED`.** A message held by
    `BR-PAY-018`'s paper suppression is held for a DIFFERENT reason with a
    different fix, and releasing it here would undo a hold this rule never
    placed — `delivery_ops.release_held_for_accounts` is that hold's own and
    only door.

    Refuses a suppression that is already released, rather than returning
    quietly: a clerk pressing Release twice should be told the second press did
    nothing, and a caller looping over a selection needs the break recorded.
    """
    tenant_id = _tenant_id()
    row = suppression_models.SuppressedAddress.objects.filter(
        tenant_id=tenant_id, pk=suppression_id
    ).first()
    if row is None:
        raise SuppressionRefused(
            "there is no such blocked address for this utility. It may already have been "
            "removed from the list by someone else."
        )
    if row.released_at is not None:
        raise SuppressionRefused(
            "this address is not blocked any more — it was released on "
            f"{row.released_at:%Y-%m-%d}. Nothing has changed."
        )

    row.released_at = at
    row.released_by = actor_user_id or audit.actor_user_id(actor)
    row.released_note = note
    row.save(update_fields=["released_at", "released_by", "released_note", "updated_at"])

    held = models.OutboundMessage.objects.filter(
        tenant_id=tenant_id,
        channel=row.channel,
        held=True,
        held_reason=HELD_SUPPRESSED,
    )
    if row.channel == models.CHANNEL_EMAIL:
        held = held.filter(recipient_address__iexact=row.address)
    else:
        held = held.filter(recipient_address=row.address)
    released_ids = [str(one.pk) for one in held]
    if released_ids:
        held.update(held=False, held_reason=None)

    audit.money_action(
        actor,
        AUDIT_RELEASED,
        AUDIT_ENTITY,
        str(row.pk),
        before={"released_at": None, "reason": row.reason},
        after={
            "channel": row.channel,
            "address": row.address,
            "note": note,
            "released_messages": len(released_ids),
        },
    )
    return row


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-NOT-5632 (12-governance/10-defect-log.csv) · apps/notifications/models.py (STATUSES + PROVIDER_OUTCOME_STATUSES + the hard/soft paragraph, which is the policy this binds a writer to) · apps/runbooks/definitions/undeliverable_contacts.py (the THRESHOLD policy, deliberately not duplicated here) · apps/notifications/delivery_ops.py (BR-PAY-018's paper half, whose shape this repeats) · 04-docs/02-decisions/02-database-design-brief.md DB-16
# generated: 2026-09-17 by an AI lane (SendGrid/Postmark gap 4 — the do-not-send list)
# checklist: A✔ B=deferred(no frontend half — the blocked-addresses SCREEN is DEF-NOT-5637; its API is served here) C✔ D✔ E=deferred(as B) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: pytest tests/test_def_not_5632_suppression.py — every case proved RED first; the SAVEPOINT case was proved on REAL PostgreSQL 16 (sqlite cannot reproduce it at all — hard-won law 14), by removing the nested atomic and watching `InFailedSqlTransaction` where the suite had been green
# exceptions: (1) NO AUTOMATIC WRITER — `BR-NOT-013` holds and no provider adapter with a feedback door exists, so `suppress_for_outcome` has no production caller today. Stated out loud (law 2). The READ half is live and wired from this commit. (2) NO THRESHOLD — runbook 22 owns it; see the docstring. (3) `DEF-RBS-4331` IS NOT CLOSED — the customers-side contact-channel fact is a different fact with a different key and is still owed. (4) AMENDED 2026-10-02 (PO: *"A · Email and text only - this correct"*, `DEF-NOT-8538`): PRINT, `in_app` and `portal` are REFUSED here, a postal address by name; `BR-PAY-018`'s flag and `outbound_messages.held` remain the paper rail, unchanged.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
