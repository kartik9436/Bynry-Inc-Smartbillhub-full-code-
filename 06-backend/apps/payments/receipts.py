# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-025 (the receipt election half — CR-009 C-13 wired its ONE
#           existing consumer)   Screens: S22 (record payment) · S35 · S8
# Rules:    BR-PAY-024 (a receipt is auto-queued on a recorded payment — RCT
#           series, print v1) · BR-NOT-022 (the A15 "receipt on record-payment"
#           election ships DEFAULT ON — PO 2026-08-17, OQ-205 CLOSED) ·
#           BR-NOT-005 (queue only; nothing here sends) · BR-TEN-013 / B1
#           (cross-module work through the owner's published callables, by
#           name) · CLAUDE.md rule 6 (the queue's unique key dedupes a replay)
# Rules:    [ADDED 2026-08-29 · CR-048 B1+B3] BR-NOT-017 (ONE HOME for every
#           notification rule — payments now NAMES the event so that home is
#           read) · BR-NOT-018 (an event this platform cannot fire is named,
#           never guessed — the two keys here are read from
#           `notifications.rule_catalog`) · BR-PAY-013 (the returned-payment
#           letter, on the bounce this module is now called from)
# Tests:    06-backend/tests/test_cr_009_c13_a15_toggles.py ·
#           06-backend/tests/test_cr048_b3_payments_fires_its_events.py
# Impacts:  apps/payments/services.record_payment (the caller) ·
#           apps/payments/reversal._write_reversal (the second caller, added
#           2026-08-29 — the NSF letter) ·
#           apps/notifications/selectors.receipt_on_record_payment_election ·
#           apps/notifications/services.queue_document (its `event_key`)
# ───────────────────────────────────────────────────────
"""The documents a payment leaves on the queue — and the rules over them.

HUMAN-REVIEW-PENDING — 🔒 THE QUEUE WRITE. This file decides **which document a
customer is sent when their payment bounces, and on which channel**, and it runs
inside the money transaction. Flagged 2026-08-30 by the `DEF-2473` lane, which
changed both halves of that (a second write for the printed letter, and the
outcome codes S22 groups on); it carries a row in
`12-governance/09-human-review-ledger.md` stating in plain English what a person
is being asked to rule on. AI-authored under the PO ruling of 2026-08-09: *"AI
will do it; we will review it later as human."*

HUMAN-OWNED — added 2026-08-31 when the PO's ruling put this file on
10-scripts/gates/human_owned.txt ("groups one, two, three and four ... That is
56 files"). The guard list requires both markers; this file carried only
HUMAN-REVIEW-PENDING, which is exactly why G53 could not see it (DEF-2790).

⚠ **THE TITLE OF THIS FILE WIDENED ON 2026-08-29 (CR-048 B3).** It read *"The
receipt a recorded payment leaves on the queue — and the election over it"* and
that was the whole of it: one print row, on one event, behind one A15 toggle.
It now holds BOTH of payments' SET-12 events — `payment_received` when money is
recorded and `payment_failed` when a payment comes back — because both are the
same act (write a customer document to the platform queue, and let nothing that
happens to it touch the money) and a second copy of that act is the shape that
drifts.

╔══════════════════════════════════════════════════════════════════════════╗
║  A FAILED RECEIPT MUST NEVER FAIL THE PAYMENT.                            ║
╚══════════════════════════════════════════════════════════════════════════╝
Money that was handed over is recorded whatever happens to its paperwork. So
this module RETURNS problem rows rather than raising: every outcome — queued,
election off, election unreadable, queue refused — lands on the
`RecordedPayment.problems` list as a CODE a screen can group on, and none of
them can take the payment row down with it.

WHAT THIS CLOSES. `record_payment` carried `no_receipt_queued` on every result
since it shipped: *"BR-PAY-024 auto-queues a receipt on every cleared payment …
this path does not make it."* CR-009's C-13 ruling (PO 2026-08-17: the four
A15 elections ship DEFAULT ON — *"keep them default to start with Utility will
amake them off"*) put a toggle in front of that queue write, and a toggle
nothing reads is dead UI (hard-won law 2) — so wiring THIS consumer is what
made the toggle honest, and queueing the receipt is what makes the old
`no_receipt_queued` sentence false. Both changed in the same commit.

WHAT IS QUEUED. One `pdf_print` row (BR-PAY-024: *"RCT- series, print v1"*),
source `payment` + the payment's own id — so the queue's unique key
`(tenant, source_type, source_id, channel, copy_no)` makes a replayed record
call find its own receipt and write nothing (rule 6). The template is the
seeded `receipt` class (A13's own body, planted at provisioning); the pin is
resolved AT QUEUE TIME by the owner (BR-BIL-026) and a tenant with no
published body gets a row that HOLDS with the reason, never invented content.
The RECIPIENT is resolved by notifications through customers' published read,
or honestly recorded unresolvable — payments names no address it has no right
to read (the same posture `apps/billing/delivery_seam.py` documents).

════════════════════════════════════════════════════════════════════════════
THE EMAIL RECEIPT — ADDED 2026-08-29 (CR-048 B3), AND WHY THE OLD REFUSAL WENT
════════════════════════════════════════════════════════════════════════════
⚠ **THIS SECTION REPLACES A BULLET THAT SAID THE OPPOSITE**, and it is left
visible rather than deleted because a reader who took the old sentence at its
word would otherwise never learn it had moved (hard-won law 1). It read:

    *"**No email receipt row.** The emailed receipt is the `payment_received`
    SET-12 rule's business (US-NOT-017) on a channel whose dispatch is deferred;
    writing a second email row from here would give one payment two email
    receipts the day that rule fires."*

**Its reasoning was sound and its premise is spent.** The objection was to a
SECOND writer racing the rule's own. CR-048's finding is that the rule has no
writer at all — *"the queue never reads the notification rule"* — so `payment_
received` fires from nowhere, and A1 (2026-08-29) made the queue read the rule
whenever a caller names the event. **This module is that one writer.** There is
no second one to double with, and until this landed the email half of *Payment
received* on Settings → Notifications was a switch over nothing: a utility could
turn it off, and off is what it already was.

So a recorded payment now leaves **two** rows, both naming `payment_received`:

  * `pdf_print`, template `receipt` — BR-PAY-024's own document. The event has
    no print switch, so the rule cannot take it away and the result says so.
  * `email`, template `email_payment_receipt` — the channel the rule governs.
    Switched off on SET-12, no row is written and the outcome names the switch.

**TWO WRITES AND NOT TWO CHANNELS ON ONE**, because a queue write carries ONE
template pin for every channel it names, and an email row pinned to the print
class would render the wrong document.

WHAT IS DELIBERATELY NOT HERE:
  * **No SMS receipt.** `sms_payment_received` is catalogued, but the
    `payment_received` event's channels are email alone and its template map has
    no SMS entry — so there is no switch to obey and nothing to render. Adding
    one would be this lane writing a rule, not implementing one.
  * **No render and no send** (BR-NOT-005/BR-NOT-013) — a queue row is the
    finished state of this release.
  * **No election cache.** The flag is read fresh per recorded payment through
    the published notifications read, so a clerk's change applies to the very
    next payment.
"""

