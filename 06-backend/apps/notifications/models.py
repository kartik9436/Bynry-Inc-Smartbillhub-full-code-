# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-001 (`outbound_messages` — the platform-wide queue table and
#           the only send path)   Screens: S8 · S30 · S35
#           Other stories that USE this table are named in the docstring, not
#           here — G10 reads a Trace US-ID as "this file ships that story's
#           test cases", and this slice ships schema.
# Rules:    BR-NOT-005 (EVERY email/SMS/print from ANY module is written to the
#           outbound table first — never sent inline; the dispatcher on top
#           sends in tenant-config batches; statuses queued→sent→delivered/
#           failed/bounced; retry ×3 with backoff) · BR-BIL-016 (one delivery
#           record per document per channel) · BR-BIL-036 (PRINT is the primary
#           channel; email/SMS are notifications of the amount; an account with
#           NO email address is normal, not an exception) · BR-NOT-006 (the
#           template pinning tuple includes the language variant) ·
#           BR-TEN-017 (an issued document is never re-rendered — the recipient
#           is snapshotted at queue time) · BR-PAY-024 (receipts ride this
#           queue) · CLAUDE.md rule 1 (tenant scoping; RLS FORCE) · rule 6
#           (idempotency — a re-emitted source event never queues a second copy)
# Change:   CR-048 wave B task B6, 2026-08-30 — TWO NULLABLE COLUMNS on
#           `outbound_messages` (`event_key`, `rule_suppressed_channels`) and a
#           partial index over the first, so per-event counts are arithmetic
#           over a stamped fact instead of a reverse map. Plus a NINTH source
#           kind, `move` (task B10), whose source is a move RECORD and which
#           gets NO print floor — BR-NOT-024 names four kinds and a move is
#           none of them. Migration 0016; the rule-6 key is untouched.
# Tests:    06-backend/tests/test_us_not_001_outbound_queue.py ·
#           06-backend/tests/test_us_not_001_outbound_isolation.py ·
#           06-backend/tests/test_cr048_b6_b10.py (CR-048 B6 + B10)
# Impacts:  apps/billing (a row per bill per channel at release; the per-run
#           delivery dashboard reads them) · apps/payments (receipts, collection
#           notices, plan notices) · apps/reports + apps/ledger (scheduled-report
#           and bookkeeper rows, W6) · the dispatcher, which will be this
#           module's and is the ONLY writer of batch_id / attempts /
#           provider_* / sent_at.
#           Their US-IDs are DELIBERATELY not written here — G10 reads any
#           US-ID inside this block as "this file ships that story's test
#           cases", including on an Impacts line. It caught exactly that on the
#           first version of this header. The IDs are in the docstring below,
#           where the gate reads prose rather than a claim; `apps/billing/
#           models.py` and `late_fee.py` each record making the same mistake.
# ───────────────────────────────────────────────────────
"""notifications models — `outbound_messages`, the PLATFORM-WIDE outbound queue.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — the idempotency key on this table is a
CLAUDE.md 🔒 path (rule 6), and every row carries a customer's name, postal
address, phone number or email address. AI-authored 2026-08-11 under the PO
ruling of 2026-08-09; rows in 12-governance/09-human-review-ledger.md.

WHY ONE TABLE, AND WHY IT LIVES HERE. B2 Addendum **r12 #16** (PO-approved
2026-08-08): *"`outbound_messages` is PLATFORM-WIDE (BR-NOT-005): one table for
email + SMS + print across ALL modules; module writers insert; ONLY the
dispatcher service sends; batch size/cadence tenant-config; provider adapters
(BYO mailbox, transactional ESP, Twilio) behind one seam."* r16 #6 says the
same thing from the other end: *"delivery queue = ONE table = outbound_messages
→ notifications"*. The shape of a row is fixed by **r10 #8**: *"one row per bill
× channel; status queued|sent|delivered|failed|bounced; batch id; provider
response"*, which BR-NOT-005 generalises from bills to every message the
platform emits.

The B1 module boundary has ONE ruled exception and this table is it: writers in
billing, payments, reports and ledger INSERT here (r16 #7 adds it to the §2
reviewed interface register). They insert and nothing else. Advancing a status,
stamping a batch, recording a provider response — all of that belongs to the
dispatcher, which is US-NOT-002 and is NOT in this slice.

STORIES THAT USE THIS TABLE AND ARE NOT SHIPPED HERE, named in prose because a
Trace-header citation is a completion claim (`apps/billing/models.py` records
learning this the hard way, and `late_fee.py` records making the same mistake
before it): US-NOT-002 the dispatcher · US-NOT-003 channel routing and the
provider seam · US-NOT-004 the Settings dispatch home · US-NOT-013/014 the
delivery-ops dashboard, re-queue and returned-mail marking · US-BIL-023 the
per-bill queue write at release · US-BIL-024 the per-run dashboard. This file
ships the TABLE they all need and stops.

────────────────────────────────────────────────────────────────────────────
THE IDEMPOTENCY KEY — `UNIQUE (tenant, source_type, source_id, channel,
copy_no)` — and why it is five columns rather than a text key
────────────────────────────────────────────────────────────────────────────
CLAUDE.md rule 6 and US-NOT-001 TC-5 state the requirement in the same words:
a re-emitted source event (a job retry, a re-run release, a webhook delivered
twice) must never produce a second row. US-NOT-001 §5 names the key itself —
*"unique key on source ref × channel"* — and r12 #17 leaves its MECHANICS to
the Eng-Lead. These five columns are that mechanic.

`source_type` + `source_id` + `channel` is "source ref × channel" verbatim, and
every one of them is a column the row has to carry anyway. That is the whole
argument for this shape over the text `idempotency_key` column `bill_runs`
uses: a text key is computed by the caller, and a caller that computes it
wrongly duplicates silently. Here there is nothing to compute. A second release
of the same bill to the same channel is refused by the database whether or not
the writer remembered anything.

`copy_no` (0 by default) is the one deliberate door. Two ratified behaviours
would otherwise contradict each other:

  * US-NOT-001 TC-5 — a re-emitted event must NOT create a row.
  * US-NOT-011 §5 — a staff **re-send** of a receipt *"[creates] new queue
    rows, audited"*, and US-BIL-024 TC-4 does the same for a deliberate re-send
    of a delivered bill.

Automatic writers always leave `copy_no = 0`, so a replay collides. A human
asking for another copy takes `copy_no = 1, 2, …`, which is a different key and
a new row — and the number itself records how many copies were ever asked for,
which no boolean flag would. Note what is NOT a new row: the dashboard
**re-queue** action (US-NOT-013 / US-BIL-024 TC-3) sets an existing row's
status back to `queued` — same row, same `copy_no`.

`source_id` is NOT NULL on purpose. A NULL anywhere in a unique key means no
uniqueness at all in PostgreSQL, so a nullable source column would quietly
switch the guarantee off for exactly the rows nobody was watching. US-NOT-001
§5 marks source ref *required*, so this costs nothing.

It is a plain uuid rather than a foreign key because the source is polymorphic —
an invoice, a payment, a notice, a plan, a report. B2 r16 #5 keeps *"polymorphic
source_id integrity"* on the Eng residue list (O-4); it is not resolved here,
and this docstring says so rather than implying the column is enforced.

────────────────────────────────────────────────────────────────────────────
THE MISSING EMAIL ADDRESS — normal, and RECORDED rather than dropped
────────────────────────────────────────────────────────────────────────────
BR-BIL-036, from the PO's closure of OQ-091 on 2026-08-10:

    PRINT is the primary delivery channel; email and SMS are NOTIFICATIONS of
    the amount, not a replacement for the document. […] An account with NO
    email address is normal, not an exception — delivery must never assume one
    exists, and such an account still bills, still renders and still dispatches.

Two consequences are built into the columns.

**The print row never depends on the email row.** Rows are independent: one per
channel, each with its own address snapshot and its own status. Nothing about
an account's missing email can reach the `pdf_print` row, because they share no
column that could carry the failure.

**An absent address is stated, never implied by silence.** `recipient_address`
is nullable and `unavailable_reason` says why it is null, and the CHECK
constraint `ck_outbound_msgs_address_or_reason` makes exactly one of the two
present on every row. So the third possibility — the row that quietly has
neither, or the message that was never queued at all and left no trace — is not
a thing this table can hold. The dispatch home (US-NOT-004) and the per-run
dashboard (US-BIL-024) can then answer "982 email rows, 142 with no address on
file" instead of showing 982 rows and an unexplained gap.

What this file does NOT decide: whether the dispatcher skips a row carrying an
`unavailable_reason`, and what happens if the customer supplies an address
later. Both belong to US-NOT-002, are not written anywhere yet, and are named
in the migration's `exceptions:` line so the gap is findable rather than
assumed handled (hard-won law 1).

────────────────────────────────────────────────────────────────────────────
DISPOSITION OF THE BASE B2 `notifications` TABLE (field-map N-6, Eng-Lead 🔒)
────────────────────────────────────────────────────────────────────────────
The notifications field map records the open item: *"base B2
`notification_templates` (code/channel/subject/body) predates the r8 designers
… and base `notifications` predates r12 #16 `outbound_messages` — column/table
disposition unresolved in the addenda … Eng-Lead 🔒 at migration authoring."*

Disposed here: **`outbound_messages` REPLACES the base `notifications` table,
which is not built.** r12 #16 says one table across all modules and r16 #6 says
"delivery queue = ONE table"; building both would be two tables for one job and
the base table's five columns are a strict subset of this one's. Its
`account_id` FK, `template_id`, `status` and `sent_at` all survive here.

`notification_templates` is NOT disposed of and NOT built: it is EP-NOT-02's
(template designers, versions, language variants), a different slice. That is
why `template_id` / `template_version` / `template_code` / `template_language`
are plain columns rather than foreign keys — the B11 F-3 deferred-FK convention
this repo already uses, and the same call `apps/billing/models.py` made for
`invoices.template_id`. A pin that waits for its table is a pin that is missing
exactly when it is needed.

────────────────────────────────────────────────────────────────────────────
WHAT THIS TABLE IS NOT
────────────────────────────────────────────────────────────────────────────
There is no dispatcher, no provider adapter and no send path in this module.
`batch_id` is a plain uuid and there is no batch table: a batch is MINTED by
the dispatcher at handoff (US-NOT-002 §5, r10 #8 "batch id"), and neither r10
#8 nor r12 #16 nor the field map ever names a batch TABLE. A table nothing
writes is the defect hard-won law 2 exists to prevent.

The dispatcher-owned columns (`batch_id`, `attempts`, `next_attempt_at`,
`last_attempt_at`, `sent_at`, `provider_reference`, `provider_response`,
`last_error`) exist here because US-NOT-001 §5 puts them on the row — *"counters
+ batch ref + provider payload … written by dispatcher only"*. They ship empty
and stay empty until US-NOT-002 lands.

Also deliberately absent: the returned-mail / held markers (US-NOT-014,
BR-PAY-018) and the tenant dispatch settings (batch size, quiet hours,
channel-activation flags — US-NOT-004, BR-TEN-041). Both are their own stories.

**PARTITIONING IS A KNOWN, REPORTED DEVIATION.** B2 r16 #1 and NFR-24 say
`outbound_messages` is *born partitioned* (monthly RANGE, and
`core/partitioning.py` already registers it with `key_column="created_at"`).
This table ships UNPARTITIONED, because PostgreSQL requires every unique
constraint on a partitioned table to contain the partition key: adding
`created_at` to the key above would mean the same bill re-released in a later
month lands in a different partition and is accepted as a new row — i.e. hard
rule 6 would be switched off to satisfy an NFR. The hard rule wins, and the
deviation is stated in the migration's `exceptions:` line, not taken quietly.
Making both true needs a decision that is not in any signed document (hash
partitioning on `tenant_id`, which is monthly-partitioning's opposite; or an
unpartitioned companion key table) — so it is REPORTED for the PO/Eng-Lead
rather than chosen here.
"""

