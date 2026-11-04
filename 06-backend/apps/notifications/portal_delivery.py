# ── Trace ──────────────────────────────────────────────
# Change:   CR-084 — the customer portal becomes a delivery channel. PO
#           2026-09-07, pointing at the greyed-out row on Settings →
#           Notifications → Bill ready: *"can you swithc on this now - Customer
#           portal"*.   Screens: S8 (Settings → Notifications) · CWP-027 (Your
#           bills) · CWP-031 (Documents and letters)
# Rules:    BR-NOT-1031 (the customer portal is a delivery channel and the
#           PLATFORM is its provider — no integration, no credentials, no
#           vendor) · BR-NOT-010 AS AMENDED (v1 channels; door-hanger still out
#           until v2) · BR-NOT-005 (queue only: nothing here is reachable from a
#           request that wants to SEND) · BR-CWP-045 (documents are SERVED,
#           never re-rendered) · BR-CWP-083 / OQ-1399 CLOSED 2026-09-04 (the
#           portal is a CONVENIENCE COPY; post and email remain the delivery
#           record) · BR-BIL-036 (print is the FLOOR — a portal row can only
#           ever be an EXTRA route) · CLAUDE.md hard rule 1 (tenant scoping)
# Tests:    06-backend/tests/test_cr084_portal_channel.py
# Impacts:  apps/notifications/provider_seam.py (resolves this module as the
#           adapter for `portal`, exactly as it resolves `in_app`) ·
#           apps/notifications/dispatcher.py (hands it the batch) ·
#           apps/notifications/correspondence_reads.py (the read CWP-031 serves
#           the row through) · apps/portal/selectors.py `documents`
# ───────────────────────────────────────────────────────
"""notifications → CUSTOMER PORTAL delivery: publishing, not posting.

╔══════════════════════════════════════════════════════════════════════════╗
║  THIS IS A PROVIDER ADAPTER. IT IS NOT A SECOND SEND PATH.               ║
╚══════════════════════════════════════════════════════════════════════════╝

`deliver_batch` has exactly one caller — `provider_seam.dispatch_batch`, invoked
by the dispatcher after it has claimed a batch, rendered it and stamped a batch
id. That is the same door a real ESP would come through, and it is the whole
reason `in_app` was built this way first: a channel that proves the pipeline is
only proof if the message travelled the REAL path.

────────────────────────────────────────────────────────────────────────────
WHAT "DELIVERY" MEANS ON THIS CHANNEL, AND WHY IT IS NOT A NO-OP
────────────────────────────────────────────────────────────────────────────
The other four channels HAND A COPY to somebody else — a print house, an SMTP
server, Twilio, a staff mailbox row. This one does not, and it is worth being
precise about why that is delivery rather than nothing happening:

**The customer's portal reads `outbound_messages` directly.**
`correspondence_reads.account_correspondence` is the published read behind
`CWP-031` *Documents and letters*, and `apps/portal/selectors.documents` is its
one portal caller. So the row IS the copy. Writing a second artefact somewhere
for the portal to read would be two records of one document — which is exactly
what `frozen_documents` treats as a constraint violation, not as a feature.

**So what this adapter does is CHECK, and then say so.** The one thing that can
be untrue about a portal delivery is that there is nothing for the customer to
open: a bill whose PDF was never stored has a row on the queue and no document
behind it, and reporting *published to your portal* over that would be the
switch-with-nothing-behind-it the old refusal sentence warned about. So the
document store is asked, per message, and a row with no artefact FAILS with its
reason instead of being marked sent.

⚠ **NOT RETRYABLE, AND THAT IS DELIBERATE.** A missing stored document is a
configuration or a render gap, not a provider outage; it will not acquire an
artefact by being retried three times with backoff. It rests `failed` with the
reason on it, where the dispatch home's re-queue can pick it up once the
document exists.

────────────────────────────────────────────────────────────────────────────
`sent`, NEVER `delivered` — AND THE PORTAL IS THE CHANNEL WHERE THAT MATTERS
MOST
────────────────────────────────────────────────────────────────────────────
`OQ-1399` closed on 2026-09-04 with the portal as a **convenience copy**: post
and email remain the delivery record (`BR-CWP-083`). A portal row therefore
says *we published this where you can read it* and may never say *you read it*.
`delivered` stays what `BR-NOT-013` makes it — a provider confirmation nothing
in this repo can write — and this adapter does not become one by being local.

Whether a person actually opened the document is a different fact in a different
place, and this product does not record it. That is stated rather than implied,
because a portal channel is exactly where somebody would later be tempted to
claim otherwise.

────────────────────────────────────────────────────────────────────────────
THE ADDRESS OF A PORTAL MESSAGE IS THE ACCOUNT NUMBER
────────────────────────────────────────────────────────────────────────────
Every other channel's `recipient_address` is an email address, an E.164 number,
a postal line or a user id. This one's is the **account number** — `AC-000141`,
the reference printed on the bill the customer is holding and the one the
portal's own enrolment asks them for. Not the account's uuid: a database id is
never a visible value (B14 rule 31) and `recipient_address` is drawn on the
staff dispatch home.

⚠ **AND IT IS NEVER `unavailable`, WHICH IS THE ONE DECISION HERE THAT COULD
HAVE GONE THE OTHER WAY.** An account nobody has enrolled in the portal still
gets its portal copy, because publication does not depend on anyone having
signed up yet: the document is there the day they do. Recording *not enrolled*
as an unavailable reason would make a bill's permanent delivery record depend on
a customer's FUTURE sign-up, and that record would then be wrong the day after
they enrolled. `customers.selectors.delivery_recipients_for_account` answers
this channel with an address for every account it can resolve, and the reasoning
is written there too.

────────────────────────────────────────────────────────────────────────────
NOTHING IS FROZEN HERE, AND THE REASON IS NOT `in_app`'s
────────────────────────────────────────────────────────────────────────────
`frozen_documents.FREEZE_CHANNELS` holds the three channels a customer document
LEAVES on. `portal` is absent, and not because the channel is unimportant — it
is because the portal SERVES the artefact that another route already froze
(`BR-CWP-045`: documents are served, never re-rendered), and the store holds one
artefact per (source, channel, content type). A second freeze under a new
channel would be a second copy of one document.

⚠ **THAT LEANS ON THE PRINT FLOOR AND SAYS SO OUT LOUD.** `portal` is offered
only on events whose source kind has a floor (`invoice` today), so a frozen
artefact always exists by the time this adapter runs. The check below is what
turns that dependency from an assumption into a verdict: if the floor ever stops
applying to an event that offers this channel, these rows fail loudly by name
instead of reporting a publication of nothing.
"""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from apps.notifications import models
from apps.tenancy import document_store

