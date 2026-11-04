# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-041 (EP-INT-11) — the partner surface reads payments.
#           CR-069 §11: one seam file per module integrations reads from.
# Rules:    BR-INT-054 (integrations LANDS and HANDS OVER; it does not
#           interpret — so this seam returns our columns and computes nothing)
#           · CLAUDE.md hard rule 1 (the read runs under the request's tenant
#           context; there is no tenant argument to point elsewhere) ·
#           hard rule 2 (money stored to 4 decimals, DISPLAYED to 2)
# Tests:    06-backend/tests/test_us_int_041_partner_surface.py
# Impacts:  apps/integrations/partner_api.py
# ───────────────────────────────────────────────────────
"""integrations → payments: the payments a partner may collect, as we hold them.

READ-ONLY UNTIL WAVE N, AND STILL WRITING NOTHING ITSELF
---------------------------------------------------------
⚠ **AMENDED 2026-09-06 (wave N, `US-INT-044`). THIS SECTION SAID *"there is no
function in this file that saves anything"* AND THAT IS NO LONGER TRUE OF THE
FILE, THOUGH IT IS STILL TRUE OF THE MODULE.** `land_inbound_delivery()` at
the foot of this file lands the raw envelope a kiosk posts to us. It performs
no ORM write of its own: it calls `apps.payments.webhooks.land_delivery`,
which is payments' own code writing payments' own table, exactly as `B2` §2
and the module map require. The seam is the ADDRESS, not the writer — which is
the same discipline `billing/payments_seam.py` and `billing/posting_seam.py`
already keep in the other direction.

**What integrations still may not do is unchanged and is the important half:
it does not RECORD A PAYMENT.** `record_payment` with channel `KIOSK`, the
reversal row a return produces, `DRIVEUP → OTHER` and the clerk-visible risk
flag are all Runbooks' (`BR-INT-058`, `CR-069` §20.4 wave N, `OQ-INT-1729`
ruled option (a) on 2026-09-06). The door lands what arrived and stops.

A partner READING from us still has nothing to write, and the three read
functions above are untouched.

WHY THE SHAPE IS SO PLAIN
--------------------------
Four fields — our receipt number, the day it posted, the amount, the currency.
No tender name in the partner's vocabulary, no project type, no account string.
`BR-INT-054` and `CR-069` §20.4 put all three of those in Runbooks: turning our
*Bank transfer* into their `ACHCHECK` is the ETL lookup, and building a business
record for somebody else is outbound ETL. `runners/serve.partner_fields()` is
the seam they arrive through when Runbooks lands, and it returns nothing today.

⚠ **THE AMOUNT IS FORMATTED HERE AND NOWHERE ELSE.** Hard rule 2: money is
STORED to four decimals and DISPLAYED to two. A partner's file is a display, so
`amount` leaves as a two-decimal string — `"142.18"`, never `142.18` as a float
and never `142.180000`. A float would be the one thing hard rule 2 names by
name; a string keeps the exactness across every JSON parser on the far end.

⚠ **AND THE SHAPE STOPPED BEING PLAIN ON 2026-09-16 — `CR-110-BRC04` PHASE 2
WAVE 4, AND THE PARAGRAPH ABOVE IS KEPT BECAUSE ITS REASONING IS WHAT MOVED.**
The PO ruled: *"this will not be required in case of they read cases - we just
need to actiavte connectors and issue a key thats all"*, which struck the clerk
mapping screen. **For a READ the partner maps at THEIR end**, from the reference
endpoint. So the four coded fields are now on the payload — and they are OURS,
published with a word each, **never translated into the partner's vocabulary**:

    type           payments.type       payment · credit · adjustment
    projectType    payments.purpose    bill · deposit · plan_down · prepay
    tenderType     payment_methods     the tenant's own tenders, their words
    paymentPayType payments.status     posted · cleared · reversed · …

**That does NOT reopen `BR-INT-054`, and the distinction is the whole of it.**
What Runbooks owns is the TRANSLATION — deciding that our *Bank transfer* is
their `ACHCHECK` — and `serve.partner_fields()` is still where that arrives and
still returns nothing. Publishing our own code with our own label is not ETL: it
is the same act as the reference endpoint, which the PO commissioned in the same
hour for exactly this purpose.

⚠ **`tenderType` READS THE TENANT'S `payment_methods` ROW ITSELF** — code and
name — which is the identical pair `mappings.our_choices(tenant_id, "tender")`
publishes on the reference endpoint. One source, so the document a partner
cached and the label on the payload cannot disagree.

⚠ **AND THE VENDOR'S OWN DOCUMENT IS NOT IN THIS REPO.** The four names above
are the supplied payload's; what each MEANS in Aclarian's world is not written
anywhere we hold, so the mapping to our four payment vocabularies is OURS and is
recorded on the CR with its reasoning rather than left to be inferred. Each is a
one-line change in one place if the partner's engineer says otherwise.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from core.tenancy import current_tenant_id

#: Only money the utility took and stands behind is handed over: `posted`
#: (taken and applied, PO 2026-10-21) and `cleared` (reconciled with the bank
#: statement). A processing, failed or cancelled payment is not a payment a
#: finance system should post, and a partner that collected one would book a
#: receipt the utility never took. Each row says which of the two it is, in
#: our own word (`paymentPayType`), never translated.
#:
#: ⚠ **`deposited` AND `settled` ARE NOT STATUSES THIS PRODUCT HAS, AND NEVER
#: WERE — `DEF-INT-5543`, found while writing `paymentPayType`.** The column's
#: vocabulary is `processing · cleared · failed · reversed · posted ·
#: cancelled` (`payments.models.PAYMENT_STATUSES`; `cancelled` added by
#: `payments/0035`, `CR-137-BRC07` `P3.5`, and deliberately NOT added below —
#: a payment taken by mistake and undone is not money a finance system should
#: post, which is this tuple's own test), so two of the four values below match
#: no row and the filter is right by accident. It is left exactly as it is here
#: and filed instead: correcting a served set is a change to what a partner
#: collects, and it belongs in a commit that says so rather than in a wave
#: about payload shape. **A reader taking this tuple as the definition of
#: *settled money* would believe two states are served that cannot be.**
COLLECTABLE_STATUSES = ("posted", "deposited", "cleared", "settled")


def _model() -> Any:
    """Imported inside the call so the module graph stays a DAG — integrations
    is loaded at `AppConfig.ready()` and payments must not have to be."""
    from apps.payments import models as payments_models

    return payments_models.Payment


def display_amount(value: Any) -> str:
    """Four stored decimals → two displayed, half-up (hard rule 2, B4)."""
    return str(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


#: `CR-132-BRC07` — the origin the New World feed selects, and the ONLY value
#: it selects. PO ruling 2026-09-22: the feed carries online money only, which
#: is the customer's own requirement rather than our narrowing. The word is the
#: payment column's (`payments.origin`, `payments/0029`), which is the same
#: vocabulary `apps/payments/idempotency.py` has used since `US-PAY-001`.
ORIGIN_ONLINE = "webhook"


def collectable(
    *,
    since: date | None = None,
    until: date | None = None,
    origin: str | None = None,
    posted_from: Any = None,
    posted_before: Any = None,
) -> Any:
    """The queryset a partner's page is cut from — newest last, so paging is
    stable across requests made minutes apart.

    ⚠ NO TENANT ARGUMENT. The tenant is on the database session already
    (`app.tenant_id`, set from the path by `TenantContextMiddleware`); adding a
    parameter here would be adding the one thing hard rule 1 forbids — a way to
    ask for another utility's rows.

    ⚠ **THE `tenant_id` FILTER IS BELT AND BRACES AND IT IS THE THIRD PLACE
    THIS WAVE NEEDED IT.** RLS `FORCE` scopes this on PostgreSQL, so it is
    redundant in production. **The suite runs on SQLite, which has no RLS**
    (`config/settings/test.py` hardcodes it), and the first draft relied on RLS
    alone: `test_tc7…` asked Lone Star Ridge for its seven payments and got
    ELEVEN — its own seven and Brazos Bend's four. Written the other way round,
    a partner reading another utility's money would have passed the entire
    suite, because the one mechanism that stops it does not exist on the vendor
    the suite runs on (CLAUDE.md law 7, *structurally incapable of failing*).
    So the tenant is stated twice, and the isolation case can go red on either
    vendor. `runners/serve.py` and `subprocessors.py` carry the same paragraph.

    """
    tenant_id = current_tenant_id()
    if tenant_id is None:
        return _model().objects.none()
    query = _model().objects.filter(tenant_id=tenant_id, status__in=COLLECTABLE_STATUSES)
    if since is not None:
        query = query.filter(posted_at__date__gte=since)
    if until is not None:
        query = query.filter(posted_at__date__lte=until)
    # ── `CR-173-BRC10` · A DAY ON THE UTILITY'S OWN CLOCK ──────────────────
    # `since`/`until` are calendar dates read through `__date`, which takes
    # the date in the SERVER's zone. The City's file is the utility's own day
    # (PO 2026-10-07 Q2: *"Ann Arbor's local day"*), so a 9 pm payment on
    # 5 Oct in Michigan — 01:00 UTC on the 6th — belongs to the 5th. The file
    # builder passes the two INSTANTS that bound that local day instead:
    # `posted_from` inclusive, `posted_before` exclusive, so consecutive days
    # tile with no gap and no overlap, through a daylight-saving change too.
    if posted_from is not None:
        query = query.filter(posted_at__gte=posted_from)
    if posted_before is not None:
        query = query.filter(posted_at__lt=posted_before)
    # ── `CR-132-BRC07` · ONE FEED SELECTS ONE ORIGIN ───────────────────────
    # ⚠ **IT FILTERS ON THE COLUMN AND NOT ON THE IDEMPOTENCY KEY'S PREFIX,
    # WHICH IS THE WHOLE REASON `payments/0029` EXISTS.** `webhook_key` is
    # NULL on every payment recorded without an idempotency reference, so
    # `webhook_key__startswith="webhook|"` would look right, pass every test
    # written against seeded webhook rows, and silently omit real ones.
    #
    # ⚠ **A NULL ORIGIN IS EXCLUDED BY THIS FILTER RATHER THAN BY A DEFAULT.**
    # The column is nullable on purpose (see the migration); an `=` comparison
    # excludes NULL in SQL, so a payment written by a path that forgot to
    # stamp an origin is LEFT OUT of a money feed rather than swept into it.
    # Out of a general ledger is a gap somebody can find; wrongly in it is a
    # posting nobody questions.
    if origin is not None:
        query = query.filter(origin=origin)
    return query.order_by("posted_at", "id")


class PageContext:
    """What a page of payments needs that is not on the payment row.

    ⚠ **ASKED ONCE FOR THE PAGE, NEVER PER ROW.** The PO set the page at 1,000
    (*"make this as 1000 per page"*), so a per-row account name or a per-row
    chart lookup is a thousand round trips for one column — DEF-2723's shape on
    a surface a partner pulls a month of at a time.

    `as_record` still works with no context: it builds one for the single
    payment it was handed, so a page and a spot check come out of the same code.
    """

    __slots__ = ("names", "gl_codes")

    def __init__(self, *, names: dict[str, str | None], gl_codes: dict[str, str]) -> None:
        self.names = names
        self.gl_codes = gl_codes


def page_context(payments: list[Any]) -> PageContext:
    """The two shared reads for ONE page of payments."""
    from apps.customers import selectors as customers_selectors
    from apps.ledger import selectors as ledger_selectors

    account_ids = sorted({str(one.account_id) for one in payments})
    # ⚠ THE PUBLISHED BATCHED SELECTOR, NOT A SECOND DERIVATION — the same one
    # the accounts list's Name column reads, in the same order. Its docstring
    # records why that order is load-bearing.
    names = customers_selectors.primary_contact_names_for(account_ids) if account_ids else {}
    gl_ids = {
        str(one.method.clearing_gl_account_id)
        for one in payments
        if one.method is not None and one.method.clearing_gl_account_id
    }
    labels = ledger_selectors.account_labels(sorted(gl_ids)) if gl_ids else {}
    return PageContext(
        names=names,
        gl_codes={key: str(value["code"]) for key, value in labels.items() if value.get("code")},
    )


def _coded(code: Any, labels: dict[str, str]) -> dict[str, str] | None:
    """A coded value as `{code, label}` — the shape EVERY coded field leaves
    this surface in (PO 2026-09-16). The words are `reference.py`'s, which is
    the file whose whole job is *every code we can put on a partner payload,
    with its meaning*; writing a second set here is how two labels for one code
    start disagreeing."""
    from apps.integrations import reference

    if code in (None, ""):
        return None
    return {"code": str(code), "label": labels.get(str(code)) or reference.derived_label(code)}


def as_record(payment: Any, context: PageContext | None = None) -> dict[str, Any]:
    """One payment, in the fields that are ours to hand over.

    `id` is the utility's own receipt number (`PMT-000412`) and NOT the database
    key — B14 rule 31 is about screens, but the reasoning travels: a partner
    that keyed its ledger on our internal uuid would be coupled to our storage
    forever. `payment_no` is the number a clerk and a customer both already use.

    ⚠ **`FeeEntryId` IS THE CONFIRMATION NUMBER AND IS OFTEN NULL.** It is the
    reference the money arrived with — a cheque number, a processor's
    transaction id — which is `payments.confirmation`, one of the exactly three
    columns the PO opened to correction on 2026-09-02 (hard rule 4,
    `payments/0014`). A partner reconciling a bank statement matches on this;
    `null` means the utility recorded no reference, and inventing one would put
    a number on a bank line that nobody can look up.

    ⚠ **`paymentDate` IS THE FULL TIMESTAMP HERE AND A DATE ON THE RETIRED FLAT
    ROUTE.** `posted_at` is when the record entered the system (BR-PAY-021,
    user-entered and never a clock) and the supplied document draws a timestamp;
    a date alone cannot order two payments taken at the same counter on the same
    morning, which is what a partner's job pages by.

    ⚠ **`accountString` IS THE TENDER'S CLEARING ACCOUNT, AND `null` WHEN THE
    TENDER IS UNMAPPED.** `payment_methods.clearing_gl_account_id` is the CASH
    side (CR-008 second-set ruling 1) — where money a customer HANDS OVER lands
    — and it is what `payments.ledger_seam.post_payment_cleared` debits. When it
    is NULL that posting falls back to the `undeposited_funds` designation, and
    **that fallback is deliberately not published here**: resolving it would be
    this seam stating a posting decision it did not make, free to disagree with
    the ledger the day either moves. A null a partner's job can stop on beats a
    default it will post.
    """
    from apps.integrations import reference

    if context is None:
        context = page_context([payment])

    method = payment.method
    gl_account_id = method.clearing_gl_account_id if method is not None else None
    return {
        "id": payment.payment_no,
        "FeeEntryId": payment.confirmation,
        "consumerNo": payment.account.account_no,
        "customer_name": context.names.get(str(payment.account_id)),
        # `Z` and not `+00:00` — the supplied document draws
        # `2025-01-01T00:00:00Z`, and one spelling of UTC is enough.
        "paymentDate": _utc_text(payment.posted_at),
        "type": _coded(payment.type, reference.PAYMENT_TYPE_LABELS),
        "projectType": _coded(payment.purpose, reference.PAYMENT_PURPOSE_LABELS),
        "tenderType": (
            {"code": str(method.code), "label": str(method.name or method.code)}
            if method is not None
            else None
        ),
        "paymentPayType": _coded(payment.status, reference.PAYMENT_STATUS_LABELS),
        "amount": display_amount(payment.amount),
        "currency": payment.currency,
        # The clerk's own note. `""` and not null when there is none, because
        # the supplied document draws an empty string and a description is text.
        "description": payment.memo or "",
        "accountString": context.gl_codes.get(str(gl_account_id)) if gl_account_id else None,
    }


def _utc_text(moment: Any) -> str | None:
    """`2025-01-01T00:00:00Z`. A naive datetime is read as UTC, which is what
    `USE_TZ` already guarantees on every stored column."""
    if moment is None:
        return None
    from datetime import timezone as _timezone

    if moment.tzinfo is None:
        return moment.replace(microsecond=0).isoformat() + "Z"
    return moment.astimezone(_timezone.utc).replace(tzinfo=None, microsecond=0).isoformat() + "Z"


def records_for(payments: list[Any]) -> list[dict[str, Any]]:
    """A whole page, with the two shared reads made once."""
    rows = list(payments)
    if not rows:
        return []
    context = page_context(rows)
    return [as_record(one, context) for one in rows]


def page_queryset(
    *,
    since: date | None = None,
    until: date | None = None,
    origin: str | None = None,
    posted_from: Any = None,
    posted_before: Any = None,
) -> Any:
    """`collectable` with the joins a record needs, so a page of 1,000 payments
    is not 2,000 extra statements for the account and the tender."""
    return collectable(
        since=since,
        until=until,
        origin=origin,
        posted_from=posted_from,
        posted_before=posted_before,
    ).select_related(
        "account", "method"
    )


def land_inbound_delivery(
    *,
    provider: str,
    event_id: str,
    body: dict[str, Any],
    received_at: Any,
    audit_after: dict[str, Any] | None = None,
) -> Any:
    """Land ONE arriving notification: the composite key deduped, the raw
    envelope persisted, and **nothing applied** (`BR-INT-058`).

    Returns payments' own `LandedDelivery` — `landed=True` when this call
    wrote the row, `landed=False` when the key was already present and the
    door must answer `409`.

    ⚠ **THE IMPORT IS INSIDE THE CALL, AS EVERY OTHER FUNCTION HERE DOES IT.**
    `G6` refuses a module-scope import of another app's model module from
    `apps/integrations/` (B2 §2), and beyond the gate the module graph has to
    stay a DAG: integrations is loaded at `AppConfig.ready()` and payments
    must not have to be.

    ⚠ **AND THE SENTENCE ABOVE IS DELIBERATELY PARAPHRASED RATHER THAN QUOTING
    THE PATTERN (`DEF-INT-4258`).** A first draft spelled the forbidden import
    out inside backticks, and G6 went RED on this docstring — its cross-module
    clause judges the RAW line, while the two rules beside it strip inline-code
    spans first. That is the DEF-043 shape the gate's own comment says was
    fixed generally; it was not carried to this clause. Filed, not worked
    around here: loosening a module-boundary matcher is not a thing a lane
    passing through should do.

    ⚠ **NOTHING IN THIS FILE OPENS A TRANSACTION.** The SAVEPOINT that makes a
    batch survive one bad item on PostgreSQL is inside `land_delivery`, next
    to the INSERT it protects, where CLAUDE.md law 14 says it belongs. A
    second `atomic()` here would nest a savepoint inside a savepoint and read
    as though the guarantee lived in two places.
    """
    from apps.payments import webhooks as payments_webhooks

    return payments_webhooks.land_delivery(
        provider=provider,
        event_id=event_id,
        body=body,
        received_at=received_at,
        actor=None,  # BR-AUD-003 — there is no user behind a kiosk.
        audit_after=audit_after,
    )


def record_partner_payment(
    *,
    actor: Any,
    account_id: Any,
    amount: Any,
    posted_at: Any,
    currency: str | None,
    method_code: str,
    confirmation: str,
    memo: str | None,
    invoice_no: str,
    idempotency_reference: str,
) -> Any:
    """`POST /partner/v1/make-payment/` — ONE payment, recorded by PAYMENTS.

    ⚠ **THIS SEAM WRITES NOTHING AND THAT IS THE WHOLE POINT OF IT BEING
    HERE.** Every row this call produces — the payment, its allocations, its
    journal entry, its audit rows — is written by `payments.services.
    record_payment` inside ONE transaction that belongs to payments. B2 §2:
    integrations does not write another module's tables, and hard rules 4, 5
    and 7 all name that service as the writer. The seam is the ADDRESS, exactly
    as `land_inbound_delivery` above says of itself.

    ⚠ **AND THIS FILE'S OWN HEADING IS NOW NARROWER THAN IT WAS — AMENDED
    2026-09-24.** The module docstring says *"What integrations still may not
    do is unchanged and is the important half: it does not RECORD A PAYMENT"*,
    and for the KIOSK relationship that stays exactly true (`BR-INT-058` puts
    the apply half in Runbooks; `OQ-INT-1729` ruled option (a) on 2026-09-06).
    **A partner POSTING a payment on the partner door is a different
    relationship and was ruled separately**: PO 2026-09-18, *"they post to us
    daily"*, and the Make Payment design confirmed in full on 2026-09-24. Two
    doors, two authentications, two rules — which is why this function stands
    beside that one rather than in place of it.

    THE FOUR ARGUMENTS THAT ARE DECISIONS, NOT PASS-THROUGHS
    ---------------------------------------------------------
    **`cleared_at` is NOT PASSED, and the payment is `posted`** (amended
    2026-10-21, `CR-186-BRC10`; until then this paragraph read *"so the payment
    is `processing`"* and `OQ-PAY-12627` was open). The PO answered that
    question `posted` — *"we cannot mark payment clear yet"*, *"we have to
    return posted and internal status also should be posted or processing"* —
    and ruled the same for every method the same day: the record is created
    `posted` at entry, applied to its bill and journalled then, and becomes
    `cleared` only when the utility reconciles its deposit batch with the bank
    statement. `record_payment` writes `posted` at entry; a clearing date passed
    from here would be this door claiming the bank agreed, which is exactly
    what the ruling says it cannot.

    **`counter_session_id` is NOT PASSED, so it is NULL.** PO ruling 2026-09-23
    §3.4: only `cash`, `check` and `money_order` — money that passes through a
    person's hands — need an open till, and an Invoice Cloud payment is taken
    on THEIR portal. `invoice_cloud_payment._method_for` refuses the three hand
    tenders on that door, so this stays TRUE rather than being assumed.
    ⚠ **THE DEPOSIT BATCH IS NO LONGER NULL** (PO 2026-10-21, *"one batch per
    provider per day"*): payments stamps the day's Invoice Cloud batch at
    posting, and the reply carries it.

    **`targets` names the bill and `order` is `specific`.** *This bill, up to
    what it owes; anything it cannot absorb carries as account credit* —
    `BR-PAY-010`'s overpayment rule, which is also the PO's own *"Overpayment →
    credit note … yes"* of 2026-09-17, and confirmed unchanged on 2026-10-21
    (*"as of now this is correct"*). It is APPLIED at posting.

    **`purpose` is left at its default `bill`** and `payment_type` at
    `payment`. A partner sends money a customer handed over; a credit or an
    adjustment is the utility's own decision and would require a `reason_code`
    (`CR-059` CS-35).
    """
    from apps.payments import allocation, idempotency, services

    class _Target:
        """`allocation.AllocationTargetLike` — the allocator reads these two
        names and nothing else. `amount=None` is the `specific` instruction:
        the partner named a BILL, not a figure against it."""

        __slots__ = ("invoice_number", "amount")

        def __init__(self, invoice_number: str) -> None:
            self.invoice_number = invoice_number
            self.amount = None

    # The named bill, if it still owes anything; anything above what it owes
    # becomes account credit (PO 2026-10-21: *"Specific bill: Only the bill
    # named; anything above what it owes becomes account credit"*). A bill that
    # owes NOTHING (already paid in full, e.g. by an earlier payment) is not an
    # open bill, so the whole payment is carried as credit, rather than refused
    # and lost to a partner that has already taken the customer's money.
    from apps.payments import billing_seam as payments_billing_seam

    still_open = any(
        getattr(bill, "number", None) == invoice_no
        for bill in payments_billing_seam.open_invoices_for_account(account_id).invoices
    )

    return services.record_payment(
        actor,
        account_id=account_id,
        amount=amount,
        posted_at=posted_at,
        # ⚠ NO `cleared_at` — `posted` at entry, `cleared` only at bank
        # reconciliation (`OQ-PAY-12627` answered `posted`, PO 2026-10-21).
        # See the docstring.
        currency=currency,
        method_code=method_code,
        confirmation=confirmation,
        memo=memo,
        order=allocation.ORDER_SPECIFIC if still_open else allocation.ORDER_CARRY_CREDIT,
        targets=(_Target(invoice_no),) if still_open else (),
        # Hard rule 6. ⚠ **THE SOURCE IS `webhook` AND THE PROVIDER TRAVELS IN
        # THE REFERENCE**, giving `webhook|invoice_cloud:TID161007`.
        # `settlements._payment_for` re-composes exactly that string to find a
        # payout's members, so a payment keyed any other way would be invisible
        # to the settlement that later names it. The constant is read from
        # payments' own module rather than re-typed: one spelling of a
        # namespace that decides whether money is found twice.
        idempotency_source=idempotency.SOURCE_WEBHOOK,
        idempotency_reference=idempotency_reference,
    )


# ═══════════════════════════════════════════════════════════════════════════
# `CR-174-BRC10` · A PAYMENT AGENT'S THREE CALLS — the address, never the writer
# ═══════════════════════════════════════════════════════════════════════════
#
# PO 2026-10-07 (D1), verbatim: *"(a). A person standing at a machine needs the
# live balance. Runbooks still handle the exceptions in D2."* So for an
# operation that DECLARES an apply (`Operation.applies`), the door calls these
# three. Every row they produce — the payment, its allocations, its journal
# entry, the reversal, the audit rows, the stamp on the landing row — is
# written by `apps.payments.agent_door`, which is payments' own code writing
# payments' own tables (B2 §2). This file still performs no ORM write.


def agent_account_position(account_ref: Any, *, as_of: date) -> dict[str, Any] | None:
    """The lookup: the ONE balance read the customer portal reads, or None."""
    from apps.payments import agent_door

    return agent_door.account_position(account_ref, as_of=as_of)


def post_agent_payment(**kwargs: Any) -> Any:
    """Record one agent payment, or park it for a clerk (D2)."""
    from apps.payments import agent_door

    return agent_door.post_payment(**kwargs)


def post_agent_return(**kwargs: Any) -> Any:
    """Reverse the payment an agent's return names, through `reverse_payment`."""
    from apps.payments import agent_door

    return agent_door.post_return(**kwargs)


def agent_outcomes() -> Any:
    """The four outcome CODES, read from their owner rather than re-typed."""
    from apps.payments import agent_door

    return agent_door


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-041@wave-S (EP-INT-11) · US-INT-044@wave-N (EP-INT-13)
# generated: 2026-09-06 by the CR-069 wave S build lane (integrations half)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
# gates: pytest tests/test_us_int_041_partner_surface.py
# exceptions: this file performs no ORM write of its own — `land_inbound_delivery` calls payments' own `webhooks.land_delivery` and `record_partner_payment` calls payments' own `services.record_payment` (B2 §2: integrations does not write another module's rows; the seam is the address, not the writer). ⚠ AMENDED 2026-09-24: this line read "It records NO payment: BR-INT-058 puts the apply half in Runbooks and it is not built" and that is still true OF THE KIOSK — `record_partner_payment` is the PARTNER DOOR's write, a different relationship ruled separately (PO 2026-09-18 "they post to us daily"; the Make Payment design confirmed 2026-09-24). Still no ORM write here
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