from datetime import time

from django.db import models
from django.db.models import F, Q

from core.dbfields import uuid7_pk

#: r12 #16 — "one table for email + SMS + print". The v1 channel vocabulary is
#: US-NOT-003 §4's, verbatim: pdf_print is live, email dispatch defers to W6
#: (OQ-073 closed), SMS dispatch to v1.1 behind the Twilio seam. Rows for the
#: deferred channels are written from day one; only the SEND defers.
#: BR-NOT-010: door-hanger is NOT a channel until v2 and is absent on purpose.
CHANNEL_PRINT = "pdf_print"
CHANNEL_EMAIL = "email"
CHANNEL_SMS = "sms"
#: ⚠ A FOURTH CHANNEL ARRIVED 2026-08-17 (CR-009 fourth ruling set), and it is
#: the FIRST one this platform can actually deliver on.
#:
#: PO verbatim: *"We can confirm it whether it is working on not if we get in
#: APp Notifcaition, which does not require any integration and it is proof that
#: notification is working"*.
#:
#: Every other channel here waits on a third party — email on an SMTP-vs-ESP
#: decision nobody has taken, SMS on Twilio, print on a fulfilment vendor
#: (BR-NOT-013: *"no provider adapter exists or is coming on ANY channel, print
#: included"*). **In-app waits on nobody**, because the recipient's mailbox is a
#: table in this database and the "provider" is this application. So a message
#: that arrives in a staff member's inbox is proof that the queue, the rule, the
#: template resolution, the rendering and the dispatcher all work end to end —
#: which is the whole reason the PO asked for it first.
#:
#: BR-NOT-010 named three v1 channels and is NOT contradicted: it kept
#: door-hanger out until v2 and speaks about the CUSTOMER channels a document
#: goes out on. This one carries a message to a signed-in USER of the utility,
#: inside the product. BR-NOT-019 is the rule that adds it; it is written down in
#: 04-docs/05-modules/10-notifications/02-business-rules.md rather than only
#: here, because a channel that exists only in a comment is hard-won law 1.
CHANNEL_IN_APP = "in_app"
#: ⚠ A FIFTH CHANNEL ARRIVED 2026-09-07 (`CR-084`), AND IT IS THE FIRST ONE A
#: CUSTOMER — rather than a member of the utility's own staff — CAN ACTUALLY BE
#: REACHED ON.
#:
#: PO verbatim, pointing at the greyed-out *Customer portal* row on Settings →
#: Notifications → Bill ready: *"can you swithc on this now - Customer portal"*.
#:
#: The sentence it replaced was TRUE WHEN IT WAS WRITTEN — *"there is no
#: customer portal in this product"* — and stopped being true when `CR-068`
#: shipped one and `CR-082` seeded its self-service content. Nobody went back to
#: the refusal, which is hard-won law 2's mirror exactly: a hold with a clock in
#: it, and landing the screen and releasing the control that points at it are
#: two acts of which only the first feels like the work.
#:
#: **What a portal delivery IS, in one sentence:** the document is published to
#: the customer's own portal, where they read it under *Your bills* and
#: *Documents and letters* after signing in — `CWP-027` and `CWP-031`, both
#: shipped, both already reading THIS table through
#: `correspondence_reads.account_correspondence`.
#:
#: Like `in_app` and unlike the other three, it waits on nobody: no vendor
#: decision, no per-tenant connection, no credentials, no cost. The "provider"
#: is this application, and `portal_delivery.deliver_batch` is its adapter.
#:
#: BR-NOT-010 named three v1 channels and is AMENDED rather than contradicted:
#: its live clause — *door-hanger is NOT a channel until v2* — is untouched and
#: still enforced. `BR-NOT-1031` is the rule that adds this one; it is written
#: down in 04-docs/05-modules/10-notifications/02-business-rules.md rather than
#: only here, because a channel that exists only in a comment is hard-won law 1.
CHANNEL_PORTAL = "portal"
CHANNELS = (CHANNEL_PRINT, CHANNEL_EMAIL, CHANNEL_SMS, CHANNEL_IN_APP, CHANNEL_PORTAL)

#: r10 #8 / BR-NOT-005, verbatim. Forward-only: the re-queue ACTION
#: (US-NOT-013 / US-BIL-024) is the only reset, and enforcing that is the
#: dispatcher's job — this file records the vocabulary, not the transitions.
STATUS_QUEUED = "queued"
STATUS_SENT = "sent"
STATUS_DELIVERED = "delivered"
STATUS_FAILED = "failed"
#: ⚠ **LEGACY SINCE 2026-09-17, AND DELIBERATELY STILL LAWFUL — `DEF-NOT-5626`.**
#: It was the ONLY word this table had for a bounce, and it collapses the two
#: things a bounce can be. Nothing in this repo has ever written it
#: (`BR-NOT-013`: *"`delivered` and `bounced` can never be written by anything in
#: this repo"* — both are provider facts and no adapter existed), so on this
#: deployment no row carries it and **no row was rewritten to one of the two
#: values below.** That is the honest answer rather than the tidy one: a row
#: reading `bounced` states *the provider bounced this and we do not know which
#: kind*, and guessing it into `bounced_hard` would suppress a live consumer's
#: address on no evidence. New writers use the two below; this value stays
#: readable, stays on the failures list, and is never written again.
STATUS_BOUNCED = "bounced"

# ══════════════════════════════════════════════════════════════════════════
#  THE FOUR NORMALISED PROVIDER OUTCOMES — ADDED 2026-09-17 (`DEF-NOT-5626`)
# ══════════════════════════════════════════════════════════════════════════
#
# SendGrid and Postmark each report what happened to an email, in their own
# words. **Neither vocabulary may escape its adapter** — the product sees one
# fixed set, and this is it:
#
#     SendGrid    delivered · bounce(+type) · deferred · dropped ·
#                 spamreport · unsubscribe
#     Postmark    Delivery · Bounce(+hard/soft Type) · SpamComplaint ·
#                 SubscriptionChange
#     ─────────── normalised ────────────────────────────────────────────────
#     delivered · bounced_hard · bounced_soft · complained · unsubscribed ·
#     failed
#
# Two of the six already existed (`delivered`, `failed`). The four here are the
# rest. **Adding them is NOT the adapters** — no adapter exists yet and
# `BR-NOT-013` still holds: nothing in this repo writes a provider fact. This
# slice ships the WORDS, so that the adapters have somewhere to put an answer
# instead of inventing a vocabulary each.
#
# ──────────────────────────────────────────────────────────────────────────
#  WHY HARD AND SOFT ARE TWO VALUES AND MUST NEVER BE FOLDED BACK INTO ONE
# ──────────────────────────────────────────────────────────────────────────
#
# **They demand OPPOSITE actions, and getting it wrong costs a real consumer
# their bill.**
#
#   * A **HARD** bounce means the mailbox does not exist — the domain has no
#     such user, the account was deleted, the address was mistyped at sign-up.
#     Sending again cannot succeed and the provider will not keep accepting it;
#     enough of them and OUR sending reputation degrades for every utility on
#     the platform. So a hard bounce **SUPPRESSES the address** and the
#     consumer keeps getting their bill on paper.
#   * A **SOFT** bounce means the mailbox is full, the server is busy, or the
#     message was greylisted. It is TEMPORARY. So a soft bounce is
#     **RETRIED and NEVER suppresses** — `BR-NOT-005`'s retry ×3 with backoff
#     is already the product's answer to a transient failure, and
#     `delivery_ops.REQUEUEABLE_STATUSES` is where the difference is enforced:
#     `bounced_soft` is on that tuple and `bounced_hard` is deliberately NOT.
#
# **What today's single `bounced` does is choose one of those two errors.**
# Treat every bounce as hard and a customer whose mailbox was full on Tuesday
# loses email delivery for ever. Treat every bounce as soft and we post to a
# dead mailbox three times a month, for ever, and burn the reputation every
# other utility on this platform sends through.
#
# **A later lane will be tempted to simplify these back into one value.** The
# two words look like a distinction without a difference until you ask what the
# product DOES with each, and the answer is that one of them takes a consumer's
# email away and the other must never be allowed to. That is why this paragraph
# is here and not in a change request.
#
# ⚠ **`deferred` and `dropped` ARE NOT TWO MORE STATUSES.** SendGrid's
# `deferred` is a retry in progress — the row is still `queued` or `sent` and
# nothing has happened to it yet — and `dropped` is SendGrid refusing to send
# because the address is on ITS OWN suppression list, which is a hard failure by
# any reading. Mapping them is the ADAPTER's job and is not decided here; they
# are named so a reader does not conclude the six are short.
STATUS_BOUNCED_HARD = "bounced_hard"
STATUS_BOUNCED_SOFT = "bounced_soft"
#: The consumer marked the message as spam. Their provider told ours. Like a
#: hard bounce it suppresses — but for a different reason, which is why it is a
#: different word: nothing is wrong with the address, the person does not want
#: the mail, and continuing to send it is what gets a sender blocked.
STATUS_COMPLAINED = "complained"
#: The consumer used the unsubscribe link. This is the ONE outcome of the six
#: that is not a failure of any kind — it is a person exercising a choice, and
#: it must not be shown to a clerk on a list called *failures*.
STATUS_UNSUBSCRIBED = "unsubscribed"

