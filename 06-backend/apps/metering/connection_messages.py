# ── Trace ──────────────────────────────────────────────
# Story:    New Connect step 7 — `Telling the customer`
#           Screens: 05-prototype/02 Accounts Menu Blueprint.pdf p091, read AS
#           AN IMAGE at scale 2 (B14 rule 42)
# Rules:    PO ruling 2026-09-16 (step 7 is THREE messages, not the drawn six) ·
#           OQ-MET-12360 CLOSED 2026-09-16 (*"using existing template and
#           notification"*) · BR-MET-112 (nothing is written until the last
#           button) · BR-MET-113 (the owner account every connection charge is
#           tagged to) · BR-MET-115 (the completion letter, which is NOT one of
#           these three) · BR-BIL-025 (three axes, two fallbacks) ·
#           BR-BIL-036 (print is the floor) · BR-NOT-005 (queue only) ·
#           BR-NOT-013 (no adapter on any channel) · BR-NOT-002 (a contract
#           version is effective-dated and cannot be seeded) ·
#           CLAUDE.md hard rule 1 (tenant scoping) · rule 7 (audit) ·
#           B14 rules 31, 32, 33, 37, 42
# Blocked:  OQ-379 (the quote is
#           recorded and posted by nothing, which blocks message three twice)
# Tests:    06-backend/tests/test_new_connect_step7_messages.py
# Impacts:  apps/notifications/catalogs.py (two new classes) ·
#           apps/notifications/seed_templates.py (their two bodies) ·
#           apps/notifications/connection_events.py (the picker read) ·
#           apps/metering/seams.py (three resolutions)
# ───────────────────────────────────────────────────────
"""The three messages a new build sends its owner, and who they go to.

╔══════════════════════════════════════════════════════════════════════════╗
║  WHAT THIS IS FOR, in one sentence a clerk would recognise:              ║
║  when somebody presses Create connection, the owner is told the build    ║
║  exists, sent the agreement for it, and told what it costs.              ║
╚══════════════════════════════════════════════════════════════════════════╝

PO, 2026-09-16, verbatim:

    *"in this step we have to do the communication with owner that request is
    created - may be we ahve to send contract , maybe we have to send cost and
    ask them to pay it - all this communciation will be required here and we
    have to make it 3 or 3 communciiton default thats - all these 6-8 line
    items are not required"*

────────────────────────────────────────────────────────────────────────────
THE DRAWN SIX BECOME THREE, AND WHICH THREE IS NOT OBVIOUS FROM THE COUNT
────────────────────────────────────────────────────────────────────────────
p091 draws SIX rows. The ruling keeps three, and a lane that simply took the
first three would take the wrong ones — the drawing's order is not the
ruling's. Each departure has a DIFFERENT reason, which is why they are listed
in `NOT_AT_CREATION` with their own words rather than deleted:

  * *Schedule of works*, *Inspection booked*, *Welcome pack* — the PO's
    *"not required"*. Two of the three were already drawn UNTICKED, and p091
    says why in its own voice: *"An SMS about a booking nobody has made yet has
    nothing to say, and the welcome pack belongs to whoever moves in rather
    than to the developer."*
  * *Unit energised* — **NOT dropped, and this is the one worth reading
    twice.** Its drawn `WHEN` is *As each unit activates*, so it never fired on
    commit even in the picture, and `BR-MET-115` already moved that letter to
    the work-order screen (PO 2026-08-25: *"sent it whnr utility user mar that
    job complete traigger it tat that time"*). It is a different message at a
    different moment with its own ruling. Recording it as "dropped" would
    quietly reverse a PO ruling by bookkeeping.

⚠ **AND THE STATUS MESSAGE IS NOT HERE EITHER, FOR THE SAME KIND OF REASON.**
The PO also said, earlier the same day, *"we need to send mesage that request
is created and what is the status of request"*. A STATUS message fires on a
STATE CHANGE, not at creation, so it was never one of this step's defaults.
Two genuine rulings look contradictory until the trigger is named (CLAUDE.md
law 13), so the trigger is named here rather than re-asked.

────────────────────────────────────────────────────────────────────────────
THE CONTRACT NEEDED NOTHING BUILT, WHICH IS THE WHOLE OF `OQ-MET-12360`
────────────────────────────────────────────────────────────────────────────
PO, closing it the day it was minted: *"using existing template and
notification"*. So the contract is **a document we render and send** — not an
agreement signed and returned. Nothing waits for it to come back, no file is
stored, no state is added to a connection, and **no gate stands in front of
energising a build.**

And the template it uses already existed: **`contract_service_agreement`**, in
the `contracts` group, whose platform wording states the shape of the bargain
and defers every figure to the utility's own published policy. A second
`new_connect_contract` class beside it would have been two documents stating
terms for one service.

⚠ **A CONTRACT CLASS HAS NO PUBLISHED VERSION UNTIL A SYSTEM ADMIN PUBLISHES
ONE, AND THAT IS `BR-NOT-002` RATHER THAN A GAP HERE.** Every contract version
is effective-dated and `seed_notice_templates` REFUSES to seed one, because
there is no human in a provisioning transaction to choose that date. So on a
utility that has not published its agreement, message two reports that it has
no wording — by name, with the reason — instead of queueing a blank.

────────────────────────────────────────────────────────────────────────────
⚠ HISTORY — `OQ-376`, ANSWERED BY `OQ-NOT-12521` (2026-09-21) AND BUILT
2026-10-02 (`CR-163-BRC10`): `connection` IS NOW A SOURCE KIND, and the
section below describes the world before it. Read it as why, not as now.
────────────────────────────────────────────────────────────────────────────
`queue_document` takes its `source_type` from a platform CONSTANT of fourteen
kinds and **`connection` is not one of them.** Measured against real
PostgreSQL on 2026-09-16, the queue answers:

    'connection' is not a source kind this platform queues (invoice, payment,
    notice, plan, report, ledger, test, bulk_action, move, account, portal,
    appointment, message, service_request). The vocabulary is a CONSTANT, not
    a tenant lookup — a tenant cannot invent a source the platform has no
    writer for, and a row nothing recognises is a message nothing will ever
    send.

That is `OQ-376`, OPEN, and this module **does not answer it** (prime
directive: never resolve an open question by choosing a value). Its option (B)
— send them as `notice` — is the tempting one and is wrong: the kind is what
reports group by, so a connect letter filed as a notice is counted among
disconnection notices and shows up only in somebody's monthly figures.

So every occasion returns `not_sent` carrying the platform's own sentence and
`tracks: "OQ-376"`. **It never reports a message it did not queue.**

────────────────────────────────────────────────────────────────────────────
⚠ AND MESSAGE THREE IS BLOCKED A SECOND TIME, BY MONEY — `OQ-379`
────────────────────────────────────────────────────────────────────────────
*"What it costs, please pay it"* has to say what it costs. `connection.
quote_total` is a RECORDED figure and nothing posts it — `commit_connection`
says so itself on every build, as the `quote_recorded_not_posted` absence. The
step-8 drawing says the same in orange: *"the quote stands on the build and the
money has nowhere to post."*

**So this module will not put that number in a letter.** A figure a customer
is asked to pay, that no ledger holds, is a promise the books cannot honour;
`{amount_due}` is MANDATORY CONTENT on the class for exactly that reason, and
the guard here is what keeps the two facts consistent. When the quote reaches
the books, `_amount_owed` is the one function that changes and the letter
needs no edit.

────────────────────────────────────────────────────────────────────────────
NOTHING IS SENT, AND NO SURFACE BUILT ON THIS MAY SAY OTHERWISE
────────────────────────────────────────────────────────────────────────────
p091 says it in red: *"Everything here is queued, and nothing is sent. This
product writes a row per message and no sender picks it up — no email, no
text, no print file."* `BR-NOT-013`. `nothing_is_sent()` publishes that fact so
no screen has to remember it — a control reading *sent* over a row nobody
delivers is hard-won law 2's mirror, and the customer portal shipped eight of
those in one day on 2026-09-05.

────────────────────────────────────────────────────────────────────────────
NO TABLE, AND THAT IS `BR-MET-112` RATHER THAN A CORNER CUT
────────────────────────────────────────────────────────────────────────────
The drawn ticks and the drawn radio are a CLERK'S CHOICES, and every step of
this wizard is a draft until the last button: *"nothing is written until step
9"*. So the choices ride on the commit payload and are read here — there is
nowhere for a half-finished step 7 to be stored, and `OQ-MET-12360` says in as
many words that this needs **"no schema at all"**.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from apps.metering import seams
from core import audit as core_audit
from core import errors
from core import tenancy as core_tenancy

BR_REF = "BR-MET-112"

#: What happened to one message. Three words, and they stay distinguishable
#: because a dashboard counts them: we wrote a row · we did not and here is why
#: · the clerk asked us not to.
STATE_QUEUED = "queued"
STATE_NOT_SENT = "not_sent"
STATE_NOT_ASKED = "not_asked"

#: The one moment these three share. Named rather than implied, because the two
#: messages this step does NOT own are defined by having a different one.
WHEN_ON_COMMIT = "on_commit"

#: Why a message did not go, when the commit itself was fine. CODES, never
#: sentences — B14 rule 32 keeps our vocabulary off a clerk's screen, so the
#: front end renders each one through its own eleven catalogues (rule 35).
REASON_PLATFORM_HAS_NO_WRITER = "the_platform_cannot_file_a_connection_message_yet"
REASON_NO_WORDING = "this_utility_has_not_published_wording_for_this_one"
REASON_AMOUNT_NOT_IN_THE_BOOKS = "the_amount_is_not_in_the_books_yet"
REASON_NO_OWNER_ACCOUNT = "this_build_names_no_owner_account"
REASON_CLERK_UNTICKED = "the_clerk_did_not_ask_for_this_one"
#: ⚠ **`Q8`, PO 2026-10-02: *"messages fire on approval (BR-MET-115)"*.** The
#: three letters are no longer queued when the build is CREATED; they wait for
#: approval, which `fire_on_approval` below is for (`CR-162-BRC10`), and a clerk can send any
#: of them sooner with *Send now* (`CR-163-BRC10` item 26).
REASON_SENT_ON_APPROVAL = "sent_on_approval"
#: ⊕ `DEF-MET-9229` — the utility has no published template for this letter, so
#: there is nothing to render and nothing is queued (step 5 already says so).
REASON_NO_TEMPLATE = "no_template"


def template_published(code: str | None) -> bool | None:
    """`True` when this utility has a PICKABLE (published) variant of the
    template class `code`, `False` when it has none, `None` when notifications
    could not be asked. The same read the Messages tab's *No template* uses."""
    rows = seams.connection_templates()
    if rows is None or not code:
        return None
    return any(str(row.get("code")) == code and row.get("pickable") for row in rows)

