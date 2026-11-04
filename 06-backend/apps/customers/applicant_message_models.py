# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-017 (the service-request register) × US-CUS-004
#           Screens: blueprint entry 06 capture step 6 (p080–p081)
# Rules:    BR-CUS-1076 (this table's own rule) · BR-CUS-079 (the applicant is
#           acknowledged) · BR-NOT-005 (queue only — nothing sends) ·
#           BR-NOT-013 (no delivery adapter on any channel) · BR-BIL-025 (a
#           template resolves on three axes and falls back on two) ·
#           BR-BIL-027 (nothing renders from a draft) · CLAUDE.md rule 1
#           (tenant scoping) · rule 6 (idempotency) · B14 rule 31 (no database
#           id on screen) · B14 rule 37 (a drawn figure is an illustration)
# Change:   CR-094-BRC01 lane J — the drawn `What goes out to the applicant`
#           block and its `Choosing a template` picker.
# Tests:    06-backend/tests/test_cr094_applicant_messages_block.py
# Impacts:  apps/customers/applicant_messages.py (the only writer) ·
#           apps/customers/models.py (registers this model) ·
#           apps/customers/migrations/0051 + 0052 (the table and its RLS)
# ───────────────────────────────────────────────────────
"""What a captured request INTENDS to say to the applicant (`service_request_messages`).

╔══════════════════════════════════════════════════════════════════════════╗
║  WHAT THIS IS FOR, in one sentence a clerk would recognise:              ║
║  at the counter a clerk ticks which messages this application will send  ║
║  and picks the wording for each, and the one that goes out when the      ║
║  decision is made is the reason the block exists.                        ║
╚══════════════════════════════════════════════════════════════════════════╝

Blueprint entry 06, capture step 6, read AS AN IMAGE (p080, scale 2 and scale
4 — B14 rule 42). The drawing is a table of FIVE rows under the columns `SEND ·
WHAT IT SAYS · TO · CHANNEL · TEMPLATE · WHEN`, three of them ticked, and
beneath it a template picker with a radio per row.

────────────────────────────────────────────────────────────────────────────
WHY A ROW RATHER THAN A FLAG, AND WHY ONLY FOUR COLUMNS OF THE SIX ARE STORED
────────────────────────────────────────────────────────────────────────────
Three rows are ticked and two are not, so the tick is a CHOICE and a choice is
data. What is NOT data is everything the request already holds:

  * `TO` — the applicant's own name, on `service_requests.applicant_name`;
  * the request number, on `service_requests.request_no`;
  * `CHANNEL` — **the template's own**, not this table's. A class knows what it
    is written for: an email letter is five paragraphs and an SMS is 160
    characters, and a second copy of that fact here is a second thing to keep
    in step. `notifications` publishes it beside each template row.
  * `WHEN` — **derived from the occasion, never stored.** Each of the five
    occasions fires at exactly one moment and always has; a column would be a
    copy of a constant that can drift from it, and the drawn `WHEN` column is
    served from `applicant_messages.OCCASIONS` so the two cannot disagree.

Hard rule 8's reasoning, one table over: a fact has ONE home and everything
else walks to it.

────────────────────────────────────────────────────────────────────────────
WHAT THE CLERK PICKS IS A CLASS, AND THE VERSION IS PINNED WHEN IT IS SENT
────────────────────────────────────────────────────────────────────────────
The picker draws `TEMPLATE · GROUP · CHANNEL · VARIANT · VERSION` and a version
number beside each name (`Request decided v4`). **`template_code` stores the
CLASS and `template_version_seen` stores the number the clerk was shown — as
evidence, never as a pin.**

The reason is p081's own third rule, read as an image: *"A template resolves on
three axes and falls back on two. The class of letter, the customer category
and the language — and where no variant exists for a category or a language,
the default one is used."* That is `notifications.template_service.resolve`,
which is `BR-BIL-025`'s order and the same call the dispatcher makes. Resolution
needs the applicant's language and category, and it happens when the message is
QUEUED — which for the decision row is days after capture. Pinning a version at
capture would send wording the utility had since corrected and republished, and
would make a draft pinnable, which `BR-BIL-027` forbids.

So the version travels one way only: what was SHOWN is kept so a reader can see
what the clerk was looking at, and what was SENT is stamped on `fired_*` when it
goes.

────────────────────────────────────────────────────────────────────────────
NOTHING HERE SENDS, AND NOTHING HERE QUEUES EITHER
────────────────────────────────────────────────────────────────────────────
This table is an INTENTION. `apps/customers/applicant_messages.py` is what acts
on it, and even that only reaches the outbound queue through the notifications
seam — customers may not write another module's tables. The drawing's own last
line is the standing honesty rule for every surface built on this table:
*"Everything here is queued, and nothing is sent. This product writes a row per
message and no sender picks it up — no email, no text, no print file."*
`BR-NOT-013` is why, and no docstring, screen or payload built on this table may
say otherwise.

⚠ **THE 🔒 SENSITIVE PATHS HERE ARE THE TWO MIGRATIONS, NOT THIS FILE**, and
saying so precisely is the point. `customers/0051` (migration ordering) and
`customers/0052` (the RLS policy) each carry the marker and both are named on
one row of `12-governance/09-human-review-ledger.md`. This module is an ordinary
Django model; an earlier draft claimed the protocol for it too, and `G53` was
right to object — a file that invokes the protocol and is on no guard list is a
claim nothing keeps, and widening that list is a process event for the Product
Owner rather than something a lane does on its way past.
"""