#: ⚠ **NINE VALUES. `test_us_not_001_outbound_queue` ASSERTS THIS EXACT TUPLE**,
#: so a lane adding or removing one goes red and has to come here and read why.
STATUSES = (
    STATUS_QUEUED,
    STATUS_SENT,
    STATUS_DELIVERED,
    STATUS_FAILED,
    STATUS_BOUNCED,
    STATUS_BOUNCED_HARD,
    STATUS_BOUNCED_SOFT,
    STATUS_COMPLAINED,
    STATUS_UNSUBSCRIBED,
)

#: The six an email provider can report, in the normalised vocabulary. This is
#: the CONTRACT an adapter maps onto — it is not the same list as `STATUSES`,
#: because `queued` and `sent` are OURS (nobody reports them to us) and
#: `bounced` is legacy and is never written again.
PROVIDER_OUTCOME_STATUSES = (
    STATUS_DELIVERED,
    STATUS_BOUNCED_HARD,
    STATUS_BOUNCED_SOFT,
    STATUS_COMPLAINED,
    STATUS_FAILED,
    STATUS_UNSUBSCRIBED,
)

#: The statuses a CLERK has to look at — the S30/S8 failures list and the
#: partial index under it. Defined ONCE and read by `Meta.indexes` below,
#: `selectors._apply_order` and `delivery_ops.failures`, because three
#: hand-maintained copies of this tuple is how a new status becomes invisible on
#: the one screen that exists to show it (hard-won law 7, *reporting zero over a
#: scope it silently excludes*).
#:
#: ⚠ **`unsubscribed` IS NOT ON IT, AND THAT IS A DECISION RATHER THAN AN
#: OVERSIGHT.** A consumer who unsubscribed is not a problem for a clerk to
#: repair; putting them on a list headed *failures* invites somebody to
#: re-subscribe them. They appear on the blocked-addresses screen instead, which
#: is where a person can see the choice and, if it was a mistake, undo it.
ATTENTION_STATUSES = (
    STATUS_FAILED,
    STATUS_BOUNCED,
    STATUS_BOUNCED_HARD,
    STATUS_BOUNCED_SOFT,
    STATUS_COMPLAINED,
)

#: US-NOT-001 §5 names five — "invoice / payment / notice / plan / report" —
#: and the field map §4 adds a sixth for the W6 bookkeeper rows ("source=
#: ledger"). Both are signed text, so both are here. Like `BILL_TYPES` in
#: billing this is a CONSTANT, not a lookup table: BR-TEN-036 made the
#: tenant-extensible vocabularies lookups and this is not one — a tenant cannot
#: invent a source the platform has no writer for.
#: ⚠ A SEVENTH ARRIVED 2026-08-17 (CR-009 SET-12/SET-12D lane) — `test`, and it
#: is the only one whose source is not a document. The PO ruled *"lets build the
#: infra and capabilities; the moment we take the decison on ESP or SMTP … we
#: just need to plug it"*, so SET-12D's "Send test" ENQUEUES a message addressed
#: to the signed-in user's own address (`rule_service.queue_test`) — BR-NOT-005
#: is intact, because the forbidden thing is a route that TRANSMITS inside the
#: request and this writes a queue row like every other writer.
#: **`source_id` is the NOTIFICATION RULE's id**, which is honest: the source of
#: a test message is the rule whose button was pressed. Minting a fake invoice
#: id to satisfy the column would put a row on the queue pointing at a bill that
#: does not exist, and the queue is the record of what a utility sent.
#: It gets NO entry in `CHANNEL_FLOOR_BY_SOURCE` and none in
#: `PIN_REQUIRED_SOURCES`: a test is not a bill, so nothing forces it onto paper
#: and nothing demands a frozen version of a document there is no document for.
#: ⚠ AN EIGHTH ARRIVED 2026-08-17 (CR-009 in-app lane) — `bulk_action`, and like
#: `test` its source is not a document. PO verbatim: *"for single notification
#: send 1 message and for bulk action also send 1 message only saying nulk action
#: is completed"* (BR-NOT-020).
#: **`source_id` is the BULK OPERATION's own id** — the bill run, the batch, the
#: import. That choice is what makes the one-message rule STRUCTURAL rather than
#: a habit: the unique key below is (tenant, source_type, source_id, channel,
#: copy_no), so a second summary for the SAME operation is refused by PostgreSQL
#: whether or not the writer remembered the rule. A bulk run over 1,200 accounts
#: cannot produce 1,200 rows here, and it cannot produce two.
#: It gets NO entry in `CHANNEL_FLOOR_BY_SOURCE` — a summary for a clerk is not a
#: bill and nothing forces it onto paper.
#: ⚠ A NINTH ARRIVED 2026-08-30 (CR-048 wave B task B10) — `move`, whose source
#: is a MOVE RECORD (`apps.customers.moves.MoveRecord`) and not a document.
#: **`source_id` is the MOVE RECORD's own id, and that choice is the whole of
#: rule 6 for these two messages.** A welcome letter and a move-out final-bill
#: letter both concern an ACCOUNT, so the obvious key is the account — and it is
#: WRONG: the same account is moved into and later moved out of, so the two
#: messages would share (tenant, source_type, source_id, channel, copy_no) and
#: the move-out letter would silently dedupe into the welcome written months
#: earlier. The move record is one row per JOB (BR-CUS-150), so a move-in and a
#: move-out have different ids by construction and a replayed wizard finds its
#: own row.
#: ⚠ **THIS SAID `move` GETS NO FLOOR AND IT NOW HAS ONE (2026-08-30).** The
#: paragraph read: *"It gets NO entry in `CHANNEL_FLOOR_BY_SOURCE`. BR-NOT-024
#: names the four kinds print is the floor on … and a move message is none of
#: them. Adding a fifth here would be this module inventing a signed rule …"*
#: **That reasoning was right about the process and wrong about the rule.** It
#: was right that a lane may not widen a signed rule by editing a dictionary —
#: so the merge lane put it to the PO instead, and the PO confirmed the four
#: were narrower than what they had said: *"Im okay with your suggestions, you
#: are correct"*. BR-NOT-024 now names SIX kinds and `move` is one of them.
#: **The consequence this paragraph used to state has been REVERSED, not
#: softened:** a utility that switches *Move-in welcome* off now still posts the
#: letter.
#: ⚠ A TENTH ARRIVED 2026-08-30 (CR-048 wave B task B11) — `account`, the kind
#: for correspondence about an ACCOUNT's own life rather than about a document:
#: the account-closed confirmation, the deposit confirmation and the rate-plan
#: change letter. All three are filed `CAT_ACCOUNT_LIFECYCLE` by
#: `catalogs.LISTINGS`, which is the evidence the kind was chosen from —
#: `rule_catalog.EVENTS` states that rule once, in the payments block, so the
#: choice is checkable rather than a taste.
#: **`source_id` IS NEVER THE ACCOUNT, and that is the point of the kind rather
#: than an exception to it.** Every one of these three messages concerns an
#: account, so the account is the obvious key and it loses the second message
#: exactly as it would have lost the move-out letter above. Each names the row
#: for its OWN occasion instead: the disconnect CASE that was closed out, the
#: PAYMENT that cleared as a deposit, and the `unit_plan_assignments` row the
#: rate change wrote. A customer can be given two deposits and two rate changes;
#: they get two letters, because those are two rows.
#: ⚠ **THIS SAID `account` GETS NO FLOOR AND IT NOW HAS ONE (2026-08-30) — AND
#: THIS IS THE KIND THAT DECIDED THE WHOLE QUESTION.** The paragraph read: *"It
#: gets NO entry in `CHANNEL_FLOOR_BY_SOURCE`, for `move`'s stated reason —
#: BR-NOT-024 names four kinds and none of them is this one. So a utility that
#: switches *Account closed* off gets no row at all."* The merge lane put that
#: consequence to the PO rather than accepting it, because **one of these three
#: is the DEPOSIT-RECEIVED confirmation, which acknowledges MONEY RECEIVED and
#: is a receipt by any reading** — and BR-NOT-024's own words are *"don't switch
#: of print for any document it is awayls on"*. PO, verbatim: *"Im okay with
#: your suggestions, you are correct"*. **The floor now names six kinds and this
#: is one of them, so a utility switching *Account closed* off still posts the
#: letter.**
#: `CR-188-BRC10` — `OutboundMessage.priority` of an account-access email.
PRIORITY_IMMEDIATE = 100
PRIORITY_NORMAL = 0

