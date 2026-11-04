# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-014 (bounces + returned mail — the store the bad-address
#           flow has never had)   Screens: S8 · S30
# Rules:    BR-NOT-005 (the status lifecycle is forward-only; retry ×3 with
#           backoff IS the product's answer to a transient failure, which is
#           why a soft bounce may never reach this table) · BR-NOT-013
#           (`delivered` and `bounced` are PROVIDER facts and nothing in this
#           repo writes one — unchanged; this ships the STORE, not a writer of
#           provider facts) · BR-NOT-024 (print is the floor on every customer
#           document, so suppressing email never costs a consumer their bill) ·
#           BR-PAY-018 (a suppression is what a bad address earns; its PAPER
#           half already exists as `outbound_messages.held`) · BR-TEN-017 (the
#           recipient is a SNAPSHOT, never re-resolved) · CLAUDE.md hard rule 1
#           (tenant scoping — RLS FORCE, applied by migration 0020) · hard rule
#           4 (this table is NOT a financial record and is deliberately not
#           append-only — see RELEASE below) · hard rule 7 (every money action
#           writes `audit_log` — `suppression.py` does, on both doors)
# Change:   DEF-NOT-5632, 2026-09-17 — the guarantee four docstrings claim had
#           no table behind it.
# Tests:    06-backend/tests/test_def_not_5632_suppression.py
# Impacts:  apps/notifications/suppression.py (the only writer) ·
#           apps/notifications/dispatcher.py (`_selectable`) ·
#           apps/notifications/services.py (`queue_document` holds a new row)
# ───────────────────────────────────────────────────────
"""The do-not-send list — one row per ADDRESS we have been told to stop using.

╔══════════════════════════════════════════════════════════════════════════╗
║  THIS TABLE DOES NOT DECIDE ANYTHING. IT RECORDS A DECISION MADE         ║
║  ELSEWHERE, AND REFUSES EXACTLY ONE THING ABSOLUTELY.                    ║
╚══════════════════════════════════════════════════════════════════════════╝
The policy that decides WHICH channels are undeliverable already exists and is
built: `apps/runbooks/definitions/undeliverable_contacts.py` (runbook 22), whose
own words are *"No column records a suppression, so '31 suppressed' is what this
run WOULD suppress. The KPI tile says To suppress until a writer is bound."*
**This is the writer it was waiting for, and it is not a second policy.**

The split, stated here because getting it wrong is how a repo ends up with two
answers to one question:

* **THE THRESHOLD IS THE RUNBOOK'S AND IS NOT IN THIS MODULE.** *Suppress after
  2 hard bounces, or 1 returned letter* is `RB-122`'s card, it is tenant-tunable
  (`suppress_after_bounces`), and **no count, window or threshold appears
  anywhere in `suppression.py` or in this file.** A lane that adds a
  `count >= 2` here has created the second source of truth this design exists to
  avoid.
* **WHAT A COMPLAINT AND AN UNSUBSCRIBE MEAN IS THIS MODULE'S AND IS ALREADY
  RULED**, in `models.py`, in its own words: of a complaint, *"Like a hard bounce
  it suppresses — but for a different reason"*; of an unsubscribe, *"They appear
  on the blocked-addresses screen instead."* Neither is a threshold question and
  the runbook never claimed one — `HARD_KINDS` there is bounces, failed texts and
  returned post, and a complaint is on none of them. A person clicking *this is
  spam* is an instruction, not evidence to be accumulated.
* **THE ONE THING REFUSED ABSOLUTELY IS A SOFT BOUNCE**, and it is refused at the
  WRITER rather than left to callers (`suppression.suppress`). See below.

────────────────────────────────────────────────────────────────────────────
WHY THIS IS KEYED BY ADDRESS AND IS NOT A COLUMN ON `customers.Contact`
────────────────────────────────────────────────────────────────────────────
It was very nearly the latter. `customers.Contact` carries `email` and `phone`,
the `suppress_channel` port is declared with `owning_module="customers"`, and
`apps/customers/runbook_ports.py` says in as many words that the missing thing is
*"a contact channel marked undeliverable, dated"*. **Three reasons it is not
that, and the second is the load-bearing one:**

1. **A write from here would be a CROSS-MODULE WRITE, which DB-16 forbids
   outright.** The writer of a suppression is the provider-feedback path, which
   lives in this module; a column on `customers.Contact` would have notifications
   writing a customers table on every webhook. The port pattern exists precisely
   so a RUNBOOK can cause such a write through customers' OWN service — it does
   not hand notifications a write path, and binding `suppress_channel` to a
   writer in this module would make `BR-RBS-022` false (*a port maps to exactly
   ONE service function in the OWNING module*).

2. **THE TWO FACTS HAVE DIFFERENT KEYS, AND A CONTACT-KEYED STORE CANNOT HOLD
   THE ONE THE PROVIDER REPORTS.** What SendGrid or Postmark tells us is about a
   MAILBOX. Measured against this product:
     * `OutboundMessage.recipient_address` is already the delivery key — a
       snapshot TextField, *"the address as it stood when the row was written"*,
       never re-resolved (`BR-TEN-017`). The rail is address-keyed end to end.
     * **The product sends to addresses that have no `Contact` row at all.** A
       staff failure goes to *"the user who started the action, plus all System
       Admins"* (`BR-NOT-021`, `staff_recipients.py`), and *Send test to me*
       queues to the signed-in user's own address (`rule_service.queue_test`).
       A hard bounce on a System Admin's mailbox has nowhere to go in a
       contact-keyed store.
     * **One address sits on many contacts** — a landlord on forty units, a
       family sharing one mailbox. A per-contact column records the same dead
       mailbox N times and can disagree with itself; N rows cannot.

3. **BOTH FACTS ARE REAL AND THIS CLOSES ONLY ONE OF THEM.** ⚠ **`DEF-RBS-4331`
   IS NOT CLOSED BY THIS TABLE AND A LATER LANE MUST NOT READ IT AS CLOSED.**
   *This person's email channel is undeliverable, dated* is a statement about a
   CUSTOMER that belongs on their record, drives the fall-back ladder and is
   customers' own design decision — `apps/customers/runbook_ports.py`, verbatim:
   *"A column plus its rule is customers' design decision, not a runbook lane's."*
   *Do not send to this address* is a statement about a RAIL. This is the second
   one. The first is still owed.

**NO SEAM IS NEEDED AND NONE IS ADDED.** Every input to a suppression is already
in this module: the outcome is this module's own status vocabulary and the
address is this module's own column. A seam with nothing to resolve would be a
file claiming a boundary that is not crossed (hard-won law 1).

────────────────────────────────────────────────────────────────────────────
⚠ THIS TABLE IS PER TENANT AND THE PROVIDER'S LIST IS NOT — `DEF-NOT-5639`
────────────────────────────────────────────────────────────────────────────
**The tenant scoping below is correct and is not the thing to change.** Every
row pairs a consumer's address with the fact that they bounced or reported this
utility as spam; that is utility A's PII (`BR-CUS-045`) and hard rule 1 is not
optional.

**But the Product Owner ruled on 2026-09-17 that the PLATFORM holds the provider
account** — *"our account - we will provdie servcie to utilities as platform
provider"* — so ONE SendGrid or Postmark account serves every utility, and **the
provider keeps its own suppression list against that shared account.** When
utility A hard-bounces an address, the provider suppresses it for the whole
account, and a later message from utility B to the same consumer comes back
`dropped` — which `models.py` already defines as *"SendGrid refusing to send
because the address is on ITS OWN suppression list"*. Utility B's blocked-
addresses screen holds no row and truthfully reports **nothing blocked**, over a
message that will never arrive. That is hard-won law 7's *reporting zero over a
scope it silently excludes*, and **no gate here could see it** — nothing crosses
a tenant boundary in the database; the state lives at the provider.

It is FILED (`DEF-NOT-5639`) rather than left in this docstring, because a
finding recorded only in the file you happen to be in is a finding nobody can
count. The commercial answer — SendGrid subusers (Pro plan or above) or a
Postmark Server per utility (no extra cost) — is measured in the decision log
and is the Product Owner's to make.

────────────────────────────────────────────────────────────────────────────
WHY A SECOND TABLE AND NOT A COLUMN ON `outbound_messages`
────────────────────────────────────────────────────────────────────────────
The same argument `InAppMessage` already makes one file over, in the same shape:
`outbound_messages` is one row per DOCUMENT per channel, and a suppression is a
standing fact about an ADDRESS that outlives every document sent to it and
governs documents not yet written. A column on the queue row could only ever say
*this one message was blocked*, which is the consequence rather than the fact,
and it would have to be re-derived onto every future row by whoever remembered.

────────────────────────────────────────────────────────────────────────────
RELEASE, AND WHY THIS TABLE IS NOT APPEND-ONLY
────────────────────────────────────────────────────────────────────────────
Hard rule 4 names issued invoices, invoice lines, payments and journal entries.
**This is none of them** — no money moves and no balance changes (`BR-PAY-018`
says as much of its own half: *"balances unaffected"*). So a release is allowed
to be a state change rather than a reversing row.

**It is still not an UPDATE that forgets.** A release stamps `released_at`,
`released_by` and `released_note` and **the row stays**, because the question a
utility will actually be asked is *why did this customer stop getting email in
March* and the answer must survive `audit_log`'s retention pruning — the cost
`OQ-1340` is open about on the payments correction path. The unique constraint is
therefore PARTIAL, on `released_at IS NULL`: **at most one ACTIVE suppression per
address per channel, and every released one kept as history.** Re-suppressing a
released address writes a NEW row, so the third time an address goes bad there
are three rows and a clerk can see the pattern.

────────────────────────────────────────────────────────────────────────────
WHAT IS DELIBERATELY NOT A COLUMN — read this before adding one
────────────────────────────────────────────────────────────────────────────
* **No threshold, count, window or `failures_seen`.** See the top of this file.
* **No `contact_id` and no FK to `customers`.** The address is the key precisely
  because it outlives and out-spans any one contact, and a nullable FK would
  invite a join that answers the wrong question on the rows that matter (staff
  and test addresses, which have no contact).
* **No `expires_at`.** *Re-enable when the contact is updated* is `RB-122`'s own
  declared parameter with **nothing to re-enable and nothing to watch**, recorded
  as blind spot 3 of 3 with its figure. It is now re-enable-able BY HAND — that
  is `release()` — and an automatic expiry is a policy nobody has ruled. Adding a
  date here would be choosing one.
* **`suppressed_by` / `released_by` are plain UUIDs, not FKs to `identity.User`.**
  B2 §2's cross-module FK set is a REVIEWED set and a lane does not add to it in
  passing; `OutboundMessage.returned_by` and `InAppMessage.user_id` are the
  precedent sitting in the same module, for the same reason.
"""