from __future__ import annotations

from decimal import Decimal
from importlib import import_module
from types import SimpleNamespace
from typing import Any

from django.db import transaction

#: The notifications contracts this module depends on, named once so each is
#: greppable from BOTH sides of the boundary (the tenancy_seam discipline).
QUEUE_MODULE = "notifications"
QUEUE_WRITE = "queue_document"
ELECTION_READ = "receipt_on_record_payment_election"

#: ⚠ ADDED 2026-09-07 · `DEF-PAY-4409` — THE TWO READS THE RECEIPT'S FIGURES
#: COME FROM, named once so each is greppable from BOTH sides of the boundary
#: (the `QUEUE_WRITE` discipline three lines up). Neither module's ORM is
#: touched here: B1 / BR-TEN-013, cross-module work through the owner's
#: published callables, resolved BY NAME at call time.
#:
#: `ledger.reporting.ar_positions` is DEF-127's one derivation of what an
#: account owes — the same Σ the S17 row, the account header and the S36 KPI
#: all read, so a receipt cannot state a balance that disagrees with the screen
#: a clerk opens next. `accounts.balance` is a CACHE nothing writes (BR-CUS-015)
#: and is deliberately NOT read here; serving it is what told a customer owing
#: 108.88 that their balance was zero.
AR_MODULE = "ledger"
AR_KIND = "reporting"
AR_READ = "ar_positions"
#: The read notifications ITSELF uses to address the message
#: (`services.RECIPIENT_READ`). Using the same one for the greeting means the
#: name in *"Hi Maria,"* and the name on the envelope are one fact — a receipt
#: addressed to one person and greeting another is a defect nothing would catch.
RECIPIENT_MODULE = "customers"
RECIPIENT_READ = "delivery_recipients_for_account"

#: ⚠ ADDED 2026-08-29 · CR-048 B1+B3. The SET-12 EVENT KEYS these two documents
#: are, spelled exactly as `apps/notifications/rule_catalog.EVENT_KEYS` spells
#: them and READ from there rather than guessed — an event key this platform
#: cannot fire is refused by name at the queue (`channel_decision`), so a typo
#: here is a refusal and never a silent send.
#:
#: **WHY A KEY IS PASSED AT ALL, in one sentence:** `source_type` is one-to-MANY
#: onto events — `payment` is `payment_received` OR `payment_failed` — so the
#: queue cannot derive which of this utility's two rules governs a document, and
#: the caller is the only place that knows. This module holds both facts:
#: a payment being RECORDED is `payment_received`, and a payment that came BACK
#: (`reversal_reason` = nsf) is `payment_failed`. Neither is a new flag; both are
#: read off rows payments already writes.
EVENT_PAYMENT_RECEIVED = "payment_received"
EVENT_PAYMENT_FAILED = "payment_failed"

#: BR-PAY-024's document class — A13's own `receipt`, seeded on every tenant.
RECEIPT_TEMPLATE_CODE = "receipt"
#: The EMAIL receipt's own class (CR-048 B3). A queue write carries ONE template
#: pin for every channel it writes, so the emailed receipt is a SECOND write
#: rather than a second channel on the first — an email row pinned to the print
#: class would render the wrong document, which is worse than not sending it.
EMAIL_RECEIPT_TEMPLATE_CODE = "email_payment_receipt"
#: The returned-payment letter's class (CR-048 B3). `catalogs.py` names it
#: *"Payment failed / NSF"* and its Used-by read *"a returned payment does not
#: send this"* — which is the gap `reversal.REVERSE_UNAVAILABLE` reported from
#: the other side as `no_nsf_notice_queued`, and this is where it closes.
FAILED_PAYMENT_TEMPLATE_CODE = "email_payment_failed"
#: ⚠ ADDED 2026-08-30 · DEF-2473 — THE PRINT CLASS THE BOUNCE LETTER NEVER HAD.
#: `email_payment_failed` above is an EMAIL class, and it was the ONLY class this
#: letter had. BR-NOT-024's print floor adds `pdf_print` to every `payment` write,
#: so the printed copy was pinned to the email class and rendered an email body
#: onto paper — measured with the email switch off: one row, channel `pdf_print`,
#: template_code `email_payment_failed`.
#:
#: **The floor is signed law and is correct; the missing class was the gap.** This
#: is that class, and it ships with NO WORDING on purpose — see
#: `catalogs.LISTINGS["payment_failed_letter"]` and `seed_templates.NOT_SEEDED`.
#: A blank letter that holds and says why is a fixed defect; a letter this lane
#: drafted about somebody's returned money would be a new one (BR-NOT-015).
FAILED_PAYMENT_LETTER_TEMPLATE_CODE = "payment_failed_letter"
#: ⚠ ADDED 2026-08-30 · CR-048 wave B task B11 — the SMS receipt, and it is the
#: THIRD write for one payment rather than a third channel on either of the
#: first two, for `EMAIL_RECEIPT_TEMPLATE_CODE`'s stated reason: a queue write
#: carries ONE template pin for every channel it writes, so an SMS row pinned to
#: the print or email class would render the wrong document.
#:
#: **IT NEEDS NO NEW EVENT AND THAT IS DELIBERATE.** `sms_payment_received` is
#: the same receipt on a third surface, so it is a CHANNEL on `payment_received`
#: (rule_catalog, amended the same commit) — a utility that switches *Payment
#: received* off stops being in touch about a payment, rather than having to
#: find and switch off a second row that means the same thing.
#:
#: ⚠ **SMS IS v1.1 (BR-NOT-010) AND NOTHING SENDS ON IT (BR-NOT-013).** This
#: writes a queue row exactly as the print and email halves do; the row states
#: its own undeliverability, and an account with no SMS opt-in gets a row
#: carrying `no_sms_opt_in` rather than no row at all — A15's rule made visible
#: instead of silent.
SMS_RECEIPT_TEMPLATE_CODE = "sms_payment_received"
#: The queue vocabulary, repeated rather than imported (B1; the strings ARE the
#: contract — `source_type` is validated by the owner against SOURCE_TYPES).
SOURCE_PAYMENT = "payment"
CHANNEL_PRINT = "pdf_print"
CHANNEL_EMAIL = "email"
CHANNEL_SMS = "sms"