from __future__ import annotations

from django.db import models

from core.dbfields import uuid7_pk


class ServiceRequestMessage(models.Model):
    """One drawn row of `What goes out to the applicant` (`service_request_messages`).

    One row per (request, occasion) and no more — the unique constraint is the
    whole idempotency story for this table (CLAUDE.md rule 6): a clerk saving
    the block twice writes the same five rows, and a decision that fires twice
    finds `fired_at` already stamped and writes nothing.

    ⚠ **`fired_ref` IS A QUEUE ROW ID AND IS NEVER RENDERED** (B14 rule 31). It
    is here so that *"was this actually written, and which row is it"* can be
    answered from the request rather than inferred from a 200, which is
    hard-won law 1 applied to a promise made to a customer.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    request = models.ForeignKey(
        "customers.ServiceRequest",
        on_delete=models.PROTECT,
        db_column="request_id",
        related_name="applicant_messages",
    )
    #: One of `applicant_messages.OCCASIONS`. The WHEN, the default tick and
    #: which classes may render it all hang off this value and none of them is
    #: stored beside it.
    occasion = models.TextField()
    #: The drawn `SEND` tick. Defaulted from the occasion when the block is
    #: first read, and thereafter whatever the clerk left it at.
    send = models.BooleanField(default=False)
    #: The CLASS the clerk picked, or NULL for the drawn `— none chosen`.
    template_code = models.TextField(null=True, blank=True)
    #: The exact VARIANT ROW they picked — `notification_templates.id`, as a
    #: plain UUID, because a customers→notifications FK is not in B2 §2's
    #: reviewed interface set. It travels to `resolve` as its
    #: `override_template_id`, which is `BR-BIL-025`'s own word for *"this
    #: variant, not the category default"* — so an explicit pick is honoured by
    #: the mechanism that already exists rather than by a second one.
    template_id = models.UUIDField(null=True, blank=True)
    #: The version number the picker was SHOWING when they picked. Evidence,
    #: not a pin — see the module docstring.
    template_version_seen = models.IntegerField(null=True, blank=True)
    #: Stamped when the occasion fires, so a row that has already gone cannot
    #: go again. `already_handed_over` rows are stamped at capture and never
    #: queue anything at all.
    fired_at = models.DateTimeField(null=True, blank=True)
    #: `queued` · `not_sent` · `already_handed_over`. The same vocabulary
    #: `service_request_service` uses for the acknowledgement, so one screen
    #: reads one set of words.
    fired_state = models.TextField(null=True, blank=True)
    #: Why nothing went, when nothing went. A code, never a sentence.
    fired_reason = models.TextField(null=True, blank=True)
    #: The `outbound_messages` row, as a plain string: a customers→notifications
    #: FK is not in B2 §2's reviewed interface set, and the `charge_code_id`
    #: precedent one table over is the same shape for the same reason.
    fired_ref = models.TextField(null=True, blank=True)
    #: What actually rendered. It can differ from `template_code` on the
    #: decision row, where the OUTCOME picks between two classes — see
    #: `applicant_messages.OCCASIONS`.
    fired_template_code = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "service_request_messages"
        constraints = [
            models.UniqueConstraint(
                fields=["request", "occasion"], name="ux_sr_messages_request_occasion"
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "request"], name="ix_sr_messages_request"),
        ]

    def __str__(self) -> str:  # pragma: no cover - admin convenience only
        return f"{self.occasion} on {self.request_id}"


#: `DEF-CUS-10042` — the moments a clerk-added message may wait for. Each is a
#: moment this product already reaches on a request; nothing here schedules.
EXTRA_ON_SUBMIT = "on_submit"
EXTRA_ON_APPROVE = "on_approve"
EXTRA_ON_REFUSE = "on_refuse"
EXTRA_SEND_WHEN: tuple[str, ...] = (EXTRA_ON_SUBMIT, EXTRA_ON_APPROVE, EXTRA_ON_REFUSE)
#: `email` queues; `text` is stored and recorded as not queued, because no
#: service-request wording has been written for 160 characters and no SMS
#: route reaches an applicant who is not yet a customer (`BR-NOT-013`).
EXTRA_CHANNELS: tuple[str, ...] = ("email", "text")


class ServiceRequestExtraMessage(models.Model):
    """One message a CLERK added to a request's *What the customer is told*
    (`service_request_extra_messages`) — PO 2026-10-11, `DEF-CUS-10042`: *"use
    table array componnet and allow user to add more communcation to user"*.

    The automatic rows stay on `ServiceRequestMessage` and are not touched; this
    is the second list, shaped as Move-in's `move_extra_messages` already is
    (send THIS template, TO this address, by this CHANNEL, at this MOMENT).

    ⚠ **A ROW IS A PLAN UNTIL `fired_at` IS STAMPED, AND THEN IT IS A RECORD.**
    A draft's rows are replaced whole by the clerk's table; a fired row is never
    rewritten and a later save keeps it (hard rule 4's posture for anything a
    customer was told). `notification_id` is the queue row, never rendered (B14
    rule 31) and never a foreign key (notifications is another module, B2 §2).
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    request = models.ForeignKey(
        "customers.ServiceRequest",
        on_delete=models.PROTECT,
        db_column="request_id",
        related_name="extra_messages",
    )
    seq = models.SmallIntegerField()
    #: A published template's CODE (`notifications_seam.message_templates()`).
    template_code = models.TextField()
    channel = models.TextField()
    #: Where it goes. Defaults to the applicant's email; the clerk may change it.
    to_address = models.TextField()
    send_when = models.TextField()
    fired_at = models.DateTimeField(null=True, blank=True)
    #: `queued` | `not_sent` — never *sent* (`BR-NOT-013`).
    fired_state = models.TextField(null=True, blank=True)
    fired_reason = models.TextField(null=True, blank=True)
    notification_id = models.UUIDField(null=True, blank=True)  # DEFERRED FK → notifications
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "customers"
        db_table = "service_request_extra_messages"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(channel__in=EXTRA_CHANNELS),
                name="ck_sr_extra_messages_channel",
            ),
            models.CheckConstraint(
                condition=models.Q(send_when__in=EXTRA_SEND_WHEN),
                name="ck_sr_extra_messages_send_when",
            ),
            models.UniqueConstraint(fields=["request", "seq"], name="uq_sr_extra_messages_seq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "request"], name="ix_sr_extra_messages_request"),
        ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-094-BRC01 lane J (12-governance/11-change-requests.md → CR-094-BRC01 · 05-prototype/02 Accounts Menu Blueprint.pdf entry 06 p080 and p081, read AS IMAGES at scale 2 and 4 · apps/customers/applicant_messages.py · apps/customers/notifications_seam.py · apps/notifications/service_request_events.py · CLAUDE.md hard rule 1 · B14 rules 31/37/42)
# generated: 2026-09-15 by story-coder (CR-094-BRC01 lane J)
# checklist: A✔ B=deferred(the screen is lane D's — the payload and its worked example are published in this wave's conformance file) C✔ D✔ E=deferred(as B) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest under PostgreSQL — see the lane record for the red proofs
# exceptions: (1) NO CHANNEL COLUMN — the channel is the template class's own fact and notifications publishes it. (2) NO `when` COLUMN — derived from the occasion. (3) NO VERSION PIN — `template_version_seen` is evidence; resolution happens at queue time through `BR-BIL-025`'s order.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