from __future__ import annotations

from django.db import models
from django.db.models import Q

from core.dbfields import uuid7_pk

# ── why an address is on the list ──────────────────────────────────────────
#
# CODES, not sentences, for `held_reason`'s reason: *"A CODE, because the
# dashboard groups on it."* The clerk-facing words are the catalogue's, in
# eleven languages; a sentence in this column would be English in a database.
#
# ⚠ THERE ARE THREE AND THEY ARE NOT INTERCHANGEABLE. A clerk deciding whether
# to ring a customer needs to know which of these happened: a hard bounce is a
# mistyped or dead address they can fix, a complaint is a person who does not
# want the mail, and an unsubscribe is a person who pressed a button we gave
# them. Folding them into one `blocked` would make the one screen built to
# explain this unable to.

#: The mailbox does not exist. `models.STATUS_BOUNCED_HARD`.
REASON_HARD_BOUNCE = "hard_bounce"
#: The consumer marked the message as spam. `models.STATUS_COMPLAINED`.
REASON_COMPLAINT = "complaint"
#: The consumer used the unsubscribe link. `models.STATUS_UNSUBSCRIBED`.
#: ⚠ NOT A FAULT, and the one of the three that must never be presented to a
#: clerk as something to repair (`models.ATTENTION_STATUSES` leaves it off the
#: failures list for exactly this reason).
REASON_UNSUBSCRIBED = "unsubscribed"
#: A person put this address on the list by hand. There is no writer for it
#: today and it is NOT offered on any screen — it exists so that the column's
#: vocabulary is complete when one arrives, and `suppression.suppress` accepts
#: it, so a later lane adds a button and not a value.
REASON_MANUAL = "manual"

