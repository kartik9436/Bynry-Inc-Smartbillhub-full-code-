# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-013 (the platform delivery dashboard + re-queue — this file
#           is its LIST half: the S8 capability row, served)
#           Screens: S8 · S30 · S35
# Rules:    BR-NOT-005 (the platform-wide queue and its five statuses) ·
#           BR-TEN-041 #8 (Settings → Notifications is the delivery/dispatch
#           home) · BR-SHL-011 (the list grammar: q · sort · dir · page · per ·
#           f.<name>, and a list URL never errors over its params) ·
#           BR-SHL-010 (the per-screen vocabulary is the capability row's) ·
#           BR-AUD-006 (no PII beyond what the screen is entitled to show) ·
#           BR-TEN-003 / HR-1 (another tenant's row reads as absent) ·
#           CLAUDE.md rule 1 (tenant scoping; RLS FORCE) · rule 2 (money is
#           Decimal + its CURRENCY, never a float and never a bare number)
# Tests:    06-backend/tests/test_def_128_notifications_api.py
# Impacts:  apps/notifications/api.py (the only caller)
# ───────────────────────────────────────────────────────
"""The delivery queue, as a list a person can read — US-NOT-013's S8 row.

THIN AND READ-ONLY. No status moves here, no row is written, and there is no
clock: `created_at` IS the `queued_at` the capability row sorts by, and an "age"
computed from `timezone.now()` would age every row by a day the moment somebody
opened the screen from another timezone (BR-TEN-043; gate G6 greps for it).

────────────────────────────────────────────────────────────────────────────
THE DEFAULT SORT IS "FAILED FIRST", AND IT IS A RULE RATHER THAN A PREFERENCE
────────────────────────────────────────────────────────────────────────────
EP-NOT-04's capability matrix, verbatim: *"Default sort: failed+bounced first,
then queued_at."* US-NOT-013 TC-2 asserts it from the other side. The reason is
what the screen is FOR: the dispatch home is opened when something has gone
wrong, and a queue sorted newest-first buries six failed letters under nine
hundred that are fine.

It is expressed as an annotated rank rather than as two queries, so paging
works: sorting a page in Python would put "failed first" inside page 1 and
nowhere else, which is the shape of a list that looks right in a screenshot.

────────────────────────────────────────────────────────────────────────────
WHAT THIS LIST DOES NOT SAY
────────────────────────────────────────────────────────────────────────────
* **No `delivered`/`bounced` row will ever appear.** Both are PROVIDER facts and
  no provider adapter exists on any channel — delivery is out of this release by
  PO ruling (2026-08-15). `delivery_ops.queue_health()` carries that as data and
  the summary endpoint serves it, so a screen renders "not reported" rather than
  a zero that reads as a delivery failure.
* **No money.** An `outbound_messages` row carries a recipient, a channel and a
  template pin; the AMOUNT a notice states lives on the document it renders. So
  no figure on this list is a money figure and none is served as one. The
  notice-history read is where money does appear (`detail.reconnect_fee`), and
  `money_str` below is why it never appears without its currency.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from django.db.models import Case, IntegerField, Q, QuerySet, Value, When

from apps.notifications import customers_seam, models, tenancy_seam
from core import errors
from core import tenancy as core_tenancy
from core.pagination import ListParams, parse_list_params

#: BR-SHL-010 — the S8 capability row's vocabulary and no more. An undeclared
#: `f.*` is ignored rather than refused (BR-SHL-011: *"a list URL never errors
#: over its params"*), so a stale bookmark renders a list instead of a stack
#: trace.
QUEUE_SORTS = ("status", "channel", "source_type", "queued_at", "attempts")
#: `returned` was added 2026-08-16 for US-PAY-016's bulk mark. It is the
#: difference between the fourteen envelopes a clerk is holding and every letter
#: the utility has ever posted: without it the S35 stack screen is a nine-
#: hundred-row list with the fourteen somewhere inside it, which is not a
#: surface anybody works a Tuesday chore from.
QUEUE_FILTERS = (
    "status",
    "channel",
    "source_type",
    "account_id",
    "held",
    "returned",
    "from",
    "to",
    #: DEF-NOT-10650 (PO 2026-10-29, 1A) — *Needing attention*:
    #: `models.ATTENTION_STATUSES`, the tuple the triage sort below reads.
    "attention",
)
DEFAULT_QUEUE_SORT = "triage"

#: `notice_history`'s own vocabulary (r12 #7), for `GET /notices`.
NOTICE_FILTERS = ("account_id", "notice_type", "tier", "outcome", "certified")

#: ⚠ **`NOTICE_READ_CAP = 2000` LIVED HERE AND IS DELETED (`DEF-NOT-5750`,
#: 2026-09-19).** `GET /notices` asked payments for 2,000 rows and paged them in
#: memory, so the 2,001st notice was unreachable on every page — a maximum
#: `NFR-5` forbids, and one a single dunning cycle over 40,000 accounts passes
#: in a night. **The number was not raised, it was removed**: the page is taken
#: in the DATABASE now, through `payments_seam.notice_history_window` onto
#: payments' `notice_history_page` / `notice_history_count`. The response's
#: `notice_history_truncated` problem row went with it — nothing truncates, so
#: a sentence saying where the record stopped would be a lie on screen. Recorded
#: rather than silently dropped: the constant was CITED, and an absence is
#: invisible to every check this repo has (the `DEF-CUS-3653` lesson).

#: The one tier BR-CUS-039 makes certified mail mandatory for, spelled as
#: `apps/payments/collections_models.py` and `apps/notifications/notices.py`
#: both spell it. One vocabulary across the boundary or the certified register
#: quietly lists nothing.
TIER_FINAL_48_HOUR = "final_48_hour"

#: Why a certified letter carries no tracking number here. Stated as a CODE on
#: the response, not only in prose — hard-won law 1.
CERTIFIED_NUMBER_UNAVAILABLE = "certified_number_unavailable"


def _tenant_id() -> Any:
    """Hard rule 1: no tenant table is touched without `app.tenant_id` set."""
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def tenant_currency() -> tuple[str | None, tuple[dict[str, Any], ...]]:
    """(currency, problems) — the CHAR(3) every money figure must travel with.

    CLAUDE.md rule 2 makes currency a column, not a constant, and BR-TEN-042
    locks it per tenant. A response that served `reconnect_fee: "45.00"` with no
    currency would be read as dollars by every reader who happens to be in
    dollars, which is precisely the class of error the rule exists to prevent.

    REPORTS rather than refuses, following `tenancy_seam.regional_formats`'s
    ruled posture (OQ-117, PO 2026-08-12 — *"issue and report it"*): a notice
    history with a named currency gap is still the record a clerk needs, and the
    gap travels beside it.
    """
    try:
        formats, problems = tenancy_seam.regional_formats()
    except Exception as unreadable:  # pragma: no cover - tenancy publishes this
        return None, (
            {
                "code": "tenant_currency_unavailable",
                "br_ref": "BR-TEN-042",
                "detail": f"the tenant's Regional settings could not be read ({unreadable}), "
                "so any money figure below is served WITHOUT its currency and must not be "
                "rendered as though it were the reader's own.",
            },
        )
    return (formats.get("currency") or None), problems


def money_str(value: Any) -> str | None:
    """A money figure as a STRING at NUMERIC(18,6) fidelity — never a float.

    JSON has one number type and it is a double. Serialising `Decimal("45.00")`
    as a JSON number hands the client `45.0` and, at six decimal places on a
    prorated figure, hands it something that is not the stored value at all.
    Every money member on this module's responses is a string for that reason —
    the same call `apps/payments/selectors.py` made.

    `None` stays `None`: absent is not zero, and a reconnect fee that was never
    configured must never print as 0.00 on a legal notice (BR-BIL-007).
    """
    if value is None or value == "":
        return None
    try:
        return str(Decimal(str(value)))
    except (InvalidOperation, TypeError, ValueError):
        # A detail payload is JSON written by a generator; a value that is not a
        # number is served back verbatim rather than dropped, because dropping
        # it would hide what was actually recorded on a regulatory row.
        return str(value)


def list_params(query_params: Any) -> ListParams:
    """BR-SHL-011 params for the queue list, in the S8 capability vocabulary."""
    return parse_list_params(
        query_params,
        allowed_sorts=QUEUE_SORTS,
        default_sort=DEFAULT_QUEUE_SORT,
        allowed_filters=QUEUE_FILTERS,
    )


def queue_queryset() -> QuerySet:
    """Every outbound row for THIS tenant. The one entry point to the table."""
    return models.OutboundMessage.objects.filter(tenant_id=_tenant_id())


def _apply_search(rows: QuerySet, term: str) -> QuerySet:
    """The capability row's three search fields: recipient · account · ref.

    `message ref` is read as the row's own id OR the source document's id — a
    clerk holding a reference does not know which of the two they have, and
    asking them to is the kind of question a support call is made of.
    """
    if not term:
        return rows
    matched = Q(recipient_address__icontains=term) | Q(template_code__icontains=term)
    for field in ("pk", "source_id", "account_id"):
        try:
            matched |= Q(**{field: term})
        except (ValueError, TypeError):  # pragma: no cover - non-uuid terms
            continue
    return rows.filter(matched)


def _apply_filters(rows: QuerySet, filters: dict[str, str]) -> QuerySet:
    """Declared filters only. An unparseable value narrows to nothing rather
    than being ignored: a screen that asked for one account and got the whole
    platform back would be showing another customer's mail."""
    if "status" in filters:
        rows = rows.filter(status=filters["status"])
    if "channel" in filters:
        rows = rows.filter(channel=filters["channel"])
    if "source_type" in filters:
        rows = rows.filter(source_type=filters["source_type"])
    if "account_id" in filters:
        rows = rows.filter(account_id=filters["account_id"])
    if "held" in filters:
        rows = rows.filter(held=str(filters["held"]).lower() in ("1", "true", "yes"))
    # DEF-NOT-10650 (1A) — the screen OPENS on this. `false` is every message,
    # which is the switch's other half and the same as omitting it.
    # DEF-NOT-10665 (D1 A) — and a failure already retried to a corrected
    # address has left it: `attention.needing_attention`, the count's own rule.
    if str(filters.get("attention", "")).lower() in ("1", "true", "yes"):
        from apps.notifications import attention

        rows = attention.needing_attention(rows)
    # US-PAY-016's stack. `f.returned=false` is the pile still to work; `true` is
    # what has already come back. The column is a TIMESTAMP, so the filter is
    # null-ness rather than equality — asking `returned_at=false` of a database
    # would be asking a date to be a boolean.
    if "returned" in filters:
        rows = rows.filter(
            returned_at__isnull=str(filters["returned"]).lower() not in ("1", "true", "yes")
        )
    # The capability row's date range, over `created_at` — which IS `queued_at`
    # (models.py). Bounds are the CALLER's, parsed as given: no clock is read
    # here and no default window is invented (BR-TEN-043).
    if filters.get("from"):
        rows = rows.filter(created_at__date__gte=filters["from"])
    if filters.get("to"):
        rows = rows.filter(created_at__date__lte=filters["to"])
    return rows


