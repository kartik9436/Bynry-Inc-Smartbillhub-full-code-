# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-017 (SET-12 the notification event matrix + SET-12D the event
#           rule page — CR-009)   Screens: S8 (Settings → Notifications)
# Rules:    BR-NOT-017 (ONE HOME: every notification rule, internal and
#           external, lives on Settings → Notifications — PO 2026-08-17) ·
#           BR-NOT-018 (an event with no trigger is DRAWN and REFUSED by name,
#           never silently enabled — PO 2026-08-17 field-work clause) ·
#           BR-NOT-005 (queue only; no synchronous send endpoint anywhere) ·
#           BR-NOT-010 (v1 channels: print live · email W6 · SMS v1.1) ·
#           BR-NOT-013 (delivery is out of this release on EVERY channel) ·
#           BR-NOT-014 (three disconnect tiers, one slot each) ·
#           BR-PAY-017 (the collections ladder: due+3 → 10 → 5 → 48h) ·
#           BR-SHL-025 (a forbidden or impossible control renders WITH its
#           reason, never hidden)
# Change:   CR-048 wave B task B9 — *"Report what is covered and what is not …
#           as data in the response, not a note somebody remembers"* (the three
#           counts and the DERIVATION that keeps the third one true) ·
#           **task B10, 2026-08-30 — THREE MORE EVENTS**: moving in, moving out
#           and a missed payment-plan instalment, each with wording already
#           seeded and no rule to send it. Fifteen became EIGHTEEN and B9's
#           derived gap fell 16 → 13 with nobody editing a number ·
#           **task B6 — `EventClass.source_type`**, so the rail can say whether
#           a full suppression of an event can be recorded at all ·
#           **task B11, 2026-08-30 — THE REMAINING THIRTEEN**: statement, credit,
#           refund, write-off, deposit, autopay, rate-plan change, two more plan
#           notices, the outage and door-hanger wordings, the account-closed
#           confirmation and the SMS receipt. Eighteen became THIRTY and B9's
#           derived gap fell 13 → **0**, again with nobody editing a number.
#           Seven have a LIVE trigger, five are DRAWN AND REFUSED (BR-NOT-018)
#           and one joined an event that already existed.
# Tests:    06-backend/tests/test_cr_009_notification_rules.py ·
#           06-backend/tests/test_cr048_b_engine_on.py (CR-048 B9) ·
#           06-backend/tests/test_cr048_b6_b10.py (CR-048 B6 + B10)
# Impacts:  apps/notifications/rule_models.py · rule_service.py · rules_api.py ·
#           apps/notifications/bulk_summary.py (fires two of these events) ·
#           apps/notifications/seed_templates.py (the catalogue B9 measures
#           against) · 07-frontend/src/features/notifications/NotificationRules.tsx
# ───────────────────────────────────────────────────────
"""The events this platform can notify about — the vocabulary, frozen in code.

CR-009's SET-12 is a matrix over EVENTS, and an event is not tenant data: a
utility cannot invent "bill ready", because only a writer in this codebase can
fire one. So the rows are a CONSTANT here and the tenant owns only the RULE
attached to each (`rule_models.NotificationRule`) — the same shape
`models.SOURCE_TYPES` and `catalogs.CATALOGS` already use, and for the same
reason: a row nothing recognises is a rule nothing will ever apply.

╔══════════════════════════════════════════════════════════════════════════╗
║  THE PO's REQUIREMENT SAYS "16 total" AND NAMES FIFTEEN.                 ║
╚══════════════════════════════════════════════════════════════════════════╝
Counted at build time from the requirement quoted verbatim in
`12-governance/11-change-requests.md` → CR-009: Billing 2 · Payments 2 ·
Collections 3 · Field work 3 · Staff & system 5 = **15**. The sixteenth is not
named anywhere in the text. Two readings are available and both are guesses —
*"Billing run completed/failed"* may be two events, or one was dropped in
transcription — so **fifteen are built and the discrepancy is REPORTED rather
than filled in** (recorded in the CR section and in the decision log,
2026-08-17). Inventing a sixteenth event would put a row on a settings screen
that no writer in this codebase can ever fire.

⚠ **AND THE TOTAL IS THIRTY SINCE 2026-08-30 (CR-048 wave B tasks B10 AND B11),
WHICH DOES NOT RESOLVE THE PARAGRAPH ABOVE AND MUST NOT BE READ AS DOING SO.** The
requirement still claims sixteen and still names fifteen, and that discrepancy
is still open and still reported. B10 added THREE MORE events that the
requirement never named at all — moving in, moving out, and a missed
payment-plan instalment — because each had wording seeded, a live moment to fire
from, and no rule to govern it. **B11 then added TWELVE more**, closing the last
of the seeded-and-unreachable wordings; seven of those have a live writer, five
are DRAWN AND REFUSED by name (BR-NOT-018) with the question that owns each
absence, and a thirteenth class needed no new event at all because it is the SMS
face of a receipt `payment_received` already governs. ⚠ **AND `CR-136-BRC07`
`P2.11` ADDED A THIRTY-FIRST ON 2026-09-23** — `counter_left_open`, a counter
nobody closed, staff & system, LIVE from its first commit. It is here rather
than behind `queue_staff_alert` because BR-NOT-017 gives every notification
rule ONE home and `DEF-3422`'s exception does not reach it: a till left open is
the utility's own shift, not the product's setup failing. So
`BUILT_EVENT_COUNT` is
32 (⚠ this line read **31** until 2026-09-27, when `CR-142-BRC07` `P4.10` added
`scheduled_report_ready`; the constant is `len(EVENTS)` and was never wrong — the
PROSE was, which is this repo's most-filed rot)
against a `REQUIREMENT_CLAIMS_EVENT_COUNT` of 16, and the two are measuring
different
things: one counts what this platform can notify about, the other records what
one document once claimed. **A reader who subtracts them gets a meaningless
number; that is why both are named constants and neither is a total.**

────────────────────────────────────────────────────────────────────────────
THREE THINGS EVERY ROW MUST BE HONEST ABOUT, BECAUSE THE SCREEN DRAWS THEM
────────────────────────────────────────────────────────────────────────────
**1 · CHANNELS THAT DO NOT EXIST.** The requirement names *Portal*, *Mail* and
*In-app*. ⚠ **AMENDED 2026-08-17: this paragraph used to say "This platform has
exactly three channels — `pdf_print`, `email`, `sms`" and IN-APP WAS ONE OF THE
THREE IT LISTED AS MISSING.** There are four now (`models.CHANNELS`,
BR-NOT-019), and `in_app` is the one that actually delivers. ⚠ **AMENDED AGAIN
2026-08-18:** it then sat in `unavailable_channels` on the staff events because
the ADDRESSEE was unruled (OQ-261); the PO closed that question (BR-NOT-021)
and `in_app` is now a real channel row on all five staff events.
*Portal* is still absent entirely, and "Mail" on a disconnect notice still means
physical post, which is a FULFILMENT VENDOR and not a flag anybody can switch.
So a requested channel with no implementation is carried in
`unavailable_channels` with its reason and is **drawn disabled with that
reason** (BR-SHL-025). It is never a togglable row, because a toggle a utility
can turn on is a promise that something happens when they do.

**2 · TRIGGERS THAT DO NOT EXIST.** `trigger` names the writer that fires the
event, or the OPEN QUESTION that owns its absence. Three field-work events are
*"fired by Work → Rules"* and Work is R5 with **OQ-249** still open; a further
three staff events (SLA breach, daily digest, security alerts) have no concept
anywhere in this codebase at all. Their audience, channels and template are
still this screen's to own — the CR says so explicitly — so the row exists and
says what will not happen yet.

**3 · WHO A STAFF NOTIFICATION GOES TO — RULED 2026-08-17, WIRED 2026-08-18.**
⚠ This paragraph used to mint **OQ-261** (*"Owner" is not one of this
platform's three roles … every staff event carries
`staff_recipient_unresolved`*). **The PO closed it, verbatim: "the user who
started the action, plus all System Admins for failures"** (decision log
C-11 → BR-NOT-021). The policy is a PLATFORM RULE, not a per-rule setting:
`staff_recipients.py` is its one implementation, every staff event carries
`staff_recipient_policy` on the wire so the audience card can state it, and
`rule_service` still refuses any attempt to SET a recipient — now citing the
ruling rather than raising the question, because the PO chose a policy over
every one of the question's three picker options.

────────────────────────────────────────────────────────────────────────────
WHAT IS DELIBERATELY ABSENT — recorded so a later reader does not rebuild it
────────────────────────────────────────────────────────────────────────────
* **The medical / life-support skip.** The requirement asks the audience card
  for *"skip medical–life-support flags"* routing *"a CSR task instead"*. **PO
  ruling 2026-08-17, verbatim: _"Skip it ; not required as this point of
  time"_.** No flag is added to an account, no filter option is drawn and no
  CSR-task route is minted. It is absent BY RULING, not by oversight — which is
  why it is written here, in the file a reader diffing the CR against the
  product will open first.
* **Notice WORDING.** This module schedules; `catalogs.py` / the Templates
  catalog own what a letter says (the CR's own stated purpose: *"Notifications
  decide when and to whom; Templates define what it says"*). The five
  disconnect clauses are the PO's and are being authored elsewhere — nothing
  here authors a sentence a customer will read.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from apps.notifications import models

# ── categories, in the order the PO's requirement lists them ────────────────
CATEGORY_BILLING = "billing"
CATEGORY_PAYMENTS = "payments"
CATEGORY_COLLECTIONS = "collections"
CATEGORY_FIELD_WORK = "field_work"
CATEGORY_STAFF_SYSTEM = "staff_system"
#: ⚠ **A SIXTH, ADDED 2026-08-30 (CR-048 wave B task B10), AND IT IS OURS AND
#: NOT THE PO's.** The five above are the PO's own requirement list, in the
#: PO's own order, and neither the order nor the membership of those five has
#: moved. B10 adds two events that belong to none of them — moving in and
#: moving out — and the alternatives were both worse than a sixth heading:
#: filing a welcome letter under *Billing* puts it in a group a System Admin
#: would never look in, and inventing a category per event is a screen nobody
#: can scan. The name is `catalogs.py`'s own, already used for exactly these
#: template classes (`CAT_ACCOUNT_LIFECYCLE` holds `email_welcome`,
#: `email_move_out_final`, `email_deposit`, `email_account_closed`), so the
#: settings screen and the template library group the same messages under the
#: same heading rather than two spellings of one idea.
CATEGORY_ACCOUNT_LIFECYCLE = "account_lifecycle"

CATEGORIES: tuple[str, ...] = (
    CATEGORY_BILLING,
    CATEGORY_PAYMENTS,
    CATEGORY_COLLECTIONS,
    CATEGORY_FIELD_WORK,
    CATEGORY_STAFF_SYSTEM,
    # LAST, so the PO's five keep their ruled order and position. A screen that
    # iterates this tuple draws the requirement's own list first and ours after.
    CATEGORY_ACCOUNT_LIFECYCLE,
)

#: `CR-188-BRC10` — who a staff sign-in email goes to. Rendered verbatim on
#: Settings → Notifications in place of BR-NOT-021's sentence.
STAFF_ACCESS_RECIPIENT_POLICY = "Sent to the person whose sign-in it is, at their own email address."

# ── audience kinds ─────────────────────────────────────────────────────────
AUDIENCE_CUSTOMER = "customer"
AUDIENCE_STAFF = "staff"

#: Who, among a customer's contacts, receives it. The requirement's own two
#: options; there is no third, because a third would be a rule nobody has made.
CUSTOMER_SCOPE_ALL_CONTACTS = "all_contacts"
CUSTOMER_SCOPE_PRIMARY_ONLY = "primary_only"
CUSTOMER_SCOPES: tuple[str, ...] = (CUSTOMER_SCOPE_ALL_CONTACTS, CUSTOMER_SCOPE_PRIMARY_ONLY)

#: BR-NOT-021 (OQ-261 CLOSED, PO 2026-08-17). A staff rule STILL has no settable
#: recipient — the recipient is a RULED PLATFORM POLICY, not tenant data — and
#: this sentence is what the wire and the screen state instead of a picker. The
#: constant exists so the wire, the screen and the service all quote the same
#: ruling rather than three spellings of it. (The old constants here were
#: STAFF_RECIPIENT_UNRESOLVED / STAFF_RECIPIENT_OQ = "OQ-261"; both left with
#: the question they carried.)
STAFF_RECIPIENT_POLICY = (
    "Sent to the user who started the action; failures also reach every active "
    "System Admin (PO 2026-08-17, BR-NOT-021 — OQ-261 closed)."
)
STAFF_RECIPIENT_BR = "BR-NOT-021"

# ── plan class filter (BR-NOT-001's consumer categories, the two the CR names) ─
PLAN_CLASS_ALL = "all"
PLAN_CLASSES: tuple[str, ...] = (PLAN_CLASS_ALL, "residential", "commercial")

# ── timing ─────────────────────────────────────────────────────────────────
TRIGGER_IMMEDIATE = "immediate"
TRIGGER_OFFSET_DAYS = "offset_days"
TRIGGER_FIXED_TIME = "fixed_time"
TRIGGER_MODES: tuple[str, ...] = (TRIGGER_IMMEDIATE, TRIGGER_OFFSET_DAYS, TRIGGER_FIXED_TIME)

QUIET_HOURS_RESPECT = "respect"
QUIET_HOURS_OVERRIDE = "override"
QUIET_HOURS_MODES: tuple[str, ...] = (QUIET_HOURS_RESPECT, QUIET_HOURS_OVERRIDE)

FAILURE_RETRY_THEN_EMAIL = "retry_3_days_then_email"
FAILURE_RETRY_ONCE = "retry_once"
FAILURE_NONE = "none"
FAILURE_POLICIES: tuple[str, ...] = (FAILURE_RETRY_THEN_EMAIL, FAILURE_RETRY_ONCE, FAILURE_NONE)

LANGUAGE_AUTO = "auto"
LANGUAGE_ENGLISH_ONLY = "english_only"
LANGUAGE_MODES: tuple[str, ...] = (LANGUAGE_AUTO, LANGUAGE_ENGLISH_ONLY)

# ── channels the requirement names that this platform does not have ────────
#: CODE → the reason, in a sentence a System Admin can act on. Never prose in
#: the screen: the screen renders a catalogue key and this is the fact behind it
#: (BR-SHL-020's shape, the same one `provider_seam.ChannelRoute.problem` uses).
UNAVAILABLE_CHANNELS: dict[str, str] = {
    # ⚠ **THE `portal` ENTRY THAT LIVED HERE FROM 2026-08-17 TO 2026-09-07 IS
    # DELETED, AND IT IS THE SECOND TIME THIS DICTIONARY HAS LOST A ROW TO THE
    # THING IT REFUSED ARRIVING.** It read: *"there is no customer portal in
    # this product. A 'Portal' delivery flag would be a switch with nothing
    # behind it — BR-NOT-010 names three v1 channels (print, email, SMS) and no
    # signed document adds a fourth."*
    #
    # Every clause of that was true when it was written. `CR-068` then built the
    # portal — seventy-five screens, `CWP-027` *Your bills* and `CWP-031`
    # *Documents and letters* among them, both reading `outbound_messages`
    # already — and `CR-082` seeded its self-service content, and **nobody came
    # back to this sentence**. The Product Owner found it on the live product
    # and ruled, verbatim: *"can you swithc on this now - Customer portal"*
    # (`CR-084`, 2026-09-07).
    #
    # That is hard-won law 2's mirror in its plainest form — a refusal with a
    # clock in it, where landing the screen and releasing the control that
    # points at it are two acts and only the first feels like the work. The
    # lesson CLAUDE.md draws from it is the reason `tests/test_cr084_portal_
    # channel.py` asserts the channel by NAME on the event that offers it: a
    # hold with no test that fires when the hold expires is a promise nobody is
    # keeping.
    "mail": (
        "'Mail' on a disconnect notice means PHYSICAL POST, which is a "
        "fulfilment vendor and not a channel flag. The platform's paper channel "
        "is `pdf_print` — it RENDERS the letter; who franks and posts it is an "
        "integration nobody has chosen (BR-NOT-013: no adapter on any channel, "
        "print included)."
    ),
    # ⚠ **THE `in_app` ENTRY THAT LIVED HERE FROM 2026-08-17 TO 2026-08-18 IS
    # DELETED, exactly as it promised it would be** — *"When OQ-261 closes,
    # this entry is DELETED and `in_app` joins `channels` on the five staff
    # events — a change of one line per event, because everything behind it is
    # already built."* The PO closed OQ-261 on 2026-08-17 (*"the user who
    # started the action, plus all System Admins for failures"* → BR-NOT-021),
    # so the surface AND the addressee now both exist, and `in_app` is a real
    # channel row on all five staff events below. Its own two earlier reasons
    # are kept in the git history rather than re-quoted at length: first "no
    # surface" (false as of the 2026-08-17 build), then "no addressee" (false
    # as of the C-11 ruling).
}


@dataclass(frozen=True)
class EventClass:
    """One row of SET-12. Frozen: a tenant configures it, never defines it."""

    key: str
    category: str
    audience: str
    #: Channels that EXIST here and are offered as toggles. A subset of
    #: `models.CHANNELS`, always — a channel outside it cannot be queued
    #: (`services._refuse_unless_writable`) and would be a dead row.
    channels: tuple[str, ...]
    #: What the requirement asked for that this platform has no implementation
    #: of. Keys of `UNAVAILABLE_CHANNELS`. Drawn disabled with the reason.
    unavailable_channels: tuple[str, ...] = ()
    #: channel → the `catalogs.py` template class this event renders from, when
    #: one exists. A channel absent from this map has NO template class and the
    #: screen says so rather than offering a variant picker over nothing.
    template_classes: dict[str, str] = field(default_factory=dict)
    #: The writer that fires this event, or the OPEN QUESTION owning its
    #: absence. `None` means a real writer exists today.
    trigger_blocked_by: str | None = None
    #: ⚠ ADDED 2026-08-30 (CR-048 B6). Which `models.SOURCE_TYPES` kind this
    #: event's writer queues under, where that is KNOWN. `None` means nobody has
    #: written it down — which is honest, not a default: it is filled in for an
    #: event only by the lane that wires or reads its writer, never guessed from
    #: the event's name.
    #:
    #: It exists for exactly one question, and only the floorless kinds make it
    #: matter: **can a full suppression of this event be recorded at all?** A
    #: source kind with a print floor always leaves a surviving row to stamp
    #: (BR-NOT-024); one without a floor can be suppressed to nothing and leaves
    #: no row, so `delivery_counts` reports that event's suppression figure as
    #: unavailable rather than as a zero that reads as "your switch did
    #: nothing". Measuring it from the rows instead would answer "recordable"
    #: for any event that has never fired — which is the case where the wrong
    #: answer is most likely to be believed.
    source_type: str | None = None
    #: A sentence for the row, keyed for i18n by `notifications.rules.timing.<>`.
    timing_key: str = ""
    #: Collections events carry the escalation ladder (BR-PAY-017). Exactly one
    #: event does today, and the flag is per-event rather than per-category
    #: because "hi-usage alert" is a collections-category row with no ladder.
    has_ladder: bool = False
    #: `CR-188-BRC10` — a staff event whose recipient is NOT the ruled
    #: BR-NOT-021 policy. A sign-in link goes to the person whose account it
    #: is, never to the admin who clicked or to every System Admin, so the
    #: sentence the screen states for it is this one. `None` = the policy.
    staff_recipient_policy_override: str | None = None

    def as_wire(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "category": self.category,
            "audience": self.audience,
            "channels": list(self.channels),
            "unavailable_channels": [
                {"channel": channel, "reason": UNAVAILABLE_CHANNELS[channel]}
                for channel in self.unavailable_channels
            ],
            "template_classes": dict(self.template_classes),
            "trigger_blocked_by": self.trigger_blocked_by,
            # CR-048 B6 — provenance for the rail: which queue kind this event's
            # messages ride, or `null` where nobody has written it down.
            "source_type": self.source_type,
            "timing_key": self.timing_key,
            "has_ladder": self.has_ladder,
            # BR-NOT-021 (OQ-261 CLOSED 2026-08-17) — the ruled recipient
            # policy, carried per row so a screen never has to infer it from
            # `audience == "staff"` — an inference is a place to be wrong.
            # (Replaces the pre-ruling `staff_recipient_unresolved` flag.)
            "staff_recipient_policy": (
                (self.staff_recipient_policy_override or STAFF_RECIPIENT_POLICY)
                if self.audience == AUDIENCE_STAFF
                else None
            ),
        }


E = models.CHANNEL_EMAIL
S = models.CHANNEL_SMS
P = models.CHANNEL_PRINT
A = models.CHANNEL_IN_APP
#: `CR-084` — the customer's own portal. Spelled out rather than given a single
#: letter: `P` is already print, and a one-letter alias for a channel this
#: catalogue offers on exactly one event would be a spelling to get wrong on the
#: day it spreads (`NotificationRules.tsx` records what `print` vs `pdf_print`
#: cost when a channel name was typed twice).
PORTAL = models.CHANNEL_PORTAL


#: ⚠ **EIGHTEEN since 2026-08-30 — this line read "The fifteen" until CR-048
#: wave B task B10 added three.** ORDER IS STILL THE PO's: the requirement's own
#: five categories keep their order and their membership, each event stays where
#: it was written inside its category, and the three additions go LAST within
#: their group — the missed-instalment row at the end of collections, the two
#: move rows in a sixth category after all five of the PO's.
EVENTS: tuple[EventClass, ...] = (
    # ── 1 · Billing ────────────────────────────────────────────────────────
    EventClass(
        key="bill_ready",
        category=CATEGORY_BILLING,
        audience=AUDIENCE_CUSTOMER,
        # ⚠ **"Email+SMS+Portal" — AND THE THIRD IS A CHANNEL NOW (`CR-084`,
        # PO 2026-09-07).** This line read `channels=(E, S)` with
        # `unavailable_channels=("portal",)` beside it, and the comment said
        # *"the third is not a channel here"*. The requirement asked for three
        # from the first day; two of them were all this platform had.
        #
        # ⚠ **PORTAL CARRIES NO TEMPLATE CLASS, AND THAT IS THE DESIGN RATHER
        # THAN A GAP.** Email and SMS need WORDING — a subject and a body a
        # customer reads in their mail. A portal delivery publishes the BILL,
        # and `CWP-031` names each document from facts the server serves (the
        # month it covers, the amount, the reference) in the reader's own
        # language, because a catalogue writes its own sentences (B14 rule 35).
        # Minting an `email_bill_ready`-shaped class for it would author wording
        # no screen displays, which is a switch with something behind it that
        # nobody can see — the same failure the old refusal warned about,
        # arrived at from the other side.
        channels=(E, S, PORTAL),
        template_classes={E: "email_bill_ready", S: "sms_bill_ready"},
        timing_key="on_issue",
    ),
    EventClass(
        key="bill_corrected",
        category=CATEGORY_BILLING,
        audience=AUDIENCE_CUSTOMER,
        channels=(E,),
        template_classes={E: "email_corrected_bill"},
        timing_key="on_correction",
    ),
    # ⚠ ADDED 2026-08-30 · CR-048 wave B task B11, and it is DRAWN AND REFUSED.
    # `email_statement` is one of the thirteen seeded wordings; unlike the seven
    # this wave wired, **there is no statement in this product at all** — no
    # statement run, no statement document, nothing in `apps/billing` that
    # assembles a period's opening and closing balance for a customer to read.
    # (`billing/documents.py`'s "bill / statement rendering" is one renderer for
    # the BILL; `payments` uses the word for a BANK statement, which is an
    # import and not a customer's letter.) So the row exists and says so:
    # BR-NOT-018 — an event with no trigger is DRAWN and REFUSED by name, never
    # silently enabled. OQ-1160 owns the absence.
    EventClass(
        key="statement_ready",
        category=CATEGORY_BILLING,
        audience=AUDIENCE_CUSTOMER,
        channels=(E,),
        template_classes={E: "email_statement"},
        trigger_blocked_by="OQ-1160",
        timing_key="on_statement_run",
    ),
    # ── 2 · Payments ───────────────────────────────────────────────────────
    EventClass(
        key="payment_received",
        category=CATEGORY_PAYMENTS,
        audience=AUDIENCE_CUSTOMER,
        # ⚠ **SMS ADDED 2026-08-30 · CR-048 wave B task B11, AND IT IS THE ONE
        # CLASS OF THE THIRTEEN THAT NEEDED NO NEW EVENT.** `sms_payment_received`
        # is not a different MOMENT — it is the same receipt on a third surface,
        # exactly as `sms_bill_ready` sits beside `email_bill_ready` on
        # `bill_ready` above. Minting a `payment_received_sms` event would have
        # put a second row on SET-12 for one thing that happens, and a utility
        # switching *Payment received* off would then have to find and switch off
        # a second row to stop being in touch about it.
        #
        # Naming the class here is what takes it out of B9's coverage count:
        # `ruled_template_classes()` reads `template_classes.values()`, so a
        # class named on ANY channel of ANY event has a rule.
        channels=(E, S),
        template_classes={E: "email_payment_receipt", S: "sms_payment_received"},
        # `payments.receipts.queue_receipt_for_recorded_payment` queues under
        # `payment`, which carries BR-NOT-024's print floor — so a utility that
        # switches every electronic channel off still leaves a printed receipt
        # row to stamp, and a suppression is always recordable here.
        source_type="payment",
        timing_key="immediate",
    ),
    EventClass(
        key="payment_failed",
        category=CATEGORY_PAYMENTS,
        audience=AUDIENCE_CUSTOMER,
        channels=(E, S),
        template_classes={E: "email_payment_failed"},
        timing_key="immediate_then_retry",
    ),
    # ── CR-048 wave B task B11, 2026-08-30 · the two money-back messages ────
    #
    # ╔══════════════════════════════════════════════════════════════════════╗
    # ║  WHICH SOURCE KIND A MESSAGE RIDES, DECIDED ONCE FOR ALL THIRTEEN.   ║
    # ╚══════════════════════════════════════════════════════════════════════╝
    # `source_type` is a statement about WHAT THE DOCUMENT IS, never about which
    # module happened to write it, and the evidence used is `catalogs.LISTINGS[
    # code].category` — the filing this platform already publishes on SET-09:
    #
    #     CAT_PAYMENTS          → `payment`   (floored, BR-NOT-024)
    #     CAT_COLLECTIONS       → `notice`    (floored) · the plan letters → `plan`
    #     CAT_ACCOUNT_LIFECYCLE → `account`   (NO floor — see below)
    #
    # A rule rather than a choice per event, because the alternative is thirteen
    # judgement calls nobody can check, and because the kind decides whether
    # BR-NOT-024's print floor applies — which is the difference between a
    # utility being able to switch a message off entirely and not.
    #
    # ⚠ **NO FLOOR ENTRY WAS ADDED FOR `account`, AND THAT IS A CONSTRAINT AND
    # NOT AN OVERSIGHT.** BR-NOT-024 (PO 2026-08-29) names FOUR kinds —
    # `invoice`, `payment`, `notice`, `plan`. Adding a fifth would be this
    # module writing signed law. So a utility that switches *Account closed* or
    # *Deposit received* off gets no row at all, exactly as B10 ruled for a
    # move. The lane report carries this as a stated consequence.
    EventClass(
        key="refund_issued",
        category=CATEGORY_PAYMENTS,
        audience=AUDIENCE_CUSTOMER,
        channels=(E,),
        template_classes={E: "email_refund_issued"},
        # `payments.refunds.issue_refund` queues under `payment`, keyed on the
        # REFUND row. Floored, so a suppression is always recordable.
        source_type="payment",
        timing_key="on_refund_issued",
    ),
    EventClass(
        key="credit_issued",
        category=CATEGORY_PAYMENTS,
        audience=AUDIENCE_CUSTOMER,
        channels=(E,),
        template_classes={E: "email_credit_issued"},
        # `billing.corrections.execute_credit_only` queues under `payment`,
        # keyed on the CREDIT NOTE row.
        source_type="payment",
        timing_key="on_credit_raised",
    ),
    # ⚠ DRAWN AND REFUSED (BR-NOT-018). `email_autopay` has wording and there is
    # **nothing to confirm**: BR-CUS-059 makes `accounts.autopay` a CAPTURE-ONLY
    # flag in v1 — no autopay charge runs anywhere in this codebase, and the
    # palette's `{next_charge_date}`, `{next_amount}` and `{method}` name three
    # facts the product does not hold. Firing this off the flag being ticked
    # would tell a customer we are about to take money we have no way of taking,
    # which is `catalogs.py`'s own stated objection to r10's *"we will email you
    # 3 days before every charge"* one step further on. OQ-1162 owns it.
    EventClass(
        key="autopay_enrolled",
        category=CATEGORY_PAYMENTS,
        audience=AUDIENCE_CUSTOMER,
        channels=(E,),
        template_classes={E: "email_autopay"},
        trigger_blocked_by="OQ-1162",
        timing_key="on_autopay_enrolled",
    ),
    # ── 3 · Collections ────────────────────────────────────────────────────
    # ⚠ **PRINT JOINED 2026-10-29 (`DEF-PAY-10651`, PO "1A 2A")** — the
    # printed letter (`dunning`) for a customer no email or consented text can
    # reach. It is a FALLBACK, not a third copy: `past_due_reminder.plan` adds
    # it only when nothing digital is left, and its toggle here is how a utility
    # sees and stops it. The reminder queues under its own floorless kind,
    # `reminder` — switching the event off sends nothing at all (1A).
    EventClass(
        key="past_due_reminder",
        category=CATEGORY_COLLECTIONS,
        audience=AUDIENCE_CUSTOMER,
        channels=(E, S, P),
        template_classes={E: "email_past_due", S: "sms_past_due", P: "dunning"},
        source_type="reminder",
        timing_key="ladder",
        has_ladder=True,
    ),
    EventClass(
        key="disconnect_notice",
        category=CATEGORY_COLLECTIONS,
        audience=AUDIENCE_CUSTOMER,
        # "Mail+Email". The paper half of this one is `pdf_print`, which RENDERS
        # the letter; posting it is the vendor gap named in UNAVAILABLE_CHANNELS.
        channels=(P, E),
        unavailable_channels=("mail",),
        # BR-NOT-014 — three tiers, one slot each. The per-STAGE class lives on
        # the ladder stage, not here; this is the channel default.
        template_classes={P: "disconnect_notice_10_day", S: "sms_disconnect"},
        timing_key="ladder",
        has_ladder=True,
    ),
    # ⚠ **LIVE SINCE 2026-10-14 (`CR-182-BRC10`, PO A1–A5) — OQ-262's
    # high-usage half is answered.** PO verbatim: *"A4 … send her Email; A5 …
    # Option 2 Tell them as soon as the reading is flagged"*. The writer is
    # `apps/metering/high_consumption.notify_if_flagged`, called the moment a
    # reading is written; "high" is BR-MET-020/120's own flag (A6, our default),
    # so staff and customer agree. **EMAIL ONLY**: SMS was offered (*"Email+SMS"*
    # in the CR-009 requirement) and the PO chose email — an SMS toggle with no
    # wording and no writer would be a promise. It read `channels=(E, S)` with
    # `trigger_blocked_by="OQ-262"` until this commit; `notifications/0022` moves
    # every utility that never touched the row to the new default.
    EventClass(
        key="high_usage_alert",
        category=CATEGORY_COLLECTIONS,
        audience=AUDIENCE_CUSTOMER,
        channels=(E,),
        template_classes={E: "email_high_usage_alert"},
        # `metering.high_consumption` queues under `usage_alert`, keyed on the
        # READING — no print floor, so a switched-off rule leaves nothing.
        source_type="usage_alert",
        timing_key="high_usage_threshold",
    ),
    # ⚠ ADDED 2026-08-30 · CR-048 wave B task B10, the third of *"the three real
    # omissions"*, described by the CR as *"the one a utility most needs to
    # send"*. Collections, because a missed instalment is a chasing event and
    # `catalogs.LISTINGS["plan_notice_missed"]` files its wording under
    # collections too.
    #
    # **THE TRIGGER ALREADY EXISTED AND WAS SENDING THE WRONG THING** — which is
    # why this is an omission and not new scope. `apps.payments.notices.
    # send_plan_notices` has queued a missed-instalment message since
    # 2026-08-11, pinned to the template code `plan_installment_missed`, and
    # that string is a NOTICE-HISTORY type, not a template class: nothing in
    # `catalogs.py` or `seed_templates.py` has ever declared it. The wording a
    # customer would have read is `plan_notice_missed`, seeded and never
    # reachable. This row is what makes the two the same message.
    #
    # No `trigger_blocked_by`: the writer is live today.
    EventClass(
        key="payment_plan_instalment_missed",
        category=CATEGORY_COLLECTIONS,
        audience=AUDIENCE_CUSTOMER,
        # ⚠ **EMAIL ONLY, AND PRINT IS DELIBERATELY NOT A TOGGLE HERE.** The
        # seeded body is an EMAIL body (`catalogs.LISTINGS` kind "Email") and no
        # print class for a plan notice exists — so a `pdf_print` row on this
        # event would seed OFF (`rule_service._seeded_channel_enabled` ships a
        # channel ON only where the platform can render something on it), and
        # BR-NOT-024's floor would then put the letter on paper anyway. Every
        # printed plan letter would report its own print channel as *suppressed
        # by your rule*, which is false, and a false number is exactly what the
        # "Last 30 days" rail exists to stop drawing.
        #
        # Paper is not un-governed here: it is FLOORED, which is a stronger
        # statement than a toggle — no rule and no master switch removes it.
        channels=(E,),
        template_classes={E: "plan_notice_missed"},
        # `payments.notices.send_plan_notices` queues under `plan`, which DOES
        # carry BR-NOT-024's print floor — so a suppression here is always
        # recorded on the surviving print row.
        source_type="plan",
        # BR-PAY-016 as the PO left it on 2026-08-11: the notice goes the day
        # AFTER an unmet due date. Nothing drops off and no counter is kept —
        # `payments/notices.py` holds the whole of that reasoning.
        timing_key="day_after_missed_instalment",
    ),
    # ⚠ ADDED 2026-08-30 · CR-048 wave B task B11 — *"two more plan notices"*.
    #
    # **THE REMINDER HAD BOTH OF B10's FAULTS AND B10 SAID SO IN WRITING**, in
    # `payments/notices.py`: *"THE REMINDER IS DELIBERATELY LEFT AS IT WAS, both
    # faults included … adopting it here would take a class out of B9's coverage
    # count that B11 is about to report on."* This is that adoption. It pinned
    # `plan_installment_reminder` — a NOTICE-HISTORY type, not a template class,
    # declared by nothing in `catalogs.LISTINGS` or `seed_templates.SEEDABLE`
    # (DEF-2511) — and keyed every reminder on the PLAN, so the reminder for
    # instalment 4 deduped into the reminder for instalment 3 and a customer on
    # a twelve-month plan was reminded ONCE (DEF-2512). Both are closed on this
    # commit: the code is `plan_notice_upcoming`, the key is the INSTALMENT.
    EventClass(
        key="payment_plan_instalment_upcoming",
        category=CATEGORY_COLLECTIONS,
        audience=AUDIENCE_CUSTOMER,
        # EMAIL ONLY, for `payment_plan_instalment_missed`'s stated reason one
        # row up: the seeded body is an EMAIL body and no print class for a plan
        # notice exists, so a `pdf_print` toggle would seed OFF and BR-NOT-024's
        # floor would put the letter on paper anyway — every printed plan letter
        # reporting its own print channel as *suppressed by your rule*, which is
        # false. Paper is FLOORED here, which is stronger than a toggle.
        channels=(E,),
        template_classes={E: "plan_notice_upcoming"},
        source_type="plan",
        # BR-PAY-016 CONFIRMED: *"reminder 3 days before installment"*, and the
        # cadence is an ARGUMENT to `send_plan_notices`, not a constant — the
        # sentence this key renders says "before", never "3 days before".
        timing_key="days_before_instalment",
    ),
    # ⚠ DRAWN AND REFUSED (BR-NOT-018), and the blocker is a RULING plus a
    # question. `plan_notice_void` is wording ahead of a flow — the posture the
    # PO ratified for the service templates on 2026-08-16 (*"wording can exist
    # before the flow that sends it"*) — and `catalogs.py` says so on the class
    # itself: *"AND THE EVENT IT ANNOUNCES STILL HAS NO WRITER."* Measured on
    # this commit: `collections_models.PLAN_STATUSES` is
    # `proposed · agreement_sent · active · closed` and has **no void value at
    # all**, and the PO's 2026-08-11 *"nodrop we chase for payments until write
    # off"* removed the only automatic void BR-PAY-016 ever had. So nothing can
    # fire it, and what would is a staff action nobody has specified — OQ-1163.
    EventClass(
        key="payment_plan_voided",
        category=CATEGORY_COLLECTIONS,
        audience=AUDIENCE_CUSTOMER,
        channels=(E,),
        template_classes={E: "plan_notice_void"},
        trigger_blocked_by="OQ-1163",
        timing_key="on_plan_voided",
    ),
    # ⚠ ADDED 2026-08-30 · CR-048 wave B task B11 — *"write-off"*. The trigger is
    # live today: `payments.writeoffs.approve_write_off` is what the CR's own
    # catalogue row has been describing since 2026-08-16 —
    # *"Not in use yet — approving a write-off does not send a letter."*
    EventClass(
        key="write_off_approved",
        category=CATEGORY_COLLECTIONS,
        audience=AUDIENCE_CUSTOMER,
        # ⚠ **PRINT, AND ONLY PRINT — the one event of the thirteen whose class
        # is a LETTER.** `catalogs.AUTHORED_CATALOGS["writeoff_notice"]` is
        # `GROUP_PRINTABLE` on `models.CHANNEL_PRINT` and its palette carries
        # `{utility_address}`, which only a posted letter needs. Offering email
        # here would be a toggle over a body written for paper.
        channels=(P,),
        template_classes={P: "writeoff_notice"},
        # `notice` — CAT_COLLECTIONS by the rule stated in the payments block
        # above — which carries BR-NOT-024's floor. So the floor and the ask are
        # the SAME channel here, and this letter cannot be switched off at all.
        # That is the correct outcome for a document stating that a balance was
        # removed from a customer's account.
        source_type="notice",
        timing_key="on_write_off_approved",
    ),
    # ⚠ ADDED 2026-10-29 · `DEF-NOT-10649` — THE TWO MOMENTS AFTER THE LADDER.
    # PO, verbatim: *"1 A, 2 A, 3 A, 4 A"* (decision log *"A cut and a
    # restoration TELL THE CUSTOMER"*): both messages; email and SMS, each only
    # where the customer has it and (SMS) consented; automatic and ON by
    # default, switchable here; a default safety text each utility edits.
    # Until this commit *Mark as cut* billed, charged $75.00 and wrote
    # *Disconnected* and the customer heard nothing — the three rows above stop
    # at the 48-hour notice.
    #
    # LIVE from their first commit (`customers.disconnects.commit_cut` and
    # `.restore_service`, through `customer_events`), so both seed ON.
    # `service_state` — a kind of their own with NO print floor, because
    # `account` carries BR-NOT-024's floor and would post a letter the PO did
    # not ask for (2A) and no utility could switch off (3A). So a utility
    # switching either event off gets no row at all.
    EventClass(
        key="service_disconnected",
        category=CATEGORY_COLLECTIONS,
        audience=AUDIENCE_CUSTOMER,
        channels=(E, S),
        template_classes={E: "service_disconnected_guide", S: "sms_service_disconnected"},
        source_type="service_state",
        timing_key="on_cut",
    ),
    EventClass(
        key="service_restored",
        category=CATEGORY_COLLECTIONS,
        audience=AUDIENCE_CUSTOMER,
        channels=(E, S),
        template_classes={E: "service_restored", S: "sms_service_restored"},
        source_type="service_state",
        timing_key="on_restore",
    ),
    # ── 4 · Field work — the customer told about a visit ───────────────────
    #
    # ⚠ **THESE THREE CARRIED `trigger_blocked_by="OQ-249"` UNTIL 2026-10-04
    # (`CR-168-BRC10` P6.1/P6.5, lane SRV-5), AND THE FOURTH (`visit_moved`) IS
    # NEW.** Ruling 3 (23 Sep): *"Notification reaches the consumer and the back
    # office"* — four consumer kinds: booked, moved, on the way, done. Work fires
    # each through `work_customer_messages.queue_visit_message` (by name, from
    # `apps/work/visit_notices.py`): booked when a job with a customer first gets
    # its date, moved when that date or window changes, on the way when the
    # technician departs, done when the office ACCEPTS a passed job. The queue
    # kind is `appointment` (`OQ-WRK-1495`: never `notice`); no print floor.
    # Channels are the customer's reach as a BILL reads it — email whenever an
    # email is on file, SMS with `.sms_reminders` consent (`DEF-WRK-10663`, PO
    # 2026-10-29 B1 A; it was `accounts.paperless` until then) — ∩ these
    # toggles; the do-not-send list holds a row rather than dropping it
    # (`DEF-NOT-5632`).
    #
    # ⚠ **A UTILITY SEEDED BEFORE 2026-10-04 HOLDS A STORED RULE SEEDED OFF FOR
    # THE FIRST THREE** (they were drawn and refused) and it stays off until a
    # supervisor switches it on — SRV-4's `sla_breach` precedent: the switch is
    # theirs, and the seeded answer was right for its day. `visit_moved` has no
    # stored row on such a utility and reads the catalogue's default (on).
    # ⚠ **ADDED 2026-10-29 (`DEF-WRK-10652`, PO ruling 1A, *"1A 2A 3B 4A,
    # start"*).** A job WITH A CUSTOMER raised WITHOUT a visit window tells the
    # customer *Work order logged — we'll confirm a date*. Work fires it after
    # the raise commits (`visit_notices.after_raise`); a raise that books a
    # window is told `appointment_window` only, never both. The same customer
    # election ∩ these toggles, the same `appointment` kind, no print floor.
    EventClass(
        key="work_order_logged",
        category=CATEGORY_FIELD_WORK,
        audience=AUDIENCE_CUSTOMER,
        channels=(S, E),
        template_classes={E: "service_work_order_logged", S: "sms_work_order_logged"},
        source_type="appointment",
        timing_key="on_raise",
    ),
    EventClass(
        key="appointment_window",
        category=CATEGORY_FIELD_WORK,
        audience=AUDIENCE_CUSTOMER,
        channels=(S, E),
        template_classes={E: "service_appointment", S: "sms_visit_booked"},
        source_type="appointment",
        timing_key="on_scheduling",
    ),
    EventClass(
        key="visit_moved",
        category=CATEGORY_FIELD_WORK,
        audience=AUDIENCE_CUSTOMER,
        channels=(S, E),
        template_classes={E: "service_visit_moved", S: "sms_visit_moved"},
        source_type="appointment",
        timing_key="on_visit_moved",
    ),
    EventClass(
        key="technician_on_the_way",
        category=CATEGORY_FIELD_WORK,
        audience=AUDIENCE_CUSTOMER,
        channels=(S,),
        template_classes={S: "sms_technician_on_the_way"},
        source_type="appointment",
        timing_key="eta_push",
    ),
    EventClass(
        key="completion_receipt",
        category=CATEGORY_FIELD_WORK,
        audience=AUDIENCE_CUSTOMER,
        channels=(E,),
        template_classes={E: "service_work_completed"},
        source_type="appointment",
        timing_key="on_completion",
    ),
    # ⚠ ADDED 2026-08-30 · CR-048 wave B task B11 — the two remaining service
    # wordings. Both are DRAWN AND REFUSED (BR-NOT-018) and neither is new
    # scope: the PO ruled on 2026-08-16 that *"wording can exist before the flow
    # that sends it"*, and these two rows are what makes that wording REACHABLE
    # from the one screen where a utility looks for it (BR-NOT-017, ONE HOME).
    EventClass(
        key="door_hanger_left",
        category=CATEGORY_FIELD_WORK,
        audience=AUDIENCE_CUSTOMER,
        # PRINT ONLY. A door hanger is a piece of card left on a handle;
        # `catalogs` files it `GROUP_PRINTABLE` with `{utility_address}`.
        channels=(P,),
        template_classes={P: "service_door_hanger"},
        # The SAME blocker the three field-work rows above carry — Work is R5
        # (PO 2026-08-16, *"it will be R5 ; you dont need to do anything right
        # now"*). Nothing new is asked of the PO by this row.
        trigger_blocked_by="OQ-249",
        timing_key="on_field_visit",
    ),
    # ⚠ **NOT OQ-249, AND THE DIFFERENCE IS THE WHOLE REASON THIS ROW HAS ITS
    # OWN QUESTION.** A door hanger is left during a VISIT, so Work → Rules
    # fires it and R5 owns it. A planned-outage notice is not field work at all:
    # it is a broadcast to *"everyone on this main"*, and this platform has no
    # outage record, no service-area geometry and no way to select the affected
    # customers — so even with Work built, nothing here would know who to tell.
    # OQ-1161.
    EventClass(
        key="planned_outage_notice",
        category=CATEGORY_FIELD_WORK,
        audience=AUDIENCE_CUSTOMER,
        channels=(E, S),
        template_classes={E: "service_outage_notice"},
        trigger_blocked_by="OQ-1161",
        timing_key="before_planned_outage",
    ),
    # ── 5 · Staff & system — addressee RULED (BR-NOT-021, OQ-261 closed):
    # the initiator, plus every active System Admin for failures. `in_app`
    # joined `channels` on all five with the 2026-08-18 wiring, exactly the
    # one-line-per-event change the old unavailable entry promised. The two
    # events whose live writer is `bulk_summary.queue_bulk_summary` carry its
    # class as their in-app template; the other three have no writer yet
    # (OQ-249 / OQ-262) and no in-app class, so their toggle seeds OFF and the
    # screen says why — BR-NOT-018 unchanged.
    EventClass(
        key="billing_run_completed",
        category=CATEGORY_STAFF_SYSTEM,
        audience=AUDIENCE_STAFF,
        channels=(A, E),
        template_classes={A: "staff_bulk_summary"},
        # `bulk_summary.queue_bulk_summary` queues under `bulk_action`, which has
        # NO print floor — so this event can be suppressed to nothing.
        source_type="bulk_action",
        timing_key="on_run_finished",
    ),
    EventClass(
        key="reconciliation_exceptions",
        category=CATEGORY_STAFF_SYSTEM,
        audience=AUDIENCE_STAFF,
        channels=(A, E),
        template_classes={A: "staff_bulk_summary"},
        source_type="bulk_action",
        timing_key="on_exception",
    ),
    # ── `CR-136-BRC07` task `P2.11`, 2026-09-23 — THE UNCLOSED TILL ────────
    #
    # Blueprint p017: *"Notifications: the unclosed till · A supervisor is
    # told · rule_catalog.py · Nobody has to notice a missing count by
    # looking."* This is that row.
    #
    # **IT TELLS AND IT NEVER CLOSES.** PO ruling 2026-09-23 §3.1, verbatim:
    # *"(a) Your ruling stands — no auto-close. A System Admin closes it. Dana
    # cannot work Tuesday until someone is free to do that"*. The blueprint
    # drew a midnight auto-close at `P2.18` and the PO struck it, so this event
    # is the ONLY thing that makes an unclosed till visible without somebody
    # opening screen 3·1 and looking — and a System Admin is precisely who must
    # act, because a forced close is now the only way the till gets sealed.
    #
    # **WHY IT IS A SET-12 ROW RATHER THAN A `queue_staff_alert`.** BR-NOT-017
    # is signed: *"ONE HOME: every notification rule, internal and external,
    # lives on Settings → Notifications"*. `queue_staff_alert` is the one
    # documented exception (DEF-3422) and its reasoning does not reach here:
    # it exists because *"there is no SET-12 row for the product's own setup
    # not finishing, and inventing one would let a utility switch off an
    # operational failure it has no reason to know exists."* A till left open
    # is not the product failing — it is the utility's own shift, a thing every
    # counter supervisor already has a word for, and it belongs beside
    # `reconciliation_exceptions` on the same screen and under the same rule.
    #
    # **`source_type="bulk_action"` HAS NO PRINT FLOOR** (BR-NOT-024 puts the
    # floor on `invoice`, `payment`, `notice` and `plan`), so a utility CAN
    # switch this off entirely — the same exposure `billing_run_completed` and
    # `reconciliation_exceptions` already carry, accepted rather than
    # discovered. Recorded in the decision-log row of 2026-09-23.
    #
    # It has a LIVE writer from its first commit — `apps/payments/
    # counter_watch.py` through `apps/payments/run_alert_seam.py` — so it
    # carries NO `trigger_blocked_by`, unlike the three below it.
    EventClass(
        key="counter_left_open",
        category=CATEGORY_STAFF_SYSTEM,
        audience=AUDIENCE_STAFF,
        channels=(A, E),
        template_classes={A: "staff_bulk_summary"},
        source_type="bulk_action",
        timing_key="end_of_banking_day",
    ),
    # ── `CR-142-BRC07` task `P4.10`, 2026-09-27 — THE SCHEDULED REPORT ────
    #
    # Brief p14, the phase's own DONE WHEN: *"A schedule set on Friday
    # produces a file on Monday, delivered to named internal staff."* Until
    # this row the product did the first half: `apps/reports/schedules.py`
    # fired the run, the file appeared on screen `5·1`, and **nobody was
    # told**. A schedule stores its recipients (`BR-REP-020`) and nothing
    # read them after the picker — which is hard-won law 2's mirror on the
    # server: a stored list behind no delivery.
    #
    # **EMAIL ONLY, AND IN-APP IS ABSENT ON PURPOSE.** The five rows above
    # carry `(A, E)` because a bulk action is something a clerk started and is
    # watching. A schedule is the opposite — it fires at 06:00 on a day nobody
    # is at the screen, which is the entire reason it exists — so a bell in a
    # session nobody is in is not delivery. `BR-REP-017` names the channel:
    # *"scheduled-report email ships W6 with all email; v1 = download only"*,
    # and `US-REP-015` is explicit that the queue ROWS are written now and the
    # dispatch is flipped later. This row is the rule those rows are read
    # under.
    #
    # **`source_type="report"` HAS NO PRINT FLOOR**, so a utility CAN switch
    # this off to nothing — `BR-NOT-024` puts the floor on customer documents
    # and a staff report is not one. That exposure is the same one
    # `billing_run_completed` and `counter_left_open` already carry, accepted
    # rather than discovered.
    #
    # It has a LIVE writer from its first commit — `apps/reports/delivery.py`
    # through `apps/reports/notifications_seam.py` — so it carries no
    # `trigger_blocked_by`.
    EventClass(
        key="scheduled_report_ready",
        category=CATEGORY_STAFF_SYSTEM,
        audience=AUDIENCE_STAFF,
        channels=(E,),
        template_classes={E: "email_scheduled_report"},
        source_type="report",
        timing_key="on_run_finished",
    ),
    # ── `CR-188-BRC10` (PO 2026-10-22) — A MEMBER OF STAFF'S OWN SIGN-IN ──
    #
    # *Create user* emails an invitation and *Reset temp password* / *Resend
    # invitation* a reset, each with a one-time sign-in link and never a
    # password (answer 1). Email only; LIVE writer from the first commit
    # (`apps/identity/password_links.py` through `seams/notifications_seam.py`).
    # Sent instantly at the highest priority (PO 2026-10-22, *"this should be
    # instant email"*) through `services.send_now`.
    EventClass(
        key="staff_user_invited",
        category=CATEGORY_STAFF_SYSTEM,
        audience=AUDIENCE_STAFF,
        channels=(E,),
        template_classes={E: "staff_user_invite"},
        source_type="staff_access",
        timing_key="on_user_created",
        staff_recipient_policy_override=STAFF_ACCESS_RECIPIENT_POLICY,
    ),
    EventClass(
        key="staff_password_reset",
        category=CATEGORY_STAFF_SYSTEM,
        audience=AUDIENCE_STAFF,
        channels=(E,),
        template_classes={E: "staff_password_reset_link"},
        source_type="staff_access",
        timing_key="on_password_reset",
        staff_recipient_policy_override=STAFF_ACCESS_RECIPIENT_POLICY,
    ),
    # ⚠ **`sla_breach` HAS A WRITER SINCE 2026-10-04 (`CR-168-BRC10` P3.58,
    # lane SRV-4).** This row carried `trigger_blocked_by="OQ-249"` with the
    # comment *"There is no SLA concept anywhere in this codebase — measured
    # 2026-08-17"*. That was true that day and false from `BR-WRK-018`
    # (`work_priorities.sla_hours`, a stamped `due_at`) onward: a stale body,
    # noted by lane WORK-SRV in round 1. It is now the escalation *Past due* —
    # a Work rule's row fires it, once per job, through
    # `work_escalations.queue_work_escalation` (in-app; email has no template
    # and ships off, BR-SHL-025). ⚠ A tenant provisioned before today holds a
    # stored rule seeded OFF (it was drawn and refused); it stays off until a
    # supervisor switches it on — the switch is theirs, and the seeded answer
    # was correct for the world it was seeded in.
    EventClass(
        key="sla_breach",
        category=CATEGORY_STAFF_SYSTEM,
        audience=AUDIENCE_STAFF,
        channels=(A, E),
        template_classes={A: "staff_field_work"},
        source_type="field_work",
        timing_key="on_sla_breach",
    ),
    # ── `CR-168-BRC10` P3.58 (2026-10-04, lane SRV-4) — SIX ESCALATIONS ─────
    #
    # Ruling 34 (24 Sep): *"add all these escalations in the wireframe"*. A Work
    # rule's *When it stalls* rows fire these, once per job per kind, through
    # `work_escalations.queue_work_escalation` — worded HERE and nowhere else
    # (`BR-NOT-017`, one home), each with the utility's own switch. Who is told
    # is `BR-NOT-021` (whoever acted, plus every System Admin) and, for these
    # rows only, a rule's *Also tell* people ADDED (PO 2026-10-04, *"(a) Allow
    # the extra people, for Work escalations only."*). In-app only: the
    # message is a bell for the office, rendered by FIELD-2's
    # `staff_field_work` class; no email template exists for it and none is
    # offered (a toggle over a channel with no template is a promise).
    EventClass(
        key="work_job_not_assigned",
        category=CATEGORY_FIELD_WORK,
        audience=AUDIENCE_STAFF,
        channels=(A,),
        template_classes={A: "staff_field_work"},
        source_type="field_work",
        timing_key="on_escalation",
    ),
    EventClass(
        key="work_job_not_accepted",
        category=CATEGORY_FIELD_WORK,
        audience=AUDIENCE_STAFF,
        channels=(A,),
        template_classes={A: "staff_field_work"},
        source_type="field_work",
        timing_key="on_escalation",
    ),
    EventClass(
        key="work_job_running_late",
        category=CATEGORY_FIELD_WORK,
        audience=AUDIENCE_STAFF,
        channels=(A,),
        template_classes={A: "staff_field_work"},
        source_type="field_work",
        timing_key="on_escalation",
    ),
    EventClass(
        key="work_hold_overdue",
        category=CATEGORY_FIELD_WORK,
        audience=AUDIENCE_STAFF,
        channels=(A,),
        template_classes={A: "staff_field_work"},
        source_type="field_work",
        timing_key="on_escalation",
    ),
    EventClass(
        key="work_job_failed",
        category=CATEGORY_FIELD_WORK,
        audience=AUDIENCE_STAFF,
        channels=(A,),
        template_classes={A: "staff_field_work"},
        source_type="field_work",
        timing_key="on_escalation",
    ),
    EventClass(
        key="work_approval_overdue",
        category=CATEGORY_FIELD_WORK,
        audience=AUDIENCE_STAFF,
        channels=(A,),
        template_classes={A: "staff_field_work"},
        source_type="field_work",
        timing_key="on_escalation",
    ),
    # ── `CR-168-BRC10` P6.2 (2026-10-04, lane SRV-5) — THE BACK OFFICE TOLD ─
    #
    # Ruling 3's second half: *"at risk, declined, blocked"*. Unlike the six
    # escalations above these need NO rule row on a Work rule — they fire on
    # EVERY job, from the act itself: a technician declines (`mobile.
    # decline_job`), a job is put on hold (`dispatch.hold` — *blocked*: it
    # cannot go ahead, and the hold reason says why), or the hourly sweep finds
    # an open job inside the at-risk window (`promise.at_risk_window_hours`).
    # Each is a FAILURE in `BR-NOT-021`'s sense — the plan is not going to
    # happen as sent — so whoever sent the job to the field AND every active
    # System Admin are told; no *Also tell* (that narrowing is for a rule's
    # escalations only). One message per job per occasion; each its own
    # switch here (P6.4 — *"a tenant chooses per event"*).
    EventClass(
        key="work_job_at_risk",
        category=CATEGORY_FIELD_WORK,
        audience=AUDIENCE_STAFF,
        channels=(A,),
        template_classes={A: "staff_field_work"},
        source_type="field_work",
        timing_key="on_at_risk",
    ),
    EventClass(
        key="work_job_declined",
        category=CATEGORY_FIELD_WORK,
        audience=AUDIENCE_STAFF,
        channels=(A,),
        template_classes={A: "staff_field_work"},
        source_type="field_work",
        timing_key="on_declined",
    ),
    EventClass(
        key="work_job_blocked",
        category=CATEGORY_FIELD_WORK,
        audience=AUDIENCE_STAFF,
        channels=(A,),
        template_classes={A: "staff_field_work"},
        source_type="field_work",
        timing_key="on_hold",
    ),
    # `DEF-WRK-10350` (2026-10-21) — R28, `BR-FLD-00028` (PO ruled): *"No
    # acknowledgement in 5 minutes and dispatch is told"*. Work's
    # `work.alerts_sweep` finds an emergency alert unanswered past its five
    # minutes and asks for this notice once. Until this row existed the kind
    # was refused by name and only an audit row and the office's overdue list
    # carried it. Same audience as the three above (a FAILURE: the sender and
    # every active System Admin), its own switch.
    EventClass(
        key="work_emergency_unacknowledged",
        category=CATEGORY_FIELD_WORK,
        audience=AUDIENCE_STAFF,
        channels=(A,),
        template_classes={A: "staff_field_work"},
        source_type="field_work",
        timing_key="on_emergency_unacknowledged",
    ),
    # ── `CR-168-BRC10` P3.59 (2026-10-04, lane SRV-4) — TWO REMINDERS ───────
    #
    # Ruling 34's second half: *"if reminders can be managed in notifications
    # then remove"* — the rule builder loses its reminders (a `reminders` key is
    # refused at save) and Notifications gains the ones it lacked. A
    # certificate running out within 30 days (the certification watch's own
    # window, `DEF-WRK-9639`) tells every System Admin; a technician's day
    # tells the technician how many jobs they hold today. Both are written by
    # Work's escalation sweep (`apps/work/escalations.py`). *A job waiting for
    # approval* is the escalation `work_approval_overdue` above, set per rule;
    # the customer's day-before visit reminder is `appointment_window`'s
    # timing and travels with the consumer messages (P6, lane SRV-5).
    EventClass(
        key="certificate_expiring",
        category=CATEGORY_FIELD_WORK,
        audience=AUDIENCE_STAFF,
        channels=(A,),
        template_classes={A: "staff_field_work"},
        source_type="field_work",
        timing_key="before_certificate_expiry",
    ),
    EventClass(
        key="technician_day",
        category=CATEGORY_FIELD_WORK,
        audience=AUDIENCE_STAFF,
        channels=(A,),
        template_classes={A: "staff_field_work"},
        source_type="field_work",
        timing_key="start_of_day",
    ),
    EventClass(
        key="daily_digest",
        category=CATEGORY_STAFF_SYSTEM,
        audience=AUDIENCE_STAFF,
        channels=(A, E),
        trigger_blocked_by="OQ-262",
        timing_key="daily_at",
    ),
    EventClass(
        key="security_alerts",
        category=CATEGORY_STAFF_SYSTEM,
        audience=AUDIENCE_STAFF,
        channels=(A, E),
        trigger_blocked_by="OQ-262",
        timing_key="on_security_event",
    ),
    # ── 6 · Account lifecycle — CR-048 wave B task B10, added 2026-08-30 ────
    #
    # ╔══════════════════════════════════════════════════════════════════════╗
    # ║  THE FINDING THESE TWO CLOSE, in the teardown's own words:           ║
    # ║  *"The module that owns moving in has no notification events at all. ║
    # ║   A customer moving in is told NOTHING."*                            ║
    # ╚══════════════════════════════════════════════════════════════════════╝
    #
    # Both wordings have been seeded and unreachable since 2026-08-16:
    # `email_welcome` and `email_move_out_final` are two of the sixteen classes
    # `seeded_wording_without_rule()` counts. Naming them here is what takes
    # them OUT of that count — see the derivation section below, which is why
    # the figure falls to thirteen on this commit with nobody editing a number.
    #
    # **EMAIL ONLY, AND THE ABSENCE OF A PRINT ROW IS THE RULING, NOT AN
    # OVERSIGHT.** BR-NOT-024 (PO 2026-08-29) makes print the floor on
    # `invoice`, `payment`, `notice` and `plan`. A move message is none of the
    # four, and `models.SOURCE_TYPES` gives `move` no floor entry for exactly
    # that reason: inventing a fifth would be this module writing a signed rule.
    # The consequence is deliberate and is what CR-048's first acceptance case
    # asks for — a utility that switches *Move-in welcome* off gets NO row.
    EventClass(
        key="move_in_welcome",
        category=CATEGORY_ACCOUNT_LIFECYCLE,
        audience=AUDIENCE_CUSTOMER,
        channels=(E,),
        template_classes={E: "email_welcome"},
        # `customer_events.queue_move_in_welcome` queues under `move`, keyed on
        # the MOVE RECORD. No floor (see `models.SOURCE_TYPES`).
        source_type="move",
        timing_key="on_move_in",
    ),
    EventClass(
        key="move_out_final_bill",
        category=CATEGORY_ACCOUNT_LIFECYCLE,
        audience=AUDIENCE_CUSTOMER,
        channels=(E,),
        template_classes={E: "email_move_out_final"},
        source_type="move",
        timing_key="on_move_out",
    ),
    # ⚠ **`email_account_closed` ARRIVES HERE 2026-08-30, EXACTLY AS B10 SAID IT
    # WOULD.** B10's own comment stood in this place: *"it is a DIFFERENT moment
    # from a move-out (`close_out.py`, not `services.move_out`) and it belongs to
    # the wave that reviews all thirteen remaining classes together."* This is
    # that wave, and the moment is `customers.close_out.close_out` — the act
    # that makes an account TERMINAL after its service was cut.
    EventClass(
        key="account_closed",
        category=CATEGORY_ACCOUNT_LIFECYCLE,
        audience=AUDIENCE_CUSTOMER,
        channels=(E,),
        template_classes={E: "email_account_closed"},
        # `account` — a NEW source kind (`models.SOURCE_TYPES`), added by this
        # wave for the three account-lifecycle documents below, and given NO
        # print floor for BR-NOT-024's stated reason. See the payments block
        # above for the source-kind rule and the constraint.
        source_type="account",
        timing_key="on_account_closed",
    ),
    EventClass(
        key="deposit_received",
        category=CATEGORY_ACCOUNT_LIFECYCLE,
        audience=AUDIENCE_CUSTOMER,
        channels=(E,),
        template_classes={E: "email_deposit"},
        # ⚠ `account`, NOT `payment`, and the source-kind rule is what decides
        # it: `catalogs.LISTINGS["email_deposit"].category` is
        # CAT_ACCOUNT_LIFECYCLE. A deposit confirmation is correspondence about
        # the account holding a customer's money, not a receipt for a
        # transaction — the receipt for that same payment is a separate document
        # with its own event (`payment_received`) and its own print floor.
        source_type="account",
        timing_key="on_deposit_cleared",
    ),
    # ⚠ **THE TRIGGER FOR THIS ONE HAS EXISTED SINCE W6 AND WAS QUEUEING A
    # DOCUMENT THAT COULD NOT RENDER.** `customers.services._queue_plan_change_
    # email` pinned the code `plan_change`, which nothing in `catalogs.LISTINGS`
    # or `seed_templates.SEEDABLE` declares (DEF-2511 again, the third
    # occurrence this wave found); keyed every one on the ACCOUNT, so a
    # customer's second rate change deduped into their first (DEF-2512 again);
    # rode `source_type="plan"`, which since BR-NOT-024 landed on 2026-08-29
    # means the PAYMENT-PLAN print floor was putting a rate-plan email on paper;
    # and passed no `event_key`, so the switch on SET-12 did nothing. All four
    # are closed on this commit.
    EventClass(
        key="rate_plan_changed",
        category=CATEGORY_ACCOUNT_LIFECYCLE,
        audience=AUDIENCE_CUSTOMER,
        channels=(E,),
        template_classes={E: "email_plan_change"},
        # `account`: `catalogs.LISTINGS["email_plan_change"].category` is
        # CAT_ACCOUNT_LIFECYCLE. The key is called `rate_plan_changed` and not
        # `plan_change` so that no reader of SET-12 confuses it with the three
        # PAYMENT-plan events in collections — the same two words mean two
        # different things in this product and the screen must not blur them.
        source_type="account",
        timing_key="on_rate_plan_changed",
    ),
)

EVENTS_BY_KEY: dict[str, EventClass] = {event.key: event for event in EVENTS}
EVENT_KEYS: tuple[str, ...] = tuple(event.key for event in EVENTS)

#: The count the PO's requirement claims, kept next to the count we built so the
#: discrepancy is a FACT in the code rather than a note somebody remembers.
REQUIREMENT_CLAIMS_EVENT_COUNT = 16
BUILT_EVENT_COUNT = len(EVENTS)


# ══════════════════════════════════════════════════════════════════════════
#  CR-048 TASK B9 — THE THIRD COUNT, DERIVED AND NOT TYPED IN
# ══════════════════════════════════════════════════════════════════════════
# The teardown of 2026-08-29 states three facts and the CR repeats them:
# fifteen events are BUILT, the requirement CLAIMS sixteen, and **sixteen more
# customer messages have wording seeded and no rule to send them**. The first
# two are the constants above. The third is computed below rather than typed
# in, for the reason the CR gives about all three — *"as data in the response,
# not a note somebody remembers"* — and for one more:
#
# **A typed-in 16 goes stale on the day it stops being true, which is the day
# wave B10/B11 lands.** B10 adds three events (move-in, move-out, missed
# payment-plan instalment) and B11 adds thirteen; each one that names a seeded
# class must take that class OUT of this count on the same commit. A constant
# would have to be edited sixteen more times by sixteen different hands, and
# the one that is forgotten leaves the settings screen reporting a gap that has
# already been closed.
#
# THE DERIVATION, IN ONE SENTENCE: **a class this platform seeds wording for,
# that is a MESSAGE, that no event names, and that no live writer reaches by
# some other route.** Four inputs, three of them already code-owned constants.
# It measures 16 today, which is the teardown's own figure reached
# independently — and the sixteen it names are exactly the CR's own task
# breakdown (B10's three plus B11's thirteen), which is the check that this is
# the same set the teardown counted and not a coincidence of arithmetic.

#: Classes a LIVE WRITER already resolves by a route that is NOT a SET-12 rule.
#: They have wording AND a sender, so they are not part of the gap even though
#: no event names them — counting them would report work as missing that is
#: done, which is the same failure as reporting missing work as done.
#:
#: Written as an explicit map with the writer beside each class, for the reason
#: `notices.TIER_TO_CLASS` gives about itself: a name-derived rule would
#: silently absorb a class somebody added. `test_cr048_b_engine_on.py` asserts
#: every key here is still a class this platform seeds, so a class that is
#: renamed or dropped fails the suite rather than quietly inflating the count.
WRITER_REACHED_CLASSES: dict[str, str] = {
    "dunning": (
        "notifications.notices.generate_reminder resolves it (BR-NOT-008's two "
        "reminder stages). The `past_due_reminder` event offers email and SMS "
        "and has no print switch, so no rule governs this printed class — but a "
        "writer does send it."
    ),
    "receipt": (
        "apps.payments.receipts pins it by code when a payment is recorded. The "
        "`payment_received` event offers email only, so this printed receipt is "
        "outside every rule and inside a live flow."
    ),
    "disconnect_notice_5_day": (
        "notifications.notices.generate_disconnect_notice resolves it through "
        "TIER_TO_CLASS at BR-NOT-014's second tier. The `disconnect_notice` "
        "event names the first tier's class, and one event rules the ladder."
    ),
    "disconnect_notice_48_hour": (
        "the same writer at BR-NOT-014's final tier — see the entry above."
    ),
    #: ⚠ **THE FIRST ENTRY HERE WHOSE WRITER IS A PERSON** (`CR-094-BRC01` wave
    #: K, `ACC-S16`, 2026-09-12). Every other class in this map is reached by a
    #: flow the product runs; this one is reached by a clerk pressing *Queue the
    #: message* on an account.
    #:
    #: **IT HAS NO SET-12 EVENT ON PURPOSE AND MUST NEVER BE GIVEN ONE.** A
    #: SET-12 rule lets a utility switch off a CLASS of automatic message. A
    #: clerk writing to a customer on a collections call is not that: a rule
    #: that silently swallowed it would leave the clerk believing they had
    #: written to somebody when nothing was written at all, and the settings
    #: screen would offer a switch whose real effect is to break a button.
    "account_message": (
        "customers.communication_api.account_communication queues it — the "
        "Communication dialog on an account (ACC-S16). The writer is a CLERK "
        "and not a flow, so no SET-12 rule governs it and none should: a "
        "utility may not switch off its own staff's typing."
    ),
    #: `DEF-CWP-10381` (2026-10-22) — the customer portal's reset link. **No
    #: SET-12 event, on purpose, for `account_message`'s reason:** it is asked
    #: for by the person who then waits for it, and a switch that swallowed it
    #: would lock every customer out while the screen said *check your email*.
    "portal_password_reset": (
        "portal.credentials.send_reset queues it when a customer with a portal "
        "login asks for a new password, and hands it to the instant send. The "
        "writer is the customer's own request, so no SET-12 rule governs it."
    ),
    #: `CR-189-BRC10` / `DEF-CWP-10402` (2026-10-22) — the portal's one-time
    #: codes and the changed-email notice. Same reason as the reset link: each
    #: is asked for by the customer standing at the screen (or, for the notice,
    #: is the security warning to the old address), and a switch that
    #: swallowed it would lock them out or hide a takeover.
    "portal_enrolment_code": (
        "portal.credentials.queue_code queues it when a customer signs up, adds "
        "an account, confirms a payment change or updates their email, and hands "
        "it to the instant send. The writer is the customer's own request."
    ),
    "portal_email_change_code": (
        "portal.email_update queues it to the NEW address a customer typed on "
        "Update your email, and sends it instantly. The customer's own request."
    ),
    "portal_email_changed_notice": (
        "portal.email_update queues it to the OLD address once a change is "
        "confirmed. A security notice; no utility may switch it off."
    ),
}

#: Catalogue KINDS that are not a message at all. `bill_insert` is a PDF PAGE
#: bound into a bill: it has no channel, no recipient and no rule to have,
#: because it is not sent — it is part of something else that is. Counting it
#: as an unsent customer message would put a row on this report that no event
#: could ever close.
NON_MESSAGE_KINDS: frozenset[str] = frozenset({"PDF page"})

#: What the 2026-08-29 teardown counted, kept beside the derived figure exactly
#: as `REQUIREMENT_CLAIMS_EVENT_COUNT` sits beside `BUILT_EVENT_COUNT`. The two
#: agree today. If a later change makes them disagree, the DERIVED number is
#: the true one and the disagreement is a fact worth seeing rather than an
#: assertion worth failing.
TEARDOWN_CLAIMS_UNRULED_COUNT = 16

#: ⚠ **THE TWO ABOVE PARTED COMPANY ON 2026-08-30, ON PURPOSE, AND THIS IS THE
#: RECONCILIATION.** B9's own docstring predicted it — *"a typed-in 16 goes
#: stale on the day it stops being true, which is the day wave B10/B11 lands"* —
#: and B10 is that day. Three classes were adopted by three new events, so the
#: derived count is now THIRTEEN while the teardown's historical figure stays
#: SIXTEEN. Neither number is wrong and neither should be edited: 16 is what was
#: true on 2026-08-29 and 13 is what is true now.
#:
#: What would be wrong is the two disagreeing with no stated reason, so the
#: bridge is CODE rather than prose: class → the event that adopted it, and
#: `coverage()` publishes `13 + 3 = 16` as an arithmetic tie-out a reader can
#: check. When B11 adopts its thirteen, each one is appended here on the same
#: commit and the sum still reconciles — which is the same discipline
#: `WRITER_REACHED_CLASSES` keeps one constant up.
#:
#: ⚠ **AND ON 2026-08-30 IT CLOSED COMPLETELY — B11 ADOPTED THE REMAINING
#: THIRTEEN AND THE DERIVED GAP IS NOW ZERO.** The tie-out is exact and is the
#: check worth reading: `0 + 16 = 16`. Every one of the teardown's sixteen
#: classes is named by an event, so `seeded_wording_without_rule()` returns an
#: empty tuple and `reconciles` is still True — which is the property this
#: bridge was built for and the first time it has been tested at the boundary.
#:
#: ⚠ **ZERO DOES NOT MEAN THIRTEEN MESSAGES NOW GO OUT.** Seven of B11's
#: thirteen have a LIVE trigger; five are DRAWN AND REFUSED (BR-NOT-018) with
#: the question that owns each absence on the row; the thirteenth
#: (`sms_payment_received`) joined an event that already existed. A class leaves
#: this gap when a RULE names it, which is what the gap measures — *"wording
#: seeded and no rule to send it"* — and a row that refuses by name is a rule.
#: The count that answers *"how many of these can actually fire"* is a different
#: one and is already on the wire per row: `trigger_blocked_by`.
ADOPTED_SINCE_TEARDOWN: dict[str, str] = {
    # ── wave B10, 2026-08-30 (three) ────────────────────────────────────────
    "email_welcome": "move_in_welcome",
    "email_move_out_final": "move_out_final_bill",
    "plan_notice_missed": "payment_plan_instalment_missed",
    # ── wave B11, 2026-08-30 (thirteen) · LIVE TRIGGER ──────────────────────
    "plan_notice_upcoming": "payment_plan_instalment_upcoming",
    "sms_payment_received": "payment_received",  # a channel, not a new event
    "email_refund_issued": "refund_issued",
    "email_credit_issued": "credit_issued",
    "writeoff_notice": "write_off_approved",
    "email_account_closed": "account_closed",
    "email_deposit": "deposit_received",
    "email_plan_change": "rate_plan_changed",
    # ── wave B11 · DRAWN AND REFUSED, with the question that owns it ────────
    "email_statement": "statement_ready",  # OQ-1160 — no statement in the product
    "service_outage_notice": "planned_outage_notice",  # OQ-1161 — no outage record
    "email_autopay": "autopay_enrolled",  # OQ-1162 — autopay is capture-only
    "plan_notice_void": "payment_plan_voided",  # OQ-1163 — nothing voids a plan
    "service_door_hanger": "door_hanger_left",  # OQ-249 — Work is R5
}


def ruled_template_classes() -> frozenset[str]:
    """Every template class some event names, on any channel.

    A class in here has a rule: a System Admin can switch its channel off on
    SET-12 and the queue now obeys them (CR-048 wave A).
    """
    named: set[str] = set()
    for row in EVENTS:
        named.update(row.template_classes.values())
    return frozenset(named)


def seeded_wording_without_rule() -> tuple[str, ...]:
    """The classes with wording written and nothing that can ever send them.

    Sorted, so the wire order is stable and a diff of two responses is
    readable. Imports at CALL time — `seed_templates` imports `catalogs` which
    imports this module's neighbours, and a module-level import here would be a
    cycle for the sake of a number nobody needs at import time.
    """
    from apps.notifications import catalogs, seed_templates

    ruled = ruled_template_classes()
    gap: list[str] = []
    for seed in seed_templates.SEEDABLE:
        if seed.code in ruled or seed.code in WRITER_REACHED_CLASSES:
            continue
        # DEF-BIL-4454 — a *What changed* sentence is sent by its host
        # email's rule (`catalogs.PRINTED_INSIDE`), never on its own.
        if catalogs.PRINTED_INSIDE.get(seed.code) in ruled:
            continue
        listing = catalogs.LISTINGS.get(seed.code)
        if listing is not None and listing.kind in NON_MESSAGE_KINDS:
            continue
        gap.append(seed.code)
    return tuple(sorted(gap))


def coverage() -> dict[str, Any]:
    """CR-048 B9's three counts, as data a screen can render without arithmetic.

    Deliberately carries the CODES as well as the counts: a bare integer is a
    claim, and a list is something a person can check. The screen is free to
    show only the number.
    """
    unruled = seeded_wording_without_rule()
    return {
        "built_event_count": BUILT_EVENT_COUNT,
        "requirement_claims_event_count": REQUIREMENT_CLAIMS_EVENT_COUNT,
        "seeded_wording_without_rule_count": len(unruled),
        "seeded_wording_without_rule": list(unruled),
        "teardown_claims_seeded_wording_without_rule_count": (TEARDOWN_CLAIMS_UNRULED_COUNT),
        "writer_reached_without_rule": dict(WRITER_REACHED_CLASSES),
        # CR-048 B10 — the bridge between the two counts above, as arithmetic
        # rather than as a sentence. `reconciles` is the whole assertion: if it
        # ever reads False, a class left the gap by some route nobody wrote
        # down, and THAT is the fact worth seeing.
        "teardown_reconciliation": {
            "teardown_count": TEARDOWN_CLAIMS_UNRULED_COUNT,
            "adopted_since_teardown": dict(ADOPTED_SINCE_TEARDOWN),
            "adopted_since_teardown_count": len(ADOPTED_SINCE_TEARDOWN),
            "derived_count_now": len(unruled),
            "reconciles": (
                len(unruled) + len(ADOPTED_SINCE_TEARDOWN) == TEARDOWN_CLAIMS_UNRULED_COUNT
            ),
        },
    }


def event(key: str) -> EventClass:
    """The event class, or a KeyError naming the whole vocabulary."""
    try:
        return EVENTS_BY_KEY[key]
    except KeyError as missing:
        raise KeyError(
            f"{key!r} is not a notification event. The vocabulary is a CONSTANT "
            f"({', '.join(EVENT_KEYS)}) — a tenant cannot invent an event, because "
            "only a writer in this codebase can fire one."
        ) from missing


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-017@cr009a17 (12-governance/11-change-requests.md → CR-009 in full, including the three PO ruling sets of 2026-08-17 · 04-docs/05-modules/10-notifications/02-business-rules.md · apps/notifications/catalogs.py (the template classes named here) · apps/notifications/models.py CHANNELS/SOURCE_TYPES)
# generated: 2026-08-17 by story-coder (CR-009 SET-12/SET-12D lane)
# checklist: A✔ B✔ C✔ D=deferred(constants only — the routes are rules_api.py) E=deferred(no-frontend-half — NotificationRules.tsx consumes this over the wire) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see rules_api.py and rule_service.py trailers — this file ships with them
# exceptions: (0) [CR-048 B9, 2026-08-29] THE THIRD COUNT IS DERIVED, NEVER TYPED IN. `seeded_wording_without_rule()` measures the seeded template catalogue against the event catalogue and reports SIXTEEN classes with wording and no rule — the teardown's own figure, reached independently, and the same sixteen the CR's tasks B10 (three) and B11 (thirteen) name. It is a computation and not a constant so that it FALLS ON ITS OWN as those waves land; a hardcoded 16 would need editing sixteen more times by sixteen hands. Two exclusions are stated rather than implied: `WRITER_REACHED_CLASSES` (four classes a live writer already sends by another route) and `NON_MESSAGE_KINDS` (`bill_insert` is a PDF page bound into a bill, not a message anything could send). `TEARDOWN_CLAIMS_UNRULED_COUNT` sits beside the derived figure exactly as `REQUIREMENT_CLAIMS_EVENT_COUNT` sits beside `BUILT_EVENT_COUNT`, so a future disagreement is visible rather than silently resolved. (1) FIFTEEN EVENTS, NOT SIXTEEN. The requirement claims 16 and names 15; both counts are constants here and the discrepancy is REPORTED (decision log 2026-08-17), never resolved by inventing a row. (2) NO MEDICAL/LIFE-SUPPORT FILTER — PO ruling 2026-08-17 *"Skip it ; not required as this point of time"*; absent by ruling, recorded here because the clause IS in the PO's written requirement. (3) [AMENDED 2026-08-18] TWO NAMED CHANNELS DO NOT EXIST (Portal, Mail) and are carried as `unavailable_channels` with a reason each rather than as toggles; In-app LEFT that dictionary when OQ-261 closed and is a real channel on the five staff events. (4) SIX EVENTS HAVE NO TRIGGER — three field-work on OQ-249, three staff/system on OQ-262 — and say so on the wire. (5) [AMENDED 2026-08-18] NO STAFF RECIPIENT is settable anywhere — no longer because the question is open, but because the answer is a RULED PLATFORM POLICY (BR-NOT-021: initiator + all System Admins on failure), served per row as `staff_recipient_policy`.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