#: The three channels a clerk may pick on *Send now* — the PO's own list,
#: *"choose channel (email/print/SMS)"*. Spelled as `outbound_messages` spells
#: them (`pdf_print` is print).
SENDABLE_CHANNELS: tuple[str, ...] = ("email", "pdf_print", "sms")
RECIPIENT_OWNER = "owner"
RECIPIENT_CO_APPLICANT = "co_applicant"
#: What a row on the build record says once something was queued for it.
STATE_SENT = "sent"

#: The classes these three render from. STRINGS, resolved by name, because
#: metering may not import notifications (B1 · B2 §2).
CLASS_CONFIRMED = "new_connect_confirmed"
CLASS_CONTRACT = "contract_service_agreement"
CLASS_QUOTE = "new_connect_quote"


@dataclass(frozen=True)
class Occasion:
    """One of the PO's three messages.

    Everything that is NOT a clerk's choice lives here — what it is, when it
    fires, which channels it goes out on and which class renders it. The
    clerk's choices (the tick, the template variant) arrive on the commit
    payload, because `BR-MET-112` gives this wizard nowhere to store them.
    """

    code: str
    when: str
    #: All three are drawn ticked and the PO called them *defaults*.
    send_by_default: bool
    #: ⚠ **THE DRAWING DECIDES THIS AND IT IS NOT UNIFORM.** Message three goes
    #: by email AND on paper — p091: *"Print is the floor here too. The quote
    #: goes by email AND on paper: an owner who never opens the address on file
    #: still gets the figure they owe."* (`BR-BIL-036`.)
    channels: tuple[str, ...]
    template_code: str
    #: True where the letter must state a figure the books hold. Exactly one of
    #: the three, and the guard is `_amount_owed`.
    needs_money: bool = False