#: What this adapter calls itself on every answer, so a delivery record a year
#: from now says which code marked the row. `platform.` is `in_app`'s prefix and
#: means the same thing here: no third party was involved.
ADAPTER = "platform.portal"

#: Why a portal publication could not be reported. CODES, never prose — the
#: dispatch home groups on them.
REASON_NO_DOCUMENT = "no_document_to_publish"
REASON_NO_ACCOUNT = "no_account_on_the_row"


class PortalDeliveryRefused(Exception):
    """The batch itself is unusable — not one message's problem."""


def deliver_batch(messages: tuple[dict[str, Any], ...]) -> dict[str, dict[str, Any]]:
    """Publish each message to its account's portal — or say why it could not.

    The contract is `provider_seam`'s, implemented verbatim: one answer per
    message id, `status` plus whatever the dispatcher needs to record. Nothing
    here advances a row; the dispatcher does that with the answer.
    """
    if not isinstance(messages, (list, tuple)):  # pragma: no cover - defensive
        raise PortalDeliveryRefused(
            "the portal adapter was handed something that is not a batch of messages, so "
            "it cannot answer per message and the dispatcher would mark rows sent that "
            "nobody published."
        )

    answers: dict[str, dict[str, Any]] = {}
    now = timezone.now()

    for message in messages:
        message_id = str(message.get("id"))
        source_type = message.get("source_type")
        source_id = message.get("source_id")
        account_id = message.get("account_id")

        if not account_id:
            answers[message_id] = {
                "status": models.STATUS_FAILED,
                "error": (
                    "this message names no account, and the customer portal shows a "
                    "document to the person who holds the account it belongs to. There is "
                    "nobody to publish it to. Not retryable: it will not acquire an "
                    "account by waiting."
                ),
                "retryable": False,
                "response": {"adapter": ADAPTER, "reason": REASON_NO_ACCOUNT},
            }
            continue

        stored = _stored_document(source_type, source_id)
        if stored is None:
            answers[message_id] = {
                "status": models.STATUS_FAILED,
                "error": (
                    "no copy of this document was kept, so there is nothing for the "
                    "customer to open in their portal. Reporting it as published would be "
                    "a switch with nothing behind it. Not retryable by the provider: the "
                    "document has to exist first, and re-queueing is what picks it up "
                    "once it does."
                ),
                "retryable": False,
                "response": {"adapter": ADAPTER, "reason": REASON_NO_DOCUMENT},
            }
            continue

        answers[message_id] = {
            "status": models.STATUS_SENT,
            # The document the customer will open. NOT a queue-row id and not an
            # account id: this is the artefact reference the portal serves, and
            # it is what makes "published" checkable after the fact.
            "provider_reference": stored,
            "response": {
                "adapter": ADAPTER,
                "published_at": now.isoformat(),
                "stored_document_id": stored,
                # ⚠ Reported as DATA rather than left to a screen to remember:
                # a portal row says the document is READABLE, never that it was
                # read. `OQ-1399` closed with the portal as a convenience copy.
                "delivery_reported": False,
            },
        }

    return answers