SOURCE_TYPES = (
    "invoice",
    "payment",
    "notice",
    "plan",
    "report",
    "ledger",
    "test",
    "bulk_action",
    "move",
    "account",
    #: ⊕ **ADDED 2026-09-04 (CR-068 wave E) AND IT IS NOT A TIDINESS EDIT — IT
    #: IS THE ONLY WAY THE FLOOR STAYS CORRECT.** The customer portal queues
    #: one-time enrolment codes and password-reset links here (`BR-CWP-033`),
    #: and `CHANNEL_FLOOR_BY_SOURCE` is keyed on THIS tuple's values. Filing an
    #: enrolment code under `account` — the nearest existing kind — would put it
    #: under that kind's PRINT floor and **post a six-digit login code by
    #: letter**, arriving four days after it expired. `portal` is deliberately
    #: NOT in the floor dict: a code is not a document, there is no envelope for
    #: it, and it is worthless within ten minutes.
    "portal",
    #: ⚠ **A TWELFTH ARRIVED 2026-09-05 (CR-070 wave I) — `appointment`, AND THE
    #: RULING THAT ADDED IT SAYS *ELEVEN*.** `OQ-WRK-1495`, closed 2026-09-04:
    #: *"the platform's message-source constant grows from ten kinds to
    #: eleven"*. It was written the same day `portal` landed directly above for
    #: reasons of its own, so the constant already stood at eleven and this makes
    #: **twelve**. Recorded here because the next lane will read that ruling and
    #: needs to know the arithmetic in it is stale, not the choice.
    #:
    #: **WHAT IT IS FOR.** A visit that MOVED — *your visit has moved to
    #: 12:00–17:00*. `source_id` is the WORK ORDER's own id (`BR-WRK-031`).
    #:
    #: ⛔ **THE WHOLE REASON IT IS A KIND OF ITS OWN IS THE MONTHLY REPORT, NOT
    #: THE WORDING.** PO verbatim: *"filing an appointment change beside
    #: disconnection notices distorts every monthly report"*. `notice` was the
    #: nearest existing kind and sending on it would have been INVISIBLE: the
    #: customer gets the right words either way, and a count of notices that
    #: quietly includes appointment changes is wrong every month with nothing on
    #: the report to show it. That is the same failure `portal` above avoids for
    #: a different reason and `move` avoids for a third.
    #:
    #: ⚠ **ADDING A KIND HERE IS TWO EDITS, AND THE SECOND ONE IS THE ONE THAT
    #: GETS FORGOTTEN — IT ALREADY HAS (`DEF-NOT-4032`).** Every value of this
    #: tuple must be classified in ONE of the three buckets at the top of
    #: `06-backend/tests/test_cr048_print_floor.py`, and
    #: `test_br_not_024__every_source_type_is_classified_one_way_or_the_other`
    #: fails NAMING the kind when it is not. `portal` directly above was added on
    #: 2026-09-04 without that second edit and left the guard red for a day, so
    #: this paragraph sits where the first edit is made rather than in the test
    #: nobody had a reason to run.
    #:
    #: It gets NO entry in `CHANNEL_FLOOR_BY_SOURCE`, and it is classified in the
    #: floor test's `NOT_A_DOCUMENT_KINDS` bucket with its reasoning written out:
    #: an appointment change is not a document, and a POSTED one arrives after
    #: the visit it was warning about. If a utility ever asks for a floor here
    #: that is a rule question for the PO, not a dictionary edit — the `move`
    #: precedent, where a lane correctly refused to widen a signed rule by
    #: editing this file and put it to the PO instead.
    "appointment",
    #: ⚠ **A THIRTEENTH ARRIVED 2026-09-12 (`CR-094-BRC01` wave K, `ACC-S16`) —
    #: `message`, AND IT IS THE FIRST KIND A HUMAN COMPOSES ROW BY ROW.** Every
    #: other value here names a document or an event the PRODUCT produced. This
    #: one is what a clerk typed to a customer from the account screen, on a
    #: call, in their own words.
    #:
    #: **`source_id` IS THE COMPOSED MESSAGE'S OWN ID, minted by the screen and
    #: sent with the submit.** There is no other occasion row to key on — the
    #: occasion IS the composing — and that is the difference from `move`, which
    #: keys on a job record that already existed. Minting it on the CLIENT is
    #: what makes a double-clicked *Queue the message* write one message and not
    #: two: the second submit carries the same id and meets the unique key
    #: below, exactly as a replayed bill run does.
    #:
    #: ⛔ **IT GETS NO ENTRY IN `CHANNEL_FLOOR_BY_SOURCE`, AND FILING IT UNDER
    #: `account` INSTEAD WOULD HAVE POSTED A LETTER EVERY TIME.** `account` is
    #: account-lifecycle correspondence and carries the PRINT floor
    #: (`BR-NOT-024`, six kinds), so a clerk emailing *"I am looking into where
    #: your balance came from and will call you back Friday"* would also have
    #: put that sentence in an envelope — a real cost, on a message whose whole
    #: point is that it is quick. A courtesy note is not a document: it freezes
    #: no copy, and `A19` rule 3's postal floor is about a NOTICE.
    #:
    #: It is classified in the floor test's `NOT_A_DOCUMENT_KINDS` bucket — the
    #: second edit the `appointment` paragraph above warns gets forgotten.
    "message",
    #: ⚠ **A FOURTEENTH ARRIVED 2026-09-15 (`CR-094-BRC01`, `DEF-CUS-5389`) —
    #: `service_request`, AND IT IS THE FIRST KIND WHOSE RECIPIENT IS NOT A
    #: CUSTOMER OF THIS UTILITY.** An APPLICANT is somebody who has asked for
    #: service and has no account, no customer row and, when the answer is no,
    #: never will. Every other kind here addresses somebody already on the
    #: books.
    #:
    #: **WHAT IT IS FOR.** The three things a service request says to the person
    #: who raised it: the acknowledgement on submission (`BR-CUS-079`), the
    #: refusal letter, and the message a clerk sends when they ask for more.
    #:
    #: **`source_id` IS THE ROW FOR THE OCCASION, AND THE OCCASION IS DIFFERENT
    #: FOR EACH OF THE THREE.** The acknowledgement keys on the SERVICE REQUEST
    #: itself, because a request is acknowledged exactly once and a replayed
    #: submit must find that row and write nothing. The refusal letter and the
    #: ask-for-more message key on the `service_request_events` row that records
    #: the act — the `move` precedent, where a job record that already exists is
    #: the key. Keying all three on the request would be the mistake `move`
    #: documents one kind up: the second message would dedupe into the first and
    #: the clerk would be told it was queued with nothing written. A request can
    #: be asked for more twice and, after a reopen, refused twice.
    #: The whole argument is in `apps/notifications/service_request_events.py`.
    #:
    #: ⛔ **IT GETS NO ENTRY IN `CHANNEL_FLOOR_BY_SOURCE`, AND THE REASON IS
    #: PHYSICAL BEFORE IT IS A JUDGMENT: THIS PRODUCT HOLDS NO POSTAL ADDRESS
    #: FOR AN APPLICANT.** A request carries the address of the PROPERTY that
    #: wants service, never a mailing address for the person asking — and the
    #: commonest refusal reason drawn on the blueprint is *Not our service
    #: area*, so a print floor would post a letter to a street this utility has
    #: just said it does not serve. It is still filed in the floor test's
    #: `NOT_A_DOCUMENT_KINDS` bucket rather than in `NO_POSTAL_SURFACE_KINDS`,
    #: because a utility could reasonably want a posted refusal once an
    #: applicant mailing address exists — and a bucket that made it look settled
    #: would hide that. If one is asked for, it is a `BR-NOT-024` amendment for
    #: the PO, never an edit to a dictionary (the `move` precedent).
    #:
    #: ⚠ **AND THE SECOND EDIT IS THE ONE THAT GETS FORGOTTEN** — the
    #: `appointment` paragraph above says so and `portal` proved it. This kind
    #: is classified in `06-backend/tests/test_cr048_print_floor.py`'s
    #: `NOT_A_DOCUMENT_KINDS` in the same commit that adds it here.
    "service_request",
    #: ⚠ **A FIFTEENTH ARRIVED 2026-09-20 (`DEF-CUS-5949`) — `transfer`, AND IT
    #: IS THE FIRST KIND WHERE *WHO THE MESSAGE IS FOR* CANNOT BE READ OFF
    #: `account_id`.** A property sale REASSIGNS the account (`BR-CUS-1030`):
    #: the account does not move, its CUSTOMER changes. So from the instant the
    #: commit lands, `account_id` means *the buyer*, and the letter telling the
    #: SELLER they no longer hold it would be indistinguishable from the
    #: buyer's if it carried that column. **The seller's row carries
    #: `account_id` NULL and names its party in `recipient_snapshot.party`** —
    #: the whole argument, and why a `recipient_customer_id` column was weighed
    #: and rejected, is in `apps/notifications/transfer_events.py`.
    #:
    #: **WHAT IT IS FOR.** The three messages the blueprint draws on commit:
    #: change of ownership to the buyer, change of ownership to the seller, and
    #: a field-visit SMS to the buyer about the changeover read.
    #:
    #: **`source_id` IS DERIVED, AND THIS IS THE FIRST KIND WHERE IT IS.** Every
    #: other kind names a ROW for the occasion; a sale has exactly ONE occasion
    #: row and three messages come off it, two of them on the same channel.
    #: Keying all three on `transfer.id` would meet the unique index below and
    #: silently dedupe the seller's letter into the buyer's — `move`'s
    #: documented trap one kind over. So it is `uuid5(transfer.id, party +
    #: channel)`: derived rather than minted, so a replayed commit computes the
    #: same three keys and writes nothing (rule 6), and the transfer's real id
    #: travels in `render_context["transfer_id"]` so nothing is lost.
    #:
    #: ⛔ **IT GETS NO ENTRY IN `CHANNEL_FLOOR_BY_SOURCE`.** `BR-NOT-024` names
    #: SIX source kinds print is the floor on and a transfer is none of them,
    #: and a lane may not widen a signed rule by editing a dictionary — the
    #: `move` precedent, where the merge lane put it to the PO instead. The
    #: consequence is stated rather than hidden: a utility gets an email and a
    #: text and no posted letter. If one is asked for, that is a `BR-NOT-024`
    #: amendment for the PO.
    #:
    #: ⚠ **AND THE SECOND EDIT IS THE ONE THAT GETS FORGOTTEN** — `portal`
    #: proved it. This kind is classified in
    #: `06-backend/tests/test_cr048_print_floor.py`'s `NOT_A_DOCUMENT_KINDS`
    #: bucket in the SAME commit that adds it here.
    "transfer",
    #: ⚠ **`connection` ARRIVED 2026-10-02 (`CR-163-BRC10` item 26) — RULED ON
    #: 2026-09-21 AND NOT BUILT FOR ELEVEN DAYS.** `OQ-NOT-12521`, closed option
    #: A, PO verbatim: *"A · A new connection kind — Its own retention, its own
    #: template group, and a clerk sees connection letters grouped as connection
    #: letters."* Until this line every New Connection letter was refused BY
    #: NAME at the door and the build record said *"not sent"* on every row.
    #:
    #: **`source_id` IS ONE ROW PER OCCASION, NOT THE CONNECTION'S OWN ID** —
    #: `metering.connection_messages.occasion_source_id`, a `uuid5` of the build
    #: and the occasion code. The unique key below is (source, channel, copy),
    #: so three letters keyed on the build itself would collide on `email` and
    #: the third would silently become the first: the `service_request`
    #: precedent two kinds up, one table over.
    #:
    #: ⛔ **REUSING `notice` WAS THE EXPLICITLY REJECTED OPTION** — it would put
    #: a welcome letter among disconnection notices. Classified in the floor
    #: test's `NOT_A_DOCUMENT_KINDS` bucket with its reasoning: each occasion
    #: already names print where the drawing does (the contract, the quote), so
    #: a floor on the KIND would be a `BR-NOT-024` amendment for the PO.
    "connection",
    #: ⚠ **`field_work` ARRIVED 2026-10-04 (`CR-168-BRC10` §F, lane FIELD-2) —
    #: THE FIRST STAFF-ADDRESSED KIND THAT IS NOT A BULK RUN.** TECHNICIAN SYNC
    #: DESIGN (5): *"the office is told when a job closes, when its photos are
    #: complete (Accept unlocks), and when anything is flagged Needs review"*.
    #: Lane FIELD-FIX found nothing to queue those under: `bulk_action` is a
    #: RUN's summary (*"Billing run finished. 40 processed · 0 failed"*) and a
    #: field close is one job's event, so filing it there would put job closes
    #: in every count of bulk runs — the `appointment` argument one kind up.
    #: `source_id` is a `uuid5` of (job, event, discriminator) —
    #: `field_work_events.source_id_for` — so a close and its photos-complete
    #: are two rows, not one row colliding with itself. In-app only; classified
    #: in the floor test's `NOT_A_DOCUMENT_KINDS`: nothing about it is a letter.
    "field_work",
    #: ⚠ **`usage_alert` ARRIVED 2026-10-14 (`CR-182-BRC10`, PO A1–A5) — A
    #: READING FLAGGED HIGH TELLS THE CUSTOMER.** `source_id` is the METER
    #: READING's id (`apps/metering/high_consumption.py`), so a re-save of the
    #: same reading meets the unique key and writes nothing (hard rule 6).
    #: Its own kind and not `account` — that kind carries the PRINT floor
    #: (`BR-NOT-024`) and would post a letter for every flagged reading, days
    #: after the email that was the point (PO A4 chose email, not paper).
    #: Classified in the floor test's `NOT_A_DOCUMENT_KINDS` in the same commit.
    "usage_alert",
    #: `CR-190-BRC10` (2026-10-22) — an agreement to accept by link, and its
    #: acceptance confirmation. `source_id` is the `agreement_requests` row, so
    #: a Resend is a new row. **NO PRINT FLOOR, BY THE PO'S OWN RULING OF THAT
    #: DAY**: *"email it as a PDF attachment (plus a letter if the customer
    #: wants paper)"* — the letter is the customer's choice (`paperless`), not a
    #: floor. Classified in the floor test's arguable bucket in the same commit.
    "agreement",
    #: ⚠ **`staff_access` ARRIVED 2026-10-22 (`CR-188-BRC10`)** — a member of
    #: staff's invitation or password-reset email, carrying a one-time sign-in
    #: link and never a password. `source_id` is the `password_links` row, so a
    #: resend is a new row. No postal surface exists for staff (classified in
    #: the floor test's `NO_POSTAL_SURFACE_KINDS` in the same commit).
    "staff_access",
    #: ⚠ **`service_state` ARRIVED 2026-10-29 (`DEF-NOT-10649`, PO *"1 A, 2 A,
    #: 3 A, 4 A"*)** — *Service disconnected* when a cut is recorded and
    #: *Service restored* when it is restored, by EMAIL AND TEXT (2A) and
    #: switchable off per utility (3A). `source_id` is `uuid5(case, act)`
    #: (`customer_events.service_state_source_id`), so a replay writes nothing.
    #: Its own kind and not `account` — that kind carries the PRINT floor
    #: (`BR-NOT-024`), so it would post a letter the PO did not ask for and a
    #: utility could never switch off: 2A and 3A both broken by the nearest
    #: existing kind. `usage_alert`'s reasoning, one occasion over. Classified in
    #: the floor test's `NOT_A_DOCUMENT_KINDS` in the same commit.
    "service_state",
    #: ⚠ **`reminder` ARRIVED 2026-10-29 (`DEF-PAY-10651`, PO *"1A 2A 3A 4B"*)
    #: — THE FRIENDLY PAST-DUE REMINDER, LADDER RUNG 1, MOVED OFF `notice`.**
    #: `notice` carries the PRINT floor (`BR-NOT-024`), which survives even the
    #: rule's master switch; the PO ruled that switching *Past-due reminder* off
    #: sends nothing (1A) and that paper goes only to a customer no email or
    #: consented text can reach (2A). Under the floor both cannot hold, so the
    #: reminder has its own kind with NO floor and
    #: `notifications.past_due_reminder` adds the letter itself when it is the
    #: only way through. The DISCONNECTION notices stay on `notice` and keep the
    #: floor. `source_id` is payments' `ladder_notice_source_id` with the
    #: business date. Classified in the floor test's `NOT_A_DOCUMENT_KINDS` in
    #: the same commit.
    "reminder",
)