REASONS = (REASON_HARD_BOUNCE, REASON_COMPLAINT, REASON_UNSUBSCRIBED, REASON_MANUAL)

#: ══ THE ONLY TWO CHANNELS AN ADDRESS ON THIS LIST MAY BE FOR ══════════════
#: PO ruling 2026-10-02, verbatim: *"A · Email and text only - this correct"*,
#: shown Dana asking us to stop emailing `dana@example.com`. So `address` holds
#: an email address or a phone number and never a postal one; a POSTAL address
#: is refused BY NAME in `suppression.suppress` (paper keeps `BR-PAY-018`'s
#: bad-address flag), and `in_app` / `portal` are refused too — they have no
#: address a person could ask us to stop using.
#:
#: Literal strings rather than `models.CHANNEL_EMAIL` / `CHANNEL_SMS` because
#: `G85` reads this tuple with `ast` and permits the `address` column ONLY while
#: it is exactly these two; a test pins them to the `models` constants.
#: **Widening it is a new PO ruling and turns `G85` red** — hard rule 8.
SUPPRESSIBLE_CHANNELS: tuple[str, ...] = ("email", "sms")

#: ⚠ **`soft_bounce` IS NOT ON THAT TUPLE AND MUST NEVER BE ADDED.** It is not
#: an oversight and it is not a gap — it is the guard this whole slice exists
#: around. `models.py` states it: a soft bounce is *"RETRIED and NEVER
#: suppresses"*, and `BR-NOT-005`'s retry ×3 is the product's own answer to a
#: transient failure. A mailbox full on Tuesday is not a dead address, and
#: suppressing on it takes a real consumer's only working channel away.
#: `suppression.suppress` refuses it BY NAME rather than by absence from this
#: tuple, so the refusal carries a sentence a person can read.


