# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-017 (the service-request register) × US-NOT-001 (the queue)
#           Screens: the request's own screen, blueprint entry 06 drawings
#           8–11 (p082–p086)
# Rules:    BR-CUS-079 (an applicant is acknowledged on submission) ·
#           BR-CUS-090 clause (3) (the acknowledgement may not say *nothing is
#           charged* when money was taken) · BR-NOT-005 (queue only — nothing
#           here sends) · BR-NOT-013 (no delivery adapter on any channel) ·
#           BR-NOT-024 (the print floor, and why this kind is not on it) ·
#           BR-NOT-006 (the pin carries the language variant) · BR-TEN-017
#           (the recipient is snapshotted at queue time) · BR-TEN-043 (no wall
#           clock) · CLAUDE.md rule 1 (tenant scoping) · rule 6 (idempotency)
# Change:   CR-094-BRC01 — `DEF-CUS-5389`, and the absence the request's own
#           History tab printed at a clerk: *"'service_request' is not a source
#           kind this platform queues … a row nothing recognises is a message
#           nothing will ever send."*
# Tests:    06-backend/tests/test_cr094_service_request_messages.py
# Impacts:  apps/customers/notifications_seam.py (the ONLY caller — customers
#           resolves this module BY NAME and never imports it) ·
#           apps/notifications/models.py SOURCE_TYPES (`service_request`) ·
#           apps/notifications/catalogs.py (the four classes) ·
#           apps/notifications/seed_templates.py (the four bodies) ·
#           06-backend/tests/test_cr048_print_floor.py (the classification)
# ───────────────────────────────────────────────────────
"""The four things a service request says to the person who raised it.

╔══════════════════════════════════════════════════════════════════════════╗
║  WHAT THIS IS FOR, in one sentence a clerk would recognise:              ║
║  somebody applies for service and hears back — *we have your request*,   ║
║  *we need one more thing from you*, *we are going ahead*, or *we cannot  ║
║  go ahead, and here is why*.                                             ║
╚══════════════════════════════════════════════════════════════════════════╝

Before this file, **nothing the product did with a service request ever reached
the applicant.** The acknowledgement was written, wired and called on every
submission since CR-031, and every call ended in the same refusal, because
`service_request` was not one of the thirteen source kinds the platform queued.
The request's own History tab printed that refusal at a clerk, in those words.

────────────────────────────────────────────────────────────────────────────
THE RECIPIENT IS NOT A CUSTOMER, AND EVERYTHING ELSE HERE FOLLOWS FROM THAT
────────────────────────────────────────────────────────────────────────────
An APPLICANT holds no account, no customer row and no `contacts` record, so
`services._recipients_for`'s published customer read has nothing to look up —
it would answer `recipient_not_resolvable` for every channel and write rows
addressed to nobody. **The caller wins**, which that function says in as many
words, so the address travels IN: `apps/customers` holds `applicant_email` on
the request, and this module turns it into a `Recipient` and lets the queue
snapshot it (BR-TEN-017). `account_id` stays NULL, which the column has allowed
since it was written for the staff-addressed report rows.

────────────────────────────────────────────────────────────────────────────
EMAIL ONLY, AND SAYING SO IS BETTER THAN QUEUEING A LETTER INTO A TEXT MESSAGE
────────────────────────────────────────────────────────────────────────────
All five classes are EMAIL classes. `queue_document` writes one row per channel
from ONE pin, so naming `sms` beside `email` would put a five-paragraph letter
into a channel CR-007 counts to 160 characters. An applicant who left a phone
number and no email therefore gets nothing, and the caller records WHY rather
than recording a message that does not exist. Writing SMS wording for these
occasions is real work with its own 160-character budget; it is named as
absent instead of faked.

⚠ **AND THAT IS WHY p081's *'A text never replaces a posted notice'* IS A
GUARD AND NOT A DESCRIPTION.** The drawing shows the decision row going by
`Email · SMS`, the SMS riding alongside the letter and never instead of it.
This product has no SMS wording for any of these, so the courtesy half is
ABSENT rather than faked — and `applicant_templates` marks any variant a tenant
publishes on a channel that is not writing as unpickable for that row, so the
absence cannot quietly become a substitution.

────────────────────────────────────────────────────────────────────────────
THE IDEMPOTENCY KEY, AND WHY IT IS NOT THE REQUEST FOR ALL FOUR
────────────────────────────────────────────────────────────────────────────
The queue's key is (tenant, source_type, source_id, channel, copy_no).

  * **The acknowledgement keys on the SERVICE REQUEST.** A request is
    acknowledged exactly once, `submit` is idempotent, and a double-clicked
    submit must find the row already there and write nothing. That is rule 6
    with the request itself as the key, which is what `submit`'s own docstring
    already says it is.
  * **The approval letter keys on the SERVICE REQUEST too**, for the same
    reason read the other way round: a request is approved once and approval is
    terminal for the application, so *"approving twice queues one, not two"* is
    a property of the key rather than of a caller remembering.
  * **The refusal letter and the ask-for-more message key on the
    `service_request_events` ROW that records the act** — the `move` precedent,
    where a job record that already exists is the key.

Keying all three on the request would be `move`'s documented trap one kind up: a
request asked for more twice, or refused, reopened and refused again, would meet
the unique key on the second message, `queue_document` would report
`created=False`, the clerk would be told it was queued, and **the applicant
would be sent the first letter's contents and never the second's.** Nothing
about that looks like a failure — there is a row, it is just the wrong message.

────────────────────────────────────────────────────────────────────────────
NO EVENT KEY, DELIBERATELY — AND IT IS NOT THE SAME REASON FOR ALL THREE
────────────────────────────────────────────────────────────────────────────
`queue_document`'s `event_key` is what lets a utility switch a class of
automatic message off on Settings → Notifications. None of these four passes
one:

  * the refusal and the ask are a CLERK pressing a button, which is
    `queue_account_message`'s argument verbatim — a rule that silently swallowed
    it would leave the clerk believing they had written to an applicant when
    nothing was written;
  * the acknowledgement is automatic, and it is a RULED OBLIGATION rather than a
    courtesy: `BR-CUS-079`, CONFIRMED by the PO — *"when you take and submit SR
    - we have to send email or text messge to customer"*. A switch would let a
    utility turn off a rule they signed;
  * the approval letter is switched by the request's OWN drawn tick
    (`service_request_messages`, `BR-CUS-1076`), which is a per-request answer
    a clerk gave at the counter and not a per-tenant rule — two switches over
    one message is how a clerk ends up unable to say why nothing went.

If a utility asks for the acknowledgement to be switchable, that is a
`BR-CUS-079` question for the PO and a new row in `rule_catalog.EVENTS` — never
a keyword quietly added here.

────────────────────────────────────────────────────────────────────────────
NOTHING HERE SENDS, AND NOTHING HERE DECIDES A FACT
────────────────────────────────────────────────────────────────────────────
Every function writes ONE queue row set and returns. `BR-NOT-013` — no provider
adapter exists on any channel — so a real deployment delivers these the day an
adapter is plugged in, to the address in `outbound_messages.recipient_address`,
which is the applicant's own email as they typed it on the request. Every merge
value is a fact the caller already holds, and this module reads no clock.

⚠ **AMENDED 2026-10-22 — `DEF-CUS-10445`, ONE LOOKUP, AND ONLY TO FILL A GAP.**
This paragraph read *"this module looks nothing up"*. A request raised for
somebody who already holds an account may carry no typed applicant name; the
ruling of that day says the name and address then come from the account holder
*"via the shared customer-details builder"*. So a caller may pass `account_id`,
and `customer_context.customer_context` fills ONLY a name or an address the
caller left blank — the caller's own facts always win. The address the caller
holds travels as PARTS (`service_address_parts`, the same
`{line1, unit_label, city, state, postal_code}` shape the builder composes for
every customer letter), so an acknowledgement and a welcome write one address
the same way: `1408 Elm St · A, Austin, TX 78704`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from apps.notifications import catalogs, models, services
from apps.notifications import template_models as tm
from core import errors
from core import tenancy as core_tenancy

#: The SOURCE KIND all three messages ride. Added to `models.SOURCE_TYPES` on
#: 2026-09-15 and classified in the print-floor test's `NOT_A_DOCUMENT_KINDS` in
#: the same commit — the second edit that gets forgotten.
SOURCE_SERVICE_REQUEST = "service_request"

#: The four classes. Two acknowledgements, because `BR-CUS-090` clause (3)
#: cannot be satisfied by one body that has no conditional in it.
TEMPLATE_ACKNOWLEDGEMENT = "service_request_acknowledgement"
TEMPLATE_ACKNOWLEDGEMENT_FEE = "service_request_acknowledgement_fee"
TEMPLATE_REFUSED = "service_request_refused"
TEMPLATE_MORE_INFO = "service_request_more_info"
#: ⚠ THE FIFTH CLASS · 2026-09-15 · `CR-094-BRC01` lane J. The drawn row five
#: of `What goes out to the applicant` fires *"On approve or refuse"* and only
#: the refuse half of it had wording, so the one decision an applicant wants to
#: hear about was the one nothing told them.
#:
#: ⚠ **IT IS A SEPARATE CLASS AND NOT A CONDITIONAL IN THE REFUSAL, FOR THE
#: REASON THE ACKNOWLEDGEMENT IS TWO CLASSES:** a template body has no
#: conditional in it. *"We are going ahead"* and *"We are not able to go ahead"*
#: are two letters, and the refusal additionally makes the clerk's own sentence
#: MANDATORY content while an approval has no such box drawn anywhere.
TEMPLATE_APPROVED = "service_request_approved"

#: The two classes the decision row may pin, in the order the picker lists them.
DECISION_TEMPLATES: tuple[str, ...] = (TEMPLATE_APPROVED, TEMPLATE_REFUSED)

#: The one channel these classes are written for. See the module docstring.
APPLICANT_CHANNEL = models.CHANNEL_EMAIL


class ApplicantMessageRefused(Exception):
    """What a human can act on: no address, or an empty message.

    Its own type rather than `customer_events.MoveMessageRefused` because the
    two modules answer different callers and a seam that caught one type for
    both would catch a move's refusal on a service request's failure path.
    """


@dataclass(frozen=True)
class ApplicantMessage:
    """One queued message, as the caller needs to report it.

    `message_id` is NULL when the utility's rule left no channel — which cannot
    happen today (no event key is passed, so no rule is read) but is the shape
    every other writer in this module returns, and a caller that assumed a row
    would be the thing that broke when it can.
    """

    template_code: str
    source_id: str
    message_id: str | None
    created: bool
    channels: tuple[str, ...]
    #: The address the queue snapshotted, so a caller can say WHERE a real
    #: deployment would send this rather than only that it was queued.
    address: str | None
    problems: tuple[dict[str, Any], ...]


def _tenant_id() -> Any:
    """Hard rule 1: no tenant table is touched without `app.tenant_id` set.

    The same refusal `template_service` raises, for the same reason: the test
    database is SQLite and has no RLS at all, so a queryset that leaned on the
    policy would pass the whole suite.
    """
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _pin(template_code: str, override_template_id: Any, language: str | None) -> Any:
    """The class, or the EXACT variant a clerk picked at capture.

    ⚠ **A PICK IS AN OVERRIDE, AND `BR-BIL-025` ALREADY HAS THAT WORD.** The
    rule's order is *account override → exact (category, language) → language
    fallback → category fallback → the mandatory default*, and p081 draws the
    same shape on this screen: *"A template resolves on three axes and falls
    back on two."* So a clerk who picked a specific row on the drawn picker
    travels as `override_template_id` through the resolver every other document
    in this product uses, rather than through a second mechanism written here.

    ⚠ **AND THIS IS WHERE p081's DRAFT RULE BITES.** *"The draft version is
    listed and cannot be picked."* `resolve` returns PUBLISHED versions only
    (`BR-BIL-027`), and an override pointing at a variant with no published
    version raises rather than falling through to a default — so a pick that
    has since been unpublished REFUSES, loudly, instead of quietly sending
    different wording than the clerk chose.

    ⚠ **AN OVERRIDE FOR A DIFFERENT CLASS IS IGNORED, NOT OBEYED, AND THE
    REASON IS A LETTER GOING TO THE WRONG PERSON'S EXPECTATION.** `resolve`
    honours an override outright and reads the CODE off the override row, so a
    pick made on the decision line — where the clerk chose before anybody knew
    whether it would be approved or refused — would otherwise pin *"we are not
    able to go ahead"* onto an approval. The class is the OUTCOME's to decide;
    the pick is a choice of variant within it. When the two disagree the pick
    stands down, and the row records BOTH, so `template_code` (what was picked)
    and `fired_template_code` (what rendered) differ visibly rather than one
    silently becoming the other.

    With no override this returns a bare code pin and `services._pinned`
    resolves it exactly as it always has.
    """
    if override_template_id is None:
        return services.TemplatePin(code=template_code)
    from apps.notifications import template_service

    picked = tm.NotificationTemplate.objects.filter(
        tenant_id=_tenant_id(), pk=override_template_id
    ).first()
    if picked is not None and picked.code != template_code:
        return services.TemplatePin(code=template_code)
    try:
        resolved = template_service.resolve(
            code=template_code,
            language=language,
            override_template_id=override_template_id,
        )
    except template_service.TemplateRefused as unresolved:
        raise ApplicantMessageRefused(
            f"the wording picked for this message cannot be used: {unresolved} Nothing is "
            "sent from a draft and nothing falls back past a pick somebody made on "
            "purpose, so the decision stands and this message is not queued."
        ) from unresolved
    return services.TemplatePin(
        code=template_code,
        template_id=resolved.template_id,
        version=resolved.version,
        language=resolved.language,
    )


def _applicant_facts(
    *,
    applicant_name: str | None,
    service_address: str | None,
    service_address_parts: dict[str, Any] | None,
    account_id: Any,
) -> tuple[str | None, str | None]:
    """The name and address a letter is for — the caller's, then the account's.

    `DEF-CUS-10445`. The PARTS win over the caller's one-line string, because
    the parts are composed by the one builder every customer letter uses
    (`customer_context.service_address_line`); the string is what an older
    caller still sends. Only a value still blank after both is asked of the
    account holder, and only when the caller named an account.
    """
    from apps.notifications import customer_context

    name = (applicant_name or "").strip() or None
    line = customer_context.service_address_line(service_address_parts) or (
        (service_address or "").strip() or None
    )
    if account_id not in (None, "") and (name is None or line is None):
        holder = customer_context.customer_context(account_id)
        name = name or holder.get("customer_name")
        line = line or holder.get("service_address")
    return name, line


def _queue(
    *,
    template_code: str,
    source_id: Any,
    applicant_email: str | None,
    applicant_name: str | None,
    request_no: str | None,
    service_address: str | None,
    extra_context: dict[str, Any],
    actor: Any,
    job: str,
    language: str | None,
    on_date: date | None,
    override_template_id: Any = None,
    preferred_language: str | None = None,
    service_address_parts: dict[str, Any] | None = None,
    account_id: Any = None,
) -> ApplicantMessage:
    """One message, one channel, one row. Raises only what a human can repair."""
    from apps.notifications import message_language

    applicant_name, service_address = _applicant_facts(
        applicant_name=applicant_name,
        service_address=service_address,
        service_address_parts=service_address_parts,
        account_id=account_id,
    )
    address = (applicant_email or "").strip()
    if not address:
        raise ApplicantMessageRefused(
            "this applicant gave no email address, so there is nowhere to send the "
            "message. All five service-request classes are email classes — an SMS "
            "carries 160 characters and none of these letters has been written for "
            "one — so a phone number alone cannot be used here."
        )
    write = services.queue_document(
        source_type=SOURCE_SERVICE_REQUEST,
        source_id=source_id,
        channels=(APPLICANT_CHANNEL,),
        template=_pin(template_code, override_template_id, language),
        # NULL on purpose: an applicant has no account. The column has been
        # nullable since the staff-addressed report rows were written.
        account_id=None,
        recipients=(
            services.Recipient(
                channel=APPLICANT_CHANNEL,
                address=address,
                snapshot={"name": applicant_name or "", "request_no": request_no or ""},
            ),
        ),
        render_context={
            "applicant_name": applicant_name or "",
            "request_no": request_no or "",
            "service_address": service_address or "",
            **extra_context,
        },
        actor=actor,
        job=job,
        # `language` is the utility's default and the FALLBACK; the applicant's
        # own stated language is asked first (PO option B, 2026-10-29,
        # superseding `OQ-CUS-12619` (a) for messages). `account_id` is None on
        # the row on purpose, so the language an applicant stated on the
        # request is passed explicitly — and, where none was stated but the
        # request already names an account, the account's is read.
        language=language,
        preferred_language=preferred_language or message_language.account_language(account_id),
        on_date=on_date,
        # NO `event_key`. See the module docstring — and it is not the same
        # reason for the clerk's two messages as for the acknowledgement.
    )
    message = write.messages[0] if write.messages else None
    return ApplicantMessage(
        template_code=template_code,
        source_id=str(source_id),
        message_id=str(message.id) if message is not None else None,
        created=bool(message.created) if message is not None else False,
        channels=tuple(item.channel for item in write.messages),
        address=address if message is not None else None,
        problems=tuple(write.problems),
    )


def queue_request_acknowledgement(
    *,
    request_id: Any,
    request_no: str | None,
    applicant_name: str | None,
    applicant_email: str | None,
    service_address: str | None,
    fee_amount: Any = None,
    fee_method: str | None = None,
    receipt_no: str | None = None,
    fee_currency: str | None = None,
    actor: Any = None,
    job: str | None = None,
    language: str | None = None,
    preferred_language: str | None = None,
    on_date: date | None = None,
    service_type: str | None = None,
    target_date: date | None = None,
    service_address_parts: dict[str, Any] | None = None,
    account_id: Any = None,
) -> ApplicantMessage:
    """`BR-CUS-079`'s acknowledgement, keyed on the request itself.

    ⊕ **`DEF-CUS-10445` (PO 2026-10-22).** Both classes also carry
    `{service_type}` — the requested services' names, as the caller read them
    from Settings → Services — and `{target_date}` — a DATE, which the renderer
    writes in the utility's Regional format. The caller decides both (the
    preferred date, or the request date plus the utility's
    `service_request_default_target_days`); this module only carries them.

    ⚠ **WHICH OF THE TWO CLASSES IS PINNED IS DECIDED BY WHETHER A RECEIPT
    EXISTS, AND THAT IS `BR-CUS-090` CLAUSE (3) MADE UNREACHABLE-BY-CONSTRUCTION
    RATHER THAN REMEMBERED.** The ruling: *"THE ACKNOWLEDGEMENT MAY NOT SAY
    'Nothing is charged' WHEN MONEY WAS TAKEN … It is the FIRST thing an
    applicant receives and it is customer-facing, so a false sentence there is a
    money defect, not a copy nit."* A template body has no conditional, so one
    class could only ever carry one of the two sentences. Passing a receipt
    number pins the class whose body states the amount, the method and the
    receipt; passing none pins the class whose body says nothing is charged.

    ⚠ **AMENDED 2026-10-22 — `CR-190-BRC10`, PO: *"Callers pass money as a
    value plus currency, never a pre-formatted string"*.** `fee_amount` used to
    arrive as a string the caller had written as `25.00 USD`. It now arrives as
    a `Decimal` with `fee_currency`, and is handed to the renderer as
    `rendering.Money`, which writes `$25.00` in the utility's region (B4 ❄
    rounding unchanged). A string from an old caller is still parsed, never
    printed raw.
    """
    from decimal import Decimal, InvalidOperation

    from apps.notifications import rendering

    def money(value: Any) -> Any:
        if value in (None, ""):
            return None
        if isinstance(value, rendering.Money):
            return value
        try:
            figure = value if isinstance(value, Decimal) else Decimal(str(value).split()[0])
        except (InvalidOperation, IndexError, TypeError, ValueError):
            return None
        return rendering.Money(figure, fee_currency)

    facts = {"service_type": (service_type or "").strip() or None, "target_date": target_date}
    if receipt_no:
        template_code = TEMPLATE_ACKNOWLEDGEMENT_FEE
        extra = {
            "fee_amount": money(fee_amount),
            "fee_method": fee_method or "",
            "receipt_no": receipt_no,
            **facts,
        }
    else:
        template_code = TEMPLATE_ACKNOWLEDGEMENT
        extra = dict(facts)
    return _queue(
        template_code=template_code,
        source_id=request_id,
        applicant_email=applicant_email,
        applicant_name=applicant_name,
        request_no=request_no,
        service_address=service_address,
        extra_context=extra,
        actor=actor,
        job=job or "customers.service_request_submit",
        language=language,
        preferred_language=preferred_language,
        on_date=on_date,
        service_address_parts=service_address_parts,
        account_id=account_id,
    )


def queue_request_refused(
    *,
    occasion_id: Any,
    request_no: str | None,
    applicant_name: str | None,
    applicant_email: str | None,
    service_address: str | None,
    message_body: str,
    actor: Any = None,
    job: str | None = None,
    language: str | None = None,
    preferred_language: str | None = None,
    on_date: date | None = None,
) -> ApplicantMessage:
    """The refusal letter the blueprint's Refuse dialog promises.

    `occasion_id` is the `service_request_events` row recording the refusal —
    never the request, so a request refused, reopened and refused again sends
    two letters rather than silently deduping into the first.

    `message_body` is the clerk's own `What to tell them` text, whose helper
    line on the drawing reads *Goes into the refusal letter.* It is REQUIRED
    here: `catalogs` makes `{message_body}` mandatory content on this class, so
    an empty one would queue a letter with a hole where the reason should be.
    The five refusal REASONS are not passed and are not in the palette — they
    are what the utility files the refusal under, not what the applicant is
    told.
    """
    if not (message_body or "").strip():
        raise ApplicantMessageRefused(
            "a refusal letter with nothing in it tells an applicant no and nothing "
            "about why. The blueprint's Refuse dialog carries a `What to tell them` "
            "box for exactly this sentence, and this class makes it mandatory content."
        )
    return _queue(
        template_code=TEMPLATE_REFUSED,
        source_id=occasion_id,
        applicant_email=applicant_email,
        applicant_name=applicant_name,
        request_no=request_no,
        service_address=service_address,
        extra_context={"message_body": message_body},
        actor=actor,
        job=job or "customers.service_request_refuse",
        language=language,
        preferred_language=preferred_language,
        on_date=on_date,
    )


def queue_request_more_info(
    *,
    occasion_id: Any,
    request_no: str | None,
    applicant_name: str | None,
    applicant_email: str | None,
    service_address: str | None,
    message_body: str,
    actor: Any = None,
    job: str | None = None,
    language: str | None = None,
    preferred_language: str | None = None,
    on_date: date | None = None,
) -> ApplicantMessage:
    """The message the blueprint's Ask-for-more dialog promises.

    ⚠ **THIS REPLACES ONE FIXED SENTENCE SENT TO EVERY APPLICANT ALIKE.** Until
    this file, asking for more put *"More information is needed before this can
    be reviewed."* on the timeline, the same words on every request in the
    product, and put nothing at all in front of the applicant. A clerk could not
    say what was actually needed.

    `occasion_id` is the `service_request_events` row recording the ask. A
    request can be asked for more, answered and asked again; each ask is its own
    row and therefore its own message.

    The tick list drawn above the message box is NOT sent — see the class note
    in `catalogs`. It is the clerk's checklist, stored on the request and kept
    on its history.
    """
    if not (message_body or "").strip():
        raise ApplicantMessageRefused(
            "an ask with no message is the fixed sentence this replaced. The "
            "blueprint's dialog carries a `Message to the applicant` box whose helper "
            "line reads *Sent to them and kept on the request's history.* — the "
            "clerk's own words are the ask."
        )
    return _queue(
        template_code=TEMPLATE_MORE_INFO,
        source_id=occasion_id,
        applicant_email=applicant_email,
        applicant_name=applicant_name,
        request_no=request_no,
        service_address=service_address,
        extra_context={"message_body": message_body},
        actor=actor,
        job=job or "customers.service_request_more_info",
        language=language,
        preferred_language=preferred_language,
        on_date=on_date,
    )


def queue_request_approved(
    *,
    occasion_id: Any,
    request_no: str | None,
    applicant_name: str | None,
    applicant_email: str | None,
    service_address: str | None,
    override_template_id: Any = None,
    actor: Any = None,
    job: str | None = None,
    language: str | None = None,
    preferred_language: str | None = None,
    on_date: date | None = None,
) -> ApplicantMessage:
    """The letter an applicant gets when their request is APPROVED.

    ⚠ **THIS IS THE HALF THAT NEVER EXISTED, AND IT IS THE PO'S OWN QUESTION**
    of 2026-09-15 about the approval modal: *"at the time of approval we are
    also linking notification and templates to the modal - are you ensuring it
    will work?"* It did not. The blueprint's step-6 block draws row five firing
    *"On approve or refuse"*; refusing has queued a letter since `BR-CUS-1075`,
    and approving queued nothing at all — so somebody could apply for service,
    be approved, and never hear a word.

    ⚠ **`occasion_id` IS THE TIMELINE ROW RECORDING THE APPROVAL, NOT THE
    REQUEST — AND THE FIRST DRAFT OF THIS LANE GOT THAT WRONG AND THE TEST
    CAUGHT IT (2026-09-15).** Keying on the request looked right, because a
    request is approved once. But **the ACKNOWLEDGEMENT already keys on the
    request**, and the queue's key is (tenant, source kind, source id, channel,
    copy no) — so the approval letter met the acknowledgement's own row,
    `queue_document` reported `created=False`, the clerk was told it was queued,
    and **the applicant would have been sent *"we have your request"* on the day
    they were approved.** That is the trap this module's docstring already warns
    about for the ask, one occasion further along, and nothing about it looks
    like a failure: there is a row, it is just the wrong letter.

    So all three of the clerk-visible letters key on the act's own append-only
    timeline row, and *"approving twice queues one, not two"* is carried by
    `service_request_messages.fired_at` — a row that has gone is never written
    a second time, so a second message is never even attempted.

    ⚠ **THERE IS NO CLERK MESSAGE BOX ON THE APPROVE MODAL** and this class
    therefore carries no `{message_body}`. The drawing gives the clerk a
    `What to tell them` box on REFUSE alone, and inventing one here would be
    inventing a control. What the applicant reads is the utility's own published
    wording and their own request number.

    `override_template_id` is the variant the clerk picked on the drawn
    template picker, if they picked one — see `_pin`.
    """
    return _queue(
        template_code=TEMPLATE_APPROVED,
        source_id=occasion_id,
        applicant_email=applicant_email,
        applicant_name=applicant_name,
        request_no=request_no,
        service_address=service_address,
        extra_context={},
        actor=actor,
        job=job or "customers.service_request_approve",
        language=language,
        preferred_language=preferred_language,
        on_date=on_date,
        override_template_id=override_template_id,
    )


def queue_request_extra_message(
    *,
    message_id: Any,
    template_code: str,
    to_address: str | None,
    request_no: str | None,
    applicant_name: str | None,
    service_address: str | None,
    actor: Any = None,
    job: str | None = None,
    language: str | None = None,
    preferred_language: str | None = None,
    on_date: date | None = None,
    service_type: str | None = None,
    target_date: date | None = None,
    service_address_parts: dict[str, Any] | None = None,
    account_id: Any = None,
) -> ApplicantMessage:
    """A message a CLERK added to a request (`DEF-CUS-10042`, PO 2026-10-11).

    Keyed on the added row's own id, so a replayed submit or decision finds its
    own queue row and writes nothing, and two added rows with the same wording
    are two messages. The wording is whichever published template the clerk
    picked, resolved through the same pin every other letter here uses.

    ⊕ `DEF-CUS-10445` — the picker lists the acknowledgement class too, so an
    added message carries the same `{service_type}` and `{target_date}` the
    acknowledgement does; a class whose palette lacks them never reads them.
    """
    return _queue(
        template_code=template_code,
        source_id=message_id,
        applicant_email=to_address,
        applicant_name=applicant_name,
        request_no=request_no,
        service_address=service_address,
        extra_context={
            "service_type": (service_type or "").strip() or None,
            "target_date": target_date,
        },
        actor=actor,
        job=job or "customers.service_request_extra_message",
        language=language,
        preferred_language=preferred_language,
        on_date=on_date,
        service_address_parts=service_address_parts,
        account_id=account_id,
    )


# ═══════════════════════════════════════════════════════════════════════════
# THE PICKER'S READ — `Choosing a template` (p080, read as an image)
# ═══════════════════════════════════════════════════════════════════════════
#: Which channels count as *in writing* for p081's rule *"A text never replaces
#: a posted notice."* A printed notice and an email both leave a document
#: somebody can keep and re-read; a text does not, and that is the whole
#: distinction the rule draws. `pdf_print` is this product's spelling of a
#: posted notice (`models.CHANNEL_PRINT`).
WRITING_CHANNELS: tuple[str, ...] = (models.CHANNEL_EMAIL, models.CHANNEL_PRINT)


def applicant_templates(
    *, codes: tuple[str, ...] = (), search: str | None = None
) -> tuple[dict[str, Any], ...]:
    """Every published or draft VARIANT of the given classes, as the picker lists it.

    The drawn columns are `TEMPLATE · GROUP · CHANNEL · VARIANT · VERSION` with
    a radio per row, so one row here is one VARIANT of one class — the
    `(category, language)` pair `BR-BIL-025` resolves on — carrying its live
    version number and status.

    ⚠ **A DRAFT IS RETURNED, NOT FILTERED OUT.** p081, read as an image: *"The
    draft version is listed and cannot be picked. Hiding it sends a clerk
    looking for something they can see exists; offering it would queue a letter
    nobody has approved."* So the row travels with `pickable: false` and the
    reason, and the decision about what to do with it belongs to the screen —
    which must show it.

    ⚠ **`search` MATCHES THE NAME A HUMAN GAVE IT**, which is the search box's
    own helper line on the drawing, and never the class code: B14 rule 31 keeps
    a database value off a screen, so a clerk cannot be expected to search by
    one.

    ⚠ **NO ROW CARRIES A BODY.** The picker chooses wording, it does not preview
    it, and a body is customer-facing copy that would then need translating for
    a screen that only renders a name.
    """
    tenant_id = _tenant_id()
    wanted = tuple(codes) or tuple(
        code for code in catalogs.known_template_codes() if code.startswith("service_request_")
    )
    rows: list[dict[str, Any]] = []
    for template in tm.NotificationTemplate.objects.filter(
        tenant_id=tenant_id, code__in=wanted
    ).order_by("code", "category", "language"):
        if search and search.strip().lower() not in (template.name or "").lower():
            continue
        version = (
            tm.NotificationTemplateVersion.objects.filter(
                tenant_id=tenant_id, template_id=template.pk
            )
            .order_by("-version")
            .first()
        )
        if version is None:
            # A variant nobody has written a word of. Not listed: the rule is
            # about a DRAFT being visible, and a template with no version at all
            # is not a draft, it is an empty row.
            continue
        published = version.status == tm.VERSION_PUBLISHED
        writing = template.channel in WRITING_CHANNELS
        rows.append(
            {
                "template_id": str(template.pk),
                "code": template.code,
                #: The tenant-facing NAME — *Service request approved* — never
                #: the code (B14 rule 31).
                "name": template.name,
                "group": template.group,
                "channel": template.channel,
                #: The drawn `VARIANT` column is this pair, which the screen
                #: renders as *Default · English* in its own catalogue.
                "category": template.category,
                "language": template.language,
                "version": version.version,
                "status": version.status,
                "pickable": published,
                "not_pickable_reason": None if published else "nobody_has_published_this_version",
                "is_writing": writing,
            }
        )
    return tuple(rows)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-094-BRC01 · DEF-CUS-5389 (12-governance/11-change-requests.md → CR-094-BRC01 · 05-prototype/02 Accounts Menu Blueprint.pdf entry 06 drawings 10 and 11, read as images at scale 2 and 4 · apps/notifications/models.py SOURCE_TYPES · apps/notifications/catalogs.py (the four classes) · apps/notifications/seed_templates.py (the four bodies) · apps/customers/notifications_seam.py (the only caller) · apps/customers/service_request_service.py (the three moments) · CLAUDE.md hard rule 7 · hard-won law 14)
# generated: 2026-09-15 by story-coder (CR-094-BRC01 lane C)
# checklist: A✔ B=deferred(no frontend half — wave 2 draws the two modals; the payload and its worked example are published in this wave's conformance file) C✔ D=deferred(no HTTP surface of its own — reached through the existing submit, refuse and transitions endpoints) E=deferred(as B) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest under PostgreSQL — RED PROVED FIRST: a refusal on the demo tenant queued ZERO rows and the request's own History tab printed the refusal `'service_request' is not a source kind this platform queues`; quoted in the lane report.
# exceptions: (1) NOTHING SENDS — every message is a `queue_document` write (BR-NOT-005) and no adapter exists on any channel (BR-NOT-013). (2) EMAIL ONLY — an applicant with a phone and no email gets nothing, recorded as a named absence rather than an SMS rendered from an email body. (3) NO PRINT FLOOR — this product holds no mailing address for an applicant, and the commonest drawn refusal reason is *Not our service area*. (4) NO EVENT KEY on any of the three, for two different reasons, both in the module docstring.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
