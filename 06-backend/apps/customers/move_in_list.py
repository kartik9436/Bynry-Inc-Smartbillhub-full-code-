# ── Trace ──────────────────────────────────────────────
# Change:   CR-171-BRC10 P1.04 — the Move-ins list serves every status a move-in
#           can be in: requests, drafts, jobs, committed move-ins, cancelled.
# Rules:    CR-171 §6.1 (the status model — our judgment, recorded) ·
#           §2 S3/S4 (requests and finished move-ins join the list) ·
#           BR-CUS-1077 (approval raises a job, no account) · BR-SHL-048 (a
#           draft joins to nothing) · BR-CUS-055 (status CLASS, never label) ·
#           NFR-3 / NFR-5 (server paging, no cap) · CLAUDE.md hard rules 1, 8
# Tests:    06-backend/tests/test_cr171_p1_04_move_ins_list.py
# ───────────────────────────────────────────────────────
"""The Move-ins list of the redesign (image 01, 02) — ONE status per row.

**ONE FUNCTION DECIDES A ROW'S STATUS** (§6.1), and the list's pill, the record
page's chip, the Status filter and the five tiles all read it, so they can
never disagree (the `DEF-127` shape). The status is computed TWICE BY
CONSTRUCTION — once as a SQL `CASE` so the filter, the tiles and the page are
decided by the database (`NFR-3`), once as `status_of` for a single object —
and `tests/test_cr171_p1_04_move_ins_list.py` holds every served row's status
equal to the filter bucket it was selected by. That test is what makes two
spellings one rule.

| Status | Row | Rule |
|---|---|---|
| `to_approve` | `service_requests` `submitted`/`under_review`, resolved *served, vacant* | `move_in_request.request_status` |
| `waiting_on_customer` | the same, `more_info` | ″ |
| `declined` | the same, `refused` (a reopen moves it back — `OQ-CUS-12789` (a), lane FLOW) | ″ |
| `not_started` | `move_in_jobs` `pending` with no draft; a legacy draft ACCOUNT with no move record | `BR-CUS-1077` |
| `draft` | a `move_in` `wizard_parks` row — or a pending job whose request a draft names | `BR-SHL-048` |
| `waiting_on_a_read` | a `move_records` move-in on an open account whose unit has a meter with no read on/after the move-in date | `move_reads.unit_reads_cell` |
| `completed` | any other `move_records` move-in | |
| `cancelled` | `move_in_jobs` `cancelled`, or a move-in whose account closed before the day it opened (`move_in_cancel.is_cancelled`, P1.22) | S2 |

⚠ **A PARKED DRAFT FOR A REQUEST IS NOT ITS OWN ROW** (§9.REQ). A draft whose
`service_request_id` (in `subject_ref` — the Edit door — or in `values` — the
seven-step wizard) names a request that is still a request row IS that
request's edit; one naming the request of a pending job IS that job, which then
reads `draft`. Only an unlinked draft (or one whose request has gone on to be
completed or withdrawn) is a row of its own.

⚠ **`waiting_on_a_read` NAMES A READ AND NOTHING ELSE — §6.1 AMENDED.** §6.1
also said *"or whose move-in visit is open"*. An open visit is not a missing
reading, and Work publishes no set-wise read of open visits, so judging it for
the filter would be one Work call per move-in in the tenant. The visit is the
record page's *Still open* row (P1.05) instead. Decision log 2026-10-05,
MVI-LIST (2).

⚠ **A MOVE-IN WHOSE ACCOUNT HAS CLOSED IS `completed` WITHOUT ASKING METERING.**
The tenancy it opened is over; a reading owed to it is the move-out's final
read, which the Move-outs list owns. This also bounds the read sweep to LIVE
move-ins.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from django.db.models import Case, Count, DateField, Exists, F, OuterRef, Q, TextField, Value, When
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Cast, Coalesce

from apps.customers import models, move_in_jobs, move_in_request, move_reads, moves, seams, transfers
from apps.customers import service_request as sr_rules
from core import pagination

# ═══════════════════════════════════════════════════════════════════════════
# 1 · THE STATUS VOCABULARY
# ═══════════════════════════════════════════════════════════════════════════
STATUS_TO_APPROVE = move_in_request.STATUS_TO_APPROVE
STATUS_WAITING_ON_CUSTOMER = move_in_request.STATUS_WAITING_ON_CUSTOMER
STATUS_DECLINED = move_in_request.STATUS_DECLINED
STATUS_NOT_STARTED = "not_started"
STATUS_DRAFT = "draft"
STATUS_WAITING_ON_A_READ = "waiting_on_a_read"
STATUS_COMPLETED = "completed"
STATUS_CANCELLED = "cancelled"

#: The eight, in the order the details view and the pill tones are drawn.
STATUSES: tuple[str, ...] = (
    STATUS_TO_APPROVE,
    STATUS_WAITING_ON_CUSTOMER,
    STATUS_DECLINED,
    STATUS_NOT_STARTED,
    STATUS_DRAFT,
    STATUS_WAITING_ON_A_READ,
    STATUS_COMPLETED,
    STATUS_CANCELLED,
)

#: Image 02's Status radio: *All · To approve · Open · Completed*. A group is
#: a set of statuses; `f.status` takes a group OR a single status, so the
#: details view's eight words are each filterable too. `declined` and
#: `cancelled` are in no drawn group — they show under *All* and by name.
STATUS_GROUP_ALL = "all"
STATUS_GROUPS: dict[str, tuple[str, ...]] = {
    "to_approve": (STATUS_TO_APPROVE, STATUS_WAITING_ON_CUSTOMER),
    "open": (STATUS_NOT_STARTED, STATUS_DRAFT, STATUS_WAITING_ON_A_READ),
    "completed": (STATUS_COMPLETED,),
    "closed": (STATUS_DECLINED, STATUS_CANCELLED),
}
#: ⚠ `to_approve` is BOTH a group and a status; as a filter value it is the
#: GROUP (the drawn radio), which contains the status of the same name.

#: ⚠ **A CANCELLED COMMITTED MOVE-IN IS READ BY `move_in_cancel.is_cancelled`
#: (lane FLOW's ONE predicate: the account closed before the day it opened),
#: never by a close reason.** This first read `close_reason = "move_in_cancelled"`
#: — a value `ck_accounts_close_reason` refuses and nothing writes, so no
#: cancelled move-in could ever read *Cancelled* (`DEF-CUS-9713`).

ROW_KIND_REQUEST = "request"
ROW_KIND_MOVE_RECORD = "move_record"

#: The row's one icon (image 01): Review · Start · Resume · View.
ACTION_REVIEW = "review"
ACTION_START = "start"
ACTION_RESUME = "resume"
ACTION_VIEW = "view"
_ACTION_BY_STATUS: dict[str, str] = {
    STATUS_TO_APPROVE: ACTION_REVIEW,
    STATUS_WAITING_ON_CUSTOMER: ACTION_REVIEW,
    STATUS_DECLINED: ACTION_VIEW,
    STATUS_NOT_STARTED: ACTION_START,
    STATUS_DRAFT: ACTION_RESUME,
    STATUS_WAITING_ON_A_READ: ACTION_VIEW,
    STATUS_COMPLETED: ACTION_VIEW,
    STATUS_CANCELLED: ACTION_VIEW,
}

#: The two filter dimensions the redesign declares (image 02), plus the legacy
#: `state` the seven-step screen still sends until P2.01 replaces it.
FILTERS: tuple[str, ...] = ("status", "service", "state")

SEARCH_HINT = "Search customer, unit, MVI…"
SEARCH_LEGS: tuple[str, ...] = ("customer", "unit", "address", "reference", "account_no", "request_no")

#: A request's state → status, read off REQ's ONE function rather than copied.
_REQUEST_STATUS_BY_STATE: dict[str, str] = {
    state: status
    for state in models.ServiceRequest.STATES
    if (status := move_in_request.request_status(state)) is not None
}
REQUEST_ROW_STATES: tuple[str, ...] = tuple(_REQUEST_STATUS_BY_STATE)

#: A request whose clerk has already decided it is ANOTHER kind of job is not a
#: move-in row, however its address resolved.
_OTHER_OUTCOMES: tuple[str, ...] = (
    models.ServiceRequest.OUTCOME_NEW_CONNECTION,
    models.ServiceRequest.OUTCOME_MOVE_OUT,
    models.ServiceRequest.OUTCOME_TRANSFER,
    models.ServiceRequest.OUTCOME_DISCONNECT,
    models.ServiceRequest.OUTCOME_CLOSED,
)

#: ⚠ **EVERY COLUMN BUT `id` IS AN ANNOTATION, ON EVERY ARM, ON PURPOSE.**
#: Django orders a `values()` SELECT as model fields first and annotations
#: after, so an arm where `account_no` is a real column (accounts) and one
#: where it is a `Value(None)` (jobs) put it in different POSITIONS — and a
#: `UNION` matches by position. SQLite does not care; PostgreSQL refused it
#: (*"UNION types date and text cannot be matched"*), measured 2026-10-05 on
#: `config.settings.pgtest`. Prefixed names cannot collide with a field.
#: ⚠ **AND A NULL IS CAST, NEVER BARE.** Under `SELECT DISTINCT` PostgreSQL
#: resolves an untyped `NULL` to `text` before the `UNION` sees it, so a draft's
#: NULL move-in date met the other arms' `date` and was refused the same way.
UNION_COLUMNS: tuple[str, ...] = (
    "id",
    "row_kind",
    "row_status",
    "u_created",
    "u_account_no",
    "u_move_in_on",
)


def _tenant_id() -> Any:
    return move_reads._tenant_id()


def statuses_for_filter(value: Any) -> tuple[str, ...] | None:
    """`f.status` → the statuses it selects; None = no filter; () = nothing.

    BR-SHL-011: an unknown value selects NOTHING rather than everything —
    falling back to *no filter* would silently show a clerk more than asked.
    """
    raw = str(value or "").strip()
    if not raw or raw == STATUS_GROUP_ALL:
        return None
    if raw in STATUS_GROUPS:
        return STATUS_GROUPS[raw]
    if raw in STATUSES:
        return (raw,)
    return ()


def services_for_filter(value: Any) -> tuple[str, ...]:
    """`f.service=water,sewer` → the codes. A row matches if it takes ANY of
    them (image 02's ticks are an OR, as every tick list in this product is)."""
    return tuple(code.strip() for code in str(value or "").split(",") if code.strip())


# ═══════════════════════════════════════════════════════════════════════════
# 2 · WHICH DRAFTS BELONG TO A REQUEST OR A JOB (bounded: request-linked drafts)
# ═══════════════════════════════════════════════════════════════════════════
def _park_link_expr() -> Any:
    return Coalesce(
        KeyTextTransform("service_request_id", "subject_ref"),
        KeyTextTransform("service_request_id", "values"),
        output_field=TextField(),
    )


def _parks() -> Any:
    return seams.wizard_park_queryset(flow=moves.KIND_MOVE_IN)


def _linked_request_ids() -> dict[str, str]:
    """`{request_id: park_id}` for every move-in draft that names a request.

    ONE column of the drafts that carry a link — not the drafts' values — so
    the read is the size of the request-linked drafts, never of a blob.
    Newest draft wins when two name one request.
    """
    out: dict[str, str] = {}
    rows = (
        _parks()
        .annotate(link=_park_link_expr())
        .exclude(link__isnull=True)
        .exclude(link="")
        .order_by("parked_at")
        .values_list("id", "link")
    )
    for park_id, link in rows:
        out[str(link)] = str(park_id)
    return out


class _Context:
    """The facts every arm and every row shares, read ONCE per list call."""

    def __init__(self, *, as_of: date) -> None:
        self.as_of = as_of
        self.linked = _linked_request_ids()
        linked_ids = list(self.linked)
        self.request_row_ids: set[str] = (
            {str(i) for i in _requests_base().filter(id__in=linked_ids).values_list("id", flat=True)}
            if linked_ids
            else set()
        )
        self.drafted_job_request_ids: set[str] = (
            {
                str(i)
                for i in move_in_jobs.pending_queryset()
                .filter(request_id__in=linked_ids)
                .values_list("request_id", flat=True)
            }
            if linked_ids
            else set()
        )
        self.suppressed_links: list[str] = sorted(
            self.request_row_ids | self.drafted_job_request_ids
        )
        self.reads_unwired = False
        self.waiting_record_ids, self.reads_unjudged = _records_waiting_on_a_read()
        if self.waiting_record_ids is None:
            self.reads_unwired = True
            self.waiting_record_ids = set()


# ═══════════════════════════════════════════════════════════════════════════
# 3 · WAITING ON A READ — every LIVE move-in, judged in one sweep
# ═══════════════════════════════════════════════════════════════════════════
def _records_base() -> Any:
    rows = moves.MoveRecord.objects.filter(tenant_id=_tenant_id(), kind=moves.KIND_MOVE_IN)
    return transfers.exclude_transfer_halves(rows, field="account_id")


def _records_waiting_on_a_read() -> tuple[set[str] | None, int]:
    """`(record ids waiting on a read, how many could not be judged)`.

    `None` for the set means metering publishes no set-wise read here, so no
    move-in can be judged and none is CALLED waiting — the response says so
    (`reads_unwired`) rather than letting *completed* stand for *unknown*.
    Cost: one `move_records` query, `assets_on_units`' three, one grouped
    `MAX(read_at)` — whatever the tenant's size. Measured in the CR (§9.LIST).
    """
    live = list(
        _records_base()
        .filter(account__closed_at__isnull=True)
        .values_list("id", "account__unit_id", "effective_on")
    )
    if not live:
        return set(), 0
    answers = seams.latest_read_dates_for_units({str(u) for _i, u, _d in live if u})
    if answers is None:
        return None, len(live)
    waiting: set[str] = set()
    unjudged = 0
    for record_id, unit_id, effective_on in live:
        cell = move_reads.unit_reads_cell(
            answers.get(str(unit_id)) if unit_id else None,
            measured_from=effective_on,
            final=False,
        )
        if cell["state"] == move_reads.READS_STATE_DUE:
            waiting.add(str(record_id))
        elif cell["state"] is None and cell.get("meters_total") != 0:
            unjudged += 1
    return waiting, unjudged


# ═══════════════════════════════════════════════════════════════════════════
# 4 · THE FIVE ARMS — each a queryset publishing UNION_COLUMNS
# ═══════════════════════════════════════════════════════════════════════════
#: The resolution kinds that make a request a MOVE-IN request — read off FLOW's
#: ONE predicate (`service_request.suggests_move_in`, CR §9.FLOW), never a
#: second classifier, so the list and the Reopen door cannot disagree.
MOVE_IN_RESOLUTIONS: tuple[str, ...] = tuple(
    kind for kind in models.ServiceRequest.RESOLUTIONS if sr_rules.suggests_move_in(kind)
)


def _requests_base() -> Any:
    return models.ServiceRequest.objects.filter(
        tenant_id=_tenant_id(),
        state__in=REQUEST_ROW_STATES,
        resolution_kind__in=MOVE_IN_RESOLUTIONS,
    ).exclude(outcome__in=_OTHER_OUTCOMES)


def _request_status_case() -> Case:
    return Case(
        *[When(state=state, then=Value(status)) for state, status in _REQUEST_STATUS_BY_STATE.items()],
        default=Value(None),
        output_field=TextField(),
    )


def _term(q: str | None) -> str | None:
    from apps.customers import selectors

    term = (q or "").strip()
    return term if len(term) >= selectors.MIN_SEARCH_CHARS else None


def _request_ids_matching(term: str) -> Any:
    return models.ServiceRequest.objects.filter(
        tenant_id=_tenant_id(), request_no__icontains=term
    ).values("id")


def _requests_arm(*, term, services, legacy_state) -> Any:
    rows = _requests_base().annotate(
        row_kind=Value(ROW_KIND_REQUEST, output_field=TextField()),
        row_status=_request_status_case(),
        u_account_no=Cast(Value(None), output_field=TextField()),
        u_move_in_on=F("requested_start"),
    )
    if legacy_state:
        return rows.none()
    if term:
        matches = Q(applicant_name__icontains=term) | Q(request_no__icontains=term)
        unit_ids = [str(u) for u in seams.unit_ids_matching(term)]
        if unit_ids:
            matches |= Q(resolved_unit_id__in=unit_ids)
        rows = rows.filter(matches)
    if services:
        rows = rows.filter(
            Exists(
                models.ServiceRequestService.objects.filter(
                    request_id=OuterRef("pk"), service__code__in=services
                )
            )
        )
    return rows


def _jobs_arm(*, term, services, legacy_state, ctx: _Context) -> Any:
    rows = move_in_jobs.MoveInJob.objects.filter(
        tenant_id=_tenant_id(),
        state__in=(move_in_jobs.STATE_PENDING, move_in_jobs.STATE_CANCELLED),
    ).annotate(
        row_kind=Value(move_reads.ROW_KIND_PENDING_JOB, output_field=TextField()),
        row_status=Case(
            When(state=move_in_jobs.STATE_CANCELLED, then=Value(STATUS_CANCELLED)),
            *(
                [
                    When(
                        request_id__in=sorted(ctx.drafted_job_request_ids),
                        then=Value(STATUS_DRAFT),
                    )
                ]
                if ctx.drafted_job_request_ids
                else []
            ),
            default=Value(STATUS_NOT_STARTED),
            output_field=TextField(),
        ),
        u_account_no=Cast(Value(None), output_field=TextField()),
        u_move_in_on=F("request__requested_start"),
    )
    if legacy_state:
        if legacy_state != move_reads.MOVE_IN_STATE_PENDING:
            return rows.none()
        rows = rows.filter(state=move_in_jobs.STATE_PENDING)
    if term:
        matches = (
            Q(request__applicant_name__icontains=term)
            | Q(request__request_no__icontains=term)
            | Q(move_no__icontains=term)
        )
        unit_ids = [str(u) for u in seams.unit_ids_matching(term)]
        if unit_ids:
            matches |= Q(request__resolved_unit_id__in=unit_ids)
        rows = rows.filter(matches)
    if services:
        rows = rows.filter(
            Exists(
                models.ServiceRequestService.objects.filter(
                    request_id=OuterRef("request_id"), service__code__in=services
                )
            )
        )
    return rows


def _parks_arm(*, term, services, legacy_state, ctx: _Context) -> Any:
    rows = _parks().annotate(link=_park_link_expr())
    if ctx.suppressed_links:
        rows = rows.filter(Q(link__isnull=True) | ~Q(link__in=ctx.suppressed_links))
    rows = rows.annotate(
        row_kind=Value(move_reads.ROW_KIND_PARKED_MOVE_IN, output_field=TextField()),
        row_status=Value(STATUS_DRAFT, output_field=TextField()),
        u_account_no=Cast(Value(None), output_field=TextField()),
        u_move_in_on=Cast(Value(None), output_field=DateField()),
    )
    if legacy_state:
        if legacy_state == move_reads.MOVE_IN_STATE_IN_PROGRESS:
            rows = rows.filter(waiting_on="")
        elif legacy_state == move_reads.MOVE_IN_STATE_PARKED:
            rows = rows.exclude(waiting_on="")
        else:
            return rows.none()
    if term:
        rows = rows.filter(Q(subject_label__icontains=term) | Q(reference__icontains=term))
    if services:
        # The draft's ticks are a JSON list of codes; matched on the quoted code
        # inside its text, which reads the same on PostgreSQL and SQLite. A
        # draft with no ticks yet cannot answer and is not matched.
        rows = rows.annotate(svc=KeyTextTransform("services", "values"))
        match = Q()
        for code in services:
            match |= Q(svc__contains=f'"{code}"')
        rows = rows.filter(match)
    return rows


def _agreement_on(account_ref: str, services: tuple[str, ...]) -> Exists:
    return Exists(
        models.ServiceAgreement.objects.filter(
            account_id=OuterRef(account_ref), service_point__service__code__in=services
        )
    )


def _accounts_arm(*, term, services, legacy_state, as_of: date) -> Any:
    """The legacy BR-CUS-018 draft accounts — `not_started`. One that already
    carries a move-in record is that record's row, never a second one."""
    rows = (
        move_reads.move_ins_queryset(
            q=term, filters={"state": legacy_state} if legacy_state else None, as_of=as_of
        )
        .order_by()
        .exclude(
            Exists(
                moves.MoveRecord.objects.filter(
                    account_id=OuterRef("pk"), kind=moves.KIND_MOVE_IN
                )
            )
        )
        .annotate(
            row_kind=Value(move_reads.ROW_KIND_ACCOUNT, output_field=TextField()),
            row_status=Value(STATUS_NOT_STARTED, output_field=TextField()),
            u_account_no=F("account_no"),
            u_move_in_on=F("opened_at"),
        )
    )
    if services:
        rows = rows.filter(_agreement_on("pk", services))
    return rows


def _records_arm(*, term, services, legacy_state, ctx: _Context) -> Any:
    waiting = sorted(ctx.waiting_record_ids)
    rows = _records_base().annotate(
        row_kind=Value(ROW_KIND_MOVE_RECORD, output_field=TextField()),
        row_status=Case(
            # `DEF-CUS-9713` — `move_in_cancel.is_cancelled` in SQL: the account
            # closed BEFORE the day it opened. Held equal to the predicate by
            # `test_a_committed_move_in_cancelled_through_the_cancel_door…`.
            When(
                account__closed_at__lt=F("account__opened_at"),
                then=Value(STATUS_CANCELLED),
            ),
            # `DEF-CUS-10126` — `record_is_cancelled`'s second half: a move-in
            # that REOPENED an account and was cancelled gives the account back
            # its earlier tenancy, so it closes before THIS move-in's day.
            When(
                reopening__isnull=False,
                account__closed_at__lt=F("effective_on"),
                then=Value(STATUS_CANCELLED),
            ),
            *([When(id__in=waiting, then=Value(STATUS_WAITING_ON_A_READ))] if waiting else []),
            default=Value(STATUS_COMPLETED),
            output_field=TextField(),
        ),
        u_account_no=F("account__account_no"),
        # `DEF-CUS-9790` — the account's start, which *Change move-in date*
        # moves; the record is never updated (BR-CUS-152).
        u_move_in_on=Case(
            # `DEF-CUS-10126` — a cancelled move-in that REOPENED an account:
            # the account has its earlier tenancy's dates back, so the move-in
            # keeps the date it was committed as (`move_in_date_of`).
            When(
                reopening__isnull=False,
                account__closed_at__lt=F("effective_on"),
                then=F("effective_on"),
            ),
            default=Coalesce(F("account__opened_at"), F("effective_on")),
            output_field=DateField(),
        ),
    )
    if legacy_state:
        return rows.none()
    if term:
        matches = (
            Q(move_no__icontains=term)
            | Q(account__account_no__icontains=term)
            | Q(account__customeraccount__customer__display_name__icontains=term)
            | Q(account__customeraccount__customer__customer_no__icontains=term)
            | Q(request_id__in=_request_ids_matching(term))
        )
        unit_ids = [str(u) for u in seams.unit_ids_matching(term)]
        if unit_ids:
            matches |= Q(account__unit_id__in=unit_ids)
        rows = rows.filter(matches)
    if services:
        rows = rows.filter(_agreement_on("account_id", services))
    return rows


def _arms(*, q, filters, ctx: _Context) -> list[Any]:
    filters = filters or {}
    term = _term(q)
    services = services_for_filter(filters.get("service"))
    legacy_state = str(filters.get("state") or "").strip() or None
    statuses = statuses_for_filter(filters.get("status"))
    arms = [
        _requests_arm(term=term, services=services, legacy_state=legacy_state),
        _jobs_arm(term=term, services=services, legacy_state=legacy_state, ctx=ctx),
        _parks_arm(term=term, services=services, legacy_state=legacy_state, ctx=ctx),
        _accounts_arm(term=term, services=services, legacy_state=legacy_state, as_of=ctx.as_of),
        _records_arm(term=term, services=services, legacy_state=legacy_state, ctx=ctx),
    ]
    out = []
    for arm in arms:
        if statuses is not None:
            arm = arm.filter(row_status__in=list(statuses)) if statuses else arm.none()
        arm = arm.annotate(u_created=F("created_at"))
        out.append(arm.order_by().values(*UNION_COLUMNS).distinct())
    return out


SORTS: dict[str, tuple[Any, ...]] = {
    "created": ("u_created", "id"),
    "move_in_date": ("u_move_in_on", "id"),
    "account": ("u_account_no", "id"),
}
DEFAULT_SORT = "created"


def page_keys(*, q, filters, sort, dir, page, per, ctx: _Context) -> tuple[int, list[tuple[str, str, str]]]:
    """`(total, [(row_kind, id, status), …])` — ONE ordered window, in SQL."""
    first, *rest = _arms(q=q, filters=filters, ctx=ctx)
    combined = first.union(*rest).order_by(
        *pagination.order_terms(sort, dir, columns=SORTS, default=DEFAULT_SORT)
    )
    total = combined.count()
    start = (page - 1) * per
    return total, [
        (str(row["row_kind"]), str(row["id"]), str(row["row_status"]))
        for row in combined[start : start + per]
    ]


# ═══════════════════════════════════════════════════════════════════════════
# 5 · THE FIVE TILES (image 01) — over the whole list, never the page
# ═══════════════════════════════════════════════════════════════════════════
#: The statuses *Starting this week* counts: everything not finished or
#: closed. A declined request and a completed move-in are not "starting".
STARTING_STATUSES: tuple[str, ...] = STATUS_GROUPS["to_approve"] + STATUS_GROUPS["open"]


def tiles(ctx: _Context) -> dict[str, Any]:
    counts = {status: 0 for status in STATUSES}
    starting = 0
    week_end = ctx.as_of + timedelta(days=move_reads.WEEK_DAYS)
    for arm in _arms(q=None, filters=None, ctx=ctx):
        for row in arm.order_by().values("row_status").annotate(n=Count("id")).values_list("row_status", "n"):
            status, n = row
            if status in counts:
                counts[status] += n
        starting += (
            arm.filter(
                row_status__in=list(STARTING_STATUSES),
                u_move_in_on__gte=ctx.as_of,
                u_move_in_on__lte=week_end,
            )
            .order_by()
            .count()
        )
    return {
        "to_approve": counts[STATUS_TO_APPROVE],
        "not_started": counts[STATUS_NOT_STARTED],
        "drafts": counts[STATUS_DRAFT],
        "starting_this_week": starting,
        "waiting_on_a_read": counts[STATUS_WAITING_ON_A_READ],
        "by_status": counts,
        "reads_unjudged": ctx.reads_unjudged,
        "reads_unwired": ctx.reads_unwired,
        "starting_basis": {
            "statuses": list(STARTING_STATUSES),
            "window_days": move_reads.WEEK_DAYS,
            "note": "drafts carry no date the list can sort or count until resumed",
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# 6 · THE ROWS — the existing builders, plus the redesign's cells
# ═══════════════════════════════════════════════════════════════════════════
def _services_for_requests(request_ids: list[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    if not request_ids:
        return out
    for request_id, code in (
        models.ServiceRequestService.objects.filter(
            tenant_id=_tenant_id(), request_id__in=request_ids
        )
        .order_by("created_at", "id")
        .values_list("request_id", "service__code")
    ):
        out.setdefault(str(request_id), []).append(code)
    return out


def _park_services(park: Any) -> list[str] | None:
    values = park.values if isinstance(park.values, dict) else {}
    raw = values.get("services")
    if not isinstance(raw, list):
        return None
    return [str(code) for code in raw if isinstance(code, str) and code.strip()]


def _opening_read_cell(answer: dict[str, Any] | None, account: Any, effective_on: Any) -> dict[str, Any]:
    """Image 01's OPENING READ: *Waiting* while due, the readings once taken."""
    from apps.customers import move_record_reads

    cell = move_reads.unit_reads_cell(answer, measured_from=effective_on, final=False)
    readings: list[dict[str, Any]] = []
    if cell["state"] == move_reads.READS_STATE_TAKEN and account is not None:
        reads = move_record_reads._opening_reads(
            account, effective_on=effective_on, kind=moves.KIND_MOVE_IN
        )
        readings = [
            {"register": row["register"], "reading": row.get("reading"), "unit": row.get("unit")}
            for row in reads.get("rows") or ()
            if row.get("how") == move_record_reads.HOW_READ
        ]
    return {
        "state": cell["state"],
        "meters_total": cell["meters_total"],
        "meters_read": cell["meters_read"],
        "missing": cell["missing"],
        "readings": readings,
        "unavailable": cell["unavailable"],
    }


_NO_OPENING_READ_YET: dict[str, Any] = {
    "code": "no_opening_read_before_complete",
    "br_ref": "CR-171 §6.1",
    "detail": "Opening reads are taken when the move-in is completed.",
}


def _not_yet_read() -> dict[str, Any]:
    return {
        "state": None,
        "meters_total": None,
        "meters_read": None,
        "missing": [],
        "readings": [],
        "unavailable": dict(_NO_OPENING_READ_YET),
    }


def _decorate(row: dict[str, Any], *, status: str, reference: str | None, services: list[str] | None,
              opening_read: dict[str, Any]) -> dict[str, Any]:
    row.update(
        {
            "status": status,
            "reference": reference,
            "services": services,
            "opening_read": opening_read,
            "action": _ACTION_BY_STATUS[status],
        }
    )
    return row


def _request_row(request: Any, *, as_of: date) -> dict[str, Any]:
    status = _REQUEST_STATUS_BY_STATE[request.state]
    return {
        "move_no": None,
        "move_no_unavailable": None,
        "row_kind": ROW_KIND_REQUEST,
        "request_id": str(request.id),
        "job_id": None,
        "park_id": None,
        "account_id": None,
        "account_no": None,
        "customer": request.applicant_name,
        "customer_no": None,
        "customer_source": "request_applicant",
        "customer_absence": None,
        "unit_id": str(request.resolved_unit_id) if request.resolved_unit_id else None,
        "unit": move_reads._premise_for_request(request),
        "move_in_date": request.requested_start.isoformat() if request.requested_start else None,
        "step": move_reads.move_in_step_cell(None),
        "deposit": None,
        "booked_in_on": request.created_at.date().isoformat() if request.created_at else None,
        "age_days": (as_of - request.created_at.date()).days if request.created_at else None,
        "request": {
            "id": str(request.id),
            "request_no": request.request_no,
            "state": request.state,
            "requested_start": (
                request.requested_start.isoformat() if request.requested_start else None
            ),
        },
        "actions": list(move_in_request.request_actions(request.state)),
        "_status": status,
    }


def _record_row(record: Any, account: Any, *, as_of: date, customer: dict[str, Any] | None,
                answer: dict[str, Any] | None) -> dict[str, Any]:
    effective = record.effective_on
    from apps.customers import move_record_reads

    moved_on = move_record_reads.move_in_date_of(record, account)  # `DEF-CUS-9790`
    return {
        "move_no": record.move_no,
        "move_no_unavailable": None if record.move_no else dict(moves.MOVE_NUMBER_UNAVAILABLE[record.kind]),
        "row_kind": ROW_KIND_MOVE_RECORD,
        "record_id": str(record.id),
        "request_id": str(record.request_id) if record.request_id else None,
        "job_id": None,
        "park_id": None,
        "account_id": str(record.account_id),
        "account_no": getattr(account, "account_no", None),
        "customer": (customer or {}).get("customer"),
        "customer_no": (customer or {}).get("customer_no"),
        "customer_source": (customer or {}).get("source"),
        "unit_id": str(account.unit_id) if account is not None and account.unit_id else None,
        "unit": move_reads._premise(account.unit_id) if account is not None else None,
        "move_in_date": moved_on.isoformat() if moved_on else None,
        "step": {**move_reads.move_in_step_cell(None), "done": True},
        "deposit": move_reads._deposit_cell(account) if account is not None else None,
        "booked_in_on": record.created_at.date().isoformat(),
        "age_days": (as_of - record.created_at.date()).days,
        "_opening_read": _opening_read_cell(answer, account, effective),
    }


def build_rows(keys: list[tuple[str, str, str]], *, ctx: _Context) -> list[dict[str, Any]]:
    """The page, ONE query per row kind (plus the per-page reads), in key order."""
    as_of = ctx.as_of
    by_kind: dict[str, list[str]] = {}
    for kind, key, _status in keys:
        by_kind.setdefault(kind, []).append(key)
    status_of = {key: status for _kind, key, status in keys}
    built: dict[str, dict[str, Any]] = {}

    # ── the three kinds the list already had, through their own builders ──
    accounts = (
        list(
            models.Account.objects.filter(
                tenant_id=_tenant_id(), id__in=by_kind.get(move_reads.ROW_KIND_ACCOUNT, [])
            ).select_related("status")
        )
        if by_kind.get(move_reads.ROW_KIND_ACCOUNT)
        else []
    )
    # Not `pending_queryset` — a CANCELLED job is a row of this list now.
    jobs = (
        list(
            move_in_jobs.MoveInJob.objects.filter(
                tenant_id=_tenant_id(), id__in=by_kind.get(move_reads.ROW_KIND_PENDING_JOB, [])
            ).select_related("request")
        )
        if by_kind.get(move_reads.ROW_KIND_PENDING_JOB)
        else []
    )
    parks = (
        list(_parks().filter(id__in=by_kind.get(move_reads.ROW_KIND_PARKED_MOVE_IN, [])))
        if by_kind.get(move_reads.ROW_KIND_PARKED_MOVE_IN)
        else []
    )
    unit_ids = [row.unit_id for row in accounts] + [
        job.request.resolved_unit_id for job in jobs if job.request.resolved_unit_id
    ]
    unit_ids += [
        (park.subject_ref or {}).get("unit_id")
        for park in parks
        if isinstance(park.subject_ref, dict) and (park.subject_ref or {}).get("unit_id")
    ]
    reads_answers = move_reads._unit_reads_answers(unit_ids) if unit_ids else {}
    customers = move_reads._customer_names([row.id for row in accounts])
    requests_by_no = move_reads._requests_by_account_no(
        [row.account_no for row in accounts], outcome=models.ServiceRequest.OUTCOME_MOVE_IN
    )
    account_services = _account_service_codes([row.id for row in accounts])
    for row in accounts:
        built[str(row.id)] = _decorate(
            move_reads.move_in_row(
                row,
                as_of=as_of,
                customer=customers.get(str(row.id)),
                request=requests_by_no.get(row.account_no),
                reads=move_reads.unit_reads_cell(
                    None if reads_answers is None else reads_answers.get(str(row.unit_id)),
                    measured_from=row.opened_at,
                    final=False,
                ),
            ),
            status=status_of[str(row.id)],
            reference=None,
            services=account_services.get(str(row.id), []),
            opening_read=_not_yet_read(),
        )
    job_services = _services_for_requests([str(job.request_id) for job in jobs])
    drafted_park_ids = [
        ctx.linked[str(job.request_id)] for job in jobs if str(job.request_id) in ctx.linked
    ]
    job_parks = (
        {str(p.id): p for p in _parks().filter(id__in=drafted_park_ids)} if drafted_park_ids else {}
    )
    for job in jobs:
        status = status_of[str(job.id)]
        row = move_reads.move_in_job_row(
            job,
            as_of=as_of,
            reads=move_reads.unit_reads_cell(
                None
                if reads_answers is None
                else reads_answers.get(str(job.request.resolved_unit_id)),
                measured_from=job.request.requested_start,
                final=False,
            ),
        )
        row["park_id"] = ctx.linked.get(str(job.request_id)) if status == STATUS_DRAFT else None
        if row["park_id"] and row["park_id"] in job_parks:
            # The job IS its draft now — the draft's step, in four (P1.03).
            row["step"] = move_reads.move_in_step_cell(
                move_reads.move_in_park_step(job_parks[row["park_id"]])
            )
        built[str(job.id)] = _decorate(
            row,
            status=status,
            reference=job.move_no or None,
            services=job_services.get(str(job.request_id), []),
            opening_read=_not_yet_read(),
        )
    for park in parks:
        built[str(park.id)] = _decorate(
            move_reads.move_in_park_row(
                park,
                as_of=as_of,
                reads=move_reads.unit_reads_cell(None, measured_from=None, final=False),
            ),
            status=status_of[str(park.id)],
            reference=(park.reference or "").strip() or None,
            services=_park_services(park),
            opening_read=_not_yet_read(),
        )

    # ── requests ──
    request_ids = by_kind.get(ROW_KIND_REQUEST, [])
    if request_ids:
        req_services = _services_for_requests(request_ids)
        for request in models.ServiceRequest.objects.filter(
            tenant_id=_tenant_id(), id__in=request_ids
        ):
            row = _request_row(request, as_of=as_of)
            status = row.pop("_status")
            built[str(request.id)] = _decorate(
                row,
                status=status,
                reference=request.request_no,
                services=req_services.get(str(request.id), []),
                opening_read=_not_yet_read(),
            )

    # ── committed move-ins ──
    record_ids = by_kind.get(ROW_KIND_MOVE_RECORD, [])
    if record_ids:
        records = list(
            moves.MoveRecord.objects.filter(tenant_id=_tenant_id(), id__in=record_ids)
        )
        acct_ids = [r.account_id for r in records]
        accts = {
            str(a.id): a
            for a in models.Account.objects.filter(tenant_id=_tenant_id(), id__in=acct_ids)
        }
        names = move_reads._customer_names(acct_ids)
        svc = _account_service_codes(acct_ids)
        from apps.customers import move_in_reopen

        reopened = move_in_reopen.for_move_records(record_ids)  # one query a page
        answers = seams.latest_read_dates_for_units(
            {str(a.unit_id) for a in accts.values() if a.unit_id}
        )
        for record in records:
            account = accts.get(str(record.account_id))
            row = _record_row(
                record,
                account,
                as_of=as_of,
                customer=names.get(str(record.account_id)),
                answer=(
                    None
                    if answers is None or account is None or not account.unit_id
                    else answers.get(str(account.unit_id))
                ),
            )
            opening = row.pop("_opening_read")
            built[str(record.id)] = _decorate(
                row,
                status=status_of[str(record.id)],
                reference=record.move_no,
                services=svc.get(str(record.account_id), []),
                opening_read=opening,
            )
            # CR-181-BRC10 F3 — *Reopened AC-…* and the balance choice, or None.
            built[str(record.id)]["reopened"] = reopened.get(str(record.id))
    _name_units_by_number(built.values())
    return [built[key] for _kind, key, _s in keys if key in built]


def _name_units_by_number(rows: Any) -> None:
    """`DEF-CUS-9763` — the Unit cell names the unit by its NUMBER and label.

    Images 01 and 03–17 draw `Kestrel Park ph. 2 · SCW-U-311`; every row
    builder above takes the shared `selectors._premise_cell` (address ·
    label), which other tabs print and which this does not change. So the
    move-in list re-composes its OWN cell — address · unit number · label,
    step 1's form — from ONE batched read for the page, and only on rows that
    resolved to a unit. A row with no unit keeps its address (hard rule 8).
    """
    rows = [row for row in rows if row.get("unit_id")]
    if not rows:
        return
    refs = seams.unit_refs([row["unit_id"] for row in rows])
    for row in rows:
        ref = refs.get(str(row["unit_id"]))
        if not ref:
            continue
        parts = [
            (ref.get("premise_address") or "").strip(),
            (ref.get("unit_no") or "").strip(),
            (ref.get("label") or "").strip(),
        ]
        line = " · ".join(part for part in parts if part)
        if line:
            row["unit"] = line


def _account_service_codes(account_ids: list[Any]) -> dict[str, list[str]]:
    from apps.customers import selectors

    if not account_ids:
        return {}
    accounts = list(models.Account.objects.filter(tenant_id=_tenant_id(), id__in=list(account_ids)))
    return {str(k): v for k, v in selectors.service_codes_for_accounts(accounts).items()}


# ═══════════════════════════════════════════════════════════════════════════
# 7 · status_of — the same rule for ONE object (the record page reads this)
# ═══════════════════════════════════════════════════════════════════════════
def status_of_request(request: Any) -> str | None:
    return _REQUEST_STATUS_BY_STATE.get(str(getattr(request, "state", "") or ""))


def status_of_job(job: Any) -> str:
    if job.state == move_in_jobs.STATE_CANCELLED:
        return STATUS_CANCELLED
    if str(job.request_id) in _linked_request_ids():
        return STATUS_DRAFT
    return STATUS_NOT_STARTED


def status_of_record(record: Any, account: Any) -> str:
    from apps.customers import move_in_cancel

    if account is not None and move_in_cancel.record_is_cancelled(record, account):
        return STATUS_CANCELLED
    if account is None or account.closed_at is not None or not account.unit_id:
        return STATUS_COMPLETED
    answers = seams.latest_read_dates_for_units([str(account.unit_id)])
    if answers is None:
        return STATUS_COMPLETED
    cell = move_reads.unit_reads_cell(
        answers.get(str(account.unit_id)), measured_from=record.effective_on, final=False
    )
    return STATUS_WAITING_ON_A_READ if cell["state"] == move_reads.READS_STATE_DUE else STATUS_COMPLETED


# ═══════════════════════════════════════════════════════════════════════════
# 8 · THE LIST
# ═══════════════════════════════════════════════════════════════════════════
def move_ins_list(
    *,
    q: str | None = None,
    page: int = 1,
    per: int = move_reads.DEFAULT_PER,
    as_of: date | None = None,
    filters: dict[str, Any] | None = None,
    sort: str | None = None,
    dir: str = move_reads.MOVE_DEFAULT_DIR,
) -> dict[str, Any]:
    on = move_reads._as_of(as_of)
    page = max(1, int(page or 1))
    per = max(1, min(int(per or move_reads.DEFAULT_PER), move_reads.MAX_PER))
    ctx = _Context(as_of=on)
    total, keys = page_keys(q=q, filters=filters, sort=sort, dir=dir, page=page, per=per, ctx=ctx)
    rows = build_rows(keys, ctx=ctx)
    new_tiles = tiles(ctx)
    legacy = move_reads.move_in_kpis(as_of=on)
    return {
        "rows": rows,
        # The five drawn tiles (image 01), plus the seven-step screen's own keys
        # until P2.01 replaces it. `starting_this_week` is the NEW definition
        # (every status still to start) — a superset of the old window.
        "kpis": {**legacy, **new_tiles},
        "page": page,
        "per": per,
        "total": total,
        "pages": (total + per - 1) // per if per else 0,
        "columns": list(move_reads.MOVE_IN_COLUMNS),
        "sorts": list(SORTS),
        "sort": sort if sort in SORTS else DEFAULT_SORT,
        "dir": dir,
        "statuses": list(STATUSES),
        "status_groups": {name: list(members) for name, members in STATUS_GROUPS.items()},
        "states": [dict(state) for state in move_reads.MOVE_IN_STATES],
        "filters": list(FILTERS),
        "search": {
            "hint": SEARCH_HINT,
            "min_chars": move_reads._min_search_chars(),
            "legs": SEARCH_LEGS,
            "unavailable": [
                dict(move_reads.SEARCH_REQUEST_LEG_IS_BEST_EFFORT),
                dict(move_reads.PENDING_JOB_SEARCH_LEGS_ARE_NARROWER),
                dict(move_reads.PARKED_MOVE_IN_SEARCH_LEGS_ARE_NARROWER),
            ],
        },
        "exclusion": {
            "callout": (
                "A transfer appears only here. Its two halves are deliberately kept out of "
                "Move-ins and Move-outs — the same job listed three times would be counted "
                "three times."
            ),
            "contract": list(transfers.EXCLUSION_CONTRACT),
            "half_account_ids": sorted(transfers.transfer_half_account_ids()),
        },
        # `PENDING_JOB_CLOSES_ON_THE_RECORDED_MOVE` is still exactly true. The
        # two it rode beside are not, and are retired: a request IS a row here
        # now (S3) and so is a finished move-in (S4).
        "unavailable": [dict(move_reads.PENDING_JOB_CLOSES_ON_THE_RECORDED_MOVE)],
        "as_of": on.isoformat(),
    }
