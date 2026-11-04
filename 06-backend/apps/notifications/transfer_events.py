# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-016 (the property sale) × US-NOT-001 (the queue)
#           Screens: S89 the transfer wizard · the TRANSFER RECORD
# Rules:    BR-CUS-1030 (a transfer REASSIGNS the account — the CUSTOMER
#           changes and nothing else does) · BR-NOT-005 (queue only — nothing
#           here sends) · BR-NOT-013 (no delivery adapter on any channel) ·
#           BR-NOT-024 (the print floor, and why this kind is not on it) ·
#           BR-TEN-017 (the recipient is snapshotted at queue time) ·
#           BR-TEN-043 (no wall clock) · CLAUDE.md rule 1 (tenant scoping) ·
#           rule 6 (idempotency)
# Change:   `DEF-CUS-5949` — *"A sale tells nobody it happened"*, from the PO's
#           own two words on the transfer wizard: *"no commucation options"*.
# Tests:    06-backend/tests/test_transfer_scenarios.py (the `communication`
#           dimension of all twenty-five scenarios)
# Impacts:  apps/customers/notifications_seam.py (the ONLY caller — customers
#           resolves this module BY NAME and never imports it) ·
#           apps/notifications/models.py SOURCE_TYPES (`transfer`) ·
#           apps/notifications/catalogs.py (the three classes) ·
#           06-backend/tests/test_cr048_print_floor.py (the classification)
# ───────────────────────────────────────────────────────
"""The three things a property sale says, and to WHICH of the two parties.

╔══════════════════════════════════════════════════════════════════════════╗
║  WHAT THIS IS FOR, in one sentence a clerk would recognise:              ║
║  a house is sold, and the person who bought it and the person who sold   ║
║  it are each told that the account changed hands on that day.            ║
╚══════════════════════════════════════════════════════════════════════════╝

Before this file **a committed sale queued nothing at all**: `notifications_
seam` published five account write names and not one of them was a transfer,
so neither party heard anything. The blueprint draws three messages going out
on commit and the scenario suite declares the same three — two to the buyer,
one to the seller.

⚠ **QUEUED IS NOT SENT AND THIS MODULE NEVER CLAIMS OTHERWISE.** Measured on
the beta on 2026-09-20: **373 messages are queued in this product and not one
has ever been sent** — `sent_at` is null on every row and `BR-NOT-013` says
why, there is no provider adapter on email, SMS or print. Every sentence this
module and its callers write says *queued*.

────────────────────────────────────────────────────────────────────────────
⛔ THE HARD PART: A MESSAGE ADDRESSES AN ACCOUNT, AND AFTER A SALE THE ACCOUNT
   IS THE BUYER'S
────────────────────────────────────────────────────────────────────────────
`outbound_messages` has `account_id` and **no customer or recipient column**.
`BR-CUS-1030` makes a sale a REASSIGNMENT: the account does not move, its
CUSTOMER changes. So from the instant the commit lands, *"the account"* means
*"the buyer"*, and a row addressed by `account_id` alone **cannot be told apart
from a row addressed to the person who has just sold the property.**

**THE SELLER'S MESSAGE THEREFORE CARRIES NO `account_id` AT ALL.** It is
`NULL`, exactly as it is for an applicant (`service_request_events`) and for
the staff-addressed report rows the column was made nullable for, and WHO the
message is for travels three ways instead, none of them a new column:

  1. **`recipient_snapshot.party`** — the literal string `seller` or `buyer`,
     written beside the name and the customer id. `BR-TEN-017` already makes
     this payload the record of who a message was addressed to as it stood at
     queue time, which is the question being asked.
  2. **the `template_code`** — `transfer_to_seller` is a different class from
     `transfer_to_buyer`, because the two letters say different things.
  3. **`source_id`** — see the idempotency section: it is derived per party, so
     the two rows cannot collide even on one channel.

**WHY NOT A `recipient_customer_id` COLUMN.** It was weighed and rejected, and
the reasoning is in `12-governance/02-decision-log.md` under *A transfer
message names its party in the snapshot, not in a new column* (2026-09-20).
The short form: a column would be a 🔒 migration on a table eleven writers
share, to record a fact `recipient_snapshot` was built to record, and it would
still not answer the question for the 373 rows already queued. The snapshot is
readable by every existing dashboard, costs no migration, and is what
`service_request_events` already does for the same reason one kind over.

⚠ **AND IT IS A JUDGMENT, NOT A GUESS.** If a later screen needs to LIST *every
message ever addressed to this customer*, a JSONB read is the wrong index and a
column becomes right. That is a new ruling with a migration and a review-ledger
row, and it is named here so the next lane does not have to rediscover the
trade.

────────────────────────────────────────────────────────────────────────────
THE IDEMPOTENCY KEY — DERIVED PER PARTY, BECAUSE THERE IS ONLY ONE ROW
────────────────────────────────────────────────────────────────────────────
The queue's key is `(tenant, source_type, source_id, channel, copy_no)`.

Every other writer in this product names a ROW for the occasion: a move record,
a disconnect case, a `service_request_events` row. **A sale has exactly one
occasion row — the `transfers` row — and three messages come off it**, two of
them on the same channel. Keying all three on `transfer.id` would put the
buyer's letter and the seller's letter on one key: the second would meet the
unique index, `queue_document` would report `created=False`, the caller would
be told it was queued, and **the seller would be sent the buyer's letter or
nothing at all.** That is `move`'s documented trap, one kind over.

So `source_id` is `uuid5(transfer.id, party+channel)` — **derived, not minted**,
and the derivation is the whole point: a replayed commit computes the same three
ids and writes nothing (CLAUDE.md rule 6), while three messages off one sale
cannot collide with each other. It is a KEY and not a row pointer, which is
stated here because `source_id`'s own column comment says *"which of its
rows"* and a reader is owed the difference. `transfer.id` is recoverable from
every row through `render_context["transfer_id"]`, so nothing is lost.

────────────────────────────────────────────────────────────────────────────
NO EVENT KEY, AND NO PRINT FLOOR — BOTH DELIBERATE
────────────────────────────────────────────────────────────────────────────
`event_key` is what lets a utility switch a class of automatic message off on
Settings → Notifications. **None is passed**, because `rule_catalog.EVENTS` has
no transfer event and inventing one here would be this module minting a SET-12
row a tenant would then see a toggle for. Adding one is a `CR` with a row in
`rule_catalog.EVENTS`, not a keyword quietly added here.

`transfer` gets **no entry in `CHANNEL_FLOOR_BY_SOURCE`**. `BR-NOT-024` names
SIX source kinds print is the floor on and a transfer is none of them; a lane
may not widen a signed rule by editing a dictionary — that is the `move`
precedent, where the merge lane put it to the PO instead. If a utility asks for
a posted change-of-ownership letter, that is a `BR-NOT-024` amendment for the
PO. The consequence is stated rather than hidden: **a utility gets an email and
a text and no letter**, and because there is no floor and no rule join, all
three rows are written unconditionally.

────────────────────────────────────────────────────────────────────────────
THE WORDING IS SEEDED DEFAULT, NOT SIGNED LAW
────────────────────────────────────────────────────────────────────────────
The three classes are catalogued here — the TOKEN WHITELIST is engineering
vocabulary and is this lane's to define — and their BODIES are seeded in
`seed_templates.py` as defaults a tenant edits on Settings, the same posture
every authored class in this product takes. **Nobody has ratified the words a
change-of-ownership letter uses**, and that is `OQ-CUS-12524`, OPEN. It does not
block the queue: a row with an unratified default body is a message that can be
edited, where no row at all is a sale that told nobody.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from apps.notifications import catalogs, customer_context, models, services
from core import errors
from core import tenancy as core_tenancy

#: The SOURCE KIND all three messages ride. Added to `models.SOURCE_TYPES` and
#: classified in the print-floor test's `NOT_A_DOCUMENT_KINDS` bucket in the
#: SAME commit — the second edit that `portal` proved gets forgotten.
SOURCE_TRANSFER = "transfer"

#: The three classes. Two letters and one text, because the two letters say
#: different things to two different people and the text is a different
#: channel with a 160-character budget.
TEMPLATE_TO_BUYER = "transfer_to_buyer"
TEMPLATE_TO_SELLER = "transfer_to_seller"
TEMPLATE_FIELD_VISIT = "transfer_field_visit_sms"

#: WHICH PARTY a row is for, written into `recipient_snapshot.party`. Two
#: CODES rather than prose, because a dashboard groups on them and cannot
#: group on a sentence — the reasoning every other code family in this module
#: carries.
PARTY_BUYER = "buyer"
PARTY_SELLER = "seller"

#: The namespace the derived `source_id` is computed in. A fixed UUID rather
#: than `uuid.NAMESPACE_OID`, so the derivation is this product's and cannot
#: collide with anything else that hashes the same transfer id.
_TRANSFER_MESSAGE_NAMESPACE = uuid.UUID("6f3d5f2a-8b41-4d2e-9c77-0a1b2c3d4e5f")


class TransferMessageRefused(Exception):
    """This message cannot be queued, and here is why — in a clerk's words.

    Its own type rather than `customer_events.MoveMessageRefused` for the
    reason `ApplicantMessageRefused` exists: the seam resolves a refusal type
    per module, and catching a move's type on a sale's failure path would
    report every real problem as `..._error` and lose the sentence a human
    could have acted on.
    """


@dataclass(frozen=True)
class TransferMessage:
    """One queued message, as the caller needs to report it."""

    template_code: str
    #: `buyer` or `seller` — WHO this row is for, carried out of this module so
    #: a caller can say so without re-reading the snapshot it just wrote.
    party: str
    source_id: str
    message_id: str | None
    created: bool
    channels: tuple[str, ...]
    #: The address the queue snapshotted, or None when there was none. Carried
    #: because proving a row exists and proving it is addressed to the right
    #: person are two different claims.
    address: str | None
    problems: tuple[dict[str, Any], ...]


def _tenant_id() -> Any:
    """Hard rule 1: no tenant table is touched without `app.tenant_id` set.

    Raised rather than leaned on, for `service_request_events`' reason: the
    default suite runs on SQLite, which has no RLS at all, so a queryset
    trusting the policy would pass every test and write across tenants in
    production.
    """
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def message_key(transfer_id: Any, *, party: str, channel: str) -> uuid.UUID:
    """The derived `source_id` for ONE of a sale's messages.

    ⚠ **PUBLISHED RATHER THAN PRIVATE, AND THAT IS WHAT MAKES RULE 6 CHECKABLE
    INSTEAD OF PROMISED.** A test, a support query or a later read can compute
    the same three keys from a transfer id and look the rows up; a private
    helper would leave *"a replayed commit writes nothing"* as a claim in a
    docstring, which is hard-won law 1's whole subject.
    """
    return uuid.uuid5(_TRANSFER_MESSAGE_NAMESPACE, f"{transfer_id}:{party}:{channel}")


#: Per channel, what an ABSENT address means when the caller LOOKED and found
#: nothing. ⚠ **`REASON_NOT_RESOLVABLE` IS NOT USED HERE AND THAT IS THE
#: POINT** — `models.py` spends a paragraph on the difference: *"'0 of 1,122
#: hold an address' and 'we could not count' must never render the same."* The
#: sale's caller reads `contacts` itself, so an empty address is a VERIFIED
#: absence and is recorded as one.
_NO_ADDRESS_REASON = {
    models.CHANNEL_EMAIL: models.REASON_NO_EMAIL,
    models.CHANNEL_SMS: models.REASON_NO_MOBILE,
}


def _queue(
    *,
    template_code: str,
    party: str,
    channel: str,
    transfer_id: Any,
    account_id: Any,
    address: str | None,
    recipient_name: str | None,
    customer_id: Any,
    context: dict[str, Any],
    actor: Any,
    job: str,
    language: str | None,
    on_date: date | None,
) -> TransferMessage:
    """One message, one channel, one row. Raises only what a human can repair.

    ⚠ **AN ABSENT ADDRESS IS A ROW, NOT A REFUSAL, AND THAT IS `BR-BIL-036`.**
    *"An account with NO email address is normal, not an exception."* A missing
    address travels as `unavailable_reason` on the row — the queue's own way of
    RECORDING an absence — so the sale still leaves three rows and a clerk can
    see that one of them has nowhere to go. A refusal here would delete the
    evidence that the message was owed.
    """
    _tenant_id()
    if catalogs.catalog_for(template_code) is None:  # pragma: no cover - defensive
        raise TransferMessageRefused(
            f"{template_code!r} has no template class, so this message has no token "
            "whitelist to render against and nothing is queued. A letter rendered "
            "against no whitelist is a letter nobody checked."
        )
    cleaned = (address or "").strip()
    recipient = services.Recipient(
        channel=channel,
        address=cleaned or None,
        # ⛔ **THE ONE FIELD THAT ANSWERS *WHO IS THIS FOR* FOR THE SELLER.**
        # See the module docstring: after a sale `account_id` names the buyer,
        # so the party and the customer id live here or nowhere.
        snapshot={
            "party": party,
            "name": recipient_name or "",
            "customer_id": str(customer_id) if customer_id else "",
        },
        unavailable_reason=(
            None if cleaned else _NO_ADDRESS_REASON.get(channel, models.REASON_NOT_RESOLVABLE)
        ),
    )
    write = services.queue_document(
        source_type=SOURCE_TRANSFER,
        source_id=message_key(transfer_id, party=party, channel=channel),
        channels=(channel,),
        template=services.TemplatePin(code=template_code),
        account_id=account_id,
        recipients=(recipient,),
        render_context={
            # `transfer_id` is how the real row is recovered from a derived
            # key — see the idempotency section of the module docstring.
            "transfer_id": str(transfer_id),
            **context,
        },
        actor=actor,
        job=job,
        language=language,
        on_date=on_date,
        # NO `event_key`. See the module docstring.
    )
    message = write.messages[0] if write.messages else None
    return TransferMessage(
        template_code=template_code,
        party=party,
        source_id=str(message_key(transfer_id, party=party, channel=channel)),
        message_id=str(message.id) if message is not None else None,
        created=bool(message.created) if message is not None else False,
        channels=tuple(item.channel for item in write.messages),
        address=cleaned or None,
        problems=tuple(write.problems),
    )


def queue_transfer_to_buyer(
    *,
    transfer_id: Any,
    account_id: Any,
    account_no: str | None,
    buyer_customer_id: Any,
    buyer_name: str | None,
    buyer_email: str | None,
    service_address: str | None,
    sold_on: date | None = None,
    actor: Any = None,
    job: str | None = None,
    language: str | None = None,
) -> TransferMessage:
    """*The account is yours from today* — the buyer's change-of-ownership letter.

    `account_id` IS set on this row: after the commit the account belongs to the
    buyer, so the column says something true and the account timeline (S35) and
    `GET /outbound?f.account_id=` both find it.

    ⚠ **NO BALANCE AND NO DEPOSIT FIGURE TRAVELS IN THE BODY, AND THE ABSENCE IS
    A DECISION.** `BR-CUS-1030` means the account's own ledger is unbroken
    across the sale, so *what the buyer took on* is a figure the account screen
    already states and that moves the instant a payment lands. A number frozen
    into a letter queued today and delivered whenever an adapter is plugged in
    would be wrong by exactly the amount the account has moved since — the same
    reasoning the transfer record page carries for `Balance as it stood`.
    """
    return _queue(
        template_code=TEMPLATE_TO_BUYER,
        party=PARTY_BUYER,
        channel=models.CHANNEL_EMAIL,
        transfer_id=transfer_id,
        account_id=account_id,
        address=buyer_email,
        recipient_name=buyer_name,
        customer_id=buyer_customer_id,
        context={
            "customer_name": buyer_name or "",
            "first_name": customer_context.greeting_name(buyer_name) or "",
            "account_no": account_no or "",
            "service_address": service_address or "",
            # A DATE, never `.isoformat()` (DEF-NOT-10480): the renderer formats
            # by TYPE, so a string printed `2026-10-22` whatever the utility's
            # Regional format said. The queue codec keeps the type on the row.
            "sold_on": sold_on,
        },
        actor=actor,
        job=job or "customers.transfer_reassign",
        language=language,
        on_date=sold_on,
    )


def queue_transfer_to_seller(
    *,
    transfer_id: Any,
    account_no: str | None,
    seller_customer_id: Any,
    seller_name: str | None,
    seller_email: str | None,
    service_address: str | None,
    sold_on: date | None = None,
    actor: Any = None,
    job: str | None = None,
    language: str | None = None,
) -> TransferMessage:
    """*The account is no longer yours* — the seller's change-of-ownership letter.

    ⛔ **`account_id` IS DELIBERATELY NOT A PARAMETER OF THIS FUNCTION.** It is
    not omitted at the call site where a later lane could "fix" it; there is
    nowhere to pass it. The account belongs to the buyer from the moment the
    commit lands, so stamping it here would file the seller's letter under the
    buyer's account and make the two indistinguishable on every screen that
    reads the column. The whole argument is in the module docstring.

    ⚠ **`seller_email` IS THE ADDRESS THE UTILITY HELD BEFORE THE SALE, AND THE
    CALLER MUST READ IT BEFORE IT CARRIES THE BUYER'S DETAILS ONTO THE
    ACCOUNT.** `contacts` is keyed to the ACCOUNT, and `BR-CUS-1081` has the
    sale write the buyer's email onto exactly that row. A caller that read the
    contact afterwards would address the seller's letter to the buyer — which
    is the same confusion this module exists to prevent, arriving through the
    back door.
    """
    return _queue(
        template_code=TEMPLATE_TO_SELLER,
        party=PARTY_SELLER,
        channel=models.CHANNEL_EMAIL,
        transfer_id=transfer_id,
        account_id=None,
        address=seller_email,
        recipient_name=seller_name,
        customer_id=seller_customer_id,
        context={
            "customer_name": seller_name or "",
            "first_name": customer_context.greeting_name(seller_name) or "",
            "account_no": account_no or "",
            "service_address": service_address or "",
            # A DATE, never `.isoformat()` (DEF-NOT-10480): the renderer formats
            # by TYPE, so a string printed `2026-10-22` whatever the utility's
            # Regional format said. The queue codec keeps the type on the row.
            "sold_on": sold_on,
        },
        actor=actor,
        job=job or "customers.transfer_reassign",
        language=language,
        on_date=sold_on,
    )


def queue_transfer_field_visit(
    *,
    transfer_id: Any,
    account_id: Any,
    account_no: str | None,
    buyer_customer_id: Any,
    buyer_name: str | None,
    buyer_phone: str | None,
    service_address: str | None,
    sold_on: date | None = None,
    actor: Any = None,
    job: str | None = None,
    language: str | None = None,
) -> TransferMessage:
    """*Somebody is coming to read the meter* — the third drawn message.

    **SMS, and to the BUYER.** The visit is the changeover read
    (`BR-WRK-055`), which happens on the property the buyer now holds, so the
    person who needs to let a technician in is the new owner. The seller gets
    no text: they are not going to be there.

    ⚠ **IT IS QUEUED WHETHER OR NOT A CREW COULD BE BOOKED, AND THAT IS THE
    HONEST ORDER.** `services._raise_flow_work` runs AFTER the commit and is
    allowed to fail — *"a field module able to refuse a property transfer would
    be this product telling somebody they may not sell their house"*. So this
    text says a visit is being arranged, never that one is confirmed at a time,
    and it carries no appointment window. A window in a queued text is a
    promise nothing in this product is yet able to keep.
    """
    return _queue(
        template_code=TEMPLATE_FIELD_VISIT,
        party=PARTY_BUYER,
        channel=models.CHANNEL_SMS,
        transfer_id=transfer_id,
        account_id=account_id,
        address=buyer_phone,
        recipient_name=buyer_name,
        customer_id=buyer_customer_id,
        context={
            "customer_name": buyer_name or "",
            "first_name": customer_context.greeting_name(buyer_name) or "",
            "account_no": account_no or "",
            "service_address": service_address or "",
            # A DATE, never `.isoformat()` (DEF-NOT-10480): the renderer formats
            # by TYPE, so a string printed `2026-10-22` whatever the utility's
            # Regional format said. The queue codec keeps the type on the row.
            "sold_on": sold_on,
        },
        actor=actor,
        job=job or "customers.transfer_reassign",
        language=language,
        on_date=sold_on,
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-CUS-5949 · apps/customers/transfers.py `reassign_account` ·
#         apps/customers/notifications_seam.py · apps/notifications/services.py
#         `queue_document` · apps/notifications/service_request_events.py (the
#         recipient-travels-in precedent) · BR-CUS-1030 · BR-NOT-013 ·
#         BR-NOT-024 · BR-TEN-017 · decision log 2026-09-20
# generated: 2026-09-20 by lane TRANSFER BACKEND
# checklist: A✔ B=n/a(no screen of its own) C✔ D=n/a(not an API surface)
#            E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# ──────────────────────────────────────────────────────────