#: ⚠ **THE ORDER IS THE PO'S, AND IT IS THE ORDER THEY SAID THEM IN** — the
#: build exists, then the contract, then the cost. Two clerks reading this step
#: must see the same three rows in the same order, and a screen that sorted
#: them itself would be a second opinion about a ruling.
#:
#: ⚠ **NO LABELS HERE, DELIBERATELY.** p091's words — *Build confirmed*,
#: *Quote and what is owed* — are screen copy, which belongs in the eleven
#: catalogues in each language's own vocabulary (B14 rule 35) and never in a
#: server constant. What travels from here is the CODE the screen renders.
OCCASIONS: tuple[Occasion, ...] = (
    Occasion(
        code="build_created",
        when=WHEN_ON_COMMIT,
        send_by_default=True,
        channels=("email",),
        template_code=CLASS_CONFIRMED,
    ),
    Occasion(
        code="contract",
        when=WHEN_ON_COMMIT,
        send_by_default=True,
        #: PRINT, and it is the class's own channel rather than a choice made
        #: here: a contract is a `GROUP_CONTRACT` class and every one of them is
        #: `CHANNEL_PRINT`. An agreement emailed and never posted is the one
        #: document a utility is later asked to produce on paper.
        channels=("pdf_print",),
        template_code=CLASS_CONTRACT,
    ),
    Occasion(
        code="quote_and_what_is_owed",
        when=WHEN_ON_COMMIT,
        send_by_default=True,
        channels=("email", "pdf_print"),
        template_code=CLASS_QUOTE,
        needs_money=True,
    ),
)

OCCASION_CODES: tuple[str, ...] = tuple(one.code for one in OCCASIONS)
_BY_CODE: dict[str, Occasion] = {one.code: one for one in OCCASIONS}


#: ⚠ **THE DRAWN ROWS THIS STEP NO LONGER SENDS, KEPT WITH THEIR REASONS.**
#: A lane reading p091 will find six rows and three here, and the gap has to be
#: explainable or somebody re-adds them. Each `code` is the drawing's row; each
#: `because` is why it is not a creation default; `moved_to` is set only where
#: the message still exists somewhere else, which is the distinction that
#: matters — *dropped* and *fires elsewhere* are different facts.
NOT_AT_CREATION: tuple[dict[str, Any], ...] = (
    {
        "code": "schedule_of_works",
        "because": "po_said_not_required",
        "moved_to": None,
        "ruling": "PO 2026-09-16 — 'all these 6-8 line items are not required'",
    },
    {
        "code": "inspection_booked",
        "because": "po_said_not_required",
        "moved_to": None,
        "ruling": "PO 2026-09-16; drawn UNTICKED, and p091's own reason is that "
        "an SMS about a booking nobody has made yet has nothing to say",
    },
    {
        "code": "welcome_pack",
        "because": "po_said_not_required",
        "moved_to": None,
        "ruling": "PO 2026-09-16; drawn UNTICKED, and p091's own reason is that "
        "the welcome pack belongs to whoever moves in rather than to the developer",
    },
    {
        #: ⚠ NOT a drop. Read the module docstring before touching this row.
        "code": "unit_energised",
        "because": "fires_at_a_different_moment",
        "moved_to": "the work-order screen, when a person marks the job complete",
        "ruling": "BR-MET-115, PO 2026-08-25 — drawn WHEN is 'As each unit "
        "activates', so it never fired on commit even in the picture",
    },
)


def _tenant_id() -> Any:
    """Hard rule 1: no tenant table is touched without `app.tenant_id` set."""
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def occasion(code: str) -> Occasion:
    """The occasion, or a refusal naming what this step actually has."""
    found = _BY_CODE.get(code)
    if found is None:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="metering.connection.messageOccasionUnknown",
            params={"value": str(code)},
        )
    return found


def nothing_is_sent() -> dict[str, Any]:
    """p091's red sentence, published so no screen has to remember it.

    ⚠ **THIS IS A FACT ABOUT THE PRODUCT AND NOT A LABEL.** `BR-NOT-013`: no
    provider adapter exists on any channel, print included. A surface built on
    this block must not say a message REACHED anybody — the truest word this
    product has is QUEUED. The SENTENCE a clerk reads is the front end's, in
    its own catalogues; what travels here is the fact it renders.
    """
    return {"queued_only": True, "delivers": False, "br_ref": "BR-NOT-013"}


# ═══════════════════════════════════════════════════════════════════════════
# WHO WE ARE TELLING — the drawn read-only block
# ═══════════════════════════════════════════════════════════════════════════
def who_we_are_telling(connection: Any) -> dict[str, Any]:
    """Contact, email, phone and preferred language for one build's owner.

    ⚠ **IT READS THE SAME SOURCE THE QUEUE ITSELF READS, AND THAT IS THE WHOLE
    DESIGN.** `queue_document` resolves a recipient through
    `customers.selectors.delivery_recipients_for_account`; so does this. A
    screen that showed an address from one read while the queue wrote a row
    against another would let a clerk confirm an address no letter ever used —
    and nothing in the product would ever report the disagreement.

    ⚠ **THE DRAWING SHOWS THIS READ-ONLY AND SO DOES THE PAYLOAD.** There is no
    edit door here: an owner's contact details belong to their customer record,
    and a second place to change them is how two addresses come to disagree
    (hard rule 8's reasoning, one entity over).

    Three answers per channel, kept apart because they are three different
    facts: an address · *none on file*, which is ordinary · *not resolvable*,
    which is a fact about the platform and never about the person.
    """
    account_id = getattr(connection, "owner_account_id", None)
    if account_id is None:
        # `BR-MET-113` fills this at commit for any build whose owner is named,
        # so NULL here is a build with no named owner rather than a bug. It is
        # reported as an absence: a blank contact block would read as "we hold
        # nothing for them", which is a different and much worse claim.
        return {
            "account": None,
            "unavailable": [
                {
                    "field": "contact",
                    "code": REASON_NO_OWNER_ACCOUNT,
                    "br_ref": "BR-MET-113",
                    "detail": "This build names no owner account, so there is no customer "
                    "record to address. Nothing can be told about it and no message is "
                    "queued.",
                }
            ],
            **nothing_is_sent(),
        }

    read = seams.delivery_recipients(account_id, channels=("email", "sms", "pdf_print"))
    absences: list[dict[str, Any]] = []
    if read is None:
        absences.append(
            {
                "field": "contact",
                "code": "recipient_read_unpublished",
                "br_ref": "BR-TEN-017",
                "detail": "customers publishes no delivery_recipients_for_account, so "
                "nobody could look. An address is never inferred and never invented.",
            }
        )
        read = {}

    def _channel(name: str) -> dict[str, Any]:
        entry = dict(read.get(name) or {})
        return {
            "address": entry.get("address"),
            "unavailable_reason": entry.get("unavailable_reason")
            or (None if entry.get("address") else "recipient_not_resolvable"),
        }

    email = _channel("email")
    postal = _channel("pdf_print")
    name = ((read.get("email") or {}).get("snapshot") or {}).get("name") or (
        (postal_snap := (read.get("pdf_print") or {}).get("snapshot") or {})
        and postal_snap.get("name")
    )

    language = seams.account_language(account_id)
    if language is None:
        absences.append(
            {
                "field": "preferred_language",
                "code": "no_published_language_read",
                "br_ref": "BR-CUS-064",
                "detail": "The account carries a preferred language and customers publishes "
                "no read for it by id. The letters go in the utility's default language "
                "either way. Reported rather than rendered as English, which would be a "
                "guess about a customer printed on their own screen.",
            }
        )

    return {
        "account": {
            # ⚠ NOT the account id. B14 rule 31 — no database id is ever the
            # visible value of a field; the NUMBER is what a clerk reads back.
            "contact_name": name,
            "email": email,
            "phone": _channel("sms"),
            "postal": postal,
            "preferred_language": language,
        },
        "unavailable": absences,
        **nothing_is_sent(),
    }