#: Outcome codes. CODES, because the S22 result panel groups on them.
RECEIPT_QUEUED = "receipt_queued"
RECEIPT_EMAIL_QUEUED = "receipt_email_queued"
#: CR-048 B11 — its own code, not a reuse of the email one: the S22 result panel
#: groups on these, and "the receipt went by text" and "the receipt went by
#: email" are two different things for a clerk reading that panel.
RECEIPT_SMS_QUEUED = "receipt_sms_queued"
RECEIPT_ELECTION_OFF = "receipt_election_off"
#: DEF-PAY-10086 — a credit or adjustment row is not money received.
RECEIPT_NOT_FOR_NON_CASH = "receipt_not_for_non_cash_row"
RECEIPT_ELECTION_UNREADABLE = "receipt_election_unreadable"
RECEIPT_QUEUE_UNAVAILABLE = "receipt_queue_unavailable"
RECEIPT_QUEUE_REFUSED = "receipt_queue_refused"
#: ⚠ ADDED 2026-08-29 · CR-048 B3. A refusal is the queue saying no for a reason
#: a human can act on; THIS is anything else the queue path can raise — a bug in
#: the rule read, a database error under it, an import that half-loaded. Both end
#: on `problems` and NEITHER may reach the payment (see `_queue_one`).
RECEIPT_QUEUE_ERROR = "receipt_queue_error"
#: The returned-payment letter's own outcome codes (CR-048 B3).
#: ⚠ **THIS ONE IS THE EMAIL ROW AND ONLY THE EMAIL ROW (DEF-2473).** It has
#: always been spelled as though it covered the whole document, and that is what
#: made it a false statement to S22: it was reported whenever ANY row was
#: written, so a utility that had switched *Payment failed — email* OFF got
#: `payment_failed_notice_queued channel=email` sitting beside
#: `channel_switched_off_by_rule channel=email`, with no email row in the table.
#: The CODE is unchanged — every consumer of it asserts the email row's presence
#: and keeps working — and what changed is that it is now only emitted when an
#: email row actually exists. The printed copy has its own code below, exactly as
#: the receipt path already gives print, email and SMS a code each.
FAILED_NOTICE_QUEUED = "payment_failed_notice_queued"
#: ⚠ ADDED 2026-08-30 · DEF-2473. The PRINTED returned-payment letter, and its
#: own code for the receipt path's own stated reason: S22's result panel groups
#: on these, and "we posted them a letter" and "we emailed them" are two
#: different things for a clerk reading that panel. Adding a code breaks no
#: consumer; renaming either of the two existing ones would have.
FAILED_NOTICE_LETTER_QUEUED = "payment_failed_letter_queued"
FAILED_NOTICE_QUEUE_UNAVAILABLE = "payment_failed_notice_queue_unavailable"
FAILED_NOTICE_QUEUE_REFUSED = "payment_failed_notice_refused"
FAILED_NOTICE_QUEUE_ERROR = "payment_failed_notice_error"
#: ⚠ ADDED 2026-09-07 · `DEF-PAY-4409`. ONE FIGURE on the receipt could not be
#: read, and the receipt was queued anyway with that figure named as an absence.
#: Its own code because S22's result panel groups on these: "the receipt went
#: out" and "the receipt went out with the balance missing" are two different
#: things for a clerk, and the second is the one somebody may want to chase.
RECEIPT_FIGURE_UNREADABLE = "receipt_figure_unreadable"


def _published(module: str, attribute: str, kind: str) -> Any:
    """ANY module's published callable, or None while it publishes none.

    ⚠ **WIDENED 2026-09-07 (`DEF-PAY-4409`).** It read only notifications, and
    `_resolve` below is that call kept under its old name so no existing line
    changes. The receipt's figures come from two more modules and both arrive
    the same way — resolved BY NAME at call time, never imported (B1).
    """
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - defensive
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


def _resolve(attribute: str, kind: str) -> Any:
    """Notifications' published callable, or None while it publishes none."""
    return _published(QUEUE_MODULE, attribute, kind)


