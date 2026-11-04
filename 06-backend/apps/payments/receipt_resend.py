# ── Trace ──────────────────────────────────────────────
# Change:   CR-137-BRC07 · P3.3 (`POST /payments/{id}/receipt` — *"re-queues an
#           existing document; templates, channels and queue all exist"*) and
#           P3.19 (*"paper at the window — the queue is asynchronous; a counter
#           needs a receipt in hand now"*). Blueprint 2·3h (p049–p050).
# Story:    US-PAY-025 (the receipt) · US-NOT-011 §5 (the re-send, and its
#           `copy_no` rule)   Screens: S33 · S35 · 2·2 · 2·3h
# Rules:    BR-PAY-024 (a receipt is queued on a recorded payment — RCT series)
#           · BR-NOT-005 (queue only; nothing here sends) · BR-NOT-013 (nothing
#           dispatches in this release) · BR-NOT-024 (the print floor) ·
#           BR-BIL-016 (`copy_no` 0 is the delivery record) · BR-BIL-026 (the
#           template version is PINNED at queue time and never re-resolved) ·
#           BR-PAY-018 (a HELD row is never re-sent) · BR-TEN-017 (the recipient
#           snapshot) · CLAUDE.md hard rule 6 (idempotency) · hard rule 7 ·
#           hard-won law 14 (a SAVEPOINT, because this runs on PostgreSQL) ·
#           B1 (cross-module work through the owner's published callables)
# Tests:    06-backend/tests/test_cr137_p3_detail_cancel_receipt.py
# Impacts:  apps/payments/detail_api.py (the two doors) ·
#           apps/notifications/services.queue_document (the ONE writer of
#           `outbound_messages` — reached by name, never imported around) ·
#           apps/notifications/selectors.deliveries_for_source + row_or_404 ·
#           apps/notifications/rendering.render_for_dispatch (P3.19's read)
# ───────────────────────────────────────────────────────
"""Send the receipt again — and hand one over the counter NOW.

╔══════════════════════════════════════════════════════════════════════════╗
║  THERE IS ONE RECEIPT PATH AND THIS IS NOT A SECOND ONE.                 ║
╚══════════════════════════════════════════════════════════════════════════╝
PO ruling 2026-09-22, verbatim: *"we can not have two path for 1 capabilities
wew will confuse user"*. So nothing here composes a document, picks a template,
resolves a recipient or decides a channel. It reaches the machine that already
exists:

    the document      `outbound_messages`, the row `record_payment` already
                      queued through `receipts.queue_receipt_for_recorded_payment`
    the writer        `apps.notifications.services.queue_document` — B1's ONE
                      write path into that table, and its own docstring says so
    the pin           copied off the existing row, never re-resolved (BR-BIL-026)
    the recipient     the snapshot the original row carries (BR-TEN-017)
    the figures       `render_context`, copied off the row — `DEF-NOT-4449` is
                      what dropping it costs: *Amount ——* on a resent receipt
    the renderer      `apps.notifications.rendering.render_for_dispatch`

⚠ **THE ~30 LINES THAT BUILD THE `queue_document` CALL ARE ALSO IN
`apps/notifications/api.outbound_resend`, AND THAT IS REPORTED RATHER THAN
TIDIED (`DEF-PAY-6231`).** The resend is implemented INSIDE that view rather
than in a callable this module could ask for, and `delivery_ops.py` — where it
belongs — is on `10-scripts/gates/human_owned.txt`, so extracting it is a 🔒
change with its own review row and is notifications' to make, not a payments
lane's. **The two copies are a drift risk and the defect row says so**; what
they are NOT is two paths for a user, because both end in the same writer,
writing the same table, keyed the same way.

WHY THE PAYMENTS DOOR EXISTS AT ALL
═══════════════════════════════════
`POST /outbound/{id}/resend` addresses a MESSAGE ROW. A clerk looking at
`PMT-2609-000418` does not have one and has no way to get one — that is a
dispatch-home concept. The drawing asks the question the other way round
(p049): *"They lost the receipt and want another."* **Send by: Email × Text ×**,
and the check box reads *"Queues two receipts. Nothing about the payment
changes."* So this door takes a PAYMENT and a set of CHANNELS, and finds the
rows itself.

`copy_no` IS REQUIRED AND IS THE WHOLE IDEMPOTENCY GUARANTEE (hard rule 6)
══════════════════════════════════════════════════════════════════════════
`outbound_messages` is keyed `UNIQUE (tenant, source_type, source_id, channel,
copy_no)`. `copy_no = 0` is the delivery record BR-BIL-016 mandates; 1, 2, … are
the deliberate extra copies a human asked for.

**This endpoint REFUSES without one, exactly as the notifications door does, and
for the reason that door records:** an endpoint that allocated the number itself
would post a second letter on every double click, every retried request and
every impatient refresh — *and would look perfectly correct doing it*. With the
number stated, a repeated submit collides with its own row IN THE DATABASE and
comes back `created: false`: same row, one receipt, no postage.

**The screen is not asked to invent it.** `GET /payments/{id}` serves
`receipts[]` and `next_copy_no`, which is also what draws the modal's ① *"Sent
09/21 11:42 by email and text"* — so the number the clerk submits is the number
the server just showed them, and the round trip is what makes the collision
meaningful rather than accidental.

⚠ **ONE NUMBER ACROSS EVERY CHANNEL IN ONE SUBMIT, AND THE KEY IS WHY.** The
channel is a column in the unique key, so `copy_no = 1` on email and `copy_no =
1` on text are two distinct rows by construction. Two receipts, one act, one
number — which is the drawing's *"Queues two receipts"* exactly.

════════════════════════════════════════════════════════════════════════════
P3.19 · PAPER AT THE WINDOW — AND WHY IT IS A **READ**, NOT A SEND
════════════════════════════════════════════════════════════════════════════
The task: *"The queue is asynchronous; a counter needs a receipt in hand now. A
counter customer leaves with paper."*

⚠ **THE OBVIOUS BUILD IS FORBIDDEN BY SIGNED LAW.** A11 Addendum r2 §4:
*"no synchronous send endpoint anywhere (queue only, BR-NOT-005)"*, and
`apps/notifications/api.py` states it in capitals — *"THERE IS NO SEND ENDPOINT
AND THERE MUST NEVER BE ONE … minting one is a gate failure."* So a
`POST /payments/{id}/receipt/print-now` that dispatched anything is out, and it
is out on rules nobody may quietly reinterpret.

**SO WHAT DOES "SYNCHRONOUS" ACTUALLY MEAN AT A COUNTER? It means RENDERED, not
SENT.** Walk the moment through:

  1. The customer is **standing there**. There is no address to resolve, no
     provider to hand off to and no delivery to record — the delivery is a
     person taking a piece of paper. The whole apparatus a send endpoint exists
     to drive is inapplicable, which is why refusing to mint one costs nothing.
  2. **The document already exists.** BR-NOT-024's print floor puts a
     `pdf_print` row on every recorded payment *"so a utility that switches
     every electronic channel off still gets paper"* (p050). The receipt is not
     missing; it is queued, pinned and stamped with its figures.
  3. **What is missing is a way to LOOK at it.** The queue is emptied by a job
     that runs on its own clock, and a clerk cannot wait for it with a customer
     at the window.

So P3.19 is `GET /payments/{id}/receipt/document`: it renders the row that is
already there, through notifications' own `render_for_dispatch` — the PINNED
version, no substitution (BR-BIL-026) — and returns the body for the browser to
print. **It queues nothing, sends nothing, dispatches nothing, and touches no
money.** The queued row stays exactly where it was and the print job will still
pick it up; a counter reprint is not a second delivery, it is the same document
read early.

⚠ **IT IS TEXT, NOT A PDF, AND THAT IS THE REPO'S OWN STANDING POSITION** —
`rendering.py`'s exception (2): *"NO PDF. OQ-149 closed 2026-08-12 … no
page-rendering library is in the image; printable classes render their TEXT body
here."* The browser's own print dialog is what puts it on paper.

**Hard rule 7 applies and the row is written.** Handing a customer a document
that states what they paid is a money act in every sense that matters later:
`payment.receipt_printed`, naming who printed it and which copy they were
looking at. `unsent_preview.preview` sets the precedent — a read that discloses
a document's contents writes its own trail.

The whole of this reasoning is in `12-governance/02-decision-log.md` under
2026-09-23, because the drawing does not settle it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from typing import Any

from django.db import transaction

from apps.payments import models
from apps.payments.exceptions import PaymentRuleError
from core import audit as core_audit
from core import errors
from core import tenancy as core_tenancy

#: `outbound_messages.source_type` for a payment's documents — the same string
#: `receipts.SOURCE_PAYMENT` writes, so the two never address different rows.
SOURCE_PAYMENT = "payment"

#: The three channels a receipt goes out on (`receipts.queue_receipt_for_
#: recorded_payment` writes all three). Named here so a caller cannot ask for a
#: channel that is not a receipt channel and get a silent nothing.
CHANNEL_PRINT = "pdf_print"
CHANNEL_EMAIL = "email"
CHANNEL_SMS = "sms"
RECEIPT_CHANNELS = (CHANNEL_PRINT, CHANNEL_EMAIL, CHANNEL_SMS)

AUDIT_RESENT = "payment.receipt_resent"
AUDIT_PRINTED = "payment.receipt_printed"
AUDIT_ENTITY = "payment"

#: Outcome codes. Sentences live in the eleven catalogues (B14 rule 35).
RESENT = "receipt_resent"
RESEND_QUEUE_REFUSED = "receipt_resend_queue_refused"
RESEND_QUEUE_ERROR = "receipt_resend_queue_error"
NOTHING_ABOUT_THE_PAYMENT_CHANGED = "resend_touched_no_money"

NOTIFICATIONS = "notifications"


def _tenant_id() -> Any:
    """CLAUDE.md rule 1 — nothing touches a tenant table without `app.tenant_id`."""
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _resolve(attribute: str, kind: str) -> Any:
    """A notifications callable, by NAME (B1) — or None while it is unpublished."""
    try:
        target = import_module(f"apps.{NOTIFICATIONS}.{kind}")
    except ImportError:  # pragma: no cover - defensive
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) or isinstance(found, type) else None


@dataclass(frozen=True)
class ResentReceipt:
    """What a resend queued — one entry per channel the clerk chose."""

    payment_id: str
    payment_no: str | None
    copy_no: int
    #: `[{channel, message_id, created}]` — `created: false` is a REPLAY on that
    #: channel and means the customer gets one copy, not two (hard rule 6).
    queued: tuple[dict[str, Any], ...] = ()
    problems: tuple[dict[str, Any], ...] = field(default=())


# ── the read behind the modal's ① and behind `next_copy_no` ────────────────
def receipt_deliveries(payment: models.Payment) -> list[dict[str, Any]]:
    """Every receipt row this payment has, through notifications' own read.

    `[]` means *the queue was asked and had nothing* — a real answer, and a
    different one from *the queue could not be asked*, which is `None` from the
    seam (`deliveries_for_source` states that distinction itself). A payment
    recorded while the utility had the receipt election switched OFF genuinely
    has no rows, and the modal's ① then says so rather than claiming a first send.
    """
    read = _resolve("deliveries_for_source", "selectors")
    if read is None:  # pragma: no cover - published since W3
        return []
    return [
        row
        for row in read(SOURCE_PAYMENT, str(payment.pk))
        if row.get("channel") in RECEIPT_CHANNELS
    ]


def next_copy_no(deliveries: list[dict[str, Any]]) -> int:
    """The number the modal will submit — highest copy seen, plus one.

    ⚠ **IT IS A SUGGESTION THE SERVER MAKES, NOT A NUMBER THE SERVER TAKES.**
    The clerk's browser sends it back and `resend_receipt` uses what it is GIVEN.
    That round trip is the whole point: a double-click submits the same number
    twice and the second collides with its own row, whereas a server that
    allocated at write time would hand out 1 and then 2 and post two receipts.
    """
    highest = max((int(row.get("copy_no") or 0) for row in deliveries), default=0)
    return highest + 1


def _latest_on(deliveries: list[dict[str, Any]], channel: str) -> dict[str, Any] | None:
    rows = [row for row in deliveries if row.get("channel") == channel]
    if not rows:
        return None
    return max(rows, key=lambda row: int(row.get("copy_no") or 0))


def _channels_or_refuse(channels: Any) -> tuple[str, ...]:
    wanted = tuple(str(one).strip() for one in (channels or ()) if str(one).strip())
    if not wanted:
        raise PaymentRuleError(
            "no channel was chosen, so nothing was queued. A resend needs at least one way "
            "to reach the customer — the modal's *Send by* field is required.",
            br_ref="BR-PAY-024",
        )
    unknown = [one for one in wanted if one not in RECEIPT_CHANNELS]
    if unknown:
        raise PaymentRuleError(
            f"{', '.join(unknown)} is not a receipt channel. A receipt goes out on "
            f"{', '.join(RECEIPT_CHANNELS)} and on nothing else; a channel nothing writes is a "
            "receipt a clerk would believe had been sent.",
            br_ref="BR-PAY-024",
        )
    # De-duplicated, in the product's own order, so two identical entries in one
    # submit cannot ask the writer for the same key twice inside one transaction.
    return tuple(one for one in RECEIPT_CHANNELS if one in wanted)


def _copy_no_or_refuse(copy_no: Any) -> int:
    try:
        number = int(str(copy_no))
    except (TypeError, ValueError) as problem:
        raise PaymentRuleError(
            "a resend needs the copy number it is making. Without one this endpoint would "
            "allocate the next free number on every submit, and a double-click would post two "
            "receipts while looking perfectly correct (CLAUDE.md hard rule 6).",
            br_ref="BR-BIL-016",
        ) from problem
    if number < 1:
        raise PaymentRuleError(
            f"copy {number} is not a resend. Copy 0 is the delivery record the original send "
            "wrote (BR-BIL-016); re-queueing at 0 would collide with the receipt the customer "
            "already has rather than making them a new one.",
            br_ref="BR-BIL-016",
        )
    return number


def resend_receipt(
    *,
    actor: Any,
    payment: models.Payment,
    channels: Any,
    copy_no: Any,
) -> ResentReceipt:
    """`POST /payments/{id}/receipt` — the customer gets another copy.

    ⚠ **NOTHING ABOUT THE PAYMENT CHANGES**, which is the drawing's own
    reassurance (p049 ③) and p050's act table: *Resend · a queue row · the
    ledger: Nothing · what changes elsewhere: Nothing about the payment.* No
    column of `payments` is read for writing and no money function is called.
    """
    tenant_id = _tenant_id()
    wanted = _channels_or_refuse(channels)
    number = _copy_no_or_refuse(copy_no)
    deliveries = receipt_deliveries(payment)

    write = _resolve("queue_document", "services")
    pin_type = _resolve("TemplatePin", "services")
    recipient_type = _resolve("Recipient", "services")
    refusal_type = _resolve("QueueWriteRefused", "services")
    row_or_404 = _resolve("row_or_404", "selectors")
    decode = _resolve("decode_context", "rendering")
    if write is None or pin_type is None or recipient_type is None or row_or_404 is None:
        raise PaymentRuleError(  # pragma: no cover - published since W3
            "the platform outbound queue is not published on this deployment, so nothing "
            "could be re-queued. Reported rather than swallowed.",
            br_ref="BR-NOT-005",
        )

    queued: list[dict[str, Any]] = []
    problems: list[dict[str, Any]] = []
    for channel in wanted:
        previous = _latest_on(deliveries, channel)
        if previous is None:
            # ⚠ **RE-QUEUES AN EXISTING DOCUMENT** — the task's own words. With
            # no row on this channel there is nothing to copy: no pin, no
            # recipient snapshot, no figures. Queueing a fresh one here would be
            # this module composing a receipt, which is the second path the PO
            # ruled out.
            raise PaymentRuleError(
                f"this payment has no {channel} receipt to send again. A resend copies the "
                "document that went out — its pinned wording, its recipient and its figures — "
                "and there is none on that channel. A payment recorded while the utility had "
                "receipts switched off has no receipt to repeat (Settings → Notifications).",
                br_ref="BR-PAY-024",
            )
        if previous.get("held"):
            # BR-PAY-018 — that letter's address is already known to be wrong.
            raise PaymentRuleError(
                f"the {channel} receipt is HELD: the customer's own mail came back from that "
                f"address ({previous.get('held_reason') or 'address unusable'}). Sending it "
                "again is the one outcome the hold exists to prevent. Fix the address first.",
                br_ref="BR-PAY-018",
            )
        row = row_or_404(previous["id"])
        # ⚠ **A SAVEPOINT PER CHANNEL, AND IT IS NOT TIDINESS** (hard-won law
        # 14). On PostgreSQL one failed INSERT aborts the WHOLE transaction, so
        # a refusal on the second channel would take the first channel's row
        # down with it at COMMIT — green on the SQLite suite, lost in
        # production. `receipts._queue_one` makes the same argument for the
        # same reason one module along.
        try:
            with transaction.atomic():
                written = write(
                    source_type=row.source_type,
                    source_id=row.source_id,
                    channels=(row.channel,),
                    template=pin_type(
                        code=row.template_code,
                        template_id=row.template_id,
                        version=row.template_version,
                        language=row.template_language,
                    ),
                    account_id=row.account_id,
                    recipients=(
                        recipient_type(
                            channel=row.channel,
                            address=row.recipient_address,
                            snapshot=row.recipient_snapshot,
                            unavailable_reason=row.unavailable_reason,
                        ),
                    ),
                    copy_no=number,
                    actor=actor,
                    # ⚠ `DEF-NOT-4449` — THE FIGURES TRAVEL WITH THE COPY, and
                    # DECODED, because `queue_document` encodes on the way in.
                    # Hand the raw column back and a customer's receipt prints
                    # `{'__money__': '158.1000'}`.
                    render_context=(decode(row.render_context) or None) if decode else None,
                )
        except Exception as failure:  # noqa: BLE001 — the one boundary where broad is right
            refused = refusal_type is not None and isinstance(failure, refusal_type)
            problems.append(
                {
                    "code": RESEND_QUEUE_REFUSED if refused else RESEND_QUEUE_ERROR,
                    "br_ref": "BR-PAY-024",
                    "channel": channel,
                    "detail": f"the {channel} copy could not be queued: {failure}",
                }
            )
            continue
        messages = tuple(getattr(written, "messages", ()) or ())
        # ⚠ **THE MESSAGE FOR *THIS* CHANNEL, NEVER `messages[0]`** — `DEF-2473`.
        # BR-NOT-024's print floor means a write asking for email can come back
        # carrying a PRINT row, and reporting that as "queued by email" is a
        # false statement to a clerk.
        mine = next((one for one in messages if getattr(one, "channel", None) == channel), None)
        if mine is None:
            problems.extend(tuple(getattr(written, "problems", ()) or ()))
            continue
        queued.append(
            {
                "channel": channel,
                "message_id": str(getattr(mine, "id", "")) or None,
                "created": bool(getattr(mine, "created", False)),
            }
        )
        problems.extend(tuple(getattr(written, "problems", ()) or ()))

    # Hard rule 7. The trail names the copy and the channels, because *"did we
    # send that twice?"* is the question somebody asks three weeks later.
    core_audit.money_action(
        actor,
        AUDIT_RESENT,
        AUDIT_ENTITY,
        str(payment.pk),
        after={
            "copy_no": number,
            "channels": list(wanted),
            "queued": [one["channel"] for one in queued],
            "job": None if actor is not None else "payments.receipt_resend",
        },
    )
    problems.append(
        {
            "code": NOTHING_ABOUT_THE_PAYMENT_CHANGED,
            "br_ref": "BR-PAY-002",
            "detail": "a resend writes a queue row and nothing else — no money moved, no "
            "journal entry was made and no column of the payment changed.",
        }
    )
    _ = tenant_id  # the seam scopes its own reads; named so rule 1 is visible here
    return ResentReceipt(
        payment_id=str(payment.pk),
        payment_no=payment.payment_no,
        copy_no=number,
        queued=tuple(queued),
        problems=tuple(problems),
    )


# ── P3.19 · the receipt in hand, NOW ───────────────────────────────────────
def counter_receipt_document(*, actor: Any, payment: models.Payment) -> dict[str, Any]:
    """`GET /payments/{id}/receipt/document` — the paper, rendered, right now.

    A READ. Read the module docstring's P3.19 section before changing that:
    signed law forbids a synchronous SEND endpoint anywhere in this product, and
    this is not one — it renders a row that is already queued and dispatches
    nothing. The queued row keeps its place and the print job will still take it.

    Refuses by NAME when there is no printed receipt to show, because the two
    reasons a clerk meets are different and only one of them is fixable at the
    counter: the utility switched receipts off (Settings → Notifications), or
    the row is pinned to a template version that cannot be loaded (BR-BIL-026 —
    and re-rendering against today's published wording is the substitution that
    rule exists to forbid).
    """
    deliveries = receipt_deliveries(payment)
    printed = _latest_on(deliveries, CHANNEL_PRINT)
    if printed is None:
        raise PaymentRuleError(
            "there is no printed receipt for this payment. BR-NOT-024's print floor puts one "
            "on every recorded payment, so a payment with none was recorded while this "
            "utility had receipts switched off (Settings → Notifications). Nothing is "
            "rendered — a receipt composed here would be a second receipt path.",
            br_ref="BR-PAY-024",
        )
    row_or_404 = _resolve("row_or_404", "selectors")
    render = _resolve("render_for_dispatch", "rendering")
    refused_type = _resolve("RenderRefused", "rendering")
    if row_or_404 is None or render is None:  # pragma: no cover - published since W3
        raise PaymentRuleError(
            "the document renderer is not published on this deployment, so the receipt could "
            "not be produced. Reported rather than swallowed.",
            br_ref="BR-NOT-005",
        )
    row = row_or_404(printed["id"])
    try:
        artifact = render(row)
    except Exception as failure:  # noqa: BLE001 — a refusal and a fault are both answers
        if refused_type is not None and isinstance(failure, refused_type):
            raise PaymentRuleError(
                f"this receipt cannot be rendered: {failure}",
                br_ref="BR-BIL-026",
            ) from failure
        raise

    core_audit.money_action(
        actor,
        AUDIT_PRINTED,
        AUDIT_ENTITY,
        str(payment.pk),
        after={
            "channel": CHANNEL_PRINT,
            "copy_no": printed.get("copy_no"),
            "template_code": artifact.template_code,
            "template_version": artifact.template_version,
            "job": None if actor is not None else "payments.receipt_print",
        },
    )
    return {
        "payment_id": str(payment.pk),
        "payment_no": payment.payment_no,
        "channel": CHANNEL_PRINT,
        "copy_no": printed.get("copy_no"),
        "template_code": artifact.template_code,
        "template_version": artifact.template_version,
        "language": artifact.language,
        "subject": artifact.subject,
        # TEXT, not a PDF — `rendering.py` exception (2), OQ-149. The browser's
        # own print dialog is what puts it on paper.
        "body": artifact.body,
        # ⚠ Carried rather than hidden: a receipt printed with a token missing is
        # a fact the clerk holding it should be able to see (hard-won law 1).
        "absences": list(artifact.absences or ()),
        "problems": list(artifact.problems or ()),
        # It was already queued and it still is. Said plainly so nobody reads
        # this as a delivery.
        "queued_row_untouched": True,
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-137-BRC07 §3 P3.3 + P3.19 · 05-prototype/06 Payments Page Blueprint.pdf
#         2·3h p049–p050 (on this branch since `da07c7f8d`)
#         · 04-docs/01-spec/11-api-contracts.md Addendum r2 §4 (no synchronous
#         send endpoint) · apps/notifications/api.py (the resend discipline) ·
#         apps/payments/receipts.py (the three channels and the savepoint) ·
#         BR-PAY-024 · BR-NOT-005 · BR-NOT-013 · BR-NOT-024 · BR-BIL-016 ·
#         BR-BIL-026 · BR-PAY-018 · CLAUDE.md hard rules 6, 7 · hard-won law 14
# generated: 2026-09-23 by the CR-137 P3-BACK lane
# checklist: A✔ B=deferred(P3.11 owns the Resend modal) C✔ D✔ E=deferred(P3.11)
#            F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions:
#   E1 ⚠ **THIS READ *"the blueprint PDF is NOT on this branch"* WHILE THIS LANE
#      WAS BUILDING, AND IT IS NO LONGER TRUE.** It was true at the pinned tip and
#      the drawing was read from `origin/claude/confirm-understanding-3ktufc`;
#      `da07c7f8d` put it on THIS branch at `05-prototype/06 Payments Page
#      Blueprint.pdf`, 2,905,141 bytes, sha256 `0cc31baf…`, and the copy read here
#      is byte-identical to it. `DEF-PAY-6230` is CLOSED. Read it from the branch.
#   E2 the ~30 lines that build the `queue_document` call also live inside
#      `apps/notifications/api.outbound_resend`. NOT extracted here:
#      `delivery_ops.py` is on `human_owned.txt` and the extraction is
#      notifications' 🔒 change to make. FILED as `DEF-PAY-6231`.
#   E3 P3.19 is a **GET that renders**, never a send. A11 r2 §4 forbids a
#      synchronous send endpoint anywhere and this mints none — the queued row
#      is untouched and the print job still takes it. The reasoning is in
#      `12-governance/02-decision-log.md`, 2026-09-23, because the drawing does
#      not settle it.
#   E4 the receipt is TEXT and not a PDF — `rendering.py` exception (2),
#      `OQ-149` CLOSED 2026-08-12. The browser prints it.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