def _apply_order(rows: QuerySet, params: ListParams) -> QuerySet:
    """The capability row's default — *"failed+bounced first, then queued_at"*.

    An annotated rank, so the rule survives pagination (see the module
    docstring). A caller that names one of the five sortable columns gets that
    instead, which is the capability row's other half.
    """
    if params.sort in (None, DEFAULT_QUEUE_SORT):
        rows = rows.annotate(
            triage=Case(
                # `ATTENTION_STATUSES` — the same tuple the partial index and
                # `delivery_ops.failures` read (`DEF-NOT-5626`). A hard bounce
                # sorts first exactly as a failure does; an `unsubscribed` row
                # does not, because it is a choice and not a fault.
                When(status__in=models.ATTENTION_STATUSES, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        )
        return rows.order_by("triage", "-created_at", "-id")
    column = {"queued_at": "created_at"}.get(params.sort, params.sort)
    prefix = "-" if params.dir == "desc" else ""
    # `id` breaks every tie: two rows written in the same millisecond by one bill
    # run must not swap places between page 1 and page 2.
    return rows.order_by(f"{prefix}{column}", "-id")


def queue_list_queryset(params: ListParams) -> QuerySet:
    from apps.notifications import attention

    # DEF-NOT-10665 — every listed row says whether it was retried to a new
    # address, in the same statement as the page (an annotation, not a read
    # per row).
    rows = queue_queryset().annotate(retried_to_new_address=attention.retried_to_new_address())
    return _apply_order(_apply_filters(_apply_search(rows, params.q), params.filters), params)


def queue_recipient_name(row: Any) -> str | None:
    """`DEF-NOT-9666` — the NAME of a staff member an in-app row is addressed
    to, from its snapshot; None for every other channel.

    An in-app row's `recipient_address` is a USER ID — the queue screen drew it
    as the recipient, which is B14 rule 31's database id on screen. A staff
    member's name on a staff screen is the clerk's own colleague; a CUSTOMER's
    name stays off the list (the posture `queue_row`'s docstring states), so
    this answers only for `in_app`.
    """
    if getattr(row, "channel", None) != models.CHANNEL_IN_APP:
        return None
    snapshot = getattr(row, "recipient_snapshot", None) or {}
    name = snapshot.get("display_name") if isinstance(snapshot, dict) else None
    return str(name) if name else None


def queue_row(row: models.OutboundMessage) -> dict[str, Any]:
    """One S8 row: Type · Account · Channel · Status · Attempts · Last error ·
    Batch (+ provider ref, source module — the IS-5 available columns).

    `recipient_address` IS served — it is the capability row's first search
    field and the column a clerk uses to see WHERE a letter went — and
    `recipient_snapshot` is NOT: the envelope payload carries a customer's name
    and full postal address, and a list of nine hundred rows is not the surface
    that needs them (BR-AUD-006's posture). The detail is on the row for anyone
    entitled to open it.
    """
    return {
        "id": str(row.pk),
        "source_type": row.source_type,
        "source_id": str(row.source_id),
        "account_id": str(row.account_id) if row.account_id else None,
        "channel": row.channel,
        "copy_no": row.copy_no,
        "status": row.status,
        "held": row.held,
        "held_reason": row.held_reason,
        "attempts": row.attempts,
        "last_error": row.last_error,
        "batch_id": str(row.batch_id) if row.batch_id else None,
        "provider_reference": row.provider_reference,
        "template_code": row.template_code,
        "template_version": row.template_version,
        "template_language": row.template_language,
        "recipient_address": row.recipient_address,
        # DEF-NOT-9666 — a staff recipient by NAME (in-app rows only).
        "recipient_name": queue_recipient_name(row),
        #: BR-BIL-036 made visible: an absent address is STATED, never implied
        #: by a blank cell. "no email address on file" and "nobody looked" are
        #: different facts and this column is which one it is.
        "unavailable_reason": row.unavailable_reason,
        "queued_at": row.created_at.isoformat() if row.created_at else None,
        "dispatch_not_before": (
            row.dispatch_not_before.isoformat() if row.dispatch_not_before else None
        ),
        "last_attempt_at": row.last_attempt_at.isoformat() if row.last_attempt_at else None,
        # DEF-NOT-10650 (4B) — the LAST attempt's diagnostics, for the error
        # details panel. What the provider answered, as it answered it, and
        # when the next try is due. No per-attempt history exists or is implied.
        "next_attempt_at": row.next_attempt_at.isoformat() if row.next_attempt_at else None,
        "provider_response": row.provider_response,
        "sent_at": row.sent_at.isoformat() if row.sent_at else None,
        "returned_at": row.returned_at.isoformat() if row.returned_at else None,
        # DEF-NOT-10665 (PO 2026-10-29, D1 A) — a failure a clerk already sent
        # on to a corrected address: *Retried to a new address*, and out of
        # *Needing attention*. Annotated on the list; read once for a lone row.
        "retried_to_new_address": _retried(row),
    }


def _retried(row: models.OutboundMessage) -> bool:
    annotated = getattr(row, "retried_to_new_address", None)
    if annotated is not None:
        return bool(annotated)
    from apps.notifications import attention

    return (
        models.OutboundMessage.objects.filter(pk=row.pk)
        .filter(attention.retried_to_new_address())
        .exists()
    )


def queue_page(rows: Any) -> list[dict[str, Any]]:
    """A PAGE of S8 rows, each carrying its account's human-facing NUMBER.

    ⛔ **`DEF-PAY-6344` — THE PO, ON THE DEPLOYED BUILD: *"this modal is showing
    db keys"*.** Payments → Summary → *Mark returned post* reads this list, and
    its Account column printed `01a07fa5-1034-71f7-995c-05da83d1c972` on every
    row, because `account_id` was the only account fact on the wire. B14 rule
    31 (PO 2026-08-30): *"no Databse ID on screen - that is a rule"*. The screen
    could not fix it by itself — the number was not served.

    ⚠ **`account_no` IS NOT PII, AND THAT IS WHY IT IS SAFE TO SERVE HERE.**
    `queue_row` withholds `recipient_snapshot` for BR-AUD-006's posture — a
    customer's NAME and full POSTAL ADDRESS. The screen's own exceptions note
    used that posture to justify printing the id; but an account number is
    neither a name nor an address, and the SENT TO column one cell away already
    prints `recipient_address`. The choice was never *"the id or the full
    name"*.

    ⛔ **ONE STATEMENT FOR THE PAGE, NEVER ONE PER ROW** (`customers_seam`'s
    box). The numbers are read for every id on the page at once and then
    stitched on by key — no join names both modules' tables.

    `deliveries_for_source` below does NOT call this: billing's delivery panel
    and payments' receipt resend read four columns of one bill's rows and no
    account label, so paying a statement there would buy nothing.
    """
    page = list(rows or [])
    numbers = customers_seam.account_numbers(row.account_id for row in page)
    served = []
    for row in page:
        body = queue_row(row)
        body["account_no"] = numbers.get(body["account_id"]) if body["account_id"] else None
        served.append(body)
    return served


def deliveries_for_source(source_type: str, source_id: Any) -> list[dict[str, Any]]:
    """Every queued delivery for ONE source record — a bill, a notice, a letter.

    PUBLISHED FOR BILLING (US-BIL-023/024). `outbound_messages` is this module's
    table and billing may not read it (B1), so the per-bill question is answered
    here and resolved BY NAME through `apps/billing/delivery_seam.py` — the same
    way that seam already resolves the channel election.

    **Why it did not exist until 2026-08-16, and what that cost.** `issue.py`
    has written a row here for every bill it issued since 2026-08-11, and the
    only reads were the S8 triage list (every row, all sources) and the summary.
    Nothing could ask *"where did THIS bill go?"*, so `GET /invoices/{id}`
    served `deliveries: null` and S30's delivery panel — which is built, and has
    been since the detail screen landed — rendered its absence branch on every
    bill. An engine that writes and a screen that reads, with no question
    between them.

    RETURNS `[]` FOR A BILL WITH NO ROWS, and that is a real and different
    answer from "the queue cannot be asked": a draft has never been queued
    because queueing happens at issue. The SEAM turns an unreachable module into
    `None`; an empty list from here means the queue was asked and had nothing,
    which for a draft is the truth.

    Ordered by channel then copy so a reprint (`copy_no > 0`) reads under its
    original rather than above it, and two channels always list in the same
    order on a screen a clerk reads twice.
    """
    if source_id is None:
        return []
    rows = models.OutboundMessage.objects.filter(
        tenant_id=_tenant_id(), source_type=source_type, source_id=source_id
    ).order_by("channel", "copy_no", "created_at", "id")
    return [queue_row(row) for row in rows]


def deliveries_for_sources(source_type: str, source_ids: Any) -> QuerySet:
    """Every queued delivery for a SET of source records, newest first — a
    QUERYSET, so the caller's paginator takes the page in SQL (`NFR-3`).

    PUBLISHED FOR CUSTOMERS (`CR-171-BRC10` P1.07, image 22 — a move-in
    request's *Messages* tab: Message · To · Channel · When · State). One
    service request's letters sit under SEVERAL source ids: the acknowledgement
    is keyed on the request, and every refusal, ask and approval on the
    timeline row recording it (`service_request_events` explains why). So the
    question is *every row for these ids*, which `deliveries_for_source` cannot
    ask in one statement. Serialise a page with `source_delivery_row`.
    """
    wanted = [str(one) for one in (source_ids or []) if one]
    return models.OutboundMessage.objects.filter(
        tenant_id=_tenant_id(), source_type=str(source_type), source_id__in=wanted
    ).order_by("-created_at", "-id")


def source_delivery_row(row: models.OutboundMessage) -> dict[str, Any]:
    """One row of `deliveries_for_sources`: `queue_row` plus the RECIPIENT'S
    NAME from the frozen envelope (`BR-TEN-017`).

    ⚠ **THE NAME IS SERVED HERE AND NOT ON `queue_row`, AND THE DIFFERENCE IS
    THE SURFACE.** `queue_row` feeds a nine-hundred-row platform list and keeps
    a customer's name off it (BR-AUD-006). This answers for ONE record a clerk
    already has open, whose own page already prints that person's name, and the
    drawn *To* column is the name — the address alone would leave it blank.
    Only the name travels; the postal lines in the snapshot do not.
    """
    body = queue_row(row)
    snapshot = row.recipient_snapshot if isinstance(row.recipient_snapshot, dict) else {}
    name = snapshot.get("name") or snapshot.get("display_name")
    body["recipient_display_name"] = str(name) if name else None
    return body


def template_pin_count(template_id: Any, version: Any) -> int:
    """How many queue rows pin THIS template version — `DEF-2496` / BR-NOT-025.

    PUBLISHED FOR BILLING, for the same reason and through the same door as
    `deliveries_for_source` above: `outbound_messages` is this module's table and
    billing may not read it (B1), so the question is answered here and resolved
    BY NAME through `apps/billing/delivery_seam.py`.

    ⚠ **`template_id` IS POLYMORPHIC AND NOTHING SAID SO UNTIL DEF-2496.**
    Measured on the development database: of 181 `outbound_messages` rows, 87
    carry a NOTIFICATION template's id and **94 carry a BILL template's id** —
    every one of those a `pdf_print` row whose `source_type` is `invoice`. So
    this same column answers for both stores, and a caller passing a bill
    template's id gets the printed-bill rows pinned to it.

    WHY BILLING NEEDED IT. `templates_service.pin_count` counted `invoices`
    ALONE, so a bill layout pinned by a printed bill and by no issued invoice
    read as UNPINNED and its delete was allowed by the very service that exists
    to refuse it. BR-NOT-025 says *any sent document*, and a printed bill is one.

    This is the READABLE half — it gives a refusal a number to name. The
    guarantee is `billing/0025`'s trigger, which counts this table in the engine
    where no caller can decline to ask.
    """
    if template_id is None or version is None:
        return 0
    return models.OutboundMessage.objects.filter(
        tenant_id=_tenant_id(), template_id=template_id, template_version=version
    ).count()


def receipt_on_record_payment_election() -> bool:
    """A15's "receipt on record-payment" election, for the tenant in context.

    PUBLISHED FOR PAYMENTS (CR-009 C-13 → BR-NOT-022, OQ-205 CLOSED — the four
    elections ship DEFAULT ON per the PO's own ruling). `notification_settings`
    is this module's table and payments may not read it (B1), so
    `apps/payments/receipts.py` resolves THIS callable by name at record time.
    Published from selectors because it is a READ, which is where this repo's
    seams look for one; the value itself lives with the other dispatch config
    (`dispatch_config.receipt_on_record_payment_election`) so there is one
    reader of the row, not two.
    """
    from apps.notifications import dispatch_config  # local: settings write path

    return dispatch_config.receipt_on_record_payment_election()


def row_or_404(message_id: Any) -> models.OutboundMessage:
    """One row of THIS tenant, or a 404 that cannot be told from any other.

    An unknown id, a malformed id and another tenant's id are ONE answer
    (HR-1 / 11b G4) — the body is byte-identical, so existence cannot be probed.
    US-NOT-013 TC-5 is exactly this: *"Re-queue via forged row ids from another
    tenant → Rejected, server-validated scope."*
    """
    try:
        row = queue_queryset().filter(pk=message_id).first()
    except (ValueError, TypeError, errors.ValidationError):
        row = None
    if row is None:
        raise errors.NotFoundError()
    return row


def notice_row(row: dict[str, Any], *, currency: str | None) -> dict[str, Any]:
    """One notice-history row, with its money figures CARRYING their currency.

    A notice states a balance and a reconnect fee to a customer, and the same
    figure has to read the same on every surface that repeats it. So every money
    member here is (a) a string at NUMERIC(18,6) fidelity and (b) accompanied by
    `currency` — never a bare number a reader denominates for themselves.

    `certified_mail` is lifted out of the generator's `detail` payload onto the
    row because it is the whole point of the 48-hour tier (BR-CUS-039) and a
    register that made a reader open a JSON blob to find it is not a register.
    """
    detail = dict(row.get("detail") or {})
    certified = bool(detail.get("certified_mail")) or row.get("tier") == TIER_FINAL_48_HOUR
    return {
        "id": row.get("id"),
        "account_id": row.get("account_id"),
        "notice_type": row.get("notice_type"),
        "tier": row.get("tier"),
        "channel": row.get("channel"),
        "outcome": row.get("outcome"),
        "skip_reason": row.get("skip_reason"),
        "outbound_message_id": row.get("outbound_message_id"),
        "occurred_on": row.get("occurred_on"),
        "certified_mail": certified,
        #: US-NOT-009 TC-2 puts the certified NUMBER on the queue row from the
        #: provider response. No provider adapter exists on any channel (PO
        #: 2026-08-15), so it is NULL with its reason beside it — never a
        #: fabricated tracking number on a legal record.
        "certified_number": detail.get("certified_no"),
        "cut_date": detail.get("cut_date"),
        "template_version": detail.get("template_version"),
        # ── money (rule 2) ──────────────────────────────────────────────
        "reconnect_fee": money_str(detail.get("reconnect_fee")),
        "balance": money_str(detail.get("balance")),
        "currency": currency,
        "detail": detail,
    }


# ── CR-075 wave Q′ · the read runbook 22 makes (US-RBS-034) ────────────────
#
# ⚠ **IT LIVES HERE BECAUSE `G20` RESOLVES `selectors` AND `services` AND
# NOTHING ELSE.** The facts themselves are `delivery_ops`', which is a THIRD
# kind — the `13-selector-inventory.md` W-1 shape, where a real, tested,
# correct function is invisible to a seam and answers `None`, which reads as
# *no findings*. So this composes `delivery_ops`' own two reads rather than
# querying the table a second time: two counters over one table is how a
# dashboard and a runbook come to disagree about the same morning.


def undeliverable_feedback(*, limit: int = 2000) -> dict[str, Any]:
    """Every message this utility has been told did not arrive — and how it knows.

    Two sources, and they are different KINDS of fact, which is why the answer
    names which is which rather than pooling them:

    * **A provider fact** — `failed` or `bounced` on the row, written by an ESP
      or a carrier through its own feedback door.
    * **A person's observation** — `returned_at`, stamped when a clerk marks a
      paper letter returned (`US-NOT-014` TC-1). Only paper can be returned:
      *"an email that did not arrive comes back as a provider BOUNCE on a
      webhook … not something a clerk can observe about an envelope."*

    ⚠ **`not_reported` IS THE LOAD-BEARING HALF OF THIS ANSWER AND IT IS NOT
    DECORATION.** `delivery_ops.queue_health` records the reason in as many
    words: *"`delivered` and `bounced` are PROVIDER facts … and no provider
    adapter exists on any channel, print included: delivery is out of this
    release by PO ruling (2026-08-15). Their counts are structurally zero here
    and must be rendered as NOT REPORTED, never as zero."* A caller that read
    an empty list as *nothing bounced today* would report a clean morning over
    a channel nobody is listening to — the exact shape hard-won law 7 calls a
    declared blind spot with no number attached. So the count of what could not
    be reported travels beside the count of what was.
    """
    tenant_id = _tenant_id()
    from apps.notifications import delivery_ops

    items: list[dict[str, Any]] = []
    for row in delivery_ops.failures(limit=limit):
        items.append(
            {
                "message_id": str(row.pk),
                "account_id": str(row.account_id) if row.account_id else None,
                "channel": row.channel,
                "status": row.status,
                "told_by": "provider",
                "recipient_address": row.recipient_address,
                "attempts": row.attempts,
                "provider_text": row.last_error,
                "source_type": row.source_type,
                "template_code": row.template_code,
                "at": row.last_attempt_at.isoformat() if row.last_attempt_at else None,
            }
        )
    for row in delivery_ops.returned_mail_read_model(limit=limit):
        items.append(
            {
                "message_id": row["message_id"],
                "account_id": row["account_id"],
                "channel": row["channel"],
                "status": models.STATUS_SENT,
                "told_by": "a person",
                "recipient_address": None,
                "attempts": None,
                "provider_text": None,
                "source_type": row["source_type"],
                "template_code": row["template_code"],
                "at": row["returned_at"].isoformat() if row["returned_at"] else None,
            }
        )

    queued = models.OutboundMessage.objects.filter(tenant_id=tenant_id)
    return {
        "items": items,
        "messages_on_file": queued.count(),
        #: The statuses no adapter on this deployment can write. A runbook draws
        #: this as *not reported* and never as a zero (see the docstring).
        "not_reported": list(delivery_ops.UNPOPULATED_STATUSES),
        "channels_with_traffic": sorted(
            {row["channel"] for row in queued.values("channel").distinct()}
        ),
    }


# ════════════════════════════════════════════════════════════════════════════
# CR-075 WAVE R′ — *HAVE WE ALREADY TOLD THEM?* (`RB-111`, `US-RBS-023`)
# ════════════════════════════════════════════════════════════════════════════


def queued_source_ids(source_type: str, source_ids: Any) -> dict[str, dict[str, Any]]:
    """Which of these source ids ALREADY HAVE a queue row — one query for all.

    `deliveries_for_source` above answers the same question for ONE id and is
    the right shape for a bill's detail screen. The leak alert asks it for
    **1,840 meters × the days in its window** at 07:30 every morning, and one
    query per id would be twelve thousand of them; this is the bulk form and
    the whole reason it exists.

    ⚠ **THIS IS THE ONLY DURABLE RECORD IN THE PRODUCT THAT WE TOLD SOMEBODY
    SOMETHING** (`DEF-RBS-4331`, and the `flag_meter` port's own docstring —
    *"there is no column anywhere to hold 'told about a leak on <date>'"*). A
    runbook's *once per meter every 7 days* guard therefore reads OUR OWN
    OUTBOX rather than a flag on the meter. That is a read of this module's own
    table through this module's own selector, which is what a seam is for; the
    forbidden substitute is writing a NOTE, and `BR-RBS-040` makes a note an
    engine act rather than a port precisely so nobody reaches for it here.

    ⚠ **IT IS KEYED ON `source_id`, WHICH THE CALLER MINTS DETERMINISTICALLY.**
    `apps/notifications/runbook_ports.runbook_source_id` derives one from
    `runbook key | subject | discriminator`, so *"did we alert meter WM-04471 on
    the 4th"* is a question with a computable answer and no new column.

    Returns `{source_id: {"channels": [...], "statuses": [...], "queued_on":
    "YYYY-MM-DD"}}`, and an id with no row is **ABSENT** rather than present
    with an empty value — the same posture as `last_issued_invoice_dates`, so a
    caller's `in` test and its `.get()` agree.
    """
    wanted = [str(one) for one in (source_ids or []) if one]
    if not wanted:
        return {}
    rows = (
        models.OutboundMessage.objects.filter(
            tenant_id=_tenant_id(), source_type=str(source_type), source_id__in=wanted
        )
        .values("source_id", "channel", "status", "created_at")
        .order_by("created_at", "id")
    )
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row["source_id"])
        seen = out.setdefault(key, {"channels": [], "statuses": [], "queued_on": None})
        if row["channel"] not in seen["channels"]:
            seen["channels"].append(row["channel"])
        if row["status"] not in seen["statuses"]:
            seen["statuses"].append(row["status"])
        if seen["queued_on"] is None:
            seen["queued_on"] = row["created_at"].date().isoformat()
    return out


def delivery_addresses_for_messages(message_ids: Any) -> dict[str, dict[str, Any]]:
    """WHERE each of these letters was addressed — one query for a page.

    PUBLISHED FOR PAYMENTS' needs-attention list (`DEF-PAY-6342`, PO ruling
    2026-09-23: *"ensure you update correct address - mailing or service"*). A
    returned letter went either to the account's MAILING address or to its
    SERVICE address, and the clerk's clear step sends them to a different door
    for each — so the list has to say which. The answer is the queue row's own
    frozen snapshot (`BR-TEN-017`), never a re-resolution: what the envelope
    said when it was posted, not where the account points today.

    ⚠ **ONLY TWO FACTS TRAVEL — the one-line address and its `source`.** The
    snapshot also holds the customer's name and every postal line, and this
    module's own list does not serve it for exactly that reason (the trailer's
    exception (2)); a page of returned letters needs *which address*, not the
    envelope.

    `source` is None for a letter queued before the service-address fallback
    existed — it carried no address at all — and `address` is None beside it.
    An id with no row is ABSENT, as in `queued_source_ids` above.
    """
    wanted = [str(one) for one in (message_ids or []) if one]
    if not wanted:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in models.OutboundMessage.objects.filter(
        tenant_id=_tenant_id(), pk__in=wanted
    ).values("id", "recipient_address", "recipient_snapshot"):
        snapshot = row["recipient_snapshot"] if isinstance(row["recipient_snapshot"], dict) else {}
        out[str(row["id"])] = {
            "address": row["recipient_address"],
            "source": snapshot.get("source") if row["recipient_address"] else None,
        }
    return out


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-013@6c2a90f (the same packet `apps/notifications/delivery_ops.py` was cut from — 04-docs/05-modules/10-notifications/06-epics/EP-NOT-04-delivery-ops.md US-NOT-013 §1/§3/§5 + its capability matrix · 10-notifications/02-business-rules.md · 10-notifications/04-flows.md §4 + §6 · 08-qa/01-e2e/journeys/J17-delivery-life.md — because this is that story's LIST half and a second packet hash would make one story look like two)
# generated: 2026-08-16 by story-coder (DEF-128 notifications API lane)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_def_128_notifications_api.py
# exceptions: (1) NO `delivered`/`bounced` ROW CAN EVER APPEAR in this list —
#         both are provider facts and no provider adapter exists on any channel
#         (PO ruling 2026-08-15). The STATUSES are filterable because the
#         vocabulary is BR-NOT-005's; the summary endpoint reports the two as
#         unpopulated so a screen renders "not reported" rather than zero.
#         (2) `recipient_snapshot` IS NOT SERVED on the list row. It carries the
#         customer's name and full postal address and nine hundred of them is
#         not what a triage screen needs (BR-AUD-006's posture).
#         (3) NO AGE / NO "DAYS QUEUED" COLUMN. It would need a clock, and
#         BR-TEN-043 makes the business date an input; the screen has
#         `queued_at` and can subtract the tenant's own today.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