# ═══════════════════════════════════════════════════════════════════════════
# CHOOSING A TEMPLATE — the drawn picker's rows
# ═══════════════════════════════════════════════════════════════════════════
def template_choices(*, search: str | None = None) -> dict[str, Any]:
    """The picker's rows for this step's three classes, drafts included.

    ⚠ **A DRAFT IS LISTED AND IS NOT PICKABLE, WHICH IS THE POINT.** p091, read
    as an image: *"The Spanish variant is a draft, and drafts are listed but
    cannot be picked. Hiding it would send a clerk looking for something they
    can see exists; showing it as choosable would queue a letter nobody has
    approved."* So the filtering is NOT done here and must not be done by the
    screen either — every row travels with `pickable` and, when false, the
    reason it cannot be chosen.

    ⚠ **`search` MATCHES THE NAME A HUMAN GAVE IT** — the search box's own
    helper line is *"Searches the name a human gave it."* — and never the class
    code, because B14 rule 31 keeps a database value off a screen and a clerk
    cannot be expected to search by one.

    ⚠ **NO ROW CARRIES A BODY.** The picker names the version that would be
    used; it does not render it. p091 says so itself, in the one dotted box on
    the page: *"The template picker names the version that would be used and
    does not render it. Nothing on this screen proves the merge fields resolve
    against a build that does not exist yet."*
    """
    _tenant_id()
    rows = seams.connection_templates(search=search)
    if rows is None:
        return {
            "rows": (),
            "unavailable": [
                {
                    "field": "templates",
                    "code": "template_read_unpublished",
                    "detail": "notifications publishes no connection_templates read.",
                }
            ],
        }
    return {"rows": tuple(rows), "unavailable": []}


# ═══════════════════════════════════════════════════════════════════════════
# THE MONEY GUARD — one function, and it is the one that changes
# ═══════════════════════════════════════════════════════════════════════════
def _amount_owed(connection: Any) -> tuple[Decimal | None, dict[str, Any] | None]:
    """What the books hold for this build, or why they hold nothing.

    ⚠ **`connections.quote_total` IS NOT AN ANSWER TO THIS QUESTION AND MUST
    NOT BE RETURNED AS ONE.** It is what step 6 recorded on the build;
    `commit_connection` reports on EVERY build that it was
    `quote_recorded_not_posted` and posts it nowhere (`OQ-379`). A letter that
    asks an owner to pay a figure no ledger holds is a promise the books cannot
    honour, and it is the kind of error that is only ever found by a customer.

    So this returns `(None, absence)` until the quote reaches the books, and
    the caller declines to queue the letter rather than sending a blank where
    the figure should be. **When the posting path lands, THIS function is what
    changes** — the class, the body and the caller all stay as they are.

    ⚠ **THE POSTING PATH LANDED ON 2026-09-28 (`BR-MET-1187`, `d7a40eea5`) AND
    THIS FUNCTION DID NOT CHANGE UNTIL 2026-10-02 (`DEF-MET-9216`).** The
    commit raises and ISSUES the quote bill in the same act, so a build with
    charges has a figure in the books from the moment it exists — and this
    went on answering *"not in the books"* for every build, so the PO's third
    letter (*"we have to send cost and ask them to pay it"*) was never queued,
    not at Create and not at approval. Found by the New Connection end-to-end
    walk: `CON-26-0129`, quote `BL-2610-000103` issued for **$135.00**, read
    *Sent on approval* on the Messages tab after the build was Activated.
    The figure is now the build record's own **Outstanding** — every bill the
    build raised (`connections.quote_invoice_id` and any added fee), less what
    payments has allocated against them (`connection_record._money`) — so the
    letter and the request's Charges tab cannot disagree. A build with NO bill
    keeps the refusal below: `quote_total` is still never used as the figure.
    """
    from apps.metering import connection_record

    outstanding = (connection_record._money(connection).get("outstanding") or {}).get("stored")
    if outstanding is not None:
        return Decimal(str(outstanding)), None
    recorded = getattr(connection, "quote_total", None)
    return None, {
        "field": "amount_due",
        "code": REASON_AMOUNT_NOT_IN_THE_BOOKS,
        "tracks": "OQ-379",
        "br_ref": "BR-BIL-020",
        "detail": (
            "The quote is recorded on the build and posted by nothing, which "
            "commit_connection reports on every build. Until it reaches the books there "
            "is no figure to put in a letter asking for payment, and "
            f"{'the recorded total is not used as a substitute' if recorded is not None else 'no total is even recorded'}."
        ),
    }