# ══════════════════════════════════════════════════════════════════════════
# THE FIGURES ON THE RECEIPT — ADDED 2026-09-07 (`DEF-PAY-4409`)
# ══════════════════════════════════════════════════════════════════════════
# **WHAT THE DEFECT WAS.** Every value on a customer receipt printed `——`:
#
#     Hi ——,          Amount ——      Date ——      Method ——
#     Confirmation ——     Applied to ——
#     Balance before this payment ——      Balance after this payment ——
#
# The template was right and the renderer was right. `queue_document` takes a
# `render_context`; two sibling callers pass one and work
# (`apps/billing/delivery_seam.py` for the credit letter,
# `apps/payments/notices.py` for the plan notices) and **this file passed none
# — the parameter was not even on `_queue_one`.** `rendering.py` says so in its
# own docstring: the queue row does NOT hold the balance or the date, the
# caller must supply them at queue time, and a catalogued token with no value
# becomes a NAMED ABSENCE rather than a fabricated figure. That behaviour is
# correct and is untouched. What was missing is this half.
#
# **NOTHING HERE IS INVENTED AND NOTHING NEW IS COMPUTED.** Every value is a
# fact `record_payment` already holds or a figure an owning module already
# publishes: the payment's own columns, the allocator's own rows, the ledger's
# own per-account Σ, and the same recipient read notifications uses to address
# the message. The token SPELLINGS are read off `catalogs.CATALOGS["receipt"]`
# and the two authored palettes beside it, never guessed — that whitelist is
# what refuses `{meter_no}` on a receipt (US-NOT-005 TC-5) and it is the list
# this context is built against.
#
# **A KEY IS PRESENT EVEN WHEN ITS VALUE IS None, AND THAT IS THE POINT.**
# `render` treats a missing key and a None value identically — both print
# `——` — but a CHECK cannot: a caller that never mentioned `{confirmation}`
# has forgotten it, and a caller that passed `confirmation=None` is stating
# that this cash payment has no confirmation number. Stating every token this
# document can carry is what makes the first case findable (see
# `notifications.services._context_gap`, the guard this defect bought).
#
# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  EVERY READ BELOW RUNS IN ITS OWN SAVEPOINT — CLAUDE.md hard-won law 14.  ║
# ╚══════════════════════════════════════════════════════════════════════════╝
# This module's one law is *a failed receipt must never fail the payment*, and
# these are the first DATABASE READS it has ever done. On PostgreSQL a
# statement that errors inside a transaction ABORTS the whole transaction: a
# read that raised here would catch cleanly, and then the payment's own INSERT
# would be doomed at COMMIT with *"current transaction is aborted"*. SQLite has
# no such state, so the version without the nested `atomic()` passes the entire
# suite and loses a customer's money the first time the ledger read refuses in
# production. **Do not "simplify" the savepoints away.**
#
# They are also SEPARATE — one per figure rather than one around the lot — so a
# ledger with no AR designation costs the receipt its balances and still leaves
# it the amount, the date, the method and the confirmation number. A receipt
# missing one line is a receipt; a receipt missing every line is what the PO
# opened.


def _figure(*, token: str, reader: Any) -> tuple[Any, tuple[dict[str, Any], ...]]:
    """ONE value, read inside its OWN savepoint, or None and a reason.

    Never raises. See the block comment above for why the savepoint is the
    point and why there is one per figure.
    """
    try:
        with transaction.atomic():
            return reader(), ()
    except Exception as failure:  # noqa: BLE001 — a figure must not fail the money
        return None, (
            {
                "code": RECEIPT_FIGURE_UNREADABLE,
                "br_ref": "BR-PAY-024",
                "token": token,
                "detail": f"{{{token}}} could not be read for this receipt: {failure} The "
                "receipt is queued anyway with that one field printed as a named absence "
                "(——), and the payment stands. A document with a named absence goes out "
                "because the customer needs the rest of it (OQ-117).",
            },
        )


def _method_name(payment: Any) -> Any:
    """The tender's own name — 'Cheque', 'Card', whatever this utility calls it.

    `payment_methods` is a SEEDED, TENANT-EXTENSIBLE lookup (BR-TEN-036,
    OQ-031), so the word on the receipt is the tenant's word and never a
    constant this module holds. A payment with no method recorded returns None
    and the line prints as an absence rather than as a guess.
    """
    if getattr(payment, "method_id", None) is None:
        return None
    return getattr(payment.method, "name", None) or None


def _applied_to_bill(recorded: Any) -> Any:
    """The BILL NUMBERS this payment met, in the order the allocator met them.

    A19 r8 ratifies *applied-to bill* as receipt content and the allocator has
    already answered it: `RecordedPayment.allocations` carries `invoice_number`
    per bill, written in the same transaction as the allocation rows themselves,
    so the receipt and the trail cannot name different bills.

    **A payment that met NO bill returns None**, which prints the named absence.
    That is a real state — BR-PAY-010 carries whatever no bill could absorb as
    account credit, and BR-PAY-001's *carry credit* touches no bill at all — and
    a sentence explaining it would be this lane authoring prose for a customer
    document (BR-NOT-015). `{balance_after}` on the same receipt already tells
    them where the money went.
    """
    rows = tuple(getattr(recorded, "allocations", ()) or ())
    numbers = [str(row.get("invoice_number")) for row in rows if row.get("invoice_number")]
    return ", ".join(numbers) or None


def _customer_name(account_id: Any) -> Any:
    """Who this receipt is addressed to, through customers' OWN published read.

    `delivery_recipients_for_account` is the read `apps/notifications/services.py`
    already calls to put an ADDRESS on the queue row. Reading the same one for
    the greeting is deliberate: the name in *"Hi Maria,"* and the name on the
    envelope are then one fact, and a receipt addressed to one person and
    greeting another is a defect no gate in this repo could see.

    An account with no contact returns None with NO problem row. That is an
    ordinary account, not a fault — the receipt greets nobody by name and prints
    the absence, exactly as `rendering` does for every other missing value.
    """
    read = _published(RECIPIENT_MODULE, RECIPIENT_READ, "selectors")
    if read is None:  # pragma: no cover - customers publishes this today
        return None
    answered = dict(read(account_id, channels=("email", "pdf_print")) or {})
    for entry in answered.values():
        name = ((entry or {}).get("snapshot") or {}).get("name")
        if name:
            return str(name)
    return None


def _ar_balance(account_id: Any, *, with_held_credit: bool = False) -> Any:
    """WHAT THIS ACCOUNT OWES, from the books — never from the cached column.

    ⚠ **`with_held_credit=True` is the ACCOUNT's net position (1200 + 2400,
    signed, negative = in credit) — the account header's own figure
    (`DEF-PAY-10707`).** The printed receipt asks for it (`DEF-PAY-10770`, PO
    W4 = A: Hugo's $68.00 that met no bill prints *"Credit on account
    $68.00"*, never *"Balance remaining $0.00"*). Off by default, so every
    other caller's figure is byte-for-byte what it was.

    `ledger.reporting.ar_positions` is DEF-127's single derivation: the
    per-account slice of the same Σ `ar_control` publishes as the tie-out total,
    so this figure, the S17 row and the S36 KPI cannot disagree.
    `accounts.balance` is a CACHE nothing in this product writes (BR-CUS-015)
    and serving it is what told a customer owing 108.88 that they owed nothing.

    **`available=False` RETURNS None, NEVER 0.00** — DEF-127's own lesson, that
    the absence of an answer must not be spelled the same way as zero. A tenant
    with no AR designation gets a receipt whose balance lines read `——`, which
    is true, rather than `0.00 USD`, which a customer would act on.

    Called AFTER the payment's journal entry is written and INSIDE the same
    transaction, so what it returns is the balance AFTER this payment.
    """
    read = _published(AR_MODULE, AR_READ, AR_KIND)
    if read is None:  # pragma: no cover - the ledger publishes this today
        return None
    if with_held_credit:
        answer = dict(read(account_ids=(str(account_id),), with_held_credit=True) or {})
    else:
        answer = dict(read(account_ids=(str(account_id),)) or {})
    if not answer.get("available"):
        return None
    return dict(answer.get("positions") or {}).get(str(account_id), Decimal("0"))