#: Why a row carries no recipient address. `no_email_address` is the one
#: BR-BIL-036 calls normal — *"many accounts have NO email address at all"*.
#: The others are its siblings on the other two channels.
REASON_NO_EMAIL = "no_email_address"
REASON_NO_MOBILE = "no_mobile_number"
REASON_NO_SMS_OPT_IN = "no_sms_opt_in"  # A15: no opt-in, no SMS
REASON_NO_POSTAL = "no_postal_address"
#: ⚠ NOT A FACT ABOUT THE CUSTOMER — a fact about the PLATFORM, and that is
#: exactly why it is a fifth value rather than one of the four above.
#:
#: The four above each assert something about a person: this account holds no
#: email address, this one never opted in to SMS. `recipient_not_resolvable`
#: asserts only that NOBODY LOOKED — the owning module publishes no
#: delivery-recipient read, so the address is UNKNOWN, not absent (the read is
#: named in `apps/notifications/services.py` as `RECIPIENT_READ`).
#:
#: Recording an unresolved address as `no_email_address` would put a number on
#: a dashboard that says "142 of your customers have no email address" when the
#: truth is "we did not ask". That is the same lie `apps/billing/release.py`
#: refuses when it reports mandate coverage as UNAVAILABLE rather than as zero:
#: *"'0 of 1,122 hold an address' and 'we could not count' must never render
#: the same."* Added 2026-08-11 by the queue-write lane; the reason it exists
#: at all is a REPORTED gap, not a settled design (decision log, same date).
REASON_NOT_RESOLVABLE = "recipient_not_resolvable"
UNAVAILABLE_REASONS = (
    REASON_NO_EMAIL,
    REASON_NO_MOBILE,
    REASON_NO_SMS_OPT_IN,
    REASON_NO_POSTAL,
    REASON_NOT_RESOLVABLE,
)