def _stored_document(source_type: Any, source_id: Any) -> str | None:
    """The id of the kept artefact for this document, or None if none was kept.

    Asked of `tenancy.document_store` — the module that owns `stored_documents`
    — rather than by querying the table here, which would be the cross-module
    read B1 forbids. Any CHANNEL's artefact answers: the portal serves the copy
    that was frozen for whichever route the document went out on, which is what
    `BR-CWP-045` means by SERVED rather than re-rendered.
    """
    if not source_type or not source_id:
        return None
    # `DocumentLookup` never returns an empty success — either `document` is set
    # or it carries `document_not_stored` — so `found` is the whole test and
    # there is no absence to infer. No `channel` is passed: the portal serves
    # whichever route's copy was kept.
    lookup = document_store.for_source(source_type=str(source_type), source_id=source_id)
    if not lookup.found or lookup.document is None:
        return None
    return str(lookup.document.id)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-084 (12-governance/11-change-requests.md → CR-084 in full · 04-docs/05-modules/10-notifications/02-business-rules.md BR-NOT-1031 · apps/notifications/provider_seam.py (the adapter contract, quoted) · apps/notifications/in_app.py (the precedent, read before this was written) · apps/notifications/correspondence_reads.py (the read the portal serves this row through))
# generated: 2026-09-07 by story-coder (CR-084 portal channel lane)
# checklist: A✔ B✔ C✔ D=n/a(no HTTP surface — the channel is drawn by the rule screen the server already feeds) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_cr084_portal_channel.py — RED PROVED FIRST through pytest, see that file's trailer
# exceptions: (1) `sent`, NEVER `delivered` — `BR-NOT-013` keeps `delivered` a provider CONFIRMATION nothing in this repo can write, and `OQ-1399` closed with the portal as a convenience copy, so this channel in particular may never claim a customer read anything. (2) NO SECOND ARTEFACT AND NO FREEZE — the portal serves what another route already froze (`BR-CWP-045`); the store holds one artefact per (source, channel, content type) and a portal freeze would be a second copy of one document. (3) NO `unavailable_reason` FOR AN UNENROLLED ACCOUNT — publication does not depend on a future sign-up; the reasoning is in the module docstring and in `customers.selectors.delivery_recipients_for_account`. (4) A MISSING STORED DOCUMENT IS NOT RETRYABLE — it is a render or configuration gap, not a provider outage, and burning three attempts would put it on a delivery dashboard as one.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