def receipt_render_context(
    *,
    payment: Any,
    recorded: Any = None,
    account: Any = None,
    actor: Any = None,
) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    """Every token the three receipt bodies can name, and what it is worth.

    Returns `(context, problems)`. The context is passed straight to
    `queue_document(render_context=...)`, which stamps it on the queue row
    (`outbound_messages.render_context`) so the dispatch-time render has the
    figures BR-NOT-012 says live there. `rendering.encode_context` tags the
    `Decimal`s and `datetime`s on the way in and restores them on the way out,
    which is why money is passed as a **Decimal and never as a string**: the
    codec is what makes `format_money` — the one display-rounding path (2 dp
    beside the tenant's CHAR(3), CLAUDE.md rule 2) — run on the far side of the
    JSON column. A string here would print `123.4500` on a customer's receipt.

    ⚠ **THIS WRITES NOTHING AND WIDENS NO TRANSACTION** (hard rule 4). It reads
    three published values and copies columns the payment already carries;
    hard rule 7's audit row for this money action was written by
    `record_payment` before this is ever called, and BR-AUD-006's posture — the
    FACT of an address, never the address — is why the customer's name and
    balances are NOT copied into a second audit payload here.
    """
    problems: tuple[dict[str, Any], ...] = ()

    method, trouble = _figure(token="method", reader=lambda: _method_name(payment))
    problems += trouble
    name, trouble = _figure(
        token="customer_name", reader=lambda: _customer_name(getattr(payment, "account_id", None))
    )
    problems += trouble
    balance_after, trouble = _figure(
        token="balance_after", reader=lambda: _ar_balance(getattr(payment, "account_id", None))
    )
    problems += trouble

    # BR-PAY-010 / `ledger_seam.post_payment_cleared`: the ONLY leg of a payment
    # that credits AR is what the allocator applied to bills. Credit carried and
    # a deposit held are their own accounts and move this balance by nothing. So
    # the balance before is the balance after plus exactly that figure, and the
    # arithmetic is the seam's own — it REFUSES a posting whose legs do not foot
    # to the payment, so the two figures cannot drift apart.
    #
    # An unreadable balance stays unreadable on BOTH lines rather than one of
    # them turning into a bare number with nothing to compare it against.
    applied = getattr(recorded, "applied", None) or Decimal("0")
    balance_before = None if balance_after is None else balance_after + applied

    context: dict[str, Any] = {
        # ── the payment's own columns · no read, so nothing to fail ──────────
        "amount": getattr(payment, "amount", None),
        # BR-PAY-021's BUSINESS date and never the clearing date: `posted_at` is
        # NOT NULL, is user-entered (BR-PAY-033), and is the date this
        # transaction is judged on-time by. A cheque handed over on the 31st and
        # cleared on the 3rd is a receipt for the 31st, which is the date the
        # customer wrote on it and the only one they can check.
        "date": getattr(payment, "posted_at", None),
        "confirmation": getattr(payment, "confirmation", None) or None,
        "method": method,
        # ── the allocator's own rows, already in hand ────────────────────────
        "applied_to_bill": _applied_to_bill(recorded),
        # ── the books ───────────────────────────────────────────────────────
        "balance_before": balance_before,
        "balance_after": balance_after,
        # A13's printed receipt and the SMS both say *your new balance*, which
        # is the same figure under this class's older spelling. One value, two
        # names, so the printed and the emailed receipt of one payment can never
        # state different balances.
        "balance": balance_after,
        # ── who it is for, and who took it ──────────────────────────────────
        "customer_name": name,
        # A13's greeting. The contact carries ONE `full_name` and no separate
        # given-name column, so this is its first whitespace-delimited word —
        # see 12-governance/02-decision-log.md, 2026-09-07, for the judgment and
        # the case it gets wrong (a name recorded surname-first).
        "first_name": (name or "").split()[0] if name else None,
        "account_no": getattr(account, "account_no", None) or None,
        # A19 r8's *processed-by staff name*. None for a job or a webhook, which
        # is honest: nobody stood at a counter and took this money.
        "processed_by": (getattr(actor, "full_name", None) or None),
    }
    return context, problems