# ═══════════════════════════════════════════════════════════════════════════
# THE FIRING — three messages, on commit
# ═══════════════════════════════════════════════════════════════════════════
def queue_on_commit(
    actor: Any, connection: Any, choices: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Queue the PO's three messages for a build that has just been created.

    ⚠ **THIS IS THE STEP-7 HALF OF `commit_connection` AND IT IS CALLED BY IT,
    NOT INSTEAD OF IT.** It writes nothing but queue rows and one audit row per
    message, so it is safe inside the commit's transaction and safe after it.

    `choices` is step 7's slice of the commit payload — the clerk's ticks and
    their template picks — because `BR-MET-112` gives this wizard nowhere to
    store a half-finished step. Absent or empty, all three defaults stand,
    which is what the PO ruled and what the drawing draws.

    ⚠ **IT NEVER REPORTS A MESSAGE IT DID NOT QUEUE.** Every outcome carries
    the state, and where nothing was written it carries the reason and the
    question that would unblock it. A count of three over rows that do not
    exist is the defect `queue_document`'s own docstring was written against,
    and step 8's *"Three messages are queued to the owner"* must read THIS
    manifest rather than the drawing.
    """
    _tenant_id()
    picks = dict((choices or {}).get("templates") or {})
    asked = (choices or {}).get("send")
    account_id = getattr(connection, "owner_account_id", None)
    # The language is decided when a letter is actually queued — see
    # `fire_on_approval` and `send_now` — because nothing is queued here.

    outcomes: list[dict[str, Any]] = []
    for one in OCCASIONS:
        wanted = (
            one.send_by_default
            if asked is None
            else bool((asked or {}).get(one.code, one.send_by_default))
        )
        # ⚠ **`Q8` (PO 2026-10-02): A LETTER THE CLERK ASKED FOR WAITS FOR
        # APPROVAL; IT IS NOT QUEUED AT CREATE.** Until `CR-163-BRC10` this
        # called `_fire_one` here, and every call was refused because the
        # platform had no `connection` kind — so NOTHING was ever queued at
        # Create, and the count step 8 reads back is unchanged at zero. The
        # kind exists now; firing here would start writing the three letters
        # the moment a build is created, which is the opposite of the ruling.
        # The clerk's tick and template pick are still recorded on the outcome
        # so approval — or a *Send now* — can honour them.
        if not wanted:
            outcomes.append(
                {
                    "code": one.code,
                    "when": one.when,
                    "template_code": one.template_code,
                    "state": STATE_NOT_ASKED,
                    "reason": REASON_CLERK_UNTICKED,
                }
            )
            continue
        base = {"code": one.code, "when": one.when, "template_code": one.template_code}
        # The two refusals that are TRUE at Create are still reported as
        # themselves, in the order they always ran: a build with nobody to
        # address, and a letter asking for money the books do not hold
        # (`OQ-379`). Everything else waits for approval.
        if account_id is None:
            outcomes.append(
                {**base, "state": STATE_NOT_SENT, "reason": REASON_NO_OWNER_ACCOUNT}
            )
            continue
        if one.needs_money:
            amount, gap = _amount_owed(connection)
            if amount is None:
                outcomes.append(
                    {
                        **base,
                        "state": STATE_NOT_SENT,
                        "reason": REASON_AMOUNT_NOT_IN_THE_BOOKS,
                        "unavailable": [gap],
                    }
                )
                continue
        outcomes.append(
            {
                **base,
                "state": STATE_NOT_SENT,
                "reason": REASON_SENT_ON_APPROVAL,
                "override_template": (
                    str(picks[one.code]) if picks.get(one.code) else None
                ),
            }
        )

    queued = tuple(o for o in outcomes if o["state"] == STATE_QUEUED)
    return {
        "connection_id": str(getattr(connection, "id", "") or ""),
        "messages": tuple(outcomes),
        # ⚠ **THE NUMBER STEP 8 READS BACK, AND IT COUNTS ROWS RATHER THAN
        # INTENTIONS.** `DEF-MET-5428` is the same lesson one step over: the
        # review step promised nine work orders and the server raised none,
        # because the count was recomputed in the browser instead of read off
        # what the commit actually did.
        "queued_count": len(queued),
        "decided_count": len(outcomes),
        "not_at_creation": NOT_AT_CREATION,
        **nothing_is_sent(),
        "br_ref": BR_REF,
    }


def occasion_source_id(connection_id: Any, code: str) -> uuid.UUID:
    """**The `outbound_messages.source_id` one occasion of one build files under.**

    `outbound_messages` is unique on (source, channel, copy). Keyed on the
    build's own id, the *build confirmed* email and the *quote* email would be
    the same row and the second would silently become the first — the
    `service_request` kind's lesson, where each occasion keys on its own row.
    A build has no row per occasion, so the key is DERIVED: `uuid5` of the
    build and the occasion code, the same answer every time, which is what lets
    the record find the rows again and lets a retried send find its own copy.
    """
    return uuid.uuid5(uuid.UUID(str(connection_id)), f"connection-message:{code}")


def _letter_language(
    account_id: Any, *, template_code: str | None = None, category: str | None = None
) -> str | None:
    """**THE LANGUAGE CHOSEN ON STEP 1, FALLING BACK TO THE UTILITY'S** —
    `DEF-CUS-9195`, PO ruling 2026-10-02 (decision log, *"SEVEN PO ANSWERS IN
    ONE MESSAGE"*, item 2), verbatim: *"A with the English fallback. She asked
    for Spanish. Today her choice is saved but never used."*

    ⊕ **SUBSUMED 2026-10-29 (PO option B, *"Question: which language should
    messages be sent in? - B"*).** What this did for New Connection letters
    alone is now the rule for every message, applied once in
    `notifications.message_language.language_for`, which `queue_document`
    runs for each pin; this still chooses the language so the step-7 preview
    and the queue ask for the same one, and both answers agree.
    `test_cr199_messages_follow_the_customers_language.py` guards the rule.

    The owner's stated language is step 1's, stored on the master or owner's
    account since 2.463.0. It is used where the utility PUBLISHED wording of
    this letter in it — asked of the resolver `queue_document` pins with
    (`seams.template_published_in`), so the language chosen here and the
    wording pinned cannot disagree. Tried as stated, then by its base language
    (`es-MX` finds an `es` template — the same language, a judgment recorded in
    the decision log 2026-10-02). Otherwise the utility's default language:
    *"with the English fallback"*.

    `None` from the utility means it never set one; the resolver then takes
    the `default` wording, exactly as before."""
    utility = seams.tenant_default_language()
    if account_id is None or not template_code:
        return utility
    stated = (seams.account_language(account_id) or "").strip()
    if not stated:
        return utility
    tries = [stated]
    base = stated.split("-")[0]
    if base and base != stated:
        tries.append(base)
    for code in tries:
        if utility and code.lower() == utility.lower():
            return utility
        if seams.template_published_in(template_code, category=category, language=code):
            return code
    return utility


def _context(connection: Any, one: Occasion) -> tuple[dict[str, Any], dict[str, Any] | None]:
    context: dict[str, Any] = {
        "connection_no": getattr(connection, "connection_no", None),
        "target_activation": getattr(connection, "target_activation", None),
    }
    # ⊕ `DEF-MET-9232` — WHO the letter is to and WHERE. The three letters'
    # bodies greet the customer by name and quote the account number and the
    # service address, and this context carried none of them, so every queued
    # copy printed three named absences and the preview printed dashes. Read
    # through customers' own reads — the account holder's name and the service
    # address walked to the premises (hard rule 8) are the ones the build's
    # bill freezes, so the letter and the bill name the same person and place.
    # Every key is ALWAYS passed: a value nobody holds goes as None, which the
    # queue reads as *genuinely absent* rather than *forgotten*.
    account_id = getattr(connection, "owner_account_id", None)
    numbers = seams.master_account_numbers([account_id]) if account_id else {}
    addressee = (seams.account_addressee(account_id) if account_id else None) or {}
    service = addressee.get("service") if isinstance(addressee.get("service"), dict) else None
    street = (
        ", ".join(
            str(part).strip()
            for part in (
                service.get("line1"),
                service.get("city"),
                " ".join(
                    str(bit).strip()
                    for bit in (service.get("state"), service.get("postal_code"))
                    if bit and str(bit).strip()
                ),
            )
            if part and str(part).strip()
        )
        if service
        else ""
    )
    name = addressee.get("customer_name")
    context["customer_name"] = name.strip() or None if isinstance(name, str) else None
    context["account_no"] = (numbers.get(str(account_id)) or {}).get("account_no")
    context["service_address"] = street or None
    if one.needs_money:
        context["currency"] = seams.tenant_currency()
        amount, gap = _amount_owed(connection)
        if amount is None:
            return context, gap
        context["amount_due"] = str(amount)
    return context, None


def recipients_for(connection: Any) -> list[dict[str, Any]]:
    """Who a clerk may send a New Connection letter to — the PO's *"recipient
    (owner, co-applicant)"*. The owner is the build's owner ACCOUNT (the queue
    resolves its addresses itself); the co-applicant is the request's, contact
    only, offered on the channels they gave an address for and never on print —
    the product holds no postal address for a co-applicant (REQ-03.1)."""
    out: list[dict[str, Any]] = []
    if getattr(connection, "owner_account_id", None) is not None:
        out.append({"code": RECIPIENT_OWNER, "name": None, "channels": list(SENDABLE_CHANNELS)})
    co = seams.request_co_applicant(getattr(connection, "service_request_id", None))
    if co:
        channels = [
            channel
            for channel, address in (("email", co.get("email")), ("sms", co.get("phone")))
            if address
        ]
        if channels:
            out.append({"code": RECIPIENT_CO_APPLICANT, "name": co.get("name"), "channels": channels})
    return out


def deliveries_by_occasion(connection: Any) -> dict[str, list[dict[str, Any]] | None]:
    """Every queued row of every occasion of this build, read from the queue —
    `None` for an occasion when notifications could not be asked."""
    codes = [one.code for one in OCCASIONS] + [one["code"] for one in NOT_AT_CREATION]
    return {
        code: seams.deliveries_for_source(
            "connection", occasion_source_id(getattr(connection, "id"), code)
        )
        for code in codes
    }


def send_now(
    actor: Any,
    connection: Any,
    code: str,
    *,
    channel: str,
    recipient: str = RECIPIENT_OWNER,
    template_code: str | None = None,
) -> dict[str, Any]:
    """**Send one New Connection letter NOW** — `CR-163-BRC10` item 26.

    The PO's *"per row Send now … choose channel (email/print/SMS) and
    recipient (owner, co-applicant), Resend once sent — through notifications'
    existing send/queue path, audited"*. It is ONE call to
    `notifications.queue_document`, the only write path into
    `outbound_messages` (B1); nothing here writes that table.

    **A resend is the next COPY**, never an edit: copy 0 is the first send,
    and each further press queues copy 1, 2, … on that channel — the queue's
    own unique key (source, channel, copy) makes a double-click land on the
    same copy rather than queue two.

    ⚠ **QUEUED IS NOT SENT (`BR-NOT-013`).** No provider adapter exists, so the
    answer says `queued` and never claims anybody was told.

    Audited (`connection.message_sent_now`) — who pressed, which letter, which
    channel, which recipient kind, which copy. Not a money action; the module
    rule (`BR-MET-048`) is what this satisfies.
    """
    _tenant_id()
    one = occasion(code)
    if channel not in SENDABLE_CHANNELS:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="metering.connection.messageChannelUnknown",
            params={"value": str(channel)},
        )
    account_id = getattr(connection, "owner_account_id", None)
    if account_id is None:
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-MET-113",
            message_key="metering.connection.messageNoOwnerAccount",
            params={"connection_no": getattr(connection, "connection_no", "") or ""},
        )
    supplied: tuple[Any, ...] = ()
    if recipient == RECIPIENT_CO_APPLICANT:
        co = seams.request_co_applicant(getattr(connection, "service_request_id", None)) or {}
        address = co.get("email") if channel == "email" else co.get("phone") if channel == "sms" else None
        built = (
            seams.message_recipient(channel=channel, address=address, name=co.get("name"))
            if address
            else None
        )
        if built is None:
            raise errors.ValidationError(
                errors.VAL_UNKNOWN_LOOKUP,
                message_key="metering.connection.messageRecipientUnknown",
                params={"value": str(recipient)},
            )
        supplied = (built,)
    elif recipient != RECIPIENT_OWNER:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="metering.connection.messageRecipientUnknown",
            params={"value": str(recipient)},
        )

    context, gap = _context(connection, one)
    if gap is not None:
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref=BR_REF,
            message_key="metering.connection.messageAmountNotInBooks",
            params={"connection_no": getattr(connection, "connection_no", "") or ""},
        )
    source_id = occasion_source_id(connection.id, one.code)
    already = seams.deliveries_for_source("connection", source_id) or []
    copies = [int(row.get("copy_no") or 0) for row in already if row.get("channel") == channel]
    copy_no = (max(copies) + 1) if copies else 0
    try:
        written = seams.queue_document(
            source_type="connection",
            source_id=source_id,
            channels=(channel,),
            # The CLASS; `queue_document` pins the version at queue time
            # (`BR-BIL-026`) and refuses a row that names neither.
            # A clerk's template pick from Create (`fire_on_approval`) wins over
            # the occasion's default class.
            template=seams.template_pin(template_code or one.template_code),
            account_id=account_id,
            recipients=supplied,
            actor=actor,
            category=one.code,
            language=_letter_language(
                account_id,
                template_code=template_code or one.template_code,
                category=one.code,
            ),
            render_context=context,
            copy_no=copy_no,
        )
    except tuple(seams.queue_refusals()) as refused:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-NOT-013",
            message_key="metering.connection.messageQueueRefused",
            params={"detail": str(refused)},
        ) from refused
    if written is None:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="B1",
            message_key="metering.connection.messageQueueRefused",
            params={"detail": "notifications_queue_document_is_not_wired"},
        )
    rows = tuple(getattr(written, "rows", ()) or getattr(written, "messages", ()) or ())
    core_audit.write_row(
        action="connection.message_sent_now",
        entity_type="connection",
        entity_id=getattr(connection, "id", None),
        actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
        after={
            "occasion": one.code,
            "channel": channel,
            "recipient": recipient,
            "copy_no": copy_no,
            "rows": len(rows),
            "br_ref": BR_REF,
        },
    )
    return {
        "code": one.code,
        "channel": channel,
        "recipient": recipient,
        "copy_no": copy_no,
        "state": STATE_QUEUED if rows else STATE_NOT_SENT,
        "rows": len(rows),
        "problems": tuple(getattr(written, "problems", ()) or ()),
        **nothing_is_sent(),
    }


def preview(connection: Any, code: str) -> dict[str, Any]:
    """What one letter would say for THIS build — nothing written (item 26)."""
    _tenant_id()
    one = occasion(code)
    context, _gap = _context(connection, one)
    answer = seams.connection_message_preview(
        template_code=one.template_code,
        category=one.code,
        language=_letter_language(
            getattr(connection, "owner_account_id", None),
            template_code=one.template_code,
            category=one.code,
        ),
        context=context,
    )
    if answer is None:
        return {"available": False, "reason": "preview_unpublished", "code": one.code}
    return {**answer, "code": one.code}


def _fire_one(
    actor: Any,
    connection: Any,
    one: Occasion,
    *,
    account_id: Any,
    language: str | None,
    override_template: Any,
    asked: bool,
) -> dict[str, Any]:
    """One occasion's outcome at approval — through `send_now`, the ONE engine.

    ⚠ **REWRITTEN 2026-10-02 (`CR-163-BRC10`, merged with `CR-162-BRC10`).**
    This used to call `queue_document` itself; under `CR-163` every letter goes
    through `send_now`, so the per-occasion source id, the copy number, the
    template pin and the audit row cannot differ between a clerk's *Send now*
    and approval. A channel that already holds a copy for this occasion (a
    clerk's earlier *Send now*) is not queued again — a letter cannot be
    unsent, and approval is not a resend. `language` is decided by `send_now`
    (`_letter_language`, `DEF-CUS-9195` — step 1's language with the utility's
    as fallback) and is accepted here only so the caller's signature stands."""
    del language
    base = {"code": one.code, "when": one.when, "template_code": one.template_code}
    if not asked:
        return {**base, "state": STATE_NOT_ASKED, "reason": REASON_CLERK_UNTICKED}
    if account_id is None:
        return {**base, "state": STATE_NOT_SENT, "reason": REASON_NO_OWNER_ACCOUNT}
    # ⊕ `DEF-MET-9229` — a letter with no template is not queued. It was: on
    # `CON-26-0129` the contract went to the print queue at approval naming
    # `contract_service_agreement`, a class the utility had never published,
    # so the row could never render — while step 5 had told the clerk *Not
    # sent · No template*. A template published later is picked up by *Send
    # now*; approval does not invent one.
    if template_published(override_template or one.template_code) is False:
        return {**base, "state": STATE_NOT_SENT, "reason": REASON_NO_TEMPLATE}
    existing = seams.deliveries_for_source(
        "connection", occasion_source_id(connection.id, one.code)
    ) or []
    queued: list[str] = []
    refusal: Any = None
    for channel in one.channels:
        if any(row.get("channel") == channel for row in existing):
            queued.append(channel)
            continue
        try:
            sent = send_now(
                actor, connection, one.code, channel=channel, template_code=override_template
            )
        except (errors.ValidationError, errors.BizError) as refused:
            refusal = refused
            continue
        if sent.get("state") == STATE_QUEUED:
            queued.append(channel)
    if queued:
        return {**base, "state": STATE_QUEUED, "channels": tuple(queued)}
    key = getattr(refusal, "message_key", None)
    if key == "metering.connection.messageAmountNotInBooks":
        return {**base, "state": STATE_NOT_SENT, "reason": REASON_AMOUNT_NOT_IN_THE_BOOKS}
    return {
        **base,
        "state": STATE_NOT_SENT,
        "reason": REASON_PLATFORM_HAS_NO_WRITER if refusal is not None else "nothing_queued",
        "detail": str(getattr(refusal, "params", {}) or ""),
    }

# ═══════════════════════════════════════════════════════════════════════════
# CR-162-BRC10 · THE MESSAGES GO ON APPROVAL — the first activation fires them
# ═══════════════════════════════════════════════════════════════════════════
#: The moment the PO moved these three to (decision log 2026-10-02, Q8:
#: *"messages fire on approval (BR-MET-115)"*).
WHEN_ON_APPROVAL = "on_approval"

#: The `BR-MET-115` letter itself — *"your service is on"* — sent on every
#: activation, for the units and services that activation switched on.
CLASS_SERVICE_LIVE = "new_connect_service_live"


def _commit_outcomes(connection: Any) -> dict[str, dict[str, Any]]:
    """What the commit recorded for each of the three occasions, by code — read
    off the commit's stored answer (`connections.commit_result`, written by
    `_remember_the_commit`). Empty when the commit stored none (a press with no
    token), in which case every occasion is treated as asked — the PO's
    defaults."""
    stored = getattr(connection, "commit_result", None) or {}
    manifest = stored.get("manifest") if isinstance(stored, dict) else None
    block = (manifest or {}).get("messages") if isinstance(manifest, dict) else None
    rows = (block or {}).get("messages") if isinstance(block, dict) else None
    out: dict[str, dict[str, Any]] = {}
    for row in rows or ():
        if isinstance(row, dict) and row.get("code"):
            out[str(row["code"])] = row
    return out


def fire_on_approval(
    actor: Any, connection: Any, *, first: bool, activated: list[dict[str, Any]]
) -> dict[str, Any]:
    """**`CR-162-BRC10` item 3 — the queued messages go when the build is
    approved, inside the activation's transaction (`BR-MET-115`).**

    PO 2026-08-25 (`BR-MET-115`): *"sent it whnr utility user mar that job
    complete traigger it tat that time"*; PO 2026-10-02 (Q8): *"messages fire
    on approval"*. Two things go:

      * **On the FIRST activation only, step 5's three messages** — each one the
        clerk asked for at Create and that the commit did not already queue.
        `not_asked` at Create stays not asked; one already `queued` is never
        queued twice (a letter cannot be unsent).
      * **On EVERY activation, the service-live letter** for exactly the units
        and services that activation switched on.

    ⚠ **IT NEVER REPORTS A MESSAGE IT DID NOT QUEUE**, the rule this module was
    written under. ⚠ **AMENDED 2026-10-02 (`CR-163-BRC10`, at the merge):**
    this read *"the platform still has no `connection` source kind (`OQ-376`),
    so every outcome is `not_sent`"*. The kind exists now (`OQ-NOT-12521`,
    closed 2026-09-21), and step 5's three letters QUEUE here, through
    `_fire_one` → `send_now`. The service-live letter below still names no
    template class to pin, so the queue refuses it by name and it reports
    `not_sent` — not built by lane NC-B, reported to the coordinator. A refusal
    is raised before any row is written, so catching it inside the
    activation's transaction cannot poison it (law 14)."""
    _tenant_id()
    account_id = getattr(connection, "owner_account_id", None)
    # `DEF-CUS-9195` — the service-live letter too goes in step 1's language
    # where the utility published it, the utility's otherwise.
    language = _letter_language(
        account_id, template_code=CLASS_SERVICE_LIVE, category=CLASS_SERVICE_LIVE
    )
    outcomes: list[dict[str, Any]] = []
    if first:
        earlier = _commit_outcomes(connection)
        for one in OCCASIONS:
            before = earlier.get(one.code) or {}
            if before.get("state") == STATE_QUEUED:
                continue  # already queued at Create — never twice
            asked = before.get("state") != STATE_NOT_ASKED
            outcome = _fire_one(
                actor,
                connection,
                one,
                account_id=account_id,
                language=language,
                override_template=before.get("override_template"),
                asked=asked,
            )
            outcomes.append({**outcome, "when": WHEN_ON_APPROVAL})
    outcomes.append(_service_live(actor, connection, account_id, language, activated))
    queued = [o for o in outcomes if o.get("state") == STATE_QUEUED]
    return {
        "messages": tuple(outcomes),
        "queued_count": len(queued),
        "decided_count": len(outcomes),
        **nothing_is_sent(),
        "br_ref": "BR-MET-115",
    }


def _service_live(
    actor: Any,
    connection: Any,
    account_id: Any,
    language: str | None,
    activated: list[dict[str, Any]],
) -> dict[str, Any]:
    """The `BR-MET-115` letter for one activation — the same queue door and the
    same refusal handling as `_fire_one`, under the class the per-order send
    already names (`connections.dispatch_communication`)."""
    base = {
        "code": "service_live",
        "when": WHEN_ON_APPROVAL,
        "template_code": CLASS_SERVICE_LIVE,
    }
    if account_id is None:
        return {**base, "state": STATE_NOT_SENT, "reason": REASON_NO_OWNER_ACCOUNT}
    try:
        written = seams.queue_document(
            source_type="connection",
            source_id=getattr(connection, "id", None),
            channels=("in_app",),
            account_id=account_id,
            actor=actor,
            category=CLASS_SERVICE_LIVE,
            language=language,
            render_context={
                "connection_no": getattr(connection, "connection_no", None),
                "units": sorted({str(row.get("unit_label") or "") for row in activated}),
                "services": sorted({str(row.get("service") or "") for row in activated}),
            },
        )
    except tuple(seams.queue_refusals()) as refused:
        return {
            **base,
            "state": STATE_NOT_SENT,
            "reason": REASON_PLATFORM_HAS_NO_WRITER,
            "tracks": "OQ-376",
            "detail": str(refused),
        }
    if written is None or not tuple(getattr(written, "rows", ()) or ()):
        return {**base, "state": STATE_NOT_SENT, "reason": "notifications_queue_document_is_not_wired"}
    core_audit.write_row(
        action="connection.message_queued",
        entity_type="connection",
        entity_id=getattr(connection, "id", None),
        actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
        after={"occasion": "service_live", "channels": ["in_app"], "br_ref": "BR-MET-115"},
    )
    return {**base, "state": STATE_QUEUED, "channels": ("in_app",)}

# ── Lifecycle ─────────────────────────────────────────────
# packet: New Connect step 7 (PO ruling 2026-09-16 · OQ-MET-12360 closed · 05-prototype/02 Accounts Menu Blueprint.pdf p091 read as an image at scale 2 · apps/notifications/catalogs.py · apps/notifications/seed_templates.py · apps/notifications/connection_events.py · CLAUDE.md hard rule 1, rule 7, prime directive)
# generated: 2026-09-16 by story-coder (wave 1 lane D)
# checklist: A✔ B=deferred(the step-7 screen is a later wave's; this publishes its three reads) C✔ D=deferred(no HTTP surface — apps/metering/api.py is another lane's file this wave) E=deferred(as B) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest under PostgreSQL — RED PROVED FIRST, quoted in the lane report.
# exceptions: (1) NOTHING IS QUEUED TODAY — OQ-376, the platform has no `connection` source kind; every occasion records not_sent carrying the platform's own refusal. (2) MESSAGE THREE IS BLOCKED TWICE — OQ-379, the quote is recorded and posted by nothing, so the letter that must state a figure does not go. (3) NOTHING IS SENT on any channel — BR-NOT-013. (4) NO EVENT KEY — SET-12 has no row for a connection message and inventing one would switch a letter off under a name a System Admin never chose.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