class OutboundMessage(models.Model):
    """One message, on one channel, waiting for the dispatcher.

    B2 r12 #16 + r10 #8. Written by any module through the ruled insert
    interface; advanced only by the dispatcher (US-NOT-002, not built).
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")

    # ── what this message is about ──────────────────────────────────────
    #: r12 #16 "across ALL modules" — which module's event produced the row and
    #: which of its rows. Required (US-NOT-001 §5), and required is what makes
    #: the idempotency key below a real key rather than a suggestion.
    source_type = models.TextField()  # SOURCE_TYPES
    #: Deliberately NOT a foreign key — the target is a different table per
    #: source_type. Polymorphic source_id integrity is B2 r16 #5's O-4 residue
    #: and is NOT closed here.
    source_id = models.UUIDField()
    #: BR-BIL-016 / r12 #16 — one row per document per CHANNEL.
    channel = models.TextField()  # CHANNELS
    #: 0 = the delivery record BR-BIL-016 mandates. > 0 = a deliberate,
    #: human-requested extra copy (US-NOT-011 receipt re-send, US-BIL-024 TC-4).
    #: Automatic writers never set it; see the docstring's key section.
    copy_no = models.IntegerField(default=0)
    #: `CR-188-BRC10` (PO 2026-10-22, *"this should be on highest priority in
    #: quesu"*). `PRIORITY_IMMEDIATE` on an account-access email — sent at once
    #: by `services.send_now` and, if that attempt could not deliver it, claimed
    #: FIRST by the next cycle. 0 for everything else, which keeps FIFO.
    priority = models.SmallIntegerField(default=0)
    #: B2 §2 carried `notifications.account_id`; kept, and kept NULLABLE —
    #: US-NOT-015's scheduled-report and bookkeeper rows are addressed to staff
    #: and belong to no customer account.
    account = models.ForeignKey(  # ⚠ cross-module FK → customers (reviewed set)
        "customers.Account",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="account_id",
    )

    # ── how it will be rendered (pinned, never re-resolved) ─────────────
    #: BR-BIL-026's pattern applied to every message class: the row records
    #: WHICH template version it is to be rendered from, so a template
    #: published between queueing and dispatch cannot change the document.
    #: Plain columns: the template tables are EP-NOT-02 (see docstring).
    template_code = models.TextField(null=True, blank=True)
    template_id = models.UUIDField(null=True, blank=True)
    template_version = models.IntegerField(null=True, blank=True)
    #: BR-NOT-006 — the pinning tuple includes the LANGUAGE variant, so a
    #: reprint renders its pinned language forever.
    template_language = models.TextField(null=True, blank=True)
    #: THE FACTS THIS MESSAGE STATES, stamped by the writer that HELD them.
    #:
    #: ⚠ ADDED 2026-08-17 (CR-009 in-app lane), and it closes a gap this module
    #: has been REPORTING rather than fixing: `rendering.render_for_dispatch`'s
    #: own docstring says *"the merge context is still empty on this deployment
    #: unless a caller supplies one … so a dispatch-time render produces the
    #: template's text with its catalogued tokens marked as NAMED ABSENCES"*.
    #: A bulk-run summary rendered that way reads *"—— finished. —— processed ·
    #: —— failed"*, which is not a notification, and the PO asked for in-app
    #: precisely so that a real message can be READ.
    #:
    #: It is authorised law rather than a new idea: BR-NOT-012 already speaks of
    #: *"the notification's own STORED RENDER CONTEXT for non-invoice notices"*.
    #: The words "non-invoice" are load-bearing and are honoured — see below.
    #:
    #: **WHAT MAY GO IN IT, AND WHAT MAY NOT.** Only facts the WRITER already
    #: holds and that the template's own token whitelist names. Nothing here is
    #: looked up at dispatch and nothing is invented: a NULL context still
    #: renders named absences exactly as before, so no existing writer's
    #: behaviour changed on the day this column arrived.
    #:
    #: ⚠ **THIS PARAGRAPH READ *"AN INVOICE'S FIGURES ARE STILL NOT PUT HERE"*
    #: FROM 2026-08-17 UNTIL 2026-09-07, AND IT IS SUPERSEDED. `DEF-BIL-4448`.**
    #: What it said, kept because the reasoning is worth reading before anybody
    #: re-makes it: *"BR-BIL-026 freezes a bill's template version at issue and
    #: BR-TEN-017 says an issued document is never re-rendered; where a bill's
    #: numbers live is billing's question, not this module's, and duplicating
    #: them onto a queue row would create a second copy of a money figure free
    #: to disagree with the invoice (hard-won law 5)."*
    #:
    #: **WHAT SUPERSEDES IT IS A LATER, CONFIRMED PO RULING: `BR-NOT-027`
    #: (2026-08-30, `CR-049`).** Its part (1) is *"Keep all the underlying data
    #: — we already do (`outbound_messages.render_context`)"*, and the rule
    #: states in its own words that **its reach includes the bill**: *"SO THE
    #: RULE'S REACH IS WIDER THAN IT WAS FIRST WRITTEN: BR-NOT-027 APPLIES TO
    #: THE BILL TOO."* This column IS the store that ruling names.
    #:
    #: **AND THE ORIGINAL WORRY IS ANSWERED BY CONSTRUCTION RATHER THAN WAIVED.**
    #: `billing.delivery_seam.bill_render_context` copies every figure out of
    #: `invoices.bill_payload` — the instance locked at issue, protected by
    #: `billing/0006`'s immutability trigger, and the same instance
    #: `billing.documents` renders the printed bill FROM. So it is not a second
    #: copy free to disagree with the invoice; it is the invoice's own stamped
    #: number, and for the two to disagree the payload would have to disagree
    #: with itself. A figure NOT in the payload is not put here either — that is
    #: still the rule, and it is why `{correction_reason}` travels as a stated
    #: absence.
    #:
    #: **WHAT THE OLD READING COST, measured on the seeded utility:** the
    #: bill-ready email's eleven merge fields — the customer's name, the service
    #: address, the bill number, both dates, the period, and all four figures of
    #: A19 §1.3's summary box — every one of them an em-dash, on the one letter
    #: a utility's customers actually read. Its subject line, A19 r8's own
    #: *"… bill is ready — $247.30 due Aug 25"*, came out *"…is ready — —— due
    #: ——"*.
    #:
    #: **WHAT MAY GO IN IT IS UNCHANGED OTHERWISE:** only facts the WRITER
    #: already holds and that the template's own token whitelist names. Nothing
    #: is looked up at dispatch and nothing is invented; a NULL context still
    #: renders named absences exactly as before.
    render_context = models.JSONField(null=True, blank=True)

    # ── who it goes to (snapshot, never re-resolved — BR-TEN-017) ───────
    #: The address as it stood when the row was written: an email address, an
    #: E.164 number, or the postal address the print vendor will use. NULL only
    #: when there is none, and then `unavailable_reason` says so.
    recipient_address = models.TextField(null=True, blank=True)
    #: The rest of what the envelope needs — name, address lines, care-of. A
    #: payload rather than columns for the same reason `invoices.
    #: issued_snapshot` is one: what a message needs is channel- and
    #: tenant-shaped, and a column per printed field puts a migration between
    #: the tenant and their own layout.
    recipient_snapshot = models.JSONField(null=True, blank=True)
    #: BR-BIL-036 — *"an account with NO email address is normal, not an
    #: exception"*. This column is how that absence is RECORDED instead of
    #: being a row nobody wrote. One of UNAVAILABLE_REASONS; the CHECK below
    #: makes exactly one of (address, reason) present.
    unavailable_reason = models.TextField(null=True, blank=True)

    # ── lifecycle ───────────────────────────────────────────────────────
    status = models.TextField(default=STATUS_QUEUED)  # STATUSES
    #: US-BIL-023 §5 (S31 step 6 "send now vs scheduled") and BR-NOT-009 quiet
    #: hours: the dispatcher honours it. NULL = eligible immediately.
    dispatch_not_before = models.DateTimeField(null=True, blank=True)

    # ── written by the DISPATCHER only (US-NOT-002 — not built) ─────────
    #: r10 #8 "batch id". A plain uuid: the batch is minted at handoff and no
    #: signed document names a batch table (see docstring).
    batch_id = models.UUIDField(null=True, blank=True)
    #: BR-NOT-005 retry ×3 with backoff. The LIMIT is the dispatcher's policy,
    #: not a column constraint — encoding "≤ 3" in DDL would make a retry
    #: policy change a migration.
    attempts = models.IntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)  # US-BIL-024 TC-2
    sent_at = models.DateTimeField(null=True, blank=True)  # B2 §2 `notifications.sent_at`
    #: r10 #8 "provider response" — the success reference and the raw payload.
    provider_reference = models.TextField(null=True, blank=True)
    provider_response = models.JSONField(null=True, blank=True)
    #: The staff-readable error the S30/S8 failures list shows (US-BIL-024
    #: TC-2). Separate from the raw payload because one is for a person.
    last_error = models.TextField(null=True, blank=True)

    # ── returned mail + paper suppression (US-NOT-014, BR-PAY-018) ──────
    # ⚠ ADDED 2026-08-15 by the notifications CONTENT lane. The docstring above
    # says these were *"deliberately absent … their own stories"*; this is that
    # story, and the dispatcher's per-cycle `held_marker_not_implemented` problem
    # is what it closes.
    #: BR-PAY-018: while an account is flagged bad-address and the tenant's
    #: `suppress_paper_on_bad_address` is ON, new PAPER rows are *"written,
    #: marked held, never dispatched, never lost"*. A flag rather than a status,
    #: deliberately: the status lifecycle is forward-only (BR-NOT-005) and a
    #: `held` status would be a sixth state the re-queue action could reach.
    #: Held is orthogonal — a queued row that is not currently selectable.
    held = models.BooleanField(default=False)
    #: WHY it is held, so the dashboard can group and a release can be explained.
    held_reason = models.TextField(null=True, blank=True)
    #: US-NOT-014 TC-1: a paper letter came back. NOT a status either — a
    #: returned letter was genuinely SENT, and rewriting its status would
    #: destroy the fact that it left the building (BR-NOT-005 forward-only).
    returned_at = models.DateTimeField(null=True, blank=True)
    returned_by = models.UUIDField(null=True, blank=True)

    # ── CR-048 B6 · WHICH SET-12 EVENT PRODUCED THIS ROW ────────────────
    #: ⚠ ADDED 2026-08-30 (CR-048 wave B task B6). A key of
    #: `rule_catalog.EVENTS_BY_KEY`, stamped by `services.queue_document` from
    #: the `event_key` its caller named. NULL where the writer named no event —
    #: which is every row written before wave B, and every writer still
    #: un-wired.
    #:
    #: **WHY THIS IS A COLUMN AND NOT A REVERSE MAP.** B6 asks for per-event
    #: counts, and `rule_models.py` already rules that *"counts are computed
    #: from `outbound_messages`, never stored"* — so the only question was how a
    #: row says which event it belongs to. It cannot be derived: `services.
    #: channel_decision`'s own docstring measured all three candidates and
    #: refused each. `source_type` is one-to-MANY onto events (`invoice` is
    #: `bill_ready` OR `bill_corrected`); `category` is the CONSUMER category
    #: and shares no vocabulary with an event category; and the template pin is
    #: ambiguous in both directions — `staff_bulk_summary` is the in-app class
    #: of TWO events, and a disconnect notice pins a per-TIER class that its
    #: event does not name. A count built on any of those would be a guess
    #: wearing a lookup table, reported to a System Admin as a fact.
    #:
    #: It is NOT a foreign key, for `NotificationRule.event_key`'s reason: the
    #: vocabulary is a code CONSTANT that no tenant can extend, so there is no
    #: table for it to point at.
    event_key = models.TextField(null=True, blank=True)
    #: ⚠ ADDED 2026-08-30 (CR-048 B6). The channels this utility's own rule
    #: REMOVED from this document, comma-joined, or NULL when it removed none.
    #:
    #: **A SUPPRESSION IS A FACT ABOUT WHAT THE PLATFORM DID, and before this
    #: column nothing recorded one.** `queue_document` returned the reason on
    #: `QueueWrite.problems` and the caller was free to drop it; a System Admin
    #: asking *"did switching that off actually do anything?"* had nothing to
    #: read. It rides the surviving row rather than a table of its own because
    #: the fact belongs to the document it is about — and because every CUSTOMER
    #: document has a print floor (BR-NOT-024), so a surviving row always
    #: exists to carry it.
    #:
    #: ⚠ **THE ONE CASE IT CANNOT RECORD, stated rather than left to be
    #: discovered:** a source kind with NO floor (`bulk_action`, `move`, `test`)
    #: whose rule suppressed EVERY channel writes no row at all, so there is
    #: nothing to stamp. `delivery_counts` reports that as a stated absence per
    #: event instead of counting zero.
    rule_suppressed_channels = models.TextField(null=True, blank=True)

    #: `created_at` IS the `queued_at` the S30 capability matrix sorts by
    #: ("failed first, then queued_at") — one column, named the way every other
    #: table in this schema names it.
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "outbound_messages"
        indexes = [
            # The dispatcher's pickup query (BR-NOT-005 batches, US-NOT-002):
            # queued rows for one channel whose time has come. Partial, like
            # B2 §4's `ix_reads_unrated` — the queue is mostly history.
            models.Index(
                fields=["tenant", "channel", "dispatch_not_before"],
                condition=Q(status=STATUS_QUEUED),
                name="ix_outbound_msgs_dispatch",
            ),
            # The dispatch-home and per-run dashboards: counts by channel ×
            # status (US-NOT-013 §5, US-BIL-024 §5).
            models.Index(fields=["tenant", "status", "channel"], name="ix_outbound_msgs_status"),
            # "Did this customer's bill go out?" on the account timeline (S35).
            models.Index(fields=["tenant", "account"], name="ix_outbound_msgs_account"),
            # The failures list, which is the dashboard's default view
            # (US-BIL-024 TC-2, capability row "failed first").
            # ⚠ WIDENED 2026-09-17 (`DEF-NOT-5626`, migration 0018) from the two
            # statuses that existed to `ATTENTION_STATUSES`, which is the same
            # tuple `selectors._apply_order` and `delivery_ops.failures` read.
            # A hard bounce that did not appear on the one screen built to show
            # a clerk what went wrong would be hard-won law 7's *reporting zero
            # over a scope it silently excludes*: the query would be correct and
            # the answer would be missing rows nobody could see were missing.
            models.Index(
                fields=["tenant", "-created_at"],
                condition=Q(status__in=ATTENTION_STATUSES),
                name="ix_outbound_msgs_failed",
            ),
            # CR-048 B6 — the "Last 30 days" rail on SET-12D and the counters on
            # the SET-12 list: one event's rows in a date window. PARTIAL on
            # `event_key IS NOT NULL`, like the dispatch index above, because
            # every row written before wave B carries no event and indexing
            # those would be size for rows the query never returns.
            models.Index(
                fields=["tenant", "event_key", "-created_at"],
                condition=Q(event_key__isnull=False),
                name="ix_outbound_msgs_event",
            ),
            # No separate (tenant, source_type, source_id) index: the unique
            # constraint below already leads with those three columns, and a
            # second index on the same prefix is write cost for nothing.
        ]
        constraints = [
            # CLAUDE.md rule 6 / US-NOT-001 TC-5. The whole reasoning is in the
            # module docstring; the short version is that a re-emitted source
            # event finds this row already here.
            models.UniqueConstraint(
                fields=["tenant", "source_type", "source_id", "channel", "copy_no"],
                name="uq_outbound_msgs_source_channel",
            ),
            # BR-BIL-036 made structural: a row either carries the address it
            # will be delivered to, or states why it has none. It can never
            # carry neither — which is the shape a silently-dropped message
            # would have had.
            models.CheckConstraint(
                condition=Q(recipient_address__isnull=False, unavailable_reason__isnull=True)
                | Q(recipient_address__isnull=True, unavailable_reason__isnull=False),
                name="ck_outbound_msgs_address_or_reason",
            ),
            models.CheckConstraint(condition=Q(copy_no__gte=0), name="ck_outbound_msgs_copy_no"),
            models.CheckConstraint(condition=Q(attempts__gte=0), name="ck_outbound_msgs_attempts"),
        ]


#: BR-BIL-016, verbatim: *"batch default 500 (tenant-config)"*. BR-NOT-005 makes
#: it platform-wide. This is the ONE home of that ratified figure — the
#: dispatcher reads the tenant's row and never carries a constant of its own, so
#: US-NOT-002 TC-2 ("changed to 200 → next cycle honours 200") is a property of
#: the schema rather than of anybody remembering.
SEEDED_BATCH_SIZE = 500
#: BR-NOT-009, verbatim: *"tenant-config send window for email/SMS, default
#: 08:00–21:00 tenant time; print/PDF generation exempt"*.
SEEDED_QUIET_HOURS_START = time(8, 0)
SEEDED_QUIET_HOURS_END = time(21, 0)


class NotificationSettings(models.Model):
    """The tenant's dispatch configuration — S8 tab 7's config half.

    BR-TEN-041 upgrade #8 makes Settings → Notifications the platform's
    delivery/dispatch home, and B2 r12 #16 makes *"batch size/cadence"*
    tenant-config. This is the row those screens edit and the dispatcher reads.

    WHY THIS TABLE IS NOTIFICATIONS' AND NOT TENANCY'S. BR-TEN-031 splits the
    settings FRAMEWORK (tenancy's: the screen, the tabs, the audit shape) from
    the CONTENT (the owning module's). `apps/notifications/models.py`'s own
    docstring already recorded the expectation — *"the tenant dispatch settings
    (batch size, quiet hours, channel-activation flags — US-NOT-004,
    BR-TEN-041) … are their own stories"* — and this is that story's table.
    Putting it in `apps.tenancy.settings_families` instead would put a
    migration in tenancy's lane between notifications and its own dispatcher.

    ONE ROW PER TENANT, created on first read with the ratified defaults above.
    There is no "unset" state for a dispatcher to interpret: a tenant that has
    never opened the screen dispatches at 500 in an 08:00–21:00 window, which is
    exactly what BR-BIL-016 and BR-NOT-009 say happens by default.

    WHAT IS DELIBERATELY NOT HERE
    -----------------------------
    * ⚠ **[AMENDED 2026-08-18] The four A15 "(opt)" toggles ARE HERE NOW — the
      ruling this bullet waited for arrived.** It used to say shipping a
      `default=True` column *"would decide, for every utility on the platform,
      whether recording a payment sends the customer a receipt … OQ-205, minted
      rather than answered."* **The PO answered it (2026-08-17, C-13 verbatim:
      "keep them default to start with Utility will amake them off") — the four
      ship ON, and note the ruling REVERSED the off-by-default recommendation;
      that was the PO's call to make.** The columns are below (`default=True`,
      which also answers OQ-216's posture: a tenant provisioned before the
      columns existed is treated as ON). One consumer exists and is wired —
      `apps/payments/receipts.py` reads `receipt_on_record_payment` through the
      published notifications read at record time; the other three toggles are
      stored, editable and honest on the screen about their consumers not being
      built yet (US-PAY-025's lockbox half, BR-LED-020's bookkeeper copies).
    * **`suppress_paper_on_bad_address`** (BR-PAY-018) and the held marker — the
      returned-mail flow is US-NOT-014, a different story with its own table
      changes. The dispatcher names the gap where it would have consulted them.
    * **A print activation flag.** Field map §1 names activation flags for
      *"email W6 · SMS v1.1"* and for nothing else, and BR-BIL-036 makes print
      the FLOOR. A tenant-settable switch that turns paper off would be a switch
      that stops bills reaching customers who have no other channel.
    """

    id = uuid7_pk()
    #: OneToOne: the dispatch home is one screen per tenant, not a list.
    tenant = models.OneToOneField("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")

    #: BR-BIL-016 / r12 #16. Read fresh on every dispatch cycle (US-NOT-002
    #: TC-2, T7-17 step 4: *"config read per dispatch cycle"*), never cached
    #: into a running drain — T7-17 step 3 keeps an in-flight hand-off intact
    #: and step 4 applies the new size from the next one.
    dispatch_batch_size = models.IntegerField(default=SEEDED_BATCH_SIZE)

    #: BR-NOT-009. Times are TENANT-LOCAL wall-clock times, not UTC: the rule
    #: says *"08:00–21:00 tenant time"*, and the zone lives on the tenant's
    #: Regional settings (read through `apps/notifications/tenancy_seam.py`).
    #: Storing a UTC instant here would silently move the window twice a year.
    quiet_hours_start = models.TimeField(default=SEEDED_QUIET_HOURS_START)
    quiet_hours_end = models.TimeField(default=SEEDED_QUIET_HOURS_END)

    #: US-NOT-003 / OQ-073 + OQ-074 closures. Rows for every channel are written
    #: from day one; only the SEND defers, and these two flags are what "defers"
    #: means in code. They ship FALSE — the unsafe option is the one you type
    #: (hard-won law 3), and the unsafe option here is a provider call made
    #: before the rails, the mailbox and the tenant's own consent exist.
    email_dispatch_active = models.BooleanField(default=False)
    sms_dispatch_active = models.BooleanField(default=False)

    # ── the four A15 "(opt)" send-time elections (C-13, OQ-205 CLOSED) ──────
    #: PO 2026-08-17, verbatim: *"keep them default to start with Utility will
    #: amake them off"* — ALL FOUR DEFAULT ON, reversing the off-by-default
    #: recommendation (the PO's call). `default=True` on the column is also the
    #: OQ-216 posture: a tenant provisioned before these columns existed gains
    #: them ON at migration, exactly as if they had always held the default.
    #: A15's four "(opt)" sends, in its own order:
    #: receipt on record-payment — CONSUMED by `apps/payments/receipts.py`.
    receipt_on_record_payment = models.BooleanField(default=True)
    #: credit-notice email — stored and editable; its consumer (the credit-issue
    #: path queueing `email_credit_issued`) is not built, and the screen says so.
    credit_notice_email = models.BooleanField(default=True)
    #: bookkeeper reconcile/QB-sync copies (BR-LED-020) — consumer not built.
    bookkeeper_copies = models.BooleanField(default=True)
    #: lockbox receipts (US-PAY-025's lockbox half) — consumer not built.
    lockbox_receipts = models.BooleanField(default=True)

    # ── the tenant EMAIL SENDER config (C-12, BR-NOT-023 — SMTP-first) ──────
    #: PO 2026-08-17, C-12 verbatim: *"both: tenant's own SMTP (Office365/
    #: Gmail) as default"* — the PLUG for the sender decision, stored ahead of
    #: the adapter (*"the moment we take the decison … we just need to plug
    #: it"*). All NULL until a System Admin fills the S8 card; NULL everywhere
    #: means "fall back to the platform ESP when that lands". Nothing here
    #: switches a send on — `email_dispatch_active` above is that switch and
    #: BR-NOT-013 still holds it shut.
    #:
    #: ⚠ **READ BY NOTHING SINCE 2026-10-22 — LISTED FOR REMOVAL (`DEF-NOT-10534`).**
    #: PO: *"We have to move everything in connector not any other place"*. The
    #: mail server lives on Settings → Connectors → Custom SMTP only;
    #: `integrations/0016` copied any value only these five held into that
    #: connection, once, audited. `smtp_host`, `smtp_port`, `smtp_username`,
    #: `smtp_secret_ref` and `sender_from_address` (and
    #: `ck_notification_settings_smtp_port`) are to be DROPPED by a later
    #: migration once a release has run with nothing reading them; the API
    #: refuses a write to any of them by name. Do not add a reader.
    smtp_host = models.TextField(null=True, blank=True)
    smtp_port = models.IntegerField(null=True, blank=True)
    smtp_username = models.TextField(null=True, blank=True)
    #: ⚠ A REFERENCE into the deployment's secret store (an env-var name, a
    #: vault path) — NEVER the password. No crypto kernel exists in this repo
    #: and the `tenants.ein` "plain for now" posture is deliberately not
    #: extended to a live credential; `sender_config.py` holds the reasoning
    #: and the write path, and is HUMAN-REVIEW-PENDING for exactly this call.
    smtp_secret_ref = models.TextField(null=True, blank=True)
    #: The from-address customers will see (A15: the utility's OWN address,
    #: never a shared sender). SPF/DKIM verification does not exist and the
    #: wire says so rather than implying it.
    sender_from_address = models.TextField(null=True, blank=True)

    #: BR-NOT-015 — the utility's DEVIATIONS from the platform's five rights
    #: clauses on a disconnection notice, keyed by clause code:
    #: `{"weather_suppression": {"enabled": false}, "dispute_rights": {"text": "…"}}`.
    #: `apps/notifications/rights_footer.py` owns the vocabulary, the defaults and
    #: the only write path.
    #:
    #: ⚠ **DEVIATIONS ONLY, AND THE EMPTY DICT IS THE POINT.** BR-NOT-015 requires
    #: the platform default to be VISIBLY MARKED as a default so it is never
    #: mistaken for the utility's own regulator's words — and with only deviations
    #: stored, "is this ours or theirs" is answered by whether the key is here.
    #: Pre-seeding five rows of platform text per tenant would need a SECOND column
    #: carrying the same claim, free to drift from the text beside it (hard-won
    #: law 1), and would freeze today's wording into every tenant provisioned
    #: before an improvement (hard-won law 4).
    #:
    #: JSON rather than a table because the CLAUSE SET is platform vocabulary, not
    #: tenant data: there are exactly five, they are named by BR-NOT-015, and a
    #: tenant cannot add a sixth. What varies per tenant is two facts about each —
    #: on/off and replacement wording — which is a settings value and belongs on
    #: the settings row (BR-TEN-031: framework in tenancy, CONTENT in the owning
    #: module).
    disconnect_rights_clauses = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notification_settings"
        constraints = [
            # US-NOT-004 TC-6, verbatim: *"Batch size set to 0 → Rejected —
            # dispatch requires a positive batch size"*. In the DDL as well as
            # in the service, because a zero here would make the dispatcher
            # select nothing and look, from every screen, like a provider
            # outage.
            models.CheckConstraint(
                condition=Q(dispatch_batch_size__gt=0),
                name="ck_notification_settings_batch_size",
            ),
            # A window that ENDS before it STARTS is not a window this schema
            # can hold. Reading `21:00–08:00` as "wraps midnight" would turn a
            # typo into the exact compliance incident BR-NOT-009 exists to
            # prevent (T5-23: *"a utility texting late-payment reminders at
            # 23:00"*). Whether a wrapping window should be EXPRESSIBLE is not
            # ruled anywhere; refusing to store one decides nothing and is
            # reversible, while accepting one silently decides everything.
            models.CheckConstraint(
                condition=Q(quiet_hours_start__lt=F("quiet_hours_end")),
                name="ck_notification_settings_quiet_window",
            ),
            # C-12 — a port outside TCP's range is not a port. NULL is lawful
            # (no SMTP configured); the service refuses first with a sentence,
            # this refuses last with certainty.
            models.CheckConstraint(
                condition=Q(smtp_port__isnull=True) | Q(smtp_port__gte=1, smtp_port__lte=65535),
                name="ck_notification_settings_smtp_port",
            ),
        ]


class InAppMessage(models.Model):
    """ONE delivered in-app message, sitting in ONE user's inbox — read or unread.

    BR-NOT-019 (PO 2026-08-17). This is the *"place for the message to land"*
    that `rule_catalog.UNAVAILABLE_CHANNELS["in_app"]` said did not exist, and
    the sentence there was amended in the same commit that created this table
    (hard-won law 1: a comment describing the product is a claim about it).

    ────────────────────────────────────────────────────────────────────────
    WHY THIS IS A SECOND TABLE AND NOT A COLUMN ON `outbound_messages`
    ────────────────────────────────────────────────────────────────────────
    `outbound_messages` is the QUEUE — what the platform undertook to send, one
    row per document per channel, written by a module and advanced only by the
    dispatcher. This is the MAILBOX — what a person has actually received and
    whether they have looked at it. They are different lifecycles owned by
    different actors, and conflating them breaks two ruled things at once:

    * **BR-NOT-005 makes the queue's status FORWARD-ONLY.** `read` is not a
      delivery status and never becomes one; a recipient marking a message read
      must not touch the row that records what the utility sent.
    * **A queue row is one MESSAGE; a mailbox row is one message × one
      RECIPIENT.** A staff FAILURE addressed to three System Admins (BR-NOT-021
      — the day this docstring predicted arrived on 2026-08-18) is ONE queue
      row and THREE inboxes. A `read_at` column on the queue row could only
      ever hold one of them.

    It is the same split `apps/notifications/models.OutboundMessage` already
    draws between the message and its provider response: the record of the
    sending and the record of the receiving are two facts.

    ────────────────────────────────────────────────────────────────────────
    `user_id` IS A PLAIN UUID, LIKE `returned_by` ABOVE
    ────────────────────────────────────────────────────────────────────────
    Not an FK to `identity.User`. B2 §2's reviewed cross-module FK set is a
    REVIEWED set — a lane does not add to it in passing — and this table already
    has the precedent it needs sitting on the row above it: `returned_at` /
    `returned_by` record which USER marked a letter returned and carry a plain
    uuid for exactly that reason. The B11 F-3 deferred-FK convention covers the
    same ground for `template_id`.

    ⚠ **WHAT THIS COSTS, STATED RATHER THAN IMPLIED:** PostgreSQL will not stop
    a row addressed to a user id that does not exist, and a soft-deleted user's
    inbox is still readable by nothing (the reads below are always scoped to the
    signed-in user). The mailbox is not a financial record and the queue row it
    points at IS the audit trail, so an orphan here loses no evidence.

    ────────────────────────────────────────────────────────────────────────
    WHO GETS A STAFF MESSAGE — RULED (BR-NOT-021), AND STILL NOT DECIDED HERE
    ────────────────────────────────────────────────────────────────────────
    ⚠ [AMENDED 2026-08-18] This section used to say the question was OQ-261,
    open, and promised: *"When OQ-261 closes, the audience widens and this
    table does not change."* Both halves came true: the PO ruled (2026-08-17,
    verbatim) *"the user who started the action, plus all System Admins for
    failures"*, `staff_recipients.py` resolves that audience, the snapshot's
    `recipients` list carries it, `in_app.deliver_batch` writes one row here
    per person — and NOT ONE COLUMN of this table changed. The writers (TWO
    until 2026-09-03, THREE now — DEF-3422):

    * `rule_service.queue_test` — *"a test goes to YOU and to nobody else"*
      (unchanged: a test is not a staff event and the ruling does not widen it).
    * `bulk_summary.queue_bulk_summary` — one message per bulk action
      (BR-NOT-020), one inbox per ruled recipient (BR-NOT-021).
    * `bulk_summary.queue_staff_alert` — one message when something the platform
      RAN came up short, published on `services` as the seam
      `apps/tenancy/sample_data.py` resolves by name. It goes through
      `queue_bulk_summary`, so it adds a caller and not a mechanism; still not
      one column of this table changed.

    ⚠ **AND THIS TABLE IS NOW THE BELL'S ONLY STORE.** `tenancy.bell_events`
    was dropped on 2026-09-03: it had no writer, no reader and no caller, and a
    second table behind one bell is two answers to *"what is in my bell"*
    (DEF-3422, decision log 2026-09-03).
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")

    #: WHOSE inbox. `identity.users.id`; a plain uuid — see the docstring.
    user_id = models.UUIDField()

    #: The queue row this was delivered FROM. In-module FK, so it is a real one:
    #: the mailbox entry must always be able to answer "which message was this,
    #: what template version rendered it, and when did the utility queue it".
    #: PROTECT rather than CASCADE — deleting a queue row is already forbidden
    #: for issued documents (CLAUDE.md rule 4) and a mailbox that outlives its
    #: own provenance is a message nobody can explain.
    outbound_message = models.ForeignKey(
        "notifications.OutboundMessage",
        on_delete=models.PROTECT,
        db_column="outbound_message_id",
        related_name="in_app_deliveries",
    )

    #: The RENDERED artifact, copied at delivery. Not re-rendered on read and not
    #: joined back to the template: BR-TEN-017 and BR-BIL-026 both say an issued
    #: document is never re-rendered, and a mailbox that re-rendered on every
    #: open would show a message that changed after it arrived.
    subject = models.TextField(null=True, blank=True)
    body = models.TextField()

    #: NULL = unread. A timestamp rather than a boolean because "when did the
    #: clerk see the failed bill run" is the question anybody asks afterwards,
    #: and a boolean cannot answer it. Forward-only in the service: there is no
    #: mark-as-unread, because BR-NOT-005's discipline is that a fact about
    #: delivery is never un-recorded.
    read_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "in_app_messages"
        indexes = [
            # The bell's unread count and the inbox list, which is EVERY read
            # this table has: one user's newest-first messages. Partial on
            # unread because the badge is the query that runs on every page.
            models.Index(
                fields=["tenant", "user_id"],
                condition=Q(read_at__isnull=True),
                name="ix_in_app_msgs_unread",
            ),
            models.Index(fields=["tenant", "user_id", "-created_at"], name="ix_in_app_msgs_inbox"),
        ]
        constraints = [
            # CLAUDE.md rule 6 at the DELIVERY end. The queue's own key stops a
            # second ROW being queued; this stops a second COPY being delivered
            # into the same inbox when a dispatch cycle re-runs over a row that
            # was claimed and not marked. Same argument, one layer down: a
            # delivery adapter that is idempotent by construction cannot double
            # up on a retry.
            models.UniqueConstraint(
                fields=["tenant", "outbound_message", "user_id"],
                name="uq_in_app_msgs_message_user",
            ),
        ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-001@2e6b19d (sha1[:7] of the four sources this slice was authored from, concatenated in order: 04-docs/02-decisions/02-database-design-brief.md — Addendum r10 #8 (delivery-queue shape) + r12 #16 (PLATFORM-WIDE) + r16 #1/#6/#7 — · 04-docs/05-modules/10-notifications/06-epics/EP-NOT-01-outbound-queue.md · 10-notifications/02-business-rules.md · 10-notifications/03-field-map.md, so a later change to any of them makes this stamp findable as stale in one grep)
# generated: 2026-08-11 by Eng-Lead (W3 notifications outbound-queue schema slice)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — models only) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the migrations' trailers — these classes and 0001/0002 ship together
# amended:   2026-08-11 by story-coder (queue-WRITE lane) — `UNAVAILABLE_REASONS`
#         gained a FIFTH value, `recipient_not_resolvable`, and nothing else in
#         this file moved: no column, no constraint, no index, so
#         `makemigrations --check` stays clean. The four existing values each
#         assert a fact about a PERSON ("this account holds no email address");
#         the new one asserts a fact about the PLATFORM ("customers publishes no
#         delivery-recipient read, so nobody looked"). Recording an unresolved
#         address as `no_email_address` would put a number on the dispatch home
#         that says N customers have no email address when the truth is that the
#         question was never asked — the same lie `apps/billing/release.py`
#         refuses about mandate coverage. REPORTED in the decision log, same
#         date; the value is engineering vocabulary, not a business ruling.
# exceptions: no dispatcher (US-NOT-002), no provider adapter (US-NOT-003) and
#         no send path of any kind. AMENDED 2026-08-11: this line used to read
#         "SCHEMA ONLY … and no queue-write service: module writers INSERT, and
#         their write paths are their own stories". There IS a queue-write
#         service now and it is THIS module's —
#         `apps/notifications/services.queue_document`, the ONLY write path into
#         this table (B1) — because a write path per module would have been four
#         implementations of BR-BIL-036's print floor and of CLAUDE.md rule 6.
#         Module writers still insert nothing themselves; they call it ·
#         the base B2 `notifications` table is REPLACED by this one and is not
#         built (field-map N-6 disposition, made here) · `notification_templates`
#         is EP-NOT-02 and is NOT built, so the template pin is plain columns
#         (B11 F-3 deferred-FK convention) · NO batch table: r10 #8 and r12 #16
#         name a batch ID, never a batch table, and the batch is minted by the
#         dispatcher · returned-mail / held markers (US-NOT-014) and the tenant
#         dispatch settings (US-NOT-004) are their own stories and are absent ·
#         UNPARTITIONED against B2 r16 #1 + NFR-24 ("born partitioned"), because
#         a monthly RANGE key would have to enter the unique constraint and
#         would switch the rule-6 idempotency guarantee off — REPORTED, see the
#         migration trailer and the docstring
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