def _queue_one(
    *,
    write: Any,
    refusal_type: Any,
    source_id: Any,
    account_id: Any,
    channel: str,
    template_code: str,
    event_key: str,
    actor: Any,
    job: str,
    queued_code: str,
    unavailable_code: str,
    refused_code: str,
    error_code: str,
    what: str,
    render_context: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], ...]:
    """ONE queue write for ONE channel, and NOTHING it can do reaches the money.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  THE SAVEPOINT IS THE POINT, AND IT IS NEW (CR-048 B3, 2026-08-29).  ║
    ╚══════════════════════════════════════════════════════════════════════╝
    This module's one law is *a failed receipt must never fail the payment*, and
    until B3 it was implemented with a `try` alone. **A `try` alone is not enough
    on PostgreSQL.** Both callers run INSIDE the money transaction, and a
    statement that errors inside a Postgres transaction aborts the whole
    transaction: the `except` catches the exception, the payment's own INSERT is
    already doomed, and the COMMIT fails afterwards with *"current transaction is
    aborted"*. On SQLite the same code passes, because SQLite has no such state —
    which is why this was invisible, and why B3's tests for it run on real
    PostgreSQL.

    So the write gets its OWN savepoint. Anything that fails inside it — the
    rule read A1 added, a template resolution, the queue's own INSERT — is rolled
    back to that savepoint and the outer transaction is left usable, so the
    payment still commits.

    And the `except` is BROAD on purpose. `queue_document` now reads a tenant
    rule table before it writes (CR-048 A1), which is one more thing standing
    between a clerk pressing *Record* and the money being recorded. Catching only
    the owner's `QueueWriteRefused` would let a bug in that read take a payment
    down. Nothing is swallowed: a refusal and a fault carry DIFFERENT codes, so a
    screen and a report can tell them apart.
    """
    if write is None:  # pragma: no cover - queue_document has existed since W3
        return (
            {
                "code": unavailable_code,
                "br_ref": "BR-PAY-024",
                "detail": f"apps.{QUEUE_MODULE}.services.{QUEUE_WRITE} is not published, "
                f"so nothing could be queued for {what}. Reported rather than swallowed.",
            },
        )
    try:
        with transaction.atomic():
            written = write(
                source_type=SOURCE_PAYMENT,
                source_id=source_id,
                channels=(channel,),
                template=SimpleNamespace(
                    code=template_code, template_id=None, version=None, language=None
                ),
                account_id=account_id,
                actor=actor,
                # ⚠ CR-048 B1 — the ONE argument that makes Settings →
                # Notifications mean something for this document. Omit it and the
                # utility's rule is never read (A1's own contract).
                event_key=event_key,
                # ⚠ ADDED 2026-09-07 · `DEF-PAY-4409` — THE ARGUMENT WITHOUT
                # WHICH EVERY FIGURE ON THIS DOCUMENT PRINTS `——`. The queue row
                # does not hold the amount, the date or the balance; the caller
                # supplies them at queue time and they are stamped on the row
                # (BR-NOT-012). Omit it and the customer gets a well-formed
                # email with nothing in it, which is what shipped for three
                # weeks with `tsc`, every gate and every test green.
                render_context=render_context,
                job=None if actor is not None else job,
            )
    except Exception as failure:  # noqa: BLE001 — the one boundary where broad is right
        refused = refusal_type is not None and isinstance(failure, refusal_type)
        return (
            {
                "code": refused_code if refused else error_code,
                "br_ref": "BR-PAY-024",
                "channel": channel,
                "event_key": event_key,
                "detail": f"{what} could not be queued: {failure} The payment stands — a "
                "failed notification must never fail the money it describes.",
            },
        )

    messages = tuple(getattr(written, "messages", ()) or ())
    problems = tuple(getattr(written, "problems", ()) or ())
    if not messages:
        # The rule left no channel. `queue_document` returns an EMPTY write
        # carrying the reason rather than raising (A1), and that reason IS the
        # outcome: a utility switching a channel off is a choice, not a fault,
        # and the codes on `problems` name which switch and where to change it.
        return problems
    # ╔══════════════════════════════════════════════════════════════════════╗
    # ║  REPORT THE ROW THIS CALL ASKED FOR, NOT WHATEVER CAME BACK FIRST.   ║
    # ║  DEF-2473, 2026-08-30.                                               ║
    # ╚══════════════════════════════════════════════════════════════════════╝
    # This read `messages[0]` and reported `queued_code` with the channel this
    # call ASKED for — which is a different question from the one a screen is
    # asking, and the two answers diverge in both directions:
    #
    #   * BR-NOT-024's print floor adds `pdf_print` to every write on a floored
    #     source kind. So a call that asks for EMAIL and has its email switched
    #     off still gets a write back — carrying the floor's PRINT row — and
    #     `messages[0]` is then a row on a channel this call never asked about.
    #     Reported as `…_queued channel=email`, it is a false statement to S22:
    #     the panel showed "queued by email" beside "email switched off", with
    #     no email row in the table.
    #   * The floor also means a LATER write for another channel finds the
    #     earlier one's print row already queued (rule 6) and returns it as a
    #     `created=False` message. `messages[0]` is that row, not this one.
    #
    # So: find the message for the channel THIS call is about. If there is none,
    # this channel was not written, and the honest outcome is the reason on
    # `problems` — never a queued code for a row that does not exist.
    mine = next(
        (row for row in messages if getattr(row, "channel", None) == channel),
        None,
    )
    if mine is None:
        return problems
    message = mine
    return (
        {
            "code": queued_code,
            "br_ref": "BR-PAY-024",
            "message_id": str(getattr(message, "id", "")) or None,
            "created": bool(getattr(message, "created", False)),
            "channel": channel,
            "event_key": event_key,
            "detail": f"{what} is on the platform outbound queue for this payment. "
            "Queueing is not sending: nothing dispatches in this release "
            "(BR-NOT-013), and the row says so on the dispatch home.",
        },
        *problems,
    )


