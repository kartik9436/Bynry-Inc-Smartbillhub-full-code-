# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-023 (the outbound delivery queue — one record per bill per
#           channel at issue; print/PDF v1, email dispatch deferred → W6)
#           Screens: S31 step 6 · S30
# Rules:    BR-BIL-016 (issue writes one delivery record per bill per channel;
#           mass sends are NEVER synchronous) · BR-BIL-036 (PRINT is the
#           primary channel and the floor — an account with no email address
#           still bills, still renders, still dispatches) · BR-BIL-026
#           (template + version pinned at issue; the queue row carries the pin
#           so a reprint renders what was sent) · BR-NOT-005 (every message is
#           a queue row first; only the dispatcher sends) · BR-NOT-006
#           (language rides the pin) · BR-TEN-043 (event time is named by the
#           caller, never read from a clock) · BR-NOT-017 (ONE HOME for every
#           notification rule — Settings → Notifications, CR-048 wave B) ·
#           BR-BIL-055 (a refusable bill is one named break, never a dead
#           batch) · BR-BIL-004 + PO 2026-08-12 / OQ-120 (the correction chain's
#           link lives on the REBILL: `invoices.corrects_invoice_id`) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 6 (idempotency) ·
#           rule 7 (audit)
# Tests:    06-backend/tests/test_us_bil_023_delivery_queue.py ·
#           06-backend/tests/test_cr048_b2_billing_fires_its_events.py
#           (CR-048 wave B — the event this seam fires, and what it costs)
# Impacts:  apps/billing/issue.issue_invoice (calls this inside the issue
#           transaction) · apps/notifications/services.queue_document (the
#           owner of the queue, resolved BY NAME — billing never imports it;
#           its `event_key` is what CR-048 wave B feeds) ·
#           apps/notifications/rule_catalog.EVENT_KEYS (the vocabulary
#           `EVENT_BILL_READY` / `EVENT_BILL_CORRECTED` are members of)
# ───────────────────────────────────────────────────────
"""billing → notifications SEAM: the delivery rows a bill leaves at issue.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this runs INSIDE `issue.issue_invoice`'s
transaction, so its refusal decides whether an immutable financial record is
created at all (CLAUDE.md rule 4), and the arguments it hands the queue owner —
`source_type`, `source_id`, `channel`, `copy_no` — are the components of a hard
rule 6 idempotency key. AI-authored 2026-08-11 under the PO ruling of
2026-08-09; row in 12-governance/09-human-review-ledger.md.

MARKER ADDED 2026-08-11 by the gate lane, and what that does and does not mean.
This file already HELD a review-ledger row naming an unreviewed decision — *"a
bill that cannot be queued does not issue"*, which BR-BIL-016 does not settle and
which the lane chose — while carrying neither marker in its docstring, so the
ledger row was the only place the claim existed and no gate could read it. The
marker was added after reading the code against CLAUDE.md's 🔒 list, not on the
strength of a lane report. It does NOT put this path on `10-scripts/gates/
human_owned.txt`: editing that file is a process event (its own header says so),
so the glob is REPORTED for the daily PO batch and was not self-granted. Until
that line lands, G7 still does not look at this file — a marker no gate reads is
hard-won law 1, and saying so here is the point of saying it at all.

BR-BIL-016, verbatim: *"Delivery is QUEUE-based: issue writes one delivery
record per bill per channel … mass sends are never synchronous."* This module
is billing's half of that sentence. The queue itself — the table, the write
path, the idempotency key, the print floor — belongs to notifications
(`outbound_messages`, B2 r12 #16), and billing gets at it exactly the way B1
requires: through the owning module's published service, resolved BY NAME at
call time.

╔══════════════════════════════════════════════════════════════════════════╗
║  QUEUEING IS NOT SENDING. NOTHING IN THIS PATH CONTACTS A PROVIDER.      ║
╚══════════════════════════════════════════════════════════════════════════╝

R2 builds the QUEUE; **R4 is where email is switched on** (B12 release table:
bills, receipts and notices actually going out through providers). Until then
rows resting `queued` are the correct, finished outcome of a bill run — not a
backlog of failures. `DELIVERY_UNAVAILABLE` below carries that fact on every
result so no caller can read "queued 1,124 bills" as "sent 1,124 bills".

WHY A SEAM AND NOT AN IMPORT
----------------------------
Billing must not touch notifications' ORM (B1), and notifications must not
import billing (it is the callee). The seam idiom this repo already uses —
`apps/billing/rating_seam.py` for the money math, `apps/metering/seams.py` for
everything metering needs from its neighbours, `apps/billing/issue.py` for the
ledger's two GL reads — resolves the owner's callable with `getattr` at CALL
time. Nothing binds the modules at import, the boundary is greppable from both
sides by name (`DELIVERY_MODULE` / `QUEUE_WRITE`), and the day an owner changes
its internals nothing here needs re-wiring.

It also adapts BOTH directions, for the reason DEF-047 taught this repo: the
callee's REFUSAL type is as much a part of the contract as its result.
`QueueWriteRefused` is notifications' vocabulary; `issue_run` catches
`BillingRuleError` and nothing else, so an untranslated refusal would kill a
run of five hundred bills over one bad row — exactly what BR-BIL-055 forbids.
Translated here, one unqueueable bill is one named break and the other 499 go
out.

THE EVENT — ADDED 2026-08-29, CR-048 WAVE B (TASKS B1 + B2)
-----------------------------------------------------------
⚠ **UNTIL THIS DATE THIS SEAM PASSED A SOURCE TYPE AND NO EVENT, AND THAT IS
WHY SETTINGS → NOTIFICATIONS DID NOTHING.** Wave A gave `queue_document` an
optional `event_key`: pass one and the utility's SET-12 rule is read and
intersected with what the caller asked for, so a channel a utility switched off
is not queued. Every writer in the product still passed `source_type="invoice"`
and no event, so `event_key` was `None` everywhere and *"Bill ready — email"*
off changed nothing at all — the CR's headline finding, in one seam.

This seam now names the event on every bill. Which one it is is decided by
`event_for_bill` from `invoices.corrects_invoice_id` — the correction chain's
own link, which billing already holds — and NOT from a new parameter, because
`issue.issue_invoice` serves the cycle run, the fee bill and the correction
rebill alike and a flag threaded through all three is a second statement of a
fact the row already makes. The full argument is in `event_for_bill`.

**WHAT IT COSTS A RUN, MEASURED:** two SELECTs per bill and no write
(`rule_service.channel_switches`, which wave A added for exactly this caller
because the SCREEN's read issues up to forty-five `get_or_create` WRITES over
fifteen events and must never run inside an issue transaction). Asserted in
`tests/test_cr048_b2_billing_fires_its_events.py`, not claimed here.

**AND IT STILL CANNOT KILL A RUN.** `channel_decision` refuses an event key the
catalogue does not define — with `QueueWriteRefused`, notifications' own
vocabulary — and the translation below turns that into one named `BillingRuleError`
for one bill (BR-BIL-055). A rule that leaves NO channel is not a refusal at all:
the print floor survives every switch on that screen (BR-BIL-036), so a bill is
never the empty case.

WHICH CHANNELS A BILL GOES OUT BY — AND WHAT IS NOT KNOWN TODAY
---------------------------------------------------------------
**Print is the floor and is never in doubt** (BR-BIL-036, the PO's closure of
OQ-091): every bill is printed, whatever else it is also sent by, and a
paperless customer still receives the document. The floor is applied inside
notifications rather than here, so no writer can forget it.

**THE ELECTION IS READABLE AS OF 2026-08-31 (CR-052 W4 task 14), AND THE
PARAGRAPH THAT STOOD HERE IS REPLACED RATHER THAN DELETED (hard-won law 1).**
It read: *"The ELECTION — which extra channels this account chose — cannot be
read on this deployment. It lives on `accounts.paperless` and
`accounts.sms_reminders`, both marked PROPOSED-SCHEMA in the customers field map
and both unbuilt … So this seam asks by name (`ELECTION_READ`) and, while
nothing answers, names NO extra channel and REPORTS the gap on the result."*

**Both columns exist** (migration `customers 0034`) and
`customers.selectors.delivery_channel_election_for_account` is the read this
module had named by string since W3 — one of the longest-standing cases of
hard-won law 2 in the repo, an engine that wrote and a screen that read with no
question between them. **Nothing in this file changed to make it work**, which
is exactly what the old paragraph promised: *"the day the preference lands, this
seam produces it with no edit here."*

**WHAT THE RUN NOW PRODUCES, MEASURED:** an account that elected nothing queues
**one** row, `pdf_print`. Paperless on queues **two** — `pdf_print` AND `email`
— and the print row is byte-identical to the one it had before. Both switches on
queues **three**. Nothing ever queues zero.

`None` still means *nobody could ask* and is still kept apart from `()`, *this
customer elected nothing* — the second is now the ordinary answer for every
account in the product, and the first survives for the deployment where
customers is unmigrated or the account is not this tenant's. Writing an email
row for every bill would assert an election no column records; writing none for
an account that has NOT elected is that account's own answer.

⚠ **AN ELECTED SMS ROW IS QUEUED WITHOUT AN ADDRESS, AND THAT IS `DEF-2700`.**
Consent is recorded; the NUMBER is not. `contacts.phone` is one free-text field
and nothing declares it a mobile, so texting it would be an inference that costs
money and reaches nobody. The row is written carrying its reason —
`outbound_messages`' own check constraint makes *address or reason* structural —
and the print row beside it is unaffected.

WHERE THIS RUNS: INSIDE THE ISSUE TRANSACTION
---------------------------------------------
`issue.issue_invoice` calls this after the status moves and before the
transaction closes, so a bill and its delivery rows are one atomic fact. The
alternative — queue afterwards, outside — produces the state nothing can
repair: an issued, immutable bill with no delivery record and no code path left
that would ever write one. Retrying is safe either way because the queue write
is idempotent on `(tenant, source_type, source_id, channel, copy_no)`; the
transaction just means there is nothing to retry.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from importlib import import_module
from inspect import signature
from typing import Any, Iterator

from django.db import transaction

from apps.billing.exceptions import BillingRuleError

#: The notifications write path, named once so the contract is greppable from
#: BOTH sides of the boundary — the same discipline as `issue.GL_REVENUE_READ`.
DELIVERY_MODULE = "notifications"
QUEUE_WRITE = "queue_document"

#: The keyword `queue_document` takes the SET-12 event on (CR-048 wave A),
#: named here for the same reason `QUEUE_WRITE` is: the contract is greppable
#: from both sides of the boundary by one string.
EVENT_PARAMETER = "event_key"

#: The READ half, named the same way and for the same reason (US-BIL-024's
#: `GET /invoices/{id}/deliveries`, served on the invoice detail):
#:
#:     apps.notifications.selectors.deliveries_for_source(source_type, source_id)
#:         -> list[dict]
#:
#: Published 2026-08-16. Until then this seam could WRITE a delivery row for
#: every bill and nothing could ask where one bill went — so `GET /invoices/{id}`
#: answered `deliveries: null` on every bill and S30's delivery panel, which has
#: been built since the detail screen landed, rendered its absence branch
#: forever. An engine that writes and a screen that reads, with no question
#: between them (hard-won law 2).
DELIVERY_READ = "deliveries_for_source"

#: The second READ half — `DEF-2496` / BR-NOT-025:
#:
#:     apps.notifications.selectors.template_pin_count(template_id, version) -> int
#:
#: Published 2026-08-30. ⚠ **IT EXISTS BECAUSE `outbound_messages.template_id`
#: IS POLYMORPHIC AND NOTHING SAID SO.** Measured on the development database:
#: of 181 rows, **94 carry a BILL template's id** — every one a `pdf_print` row
#: whose `source_type` is `invoice`. So a bill layout version can be pinned by a
#: printed bill as well as by an issued invoice, and `templates_service.
#: pin_count` counted `invoices` alone: a version pinned by a print row and by
#: no invoice read as UNPINNED and its delete was allowed by the service that
#: exists to refuse it. BR-NOT-025 says *any sent document* and a printed bill
#: is one.
#:
#: **This is the readable half only.** When notifications publishes nothing the
#: count is UNASKABLE, not zero — see `template_print_pin_count` for what that
#: distinction costs and why the database, not this seam, is the guarantee.
TEMPLATE_PIN_READ = "template_pin_count"

#: The customers read that would say which channels an account elected.
#: Contract, for the lane that publishes it:
#:
#:     apps.customers.selectors.delivery_channel_election_for_account(account_id)
#:         -> tuple[str, ...] | None
#:
#: The EXTRA channels beyond the print floor (BR-BIL-036) — `("email",)` for a
#: paperless account, `()` for one that elected nothing, and **None when the
#: question cannot be answered**. None and `()` are different facts and this
#: module keeps them apart: one is "this customer wants paper only", the other
#: is "nobody can tell", and only the first is a delivery decision.
ELECTION_MODULE = "customers"
ELECTION_READ = "delivery_channel_election_for_account"

#: The queue's own vocabulary for a bill, repeated here rather than imported:
#: billing must not import notifications (B1), and these two strings are the
#: contract, not an implementation detail. `source_type` is validated by the
#: owner against its own `SOURCE_TYPES`, so a typo fails loudly at the call.
SOURCE_INVOICE = "invoice"

# ══════════════════════════════════════════════════════════════════════════
# CR-048 WAVE B TASK B11 — THE GOODWILL-CREDIT LETTER
# ══════════════════════════════════════════════════════════════════════════
# `catalogs.LISTINGS["email_credit_issued"]` has read *"Not in use yet — no
# wording has been written for it."* since 2026-08-16 — and the wording HAS been
# written since 2026-08-17 (`AUTHORED_CATALOGS`, PO ruling *"please define it
# for this product"*), so what was actually missing was a sender. This is it:
# `corrections.execute_credit_only` — the Class-C goodwill credit the PO ruled
# on 2026-08-12, raised on the ACCOUNT and leaving the bill untouched.
#: The SET-12 event, and the source kind, and the wording. Repeated here as
#: STRINGS for `SOURCE_INVOICE`'s stated reason (B1: billing must not import
#: notifications' internals and these ARE the contract); a typo is a loud named
#: break because `channel_decision` refuses an unknown event key.
EVENT_CREDIT_ISSUED = "credit_issued"

#: ⚠ **`payment`, NOT `invoice`.** `catalogs.LISTINGS["email_credit_issued"]`
#: files this class CAT_PAYMENTS, and the source kind is chosen from what the
#: DOCUMENT is (`rule_catalog.EVENTS` states that rule once). Two consequences
#: worth naming: `invoice` is in `PIN_REQUIRED_SOURCES` and would demand a
#: frozen template id and version for a document with no versioned template
#: table; and a credit note is not a bill — pointing the queue's `source_id` at
#: a credit note while calling it an `invoice` would make every row that joins
#: on the pair wrong.
SOURCE_PAYMENT = "payment"
CHANNEL_EMAIL = "email"

#: The wording. ⚠ NOT `credit_note`, which is the LEDGER's source type for the
#: posting; a template code is not a document type (DEF-2511).
CREDIT_TEMPLATE_CODE = "email_credit_issued"

CREDIT_NOTICE_QUEUED = "credit_notice_queued"
CREDIT_NOTICE_UNAVAILABLE = "credit_notice_queue_unavailable"
CREDIT_NOTICE_ERROR = "credit_notice_queue_error"

#: `DEF-BIL-4448` — one figure on the covering email could not be read. The bill
#: is unaffected and the letter still goes, with that line as a named absence.
CORRECTED_BILL_FIGURE_UNREADABLE = "corrected_bill_original_total_unreadable"

#: THE TWO SET-12 EVENTS A BILL CAN BE (CR-048 wave B, tasks B1 + B2).
#:
#: Repeated here rather than imported, for exactly the reason `SOURCE_INVOICE`
#: is: billing must not import notifications' internals (B1) and these strings
#: ARE the contract. They are not free strings either — `channel_decision`
#: refuses an event key `rule_catalog.EVENT_KEYS` does not define, naming the
#: whole vocabulary, so a typo here is one loud named break per bill and never
#: a message silently routed to a rule that does not exist.
#:
#: WHY BILLING NAMES THE EVENT AT ALL, in one sentence: `source_type` is
#: one-to-MANY onto events. `invoice` is bill_ready OR bill_corrected — two
#: rows on SET-12 with two sets of switches — so notifications cannot derive it
#: and asking it to guess would apply one utility's answer to a question it was
#: never asked. See `event_for_bill` for which fact decides it.
EVENT_BILL_READY = "bill_ready"
EVENT_BILL_CORRECTED = "bill_corrected"

#: What the delivery path does NOT do, carried on every result — the same
#: discipline as `issue.ISSUE_UNAVAILABLE` and `release.RELEASE_HANDOFFS`: a
#: caller must not have to infer an absence and a reviewer must not have to
#: take a docstring's word for it (hard-won law 1).
DELIVERY_UNAVAILABLE: tuple[dict[str, Any], ...] = (
    {
        "code": "nothing_was_dispatched",
        "br_ref": "BR-BIL-016",
        "detail": "the rows rest `queued`. There is no dispatcher (US-NOT-002), no "
        "provider adapter (US-NOT-003) and no send of any kind in R2 — email ACTIVATION "
        "is R4 on the B12 release table. A queued row is the finished state of a bill run "
        "today, not a failed send.",
    },
    {
        "code": "document_not_rendered",
        "br_ref": "BR-BIL-033",
        "detail": "the row carries the template PIN, and nothing renders from it: "
        "`apps/billing/documents.py` is one line. BR-BIL-033 wants the render BEFORE "
        "issue and a failed render to refuse the issue; that remains unsatisfiable and is "
        "the issue lane's standing report, not something queueing closes.",
    },
    {
        "code": "recipient_not_resolved_by_billing",
        "br_ref": "BR-TEN-017",
        "detail": "billing names no recipient. The address is customers' to answer and "
        "notifications asks it by name; billing has one reviewed FK into customers (the "
        "account row) and `contacts` is not on it. The queue row records what could not "
        "be resolved rather than carrying an address billing had no right to read.",
    },
)


@dataclass(frozen=True)
class BillDelivery:
    """What one bill left in the delivery queue — and what it could not.

    `queued` counts the rows this call CREATED; `already_queued` the ones that
    were there (a replay, a double-clicked release, a resumed batch). The two
    are reported apart because "1,124 bills queued" and "1,124 bills were
    already queued" are different mornings.

    `problems` is the notifications result's own list plus billing's, unaltered
    — codes a screen can group on, never prose it would have to parse.
    """

    invoice_id: str
    channels: tuple[str, ...] = ()
    queued: tuple[str, ...] = ()
    already_queued: tuple[str, ...] = ()
    problems: tuple[dict[str, Any], ...] = ()
    unavailable: tuple[dict[str, Any], ...] = field(default=DELIVERY_UNAVAILABLE)
    #: Stated as a VALUE so a caller can assert it rather than trust prose.
    dispatched: bool = False
    #: WHICH SET-12 event this bill was queued as (CR-048 wave B). Carried for
    #: the same reason `channels` is: a run report that says "no email was
    #: queued" is only readable if it can also say which rule was consulted, and
    #: a reviewer asking *"did the corrected-bill row decide this, or the
    #: bill-ready row?"* must be able to assert the answer rather than infer it.
    event_key: str | None = None


def _resolve(module: str, attribute: str, kind: str) -> Any:
    """The owning module's callable, or None while it has not published one.

    getattr at CALL time — the idiom `gather.py`, `issue.py`, `release.py` and
    `apps/metering/seams.py` all use.
    """
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - defensive
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


def queue_credit_note(
    *, credit_note: Any, account_id: Any, amount: str, on_date: Any, reason: str, actor: Any = None
) -> tuple[dict[str, Any], ...]:
    """ONE email telling a customer a credit was raised on their account.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  THE IDEMPOTENCY TUPLE IS (tenant, "payment", CREDIT-NOTE id, email, ║
    ║  0)                                                                  ║
    ╚══════════════════════════════════════════════════════════════════════╝
    **The credit note's own id.** The obvious alternatives both lose a message:
    the ACCOUNT collides with every other credit that account is ever given,
    and the INVOICE collides with the SECOND credit raised against one bill —
    which a bulk correction case can do, because `execute_credit_only` writes a
    new note every time and never touches the one before it (hard rule 4). A
    credit note is one row per concession, so two concessions are two letters
    and a replayed correction writes nothing (rule 6).

    ⚠ **A SAVEPOINT, AND IT IS LOAD-BEARING (CLAUDE.md law 14).**
    `execute_credit_only` is `@transaction.atomic` and this runs inside it. On
    PostgreSQL a statement that errors inside a transaction ABORTS the whole
    transaction: a bare `try` would catch the exception and leave the credit
    note's own INSERT and its balanced journal pair doomed at COMMIT with
    *"current transaction is aborted"*. SQLite has no such state, so the version
    without the nested `atomic()` passes the entire suite and loses a
    customer's goodwill credit the first time the queue refuses a row in
    production. **Do not "simplify" it away.**

    Raises nothing. The letter's outcome is reported; the money is not risked.
    """
    write = _resolve(DELIVERY_MODULE, QUEUE_WRITE, "services")
    if write is None:  # pragma: no cover - notifications ships in this repo
        return (
            {
                "code": CREDIT_NOTICE_UNAVAILABLE,
                "br_ref": "BR-BIL-014",
                "detail": f"apps.{DELIVERY_MODULE}.services.{QUEUE_WRITE} is not published, "
                "so the customer has NOT been told a credit was raised. The credit and its "
                "journal entry stand.",
            },
        )
    try:
        with transaction.atomic():
            written = write(
                source_type=SOURCE_PAYMENT,
                source_id=credit_note.pk,
                channels=(CHANNEL_EMAIL,),
                template=_Pin(CREDIT_TEMPLATE_CODE),
                account_id=account_id,
                actor=actor,
                **{EVENT_PARAMETER: EVENT_CREDIT_ISSUED},
                on_date=on_date,
                # The four tokens `catalogs.CATALOGS["email_credit_issued"]`
                # whitelists. `{reason}` is A19 r8's ratified content for this
                # class — *the clerk's memo as the customer-visible reason* —
                # printed under a plain label and never reworded here.
                # `{balance}` is NOT passed: the account's balance after a
                # concession is `accounts.balance`, a CACHED column BR-CUS-015
                # says is never the balance, and billing may not read customers'
                # AR position from inside a correction. A named absence is
                # better on a customer's letter than a stale figure.
                render_context={
                    "amount": amount,
                    "date": on_date,
                    "reason": reason,
                },
            )
    except Exception as failure:  # noqa: BLE001 — the one boundary where broad is right
        return (
            {
                "code": CREDIT_NOTICE_ERROR,
                "br_ref": "BR-BIL-014",
                "detail": f"the credit letter could not be queued: {failure} The credit "
                "note and its balanced entry stand — a failed notification must never "
                "fail the money it describes.",
            },
        )
    messages = tuple(getattr(written, "messages", ()) or ())
    problems = tuple(getattr(written, "problems", ()) or ())
    if not messages:
        # The utility's rule left no channel — a choice, not a fault. The reason
        # is already on `problems`, which IS the outcome.
        return problems
    return (
        {
            "code": CREDIT_NOTICE_QUEUED,
            "br_ref": "BR-BIL-014",
            "message_id": str(getattr(messages[0], "id", "")) or None,
            "created": bool(getattr(messages[0], "created", False)),
            "event_key": EVENT_CREDIT_ISSUED,
            "detail": "the credit letter (template 'email_credit_issued') is on the "
            "platform outbound queue for this credit note. Queueing is not sending: "
            "nothing dispatches in this release (BR-NOT-013).",
        },
        *problems,
    )


class _Pin:
    """The template pin, structurally — `notification_templates` is EP-NOT-02
    and unbuilt, so a code is all there is to freeze."""

    def __init__(self, code: str) -> None:
        self.code = code
        self.template_id = None
        self.version = None
        self.language = None


def event_for_bill(invoice: Any) -> str:
    """Which SET-12 event this bill IS — read off the bill, never off a flag.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  ONE ISSUE PATH SERVES BOTH, SO THE BILL ITSELF HAS TO SAY WHICH.    ║
    ╚══════════════════════════════════════════════════════════════════════╝

    `issue.issue_invoice` is the ONLY place a bill is queued, and it is reached
    by three callers that all mean different things: `issue_run` for a cycle,
    `fee_bill` for a one-off charge, and `corrections.execute_restatement` for
    the REBILL leg of a correction. So the event cannot come from the caller —
    there is no caller-shaped seam to hang it on — and it must not come from a
    parameter someone can pass wrongly.

    **IT COMES FROM `invoices.corrects_invoice_id`, WHICH BILLING ALREADY
    HOLDS.** That column is the correction chain's link, stamped on the
    REPLACEMENT by `corrections.execute_restatement` while it is still a draft
    and pointing back at the bill it replaces (PO ruling 2026-08-12, closing
    OQ-120: *"Nod to add the link on the new bill"*). It is NULL on every bill
    that replaces nothing, which is nearly all of them, and it is frozen at
    issue by the `0017` immutability trigger along with the money — so a bill
    cannot change which event it was after the fact.

    A NEW FLAG WOULD HAVE BEEN WRONG, and the reason is worth writing down
    because it is the one judgment in CR-048 task B2. A boolean threaded down
    from `issue_invoice` would be a second statement of a fact the row already
    makes, free to disagree with it: a correction path that forgot to set it
    would email a customer under the *Bill ready* rule — which the utility may
    have switched off for a reason that has nothing to do with corrections —
    and nothing anywhere would look wrong. One fact, one carrier.

    Reads the `_id` attribute rather than the relation, so no query is issued:
    this is called once per bill inside the issue transaction and the FK is
    already on the locked row.
    """
    return (
        EVENT_BILL_CORRECTED
        if getattr(invoice, "corrects_invoice_id", None) is not None
        else EVENT_BILL_READY
    )


#: The one-time bill's Send (contract §5, build plan A7) — the three delivery
#: choices a clerk makes for ONE bill, as the EXTRA channels each asks for.
#: ⚠ **PAPER IS NOT IN ANY OF THEM AND CANNOT BE TAKEN OUT OF ANY OF THEM.**
#: BR-BIL-036 makes print the floor, applied by the queue owner
#: (`notifications.services.channel_decision`, *"THEN the floor … so a rule
#: can never take paper off a bill"*), so `email` queues email AND paper,
#: exactly as `email_and_paper` does. The difference between the two is the
#: clerk's stated intent, not the queue — said on the send answer's
#: `unavailable` list rather than hidden (`one_time_send.PAPER_IS_THE_FLOOR`).
DELIVERY_CHOICES: dict[str, tuple[str, ...]] = {
    "email": (CHANNEL_EMAIL,),
    "paper": (),
    "email_and_paper": (CHANNEL_EMAIL,),
}

_CLERK_CHANNELS: ContextVar[tuple[str, ...] | None] = ContextVar(
    "billing_clerk_delivery_channels", default=None
)


@contextmanager
def clerk_delivery_choice(delivery: str) -> Iterator[None]:
    """For the duration of ONE send, queue the channels the clerk chose.

    `issue.issue_invoice` calls `queue_bill_delivery` inside its own
    transaction and derives the channels from the ACCOUNT's standing election
    (`elected_channels`). A one-time bill's Send asks the clerk instead —
    *Email*, *Paper* or *Both* (design §1 step 3, US-BIL-033 TC-9) — so this
    scopes that answer to the send call rather than threading a parameter
    through the 🔒 issue path, which three other callers share and which none
    of them should be able to pass by accident.

    A context variable and not a module global: two sends in two threads each
    see their own choice, and the choice ends with the `with` block even when
    the issue pass raises. An unknown choice raises before anything is issued.
    """
    if delivery not in DELIVERY_CHOICES:
        raise BillingRuleError(
            f"unknown delivery choice {delivery!r}; a one-time bill is sent by "
            f"{tuple(DELIVERY_CHOICES)} (BR-BIL-016)."
        )
    token = _CLERK_CHANNELS.set(DELIVERY_CHOICES[delivery])
    try:
        yield
    finally:
        _CLERK_CHANNELS.reset(token)


#: `DEF-BIL-10535` — the clerk's three answers on Fix-a-bill's approval step,
#: in the screen's order (*Email · Paper · Both*). The same keys as
#: `DELIVERY_CHOICES`, so one door (`clerk_delivery_choice`) serves both the
#: one-time bill and the corrected bill.
CORRECTION_DELIVERY_CHOICES: tuple[str, ...] = ("email", "paper", "email_and_paper")
#: The answers that need an email address on file.
DELIVERY_CHOICES_WITH_EMAIL = frozenset({"email", "email_and_paper"})


def original_delivery_choice(invoice_ids: Any) -> str | None:
    """What the ORIGINAL bill(s) went on, as the clerk's answer — or None.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  DEF-BIL-10535 · PO 2026-10-22 Q1: *"The clerk chooses Email, Paper    ║
    ║  or Both on the approval step, with the original bill's channels      ║
    ║  ticked to start."*                                                   ║
    ╚══════════════════════════════════════════════════════════════════════╝

    An `email` row on any of the bills → `email_and_paper` (*Both*: print is on
    every bill, so that is what went); otherwise → `paper`. A one-customer
    case over several months takes the union of its bills (decision log
    2026-10-22, *Building the corrected-bill rulings*, point 1). Worked:
    Daniel Thomas's original went by post only → `paper`.

    `None` when the queue cannot be asked (`deliveries_for_bill` answers None),
    which the caller must not read as *paper*: the step then opens on nothing
    and the server falls back to the account's own channels.
    """
    any_answer = False
    for invoice_id in invoice_ids or ():
        rows = deliveries_for_bill(invoice_id)
        if rows is None:
            continue
        any_answer = True
        if any(_row_channel(row) == CHANNEL_EMAIL for row in rows):
            return "email_and_paper"
    return "paper" if any_answer else None


def _row_channel(row: Any) -> str | None:
    if isinstance(row, dict):
        return row.get("channel")
    return getattr(row, "channel", None)


def email_on_file(account_id: Any) -> bool | None:
    """Is there an email this account's mail would go to? None = cannot tell.

    `DEF-BIL-10535`. The address the queue itself addresses an email by
    (`customers.selectors.delivery_recipients_for_account`, primary contact
    first), so the grey *Email* option on the screen and the address on the
    queue row cannot disagree (decision log 2026-10-22, point 3).

    ⚠ **ITS OWN SAVEPOINT (hard-won law 14).** The approval request may run
    inside a transaction; a refused read must not abort it on PostgreSQL.
    """
    read = _resolve(ELECTION_MODULE, "delivery_recipients_for_account", "selectors")
    if read is None or account_id is None:
        return None
    try:
        with transaction.atomic():
            answer = read(account_id, (CHANNEL_EMAIL,))
    except Exception:  # noqa: BLE001 — "cannot tell" is the answer, not a crash
        return None
    found = (answer or {}).get(CHANNEL_EMAIL) or {}
    return bool(found.get("address"))


def elected_channels(account_id: Any) -> tuple[tuple[str, ...], dict[str, Any] | None]:
    """The EXTRA channels this account chose, and the reason if none is knowable.

    `((), None)` is *this customer elected nothing* — a fact about the PERSON,
    and the ordinary answer for every account in the product, because nobody has
    been asked. `((), problem)` is *nobody could tell*, a fact about the
    PLATFORM. The two must never render the same, which is the whole of what
    this function adds over calling the read directly.

    ⚠ **THE SECOND CASE IS NO LONGER THE NORMAL ONE.** Until 2026-08-31 it was
    the answer for every bill this product had ever issued, because
    `accounts.paperless` and `accounts.sms_reminders` were PROPOSED-SCHEMA. They
    are built (`customers 0034`, CR-052 task 14) and the read is published, so
    this branch now fires only where customers is genuinely unreachable — an
    unmigrated deployment, or an account that is not this tenant's.

    Print is unaffected in every case: it is the floor, applied by the queue
    owner, and no election can remove it (BR-BIL-036). A paperless customer
    still receives the document.
    """
    chosen = _CLERK_CHANNELS.get()
    if chosen is not None:
        # The one-time bill's Send carries the clerk's own choice for THIS
        # bill (build plan A7) — see `clerk_delivery_choice`. Print is still
        # the floor and is added by the queue owner, never here.
        return chosen, None
    read = _resolve(ELECTION_MODULE, ELECTION_READ, "selectors")
    elected = read(account_id) if read is not None and account_id is not None else None
    if elected is None:
        return (), {
            "code": "delivery_election_unreadable",
            "br_ref": "BR-BIL-016",
            "detail": f"apps.{ELECTION_MODULE}.selectors.{ELECTION_READ} answers nothing for "
            "this account, so the channels beyond print are UNKNOWN — not empty. The "
            "preference lives on `accounts.paperless` / `accounts.sms_reminders`, which "
            "exist since migration `customers 0034`; an answer of nothing therefore means "
            "the account itself could not be resolved for this tenant, or this deployment "
            "has not run that migration. No email or SMS row is written on a guess; the "
            "print row is unaffected (BR-BIL-036 — print is the floor).",
        }
    return tuple(elected), None


def deliveries_for_bill(invoice_id: Any) -> list[dict[str, Any]] | None:
    """Where ONE bill went — or `None` when the queue cannot be asked (US-BIL-024).

    **`None` AND `[]` ARE DIFFERENT ANSWERS AND THE WHOLE FUNCTION IS ABOUT
    KEEPING THEM APART.** `[]` means the queue was asked and holds nothing for
    this bill, which for a DRAFT is simply true — queueing happens at issue.
    `None` means notifications publishes no read, so nobody can say. A screen
    given `[]` for the second case would draw an empty delivery table on an
    issued bill and tell a clerk it was never sent to anyone, which is the
    zero-that-means-I-don't-know this release is trying to stop making.

    Reads through the owning module's selector by name — billing never touches
    `outbound_messages` (B1) — and returns its rows unaltered. Mapping them to
    the four columns S30 draws is the API's job, not the seam's: a seam that
    reshaped rows would be a second place for the queue's vocabulary to live.

    **NOTHING HERE MEANS "DELIVERED".** Every row rests `queued`: there is no
    dispatcher (US-NOT-002) and no provider adapter (US-NOT-003) in R2, so a
    queued row is the finished state of a bill run today and not a failed send
    (`DELIVERY_UNAVAILABLE`, which the caller carries onto the screen).
    """
    read = _resolve(DELIVERY_MODULE, DELIVERY_READ, "selectors")
    if read is None or invoice_id is None:
        return None
    return list(read(SOURCE_INVOICE, invoice_id))


def template_print_pin_count(template_id: Any, version: Any) -> int | None:
    """How many SENT PRINT ROWS pin this bill-layout version — or `None`.

    `DEF-2496` / BR-NOT-025. Asked through the owning module by name, because
    `outbound_messages` is notifications' table and billing may not read it (B1)
    — the same door `deliveries_for_bill` above goes through.

    ⚠ **`None` AND `0` ARE DIFFERENT ANSWERS AND THE CALLER MUST NOT COLLAPSE
    THEM.** `0` means the queue was asked and holds no print row for this
    version. `None` means notifications publishes no such read, so nobody can
    say — and a delete path that read `None` as *"nothing pins it, go ahead"*
    would delete a version on the strength of a question it could not ask. That
    is DEF-127's mistake pointed at a document instead of at money.
    `templates_service.pin_count` keeps them apart deliberately.

    **AND THIS IS THE READABLE HALF, NOT THE GUARANTEE.** The floor is
    `billing/0025`'s trigger, which counts the same table inside the engine,
    where a shell, a data migration and a future endpoint all reach and none of
    them can decline to ask.
    """
    read = _resolve(DELIVERY_MODULE, TEMPLATE_PIN_READ, "selectors")
    if read is None or template_id is None or version is None:
        return None
    return int(read(template_id, version))


# ══════════════════════════════════════════════════════════════════════════
# THE FIGURES ON THE BILL-READY EMAIL — ADDED 2026-09-07 (`DEF-BIL-4448`)
# ══════════════════════════════════════════════════════════════════════════
# **WHAT THE DEFECT WAS, and it is `DEF-PAY-4409`'s exact shape one document
# over.** `queue_bill_delivery` named no merge values at all, so every bill
# this product queued for email carried a letter reading:
#
#     Hi ——,
#     Your bill for —— is ready, and it is attached to this email.
#     Bill ——, billed ——
#     Service period —— to ——
#     Previous balance ——   Payments received ——   Current charges ——
#     Total due —— by ——
#
# The subject line — A19 r8's own *"Your Silver Creek Water bill is ready —
# $247.30 due Aug 25"* — came out as *"Your Brazos Bend Utilities bill is ready
# — —— due ——"*. Nothing was broken: the seeded body is right, the renderer is
# right, and `rendering` printed the named absence `OQ-117` ratified. The
# caller's half was missing, exactly as it was for the receipt.
#
# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  EVERY FIGURE COMES OFF THE LOCKED SNAPSHOT. NOTHING IS QUERIED, AND     ║
# ║  THAT IS A REQUIREMENT RATHER THAN AN OPTIMISATION.                      ║
# ╚══════════════════════════════════════════════════════════════════════════╝
# Two reasons, and they point the same way:
#
#   1. **BR-BIL-026 / BR-BIL-030.** `bill_payload` is the instance locked at
#      issue. The email must state the numbers the PRINTED bill states, and the
#      printed bill is rendered from that payload by `documents._summary`. A
#      live read here would let the email and the enclosure disagree about what
#      a customer owes — the failure the lock exists to prevent.
#   2. **THIS RUNS INSIDE `issue.issue_invoice`'S TRANSACTION, ONCE PER BILL,
#      FIVE HUNDRED TIMES A MORNING.** A per-bill ledger read would put five
#      hundred queries inside one money transaction for a letter. Hard rule 4
#      says do not widen what that transaction writes; this widens what it
#      READS by nothing at all on the ordinary path.
#
# So there is no savepoint here on the ordinary path and there is nothing for
# one to protect: every value is an attribute of a row the caller already holds
# in memory. The ONE database read this function can make — the original bill's
# total on a correction — is wrapped in its own savepoint (CLAUDE.md hard-won
# law 14), because on PostgreSQL a statement that errors inside a transaction
# aborts it, and losing an issued bill over a figure on a covering email would
# be a far worse defect than the em-dash it replaces.
#
# **A KEY IS PRESENT EVEN WHEN ITS VALUE IS None.** `notifications.services.
# _context_gap` cannot tell a figure nobody had from a figure nobody remembered
# unless the caller says which, so every token the three bill wordings can name
# is stated here — `correction_reason` included, which this seam genuinely does
# not hold (see below).
#
# **AND THE MONEY IS A `Decimal`, NEVER THE PAYLOAD'S TEXT.** `_stamp_balance_
# forward` writes `"45.000000"` — six-decimal TEXT, because a `Decimal` in jsonb
# reads back a float and rule 2 forbids that. Passed through as text it would
# print `45.000000` on a customer's email; passed as a `Decimal` it goes through
# `rendering.encode_context` → `format_money` → **`45.00 USD`**, which is the
# one display-rounding path B4 permits. `DEF-NOT-4413` was this exact mistake
# one screen over.


def _payload_money(payload: dict[str, Any], key: str) -> Decimal | None:
    """A stamped six-decimal money TEXT → a `Decimal`, or None.

    None rather than `Decimal("0")` on anything unreadable, and that is
    `DEF-127`'s lesson restated: an absence must never be spelled the same way
    as zero. `_stamp_balance_forward` writes NULLS — not zeros — when the
    payments seam could not be reached, and a covering email that printed
    `0.00 USD` for a previous balance the bill itself dashes would tell a
    customer in arrears that they are square.
    """
    raw = payload.get(key)
    if raw is None or raw == "":
        return None
    try:
        return Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _payload_date(payload: dict[str, Any], key: str) -> date | None:
    """A stamped ISO date TEXT → a `date`, or None.

    A `date` and not the string, for the same reason the money is a `Decimal`:
    `rendering._rendered_value` formats BY TYPE, so a string would print ISO on
    a tenant whose Regional format is `DD/MM/YYYY` and the bill beside it would
    print the tenant's.
    """
    raw = payload.get(key)
    if not raw:
        return None
    try:
        return date.fromisoformat(str(raw))
    except (TypeError, ValueError):
        return None


def _original_total(invoice: Any) -> tuple[Decimal | None, tuple[dict[str, Any], ...]]:
    """`{original_total}` — what the bill this one REPLACES was issued for.

    The only database read in this whole context, and it happens ONLY on a
    correction rebill (`corrects_invoice_id` is NULL on nearly every bill), so
    an ordinary five-hundred-bill run makes none of them.

    ⚠ **ITS OWN SAVEPOINT (CLAUDE.md hard-won law 14).** This runs inside
    `issue_invoice`'s transaction. On PostgreSQL a statement that errors inside
    a transaction ABORTS it, so a bare `try` here would catch cleanly and then
    doom the issued bill, its lines and its balanced journal pair at COMMIT with
    *"current transaction is aborted"*. SQLite has no such state, so the version
    without the nested `atomic()` passes the entire suite and loses a bill the
    first time this read refuses in production. **Do not simplify it away.**
    """
    original_id = getattr(invoice, "corrects_invoice_id", None)
    if original_id is None:
        return None, ()
    try:
        with transaction.atomic():
            from apps.billing import models as billing_models  # local: import cycle

            original = (
                billing_models.Invoice.objects.filter(tenant_id=invoice.tenant_id, pk=original_id)
                .values_list("total", flat=True)
                .first()
            )
        return (original if isinstance(original, Decimal) else None), ()
    except Exception as failure:  # noqa: BLE001 — a figure must not fail the bill
        return None, (
            {
                "code": CORRECTED_BILL_FIGURE_UNREADABLE,
                "br_ref": "BR-BIL-026",
                "token": "original_total",
                "detail": f"the total of the bill this one replaces could not be read: "
                f"{failure} The corrected-bill email is queued anyway with that one line "
                "printed as a named absence (——) and the bill itself is unaffected. A "
                "document with a named absence goes out because the customer needs the "
                "rest of it (OQ-117).",
            },
        )


def bill_render_context(invoice: Any) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    """Every token the bill wordings can name, and what it is worth on THIS bill.

    Returns `(context, problems)`. The context goes straight to
    `queue_document(render_context=...)`, which stamps it on every queue row
    this bill writes (`outbound_messages.render_context`) so the dispatch-time
    render has the figures BR-NOT-012 says live there.

    THE TOKENS ARE THE UNION OF THE THREE WORDINGS A BILL CAN BE QUEUED AS —
    `email_bill_ready` (eleven), `sms_bill_ready` (two) and
    `email_corrected_bill` (five) — read off `catalogs.AUTHORED_CATALOGS` and
    the seeded bodies rather than guessed. The union is right because
    `queue_document` takes ONE context for every channel of one document, and
    a token a body does not use is simply never substituted.

    ⚠ **`{total_due}` IS THE PAYLOAD'S FIGURE AND NOT `invoices.total`, AND THE
    DIFFERENCE IS THE WHOLE POINT OF THE LINE.** `invoices.total` is THIS
    PERIOD's charges alone — `issue.py`'s own trailer says prior balance is not
    in it — and A19 §1.3's TOTAL DUE is previous balance − payments + current
    charges. Putting `invoices.total` in the subject line would understate what
    a customer owes by their entire arrears, on the one line of the one email
    they actually read.

    ⚠ **`{correction_reason}` WAS DELIBERATELY ABSENT UNTIL 2026-10-22
    (`DEF-BIL-4454`).** The product held only internal reason CODES
    (`wrong_read`), and `correction_reasons.MECHANISM_IN_WORDS` describes the
    mechanism to a clerk, not the fault to a customer, so the line printed `——`.
    The PO then ruled Q3: one plain sentence per reason, written by us and
    editable by the utility. It is now filled by `_correction_reason`, through
    notifications' published read — this seam still invents no wording.

    ⚠ **THIS WRITES NOTHING ON THE BILL AND WIDENS NO TRANSACTION** (hard rule
    4) — its one write is the email link's `bill_links` row, in its own
    savepoint (`bill_links.mint`, DEF-BIL-10531). It reads
    attributes of a row the caller already holds, plus — on a correction only —
    one indexed row of billing's OWN table inside its own savepoint. Hard rule
    7's audit row for this bill was written by `issue_invoice` before this is
    ever called, and BR-AUD-006's posture (the FACT of an address, never the
    address) is why the customer's name is not copied into a second audit
    payload here.
    """
    payload = invoice.bill_payload if isinstance(invoice.bill_payload, dict) else {}
    problems: tuple[dict[str, Any], ...] = ()

    # BR-BIL-030 — the name captured at GATHER, not re-joined at issue: a
    # customer renamed between the run and the release must not be greeted by
    # the new name on a bill for a period billed under the old one.
    name = payload.get("customer_name") or None
    original_total, trouble = _original_total(invoice)
    problems += trouble
    correction_reason, trouble = _correction_reason(invoice)
    problems += trouble

    context: dict[str, Any] = {
        # ── who it is for ───────────────────────────────────────────────────
        # A13's greeting is `Hi {first_name},`. DEF-NOT-10542 — derived by the
        # ONE shared rule (`notifications.customer_context.greeting_name`), so
        # `Miller, Sarah` greets `Sarah` here exactly as on every other letter.
        # The stamped name is passed (BR-BIL-030) and nothing is queried; the
        # payload holds no person/company kind (decision log 2026-10-22).
        "first_name": _greeting_name(name),
        "customer_name": name,
        "account_no": payload.get("account_no") or None,
        # `DEF-BIL-9787` — the commercial bill's `{po_number}` (A19 rule 4),
        # stamped at draft by stage 6; None where the account names no PO.
        "po_number": payload.get("po_number") or None,
        # CLAUDE.md hard rule 8 — the address is the PREMISES' and is walked to,
        # never held twice. `gather._service_address(premises)` did that walk at
        # gather time and stamped the answer; re-deriving it here would be a
        # second copy free to disagree with the printed bill's masthead.
        "service_address": payload.get("service_address") or None,
        # ── which bill ──────────────────────────────────────────────────────
        "bill_no": getattr(invoice, "invoice_no", None) or None,
        # BR-BIL-070's stamped bill date — the clerk's typed date where the run
        # carried one, else the cycle's own bill day. NOT `issued_at`, which is
        # a timestamp of when the software ran and is not the date on the page.
        "bill_date": _payload_date(payload, "bill_date"),
        "period_start": getattr(invoice, "period_start", None),
        "period_end": getattr(invoice, "period_end", None),
        "due_date": getattr(invoice, "due_date", None),
        # ── the summary box, A19 §1.3, exactly as the paper bill prints it ───
        "prev_balance": _payload_money(payload, "previous_balance"),
        "payments": _payload_money(payload, "payments_credits"),
        # `invoices.total` IS current charges — this period and nothing else —
        # and it is already a Decimal on the row, so it is taken from the column
        # rather than from the payload's text copy of it.
        "current_charges": getattr(invoice, "total", None),
        "total_due": _payload_money(payload, "total_due"),
        # ── the corrected-bill wording only ─────────────────────────────────
        "original_total": original_total,
        # DEF-BIL-4454 — one customer sentence per reason on the case.
        "correction_reason": correction_reason,
    }
    # DEF-BIL-10531 (PO 2026-10-22, *"b direct PDF link"*) — `{bill_link}` and
    # `{link_expires_on}`: a secret, expiring link to THIS bill's kept PDF.
    from apps.billing import bill_links

    link, link_problems = bill_links.mint(invoice)
    context.update(link)
    return context, problems + link_problems


#: notifications' published greeting rule (`DEF-NOT-10542`).
GREETING_MODULE = "customer_context"
GREETING_READ = "greeting_name"


def _greeting_name(name: Any) -> str | None:
    """`{first_name}` from the shared builder — never a second parser here."""
    greet = _resolve(DELIVERY_MODULE, GREETING_READ, GREETING_MODULE)
    if greet is None:  # pragma: no cover - notifications ships in this repo
        return None
    return greet(str(name) if name else None)


#: notifications' published read of *What changed* (`DEF-BIL-4454`).
REASON_SENTENCES_MODULE = "correction_reason_wording"
REASON_SENTENCES_READ = "sentences_for"


def _correction_reason(invoice: Any) -> tuple[str | None, tuple[dict[str, Any], ...]]:
    """`{correction_reason}` — *What changed*, one sentence per reason.

    `DEF-BIL-4454`, PO 2026-10-22 Q3: one plain sentence per reason, written by
    us, utility-editable on Configure → Templates, in all eleven languages.
    The sentences are notifications' (`correction_reason_wording.sentences_for`,
    BR-NOT-015 — the wording is theirs to own); this asks it by name with the
    reason CODES of the case that is replacing the original bill.

    The case is found from the bill this one REPLACES: the newest case row
    naming that original. Only a correction rebill reaches here
    (`corrects_invoice_id` is NULL on nearly every bill), so an ordinary run
    makes no extra query. Worked: Daniel's case `["wrong_read"]` →
    *"We corrected your meter reading."*

    ⚠ **ITS OWN SAVEPOINT (hard-won law 14)**, for `_original_total`'s reason:
    this runs inside `issue_invoice`'s transaction, and a statement that
    errors there would doom the bill at COMMIT on PostgreSQL. A failed read
    prints `——` and the letter goes out.
    """
    original_id = getattr(invoice, "corrects_invoice_id", None)
    if original_id is None:
        return None, ()
    read = _resolve(DELIVERY_MODULE, REASON_SENTENCES_READ, REASON_SENTENCES_MODULE)
    if read is None:  # pragma: no cover - notifications ships in this repo
        return None, ()
    try:
        with transaction.atomic():
            from apps.billing.correction_models import CorrectionCaseBill  # local: cycle

            codes = (
                CorrectionCaseBill.objects.filter(
                    tenant_id=invoice.tenant_id, invoice_id=original_id
                )
                .order_by("-created_at", "-id")
                .values_list("case__reason_codes", flat=True)
                .first()
            )
            # PO option B, 2026-10-29: the sentence follows the account's
            # language like the email it sits in.
            return read(codes or (), account_id=getattr(invoice, "account_id", None)), ()
    except Exception as failure:  # noqa: BLE001 — a sentence must not fail the bill
        return None, (
            {
                "code": CORRECTED_BILL_FIGURE_UNREADABLE,
                "br_ref": "BR-BIL-026",
                "token": "correction_reason",
                "detail": f"what changed on the bill this one replaces could not be read: "
                f"{failure} The corrected-bill email is queued anyway with that line "
                "printed as a named absence (——).",
            },
        )


#: `DEF-BIL-10530` — the channels on which a bill travels as a NOTIFICATION that
#: it exists (a subject and a body a customer reads in their mail), rather than
#: as the bill itself. Print and the portal carry the DOCUMENT and keep its
#: bill-layout pin; these two take a wording class of their own.
CHANNEL_SMS = "sms"
WORDING_CHANNELS: tuple[str, ...] = (CHANNEL_EMAIL, CHANNEL_SMS)
#: notifications' published read of an event's wording class per channel.
WORDING_CLASS_READ = "template_class_for_event"


def _wording_pins(pin_type: Any, event_key: str) -> dict[str, Any]:
    """The email / text pins for this bill — a wording CLASS, never the layout.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  DEF-BIL-10530 (PO 2026-10-22): A BILL'S EMAIL WAS PINNED TO THE BILL  ║
    ║  LAYOUT AND SAT AT "WAITING · 0 TRIES" FOREVER.                        ║
    ╚══════════════════════════════════════════════════════════════════════╝

    `invoice.template_id` is a `BillTemplateVersion` — the PDF layout. Until
    this function existed it was the ONE pin `queue_document` stamped on every
    row, email included, so the email row named a notification template that
    does not exist; the dispatcher could never render it and, until the same
    fix, released it with its try reset every cycle. The PO ruled, verbatim
    from the decision log of 2026-10-22: *"Email pins `email_bill_ready`, a
    text pins `sms_bill_ready`; print and portal keep the bill layout."*

    The class is NOT typed here. It is notifications' SET-12 answer for this
    bill's event (`template_class_for_event`): `bill_ready` →
    `email_bill_ready` / `sms_bill_ready`, `bill_corrected` →
    `email_corrected_bill` — a constant read, no query. **One judgment, recorded:** `bill_corrected` offers no SMS class, and
    a corrected bill can still reach an account that elected texts (the rule
    passes an unruled channel through). That text takes the `bill_ready` class
    — the ruling's literal *"a text pins `sms_bill_ready`"*, and what it says
    (*"your new bill is ready"*) is true of a replacement bill — rather than the
    bill layout (the defect) or nothing (a row that could never say what it is).

    Returns `{}` when notifications publishes no such read, which leaves every
    row on the document pin exactly as before — and those email rows now FAIL
    with their reason at dispatch rather than wait forever, which is the other
    half of the same fix.
    """
    read = _resolve(DELIVERY_MODULE, WORDING_CLASS_READ, "services")
    if read is None:
        return {}
    pins: dict[str, Any] = {}
    for channel in WORDING_CHANNELS:
        code = read(event_key, channel) or read(EVENT_BILL_READY, channel)
        if code:
            pins[channel] = pin_type(code=code)
    return pins


def queue_bill_delivery(
    invoice: Any,
    *,
    template_code: str | None = None,
    dispatch_not_before: datetime | None = None,
    copy_no: int = 0,
    actor: Any = None,
) -> BillDelivery:
    """BR-BIL-016 — one delivery record per bill per channel. Queues; never sends.

    Called from inside `issue.issue_invoice`'s transaction, so a bill and its
    delivery rows commit together or not at all.

    The template PIN comes off the BILL, not from today's published version:
    `invoice.template_id` + `invoice.template_version` are stamped at issue and
    frozen with the money (BR-BIL-026), and the queue row must carry the same
    pair or a reprint could render something the customer never received. A bill
    with no pin is refused here as well as at issue — belt and braces on the one
    fact that can never be added later.

    `template_code` is the readable handle (`bill_residential`) and is OPTIONAL
    because `bill_templates` (r10 #4) is not built: the caller passes it when it
    has one and the row carries the pin either way. It is not defaulted to a
    plausible string — a code nobody assigned would look like a resolved
    template assignment (BR-BIL-025) that has never happened.

    `dispatch_not_before` is S31 step 6's send-now vs scheduled choice, passed
    through as a PARAMETER and never read from a clock (BR-TEN-043).

    The SET-12 EVENT is named on every write (CR-048 wave B) and is derived from
    the bill by `event_for_bill` — `bill_ready`, or `bill_corrected` when this
    bill carries `corrects_invoice_id`. It is not a parameter: see that
    function for why a flag would have been a second copy of a fact the row
    already states. The utility's rule is then read and intersected inside
    `queue_document`, so a channel switched off on Settings → Notifications is
    not queued and the reason rides back on `problems`.

    Raises `BillingRuleError` — never notifications' own exception type — so a
    bill that cannot be queued is one named break in the run's break list and
    the other bills carry on (BR-BIL-055).
    """
    write = _resolve(DELIVERY_MODULE, QUEUE_WRITE, "services")
    if write is None:
        raise BillingRuleError(
            f"apps.{DELIVERY_MODULE}.services.{QUEUE_WRITE} is not published, so this bill "
            "cannot leave a delivery record (BR-BIL-016). Billing may not write "
            "notifications' table itself (B1), and an issued bill is immutable — a bill "
            "issued with no delivery row is one nobody will ever be sent and no later "
            "path would notice."
        )
    if invoice.template_id is None or invoice.template_version is None:
        raise BillingRuleError(
            f"bill {getattr(invoice, 'invoice_no', None) or invoice.pk} carries no template "
            "pin, so its delivery row could not say what will be rendered (BR-BIL-026). The "
            "pin is stamped at issue and a reprint renders that version forever."
        )

    channels, election_problem = elected_channels(getattr(invoice, "account_id", None))
    pin_type = _resolve(DELIVERY_MODULE, "TemplatePin", "services")
    refusal_type = _resolve(DELIVERY_MODULE, "QueueWriteRefused", "services")
    if pin_type is None or refusal_type is None:  # pragma: no cover - defensive
        raise BillingRuleError(
            f"apps.{DELIVERY_MODULE}.services publishes {QUEUE_WRITE} but not its "
            "`TemplatePin` / `QueueWriteRefused` contract types, so this bill cannot be "
            "queued through the seam. Half a published interface is not an interface."
        )
    # THE EVENT (CR-048 wave B). Resolved through the module global rather than a
    # local so the decision stays greppable and testable on its own.
    event_key = event_for_bill(invoice)
    if EVENT_PARAMETER not in signature(write).parameters:  # pragma: no cover - defensive
        # Half a published interface, again, and this half is the one CR-048
        # exists for: a `queue_document` that cannot be told the event would
        # queue every bill on whatever the caller asked for and the settings
        # screen would silently go back to being decoration. Refused per bill
        # (BR-BIL-055) rather than passed and lost, because a TypeError here is
        # not a `BillingRuleError` and would take the whole run with it.
        raise BillingRuleError(
            f"apps.{DELIVERY_MODULE}.services.{QUEUE_WRITE} does not accept "
            f"`{EVENT_PARAMETER}`, so this bill cannot be queued as the event it is "
            f"({event_key}) and this utility's Settings → Notifications rule could not be "
            "applied to it (CR-048 wave A). Queueing it anyway would send on channels the "
            "utility has switched off."
        )
    pin = pin_type(
        code=template_code,
        template_id=invoice.template_id,
        version=invoice.template_version,
        # BR-NOT-006: the pinning tuple includes the LANGUAGE variant. NULL
        # here is the FALLBACK — the utility's `default` wording — and is not
        # the whole answer: ⚠ AMENDED 2026-10-29 (PO option B, *"Question:
        # which language should messages be sent in? - B"*, superseding
        # `OQ-CUS-12619` (a) for messages). `queue_document` reads the
        # account's own language from `account_id` below and asks for it
        # first, class by class, so Rosa's *Bill ready* email is Spanish where
        # Springfield published one. A bill already pinned (`template_id` +
        # `version` above) is never re-asked (BR-BIL-026).
        language=None,
    )

    # `DEF-BIL-10530` — email and text take a WORDING pin; print and the portal
    # keep the bill layout above. Passed only to a `queue_document` that can
    # take it, so an older owner degrades to the old shape rather than a
    # TypeError that would take the whole run down (BR-BIL-055).
    extra: dict[str, Any] = {}
    if "channel_templates" in signature(write).parameters:
        extra["channel_templates"] = _wording_pins(pin_type, event_key)

    # `DEF-BIL-4448` — THE FIGURES. Built from the LOCKED payload the printed
    # bill renders from, so the covering email and the enclosure state the same
    # numbers; the block comment on `bill_render_context` holds the whole
    # argument, including why nothing is queried and what is deliberately blank.
    render_context, figure_problems = bill_render_context(invoice)

    try:
        written = write(
            source_type=SOURCE_INVOICE,
            source_id=invoice.pk,
            channels=channels,
            template=pin,
            account_id=getattr(invoice, "account_id", None),
            dispatch_not_before=dispatch_not_before,
            copy_no=copy_no,
            actor=actor,
            job=None if actor is not None else "billing.issue",
            render_context=render_context,
            **extra,
            **{EVENT_PARAMETER: event_key},
        )
    except refusal_type as refusal:  # notifications' vocabulary → billing's
        raise BillingRuleError(
            f"bill {getattr(invoice, 'invoice_no', None) or invoice.pk} could not be queued "
            f"for delivery: {refusal}"
        ) from refusal

    problems = tuple(written.problems) + figure_problems
    if election_problem is not None:
        problems += (election_problem,)
    return BillDelivery(
        invoice_id=str(invoice.pk),
        channels=written.channels,
        queued=tuple(message.id for message in written.created),
        already_queued=tuple(message.id for message in written.already_queued),
        problems=problems,
        event_key=event_key,
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-023@e9d5a48 (the four billing sources — B2 §2 + Addendum r10 #8 ·
#         EP-BIL-06-templates-delivery.md · 07-billing/02-business-rules.md ·
#         07-billing/03-field-map.md)
# generated: 2026-08-11 by story-coder (W3 delivery-queue lane — billing's half
#         of BR-BIL-016; the queue itself is apps/notifications)
# checklist: A✔ B✔ C✔ D✔(2026-08-16 — the read half landed: `deliveries_for_bill` resolves notifications' newly published `deliveries_for_source`, and `GET /invoices/{id}` serves the four columns on `deliveries`. 11b §2.8 also contracts a standalone `GET /invoices/{id}/deliveries`; it is deliberately NOT mounted, because the panel is on the bill detail a clerk already has open and a second route serving one nested list would be a second place for the None-versus-[] rule to go wrong — REPORTED, not omitted quietly) E✔(S30's DeliveryPanel in 07-frontend/src/features/billing/BillDetailPage.tsx, which was BUILT with the detail screen and had rendered its absence branch on every bill in the product until this landed — hard-won law 2 from the read side) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · tests/test_us_bil_023_delivery_queue.py — the print
#         floor and the idempotency guard were each broken deliberately, run,
#         and the measured failure quoted in the lane report before either was
#         trusted green (hard-won law 7)
# exceptions: (1) QUEUES, NEVER SENDS. No provider call exists anywhere in this
#         path; email ACTIVATION is R4 (B12). `DELIVERY_UNAVAILABLE` says so on
#         every result so "queued" is never read as "sent".
#         (2) ⚠ THIS LINE READ "EVERY BILL GETS EXACTLY ONE ROW TODAY — the
#         print floor. The ELECTION (`accounts.paperless` / `.sms_reminders`) is
#         PROPOSED-SCHEMA and unbuilt and customers publishes no selector".
#         BOTH COLUMNS LANDED 2026-08-31 (customers 0034, CR-052 task 14) and
#         the read is published, so a bill now gets one row, two or three
#         according to what its account elected — and the print row is in every
#         one of them (BR-BIL-036). J17's finished shape (240 print + email rows
#         for paperless accounts) arrived with no edit in this file, which is
#         what the old sentence predicted. What an elected SMS row still lacks
#         is an ADDRESS: DEF-2700.
#         (3) BILLING NAMES NO RECIPIENT. The address is customers' to answer
#         and notifications asks it by name; billing's one reviewed FK reaches
#         the account row and not `contacts`.
#         (4) NO LANGUAGE ON THE PIN (BR-NOT-006). NULL resolves the `default`
#         variant, the utility's own default-language wording — which is what
#         OQ-CUS-12619 (2026-09-23) rules every message goes in. It was
#         described here as a customers preference billing could not read;
#         no message follows the customer's preference any more.
#         (5) THE REFUSAL TYPE IS TRANSLATED (DEF-047's lesson): notifications'
#         `QueueWriteRefused` becomes `BillingRuleError`, so one unqueueable
#         bill is one break in a run of five hundred (BR-BIL-055).
#         (6) [CR-048 wave B, 2026-08-29] THE EVENT IS NAMED ON EVERY WRITE, AND
#         IT IS DERIVED, NOT PASSED. `event_for_bill` reads
#         `invoices.corrects_invoice_id` — bill_corrected when the bill replaces
#         one, bill_ready otherwise — so `issue_invoice` gained no parameter and
#         its three callers (cycle run, fee bill, correction rebill) gained
#         nothing to get wrong. Before this, `event_key` was None on every bill
#         in the product and switching *Bill ready — email* off on SET-12
#         changed nothing at all. Cost: two SELECTs per bill, no write, measured
#         in tests/test_cr048_b2_billing_fires_its_events.py rather than claimed.
#         A `queue_document` that does not accept `event_key` is REFUSED per
#         bill rather than called without it — queueing on channels a utility
#         switched off is the defect this seam now exists to prevent.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
