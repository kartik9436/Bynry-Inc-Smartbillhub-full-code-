# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-001 (`outbound_messages` — the platform-wide queue and the
#           ONLY write path into it)   Screens: S8 · S30 · S35
#           The stories that CALL this — the bill-release write, the receipt
#           write, the notice writes — are named in the docstring and not here:
#           G10 reads a Trace US-ID as "this file ships that story's test
#           cases", and this file ships the write path, not their callers.
# Rules:    BR-NOT-005 (EVERY email/SMS/print from ANY module is WRITTEN to the
#           outbound table first — never sent inline; the dispatcher on top
#           sends in tenant-config batches) · BR-BIL-016 (one delivery record
#           per document per channel; mass sends are never synchronous) ·
#           BR-BIL-036 (PRINT is the primary channel and the FLOOR — an account
#           with NO email address is normal, not an exception) · BR-BIL-026
#           (template + version pinned, so a reprint renders what was sent) ·
#           BR-NOT-006 (the pinning tuple includes the language variant) ·
#           BR-NOT-010 (v1 channels are print/email/SMS — door-hanger is not a
#           channel until v2) · BR-TEN-017 (the recipient is snapshotted at
#           queue time and never re-resolved) · BR-TEN-043 (event time is named
#           by the caller, never read from a clock) · BR-AUD-006 (no PII in the
#           audit trail) · CLAUDE.md rule 1 (tenant scoping; RLS FORCE) ·
#           rule 6 (idempotency — a re-emitted source event never queues a
#           second copy) · rule 7 (the queue write is audited)
# Rules:    [ADDED 2026-08-29 · CR-048 A1] BR-NOT-017 (ONE HOME for every
#           notification rule — and, from A1, one PLACE THAT READS IT: the
#           queue write path consults SET-12/SET-12D before it writes) ·
#           BR-NOT-018 (an event this platform cannot fire is named, never
#           guessed)
# Tests:    06-backend/tests/test_us_not_001_queue_write.py ·
#           06-backend/tests/test_us_not_001_outbound_queue.py (the table) ·
#           06-backend/tests/test_us_not_001_outbound_isolation.py (RLS) ·
#           06-backend/tests/test_cr048_a1_rule_at_queue_time.py (the rule join)
# Impacts:  apps/billing/delivery_seam.py (the bill-release caller — resolves
#           `queue_document` BY NAME, so billing never imports this module) ·
#           apps/payments · apps/reports · apps/ledger, whose writers will
#           resolve the same function the same way ·
#           CR-048 B6 (2026-08-30): `queue_document` also STAMPS the event it
#           was given and the channels the rule removed, so
#           `delivery_counts.py` can count per event without deriving one ·
#           apps/notifications/rule_service.py (`channel_switches`, the narrow
#           read this file consumes — CR-048 A1)
# ───────────────────────────────────────────────────────
"""notifications service layer — the ONLY write path into this module's tables.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this function is where CLAUDE.md rule 6
(idempotency keys) is honoured for the platform queue, and every row it writes
carries a customer's name, postal address, phone number or email address.
AI-authored 2026-08-11 under the PO ruling of 2026-08-09 ("AI will do it; we
will review it later as human"); row in 12-governance/09-human-review-ledger.md.

B1 boundary rule: other modules call `queue_document`; they never touch this
module's ORM. `outbound_messages` is the one table B1 opens to cross-module
WRITES (B2 r16 #7 adds it to the §2 reviewed interface register) — and this
function is what that exception means in practice. A writer that reached for
`OutboundMessage.objects.create` directly would bypass the print floor, the
audit row and the refusals below, all of which are the point.

╔══════════════════════════════════════════════════════════════════════════╗
║  THIS IS A QUEUE, NOT A DISPATCHER. NOTHING HERE SENDS ANYTHING.         ║
╚══════════════════════════════════════════════════════════════════════════╝

There is no SMTP call, no ESP call, no Twilio call and no print-vendor call in
this file, and there must not be one. R2 (`04-docs/02-decisions/12-engineering-plan.md`)
builds the QUEUE; **R4 is where email is switched on** — bills, receipts and
notices actually going out through providers — and until then a row that rests
`queued` is the finished, correct outcome of a bill run, not a pending failure.
BR-NOT-005 says it from the other end: *"EVERY email and text message from ANY
module is WRITTEN TO THE OUTBOUND TABLE first — never sent inline."* US-NOT-003
adds the channel timing: print/PDF dispatch is v1, email dispatch activates at
W6 (OQ-073 closed), SMS at v1.1 behind the Twilio seam — **but rows for all
three channels are written from day one**; only the SEND defers.

The dispatcher is US-NOT-002 and does not exist. So the columns it owns —
`batch_id`, `attempts`, `next_attempt_at`, `last_attempt_at`, `sent_at`,
`provider_reference`, `provider_response`, `last_error` — are never written
here, and a test asserts they ship empty. If you find yourself adding a send,
you are in the wrong file and probably the wrong release.

WHAT ONE CALL DOES
------------------
`queue_document` is ONE service function and ONE transaction boundary. For one
source document it writes one row per channel, idempotently, and audits. It
either does all of that or none of it.

  1. Refuses anything it cannot record honestly (unknown source kind, unknown
     channel, a bill with no template pin, no tenant context).
  1b. **Reads this utility's rule for the event, when the caller names one**
     (CR-048 A1) and drops the channels they have switched off. See
     `channel_decision`. A caller that names no event skips this entirely.
  2. Adds the FLOOR channel the rule requires — see below. AFTER 1b, always:
     a tenant setting may never take paper off a bill.
  3. Resolves each channel's recipient, or records that it could not.
  4. Writes one row per channel, skipping channels already queued for this
     source (rule 6), and lets the DATABASE be the final arbiter of that.
  5. Writes one `audit_log` row per row CREATED, in the same transaction.

────────────────────────────────────────────────────────────────────────────
PRINT IS THE FLOOR (BR-BIL-036), AND THE FLOOR IS ENFORCED HERE
────────────────────────────────────────────────────────────────────────────
BR-BIL-036, the PO's closure of OQ-091 on 2026-08-10:

    PRINT is the primary delivery channel; email and SMS are NOTIFICATIONS of
    the amount, not a replacement for the document. […] An account with NO
    email address is normal, not an exception — delivery must never assume one
    exists, and such an account still bills, still renders and still dispatches.

So a caller asking to queue a BILL to `("email",)` — a paperless customer — gets
an email row AND a print row. The floor is added by this function rather than
by each caller, because a rule that every writer has to remember is a rule that
one writer will eventually optimise away, and the customer whose paper bill
stopped arriving is the one who finds out.

⚠ **THIS PARAGRAPH USED TO SAY THE FLOOR WAS `invoice` ALONE, AND IT SAID SO FOR
HOURS AFTER THE PO WIDENED IT (`DEF-2467`, 2026-08-30).** Its exact words were:
*"`CHANNEL_FLOOR_BY_SOURCE` is deliberately narrow: BR-BIL-036 rules on BILLS, so
`invoice` is the only source kind with a floor. A receipt is "(opt)" in A15 and
nothing says a notice must go on paper, so neither gets one invented here."* Every
clause of that was true when written and false the moment `BR-NOT-024` was
amended to six kinds — and the lane that amended it (mine) edited the dict two
hundred lines below and left the prose describing the old world. **That is
CLAUDE.md law 1 in the file that documents the rule I had just changed:** a
comment claiming a guarantee is not the guarantee, and the next reader would have
learned the wrong rule from the most authoritative-looking place in the module.
It is corrected here rather than deleted, because the superseded reasoning is the
record of what was signed on 2026-08-29 and the amendment only reads against it.

**The floor is now SIX source kinds** — `invoice`, `payment`, `notice`, `plan`,
`account`, `move` — by the PO's ruling of 2026-08-29 that print is the floor on
every customer document, not only on bills. `CHANNEL_FLOOR_BY_SOURCE` below is
the single statement of it; read the dict, never this paragraph, and if the two
ever disagree the dict is right and this is another `DEF-2467`.

The floor is REPORTED as well as applied (`floor_channels_added`), so a caller
can see that it asked for one channel and got two.

────────────────────────────────────────────────────────────────────────────
IDEMPOTENCY (CLAUDE.md rule 6) — THE KEY IS THE DATABASE'S, NOT THIS FILE'S
────────────────────────────────────────────────────────────────────────────
B2 defines the key and `models.py` builds it:
`UNIQUE (tenant, source_type, source_id, channel, copy_no)`. This function does
not invent one and does not compute one — there is nothing to compute, which is
the whole argument for those five columns over a caller-supplied text key.

What it does is honour it twice over. It first SELECTs the rows already queued
for this source and skips those channels; that is the fast, ordinary path and
it is what makes a double-clicked release cheap. Then it creates the remainder
inside a savepoint and catches `IntegrityError`, because between the SELECT and
the INSERT a second worker may have won the race — and in that case the DATABASE
refused the duplicate, which is the only guarantee that survives a retry that
never called this function twice at all.

Both outcomes report the same thing to the caller: the row is queued, and this
call did not create it (`created=False`). A caller must never be told a message
was queued twice.

`copy_no` is the one deliberate door, and it is the caller's to open. Automatic
writers leave it 0, so a replay collides. A HUMAN asking for another copy of a
bill (US-BIL-024 TC-4) or a receipt (US-NOT-011 §5) passes `copy_no=1, 2, …`,
which is a different key and a genuinely new message. Note what is NOT a new
row: the dashboard re-queue action (US-NOT-013) resets an existing row's status
— same row, same `copy_no` — and it is the DISPATCHER's, not this function's.

────────────────────────────────────────────────────────────────────────────
A RECIPIENT THIS PLATFORM CANNOT RESOLVE IS RECORDED, NEVER GUESSED
────────────────────────────────────────────────────────────────────────────
Two different absences, kept apart because a dashboard counts them:

  * **The customer has none.** `unavailable_reason = no_email_address` (or
    `no_mobile_number`, `no_sms_opt_in`, `no_postal_address`). This is
    BR-BIL-036's normal case and it is a fact about a person.
  * **Nobody could look.** `unavailable_reason = recipient_not_resolvable`.
    Customers publishes no `delivery_recipients_for_account`; the email address
    lives in `contacts` and the SMS opt-in column does not exist at all
    (PROPOSED-SCHEMA, unbuilt). This is a fact about the PLATFORM, and calling
    it "no email address" would put a number on a screen that says 142 of this
    utility's customers have no email address when the truth is that nobody
    asked. `apps/billing/release.py` refuses the same lie about mandate
    coverage — *"'0 of 1,122 hold an address' and 'we could not count' must
    never render the same"* — and this is that rule applied to a row.

Either way a ROW IS WRITTEN. The channel is never silently skipped: a message
that was never queued leaves no trace anywhere, and the CHECK constraint
`ck_outbound_msgs_address_or_reason` makes the third possibility — a row with
neither an address nor a reason — unrepresentable.

The read is resolved BY NAME at call time (`RECIPIENT_READ`), the seam idiom
`apps/metering/seams.py` and `apps/billing/rating_seam.py` both use: nothing
here imports customers, and the day that lane publishes the selector this
function starts using it with no edit (hard-won law 2 — built is not wired).

────────────────────────────────────────────────────────────────────────────
WHAT THIS FILE DOES NOT DO
────────────────────────────────────────────────────────────────────────────
* **It does not send.** See the box above. R4.
* **It does not render.** The template PIN travels on the row; the document is
  rendered from that pinned version at dispatch (BR-BIL-026). There is no
  renderer in this repo (`apps/billing/documents.py` is one line) and BR-BIL-033
  wants one BEFORE issue — reported by the issue lane, not closed here.
* **It does not decide WHICH channels a customer elected.** That is the account
  delivery preference (`accounts.paperless` / `.sms_reminders`, both
  PROPOSED-SCHEMA and unbuilt), a customers-owned read; the caller names the
  channels and this function adds the floor. Inventing an election here would
  mean deciding, for every account on the platform, something no column says.
  ⚠ **The UTILITY's election is a different question and is now read here
  (CR-048 A1).** *Does this utility send bill-ready emails at all?* is stored on
  `notification_rules` / `notification_rule_channels`, edited on SET-12/SET-12D,
  and until 2026-08-29 it was read by nobody on this path — so switching *Bill
  ready — email* off changed nothing. `channel_decision` is that join. It stays
  strictly the UTILITY's answer: nothing here infers a CUSTOMER's election.
* **It does not advance a status**, stamp a batch or count an attempt.
* **It does not write `notice_history`** (r12 #7, payments-owned): US-NOT-001
  TC-3 makes that the WRITER's job alongside its queue row, and it is another
  module's table.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from importlib import import_module
from typing import Any

from django.db import IntegrityError, transaction

from apps.notifications import models

#: Imported for ONE thing: `encode_context`, the codec that lets a stored
#: render context survive a JSON round trip with its types (a Decimal is money,
#: a date is a date, and JSON has neither). It lives in `rendering.py` because
#: `rendering` owns the type→string mapping it has to be the inverse of.
from apps.notifications import rendering

#: The do-not-send list (DEF-NOT-5632). Imported for ONE thing: whether a new
#: row's address is on it, so the row is written HELD rather than queued to a
#: mailbox we have been told is dead. `suppression` imports `models` and
#: nothing from this file, so there is no cycle.
from apps.notifications import suppression

#: RE-EXPORTED, NOT IMPLEMENTED HERE — **DEF-163**, the rows without which no
#: tenant can send a notice. `apps.tenancy.seams.resolve` imports
#: `apps.<module>.services` and nothing else, so a seeder living in its own file
#: has to be published on this name to be reachable at provisioning. Exactly the
#: shape `apps.billing.services.seed_bill_templates` takes for DEF-123, and the
#: function still exists only once — `seed_templates.py` owns it.
from apps.notifications.seed_templates import seed_notice_templates  # noqa: F401
from core import audit, errors
from core import tenancy as core_tenancy


def queue_staff_alert(**alert: Any) -> dict[str, Any]:
    """PUBLISHED SEAM — **DEF-3422**. One in-app alert when something the
    platform ran came up short. `bulk_summary.queue_staff_alert` is the whole of
    it; this name exists because `apps.tenancy.seams.resolve` imports
    `apps.<module>.services` and nothing else, so a function living in its own
    file is unreachable from another module until it is published here.

    `apps/tenancy/sample_data.py` has resolved THIS EXACT NAME since C-15 landed
    and got `None` every time, and recorded the gap in its own audit row —
    *"support_alert: not delivered — apps.notifications.services publishes no
    staff-alert seam"*. Nothing was wrong with either module; the wire was
    missing, and the bell therefore read *"You're all caught up"* through every
    provisioning run that came up short.

    ⚠ THE IMPORT IS LOCAL AND HAS TO BE: `bulk_summary` imports this module, so
    a top-level import here would be a cycle whose behaviour depends on which of
    the two a caller happens to import first.
    """
    from apps.notifications import bulk_summary

    return bulk_summary.queue_staff_alert(**alert)


def queue_field_work_event(**event: Any) -> dict[str, Any]:
    """PUBLISHED SEAM — CR-168-BRC10 §F (TECHNICIAN SYNC DESIGN (5)). The
    office is told when a field job closes, when its required photos have all
    arrived, and when the field sent something that needs review. Work resolves
    THIS name (`apps/work/seams/notifications_seam.py`); the body lives in
    `field_work_events`, imported locally for `queue_staff_alert`'s reason.
    Never raises."""
    from apps.notifications import field_work_events

    return field_work_events.queue_field_work_event(**event)


def seed_notification_settings(actor: Any = None) -> dict[str, Any]:
    """CR-010 item 7 (PO 2026-08-17: *"we need ready to sue notification …
    there are many gaps in data seeding"*) — WRITE the dispatch-settings row at
    provisioning instead of on first read.

    The first-read `get_or_create` in `dispatch_config._row()` STAYS — it is
    the fallback for every tenant provisioned before this change, and belt-and-
    braces for any path that reaches the dispatcher first. What this adds is
    the row existing from day zero, which changes two real things: the S8
    Notifications tab opens populated rather than materialising its row on the
    first GET, and *"which tenants have configured notifications?"* becomes
    answerable from the database — before this, no row meant "never looked",
    indistinguishable from nothing.

    The VALUES are the model's own column defaults (batch 500 · quiet hours
    08:00–21:00 tenant time · email OFF · SMS OFF — BR-BIL-016, BR-NOT-009,
    and the OQ-073/074 closures), stated nowhere here so they cannot drift
    from what the first-read path would have written. Idempotent by
    `get_or_create`; a replay writes nothing.
    """
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    row, created = models.NotificationSettings.objects.get_or_create(tenant_id=tenant_id)
    # ── DEF-258 · THE OTHER HALF OF THE SAME SENTENCE ────────────────────────
    # CR-010 item 7 asks for two things and this function shipped one of them:
    # *"the NotificationSettings row is to be WRITTEN at provisioning … AND THE
    # SET-12 RULE ROWS WITH IT"*. The matrix stayed materialise-on-first-read,
    # so on the live database the dispatch row carried the provisioning
    # timestamp (2026-08-18 08:19:26) and the fifteen rule rows carried a
    # timestamp twenty hours later — the moment somebody opened the screen.
    #
    # They seed together HERE rather than through a second seam because the
    # requirement is one sentence about one screen, and splitting it is how the
    # half got lost the first time. `rule_service` is imported inside the
    # function: it imports this module at load time, and a module-level import
    # either way is a cycle.
    from apps.notifications import rule_service

    seeded_rules = rule_service.seed_rules()
    return {
        "created": created,
        "dispatch_batch_size": int(row.dispatch_batch_size),
        "email_dispatch_active": row.email_dispatch_active,
        "sms_dispatch_active": row.sms_dispatch_active,
        **seeded_rules,
    }

#: The customers read this module needs to address a message, named once so the
#: contract is greppable from BOTH sides of the boundary — exactly as
#: `apps/billing/release.py` names `mandate_coverage_for_accounts` and
#: `apps/billing/issue.py` names the ledger's two GL reads.
#:
#: Contract, for the lane that publishes it:
#:
#:     apps.customers.selectors.delivery_recipients_for_account(
#:         account_id, channels=("pdf_print", "email", "sms")
#:     ) -> dict[str, dict]
#:
#: One entry per channel it can speak to, each either
#: ``{"address": "...", "snapshot": {...}}`` or
#: ``{"unavailable_reason": "no_email_address"}``. A channel it OMITS is
#: reported as `recipient_not_resolvable` — omission means "not answered", and
#: is never read as "none on file". An entry carrying neither key is refused:
#: a read that answers neither question is a bug, not an absence.
RECIPIENT_MODULE = "customers"
RECIPIENT_READ = "delivery_recipients_for_account"

#: `queue_document(preferred_language=...)`'s default: READ the stated language
#: from `account_id` (PO option B, 2026-10-29). A sentinel rather than None,
#: because None is a real answer — *this customer states no preference* — and
#: must not be merged with *the caller did not say*.
FROM_ACCOUNT: Any = object()

#: ⛔⛔ **PRINT IS THE FLOOR ON EVERY CUSTOMER DOCUMENT — PO RULING 2026-08-29.**
#: Verbatim: *"this is correct - don't switch of print for any document it is
#: awayls on"*, answering the question of what happens when a utility switches an
#: event off ENTIRELY.
#:
#: ⚠ **THIS SUPERSEDES THE READING THIS TABLE SHIPPED WITH**, which is quoted
#: rather than deleted so the change is visible: *"it speaks about BILLS, so
#: `invoice` has a floor and nothing else does. A receipt is marked "(opt)" in
#: A15 and no signed document says a notice must go on paper — neither gets a
#: floor invented for it here."* That reading was correct about the SIGNED
#: documents and wrong about the product: it left a utility able to switch off
#: `notice`, which carries the DISCONNECTION LETTER — a document the law makes a
#: precondition of cutting somebody's water off. A15's *"(opt)"* on a receipt is
#: superseded by this ruling; `BR-BIL-036` is unchanged and is now the narrowest
#: case of a wider rule rather than the only one.
#:
#: ⚠ **THE FOUR CUSTOMER KINDS GET THE FLOOR. THE OTHER FOUR ARE NOT "SWITCHED
#: OFF" — THEY HAVE NO POSTAL SURFACE AT ALL**, and the difference matters:
#: `bulk_action` is a summary for the clerk who ran a job (its own comment in
#: `models.py` says *"a summary for a clerk is not a bill and nothing forces it
#: onto paper"*), `report` and `ledger` are internal, and `test` is the send-test
#: row addressed to the signed-in user — printing and posting a rehearsal would
#: spend a stamp to prove nothing. A staff alert has no envelope to go in; that
#: is not a channel being disabled.
CHANNEL_FLOOR_BY_SOURCE: dict[str, tuple[str, ...]] = {
    "invoice": (models.CHANNEL_PRINT,),  # BR-BIL-036, the original case
    "payment": (models.CHANNEL_PRINT,),  # a receipt — A15's "(opt)" superseded
    "notice": (models.CHANNEL_PRINT,),  # ⛔ THE DISCONNECTION LETTER
    "plan": (models.CHANNEL_PRINT,),  # a payment-plan notice
    # ── WIDENED 2026-08-30 · BR-NOT-024 amendment · PO ruling ──────────────
    # The table held the four above for one day. The merge lane put it back to
    # the PO that the four were NARROWER THAN WHAT THEY HAD ACTUALLY SAID —
    # *"don't switch of print for any document it is awayls on"* — and the PO
    # confirmed: *"Im okay with your suggestions, you are correct"*.
    #: The account-closed confirmation, the deposit-received confirmation and
    #: the rate-plan-change letter. **A deposit confirmation acknowledges MONEY
    #: RECEIVED, which is what a receipt is** — and that was the case that made
    #: the narrow reading indefensible.
    "account": (models.CHANNEL_PRINT,),
    #: The move-in welcome and the move-out final-bill letter. NOT separately
    #: ruled, and taken under the PRINCIPLE the ruling settled rather than left
    #: sitting on the old reasoning: a floor is per SOURCE KIND, this kind holds
    #: a letter announcing a customer's FINAL BILL, and a service-start
    #: confirmation is a contractual fact rather than a greeting.
    #: ⚠ **THE COST, STATED SO IT CAN BE OVERRULED CHEAPLY:** every move-in now
    #: queues a printed letter — order 600 a year for a 3,000-connection
    #: utility at 20% turnover. Removing this one line puts it back.
    "move": (models.CHANNEL_PRINT,),
}
#: ⚠ **WHAT IS DELIBERATELY NOT HERE, and it is four kinds and not three:**
#: `report`, `ledger`, `bulk_action` and `test`. The first three are internal —
#: a summary for the clerk who ran a job has no envelope. `test` is a rehearsal
#: addressed to the signed-in user, and posting one spends a stamp to prove
#: nothing (BR-NOT-027 names it exempt from the freeze rule for the same
#: reason). **Six kinds float, four do not, and together they are every member
#: of `models.SOURCE_TYPES` — `test_cr048_print_floor.py` asserts that
#: partition, so a NEW source kind fails there by name rather than defaulting
#: to no floor, which is exactly how the disconnection letter came to be
#: switch-off-able in the first place.**

#: BR-BIL-026 pins template + version on a BILL at issue and a reprint renders
#: that version forever. A bill queued without the pin could never say what was
#: sent, so an `invoice` row is refused without one. Other message classes have
#: no versioned-template table at all yet (EP-NOT-02), so they carry the code
#: and whatever pin their writer has.
PIN_REQUIRED_SOURCES: tuple[str, ...] = ("invoice",)

#: Problem codes carried on a `QueueWrite`. CODES, never prose — the dispatch
#: home (US-NOT-004) and the per-run dashboard (US-BIL-024) group on them, and
#: a screen cannot group on a sentence.
QUEUE_RECIPIENT_READ_UNPUBLISHED = "recipient_read_unpublished"
QUEUE_RECIPIENT_UNRESOLVED = "recipient_not_resolvable"
QUEUE_RECIPIENT_ABSENT = "recipient_absent_on_record"
QUEUE_FLOOR_CHANNEL_ADDED = "print_floor_channel_added"
QUEUE_ALREADY_QUEUED = "already_queued"
#: CR-048 A1 — the four things the rule join can have to say. CODES, for the
#: same reason as the five above: a bill run's report groups on them.
#: This utility has switched this channel off for this event (SET-12D).
QUEUE_CHANNEL_SWITCHED_OFF = "channel_switched_off_by_rule"
#: This utility has switched the whole event off (SET-12's master toggle).
QUEUE_EVENT_SWITCHED_OFF = "event_switched_off_by_rule"
#: The caller asked for a channel this EVENT has no toggle for, so the rule has
#: nothing to say about it and it is passed through. Reported, never dropped.
QUEUE_CHANNEL_UNRULED = "channel_has_no_rule_toggle"
#: The rule switched off a channel that BR-BIL-036 makes the floor. The floor
#: won. This has never fired in production and exists so that if it ever does,
#: it is on a report rather than in somebody's reasoning.
QUEUE_FLOOR_OVERRODE_RULE = "print_floor_overrode_rule"
#: DEF-NOT-5632 — this address is on the do-not-send list, so the row was
#: written HELD. A CODE like the others, because the bill run's report groups on
#: it, and REPORTED rather than silent for the reason `rule_suppressed_channels`
#: exists one table over: *"A SUPPRESSION IS A FACT ABOUT WHAT THE PLATFORM DID,
#: and before this column nothing recorded one."* A caller that queues five
#: hundred bills needs to be able to say how many went nowhere and why.
#:
#: ⚠ NOT the same fact as `QUEUE_CHANNEL_SWITCHED_OFF`, which is a utility
#: choosing not to send. This is a mailbox that cannot receive. One is a
#: setting a System Admin can change on a screen; the other is a bounced
#: address a clerk has to correct on the account.
QUEUE_ADDRESS_SUPPRESSED = "address_on_do_not_send_list"

#: Hard rule 7. `entity.action`, the dotted grammar `core.audit` documents.
AUDIT_ACTION = "outbound_message.queued"
AUDIT_ENTITY = "outbound_message"


class QueueWriteRefused(Exception):
    """This message cannot be queued, and here is why — in a clerk's words.

    Deliberately NOT one of the `core.errors` catalog exceptions: those carry
    an HTTP status because they answer a request, and a queue write runs inside
    a batch over thousands of bills where the right handling is to record the
    break and carry on (BR-BIL-055). `apps/billing/exceptions.py` states the
    same reasoning for `BillingRuleError`, and billing's delivery seam
    translates this into that type so one bad bill never stops a run.
    """


@dataclass(frozen=True)
class Recipient:
    """WHO one channel's copy goes to, as it stood at queue time (BR-TEN-017).

    Exactly one of `address` / `unavailable_reason` is set — the same law the
    table's `ck_outbound_msgs_address_or_reason` constraint enforces, stated
    here too so a caller finds out at the call rather than at the INSERT.

    `snapshot` is the rest of the envelope (name, address lines, care-of). It
    is a payload rather than columns because what a message needs is channel-
    and tenant-shaped, and a column per printed field puts a migration between
    a tenant and their own layout.
    """

    channel: str
    address: str | None = None
    snapshot: dict[str, Any] | None = None
    unavailable_reason: str | None = None


@dataclass(frozen=True)
class TemplatePin:
    """WHAT will render this message, frozen at queue time (BR-BIL-026).

    `language` is BR-NOT-006's fourth axis: the pinning tuple includes the
    language variant, so a reprint renders its pinned language forever.

    Plain values rather than a foreign key because `notification_templates` is
    EP-NOT-02 and does not exist — the B11 F-3 deferred-FK convention this repo
    already uses for `invoices.template_id`. A pin that waits for its table is
    a pin that is missing exactly when it is needed.
    """

    #: The human-readable handle (`bill_residential`, `receipt`). OPTIONAL,
    #: because `bill_templates` (r10 #4) is not built and a bill's writer has
    #: only the id + version frozen on the invoice. The PIN is the load-bearing
    #: half — it is what a reprint renders from — so a row must carry the code
    #: OR the pin, and an `invoice` must carry the pin either way.
    code: str | None = None
    template_id: Any = None
    version: int | None = None
    language: str | None = None


@dataclass(frozen=True)
class QueuedMessage:
    """One row of the queue, as this call left it.

    `created` is the honest answer to "did this call queue a message?" — False
    means the row was already there (a replay, a double-clicked release, a
    resumed batch). A caller must never be told a message was queued twice.
    """

    id: str
    channel: str
    status: str
    created: bool
    unavailable_reason: str | None = None


@dataclass(frozen=True)
class QueueWrite:
    """What one `queue_document` call left in the queue — and what it could not.

    `problems` travels for the same reason `issue.ISSUE_UNAVAILABLE` does: a
    caller must not have to INFER an absence, and a reviewer must not have to
    take a docstring's word for it (hard-won law 1). An unresolvable recipient
    is on this list AND on its row.
    """

    source_type: str
    source_id: str
    messages: tuple[QueuedMessage, ...] = ()
    problems: tuple[dict[str, Any], ...] = ()
    floor_channels_added: tuple[str, ...] = ()
    #: Stated as a VALUE, not only in prose: nothing was sent, and the caller
    #: can assert it. R4 is where this stops being true (see the module
    #: docstring's box).
    dispatched: bool = field(default=False)

    @property
    def created(self) -> tuple[QueuedMessage, ...]:
        return tuple(message for message in self.messages if message.created)

    @property
    def already_queued(self) -> tuple[QueuedMessage, ...]:
        return tuple(message for message in self.messages if not message.created)

    @property
    def channels(self) -> tuple[str, ...]:
        return tuple(message.channel for message in self.messages)


def _tenant_id() -> Any:
    """Hard rule 1: no tenant table is touched without `app.tenant_id` set.

    Refuse loudly rather than run an unscoped query and leave RLS as the only
    thing between one tenant's mailing list and another's. Same guard, same
    error, as `apps/billing/issue.py` and `apps/billing/release.py`. It matters
    more here than almost anywhere: a dispatcher, a maintenance command or a
    metrics job is exactly the kind of caller that runs outside a request.
    """
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _resolve(module: str, attribute: str, kind: str = "selectors") -> Any:
    """The owning module's callable, or None while it has not published one.

    getattr at CALL time — the idiom `apps/metering/seams.py`,
    `apps/billing/issue.py` and `apps/billing/release.py` all use. No import
    statement binds notifications to customers' internals, and the moment that
    lane lands its selector this function starts using it with no re-wiring.
    """
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - defensive
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


@dataclass(frozen=True)
class ChannelDecision:
    """WHICH channels this document goes out on, and what decided each one.

    ⚠ ADDED 2026-08-29 · CR-048 wave A task A1. `channels_for` used to be the
    whole answer and returned a tuple; it still does, and is now the thin
    wrapper over this. The richer shape exists because the rule join has things
    to SAY — a channel a utility switched off has to reach a bill run's report,
    or the settings screen goes back to being decoration in a different way
    (silently this time).

    `without_rule` is deliberately carried beside `channels`: it is what this
    call would have queued before A1 existed, so the difference between the two
    fields IS the change, assertable rather than argued.
    """

    source_type: str
    event_key: str | None
    #: Floor + everything the caller asked for. What shipped before A1, and what
    #: `_refuse_unless_writable` still validates — a caller's mistake is refused
    #: on what the CALLER did, never on what the tenant's rule left of it.
    without_rule: tuple[str, ...] = ()
    #: What is actually queued. Identical to `without_rule` when no event was
    #: named, which is still every caller in the product until CR-048 wave B.
    channels: tuple[str, ...] = ()
    #: Asked for, and switched off by this utility's rule.
    suppressed: tuple[str, ...] = ()
    #: Asked for, and this event has no toggle for it — passed through.
    unruled: tuple[str, ...] = ()
    #: Added by BR-BIL-036 because this source kind has a floor.
    floor_added: tuple[str, ...] = ()
    #: The rule said off and the FLOOR said on. The floor wins; this names it.
    floor_overrode_rule: tuple[str, ...] = ()
    #: SET-12's master switch for this event is off.
    event_switched_off: bool = False
    #: False when no event was named, so no rule was read and no tenant table
    #: was touched. The honest answer to "did the settings screen matter here?".
    rule_consulted: bool = False


def channel_decision(
    source_type: str,
    requested: tuple[str, ...],
    *,
    event_key: str | None = None,
    with_floor: bool = True,
) -> ChannelDecision:
    """Intersect the caller's ask with the tenant's rule, then put the floor on.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  THIS IS CR-048's ONE MISSING BOX. THREE INPUTS, IN THIS ORDER.      ║
    ╚══════════════════════════════════════════════════════════════════════╝

      1. **What the caller asked for.** Billing asks for what the account
         elected; payments asks for what the receipt election says.
      2. **∩ what this utility's rule permits** (`notification_rules` +
         `notification_rule_channels`, SET-12 / SET-12D). Subtractive, always:
         this step can only ever REMOVE. It is why nothing here can route
         around `rule_service`'s refusal to switch on a channel whose template
         is deactivated — a channel the rule holds off stays off, and a channel
         nobody asked for cannot be introduced by a rule.
      3. **THEN the floor** (BR-BIL-036). Last, so a rule can never take paper
         off a bill. The order is the rule: intersect first and floor second is
         a different product from floor first and intersect second, and the
         second one lets a settings toggle cancel a legal instrument.

    ────────────────────────────────────────────────────────────────────────
    WHY THE EVENT ARRIVES AS ITS OWN PARAMETER, AND NOT DERIVED FROM WHAT IS
    ALREADY ON THE CALL
    ────────────────────────────────────────────────────────────────────────
    Three things already travel and none of them can answer this, which was
    checked before the parameter was added rather than assumed:

    * **`source_type` is one-to-MANY onto events.** `invoice` is `bill_ready`
      OR `bill_corrected`; `payment` is `payment_received` OR `payment_failed`;
      `notice` is `past_due_reminder` OR `disconnect_notice`. Every one of those
      pairs is two different rows on SET-12 with two different sets of switches,
      so deriving the event from the source kind would apply one utility's
      answer to a question it was not asked — and the wrong half of that pair on
      a disconnect notice is a legal document suppressed by a setting about
      reminders.
    * **`category` is the CONSUMER category** (residential / commercial,
      BR-NOT-001), passed for the template variant. It is not an event
      category and shares no vocabulary with one.
    * **The template pin is ambiguous too.** `staff_bulk_summary` is the in-app
      class of BOTH `billing_run_completed` and `reconciliation_exceptions`,
      and a disconnect notice pins a per-TIER class (`disconnect_notice_10_day`
      and its siblings), not the event's own. A reverse map would be a guess
      wearing a lookup table.

    So: an explicit, optional, keyword-only `event_key`. **A caller that does
    not pass one is untouched** — no rule is read, no tenant table is touched,
    and the returned tuple is byte-identical to what this function returned
    before A1. That is not a courtesy; it is the contract, because billing,
    payments and customers all still call with a source type and no event, and
    wiring them is CR-048 wave B.

    ────────────────────────────────────────────────────────────────────────
    AN EVENT SWITCHED OFF ENTIRELY — THE JUDGMENT, AND THE LETTER THAT DECIDED
    ────────────────────────────────────────────────────────────────────────
    SET-12's master toggle off means **every channel the utility controls is
    suppressed, and the floor is not one of them.** Queue the floor, not
    nothing.

    The disconnection letter is what settles it. A utility that switches off
    *Disconnect notice* has said "stop notifying" — it has NOT been offered, and
    must not be handed, a switch that stops the platform printing a document the
    law makes a precondition of disconnection. So the floor survives the master
    toggle for exactly the same reason it survives a per-channel toggle: it is a
    PLATFORM rule about what a document is, not a tenant preference about
    whether to be in touch, and SET-12D does not edit platform rules.

    ⚠ **THAT QUESTION WAS OPEN WHEN THIS WAS WRITTEN, AND IT IS NOW CLOSED
    (BR-NOT-024, PO 2026-08-29).** This paragraph used to read *"a `notice` HAS
    NO FLOOR TODAY … so a utility switching `disconnect_notice` off today does
    stop the letter"*, reported to CR-048 as a signed-rule question rather than
    closed by a lane adding a dictionary entry. The PO ruled it, verbatim:
    *"this is correct - don't switch of print for any document it is awayls
    on"*. `CHANNEL_FLOOR_BY_SOURCE` now carries all four customer document
    kinds — `invoice`, `payment`, `notice`, `plan` — so the disconnection
    letter is posted whatever this screen says. The paragraph is kept rather
    than deleted because the reasoning above only makes sense against the
    narrower table it was written for.

    When the intersection empties the list, `queue_document` returns an EMPTY
    write carrying the reason rather than raising: a tenant switching a setting
    off is not something a human must be asked to repair, and a refusal inside a
    five-hundred-bill run is a named break per bill (BR-BIL-055). It is not
    silent, which is what makes an empty write legitimate here — the module
    docstring's objection to empty writes is to ones that say nothing.

    No clock is read (BR-TEN-043) and nothing is written: two SELECTs, both
    inside the tenant's own context (hard rule 1).
    """
    # `with_floor=False` is `queue_document`'s, for a correction of ONE
    # channel's delivery (DEF-NOT-10650) — see the parameter there.
    floor = CHANNEL_FLOOR_BY_SOURCE.get(source_type, ()) if with_floor else ()
    asked = tuple(requested)

    def _ordered(*groups: tuple[str, ...]) -> tuple[str, ...]:
        seen: list[str] = []
        for group in groups:
            for channel in group:
                if channel not in seen:
                    seen.append(channel)
        return tuple(seen)

    without_rule = _ordered(floor, asked)
    if event_key is None:
        return ChannelDecision(
            source_type=source_type,
            event_key=None,
            without_rule=without_rule,
            channels=without_rule,
            floor_added=tuple(channel for channel in floor if channel not in asked),
        )

    # Imported inside the function: `rule_service` imports THIS module at load
    # time, so a module-level import either way is a cycle. The same idiom
    # `seed_notification_settings` above already uses, for the same reason.
    from apps.notifications import rule_service

    try:
        switches = rule_service.channel_switches(event_key)
    except KeyError:
        from apps.notifications import rule_catalog

        raise QueueWriteRefused(
            f"{event_key!r} is not a notification event this platform can fire, so there "
            "is no rule to read for it and no way to know whether this utility wants the "
            f"message sent. The events are: {', '.join(rule_catalog.EVENT_KEYS)}. The set "
            "is a CONSTANT — only a writer in this codebase can fire an event, so a "
            "utility cannot invent one and neither can a caller."
        ) from None

    # ══════════════════════════════════════════════════════════════════════
    # `CR-084` — THE PLATFORM OFFERS THE PORTAL; THE RULE DECIDES
    # ══════════════════════════════════════════════════════════════════════
    #
    # ⚠ **STEP 2 ABOVE SAYS THE RULE CAN ONLY EVER REMOVE, AND THAT INVARIANT IS
    # KEPT — WHAT MOVED IS WHO OFFERS THIS CHANNEL.**
    #
    # A caller's `requested` list is an ELECTION: billing asks for what the
    # customer chose, payments for what the receipt election says, and that is
    # why a rule may never add to it — a tenant preference must not introduce a
    # channel the customer was never asked about.
    #
    # **The portal is not an election.** It needs no address the customer had to
    # give us, it costs nothing, and its destination is the customer's own copy
    # of their own document, on a screen they already have. So it is offered by
    # the PLATFORM, like the print floor one step below, on the events whose
    # catalogue lists it — and the tenant's switch then REMOVES it exactly as it
    # removes email. The rule is still subtractive; the offer is simply not the
    # caller's to make.
    #
    # It is gated on `event.channels` and not on a constant, so a portal row can
    # only ever be written for an event whose settings screen draws a portal
    # toggle. A delivery nobody can switch off is the thing this whole file
    # exists to prevent.
    from apps.notifications import rule_catalog as _catalog

    offered = _catalog.event(event_key)
    if models.CHANNEL_PORTAL in offered.channels and models.CHANNEL_PORTAL not in asked:
        asked = asked + (models.CHANNEL_PORTAL,)
        # `without_rule` is *what would go out if no rule were read*, and the
        # offer is the platform's rather than the rule's — so it belongs in that
        # baseline. Left out, a reader comparing the two lists would see the
        # portal appear only in `channels` and conclude the RULE had added it,
        # which is the one thing the paragraph above says never happens.
        without_rule = _ordered(floor, asked)

    kept: list[str] = []
    suppressed: list[str] = []
    unruled: list[str] = []
    for channel in asked:
        permitted = switches.permits(channel)
        if permitted is None:
            # This event has no toggle for this channel, so the rule has nothing
            # to say. Passed through and REPORTED — dropping it would suppress a
            # message no utility could switch back on, which is this settings
            # screen lying in the other direction.
            unruled.append(channel)
            kept.append(channel)
        elif permitted and switches.event_enabled:
            kept.append(channel)
        else:
            suppressed.append(channel)

    channels = _ordered(floor, tuple(kept))
    return ChannelDecision(
        source_type=source_type,
        event_key=event_key,
        without_rule=without_rule,
        channels=channels,
        suppressed=tuple(suppressed),
        unruled=tuple(unruled),
        # A floor channel not in the KEPT set was added by the floor — including
        # the case where the caller asked for it and the rule took it away.
        floor_added=tuple(channel for channel in floor if channel not in kept),
        floor_overrode_rule=tuple(channel for channel in floor if channel in suppressed),
        event_switched_off=not switches.event_enabled,
        rule_consulted=True,
    )


def channels_for(
    source_type: str,
    requested: tuple[str, ...],
    *,
    event_key: str | None = None,
) -> tuple[str, ...]:
    """The channels this document is queued to, WITH the floor (BR-BIL-036).

    Published separately from `queue_document` so the floor is assertable and
    quotable on its own: a caller — or a test, or a future reader wondering
    whether a paperless customer still gets paper — can ask this question
    without writing a row. Order is stable: the floor first, then whatever the
    caller asked for, de-duplicated.

    ⚠ **THAT PROPERTY IS WHY THE RULE JOIN LIVES HERE AND NOT IN
    `queue_document` (CR-048 A1).** The question the CR is about — *"we switched
    Bill ready — email off; does this bill still get an email?"* — is the same
    kind of question as *"does a paperless customer still get paper?"*, and it
    must be answerable the same way: without writing a row, in one function, in
    a sentence a reviewer can quote. Putting the intersection in
    `queue_document` instead would have left this function answering a question
    the queue no longer asks, which is a published contract free to disagree
    with the product — and this module already has one rule about that
    (`_channel_dispatch_facts`: *"reproducing the reasoning here would be a
    second copy free to disagree with the dispatcher's"*).

    Pass `event_key` and this utility's SET-12 rule is intersected in; omit it
    and nothing changes — no rule is read and no tenant table is touched.
    `channel_decision` carries the same answer with its reasons attached; this
    returns the tuple, which is what four existing assertions ask it for.
    """
    return channel_decision(source_type, requested, event_key=event_key).channels


def template_class_for_event(event_key: str, channel: str) -> str | None:
    """The WORDING class an event's message uses on one channel, or None.

    `DEF-BIL-10530` (PO 2026-10-22). Read off the SET-12 catalogue
    (`rule_catalog.EVENTS[…].template_classes`) — the same map the settings
    screen draws its template column from — so a writer that queues a
    document's email never types a class code of its own. `bill_ready` answers
    `email_bill_ready` / `sms_bill_ready`; `bill_corrected` answers
    `email_corrected_bill` and None for SMS. None is an answer, not an error:
    the portal and print carry the DOCUMENT and have no wording class at all.

    **A constant read: no query.** SET-12D also stores a per-utility
    `notification_rule_channels.template_code`, which only its *Send test*
    reads; no document writer reads it (receipts pin `email_payment_receipt`
    by constant too), and reading it here would add a SELECT per bill to the
    issue transaction whose rule read is budgeted at two
    (`test_cr048_b2__the_rule_read_is_two_selects_and_writes_nothing`). Whether
    that stored choice should govern real messages is a question for every
    writer at once, not for this fix.
    """
    from apps.notifications import rule_catalog  # local: rule_service imports this module

    try:
        event = rule_catalog.event(event_key)
    except KeyError:
        return None
    return event.template_classes.get(channel) or None


def _rule_problems(decision: ChannelDecision) -> tuple[dict[str, Any], ...]:
    """What the rule join has to SAY about this write, in a clerk's words.

    CR-048's finding was that the rule was ignored. The fix must not create the
    opposite failure — a rule obeyed so quietly that nobody can tell why a
    customer with an email address got no email. Every channel this join removed
    is named here, and `problems` is already the channel a bill run's dashboard
    reads (US-BIL-024 groups on `code`).

    Sentences, not ids: a person reading a run report should learn what to do
    about it, which is *go to the notifications screen and switch it back on*.
    """
    if not decision.rule_consulted:
        return ()
    problems: list[dict[str, Any]] = []
    if decision.event_switched_off:
        problems.append(
            {
                "code": QUEUE_EVENT_SWITCHED_OFF,
                "br_ref": "BR-NOT-017",
                "event_key": decision.event_key,
                "detail": "this utility has switched this notification off entirely on "
                "Settings → Notifications, so nothing is queued for it beyond what the "
                "platform prints regardless. Switch the notification back on there to "
                "start sending it again.",
            }
        )
    for channel in decision.suppressed:
        problems.append(
            {
                "code": QUEUE_CHANNEL_SWITCHED_OFF,
                "br_ref": "BR-NOT-017",
                "event_key": decision.event_key,
                "channel": channel,
                "detail": f"this utility has switched {channel} off for this notification "
                "on Settings → Notifications, so no message was queued on it — even "
                "though the document asked for it. This is a choice, not a fault: turn it "
                "back on from that screen if it was not meant.",
            }
        )
    for channel in decision.unruled:
        problems.append(
            {
                "code": QUEUE_CHANNEL_UNRULED,
                "br_ref": "BR-NOT-018",
                "event_key": decision.event_key,
                "channel": channel,
                "detail": f"this notification has no {channel} switch on Settings → "
                f"Notifications, so nobody can turn {channel} off for it and the message "
                "was queued. Suppressing it here instead would leave a message no one "
                "could switch back on.",
            }
        )
    for channel in decision.floor_overrode_rule:
        problems.append(
            {
                "code": QUEUE_FLOOR_OVERRODE_RULE,
                "br_ref": "BR-BIL-036",
                "event_key": decision.event_key,
                "channel": channel,
                "detail": f"this utility has {channel} switched off for this notification, "
                "and the document was queued to it anyway: every bill is printed, whatever "
                "else it is also sent by. That is a platform rule about what a bill is, "
                "and the notifications screen does not edit it.",
            }
        )
    return tuple(problems)


def _refuse_unless_writable(
    *,
    source_type: str,
    source_id: Any,
    channels: tuple[str, ...],
    template: TemplatePin | None,
    copy_no: int,
) -> None:
    """Everything that must be TRUE before a row is written, in one place.

    All of it is cheap, and all of it produces an unrepairable row if skipped:
    a queue row with a source kind nothing dispatches, a channel no adapter
    exists for, or a bill with no template pin is a message that can never be
    sent and can never be explained.
    """
    if source_type not in models.SOURCE_TYPES:
        raise QueueWriteRefused(
            f"{source_type!r} is not a source kind this platform queues "
            f"({', '.join(models.SOURCE_TYPES)}). The vocabulary is a CONSTANT, not a "
            "tenant lookup — a tenant cannot invent a source the platform has no writer "
            "for, and a row nothing recognises is a message nothing will ever send."
        )
    if source_id is None:
        raise QueueWriteRefused(
            "a queue row needs the id of the document it is delivering (US-NOT-001 §5 "
            "marks the source ref REQUIRED). It is also part of the idempotency key, and "
            "a NULL anywhere in a unique key switches uniqueness off in PostgreSQL — so a "
            "sourceless row would quietly lose the no-duplicate guarantee too."
        )
    if not channels:
        raise QueueWriteRefused(
            "no channel was named and this source kind has no floor channel, so there is "
            "nothing to queue. An empty write would return success having delivered "
            "nothing — the shape a silently-dropped message has."
        )
    unknown = [channel for channel in channels if channel not in models.CHANNELS]
    if unknown:
        raise QueueWriteRefused(
            f"unknown delivery channel(s) {', '.join(sorted(unknown))}. v1 channels are "
            f"{', '.join(models.CHANNELS)} (r12 #16, US-NOT-003 §4); BR-NOT-010 keeps "
            "door-hanger out until v2. A channel with no adapter is a row that rests "
            "queued forever with nobody looking for it."
        )
    if copy_no < 0:
        raise QueueWriteRefused(
            f"copy_no {copy_no} is negative. 0 is the delivery record BR-BIL-016 "
            "mandates and 1, 2, … are the deliberate extra copies a HUMAN asked for; "
            "there is no message below the first one."
        )
    if template is None or not (
        template.code or (template.template_id is not None and template.version is not None)
    ):
        raise QueueWriteRefused(
            "a queue row says what it will be rendered from — the template CODE, or the "
            "pinned id + version (US-NOT-001 §1). With neither, the dispatcher has a "
            "recipient and a channel and no idea what to put in the envelope. The code is "
            "optional rather than required because `bill_templates` (r10 #4) is not built "
            "and a bill's writer holds only the pin frozen on the invoice."
        )
    if source_type in PIN_REQUIRED_SOURCES and (
        template.template_id is None or template.version is None
    ):
        raise QueueWriteRefused(
            f"a {source_type} is queued with its template VERSION pinned (BR-BIL-026): "
            "a reprint renders the pinned version forever, and a bill queued without the "
            "pin can never say what the customer was actually sent. The pin is stamped on "
            "the bill at issue — pass the invoice's own `template_id` and "
            "`template_version`, never today's published version."
        )


#: A queue row was written carrying a template CODE and no version, and the
#: registry could not resolve one. Reported, never guessed.
QUEUE_PIN_UNRESOLVED = "template_pin_unresolved"
#: The pin was resolved here, at queue time, rather than supplied by the caller.
QUEUE_PIN_RESOLVED = "template_pin_resolved_at_queue_write"


def _pinned(
    template: TemplatePin,
    *,
    category: str | None,
    language: str | None,
    on_date: Any,
    stated: str | None = None,
) -> tuple[TemplatePin, dict[str, Any] | None]:
    """Stamp the version pin onto a row AT QUEUE TIME (BR-BIL-026).

    `language` is the utility's default and `stated` the customer's own; the
    language actually asked for is `message_language.language_for` of the two
    (PO option B, 2026-10-29), and the pin records the variant's language as
    resolved — the language ACTUALLY used.

    ⚠ ADDED 2026-08-15 by the notifications CONTENT lane, and it is the reason
    anything renders at all. The field map §1 always said the row carries
    *"template code + PINNED VERSION REF … renders pinned version at dispatch"*,
    and until `notification_templates` existed there was nothing to resolve, so
    rows were written with a code and no version. Resolution has to happen HERE
    and not at dispatch: a template published between queueing and dispatch must
    not change the document, which is BR-BIL-026 in one sentence.

    A caller that already holds a pin (billing, from the invoice) keeps it —
    an issued bill's pin is a fact about that bill and is never re-resolved.

    Failure is REPORTED, never guessed: the row is still written (a message that
    was never queued leaves no trace) and it holds with the missing-template
    reason at dispatch, which is field map N-1's ratified posture.
    """
    from apps.notifications import template_service  # local: avoids an import cycle

    if template.template_id is not None and template.version is not None:
        return template, None
    if not template.code:
        return template, None
    from apps.notifications import message_language  # local: avoids an import cycle

    try:
        resolved = template_service.resolve(
            code=template.code,
            category=category,
            language=message_language.language_for(
                template.code,
                stated=stated,
                utility=language,
                category=category,
                on_date=on_date,
            ),
            on_date=on_date,
        )
    except template_service.TemplateRefused as unresolved:
        return template, {
            "code": QUEUE_PIN_UNRESOLVED,
            "br_ref": "BR-BIL-026",
            "template_code": template.code,
            "detail": f"{unresolved} The row is written anyway and will HOLD at dispatch "
            "with this reason — a message that was never queued leaves no trace, and a "
            "message rendered from a template nobody published would be content invented "
            "by this platform.",
        }
    return (
        TemplatePin(
            code=template.code,
            template_id=resolved.template_id,
            version=resolved.version,
            # J22 step 3: the language ACTUALLY used is what the pin records —
            # *"never a blank, never an unrecorded inference"*.
            language=resolved.language,
        ),
        {
            "code": QUEUE_PIN_RESOLVED,
            "br_ref": "BR-NOT-006",
            "template_code": template.code,
            "via": resolved.via,
            "fell_back": resolved.fell_back,
            "detail": f"pinned {template.code} v{resolved.version} "
            f"({resolved.category}/{resolved.language}) at queue time via {resolved.via}. "
            "The pin is frozen here so a template published between now and dispatch "
            "cannot change this document (BR-BIL-026).",
        },
    )


# ══════════════════════════════════════════════════════════════════════════
# THE FIELDS THE CALLER FORGOT — ADDED 2026-09-07 (`DEF-PAY-4409`)
# ══════════════════════════════════════════════════════════════════════════
# **WHAT THIS EXISTS FOR, in one sentence: a document with every field blank is
# not a document, and until today nothing anywhere said so.**
#
# The Product Owner opened a waiting receipt on Settings → Notifications and
# read `Hi ——, … Amount —— Date —— Method —— Confirmation ——`. Nothing was
# broken: the template was right, the renderer was right, and
# `apps/payments/receipts.py` had simply never passed a `render_context` — a
# parameter two sibling callers pass and it did not have. **Every check in this
# repo was green over it**, and each was green truthfully: no exception is
# raised, the row is well formed, the email is valid, and `rendering` prints the
# named absence exactly as OQ-117 ratified. The renderer even COUNTS the
# absences — and nothing has ever read the count.
#
# ⚠ **IT REPORTS AND IT NEVER REFUSES, AND THAT IS A RULING RATHER THAN
# TIMIDITY.** A refusal here would fail the queue write, and a queue write is
# reached from inside a bill run (BR-BIL-055), a money transaction
# (`payments.receipts`) and a committed move-out. Turning "this letter will have
# a blank line on it" into "this bill run died" is a worse defect than the one
# being fixed. The gap rides on `problems`, which is where every other thing
# this function noticed already rides.
#
# ⚠ **WHAT WOULD MAKE IT PASS WRONGLY — the question hard-won law 7 says to ask
# before trusting a check.** Three answers, and each is why the comparison is
# shaped the way it is:
#
#   1. *A token the RENDERER fills in.* `{support_phone}` and `{utility_name}`
#      are stamped from the tenant's Settings → Company at render, so a caller
#      that never mentions them is correct. Subtracted, from
#      `rendering.RENDERER_SUPPLIED`, which is DERIVED from the function that
#      does the merging rather than typed out beside it.
#   2. *A token that is legitimately OPTIONAL.* A cash payment has no
#      confirmation number and a payment that met no bill has no bill number.
#      This is the whole reason the test is **`key in context`** and not
#      `context[key] is not None`: a caller that passes `confirmation=None` has
#      STATED that this document has no confirmation number, and is silent; a
#      caller that never mentions the key has forgotten it, and is named. The
#      convention costs a caller one `None` and it is what makes a deliberate
#      absence and an oversight two different things for the first time.
#   3. *A body with no tokens at all.* `bill_insert` has none, so there is
#      nothing to report and nothing is reported.
#
# ⚠ **AND IT PRINTS WHAT IT COULD NOT SEE.** A check that cannot cover its whole
# subject must say so with a NUMBER beside it, or a declared blind spot is
# indistinguishable from an empty one (hard-won law 7, `G32`'s truthful zero
# over 21 live refusals). A row with no resolved pin has no body to compare
# against and gets `QUEUE_CONTEXT_UNCHECKED` naming the reason — never silence.
QUEUE_CONTEXT_GAP = "render_context_missing_tokens"
QUEUE_CONTEXT_UNCHECKED = "render_context_not_checked"


def _context_gap(
    template: TemplatePin, render_context: dict[str, Any] | None
) -> tuple[dict[str, Any], ...]:
    """Tokens this document's PINNED body declares that the caller never named.

    Returns at most one problem row. Never raises: this runs on the one write
    path into `outbound_messages`, and a guard that can take a bill run down is
    a worse defect than the one it reports.
    """
    from apps.notifications import rendering as _rendering  # local: import cycle
    from apps.notifications import template_service  # local: import cycle

    if template is None or template.template_id is None or template.version is None:
        return (
            {
                "code": QUEUE_CONTEXT_UNCHECKED,
                "br_ref": "BR-NOT-012",
                "template_code": getattr(template, "code", None),
                "detail": "this row carries no pinned template version, so there is no body "
                "to compare the caller's merge values against and NOTHING was checked. Said "
                "out loud because a check that silently skips part of its subject reads "
                "exactly like a check that found nothing wrong.",
            },
        )
    try:
        pinned = template_service.load_pinned(
            template_id=template.template_id, version=template.version
        )
        declared = set(_rendering.tokens_in(pinned.body or "")) | set(
            _rendering.tokens_in(pinned.subject or "")
        )
    except Exception as failure:  # noqa: BLE001 — a guard may not break the queue
        return (
            {
                "code": QUEUE_CONTEXT_UNCHECKED,
                "br_ref": "BR-NOT-012",
                "template_code": template.code,
                "detail": f"the pinned body could not be read, so the caller's merge values "
                f"were NOT checked against it: {failure}",
            },
        )
    missing = sorted(declared - _rendering.RENDERER_SUPPLIED - set(render_context or {}))
    if not missing:
        return ()
    return (
        {
            "code": QUEUE_CONTEXT_GAP,
            "br_ref": "BR-NOT-012 · DEF-PAY-4409",
            "template_code": template.code,
            "tokens": tuple(missing),
            "detail": f"{len(missing)} of the {len(declared)} merge fields this document's "
            f"body uses were not supplied by the caller ({', '.join(missing)}), so each one "
            "will print as a named absence. Pass the value, or pass the key with no value to "
            "state that this document genuinely has none — the queue cannot tell a figure "
            "nobody had from a figure nobody remembered.",
        },
    )


def _recipients_for(
    *,
    account_id: Any,
    channels: tuple[str, ...],
    supplied: dict[str, Recipient],
) -> tuple[dict[str, Recipient], tuple[dict[str, Any], ...]]:
    """One `Recipient` per channel — supplied, resolved, or honestly unresolved.

    THE CALLER WINS. A writer that knows its own recipient states it: the
    bookkeeper's address on a scheduled report (US-NOT-015) is a staff address
    and belongs to no customer account, so there is nothing to look up.

    Everything else goes through the published customers read. While that read
    does not exist, every unsupplied channel comes back
    `recipient_not_resolvable` with the gap named in `problems` — never a
    fabricated address, never a `no_email_address` this module did not verify,
    and never a skipped row.
    """
    resolved: dict[str, Recipient] = {}
    problems: list[dict[str, Any]] = []
    wanted = [channel for channel in channels if channel not in supplied]
    resolved.update({channel: supplied[channel] for channel in channels if channel in supplied})
    if not wanted:
        return resolved, ()

    read = _resolve(RECIPIENT_MODULE, RECIPIENT_READ) if account_id is not None else None
    answered: dict[str, Any] = {}
    if read is None:
        problems.append(
            {
                "code": QUEUE_RECIPIENT_READ_UNPUBLISHED,
                "br_ref": "BR-TEN-017",
                "detail": (
                    f"apps.{RECIPIENT_MODULE}.selectors.{RECIPIENT_READ} is not published"
                    if account_id is not None
                    else "no account was named, so there is no customer record to address "
                    "this message from"
                )
                + ", so the recipient could not be resolved for "
                f"{', '.join(wanted)}. The email address lives in customers' `contacts` "
                "and the SMS opt-in column is unbuilt (PROPOSED-SCHEMA); notifications "
                "has no reviewed read into either and does not guess. The rows are "
                "WRITTEN and say so — an unresolved address is recorded, never inferred "
                "to be absent and never left unqueued.",
            }
        )
    else:
        answered = dict(read(account_id, channels=tuple(wanted)) or {})

    for channel in wanted:
        entry = answered.get(channel)
        if entry is None:
            resolved[channel] = Recipient(
                channel=channel, unavailable_reason=models.REASON_NOT_RESOLVABLE
            )
            problems.append(
                {
                    "code": QUEUE_RECIPIENT_UNRESOLVED,
                    "br_ref": "BR-BIL-036",
                    "channel": channel,
                    "detail": f"no address could be resolved for {channel}. UNKNOWN is not "
                    "the same fact as none-on-file and is not recorded as one; the row "
                    "carries `recipient_not_resolvable` so a dashboard can count the two "
                    "apart.",
                }
            )
            continue
        address = entry.get("address")
        reason = entry.get("unavailable_reason")
        if bool(address) == bool(reason):
            raise QueueWriteRefused(
                f"apps.{RECIPIENT_MODULE}.selectors.{RECIPIENT_READ} answered {channel!r} "
                "with neither an address nor a reason (or with both). Exactly one is a "
                "recipient; the other shape is a row that looks queued, will never be "
                "delivered, and says nothing about why."
            )
        if reason:
            problems.append(
                {
                    "code": QUEUE_RECIPIENT_ABSENT,
                    "br_ref": "BR-BIL-036",
                    "channel": channel,
                    "detail": f"this account has no {channel} address on record "
                    f"({reason}). BR-BIL-036: that is normal, not an exception — the "
                    "print row is unaffected and the bill still goes out.",
                }
            )
        resolved[channel] = Recipient(
            channel=channel,
            address=address,
            snapshot=entry.get("snapshot"),
            unavailable_reason=reason,
        )
    return resolved, tuple(problems)


def _audit_created(
    row: models.OutboundMessage,
    *,
    actor: Any,
    job: str | None,
) -> None:
    """Hard rule 7 for the queue write, inside the caller's transaction.

    NO PII (BR-AUD-006). The trail records that a message was queued, on which
    channel, for which document, and whether it had an address — never the
    address itself, the phone number or the customer's name. Those are on the
    row, for anyone entitled to read it.
    """
    audit.money_action(
        actor,
        AUDIT_ACTION,
        AUDIT_ENTITY,
        str(row.pk),
        before=None,
        after={
            "source_type": row.source_type,
            "source_id": str(row.source_id),
            "channel": row.channel,
            "copy_no": row.copy_no,
            "status": row.status,
            "account_id": str(row.account_id) if row.account_id else None,
            "template_code": row.template_code,
            "template_version": row.template_version,
            "template_language": row.template_language,
            # BR-AUD-006 — the FACT of an address, never the address.
            "address_present": row.recipient_address is not None,
            "unavailable_reason": row.unavailable_reason,
            "dispatch_not_before": (
                row.dispatch_not_before.isoformat() if row.dispatch_not_before else None
            ),
            "dispatched": False,  # a queue write never sends (R4)
            "job": job if actor is None else None,
        },
    )


def queue_document(
    *,
    source_type: str,
    source_id: Any,
    channels: tuple[str, ...] = (),
    template: TemplatePin | None = None,
    account_id: Any = None,
    recipients: tuple[Recipient, ...] = (),
    dispatch_not_before: datetime | None = None,
    render_context: dict[str, Any] | None = None,
    copy_no: int = 0,
    actor: Any = None,
    job: str | None = None,
    category: str | None = None,
    language: str | None = None,
    on_date: Any = None,
    event_key: str | None = None,
    channel_templates: dict[str, TemplatePin] | None = None,
    with_floor: bool = True,
    preferred_language: Any = FROM_ACCOUNT,
) -> QueueWrite:
    """Queue ONE document on every channel it goes out by. One transaction.

    ⚠ **`language` IS THE FALLBACK; THE CUSTOMER'S OWN LANGUAGE IS ASKED FIRST
    (PO option B, 2026-10-29 — SUPERSEDES `OQ-CUS-12619` (a) for messages).**
    PO, verbatim: *"Question: which language should messages be sent in? -
    B"*. Every caller passes the UTILITY's default as `language`, as it has
    since 2026-09-23. `preferred_language` is the customer's stated language:
    left as `FROM_ACCOUNT` it is READ from `account_id` (so every writer that
    names an account obeys the ruling without being edited); an applicant with
    no account yet passes the language they stated; `None` says *no
    preference*. Each unpinned pin is then asked for
    `message_language.language_for(...)` — the stated language where the
    utility published that class in it, otherwise `language`. A pin that
    already holds a version is never re-asked, so a reprint renders its pinned
    language (`BR-BIL-026`).

    ⚠ **`channel_templates` — ONE DOCUMENT, TWO KINDS OF TEMPLATE (`DEF-BIL-10530`,
    PO 2026-10-22).** A bill is ONE document but it travels as two different
    things: on paper and on the portal it IS the bill, rendered from its
    BILL-LAYOUT pin (`template`); in an email or a text it is a NOTIFICATION
    that the bill exists, with its own wording class (`email_bill_ready`,
    `sms_bill_ready`). Until 2026-10-22 this function took one pin for every
    channel, so a bill's email row carried the bill LAYOUT's id as its
    notification template; `load_pinned` found no such notification version,
    the render was refused, and the dispatcher released the row to *Waiting ·
    0 tries* every cycle, forever. A channel named here takes ITS OWN pin —
    usually a bare class code, resolved below exactly as any other email's is —
    and every other channel keeps `template`. Omit it and nothing changes.

    The ONLY write path into `outbound_messages` (B1). Called by billing at
    issue (BR-BIL-016), by payments for receipts and notices, by reports for
    scheduled sends — each resolving this function BY NAME so no module imports
    another's internals.

    `event_key` names the SET-12 event this document is (CR-048 A1). Pass it and
    this utility's rule is read and intersected in — switching *Bill ready —
    email* off on the settings screen stops the email. **Omit it and nothing
    changes**: no rule is read, no tenant rule table is touched, and the write is
    byte-identical to what shipped before A1. Every caller in the product still
    omits it today; feeding them event keys is CR-048 wave B. `channel_decision`
    holds the whole argument for why this is a parameter and not derived from
    `source_type`, `category` or the template pin.

    When a utility's rule leaves no channel at all, this returns an EMPTY
    `QueueWrite` carrying the reason — it does not raise. A tenant switching a
    setting off is not something a human must be asked to repair, and a refusal
    inside a five-hundred-bill run is a named break per bill (BR-BIL-055). It is
    not audited either: hard rule 7 audits the queue WRITE, this call writes
    nothing, and the decision that suppressed it was already audited by
    `rule_service.update_rule` when a System Admin made it.

    `dispatch_not_before` is S31 step 6's *"send now vs scheduled"* and
    BR-NOT-009's quiet hours: NULL means eligible immediately. It is a
    PARAMETER and never a clock read (BR-TEN-043) — nothing in this module
    reads a wall clock, and G6 greps for it.

    Returns a `QueueWrite` naming every row, whether THIS call created it, and
    every recipient it could not resolve. It never returns an exception in
    place of a row: a channel with no address still gets a row (see the module
    docstring), because a message that was never queued leaves no trace.

    Raises `QueueWriteRefused` only for what a human can act on — an unknown
    source kind or channel, a bill with no template pin, a negative copy
    number, a recipient read that answers incoherently. Billing's seam
    translates that into `BillingRuleError` so one refusable bill is one named
    break in a run of five hundred, not a dead batch (BR-BIL-055).
    """
    tenant_id = _tenant_id()
    # ⚠ `with_floor=False` — DEF-NOT-10650 (PO 2026-10-29, *Fix address and
    # retry*). A clerk correcting ONE email's address is re-delivering that
    # email, not issuing the document again: its paper copy already went out at
    # copy 0 under the floor, and a floor here would post a SECOND letter for a
    # typo in a mailbox. Only a deliberate human copy (`copy_no` > 0) may ask
    # for it, so no automatic writer can switch the floor off by accident.
    if not with_floor and copy_no < 1:
        raise QueueWriteRefused(
            "the print floor (BR-BIL-036) may be left off only for a deliberate human "
            "copy of one channel's delivery (copy_no > 0); an original delivery record "
            "always carries its floor."
        )
    decision = channel_decision(
        source_type, tuple(channels), event_key=event_key, with_floor=with_floor
    )
    # Validated on what the CALLER asked for, not on what the tenant's rule left
    # of it: an unknown channel or a bill with no pin is the caller's mistake and
    # must be refused whether or not a utility has switched that channel off.
    _refuse_unless_writable(
        source_type=source_type,
        source_id=source_id,
        channels=decision.without_rule,
        template=template,
        copy_no=copy_no,
    )
    rule_problems = _rule_problems(decision)
    if not decision.channels:
        # The rule left nothing. An EMPTY write that SAYS SO — see the docstring
        # for why this is not a refusal and not silent.
        return QueueWrite(
            source_type=source_type,
            source_id=str(source_id),
            problems=rule_problems,
        )
    wanted = decision.channels
    floor_added = decision.floor_added
    # CR-048 B6 — the two attribution facts, computed ONCE and stamped on every
    # row this call creates. `suppressed_note` is NULL rather than an empty
    # string when the rule removed nothing, so "no suppression" and "we did not
    # look" stay distinguishable in the column (the `unavailable_reason`
    # discipline one table over).
    suppressed_note = ",".join(decision.suppressed) or None

    supplied = {recipient.channel: recipient for recipient in recipients}
    resolved, problems = _recipients_for(account_id=account_id, channels=wanted, supplied=supplied)
    problems = rule_problems + tuple(problems)

    # `CR-199-BRC10` S1 (A3 A) — the CUSTOMER-CATEGORY axis at queue time. A
    # caller that holds the account's class still passes it; one that passes
    # only the account (every writer in the product today) now gets the
    # account's own class read once, so a published "Commercial" variant is
    # actually chosen for a commercial account — and `resolve` falls back to
    # All customers when there is none. An account with no class, or no
    # account, resolves exactly as before.
    if category is None and account_id is not None:
        from apps.notifications import customers_seam  # local: keeps the import graph flat

        category = customers_seam.account_category(account_id)

    # BR-BIL-026 — freeze the version NOW, not at dispatch. `category` is the
    # account's; `language` is the UTILITY's default and is the FALLBACK, and
    # the customer's stated language is asked first, class by class (PO option
    # B, 2026-10-29, `BR-NOT-006` as amended that day — superseding the
    # 2026-09-23 *"(a) Portal only; emails in English."* for messages).
    if preferred_language is FROM_ACCOUNT:
        from apps.notifications import message_language

        stated = message_language.account_language(account_id)
    else:
        stated = preferred_language
    template, pin_problem = _pinned(
        template, category=category, language=language, on_date=on_date, stated=stated
    )
    if pin_problem is not None:
        problems += (pin_problem,)
    # `DEF-BIL-10530` — the per-channel pins, each resolved at queue time like
    # the document's own (BR-BIL-026). Only for channels actually being written;
    # an override for a channel the rule took away resolves nothing.
    pins: dict[str, TemplatePin] = {}
    for channel, override in (channel_templates or {}).items():
        if channel not in wanted:
            continue
        if override is None or not (
            override.code or (override.template_id is not None and override.version is not None)
        ):
            raise QueueWriteRefused(
                f"the {channel} pin names neither a template code nor a pinned version, so "
                "that row could never say what it will be rendered from (US-NOT-001 §1)."
            )
        resolved_pin, override_problem = _pinned(
            override, category=category, language=language, on_date=on_date, stated=stated
        )
        if override_problem is not None:
            problems += ({**override_problem, "channel": channel},)
        pins[channel] = resolved_pin
    # ⚠ `DEF-PAY-4409` — WHICH FIELDS OF THIS DOCUMENT WILL PRINT BLANK, said at
    # the moment the row is written rather than discovered by a Product Owner
    # reading `Amount ——` on a live receipt. It REPORTS and never refuses; the
    # block comment on `_context_gap` holds the whole argument, including the
    # three ways a check of this shape passes wrongly and what each cost.
    #
    # ONCE per document and not once per channel: the pin is one pin for every
    # channel this call writes, so the body is loaded once — and once more per
    # DISTINCT per-channel pin (`DEF-BIL-10530`). A channel whose rows render
    # from the document pin is only checked when some channel actually does.
    checked: set[tuple[Any, Any, Any]] = set()
    for channel in wanted:
        pin = pins.get(channel, template)
        key = (pin.code, pin.template_id, pin.version)
        if key in checked:
            continue
        checked.add(key)
        problems += _context_gap(pin, render_context)
    if floor_added:
        problems += (
            {
                "code": QUEUE_FLOOR_CHANNEL_ADDED,
                "br_ref": "BR-BIL-036",
                "detail": "PRINT is the primary delivery channel and the floor: "
                f"{', '.join(floor_added)} was added to this {source_type} because every "
                "bill is printed, whatever else it is also sent by. A paperless customer "
                "still receives the document.",
            },
        )

    messages: list[QueuedMessage] = []
    with transaction.atomic():
        # Rule 6, the ordinary path: what is already queued for this document.
        # A double-clicked release finds its own rows here and writes nothing.
        existing = {
            row.channel: row
            for row in models.OutboundMessage.objects.filter(
                tenant_id=tenant_id,
                source_type=source_type,
                source_id=source_id,
                channel__in=wanted,
                copy_no=copy_no,
            )
        }
        for channel in wanted:
            already = existing.get(channel)
            if already is not None:
                messages.append(
                    QueuedMessage(
                        id=str(already.pk),
                        channel=channel,
                        status=already.status,
                        created=False,
                        unavailable_reason=already.unavailable_reason,
                    )
                )
                continue
            recipient = resolved[channel]
            row_pin = pins.get(channel, template)  # DEF-BIL-10530
            # ⚠ THE DO-NOT-SEND LIST (DEF-NOT-5632), asked BEFORE the row is
            # written so that the row records the answer.
            #
            # **The row is still written.** `BR-PAY-018`'s paper rule, verbatim
            # — *"written, marked held, never dispatched, never lost"* — and
            # this module's own discipline one paragraph up: a channel with no
            # address still gets a row, because a message that was never queued
            # leaves no trace. A clerk asking *did this customer get their bill*
            # must find an answer, and *held, because the address is on the
            # do-not-send list* is an answer. Refusing the write would leave
            # silence, which is the one outcome nobody can act on.
            #
            # `held` and not a status: the lifecycle is forward-only
            # (`BR-NOT-005`) and `held` is orthogonal to it by design — see
            # `OutboundMessage.held`. `BR-NOT-024` is why this costs the
            # consumer nothing: print is the floor on every customer document,
            # so a suppressed email never means an unsent bill.
            suppressed_address = suppression.is_suppressed(
                channel=channel, address=recipient.address
            )
            if suppressed_address:
                problems += (
                    {
                        "code": QUEUE_ADDRESS_SUPPRESSED,
                        "br_ref": "BR-NOT-005",
                        "channel": channel,
                        "detail": "this address is on the do-not-send list, so the message "
                        "was written and marked held rather than queued for sending. It has "
                        "not been lost: releasing the address on the blocked-addresses "
                        "screen makes it selectable again. Print is the floor on every "
                        "customer document (BR-NOT-024), so the customer still receives it.",
                    },
                )
            try:
                # Rule 6, the racing path: a savepoint, because between the
                # SELECT above and this INSERT a second worker may have won.
                # The DATABASE refuses the duplicate — which is the only
                # guarantee that survives a retry that never called this
                # function twice at all (US-NOT-001 TC-5).
                with transaction.atomic():
                    row = models.OutboundMessage.objects.create(
                        tenant_id=tenant_id,
                        account_id=account_id,
                        source_type=source_type,
                        source_id=source_id,
                        channel=channel,
                        copy_no=copy_no,
                        template_code=row_pin.code,
                        template_id=row_pin.template_id,
                        template_version=row_pin.version,
                        template_language=row_pin.language,
                        recipient_address=recipient.address,
                        recipient_snapshot=recipient.snapshot,
                        unavailable_reason=recipient.unavailable_reason,
                        status=models.STATUS_QUEUED,
                        # DEF-NOT-5632 — see the block comment above the `try`.
                        held=suppressed_address,
                        held_reason=(
                            suppression.HELD_SUPPRESSED if suppressed_address else None
                        ),
                        dispatch_not_before=dispatch_not_before,
                        # CR-048 B6 — WHICH EVENT this row is, and what this
                        # utility's rule took off it. NULL for every writer that
                        # names no event, which is what keeps a pre-wave-B row
                        # and a pre-wave-B writer byte-identical. Never derived
                        # from `source_type` or the pin: see the column's own
                        # docstring for the three derivations that were measured
                        # and refused.
                        event_key=event_key,
                        rule_suppressed_channels=suppressed_note,
                        # BR-NOT-012's *"the notification's own stored render
                        # context"*. NULL for every writer that does not pass one,
                        # which is every writer that existed before 2026-08-17 —
                        # so this changed nothing already queued and nothing
                        # already rendering. The column's own docstring says what
                        # may go in it and why an invoice's figures may not.
                        render_context=rendering.encode_context(render_context),
                    )
            except IntegrityError:
                lost = models.OutboundMessage.objects.filter(
                    tenant_id=tenant_id,
                    source_type=source_type,
                    source_id=source_id,
                    channel=channel,
                    copy_no=copy_no,
                ).first()
                if lost is None:  # pragma: no cover - a different constraint failed
                    raise
                messages.append(
                    QueuedMessage(
                        id=str(lost.pk),
                        channel=channel,
                        status=lost.status,
                        created=False,
                        unavailable_reason=lost.unavailable_reason,
                    )
                )
                problems += (
                    {
                        "code": QUEUE_ALREADY_QUEUED,
                        "br_ref": "BR-BIL-016",
                        "channel": channel,
                        "detail": "another writer queued this document on this channel "
                        "first; the database refused the duplicate (CLAUDE.md rule 6). "
                        "One delivery record per document per channel — the customer gets "
                        "one bill in the post, not two.",
                    },
                )
                continue
            # Hard rule 7 — in the SAME transaction, so a queued message cannot
            # stand without its trail row (core.audit fails loudly).
            _audit_created(row, actor=actor, job=job)
            messages.append(
                QueuedMessage(
                    id=str(row.pk),
                    channel=channel,
                    status=row.status,
                    created=True,
                    unavailable_reason=row.unavailable_reason,
                )
            )

    return QueueWrite(
        source_type=source_type,
        source_id=str(source_id),
        messages=tuple(messages),
        problems=problems,
        floor_channels_added=floor_added,
    )


def send_now(message_ids: Any, *, actor: Any = None) -> None:
    """Send these just-queued rows IMMEDIATELY, at the highest priority.

    `CR-188-BRC10` — PO 2026-10-22, verbatim: *"this should be on highest
    priority in quesu this should be instant email , in case of staff access
    email same logic needs to apply email should be sent instantly no latency"*.
    THE seam for every account-access email (staff invitation, staff reset, the
    customer portal's reset link); another module resolves it BY NAME, as it
    resolves `queue_document`.

    1. The rows are already written (`queue_document`) — recorded and auditable.
    2. They are marked `PRIORITY_IMMEDIATE`, so if this attempt cannot deliver
       them the next ordinary cycle claims them first.
    3. **On commit** — never inside the caller's transaction, never inside the
       web request's own work — one job of kind `notifications.send_now` is
       enqueued on the dedicated `account_access` queue
       (`apps/notifications/send_now.py`), which runs `dispatcher.
       dispatch_messages` for exactly these rows with quiet hours NOT applied.

    Never raises: a broker that refuses the job leaves the rows queued for the
    ordinary cycle, which is the ruling's own failure path.
    """
    ids = [str(item) for item in (message_ids or ()) if item]
    if not ids:
        return
    tenant_id = _tenant_id()
    models.OutboundMessage.objects.filter(tenant_id=tenant_id, pk__in=ids).update(
        priority=models.PRIORITY_IMMEDIATE
    )
    actor_user_id = audit.actor_user_id(actor) if actor is not None else None

    def _fire() -> None:
        from apps.notifications import send_now as immediate

        immediate.enqueue_send_now(tenant_id, ids, actor_user_id=actor_user_id)

    transaction.on_commit(_fire)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-001@2e6b19d (sha1[:7] of the four sources this slice was authored from, concatenated in order: 04-docs/02-decisions/02-database-design-brief.md — Addendum r10 #8 (delivery-queue shape) + r12 #16 (PLATFORM-WIDE) + r16 #1/#6/#7 — · 04-docs/05-modules/10-notifications/06-epics/EP-NOT-01-outbound-queue.md · 10-notifications/02-business-rules.md · 10-notifications/03-field-map.md — the same four the schema slice was cut from, because this is that slice's write half)
# generated: 2026-08-11 by story-coder (W3 notifications queue-WRITE lane — the seam billing calls at issue)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — no notifications endpoints; the dispatch home is US-NOT-004) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · see the lane report for the verbatim RED transcripts —
#         the idempotency guard and the print-is-the-floor rule were each broken
#         deliberately, run, and the measured failure quoted before either was
#         trusted green (hard-won law 7)
# exceptions: (1) THIS QUEUES; IT DOES NOT SEND. No SMTP/ESP/Twilio/print-vendor
#         call exists in this module and none may be added here — email
#         ACTIVATION is R4 (B12 release table), print/PDF dispatch is US-NOT-002.
#         A row resting `queued` is the correct finished state of a bill run in
#         R2, not a pending failure.
#         (2) EVERY RECIPIENT IS `recipient_not_resolvable` ON THIS DEPLOYMENT.
#         Customers publishes no `delivery_recipients_for_account`; the address
#         lives in `contacts` and the SMS opt-in column is unbuilt. Rows are
#         still written and say so — the absence is on the row and in
#         `problems`, never a fabricated address and never a skipped channel.
#         The fifth `UNAVAILABLE_REASONS` value was ADDED for this (models.py):
#         recording an unlooked-up address as `no_email_address` would state a
#         fact about a customer that nobody checked. REPORTED, decision log
#         2026-08-11.
#         (3) THE CHANNEL ELECTION IS NOT DECIDED HERE. `accounts.paperless` and
#         `accounts.sms_reminders` are PROPOSED-SCHEMA and unbuilt, so the
#         caller names the channels and this function adds BR-BIL-036's print
#         floor. Nothing invents an election for an account.
#         (4) NO `notice_history` WRITE (r12 #7 — payments-owned). US-NOT-001
#         TC-3 makes that the writer's job beside its queue row; a cross-module
#         write from here would break B1 in the one direction the reviewed
#         interface does NOT open.
#         (5) ⚠ [CORRECTED 2026-08-29 · CR-048 A1 — hard-won law 1] THIS
#         PARAGRAPH WAS TRUE WHEN WRITTEN AND IS NOW FALSE. It read:
#         "`apps/notifications/services.py` MATCHES NO GLOB IN
#         10-scripts/gates/human_owned.txt, so G7 does not enforce the
#         HUMAN-OWNED marker this file carries". The glob WAS added — it is
#         line 74 of that file today ("Outbound queue write — the ONLY writer
#         of outbound_messages, carries BR-BIL-036's print floor and hard rule
#         6 idempotency") — so G7 enforces this file's HUMAN-OWNED marker and
#         its review-ledger row, and the gap this exception reported is closed.
#         Corrected rather than deleted because a reader who had taken the old
#         sentence at its word would otherwise never learn it had moved: a
#         comment claiming a guarantee — or, here, claiming the absence of
#         one — is not the guarantee.
#         (6) [CR-048 A1, 2026-08-29] THE JOIN IS BUILT AND NOTHING FEEDS IT
#         YET. `event_key` is optional and every writer in the product still
#         omits it — billing, payments, customers and this module's own notice
#         writers all pass a source type. So on the running product the rule is
#         still not consulted for a real document, and the settings screen is
#         still decoration until CR-048 wave B (B1/B2/B3) passes event keys.
#         That is the CR's own task order and not a deferral taken here; it is
#         stated because hard-won law 2 is exactly this shape — built is not
#         wired — and a lane reading only this file could otherwise believe A1
#         switched the screen on. What A1 makes true is that wave B is now a
#         one-argument change per caller.
#         (7) [CR-048 A1] A DISCONNECT NOTICE HAS NO PRINT FLOOR, so a utility
#         that switches that event off today stops the letter. The floor is
#         `CHANNEL_FLOOR_BY_SOURCE`, BR-BIL-036 rules on BILLS, and inventing an
#         entry for `notice` would be this lane writing a business rule about a
#         legal instrument. REPORTED to CR-048; not closed here.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