def queue_receipt_for_recorded_payment(
    *, payment: Any, recorded: Any = None, account: Any = None, actor: Any = None
) -> tuple[dict[str, Any], ...]:
    """BR-PAY-024 behind BR-NOT-022's election. Returns problem/outcome rows.

    ⚠ **`recorded` AND `account` ARRIVED 2026-09-07 (`DEF-PAY-4409`)** and they
    are the reason a receipt says anything at all. `recorded` is the
    `RecordedPayment` this call is about — the allocator's own bill numbers and
    the figure that credited AR — and `account` is the row customers' published
    read already returned to `record_payment`, so its number is copied rather
    than re-fetched. Both are OPTIONAL and both are PASSED by the one caller in
    the product: a receipt queued without them still goes out, with the fields
    they carry printed as named absences, because a failed lookup must never be
    the reason a customer is told nothing (OQ-117). `receipt_render_context`
    holds every figure and where it comes from.

    Called by `record_payment` INSIDE its transaction, after the payment row
    and its audit row exist — so a receipt row can never point at a payment
    that rolled back, and a refused receipt reports on the result rather than
    raising through the money path.

    ⚠ **THREE WRITES SINCE 2026-08-30 (CR-048 B11), NOT TWO** — print, email,
    then SMS, all three naming `payment_received`. See THE EMAIL RECEIPT in the
    module docstring for why the exception that forbade the second one is spent;
    the third arrives for the same reason and adds no new one.

    ⚠ **THE IDEMPOTENCY TUPLE, AND WHY THREE DOCUMENTS ABOUT ONE PAYMENT CANNOT
    COLLIDE.** The queue's key is (tenant, source_type, source_id, channel,
    copy_no) and all three writes share the first three — `payment` and the
    payment's OWN id. **The CHANNEL is what separates them**, and it is a column
    in the key, so the three rows are distinct by construction rather than by
    anyone remembering. A replayed `record_payment` finds all three of its own
    rows and writes nothing (rule 6).
    That is exactly the property `queue_failed_payment_notice` below does NOT
    have — a bounce letter is also an `email` row and would have collided with
    this receipt, which is why it keys on the reversing row instead.
    """
    # DEF-PAY-10086 — a credit or an adjustment is NOT money received (CR-059
    # CS-35's `NON_CASH_TYPES`). A goodwill concession is recorded as a
    # `credit` row, and its customer letter is the *credit issued* notice the
    # correction queues; a *payment received* receipt beside it told the
    # customer they had paid $40.00 they never paid (J-FIX-TWENTY S6).
    from apps.payments import models as payment_models

    if getattr(payment, "type", payment_models.PAYMENT_TYPE_PAYMENT) in (
        payment_models.PAYMENT_TYPE_CREDIT,
        payment_models.PAYMENT_TYPE_ADJUSTMENT,
    ):
        return (
            {
                "code": RECEIPT_NOT_FOR_NON_CASH,
                "br_ref": "BR-PAY-024",
                "detail": "this row is a credit or an adjustment, not money received, so "
                "no payment receipt was queued.",
            },
        )
    election = _resolve(ELECTION_READ, "selectors")
    if election is None:
        return (
            {
                "code": RECEIPT_ELECTION_UNREADABLE,
                "br_ref": "BR-NOT-022",
                "detail": f"apps.{QUEUE_MODULE}.selectors.{ELECTION_READ} is not "
                "published, so whether this utility sends receipts on record could not "
                "be read. NO receipt was queued — an unreadable election is not the "
                "same fact as one switched off, and neither is guessed.",
            },
        )
    if not election():
        return (
            {
                "code": RECEIPT_ELECTION_OFF,
                "br_ref": "BR-NOT-022",
                "detail": "this utility has switched 'receipt on record-payment' OFF "
                "(Settings → Notifications). No receipt was queued, by their own "
                "election; BR-PAY-024's document can still be produced from the payment "
                "on demand.",
            },
        )

    # ⚠ `DEF-PAY-4409` — BUILT ONCE AND SHARED BY ALL THREE WRITES, on purpose.
    # The printed, emailed and texted receipts of ONE payment must state the
    # same amount and the same balance; three contexts built three times is the
    # shape that lets them drift. Each class's palette is still a whitelist, so
    # a key no body names is simply never substituted.
    render_context, figure_problems = receipt_render_context(
        payment=payment, recorded=recorded, account=account, actor=actor
    )
    common: dict[str, Any] = {
        "write": _resolve(QUEUE_WRITE, "services"),
        "refusal_type": _resolve("QueueWriteRefused", "services"),
        # The payment's OWN id — rule 6: a replayed record call finds this exact
        # receipt row and writes nothing.
        "source_id": payment.pk,
        "account_id": getattr(payment, "account_id", None),
        "event_key": EVENT_PAYMENT_RECEIVED,
        "actor": actor,
        "job": "payments.record_receipt",
        "unavailable_code": RECEIPT_QUEUE_UNAVAILABLE,
        "refused_code": RECEIPT_QUEUE_REFUSED,
        "error_code": RECEIPT_QUEUE_ERROR,
        "render_context": render_context,
    }
    return figure_problems + (
        _queue_one(
            **common,
            channel=CHANNEL_PRINT,
            template_code=RECEIPT_TEMPLATE_CODE,
            queued_code=RECEIPT_QUEUED,
            what="a print receipt (RCT document, template 'receipt')",
        )
        + _queue_one(
            **common,
            channel=CHANNEL_EMAIL,
            template_code=EMAIL_RECEIPT_TEMPLATE_CODE,
            queued_code=RECEIPT_EMAIL_QUEUED,
            what="an emailed receipt (template 'email_payment_receipt')",
        )
        + _queue_one(
            **common,
            channel=CHANNEL_SMS,
            template_code=SMS_RECEIPT_TEMPLATE_CODE,
            queued_code=RECEIPT_SMS_QUEUED,
            what="a texted receipt (template 'sms_payment_received')",
        )
    )


def returned_payment_render_context(
    *, original: Any, nsf_fee: dict[str, Any] | None = None, bank_memo: str | None = None
) -> dict[str, Any]:
    """`DEF-PAY-10744` (audit L2-04, PO 2026-10-30) — the facts a returned-payment
    email and letter print, read AFTER the reversal and its NSF fee are written.

    Until this existed the bounce notice was queued with NO render context, so
    every figure printed `——`, and its body told the customer *"Nothing has
    changed on your account"* — false after a bounce. What it carries now:

      * `amount`, `date`, `method`, `confirmation` — the ORIGINAL payment's own
        columns (what the customer paid, when, how, the cheque or reference);
      * `bank_memo` (and `failure_reason`, the older token, the same words) —
        LBX-04's Bank memo, the bank's own words on the reversing row;
      * `nsf_fee` — the fee bill's amount when one was CHARGED, else `None`.
        `None` is not "$0.00": the token is OPTIONAL, so the fee paragraph is
        left out of the letter (no fee set on the plan, or the clerk unticked
        it). A customer is never told they were charged nothing as a figure;
      * `balance` — the account's AR position from the books (`_ar_balance`),
        so the bounced amount AND the fee are in it;
      * `due_date` — the earliest due date among the bills now open (the
        re-opened ones and the fee bill), `None` when none is dated;
      * the four customer tokens, through notifications' published
        `customer_context` (one greeting rule for every letter).

    Every read is its own savepoint (`_figure`) and an unreadable one prints its
    named absence — nothing here can fail the reversal (this module's one law).
    """
    account_id = getattr(original, "account_id", None)
    context: dict[str, Any] = {}
    read_customer = _published(QUEUE_MODULE, "customer_context", "customer_context")
    if read_customer is not None:
        customer, _ = _figure(token="customer_name", reader=lambda: read_customer(account_id))
        context.update(dict(customer or {}))
    method, _ = _figure(token="method", reader=lambda: _method_name(original))
    balance, _ = _figure(token="balance", reader=lambda: _ar_balance(account_id))
    due_date, _ = _figure(token="due_date", reader=lambda: _earliest_open_due(account_id))
    fee = None
    if nsf_fee and nsf_fee.get("status") == "charged" and nsf_fee.get("amount") is not None:
        fee = Decimal(str(nsf_fee["amount"]))
    memo = (bank_memo or "").strip() or None
    context.update(
        {
            "amount": getattr(original, "amount", None),
            "date": getattr(original, "posted_at", None),
            "method": method,
            "confirmation": getattr(original, "confirmation", None) or None,
            "bank_memo": memo,
            "failure_reason": memo,
            "nsf_fee": fee,
            "balance": balance,
            "due_date": due_date,
        }
    )
    return context