class SuppressedAddress(models.Model):
    """One address, on one channel, that this utility must not send to.

    Written ONLY by `apps/notifications/suppression.py` — one writer, like
    `services.queue_document` is the one writer of `outbound_messages` (B1).
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")

    # ── what is suppressed ──────────────────────────────────────────────
    #: One of `SUPPRESSIBLE_CHANNELS` — email or SMS, and nothing else. The
    #: table is channel-keyed rather than email-only because the same fact
    #: arrives on SMS (a disconnected number is a hard bounce by another name).
    #: ⚠ **PRINT IS REFUSED, AND SO IS EVERY OTHER CHANNEL (PO 2026-10-02).**
    #: This comment read *"PRINT is lawful here too"* until then, which made
    #: `address` able to hold a postal address — a home hard rule 8 does not
    #: allow (`DEF-NOT-8538`). Paper keeps `BR-PAY-018`'s bad-address flag.
    channel = models.TextField()
    #: An email address or a phone number, NORMALISED for matching — never a
    #: postal address (see `SUPPRESSIBLE_CHANNELS`). See `suppression.
    #: normalise_address` for what that means and why it is a judgment rather
    #: than a fact. The queue row keeps its own snapshot untouched
    #: (`BR-TEN-017`): this column exists to be MATCHED against, never to be
    #: sent to, and the two must not be confused.
    address = models.TextField()

    # ── why ──────────────────────────────────────────────────────────────
    #: One of `REASONS`. A plain TextField with no CHECK constraint and no enum
    #: type, exactly as `outbound_messages.status` is — migration 0018 states
    #: the module's reasoning: the vocabulary lives in Python, so adding a
    #: lawful value is not a DDL change.
    reason = models.TextField()
    #: The provider's own sentence, or the rule that decided it, kept for the
    #: person who has to explain this to a customer. NULL when nobody said
    #: anything — distinguishable from an empty string, the `unavailable_reason`
    #: discipline one table over.
    reason_detail = models.TextField(null=True, blank=True)
    #: WHICH message earned it. Same-module FK, so no reviewed-set question
    #: arises. Nullable and `SET_NULL`: a suppression outlives the document that
    #: caused it, and a manual entry has no document at all.
    source_message = models.ForeignKey(
        "notifications.OutboundMessage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="source_message_id",
        related_name="+",
    )

    # ── when, and by whom ────────────────────────────────────────────────
    #: A PARAMETER and never a clock read (`BR-TEN-043`) — nothing in this
    #: module reads a wall clock and G6 greps for it.
    suppressed_at = models.DateTimeField()
    #: NULL for an automated write. A plain uuid — see the docstring.
    suppressed_by = models.UUIDField(null=True, blank=True)

    # ── the way back ─────────────────────────────────────────────────────
    #: NULL = ACTIVE. This is the column the partial unique constraint and every
    #: read in `suppression.py` turn on, and it is why a release keeps history
    #: instead of deleting a row.
    released_at = models.DateTimeField(null=True, blank=True)
    released_by = models.UUIDField(null=True, blank=True)
    #: What the person said when they let it through — *"typo, corrected on the
    #: account"*. Free text on purpose: this is the one field in the table that
    #: is a human's own words, and a code list would make a clerk pick the
    #: nearest wrong one.
    released_note = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "suppressed_addresses"
        indexes = [
            # The blocked-addresses list: this tenant's ACTIVE suppressions,
            # newest first. Partial, like `ix_outbound_msgs_dispatch` — the
            # released rows are history and the screen's default view is not
            # about them.
            models.Index(
                fields=["tenant", "-suppressed_at"],
                condition=Q(released_at__isnull=True),
                name="ix_suppressed_addrs_active",
            ),
            # The history of ONE address — "has this happened before?" — which
            # is the question a clerk asks before releasing a typo for the
            # second time. Not partial: released rows are the whole point of it.
            models.Index(
                fields=["tenant", "channel", "address"],
                name="ix_suppressed_addrs_address",
            ),
        ]
        constraints = [
            # ⚠ AT MOST ONE **ACTIVE** SUPPRESSION PER ADDRESS PER CHANNEL, and
            # unlimited released ones. Two things at once, both deliberate:
            #
            #   * it is the IDEMPOTENCY guarantee (CLAUDE.md rule 6) for a
            #     feedback webhook that is delivered twice — the second write
            #     finds the row already here and the database refuses a
            #     duplicate, which is the only guarantee that survives a retry
            #     that never called our code twice at all;
            #   * and it is what lets a release KEEP the row. A plain unique on
            #     (tenant, channel, address) would have forced a release to
            #     DELETE, destroying the record of why a customer stopped
            #     getting email — and `audit_log` is pruned, so there would
            #     eventually be no answer anywhere (the cost `OQ-1340` is open
            #     about on the payments correction path).
            #
            # It also indexes exactly the lookup the dispatcher makes, so no
            # second index is declared for it: a second index on the same
            # leading columns is write cost for nothing (`outbound_messages`
            # makes the same call in its own Meta).
            models.UniqueConstraint(
                fields=["tenant", "channel", "address"],
                condition=Q(released_at__isnull=True),
                name="uq_suppressed_addrs_active",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - debugging aid
        state = "released" if self.released_at else "active"
        return f"{self.channel}:{self.address} ({self.reason}, {state})"


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-NOT-5632 (12-governance/10-defect-log.csv) · apps/notifications/models.py STATUSES + PROVIDER_OUTCOME_STATUSES + the hard/soft paragraph · apps/runbooks/definitions/undeliverable_contacts.py (the policy this binds a writer to) · apps/customers/runbook_ports.py (why `suppress_channel` is NOT this) · 04-docs/02-decisions/02-database-design-brief.md DB-16 + §3 (the policy template)
# generated: 2026-09-17 by an AI lane (SendGrid/Postmark gap 4 — the do-not-send list)
# checklist: A✔ B=deferred(no frontend half — see exceptions (3)) C✔ D✔ E=deferred(as B) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: pytest tests/test_def_not_5632_suppression.py — every case proved RED first against this file; see the test module's own trailer for each sabotage and the failure it printed
# exceptions: (1) NOTHING WRITES A SUPPRESSION AUTOMATICALLY TODAY, because `BR-NOT-013` still holds and no provider adapter with a feedback door exists — `suppression.record_provider_outcome` is the contract an adapter maps onto and its only callers today are the tests and the release API. Stated out loud rather than implied (hard-won law 2: built is not wired). The READ half IS live and wired from this commit: the dispatcher consults the list on every cycle. (2) `DEF-RBS-4331` IS NOT CLOSED — the customers-side "this contact's channel is undeliverable, dated" is a different fact with a different key and is still owed; see the docstring. (3) NO SCREEN. The blocked-addresses view the PO asked for ("Release") needs a blueprint check first (B14 rules 41/42 — a screen is built from the drawing AS AN IMAGE) and no lane has checked whether a Notifications blueprint PDF exists on any ref. The API both halves of that screen need is served; the screen is filed as DEF-NOT-5637.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