def _earliest_open_due(account_id: Any) -> Any:
    """The soonest due date among this account's open bills, or None."""
    from apps.payments import billing_seam  # local: payments' own seam, read at call time

    position = billing_seam.open_invoices_for_account(account_id)
    dates = [row.due_on for row in position.invoices if getattr(row, "due_on", None)]
    return min(dates) if dates else None


def queue_failed_payment_notice(
    *,
    reversal: Any,
    original: Any,
    actor: Any = None,
    nsf_fee: dict[str, Any] | None = None,
    bank_memo: str | None = None,
) -> tuple[dict[str, Any], ...]:
    """The `payment_failed` letter a RETURNED payment leaves on the queue.

    ⚠ ADDED 2026-08-29 · CR-048 B3, and it closes `reversal.REVERSE_UNAVAILABLE`'s
    `no_nsf_notice_queued` — *"US-PAY-009 TC-4 queues a customer NSF notice to
    the platform outbound queue … this path does not make it"*. It makes it now.

    **WHICH EVENT, AND FROM WHAT FACT.** `reversal.py` calls this only when the
    reversal reason is `nsf` — the same fact that already decides whether
    BR-PAY-013's count runs and whether the audit row is `payment.nsf` or
    `payment.reversed`. Nothing was invented for this change: a staff-initiated
    reversal (a duplicate, an error, a wrong account) is not a customer's payment
    failing and must not tell them it did.

    **`source_id` IS THE REVERSING ROW, NOT THE ORIGINAL, AND IT IS LOAD-BEARING.**
    The queue's unique key is `(tenant, source_type, source_id, channel,
    copy_no)`. The original payment already owns an `email` row under its own id —
    its emailed receipt — so keying this letter on the original would COLLIDE with
    that receipt and the bounce notice would silently dedupe into it: one row, the
    wrong document, nothing anywhere reporting a problem. The reversing row is
    one-per-bounce, so the key is exact and a re-driven bounce still writes
    nothing the second time (rule 6).

    Returns outcome rows. Like the receipt, nothing here can fail the reversal: a
    bounce that reached the books is recorded whatever happens to its letter.
    """
    common: dict[str, Any] = {
        "write": _resolve(QUEUE_WRITE, "services"),
        "refusal_type": _resolve("QueueWriteRefused", "services"),
        "source_id": reversal.pk,
        "account_id": getattr(original, "account_id", None),
        "event_key": EVENT_PAYMENT_FAILED,
        "actor": actor,
        "job": "payments.reverse_notice",
        "unavailable_code": FAILED_NOTICE_QUEUE_UNAVAILABLE,
        "refused_code": FAILED_NOTICE_QUEUE_REFUSED,
        "error_code": FAILED_NOTICE_QUEUE_ERROR,
        # DEF-PAY-10744 — the figures, stamped on BOTH rows at queue time.
        "render_context": returned_payment_render_context(
            original=original, nsf_fee=nsf_fee, bank_memo=bank_memo
        ),
    }
    # ⚠ **TWO WRITES SINCE 2026-08-30 (DEF-2473), AND THE PRINT ONE GOES FIRST.**
    # This was ONE write naming `email`, and BR-NOT-024's print floor added
    # `pdf_print` to it — so the printed copy was pinned to the EMAIL class and
    # a paper letter carried an email body. `queue_receipt_for_recorded_payment`
    # one function up has always had this right, and the reason is stated in its
    # own docstring: **a queue write carries ONE template pin for every channel
    # it names**, so a document that goes out on two channels is two writes and
    # never two channels on one. The bounce path was simply never given the same
    # treatment; it is now.
    #
    # **THE ORDER IS LOAD-BEARING AND IS NOT A STYLE CHOICE.** The floor adds
    # `pdf_print` to the EMAIL write as well, and the queue's unique key is
    # (tenant, source_type, source_id, channel, copy_no) — all four shared here.
    # Print first means the email write's floor-added channel finds a print row
    # that ALREADY EXISTS, pinned to the print class, and writes nothing (rule
    # 6). Reverse the order and the floor's row is created by the email write,
    # pinned to the email class, and the print write then dedupes into it — the
    # exact defect, restored, with both writes present and looking right.
    return _queue_one(
        **common,
        channel=CHANNEL_PRINT,
        template_code=FAILED_PAYMENT_LETTER_TEMPLATE_CODE,
        queued_code=FAILED_NOTICE_LETTER_QUEUED,
        what="a printed returned-payment letter (template 'payment_failed_letter')",
    ) + _queue_one(
        **common,
        channel=CHANNEL_EMAIL,
        template_code=FAILED_PAYMENT_TEMPLATE_CODE,
        queued_code=FAILED_NOTICE_QUEUED,
        what="a returned-payment letter (template 'email_payment_failed')",
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-025@cr009c13 (12-governance/02-decision-log.md → 2026-08-17 C-13 verbatim · 12-governance/01-open-questions.md OQ-205 closure · 04-docs/05-modules/08-payments/02-business-rules.md BR-PAY-024 · apps/notifications/services.py queue_document · apps/notifications/selectors.py receipt_on_record_payment_election)
# generated: 2026-08-18 by story-coder (CR-009 C-section lane)
# checklist: A✔ B✔ C✔ D=deferred(no new HTTP surface — record_payment's existing route carries the outcome rows) E✔(the S8 elections card is the toggle's screen; S22's problem list renders these codes) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: tests/test_cr_009_c13_a15_toggles.py — the election OFF branch was red-proved by asserting a queue row after switching the toggle off and reading the failure; the never-fail-the-payment guard by making queue_document raise and asserting the payment still recorded
# exceptions: (1) PRINT ONLY — the emailed receipt belongs to the payment_received SET-12 rule, and two writers for one email is a double send waiting for the channel to open. (2) THE ELECTION IS READ PER PAYMENT, never cached. (3) BROAD except AT THE SEAM, narrowed by type when the owner's refusal class resolves — a receipt failure of ANY shape must not take the payment down, which is this module's one law.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
